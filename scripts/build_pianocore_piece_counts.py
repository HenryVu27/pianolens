"""Build the PianoCoRe per-piece performance-count table (D-03 gate).

Reads data/raw/pianocore/metadata.csv (Zenodo 19186016 v1.0) and writes
data/processed/pianocore_piece_counts.csv with one row per piece
(composer, composition, movement) and counts per tier and per capture source, plus
data/processed/pianocore_piece_map.csv: (composer, composition, movement) -> piece_id, the
PianoCoRe part of the cross-dataset mapping in data/processed/piece_ids.parquet.

Usage: uv run python scripts/build_pianocore_piece_counts.py [--top 50]
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from pianolens.data.pianocore import pianocore_index

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/processed/pianocore_piece_counts.csv"
MAP_OUT = ROOT / "data/processed/pianocore_piece_map.csv"
KEY = ["piece_id", "composer", "composition", "movement"]


def build(meta: pd.DataFrame) -> pd.DataFrame:
    m = meta.copy()
    m["movement"] = m["movement"].fillna("")
    for col in ("tier_b", "tier_a", "tier_a_star", "is_transcription"):
        m[col] = m[col].astype(bool)
    m["disklavier"] = ~m["is_transcription"]
    g = m.groupby(KEY, sort=False)
    table = pd.DataFrame(
        {
            "n_c": g.size(),
            "n_b": g["tier_b"].sum(),
            "n_a": g["tier_a"].sum(),
            "n_a_star": g["tier_a_star"].sum(),
            "n_a_disklavier": g.apply(
                lambda d: int((d["tier_a"] & d["disklavier"]).sum()), include_groups=False
            ),
            "n_a_performers": g.apply(
                lambda d: d.loc[d["tier_a"], "performer"].nunique(), include_groups=False
            ),
            "n_scores_a": g.apply(
                lambda d: d.loc[d["tier_a"], "score_id"].nunique(), include_groups=False
            ),
        }
    ).reset_index()
    return table.sort_values(["n_a", "n_a_star", "n_c"], ascending=False).reset_index(drop=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=50)
    args = ap.parse_args()
    meta = pianocore_index(tier="c")
    table = build(meta)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(OUT, index=False)
    table[KEY].to_csv(MAP_OUT, index=False)
    canon = ~table.piece_id.str.startswith("pianocore:")
    print(f"canonical piece ids: {canon.sum()} of {len(table)} pieces (C); "
          f"{(canon & (table.n_a > 0)).sum()} of {(table.n_a > 0).sum()} pieces with A")
    a = table[table.n_a > 0]
    print(f"rows in metadata: {len(meta)}; pieces (C): {len(table)}; pieces with A: {len(a)}")
    for t in (10, 50, 100):
        print(f"pieces with >= {t} A performances: {(a.n_a >= t).sum()}; "
              f">= {t} C performances: {(table.n_c >= t).sum()}")
    print(f"wrote {OUT}")
    top = table.head(args.top)
    print("| # | piece_id | Composition | Movement | A | A* | C | A Disklavier "
          "| A named performers |")
    print("|---|---|---|---|---|---|---|---|---|")
    for i, r in enumerate(top.itertuples(), 1):
        comp = r.composition.replace("_", " ").replace("|", "/")
        mov = r.movement.replace("_", " ")
        pid = r.piece_id if not r.piece_id.startswith("pianocore:") else "(prefixed)"
        print(f"| {i} | {pid} | {comp} | {mov} | {r.n_a} | {r.n_a_star} "
              f"| {r.n_c} | {r.n_a_disklavier} | {r.n_a_performers} |")


if __name__ == "__main__":
    main()
