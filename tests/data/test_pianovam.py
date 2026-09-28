import pytest

from pianolens.data import pianovam

pytestmark = pytest.mark.skipif(not pianovam.data_available(), reason="data/raw/pianovam absent")


def test_index():
    md = pianovam.pianovam_index()
    assert len(md) == 107
    assert set(md["P1_skill"]) == set(pianovam.SKILLS)
    assert md["performance_id"].is_unique


def test_loads_performances():
    stats = pianovam.PianoVAMStats()
    perfs = list(pianovam.iter_performances(limit=3, stats=stats))
    assert stats.failed == 0 and len(perfs) == 3
    for p in perfs:
        assert p.provenance == "disklavier"
        assert p.meta["skill"] in pianovam.SKILLS
        assert len(p.notes) > 0
