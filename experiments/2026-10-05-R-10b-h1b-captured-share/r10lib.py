"""R-10 (H1b) shared code: R-02 curves, R-02 audit shared components, captured shares.

Everything here follows the pre-registration in README.md. Nothing in this file looks at a model;
the model enters only as a (K x beats) matrix of sample curves.

* Expert curves are computed exactly as R-02 (`curves.py` `grid_curves` / `score_grids`, imported
  from the R-02 folder), from the same note columns the PianoCoRe cache holds
  (`pianocore_cache.aligned_columns`).
* QC and blocks follow R-02 `analyze.load_blocks` (10% / 10% missing rules, nearest fill, row
  centring, Whittaker velocity smoothing at 1.5 bars) and R-02 `joint` (each block scaled to unit
  mean total variance).
* Shared components follow the R-02 audit: whole piece, n = 50 reference performances, envelope
  surrogate (phase randomisation with shared phases for the tempo and velocity rows, then each
  column rescaled to the real per-beat s.d.), parallel analysis at the 95th percentile of 20
  surrogates; k = number of leading eigenvalues above the null.
* A sampler (model samples, held-out experts, or a null) is scored by the share of the reference's
  shared-component variance that lies in the span of its centred curves (R-07 (b) statistic), on
  the same beats and with the same block scales.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd

from pianolens.eval.dimensionality import (
    explained_variance_ratio,
    phase_randomize,
    whittaker_smooth,
)

HERE = Path(__file__).resolve().parent
R02_DIR = HERE.parent / "2026-09-27-R-02-expression-dimensionality"

# R-02 constants (analyze.py), unchanged
N_REF = 50
MISS_BEAT = 0.10
MISS_PERF = 0.10
CUTOFF_BARS = 1.5
# R-02 audit parallel analysis
N_SURR = 20
PA_Q = 0.95
# R-10 pre-registered
N_CEIL_DRAWS = 5  # held-out expert draws per piece (averaged)
REF_SEED = 0  # R-02 subsample seed
# deciding statistic (README): null-adjusted span capture of the shared components
DECIDING_BASE = "c_shared"

NOTE_COLS = ["performance_id", "label", "s_onset_beat", "s_is_grace", "s_ts_beats", "s_measure",
             "p_onset_sec", "p_velocity"]


def _r02_curves():
    spec = importlib.util.spec_from_file_location("r02_curves", R02_DIR / "curves.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


_R02 = None


def r02():
    global _R02
    if _R02 is None:
        _R02 = _r02_curves()
    return _R02


def slug(s: str) -> str:
    return "".join(c if c.isalnum() or c in "-." else "_" for c in s)[:120]


# ----------------------------------------------------------------------------- selection


def majority_rows(idx: pd.DataFrame, piece_id: str) -> pd.DataFrame:
    """Tier A rows of the piece's majority refined score (R-02 rule), all sources."""
    g = idx[idx["piece_id"] == piece_id]
    key = g["refined_score_midi_path"].value_counts().index[0]
    return g[g["refined_score_midi_path"] == key].sort_values("id")


# ----------------------------------------------------------------------------- prep (experts)


def prep_piece(root: str, piece_id: str, rows: pd.DataFrame, out: Path) -> dict:
    """Expert curves (R-02 format), the score-note beat table and the whole-piece generation item.

    Writes out/curves/<slug>.npz, out/score_notes/<slug>.npz, out/gen_items/<slug>.npz and returns
    a log row. Resumable: returns early if all three exist."""
    from pianolens.data.pianocore import PianoCoRe
    from pianolens.data.pianocore_cache import aligned_columns
    from pianolens.models.expression_data import interchange_from_aligned, save_item

    s = slug(piece_id)
    paths = {k: out / k / f"{s}.npz" for k in ("curves", "score_notes", "gen_items")}
    if all(p.exists() for p in paths.values()):
        return {"piece_id": piece_id, "skipped": True}
    for p in paths.values():
        p.parent.mkdir(parents=True, exist_ok=True)
    pc = PianoCoRe(root)
    frames, items, meta, errors = [], [], [], []
    score = None
    for _, row in rows.iterrows():
        try:
            ap = pc.load(row)
        except Exception as e:  # noqa: BLE001 - record and continue
            errors.append(f"{row['id']}: load {e!r}"[:200])
            continue
        score = ap.score
        cols = aligned_columns(ap)
        frames.append(pd.DataFrame({c: cols[c] for c in NOTE_COLS + ["s_id", "performer_id"]}))
        item, info = interchange_from_aligned(ap)
        if item is not None:
            items.append(item)
        meta.append({"row_id": row["id"], "performance_id": ap.performance.performance_id,
                     "performer_id": str(ap.performance.performer_id),
                     "provenance": ap.performance.provenance,
                     "capture_model": str(row["capture_model"]),
                     "match_share": float(info.get("match_share", np.nan))})
    pc.close()
    if score is None or not frames:
        return {"piece_id": piece_id, "error": "no performance loaded", "errors": errors[:5]}
    df = pd.concat(frames, ignore_index=True)
    perf_ids = [m["performance_id"] for m in meta]
    R = r02()
    sc = df[(df["s_is_grace"] == 0) & df["s_onset_beat"].notna()]
    first = sc["performance_id"].iloc[0]
    grid, pos_grid, has, bars, bpb = R.score_grids(sc[sc["performance_id"] == first])
    m = sc[(sc["label"] == "match") & sc["p_onset_sec"].notna()]
    n, p, q = len(perf_ids), len(grid), len(pos_grid)
    T = np.full((n, p), np.nan, np.float32)
    TO = np.zeros((n, p), bool)
    V = np.full((n, p), np.nan, np.float32)
    Rr = np.full((n, q), np.nan, np.float32)
    ok = np.zeros(n, bool)
    groups = dict(tuple(m.groupby("performance_id")))
    for i, pid in enumerate(perf_ids):
        d = groups.get(pid)
        if d is None or len(d) < 8:
            errors.append(f"{pid}: too few matched notes")
            continue
        try:
            c = R.grid_curves(d["s_onset_beat"].to_numpy(float), d["p_onset_sec"].to_numpy(float),
                              d["p_velocity"].to_numpy(float), grid, pos_grid, bpb)
        except Exception as e:  # noqa: BLE001
            errors.append(f"{pid}: {type(e).__name__}: {e}"[:200])
            continue
        T[i], TO[i], V[i], Rr[i] = c["T"], c["Tobs"], c["V"], c["R"]
        ok[i] = True
    M = pd.DataFrame(meta)
    np.savez_compressed(
        paths["curves"], piece_id=piece_id, perf_ids=np.array(perf_ids),
        row_ids=M["row_id"].to_numpy(str), performer_ids=M["performer_id"].to_numpy(str),
        provenance=M["provenance"].to_numpy(str), capture_model=M["capture_model"].to_numpy(str),
        ok=ok, grid=grid, pos_grid=pos_grid, has_onset=has, bar_starts=bars, bpb=bpb,
        T=T, Tobs=TO, V=V, R=Rr)
    notes = score.notes
    np.savez_compressed(paths["score_notes"], s_id=notes["id"].astype(str),
                        onset_beat=notes["onset_beat"].astype(float),
                        is_grace=notes["is_grace"].astype(int))
    # whole-piece generation item: union of matched score notes over all renditions (R-07 rule,
    # without the 3,000-note cap); conditioning = median over renditions
    sid = np.concatenate([i["score_id"] for i in items])
    on = np.concatenate([i["score_onset_q"] for i in items])
    du = np.concatenate([i["score_dur_q"] for i in items])
    pi = np.concatenate([i["pitch"] for i in items])
    _, firsti = np.unique(sid, return_index=True)
    order = firsti[np.lexsort((pi[firsti], on[firsti]))]
    z = np.zeros(len(order))
    gen = {"score_onset_q": on[order], "score_dur_q": du[order], "pitch": pi[order],
           "perf_onset_sec": z, "perf_dur_sec": z, "velocity": z.astype(int),
           "pedal": np.zeros((0, 2)), "score_id": sid[order],
           "spq_cond": float(np.median([i["spq_cond"] for i in items])),
           "vel_cond": float(np.median([i["vel_cond"] for i in items])),
           "origin": float(items[0]["origin"]), "ts": items[0]["ts"]}
    save_item(paths["gen_items"], gen)
    return {"piece_id": piece_id, "n": n, "n_ok": int(ok.sum()), "n_beats": p,
            "gen_notes": len(order), "n_errors": len(errors), "errors": errors[:5],
            "n_performer_known": int(np.sum(~M["performer_id"].str.contains("unknown"))),
            "n_performer_distinct": int(M["performer_id"].nunique())}


# ----------------------------------------------------------------------------- model curves


def sample_curves(gen_item: dict, gen_out: dict, score_notes: dict, grid, pos_grid, bpb
                  ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """R-02 curves (T, Tobs, V on the expert grid) of each generated sample."""
    R = r02()
    lut = {s: i for i, s in enumerate(score_notes["s_id"].tolist())}
    ix = np.array([lut.get(s, -1) for s in gen_item["score_id"].astype(str).tolist()])
    beats = np.where(ix >= 0, score_notes["onset_beat"][np.clip(ix, 0, None)], np.nan)
    grace = np.where(ix >= 0, score_notes["is_grace"][np.clip(ix, 0, None)], 1).astype(bool)
    keep = np.isfinite(beats) & ~grace
    on, ve = np.asarray(gen_out["onset"]), np.asarray(gen_out["vel"])
    k = on.shape[0]
    T = np.full((k, len(grid)), np.nan)
    TO = np.zeros((k, len(grid)), bool)
    V = np.full((k, len(grid)), np.nan)
    for i in range(k):
        ok = keep & np.isfinite(on[i]) & np.isfinite(ve[i])
        c = R.grid_curves(beats[ok], on[i, ok], ve[i, ok], grid, pos_grid, bpb)
        T[i], TO[i], V[i] = c["T"], c["Tobs"], c["V"]
    return T, TO, V


# ----------------------------------------------------------------------------- QC and blocks


def _fill_nearest(row: np.ndarray) -> np.ndarray:
    ok = np.isfinite(row)
    if ok.all() or not ok.any():
        return row
    x = np.arange(len(row))
    return np.interp(x, x[ok], row[ok])


def _center_rows(x: np.ndarray) -> np.ndarray:
    return x - x.mean(axis=1, keepdims=True)


def expert_qc(z) -> dict | None:
    """R-02 load_blocks QC on all of a piece's performances; returns kept rows and beat columns."""
    ok = z["ok"]
    T, TO, V = z["T"].astype(float), z["Tobs"], z["V"].astype(float)
    has = z["has_onset"]
    if ok.sum() < 3:
        return None
    rows = np.where(ok)[0]
    tobs = TO[rows] & np.isfinite(T[rows])
    beat_keep = tobs.mean(axis=0) >= 1 - MISS_BEAT
    if beat_keep.sum() < 8:
        return None
    vgrid = beat_keep & has
    vobs = np.isfinite(V[rows][:, vgrid])
    vcols = np.where(vgrid)[0][vobs.mean(axis=0) >= 1 - MISS_BEAT]
    perf_ok = (tobs[:, beat_keep].mean(axis=1) >= 1 - MISS_PERF) & (
        np.isfinite(V[rows][:, vcols]).mean(axis=1) >= 1 - MISS_PERF)
    return {"rows": rows[perf_ok], "cols": np.where(beat_keep)[0], "vcols": vcols,
            "period": CUTOFF_BARS * float(z["bpb"]), "n_ok": int(ok.sum())}


def blocks(T: np.ndarray, V: np.ndarray, cols: np.ndarray, period: float):
    """Smooth tempo and smooth velocity blocks on the kept beats (R-02 load_blocks)."""
    Tk = _center_rows(np.vstack([_fill_nearest(r) for r in T[:, cols].astype(float)]))
    Vt = np.vstack([_fill_nearest(r) for r in V[:, cols].astype(float)])
    Vs = _center_rows(whittaker_smooth(Vt, period))
    return Tk, Vs


def block_scale(x: np.ndarray) -> float:
    """R-02 joint(): root mean total variance of the column-centred block."""
    return float(np.sqrt(((x - x.mean(0)) ** 2).sum() / len(x)))


# ----------------------------------------------------------------------------- shared components


def envelope_surrogate(dT: np.ndarray, dV: np.ndarray, rng) -> tuple[np.ndarray, np.ndarray]:
    """R-02 phase null (shared phases for a row's tempo and velocity), then each column rescaled
    to the real per-beat s.d. (the R-02 audit 'envelope' null)."""
    pT, pV = phase_randomize([dT, dV / dV.std() * dT.std()], rng)
    pV = pV / dT.std() * dV.std()
    out = []
    for real, s in ((dT, pT), (dV, pV)):
        s = s - s.mean(0)
        out.append(s / (s.std(0) + 1e-12) * real.std(0))
    return out[0], out[1]


def shared_components(Tr: np.ndarray, Vr: np.ndarray, seed: int = 0) -> dict:
    """Parallel analysis of the reference joint block against N_SURR envelope surrogates."""
    sT, sV = block_scale(Tr), block_scale(Vr)
    dT, dV = Tr - Tr.mean(0), Vr - Vr.mean(0)
    J = np.hstack([dT / sT, dV / sV])
    ev = explained_variance_ratio(J)
    rng = np.random.default_rng(seed)
    null = []
    for _ in range(N_SURR):
        eT, eV = envelope_surrogate(dT, dV, rng)
        null.append(explained_variance_ratio(np.hstack([eT / block_scale(eT),
                                                        eV / block_scale(eV)])))
    q = np.quantile(np.array(null), PA_Q, axis=0)
    above = ev[: len(q)] > q
    k = int(np.argmin(above)) if not above.all() else len(q)
    _, _, Vt = np.linalg.svd(J, full_matrices=False)
    U = Vt[:k]
    Ds = J @ U.T @ U
    return {"k": k, "share_k": float(ev[:k].sum()), "sT": sT, "sV": sV, "mT": Tr.mean(0),
            "mV": Vr.mean(0), "J": J, "U": U, "Ds": Ds, "Di": J - Ds, "ev": ev, "null_q": q}


def joint_of(T: np.ndarray, V: np.ndarray, sc: dict) -> np.ndarray:
    """A sampler's curves centred on its own mean, in the reference's joint units."""
    return np.hstack([(T - T.mean(0)) / sc["sT"], (V - V.mean(0)) / sc["sV"]])


def span_basis(Y: np.ndarray) -> np.ndarray:
    _, s, Wt = np.linalg.svd(Y, full_matrices=False)
    if s.max() <= 0:
        return np.zeros((Y.shape[1], 0))
    return Wt[s > 1e-9 * s.max()].T


def captured(sc: dict, T: np.ndarray, V: np.ndarray) -> dict:
    """Captured shares of one sampler (K curves) against the reference components."""
    Y = joint_of(T, V, sc)
    Q = span_basis(Y)
    out = {"dims": int(Q.shape[1])}
    tot_i = np.sum(sc["Di"] ** 2)
    out["c_ind"] = float(np.sum((sc["Di"] @ Q) ** 2) / tot_i) if tot_i > 0 else np.nan
    if sc["k"] > 0:
        out["c_shared"] = float(np.sum((sc["Ds"] @ Q) ** 2) / np.sum(sc["Ds"] ** 2))
        # secondary: the sampler's own top-k principal subspace (magnitude-aware)
        _, _, Wt = np.linalg.svd(Y, full_matrices=False)
        Qk = Wt[: sc["k"]].T
        out["c_shared_topk"] = float(np.sum((sc["Ds"] @ Qk) ** 2) / np.sum(sc["Ds"] ** 2))
    else:
        out["c_shared"] = out["c_shared_topk"] = np.nan
    # mean-curve centred R² against the reference mean (per block)
    for name, m, p in (("T", sc["mT"], T.mean(0)), ("V", sc["mV"], V.mean(0))):
        den = np.sum((m - m.mean()) ** 2)
        out[f"r2c_{name}"] = float(1 - np.sum((m - p) ** 2) / den) if den > 0 else np.nan
    return out


def smooth_noise(n: int, p: int, period: float, rng) -> np.ndarray:
    w = whittaker_smooth(rng.normal(size=(n, p)), period)
    return w / (w.std() + 1e-12)


# ----------------------------------------------------------------------------- per piece


def analyse_piece(z, samplers: dict[str, tuple[np.ndarray, np.ndarray]], K: int,
                  extra_null: bool = True) -> dict | None:
    """All statistics of one piece.

    ``samplers``: arm -> (T, V) raw sample curves on the piece grid (K rows, T with NaN outside
    the span; QC'd onto the expert beats here). Returns None if the piece fails QC or has fewer
    than N_REF + K kept performances."""
    qc = expert_qc(z)
    if qc is None:
        return None
    rows, cols, per = qc["rows"], qc["cols"], qc["period"]
    info = {"n_ok": qc["n_ok"], "n_kept": len(rows), "beats": len(cols)}
    if len(rows) < N_REF + K:
        return {**info, "eligible": False}
    T, V = z["T"], z["V"]
    rng = np.random.default_rng(REF_SEED)
    ref = np.sort(rng.choice(rows, N_REF, replace=False))
    pool = np.setdiff1d(rows, ref)
    Tr, Vr = blocks(T[ref], V[ref], cols, per)
    sc = shared_components(Tr, Vr, seed=0)
    out = {**info, "eligible": True, "k": sc["k"], "share_k": sc["share_k"],
           "pool": len(pool), "d": 2 * len(cols), "random_c": (K - 1) / (2 * len(cols))}
    # expert-as-sampler ceiling: N_CEIL_DRAWS draws of K held-out performances; envelope-null
    # and smooth-noise samplers built from the same draws
    acc: dict[str, list[dict]] = {"expert": [], "env_null": [], "smooth_null": []}
    for d in range(N_CEIL_DRAWS):
        r = np.random.default_rng(1000 + d)
        h = np.sort(r.choice(pool, K, replace=False))
        Th, Vh = blocks(T[h], V[h], cols, per)
        acc["expert"].append(captured(sc, Th, Vh))
        if extra_null:
            eT, eV = envelope_surrogate(Th - Th.mean(0), Vh - Vh.mean(0), r)
            acc["env_null"].append(captured(sc, eT + Th.mean(0), eV + Vh.mean(0)))
            nT = smooth_noise(K, len(cols), per, r) * Th.std()
            nV = smooth_noise(K, len(cols), per, r) * Vh.std()
            acc["smooth_null"].append(captured(sc, nT, nV))
    for name, lst in acc.items():
        if lst:
            for key in lst[0]:
                out[f"{name}_{key}"] = float(np.nanmean([x[key] for x in lst]))
    for arm, (Ts, Vs_) in samplers.items():
        Ts_b, Vs_b = blocks(np.asarray(Ts)[:K], np.asarray(Vs_)[:K], cols, per)
        for key, v in captured(sc, Ts_b, Vs_b).items():
            out[f"{arm}_{key}"] = v
        out[f"{arm}_n_samples"] = int(min(K, len(Ts)))
    return out


# ----------------------------------------------------------------------------- summary


def ratio_of_means(df: pd.DataFrame, num: str, den: str) -> float:
    return float(df[num].sum() / df[den].sum())


def cluster_boot(df: pd.DataFrame, stat, cluster: str = "work", n: int = 2000, seed: int = 0):
    """Percentile CI, resampling clusters (works) with replacement."""
    groups = [g for _, g in df.groupby(cluster)]
    rng = np.random.default_rng(seed)
    bs = []
    for _ in range(n):
        pick = rng.integers(0, len(groups), len(groups))
        bs.append(stat(pd.concat([groups[i] for i in pick], ignore_index=True)))
    bs = np.array(bs, float)
    lo, hi = np.nanpercentile(bs, [2.5, 97.5])
    return float(stat(df)), float(lo), float(hi)


def reading(lo: float, hi: float, point: float) -> str:
    """Pre-registered H1b reading of the calibrated ratio (README 'Falsified if')."""
    if lo >= 0.50:
        return "supported"
    if hi <= 0.20:
        return "falsified"
    return "inconclusive (point above 0.50)" if point >= 0.50 else (
        "inconclusive (point at or below 0.20)" if point <= 0.20 else "inconclusive")
