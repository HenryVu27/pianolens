"""The analysis worker: ``python -m pianolens.app.pipeline <job dir>``.

Steps (each recorded in ``status.json``):

1. ``transcribe`` (audio input only): ffmpeg converts the upload to 44.1 kHz WAV, Transkun 2.0.1
   (the A-01 transcriber, its own venv under ``data/interim/envs/transkun``) writes MIDI, and
   ``pianolens.audio.transcription.onset_sanity`` checks it for gross failures. Optionally the
   A-01b rule filter removes likely transcription extras (off by default).
2. ``align``: the first take is aligned to the score once, as a fast check that the recording is
   the chosen piece (match ratio, alignment-suspect flag) before the long steps.
3. ``report``: ``pianolens.report.report_from_files`` (features, PianoCoRe references, per-bar
   expert check, practise items) and ``write_report`` -> ``report.html`` / ``report.json``.
4. ``clips``: ``pianolens.compare.inputs_from_report`` + ``build_comparison`` -> ``compare/``.

All files stay inside the job folder (under ``data/interim/app``); nothing is uploaded anywhere.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import signal
import subprocess
import sys
import time
import traceback
import warnings
from pathlib import Path
from typing import Any

from pianolens.app.jobs import AUDIO_EXT, set_step, update_status

REPO = Path(__file__).resolve().parents[3]
TRANSKUN_ENV = REPO / "data" / "interim" / "envs" / "transkun"
TRANSKUN_CAPTURE_MODEL = "Transkun V2"  # PianoCoRe's name for the same model family (A-01 floor)

AUDIO_NOTE = ("Input: a transcription of an uploaded audio recording (Transkun). From phone or "
              "room audio, timing and tempo are trustworthy (A-01). Extra notes, velocity "
              "(dynamics, voicing) and pedal are low confidence; wrong and missed notes are read "
              "against expert transcriptions of the same piece.")  # fmt: skip


class Cancelled(Exception):
    pass


def transkun_binary() -> Path:
    """The Transkun CLI: ``$PIANOLENS_TRANSKUN`` or the A-01 venv."""
    env = os.environ.get("PIANOLENS_TRANSKUN")
    return Path(env) if env else TRANSKUN_ENV / "bin" / "transkun"


def transkun_version() -> str:
    b = transkun_binary()
    for d in (b.parent.parent / "lib").glob("python*/site-packages/transkun-*.dist-info"):
        return "Transkun " + d.name.split("-")[1].removesuffix(".dist")
    return "Transkun"


def to_wav(src: Path, dst: Path) -> Path:
    """Any audio ffmpeg reads -> 44.1 kHz 16-bit WAV (channels kept)."""
    subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y", "-i",
                    str(src), "-ar", "44100", "-c:a", "pcm_s16le", str(dst)],
                   check=True)  # fmt: skip
    return dst


def transcribe(wav: Path, out_mid: Path) -> dict[str, Any]:
    """Run Transkun on ``wav``; MPS first, CPU if that fails."""
    b = transkun_binary()
    if not b.is_file():
        raise FileNotFoundError(f"Transkun not found at {b}; see docs/APP.md (audio input)")
    t0 = time.time()
    err = ""
    for dev in ("mps", "cpu"):
        r = subprocess.run([str(b), "--device", dev, str(wav), str(out_mid)],
                           capture_output=True, text=True)  # fmt: skip
        if r.returncode == 0 and out_mid.is_file():
            return {"device": dev, "seconds": time.time() - t0, "model": transkun_version()}
        err = (r.stderr or r.stdout)[-2000:]
    raise RuntimeError(f"Transkun failed: {err}")


def midi_sanity(mid: Path) -> dict[str, Any]:
    import numpy as np
    import pretty_midi

    from pianolens.audio.transcription import onset_sanity

    pm = pretty_midi.PrettyMIDI(str(mid))
    notes = [(n.start, n.end - n.start, n.pitch, n.velocity) for i in pm.instruments
             for n in i.notes]  # fmt: skip
    arr = np.array(notes, dtype=[("onset_sec", "f8"), ("duration_sec", "f8"), ("pitch", "i4"),
                                 ("velocity", "i4")])  # fmt: skip
    return onset_sanity(arr)


def filter_extras(mid: Path, dst: Path) -> dict[str, Any]:
    """A-01b rule filter with the validated parameters when present (as the report CLI)."""
    from pianolens.audio.extra_filter import filter_midi

    cv = REPO / "data" / "interim" / "pianovam_a01b" / "cv.json"
    params = json.loads(cv.read_text())["final"]["rule_params"] if cv.is_file() else None
    return filter_midi(mid, dst, None, rule_params=params)


# =========================================================================== the run


def run(job_dir: Path) -> None:
    job = json.loads((job_dir / "job.json").read_text())
    spec = job["spec"]
    update_status(job_dir, state="running", pid=os.getpid(), started=time.time(), message="")
    warnings.filterwarnings("ignore")
    logging.basicConfig(level=logging.WARNING)
    work = job_dir / "work"
    work.mkdir(exist_ok=True)
    takes = [job_dir / "inputs" / t["file"] for t in job["takes"]]
    audio = spec["input_kind"] == "audio"
    notes: list[str] = []
    summary: dict[str, Any] = {"input_kind": spec["input_kind"], "n_takes": len(takes)}

    # ---------------------------------------------------------------- 1. transcribe
    mids: list[Path] = []
    wav0: Path | None = None
    if audio:
        set_step(job_dir, "transcribe", "running", "converting audio")
        info = []
        for k, t in enumerate(takes, 1):
            if t.suffix.lower() not in AUDIO_EXT:
                raise ValueError(f"{t.name}: not an audio file")
            wav = to_wav(t, work / f"take{k}.wav")
            wav0 = wav0 or wav
            set_step(job_dir, "transcribe", "running", f"take {k} of {len(takes)}",
                     (k - 1) / len(takes))
            mid = work / f"take{k}.mid"
            ti = transcribe(wav, mid)
            ti["sanity"] = midi_sanity(mid)
            if spec.get("filter_extras"):
                fi = filter_extras(mid, work / f"take{k}_filtered.mid")
                ti["extra_filter"] = {"n_in": fi["n_in"], "n_removed": fi["n_removed"]}
                mid = work / f"take{k}_filtered.mid"
            info.append(ti)
            mids.append(mid)
        model = info[0]["model"]
        summary["transcription"] = info
        notes.append(AUDIO_NOTE + f" Transcriber: {model}.")
        if spec.get("filter_extras"):
            n_rm = sum(i["extra_filter"]["n_removed"] for i in info)
            n_in = sum(i["extra_filter"]["n_in"] for i in info)
            notes.append(f"Extra-note filter (rule, A-01b) removed {n_rm} of {n_in} transcribed "
                         "notes before scoring. Extra-note flags stay low confidence.")
        secs = sum(i["seconds"] for i in info)
        set_step(job_dir, "transcribe", "done", f"{model}, {secs:.0f} s", 1.0)
    else:
        mids = takes
    provenance = "transcribed" if audio else spec.get("provenance", "unknown")

    # ---------------------------------------------------------------- score
    score: Path | None = None
    if spec.get("score_source") == "upload":
        score = job_dir / "inputs" / job["score_upload"]["file"]
    elif spec.get("piece_id"):
        from pianolens.app.catalog import load_catalog, resolve_score

        root = job_dir.parent.parent
        piece = next((p for p in load_catalog(root) if p.piece_id == spec["piece_id"]), None)
        if piece is None:
            raise ValueError(f"piece {spec['piece_id']!r} is not in the catalogue")
        score = resolve_score(piece, root)
    if score is None and not spec.get("piece_id"):
        raise ValueError("choose a supported piece or upload a score")

    # ---------------------------------------------------------------- 2. align (fast check)
    set_step(job_dir, "align", "running")
    from pianolens.align import align_performance
    from pianolens.features.correctness import correctness
    from pianolens.report.io import find_score, load_performance, load_score

    sc_path = score or find_score(spec["piece_id"])
    if sc_path is None:
        raise FileNotFoundError("no score file for this piece")
    ap = align_performance(load_score(sc_path, spec.get("piece_id")),
                           load_performance(mids[0], provenance, spec.get("piece_id")))
    cs = correctness(ap).summary
    summary["align"] = {"match_ratio": float(cs.get("match_ratio", float("nan"))),
                        "error_rate": float(cs.get("error_rate", float("nan"))),
                        "alignment_suspect": bool(cs.get("alignment_suspect", False))}  # fmt: skip
    detail = f"{100 * summary['align']['match_ratio']:.0f}% of notes matched"
    if summary["align"]["alignment_suspect"]:
        detail += " - alignment suspect: is this the right piece?"
    set_step(job_dir, "align", "done", detail)
    del ap

    # ---------------------------------------------------------------- 3. report
    set_step(job_dir, "report", "running", "features, references, expert check")
    from pianolens.report import report_from_files, write_report

    rep = report_from_files(
        mids[0], score=score, piece_id=spec.get("piece_id") or None, provenance=provenance,
        title=spec.get("title") or "", takes=mids[1:],
        exclude_references=spec.get("exclude_references") or [], notes=notes,
        expert_capture_model=TRANSKUN_CAPTURE_MODEL if audio else None)  # fmt: skip
    write_report(rep, job_dir / "report.html")
    summary["report"] = {
        "n_practise": len(rep.get("practise", [])),
        "n_issues_tiered": sum(1 for i in rep.get("issues", []) if i.get("tier") != "none"),
        "error_rate": rep.get("correctness", {}).get("error_rate"),
        "n_references": rep.get("references", {}).get("tier_d_total"),
        "errors": rep.get("errors") or {},
    }  # fmt: skip
    set_step(job_dir, "report", "done",
             f"{summary['report']['n_practise']} practise items, "
             f"{summary['report']['n_references'] or 0} references")  # fmt: skip
    update_status(job_dir, summary=summary)

    # ---------------------------------------------------------------- 4. clips
    if spec.get("clips", True):
        set_step(job_dir, "clips", "running", "selecting passages", 0.0)
        from pianolens.compare import CompareConfig, build_comparison, inputs_from_report

        inp = inputs_from_report(job_dir / "report.json", audio_path=wav0, name=job["id"],
                                 extra_exclude=spec.get("exclude_references") or [])
        n_win = [0, 0]

        def log(s: str) -> None:
            m = re.match(r"(\d+) windows", s)
            if m:
                n_win[0] = int(m.group(1))
            elif re.match(r"w\d+ ", s):
                n_win[1] += 1
            if n_win[0]:
                set_step(job_dir, "clips", "running", f"passage {n_win[1]} of {n_win[0]}",
                         n_win[1] / n_win[0])

        cfg = CompareConfig(max_windows=int(spec.get("max_windows", 8)))
        m = build_comparison(inp, job_dir / "compare", cfg, log=log)
        n_clips = sum(len(w["clips"]) for w in m["windows"])
        summary["clips"] = {"n_windows": len(m["windows"]), "n_clips": n_clips}
        set_step(job_dir, "clips", "done", f"{len(m['windows'])} passages, {n_clips} clips", 1.0)
    update_status(job_dir, state="done", summary=summary, finished=time.time(),
                  message="Finished.")


def main(argv: list[str]) -> int:
    job_dir = Path(argv[1]).resolve()

    def on_term(signum: int, frame: Any) -> None:
        raise Cancelled()

    signal.signal(signal.SIGTERM, on_term)
    try:
        run(job_dir)
        return 0
    except Cancelled:
        _fail(job_dir, "cancelled", "Cancelled.")
        return 1
    except Exception as e:  # noqa: BLE001 - reported to the user
        traceback.print_exc()
        _fail(job_dir, "failed", f"{type(e).__name__}: {e}")
        return 1
    finally:
        tmp = job_dir / "work" / "tmp"
        if tmp.exists():
            shutil.rmtree(tmp, ignore_errors=True)


def _fail(job_dir: Path, state: str, msg: str) -> None:
    st = json.loads((job_dir / "status.json").read_text())
    for s in st.get("steps", []):
        if s["state"] == "running":
            set_step(job_dir, s["name"], "failed" if state == "failed" else "cancelled")
    update_status(job_dir, state=state, message=msg, finished=time.time())


if __name__ == "__main__":
    sys.exit(main(sys.argv))
