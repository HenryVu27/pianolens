"""R-02 step 1: per-performance tempo / velocity / residual curves on each piece's score grid.

One npz per piece in ``artifacts/curves/`` (resumable). See README.md, "Curves" and
"Missing data". Nothing is imputed or dropped here: the analysis step applies the QC rules.

    uv run python experiments/2026-09-27-R-02-expression-dimensionality/curves.py --workers 13
"""

from __future__ import annotations

import argparse
import json
import math
import time
import warnings
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ART = HERE / "artifacts"
CURVES = ART / "curves"

NOTE_COLS = ["performance_id", "label", "s_onset_beat", "s_is_grace", "s_ts_beats", "s_measure",
             "p_onset_sec", "p_velocity"]
SUMMARY_KEYS = ["tempo_bpm_geomean", "tempo_log_sd", "jitter_rms_beats", "jitter_mad_beats",
                "n_positions", "n_outliers", "n_pauses", "n_tempo_steps", "edf", "cutoff_beats"]


def grid_curves(
    beats: np.ndarray,
    onsets: np.ndarray,
    vel: np.ndarray,
    grid: np.ndarray,
    pos_grid: np.ndarray,
    bpb: float,
) -> dict:
    """Curves of one performance on the piece grids.

    Returns tempo_log_ratio on ``grid`` (NaN outside the performance's span), a tempo-observed
    mask (non-outlier position within one bar), raw per-beat mean velocity (NaN where no matched
    note starts in [b, b+1)), dev_beats per score position (NaN if unmatched or outlier), and the
    F-03 summary."""
    from pianolens.features import tempo_from_onsets

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        res = tempo_from_onsets(beats, onsets, beats_per_bar=bpb)
    g = res.beats
    t = np.full(len(grid), np.nan)
    gi = np.searchsorted(grid, g["beat"].to_numpy())
    ok = (gi < len(grid)) & (grid[np.clip(gi, 0, len(grid) - 1)] == g["beat"].to_numpy())
    t[gi[ok]] = g["tempo_log_ratio"].to_numpy()[ok]

    pos = res.positions
    good = pos.loc[~pos["outlier"], "beat"].to_numpy()
    lo = np.searchsorted(good, grid - bpb - 1e-9, side="left")
    hi = np.searchsorted(good, grid + bpb + 1e-9, side="right")
    tobs = hi > lo

    vb = np.floor(beats + 1e-6)
    vs = pd.Series(vel).groupby(vb).mean()
    v = np.full(len(grid), np.nan)
    vi = np.searchsorted(grid, vs.index.to_numpy())
    okv = (vi < len(grid)) & (grid[np.clip(vi, 0, len(grid) - 1)] == vs.index.to_numpy())
    v[vi[okv]] = vs.to_numpy()[okv]

    r = np.full(len(pos_grid), np.nan)
    pb = pos["beat"].to_numpy()
    pj = np.searchsorted(pos_grid, pb)
    okp = (pj < len(pos_grid)) & np.isclose(pos_grid[np.clip(pj, 0, len(pos_grid) - 1)], pb)
    okp &= ~pos["outlier"].to_numpy()
    r[pj[okp]] = pos["dev_beats"].to_numpy()[okp]
    summ = {k: float(res.summary.get(k, np.nan)) for k in SUMMARY_KEYS}
    return {"T": t, "Tobs": tobs, "V": v, "R": r, "summary": summ}


def score_grids(sc: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, float]:
    """(beat grid, position grid, score-onset-per-beat mask, bar start beats, beats per bar)."""
    b = sc["s_onset_beat"].to_numpy(dtype=float)
    grid = np.arange(math.ceil(b.min() - 1e-9), math.floor(b.max() + 1e-9) + 1, dtype=float)
    pos_grid = np.unique(b)
    has = np.isin(grid, np.unique(np.floor(b + 1e-6)))
    bars = sc.groupby("s_measure")["s_onset_beat"].min().sort_index().to_numpy(dtype=float)
    bpb = float(np.median(sc["s_ts_beats"].to_numpy()))
    if not np.isfinite(bpb) or bpb <= 0:
        bpb = 4.0
    return grid, pos_grid, has, bars, bpb


def process_piece(piece_id: str, perf_ids: list[str], out: Path) -> dict:
    from pianolens.data import pianocore_cache as pc

    t0 = time.time()
    df = pc.load_piece_notes(piece_id, columns=NOTE_COLS)
    df = df[df["performance_id"].isin(set(perf_ids))]
    sc = df[(df["s_is_grace"] == 0) & df["s_onset_beat"].notna()]
    # score side: every performance shares the score, take one performance's rows
    first = sc["performance_id"].iloc[0]
    grid, pos_grid, has, bars, bpb = score_grids(sc[sc["performance_id"] == first])
    m = sc[(sc["label"] == "match") & sc["p_onset_sec"].notna()]
    n, p, q = len(perf_ids), len(grid), len(pos_grid)
    T = np.full((n, p), np.nan, np.float32)
    TO = np.zeros((n, p), bool)
    V = np.full((n, p), np.nan, np.float32)
    R = np.full((n, q), np.nan, np.float32)
    summ = {k: np.full(n, np.nan) for k in SUMMARY_KEYS}
    ok = np.zeros(n, bool)
    errors: list[str] = []
    groups = dict(tuple(m.groupby("performance_id", observed=True)))
    for i, pid in enumerate(perf_ids):
        d = groups.get(pid)
        if d is None or len(d) < 8:
            errors.append(f"{pid}: too few matched notes")
            continue
        try:
            c = grid_curves(d["s_onset_beat"].to_numpy(float), d["p_onset_sec"].to_numpy(float),
                            d["p_velocity"].to_numpy(float), grid, pos_grid, bpb)
        except Exception as e:  # noqa: BLE001 - record and continue
            errors.append(f"{pid}: {type(e).__name__}: {e}")
            continue
        T[i], TO[i], V[i], R[i] = c["T"], c["Tobs"], c["V"], c["R"]
        for k in SUMMARY_KEYS:
            summ[k][i] = c["summary"][k]
        ok[i] = True
    np.savez_compressed(
        out, piece_id=piece_id, perf_ids=np.array(perf_ids), ok=ok, grid=grid, pos_grid=pos_grid,
        has_onset=has, bar_starts=bars, bpb=bpb, T=T, Tobs=TO, V=V, R=R,
        **{f"s_{k}": v for k, v in summ.items()},
    )
    return {"piece_id": piece_id, "n": n, "n_ok": int(ok.sum()), "n_beats": p, "n_pos": q,
            "bpb": bpb, "sec": time.time() - t0, "errors": errors[:5], "n_errors": len(errors)}


def select_pieces(min_perf: int = 50, min_disklavier: int = 8) -> pd.DataFrame:
    """Performances to extract: majority score of pieces with >= min_perf tier A performances,
    plus pieces with >= min_disklavier Disklavier performances (control)."""
    from pianolens.data import pianocore_cache as pc

    P = pc.load_performances()
    maj = P.groupby("piece_id")["score_id"].agg(lambda s: s.value_counts().index[0])
    P = P[P["score_id"] == P["piece_id"].map(maj)]
    n_all = pc.load_performances().groupby("piece_id").size()
    dk = P[P["provenance"] == "disklavier"].groupby("piece_id").size()
    keep = set(n_all[n_all >= min_perf].index) | set(dk[dk >= min_disklavier].index)
    return P[P["piece_id"].isin(keep)]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=13)
    ap.add_argument("--limit", type=int, default=0, help="first N pieces only (smoke test)")
    ap.add_argument("--pieces", nargs="*", default=None)
    args = ap.parse_args()
    from pianolens.data import pianocore_cache as pc

    CURVES.mkdir(parents=True, exist_ok=True)
    P = select_pieces()
    meta_cols = ["performance_id", "piece_id", "provenance", "source_dataset", "score_id",
                 "tier_a_star", "refined_recall", "n_match", "n_interpolated", "duration_sec"]
    P[meta_cols].to_parquet(ART / "performances_selected.parquet")
    tasks = P.groupby("piece_id")["performance_id"].apply(list)
    tasks = tasks.loc[tasks.map(len).sort_values(ascending=False).index]
    if args.pieces:
        tasks = tasks.loc[args.pieces]
    if args.limit:
        tasks = tasks.iloc[: args.limit]
    todo = [(pid, perfs) for pid, perfs in tasks.items()
            if not (CURVES / f"{pc.piece_slug(pid)}.npz").exists()]
    print(f"{len(tasks)} pieces, {len(todo)} to do, "
          f"{sum(len(x) for _, x in todo)} performances", flush=True)
    t0 = time.time()
    log = []
    with ProcessPoolExecutor(args.workers) as ex:
        futs = {ex.submit(process_piece, pid, perfs, CURVES / f"{pc.piece_slug(pid)}.npz"): pid
                for pid, perfs in todo}
        for k, f in enumerate(as_completed(futs), 1):
            r = f.result()
            log.append(r)
            if k % 25 == 0 or k == len(futs):
                print(f"{k}/{len(futs)} {time.time() - t0:.0f}s last={r['piece_id']} "
                      f"ok={r['n_ok']}/{r['n']}", flush=True)
    with open(ART / "curves_log.jsonl", "a") as fh:
        for r in log:
            fh.write(json.dumps(r) + "\n")
    print(f"done in {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
