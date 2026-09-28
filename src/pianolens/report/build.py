"""Practice report: every number of the F-02..F-06 features for one performance, per bar and
summarized, as one JSON-ready ``dict`` (F-08).

:func:`build_report` takes an aligned performance (and optionally reference performances and
repeated takes) and returns the report data; :mod:`pianolens.report.render` turns it into a
self-contained HTML page and :mod:`pianolens.report.io` does the file loading.

What goes in, per bar (rows of the performed, unfolded ``Score.measures``):

* **Correctness** (F-02, :func:`pianolens.features.correctness.correctness`): wrong-pitch,
  missed and extra notes. Missed notes are reported per bar only (DECISIONS 2026-09-27, after
  F-01). Tiers: see :func:`_correctness_tier`.
* **Tempo and loudness shape vs experts** (F-06, :func:`pianolens.features.interpretation.
  interpret`): the per-bar *total-deviation* flag (DECISIONS 2026-09-28, after F-06), computed
  twice to get the two tiers: "notable" beyond the 95th percentile of out-of-fold expert
  deviations, "strong" beyond the 99th. The same tiers apply to the "too flat" window check.
  Velocity is low-confidence unless target and references are Disklavier / sensor (DECISIONS,
  after D-10); low-confidence velocity issues are shown but never enter "what to practise".
* **Timing steadiness** (F-04 timing noise): residual minus the leave-one-out expert consensus
  fine timing. It is computed here on the F-06 curve convention (F-03 fit without score tempo
  markings) so that target and references are measured identically; bars are tiered against
  the references' own leave-one-out noise at that bar.
* **Pedal blur** and **evenness** (F-04): per bar; tiered only against references on the same
  score (``same_score_refs``), otherwise descriptive. Evenness uses the *strict* run rule
  (sub-beat scales, arpeggios and repeated figures); the broad rule's pooled values are in the
  summary (DECISIONS 2026-09-27: both variants are kept until D-10 / R-04 decide). Evenness is
  compared with the literature only at a similar note rate (landscape 1.5).
* **Shaping** (F-05): structural coherence for velocity and articulation (the H4 primary
  channels, without markings; defined only with at least 3 CV blocks), and per-phrase tempo
  shaping ``concave_excess`` with cadence-derived phrase boundaries (DECISIONS 2026-09-28,
  after D-11 / F-05c). Tempo coherence R² is not reported: it needs annotated phrases
  (DECISIONS, after F-05b).

There is no overall grade and no invented weighting: the rating-model weights come from R-04 /
Phase 3 (plan section 3). Citations are in the feature modules and in
``docs/research/2026-09-27-landscape.md``.
"""

from __future__ import annotations

import datetime as _dt
import math
import warnings
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from typing import Any

import numpy as np
import pandas as pd

from pianolens.features.control import ControlConfig, control_features
from pianolens.features.correctness import correctness
from pianolens.features.interpretation import (
    SENSOR_PROVENANCE,
    InterpretationConfig,
    ReferenceSet,
    interpret,
    map_score_beats,
    merge_references,
    references_from_notes,
    target_from_aligned,
)
from pianolens.features.tempo import _beats_per_bar, _measure_info, matched_onsets, tempo_model
from pianolens.report import calibration as cal

__all__ = ["SCHEMA", "ReportConfig", "ReportInputs", "build_report", "error_signatures",
           "expert_error_keys",           "recurring_errors", "to_jsonable"]

SCHEMA = "pianolens.report/1"
TIERS = ("none", "notable", "strong")
_TIER_RANK = {"none": 0, "notable": 1, "strong": 2}
#: "What to practise" order within a tier: notes first, then control, then the music.
CATEGORY_RANK = {"correctness": 0, "control": 1, "interpretation": 2, "too_flat": 2}


@dataclass(frozen=True)
class ReportConfig:
    """Settings of :func:`build_report`.

    Attributes:
        interpretation: F-06 config (``flag_quantile`` is overridden by the two tiers).
        control: F-04 config.
        n_practise: items in "what to practise".
        min_tier_references: fewer references -> a value is shown but not tiered.
        coherence_min_blocks: structural coherence is reported only with this many CV blocks.
        shaping: run the F-05 shaping part (slowest part on long pieces).
        recurring_min_takes: an error key found in at least this many takes (the target
            included) is a recurring error, and its bar a "strong" correctness item.
        recurring_kinds: error kinds that can recur (``wrong_pitch``, ``missed``, ``extra``).
        recurring_min_experts: expert performances of the same score (``correctness_refs``
            plus ``same_score_refs``) needed to filter checker artefacts; with fewer, recurring
            errors are listed but not promoted.
    """

    interpretation: InterpretationConfig = field(default_factory=InterpretationConfig)
    control: ControlConfig = field(default_factory=ControlConfig)
    n_practise: int = 3
    min_tier_references: int = cal.MIN_TIER_REFERENCES
    coherence_min_blocks: int = 3
    shaping: bool = True
    recurring_min_takes: int = cal.RECURRING_MIN_TAKES
    recurring_kinds: tuple[str, ...] = cal.RECURRING_KINDS
    recurring_min_experts: int = cal.RECURRING_MIN_EXPERTS


@dataclass(eq=False)
class ReportInputs:
    """What one report is about.

    Attributes:
        ap: the target ``AlignedPerformance`` (from ``align_performance``; its score is the
            performed score).
        piece_id, title: for the header.
        provenance: capture method of the target (``disklavier``, ``sensor``, ``transcribed``,
            ``synthetic`` or ``unknown``).
        source_id: id of the target inside the reference set, if it is there (leave-one-out).
        references: tier D reference set (e.g. PianoCoRe via ``load_pianocore_references``).
        same_score_refs: other performances aligned to the *same* performed score (same repeat
            path): used for timing consensus, pedal and evenness tiers, and merged into the
            tier D references (mapped onto their score when ``references`` is given).
        same_score_provenance: capture method of ``same_score_refs``.
        takes: repeated takes of the same passage by the same player (aligned performances).
        correctness_refs: expert performances aligned to the same score and repeat path, used
            only to remove checker artefacts from recurring errors (with ``same_score_refs``).
        paths: file paths for the header (``score``, ``performance``, ``takes``, ...).
        notes: extra provenance notes for the header.
    """

    ap: Any
    piece_id: str | None = None
    title: str = ""
    provenance: str = "unknown"
    source_id: str = ""
    references: ReferenceSet | None = None
    same_score_refs: Sequence[Any] = ()
    same_score_provenance: str = "unknown"
    takes: Sequence[Any] = ()
    correctness_refs: Sequence[Any] = ()
    paths: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


# =========================================================================== helpers


def to_jsonable(x: Any) -> Any:
    """Recursively convert numpy / pandas values to JSON types; NaN and inf become None."""
    if isinstance(x, dict):
        return {str(k): to_jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [to_jsonable(v) for v in x]
    if isinstance(x, np.ndarray):
        return [to_jsonable(v) for v in x.tolist()]
    if isinstance(x, (np.bool_, bool)):
        return bool(x)
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (float, np.floating)):
        v = float(x)
        return v if math.isfinite(v) else None
    if x is pd.NA or x is None:
        return None
    if isinstance(x, (int, str)):
        return x
    return str(x)


def _f(x: Any) -> float:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return float("nan")
    return v


def _tier(value: float, q95: float, q99: float) -> str:
    """Tier of a value against the reference quantiles (larger = further from the experts)."""
    if not (np.isfinite(value) and np.isfinite(q95)):
        return "none"
    if np.isfinite(q99) and value > q99:
        return "strong"
    return "notable" if value > q95 else "none"


def _quantiles(ref_values: np.ndarray, min_n: int) -> tuple[float, float, int]:
    v = np.asarray(ref_values, float)
    v = v[np.isfinite(v)]
    if len(v) < min_n:
        return float("nan"), float("nan"), len(v)
    return (float(np.quantile(v, cal.NOTABLE_Q)), float(np.quantile(v, cal.STRONG_Q)), len(v))


def bar_labels(score: Any) -> list[str]:
    """Printed bar label per measure row; a repeated bar gets a pass suffix (``"12 (2)"``)."""
    ms = score.measures
    seen: dict[str, int] = {}
    out = []
    for m in ms:
        lab = str(m["name"]).strip() or str(int(m["number"]))
        seen[lab] = seen.get(lab, 0) + 1
        out.append(lab if seen[lab] == 1 else f"{lab} ({seen[lab]})")
    return out


def span_label(labels: Sequence[str], idx: Sequence[int]) -> str:
    """"bar 12" or "bars 12-14" for consecutive measure rows."""
    if len(idx) == 0:
        return ""
    a, b = labels[idx[0]], labels[idx[-1]]
    return f"bar {a}" if a == b else f"bars {a}-{b}"


def _bar_of(beats: np.ndarray, bar_starts: np.ndarray) -> np.ndarray:
    if len(bar_starts) == 0:
        return np.zeros(len(beats), int)
    return np.maximum(np.searchsorted(bar_starts, np.asarray(beats) + 1e-9, side="right") - 1, 0)


# =========================================================================== references


def _matched_notes(ap: Any) -> pd.DataFrame:
    notes, _ = matched_onsets(ap)
    return notes


def refs_from_aligned(
    aps: Sequence[Any], provenance: str, grid: np.ndarray, pos_grid: np.ndarray,
    bar_starts: np.ndarray, beats_per_bar: float, piece_id: str,
    config: InterpretationConfig, beat_map: Any | None = None,
) -> ReferenceSet:
    """Tier D references from aligned performances of the target's score, on a given grid.

    With ``beat_map`` (target score beats -> reference score beats) the note beats are mapped
    first and notes outside the mapped material are dropped."""
    perfs = []
    for r in aps:
        n = _matched_notes(r)
        b = n["beat"].to_numpy(float)
        if beat_map is not None:
            b = beat_map(b)
        ok = np.isfinite(b)
        perfs.append({"performance_id": str(r.performance.performance_id),
                      "provenance": provenance, "beats": b[ok],
                      "onsets_sec": n["onset_sec"].to_numpy(float)[ok],
                      "velocities": n["vel_midi"].to_numpy(float)[ok]})  # fmt: skip
    return references_from_notes(piece_id, perfs, grid, pos_grid, bar_starts, beats_per_bar,
                                 config)


def _tier_d_references(inp: ReportInputs, target: Any, cfg: ReportConfig
                       ) -> tuple[ReferenceSet | None, Any, dict[str, Any]]:
    """The tier D reference set, the target -> reference beat map, and a description."""
    icfg = cfg.interpretation
    same = list(inp.same_score_refs)
    info: dict[str, Any] = {"pianocore": 0, "same_score": len(same)}
    refs = inp.references
    if refs is not None and len(refs):
        info["pianocore"] = len(refs)
        bmap = map_score_beats(target.score_notes, refs.score_notes) \
            if refs.score_notes is not None else None
        if same:
            extra = refs_from_aligned(same, inp.same_score_provenance, refs.grid, refs.pos_grid,
                                      refs.bar_starts, refs.beats_per_bar, refs.piece_id, icfg,
                                      beat_map=bmap)
            extra.score_notes = None
            refs = merge_references(refs, extra)
        if bmap is not None:
            info["beat_map_mapped_fraction"] = float(bmap.mapped_fraction)
        return refs, bmap, info
    if same:
        sn = inp.ap.score.notes
        g = ~sn["is_grace"].astype(bool) if "is_grace" in (sn.dtype.names or ()) else \
            np.ones(len(sn), bool)
        pos = np.unique(np.round(sn["onset_beat"][g].astype(float), 6))
        refs = refs_from_aligned(same, inp.same_score_provenance, target.grid, pos,
                                 target.bar_starts, _beats_per_bar(inp.ap.score),
                                 inp.piece_id or "", icfg)
        refs.score_notes = target.score_notes  # same object: interpret uses the identity map
        return refs, None, info
    return None, None, info


def _timing_matrix(refs: ReferenceSet, target: Any, bmap: Any) -> np.ndarray:
    """Reference residual timing (``dev_beats``) at the target's score positions."""
    tp = target.pos_grid
    mp = bmap(tp) if bmap is not None else tp
    j = np.searchsorted(refs.pos_grid, mp - 1e-6)
    jj = np.clip(j, 0, max(len(refs.pos_grid) - 1, 0))
    ok = np.isfinite(mp) & (j < len(refs.pos_grid))
    if len(refs.pos_grid):
        ok &= np.isclose(refs.pos_grid[jj], mp, atol=1e-6)
    X = np.full((len(refs), len(tp)), np.nan)
    X[:, ok] = refs.timing[:, jj[ok]]
    return X


def timing_noise_bars(target_timing: np.ndarray, X: np.ndarray, bar: np.ndarray, n_bars: int,
                      min_refs: int = 3, min_tier: int = cal.MIN_TIER_REFERENCES
                      ) -> tuple[pd.DataFrame, dict[str, float]]:
    """F-04 timing noise of the target and of each reference (leave-one-out), per bar.

    ``target_timing``: target ``dev_beats`` per position (NaN = outlier / unmatched); ``X``:
    references x positions. Consensus = mean of the references where at least ``min_refs``
    have a value. A reference's own noise uses the mean of the *other* references.
    Returns per-bar ``noise_rms_beats`` (target), ``ref_q95`` / ``ref_q99`` / ``n_refs`` and a
    summary (RMS over all positions, consensus R², coverage).
    """
    n = np.isfinite(X).sum(axis=0)
    S = np.nansum(X, axis=0)
    with np.errstate(invalid="ignore", divide="ignore"):
        cons = np.where(n >= min_refs, S / np.maximum(n, 1), np.nan)
        loo = np.where(np.isfinite(X) & (n - 1 >= min_refs), (S - np.nan_to_num(X)) /
                       np.maximum(n - 1, 1), np.nan)
    tn = target_timing - cons
    rn = X - loo
    rows = []
    for b in range(n_bars):
        m = bar == b
        t = tn[m]
        t = t[np.isfinite(t)]
        trms = float(np.sqrt(np.mean(t ** 2))) if len(t) else np.nan
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            rr = np.sqrt(np.nanmean(rn[:, m] ** 2, axis=1)) if m.any() else np.zeros(0)
        q95, q99, k = _quantiles(rr, min_tier)
        rows.append({"measure_index": b, "noise_rms_beats": trms, "n_positions": len(t),
                     "ref_q95": q95, "ref_q99": q99, "n_refs": k})
    ok = np.isfinite(tn)
    dev = target_timing[ok]
    summ = {
        "noise_rms_beats": float(np.sqrt(np.mean(tn[ok] ** 2))) if ok.any() else np.nan,
        "coverage": float(ok.sum() / max(np.isfinite(target_timing).sum(), 1)),
        "consensus_r2": float(1 - np.mean(tn[ok] ** 2) / np.mean(dev ** 2))
        if ok.any() and np.mean(dev ** 2) > 0 else np.nan,
        "n_refs_median": float(np.median(n[ok])) if ok.any() else 0.0,
    }
    return pd.DataFrame(rows), summ


# =========================================================================== sections


def _correctness_tier(n_wrong: int, n_missed_extra: int, n_notes: int) -> tuple[str, float]:
    """Tier of a bar's correctness errors, and its magnitude (multiple of the notable limit).

    Both quantities are compared with what the same pipeline reports on clean expert playing
    (``calibration.CORRECTNESS_EXPERT_BARS``), with the report's two tiers: notable beyond the
    experts' 95th percentile, strong beyond the 99th. So a single wrong note is shown in the
    timeline but not tiered (7% of expert bars have one); two wrong notes are notable and three
    strong. The bar tier is the higher of the wrong-pitch and the missed + extra tiers.
    """
    c = cal.CORRECTNESS_EXPERT_BARS
    rate = n_missed_extra / n_notes if n_notes > 0 else float("nan")
    t1 = _tier(float(n_wrong), c["wrong_pitch_q95"], c["wrong_pitch_q99"])
    t2 = _tier(rate, c["missed_extra_per_note_q95"], c["missed_extra_per_note_q99"])
    tier = max(t1, t2, key=_TIER_RANK.get)
    mag = max(n_wrong / c["wrong_pitch_q95"],
              rate / c["missed_extra_per_note_q95"] if np.isfinite(rate) else 0.0)
    return tier, float(mag)


def _correctness_section(ap: Any, labels: list[str]) -> tuple[dict, pd.DataFrame, Any]:
    c = correctness(ap)
    b = c.bars.copy()
    b["n_missed_extra"] = b["n_missed"] + b["n_extra"]
    tiers = [_correctness_tier(int(w), int(me), int(n)) for w, me, n in zip(
        b["n_wrong_pitch"], b["n_missed_extra"], b["n_score_notes"], strict=True)]
    b["tier"] = [t for t, _ in tiers]
    b["magnitude"] = [m for _, m in tiers]
    s = dict(c.summary)
    s["n_bars_strong"] = int((b["tier"] == "strong").sum())
    s["n_bars_notable"] = int((b["tier"] == "notable").sum())
    s["expert_calibration"] = dict(cal.CORRECTNESS_EXPERT_BARS)
    er = _f(s.get("error_rate"))
    s["error_rate_tier"] = _tier(er, cal.CORRECTNESS_EXPERT_BARS["error_rate_q95"],
                                 cal.CORRECTNESS_EXPERT_BARS["error_rate_q99"])
    return s, b, c


def _interpretation_section(inp: ReportInputs, target: Any, refs: ReferenceSet, bmap: Any,
                            cfg: ReportConfig, n_bars: int) -> dict[str, Any]:
    icfg = cfg.interpretation
    r95 = interpret(target, refs, bmap, replace(icfg, flag_quantile=cal.NOTABLE_Q))
    r99 = interpret(target, refs, bmap, replace(icfg, flag_quantile=cal.STRONG_Q))
    out: dict[str, Any] = {"meta": {k: v for k, v in r95.meta.items()
                                    if k not in ("references", "beat_map_segments")},
                           "features": r95.features}
    vconf = r95.meta.get("velocity_confidence", "low")
    if target.provenance not in SENSOR_PROVENANCE:
        vconf = "low"
    out["velocity_confidence"] = vconf
    # per bar, per block
    bars: dict[str, pd.DataFrame] = {}
    for block in ("tempo", "velocity"):
        a = r95.bars[r95.bars["block"] == block].set_index("bar")
        z = r99.bars[r99.bars["block"] == block].set_index("bar")
        df = pd.DataFrame({"measure_index": np.arange(n_bars)})
        for col in ("dev_rms", "dev_rms_q", "dev_mean", "abs_target", "abs_lo", "abs_mid",
                    "abs_hi", "window"):
            df[col] = a[col].reindex(df["measure_index"]).to_numpy(float) if col in a \
                else np.nan
        df = df.rename(columns={"dev_rms_q": "q95"})
        df["q99"] = z["dev_rms_q"].reindex(df["measure_index"]).to_numpy(float) \
            if "dev_rms_q" in z else np.nan
        df["tier"] = [_tier(v, q5, q9) for v, q5, q9 in zip(df["dev_rms"], df["q95"], df["q99"],
                                                            strict=True)]
        with np.errstate(invalid="ignore", divide="ignore"):
            df["magnitude"] = df["dev_rms"] / df["q95"]
        bars[block] = df
    out["bars"] = bars
    # windows: typicality and too flat / too extreme, two tiers
    w95 = r95.windows.copy()
    w99 = r99.windows.set_index(["block", "window"])
    wins = []
    for _, w in w95.iterrows():
        key = (w["block"], w["window"])
        flat99 = bool(w99.loc[key, "too_flat"]) if key in w99.index and \
            "too_flat" in w99 and pd.notna(w99.loc[key, "too_flat"]) else False
        ext99 = bool(w99.loc[key, "too_extreme"]) if key in w99.index and \
            "too_extreme" in w99 and pd.notna(w99.loc[key, "too_extreme"]) else False
        flat95 = bool(w.get("too_flat")) if pd.notna(w.get("too_flat")) else False
        ext95 = bool(w.get("too_extreme")) if pd.notna(w.get("too_extreme")) else False
        bw = r95.bars[(r95.bars["block"] == w["block"]) & (r95.bars["window"] == w["window"])]
        wins.append({
            "block": w["block"], "window": int(w["window"]),
            "bars": sorted(int(x) for x in bw["bar"].unique()), "status": w.get("status"),
            "typicality_pct": _f(w.get("typicality_pct")), "magnitude": _f(w.get("magnitude")),
            "magnitude_ref_median": _f(w.get("magnitude_ref_median")),
            "magnitude_pct": _f(w.get("magnitude_pct")), "n_refs": _f(w.get("n_refs")),
            "k_shared": _f(w.get("k_shared")),
            "individual_share": _f(w.get("individual_share")),
            "flat_tier": "strong" if flat99 else ("notable" if flat95 else "none"),
            "extreme_tier": "strong" if ext99 else ("notable" if ext95 else "none"),
        })  # fmt: skip
    out["windows"] = wins
    # curves on the target's beat grid, in display units (level-aligned shape + expert level)
    curves = {}
    for block in ("tempo", "velocity"):
        bt = r95.beats[r95.beats["block"] == block]
        mid = bt["abs_mid"].to_numpy(float)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            if block == "tempo":
                level = float(np.exp(np.nanmedian(np.log(mid)))) if np.isfinite(mid).any() \
                    else float(target.tempo_bpm)

                def conv(x, level=level):
                    return level * np.exp(x)
            else:
                level = float(np.nanmedian(mid)) if np.isfinite(mid).any() else 64.0

                def conv(x, level=level):
                    return level + x
        curves[block] = {
            "beat": bt["beat"].to_numpy(float), "measure_index": bt["bar"].to_numpy(int),
            "target": conv(bt["target"].to_numpy(float)),
            "lo": conv(bt["band_lo"].to_numpy(float)), "mid": conv(bt["band_mid"].to_numpy(float)),
            "hi": conv(bt["band_hi"].to_numpy(float)), "level": level,
            "abs_target": bt["abs_target"].to_numpy(float),
            "n_refs": bt["n_refs"].to_numpy(int),
            "unit": "score beats per minute" if block == "tempo" else "MIDI velocity",
        }  # fmt: skip
    out["curves"] = curves
    # overall tempo against the references, over the same (mapped) beats
    from pianolens.features.interpretation import _interp_rows

    rr = refs.exclude([target.performance_id, target.source_id])
    rb = bmap(target.grid) if bmap is not None else target.grid
    lt = np.log(target.tempo_bpm) + target.tempo
    LR = np.log(rr.tempo_bpm)[:, None] + _interp_rows(rr.tempo, rr.grid, rb)
    cols = np.isfinite(lt) & (np.isfinite(LR).mean(axis=0) >= 0.5) if len(rr) else \
        np.zeros(len(lt), bool)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        tb = float(np.exp(np.mean(lt[cols]))) if cols.any() else float(target.tempo_bpm)
        rt = np.exp(np.nanmean(LR[:, cols], axis=1)) if cols.any() else rr.tempo_bpm
    rt = rt[np.isfinite(rt)]
    out["tempo_overall"] = {
        "target_bpm": tb, "n_beats": int(cols.sum()),
        "ref_q10": float(np.quantile(rt, 0.1)) if len(rt) else np.nan,
        "ref_median": float(np.median(rt)) if len(rt) else np.nan,
        "ref_q90": float(np.quantile(rt, 0.9)) if len(rt) else np.nan,
        "pct_refs_slower": float(np.mean(rt < tb)) if len(rt) else np.nan,
        "n_refs": len(rt),
    }  # fmt: skip
    return out


def _shaping_section(ap: Any, tc: Any, cfg: ReportConfig, errors: dict[str, str]) -> dict:
    from pianolens.features.score_basis import BasisConfig, score_basis
    from pianolens.features.shaping import (
        dynamic_compliance,
        phrase_tempo_shaping,
        structural_coherence,
        voicing,
    )

    out: dict[str, Any] = {}
    basis = None
    try:
        basis = score_basis(ap.score)
    except Exception as e:  # noqa: BLE001 - record, never fatal
        errors["score_basis"] = repr(e)
        return out
    try:
        coh = structural_coherence(ap, basis, tc).summary.set_index("channel")
        for ch in ("velocity", "articulation"):
            if ch in coh.index:
                nb = int(coh.loc[ch, "n_blocks"]) if "n_blocks" in coh else 0
                ok = nb >= cfg.coherence_min_blocks
                out[f"coherence_{ch}"] = {
                    "r2_no_markings": _f(coh.loc[ch, "r2_no_markings"]) if ok else np.nan,
                    "r2_with_markings": _f(coh.loc[ch, "r2"]) if ok else np.nan,
                    "n_blocks": nb, "defined": ok, "unit": str(coh.loc[ch, "unit"])
                    if "unit" in coh else ""}  # fmt: skip
    except Exception as e:  # noqa: BLE001
        errors["coherence"] = repr(e)
    try:
        bc = score_basis(ap.score, config=BasisConfig(phrase_source="cadence"))
        starts = bc.phrases["start_beat"].tolist()
        pts = phrase_tempo_shaping(ap, starts, tempo=tc, basis=bc)
        out["phrase_tempo"] = {k: _f(v) for k, v in pts.summary.items()}
        out["phrase_tempo"]["boundaries"] = "cadence"
    except Exception as e:  # noqa: BLE001
        errors["phrase_tempo"] = repr(e)
    try:
        out["voicing"] = {k: _f(v) for k, v in voicing(ap, basis, tc).summary.items()}
    except Exception as e:  # noqa: BLE001
        errors["voicing"] = repr(e)
    try:
        out["dynamics"] = {k: _f(v) for k, v in dynamic_compliance(ap, basis, tc).summary.items()}
    except Exception as e:  # noqa: BLE001
        errors["dynamics"] = repr(e)
    return out


def _run_rows(res: Any, labels: list[str], score: Any) -> pd.DataFrame:
    """Strict evenness runs with bar span and literature comparison."""
    runs = res.strict_runs
    notes = res.strict_run_notes
    if runs is None or len(runs) == 0:
        return pd.DataFrame()
    ms = score.measures
    from pianolens.features.correctness import measure_rows

    rows = []
    for _, r in runs.iterrows():
        rn = notes[notes["run"] == r["run"]]
        mi = measure_rows(ms, rn["quarter"].to_numpy(float)) if len(rn) else np.zeros(0, int)
        mi = mi[mi >= 0]
        lo, hi = (int(mi.min()), int(mi.max())) if len(mi) else (-1, -1)
        rate = _f(r["note_rate_nps"])
        lit = [e for e in cal.LITERATURE_EVENNESS if np.isfinite(rate)
               and abs(e["note_rate_nps"] - rate) <= cal.SIMILAR_RATE_REL * rate]
        rows.append({
            "run": int(r["run"]), "staff": int(r["staff"]), "voice": int(r["voice"]),
            "kind": str(r.get("kind", "")), "start_beat": _f(r["start_beat"]),
            "first_bar": lo, "last_bar": hi,
            "bars_label": span_label(labels, [lo, hi]) if lo >= 0 else "",
            "n_iois": int(r["n_iois"]), "note_rate_nps": rate, "ioi_cv": _f(r["ioi_cv"]),
            "vel_sd_midi": _f(r["vel_sd_midi"]),
            "literature_similar_rate": [e["label"] for e in lit],
        })  # fmt: skip
    return pd.DataFrame(rows)


def _control_section(ap: Any, tc: Any, same_refs: list[tuple[Any, Any]], labels: list[str],
                     cfg: ReportConfig, errors: dict[str, str]) -> tuple[dict, pd.DataFrame,
                                                                          pd.DataFrame]:
    res = control_features(ap, tc, references=None, config=cfg.control)
    s = res.summary
    b = res.bars.copy().rename(columns={"measure_idx": "measure_index"})
    runs = _run_rows(res, labels, ap.score)
    nb = len(b)
    # same-score references: per-bar pedal blur and strict evenness, and per-run evenness
    ref_ped, ref_even, ref_runs = [], [], []
    for rap, rtc in same_refs:
        try:
            rr = control_features(rap, rtc, references=None, config=cfg.control)
        except Exception as e:  # noqa: BLE001
            errors[f"control_ref:{rap.performance.performance_id}"] = repr(e)
            continue
        rb = rr.bars
        if len(rb) != nb:
            continue
        if rr.summary.get("pedal_available"):
            ref_ped.append(rb["pedal_blur_fraction"].to_numpy(float))
        ref_even.append(rb["even_strict_ioi_cv"].to_numpy(float))
        if len(rr.strict_runs):
            ref_runs.append(rr.strict_runs.set_index(["staff", "voice", "start_beat"]))
    n_min = cfg.min_tier_references
    ped_t, even_t = [], []
    for i in range(nb):
        v = _f(b.loc[i, "pedal_blur_fraction"])
        q5, q9, k = _quantiles(np.array([r[i] for r in ref_ped]), n_min) if ref_ped else \
            (np.nan, np.nan, 0)
        t = _tier(v, q5, q9) if v > 0 else "none"
        ped_t.append((t, q5, q9, k, v / q5 if q5 and np.isfinite(q5) and q5 > 0 else
                      (np.inf if t != "none" else np.nan)))
        v = _f(b.loc[i, "even_strict_ioi_cv"])
        q5, q9, k = _quantiles(np.array([r[i] for r in ref_even]), n_min) if ref_even else \
            (np.nan, np.nan, 0)
        t = _tier(v, q5, q9)
        even_t.append((t, q5, q9, k, v / q5 if np.isfinite(q5) and q5 > 0 else np.nan))
    for name, tt in (("pedal", ped_t), ("evenness", even_t)):
        b[f"{name}_tier"] = [x[0] for x in tt]
        b[f"{name}_ref_q95"] = [x[1] for x in tt]
        b[f"{name}_ref_q99"] = [x[2] for x in tt]
        b[f"{name}_n_refs"] = [x[3] for x in tt]
        b[f"{name}_magnitude"] = [x[4] for x in tt]
    if len(runs) and ref_runs:
        q5s, q9s, ks = [], [], []
        for _, r in runs.iterrows():
            key = (r["staff"], r["voice"], round(r["start_beat"], 6))
            vals = []
            for rr in ref_runs:
                idx = [(a, c, round(d, 6)) for a, c, d in rr.index]
                if key in idx:
                    vals.append(float(rr["ioi_cv"].iloc[idx.index(key)]))
            q5, q9, k = _quantiles(np.array(vals), n_min)
            q5s.append(q5)
            q9s.append(q9)
            ks.append(k)
        runs["ref_q95"], runs["ref_q99"], runs["n_refs"] = q5s, q9s, ks
        runs["tier"] = [_tier(v, a, c) for v, a, c in zip(runs["ioi_cv"], q5s, q9s, strict=True)]
    elif len(runs):
        runs["ref_q95"] = runs["ref_q99"] = np.nan
        runs["n_refs"] = 0
        runs["tier"] = "none"
    summ = {k: s.get(k) for k in (
        "even_ioi_cv", "even_vel_sd_midi", "even_note_rate_nps", "even_n_runs",
        "even_share_of_onsets", "even_strict_ioi_cv", "even_strict_vel_sd_midi",
        "even_strict_note_rate_nps", "even_strict_n_runs", "even_strict_share_of_onsets",
        "hand_async_mean_ms", "hand_async_median_ms", "hand_async_sd_ms", "hand_async_vel_slope_ms",
        "hand_async_resid_sd_ms", "tempo_instability_log_sd", "tempo_drift_log",
        "pedal_available", "pedal_blur_fraction", "pedal_blur_beats", "pedal_down_fraction",
        "n_harmony_changes", "jitter_nometric_rms_ms")}  # fmt: skip
    summ["n_pedal_references"] = len(ref_ped)
    summ["n_evenness_references"] = len(ref_even)
    return summ, b, runs


def error_signatures(cr: Any, labels: Sequence[str]) -> dict[str, set[tuple]]:
    """The correctness errors of one take, per bar label, as keys comparable across takes.

    ``cr``: a :class:`pianolens.features.correctness.CorrectnessResult`; ``labels``: bar labels
    of the take's performed score (:func:`bar_labels`). Keys: ``("wrong_pitch", score note id,
    played pitch)``, ``("missed", score note id)`` and ``("extra", played pitch)``. Two takes of
    the same passage share score note ids when they take the same repeat path, so an identical
    key in two takes is the same mistake at the same place.
    """
    out: dict[str, set[tuple]] = {}
    nl = len(labels)

    def add(bar: int, key: tuple) -> None:
        if 0 <= bar < nl:
            out.setdefault(labels[bar], set()).add(key)

    n = cr.notes
    for r in n[n["label"] == "wrong_pitch"].itertuples():
        add(int(r.measure_index), ("wrong_pitch", str(r.score_id), int(r.pitch)))
    for r in n[n["label"] == "extra"].itertuples():
        add(int(r.measure_index), ("extra", int(r.pitch)))
    sn = cr.score_notes
    for r in sn[sn["label"] == "missed"].itertuples():
        add(int(r.measure_index), ("missed", str(r.score_id)))
    return out


def expert_error_keys(signatures: Sequence[dict[str, set[tuple]]], min_count: int = 1
                      ) -> dict[str, set[tuple]]:
    """Error keys reported for at least ``min_count`` expert performances of the same score
    (same repeat path), per bar label. On the calibration set most errors that recur across a
    player's takes are also reported for other pianists at the same note: they are checker or
    score artefacts, not a learned mistake (``scripts/calibrate_recurring_f08b.py``)."""
    cnt: dict[str, dict[tuple, int]] = {}
    for sig in signatures:
        for lab, keys in sig.items():
            d = cnt.setdefault(lab, {})
            for k in keys:
                d[k] = d.get(k, 0) + 1
    return {lab: {k for k, c in d.items() if c >= min_count} for lab, d in cnt.items()}


def recurring_errors(signatures: Sequence[dict[str, set[tuple]]], min_takes: int,
                     kinds: Sequence[str] = cal.RECURRING_KINDS,
                     exclude: dict[str, set[tuple]] | None = None
                     ) -> dict[str, dict[tuple, int]]:
    """Error keys (of the given kinds) found in at least ``min_takes`` takes, per bar label,
    with the number of takes that have each. Keys in ``exclude`` (per bar label, e.g. from
    :func:`expert_error_keys`) never count."""
    cnt: dict[str, dict[tuple, int]] = {}
    ex = exclude or {}
    for sig in signatures:
        for lab, keys in sig.items():
            for k in keys:
                if k[0] in kinds and k not in ex.get(lab, ()):
                    d = cnt.setdefault(lab, {})
                    d[k] = d.get(k, 0) + 1
    return {lab: {k: c for k, c in d.items() if c >= min_takes} for lab, d in cnt.items()
            if any(c >= min_takes for c in d.values())}


def _describe_error(key: tuple, score_pitch: dict[str, int]) -> str:
    from pianolens.report.text import pitch_name

    if key[0] == "wrong_pitch":
        sp = score_pitch.get(key[1])
        return (f"{pitch_name(key[2])} instead of {pitch_name(sp)}" if sp is not None
                else f"wrong note {pitch_name(key[2])}")
    if key[0] == "missed":
        sp = score_pitch.get(key[1])
        return f"missed {pitch_name(sp)}" if sp is not None else "missed note"
    return f"extra {pitch_name(key[1])}"


def _takes_section(main_cr: Any, takes: Sequence[Any], labels: list[str], cfg: ReportConfig,
                   errors: dict[str, str], experts: Sequence[Any] = ()) -> dict[str, Any]:
    """Per-take correctness and tempo, and errors that recur across takes.

    A recurring error is the same error key (:func:`error_signatures`) in the same bar in at
    least ``cfg.recurring_min_takes`` takes (the target counts as a take), of a kind in
    ``cfg.recurring_kinds``, and not reported for any of the ``experts`` (aligned expert
    performances of the same score and repeat path; :func:`expert_error_keys`). Across takes
    such an error is a learned mistake, not a slip, so its bar is a "strong" correctness item
    (DECISIONS 2026-09-28, after F-08) when ``promote`` is True, i.e. with at least
    ``cfg.recurring_min_experts`` experts. Calibration: ``calibration.RECURRING_KINDS``.
    """
    rows = []
    sigs = [error_signatures(main_cr, labels)]
    main_bars = main_cr.bars
    err_by_label = dict(zip(labels, (main_bars["n_errors"] > 0).astype(int).to_numpy(),
                            strict=True))
    sp = dict(zip(main_cr.score_notes["score_id"].astype(str),
                  main_cr.score_notes["pitch"].astype(int), strict=True))
    for k, t in enumerate(takes):
        try:
            c = correctness(t)
            tl = bar_labels(t.score)
            sigs.append(error_signatures(c, tl))
            for sid, p in zip(c.score_notes["score_id"].astype(str),
                              c.score_notes["pitch"].astype(int), strict=True):
                sp.setdefault(sid, int(p))
            for lab, e in zip(tl, (c.bars["n_errors"] > 0).to_numpy(), strict=True):
                err_by_label[lab] = err_by_label.get(lab, 0) + int(e)
            tm = tempo_model(t)
            rows.append({"take": k + 1, "performance_id": str(t.performance.performance_id),
                         "accuracy": _f(c.summary["accuracy"]),
                         "n_wrong_pitch": int(c.summary["n_wrong_pitch"]),
                         "n_missed": int(c.summary["n_missed"]),
                         "n_extra": int(c.summary["n_extra"]),
                         "n_bars_with_errors": int(c.summary["n_bars_with_errors"]),
                         "tempo_bpm": _f(tm.summary["tempo_bpm_geomean"])})  # fmt: skip
        except Exception as e:  # noqa: BLE001
            errors[f"take_{k + 1}"] = repr(e)
    n_all = 1 + len(rows)
    ex_sigs = []
    for r in experts:
        try:
            if len(r.score.notes) != len(main_cr.score_notes):
                continue  # another repeat path: note ids do not line up
            ex_sigs.append(error_signatures(correctness(r), bar_labels(r.score)))
        except Exception as e:  # noqa: BLE001
            errors[f"correctness_ref:{r.performance.performance_id}"] = repr(e)
    promote = len(ex_sigs) >= cfg.recurring_min_experts
    ex_keys = expert_error_keys(ex_sigs) if ex_sigs else None
    rec = recurring_errors(sigs, cfg.recurring_min_takes, cfg.recurring_kinds,
                           exclude=ex_keys) if n_all >= 2 else {}
    rec_bars = {}
    for lab in labels:
        if lab in rec:
            items = sorted(rec[lab].items(), key=lambda kv: (-kv[1], kv[0]))
            rec_bars[lab] = [{"kind": k[0], "n_takes": c, "text": _describe_error(k, sp)}
                             for k, c in items]
    return {"n_takes": n_all, "takes": rows,
            "errors_per_bar": [err_by_label.get(lab, 0) for lab in labels],
            "recurring_min_takes": cfg.recurring_min_takes,
            "recurring_kinds": list(cfg.recurring_kinds),
            "recurring_error_bars": [lab for lab in labels if lab in rec_bars],
            "recurring": rec_bars, "n_expert_checks": len(ex_sigs), "promoted": promote}


# =========================================================================== issues


def _group_spans(tiers: Sequence[str], mags: Sequence[float]) -> list[tuple[list[int], str, float]]:
    """Consecutive tiered bars -> spans (bar indices, max tier, max magnitude)."""
    spans, cur = [], []
    for i, t in enumerate(tiers):
        if t != "none":
            cur.append(i)
        elif cur:
            spans.append(cur)
            cur = []
    if cur:
        spans.append(cur)
    out = []
    for s in spans:
        tt = max((tiers[i] for i in s), key=_TIER_RANK.get)
        m = [mags[i] for i in s if np.isfinite(mags[i])]
        out.append((s, tt, float(max(m)) if m else float("nan")))
    return out


def collect_issues(rep: dict[str, Any]) -> list[dict[str, Any]]:
    """Every tiered, localized issue in the report, most severe first.

    Order (DECISIONS 2026-09-28, after F-08): tier ("strong" before "notable"); within a tier,
    correctness first, then control (timing, pedal, evenness), then shaping and interpretation
    (tempo / loudness vs experts, too flat); within a category, errors that recur across takes
    first, then magnitude (the value as a multiple of the notable limit, i.e. of the experts'
    95th percentile). An issue is ``practise_eligible`` unless its channel is low-confidence
    (velocity on transcribed input or references).
    """
    from pianolens.report import text

    bars = rep["bars"]
    labels = [b["label"] for b in bars]
    vlow = rep["confidence"]["velocity"] == "low"
    wins = (rep.get("interpretation") or {}).get("windows", [])
    # a too-flat section explains its per-bar shape deviations: they are listed, not practised
    flat_bars = {ch: {i for w in wins if w["block"] == ch and w["flat_tier"] != "none"
                      for i in w["bars"]} for ch in ("tempo", "velocity")}
    issues = []

    def add(category: str, channel: str, tiers: list[str], mags: list[float], elig: bool = True):
        for idx, tier, mag in _group_spans(tiers, mags):
            item = {"category": category, "channel": channel, "bars": idx,
                    "bars_label": span_label(labels, idx), "tier": tier, "magnitude": mag,
                    "practise_eligible": elig}
            if category == "correctness":
                item["recurring"] = [labels[i] for i in idx
                                     if bars[i]["correctness"].get("recurring")]
            if category == "interpretation" and set(idx) & flat_bars.get(channel, set()):
                item["practise_eligible"] = False
                item["explained_by"] = "too_flat"
            item["text"] = text.issue_text(item, rep)
            issues.append(item)

    add("correctness", "notes", [b["correctness"]["tier"] for b in bars],
        [b["correctness"]["magnitude"] for b in bars])
    for ch in ("tempo", "velocity"):
        add("interpretation", ch, [b[ch]["tier"] for b in bars],
            [b[ch]["magnitude"] for b in bars], elig=not (ch == "velocity" and vlow))
        # too flat: magnitude = expert median shaping / this performance's shaping
        fm = [np.nan] * len(bars)
        for w in wins:
            if w["block"] != ch or w["flat_tier"] == "none":
                continue
            m, r = w.get("magnitude"), w.get("magnitude_ref_median")
            ratio = r / max(m, 1e-6 * r) if np.isfinite(m) and np.isfinite(r) and r > 0 \
                else np.nan
            for i in w["bars"]:
                fm[i] = ratio
        add("too_flat", ch, [b["too_flat"][ch] for b in bars], fm,
            elig=not (ch == "velocity" and vlow))
    add("control", "timing", [b["timing"]["tier"] for b in bars],
        [b["timing"]["magnitude"] for b in bars])
    add("control", "pedal", [b["pedal"]["tier"] for b in bars],
        [b["pedal"]["magnitude"] for b in bars])
    add("control", "evenness", [b["evenness"]["tier"] for b in bars],
        [b["evenness"]["magnitude"] for b in bars])
    issues.sort(key=lambda d: (-_TIER_RANK[d["tier"]], CATEGORY_RANK[d["category"]],
                               -len(d.get("recurring", ())),
                               -(d["magnitude"] if np.isfinite(d["magnitude"]) else 0.0),
                               d["bars"][0]))
    return issues


# =========================================================================== main entry


def build_report(inp: ReportInputs, config: ReportConfig | None = None) -> dict[str, Any]:
    """All report data for one performance (JSON-ready after :func:`to_jsonable`).

    Never raises for a performance that aligned: a failing component is recorded in
    ``errors`` and its fields are empty.
    """
    from pianolens.report import text

    cfg = config or ReportConfig()
    ap = inp.ap
    score = ap.score
    labels = bar_labels(score)
    nb = len(labels)
    errors: dict[str, str] = {}
    perf = ap.performance

    corr_summary, cbars, cres = _correctness_section(ap, labels)
    tc = tempo_model(ap)
    same_refs = []
    for r in inp.same_score_refs:
        try:
            same_refs.append((r, tempo_model(r)))
        except Exception as e:  # noqa: BLE001
            errors[f"tempo_ref:{r.performance.performance_id}"] = repr(e)
    inp_same = [r for r, _ in same_refs]

    target = target_from_aligned(ap, cfg.interpretation, source_id=inp.source_id)
    target.provenance = inp.provenance
    inp_for_refs = replace_inputs(inp, same_score_refs=inp_same)
    refs, bmap, ref_info = _tier_d_references(inp_for_refs, target, cfg)

    interp = None
    if refs is not None and len(refs) >= cfg.interpretation.min_references:
        try:
            interp = _interpretation_section(inp, target, refs, bmap, cfg, nb)
        except Exception as e:  # noqa: BLE001
            errors["interpretation"] = repr(e)

    # timing noise against the references (F-04 definition, F-06 curve convention)
    tbar = _bar_of(target.pos_grid, target.bar_starts)
    timing_df, timing_summ = None, {}
    if refs is not None and len(refs):
        X = _timing_matrix(refs.exclude([target.performance_id, target.source_id]), target, bmap)
        timing_df, timing_summ = timing_noise_bars(target.timing, X, tbar, nb,
                                                   cfg.interpretation.min_refs_timing,
                                                   cfg.min_tier_references)
        per = tc.time_map.period(target.pos_grid)
        timing_summ["noise_rms_ms"] = timing_summ["noise_rms_beats"] * 1000 * float(
            np.nanmedian(per)) if np.isfinite(timing_summ.get("noise_rms_beats", np.nan)) \
            else np.nan
        bar_per = pd.Series(per).groupby(tbar).median()
        timing_df["noise_rms_ms"] = timing_df["noise_rms_beats"] * 1000 * \
            bar_per.reindex(timing_df["measure_index"]).to_numpy(float)
        timing_summ["n_references"] = int(len(X))

    ctrl_summ, ctrl_bars, runs = _control_section(ap, tc, same_refs, labels, cfg, errors)
    shaping = _shaping_section(ap, tc, cfg, errors) if cfg.shaping else {}
    takes = _takes_section(cres, inp.takes, labels, cfg, errors,
                           [*inp.correctness_refs, *inp_same]) if inp.takes else None
    if takes and takes["promoted"]:  # recurring errors -> a "strong" correctness item
        rec = takes["recurring"]
        tiers = cbars["tier"].to_numpy(object)
        for i, lab in enumerate(labels):
            if lab in rec:
                tiers[i] = "strong"
        cbars["tier"] = tiers
        corr_summary["n_bars_strong"] = int((cbars["tier"] == "strong").sum())
        corr_summary["n_bars_notable"] = int((cbars["tier"] == "notable").sum())
    if takes:
        corr_summary["n_bars_recurring"] = len(takes["recurring"])

    vconf = interp["velocity_confidence"] if interp else (
        "high" if inp.provenance in SENSOR_PROVENANCE else "low")
    # ---- per-bar rows
    mq, mb, mnum = _measure_info(score)
    bars = []
    for i in range(nb):
        c = cbars.iloc[i]
        row: dict[str, Any] = {
            "index": i, "label": labels[i], "number": int(mnum[i]) if len(mnum) else i + 1,
            "start_beat": _f(mb[i]) if len(mb) else np.nan,
            "correctness": {"n_score_notes": int(c["n_score_notes"]),
                            "n_wrong_pitch": int(c["n_wrong_pitch"]),
                            "n_missed": int(c["n_missed"]), "n_extra": int(c["n_extra"]),
                            "n_errors": int(c["n_errors"]), "tier": c["tier"],
                            "magnitude": _f(c["magnitude"]),
                            "recurring": (takes or {}).get("recurring", {}).get(labels[i], [])},
        }  # fmt: skip
        for ch in ("tempo", "velocity"):
            if interp:
                d = interp["bars"][ch].iloc[i]
                row[ch] = {"dev_rms": _f(d["dev_rms"]), "q95": _f(d["q95"]), "q99": _f(d["q99"]),
                           "dev_mean": _f(d["dev_mean"]), "target": _f(d["abs_target"]),
                           "band_lo": _f(d["abs_lo"]), "band_mid": _f(d["abs_mid"]),
                           "band_hi": _f(d["abs_hi"]), "tier": d["tier"],
                           "magnitude": _f(d["magnitude"])}  # fmt: skip
            else:
                row[ch] = {"tier": "none", "magnitude": np.nan}
        row["too_flat"] = {"tempo": "none", "velocity": "none"}
        if interp:
            for w in interp["windows"]:
                if i in w["bars"] and _TIER_RANK[w["flat_tier"]] > \
                        _TIER_RANK[row["too_flat"][w["block"]]]:
                    row["too_flat"][w["block"]] = w["flat_tier"]
        if timing_df is not None:
            t = timing_df.iloc[i]
            tt = _tier(_f(t["noise_rms_beats"]), _f(t["ref_q95"]), _f(t["ref_q99"]))
            row["timing"] = {"noise_rms_beats": _f(t["noise_rms_beats"]),
                             "noise_rms_ms": _f(t["noise_rms_ms"]), "ref_q95": _f(t["ref_q95"]),
                             "ref_q99": _f(t["ref_q99"]), "n_refs": int(t["n_refs"]),
                             "tier": tt, "magnitude": _f(t["noise_rms_beats"]) / _f(t["ref_q95"])
                             if _f(t["ref_q95"]) > 0 else np.nan}  # fmt: skip
        else:
            row["timing"] = {"noise_rms_beats": np.nan, "tier": "none", "magnitude": np.nan}
        cb = ctrl_bars.iloc[i]
        row["pedal"] = {"n_harmony_changes": int(cb["n_harmony_changes"]),
                        "blur_fraction": _f(cb["pedal_blur_fraction"]),
                        "blur_beats": _f(cb["pedal_blur_beats"]),
                        "ref_q95": _f(cb["pedal_ref_q95"]), "n_refs": int(cb["pedal_n_refs"]),
                        "tier": cb["pedal_tier"], "magnitude": _f(cb["pedal_magnitude"])}
        row["evenness"] = {"ioi_cv": _f(cb["even_strict_ioi_cv"]),
                           "vel_sd_midi": _f(cb["even_strict_vel_sd_midi"]),
                           "note_rate_nps": _f(cb["even_strict_note_rate_nps"]),
                           "n_iois": int(cb["even_strict_n_iois"]),
                           "ref_q95": _f(cb["evenness_ref_q95"]),
                           "n_refs": int(cb["evenness_n_refs"]), "tier": cb["evenness_tier"],
                           "magnitude": _f(cb["evenness_magnitude"])}  # fmt: skip
        if takes:
            row["takes_with_errors"] = takes["errors_per_bar"][i]
        bars.append(row)

    rep: dict[str, Any] = {
        "schema": SCHEMA,
        "generated": _dt.date.today().isoformat(),
        "piece": {"piece_id": inp.piece_id, "title": inp.title or (inp.piece_id or ""),
                  "n_bars": nb, "beats_per_bar": _beats_per_bar(score),
                  "score_id": str(score.score_id)},
        "input": {"performance_id": str(perf.performance_id), "provenance": inp.provenance,
                  "n_notes": len(perf.notes), "has_pedal": bool(len(perf.pedal)),
                  "duration_sec": _f(perf.notes["onset_sec"].max() - perf.notes["onset_sec"]
                                     .min()) if len(perf.notes) else np.nan,
                  "paths": inp.paths, "notes": list(inp.notes)},
        "references": {**ref_info,
                       "tier_d_total": int(len(refs)) if refs is not None else 0,
                       "velocity_source": (interp or {}).get("meta", {}).get(
                           "velocity_reference_source"),
                       "n_velocity_references": (interp or {}).get("meta", {}).get(
                           "n_velocity_references"),
                       "n_tier_d_used": (interp or {}).get("meta", {}).get("n_references"),
                       "same_score_provenance": inp.same_score_provenance
                       if inp.same_score_refs else None},
        "confidence": {"velocity": vconf,
                       "alignment_suspect": bool(corr_summary.get("alignment_suspect")),
                       "transcribed": inp.provenance == "transcribed"},
        "correctness": corr_summary,
        "tempo": {k: _f(tc.summary.get(k)) for k in ("tempo_bpm_geomean", "tempo_bpm_overall",
                                                     "tempo_log_sd", "jitter_rms_ms")},
        "interpretation": {k: v for k, v in (interp or {}).items() if k not in ("bars",)},
        "timing": timing_summ,
        "control": ctrl_summ,
        "shaping": shaping,
        "evenness_runs": runs.to_dict("records") if len(runs) else [],
        "literature_evenness": list(cal.LITERATURE_EVENNESS),
        "takes": takes,
        "bars": bars,
        "errors": errors,
    }
    rep["confidence"]["notes"] = text.confidence_notes(rep)
    issues = collect_issues(rep)
    rep["issues"] = issues
    rep["practise"] = [d for d in issues if d["practise_eligible"]][: cfg.n_practise]
    rep["summary"] = text.summary_findings(rep)
    return rep


def replace_inputs(inp: ReportInputs, **kw: Any) -> ReportInputs:
    d = {k: getattr(inp, k) for k in inp.__dataclass_fields__}
    d.update(kw)
    return ReportInputs(**d)
