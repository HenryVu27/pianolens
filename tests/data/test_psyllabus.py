import pytest

from pianolens.data import psyllabus

pytestmark = pytest.mark.skipif(not psyllabus.data_available(), reason="PSyllabus absent")


def test_index_labels_and_splits():
    idx = psyllabus.psyllabus_index()
    assert len(idx) == 7901
    assert idx["difficulty"].between(0, 10).all()
    assert set(idx["split"].dropna()) == {"train", "val", "test"}


def test_loads_two_performances():
    stats = psyllabus.PsyllabusStats()
    perfs = list(psyllabus.iter_performances(limit=2, stats=stats))
    assert stats.failed == 0 and len(perfs) == 2
    assert all(p.provenance == "transcribed" and "difficulty" in p.meta for p in perfs)
