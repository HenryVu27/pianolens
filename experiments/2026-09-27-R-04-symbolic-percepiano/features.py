"""R-04 step 1: align every PercePiano segment to its segment score and extract features.

One worker per passage (all performances of one notated excerpt), because reference features
need the other performances of the same passage, and aligned performances do not pickle.
References = the other *human* performances of the passage (never Score renditions).

    uv run python experiments/2026-09-27-R-04-symbolic-percepiano/features.py [--workers 14]

Writes `artifacts/features.parquet` and `artifacts/features_meta.json`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
import warnings
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ART = HERE / "artifacts"


def passage_of(df: pd.DataFrame) -> pd.Series:
    return df["work"] + "_" + df["bars"].astype(str) + "b_" + df["segment"].astype(str)


def _one_passage(rows: list[dict]) -> tuple[pd.DataFrame, list[tuple[str, str]], float]:
    warnings.filterwarnings("ignore")
    import logging

    logging.disable(logging.WARNING)
    from pianolens.align import align_performance
    from pianolens.data.percepiano import load_percepiano_performance, load_percepiano_score
    from pianolens.features.extract import group_features

    t0 = time.time()
    aps, keep, failed = [], [], []
    for r in rows:
        row = pd.Series(r)
        score, perf = load_percepiano_score(row), load_percepiano_performance(row)
        try:
            ap = align_performance(score, perf)
        except Exception as e:  # noqa: BLE001 - parangonar's ornament step can crash
            try:
                ap = align_performance(score, perf, process_ornaments=False)
                failed.append((r["performance_id"], "retried without ornaments: " + repr(e)))
            except Exception as e2:  # noqa: BLE001 - count and continue
                failed.append((r["performance_id"], repr(e2)))
                continue
        aps.append(ap)
        keep.append(r)
    if not aps:
        return pd.DataFrame(), failed, time.time() - t0
    is_ref = [not str(r["player"]).startswith("Score") for r in keep]
    df = group_features(aps, is_ref)
    return df, failed, time.time() - t0


def main() -> None:
    from pianolens.data.percepiano import percepiano_index

    p = argparse.ArgumentParser()
    p.add_argument("--workers", type=int, default=14)
    a = p.parse_args()
    ART.mkdir(parents=True, exist_ok=True)
    idx = percepiano_index()
    idx["passage"] = passage_of(idx)
    t0 = time.time()
    groups = [g.to_dict("records") for _, g in idx.groupby("passage", sort=True)]
    out, failed, times = [], [], []
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        futs = [ex.submit(_one_passage, g) for g in groups]
        for i, f in enumerate(as_completed(futs)):
            df, fl, dt = f.result()
            out.append(df)
            failed += fl
            times.append(dt)
            if (i + 1) % 20 == 0:
                print(f"{i + 1}/{len(groups)} passages, {time.time() - t0:.0f}s", flush=True)
    feats = pd.concat(out, ignore_index=True)
    meta_cols = ["performance_id", "passage", "work", "piece_id", "performer_id", "player",
                 "bars", "segment", "provenance"]
    feats = idx[meta_cols].merge(feats, on="performance_id", how="inner")
    feats["is_score"] = feats["player"].str.startswith("Score")
    feats = feats.sort_values("performance_id").reset_index(drop=True)
    feats.to_parquet(ART / "features.parquet", index=False)
    err = feats["errors"].str.split(";").explode()
    meta = {
        "n_segments": int(len(idx)), "n_passages": len(groups), "n_featurized": int(len(feats)),
        "n_align_issues": len(failed), "align_issues": failed,
        "component_errors": err[err != ""].value_counts().to_dict(),
        "wall_sec": round(time.time() - t0, 1),
        "passage_sec_median": round(float(pd.Series(times).median()), 2),
        "n_feature_columns": int(sum("__" in c for c in feats.columns)),
        "control_py_sha256": hashlib.sha256(
            (HERE.parents[1] / "src/pianolens/features/control.py").read_bytes()).hexdigest()[:12],
    }  # fmt: skip
    (ART / "features_meta.json").write_text(json.dumps(meta, indent=2))
    print(json.dumps({k: v for k, v in meta.items() if k != "align_issues"}, indent=2))


if __name__ == "__main__":
    main()
