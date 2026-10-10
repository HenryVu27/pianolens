"""R-10 audit checks (eval-auditor, 2026-10-06). Mac only; reads the committed box results.

Recomputes the headline from `results_box/results/*/arms_per_piece.csv` and adds the audit's
post-hoc, non-deciding analyses:

  1. reproduction of every arm median / work-cluster CI and the reading;
  2. shape vs amplitude: R²c = 2 r b - b², per piece; R²c at b = 1 and at the optimal per-piece
     scale (= r²);
  3. fresh vs R10u development (R-07 samples, unseen 74): r, b, target and model amplitude;
  4. B2: dev log IOI R²c with the R-06 formula vs R-07's (only the target centered);
  5. a single amplitude scale chosen on the R10u development pieces, applied to the fresh pieces;
  6. frozen SyMuPe vs the score-feature ridge on shape (r, r²) as well as R²c;
  7. leave-one-composer-out readings; sibling-flag split; per-source within-piece contrast;
  8. H1b-axes: a structure-free envelope-surrogate sampler (16 phase-randomised copies of the
     held-out experts' deviations, per-onset s.d. restored) scored like the model; needs the
     Mac fresh set (`artifacts/sets/fresh`, expert items only; about 2 min).

    uv run python experiments/2026-10-05-R-10-h1b/audit_checks.py [--skip-envnull]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "job"))
import summarize_h1b as sh  # noqa: E402

RES = HERE / "results_box" / "results"
cb = sh.cluster_boot_median
TS = ("velocity", "log_ioi")


def f3(x):
    return [round(float(v), 3) for v in x[:3]]


def prim(d: str, arm: str) -> pd.DataFrame:
    A = pd.read_csv(RES / d / "arms_per_piece.csv")
    P = pd.read_csv(RES / d / "experts_per_piece.csv")
    Pp = P[P["n"] >= 20]
    return A[(A["arm"] == arm) & A["piece"].isin(Pp["piece"])].merge(
        Pp.drop(columns=["work", "n"]), on="piece")


def scaled(g: pd.DataFrame, t: str, s: float) -> np.ndarray:
    return 2 * g[f"r_{t}"] * g[f"b_{t}"] * s - (g[f"b_{t}"] * s) ** 2


def envnull(out: dict) -> None:
    set_dir = HERE / "artifacts" / "sets" / "fresh"
    man = pd.read_csv(set_dir / "manifest.csv")
    man = man[man["kind"] == "real"]
    xp = set(pd.read_csv(HERE / "pieces" / "excluded_content_overlap.csv")["piece_id"])
    man = man[~man["passage"].isin(xp)]
    xr = pd.read_csv(HERE / "pieces" / "duplicate_renditions.csv")
    key = set(zip(xr["piece_id"], xr["dropped_performance_id"].astype(str), strict=True))
    man = man[[(p, str(q)) not in key for p, q in zip(man["passage"], man["performance_id"],
                                                        strict=True)]]
    A = pd.read_csv(RES / "fresh" / "arms_per_piece.csv")
    P = pd.read_csv(RES / "fresh" / "experts_per_piece.csv")
    axes = P[(P["n"] >= 36) & (P["k"] > 0)]["piece"].tolist()

    def env(D, rng):
        F = np.fft.rfft(D, axis=1)
        ph = rng.uniform(0, 2 * np.pi, F.shape)
        ph[:, 0] = 0
        S = np.fft.irfft(np.abs(F) * np.exp(1j * ph), n=D.shape[1], axis=1)
        S = S - S.mean(0)
        return S / (S.std(0) + 1e-12) * D.std(0)

    cache: dict = {}
    rows = []
    for piece in axes:
        g = man[man["passage"] == piece]
        gi = sh.load_item(set_dir / "gen_items" / (sh._slug(piece) + ".npz"))
        idx = pd.Index(np.unique(np.round(gi["score_onset_q"], 6)))
        V, T = sh.expert_matrix(set_dir, g["stem"].tolist(), idx, cache)
        keep = (np.isfinite(V).mean(0) >= 0.5) & (np.isfinite(T).mean(0) >= 0.5)
        V, T = V[:, keep], T[:, keep]
        k, _ = sh.parallel_k(V, T)
        rng = np.random.default_rng(123)
        ce, cn = [], []
        for h, r in sh.holdout_draws(len(V), piece):
            J, Vk, sv, st = sh.basis(V[r], T[r], k)
            ce.append(sh.capture(J, Vk, V[h], T[h], sv, st))
            Vh = sh._fill(V[h])
            Vh = Vh - Vh.mean(1, keepdims=True)
            Th = sh._fill(T[h])
            Dv, Dt = Vh - Vh.mean(0), Th - Th.mean(0)
            cn.append(np.mean([sh.capture(J, Vk, env(Dv, rng), env(Dt, rng), sv, st)
                               for _ in range(5)]))
        pr = P.set_index("piece").loc[piece]
        am = A[A["piece"] == piece].set_index("arm")
        rows.append({"piece": piece, "work": pr["work"], "k": k, "k_box": int(pr["k"]),
                     "cap_oracle": np.mean(ce), "cap_oracle_box": pr["cap_oracle"],
                     "cap_env": np.mean(cn), "cap_p100": am.loc["frozen_p100", "cap_model"],
                     "cap_p95": am.loc["frozen_p95", "cap_model"],
                     # addendum 2026-10-10: Pianist Transformer arm, when present
                     "cap_pt": (am.loc["pt_frozen", "cap_model"] if "pt_frozen" in am.index
                                else np.nan)})
    D = pd.DataFrame(rows)
    D["ratio_env"] = D["cap_env"] / D["cap_oracle"]
    arms = ("p100", "p95", "pt") if D["cap_pt"].notna().any() else ("p100", "p95")
    for a in arms:
        D[f"ratio_{a}"] = D[f"cap_{a}"] / D["cap_oracle"]
        D[f"adj_{a}"] = (D[f"cap_{a}"] - D["cap_env"]) / (D["cap_oracle"] - D["cap_env"])
    out["envnull"] = {
        "pieces": len(D), "k_matches_box": bool((D["k"] == D["k_box"]).all()),
        "cap_oracle_max_abs_diff_vs_box": float(
            (D["cap_oracle"] - D["cap_oracle_box"]).abs().max()),
        **{c: f3(cb(D, c)) for c in ["ratio_env"] + [f"{p}_{a}" for p in ("ratio", "adj")
                                                     for a in arms]},
        "pieces_model_p100_at_or_below_env": int((D["cap_p100"] <= D["cap_env"]).sum())}
    if "pt" in arms:
        out["envnull"]["pieces_pt_at_or_below_env"] = int((D["cap_pt"] <= D["cap_env"]).sum())


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-envnull", action="store_true")
    a = ap.parse_args(argv)
    out: dict = {}
    s = json.loads((RES / "fresh" / "summary.json").read_text())
    F, F1, FR = prim("fresh", "frozen_p95"), prim("fresh", "frozen_p100"), prim("fresh", "ridge")
    # 1. reproduction
    rep = {}
    for arm, g in (("frozen_p95", F), ("frozen_p100", F1), ("ridge", FR)):
        for t in TS:
            for c in (f"r2c_{t}", f"r_{t}", f"r2_{t}", f"b_{t}"):
                assert np.allclose(cb(g, c)[:3], s["arms"][arm][c][:3]), (arm, c)
            pt, lo, hi, _ = cb(g, f"r2c_{t}")
            rep[f"{arm}:{t}"] = [*f3((pt, lo, hi)), sh.reading(pt, lo, hi, 0.5, 0.2)]
    out["reproduced"] = rep
    # 2-3. decomposition, fresh vs dev
    u = pd.read_csv(HERE / "artifacts" / "r10u_pieces.csv")
    unseen = set(u[(u["n_periscope_paired"] == 0) & u["r02"]]["piece_id"])
    D = prim("r10u_r07", "frozen_r07_p95")
    Du = D[D["piece"].isin(unseen)]
    dec = {}
    for name, g in (("fresh_p95", F), ("fresh_p100", F1), ("ridge", FR), ("dev_unseen", Du)):
        for t in TS:
            r, b = g[f"r_{t}"], g[f"b_{t}"]
            sdt = np.sqrt(g[f"ss_target_{t}"] / g["n_onsets"])
            dec[f"{name}:{t}"] = {
                "n": len(g), "R2c": f3(cb(g, f"r2c_{t}")), "r": f3(cb(g, f"r_{t}")),
                "b": f3(cb(g, f"b_{t}")),
                "R2c_at_b1": f3(cb(g.assign(x=2 * r - 1), "x")),
                "r2_optimal_scale": f3(cb(g.assign(x=r ** 2), "x")),
                "sd_target": round(float(sdt.median()), 4),
                "sd_model": round(float((b * sdt).median()), 4),
                "reliability": round(float(g[f"reliability_{t}"].median()), 3),
                "oracle": round(float(g[f"oracle_analytic_{t}"].median()), 3),
                "n_renditions": float(g["n"].median())}
    out["decomposition"] = dec
    # 4. B2
    out["B2_dev_unseen_log_ioi"] = {"R06_formula": f3(cb(Du, "r2c_log_ioi")),
                                    "R07_formula": f3(cb(Du, "r2c_r07_log_ioi")),
                                    "velocity": f3(cb(Du, "r2c_velocity")), "n": len(Du)}
    # 5. dev-chosen global scale
    sc = {}
    for t in TS:
        s_dev = minimize_scalar(lambda x, t=t: -np.median(scaled(Du, t, x)), bounds=(0.1, 2),
                                method="bounded").x
        pt, lo, hi, _ = cb(F.assign(x=scaled(F, t, s_dev)), "x")
        sc[t] = {"s_dev": round(float(s_dev), 3),
                 "dev_median": round(float(np.median(scaled(Du, t, s_dev))), 3),
                 "fresh": f3((pt, lo, hi)), "reading": sh.reading(pt, lo, hi, 0.5, 0.2)}
    out["dev_scale"] = sc
    # 6. model vs ridge
    M = F.merge(FR[["piece", "r_velocity", "r_log_ioi", "r2c_velocity", "r2c_log_ioi"]],
                on="piece", suffixes=("", "_ridge"))
    mr = {}
    for t in TS:
        g = M.assign(dr=M[f"r_{t}"] - M[f"r_{t}_ridge"],
                     dR=M[f"r2c_{t}"] - M[f"r2c_{t}_ridge"],
                     dS=scaled(M, t, sc[t]["s_dev"]) - M[f"r2c_{t}_ridge"])
        mr[t] = {"r_diff": f3(cb(g, "dr")), "R2c_diff": f3(cb(g, "dR")),
                 "dev_scaled_model_minus_ridge_R2c": f3(cb(g, "dS"))}
    out["model_vs_ridge"] = mr
    # 7. composer, sibling, source
    comp = pd.read_csv(HERE / "pieces" / "fresh_pieces.csv").set_index("piece_id")["composer"]
    F["composer"] = F["piece"].map(comp)
    loco = {}
    for t in TS:
        rd = {c: cb(F[F["composer"] != c], f"r2c_{t}") for c in sorted(F["composer"].unique())}
        rr = {c: sh.reading(*v[:3], 0.5, 0.2) for c, v in rd.items()}
        loco[t] = {"not_falsified_when_dropping": {c: f3(rd[c]) for c, v in rr.items()
                                                   if v != "falsified"},
                   "range": [round(min(v[0] for v in rd.values()), 3),
                             round(max(v[0] for v in rd.values()), 3)]}
    out["loco"] = loco
    sib = pd.read_csv(HERE / "pieces" / "sibling_flag.csv").set_index("piece_id")[
        "sibling_paired"]
    F["sib"] = F["piece"].map(sib)
    out["sibling"] = {f"{t}:{k}": {"R2c": f3(cb(g, f"r2c_{t}")),
                                   "r": round(float(g[f"r_{t}"].median()), 3),
                                   "b": round(float(g[f"b_{t}"].median()), 3), "n": len(g)}
                      for t in TS for k, g in F.groupby("sib")}
    S = pd.read_csv(RES / "fresh" / "per_source.csv")
    r = S[(S["level"] == "rendition") & (S["arm"] == "frozen_p95")].copy()
    src = {}
    for t in TS:
        r["d"] = r[f"r_model_{t}"] - r[f"r_loo_{t}"]
        pm = r.groupby(["piece", "work", "source"])["d"].mean().unstack()
        for so in ("Transkun V2", "ATEPP", "ByteDance"):
            g = pm.dropna(subset=[so, "Aria-AMT"]).reset_index()
            src[f"{t}:{so}-Aria"] = f3(cb(g.assign(x=g[so] - g["Aria-AMT"]), "x")) + [len(g)]
    out["source_within_piece"] = src
    if not a.skip_envnull:
        envnull(out)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
