"""Score-to-performance note alignment.

Wraps parangonar's ``DualDTWNoteMatcher`` (Peter, Cancino-Chacon, Widmer et al., "Automatic
Note-Level Score-to-Performance Alignments in the ASAP Dataset", TISMIR 2023) and partitura's
repeat unfolding. The one thing added here is choosing which repeat structure ("score variant")
the performer played: every candidate unfolding is ranked by note count, the closest few are
aligned, and the variant with the highest match ratio wins.

Alignment format: a list of dicts in partitura's convention, one per note:

- ``{"label": "match", "score_id": str, "performance_id": str}``
- ``{"label": "deletion", "score_id": str}``   (score note not played)
- ``{"label": "insertion", "performance_id": str}``   (played note not in the score)

Score ids refer to the *unfolded* score, so they carry a repeat suffix: ``"n12-1"`` is the first
pass over note ``n12``, ``"n12-2"`` the second. This is the id scheme (n)ASAP uses.
"""

from __future__ import annotations

import copy
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import partitura as pt
from parangonar import DualDTWNoteMatcher

from pianolens.align._adapters import load_notes, to_part, to_performance_note_array

AlignmentList = list[dict[str, str]]

# partitura's unfolding recurses per segment; long sonatas exceed Python's default limit.
_MIN_RECURSION_LIMIT = 100_000

#: Repeat paths enumerated at most (DF-16). Every app-catalogue score but one has at most
#: 65,536 (Handel HWV 432/6), enumerated in about 1.4 s; Mozart K. 265 has far more and its
#: enumeration alone passed 3 GB (BL-40 audit). Above the cap a score gets two paths: the fully
#: repeated reading and the shortest one.
MAX_REPEAT_PATHS = 65_536

#: ``align(..., partial=True)`` builds every repeat path to search for the recorded span; above
#: this many paths it aligns as ``partial=False`` instead and says so in ``recorded_span``
#: (DF-17). BL-36 to BL-40 tested partial alignment on scores with at most 16 paths; a score
#: with 512 took 157 s and 2.5 GB for one 21-note excerpt (BL-40 audit).
PARTIAL_MAX_PATHS = 16


@dataclass
class AlignResult:
    """Output of :func:`align`.

    Attributes:
        alignment: partitura-style alignment list (see module docstring).
        score_note_array: note array of the unfolded score variant that was aligned
            (includes grace notes; field ``id`` matches ``score_id`` in ``alignment``).
        performance_note_array: note array of the performance (``id`` matches
            ``performance_id``).
        variant: the chosen repeat path as a string of segment letters, e.g. ``"AABB"``;
            ``""`` when the score has no repeat structure.
        n_variants: number of repeat paths the score allows.
        candidates: ``{variant: match_ratio}`` for every variant that was actually aligned.
        unfolded_part: the unfolded partitura ``Part`` (needed by features that read
            measures, time signatures or directions).
        load_notes: what building the score changed or found fragile (tremolos expanded, chord
            notes moved to the lower staff, a close staff choice; ``_adapters.load_notes``).
        recorded_span: with ``align(..., partial=True)`` the recorded span
            (:class:`pianolens.align.partial.RecordedSpan`); None otherwise. When it is not
            whole, ``unfolded_part`` and ``score_note_array`` hold only the recorded rows.
        variant_labels: with ``partial=True``, the printed bar label of every measure row of the
            unfolded variant (``partial.measure_labels``), so labels of the recorded rows and
            the rows left out keep their repeat pass (``"12 (2)"``).
    """

    alignment: AlignmentList
    score_note_array: np.ndarray
    performance_note_array: np.ndarray
    variant: str
    n_variants: int
    candidates: dict[str, float] = field(default_factory=dict)
    unfolded_part: Any = None
    load_notes: list[str] = field(default_factory=list)
    recorded_span: Any = None
    variant_labels: list[str] | None = None

    @property
    def n_match(self) -> int:
        return sum(1 for a in self.alignment if a["label"] == "match")

    @property
    def n_insertion(self) -> int:
        return sum(1 for a in self.alignment if a["label"] == "insertion")

    @property
    def n_deletion(self) -> int:
        return sum(1 for a in self.alignment if a["label"] == "deletion")

    def to_alignment(
        self, score_id: str = "", performance_id: str = "", source: str = "parangonar-dualdtw"
    ) -> Any:
        """This alignment as a ``pianolens.data.types.Alignment`` (ground_truth=False)."""
        from pianolens.data.types import Alignment

        return Alignment.from_partitura(
            self.alignment, score_id, performance_id, ground_truth=False, source=source
        )

    def to_score(self, like: Any) -> Any:
        """The unfolded score variant as a ``pianolens.data.types.Score``.

        ``like`` is the ``Score`` that was aligned; its ids and metadata are copied and
        ``meta["unfolded"]`` records the chosen variant. Use this score, not ``like``, with the
        alignment: its note ids are the ones ``score_id`` refers to. ``meta["load_notes"]`` lists
        :attr:`load_notes` when there are any.
        """
        from pianolens.data.types import score_from_partitura

        meta = {**like.meta, "unfolded": self.variant}
        if self.load_notes:
            meta["load_notes"] = list(self.load_notes)
        if self.recorded_span is not None:
            meta["recorded_span"] = self.recorded_span_record()
            if not self.recorded_span.whole and self.variant_labels is not None:
                sp = self.recorded_span
                meta["bar_labels"] = list(self.variant_labels[sp.first_row:sp.last_row + 1])
        return score_from_partitura(
            self.unfolded_part,
            score_id=like.score_id,
            piece_id=like.piece_id,
            source_path=like.source_path,
            meta=meta,
            keep_part=True,
        )

    def recorded_span_record(self) -> dict[str, Any]:
        """JSON-ready record of :attr:`recorded_span` (``Score.meta["recorded_span"]``): the
        span, and ``not_recorded``, one entry per side left out, with its bar labels, row range,
        number of bars and score notes."""
        sp = self.recorded_span
        rec: dict[str, Any] = {**sp.as_dict(), "method": "subsequence onset DTW (BL-36)",
                               "not_recorded": []}
        if sp.fallback:  # DF-17: too many repeat paths to search; aligned as a whole recording
            rec["method"] = (f"partial alignment not applied: {sp.fallback} (it searches "
                             f"at most {PARTIAL_MAX_PATHS}, DF-17); aligned as a whole recording")
            rec["fallback"] = sp.fallback
        labels = self.variant_labels or []
        if sp.whole or not labels:
            return rec
        counts = (sp.candidates.get(sp.variant) or {}).get("row_notes")
        for side, rows in (("start", range(0, sp.first_row)),
                           ("end", range(sp.last_row + 1, sp.n_rows))):
            if len(rows) == 0:
                continue
            a, b = labels[rows[0]], labels[rows[-1]]
            rec["not_recorded"].append({
                "position": side, "first_row": rows[0], "last_row": rows[-1],
                "n_bars": len(rows), "bars_label": f"bar {a}" if a == b else f"bars {a}-{b}",
                "n_score_notes": int(sum(counts[r] for r in rows)) if counts else None})
        return rec

    def match_pairs(self) -> list[tuple[str, str]]:
        """(score_id, performance_id) for every matched note."""
        return [
            (a["score_id"], a["performance_id"]) for a in self.alignment if a["label"] == "match"
        ]


def match_ratio(alignment: AlignmentList, n_score: int, n_perf: int) -> float:
    """Dice ratio 2 * matches / (score notes + performance notes), in [0, 1].

    1.0 means every score note and every performed note is matched. Used to rank repeat
    variants: an unfolding with too many repeats adds deletions, one with too few adds
    insertions, and both lower the ratio.
    """
    if n_score + n_perf == 0:
        return 1.0
    n_match = sum(1 for a in alignment if a["label"] == "match")
    return 2.0 * n_match / (n_score + n_perf)


def repeat_variants(part: Any) -> list[tuple[str, int]]:
    """All repeat paths of ``part`` with their note counts, without building the parts.

    Returns ``[(variant_string, n_notes), ...]`` in partitura's path order (the first is the
    fully repeated reading). ``n_notes`` counts tied-merged notes, grace notes included,
    whose onset falls in each traversed segment. Past :data:`MAX_REPEAT_PATHS` paths only the
    fully repeated and the shortest reading are listed (DF-16).
    """
    return [(v, n) for v, n, _ in _variants_with_paths(part)]


class _TooManyPaths(Exception):
    pass


class _CappedPaths(list):
    """The list partitura's ``unfold_paths`` appends finished paths to; stops past ``cap``."""

    def __init__(self, cap: int) -> None:
        super().__init__()
        self.cap = cap

    def append(self, item: Any) -> None:
        if len(self) >= self.cap:
            raise _TooManyPaths
        super().append(item)


def _variants_with_paths(part: Any) -> list[tuple[str, int, Any]]:
    return _variants_info(part)[0]


def _variants_info(part: Any, cap: int | None = None) -> tuple[list[tuple[str, int, Any]], bool]:
    """``[(variant, n_notes, path), ...]`` and whether that is every repeat path.

    Up to ``cap`` (default :data:`MAX_REPEAT_PATHS`) paths this is exactly
    ``partitura.score.get_paths(part)`` in its order. Past the cap the enumeration stops (it
    never lists every path) and the fully repeated and the shortest reading are returned
    (``complete`` False)."""
    _raise_recursion_limit()
    cap = MAX_REPEAT_PATHS if cap is None else cap
    # get_paths is stateful: it reuses segment objects left on the part by earlier calls, and a
    # second call can return a different (smaller) path set. Rebuild segments every time.
    pt.score.add_segments(part, force_new=True)
    segments = pt.score.get_segments(part)
    acc = _CappedPaths(cap)
    complete = True
    try:  # = get_paths(part, no_repeats=False, all_repeats=False, ignore_leap_info=True)
        pt.score.unfold_paths(pt.score.Path([chr(65)], segments), acc, ignore_leap_info=True)
        paths = list(acc)
    except _TooManyPaths:
        complete, ids = False, []
        for kw in ({"all_repeats": True}, {"no_repeats": True}):
            pt.score.add_segments(part, force_new=True)  # each call on fresh segments
            for p in pt.score.get_paths(part, ignore_leap_info=True, **kw):
                if list(p.path) not in ids:
                    ids.append(list(p.path))
        # rebuilding segments detaches the old ones: rebind every path to the current ones
        segments = pt.score.get_segments(part)
        paths = [pt.score.Path(i, segments) for i in ids]
    segments = pt.score.get_segments(part)
    onsets = np.array([n.start.t for n in part.notes_tied])
    seg_counts = {
        sid: int(np.sum((onsets >= s.start.t) & (onsets < s.end.t))) for sid, s in segments.items()
    }
    return [("".join(p.path), sum(seg_counts[s] for s in p.path), p) for p in paths], complete


_UNFOLDED_ID = re.compile(r".+-\d+$")


def is_unfolded(part: Any) -> bool:
    """True if every note id already carries a repeat suffix (``n12-1``), i.e. ``part`` is the
    output of a partitura unfolding. Unfolding such a part again crashes in partitura 1.9.0."""
    notes = part.notes_tied
    return bool(notes) and all(n.id and _UNFOLDED_ID.match(n.id) for n in notes)


def _build(part: Any, path: Any, n_variants: int) -> Any:
    if n_variants <= 1 and is_unfolded(part):
        return part
    return pt.score.new_part_from_path(path, part, update_ids=True)


def unfold_variant(part: Any, variant: str | None = None) -> Any:
    """Build the unfolded ``Part`` for a repeat path string.

    ``None`` or ``""`` is allowed only when the score has a single path (no repeats). Note ids
    get partitura's repeat suffix (``-1``, ``-2``) in every case, so ids are comparable with
    (n)ASAP ground truth.
    """
    variants = _variants_with_paths(part)
    if not variant:
        if len(variants) > 1:
            raise ValueError("score has repeats; pass a variant string")
        return _build(part, variants[0][2], len(variants))
    for v, _, p in variants:
        if v == variant:
            return _build(part, p, len(variants))
    raise ValueError(f"variant {variant!r} is not a valid repeat path of this score")


def score_note_array(part: Any) -> np.ndarray:
    """Note array with the fields DualDTWNoteMatcher needs (grace-note fields included)."""
    return part.note_array(include_grace_notes=True)


def align_note_arrays(
    score_na: np.ndarray,
    perf_na: np.ndarray,
    *,
    score_part: Any = None,
    process_ornaments: bool = True,
    matcher: DualDTWNoteMatcher | None = None,
) -> AlignmentList:
    """Run DualDTWNoteMatcher on an already unfolded score note array.

    ``score_part`` is only used to tag ornamented notes (trills, turns, mordents), which the
    matcher then allows to absorb extra performed notes. Ids are returned as plain ``str``.
    """
    if len(score_na) == 0:
        # BL-40: a partial alignment can trim a wrong score to a span with no notes; parangonar
        # then crashes (``join_by`` on an empty array). Every performed note is an insertion.
        return [{"label": "insertion", "performance_id": str(i)} for i in perf_na["id"]]
    matcher = matcher or DualDTWNoteMatcher()
    use_orn = process_ornaments and score_part is not None
    if not use_orn:
        raw = matcher(score_na, perf_na, process_ornaments=False, score_part=score_part)
        return [_clean(a) for a in raw]
    s_copy, p_copy = score_na.copy(), perf_na.copy()  # the ornament step edits arrays in place
    try:
        raw = matcher(score_na, perf_na, process_ornaments=True, score_part=score_part)
    except np.exceptions.DTypePromotionError:
        # parangonar 3.3.3: the ornament step crashes when no performed note is left unmatched
        # (``na_within`` returns a plain empty list that ``np.concatenate`` cannot join to the
        # structured arrays). There is nothing for it to re-match then, so align without it.
        raw = matcher(s_copy, p_copy, process_ornaments=False, score_part=score_part)
    return [_clean(a) for a in raw]


def align(
    score: Any,
    performance: Any,
    *,
    repeats: str = "auto",
    max_candidates: int = 6,
    process_ornaments: bool = True,
    partial: bool = False,
) -> AlignResult:
    """Align a score to a performance at the note level.

    Args:
        score: a partitura ``Score`` or ``Part``, a path to a score file (MusicXML, MEI, ...),
            or an object with a ``.part`` / ``.score`` attribute holding one of those.
        performance: a partitura ``Performance`` / ``PerformedPart``, a path to a MIDI file, a
            performance note array (fields ``onset_sec``, ``duration_sec``, ``pitch``,
            ``velocity``, ``id``), or an object with ``.note_array``.
        repeats: how to unfold repeats.
            ``"auto"``: rank all repeat paths by |score notes - performed notes|, align the
            ``max_candidates`` closest, keep the best match ratio.
            ``"maximal"`` / ``"minimal"``: take every repeat / no repeat.
            Any other string is taken as an explicit path, e.g. ``"AABBC"``.
        max_candidates: how many variants ``"auto"`` aligns (each costs one DTW run).
        process_ornaments: let ornamented score notes absorb extra performed notes.
        partial: BL-36, the performance may cover only part of the score
            (:mod:`pianolens.align.partial`). The recorded span and repeat path are found by
            subsequence onset DTW over the repeat paths (all of them for ``"auto"``); a whole
            recording gives exactly the result of ``partial=False`` (plus ``recorded_span``),
            a partial one an alignment to the score trimmed to the recorded rows.

    Returns:
        :class:`AlignResult`.
    """
    part = to_part(score)
    perf_na = to_performance_note_array(performance)
    variants, complete = _variants_info(part)
    by_name = {v: p for v, _, p in variants}
    n_variants = len(variants)
    fallback = None
    if partial and (not complete or n_variants > PARTIAL_MAX_PATHS):
        # DF-17: searching every path for the span is unbounded on such scores; align whole
        fallback = (f"{'more than ' if not complete else ''}"
                    f"{MAX_REPEAT_PATHS if not complete else n_variants:,} repeat paths")
        partial = False

    if n_variants <= 1:
        chosen = [v for v, _, _ in variants]
    elif repeats == "auto":
        n_perf = len(perf_na)
        ranked = sorted(variants, key=lambda v: (abs(v[1] - n_perf), -v[1]))
        chosen = [v for v, _, _ in ranked[: max(1, max_candidates)]]
    elif repeats == "maximal":
        chosen = [max(variants, key=lambda v: v[1])[0]]
    elif repeats == "minimal":
        chosen = [min(variants, key=lambda v: v[1])[0]]
    elif repeats in by_name:
        chosen = [repeats]
    else:
        raise ValueError(f"variant {repeats!r} is not a valid repeat path of this score")

    span = labels = None
    if partial:
        from pianolens.align import partial as pa

        # every repeat path for "auto" (a partial recording's note count says nothing about
        # the path), in the order "auto" would try them so ties keep its preference
        order = (sorted(variants, key=lambda v: (abs(v[1] - len(perf_na)), -v[1]))
                 if repeats == "auto" and n_variants > 1 else
                 [v for v in variants if v[0] in chosen])
        built = {v: _build(part, p, n_variants) for v, _, p in order}
        span = pa.detect_span([(v, built[v]) for v, _, _ in order], perf_na)
        upart = built[span.variant]
        labels = _variant_labels(upart)
        for v, d in span.candidates.items():
            if v == span.variant:
                d["row_notes"] = _row_note_counts(upart)
        if not span.whole:
            path = by_name[span.variant]

            def fresh(first: bool = False) -> Any:
                # a new unfolding to trim in place (deep copies of long parts overflow the
                # recursion limit); the detection's own part is used once when it is not the
                # caller's part object
                p = upart if first else _build(part, path, n_variants)
                return copy.deepcopy(p) if p is part else p

            res = _align_partial(fresh, span, perf_na, n_variants, process_ornaments)
            res.variant_labels = labels
            res.load_notes = load_notes(part)
            return res

    matcher = DualDTWNoteMatcher()
    best: AlignResult | None = None
    candidates: dict[str, float] = {}
    for variant in chosen:
        upart = _build(part, by_name[variant], n_variants)
        sna = score_note_array(upart)
        al = align_note_arrays(
            sna, perf_na, score_part=upart, process_ornaments=process_ornaments, matcher=matcher
        )
        ratio = match_ratio(al, len(sna), len(perf_na))
        candidates[variant] = ratio
        if best is None or ratio > candidates[best.variant]:
            best = AlignResult(al, sna, perf_na, variant, n_variants, unfolded_part=upart)
    if best is None:
        raise ValueError("score has no notes to align")
    best.candidates = candidates
    best.load_notes = load_notes(part)
    if fallback is not None:
        from pianolens.align import partial as pa

        best.variant_labels = _variant_labels(best.unfolded_part)
        n = len(best.variant_labels)
        best.recorded_span = pa.RecordedSpan(best.variant, 0, n - 1, n, True, float("nan"),
                                             fallback=fallback)
    if span is not None:
        if best.variant != span.variant:  # "auto" picked another path for a whole recording
            labels = _variant_labels(best.unfolded_part)
            span.candidates.setdefault(best.variant, {})["row_notes"] = \
                _row_note_counts(best.unfolded_part)
            n = len(labels)
            span.variant, span.first_row, span.last_row, span.n_rows = best.variant, 0, n - 1, n
        best.recorded_span = span
        best.variant_labels = labels
    return best


def _variant_labels(upart: Any) -> list[str]:
    from pianolens.align.partial import measure_labels
    from pianolens.data.types import measures_from_partitura

    ms = measures_from_partitura(upart)
    return measure_labels(ms["number"], ms["name"])


def _row_note_counts(upart: Any) -> list[int]:
    """Score notes (grace notes excluded) starting in each measure row of an unfolded part."""
    from pianolens.align.partial import _measure_starts, _rows_of_divs

    sna = score_note_array(upart)
    ng = sna[~sna["is_grace"].astype(bool)]
    starts = _measure_starts(upart)
    return np.bincount(_rows_of_divs(starts, ng["onset_div"]), minlength=len(starts)).tolist()


def _align_partial(fresh: Any, span: Any, perf_na: np.ndarray, n_variants: int,
                   process_ornaments: bool) -> AlignResult:
    """BL-36 step 2, revised in BL-37 (:mod:`pianolens.align.partial`).

    1. Align the DTW span itself (``D``) and the span widened by the margin (``W``); shrink the
       trimmed sides of both.
    2. On each trimmed side, the margin rows ``W`` keeps beyond the DTW span are used only when
       they explain performed notes ``D`` leaves unmatched (``partial.margin_needed``). An
       anchored note alignment otherwise pulls the first (last) performed notes into unplayed
       margin bars, and the real edge bar is reported missed (BL-37 dev).
    3. Align the final rows (or reuse ``D`` / ``W`` when they match); a note tied in from
       before the span is optional.
    ``fresh(first)`` returns an unfolded part of the chosen path that may be trimmed in place.
    """
    from pianolens.align import partial as pa

    n_rows = span.n_rows
    lo_trim, hi_trim = span.first_row > 0, span.last_row < n_rows - 1
    upart = fresh(True)
    starts = pa._measure_starts(upart)
    row_notes = _row_note_counts(upart)

    def run(r0: int, r1: int, part: Any = None) -> dict:
        tp = pa.trim_part(part if part is not None else fresh(), r0, r1, inplace=True)
        sna = score_note_array(tp)
        al = align_note_arrays(sna, perf_na, score_part=tp, process_ornaments=process_ornaments)
        row_of = dict(zip(sna["id"].astype(str), pa._rows_of_divs(starts, sna["onset_div"]),
                          strict=True))
        grace = dict(zip(sna["id"].astype(str), sna["is_grace"].astype(bool), strict=True))
        n_notes = np.zeros(n_rows, int)
        n_missed = np.zeros(n_rows, int)
        for x in al:
            sid = x.get("score_id")
            if sid is None or grace.get(sid, False):
                continue
            n_notes[row_of[sid]] += 1
            n_missed[row_of[sid]] += x["label"] == "deletion"
        f, last = pa.shrink_rows(n_notes, n_missed, r0, r1, lo_trim, hi_trim)
        return {"rows": (r0, r1), "part": tp, "sna": sna, "al": al, "row_of": row_of,
                "shrunk": (f, last)}

    d0, d1 = span.first_row, span.last_row
    e0, e1 = pa.widen_rows(row_notes, d0, d1, lo_trim, hi_trim)
    w = run(e0, e1, upart)
    d = run(d0, d1) if (e0, e1) != (d0, d1) else w
    unmatched_d = {x["performance_id"] for x in d["al"] if x["label"] == "insertion"}

    def side(lo: bool) -> int:
        wf = w["shrunk"][0] if lo else w["shrunk"][1]
        df = d["shrunk"][0] if lo else d["shrunk"][1]
        margin = range(wf, d0) if lo else range(d1 + 1, wf + 1)
        if len(margin) == 0:  # W kept no margin row on this side
            return df if (wf >= d0 if lo else wf <= d1) else wf
        used = {x["performance_id"] for x in w["al"] if x["label"] == "match"
                and w["row_of"].get(x["score_id"], -1) in margin}
        return wf if pa.margin_needed(used, unmatched_d) else df

    f = side(True) if lo_trim else 0
    last = side(False) if hi_trim else n_rows - 1
    best = next((x for x in (d, w) if x["rows"] == (f, last)), None)
    if best is None:
        best = run(f, last)
    tpart, sna, al = best["part"], best["sna"], best["al"]
    tails = set(pa.edge_tails(tpart)) if f > 0 else set()
    unplayed = {x["score_id"] for x in al if x["label"] == "deletion" and x["score_id"] in tails}
    if unplayed:  # BL-37: a note tied in from before the span is optional
        al = [x for x in al if x.get("score_id") not in unplayed]
        tpart = pa.drop_notes(tpart, unplayed)
        sna = score_note_array(tpart)
    span.first_row, span.last_row = int(f), int(last)
    span.whole = f == 0 and last == n_rows - 1  # nothing left out after all
    span.refined = True
    ratio = match_ratio(al, len(sna), len(perf_na))
    return AlignResult(al, sna, perf_na, span.variant, n_variants, {span.variant: ratio},
                       unfolded_part=tpart, recorded_span=span)


def _clean(entry: dict[str, Any]) -> dict[str, str]:
    """Copy an alignment entry, casting numpy string ids to ``str`` and dropping extras."""
    out = {"label": str(entry["label"])}
    for key in ("score_id", "performance_id"):
        if key in entry:
            out[key] = str(entry[key])
    return out


def _raise_recursion_limit() -> None:
    if sys.getrecursionlimit() < _MIN_RECURSION_LIMIT:
        sys.setrecursionlimit(_MIN_RECURSION_LIMIT)


def load_score_part(path: str | Path) -> Any:
    """Load a score file and merge its parts into one ``Part`` (piano staves are often split),
    with MusicXML tremolos expanded (:func:`pianolens.align._adapters.to_part`)."""
    return to_part(Path(path))


def align_performance(score: Any, performance: Any, **kwargs: Any) -> Any:
    """Align project types and return a ``pianolens.data.types.AlignedPerformance``.

    ``score`` is a ``pianolens.data.types.Score``. When it has a ``source_path`` the original
    (folded) score is re-read so the repeat variant is chosen from this performance, not taken
    from however the loader unfolded it (the ASAP loader unfolds maximally). The returned
    ``AlignedPerformance.score`` is the unfolded variant that the alignment ids refer to.
    ``kwargs`` go to :func:`align` (``partial=True``: BL-36, the score is trimmed to the
    recorded span; ``score.meta["recorded_span"]`` lists the bars left out and
    ``score.meta["bar_labels"]`` keeps their printed labels with repeat passes).
    """
    from pianolens.data.types import AlignedPerformance

    res = align(score, performance, **kwargs)
    return AlignedPerformance(
        performance=performance,
        score=res.to_score(score),
        alignment=res.to_alignment(score.score_id, performance.performance_id),
    )
