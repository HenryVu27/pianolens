import numpy as np
import pytest

from pianolens.audio import render as R
from pianolens.data.midi_io import performance_from_midi
from pianolens.data.types import PEDAL_DTYPE, Performance, PerformerId, PieceId

_NOTE_DTYPE = np.dtype([("onset_sec", "f8"), ("duration_sec", "f8"), ("pitch", "i4"),
                        ("velocity", "i4"), ("id", "U8")])

needs_renderer = pytest.mark.skipif(not R.renderer_available(),
                                    reason="fluidsynth or the Salamander soundfont is missing")


def _perf(velocity: int = 80, pedal: bool = True) -> Performance:
    notes = np.array([
        (0.00, 0.40, 60, velocity, "n0"),
        (0.50, 0.40, 64, velocity, "n1"),
        (1.00, 0.80, 67, velocity, "n2"),
        (1.00, 0.80, 48, velocity, "n3"),
        (1.90, 0.30, 60, velocity, "n4"),  # re-strike of pitch 60
    ], dtype=_NOTE_DTYPE)
    ped = np.array([(0.9, 64, 127), (1.85, 64, 0)] if pedal else [], dtype=PEDAL_DTYPE)
    return Performance("test:perf", PieceId("test_piece"), PerformerId("test:p"), "synthetic",
                       notes, ped, "test")


def test_performance_to_midi_roundtrip(tmp_path):
    perf = _perf()
    mid = R.performance_to_midi(perf, tmp_path / "p.mid")
    back = performance_from_midi(mid, dataset="test", performance_id="x",
                                 piece_id=PieceId("t"), performer_id=PerformerId("t"),
                                 provenance="synthetic")
    a = np.sort(perf.notes, order=["onset_sec", "pitch"])
    b = np.sort(back.notes, order=["onset_sec", "pitch"])
    assert len(a) == len(b)
    assert np.array_equal(a["pitch"], b["pitch"])
    assert np.array_equal(a["velocity"], b["velocity"])
    assert np.allclose(a["onset_sec"], b["onset_sec"], atol=1e-3)
    assert np.allclose(a["duration_sec"], b["duration_sec"], atol=1e-3)
    sustain = back.pedal[back.pedal["number"] == 64]
    assert np.allclose(sustain["time_sec"], [0.9, 1.85], atol=1e-3)
    assert list(sustain["value"]) == [127, 0]


def test_config_hash_tracks_sound_settings():
    base = R.RenderConfig()
    assert base.config_hash() == R.RenderConfig().config_hash()
    assert base.config_hash() != R.RenderConfig(gain=0.5).config_hash()
    assert base.config_hash() != R.RenderConfig(reverb=False).config_hash()
    # the soundfont's location does not matter, only its file name
    moved = R.RenderConfig(soundfont="/elsewhere/SalC5Light2.sf2")
    assert base.config_hash() == moved.config_hash()
    assert R.render_dir(base, "percepiano").name == "percepiano"
    assert base.config_hash() in str(R.render_dir(base, "percepiano"))


def test_fluidsynth_settings_are_pinned():
    s = R.RenderConfig().fluidsynth_settings()
    for key in ("synth.reverb.room-size", "synth.chorus.depth", "synth.polyphony",
                "synth.sample-rate", "synth.gain", "audio.file.format"):
        assert key in s
    assert R.RenderConfig(chorus=False).fluidsynth_settings()["synth.chorus.active"] == "0"


@needs_renderer
def test_soundfont_hash_matches_manifest():
    assert R.file_sha256(R.SOUNDFONT_PATH) == R.SOUNDFONT_SHA256


@needs_renderer
def test_render_is_deterministic_mono_fixed_rate():
    a = R.render_performance(_perf())
    b = R.render_performance(_perf())
    assert a.sample_rate == 24_000 and a.audio.ndim == 1 and a.audio.dtype == np.float32
    assert np.array_equal(a.audio, b.audio)
    # FluidSynth renders past the last MIDI event (2.2 s) by a few seconds of release tail
    assert 2.2 <= len(a.audio) / a.sample_rate < 6.0
    assert 0.01 < a.peak < 1.0
    assert a.gain_db == 0.0


@needs_renderer
def test_velocity_changes_level_without_normalisation():
    soft = R.render_performance(_perf(velocity=30))
    loud = R.render_performance(_perf(velocity=110))
    rms = [float(np.sqrt(np.mean(x.audio**2))) for x in (soft, loud)]
    assert rms[1] > 2 * rms[0]


@needs_renderer
def test_normalisation_modes(tmp_path):
    peak = R.render_performance(_perf(), R.RenderConfig(normalize="peak", peak_dbfs=-3.0))
    assert abs(20 * np.log10(peak.peak) - (-3.0)) < 1e-3
    pyln = pytest.importorskip("pyloudnorm")
    lufs = R.render_performance(_perf(), R.RenderConfig(normalize="lufs", target_lufs=-20.0))
    measured = pyln.Meter(lufs.sample_rate).integrated_loudness(lufs.audio.astype(np.float64))
    assert abs(measured - (-20.0)) < 0.1


@needs_renderer
def test_render_to_wav_writes_file(tmp_path):
    sf = pytest.importorskip("soundfile")
    mid = R.performance_to_midi(_perf(), tmp_path / "p.mid")
    res = R.render_to_wav(mid, tmp_path / "p.wav")
    y, sr = sf.read(str(tmp_path / "p.wav"), dtype="float32")
    assert sr == 24_000 and y.ndim == 1 and len(y) == len(res.audio)
    assert np.max(np.abs(y - res.audio)) < 1e-4  # PCM_16 quantisation only
