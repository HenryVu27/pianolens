"""R-09 transcription-noise floor: coherence on the same performance, Disklavier vs transcribed.

    OMP_NUM_THREADS=1 uv run python \
        experiments/2026-09-28-R-09-coherence-skill/noise_floor.py --workers 6

The 65 pairs are D-10's (``scripts/check_transcription_noise_d10.py``): PianoCoRe duplicates that
pair an ASAP Disklavier file with a transcription of the same performance (59 Aria-AMT, 6
Transkun V2), matched to ``data/raw/asap`` by that script. Their list is read from its output
``data/interim/skill_control_d10/transcription_pairs.csv`` (``trans_path``,
``asap_performance_id``), so the pairs are exactly D-10's. Both renditions are aligned to the
same ASAP score; ``build.coherence_row`` gives the coherence and phrase-tempo values.
Writes ``artifacts/noise_pairs.csv``.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
import warnings
import zipfile
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / "artifacts"
PAIRS = ROOT / "data" / "interim" / "skill_control_d10" / "transcription_pairs.csv"
RAW_ZIP = ROOT / "data" / "raw" / "pianocore" / "PianoCoRe-1.0-raw-midi.zip"


def run_pair(p: dict, asap_row: dict) -> dict:
    warnings.filterwarnings("ignore")
    import logging

    logging.disable(logging.WARNING)
    sys.path.insert(0, str(HERE))
    from build import coherence_row

    from pianolens.align import align_performance
    from pianolens.data.asap import load_asap_performance, load_asap_score
    from pianolens.data.midi_io import performance_from_midi
    from pianolens.features.correctness import correctness
    from pianolens.features.score_basis import score_basis
    from pianolens.features.tempo import tempo_model

    row = pd.Series(asap_row)
    score = load_asap_score(row)
    disk = load_asap_performance(row)
    with zipfile.ZipFile(RAW_ZIP) as z, tempfile.TemporaryDirectory() as td:
        f = Path(td) / "t.mid"
        f.write_bytes(z.read("PianoCoRe/raw/" + p["trans_path"]))
        trans = performance_from_midi(f, dataset="pianocore", performance_id="trans",
                                      piece_id=row["piece_id"], performer_id=row["performer_id"],
                                      provenance="transcribed")  # fmt: skip
    out = {"trans_path": p["trans_path"], "capture_model": p["capture_model"],
           "asap_performance_id": row["performance_id"], "piece_id": row["piece_id"]}
    for tag, perf in (("disk", disk), ("trans", trans)):
        ap = align_performance(score, perf)
        tc = tempo_model(ap)
        basis = score_basis(ap.score)
        out[f"{tag}_match_ratio"] = float(correctness(ap).summary["match_ratio"])
        out.update({f"{tag}_{k}": v for k, v in coherence_row(ap, tc, basis).items()})
    return out


def main() -> None:
    warnings.filterwarnings("ignore")
    from pianolens.data.asap import asap_index

    a = argparse.ArgumentParser()
    a.add_argument("--workers", type=int, default=6)
    args = a.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    pr = pd.read_csv(PAIRS)
    idx = asap_index().set_index("performance_id", drop=False)
    todo = [(p, idx.loc[p["asap_performance_id"]].to_dict()) for p in pr.to_dict("records")]
    print(f"{len(todo)} pairs", flush=True)
    rows, fails = [], []
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(run_pair, p, r): p for p, r in todo}
        for f in as_completed(futs):
            try:
                rows.append(f.result())
            except Exception as e:  # noqa: BLE001
                fails.append({"trans_path": futs[f]["trans_path"], "error": repr(e)})
    pd.DataFrame(rows).to_csv(OUT / "noise_pairs.csv", index=False)
    if fails:
        pd.DataFrame(fails).to_csv(OUT / "noise_pairs_failures.csv", index=False)
    print(f"{len(rows)} pairs done, {len(fails)} failures")


if __name__ == "__main__":
    main()
