"""Audible A/B comparison engine (P-01): clips for every flagged passage of a practice report.

For each comparison window (:func:`pianolens.compare.windows.select_windows`) the engine makes
up to four clips of the same score span, each with about one bar of pre- and post-roll:

``user_audio``
    The user's own recording, cut at the alignment times (only when an audio file is given;
    MIDI-only input skips it). The performance MIDI must share the audio's time base, which is
    true for a transcription of that audio.
``user_render``
    The user's performance (MIDI or transcription) rendered with the fixed S-02 piano
    (:mod:`pianolens.audio.render`), cut at the same times.
``expert_typical``
    The reference closest to the expert median in this window
    (:func:`pianolens.compare.experts.rank_experts`), rendered with the same piano and cut at
    its own alignment times for the same score span.
``expert_contrast``
    Optional: a reference far from the median but still inside the expert distribution.

**Cut points.** A clip runs from the start of the bar before the window to the end of the bar
after it, in each performer's own time (:mod:`pianolens.compare.timemap`), so rubato is
followed. At the first bar of the piece the pre-roll is ``edge_pad_sec``; at the last bar the
post-roll ends ``edge_pad_sec`` after the last key release. The manifest gives, per clip, the
source start and end, the window's on and off times inside the clip, and the time of every bar
line inside the clip (``bar_times``) so a player can keep position when switching clips.

**Level.** Each window's clips are matched in integrated loudness (BS.1770) and faded in and out
(20 ms); see :mod:`pianolens.compare.clips`. Mono, 44.1 kHz, MP3.

**Checks** (per clip, in the manifest): clip duration vs the requested span; the cut error
(median onset of the window's first score position minus the window-on time in the clip; zero
up to the isotonic smoothing); for the user's audio, the detected audio onset nearest the
window-on time; for experts, the share of the window's score notes found in the expert's score
at the mapped beats (``score_span_match``).

Outputs are for local use only: they can contain personal recordings and non-commercial
reference data (DECISIONS 2026-09-28, the platform). Write them under ``data/interim/``.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import numpy as np

from pianolens.compare import clips as C
from pianolens.compare.experts import ExpertChoice, rank_experts
from pianolens.compare.timemap import TimeMap, time_map_from_aligned
from pianolens.compare.windows import Window, select_windows

__all__ = ["CLIP_KINDS", "SCHEMA", "CompareConfig", "CompareInputs", "ExpertSource",
           "PianoCoReExperts", "build_comparison", "inputs_from_report"]

SCHEMA = "pianolens.compare/1"
CLIP_KINDS = ("user_audio", "user_render", "expert_typical", "expert_contrast")
CLIP_LABELS = {"user_audio": "Your recording", "user_render": "You, same piano",
               "expert_typical": "Typical expert", "expert_contrast": "Another expert"}


class ExpertSource(Protocol):
    """Loads a reference performance (with pedal) by its reference-set performance id."""

    def load(self, performance_id: str) -> Any | None: ...

    def describe(self, performance_id: str) -> dict[str, Any]: ...


class PianoCoReExperts:
    """PianoCoRe tier A performances from the refined zip (``pianolens.data.pianocore``).

    Reference ids are ``pianocore:<row id>``. Each load is about 1 s; results are cached."""

    def __init__(self, root: Path | str | None = None) -> None:
        self._root = root
        self._loader: Any = None
        self._cache: dict[str, Any] = {}

    @property
    def loader(self) -> Any:
        if self._loader is None:
            from pianolens.data.pianocore import PianoCoRe

            self._loader = PianoCoRe() if self._root is None else PianoCoRe(self._root)
        return self._loader

    def _row(self, performance_id: str) -> Any:
        rid = performance_id.split(":", 1)[1] if ":" in performance_id else performance_id
        idx = self.loader.index
        rows = idx[idx["id"] == rid]
        return rows.iloc[0] if len(rows) else None

    def load(self, performance_id: str) -> Any | None:
        if performance_id not in self._cache:
            row = self._row(performance_id)
            try:
                self._cache[performance_id] = None if row is None else self.loader.load(row)
            except Exception:  # noqa: BLE001 - an unreadable reference is skipped
                self._cache[performance_id] = None
        return self._cache[performance_id]

    def describe(self, performance_id: str) -> dict[str, Any]:
        row = self._row(performance_id)
        if row is None:
            return {}
        def txt(k: str) -> str:
            v = row.get(k, "")
            return "" if v is None or (isinstance(v, float) and np.isnan(v)) else str(v)

        return {"performer": txt("performer"), "source_dataset": txt("performance_dataset"),
                "source_performance_id": txt("performance_id"),
                "capture_model": txt("capture_model")}


@dataclass(frozen=True)
class CompareConfig:
    """Settings of :func:`build_comparison`."""

    max_windows: int = 8
    max_bars: int = 4
    merge_gap: int = 1
    min_tier: str = "notable"
    pre_bars: int = 1
    post_bars: int = 1
    edge_pad_sec: float = 0.6
    target_lufs: float = -20.0
    max_peak_dbfs: float = -1.0
    fade_ms: float = C.FADE_MS
    bitrate: str = C.MP3_BITRATE
    contrast: bool = True
    min_coverage: float = 0.8
    min_span_match: float = 0.6
    max_expert_tries: int = 8
    audio_checks: bool = True
    render_lookback_sec: float = 6.0


@dataclass(eq=False)
class CompareInputs:
    """What one comparison is about.

    Attributes:
        report: the report dict (``pianolens.report/1``; ``build_report`` output or its JSON).
        ap: the target ``AlignedPerformance`` the report was built from (performed score).
        references: tier D reference set (target excluded), or None for no expert clips.
        beat_map: target -> reference score beats; None = ``map_score_beats`` on the two
            scores' notes when both are known, else identity.
        experts: loads reference MIDI by id (default :class:`PianoCoReExperts`).
        audio_path: the user's original recording, if any.
        name: output name (folder under ``out_root``).
        report_path: for the manifest.
    """

    report: Mapping[str, Any]
    ap: Any
    references: Any | None = None
    beat_map: Any | None = None
    experts: ExpertSource | None = None
    audio_path: Path | str | None = None
    name: str = "comparison"
    report_path: Path | str | None = None
    source_id: str = ""


# =========================================================================== helpers


def _bar_grid(report: Mapping[str, Any], ap: Any) -> tuple[np.ndarray, np.ndarray, list[str]]:
    """Bar start beats, bar end beats and labels, checked against the aligned score."""
    from pianolens.features.tempo import _beats_per_bar, _measure_info

    bars = report["bars"]
    starts = np.array([float(b["start_beat"]) for b in bars])
    labels = [str(b["label"]) for b in bars]
    _, mb, _ = _measure_info(ap.score)
    mb = np.asarray(mb, float)
    if len(mb) != len(starts) or not np.allclose(mb, starts, atol=1e-6):
        raise ValueError(f"report bars ({len(starts)}) do not match the aligned score's measures "
                         f"({len(mb)}); rebuild the report or pass the same alignment")
    sn = ap.score.notes
    end = float(np.max(sn["onset_beat"] + sn["duration_beat"])) if len(sn) else starts[-1]
    end = max(end, starts[-1] + _beats_per_bar(ap.score))
    ends = np.append(starts[1:], end)
    return starts, ends, labels


def _score_notes(ap: Any) -> tuple[np.ndarray, np.ndarray]:
    sn = ap.score.notes
    g = ~sn["is_grace"].astype(bool) if "is_grace" in (sn.dtype.names or ()) else \
        np.ones(len(sn), bool)
    return sn["onset_beat"][g].astype(float), sn["pitch"][g].astype(int)


def _first_position_onset(ap: Any, b0: float, b1: float) -> tuple[float, float] | None:
    """(score beat, median onset) of the first matched score position in ``[b0, b1)``."""
    from pianolens.features.tempo import matched_onsets

    notes, _ = matched_onsets(ap)
    w = notes[(notes["beat"] >= b0 - 1e-9) & (notes["beat"] < b1 - 1e-9)]
    if w.empty:
        return None
    first = float(w["beat"].min())
    return first, float(w.loc[np.isclose(w["beat"], first), "onset_sec"].median())


def _last_offset(ap: Any) -> float:
    n = ap.performance.notes
    return float(np.max(n["onset_sec"] + n["duration_sec"])) if len(n) else 0.0


def _span(tm: TimeMap, ap: Any, starts: np.ndarray, ends: np.ndarray, i0: int, i1: int,
          cfg: CompareConfig, offset: float = 0.0) -> dict[str, Any]:
    """Clip times for bars ``i0..i1`` (+ pre/post-roll), in one performer's time.

    ``offset`` shifts the target's score beats onto this performer's score (experts)."""
    b0, b1 = starts[i0] + offset, ends[i1] + offset
    t_on, t_off = tm.at(b0), tm.at(b1)
    anchors_b = [starts[i] + offset for i in range(i0, i1 + 1)] + [b1]
    ip = i0 - cfg.pre_bars
    if ip >= 0:
        t_start = tm.at(starts[ip] + offset)
        anchors_b = [starts[i] + offset for i in range(ip, i0)] + anchors_b
    else:
        t_start = max(0.0, t_on - cfg.edge_pad_sec)
    iq = i1 + cfg.post_bars
    if iq < len(ends):
        t_end = tm.at(ends[iq] + offset)
        anchors_b += [ends[i] + offset for i in range(i1 + 1, iq + 1)]
    else:
        t_end = max(t_off, _last_offset(ap)) + cfg.edge_pad_sec
    t_end = max(t_end, t_off + 0.25)
    bar_times = [float(tm.at(b) - t_start) for b in anchors_b]
    return {"start_sec": float(t_start), "end_sec": float(t_end),
            "window_on": float(t_on - t_start), "window_off": float(t_off - t_start),
            "bar_times": bar_times, "score_beats": [float(b0), float(b1)]}  # fmt: skip


def _cut_check(ap: Any, span: dict[str, Any]) -> dict[str, Any]:
    b0, b1 = span["score_beats"]
    fp = _first_position_onset(ap, b0, b1)
    if fp is None:
        return {"first_note_beat": None, "cut_error_ms": None}
    beat, onset = fp
    err = (onset - span["start_sec"]) - span["window_on"]
    # the window can start on a rest: then the expected time is the note's own map time
    return {"first_note_beat": beat, "first_note_in_clip": onset - span["start_sec"],
            "cut_error_ms": 1000 * err if np.isclose(beat, b0) else None}


def _offset_to(bmap: Any, beats: np.ndarray) -> float | None:
    """The most common (reference - target) beat offset over ``beats``."""
    if bmap is None:
        return 0.0
    m = bmap(beats)
    d = np.round(m - beats, 3)
    d = d[np.isfinite(d)]
    if not len(d):
        return None
    u, c = np.unique(d, return_counts=True)
    return float(u[np.argmax(c)])


def _span_match(tb: np.ndarray, tp: np.ndarray, offset: float, eb: np.ndarray, ep: np.ndarray,
                tol: float = 0.125) -> float:
    """Share of the target's window notes (beat + offset, pitch) that the expert's score has
    within ``tol`` beats (scores quantise irregular tuplets differently: 354.9 vs 354.917)."""
    if not len(tb):
        return float("nan")
    q = tb + offset
    near = (eb >= q.min() - 1) & (eb <= q.max() + 1)
    eb, ep = eb[near], ep[near]
    hit = [bool(np.any((ep == p) & (np.abs(eb - b) <= tol))) for b, p in zip(q, tp, strict=True)]
    return float(np.mean(hit))


def excerpt_performance(perf: Any, t0: float, t1: float) -> Any:
    """Notes with onsets in ``[t0, t1)`` and the pedal from ``t0``, shifted so ``t0`` is 0.

    Each controller's last value before ``t0`` is set at 0, so a pedal held into the excerpt
    stays down. Notes struck before ``t0`` are left out (a render loses their ringing)."""
    from dataclasses import replace

    from pianolens.data.types import PEDAL_DTYPE

    n = perf.notes
    keep = (n["onset_sec"] >= t0) & (n["onset_sec"] < t1)
    notes = n[keep].copy()
    notes["onset_sec"] = notes["onset_sec"] - t0
    pd_ = perf.pedal
    rows = []
    if len(pd_):
        before = pd_[pd_["time_sec"] < t0]
        for num in np.unique(before["number"]):
            last = before[before["number"] == num][-1]
            rows.append((0.0, int(num), int(last["value"])))
        for e in pd_[(pd_["time_sec"] >= t0) & (pd_["time_sec"] < t1)]:
            rows.append((float(e["time_sec"]) - t0, int(e["number"]), int(e["value"])))
    pedal = np.array(rows, dtype=PEDAL_DTYPE) if rows else np.zeros(0, PEDAL_DTYPE)
    if len(pedal):
        pedal = pedal[np.argsort(pedal["time_sec"], kind="stable")]
    return replace(perf, notes=notes, pedal=pedal)


def render_span(render: Callable[[Any], np.ndarray], perf: Any, start: float, end: float,
                lookback: float) -> np.ndarray:
    """Rendered audio of ``perf`` over ``[start, end)`` in its own time: an excerpt from
    ``start - lookback`` is rendered and cut, so notes struck in the lookback still ring."""
    a = max(0.0, start - lookback)
    y = render(excerpt_performance(perf, a, end))
    return C.cut(y, start - a, end - a)


# =========================================================================== main


def build_comparison(
    inp: CompareInputs,
    out_dir: Path | str,
    config: CompareConfig | None = None,
    render: Callable[[Any], np.ndarray] | None = None,
    log: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Make the clips and ``manifest.json`` for one report under ``out_dir``.

    ``render`` maps a ``Performance`` to mono float32 audio at 44.1 kHz; the default is the S-02
    renderer (``pianolens.audio.render``, CrescendAI Salamander config at 44.1 kHz). Returns the
    manifest dict (also written to ``out_dir/manifest.json``).
    """
    cfg = config or CompareConfig()
    out_dir = Path(out_dir)
    (out_dir / "clips").mkdir(parents=True, exist_ok=True)
    say = log or (lambda s: None)
    t0 = time.time()
    render_info: dict[str, Any] = {}
    if render is None:
        from dataclasses import replace

        from pianolens.audio import render as R

        rcfg = replace(R.CRESCENDAI_SALAMANDER, sample_rate=C.SAMPLE_RATE)
        render_info = {"renderer": "pianolens.audio.render (S-02)",
                       "soundfont": Path(rcfg.soundfont).name, "config_hash": rcfg.config_hash(),
                       "fluidsynth": R.fluidsynth_version()}  # fmt: skip

        def render(perf: Any) -> np.ndarray:
            return R.render_performance(perf, rcfg).audio

    rep, ap = inp.report, inp.ap
    starts, ends, labels = _bar_grid(rep, ap)
    tm_user = time_map_from_aligned(ap)
    tb_all, tp_all = _score_notes(ap)
    wins = select_windows(rep, cfg.max_windows, cfg.max_bars, cfg.merge_gap, cfg.min_tier)
    say(f"{len(wins)} windows")

    look = cfg.render_lookback_sec
    y_audio = C.load_audio(inp.audio_path) if inp.audio_path else None
    audio_lag = None
    if y_audio is not None and cfg.audio_checks:
        # one 60 s stretch from 30% into the performance: long enough for a stable estimate
        a = 0.3 * _last_offset(ap)
        seg = render_span(render, ap.performance, a, a + 60.0, look)
        lag, corr = C.estimate_lag(seg, C.cut(y_audio, a, a + 60.0))
        audio_lag = {"lag_ms": 1000 * lag, "correlation": corr, "from_sec": a, "length_sec": 60.0,
                     "meaning": "original audio relative to the rendered performance MIDI; "
                                "positive = audio late"}  # fmt: skip
        say(f"audio lag {1000 * lag:+.0f} ms (r={corr:.2f})")

    refs = inp.references
    bmap = inp.beat_map
    target_grid = None
    if refs is not None and len(refs):
        from pianolens.features.interpretation import map_score_beats, target_from_aligned

        target = target_from_aligned(ap, source_id=inp.source_id)
        target_grid = target.grid
        refs = refs.exclude([target.performance_id, inp.source_id])
        if bmap is None and target.score_notes is not None and refs.score_notes is not None:
            bmap = map_score_beats(target.score_notes, refs.score_notes)
    experts = inp.experts if inp.experts is not None else (
        PianoCoReExperts() if refs is not None and len(refs) else None)
    expert_tm: dict[str, TimeMap] = {}

    def expert_clip(order: np.ndarray, choice: ExpertChoice, w: Window, skip: set[str]
                    ) -> tuple[dict[str, Any], np.ndarray] | None:
        tries = 0
        for row in order:
            pid = str(refs.performance_ids[row])
            src = str(refs.source_ids[row])
            if pid in skip or src in skip:
                continue
            if tries >= cfg.max_expert_tries:
                break
            tries += 1
            eap = experts.load(pid) if experts is not None else None
            if eap is None:
                continue
            wmask = (tb_all >= starts[w.first] - 1e-9) & (tb_all < ends[w.last] - 1e-9)
            off = _offset_to(bmap, np.unique(tb_all[wmask]))
            if off is None:
                continue
            eb, ep = _score_notes(eap)
            sm = _span_match(tb_all[wmask], tp_all[wmask], off, eb, ep)
            if not np.isfinite(sm) or sm < cfg.min_span_match:
                continue
            if pid not in expert_tm:
                try:
                    expert_tm[pid] = time_map_from_aligned(eap)
                except ValueError:
                    continue
            sp = _span(expert_tm[pid], eap, starts, ends, w.first, w.last, cfg, offset=off)
            meta = {"performance_id": pid, "source_id": src,
                    "provenance": str(refs.provenance[row]), "beat_offset": off,
                    "score_span_match": sm, **choice.info(int(row)),
                    **(experts.describe(pid) if experts is not None else {}),
                    **_cut_check(eap, sp)}  # fmt: skip
            meta["_perf"] = eap.performance
            return {**sp, **meta}, render_span(render, eap.performance, sp["start_sec"],
                                               sp["end_sec"], look)
        return None

    windows_out = []
    for k, w in enumerate(wins):
        wid = f"w{k + 1:02d}"
        sp = _span(tm_user, ap, starts, ends, w.first, w.last, cfg)
        raw: dict[str, np.ndarray] = {}
        meta: dict[str, dict[str, Any]] = {}
        chk = _cut_check(ap, sp)
        if y_audio is not None:
            raw["user_audio"] = C.cut(y_audio, sp["start_sec"], sp["end_sec"])
            meta["user_audio"] = {**sp, **chk, "source": str(inp.audio_path)}
        raw["user_render"] = render_span(render, ap.performance, sp["start_sec"], sp["end_sec"],
                                         look)
        meta["user_render"] = {**sp, **chk, "source": "rendered performance"}
        choice_info: dict[str, Any] = {}
        if refs is not None and len(refs) and target_grid is not None:
            lo = starts[max(w.first - cfg.pre_bars, 0)]
            hi = ends[min(w.last + cfg.post_bars, len(ends) - 1)]
            cols = target_grid[(target_grid >= lo - 1e-9) & (target_grid < hi - 1e-9)]
            choice = rank_experts(refs, cols, bmap, cfg.min_coverage)
            choice_info = {"n_eligible": choice.n_eligible, "n_references": choice.n_references,
                           "n_columns": len(cols)}
            got = expert_clip(choice.typical_order(), choice, w, set())
            if got is not None:
                meta["expert_typical"], raw["expert_typical"] = got
                if cfg.contrast:
                    skip = {meta["expert_typical"]["performance_id"],
                            meta["expert_typical"]["source_id"]}
                    got2 = expert_clip(choice.contrast_order(), choice, w, skip)
                    if got2 is not None:
                        meta["expert_contrast"], raw["expert_contrast"] = got2
        # level, fades, encode
        faded = {kk: C.apply_fades(v, C.SAMPLE_RATE, cfg.fade_ms) for kk, v in raw.items()}
        matched, loud = C.match_loudness(faded, cfg.target_lufs, cfg.max_peak_dbfs)
        clips_out = {}
        for kind in CLIP_KINDS:
            if kind not in matched:
                continue
            y = matched[kind]
            rel = Path("clips") / f"{wid}_{kind}.mp3"
            C.encode_mp3(y, out_dir / rel, C.SAMPLE_RATE, cfg.bitrate)
            m = dict(meta[kind])
            perf = m.pop("_perf", ap.performance)
            expected = m["end_sec"] - m["start_sec"]
            entry = {"label": CLIP_LABELS[kind], "path": rel.as_posix(),
                     "duration_sec": len(y) / C.SAMPLE_RATE, "expected_duration_sec": expected,
                     "duration_error_ms": 1000 * (len(y) / C.SAMPLE_RATE - expected),
                     **m, **loud[kind]}  # fmt: skip
            if cfg.audio_checks:
                on = C.nearest_onset(y, m.get("first_note_in_clip", m["window_on"]))
                entry["audio_onset_in_clip"] = on
                entry["audio_onset_error_ms"] = None if on is None or \
                    m.get("first_note_in_clip") is None else \
                    1000 * (on - m["first_note_in_clip"])
            if cfg.audio_checks:
                pn = perf.notes
                inside = (pn["onset_sec"] >= m["start_sec"]) & (pn["onset_sec"] < m["end_sec"])
                lag, corr = C.onset_train_lag(y, pn["onset_sec"][inside] - m["start_sec"],
                                              pn["velocity"][inside].astype(float))
                entry["onset_train_lag_ms"], entry["onset_train_corr"] = 1000 * lag, corr
            if cfg.audio_checks and kind == "user_audio":
                lag, corr = C.estimate_lag(matched["user_render"], y, max_lag_sec=0.5)
                entry["lag_vs_render_ms"], entry["lag_vs_render_corr"] = 1000 * lag, corr
            clips_out[kind] = entry
        windows_out.append({
            "id": wid, "bars": w.bars, "bars_label": w.label(labels), "tier": w.tier,
            "truncated": w.truncated, "reasons": w.reasons, "expert_choice": choice_info,
            "window_body_sec": {k2: v["window_off"] - v["window_on"]
                                for k2, v in clips_out.items()},
            "clips": clips_out,
        })  # fmt: skip
        say(f"{wid} {w.label(labels)} {w.tier}: {', '.join(clips_out)}")

    manifest = {
        "schema": SCHEMA,
        "generated": time.strftime("%Y-%m-%d"),
        "name": inp.name,
        "report": {"path": str(inp.report_path) if inp.report_path else None,
                   "piece_id": rep.get("piece", {}).get("piece_id"),
                   "title": rep.get("piece", {}).get("title"),
                   "performance_id": rep.get("input", {}).get("performance_id"),
                   "provenance": rep.get("input", {}).get("provenance"),
                   "n_bars": len(starts)},
        "audio": {"sample_rate": C.SAMPLE_RATE, "channels": 1, "format": "mp3",
                  "bitrate": cfg.bitrate, "fade_ms": cfg.fade_ms,
                  "target_lufs": cfg.target_lufs, "max_peak_dbfs": cfg.max_peak_dbfs,
                  "user_audio": str(inp.audio_path) if inp.audio_path else None,
                  "user_audio_lag": audio_lag, **render_info},
        "references": {"n": 0 if refs is None else len(refs),
                       "beat_map_mapped_fraction": None if bmap is None
                       else float(bmap.mapped_fraction)},
        "config": {k: getattr(cfg, k) for k in cfg.__dataclass_fields__},
        "user_time_map": {"n_knots": len(tm_user.beats), "n_dropped": tm_user.n_dropped},
        "windows": windows_out,
        "runtime_sec": time.time() - t0,
        "privacy": "Local only. May contain personal recordings and non-commercial reference "
                   "data; never commit, upload or share.",
    }  # fmt: skip
    (out_dir / "manifest.json").write_text(json.dumps(_jsonable(manifest), indent=1))
    return manifest


def _jsonable(x: Any) -> Any:
    if isinstance(x, dict):
        return {str(k): _jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_jsonable(v) for v in x]
    if isinstance(x, (np.floating, float)):
        v = float(x)
        return v if np.isfinite(v) else None
    if isinstance(x, np.integer):
        return int(x)
    if isinstance(x, np.bool_):
        return bool(x)
    if isinstance(x, Path):
        return str(x)
    return x


# =========================================================================== from files


def inputs_from_report(
    report_json: Path | str,
    audio_path: Path | str | None = None,
    performance: Path | str | None = None,
    score: Path | str | None = None,
    name: str | None = None,
    use_pianocore: bool = True,
    extra_exclude: Sequence[str] = (),
) -> CompareInputs:
    """Rebuild the comparison inputs from a report JSON written by ``write_report``.

    The report records its score and performance paths, piece id, provenance and excluded
    references; the performance is aligned again with ``align_performance`` (deterministic) and
    the bar grid is checked against the report. PianoCoRe references are loaded for the piece
    (same exclusions)."""
    from pianolens.align import align_performance
    from pianolens.report.io import load_performance, load_score

    report_json = Path(report_json)
    rep = json.loads(report_json.read_text())
    paths = rep["input"]["paths"]
    piece_id = rep["piece"]["piece_id"]
    sc = load_score(score or paths["score"], piece_id)
    perf = load_performance(performance or paths["performance"], rep["input"]["provenance"],
                            piece_id, performance_id=rep["input"].get("performance_id"))
    ap = align_performance(sc, perf)
    excl = [*paths.get("excluded_references", []), *extra_exclude]
    refs = None
    if use_pianocore and piece_id:
        from pianolens.data import pianocore_cache as pc
        from pianolens.features.interpretation import load_pianocore_references

        if pc.cache_available():
            refs = load_pianocore_references(piece_id, exclude=excl)
    src = next((e for e in paths.get("excluded_references", []) if e.startswith("ASAP_")), "")
    return CompareInputs(report=rep, ap=ap, references=refs, audio_path=audio_path,
                         name=name or report_json.stem, report_path=report_json, source_id=src)
