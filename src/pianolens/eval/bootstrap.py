"""Cluster bootstrap: resample whole groups (pieces, performers, raters), never single rows.

Rows of the same piece are correlated, so a row bootstrap gives CIs that are far too narrow.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class BootstrapResult:
    estimate: float  # metric on the full data
    low: float
    high: float
    samples: np.ndarray  # finite bootstrap replicates
    n_failed: int  # replicates where the metric was NaN (dropped)

    def __str__(self) -> str:
        return f"{self.estimate:.3f} [{self.low:.3f}, {self.high:.3f}]"


def _group_index(groups, n: int) -> list[np.ndarray]:
    if groups is None:
        return [np.array([i]) for i in range(n)]
    groups = np.asarray(groups)
    if len(groups) != n:
        raise ValueError("groups must have one label per row")
    _, inv = np.unique(groups, return_inverse=True)
    order = np.argsort(inv, kind="stable")
    bounds = np.flatnonzero(np.diff(inv[order])) + 1
    return np.split(order, bounds)


def bootstrap_indices(groups, n: int, n_boot: int, seed: int = 0):
    """Yield row-index arrays, one per replicate, built by resampling groups with replacement."""
    members = _group_index(groups, n)
    rng = np.random.default_rng(seed)
    k = len(members)
    for _ in range(n_boot):
        pick = rng.integers(0, k, size=k)
        yield np.concatenate([members[i] for i in pick])


def bootstrap_ci(metric: Callable[..., float], *arrays, groups=None, n_boot: int = 2000,
                 alpha: float = 0.05, seed: int = 0, pass_groups: bool = False
                 ) -> BootstrapResult:
    """Percentile CI of ``metric(*arrays)`` under a group (cluster) bootstrap.

    ``arrays`` are row-aligned (1-D or 2-D, first axis = rows). ``groups=None`` falls back to a
    row bootstrap. With ``pass_groups=True`` the resampled group labels are passed to the metric
    as ``groups=`` (for within-group metrics such as ``pairwise_accuracy``). Resampled copies of
    a group get distinct labels so that they are not merged.
    """
    arrays = [np.asarray(a) for a in arrays]
    n = len(arrays[0])
    if any(len(a) != n for a in arrays):
        raise ValueError("arrays must share their first dimension")
    g_arr = None if groups is None else np.asarray(groups)

    def call(idx, labels):
        if pass_groups:
            return metric(*[a[idx] for a in arrays], groups=labels)
        return metric(*[a[idx] for a in arrays])

    estimate = float(call(np.arange(n), g_arr))
    members = _group_index(g_arr, n)
    rng = np.random.default_rng(seed)
    k = len(members)
    reps = np.empty(n_boot)
    for b in range(n_boot):
        pick = rng.integers(0, k, size=k)
        idx = np.concatenate([members[i] for i in pick])
        labels = np.repeat(np.arange(k), [len(members[i]) for i in pick]) if pass_groups else None
        reps[b] = call(idx, labels)
    ok = np.isfinite(reps)
    reps_ok = reps[ok]
    if len(reps_ok) == 0:
        return BootstrapResult(estimate, float("nan"), float("nan"), reps_ok, int((~ok).sum()))
    low, high = np.quantile(reps_ok, [alpha / 2, 1 - alpha / 2])
    return BootstrapResult(estimate, float(low), float(high), reps_ok, int((~ok).sum()))


def paired_bootstrap_diff(metric: Callable[[np.ndarray, np.ndarray], float], y_true,
                          pred_a, pred_b, groups=None, n_boot: int = 2000, alpha: float = 0.05,
                          seed: int = 0) -> BootstrapResult:
    """CI of ``metric(y, pred_a) - metric(y, pred_b)`` with the same resample for both."""
    y_true, pred_a, pred_b = (np.asarray(x, dtype=float) for x in (y_true, pred_a, pred_b))

    def diff(y, a, b):
        return metric(y, a) - metric(y, b)

    return bootstrap_ci(diff, y_true, pred_a, pred_b, groups=groups, n_boot=n_boot,
                        alpha=alpha, seed=seed)
