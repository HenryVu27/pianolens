"""LLM phrase cache (DF-02): write / load, hashing, mapping onto score variants, and
``BasisConfig(phrase_source="llm")`` with its fallback to the cadence detector."""

from __future__ import annotations

import json

import numpy as np
import pytest

from pianolens.data import types
from pianolens.features.phrases_llm import (
    CACHE_SCHEMA,
    anchors,
    cache_path,
    edition_hash,
    load_cache,
    resolve_llm_phrases,
    score_hash,
    write_cache,
)
from pianolens.features.score_basis import BasisConfig, score_basis
from tests.features.test_control import S_DTYPE, build, scale_texture


def _score(n_bars: int, passes: int = 1, pid: str = "test:piece") -> types.Score:
    """Quarter notes C4.. in 4/4, ``n_bars`` bars, written out ``passes`` times (ids ``n<i>-<k>``,
    as partitura's unfolding names them)."""
    rows = []
    for k in range(passes):
        for i in range(4 * n_bars):
            b = float(4 * n_bars * k + i)
            rows.append((b, 1.0, b, 1.0, 60 + i % 12, f"n{i}-{k + 1}", False, 4, 1, 1))
    sn = np.array(rows, dtype=S_DTYPE)
    nb = n_bars * passes
    ms = np.zeros(nb, dtype=types.MEASURE_DTYPE)
    ms["number"] = np.arange(1, nb + 1)
    ms["start_quarter"] = 4.0 * np.arange(nb)
    ms["end_quarter"] = ms["start_quarter"] + 4
    return types.Score("test:s", types.PieceId(pid), sn, ms)


def _prov(score, style: str = "romantic") -> dict:
    return {"model": "claude-test", "date": "2026-09-29", "protocol": "R-08 (test)",
            "score_hash": score_hash(score), "edition_hash": edition_hash(score),
            "style": style}


def _run(score, name: str, starts, ends) -> dict:
    return {"run": name, "starts": list(starts), "ends": list(ends),
            "start_anchors": anchors(score, starts), "end_anchors": anchors(score, ends)}


def test_cache_path_is_file_safe_and_distinct(tmp_path):
    a = cache_path("pianocore:Composer,_X/Set,_Op.1/No.1", tmp_path)
    b = cache_path("pianocore:Composer,_X/Set,_Op.1/No.2", tmp_path)
    assert a.parent == tmp_path and a != b
    assert "/" not in a.name and ":" not in a.name and a.suffix == ".json"


def test_write_and_load_roundtrip(tmp_path):
    sc = _score(8)
    p = write_cache(sc.piece_id, _prov(sc), [_run(sc, "A", [0.0, 16.0], [15.0, 31.0])],
                    tmp_path)
    doc, why = load_cache(sc.piece_id, tmp_path)
    assert why == "" and doc["schema"] == CACHE_SCHEMA and doc["runs"][0]["starts"] == [0, 16]
    assert json.loads(p.read_text())["provenance"]["model"] == "claude-test"


def test_write_rejects_missing_provenance(tmp_path):
    sc = _score(4)
    prov = _prov(sc)
    del prov["model"]
    with pytest.raises(ValueError, match="model"):
        write_cache(sc.piece_id, prov, [_run(sc, "A", [0.0], [])], tmp_path)


def test_load_reports_missing_and_bad_cache(tmp_path):
    sc = _score(4)
    assert load_cache(sc.piece_id, tmp_path) == (None, "no LLM phrase cache for this piece")
    p = cache_path(sc.piece_id, tmp_path)
    p.write_text(json.dumps({"schema": "other/0", "piece_id": sc.piece_id}))
    doc, why = load_cache(sc.piece_id, tmp_path)
    assert doc is None and "schema" in why
    p.write_text("{not json")
    assert "unreadable" in load_cache(sc.piece_id, tmp_path)[1]


def test_hashes_separate_variant_and_edition():
    one, two = _score(4, 1), _score(4, 2)
    assert score_hash(one) != score_hash(two)
    assert edition_hash(one) == edition_hash(two)  # same written notes, other repeat path
    other = _score(5, 1)
    assert edition_hash(other) != edition_hash(one)


def test_resolve_exact_variant(tmp_path):
    sc = _score(8)
    write_cache(sc.piece_id, _prov(sc), [_run(sc, "A", [0.0, 8.0, 20.0], [7.0, 19.0]),
                                         _run(sc, "B", [0.0, 16.0], [15.0])], tmp_path)
    got, why = resolve_llm_phrases(sc, root=tmp_path)
    assert why == "" and got.mapping == "exact" and got.style == "romantic"
    assert [r.run for r in got.runs] == ["A", "B"]
    assert got.runs[0].starts == [0.0, 8.0, 20.0] and got.runs[1].ends == [15.0]


def test_resolve_other_repeat_path_by_note_ids(tmp_path):
    """Annotated on one pass; the target plays the passage twice: every boundary recurs."""
    one, two = _score(4, 1), _score(4, 2)
    write_cache(one.piece_id, _prov(one), [_run(one, "A", [0.0, 8.0], [7.0])], tmp_path)
    got, why = resolve_llm_phrases(two, root=tmp_path)
    assert why == "" and got.mapping == "note_ids"
    assert got.runs[0].starts == [0.0, 8.0, 16.0, 24.0]
    assert got.runs[0].ends == [7.0, 23.0] and got.runs[0].n_unmapped == 0


def test_resolve_refuses_another_edition(tmp_path):
    sc = _score(4)
    write_cache(sc.piece_id, _prov(sc), [_run(sc, "A", [0.0, 8.0], [7.0])], tmp_path)
    other = _score(5, pid=sc.piece_id)
    got, why = resolve_llm_phrases(other, root=tmp_path)
    assert got is None and "edition hash mismatch" in why


def test_score_basis_llm_source_uses_cache(tmp_path):
    ap = build(scale_texture(16), lambda b: 0.5 * b)
    sc = ap.score
    write_cache(sc.piece_id, _prov(sc), [_run(sc, "A", [0.0, 16.0, 36.0], [15.0, 35.0]),
                                         _run(sc, "B", [0.0, 32.0], [31.0])], tmp_path)
    b = score_basis(sc, config=BasisConfig(phrase_source="llm", llm_cache_dir=str(tmp_path),
                                           include_tension=False))
    assert b.meta["phrase_source"] == "llm" and "phrase_source_fallback" not in b.meta
    starts = b.phrases.loc[b.phrases["source"] == "llm", "start_beat"].tolist()
    assert starts == [0.0, 16.0, 36.0]  # first run; the 28-beat last phrase is not split
    assert len(b.meta["llm_phrases"].runs) == 2


def test_score_basis_llm_falls_back_to_cadence(tmp_path):
    ap = build(scale_texture(16), lambda b: 0.5 * b)
    b = score_basis(ap.score, config=BasisConfig(phrase_source="llm",
                                                 llm_cache_dir=str(tmp_path),
                                                 include_tension=False))
    ref = score_basis(ap.score, config=BasisConfig(phrase_source="cadence",
                                                   include_tension=False))
    assert b.meta["phrase_source"] == "cadence"
    assert b.meta["phrase_source_fallback"] == "no LLM phrase cache for this piece"
    assert b.phrases["start_beat"].tolist() == ref.phrases["start_beat"].tolist()


def test_score_basis_rejects_unknown_source():
    ap = build(scale_texture(4), lambda b: 0.5 * b)
    with pytest.raises(ValueError, match="phrase_source"):
        score_basis(ap.score, config=BasisConfig(phrase_source="oracle"))
