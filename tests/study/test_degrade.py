"""Known-answer tests for pianolens.study.degrade and pianolens.study.excerpt (S-01)."""

from __future__ import annotations

import math

import numpy as np
import pytest

from pianolens.data import types
from pianolens.features.control import control_features
from pianolens.features.tempo import tempo_model
from pianolens.study import (
    articulation_scale,
    degrade,
    dynamics_flatten,
    excerpt,
    pedal_blur,
    tempo_flatten,
    timing_jitter,
    velocity_components,
    voicing_scale,
    wrong_notes,
)

S_DTYPE = [("onset_beat", "f8"), ("duration_beat", "f8"), ("onset_quarter", "f8"),
           ("duration_quarter", "f8"), ("pitch", "i4"), ("id", "U16"), ("is_grace", "?"),
           ("ts_beats", "i4"), ("staff", "i4"), ("voice", "i4")]  # fmt: skip
P_DTYPE = [("onset_sec", "f8"), ("duration_sec", "f8"), ("pitch", "i4"), ("velocity", "i4"),
           ("id", "U16")]  # fmt: skip


def build(notes, onset_fn, *, vel=None, dur=0.2, pedal=None, provenance="disklavier"):
    """AlignedPerformance, every note matched. ``notes``: (beat, dur_beats, pitch, staff, voice),
    4/4 with beat = quarter. Performed onset = onset_fn(beat)."""
    n = len(notes)
    sn = np.zeros(n, dtype=S_DTYPE)
    for i, (b, d, p, st, vo) in enumerate(notes):
        sn[i] = (b, d, b, d, p, f"n{i}", False, 4, st, vo)
    nbars = int(math.ceil(max(b + d for b, d, *_ in notes) / 4))
    ms = np.zeros(nbars, dtype=types.MEASURE_DTYPE)
    ms["number"] = np.arange(1, nbars + 1)
    ms["start_quarter"] = 4.0 * np.arange(nbars)
    ms["end_quarter"] = ms["start_quarter"] + 4
    score = types.Score("synth:s", types.PieceId("synth"), sn, ms)
    pn = np.zeros(n, dtype=P_DTYPE)
    pn["onset_sec"] = [onset_fn(b) for b, *_ in notes]
    pn["duration_sec"] = dur
    pn["pitch"] = [p for _, _, p, *_ in notes]
    pn["velocity"] = 64 if vel is None else np.clip(np.round(vel), 1, 127)
    pn["id"] = [f"p{i}" for i in range(n)]
    ped = np.zeros(0, types.PEDAL_DTYPE) if pedal is None else np.array(
        pedal, dtype=types.PEDAL_DTYPE)
    perf = types.Performance("synth:p", types.PieceId("synth"), types.PerformerId("synth:x"),
                             provenance, pn, ped, "synth")
    pairs = np.array([("match", f"n{i}", f"p{i}") for i in range(n)], dtype=types.ALIGNMENT_DTYPE)
    al = types.Alignment(pairs, "synth:s", "synth:p", True, "test")
    return types.AlignedPerformance(perf, score, al)


def by_id(ap):
    n = ap.performance.notes
    return {str(i): k for k, i in enumerate(n["id"])}


def eighths_with_bass(n_bars=64):
    """RH eighth notes (8 notes/s at 0.25 s per beat) over LH quarter-note chords."""
    rh = [(0.5 * k, 0.5, 72 + (k % 5), 1, 1) for k in range(8 * n_bars)]
    lh = [(float(k), 1.0, p, 2, 5) for k in range(4 * n_bars) for p in (48, 55)]
    return rh + lh


# --------------------------------------------------------------------------- timing jitter


def test_timing_jitter_known_sd_and_threshold_ratio():
    ap = build(eighths_with_bass(), lambda b: 0.25 * b)  # eighths at 8 notes/s
    r = timing_jitter(ap, sd_ms=10.0, seed=3)
    p = r.physical
    assert p["position_rate_per_s"] == pytest.approx(8.0)
    assert p["onset_shift_sd_ms"] == pytest.approx(10.0, rel=0.06)
    # neighbouring IOIs share a shift: added IOI s.d. = sqrt(2) * onset s.d.
    assert p["added_ioi_sd_ms"] == pytest.approx(10.0 * math.sqrt(2), rel=0.07)
    assert r.reference["timing_ioi_sd"]["ratio"] == pytest.approx(
        p["added_ioi_sd_ms"] / 10.22)
    assert p["added_ioi_cv"] == pytest.approx(p["added_ioi_sd_ms"] / 125.0, rel=0.02)
    # chords move together; order kept; durations unchanged
    new, old = r.performance.notes, ap.performance.notes
    ni, oi = by_id(r.aligned), by_id(ap)
    shift = {k: new["onset_sec"][ni[k]] - old["onset_sec"][oi[k]] for k in oi}
    lh = [(f"p{i}") for i, (b, _, _, st, _) in enumerate(eighths_with_bass()) if st == 2]
    for a, b in zip(lh[0::2], lh[1::2], strict=True):  # the two notes of each LH chord
        assert shift[a] == pytest.approx(shift[b])
    rh_on = np.sort([new["onset_sec"][ni[f"p{i}"]] for i in range(8 * 64)])
    assert np.all(np.diff(rh_on) > 0)
    assert np.allclose(np.sort(new["duration_sec"]), np.sort(old["duration_sec"]))


def test_timing_jitter_cv_scales_with_ioi_and_zero_is_identity():
    slow = build(eighths_with_bass(), lambda b: 0.5 * b)  # 4 notes/s
    r = timing_jitter(slow, cv=0.04, seed=1)
    assert r.physical["added_ioi_cv"] == pytest.approx(0.04 * math.sqrt(2), rel=0.08)
    assert r.physical["onset_shift_sd_ms"] == pytest.approx(0.04 * 250.0, rel=0.1)
    z = timing_jitter(slow, sd_ms=0.0)
    assert np.allclose(np.sort(z.performance.notes["onset_sec"]),
                       np.sort(slow.performance.notes["onset_sec"]))
    a = timing_jitter(slow, cv=0.04, seed=1).performance.notes["onset_sec"]
    assert np.array_equal(a, r.performance.notes["onset_sec"])  # deterministic
    with pytest.raises(ValueError):
        timing_jitter(slow)


def test_timing_jitter_moves_pedal_with_its_position_and_truncates():
    notes = [(float(k), 1.0, 60, 1, 1) for k in range(16)]
    ped = [(0.5 * k + 0.1, 64, 127 if k % 2 else 0) for k in range(16)]
    ap = build(notes, lambda b: 0.5 * b, pedal=ped)
    r = timing_jitter(ap, sd_ms=400.0, seed=0)  # huge: must be truncated at 0.45 IOI
    on = np.sort(r.performance.notes["onset_sec"])
    assert np.all(np.diff(on) > 0)
    assert r.physical["n_bound_binding"] == 16
    assert r.physical["onset_shift_sd_ms"] < 0.45 * 500
    assert np.all(np.abs(on - 0.5 * np.arange(16)) <= 0.45 * 0.5 + 1e-9)
    # each pedal event keeps its 0.1 s delay after the position it follows
    assert np.allclose(np.sort(r.performance.pedal["time_sec"]) - on, 0.1)


# --------------------------------------------------------------------------- tempo


def rit(b):
    return 0.5 * b + 0.004 * b**2  # quadratic time map: the P-spline reproduces it exactly


def test_tempo_flatten_alpha_one_gives_constant_tempo():
    notes = [(float(k), 1.0, 60 + k % 7, 1, 1) for k in range(64)]
    ap = build(notes, rit, pedal=[(rit(10.0) + 0.05, 64, 127), (rit(20.0), 64, 0)])
    r = tempo_flatten(ap, 1.0)
    on = np.sort(r.performance.notes["onset_sec"])
    assert np.allclose(np.diff(on), (rit(63) - rit(0)) / 63, atol=1e-3)
    assert on[0] == pytest.approx(0.0, abs=1e-6) and on[-1] == pytest.approx(rit(63), abs=1e-4)
    assert r.physical["tempo_log_sd_after"] == pytest.approx(0.0, abs=1e-9)
    assert r.physical["tempo_log_sd_before"] > 0.1
    # the pedal goes through the same warp: down 0.05 s after beat 10 -> still just after it
    # (a delay scales with the local tempo change: mean period / period at beat 10)
    d = r.performance.pedal["time_sec"][0] - on[10]
    assert d == pytest.approx(0.05 * ((rit(63) - rit(0)) / 63) / (0.5 + 0.008 * 10), rel=0.02)
    # alpha 0 is the identity, alpha 0.5 is halfway
    z = tempo_flatten(ap, 0.0)
    assert np.allclose(z.performance.notes["onset_sec"], ap.performance.notes["onset_sec"])
    h = np.sort(tempo_flatten(ap, 0.5).performance.notes["onset_sec"])
    orig = np.sort(ap.performance.notes["onset_sec"])
    assert np.allclose(h, 0.5 * (orig + on), atol=1e-3)


def test_tempo_flatten_keeps_residual_in_beats():
    rng = np.random.default_rng(0)
    res = rng.normal(0, 0.01, 64)
    notes = [(float(k), 1.0, 60, 1, 1) for k in range(64)]
    ap = build(notes, lambda b: rit(b) + res[int(b)])
    r = tempo_flatten(ap, 1.0)
    ids = np.array([int(i[1:]) for i in r.performance.notes["id"]])
    on = r.performance.notes["onset_sec"][np.argsort(ids)]
    # residual about the F-03 smooth curve T, in beats, is kept: after flattening,
    # onset - D(b) = (onset0 - T(b)) * mean period / T'(b) to first order
    tm = tempo_model(ap).time_map
    b = np.arange(64.0)
    t_s = tm.time(b)
    pbar = (t_s[-1] - t_s[0]) / 63
    expected = (np.array([rit(x) + res[int(x)] for x in b]) - t_s) * pbar / tm.period(b)
    got = on - (t_s[0] + b * pbar)
    assert np.max(np.abs(got - expected)) < 1e-3
    assert np.std(expected) > 0.005


# --------------------------------------------------------------------------- velocity


def melody_over_bass(n_bars=16, cresc=True):
    """Melody (RH, 72+) and bass (LH, 48) struck together each beat."""
    notes, vel = [], []
    for k in range(4 * n_bars):
        c = (20.0 * k / (4 * n_bars)) if cresc else 0.0
        notes.append((float(k), 1.0, 72 + k % 3, 1, 1))
        vel.append(80 + c)
        notes.append((float(k), 1.0, 48, 2, 5))
        vel.append(50 + c)
    return notes, np.array(vel)


def test_velocity_components_find_melody_gap():
    notes, vel = melody_over_bass(cresc=False)
    ap = build(notes, lambda b: 0.5 * b, vel=vel)
    c = velocity_components(ap)
    assert c["melody"].sum() == len(notes) // 2
    assert np.allclose(c["gap"], 30.0) and np.allclose(c["p_melody"], 0.5)
    assert np.allclose(c["D"], 0.0)


def test_dynamics_flatten_removes_crescendo_keeps_voicing():
    notes, vel = melody_over_bass(cresc=True)
    ap = build(notes, lambda b: 0.5 * b, vel=np.round(vel))
    r = dynamics_flatten(ap, 1.0)
    v = r.performance.notes["velocity"]
    mel = r.performance.notes["pitch"] >= 72
    assert np.ptp(v[mel]) <= 1 and np.ptp(v[~mel]) <= 1
    assert v[mel].mean() - v[~mel].mean() == pytest.approx(30.0, abs=1.0)
    assert r.physical["dynamics_sd_after_midi"] < 0.6
    assert r.physical["velocity_change_rms_midi"] == pytest.approx(np.std(np.round(vel[::2])),
                                                                   abs=0.6)
    half = dynamics_flatten(ap, 0.5).physical["dynamics_sd_after_midi"]
    assert half == pytest.approx(0.5 * r.physical["dynamics_sd_before_midi"], abs=0.5)


def test_voicing_zero_and_inverted_keep_mean():
    notes, vel = melody_over_bass(cresc=False)
    ap = build(notes, lambda b: 0.5 * b, vel=vel)
    z = voicing_scale(ap, 0.0)
    assert np.all(z.performance.notes["velocity"] == 65)
    assert z.physical["gap_after_midi"] == pytest.approx(0.0)
    inv = voicing_scale(ap, -1.0)
    v = inv.performance.notes["velocity"]
    mel = inv.performance.notes["pitch"] >= 72
    assert np.all(v[mel] == 50) and np.all(v[~mel] == 80)
    assert inv.physical["gap_change_midi"] == pytest.approx(60.0)
    jnd = inv.reference["velocity_jnd"]
    assert jnd["ratio_lo"] == pytest.approx(60 / 4.48) and jnd["ratio_hi"] == pytest.approx(
        60 / 2.71)
    assert np.mean(v) == pytest.approx(np.mean(vel))


def test_velocity_clipping_is_reported():
    notes, vel = melody_over_bass(cresc=False)
    vel = np.where(np.arange(len(vel)) % 2 == 0, 120, 10)
    ap = build(notes, lambda b: 0.5 * b, vel=vel)
    r = voicing_scale(ap, -2.0)
    v = r.performance.notes["velocity"]
    assert v.min() >= 1 and v.max() <= 127 and r.physical["n_clipped"] > 0


# --------------------------------------------------------------------------- pedal


def harmony_texture(reps=4):
    """reps x (I | I | IV | IV | V7 | V7 | I | I), LH Alberti eighths, RH whole notes.
    Harmony changes every 2 bars except the I -> I seam between repetitions."""
    chords = {0: (48, 55, 52), 1: (53, 60, 57), 2: (43, 50, 47), 3: (48, 55, 52)}
    rh_top = {0: 72, 1: 72, 2: 71, 3: 72}
    notes = []
    for bar in range(8 * reps):
        g = (bar % 8) // 2
        low, fifth, third = chords[g]
        for k, p in enumerate([low, fifth, third, fifth] * 2):
            notes.append((4 * bar + 0.5 * k, 0.5, p, 2, 5))
        notes.append((4.0 * bar, 4.0, rh_top[g], 1, 1))
        if g == 2:
            notes.append((4.0 * bar, 4.0, 65, 1, 1))
    return notes


def clean_pedal(n_beats):
    """Syncopated pedalling: lift 50 ms after every bar line, re-press 100 ms later."""
    ped = [(0.0, 64, 127)]
    for bar in range(1, n_beats // 4):
        t = 2.0 * bar
        ped += [(t + 0.05, 64, 0), (t + 0.15, 64, 127)]
    ped.append((0.5 * n_beats, 64, 0))
    return ped


@pytest.mark.parametrize("fraction", [0.0, 0.5, 1.0])
def test_pedal_blur_hits_target_fraction_by_the_f04_measure(fraction):
    ap = build(harmony_texture(), lambda b: 0.5 * b, pedal=clean_pedal(128))
    base = control_features(ap).summary
    n = base["n_harmony_changes"]
    assert n >= 10 and base["pedal_blur_fraction"] == 0.0
    r = pedal_blur(ap, fraction, seed=2)
    after = control_features(r.aligned).summary
    assert after["pedal_blur_fraction"] == pytest.approx(round(fraction * n) / n)
    assert r.physical["blur_fraction_after"] == pytest.approx(after["pedal_blur_fraction"])
    # notes untouched
    assert np.array_equal(np.sort(r.performance.notes["onset_sec"]),
                          np.sort(ap.performance.notes["onset_sec"]))
    if fraction == 0:
        assert len(r.performance.pedal) == len(ap.performance.pedal)


def test_pedal_blur_counts_existing_blur_and_adds_pedal_where_none():
    ap = build(harmony_texture(), lambda b: 0.5 * b)  # no pedal at all
    r = pedal_blur(ap, 1.0)
    assert r.physical["blur_fraction_before"] == 0.0
    assert r.physical["blur_fraction_after"] == 1.0
    assert control_features(r.aligned).summary["pedal_blur_fraction"] == 1.0


# --------------------------------------------------------------------------- articulation


def test_articulation_scales_durations_without_same_pitch_overlap():
    notes = [(float(k), 1.0, 60, 1, 1) for k in range(16)]  # repeated key
    ap = build(notes, lambda b: 0.5 * b, dur=0.4)
    s = articulation_scale(ap, 0.5)
    assert np.allclose(s.performance.notes["duration_sec"], 0.2)
    assert s.physical["duration_ratio_median"] == pytest.approx(0.5)
    assert s.physical["melody_kor_before"] == pytest.approx(0.8)
    assert s.physical["melody_kor_after"] == pytest.approx(0.4)
    leg = articulation_scale(ap, 3.0)
    n = leg.performance.notes
    o = np.argsort(n["onset_sec"])
    assert np.all(n["onset_sec"][o][:-1] + n["duration_sec"][o][:-1] < n["onset_sec"][o][1:])
    assert leg.physical["n_duration_cuts"] == 15


# --------------------------------------------------------------------------- wrong notes


def test_wrong_notes_change_pitch_only():
    notes = [(0.5 * k, 0.5, 60 + k % 12, 1, 1) for k in range(200)]
    ap = build(notes, lambda b: 0.25 * b)
    r = wrong_notes(ap, 0.1, seed=4)
    assert r.physical["n_wrong_pitch"] == 20 and r.physical["n_extra"] == 0
    assert r.physical["rate_per_note"] == pytest.approx(0.1)
    old = ap.performance.notes
    new = r.performance.notes
    oi, ni = by_id(ap), by_id(r.aligned)
    changed = [k for k in oi if new["pitch"][ni[k]] != old["pitch"][oi[k]]]
    assert len(changed) == 20
    for k in oi:
        assert new["onset_sec"][ni[k]] == old["onset_sec"][oi[k]]
        assert new["velocity"][ni[k]] == old["velocity"][oi[k]]
    labels = r.aligned.alignment.pairs["label"]
    assert (labels == "insertion").sum() == 20 and (labels == "deletion").sum() == 20


def test_wrong_notes_refuse_transcribed_midi():
    notes = [(0.5 * k, 0.5, 60, 1, 1) for k in range(20)]
    ap = build(notes, lambda b: 0.25 * b, provenance="transcribed")
    with pytest.raises(ValueError):
        wrong_notes(ap, 0.1)


# --------------------------------------------------------------------------- dispatcher, excerpt


def test_degrade_dispatch_and_ids():
    notes, vel = melody_over_bass(cresc=True)
    ap = build(notes, lambda b: 0.5 * b, vel=vel)
    r = degrade(ap, "timing_jitter", 8.0, unit="ms", seed=1)
    assert r.level_name == "sd_ms" and r.performance.provenance == "synthetic"
    assert r.performance.meta["degradation"]["source_performance_id"] == "synth:p"
    assert set(r.performance.notes["id"]) == set(ap.performance.notes["id"])
    assert "ratio_timing_ioi_sd" in r.summary()
    assert degrade(ap, "voicing", 0.5).level_name == "k"
    with pytest.raises(ValueError):
        degrade(ap, "loudness", 1.0)


def test_excerpt_cuts_bars_and_keeps_pedal_state():
    notes = [(float(k), 1.0, 60 + k % 5, 1, 1) for k in range(16)]  # 4 bars of quarters
    ped = [(0.0, 64, 127), (2.05, 64, 0), (2.15, 64, 127), (7.9, 64, 0)]
    ap = build(notes, lambda b: 0.5 * b, dur=0.45, pedal=ped)
    ex = excerpt(ap, 1, 2, lead_in_sec=0.25, release_sec=1.0)
    n = ex.performance.notes
    assert len(n) == 8 and n["onset_sec"].min() == pytest.approx(0.25)
    assert ex.performance.meta["excerpt"]["t_start_sec"] == pytest.approx(2.0)
    assert ex.performance.meta["excerpt"]["t_end_sec"] == pytest.approx(6.0)
    p = ex.performance.pedal
    assert p["time_sec"][0] == 0.0 and p["value"][0] == 127  # pedal already down at the cut
    assert p["value"][-1] == 0 and p["time_sec"][-1] == pytest.approx(4.0 + 0.25 + 1.0)
    assert len(ex.alignment.pairs) == 8


def test_pedal_blur_relative_to_clean_changes():
    ped = [(0.0, 64, 127), (40.0, 64, 0)] + [(t, 64, v) for bar in range(10, 32, 2)
                                             for t, v in ((2.0 * bar + 0.05, 0),
                                                          (2.0 * bar + 0.15, 127))]
    ped = sorted(ped)
    ap = build(harmony_texture(), lambda b: 0.5 * b, pedal=ped)
    r0 = pedal_blur(ap, 0.0, relative_to="clean")
    was = r0.physical["blur_fraction_before"]
    n = r0.physical["n_harmony_changes"]
    assert 0 < was < 1
    r = pedal_blur(ap, 0.5, relative_to="clean", seed=1)
    n_clean = round((1 - was) * n)
    assert r.physical["n_blurs_added"] == round(0.5 * n_clean)
    assert r.physical["added_fraction_of_clean"] == pytest.approx(round(0.5 * n_clean) / n_clean)


def test_excerpt_cut_score_restricts_harmony_and_drops_outside_matches():
    ap = build(harmony_texture(reps=1), lambda b: 0.5 * b)
    ex = excerpt(ap, 2, 5)  # IV IV V7 V7: one change inside (IV -> V7)
    assert len(ex.score.measures) == 4
    from pianolens.features.control import harmony_changes

    assert len(harmony_changes(ex.score)) == 1
    # notes of bar 6 played early would still be dropped: all kept notes map inside the bars
    kept = set(ex.performance.notes["id"].astype(str))
    assert all(pid in kept for lab, _, pid in ex.alignment.pairs.tolist() if pid)
    assert len(kept) == 4 * 9 + 2  # 8 Alberti + 1 RH per bar, + the two G7 sevenths


def test_wrong_notes_at_least_one_in_short_clips():
    notes = [(0.5 * k, 0.5, 60 + k % 12, 1, 1) for k in range(20)]
    ap = build(notes, lambda b: 0.25 * b)
    assert wrong_notes(ap, 0.01).physical["n_injected"] == 0
    r = wrong_notes(ap, 0.01, at_least_one=True)
    assert r.physical["n_injected"] == 1 and r.physical["rate_per_note"] == pytest.approx(0.05)


@pytest.mark.parametrize("hold", [0.75, 1.5])
def test_pedal_blur_hold_is_a_late_pedal_change(hold):
    ap = build(harmony_texture(), lambda b: 0.5 * b, pedal=clean_pedal(128))
    r = degrade(ap, "pedal_blur", hold, grade="hold", relative_to="clean")
    s = control_features(r.aligned).summary
    assert s["pedal_blur_fraction"] == 1.0
    assert s["pedal_blur_beats"] == pytest.approx(hold, abs=0.02)
    assert r.physical["added_hold_mean_beats"] == pytest.approx(hold, abs=0.02)


def test_pedal_blur_graded_by_hold_is_labelled_by_hold():
    """DF-04: a hold-graded stimulus must carry the hold in beats as its level, not the fraction."""
    ap = build(harmony_texture(), lambda b: 0.5 * b, pedal=clean_pedal(128))
    r = degrade(ap, "pedal_blur", 1.25, grade="hold", relative_to="clean")
    assert r.level == 1.25 and r.level_name == "hold_beats"
    assert r.summary()["level"] == 1.25 and r.summary()["level_name"] == "hold_beats"
    assert "pedal-h1.25-" in r.performance.performance_id
    f = degrade(ap, "pedal_blur", 0.5, relative_to="clean", seed=1)
    assert f.level == 0.5 and f.level_name == "fraction"
