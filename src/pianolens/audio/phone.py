"""A simple phone-in-a-room simulation for rendered piano audio (A-01).

Used to ask "how much error does transcription add when the audio sounds like a phone recording of
a piano in a room" where the true MIDI is known. It is deliberately simple and is **not** a
calibrated model of any phone or room:

1. **Room.** Convolution with a synthetic impulse response: a unit direct path plus exponentially
   decaying Gaussian noise (the classic stochastic late-reverb model), with a given RT60 and
   direct-to-reverberant ratio. Early reflections are not modelled.
2. **Phone microphone / processing.** A 2nd-order Butterworth high-pass (small MEMS capsules and
   phone voice processing cut the low end) and a 2nd-order low-pass (codec band limit).
3. **Noise.** Pink noise (1/f power) added at a given SNR relative to the signal's RMS.
4. **Level.** Scaled to a fixed peak (``peak_dbfs``), as phone automatic gain roughly does.

Lossy codec round trips (AAC / Opus, as on YouTube) are applied outside this module with ffmpeg.
Every step is seeded, so the same input and ``PhoneSimConfig`` give the same output.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
from scipy import signal


@dataclass(frozen=True)
class PhoneSimConfig:
    rt60_s: float = 0.5  # reverberation time of the synthetic room
    drr_db: float = 3.0  # direct-to-reverberant energy ratio
    highpass_hz: float = 120.0
    lowpass_hz: float = 12_000.0
    snr_db: float = 35.0  # signal RMS over pink-noise RMS
    peak_dbfs: float = -3.0
    seed: int = 0

    def as_dict(self) -> dict:
        return asdict(self)


def room_ir(sr: int, rt60_s: float, drr_db: float, rng: np.random.Generator) -> np.ndarray:
    """Synthetic room impulse response: direct path (sample 0) + exponentially decaying noise.

    The tail's energy decays by 60 dB in ``rt60_s``; its total energy is set so the direct path
    carries ``drr_db`` more energy than the tail. Length is 1.2 x RT60.
    """
    n = max(2, int(round(1.2 * rt60_s * sr)))
    t = np.arange(n) / sr
    # amplitude envelope exp(-t / tau) gives energy exp(-2t / tau); -60 dB at rt60
    tau = 2.0 * rt60_s / (6.0 * np.log(10.0))
    tail = rng.standard_normal(n) * np.exp(-t / tau)
    tail[0] = 0.0
    e_tail = float(np.sum(tail**2))
    tail *= np.sqrt(10.0 ** (-drr_db / 10.0) / e_tail)
    tail[0] = 1.0
    return tail


def pink_noise(n: int, rng: np.random.Generator) -> np.ndarray:
    """Pink (1/f power) noise with unit RMS, by shaping white noise in the frequency domain."""
    spec = np.fft.rfft(rng.standard_normal(n))
    f = np.arange(len(spec), dtype=float)
    f[0] = 1.0
    x = np.fft.irfft(spec / np.sqrt(f), n)
    return x / np.sqrt(np.mean(x**2))


def simulate_phone(y: np.ndarray, sr: int, config: PhoneSimConfig | None = None) -> np.ndarray:
    """Apply room, microphone band limits, pink noise and peak level to mono audio ``y``.

    Returns float32 mono audio of the same length as ``y``.
    """
    cfg = config or PhoneSimConfig()
    rng = np.random.default_rng(cfg.seed)
    x = np.asarray(y, dtype=np.float64)
    if cfg.rt60_s > 0:
        x = signal.fftconvolve(x, room_ir(sr, cfg.rt60_s, cfg.drr_db, rng))[: len(y)]
    nyq = sr / 2.0
    if 0 < cfg.highpass_hz < nyq:
        x = signal.sosfilt(signal.butter(2, cfg.highpass_hz, "highpass", fs=sr, output="sos"), x)
    if 0 < cfg.lowpass_hz < nyq:
        x = signal.sosfilt(signal.butter(2, cfg.lowpass_hz, "lowpass", fs=sr, output="sos"), x)
    rms = float(np.sqrt(np.mean(x**2)))
    if np.isfinite(cfg.snr_db) and rms > 0:
        x = x + pink_noise(len(x), rng) * rms * 10.0 ** (-cfg.snr_db / 20.0)
    peak = float(np.max(np.abs(x))) if len(x) else 0.0
    if peak > 0:
        x = x * (10.0 ** (cfg.peak_dbfs / 20.0) / peak)
    return x.astype(np.float32)
