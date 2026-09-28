"""Known-answer tests for pianolens.features.control (F-04, tier B)."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from pianolens.data import types
from pianolens.features.control import (
    ControlConfig,
    control_features,
    even_runs,
    fine_timing_consensus,
    harmony_changes,
    reference_residuals,
    strict_runs,
)
from pianolens.features.tempo import tempo_model

S_DTYPE = [("onset_beat", "f8"), ("duration_beat", "f8"), ("onset_quarter", "f8"),
           ("duration_quarter", "f8"), ("pitch", "i4"), ("id", "U16"), ("is_grace", "?"),
           ("ts_beats", "i4"), ("staff", "i4"), ("voice", "i4")]  # fmt: skip
P_DTYPE = [("onset_sec", "f8"), ("duration_sec", "f8"), ("pitch", "i4"), ("velocity", "i4"),
           ("id", "U16")]  # fmt: skip


def build(notes, onset_fn, *, vel=None, offsets=None, pedal=None, pid="synth:p"):
    """Manual AlignedPerformance, every note matched. ``notes``: (beat, dur, pitch, staff, voice).

    4/4, beat = quarter. Performed onset of note i = onset_fn(beat_i) + offsets[i].
    """
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
    if offsets is not None:
        pn["onset_sec"] += offsets
    pn["duration_sec"] = 0.2
    pn["pitch"] = [p for _, _, p, *_ in notes]
    pn["velocity"] = 64 if vel is None else np.clip(np.round(vel), 1, 127)
    pn["id"] = [f"p{i}" for i in range(n)]
    ped = np.zeros(0, types.PEDAL_DTYPE) if pedal is None else np.array(
        pedal, dtype=types.PEDAL_DTYPE)
    perf = types.Performance(pid, types.PieceId("synth"), types.PerformerId("synth:x"),
                             "synthetic", pn, ped, "synth")
    pairs = np.array([("match", f"n{i}", f"p{i}") for i in range(n)], dtype=types.ALIGNMENT_DTYPE)
    al = types.Alignment(pairs, "synth:s", pid, False, "test")
    return types.AlignedPerformance(perf, score, al)


def scale_texture(n_bars=16):
    """RH eighth-note scale (staff 1, voice 1) over LH quarter notes (staff 2, voice 5)."""
    rh = [(0.5 * k, 0.5, 60 + (k % 15), 1, 1) for k in range(8 * n_bars)]
    lh = [(float(k), 1.0, 36 + (k % 7), 2, 5) for k in range(4 * n_bars)]
    return rh + lh


def rit(b):
    """Linear ritardando: beat period 0.5 s -> about 0.66 s over 64 beats (quadratic time map)."""
    return 0.5 * b + 0.00125 * b**2


# --------------------------------------------------------------------------- evenness


def test_even_runs_detects_scale_and_not_across_rests():
    notes = [(0.5 * k, 0.5, 60 + k, 1, 1) for k in range(8)]  # 8 eighths
    notes += [(6.0 + 0.5 * k, 0.5, 70 + k, 1, 1) for k in range(5)]  # after a rest, only 5
    notes += [(float(k), 1.0, 40, 2, 5) for k in range(4)]  # 4 quarters: too short
    ap = build(notes, lambda b: 0.5 * b)
    r = even_runs(ap.score, min_notes=6)
    assert r["run"].nunique() == 1
    assert len(r) == 8 and set(r["staff"]) == {1}


def test_perfectly_even_scale_under_ritardando_has_zero_cv():
    ap = build(scale_texture(), rit)
    res = control_features(ap)
    s = res.summary
    assert s["even_n_runs"] == 2  # the RH scale and the LH quarters
    assert s["even_ioi_cv"] < 1e-4
    assert s["even_vel_sd_midi"] < 1e-9
    assert res.bars["even_ioi_cv"].max() < 1e-4
    assert len(res.bars) == 16


def test_note_rate_reported_per_run_bar_and_summary():
    # RH eighths every 0.25 s (4 notes/s), LH quarters every 0.5 s (2 notes/s)
    res = control_features(build(scale_texture(), lambda b: 0.5 * b))
    rates = res.runs.set_index("staff")["note_rate_nps"]
    assert rates[1] == pytest.approx(4.0) and rates[2] == pytest.approx(2.0)
    # bar 1: 8 RH IOIs of 0.25 s + 4 LH IOIs of 0.5 s -> 12 IOIs in 4 s
    assert res.bars.loc[0, "even_note_rate_nps"] == pytest.approx(3.0)
    assert res.bars.loc[0, "even_n_iois"] == 12
    s = res.summary
    assert s["even_note_rate_nps"] == pytest.approx((127 + 63) / (127 * 0.25 + 63 * 0.5))
    assert s["even_strict_note_rate_nps"] == pytest.approx(4.0)  # LH quarters are not sub-beat


def test_injected_velocity_noise_recovered_over_crescendo():
    notes = scale_texture()
    rng = np.random.default_rng(1)
    vel = np.full(len(notes), 64.0)
    n_rh = 8 * 16
    vel[:n_rh] = np.linspace(40, 100, n_rh) + rng.normal(0, 6, n_rh)  # crescendo + noise
    ap = build(notes, rit, vel=vel)
    res = control_features(ap)
    rh = res.runs[res.runs["staff"] == 1].iloc[0]
    assert rh["vel_sd_midi"] == pytest.approx(6, rel=0.2)
    lh = res.runs[res.runs["staff"] == 2].iloc[0]
    assert lh["vel_sd_midi"] < 1e-9  # constant 64, no trend
    assert res.summary["even_ioi_cv"] < 1e-4  # timing untouched


def test_injected_timing_noise_gives_expected_cv():
    notes = scale_texture()
    rng = np.random.default_rng(2)
    off = np.zeros(len(notes))
    n_rh = 8 * 16
    off[:n_rh] = rng.normal(0, 0.01, n_rh)  # 10 ms onset noise on the RH scale
    ap = build(notes, lambda b: 0.5 * b, offsets=off)
    res = control_features(ap)
    rh = res.runs[res.runs["staff"] == 1].iloc[0]
    # IOI noise SD = sqrt(2) * 10 ms over a 250 ms IOI
    assert rh["ioi_cv"] == pytest.approx(math.sqrt(2) * 0.01 / 0.25, rel=0.2)


def strict_texture():
    """Four 8-eighth streams in bars 1-2 plus a quarter-note scale:

    staff 1 voice 1: a rising scale (monotone), bar 1; then a zigzag melody (not strict), bar 3.
    staff 2 voice 5: Alberti C-G-E-G twice (figure, period 4), bar 1.
    staff 2 voice 6: repeated-note bass, 8 x C2 (figure, period 1), bar 3.
    staff 1 voice 2: a rising quarter-note scale, 8 notes from bar 5 (broad only: not sub-beat).
    """
    scale = [(0.5 * k, 0.5, 60 + 2 * k, 1, 1) for k in range(8)]
    zigzag = [(8 + 0.5 * k, 0.5, p, 1, 1)
              for k, p in enumerate([60, 64, 62, 65, 61, 67, 63, 60])]
    alberti = [(0.5 * k, 0.5, p, 2, 5) for k, p in enumerate([48, 55, 52, 55] * 2)]
    drum = [(8 + 0.5 * k, 0.5, 36, 2, 6) for k in range(8)]
    slow = [(16.0 + k, 1.0, 60 + 2 * k, 1, 2) for k in range(8)]
    return scale + zigzag + alberti + drum + slow


def test_strict_runs_keep_scales_and_figures_only():
    ap = build(strict_texture(), lambda b: 0.5 * b)
    broad = even_runs(ap.score, min_notes=6)
    # broad: scale, zigzag (after a rest), Alberti, drum, slow: five runs of 8
    assert sorted(broad.groupby("run").size()) == [8] * 5
    r = strict_runs(ap.score, min_notes=6)
    got = {(int(st), int(vo), k, len(g))
           for (st, vo, k), g in r.groupby(["staff", "voice", "kind"])}
    assert got == {(1, 1, "monotone", 8), (2, 5, "figure", 8), (2, 6, "figure", 8)}


def test_strict_evenness_ignores_noise_outside_strict_runs():
    notes = strict_texture()
    off = np.zeros(len(notes))
    rng = np.random.default_rng(3)
    off[8:16] = rng.normal(0, 0.02, 8)  # 20 ms noise on the zigzag melody only
    res = control_features(build(notes, lambda b: 0.5 * b, offsets=off))
    s = res.summary
    assert s["even_strict_n_runs"] == 3 and s["even_n_runs"] == 5
    # strict runs are played evenly; the only trace of the zigzag noise is through the smooth
    # time map (the drum bass shares its beats), about 1% of the zigzag's own IOI CV (~0.11)
    assert s["even_strict_ioi_cv"] < 0.005
    assert s["even_ioi_cv"] > 0.02  # the broad rule sees the zigzag noise
    assert s["even_strict_share_of_onsets"] < s["even_share_of_onsets"]
    assert set(res.strict_runs["kind"]) == {"monotone", "figure"}
    b = res.bars
    assert b.loc[0, "even_strict_n_iois"] > 0 and b.loc[0, "even_strict_ioi_cv"] < 0.005
    assert b.loc[4:5, "even_strict_n_iois"].sum() == 0 and b.loc[4:5, "even_n_iois"].sum() > 0


def test_strict_scale_texture_is_one_long_monotone_run():
    res = control_features(build(scale_texture(), rit))
    sr = res.strict_runs
    assert len(sr) == 1 and sr.iloc[0]["n_onsets"] == 8 * 16 and sr.iloc[0]["kind"] == "monotone"
    assert res.summary["even_strict_ioi_cv"] < 1e-4


# --------------------------------------------------------------------------- synchrony


def test_constant_left_hand_lead_and_velocity_artifact():
    notes = scale_texture(8)
    is_lh = np.array([st == 2 for _, _, _, st, _ in notes])
    # LH leads by 20 ms everywhere, equal velocities
    off = np.where(is_lh, -0.02, 0.0)
    res = control_features(build(notes, lambda b: 0.5 * b, offsets=off))
    s = res.summary
    assert s["n_cross_staff_onsets"] == 32
    assert s["hand_async_mean_ms"] == pytest.approx(20, abs=1e-6)
    assert s["hand_async_resid_sd_ms"] < 1e-6
    assert s["hand_async_equalvel_sd_ms"] < 1e-6 and s["n_equalvel_onsets"] == 32
    assert res.bars["hand_async_mean_ms"].to_numpy() == pytest.approx(np.full(8, 20))
    # Velocity artifact: RH louder by dv -> RH earlier by 2 ms per velocity unit
    rng = np.random.default_rng(3)
    vel = np.full(len(notes), 60.0)
    q = np.array([b for b, *_ in notes])
    dv_by_q = {x: float(rng.integers(0, 30)) for x in np.unique(q)}
    rh_dv = np.array([dv_by_q[x] for x in q])
    vel = np.where(is_lh, 60.0, 60.0 + rh_dv)
    off = np.where(is_lh, 0.0, -0.002 * rh_dv)
    res = control_features(build(notes, lambda b: 0.5 * b, vel=vel, offsets=off))
    s = res.summary
    assert s["hand_async_vel_slope_ms"] == pytest.approx(-2.0, abs=1e-6)
    assert s["hand_async_resid_sd_ms"] < 1e-6
    assert s["hand_async_sd_ms"] > 5


# --------------------------------------------------------------------------- timing noise


def test_consensus_leave_one_out():
    a = pd.Series([0.1, 0.2, np.nan], index=[0.0, 1.0, 2.0])
    b = pd.Series([0.3, 0.4, 0.5], index=[0.0, 1.0, 2.0])
    c = pd.Series([0.5, 0.6, 0.7], index=[0.0, 1.0, 2.0])
    cons = fine_timing_consensus({"a": a, "b": b, "c": c}, leave_out="c", min_references=2)
    assert cons["consensus_beats"].tolist()[:2] == pytest.approx([0.2, 0.3])
    assert np.isnan(cons["consensus_beats"].iloc[2])  # only 1 reference left there
    assert cons["n_refs"].tolist() == [2, 2, 1]


def test_timing_noise_removes_shared_fine_timing():
    notes = [(0.5 * k, 0.5, 60 + (k % 12), 1, 1) for k in range(8 * 16)]
    beats = np.array([b for b, *_ in notes])
    rng = np.random.default_rng(4)
    shared = rng.normal(0, 0.03, len(notes))  # shared fine timing (s), same for everyone
    refs = {}
    for r in range(30):
        ap_r = build(notes, lambda b: 0.5 * b, offsets=shared + rng.normal(0, 0.003, len(notes)),
                     pid=f"ref{r}")
        refs[f"ref{r}"] = reference_residuals(tempo_model(ap_r))
    target = build(notes, lambda b: 0.5 * b, offsets=shared + rng.normal(0, 0.01, len(notes)))
    refs["synth:p"] = pd.Series(0.0, index=beats)  # the target itself: must be left out
    res = control_features(target, references=refs)
    s = res.summary
    assert s["timing_noise_source"] == "consensus"
    assert s["timing_noise_coverage"] > 0.95
    assert s["timing_noise_n_refs_median"] == 30
    # 10 ms of own noise; the shared 30 ms pattern is removed
    assert s["timing_noise_rms_ms"] == pytest.approx(10, rel=0.2)
    assert s["jitter_nometric_rms_ms"] > 25
    assert s["timing_consensus_r2"] > 0.8
    assert res.bars["timing_noise_rms_ms"].notna().all()
    # no references: fallback
    s0 = control_features(target).summary
    assert s0["timing_noise_source"] == "nometric"
    assert s0["timing_noise_best_rms_ms"] == s0["jitter_nometric_rms_ms"]
    assert np.isnan(s0["timing_noise_rms_ms"])


# --------------------------------------------------------------------------- stability


def modulated_onsets(amp, period_beats, n_beats=64, p0=0.5):
    """Onset function for beat period p0 * exp(-amp * sin(2 pi b / period))."""
    fine = np.linspace(0, n_beats + 1, 20001)
    per = p0 * np.exp(-amp * np.sin(2 * np.pi * fine / period_beats))
    t = np.concatenate([[0], np.cumsum(0.5 * (per[1:] + per[:-1]) * np.diff(fine))])
    return lambda b: float(np.interp(b, fine, t))


def test_tempo_stability_constant_vs_wobble_vs_arc():
    notes = [(0.5 * k, 0.5, 60 + (k % 12), 1, 1) for k in range(8 * 16)]
    flat = control_features(build(notes, lambda b: 0.5 * b)).summary
    assert flat["tempo_instability_log_sd"] < 1e-6
    assert flat["n_stability_sections"] == 1
    amp = 0.1
    wobble = control_features(build(notes, modulated_onsets(amp, 8.0)))  # 2-bar wobble
    arc = control_features(build(notes, modulated_onsets(amp, 32.0)))  # 8-bar arc
    w, a = wobble.summary, arc.summary
    # the 2-bar wobble mostly passes the 1.5-bar curve and is outside the 4-bar allowance
    assert w["tempo_instability_log_sd"] > 0.5 * amp / math.sqrt(2)
    assert a["tempo_instability_log_sd"] < 0.2 * amp / math.sqrt(2)
    assert w["tempo_instability_log_sd"] > 5 * a["tempo_instability_log_sd"]
    assert a["tempo_phrase_log_sd"] > 0.8 * amp / math.sqrt(2)
    assert wobble.bars["tempo_instability_log_rms"].notna().sum() >= 14


# --------------------------------------------------------------------------- pedal


def harmony_texture():
    """8 bars: I (C) | I | IV (F) | IV | V7 (G) | V7 | I | I; LH Alberti eighths, RH whole
    notes. Harmony changes at beats 8, 16 and 24."""
    chords = {0: (48, 55, 52), 1: (53, 60, 57), 2: (43, 50, 47), 3: (48, 55, 52)}
    rh_top = {0: 72, 1: 72, 2: 71, 3: 72}
    notes = []
    for bar in range(8):
        c = chords[bar // 2]
        low, fifth, third = c
        for k, p in enumerate([low, fifth, third, fifth] * 2):
            notes.append((4 * bar + 0.5 * k, 0.5, p, 2, 5))
        notes.append((4.0 * bar, 4.0, rh_top[bar // 2], 1, 1))
        if bar // 2 == 2:
            notes.append((4.0 * bar, 4.0, 65, 1, 1))  # the seventh of G7
    return notes


def test_harmony_changes_ignore_alberti_within_a_chord():
    ap = build(harmony_texture(), lambda b: 0.5 * b)
    ch = harmony_changes(ap.score)
    assert ch["beat"].tolist() == [8.0, 16.0, 24.0]
    assert ch["measure_idx"].tolist() == [2, 4, 6]


def test_harmony_window_is_a_quarter_note_in_alla_breve():
    """2/2 (beat = half note): C and G block triads alternate every quarter for 4 bars."""
    notes = []
    for k in range(16):
        chord = (48, 52, 55) if k % 2 == 0 else (43, 47, 50)
        notes += [(float(k), 1.0, p, 2, 5) for p in chord]
    ap = build(notes, lambda b: 0.5 * b)
    sn = ap.score.notes
    sn["onset_beat"] /= 2  # re-meter as 2/2: beats are half notes
    sn["duration_beat"] /= 2
    ch = harmony_changes(ap.score)
    assert len(ch) == 15 and ch["quarter"].tolist() == [float(k) for k in range(1, 16)]
    assert len(harmony_changes(ap.score, unit="beat")) == 0  # the F-04 rule: one blend per beat


def test_functional_templates_do_not_merge_tonic_and_dominant():
    """Incomplete I (C-E) then incomplete V (G-B): the union is C-E-G-B, a major 7th."""
    notes = [(float(k), 1.0, p, 2, 5) for k in range(0, 8, 2) for p in (48, 52)]
    notes += [(float(k), 1.0, p, 2, 5) for k in range(1, 8, 2) for p in (43, 47)]
    ap = build(notes, lambda b: 0.5 * b)
    assert len(harmony_changes(ap.score)) == 7
    assert len(harmony_changes(ap.score, templates="all")) == 0


def test_pedal_blur_held_vs_changed_vs_absent():
    notes = harmony_texture()
    held = [(0.0, 64, 127), (40.0, 64, 0)]  # down all through
    res = control_features(build(notes, lambda b: 0.5 * b, pedal=held))
    s = res.summary
    assert s["pedal_available"] and s["n_harmony_changes"] == 3
    assert s["pedal_blur_fraction"] == 1.0
    assert s["pedal_blur_beats"] == pytest.approx(4.0)  # capped at pedal_max_blur_beats
    assert res.bars["pedal_blur_fraction"].tolist()[2::2] == [1.0, 1.0, 1.0]
    # syncopated pedalling: lift 50 ms after each change, re-press 100 ms later
    clean = [(0.0, 64, 127)]
    for tc in (4.0, 8.0, 12.0):
        clean += [(tc + 0.05, 64, 0), (tc + 0.15, 64, 127)]
    clean.append((20.0, 64, 0))
    s = control_features(build(notes, lambda b: 0.5 * b, pedal=clean)).summary
    assert s["pedal_blur_fraction"] == 0.0 and s["pedal_blur_beats"] == 0.0
    # one change held, two changed
    mixed = [(0.0, 64, 127), (4.05, 64, 0), (4.15, 64, 127), (12.05, 64, 0), (12.15, 64, 127),
             (20.0, 64, 0)]  # fmt: skip
    s = control_features(build(notes, lambda b: 0.5 * b, pedal=mixed)).summary
    assert s["pedal_blur_fraction"] == pytest.approx(1 / 3)
    # no pedal data
    s = control_features(build(notes, lambda b: 0.5 * b)).summary
    assert not s["pedal_available"] and np.isnan(s["pedal_blur_fraction"])


# --------------------------------------------------------------------------- robustness


def test_unmatched_notes_and_single_staff_do_not_crash():
    notes = [(0.5 * k, 0.5, 60 + (k % 12), 1, 1) for k in range(64)]
    ap = build(notes, lambda b: 0.5 * b)
    pairs = ap.alignment.pairs.copy()
    pairs[5] = ("deletion", "n5", "")
    pairs[9] = ("interpolated", "n9", "p9")
    ap = types.AlignedPerformance(ap.performance, ap.score,
                                  types.Alignment(pairs, "synth:s", "synth:p", False, "t"))
    res = control_features(ap, config=ControlConfig(run_min_notes=6))
    s = res.summary
    assert s["n_cross_staff_onsets"] == 0 and np.isnan(s["hand_async_mean_ms"])
    assert s["n_deletion"] == 1 and s["n_interpolated_skipped"] == 1
    assert s["even_ioi_cv"] < 1e-4
    assert len(res.bars) == 8
