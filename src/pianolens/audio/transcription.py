"""Transcription quality measures without and with ground truth (A-01).

* :func:`note_f1`: note-level precision / recall / F1 between two note lists (same pitch, onset
  within a tolerance, one-to-one), the onset-only metric of mir_eval's ``transcription`` module
  (Raffel et al. 2014). Used both against ground truth and between two transcribers of the same
  audio (their agreement is an uncertainty estimate when no ground truth exists).
* :func:`onset_sanity`: cheap checks on a transcribed note list that flag gross failures
  (double-triggered notes, very short notes, notes outside the piano range).
* :func:`pedal_summary`: sustain / soft pedal usage from ``Performance.pedal``-style events.
* :func:`velocity_agreement`: straight-line fit of one velocity list on another.

Transcription output is low-confidence for velocity, offsets and pedal (``rules/audio.md``); these
functions measure, they do not correct.
"""

from __future__ import annotations

from collections import defaultdict

import numpy as np
import pandas as pd

__all__ = ["match_notes", "note_f1", "onset_sanity", "pedal_summary", "robust_sd",
           "velocity_agreement"]  # fmt: skip


def robust_sd(x: np.ndarray) -> float:
    """1.4826 x median absolute deviation (NaN for fewer than 2 values)."""
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    if len(x) < 2:
        return float("nan")
    return float(1.4826 * np.median(np.abs(x - np.median(x))))


def _as_frame(notes) -> pd.DataFrame:  # noqa: ANN001 - structured array or DataFrame
    return pd.DataFrame({"onset_sec": np.asarray(notes["onset_sec"], dtype=float),
                         "pitch": np.asarray(notes["pitch"], dtype=int)})  # fmt: skip


def match_notes(ref, est, onset_tol: float = 0.05, offset: float = 0.0  # noqa: ANN001
                ) -> list[tuple[int, int]]:
    """One-to-one matches (ref index, est index): same pitch, ``|est - offset - ref| <= tol``.

    Per pitch, both lists are walked in time order and each ref note takes the earliest unused
    est note within tolerance. With one tolerance for all notes of an interval graph on a line,
    this greedy matching has maximum cardinality.
    """
    r, e = _as_frame(ref), _as_frame(est)
    e_on = e["onset_sec"].to_numpy() - offset
    by_pitch: dict[int, list[int]] = defaultdict(list)
    for j in np.argsort(e_on, kind="stable"):
        by_pitch[int(e["pitch"].iat[j])].append(int(j))
    ptr: dict[int, int] = defaultdict(int)
    out = []
    for i in np.argsort(r["onset_sec"].to_numpy(), kind="stable"):
        p, t = int(r["pitch"].iat[i]), float(r["onset_sec"].iat[i])
        cand = by_pitch.get(p, [])
        k = ptr[p]
        while k < len(cand) and e_on[cand[k]] < t - onset_tol:
            k += 1
        ptr[p] = k
        if k < len(cand) and abs(e_on[cand[k]] - t) <= onset_tol:
            out.append((int(i), cand[k]))
            ptr[p] = k + 1
    return out


def note_f1(ref, est, onset_tol: float = 0.05, estimate_offset: bool = False  # noqa: ANN001
            ) -> dict[str, float]:
    """Onset-only note precision / recall / F1 of ``est`` against ``ref``.

    ``estimate_offset``: first match at 0.2 s tolerance and remove the median onset difference
    (for two clocks that differ by a constant, e.g. a trimmed recording). The removed offset is
    returned as ``offset_sec``. ``onset_err_rsd_ms`` is the robust SD of matched onset errors.
    """
    offset = 0.0
    if estimate_offset:
        m0 = match_notes(ref, est, onset_tol=0.2)
        if m0:
            r, e = _as_frame(ref), _as_frame(est)
            offset = float(np.median([e["onset_sec"].iat[j] - r["onset_sec"].iat[i]
                                      for i, j in m0]))  # fmt: skip
    m = match_notes(ref, est, onset_tol=onset_tol, offset=offset)
    n_ref, n_est, n_m = len(ref["pitch"]), len(est["pitch"]), len(m)
    p = n_m / n_est if n_est else float("nan")
    rc = n_m / n_ref if n_ref else float("nan")
    f = 2 * p * rc / (p + rc) if n_m else 0.0
    r_on = np.asarray(ref["onset_sec"], dtype=float)
    e_on = np.asarray(est["onset_sec"], dtype=float)
    err = np.array([e_on[j] - offset - r_on[i] for i, j in m]) * 1000.0
    return {"precision": p, "recall": rc, "f1": f, "n_ref": n_ref, "n_est": n_est,
            "n_match": n_m, "offset_sec": offset, "onset_err_rsd_ms": robust_sd(err),
            "onset_err_mean_ms": float(np.mean(err)) if len(err) else float("nan")}  # fmt: skip


def velocity_agreement(ref_vel: np.ndarray, est_vel: np.ndarray) -> dict[str, float]:
    """Fit ``est = a + b * ref``: slope, Spearman rho and robust residual SD (MIDI units)."""
    x, y = np.asarray(ref_vel, float), np.asarray(est_vel, float)
    if len(x) < 3:
        return {"vel_slope": float("nan"), "vel_spearman": float("nan"),
                "vel_resid_rsd_midi": float("nan")}  # fmt: skip
    b, a = np.polyfit(x, y, 1)
    return {"vel_slope": float(b),
            "vel_spearman": float(pd.Series(x).corr(pd.Series(y), method="spearman")),
            "vel_resid_rsd_midi": robust_sd(y - (a + b * x))}  # fmt: skip


def onset_sanity(notes, double_trigger_sec: float = 0.05, short_sec: float = 0.03  # noqa: ANN001
                 ) -> dict[str, float]:
    """Gross-failure checks on a performance note array (``onset_sec``, ``duration_sec``,
    ``pitch``, ``velocity``).

    * ``share_double_trigger``: notes whose same-pitch predecessor started less than
      ``double_trigger_sec`` earlier (a piano cannot repeat a key that fast; a transcriber
      that splits one note in two can);
    * ``share_short``: notes shorter than ``short_sec`` (key-down time);
    * ``share_out_of_range``: pitches outside A0-C8 (21-108);
    * ``notes_per_sec`` over the span from first to last onset, and velocity mean / SD.
    """
    on = np.asarray(notes["onset_sec"], float)
    pitch = np.asarray(notes["pitch"], int)
    dur = np.asarray(notes["duration_sec"], float)
    vel = np.asarray(notes["velocity"], float)
    n = len(on)
    if n == 0:
        return {"n_notes": 0}
    order = np.lexsort((on, pitch))
    same = pitch[order][1:] == pitch[order][:-1]
    gap = np.diff(on[order])
    n_double = int(np.sum(same & (gap < double_trigger_sec)))
    span = float(on.max() - on.min())
    return {"n_notes": n,
            "notes_per_sec": n / span if span > 0 else float("nan"),
            "share_double_trigger": n_double / n,
            "share_short": float(np.mean(dur < short_sec)),
            "share_out_of_range": float(np.mean((pitch < 21) | (pitch > 108))),
            "pitch_min": int(pitch.min()), "pitch_max": int(pitch.max()),
            "vel_mean": float(vel.mean()), "vel_sd": float(vel.std())}  # fmt: skip


def pedal_summary(pedal, start_sec: float, end_sec: float, number: int = 64,  # noqa: ANN001
                  threshold: int = 64) -> dict[str, float]:
    """Pedal ``number`` (64 sustain, 67 soft) over ``[start_sec, end_sec]``: number of presses,
    share of the time held down, median press length. ``pedal``: rows of
    (``time_sec``, ``number``, ``value``) sorted by time; down = value >= ``threshold``."""
    span = end_sec - start_sec
    if pedal is None or len(pedal) == 0 or span <= 0:
        return {"n_presses": 0, "down_fraction": 0.0, "median_press_sec": float("nan")}
    ev = [(float(t), int(v)) for t, k, v in zip(pedal["time_sec"], pedal["number"],
                                                 pedal["value"], strict=True) if int(k) == number]
    down_at, presses = None, []
    for t, v in ev:
        if v >= threshold and down_at is None:
            down_at = t
        elif v < threshold and down_at is not None:
            presses.append((down_at, t))
            down_at = None
    if down_at is not None:
        presses.append((down_at, end_sec))
    held = sum(max(0.0, min(b, end_sec) - max(a, start_sec)) for a, b in presses)
    return {"n_presses": len(presses), "down_fraction": held / span,
            "median_press_sec": float(np.median([b - a for a, b in presses])) if presses
            else float("nan")}  # fmt: skip
