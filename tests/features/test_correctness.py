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


# --------------------------------------------------------------------------- DF-10


def different_pitch_match(delta: int, ornamented: tuple[str, ...] = (), orn: str = "trill-mark"):
    """s12 matched to p12, but p12 was played ``delta`` semitones off (an aligner match of a
    different pitch, as parangonar's ornament step produces)."""
    sn, pn, pairs, _ = build()
    pn["pitch"][12] += delta
    part = SimpleNamespace(notes_tied=[SimpleNamespace(id=i, ornaments=[orn])
                                       for i in ornamented])  # fmt: skip
    return sn, pn, pairs, part


@pytest.mark.parametrize("rule", ["legacy", "tight"])
def test_different_pitch_match_is_wrong_pitch(rule):
    """DF-10: a match of another pitch on a plain note is a wrong pitch, never correct."""
    res = correctness(aligned(*different_pitch_match(1)), ornament_rule=rule)
    row = res.notes.set_index("performance_id").loc["p12"]
    assert row["label"] == "wrong_pitch" and row["score_id"] == "s12"
    assert res.score_notes.set_index("score_id").loc["s12", "label"] == "wrong_pitch"
    assert res.summary["n_pitch_dissolved"] == 1 and res.summary["n_correct"] == 31


def test_different_pitch_match_forced_pair_outside_window():
    """A dissolved match stays a wrong pitch even when its onset is outside the pairing window."""
    sn, pn, pairs, part = different_pitch_match(2)
    pn["onset_sec"][12] += 0.15
    res = correctness(aligned(sn, pn, pairs, part))
    assert res.notes.set_index("performance_id").loc["p12", "label"] == "wrong_pitch"
    assert res.summary["n_extra"] == 0 and res.summary["n_missed"] == 0


@pytest.mark.parametrize(("orn", "delta", "rule", "correct"), [
    ("trill-mark", 2, "legacy", True),         # trill started on the upper auxiliary
    ("trill-mark", 2, "tight", True),
    ("trill-mark", -1, "tight", True),         # closing turn uses the lower auxiliary
    ("inverted-mordent", 1, "tight", True),
    ("inverted-mordent", -1, "tight", False),  # wrong side for this ornament
    ("inverted-mordent", -1, "legacy", True),
    ("mordent", -2, "tight", True),
    ("mordent", 2, "tight", False),
    ("tremolo", 1, "tight", False),            # a tremolo re-strikes its own pitch
])  # fmt: skip
def test_ornament_rule_on_matches(orn, delta, rule, correct):
    res = correctness(aligned(*different_pitch_match(delta, ("s12",), orn)), ornament_rule=rule)
    lab = res.notes.set_index("performance_id").loc["p12", "label"]
    assert (lab == "correct") is correct
    assert res.summary["n_ornament_matches"] == int(correct)
    if not correct:
        assert lab == "wrong_pitch"


def test_ornaments_off_requires_same_pitch():
    res = correctness(aligned(*different_pitch_match(2, ("s12",))), ornaments=False)
    assert res.notes.set_index("performance_id").loc["p12", "label"] == "wrong_pitch"


def test_unknown_ornament_rule_rejected():
    with pytest.raises(ValueError):
        correctness(aligned(*build()[:3]), ornament_rule="loose")


# --------------------------------------------------------------------------- BL-23 tight rule


def test_tight_rule_pairs_wrong_note_next_to_trill():
    """A wrong key next to a trill: legacy tolerates it as an ornament note; tight pairs it with
    the note it replaced (BL-20: the whitelist ran before wrong-pitch pairing)."""
    sn, pn, pairs, part = build(ornamented=("s12",))  # s12: quarter 6, 3.0 s, pitch 61
    # s14 (quarter 7, pitch 62, 3.5 s) played as 63 = trill principal + 2, 20 ms early
    i = 14
    pn["pitch"][i] = int(sn["pitch"][12]) + 2
    pn["onset_sec"][i] -= 0.02
    pairs[i] = ("deletion", f"s{i}", "")
    pairs.append(("insertion", "", f"p{i}"))
    # the trill's other notes: upper auxiliary and principal
    p12 = int(sn["pitch"][12])
    extras = np.array([(3.1, 0.05, p12 + 2, 40, "t0"), (3.2, 0.05, p12, 40, "t1")],
                      dtype=P_DTYPE)  # fmt: skip
    pn = np.concatenate([pn, extras])
    pairs += [("insertion", "", "t0"), ("insertion", "", "t1")]
    # the trill lasts to its expected offset (3.5 s), so p14 (3.48 s) is inside its window
    legacy = correctness(aligned(sn, pn, pairs, part), ornament_rule="legacy")
    tight = correctness(aligned(sn, pn, pairs, part), ornament_rule="tight")
    assert legacy.notes.set_index("performance_id").loc["p14", "label"] == "ornament"
    assert legacy.score_notes.set_index("score_id").loc["s14", "label"] == "missed"
    t = tight.notes.set_index("performance_id")
    assert t.loc["p14", "label"] == "wrong_pitch" and t.loc["p14", "score_id"] == "s14"
    assert t.loc["t0", "label"] == t.loc["t1", "label"] == "ornament"  # genuine trill notes


def test_tight_rule_grace_notes():
    """Played grace: only re-strikes of its pitch are tolerated. Unplayed grace: ±2 (the grace
    played at a neighbouring pitch)."""
    sn, pn, pairs, part = build(grace_at=4)  # g0: pitch 72 before quarter 4 (2.0 s)
    pn = np.concatenate([pn, np.array([(1.96, 0.03, 72, 40, "gp"), (1.97, 0.03, 72, 40, "gr"),
                                       (1.98, 0.03, 70, 40, "gx")], dtype=P_DTYPE)])
    played = pairs + [("match", "g0", "gp"), ("insertion", "", "gr"), ("insertion", "", "gx")]
    lab = correctness(aligned(sn, pn, played, part),
                      ornament_rule="tight").notes.set_index("performance_id")["label"]
    assert lab["gp"] == "correct" and lab["gr"] == "ornament" and lab["gx"] == "extra"
    unplayed = pairs + [("deletion", "g0", "")] + [("insertion", "", k) for k in
                                                   ("gp", "gr", "gx")]  # fmt: skip
    res = correctness(aligned(sn, pn, unplayed, part), ornament_rule="tight")
    lab = res.notes.set_index("performance_id")["label"]
    assert lab["gx"] == "ornament" and lab["gp"] == "ornament"
    assert res.score_notes.set_index("score_id").loc["g0", "label"] == "ornament_skipped"


# --------------------------------------------------------------------------- BL-23 reassign


def absorbed_case():
    """s10 (pitch 60 at 2.5 s) played as 61, the pitch written for s12 at 3.0 s. The aligner
    matched s12 to that early wrong key and left the real s12 note unmatched (BL-20 absorption)."""
    sn, pn, pairs, _ = build()
    y = int(sn["pitch"][12])
    pn["pitch"][10] = y  # wrong key at 2.5 s equal to the pitch written at 3.0 s
    pairs[10] = ("deletion", "s10", "")
    pairs[12] = ("match", "s12", "p10")  # absorbed: s12 matched to the wrong key
    pairs.append(("insertion", "", "p12"))  # the note that really played s12
    return sn, pn, pairs


def test_reassign_moves_absorbed_match():
    sn, pn, pairs = absorbed_case()
    base = correctness(aligned(sn, pn, pairs), reassign=False)
    b = base.notes.set_index("performance_id")
    assert b.loc["p10", "label"] == "correct" and b.loc["p10", "score_id"] == "s12"
    res = correctness(aligned(sn, pn, pairs))  # BL-23 default: reassign=True
    assert res.params["reassign"] and res.params["ornament_rule"] == "legacy"
    r = res.notes.set_index("performance_id")
    assert r.loc["p12", "label"] == "correct" and r.loc["p12", "score_id"] == "s12"
    assert r.loc["p10", "label"] == "wrong_pitch" and r.loc["p10", "score_id"] == "s10"
    assert res.summary["n_reassigned"] == 1
    assert res.summary["n_missed"] == 0 and res.summary["n_extra"] == 0


def test_reassign_keeps_good_matches():
    """A clean performance with an extra repeated note far from its written time: no swap."""
    sn, pn, pairs, _ = build()
    y = int(sn["pitch"][12])
    pn = np.concatenate([pn, np.array([(3.2, 0.05, y, 30, "x0")], dtype=P_DTYPE)])
    pairs.append(("insertion", "", "x0"))
    res = correctness(aligned(sn, pn, pairs), reassign=True)
    assert res.summary["n_reassigned"] == 0
    assert res.notes.set_index("performance_id").loc["x0", "label"] == "extra"
    # an extra only 20 ms closer than the match (inside the 30 ms margin) does not move it
    pn2 = pn.copy()
    pn2["onset_sec"][12] += 0.04
    pn2["onset_sec"][-1] = 3.02
    res2 = correctness(aligned(sn, pn2, pairs), reassign=True)
    assert res2.summary["n_reassigned"] == 0


# --------------------------------------------------------------------------- DF-13 window rules


def _paired(res) -> bool:
    return res.notes.set_index("performance_id").loc["p10", "label"] == "wrong_pitch"


def test_window_rule_default_is_fixed():
    res = correctness(aligned(*wrong_pitch_case(1, 0.02)))
    assert res.params["wrong_pitch_window"] == "fixed"
    with pytest.raises(ValueError):
        correctness(aligned(*wrong_pitch_case(1, 0.02)), wrong_pitch_window="bogus")


@pytest.mark.parametrize(("dt", "fixed", "wide"), [(0.15, False, True), (0.19, False, True),
                                                   (0.25, False, False)])
def test_wide_window(dt, fixed, wide):
    case = wrong_pitch_case(1, dt)
    assert _paired(correctness(aligned(*case))) is fixed
    assert _paired(correctness(aligned(*case), wrong_pitch_window="wide")) is wide


def test_tempo_window_scales_with_tempo():
    """build() plays 0.5 s per quarter, so the tempo window is 0.4 x 0.5 = 0.2 s."""
    from pianolens.features.correctness import pairing_windows

    sn, pn, pairs = wrong_pitch_case(1, 0.0)
    kq = np.unique(sn["onset_quarter"]).astype(float)
    w = pairing_windows("tempo", sn["onset_quarter"], kq, 0.5 * kq, np.full(len(sn), -1),
                        pn["onset_sec"], 0.1)
    assert np.allclose(w, 0.2)
    # four times slower: 0.8 s, clipped to the 0.3 s upper limit; much faster: 0.1 s floor
    assert np.allclose(pairing_windows("tempo", sn["onset_quarter"], kq, 2.0 * kq,
                                       np.full(len(sn), -1), pn["onset_sec"], 0.1), 0.3)
    assert np.allclose(pairing_windows("tempo", sn["onset_quarter"], kq, 0.1 * kq,
                                       np.full(len(sn), -1), pn["onset_sec"], 0.1), 0.1)
    assert _paired(correctness(aligned(*wrong_pitch_case(1, 0.18)), wrong_pitch_window="tempo"))
    assert not _paired(correctness(aligned(*wrong_pitch_case(1, 0.22)),
                                   wrong_pitch_window="tempo"))


def test_error_window_follows_local_onset_error():
    """Tight playing (chord spread 12 ms) keeps the 100 ms floor; a chord nearby played 80 ms
    apart widens the window to 2 x 80 ms = 160 ms around it, but not far away."""
    case = wrong_pitch_case(1, 0.15)
    assert not _paired(correctness(aligned(*case), wrong_pitch_window="error"))
    sn, pn, pairs = wrong_pitch_case(1, 0.15)
    pn["onset_sec"][13] += 0.08  # quarter 6 (two onsets after s10): its chord-mate is 80 ms early
    res = correctness(aligned(sn, pn, pairs), wrong_pitch_window="error")
    assert _paired(res)
    assert res.params["wrong_pitch_window"] == "error"
    sn, pn, pairs = wrong_pitch_case(1, 0.15)
    pn["onset_sec"][29] += 0.08  # quarter 14: more than 3 onsets away
    assert not _paired(correctness(aligned(sn, pn, pairs), wrong_pitch_window="error"))
