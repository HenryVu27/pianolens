import numpy as np
import pytest

from pianolens.models.expression_data import (
    VARIANTS,
    item_variants,
    load_item,
    pairs_from_item,
    save_item,
)
from pianolens.models.expression_io import global_seconds_per_quarter, note_expression


def _item(n=24, seed=0):
    rng = np.random.default_rng(seed)
    so = np.repeat(np.arange(n // 2, dtype=float), 2)  # two-note chords, one per quarter
    spq = 0.5
    on = so * spq + rng.normal(0, 0.02, n) + 1.0
    return {
        "score_onset_q": so, "score_dur_q": np.ones(n), "pitch": np.tile([60, 64], n // 2),
        "perf_onset_sec": on, "perf_dur_sec": 0.45 + rng.normal(0, 0.03, n),
        "velocity": np.clip(60 + rng.normal(0, 10, n), 1, 127).round().astype(int),
        "pedal": np.array([[1.0, 127.0], [2.0, 0.0]]), "spq_cond": spq, "vel_cond": 60.0,
        "origin": 0.0, "ts": np.array([[0.0, 4, 4]]),
    }


def test_all_variants_keep_notes_and_conditioning():
    it = _item()
    vs = item_variants(it, seed=1)
    assert list(vs) == list(VARIANTS)
    for v in vs.values():
        assert len(v["perf_onset_sec"]) == len(it["pitch"])
        assert v["spq_cond"] == it["spq_cond"] and v["vel_cond"] == it["vel_cond"]
        assert np.array_equal(v["pitch"], it["pitch"])
        assert v["velocity"].min() >= 1 and v["velocity"].max() <= 127


def test_deadpan_family_is_flat():
    it = _item()
    vs = item_variants(it, seed=1)
    dp = vs["deadpan"]
    e = note_expression(dp["score_onset_q"], dp["score_dur_q"], dp["perf_onset_sec"],
                        dp["perf_dur_sec"], dp["velocity"])
    assert np.nanmax(np.abs(e["log_ioi"])) < 1e-9
    assert set(dp["velocity"]) == {60} and len(dp["pedal"]) == 0
    assert set(vs["deadpan_vel+12"]["velocity"]) == {72}
    assert set(vs["deadpan_vel-12"]["velocity"]) == {48}
    slow = vs["deadpan_slow15"]
    assert global_seconds_per_quarter(slow["score_onset_q"], slow["perf_onset_sec"]) == \
        pytest.approx(0.5 * 1.15)
    nz = vs["deadpan_noise10_4"]
    assert 0.003 < np.std(nz["perf_onset_sec"] - dp["perf_onset_sec"]) < 0.02


def test_half_deadpans_and_jitter():
    it = _item()
    vs = item_variants(it, seed=1)
    ht, hv = vs["half_flat_timing"], vs["half_flat_velocity"]
    assert np.array_equal(ht["velocity"], it["velocity"])
    assert np.allclose(ht["perf_onset_sec"], vs["deadpan"]["perf_onset_sec"])
    assert np.array_equal(hv["perf_onset_sec"], it["perf_onset_sec"])
    assert set(hv["velocity"]) == {60} and len(hv["pedal"]) == 2
    j = vs["jitT20"]
    assert np.array_equal(j["velocity"], it["velocity"])
    assert not np.allclose(j["perf_onset_sec"], it["perf_onset_sec"])
    assert np.array_equal(vs["jitV8"]["perf_onset_sec"], it["perf_onset_sec"])


def test_scale_variants_scale_velocity_deviation():
    it = _item()
    vs = item_variants(it, seed=1)
    dev = it["velocity"] - 60.0
    assert np.abs(vs["scale0.5"]["velocity"] - (60 + 0.5 * dev)).max() <= 0.5 + 1e-9
    e1 = note_expression(**{k: it[k] for k in ("score_onset_q", "score_dur_q")},
                         perf_onset_sec=it["perf_onset_sec"], perf_dur_sec=it["perf_dur_sec"],
                         velocity=it["velocity"])
    ex = vs["scale1.5"]
    e2 = note_expression(ex["score_onset_q"], ex["score_dur_q"], ex["perf_onset_sec"],
                         ex["perf_dur_sec"], ex["velocity"])
    assert np.nanstd(e2["log_ioi"]) > np.nanstd(e1["log_ioi"])


def test_variants_seeded_and_roundtrip(tmp_path):
    it = _item()
    a = item_variants(it, seed=3, names=["deadpan_noise10_4"])["deadpan_noise10_4"]
    b = item_variants(it, seed=3, names=["deadpan_noise10_4"])["deadpan_noise10_4"]
    assert np.array_equal(a["perf_onset_sec"], b["perf_onset_sec"])
    save_item(tmp_path / "x.npz", a, kind="deadpan_noise10_4")
    back = load_item(tmp_path / "x.npz")
    assert str(back["kind"]) == "deadpan_noise10_4"
    assert len(pairs_from_item(back)) == len(it["pitch"])


def test_flat_training_rendition_is_near_flat():
    from pianolens.models.expression_data import flat_training_rendition

    it = _item(n=40)
    f = flat_training_rendition(it, np.random.default_rng(0))
    assert len(f["pedal"]) == 0 and np.array_equal(f["pitch"], it["pitch"])
    assert np.abs(f["velocity"] - 60).max() <= 4 * 5
    dp = item_variants(it, seed=0, names=["deadpan"])["deadpan"]
    assert np.abs(f["perf_onset_sec"] - dp["perf_onset_sec"]).max() < 0.06
