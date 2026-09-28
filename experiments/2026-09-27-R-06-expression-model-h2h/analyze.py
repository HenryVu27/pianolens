"""R-06 analysis (project env): metrics (a)-(c) for SyMuPe, Pianist Transformer and baselines.

    OMP_NUM_THREADS=1 uv run python experiments/2026-09-27-R-06-expression-model-h2h/analyze.py
Writes artifacts/results/*.csv and artifacts/results/summary.json.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from baseline import predict as ridge_predict  # noqa: E402

from pianolens.models.expression_io import note_expression  # noqa: E402

ART = HERE / "artifacts"
RES = ART / "results"
MODELS = ("symupe", "pt")
TARGETS = ("velocity", "log_ioi", "log_art")
LL_FIELDS = {
    "symupe": {"timing": ["TimeShift"], "velocity": ["Velocity"], "duration": ["TimeDuration"],
               "pedal": ["TimeDurationSustain"]},
    "pt": {"timing": ["interval"], "velocity": ["velocity"], "duration": ["duration"],
           "pedal": ["pedal1", "pedal2", "pedal3", "pedal4"]},
}
ALT_KINDS = ["jitT10", "jitT20", "jitT40", "jitV4", "jitV8", "jitV16", "deadpan"]
N_BOOT = 2000
MIN_B = 6
MIN_B2 = 10


def load(path: Path) -> dict:
    z = np.load(path, allow_pickle=False)
    return {k: z[k] for k in z.files}


def feats(it: dict) -> pd.DataFrame:
    ex = note_expression(it["score_onset_q"], it["score_dur_q"], it["perf_onset_sec"],
                         it["perf_dur_sec"], it["velocity"])
    ex["score_id"] = it["score_id"]
    ex["onset_q"] = np.round(it["score_onset_q"], 6)
    return ex


def _slug(s: str) -> str:
    return "".join(c if c.isalnum() or c in "-." else "_" for c in s)


# ---------------------------------------------------------------------- predictions

def passage_predictions(set_name: str, passage: str) -> dict | None:
    """Per model: per-note mean / sd of sample features (indexed by score_id) and sample onset
    curves (K x onsets, indexed by onset_q)."""
    gpath = ART / "gen_items" / set_name / f"{_slug(passage)}.npz"
    if not gpath.exists():
        return None
    g = load(gpath)
    out = {"score": g}
    for m in MODELS:
        p = ART / m / "generate" / set_name / gpath.name
        if not p.exists():
            continue
        z = load(p)
        per = []
        curves = []
        for k in range(z["onset"].shape[0]):
            ex = note_expression(g["score_onset_q"], g["score_dur_q"], z["onset"][k],
                                 z["dur"][k], z["vel"][k])
            ex["onset_q"] = np.round(g["score_onset_q"], 6)
            per.append(ex[list(TARGETS)].to_numpy())
            curves.append(ex.groupby("onset_q")[["velocity", "log_ioi"]].mean())
        arr = np.stack(per)  # K x n x 3
        with np.errstate(invalid="ignore"):
            mean = np.nanmean(arr, 0)
            sd = np.nanstd(arr, 0)
        out[m] = {
            "mean": pd.DataFrame(mean, columns=TARGETS, index=g["score_id"]),
            "sd": pd.DataFrame(sd, columns=TARGETS, index=g["score_id"]),
            "curves": curves,
        }
    return out


def corr(a: np.ndarray, b: np.ndarray) -> float:
    ok = np.isfinite(a) & np.isfinite(b)
    if ok.sum() < 5 or np.std(a[ok]) == 0 or np.std(b[ok]) == 0:
        return np.nan
    return float(np.corrcoef(a[ok], b[ok])[0, 1])


def target_r(actual: pd.DataFrame, pred: pd.DataFrame) -> dict[str, float]:
    """r per target; log_ioi on one row per score onset."""
    out = {}
    for t in TARGETS:
        if t == "log_ioi":
            first = ~actual["onset_q"].duplicated()
            out[t] = corr(actual.loc[first, t].to_numpy(), pred.loc[first.values, t].to_numpy())
        else:
            out[t] = corr(actual[t].to_numpy(), pred[t].to_numpy())
    return out


# ---------------------------------------------------------------------- bootstrap

def cluster_boot(df: pd.DataFrame, value: str, work: str = "work", cluster: str = "passage",
                 n_boot: int = N_BOOT, seed: int = 0) -> tuple[float, float, float]:
    """Unweighted mean over works of (mean over rows per work); CI by resampling clusters
    within works."""
    d = df.dropna(subset=[value])
    if d.empty:
        return (np.nan, np.nan, np.nan)
    # cluster sums/counts per work
    agg = d.groupby([work, cluster])[value].agg(["sum", "count"]).reset_index()
    works = sorted(agg[work].unique())

    def stat(tab):
        return np.mean([t["sum"].sum() / t["count"].sum() for t in tab])

    tabs = [agg[agg[work] == w] for w in works]
    point = stat(tabs)
    rng = np.random.default_rng(seed)
    boots = []
    one_each = all(len(t) == 1 for t in tabs)  # A, V: a work is one piece -> resample pieces
    for _ in range(n_boot):
        if one_each:
            boots.append(stat([tabs[i] for i in rng.integers(0, len(tabs), len(tabs))]))
            continue
        rs = []
        for t in tabs:
            idx = rng.integers(0, len(t), len(t))
            rs.append(t.iloc[idx])
        boots.append(stat(rs))
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return (float(point), float(lo), float(hi))


def per_work(df: pd.DataFrame, value: str) -> dict[str, float]:
    return {w: float(g[value].mean()) for w, g in df.dropna(subset=[value]).groupby("work")}


# ---------------------------------------------------------------------- scores for (c)

def ll_score(m: str, item: str, set_name: str) -> dict | None:
    p = ART / m / "score" / set_name / f"{item}.npz"
    if not p.exists():
        return None
    z = load(p)
    out = {}
    for grp, keys in LL_FIELDS[m].items():
        out[grp] = float(np.nanmean(np.nanmean(np.stack([z[k] for k in keys]), 0)))
    per_note = z[LL_FIELDS[m]["timing"][0]] + z[LL_FIELDS[m]["velocity"][0]] \
        + z[LL_FIELDS[m]["duration"][0]]
    out["core"] = float(np.nanmean(per_note))
    return out


def paired_auc(real: pd.Series, alt: pd.Series) -> pd.Series:
    j = pd.concat([real.rename("r"), alt.rename("a")], axis=1).dropna()
    return (j["r"] > j["a"]).astype(float) + 0.5 * (j["r"] == j["a"]).astype(float)


# ---------------------------------------------------------------------- main

def main() -> None:
    RES.mkdir(parents=True, exist_ok=True)
    man = pd.read_parquet(ART / "manifest.parquet")
    man = man[man["item"].notna()].copy()
    man["work"] = np.where(man["set"] == "P", man["piece_id"], man["passage"])
    ridge = load(ART / "baseline.npz")
    real = man[man["kind"] == "real"]

    a_rows, b_rows, b2_rows, c_rows = [], [], [], []
    for (set_name, passage), grp in real.groupby(["set", "passage"]):
        pp = passage_predictions(set_name, passage)
        if pp is None:
            continue
        work = grp["work"].iloc[0]
        rend = {}
        for _, row in grp.iterrows():
            it = load(ART / "items" / set_name / f"{row['item']}.npz")
            f = feats(it)
            rp = ridge_predict(it, ridge)
            rp.index = it["score_id"]
            rend[row["item"]] = (f, rp)
        # (a) per rendition
        for item, (f, rp) in rend.items():
            preds = {"ridge": rp.loc[f["score_id"]].reset_index(drop=True)}
            for m in MODELS:
                if m in pp:
                    preds[m] = pp[m]["mean"].reindex(f["score_id"]).reset_index(drop=True)
            others = [o[0] for k, o in rend.items() if k != item]
            if others:
                cat = pd.concat([o.set_index("score_id")[list(TARGETS)] for o in others])
                loo = cat.groupby(level=0).mean()
                preds["loo_others"] = loo.reindex(f["score_id"]).reset_index(drop=True)
            fa = f.reset_index(drop=True)
            for name, pr in preds.items():
                rr = target_r(fa, pr)
                a_rows.append({"set": set_name, "work": work, "passage": passage, "item": item,
                               "predictor": name, **rr,
                               "composite": np.nanmean([rr[t] for t in TARGETS])})
        # (b) mean curves
        if len(rend) >= MIN_B:
            curves = []
            for f, _ in rend.values():
                c = f.groupby("onset_q")[["velocity", "log_ioi"]].mean()
                c["velocity"] = c["velocity"] - c["velocity"].mean()
                curves.append(c)
            idx = sorted(set().union(*[c.index for c in curves]))
            V = np.array([c["velocity"].reindex(idx).to_numpy() for c in curves])
            T = np.array([c["log_ioi"].reindex(idx).to_numpy() for c in curves])
            keep = (np.isfinite(V).mean(0) >= 0.5) & (np.isfinite(T).mean(0) >= 0.5)
            idx = np.array(idx)[keep]
            V, T = V[:, keep], T[:, keep]
            mv, mt = np.nanmean(V, 0), np.nanmean(T, 0)
            preds = {}
            rp_all = ridge_predict(pp["score"], ridge)
            rp_all["onset_q"] = np.round(pp["score"]["score_onset_q"], 6)
            rc = rp_all.groupby("onset_q")[["velocity", "log_ioi"]].mean().reindex(idx)
            preds["ridge"] = (rc["velocity"].to_numpy(), rc["log_ioi"].to_numpy())
            for m in MODELS:
                if m in pp:
                    cs = [c.reindex(idx) for c in pp[m]["curves"]]
                    pv = np.nanmean([c["velocity"].to_numpy() - np.nanmean(c["velocity"])
                                     for c in cs], 0)
                    pt_ = np.nanmean([c["log_ioi"].to_numpy() for c in cs], 0)
                    preds[m] = (pv, pt_)
            # split-half ceiling (Spearman-Brown)
            rng = np.random.default_rng(0)
            n = len(V)
            shv, sht = [], []
            for _ in range(50):
                perm = rng.permutation(n)
                h1, h2 = perm[: n // 2], perm[n // 2:]
                shv.append(corr(np.nanmean(V[h1], 0), np.nanmean(V[h2], 0)))
                sht.append(corr(np.nanmean(T[h1], 0), np.nanmean(T[h2], 0)))
            rel = {}
            for key, s in (("velocity", shv), ("log_ioi", sht)):
                r = np.nanmean(s)
                rel[key] = float(2 * r / (1 + r)) if np.isfinite(r) and r > -1 else np.nan
            for name, (pv, pt_) in preds.items():
                for key, mcur, pcur in (("velocity", mv, pv), ("log_ioi", mt, pt_)):
                    ok = np.isfinite(mcur) & np.isfinite(pcur)
                    if ok.sum() < 5:
                        continue
                    mc = mcur[ok] - mcur[ok].mean()
                    pc = pcur[ok] - pcur[ok].mean()
                    r2c = 1 - np.sum((mc - pc) ** 2) / np.sum(mc**2)
                    b_rows.append({"set": set_name, "work": work, "passage": passage,
                                   "predictor": name, "target": key, "n_perf": n,
                                   "n_onsets": int(ok.sum()), "r2_centered": float(r2c),
                                   "r2": corr(mc, pc) ** 2, "r": corr(mc, pc),
                                   "reliability": rel[key]})
            # (b2) shared components (exploratory)
            if n >= MIN_B2:
                b2_rows.extend(shared_components(set_name, work, passage, V, T, idx, pp))
        # (c) scores per item of this passage
        items = man[(man["set"] == set_name) & (man["passage"] == passage)]
        for _, row in items.iterrows():
            it = load(ART / "items" / set_name / f"{row['item']}.npz")
            f = feats(it)
            rp = ridge_predict(it, ridge)
            rec = {"set": set_name, "work": work, "passage": passage, "item": row["item"],
                   "kind": row["kind"], "performance_id": row["performance_id"]}
            for m in MODELS:
                s = ll_score(m, row["item"], set_name)
                if s:
                    rec.update({f"{m}_ll_{k}": v for k, v in s.items()})
                if m in pp:
                    mu = pp[m]["mean"].reindex(f["score_id"]).reset_index(drop=True)
                    sd = pp[m]["sd"].reindex(f["score_id"]).reset_index(drop=True)
                    zs = []
                    for t in TARGETS:
                        floor = np.nanmedian(pp[m]["sd"][t].to_numpy())
                        s_ = np.maximum(sd[t].to_numpy(), floor)
                        zs.append(np.nanmean(((f[t].to_numpy() - mu[t].to_numpy()) / s_) ** 2))
                    rec[f"{m}_gen"] = -float(np.nanmean(zs))
            resid = []
            for t, s_ in zip(TARGETS, ridge["resid_sd"], strict=True):
                y = f[t].to_numpy()
                yhat = rp[t].to_numpy()
                if t == "log_art":
                    y = np.clip(y, -3, 3)
                resid.append(np.nanmean(((y - yhat) / s_) ** 2))
            rec["ridge_gauss"] = -0.5 * float(np.nansum(resid))
            c = f.groupby("onset_q")[["velocity", "log_ioi"]].mean()
            rec["_dv2"] = float(np.nanmean(np.diff(c["velocity"].to_numpy()) ** 2))
            rec["_dt2"] = float(np.nanmean(np.diff(c["log_ioi"].to_numpy()) ** 2))
            c_rows.append(rec)

    A = pd.DataFrame(a_rows)
    B = pd.DataFrame(b_rows)
    B2 = pd.DataFrame(b2_rows)
    C = pd.DataFrame(c_rows)
    rr = C[C["kind"] == "real"]
    sv, st = np.nanmedian(rr["_dv2"]), np.nanmedian(rr["_dt2"])
    C["smooth"] = -(C["_dv2"] / sv + C["_dt2"] / st)
    A.to_csv(RES / "a_per_rendition.csv", index=False)
    B.to_csv(RES / "b_per_passage.csv", index=False)
    B2.to_csv(RES / "b2_shared.csv", index=False)
    C.to_csv(RES / "c_scores.csv", index=False)
    summary = summarise(A, B, B2, C)
    (RES / "summary.json").write_text(json.dumps(summary, indent=1, default=float))
    print(json.dumps(summary, indent=1, default=float)[:6000])


def _envelope_surrogate(D: np.ndarray, rng) -> np.ndarray:
    """Phase-randomise each row, then rescale columns to the real column s.d. (R-02 audit)."""
    F = np.fft.rfft(D, axis=1)
    ph = rng.uniform(0, 2 * np.pi, F.shape)
    ph[:, 0] = 0
    S = np.fft.irfft(np.abs(F) * np.exp(1j * ph), n=D.shape[1], axis=1)
    S = S - S.mean(0)
    return S / (S.std(0) + 1e-12) * D.std(0)


def shared_components(set_name, work, passage, V, T, idx, pp) -> list[dict]:
    """Exploratory (b2): k shared components by parallel analysis against an envelope null; share
    of expert variance in them that lies in the span of each model's sample deviations."""
    def fill(X):
        X = X.copy()
        cm = np.nanmean(X, 0)
        r, c = np.where(~np.isfinite(X))
        X[r, c] = cm[c]
        return X

    Vf, Tf = fill(V), fill(T)
    sv, st = np.std(Vf - Vf.mean(0)), np.std(Tf - Tf.mean(0))
    J = np.hstack([(Vf - Vf.mean(0)) / sv, (Tf - Tf.mean(0)) / st])
    n, d = J.shape
    ev = np.linalg.svd(J, compute_uv=False) ** 2
    ev = ev / ev.sum()
    rng = np.random.default_rng(0)
    null = []
    for _ in range(20):
        S = np.hstack([_envelope_surrogate(J[:, : d // 2], rng),
                       _envelope_surrogate(J[:, d // 2:], rng)])
        e = np.linalg.svd(S, compute_uv=False) ** 2
        null.append(e / e.sum())
    q = np.quantile(np.array(null), 0.95, axis=0)
    above = ev[: len(q)] > q
    k = int(np.argmin(above)) if not above.all() else len(q)
    rows = []
    base = {"set": set_name, "work": work, "passage": passage, "n_perf": n, "d": d, "k": k,
            "var_shared": float(ev[:k].sum())}
    if k == 0:
        return [{**base, "predictor": "none"}]
    _, _, Vt = np.linalg.svd(J, full_matrices=False)
    Uk = Vt[:k].T
    Ds = J @ Uk @ Uk.T
    tot = np.sum(Ds**2)
    for m in MODELS:
        if m not in pp:
            continue
        cs = [c.reindex(idx) for c in pp[m]["curves"]]
        Sv = fill(np.array([c["velocity"].to_numpy() - np.nanmean(c["velocity"]) for c in cs]))
        St = fill(np.array([c["log_ioi"].to_numpy() for c in cs]))
        M = np.hstack([(Sv - Sv.mean(0)) / sv, (St - St.mean(0)) / st])
        U, s, Wt = np.linalg.svd(M, full_matrices=False)
        Q = Wt[s > 1e-9 * s.max()].T
        cap = float(np.sum((Ds @ Q) ** 2) / tot)
        rnd = []
        for _ in range(200):
            R, _ = np.linalg.qr(rng.normal(size=(d, Q.shape[1])))
            rnd.append(np.sum((Ds @ R) ** 2) / tot)
        rows.append({**base, "predictor": m, "model_dims": int(Q.shape[1]), "captured": cap,
                     "random_mean": float(np.mean(rnd)),
                     "random_p95": float(np.quantile(rnd, 0.95))})
    return rows


def summarise(A, B, B2, C) -> dict:
    out = {"a": {}, "a_diff": {}, "b": {}, "b2": {}, "c": {}}
    for set_name in ("P", "A", "V"):
        a = A[A["set"] == set_name]
        if a.empty:
            continue
        cl = "passage"
        out["a"][set_name] = {}
        for pred, g in a.groupby("predictor"):
            out["a"][set_name][pred] = {
                t: {"mean_ci": cluster_boot(g, t, cluster=cl), "per_work": per_work(g, t)}
                for t in (*TARGETS, "composite")}
        w = a.pivot_table(index=["work", "passage", "item"], columns="predictor",
                          values="composite").reset_index()
        for x, y in (("symupe", "pt"), ("symupe", "ridge"), ("pt", "ridge")):
            if x in w and y in w:
                w[f"{x}-{y}"] = w[x] - w[y]
                out["a_diff"].setdefault(set_name, {})[f"{x}-{y}"] = {
                    "mean_ci": cluster_boot(w, f"{x}-{y}"), "per_work": per_work(w, f"{x}-{y}")}
        b = B[B["set"] == set_name] if not B.empty else B
        if not b.empty:
            out["b"][set_name] = {}
            for (pred, t), g in b.groupby(["predictor", "target"]):
                out["b"][set_name][f"{pred}/{t}"] = {
                    "median_r2c": float(g["r2_centered"].median()),
                    "median_r2": float(g["r2"].median()),
                    "median_reliability": float(g["reliability"].median()),
                    "n_passages": int(len(g)),
                    "per_work_median_r2c": {k: float(v) for k, v in
                                            g.groupby("work")["r2_centered"].median().items()},
                    "per_work_median_r2": {k: float(v) for k, v in
                                           g.groupby("work")["r2"].median().items()}}
        if not B2.empty:
            b2 = B2[B2["set"] == set_name]
            if not b2.empty:
                kk = b2.drop_duplicates("passage")
                out["b2"][set_name] = {
                    "n_passages": int(len(kk)), "k_median": float(kk["k"].median()),
                    "k_dist": kk["k"].value_counts().sort_index().to_dict(),
                    "var_shared_median": float(kk["var_shared"].median())}
                for m in MODELS:
                    g = b2[b2["predictor"] == m]
                    if not g.empty:
                        out["b2"][set_name][m] = {
                            "captured_median": float(g["captured"].median()),
                            "random_mean_median": float(g["random_mean"].median()),
                            "share_above_random_p95": float((g["captured"]
                                                             > g["random_p95"]).mean())}
        c = C[C["set"] == set_name]
        if c.empty:
            continue
        scores = [col for col in c.columns
                  if col.endswith(("_ll_core", "_ll_timing", "_ll_velocity", "_ll_duration",
                                   "_ll_pedal", "_gen")) or col in ("ridge_gauss", "smooth")]
        real = c[c["kind"] == "real"].set_index("performance_id")
        out["c"][set_name] = {}
        for sc in scores:
            res = {}
            for kind in ALT_KINDS:
                alt = c[c["kind"] == kind].set_index("performance_id")
                pa = paired_auc(real[sc], alt[sc])
                d = pd.DataFrame({"v": pa})
                d["work"] = real.loc[d.index, "work"].values
                d["passage"] = real.loc[d.index, "passage"].values
                res[kind] = cluster_boot(d, "v")
            if set_name == "P":
                ext = c[c["kind"] == "ext_deadpan"]
                rows = []
                for (w_, p_), g in c[c["kind"] == "real"].groupby(["work", "passage"]):
                    e = ext[ext["passage"] == p_][sc].dropna().to_numpy()
                    h = g[sc].dropna().to_numpy()
                    if len(e) and len(h):
                        v = ((h[:, None] > e[None]) + 0.5 * (h[:, None] == e[None])).mean()
                        rows.append({"work": w_, "passage": p_, "v": float(v)})
                if rows:
                    res["ext_deadpan"] = cluster_boot(pd.DataFrame(rows), "v")
            jit = [res[k][0] for k in ALT_KINDS[:6]]
            res["jitter_mean"] = float(np.mean(jit))
            out["c"][set_name][sc] = res
        # paired model difference of the mean jitter AUC (decision tie-break), per rendition
        per = {}
        for m in ("symupe_ll_core", "pt_ll_core", "symupe_gen", "pt_gen"):
            if m not in c.columns:
                continue
            ind = []
            for kind in ALT_KINDS[:6]:
                alt = c[c["kind"] == kind].set_index("performance_id")
                ind.append(paired_auc(real[m], alt[m]).rename(kind))
            per[m] = pd.concat(ind, axis=1).mean(1)
        for x, y in (("symupe_ll_core", "pt_ll_core"), ("symupe_gen", "pt_gen")):
            if x in per and y in per:
                d = pd.DataFrame({"v": per[x] - per[y]}).dropna()
                d["work"] = real.loc[d.index, "work"].values
                d["passage"] = real.loc[d.index, "passage"].values
                out["c"][set_name][f"jitter_auc_diff:{x}-{y}"] = cluster_boot(d, "v")
    return out


if __name__ == "__main__":
    main()
