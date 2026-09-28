"""Known-answer tests for pianolens.features.interpretation (F-06, tier D)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from pianolens.eval.dimensionality import whittaker_smooth
from pianolens.features.interpretation import (
    InterpretationConfig,
    ReferenceSet,
    TargetCurves,
    curve_agreement,
    interpret,
    map_score_beats,
    parallel_analysis,
    references_from_notes,
    shared_core,
    target_from_aligned,
    target_from_notes,
    target_from_references,
)
from tests.features.test_control import build, scale_texture

W = 64  # beats
BPB = 4


def bumps(w: int, centers, width: float = 4.0) -> np.ndarray:
    """Localized, row-centered, unit-norm shapes (like section-level expressive gestures)."""
    x = np.arange(w)
    c = np.array([np.exp(-0.5 * ((x - m) / width) ** 2) for m in centers])
    c -= c.mean(axis=1, keepdims=True)
    q, _ = np.linalg.qr(c.T)
    return q.T[: len(centers)] * np.sign(q.T[: len(centers)].sum(axis=1, keepdims=True) + 1e-12)


def model(k: int = 3, seed: int = 0):
    comps = bumps(W, np.linspace(10, 54, k))
    sd = np.array([2.5, 2.2, 2.0, 1.8, 1.6])[:k]
    x = np.arange(W)
    mu = 1.2 * np.sin(2 * np.pi * x / 32) + 0.6 * np.cos(2 * np.pi * x / 21)
    mu -= mu.mean()
    return comps, sd, mu


def synth(n: int = 80, k: int = 3, seed: int = 0, noise: float = 0.3, smooth: bool = False):
    rng = np.random.default_rng(seed)
    comps, sd, mu = model(k)
    z = rng.normal(size=(n, k)) * sd
    e = rng.normal(size=(n, W)) * noise
    if smooth:
        e = whittaker_smooth(e, 6.0)
        e *= noise / e.std()
    x = mu + z @ comps + e
    return x - x.mean(axis=1, keepdims=True)


def refset(tempo: np.ndarray, vel: np.ndarray | None = None, prov=None, ids=None) -> ReferenceSet:
    n = len(tempo)
    vel = tempo * 10 if vel is None else vel
    ids = np.array([f"r{i}" for i in range(n)] if ids is None else ids, dtype=object)
    prov = np.array(["transcribed"] * n if prov is None else prov, dtype=object)
    return ReferenceSet(
        piece_id="synth", grid=np.arange(W, dtype=float), pos_grid=np.arange(W, dtype=float),
        bar_starts=np.arange(0, W, BPB, dtype=float), beats_per_bar=BPB, performance_ids=ids,
        provenance=prov, source_ids=ids.copy(), tempo=tempo.copy(), velocity=vel.copy(),
        velocity_smooth=vel.copy(), timing=np.zeros((n, W)), tempo_bpm=np.full(n, 120.0),
    )  # fmt: skip


def target(tempo: np.ndarray, vel: np.ndarray | None = None, pid="t", prov="disklavier"
           ) -> TargetCurves:
    vel = tempo * 10 if vel is None else vel
    return TargetCurves(
        performance_id=pid, provenance=prov, grid=np.arange(W, dtype=float),
        bar_starts=np.arange(0, W, BPB, dtype=float), bar_numbers=np.arange(1, W // BPB + 1),
        tempo=tempo.copy(), velocity=vel.copy(), velocity_smooth=vel.copy(),
        pos_grid=np.arange(W, dtype=float), timing=np.zeros(W), tempo_bpm=120.0,
    )  # fmt: skip


CFG = InterpretationConfig(window_bars=None, n_surrogates=40, min_references=10, pa_n=None)


def typical_target(k: int = 3, noise: float = 0.1, seed: int = 99) -> np.ndarray:
    comps, sd, mu = model(k)
    rng = np.random.default_rng(seed)
    t = mu + (0.5 * sd * np.array([1, -1, 1, -1, 1][:k])) @ comps + rng.normal(size=W) * noise
    return t - t.mean()


# --------------------------------------------------------------------------- decomposition


@pytest.mark.parametrize("k", [1, 2, 3])
@pytest.mark.parametrize("smooth", [False, True])
def test_horn_parallel_analysis_recovers_k(k, smooth):
    x = synth(k=k, smooth=smooth)
    got, ev, thr = parallel_analysis(x, n_surrogates=40, rng=np.random.default_rng(0))
    assert got == k
    assert ev[k - 1] > thr[k - 1] and ev[k] <= thr[k]


def test_horn_undercounts_many_strong_components_and_sequential_does_not():
    """Known limitation (documented): strong components leak into Horn's surrogates."""
    comps, _, mu = model(5)
    rng = np.random.default_rng(0)
    x = mu + (rng.normal(size=(80, 5)) * [6.0, 4.5, 3.5, 3.0, 2.5]) @ comps \
        + rng.normal(size=(80, W)) * 0.3
    x -= x.mean(axis=1, keepdims=True)
    horn, _, _ = parallel_analysis(x, 40, rng=np.random.default_rng(0), method="horn")
    seq, _, _ = parallel_analysis(x, 40, rng=np.random.default_rng(0), method="sequential")
    assert horn < 5 and seq == 5


def test_fixed_n_parallel_analysis_uses_subsamples():
    x = synth(n=200, k=2)
    core = shared_core(x, rng=np.random.default_rng(0), pa_n=50, pa_draws=5)
    assert core.k == 2 and core.n_refs == 200  # k from n = 50 draws, components from all rows


def test_pure_noise_has_no_shared_component():
    rng = np.random.default_rng(3)
    x = whittaker_smooth(rng.normal(size=(80, W)), 6.0)
    x *= np.linspace(0.5, 2.0, W)  # a per-beat variance profile alone is not shared structure
    x = x - x.mean(1, keepdims=True)
    for method in ("horn", "sequential"):
        k, _, _ = parallel_analysis(x, 40, rng=np.random.default_rng(0), method=method)
        assert k == 0


def test_shared_core_recovers_the_subspace():
    comps, _, _ = model(3)
    core = shared_core(synth(k=3), rng=np.random.default_rng(0), pa_n=None)
    assert core.k == 3
    s = np.linalg.svd(core.components @ comps.T, compute_uv=False)  # cosines of the angles
    assert s.min() > 0.99
    assert 0.5 < core.shared_share < 1.0


# --------------------------------------------------------------------------- interpret


def test_typical_target_is_typical_and_not_flagged():
    x = synth()
    r = interpret(target(typical_target()), refset(x), config=CFG)
    w = r.windows.set_index("block").loc["tempo"]
    assert w["status"] == "ok" and w["k_shared"] == 3
    assert w["typicality_pct"] > 0.2
    assert w["individual_share"] < 0.2  # built from the shared components only
    assert not w["too_flat"] and not w["too_extreme"]
    b = r.bars[r.bars["block"] == "tempo"]
    assert not b["out_of_band"].any()
    assert r.features["interp__tempo_frac_bars_out_of_band"] == 0.0


def test_injected_out_of_band_bar_is_flagged_exactly_there():
    t = typical_target()
    bar = 7  # beats 28-31
    t[bar * BPB:(bar + 1) * BPB] += 4.0
    t -= t.mean()
    r = interpret(target(t), refset(synth()), config=CFG)
    b = r.bars[r.bars["block"] == "tempo"]
    assert b.loc[b["out_of_band"].astype(bool), "bar"].tolist() == [bar]
    assert b.loc[b["bar"] == bar, "dev_mean"].item() > 2.5  # +4 minus the re-centering


def test_windowed_flags_still_localize():
    t = typical_target()
    t[40:44] -= 4.0  # bar 10
    t -= t.mean()
    cfg = InterpretationConfig(window_bars=8, n_surrogates=40, min_references=10, pa_n=None)
    r = interpret(target(t), refset(synth()), config=cfg)
    assert sorted(r.windows.loc[r.windows["block"] == "tempo", "window"]) == [0, 1]
    b = r.bars[r.bars["block"] == "tempo"]
    assert b.loc[b["out_of_band"].astype(bool), "bar"].tolist() == [10]


def test_deadpan_target_is_not_typical():
    """Guard (R-06): a flat rendition sits at the centre of the shared space but must come out
    atypical and too flat, never maximally typical."""
    r = interpret(target(np.zeros(W)), refset(synth()), config=CFG)
    w = r.windows.set_index("block").loc["tempo"]
    assert w["too_flat"] and w["magnitude"] == pytest.approx(0.0)
    assert w["magnitude_pct"] == 0.0
    assert w["typicality_pct"] < 0.05
    # the shared coordinates alone would look ordinary: the magnitude term is what flags it
    assert w["mahal2_shared"] < w["mahal2"]


def test_deadpan_variants_are_not_typical():
    """R-06 audit lesson: check deadpan plus small noise and half-deadpans, not only an exact
    deadpan. Channels are judged separately, so a half-deadpan is flagged on its flat channel
    only."""
    x = synth()
    t = typical_target()
    rng = np.random.default_rng(5)
    noisy = rng.normal(size=W) * 0.05  # deadpan plus small noise
    r = interpret(target(noisy, 10 * noisy), refset(x), config=CFG)
    w = r.windows.set_index("block")
    for b in ("tempo", "velocity"):
        assert w.loc[b, "too_flat"] and w.loc[b, "typicality_pct"] < 0.05
    # flat timing with human velocity, and the reverse
    for flat, human in (("tempo", "velocity"), ("velocity", "tempo")):
        tv = np.zeros(W) if flat == "tempo" else t
        vv = np.zeros(W) if flat == "velocity" else 10 * t
        w = interpret(target(tv, vv), refset(x), config=CFG).windows.set_index("block")
        assert w.loc[flat, "too_flat"] and w.loc[flat, "typicality_pct"] < 0.05
        assert not w.loc[human, "too_flat"] and w.loc[human, "typicality_pct"] > 0.2


def test_flattened_expert_is_less_typical_than_the_expert():
    x = synth()
    t = typical_target()
    full = interpret(target(t), refset(x), config=CFG).windows.set_index("block").loc["tempo"]
    flat = interpret(target(0.15 * t), refset(x), config=CFG).windows.set_index("block")
    flat = flat.loc["tempo"]
    assert flat["too_flat"] and not full["too_flat"]
    assert flat["typicality_pct"] < full["typicality_pct"]


def test_extreme_shared_coordinates_are_atypical():
    comps, sd, mu = model(3)
    t = mu + np.array([6 * sd[0], 0, 0]) @ comps
    r = interpret(target(t - t.mean()), refset(synth()), config=CFG)
    w = r.windows.set_index("block").loc["tempo"]
    assert w["typicality_pct"] < 0.05
    assert abs(w["target_z"][0]) > 4 * sd[0]


def test_leave_one_out_excludes_the_target():
    x = synth()
    refs = refset(x)
    t, rest = target_from_references(refs, "r5")
    assert "r5" not in set(rest.performance_ids) and len(rest) == len(refs) - 1
    assert np.array_equal(t.tempo, x[5])
    a = interpret(t, refs, config=CFG)  # r5 still in: interpret must drop it
    b = interpret(t, rest, config=CFG)
    assert a.meta["loo_excluded"] == ["r5"] and b.meta["loo_excluded"] == []
    assert a.meta["n_references"] == b.meta["n_references"] == len(refs) - 1
    pd.testing.assert_frame_equal(a.bars, b.bars)
    assert a.features == pytest.approx(b.features, nan_ok=True)


def test_leave_one_out_by_source_id():
    refs = refset(synth())
    refs.source_ids[3] = "ASAP_Someone01"
    t = target(typical_target(), pid="asap:Chopin/x/Someone01")
    t.source_id = "ASAP_Someone01"
    r = interpret(t, refs, config=CFG)
    assert r.meta["loo_excluded"] == ["r3"]


def test_velocity_uses_sensor_references_when_enough():
    x = synth()
    prov = ["disklavier"] * 10 + ["transcribed"] * 70
    r = interpret(target(typical_target()), refset(x, prov=prov), config=CFG)
    assert r.meta["velocity_reference_source"] == "sensor"
    assert r.meta["velocity_confidence"] == "high"
    assert r.meta["references"]["velocity"] == [f"r{i}" for i in range(10)]
    assert len(r.meta["references"]["tempo"]) == 80
    # transcribed target: still low confidence
    r2 = interpret(target(typical_target(), prov="transcribed"), refset(x, prov=prov), config=CFG)
    assert r2.meta["velocity_confidence"] == "low"
    # too few sensor references: all used, low confidence, flagged in the features
    r3 = interpret(target(typical_target()), refset(x), config=CFG)
    assert r3.meta["velocity_reference_source"] == "all"
    assert r3.features["interp__velocity_low_confidence"] == 1.0


def test_expert_band_known_quantiles():
    shape = np.sin(2 * np.pi * np.arange(W) / W)
    c = np.linspace(0.5, 1.5, 81)  # median 1.0, deciles 0.6 / 1.4
    x = c[:, None] * shape
    r = interpret(target(0.3 * shape), refset(x), config=CFG)
    b = r.beats[r.beats["block"] == "tempo"]
    np.testing.assert_allclose(b["band_mid"], shape, atol=1e-9)
    np.testing.assert_allclose(b["band_lo"], np.minimum(0.6 * shape, 1.4 * shape), atol=1e-9)
    np.testing.assert_allclose(b["band_hi"], np.maximum(0.6 * shape, 1.4 * shape), atol=1e-9)
    np.testing.assert_allclose(b["target"], 0.3 * shape, atol=1e-9)
    # absolute tempo band in beats per minute: 120 * exp(curve)
    np.testing.assert_allclose(b["abs_mid"], 120 * np.exp(shape), rtol=1e-9)
    bars = r.bars[r.bars["block"] == "tempo"]
    assert len(bars) == W // BPB and bars["abs_mid"].notna().all()


def test_reference_features_known_answers():
    x = synth()
    cons = x.mean(axis=0)
    r = interpret(target(cons), refset(x), config=CFG).features
    assert r["ref__tempo_smooth_r"] == pytest.approx(1.0)
    assert r["ref__tempo_smooth_rms"] == pytest.approx(0.0, abs=1e-9)
    assert r["ref__tempo_smooth_rms_pct"] == 0.0  # closer to the consensus than every expert
    far = interpret(target(cons + 5 * np.sign(np.sin(np.arange(W)))), refset(x), config=CFG)
    assert far.features["ref__tempo_smooth_rms_pct"] == 1.0
    assert far.features["ref__n_references"] == 80.0


def test_curve_agreement_matches_extract():
    from pianolens.features import extract

    idx = np.arange(10)
    t = pd.Series(np.arange(10.0), index=idx)
    refs = [pd.Series(2 * np.arange(10.0) + 1, index=idx), pd.Series(np.arange(10.0), index=idx)]
    r, rms = curve_agreement(t, refs, 2, 5)
    assert r == pytest.approx(1.0)
    assert rms == pytest.approx(np.sqrt(np.mean((np.arange(10) - 4.5) ** 2)) * 0.5)
    assert extract._agreement(t, refs, 2, 5) == (r, rms)


# --------------------------------------------------------------------------- score mapping


def _score(bars, offset=0.0):
    rows = []
    for i, b in enumerate(bars):
        pitches = np.random.default_rng(b).integers(40, 90, 4)  # material of bar b
        for k in range(4):
            rows.append((offset + 4 * i + k, int(pitches[k])))
    return pd.DataFrame(rows, columns=["beat", "pitch"])


def test_map_score_beats_offset_and_repeat():
    ref = _score(list(range(12)))  # bars A0..A11 once
    src = _score([0, 1, 2, 3, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11], offset=-2.0)  # repeat 0-3
    m = map_score_beats(src, ref)
    assert m.mapped_fraction == 1.0
    beats = np.array([-2.0, 0.5, 13.0, 14.0, 20.0, 45.0])
    # -2 is the first beat (ref 0); 13 is the last beat of the first pass (ref 15); 14 starts
    # the repeat (ref 0 again); 20 -> ref 6; 45 is in the tail after the repeat -> ref 31
    np.testing.assert_allclose(m(beats), [0.0, 2.5, 15.0, 0.0, 6.0, 31.0])
    assert len(m.segments) == 2


def test_map_score_beats_marks_foreign_material_unmapped():
    ref = _score(list(range(8)))
    src = _score([0, 1, 2, 3, 20, 21, 4, 5, 6, 7])  # two bars the reference does not have
    m = map_score_beats(src, ref)
    mapped = m(np.arange(0.0, 40.0))
    assert np.isnan(mapped[16:24]).all()
    np.testing.assert_allclose(mapped[:16], np.arange(16.0))
    np.testing.assert_allclose(mapped[24:], np.arange(16.0, 32.0))


# --------------------------------------------------------------------------- end to end


def test_end_to_end_from_aligned_performances():
    """References and target as note-level performances of the same score: an expert-like
    target is not flagged, a deadpan one is too flat and atypical."""
    notes = scale_texture(16)
    beats = np.array([b for b, *_ in notes])
    rng = np.random.default_rng(0)
    bar_starts = np.arange(0, 64, 4.0)
    fine = np.linspace(0, 64, 6401)
    perfs = []
    depth = np.quantile(rng.normal(0.25, 0.08, 4000), np.linspace(0.02, 0.98, 40))
    for i in range(40):
        a = depth[(7 * i) % 40]  # slowing depth into bar 8 and at the end, spread over performers
        lt = -a * (np.exp(-0.5 * ((fine - 30) / 3) ** 2) + np.exp(-0.5 * ((fine - 62) / 3) ** 2))
        tmap = np.concatenate([[0], np.cumsum(0.5 * np.exp(-lt[:-1]) * np.diff(fine))])
        on = np.interp(beats, fine, tmap)
        vel = 60 + 12 * np.sin(np.pi * beats / 64) * rng.normal(1, 0.2) \
            + rng.normal(0, 2, len(beats))
        perfs.append({"performance_id": f"e{i}", "provenance": "disklavier", "beats": beats,
                      "onsets_sec": on, "velocities": vel})
    grid = np.arange(0, 64.0)
    refs = references_from_notes("synth", perfs, grid, np.unique(beats), bar_starts, 4.0)
    assert len(refs) == 40
    cfg = InterpretationConfig(window_bars=None, n_surrogates=20, min_references=10)
    ap = build(notes, lambda b: 0.5 * b)  # deadpan: constant tempo, constant velocity
    t = target_from_aligned(ap)
    assert np.nanmax(np.abs(t.tempo)) < 1e-6
    r = interpret(t, refs, config=cfg)
    w = r.windows.set_index("block")
    assert w.loc["tempo", "too_flat"] and w.loc["tempo", "typicality_pct"] < 0.05
    assert w.loc["velocity", "too_flat"]
    # an expert-like target from the same generator
    p = perfs[20]  # median depth: (7 * 20) % 40 = 20 -> quantile 0.5
    t2 = target_from_notes("x", "disklavier", p["beats"], p["onsets_sec"], p["velocities"],
                           bar_starts, 4.0)
    r2 = interpret(t2, refs.exclude(["e20"]), config=cfg)
    w2 = r2.windows.set_index("block")
    assert not w2.loc["tempo", "too_flat"] and w2.loc["tempo", "typicality_pct"] > 0.05
    assert r2.bars.loc[r2.bars["block"] == "tempo", "out_of_band"].sum() <= 1
