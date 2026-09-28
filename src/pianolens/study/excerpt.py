"""Cut an aligned performance to a range of score bars, for listening stimuli (S-03).

Cut *after* degrading: degradations such as tempo flattening move events in time, so the cut
is placed by score bars through the alignment of each version, not by fixed seconds.

The cut keeps every performed note whose onset lies in ``[t_start, t_end)``: ``t_start`` is the
earliest matched onset in the first bar, ``t_end`` the median onset of the first score position
of the bar after the range (or the last offset when the range ends the piece). Notes still held
at ``t_end`` are cut at ``t_end + release_sec``. The sustain pedal state at ``t_start`` is set at
time 0, pedal events after ``t_end`` are dropped and the pedal is lifted at
``t_end + release_sec``. Times are shifted so the first onset sits at ``lead_in_sec``.
"""

from __future__ import annotations

import dataclasses
from typing import Any

import numpy as np

from pianolens.data.types import PEDAL_DTYPE, AlignedPerformance, Alignment, Score

__all__ = ["bar_window", "excerpt"]


def bar_window(ap: AlignedPerformance, first_bar: int, last_bar: int) -> tuple[float, float]:
    """(t_start, t_end) in performance seconds of measure rows ``first_bar..last_bar``
    (row indices into ``score.measures``, inclusive; unfolded order)."""
    from pianolens.features._score_utils import matched_note_frame

    df, _ = matched_note_frame(ap)
    inside = df[(df["measure_idx"] >= first_bar) & (df["measure_idx"] <= last_bar)]
    if inside.empty:
        raise ValueError(f"no matched notes in measure rows {first_bar}..{last_bar}")
    t_start = float(inside["onset_sec"].min())
    after = df[df["measure_idx"] > last_bar]
    if after.empty:
        n = ap.performance.notes
        t_end = float((n["onset_sec"] + n["duration_sec"]).max())
    else:
        first_q = after["quarter"].min()
        t_end = float(after.loc[after["quarter"] == first_q, "onset_sec"].median())
    return t_start, t_end


def _cut_score(score: Score, first_bar: int, last_bar: int) -> Score:
    from pianolens.features.correctness import measure_rows

    rows = measure_rows(score.measures, score.notes["onset_quarter"].astype(float))
    keep = (rows >= first_bar) & (rows <= last_bar)
    meta = {**score.meta, "excerpt_bar_rows": (first_bar, last_bar)}
    return dataclasses.replace(score, notes=score.notes[keep].copy(),
                               measures=score.measures[first_bar:last_bar + 1].copy(),
                               meta=meta, part=None)  # fmt: skip


def excerpt(ap: AlignedPerformance, first_bar: int, last_bar: int, *, lead_in_sec: float = 0.25,
            release_sec: float = 1.0, cut_score: bool = True, tag: str | None = None
            ) -> AlignedPerformance:
    """Excerpt of measure rows ``first_bar..last_bar`` (inclusive) as a new aligned performance.

    Performed notes matched to score notes inside the bars are kept, plus unmatched performed
    notes (insertions) whose onset lies in the window; notes matched to score notes outside the
    bars are dropped even if played inside the window. With ``cut_score`` the score is cut to
    the same bars (measure rows then restart at 0) and loses its partitura ``part``, so
    harmony, tempo and melody analyses of the excerpt see only these bars. The alignment keeps
    the pairs of kept notes and the deletions inside the bars. ``meta["excerpt"]`` records the
    window.
    """
    from pianolens.features.correctness import measure_rows

    perf = ap.performance
    t0, t1 = bar_window(ap, first_bar, last_bar)
    n = perf.notes
    ids = n["id"].astype(str)
    srow = dict(zip(ap.score.notes["id"].astype(str),
                    measure_rows(ap.score.measures, ap.score.notes["onset_quarter"].astype(float)),
                    strict=True))  # fmt: skip
    matched_row: dict[str, int] = {}
    if ap.alignment is not None:
        for _lab, sid, pid in ap.alignment.pairs.tolist():
            if pid and sid:
                matched_row[pid] = srow.get(sid, -1)
    in_window = (n["onset_sec"] >= t0 - 0.03) & (n["onset_sec"] < t1 - 1e-4)
    keep = np.array([
        (first_bar <= matched_row[i] <= last_bar) if i in matched_row else bool(w)
        for i, w in zip(ids, in_window, strict=True)
    ], dtype=bool)  # fmt: skip
    notes = n[keep].copy()
    start = float(notes["onset_sec"].min()) if len(notes) else t0
    shift = lead_in_sec - start
    end_cut = t1 + release_sec
    off = np.minimum(notes["onset_sec"] + notes["duration_sec"], end_cut)
    notes["duration_sec"] = np.maximum(0.02, off - notes["onset_sec"])
    notes["onset_sec"] = notes["onset_sec"] + shift
    names = notes.dtype.names or ()
    for f in ("onset_tick", "duration_tick"):  # ticks are meaningless after the cut
        if f in names:
            notes[f] = 0

    ped = perf.pedal
    rows = []
    for num in np.unique(ped["number"]) if len(ped) else []:
        p = ped[ped["number"] == num]
        p = p[np.argsort(p["time_sec"], kind="stable")]
        k = int(np.searchsorted(p["time_sec"], start, side="right")) - 1
        v0 = int(p["value"][k]) if k >= 0 else 0
        rows.append((0.0, int(num), v0))
        inside = p[(p["time_sec"] > start) & (p["time_sec"] < end_cut)]
        rows += [(float(t) + shift, int(num), int(v)) for t, _, v in inside.tolist()]
        rows.append((end_cut + shift, int(num), 0))
    pedal = np.array(rows, dtype=PEDAL_DTYPE) if rows else np.zeros(0, PEDAL_DTYPE)
    pedal = pedal[np.argsort(pedal["time_sec"], kind="stable")]

    kept_ids = set(notes["id"].astype(str).tolist())
    new_id = f"{perf.performance_id}@b{first_bar}-{last_bar}" if tag is None else tag
    al: Alignment | None = None
    if ap.alignment is not None:
        pairs = [
            (lab, sid, pid) for lab, sid, pid in ap.alignment.pairs.tolist()
            if (pid and pid in kept_ids)
            or (not pid and first_bar <= srow.get(sid, -1) <= last_bar)
        ]
        al = Alignment(np.array(pairs, dtype=ap.alignment.pairs.dtype), ap.alignment.score_id,
                       new_id, ap.alignment.ground_truth, f"{ap.alignment.source}+excerpt")
    meta: dict[str, Any] = {**perf.meta, "excerpt": {
        "first_bar_row": first_bar, "last_bar_row": last_bar, "t_start_sec": t0,
        "t_end_sec": t1, "shift_sec": shift, "release_sec": release_sec,
        "duration_sec": (t1 - start) + lead_in_sec}}  # fmt: skip
    new_perf = dataclasses.replace(perf, performance_id=new_id, notes=notes, pedal=pedal,
                                   meta=meta)  # fmt: skip
    score = _cut_score(ap.score, first_bar, last_bar) if cut_score else ap.score
    return AlignedPerformance(new_perf, score, al)
