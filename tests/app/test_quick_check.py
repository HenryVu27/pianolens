"""BL-40: the app's quick wrong-piece decision (``pianolens.app.quick_check.decide``)."""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest

from pianolens.app import quick_check as qc
from pianolens.app.quick_check import decide

RULE = {"partial_stop": 0.65, "min_notes": 50}


@pytest.mark.parametrize("span_whole", [True, False])
@pytest.mark.parametrize("n", [5, 5000])
def test_partial_off_is_todays_rule(span_whole, n):
    """Partial off: stop below 0.5 whatever the span flag and the length (DF-05)."""
    for mode in ("all", "high"):
        kw = {**RULE, "short_mode": mode}
        assert decide(0.49, partial=False, span_whole=span_whole, n_performed=n, **kw) == "stop"
        assert decide(0.50, partial=False, span_whole=span_whole, n_performed=n, **kw) == "pass"
        assert decide(0.60, partial=False, span_whole=span_whole, n_performed=n, **kw) == "pass"


def test_whole_span_keeps_todays_rule():
    """A whole span under partial=True has the partial=False alignment: same decision."""
    for mode in ("all", "high"):
        kw = {**RULE, "short_mode": mode}
        assert decide(0.55, partial=True, span_whole=True, n_performed=10, **kw) == "pass"
        assert decide(0.45, partial=True, span_whole=True, n_performed=10, **kw) == "stop"


def test_trimmed_span_uses_partial_stop():
    kw = {**RULE, "short_mode": "high"}
    assert decide(0.64, partial=True, span_whole=False, n_performed=500, **kw) == "stop"
    assert decide(0.65, partial=True, span_whole=False, n_performed=500, **kw) == "pass"
    assert decide(0.99, partial=True, span_whole=False, n_performed=50, **kw) == "pass"


def test_short_trimmed_take_confirms():
    """Below the minimum length: "high" confirms only at or above the stop, "all" always."""
    hi = {**RULE, "short_mode": "high"}
    al = {**RULE, "short_mode": "all"}
    assert decide(0.90, partial=True, span_whole=False, n_performed=49, **hi) == "confirm"
    assert decide(0.30, partial=True, span_whole=False, n_performed=49, **hi) == "stop"
    assert decide(0.90, partial=True, span_whole=False, n_performed=49, **al) == "confirm"
    assert decide(0.30, partial=True, span_whole=False, n_performed=49, **al) == "confirm"


def test_nan_ratio_counts_as_no_match():
    assert decide(math.nan, partial=False, span_whole=True, n_performed=100) == "stop"
    assert decide(math.nan, partial=True, span_whole=False, n_performed=10**6,
                  **RULE, short_mode="high") == "stop"


def test_bad_mode_raises():
    with pytest.raises(ValueError):
        decide(0.9, partial=True, span_whole=False, n_performed=10, short_mode="sometimes")


def test_defaults_are_the_module_constants(monkeypatch):
    monkeypatch.setattr(qc, "PARTIAL_STOP_MATCH", 0.7)
    monkeypatch.setattr(qc, "PARTIAL_MIN_NOTES", 40)
    monkeypatch.setattr(qc, "PARTIAL_SHORT_MODE", "all")
    assert decide(0.69, partial=True, span_whole=False, n_performed=100) == "stop"
    assert decide(0.70, partial=True, span_whole=False, n_performed=100) == "pass"
    assert decide(0.10, partial=True, span_whole=False, n_performed=39) == "confirm"


def test_pipeline_uses_the_same_stop():
    from pianolens.app import pipeline

    assert pipeline.WRONG_PIECE_MATCH == qc.WRONG_PIECE_MATCH == 0.5


# ----------------------------------------------------------------------------- app pipeline

REPO = Path(__file__).resolve().parents[2]
ASAP_OP10_3 = REPO / "data" / "raw" / "asap" / "Chopin" / "Etudes_op_10" / "3"


def _excerpt_midi(src, lo: int, hi: int) -> bytes:
    """Notes lo..hi (onset order) of a MIDI file as a new MIDI file's bytes."""
    import tempfile

    import partitura as pt

    na = pt.load_performance_midi(str(src)).note_array()
    na = na[np.argsort(na["onset_sec"], kind="stable")][lo:hi].copy()
    na["onset_sec"] -= na["onset_sec"].min()
    pp = pt.performance.PerformedPart.from_note_array(na)
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "x.mid"
        pt.save_performance_midi(pp, str(out))
        return out.read_bytes()


def _run_excerpt(tmp_path, monkeypatch, piece_id: str, **rule) -> dict:
    from pianolens.align import partial as pa
    from pianolens.app import pipeline
    from pianolens.app.catalog import load_catalog
    from pianolens.app.jobs import JobSpec, JobStore, Upload

    if not [p for p in load_catalog(REPO / "data" / "interim" / "app") if p.piece_id == piece_id]:
        pytest.skip(f"catalogue has no {piece_id}")
    (tmp_path / "catalog.json").write_text(
        (REPO / "data" / "interim" / "app" / "catalog.json").read_text())
    monkeypatch.setattr(pa, "PARTIAL_DEFAULT", True)  # the app reads it at run time
    for k, v in rule.items():
        monkeypatch.setattr(qc, k, v)
    store = JobStore(tmp_path)
    spec = JobSpec(piece_id=piece_id, title="t", provenance="disklavier", clips=False,
                   score_source="catalog")
    data = _excerpt_midi(ASAP_OP10_3 / "SunMeiting08.mid", 200, 260)
    jid, _ = store.create(spec, [Upload("x.mid", data)], start=False)
    pipeline.run(store.path(jid))
    return json.loads((store.path(jid) / "status.json").read_text())


@pytest.mark.skipif(not (ASAP_OP10_3 / "SunMeiting08.mid").is_file(), reason="needs ASAP")
def test_app_asks_to_confirm_a_short_trimmed_take(tmp_path, monkeypatch):
    """partial on, a 60-note excerpt of the right piece, minimum 1,000 notes: confirm."""
    st = _run_excerpt(tmp_path, monkeypatch, "chopin_op10_no3", PARTIAL_MIN_NOTES=1000,
                      PARTIAL_SHORT_MODE="all")
    a = st["summary"]["align"]
    assert a["span_whole"] is False and a["n_performed_notes"] == 60
    assert a["decision"] == "confirm" and st["state"] == "stopped"
    assert st["confirm_piece"] is True and st["wrong_piece"] is False
    assert "too short to check" in st["message"]
    assert [s["state"] for s in st["steps"]] == ["failed", "pending"]


@pytest.mark.skipif(not (ASAP_OP10_3 / "SunMeiting08.mid").is_file(), reason="needs ASAP")
def test_app_stops_a_trimmed_take_below_the_partial_stop(tmp_path, monkeypatch):
    """partial on, the excerpt on another piece, trimmed-span stop 0.99: stopped as wrong."""
    st = _run_excerpt(tmp_path, monkeypatch, "chopin_op10_no4", PARTIAL_STOP_MATCH=0.99,
                      PARTIAL_MIN_NOTES=0)
    a = st["summary"]["align"]
    assert a["span_whole"] is False and a["decision"] == "stop"
    assert st["state"] == "stopped" and st["wrong_piece"] is True
    assert "part of the chosen score" in st["message"]
