"""R-09 analysis: coherence vs MAJEPPA skill level, context-matched (pre-registered in README.md).

    OMP_NUM_THREADS=1 uv run python \
        experiments/2026-09-28-R-09-coherence-skill/analyze.py --boot 2000

Reads ``artifacts/coherence.csv`` (build.py) and ``artifacts/noise_pairs.csv`` (noise_floor.py).
Writes ``artifacts/{counts,context_by_level,effects,level_means,difficulty,lpo,noise_floor,
verdict}.csv`` and prints the tables.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import numpy as np
import pandas as pd

from pianolens.eval import bootstrap_indices
from pianolens.eval.metrics import pairwise_accuracy, spearman
from pianolens.eval.splits import group_kfold

HERE = Path(__file__).resolve().parent
ART = HERE / "artifacts"
RANK = {"child_beginner": 1, "adult_beginner": 2, "adult_intermediate": 3,
        "child_professional": 4, "piano_teacher": 5, "virtuoso": 6}  # fmt: skip
G3 = {"beginner": 0, "intermediate": 1, "advanced": 2}
PRIMARY = {"articulation": "articulation_r2_no_markings", "timing": "timing_r2_no_markings"}
SECONDARY = {"concave_excess": "pts_concave_excess", "velocity": "velocity_r2_no_markings"}
OUTCOMES = {**PRIMARY, **SECONDARY}
SESOI = {"articulation": 0.01, "timing": 0.01, "concave_excess": 0.02, "velocity": 0.01}
MATCHED = ("practice", "performance")


# ------------------------------------------------------------------------------ data


def load() -> pd.DataFrame:
    d = pd.read_csv(ART / "coherence.csv")
    d["rank6"] = d["expertise_level"].map(RANK)
    d["g3"] = d["skill_group"].map(G3)
    d["log_rate"] = np.log(d["note_rate_nps"])
    d["log_dur"] = np.log(d["duration_s"])
    return d


def gate(d: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Trusted alignment + quantized score; per-outcome validity masks. Returns (gated, counts)."""
    rows = []
    trusted = d[~d["alignment_suspect"].astype(bool)]
    quant = trusted[trusted["score_offgrid_share"] <= 0.10]
    g = quant.copy()
    for name, col in OUTCOMES.items():
        if name == "concave_excess":
            ok = (g["pts_n_phrases"] >= 4) & g[col].notna()
        else:
            ch = col.split("_r2")[0]
            ok = (g[f"{ch}_n_blocks"] >= 3) & (g[f"{ch}_n"] >= 20) & g[col].notna()
        g[f"ok_{name}"] = ok
    for lev in [*RANK, "total"]:
        sel = (lambda x: x) if lev == "total" else (lambda x, lev=lev: x[x.expertise_level == lev])
        r = {"level": lev, "selected": len(sel(d)), "trusted_alignment": len(sel(trusted)),
             "quantized_score": len(sel(quant))}
        for name in OUTCOMES:
            r[f"valid_{name}"] = int(sel(g)[f"ok_{name}"].sum())
        rows.append(r)
    return g, pd.DataFrame(rows)


# ------------------------------------------------------------------------------ FE OLS


def _demean(a: np.ndarray, codes: np.ndarray, n: int) -> np.ndarray:
    cnt = np.bincount(codes, minlength=n).astype(float)
    if a.ndim == 1:
        return a - (np.bincount(codes, a, n) / cnt)[codes]
    return np.column_stack([a[:, j] - (np.bincount(codes, a[:, j], n) / cnt)[codes]
                            for j in range(a.shape[1])])


def design(df: pd.DataFrame, skill: str, ctx_fe: bool, covs: bool) -> tuple[np.ndarray, list[str]]:
    cols, names = [], []
    if skill == "rank6":
        cols.append(df["rank6"].to_numpy(float))
        names.append("b_rank")
    elif skill == "g3trend":
        cols.append(df["g3"].to_numpy(float))
        names.append("b_g3")
    elif skill == "g3dummies":
        for k in ("intermediate", "advanced"):
            cols.append((df["skill_group"] == k).to_numpy(float))
            names.append(f"d_{k}")
    elif skill == "levels":
        levs = sorted(df["expertise_level"].unique(), key=RANK.get)
        for k in levs[1:]:
            cols.append((df["expertise_level"] == k).to_numpy(float))
            names.append(f"d_{k}")
    if ctx_fe:
        cts = sorted(df["recording_type"].unique())
        for k in cts[1:]:
            cols.append((df["recording_type"] == k).to_numpy(float))
            names.append(f"ctx_{k}")
    if covs:
        cols += [df["log_rate"].to_numpy(float), df["log_dur"].to_numpy(float)]
        names += ["g_log_rate", "g_log_dur"]
    return np.column_stack(cols), names


def fe_ols(y: np.ndarray, X: np.ndarray, piece: np.ndarray) -> np.ndarray:
    codes, n = np.unique(piece, return_inverse=True)[1], len(np.unique(piece))
    yd, Xd = _demean(y, codes, n), _demean(X, codes, n)
    return np.linalg.lstsq(Xd, yd, rcond=None)[0]


def with_multi_level_pieces(df: pd.DataFrame, level_col: str = "expertise_level") -> pd.DataFrame:
    k = df.groupby("piece_id")[level_col].nunique()
    return df[df["piece_id"].isin(k[k >= 2].index)]


def estimate(df: pd.DataFrame, ycol: str, skill: str, ctx_fe: bool, covs: bool, n_boot: int,
             seed: int = 0) -> dict:
    X, names = design(df, skill, ctx_fe, covs)
    y = df[ycol].to_numpy(float)
    piece = df["piece_id"].to_numpy()
    est = fe_ols(y, X, piece)
    boots = np.array([fe_ols(y[i], X[i], piece[i])
                      for i in bootstrap_indices(df["recording_id"].to_numpy(), len(df), n_boot,
                                                 seed)])  # fmt: skip
    out = {"n": len(df), "n_pieces": df["piece_id"].nunique(),
           "n_recordings": df["recording_id"].nunique()}
    for j, nm in enumerate(names):
        if nm.startswith("ctx_"):
            continue
        b = boots[:, j]
        out[nm] = est[j]
        out[f"{nm}_lo95"], out[f"{nm}_hi95"] = np.percentile(b, [2.5, 97.5])
        out[f"{nm}_lo975"], out[f"{nm}_hi975"] = np.percentile(b, [1.25, 98.75])
    return out


# ------------------------------------------------------------------------------ analyses


def samples(g: pd.DataFrame, ok: str) -> dict[str, tuple[pd.DataFrame, bool]]:
    v = g[g[ok]]
    m = v[v["recording_type"].isin(MATCHED)]
    return {
        "A1_matched": (with_multi_level_pieces(m), True),
        "A1p_practice": (with_multi_level_pieces(m[m.recording_type == "practice"]), False),
        "A1f_performance": (with_multi_level_pieces(m[m.recording_type == "performance"]), False),
        "S5_matched_levels1-4": (with_multi_level_pieces(m[m.rank6 <= 4]), True),
        "A2_pooled_ctx_fe": (with_multi_level_pieces(v[v.recording_type != "fast_demo"]), True),
        "A3_pooled_no_ctx": (with_multi_level_pieces(v), False),
    }


def run_effects(g: pd.DataFrame, n_boot: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows, lm = [], []
    for name, col in OUTCOMES.items():
        for sname, (df, ctx) in samples(g, f"ok_{name}").items():
            if df["piece_id"].nunique() < 3:
                continue
            for covs in (True, False):
                r = estimate(df, col, "rank6", ctx, covs, n_boot)
                rows.append({"outcome": name, "analysis": sname, "coding": "rank6",
                             "covariates": covs, "y_mean": df[col].mean(),
                             "y_sd": df[col].std(), **r})
            for coding in ("g3trend", "g3dummies"):
                d3 = with_multi_level_pieces(df, "skill_group")
                if d3["piece_id"].nunique() < 3:
                    continue
                r = estimate(d3, col, coding, ctx, True, n_boot)
                rows.append({"outcome": name, "analysis": sname, "coding": coding,
                             "covariates": True, **r})
            if sname in ("A1_matched", "A2_pooled_ctx_fe", "A3_pooled_no_ctx"):
                r = estimate(df, col, "levels", ctx, True, n_boot)
                for k, v in r.items():
                    if k.startswith("d_") and not k.endswith(("lo95", "hi95", "lo975", "hi975")):
                        lev = k[2:]
                        lm.append({"outcome": name, "analysis": sname, "level": lev,
                                   "n_level": int((df.expertise_level == lev).sum()),
                                   "diff_vs_lowest": v, "lo95": r[f"{k}_lo95"],
                                   "hi95": r[f"{k}_hi95"]})
                raw = df.groupby("expertise_level")[col].agg(["size", "mean", "median"])
                for lev, rr in raw.iterrows():
                    lm.append({"outcome": name, "analysis": sname, "level": lev,
                               "n_level": int(rr["size"]), "raw_mean": rr["mean"],
                               "raw_median": rr["median"]})
    return pd.DataFrame(rows), pd.DataFrame(lm)


def verdict(eff: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for name in OUTCOMES:
        e = eff[(eff.outcome == name) & (eff.analysis == "A1_matched")]
        r = e[(e.coding == "rank6") & e.covariates].iloc[0]
        d = e[e.coding == "g3dummies"].iloc[0]
        lo, hi = (r["b_rank_lo975"], r["b_rank_hi975"]) if name in PRIMARY else (
            r["b_rank_lo95"], r["b_rank_hi95"])
        ordered = 0 <= d["d_intermediate"] <= d["d_advanced"]
        if lo > 0 and ordered:
            v = "supported"
        elif hi < SESOI[name]:
            v = "falsified (CI below SESOI)" if lo >= 0 or hi >= 0 else "falsified (CI below 0)"
        else:
            v = "inconclusive"
        rows.append({"outcome": name, "role": "primary" if name in PRIMARY else "secondary",
                     "b_rank": r["b_rank"], "ci_lo": lo, "ci_hi": hi,
                     "ci_level": 0.975 if name in PRIMARY else 0.95, "sesoi": SESOI[name],
                     "d_intermediate": d["d_intermediate"], "d_advanced": d["d_advanced"],
                     "g3_ordered": ordered, "verdict": v})
    return pd.DataFrame(rows)


# ------------------------------------------------------------------------------ difficulty


_CAT = re.compile(r"\b(op|opus|bwv|kv|k|hob|d|woo|no|nr|n)\.?\s*(\d+[a-z]?)", re.I)


def _key(composer: str, title: str, surname_last: bool) -> tuple | None:
    """(surname, catalogue tokens); MAJEPPA names end in the surname, PSyllabus ones start
    with it ("Bach J.S.")."""
    if not isinstance(composer, str) or not isinstance(title, str) or not composer.split():
        return None
    parts = composer.split()
    sur = re.sub(r"[^a-z]", "", (parts[-1] if surname_last else parts[0]).lower())
    toks = []
    for k, v in _CAT.findall(title):
        k = k.lower()
        k = {"opus": "op", "kv": "k", "nr": "no", "n": "no"}.get(k, k)
        toks.append(f"{k}{v.lower()}")
    if not toks or not any(t.startswith(("op", "bwv", "k", "hob", "d", "woo")) for t in toks):
        return None
    return sur, tuple(toks)


def difficulty_join(g: pd.DataFrame) -> pd.Series:
    from pianolens.data.psyllabus import psyllabus_index

    ps = psyllabus_index()
    ps["key"] = [_key(c, t, False) for c, t in zip(ps["composer"], ps["title"], strict=True)]
    diff = ps.dropna(subset=["key"]).groupby("key")["difficulty"].median()
    keys = [_key(c, t, True) for c, t in zip(g["composer"], g["piece_title"], strict=True)]
    return pd.Series([diff.get(k, np.nan) if k else np.nan for k in keys], index=g.index)


def run_difficulty(g: pd.DataFrame, n_boot: int) -> pd.DataFrame:
    g = g.copy()
    g["difficulty"] = difficulty_join(g)
    rows = [{"what": "join coverage (gated performances)", "value": g["difficulty"].notna().mean(),
             "n": int(g["difficulty"].notna().sum()),
             "n_pieces": int(g.loc[g["difficulty"].notna(), "piece_id"].nunique())}]
    for name, col in PRIMARY.items():
        v = g[g[f"ok_{name}"] & g["recording_type"].isin(MATCHED) & g["difficulty"].notna()]
        v = with_multi_level_pieces(v)
        if v["piece_id"].nunique() < 5:
            rows.append({"what": f"{name}: too few joined pieces", "n": len(v)})
            continue
        # (i) no piece FE: constant "piece" -> intercept only; context FE + rank + covs + difficulty
        X, names = design(v, "rank6", True, True)
        X = np.column_stack([X, v["difficulty"].to_numpy(float)])
        names = [*names, "g_difficulty"]
        y = v[col].to_numpy(float)
        one = np.zeros(len(v), int)
        est = fe_ols(y, X, one)
        bs = np.array([fe_ols(y[i], X[i], one[i]) for i in
                       bootstrap_indices(v["recording_id"].to_numpy(), len(v), n_boot, 0)])
        for nm in ("b_rank", "g_difficulty"):
            j = names.index(nm)
            lo, hi = np.percentile(bs[:, j], [2.5, 97.5])
            rows.append({"what": f"{name}: no piece FE, {nm}", "value": est[j], "lo95": lo,
                         "hi95": hi, "n": len(v), "n_pieces": v["piece_id"].nunique()})
        # (ii) piece FE + rank x difficulty (centered)
        X, names = design(v, "rank6", True, True)
        dc = v["difficulty"].to_numpy(float) - v["difficulty"].mean()
        X = np.column_stack([X, v["rank6"].to_numpy(float) * dc])
        names = [*names, "b_rank_x_difficulty"]
        pc = v["piece_id"].to_numpy()
        est = fe_ols(y, X, pc)
        bs = np.array([fe_ols(y[i], X[i], pc[i]) for i in
                       bootstrap_indices(v["recording_id"].to_numpy(), len(v), n_boot, 0)])
        for nm in ("b_rank", "b_rank_x_difficulty"):
            j = names.index(nm)
            lo, hi = np.percentile(bs[:, j], [2.5, 97.5])
            rows.append({"what": f"{name}: piece FE, {nm}", "value": est[j], "lo95": lo,
                         "hi95": hi, "n": len(v), "n_pieces": v["piece_id"].nunique()})
    return pd.DataFrame(rows)


# ------------------------------------------------------------------------------ S8 LPO


def _ridge_fit(X: np.ndarray, y: np.ndarray, alpha: float) -> tuple[np.ndarray, ...]:
    mu, sd = X.mean(0), X.std(0)
    sd[sd == 0] = 1
    Z = (X - mu) / sd
    w = np.linalg.solve(Z.T @ Z + alpha * len(y) * np.eye(Z.shape[1]), Z.T @ (y - y.mean()))
    return w, mu, sd, y.mean()


def _ridge_pred(m: tuple, X: np.ndarray) -> np.ndarray:
    w, mu, sd, ym = m
    return ((X - mu) / sd) @ w + ym


def _features(df: pd.DataFrame, train: np.ndarray, with_coh: bool) -> np.ndarray:
    cols = [df["log_rate"].to_numpy(float), df["log_dur"].to_numpy(float),
            (df["recording_type"] == "practice").to_numpy(float)]
    if with_coh:
        for name, c in (("articulation", PRIMARY["articulation"]), ("timing", PRIMARY["timing"]),
                        ("concave_excess", SECONDARY["concave_excess"])):
            x = df[c].where(df[f"ok_{name}"]).to_numpy(float)
            miss = ~np.isfinite(x)
            med = np.nanmedian(x[train]) if np.isfinite(x[train]).any() else 0.0
            cols += [np.where(miss, med, x), miss.astype(float)]
    return np.column_stack(cols)


def run_lpo(g: pd.DataFrame, n_boot: int) -> pd.DataFrame:
    df = g[g["recording_type"].isin(MATCHED)
           & (g["ok_articulation"] | g["ok_timing"])].reset_index(drop=True)
    df = with_multi_level_pieces(df).reset_index(drop=True)
    y = df["rank6"].to_numpy(float)
    pieces = df["piece_id"].to_numpy()
    alphas = np.logspace(-3, 2, 11)
    preds = {}
    for with_coh in (False, True):
        oof = np.full(len(df), np.nan)
        for tr, te in group_kfold(pieces, 5, seed=0):
            inner = group_kfold(pieces[tr], 4, seed=0)
            err = []
            for a in alphas:
                e = 0.0
                for itr, ite in inner:
                    Xi = _features(df.iloc[tr], itr, with_coh)
                    m = _ridge_fit(Xi[itr], y[tr][itr], a)
                    e += float(np.sum((_ridge_pred(m, Xi[ite]) - y[tr][ite]) ** 2))
                err.append(e)
            a = alphas[int(np.argmin(err))]
            X = _features(df, tr, with_coh)
            oof[te] = _ridge_pred(_ridge_fit(X[tr], y[tr], a), X[te])
        preds["coherence" if with_coh else "covariates"] = oof
    rows = []
    bi = _labelled_boot(pieces, n_boot, 0)
    for nm, p in preds.items():
        sp = [spearman(y[i], p[i]) for i, _ in bi]
        pa = [pairwise_accuracy(y[i], p[i], groups=lab) for i, lab in bi]
        rows.append({"model": nm, "n": len(df), "n_pieces": len(set(pieces)),
                     "spearman": spearman(y, p), "sp_lo": np.percentile(sp, 2.5),
                     "sp_hi": np.percentile(sp, 97.5),
                     "wp_pair_acc": pairwise_accuracy(y, p, groups=pieces),
                     "pa_lo": np.percentile(pa, 2.5), "pa_hi": np.percentile(pa, 97.5)})
    d_sp = [spearman(y[i], preds["coherence"][i]) - spearman(y[i], preds["covariates"][i])
            for i, _ in bi]
    d_pa = [pairwise_accuracy(y[i], preds["coherence"][i], groups=lab)
            - pairwise_accuracy(y[i], preds["covariates"][i], groups=lab) for i, lab in bi]
    rows.append({"model": "coherence - covariates", "n": len(df),
                 "spearman": rows[1]["spearman"] - rows[0]["spearman"],
                 "sp_lo": np.percentile(d_sp, 2.5), "sp_hi": np.percentile(d_sp, 97.5),
                 "wp_pair_acc": rows[1]["wp_pair_acc"] - rows[0]["wp_pair_acc"],
                 "pa_lo": np.percentile(d_pa, 2.5), "pa_hi": np.percentile(d_pa, 97.5)})
    return pd.DataFrame(rows)


def _labelled_boot(groups: np.ndarray, n_boot: int, seed: int
                   ) -> list[tuple[np.ndarray, np.ndarray]]:
    """Cluster bootstrap by group; each resampled copy of a group gets its own label."""
    uniq, inv = np.unique(groups, return_inverse=True)
    members = [np.flatnonzero(inv == k) for k in range(len(uniq))]
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(n_boot):
        pick = rng.integers(0, len(uniq), len(uniq))
        idx = np.concatenate([members[k] for k in pick])
        lab = np.concatenate([np.full(len(members[k]), j) for j, k in enumerate(pick)])
        out.append((idx, lab))
    return out


# ------------------------------------------------------------------------------ noise floor


def run_noise() -> pd.DataFrame:
    p = ART / "noise_pairs.csv"
    if not p.exists():
        return pd.DataFrame()
    d = pd.read_csv(p)
    rows = []
    for name, col in OUTCOMES.items():
        for model, g in [*d.groupby("capture_model"), ("all", d)]:
            if name == "concave_excess":
                ok = (g["disk_pts_n_phrases"] >= 4) & (g["trans_pts_n_phrases"] >= 4)
            else:
                ch = col.split("_r2")[0]
                ok = (g[f"disk_{ch}_n_blocks"] >= 3) & (g[f"trans_{ch}_n_blocks"] >= 3)
            g = g[ok & g[f"disk_{col}"].notna() & g[f"trans_{col}"].notna()]
            if len(g) == 0:
                continue
            a, b = g[f"disk_{col}"].to_numpy(), g[f"trans_{col}"].to_numpy()
            diff = b - a
            rows.append({"outcome": name, "transcriber": model, "n_pairs": len(g),
                         "disk_median": np.median(a), "trans_median": np.median(b),
                         "median_diff": np.median(diff), "mean_diff": diff.mean(),
                         "median_abs_diff": np.median(np.abs(diff)),
                         "spearman_disk_trans": spearman(a, b) if len(g) >= 4 else np.nan,
                         "share_absdiff_gt_5xSESOI": float(np.mean(np.abs(diff)
                                                                   > 5 * SESOI[name]))})
    return pd.DataFrame(rows)


# ------------------------------------------------------------------------------ post hoc


def run_posthoc(g: pd.DataFrame, n_boot: int) -> pd.DataFrame:
    """POST HOC (added after the pre-registered results were seen; not part of the verdict).

    8-bar Czerny Op. 101 etudes pass ``n_blocks >= 3`` because their bars are numbered 0-8
    (three 4-bar blocks, one of them a single bar) and give R² down to -80 (velocity). Variants:
    (a) also require >= 12 distinct score bars; (b) (a) + R² floored at -1; (c) (a) + outcome
    replaced by its within-piece percentile rank (0-1), a scale-free check.
    """
    rows = []
    g = g[g["n_score_bars"] >= 12].copy()
    for name, col in OUTCOMES.items():
        for variant in ("a_min12bars", "b_floor_-1", "c_within_piece_rank"):
            h = g.copy()
            if variant != "a_min12bars" and name != "concave_excess":
                h[col] = h[col].clip(lower=-1)
            for sname, (df, ctx) in samples(h, f"ok_{name}").items():
                if sname not in ("A1_matched", "A2_pooled_ctx_fe", "A3_pooled_no_ctx"):
                    continue
                df = df.copy()
                if variant == "c_within_piece_rank":
                    df[col] = df.groupby("piece_id")[col].rank(pct=True)
                r = estimate(df, col, "rank6", ctx, True, n_boot)
                d3 = with_multi_level_pieces(df, "skill_group")
                r3 = estimate(d3, col, "g3dummies", ctx, True, n_boot)
                rows.append({"outcome": name, "variant": variant, "analysis": sname,
                             **{k: v for k, v in r.items() if k.startswith(("n", "b_rank"))},
                             "d_intermediate": r3["d_intermediate"],
                             "d_advanced": r3["d_advanced"],
                             "d_advanced_lo95": r3["d_advanced_lo95"],
                             "d_advanced_hi95": r3["d_advanced_hi95"]})
    return pd.DataFrame(rows)


# ------------------------------------------------------------------------------ main


def main() -> None:
    a = argparse.ArgumentParser()
    a.add_argument("--boot", type=int, default=2000)
    args = a.parse_args()
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 40)
    d = load()
    g, counts = gate(d)
    counts.to_csv(ART / "counts.csv", index=False)
    print("counts per gate:\n", counts.to_string(index=False))
    ctx = pd.crosstab(g["expertise_level"], g["recording_type"]).reindex(list(RANK))
    ctx.to_csv(ART / "context_by_level.csv")
    print("\ngated sample, level x context:\n", ctx.to_string())
    eff, lm = run_effects(g, args.boot)
    eff.to_csv(ART / "effects.csv", index=False)
    lm.to_csv(ART / "level_means.csv", index=False)
    cols = ["outcome", "analysis", "coding", "covariates", "n", "n_pieces", "b_rank",
            "b_rank_lo95", "b_rank_hi95", "b_rank_lo975", "b_rank_hi975", "b_g3", "b_g3_lo95",
            "b_g3_hi95", "d_intermediate", "d_advanced", "d_advanced_lo95", "d_advanced_hi95"]
    print("\neffects:\n", eff[[c for c in cols if c in eff]].round(4).to_string(index=False))
    print("\nlevel means:\n", lm.round(4).to_string(index=False))
    v = verdict(eff)
    v.to_csv(ART / "verdict.csv", index=False)
    print("\nverdict:\n", v.round(4).to_string(index=False))
    dif = run_difficulty(g, args.boot)
    dif.to_csv(ART / "difficulty.csv", index=False)
    print("\ndifficulty:\n", dif.round(4).to_string(index=False))
    lpo = run_lpo(g, args.boot)
    lpo.to_csv(ART / "lpo.csv", index=False)
    print("\nleave-piece-out skill-rank prediction:\n", lpo.round(4).to_string(index=False))
    ph = run_posthoc(g, args.boot)
    ph.to_csv(ART / "effects_posthoc.csv", index=False)
    print("\nPOST HOC robustness (not in the verdict):\n", ph.round(4).to_string(index=False))
    nz = run_noise()
    nz.to_csv(ART / "noise_floor.csv", index=False)
    print("\nnoise floor:\n", nz.round(4).to_string(index=False))


if __name__ == "__main__":
    main()
