"""Known-answer tests for partial recordings (BL-36, ``align(..., partial=True)``)."""

from __future__ import annotations

import numpy as np
import pytest

from pianolens.align import align, align_performance
from pianolens.align import partial as pa
from pianolens.align.core import _variants_with_paths
from tests.align.test_align import make_part, make_perf
from tests.features.test_control import P_DTYPE

N_BARS = 40
COPY_FROM, COPY_TO = 2, 20  # rows 20-23 repeat rows 2-5 note for note (a written-out repeat)


def _bars(seed: int = 3, n_bars: int = N_BARS) -> list[list[int]]:
    rng = np.random.default_rng(seed)
    bars = [list(rng.integers(55, 80, 4)) for _ in range(n_bars)]
    if n_bars >= COPY_TO + 4:
        for k in range(4):
            bars[COPY_TO + k] = list(bars[COPY_FROM + k])
    return bars


def _project_types(part, perf_na):
    """``Score`` (part kept) and ``Performance`` for ``align_performance``."""
    from pianolens.data import types

    sc = types.score_from_partitura(part, score_id="t", piece_id=types.PieceId("t"),
                                    keep_part=True)
    pn = np.zeros(len(perf_na), dtype=P_DTYPE)
    for f in ("onset_sec", "duration_sec", "pitch", "velocity", "id"):
        pn[f] = perf_na[f]
    pf = types.Performance("p", types.PieceId("t"), types.PerformerId("t:x"), "synthetic", pn,
                           np.zeros(0, types.PEDAL_DTYPE), "test")
    return sc, pf


def _events(bars: list[list[int]]) -> list[tuple[int, list[int]]]:
    return [(4 * b + i, [int(p)]) for b, bar in enumerate(bars) for i, p in enumerate(bar)]


def _deadpan(bars: list[list[int]], rows: range, quarter_sec: float = 0.5):
    pitches = [int(p) for r in rows for p in bars[r]]
    return make_perf(np.arange(len(pitches)) * quarter_sec + 1.0, pitches)


def _naive_subsequence(p, member) -> float:
    m, n = len(p), member.shape[0]
    c = np.array([[0.0 if member[j, p[i]] else 1.0 for j in range(n)] for i in range(m)])
    d = np.full((m, n), np.inf)
    d[0] = c[0]
    for i in range(1, m):
        for j in range(n):
            b = d[i - 1, j]
            if j > 0:
                b = min(b, d[i - 1, j - 1], d[i, j - 1])
            d[i, j] = c[i, j] + b
    return float(d[-1].min())


def test_subsequence_dtw_matches_the_naive_recursion_and_its_start():
    rng = np.random.default_rng(0)
    for _ in range(200):
        n, m = int(rng.integers(1, 12)), int(rng.integers(2, 12))
        member = np.zeros((n, 128), bool)
        for j in range(n):
            member[j, rng.integers(60, 66, size=rng.integers(1, 3))] = True
        p = rng.integers(60, 66, size=m)
        cost, j0, j1 = pa.subsequence_onset_dtw(p, member)
        assert cost == pytest.approx(_naive_subsequence(p, member))
        # the reported start and end bound an optimal path: same cost inside them
        assert j0 <= j1
        assert _naive_subsequence(p, member[j0:j1 + 1]) == pytest.approx(cost)


def test_subsequence_dtw_finds_an_exact_excerpt():
    member = np.zeros((10, 128), bool)
    for j, p in enumerate([60, 62, 64, 65, 67, 69, 71, 72, 74, 76]):
        member[j, p] = True
    cost, j0, j1 = pa.subsequence_onset_dtw(np.array([65, 67, 69, 71]), member)
    assert (cost, j0, j1) == (0.0, 3, 6)


def test_whole_recording_is_unchanged():
    bars = _bars()
    part = make_part(_events(bars))
    perf = _deadpan(bars, range(N_BARS))
    base = align(part, perf)
    res = align(part, perf, partial=True)
    assert res.recorded_span.whole
    assert res.alignment == base.alignment
    assert res.variant == base.variant
    assert np.array_equal(res.score_note_array, base.score_note_array)
    assert res.recorded_span_record()["not_recorded"] == []


def test_start_cut_onto_a_written_out_repeat_lands_on_the_right_occurrence():
    """Rows 20-23 repeat rows 2-5. A recording of rows 20-29 must be aligned to rows 20-29, not
    to the earlier copy; rows 0-19 and 30-39 are not recorded."""
    bars = _bars()
    part = make_part(_events(bars))
    rows = range(20, 30)
    perf = _deadpan(bars, rows)
    # today's anchored DTW puts the first recorded notes on the earlier copy (rows 2-5)
    base_rows = {int(s[1:].split("-")[0]) // 4 for s, _ in align(part, perf).match_pairs()}
    assert min(base_rows) < 20
    res = align(part, perf, partial=True)
    sp = res.recorded_span
    assert not sp.whole
    assert (sp.first_row, sp.last_row) == (20, 29)
    assert res.n_match == len(perf) and res.n_insertion == 0 and res.n_deletion == 0
    want = {f"n{4 * r + i}-1" for r in rows for i in range(4)}
    assert {s for s, _ in res.match_pairs()} == want
    rec = res.recorded_span_record()
    assert [(d["position"], d["bars_label"], d["n_bars"]) for d in rec["not_recorded"]] == [
        ("start", "bars 1-20", 20), ("end", "bars 31-40", 10)]
    assert rec["not_recorded"][0]["n_score_notes"] == 80


def test_short_edges_snap_to_the_piece():
    """Leaving out 4 notes at each end (under SNAP_NOTES) is a whole recording."""
    bars = _bars()
    part = make_part(_events(bars))
    perf = _deadpan(bars, range(1, N_BARS - 1))
    assert 4 <= pa.SNAP_NOTES
    assert align(part, perf, partial=True).recorded_span.whole


def test_repeat_sign_second_pass_keeps_its_labels():
    """A 16-bar section with a repeat sign; the recording starts at bar 9 of the first pass and
    plays the whole second pass. The path is AA and the second pass keeps its "(2)" labels."""
    bars = _bars(seed=5, n_bars=16)
    part = make_part(_events(bars), repeat=(0, 64))
    assert sorted(v for v, _, _ in _variants_with_paths(part)) == ["A", "AA"]
    rows = list(range(8, 16)) + list(range(16))
    perf = _deadpan(bars + bars, range(8, 32))
    assert len(perf) == 4 * len(rows)
    sc, pf = _project_types(part, perf)
    ap = align_performance(sc, pf, partial=True)
    meta = ap.score.meta
    assert meta["unfolded"] == "AA"
    assert meta["recorded_span"]["first_row"] == 8
    labels = meta["bar_labels"]
    assert labels[0] == "9" and labels[8] == "1 (2)" and labels[-1] == "16 (2)"
    from pianolens.report.build import bar_labels

    assert bar_labels(ap.score) == labels
    assert [d["bars_label"] for d in meta["recorded_span"]["not_recorded"]] == ["bars 1-8"]


def test_widen_rows_adds_bars_and_notes_up_to_the_edges():
    notes = [2, 2, 2, 0, 0, 8, 8, 8, 8, 8]
    # two rows give only 0 notes; keep going until 4 notes are added
    assert pa.widen_rows(notes, 5, 6, True, False, bars=2, notes=4) == (1, 6)
    assert pa.widen_rows(notes, 5, 6, True, True, bars=2, notes=4) == (1, 8)
    assert pa.widen_rows(notes, 2, 9, True, True, bars=2, notes=100) == (0, 9)
    assert pa.widen_rows(notes, 5, 6, False, False) == (5, 6)


def test_shrink_rows_drops_missed_edges_only_on_trimmed_sides():
    n = [4, 4, 0, 4, 4, 4]
    miss = [4, 3, 0, 1, 0, 4]
    assert pa.shrink_rows(n, miss, 0, 5, True, True) == (3, 4)
    assert pa.shrink_rows(n, miss, 0, 5, False, False) == (0, 5)
    assert pa.shrink_rows(n, miss, 0, 5, True, False) == (3, 5)
    assert pa.shrink_rows([4, 4], [4, 4], 0, 1, True, True) == (1, 1)  # never empty


def test_trim_part_keeps_coordinates_and_ids():
    bars = _bars()
    part = make_part(_events(bars))
    t = pa.trim_part(part, 5, 9)
    na = t.note_array()
    assert len(na) == 20 and len(t.measures) == 5
    assert na["onset_beat"].min() == 20 and na["onset_beat"].max() == 39
    assert set(na["id"]) == {f"n{k}" for k in range(20, 40)}
    assert len(part.note_array()) == 4 * N_BARS  # the original is untouched


def test_measure_labels_match_report_bar_labels():
    from pianolens.data.types import measures_from_partitura, score_from_partitura
    from pianolens.report.build import bar_labels

    part = make_part(_events(_bars(seed=5, n_bars=16)), repeat=(0, 64))
    up = [p for v, _, p in _variants_with_paths(part) if v == "AA"][0]
    import partitura as ptt

    upart = ptt.score.new_part_from_path(up, part, update_ids=True)
    ms = measures_from_partitura(upart)
    sc = score_from_partitura(upart, score_id="t", piece_id="t")
    assert pa.measure_labels(ms["number"], ms["name"]) == bar_labels(sc)


def test_report_grades_only_recorded_bars_and_lists_the_rest_once():
    from pianolens.report import ReportConfig, ReportInputs, build_report, render_html, to_jsonable

    bars = _bars()
    part = make_part(_events(bars))
    sc, pf = _project_types(part, _deadpan(bars, range(20, 30)))
    cfg = ReportConfig(shaping=False)
    rep = build_report(ReportInputs(ap=align_performance(sc, pf, partial=True),
                                    provenance="synthetic", four_hands=False), cfg)
    rs = rep["recorded_span"]
    assert not rs["whole"] and rs["n_bars_recorded"] == 10 and rs["n_bars_not_recorded"] == 30
    assert rs["bars_label"] == "bars 21-30"
    assert [b["label"] for b in rep["bars"]] == [str(r + 1) for r in range(20, 30)]
    assert rep["correctness"]["n_missed"] == 0
    assert all(b["correctness"]["tier"] == "none" for b in rep["bars"])
    notes = [n for n in rep["confidence"]["notes"] if n.startswith("Not recorded")]
    assert notes == ["Not recorded: bars 1-20 (before the recording starts) and bars 31-40 "
                     "(after it ends). The recording covers bars 21-30, and only those bars "
                     "are graded. The bars not recorded are not counted as mistakes and are "
                     "not in the practise list."]
    html = render_html(to_jsonable(rep))
    assert html.count("Not recorded: bars 1-20") == 1
    # without span detection the same recording grades all 40 bars and has no record
    off = build_report(ReportInputs(ap=align_performance(sc, pf), provenance="synthetic",
                                    four_hands=False), cfg)
    assert "recorded_span" not in off and len(off["bars"]) == N_BARS
    assert off["correctness"]["n_missed"] > 0
