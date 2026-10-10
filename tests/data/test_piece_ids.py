"""Partial-score labels (DF-14): whole-work titles whose score holds one movement or part."""

import pytest

from pianolens.data import asap, pianocore
from pianolens.data.piece_ids import PARTIAL_SCORES, score_movement


def test_score_movement_fills_only_missing_movements():
    assert score_movement("bach_bwv971") == "2. Andante"
    assert score_movement("bach_bwv971", None) == "2. Andante"
    assert score_movement("bach_bwv971", float("nan")) == "2. Andante"
    assert score_movement("asap:Bach/Italian_concerto", "") == "2. Andante"
    assert score_movement("chopin_op22") == "Grande polonaise brillante"
    # the source's own movement wins; unknown ids stay empty
    assert score_movement("bach_bwv971", "3. Presto") == "3. Presto"
    assert score_movement("chopin_op10_no3") == ""
    assert score_movement("chopin_op10_no3", "x") == "x"


def test_partial_scores_ids_are_not_renamed():
    # DF-14 relabels; it never introduces movement ids (DECISIONS 2026-10-10)
    assert set(PARTIAL_SCORES) == {"bach_bwv971", "asap:Bach/Italian_concerto", "chopin_op22"}
    assert all("_mv" not in k for k in PARTIAL_SCORES)


@pytest.mark.skipif(not asap.data_available(), reason="(n)ASAP not downloaded to data/raw/asap")
def test_asap_italian_concerto_is_second_movement():
    import partitura as pt

    idx = asap.asap_index()
    row = idx[idx["title"] == "Italian_concerto"].iloc[0]
    score = asap.load_asap_score(row, keep_part=True)
    assert score.meta["movement"] == "2. Andante"
    assert len(score.notes) == 1085
    part = score.part
    assert len(list(part.iter_all(pt.score.Measure))) == 49
    assert {(t.beats, t.beat_type) for t in part.iter_all(pt.score.TimeSignature)} == {(3, 4)}
    assert {k.fifths for k in part.iter_all(pt.score.KeySignature)} == {-1}
    perf = asap.load_asap_performance(row)
    assert perf.meta["movement"] == "2. Andante"
    other = idx[idx["title"] == "Etudes_op_10_3"].iloc[0]
    assert asap.load_asap_performance(other).meta["movement"] == ""


@pytest.mark.skipif(not pianocore.data_available(), reason="data/raw/pianocore not downloaded")
def test_pianocore_partial_scores_carry_movement():
    pc = pianocore.PianoCoRe()
    idx = pc.index
    for pid, mv in (("bach_bwv971", "2. Andante"), ("chopin_op22", "Grande polonaise brillante")):
        rows = idx[(idx["piece_id"] == pid) & idx["refined_score_midi_path"].notna()]
        assert len(rows) > 0
        assert pc.load_score(rows.iloc[0]).meta["movement"] == mv
