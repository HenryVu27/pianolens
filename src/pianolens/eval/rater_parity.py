"""Rater parity: does a model agree with the panel as well as a typical held-out rater does?

Input is a segments x raters matrix with NaN for "not rated". For each rater j:

- target_j = mean of the *other* raters on each segment j rated (leave-one-rater-out mean),
  using only segments that at least ``min_other_raters`` other raters also rated;
- r_rater_j = corr(rater j, target_j);
- r_model_j = corr(model, target_j) on exactly the same segments.

Both correlations use the same target and the same segments, so ``r_model_j - r_rater_j`` is a
paired, like-for-like comparison. A model "reaches rater parity" when that difference is >= 0
for the typical rater (median / mean over raters).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .metrics import pearson, spearman

_CORR = {"pearson": pearson, "spearman": spearman}


def _fisher_mean(r: np.ndarray) -> float:
    r = r[np.isfinite(r)]
    if len(r) == 0:
        return float("nan")
    return float(np.tanh(np.mean(np.arctanh(np.clip(r, -0.999999, 0.999999)))))


@dataclass
class RaterParity:
    per_rater: pd.DataFrame
    summary: dict = field(default_factory=dict)


def loo_means(ratings: np.ndarray) -> np.ndarray:
    """Leave-one-rater-out means: entry [i, j] is the mean of row i over raters other than j.

    NaN where no other rater rated segment i.
    """
    r = np.asarray(ratings, dtype=float)
    obs = np.isfinite(r)
    tot = np.where(obs, r, 0.0).sum(axis=1, keepdims=True)
    cnt = obs.sum(axis=1, keepdims=True)
    others_sum = tot - np.where(obs, r, 0.0)
    others_cnt = cnt - obs
    with np.errstate(invalid="ignore", divide="ignore"):
        out = others_sum / others_cnt
    out[others_cnt == 0] = np.nan
    return out


def rater_parity(ratings, model=None, *, method: str = "pearson", min_segments: int = 10,
                 min_other_raters: int = 1, rater_ids=None, n_boot: int = 0,
                 seed: int = 0) -> RaterParity:
    """Compute rater parity.

    ratings: (n_segments, n_raters) array or DataFrame, NaN = missing.
    model: optional (n_segments,) predictions (out-of-fold predictions for a fair ceiling).
    min_segments: raters with fewer usable segments are dropped from the summary.
    n_boot: if > 0, percentile CIs by resampling *raters* for the summary means.
    """
    if isinstance(ratings, pd.DataFrame):
        if rater_ids is None:
            rater_ids = list(ratings.columns)
        ratings = ratings.to_numpy(dtype=float)
    r = np.asarray(ratings, dtype=float)
    if r.ndim != 2:
        raise ValueError("ratings must be 2-D (segments x raters)")
    if rater_ids is None:
        rater_ids = list(range(r.shape[1]))
    corr = _CORR[method]
    if model is not None:
        model = np.asarray(model, dtype=float).ravel()
        if len(model) != r.shape[0]:
            raise ValueError("model must have one prediction per segment")

    obs = np.isfinite(r)
    n_others = obs.sum(axis=1, keepdims=True) - obs
    target = loo_means(r)
    rows = []
    for j, rid in enumerate(rater_ids):
        m = obs[:, j] & (n_others[:, j] >= min_other_raters) & np.isfinite(target[:, j])
        if model is not None:
            m &= np.isfinite(model)
        n = int(m.sum())
        row = {"rater": rid, "n_segments": n, "r_rater": np.nan}
        if model is not None:
            row["r_model"] = np.nan
        if n >= max(min_segments, 3):
            row["r_rater"] = corr(target[m, j], r[m, j])
            if model is not None:
                row["r_model"] = corr(target[m, j], model[m])
        rows.append(row)
    per = pd.DataFrame(rows)
    used = per[(per.n_segments >= max(min_segments, 3)) & per.r_rater.notna()].copy()
    if model is not None:
        used = used[used.r_model.notna()]
        per["diff"] = per.r_model - per.r_rater

    rr = used.r_rater.to_numpy()
    s: dict = {
        "method": method,
        "n_raters": int(len(used)),
        "rater_r_median": float(np.median(rr)) if len(rr) else float("nan"),
        "rater_r_mean_fisher": _fisher_mean(rr),
    }
    if model is not None:
        rm = used.r_model.to_numpy()
        d = rm - rr
        s.update({
            "model_r_median": float(np.median(rm)) if len(rm) else float("nan"),
            "model_r_mean_fisher": _fisher_mean(rm),
            "diff_mean": float(np.mean(d)) if len(d) else float("nan"),
            "diff_median": float(np.median(d)) if len(d) else float("nan"),
            "frac_raters_model_beats": float(np.mean(d > 0)) if len(d) else float("nan"),
        })
        has = obs.any(axis=1)
        if has.any():
            full = np.nanmean(r[has], axis=1)
            s["model_r_full_panel"] = corr(full, model[has])
    if n_boot > 0 and len(used) > 1:
        rng = np.random.default_rng(seed)
        k = len(used)
        picks = rng.integers(0, k, size=(n_boot, k))
        boot_r = np.array([_fisher_mean(rr[p]) for p in picks])
        s["rater_r_mean_ci"] = tuple(np.quantile(boot_r, [0.025, 0.975]).tolist())
        if model is not None:
            boot_d = (rm - rr)[picks].mean(axis=1)
            s["diff_mean_ci"] = tuple(np.quantile(boot_d, [0.025, 0.975]).tolist())
    return RaterParity(per_rater=per, summary=s)


def ratings_matrix(df: pd.DataFrame, segment: str, rater: str, value: str) -> pd.DataFrame:
    """Pivot long ratings (one row per segment x rater) into a segments x raters matrix.

    Duplicate (segment, rater) pairs are averaged.
    """
    return df.pivot_table(index=segment, columns=rater, values=value, aggfunc="mean")
