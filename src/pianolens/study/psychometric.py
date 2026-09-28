"""Fits for the S-03 perceptual cost study, with listener-clustered (sandwich) standard errors.

* :func:`fit_detection`: psychometric function for the detection task (reference-then-two
  choice, chance 0.5): ``P(correct | x) = g + (1 - g - lapse) * sigmoid(s * (log2 x - a))``.
  ``a`` is the log2 threshold (the level where the sigmoid is 0.5, i.e. about 74% correct with
  a 2% lapse), ``s = exp(b)`` the slope per log2 unit. Guess ``g`` and ``lapse`` are fixed
  (the protocol estimates the lapse from the easy catch trials).
* :func:`fit_logit`: binomial logistic regression (Newton / IRLS) with cluster-robust
  covariance, used for the preference model ``logit P(choose original) = gamma * s + sum_d
  beta_d * x_d`` (``s`` = +1/2 when the original is second, -1/2 when first; ``x_d`` = level of
  dimension ``d`` in threshold units, 0 for other dimensions; no intercept, since identical
  pairs carry no preference).

Both use the CR1 sandwich (``G / (G - 1)`` small-sample factor, ``G`` clusters = listeners),
because trials of one listener are not independent.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.optimize import minimize
from scipy.special import expit

__all__ = ["DetectionFit", "LogitFit", "fit_detection", "fit_logit"]


@dataclass
class DetectionFit:
    log2_threshold: float
    log_slope: float
    cov: np.ndarray  # 2x2 cluster-robust covariance of (log2_threshold, log_slope)
    n_clusters: int
    converged: bool
    guess: float
    lapse: float

    @property
    def threshold(self) -> float:
        return float(2.0**self.log2_threshold)

    @property
    def se_log2_threshold(self) -> float:
        v = float(self.cov[0, 0])
        return float(np.sqrt(v)) if v >= 0 else float("nan")

    def threshold_ci(self, z: float = 1.96) -> tuple[float, float]:
        h = z * self.se_log2_threshold
        return float(2 ** (self.log2_threshold - h)), float(2 ** (self.log2_threshold + h))

    def p_correct(self, x: np.ndarray) -> np.ndarray:
        z = np.exp(self.log_slope) * (np.log2(np.asarray(x, float)) - self.log2_threshold)
        return self.guess + (1 - self.guess - self.lapse) * expit(z)


def _det_parts(theta: np.ndarray, lx: np.ndarray, guess: float, lapse: float):
    a, b = theta
    s = np.exp(b)
    z = s * (lx - a)
    sig = expit(z)
    p = np.clip(guess + (1 - guess - lapse) * sig, 1e-9, 1 - 1e-9)
    dsig = (1 - guess - lapse) * sig * (1 - sig)
    dp = np.stack([-s * dsig, z * dsig], axis=1)  # d p / d (a, b)
    return p, dp


def _cr1(scores: np.ndarray, cluster: np.ndarray, bread: np.ndarray) -> tuple[np.ndarray, int]:
    uc, inv = np.unique(cluster, return_inverse=True)
    g = len(uc)
    meat = np.zeros((scores.shape[1], scores.shape[1]))
    sums = np.zeros((g, scores.shape[1]))
    np.add.at(sums, inv, scores)
    meat = sums.T @ sums
    fac = g / (g - 1) if g > 1 else 1.0
    return fac * bread @ meat @ bread, g


def fit_detection(x: np.ndarray, k: np.ndarray, n: np.ndarray, cluster: np.ndarray, *,
                  guess: float = 0.5, lapse: float = 0.02) -> DetectionFit:
    """Fit the detection psychometric function.

    Args:
        x: level (> 0) per row, in any positive unit (the threshold comes out in that unit).
        k, n: correct responses and trials per row (rows may be single trials).
        cluster: listener id per row.
    """
    x, k, n = (np.asarray(v, float) for v in (x, k, n))
    lx = np.log2(x)
    cluster = np.asarray(cluster)

    def nll(theta):
        p, dp = _det_parts(theta, lx, guess, lapse)
        ll = k * np.log(p) + (n - k) * np.log1p(-p)
        dl = k / p - (n - k) / (1 - p)
        return -ll.sum(), -(dl[:, None] * dp).sum(axis=0)

    a0 = float(np.median(lx))
    res = minimize(nll, np.array([a0, np.log(2.0)]), jac=True, method="L-BFGS-B",
                   bounds=[(lx.min() - 6, lx.max() + 6), (np.log(0.05), np.log(50))])
    theta = res.x
    # observed information by finite differences of the analytic gradient
    h = 1e-5
    H = np.zeros((2, 2))
    for j in range(2):
        e = np.zeros(2)
        e[j] = h
        H[:, j] = (nll(theta + e)[1] - nll(theta - e)[1]) / (2 * h)
    H = 0.5 * (H + H.T)
    p, dp = _det_parts(theta, lx, guess, lapse)
    dl = k / p - (n - k) / (1 - p)
    scores = dl[:, None] * dp
    try:
        bread = np.linalg.inv(H)
        cov, g = _cr1(scores, cluster, bread)
    except np.linalg.LinAlgError:
        cov, g = np.full((2, 2), np.nan), len(np.unique(cluster))
    return DetectionFit(float(theta[0]), float(theta[1]), cov, g, bool(res.success), guess,
                        lapse)  # fmt: skip


@dataclass
class LogitFit:
    coef: np.ndarray
    cov: np.ndarray  # cluster-robust (CR1)
    n_clusters: int
    converged: bool
    names: list[str]

    def se(self) -> np.ndarray:
        return np.sqrt(np.diag(self.cov))


def fit_logit(X: np.ndarray, k: np.ndarray, n: np.ndarray, cluster: np.ndarray,
              names: list[str] | None = None, ridge: float = 1e-6, max_iter: int = 50
              ) -> LogitFit:
    """Binomial logistic regression without an implicit intercept (add a column if needed).

    ``k`` successes out of ``n`` per row; ``cluster`` for the sandwich covariance. A tiny ridge
    keeps separated fits finite.
    """
    X = np.asarray(X, float)
    k, n = np.asarray(k, float), np.asarray(n, float)
    beta = np.zeros(X.shape[1])
    converged = False
    for _ in range(max_iter):
        p = expit(X @ beta)
        w = n * p * (1 - p)
        grad = X.T @ (k - n * p) - ridge * beta
        H = (X * w[:, None]).T @ X + ridge * np.eye(X.shape[1])
        step = np.linalg.solve(H, grad)
        beta = beta + step
        if np.max(np.abs(step)) < 1e-8:
            converged = True
            break
    p = expit(X @ beta)
    w = n * p * (1 - p)
    H = (X * w[:, None]).T @ X + ridge * np.eye(X.shape[1])
    scores = X * (k - n * p)[:, None]
    bread = np.linalg.inv(H)
    cov, g = _cr1(scores, np.asarray(cluster), bread)
    return LogitFit(beta, cov, g, converged,
                    names or [f"x{j}" for j in range(X.shape[1])])  # fmt: skip
