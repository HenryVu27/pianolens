"""Known-answer tests for pianolens.features.extract (R-04 batch features)."""

from __future__ import annotations

import numpy as np
import pytest

from pianolens.features.extract import (
    ExtractConfig,
    group_features,
    reference_features,
    segment_features,
)
from tests.features.test_control import build, scale_texture


def _vel_pattern(notes, offset=0.0):
    """Velocity varying with pitch (so curves have shape) plus a constant offset."""
    return np.array([50 + (p % 12) * 2 + offset for _, _, p, *_ in notes], dtype=float)


def test_deadpan_has_zero_spread_timing_and_no_pedal():
    notes = scale_texture(8)
    f = segment_features(build(notes, lambda b: 0.5 * b)).features
    assert f["glob__vel_sd_midi"] == pytest.approx(0.0)
    assert f["glob__vel_range_p95_p5_midi"] == pytest.approx(0.0)
    assert f["tempo__jitter_rms_beats"] == pytest.approx(0.0, abs=1e-6)
    assert f["tempo__smooth_log_sd"] == pytest.approx(0.0, abs=1e-6)
    assert f["glob__chord_async_ms"] == pytest.approx(0.0, abs=1e-6)
    assert f["glob__pedal_presses_per_sec"] == 0.0
    assert f["glob__pedal_depth_mean"] == 0.0
    assert f["corr__accuracy"] == pytest.approx(1.0)
    assert np.log(120.0) == pytest.approx(f["tempo__log_bpm"], abs=1e-6)  # 0.5 s per beat


def test_articulation_and_notes_per_sec():
    notes = scale_texture(8)
    f = segment_features(build(notes, lambda b: 0.5 * b)).features
    # key-down 0.2 s; RH eighths are 0.25 s notated at 0.5 s/beat -> log(0.8); LH log(0.4)
    assert f["glob__art_median_log"] == pytest.approx(np.log(0.8), abs=1e-6)
    span = 31.5 * 0.5 + 0.2  # last RH eighth at beat 31.5, key-down 0.2 s
    assert f["glob__notes_per_sec"] == pytest.approx(len(notes) / span, rel=1e-6)


def test_short_segment_coherence_is_undefined():
    notes = scale_texture(4)  # 4 written bars < coherence_min_bars
    f = segment_features(build(notes, lambda b: 0.5 * b, vel=_vel_pattern(notes))).features
    assert np.isnan(f["shape__coherence_velocity_r2"])
    f8 = segment_features(build(scale_texture(8), lambda b: 0.5 * b,
                                vel=_vel_pattern(scale_texture(8)))).features
    assert np.isfinite(f8["shape__coherence_velocity_r2"])
    assert -1.0 <= f8["shape__coherence_velocity_r2"] <= 1.0
    assert "shape__coherence_tempo_r2" not in f8


def test_pedal_depth_and_presses():
    notes = scale_texture(4)
    total = 15.5 * 0.5 + 0.2  # first onset 0 to the last key release
    ped = [(0.0, 64, 127), (total / 2, 64, 0)]
    f = segment_features(build(notes, lambda b: 0.5 * b, pedal=ped)).features
    assert f["glob__pedal_presses_per_sec"] == pytest.approx(1 / total)
    assert f["glob__pedal_depth_mean"] == pytest.approx(0.5, abs=0.01)
    assert f["glob__soft_pedal_fraction"] == 0.0


def test_reference_features_identical_and_shifted():
    notes = scale_texture(8)
    cfg = ExtractConfig()
    rng = np.random.default_rng(0)
    offs = rng.normal(0, 0.01, len(notes))
    refs = {f"r{i}": segment_features(build(notes, lambda b: 0.5 * b, vel=_vel_pattern(notes),
                                            offsets=offs, pid=f"r{i}"), cfg)
            for i in range(4)}  # fmt: skip
    same = segment_features(build(notes, lambda b: 0.5 * b, vel=_vel_pattern(notes),
                                  offsets=offs, pid="t"), cfg)
    r = reference_features(same, refs, cfg)
    assert r["ref__n_references"] == 4
    assert r["ref__velocity_r"] == pytest.approx(1.0)
    assert r["ref__velocity_rms"] == pytest.approx(0.0, abs=1e-9)
    assert r["ref__timing_r"] == pytest.approx(1.0)
    assert r["ref__timing_noise_rms_beats"] == pytest.approx(0.0, abs=1e-9)
    assert r["ref__rel_vel_mean_midi"] == pytest.approx(0.0)
    louder = segment_features(build(notes, lambda b: 0.5 * b, vel=_vel_pattern(notes, 10),
                                    offsets=offs, pid="t2"), cfg)
    r2 = reference_features(louder, refs, cfg)
    assert r2["ref__rel_vel_mean_midi"] == pytest.approx(10.0)
    assert r2["ref__velocity_rms"] == pytest.approx(0.0, abs=1e-9)  # curves are centred
    slower = segment_features(build(notes, lambda b: 0.6 * b, vel=_vel_pattern(notes),
                                    offsets=offs, pid="t3"), cfg)
    assert reference_features(slower, refs, cfg)["ref__rel_log_bpm"] == pytest.approx(
        np.log(0.5 / 0.6), abs=1e-3)


def test_group_features_leave_one_out_and_non_references():
    notes = scale_texture(8)
    aps = [build(notes, lambda b: 0.5 * b, vel=_vel_pattern(notes, i), pid=f"p{i}")
           for i in range(5)]
    df = group_features(aps, [True, True, True, True, False])
    assert list(df["performance_id"]) == [f"p{i}" for i in range(5)]
    # references never include the target itself; the non-reference sees all 4
    assert list(df["ref__n_references"]) == [3, 3, 3, 3, 4]
    # p4 is 4 velocity units above p0..p3 (median 1.5)
    assert df.loc[4, "ref__rel_vel_mean_midi"] == pytest.approx(4 - 1.5)
    assert (df["errors"] == "").all()
