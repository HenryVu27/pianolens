import pytest

from pianolens.data import expert_novice as en

pytestmark = pytest.mark.skipif(not en.data_available(), reason="data/raw/expert_novice absent")


def test_recordings_index():
    idx = en.recordings_index()
    assert len(idx) == 83
    assert idx["wav_path"].notna().all() and idx["alignment_path"].notna().all()
    assert idx["performer_id"].nunique() == 21


def test_ratings_match_paper_count():
    r = en.load_ratings()
    assert len(r.table) == 803  # paper: 803 ratings
    assert r.table["value"].between(1, 5).all()
    assert r.matrix("overall").shape[0] == 83


def test_beat_alignment():
    path = en.recordings_index()["alignment_path"].iloc[0]
    df = en.load_beat_alignment(path)
    assert list(df.columns) == ["bar", "beat_frac", "time_sec"]
    assert df["time_sec"].is_monotonic_increasing
