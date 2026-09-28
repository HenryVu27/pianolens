"""Fixed-piano rendering: a ``Performance`` or MIDI file to audio with one piano sound (S-02).

Every rendered stimulus and every rendered-audio model input in PianoLens goes through this module,
so they all share one piano.

**Piano.** Salamander Grand Piano, "SalamanderC5-Light" SF2 (``SalC5Light2.sf2``, 7 velocity
layers, 44.1 kHz), a conversion by hed-sounds of Alexander Holm's Salamander Grand Piano samples.
This is the file CrescendAI rendered PercePiano with for its paper-era MuQ results (repo
``Jai-Dhiman/crescendai``, commit ``1ec53b10``, ``model/src/percepiano/audio/render_midi.py``).
Source, hash and license are in ``DATASETS.md``. Expected at ``SOUNDFONT_PATH``.

**Renderer.** The FluidSynth command-line program (``brew install fluidsynth``; tested with 2.6.1),
called the way CrescendAI called it (``fluidsynth -ni -F out.wav -r 44100 -g 0.8 sf2 mid``), except:

* every synth setting that shapes the sound (reverb, chorus, polyphony, interpolation) is passed
  explicitly, so a FluidSynth upgrade that changes a default does not silently change the piano;
  the values are FluidSynth 2.6.1's defaults, which CrescendAI got implicitly;
* FluidSynth writes 32-bit float, not 16-bit. That skips FluidSynth's dithered 16-bit conversion
  (a source of run-to-run noise) and keeps peaks above full scale measurable.

**Output.** FluidSynth renders stereo at 44.1 kHz. ``render_*`` then downmixes to mono (channel
mean) and resamples with soxr ``HQ`` to ``RenderConfig.sample_rate`` (24 kHz by default, the MuQ
input rate). That is what ``librosa.load(path, sr=24000, mono=True)`` does to CrescendAI's WAVs.
FluidSynth's fast render keeps going for about 2-3 s after the last MIDI event (measured with
2.6.1), so release tails are kept and each file ends in a short stretch of near-silence. No
trimming is applied, to stay close to CrescendAI's files.

**Loudness policy.** ``normalize="none"`` is the default and the right choice for any model input:
MIDI velocity is the performer's dynamics, so per-file normalisation would erase exactly what the
raters judged. The level is fixed by the synth gain (0.8) alone, identical for every file.
``"peak"`` (scale to a peak of ``peak_dbfs``) and ``"lufs"`` (ITU-R BS.1770 integrated loudness to
``target_lufs``, via pyloudnorm) exist only for listening stimuli where a study protocol explicitly
wants level-matched clips; the study must say so. If a rendered peak exceeds full scale, the WAV
writer would clip; ``render_*`` records the peak in ``RenderResult.peak`` so callers can check.

**Determinism.** Same MIDI + same config + same FluidSynth version + same soundfont gives
bit-identical output (``tests/audio/test_render.py`` checks this). The config hash and the
soundfont hash go into every render manifest.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

import mido
import numpy as np

from pianolens.data.types import Performance

_REPO = Path(__file__).resolve().parents[3]
SOUNDFONT_PATH = _REPO / "data" / "raw" / "soundfonts" / "salamander_c5_light" / "SalC5Light2.sf2"
SOUNDFONT_SHA256 = "f0c8cb73b87e1b3b1a190e9e37ace4668fb4fcfa381f94aac00178b72e68fca4"
RENDER_ROOT = _REPO / "data" / "interim" / "renders"

Normalize = Literal["none", "peak", "lufs"]

# FluidSynth 2.6.1 defaults, pinned. CrescendAI ran the CLI without -R/-C flags, so it got the
# defaults of whatever FluidSynth version it had (not recorded in its repo).
_SYNTH_SETTINGS: dict[str, str] = {
    "synth.reverb.active": "1",
    "synth.reverb.room-size": "0.5",
    "synth.reverb.damp": "0.2",
    "synth.reverb.width": "0.8",
    "synth.reverb.level": "0.7",
    "synth.chorus.active": "1",
    "synth.chorus.nr": "3",
    "synth.chorus.level": "0.6",
    "synth.chorus.speed": "0.2",
    "synth.chorus.depth": "4.25",
    "synth.polyphony": "256",
    "synth.cpu-cores": "1",
    "synth.min-note-length": "10",
    "player.timing-source": "sample",
    "player.reset-synth": "1",
    "audio.file.format": "float",
    "audio.file.type": "wav",
}


@dataclass(frozen=True)
class RenderConfig:
    """Everything that determines the rendered audio, apart from the MIDI itself."""

    soundfont: str = str(SOUNDFONT_PATH)
    synth_rate: int = 44_100
    sample_rate: int = 24_000
    gain: float = 0.8
    reverb: bool = True
    chorus: bool = True
    normalize: Normalize = "none"
    peak_dbfs: float = -1.0
    target_lufs: float = -23.0

    def fluidsynth_settings(self) -> dict[str, str]:
        s = dict(_SYNTH_SETTINGS)
        s["synth.reverb.active"] = "1" if self.reverb else "0"
        s["synth.chorus.active"] = "1" if self.chorus else "0"
        s["synth.sample-rate"] = str(self.synth_rate)
        s["synth.gain"] = repr(float(self.gain))
        return s

    def config_hash(self) -> str:
        """Short hash of the settings that shape the sound (soundfont by name, not path)."""
        d = asdict(self)
        d["soundfont"] = Path(self.soundfont).name
        d["fluidsynth"] = self.fluidsynth_settings()
        blob = json.dumps(d, sort_keys=True).encode()
        return hashlib.sha256(blob).hexdigest()[:12]


CRESCENDAI_SALAMANDER = RenderConfig()
"""The default config: CrescendAI's paper-era Salamander render, then 24 kHz mono."""


@dataclass(frozen=True)
class RenderResult:
    audio: np.ndarray  # float32, mono, (n_samples,)
    sample_rate: int
    peak: float  # max |sample| after normalisation
    gain_db: float  # normalisation gain applied (0 for "none")


# --------------------------------------------------------------------------- availability


def fluidsynth_path() -> str | None:
    return shutil.which("fluidsynth")


def fluidsynth_version() -> str | None:
    exe = fluidsynth_path()
    if exe is None:
        return None
    out = subprocess.run([exe, "--version"], capture_output=True, text=True, check=False).stdout
    for line in out.splitlines():
        if "version" in line.lower():
            return line.split()[-1]
    return None


def renderer_available(config: RenderConfig = CRESCENDAI_SALAMANDER) -> bool:
    return fluidsynth_path() is not None and Path(config.soundfont).is_file()


def file_sha256(path: Path | str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# --------------------------------------------------------------------------- Performance -> MIDI

_PPQ = 960
_TEMPO = 500_000  # microseconds per quarter: 120 bpm, so 1 tick = 1/1920 s (~0.52 ms)


def _sec_to_tick(t: float) -> int:
    return int(round(t * 1e6 / _TEMPO * _PPQ))


def performance_to_midi(perf: Performance, path: Path | str, *, program: int = 0) -> Path:
    """Write a ``Performance`` as a one-track MIDI file (notes on channel 0, pedal CCs).

    Onsets and key releases are quantised to 1/1920 s. Notes use ``duration_sec`` (key-down
    time); sustain is carried by the pedal events, as in the source MIDI. Overlapping notes of
    the same pitch are written in time order; a note_off at the same tick as a note_on sorts
    first, so a re-struck key is not cut.
    """
    events: list[tuple[int, int, mido.Message]] = []
    # sort key: (tick, order) with order 0 = note_off, 1 = control, 2 = note_on
    for n in perf.notes:
        on = _sec_to_tick(float(n["onset_sec"]))
        off = max(on + 1, _sec_to_tick(float(n["onset_sec"] + n["duration_sec"])))
        pitch, vel = int(n["pitch"]), int(np.clip(n["velocity"], 1, 127))
        events.append((on, 2, mido.Message("note_on", note=pitch, velocity=vel, channel=0)))
        events.append((off, 0, mido.Message("note_off", note=pitch, velocity=0, channel=0)))
    for p in perf.pedal:
        events.append((_sec_to_tick(float(p["time_sec"])), 1,
                       mido.Message("control_change", control=int(p["number"]),
                                    value=int(np.clip(p["value"], 0, 127)), channel=0)))
    events.sort(key=lambda e: (e[0], e[1]))
    track = mido.MidiTrack()
    track.append(mido.MetaMessage("set_tempo", tempo=_TEMPO, time=0))
    track.append(mido.Message("program_change", program=program, channel=0, time=0))
    last = 0
    for tick, _, msg in events:
        track.append(msg.copy(time=tick - last))
        last = tick
    track.append(mido.MetaMessage("end_of_track", time=0))
    mid = mido.MidiFile(type=0, ticks_per_beat=_PPQ)
    mid.tracks.append(track)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    mid.save(str(path))
    return path


# --------------------------------------------------------------------------- rendering


def _fluidsynth_raw(midi_path: Path, config: RenderConfig) -> tuple[np.ndarray, int]:
    """Run FluidSynth; return (float32 array (n, channels), synth rate)."""
    import soundfile as sf

    exe = fluidsynth_path()
    if exe is None:
        raise RuntimeError("fluidsynth not found; install it with `brew install fluidsynth`")
    if not Path(config.soundfont).is_file():
        raise FileNotFoundError(f"soundfont missing: {config.soundfont} (see DATASETS.md)")
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "raw.wav"
        cmd = [exe, "-n", "-i", "-q", "-F", str(out), "-r", str(config.synth_rate),
               "-g", repr(float(config.gain))]
        for k, v in config.fluidsynth_settings().items():
            cmd += ["-o", f"{k}={v}"]
        cmd += [str(config.soundfont), str(midi_path)]
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=600)
        if proc.returncode != 0 or not out.is_file():
            raise RuntimeError(f"fluidsynth failed on {midi_path}: {proc.stderr.strip()[:500]}")
        audio, sr = sf.read(str(out), dtype="float32", always_2d=True)
    return audio, int(sr)


def _normalize(y: np.ndarray, sr: int, config: RenderConfig) -> tuple[np.ndarray, float]:
    if config.normalize == "none":
        return y, 0.0
    if config.normalize == "peak":
        peak = float(np.max(np.abs(y))) if len(y) else 0.0
        if peak == 0:
            return y, 0.0
        gain_db = config.peak_dbfs - 20 * np.log10(peak)
    elif config.normalize == "lufs":
        import pyloudnorm as pyln

        loud = pyln.Meter(sr).integrated_loudness(y.astype(np.float64))
        if not np.isfinite(loud):
            return y, 0.0
        gain_db = config.target_lufs - loud
    else:
        raise ValueError(f"unknown normalize={config.normalize!r}")
    return (y * np.float32(10 ** (gain_db / 20))).astype(np.float32), float(gain_db)


def render_midi(midi_path: Path | str, config: RenderConfig = CRESCENDAI_SALAMANDER
                ) -> RenderResult:
    """Render a MIDI file to mono float32 audio at ``config.sample_rate``."""
    import soxr

    raw, sr = _fluidsynth_raw(Path(midi_path), config)
    mono = raw.mean(axis=1).astype(np.float32)
    if config.sample_rate != sr:
        mono = soxr.resample(mono, sr, config.sample_rate, quality="HQ").astype(np.float32)
    mono, gain_db = _normalize(mono, config.sample_rate, config)
    peak = float(np.max(np.abs(mono))) if len(mono) else 0.0
    return RenderResult(mono, config.sample_rate, peak, gain_db)


def render_performance(perf: Performance, config: RenderConfig = CRESCENDAI_SALAMANDER
                       ) -> RenderResult:
    """Render a ``Performance`` (via a temporary MIDI file from ``performance_to_midi``)."""
    with tempfile.TemporaryDirectory() as tmp:
        mid = performance_to_midi(perf, Path(tmp) / "perf.mid")
        return render_midi(mid, config)


def write_wav(result: RenderResult, path: Path | str, subtype: str = "PCM_16") -> Path:
    """Write a render. PCM_16 clips samples beyond full scale; check ``result.peak`` first."""
    import soundfile as sf

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), result.audio, result.sample_rate, subtype=subtype)
    return path


def render_to_wav(source: Performance | Path | str, wav_path: Path | str,
                  config: RenderConfig = CRESCENDAI_SALAMANDER, subtype: str = "PCM_16"
                  ) -> RenderResult:
    """Render a ``Performance`` or a MIDI path and write it to ``wav_path``."""
    if isinstance(source, Performance):
        res = render_performance(source, config)
    else:
        res = render_midi(source, config)
    write_wav(res, wav_path, subtype=subtype)
    return res


def render_dir(config: RenderConfig, corpus: str) -> Path:
    """Canonical output folder: ``data/interim/renders/<soundfont stem>-<config hash>/<corpus>``."""
    stem = Path(config.soundfont).stem.lower()
    return RENDER_ROOT / f"{stem}-{config.config_hash()}" / corpus
