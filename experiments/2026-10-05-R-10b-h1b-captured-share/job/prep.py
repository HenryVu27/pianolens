"""R-10 prep (CPU): expert curves (R-02), score-note beat table and whole-piece generation items.

    python prep.py --pianocore DIR --pieces ../pieces.csv --set decision --out OUT/data --workers 4

Resumable: pieces whose three output files exist are skipped. Runs at below-normal CPU priority
on Windows (the machine is shared). Log rows are appended to OUT/data/prep_log.jsonl.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))


def below_normal() -> None:
    if os.name == "nt":
        import ctypes

        k = ctypes.windll.kernel32
        k.SetPriorityClass(k.GetCurrentProcess(), 0x00004000)  # BELOW_NORMAL_PRIORITY_CLASS
    else:
        os.nice(5)


def _work(args):
    below_normal()
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    import r10lib

    root, pid, rows, out = args
    t0 = time.time()
    try:
        r = r10lib.prep_piece(root, pid, rows, Path(out))
    except Exception as e:  # noqa: BLE001
        r = {"piece_id": pid, "error": repr(e)[:300]}
    r["sec"] = round(time.time() - t0, 1)
    return r


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pianocore", required=True)
    ap.add_argument("--pieces", default=str(HERE.parent / "pieces.csv"))
    ap.add_argument("--set", nargs="+", default=["decision"])
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args(argv)
    below_normal()
    import r10lib

    from pianolens.data.pianocore import pianocore_index

    pieces = pd.read_csv(a.pieces)
    pieces = pieces[pieces["set"].isin(a.set)].drop_duplicates("piece_id")
    idx = pianocore_index(a.pianocore, tier="a")
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    jobs = [(a.pianocore, pid, r10lib.majority_rows(idx, pid), str(out))
            for pid in pieces["piece_id"]]
    print(f"{len(jobs)} pieces, {sum(len(j[2]) for j in jobs)} performances", flush=True)
    t0 = time.time()
    with ProcessPoolExecutor(a.workers) as ex, open(out / "prep_log.jsonl", "a") as fh:
        futs = [ex.submit(_work, j) for j in jobs]
        for i, f in enumerate(as_completed(futs), 1):
            r = f.result()
            fh.write(json.dumps(r, default=str) + "\n")
            fh.flush()
            print(f"{i}/{len(jobs)} {time.time() - t0:.0f}s {r.get('piece_id')} "
                  f"{'skip' if r.get('skipped') else r.get('n_ok', r.get('error'))}", flush=True)
    print(f"prep done in {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
