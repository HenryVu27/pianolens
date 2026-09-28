"""A-01 controlled check: transcription error where the true MIDI is known.

    uv run python scripts/a01_controlled_check.py [--skip-transcribe]

Three MAESTRO v3 Disklavier performances of pieces Henry recorded (Chopin Op. 27 No. 2, Op. 9
No. 3, Nocturne in C-sharp minor Op. posth.; MAESTRO has no Op. 64 No. 2 or Op. 9 No. 1) are
rendered with the S-02 piano (``pianolens.audio.render``, Salamander C5, FluidSynth, here at
44.1 kHz) in two conditions:

* ``clean``: the render as is (FluidSynth's default reverb included);
* ``phone``: ``pianolens.audio.phone.simulate_phone`` (synthetic room RT60 0.5 s, DRR 3 dB,
  high-pass 120 Hz, low-pass 12 kHz, pink noise at 35 dB SNR, -3 dBFS peak) followed by an AAC
  128 kbit/s round trip with ffmpeg (YouTube-like delivery; Henry's takes came from YouTube).

Each file is transcribed by Transkun (MPS) and Aria-AMT (``scripts/transcribe_aria_amt_mac.py``,
MPS). Scored against the MAESTRO MIDI: note F1 (onset 50 ms), onset error, velocity fit, pedal
usage; and downstream, both the true MIDI and the transcription are aligned to the PianoCoRe
MusicXML score and scored with F-02 correctness, so the error rate the transcriber adds is
measured in the report's own units.

Caveat: MAESTRO audio is the training domain of both transcribers, and one of these MIDIs is in
MAESTRO's train split (the audio here is a different piano, so this is not a leak of audio).
Salamander + synthetic room is not a real phone; the real takes stay the primary evidence.

Writes ``data/interim/henry_takes/controlled/`` (gitignored).
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data" / "interim" / "henry_takes"
OUT = BASE / "controlled"
ENVS = ROOT / "data" / "interim" / "envs"
MAESTRO = ROOT / "data" / "raw" / "maestro_v3_midi" / "maestro-v3.0.0"
PIECES = {  # tag: (score key in scores.json, MAESTRO midi)
    "op27no2": ("01", "2015/MIDI-Unprocessed_R1_D2-21-22_mid--AUDIO-from_mp3_22_R1_2015_wav--4.midi"),  # noqa: E501
    "op9no3": ("03", "2009/MIDI-Unprocessed_02_R1_2009_03-06_ORIG_MID--AUDIO_02_R1_2009_02_R1_2009_03_WAV.midi"),  # noqa: E501
    "op_posth": ("04", "2014/MIDI-UNPROCESSED_04-05_R1_2014_MID--AUDIO_05_R1_2014_wav--6.midi"),
}  # fmt: skip
CONDITIONS = ("clean", "phone")
TRANSCRIBERS = ("transkun", "aria_amt")


def render_all() -> None:
    from pianolens.audio.phone import PhoneSimConfig, simulate_phone
    from pianolens.audio.render import RenderConfig, render_midi

    cfg = RenderConfig(sample_rate=44_100)
    for seed, (tag, (_, rel)) in enumerate(PIECES.items()):
        d = OUT / tag
        d.mkdir(parents=True, exist_ok=True)
        shutil.copy(MAESTRO / rel, d / "gt.mid")
        if (d / "phone.wav").is_file():
            continue
        r = render_midi(d / "gt.mid", cfg)
        y = r.audio / max(1.0, r.peak)
        sf.write(d / "clean.wav", y, r.sample_rate, subtype="PCM_16")
        ph = simulate_phone(y, r.sample_rate, PhoneSimConfig(seed=seed))
        sf.write(d / "phone_pre.wav", ph, r.sample_rate, subtype="PCM_16")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", d / "phone_pre.wav", "-c:a", "aac",
                        "-b:a", "128k", d / "phone.m4a"], check=True)  # fmt: skip
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", d / "phone.m4a", "-ar", "48000",
                        "-ac", "1", "-c:a", "pcm_s16le", d / "phone.wav"], check=True)  # fmt: skip
        (d / "phone_pre.wav").unlink()
        (d / "render.json").write_text(json.dumps({"peak": r.peak, "config": cfg.config_hash(),
                                                   "sr": r.sample_rate}))  # fmt: skip


def transcribe_all() -> dict:
    times = {}
    wavs = [OUT / tag / f"{c}.wav" for tag in PIECES for c in CONDITIONS]
    for w in wavs:
        o = w.parent / f"{w.stem}_transkun.mid"
        t0 = time.time()
        subprocess.run([ENVS / "transkun" / "bin" / "transkun", "--device", "mps", w, o],
                       check=True, capture_output=True)  # fmt: skip
        times[f"{w.parent.name}/{w.stem}/transkun"] = time.time() - t0
    for w in wavs:
        t0 = time.time()
        subprocess.run([ENVS / "aria-amt" / "bin" / "python",
                        ROOT / "scripts" / "transcribe_aria_amt_mac.py", w, "--checkpoint",
                        ENVS / "aria-weights" / "piano-medium-double-1.0.safetensors",
                        "--out-dir", w.parent, "--device", "mps", "--names",
                        f"{w.stem}_aria_amt"], check=True, capture_output=True)  # fmt: skip
        times[f"{w.parent.name}/{w.stem}/aria_amt"] = time.time() - t0
    (OUT / "transcribe_times.json").write_text(json.dumps(times, indent=1))
    return times


def evaluate() -> pd.DataFrame:
    import logging

    warnings.filterwarnings("ignore")
    logging.disable(logging.WARNING)
    from pianolens.align import align_performance
    from pianolens.audio.transcription import (
        match_notes,
        note_f1,
        onset_sanity,
        pedal_summary,
        velocity_agreement,
    )
    from pianolens.features.correctness import correctness
    from pianolens.report.io import load_performance, load_score

    meta = json.loads((BASE / "scores" / "scores.json").read_text())
    rows = []
    for tag, (k, _) in PIECES.items():
        d = OUT / tag
        sc = load_score(BASE / "scores" / f"{k}_score.mxl", meta[k]["piece_id"])
        gt = load_performance(d / "gt.mid", "disklavier", meta[k]["piece_id"], "gt")
        gap = align_performance(sc, gt)
        gcr = correctness(gap)
        g_err = gcr.score_notes.set_index("score_id")["label"].astype(str)
        gn = gt.notes
        t0 = float(gn["onset_sec"].min())
        t1 = float((gn["onset_sec"] + gn["duration_sec"]).max())
        g_sus = pedal_summary(gt.pedal, t0, t1, 64)
        base = {"piece": tag, "gt_error_rate": gcr.summary["error_rate"],
                "gt_match_ratio": gcr.summary["match_ratio"], "gt_n_notes": len(gn),
                "gt_sus_down_fraction": g_sus["down_fraction"],
                "gt_sus_presses": g_sus["n_presses"]}  # fmt: skip
        for c in CONDITIONS:
            for t in TRANSCRIBERS:
                est = load_performance(d / f"{c}_{t}.mid", "transcribed", meta[k]["piece_id"], t)
                en = est.notes
                f = note_f1(gn, en, 0.05, estimate_offset=True)
                m = match_notes(gn, en, 0.05, offset=f["offset_sec"])
                v = velocity_agreement(np.array([gn["velocity"][i] for i, _ in m], float),
                                       np.array([en["velocity"][j] for _, j in m], float))
                eap = align_performance(sc, est)
                ecr = correctness(eap)
                e_err = ecr.score_notes.set_index("score_id")["label"].astype(str)
                ci = g_err.index.intersection(e_err.index)
                ge = g_err.loc[ci].isin(["wrong_pitch", "missed"])
                ee = e_err.loc[ci].isin(["wrong_pitch", "missed"])
                s = ecr.summary
                gsz = max(1.0, s["n_score_notes"])
                es = pedal_summary(est.pedal, t0 + f["offset_sec"], t1 + f["offset_sec"], 64)
                rows.append({**base, "condition": c, "transcriber": t, **{
                    "f1": f["f1"], "precision": f["precision"], "recall": f["recall"],
                    "offset_ms": 1000 * f["offset_sec"], "onset_err_rsd_ms":
                    f["onset_err_rsd_ms"], **v,
                    "est_error_rate": s["error_rate"], "est_match_ratio": s["match_ratio"],
                    "est_wrong_rate": s["n_wrong_pitch"] / gsz,
                    "est_missed_rate": s["n_missed"] / gsz, "est_extra_rate": s["n_extra"] / gsz,
                    "added_error_rate": s["error_rate"] - gcr.summary["error_rate"],
                    "score_err_new": int((ee & ~ge).sum()), "score_err_lost": int((ge & ~ee).sum()),
                    "score_err_gt": int(ge.sum()),
                    "est_sus_down_fraction": es["down_fraction"],
                    "est_sus_presses": es["n_presses"],
                    **{f"on_{a}": b for a, b in onset_sanity(en).items()},
                }})  # fmt: skip
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "controlled.csv", index=False)
    return df


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-transcribe", action="store_true")
    args = ap.parse_args()
    render_all()
    if not args.skip_transcribe:
        print(transcribe_all())
    df = evaluate()
    pd.set_option("display.width", 250)
    print(df.drop(columns=[c for c in df.columns if c.startswith("on_")]).round(3).T.to_string())


if __name__ == "__main__":
    main()
