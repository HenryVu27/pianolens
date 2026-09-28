"""Score-to-performance note alignment (parangonar DualDTW + partitura repeat unfolding)."""

from pianolens.align.core import (
    AlignmentList,
    AlignResult,
    align,
    align_note_arrays,
    align_performance,
    is_unfolded,
    load_score_part,
    match_ratio,
    repeat_variants,
    score_note_array,
    unfold_variant,
)
from pianolens.align.evaluate import PRF, AlignmentScores, evaluate_alignment

__all__ = [
    "PRF",
    "AlignResult",
    "AlignmentList",
    "AlignmentScores",
    "align",
    "align_note_arrays",
    "align_performance",
    "is_unfolded",
    "evaluate_alignment",
    "load_score_part",
    "match_ratio",
    "repeat_variants",
    "score_note_array",
    "unfold_variant",
]
