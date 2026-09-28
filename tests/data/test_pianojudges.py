import pytest

from pianolens.data import pianojudges as pj

pytestmark = pytest.mark.skipif(not pj.data_available(), reason="data/raw/pianojudges absent")


def test_cipi_index():
    c = pj.load_cipi_index()
    assert len(c) == 652
    assert c["henle"].between(1, 9).all()
    assert set(c["split"].dropna()) == {"train", "val", "test"}


def test_channel_lists():
    ch = pj.load_channel_lists()
    assert set(ch["level"]) == {"novice", "advanced"}
    assert ch["url"].str.startswith("http").all()
