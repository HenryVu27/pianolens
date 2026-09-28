"""Dimensionality of a set of curves: PCA counts, held-out reconstruction, surrogate nulls.

Rows are observations (performances), columns are positions on a shared grid (score beats).
Used by R-02 (H1). Everything is plain numpy so it does not depend on the data types.

* :func:`explained_variance_ratio`: PCA of the column-centered matrix (SVD).
* :func:`n_components_for`: smallest k whose cumulative explained variance reaches a threshold.
* :func:`heldout_r2_curve`: fit the mean and the components on a random subset of rows, measure
  the reconstruction R² of the held-out rows with k components. This is the honest count: an
  in-sample PCA always "explains" 100% with n - 1 components, however noisy the rows are.
* Surrogates (nulls): :func:`phase_randomize` keeps each row's power spectrum (so its variance
  and smoothness) but draws new Fourier phases, which removes any structure shared across rows;
  :func:`column_shuffle` permutes each column across rows independently.
* :func:`whittaker_smooth`: discrete smoother with an order-``d`` difference penalty. With
  ``lam = (period / (2 pi))**(2 d)`` its gain is about ``1 / (1 + (period * f)**(2 d))`` at
  frequency ``f`` (cycles per sample): one half at the given period, the same convention as the
  F-03 tempo P-spline.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
from scipy import sparse
from scipy.linalg import solveh_banded

__all__ = [
    "column_shuffle",
    "explained_variance_ratio",
    "heldout_r2_curve",
    "loo_r2_curve",
    "mean_curve_share",
    "n_components_for",
    "phase_randomize",
    "whittaker_smooth",
]


def explained_variance_ratio(x: np.ndarray) -> np.ndarray:
    """Explained-variance ratio of each principal component of ``x`` (rows centered by column).

    Returns ``min(n, p)`` ratios in decreasing order (the last is ~0 after centering when
    ``n <= p``); all zeros if ``x`` has no variance."""
    x = np.asarray(x, dtype=float)
    xc = x - x.mean(axis=0, keepdims=True)
    s = np.linalg.svd(xc, compute_uv=False)
    ev = s**2
    tot = ev.sum()
    return ev / tot if tot > 0 else np.zeros_like(ev)


def n_components_for(ratios: np.ndarray, threshold: float = 0.8) -> int:
    """Smallest k such that the first k ratios sum to at least ``threshold``."""
    c = np.cumsum(np.asarray(ratios, dtype=float))
    if len(c) == 0 or c[-1] <= 0:
        return 0
    return int(np.searchsorted(c, threshold - 1e-12) + 1)


def mean_curve_share(x: np.ndarray) -> float:
    """Share of the rows' total sum of squares carried by the column means (the shared curve).

    ``1 - SS(x - column mean) / SS(x)``. Rows are assumed to be centered already (each row's own
    mean removed), so this is the part of each row's shape that all rows have in common."""
    x = np.asarray(x, dtype=float)
    tot = float((x**2).sum())
    if tot <= 0:
        return float("nan")
    return 1.0 - float(((x - x.mean(axis=0)) ** 2).sum()) / tot


def _recon_sse(xtr: np.ndarray, xte: np.ndarray, ks: Sequence[int]) -> tuple[np.ndarray, float]:
    mu = xtr.mean(axis=0)
    _, _, vt = np.linalg.svd(xtr - mu, full_matrices=False)
    d = xte - mu
    ss = float((d**2).sum())
    sse = np.empty(len(ks))
    scores = d @ vt.T  # (n_te, r)
    total = (d**2).sum()
    for j, k in enumerate(ks):
        kk = min(k, vt.shape[0])
        # residual SS = |d|^2 - |projection|^2 (vt rows are orthonormal)
        sse[j] = total - float((scores[:, :kk] ** 2).sum())
    return sse, ss


def heldout_r2_curve(
    x: np.ndarray,
    ks: Sequence[int],
    n_splits: int = 5,
    test_frac: float = 0.2,
    seed: int = 0,
) -> np.ndarray:
    """Held-out reconstruction R² for each k in ``ks``, averaged over random row splits.

    Each split fits the column mean and the principal axes on ``1 - test_frac`` of the rows, and
    reconstructs the held-out rows as mean + projection on the first k axes (k capped at the
    number of axes). R² = 1 - SSE / SS about the training mean, pooled over held-out rows, then
    averaged over splits (seeds ``seed .. seed + n_splits - 1``)."""
    x = np.asarray(x, dtype=float)
    n = len(x)
    n_te = max(1, int(round(test_frac * n)))
    if n - n_te < 2:
        raise ValueError("too few rows for a held-out split")
    out = np.zeros(len(ks))
    for s in range(n_splits):
        perm = np.random.default_rng(seed + s).permutation(n)
        te, tr = perm[:n_te], perm[n_te:]
        sse, ss = _recon_sse(x[tr], x[te], ks)
        out += 1.0 - sse / ss if ss > 0 else np.nan
    return out / n_splits


def loo_r2_curve(x: np.ndarray, ks: Sequence[int]) -> np.ndarray:
    """Leave-one-row-out reconstruction R² for each k (pooled SSE / pooled SS over rows)."""
    x = np.asarray(x, dtype=float)
    n = len(x)
    if n < 3:
        raise ValueError("need at least 3 rows")
    sse_t = np.zeros(len(ks))
    ss_t = 0.0
    for i in range(n):
        m = np.ones(n, bool)
        m[i] = False
        sse, ss = _recon_sse(x[m], x[i : i + 1], ks)
        sse_t += sse
        ss_t += ss
    return 1.0 - sse_t / ss_t


def phase_randomize(
    blocks: np.ndarray | Sequence[np.ndarray], rng: np.random.Generator
) -> list[np.ndarray]:
    """Fourier phase-randomized surrogates, row by row (Theiler et al. 1992, Physica D 58:77-94).

    Each row gets new uniform random phases (DC and, for even length, Nyquist terms kept), so its
    amplitude spectrum, variance and mean are unchanged while any alignment of features across
    rows is destroyed. Several blocks with the same number of columns receive the **same** random
    phases for the same row, which keeps their cross-spectrum within the row (e.g. the coupling
    of a performance's tempo and velocity curves). Returns a list of arrays like ``blocks``."""
    if isinstance(blocks, np.ndarray):
        blocks = [blocks]
    blocks = [np.asarray(b, dtype=float) for b in blocks]
    n, p = blocks[0].shape
    if any(b.shape != (n, p) for b in blocks):
        raise ValueError("blocks must share a shape")
    nf = p // 2 + 1
    ph = rng.uniform(0, 2 * np.pi, size=(n, nf))
    ph[:, 0] = 0.0
    if p % 2 == 0:
        ph[:, -1] = 0.0
    rot = np.exp(1j * ph)
    return [np.fft.irfft(np.fft.rfft(b, axis=1) * rot, n=p, axis=1) for b in blocks]


def column_shuffle(x: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Permute each column independently across rows (keeps every column's values)."""
    x = np.asarray(x, dtype=float)
    idx = np.argsort(rng.random(x.shape), axis=0)
    return np.take_along_axis(x, idx, axis=0)


def whittaker_smooth(y: np.ndarray, period: float, order: int = 3) -> np.ndarray:
    """Whittaker smoother along the last axis, half gain at ``period`` samples (Eilers 2003,
    Analytical Chemistry 75:3631-3636).

    Solves ``(I + lam D'D) z = y`` with ``D`` the order-``order`` difference matrix and
    ``lam = (period / (2 pi))**(2 order)``. Polynomials of degree < ``order`` pass unchanged."""
    y = np.asarray(y, dtype=float)
    p = y.shape[-1]
    if p <= order:
        return y.copy()
    lam = (period / (2 * np.pi)) ** (2 * order)
    coef = np.diff(np.eye(order + 1), n=order, axis=0)[0]  # e.g. [-1, 3, -3, 1]
    d = sparse.diags(
        [np.full(p - order, c) for c in coef], offsets=list(range(order + 1)),
        shape=(p - order, p),
    )
    a = (sparse.identity(p) + lam * (d.T @ d)).todia()
    # upper banded storage for solveh_banded
    ab = np.zeros((order + 1, p))
    for k in range(order + 1):
        ab[order - k, k:] = a.diagonal(k)
    flat = y.reshape(-1, p).T
    z = solveh_banded(ab, flat)
    return z.T.reshape(y.shape)
