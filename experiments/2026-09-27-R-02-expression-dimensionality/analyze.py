"""R-02 step 2: PCA counts, held-out reconstruction, nulls, transcription controls, figures.

    uv run python experiments/2026-09-27-R-02-expression-dimensionality/analyze.py pieces
    uv run python experiments/2026-09-27-R-02-expression-dimensionality/analyze.py disklavier
    uv run python experiments/2026-09-27-R-02-expression-dimensionality/analyze.py vienna
    uv run python experiments/2026-09-27-R-02-expression-dimensionality/analyze.py figures
    uv run python experiments/2026-09-27-R-02-expression-dimensionality/analyze.py summarize

Definitions and QC rules: README.md (pre-registered). Seeds: subsample 0, held-out splits 0-4,
surrogates 0, Disklavier / Vienna transcribed subsamples 0-49, bootstrap 0.
"""

from __future__ import annotations

import argparse
import pickle
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd

from pianolens.eval import bootstrap_ci
from pianolens.eval.dimensionality import (
    column_shuffle,
    explained_variance_ratio,
    heldout_r2_curve,
    loo_r2_curve,
    mean_curve_share,
    n_components_for,
    phase_randomize,
    whittaker_smooth,
)

HERE = Path(__file__).resolve().parent
ART = HERE / "artifacts"
CURVES = ART / "curves"
FIG = ART / "figures"
sys.path.insert(0, str(HERE))

KS = list(range(1, 21))  # pre-registered range
KS_EXT = list(range(1, 41))  # exploratory extension (added after the first piece, see README)
N_SUB = 50
MISS_BEAT = 0.10  # drop beats unobserved in more than this share of performances
MISS_PERF = 0.10  # then drop performances unobserved on more than this share of beats
MISS_POS = 0.20  # residual timing: positions / performances
CUTOFF_BARS = 1.5


# --------------------------------------------------------------------------- QC + blocks


def _fill_nearest(row: np.ndarray) -> np.ndarray:
    ok = np.isfinite(row)
    if ok.all() or not ok.any():
        return row
    x = np.arange(len(row))
    return np.interp(x, x[ok], row[ok])  # linear inside, nearest edge value outside


def _center_rows(x: np.ndarray) -> np.ndarray:
    return x - x.mean(axis=1, keepdims=True)


def load_blocks(path: Path) -> dict | None:
    """Apply the pre-registered QC to one piece's curves; return the blocks and counts."""
    z = np.load(path, allow_pickle=False)
    ok = z["ok"]
    perf_ids = z["perf_ids"]
    T, TO, V, R = z["T"].astype(float), z["Tobs"], z["V"].astype(float), z["R"].astype(float)
    grid, has, bpb = z["grid"], z["has_onset"], float(z["bpb"])
    info = {"piece_id": str(z["piece_id"]), "n_total": len(ok), "n_ok": int(ok.sum()),
            "beats_total": len(grid), "pos_total": R.shape[1], "bpb": bpb,
            "edf_median": float(np.nanmedian(z["s_edf"])) if ok.any() else np.nan,
            "n_pauses_median": float(np.nanmedian(z["s_n_pauses"])) if ok.any() else np.nan}
    if ok.sum() < 3:
        return None
    rows = np.where(ok)[0]
    tobs = TO[rows] & np.isfinite(T[rows])
    beat_keep = tobs.mean(axis=0) >= 1 - MISS_BEAT
    if beat_keep.sum() < 8:
        return None
    vgrid = beat_keep & has
    vobs = np.isfinite(V[rows][:, vgrid])
    vbeat_keep_local = vobs.mean(axis=0) >= 1 - MISS_BEAT
    vcols = np.where(vgrid)[0][vbeat_keep_local]
    perf_ok = (tobs[:, beat_keep].mean(axis=1) >= 1 - MISS_PERF) & (
        np.isfinite(V[rows][:, vcols]).mean(axis=1) >= 1 - MISS_PERF)
    rows = rows[perf_ok]
    cols = np.where(beat_keep)[0]
    info.update(n_kept=len(rows), beats_kept=len(cols), vbeats_kept=len(vcols))
    if len(rows) < 3:
        return None
    Tk = np.vstack([_fill_nearest(r) for r in T[np.ix_(rows, cols)]])
    Tk = _center_rows(Tk)
    # velocity: raw per-beat block on vcols; smooth block on the tempo grid
    Vr = np.vstack([_fill_nearest(r) for r in V[np.ix_(rows, vcols)]])
    Vr = _center_rows(Vr)
    Vt = np.vstack([_fill_nearest(r) for r in V[np.ix_(rows, cols)]])  # interp over no-onset beats
    period = CUTOFF_BARS * bpb
    Vs = _center_rows(whittaker_smooth(Vt, period))
    # residual timing
    Rr = R[rows]
    pos_keep = np.isfinite(Rr).mean(axis=0) >= 1 - MISS_POS
    rrows_local = np.isfinite(Rr[:, pos_keep]).mean(axis=1) >= 1 - MISS_POS
    Rk = Rr[np.ix_(rrows_local, pos_keep)]
    colmean = np.nanmean(Rk, axis=0) if len(Rk) else np.zeros(pos_keep.sum())
    Rk = np.where(np.isfinite(Rk), Rk, colmean)
    Rk = _center_rows(Rk) if len(Rk) else Rk
    info.update(pos_kept=int(pos_keep.sum()), n_resid_kept=int(rrows_local.sum()))
    return {
        "info": info, "perf_ids": perf_ids[rows], "grid": grid[cols], "vgrid": grid[vcols],
        "bar_starts": z["bar_starts"], "T": Tk, "Vs": Vs, "Vr": Vr,
        "Vt": Vt - Vt.mean(1, keepdims=True),
        "R": Rk, "resid_perf_ids": perf_ids[rows][rrows_local], "period": period,
        "tempo_bpm": z["s_tempo_bpm_geomean"][rows],
    }


def joint(t: np.ndarray, v: np.ndarray) -> np.ndarray:
    """Concatenate two blocks, each scaled to unit mean total variance (column-centered)."""
    def s(x):
        return np.sqrt(((x - x.mean(0)) ** 2).sum() / len(x))
    return np.hstack([t / s(t), v / s(v)])


# --------------------------------------------------------------------------- statistics


def stats(x: np.ndarray, heldout: bool = True) -> dict:
    r = explained_variance_ratio(x)
    out = {"k80_in": n_components_for(r, 0.8), "k90_in": n_components_for(r, 0.9),
           "pc1": float(r[0]), "top3": float(r[:3].sum()), "top10": float(r[:10].sum()),
           "max_k": int(min(len(x) - 1, x.shape[1])), "ratios": r[:50].astype(np.float32),
           "mean_share": mean_curve_share(x)}
    if heldout and len(x) >= 10:
        h = heldout_r2_curve(x, KS_EXT, n_splits=5, seed=0)
        out["ho"] = h.astype(np.float32)
        out["k80_ho"] = next((k for k, v in zip(KS, h, strict=False) if v >= 0.8), 21)
        out["k90_ho"] = next((k for k, v in zip(KS, h, strict=False) if v >= 0.9), 21)
        out["k80_ho_ext"] = next((k for k, v in zip(KS_EXT, h, strict=True) if v >= 0.8), 41)
        out["ho_r2_k20"] = float(h[19])
        out["ho_r2_k5"], out["ho_r2_k10"] = float(h[4]), float(h[9])
    return out


def smooth_noise_like(d: np.ndarray, period: float, rng) -> np.ndarray:
    sd = d.std(axis=0)
    w = whittaker_smooth(rng.normal(size=d.shape), period)
    w = w / w.std(axis=0, keepdims=True)
    return w * sd


def analyse_set(b: dict, rows: np.ndarray, seed: int = 0) -> list[dict]:
    """All blocks, real and null, for a set of performance rows of one piece."""
    T, Vs, Vr = b["T"][rows], b["Vs"][rows], b["Vr"][rows]
    per = b["period"]
    out = []

    def add(block, source, x, heldout=True):
        s = stats(x, heldout)
        s.update(block=block, source=source, n=len(x), p=x.shape[1])
        out.append(s)

    add("tempo", "real", T)
    add("vel_smooth", "real", Vs)
    add("vel_raw", "real", Vr)
    add("joint", "real", joint(T, Vs))
    # sensitivity: 3-bar smoothing; row-z-scored velocity
    T3 = _center_rows(whittaker_smooth(T, 2 * per))
    V3 = _center_rows(whittaker_smooth(b["Vt"][rows], 2 * per))
    add("joint_3bar", "real", joint(T3, V3))
    Vz = Vs / Vs.std(axis=1, keepdims=True)
    add("joint_velz", "real", joint(T, Vz))
    # nulls
    rng = np.random.default_rng(seed)
    dT, dV = T - T.mean(0), Vs - Vs.mean(0)
    pT, pV = phase_randomize([dT, dV / dV.std() * dT.std()], rng)
    pV = pV / dT.std() * dV.std()
    (pVr,) = phase_randomize(Vr - Vr.mean(0), rng)
    add("tempo", "phase", pT)
    add("vel_smooth", "phase", pV)
    add("vel_raw", "phase", pVr)
    add("joint", "phase", joint(pT, pV))
    sT, sV = column_shuffle(T, rng), column_shuffle(Vs, rng)
    add("tempo", "shuffle", sT)
    add("vel_smooth", "shuffle", sV)
    add("joint", "shuffle", joint(sT, sV))
    wT = rng.normal(size=T.shape) * dT.std(0)
    wV = rng.normal(size=Vs.shape) * dV.std(0)
    add("tempo", "white", wT, heldout=False)
    add("joint", "white", joint(wT, wV), heldout=False)
    nT, nV = smooth_noise_like(dT, per, rng), smooth_noise_like(dV, per, rng)
    add("tempo", "smooth_noise", nT, heldout=False)
    add("joint", "smooth_noise", joint(nT, nV), heldout=False)
    return out


def _agg_rows(rs: list[dict], block: str, source: str) -> dict:
    """One row per piece from several windows: medians of the scalars and of the curves."""
    out = {"block": block, "source": source, "variant": "n50", "n_windows": len(rs)}
    for k in ["k80_in", "k90_in", "pc1", "top3", "top10", "mean_share", "k80_ho", "k90_ho",
              "k80_ho_ext", "ho_r2_k5", "ho_r2_k10", "ho_r2_k20", "n", "p", "max_k"]:
        vals = [r[k] for r in rs if k in r]
        if vals:
            out[k] = float(np.median(vals))
    for k in ["ratios", "ho"]:
        arrs = [r[k] for r in rs if k in r]
        if arrs:
            L = min(len(a) for a in arrs)
            out[k] = np.median(np.array([a[:L] for a in arrs]), axis=0).astype(np.float32)
    return out


def exploratory(b: dict, sub: np.ndarray) -> list[dict]:
    """Added after the dry run (README, "Amendments"): 16-bar windows and outlier trimming."""
    out = []
    T, Vt = b["T"], b["Vt"]
    per = b["period"]
    bpb = b["info"]["bpb"]
    w = int(round(16 * bpb))
    p = T.shape[1]
    reals, nulls = [], []
    rng = np.random.default_rng(0)
    for s0 in range(0, p - w + 1, w):
        cs = slice(s0, s0 + w)
        tw = _center_rows(T[np.ix_(sub, np.arange(p)[cs])])
        vw = _center_rows(whittaker_smooth(Vt[np.ix_(sub, np.arange(p)[cs])], per))
        reals.append(stats(joint(tw, vw)))
        dT, dV = tw - tw.mean(0), vw - vw.mean(0)
        pT, pV = phase_randomize([dT, dV / dV.std() * dT.std()], rng)
        pV = pV / dT.std() * dV.std()
        nulls.append(stats(joint(pT, pV)))
    if reals:
        for rs, src in ((reals, "real"), (nulls, "phase")):
            a = _agg_rows(rs, "joint_win16", src)
            a.update(n=len(sub), p=2 * w)
            out.append(a)
    # trimmed: drop the 10% of performances farthest from the median joint curve, then n = 50
    J = joint(T, b["Vs"])
    dist = np.sqrt(((J - np.median(J, axis=0)) ** 2).sum(axis=1))
    keep = np.where(dist <= np.quantile(dist, 0.9))[0]
    if len(keep) >= N_SUB:
        ts = np.sort(np.random.default_rng(0).permutation(keep)[:N_SUB])
        s = stats(joint(T[ts], b["Vs"][ts]))
        s.update(block="joint_trim10", source="real", n=N_SUB, p=J.shape[1], variant="n50")
        out.append(s)
    return out


def analyse_piece(path: Path) -> dict | None:
    b = load_blocks(path)
    if b is None:
        return {"info": {"piece_id": path.stem, "failed": True}, "rows": []}
    info = b["info"]
    n = len(b["T"])
    results = []
    rng = np.random.default_rng(0)
    if n >= N_SUB:
        sub = np.sort(rng.permutation(n)[:N_SUB])
        for r in analyse_set(b, sub):
            r["variant"] = "n50"
            results.append(r)
        nr = len(b["R"])
        if nr >= N_SUB:
            rs = np.sort(np.random.default_rng(0).permutation(nr)[:N_SUB])
            x = b["R"][rs]
            s = stats(x)
            s.update(block="residual", source="real", n=len(x), p=x.shape[1], variant="n50")
            results.append(s)
            (pr,) = phase_randomize(x - x.mean(0), np.random.default_rng(0))
            s = stats(pr)
            s.update(block="residual", source="phase", n=len(x), p=x.shape[1], variant="n50")
            results.append(s)
        results.extend(exploratory(b, sub))
    for r in analyse_set(b, np.arange(n)):
        r["variant"] = "all"
        results.append(r)
    for r in results:
        r["piece_id"] = info["piece_id"]
    return {"info": info, "rows": results}


def cmd_pieces(args) -> None:
    files = sorted(CURVES.glob("*.npz"))
    if args.limit:
        files = files[: args.limit]
    t0 = time.time()
    infos, rows = [], []
    with ProcessPoolExecutor(args.workers) as ex:
        futs = [ex.submit(analyse_piece, f) for f in files]
        for k, f in enumerate(as_completed(futs), 1):
            r = f.result()
            infos.append(r["info"])
            rows.extend(r["rows"])
            if k % 100 == 0:
                print(f"{k}/{len(files)} {time.time() - t0:.0f}s", flush=True)
    with open(ART / "piece_results.pkl", "wb") as fh:
        pickle.dump({"infos": infos, "rows": rows}, fh)
    pd.DataFrame(infos).to_csv(ART / "piece_qc.csv", index=False)
    scal = pd.DataFrame([{k: v for k, v in r.items() if np.ndim(v) == 0} for r in rows])
    scal.to_csv(ART / "piece_stats.csv", index=False)
    print(f"{len(infos)} pieces, {len(rows)} rows, {time.time() - t0:.0f}s")


# --------------------------------------------------------------------------- Disklavier control


def _small_stats(x: np.ndarray) -> dict:
    r = explained_variance_ratio(x)
    lo = loo_r2_curve(x, [1, 2, 3])
    return {"k80_in": n_components_for(r, 0.8), "pc1": float(r[0]), "top3": float(r[:3].sum()),
            "loo_r2_k1": lo[0], "loo_r2_k2": lo[1], "loo_r2_k3": lo[2]}


def disk_piece(path: Path, min_d: int) -> list[dict]:
    b = load_blocks(path)
    if b is None:
        return []
    sel = pd.read_parquet(ART / "performances_selected.parquet",
                          columns=["performance_id", "provenance"]).set_index("performance_id")
    prov = sel.loc[b["perf_ids"], "provenance"].to_numpy()
    dk, tr = np.where(prov == "disklavier")[0], np.where(prov == "transcribed")[0]
    d = len(dk)
    if d < min_d or len(tr) < 2 * d:
        return []
    out = []
    blocks = {"tempo": lambda r: b["T"][r], "vel_smooth": lambda r: b["Vs"][r],
              "joint": lambda r: joint(b["T"][r], b["Vs"][r])}
    for name, f in blocks.items():
        real = _small_stats(f(dk))
        subs = []
        rng = np.random.default_rng(0)
        for _ in range(50):
            subs.append(_small_stats(f(np.sort(rng.choice(tr, d, replace=False)))))
        subs_df = pd.DataFrame(subs)
        row = {"piece_id": b["info"]["piece_id"], "block": name, "d": d, "n_trans": len(tr),
               "p": len(b["grid"])}
        for k, v in real.items():
            row[f"disk_{k}"] = v
            row[f"trans_{k}"] = float(subs_df[k].median())
        out.append(row)
    return out


def cmd_disklavier(args) -> None:
    files = sorted(CURVES.glob("*.npz"))
    rows = []
    with ProcessPoolExecutor(args.workers) as ex:
        for r in ex.map(disk_piece, files, [args.min_d] * len(files)):
            rows.extend(r)
    df = pd.DataFrame(rows)
    df.to_csv(ART / "disklavier_control.csv", index=False)
    from scipy.stats import wilcoxon

    lines = []
    for blk, g in df.groupby("block"):
        for k in ["k80_in", "pc1", "top3", "loo_r2_k1", "loo_r2_k3"]:
            diff = (g[f"disk_{k}"] - g[f"trans_{k}"]).to_numpy()
            ci = bootstrap_ci(lambda x: float(np.median(x)), diff, n_boot=2000, seed=0)
            p = wilcoxon(diff).pvalue if np.any(diff != 0) else 1.0
            lines.append({"block": blk, "metric": k, "n_pieces": len(g),
                          "disk_median": g[f"disk_{k}"].median(),
                          "trans_median": g[f"trans_{k}"].median(),
                          "median_diff": ci.estimate, "ci_low": ci.low, "ci_high": ci.high,
                          "wilcoxon_p": p})
    s = pd.DataFrame(lines)
    s.to_csv(ART / "disklavier_summary.csv", index=False)
    print(s.to_string())


# --------------------------------------------------------------------------- Vienna control


def _offset(v_notes: pd.DataFrame, pc_notes: pd.DataFrame) -> tuple[float, float]:
    """Beat offset mapping Vienna score beats onto PianoCoRe score beats, by note matching."""
    pcset = {(round(b, 3), p) for b, p in zip(pc_notes["b"], pc_notes["pitch"], strict=True)}
    cands = {}
    for vb, vp in zip(v_notes["b"][:40], v_notes["pitch"][:40], strict=True):
        for pb in pc_notes.loc[pc_notes["pitch"] == vp, "b"]:
            cands[round(pb - vb, 3)] = 0
    best, frac = 0.0, 0.0
    for dlt in cands:
        hit = np.mean([(round(b + dlt, 3), p) in pcset
                       for b, p in zip(v_notes["b"], v_notes["pitch"], strict=True)])
        if hit > frac:
            best, frac = dlt, hit
    return best, frac


def _curves_matrix(perfs: list[tuple[np.ndarray, np.ndarray, np.ndarray]], grid, pos_grid, bpb,
                   has):
    from curves import grid_curves

    T, TO, V = [], [], []
    for beats, on, vel in perfs:
        c = grid_curves(beats, on, vel, grid, pos_grid, bpb)
        T.append(c["T"])
        TO.append(c["Tobs"])
        V.append(c["V"])
    T, TO, V = np.array(T), np.array(TO), np.array(V)
    # same QC as load_blocks (tempo + smooth velocity only)
    tobs = TO & np.isfinite(T)
    bk = tobs.mean(0) >= 1 - MISS_BEAT
    pk = tobs[:, bk].mean(1) >= 1 - MISS_PERF
    Tk = _center_rows(np.vstack([_fill_nearest(r) for r in T[np.ix_(pk, bk)]]))
    Vt = np.vstack([_fill_nearest(r) for r in V[np.ix_(pk, bk)]])
    Vs = _center_rows(whittaker_smooth(Vt, CUTOFF_BARS * bpb))
    return Tk, Vs, grid[bk]


def cmd_vienna(args) -> None:
    from pianolens.data import pianocore_cache as pc
    from pianolens.data import vienna4x22
    from pianolens.features.tempo import matched_onsets

    by_piece: dict[str, list] = {}
    scores = {}
    for ap in vienna4x22.iter_aligned():
        pid = str(ap.performance.piece_id)
        notes, _ = matched_onsets(ap)
        by_piece.setdefault(pid, []).append(notes)
        sn = ap.score.notes
        g = ~sn["is_grace"].astype(bool)
        scores[pid] = (pd.DataFrame({"b": sn["onset_beat"][g].astype(float),
                                     "pitch": sn["pitch"][g].astype(int)})
                       .sort_values("b").reset_index(drop=True),
                       float(np.median(sn["ts_beats"])))
    sel = pd.read_parquet(ART / "performances_selected.parquet")
    rows = []
    for pid, plist in by_piece.items():
        if pid not in set(sel["piece_id"]):
            print(f"{pid}: not in tier A selection, skipped")
            continue
        vsc, bpb = scores[pid]
        df = pc.load_piece_notes(pid, columns=["performance_id", "label", "s_onset_beat",
                                               "s_pitch", "s_is_grace", "p_onset_sec",
                                               "p_velocity"])
        ids = sel.loc[(sel["piece_id"] == pid) & (sel["provenance"] == "transcribed"),
                      "performance_id"].to_numpy()
        df = df[df["s_is_grace"] == 0]
        one = df[df["performance_id"] == df["performance_id"].iloc[0]]
        pcn = pd.DataFrame({"b": one["s_onset_beat"].astype(float),
                            "pitch": one["s_pitch"].astype(int)})
        dlt, frac = _offset(vsc, pcn)
        # keep the Vienna notes that map; restrict to their contiguous beat range
        mapped = np.array([(round(b + dlt, 3), p) in
                           {(round(x, 3), y) for x, y in zip(pcn["b"], pcn["pitch"],
                                                              strict=True)}
                           for b, p in zip(vsc["b"], vsc["pitch"], strict=True)])
        # longest run of mapped notes (a repeat the PianoCoRe score lacks breaks the run)
        best, cur, start, bs = 0, 0, 0, 0
        for i, m in enumerate(mapped):
            cur = cur + 1 if m else 0
            if cur == 1:
                start = i
            if cur > best:
                best, bs = cur, start
        lo_b, hi_b = vsc["b"].iloc[bs], vsc["b"].iloc[bs + best - 1]
        print(f"{pid}: offset {dlt}, mapped {frac:.2f}, run {best}/{len(vsc)} notes, "
              f"beats {lo_b}..{hi_b}")
        grid = np.arange(np.ceil(lo_b), np.floor(hi_b) + 1)
        pos_grid = np.unique(vsc["b"][(vsc["b"] >= lo_b) & (vsc["b"] <= hi_b)])
        has = np.isin(grid, np.unique(np.floor(pos_grid + 1e-6)))
        vperfs = []
        for n in plist:
            n = n[(n["beat"] >= lo_b) & (n["beat"] <= hi_b)]
            vperfs.append((n["beat"].to_numpy(float), n["onset_sec"].to_numpy(float),
                           n["vel_midi"].to_numpy(float)))
        vT, vV, _ = _curves_matrix(vperfs, grid, pos_grid, bpb, has)
        rng = np.random.default_rng(0)
        pool = rng.choice(ids, min(300, len(ids)), replace=False)
        m = df[df["performance_id"].isin(set(pool)) & (df["label"] == "match")]
        m = m[(m["s_onset_beat"] >= lo_b + dlt) & (m["s_onset_beat"] <= hi_b + dlt)]
        pperfs = [(g["s_onset_beat"].to_numpy(float) - dlt, g["p_onset_sec"].to_numpy(float),
                   g["p_velocity"].to_numpy(float))
                  for _, g in m.groupby("performance_id", observed=True) if len(g) >= 8]
        pT, pV, _ = _curves_matrix(pperfs, grid, pos_grid, bpb, has)
        nv = len(vT)
        for blk, fv, fp in (("tempo", vT, pT), ("vel_smooth", vV, pV),
                            ("joint", joint(vT, vV), None)):
            real = _small_stats(fv)
            subs = []
            for _ in range(50):
                r = np.sort(rng.choice(len(pT), nv, replace=False))
                x = fp[r] if fp is not None else joint(pT[r], pV[r])
                subs.append(_small_stats(x))
            sd = pd.DataFrame(subs)
            row = {"piece_id": pid, "block": blk, "n_vienna": nv, "n_pool": len(pT),
                   "beats": len(grid), "offset": dlt, "mapped_frac": frac}
            for k, v in real.items():
                row[f"vienna_{k}"] = v
                row[f"trans_{k}_median"] = float(sd[k].median())
                row[f"trans_{k}_p05"] = float(sd[k].quantile(0.05))
                row[f"trans_{k}_p95"] = float(sd[k].quantile(0.95))
            rows.append(row)
    out = pd.DataFrame(rows)
    out.to_csv(ART / "vienna_control.csv", index=False)
    cols = ["piece_id", "block", "n_vienna", "n_pool", "beats", "vienna_k80_in",
            "trans_k80_in_median", "vienna_pc1", "trans_pc1_median", "trans_pc1_p05",
            "trans_pc1_p95", "vienna_loo_r2_k3", "trans_loo_r2_k3_median"]
    print(out[cols].to_string())


def main() -> None:
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("pieces")
    p.add_argument("--workers", type=int, default=13)
    p.add_argument("--limit", type=int, default=0)
    p = sp.add_parser("disklavier")
    p.add_argument("--workers", type=int, default=13)
    p.add_argument("--min-d", type=int, default=8)
    sp.add_parser("vienna")
    sp.add_parser("figures")
    sp.add_parser("summarize")
    args = ap.parse_args()
    FIG.mkdir(parents=True, exist_ok=True)
    if args.cmd == "pieces":
        cmd_pieces(args)
    elif args.cmd == "disklavier":
        cmd_disklavier(args)
    elif args.cmd == "vienna":
        cmd_vienna(args)
    elif args.cmd == "figures":
        from report import cmd_figures

        cmd_figures()
    else:
        from report import cmd_summarize

        cmd_summarize()


if __name__ == "__main__":
    main()
