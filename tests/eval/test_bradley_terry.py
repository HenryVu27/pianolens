import numpy as np
import pytest
from scipy.special import expit

from pianolens.eval import fit_bradley_terry


def test_two_items_closed_form():
    # A beats B 3 times, B beats A once: MLE s_A - s_B = log(3)
    comps = [("A", "B")] * 3 + [("B", "A")]
    bt = fit_bradley_terry(comps, l2=0.0)
    assert bt.converged
    assert bt.score("A") - bt.score("B") == pytest.approx(np.log(3), abs=1e-5)
    assert bt.score("A") + bt.score("B") == pytest.approx(0.0, abs=1e-9)
    assert bt.prob("A", "B") == pytest.approx(0.75, abs=1e-5)


def _simulate(n_comp, seed=0):
    rng = np.random.default_rng(seed)
    true = np.linspace(-2, 2, 12)
    comps = []
    for _ in range(n_comp):
        i, j = rng.choice(12, size=2, replace=False)
        comps.append((i, j) if rng.random() < expit(true[i] - true[j]) else (j, i))
    return true, comps


def test_matches_mm_algorithm_exactly():
    # Hunter (2004) MM iterations converge to the same MLE
    _, comps = _simulate(3000)
    bt = fit_bradley_terry(comps, items=range(12), l2=0.0)
    wins = np.zeros(12)
    n = np.zeros((12, 12))
    for w, loser in comps:
        wins[w] += 1
        n[w, loser] += 1
        n[loser, w] += 1
    p = np.ones(12)
    for _ in range(5000):
        p = wins / (n / (p[:, None] + p[None, :])).sum(axis=1)
        p /= np.exp(np.log(p).mean())
    np.testing.assert_allclose(bt.scores, np.log(p), atol=1e-4)


def test_recovers_simulated_strengths():
    true, comps = _simulate(30000)
    bt = fit_bradley_terry(comps, items=range(12), l2=0.0)
    np.testing.assert_allclose(bt.scores, true, atol=0.15)
    assert np.corrcoef(bt.scores, true)[0, 1] > 0.99


def test_perfect_separation_stays_finite_and_ordered():
    comps = [("a", "b"), ("b", "c"), ("a", "c")]
    bt = fit_bradley_terry(comps, l2=1e-2)
    assert np.all(np.isfinite(bt.scores))
    assert list(bt.as_series().index) == ["a", "b", "c"]
    assert bt.accuracy(comps) == 1.0


def test_accuracy_and_unseen_items():
    bt = fit_bradley_terry([("a", "b")] * 2 + [("b", "a")])
    assert bt.accuracy([("a", "b"), ("b", "a")]) == 0.5
    assert bt.prob("zzz", "yyy") == 0.5
    assert bt.accuracy([("zzz", "yyy")]) == 0.5
    with pytest.raises(ValueError):
        fit_bradley_terry([("a", "a")])


def test_weights_equal_repeated_comparisons():
    rep = fit_bradley_terry([("a", "b")] * 3 + [("b", "a")], l2=0.0)
    w = fit_bradley_terry([("a", "b"), ("b", "a")], weights=[3, 1], l2=0.0)
    np.testing.assert_allclose(rep.scores, w.scores, atol=1e-6)
