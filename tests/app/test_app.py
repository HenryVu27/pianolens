"""Tests for the local web app (P-02): upload parsing, job ids, bar-overlap matching, curve
windows, request guards, and an end-to-end smoke test (server, MIDI upload, worker, results)."""

from __future__ import annotations

import json
import shutil
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

import pytest

from pianolens.app.catalog import MIN_REFERENCES, Piece
from pianolens.app.jobs import JobSpec, JobStore, Upload
from pianolens.app.results import best_window, window_curves
from pianolens.app.server import make_server, parse_multipart

REPO = Path(__file__).resolve().parents[2]
ASAP_OP10_3 = REPO / "data" / "raw" / "asap" / "Chopin" / "Etudes_op_10" / "3"


def _multipart(fields: dict[str, str], files: list[tuple[str, str, bytes]]) -> tuple[str, bytes]:
    b = uuid.uuid4().hex
    body = b""
    for k, v in fields.items():
        body += f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
    for k, name, data in files:
        body += (f'--{b}\r\nContent-Disposition: form-data; name="{k}"; filename="{name}"\r\n'
                 "Content-Type: application/octet-stream\r\n\r\n").encode() + data + b"\r\n"
    body += f"--{b}--\r\n".encode()
    return f"multipart/form-data; boundary={b}", body


def test_parse_multipart_fields_and_binary_files():
    blob = bytes(range(256)) * 4 + b"\r\n--not-a-boundary\r\n"
    ctype, body = _multipart({"piece_id": "chopin_op10_no3", "title": "Étude"},
                             [("performance", "a.mid", blob), ("performance", "b.mid", b"x")])
    fields, files = parse_multipart(ctype, body)
    assert fields == {"piece_id": "chopin_op10_no3", "title": "Étude"}
    assert [u.filename for u in files["performance"]] == ["a.mid", "b.mid"]
    assert files["performance"][0].data == blob


def test_job_id_depends_on_bytes_piece_and_options_not_title():
    s1 = JobSpec(piece_id="p", title="A")
    ups = [Upload("x.mid", b"abc")]
    a = JobStore.job_id(s1, ups, None)
    assert a == JobStore.job_id(JobSpec(piece_id="p", title="B"), ups, None)
    assert a != JobStore.job_id(JobSpec(piece_id="q", title="A"), ups, None)
    assert a != JobStore.job_id(s1, [Upload("x.mid", b"abd")], None)
    assert a != JobStore.job_id(JobSpec(piece_id="p", title="A", max_windows=3), ups, None)
    assert len(a) == 16


def test_best_window_by_bar_overlap():
    wins = [{"id": "w01", "bars": [3, 4]}, {"id": "w02", "bars": [10, 11, 12]},
            {"id": "w03", "bars": [11, 12, 13]}]
    assert best_window([4], wins) == "w01"
    assert best_window([11, 12, 13], wins) == "w03"  # 3 shared bars beat 2
    assert best_window([11], wins) == "w02"  # tie: first
    assert best_window([20], wins) is None


def test_window_curves_pads_one_bar_and_marks_flagged():
    mi = [0, 1, 1, 2, 2, 3, 3, 4, 4, 5]
    rep = {"bars": [{"index": i, "label": str(i + 1)} for i in range(6)],
           "interpretation": {"curves": {"tempo": {
               "beat": list(range(10)), "measure_index": mi, "target": [1.0] * 10,
               "lo": [0.0] * 10, "mid": [0.5] * 10, "hi": [2.0] * 10, "unit": "bpm"}}}}
    c = window_curves(rep, [2, 3])["tempo"]
    assert c["beat"] == [1, 2, 3, 4, 5, 6, 7, 8]  # bars 1..4
    assert c["flagged"] == [False, False, True, True, True, True, False, False]
    assert c["bar"][0] == "2"  # labels, not indices
    assert window_curves(rep, []) == {}


@pytest.fixture()
def server(tmp_path):
    pieces = [Piece("toy_piece", "Nobody", "Toy", MIN_REFERENCES, 0, "asap", "x.musicxml")]
    srv, app = make_server(0, tmp_path, catalog=pieces)
    import threading

    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{app.port}", app
    srv.shutdown()
    srv.server_close()


def _req(url: str, data: bytes | None = None,
         headers: dict[str, str] | None = None) -> tuple[int, bytes]:
    r = urllib.request.Request(url, data=data, headers=headers or {},
                               method="POST" if data is not None else "GET")
    try:
        with urllib.request.urlopen(r, timeout=30) as f:
            return f.status, f.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def test_guards_and_validation(server):
    base, app = server
    code, body = _req(base + "/")
    assert code == 200 and b"New analysis" in body
    assert _req(base + "/api/pieces")[0] == 200
    assert json.loads(_req(base + "/api/pieces")[1])[0]["piece_id"] == "toy_piece"
    assert _req(base + "/", headers={"Host": "attacker.example"})[0] == 403  # DNS rebinding
    ctype, mp = _multipart({"piece_id": "toy_piece"}, [("performance", "a.mid", b"x")])
    code, _ = _req(base + "/api/jobs", mp, {"Content-Type": ctype,
                                            "Origin": "http://attacker.example"})
    assert code == 403  # cross-site POST
    ctype, mp = _multipart({"piece_id": "no_such_piece"}, [("performance", "a.mid", b"x")])
    code, body = _req(base + "/api/jobs", mp, {"Content-Type": ctype})
    assert code == 400 and b"Unknown piece" in body
    ctype, mp = _multipart({"piece_id": "toy_piece"}, [("performance", "a.txt", b"x")])
    assert _req(base + "/api/jobs", mp, {"Content-Type": ctype})[0] == 400
    assert _req(base + "/jobs/../../etc/passwd")[0] == 404
    assert _req(base + "/jobs/0123456789abcdef/clips/..%2Fjob.json")[0] == 404
    assert _req(base + "/history")[0] == 200
    assert not any(app.root.joinpath("jobs").iterdir())


def _have_smoke_data() -> bool:
    from pianolens.data import pianocore_cache

    return ((ASAP_OP10_3 / "SunMeiting08.mid").is_file() and pianocore_cache.cache_available()
            and shutil.which("fluidsynth") is not None and shutil.which("ffmpeg") is not None)


@pytest.mark.skipif(not _have_smoke_data(), reason="needs ASAP, the PianoCoRe cache, fluidsynth")
def test_smoke_upload_midi_poll_results(tmp_path):
    """Start the server, upload the ASAP performance of Chopin Op. 10/3, wait for the worker,
    fetch the results page, the report and one clip, then delete the job."""
    import threading

    srv, app = make_server(0, tmp_path)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{app.port}"
    try:
        data = (ASAP_OP10_3 / "SunMeiting08.mid").read_bytes()
        ctype, mp = _multipart({"piece_id": "chopin_op10_no3", "provenance": "disklavier",
                                "exclude_references": "ASAP_SunMeiting08", "max_windows": "1"},
                               [("performance", "SunMeiting08.mid", data)])
        code, body = _req(base + "/api/jobs", mp, {"Content-Type": ctype})
        assert code == 200, body
        jid = json.loads(body)["id"]
        t0 = time.time()
        while True:
            d = json.loads(_req(f"{base}/api/jobs/{jid}")[1])
            if d["status"]["state"] not in ("running", "queued"):
                break
            assert time.time() - t0 < 600, d["status"]
            time.sleep(1)
        assert d["status"]["state"] == "done", (d["status"],
                                                (app.store.path(jid) / "worker.log").read_text())
        assert [s["state"] for s in d["status"]["steps"]] == ["done"] * 3  # align, report, clips
        r = d["results"]
        assert r["facts"]["n_references"] >= MIN_REFERENCES
        assert len(r["windows"]) == 1 and r["windows"][0]["clips"]
        assert all(p["window"] in (None, r["windows"][0]["id"]) for p in r["practise"])
        assert _req(f"{base}/jobs/{jid}")[0] == 200
        code, rep = _req(f"{base}/jobs/{jid}/report")
        assert code == 200 and b"<html" in rep[:200]
        clip = next(iter(r["windows"][0]["clips"].values()))
        code, mp3 = _req(base + clip["url"])
        assert code == 200 and len(mp3) > 1000
        # same upload again: cached result, no new run
        code, body = _req(base + "/api/jobs", mp, {"Content-Type": ctype})
        assert json.loads(body) == {"id": jid, "reused": True, "url": f"/jobs/{jid}"}
        assert jid.encode() in _req(base + "/history")[1]
        assert json.loads(_req(f"{base}/api/jobs/{jid}/delete", b"")[1])["ok"]
        assert not app.store.path(jid).exists()
    finally:
        srv.shutdown()
        srv.server_close()


# --------------------------------------------------------------------------- DF-05


def test_job_id_includes_code_version_not_override():
    from pianolens.app.jobs import code_version

    ups = [Upload("x.mid", b"abc")]
    v = code_version()
    assert len(v) == 12 and v == code_version()
    a = JobStore.job_id(JobSpec(piece_id="p", title="A", code_version=v), ups, None)
    assert a != JobStore.job_id(JobSpec(piece_id="p", title="A", code_version="old"), ups, None)
    assert a == JobStore.job_id(JobSpec(piece_id="p", title="A", code_version=v,
                                        ignore_wrong_piece=True), ups, None)


def test_create_fills_code_version(tmp_path):
    from pianolens.app.jobs import code_version

    store = JobStore(tmp_path)
    jid, reused = store.create(JobSpec(piece_id="p", title="A"), [Upload("x.mid", b"abc")],
                               start=False)
    assert not reused
    assert store.job(jid)["spec"]["code_version"] == code_version()


def _app_no_worker(tmp_path):
    from pianolens.app.server import App

    app = App(tmp_path, [Piece("toy_piece", "Nobody", "Toy", MIN_REFERENCES, 0, "asap", "x")])
    app.store.start = lambda jid: None  # no worker process
    return app


def test_midi_can_be_marked_transcribed(tmp_path):
    app = _app_no_worker(tmp_path)
    jid, _ = app.create_job({"piece_id": "toy_piece", "provenance": "transcribed:transkun",
                             "filter_extras": "on"}, {"performance": [Upload("a.mid", b"1")]})
    spec = app.store.job(jid)["spec"]
    assert spec["provenance"] == "transcribed" and spec["capture_model"] == "Transkun V2"
    assert spec["filter_extras"] and spec["input_kind"] == "midi"
    jid, _ = app.create_job({"piece_id": "toy_piece", "provenance": "transcribed"},
                            {"performance": [Upload("a.mid", b"2")]})
    spec = app.store.job(jid)["spec"]
    assert spec["provenance"] == "transcribed" and spec["capture_model"] is None
    # key-captured MIDI: the extras filter does not apply
    jid, _ = app.create_job({"piece_id": "toy_piece", "provenance": "disklavier",
                             "filter_extras": "on"}, {"performance": [Upload("a.mid", b"3")]})
    spec = app.store.job(jid)["spec"]
    assert spec["provenance"] == "disklavier" and not spec["filter_extras"]
    jid, _ = app.create_job({"piece_id": "toy_piece"},
                            {"performance": [Upload("a.ogg", b"4"), Upload("b.aac", b"5")]})
    spec = app.store.job(jid)["spec"]
    assert spec["input_kind"] == "audio" and spec["capture_model"] == "Transkun V2"


def test_trust_notes_follow_transcription_not_file_type():
    from pianolens.app.results import trust_notes

    rep = {"confidence": {"velocity": "high"}}
    audio_like = trust_notes(rep, "audio")
    assert trust_notes(rep, "midi", transcribed=True) == audio_like
    assert trust_notes(rep, "midi") != audio_like


def test_same_score_references_gating():
    from pianolens.app.pipeline import same_score_references

    assert same_score_references("x", 5, "disklavier", [], []) == []  # PianoCoRe refs: no
    assert same_score_references("x", 0, "transcribed", [], []) == []  # transcribed: no
    assert same_score_references(None, 0, "disklavier", [], []) == []


def _asap_piece_perfs(piece_id: str) -> list[Path]:
    from pianolens.report.io import _asap_performances

    return _asap_performances(piece_id, [], 10_000)


@pytest.mark.skipif(not (REPO / "data" / "raw" / "asap").is_dir(),
                    reason="needs ASAP")
def test_same_score_references_from_asap():
    from pianolens.app.pipeline import same_score_references

    perfs = _asap_piece_perfs("chopin_op10_no12")
    if len(perfs) < 3:
        pytest.skip("ASAP index unavailable")
    got = same_score_references("chopin_op10_no12", 0, "disklavier", [], [], min_refs=1)
    assert got == perfs
    # the upload's own file (identical bytes) and excluded ids are left out
    got = same_score_references("chopin_op10_no12", 0, "unknown", [f"ASAP_{perfs[0].stem}"],
                                [perfs[1].read_bytes()], min_refs=1)
    assert perfs[0] not in got and perfs[1] not in got and len(got) == len(perfs) - 2
    assert same_score_references("chopin_op10_no12", 0, "disklavier", [], [],
                                 min_refs=len(perfs) + 1) == []


@pytest.mark.skipif(not (ASAP_OP10_3 / "SunMeiting08.mid").is_file(), reason="needs ASAP")
def test_wrong_piece_stops_run_and_override_is_recorded(tmp_path):
    """Op. 10/3 uploaded as Op. 10/4: the quick check stops the run before the report."""
    from pianolens.app import pipeline
    from pianolens.app.catalog import load_catalog
    from pianolens.app.server import _retry

    cat = [p for p in load_catalog(REPO / "data" / "interim" / "app")
           if p.piece_id == "chopin_op10_no4"]
    if not cat:
        pytest.skip("catalogue has no chopin_op10_no4")
    (tmp_path / "catalog.json").write_text(
        (REPO / "data" / "interim" / "app" / "catalog.json").read_text())
    store = JobStore(tmp_path)
    data = (ASAP_OP10_3 / "SunMeiting08.mid").read_bytes()
    spec = JobSpec(piece_id="chopin_op10_no4", title="t", provenance="disklavier",
                   clips=False, score_source="catalog")
    jid, _ = store.create(spec, [Upload("SunMeiting08.mid", data)], start=False)
    pipeline.run(store.path(jid))
    st = json.loads((store.path(jid) / "status.json").read_text())
    assert st["state"] == "stopped" and st["wrong_piece"]
    assert st["summary"]["align"]["match_ratio"] < pipeline.WRONG_PIECE_MATCH
    assert "probably another piece" in st["message"]
    assert [s["state"] for s in st["steps"]] == ["failed", "pending"]
    assert not (store.path(jid) / "report.json").exists()
    store.start = lambda j: None
    assert _retry(store, jid, ignore_wrong_piece=True)
    assert store.job(jid)["spec"]["ignore_wrong_piece"] is True
