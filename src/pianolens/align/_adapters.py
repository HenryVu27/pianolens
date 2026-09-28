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


def to_part(score: Any) -> Any:
    """Return a single merged partitura ``Part`` from a score-like input."""
    if isinstance(score, str | Path):
        score = pt.load_score(str(score))
    if isinstance(score, pt.score.Part):
        return score
    if isinstance(score, pt.score.Score | pt.score.PartGroup | list):
        parts = score.parts if hasattr(score, "parts") else score
        if len(parts) == 1 and isinstance(parts[0], pt.score.Part):
            return parts[0]
        return pt.score.merge_parts(parts)
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
