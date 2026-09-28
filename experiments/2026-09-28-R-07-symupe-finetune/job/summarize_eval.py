"""R-07 evaluation summary (any env with pianolens): per-note prediction, typicality scores and
their deadpan-battery AUCs, the pre-registered pass / fail reading, and the H1b preview.

Inputs: one set dir (make_eval_items.py) and eval output dirs (symupe_eval.py / pt_eval.py):
  --arm E=DIR          fine-tuned expressive model (score/, gen/, typset/)
  --arm F=DIR          flat model (score/)            -> S-LR = S-RAW(E) - S-RAW(F)
  --arm frozen=DIR     pretrained model (score/, gen/, typset/) for the frozen reference
  --arm pt=DIR ...     any other arm: (a), S-RAW, S-DEV, H1b preview
Scores (README, "Typicality scores"): S-RAW, S-LR, S-TYP, S-DEV; baselines: smoothness,
expressiveness amount. Writes to --out: a_per_rendition.csv, scores.csv, auc.csv,
pass_fail.json, h1b.csv, summary.json.

    python summarize_eval.py --set OUT/eval_sets/P --arm E=OUT/eval/E/P --arm F=OUT/eval/F/P \\
        --arm frozen=OUT/eval/frozen/P --out OUT/results/P --primary-arm E
"""

from __future__ import annotations

import argparse
import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from pianolens.models.expression_data import load_item
from pianolens.models.expression_io import note_expression

TARGETS = ("velocity", "log_ioi", "log_art")
FIELDS = {"symupe": {"T": "TimeShift", "V": "Velocity", "D": "TimeDuration"},
          "pt": {"T": "interval", "V": "velocity", "D": "duration"}}
REQUIRED = ["deadpan", "deadpan_vel+12", "deadpan_vel-12", "deadpan_slow15", "deadpan_noise10_4",
            "half_flat_timing", "half_flat_velocity"]
NOISE_REQUIRED = ["jitT20", "jitT40", "jitV8", "jitV16"]
N_BOOT = 2000


def _slug(s: str) -> str:
    return "".join(c if c.isalnum() or c in "-." else "_" for c in s)


def corr(a, b) -> float:
    ok = np.isfinite(a) & np.isfinite(b)
    if ok.sum() < 5 or np.std(a[ok]) == 0 or np.std(b[ok]) == 0:
        return np.nan
    return float(np.corrcoef(a[ok], b[ok])[0, 1])


def feats(it: dict) -> pd.DataFrame:
    ex = note_expression(it["score_onset_q"], it["score_dur_q"], it["perf_onset_sec"],
                         it["perf_dur_sec"], it["velocity"])
    ex["score_id"] = it["score_id"]
    ex["onset_q"] = np.round(it["score_onset_q"], 6)
    return ex


def target_r(actual: pd.DataFrame, pred: pd.DataFrame, zero_if_flat: bool) -> dict:
    """R-06 (a): r per target, log IOI on one row per onset. ``zero_if_flat``: a target with
    zero variance in the rendition scores 0 instead of NaN (S-DEV)."""
    out = {}
    for t in TARGETS:
        rows = ~actual["onset_q"].duplicated() if t == "log_ioi" else slice(None)
        a = actual.loc[rows, t].to_numpy(float)
        p = pred.loc[rows.values if t == "log_ioi" else slice(None), t].to_numpy(float)
        r = corr(a, p)
        if zero_if_flat and not np.isfinite(r):
            ok = np.isfinite(a)
            if ok.sum() >= 5 and np.std(a[ok]) < 1e-9:
                r = 0.0
        out[t] = r
    out["composite"] = float(np.nanmean([out[t] for t in TARGETS])) \
        if any(np.isfinite(out[t]) for t in TARGETS) else np.nan
    return out


def gen_prediction(set_dir: Path, arm_dir: Path, passage_file: str) -> dict | None:
    g_path = set_dir / "gen_items" / passage_file
    z_path = arm_dir / "gen" / passage_file
    if not (g_path.exists() and z_path.exists()):
        return None
    g, z = load_item(g_path), load_item(z_path)
    per, curves = [], []
    for k in range(z["onset"].shape[0]):
        ex = note_expression(g["score_onset_q"], g["score_dur_q"], z["onset"][k], z["dur"][k],
                             z["vel"][k])
        ex["onset_q"] = np.round(g["score_onset_q"], 6)
        per.append(ex[list(TARGETS)].to_numpy())
        curves.append(ex.groupby("onset_q")[["velocity", "log_ioi"]].mean())
    arr = np.stack(per)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        mean = pd.DataFrame(np.nanmean(arr, 0), columns=TARGETS, index=g["score_id"])
    return {"mean": mean, "curves": curves}


def ll_fields(arm_dir: Path, name: str, model: str) -> dict | None:
    p = arm_dir / "score" / f"{name}.npz"
    if not p.exists():
        return None
    z = load_item(p)
    f = FIELDS[model]
    out = {k: float(np.nanmean(z[v])) for k, v in f.items()}
    out["core"] = float(np.nanmean(z[f["T"]] + z[f["V"]] + z[f["D"]]))
    return out


def s_typ(item_ll: dict, ref: dict, model: str) -> float:
    zs = []
    for k, v in FIELDS[model].items():
        x = np.asarray(ref[v], float)
        x = x[np.isfinite(x)]
        if len(x) < 2:
            return np.nan
        zs.append((item_ll[k] - x.mean()) / max(x.std(ddof=1), 1e-6))
    return -float(np.sqrt(np.mean(np.square(zs))))


# ------------------------------------------------------------------------------ bootstrap


def two_way_weights(df: pd.DataFrame, rng, c1: str = "passage", c2: str = "performer"):
    """Pigeonhole bootstrap weights: product of resampling multiplicities of both clusters."""
    w = np.ones(len(df))
    for c in (c1, c2):
        u, inv = np.unique(df[c].astype(str), return_inverse=True)
        m = np.bincount(rng.integers(0, len(u), len(u)), minlength=len(u))
        w = w * m[inv]
    return w


def work_mean(df: pd.DataFrame, value: str, w=None) -> float:
    w = np.ones(len(df)) if w is None else w
    vals = []
    for _, idx in df.groupby("work").indices.items():
        ww = w[idx]
        if ww.sum() > 0:
            vals.append(np.sum(ww * df[value].to_numpy()[idx]) / ww.sum())
    return float(np.mean(vals)) if vals else np.nan


def t_interval(df: pd.DataFrame, value: str) -> tuple:
    """Mean of per-work means with a t-interval (R-08a audit: report next to the bootstrap when
    there are six or fewer groups)."""
    from scipy import stats

    m = df.dropna(subset=[value]).groupby("work")[value].mean().to_numpy()
    if len(m) < 2:
        return (float(m.mean()) if len(m) else np.nan, np.nan, np.nan)
    h = stats.t.ppf(0.975, len(m) - 1) * m.std(ddof=1) / np.sqrt(len(m))
    return (float(m.mean()), float(m.mean() - h), float(m.mean() + h))


def boot_ci(df: pd.DataFrame, value: str, pooled: bool, seed: int = 0) -> tuple:
    d = df.dropna(subset=[value]).reset_index(drop=True)
    if d.empty:
        return (np.nan, np.nan, np.nan)
    rng = np.random.default_rng(seed)
    v = d[value].to_numpy(float)

    def stat(w):
        return float(np.sum(w * v) / np.sum(w)) if pooled else work_mean(d, value, w)

    point = stat(np.ones(len(d)))
    bs = []
    for _ in range(N_BOOT):
        w = two_way_weights(d, rng)
        if w.sum() > 0:
            bs.append(stat(w))
    lo, hi = np.nanpercentile(bs, [2.5, 97.5])
    return (point, float(lo), float(hi))


# ------------------------------------------------------------------------------ H1b preview


def _envelope_surrogate(D, rng):
    """R-06 / R-02 audit: phase-randomise rows, rescale columns to the real column s.d."""
    F = np.fft.rfft(D, axis=1)
    ph = rng.uniform(0, 2 * np.pi, F.shape)
    ph[:, 0] = 0
    S = np.fft.irfft(np.abs(F) * np.exp(1j * ph), n=D.shape[1], axis=1)
    S = S - S.mean(0)
    return S / (S.std(0) + 1e-12) * D.std(0)


def _fill(X):
    X = X.copy()
    cm = np.nanmean(X, 0)
    r, c = np.where(~np.isfinite(X))
    X[r, c] = cm[c]
    return X


def h1b_passage(V, T, curves, n_null: int = 100) -> dict:
    """Mean-curve centered R² (velocity centered per rendition) and shared-component capture."""
    out = {"n_perf": V.shape[0], "n_onsets": V.shape[1]}
    Vf, Tf = _fill(V), _fill(T)
    Sv = _fill(np.array([c["velocity"].to_numpy() for c in curves]))
    St = _fill(np.array([c["log_ioi"].to_numpy() for c in curves]))
    Vf = Vf - Vf.mean(1, keepdims=True)
    Sv = Sv - Sv.mean(1, keepdims=True)
    for name, E, S in (("velocity", Vf, Sv), ("log_ioi", Tf, St)):
        m, p = E.mean(0), S.mean(0)
        ok = np.isfinite(m) & np.isfinite(p)
        den = np.sum((m[ok] - m[ok].mean()) ** 2)
        out[f"r2c_{name}"] = float(1 - np.sum((m[ok] - p[ok]) ** 2) / den) if den > 0 else np.nan
        half = np.random.default_rng(0).permutation(E.shape[0])
        a, b = E[half[::2]].mean(0), E[half[1::2]].mean(0)
        r = corr(a, b)
        out[f"reliability_{name}"] = 2 * r / (1 + r) if np.isfinite(r) else np.nan
    sv, st = np.std(Vf - Vf.mean(0)), np.std(Tf - Tf.mean(0))
    J = np.hstack([(Vf - Vf.mean(0)) / sv, (Tf - Tf.mean(0)) / st])
    n, d = J.shape
    ev = np.linalg.svd(J, compute_uv=False) ** 2
    ev = ev / ev.sum()
    rng = np.random.default_rng(0)
    null = []
    for _ in range(n_null):
        S = np.hstack([_envelope_surrogate(J[:, : d // 2], rng),
                       _envelope_surrogate(J[:, d // 2:], rng)])
        e = np.linalg.svd(S, compute_uv=False) ** 2
        null.append(e / e.sum())
    q = np.quantile(np.array(null), 0.95, axis=0)
    above = ev[: len(q)] > q
    k = int(np.argmin(above)) if not above.all() else len(q)
    out.update(k=k, var_shared=float(ev[:k].sum()))
    if k == 0:
        return out
    _, _, Vt = np.linalg.svd(J, full_matrices=False)
    Ds = J @ Vt[:k].T @ Vt[:k]
    tot = np.sum(Ds ** 2)
    M = np.hstack([(Sv - Sv.mean(0)) / sv, (St - St.mean(0)) / st])
    _, s, Wt = np.linalg.svd(M, full_matrices=False)
    Q = Wt[s > 1e-9 * s.max()].T
    rnd = [np.sum((Ds @ np.linalg.qr(rng.normal(size=(d, Q.shape[1])))[0]) ** 2) / tot
           for _ in range(200)]
    out.update(model_dims=int(Q.shape[1]), captured=float(np.sum((Ds @ Q) ** 2) / tot),
               random_mean=float(np.mean(rnd)), random_p95=float(np.quantile(rnd, 0.95)))
    return out


# ------------------------------------------------------------------------------ main


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", required=True)
    ap.add_argument("--arm", action="append", default=[], help="name=dir; name 'pt*' = PT")
    ap.add_argument("--out", required=True)
    ap.add_argument("--primary-arm", default="E")
    ap.add_argument("--min-h1b-renditions", type=int, default=20)
    a = ap.parse_args(argv)
    set_dir, out = Path(a.set), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    arms = dict(x.split("=", 1) for x in a.arm)
    model_of = {k: ("pt" if k.startswith("pt") else "symupe") for k in arms}
    man = pd.read_csv(set_dir / "manifest.csv")
    real = man[man["kind"] == "real"]

    # (a) + S-DEV per rendition and per variant item
    a_rows, s_rows = [], []
    feats_cache: dict[str, pd.DataFrame] = {}

    def fx(stem_kind: str) -> pd.DataFrame:
        if stem_kind not in feats_cache:
            feats_cache[stem_kind] = feats(load_item(set_dir / "items" / f"{stem_kind}.npz"))
        return feats_cache[stem_kind]

    for arm, adir in arms.items():
        adir = Path(adir)
        preds = {}
        for passage in sorted(man["passage"].unique()):
            fname = _slug(passage) + ".npz"
            preds[passage] = gen_prediction(set_dir, adir, fname)
        for r in man.itertuples():
            name = f"{r.stem}__{r.kind}"
            if not (set_dir / "items" / f"{name}.npz").exists():
                continue
            pr = preds.get(r.passage)
            rec = {"arm": arm, "stem": r.stem, "kind": r.kind, "passage": r.passage,
                   "work": r.work, "performer": r.performer}
            if pr is not None:
                ex = fx(name)
                pred = pr["mean"].reindex(ex["score_id"])
                rt = target_r(ex, pred, zero_if_flat=True)
                rec["S-DEV"] = rt["composite"]
                if r.kind == "real":
                    a_rows.append({**rec, **target_r(ex, pred, zero_if_flat=False)})
            ll = ll_fields(adir, name, model_of[arm])
            if ll is not None:
                rec["S-RAW"] = ll["core"]
                rec.update({f"ll_{k}": v for k, v in ll.items() if k != "core"})
                tp = adir / "typset" / f"{r.stem}__real.npz"
                if tp.exists():
                    rec["S-TYP"] = s_typ(ll, load_item(tp), model_of[arm])
            ex = fx(name)
            dv = np.diff(ex["velocity"].to_numpy(float))
            dt = np.diff(ex.loc[~ex["onset_q"].duplicated(), "log_ioi"].to_numpy(float))
            rec["_dv2"], rec["_dt2"] = float(np.nanmean(dv ** 2)), float(np.nanmean(dt ** 2))
            rec["_sd"] = [float(np.nanstd(ex[t])) for t in TARGETS]
            s_rows.append(rec)
    A = pd.DataFrame(a_rows)
    S = pd.DataFrame(s_rows)
    if "F" in arms and a.primary_arm in arms and "S-RAW" in S:
        f = S[S["arm"] == "F"].set_index(["stem", "kind"])["S-RAW"]
        e = S["arm"] == a.primary_arm
        S.loc[e, "S-LR"] = S.loc[e, "S-RAW"].to_numpy() - f.reindex(
            pd.MultiIndex.from_frame(S.loc[e, ["stem", "kind"]])).to_numpy()
    if not S.empty:  # baselines (model-free), computed once per item
        rr = S[S["kind"] == "real"]
        sv, st = np.nanmedian(rr["_dv2"]), np.nanmedian(rr["_dt2"])
        S["B-smooth"] = -(S["_dv2"] / sv + S["_dt2"] / st)
        med = np.nanmedian(np.array(rr["_sd"].tolist()), 0)
        S["B-amount"] = [float(np.nanmean(np.array(x) / med)) for x in S["_sd"]]
        S = S.drop(columns=["_dv2", "_dt2", "_sd"])
    A.to_csv(out / "a_per_rendition.csv", index=False)
    S.to_csv(out / "scores.csv", index=False)

    summary: dict = {"set": str(set_dir), "arms": arms, "n_real": int(len(real)),
                     "n_passages": int(real["passage"].nunique()),
                     "n_works": int(real["work"].nunique())}
    # (a) per arm and paired differences vs frozen
    a_sum = {}
    for arm, g in A.groupby("arm"):
        a_sum[arm] = {t: boot_ci(g, t, pooled=False) for t in (*TARGETS, "composite")}
        a_sum[arm]["per_work_composite"] = g.groupby("work")["composite"].mean().to_dict()
        if g["work"].nunique() <= 6:
            a_sum[arm]["t_interval_composite"] = t_interval(g, "composite")
    if "frozen" in arms:
        base = A[A["arm"] == "frozen"].set_index("stem")
        for arm in arms:
            if arm == "frozen":
                continue
            g = A[A["arm"] == arm].set_index("stem")
            j = g.join(base[list(TARGETS) + ["composite"]], rsuffix="_frozen", how="inner")
            for t in (*TARGETS, "composite"):
                j[f"d_{t}"] = j[t] - j[f"{t}_frozen"]
            j = j.reset_index()
            a_sum[f"{arm}-frozen"] = {t: boot_ci(j, f"d_{t}", pooled=False)
                                      for t in (*TARGETS, "composite")}
            a_sum[f"{arm}-frozen"]["per_work_composite"] = \
                j.groupby("work")["d_composite"].mean().to_dict()
            if j["work"].nunique() <= 6:
                a_sum[f"{arm}-frozen"]["t_interval_composite"] = t_interval(j, "d_composite")
    summary["a"] = a_sum

    # typicality AUCs
    auc_rows = []
    score_cols = [c for c in ("S-RAW", "S-LR", "S-TYP", "S-DEV", "B-smooth", "B-amount")
                  if c in S]
    for arm, g in S.groupby("arm"):
        rl = g[g["kind"] == "real"].set_index("stem")
        for kind in sorted(set(g["kind"]) - {"real"}):
            alt = g[g["kind"] == kind]
            for sc in score_cols:
                if sc.startswith("B-") and arm != a.primary_arm:
                    continue
                if kind == "ext_deadpan":  # all human x Score pairs within a passage
                    pr = []
                    for p, gp in alt.groupby("passage"):
                        h = rl[rl["passage"] == p]
                        for x in gp[sc].dropna():
                            for st_, hv in h[sc].dropna().items():
                                pr.append({"stem": st_, "passage": p,
                                           "work": h.at[st_, "work"],
                                           "performer": h.at[st_, "performer"],
                                           "ind": float(hv > x) + 0.5 * float(hv == x)})
                    d = pd.DataFrame(pr)
                else:
                    j = alt.set_index("stem")[[sc]].join(rl[[sc, "passage", "work", "performer"]],
                                                         rsuffix="_real", how="inner")
                    j = j.dropna(subset=[sc, f"{sc}_real"])
                    j["ind"] = (j[f"{sc}_real"] > j[sc]).astype(float) \
                        + 0.5 * (j[f"{sc}_real"] == j[sc]).astype(float)
                    d = j.reset_index()
                if d.empty:
                    continue
                pt, lo, hi = boot_ci(d, "ind", pooled=True)
                auc_rows.append({"arm": arm, "score": sc, "variant": kind, "auc": pt, "lo": lo,
                                 "hi": hi, "n": len(d),
                                 "min_work_auc": float(d.groupby("work")["ind"].mean().min())})
    AUC = pd.DataFrame(auc_rows)
    AUC.to_csv(out / "auc.csv", index=False)

    # pre-registered reading (applied per score on this set; the set-level combination of P and
    # V is done in the README)
    pf = {}
    for (arm, sc), g in AUC.groupby(["arm", "score"]) if not AUC.empty else []:
        g = g.set_index("variant")

        def ok(v, need_ci=True, g=g):
            if v not in g.index:
                return None
            r = g.loc[v]
            return bool(r["auc"] >= 0.75 and (r["lo"] > 0.5 if need_ci else True)
                        and r["min_work_auc"] >= 0.5)

        req = {v: ok(v) for v in REQUIRED}
        noise = {v: ok(v) for v in NOISE_REQUIRED}
        point = {v: (bool(g.loc[v, "auc"] >= 0.75) if v in g.index else None) for v in REQUIRED}
        pf[f"{arm}:{sc}"] = {"required_ci": req, "noise_ci": noise, "required_point": point,
                             "R1_pass": all(x is True for x in req.values()),
                             "R2_pass": all(x is True for x in noise.values()),
                             "R3_point_pass": all(x is True for x in point.values())}
    (out / "pass_fail.json").write_text(json.dumps(pf, indent=1))
    summary["pass_fail"] = pf

    # H1b preview: passages with enough real renditions
    h_rows = []
    for arm, adir in arms.items():
        for passage, g in real.groupby("passage"):
            if len(g) < a.min_h1b_renditions:
                continue
            fname = _slug(passage) + ".npz"
            pr = gen_prediction(set_dir, Path(adir), fname)
            if pr is None:
                continue
            gi = load_item(set_dir / "gen_items" / fname)
            idx = pd.Index(np.unique(np.round(gi["score_onset_q"], 6)))
            V, T = [], []
            for st_ in g["stem"]:
                c = fx(f"{st_}__real").groupby("onset_q")[["velocity", "log_ioi"]].mean()
                c = c.reindex(idx)
                V.append(c["velocity"].to_numpy())
                T.append(c["log_ioi"].to_numpy())
            V, T = np.array(V), np.array(T)
            keep = (np.isfinite(V).mean(0) >= 0.5) & (np.isfinite(T).mean(0) >= 0.5)
            curves = [c.reindex(idx)[keep] for c in pr["curves"]]
            h_rows.append({"arm": arm, "passage": passage, "work": g["work"].iloc[0],
                           **h1b_passage(V[:, keep], T[:, keep], curves)})
    H = pd.DataFrame(h_rows)
    H.to_csv(out / "h1b.csv", index=False)
    if not H.empty:
        summary["h1b"] = {arm: {c: float(g[c].median()) for c in g.columns
                                if c.startswith(("r2c", "reliability", "captured", "random", "k"))
                                and g[c].notna().any()}
                          for arm, g in H.groupby("arm")}
    (out / "summary.json").write_text(json.dumps(summary, indent=1, default=float))
    print(json.dumps(summary, indent=1, default=float)[:4000])


if __name__ == "__main__":
    main()
