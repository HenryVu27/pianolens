"""Audible A/B comparison (P-01): clips of each flagged passage of a practice report.

* :func:`select_windows`: which passages (tiered report issues, merged, capped).
* :func:`build_comparison`: clips (user audio, user re-rendered, typical and contrasting expert
  on the same piano) plus ``manifest.json``; :func:`inputs_from_report` rebuilds the inputs from
  a report JSON.
* :func:`write_player`: a self-contained A/B player page for a manifest.

Outputs are local only (personal recordings, non-commercial reference data).
"""

from pianolens.compare.engine import (
    CLIP_KINDS,
    SCHEMA,
    CompareConfig,
    CompareInputs,
    PianoCoReExperts,
    build_comparison,
    inputs_from_report,
)
from pianolens.compare.experts import ExpertChoice, rank_experts
from pianolens.compare.player import player_html, write_player
from pianolens.compare.timemap import TimeMap, time_map_from_aligned, time_map_from_notes
from pianolens.compare.windows import Window, select_windows

__all__ = [
    "CLIP_KINDS",
    "SCHEMA",
    "CompareConfig",
    "CompareInputs",
    "ExpertChoice",
    "PianoCoReExperts",
    "TimeMap",
    "Window",
    "build_comparison",
    "inputs_from_report",
    "player_html",
    "rank_experts",
    "select_windows",
    "time_map_from_aligned",
    "time_map_from_notes",
    "write_player",
]
