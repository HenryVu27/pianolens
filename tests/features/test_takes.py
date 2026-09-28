"""Known-answer tests for pianolens.features.takes (F-07)."""

from __future__ import annotations

import numpy as np
import pytest

from pianolens.features.score_basis import score_basis
from pianolens.features.takes import (
    TakesConfig,
    decompose_takes,
    spearman_brown,
    take_structure,
    variance_components,
)
from tests.features.test_shaping import build_part, manual_ap, melody_events


def test_variance_components_recovers_known_variances():
    rng = np.random.default_rng(0)
    n, k, a, b = 20000, 3, 4.0, 1.0
    s = rng.normal(0, np.sqrt(a), n)
    Y = s[:, None] + rng.normal(0, np.sqrt(b), (n, k)) + np.array([5.0, -2.0, 0.0])  # levels
    vc = variance_components(Y)
    assert vc["var_consistent"] == pytest.approx(a, rel=0.03)
    assert vc["var_specific"] == pytest.approx(b, rel=0.03)
    assert vc["icc_single"] == pytest.approx(a / (a + b), abs=0.01)
    assert vc["icc_mean"] == pytest.approx(spearman_brown(vc["icc_single"], k), abs=1e-9)
    assert vc["icc_single_ci_lo"] < vc["icc_single"] < vc["icc_single_ci_hi"]


def test_variance_components_pure_noise_and_identical_takes():
    rng = np.random.default_rng(1)
    vc = variance_components(rng.normal(size=(5000, 2)))
    assert abs(vc["icc_single"]) < 0.05
    assert abs(vc["var_consistent"]) < 0.05
    same = np.repeat(rng.normal(size=(100, 1)), 3, axis=1)
    vc = variance_components(same)
    assert vc["icc_single"] == pytest.approx(1.0)
    assert vc["var_specific"] == pytest.approx(0.0, abs=1e-12)
    assert np.isnan(variance_components(np.zeros((2, 2)))["icc_single"])


def _takes(k=3, *, a_vel=64.0, b_vel=16.0, a_t=0.02, b_t=0.01, seed=0, n_bars=24,
           vel_fn=None, drop=None):
    """k takes of one melody: shared intent + independent noise in velocity and timing.

    Timing: onset = beat * 0.5 s + (intent_i + noise_ij) * 0.5 s, i.e. dev_beats of variance
    a_t^2 (shared) and b_t^2 (per take), iid per note (fine-scale, so the smooth tempo does
    not absorb it)."""
    part = build_part(melody_events(n_bars=n_bars, step_q=0.5, seed=seed))
    rng = np.random.default_rng(seed + 100)
    probe = manual_ap(part)
    n = len(probe.score.notes)
    iv = rng.normal(0, np.sqrt(a_vel), n)
    it = rng.normal(0, a_t, n)
    aps = []
    for j in range(k):
        nv = rng.normal(0, np.sqrt(b_vel), n)
        nt = rng.normal(0, b_t, n)
        extra = vel_fn(j) if vel_fn else (lambda beat, pitch: 0.0)
        aps.append(manual_ap(
            part,
            vel=lambda beat, pitch, nv=nv, extra=extra: 64 + iv + nv + extra(beat, pitch),
            onset=lambda beat, nt=nt: (beat + it + nt) * 0.5,
            drop=drop(j) if drop else (),
        ))
    return aps


def test_decompose_recovers_shared_and_take_specific_variance():
    aps = _takes(k=3)
    res = decompose_takes(aps, bases=score_basis(aps[0].score))
    s = res.summary.set_index("channel")
    v = s.loc["velocity"]
    assert v["k"] == 3 and v["n"] == 192 and v["n_dropped"] == 0
    # velocity is rounded to integers (+1/12 variance per take)
    assert v["var_consistent"] == pytest.approx(64, rel=0.2)
    assert v["var_specific"] == pytest.approx(16 + 1 / 12, rel=0.2)
    assert v["icc_single"] == pytest.approx(64 / 80, abs=0.06)
    assert v["icc_mean"] == pytest.approx(spearman_brown(v["icc_single"], 3), abs=1e-9)
    t = s.loc["timing"]
    # timing residual keeps most fine-scale variance (the smooth fit takes a little)
    assert t["var_consistent"] == pytest.approx(0.02**2, rel=0.3)
    assert t["var_specific"] == pytest.approx(0.01**2, rel=0.3)
    assert t["icc_single"] == pytest.approx(0.8, abs=0.08)
    # decomposition is exact: y = consistent + specific
    o = res.observations["velocity"]
    assert np.allclose(o["y_1"], o["consistent"] + o["specific_1"])
    assert np.allclose(o[[f"specific_{j}" for j in range(3)]].sum(axis=1), 0)
    assert len(res.features["velocity"]) == len(o)
    # per-bar output
    b = res.bars[res.bars["channel"] == "velocity"]
    assert len(b) == 24 and b["specific_rms"].median() == pytest.approx(4.0, rel=0.35)
    bt = res.bars_by_take
    assert set(bt["take"]) == set(res.take_ids) and len(res.take_ids) == 3
    assert len(res.pairs[res.pairs["channel"] == "velocity"]) == 3


def test_level_offsets_are_reported_and_removed():
    aps = _takes(k=2, vel_fn=lambda j: (lambda beat, pitch: 10.0 * j))
    res = decompose_takes(aps)
    v = res.summary.set_index("channel").loc["velocity"]
    assert v["level_1"] - v["level_0"] == pytest.approx(10.0, abs=0.6)
    assert v["icc_single"] > 0.6  # the level offset is not take-specific shape


def test_identical_takes_have_no_specific_part():
    aps = _takes(k=2, b_vel=0.0, b_t=0.0)
    s = decompose_takes(aps).summary.set_index("channel")
    assert s.loc["velocity", "var_specific"] == pytest.approx(0.0, abs=1e-9)
    assert s.loc["velocity", "icc_single"] == pytest.approx(1.0)
    assert s.loc["timing", "icc_single"] == pytest.approx(1.0, abs=1e-6)


def test_unplayed_notes_are_intersected_and_counted():
    aps = _takes(k=2, drop=lambda j: range(10, 20) if j == 1 else ())
    res = decompose_takes(aps)
    v = res.summary.set_index("channel").loc["velocity"]
    assert v["n_dropped"] == 10
    n_all = len(aps[0].score.notes)
    assert v["n"] == n_all - 10


def test_take_structure_separates_structured_intent_from_noise():
    # shared intent is metrical (downbeats +12), noise is iid: structure explains the
    # consistent part / pair sum, not the take-specific part / pair difference
    def downbeat(j):
        return lambda beat, pitch: 12.0 * (np.mod(beat, 4) == 0)

    aps = _takes(k=3, a_vel=1.0, b_vel=16.0, vel_fn=downbeat, n_bars=32)
    res = decompose_takes(aps, config=TakesConfig(channels=("velocity",)))
    st = take_structure(res).set_index("channel").loc["velocity"]
    assert st["r2_consistent"] > 0.4
    assert st["r2_pair_sum"] > 0.3
    assert st["r2_pair_diff"] < 0.05
    assert st["r2_specific"] < 0.05
    assert st["delta_pair"] > 0.3 and st["n_pairs"] == 3


def test_take_structure_detects_structured_take_differences():
    # take 0 accents downbeats, take 1 un-accents them: the difference is structured
    def flip(j):
        return lambda beat, pitch: (12.0 if j == 0 else -12.0) * (np.mod(beat, 4) == 0)

    aps = _takes(k=2, a_vel=1.0, b_vel=16.0, vel_fn=flip, n_bars=32)
    res = decompose_takes(aps, config=TakesConfig(channels=("velocity",)))
    st = take_structure(res).set_index("channel").loc["velocity"]
    assert st["r2_pair_diff"] > 0.3
    assert st["r2_pair_sum"] < 0.05
    assert st["delta_pair"] < -0.3


def test_needs_two_takes():
    aps = _takes(k=2)
    with pytest.raises(ValueError):
        decompose_takes(aps[:1])
    with pytest.raises(ValueError):
        decompose_takes(aps, config=TakesConfig(channels=("loudness",)))


def test_take_structure_undefined_on_short_passages():
    # 8 written bars < 12 (F-05d minimum length): R² is NaN with a reason, not a noisy number
    aps = _takes(k=2, n_bars=8)
    res = decompose_takes(aps, config=TakesConfig(channels=("velocity",)))
    st = take_structure(res).set_index("channel").loc["velocity"]
    assert st["n_written_bars"] == 8 and st["n_blocks"] == 2
    assert st["undefined_reason"] == "too_few_bars"
    assert np.isnan(st.get("r2_pair_sum", np.nan))
