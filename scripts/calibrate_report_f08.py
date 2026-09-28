"""F-08 calibration: what the correctness pipeline reports per bar on clean expert playing.

Run: ``uv run python scripts/calibrate_report_f08.py [--workers 12]``

The practice report (``pianolens.report``) ranks correctness issues with the same two tiers as
the tier D flags (DECISIONS 2026-09-28, after F-06): "notable" beyond the 95th percentile of
expert bars, "strong" beyond the 99th. For correctness, the expert bars are the clean copies
(rate 0) of the D-08 mistake set: 100 (n)ASAP performances, aligned with
``align_performance`` and labelled with ``correctness`` exactly as in production. Their
"errors" are real slips plus alignment and ground-truth noise, i.e. what the pipeline reports
on expert playing.

Output (gitignored): ``data/interim/reports/calibration/correctness_bars.parquet`` (one row per
bar) and ``correctness_quantiles.json``. The quantiles are copied into
``pianolens.report.calibration`` by hand; rerunning the script reproduces them.
"""

from __future__ import annotations

import argparse
import json
import warnings
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "data" / "interim" / "reports" / "calibration"
_STATE: dict = {}


def _init() -> None:
    warnings.filterwarnings("ignore")
    from pianolens.data import asap
    from pianolens.data.perturb import load_mistake_set

    index, get = load_mistake_set(REPO / "data" / "processed" / "mistakes_v1")
    _STATE["get"] = get
    _STATE["index"] = index.set_index("key")
    _STATE["asap"] = asap.asap_index().set_index("performance_id", drop=False)


def run_one(key: str) -> pd.DataFrame:
    from pianolens.align import align_performance
    from pianolens.data import asap
    from pianolens.features.correctness import correctness

    perf, _ = _STATE["get"](key)
    row = _STATE["asap"].loc[_STATE["index"].loc[key, "performance_id"]]
    ap = align_performance(asap.load_asap_score(row), perf)
    bars = correctness(ap).bars
    bars = bars[bars["n_score_notes"] > 0].copy()
    bars["key"] = key
    bars["piece_id"] = row["piece_id"]
    return bars[["key", "piece_id", "measure_index", "n_score_notes", "n_wrong_pitch",
                 "n_missed", "n_extra", "n_errors"]]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--from-cache", action="store_true",
                    help="reuse correctness_bars.parquet instead of re-aligning")
    args = ap.parse_args()
    if args.from_cache:
        bars = pd.read_parquet(OUT / "correctness_bars.parquet")
    else:
        _init()
        keys = [k for k, r in _STATE["index"].iterrows() if float(r["rate"]) == 0.0]
        with ProcessPoolExecutor(args.workers, initializer=_init) as ex:
            parts = list(ex.map(run_one, keys))
        bars = pd.concat(parts, ignore_index=True)
        OUT.mkdir(parents=True, exist_ok=True)
        bars.to_parquet(OUT / "correctness_bars.parquet")
    bars["n_missed_extra"] = bars["n_missed"] + bars["n_extra"]
    out = {"n_performances": int(bars["key"].nunique()), "n_bars": len(bars),
           "n_pieces": int(bars["piece_id"].nunique())}
    for col in ("n_errors", "n_missed_extra", "n_wrong_pitch"):
        out[col] = {f"q{int(q * 100)}": float(np.quantile(bars[col], q))
                    for q in (0.5, 0.9, 0.95, 0.99)}
        out[col]["share_nonzero"] = float((bars[col] > 0).mean())
    # the same per graded score note in the bar (bars differ in note count)
    rate = bars["n_missed_extra"] / bars["n_score_notes"]
    out["missed_extra_per_note"] = {f"q{int(q * 100)}": float(np.quantile(rate, q))
                                    for q in (0.5, 0.9, 0.95, 0.99)}
    for k in (1, 2, 3):
        out["n_wrong_pitch"][f"share_ge{k}"] = float((bars["n_wrong_pitch"] >= k).mean())
    out["share_bars_any_error_per_performance"] = {
        f"q{int(q * 100)}": float(np.quantile(
            bars.groupby("key")["n_errors"].apply(lambda x: (x > 0).mean()), q))
        for q in (0.05, 0.5, 0.95)}
    per = bars.groupby("key")[["n_errors", "n_score_notes"]].sum()
    er = per["n_errors"] / per["n_score_notes"]
    out["error_rate_per_performance"] = {f"q{int(q * 100)}": float(np.quantile(er, q))
                                         for q in (0.05, 0.5, 0.95, 0.99)}
    (OUT / "correctness_quantiles.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
