import numpy as np
import pytest

from pianolens.data.types import ALIGNMENT_DTYPE, MEASURE_DTYPE, PEDAL_DTYPE
from pianolens.models.expression_io import (
    deadpan,
    global_seconds_per_quarter,
    matched_pairs,
    note_expression,
    onset_curves,
    onset_groups,
    time_signature_events,
)

S_DT = np.dtype([("onset_quarter", "f8"), ("duration_quarter", "f8"), ("pitch", "i4"),
                 ("id", "U8"), ("ts_beats", "i4"), ("ts_beat_type", "i4")])
P_DT = np.dtype([("onset_sec", "f8"), ("duration_sec", "f8"), ("pitch", "i4"),
                 ("velocity", "i4"), ("id", "U8")])


def _toy():
    # chord (60, 64) at q0, 62 at q1, 65 at q2, 67 at q3 (deleted), extra note in perf
    score = np.array([
        (0.0, 1.0, 64, "s1", 4, 4), (0.0, 1.0, 60, "s0", 4, 4), (1.0, 1.0, 62, "s2", 4, 4),
        (2.0, 1.0, 65, "s3", 4, 4), (3.0, 1.0, 67, "s4", 4, 4),
    ], dtype=S_DT)
    perf = np.array([
        (0.00, 0.4, 60, 50, "p0"), (0.02, 0.4, 64, 70, "p1"), (0.50, 0.25, 62, 60, "p2"),
        (1.10, 0.5, 65, 40, "p3"), (1.2, 0.1, 66, 30, "px"),
    ], dtype=P_DT)
    pairs = np.array([
        ("match", "s0", "p0"), ("match", "s1", "p1"), ("match", "s2", "p2"),
        ("match", "s3", "p3"), ("deletion", "s4", ""), ("insertion", "", "px"),
    ], dtype=ALIGNMENT_DTYPE)
    pedal = np.array([(0.1, 64, 127), (0.9, 64, 0), (0.5, 67, 127)], dtype=PEDAL_DTYPE)
    return score, perf, pairs, pedal


def test_matched_pairs_order_and_drops():
    score, perf, pairs, pedal = _toy()
    mp = matched_pairs(score, perf, pairs, pedal)
    assert len(mp) == 4
    assert mp.pitch.tolist() == [60, 64, 62, 65]  # score order: onset, then pitch
    assert mp.perf_id.tolist() == ["p0", "p1", "p2", "p3"]
    assert mp.velocity.tolist() == [50, 70, 60, 40]
    assert mp.pedal.shape == (2, 2)  # sustain only
    assert mp.meta["n_match"] == 4 and mp.meta["n_score"] == 5


def test_matched_pairs_drops_duplicate_onset_pitch():
    score, perf, pairs, _ = _toy()
    score = np.concatenate([score, np.array([(0.0, 0.5, 60, "s5", 4, 4)], dtype=S_DT)])
    perf = np.concatenate([perf, np.array([(0.01, 0.1, 60, 20, "p5")], dtype=P_DT)])
    pairs = np.concatenate([pairs, np.array([("match", "s5", "p5")], dtype=ALIGNMENT_DTYPE)])
    mp = matched_pairs(score, perf, pairs)
    assert len(mp) == 4
    assert np.sum(mp.pitch == 60) == 1


def test_global_spq_exact_on_mechanical_timing():
    q = np.array([0, 0, 1, 2, 3.5])
    assert global_seconds_per_quarter(q, 2.0 + 0.6 * q) == pytest.approx(0.6)


def test_note_expression_values():
    score, perf, pairs, _ = _toy()
    mp = matched_pairs(score, perf, pairs)
    ex = note_expression(mp.score_onset_q, mp.score_dur_q, mp.perf_onset_sec, mp.perf_dur_sec,
                         mp.velocity, spq=0.5)
    g, uq = onset_groups(mp.score_onset_q)
    assert uq.tolist() == [0.0, 1.0, 2.0]
    # chord onset = mean(0, 0.02) = 0.01; IOI to 0.5 = 0.49 over nominal 0.5
    assert ex["log_ioi"].iloc[0] == pytest.approx(np.log(0.49 / 0.5))
    assert ex["log_ioi"].iloc[0] == ex["log_ioi"].iloc[1]  # shared by the chord
    assert ex["log_ioi"].iloc[2] == pytest.approx(np.log(0.6 / 0.5))
    assert np.isnan(ex["log_ioi"].iloc[3])  # last onset
    assert ex["log_art"].iloc[2] == pytest.approx(np.log(0.25 / 0.5))
    cur = onset_curves(ex)
    assert len(cur) == 3 and cur["velocity"].iloc[0] == pytest.approx(60.0)


def test_deadpan_is_flat():
    score, perf, pairs, _ = _toy()
    mp = matched_pairs(score, perf, pairs)
    dp = deadpan(mp, spq=0.5, velocity=55)
    ex = note_expression(dp.score_onset_q, dp.score_dur_q, dp.perf_onset_sec, dp.perf_dur_sec,
                         dp.velocity)
    assert np.nanmax(np.abs(ex["log_ioi"])) < 1e-9
    assert set(dp.velocity.tolist()) == {55}
    assert np.allclose(ex["log_art"], np.log(0.95))


def test_time_signature_events_pickup_and_change():
    measures = np.array([(1, "0", -1.0, 0.0), (2, "1", 0.0, 4.0), (3, "2", 4.0, 7.0)],
                        dtype=MEASURE_DTYPE)
    notes = np.array([(-1.0, 1.0, 60, "a", 4, 4), (0.0, 1.0, 62, "b", 4, 4),
                      (4.0, 1.0, 64, "c", 3, 4)], dtype=S_DT)
    origin, ev = time_signature_events(measures, notes)
    assert origin == pytest.approx(-4.0)  # pickup ends a full empty bar
    assert ev == [(0.0, 4, 4), (8.0, 3, 4)]
