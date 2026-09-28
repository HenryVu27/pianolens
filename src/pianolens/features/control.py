"""Tier B: motor control features (F-04).

Computed on an aligned performance (use the score returned by
``pianolens.align.align_performance``) plus the F-03 tempo model (:func:`tempo_model`). Tier B
reads the *residual* of the tempo model, never the smooth curve's shape (that is tier C); the one
exception is tempo stability, which reads the smooth curve only in the band between the tempo
model's cutoff and a phrase-level allowance.

Every feature has a per-bar table (``ControlResult.bars``, one row per row of
``Score.measures``, unfolded order) and summary values (``ControlResult.summary``). Unmatched,
``interpolated`` and grace notes are skipped and counted (``summary["n_*_skipped"]``); gross tempo
outliers (likely alignment errors) are left out of timing statistics.

Features
--------
1. **Timing noise** (``timing_noise_*``). DECISIONS 2026-09-27 (after F-03): the tempo residual
   is partly shared, intentional fine timing, so tier B noise is the residual *minus the
   expert-consensus fine timing* of the same piece. For each score position (score beat of the
   performed, unfolded score) the consensus is the mean normalized residual ``dev_beats`` of the
   reference performances at that position, leaving the target out (leave-one-out), where at
   least ``min_references`` references have an inlier there. ``noise = dev_beats - consensus``,
   in beats and in ms (times the local smooth beat period). Summary RMS values carry the tempo
   fit's ``sqrt(n / (n - edf))`` factor, as F-03's jitter does. With ``K`` references the
   consensus carries their own noise, so the RMS is inflated by about ``sqrt(1 + 1/K)``
   (reported as ``timing_noise_n_refs_median``). ``timing_consensus_r2`` is the share of the
   residual's mean square that the consensus explains. Fallback, always reported:
   ``jitter_nometric_rms_ms`` / ``_beats`` from F-03 (residual minus the performance's own
   within-bar pattern). ``timing_noise_source`` names the one ``timing_noise_best_*`` uses
   (consensus when it covers at least half the inlier positions). Unit: beats and ms.
   Citation: Repp 1992 and 1998 (landscape 1.3); van Vugt, Jabusch, Altenmüller 2012 (1.5):
   the consensus plays the role of their systematic "irregularity" and the noise their
   trial-to-trial "instability"; Tominaga et al. 2016 (1.5): expert keystroke timing noise is
   about 8 ms at a 250 ms IOI.
2. **Evenness in passages the score marks as even** (``even_*``). A run is a maximal stretch of
   at least ``run_min_notes`` consecutive onsets in one (staff, voice) stream of the score whose
   notes all have the same notated duration and follow each other without rests (scales,
   Alberti bass, repeated accompaniment figures; at an onset with several notes the shortest
   one counts). For each run, the performed onset of a score onset is the median onset of its
   matched notes in that stream, and velocity is their mean.
   * ``even_ioi_cv``: coefficient of variation of the tempo-normalized inter-onset intervals
     ``ioi_k / (T(b_{k+1}) - T(b_k))`` (T = F-03 smooth time map), so a smooth ritardando or
     accelerando is not unevenness; only score-adjacent matched onsets in the same tempo
     segment count. Pooled over runs as ``sqrt(sum_k (x_k / mean_run - 1)^2 / sum(n_run - 1))``.
     Unit: dimensionless (fraction of the IOI).
   * ``even_vel_sd_midi``: SD of velocity residuals after removing a polynomial trend in score
     position within the run (linear; quadratic for runs of ``long_run_notes`` or more), so a
     crescendo or a hairpin is not unevenness; pooled over runs with ``n - degree - 1`` degrees
     of freedom. Unit: MIDI velocity.
   **Two variants** (DECISIONS 2026-09-27, F-04 follow-ups; R-04 picks one by predictive
   value). ``even_*`` is the **broad** rule above. ``even_strict_*`` uses the same statistics on
   **strict** runs (:func:`strict_runs`): the notes must be sub-beat (notated duration below one
   beat), and each stretch must be either a *monotone run* (every step between consecutive
   onsets moves in the same pitch direction: scales, arpeggio runs; the top pitch of the onset
   counts) or a *repeated figure* (the onset's pitch set repeats exactly with a period of
   ``strict_max_period`` onsets or fewer, at least twice: Alberti bass, broken-chord and
   repeated-note accompaniment). Overlapping or touching stretches of either kind merge into one
   strict run of at least ``run_min_notes`` onsets. ``even_strict_share_of_onsets`` shows how
   much narrower the strict rule is.
   * ``even_note_rate_nps``: the note rate of the runs, IOIs used / their summed performed
     duration (notes per second). Both unevenness measures rise with playing speed (MacKenzie and
     Van Eerd 1990), so ``even_ioi_cv`` and ``even_vel_sd_midi`` are only comparable at a
     similar note rate. Also per run (``note_rate_nps``) and per bar.
   Citations (landscape 1.5): IOI-SD scale analysis, Jabusch, Vauth, Altenmüller 2004; van Vugt,
   Jabusch, Altenmüller 2012 and 2013; CV and velocity SD rise with rate, MacKenzie and Van Eerd
   1990; expert vs amateur relative-IOI SD, Kim et al. 2021; velocity: Tominaga et al. 2016
   (expert keystroke velocity SD 4.1 MIDI across trials) and Slade et al. 2023 (velocity JND 2.7
   to 4.5 MIDI units; no published within-run expert value was found). The published values
   are raw IOI SDs of instructed metronomic scales (professionals about 8-9 ms at 8 notes/s, CV
   about 0.07; audible at about 10 ms, CV about 0.08, van Vugt 2013); this CV is tempo-normalized
   and measured in repertoire, so it also holds expressive micro-timing and alignment noise.
   Treat those values as a floor, not a norm. No MIDI study of Alberti evenness with values
   exists (landscape 1.5). Tempo normalization: Hu et al., TISMIR 2026 (landscape 1.2).
3. **Hand synchrony** (``hand_async_*``). For every score onset where both staves (staff 1 =
   right hand, staff 2 = left hand, by notation) have matched notes, ``async = mean onset of the
   staff-1 notes - mean onset of the staff-2 notes`` (ms; positive = left hand first) and
   ``dv = mean staff-1 velocity - mean staff-2 velocity`` (MIDI). Louder notes sound earlier
   (the velocity artifact, Goebl 2001, JASA), so async is regressed on ``dv`` (OLS on
   points within 3 robust SD) and reported together with it: ``hand_async_mean_ms`` (signed,
   a consistent lead may be stylistic), ``hand_async_sd_ms`` (robust SD, 1.4826 * MAD),
   ``hand_async_vel_slope_ms`` (ms per MIDI velocity unit), ``hand_async_resid_sd_ms`` (robust
   SD after the velocity fit: the motor-noise measure), and ``hand_async_equalvel_sd_ms`` over
   onsets with ``|dv| <= equal_velocity_midi`` only. ``_beats`` variants divide by the local
   smooth beat period. Unit: ms, beats, MIDI velocity. Arpeggiated chords are not excluded
   (they inflate the robust SD only slightly; Goebl, Flossmann, Widmer 2009 exclude them).
   **Sign:** positive = left hand first. This is the opposite of Goebl, Flossmann, Widmer 2009
   / 2010 (lower minus upper staff, positive = right hand early): negate before comparing with
   their corpus norms (mean +4.4 ms, mode +13 ms in Magaloff's Chopin).
   Citations (landscape 1.2, 1.5): Goebl 2001 (velocity artifact); Repp 1996 JASA (leads follow
   velocity; some pianists lead with the left hand consistently, so the mean may be stylistic);
   Goebl, Flossmann, Widmer 2009 / 2010 (corpus norms, faster pieces more synchronous, +-30 ms
   audibility band); Kim et al. 2021 (between-hand SD, experts vs amateurs).
4. **Tempo stability in sections without tempo markings** (``tempo_instability_*``). Sections
   are the F-03 tempo segments: the curve is split at score tempo markings, fermatas and
   pauses. Spans of gradual markings (rit., accel.; to their end, or ``gradual_default_bars``
   when open) are excluded. Within a section, the smooth log tempo ``l(b)`` (F-03, 1.5-bar
   cutoff) is compared with a phrase-level curve ``l_phrase(b)`` (the same robust P-spline fit
   with a ``phrase_bars``-bar cutoff, default 4 bars). The **phrase-level allowance** is
   everything in ``l_phrase``: tempo motion slower than about ``phrase_bars`` bars (phrase arcs,
   long ritardandi; Repp 1992) is interpretation, not instability.
   ``tempo_instability_log_sd`` is the RMS of ``l - l_phrase`` over the section's grid beats
   (tempo wobble at the 1.5-to-4-bar scale; the 4-bar allowance is our own choice, no source
   measures wobble beyond the phrase level; van Vugt et al. 2014 show phrasal slowing at run
   edges), pooled over sections of at least
   ``min_section_bars`` bars. Also: ``tempo_section_log_sd`` (total within-section SD of ``l``),
   ``tempo_phrase_log_sd`` (SD of ``l_phrase``) and ``tempo_drift_log`` (mean absolute net
   change of a straight-line fit to ``l`` across each section: rushing / dragging). Unit:
   natural-log tempo ratio.
5. **Pedal blur over harmony changes** (``pedal_blur_*``). Harmony changes come from the score
   by a simple rule: windows of ``harmony_window`` (default 1) quarter notes
   (``harmony_window_unit``; a quarter, not a beat, so 2/2 and 6/8 behave like 4/4); per window,
   the pitch classes holding at least ``harmony_min_weight`` of the window's sounding note-time,
   and the bass (lowest sounding pitch). A window starts a new harmony when its bass pitch class
   differs from the previous non-empty window's AND the two windows' pitch classes together do
   not fit one chord template (``harmony_templates="functional"``: major, minor, diminished,
   augmented, dominant 7, half-diminished 7, diminished 7). Major 7 and minor 7 are left out
   because two incomplete triads a fifth or a third apart (C-E + G-B, A-C-E + C-E-G) fill them.
   So Alberti figuration within one chord is not a change, and a pedal point hides a change.
   The change time is the performed onset of the first score onset in the window.
   **Validation** (F-04b, ``docs/specs/control-validation.md``): against DCML harmony labels on
   Batik-plays-Mozart (36 movements, 11,675 root changes), within 1 quarter note: precision
   0.749, recall 0.774, F1 0.761 (held-out sonatas F1 0.752). The F-04 rule (1-beat window, all
   templates) had F1 0.726. Misses: common bass / pedal points, two changes within one quarter;
   false alarms: mostly bass moves under one root (inversions), then non-chord tones.
   A change is **blurred** when the sustain pedal (CC64 >= ``pedal_threshold``) is down
   without a lift throughout ``[t - before * p, t + after * p]`` (p = local beat period;
   defaults 0.25 and 0.5 beats: a syncopated lift just after the new chord counts as clean).
   No published norm exists for this window (landscape 1.5); F-04b checked it and the
   threshold on sensor pedal data (Batik, Vienna 4x22) and kept both.
   ``pedal_blur_fraction`` = blurred / changes; ``pedal_blur_beats`` = mean held time after the
   change until the first lift (0 for clean changes; capped at the next change), in beats.
   Unit: fraction, beats. Needs pedal data: PianoCoRe has none; ASAP, MAESTRO, Vienna 4x22 and
   Batik do. With no CC64 events the features are NaN and ``pedal_available`` is False.
   Citations (landscape 1.2, 1.5): Liang, Fazekas, Sandler, JAES 2018 (pedalling from sensor
   data); Liang et al., EUSIPCO 2018 (legato pedalling: release immediately after the new chord
   onset); Repp 1996 (pedal timing varies with tempo and skill); Repp 1997 [U]; Bernays and
   Traube 2014 (part-pedalling: CC64 depth is continuous, a threshold loses it). The harmony
   rule is ours; DCML labels (Hentschel, Neuwirth, Rohrmeier, TISMIR 2021) validate it.

Citations: ``docs/research/2026-09-27-landscape.md`` sections 1.2, 1.3 and 1.5 (the F-04
citation map, applied here in F-04b): Repp 1992 (timing
follows phrase structure); Goebl 2001 (melody lead is mostly a velocity artifact; measure it with
velocity as a covariate); Hu et al., TISMIR 2026 (timing scales with tempo; chord asynchrony);
Liang, Fazekas, Sandler 2018 (pedalling). The partitura performance codec has asynchrony and pedal
helpers, but not per staff with a velocity covariate or against score harmony, hence this module.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from pianolens.features._score_utils import matched_note_frame, score_note_frame
from pianolens.features.correctness import measure_rows
from pianolens.features.tempo import (
    TempoConfig,
    TempoCurve,
    _beats_per_bar,
    fit_time_map,
    tempo_model,
)

__all__ = [
    "ControlConfig",
    "ControlResult",
    "control_features",
    "even_runs",
    "fine_timing_consensus",
    "hand_synchrony",
    "harmony_changes",
    "harmony_windows",
    "pedal_blur",
    "reference_residuals",
    "strict_runs",
    "tempo_stability",
    "timing_noise",
]

_MAD = 1.4826


@dataclass(frozen=True)
class ControlConfig:
    """Parameters of the tier B features (see the module docstring for each)."""

    min_references: int = 3
    run_min_notes: int = 6
    long_run_notes: int = 12
    strict_max_period: int = 4
    min_run_iois: int = 4
    equal_velocity_midi: float = 5.0
    phrase_bars: float = 4.0
    min_section_bars: float = 2.0
    exclude_gradual_markings: bool = True
    gradual_default_bars: float = 2.0
    harmony_window: float = 1.0
    harmony_window_unit: str = "quarter"
    harmony_templates: str = "functional"
    harmony_min_weight: float = 0.15
    pedal_threshold: int = 64
    pedal_before_beats: float = 0.25
    pedal_after_beats: float = 0.5
    pedal_max_blur_beats: float = 4.0


@dataclass(eq=False)
class ControlResult:
    """Output of :func:`control_features`.

    Attributes:
        bars: one row per score measure (``measure_idx`` = row of ``Score.measures``,
            ``measure_number``) with the per-bar columns of every feature.
        summary: summary values of every feature plus counts.
        timing: per score position: ``beat``, ``measure_idx``, ``dev_beats``, ``consensus_beats``,
            ``n_refs``, ``noise_beats``, ``noise_ms``, ``dev_nometric_beats``, ``outlier``.
        runs: per even run of the broad variant: ``run``, ``staff``, ``voice``, ``start_beat``,
            ``n_onsets``, ``n_matched``, ``dur_beat``, ``ioi_cv``, ``vel_sd_midi``,
            ``vel_trend_degree``.
        run_notes: per broad-run onset: ``run``, ``beat``, ``onset_sec``, ``vel_midi``,
            ``ioi_ratio`` (normalized IOI to the next onset), ``vel_resid_midi``.
        strict_runs, strict_run_notes: the same for the strict variant (``kind`` column in
            ``strict_runs``: ``monotone``, ``figure`` or ``mixed``).
        synchrony: per cross-staff onset: ``beat``, ``async_ms``, ``async_beats``, ``dv_midi``,
            ``resid_ms``.
        stability: per grid beat: ``beat``, ``section``, ``tempo_log_ratio``,
            ``phrase_log_ratio``, ``instability_log``, ``excluded`` (gradual marking).
        sections: per section: ``section``, ``start_beat``, ``end_beat``, ``n_beats``, stats.
        harmony: per detected harmony change: ``beat``, ``quarter``, ``time_sec``, ``blurred``,
            ``blur_beats``.
        params: the configuration used.
    """

    bars: pd.DataFrame
    summary: dict[str, Any]
    timing: pd.DataFrame
    runs: pd.DataFrame
    run_notes: pd.DataFrame
    synchrony: pd.DataFrame
    stability: pd.DataFrame
    sections: pd.DataFrame
    harmony: pd.DataFrame
    params: dict[str, Any] = field(default_factory=dict)
    strict_runs: pd.DataFrame = field(default_factory=pd.DataFrame)
    strict_run_notes: pd.DataFrame = field(default_factory=pd.DataFrame)


def _rms(x: np.ndarray) -> float:
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    return float(np.sqrt(np.mean(x**2))) if len(x) else float("nan")


def _robust_sd(x: np.ndarray) -> float:
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    return _MAD * float(np.median(np.abs(x - np.median(x)))) if len(x) else float("nan")


def _per_bar(idx: np.ndarray, values: np.ndarray, n_bars: int, how: str) -> np.ndarray:
    """Aggregate ``values`` per bar index (rms / mean / sum / count / robust_sd)."""
    out = np.full(n_bars, 0.0 if how in ("sum", "count") else np.nan)
    idx = np.asarray(idx, dtype=int)
    values = np.asarray(values, dtype=float)
    ok = (idx >= 0) & (idx < n_bars) & (np.isfinite(values) | (how == "count"))
    if not ok.any():
        return out
    df = pd.DataFrame({"b": idx[ok], "v": values[ok]})
    g = df.groupby("b")["v"]
    agg = {
        "rms": lambda: g.apply(lambda s: float(np.sqrt(np.mean(s**2)))),
        "mean": g.mean,
        "sum": g.sum,
        "count": g.size,
        "robust_sd": lambda: g.apply(_robust_sd),
    }[how]()
    out[agg.index.to_numpy(int)] = agg.to_numpy(float)
    return out


# --------------------------------------------------------------------------- 1. timing noise


def reference_residuals(curve: TempoCurve) -> pd.Series:
    """A reference performance's normalized residual per score position, for the consensus.

    Returns ``dev_beats`` indexed by score beat (rounded to 1e-6), NaN at tempo outliers. Use the
    tempo model of a reference performance aligned to the same performed (unfolded) score.
    """
    p = curve.positions
    v = np.where(p["outlier"].to_numpy(bool), np.nan, p["dev_beats"].to_numpy(float))
    return pd.Series(v, index=p["beat"].round(6).to_numpy(), name="dev_beats")


def fine_timing_consensus(
    references: Mapping[str, pd.Series | TempoCurve] | Sequence[pd.Series | TempoCurve],
    *,
    leave_out: str | None = None,
    min_references: int = 3,
) -> pd.DataFrame:
    """Expert-consensus fine timing: mean reference residual per score position.

    Args:
        references: per-performance residual series (``dev_beats`` indexed by score beat, as
            :func:`reference_residuals` returns) or :class:`TempoCurve` objects. A mapping is
            keyed by performance id.
        leave_out: key of the target performance, dropped from a mapping (leave-one-out).
        min_references: positions with fewer non-NaN references get NaN.

    Returns:
        DataFrame indexed by beat: ``consensus_beats``, ``n_refs``, ``sd_refs``.
    """
    items = list(references.items()) if isinstance(references, Mapping) else list(
        enumerate(references))
    cols = []
    for k, r in items:
        if leave_out is not None and k == leave_out:
            continue
        s = reference_residuals(r) if isinstance(r, TempoCurve) else r
        s = s.copy()
        s.index = np.round(np.asarray(s.index, dtype=float), 6)
        cols.append(s[~s.index.duplicated()].rename(str(k)))
    if not cols:
        return pd.DataFrame(columns=["consensus_beats", "n_refs", "sd_refs"], dtype=float)
    m = pd.concat(cols, axis=1)
    n = m.notna().sum(axis=1)
    out = pd.DataFrame({"consensus_beats": m.mean(axis=1), "n_refs": n,
                        "sd_refs": m.std(axis=1, ddof=1)})  # fmt: skip
    out.loc[n < min_references, "consensus_beats"] = np.nan
    return out.sort_index()


def timing_noise(
    curve: TempoCurve,
    references: Mapping[str, Any] | Sequence[Any] | None = None,
    *,
    leave_out: str | None = None,
    min_references: int = 3,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Timing noise: residual minus leave-one-out expert consensus, and the F-03 fallback.

    Returns ``(timing, summary)``; see the module docstring (feature 1).
    """
    p = curve.positions
    dof_k = float(curve.summary.get("dof_factor", 1.0))
    key = p["beat"].round(6).to_numpy()
    t = pd.DataFrame({
        "beat": p["beat"].to_numpy(float),
        "measure_idx": p["measure_idx"].to_numpy(int),
        "dev_beats": p["dev_beats"].to_numpy(float),
        "beat_period_sec": p["beat_period_sec"].to_numpy(float),
        "dev_nometric_beats": p["dev_nometric_beats"].to_numpy(float)
        if "dev_nometric_beats" in p else np.nan,
        "outlier": p["outlier"].to_numpy(bool),
    })  # fmt: skip
    if references is not None:
        cons = fine_timing_consensus(references, leave_out=leave_out,
                                     min_references=min_references)  # fmt: skip
        c = cons.reindex(key)
        t["consensus_beats"] = c["consensus_beats"].to_numpy(float)
        t["n_refs"] = c["n_refs"].fillna(0).to_numpy(int)
    else:
        t["consensus_beats"] = np.nan
        t["n_refs"] = 0
    t["noise_beats"] = np.where(t["outlier"], np.nan, t["dev_beats"] - t["consensus_beats"])
    t["noise_ms"] = 1000 * t["noise_beats"] * t["beat_period_sec"]

    inl = ~t["outlier"]
    has = inl & t["noise_beats"].notna()
    n_inl = int(inl.sum())
    coverage = float(has.sum()) / n_inl if n_inl else 0.0
    dev_ms = (t.loc[has, "dev_beats"] ** 2).mean() if has.any() else np.nan
    nz_ms = (t.loc[has, "noise_beats"] ** 2).mean() if has.any() else np.nan
    s: dict[str, Any] = {
        "timing_noise_rms_beats": dof_k * math.sqrt(nz_ms) if has.any() else np.nan,
        "timing_noise_rms_ms": dof_k * _rms(t.loc[has, "noise_ms"]) if has.any() else np.nan,
        "timing_noise_coverage": coverage,
        "timing_noise_n_refs_median": float(t.loc[has, "n_refs"].median()) if has.any()
        else 0.0,
        "timing_consensus_r2": 1.0 - nz_ms / dev_ms if has.any() and dev_ms > 0 else np.nan,
        "jitter_nometric_rms_ms": float(curve.summary.get("jitter_nometric_rms_ms", np.nan)),
        "jitter_nometric_rms_beats": float(curve.summary.get("jitter_nometric_rms_beats",
                                                              np.nan)),
    }  # fmt: skip
    use_cons = coverage >= 0.5
    s["timing_noise_source"] = "consensus" if use_cons else "nometric"
    s["timing_noise_best_rms_ms"] = (s["timing_noise_rms_ms"] if use_cons
                                     else s["jitter_nometric_rms_ms"])  # fmt: skip
    s["timing_noise_best_rms_beats"] = (s["timing_noise_rms_beats"] if use_cons
                                        else s["jitter_nometric_rms_beats"])  # fmt: skip
    return t, s


# --------------------------------------------------------------------------- 2. evenness


def even_runs(score: Any, min_notes: int = 6) -> pd.DataFrame:
    """Runs of equal-duration, rest-free consecutive onsets in one (staff, voice) stream.

    Returns one row per run onset: ``run``, ``staff``, ``voice``, ``quarter``, ``beat``,
    ``dur_quarter``, ``dur_beat``, ``pos`` (index within the run). Grace notes are ignored.
    """
    sf = score_note_frame(score)
    sf = sf[~sf["is_grace"] & (sf["dur_quarter"] > 0)]
    rows: list[pd.DataFrame] = []
    run_id = 0
    for (staff, voice), g in sf.groupby(["staff", "voice"], sort=True):
        on = (g.groupby("quarter", sort=True)
              .agg(beat=("beat", "first"), dq=("dur_quarter", "min"), db=("dur_beat", "min"),
                   pitches=("pitch", lambda x: tuple(sorted(int(v) for v in x))))
              .reset_index())  # fmt: skip
        q, d = on["quarter"].to_numpy(), on["dq"].to_numpy()
        if len(q) < min_notes:
            continue
        link = np.isclose(q[1:], q[:-1] + d[:-1], atol=1e-6) & np.isclose(d[1:], d[:-1],
                                                                          atol=1e-6)
        start = 0
        for k in range(len(link) + 1):
            if k < len(link) and link[k]:
                continue
            end = k  # run covers onsets start..end
            if end - start + 1 >= min_notes:
                r = on.iloc[start:end + 1].copy()
                r["run"], r["staff"], r["voice"] = run_id, int(staff), int(voice)
                r["pos"] = np.arange(len(r))
                rows.append(r)
                run_id += 1
            start = k + 1
    cols = ["run", "staff", "voice", "quarter", "beat", "dur_quarter", "dur_beat", "pos",
            "pitches"]
    if not rows:
        return pd.DataFrame(columns=cols)
    out = pd.concat(rows, ignore_index=True).rename(columns={"dq": "dur_quarter",
                                                             "db": "dur_beat"})
    return out[cols]


def _strict_mask(pitches: list[tuple[int, ...]], min_notes: int, max_period: int
                 ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Onsets covered by a monotone stretch / a repeated figure of >= ``min_notes`` onsets."""
    n = len(pitches)
    mono, fig = np.zeros(n, bool), np.zeros(n, bool)
    top = np.array([max(p) for p in pitches], dtype=float)
    sign = np.sign(np.diff(top))
    k = 0
    while k < n - 1:  # maximal stretches of equal, nonzero step direction
        j = k
        while j + 1 < n - 1 and sign[j + 1] == sign[k] and sign[k] != 0:
            j += 1
        if sign[k] != 0 and j - k + 2 >= min_notes:
            mono[k:j + 2] = True
        k = j + 1
    for per in range(1, max_period + 1):
        same = np.array([pitches[i] == pitches[i - per] for i in range(per, n)], bool)
        i = 0
        while i < len(same):
            if not same[i]:
                i += 1
                continue
            j = i
            while j + 1 < len(same) and same[j + 1]:
                j += 1
            lo, hi = i, j + per  # onset indices lo..hi
            if hi - lo + 1 >= max(min_notes, 2 * per):
                fig[lo:hi + 1] = True
            i = j + 1
    return mono | fig, mono, fig


def strict_runs(score: Any, min_notes: int = 6, max_period: int = 4) -> pd.DataFrame:
    """Strict even runs: sub-beat monotone runs or repeated figures (module docstring, 2).

    Built inside the broad runs of :func:`even_runs`. Returns the same columns plus ``kind``
    (``monotone``, ``figure`` or ``mixed``) and ``broad_run`` (the broad run it lies in).
    """
    broad = even_runs(score, min_notes)
    cols = ["run", "staff", "voice", "quarter", "beat", "dur_quarter", "dur_beat", "pos",
            "pitches", "kind", "broad_run"]
    if broad.empty:
        return pd.DataFrame(columns=cols)
    rows, run_id = [], 0
    for rid, g in broad.groupby("run", sort=True):
        g = g.sort_values("pos")
        if not (g["dur_beat"] < 1 - 1e-6).all():
            continue
        cover, mono, fig = _strict_mask(list(g["pitches"]), min_notes, max_period)
        k, n = 0, len(g)
        while k < n:
            if not cover[k]:
                k += 1
                continue
            j = k
            while j + 1 < n and cover[j + 1]:
                j += 1
            if j - k + 1 >= min_notes:
                r = g.iloc[k:j + 1].copy()
                m, f = mono[k:j + 1].any(), fig[k:j + 1].any()
                r["kind"] = "mixed" if m and f else ("monotone" if m else "figure")
                r["broad_run"], r["run"], r["pos"] = int(rid), run_id, np.arange(len(r))
                rows.append(r)
                run_id += 1
            k = j + 1
    if not rows:
        return pd.DataFrame(columns=cols)
    return pd.concat(rows, ignore_index=True)[cols]


def _evenness(ap: Any, curve: TempoCurve, matched: pd.DataFrame, cfg: ControlConfig,
              runs: pd.DataFrame | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    runs = even_runs(ap.score, cfg.run_min_notes) if runs is None else runs
    run_cols = ["run", "staff", "voice", "start_beat", "start_quarter", "n_onsets",
                "n_matched", "dur_beat", "ioi_cv", "vel_sd_midi", "vel_trend_degree",
                "n_iois", "ioi_scale", "vel_scale", "note_rate_nps"]  # fmt: skip
    if "kind" in runs:
        run_cols.append("kind")
    if runs.empty:
        return pd.DataFrame(columns=run_cols), pd.DataFrame(
            columns=["run", "beat", "quarter", "onset_sec", "vel_midi", "ioi_ratio",
                     "ioi_rel_scaled", "vel_resid_scaled", "ioi_sec"])
    gross = set(curve.positions.loc[curve.positions["gross_outlier"], "beat"].round(6))
    mt = matched[~matched["beat"].round(6).isin(gross)]
    perf = (mt.groupby(["staff", "voice", "quarter"])
            .agg(onset_sec=("onset_sec", "median"), vel_midi=("vel_midi", "mean"))
            .reset_index())  # fmt: skip
    rn = runs.merge(perf, on=["staff", "voice", "quarter"], how="left")
    tmap = curve.time_map
    run_rows, note_parts = [], []
    for rid, g in rn.groupby("run", sort=True):
        g = g.sort_values("pos").copy()
        b = g["beat"].to_numpy(float)
        t = g["onset_sec"].to_numpy(float)
        v = g["vel_midi"].to_numpy(float)
        seg = tmap.segment_of(b)
        ts = tmap.time(b, seg)
        # IOI to the next score onset, both matched, same tempo segment
        ioi = np.full(len(g), np.nan)
        exp_ = np.full(len(g), np.nan)
        ok = np.isfinite(t[:-1]) & np.isfinite(t[1:]) & (seg[:-1] == seg[1:])
        ioi[:-1] = np.where(ok, t[1:] - t[:-1], np.nan)
        exp_[:-1] = np.where(ok, tmap.time(b[1:], seg[:-1]) - ts[:-1], np.nan)
        with np.errstate(divide="ignore", invalid="ignore"):
            ratio = ioi / exp_
        good = np.isfinite(ratio) & (exp_ > 0)
        m = int(good.sum())
        ioi_used = np.where(good, ioi, np.nan)
        rate = m / float(np.nansum(ioi_used)) if m and np.nansum(ioi_used) > 0 else np.nan
        cv, rel_scaled, ioi_scale = np.nan, np.full(len(g), np.nan), np.nan
        if m >= cfg.min_run_iois:
            mu = float(np.mean(ratio[good]))
            rel = ratio / mu - 1.0
            ioi_scale = math.sqrt(m / (m - 1))
            cv = float(np.sqrt(np.sum(rel[good] ** 2) / (m - 1)))
            rel_scaled = np.where(good, rel * ioi_scale, np.nan)
        # velocity: remove a polynomial trend in score position
        vok = np.isfinite(v)
        nv = int(vok.sum())
        deg = 2 if nv >= cfg.long_run_notes else 1
        vsd, vres_scaled, vel_scale = np.nan, np.full(len(g), np.nan), np.nan
        if nv >= max(cfg.run_min_notes - 1, deg + 3):
            x = (b - b[0]) / max(b[-1] - b[0], 1e-9)
            coef = np.polyfit(x[vok], v[vok], deg)
            res = v - np.polyval(coef, x)
            vel_scale = math.sqrt(nv / (nv - deg - 1))
            vsd = float(np.sqrt(np.sum(res[vok] ** 2) / (nv - deg - 1)))
            vres_scaled = np.where(vok, res * vel_scale, np.nan)
        run_rows.append({
            "run": int(rid), "staff": int(g["staff"].iloc[0]), "voice": int(g["voice"].iloc[0]),
            "start_beat": float(b[0]), "start_quarter": float(g["quarter"].iloc[0]),
            "n_onsets": len(g), "n_matched": int(np.isfinite(t).sum()),
            "dur_beat": float(g["dur_beat"].iloc[0]), "ioi_cv": cv, "vel_sd_midi": vsd,
            "vel_trend_degree": deg, "n_iois": m, "ioi_scale": ioi_scale,
            "vel_scale": vel_scale, "note_rate_nps": rate,
            **({"kind": g["kind"].iloc[0]} if "kind" in g else {}),
        })  # fmt: skip
        note_parts.append(pd.DataFrame({
            "run": int(rid), "beat": b, "quarter": g["quarter"].to_numpy(float),
            "onset_sec": t, "vel_midi": v, "ioi_ratio": ratio, "ioi_rel_scaled": rel_scaled,
            "vel_resid_scaled": vres_scaled, "ioi_sec": ioi_used,
        }))  # fmt: skip
    return pd.DataFrame(run_rows, columns=run_cols), pd.concat(note_parts, ignore_index=True)


# --------------------------------------------------------------------------- 3. synchrony


def hand_synchrony(matched: pd.DataFrame, curve: TempoCurve, cfg: ControlConfig | None = None
                   ) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Asynchrony between staff 1 and staff 2 at notated-simultaneous onsets (feature 3)."""
    cfg = cfg or ControlConfig()
    cols = ["beat", "quarter", "measure_idx", "async_ms", "async_beats", "dv_midi", "resid_ms",
            "n_rh", "n_lh"]  # fmt: skip
    empty = {k: np.nan for k in (
        "hand_async_mean_ms", "hand_async_median_ms", "hand_async_sd_ms",
        "hand_async_vel_slope_ms", "hand_async_resid_sd_ms", "hand_async_resid_sd_beats",
        "hand_async_equalvel_mean_ms", "hand_async_equalvel_sd_ms", "hand_async_sd_beats")}
    empty.update({"n_cross_staff_onsets": 0, "n_equalvel_onsets": 0})
    gross = set(curve.positions.loc[curve.positions["gross_outlier"], "beat"].round(6))
    mt = matched[matched["staff"].isin([1, 2]) & ~matched["beat"].round(6).isin(gross)]
    if mt.empty:
        return pd.DataFrame(columns=cols), empty
    g = (mt.groupby(["quarter", "staff"])
         .agg(t=("onset_sec", "mean"), v=("vel_midi", "mean"), n=("onset_sec", "size"),
              beat=("beat", "first"), measure_idx=("measure_idx", "first"))
         .reset_index())  # fmt: skip
    rh = g[g["staff"] == 1].set_index("quarter")
    lh = g[g["staff"] == 2].set_index("quarter")
    q = rh.index.intersection(lh.index)
    if len(q) == 0:
        return pd.DataFrame(columns=cols), empty
    rh, lh = rh.loc[q], lh.loc[q]
    b = rh["beat"].to_numpy(float)
    per = curve.time_map.period(b)
    a_ms = 1000 * (rh["t"].to_numpy() - lh["t"].to_numpy())
    dv = rh["v"].to_numpy() - lh["v"].to_numpy()
    sd = _robust_sd(a_ms)
    med = float(np.median(a_ms))
    inl = np.abs(a_ms - med) <= 3 * max(sd, 1e-9) if sd > 0 else np.ones(len(a_ms), bool)
    slope, icpt = 0.0, float(np.mean(a_ms[inl])) if inl.any() else med
    if inl.sum() >= 3 and np.ptp(dv[inl]) > 0:
        slope, icpt = (float(x) for x in np.polyfit(dv[inl], a_ms[inl], 1))
    resid = a_ms - (icpt + slope * dv)
    df = pd.DataFrame({
        "beat": b, "quarter": np.asarray(q, float), "measure_idx": rh["measure_idx"].to_numpy(),
        "async_ms": a_ms, "async_beats": a_ms / 1000 / per, "dv_midi": dv, "resid_ms": resid,
        "n_rh": rh["n"].to_numpy(), "n_lh": lh["n"].to_numpy(),
    })  # fmt: skip
    eq = np.abs(dv) <= cfg.equal_velocity_midi
    s = {
        "hand_async_mean_ms": float(np.mean(a_ms)),
        "hand_async_median_ms": med,
        "hand_async_sd_ms": sd,
        "hand_async_sd_beats": _robust_sd(df["async_beats"]),
        "hand_async_vel_slope_ms": slope,
        "hand_async_resid_sd_ms": _robust_sd(resid),
        "hand_async_resid_sd_beats": _robust_sd(resid / 1000 / per),
        "hand_async_equalvel_mean_ms": float(np.mean(a_ms[eq])) if eq.any() else np.nan,
        "hand_async_equalvel_sd_ms": _robust_sd(a_ms[eq]) if eq.sum() >= 3 else np.nan,
        "n_cross_staff_onsets": len(df),
        "n_equalvel_onsets": int(eq.sum()),
    }
    return df, s


# --------------------------------------------------------------------------- 4. stability


def _gradual_spans(score: Any, bpb: float, default_bars: float) -> list[tuple[float, float]]:
    part = getattr(score, "part", None)
    if part is None:
        return []
    import partitura as pt

    spans = []
    bm = part.beat_map
    for cls in (pt.score.IncreasingTempoDirection, pt.score.DecreasingTempoDirection):
        for d in part.iter_all(cls, include_subclasses=True):
            s = float(bm(d.start.t))
            end = getattr(d, "end", None)
            e = float(bm(end.t)) if end is not None else s + default_bars * bpb
            spans.append((s, max(e, s + 1.0)))
    return spans


def tempo_stability(ap: Any, curve: TempoCurve, cfg: ControlConfig | None = None
                    ) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """Tempo wobble beyond a phrase-level allowance within unmarked sections (feature 4)."""
    cfg = cfg or ControlConfig()
    bpb = float(curve.summary.get("beats_per_bar", _beats_per_bar(ap.score)))
    g = curve.beats.copy()
    pos = curve.positions
    lr = g["tempo_log_ratio"].to_numpy(float)
    gp = g["beat_period_sec"].to_numpy(float)
    okp = np.isfinite(lr) & (gp > 0)
    log_pg = float(np.median(lr[okp] + np.log(gp[okp]))) if okp.any() else np.nan
    spans = _gradual_spans(ap.score, bpb, cfg.gradual_default_bars) \
        if cfg.exclude_gradual_markings else []
    excl = np.zeros(len(g), bool)
    for s, e in spans:
        excl |= (g["beat"].to_numpy() >= s) & (g["beat"].to_numpy() < e)
    g["phrase_log_ratio"] = np.nan
    g["excluded"] = excl
    sec_rows = []
    for sid in np.unique(g["segment"]):
        gm = (g["segment"] == sid).to_numpy()
        pm = (pos["segment"] == sid).to_numpy() & ~pos["outlier"].to_numpy(bool)
        pb = pos.loc[pm, "beat"].to_numpy(float)
        gb = g.loc[gm, "beat"].to_numpy(float)
        span = (pb[-1] - pb[0]) if len(pb) else 0.0
        row = {"section": int(sid), "start_beat": float(gb.min()) if len(gb) else np.nan,
               "end_beat": float(gb.max()) if len(gb) else np.nan, "n_beats": int(gm.sum()),
               "n_beats_used": 0, "section_log_sd": np.nan, "phrase_log_sd": np.nan,
               "instability_log_sd": np.nan, "drift_log": np.nan}  # fmt: skip
        if span >= cfg.min_section_bars * bpb and len(pb) >= 6:
            tm, _ = fit_time_map(pb, pos.loc[pm, "time_sec"].to_numpy(float),
                                 period_beats=cfg.phrase_bars * bpb,
                                 knot_spacing=TempoConfig().knot_spacing_beats)  # fmt: skip
            inside = (gb >= pb[0]) & (gb <= pb[-1])
            pp = tm.period(gb)
            with np.errstate(divide="ignore", invalid="ignore"):
                ph = np.where(inside & (pp > 0), log_pg - np.log(pp), np.nan)
            g.loc[gm, "phrase_log_ratio"] = ph
            use = inside & ~excl[gm] & np.isfinite(ph) & np.isfinite(lr[gm])
            if use.sum() >= 3:
                lv, pv, bv = lr[gm][use], ph[use], gb[use]
                slope = np.polyfit(bv, lv, 1)[0]
                row.update({
                    "n_beats_used": int(use.sum()),
                    "section_log_sd": float(np.std(lv)),
                    "phrase_log_sd": float(np.std(pv)),
                    "instability_log_sd": _rms(lv - pv),
                    "drift_log": float(slope * (bv[-1] - bv[0])),
                })  # fmt: skip
        sec_rows.append(row)
    g["instability_log"] = np.where(g["excluded"], np.nan,
                                    g["tempo_log_ratio"] - g["phrase_log_ratio"])  # fmt: skip
    sections = pd.DataFrame(sec_rows)
    ok = sections["n_beats_used"] > 0 if len(sections) else pd.Series(dtype=bool)
    su = sections[ok] if len(sections) else sections
    w = su["n_beats_used"].to_numpy(float) if len(su) else np.zeros(0)

    def pooled(col: str) -> float:
        if not len(su):
            return float("nan")
        return float(np.sqrt(np.sum(w * su[col].to_numpy(float) ** 2) / np.sum(w)))

    s = {
        "tempo_instability_log_sd": pooled("instability_log_sd"),
        "tempo_section_log_sd": pooled("section_log_sd"),
        "tempo_phrase_log_sd": pooled("phrase_log_sd"),
        "tempo_drift_log": float(np.average(np.abs(su["drift_log"]), weights=w)) if len(su)
        else float("nan"),
        "n_stability_sections": len(su),
        "n_sections": len(sections),
        "n_gradual_marking_spans": len(spans),
        "stability_beats_excluded": int(excl.sum()),
    }
    cols = ["beat", "measure_idx", "segment", "tempo_log_ratio", "phrase_log_ratio",
            "instability_log", "excluded"]
    return g[cols].rename(columns={"segment": "section"}), sections, s


# --------------------------------------------------------------------------- 5. pedal blur

_CHORD_SHAPES = {"maj": (0, 4, 7), "min": (0, 3, 7), "dim": (0, 3, 6), "aug": (0, 4, 8),
                 "dom7": (0, 4, 7, 10), "maj7": (0, 4, 7, 11), "min7": (0, 3, 7, 10),
                 "hdim7": (0, 3, 6, 10), "dim7": (0, 3, 6, 9)}  # fmt: skip


def _chord_set(names: Sequence[str]) -> list[frozenset[int]]:
    return [frozenset((r + i) % 12 for i in _CHORD_SHAPES[n]) for n in names for r in range(12)]


_TEMPLATE_SETS = {
    "all": _chord_set(list(_CHORD_SHAPES)),
    "no_maj7": _chord_set([n for n in _CHORD_SHAPES if n != "maj7"]),
    "functional": _chord_set(["maj", "min", "dim", "aug", "dom7", "hdim7", "dim7"]),
    "triads": _chord_set(["maj", "min", "dim", "aug"]),
}
_CHORDS = _TEMPLATE_SETS["all"]


def harmony_windows(score: Any, window: float = 1.0, min_weight: float = 0.15,
                    unit: str = "quarter") -> pd.DataFrame:
    """Per-window pitch content used by :func:`harmony_changes`.

    One row per non-empty window of ``window`` units (``unit``: score ``beat`` or
    ``quarter`` note): ``window_start`` (in that unit), ``bass`` (pitch
    class of the lowest sounding pitch), ``pcs`` (frozenset: pitch classes holding at least
    ``min_weight`` of the window's sounding note-time, plus the bass), ``first_onset`` (beat of
    the first score onset in the window, NaN when only held notes sound), ``quarter`` and
    ``measure_idx`` of that onset (NaN / -1 when none).
    """
    sf = score_note_frame(score)
    sf = sf[~sf["is_grace"] & (sf["dur_beat"] > 0)]
    cols = ["window_start", "bass", "pcs", "first_onset", "quarter", "measure_idx"]
    if sf.empty:
        return pd.DataFrame(columns=cols)
    u = "beat" if unit == "beat" else "quarter"
    on, dur = sf[u].to_numpy(float), sf[f"dur_{u}"].to_numpy(float)
    off = on + dur
    pitch = sf["pitch"].to_numpy(int)
    qarr = sf["quarter"].to_numpy(float)
    barr = sf["beat"].to_numpy(float)
    mi = sf["measure_idx"].to_numpy(int)
    order = np.argsort(on, kind="stable")
    rows = []
    w0 = math.floor(on.min() / window) * window
    while w0 < off.max() - 1e-9:
        w1 = w0 + window
        ov = np.minimum(off, w1) - np.maximum(on, w0)
        m = ov > 1e-9
        if m.any():
            wts = pd.Series(ov[m]).groupby(pitch[m] % 12).sum()
            wts = wts / wts.sum()
            pcs = set(int(x) for x in wts.index[wts >= min_weight])
            bass = int(pitch[m].min()) % 12
            pcs.add(bass)
            att = order[(on[order] >= w0 - 1e-9) & (on[order] < w1 - 1e-9)]
            k = att[0] if len(att) else None
            rows.append((float(w0), bass, frozenset(pcs),
                         float(barr[k]) if k is not None else np.nan,
                         float(qarr[k]) if k is not None else np.nan,
                         int(mi[k]) if k is not None else -1))  # fmt: skip
        w0 = w1
    return pd.DataFrame(rows, columns=cols)


def harmony_changes(score: Any, window: float = 1.0, min_weight: float = 0.15, *,
                    unit: str = "quarter", windows: pd.DataFrame | None = None,
                    templates: str = "functional", require_bass_change: bool = True
                    ) -> pd.DataFrame:
    """Score harmony changes by the bass-plus-chord-template rule (module docstring, feature 5).

    Returns ``beat`` (first score onset in the window that starts the new harmony), ``quarter``,
    ``window_start``, ``bass``, ``prev_bass``, ``pcs`` (sorted tuple), ``measure_idx``.
    ``templates`` (a key of ``_TEMPLATE_SETS``), ``unit`` and ``require_bass_change`` exist for
    the F-04b validation (``docs/specs/control-validation.md``); the defaults are the documented
    rule. ``windows``: precomputed :func:`harmony_windows` output.
    """
    cols = ["beat", "quarter", "window_start", "bass", "prev_bass", "pcs", "measure_idx"]
    w = harmony_windows(score, window, min_weight, unit) if windows is None else windows
    chords = _TEMPLATE_SETS[templates]
    rows, prev = [], None
    for r in w.itertuples(index=False):
        if prev is not None and (r.bass != prev[0] or not require_bass_change) \
                and np.isfinite(r.first_onset) \
                and not any((r.pcs | prev[1]) <= c for c in chords):
            rows.append((r.first_onset, r.quarter, r.window_start, r.bass, prev[0],
                         tuple(sorted(r.pcs)), r.measure_idx))
        prev = (r.bass, r.pcs)
    return pd.DataFrame(rows, columns=cols)


def _pedal_state(pedal: np.ndarray, threshold: int) -> tuple[np.ndarray, np.ndarray]:
    """Sustain-pedal step function: (event times, down flag after each event)."""
    if pedal is None or len(pedal) == 0:
        return np.zeros(0), np.zeros(0, bool)
    p = pedal[pedal["number"] == 64]
    p = p[np.argsort(p["time_sec"], kind="stable")]
    return p["time_sec"].astype(float), p["value"].astype(int) >= threshold


def _down_at(times: np.ndarray, down: np.ndarray, t: float) -> bool:
    k = int(np.searchsorted(times, t, side="right")) - 1
    return bool(down[k]) if k >= 0 else False


def pedal_blur(ap: Any, curve: TempoCurve, cfg: ControlConfig | None = None,
               changes: pd.DataFrame | None = None) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Share of score harmony changes the sustain pedal is held across (feature 5)."""
    cfg = cfg or ControlConfig()
    times, down = _pedal_state(ap.performance.pedal, cfg.pedal_threshold)
    ch = harmony_changes(ap.score, cfg.harmony_window, cfg.harmony_min_weight,
                         unit=cfg.harmony_window_unit, templates=cfg.harmony_templates) \
        if changes is None else changes.copy()
    avail = len(times) > 0
    s: dict[str, Any] = {"pedal_available": avail, "n_pedal_events": len(times),
                         "n_harmony_changes": len(ch)}  # fmt: skip
    ch["time_sec"] = np.nan
    ch["beat_period_sec"] = np.nan
    ch["blurred"] = np.nan
    ch["blur_beats"] = np.nan
    if not avail or ch.empty:
        s.update({"pedal_blur_fraction": np.nan, "pedal_blur_beats": np.nan,
                  "pedal_down_fraction": np.nan, "n_harmony_changes_used": 0})
        return ch, s
    pos = curve.positions
    ptime = dict(zip(pos["beat"].round(6), np.where(pos["gross_outlier"], np.nan,
                                                    pos["time_sec"]), strict=True))
    b = ch["beat"].to_numpy(float)
    tc = np.array([ptime.get(round(x, 6), np.nan) for x in b])
    tc = np.where(np.isfinite(tc), tc, curve.time_map.time(b))
    per = curve.time_map.period(b)
    nxt = np.append(tc[1:], np.inf)
    blurred, blur_b = np.zeros(len(b)), np.zeros(len(b))
    for i in range(len(b)):
        a0 = tc[i] - cfg.pedal_before_beats * per[i]
        a1 = tc[i] + cfg.pedal_after_beats * per[i]
        lifts = times[(times > a0) & (times <= a1) & ~down]
        held = _down_at(times, down, a0) and len(lifts) == 0
        blurred[i] = float(held)
        if held:
            later = times[(times > a1) & ~down]
            t_up = later[0] if len(later) else np.inf
            cap = min(nxt[i], tc[i] + cfg.pedal_max_blur_beats * per[i])
            blur_b[i] = (min(t_up, cap) - tc[i]) / per[i]
    ch["time_sec"], ch["beat_period_sec"] = tc, per
    ch["blurred"], ch["blur_beats"] = blurred, blur_b
    # fraction of the performance time with the pedal down (context)
    t_lo = float(ap.performance.notes["onset_sec"].min())
    t_hi = float((ap.performance.notes["onset_sec"] + ap.performance.notes["duration_sec"]).max())
    grid = np.linspace(t_lo, t_hi, 2000) if t_hi > t_lo else np.array([t_lo])
    idx = np.searchsorted(times, grid, side="right") - 1
    dfrac = float(np.mean(np.where(idx >= 0, down[np.maximum(idx, 0)], False)))
    s.update({"pedal_blur_fraction": float(blurred.mean()),
              "pedal_blur_beats": float(blur_b.mean()), "pedal_down_fraction": dfrac,
              "n_harmony_changes_used": len(b)})  # fmt: skip
    return ch, s


# --------------------------------------------------------------------------- main entry


def control_features(
    ap: Any,
    curve: TempoCurve | None = None,
    *,
    references: Mapping[str, Any] | Sequence[Any] | None = None,
    config: ControlConfig | None = None,
) -> ControlResult:
    """All tier B control features of an aligned performance.

    Args:
        ap: ``AlignedPerformance`` from ``align_performance`` (score with ``part`` kept, for tempo
            and gradual markings; staff numbers from the score note array).
        curve: its F-03 :func:`tempo_model` output; computed with defaults when omitted.
        references: other performances of the same piece on the same performed score, as a
            mapping ``performance_id -> residual series or TempoCurve`` (the target's own id is
            left out) or a sequence; see :func:`fine_timing_consensus`. None: fallback only.
        config: :class:`ControlConfig`.

    Returns:
        :class:`ControlResult`.
    """
    cfg = config or ControlConfig()
    curve = curve if curve is not None else tempo_model(ap)
    matched, counts = matched_note_frame(ap)
    ms = ap.score.measures
    nb = len(ms)

    timing, s_t = timing_noise(curve, references, leave_out=ap.performance.performance_id,
                               min_references=cfg.min_references)  # fmt: skip
    runs, run_notes = _evenness(ap, curve, matched, cfg)
    sruns, srun_notes = _evenness(
        ap, curve, matched, cfg,
        strict_runs(ap.score, cfg.run_min_notes, cfg.strict_max_period))
    sync, s_h = hand_synchrony(matched, curve, cfg)
    stab, sections, s_s = tempo_stability(ap, curve, cfg)
    harm, s_p = pedal_blur(ap, curve, cfg)

    bars = pd.DataFrame({"measure_idx": np.arange(nb),
                         "measure_number": ms["number"] if nb else np.zeros(0, int)})
    inl = ~timing["outlier"]
    ti = timing["measure_idx"].to_numpy(int)
    k = float(curve.summary.get("dof_factor", 1.0))
    bars["timing_noise_rms_beats"] = k * _per_bar(ti, timing["noise_beats"].where(inl), nb, "rms")
    bars["timing_noise_rms_ms"] = k * _per_bar(ti, timing["noise_ms"].where(inl), nb, "rms")
    nm_ms = 1000 * timing["dev_nometric_beats"] * timing["beat_period_sec"]
    bars["jitter_nometric_rms_ms"] = k * _per_bar(ti, nm_ms.where(inl), nb, "rms")
    bars["jitter_nometric_rms_beats"] = k * _per_bar(
        ti, timing["dev_nometric_beats"].where(inl), nb, "rms")
    for pre, rn in (("even", run_notes), ("even_strict", srun_notes)):
        if len(rn):
            rb = measure_rows(ms, rn["quarter"].to_numpy(float))
            bars[f"{pre}_ioi_cv"] = _per_bar(rb, rn["ioi_rel_scaled"], nb, "rms")
            bars[f"{pre}_vel_sd_midi"] = _per_bar(rb, rn["vel_resid_scaled"], nb, "rms")
            # "count" counts NaNs too, so count finite values as a sum of flags
            bars[f"{pre}_n_iois"] = _per_bar(
                rb, np.isfinite(rn["ioi_rel_scaled"]).astype(float), nb, "sum").astype(int)
            n_ioi = _per_bar(rb, np.isfinite(rn["ioi_sec"]).astype(float), nb, "sum")
            with np.errstate(divide="ignore", invalid="ignore"):
                bars[f"{pre}_note_rate_nps"] = np.where(
                    n_ioi > 0, n_ioi / _per_bar(rb, rn["ioi_sec"], nb, "sum"), np.nan)
        else:
            bars[f"{pre}_ioi_cv"] = bars[f"{pre}_vel_sd_midi"] = np.nan
            bars[f"{pre}_n_iois"] = 0
            bars[f"{pre}_note_rate_nps"] = np.nan
    si = sync["measure_idx"].to_numpy(int) if len(sync) else np.zeros(0, int)
    bars["hand_async_n"] = _per_bar(si, sync.get("async_ms", pd.Series(dtype=float)), nb,
                                    "count").astype(int)  # fmt: skip
    bars["hand_async_mean_ms"] = _per_bar(si, sync.get("async_ms", pd.Series(dtype=float)), nb,
                                          "mean")  # fmt: skip
    bars["hand_async_dv_mean_midi"] = _per_bar(si, sync.get("dv_midi", pd.Series(dtype=float)),
                                               nb, "mean")  # fmt: skip
    mean_resid = float(np.median(sync["resid_ms"])) if len(sync) else 0.0
    bars["hand_async_resid_rms_ms"] = _per_bar(
        si, sync.get("resid_ms", pd.Series(dtype=float)) - mean_resid, nb, "rms")
    gi = stab["measure_idx"].to_numpy(int)
    bars["tempo_instability_log_rms"] = _per_bar(gi, stab["instability_log"], nb, "rms")
    hi = harm["measure_idx"].to_numpy(int) if len(harm) else np.zeros(0, int)
    bars["n_harmony_changes"] = _per_bar(hi, harm.get("beat", pd.Series(dtype=float)), nb,
                                         "count").astype(int)  # fmt: skip
    bars["pedal_blur_fraction"] = _per_bar(hi, harm.get("blurred", pd.Series(dtype=float)), nb,
                                           "mean")  # fmt: skip
    bars["pedal_blur_beats"] = _per_bar(hi, harm.get("blur_beats", pd.Series(dtype=float)), nb,
                                        "mean")  # fmt: skip

    summary: dict[str, Any] = {**s_t}
    score_q = np.unique(ap.score.notes["onset_quarter"])
    for pre, rs, rn in (("even", runs, run_notes), ("even_strict", sruns, srun_notes)):
        ru = rs[rs["n_iois"] >= cfg.min_run_iois] if len(rs) else rs
        runs_q = rn["quarter"].unique() if len(rn) else np.zeros(0)
        if len(rn):
            summary[f"{pre}_ioi_cv"] = _rms(rn["ioi_rel_scaled"].to_numpy(float))
            summary[f"{pre}_vel_sd_midi"] = _rms(rn["vel_resid_scaled"].to_numpy(float))
            io = rn["ioi_sec"].to_numpy(float)
            io = io[np.isfinite(io)]
            summary[f"{pre}_note_rate_nps"] = len(io) / float(io.sum()) if io.sum() > 0 \
                else np.nan
        else:
            summary[f"{pre}_ioi_cv"] = summary[f"{pre}_vel_sd_midi"] = np.nan
            summary[f"{pre}_note_rate_nps"] = np.nan
        summary.update({
            f"{pre}_n_runs": len(rs),
            f"{pre}_n_runs_used": len(ru),
            f"{pre}_n_iois": int(rs["n_iois"].sum()) if len(rs) else 0,
            f"{pre}_share_of_onsets": float(np.isin(score_q, runs_q).mean()) if len(rs)
            else 0.0,
        })  # fmt: skip
    summary.update(s_h)
    summary.update(s_s)
    summary.update(s_p)
    summary.update(counts)
    return ControlResult(bars, summary, timing, runs, run_notes, sync, stab, sections, harm,
                         asdict(cfg), sruns, srun_notes)
