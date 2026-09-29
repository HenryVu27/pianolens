"""Audio clip helpers for the A/B comparison (P-01): load, cut, fade, loudness-match, encode.

All clips are mono float32 at :data:`SAMPLE_RATE` (44.1 kHz, the S-02 synth rate, so renders
are not resampled).

* **Cut:** sample-exact at the requested times; a cut that reaches before the start or after
  the end of the source is padded with silence, so the clip timeline always equals the
  requested span (the manifest's offsets stay true).
* **Fades:** raised-cosine, :data:`FADE_MS` in and out.
* **Loudness:** ITU-R BS.1770 integrated loudness (pyloudnorm). The clips of one window are
  brought to the same loudness; the common target is lowered if any clip would peak above
  ``max_peak_dbfs``, so they stay matched.
* **Encoding:** MP3 (libmp3lame via ffmpeg, mono, :data:`MP3_BITRATE`). ffmpeg writes the LAME
  gapless header, so a decoder that honours it returns the clip without encoder delay.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import warnings
from pathlib import Path

import numpy as np

__all__ = ["FADE_MS", "MP3_BITRATE", "SAMPLE_RATE", "apply_fades", "cut", "decode_audio",
           "encode_mp3", "estimate_lag", "ffmpeg_available", "integrated_loudness",
           "load_audio", "match_loudness", "nearest_onset", "onset_train_lag"]

SAMPLE_RATE = 44_100
FADE_MS = 20.0
MP3_BITRATE = "96k"


def load_audio(path: Path | str, sr: int = SAMPLE_RATE) -> np.ndarray:
    """Any file soundfile can read, as mono float32 at ``sr`` (channel mean, soxr HQ)."""
    import soundfile as sf
    import soxr

    y, fs = sf.read(str(path), dtype="float32", always_2d=True)
    y = y.mean(axis=1).astype(np.float32)
    if fs != sr:
        y = soxr.resample(y, fs, sr, quality="HQ").astype(np.float32)
    return y


def cut(y: np.ndarray, start_sec: float, end_sec: float, sr: int = SAMPLE_RATE) -> np.ndarray:
    """Samples ``[start, end)``; zero-padded where the span leaves the signal."""
    a, b = int(round(start_sec * sr)), int(round(end_sec * sr))
    if b <= a:
        return np.zeros(0, np.float32)
    out = np.zeros(b - a, np.float32)
    lo, hi = max(a, 0), min(b, len(y))
    if hi > lo:
        out[lo - a:hi - a] = y[lo:hi]
    return out


def apply_fades(y: np.ndarray, sr: int = SAMPLE_RATE, fade_ms: float = FADE_MS) -> np.ndarray:
    n = min(int(round(fade_ms * 1e-3 * sr)), len(y) // 2)
    if n <= 0:
        return y
    ramp = (0.5 - 0.5 * np.cos(np.linspace(0, np.pi, n))).astype(np.float32)
    out = y.astype(np.float32, copy=True)
    out[:n] *= ramp
    out[-n:] *= ramp[::-1]
    return out


def integrated_loudness(y: np.ndarray, sr: int = SAMPLE_RATE) -> float:
    """BS.1770 integrated loudness (LUFS); -inf for silence or clips under 0.4 s."""
    import pyloudnorm as pyln

    if len(y) < int(0.4 * sr) or not np.any(y):
        return float("-inf")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return float(pyln.Meter(sr).integrated_loudness(y.astype(np.float64)))


def match_loudness(clips: dict[str, np.ndarray], target_lufs: float = -20.0,
                   max_peak_dbfs: float = -1.0, sr: int = SAMPLE_RATE
                   ) -> tuple[dict[str, np.ndarray], dict[str, dict[str, float]]]:
    """Bring every clip to one integrated loudness. Returns the clips and, per clip,
    ``lufs_in``, ``gain_db`` and ``peak_dbfs`` after gain, plus the common ``target_lufs``."""
    loud = {k: integrated_loudness(v, sr) for k, v in clips.items()}
    peaks = {k: float(np.max(np.abs(v))) if len(v) else 0.0 for k, v in clips.items()}
    target = target_lufs
    for k in clips:
        if np.isfinite(loud[k]) and peaks[k] > 0:
            peak_after = 20 * np.log10(peaks[k]) + (target - loud[k])
            if peak_after > max_peak_dbfs:
                target -= peak_after - max_peak_dbfs
    out, info = {}, {}
    for k, v in clips.items():
        g = target - loud[k] if np.isfinite(loud[k]) else 0.0
        y = (v * np.float32(10 ** (g / 20))).astype(np.float32)
        pk = float(np.max(np.abs(y))) if len(y) else 0.0
        out[k] = y
        info[k] = {"lufs_in": loud[k], "gain_db": float(g), "target_lufs": float(target),
                   "peak_dbfs": 20 * float(np.log10(pk)) if pk > 0 else float("-inf")}
    return out, info


# --------------------------------------------------------------------------- encode / decode


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def encode_mp3(y: np.ndarray, path: Path | str, sr: int = SAMPLE_RATE,
               bitrate: str = MP3_BITRATE) -> Path:
    """Write mono MP3 via ffmpeg/libmp3lame (float WAV in a temp dir, never next to the output)."""
    import soundfile as sf

    exe = shutil.which("ffmpeg")
    if exe is None:
        raise RuntimeError("ffmpeg not found; install it with `brew install ffmpeg`")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "clip.wav"
        sf.write(str(wav), np.clip(y, -1, 1), sr, subtype="FLOAT")
        cmd = [exe, "-hide_banner", "-loglevel", "error", "-y", "-i", str(wav), "-ac", "1",
               "-ar", str(sr), "-codec:a", "libmp3lame", "-b:a", bitrate, "-map_metadata", "-1",
               str(path)]  # fmt: skip
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=120)
        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg failed: {proc.stderr.strip()[:400]}")
    return path


def decode_audio(path: Path | str, sr: int = SAMPLE_RATE) -> np.ndarray:
    """Decode any file with ffmpeg to mono float32 (used to check encoded clips)."""
    exe = shutil.which("ffmpeg")
    if exe is None:
        raise RuntimeError("ffmpeg not found")
    cmd = [exe, "-hide_banner", "-loglevel", "error", "-i", str(path), "-f", "f32le", "-ac", "1",
           "-ar", str(sr), "-"]
    proc = subprocess.run(cmd, capture_output=True, check=True, timeout=120)
    return np.frombuffer(proc.stdout, dtype=np.float32).copy()


# --------------------------------------------------------------------------- listening proxies


def _onset_env(y: np.ndarray, sr: int, hop: int) -> np.ndarray:
    import librosa

    return librosa.onset.onset_strength(y=y.astype(np.float32), sr=sr, hop_length=hop)


def estimate_lag(a: np.ndarray, b: np.ndarray, sr: int = SAMPLE_RATE, max_lag_sec: float = 1.0,
                 hop: int = 441) -> tuple[float, float]:
    """Lag of ``b`` relative to ``a`` (seconds; positive = ``b`` late) from the cross-correlation
    of onset-strength envelopes, and the peak normalised correlation."""
    ea, eb = _onset_env(a, sr, hop), _onset_env(b, sr, hop)
    n = min(len(ea), len(eb))
    ea, eb = ea[:n] - ea[:n].mean(), eb[:n] - eb[:n].mean()
    m = int(round(max_lag_sec * sr / hop))
    lags = np.arange(-m, m + 1)
    den = float(np.sqrt((ea ** 2).sum() * (eb ** 2).sum())) or 1.0
    cc = np.array([np.dot(ea[max(0, -k):n - max(0, k)], eb[max(0, k):n - max(0, -k)])
                   for k in lags]) / den  # fmt: skip
    i = int(np.argmax(cc))
    return float(lags[i] * hop / sr), float(cc[i])


def nearest_onset(y: np.ndarray, t_sec: float, sr: int = SAMPLE_RATE, search_sec: float = 0.25,
                  hop: int = 128) -> float | None:
    """Detected onset (librosa, backtracked to the energy rise) nearest to ``t_sec`` within
    ``search_sec``; None if there is none."""
    import librosa

    if not len(y):
        return None
    on = librosa.onset.onset_detect(y=y.astype(np.float32), sr=sr, hop_length=hop, units="time",
                                    backtrack=False)
    if not len(on):
        return None
    j = int(np.argmin(np.abs(on - t_sec)))
    return float(on[j]) if abs(on[j] - t_sec) <= search_sec else None


def onset_train_lag(y: np.ndarray, onsets_sec: np.ndarray, weights: np.ndarray | None = None,
                    sr: int = SAMPLE_RATE, max_lag_sec: float = 0.2, hop: int = 128,
                    sigma_frames: float = 2.0) -> tuple[float, float]:
    """Lag of the audio against the note onsets it should contain (seconds; positive = audio
    late), from the cross-correlation of the onset-strength envelope with a train of Gaussian
    bumps at ``onsets_sec`` (weighted, e.g. by velocity). Checks a whole clip's timeline, not
    one onset. Returns (lag, peak normalised correlation)."""
    env = _onset_env(y, sr, hop)
    n = len(env)
    train = np.zeros(n)
    fr = np.round(np.asarray(onsets_sec, float) * sr / hop).astype(int)
    w = np.ones(len(fr)) if weights is None else np.asarray(weights, float)
    ok = (fr >= 0) & (fr < n)
    np.add.at(train, fr[ok], w[ok])
    k = np.arange(-int(4 * sigma_frames), int(4 * sigma_frames) + 1)
    train = np.convolve(train, np.exp(-0.5 * (k / sigma_frames) ** 2), mode="same")
    a, b = train - train.mean(), env - env.mean()
    m = int(round(max_lag_sec * sr / hop))
    lags = np.arange(-m, m + 1)
    den = float(np.sqrt((a ** 2).sum() * (b ** 2).sum())) or 1.0
    cc = np.array([np.dot(a[max(0, -j):n - max(0, j)], b[max(0, j):n - max(0, -j)])
                   for j in lags]) / den  # fmt: skip
    i = int(np.argmax(cc))
    return float(lags[i] * hop / sr), float(cc[i])
