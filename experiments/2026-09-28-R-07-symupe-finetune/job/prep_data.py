"""R-07 data prep (project env): PianoCoRe tier A + (n)ASAP -> interchange items, split enforced.

Reads the committed split (``../split/pieces.csv``) and writes, under ``--out``:

  items/<split>/<piece slug>/<performance>.npz   one interchange item per performance
                                                 (pianolens.models.expression_data)
  manifest.parquet                               one row per item (ids, split, role, source,
                                                 counts, conditioning)
  leakage_report.json                            pianolens.models.expression_split.leakage_check
                                                 over every train row; the script fails on any
                                                 violation, before anything is trained
  prep_meta.json                                 arguments, counts, wall time

Selection (pre-registered in the README):
  * PianoCoRe tier A rows of train / val pieces, minus rows whose source is ASAP (the (n)ASAP
    ground-truth versions are used instead); at most ``--cap`` performances per piece, drawn
    with a per-piece seed; items with matched share < ``--min-match`` are dropped.
  * Test pieces (roles R10u / R10s): the same rule with ``--test-cap`` (evaluation curves).
    P / V / A test sets are evaluated on the R-06 items, not built here.
  * (n)ASAP performances with a robust ground-truth alignment of train / val pieces.

Usage (GPU box or Mac):
    python prep_data.py --pianocore $DATA/pianocore --asap $DATA/asap --out $OUT/data \\
        --workers 12
    python prep_data.py ... --dry-run   # 6 train, 2 val, 2 test pieces, 3 perfs each
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import time
import zlib
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
SPLIT = HERE.parent / "split" / "pieces.csv"
SEED = 20260928
log = logging.getLogger("r07.prep")


def slug(s: str) -> str:
    return "".join(c if c.isalnum() or c in "-." else "_" for c in s)[:120]


def select_pianocore(idx: pd.DataFrame, split: pd.DataFrame, cap: int, test_cap: int,
                     dry_run: bool) -> pd.DataFrame:
    """Rows to load: one per selected performance, with split / role / work columns."""
    sp = split.set_index("piece_id")
    idx = idx[idx["piece_id"].isin(sp.index)].copy()
    idx["split"] = idx["piece_id"].map(sp["split"])
    idx["role"] = idx["piece_id"].map(sp["role"])
    idx["work"] = idx["piece_id"].map(sp["work"])
    idx = idx[idx["performance_dataset"] != "ASAP"]
    keep = idx["split"].isin(["train", "val"]) | idx["role"].isin(["R10u", "R10s"])
    idx = idx[keep]
    if dry_run:  # shortest scores first, fixed piece counts per split
        per = (idx.groupby("piece_id")
               .agg(split=("split", "first"), role=("role", "first"), n=("id", "size"),
                    notes=("refined_score_note_count", "median"))
               .reset_index())
        per = per[per["n"] >= 3].sort_values(["notes", "piece_id"])
        pick = pd.concat([per[per["split"] == "train"].head(6), per[per["split"] == "val"].head(2),
                          per[per["role"] == "R10u"].head(2)])
        idx = idx[idx["piece_id"].isin(pick["piece_id"])]
        cap = test_cap = 3
    out = []
    for pid, g in idx.groupby("piece_id", sort=True):
        c = test_cap if g["split"].iloc[0] == "test" else cap
        rng = np.random.default_rng(SEED + zlib.crc32(pid.encode()) % 100_003)
        ids = np.sort(g["id"].to_numpy())
        take = ids if len(ids) <= c else np.sort(rng.choice(ids, size=c, replace=False))
        out.append(g[g["id"].isin(take)])
    return pd.concat(out, ignore_index=True) if out else idx.iloc[:0]


def _pianocore_piece(args) -> list[dict]:
    root, rows, out, min_match = args
    from pianolens.data.pianocore import PianoCoRe
    from pianolens.models.expression_data import interchange_from_aligned, save_item

    pc = PianoCoRe(root)
    res = []
    rows = rows.sort_values("refined_score_midi_path", kind="stable")
    for _, row in rows.iterrows():
        base = {"source": "pianocore", "row_id": row["id"], "piece_id": row["piece_id"],
                "work": row["work"], "split": row["split"], "role": row["role"],
                "source_dataset": row["performance_dataset"],
                "source_performance_id": row["performance_id"],
                "tier_a_star": bool(row["tier_a_star"]), "capture_model": row["capture_model"],
                "score_key": row["refined_score_midi_path"]}
        try:
            ap = pc.load(row)
            item, info = interchange_from_aligned(ap)
        except Exception as e:  # noqa: BLE001 - record and continue
            res.append({**base, "item": "", "excluded": f"load_error: {e!r}"[:200]})
            continue
        if item is not None and info["match_share"] < min_match:
            info["excluded"] = "match_share"
        if item is None or info["excluded"]:
            res.append({**base, **info, "item": ""})
            continue
        rel = Path("items") / row["split"] / slug(row["piece_id"]) / f"{slug(row['id'])}.npz"
        (out / rel).parent.mkdir(parents=True, exist_ok=True)
        save_item(out / rel, item)
        res.append({**base, **info, "item": str(rel), "spq_cond": item["spq_cond"],
                    "vel_cond": item["vel_cond"]})
    pc.close()
    return res


def _asap_folder(args) -> list[dict]:
    root, rows, out, min_match = args
    from pianolens.data.asap import iter_asap
    from pianolens.models.expression_data import interchange_from_aligned, save_item

    res = []
    meta = rows.set_index("performance_id")
    for ap in iter_asap(root, index=rows):
        if ap.alignment is None:
            continue
        pid = ap.performance.performance_id
        r = meta.loc[pid]
        base = {"source": "asap", "row_id": pid, "piece_id": r["piece_id"], "work": r["work"],
                "split": r["split"], "role": r["role"], "source_dataset": "ASAP",
                "source_performance_id": pid, "tier_a_star": False, "capture_model": "disklavier",
                "score_key": r["xml_score"]}
        item, info = interchange_from_aligned(ap)
        if item is not None and info["match_share"] < min_match:
            info["excluded"] = "match_share"
        if item is None or info["excluded"]:
            res.append({**base, **info, "item": ""})
            continue
        rel = Path("items") / r["split"] / slug(r["piece_id"]) / f"{slug(pid)}.npz"
        (out / rel).parent.mkdir(parents=True, exist_ok=True)
        save_item(out / rel, item)
        res.append({**base, **info, "item": str(rel), "spq_cond": item["spq_cond"],
                    "vel_cond": item["vel_cond"]})
    return res


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pianocore", required=True, help="dir with metadata.csv + refined zip")
    ap.add_argument("--asap", required=True, help="(n)ASAP repo checkout")
    ap.add_argument("--out", required=True)
    ap.add_argument("--split", default=str(SPLIT))
    ap.add_argument("--cap", type=int, default=50)
    ap.add_argument("--test-cap", type=int, default=50)
    ap.add_argument("--min-match", type=float, default=0.8)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-asap", action="store_true")
    a = ap.parse_args(argv)
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    logging.basicConfig(level=logging.WARNING)
    from pianolens.data.asap import asap_index
    from pianolens.data.pianocore import pianocore_index
    from pianolens.models.expression_split import leakage_check

    t0 = time.time()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    split = pd.read_csv(a.split)
    idx = pianocore_index(a.pianocore, tier="a")
    nc = pd.read_csv(Path(a.pianocore) / "metadata.csv", usecols=["id", "refined_score_note_count"])
    idx = idx.merge(nc, on="id", how="left")
    sel = select_pianocore(idx, split, a.cap, a.test_cap, a.dry_run)
    jobs = [(a.pianocore, g, out, a.min_match) for _, g in sel.groupby("piece_id")]
    rows: list[dict] = []
    with ProcessPoolExecutor(a.workers) as ex:
        for r in ex.map(_pianocore_piece, jobs):
            rows.extend(r)
    if not a.no_asap:
        md = asap_index(a.asap)
        sp = split.set_index("piece_id")
        md = md[md["piece_id"].isin(sp.index) & (md["robust_note_alignment"] == 1)].copy()
        for c in ("split", "role", "work"):
            md[c] = md["piece_id"].map(sp[c])
        md = md[md["split"].isin(["train", "val"])]
        if a.dry_run:
            md = md[md["folder"].isin(sorted(md["folder"].unique())[:1])].head(2)
        ajobs = [(a.asap, g, out, a.min_match) for _, g in md.groupby("folder")]
        with ProcessPoolExecutor(a.workers) as ex:
            for r in ex.map(_asap_folder, ajobs):
                rows.extend(r)
    man = pd.DataFrame(rows)
    man.to_parquet(out / "manifest.parquet")
    man.to_csv(out / "manifest.csv", index=False)
    used = man[man["item"] != ""]
    rep = leakage_check(split, used.loc[used["split"] == "train", "piece_id"],
                        raise_on_error=False)
    report = rep.as_dict()
    # second check: no source performance appears in two splits
    dup = used.groupby("source_performance_id")["split"].nunique()
    report["performances_in_two_splits"] = sorted(dup[dup > 1].index.tolist())
    report["split_sha256"] = __import__("hashlib").sha256(Path(a.split).read_bytes()).hexdigest()
    (out / "leakage_report.json").write_text(json.dumps(report, indent=1))
    counts = (used.groupby(["split", "source"]).agg(items=("item", "size"),
                                                   pieces=("piece_id", "nunique"),
                                                   notes=("n_notes", "sum"))
              .reset_index().to_dict("records"))
    meta = {"args": vars(a), "seconds": round(time.time() - t0, 1), "seed": SEED,
            "rows": len(man), "items": len(used),
            "excluded": man.loc[man["item"] == "", "excluded"].str.split(":").str[0]
            .value_counts().to_dict(), "counts": counts}
    (out / "prep_meta.json").write_text(json.dumps(meta, indent=1, default=str))
    print(json.dumps(meta, indent=1, default=str))
    if not rep.ok or report["performances_in_two_splits"]:
        raise SystemExit(f"LEAKAGE: {report}")
    print("leakage check: OK")


if __name__ == "__main__":
    main()
