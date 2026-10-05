"""Analysis jobs on disk: one folder per upload, a worker process per run, status as JSON.

Layout of ``<app root>/jobs/<job id>/``::

    job.json       what was asked: piece, input kind, options, input file names and hashes
    status.json    state, steps with start/end times, messages, worker pid (written atomically)
    inputs/        the uploaded files (take1.*, take2.*, ..., score.* for an uploaded score)
    work/          intermediate files (converted audio, transcriptions)
    report.html / report.json      the F-08 report (``pianolens.report.write_report``)
    compare/       P-01 clips and manifest.json
    worker.log     the worker's stdout / stderr

The job id is a hash of the uploaded bytes, the piece, the options and the analysis code
(:func:`code_version`), so the same upload with the same settings reuses the cached result
until the code changes; after a code change the same upload runs again (DEFECTS DF-05). Jobs
run in a separate process (``python -m pianolens.app.pipeline <job dir>``) in its own process
group, so cancelling kills the transcriber and the renderer too. Nothing here makes network calls.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

__all__ = ["AUDIO_EXT", "MIDI_EXT", "SCORE_EXT", "STEPS", "JobStore", "Upload", "code_version",
           "default_root"]

AUDIO_EXT = (".wav", ".mp3", ".m4a", ".flac", ".aac", ".ogg")
MIDI_EXT = (".mid", ".midi")
SCORE_EXT = (".musicxml", ".xml", ".mxl", ".mei")
STEPS = ("transcribe", "align", "report", "clips")
STEP_LABELS = {"transcribe": "Transcribe audio (Transkun)",
               "align": "Align to the score",
               "report": "Features, expert references and report",
               "clips": "Comparison clips"}  # fmt: skip
TERMINAL = ("done", "failed", "cancelled", "interrupted", "stopped")
#: Bump for a change that alters results but not the Python source under ``src/pianolens``
#: (e.g. a new calibration data file or transcriber). Source changes are picked up by the hash.
PIPELINE_VERSION = 1
#: Spec fields that do not change the analysis and so are not part of the job id.
_NOT_HASHED = ("title", "composer", "ignore_wrong_piece")
#: Modules that only serve pages; editing them does not make stored results stale.
_UI_ONLY = ("app/server.py", "app/pages.py")


def code_version() -> str:
    """Hash of the analysis code: every ``.py`` file under ``src/pianolens`` (report, features,
    alignment, compare, the app worker, ...) except the page-serving modules, plus
    ``PIPELINE_VERSION``. About 80 small files, read on each new upload."""
    src = Path(__file__).resolve().parents[1]
    h = hashlib.sha256(f"pipeline:{PIPELINE_VERSION}".encode())
    for f in sorted(src.rglob("*.py")):
        rel = f.relative_to(src).as_posix()
        if rel in _UI_ONLY:
            continue
        h.update(rel.encode() + b"\0" + f.read_bytes() + b"\0")
    return h.hexdigest()[:12]


def default_root() -> Path:
    """``data/interim/app`` of this repository (gitignored)."""
    return Path(__file__).resolve().parents[3] / "data" / "interim" / "app"


@dataclass
class Upload:
    """One uploaded file: its original name and bytes."""

    filename: str
    data: bytes

    @property
    def ext(self) -> str:
        return Path(self.filename).suffix.lower()

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.data).hexdigest()


@dataclass
class JobSpec:
    """What one analysis is about (``job.json``)."""

    piece_id: str | None
    title: str
    composer: str = ""
    input_kind: str = "midi"  # "audio" or "midi"
    provenance: str = "unknown"  # audio input is always "transcribed"; MIDI can be marked so too
    capture_model: str | None = None  # transcriber of transcribed input (PianoCoRe name), if known
    filter_extras: bool = False
    exclude_references: list[str] = field(default_factory=list)
    max_windows: int = 8
    clips: bool = True
    score_source: str = ""  # "catalog", "upload" or ""
    code_version: str = ""  # code_version() at upload; filled in by JobStore.create
    ignore_wrong_piece: bool = False  # run on even if the quick check says another piece

    @property
    def transcribed(self) -> bool:
        return self.provenance == "transcribed"


def _write_json(path: Path, data: Any) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=1))
    tmp.replace(path)


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def _alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


class JobStore:
    """Create, run, list, cancel and delete jobs under ``root / "jobs"``."""

    def __init__(self, root: Path | str | None = None, python: str | None = None) -> None:
        self.root = Path(root) if root else default_root()
        self.jobs_dir = self.root / "jobs"
        self.jobs_dir.mkdir(parents=True, exist_ok=True)
        self.python = python or sys.executable
        self._procs: dict[str, subprocess.Popen] = {}

    # ------------------------------------------------------------------ ids and paths

    @staticmethod
    def job_id(spec: JobSpec, takes: list[Upload], score: Upload | None) -> str:
        h = hashlib.sha256()
        payload = {k: v for k, v in spec.__dict__.items() if k not in _NOT_HASHED}
        h.update(json.dumps(payload, sort_keys=True).encode())
        for u in takes:
            h.update(u.sha256.encode())
        if score is not None:
            h.update(b"score:" + score.sha256.encode())
        return h.hexdigest()[:16]

    def path(self, job_id: str) -> Path:
        if not job_id or not all(c in "0123456789abcdef" for c in job_id):
            raise KeyError(job_id)
        return self.jobs_dir / job_id

    # ------------------------------------------------------------------ create / run

    def create(self, spec: JobSpec, takes: list[Upload], score: Upload | None = None,
               start: bool = True) -> tuple[str, bool]:
        """Store the inputs and start the worker. Returns (job id, reused) where ``reused``
        means a finished or running job with the same inputs already existed."""
        if not takes:
            raise ValueError("no performance uploaded")
        if not spec.code_version:
            spec.code_version = code_version()
        jid = self.job_id(spec, takes, score)
        d = self.path(jid)
        st = self.status(jid)
        if st and st["state"] in ("done", "running", "queued"):
            return jid, True
        if d.exists():
            shutil.rmtree(d)
        (d / "inputs").mkdir(parents=True)
        (d / "work").mkdir()
        names = []
        for k, u in enumerate(takes, 1):
            f = d / "inputs" / f"take{k}{u.ext}"
            f.write_bytes(u.data)
            names.append({"file": f.name, "original_name": Path(u.filename).name,
                          "sha256": u.sha256, "bytes": len(u.data)})  # fmt: skip
        score_info = None
        if score is not None:
            f = d / "inputs" / f"score{score.ext}"
            f.write_bytes(score.data)
            score_info = {"file": f.name, "original_name": Path(score.filename).name,
                          "sha256": score.sha256}  # fmt: skip
        job = {"id": jid, "created": time.strftime("%Y-%m-%d %H:%M:%S"),
               "spec": spec.__dict__, "takes": names, "score_upload": score_info}  # fmt: skip
        _write_json(d / "job.json", job)
        steps = [s for s in STEPS if (s != "transcribe" or spec.input_kind == "audio")
                 and (s != "clips" or spec.clips)]
        _write_json(d / "status.json", {
            "state": "queued", "steps": [{"name": s, "label": STEP_LABELS[s], "state": "pending"}
                                         for s in steps],
            "message": "", "updated": time.time()})  # fmt: skip
        if start:
            self.start(jid)
        return jid, False

    def start(self, job_id: str) -> None:
        d = self.path(job_id)
        log = open(d / "worker.log", "ab")  # noqa: SIM115 - handed to the child
        env = {**os.environ, "PYTHONUNBUFFERED": "1"}
        p = subprocess.Popen([self.python, "-m", "pianolens.app.pipeline", str(d)],
                             stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                             start_new_session=True, env=env)  # fmt: skip
        log.close()
        self._procs[job_id] = p
        (d / "worker.pid").write_text(str(p.pid))  # the worker owns status.json from here on

    def _pid(self, job_id: str) -> int | None:
        try:
            return int((self.path(job_id) / "worker.pid").read_text())
        except (OSError, ValueError):
            return None

    def cancel(self, job_id: str) -> bool:
        st = self.status(job_id)
        if not st or st["state"] in TERMINAL:
            return False
        pid = self._pid(job_id)
        if pid and _alive(pid):
            try:
                os.killpg(pid, signal.SIGTERM)
            except (ProcessLookupError, PermissionError):
                pass
            p = self._procs.pop(job_id, None)
            if p is not None:
                try:
                    p.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(pid, signal.SIGKILL)
        st = self.status(job_id) or st
        st["state"] = "cancelled"
        st["message"] = "Cancelled."
        for s in st.get("steps", []):
            if s["state"] == "running":
                s["state"] = "cancelled"
        st["updated"] = time.time()
        _write_json(self.path(job_id) / "status.json", st)
        return True

    # ------------------------------------------------------------------ read

    def job(self, job_id: str) -> dict[str, Any] | None:
        return _read_json(self.path(job_id) / "job.json")

    def status(self, job_id: str) -> dict[str, Any] | None:
        d = self.path(job_id)
        st = _read_json(d / "status.json")
        if st is None:
            return None
        p = self._procs.get(job_id)
        pid = self._pid(job_id)
        dead = (p.poll() is not None) if p is not None else (pid is not None
                                                              and not _alive(pid))
        if st["state"] in ("running", "queued") and dead:
            # the worker died without writing a final state (killed, or the server restarted)
            st["state"] = "interrupted"
            st["message"] = st.get("message") or "The worker stopped unexpectedly."
        return st

    def list(self) -> list[dict[str, Any]]:
        """All jobs, newest first: job.json plus the current state."""
        out = []
        for d in self.jobs_dir.iterdir() if self.jobs_dir.is_dir() else []:
            j = _read_json(d / "job.json")
            if j is None:
                continue
            st = self.status(d.name) or {}
            j["state"] = st.get("state", "unknown")
            j["summary"] = st.get("summary", {})
            out.append(j)
        return sorted(out, key=lambda j: j.get("created", ""), reverse=True)

    def delete(self, job_id: str) -> bool:
        d = self.path(job_id)
        if not d.is_dir():
            return False
        st = self.status(job_id)
        if st and st["state"] in ("running", "queued"):
            self.cancel(job_id)
        shutil.rmtree(d)
        return True


def update_status(job_dir: Path, **kw: Any) -> dict[str, Any]:
    """Worker side: merge ``kw`` into ``status.json``."""
    st = _read_json(job_dir / "status.json") or {"steps": []}
    st.update(kw)
    st["updated"] = time.time()
    _write_json(job_dir / "status.json", st)
    return st


def set_step(job_dir: Path, name: str, state: str, detail: str | None = None,
             progress: float | None = None) -> None:
    """Worker side: set one step's state (``running``, ``done``, ``failed``, ``skipped``)."""
    st = _read_json(job_dir / "status.json") or {"steps": []}
    for s in st["steps"]:
        if s["name"] == name:
            if state == "running" and s["state"] != "running":
                s["started"] = time.time()
            if state in ("done", "failed", "skipped"):
                s["ended"] = time.time()
            s["state"] = state
            if detail is not None:
                s["detail"] = detail
            if progress is not None:
                s["progress"] = progress
    st["updated"] = time.time()
    _write_json(job_dir / "status.json", st)
