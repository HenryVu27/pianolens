"""Bradley-Terry scale from pairwise comparisons.

P(i beats j) = sigmoid(s_i - s_j). Scores are log-strengths, centred to mean zero. A small L2
penalty keeps the fit finite when an item wins (or loses) every comparison, and pins the scale
when the comparison graph is disconnected.
"""

from __future__ import annotations

from collections.abc import Hashable, Iterable, Sequence
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import expit, log_expit


@dataclass
class BradleyTerry:
    items: list
    scores: np.ndarray  # log-strength per item, mean zero
    n_comparisons: int
    converged: bool

    def __post_init__(self) -> None:
        self._index = {it: i for i, it in enumerate(self.items)}

    def as_series(self) -> pd.Series:
        return pd.Series(self.scores, index=self.items, name="bt_score").sort_values(
            ascending=False)

    def score(self, item: Hashable) -> float:
        return float(self.scores[self._index[item]])

    def prob(self, a: Hashable, b: Hashable) -> float:
        """P(a beats b). Unseen items get score 0 (the mean)."""
        sa = self.scores[self._index[a]] if a in self._index else 0.0
        sb = self.scores[self._index[b]] if b in self._index else 0.0
        return float(expit(sa - sb))

    def accuracy(self, comparisons: Iterable[tuple[Hashable, Hashable]]) -> float:
        """Held-out pairwise accuracy: fraction of (winner, loser) pairs the scale orders
        correctly. Equal scores (including two unseen items) count 0.5."""
        hits = []
        for w, loser in comparisons:
            p = self.prob(w, loser)
            hits.append(1.0 if p > 0.5 else 0.5 if p == 0.5 else 0.0)
        return float(np.mean(hits)) if hits else float("nan")


def fit_bradley_terry(comparisons: Sequence[tuple[Hashable, Hashable]], items=None, *,
                      l2: float = 1e-4, weights=None, tol: float = 1e-10) -> BradleyTerry:
    """Fit by penalized maximum likelihood (L-BFGS).

    comparisons: sequence of (winner, loser).
    items: optional full item list (items with no comparisons get score ~0).
    l2: ridge penalty on the scores; 0 gives the plain MLE (needs a connected graph and no
        item that always wins or always loses).
    weights: optional per-comparison weights (e.g. counts).
    """
    comps = list(comparisons)
    if not comps:
        raise ValueError("no comparisons")
    if items is None:
        seen: dict = {}
        for w, loser in comps:
            seen.setdefault(w, None)
            seen.setdefault(loser, None)
        items = list(seen)
    else:
        items = list(items)
    idx = {it: i for i, it in enumerate(items)}
    wi = np.array([idx[w] for w, _ in comps])
    li = np.array([idx[loser] for _, loser in comps])
    if np.any(wi == li):
        raise ValueError("an item cannot be compared with itself")
    wts = np.ones(len(comps)) if weights is None else np.asarray(weights, dtype=float)
    n = len(items)

    def fun(s):
        d = s[wi] - s[li]
        nll = -np.sum(wts * log_expit(d)) + 0.5 * l2 * np.dot(s, s)
        g_d = -wts * expit(-d)
        grad = np.bincount(wi, g_d, minlength=n) - np.bincount(li, g_d, minlength=n) + l2 * s
        return nll, grad

    res = minimize(fun, np.zeros(n), jac=True, method="L-BFGS-B",
                   options={"maxiter": 10000, "ftol": tol, "gtol": 1e-9})
    s = res.x - res.x.mean()
    return BradleyTerry(items=items, scores=s, n_comparisons=len(comps),
                        converged=bool(res.success))
