"""Known-answer tests for pianolens.study.power_s04 (S-04 design simulation)."""

from __future__ import annotations

import numpy as np
import pytest

from pianolens.eval.bradley_terry import fit_bradley_terry
from pianolens.study.power_s04 import (
    S04Assumptions,
    _truth,
    bt_standard_errors,
    h7_verdict,
    schedule_pairs,
    session_minutes_s04,
    simulate_once,
)


def test_schedule_is_balanced_within_passage_and_by_position():
    rng = np.random.default_rng(0)
    df = schedule_pairs(3, 5, 20, 30, rng)
    assert len(df) == 600 and (df["i"] != df["j"]).all()
    key = np.minimum(df["i"], df["j"]) * 10 + np.maximum(df["i"], df["j"]) + 100 * df["passage"]
    counts = key.value_counts()
    assert len(counts) == 3 * 10 and counts.max() - counts.min() <= 1
    # each pair is presented in both orders about equally often
    for _, g in df.groupby(key):
        assert abs((g["i"] < g["j"]).sum() - (g["i"] > g["j"]).sum()) <= 1


def test_bt_standard_errors_shrink_with_more_comparisons():
    rng = np.random.default_rng(1)
    true = np.array([-1.0, 0.0, 1.0, 0.5])
    se = []
    for reps in (50, 800):
        i = rng.integers(0, 4, reps * 6)
        j = (i + rng.integers(1, 4, len(i))) % 4
        win = rng.random(len(i)) < 1 / (1 + np.exp(-(true[i] - true[j])))
        w, lo = np.where(win, i, j), np.where(win, j, i)
        bt = fit_bradley_terry(list(zip(w, lo, strict=True)), items=[0, 1, 2, 3], l2=0.1)
        se.append(bt_standard_errors(bt.scores, w, lo, l2=0.1).mean())
    assert se[1] < se[0] / 3  # about sqrt(16) = 4 times smaller


def test_truth_model_variance_partition():
    a = S04Assumptions(n_passages=400, n_perf=50, r2_d2m=0.2, r2_feat=0.3)
    q, d2m, F = _truth(a, np.random.default_rng(2))
    y, x0 = q.ravel(), d2m.ravel()
    X1 = np.column_stack([x0, F.reshape(-1, F.shape[-1])])
    r2 = [1 - np.var(y - X @ np.linalg.lstsq(X, y, rcond=None)[0]) / np.var(y)
          for X in (x0[:, None], X1)]
    assert np.var(y) == pytest.approx(1.0, abs=0.05)
    assert r2[0] == pytest.approx(0.2, abs=0.03)
    assert r2[1] == pytest.approx(0.5, abs=0.03)


def test_h7_verdict_reading():
    assert h7_verdict(0.2, 0.05, 0.35, 0.1) == "supported"
    assert h7_verdict(0.0, -0.1, 0.08, 0.1) == "falsified"
    assert h7_verdict(0.08, 0.01, 0.2, 0.1) == "inconclusive"
    assert h7_verdict(0.12, -0.02, 0.3, 0.1) == "inconclusive"


def test_simulation_runs_and_reports_design_quantities():
    a = S04Assumptions(n_passages=6, n_perf=6, trials_per_listener=30, n_boot=50)
    r = simulate_once(a, 12, np.random.default_rng(3))
    assert r["verdict"] in ("supported", "falsified", "inconclusive")
    assert r["comparisons_per_item"] == pytest.approx(2 * 12 * 30 / 36)
    assert r["gain_lo"] <= r["gain_rel"] <= r["gain_hi"] or np.isnan(r["gain_rel"])
    assert 0.0 <= r["acc_true"] <= 1.0
    assert session_minutes_s04(S04Assumptions()) == pytest.approx(50 * 43.6 / 60)
