"""R-10 H1b summary (any env with pianolens + scipy; CPU).

Statistics (definitions fixed in ../README.md, "Method"):

  Decisions (README): H1b-consensus is read on arm frozen_p95 (top-p 0.95 samples), H1b-axes on
  arm frozen_p100 (top-p 1.0); every reading is printed for every arm, the others are
  sensitivity analyses. Pre-run amendments (README, below "Run record"): --exclude-pieces (A1),
  --exclude-renditions (A2), --sibling-flag (A4 split), r² and amplitude ratio b next to every
  R²c (R1), composer-cluster CI (R2), headline rule (A3).
  primary  H1b-consensus: per piece and target (velocity, log IOI), centered R² of the model's
           mean curve against the expert mean curve, both curves centered (R-06 formula,
           R-06 analyze.py), no refit. Median over pieces; 95% CI by a work-cluster bootstrap.
           Next to it: the K-matched expert oracle (empirical: mean of 16 held-out experts vs
           the mean of the rest, pieces with n >= 36; analytic: expected R²c of a mean of 16 new
           experts vs this piece's n-expert mean, all pieces) and the ratio R²c / oracle.
  second.  H1b-axes: captured share of the k shared components (parallel analysis, envelope
           null) by the model's 16 samples, divided by the captured share of 16 held-out experts
           in the same reduced subspace (subspace estimated from the other n - 16 performers;
           R-07 audit script B2). Pieces with n >= 36 and k > 0.
  explor.  Conditional component prediction (leave-one-performer-out; first half -> second
           half), expert basis vs model basis vs performer-mean vs zero.
  baselines  flat curve (R²c = 0 by construction), score-feature ridge (train_ridge.py), and
           the R10u development numbers (separate run of this script on R-07's R10u set).

Inputs: --set DIR (manifest.csv with kind == real rows, items/, gen_items/), and any number of
--arm NAME=DIR where DIR holds <gen item name>.npz (symupe_gen.py / pt_gen.py output), plus
optionally --ridge model.npz (train_ridge.py). --experts-only computes the expert side only
(used before the pre-registration; no model output is read).

    python summarize_h1b.py --set OUT/sets/fresh --arm frozen=OUT/gen/frozen_p100/fresh \\
        --ridge OUT/ridge/ridge.npz --out OUT/results/fresh
"""

from __future__ import annotations

import argparse
import json
import warnings
import zlib
from pathlib import Path

import numpy as np
import pandas as pd

from pianolens.models.expression_data import load_item
from pianolens.models.expression_io import note_expression

TARGETS = ("velocity", "log_ioi")
N_BOOT = 2000
K_ORACLE = 16
MIN_REF = 20
DRAWS = 20
N_NULL = 100
THRESH = {"consistent": 0.50, "falsified": 0.20}          # plan H1b row, applied to R²c
AXES_THRESH = {"consistent": 0.80, "floor": 0.40}         # README, after the reachability check


def _slug(s: str) -> str:
    return "".join(c if c.isalnum() or c in "-." else "_" for c in s)


def feats(it: dict) -> pd.DataFrame:
    ex = note_expression(it["score_onset_q"], it["score_dur_q"], it["perf_onset_sec"],
                         it["perf_dur_sec"], it["velocity"])
    ex["score_id"] = it["score_id"]
    ex["onset_q"] = np.round(it["score_onset_q"], 6)
    return ex


def corr(a, b) -> float:
    ok = np.isfinite(a) & np.isfinite(b)
    if ok.sum() < 5 or np.std(a[ok]) == 0 or np.std(b[ok]) == 0:
        return np.nan
    return float(np.corrcoef(a[ok], b[ok])[0, 1])


def r2c(m: np.ndarray, p: np.ndarray) -> float:
    """R-06 (b): centered R², both curves centered over the onsets where both are finite."""
    ok = np.isfinite(m) & np.isfinite(p)
    if ok.sum() < 5:
        return np.nan
    mc, pc = m[ok] - m[ok].mean(), p[ok] - p[ok].mean()
    den = np.sum(mc ** 2)
    return float(1 - np.sum((mc - pc) ** 2) / den) if den > 0 else np.nan


def shape_amp(m: np.ndarray, p: np.ndarray) -> tuple[float, float]:
    """Pre-run amendment R1: Pearson r and amplitude ratio b = sd(pc) / sd(mc) over the onsets
    where both are finite, so that R²c = 2 r b - b² (both curves centered)."""
    ok = np.isfinite(m) & np.isfinite(p)
    if ok.sum() < 5:
        return np.nan, np.nan
    mc, pc = m[ok] - m[ok].mean(), p[ok] - p[ok].mean()
    sm = np.sqrt(np.mean(mc ** 2))
    return corr(mc, pc), float(np.sqrt(np.mean(pc ** 2)) / sm) if sm > 0 else np.nan


def r2c_r07(m: np.ndarray, p: np.ndarray) -> float:
    """R-07 summarize_eval h1b_passage: only the target centered (kept for continuity)."""
    ok = np.isfinite(m) & np.isfinite(p)
    den = np.sum((m[ok] - m[ok].mean()) ** 2)
    return float(1 - np.sum((m[ok] - p[ok]) ** 2) / den) if den > 0 else np.nan


def nanmean0(X):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        return np.nanmean(X, 0)


def center_rows(X):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        return X - np.nanmean(X, 1, keepdims=True)


def mean_curves(V, T):
    """Mean curve per target: velocity rows centered per rendition (R-06), nan-aware means."""
    return nanmean0(center_rows(V)), nanmean0(T)


def _fill(X):
    """Column-mean fill (R-07); a column with no finite value takes the overall mean, so it
    carries no deviation (only happens for small subsets, e.g. 2 held-out experts)."""
    X = X.copy()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        cm = np.nanmean(X, 0)
    cm = np.where(np.isfinite(cm), cm, np.nanmean(X))
    r, c = np.where(~np.isfinite(X))
    X[r, c] = cm[c]
    return X


# ------------------------------------------------------------------------------ curves


def expert_matrix(set_dir: Path, stems, idx: pd.Index, cache: dict):
    V, T = [], []
    for st in stems:
        if st not in cache:
            cache[st] = feats(load_item(set_dir / "items" / f"{st}__real.npz")).groupby(
                "onset_q")[["velocity", "log_ioi"]].mean()
        c = cache[st].reindex(idx)
        V.append(c["velocity"].to_numpy())
        T.append(c["log_ioi"].to_numpy())
    return np.array(V), np.array(T)


def gen_curves(gen_item: dict, z: dict, idx: pd.Index):
    """Per-sample curves of a generation output (R-07 gen_prediction, curves part)."""
    Sv, St = [], []
    for k in range(z["onset"].shape[0]):
        ex = note_expression(gen_item["score_onset_q"], gen_item["score_dur_q"], z["onset"][k],
                             z["dur"][k], z["vel"][k])
        ex["onset_q"] = np.round(gen_item["score_onset_q"], 6)
        c = ex.groupby("onset_q")[["velocity", "log_ioi"]].mean().reindex(idx)
        Sv.append(c["velocity"].to_numpy())
        St.append(c["log_ioi"].to_numpy())
    return np.array(Sv), np.array(St)


def ridge_curves(gen_item: dict, model: dict, idx: pd.Index):
    from train_ridge import predict

    P = predict(gen_item, model)
    P["onset_q"] = np.round(gen_item["score_onset_q"], 6)
    c = P.groupby("onset_q")[["velocity", "log_ioi"]].mean().reindex(idx)
    return c["velocity"].to_numpy()[None], c["log_ioi"].to_numpy()[None]


# ------------------------------------------------------------------------------ expert side


def reliability(X, n_split: int = 50, seed: int = 0) -> float:
    """R-06: mean split-half r of the mean curve over 50 random splits, Spearman-Brown."""
    rng = np.random.default_rng(seed)
    n = len(X)
    rs = []
    for _ in range(n_split):
        p = rng.permutation(n)
        rs.append(corr(nanmean0(X[p[: n // 2]]), nanmean0(X[p[n // 2:]])))
    r = np.nanmean(rs)
    return float(2 * r / (1 + r)) if np.isfinite(r) and r > -1 else np.nan


def analytic_oracle(X, K: int = K_ORACLE) -> dict:
    """Expected R²c of the mean of K new exchangeable experts against this piece's n-expert mean
    curve, from the per-onset between-performer variance (random-effects model):
      E SS(a - b) = sum_j s2_j (1/K + 1/n_j),  E SS(b_c) = SS(m_c)  (observed),
      oracle = 1 - E SS(a - b) / SS(m_c);  noise = sum_j s2_j / n_j  (target noise part)."""
    m = nanmean0(X)
    nj = np.isfinite(X).sum(0)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        s2 = np.nanvar(X, 0, ddof=1)
    ok = np.isfinite(m) & np.isfinite(s2) & (nj >= 2)
    mc = m[ok] - m[ok].mean()
    ss = float(np.sum(mc ** 2))
    noise = float(np.sum(s2[ok] / nj[ok]))
    err = float(np.sum(s2[ok] * (1 / K + 1 / nj[ok])))
    return {"oracle_analytic": 1 - err / ss if ss > 0 else np.nan, "ss_target": ss,
            "ss_noise": noise, "ss_signal": ss - noise}


def parallel_k(V, T, n_null: int = N_NULL, seed: int = 0):
    """R-07 h1b_passage: k leading eigenvalues of the joint deviation matrix above the 95th
    percentile of an envelope-preserving surrogate (R-02 audit)."""
    Vf, Tf = _fill(V), _fill(T)
    Vf = Vf - Vf.mean(1, keepdims=True)
    sv, st = np.std(Vf - Vf.mean(0)), np.std(Tf - Tf.mean(0))
    J = np.hstack([(Vf - Vf.mean(0)) / sv, (Tf - Tf.mean(0)) / st])
    n, d = J.shape
    ev = np.linalg.svd(J, compute_uv=False) ** 2
    ev = ev / ev.sum()
    rng = np.random.default_rng(seed)

    def env(D):
        F = np.fft.rfft(D, axis=1)
        ph = rng.uniform(0, 2 * np.pi, F.shape)
        ph[:, 0] = 0
        S = np.fft.irfft(np.abs(F) * np.exp(1j * ph), n=D.shape[1], axis=1)
        S = S - S.mean(0)
        return S / (S.std(0) + 1e-12) * D.std(0)

    null = []
    for _ in range(n_null):
        S = np.hstack([env(J[:, : d // 2]), env(J[:, d // 2:])])
        e = np.linalg.svd(S, compute_uv=False) ** 2
        null.append(e / e.sum())
    q = np.quantile(np.array(null), 0.95, axis=0)
    above = ev[: len(q)] > q
    k = int(np.argmin(above)) if not above.all() else len(q)
    return k, float(ev[:k].sum())


def basis(V, T, k):
    """R-07 audit B2 ``basis``: reduced subspace from a reference group of performers."""
    Vf, Tf = _fill(V), _fill(T)
    Vf = Vf - Vf.mean(1, keepdims=True)
    sv, st = np.std(Vf - Vf.mean(0)), np.std(Tf - Tf.mean(0))
    J = np.hstack([(Vf - Vf.mean(0)) / sv, (Tf - Tf.mean(0)) / st])
    return J, np.linalg.svd(J, full_matrices=False)[2][:k], sv, st


def capture(J, Vk, Vs, Ts, sv, st):
    """R-07 audit B2 ``capture``: share of the reference group's k-component variance lying in
    the span of a set of curves' deviations from their own mean."""
    Ds = J @ Vk.T @ Vk
    Sv, St = _fill(Vs), _fill(Ts)
    Sv = Sv - Sv.mean(1, keepdims=True)
    M = np.hstack([(Sv - Sv.mean(0)) / sv, (St - St.mean(0)) / st])
    _, s, Wt = np.linalg.svd(M, full_matrices=False)
    Q = Wt[s > 1e-9 * s.max()].T
    return float(np.sum((Ds @ Q) ** 2) / np.sum(Ds ** 2))


def capture_random(J, Vk, dims: int, rng, n: int = 50) -> float:
    Ds = J @ Vk.T @ Vk
    tot = np.sum(Ds ** 2)
    return float(np.mean([np.sum((Ds @ np.linalg.qr(rng.normal(size=(J.shape[1], dims)))[0])
                                 ** 2) / tot for _ in range(n)]))


def holdout_draws(n: int, seed_key: str, draws: int = DRAWS, K: int = K_ORACLE):
    rng = np.random.default_rng(1 + zlib.crc32(seed_key.encode()) % 1_000_003)
    out = []
    for _ in range(draws):
        p = rng.permutation(n)
        out.append((p[:K], p[K:]))
    return out


# ------------------------------------------------------------------------------ exploratory


def conditional_prediction(V, T, k: int, model_curves=None) -> dict:
    """Leave-one-performer-out: component scores estimated on the first half of the onsets,
    deviation predicted on the second half. Bases: expert (top k of the other performers),
    model (top k of the model samples' deviations, if given). Baselines: zero (= consensus) and
    performer mean (the performer's mean deviation per target on the first half)."""
    Vf, Tf = _fill(V), _fill(T)
    Vf = Vf - Vf.mean(1, keepdims=True)
    n, P = Vf.shape
    A = np.zeros(2 * P, bool)
    A[: P // 2] = True
    A[P: P + P // 2] = True
    B = ~A
    blk = np.r_[np.zeros(P, int), np.ones(P, int)]
    res = {"zero": [], "perf_mean": [], "expert_basis": [], "model_basis": []}
    if model_curves is not None:
        Sv, St = model_curves
        Sv, St = _fill(Sv), _fill(St)
        Sv = Sv - Sv.mean(1, keepdims=True)
    for i in range(n):
        o = np.r_[:i, i + 1:n]
        mv, mt = Vf[o].mean(0), Tf[o].mean(0)
        sv, st = np.std(Vf[o] - mv), np.std(Tf[o] - mt)
        J = np.hstack([(Vf[o] - mv) / sv, (Tf[o] - mt) / st])
        y = np.r_[(Vf[i] - mv) / sv, (Tf[i] - mt) / st]
        ss = np.sum(y[B] ** 2)
        res["zero"].append(1.0)  # SSE / SS of predicting 0 (R² = 0 by construction)
        pm = np.where(blk == 0, y[A & (blk == 0)].mean(), y[A & (blk == 1)].mean())
        res["perf_mean"].append(np.sum((y[B] - pm[B]) ** 2) / ss)
        bases = {"expert_basis": np.linalg.svd(J, full_matrices=False)[2][:k]}
        if model_curves is not None:
            M = np.hstack([(Sv - Sv.mean(0)) / sv, (St - St.mean(0)) / st])
            bases["model_basis"] = np.linalg.svd(M, full_matrices=False)[2][:k]
        for name, W in bases.items():
            z, *_ = np.linalg.lstsq(W[:, A].T, y[A], rcond=None)
            res[name].append(np.sum((y[B] - z @ W[:, B]) ** 2) / ss)
    return {f"cond_r2_{k_}": float(1 - np.mean(v)) for k_, v in res.items() if v}


# ------------------------------------------------------------------------------ per piece


def piece_rows(set_dir: Path, piece: str, g: pd.DataFrame, arms: dict, ridge, cache: dict,
               experts_only: bool, min_oracle: int) -> tuple[dict, list[dict]]:
    fname = _slug(piece) + ".npz"
    gi = load_item(set_dir / "gen_items" / fname)
    idx = pd.Index(np.unique(np.round(gi["score_onset_q"], 6)))
    V, T = expert_matrix(set_dir, g["stem"].tolist(), idx, cache)
    keep = (np.isfinite(V).mean(0) >= 0.5) & (np.isfinite(T).mean(0) >= 0.5)
    V, T = V[:, keep], T[:, keep]
    Vc = center_rows(V)
    mv, mt = mean_curves(V, T)
    n = len(V)
    E = {"piece": piece, "work": g["work"].iloc[0], "n": n, "n_onsets": int(keep.sum()),
         "gen_notes": int(len(gi["pitch"]))}
    for col in ("capture_model", "source_dataset"):
        if col in g:
            for k_, v in g[col].value_counts().items():
                E[f"n_{col}_{_slug(str(k_))}"] = int(v)
    for t, X in (("velocity", Vc), ("log_ioi", T)):
        E[f"reliability_{t}"] = reliability(X)
        for k_, v in analytic_oracle(X).items():
            E[f"{k_}_{t}"] = v
    k, var_shared = parallel_k(V, T)
    E.update(k=k, var_shared=var_shared)
    draws = holdout_draws(n, piece) if n >= min_oracle else []
    if draws:
        for t, X in (("velocity", Vc), ("log_ioi", T)):
            E[f"oracle_emp_{t}"] = float(np.mean(
                [r2c(nanmean0(X[r]), nanmean0(X[h])) for h, r in draws]))
            rb = np.array([shape_amp(nanmean0(X[r]), nanmean0(X[h])) for h, r in draws])
            E[f"oracle_emp_r2_{t}"] = float(np.mean(rb[:, 0] ** 2))
            E[f"oracle_emp_b_{t}"] = float(np.mean(rb[:, 1]))
        if k > 0:
            ce, cr = [], []
            rng = np.random.default_rng(7)
            for h, r in draws:
                J, Vk, sv, st = basis(V[r], T[r], k)
                ce.append(capture(J, Vk, V[h], T[h], sv, st))
                cr.append(capture_random(J, Vk, K_ORACLE - 1, rng))
            E.update(cap_oracle=float(np.mean(ce)), cap_random=float(np.mean(cr)))
    if experts_only:
        return E, []

    A_rows = []
    preds = {}
    for arm, adir in arms.items():
        zp = Path(adir) / fname
        if zp.exists():
            Sv, St = gen_curves(gi, load_item(zp), idx)
            preds[arm] = (Sv[:, keep], St[:, keep])
    if ridge is not None:
        Rv, Rt = ridge_curves(gi, ridge, idx)
        preds["ridge"] = (Rv[:, keep], Rt[:, keep])
    for arm, (Sv, St) in preds.items():
        pv, pt = mean_curves(Sv, St)
        row = {"arm": arm, "piece": piece, "work": E["work"], "n": n, "K": len(Sv)}
        for t, m, p in (("velocity", mv, pv), ("log_ioi", mt, pt)):
            row[f"r2c_{t}"] = r2c(m, p)
            row[f"r_{t}"] = corr(m, p)
            rr, bb = shape_amp(m, p)
            row[f"r2_{t}"], row[f"b_{t}"] = rr ** 2, bb
            row[f"r2c_r07_{t}"] = r2c_r07(m, p)
            row[f"ratio_analytic_{t}"] = row[f"r2c_{t}"] / E[f"oracle_analytic_{t}"]
            # disattenuated (vs the noise-free consensus; descriptive)
            ok = np.isfinite(m) & np.isfinite(p)
            sse = np.sum(((m[ok] - m[ok].mean()) - (p[ok] - p[ok].mean())) ** 2)
            row[f"r2c_true_{t}"] = float(1 - (sse - E[f"ss_noise_{t}"]) / E[f"ss_signal_{t}"]) \
                if E[f"ss_signal_{t}"] > 0 else np.nan
        row["ioi_offset"] = float(np.nanmean(pt) - np.nanmean(mt))
        if draws:
            Xs = {"velocity": (Vc, pv), "log_ioi": (T, pt)}
            for t, (X, p) in Xs.items():
                mm = np.mean([r2c(nanmean0(X[r]), p) for _, r in draws])
                row[f"r2c_vs_rest_{t}"] = float(mm)
                row[f"ratio_emp_{t}"] = float(mm / E[f"oracle_emp_{t}"])
            if k > 0 and len(Sv) > 1:
                cm = []
                for _h, r in draws:
                    J, Vk, sv, st = basis(V[r], T[r], k)
                    cm.append(capture(J, Vk, Sv, St, sv, st))
                row["cap_model"] = float(np.mean(cm))
                row["axes_ratio"] = row["cap_model"] / E["cap_oracle"]
        if k > 0 and len(Sv) > 1:
            row.update(conditional_prediction(V, T, k, (Sv, St)))
        A_rows.append(row)
    if k > 0:
        E.update({f"expert_{k_}": v for k_, v in conditional_prediction(V, T, k).items()})
    return E, A_rows


# ------------------------------------------------------------------------------ summary


def cluster_boot_median(df: pd.DataFrame, col: str, seed: int = 0, n_boot: int = N_BOOT,
                        cluster: str = "work"):
    d = df.dropna(subset=[col])
    if d.empty:
        return (np.nan, np.nan, np.nan, 0)
    works = d[cluster].to_numpy()
    u, inv = np.unique(works, return_inverse=True)
    vals = d[col].to_numpy(float)
    rng = np.random.default_rng(seed)
    bs = []
    for _ in range(n_boot):
        m = np.bincount(rng.integers(0, len(u), len(u)), minlength=len(u))
        w = m[inv]
        bs.append(np.median(np.repeat(vals, w)) if w.sum() else np.nan)
    lo, hi = np.nanpercentile(bs, [2.5, 97.5])
    return (float(np.median(vals)), float(lo), float(hi), int(len(d)))


def reading(point, lo, hi, cons, fals) -> str:
    """Pre-registered three-way reading (README): the point decides the side, the CI must exclude
    the opposite threshold."""
    if not np.isfinite(point):
        return "n/a"
    if point >= cons and lo > fals:
        return "consistent"
    if point <= fals and hi < cons:
        return "falsified"
    return "inconclusive"


def composer_of(piece: str, meta: dict) -> str:
    if piece in meta:
        return meta[piece]
    return piece.split(":")[1].split("/")[0] if piece.startswith("pianocore:") \
        else piece.split("_")[0]


def summarise(P: pd.DataFrame, A: pd.DataFrame, primary_arm: str, min_r: int,
              min_oracle: int, composers: dict | None = None, sibling: dict | None = None,
              axes_arm: str = "frozen_p100") -> dict:
    s: dict = {}
    Pp = P[P["n"] >= min_r]
    s["pieces"] = {"total": int(len(P)), "primary_n_ge_min": int(len(Pp)),
                   "works_primary": int(Pp["work"].nunique()),
                   "oracle_eligible": int((Pp["n"] >= min_oracle).sum()),
                   "axes_eligible": int(((Pp["n"] >= min_oracle) & (Pp["k"] > 0)).sum())}
    ex = {}
    for c in [c for c in Pp.columns if c.startswith(("reliability", "oracle", "cap_", "k",
                                                     "var_shared", "expert_cond"))]:
        if Pp[c].notna().any():
            ex[c] = cluster_boot_median(Pp, c)
    s["experts"] = ex
    if A.empty:
        return s
    A = A[A["piece"].isin(Pp["piece"])]
    arms = {}
    for arm, g in A.groupby("arm"):
        r = {}
        for c in [c for c in g.columns if c.startswith(("r2c", "r_", "r2_", "b_", "ratio",
                                                        "cap_", "axes", "cond_r2",
                                                        "ioi_offset"))]:
            if g[c].notna().any():
                r[c] = cluster_boot_median(g, c)
        for t in TARGETS:
            pt, lo, hi, _ = r[f"r2c_{t}"]
            r[f"reading_{t}"] = reading(pt, lo, hi, THRESH["consistent"], THRESH["falsified"])
            orc = Pp[f"oracle_analytic_{t}"].median()
            r[f"ratio_of_medians_analytic_{t}"] = float(pt / orc)
            if f"r2c_vs_rest_{t}" in r:
                oe = Pp.loc[Pp["n"] >= min_oracle, f"oracle_emp_{t}"].median()
                r[f"ratio_of_medians_emp_{t}"] = float(r[f"r2c_vs_rest_{t}"][0] / oe)
        rv, rt = r["reading_velocity"], r["reading_log_ioi"]
        r["reading_H1b_consensus"] = rv if rv == rt else f"mixed (velocity {rv}, log IOI {rt})"
        if "axes_ratio" in r:
            pt, lo, hi, _ = r["axes_ratio"]
            r["reading_H1b_axes"] = reading(pt, lo, hi, AXES_THRESH["consistent"],
                                            AXES_THRESH["floor"]).replace("falsified", "floor")
        # per composer and leave-one-composer-out medians (sensitivity)
        comp = g["piece"].map(lambda p: composer_of(p, composers or {}))
        gc = g.assign(composer=comp.to_numpy())
        for t in TARGETS:
            # R2: composer-cluster CI (descriptive; the work-cluster CI decides)
            r[f"r2c_{t}_composer_cluster_ci"] = cluster_boot_median(gc, f"r2c_{t}",
                                                                    cluster="composer")
            if sibling:  # A4: exploratory split by the committed sibling flag
                fl = g["piece"].map(sibling)
                r[f"sibling_split_r2c_{t}"] = {
                    str(k_): cluster_boot_median(g[fl == k_], f"r2c_{t}")
                    for k_ in sorted(fl.dropna().unique())}
        if "axes_ratio" in g:
            r["axes_ratio_per_piece"] = g.dropna(subset=["axes_ratio"]).set_index("piece")[
                "axes_ratio"].round(4).to_dict()
        for t in TARGETS:
            r[f"per_composer_median_r2c_{t}"] = g.groupby(comp)[f"r2c_{t}"].median().round(
                4).to_dict()
            r[f"loco_range_r2c_{t}"] = [float(g.loc[comp != c_, f"r2c_{t}"].median())
                                        for c_ in sorted(set(comp))]
            r[f"loco_range_r2c_{t}"] = [min(r[f"loco_range_r2c_{t}"]),
                                        max(r[f"loco_range_r2c_{t}"])]
        arms[arm] = r
    s["arms"] = arms
    # A3 headline rule: the registered reading (primary arm), plus the top-p 1.0 reading
    # whenever it differs for either target
    if primary_arm in arms:
        pr = arms[primary_arm]
        h = (f"H1b-consensus ({primary_arm}, registered): velocity {pr['reading_velocity']}, "
             f"log IOI {pr['reading_log_ioi']}")
        if axes_arm in arms and axes_arm != primary_arm:
            al = arms[axes_arm]
            if (al["reading_velocity"], al["reading_log_ioi"]) != (pr["reading_velocity"],
                                                                   pr["reading_log_ioi"]):
                h += (f"; on {axes_arm} (top-p 1.0, not deciding) it reads velocity "
                      f"{al['reading_velocity']}, log IOI {al['reading_log_ioi']}")
            if "reading_H1b_axes" in al:
                h += f". H1b-axes ({axes_arm}, registered): {al['reading_H1b_axes']}"
        s["headline"] = h
    # paired differences against the ridge baseline and between arms
    W = A.pivot_table(index=["piece", "work"], columns="arm",
                      values=[f"r2c_{t}" for t in TARGETS]).reset_index()
    pairs = {}
    names = sorted(A["arm"].unique())
    for a_ in names:
        for b_ in names:
            if a_ == b_ or (b_ != "ridge" and not (a_ == primary_arm)):
                continue
            for t in TARGETS:
                d = pd.DataFrame({"work": W["work"],
                                  "d": W[(f"r2c_{t}", a_)] - W[(f"r2c_{t}", b_)]})
                pairs[f"{a_}-{b_}:{t}"] = cluster_boot_median(d, "d")
    s["paired_median_differences"] = pairs
    return s


def per_source(set_dir: Path, man: pd.DataFrame, arms: dict, min_src: int, cache: dict):
    """R²c of each arm against the mean curve of one capture model's renditions (pieces with at
    least ``min_src`` renditions of that source), with that subset's analytic oracle."""
    rows = []
    for piece, g in man.groupby("passage"):
        fname = _slug(piece) + ".npz"
        gi = load_item(set_dir / "gen_items" / fname)
        idx = pd.Index(np.unique(np.round(gi["score_onset_q"], 6)))
        Vall, Tall = expert_matrix(set_dir, g["stem"].tolist(), idx, cache)
        keep = (np.isfinite(Vall).mean(0) >= 0.5) & (np.isfinite(Tall).mean(0) >= 0.5)
        preds = {}
        for arm, adir in arms.items():
            zp = Path(adir) / fname
            if zp.exists():
                Sv, St = gen_curves(gi, load_item(zp), idx)
                preds[arm] = mean_curves(Sv[:, keep], St[:, keep])
        # rendition level: r of each rendition's curve with each arm's mean curve and with the
        # leave-one-out expert mean (same piece), by capture model (descriptive)
        Vk, Tk = center_rows(Vall[:, keep]), Tall[:, keep]
        for i, (src, stem) in enumerate(zip(g["capture_model"], g["stem"], strict=True)):
            o = np.r_[:i, i + 1:len(g)]
            loo = {"velocity": nanmean0(Vk[o]), "log_ioi": nanmean0(Tk[o])}
            own = {"velocity": Vk[i], "log_ioi": Tk[i]}
            rec = {"level": "rendition", "piece": piece, "work": g["work"].iloc[0],
                   "source": src, "stem": stem}
            for t in TARGETS:
                rec[f"r_loo_{t}"] = corr(own[t], loo[t])
            for arm, (pv, pt) in preds.items():
                mm = {"velocity": pv, "log_ioi": pt}
                rows.append({**rec, "arm": arm,
                             **{f"r_loo_{t}": rec[f"r_loo_{t}"] for t in TARGETS},
                             **{f"r_model_{t}": corr(own[t], mm[t]) for t in TARGETS}})
        for src, gs in g.groupby("capture_model"):
            if len(gs) < min_src:
                continue
            sel = g["capture_model"].to_numpy() == src
            V, T = Vall[sel][:, keep], Tall[sel][:, keep]
            mv, mt = mean_curves(V, T)
            base = {"level": "piece", "piece": piece, "work": g["work"].iloc[0], "source": src,
                    "n_src": len(gs),
                    "oracle_analytic_velocity": analytic_oracle(center_rows(V))[
                        "oracle_analytic"],
                    "oracle_analytic_log_ioi": analytic_oracle(T)["oracle_analytic"]}
            for arm, (pv, pt) in preds.items():
                rows.append({**base, "arm": arm, "r2c_velocity": r2c(mv, pv),
                             "r2c_log_ioi": r2c(mt, pt)})
            if not preds:
                rows.append(base)
    return pd.DataFrame(rows)


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", required=True)
    ap.add_argument("--arm", action="append", default=[], help="name=dir of gen outputs")
    ap.add_argument("--ridge", default=None)
    ap.add_argument("--out", required=True)
    ap.add_argument("--primary-arm", default="frozen_p95",
                    help="arm whose paired differences are reported (H1b-consensus arm)")
    ap.add_argument("--min-renditions", type=int, default=20)
    ap.add_argument("--min-oracle", type=int, default=K_ORACLE + MIN_REF)
    ap.add_argument("--min-source", type=int, default=10)
    ap.add_argument("--experts-only", action="store_true")
    ap.add_argument("--pieces", nargs="*", default=None, help="restrict to these piece ids")
    ap.add_argument("--meta", default=None, help="CSV with piece_id, composer (per-composer "
                    "tables); default: composer guessed from the piece id")
    ap.add_argument("--exclude-pieces", default=None,
                    help="CSV with piece_id: pieces dropped from every statistic (amendment A1)")
    ap.add_argument("--exclude-renditions", default=None,
                    help="CSV with piece_id, dropped_performance_id (amendment A2)")
    ap.add_argument("--sibling-flag", default=None,
                    help="CSV with piece_id, sibling_paired (amendment A4, exploratory split)")
    ap.add_argument("--axes-arm", default="frozen_p100")
    a = ap.parse_args(argv)
    set_dir, out = Path(a.set), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    arms = dict(x.split("=", 1) for x in a.arm)
    if a.experts_only:
        arms, ridge = {}, None
    else:
        ridge = dict(np.load(a.ridge)) if a.ridge else None
    man = pd.read_csv(set_dir / "manifest.csv")
    man = man[man["kind"] == "real"]
    if a.pieces:
        man = man[man["passage"].isin(a.pieces)]
    excl = {"pieces_file": a.exclude_pieces, "renditions_file": a.exclude_renditions,
            "pieces_dropped": 0, "renditions_dropped": 0}
    if a.exclude_pieces:
        xp = set(pd.read_csv(a.exclude_pieces)["piece_id"])
        excl["pieces_dropped"] = int(man.loc[man["passage"].isin(xp), "passage"].nunique())
        man = man[~man["passage"].isin(xp)]
    if a.exclude_renditions:
        xr = pd.read_csv(a.exclude_renditions)
        pid_col = "performance_id" if "performance_id" in man else "performer"
        key = set(zip(xr["piece_id"], xr["dropped_performance_id"].astype(str), strict=True))
        drop = np.array([(p, str(q)) in key for p, q in zip(man["passage"], man[pid_col],
                                                              strict=True)], dtype=bool)
        excl["renditions_dropped"] = int(drop.sum())
        excl["renditions_listed"] = int(len(xr))
        man = man[~drop]
    cache: dict = {}
    P_rows, A_rows = [], []
    for piece, g in man.groupby("passage"):
        if len(g) < min(a.min_renditions, 6):
            continue
        e, rows = piece_rows(set_dir, piece, g, arms, ridge, cache, a.experts_only,
                             a.min_oracle)
        P_rows.append(e)
        A_rows.extend(rows)
        print(f"{piece}: n={e['n']} k={e['k']}", flush=True)
    P = pd.DataFrame(P_rows)
    A = pd.DataFrame(A_rows)
    P.to_csv(out / "experts_per_piece.csv", index=False)
    if not A.empty:
        A.to_csv(out / "arms_per_piece.csv", index=False)
    composers = {}
    if a.meta:
        mt = pd.read_csv(a.meta)
        if "composer" in mt:
            composers = dict(zip(mt["piece_id"], mt["composer"], strict=True))
    sibling = None
    if a.sibling_flag:
        sf = pd.read_csv(a.sibling_flag)
        sibling = dict(zip(sf["piece_id"], sf["sibling_paired"].astype(bool), strict=True))
    s = summarise(P, A, a.primary_arm, a.min_renditions, a.min_oracle, composers, sibling,
                  a.axes_arm)
    s.update({"set": str(set_dir), "arms": {**s.get("arms", {})}, "arm_dirs": arms,
              "exclusions": excl,
              "ridge": a.ridge, "experts_only": a.experts_only,
              "thresholds": {"consensus": THRESH, "axes": AXES_THRESH}})
    if "capture_model" in man and not a.experts_only:
        S = per_source(set_dir, man[man["passage"].isin(P.loc[P["n"] >= a.min_renditions,
                                                              "piece"])],
                       arms, a.min_source, cache)
        S.to_csv(out / "per_source.csv", index=False)
        if not S.empty and "arm" in S:
            Sp = S[(S["level"] == "piece")].dropna(subset=["arm"])
            s["per_source_piece_level"] = {f"{arm}:{src}": {
                "pieces": int(len(g)),
                **{c: cluster_boot_median(g, c)[:3] for c in
                   ("r2c_velocity", "r2c_log_ioi", "oracle_analytic_velocity",
                    "oracle_analytic_log_ioi")}}
                for (arm, src), g in Sp.groupby(["arm", "source"])}
            Sr = S[(S["level"] == "rendition")].dropna(subset=["arm"])
            s["per_source_rendition_level"] = {f"{arm}:{src}": {
                "renditions": int(len(g)), "pieces": int(g["piece"].nunique()),
                **{f"median_{c}": float(g[c].median()) for c in
                   ("r_model_velocity", "r_loo_velocity", "r_model_log_ioi", "r_loo_log_ioi")}}
                for (arm, src), g in Sr.groupby(["arm", "source"])}
    (out / "summary.json").write_text(json.dumps(s, indent=1, default=float))
    print(json.dumps(s, indent=1, default=float)[:6000])


if __name__ == "__main__":
    main()
