"""Thin input adapters so :mod:`pianolens.align` accepts partitura objects, file paths, note
arrays, or the project's common types (``pianolens.data.types``) without importing them.

The common types are duck-typed on purpose: this module must not depend on the loader code
that another agent owns. Anything with a ``.part`` / ``.score`` attribute is unwrapped as a
score; anything with a ``.note_array`` (array or method) is read as a performance.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import partitura as pt

_PERF_FIELDS = ("onset_sec", "duration_sec", "pitch", "id")


_STAFFED = (pt.score.GenericNote, pt.score.Clef, pt.score.Words, pt.score.Direction)


def _set_staves(part: Any, mapping: dict[int, int]) -> None:
    # collect first: an object can match several classes, and a mapping must apply only once
    objs = {id(e): e for e in part.iter_all(_STAFFED, include_subclasses=True)}
    for e in objs.values():
        st = getattr(e, "staff", None)
        if st is not None and int(st) in mapping:
            e.staff = mapping[int(st)]


def _number_parts_consecutively(parts: list[Any]) -> None:
    """Give each part's staves global numbers in part order (part 1: 1..n1, part 2: n1+1..).
    ``merge_parts`` (reassign="voice") keeps staff numbers, so one-staff-per-part scores would
    otherwise merge onto staff 1."""
    offset = 0
    for p in parts:
        staves = sorted({int(n.staff) if n.staff is not None else 1 for n in p.notes_tied})
        if not staves:
            continue
        _set_staves(p, {s: offset + k + 1 for k, s in enumerate(staves)})
        for n in p.iter_all(pt.score.GenericNote, include_subclasses=True):
            if n.staff is None:
                n.staff = offset + 1
        offset += len(staves)


def normalise_piano_staves(part: Any) -> dict[int, int]:
    """Renumber a merged piano part's staves to 1 (upper) and 2 (lower), in place (DF-09).

    Hand synchrony and the even-run streams read staff 1 as the upper and staff 2 as the lower
    staff; some scores number them 3/4, 2/3 or 1/3, or add small extra staves. Rule:

    - One staff: unchanged (1).
    - Two staves: the lower number (the upper staff on the page) -> 1, the other -> 2.
    - Three or more: the two staves with the most notes are the main pair (ties: lower number
      first); the one printed higher -> 1, the other -> 2. Any other staff printed above the
      pair -> 1, below it -> 2, between them -> the main staff whose mean pitch is nearer.

    Notes, clefs, words and directions are renumbered. Returns the mapping (old -> new).
    """
    notes = list(part.notes_tied)
    count: dict[int, int] = {}
    psum: dict[int, float] = {}
    for n in notes:
        st = int(n.staff) if n.staff is not None else 1
        count[st] = count.get(st, 0) + 1
        psum[st] = psum.get(st, 0.0) + float(n.midi_pitch)
    staves = sorted(count)
    if len(staves) <= 1:
        mapping = {s: 1 for s in staves}
    elif len(staves) == 2:
        mapping = {staves[0]: 1, staves[1]: 2}
    else:
        main = sorted(sorted(staves, key=lambda s: (-count[s], s))[:2])
        up, lo = main
        mean = {s: psum[s] / count[s] for s in staves}
        mapping = {}
        for s in staves:
            if s == up or s < up:
                mapping[s] = 1
            elif s == lo or s > lo:
                mapping[s] = 2
            else:
                mapping[s] = 1 if abs(mean[s] - mean[up]) <= abs(mean[s] - mean[lo]) else 2
    if any(k != v for k, v in mapping.items()):
        _set_staves(part, mapping)
    return mapping


def to_part(score: Any) -> Any:
    """Return a single merged partitura ``Part`` from a score-like input.

    Staves are numbered upper = 1, lower = 2 (:func:`normalise_piano_staves`; multi-part scores
    first get consecutive staff numbers in part order). This is the one place every aligned
    score is built (``align_performance`` re-reads the score file through it), so tier B's hand
    synchrony and even runs see the same numbering for every score. A partitura ``Part`` or
    ``Score`` passed in is renumbered in place.
    """
    if isinstance(score, str | Path):
        score = pt.load_score(str(score))
    if isinstance(score, pt.score.Part):
        normalise_piano_staves(score)
        return score
    if isinstance(score, pt.score.Score | pt.score.PartGroup | list):
        parts = score.parts if hasattr(score, "parts") else score
        if len(parts) == 1 and isinstance(parts[0], pt.score.Part):
            normalise_piano_staves(parts[0])
            return parts[0]
        _number_parts_consecutively(list(parts))
        merged = pt.score.merge_parts(parts)
        normalise_piano_staves(merged)
        return merged
    # pianolens.data.types.Score: prefer the source file (folded, so repeats can be chosen)
    src = getattr(score, "source_path", None)
    if src is not None and Path(src).is_file():
        return to_part(Path(src))
    for attr in ("part", "score", "partitura_score"):
        inner = getattr(score, attr, None)
        if inner is not None and inner is not score:
            return to_part(inner)
    raise TypeError(
        f"cannot read a score from {type(score).__name__}; a pianolens Score needs a "
        "source_path or a kept partitura part (keep_part=True)"
    )


def to_performance_note_array(performance: Any) -> np.ndarray:
    """Return a performance note array with at least ``onset_sec, duration_sec, pitch, id``."""
    if isinstance(performance, str | Path):
        performance = pt.load_performance_midi(str(performance))
    if isinstance(performance, np.ndarray):
        na = performance
    elif isinstance(getattr(performance, "notes", None), np.ndarray):
        na = performance.notes  # pianolens.data.types.Performance
    else:
        attr = getattr(performance, "note_array", None)
        if attr is None:
            for name in ("performance", "performed_part", "partitura_performance"):
                inner = getattr(performance, name, None)
                if inner is not None and inner is not performance:
                    return to_performance_note_array(inner)
            raise TypeError(f"cannot read a performance from {type(performance).__name__}")
        na = attr() if callable(attr) else attr
    missing = [f for f in _PERF_FIELDS if f not in (na.dtype.names or ())]
    if missing:
        raise ValueError(f"performance note array lacks fields {missing}")
    return na
