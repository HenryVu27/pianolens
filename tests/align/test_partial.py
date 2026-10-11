"""Known-answer tests for partial recordings (BL-36, ``align(..., partial=True)``)."""

from __future__ import annotations

import numpy as np
import pytest

from pianolens.align import align, align_performance
from pianolens.align import partial as pa
from pianolens.align.core import _variants_with_paths
from tests.align.test_align import SCALE, make_part, make_perf, melody
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
                     "not in the practise list. The first and last recorded bars may list "
                     "notes as missed if the recording starts or ends partway through them."]
    html = render_html(to_jsonable(rep))
    assert html.count("Not recorded: bars 1-20") == 1
    # without span detection the same recording grades all 40 bars and has no record
    off = build_report(ReportInputs(ap=align_performance(sc, pf), provenance="synthetic",
                                    four_hands=False), cfg)
    assert "recorded_span" not in off and len(off["bars"]) == N_BARS
    assert off["correctness"]["n_missed"] > 0


# ---------------------------------------------------------------- report.io.restrict_to_score
# A 16-bar section with a repeat sign (path AA) and a note tied from bar 8 beat 4 into bar 9
# beat 1. The target plays bars 9-16 of the first pass and the whole second pass, so its span is
# rows 8-31 of AA and the tie crosses the span's first edge.

def _tied_repeat_part(bars: list[list[int]]):
    import partitura as ptt

    from tests.align.test_align import _SPELL

    part = ptt.score.Part("P0", "piano", quarter_duration=4)
    part.add(ptt.score.TimeSignature(4, 4), 0)
    notes = {}
    for b, bar in enumerate(bars):
        for i, p in enumerate(bar):
            q = 4 * b + i
            step, alter = _SPELL[int(p) % 12]
            n = ptt.score.Note(step=step, octave=int(p) // 12 - 1, alter=alter, id=f"n{q}",
                               voice=1)
            part.add(n, start=4 * q, end=4 * (q + 1))
            notes[q] = n
    notes[31].tie_next, notes[32].tie_prev = notes[32], notes[31]  # bar 8 beat 4 -> bar 9 beat 1
    part.add(ptt.score.Repeat(), 0, 4 * 4 * len(bars))
    ptt.score.add_measures(part)
    return part


def _tied_repeat_case():
    bars = _bars(seed=11, n_bars=16)
    bars[8][0] = bars[7][3]  # the tie tail has the head's pitch
    part = _tied_repeat_part(bars)

    def played(seq_bars):  # the tied note is struck once, at its head
        out = []
        for b in seq_bars:
            out += [int(p) for i, p in enumerate(bars[b % 16]) if not (b % 16 == 8 and i == 0)]
        return out

    expert = played(range(32))
    # the target starts at bar 9, so it strikes the tied note there
    target = [int(p) for p in bars[8]] + played(range(9, 32))
    sc, ref = _project_types(part, make_perf(np.arange(len(expert)) * 0.5, expert))
    _, tgt = _project_types(part, make_perf(np.arange(len(target)) * 0.5 + 1.0, target))
    ap = align_performance(sc, tgt, partial=True)
    rap = align_performance(sc, ref)
    return ap, rap


def test_restrict_to_score_keeps_only_the_target_bars_on_a_repeat_path():
    from pianolens.features.correctness import correctness
    from pianolens.report.build import bar_error_table, bar_labels
    from pianolens.report.io import _same_path, restrict_to_score

    ap, rap = _tied_repeat_case()
    rs = ap.score.meta["recorded_span"]
    assert ap.score.meta["unfolded"] == "AA" and (rs["first_row"], rs["last_row"]) == (8, 31)
    labels = bar_labels(ap.score)
    assert labels[0] == "9" and labels[8] == "1 (2)" and labels[-1] == "16 (2)"
    assert "n32-1" in set(ap.score.notes["id"].astype(str))  # the target struck the tied note
    assert _same_path(rap, ap)
    r = restrict_to_score(rap, ap.score)
    assert r.score is ap.score
    keep = set(ap.score.notes["id"].astype(str))
    pairs = [tuple(x) for x in r.alignment.pairs.tolist()]
    assert all(sid in keep for _, sid, _ in pairs if sid)
    # BL-37: the performed notes matched outside the span leave the restricted performance
    # (32 in bars 1-8 of the first pass), except the tie head, which now plays the tie tail
    outside = {p for lab, s, p in rap.alignment.pairs.tolist() if lab == "match" and s not in keep}
    assert len(outside) == 32
    head_pid = dict((s, p) for lab, s, p in rap.alignment.pairs.tolist())["n31-1"]
    assert ("match", "n32-1", head_pid) in pairs
    kept_ids = set(r.performance.notes["id"].astype(str))
    assert kept_ids == set(rap.performance.notes["id"].astype(str)) - (outside - {head_pid})
    # the restricted perfect expert is exact in every span bar
    t = bar_error_table(correctness(r), labels)
    assert t["n_missed"].sum() == 0 and t["n_extra"].sum() == 0
    assert t["n_wrong_pitch"].sum() == 0


def test_restrict_to_score_drops_unmatched_notes_outside_the_span():
    from pianolens.report.io import restrict_to_score

    ap, rap = _tied_repeat_case()
    # an extra note in the expert, early in the first pass (outside the span)
    pairs = [tuple(x) for x in rap.alignment.pairs.tolist()]
    import dataclasses

    from pianolens.data import types

    extra = np.zeros(1, dtype=rap.performance.notes.dtype)
    extra["onset_sec"], extra["duration_sec"], extra["pitch"] = 1.25, 0.2, 100
    extra["velocity"], extra["id"] = 64, "pX"
    perf = dataclasses.replace(rap.performance,
                               notes=np.concatenate([rap.performance.notes, extra]))
    al = types.Alignment(np.array(pairs + [("insertion", "", "pX")], dtype=types.ALIGNMENT_DTYPE),
                         "t", "p", False, "test")
    r = restrict_to_score(types.AlignedPerformance(perf, rap.score, al), ap.score)
    assert "pX" not in set(r.performance.notes["id"].astype(str))
    assert all(p != "pX" for _, _, p in r.alignment.pairs.tolist())


def test_restrict_to_score_first_span_bar_is_exact_for_a_perfect_expert():
    """BL-37 (was a strict xfail after the BL-36 audit): the tie tail is matched to the expert's
    tie head and the notes matched before the span no longer land as extras."""
    from pianolens.features.correctness import correctness
    from pianolens.report.build import bar_error_table, bar_labels
    from pianolens.report.io import restrict_to_score

    ap, rap = _tied_repeat_case()
    t = bar_error_table(correctness(restrict_to_score(rap, ap.score)), bar_labels(ap.score))
    first = t[t["label"] == "9"].iloc[0]
    assert first["n_missed"] == 0 and first["n_extra"] == 0


def test_partial_alignment_first_bar_is_exact_when_a_tie_crosses_the_edge():
    """BL-37 (was a strict xfail): after the shrink the final rows are realigned, so the target's
    struck tie tail is matched instead of becoming an extra plus a missed note."""
    from pianolens.features.correctness import correctness

    ap, _ = _tied_repeat_case()
    s = correctness(ap).summary
    assert s["n_missed"] == 0 and s["n_extra"] == 0


def test_unstruck_tie_tail_at_the_span_start_is_dropped():
    """BL-37: a recording that starts after a tied note's head (the tail is not struck again)
    does not get the tail as a missed note; the score drops it, as the uncut score counts it in
    the bar before."""
    from pianolens.features.correctness import correctness

    bars = _bars(seed=11, n_bars=16)
    bars[8][0] = bars[7][3]
    part = _tied_repeat_part(bars)
    played = []
    for b in range(9, 32):  # from bar 9 of the first pass, tie tail not struck
        played += [int(p) for i, p in enumerate(bars[b % 16]) if not (b % 16 == 8 and i == 0)]
    sc, tgt = _project_types(part, make_perf(np.arange(len(played)) * 0.5 + 1.0, played))
    ap = align_performance(sc, tgt, partial=True)
    assert "n32-1" not in set(ap.score.notes["id"].astype(str))
    s = correctness(ap).summary
    assert s["n_missed"] == 0 and s["n_extra"] == 0


def test_edge_low_confidence_policy_only_touches_edge_bars_of_a_trimmed_span():
    """BL-37 policy (off by default): missed notes in the first / last k graded bars of a
    trimmed side are low confidence; whole recordings and the default config are unchanged."""
    from pianolens.report import ReportConfig, ReportInputs, build_report
    from pianolens.report.build import edge_bars

    bars = _bars()
    part = make_part(_events(bars))
    # recording of bars 21-30 that misses 3 of the 4 notes of bar 21 and of bar 25
    rows = list(range(20, 30))
    pitches = [int(p) for r in rows for i, p in enumerate(bars[r])
               if not (r in (20, 24) and i > 0)]
    sc, pf = _project_types(part, make_perf(np.arange(len(pitches)) * 0.5 + 1.0, pitches))
    ap = align_performance(sc, pf, partial=True)
    n = ap.score.measures
    assert edge_bars(ap.score, [4] * len(n), 2) == [0, 1, len(n) - 2, len(n) - 1]
    assert edge_bars(ap.score, [4] * len(n), 0) == []
    base = ReportConfig(shaping=False)
    off = build_report(ReportInputs(ap=ap, provenance="synthetic", four_hands=False), base)
    on = build_report(ReportInputs(ap=ap, provenance="synthetic", four_hands=False),
                      ReportConfig(shaping=False, edge_low_confidence_bars=2))
    lab = {b["label"]: b for b in on["bars"]}
    loff = {b["label"]: b for b in off["bars"]}
    first = on["bars"][0]["label"]
    if lab[first]["correctness"]["n_missed"]:
        assert lab[first]["correctness"]["n_missed_low_confidence"] == \
            lab[first]["correctness"]["n_missed"]
    assert "edge_low_confidence" not in off["correctness"]
    assert on["correctness"]["edge_low_confidence"]["n_bars"] == 2
    # an interior bar with missed notes keeps its count and tier
    assert lab["25"]["correctness"]["n_missed_low_confidence"] == 0
    assert lab["25"]["correctness"]["tier"] == loff["25"]["correctness"]["tier"]
    # a whole recording: no edge bars, report identical with the policy on
    sc2, pf2 = _project_types(part, _deadpan(bars, range(N_BARS)))
    ap2 = align_performance(sc2, pf2, partial=True)
    assert edge_bars(ap2.score, [4] * N_BARS, 2) == []
    a = build_report(ReportInputs(ap=ap2, provenance="synthetic", four_hands=False), base)
    b = build_report(ReportInputs(ap=ap2, provenance="synthetic", four_hands=False),
                     ReportConfig(shaping=False, edge_low_confidence_bars=2))
    b["correctness"].pop("edge_low_confidence")
    a.pop("generated"), b.pop("generated")
    import json

    assert json.dumps(a, sort_keys=True, default=str) == json.dumps(b, sort_keys=True, default=str)


def test_ornament_step_crash_without_unmatched_notes_falls_back():
    """parangonar 3.3.3's ornament step crashes (numpy DTypePromotionError) when every performed
    note is matched and the score has a matched ornamented note (found in BL-37 on short
    excerpts); ``align_note_arrays`` then aligns without the ornament step."""
    part = make_part(melody(SCALE))
    for n in part.notes_tied:
        if n.id == "n3":
            n.ornaments = {"trill": True}
    perf = make_perf(np.arange(len(SCALE)) * 0.5, SCALE)
    res = align(part, perf)
    assert res.n_match == len(SCALE) and res.n_insertion == 0


def test_margin_needed_only_when_it_explains_otherwise_unmatched_notes():
    # the widened alignment matched p1..p4 in margin rows; the DTW-span alignment left p1..p3
    # unmatched -> the margin explains 3 notes nothing else does
    assert pa.margin_needed({"p1", "p2", "p3", "p4"}, {"p1", "p2", "p3", "x"}, 3, 0.5)
    # the margin only took notes the DTW-span alignment matched elsewhere (a pulled edge)
    assert not pa.margin_needed({"p1", "p2", "p3", "p4"}, {"x"}, 3, 0.5)
    assert not pa.margin_needed({"p1", "p2"}, {"p1", "p2"}, 3, 0.5)  # too few
    assert not pa.margin_needed(set(), {"p1"}, 3, 0.5)


def test_played_opening_left_out_by_the_dtw_is_recovered_by_the_margin():
    """Rows 0-3 hold one note each (a sparse opening), then dense bars. A recording of the whole
    piece is whole; a recording from row 20 leaves the opening out."""
    rng = np.random.default_rng(4)
    bars = [[int(rng.integers(55, 80))] for _ in range(4)]
    bars += [list(rng.integers(55, 80, 4)) for _ in range(36)]
    events = []
    for b, bar in enumerate(bars):
        for i, p in enumerate(bar):
            events.append((4 * b + i, [int(p)]))
    part = make_part(events)
    full = [int(p) for bar in bars for p in bar]
    res = align(part, make_perf(np.arange(len(full)) * 0.5 + 1.0, full), partial=True)
    assert res.recorded_span.whole
    late = [int(p) for bar in bars[20:] for p in bar]
    res2 = align(part, make_perf(np.arange(len(late)) * 0.5 + 1.0, late), partial=True)
    assert res2.recorded_span.first_row == 20 and res2.n_match == len(late)


def test_edge_outside_notes_marks_only_notes_before_the_first_played_one():
    """BL-39 narrow rule. Bar 21 holds 8 eighth notes; the recording starts on its third note,
    omits its sixth, and plays bars 22-30. In bar 21, notes 1-2 are outside (due before the
    first matched note), while the omitted sixth note is inside, so it still counts."""
    from pianolens.features.correctness import correctness
    from pianolens.report.build import edge_outside_notes

    bars = _bars()
    rng = np.random.default_rng(9)
    dense = [int(p) for p in rng.integers(55, 80, 8)]
    events = []
    for b, bar in enumerate(bars):
        if b == 20:
            events += [(80 + 0.5 * i, [p]) for i, p in enumerate(dense)]
        else:
            events += [(4 * b + i, [int(p)]) for i, p in enumerate(bar)]
    part = make_part(events)
    played = [p for i, p in enumerate(dense) if i >= 2 and i != 5]
    played += [int(p) for r in range(21, 30) for p in bars[r]]
    sc, pf = _project_types(part, make_perf(np.arange(len(played)) * 0.4 + 1.0, played))
    ap = align_performance(sc, pf, partial=True)
    assert ap.score.meta["recorded_span"]["first_row"] == 20
    cr = correctness(ap)
    sn = cr.score_notes
    for basis in ("score", "score_le", "time"):
        out = edge_outside_notes(ap.score, cr, 1, basis, 0.05)
        got = set(sn.loc[out, "score_id"].astype(str))
        assert {"n80-1", "n81-1"} <= got, basis  # bar 21's first two notes
        assert "n85-1" not in got, basis  # the omitted sixth note stays a mistake
        assert not (set(sn.loc[out, "measure_index"]) - {0, len(ap.score.measures) - 1})
    # the report path: only the 2 outside notes are low confidence in bar 21
    from pianolens.report import ReportConfig, ReportInputs, build_report

    rep = build_report(ReportInputs(ap=ap, provenance="synthetic", four_hands=False),
                       ReportConfig(shaping=False, edge_low_confidence_bars=1,
                                    edge_low_confidence_rule="outside"))
    c21 = rep["bars"][0]["correctness"]
    assert c21["n_missed"] == 3 and c21["n_missed_low_confidence"] == 2
    off = build_report(ReportInputs(ap=ap, provenance="synthetic", four_hands=False),
                       ReportConfig(shaping=False))
    assert off["bars"][0]["correctness"]["n_missed_low_confidence"] == 0
    # whole recording: nothing is outside
    sc2, pf2 = _project_types(part, make_perf(np.arange(len(events)) * 0.4 + 1.0,
                                              [e[1][0] for e in events]))
    ap2 = align_performance(sc2, pf2, partial=True)
    assert ap2.score.meta["recorded_span"]["whole"]
    assert not edge_outside_notes(ap2.score, correctness(ap2), 1).any()


def test_edge_rule_config_is_validated_and_defaults_to_the_registered_basis():
    from pianolens.report import ReportConfig

    assert ReportConfig().edge_outside_basis == "score_le"  # BL-39 registered basis
    assert ReportConfig().edge_low_confidence_rule == "bar"
    with pytest.raises(ValueError):
        ReportConfig(edge_low_confidence_rule="outsde")
    with pytest.raises(ValueError):
        ReportConfig(edge_outside_basis="onset")


def _late_start_case():
    """A recording that starts on the third note of an 8-note bar 21 (see the narrow-rule test)."""
    bars = _bars()
    rng = np.random.default_rng(9)
    dense = [int(p) for p in rng.integers(55, 80, 8)]
    events = []
    for b, bar in enumerate(bars):
        if b == 20:
            events += [(80 + 0.5 * i, [p]) for i, p in enumerate(dense)]
        else:
            events += [(4 * b + i, [int(p)]) for i, p in enumerate(bar)]
    part = make_part(events)
    played = [p for i, p in enumerate(dense) if i >= 2]
    played += [int(p) for r in range(21, 30) for p in bars[r]]
    sc, pf = _project_types(part, make_perf(np.arange(len(played)) * 0.4 + 1.0, played))
    return part, events, align_performance(sc, pf, partial=True)


def test_summary_and_text_name_the_edge_rule():
    from pianolens.report import ReportConfig, ReportInputs, build_report

    _, _, ap = _late_start_case()
    inp = ReportInputs(ap=ap, provenance="synthetic", four_hands=False)
    out = build_report(inp, ReportConfig(shaping=False, edge_low_confidence_bars=1,
                                         edge_low_confidence_rule="outside"))
    ec = out["correctness"]["edge_low_confidence"]
    assert ec["rule"] == "outside" and ec["basis"] == "score_le" and ec["tol_sec"] == 0.0
    note = [n for n in out["confidence"]["notes"] if n.startswith("Not recorded")][0]
    assert "due before the first played note" in note and "still count" in note
    bar = build_report(inp, ReportConfig(shaping=False, edge_low_confidence_bars=1))
    assert bar["correctness"]["edge_low_confidence"]["rule"] == "bar"
    assert "basis" not in bar["correctness"]["edge_low_confidence"]
    note = [n for n in bar["confidence"]["notes"] if n.startswith("Not recorded")][0]
    assert "often loses them" in note


def test_no_edge_policy_adds_a_plain_caveat_only_for_a_trimmed_span():
    """BL-39 audit: partial=True at k = 0 says the edge bar may list notes as missed; no tier
    changes, and nothing is added for a whole recording."""
    from pianolens.report import ReportConfig, ReportInputs, build_report

    part, events, ap = _late_start_case()
    cfg = ReportConfig(shaping=False)
    rep = build_report(ReportInputs(ap=ap, provenance="synthetic", four_hands=False), cfg)
    assert "edge_low_confidence" not in rep["correctness"]
    note = [n for n in rep["confidence"]["notes"] if n.startswith("Not recorded")][0]
    assert note.endswith("The first and last recorded bars may list notes as missed if the "
                         "recording starts or ends partway through them.")
    assert rep["bars"][0]["correctness"]["n_missed_low_confidence"] == 0
    sc2, pf2 = _project_types(part, make_perf(np.arange(len(events)) * 0.4 + 1.0,
                                              [e[1][0] for e in events]))
    whole = build_report(ReportInputs(ap=align_performance(sc2, pf2, partial=True),
                                      provenance="synthetic", four_hands=False), cfg)
    assert not any("may list notes as missed" in n for n in whole["confidence"]["notes"])


def test_edge_caveat_text_names_the_side():
    from pianolens.report.text import edge_caveat_text

    assert edge_caveat_text({"not_recorded": [{"position": "start"}]}).startswith(
        "The first recorded bar")
    assert edge_caveat_text({"not_recorded": [{"position": "end"}]}).startswith(
        "The last recorded bar")
