"""Known-answer tests for pianolens.study.psychometric and pianolens.study.power."""

from __future__ import annotations

import numpy as np
import pytest
from scipy.special import expit

from pianolens.study.power import Assumptions, h6_verdict, session_minutes, simulate_once
from pianolens.study.psychometric import fit_detection, fit_logit


def test_fit_detection_recovers_threshold_and_slope():
    rng = np.random.default_rng(0)
    x = np.repeat([0.25, 0.5, 1, 2, 4, 8], 4000)
    p = 0.5 + (0.5 - 0.02) * expit(2.0 * (np.log2(x) - 1.0))  # threshold 2
    k = (rng.random(len(x)) < p).astype(float)
    cl = np.arange(len(x)) % 50
    f = fit_detection(x, k, np.ones(len(x)), cl)
    assert f.threshold == pytest.approx(2.0, rel=0.05)
    assert np.exp(f.log_slope) == pytest.approx(2.0, rel=0.1)
    lo, hi = f.threshold_ci()
    assert lo < 2.0 < hi
    assert f.p_correct(np.array([2.0]))[0] == pytest.approx(0.745, abs=0.01)


def test_fit_detection_cluster_se_grows_with_listener_heterogeneity():
    rng = np.random.default_rng(1)
    x = np.tile(np.repeat([0.5, 1, 2, 4], 20), 30)
    cl = np.repeat(np.arange(30), 80)
    se = []
    for tau in (0.0, 1.0):
        u = rng.normal(0, tau, 30)[cl]
        p = 0.5 + 0.49 * expit(2.0 * (np.log2(x) - u))
        k = (rng.random(len(x)) < p).astype(float)
        se.append(fit_detection(x, k, np.ones(len(x)), cl).se_log2_threshold)
    assert se[1] > 1.5 * se[0]


def test_fit_logit_recovers_coefficients():
    rng = np.random.default_rng(2)
    n = 20000
    s = np.where(rng.random(n) < 0.5, 0.5, -0.5)
    x = rng.choice([0.0, 1.0, 2.0, 4.0], n)
    X = np.column_stack([s, x])
    y = (rng.random(n) < expit(0.3 * s + 0.5 * x)).astype(float)
    f = fit_logit(X, y, np.ones(n), np.arange(n) % 100)
    assert f.converged
    assert f.coef == pytest.approx([0.3, 0.5], abs=0.08)
    assert np.all(f.se() > 0)


def test_h6_verdict_reading():
    cov = np.eye(3) * 1e-4
    assert h6_verdict(np.array([1.0, 1.0, 1.0]), cov)["verdict"] == "falsified"
    assert h6_verdict(np.array([3.0, 1.0, 1.0]), cov)["verdict"] == "supported"
    assert h6_verdict(np.array([1.0, 1.0, 1.0]), np.eye(3))["verdict"] == "inconclusive"


def test_session_minutes_and_simulation_run():
    a = Assumptions(det_reps=3, pref_reps=2)
    m = session_minutes(a)
    assert m["n_det_trials"] == 7 * 4 * 3 and m["n_pref_trials"] == 7 * 3 * 2 + 7
    r = simulate_once(a, 12, np.random.default_rng(0))
    assert r["verdict"] in ("supported", "falsified", "inconclusive")
    assert r["det_ci_halfwidth_log2_mean"] > 0
