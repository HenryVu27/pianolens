"""Shared reader for corpora distributed as partitura match files (Vienna 4x22, Batik).

A match file holds the performance, the score notes and the note alignment in one file.
``partitura.load_match(create_score=True)`` rebuilds the score from the match file, so the
alignment's score ids refer to that score's note ids exactly (repeats as performed).
"""

from __future__ import annotations

import logging
import warnings
from pathlib import Path
from typing import Any

import partitura as pt

from pianolens.data.types import (
    AlignedPerformance,
    Alignment,
    PerformerId,
    PieceId,
    Provenance,
    performance_from_partitura,
    score_from_partitura,
)

log = logging.getLogger(__name__)


def load_match_file(
    path: Path,
    *,
    dataset: str,
    performance_id: str,
    score_id: str,
    piece_id: PieceId,
    performer_id: PerformerId,
    provenance: Provenance,
    meta: dict[str, Any] | None = None,
) -> AlignedPerformance:
    """Load one match file into an ``AlignedPerformance`` with a ground-truth alignment."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        perf, alignment, score = pt.load_match(str(path), create_score=True)
    parts = list(score.parts)
    part = parts[0] if len(parts) == 1 else pt.score.merge_parts(parts)
    s = score_from_partitura(part, score_id=score_id, piece_id=piece_id, source_path=path,
                             meta={"format": "match"})  # fmt: skip
    p = performance_from_partitura(
        perf,
        performance_id=performance_id,
        piece_id=piece_id,
        performer_id=performer_id,
        provenance=provenance,
        dataset=dataset,
        source_path=path,
        meta=meta,
    )
    al = Alignment.from_partitura(alignment, score_id, performance_id, ground_truth=True,
                                  source=f"{dataset}-match")  # fmt: skip
    return AlignedPerformance(p, s, al)
