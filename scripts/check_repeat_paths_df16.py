"""DF-16 / DF-17: repeat-path counts of every app-catalogue score, and timed runs on the large ones.

``uv run python scripts/check_repeat_paths_df16.py count [--out CSV]``
    Every catalogue score (``data/interim/app/catalog.json``): repeat paths with the bounded
    enumeration (``align.core._variants_info``; "more than MAX_REPEAT_PATHS" when capped),
    parse and enumeration seconds. Appends one row per score, so a stopped run resumes.

``uv run python scripts/check_repeat_paths_df16.py one PIECE_ID KIND [--partial]``
    One score in this process: KIND ``quick`` (the app's quick check on a 21-note excerpt of
    the score's own notes played deadpan) or ``report`` (``report_from_files`` on the same
    excerpt, as the CLI). Prints seconds, peak RSS and the recorded-span record. Run it under a
    memory watch, one score at a time.
"""

from __future__ import annotations

import argparse
import csv
import json
import resource
import sys
import tempfile
import time
import warnings
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CATALOG = REPO / "data" / "interim" / "app" / "catalog.json"
ASAP = REPO / "data" / "raw" / "asap"


def score_path(piece: dict, td: Path) -> Path:
    if piece["source"] == "asap":
        return ASAP / piece["score"]
    from pianolens.data.pianocore import DEFAULT_ROOT, RAW_PREFIX, RAW_ZIP

    f = td / ("score" + Path(piece["score"]).suffix)
    with zipfile.ZipFile(DEFAULT_ROOT / RAW_ZIP) as z:
        f.write_bytes(z.read(RAW_PREFIX + piece["score"]))
    return f


def pieces() -> list[dict]:
    return json.loads(CATALOG.read_text())["pieces"]


def count(out: Path) -> None:
    from pianolens.align._adapters import to_part
    from pianolens.align.core import _variants_info

    done = set()
    if out.is_file():
        done = {r["piece_id"] for r in csv.DictReader(out.open())}
    new = not out.is_file()
    with out.open("a", newline="") as fh:
        w = csv.writer(fh)
        if new:
            w.writerow(["piece_id", "source", "n_paths", "complete", "parse_sec", "enum_sec"])
        for p in pieces():
            if p["piece_id"] in done:
                continue
            with tempfile.TemporaryDirectory() as td:
                t0 = time.time()
                part = to_part(score_path(p, Path(td)))
                t1 = time.time()
                v, complete = _variants_info(part)
                w.writerow([p["piece_id"], p["source"], len(v), complete, round(t1 - t0, 2),
                            round(time.time() - t1, 2)])
                fh.flush()


def excerpt_midi(sc_path: Path, dst: Path, n: int = 21) -> None:
    """n consecutive score notes (first path, from the middle), deadpan at 120 bpm, as MIDI."""
    import numpy as np
    import partitura as pt

    from pianolens.align._adapters import to_part

    na = to_part(sc_path).note_array()
    na = na[np.argsort(na["onset_beat"], kind="stable")]
    k = max(0, len(na) // 2 - n // 2)
    sel = na[k:k + n]
    pna = np.zeros(len(sel), dtype=[("onset_sec", "f8"), ("duration_sec", "f8"),
                                    ("pitch", "i4"), ("velocity", "i4"), ("id", "U16")])
    pna["onset_sec"] = (sel["onset_beat"] - sel["onset_beat"][0]) * 0.5
    pna["duration_sec"] = 0.4
    pna["pitch"], pna["velocity"] = sel["pitch"], 64
    pna["id"] = [f"p{i}" for i in range(len(sel))]
    pt.save_performance_midi(pt.performance.PerformedPart.from_note_array(pna), str(dst))


def one(piece_id: str, kind: str, partial: bool) -> None:
    piece = next(p for p in pieces() if p["piece_id"] == piece_id)
    with tempfile.TemporaryDirectory() as td:
        sp = score_path(piece, Path(td))
        mid = Path(td) / "excerpt.mid"
        excerpt_midi(sp, mid)
        t0 = time.time()
        if kind == "quick":  # app/pipeline.py step 2
            from pianolens.align import align_performance
            from pianolens.features.correctness import correctness
            from pianolens.report.io import load_performance, load_score

            ap = align_performance(load_score(sp, piece_id),
                                   load_performance(mid, "unknown", piece_id), partial=partial)
            ratio = correctness(ap).summary["match_ratio"]
            rs = ap.score.meta.get("recorded_span") or {}
            extra = {"ratio": round(float(ratio), 3)}
        else:  # the CLI report path
            from pianolens.report import report_from_files

            rep = report_from_files(mid, score=sp, piece_id=piece_id, provenance="unknown",
                                    partial=partial)
            rs = rep.get("recorded_span") or {}
            notes = [n for n in rep["confidence"]["notes"] if n.startswith("This score has")]
            extra = {"fallback_note": bool(notes), "n_bars": len(rep["bars"])}
        sec = time.time() - t0
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 2**30  # bytes on macOS
    print(json.dumps({"piece_id": piece_id, "kind": kind, "partial": partial,
                      "sec": round(sec, 1), "peak_gb": round(peak, 2), **extra,
                      "whole": rs.get("whole"), "fallback": rs.get("fallback"),
                      "method": rs.get("method")}), flush=True)


def main() -> None:
    warnings.filterwarnings("ignore")
    import logging

    logging.disable(logging.WARNING)
    sys.setrecursionlimit(100_000)
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("count")
    c.add_argument("--out", type=Path, default=REPO / "data" / "interim" / "df16_paths.csv")
    o = sub.add_parser("one")
    o.add_argument("piece_id")
    o.add_argument("kind", choices=("quick", "report"))
    o.add_argument("--partial", action="store_true")
    a = ap.parse_args()
    if a.cmd == "count":
        count(a.out)
    else:
        one(a.piece_id, a.kind, a.partial)


if __name__ == "__main__":
    main()
