"""R-10 reachability simulation (experts only, calibration pieces; no model, no decision piece).

For each calibration piece and each candidate K, a synthetic "sampler" is built from K held-out
real performances of which a fraction (1 - f) is replaced by envelope surrogates of themselves
(same smoothness and per-beat s.d., no cross-performer alignment). f = 1 is a perfect sampler of
the performer distribution, f = 0 a structure-free one. Each synthetic sampler is scored exactly
like a model arm (r10lib.captured), the calibrated ratio is computed over pieces, and the
pre-registered reading (r10lib.reading) is applied with a work-cluster bootstrap. Repeating over
independent draws gives the probability of each verdict branch at each true level.

    python simulate.py --data artifacts/calib --pieces pieces.csv --out artifacts/sim
"""

from __future__ import annotations

import argparse
import json
import os
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
import r10lib as L

HERE = Path(__file__).resolve().parent
KS = (16, 24, 32, 48)
FS = (0.0, 0.25, 0.5, 0.75, 1.0)
REPS = 10


def piece_sim(args) -> list[dict]:
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    path, work = args
    z = np.load(path, allow_pickle=False)
    qc = L.expert_qc(z)
    if qc is None:
        return []
    rows, cols, per = qc["rows"], qc["cols"], qc["period"]
    T, V = z["T"], z["V"]
    rng = np.random.default_rng(L.REF_SEED)
    if len(rows) < L.N_REF + min(KS):
        return []
    ref = np.sort(rng.choice(rows, L.N_REF, replace=False))
    pool = np.setdiff1d(rows, ref)
    Tr, Vr = L.blocks(T[ref], V[ref], cols, per)
    sc = L.shared_components(Tr, Vr, seed=0)
    out = []
    base = {"piece_id": str(z["piece_id"]), "work": work, "k": sc["k"], "share_k": sc["share_k"],
            "n_kept": len(rows), "beats": len(cols)}
    if sc["k"] == 0:
        return [{**base, "K": K, "eligible": len(pool) >= K} for K in KS]
    for K in KS:
        if len(pool) < K:
            out.append({**base, "K": K, "eligible": False})
            continue
        row = {**base, "K": K, "eligible": True, "random_c": (K - 1) / (2 * len(cols))}
        ce, en, sn = [], [], []
        for d in range(L.N_CEIL_DRAWS):
            r = np.random.default_rng(1000 + d)
            h = np.sort(r.choice(pool, K, replace=False))
            Th, Vh = L.blocks(T[h], V[h], cols, per)
            ce.append(L.captured(sc, Th, Vh))
            eT, eV = L.envelope_surrogate(Th - Th.mean(0), Vh - Vh.mean(0), r)
            en.append(L.captured(sc, eT, eV))
            nT = L.smooth_noise(K, len(cols), per, r) * Th.std()
            nV = L.smooth_noise(K, len(cols), per, r) * Vh.std()
            sn.append(L.captured(sc, nT, nV))
        for name, lst in (("expert", ce), ("env_null", en), ("smooth_null", sn)):
            for key in ("c_shared", "c_shared_topk", "c_ind", "r2c_T", "r2c_V"):
                row[f"{name}_{key}"] = float(np.nanmean([x[key] for x in lst]))
        for rep in range(REPS):
            r = np.random.default_rng(5000 + rep)
            h = np.sort(r.choice(pool, K, replace=False))
            Th, Vh = L.blocks(T[h], V[h], cols, per)
            dT, dV = Th - Th.mean(0), Vh - Vh.mean(0)
            eT, eV = L.envelope_surrogate(dT, dV, r)
            for f in FS:
                m = int(round(f * K))
                sel = r.permutation(K)[:m]
                sT, sV = eT.copy(), eV.copy()
                sT[sel], sV[sel] = dT[sel], dV[sel]
                c = L.captured(sc, sT, sV)
                row[f"syn_f{f}_r{rep}"] = c["c_shared"]
                row[f"syntopk_f{f}_r{rep}"] = c["c_shared_topk"]
        out.append(row)
    return out


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(HERE / "artifacts" / "calib"))
    ap.add_argument("--pieces", default=str(HERE / "pieces.csv"))
    ap.add_argument("--out", default=str(HERE / "artifacts" / "sim"))
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--boot", type=int, default=1000)
    a = ap.parse_args(argv)
    t0 = time.time()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    P = pd.read_csv(a.pieces)
    P = P[P["set"] == "calibration"]
    jobs = [(str(Path(a.data) / "curves" / f"{L.slug(p)}.npz"), w)
            for p, w in zip(P["piece_id"], P["work"], strict=True)]
    jobs = [j for j in jobs if Path(j[0]).exists()]
    rows = []
    with ProcessPoolExecutor(a.workers) as ex:
        for r in ex.map(piece_sim, jobs):
            rows.extend(r)
    D = pd.DataFrame(rows)
    D.to_csv(out / "sim_pieces.csv", index=False)
    summ = []
    for K, g in D[D["eligible"] & (D["k"] > 0)].groupby("K"):
        s = {"K": K, "pieces": len(g), "k_median": float(g["k"].median()),
             "share_k_median": float(g["share_k"].median()),
             "ceiling_mean": float(g["expert_c_shared"].mean()),
             "ceiling_median": float(g["expert_c_shared"].median()),
             "random_ratio": L.ratio_of_means(g, "random_c", "expert_c_shared"),
             "env_null_ratio": L.ratio_of_means(g, "env_null_c_shared", "expert_c_shared"),
             "smooth_null_ratio": L.ratio_of_means(g, "smooth_null_c_shared", "expert_c_shared"),
             "ceiling_topk_mean": float(g["expert_c_shared_topk"].mean()),
             "expert_r2c_T": float(g["expert_r2c_T"].median()),
             "expert_r2c_V": float(g["expert_r2c_V"].median())}
        variants = {
            "span_raw": ("syn", "expert_c_shared", None),
            "span_adj": ("syn", "expert_c_shared", "env_null_c_shared"),
            "topk_raw": ("syntopk", "expert_c_shared_topk", None),
            "topk_adj": ("syntopk", "expert_c_shared_topk", "env_null_c_shared_topk"),
        }
        for vname, (pre, den, null) in variants.items():
            for f in FS:
                ratios, his, los, verdicts = [], [], [], []
                for rep in range(REPS):
                    col = f"{pre}_f{f}_r{rep}"

                    def stat(d, col=col, den=den, null=null):
                        if null is None:
                            return L.ratio_of_means(d, col, den)
                        return float((d[col] - d[null]).sum() / (d[den] - d[null]).sum())

                    p, lo, hi = L.cluster_boot(g, stat, n=a.boot, seed=rep)
                    ratios.append(p)
                    los.append(lo)
                    his.append(hi)
                    verdicts.append(L.reading(lo, hi, p).split(" (")[0])
                vc = pd.Series(verdicts).value_counts(normalize=True).to_dict()
                s[f"{vname}_f{f}"] = {
                    "ratio_mean": float(np.mean(ratios)), "ratio_sd": float(np.std(ratios)),
                    "ci_halfwidth": float(np.mean(np.array(his) - np.array(los)) / 2),
                    "p_supported": vc.get("supported", 0.0),
                    "p_falsified": vc.get("falsified", 0.0),
                    "p_inconclusive": vc.get("inconclusive", 0.0)}
        s["env_null_ratio_topk"] = L.ratio_of_means(g, "env_null_c_shared_topk",
                                                    "expert_c_shared_topk")
        summ.append(s)
    (out / "sim_summary.json").write_text(json.dumps(summ, indent=1))
    print(json.dumps(summ, indent=1))
    print(f"done in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
