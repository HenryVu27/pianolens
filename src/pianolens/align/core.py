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
    """

    alignment: AlignmentList
    score_note_array: np.ndarray
    performance_note_array: np.ndarray
    variant: str
    n_variants: int
    candidates: dict[str, float] = field(default_factory=dict)
    unfolded_part: Any = None
    load_notes: list[str] = field(default_factory=list)

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
        return score_from_partitura(
            self.unfolded_part,
            score_id=like.score_id,
            piece_id=like.piece_id,
            source_path=like.source_path,
            meta=meta,
            keep_part=True,
        )

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
    whose onset falls in each traversed segment.
    """
    return [(v, n) for v, n, _ in _variants_with_paths(part)]


def _variants_with_paths(part: Any) -> list[tuple[str, int, Any]]:
    _raise_recursion_limit()
    # get_paths is stateful: it reuses segment objects left on the part by earlier calls, and a
    # second call can return a different (smaller) path set. Rebuild segments every time.
    pt.score.add_segments(part, force_new=True)
    paths = pt.score.get_paths(part, no_repeats=False, all_repeats=False, ignore_leap_info=True)
    segments = pt.score.get_segments(part)
    onsets = np.array([n.start.t for n in part.notes_tied])
    seg_counts = {
        sid: int(np.sum((onsets >= s.start.t) & (onsets < s.end.t))) for sid, s in segments.items()
    }
    return [("".join(p.path), sum(seg_counts[s] for s in p.path), p) for p in paths]


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
    matcher = matcher or DualDTWNoteMatcher()
    use_orn = process_ornaments and score_part is not None
    raw = matcher(score_na, perf_na, process_ornaments=use_orn, score_part=score_part)
    return [_clean(a) for a in raw]


def align(
    score: Any,
    performance: Any,
    *,
    repeats: str = "auto",
    max_candidates: int = 6,
    process_ornaments: bool = True,
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

    Returns:
        :class:`AlignResult`.
    """
    part = to_part(score)
    perf_na = to_performance_note_array(performance)
    variants = _variants_with_paths(part)
    by_name = {v: p for v, _, p in variants}
    n_variants = len(variants)

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
    return best


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
    ``kwargs`` go to :func:`align`.
    """
    from pianolens.data.types import AlignedPerformance

    res = align(score, performance, **kwargs)
    return AlignedPerformance(
        performance=performance,
        score=res.to_score(score),
        alignment=res.to_alignment(score.score_id, performance.performance_id),
    )
