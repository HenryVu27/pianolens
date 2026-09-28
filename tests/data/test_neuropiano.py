import pytest

from pianolens.data import neuropiano as n

pytestmark = pytest.mark.skipif(not n.data_available(), reason="data/raw/neuropiano absent")


def test_ratings():
    r = n.load_ratings()
    t = r.table
    assert t["performance_id"].nunique() == 104
    assert len(r.dimensions) == 13
    assert t["value"].between(0, 6).all()


def test_audio_bytes_are_wav():
    pid = n.load_ratings().table["performance_id"].iloc[0]
    assert n.load_audio_bytes(pid)[:4] == b"RIFF"
