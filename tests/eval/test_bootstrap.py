import numpy as np
import pytest

from pianolens.eval import bootstrap_ci, paired_bootstrap_diff, pairwise_accuracy, r2


def test_group_bootstrap_is_wider_than_row_bootstrap_for_clustered_data():
    # 8 groups, 200 identical rows each: the information is 8 values, not 1600.
    rng = np.random.default_rng(0)
    group_means = rng.normal(size=8)
    g = np.repeat(np.arange(8), 200)
    x = group_means[g]
    by_group = bootstrap_ci(np.mean, x, groups=g, n_boot=1000, seed=1)
    by_row = bootstrap_ci(np.mean, x, n_boot=1000, seed=1)
    assert by_group.estimate == pytest.approx(x.mean())
    assert by_group.low <= x.mean() <= by_group.high
    # group CI roughly matches the SE of a mean of 8 values; row CI is ~sqrt(200) narrower
    se8 = group_means.std() / np.sqrt(8)
    assert (by_group.high - by_group.low) == pytest.approx(2 * 1.96 * se8, rel=0.35)
    assert (by_group.high - by_group.low) > 5 * (by_row.high - by_row.low)


def test_group_bootstrap_resamples_whole_groups():
    # each group has a single distinct value; every replicate mean must be a mean of
    # group values with integer multiplicities summing to k (never a partial group)
    g = np.repeat([0, 1], [3, 1])
    x = np.array([0.0, 0.0, 0.0, 1.0])
    res = bootstrap_ci(np.mean, x, groups=g, n_boot=200, seed=0)
    # possible replicates: {0,0}->0, {1,1}->1, {0,1}->0.25
    assert set(np.round(res.samples, 6)) <= {0.0, 1.0, 0.25}


def test_percentile_ci_coverage_on_iid_normal():
    # nominal 95%; allow slack for 200 simulations
    rng = np.random.default_rng(42)
    hits = 0
    n_sim = 200
    for s in range(n_sim):
        x = rng.normal(size=60)
        res = bootstrap_ci(np.mean, x, n_boot=400, seed=s)
        hits += res.low <= 0.0 <= res.high
    assert 0.88 <= hits / n_sim <= 0.99


def test_nan_replicates_are_counted_and_dropped():
    g = np.array([0, 0, 1, 1])
    y = np.array([1.0, 2.0, 3.0, 4.0])
    res = bootstrap_ci(r2, y, y, groups=g, n_boot=300, seed=0)
    assert res.estimate == pytest.approx(1.0)
    assert res.n_failed + len(res.samples) == 300


def test_pass_groups_for_within_group_metric():
    y = np.array([1, 2, 10, 20, 5, 6], dtype=float)
    p = np.array([1, 2, 30, 40, 6, 5], dtype=float)
    g = np.array([0, 0, 1, 1, 2, 2])
    res = bootstrap_ci(pairwise_accuracy, y, p, groups=g, n_boot=300, seed=0,
                       pass_groups=True)
    assert res.estimate == pytest.approx(2 / 3)
    # within-group accuracy per group is 1 or 0, so every replicate is a multiple of 1/3
    assert np.allclose(np.round(res.samples * 3), res.samples * 3)


def test_paired_diff_detects_better_model():
    rng = np.random.default_rng(0)
    g = np.repeat(np.arange(30), 10)
    y = rng.normal(size=300)
    good = y + rng.normal(scale=0.3, size=300)
    bad = y + rng.normal(scale=1.5, size=300)
    res = paired_bootstrap_diff(r2, y, good, bad, groups=g, n_boot=500)
    assert res.low > 0
