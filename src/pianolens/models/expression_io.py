"""Model-agnostic interchange and per-note expression targets for score-conditioned expression
models (R-06: SyMuPe EncDec vs Pianist Transformer).

The external models run in their own virtual environments, so this module only prepares plain
arrays that any adapter can turn into MIDI:

* :func:`matched_pairs` turns an aligned performance into one row per *matched* score note, in
  score order (onset, then pitch). Unmatched score notes (deletions), extra performed notes
  (insertions) and ``interpolated`` pairs are dropped, so row ``i`` of the score side and row
  ``i`` of the performance side are the same note. Duplicate (onset, pitch) score notes keep
  the first.
* :func:`global_seconds_per_quarter` is the one global tempo number a rendition is conditioned
  on (least-squares slope of chord onset time on score onset).
* :func:`note_expression` computes the per-note targets used everywhere in R-06: velocity,
  log inter-onset-interval ratio (tempo-normalised, per score onset) and log articulation
  (key-down duration over nominal duration). The same function is applied to real, perturbed,
  deadpan and model-generated renditions, so they are compared like for like.
* :func:`onset_curves` gives one value per score onset (the curve that is averaged across
  performers for the "across-performer mean" analysis).
* :func:`deadpan` renders the matched score notes mechanically at a given tempo and velocity.
* :func:`time_signature_events` lays the score on a bar grid that starts at tick 0 (a pickup
  measure is placed at the end of an otherwise empty first bar).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

__all__ = [
    "NotePairs",
    "deadpan",
    "global_seconds_per_quarter",
    "matched_pairs",
    "note_expression",
    "onset_curves",
    "onset_groups",
    "time_signature_events",
]

_CHORD_Q = 1e-6


@dataclass(eq=False)
class NotePairs:
    """Matched score/performance notes in score order (one row per note).

    Attributes:
        score_onset_q, score_dur_q: score onset and duration in quarters.
        pitch: MIDI pitch (same on both sides).
        perf_onset_sec, perf_dur_sec: performed onset and key-down duration in seconds.
        velocity: performed MIDI velocity.
        score_id, perf_id: note ids (for traceability).
        pedal: sustain pedal events ``(time_sec, value)`` of the performance, CC 64 only.
        meta: free-form (performance id, piece id, counts of dropped notes, ...).
    """

    score_onset_q: np.ndarray
    score_dur_q: np.ndarray
    pitch: np.ndarray
    perf_onset_sec: np.ndarray
    perf_dur_sec: np.ndarray
    velocity: np.ndarray
    score_id: np.ndarray
    perf_id: np.ndarray
    pedal: np.ndarray = field(default_factory=lambda: np.zeros((0, 2)))
    meta: dict = field(default_factory=dict)

    def __len__(self) -> int:
        return len(self.pitch)

    def to_npz_dict(self, prefix: str = "") -> dict[str, np.ndarray]:
        return {
            f"{prefix}score_onset_q": self.score_onset_q.astype(float),
            f"{prefix}score_dur_q": self.score_dur_q.astype(float),
            f"{prefix}pitch": self.pitch.astype(int),
            f"{prefix}perf_onset_sec": self.perf_onset_sec.astype(float),
            f"{prefix}perf_dur_sec": self.perf_dur_sec.astype(float),
            f"{prefix}velocity": self.velocity.astype(int),
            f"{prefix}pedal": np.asarray(self.pedal, dtype=float).reshape(-1, 2),
        }

    def with_performance(self, onset: np.ndarray, dur: np.ndarray, vel: np.ndarray,
                         pedal: np.ndarray | None = None, **meta) -> NotePairs:
        """Same score side, another rendition (e.g. deadpan or a model sample)."""
        return NotePairs(
            self.score_onset_q, self.score_dur_q, self.pitch, np.asarray(onset, float),
            np.asarray(dur, float), np.asarray(vel), self.score_id, self.perf_id,
            np.zeros((0, 2)) if pedal is None else np.asarray(pedal, float),
            {**self.meta, **meta},
        )


def matched_pairs(score_notes: np.ndarray, perf_notes: np.ndarray, pairs: np.ndarray,
                  pedal: np.ndarray | None = None, meta: dict | None = None) -> NotePairs:
    """Matched notes of an alignment, in score order.

    Args:
        score_notes: score note array (``onset_quarter``, ``duration_quarter``, ``pitch``,
            ``id``); grace notes have duration 0 and are kept.
        perf_notes: performance note array (``onset_sec``, ``duration_sec``, ``velocity``,
            ``pitch``, ``id``).
        pairs: alignment rows (``ALIGNMENT_DTYPE``); only ``match`` rows are used.
        pedal: ``PEDAL_DTYPE`` array; sustain (64) events are kept.
    """
    m = pairs[pairs["label"] == "match"]
    s_ix = {sid: i for i, sid in enumerate(score_notes["id"])}
    p_ix = {pid: i for i, pid in enumerate(perf_notes["id"])}
    si, pi = [], []
    for sid, pid in zip(m["score_id"], m["performance_id"], strict=True):
        if sid in s_ix and pid in p_ix:
            si.append(s_ix[sid])
            pi.append(p_ix[pid])
    si, pi = np.array(si, dtype=int), np.array(pi, dtype=int)
    s, p = score_notes[si], perf_notes[pi]
    order = np.lexsort((s["pitch"], s["onset_quarter"]))
    s, p = s[order], p[order]
    # one performed note per (score onset, pitch) and per performed note
    key = np.round(s["onset_quarter"] / _CHORD_Q).astype(np.int64) * 128 + s["pitch"]
    _, first = np.unique(key, return_index=True)
    keep = np.zeros(len(s), bool)
    keep[first] = True
    _, pfirst = np.unique(p["id"], return_index=True)
    pkeep = np.zeros(len(p), bool)
    pkeep[pfirst] = True
    keep &= pkeep
    s, p = s[keep], p[keep]
    ped = np.zeros((0, 2))
    if pedal is not None and len(pedal):
        sus = pedal[pedal["number"] == 64]
        ped = np.stack([sus["time_sec"].astype(float), sus["value"].astype(float)], axis=1)
    info = dict(meta or {})
    info.update(n_match=int(len(m)), n_kept=int(len(s)), n_score=int(len(score_notes)),
                n_perf=int(len(perf_notes)))
    return NotePairs(
        score_onset_q=s["onset_quarter"].astype(float),
        score_dur_q=s["duration_quarter"].astype(float),
        pitch=s["pitch"].astype(int),
        perf_onset_sec=p["onset_sec"].astype(float),
        perf_dur_sec=p["duration_sec"].astype(float),
        velocity=p["velocity"].astype(int),
        score_id=s["id"].astype(str),
        perf_id=p["id"].astype(str),
        pedal=ped,
        meta=info,
    )


def onset_groups(score_onset_q: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """(group index per note, unique onsets). Notes sharing a score onset form one group."""
    uq, inv = np.unique(np.round(np.asarray(score_onset_q, float) / _CHORD_Q).astype(np.int64),
                        return_inverse=True)
    return inv, uq * _CHORD_Q


def _group_mean(values: np.ndarray, groups: np.ndarray, n: int) -> np.ndarray:
    s = np.bincount(groups, weights=values, minlength=n)
    c = np.bincount(groups, minlength=n)
    with np.errstate(invalid="ignore", divide="ignore"):
        return s / c


def global_seconds_per_quarter(score_onset_q: np.ndarray, perf_onset_sec: np.ndarray) -> float:
    """Least-squares slope of chord onset time (mean over the chord) on score onset."""
    g, uq = onset_groups(score_onset_q)
    t = _group_mean(np.asarray(perf_onset_sec, float), g, len(uq))
    if len(uq) < 2:
        return float("nan")
    x = uq - uq.mean()
    return float(np.sum(x * (t - t.mean())) / np.sum(x * x))


def note_expression(score_onset_q: np.ndarray, score_dur_q: np.ndarray,
                    perf_onset_sec: np.ndarray, perf_dur_sec: np.ndarray,
                    velocity: np.ndarray, spq: float | None = None,
                    min_dur_q: float = 1 / 16) -> pd.DataFrame:
    """Per-note expression targets.

    Columns:
        velocity: MIDI velocity.
        log_ioi: log of (performed IOI / nominal IOI) from this note's score onset to the next
            one, where performed onsets are chord means and nominal = score IOI x ``spq``; NaN
            for the last onset. Shared by the notes of a chord.
        log_art: log of key-down duration / (score duration x ``spq``); NaN for grace notes and
            notes shorter than ``min_dur_q``.
        group: score-onset group index.
    ``spq`` defaults to :func:`global_seconds_per_quarter` of this rendition, which makes the
    IOI and articulation targets tempo-normalised.
    """
    so = np.asarray(score_onset_q, float)
    sd = np.asarray(score_dur_q, float)
    po = np.asarray(perf_onset_sec, float)
    pdur = np.asarray(perf_dur_sec, float)
    if spq is None:
        spq = global_seconds_per_quarter(so, po)
    g, uq = onset_groups(so)
    t = _group_mean(po, g, len(uq))
    with np.errstate(invalid="ignore", divide="ignore"):
        ioi = np.diff(t) / (np.diff(uq) * spq)
        lg = np.full(len(uq), np.nan)
        ok = ioi > 0
        lg[:-1][ok] = np.log(ioi[ok])
        art = np.full(len(so), np.nan)
        ok = (sd >= min_dur_q) & (pdur > 0)
        art[ok] = np.log(pdur[ok] / (sd[ok] * spq))
    return pd.DataFrame({
        "velocity": np.asarray(velocity, float),
        "log_ioi": lg[g],
        "log_art": art,
        "group": g,
    })


def onset_curves(expr: pd.DataFrame) -> pd.DataFrame:
    """One row per score onset: mean velocity and log IOI ratio of the chord."""
    return expr.groupby("group")[["velocity", "log_ioi"]].mean()


def deadpan(pairs: NotePairs, spq: float, velocity: float, legato: float = 0.95) -> NotePairs:
    """Mechanical rendition: exact score timing at ``spq`` seconds per quarter, constant
    velocity, durations ``legato`` x nominal (grace notes get 1/16 quarter)."""
    so = pairs.score_onset_q - pairs.score_onset_q.min()
    dur = np.where(pairs.score_dur_q > 0, pairs.score_dur_q, 1 / 16) * spq * legato
    vel = np.full(len(pairs), int(round(velocity)))
    return pairs.with_performance(so * spq, dur, vel, None, rendition="deadpan")


def time_signature_events(measures: np.ndarray, score_notes: np.ndarray
                          ) -> tuple[float, list[tuple[float, int, int]]]:
    """Origin (in quarters) and time signature events ``(quarter, num, den)`` relative to it.

    The origin is chosen so bar lines fall on multiples of the bar length: for a pickup
    measure, origin = end of the first measure minus a full bar. Time signatures per measure
    are read from the note array fields ``ts_beats`` / ``ts_beat_type`` (the first note that
    starts in the measure); measures without notes inherit the previous signature.
    """
    if len(measures) == 0:
        return float(np.min(score_notes["onset_quarter"])), [(0.0, 4, 4)]
    has_ts = "ts_beats" in (score_notes.dtype.names or ())
    on = score_notes["onset_quarter"]
    sigs: list[tuple[int, int]] = []
    prev = (4, 4)
    for st, en in zip(measures["start_quarter"], measures["end_quarter"], strict=True):
        if has_ts:
            k = np.where((on >= st - 1e-9) & (on < en - 1e-9))[0]
            if len(k):
                prev = (int(score_notes["ts_beats"][k[0]]), int(score_notes["ts_beat_type"][k[0]]))
        sigs.append(prev)
    num, den = sigs[0]
    bar_q = num * 4.0 / den
    first_len = float(measures["end_quarter"][0] - measures["start_quarter"][0])
    origin = float(measures["start_quarter"][0])
    if first_len < bar_q - 1e-6:
        origin = float(measures["end_quarter"][0]) - bar_q
    events = [(0.0, num, den)]
    for (st, (n_, d_)) in zip(measures["start_quarter"][1:], sigs[1:], strict=True):
        if (n_, d_) != (events[-1][1], events[-1][2]):
            events.append((float(st) - origin, n_, d_))
    return origin, events
