"""Build the PianoCoRe score note-count table used by the raw-MIDI guard (BL-35).

For every score MusicXML named by a tier A row (``score_xml_path``, 1,591 files) this writes one
row to ``data/processed/pianocore_score_notes.parquet``:

- ``folded``: notes of the score as written (tied notes merged, grace notes included), read
  through ``pianolens.align._adapters.to_part`` so tremolos and staves match what the aligner
  sees.
- ``unfolded_max``: notes of the longest repeat reading. This is the maximum over
  ``pianolens.align.repeat_variants`` (the aligner's own repeat paths), or partitura's
  ``unfold_part_maximal`` when the path enumeration does not finish within ``--timeout``
  seconds (variation sets with many repeats).
- ``method``: ``variants``, ``maximal`` or ``failed`` (the score does not load); ``error``.

``pianocore.raw_guard`` divides raw performance notes by ``unfolded_max`` so that performances
that play every repeat are not mistaken for performances longer than their score.

Each score runs in its own subprocess with a timeout (partitura's path enumeration can hang).

Usage: uv run python scripts/build_pianocore_score_notes.py [--workers 8] [--timeout 120]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "processed" / "pianocore_score_notes.parquet"


def _count(rel: str, mode: str) -> dict:
    """Run in a subprocess: count notes of one score (``mode`` = ``variants`` or ``maximal``)."""
    import logging
    import tempfile
    import warnings
    import zipfile

    warnings.simplefilter("ignore")
    logging.disable(logging.WARNING)
    import partitura as pt

    from pianolens.align import repeat_variants
    from pianolens.align._adapters import to_part
    from pianolens.data.pianocore import DEFAULT_ROOT, RAW_PREFIX, RAW_ZIP

    sys.setrecursionlimit(100_000)
    with zipfile.ZipFile(DEFAULT_ROOT / RAW_ZIP) as z, tempfile.TemporaryDirectory() as d:
        p = Path(d) / Path(rel).name
        p.write_bytes(z.read(RAW_PREFIX + rel))
        part = to_part(p)
    folded = len(part.notes_tied)
    if mode == "variants":
        counts = [n for _, n in repeat_variants(part)]
        return {"folded": folded, "unfolded_max": max([folded, *counts]),
                "n_variants": len(counts)}  # fmt: skip
    maximal = len(pt.score.unfold_part_maximal(part).notes_tied)
    return {"folded": folded, "unfolded_max": max(folded, maximal), "n_variants": -1}


def _run(rel: str, mode: str, timeout: float) -> dict:
    cmd = [sys.executable, __file__, "--one", rel, "--mode", mode]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
    lines = [ln for ln in r.stdout.splitlines() if ln.startswith("{")]
    if r.returncode != 0 or not lines:
        raise RuntimeError((r.stderr.strip().splitlines() or ["no output"])[-1][:300])
    return json.loads(lines[-1])


def score_row(rel: str, timeout: float) -> dict:
    t = time.time()
    row = {"score_xml_path": rel, "folded": -1, "unfolded_max": -1, "n_variants": 0,
           "method": "failed", "error": ""}  # fmt: skip
    for mode in ("variants", "maximal"):
        try:
            row.update(_run(rel, mode, timeout), method=mode, error="")
            break
        except (subprocess.TimeoutExpired, RuntimeError) as e:
            row["error"] = f"{mode}: {e!r}"[:300]
    row["seconds"] = round(time.time() - t, 1)
    return row


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--timeout", type=float, default=120.0)
    ap.add_argument("--one", help=argparse.SUPPRESS)
    ap.add_argument("--mode", default="variants", help=argparse.SUPPRESS)
    args = ap.parse_args()
    if args.one:
        print(json.dumps(_count(args.one, args.mode)))
        return

    import pandas as pd

    from pianolens.data.pianocore import pianocore_index

    rels = sorted(pianocore_index(tier="a")["score_xml_path"].dropna().astype(str).unique())
    print(f"{len(rels)} tier A score files", flush=True)
    with ThreadPoolExecutor(args.workers) as ex:
        rows = []
        for i, r in enumerate(ex.map(lambda s: score_row(s, args.timeout), rels)):
            rows.append(r)
            if i % 100 == 0:
                print(i, flush=True)
    df = pd.DataFrame(rows).sort_values("score_xml_path").reset_index(drop=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT, index=False)
    print(df["method"].value_counts().to_string())
    print(f"wrote {OUT} ({len(df)} rows)")


if __name__ == "__main__":
    main()
