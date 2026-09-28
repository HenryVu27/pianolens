import pytest

from pianolens.data import mazurkabl as m

pytestmark = pytest.mark.skipif(not m.data_available(), reason="data/raw/mazurkabl absent")


def test_piece_id():
    assert m.mazurka_piece_id("M06-1") == "chopin_op6_no1"


def test_load_one_mazurka():
    df = m.load_mazurka("M06-1")
    assert list(df.columns) == list(m.BEAT_COLUMNS)
    assert df["performance_id"].nunique() > 10
    assert df["time_sec"].notna().all() and df["loudness"].notna().all()
    assert len(m.mazurkas()) == 46


def test_beat_curves():
    curves = m.load_beat_curves("M06-1")
    df = m.load_mazurka("M06-1")
    assert len(curves) == df["performance_id"].nunique()
    c = curves[0]
    assert c.piece_id == "chopin_op6_no1" and c.loudness_unit == "sone_norm"
    assert len(c) == len(df[df["performance_id"] == c.performance_id])
    assert c.beat is not None and c.beat.min() == 0
    assert (c.tempo_bpm[:-1] > 0).all()
