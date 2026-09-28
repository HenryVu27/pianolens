"""Load every (n)ASAP performance + score + ground-truth alignment and print counts.

Usage: uv run python scripts/check_asap.py [--root data/raw/asap]
"""

from __future__ import annotations

import argparse
import logging
import time
import warnings
from pathlib import Path

from pianolens.data.asap import DEFAULT_ROOT, AsapStats, asap_index, iter_asap


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    args = ap.parse_args()
    logging.basicConfig(level=logging.WARNING)
    warnings.filterwarnings("ignore")
    logging.getLogger("partitura").setLevel(logging.ERROR)

    t0 = time.time()
    idx = asap_index(args.root)
    stats = AsapStats()
    for _ in iter_asap(args.root, index=idx, stats=stats):
        pass
    canonical = sum(not p.startswith("asap:") for p in set(idx["piece_id"]))
    print(f"rows in metadata.csv:        {stats.rows}")
    print(f"loaded (perf+score+align):   {stats.loaded}")
    print(f"failed:                      {len(stats.failed)}")
    for f, e in stats.failed:
        print(f"  {f}: {e[:160]}")
    print(f"without alignment file:      {len(stats.no_alignment)} {stats.no_alignment}")
    print(f"score files:                 {len(stats.scores)}")
    print(f"(composer, title) pairs:     {idx.groupby(['composer', 'title']).ngroups}")
    print(f"piece ids:                   {len(stats.pieces)} ({canonical} canonical)")
    print(f"performer ids (heuristic):   {len(stats.performers)}")
    print(f"robust_note_alignment == 1:  {int((idx['robust_note_alignment'] == 1).sum())}")
    print(f"alignment matches:           {stats.matches}")
    print(f"alignment insertions:        {stats.insertions}")
    print(f"alignment deletions:         {stats.deletions}")
    print(f"alignment other labels:      {stats.other_labels}")
    print(f"align score ids not in score notes:  {stats.align_score_ids_missing}")
    print(f"align perf ids not in perf notes:    {stats.align_perf_ids_missing}")
    print(f"score notes not in alignment:        {stats.score_notes_unaligned}")
    print(f"perf notes not in alignment:         {stats.perf_notes_unaligned}")
    print(f"elapsed: {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
