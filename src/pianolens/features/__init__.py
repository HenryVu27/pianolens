"""pianolens.features"""

from pianolens.features.control import ControlConfig, ControlResult, control_features
from pianolens.features.score_basis import BasisConfig, ScoreBasis, score_basis
from pianolens.features.shaping import (
    ShapingConfig,
    dynamic_compliance,
    pooled_structural_coherence,
    repeated_material,
    shaping,
    structural_coherence,
    voicing,
)
from pianolens.features.tempo import (
    TempoConfig,
    TempoCurve,
    phrase_arcs,
    score_tempo_breaks,
    tempo_from_onsets,
    tempo_model,
)

__all__ = [
    "ControlConfig",
    "ControlResult",
    "control_features",
    "BasisConfig",
    "ScoreBasis",
    "ShapingConfig",
    "dynamic_compliance",
    "pooled_structural_coherence",
    "repeated_material",
    "score_basis",
    "shaping",
    "structural_coherence",
    "voicing",
    "TempoConfig",
    "TempoCurve",
    "phrase_arcs",
    "score_tempo_breaks",
    "tempo_from_onsets",
    "tempo_model",
]
