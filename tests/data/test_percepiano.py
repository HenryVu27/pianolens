import pytest

from pianolens.data import percepiano as pp


def test_parse_segment_name_player_before_segment():
    s = pp.parse_segment_name("Schubert_D960_mv2_8bars_3_05.mid")
    assert (s.work, s.bars, s.player, s.segment) == ("Schubert_D960_mv2", 8, "3", 5)
    assert s.score_stem == "Schubert_D960_mv2_8bars_Score_05"
    s = pp.parse_segment_name(" Schubert_D935_no.3_4bars_2_1.mid")  # leading space in repo
    assert s.stem == "Schubert_D935_no.3_4bars_2_1"
    assert pp.parse_segment_name("Beethoven_WoO80_var10_8bars_Score2_8").is_score_rendition


def test_performer_ids_are_per_composer():
    b = pp.percepiano_performer_id(pp.parse_segment_name("Beethoven_WoO80_var3_8bars_1_2"))
    s = pp.percepiano_performer_id(pp.parse_segment_name("Schubert_D960_mv3_8bars_1_01"))
    assert b == "percepiano:beethoven:1" and s == "percepiano:schubert:1"
    score = pp.percepiano_performer_id(pp.parse_segment_name("Schubert_D960_mv3_8bars_Score_01"))
    assert score == "percepiano:score"


def test_rated_stem_follows_author_renames():
    assert pp._rated_stem("Beethoven_WoO80_var10_8bars_Score_8.wav") == (
        "Beethoven_WoO80_var10_8bars_Score2_8"
    )
    assert pp._rated_stem("Beethoven_WoO80_thema_8bars_score_1.wav") == (
        "Beethoven_WoO80_thema_8bars_Score_1"
    )
    assert pp._rated_stem("Schubert_D935_no.3_4bars_2_1.wav") == "Schubert_D935_no.3_4bars_2_1"


needs_data = pytest.mark.skipif(
    not pp.data_available(), reason="PercePiano not downloaded to data/raw/percepiano"
)


@needs_data
def test_index_counts():
    idx = pp.percepiano_index()
    assert len(idx) == 1202
    assert idx["performance_id"].is_unique
    assert idx["piece_id"].nunique() == 4
    human = idx[idx["provenance"] != "synthetic"]
    assert human["performer_id"].nunique() == 25


@needs_data
def test_ratings_match_official_means_without_dedupe():
    raw = pp.load_percepiano_ratings(drop_exact_duplicates=False)
    off = pp.load_percepiano_official_means()
    assert len(off) == 1189
    ours = (raw.mean() / 7).loc[off.index, list(pp.DIMENSIONS)]
    assert (ours - off).abs().max().max() < 1e-9
    r = pp.load_percepiano_ratings()
    assert r.table["rater_id"].nunique() == 63
    assert set(r.table["performance_id"]) <= set(pp.percepiano_index()["performance_id"])
    assert r.table["value"].between(1, 7).all()


@needs_data
def test_load_one_segment_with_score_and_span():
    idx = pp.percepiano_index()
    row = idx[idx["performance_id"] == "percepiano:Beethoven_WoO80_var10_8bars_1_8"]
    (ap,) = list(pp.iter_percepiano(index=row))
    assert ap.performance.piece_id == "beethoven_woo80"
    assert ap.performance.provenance == "disklavier"
    assert ap.score is not None and len(ap.score.measures) == 8
    if pp.DEFAULT_SPANS.is_file():  # built by scripts/build_percepiano_spans.py
        assert ap.performance.span == (81, 88)
