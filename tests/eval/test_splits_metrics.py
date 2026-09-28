import numpy as np
import pytest

from pianolens.eval import (
    check_disjoint,
    group_fold_ids,
    group_kfold,
    kendall,
    pairwise_accuracy,
    pearson,
    r2,
    spearman,
)


def _groups():
    # 10 pieces of very different sizes
    sizes = [50, 40, 30, 20, 10, 10, 5, 5, 3, 2]
    return np.repeat([f"p{i}" for i in range(len(sizes))], sizes)


def test_group_kfold_no_leakage_and_full_coverage():
    g = _groups()
    splits = group_kfold(g, 4, seed=1)
    assert len(splits) == 4
    check_disjoint(g, splits)
    test_rows = np.concatenate([te for _, te in splits])
    assert sorted(test_rows.tolist()) == list(range(len(g)))
    for tr, te in splits:
        assert len(tr) + len(te) == len(g)


def test_group_kfold_balanced_and_deterministic():
    g = _groups()
    f1 = group_fold_ids(g, 4, seed=3)
    f2 = group_fold_ids(g, 4, seed=3)
    assert np.array_equal(f1, f2)
    sizes = np.bincount(f1)
    # 175 rows, largest group 50: greedy gives every fold between 40 and 50 rows
    assert sizes.max() - sizes.min() <= 10
    # every group constant within fold
    for p in np.unique(g):
        assert len(np.unique(f1[g == p])) == 1


def test_leave_one_group_out_and_errors():
    g = np.array(["a", "a", "b", "c", "c", "c"])
    splits = group_kfold(g)
    assert len(splits) == 3
    assert {tuple(sorted(set(g[te]))) for _, te in splits} == {("a",), ("b",), ("c",)}
    with pytest.raises(ValueError):
        group_kfold(g, 4)
    with pytest.raises(AssertionError):
        check_disjoint(g, [(np.array([0, 2]), np.array([1]))])


def test_r2_known_values():
    y = np.array([1.0, 2.0, 3.0, 4.0])
    assert r2(y, y) == pytest.approx(1.0)
    assert r2(y, np.full(4, y.mean())) == pytest.approx(0.0)
    # SSE = 4 * 1 = 4, SST = 5  -> 1 - 4/5 = 0.2
    assert r2(y, y + 1) == pytest.approx(0.2)


def test_correlations_known_values():
    y = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    assert spearman(y, np.exp(y)) == pytest.approx(1.0)
    assert pearson(y, -2 * y) == pytest.approx(-1.0)
    # one discordant pair out of 10: tau = (9 - 1) / 10
    assert kendall(y, [1, 2, 3, 5, 4]) == pytest.approx(0.8)
    assert np.isnan(pearson(y, np.ones(5)))
    # NaN pairs are dropped
    assert spearman([1, 2, np.nan, 4], [1, 2, 3, 4]) == pytest.approx(1.0)


def test_pairwise_accuracy_hand_example():
    y = np.array([1.0, 2.0, 3.0, 3.0])
    p = np.array([1.0, 3.0, 2.0, 5.0])
    # pairs (true ties skipped: (2,3)): (0,1)ok (0,2)ok (0,3)ok (1,2)wrong (1,3)ok -> 4/5
    assert pairwise_accuracy(y, p) == pytest.approx(0.8)
    # tie in prediction counts half: pairs (0,1) tie ->0.5, (0,2) ok, (1,2) ok -> 2.5/3
    assert pairwise_accuracy([1, 2, 3], [1, 1, 2]) == pytest.approx(2.5 / 3)
    # within-group only: cross-group pairs ignored
    y = np.array([1, 2, 10, 20])
    p = np.array([2, 1, 30, 40])
    g = np.array([0, 0, 1, 1])
    assert pairwise_accuracy(y, p, groups=g) == pytest.approx(0.5)
