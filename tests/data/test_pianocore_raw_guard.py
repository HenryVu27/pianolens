"""BL-35: guard against raw PianoCoRe performance MIDI that holds more than its score."""

import logging
import zipfile

import pandas as pd
import pytest

from pianolens.data import pianocore as pc
from pianolens.data.pianocore import (
    RAW_NOTE_RATIO_MAX,
    RAW_PREFIX,
    RAW_SPAN_RATIO_MAX,
    RawLongerThanScore,
    data_available,
    guard_jobs,
    raw_guard,
    raw_guard_reason,
    read_raw_performance,
)


def _row(i, piece_id="chopin_op10_no1", xml="s/a.mxl", perf_notes=1000, score_notes=1000,
         raw_dur=100.0, refined_dur=100.0):  # fmt: skip
    return {"id": f"PianoCoRe_{i:06d}", "piece_id": piece_id, "score_xml_path": xml,
            "performance_midi_path": f"p/{i}.mid", "performance_note_count": perf_notes,
            "score_note_count": score_notes, "performance_duration": raw_dur,
            "refined_performance_duration": refined_dur}  # fmt: skip


def _table(*rows):
    return pd.DataFrame(rows, columns=["score_xml_path", "folded", "unfolded_max"])


# ----------------------------------------------------------------------------- the rule


def test_note_rule_boundary():
    assert raw_guard_reason(RAW_NOTE_RATIO_MAX * 1000, 1000) == ""
    assert "ratio" in raw_guard_reason(RAW_NOTE_RATIO_MAX * 1000 + 1, 1000)


def test_missing_score_count_never_flags():
    assert raw_guard_reason(5000, 0) == ""
    assert raw_guard_reason(5000, float("nan")) == ""


def test_span_rule_only_for_partial_scores():
    long = {"raw_duration": 800.0, "refined_duration": 300.0}
    assert raw_guard_reason(1000, 1000, **long) == ""
    assert "partial score" in raw_guard_reason(1000, 1000, partial_score=True, **long)
    ok = {"raw_duration": RAW_SPAN_RATIO_MAX * 300.0, "refined_duration": 300.0}
    assert raw_guard_reason(1000, 1000, partial_score=True, **ok) == ""
    # tier C rows have no refined file: the span rule cannot apply
    assert raw_guard_reason(1000, 1000, partial_score=True, raw_duration=800.0,
                            refined_duration=float("nan")) == ""  # fmt: skip


# ----------------------------------------------------------------------------- index level


def test_unfolded_count_protects_full_repeats():
    # score written with repeats: 600 notes folded, 1,100 when every repeat is played
    idx = pd.DataFrame([_row(1, perf_notes=1080, score_notes=600)])
    assert raw_guard(idx, _table(("s/a.mxl", 600, 1100))).iloc[0] == ""
    assert raw_guard(idx, _table(("s/a.mxl", 600, 600))).iloc[0] != ""


def test_falls_back_to_metadata_count():
    idx = pd.DataFrame([_row(1, xml="s/missing.mxl", perf_notes=1700, score_notes=1000),
                        _row(2, xml="s/failed.mxl", perf_notes=1600, score_notes=1000)])
    table = _table(("s/failed.mxl", -1, -1))
    assert list(raw_guard(idx, table) != "") == [True, False]


def test_partial_score_piece_gets_span_rule():
    idx = pd.DataFrame([
        _row(1, piece_id="chopin_op22", perf_notes=1220, raw_dur=810.0, refined_dur=556.0),
        _row(2, piece_id="chopin_op22", perf_notes=1000, raw_dur=560.0, refined_dur=556.0),
        _row(3, piece_id="chopin_op23", perf_notes=1220, raw_dur=810.0, refined_dur=556.0),
    ])  # fmt: skip
    r = raw_guard(idx, _table(("s/a.mxl", 1000, 1000)))
    assert list(r != "") == [True, False, False]


def test_guard_jobs_drops_after_draw_and_logs(caplog):
    idx = pd.DataFrame([_row(1), _row(2, perf_notes=3000), _row(3)])
    table = _table(("s/a.mxl", 1000, 1000))
    jobs = [{"id": "PianoCoRe_000003"}, {"id": "PianoCoRe_000002"}, {"id": "other"},
            {"id": "PianoCoRe_000001"}]  # fmt: skip
    orig = pc.score_note_table
    pc.score_note_table = lambda *a, **k: table
    try:
        with caplog.at_level(logging.WARNING, logger="pianolens.data.pianocore"):
            kept = guard_jobs(jobs, idx, label="t")
        tuples = guard_jobs([("k", "PianoCoRe_000002", "p", "t"), ("k", "PianoCoRe_000001",
                                                                   "p", "t")], idx, id_key=1)
    finally:
        pc.score_note_table = orig
    assert [j["id"] for j in kept] == ["PianoCoRe_000003", "other", "PianoCoRe_000001"]
    assert [t[1] for t in tuples] == ["PianoCoRe_000001"]
    assert "PianoCoRe_000002" in caplog.text and "1 of 4 jobs skipped" in caplog.text


def test_read_raw_performance(tmp_path):
    zp = tmp_path / "raw.zip"
    with zipfile.ZipFile(zp, "w") as z:
        z.writestr(RAW_PREFIX + "p/1.mid", b"one")
        z.writestr(RAW_PREFIX + "p/2.mid", b"two")
    idx = pd.DataFrame([_row(1), _row(2, perf_notes=3000)])
    orig = pc.score_note_table
    pc.score_note_table = lambda *a, **k: _table(("s/a.mxl", 1000, 1000))
    try:
        with zipfile.ZipFile(zp) as z:
            assert read_raw_performance(idx.iloc[0], z) == b"one"
            with pytest.raises(RawLongerThanScore, match="PianoCoRe_000002"):
                read_raw_performance(idx.iloc[1], z)
            assert read_raw_performance(idx.iloc[1], z, guard=False) == b"two"
    finally:
        pc.score_note_table = orig


# ----------------------------------------------------------------------------- real data

needs_table = pytest.mark.skipif(
    not (data_available() and pc.SCORE_NOTES_TABLE.is_file()),
    reason="data/raw/pianocore or data/processed/pianocore_score_notes.parquet missing",
)


@needs_table
def test_df14_files_are_caught():
    idx = pc.pianocore_index(tier="a")
    idx = idx[idx["piece_id"].isin(["bach_bwv971", "chopin_op22"])]
    r = raw_guard(idx)
    bwv = idx[(idx["piece_id"] == "bach_bwv971") & (r != "")]
    # DF-14: the 4 PERiScoPe files holding the whole Italian Concerto, and nothing else
    assert sorted(bwv["performance_id"].astype(str)) == sorted(
        ["PERiScoPe_48777871", "PERiScoPe_63671018", "PERiScoPe_95292898",
         "PERiScoPe_1686937457"])  # fmt: skip
    op22 = r[idx["piece_id"] == "chopin_op22"]
    assert 300 <= int((op22 != "").sum()) <= 360  # 330 measured on 2026-10-11 (BL-35)
