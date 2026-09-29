"""Known-answer tests for pianolens.compare (P-01): windows, time map, expert choice, clips,
the engine end to end with a synthetic click renderer, and the player page."""

from __future__ import annotations

import json
import math
import re

import numpy as np
import pytest

from pianolens.compare import clips as C
from pianolens.compare.engine import (
    CompareConfig,
    CompareInputs,
    _span_match,
    build_comparison,
    excerpt_performance,
)
from pianolens.compare.experts import rank_experts
from pianolens.compare.player import player_html
from pianolens.compare.timemap import time_map_from_aligned, time_map_from_notes
from pianolens.compare.windows import select_windows
from pianolens.data import types
from pianolens.features.interpretation import references_from_notes

SR = C.SAMPLE_RATE
PERF_DTYPE = [("onset_sec", "f8"), ("duration_sec", "f8"), ("pitch", "i4"),
              ("velocity", "i4"), ("id", "U32")]  # fmt: skip
SCORE_DTYPE = [("onset_beat", "f8"), ("duration_beat", "f8"), ("onset_quarter", "f8"),
               ("duration_quarter", "f8"), ("pitch", "i4"), ("id", "U32"),
               ("is_grace", "?"), ("ts_beats", "i4")]  # fmt: skip
N_BARS = 8
BEATS = np.arange(0, 4 * N_BARS, dtype=float)  # one quarter note per beat, 4/4


def _issue(bars, tier, category="control", channel="timing", magnitude=1.0, eligible=True):
    return {"category": category, "channel": channel, "bars": bars, "tier": tier,
            "magnitude": magnitude, "practise_eligible": eligible, "text": f"{channel} {bars}"}


# --------------------------------------------------------------------------- windows


def test_windows_priority_merge_and_cap():
    rep = {"issues": [
        _issue([10], "notable", magnitude=5.0),
        _issue([3], "strong", "interpretation", "tempo", 1.2),
        _issue([4], "strong", "correctness", "notes", 1.0),
        _issue([20], "strong", "interpretation", "velocity", 3.0, eligible=False),
        _issue([30], "none"),
        _issue([40, 41, 42, 43, 44, 45], "notable", "too_flat", "tempo", 2.0),
    ]}
    w = select_windows(rep, max_windows=3, max_bars=4)
    # strong + eligible first (correctness before interpretation, merged as adjacent bars),
    # then the non-eligible strong one, then the first notable by category (control before
    # too_flat); the cap is 3
    assert [x.bars for x in w] == [[3, 4], [20], [10]]
    assert w[0].tier == "strong" and len(w[0].reasons) == 2
    assert all(30 not in x.bars for x in w)
    w = select_windows(rep, max_windows=8, max_bars=4)
    flat = [x for x in w if x.bars[0] == 40][0]
    assert flat.bars == [40, 41, 42, 43] and flat.truncated
    assert select_windows(rep, min_tier="strong", max_windows=8)[-1].bars == [20]


def test_windows_never_overlap_after_growth():
    # [4] and [6] start apart; [5] joins [4]; then [3] extends it to 3-5, which touches [6]:
    # the union 3-6 fits in 4 bars, so they must end up as one window
    rep = {"issues": [_issue([4], "strong", magnitude=4), _issue([6], "strong", magnitude=3),
                      _issue([5], "strong", magnitude=2), _issue([3], "strong", magnitude=1)]}
    w = select_windows(rep, max_windows=8, max_bars=4)
    assert [x.bars for x in w] == [[3, 4, 5, 6]]
    seen = set()
    rep2 = {"issues": [_issue([0, 1, 2], "strong", magnitude=4),
                       _issue([4, 5, 6], "strong", magnitude=3),
                       _issue([3], "strong", magnitude=2)]}
    for x in select_windows(rep2, max_windows=8, max_bars=4):
        assert not seen & set(x.bars)
        seen |= set(x.bars)


# --------------------------------------------------------------------------- time map


def test_time_map_follows_rubato_and_drops_outliers():
    b = np.repeat(np.arange(16.0), 3)  # chords of 3
    t_true = 0.5 * np.arange(16.0) + 0.3 * np.sin(np.arange(16.0) / 3)
    t = np.repeat(t_true, 3) + np.tile([-0.01, 0.0, 0.01], 16)
    t[20] += 5.0  # one misaligned note: the chord median ignores it
    tm = time_map_from_notes(b, t)
    assert tm(np.arange(16.0)) == pytest.approx(t_true, abs=1e-9)
    assert tm.at(7.5) == pytest.approx((t_true[7] + t_true[8]) / 2)
    # an outlier position (a whole chord misaligned) is dropped, not allowed to bend time
    t2 = t_true.copy()
    t2[9] = t_true[9] + 3.0
    tm2 = time_map_from_notes(np.arange(16.0), t2)
    assert tm2.n_dropped == 1 and tm2.at(9.0) == pytest.approx((t_true[8] + t_true[10]) / 2,
                                                               abs=0.05)
    assert np.all(np.diff(tm2(np.linspace(-2, 18, 200))) >= 0)
    # linear extension past the ends at the edge tempo
    assert tm.at(-1.0) < tm.at(0.0) < tm.at(15.0) < tm.at(16.0)


# --------------------------------------------------------------------------- synthetic set


def _onsets(a: float, beats: np.ndarray = BEATS) -> np.ndarray:
    """Seconds for score beats with local beat period 0.5 * (1 + a sin(pi b / 32))."""
    L = 4 * N_BARS
    return 0.5 * beats - 0.5 * a * L / math.pi * (np.cos(math.pi * beats / L) - 1)


def _manual_ap(onsets, pid="synth:p", pedal=None, provenance="synthetic"):
    n = len(BEATS)
    pitches = [60 + (i * 5) % 17 for i in range(n)]
    sn = np.zeros(n, dtype=SCORE_DTYPE)
    sn["onset_beat"] = sn["onset_quarter"] = BEATS
    sn["duration_beat"] = sn["duration_quarter"] = 1.0
    sn["pitch"] = pitches
    sn["id"] = [f"n{i}" for i in range(n)]
    sn["ts_beats"] = 4
    starts = np.arange(0, 4 * N_BARS, 4.0)
    ms = np.zeros(len(starts), dtype=types.MEASURE_DTYPE)
    ms["number"] = np.arange(1, len(starts) + 1)
    ms["start_quarter"] = starts
    ms["end_quarter"] = starts + 4
    score = types.Score("synth:s", types.PieceId("synth"), sn, ms)
    pn = np.zeros(n, dtype=PERF_DTYPE)
    pn["onset_sec"] = onsets
    pn["duration_sec"] = 0.3
    pn["pitch"] = pitches
    pn["velocity"] = 64
    pn["id"] = [f"p{i}" for i in range(n)]
    ped = np.zeros(0, types.PEDAL_DTYPE) if pedal is None else pedal
    perf = types.Performance(pid, types.PieceId("synth"), types.PerformerId("synth:x"),
                             provenance, pn, ped, "synth")
    rows = [("match", f"n{i}", f"p{i}") for i in range(n)]
    al = types.Alignment(np.array(rows, dtype=types.ALIGNMENT_DTYPE), "synth:s", pid, False,
                         "test")
    return types.AlignedPerformance(perf, score, al)


AMPS = {"ref:m2": -0.3, "ref:m1": -0.15, "ref:0": 0.0, "ref:p1": 0.15, "ref:p2": 0.3,
        "ref:p3": 0.2, "ref:m3": -0.2}  # fmt: skip


def _refs():
    perfs = [{"performance_id": k, "provenance": "transcribed", "beats": BEATS,
              "onsets_sec": _onsets(a), "velocities": np.full(len(BEATS), 64.0)}
             for k, a in AMPS.items()]  # fmt: skip
    return references_from_notes("synth", perfs, BEATS, BEATS, np.arange(0, 32, 4.0), 4.0)


class DictExperts:
    def __init__(self):
        self.aps = {k: _manual_ap(_onsets(a), pid=k) for k, a in AMPS.items()}

    def load(self, pid):
        return self.aps.get(pid)

    def describe(self, pid):
        return {"performer": pid.upper()}


def click_render(perf) -> np.ndarray:
    """A 60 ms decaying tone at every note onset: onsets are exactly known in the audio."""
    n = perf.notes
    end = float(np.max(n["onset_sec"])) + 1.0 if len(n) else 1.0
    y = np.zeros(int(end * SR), np.float32)
    k = np.arange(int(0.06 * SR))
    burst = (np.sin(2 * np.pi * 440 * k / SR) * np.exp(-k / (0.015 * SR))).astype(np.float32)
    for t in n["onset_sec"]:
        i = int(round(t * SR))
        seg = y[i:i + len(burst)]
        seg += 0.3 * burst[:len(seg)]
    return y


def test_rank_experts_picks_the_median_reading():
    refs = _refs()
    ch = rank_experts(refs, BEATS[8:24], None)
    assert ch.n_eligible == len(AMPS)
    assert refs.performance_ids[ch.typical_order()[0]] == "ref:0"
    # far but in band: at the 90th percentile of distance, an outer reading
    assert refs.performance_ids[ch.contrast_order()[0]] in ("ref:p2", "ref:m2", "ref:p3",
                                                           "ref:m3")
    assert ch.info(int(ch.rows[0]))["distance_percentile"] == 0.0


# --------------------------------------------------------------------------- clips


def test_cut_pads_and_fades():
    y = np.ones(SR, np.float32)
    c = C.cut(y, -0.5, 0.5)
    assert len(c) == SR and c[: SR // 2].max() == 0 and c[SR // 2:].min() == 1
    f = C.apply_fades(np.ones(SR, np.float32))
    n = int(0.02 * SR)
    assert f[0] == 0 and f[-1] == 0 and f[n] == 1 and f[n // 2] == pytest.approx(0.5, abs=0.01)


def test_match_loudness_equalises_and_respects_peak():
    t = np.arange(3 * SR) / SR
    quiet = (0.01 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    loud = (0.5 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    out, info = C.match_loudness({"a": quiet, "b": loud}, target_lufs=-20)
    la, lb = C.integrated_loudness(out["a"]), C.integrated_loudness(out["b"])
    assert la == pytest.approx(lb, abs=0.05) and la == pytest.approx(-20, abs=0.1)
    out, info = C.match_loudness({"a": quiet, "b": loud}, target_lufs=0, max_peak_dbfs=-1)
    assert max(v["peak_dbfs"] for v in info.values()) == pytest.approx(-1, abs=0.01)
    assert info["a"]["target_lufs"] == info["b"]["target_lufs"] < 0


def test_excerpt_keeps_pedal_state_and_shifts_time():
    ped = np.array([(0.5, 64, 127), (1.0, 67, 100), (6.0, 64, 0)], dtype=types.PEDAL_DTYPE)
    ap = _manual_ap(_onsets(0.0), pedal=ped)
    ex = excerpt_performance(ap.performance, 2.0, 4.0)
    assert ex.notes["onset_sec"].min() >= 0 and ex.notes["onset_sec"].max() < 2.0
    assert len(ex.notes) == 4  # beats 4..7 at 0.5 s per beat
    assert {(e["number"], e["value"]) for e in ex.pedal if e["time_sec"] == 0} == {(64, 127),
                                                                                   (67, 100)}
    assert len(ap.performance.notes) == len(BEATS)  # the source is not modified


# --------------------------------------------------------------------------- engine


def _report():
    bars = [{"index": i, "label": str(i + 1), "start_beat": 4.0 * i} for i in range(N_BARS)]
    return {"piece": {"piece_id": "synth", "title": "Synthetic"},
            "input": {"performance_id": "synth:p", "provenance": "synthetic"}, "bars": bars,
            "issues": [_issue([3], "strong", "interpretation", "tempo", 2.0),
                       _issue([0], "notable"), _issue([7], "notable", magnitude=0.5)]}


@pytest.mark.skipif(not C.ffmpeg_available(), reason="ffmpeg not installed")
def test_engine_end_to_end(tmp_path):
    import soundfile as sf

    user = _manual_ap(_onsets(0.25))
    # the "original recording": the click render, delayed by nothing, at 48 kHz stereo
    y = click_render(user.performance)
    import soxr

    y48 = soxr.resample(y, SR, 48_000)
    wav = tmp_path / "take.wav"
    sf.write(wav, np.stack([y48, y48], axis=1), 48_000)
    inp = CompareInputs(report=_report(), ap=user, references=_refs(), experts=DictExperts(),
                        audio_path=wav, name="synthetic")
    m = build_comparison(inp, tmp_path / "out", CompareConfig(), render=click_render)
    assert (tmp_path / "out" / "manifest.json").is_file()
    assert [w["bars"] for w in m["windows"]] == [[3], [0], [7]]
    w = m["windows"][0]
    assert set(w["clips"]) == {"user_audio", "user_render", "expert_typical", "expert_contrast"}
    assert w["clips"]["expert_typical"]["performance_id"] == "ref:0"
    assert w["clips"]["expert_typical"]["performer"] == "REF:0"
    assert w["clips"]["expert_contrast"]["performance_id"] != "ref:0"
    tm = time_map_from_aligned(user)
    for kind, c in w["clips"].items():
        assert (tmp_path / "out" / c["path"]).stat().st_size > 1000
        assert abs(c["duration_error_ms"]) < 0.1
        # pre-roll = bar 3 (beats 8-12), post-roll = bar 5 (beats 16-20), in each performer's time
        assert len(c["bar_times"]) == 4 and c["bar_times"][0] == 0
        assert c["window_on"] == pytest.approx(c["bar_times"][1])
        assert c["score_span_match" if kind.startswith("expert") else "cut_error_ms"] in (
            1.0, 0.0)  # fmt: skip
        assert abs(c["audio_onset_error_ms"]) <= 50  # a click really is at the window start
        assert abs(c["onset_train_lag_ms"]) <= 10 and c["onset_train_corr"] > 0.5
        dec = C.decode_audio(tmp_path / "out" / c["path"])
        assert abs(len(dec) / SR - c["duration_sec"]) < 0.002
    u = w["clips"]["user_render"]
    assert u["start_sec"] == pytest.approx(tm.at(8.0)) and u["end_sec"] == pytest.approx(
        tm.at(20.0))
    assert abs(w["clips"]["user_audio"]["lag_vs_render_ms"]) <= 12
    assert abs(m["audio"]["user_audio_lag"]["lag_ms"]) <= 12
    # first bar: no bar before it, so a short pad; last bar: runs past the last release
    w0 = m["windows"][1]["clips"]["user_render"]
    assert w0["start_sec"] == 0.0 and len(w0["bar_times"]) == 3
    w7 = m["windows"][2]["clips"]["user_render"]
    assert w7["end_sec"] > float(np.max(user.performance.notes["onset_sec"])) + 0.3
    # loudness matched within a window
    lufs = [C.integrated_loudness(C.decode_audio(tmp_path / "out" / c["path"]))
            for c in w["clips"].values()]
    assert max(lufs) - min(lufs) < 0.5
    # player: self-contained, one embedded clip per manifest clip, no network URLs
    html = player_html(m, tmp_path / "out")
    assert html.count("data:audio/mpeg;base64,") == sum(len(x["clips"]) for x in m["windows"])
    assert not re.search(r"https?://", html)
    payload = html.split("const DATA = ", 1)[1].split(";\n", 1)[0]
    assert len(json.loads(payload)["windows"]) == 3


def test_engine_rejects_a_report_from_another_score(tmp_path):
    rep = _report()
    rep["bars"] = rep["bars"][:-1]
    inp = CompareInputs(report=rep, ap=_manual_ap(_onsets(0.0)))
    with pytest.raises(ValueError, match="do not match"):
        build_comparison(inp, tmp_path, render=click_render)


def test_span_match_tolerates_tuplet_quantisation():
    tb, tp = np.array([354.0, 354.9, 355.2]), np.array([61, 68, 73])
    eb, ep = np.array([356.0, 356.9167, 357.2083, 400.0]), np.array([61, 68, 73, 68])
    assert _span_match(tb, tp, 2.0, eb, ep) == 1.0
    assert _span_match(tb, tp, 0.0, eb, ep) == 0.0
    assert _span_match(tb, np.array([61, 69, 73]), 2.0, eb, ep) == pytest.approx(2 / 3)
