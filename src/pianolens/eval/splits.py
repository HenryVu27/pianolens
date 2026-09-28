"""Grouped K-fold splits: every group (piece, performer) lands in exactly one test fold.

Use ``group_kfold(piece_ids, k)`` for leave-piece-out and ``group_kfold(performer_ids, k)`` for
leave-performer-out. ``n_splits=None`` gives leave-one-group-out.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

Split = tuple[np.ndarray, np.ndarray]


def group_fold_ids(groups: Sequence | np.ndarray, n_splits: int | None = None, *,
                   seed: int = 0) -> np.ndarray:
    """Return a fold id (0..n_splits-1) for every row, constant within each group.

    Groups are shuffled with ``seed`` and then assigned greedily, largest first, to the fold
    with the fewest rows so far. That balances fold sizes when group sizes differ a lot.
    ``n_splits=None`` means one fold per group (leave-one-group-out).
    """
    groups = np.asarray(groups)
    if groups.ndim != 1:
        raise ValueError("groups must be 1-D")
    uniq, inverse, counts = np.unique(groups, return_inverse=True, return_counts=True)
    n_groups = len(uniq)
    if n_splits is None:
        n_splits = n_groups
    if n_splits < 2:
        raise ValueError("n_splits must be at least 2")
    if n_splits > n_groups:
        raise ValueError(f"n_splits={n_splits} exceeds the number of groups ({n_groups})")

    rng = np.random.default_rng(seed)
    order = rng.permutation(n_groups)
    # stable sort by size (desc) after the random shuffle: ties broken by the shuffle
    order = order[np.argsort(-counts[order], kind="stable")]
    fold_of_group = np.empty(n_groups, dtype=int)
    load = np.zeros(n_splits, dtype=int)
    for g in order:
        f = int(np.argmin(load))
        fold_of_group[g] = f
        load[f] += counts[g]
    return fold_of_group[inverse]


def group_kfold(groups: Sequence | np.ndarray, n_splits: int | None = None, *,
                seed: int = 0) -> list[Split]:
    """Grouped K-fold. Returns ``[(train_idx, test_idx), ...]``; no group straddles a split."""
    fold = group_fold_ids(groups, n_splits, seed=seed)
    idx = np.arange(len(fold))
    return [(idx[fold != f], idx[fold == f]) for f in range(fold.max() + 1)]


def check_disjoint(groups: Sequence | np.ndarray, splits: Sequence[Split]) -> None:
    """Raise if any group appears in both train and test of a split (leakage check)."""
    groups = np.asarray(groups)
    for i, (tr, te) in enumerate(splits):
        shared = set(groups[tr]) & set(groups[te])
        if shared:
            raise AssertionError(f"split {i}: groups in both train and test: {sorted(shared)[:5]}")
