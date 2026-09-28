"""Point metrics for predicted vs true scores. All take 1-D arrays and ignore NaN pairs."""

from __future__ import annotations

import numpy as np
from scipy import stats


def _clean(y_true, y_pred) -> tuple[np.ndarray, np.ndarray]:
    y_true = np.asarray(y_true, dtype=float).ravel()
    y_pred = np.asarray(y_pred, dtype=float).ravel()
    if y_true.shape != y_pred.shape:
        raise ValueError(f"shape mismatch: {y_true.shape} vs {y_pred.shape}")
    ok = np.isfinite(y_true) & np.isfinite(y_pred)
    return y_true[ok], y_pred[ok]


def r2(y_true, y_pred) -> float:
    """Coefficient of determination, 1 - SSE/SST, SST around the mean of ``y_true``.

    Predicting the mean of the evaluated targets gives 0; worse predictions go negative.
    """
    t, p = _clean(y_true, y_pred)
    sst = np.sum((t - t.mean()) ** 2)
    if len(t) < 2 or sst == 0:
        return float("nan")
    return float(1.0 - np.sum((t - p) ** 2) / sst)


def pearson(y_true, y_pred) -> float:
    t, p = _clean(y_true, y_pred)
    if len(t) < 2 or np.std(t) == 0 or np.std(p) == 0:
        return float("nan")
    return float(np.corrcoef(t, p)[0, 1])


def spearman(y_true, y_pred) -> float:
    t, p = _clean(y_true, y_pred)
    if len(t) < 2 or np.std(t) == 0 or np.std(p) == 0:
        return float("nan")
    return float(stats.spearmanr(t, p).statistic)


def kendall(y_true, y_pred) -> float:
    """Kendall tau-b (handles ties)."""
    t, p = _clean(y_true, y_pred)
    if len(t) < 2 or np.std(t) == 0 or np.std(p) == 0:
        return float("nan")
    return float(stats.kendalltau(t, p).statistic)


def pairwise_accuracy(y_true, y_pred, groups=None) -> float:
    """Fraction of pairs ordered the same way by prediction and truth.

    Pairs tied in ``y_true`` are skipped. Pairs tied in ``y_pred`` (but not in truth) count 0.5.
    With ``groups``, only pairs within the same group are compared (e.g. performances of the
    same piece).
    """
    y_true = np.asarray(y_true, dtype=float).ravel()
    y_pred = np.asarray(y_pred, dtype=float).ravel()
    if y_true.shape != y_pred.shape:
        raise ValueError(f"shape mismatch: {y_true.shape} vs {y_pred.shape}")
    ok = np.isfinite(y_true) & np.isfinite(y_pred)
    if groups is None:
        g = np.zeros(len(y_true), dtype=int)
    else:
        g = np.asarray(groups)
        if g.shape != y_true.shape:
            raise ValueError("groups must match y_true")
    y_true, y_pred, g = y_true[ok], y_pred[ok], g[ok]
    score = 0.0
    n = 0
    for gv in np.unique(g):
        m = g == gv
        t, p = y_true[m], y_pred[m]
        dt = np.sign(t[:, None] - t[None, :])
        dp = np.sign(p[:, None] - p[None, :])
        iu = np.triu_indices(len(t), k=1)
        dt, dp = dt[iu], dp[iu]
        keep = dt != 0
        dt, dp = dt[keep], dp[keep]
        score += np.sum(dt == dp) + 0.5 * np.sum(dp == 0)
        n += len(dt)
    return float(score / n) if n else float("nan")


METRICS = {
    "r2": r2,
    "pearson": pearson,
    "spearman": spearman,
    "kendall": kendall,
    "pairwise_accuracy": pairwise_accuracy,
}
