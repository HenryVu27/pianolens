"""Simulation-based power analysis for the S-03 perceptual cost study (H6).

The design (``study/protocol-S03.md``): every listener does

* **Part A, detection.** Reference then two choices (one identical to the reference, one
  degraded); which one differs? Chance 0.5. Constant stimuli: ``det_levels_rel`` multiples of the
  pilot threshold per dimension, ``det_reps`` trials per level, excerpts rotated.
* **Part B, preference.** Original vs degraded, "which do you prefer?", at ``pref_levels_rel``
  multiples of the pilot threshold, ``pref_reps`` trials per level, order counterbalanced, plus
  identical pairs.

The analysis (:mod:`pianolens.study.psychometric`): a detection psychometric fit per dimension
gives the threshold; preference is modelled as ``logit P(choose original) = gamma * s +
beta_d * x / theta_d`` (``s`` = +-1/2 for position; ``x / theta_d`` = level in threshold units).
H6 compares the ``beta_d``: cost per threshold unit.

**Pre-registered H6 reading** (see the protocol):

* *supported*: the Wald test that all ``beta_d`` are equal has p < 0.05, and at least one
  ordered pair has ``beta_i - m beta_j > 0`` at one-sided alpha 0.05 / 42 (Bonferroni over the
  42 ordered pairs of 7 dimensions), margin ``m`` = 2;
* *falsified* ("indistinguishable"): every ordered pair has ``beta_i - m beta_j < 0`` at
  one-sided alpha 0.05 (TOST: all ratios within 1/m..m);
* *inconclusive* otherwise.

The uncertainty of ``theta_d`` enters by the delta method: ``var(beta_d) += beta_d^2 *
var(ln theta_d)``.

Every number in :class:`Assumptions` is an **assumption**, not a measurement: no published
study gives these parameters for these stimuli. The pilot (Henry, subject zero) checks the
ladder placement; the first recruited listeners are needed to check the variance parameters.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.special import expit
from scipy.stats import chi2, norm

from pianolens.study.psychometric import fit_detection, fit_logit

__all__ = ["H6_MARGIN", "Assumptions", "h6_verdict", "session_minutes", "simulate_once",
           "power_table"]

#: Pre-registered H6 margin (protocol-S03.md section 2): a two-fold difference in cost per
#: threshold unit. The single source for :func:`h6_verdict` and :class:`Assumptions`.
H6_MARGIN: float = 2.0


@dataclass(frozen=True)
class Assumptions:
    """Simulation parameters. Thresholds are 1 in every dimension (the unit is arbitrary).

    The design defaults are design A2 of the protocol (sections 4.2-4.3): detection at 0.5, 1,
    2, 4 x threshold with 3 trials per level (84 trials), preference at 2, 4, 8 x threshold with
    2 trials per level plus 7 identical pairs (49 trials). ``scripts/power_s03.py`` builds its
    A2 design from these defaults and derives A1 and B2 from it.
    """

    n_dims: int = 7
    n_excerpts: int = 8
    # Part A
    det_levels_rel: tuple[float, ...] = (0.5, 1.0, 2.0, 4.0)
    det_reps: int = 3
    det_slope: float = 2.0  # psychometric slope per log2 unit of level
    det_tau_log2: float = 0.5  # between-listener s.d. of log2 threshold
    det_excerpt_sd_log2: float = 0.3  # between-excerpt s.d. of log2 threshold
    ladder_error_log2: float = 0.0  # pilot misplaces the ladder by this (log2)
    lapse: float = 0.02
    # Part B
    pref_levels_rel: tuple[float, ...] = (2.0, 4.0, 8.0)
    pref_reps: int = 2
    pref_identical: int = 7
    pref_beta: float = 0.4  # logit of preferring the original per threshold unit
    pref_beta_sd: float = 0.2  # between-listener s.d. of beta
    position_bias: float = 0.3  # logit bias toward the second item
    ratio: float = 1.0  # beta of dimension 0 / beta of the others (H6 alternative)
    margin: float = H6_MARGIN  # H6 margin: "differ enough" = a slope ratio beyond this
    # session timing (seconds)
    det_clip_sec: float = 6.0
    pref_clip_sec: float = 12.0
    response_sec: float = 4.0
    gap_sec: float = 0.6


def session_minutes(a: Assumptions) -> dict[str, float]:
    """Listening time estimate per listener (excludes consent, checks and breaks)."""
    n_det = a.n_dims * len(a.det_levels_rel) * a.det_reps
    n_pref = a.n_dims * len(a.pref_levels_rel) * a.pref_reps + a.pref_identical
    t_det = n_det * (3 * a.det_clip_sec + 2 * a.gap_sec + a.response_sec)
    t_pref = n_pref * (2 * a.pref_clip_sec + a.gap_sec + a.response_sec)
    return {"n_det_trials": n_det, "n_pref_trials": n_pref, "det_min": t_det / 60,
            "pref_min": t_pref / 60, "total_min": (t_det + t_pref) / 60}  # fmt: skip


def h6_verdict(beta: np.ndarray, cov: np.ndarray, margin: float = H6_MARGIN,
               alpha: float = 0.05) -> dict[str, object]:
    """Apply the pre-registered H6 reading to cost slopes ``beta`` with covariance ``cov``.

    ``margin`` defaults to the pre-registered :data:`H6_MARGIN` (2). Other values are for
    sensitivity analyses only and must be reported as such.
    """
    d = len(beta)
    C = np.zeros((d - 1, d))
    C[:, 0] = -1
    C[np.arange(d - 1), np.arange(1, d)] = 1
    diff = C @ beta
    try:
        wald = float(diff @ np.linalg.solve(C @ cov @ C.T, diff))
    except np.linalg.LinAlgError:
        wald = float("nan")
    p_equal = float(chi2.sf(wald, d - 1)) if np.isfinite(wald) else float("nan")
    n_ord = d * (d - 1)
    z_sup = norm.isf(alpha / n_ord)
    z_eq = norm.isf(alpha)
    differ, all_within = False, True
    for i in range(d):
        for j in range(d):
            if i == j:
                continue
            c = np.zeros(d)
            c[i], c[j] = 1.0, -margin
            est = float(c @ beta)
            se = float(np.sqrt(max(c @ cov @ c, 0.0)))
            if est - z_sup * se > 0:
                differ = True
            if not est + z_eq * se < 0:
                all_within = False
    if differ and p_equal < alpha:
        verdict = "supported"
    elif all_within:
        verdict = "falsified"
    else:
        verdict = "inconclusive"
    return {"verdict": verdict, "p_equal": p_equal, "wald": wald}


def simulate_once(a: Assumptions, n_listeners: int, rng: np.random.Generator
                  ) -> dict[str, float]:
    """Simulate one study with ``n_listeners`` and analyse it as pre-registered."""
    D, L = a.n_dims, n_listeners
    lev = np.asarray(a.det_levels_rel) * 2.0**a.ladder_error_log2
    # ---- Part A
    u = rng.normal(0, a.det_tau_log2, (L, D))
    e = rng.normal(0, a.det_excerpt_sd_log2, (a.n_excerpts, D))
    rows = []
    for d in range(D):
        li, xi = np.meshgrid(np.arange(L), np.arange(len(lev)), indexing="ij")
        li = np.repeat(li.ravel(), a.det_reps)
        xi = np.repeat(xi.ravel(), a.det_reps)
        ex = (li * 3 + np.arange(len(li))) % a.n_excerpts  # rotate excerpts
        x = lev[xi]
        z = a.det_slope * (np.log2(x) - u[li, d] - e[ex, d])
        p = 0.5 + (0.5 - a.lapse) * expit(z)
        y = rng.random(len(p)) < p
        rows.append((d, li, x, y))
    theta_hat = np.zeros(D)
    var_ln_theta = np.zeros(D)
    ci_hw_log2 = np.zeros(D)
    for d, li, x, y in rows:
        f = fit_detection(x, y.astype(float), np.ones(len(y)), li, lapse=a.lapse)
        theta_hat[d] = f.threshold
        var_ln_theta[d] = f.cov[0, 0] * np.log(2) ** 2
        ci_hw_log2[d] = 1.96 * f.se_log2_threshold
    # ---- Part B
    plev = np.asarray(a.pref_levels_rel) * 2.0**a.ladder_error_log2
    beta_true = np.full(D, a.pref_beta)
    beta_true[0] *= a.ratio
    b_il = beta_true[None, :] + rng.normal(0, a.pref_beta_sd, (L, D))
    X_rows, y_rows, cl = [], [], []
    for i in range(L):
        for d in range(D):
            xs = np.repeat(plev, a.pref_reps)
            s = np.where(np.arange(len(xs)) % 2 == (i % 2), 0.5, -0.5)  # counterbalanced
            p = expit(a.position_bias * s + b_il[i, d] * xs)
            y = rng.random(len(p)) < p
            X = np.zeros((len(xs), D + 1))
            X[:, 0] = s
            X[:, 1 + d] = xs / theta_hat[d]
            X_rows.append(X)
            y_rows.append(y)
            cl.append(np.full(len(xs), i))
        s = np.where(np.arange(a.pref_identical) % 2 == 0, 0.5, -0.5)
        y = rng.random(a.pref_identical) < expit(a.position_bias * s)
        X = np.zeros((a.pref_identical, D + 1))
        X[:, 0] = s
        X_rows.append(X)
        y_rows.append(y)
        cl.append(np.full(a.pref_identical, i))
    X = np.vstack(X_rows)
    y = np.concatenate(y_rows).astype(float)
    fit = fit_logit(X, y, np.ones(len(y)), np.concatenate(cl))
    beta = fit.coef[1:]
    cov = fit.cov[1:, 1:] + np.diag(beta**2 * var_ln_theta)
    v = h6_verdict(beta, cov, margin=a.margin)
    se_b = np.sqrt(np.diag(cov))
    return {
        "verdict": v["verdict"],
        "p_equal": v["p_equal"],
        "det_ci_halfwidth_log2_mean": float(np.mean(ci_hw_log2)),
        "det_ci_halfwidth_log2_max": float(np.max(ci_hw_log2)),
        "det_theta_bias_log2": float(np.mean(np.log2(theta_hat))),
        "pref_beta_rel_ci_halfwidth_mean": float(np.mean(1.96 * se_b / np.abs(beta))),
        "pref_beta_mean": float(np.mean(beta[1:])),
        "position_bias_hat": float(fit.coef[0]),
    }


def power_table(base: Assumptions, n_grid: list[int], ratios: list[float], n_rep: int,
                seed: int = 0, **overrides: object) -> pd.DataFrame:
    """Operating characteristics over listener counts and true slope ratios."""
    a0 = dataclasses.replace(base, **overrides) if overrides else base
    out = []
    for r in ratios:
        a = dataclasses.replace(a0, ratio=r)
        for n in n_grid:
            rng = np.random.default_rng([seed, n, int(r * 1000)])
            sims = pd.DataFrame([simulate_once(a, n, rng) for _ in range(n_rep)])
            out.append({
                "ratio": r, "n_listeners": n, "n_rep": n_rep,
                "p_supported": float((sims["verdict"] == "supported").mean()),
                "p_falsified": float((sims["verdict"] == "falsified").mean()),
                "p_inconclusive": float((sims["verdict"] == "inconclusive").mean()),
                "det_ci_hw_log2_mean": float(sims["det_ci_halfwidth_log2_mean"].median()),
                "det_ci_hw_log2_max": float(sims["det_ci_halfwidth_log2_max"].median()),
                "pref_beta_rel_ci_hw": float(sims["pref_beta_rel_ci_halfwidth_mean"].median()),
            })  # fmt: skip
    return pd.DataFrame(out)
