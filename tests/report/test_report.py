"""Known-answer tests for the practice report (F-08): JSON content and a self-contained HTML."""

from __future__ import annotations

import json
import re

import numpy as np
import pytest

from pianolens.data import types
from pianolens.features.interpretation import InterpretationConfig
from pianolens.report import (
    SCHEMA,
    ReportConfig,
    ReportInputs,
    build_report,
    render_html,
    to_jsonable,
)
from pianolens.report.build import _correctness_tier, timing_noise_bars
from tests.features.test_control import build, scale_texture

N_BARS = 16
NOTES = scale_texture(N_BARS)  # RH eighth scale over LH quarters, 4/4, 16 bars
BEATS = np.array([b for b, *_ in NOTES])
CFG = ReportConfig(interpretation=InterpretationConfig(n_surrogates=20, min_references=10),
                   shaping=False)
WRONG_BAR = 5  # measure index with three wrong notes -> "strong"
JITTER_BAR = 10  # measure index with 40 ms timing noise


def _tempo_fn(depth: float):
    """Time map with a slowing of ``depth`` (log tempo) into bar 8 and at the end."""
    fine = np.linspace(0, 64, 6401)
    lt = -depth * (np.exp(-0.5 * ((fine - 30) / 3) ** 2) + np.exp(-0.5 * ((fine - 62) / 3) ** 2))
    tmap = np.concatenate([[0], np.cumsum(0.5 * np.exp(-lt[:-1]) * np.diff(fine))])
    return lambda b: float(np.interp(b, fine, tmap))


def _vel(scale: float, rng) -> np.ndarray:
    return 60 + 12 * np.sin(np.pi * BEATS / 64) * scale + rng.normal(0, 2, len(BEATS))


def _refs(n: int = 30):
    rng = np.random.default_rng(1)
    depths = np.quantile(rng.normal(0.25, 0.08, 4000), np.linspace(0.03, 0.97, n))
    out = []
    for i, d in enumerate(depths):
        off = rng.normal(0, 0.005, len(NOTES))  # 5 ms timing noise
        ap = build(NOTES, _tempo_fn(d), vel=_vel(rng.normal(1, 0.2), rng), offsets=off,
                   pid=f"ref{i}")
        ap.performance.provenance = "disklavier"
        out.append(ap)
    return out


def _with_wrong_notes(ap, bar: int, k: int):
    """Turn ``k`` matched RH notes of measure ``bar`` into wrong pitches (+1 semitone)."""
    idx = [i for i, (b, _, _, st, _) in enumerate(NOTES) if st == 1 and 4 * bar <= b < 4 * bar + 4]
    pairs = [tuple(p) for p in ap.alignment.pairs.tolist()]
    for i in idx[:k]:
        ap.performance.notes["pitch"][i] += 1
        pairs.remove(("match", f"n{i}", f"p{i}"))
        pairs += [("deletion", f"n{i}", ""), ("insertion", "", f"p{i}")]
    ap.alignment = types.Alignment(np.array(pairs, dtype=types.ALIGNMENT_DTYPE),
                                   ap.alignment.score_id, ap.alignment.performance_id, False,
                                   "test")
    return ap


def _target(prov: str = "disklavier"):
    rng = np.random.default_rng(7)
    off = rng.normal(0, 0.005, len(NOTES))
    in_bar = (BEATS >= 4 * JITTER_BAR) & (BEATS < 4 * JITTER_BAR + 4)
    off[in_bar] = rng.normal(0, 0.04, in_bar.sum())
    ap = build(NOTES, _tempo_fn(0.25), vel=_vel(1.0, rng), offsets=off, pid="target")
    ap.performance.provenance = prov
    return _with_wrong_notes(ap, WRONG_BAR, 3)


@pytest.fixture(scope="module")
def refs():
    return _refs()


@pytest.fixture(scope="module")
def report(refs):
    inp = ReportInputs(ap=_target(), piece_id="synth", title="Synthetic scale study",
                       provenance="disklavier", same_score_refs=refs,
                       same_score_provenance="disklavier")
    return to_jsonable(build_report(inp, CFG))


def test_json_schema_and_numbers(report):
    s = json.dumps(report, allow_nan=False)  # strict JSON: no NaN / inf
    assert json.loads(s)["schema"] == SCHEMA
    for key in ("piece", "input", "references", "confidence", "correctness", "interpretation",
                "timing", "control", "bars", "issues", "practise", "summary", "errors"):
        assert key in report
    assert len(report["bars"]) == N_BARS
    assert [c["title"] for c in report["summary"]] == ["Correctness", "Control", "Shaping",
                                                       "Interpretation"]
    # no overall grade anywhere
    assert not re.search(r'"(grade|overall_score|total_score)"', s)
    b = report["bars"][WRONG_BAR]["correctness"]
    assert b["n_wrong_pitch"] == 3 and b["tier"] == "strong"
    assert sum(x["correctness"]["n_errors"] for x in report["bars"]) == 3
    assert report["correctness"]["n_wrong_pitch"] == 3
    assert report["references"]["same_score"] == 30
    assert report["confidence"]["velocity"] == "high"
    for bar in report["bars"]:
        for ch in ("tempo", "velocity", "timing", "pedal", "evenness"):
            assert bar[ch]["tier"] in ("none", "notable", "strong")


def test_localized_issues_are_found(report):
    # both injected problems are in "what to practise": the wrong notes and the noisy bar
    prac = {(d["category"], d["channel"], tuple(d["bars"])): d for d in report["practise"]}
    wrong = prac[("correctness", "notes", (WRONG_BAR,))]
    assert "3 wrong notes" in wrong["text"] and wrong["bars_label"] == f"bar {WRONG_BAR + 1}"
    # the jittered bar shows up as unsteady timing and / or uneven running notes
    assert any(k[0] == "control" and k[2] == (JITTER_BAR,) for k in prac)
    # 40 ms jitter in one bar vs 5 ms elsewhere: timing steadiness flags that bar
    assert report["bars"][JITTER_BAR]["timing"]["tier"] != "none"
    flagged = [i for i, b in enumerate(report["bars"]) if b["timing"]["tier"] != "none"]
    assert len(flagged) <= 3
    assert report["timing"]["n_references"] == 30
    # an expert-like shape: at most a stray tempo-shape flag, never too flat
    assert sum(b["tempo"]["tier"] != "none" for b in report["bars"]) <= 2
    assert all(b["too_flat"]["tempo"] == "none" for b in report["bars"])
    # the practise list is ranked by tier, then magnitude
    ranks = [{"strong": 2, "notable": 1}[d["tier"]] for d in report["practise"]]
    assert ranks == sorted(ranks, reverse=True) and len(report["practise"]) <= 3


def test_deadpan_is_too_flat(refs):
    ap = build(NOTES, lambda b: 0.5 * b, pid="deadpan")  # constant tempo and velocity
    rep = to_jsonable(build_report(ReportInputs(ap=ap, provenance="synthetic",
                                                same_score_refs=refs,
                                                same_score_provenance="disklavier"), CFG))
    wins = rep["interpretation"]["windows"]
    assert all(w["flat_tier"] == "strong" for w in wins if w["block"] == "tempo")
    assert rep["practise"][0]["category"] == "too_flat"
    assert "too flat" in rep["practise"][0]["text"]
    # the flat section explains its per-bar shape deviations: none of them is practised
    assert not any(d["category"] == "interpretation" for d in rep["practise"])


def test_transcribed_velocity_is_low_confidence(refs):
    inp = ReportInputs(ap=_target("transcribed"), provenance="transcribed", same_score_refs=refs,
                       same_score_provenance="disklavier")
    rep = to_jsonable(build_report(inp, CFG))
    assert rep["confidence"]["velocity"] == "low"
    assert any("low confidence" in n for n in rep["confidence"]["notes"])
    assert any("doubles the apparent note-error rate" in n for n in rep["confidence"]["notes"])
    assert not any(d["channel"] == "velocity" for d in rep["practise"])


def test_no_references_still_reports():
    rep = to_jsonable(build_report(ReportInputs(ap=_target()), CFG))
    assert rep["interpretation"] == {} and rep["references"]["tier_d_total"] == 0
    assert any("No expert reference" in n for n in rep["confidence"]["notes"])
    assert rep["practise"][0]["category"] == "correctness"
    html = render_html(rep)
    assert "No expert band" in html


def test_html_is_self_contained(report, tmp_path):
    html = render_html(report, tmp_path)
    assert html.startswith("<!doctype html>")
    assert not re.search(r"https?://", html)
    assert "<script" not in html and "<link" not in html and "@import" not in html
    assert not re.search(r'src\s*=', html)
    assert "prefers-color-scheme:dark" in html
    assert html.count("<svg") >= 4  # timeline, tempo, loudness, evenness
    heads = ["<h1>", "Confidence notes", "<h2>Summary", "<h2>Bar by bar", "<h2>Tempo against",
             "<h2>Loudness against", "<h2>Evenness per run", "<h2>What to practise",
             "<h2>Methods and limitations"]
    pos = [html.index(h) for h in heads]
    assert pos == sorted(pos)
    # links to the specs are relative files, not URLs
    assert "correctness-validation.md" in html


@pytest.mark.parametrize("wrong, missed_extra, n, tier", [
    (0, 0, 10, "none"), (1, 0, 10, "none"), (2, 0, 10, "notable"), (3, 0, 10, "strong"),
    (0, 2, 10, "none"), (0, 3, 10, "notable"), (0, 7, 10, "strong"),
])  # fmt: skip
def test_correctness_tiers_follow_expert_calibration(wrong, missed_extra, n, tier):
    """Expert bars: >= 1 wrong note in 7%, >= 2 in 2.1%, >= 3 in 0.85%; missed + extra per note
    95th percentile 0.267, 99th 0.634 (scripts/calibrate_report_f08.py)."""
    assert _correctness_tier(wrong, missed_extra, n)[0] == tier


def test_timing_noise_bars_known_answer():
    """References share a fine-timing pattern; the target follows it except in bar 1, where it
    adds 0.1 beat of noise. Its noise is ~0 elsewhere and flagged only in bar 1."""
    rng = np.random.default_rng(0)
    pattern = np.tile([0.0, 0.05, -0.03, 0.02], 8)  # 32 positions, 8 bars of 4
    X = pattern + rng.normal(0, 0.01, (50, 32))
    bar = np.repeat(np.arange(8), 4)
    t = pattern.copy()
    t[4:8] += np.array([0.1, -0.1, 0.1, -0.1])
    df, s = timing_noise_bars(t, X, bar, 8)
    assert df.loc[1, "noise_rms_beats"] == pytest.approx(0.1, abs=0.01)
    assert (df.drop(index=1)["noise_rms_beats"] < 0.01).all()
    assert (df["noise_rms_beats"] > df["ref_q99"]).tolist() == [i == 1 for i in range(8)]
    # the shared pattern explains part of the residual even with bar 1's added noise
    assert 0 < s["consensus_r2"] < 1


def test_files_in_html_and_json_out(tmp_path):
    """Score MusicXML + performance MIDI -> aligned report files, no references needed."""
    import partitura as pt

    from pianolens.report import report_from_files, write_report
    from tests.align.test_align import make_part, make_perf, melody

    pitches = [60, 62, 64, 65, 67, 69, 71, 72] * 4  # 8 bars of quarters
    xml = tmp_path / "s.musicxml"
    pt.save_musicxml(make_part(melody(pitches)), str(xml))
    played = list(pitches)
    played[9] += 1  # one wrong note in bar 3
    na = make_perf(np.arange(len(played)) * 0.5, played)
    mid = tmp_path / "p.mid"
    pt.save_performance_midi(pt.performance.PerformedPart.from_note_array(na), str(mid))
    rep = report_from_files(mid, score=xml, provenance="transcribed", use_pianocore=False,
                            config=CFG)
    h, j = write_report(rep, tmp_path / "out" / "r.html")
    data = json.loads(j.read_text())
    assert data["correctness"]["n_wrong_pitch"] == 1
    assert data["bars"][2]["correctness"]["n_wrong_pitch"] == 1
    assert data["confidence"]["velocity"] == "low"
    text = h.read_text()
    assert "<svg" in text and not re.search(r"https?://", text)


# ---------------------------------------------------------------- F-08b: recurring errors

REC_BAR = 3  # the same wrong note in every take
SLIP_BARS = (12, 7, 14)  # one different random slip per take


def _take(k: int):
    rng = np.random.default_rng(20 + k)
    ap = build(NOTES, _tempo_fn(0.25), vel=_vel(1.0, rng),
               offsets=rng.normal(0, 0.005, len(NOTES)), pid=f"take{k}")
    ap.performance.provenance = "disklavier"
    ap = _with_wrong_notes(ap, REC_BAR, 1)
    return _with_wrong_notes(ap, SLIP_BARS[k], 1)


def test_error_signatures_and_recurrence():
    from pianolens.features.correctness import correctness
    from pianolens.report.build import bar_labels, error_signatures, recurring_errors

    sigs = []
    for k in range(3):
        ap = _take(k)
        sigs.append(error_signatures(correctness(ap), bar_labels(ap.score)))
    lab = str(REC_BAR + 1)
    assert all(any(key[0] == "wrong_pitch" for key in s.get(lab, ())) for s in sigs)
    rec = recurring_errors(sigs, 2)
    assert list(rec) == [lab]
    assert list(rec[lab].values()) == [3]
    assert recurring_errors(sigs[:1], 2) == {}
    # only the kinds asked for count
    assert recurring_errors(sigs, 2, kinds=("missed",)) == {}


def test_recurring_error_is_strong_and_slips_are_not(refs):
    inp = ReportInputs(ap=_take(0), provenance="disklavier", same_score_refs=refs,
                       same_score_provenance="disklavier", takes=[_take(1), _take(2)])
    rep = to_jsonable(build_report(inp, CFG))
    bars = rep["bars"]
    rb = bars[REC_BAR]["correctness"]
    # one wrong note alone is within the expert range; recurring in 3 of 3 takes -> strong
    assert rb["n_wrong_pitch"] == 1 and rb["tier"] == "strong"
    assert rb["recurring"][0]["n_takes"] == 3 and rb["recurring"][0]["kind"] == "wrong_pitch"
    assert " instead of " in rb["recurring"][0]["text"]
    # the main take's own slip (one wrong note, not repeated) stays untiered
    assert bars[SLIP_BARS[0]]["correctness"]["n_wrong_pitch"] == 1
    assert bars[SLIP_BARS[0]]["correctness"]["tier"] == "none"
    assert not bars[SLIP_BARS[1]]["correctness"]["recurring"]
    assert rep["takes"]["recurring_error_bars"] == [str(REC_BAR + 1)]
    assert rep["correctness"]["n_bars_recurring"] == 1
    top = rep["practise"][0]
    assert top["category"] == "correctness" and top["bars"] == [REC_BAR]
    assert "recurs across your takes" in top["text"] and "3 of 3 takes" in top["text"]
    html = render_html(rep)
    assert "recurring" in html


def test_correctness_ranks_first_within_each_tier(report):
    from pianolens.report.build import _TIER_RANK, CATEGORY_RANK

    iss = report["issues"]
    for tier in ("strong", "notable"):
        cats = [CATEGORY_RANK[d["category"]] for d in iss if d["tier"] == tier]
        assert cats == sorted(cats)
    tiers = [_TIER_RANK[d["tier"]] for d in iss]
    assert tiers == sorted(tiers, reverse=True)
    # the 3 wrong notes (strong) come before any strong control or shaping issue
    strong = [d for d in iss if d["tier"] == "strong"]
    assert strong[0]["category"] == "correctness"


def test_recurring_error_needs_expert_check():
    """Without expert recordings of the score, a recurring wrong note is listed, not promoted."""
    inp = ReportInputs(ap=_take(0), provenance="disklavier", takes=[_take(1), _take(2)])
    rep = to_jsonable(build_report(inp, CFG))
    assert rep["takes"]["promoted"] is False and rep["takes"]["n_expert_checks"] == 0
    rb = rep["bars"][REC_BAR]["correctness"]
    assert rb["recurring"] and rb["tier"] == "none"
    card = [c for c in rep["summary"] if c["title"] == "Correctness"][0]
    assert any("not marked strong" in f for f in card["findings"])


def test_expert_errors_are_not_recurring():
    """An error that experts also show at the same note is a checker artefact, not learned."""
    from pianolens.report.build import expert_error_keys, recurring_errors

    key = ("wrong_pitch", "n9", 61)
    takes = [{"3": {key}}, {"3": {key}}]
    assert recurring_errors(takes, 2) == {"3": {key: 2}}
    ex = expert_error_keys([{"3": {key}}, {"4": {("extra", 60)}}])
    assert recurring_errors(takes, 2, exclude=ex) == {}
