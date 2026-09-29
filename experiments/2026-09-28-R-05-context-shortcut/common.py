"""R-05 shared helpers: labels, CV groups, fast AUC."""

from __future__ import annotations

import numpy as np
import pandas as pd

BEGINNER = ("child_beginner", "adult_beginner")
ADVANCED = ("child_professional", "piano_teacher", "virtuoso")
LEVEL_GROUP3 = {"child_beginner": 0, "adult_beginner": 0, "adult_intermediate": 1,
                "child_professional": 2, "piano_teacher": 2, "virtuoso": 2}  # fmt: skip


def cv_groups(sample: pd.DataFrame) -> np.ndarray:
    """Connected components of the (piece_id, recording_id) graph, so neither a piece nor a
    source video straddles train and test."""
    parent: dict[str, str] = {}

    def find(x: str) -> str:
        while parent.setdefault(x, x) != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for p, r in zip(sample.piece_id, sample.recording_id, strict=True):
        a, b = find("p:" + str(p)), find("r:" + str(r))
        if a != b:
            parent[a] = b
    comp = [find("p:" + str(p)) for p in sample.piece_id]
    _, inv = np.unique(comp, return_inverse=True)
    return inv


def auc(y: np.ndarray, s: np.ndarray) -> float:
    """ROC AUC via mid-ranks (ties count half)."""
    from scipy.stats import rankdata

    y = np.asarray(y).astype(bool)
    n1 = int(y.sum())
    n0 = len(y) - n1
    if n1 == 0 or n0 == 0:
        return float("nan")
    r = rankdata(s)
    return float((r[y].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))
