"""Graded single-dimension degradations of aligned expert MIDI (S-01, Phase 3, H6).

Each function takes an :class:`~pianolens.data.types.AlignedPerformance` (performance + score +
alignment; exact-timing sources: disklavier / sensor) and changes **one** expressive dimension by
a controlled amount. It returns a :class:`DegradeResult`: the degraded aligned performance
(note ids kept, so excerpts can be cut by score bars afterwards), the control parameter, the
change **measured in physical units** (ms, MIDI velocity, beats, notes per second) and, where
the landscape doc (section 1.5) gives one, the ratio of that change to a published audibility
threshold. Where no threshold is published, ``reference`` says so; the S-03 study measures it.

Dimensions (``DIMENSIONS``) and their control parameter:

========================  ===========================================================  =========
dimension                 what changes                                                 level
========================  ===========================================================  =========
``timing_jitter``         random onset shifts per score position (chord), s.d. in ms   ``sd_ms``
                          or relative to the local inter-onset interval (``cv``)       or ``cv``
``tempo_flatten``         smooth tempo curve (F-03 time map) pulled toward a constant  ``alpha``
                          tempo with the same total duration; residual timing kept
                          (in beats)
``dynamics_flatten``      velocity contour pulled toward the mean; the melody vs       ``alpha``
                          accompaniment gap (voicing) is kept
``voicing``               melody vs accompaniment velocity gap scaled by ``k``         ``k``
                          (1 = original, 0 = no gap, -1 = inverted); local mean kept
``pedal_blur``            sustain pedal held across a share of the score harmony       ``fraction``
                          changes (F-04b detector), or across all of them for a        or ``hold``
                          graded time (a late pedal change)
``articulation``          key-down durations scaled (< 1 detached / staccato,          ``factor``
                          > 1 legato / overlapping)
``wrong_notes``           wrong pitches (neighbour keys, a few octaves) per played      ``rate``
                          note, via :func:`pianolens.data.perturb.perturb` (D-08)
========================  ===========================================================  =========

Design choices, so the dimensions stay separate:

* **Timing jitter** moves every note of a score position by the same amount, so chords stay
  together (asynchrony is another dimension). Offsets move with onsets (durations unchanged) and
  each pedal event moves with the position it follows, so syncopated pedal changes keep their
  delay. Shifts are drawn from a normal truncated at 0.45 of the smaller neighbouring IOI, so
  the note order never changes; the achieved s.d. is reported, and ``n_bound_binding`` counts
  positions where the bound is under two requested s.d. (the achieved s.d. is then smaller).
  Onset jitter of s.d. ``s`` adds IOI s.d. ``sqrt(2) * s`` (neighbouring IOIs share a shift), so
  the audibility threshold of van Vugt et al. 2013 (IOI s.d. about 10.22 ms at 8 notes/s, IOI
  CV about 0.08, landscape 1.5) corresponds to onset s.d. of about 7.2 ms at that rate. The
  ``reference`` ratio uses the achieved *added IOI* s.d. and CV. The threshold was measured on
  isochronous scales; in repertoire with expressive timing it is a lower bound, not a norm.
* **Tempo flattening** warps time by ``W(t) = (1 - a) t + a D(T^-1(t))`` where ``T`` is the
  F-03 smooth time map and ``D`` the straight line through its first and last positions. Every
  event (onsets, offsets, pedal) goes through ``W``, so articulation and pedal scale with the
  local tempo, and the residual (note minus smooth curve) is kept in beats. No listener threshold
  for smooth-tempo modulation is in the landscape doc.
* **Velocity** is decomposed per matched note as ``v = m + D + V``: ``m`` the performance mean,
  ``V`` the voicing term and ``D`` the rest (the dynamic contour, accents, noise). Melody notes
  are the score skyline (the highest pitch starting at an onset, not below a held note; same rule
  as ``score_basis``). The local gap ``g`` is the kernel-weighted (Gaussian, bandwidth one bar)
  mean melody velocity minus mean accompaniment velocity, and ``p`` the local melody share of
  notes; ``V = (1 - p) g`` for melody notes and ``-p g`` for the others, so the local mean of
  ``V`` is about zero. ``dynamics_flatten`` scales ``D`` by ``1 - alpha``; ``voicing`` scales
  ``V`` by ``k``. Unmatched notes (insertions) have ``V = 0``. Results are rounded and clipped
  to 1..127, and the achieved change is reported. The audibility reference is the velocity JND
  for consecutive tones, 2.71 to 4.48 MIDI units (Slade et al. 2023, landscape 1.5); it was
  measured on a Disklavier, not on the S-02 soundfont, so the ratio is approximate.
* **Pedal blur** uses the F-04b harmony-change rule (``control.harmony_changes``) and the F-04
  blur rule (pedal down without a lift from 0.25 beat before to 0.5 beat after the change). To
  blur a change it sets CC64 to 127 from 0.25 beat before the change until ``hold_beats`` after
  it (or until the next change's window), then inserts a late pedal change: a lift, and 60 ms
  later the pianist's own pedal state. Two ways to grade it: by the share of changes blurred
  (``fraction``, of all changes or of the cleanly pedalled ones) or, with every clean change
  blurred, by how late the change comes (``hold_beats``; ``degrade(..., grade="hold")``). The
  second works in short clips with only one or two harmony changes. No published
  pedal-timing norm exists (landscape 1.5).
* **Articulation** scales every key-down duration, clipped so a key never overlaps the next
  onset of the same pitch and never goes below 20 ms. With the pedal down, shorter key-down
  times are partly masked; ``physical["pedal_down_fraction"]`` reports how much. No audibility
  threshold is in the landscape doc (Bresin and Battel 2000 define the KOT / KOR measures).
* **Wrong notes** only change pitches (no extra or missed notes, unless ``mix`` says so) and keep
  timing and velocity, so correctness varies alone.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from pianolens.data.types import ALIGNMENT_DTYPE, AlignedPerformance, Alignment, Performance

__all__ = [
    "DIMENSIONS",
    "REFERENCES",
    "DegradeResult",
    "articulation_scale",
    "degrade",
    "dynamics_flatten",
    "pedal_blur",
    "position_times",
    "tempo_flatten",
    "timing_jitter",
    "velocity_components",
    "voicing_scale",
    "wrong_notes",
]

DIMENSIONS: tuple[str, ...] = (
    "timing_jitter",
    "tempo_flatten",
    "dynamics_flatten",
    "voicing",
    "pedal_blur",
    "articulation",
    "wrong_notes",
)

REFERENCES: dict[str, dict[str, Any]] = {
    "timing_ioi_sd": {
        "value_ms": 10.22,
        "sd_ms": 2.51,
        "rate_notes_per_s": 8.0,
        "what": "IOI s.d. at which listeners detected unevenness in isochronous scales",
        "source": "van Vugt, Jabusch, Altenmueller 2013, Front. Psychol. 4:134 (landscape 1.5)",
    },
    "timing_ioi_cv": {
        "value": 0.08,
        "what": "the same threshold as a CV (derived: 10.22 ms / 125 ms IOI)",
        "source": "derived in landscape 1.5 from van Vugt et al. 2013",
    },
    "velocity_jnd": {
        "lo": 2.71,
        "hi": 4.48,
        "what": "JND in key velocity between consecutive tones (Disklavier, 0.68-1.22 dBC)",
        "source": "Slade, Gascon, Comeau, Russell 2023, Psychol. Music 51:924 (landscape 1.5)",
    },
}

_NO_REFERENCE = {"none": "no published audibility threshold in the landscape doc; S-03 measures it"}
_EPS = 1e-9
_MIN_DUR_SEC = 0.02
_REPEDAL_SEC = 0.06  # lift-to-repress time of an inserted late pedal change


@dataclass(eq=False)
class DegradeResult:
    """A degraded aligned performance plus its level in control and physical units.

    Attributes:
        aligned: the degraded ``AlignedPerformance`` (same score; note ids kept except injected
            extras; alignment updated for wrong notes).
        dimension: one of ``DIMENSIONS``.
        level: the control parameter value.
        level_name: its name (``sd_ms``, ``cv``, ``alpha``, ``k``, ``fraction``, ``factor``,
            ``rate``).
        physical: the achieved change, measured on the output, in physical units (keys end in
            the unit: ``_ms``, ``_midi``, ``_beats``, ``_per_s``...).
        reference: literature threshold(s) and the ratio of the change to them, or a note that
            none is published.
        meta: seed and dimension-specific details.
    """

    aligned: AlignedPerformance
    dimension: str
    level: float
    level_name: str
    physical: dict[str, float]
    reference: dict[str, Any]
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def performance(self) -> Performance:
        return self.aligned.performance

    def summary(self) -> dict[str, Any]:
        """Flat dict for manifests: dimension, level, physical values, threshold ratios."""
        out: dict[str, Any] = {"dimension": self.dimension, "level_name": self.level_name,
                               "level": self.level}  # fmt: skip
        out.update({f"phys_{k}": v for k, v in self.physical.items()})
        for k, v in self.reference.items():
            if isinstance(v, dict) and "ratio" in v:
                out[f"ratio_{k}"] = v["ratio"]
            elif isinstance(v, dict) and "ratio_lo" in v:
                out[f"ratio_{k}_lo"] = v["ratio_lo"]
                out[f"ratio_{k}_hi"] = v["ratio_hi"]
        return out


# --------------------------------------------------------------------------- helpers


def _pairs_frame(ap: AlignedPerformance) -> pd.DataFrame:
    """Matched, non-grace notes: score_id, performance_id, beat, quarter, pitch (score)."""
    from pianolens.features._score_utils import matched_note_frame

    df, _ = matched_note_frame(ap)
    return df


def position_times(ap: AlignedPerformance) -> pd.DataFrame:
    """One row per score position (distinct beat) with matched notes: ``beat``, ``quarter``,
    ``time_sec`` (median performed onset), sorted by beat."""
    df = _pairs_frame(ap)
    if df.empty:
        return pd.DataFrame(columns=["beat", "quarter", "time_sec"])
    g = df.groupby("beat", sort=True)
    return pd.DataFrame({"beat": g["beat"].first(), "quarter": g["quarter"].first(),
                         "time_sec": g["onset_sec"].median()}).reset_index(drop=True)  # fmt: skip


def _copy_notes(perf: Performance) -> np.ndarray:
    return perf.notes.copy()


def _sync_ticks(orig: np.ndarray, new: np.ndarray) -> None:
    """Keep ``onset_tick`` / ``duration_tick`` (if present) consistent with new seconds."""
    names = new.dtype.names or ()
    if "onset_tick" not in names or len(orig) < 2:
        return
    from pianolens.data.perturb import _tick_map, _to_ticks

    tmap = _tick_map(orig)
    if tmap is None:
        return
    on = _to_ticks(tmap, new["onset_sec"].astype(float))
    off = _to_ticks(tmap, (new["onset_sec"] + new["duration_sec"]).astype(float))
    new["onset_tick"] = on
    if "duration_tick" in names:
        new["duration_tick"] = np.maximum(1, off - on)


def _fix_same_pitch_overlaps(notes: np.ndarray, gap: float = 0.001) -> int:
    """Cut key-down durations so a note never sounds past the next onset of its pitch.

    Returns the number of notes shortened. MIDI cannot hold one key twice.
    """
    n_cut = 0
    on = notes["onset_sec"]
    for p in np.unique(notes["pitch"]):
        idx = np.flatnonzero(notes["pitch"] == p)
        idx = idx[np.argsort(on[idx], kind="stable")]
        for a, b in zip(idx[:-1], idx[1:], strict=True):
            limit = on[b] - on[a] - gap
            if notes["duration_sec"][a] > limit:
                notes["duration_sec"][a] = max(_MIN_DUR_SEC, limit)
                n_cut += 1
    return n_cut


def _new_aligned(ap: AlignedPerformance, notes: np.ndarray, pedal: np.ndarray, tag: str,
                 info: dict[str, Any], alignment: Alignment | None = None) -> AlignedPerformance:
    perf = ap.performance
    new_id = f"{perf.performance_id}#{tag}"
    order = np.argsort(notes["onset_sec"], kind="stable")
    notes = notes[order]
    pedal = pedal[np.argsort(pedal["time_sec"], kind="stable")] if len(pedal) else pedal
    meta = {**perf.meta, "degradation": {**info, "source_performance_id": perf.performance_id,
                                         "source_provenance": perf.provenance}}  # fmt: skip
    new_perf = dataclasses.replace(perf, performance_id=new_id, provenance="synthetic",
                                   notes=notes, pedal=pedal, meta=meta)  # fmt: skip
    al = alignment if alignment is not None else ap.alignment
    if al is not None:
        al = Alignment(al.pairs.copy(), al.score_id, new_id, al.ground_truth,
                       f"{al.source}+degrade")  # fmt: skip
    return AlignedPerformance(new_perf, ap.score, al)


def _local_ioi(t: np.ndarray, width: int = 2) -> np.ndarray:
    """Median absolute IOI over +-``width`` neighbouring positions (floor 10 ms)."""
    if len(t) < 2:
        return np.full(len(t), np.nan)
    d = np.abs(np.diff(t))
    out = np.empty(len(t))
    for k in range(len(t)):
        lo, hi = max(0, k - width), min(len(d), k + width)
        out[k] = np.median(d[lo:hi]) if hi > lo else d[min(k, len(d) - 1)]
    return np.maximum(out, 0.01)


def _nearest_index(sorted_t: np.ndarray, t: np.ndarray) -> np.ndarray:
    j = np.clip(np.searchsorted(sorted_t, t), 1, len(sorted_t) - 1)
    left = sorted_t[j - 1]
    right = sorted_t[j]
    return np.where(np.abs(t - left) <= np.abs(right - t), j - 1, j)


def _ratio(value: float, ref: float) -> float:
    return float(value / ref) if np.isfinite(value) else float("nan")


# --------------------------------------------------------------------------- timing jitter


def timing_jitter(ap: AlignedPerformance, sd_ms: float | None = None, cv: float | None = None,
                  seed: int = 0, max_frac: float = 0.45) -> DegradeResult:
    """Random onset shifts per score position. Give exactly one of ``sd_ms`` (absolute s.d.)
    or ``cv`` (s.d. as a fraction of the local IOI between positions)."""
    if (sd_ms is None) == (cv is None):
        raise ValueError("give exactly one of sd_ms or cv")
    rng = np.random.default_rng(seed)
    pos = position_times(ap)
    t = pos["time_sec"].to_numpy(float)
    order = np.argsort(t, kind="stable")
    ts = t[order]
    ioi = _local_ioi(ts)
    sd = np.full(len(ts), (sd_ms or 0.0) / 1000.0) if sd_ms is not None else cv * ioi
    gaps = np.diff(ts)
    left = np.concatenate([[np.inf], gaps])
    right = np.concatenate([gaps, [np.inf]])
    bound = max_frac * np.minimum(left, right)
    bound = np.where(np.isfinite(bound), bound, max_frac * ioi)
    shift = np.zeros(len(ts))
    for k in range(len(ts)):
        if sd[k] <= 0:
            continue
        for _ in range(100):
            s = rng.normal(0.0, sd[k])
            if abs(s) <= bound[k]:
                break
        shift[k] = float(np.clip(s, -bound[k], bound[k]))

    notes = _copy_notes(ap.performance)
    pf = _pairs_frame(ap)
    beat_shift = dict(zip(pos["beat"].to_numpy()[order].round(9), shift, strict=True))
    pid_shift = dict(zip(pf["performance_id"], pf["beat"].round(9).map(beat_shift),
                         strict=True))  # fmt: skip
    ids = notes["id"].astype(str)
    on = notes["onset_sec"].astype(float)
    near = _nearest_index(ts, on) if len(ts) > 1 else np.zeros(len(on), int)
    s_note = np.array([pid_shift.get(i, np.nan) for i in ids])
    s_note = np.where(np.isfinite(s_note), s_note, shift[near] if len(ts) else 0.0)
    notes["onset_sec"] = np.maximum(0.0, on + s_note)
    n_cut = _fix_same_pitch_overlaps(notes)
    _sync_ticks(ap.performance.notes, notes)

    pedal = ap.performance.pedal.copy()
    if len(pedal) and len(ts):
        k = np.clip(np.searchsorted(ts, pedal["time_sec"], side="right") - 1, 0, len(ts) - 1)
        pedal["time_sec"] = np.maximum(0.0, pedal["time_sec"] + shift[k])

    ds = np.diff(shift)
    iois = np.diff(ts)
    ok = iois > 0.01
    added_sd = float(np.std(ds[ok])) * 1000 if ok.sum() > 1 else float("nan")
    added_cv = float(np.std(ds[ok] / iois[ok])) if ok.sum() > 1 else float("nan")
    rate = float(1.0 / np.median(iois[ok])) if ok.any() else float("nan")
    phys = {
        "onset_shift_sd_ms": float(np.std(shift)) * 1000,
        "onset_shift_rms_ms": float(np.sqrt(np.mean(shift**2))) * 1000,
        "added_ioi_sd_ms": added_sd,
        "added_ioi_cv": added_cv,
        "position_rate_per_s": rate,
        "n_bound_binding": int(np.sum((sd > 0) & (bound < 2 * sd))),
        "n_positions": len(ts),
        "n_duration_cuts": n_cut,
    }
    ref = {
        "timing_ioi_sd": {**REFERENCES["timing_ioi_sd"],
                          "ratio": _ratio(added_sd, REFERENCES["timing_ioi_sd"]["value_ms"])},
        "timing_ioi_cv": {**REFERENCES["timing_ioi_cv"],
                          "ratio": _ratio(added_cv, REFERENCES["timing_ioi_cv"]["value"])},
    }  # fmt: skip
    name, level = ("sd_ms", float(sd_ms)) if sd_ms is not None else ("cv", float(cv))
    info = {"dimension": "timing_jitter", name: level, "seed": seed}
    out = _new_aligned(ap, notes, pedal, f"jit-{name}{level:g}-s{seed}", info)
    return DegradeResult(out, "timing_jitter", level, name, phys, ref, {"seed": seed})


# --------------------------------------------------------------------------- tempo flattening


def _time_map_grid(ap: AlignedPerformance, tempo: Any | None) -> tuple[Any, np.ndarray, np.ndarray]:
    from pianolens.features.tempo import tempo_model

    tc = tempo if tempo is not None else tempo_model(ap)
    pos = tc.positions
    b0, b1 = float(pos["beat"].min()), float(pos["beat"].max())
    grid = np.linspace(b0, b1, max(200, int((b1 - b0) * 16) + 1))
    tg = tc.time_map.time(grid)
    tg = np.maximum.accumulate(tg)
    return tc, grid, tg


def tempo_flatten(ap: AlignedPerformance, alpha: float, tempo: Any | None = None
                  ) -> DegradeResult:
    """Pull the smooth tempo curve toward a constant tempo by ``alpha`` (0 = unchanged,
    1 = constant tempo with the same duration between the first and last positions)."""
    tc, grid, tg = _time_map_grid(ap, tempo)
    b0, b1 = grid[0], grid[-1]
    t0, t1 = tg[0], tg[-1]
    pbar = (t1 - t0) / (b1 - b0)
    p0 = float(tc.time_map.period(np.array([b0]))[0])
    p1 = float(tc.time_map.period(np.array([b1]))[0])

    def t_inv(t: np.ndarray) -> np.ndarray:
        b = np.interp(t, tg, grid)
        b = np.where(t < t0, b0 + (t - t0) / p0, b)
        return np.where(t > t1, b1 + (t - t1) / p1, b)

    def warp(t: np.ndarray) -> np.ndarray:
        t = np.asarray(t, dtype=float)
        d = t0 + (t_inv(t) - b0) * pbar
        return (1 - alpha) * t + alpha * d

    notes = _copy_notes(ap.performance)
    on = notes["onset_sec"].astype(float)
    off = on + notes["duration_sec"].astype(float)
    new_on, new_off = warp(on), warp(off)
    notes["onset_sec"] = np.maximum(0.0, new_on)
    notes["duration_sec"] = np.maximum(_MIN_DUR_SEC, new_off - new_on)
    _sync_ticks(ap.performance.notes, notes)
    pedal = ap.performance.pedal.copy()
    if len(pedal):
        pedal["time_sec"] = np.maximum(0.0, warp(pedal["time_sec"].astype(float)))

    # physical: tempo spread of the smooth curve before / after, on the integer-beat grid
    bg = np.arange(np.ceil(b0), np.floor(b1) + 1)
    per = tc.time_map.period(bg) if len(bg) else np.array([pbar])
    per_new = (1 - alpha) * per + alpha * pbar
    log_before = np.log(pbar / per)
    log_after = np.log(pbar / per_new)
    pt = tc.positions["time_sec"].to_numpy(float)
    disp = warp(pt) - pt
    phys = {
        "tempo_log_sd_before": float(np.std(log_before)),
        "tempo_log_sd_after": float(np.std(log_after)),
        "tempo_max_dev_pct_before": float(np.max(np.abs(np.expm1(log_before))) * 100),
        "tempo_max_dev_pct_after": float(np.max(np.abs(np.expm1(log_after))) * 100),
        "onset_shift_rms_ms": float(np.sqrt(np.mean(disp**2))) * 1000,
        "onset_shift_max_ms": float(np.max(np.abs(disp))) * 1000,
        "mean_tempo_bpm": float(60.0 / pbar),
    }
    info = {"dimension": "tempo_flatten", "alpha": alpha}
    out = _new_aligned(ap, notes, pedal, f"tempo-a{alpha:g}", info)
    return DegradeResult(out, "tempo_flatten", float(alpha), "alpha", phys, dict(_NO_REFERENCE),
                         {"tempo_breaks": len(tc.breaks)})  # fmt: skip


# --------------------------------------------------------------------------- velocity


def _skyline_melody(ap: AlignedPerformance) -> pd.Series:
    """Score id -> True for skyline melody notes (top starting pitch, not below a held note)."""
    from pianolens.features._score_utils import score_note_frame

    sf = score_note_frame(ap.score)
    sf = sf[~sf["is_grace"]]
    q = sf["quarter"].to_numpy(float)
    e = q + sf["dur_quarter"].to_numpy(float)
    p = sf["pitch"].to_numpy(int)
    uq = np.unique(q)
    top = pd.Series(p).groupby(q).max().reindex(uq).to_numpy()
    held = np.full(len(uq), -1)
    for k, x in enumerate(uq):
        m = (q < x - 1e-6) & (e > x + 1e-6)
        if m.any():
            held[k] = p[m].max()
    is_new = dict(zip(uq, top >= held, strict=True))
    topd = dict(zip(uq, top, strict=True))
    mel = [bool(is_new[x]) and pi == topd[x] for x, pi in zip(q, p, strict=True)]
    return pd.Series(mel, index=sf["score_id"].to_numpy()).groupby(level=0).any()


def velocity_components(ap: AlignedPerformance, bandwidth_bars: float = 1.0) -> pd.DataFrame:
    """Per performed note: ``performance_id``, ``velocity``, ``melody`` (bool; False for
    unmatched), ``matched``, ``gap`` (local melody - accompaniment velocity), ``p_melody``,
    ``V`` (voicing term), ``D`` (dynamics term) and ``mean`` (performance mean velocity)."""
    perf = ap.performance
    ids = perf.notes["id"].astype(str)
    vel = perf.notes["velocity"].astype(float)
    pf = _pairs_frame(ap)
    mel_of = _skyline_melody(ap)
    pf["melody"] = pf["score_id"].map(mel_of).fillna(False).astype(bool)
    by_pid = pf.drop_duplicates("performance_id").set_index("performance_id")
    matched = np.array([i in by_pid.index for i in ids])
    q = np.array([by_pid.at[i, "quarter"] if m else np.nan for i, m in zip(ids, matched,
                                                                           strict=True)])
    mel = np.array([bool(by_pid.at[i, "melody"]) if m else False
                    for i, m in zip(ids, matched, strict=True)])  # fmt: skip
    ms = ap.score.measures
    bar_q = float(np.median(ms["end_quarter"] - ms["start_quarter"])) if len(ms) else 4.0
    h = bandwidth_bars * bar_q
    gap = np.zeros(len(ids))
    pm = np.zeros(len(ids))
    mq, aq = q[matched & mel], q[matched & ~mel]
    mv, av = vel[matched & mel], vel[matched & ~mel]
    for i in np.flatnonzero(matched):
        wm = np.exp(-0.5 * ((mq - q[i]) / h) ** 2)
        wa = np.exp(-0.5 * ((aq - q[i]) / h) ** 2)
        sm, sa = wm.sum(), wa.sum()
        if sm > 1e-3 and sa > 1e-3:
            gap[i] = wm @ mv / sm - wa @ av / sa
            pm[i] = sm / (sm + sa)
    V = np.where(mel, (1 - pm) * gap, -pm * gap)
    V = np.where(matched, V, 0.0)
    m = float(vel.mean()) if len(vel) else 0.0
    D = vel - m - V
    return pd.DataFrame({"performance_id": ids, "velocity": vel, "melody": mel,
                         "matched": matched, "gap": gap, "p_melody": pm, "V": V, "D": D,
                         "mean": m})  # fmt: skip


def _mean_gap(ap: AlignedPerformance, vel: np.ndarray, comp: pd.DataFrame) -> float:
    """Plain mean velocity of melody minus accompaniment matched notes (whole performance)."""
    mm = comp["matched"].to_numpy() & comp["melody"].to_numpy()
    aa = comp["matched"].to_numpy() & ~comp["melody"].to_numpy()
    if not mm.any() or not aa.any():
        return float("nan")
    return float(vel[mm].mean() - vel[aa].mean())


def _velocity_result(ap: AlignedPerformance, new_vel: np.ndarray, comp: pd.DataFrame,
                     dimension: str, level: float, name: str, tag: str) -> DegradeResult:
    notes = _copy_notes(ap.performance)
    rounded = np.clip(np.round(new_vel), 1, 127)
    notes["velocity"] = rounded
    old = comp["velocity"].to_numpy(float)
    change = rounded - old
    new_D = rounded - comp["mean"].to_numpy() - comp["V"].to_numpy()
    jnd = REFERENCES["velocity_jnd"]
    if dimension == "voicing":
        g0 = _mean_gap(ap, old, comp)
        g1 = _mean_gap(ap, rounded, comp)
        dg = abs(g1 - g0)
        phys = {"gap_before_midi": g0, "gap_after_midi": g1, "gap_change_midi": dg,
                "velocity_change_rms_midi": float(np.sqrt(np.mean(change**2))),
                "n_melody_notes": int((comp["melody"] & comp["matched"]).sum())}  # fmt: skip
        key = dg
    else:
        phys = {"dynamics_sd_before_midi": float(np.std(comp["D"])),
                "dynamics_sd_after_midi": float(np.std(new_D)),
                "velocity_change_rms_midi": float(np.sqrt(np.mean(change**2))),
                "velocity_sd_before_midi": float(np.std(old)),
                "velocity_sd_after_midi": float(np.std(rounded))}  # fmt: skip
        key = phys["velocity_change_rms_midi"]
    phys["n_clipped"] = int(np.sum((new_vel < 0.5) | (new_vel > 127.5)))
    ref = {"velocity_jnd": {**jnd, "ratio_lo": _ratio(key, jnd["hi"]),
                            "ratio_hi": _ratio(key, jnd["lo"]),
                            "compared": "gap change" if dimension == "voicing"
                            else "rms velocity change per note"}}  # fmt: skip
    info = {"dimension": dimension, name: level}
    out = _new_aligned(ap, notes, ap.performance.pedal.copy(), tag, info)
    return DegradeResult(out, dimension, float(level), name, phys, ref)


def dynamics_flatten(ap: AlignedPerformance, alpha: float, bandwidth_bars: float = 1.0
                     ) -> DegradeResult:
    """Scale the dynamics term ``D`` by ``1 - alpha`` (voicing kept). ``alpha`` = 1 is flat."""
    comp = velocity_components(ap, bandwidth_bars)
    new = comp["mean"] + (1 - alpha) * comp["D"] + comp["V"]
    return _velocity_result(ap, new.to_numpy(float), comp, "dynamics_flatten", alpha, "alpha",
                            f"dyn-a{alpha:g}")  # fmt: skip


def voicing_scale(ap: AlignedPerformance, k: float, bandwidth_bars: float = 1.0
                  ) -> DegradeResult:
    """Scale the melody - accompaniment gap by ``k`` (1 unchanged, 0 none, -1 inverted)."""
    comp = velocity_components(ap, bandwidth_bars)
    new = comp["mean"] + comp["D"] + k * comp["V"]
    return _velocity_result(ap, new.to_numpy(float), comp, "voicing", k, "k", f"voic-k{k:g}")


# --------------------------------------------------------------------------- pedal blur


def _cc64_value_at(times: np.ndarray, values: np.ndarray, t: float) -> int:
    k = int(np.searchsorted(times, t, side="right")) - 1
    return int(values[k]) if k >= 0 else 0


def _blurred(times: np.ndarray, values: np.ndarray, t: float, per: float, before: float,
             after: float, threshold: int) -> bool:
    a0, a1 = t - before * per, t + after * per
    down = values >= threshold
    lifts = times[(times > a0) & (times <= a1) & ~down]
    return _cc64_value_at(times, values, a0) >= threshold and len(lifts) == 0


def pedal_blur(ap: AlignedPerformance, fraction: float, hold_beats: float | None = None,
               seed: int = 0, tempo: Any | None = None, before_beats: float = 0.25,
               after_beats: float = 0.5, threshold: int = 64, relative_to: str = "all"
               ) -> DegradeResult:
    """Hold the sustain pedal across harmony changes (F-04 blur rule).

    ``relative_to="all"``: blur until ``fraction`` of all detected changes are blurred
    (changes the pianist already blurred count). ``relative_to="clean"``: blur ``fraction`` of
    the changes the pianist pedalled cleanly. ``hold_beats``: how long past the change the
    pedal stays down (None = until just before the next change's window)."""
    from pianolens.features.control import harmony_changes
    from pianolens.features.tempo import tempo_model

    rng = np.random.default_rng(seed)
    tc = tempo if tempo is not None else tempo_model(ap)
    ch = harmony_changes(ap.score)
    pos = tc.positions
    ptime = dict(zip(pos["beat"].round(6), pos["time_sec"], strict=True))
    b = ch["beat"].to_numpy(float)
    t = np.array([ptime.get(round(x, 6), np.nan) for x in b])
    t = np.where(np.isfinite(t), t, tc.time_map.time(b)) if len(b) else t
    per = tc.time_map.period(b) if len(b) else np.zeros(0)

    ped = ap.performance.pedal
    other = ped[ped["number"] != 64]
    p64 = ped[ped["number"] == 64]
    p64 = p64[np.argsort(p64["time_sec"], kind="stable")]
    times, values = p64["time_sec"].astype(float), p64["value"].astype(int)
    was = np.array([_blurred(times, values, t[i], per[i], before_beats, after_beats, threshold)
                    for i in range(len(b))], dtype=bool)  # fmt: skip
    n = len(b)
    if relative_to not in ("all", "clean"):
        raise ValueError("relative_to must be 'all' or 'clean'")
    n_clean = int((~was).sum())
    target = int(round(fraction * n)) if relative_to == "all" else \
        int(was.sum()) + int(round(fraction * n_clean))
    nxt = np.append(t[1:] - before_beats * per[1:], np.inf) if n else np.zeros(0)
    ends = np.array([
        min(nxt[i] - 0.01, t[i] + hold_beats * per[i]) if hold_beats is not None
        else nxt[i] - 0.01 for i in range(n)
    ])  # fmt: skip
    # a change can be blurred only if the forced hold covers its after-window
    ends = np.where(np.isfinite(ends), ends, t + max(after_beats + 0.5, 1.0) * per)
    eligible = np.flatnonzero(~was & (ends > t + after_beats * per + 0.01))
    need = max(0, target - int(was.sum()))
    chosen = np.sort(rng.choice(eligible, size=min(need, len(eligible)), replace=False)) \
        if need and len(eligible) else np.array([], dtype=int)

    new_t, new_v = list(times), list(values)
    for i in chosen:
        a = t[i] - before_beats * per[i] - 0.005
        e = ends[i]
        cur_t, cur_v = np.array(new_t), np.array(new_v)
        # a late pedal change: lift at e, then back to the pianist's state 60 ms later
        restore = _cc64_value_at(cur_t, cur_v, e + _REPEDAL_SEC)
        keep = (cur_t < a) | (cur_t > e + _REPEDAL_SEC)
        new_t = [*cur_t[keep], a, e, e + _REPEDAL_SEC]
        new_v = [*cur_v[keep], 127, 0, restore]
        o = np.argsort(new_t, kind="stable")
        new_t = list(np.asarray(new_t)[o])
        new_v = list(np.asarray(new_v)[o])
    new64 = np.zeros(len(new_t), dtype=ped.dtype)
    new64["time_sec"] = new_t
    new64["number"] = 64
    new64["value"] = new_v
    pedal = np.concatenate([other, new64]) if len(other) else new64
    pedal = pedal[np.argsort(pedal["time_sec"], kind="stable")]

    nt, nv = new64["time_sec"].astype(float), new64["value"].astype(int)
    now = np.array([_blurred(nt, nv, t[i], per[i], before_beats, after_beats, threshold)
                    for i in range(n)], dtype=bool)  # fmt: skip
    added = now & ~was
    hold = [(ends[i] - t[i]) for i in np.flatnonzero(added)]
    phys = {
        "n_harmony_changes": n,
        "blur_fraction_before": float(was.mean()) if n else float("nan"),
        "blur_fraction_after": float(now.mean()) if n else float("nan"),
        "n_blurs_added": int(added.sum()),
        "added_hold_mean_ms": float(np.mean(hold)) * 1000 if hold else 0.0,
        "added_hold_mean_beats": float(np.mean([(ends[i] - t[i]) / per[i]
                                                for i in np.flatnonzero(added)]))
        if hold else 0.0,
        "n_eligible": len(eligible),
        "added_fraction_of_clean": float(added.sum() / n_clean) if n_clean else float("nan"),
    }  # fmt: skip
    info = {"dimension": "pedal_blur", "fraction": fraction, "hold_beats": hold_beats,
            "relative_to": relative_to, "seed": seed}  # fmt: skip
    out = _new_aligned(ap, _copy_notes(ap.performance), pedal,
                       f"pedal-f{fraction:g}-s{seed}", info)  # fmt: skip
    return DegradeResult(out, "pedal_blur", float(fraction), "fraction", phys,
                         dict(_NO_REFERENCE), {"seed": seed, "chosen": chosen.tolist()})


# --------------------------------------------------------------------------- articulation


def _pedal_down_fraction(pedal: np.ndarray, t0: float, t1: float, threshold: int = 64) -> float:
    p = pedal[pedal["number"] == 64] if len(pedal) else pedal
    if len(p) == 0 or t1 <= t0:
        return 0.0
    p = p[np.argsort(p["time_sec"], kind="stable")]
    grid = np.linspace(t0, t1, 2000)
    k = np.searchsorted(p["time_sec"], grid, side="right") - 1
    return float(np.mean(np.where(k >= 0, p["value"][np.maximum(k, 0)] >= threshold, False)))


def _melody_overlap_ratio(ap: AlignedPerformance, notes: np.ndarray) -> float:
    """Median key-down duration / IOI to the next skyline melody note (KOR-like, 1 = legato)."""
    comp_mel = _skyline_melody(ap)
    pf = _pairs_frame(ap)
    pf = pf[pf["score_id"].map(comp_mel).fillna(False).astype(bool)]
    if len(pf) < 3:
        return float("nan")
    pos = {i: k for k, i in enumerate(notes["id"].astype(str))}
    idx = np.array([pos[i] for i in pf["performance_id"] if i in pos])
    idx = idx[np.argsort(notes["onset_sec"][idx], kind="stable")]
    on = notes["onset_sec"][idx]
    dur = notes["duration_sec"][idx]
    ioi = np.diff(on)
    ok = ioi > 0.02
    return float(np.median(dur[:-1][ok] / ioi[ok])) if ok.any() else float("nan")


def articulation_scale(ap: AlignedPerformance, factor: float) -> DegradeResult:
    """Scale every key-down duration by ``factor`` (clipped: no same-pitch overlap, >= 20 ms)."""
    notes = _copy_notes(ap.performance)
    old = notes["duration_sec"].astype(float).copy()
    notes["duration_sec"] = np.maximum(_MIN_DUR_SEC, old * factor)
    n_cut = _fix_same_pitch_overlaps(notes)
    _sync_ticks(ap.performance.notes, notes)
    ratio = notes["duration_sec"] / np.maximum(old, 1e-6)
    t0 = float(notes["onset_sec"].min())
    t1 = float((notes["onset_sec"] + notes["duration_sec"]).max())
    phys = {
        "duration_ratio_median": float(np.median(ratio)),
        "duration_change_median_ms": float(np.median(notes["duration_sec"] - old)) * 1000,
        "melody_kor_before": _melody_overlap_ratio(ap, ap.performance.notes),
        "melody_kor_after": _melody_overlap_ratio(ap, notes),
        "pedal_down_fraction": _pedal_down_fraction(ap.performance.pedal, t0, t1),
        "n_duration_cuts": n_cut,
    }
    info = {"dimension": "articulation", "factor": factor}
    out = _new_aligned(ap, notes, ap.performance.pedal.copy(), f"art-x{factor:g}", info)
    return DegradeResult(out, "articulation", float(factor), "factor", phys, dict(_NO_REFERENCE))


# --------------------------------------------------------------------------- wrong notes


def wrong_notes(ap: AlignedPerformance, rate: float, seed: int = 0,
                mix: tuple[float, float, float] = (1.0, 0.0, 0.0),
                require_exact_timing: bool = True, at_least_one: bool = False
                ) -> DegradeResult:
    """Wrong pitches at ``rate`` per matched note via :func:`pianolens.data.perturb.perturb`.

    ``mix`` = share of (wrong pitch, extra, missed); the default changes pitches only.
    ``at_least_one``: for short clips, inject one mistake when ``rate * n`` rounds to 0
    (``physical["rate_per_note"]`` reports the achieved rate).
    """
    from pianolens.data.perturb import MistakeSpec, perturb

    n_match = int((ap.alignment.pairs["label"] == "match").sum())
    eff = rate
    if at_least_one and rate > 0 and n_match and round(rate * n_match) < 1:
        eff = 1.0 / n_match
    spec = MistakeSpec(rate=eff, mix=mix)
    perf, labels = perturb(ap.performance, ap.alignment, spec, seed,
                           require_exact_timing=require_exact_timing)  # fmt: skip
    counts = labels.counts(injected=True)
    n_inj = sum(counts.values())
    on = ap.performance.notes["onset_sec"]
    dur = float(on.max() - on.min()) if len(on) else 0.0
    phys = {
        "n_injected": n_inj,
        "n_wrong_pitch": counts["wrong_pitch"],
        "n_extra": counts["extra"],
        "n_missed": counts["missed"],
        "rate_per_note": n_inj / max(1, n_match),
        "rate_per_s": n_inj / dur if dur > 0 else float("nan"),
    }
    info = {"dimension": "wrong_notes", "rate": rate, "mix": list(mix), "seed": seed}
    al = Alignment(np.array(labels.alignment.pairs, dtype=ALIGNMENT_DTYPE),
                   labels.alignment.score_id, perf.performance_id, True,
                   labels.alignment.source)  # fmt: skip
    base = dataclasses.replace(ap, performance=dataclasses.replace(
        ap.performance, notes=perf.notes, pedal=perf.pedal))
    out = _new_aligned(base, perf.notes.copy(), perf.pedal.copy(),
                       f"wrong-r{rate:g}-s{seed}", info, alignment=al)  # fmt: skip
    return DegradeResult(out, "wrong_notes", float(rate), "rate", phys, dict(_NO_REFERENCE),
                         {"seed": seed, "labels": labels})


# --------------------------------------------------------------------------- dispatcher


def degrade(ap: AlignedPerformance, dimension: str, level: float, seed: int = 0,
            **options: Any) -> DegradeResult:
    """Apply one degradation by name. ``level`` is the dimension's control parameter:
    ``timing_jitter`` -> ``cv`` (pass ``unit="ms"`` for ``sd_ms``), ``tempo_flatten`` and
    ``dynamics_flatten`` -> ``alpha``, ``voicing`` -> ``k``, ``pedal_blur`` -> ``fraction``,
    ``articulation`` -> ``factor``, ``wrong_notes`` -> ``rate``."""
    if dimension == "timing_jitter":
        unit = options.pop("unit", "cv")
        kw = {"sd_ms": level} if unit == "ms" else {"cv": level}
        return timing_jitter(ap, seed=seed, **kw, **options)
    if dimension == "tempo_flatten":
        return tempo_flatten(ap, level, **options)
    if dimension == "dynamics_flatten":
        return dynamics_flatten(ap, level, **options)
    if dimension == "voicing":
        return voicing_scale(ap, level, **options)
    if dimension == "pedal_blur":
        if options.pop("grade", "fraction") == "hold":
            frac = options.pop("fraction", 1.0)
            return pedal_blur(ap, frac, hold_beats=level, seed=seed, **options)
        return pedal_blur(ap, level, seed=seed, **options)
    if dimension == "articulation":
        return articulation_scale(ap, level, **options)
    if dimension == "wrong_notes":
        return wrong_notes(ap, level, seed=seed, **options)
    raise ValueError(f"unknown dimension {dimension!r}; one of {DIMENSIONS}")
