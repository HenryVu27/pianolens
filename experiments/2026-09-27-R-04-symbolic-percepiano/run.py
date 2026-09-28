"""R-04 step 2: symbolic feature models vs frozen MuQ on PercePiano under leave-work-out.

Pre-registered in README.md. Reads `artifacts/features.parquet` (features.py), R-03's MuQ
out-of-fold predictions and pooled embeddings, and the PercePiano labels.

    uv run python experiments/2026-09-27-R-04-symbolic-percepiano/run.py [--jobs 14] [--quick]

Writes `artifacts/results.json`, `oof_predictions.npz`, `per_dimension.csv`, `per_work.csv`,
`importance_*.csv`, `ridge_coefs.csv`, `gam_partial_dependence.csv`, `run.log`.
"""

from __future__ import annotations

import os

os.environ.setdefault("OMP_NUM_THREADS", "1")  # workers are parallel; keep GBM single-threaded

import argparse  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
import time  # noqa: E402
import warnings  # noqa: E402
from dataclasses import dataclass  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from joblib import Parallel, delayed  # noqa: E402
from scipy.stats import rankdata  # noqa: E402
from sklearn.ensemble import HistGradientBoostingRegressor  # noqa: E402
from sklearn.linear_model import Ridge  # noqa: E402
from sklearn.preprocessing import SplineTransformer  # noqa: E402

from pianolens.data.percepiano import (  # noqa: E402
    DIMENSIONS,
    load_percepiano_official_means,
    load_percepiano_ratings,
)
from pianolens.eval import (  # noqa: E402
    group_kfold,
    loo_means,
    pairwise_accuracy,
    r2,
    rater_parity,
    spearman,
)

HERE = Path(__file__).resolve().parent
ART = HERE / "artifacts"
R03 = HERE.parent / "2026-09-27-R-03-muq-percepiano" / "artifacts"
R01 = HERE.parent / "2026-09-27-R-01-percepiano-factors" / "artifacts"
DIMS = list(DIMENSIONS)
NB_R2, NB_ACC, NB_RHO, NB_DIFF = 2000, 1000, 500, 1000
ALPHAS = tuple(float(a) for a in np.logspace(-1, 4, 11))
GBM_GRID = tuple((d, it) for d in (2, 3) for it in (100, 300))
FUSION_W = (0.03, 0.1, 0.3)
MARGIN = {"within_pairacc": 0.02, "within_spearman": 0.05}
LOG: list[str] = []


def log(*a) -> None:
    s = " ".join(str(x) for x in a)
    print(s, flush=True)
    LOG.append(s)


# =========================================================================== metrics
# Row-level definitions identical to R-03 run.py (copied: that module imports torch).


def _inv(groups):
    _, inv, cnt = np.unique(groups, return_inverse=True, return_counts=True)
    return inv, cnt


def r2_mean(y, p) -> float:
    y, p = np.asarray(y, float), np.asarray(p, float)
    sst = ((y - y.mean(0)) ** 2).sum(0)
    return float(np.mean(1 - ((p - y) ** 2).sum(0) / sst))


def _center(a, groups):
    return a - pd.DataFrame(a).groupby(np.asarray(groups)).transform("mean").to_numpy()


def within_r2(y, p, groups) -> float:
    inv, cnt = _inv(groups)
    m = cnt[inv] >= 2
    g = np.asarray(groups)[m]
    return r2_mean(_center(np.asarray(y, float)[m], g), _center(np.asarray(p, float)[m], g))


def _pairs(groups):
    inv, cnt = _inv(groups)
    a, b = [], []
    for g in np.flatnonzero(cnt >= 2):
        mem = np.flatnonzero(inv == g)
        i, j = np.triu_indices(len(mem), 1)
        a.append(mem[i])
        b.append(mem[j])
    return np.concatenate(a), np.concatenate(b)


def within_pairacc(y, p, groups) -> float:
    a, b = _pairs(groups)
    y, p = np.asarray(y, float), np.asarray(p, float)
    t, q = np.sign(y[a] - y[b]), np.sign(p[a] - p[b])
    valid = t != 0
    score = np.where(q == 0, 0.5, (q == t).astype(float))
    return float(np.mean((score * valid).sum(0) / valid.sum(0)))


def within_spearman(y, p, groups) -> float:
    inv, cnt = _inv(groups)
    y, p = np.asarray(y, float), np.asarray(p, float)
    vals = []
    for g in np.flatnonzero(cnt >= 3):
        m = inv == g
        ry, rp = rankdata(y[m], axis=0), rankdata(p[m], axis=0)
        ry, rp = ry - ry.mean(0), rp - rp.mean(0)
        den = np.sqrt((rp**2).sum(0) * (ry**2).sum(0))
        with np.errstate(invalid="ignore", divide="ignore"):
            vals.append((rp * ry).sum(0) / den)
    return float(np.nanmean(np.stack(vals)))


class PassageStats:
    """Per-passage sufficient statistics so a cluster bootstrap over passages is a weighted sum.

    For weights w (replicates x passages; how often each passage was drawn) every metric equals
    the row-level definition on the resampled rows (resampled copies are separate passages).
    """

    def __init__(self, y, groups):
        self.y = np.asarray(y, float)
        self.inv, self.cnt = _inv(groups)
        self.k = len(self.cnt)
        self.a, self.b = _pairs(groups)
        self.pg = self.inv[self.a]
        self.t = np.sign(self.y[self.a] - self.y[self.b])
        D = self.y.shape[1]
        self.n = self.cnt.astype(float)
        self.sy = self._gsum(self.y)
        self.sy2 = self._gsum(self.y**2)
        yc = self.y - (self.sy / self.n[:, None])[self.inv]
        self.sst_w = self._gsum(yc**2) * (self.cnt >= 2)[:, None]
        self.yc = yc
        ry = np.zeros_like(self.y)
        for g in range(self.k):
            m = self.inv == g
            ry[m] = rankdata(self.y[m], axis=0)
        self.ry = ry
        self.D = D

    def _gsum(self, a):
        out = np.zeros((self.k,) + a.shape[1:])
        np.add.at(out, self.inv, a)
        return out

    def stats(self, p):
        p = np.asarray(p, float)
        s = {"sse": self._gsum((p - self.y) ** 2)}
        pc = p - (self._gsum(p) / self.n[:, None])[self.inv]
        s["sse_w"] = self._gsum((self.yc - pc) ** 2) * (self.cnt >= 2)[:, None]
        q = np.sign(p[self.a] - p[self.b])
        valid = self.t != 0
        score = np.where(q == 0, 0.5, (q == self.t).astype(float)) * valid
        corr, val = np.zeros((self.k, self.D)), np.zeros((self.k, self.D))
        np.add.at(corr, self.pg, score)
        np.add.at(val, self.pg, valid.astype(float))
        s["corr"], s["val"] = corr, val
        rho = np.full((self.k, self.D), np.nan)
        for g in np.flatnonzero(self.cnt >= 3):
            m = self.inv == g
            ry = self.ry[m] - self.ry[m].mean(0)
            rp = rankdata(p[m], axis=0)
            rp = rp - rp.mean(0)
            den = np.sqrt((rp**2).sum(0) * (ry**2).sum(0))
            with np.errstate(invalid="ignore", divide="ignore"):
                rho[g] = (rp * ry).sum(0) / den
        s["rho"] = rho
        return s

    def metrics(self, s, W):
        """W: (B, k) weights -> dict of (B,) arrays."""
        N = W @ self.n
        Sy, Sy2 = W @ self.sy, W @ self.sy2
        sst = Sy2 - Sy**2 / N[:, None]
        out = {"r2": np.mean(1 - (W @ s["sse"]) / sst, axis=1)}
        with np.errstate(invalid="ignore", divide="ignore"):
            out["within_r2"] = np.mean(1 - (W @ s["sse_w"]) / (W @ self.sst_w), axis=1)
            out["within_pairacc"] = np.mean((W @ s["corr"]) / (W @ s["val"]), axis=1)
        ok = np.isfinite(s["rho"])
        with np.errstate(invalid="ignore", divide="ignore"):
            out["within_spearman"] = (W @ np.where(ok, s["rho"], 0)).sum(1) / (W @ ok).sum(1)
        return out

    def weights(self, n_boot, seed):
        rng = np.random.default_rng(seed)
        W = np.zeros((n_boot, self.k))
        pick = rng.integers(0, self.k, size=(n_boot, self.k))
        np.add.at(W, (np.repeat(np.arange(n_boot), self.k), pick.ravel()), 1)
        return W


METRICS = ("r2", "within_r2", "within_pairacc", "within_spearman")
NB = {"r2": NB_R2, "within_r2": NB_R2, "within_pairacc": NB_ACC, "within_spearman": NB_RHO}


def evaluate(y, p, groups, seed=0) -> dict:
    ps = PassageStats(y, groups)
    s = ps.stats(p)
    one = np.ones((1, ps.k))
    est = ps.metrics(s, one)
    out = {}
    for m in METRICS:
        W = ps.weights(NB[m], seed)
        reps = ps.metrics(s, W)[m]
        reps = reps[np.isfinite(reps)]
        lo, hi = np.quantile(reps, [0.025, 0.975]) if len(reps) else (np.nan, np.nan)
        out[m] = [round(float(est[m][0]), 4), round(float(lo), 4), round(float(hi), 4)]
    return out


def point(y, p, groups) -> dict:
    ps = PassageStats(y, groups)
    est = ps.metrics(ps.stats(p), np.ones((1, ps.k)))
    return {m: round(float(est[m][0]), 4) for m in METRICS}


def paired(y, pa, pb, groups, seed=0, n_boot=NB_DIFF) -> dict:
    """Δ = metric(pa) - metric(pb) with the same passage resamples."""
    ps = PassageStats(y, groups)
    sa, sb = ps.stats(pa), ps.stats(pb)
    one = np.ones((1, ps.k))
    ea, eb = ps.metrics(sa, one), ps.metrics(sb, one)
    W = ps.weights(n_boot, seed)
    ra, rb = ps.metrics(sa, W), ps.metrics(sb, W)
    out = {}
    for m in METRICS:
        d = ra[m] - rb[m]
        d = d[np.isfinite(d)]
        lo, hi = np.quantile(d, [0.025, 0.975]) if len(d) else (np.nan, np.nan)
        out[m] = [round(float(ea[m][0] - eb[m][0]), 4), round(float(lo), 4), round(float(hi), 4)]
    return out


def per_dim(y, p, groups) -> pd.DataFrame:
    ps = PassageStats(y, groups)
    s = ps.stats(p)
    one = np.ones(ps.k)
    sst = one @ ps.sy2 - (one @ ps.sy) ** 2 / ps.n.sum()
    ok = np.isfinite(s["rho"])
    with np.errstate(invalid="ignore", divide="ignore"):
        return pd.DataFrame({
            "r2": 1 - (one @ s["sse"]) / sst,
            "within_r2": 1 - (one @ s["sse_w"]) / (one @ ps.sst_w),
            "within_pairacc": (one @ s["corr"]) / (one @ s["val"]),
            "within_spearman": (one @ np.where(ok, s["rho"], 0)) / (one @ ok),
        }, index=DIMS[: y.shape[1]] if y.shape[1] == 19 else None)  # fmt: skip


def selfcheck() -> None:
    """Vectorised metrics == R-03 row-level ones == pianolens.eval, incl. one bootstrap draw."""
    rng = np.random.default_rng(0)
    g = rng.integers(0, 12, 90)
    y = rng.integers(1, 6, (90, 3)).astype(float)
    p = y + rng.normal(0, 2, (90, 3))
    ps = PassageStats(y, g)
    est = ps.metrics(ps.stats(p), np.ones((1, ps.k)))
    assert np.isclose(est["r2"][0], np.mean([r2(y[:, d], p[:, d]) for d in range(3)]))
    assert np.isclose(est["within_pairacc"][0], np.mean(
        [pairwise_accuracy(y[:, d], p[:, d], groups=g) for d in range(3)]))
    sp = [spearman(y[g == k, d], p[g == k, d]) for k in np.unique(g) if (g == k).sum() >= 3
          for d in range(3)]
    assert np.isclose(est["within_spearman"][0], np.nanmean(sp))
    assert np.isclose(est["within_r2"][0], within_r2(y, p, g))
    W = ps.weights(1, 5)
    rep = ps.metrics(ps.stats(p), W)
    groups_sorted = np.unique(g)
    idx, lab = [], []
    for j, c in enumerate(W[0].astype(int)):
        for r in range(c):
            m = np.flatnonzero(g == groups_sorted[j])
            idx.append(m)
            lab.append(np.full(len(m), 1000 * j + r))
    idx, lab = np.concatenate(idx), np.concatenate(lab)
    assert np.isclose(rep["r2"][0], r2_mean(y[idx], p[idx]))
    assert np.isclose(rep["within_r2"][0], within_r2(y[idx], p[idx], lab))
    assert np.isclose(rep["within_pairacc"][0], within_pairacc(y[idx], p[idx], lab))
    assert np.isclose(rep["within_spearman"][0], within_spearman(y[idx], p[idx], lab))


# =========================================================================== models


class Prep:
    """Median imputation + missing indicators + standardization (clipped at 5 SD), fit on
    training rows only."""

    def fit(self, X: pd.DataFrame):
        self.cols = list(X.columns)
        self.med = X.median()
        self.ind = [c for c in self.cols if X[c].isna().any()]
        Z = X.fillna(self.med)
        self.mu = Z.mean()
        self.sd = Z.std().replace(0, 1.0).fillna(1.0)
        return self

    def z(self, X: pd.DataFrame) -> np.ndarray:
        Z = ((X[self.cols].fillna(self.med) - self.mu) / self.sd).to_numpy(float)
        return np.clip(np.nan_to_num(Z), -5, 5)

    def transform(self, X: pd.DataFrame) -> np.ndarray:
        return np.hstack([self.z(X), X[self.ind].isna().to_numpy(float)])


@dataclass
class Cand:
    family: str
    params: tuple

    @property
    def name(self) -> str:
        return f"{self.family}{self.params}"


class Model:
    def __init__(self, cand: Cand, cols: list[str], muq_cols: list[str] | None = None):
        self.c, self.cols, self.muq_cols = cand, cols, muq_cols or []

    def fit(self, X: pd.DataFrame, Y: np.ndarray):
        f = self.c.family
        self.prep = Prep().fit(X[self.cols])
        if f == "ridge":
            self.m = Ridge(alpha=self.c.params[0]).fit(self.prep.transform(X[self.cols]), Y)
        elif f == "gam":
            self.spl = SplineTransformer(n_knots=4, degree=3, extrapolation="constant")
            Z = self.prep.z(X[self.cols])
            B = self.spl.fit_transform(Z)
            ind = X[self.prep.ind].isna().to_numpy(float)
            self.m = Ridge(alpha=self.c.params[0]).fit(np.hstack([B, ind]), Y)
        elif f == "gbm":
            d, it = self.c.params
            # sklearn 1.9 HGB crashes on a column with fewer than 2 distinct non-NaN values
            self.gcols = [c for c in self.cols if X[c].nunique(dropna=True) >= 2]
            Xa = X[self.gcols].to_numpy(float)
            self.m = [HistGradientBoostingRegressor(
                max_depth=d, max_iter=it, learning_rate=0.05, min_samples_leaf=20,
                l2_regularization=1.0, random_state=0).fit(Xa, Y[:, k])
                for k in range(Y.shape[1])]  # fmt: skip
        elif f == "fusion":
            w, a = self.c.params
            self.mp = Prep().fit(X[self.muq_cols])
            M = self.mp.z(X[self.muq_cols]) * w
            self.m = Ridge(alpha=a).fit(np.hstack([self.prep.transform(X[self.cols]), M]), Y)
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        f = self.c.family
        if f == "ridge":
            return self.m.predict(self.prep.transform(X[self.cols]))
        if f == "gam":
            B = self.spl.transform(self.prep.z(X[self.cols]))
            return self.m.predict(np.hstack([B, X[self.prep.ind].isna().to_numpy(float)]))
        if f == "gbm":
            Xa = X[self.gcols].to_numpy(float)
            return np.column_stack([m.predict(Xa) for m in self.m])
        M = self.mp.z(X[self.muq_cols]) * self.c.params[0]
        return self.m.predict(np.hstack([self.prep.transform(X[self.cols]), M]))


def candidates(kind: str) -> list[Cand]:
    if kind == "fusion":
        return [Cand("fusion", (w, a)) for w in FUSION_W for a in ALPHAS]
    return ([Cand("ridge", (a,)) for a in ALPHAS] + [Cand("gam", (a,)) for a in ALPHAS]
            + [Cand("gbm", g) for g in GBM_GRID])


def nested_fold(X, Y, passage, inner_groups, tr, te, cols, kind="symbolic", muq_cols=None,
                keep_models=False) -> dict:
    """Choose family + hyperparameters on leave-one-inner-group-out inside ``tr`` by mean inner
    WP Spearman; refit on ``tr``; predict ``te``. Returns the primary prediction and the best
    of each family."""
    warnings.filterwarnings("ignore")
    cands = candidates(kind)
    ig = inner_groups[tr]
    inner = [(tr[ig != g], tr[ig == g]) for g in np.unique(ig)]
    scores = {}
    for c in cands:
        oof = np.full((len(tr), Y.shape[1]), np.nan)
        pos = {r: i for i, r in enumerate(tr)}
        for itr, iva in inner:
            m = Model(c, cols, muq_cols).fit(X.iloc[itr], Y[itr])
            oof[[pos[r] for r in iva]] = m.predict(X.iloc[iva])
        scores[c.name] = within_spearman(Y[tr], oof, passage[tr])
    best = {}
    for c in cands:
        if c.family not in best or scores[c.name] > scores[best[c.family].name]:
            best[c.family] = c
    primary = max(best.values(), key=lambda c: scores[c.name])
    out = {"te": te, "primary": primary.name, "inner_scores": scores, "pred": {},
           "models": {}}
    for fam, c in best.items():
        m = Model(c, cols, muq_cols).fit(X.iloc[tr], Y[tr])
        out["pred"][fam] = m.predict(X.iloc[te])
        out["pred_name_" + fam] = c.name
        if keep_models:
            out["models"][fam] = m
    out["pred"]["primary"] = out["pred"][primary.family]
    if keep_models:
        out["models"]["primary"] = out["models"][primary.family]
    return out


def assemble(results: list[dict], n: int, d: int) -> dict:
    fams = results[0]["pred"].keys()
    P = {f: np.full((n, d), np.nan) for f in fams}
    for r in results:
        for f in fams:
            P[f][r["te"]] = r["pred"][f]
    return P


# =========================================================================== baselines


def baselines(Y, passage, perf, is_score, folds) -> dict:
    tm, pp, dp = (np.zeros_like(Y) for _ in range(3))
    for tr, te in folds:
        mu = Y[tr].mean(0)
        yc = _center(Y[tr], passage[tr])
        tm[te] = mu
        off = pd.DataFrame(yc).groupby(perf[tr]).mean()
        pp[te] = mu + np.vstack([off.loc[p].to_numpy() if p in off.index else np.zeros(Y.shape[1])
                                 for p in perf[te]])  # fmt: skip
        s_off, h_off = yc[is_score[tr]].mean(0), yc[~is_score[tr]].mean(0)
        dp[te] = mu + np.where(is_score[te][:, None], s_off, h_off)
    return {"train_mean": tm, "performer_prior": pp, "deadpan_indicator": dp}


# =========================================================================== ceilings


def wp_parity(pids, pred, ratings, passage, keep_rows=None, untied=False) -> dict:
    """R-03 post-audit within-passage single-rater parity (copied unchanged)."""
    out = []
    for d, dim in enumerate(DIMENSIONS):
        Rm = ratings.matrix(dim).reindex(pids).to_numpy(dtype=float)
        T = loo_means(Rm)
        acc_r, acc_m, n_tie, n_all = [], [], 0, 0
        for j in range(Rm.shape[1]):
            ok = np.isfinite(Rm[:, j]) & np.isfinite(T[:, j])
            if keep_rows is not None:
                ok &= keep_rows
            if ok.sum() < 2:
                continue
            idx = np.flatnonzero(ok)
            g = passage[idx]
            iu = np.triu_indices(len(idx), 1)
            same = (g[:, None] == g[None, :])[iu]
            if same.sum() < 10:
                continue
            a, b = iu[0][same], iu[1][same]
            t = np.sign(T[idx[a], j] - T[idx[b], j])
            keep = t != 0
            if keep.sum() < 10:
                continue
            rr = np.sign(Rm[idx[a], j] - Rm[idx[b], j])[keep]
            mm = np.sign(pred[idx[a], d] - pred[idx[b], d])[keep]
            t = t[keep]
            n_tie += int((rr == 0).sum())
            n_all += len(rr)
            if untied:
                k2 = rr != 0
                if k2.sum() < 10:
                    continue
                rr, mm, t = rr[k2], mm[k2], t[k2]
            acc_r.append(np.mean(np.where(rr == 0, 0.5, rr == t)))
            acc_m.append(np.mean(np.where(mm == 0, 0.5, mm == t)))
        out.append((float(np.mean(acc_r)), float(np.mean(acc_m)), n_tie / max(n_all, 1)))
    a = np.array(out)
    return {"rater_acc": round(float(a[:, 0].mean()), 3),
            "model_acc": round(float(a[:, 1].mean()), 3),
            "dims_model_ahead": int((a[:, 1] > a[:, 0]).sum()),
            "rater_tie_share": round(float(a[:, 2].mean()), 3)}


def pearson_parity(pids, pred, ratings) -> dict:
    rows = []
    for d, dim in enumerate(DIMENSIONS):
        R = ratings.matrix(dim).reindex(pids).to_numpy(float)
        s = rater_parity(R, pred[:, d], method="pearson", min_segments=10, n_boot=1000,
                         seed=d).summary
        lo, hi = s["diff_mean_ci"]
        rows.append((s["rater_r_mean_fisher"], s["model_r_mean_fisher"], lo > 0, hi < 0))
    a = np.array(rows, dtype=float)
    return {"rater_r": round(float(a[:, 0].mean()), 3), "model_r": round(float(a[:, 1].mean()), 3),
            "model_above": int(a[:, 2].sum()), "model_below": int(a[:, 3].sum()),
            "tied": int(19 - a[:, 2].sum() - a[:, 3].sum())}


def split_half(pids, ratings, passage, keep_rows, n_splits=200, seed=0) -> dict:
    """Panel reliability: random rater halves; per-segment half means (>= 2 raters per half);
    WP acc / WP rho of half A vs half B; within-passage Pearson of centred half means and its
    Spearman-Brown full-panel value."""
    rng = np.random.default_rng(seed)
    mats = {dim: ratings.matrix(dim).reindex(pids).to_numpy(float) for dim in DIMS}
    n_r = next(iter(mats.values())).shape[1]
    acc, rho, rw = [], [], []
    for _ in range(n_splits):
        perm = rng.permutation(n_r)
        A, B = perm[: n_r // 2], perm[n_r // 2:]
        for dim in DIMS:
            R = mats[dim]
            ca, cb = np.isfinite(R[:, A]).sum(1), np.isfinite(R[:, B]).sum(1)
            with np.errstate(invalid="ignore"), warnings.catch_warnings():
                warnings.simplefilter("ignore")
                ma, mb = np.nanmean(R[:, A], 1), np.nanmean(R[:, B], 1)
            ok = (ca >= 2) & (cb >= 2) & keep_rows
            g = passage[ok]
            ya, yb = ma[ok][:, None], mb[ok][:, None]
            acc.append(within_pairacc(yb, ya, g))
            rho.append(within_spearman(yb, ya, g))
            inv, cnt = _inv(g)
            m2 = cnt[inv] >= 2
            ac, bc = _center(ya[m2], g[m2])[:, 0], _center(yb[m2], g[m2])[:, 0]
            rw.append(float(np.corrcoef(ac, bc)[0, 1]))
    r = float(np.nanmean(rw))
    return {"half_wp_pairacc": round(float(np.nanmean(acc)), 3),
            "half_wp_spearman": round(float(np.nanmean(rho)), 3),
            "half_within_pearson": round(r, 3),
            "spearman_brown_within_pearson": round(2 * r / (1 + r), 3),
            "n_splits": n_splits}


# =========================================================================== importance

GROUPS = {
    "correctness": lambda c: c.startswith("corr__"),
    "tempo_shape": lambda c: c in ("tempo__log_bpm", "tempo__overall_vs_smooth_log",
                                   "tempo__smooth_log_sd", "tempo__smooth_log_p90_p10",
                                   "tempo__pauses_per_bar", "glob__notes_per_sec")
    or c.startswith("ctrl__tempo_"),
    "timing_jitter": lambda c: c.startswith("tempo__jitter"),
    "evenness_note_rate": lambda c: c.startswith("ctrl__even_") and c.endswith("_note_rate_nps"),
    "evenness_broad": lambda c: c.startswith("ctrl__even_") and "strict" not in c,
    "evenness_strict": lambda c: c.startswith("ctrl__even_strict"),
    "sync_asynchrony": lambda c: c.startswith("ctrl__hand_") or c.startswith("glob__chord_"),
    "pedal": lambda c: c.startswith("ctrl__pedal_") or c.startswith("glob__pedal_")
    or c.startswith("glob__soft_pedal"),
    "velocity_dynamics": lambda c: c.startswith("glob__vel_"),
    "articulation": lambda c: c.startswith("glob__art_") or c.startswith("glob__legato"),
    "voicing": lambda c: c.startswith("shape__voicing_"),
    "coherence_repeats": lambda c: c.startswith("shape__coherence_") or c.startswith(
        "shape__repeat_"),
    "dynamic_compliance": lambda c: c.startswith("shape__dyn_"),
    "ref_timing": lambda c: c.startswith("ref__timing") or c == "ref__rel_jitter_rms_beats",
    "ref_curves": lambda c: c.startswith("ref__") and c.endswith(("_r", "_rms"))
    and not c.startswith("ref__timing"),
    "ref_relative": lambda c: c.startswith("ref__rel_") and c != "ref__rel_jitter_rms_beats",
}


def group_of(c: str) -> str:
    for g, f in GROUPS.items():
        if f(c):
            return g
    return "other"


def perm_importance(model, X, Y, passage, cols, te, n_rep=5, seed=0) -> pd.DataFrame:
    """Drop in per-dimension WP Spearman when a feature group is permuted within passages."""
    rng = np.random.default_rng(seed)
    Xt = X.iloc[te].reset_index(drop=True)
    g = passage[te]
    base = per_dim(Y[te], model.predict(Xt), g)["within_spearman"].to_numpy()
    groups = sorted({group_of(c) for c in cols})
    rows = {}
    members = [np.flatnonzero(g == v) for v in np.unique(g)]
    for grp in groups:
        gc = [c for c in cols if group_of(c) == grp]
        drops = []
        for _ in range(n_rep):
            Xp = Xt.copy()
            perm = np.arange(len(Xt))
            for m in members:
                perm[m] = rng.permutation(m)
            Xp[gc] = Xt[gc].to_numpy()[perm]
            drops.append(base - per_dim(Y[te], model.predict(Xp), g)["within_spearman"].to_numpy())
        rows[grp] = np.mean(drops, axis=0)
    return pd.DataFrame(rows, index=DIMS[: Y.shape[1]])


# =========================================================================== main


def code_hash() -> str:
    repo = HERE.parents[1]
    h = hashlib.sha256()
    for p in sorted(list((repo / "src").rglob("*.py")) + [HERE / "run.py", HERE / "features.py"]):
        h.update(p.read_bytes())
    return h.hexdigest()[:12]


def factor_weights() -> np.ndarray:
    """Unit-weighted salient-item scores for the R-01 k = 4 factors: (19, 4) weights on z-scored
    items (sign of the loading; each item on the factor with its largest |loading|)."""
    L = pd.read_csv(R01 / "loadings_k4.csv", index_col=0)[["F1", "F2", "F3", "F4"]].to_numpy()
    W = np.zeros_like(L)
    k = np.abs(L).argmax(1)
    W[np.arange(len(L)), k] = np.sign(L[np.arange(len(L)), k])
    return W / np.abs(W).sum(0)


def main() -> None:
    ap_ = argparse.ArgumentParser()
    ap_.add_argument("--jobs", type=int, default=14)
    ap_.add_argument("--quick", action="store_true", help="smoke test: fewer candidates")
    a = ap_.parse_args()
    if a.quick:
        global ALPHAS, GBM_GRID, FUSION_W
        ALPHAS, GBM_GRID, FUSION_W = (10.0, 1000.0), ((2, 100),), (0.1,)
    selfcheck()
    t0 = time.time()
    par = Parallel(n_jobs=a.jobs, backend="loky")

    # ------------------------------------------------------------------ data
    F = pd.read_parquet(ART / "features.parquet").set_index("performance_id")
    OOF = np.load(R03 / "oof_predictions.npz")
    PA = np.load(R03 / "oof_predictions_postaudit.npz")
    pids = OOF["pids_all_labeled"].astype(str)
    assert (PA["pids_all_labeled"].astype(str) == pids).all() if "pids_all_labeled" in PA else True
    F = F.loc[pids]
    official = load_percepiano_official_means()
    ratings = load_percepiano_ratings()
    dedup = ratings.mean()[DIMS] / 7.0
    Y = official.loc[pids, DIMS].to_numpy(float)
    Ydd = dedup.loc[pids, DIMS].to_numpy(float)
    passage = F["passage"].to_numpy()
    work4 = F["piece_id"].to_numpy()
    work3 = np.where(np.char.startswith(work4.astype(str), "schubert_d960"), "schubert_d960",
                     work4)
    perf = F["performer_id"].to_numpy()
    is_score = F["is_score"].to_numpy(bool)
    assert (PA["noscore_mask_all_labeled"] == ~is_score).all()
    n = len(pids)
    muq = {"c": OOF["c_official_1000"].mean(1), "c3": PA["c3_official_1000"].mean(1),
           "d": OOF["d_official_1000"].mean(1)}
    muq_seedavg = {"c": OOF["c_official_1000"], "c3": PA["c3_official_1000"]}
    s0 = [c for c in F.columns if "__" in c and not c.startswith("ref__")]
    s1 = s0 + [c for c in F.columns if c.startswith("ref__")]
    Z = np.load(R03 / "muq_pooled.npz")
    zpid = np.array([f"percepiano:{s}" for s in Z["stems"]])
    zi = pd.Series(np.arange(len(zpid)), index=zpid).loc[pids].to_numpy()
    muq_cols = [f"muq_{i}" for i in range(Z["pooled_1000"].shape[2])]
    X = pd.concat([F[s1].reset_index(drop=True),
                   pd.DataFrame(Z["pooled_1000"][zi, 13, :], columns=muq_cols)], axis=1)
    log(f"rows {n}, S0 {len(s0)} features, S1 {len(s1)}; score rows {is_score.sum()}")

    splits = {
        "c": ([(np.flatnonzero(work4 != w), np.flatnonzero(work4 == w))
               for w in sorted(set(work4))], work4),
        "c3": ([(np.flatnonzero(work3 != w), np.flatnonzero(work3 == w))
                for w in sorted(set(work3))], work3),
        "d": (group_kfold(perf, 4, seed=0), work4),
    }
    for k, (folds, _) in splits.items():
        if k != "d":
            for tr, te in folds:
                assert not (set(passage[tr]) & set(passage[te]))
                assert not (set(work4[tr]) & set(work4[te]))

    # ------------------------------------------------------------------ jobs
    jobs = []  # (key, split, cols, kind, target, keep_models)
    for sp in ("c", "c3", "d"):
        jobs.append(("S0", sp, s0, "symbolic", "official", sp != "d"))
        jobs.append(("S1", sp, s1, "symbolic", "official", False))
    for sp in ("c", "c3"):
        jobs.append(("S0_dedup", sp, s0, "symbolic", "dedup", False))
        jobs.append(("S0_broad_only", sp, [c for c in s0 if group_of(c) != "evenness_strict"],
                     "symbolic", "official", False))
        jobs.append(("S0_strict_only", sp, [c for c in s0 if group_of(c) != "evenness_broad"],
                     "symbolic", "official", False))
        jobs.append(("S0_factors", sp, s0, "symbolic", "factors", False))
        jobs.append(("fusion_early", sp, s0, "fusion", "official", False))
    FW = factor_weights()
    Yz_mu, Yz_sd = Y.mean(0), Y.std(0)
    Yfac = ((Y - Yz_mu) / Yz_sd) @ FW
    targets = {"official": Y, "dedup": Ydd, "factors": Yfac}

    tasks = []
    for ji, (_key, sp, cols, kind, tgt, keep) in enumerate(jobs):
        folds, inner_g = splits[sp]
        for fi, (tr, te) in enumerate(folds):
            tasks.append((ji, fi, tr, te, cols, kind, tgt, keep, inner_g))
    log(f"{len(jobs)} jobs, {len(tasks)} outer folds; starting")
    outs = par(delayed(nested_fold)(X, targets[tgt], passage, ig, tr, te, cols, kind,
                                    muq_cols if kind == "fusion" else None, keep)
               for (ji, fi, tr, te, cols, kind, tgt, keep, ig) in tasks)
    log(f"models done {time.time() - t0:.0f}s")
    by_job: dict = {}
    for t, o in zip(tasks, outs, strict=True):
        by_job.setdefault(t[0], []).append((t[1], o))
    preds, choices, models = {}, {}, {}
    for ji, (key, sp, _cols, _kind, tgt, keep) in enumerate(jobs):
        rs = [o for _, o in sorted(by_job[ji], key=lambda x: x[0])]
        P = assemble(rs, n, targets[tgt].shape[1])
        for fam, p in P.items():
            preds[f"{key}|{sp}|{fam}"] = p
        choices[f"{key}|{sp}"] = [{"primary": o["primary"],
                                   **{k: v for k, v in o.items() if k.startswith("pred_name_")},
                                   "inner_best_rho": round(max(o["inner_scores"].values()), 4)}
                                  for o in rs]  # fmt: skip
        if keep:
            models[f"{key}|{sp}"] = [(o["te"], o["models"]) for o in rs]

    res: dict = {"code_hash": code_hash(), "n": n, "n_score": int(is_score.sum()),
                 "features_S0": s0, "features_S1": [c for c in s1 if c not in s0],
                 "choices": choices, "margins": MARGIN}  # fmt: skip

    # ------------------------------------------------------------------ baselines + main table
    base = {sp: baselines(Y, passage, perf, is_score, splits[sp][0]) for sp in ("c", "c3", "d")}
    for sp in ("c", "c3"):
        preds[f"late_fusion|{sp}|primary"] = 0.5 * (muq[sp] + preds[f"S0|{sp}|primary"])
    table = {}
    for sp in ("c", "c3"):
        for mask_name, mask in (("all", np.ones(n, bool)), ("noscore", ~is_score)):
            rows = {}
            cand = {**{f"baseline_{k}": v for k, v in base[sp].items()},
                    "MuQ (seed ensemble)": muq[sp],
                    "S0 primary": preds[f"S0|{sp}|primary"],
                    "S1 primary (transductive)": preds[f"S1|{sp}|primary"],
                    **{f"S0 {f}": preds[f"S0|{sp}|{f}"] for f in ("ridge", "gam", "gbm")},
                    **{f"S1 {f}": preds[f"S1|{sp}|{f}"] for f in ("ridge", "gam", "gbm")},
                    "MuQ+S0 late fusion": preds[f"late_fusion|{sp}|primary"],
                    "MuQ+S0 early fusion": preds[f"fusion_early|{sp}|primary"]}
            for name, p in cand.items():
                rows[name] = evaluate(Y[mask], p[mask], passage[mask])
            per_seed = [point(Y[mask], muq_seedavg[sp][mask, s], passage[mask])
                        for s in range(muq_seedavg[sp].shape[1])]
            rows["MuQ (seed average, R-03)"] = {
                m: round(float(np.mean([r[m] for r in per_seed])), 4) for m in METRICS}
            table[f"{sp}|{mask_name}"] = rows
            log(f"== {sp} {mask_name}")
            for k, v in rows.items():
                log(f"  {k:32s}", {m: v[m] for m in METRICS})
    res["main_table"] = table

    # ------------------------------------------------------------------ H3 decision
    h3 = {}
    for fs in ("S0", "S1"):
        cells = {}
        for sp in ("c", "c3"):
            for mask_name, mask in (("all", np.ones(n, bool)), ("noscore", ~is_score)):
                d = paired(Y[mask], preds[f"{fs}|{sp}|primary"][mask], muq[sp][mask],
                           passage[mask])
                cell = {"delta": d}
                for m in ("within_pairacc", "within_spearman"):
                    est, lo, hi = d[m]
                    cell[m] = ("non-inferior" if lo > -MARGIN[m] else
                               "inferior" if est < -MARGIN[m] and hi < 0 else "neither")
                    cell[m + "_beats"] = lo > 0
                cells[f"{sp}|{mask_name}"] = cell
        ok_all = all(c[m] == "non-inferior" for c in cells.values()
                     for m in ("within_pairacc", "within_spearman"))
        beats = all(c[m + "_beats"] for c in cells.values()
                    for m in ("within_pairacc", "within_spearman"))
        fals = any(all(cells[f"{sp}|{mk}"][m] == "inferior" for sp in ("c", "c3"))
                   for m in ("within_pairacc", "within_spearman") for mk in ("all", "noscore"))
        verdict = ("supported (beats)" if ok_all and beats else "supported (matches)" if ok_all
                   else "falsified" if fals else "inconclusive")
        h3[fs] = {"cells": cells, "verdict": verdict}
        log(f"H3 {fs}: {verdict}")
        for k, c in cells.items():
            log(f"   {k}", c["delta"]["within_pairacc"], c["within_pairacc"],
                c["delta"]["within_spearman"], c["within_spearman"], "R2", c["delta"]["r2"])
    res["h3"] = h3
    # other paired comparisons (descriptive)
    extra = {}
    for sp in ("c", "c3"):
        for name, p in (("S1_vs_S0", (preds[f"S1|{sp}|primary"], preds[f"S0|{sp}|primary"])),
                        ("late_fusion_vs_MuQ", (preds[f"late_fusion|{sp}|primary"], muq[sp])),
                        ("late_fusion_vs_S0", (preds[f"late_fusion|{sp}|primary"],
                                               preds[f"S0|{sp}|primary"])),
                        ("early_fusion_vs_MuQ", (preds[f"fusion_early|{sp}|primary"], muq[sp])),
                        ("S0_vs_performer_prior", (preds[f"S0|{sp}|primary"],
                                                   base[sp]["performer_prior"])),
                        ("S0_vs_deadpan", (preds[f"S0|{sp}|primary"],
                                           base[sp]["deadpan_indicator"]))):
            for mask_name, mask in (("all", np.ones(n, bool)), ("noscore", ~is_score)):
                extra[f"{name}|{sp}|{mask_name}"] = paired(Y[mask], p[0][mask], p[1][mask],
                                                           passage[mask])
    res["paired_extra"] = extra

    # ------------------------------------------------------------------ per work, per dimension
    pw = []
    for sp in ("c", "c3"):
        for w in sorted(set(splits[sp][1])):
            m = splits[sp][1] == w
            for name, p in (("MuQ", muq[sp]), ("S0", preds[f"S0|{sp}|primary"]),
                            ("S1", preds[f"S1|{sp}|primary"]),
                            ("train_mean", base[sp]["train_mean"])):
                for mk, mm in (("all", m), ("noscore", m & ~is_score)):
                    pw.append({"split": sp, "work": w, "model": name, "rows": mk,
                               "n": int(mm.sum()), **point(Y[mm], p[mm], passage[mm])})
    pd.DataFrame(pw).to_csv(ART / "per_work.csv", index=False)
    pdim = []
    for sp in ("c", "c3"):
        for mk, mm in (("all", np.ones(n, bool)), ("noscore", ~is_score)):
            for name, p in (("MuQ", muq[sp]), ("S0", preds[f"S0|{sp}|primary"]),
                            ("S1", preds[f"S1|{sp}|primary"]),
                            ("late_fusion", preds[f"late_fusion|{sp}|primary"]),
                            ("performer_prior", base[sp]["performer_prior"]),
                            ("deadpan", base[sp]["deadpan_indicator"])):
                t = per_dim(Y[mm], p[mm], passage[mm])
                t.insert(0, "model", name)
                t.insert(0, "rows", mk)
                t.insert(0, "split", sp)
                pdim.append(t.rename_axis("dimension").reset_index())
    pd.concat(pdim).round(4).to_csv(ART / "per_dimension.csv", index=False)

    # ------------------------------------------------------------------ sensitivity + (d)
    sens = {}
    for sp in ("c", "c3"):
        sens[f"dedup|{sp}"] = {"S0": point(Ydd, preds[f"S0_dedup|{sp}|primary"], passage),
                               "MuQ": point(Ydd, muq[sp], passage)}
        for v in ("S0_broad_only", "S0_strict_only"):
            for mk, mm in (("all", np.ones(n, bool)), ("noscore", ~is_score)):
                sens[f"{v}|{sp}|{mk}"] = point(Y[mm], preds[f"{v}|{sp}|primary"][mm],
                                               passage[mm])
        for mk, mm in (("all", np.ones(n, bool)), ("noscore", ~is_score)):
            sens[f"S0|{sp}|{mk}"] = point(Y[mm], preds[f"S0|{sp}|primary"][mm], passage[mm])
        muq_fac = ((muq[sp] - Yz_mu) / Yz_sd) @ FW
        for mk, mm in (("all", np.ones(n, bool)), ("noscore", ~is_score)):
            sens[f"factors|{sp}|{mk}"] = {
                "S0": evaluate(Yfac[mm], preds[f"S0_factors|{sp}|primary"][mm], passage[mm]),
                "MuQ": evaluate(Yfac[mm], muq_fac[mm], passage[mm]),
                "S0_per_factor": per_dim(Yfac[mm], preds[f"S0_factors|{sp}|primary"][mm],
                                         passage[mm]).round(4).to_dict("list"),
                "MuQ_per_factor": per_dim(Yfac[mm], muq_fac[mm], passage[mm]).round(4
                                                                                  ).to_dict("list"),
            }
    # alignment-failure passages (match ratio < 0.8 for most performers) left out
    badp = F.groupby("passage")["corr__match_ratio"].median()
    badp = set(badp[badp < 0.8].index)
    keep = ~np.isin(passage, list(badp))
    sens["bad_alignment_passages"] = sorted(badp)
    for sp in ("c", "c3"):
        sens[f"no_bad_alignment|{sp}"] = {"S0": point(Y[keep], preds[f"S0|{sp}|primary"][keep],
                                                      passage[keep]),
                                          "MuQ": point(Y[keep], muq[sp][keep], passage[keep])}
    res["sensitivity"] = sens
    res["leave_performer_out"] = {
        "S0": evaluate(Y, preds["S0|d|primary"], passage),
        "S1": evaluate(Y, preds["S1|d|primary"], passage),
        "MuQ": evaluate(Y, muq["d"], passage),
        "train_mean": evaluate(Y, base["d"]["train_mean"], passage),
    }
    log("sensitivity + (d) done", f"{time.time() - t0:.0f}s")

    # ------------------------------------------------------------------ ceilings
    ceil = {}
    for sp in ("c", "c3"):
        for name, p in (("S0", preds[f"S0|{sp}|primary"]), ("S1", preds[f"S1|{sp}|primary"]),
                        ("MuQ", muq[sp])):
            ceil[f"wp_parity|{sp}|{name}"] = {
                "ties_half": wp_parity(pids, p, ratings, passage),
                "untied": wp_parity(pids, p, ratings, passage, untied=True),
                "untied_noscore": wp_parity(pids, p, ratings, passage, keep_rows=~is_score,
                                            untied=True),
            }
            ceil[f"pearson_parity|{sp}|{name}"] = pearson_parity(pids, p, ratings)
            log("parity", sp, name, ceil[f"wp_parity|{sp}|{name}"]["untied"],
                ceil[f"pearson_parity|{sp}|{name}"])
    ceil["split_half|all"] = split_half(pids, ratings, passage, np.ones(n, bool))
    ceil["split_half|noscore"] = split_half(pids, ratings, passage, ~is_score)
    log("split-half", ceil["split_half|all"], ceil["split_half|noscore"])
    res["ceilings"] = ceil

    # ------------------------------------------------------------------ interpretability
    imp = {}
    for sp in ("c", "c3"):
        for fam in ("primary", "ridge", "gbm") if sp == "c" else ("primary",):
            parts = []
            for te, ms in models[f"S0|{sp}"]:
                parts.append((len(te), perm_importance(ms[fam], X, Y, passage, s0, te)))
            tot = sum(w for w, _ in parts)
            M = sum(w * t for w, t in parts) / tot
            M.round(4).to_csv(ART / f"importance_{sp}_{fam}.csv")
            imp[f"{sp}|{fam}"] = {"mean_over_dims": M.mean().round(4).sort_values(
                ascending=False).to_dict(),
                "top_group_per_dim": M.idxmax(axis=1).to_dict()}  # fmt: skip
            log("importance", sp, fam, imp[f"{sp}|{fam}"]["mean_over_dims"])
    res["importance"] = imp
    # ridge coefficients and GAM partial dependence on all labelled rows
    alpha_c = [c["pred_name_ridge"] for c in choices["S0|c"]]
    a_r = float(pd.Series([float(x[len("ridge("):-2]) for x in alpha_c]).median())
    rm = Model(Cand("ridge", (a_r,)), s0).fit(X, Y)
    names = s0 + [f"{c}__missing" for c in rm.prep.ind]
    coefs = pd.DataFrame(rm.m.coef_.T, index=names, columns=DIMS)
    coefs.round(5).to_csv(ART / "ridge_coefs.csv")
    top = {d: coefs[d].abs().sort_values(ascending=False).head(5).index.tolist() for d in DIMS}
    res["ridge_alpha_all_rows"] = a_r
    res["ridge_top5"] = {d: [(f, round(float(coefs.loc[f, d]), 4)) for f in top[d]] for d in DIMS}
    gam_c = [c["pred_name_gam"] for c in choices["S0|c"]]
    a_g = float(pd.Series([float(x[len("gam("):-2]) for x in gam_c]).median())
    gm = Model(Cand("gam", (a_g,)), s0).fit(X, Y)
    pdr = []
    for di, d in enumerate(DIMS):
        for f in [x for x in top[d] if not x.endswith("__missing")][:3]:
            v = X[f].dropna()
            for q in np.linspace(0.05, 0.95, 9):
                Xg = X.copy()
                Xg[f] = float(v.quantile(q))
                pdr.append({"dimension": d, "feature": f, "quantile": round(q, 3),
                            "x": float(v.quantile(q)),
                            "pd": float(gm.predict(Xg)[:, di].mean())})
    pd.DataFrame(pdr).round(5).to_csv(ART / "gam_partial_dependence.csv", index=False)
    res["gam_alpha_all_rows"] = a_g

    # ------------------------------------------------------------------ save
    np.savez_compressed(ART / "oof_predictions.npz", pids=pids,
                        **{k.replace("|", "__"): v.astype(np.float32) for k, v in preds.items()})
    res["wall_sec"] = round(time.time() - t0, 1)
    (ART / "results.json").write_text(json.dumps(res, indent=1, default=str))
    (ART / "run.log").write_text("\n".join(LOG))
    log(f"done {res['wall_sec']}s")


if __name__ == "__main__":
    main()
