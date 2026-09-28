"""Build the note-aligned PianoCoRe tier A cache (D-07, BACKLOG BL-09).

Runs ``pianolens.data.pianocore.PianoCoRe.load`` over every tier A performance, one piece per
task, in a process pool, and writes ``data/processed/pianocore_A`` (layout in
``pianolens.data.pianocore_cache``). Resumable: a piece whose ``_state/<slug>.json`` exists is
skipped, and each piece file is written to a temporary name and renamed when complete. Rerun the
same command after an interruption. ``--consolidate-only`` rewrites the manifests from
``_state`` without loading anything.

Usage:
    uv run python scripts/build_pianocore_cache.py --workers 12
    uv run python scripts/build_pianocore_cache.py --workers 2 --max-pieces 5 --out /tmp/pc
"""

from __future__ import annotations

import argparse
import json
import logging
import multiprocessing as mp
import os
import time
import warnings
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from pianolens.data.pianocore import PianoCoRe, pianocore_index
from pianolens.data.pianocore_cache import (
    DEFAULT_CACHE,
    NOTE_SCHEMA,
    PERFORMANCE_COLUMNS,
    aligned_columns,
    columns_to_table,
    performance_record,
    piece_slug,
)

FLUSH_ROWS = 400_000  # rows buffered per worker before a parquet row group is written

_PC: PianoCoRe | None = None
_GROUPS: dict[str, pd.DataFrame] = {}
_OUT: Path | None = None


def _init(index_path: str, out: str, tier: str) -> None:
    global _PC, _GROUPS, _OUT
    warnings.simplefilter("ignore")
    logging.getLogger("pianolens").setLevel(logging.ERROR)
    idx = pd.read_parquet(index_path)
    _PC = PianoCoRe(tier=tier)
    _PC.__dict__["index"] = idx  # skip re-reading the 206 MB metadata.csv per worker
    _GROUPS = {k: g for k, g in idx.groupby("piece_id", sort=False)}
    _OUT = Path(out)


def _atomic_json(path: Path, obj: dict) -> None:
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False))
    os.replace(tmp, path)


def _do_piece(piece_id: str) -> dict:
    assert _PC is not None and _OUT is not None
    t0 = time.time()
    slug = piece_slug(piece_id)
    rows = _GROUPS[piece_id].sort_values("refined_score_midi_path", kind="stable")
    final = _OUT / "notes" / f"{slug}.parquet"
    tmp = final.with_suffix(".parquet.tmp")
    writer = pq.ParquetWriter(tmp, NOTE_SCHEMA, compression="zstd")
    buf: list[pa.Table] = []
    buffered = 0
    records: list[dict] = []
    failures: list[dict] = []
    n_rows = 0
    try:
        for _, row in rows.iterrows():
            before = _PC.stats.pitch_mismatch
            try:
                ap = _PC.load(row)
                table = columns_to_table(aligned_columns(ap))
                rec = performance_record(ap, row, _PC.stats.pitch_mismatch > before)
            except Exception as e:  # noqa: BLE001 - count and continue
                failures.append(
                    {"pianocore_row_id": str(row["id"]), "piece_id": piece_id, "error": repr(e)}
                )
                continue
            records.append(rec)
            buf.append(table)
            buffered += table.num_rows
            if buffered >= FLUSH_ROWS:
                writer.write_table(pa.concat_tables(buf).combine_chunks())
                n_rows += buffered
                buf, buffered = [], 0
        if buf:
            writer.write_table(pa.concat_tables(buf).combine_chunks())
            n_rows += buffered
    finally:
        writer.close()
        _PC._score_cache.clear()
    os.replace(tmp, final)
    perf_path = _OUT / "_state" / f"{slug}.perfs.parquet"
    pd.DataFrame(records, columns=list(PERFORMANCE_COLUMNS)).to_parquet(perf_path, index=False)
    summary = {
        "piece_id": piece_id,
        "slug": slug,
        "file": f"notes/{slug}.parquet",
        "n_performances": len(records),
        "n_failed": len(failures),
        "n_rows": n_rows,
        "seconds": round(time.time() - t0, 2),
        "failures": failures,
    }
    _atomic_json(_OUT / "_state" / f"{slug}.json", summary)
    return summary


def consolidate(out: Path) -> None:
    states = [json.loads(p.read_text()) for p in sorted((out / "_state").glob("*.json"))]
    pieces = pd.DataFrame(
        [{k: s[k] for k in ("piece_id", "slug", "file", "n_performances", "n_failed",
                            "n_rows", "seconds")} for s in states]  # fmt: skip
    ).sort_values("n_performances", ascending=False)
    pieces.to_parquet(out / "pieces.parquet", index=False)
    failures = pd.DataFrame(
        [f for s in states for f in s["failures"]],
        columns=["pianocore_row_id", "piece_id", "error"],
    )
    failures.to_parquet(out / "failures.parquet", index=False)
    perf_files = sorted((out / "_state").glob("*.perfs.parquet"))
    perfs = pd.concat([pd.read_parquet(p) for p in perf_files], ignore_index=True)
    perfs.to_parquet(out / "performances.parquet", index=False)
    print(
        f"consolidated: {len(pieces)} pieces, {len(perfs)} performances, "
        f"{len(failures)} failures, {int(pieces['n_rows'].sum())} note rows"
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--tier", default="a", choices=["a", "a_star"])
    ap.add_argument("--out", type=Path, default=DEFAULT_CACHE)
    ap.add_argument("--max-pieces", type=int, default=None, help="smallest N pieces (testing)")
    ap.add_argument("--consolidate-only", action="store_true")
    args = ap.parse_args()
    out: Path = args.out
    (out / "notes").mkdir(parents=True, exist_ok=True)
    (out / "_state").mkdir(parents=True, exist_ok=True)
    if args.consolidate_only:
        consolidate(out)
        return

    t0 = time.time()
    idx = pianocore_index(tier=args.tier)
    index_path = out / "_state" / "index.parquet"
    idx.to_parquet(index_path, index=False)
    counts = idx["piece_id"].value_counts()  # largest first: long tasks start early
    if args.max_pieces:
        counts = counts.iloc[::-1].head(args.max_pieces)
    todo = [p for p in counts.index if not (out / "_state" / f"{piece_slug(p)}.json").exists()]
    total = int(counts.loc[todo].sum())
    print(f"{len(idx)} tier {args.tier} rows, {len(counts)} pieces; {len(todo)} pieces "
          f"({total} performances) to do; {args.workers} workers", flush=True)  # fmt: skip
    done_perfs = failed = 0
    ctx = mp.get_context("spawn")
    with ctx.Pool(args.workers, initializer=_init,
                  initargs=(str(index_path), str(out), args.tier),
                  maxtasksperchild=25) as pool:  # fmt: skip
        for i, s in enumerate(pool.imap_unordered(_do_piece, todo, chunksize=1), 1):
            done_perfs += s["n_performances"] + s["n_failed"]
            failed += s["n_failed"]
            el = time.time() - t0
            eta = el / max(done_perfs, 1) * (total - done_perfs)
            print(
                f"[{i}/{len(todo)}] {s['piece_id'][:60]}: {s['n_performances']} ok, "
                f"{s['n_failed']} failed, {s['seconds']:.0f}s | {done_perfs}/{total} perfs, "
                f"{failed} failed, {el / 60:.1f} min, eta {eta / 60:.0f} min",
                flush=True,
            )
    consolidate(out)
    print(f"wall time {(time.time() - t0) / 60:.1f} min", flush=True)


if __name__ == "__main__":
    main()
