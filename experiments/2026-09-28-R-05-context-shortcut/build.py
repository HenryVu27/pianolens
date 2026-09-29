"""R-05 step 1: sample MAJEPPA clips, render 30 s excerpts, simulate 4 recording contexts, MuQ.

For every sampled clip: the first ``EXCERPT_S`` seconds of the Transkun MIDI (from the first
onset) are rendered once with the fixed S-02 renderer (``pianolens.audio.render``, default
config), then post-processed into 4 simulated recording contexts (``CONTEXTS``). Every context
ends with an AAC round trip (all MAJEPPA audio came from YouTube). Context parameters are drawn
per clip from fixed ranges with a seed derived from (clip, context), so a clip's audio in a
context is the same whichever dataset it is used in.

Each of the 4 versions goes through frozen MuQ-large-msd-iter (fp32, 24 kHz, MPS; one batch of 4
per clip) and is pooled as in R-03 (mean || population std over frames) for hidden states 0-12
and the L9-12 average (row 13).

Outputs (artifacts/):
  sample.csv                      the sampled clips with labels and excerpt stats
  emb_partial/<P_NNNN>.npz        per clip: pooled (4 contexts, 14 layers, 2048) float32
  embeddings.npz                  ids, l912 (N, 4, 2048) f32, layers (N, 4, 14, 2048) f16
  build_meta.json                 versions, config hashes, timing

Usage:
  uv run python experiments/2026-09-28-R-05-context-shortcut/build.py --pilot 8
  uv run python experiments/2026-09-28-R-05-context-shortcut/build.py --workers 6
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ART = HERE / "artifacts"
MODEL_ID = "OpenMuQ/MuQ-large-msd-iter"
SR = 24_000
EXCERPT_S = 30.0
MIN_DUR_S = 10.0
PER_LEVEL = 250
SAMPLE_SEED = 0

CONTEXTS = ("clean", "phone_room", "recital_phone", "concert_hall")
# Real MAJEPPA recording_type -> simulated context (the confound mirrors these labels).
RECTYPE_TO_CONTEXT = {
    "demo_class": "clean", "slow_demo": "clean", "fast_demo": "clean",
    "practice": "phone_room", "sight_read": "phone_room",
    "performance": "recital_phone",
    "concert_performance": "concert_hall",
}  # fmt: skip
# Per-clip parameter ranges (uniform). lowpass 0 = none (24 kHz audio has a 12 kHz Nyquist).
CONTEXT_RANGES = {
    # close mic in a small treated room, good gear
    "clean": dict(rt60_s=(0.20, 0.35), drr_db=(10.0, 15.0), highpass_hz=(30.0, 40.0),
                  lowpass_hz=(0.0, 0.0), snr_db=(50.0, 60.0), aac_kbps=(160, 160)),
    # phone on the piano / music stand in a living room
    "phone_room": dict(rt60_s=(0.40, 0.80), drr_db=(0.0, 6.0), highpass_hz=(100.0, 200.0),
                       lowpass_hz=(7000.0, 10000.0), snr_db=(25.0, 40.0), aac_kbps=(96, 96)),
    # phone in the audience of a recital hall
    "recital_phone": dict(rt60_s=(1.20, 1.80), drr_db=(-6.0, 0.0), highpass_hz=(100.0, 200.0),
                          lowpass_hz=(7000.0, 10000.0), snr_db=(25.0, 40.0), aac_kbps=(96, 96)),
    # concert recording: good microphones at a distance in a large hall
    "concert_hall": dict(rt60_s=(1.60, 2.40), drr_db=(-3.0, 3.0), highpass_hz=(30.0, 40.0),
                         lowpass_hz=(0.0, 0.0), snr_db=(45.0, 60.0), aac_kbps=(160, 160)),
}  # fmt: skip
LEVELS = ("child_beginner", "adult_beginner", "adult_intermediate", "child_professional",
          "piano_teacher", "virtuoso")  # fmt: skip


# --------------------------------------------------------------------------- sampling


def _midi_path(pid: str) -> Path:
    from pianolens.data.majeppa import DEFAULT_ROOT

    return DEFAULT_ROOT / "extracted" / "performance" / f"{pid}.mid"


def _span(pid: str) -> tuple[float, float, int]:
    """(first onset, last onset, n notes) of a performance MIDI, via mido."""
    import mido

    t, first, last, n = 0.0, None, None, 0
    for msg in mido.MidiFile(str(_midi_path(pid))):
        t += msg.time
        if msg.type == "note_on" and msg.velocity > 0:
            first = t if first is None else first
            last, n = t, n + 1
    return (first or 0.0), (last or 0.0), n


def build_sample(workers: int) -> pd.DataFrame:
    from pianolens.data.majeppa import majeppa_index

    md = majeppa_index()
    md = md[md.score_id.notna() & md.expertise_level.isin(LEVELS)].copy()
    md = md[md.recording_type.isin(RECTYPE_TO_CONTEXT)]
    with ProcessPoolExecutor(workers) as ex:
        spans = list(ex.map(_span, md.performance_id, chunksize=32))
    md["first_onset_s"] = [s[0] for s in spans]
    md["midi_dur_s"] = [s[1] - s[0] for s in spans]
    md["n_notes_total"] = [s[2] for s in spans]
    md = md[md.midi_dur_s >= MIN_DUR_S]
    rng = np.random.default_rng(SAMPLE_SEED)
    parts = []
    for lv in LEVELS:
        sub = md[md.expertise_level == lv].sort_values("performance_id")
        take = rng.choice(len(sub), size=min(PER_LEVEL, len(sub)), replace=False)
        parts.append(sub.iloc[np.sort(take)])
    s = pd.concat(parts).reset_index(drop=True)
    s["context_real"] = s.recording_type.map(RECTYPE_TO_CONTEXT)
    return s


# --------------------------------------------------------------------------- audio


def excerpt(perf, t0: float, dur: float):
    """Notes with onset in [t0, t0 + dur), shifted to start at 0; pedal state carried in."""
    from pianolens.data.types import PEDAL_DTYPE

    n = perf.notes
    keep = (n["onset_sec"] >= t0 - 1e-9) & (n["onset_sec"] < t0 + dur)
    notes = n[keep].copy()
    notes["onset_sec"] = notes["onset_sec"] - t0
    rows = []
    p = perf.pedal
    for num in np.unique(p["number"]) if len(p) else []:
        before = p[(p["number"] == num) & (p["time_sec"] < t0)]
        if len(before):
            rows.append((0.0, int(num), int(before["value"][-1])))
    inw = p[(p["time_sec"] >= t0) & (p["time_sec"] < t0 + dur)] if len(p) else p
    rows += [(float(r["time_sec"]) - t0, int(r["number"]), int(r["value"])) for r in inw]
    pedal = np.array(sorted(rows), dtype=PEDAL_DTYPE)
    return replace(perf, notes=notes, pedal=pedal)


def context_params(pid: str, ctx: str) -> dict:
    seed = int(hashlib.sha256(f"R-05|{pid}|{ctx}".encode()).hexdigest()[:8], 16)
    rng = np.random.default_rng(seed)
    out = {k: float(rng.uniform(lo, hi)) for k, (lo, hi) in CONTEXT_RANGES[ctx].items()}
    out["aac_kbps"] = int(round(out["aac_kbps"]))
    out["seed"] = seed
    return out


def aac_roundtrip(y: np.ndarray, kbps: int) -> np.ndarray:
    import soundfile as sf

    with tempfile.TemporaryDirectory() as tmp:
        src, enc, dec = (Path(tmp) / f for f in ("in.wav", "x.m4a", "out.wav"))
        sf.write(str(src), y, SR, subtype="FLOAT")
        for cmd in (["ffmpeg", "-v", "error", "-y", "-i", str(src), "-c:a", "aac", "-b:a",
                     f"{kbps}k", str(enc)],
                    ["ffmpeg", "-v", "error", "-y", "-i", str(enc), "-ar", str(SR), "-ac", "1",
                     "-c:a", "pcm_f32le", str(dec)]):
            subprocess.run(cmd, check=True, capture_output=True)
        z, sr = sf.read(str(dec), dtype="float32")
    assert sr == SR
    z = z[: len(y)]
    if len(z) < len(y):
        z = np.pad(z, (0, len(y) - len(z)))
    return z


def apply_context(y: np.ndarray, pid: str, ctx: str) -> np.ndarray:
    from pianolens.audio.phone import PhoneSimConfig, simulate_phone

    p = context_params(pid, ctx)
    cfg = PhoneSimConfig(rt60_s=p["rt60_s"], drr_db=p["drr_db"], highpass_hz=p["highpass_hz"],
                         lowpass_hz=p["lowpass_hz"], snr_db=p["snr_db"], peak_dbfs=-3.0,
                         seed=p["seed"] % (2**32))
    return aac_roundtrip(simulate_phone(y, SR, cfg), p["aac_kbps"])


def render_clip(row: dict) -> tuple[str, np.ndarray, dict]:
    """Worker: (performance_id, audio (4, n) float32, stats)."""
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    from pianolens.audio import render as R
    from pianolens.data.midi_io import performance_from_midi
    from pianolens.data.types import PerformerId, PieceId

    pid = row["performance_id"]
    perf = performance_from_midi(_midi_path(pid), dataset="majeppa",
                                 performance_id=f"majeppa:{pid}", piece_id=PieceId(row["piece_id"]),
                                 performer_id=PerformerId(f"majeppa:recording/{row['recording_id']}"),
                                 provenance="transcribed")
    t0 = float(np.min(perf.notes["onset_sec"]))
    ex = excerpt(perf, t0, EXCERPT_S)
    res = R.render_performance(ex, R.CRESCENDAI_SALAMANDER)
    y = res.audio[: int(EXCERPT_S * SR)]
    audio = np.stack([apply_context(y, pid, c) for c in CONTEXTS])
    n = ex.notes
    stats = {
        "performance_id": pid,
        "excerpt_s": len(y) / SR,
        "n_notes": int(len(n)),
        "note_rate": float(len(n) / max(float(n["onset_sec"].max()), 1e-3)),
        "vel_mean": float(n["velocity"].mean()),
        "vel_sd": float(n["velocity"].std()),
        "pitch_mean": float(n["pitch"].mean()),
        "render_peak": res.peak,
    }
    return pid, audio.astype(np.float32), stats


# --------------------------------------------------------------------------- MuQ


def pool(h):
    """h: (T, D) -> (2D,) mean || std, population variance, +1e-8 inside the sqrt (as R-03)."""
    import torch

    h = h.double()
    mean = h.mean(0)
    var = ((h - mean) ** 2).mean(0)
    return torch.cat([mean, (var + 1e-8).sqrt()]).float().numpy()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--pilot", type=int, default=0, help="only the first N sampled clips")
    args = ap.parse_args()
    import torch
    from muq import MuQ

    from pianolens.audio import render as R

    ART.mkdir(parents=True, exist_ok=True)
    part = ART / "emb_partial"
    part.mkdir(exist_ok=True)
    sample_csv = ART / "sample.csv"
    if sample_csv.is_file():
        sample = pd.read_csv(sample_csv)
    else:
        sample = build_sample(args.workers)
        sample.to_csv(sample_csv, index=False)
    rows = sample.to_dict("records")
    if args.pilot:
        rows = rows[:: max(1, len(rows) // args.pilot)][: args.pilot]
    todo = [r for r in rows if not (part / f"{r['performance_id']}.npz").is_file()]
    print(f"{len(rows)} clips, {len(todo)} to do", flush=True)

    dev = "mps" if torch.backends.mps.is_available() else "cpu"
    model = MuQ.from_pretrained(MODEL_ID).to(dev).eval()
    t0 = time.time()
    t_muq = 0.0
    done = 0
    stats_path = ART / "excerpt_stats.jsonl"
    with ProcessPoolExecutor(args.workers) as ex, open(stats_path, "a") as fstats:
        for pid, audio, stats in ex.map(render_clip, todo, chunksize=1):
            ta = time.time()
            with torch.no_grad():
                o = model(torch.from_numpy(audio).to(dev), output_hidden_states=True)
                hs = torch.stack(list(o.hidden_states)).cpu()  # (13, 4, T, 1024)
            layers = torch.cat([hs, hs[9:13].mean(0, keepdim=True)])  # (14, 4, T, 1024)
            pooled = np.stack([np.stack([pool(layers[k, c]) for k in range(14)])
                               for c in range(len(CONTEXTS))])  # (4, 14, 2048)
            t_muq += time.time() - ta
            stats["n_frames"] = int(hs.shape[2])
            np.savez(part / f"{pid}.npz", pooled=pooled.astype(np.float32))
            fstats.write(json.dumps(stats) + "\n")
            fstats.flush()
            done += 1
            if done % 50 == 0 or done == len(todo):
                el = time.time() - t0
                print(f"{done}/{len(todo)} {el:.0f}s {el / done:.2f}s/clip "
                      f"(muq {t_muq / done:.2f}s/clip)", flush=True)
    wall = time.time() - t0

    if args.pilot:
        print(json.dumps({"pilot_clips": done, "wall_s": round(wall, 1),
                          "s_per_clip": round(wall / max(done, 1), 2),
                          "muq_s_per_clip": round(t_muq / max(done, 1), 2)}))
        return

    ids = sample.performance_id.tolist()
    l912 = np.empty((len(ids), len(CONTEXTS), 2048), np.float32)
    layers_all = np.empty((len(ids), len(CONTEXTS), 14, 2048), np.float16)
    for i, pid in enumerate(ids):
        z = np.load(part / f"{pid}.npz")["pooled"]
        l912[i] = z[:, 13]
        layers_all[i] = z.astype(np.float16)
    np.savez(ART / "embeddings.npz", ids=np.array(ids), contexts=np.array(CONTEXTS), l912=l912,
             layers=layers_all)
    st = pd.read_json(stats_path, lines=True).drop_duplicates("performance_id", keep="last")
    st.to_csv(ART / "excerpt_stats.csv", index=False)
    meta = {"model": MODEL_ID, "device": dev, "dtype": "float32", "n": len(ids),
            "new_clips": done, "wall_s_new": round(wall, 1), "torch": torch.__version__,
            "render_config": R.CRESCENDAI_SALAMANDER.config_hash(),
            "fluidsynth": R.fluidsynth_version(), "contexts": CONTEXTS,
            "context_ranges": CONTEXT_RANGES, "rectype_to_context": RECTYPE_TO_CONTEXT,
            "excerpt_s": EXCERPT_S, "per_level": PER_LEVEL, "sample_seed": SAMPLE_SEED}
    (ART / "build_meta.json").write_text(json.dumps(meta, indent=2))
    print(json.dumps({k: meta[k] for k in ("n", "new_clips", "wall_s_new")}))


if __name__ == "__main__":
    main()
