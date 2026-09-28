import pytest

from pianolens.data import rach3

pytestmark = pytest.mark.skipif(not rach3.data_available(), reason="data/raw/rach3 absent")


def test_index_hanon_subset():
    md = rach3.rach3_index()
    hanon = md[md["piece_code"] == "hanoncexercs"]
    assert hanon.groupby("pianist").size().to_dict() == {"p1": 124, "p2": 36, "p3": 87}
    assert set(hanon["level"]) == {"advanced", "beginner"}


def test_loads():
    stats = rach3.Rach3Stats()
    perfs = list(rach3.iter_performances(piece_code="hanoncexercs", limit=2, stats=stats))
    assert stats.failed == 0 and len(perfs) == 2
    assert all(len(p.notes) > 0 and p.provenance == "sensor" for p in perfs)
