"""R-10 analysis: model sample curves (R-02), per-piece statistics, pre-registered summary.

    python analyze.py --data OUT/data --gen OUT/gen --pieces ../pieces.csv --set decision \
        --arms frozen pt_frozen E --k 32 --out OUT/results

Reads every arm's generation chunks (OUT/gen/<arm>/c<i>/<slug>.npz, 16 samples each, chunk
order fixed), builds R-02 curves for each sample on the expert grid (cached in
OUT/model_curves/<arm>/<slug>.npz), runs r10lib.analyse_piece and writes:

  per_piece.csv   one row per piece: k, shared share, every sampler's captured shares and R²c
  summary.json    per arm: calibrated ratio (deciding), CIs, reading; nulls; secondary tables
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import r10lib as L  # noqa: E402

PRIMARY = "frozen"


def load_samples(gen: Path, arm: str, s: str, k: int, chunk: int) -> dict | None:
    on, ve = [], []
    for c in range(-(-k // chunk)):
        f = gen / arm / f"c{c}" / f"{s}.npz"
        if not f.exists():
            return None
        z = np.load(f)
        on.append(z["onset"])
        ve.append(z["vel"])
    return {"onset": np.vstack(on)[:k], "vel": np.vstack(ve)[:k]}


def piece_job(args) -> dict | None:
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    data, gen, mc, pid, work, arms, k, chunk = args
    from pianolens.models.expression_data import load_item

    s = L.slug(pid)
    z = dict(np.load(Path(data) / "curves" / f"{s}.npz", allow_pickle=False))
    gi = load_item(Path(data) / "gen_items" / f"{s}.npz")
    sn = dict(np.load(Path(data) / "score_notes" / f"{s}.npz", allow_pickle=False))
    samplers, missing = {}, []
    for arm in arms:
        cache = Path(mc) / arm / f"{s}.npz"
        if cache.exists():
            c = np.load(cache)
            samplers[arm] = (c["T"], c["V"])
            continue
        g = load_samples(Path(gen), arm, s, k, chunk)
        if g is None or len(g["onset"]) < k:
            missing.append(arm)
            continue
        T, TO, V = L.sample_curves(gi, g, sn, z["grid"], z["pos_grid"], float(z["bpb"]))
        cache.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(cache, T=T, Tobs=TO, V=V)
        samplers[arm] = (T, V)
    r = L.analyse_piece(z, samplers, k)
    if r is None:
        return {"piece_id": pid, "work": work, "eligible": False, "qc_failed": True}
    return {"piece_id": pid, "work": work, "missing_arms": ",".join(missing), **r}


def summarize(D: pd.DataFrame, arms: list[str], boot: int) -> dict:
    E = D[D["eligible"].astype(bool)]
    S = E[E["k"] > 0]
    out = {"pieces_eligible": len(E), "pieces_k_pos": len(S), "works": int(S["work"].nunique()),
           "k_median": float(S["k"].median()), "share_k_median": float(S["share_k"].median()),
           "ceiling_c_shared_mean": float(S["expert_c_shared"].mean()),
           "ceiling_c_shared_topk_mean": float(S["expert_c_shared_topk"].mean())}

    def adj(col: str, base: str):
        num, den, null = f"{col}_{base}", f"expert_{base}", f"env_null_{base}"
        return lambda d: float((d[num] - d[null]).sum() / (d[den] - d[null]).sum())

    def raw(col: str, base: str):
        return lambda d: L.ratio_of_means(d, f"{col}_{base}", f"expert_{base}")

    nulls = {}
    for nm in ("env_null", "smooth_null"):
        nulls[nm] = {b: L.cluster_boot(S, raw(nm, b), n=boot) for b in ("c_shared",
                                                                        "c_shared_topk")}
    nulls["random_span"] = L.ratio_of_means(S, "random_c", "expert_c_shared")
    out["nulls_raw_ratio"] = nulls
    out["arms"] = {}
    for arm in arms:
        A = S[S[f"{arm}_c_shared"].notna()] if f"{arm}_c_shared" in S else S.iloc[:0]
        if A.empty:
            continue
        r = {"pieces": len(A)}
        p, lo, hi = L.cluster_boot(A, adj(arm, L.DECIDING_BASE), n=boot)
        r["deciding"] = {"statistic": f"null-adjusted ratio, {L.DECIDING_BASE}", "point": p,
                         "ci": [lo, hi], "reading": L.reading(lo, hi, p)}
        for b in ("c_shared", "c_shared_topk"):
            r[f"adj_{b}"] = L.cluster_boot(A, adj(arm, b), n=boot)
            r[f"raw_{b}"] = L.cluster_boot(A, raw(arm, b), n=boot)
            r[f"mean_{b}"] = float(A[f"{arm}_{b}"].mean())
            r[f"minus_env_null_{b}"] = L.cluster_boot(
                A, lambda d, b=b, arm=arm: float((d[f"{arm}_{b}"] - d[f"env_null_{b}"]).mean()),
                n=boot)
        # individual part and mean curve (secondary)
        r["raw_c_ind"] = L.cluster_boot(A, raw(arm, "c_ind"), n=boot)
        r["adj_c_ind"] = L.cluster_boot(A, adj(arm, "c_ind"), n=boot)
        for blk in ("T", "V"):
            r[f"r2c_{blk}_median"] = float(A[f"{arm}_r2c_{blk}"].median())
            r[f"r2c_{blk}_ratio"] = L.cluster_boot(
                A, lambda d, blk=blk, arm=arm: float(d[f"{arm}_r2c_{blk}"].clip(lower=0).sum()
                                            / d[f"expert_r2c_{blk}"].clip(lower=0).sum()), n=boot)
        # leave-one-work-out range of the deciding point estimate
        lo_ = [adj(arm, L.DECIDING_BASE)(A[A["work"] != w]) for w in A["work"].unique()]
        r["deciding_lowo_range"] = [float(min(lo_)), float(max(lo_))]
        out["arms"][arm] = r
    for arm in arms:
        if arm == PRIMARY or arm not in out["arms"] or PRIMARY not in out["arms"]:
            continue
        A = S[S[f"{arm}_c_shared"].notna() & S[f"{PRIMARY}_c_shared"].notna()]
        b = L.DECIDING_BASE
        out["arms"][arm][f"minus_{PRIMARY}_deciding"] = L.cluster_boot(
            A, lambda d, b=b, arm=arm: adj(arm, b)(d) - adj(PRIMARY, b)(d), n=boot)
    return out


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--gen", required=True)
    ap.add_argument("--pieces", default=str(HERE.parent / "pieces.csv"))
    ap.add_argument("--set", nargs="+", default=["decision"])
    ap.add_argument("--arms", nargs="+", default=["frozen", "pt_frozen", "E"])
    ap.add_argument("--k", type=int, required=True)
    ap.add_argument("--chunk", type=int, default=16, help="samples per generation chunk")
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--boot", type=int, default=2000)
    a = ap.parse_args(argv)
    t0 = time.time()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    mc = Path(a.gen).parent / "model_curves"
    P = pd.read_csv(a.pieces)
    P = P[P["set"].isin(a.set)].drop_duplicates("piece_id")
    jobs = [(a.data, a.gen, str(mc), pid, w, a.arms, a.k, a.chunk)
            for pid, w in zip(P["piece_id"], P["work"], strict=True)
            if (Path(a.data) / "curves" / f"{L.slug(pid)}.npz").exists()]
    with ProcessPoolExecutor(a.workers) as ex:
        rows = [r for r in ex.map(piece_job, jobs) if r is not None]
    D = pd.DataFrame(rows)
    D.to_csv(out / "per_piece.csv", index=False)
    summ = {"k": a.k, "arms_requested": a.arms, "pieces_listed": len(P),
            "pieces_prepared": len(jobs), **summarize(D, a.arms, a.boot),
            "seconds": round(time.time() - t0, 1)}
    (out / "summary.json").write_text(json.dumps(summ, indent=1, default=float))
    print(json.dumps(summ, indent=1, default=float))


if __name__ == "__main__":
    main()
