"""R-10 pre-registration checks (Mac, project env). Expert-side data only: no model output on the
fresh pieces exists or is read. Uses
  * the fresh set and the R10u development set built by job/build_set.py (expert renditions),
  * R-07's committed R10u ``h1b.csv`` (development data: frozen SyMuPe, top-p 0.95, R-07 log IOI
    formula) for the spread of per-piece model R²c.

Writes artifacts/reachability/*.csv and reachability.json; the numbers are quoted in the README.

  A. analytic K-matched oracle vs the empirical hold-out oracle (same target size n - 16);
  B. operating characteristic of the primary reading (thresholds 0.50 / 0.20 on median R²c,
     point + opposite-threshold CI rule) at the fresh set's size;
  C. H1b-axes: captured share of K' held-out experts relative to 16 (equivalent-experts scale),
     expert-as-model ratio (R10u, 16 + 16 + 18), random-subspace floor, and the operating
     characteristic of the ratio thresholds at the fresh set's size.

    OMP_NUM_THREADS=4 uv run python experiments/2026-10-05-R-10-h1b/reachability.py \\
        --r07-h1b <R-07 results/R10u/h1b.csv>
"""

from __future__ import annotations

import argparse
import json
import sys
import zlib
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "job"))
import summarize_h1b as sh  # noqa: E402

ART = HERE / "artifacts"
OUT = ART / "reachability"
SPLIT = HERE.parents[0] / "2026-09-28-R-07-symupe-finetune" / "split" / "pieces.csv"
GRID = np.round(np.arange(-0.10, 0.751, 0.05), 2)
AX_GRID = np.round(np.arange(0.1, 1.31, 0.1), 2)
REPS = 400
BOOT = 1000


def piece_matrices(set_dir: Path, min_n: int):
    man = pd.read_csv(set_dir / "manifest.csv")
    man = man[man["kind"] == "real"]
    cache: dict = {}
    for piece, g in man.groupby("passage"):
        if len(g) < min_n:
            continue
        gi = sh.load_item(set_dir / "gen_items" / (sh._slug(piece) + ".npz"))
        idx = pd.Index(np.unique(np.round(gi["score_onset_q"], 6)))
        V, T = sh.expert_matrix(set_dir, g["stem"].tolist(), idx, cache)
        keep = (np.isfinite(V).mean(0) >= 0.5) & (np.isfinite(T).mean(0) >= 0.5)
        yield piece, g["work"].iloc[0], V[:, keep], T[:, keep]


def analytic_at(X, K: int, n_target_frac: float) -> float:
    """Analytic oracle against a target of size n_j * frac (frac = (n - 16) / n)."""
    import warnings

    m = sh.nanmean0(X)
    nj = np.isfinite(X).sum(0).astype(float)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        s2 = np.nanvar(X, 0, ddof=1)
    ok = np.isfinite(m) & np.isfinite(s2) & (nj >= 2)
    mc = m[ok] - m[ok].mean()
    sig = np.sum(mc ** 2) - np.sum(s2[ok] / nj[ok])
    nt = nj[ok] * n_target_frac
    return float(1 - np.sum(s2[ok] * (1 / K + 1 / nt)) / (sig + np.sum(s2[ok] / nt)))


def part_a(sets: dict) -> pd.DataFrame:
    rows = []
    for name, d in sets.items():
        for piece, _work, V, T in piece_matrices(d, 36):
            n = len(V)
            draws = sh.holdout_draws(n, piece)
            for t, X in (("velocity", sh.center_rows(V)), ("log_ioi", T)):
                emp = np.mean([sh.r2c(sh.nanmean0(X[r]), sh.nanmean0(X[h])) for h, r in draws])
                rows.append({"set": name, "piece": piece, "target": t, "n": n, "empirical": emp,
                             "analytic_same_target": analytic_at(X, 16, (n - 16) / n),
                             "analytic_full_n": sh.analytic_oracle(X)["oracle_analytic"]})
    return pd.DataFrame(rows)


def reading_vec(point, lo, hi, cons, fals):
    out = np.full(point.shape, "inconclusive", dtype=object)
    out[(point >= cons) & (lo > fals)] = "consistent"
    out[(point <= fals) & (hi < cons)] = "falsified"
    return out


def oc(dev: np.ndarray, n: int, grid, cons, fals, scale: float = 1.0, seed: int = 0,
       log_shift: bool = False) -> pd.DataFrame:
    """P(reading) when per-piece values follow the development spread shifted to median mu."""
    rng = np.random.default_rng(seed)
    base = np.log(dev) - np.median(np.log(dev)) if log_shift else dev - np.median(dev)
    rows = []
    for mu in grid:
        x = rng.choice(base, size=(REPS, n)) * scale
        x = np.exp(np.log(mu) + x) if log_shift else mu + x
        pt = np.median(x, 1)
        bi = rng.integers(0, n, size=(REPS, BOOT, n))
        bm = np.median(np.take_along_axis(np.repeat(x[:, None, :], BOOT, 1), bi, 2), 2)
        lo, hi = np.percentile(bm, [2.5, 97.5], axis=1)
        r = reading_vec(pt, lo, hi, cons, fals)
        rows.append({"mu": mu, "scale": scale,
                     **{k: float(np.mean(r == k)) for k in ("consistent", "inconclusive",
                                                             "falsified")},
                     "ci_halfwidth": float(np.median((hi - lo) / 2))})
    return pd.DataFrame(rows)


def part_c(sets: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Equivalent-experts curve and the expert-as-model ratio."""
    eq, em = [], []
    for name, d in sets.items():
        for piece, _work, V, T in piece_matrices(d, 36):
            n = len(V)
            k, _ = sh.parallel_k(V, T)
            if k == 0:
                continue
            rng = np.random.default_rng(1 + zlib.crc32(piece.encode()) % 1_000_003)
            caps = {kk: [] for kk in (2, 4, 8, 12, 16)}
            for _ in range(10):
                p = rng.permutation(n)
                h, r = p[:16], p[16:]
                J, Vk, sv, st = sh.basis(V[r], T[r], k)
                for kk in caps:
                    caps[kk].append(sh.capture(J, Vk, V[h[:kk]], T[h[:kk]], sv, st))
            c16 = np.mean(caps[16])
            eq.append({"set": name, "piece": piece, "n": n, "k": k, "cap16": c16,
                       **{f"ratio_K{kk}": np.mean(v) / c16 for kk, v in caps.items()}})
            if n >= 50:
                ra = []
                for _ in range(10):
                    p = rng.permutation(n)
                    mdl, orc, r = p[:16], p[16:32], p[32:]
                    J, Vk, sv, st = sh.basis(V[r], T[r], k)
                    ra.append(sh.capture(J, Vk, V[mdl], T[mdl], sv, st)
                              / sh.capture(J, Vk, V[orc], T[orc], sv, st))
                em.append({"set": name, "piece": piece, "n": n, "k": k,
                           "ratio_expert_as_model": float(np.mean(ra)),
                           "ratio_single_draw_sd": float(np.std(ra))})
    return pd.DataFrame(eq), pd.DataFrame(em)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--r07-h1b", required=True, help="R-07 results/R10u/h1b.csv")
    ap.add_argument("--fresh", default=str(ART / "sets" / "fresh"))
    ap.add_argument("--dev", default=str(ART / "sets" / "r10u_dev"))
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    sets = {"fresh": Path(a.fresh), "r10u_dev": Path(a.dev)}
    res: dict = {}

    A = part_a(sets)
    A.to_csv(OUT / "a_oracle_validation.csv", index=False)
    res["A"] = {f"{s}:{t}": {"pieces": int(len(g)),
                              "median_empirical": float(g["empirical"].median()),
                              "median_analytic_same_target": float(
                                  g["analytic_same_target"].median()),
                              "median_abs_diff": float((g["empirical"]
                                                        - g["analytic_same_target"]).abs()
                                                       .median()),
                              "max_abs_diff": float((g["empirical"]
                                                     - g["analytic_same_target"]).abs().max()),
                              "corr": float(np.corrcoef(g["empirical"],
                                                        g["analytic_same_target"])[0, 1])}
                for (s, t), g in A.groupby(["set", "target"])}

    sp = pd.read_csv(SPLIT).set_index("piece_id")
    H = pd.read_csv(a.r07_h1b)
    H = H[(H["arm"] == "frozen")]
    H = H[H["passage"].map(lambda p: bool(sp.at[p, "r02"] and sp.at[p, "n_periscope_paired"]
                                          == 0) if p in sp.index else False)]
    fresh_n = pd.read_csv(ART / "prereg_experts" / "fresh" / "experts_per_piece.csv")
    n_primary = int((fresh_n["n"] >= 20).sum())
    res["B_inputs"] = {"dev_pieces": int(len(H)), "n_primary": n_primary,
                       "dev_median_velocity": float(H["r2c_velocity"].median()),
                       "dev_median_log_ioi_r07_formula": float(H["r2c_log_ioi"].median()),
                       "dev_iqr_velocity": [float(x) for x in
                                            H["r2c_velocity"].quantile([.25, .75])],
                       "dev_iqr_log_ioi": [float(x) for x in
                                           H["r2c_log_ioi"].quantile([.25, .75])]}
    B = []
    for t in ("velocity", "log_ioi"):
        for scale in (1.0, 1.5):
            d = oc(H[f"r2c_{t}"].to_numpy(float), n_primary, GRID, 0.50, 0.20, scale)
            d["target"] = t
            B.append(d)
    B = pd.concat(B)
    B.to_csv(OUT / "b_primary_oc.csv", index=False)
    res["B"] = B.round(3).to_dict("records")

    EQ, EM = part_c(sets)
    EQ.to_csv(OUT / "c_equivalent_experts.csv", index=False)
    EM.to_csv(OUT / "c_expert_as_model.csv", index=False)
    res["C_equivalent_experts_median"] = {
        s: {c: float(g[c].median()) for c in g.columns if c.startswith("ratio_K")} | {
            "pieces": int(len(g)), "median_cap16": float(g["cap16"].median())}
        for s, g in EQ.groupby("set")}
    res["C_expert_as_model"] = {
        "pieces": int(len(EM)), "median": float(EM["ratio_expert_as_model"].median()),
        "iqr": [float(x) for x in EM["ratio_expert_as_model"].quantile([.25, .75])],
        "sd": float(EM["ratio_expert_as_model"].std())}
    fx = fresh_n[(fresh_n["n"] >= 36) & (fresh_n["k"] > 0)]
    res["C_random_floor_fresh"] = {"pieces": int(len(fx)),
                                   "median_ratio": float((fx["cap_random"]
                                                          / fx["cap_oracle"]).median())}
    n_axes = int(len(fx))
    C = oc(EM["ratio_expert_as_model"].to_numpy(float), n_axes, AX_GRID, 0.80, 0.40, 1.0,
           log_shift=True)
    C2 = oc(EM["ratio_expert_as_model"].to_numpy(float), n_axes, AX_GRID, 0.80, 0.40, 1.5,
            log_shift=True)
    C["spread"], C2["spread"] = "expert_as_model", "expert_as_model"
    # realistic model spread: per-piece captured share of frozen SyMuPe on R10u (R-07 h1b.csv,
    # full-panel subspace, top-p 0.95), log scale
    cap = H["captured"].dropna().to_numpy(float)
    C3 = oc(cap, n_axes, AX_GRID, 0.80, 0.40, 1.0, log_shift=True)
    C3["spread"] = "r07_frozen_captured"
    res["C_dev_captured_log_sd"] = float(np.std(np.log(cap)))
    res["C_expert_as_model_log_sd"] = float(np.std(np.log(EM["ratio_expert_as_model"])))
    C = pd.concat([C, C2, C3])
    C.to_csv(OUT / "c_axes_oc.csv", index=False)
    res["C_axes_oc"] = C.round(3).to_dict("records")
    (OUT / "reachability.json").write_text(json.dumps(res, indent=1, default=float))
    print(json.dumps({k: v for k, v in res.items() if k not in ("B", "C_axes_oc")}, indent=1,
                     default=float))
    pd.set_option("display.width", 200)
    print(B.round(3).to_string(index=False))
    print(C.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
