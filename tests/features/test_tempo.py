"""Known-answer tests for pianolens.features.tempo (F-03)."""

from __future__ import annotations

import math

import numpy as np
import partitura as pt
import pytest

from pianolens.align import align_performance
from pianolens.data import types
from pianolens.features.tempo import (
    TempoConfig,
    fit_time_map,
    phrase_arcs,
    score_tempo_breaks,
    tempo_from_onsets,
    tempo_model,
)

PERF_DTYPE = [("onset_sec", "f8"), ("duration_sec", "f8"), ("pitch", "i4"),
              ("velocity", "i4"), ("id", "U32")]  # fmt: skip
SCORE_DTYPE = [("onset_beat", "f8"), ("duration_beat", "f8"), ("onset_quarter", "f8"),
               ("duration_quarter", "f8"), ("pitch", "i4"), ("id", "U32"),
               ("is_grace", "?"), ("ts_beats", "i4")]  # fmt: skip
_SPELL = {
    0: ("C", None), 1: ("C", 1), 2: ("D", None), 3: ("D", 1), 4: ("E", None), 5: ("F", None),
    6: ("F", 1), 7: ("G", None), 8: ("G", 1), 9: ("A", None), 10: ("A", 1), 11: ("B", None),
}  # fmt: skip


def melody_pitches(n, seed=0):
    """A melody with no immediate pitch repeats (keeps DTW unambiguous)."""
    rng = np.random.default_rng(seed)
    out = [60]
    while len(out) < n:
        p = int(rng.integers(55, 80))
        if p != out[-1]:
            out.append(p)
    return out


# --------------------------------------------------------------------------- builders


def manual_ap(beats, onsets, *, pitches=None, grace=(), interpolated=(), beats_per_bar=4):
    """AlignedPerformance built by hand (no partitura, no DTW): note i <-> performed note i.

    ``beats`` are score beats (4/4, beat = quarter), ``onsets`` performed seconds.
    """
    n = len(beats)
    pitches = melody_pitches(n) if pitches is None else pitches
    sn = np.zeros(n, dtype=SCORE_DTYPE)
    sn["onset_beat"] = beats
    sn["onset_quarter"] = beats
    sn["duration_beat"] = sn["duration_quarter"] = 0.5
    sn["pitch"] = pitches
    sn["id"] = [f"n{i}" for i in range(n)]
    sn["is_grace"] = [i in grace for i in range(n)]
    sn["ts_beats"] = beats_per_bar
    lo = math.floor(min(beats) / beats_per_bar) * beats_per_bar
    starts = np.arange(lo, max(beats) + 1e-9, beats_per_bar)
    ms = np.zeros(len(starts), dtype=types.MEASURE_DTYPE)
    ms["number"] = np.arange(len(starts)) + (0 if lo < 0 else 1)
    ms["start_quarter"] = starts
    ms["end_quarter"] = starts + beats_per_bar
    score = types.Score("synth:s", types.PieceId("synth"), sn, ms)
    pn = np.zeros(n, dtype=PERF_DTYPE)
    pn["onset_sec"] = onsets
    pn["duration_sec"] = 0.2
    pn["pitch"] = pitches
    pn["velocity"] = 64
    pn["id"] = [f"p{i}" for i in range(n)]
    perf = types.Performance("synth:p", types.PieceId("synth"), types.PerformerId("synth:x"),
                             "synthetic", pn, np.zeros(0, types.PEDAL_DTYPE), "synth")
    rows = [("interpolated" if i in interpolated else "match", f"n{i}", f"p{i}")
            for i in range(n)]
    al = types.Alignment(np.array(rows, dtype=types.ALIGNMENT_DTYPE), "synth:s", "synth:p",
                         False, "test")
    return types.AlignedPerformance(perf, score, al)


def make_part(pitches, *, step_q=0.5, quarter=4, extras=()):
    """Melody part, one note every ``step_q`` quarters, 4/4. ``extras``: (obj, onset_q)."""
    part = pt.score.Part("P0", "piano", quarter_duration=quarter)
    part.add(pt.score.TimeSignature(4, 4), 0)
    d = int(step_q * quarter)
    for i, p in enumerate(pitches):
        step, alter = _SPELL[p % 12]
        note = pt.score.Note(step=step, octave=p // 12 - 1, alter=alter, id=f"n{i}", voice=1)
        part.add(note, start=i * d, end=(i + 1) * d)
    for obj, onset_q in extras:
        part.add(obj, int(onset_q * quarter))
    pt.score.add_measures(part)
    return part


def aligned(part, onsets, pitches):
    score = types.score_from_partitura(part, score_id="synth:s",
                                       piece_id=types.PieceId("synth"), keep_part=True)
    pn = np.zeros(len(onsets), dtype=PERF_DTYPE)
    pn["onset_sec"] = onsets
    pn["duration_sec"] = 0.2
    pn["pitch"] = pitches
    pn["velocity"] = 64
    pn["id"] = [f"p{i}" for i in range(len(onsets))]
    perf = types.Performance("synth:p", types.PieceId("synth"), types.PerformerId("synth:x"),
                             "synthetic", pn, np.zeros(0, types.PEDAL_DTYPE), "synth")
    return align_performance(score, perf)


EIGHTHS = np.arange(0, 64, 0.5)  # 16 bars of eighth notes, in quarter beats


# --------------------------------------------------------------------------- known answers


def test_deadpan_end_to_end_zero_jitter():
    pitches = melody_pitches(len(EIGHTHS))
    ap = aligned(make_part(pitches), EIGHTHS * 0.5, pitches)  # 120 BPM
    tc = tempo_model(ap)
    s = tc.summary
    assert s["n_match"] == len(EIGHTHS) and s["n_positions"] == len(EIGHTHS)
    assert s["tempo_bpm_geomean"] == pytest.approx(120, abs=1e-6)
    assert s["tempo_bpm_overall"] == pytest.approx(120, abs=1e-6)
    assert s["jitter_rms_ms"] < 1e-3 and s["jitter_mad_ms"] < 1e-3
    assert s["tempo_log_sd"] < 1e-6
    assert s["n_outliers"] == 0 and s["n_segments"] == 1
    # per-bar output: 16 bars, flat tempo, no jitter
    assert len(tc.bars) == 16
    assert tc.bars["tempo_bpm"].to_numpy() == pytest.approx(np.full(16, 120), abs=1e-6)
    assert tc.bars["jitter_rms_ms"].max() < 1e-3
    assert list(tc.bars["measure_number"]) == list(range(1, 17))
    # beat grid and per-note table
    assert list(tc.beats["beat"]) == list(range(64))
    assert tc.notes["dev_sec"].abs().max() < 1e-6
    bc = tc.to_beat_curve(ap.performance)
    assert len(bc) == 64 and np.allclose(bc.tempo_bpm, 120)


def test_constant_ritardando_is_recovered_by_the_smooth_curve():
    b = np.arange(0, 128, 0.5)
    length = 128.0
    t = 0.5 * b + 0.2 * b**2 / length  # beat period 0.5 -> 0.9 s linearly
    tc = tempo_from_onsets(b, t)
    p_true = 0.5 + 0.4 * b / length
    assert tc.positions["beat_period_sec"].to_numpy() == pytest.approx(p_true, abs=1e-5)
    assert tc.summary["jitter_rms_ms"] < 0.01
    assert tc.summary["n_tempo_steps"] == 0 and tc.summary["n_segments"] == 1
    # the smooth log tempo spans log(0.9 / 0.5)
    lr = tc.beats["tempo_log_ratio"]
    assert lr.max() - lr.min() == pytest.approx(math.log(0.9 / 0.5), abs=0.02)


@pytest.mark.parametrize("seed", [0, 1, 2])
def test_injected_20ms_noise_gives_20ms_jitter(seed):
    rng = np.random.default_rng(seed)
    b = np.arange(0, 256, 0.5)
    ap = manual_ap(b, 0.5 * b + rng.normal(0, 0.020, len(b)))
    s = tempo_model(ap).summary
    assert 17 <= s["jitter_rms_ms"] <= 23
    assert 0.034 <= s["jitter_rms_beats"] <= 0.046  # 20 ms / 500 ms beat
    assert s["tempo_bpm_geomean"] == pytest.approx(120, rel=0.01)
    assert s["n_outliers"] <= 3


def test_step_tempo_change_is_detected_and_split_on_request():
    b = np.arange(0, 128, 0.5)
    t = np.where(b < 64, b * 1.0, 64 + (b - 64) * (60 / 90))  # 60 -> 90 BPM at beat 64
    tc = tempo_from_onsets(b, t)
    steps = tc.breaks[tc.breaks["kind"] == "tempo_step"]
    assert len(steps) == 1
    assert steps["beat"].iloc[0] == 64
    assert steps["log_ratio"].iloc[0] == pytest.approx(math.log(60 / 90), abs=1e-6)
    assert steps["type"].iloc[0] == "none"  # reported only, by default
    split = tempo_from_onsets(b, t, config=TempoConfig(split_on_steps=True))
    g = split.beats.set_index("beat")["tempo_bpm"]
    assert g.loc[:63].to_numpy() == pytest.approx(60, abs=1e-4)
    assert g.loc[64:].to_numpy() == pytest.approx(90, abs=1e-4)
    assert split.summary["jitter_rms_ms"] < 0.01
    assert split.summary["jitter_rms_ms"] < tc.summary["jitter_rms_ms"]


def test_step_with_noise_still_detected():
    rng = np.random.default_rng(5)
    b = np.arange(0, 128, 0.5)
    t = np.where(b < 64, b * 1.0, 64 + (b - 64) * (60 / 90)) + rng.normal(0, 0.02, len(b))
    steps = tempo_from_onsets(b, t).breaks.query("kind == 'tempo_step'")
    assert len(steps) == 1 and abs(steps["beat"].iloc[0] - 64) <= 1


def test_score_tempo_marking_splits_the_curve():
    n = 128
    pitches = melody_pitches(n)
    part = make_part(pitches, extras=[(pt.score.ConstantTempoDirection("più mosso",
                                                                       "più mosso"), 32)])
    b = np.arange(n) * 0.5
    onsets = np.where(b < 32, b * 1.0, 32 + (b - 32) * (60 / 90))
    ap = aligned(part, onsets, pitches)
    marks = score_tempo_breaks(ap.score)
    assert list(marks["kind"]) == ["tempo_marking"] and marks["beat"].iloc[0] == 32
    tc = tempo_model(ap)
    br = tc.breaks.query("kind == 'tempo_marking'")
    assert len(br) == 1 and br["beat"].iloc[0] == 32 and br["type"].iloc[0] == "kink"
    g = tc.beats.set_index("beat")["tempo_bpm"]
    assert g.loc[:31].to_numpy() == pytest.approx(60, abs=1e-3)
    assert g.loc[32:].to_numpy() == pytest.approx(90, abs=1e-3)
    assert tc.summary["jitter_rms_ms"] < 0.01


def test_non_tempo_words_are_not_breaks():
    part = make_part(melody_pitches(16), extras=[
        (pt.score.ConstantTempoDirection("tenuto", "ten."), 2),
        (pt.score.DecreasingTempoDirection("ritardando", "rit."), 4),
    ])
    score = types.score_from_partitura(part, score_id="s", piece_id=types.PieceId("s"),
                                       keep_part=True)
    assert len(score_tempo_breaks(score)) == 0


@pytest.mark.parametrize("marked", [True, False])
def test_fermata_or_pause_is_a_gap_not_a_tempo_dip(marked):
    n = 128
    pitches = melody_pitches(n)
    hold_at = 60  # note index held; beat 30
    extras = [(pt.score.Fermata(), hold_at * 0.5)] if marked else []
    part = make_part(pitches, extras=extras)
    onsets = np.arange(n) * 0.5 * 0.5
    onsets[hold_at + 1:] += 1.2  # held 1.2 s extra
    tc = tempo_model(aligned(part, onsets, pitches))
    gaps = tc.breaks.query("type == 'gap'")
    assert len(gaps) == 1
    assert gaps["kind"].iloc[0] == ("fermata" if marked else "pause")
    assert gaps["beat"].iloc[0] == 30
    assert gaps["excess_sec"].iloc[0] == pytest.approx(1.2, abs=1e-6)
    assert tc.summary["jitter_rms_ms"] < 0.01
    assert tc.beats["tempo_bpm"].to_numpy() == pytest.approx(120, abs=1e-3)
    assert tc.summary["tempo_bpm_overall"] < 120  # the hold is in the overall figure only


def test_gross_misalignment_is_flagged_and_ignored():
    b = np.arange(0, 64, 0.5)
    t = 0.5 * b
    t[40] += 0.4  # e.g. a note matched to the wrong performed note
    tc = tempo_from_onsets(b, t)
    pos = tc.positions
    assert bool(pos.loc[40, "outlier"]) and bool(pos.loc[40, "gross_outlier"])
    assert pos["outlier"].sum() == 1
    assert tc.summary["jitter_rms_ms"] < 0.01
    assert tc.beats["tempo_bpm"].to_numpy() == pytest.approx(120, abs=1e-3)
    assert pos.loc[40, "dev_sec"] == pytest.approx(0.4, abs=1e-6)


def test_chords_collapse_to_median_and_offsets_are_kept():
    beats = np.repeat(np.arange(0, 32, 1.0), 3)
    onsets = 0.5 * beats
    onsets[1::3] += 0.030  # one late chord note per chord
    tc = tempo_from_onsets(beats, onsets)
    assert tc.summary["n_positions"] == 32
    assert tc.summary["jitter_rms_ms"] < 0.01
    assert tc.positions["chord_spread_sec"].to_numpy() == pytest.approx(0.030)
    assert tc.notes["chord_offset_sec"].max() == pytest.approx(0.030)


def test_grace_interpolated_and_unmatched_are_skipped_and_counted():
    b = np.arange(0, 32, 0.5)
    t = 0.5 * b
    t[10] += 0.3  # grace note: timing irrelevant
    t[20] += 0.3  # interpolated pair: not played
    ap = manual_ap(b, t, grace={10}, interpolated={20})
    # add an insertion and a deletion
    extra = np.array([("insertion", "", "p999"), ("deletion", "n5", "")],
                     dtype=types.ALIGNMENT_DTYPE)
    ap.alignment.pairs = np.concatenate([ap.alignment.pairs, extra])
    s = tempo_model(ap).summary
    assert s["n_grace_skipped"] == 1
    assert s["n_interpolated_skipped"] == 1
    assert s["n_insertion"] == 1 and s["n_deletion"] == 1
    assert s["n_notes_used"] == len(b) - 2
    assert s["jitter_rms_ms"] < 0.01 and s["n_outliers"] == 0


def test_pickup_bar_negative_beats():
    b = np.arange(-1, 32, 0.5)  # one-beat anacrusis
    ap = manual_ap(b, 0.5 * (b + 1))
    tc = tempo_model(ap)
    assert tc.beats["beat"].iloc[0] == -1
    assert tc.bars["measure_number"].iloc[0] == 0  # pickup bar
    assert tc.positions.loc[0, "beat_in_bar"] == 3  # last beat of the pickup bar
    assert tc.summary["tempo_bpm_geomean"] == pytest.approx(120, abs=1e-6)


def test_metric_profile_captures_bar_periodic_pattern():
    rng = np.random.default_rng(7)
    b = np.arange(0, 128, 0.5)
    t = 0.5 * b + np.where(b % 4 == 1, 0.035, 0.0) + rng.normal(0, 0.010, len(b))
    tc = tempo_model(manual_ap(b, t))  # beat 2 of every bar 35 ms late, plus 10 ms noise
    prof = tc.metric_profile.set_index("beat_in_bar")["dev_metric_beats"]
    # 0.07 beat late; a 1.5-bar cutoff lets the smooth curve absorb under 10% of it
    assert prof.loc[1.0] == pytest.approx(0.07, abs=0.015)
    assert prof.drop(1.0).abs().max() < 0.03
    assert tc.summary["jitter_rms_ms"] > 13
    assert 8 <= tc.summary["jitter_nometric_rms_ms"] <= 13


@pytest.mark.parametrize(("period", "lo", "hi"), [(8, 0.35, 0.6), (16, 0.97, 1.01),
                                                  (4, 0.0, 0.02)])
def test_cutoff_sets_the_half_gain_period(period, lo, hi):
    b = np.arange(0, 400, 0.25)
    pert = 0.02 * np.sin(2 * np.pi * b / period)
    tmap, _ = fit_time_map(b, 0.5 * b + pert, period_beats=8, robust_iterations=0)
    m = (b > 50) & (b < 350)
    gain = np.std(tmap.time(b)[m] - 0.5 * b[m]) / np.std(pert[m])
    assert lo <= gain <= hi


def test_gcv_smoothing_on_pure_noise_is_smooth():
    rng = np.random.default_rng(3)
    b = np.arange(0, 256, 0.5)
    tc = tempo_from_onsets(b, 0.5 * b + rng.normal(0, 0.02, len(b)),
                           config=TempoConfig(smoothing="gcv"))
    assert tc.summary["smoothing"] == "gcv"
    assert tc.summary["cutoff_beats"] > 16
    assert 17 <= tc.summary["jitter_rms_ms"] <= 23


def test_phrase_arcs_recover_parabolas():
    b = np.arange(0, 64, 0.25)
    u = (b % 32) / 32 * 2 - 1  # two 32-beat phrases
    period = 0.5 * np.exp(0.2 * u**2)  # slower at phrase edges, faster in the middle
    t = np.concatenate([[0], np.cumsum(period[:-1] * np.diff(b))])
    tc = tempo_from_onsets(b, t, config=TempoConfig(cutoff_beats=4))
    arcs = phrase_arcs(tc, [0, 32])
    assert len(arcs) == 2
    assert (arcs["r2"] > 0.9).all()
    assert (arcs["c2"] < -0.1).all()  # log tempo is an inverted parabola


def test_tiny_and_degenerate_inputs_do_not_crash():
    for b, t in [([0.0], [1.0]), ([0.0, 1.0], [0.0, 0.5]), ([0.0, 0.5, 1.0], [0, 0.2, 0.5])]:
        tc = tempo_from_onsets(np.array(b), np.array(t))
        assert tc.summary["n_positions"] == len(b)
    with pytest.raises(ValueError):
        tempo_from_onsets(np.array([]), np.array([]))


def test_penalized_fit_survives_cholesky_failure(monkeypatch):
    """DF-01: a non-positive-definite normal matrix must not crash the fit."""
    import numpy as np

    from pianolens.features import tempo as tempo_mod

    real = tempo_mod.cho_factor
    calls = {"n": 0}

    def flaky(a, *args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise np.linalg.LinAlgError("potrf")
        return real(a, *args, **kwargs)

    monkeypatch.setattr(tempo_mod, "cho_factor", flaky)
    x = np.arange(0.0, 64.0)
    y = 0.5 * x
    seg, hat = tempo_mod._penalized_fit(x, y, np.ones_like(x), 1.0, None, 6.0)
    assert np.all(np.isfinite(hat))
    assert calls["n"] == 2

    def always_fail(a, *args, **kwargs):
        raise np.linalg.LinAlgError("potrf")

    monkeypatch.setattr(tempo_mod, "cho_factor", always_fail)
    seg, hat = tempo_mod._penalized_fit(x, y, np.ones_like(x), 1.0, None, 6.0)
    assert np.all(np.isfinite(hat))
