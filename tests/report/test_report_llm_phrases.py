"""DF-02: the report's per-phrase tempo measure uses cached LLM phrase boundaries when they exist
and discloses the source, the phrase-count ratio and the caveats; otherwise it falls back to the
cadence detector and says why."""

from __future__ import annotations

import pytest

from pianolens.features.phrases_llm import (
    CACHE_ENV,
    anchors,
    edition_hash,
    score_hash,
    write_cache,
)
from pianolens.features.tempo import tempo_model
from pianolens.report import ReportConfig, render_html
from pianolens.report.build import _shaping_section, _untested_genre
from pianolens.report.render import _phrase_method
from pianolens.report.text import PHRASE_CAVEATS, PHRASE_DESCRIPTIVE, _phrase_tempo_text
from tests.report.test_report import _target


@pytest.fixture(scope="module")
def target():
    ap = _target()
    return ap, tempo_model(ap)


def _cache(ap, root, style="romantic", recognised=None):
    sc = ap.score
    prov = {"model": "claude-test", "date": "2026-09-29", "protocol": "R-08 (test)",
            "score_hash": score_hash(sc), "edition_hash": edition_hash(sc), "style": style}
    if recognised is not None:
        prov["recognised_piece"] = recognised
    runs = []
    for name, st in (("A", [0.0, 16.0, 32.0, 48.0]), ("B", [0.0, 12.0, 24.0, 32.0, 48.0])):
        en = [x - 1.0 for x in st[1:]]
        runs.append({"run": name, "starts": st, "ends": en, "start_anchors": anchors(sc, st),
                     "end_anchors": anchors(sc, en)})
    write_cache(sc.piece_id, prov, runs, root)


def _phrase_tempo(ap, tc):
    errors: dict[str, str] = {}
    out = _shaping_section(ap, tc, ReportConfig(), errors)
    assert "phrase_tempo" not in errors, errors
    return out["phrase_tempo"]


def test_llm_boundaries_used_and_disclosed(target, tmp_path, monkeypatch):
    ap, tc = target
    monkeypatch.setenv(CACHE_ENV, str(tmp_path))
    _cache(ap, tmp_path)
    p = _phrase_tempo(ap, tc)
    assert p["boundaries"] == "llm"
    assert [r["run"] for r in p["llm_runs"]] == ["A", "B"]
    # the reported value is the mean over runs (F-05e convention)
    ce = [r["concave_excess"] for r in p["llm_runs"]]
    assert p["concave_excess"] == pytest.approx(sum(ce) / 2)
    assert p["n_phrases"] == pytest.approx(sum(r["n_phrases"] for r in p["llm_runs"]) / 2)
    assert p["phrase_count_ratio"] == pytest.approx(p["n_phrases"] / p["n_phrases_cadence"])
    assert p["phrase_count_reference"] == "cadence detector"
    assert p["caveats"] == ["romantic"]  # 4/4 synthetic score: no compound-meter caveat
    assert p["llm_provenance"]["model"] == "claude-test"
    txt = _phrase_tempo_text(p)
    assert "language model" in txt and "ratio" in txt and PHRASE_CAVEATS["romantic"] in txt
    assert PHRASE_DESCRIPTIVE in txt and "cadence-detector boundaries" in txt
    # the flag follows the sign rule exactly
    assert p["undetermined"] == (p["concave_excess"] * p["concave_excess_cadence"] < 0)
    assert p["llm_provenance"]["recognised_runs"] == 0 and p["llm_provenance"]["n_runs"] == 2
    assert "named the piece" not in txt
    meth = _phrase_method({"shaping": {"phrase_tempo": p}})
    assert "language model" in meth and "claude-test" in meth and "Romantic" in meth
    assert "0.64" in meth and "0.55-0.72" in meth and "0.14 to 0.92" in meth
    assert "Nocturnes and waltzes were never tested" in meth and "undetermined" in meth
    assert "no practice item depends" in meth


def test_recognition_from_cache_is_disclosed(target, tmp_path, monkeypatch):
    ap, tc = target
    monkeypatch.setenv(CACHE_ENV, str(tmp_path))
    _cache(ap, tmp_path, recognised={"A": "Some composer, Some piece", "B": None})
    p = _phrase_tempo(ap, tc)
    assert p["llm_provenance"]["recognised_runs"] == 1
    assert "named the piece in 1 of 2 readings" in _phrase_tempo_text(p)
    assert "named the piece in 1 of 2 readings" in _phrase_method({"shaping": {"phrase_tempo": p}})


def _llm_block(ce, cc, **kw):
    p = {"boundaries": "llm", "concave_share": 0.6, "null_concave_share": 0.4, "n_phrases": 10.0,
         "concave_excess": ce, "concave_excess_cadence": cc,
         "llm_runs": [{"run": "A", "concave_excess": ce + 0.1},
                      {"run": "B", "concave_excess": ce - 0.1}],
         "phrase_count_ratio": 1.25, "n_phrases_cadence": 8.0,
         "phrase_count_reference": "cadence detector", "caveats": ["romantic"],
         "llm_provenance": {"model": "m", "recognised_runs": 2, "n_runs": 2},
         "undetermined": ce * cc < 0}
    p.update(kw)
    return p


def test_sign_disagreement_is_undetermined():
    txt = _phrase_tempo_text(_llm_block(0.31, -0.25))
    assert txt.startswith("Phrases in time (undetermined):")
    assert "disagree in direction" in txt
    # both values and the run spread stay visible
    assert "+31 points" in txt and "-25 points" in txt and "+41, +21" in txt
    assert "named the piece in 2 of 2 readings" in txt and PHRASE_DESCRIPTIVE in txt
    same = _phrase_tempo_text(_llm_block(0.31, 0.08))
    assert "undetermined" not in same and "disagree" not in same


def test_untested_genre_caveat():
    assert _untested_genre("pianocore:Chopin/Nocturnes,_Op.9/Nocturne_No.1") == "nocturne"
    assert _untested_genre("pianocore:Chopin/Waltzes,_Op.64/Waltz_No.7") == "waltz"
    assert _untested_genre("dcml:chopin_mazurkas/BI85") == ""
    txt = _phrase_tempo_text(_llm_block(0.2, 0.1, caveats=["romantic", "genre_untested"],
                                        untested_genre="nocturne"))
    assert "this piece is a nocturne; no nocturne was among" in txt and "{genre}" not in txt


def test_classical_cache_has_no_romantic_caveat(target, tmp_path, monkeypatch):
    ap, tc = target
    monkeypatch.setenv(CACHE_ENV, str(tmp_path))
    _cache(ap, tmp_path, style="classical")
    p = _phrase_tempo(ap, tc)
    assert p["boundaries"] == "llm" and p["caveats"] == []
    assert "Caution" not in _phrase_tempo_text(p)


def test_fallback_to_cadence_is_disclosed(target, tmp_path, monkeypatch):
    ap, tc = target
    monkeypatch.setenv(CACHE_ENV, str(tmp_path))  # empty cache folder
    p = _phrase_tempo(ap, tc)
    assert p["boundaries"] == "cadence"
    assert p["llm_fallback_reason"] == "no LLM phrase cache for this piece"
    assert "llm_runs" not in p and "phrase_count_ratio" not in p
    txt = _phrase_tempo_text(p)
    assert "found from cadences" in txt and "no LLM phrase cache" in txt
    assert PHRASE_DESCRIPTIVE in txt and "undetermined" not in txt
    meth = _phrase_method({"shaping": {"phrase_tempo": p}})
    assert "cadences" in meth and "no language-model boundaries" in meth


def test_compound_meter_caveat_text():
    p = {"boundaries": "llm", "concave_share": 0.6, "null_concave_share": 0.4, "n_phrases": 10.0,
         "concave_excess": 0.2, "llm_runs": [{"run": "A", "concave_excess": 0.2}],
         "phrase_count_ratio": 1.25, "n_phrases_cadence": 8.0,
         "phrase_count_reference": "cadence detector", "caveats": ["romantic", "compound_meter"],
         "llm_provenance": {"model": "m"}}
    txt = _phrase_tempo_text(p)
    assert PHRASE_CAVEATS["compound_meter"] in txt and PHRASE_CAVEATS["romantic"] in txt
    assert "BL-17" in PHRASE_CAVEATS["romantic"] and "BL-17" in PHRASE_CAVEATS["compound_meter"]
    assert "ratio 1.25" in txt and "+20 points" in txt


def test_methods_footer_in_html(target, tmp_path, monkeypatch):
    from pianolens.report import ReportInputs, build_report

    ap, _ = target
    monkeypatch.setenv(CACHE_ENV, str(tmp_path))
    _cache(ap, tmp_path)
    rep = build_report(ReportInputs(ap=ap, piece_id="synth", title="t", provenance="disklavier"))
    assert rep["shaping"]["phrase_tempo"]["boundaries"] == "llm"
    html = render_html(rep)
    assert "language model" in html and "protocol R-08" in html
