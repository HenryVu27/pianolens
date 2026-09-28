import pytest

from pianolens.data import majeppa

pytestmark = pytest.mark.skipif(not majeppa.data_available(), reason="data/raw/majeppa absent")


def test_index():
    md = majeppa.majeppa_index()
    assert len(md) == 4449
    assert set(md["expertise_level"]) == set(majeppa.EXPERTISE_LEVELS)


def test_loads_performances_with_scores():
    stats = majeppa.MajeppaStats()
    aps = list(majeppa.iter_aligned(limit=5, stats=stats))
    assert stats.failed == 0 and len(aps) == 5
    for ap in aps:
        assert ap.performance.provenance == "transcribed"
        assert ap.performance.meta["expertise_level"] in majeppa.EXPERTISE_LEVELS
        assert ap.performance.performer_id.startswith("majeppa:recording/")
    with_score = [ap for ap in aps if ap.score is not None]
    assert with_score
    path = majeppa.load_dtw_path(with_score[0].performance.performance_id)
    assert list(path.columns) == ["score_s", "perf_s"]


@pytest.mark.parametrize(
    ("composer", "title", "expected"),
    [
        ("Frederic Chopin", "12 Etudes, Op. 10 - No. 2 in A Minor Chromatique", "chopin_op10_no2"),
        ("Robert Schumann", "Kreisleriana, Op. 16 - V. Sehr lebhaft", "schumann_op16_no5"),
        ("Claude Debussy", "Suite bergamasque, L. 75 - III. Clair de lune", "debussy_l75_mv3"),
        ("Czerny", "School Of Velocity Op 299 No 29", "czerny_op299_no29"),
        ("Frederic Chopin", "Nocturne No.18 in E, Op.62 No.2", "chopin_op62_no2"),
        ("Clementi", "Sonatina Op 36 No 1 Allegro", "majeppa:S"),  # movement not numbered
        ("Robert Schumann", "Faschingsschwank Aus Wien Op 26 I Allegro", "majeppa:S"),
        (None, "Super Mario Theme", "majeppa:S"),
    ],
)  # fmt: skip
def test_majeppa_piece_id(composer, title, expected):
    assert majeppa.majeppa_piece_id(composer, title, "S") == expected


def test_track_staff():
    keys = majeppa.score_track_staff("S_0001")
    assert keys is not None
    staffs = set(keys.values())
    assert {1, 2} <= staffs
    # staff 1 is the upper track
    hi = [p for (_, p), s in keys.items() if s == 1]
    lo = [p for (_, p), s in keys.items() if s == 2]
    assert sum(hi) / len(hi) > sum(lo) / len(lo)


def test_snap_score_durations():
    import numpy as np

    dt = [("onset_quarter", "f8"), ("duration_quarter", "f8"), ("duration_beat", "f8"),
          ("staff", "i8"), ("voice", "i8")]
    notes = np.array([(0.0, 0.4979, 0.4979, 1, 1), (0.5, 0.4729, 0.4729, 1, 1),
                      (1.0, 0.25, 0.25, 1, 1),  # staccato: gap 0.25 of a 0.5 IOI, kept
                      (1.5, 0.5, 0.5, 1, 1), (0.0, 1.9, 1.9, 2, 2), (2.0, 1.0, 1.0, 2, 2)],
                     dtype=dt)
    out, n = majeppa.snap_score_durations(notes)
    assert n == 3
    np.testing.assert_allclose(out["duration_quarter"], [0.5, 0.5, 0.25, 0.5, 2.0, 1.0])
    np.testing.assert_allclose(out["duration_beat"], out["duration_quarter"])
