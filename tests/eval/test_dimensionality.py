import numpy as np
import pytest

from pianolens.eval.dimensionality import (
    column_shuffle,
    explained_variance_ratio,
    heldout_r2_curve,
    loo_r2_curve,
    mean_curve_share,
    n_components_for,
    phase_randomize,
    whittaker_smooth,
)


def _low_rank(n=60, p=80, k=3, noise=0.0, seed=0):
    rng = np.random.default_rng(seed)
    scores = rng.normal(size=(n, k)) * np.array([5.0, 3.0, 2.0][:k])
    basis = np.linalg.qr(rng.normal(size=(p, k)))[0].T
    return scores @ basis + 7.0 + noise * rng.normal(size=(n, p))


def test_exact_rank_counts():
    x = _low_rank(k=3)
    r = explained_variance_ratio(x)
    assert r[:3].sum() == pytest.approx(1.0)
    assert r[3:].max() < 1e-12
    assert n_components_for(r, 0.999) == 3
    assert n_components_for(r, 0.5) == 1  # 25/(25+9+4) = 0.66


def test_n_components_threshold_edges():
    assert n_components_for(np.array([0.5, 0.3, 0.2]), 0.8) == 2
    assert n_components_for(np.array([0.5, 0.3, 0.2]), 0.81) == 3
    assert n_components_for(np.zeros(3), 0.8) == 0


def test_heldout_r2_recovers_rank_and_penalizes_noise():
    x = _low_rank(k=2, noise=0.01)
    r2 = heldout_r2_curve(x, ks=[1, 2, 5])
    assert r2[1] > 0.999
    assert r2[0] < r2[1]
    # pure noise: held-out reconstruction with few components is poor
    noise = np.random.default_rng(1).normal(size=(50, 100))
    assert heldout_r2_curve(noise, ks=[5])[0] < 0.15
    # while in-sample 5 of 49 components "explain" more than their share
    assert explained_variance_ratio(noise)[:5].sum() > 0.1


def test_loo_matches_rank():
    x = _low_rank(n=12, k=2, noise=0.0)
    r2 = loo_r2_curve(x, ks=[1, 2])
    assert r2[1] == pytest.approx(1.0, abs=1e-9)


def test_mean_curve_share():
    rng = np.random.default_rng(0)
    base = np.sin(np.linspace(0, 6, 40))
    x = base + 0.0 * rng.normal(size=(10, 40))
    assert mean_curve_share(x) == pytest.approx(1.0)
    x = rng.normal(size=(2000, 40))
    assert mean_curve_share(x) < 0.01


def test_phase_randomize_keeps_spectrum_and_coupling():
    rng = np.random.default_rng(0)
    a = rng.normal(size=(5, 64)).cumsum(axis=1)
    b = 2 * a + 1
    sa, sb = phase_randomize([a, b], np.random.default_rng(1))
    np.testing.assert_allclose(np.abs(np.fft.rfft(sa, axis=1)), np.abs(np.fft.rfft(a, axis=1)),
                               atol=1e-8)
    np.testing.assert_allclose(sa.var(axis=1), a.var(axis=1), rtol=1e-8)
    np.testing.assert_allclose(sa.mean(axis=1), a.mean(axis=1), atol=1e-9)
    np.testing.assert_allclose(sb, 2 * sa + 1, atol=1e-8)  # same phases -> coupling kept
    assert not np.allclose(sa, a)
    # odd length
    (so,) = phase_randomize(a[:, :63], np.random.default_rng(2))
    np.testing.assert_allclose(so.var(axis=1), a[:, :63].var(axis=1), rtol=1e-8)


def test_phase_randomize_destroys_shared_structure():
    x = _low_rank(n=60, p=128, k=1, noise=0.0)  # every row is the same shape
    (s,) = phase_randomize(x - x.mean(axis=1, keepdims=True), np.random.default_rng(0))
    assert explained_variance_ratio(s)[0] < 0.5


def test_column_shuffle_keeps_columns():
    x = np.arange(20.0).reshape(5, 4)
    s = column_shuffle(x, np.random.default_rng(0))
    np.testing.assert_array_equal(np.sort(s, axis=0), np.sort(x, axis=0))


def test_whittaker_gain_and_null_space():
    p, period = 400, 20.0
    t = np.arange(p, dtype=float)
    quad = 0.01 * t**2 - t + 3
    np.testing.assert_allclose(whittaker_smooth(quad, period), quad, atol=1e-6)

    def gain(per):
        y = np.sin(2 * np.pi * t / per)
        z = whittaker_smooth(y, period)
        mid = slice(100, 300)
        return np.std(z[mid]) / np.std(y[mid])

    assert gain(period) == pytest.approx(0.5, abs=0.06)
    assert gain(period / 2) < 0.03
    assert gain(2 * period) > 0.97
    # matrix input: rows smoothed independently
    y2 = np.vstack([quad, 2 * quad])
    np.testing.assert_allclose(whittaker_smooth(y2, period)[1], 2 * quad, atol=1e-5)
