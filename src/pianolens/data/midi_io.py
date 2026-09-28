"""Load plain MIDI files into the common types (for corpora without match files)."""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import Any

import partitura as pt

from pianolens.data.types import (
    Performance,
    PerformerId,
    PieceId,
    Provenance,
    Score,
    performance_from_partitura,
    score_from_partitura,
)


def performance_from_midi(
    path: Path,
    *,
    dataset: str,
    performance_id: str,
    piece_id: PieceId,
    performer_id: PerformerId,
    provenance: Provenance,
    meta: dict[str, Any] | None = None,
) -> Performance:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        perf = pt.load_performance_midi(str(path))
    return performance_from_partitura(
        perf,
        performance_id=performance_id,
        piece_id=piece_id,
        performer_id=performer_id,
        provenance=provenance,
        dataset=dataset,
        source_path=path,
        meta=meta,
    )


def score_from_midi(
    path: Path, *, score_id: str, piece_id: PieceId, meta: dict[str, Any] | None = None
) -> Score:
    """A score MIDI as a ``Score``; the measure map comes from MIDI time signatures."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        score = pt.load_score_midi(str(path))
    parts = list(score.parts)
    part = parts[0] if len(parts) == 1 else pt.score.merge_parts(parts)
    return score_from_partitura(part, score_id=score_id, piece_id=piece_id, source_path=path,
                                meta={"format": "midi", **(meta or {})})  # fmt: skip
