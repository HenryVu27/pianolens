"""Tests for pianolens.features.correctness on synthetic scores with known labels."""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from pianolens.data.types import (
    ALIGNMENT_DTYPE,
    MEASURE_DTYPE,
    PEDAL_DTYPE,
    AlignedPerformance,
    Alignment,
    Performance,
    Score,
)
from pianolens.features.correctness import (
    ONSET_TOLERANCE_SEC,
    WRONG_PITCH_WINDOW_SEC,
    correctness,
    expected_onsets,
    measure_rows,
)

S_DTYPE = np.dtype([("onset_beat", "f8"), ("duration_beat", "f8"), ("onset_quarter", "f8"),
                    ("duration_quarter", "f8"), ("pitch", "i4"), ("id", "U8"),
                    ("is_grace", "b")])  # fmt: skip
P_DTYPE = np.dtype([("onset_sec", "f8"), ("duration_sec", "f8"), ("pitch", "i4"),
                    ("velocity", "i4"), ("id", "U8")])  # fmt: skip


def build(n_bars: int = 4, grace_at: int | None = None, ornamented: tuple[str, ...] = ()):
    """Two-note chords (C4+E4 shifted) on every quarter of 4/4 bars, played at 0.5 s/quarter.

    Returns (score_notes, perf_notes, pairs, score_part) with every note matched; ids s<k>/p<k>.
    """
    s_rows, p_rows, pairs = [], [], []
    k = 0
    for q in range(4 * n_bars):
        for iv in (0, 4):
            pitch = 60 + (q % 5) + iv
            s_rows.append((q, 1, q, 1, pitch, f"s{k}", False))
            p_rows.append((0.5 * q + 0.003 * iv, 0.4, pitch, 64, f"p{k}"))
            pairs.append(("match", f"s{k}", f"p{k}"))
            k += 1
    if grace_at is not None:
        s_rows.append((grace_at, 0, grace_at, 0, 72, "g0", True))
    sn = np.array(s_rows, dtype=S_DTYPE)
    pn = np.array(p_rows, dtype=P_DTYPE)
    part = SimpleNamespace(notes_tied=[SimpleNamespace(id=i, ornaments=["trill-mark"])
                                       for i in ornamented])  # fmt: skip
    return sn, pn, pairs, part


def aligned(sn, pn, pairs, part=None, n_bars=4) -> AlignedPerformance:
    measures = np.array([(m + 1, str(m + 1), 4.0 * m, 4.0 * (m + 1)) for m in range(n_bars)],
                        dtype=MEASURE_DTYPE)  # fmt: skip
    score = Score("s", "piece", sn, measures, part=part)
    perf = Performance("p", "piece", "x", "disklavier", pn, np.empty(0, PEDAL_DTYPE), "test")
    al = Alignment(np.array(pairs, dtype=ALIGNMENT_DTYPE), "s", "p", False, "test")
    return AlignedPerformance(perf, score, al)


def wrong_pitch_case(delta: int, dt: float):
    """Score note s10 played with pitch + delta at onset + dt: alignment has ins + del."""
    sn, pn, pairs, part = build()
    i = 10
    pn["pitch"][i] += delta
    pn["onset_sec"][i] += dt
    pairs[i] = ("deletion", f"s{i}", "")
    pairs.append(("insertion", "", f"p{i}"))
    return sn, pn, pairs


def test_perfect_performance():
    res = correctness(aligned(*build()[:3]))
    assert set(res.notes["label"]) == {"correct"}
    assert set(res.score_notes["label"]) == {"correct"}
    assert res.summary["accuracy"] == 1.0
    assert res.summary["error_rate"] == 0.0
    assert res.summary["match_ratio"] == 1.0
    assert list(res.bars["n_score_notes"]) == [8, 8, 8, 8]
    assert res.bars["accuracy"].eq(1.0).all()


@pytest.mark.parametrize("delta", [1, -2, 12])
def test_wrong_pitch_paired(delta):
    res = correctness(aligned(*wrong_pitch_case(delta, 0.02)))
    row = res.notes.set_index("performance_id").loc["p10"]
    assert row["label"] == "wrong_pitch" and row["score_id"] == "s10"
    assert res.score_notes.set_index("score_id").loc["s10", "label"] == "wrong_pitch"
    assert res.summary["n_wrong_pitch"] == 1
    assert res.summary["n_missed"] == 0 and res.summary["n_extra"] == 0
    # s10 is in bar 2 (quarter 5)
    assert res.bars.loc[1, "n_wrong_pitch"] == 1


@pytest.mark.parametrize(("delta", "dt", "kw"), [
    (5, 0.0, {}),            # too far in pitch
    (1, 0.12, {}),           # too late for the default 100 ms window
    (1, 0.08, {"wrong_pitch_window_sec": 0.05}),
    (12, 0.0, {"allow_octave": False}),
])  # fmt: skip
def test_wrong_pitch_not_paired(delta, dt, kw):
    res = correctness(aligned(*wrong_pitch_case(delta, dt)), **kw)
    assert res.notes.set_index("performance_id").loc["p10", "label"] == "extra"
    assert res.score_notes.set_index("score_id").loc["s10", "label"] == "missed"
    assert res.summary["n_extra"] == 1 and res.summary["n_missed"] == 1


def test_default_window_pairs_late_note():
    """80 ms late is outside the 50 ms onset tolerance but inside the 100 ms pairing window."""
    assert WRONG_PITCH_WINDOW_SEC == 0.1 and ONSET_TOLERANCE_SEC == 0.05
    res = correctness(aligned(*wrong_pitch_case(1, 0.08)))
    assert res.summary["n_wrong_pitch"] == 1
    assert res.params["wrong_pitch_window_sec"] == 0.1


def test_closest_candidate_wins():
    sn, pn, pairs = wrong_pitch_case(1, 0.0)
    # a second, later unmatched note one semitone off: the on-time one must be paired
    pn = np.concatenate([pn, np.array([(2.5 + 0.04, 0.1, int(sn["pitch"][10]) - 1, 30, "x1")],
                                      dtype=P_DTYPE)])  # fmt: skip
    pairs.append(("insertion", "", "x1"))
    res = correctness(aligned(sn, pn, pairs)).notes.set_index("performance_id")
    assert res.loc["p10", "label"] == "wrong_pitch"
    assert res.loc["x1", "label"] == "extra"


def test_missed_and_extra_per_bar():
    sn, pn, pairs, _ = build()
    pairs[20] = ("deletion", "s20", "")  # quarter 10 -> bar 3
    keep = np.ones(len(pn), bool)
    keep[20] = False
    pn = pn[keep]
    pairs = [p for p in pairs]
    extra = np.array([(6.6, 0.1, 30, 20, "x0")], dtype=P_DTYPE)  # 6.6 s = quarter 13.2 -> bar 4
    pn = np.concatenate([pn, extra])
    pairs.append(("insertion", "", "x0"))
    res = correctness(aligned(sn, pn, pairs))
    assert res.bars["n_missed"].tolist() == [0, 0, 1, 0]
    assert res.bars["n_extra"].tolist() == [0, 0, 0, 1]
    assert res.summary["n_bars_with_missed"] == 1
    assert res.summary["accuracy"] == pytest.approx(31 / 32)
    assert res.summary["error_rate"] == pytest.approx(2 / 32)


def test_interpolated_excluded():
    sn, pn, pairs, _ = build()
    pairs[3] = ("interpolated", "s3", "p3")
    res = correctness(aligned(sn, pn, pairs))
    assert res.summary["n_interpolated"] == 1
    assert res.summary["n_score_notes"] == 31
    assert res.summary["n_performed_notes"] == 31
    assert res.summary["accuracy"] == 1.0
    assert res.bars.loc[0, "n_interpolated"] == 1


def test_grace_note_skipped_and_ornament_extras():
    sn, pn, pairs, part = build(grace_at=4, ornamented=("s12",))
    pairs.append(("deletion", "g0", ""))
    # trill notes around s12 (quarter 6 -> 3.0 s, pitch 61+... ) and a grace-like slip near q4
    p12 = int(sn["pitch"][12])
    extras = np.array([(3.1, 0.05, p12 + 2, 40, "t0"), (3.2, 0.05, p12, 40, "t1"),
                       (1.95, 0.05, 71, 40, "gx")], dtype=P_DTYPE)  # fmt: skip
    pn = np.concatenate([pn, extras])
    pairs += [("insertion", "", i) for i in ("t0", "t1", "gx")]
    res = correctness(aligned(sn, pn, pairs, part))
    lab = res.notes.set_index("performance_id")["label"]
    assert lab["t0"] == lab["t1"] == lab["gx"] == "ornament"
    assert res.score_notes.set_index("score_id").loc["g0", "label"] == "ornament_skipped"
    assert res.summary["n_extra"] == 0 and res.summary["n_missed"] == 0
    # ornaments=False grades g0 like any score note. Its expected onset is the median of its
    # chord-mates (2.006 s); gx is 1 semitone off and 56 ms early, so it pairs with g0 as a wrong
    # pitch inside the 100 ms window and stays extra + missed at 50 ms.
    off = correctness(aligned(sn, pn, pairs, part), ornaments=False)
    assert off.summary["n_ornament"] == 0
    g0 = off.score_notes.set_index("score_id").loc["g0"]
    assert g0["expected_onset_sec"] == pytest.approx(2.006)
    assert g0["label"] == "wrong_pitch" and g0["performance_id"] == "gx"
    lab_off = off.notes.set_index("performance_id")["label"]
    assert lab_off["t0"] == lab_off["t1"] == "extra"
    assert off.summary["n_missed"] == 0 and off.summary["n_extra"] == 2
    narrow = correctness(aligned(sn, pn, pairs, part), ornaments=False,
                         wrong_pitch_window_sec=ONSET_TOLERANCE_SEC)  # fmt: skip
    assert narrow.score_notes.set_index("score_id").loc["g0", "label"] == "missed"
    assert narrow.summary["n_missed"] == 1 and narrow.summary["n_extra"] == 3


def test_no_matches_and_unknown_ids_do_not_crash():
    sn, pn, _, _ = build(n_bars=1)
    pairs = [("deletion", f"s{k}", "") for k in range(len(sn))]
    pairs += [("insertion", "", f"p{k}") for k in range(len(pn))]
    pairs.append(("match", "nope", "p0"))
    res = correctness(aligned(sn, pn, pairs, n_bars=1), wrong_pitch_window_sec=0.05)
    assert res.summary["n_correct"] == 0
    assert res.summary["n_unknown_ids"] == 1
    assert res.summary["alignment_suspect"]
    assert np.isnan(res.score_notes["expected_onset_sec"]).all()


def test_helpers():
    measures = np.array([(1, "1", 0.0, 4.0), (2, "2", 4.0, 8.0)], dtype=MEASURE_DTYPE)
    np.testing.assert_array_equal(measure_rows(measures, np.array([-1, 0, 3.9, 4, 7.9, 8])),
                                  [-1, 0, 0, 1, 1, -1])  # fmt: skip
    q, t = expected_onsets(np.array([0, 0, 1, 2]), np.array([0.0, 0.02, 0.5, 0.45]))
    np.testing.assert_allclose(q, [0, 1, 2])
    np.testing.assert_allclose(t, [0.01, 0.5, 0.5])  # median, then non-decreasing
