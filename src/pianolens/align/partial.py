"""Partial recordings: which contiguous span of the score a performance covers (BL-36).

parangonar's ``DualDTWNoteMatcher`` starts with a global onset DTW (``OnsetMatcherDTW``: each
performed pitch against the set of pitches at each score onset, cost 0 if the pitch is in the
set and 1 otherwise; parangonar ``dp.metrics.element_of_set_metric``). That DTW is anchored at
both ends, so a recording of part of a piece is stretched over the whole score: the unplayed
bars are aligned and graded, and after a start cut the played part can land on an earlier
occurrence of repeated material (BL-27: Chopin Op. 20, 116 bars early).

Here the same DTW runs with the score end left open at both ends (subsequence DTW; Müller,
*Fundamentals of Music Processing*, 2015, section 7.2), on every repeat path of the score that
``align`` would consider. Every performed note must be covered; the score span that covers them
at the lowest cost is the recorded span. The occurrence of repeated material is therefore chosen
by the global cost of the whole performance, not by first match. The note alignment itself is
still parangonar's, run on the score trimmed to the span (:func:`pianolens.align.core.align`).

Steps (``align(..., partial=True)``):

1. :func:`detect_span` per repeat path: DTW span in measure rows of the unfolded path. A side
   whose excluded rows hold at most ``snap_notes`` score notes snaps to the piece edge (sparse
   openings and codas tie in the DTW). A path whose span snaps to the whole piece and whose cost
   is within ``whole_tol`` x performed notes of the best cost wins; then the recording is whole
   and ``align`` runs exactly as without this module (byte-identical output). Otherwise the
   cheapest span wins (near ties: fewer excluded rows, then ``align``'s own ranking).
2. Each trimmed side is widened by at least ``MARGIN_BARS`` rows and ``MARGIN_NOTES`` score
   notes (:func:`widen_rows`; a sparse opening the DTW left out is reached this way), the score
   is trimmed and aligned (parangonar), and each trimmed side is shrunk back while its edge row
   has no graded notes or at least ``SHRINK_SHARE`` of them missed (:func:`shrink_rows`). Notes
   If the shrink moved an edge, the score is trimmed to the final rows and aligned again (BL-37;
   BL-36 filtered the widened alignment instead, which left a note tied across the new edge
   unmatched and its performed note extra). A note tied in from before the first row is
   optional (BL-37): kept when the performance matched it (a learner starting at that bar
   strikes it again), dropped from the score when it is unmatched (the uncut score counts it in
   the bar before). If nothing is left out in the end, the recording is whole after all.

Units: DTW cost in mismatched cells (a performed pitch absent from the onset it is mapped to, or
a score onset passed without a matching pitch); spans in measure rows of the unfolded score
(inclusive); ``snap_notes`` in score notes; ``shrink_share`` a share of a row's score notes.
"""

from __future__ import annotations

import copy
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import partitura as pt

__all__ = ["MARGIN_BARS", "MARGIN_NOTES", "PARTIAL_DEFAULT", "RecordedSpan", "SHRINK_SHARE",
           "SNAP_NOTES", "WHOLE_TOL", "detect_span", "measure_labels", "onset_pitch_sets",
           "shrink_rows", "subsequence_onset_dtw", "trim_part", "widen_rows", "edge_tails",
           "drop_notes", "EDGE_TAILS_ATTR", "margin_needed", "MARGIN_EXPLAINS_NOTES",
           "MARGIN_EXPLAINS_SHARE"]

PARTIAL_DEFAULT = False
"""Whether the report (``report_from_files``, the CLI and the app) detects the recorded span by
default. Off until the BL-36 check is audited and the lead accepts it."""

SNAP_NOTES = 8
"""A side of the detected span snaps to the piece edge when the rows it leaves out hold at most
this many score notes (grace notes excluded). Used to decide whether a repeat path's span is the
whole piece; edge rows the DTW leaves out wrongly are recovered by the margin (step 2)."""

WHOLE_TOL = 0.02
"""A whole-piece span wins when its DTW cost is at most the best cost plus this share of the
performed notes; also the near-tie band between partial spans."""

MARGIN_BARS = 2
"""Rows added on each trimmed side of the DTW span before the note alignment (at least)."""

MARGIN_NOTES = 16
"""Score notes (grace notes excluded) added on each trimmed side of the DTW span before the
note alignment (at least; whole rows, up to the piece edge)."""

MARGIN_EXPLAINS_NOTES = 3
"""BL-37: margin rows kept beyond the DTW span are used only when the performed notes matched in
them include at least this many that the alignment of the DTW span leaves unmatched ..."""

MARGIN_EXPLAINS_SHARE = 0.5
"""... and at least this share of them (:func:`margin_needed`)."""

SHRINK_SHARE = 0.5
"""After the note alignment a trimmed side loses edge rows with at least this share of their
score notes missed (or no score notes), until a row is mostly found."""


@dataclass
class RecordedSpan:
    """The recorded span of one performance.

    Attributes:
        variant: repeat path of the span (``align``'s variant string; ``""`` without repeats).
        first_row, last_row: measure rows of the unfolded variant inside the span (inclusive).
        n_rows: measure rows of the unfolded variant.
        whole: True when the span is taken as the whole piece (``align`` is then unchanged).
        cost: subsequence DTW cost of the chosen span.
        cost_whole: lowest DTW cost of a span that snaps to the whole piece (None if none does).
        dtw_rows: the chosen path's DTW span (first, last row) before snapping and refinement.
        candidates: per repeat path the raw DTW result (``cost``, ``first_row``, ``last_row``,
            ``n_rows``, and score notes left out before / after the span).
        refined: True when step 2 ran (widen, note alignment on the trimmed score, shrink). A
            whole span with ``refined`` False is the unchanged ``align`` result.
        fallback: set when the span was not searched because the score has too many repeat
            paths (``core.PARTIAL_MAX_PATHS``, DF-17), e.g. ``"512 repeat paths"``; the span is
            then the whole piece and the alignment is ``partial=False``'s.
    """

    variant: str
    first_row: int
    last_row: int
    n_rows: int
    whole: bool
    cost: float
    cost_whole: float | None = None
    dtw_rows: tuple[int, int] = (0, 0)
    candidates: dict[str, dict[str, Any]] = field(default_factory=dict)
    refined: bool = False
    fallback: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {"variant": self.variant, "first_row": self.first_row, "last_row": self.last_row,
                "n_rows": self.n_rows, "whole": self.whole, "cost": self.cost,
                "cost_whole": self.cost_whole, "dtw_rows": list(self.dtw_rows),
                "refined": self.refined}


def onset_pitch_sets(score_na: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Unique onsets of the non-grace score notes and their pitch sets, as parangonar's
    ``OnsetMatcherDTW`` builds them. Returns ``(onset_beat, onset_div, member)`` with
    ``member[j, p]`` True when pitch ``p`` starts at onset ``j``."""
    # ``is_grace`` is an integer field in partitura note arrays: ``~`` would be a bitwise not
    na = score_na[~score_na["is_grace"].astype(bool)] \
        if "is_grace" in (score_na.dtype.names or ()) else score_na
    ob, inv = np.unique(na["onset_beat"], return_inverse=True)
    member = np.zeros((len(ob), 128), dtype=bool)
    member[inv, np.clip(na["pitch"].astype(int), 0, 127)] = True
    od = np.zeros(len(ob), dtype=np.int64)
    od[inv] = na["onset_div"]
    return ob, od, member


def subsequence_onset_dtw(pitches: np.ndarray, member: np.ndarray) -> tuple[float, int, int]:
    """Subsequence DTW of a performed pitch sequence against score onset pitch sets.

    Same local cost and steps as parangonar's ``DTWSL`` with ``element_of_set_metric``
    (diagonal, vertical and horizontal steps, each adding the local cost of the cell entered),
    but the path may enter the score at any onset and leave it at any later one; every performed
    note is covered (Müller 2015, section 7.2). Returns ``(cost, first_onset, last_onset)`` of
    the cheapest path; ties go to the earliest end and, for that end, the latest start. Each row
    is computed in closed form (a horizontal chain is a prefix minimum of cumulative costs), and
    only two rows are kept, so memory is O(onsets).
    """
    pitches = np.clip(np.asarray(pitches, dtype=int), 0, 127)
    n = member.shape[0]
    if n == 0 or len(pitches) == 0:
        raise ValueError("empty score or performance")
    cols = np.arange(n)
    cost_cols = (~member).astype(np.float64)  # (n, 128): cost of each pitch at each onset
    d_prev = cost_cols[:, pitches[0]].copy()  # free start: no accumulation along the first row
    s_prev = cols.copy()  # start column of the best path into each cell
    diag = np.empty(n)
    for p in pitches[1:]:
        c = cost_cols[:, p]
        diag[0] = np.inf
        diag[1:] = d_prev[:-1]
        use_diag = diag <= d_prev
        a = c + np.where(use_diag, diag, d_prev)
        s_a = np.where(use_diag, np.r_[0, s_prev[:-1]], s_prev)
        # horizontal chains: D[j] = S[j] + min_{k<=j} (A[k] - S[k]), S the cumulative cost
        cs = np.cumsum(c)
        v = a - cs
        m = np.minimum.accumulate(v)
        k = np.maximum.accumulate(np.where(v <= m, cols, -1))
        d_prev = cs + m
        s_prev = s_a[k]
    j1 = int(np.argmin(d_prev))
    return float(d_prev[j1]), int(s_prev[j1]), j1


def _measure_starts(part: Any) -> np.ndarray:
    return np.array(sorted(m.start.t for m in part.measures))


def _rows_of_divs(starts: np.ndarray, divs: np.ndarray) -> np.ndarray:
    rows = np.searchsorted(starts, divs, side="right") - 1
    return np.clip(rows, 0, max(0, len(starts) - 1))


def span_on_part(part: Any, perf_na: np.ndarray) -> dict[str, Any]:
    """Subsequence DTW span of ``perf_na`` on one unfolded part, in measure rows, with the
    score notes (grace notes excluded) left out before and after it."""
    from pianolens.align.core import score_note_array

    sna = score_note_array(part)
    _, od, member = onset_pitch_sets(sna)
    order = np.argsort(perf_na["onset_sec"], kind="stable")
    cost, j0, j1 = subsequence_onset_dtw(perf_na["pitch"][order], member)
    starts = _measure_starts(part)
    r0, r1 = (int(r) for r in _rows_of_divs(starts, od[[j0, j1]]))
    ng = sna[~sna["is_grace"].astype(bool)]
    note_rows = _rows_of_divs(starts, ng["onset_div"])
    return {"cost": cost, "first_row": r0, "last_row": r1, "n_rows": len(starts),
            "notes_before": int((note_rows < r0).sum()),
            "notes_after": int((note_rows > r1).sum()), "n_notes": int(len(ng)),
            "first_note_row": int(note_rows.min()), "last_note_row": int(note_rows.max())}


def detect_span(variants: Sequence[tuple[str, Any]], perf_na: np.ndarray, *,
                snap_notes: int | None = None, whole_tol: float | None = None) -> RecordedSpan:
    """Choose the repeat path and the recorded span (module docstring, step 1).

    ``variants``: ``[(variant_string, unfolded_part), ...]`` in the order ``align``'s "auto"
    ranking would try them (the order breaks ties). ``None`` = the module constants, read at
    call time.
    """
    snap_notes = SNAP_NOTES if snap_notes is None else snap_notes
    whole_tol = WHOLE_TOL if whole_tol is None else whole_tol
    tol = whole_tol * len(perf_na)
    rows = []
    cands: dict[str, dict[str, Any]] = {}
    for rank, (v, upart) in enumerate(variants):
        d = span_on_part(upart, perf_na)
        cands[v] = d
        f = 0 if d["notes_before"] <= snap_notes else d["first_row"]
        last = d["n_rows"] - 1 if d["notes_after"] <= snap_notes else d["last_row"]
        whole = f == 0 and last == d["n_rows"] - 1
        out = f + (d["n_rows"] - 1 - last)
        rows.append({"v": v, "d": d, "f": f, "l": last, "whole": whole, "out": out,
                     "rank": rank})
    best = min(r["d"]["cost"] for r in rows)
    wholes = [r for r in rows if r["whole"]]
    cost_whole = min((r["d"]["cost"] for r in wholes), default=None)
    if cost_whole is not None and cost_whole <= best + tol:
        r = min(wholes, key=lambda r: r["rank"])
        d = r["d"]
        return RecordedSpan(r["v"], 0, d["n_rows"] - 1, d["n_rows"], True, d["cost"],
                            cost_whole, (d["first_row"], d["last_row"]), cands)
    near = [r for r in rows if r["d"]["cost"] <= best + tol]
    r = min(near, key=lambda r: (r["out"], r["d"]["cost"], r["rank"]))
    d = r["d"]
    return RecordedSpan(r["v"], int(r["f"]), int(r["l"]), d["n_rows"], False, d["cost"],
                        cost_whole, (d["first_row"], d["last_row"]), cands)


def trim_part(part: Any, first_row: int, last_row: int, *, inplace: bool = False) -> Any:
    """An unfolded ``part`` keeping only measure rows ``first_row..last_row``.

    Notes starting outside the rows and the measures outside them are removed; everything else
    (time signatures, directions, positions in divs and beats, note ids) is kept, so the trimmed
    part has the same beat and quarter coordinates as the full one. A note tied across the span
    edge loses the tie (its part inside the span stays a note of its own). ``inplace=False``
    works on a deep copy, which can exceed the recursion limit on long parts (the timeline is a
    linked list): ``align`` passes a freshly unfolded part with ``inplace=True`` instead.
    """
    p = part if inplace else copy.deepcopy(part)
    ms = sorted(p.measures, key=lambda m: m.start.t)
    t0 = ms[first_row].start.t
    t1 = ms[last_row].end.t
    tails = []
    for n in list(p.iter_all(pt.score.GenericNote, include_subclasses=True)):
        if not (t0 <= n.start.t < t1):
            if n.tie_next is not None:
                if n.start.t < t0 and t0 <= n.tie_next.start.t < t1:
                    tails.append(n.tie_next)
                n.tie_next.tie_prev = None
            if n.tie_prev is not None:
                n.tie_prev.tie_next = None
            p.remove(n)
    for k, m in enumerate(ms):
        if k < first_row or k > last_row:
            p.remove(m)
    setattr(p, EDGE_TAILS_ATTR, sorted({str(n.id) for n in tails}))
    return p


EDGE_TAILS_ATTR = "pianolens_edge_tails"
"""Attribute :func:`trim_part` sets on the trimmed part: ids of notes tied in from before the
first row (their tie head was removed). BL-37: they are optional in ``align``'s partial path."""


def edge_tails(part: Any) -> list[str]:
    """Ids of the notes :func:`trim_part` found tied in from before the span (BL-37)."""
    return list(getattr(part, EDGE_TAILS_ATTR, None) or [])


def drop_notes(part: Any, ids: set[str]) -> Any:
    """Remove the notes with these ids from ``part`` (in place) and return it."""
    for n in list(part.iter_all(pt.score.GenericNote, include_subclasses=True)):
        if str(n.id) in ids:
            if n.tie_next is not None:
                n.tie_next.tie_prev = None
            if n.tie_prev is not None:
                n.tie_prev.tie_next = None
            part.remove(n)
    return part


def widen_rows(row_notes: Sequence[int], first: int, last: int, widen_first: bool,
               widen_last: bool, bars: int | None = None,
               notes: int | None = None) -> tuple[int, int]:
    """Step 2's margin on per-row note counts: move ``first`` back (``widen_first``) by at
    least ``bars`` rows and until at least ``notes`` score notes are added, or to row 0; and
    ``last`` forward likewise. None = ``MARGIN_BARS`` / ``MARGIN_NOTES`` at call time."""
    bars = MARGIN_BARS if bars is None else bars
    notes = MARGIN_NOTES if notes is None else notes
    n = len(row_notes)
    if widen_first:
        added, k = 0, 0
        while first > 0 and (k < bars or added < notes):
            first -= 1
            k += 1
            added += row_notes[first]
    if widen_last:
        added, k = 0, 0
        while last < n - 1 and (k < bars or added < notes):
            last += 1
            k += 1
            added += row_notes[last]
    return first, last


def margin_needed(used: set[str], unmatched_without: set[str], min_notes: int | None = None,
                  share: float | None = None) -> bool:
    """BL-37: whether margin rows are needed. ``used`` are the performed notes the widened
    alignment matched in the margin rows; ``unmatched_without`` the performed notes the
    alignment of the DTW span leaves unmatched. The margin is needed when it explains notes
    nothing else explains: at least ``MARGIN_EXPLAINS_NOTES`` of ``used`` and at least
    ``MARGIN_EXPLAINS_SHARE`` of them are in ``unmatched_without``. Otherwise the margin only
    pulled notes away from the bars they belong to."""
    min_notes = MARGIN_EXPLAINS_NOTES if min_notes is None else min_notes
    share = MARGIN_EXPLAINS_SHARE if share is None else share
    if not used:
        return False
    k = len(used & unmatched_without)
    return k >= min_notes and k >= share * len(used)


def shrink_rows(n_notes: Sequence[int], n_missed: Sequence[int], first: int, last: int,
                shrink_first: bool, shrink_last: bool,
                share: float | None = None) -> tuple[int, int]:
    """Step 2's shrink on per-row counts (index = measure row): move ``first`` forward while the
    row has no score notes or at least ``share`` of them missed (``shrink_first`` only), and
    ``last`` backward likewise. Never crosses: at least one row is kept. ``share`` None =
    ``SHRINK_SHARE`` at call time."""
    share = SHRINK_SHARE if share is None else share

    def gone(r: int) -> bool:
        return n_notes[r] == 0 or n_missed[r] >= share * n_notes[r]

    if shrink_first:
        while first < last and gone(first):
            first += 1
    if shrink_last:
        while last > first and gone(last):
            last -= 1
    return first, last


def measure_labels(numbers: Sequence[int], names: Sequence[str]) -> list[str]:
    """Printed bar label per measure row, as ``report.build.bar_labels`` makes them: the name
    (or number), with a pass suffix on repeats (``"12 (2)"``)."""
    seen: dict[str, int] = {}
    out = []
    for num, name in zip(numbers, names, strict=True):
        lab = str(name).strip() or str(int(num))
        seen[lab] = seen.get(lab, 0) + 1
        out.append(lab if seen[lab] == 1 else f"{lab} ({seen[lab]})")
    return out
