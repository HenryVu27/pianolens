import pytest

from pianolens.data import vienna4x22 as v

pytestmark = pytest.mark.skipif(not v.data_available(), reason="data/raw/vienna4x22 absent")


def test_all_match_files_present():
    assert len(v.match_files()) == 88


def test_loads_first_performances_with_ground_truth_alignment():
    stats = v.ViennaStats()
    aps = [ap for ap, _ in zip(v.iter_aligned(stats=stats), range(3), strict=False)]
    assert stats.failed == 0 and len(aps) == 3
    for ap in aps:
        assert ap.performance.provenance == "sensor"
        assert ap.performance.piece_id == "chopin_op10_no3"
        assert ap.alignment.ground_truth and len(ap.alignment.matches) > 400
        score_ids = set(ap.score.notes["id"].tolist())
        assert set(ap.alignment.matches["score_id"].tolist()) <= score_ids
