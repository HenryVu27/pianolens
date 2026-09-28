"""Tier A: note correctness labels from a score-to-performance alignment (F-02).

Every performed note gets one label, every score note gets one label, and the result is
summarised per bar and overall.

Performed notes:

* ``correct``: matched to a score note.
* ``wrong_pitch``: an unmatched performed note paired with an unmatched score note (see below).
* ``extra``: an unmatched performed note that is neither a wrong pitch nor a tolerated ornament.
* ``ornament``: an unmatched performed note next to a grace note or an ornamented score note
  (trill, mordent, turn), within ``ORNAMENT_SEMITONES`` of its pitch. Tolerated, not an error.
* ``interpolated``: a synthetic note a dataset pipeline filled in. Excluded from every count.

Score notes: ``correct``, ``wrong_pitch`` (the note the wrong pitch was meant to be),
``missed``, ``ornament_skipped`` (an unplayed grace note; tolerated), ``interpolated``.

**Wrong pitch.** The aligner matches by pitch, so a wrong key shows up as one insertion plus one
deletion, the convention of RUMAA (Chang, Dixon, Benetos, WASPAA 2025) and Nakamura, Yoshii,
Katayose (ISMIR 2017). Here such a pair is merged into one ``wrong_pitch`` when the performed
onset is within ``wrong_pitch_window_sec`` of the time the score note was expected and the
pitches differ by at most ``max_semitones`` or by an octave. Expected times come from the matched
notes: a score onset shared with matched notes gets their median performed onset; other onsets
are interpolated linearly in score quarters. Pairs are formed greedily, closest first.

**The pairing window is not an onset tolerance.** ``ONSET_TOLERANCE_SEC`` (50 ms) is the MIREX /
``mir_eval`` tolerance for deciding whether a transcribed onset hits a reference onset; it is kept
here only as a named reference value. The wrong-pitch window (``WRONG_PITCH_WINDOW_SEC``, 100 ms)
answers a different question: how far the performed onset may sit from an *estimated* expected
onset. That estimate is the median of the chord-mates' onsets (or an interpolation), so chord
spread, rolled chords and melody lead add to the error; with the ground-truth alignment 9% of
injected wrong pitches fall outside 50 ms and 5% outside 100 ms (DECISIONS 2026-09-27, F-02b,
``docs/specs/correctness-validation.md``).

**Missed notes are reliable per bar, not per note.** Which duplicate of a repeated or doubled
pitch was skipped is often ambiguous (deletion F1 0.75 in F-01, DECISIONS 2026-09-27). Read
``bars["n_missed"]`` rather than individual missed ids.

Units: counts of notes; ``accuracy`` is a fraction in [0, 1]; times in seconds.
Citations (``docs/research/2026-09-27-landscape.md`` section 1.1): note P/R/F1 with ±50 ms
(mir_eval); correct / extra / missed with wrong pitch = extra + missed (RUMAA 2025); symbolic
alignment with error detection (Nakamura et al. 2017).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

__all__ = [
    "ONSET_TOLERANCE_SEC",
    "ORNAMENT_SEMITONES",
    "WRONG_PITCH_WINDOW_SEC",
    "CorrectnessResult",
    "correctness",
    "expected_onsets",
    "measure_rows",
]

ONSET_TOLERANCE_SEC = 0.05
"""MIREX / ``mir_eval`` onset tolerance (±50 ms). Reference value only: not used for pairing."""

WRONG_PITCH_WINDOW_SEC = 0.1
"""Default max |performed onset - expected onset| for merging an insertion and a deletion into
one wrong pitch (F-02b, DECISIONS 2026-09-27). See the module docstring for why it is wider than
``ONSET_TOLERANCE_SEC``."""

ORNAMENT_SEMITONES = 2
"""Pitch range around an ornamented / grace score note within which extra notes are
tolerated (parangonar uses the same ±2 semitones for trills)."""

ORNAMENT_LEAD_SEC = 0.25
"""Ornament notes may start this long before the ornamented note's expected onset (grace notes
are played before the beat; parangonar uses the same 0.25 s)."""

GRACE_TAIL_SEC = 0.1
"""After the expected onset of a grace note's principal, extra notes stay tolerated this long."""


@dataclass(eq=False)
class CorrectnessResult:
    """Output of :func:`correctness`.

    Attributes:
        notes: one row per performed note: ``performance_id``, ``label``, ``score_id``
            (matched or intended score note, ``""`` for extras), ``onset_sec``, ``pitch``,
            ``score_pitch`` (-1 if none), ``measure_index`` (row of ``Score.measures``; -1 if
            outside the score).
        score_notes: one row per score note: ``score_id``, ``label``, ``pitch``,
            ``onset_quarter``, ``expected_onset_sec`` (NaN when there is no match to
            interpolate from), ``performance_id``, ``measure_index``.
        bars: one row per score measure (row of ``Score.measures``): ``measure_index``,
            ``measure_number``, ``measure_name``, ``n_score_notes`` (graded), ``n_correct``,
            ``n_wrong_pitch``, ``n_missed``, ``n_extra``, ``n_ornament``, ``n_interpolated``,
            ``n_errors``, ``accuracy``.
        summary: overall counts; ``accuracy`` = correct / graded score notes, ``error_rate`` =
            (wrong_pitch + missed + extra) / graded score notes, ``match_ratio`` as in
            ``pianolens.align.match_ratio`` and ``alignment_suspect`` = match_ratio < 0.8
            (docs/specs/alignment-validation.md: below that, do not trust the labels).
        params: the parameters used.
    """

    notes: pd.DataFrame
    score_notes: pd.DataFrame
    bars: pd.DataFrame
    summary: dict[str, Any]
    params: dict[str, Any] = field(default_factory=dict)


def measure_rows(measures: np.ndarray, quarters: np.ndarray) -> np.ndarray:
    """Row index into ``measures`` of each score position (quarters); -1 if outside.

    Row indices, not measure numbers: after repeat unfolding a number repeats once per pass.
    """
    q = np.asarray(quarters, dtype=float)
    out = np.full(len(q), -1, dtype=int)
    if len(measures) == 0:
        return out
    idx = np.searchsorted(measures["start_quarter"], q, side="right") - 1
    ok = (idx >= 0) & np.isfinite(q)
    idx_ok = np.clip(idx, 0, len(measures) - 1)
    ok &= q < measures["end_quarter"][idx_ok]
    out[ok] = idx[ok]
    return out


def expected_onsets(match_q: np.ndarray, match_t: np.ndarray
                    ) -> tuple[np.ndarray, np.ndarray]:
    """Monotone score-quarter -> performance-seconds map from matched notes.

    Returns ``(quarters, seconds)`` knots: one per distinct matched score onset, with the median
    performed onset, made non-decreasing. Use ``np.interp`` on them in either direction.
    """
    if len(match_q) == 0:
        return np.empty(0), np.empty(0)
    df = pd.DataFrame({"q": match_q, "t": match_t}).groupby("q", sort=True)["t"].median()
    q = df.index.to_numpy(dtype=float)
    t = np.maximum.accumulate(df.to_numpy(dtype=float))
    return q, t


def _interp(x: np.ndarray, xp: np.ndarray, fp: np.ndarray) -> np.ndarray:
    """``np.interp`` with linear extrapolation from the end knots; NaN with no knots."""
    x = np.asarray(x, dtype=float)
    if len(xp) == 0:
        return np.full(len(x), np.nan)
    if len(xp) == 1:
        return np.full(len(x), float(fp[0]))
    out = np.interp(x, xp, fp)
    lo_slope = (fp[1] - fp[0]) / max(xp[1] - xp[0], 1e-9)
    hi_slope = (fp[-1] - fp[-2]) / max(xp[-1] - xp[-2], 1e-9)
    out = np.where(x < xp[0], fp[0] + (x - xp[0]) * lo_slope, out)
    return np.where(x > xp[-1], fp[-1] + (x - xp[-1]) * hi_slope, out)


def _ornamented_ids(score: Any) -> set[str]:
    part = getattr(score, "part", None)
    if part is None:
        return set()
    return {str(n.id) for n in part.notes_tied if getattr(n, "ornaments", None)}


def correctness(
    aligned: Any,
    *,
    wrong_pitch_window_sec: float = WRONG_PITCH_WINDOW_SEC,
    max_semitones: int = 2,
    allow_octave: bool = True,
    ornaments: bool = True,
) -> CorrectnessResult:
    """Label every note of an aligned performance correct / extra / missed / wrong pitch.

    Args:
        aligned: ``pianolens.data.types.AlignedPerformance`` from
            ``pianolens.align.align_performance`` (its ``score`` must be the performed,
            unfolded score the alignment ids refer to; keep its ``part`` to use ornament marks).
        wrong_pitch_window_sec: max |performed onset - expected onset| (seconds) for merging an
            insertion and a deletion into a wrong pitch. Default ``WRONG_PITCH_WINDOW_SEC``.
        max_semitones: max pitch distance for a wrong-pitch pair (octave errors are separate).
        allow_octave: also pair notes exactly 12 semitones apart.
        ornaments: tolerate extra / unplayed notes around grace notes and ornamented notes.

    Returns:
        :class:`CorrectnessResult`. Unmatched ids that are not in the note arrays are ignored
        and counted in ``summary["n_unknown_ids"]``.
    """
    score, perf, al = aligned.score, aligned.performance, aligned.alignment
    sn, pn = score.notes, perf.notes
    s_ids = sn["id"].astype(str)
    p_ids = pn["id"].astype(str)
    s_pos = {k: i for i, k in enumerate(s_ids.tolist())}
    p_pos = {k: i for i, k in enumerate(p_ids.tolist())}

    s_label = np.full(len(sn), "missed", dtype=object)  # unaligned score notes count as missed
    p_label = np.full(len(pn), "extra", dtype=object)
    s_partner = np.full(len(sn), -1, dtype=int)
    p_partner = np.full(len(pn), -1, dtype=int)
    n_unknown = 0
    for lab, sid, pid in al.pairs.tolist():
        i = s_pos.get(sid, -1) if sid else -1
        j = p_pos.get(pid, -1) if pid else -1
        if (sid and i < 0) or (pid and j < 0):
            n_unknown += 1
        if lab in ("match", "interpolated") and i >= 0 and j >= 0:
            tag = "correct" if lab == "match" else "interpolated"
            s_label[i], p_label[j] = tag, tag
            s_partner[i], p_partner[j] = j, i
        elif lab == "ornament" and j >= 0:
            p_label[j] = "ornament"

    # score -> performance time map from played matches
    m = (s_label == "correct") & (s_partner >= 0)
    kq, kt = expected_onsets(sn["onset_quarter"][m].astype(float),
                             pn["onset_sec"][s_partner[m]].astype(float))  # fmt: skip
    exp_on = _interp(sn["onset_quarter"], kq, kt)
    exp_off = _interp(sn["onset_quarter"] + sn["duration_quarter"], kq, kt)
    p_on = pn["onset_sec"].astype(float)
    p_pitch = pn["pitch"].astype(int)
    s_pitch = sn["pitch"].astype(int)

    # ornament whitelist
    names = sn.dtype.names or ()
    is_grace = sn["is_grace"].astype(bool) if "is_grace" in names else np.zeros(len(sn), bool)
    if ornaments:
        orn_ids = _ornamented_ids(score)
        is_orn = np.array([k in orn_ids for k in s_ids.tolist()], dtype=bool)
        special = np.flatnonzero((is_grace | is_orn) & np.isfinite(exp_on))
        s_label[(s_label == "missed") & is_grace] = "ornament_skipped"
        extra_idx = np.flatnonzero(p_label == "extra")
        for i in special:
            lo = exp_on[i] - ORNAMENT_LEAD_SEC
            hi = exp_on[i] + GRACE_TAIL_SEC if is_grace[i] else max(exp_off[i], exp_on[i])
            near = extra_idx[(p_on[extra_idx] >= lo) & (p_on[extra_idx] <= hi)
                             & (np.abs(p_pitch[extra_idx] - s_pitch[i]) <= ORNAMENT_SEMITONES)]
            p_label[near] = "ornament"

    # wrong-pitch pairing: greedy, closest first
    dels = np.flatnonzero((s_label == "missed") & np.isfinite(exp_on))
    ins = np.flatnonzero(p_label == "extra")
    cands: list[tuple[float, int, int]] = []
    if len(dels) and len(ins):
        order = np.argsort(p_on[ins])
        ins_sorted, on_sorted = ins[order], p_on[ins][order]
        for i in dels:
            a = np.searchsorted(on_sorted, exp_on[i] - wrong_pitch_window_sec, side="left")
            b = np.searchsorted(on_sorted, exp_on[i] + wrong_pitch_window_sec, side="right")
            for j in ins_sorted[a:b]:
                dp = abs(int(p_pitch[j]) - int(s_pitch[i]))
                if 1 <= dp <= max_semitones or (allow_octave and dp == 12):
                    dt = abs(p_on[j] - exp_on[i])
                    # cost: time in windows + pitch (an octave costs like 3 semitones)
                    pitch_cost = (dp if dp <= max_semitones else 3) / 12
                    cands.append((dt / wrong_pitch_window_sec + pitch_cost, int(i), int(j)))
    cands.sort()
    for _, i, j in cands:
        if s_label[i] == "missed" and p_label[j] == "extra":
            s_label[i], p_label[j] = "wrong_pitch", "wrong_pitch"
            s_partner[i], p_partner[j] = j, i

    # bars
    s_bar = measure_rows(score.measures, sn["onset_quarter"])
    p_q = np.where(p_partner >= 0, sn["onset_quarter"][np.maximum(p_partner, 0)],
                   _interp(p_on, kt, kq) if len(kt) else np.nan)  # fmt: skip
    p_bar = measure_rows(score.measures, p_q)

    notes_df = pd.DataFrame({
        "performance_id": p_ids,
        "label": p_label.astype(str),
        "score_id": np.where(p_partner >= 0, s_ids[np.maximum(p_partner, 0)], ""),
        "onset_sec": p_on,
        "pitch": p_pitch,
        "score_pitch": np.where(p_partner >= 0, s_pitch[np.maximum(p_partner, 0)], -1),
        "measure_index": p_bar,
    })  # fmt: skip
    score_df = pd.DataFrame({
        "score_id": s_ids,
        "label": s_label.astype(str),
        "pitch": s_pitch,
        "onset_quarter": sn["onset_quarter"].astype(float),
        "expected_onset_sec": exp_on,
        "performance_id": np.where(s_partner >= 0, p_ids[np.maximum(s_partner, 0)], ""),
        "measure_index": s_bar,
    })  # fmt: skip
    bars = _bars(score.measures, score_df, notes_df)

    graded = int(np.isin(s_label, ("correct", "wrong_pitch", "missed")).sum())
    n = {lab: int((s_label == lab).sum()) for lab in ("correct", "wrong_pitch", "missed")}
    n_extra = int((p_label == "extra").sum())
    n_played = int((p_label != "interpolated").sum())
    ratio = 2.0 * n["correct"] / max(1, graded + n_played)
    summary = {
        "n_score_notes": graded,
        "n_performed_notes": n_played,
        "n_correct": n["correct"],
        "n_wrong_pitch": n["wrong_pitch"],
        "n_missed": n["missed"],
        "n_extra": n_extra,
        "n_ornament": int((p_label == "ornament").sum()),
        "n_ornament_skipped": int((s_label == "ornament_skipped").sum()),
        "n_interpolated": int((s_label == "interpolated").sum()),
        "n_unknown_ids": n_unknown,
        "accuracy": n["correct"] / graded if graded else float("nan"),
        "error_rate": (n["wrong_pitch"] + n["missed"] + n_extra) / graded if graded
        else float("nan"),
        "n_bars": len(bars),
        "n_bars_with_errors": int((bars["n_errors"] > 0).sum()),
        "n_bars_with_missed": int((bars["n_missed"] > 0).sum()),
        "match_ratio": ratio,
        "alignment_suspect": bool(ratio < 0.8),
    }
    params = {"wrong_pitch_window_sec": wrong_pitch_window_sec, "max_semitones": max_semitones,
              "allow_octave": allow_octave, "ornaments": ornaments}  # fmt: skip
    return CorrectnessResult(notes_df, score_df, bars, summary, params)


def _bars(measures: np.ndarray, score_df: pd.DataFrame, notes_df: pd.DataFrame) -> pd.DataFrame:
    nb = len(measures)
    bars = pd.DataFrame({
        "measure_index": np.arange(nb),
        "measure_number": measures["number"] if nb else np.empty(0, int),
        "measure_name": measures["name"] if nb else np.empty(0, str),
    })  # fmt: skip

    def count(df: pd.DataFrame, lab: str | tuple[str, ...]) -> np.ndarray:
        labs = (lab,) if isinstance(lab, str) else lab
        b = df.loc[df["label"].isin(labs) & (df["measure_index"] >= 0), "measure_index"]
        return np.bincount(b.to_numpy(dtype=int), minlength=nb)[:nb]

    bars["n_score_notes"] = count(score_df, ("correct", "wrong_pitch", "missed"))
    bars["n_correct"] = count(score_df, "correct")
    bars["n_wrong_pitch"] = count(score_df, "wrong_pitch")
    bars["n_missed"] = count(score_df, "missed")
    bars["n_extra"] = count(notes_df, "extra")
    bars["n_ornament"] = count(notes_df, "ornament")
    bars["n_interpolated"] = count(score_df, "interpolated")
    bars["n_errors"] = bars["n_wrong_pitch"] + bars["n_missed"] + bars["n_extra"]
    with np.errstate(invalid="ignore", divide="ignore"):
        bars["accuracy"] = bars["n_correct"] / bars["n_score_notes"].replace(0, np.nan)
    return bars
