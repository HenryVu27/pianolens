import pytest

from pianolens.data import maestro

pytestmark = pytest.mark.skipif(not maestro.data_available(), reason="MAESTRO MIDI absent")


def test_index_counts():
    md = maestro.maestro_index()
    assert len(md) == 1276
    assert set(md["split"]) == {"train", "validation", "test"}


def test_loads_two_performances():
    stats = maestro.MaestroStats()
    perfs = list(maestro.iter_performances(limit=2, stats=stats))
    assert stats.failed == 0 and len(perfs) == 2
    for p in perfs:
        assert p.provenance == "disklavier" and len(p.notes) > 100 and len(p.pedal) > 0
        assert p.piece_id.startswith("maestro_v3:")
