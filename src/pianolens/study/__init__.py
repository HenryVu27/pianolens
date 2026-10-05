"""pianolens.study: listening-study tooling (Phases 3-4).

* :mod:`pianolens.study.degrade`: graded single-dimension degradations of aligned expert MIDI
  (S-01), each level reported in physical units and against literature thresholds.
* :mod:`pianolens.study.excerpt`: cut an aligned performance to a bar range for a stimulus.
* :mod:`pianolens.study.psychometric`: psychometric and preference-cost fits with
  listener-clustered standard errors (S-03 analysis plan).
* :mod:`pianolens.study.power`: simulation-based power analysis for the S-03 design.
* :mod:`pianolens.study.power_s04`: simulation-based design check for the S-04 pairwise
  preference study (H7; draft).
"""

from pianolens.study.degrade import (
    DIMENSIONS,
    DegradeResult,
    articulation_scale,
    degrade,
    dynamics_flatten,
    pedal_blur,
    tempo_flatten,
    timing_jitter,
    velocity_components,
    voicing_scale,
    wrong_notes,
)
from pianolens.study.excerpt import excerpt

__all__ = [
    "DIMENSIONS",
    "DegradeResult",
    "articulation_scale",
    "degrade",
    "dynamics_flatten",
    "excerpt",
    "pedal_blur",
    "tempo_flatten",
    "timing_jitter",
    "velocity_components",
    "voicing_scale",
    "wrong_notes",
]
