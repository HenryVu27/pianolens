"""P-01: A/B comparison clips + players for Henry's 5 takes and F-08 samples (a) and (c).

    uv run python scripts/build_compare_p01.py [--only 01,a] [--no-henry]

Inputs: the Transkun reports in ``data/interim/reports/henry/`` (with the original phone audio
from ``data/raw/henry_takes/``) and ``data/interim/reports/{a,c}_*.json`` (MIDI only). Writes
``data/interim/compare/<name>/`` (clips, ``manifest.json``, ``player.html``) and
``data/interim/compare/checks.json``. PERSONAL DATA: everything under ``henry_*`` contains
Henry's recordings; never commit, upload or share it.

Checks (listening proxies), per clip:
* duration: clip length vs the requested span; body (window) length per clip;
* cut: median onset of the window's first score position vs the window-on time in the clip
  (|error| <= 50 ms);
* audio: for the original recording, the detected onset nearest the window-on time;
* decode: each MP3 decoded by ffmpeg, its length and its lag against the pre-encode clip;
* expert: the share of the window's score notes found in the expert's score at the mapped beats.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import warnings
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "data" / "interim" / "reports"
RAW = ROOT / "data" / "raw" / "henry_takes"
OUT = ROOT / "data" / "interim" / "compare"
HENRY = {"01": "01_op27no2", "02": "02_op64no2", "03": "03_op9no3", "04": "04_op_posth",
         "05": "05_op9no1"}  # fmt: skip
SAMPLES = {"a": "a_asap_op10no3_sunmeiting", "c": "c_asap_op10no3_perturbed"}


def jobs(only: set[str] | None, henry: bool) -> list[tuple[str, Path, Path | None, str]]:
    out = []
    if henry:
        for k, stem in HENRY.items():
            if only and k not in only:
                continue
            wav = sorted(RAW.glob(f"{k}_*.wav"))
            out.append((k, REPORTS / "henry" / f"{stem}.json", wav[0] if wav else None,
                        f"henry_{stem}"))
    for k, stem in SAMPLES.items():
        if only and k not in only:
            continue
        out.append((k, REPORTS / f"{stem}.json", None, f"sample_{stem}"))
    return out


def decode_check(out_dir: Path, manifest: dict) -> dict[str, dict]:
    """Decode each MP3 and compare it with the clip span (length) and itself re-cut (lag)."""
    from pianolens.compare import clips as C

    res = {}
    for w in manifest["windows"]:
        for kind, c in w["clips"].items():
            y = C.decode_audio(out_dir / c["path"])
            res[f"{w['id']}:{kind}"] = {"decoded_sec": len(y) / C.SAMPLE_RATE,
                                        "decoded_minus_clip_ms":
                                            1000 * (len(y) / C.SAMPLE_RATE - c["duration_sec"])}
    return res


def summarize(manifest: dict, dec: dict) -> dict:
    cut, dur, span, dd, body, lagr = [], [], [], [], [], []
    aud: dict[str, list[float]] = {}
    train: dict[str, list[tuple[float, float]]] = {}
    kinds: dict[str, int] = {}
    for w in manifest["windows"]:
        for kind, c in w["clips"].items():
            kinds[kind] = kinds.get(kind, 0) + 1
            dur.append(abs(c["duration_error_ms"]))
            if c.get("cut_error_ms") is not None:
                cut.append(abs(c["cut_error_ms"]))
            aud.setdefault(kind, [])
            if c.get("audio_onset_error_ms") is not None:
                aud[kind].append(c["audio_onset_error_ms"])
            if c.get("onset_train_lag_ms") is not None:
                train.setdefault(kind, []).append((c["onset_train_lag_ms"],
                                                   c["onset_train_corr"]))
            if c.get("lag_vs_render_ms") is not None:
                lagr.append(c["lag_vs_render_ms"])
            if kind.startswith("expert"):
                span.append(c["score_span_match"])
            dd.append(dec[f"{w['id']}:{kind}"]["decoded_minus_clip_ms"])
        b = w["window_body_sec"]
        if "user_audio" in b and "user_render" in b:
            body.append(abs(b["user_audio"] - b["user_render"]))

    def st(x):
        x = np.asarray(x, float)
        return None if not len(x) else {"n": len(x), "median": float(np.median(x)),
                                        "max": float(np.max(np.abs(x)))}
    def within(x):
        return float(np.mean(np.abs(x) <= 50)) if len(x) else None
    return {"n_windows": len(manifest["windows"]), "clips": kinds,
            "duration_error_ms": st(dur), "cut_error_ms_abs": st(cut),
            "cut_within_50ms": float(np.mean(np.asarray(cut) <= 50)) if cut else None,
            "audio_onset_error_ms": {k: {**(st(v) or {}), "found": f"{len(v)}/{kinds[k]}",
                                         "within_50ms": within(v)} for k, v in aud.items()},
            "onset_train_lag_ms": {k: {**(st([a for a, _ in v]) or {}),
                                       "within_50ms": float(np.mean([abs(a) <= 50 for a, _ in v])),
                                       "corr_median": float(np.median([c for _, c in v]))}
                                   for k, v in train.items()},
            "user_audio_lag_vs_render_ms": st(lagr),
            "user_audio_vs_render_body_ms": st(1000 * np.asarray(body)) if body else None,
            "expert_score_span_match": st(span),
            "decoded_minus_clip_ms": st(dd),
            "user_audio_lag": manifest["audio"].get("user_audio_lag"),
            "runtime_sec": manifest["runtime_sec"]}  # fmt: skip


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--no-henry", action="store_true")
    ap.add_argument("--summarize-only", action="store_true",
                    help="recompute checks.json from the existing manifests")
    args = ap.parse_args()
    warnings.filterwarnings("ignore")
    logging.basicConfig(level=logging.ERROR)
    from pianolens.compare import build_comparison, inputs_from_report, write_player

    only = {s for s in args.only.split(",") if s} or None
    checks_path = OUT / "checks.json"
    checks = json.loads(checks_path.read_text()) if checks_path.is_file() else {}
    for _key, rep_path, wav, name in jobs(only, not args.no_henry):
        print(f"== {name}", flush=True)
        out_dir = OUT / name
        if args.summarize_only:
            if not (out_dir / "manifest.json").is_file():
                continue
            m = json.loads((out_dir / "manifest.json").read_text())
        else:
            inp = inputs_from_report(rep_path, audio_path=wav, name=name)
            m = build_comparison(inp, out_dir, log=lambda s: print("  ", s, flush=True))
            write_player(out_dir / "manifest.json")
        dec = decode_check(out_dir, m)
        checks[name] = summarize(m, dec)
        print(json.dumps(checks[name], indent=1), flush=True)
        checks_path.write_text(json.dumps(checks, indent=1))
    return None


if __name__ == "__main__":
    sys.exit(main())
