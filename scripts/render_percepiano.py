"""Render every PercePiano segment MIDI with the fixed piano (S-02).

Writes ``<render_dir>/<stem>.wav`` (24 kHz mono PCM_16) and ``<render_dir>/manifest.csv`` with
duration, peak, and hashes. Idempotent: existing WAVs are kept unless --force.

    uv run --extra audio python scripts/render_percepiano.py [--workers 8] [--force]
"""

from __future__ import annotations

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import soundfile as sf

from pianolens.audio import render as R
from pianolens.data.percepiano import DEFAULT_ROOT, percepiano_index


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    cfg = R.CRESCENDAI_SALAMANDER
    if R.file_sha256(cfg.soundfont) != R.SOUNDFONT_SHA256:
        raise SystemExit("soundfont hash mismatch; see DATASETS.md")
    out_dir = R.render_dir(cfg, "percepiano")
    out_dir.mkdir(parents=True, exist_ok=True)
    idx = percepiano_index()

    def one(row) -> dict:
        midi = DEFAULT_ROOT / row.file
        stem = row.performance_id.split(":", 1)[1]
        wav = out_dir / f"{stem}.wav"
        if wav.is_file() and not args.force:
            y, sr = sf.read(str(wav), dtype="float32")
            peak = float(abs(y).max())
        else:
            res = R.render_to_wav(midi, wav, cfg)
            sr, peak = res.sample_rate, res.peak
            y = res.audio
        return {"performance_id": row.performance_id, "stem": stem, "wav": wav.name,
                "duration_sec": len(y) / sr, "peak": peak, "clipped": peak >= 1.0,
                "midi_sha256": R.file_sha256(midi), "wav_sha256": R.file_sha256(wav)}

    t0 = time.time()
    with ThreadPoolExecutor(args.workers) as ex:
        rows = list(ex.map(one, idx.itertuples()))
    man = pd.DataFrame(rows).sort_values("performance_id")
    man.to_csv(out_dir / "manifest.csv", index=False)
    meta = {"config": cfg.__dict__, "config_hash": cfg.config_hash(),
            "fluidsynth": R.fluidsynth_version(), "soundfont_sha256": R.SOUNDFONT_SHA256,
            "n": len(man), "wall_sec": round(time.time() - t0, 1)}
    (out_dir / "render_meta.json").write_text(json.dumps(meta, indent=2, default=str))
    print(json.dumps(meta, indent=2, default=str))
    print(man[["duration_sec", "peak"]].describe().round(3).to_string())
    print("clipped:", int(man.clipped.sum()))


if __name__ == "__main__":
    main()
