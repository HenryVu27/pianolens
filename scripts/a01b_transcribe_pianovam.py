"""A-01b: transcribe the PianoVAM audio subset with Transkun (MPS), one file at a time.

    uv run python scripts/a01b_transcribe_pianovam.py [--device mps]

Inputs: ``data/raw/pianovam/Audio/<record_time>.wav`` (the subset fetched for A-01b; see
DATASETS.md). Transkun 2.0.1 lives in the gitignored venv ``data/interim/envs/transkun`` (A-01).
Writes ``data/interim/pianovam_a01b/transkun/<record_time>.mid`` and ``runtime.csv``. Files that
already exist are skipped, so the script can be re-run after an interruption.
"""

from __future__ import annotations

import argparse
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDIO = ROOT / "data" / "raw" / "pianovam" / "Audio"
OUT = ROOT / "data" / "interim" / "pianovam_a01b" / "transkun"
TRANSKUN = ROOT / "data" / "interim" / "envs" / "transkun" / "bin" / "transkun"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default="mps")
    ap.add_argument("--reverse", action="store_true", help="work from the end (second worker)")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    log = OUT / "runtime.csv"
    if not log.exists():
        log.write_text("record_time,seconds,ok\n")
    wavs = sorted(AUDIO.glob("*.wav"), reverse=args.reverse)
    for i, w in enumerate(wavs):
        out = OUT / f"{w.stem}.mid"
        lock = OUT / f"{w.stem}.lock"
        if out.exists() or lock.exists():
            continue
        lock.touch()
        t0 = time.time()
        r = subprocess.run([str(TRANSKUN), "--device", args.device, str(w), str(out)],
                           capture_output=True, text=True)  # fmt: skip
        dt = time.time() - t0
        ok = r.returncode == 0 and out.exists()
        lock.unlink(missing_ok=True)
        with log.open("a") as f:
            f.write(f"{w.stem},{dt:.1f},{int(ok)}\n")
        print(f"[{i + 1}/{len(wavs)}] {w.stem} {dt:.1f}s {'ok' if ok else 'FAILED'}", flush=True)
        if not ok:
            print(r.stderr[-500:])


if __name__ == "__main__":
    main()
