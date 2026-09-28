"""Known-answer tests for A-01 transcription measures and the phone simulation."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from pianolens.audio.phone import PhoneSimConfig, pink_noise, room_ir, simulate_phone
from pianolens.audio.transcription import (
    match_notes,
    note_f1,
    onset_sanity,
    pedal_summary,
    velocity_agreement,
)
from pianolens.data.types import PEDAL_DTYPE


def _notes(onsets, pitches, dur=0.2, vel=64):
    n = len(onsets)
    return pd.DataFrame({"onset_sec": np.asarray(onsets, float), "pitch": np.asarray(pitches),
                         "duration_sec": np.full(n, dur), "velocity": np.full(n, vel)})


def test_note_f1_identical_and_tolerance():
    ref = _notes(np.arange(20) * 0.25, [60 + (k % 5) for k in range(20)])
    assert note_f1(ref, ref)["f1"] == 1.0
    shifted = ref.assign(onset_sec=ref["onset_sec"] + 0.03)
    r = note_f1(ref, shifted)
    assert r["f1"] == 1.0 and abs(r["onset_err_mean_ms"] - 30) < 1e-6
    assert note_f1(ref, ref.assign(onset_sec=ref["onset_sec"] + 0.06))["f1"] == 0.0
    # a constant clock offset is recovered when asked for
    r = note_f1(ref, ref.assign(onset_sec=ref["onset_sec"] + 0.09), estimate_offset=True)
    assert r["f1"] == 1.0 and abs(r["offset_sec"] - 0.09) < 1e-9


def test_note_f1_extra_and_missed():
    ref = _notes([0.0, 0.5, 1.0, 1.5], [60, 62, 64, 65])
    est = _notes([0.0, 0.5, 1.0, 1.2, 1.3], [60, 62, 64, 70, 71])  # 3 hits, 2 extra, 1 missed
    r = note_f1(ref, est)
    assert r["n_match"] == 3
    assert r["precision"] == pytest.approx(3 / 5) and r["recall"] == pytest.approx(3 / 4)


def test_match_is_one_to_one():
    ref = _notes([0.0, 0.02], [60, 60])
    est = _notes([0.01], [60])
    assert len(match_notes(ref, est)) == 1


def test_onset_sanity_double_trigger():
    n = _notes([0.0, 0.02, 1.0, 2.0], [60, 60, 62, 64])
    s = onset_sanity(n)
    assert s["share_double_trigger"] == pytest.approx(0.25)
    assert s["share_out_of_range"] == 0.0


def test_pedal_summary():
    p = np.array([(1.0, 64, 127), (3.0, 64, 0), (5.0, 64, 100), (6.0, 64, 0), (2.0, 67, 127)],
                 dtype=PEDAL_DTYPE)
    p = np.sort(p, order="time_sec")
    s = pedal_summary(p, 0.0, 10.0)
    assert s["n_presses"] == 2 and s["down_fraction"] == pytest.approx(0.3)
    soft = pedal_summary(p, 0.0, 10.0, number=67)
    assert soft["n_presses"] == 1 and soft["down_fraction"] == pytest.approx(0.8)


def test_velocity_agreement_slope():
    x = np.linspace(30, 100, 50)
    r = velocity_agreement(x, 0.5 * x + 20)
    assert r["vel_slope"] == pytest.approx(0.5) and r["vel_resid_rsd_midi"] < 1e-6


def test_room_ir_rt60_and_drr():
    sr, rt = 16_000, 0.5
    h = room_ir(sr, rt, drr_db=3.0, rng=np.random.default_rng(1))
    tail = h[1:]
    assert 10 * np.log10(1.0 / np.sum(tail**2)) == pytest.approx(3.0, abs=1e-6)
    # Schroeder backward integral: -5 dB to -35 dB slope extrapolated to 60 dB
    edc = np.cumsum(tail[::-1] ** 2)[::-1]
    edc_db = 10 * np.log10(edc / edc[0])
    t = np.arange(len(edc)) / sr
    i5, i35 = np.argmax(edc_db < -5), np.argmax(edc_db < -35)
    slope = (edc_db[i35] - edc_db[i5]) / (t[i35] - t[i5])
    assert -60 / slope == pytest.approx(rt, rel=0.1)


def test_simulate_phone_snr_highpass_determinism():
    sr = 16_000
    t = np.arange(sr * 2) / sr
    low = np.sin(2 * np.pi * 40 * t)
    cfg = PhoneSimConfig(rt60_s=0.0, snr_db=np.inf, lowpass_hz=0, highpass_hz=200, peak_dbfs=0)
    y = simulate_phone(low, sr, cfg)
    ref = simulate_phone(np.sin(2 * np.pi * 1000 * t), sr, cfg)
    # 40 Hz is ~2.3 octaves below a 2nd-order 200 Hz high-pass: > 20 dB down before the peak
    # normalisation; after it both peak at 0 dBFS, so compare the unnormalised gain instead
    from scipy import signal

    sos = signal.butter(2, 200, "highpass", fs=sr, output="sos")
    g = np.std(signal.sosfilt(sos, low)[sr:]) / np.std(low[sr:])
    assert 20 * np.log10(g) < -20
    assert np.max(np.abs(y)) == pytest.approx(1.0, abs=1e-5) and len(y) == len(low)
    assert np.max(np.abs(ref)) == pytest.approx(1.0, abs=1e-5)
    # SNR: noise added at 20 dB relative to the signal RMS
    clean = np.sin(2 * np.pi * 440 * t)
    cfg2 = PhoneSimConfig(rt60_s=0.0, highpass_hz=0, lowpass_hz=0, snr_db=20.0, peak_dbfs=0)
    noisy = simulate_phone(clean, sr, cfg2).astype(float)
    scale = np.max(np.abs(clean + 0.0)) / 1.0
    s_hat = clean / scale
    k = np.dot(noisy, s_hat) / np.dot(s_hat, s_hat)
    resid = noisy - k * s_hat
    snr = 10 * np.log10(np.mean((k * s_hat) ** 2) / np.mean(resid**2))
    assert snr == pytest.approx(20.0, abs=0.5)
    a = simulate_phone(clean, sr, PhoneSimConfig(seed=3))
    b = simulate_phone(clean, sr, PhoneSimConfig(seed=3))
    assert np.array_equal(a, b)


def test_pink_noise_spectrum_slope():
    x = pink_noise(2**16, np.random.default_rng(0))
    f = np.fft.rfftfreq(len(x))
    p = np.abs(np.fft.rfft(x)) ** 2
    band = (f > 0.001) & (f < 0.4)
    slope = np.polyfit(np.log10(f[band]), np.log10(p[band]), 1)[0]
    assert slope == pytest.approx(-1.0, abs=0.1)
