"""Batch feature extraction: one flat feature row per aligned performance (R-04).

Collects the F-02..F-05 summaries plus simple global descriptors into one ``dict`` per
performance, and optionally **reference-based** features computed against other performances of
the same score (other performers' MIDI only, never their labels). Written for short segments
(PercePiano: 4-16 bars) but works on whole pieces.

Column prefixes (the family is the part before the first ``__``):

* ``corr__``: F-02 correctness (:func:`pianolens.features.correctness.correctness`). Rates are
  per graded score note.
* ``tempo__``: F-03 tempo model (:func:`pianolens.features.tempo.tempo_model`). Log tempo in
  score beats per minute (natural log); spreads of the smooth log tempo ratio; residual jitter in
  beats (fraction of the local beat period).
* ``ctrl__``: F-04 control (:func:`pianolens.features.control.control_features`, run without
  references, so timing noise falls back to ``jitter_nometric``): evenness (broad and strict),
  hand synchrony, tempo stability, pedal blur.
* ``shape__``: F-05 shaping: structural coherence R² (velocity, timing, articulation; with and
  without markings), repeated-material consistency, voicing, dynamic-marking compliance.
* ``glob__``: global descriptors defined here (see :func:`global_descriptors`).
* ``ref__``: reference-based features (:func:`reference_features`); only when references exist.

Short-segment settings (``ExtractConfig``): structural coherence uses 1-bar CV blocks, no buffer
and at most 5 folds, and is NaN below ``coherence_min_bars`` written bars; R² is clipped to
``[-coherence_clip, 1]``. The smooth-tempo coherence channel is not reported: on a segment of a
few bars the 1.5-bar smooth curve has only a handful of degrees of freedom.

Citations: see the F-02..F-05 module docstrings and ``docs/research/2026-09-27-landscape.md``
(Goebl 2001 for melody lead with velocity; Bresin and Battel 2000 for articulation ratios; Liang,
Fazekas, Sandler 2018 for pedalling; Hu et al., TISMIR 2026 for tempo-normalized timing and chord
asynchrony).
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Any

import numpy as np
import pandas as pd

from pianolens.features.control import (
    ControlConfig,
    control_features,
    reference_residuals,
    timing_noise,
)
from pianolens.features.correctness import correctness
from pianolens.features.interpretation import curve_agreement
from pianolens.features.score_basis import ScoreBasis, score_basis
from pianolens.features.shaping import (
    ShapingConfig,
    channel_data,
    dynamic_compliance,
    repeated_material,
    structural_coherence,
    voicing,
)
from pianolens.features.tempo import TempoConfig, TempoCurve, tempo_model

__all__ = [
    "CURVES",
    "RELATIVE_KEYS",
    "SHORT_SEGMENT_SHAPING",
    "ExtractConfig",
    "SegmentFeatures",
    "global_descriptors",
    "group_features",
    "reference_features",
    "segment_features",
]

log = logging.getLogger(__name__)

SHORT_SEGMENT_SHAPING = ShapingConfig(
    block_bars=1, n_folds=5, inner_folds=3, buffer_bars=0,
    alphas=tuple(float(a) for a in np.logspace(-2, 4, 13)),
)  # fmt: skip

#: Curves kept per performance for reference features: name -> (index kind, unit).
CURVES = {
    "velocity": ("score_id", "vel_midi"),
    "timing": ("beat", "dev_beats"),
    "tempo": ("beat", "tempo_log_ratio"),
    "articulation": ("score_id", "art_log_ratio"),
}

#: Own-performance columns that also get a "relative to the references" version.
RELATIVE_KEYS = (
    "glob__vel_mean_midi", "glob__vel_sd_midi", "tempo__log_bpm", "glob__art_median_log",
    "ctrl__pedal_down_fraction", "glob__pedal_presses_per_sec", "tempo__jitter_rms_beats",
    "tempo__smooth_log_sd",
)  # fmt: skip


@dataclass(frozen=True)
class ExtractConfig:
    """Settings for :func:`segment_features` and :func:`reference_features`.

    Attributes:
        tempo: F-03 config (None = defaults: 1.5-bar cutoff).
        control: F-04 config.
        shaping: F-05 config for coherence and the other shaping parts.
        coherence_min_bars: fewer written bars -> coherence is NaN (undefined).
        coherence_clip: coherence R² is clipped below at ``-coherence_clip``.
        coherence_channels: channels reported (smooth tempo is left out on purpose).
        min_references: minimum references for the F-04 timing-noise consensus.
        curve_min_references: minimum references at a point for the curve-agreement features.
        curve_min_points: minimum common points for a curve correlation.
    """

    tempo: TempoConfig | None = None
    control: ControlConfig = field(default_factory=ControlConfig)
    shaping: ShapingConfig = SHORT_SEGMENT_SHAPING
    coherence_min_bars: int = 8
    coherence_clip: float = 1.0
    coherence_channels: tuple[str, ...] = ("velocity", "timing", "articulation")
    min_references: int = 3
    curve_min_references: int = 2
    curve_min_points: int = 5


@dataclass(eq=False)
class SegmentFeatures:
    """Output of :func:`segment_features`.

    Attributes:
        performance_id: id of the performance.
        features: flat feature dict (prefixes in the module docstring).
        curves: ``CURVES`` name -> Series (index: score note id or score beat rounded to 1e-6).
        tempo: the F-03 tempo curve (needed for the timing-noise consensus).
        errors: component name -> error message, for components that failed (their columns
            are NaN).
    """

    performance_id: str
    features: dict[str, float]
    curves: dict[str, pd.Series]
    tempo: TempoCurve | None
    errors: dict[str, str] = field(default_factory=dict)


# --------------------------------------------------------------------------- helpers


def _f(x: Any) -> float:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return float("nan")
    return v if np.isfinite(v) else float("nan")


def _time_weighted(times: np.ndarray, values: np.ndarray, t0: float, t1: float) -> float:
    """Time-weighted mean of a step function (value holds from each event time) on [t0, t1];
    0 before the first event."""
    if t1 <= t0:
        return float("nan")
    grid = np.linspace(t0, t1, 2001)
    k = np.searchsorted(times, grid, side="right") - 1
    v = np.where(k >= 0, values[np.maximum(k, 0)], 0.0)
    return float(np.mean(v))


def _pedal_features(pedal: np.ndarray | None, t0: float, t1: float, threshold: int
                    ) -> dict[str, float]:
    out = {"glob__pedal_presses_per_sec": 0.0, "glob__pedal_depth_mean": 0.0,
           "glob__soft_pedal_fraction": 0.0}  # fmt: skip
    if pedal is None or len(pedal) == 0 or t1 <= t0:
        return out
    for number, key in ((64, "sustain"), (67, "soft")):
        p = pedal[pedal["number"] == number]
        if len(p) == 0:
            continue
        p = p[np.argsort(p["time_sec"], kind="stable")]
        t = p["time_sec"].astype(float)
        v = p["value"].astype(float)
        if key == "sustain":
            down = v >= threshold
            presses = int(np.sum(down[1:] & ~down[:-1]) + int(down[0]))
            out["glob__pedal_presses_per_sec"] = presses / (t1 - t0)
            out["glob__pedal_depth_mean"] = _time_weighted(t, v / 127.0, t0, t1)
        else:
            out["glob__soft_pedal_fraction"] = _time_weighted(t, (v >= threshold).astype(float),
                                                              t0, t1)
    return out


def _curve_series(values: pd.Series | np.ndarray, index: Any) -> pd.Series:
    s = pd.Series(np.asarray(values, dtype=float), index=index)
    s = s[~s.index.duplicated(keep="first")]
    return s


# --------------------------------------------------------------------------- global descriptors


def global_descriptors(ap: Any, tc: TempoCurve, basis: ScoreBasis,
                       articulation: pd.DataFrame | None = None,
                       pedal_threshold: int = 64) -> dict[str, float]:
    """Simple whole-performance descriptors (``glob__*``).

    * ``vel_mean_midi``, ``vel_sd_midi``, ``vel_range_p95_p5_midi``: over all performed notes
      (MIDI velocity).
    * ``vel_bar_sd_midi``: SD of the bar means of matched-note velocity (large-scale dynamics).
    * ``art_median_log``, ``art_iqr_log``: median / IQR of the key-down articulation log ratio
      (F-05 ``art_log_ratio``; 0 = notated length at the local tempo).
    * ``legato_overlap_frac``: share of consecutive melody (skyline) notes, adjacent in the
      score, whose performed key-down offset is later than the next note's onset.
    * ``pedal_presses_per_sec`` (CC64 up->down transitions per second), ``pedal_depth_mean``
      (time-weighted mean CC64 value / 127), ``soft_pedal_fraction`` (CC67 down share); the span
      is first onset to last key release. No events = 0.
    * ``chord_async_ms`` / ``chord_async_beats``: median onset spread (max - min) of score
      positions with at least two matched notes; beats = / local smooth beat period.
    * ``notes_per_sec``: performed notes per second.
    """
    pn = ap.performance.notes
    out: dict[str, float] = {}
    v = pn["velocity"].astype(float)
    out["glob__vel_mean_midi"] = float(v.mean()) if len(v) else np.nan
    out["glob__vel_sd_midi"] = float(v.std()) if len(v) > 1 else np.nan
    out["glob__vel_range_p95_p5_midi"] = float(np.subtract(*np.percentile(v, [95, 5]))) \
        if len(v) else np.nan
    n = tc.notes
    bar_mean = n.groupby("measure_idx")["vel_midi"].mean() if len(n) else pd.Series(dtype=float)
    out["glob__vel_bar_sd_midi"] = float(bar_mean.std()) if len(bar_mean) > 1 else np.nan
    if articulation is not None and len(articulation):
        y = articulation["y"].to_numpy(float)
        out["glob__art_median_log"] = float(np.median(y))
        out["glob__art_iqr_log"] = float(np.subtract(*np.percentile(y, [75, 25])))
    else:
        out["glob__art_median_log"] = out["glob__art_iqr_log"] = np.nan

    # legato overlap on the skyline melody
    top = basis.notes[["score_id", "beat", "duration_beat", "is_top"]]
    dur = pd.DataFrame({"performance_id": pn["id"].astype(str),
                        "duration_sec": pn["duration_sec"].astype(float)}
                       ).drop_duplicates("performance_id")
    m = n[["score_id", "performance_id", "onset_sec"]].drop_duplicates("score_id")
    m = m.merge(top, on="score_id").merge(dur, on="performance_id")
    m = m[m["is_top"] > 0.5].sort_values("beat").drop_duplicates("beat")
    if len(m) >= 3:
        b, d = m["beat"].to_numpy(float), m["duration_beat"].to_numpy(float)
        on, off = m["onset_sec"].to_numpy(float), (m["onset_sec"] + m["duration_sec"]).to_numpy()
        adj = np.isclose(b[:-1] + d[:-1], b[1:], atol=1e-6)
        out["glob__legato_overlap_frac"] = float(np.mean(off[:-1][adj] > on[1:][adj])) \
            if adj.any() else np.nan
    else:
        out["glob__legato_overlap_frac"] = np.nan

    t0 = float(pn["onset_sec"].min()) if len(pn) else 0.0
    t1 = float((pn["onset_sec"] + pn["duration_sec"]).max()) if len(pn) else 0.0
    out.update(_pedal_features(ap.performance.pedal, t0, t1, pedal_threshold))

    pos = tc.positions
    ch = pos[(pos["n_notes"] >= 2) & ~pos["gross_outlier"]] if len(pos) else pos
    if len(ch):
        spread = ch["chord_spread_sec"].to_numpy(float)
        out["glob__chord_async_ms"] = 1000 * float(np.median(spread))
        out["glob__chord_async_beats"] = float(np.median(spread / ch["beat_period_sec"]))
    else:
        out["glob__chord_async_ms"] = out["glob__chord_async_beats"] = np.nan
    out["glob__notes_per_sec"] = len(pn) / (t1 - t0) if t1 > t0 else np.nan
    return out


# --------------------------------------------------------------------------- one performance

_CTRL_KEYS = (
    "even_ioi_cv", "even_vel_sd_midi", "even_note_rate_nps", "even_strict_ioi_cv",
    "even_strict_vel_sd_midi", "even_strict_note_rate_nps",
    "hand_async_mean_ms", "hand_async_sd_beats", "hand_async_vel_slope_ms",
    "hand_async_resid_sd_beats", "tempo_instability_log_sd", "tempo_phrase_log_sd",
    "tempo_drift_log", "pedal_blur_fraction", "pedal_blur_beats", "pedal_down_fraction",
)  # fmt: skip
_VOICING_KEYS = ("vel_diff_mean_midi", "frac_melody_louder", "lead_mean_ms", "lead_vel_corr")
_DYN_KEYS = ("hairpin_agree_frac", "hairpin_mean_signed_change_vel", "level_agree_frac",
             "level_vel_per_step", "accent_mean_excess_vel", "level_velocity_spearman")


def _n_written_bars(score: Any) -> int:
    ms = score.measures
    return int(len(np.unique(ms["number"]))) if len(ms) else 0


def segment_features(ap: Any, config: ExtractConfig | None = None) -> SegmentFeatures:
    """All own-performance features of one aligned performance (no references).

    ``ap`` must come from ``pianolens.align.align_performance`` (performed score with ``part``).
    A failing component leaves its columns NaN and is recorded in ``errors``; this never raises
    for a performance that aligned.
    """
    cfg = config or ExtractConfig()
    pid = str(ap.performance.performance_id)
    feats: dict[str, float] = {}
    errors: dict[str, str] = {}
    curves: dict[str, pd.Series] = {}

    try:
        c = correctness(ap).summary
        ng = max(int(c["n_score_notes"]), 1)
        feats.update({
            "corr__accuracy": _f(c["accuracy"]), "corr__error_rate": _f(c["error_rate"]),
            "corr__wrong_pitch_rate": c["n_wrong_pitch"] / ng,
            "corr__missed_rate": c["n_missed"] / ng, "corr__extra_rate": c["n_extra"] / ng,
            "corr__match_ratio": _f(c["match_ratio"]),
        })  # fmt: skip
    except Exception as e:  # noqa: BLE001 - record and continue
        errors["correctness"] = repr(e)

    tc = None
    try:
        tc = tempo_model(ap, cfg.tempo)
        s = tc.summary
        nb = max(_n_written_bars(ap.score), 1)
        feats.update({
            "tempo__log_bpm": float(np.log(s["tempo_bpm_geomean"])),
            "tempo__overall_vs_smooth_log": float(np.log(s["tempo_bpm_overall"]
                                                         / s["tempo_bpm_geomean"])),
            "tempo__smooth_log_sd": _f(s["tempo_log_sd"]),
            "tempo__smooth_log_p90_p10": _f(s["tempo_log_p90_p10"]),
            "tempo__jitter_rms_beats": _f(s["jitter_rms_beats"]),
            "tempo__jitter_mad_beats": _f(s["jitter_mad_beats"]),
            "tempo__jitter_nometric_rms_beats": _f(s.get("jitter_nometric_rms_beats")),
            "tempo__pauses_per_bar": s.get("n_pauses", 0) / nb,
        })  # fmt: skip
        curves["timing"] = reference_residuals(tc)
        curves["tempo"] = _curve_series(tc.beats["tempo_log_ratio"],
                                        tc.beats["beat"].round(6).to_numpy())
        curves["velocity"] = _curve_series(tc.notes["vel_midi"],
                                           tc.notes["score_id"].astype(str).to_numpy())
    except Exception as e:  # noqa: BLE001
        errors["tempo"] = repr(e)

    if tc is not None:
        try:
            cs = control_features(ap, tc, references=None, config=cfg.control).summary
            feats.update({f"ctrl__{k}": _f(cs.get(k)) for k in _CTRL_KEYS})
        except Exception as e:  # noqa: BLE001
            errors["control"] = repr(e)

        basis = None
        try:
            basis = score_basis(ap.score)
            data = channel_data(ap, basis, tc, cfg.shaping)
            art = data.get("articulation")
            if art is not None and len(art):
                curves["articulation"] = _curve_series(art["y"], art["score_id"].astype(str))
            feats.update(global_descriptors(ap, tc, basis, art, cfg.control.pedal_threshold))
        except Exception as e:  # noqa: BLE001
            errors["global"] = repr(e)

        if basis is not None:
            nbw = _n_written_bars(ap.score)
            for ch in cfg.coherence_channels:
                feats[f"shape__coherence_{ch}_r2"] = np.nan
                feats[f"shape__coherence_{ch}_r2_no_markings"] = np.nan
            if nbw >= cfg.coherence_min_bars:
                try:
                    # short-segment gate: ``coherence_min_bars`` replaces the 12-bar default
                    # of ShapingConfig.min_written_bars (F-05d; 1-bar blocks here)
                    scfg = replace(cfg.shaping, n_folds=min(cfg.shaping.n_folds, nbw),
                                   min_written_bars=cfg.coherence_min_bars)
                    coh = structural_coherence(ap, basis, tc, scfg).summary.set_index("channel")
                    for ch in cfg.coherence_channels:
                        for w in ("r2", "r2_no_markings"):
                            v = _f(coh.loc[ch, w]) if ch in coh.index else np.nan
                            feats[f"shape__coherence_{ch}_{w}"] = max(v, -cfg.coherence_clip) \
                                if np.isfinite(v) else np.nan
                except Exception as e:  # noqa: BLE001
                    errors["coherence"] = repr(e)
            try:
                rep = repeated_material(ap, basis, tc, cfg.shaping).summary.set_index("channel")
                for ch in ("velocity", "timing", "articulation"):
                    feats[f"shape__repeat_{ch}_r"] = _f(rep.loc[ch, "r_mean"]) \
                        if ch in rep.index else np.nan
            except Exception as e:  # noqa: BLE001
                errors["repeats"] = repr(e)
            try:
                vs = voicing(ap, basis, tc, cfg.shaping).summary
                feats.update({f"shape__voicing_{k}": _f(vs.get(k)) for k in _VOICING_KEYS})
            except Exception as e:  # noqa: BLE001
                errors["voicing"] = repr(e)
            try:
                ds = dynamic_compliance(ap, basis, tc, cfg.shaping).summary
                feats.update({f"shape__dyn_{k}": _f(ds.get(k)) for k in _DYN_KEYS})
            except Exception as e:  # noqa: BLE001
                errors["dynamics"] = repr(e)
    return SegmentFeatures(pid, feats, curves, tc, errors)


# --------------------------------------------------------------------------- references


# R-04 S1 curve agreement; promoted to the tier D module (F-06), same definition.
_agreement = curve_agreement


def reference_features(target: SegmentFeatures, references: Mapping[str, SegmentFeatures],
                       config: ExtractConfig | None = None) -> dict[str, float]:
    """Reference-based features (``ref__*``) of ``target`` against other performances of the
    same score. The target's own id is always left out.

    * ``ref__timing_noise_rms_beats`` / ``_ms``, ``ref__timing_consensus_r2``: F-04 timing noise
      against the leave-one-out consensus fine timing (``min_references``).
    * ``ref__<curve>_r`` / ``ref__<curve>_rms`` for ``CURVES``: Pearson r and RMS difference
      between the target's centred curve and the centred mean reference curve (units of the
      curve: MIDI velocity, beats, log tempo ratio, log articulation ratio).
    * ``ref__rel_<key>`` for ``RELATIVE_KEYS``: own value minus the median of the references.
    * ``ref__n_references``.

    Uses only the references' performances, never their labels.
    """
    cfg = config or ExtractConfig()
    refs = {k: v for k, v in references.items() if k != target.performance_id}
    out: dict[str, float] = {"ref__n_references": float(len(refs))}
    series = {k: reference_residuals(v.tempo) for k, v in refs.items() if v.tempo is not None}
    if target.tempo is not None and series:
        _, s = timing_noise(target.tempo, series, leave_out=target.performance_id,
                            min_references=cfg.min_references)
        out["ref__timing_noise_rms_beats"] = _f(s.get("timing_noise_rms_beats"))
        out["ref__timing_noise_rms_ms"] = _f(s.get("timing_noise_rms_ms"))
        out["ref__timing_consensus_r2"] = _f(s.get("timing_consensus_r2"))
    else:
        out["ref__timing_noise_rms_beats"] = out["ref__timing_noise_rms_ms"] = np.nan
        out["ref__timing_consensus_r2"] = np.nan
    for name in CURVES:
        t = target.curves.get(name)
        rs = [v.curves[name] for v in refs.values() if name in v.curves]
        r, rms = _agreement(t, rs, cfg.curve_min_references, cfg.curve_min_points) \
            if t is not None else (np.nan, np.nan)
        out[f"ref__{name}_r"], out[f"ref__{name}_rms"] = r, rms
    for key in RELATIVE_KEYS:
        vals = np.array([v.features.get(key, np.nan) for v in refs.values()], dtype=float)
        vals = vals[np.isfinite(vals)]
        own = target.features.get(key, np.nan)
        out[f"ref__rel_{key.split('__', 1)[1]}"] = float(own - np.median(vals)) \
            if len(vals) and np.isfinite(own) else np.nan
    return out


def group_features(aps: Sequence[Any], is_reference: Sequence[bool],
                   config: ExtractConfig | None = None) -> pd.DataFrame:
    """Features of several performances of one score, with reference features.

    Args:
        aps: aligned performances of the same score (each from ``align_performance``).
        is_reference: which of them may serve as references (e.g. human performances only).
            Every performance gets reference features against the *other* references.
        config: :class:`ExtractConfig`.

    Returns:
        One row per performance: ``performance_id``, ``errors`` (``;``-joined component names)
        and every feature column.
    """
    cfg = config or ExtractConfig()
    segs = [segment_features(ap, cfg) for ap in aps]
    refs = {s.performance_id: s for s, r in zip(segs, is_reference, strict=True) if r}
    rows = []
    for s in segs:
        row = {"performance_id": s.performance_id, "errors": ";".join(sorted(s.errors)),
               **s.features, **reference_features(s, refs, cfg)}
        rows.append(row)
    return pd.DataFrame(rows)
