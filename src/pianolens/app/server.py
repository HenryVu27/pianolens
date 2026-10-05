"""Local web server of the PianoLens app (P-02): standard library only, localhost only.

``serve(port)`` binds ``127.0.0.1`` and never makes outgoing requests; every page, script, style
and audio clip comes from this server. Requests whose ``Host`` is not this machine's loopback
address are refused (DNS-rebinding guard), and state-changing requests (POST) from another
origin are refused (a web page elsewhere cannot start or delete analyses).

Routes::

    GET  /                           piece picker + upload form
    GET  /history                    past analyses
    GET  /jobs/<id>                  progress, then results
    GET  /jobs/<id>/report           the F-08 report page (shown in an iframe)
    GET  /jobs/<id>/clips/<file>     one comparison clip (MP3)
    GET  /api/pieces                 the catalogue (JSON)
    GET  /api/jobs/<id>              status + results data (JSON)
    POST /api/jobs                   multipart upload -> {"id": ...}
    POST /api/jobs/<id>/cancel | /delete | /retry | /override
                                     (override = run a job the wrong-piece check stopped)
    GET  /static/<file>              app.css, app.js
"""

from __future__ import annotations

import json
import re
import threading
from email.parser import BytesParser
from email.policy import HTTP
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from pianolens.app import pages
from pianolens.app.catalog import Piece, load_catalog
from pianolens.app.jobs import (
    AUDIO_EXT,
    MIDI_EXT,
    SCORE_EXT,
    JobSpec,
    JobStore,
    Upload,
    _write_json,
)
from pianolens.app.results import results_data

__all__ = ["App", "make_server", "parse_multipart", "serve"]

STATIC = Path(__file__).with_name("static")
MAX_UPLOAD = 1 << 30  # 1 GiB
_JOB = r"(?P<id>[0-9a-f]{16})"
CSP_APP = ("default-src 'self'; img-src 'self' data:; media-src 'self' blob:; "
           "style-src 'self'; script-src 'self'; connect-src 'self'; frame-src 'self'; "
           "form-action 'self'; base-uri 'none'; frame-ancestors 'self'")  # fmt: skip
CSP_REPORT = ("default-src 'none'; style-src 'unsafe-inline'; img-src data:; "
              "frame-ancestors 'self'")  # fmt: skip
PROVENANCES = ("disklavier", "sensor", "unknown", "synthetic", "transcribed")
#: Upload-form value -> (provenance, transcriber as PianoCoRe names it). Transcribed MIDI is
#: handled like audio input after its transcription step (extras low confidence, expert check
#: against transcriptions); with a known transcriber the check uses that transcriber only.
TRANSCRIBED_CHOICES = {"transcribed:transkun": ("transcribed", "Transkun V2"),
                       "transcribed": ("transcribed", None)}  # fmt: skip
AUDIO_CAPTURE_MODEL = "Transkun V2"  # the app's own transcriber (pipeline.TRANSKUN_CAPTURE_MODEL)


Fields = dict[str, str]
Files = dict[str, list[Upload]]


def parse_multipart(content_type: str, body: bytes) -> tuple[Fields, Files]:
    """``multipart/form-data`` -> (text fields, file fields). Standard library email parser."""
    msg = BytesParser(policy=HTTP).parsebytes(
        b"Content-Type: " + content_type.encode("latin-1") + b"\r\n\r\n" + body)
    fields: dict[str, str] = {}
    files: dict[str, list[Upload]] = {}
    if not msg.is_multipart():
        raise ValueError("expected multipart/form-data")
    for part in msg.iter_parts():
        name = part.get_param("name", header="content-disposition")
        if not name:
            continue
        fn = part.get_filename()
        data = part.get_payload(decode=True) or b""
        if fn is not None:
            if data:
                files.setdefault(name, []).append(Upload(fn, data))
        else:
            fields[name] = data.decode("utf-8", "replace")
    return fields, files


class App:
    """State shared by request handlers: the job store and the catalogue."""

    def __init__(self, root: Path | str | None = None, catalog: list[Piece] | None = None,
                 port: int = 0) -> None:
        self.store = JobStore(root)
        self.root = self.store.root
        self._catalog = catalog
        self._lock = threading.Lock()
        self.port = port

    @property
    def catalog(self) -> list[Piece]:
        with self._lock:
            if self._catalog is None:
                self._catalog = load_catalog(self.root)
            return self._catalog

    def piece(self, piece_id: str) -> Piece | None:
        return next((p for p in self.catalog if p.piece_id == piece_id), None)

    def create_job(self, fields: Fields, files: Files) -> tuple[str, bool]:
        takes = files.get("performance", [])
        if not takes:
            raise ValueError("Upload a recording (audio) or a MIDI file.")
        exts = {u.ext for u in takes}
        if exts <= set(AUDIO_EXT):
            kind = "audio"
        elif exts <= set(MIDI_EXT):
            kind = "midi"
        else:
            raise ValueError("All takes must be audio (wav, mp3, m4a, flac, aac, ogg) or all "
                             "MIDI (mid, midi).")
        score = (files.get("score") or [None])[0]
        if score is not None and score.ext not in SCORE_EXT:
            raise ValueError("The score must be MusicXML (.musicxml, .xml, .mxl) or MEI.")
        pid = fields.get("piece_id", "").strip() or None
        piece = self.piece(pid) if pid else None
        if pid and piece is None:
            raise ValueError("Unknown piece; choose one from the list.")
        if piece is None and score is None:
            raise ValueError("Choose a supported piece or upload a MusicXML score.")
        prov = fields.get("provenance", "unknown")
        capture = None
        if kind == "audio":
            prov, capture = "transcribed", AUDIO_CAPTURE_MODEL
        elif prov in TRANSCRIBED_CHOICES:
            prov, capture = TRANSCRIBED_CHOICES[prov]
        elif prov not in PROVENANCES:
            prov = "unknown"
        title = fields.get("title", "").strip() or (
            f"{piece.composer}, {piece.title}" if piece else Path(score.filename).stem)
        excl = [s for s in re.split(r"[\s,]+", fields.get("exclude_references", "")) if s]
        spec = JobSpec(piece_id=piece.piece_id if piece else None, title=title[:200],
                       composer=piece.composer if piece else "", input_kind=kind,
                       provenance=prov, capture_model=capture,
                       filter_extras=prov == "transcribed" and fields.get("filter_extras") == "on",
                       ignore_wrong_piece=fields.get("ignore_wrong_piece") == "on",
                       exclude_references=excl,
                       max_windows=max(1, min(12, int(fields.get("max_windows") or 8))),
                       clips=fields.get("no_clips") != "on",
                       score_source="upload" if score is not None else "catalog")  # fmt: skip
        return self.store.create(spec, takes[:6], score)


def make_handler(app: App) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "PianoLens"
        sys_version = ""

        def log_message(self, fmt: str, *args: Any) -> None:  # quiet; no file names in logs
            pass

        # -------------------------------------------------------------- guards

        def _host_ok(self) -> bool:
            host = (self.headers.get("Host") or "").lower()
            port = self.server.server_address[1]
            return host in (f"127.0.0.1:{port}", f"localhost:{port}")

        def _origin_ok(self) -> bool:
            o = self.headers.get("Origin")
            if o is None:  # not a browser cross-site request (browsers send Origin on POST)
                return True
            port = self.server.server_address[1]
            return o in (f"http://127.0.0.1:{port}", f"http://localhost:{port}")

        # -------------------------------------------------------------- responses

        def _send(self, code: int, body: bytes, ctype: str, csp: str = CSP_APP,
                  extra: dict[str, str] | None = None) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Content-Security-Policy", csp)
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Cache-Control", "no-store")
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def _html(self, s: str, code: int = 200) -> None:
            self._send(code, s.encode(), "text/html; charset=utf-8")

        def _json(self, d: Any, code: int = 200) -> None:
            self._send(code, json.dumps(d).encode(), "application/json")

        def _file(self, f: Path, ctype: str, csp: str = CSP_APP) -> None:
            if not f.is_file():
                return self._error(404, "Not found.")
            self._send(200, f.read_bytes(), ctype, csp)

        def _error(self, code: int, msg: str) -> None:
            if self.path.startswith("/api/"):
                self._json({"error": msg}, code)
            else:
                self._html(pages.error_page(code, msg), code)

        # -------------------------------------------------------------- GET

        def do_HEAD(self) -> None:
            self.do_GET()

        def do_GET(self) -> None:
            if not self._host_ok():
                return self._send(403, b"Forbidden host", "text/plain")
            path = urlparse(self.path).path
            try:
                self._route_get(path)
            except KeyError:
                self._error(404, "Not found.")
            except Exception as e:  # noqa: BLE001 - a page error must not kill the server
                self._error(500, f"{type(e).__name__}: {e}")

        def _route_get(self, path: str) -> None:
            if path == "/":
                return self._html(pages.home_page())
            if path == "/history":
                return self._html(pages.history_page(app.store.list()))
            if path == "/api/pieces":
                return self._json([p.__dict__ for p in app.catalog])
            if path.startswith("/static/"):
                name = path.removeprefix("/static/")
                ctype = {"css": "text/css", "js": "text/javascript"}.get(name.rsplit(".")[-1])
                if not re.fullmatch(r"[a-z_]+\.(css|js)", name) or ctype is None:
                    raise KeyError(name)
                return self._file(STATIC / name, ctype + "; charset=utf-8")
            m = re.fullmatch(rf"/jobs/{_JOB}", path)
            if m:
                job = app.store.job(m["id"])
                if job is None:
                    raise KeyError(path)
                return self._html(pages.job_page(job))
            m = re.fullmatch(rf"/jobs/{_JOB}/report", path)
            if m:
                return self._file(app.store.path(m["id"]) / "report.html",
                                  "text/html; charset=utf-8", CSP_REPORT)
            m = re.fullmatch(rf"/jobs/{_JOB}/clips/(?P<f>[A-Za-z0-9_\-]+\.mp3)", path)
            if m:
                return self._file(app.store.path(m["id"]) / "compare" / "clips" / m["f"],
                                  "audio/mpeg")
            m = re.fullmatch(rf"/api/jobs/{_JOB}", path)
            if m:
                st = app.store.status(m["id"])
                job = app.store.job(m["id"])
                if st is None or job is None:
                    raise KeyError(path)
                out = {"job": job, "status": st}
                if st["state"] == "done":
                    out["results"] = results_data(app.store.path(m["id"]), m["id"])
                return self._json(out)
            raise KeyError(path)

        # -------------------------------------------------------------- POST

        def do_POST(self) -> None:
            if not self._host_ok():
                return self._send(403, b"Forbidden host", "text/plain")
            if not self._origin_ok():
                return self._json({"error": "cross-origin request refused"}, 403)
            path = urlparse(self.path).path
            try:
                n = int(self.headers.get("Content-Length") or 0)
                if n > MAX_UPLOAD:
                    return self._json({"error": "upload too large (1 GiB max)"}, 413)
                body = self.rfile.read(n) if n else b""
                if path == "/api/jobs":
                    fields, files = parse_multipart(self.headers.get("Content-Type", ""), body)
                    jid, reused = app.create_job(fields, files)
                    return self._json({"id": jid, "reused": reused, "url": f"/jobs/{jid}"})
                m = re.fullmatch(rf"/api/jobs/{_JOB}/(?P<act>cancel|delete|retry|override)",
                                 path)
                if m:
                    jid = m["id"]
                    if m["act"] == "cancel":
                        return self._json({"ok": app.store.cancel(jid)})
                    if m["act"] == "delete":
                        return self._json({"ok": app.store.delete(jid)})
                    return self._json({"ok": _retry(app.store, jid,
                                                    ignore_wrong_piece=m["act"] == "override")})
                raise KeyError(path)
            except KeyError:
                self._error(404, "Not found.")
            except ValueError as e:
                self._json({"error": str(e)}, 400)
            except Exception as e:  # noqa: BLE001
                self._json({"error": f"{type(e).__name__}: {e}"}, 500)

    return Handler


def _retry(store: JobStore, jid: str, ignore_wrong_piece: bool = False) -> bool:
    """Run a failed, cancelled, interrupted or stopped job again with the same stored inputs.
    ``ignore_wrong_piece``: the user confirmed the piece after the wrong-piece check stopped the
    run; it is recorded in ``job.json`` (it does not change the job id)."""
    st = store.status(jid)
    if st is None or st["state"] in ("running", "queued", "done"):
        return False
    d = store.path(jid)
    if ignore_wrong_piece:
        job = store.job(jid) or {}
        job.setdefault("spec", {})["ignore_wrong_piece"] = True
        _write_json(d / "job.json", job)
    for f in ("report.html", "report.json"):
        (d / f).unlink(missing_ok=True)
    fresh = [{"name": s["name"], "label": s["label"], "state": "pending"} for s in st["steps"]]
    _write_json(d / "status.json", {"state": "queued", "steps": fresh, "message": ""})
    store.start(jid)
    return True


def make_server(port: int = 8765, root: Path | str | None = None,
                catalog: list[Piece] | None = None) -> tuple[ThreadingHTTPServer, App]:
    """A server bound to 127.0.0.1 (``port`` 0 = any free port)."""
    app = App(root, catalog)
    srv = ThreadingHTTPServer(("127.0.0.1", port), make_handler(app))
    srv.daemon_threads = True
    app.port = srv.server_address[1]
    return srv, app


def serve(port: int = 8765, root: Path | str | None = None) -> None:
    srv, _ = make_server(port, root)
    try:
        srv.serve_forever()
    finally:
        srv.server_close()

