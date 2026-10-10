"""R-10 audit addendum (eval-auditor, 2026-10-10): the secondary, non-deciding arms.

Reads the committed `results_box/` CSVs from commit 9a1e9cb (Mac only, a few seconds):

  1. the refresh left the primary arms unchanged (rows and summary vs 2e90db7, via `git show`);
  2. Pianist Transformer (pt_frozen) and the R10u dev arm (frozen SyMuPe, top-p 1.0, dev_gen):
     every summary median / work-cluster CI reproduces; r, b, R²c, R²c at b = 1, r² (fix 6);
  3. fresh vs dev with the same model and top-p (1.0): shape vs amplitude;
  4. top-p 1.0 minus 0.95 on the same pieces (dev: dev_gen vs R-07 samples; fresh);
  5. one amplitude scale chosen on the dev_gen unseen 74, applied to fresh top-p 1.0.

The H1b-axes envelope null with the PT arm is in `audit_checks.py` (section 8 output).

    uv run python experiments/2026-10-05-R-10-h1b/audit_addendum.py
"""

from __future__ import annotations

import io
import json
import subprocess

import numpy as np
import pandas as pd
from audit_checks import HERE, RES, TS, cb, f3, prim, scaled, sh
from scipy.optimize import minimize_scalar
from scipy.stats import mannwhitneyu

OLD = "2e90db7"  # results_box before the 2026-10-10 refresh


def git_show(rel: str) -> str:
    return subprocess.run(["git", "-C", str(HERE), "show", f"{OLD}:./{rel}"], check=True,
                          capture_output=True, text=True).stdout


def decomp(g: pd.DataFrame) -> dict:
    r: dict = {"n": len(g), "works": int(g["work"].nunique())}
    for t in TS:
        rr, b = g[f"r_{t}"], g[f"b_{t}"]
        pt, lo, hi, _ = cb(g, f"r2c_{t}")
        sdt = np.sqrt(g[f"ss_target_{t}"] / g["n_onsets"])
        r[t] = {"R2c": f3((pt, lo, hi)), "reading": sh.reading(pt, lo, hi, 0.5, 0.2),
                "r": f3(cb(g, f"r_{t}")), "b": f3(cb(g, f"b_{t}")),
                "R2c_at_b1": f3(cb(g.assign(x=2 * rr - 1), "x")),
                "r2_best_scale": f3(cb(g.assign(x=rr ** 2), "x")),
                "sd_target": round(float(sdt.median()), 4),
                "sd_model": round(float((b * sdt).median()), 4),
                "share_negative": round(float((g[f"r2c_{t}"] < 0).mean()), 3)}
    return r


def check_summary(g: pd.DataFrame, s: dict, arm: str) -> None:
    for c in [f"{p}_{t}" for p in ("r2c", "r", "r2", "b") for t in TS] + ["axes_ratio"]:
        v = cb(g, c)
        assert np.allclose(v[:3], s["arms"][arm][c][:3]) and v[3] == s["arms"][arm][c][3], c
    for t in TS:
        assert np.allclose(2 * g[f"r_{t}"] * g[f"b_{t}"] - g[f"b_{t}"] ** 2, g[f"r2c_{t}"])
        assert s["arms"][arm][f"reading_{t}"] == sh.reading(*cb(g, f"r2c_{t}")[:3], 0.5, 0.2)


def main() -> None:
    out: dict = {}
    # 1. primary arms unchanged by the refresh
    for d in ("fresh", "fresh_as_registered"):
        rel = f"results_box/results/{d}"
        old = pd.read_csv(io.StringIO(git_show(f"{rel}/arms_per_piece.csv")))
        new = pd.read_csv(RES / d / "arms_per_piece.csv")
        so, sn = json.loads(git_show(f"{rel}/summary.json")), json.loads(
            (RES / d / "summary.json").read_text())
        out[f"unchanged:{d}"] = {
            "rows_equal": bool(new[new["arm"] != "pt_frozen"].reset_index(drop=True)[
                list(old.columns)].equals(old)),
            "summary_arms_equal": all(so["arms"][a] == sn["arms"][a] for a in so["arms"]),
            "headline_equal": so["headline"] == sn["headline"],
            "pt_rows": int((new["arm"] == "pt_frozen").sum())}
    # 2. reproduction and decomposition
    for d, arm in (("fresh", "pt_frozen"), ("fresh_as_registered", "pt_frozen"),
                   ("r10u_dev", "frozen_p100"), ("r10u_dev_no_overlap", "frozen_p100")):
        s = json.loads((RES / d / "summary.json").read_text())
        g = prim(d, arm)
        check_summary(g, s, arm)
        out[f"{arm}:{d}"] = {**decomp(g), "axes_ratio": f3(cb(g, "axes_ratio")) + [
            cb(g, "axes_ratio")[3]]}
        if arm == "pt_frozen":
            A = pd.read_csv(RES / d / "arms_per_piece.csv")
            W = A[A["piece"].isin(g["piece"])].pivot_table(
                index=["piece", "work"], columns="arm",
                values=[f"{c}_{t}" for c in ("r2c", "r") for t in TS]).reset_index()
            pr = {}
            for a_, b_ in (("frozen_p95", "pt_frozen"), ("pt_frozen", "ridge")):
                for t in TS:
                    for c in ("r2c", "r"):
                        x = pd.DataFrame({"work": W["work"],
                                          "d": W[(f"{c}_{t}", a_)] - W[(f"{c}_{t}", b_)]})
                        v = cb(x, "d")
                        if c == "r2c":
                            assert np.allclose(
                                v[:3], s["paired_median_differences"][f"{a_}-{b_}:{t}"][:3])
                        pr[f"{c} {a_}-{b_}:{t}"] = f3(v) + [round(float((x["d"] > 0).mean()), 2)]
            out[f"pt_paired:{d}"] = pr
    # 3. fresh vs dev, same model and top-p 1.0; dev restricted to the R-07 unseen 74
    u = pd.read_csv(HERE / "artifacts" / "r10u_pieces.csv")
    unseen = set(u[(u["n_periscope_paired"] == 0) & u["r02"]]["piece_id"])
    F1, F95 = prim("fresh", "frozen_p100"), prim("fresh", "frozen_p95")
    D1 = prim("r10u_dev", "frozen_p100")
    D1u = D1[D1["piece"].isin(unseen)]
    D7u = prim("r10u_r07", "frozen_r07_p95")
    D7u = D7u[D7u["piece"].isin(unseen)]
    out["dev_gen_unseen74"] = decomp(D1u)
    cmp = {}
    for t in TS:
        cols = {c: (F1[f"{c}_{t}"], D1u[f"{c}_{t}"]) for c in ("r", "b", "r2c")}
        sf = np.sqrt(F1[f"ss_target_{t}"] / F1["n_onsets"])
        sd = np.sqrt(D1u[f"ss_target_{t}"] / D1u["n_onsets"])
        cols["sd_target"] = (sf, sd)
        cols["sd_model"] = (F1[f"b_{t}"] * sf, D1u[f"b_{t}"] * sd)
        for c, (a, b) in cols.items():
            cmp[f"{t}:{c}"] = [round(float(a.median()), 3), round(float(b.median()), 3),
                               float(f"{mannwhitneyu(a, b).pvalue:.2g}")]
    out["fresh_p100_vs_dev_gen_unseen74 (fresh, dev, MW p)"] = cmp
    # 4. top-p 1.0 minus 0.95 on the same pieces
    for name, lo_, hi_ in (("dev_unseen74", D7u, D1u), ("fresh", F95, F1)):
        M = lo_.merge(hi_, on="piece", suffixes=("_95", "_100"))
        out[f"p100_minus_p95:{name}"] = {"n": len(M), **{
            f"{t}:{c}": f3(cb(pd.DataFrame({"work": M["work_95"],
                                            "d": M[f"{c}_{t}_100"] - M[f"{c}_{t}_95"]}), "d"))
            for t in TS for c in ("r", "b")}}
    # 5. one dev-chosen scale at top-p 1.0
    sc = {}
    for t in TS:
        s_dev = minimize_scalar(lambda x, t=t: -np.median(scaled(D1u, t, x)), bounds=(0.1, 2),
                                method="bounded").x
        pt, lo, hi, _ = cb(F1.assign(x=scaled(F1, t, s_dev)), "x")
        sc[t] = {"s_dev": round(float(s_dev), 3),
                 "dev_median": round(float(np.median(scaled(D1u, t, s_dev))), 3),
                 "fresh_p100": f3((pt, lo, hi)), "reading": sh.reading(pt, lo, hi, 0.5, 0.2)}
    out["dev_gen_scale_on_fresh_p100"] = sc
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
