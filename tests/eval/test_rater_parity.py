import numpy as np
import pandas as pd
import pytest

from pianolens.eval import loo_means, rater_parity, ratings_matrix

NAN = np.nan


def test_loo_means_hand_computed():
    r = np.array([
        [1.0, 2.0, 3.0],
        [4.0, NAN, 6.0],
        [NAN, NAN, 7.0],
    ])
    m = loo_means(r)
    expected = np.array([
        [2.5, 2.0, 1.5],
        [6.0, 5.0, 4.0],
        [7.0, 7.0, NAN],
    ])
    np.testing.assert_allclose(m, expected, equal_nan=True)


def test_identical_raters_and_perfect_model_give_one():
    truth = np.linspace(0, 1, 20)
    r = np.tile(truth[:, None], (1, 4))
    r[::3, 1] = NAN  # missing values do not break it
    res = rater_parity(r, model=truth, min_segments=5)
    assert res.summary["n_raters"] == 4
    assert res.summary["rater_r_median"] == pytest.approx(1.0)
    assert res.summary["model_r_median"] == pytest.approx(1.0)
    assert res.summary["diff_mean"] == pytest.approx(0.0, abs=1e-12)


def test_known_noise_levels_match_theory():
    # rater = signal + N(0, sigma^2), signal ~ N(0, 1), K raters, complete matrix.
    # corr(rater_j, mean of other K-1) = 1 / sqrt((1+s2) * (1 + s2/(K-1)))
    # corr(signal, mean of other K-1)  = 1 / sqrt(1 + s2/(K-1))
    rng = np.random.default_rng(0)
    n, k, s2 = 4000, 6, 1.0
    signal = rng.normal(size=n)
    r = signal[:, None] + rng.normal(scale=np.sqrt(s2), size=(n, k))
    res = rater_parity(r, model=signal)
    rater_theory = 1 / np.sqrt((1 + s2) * (1 + s2 / (k - 1)))
    model_theory = 1 / np.sqrt(1 + s2 / (k - 1))
    assert res.summary["rater_r_mean_fisher"] == pytest.approx(rater_theory, abs=0.02)
    assert res.summary["model_r_mean_fisher"] == pytest.approx(model_theory, abs=0.02)
    assert res.summary["frac_raters_model_beats"] == 1.0
    # a model as noisy as one rater sits at parity
    noisy_model = signal + rng.normal(scale=np.sqrt(s2), size=n)
    res2 = rater_parity(r, model=noisy_model, n_boot=500)
    lo, hi = res2.summary["diff_mean_ci"]
    assert abs(res2.summary["diff_mean"]) < 0.02
    assert lo < 0.02 and hi > -0.02


def test_sparse_matrix_and_min_segments():
    rng = np.random.default_rng(1)
    n, k = 300, 12
    signal = rng.normal(size=n)
    r = signal[:, None] + rng.normal(size=(n, k))
    r[rng.random((n, k)) < 0.6] = NAN  # 60% missing
    r[:, 11] = NAN
    r[:5, 11] = 1.0  # rater 11 has only 5 ratings: excluded
    res = rater_parity(r, model=signal, min_segments=20)
    assert res.summary["n_raters"] == 11
    row = res.per_rater.set_index("rater").loc[11]
    assert np.isnan(row.r_rater)
    assert res.summary["diff_mean"] > 0


def test_dataframe_input_and_pivot():
    long = pd.DataFrame({
        "seg": ["a", "a", "b", "b", "c", "c", "d", "d"],
        "rater": ["x", "y", "x", "y", "x", "y", "x", "y"],
        "v": [1, 1, 2, 2, 3, 3, 4, 4],
    })
    mat = ratings_matrix(long, "seg", "rater", "v")
    assert mat.shape == (4, 2)
    res = rater_parity(mat, min_segments=3, method="spearman")
    assert list(res.per_rater.rater) == ["x", "y"]
    assert res.summary["rater_r_median"] == pytest.approx(1.0)
