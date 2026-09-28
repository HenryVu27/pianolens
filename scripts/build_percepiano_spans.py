"""Locate each PercePiano segment score in a full score and write its bar range.

PercePiano's segment MusicXML files are renumbered from bar 1, so the bar range in the piece is
not stored anywhere. We recover it by exact matching of the (onset-sorted) pitch sequence of the
segment's first notes against a full score:

* Beethoven WoO 80: the full score shipped in the repo (``beethoven_woo80_score2.musicxml``).
* Schubert D.935 no.3: the (n)ASAP score ``Schubert/Impromptu_op142/3``. Segments follow the
  performance order with repeats taken, so ambiguous hits are resolved by requiring each segment
  to start after the previous one in the maximally unfolded score.
* Schubert D.960 mv2 / mv3: no full score is available; left unresolved (span empty). We only
  record the measure count of each segment.

Output: ``data/processed/percepiano_spans.csv`` with columns
``score_stem, work, bars, segment, n_measures, first_bar, last_bar, method``. ``first_bar`` /
``last_bar`` are printed measure numbers of the full score (inclusive).

Usage: uv run python scripts/build_percepiano_spans.py
"""

from __future__ import annotations

import logging
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import partitura as pt

REPO = Path(__file__).resolve().parents[1]
XML = REPO / "data/raw/percepiano/virtuoso/data/score_xml"
ASAP_D935 = REPO / "data/raw/asap/Schubert/Impromptu_op142/3/xml_score.musicxml"
OUT = REPO / "data/processed/percepiano_spans.csv"
KEY_LEN = 30


def _part(path: Path):
    s = pt.load_score(str(path))
    return pt.score.merge_parts(s.parts) if len(s.parts) > 1 else s.parts[0]


def _sorted_notes(part) -> np.ndarray:
    na = part.note_array()
    return na[np.lexsort((na["pitch"], na["onset_div"]))]


class FullScore:
    def __init__(self, part):
        self.na = _sorted_notes(part)
        self.pitches = self.na["pitch"].tolist()
        self.measures = list(part.measures)
        self.starts = np.array([m.start.t for m in self.measures])

    def hits(self, key: list[int]) -> list[int]:
        """Ordinal (0-based) of the measure where each exact match starts."""
        n = len(key)
        out = []
        for i in range(len(self.pitches) - n + 1):
            if self.pitches[i : i + n] == key:
                mi = int(np.searchsorted(self.starts, self.na["onset_div"][i], side="right") - 1)
                out.append(mi)
        return out


def _segment_files(prefix: str) -> list[Path]:
    fs = [p for p in XML.glob(f"{prefix}*_Score_*.musicxml")]
    return sorted(fs, key=lambda p: (p.stem.split("_Score_")[0], int(p.stem.split("_")[-1])))


def main() -> None:
    warnings.filterwarnings("ignore")
    logging.disable(logging.WARNING)
    sys.setrecursionlimit(10_000)
    rows = []

    woo = FullScore(_part(XML / "beethoven_woo80_score2.musicxml"))
    for p in _segment_files("Beethoven_WoO80"):
        part = _part(p)
        nm = len(list(part.measures))
        work = p.stem.split("_8bars")[0]
        h = woo.hits(_sorted_notes(part)["pitch"].tolist()[:KEY_LEN])
        first = last = None
        method = "unresolved"
        if len(h) == 1:
            first = woo.measures[h[0]].number
            method = "matched"
        elif "var32" not in work:
            # theme and variations 1-31 are 8 bars each: theme = 1-8, var n = 8n+1 .. 8n+8
            v = 0 if work.endswith("thema") else int(work.rsplit("var", 1)[1])
            first = 8 * v + 1
            method = "formula"
        if first is not None:
            last = first + nm - 1
        rows.append((p.stem, work, 8, int(p.stem.split("_")[-1]), nm, first, last, method))

    d935 = FullScore(pt.score.unfold_part_maximal(_part(ASAP_D935)))
    prev = -1
    for p in _segment_files("Schubert_D935"):
        part = _part(p)
        nm = len(list(part.measures))
        h = [m for m in d935.hits(_sorted_notes(part)["pitch"].tolist()[:KEY_LEN]) if m > prev]
        first = last = None
        method = "unresolved"
        if h:
            mi = h[0]
            prev = mi
            first = d935.measures[mi].number
            last = d935.measures[min(mi + nm - 1, len(d935.measures) - 1)].number
            method = "matched_ordered"
        rows.append((p.stem, "Schubert_D935_no.3", 4, int(p.stem.split("_")[-1]), nm, first,
                     last, method))

    for work in ("Schubert_D960_mv2", "Schubert_D960_mv3"):
        for p in _segment_files(work):
            nm = len(list(_part(p).measures))
            bars = int(p.stem.split("_")[-3].removesuffix("bars"))
            rows.append((p.stem, work, bars, int(p.stem.split("_")[-1]), nm, None, None,
                         "unresolved"))

    df = pd.DataFrame(rows, columns=["score_stem", "work", "bars", "segment", "n_measures",
                                     "first_bar", "last_bar", "method"])
    df["first_bar"] = df["first_bar"].astype("Int64")
    df["last_bar"] = df["last_bar"].astype("Int64")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False)
    print(df.groupby(["work", "method"]).size().to_string())
    print(f"wrote {OUT} ({len(df)} rows)")


if __name__ == "__main__":
    main()
