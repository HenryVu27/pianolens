"""Tempo model (F-03): beat-level tempo curve, smooth phrase-level component and residual jitter.

Definitions
-----------
Everything is computed from an aligned performance (use the score returned by
``pianolens.align.align_performance``: its note ids follow the repeat path the performer took).

* **Score position**: a distinct score onset, in score beats (``Score.notes["onset_beat"]``;
  partitura counts beats in time-signature denominator units, so 6/8 has 6 beats per bar).
  Only ``match`` pairs count. ``interpolated`` pairs (not played), grace notes and unmatched
  notes are skipped and counted.
* **Performed time of a position** ``t_j``: the median onset (s) of the performed notes matched
  to the position's score notes (chords collapse to one time; melody lead is left to F-04).
* **Time map**: performed time as a function of score beat, ``t(b)``. It is split into
  **smooth** ``T(b)`` plus **residual** ``r_j = t_j - T(b_j)``:
  ``T`` is a penalized B-spline (P-spline, Eilers and Marx 1996) with a third-order difference
  penalty, fitted by robust (Tukey bisquare) iteratively reweighted least squares. The penalty
  null space is quadratic time maps, i.e. constant tempo and constant (linear) ritardando /
  accelerando, which are never penalized.
* **Local beat period** ``p(b) = T'(b)`` (s/beat); **tempo** ``60 / p(b)`` (BPM in score beats);
  **log tempo ratio** ``tempo_log_ratio = log(p_global / p(b))`` (natural log; positive =
  faster than the performance's own global tempo). ``p_global`` is the geometric mean of
  ``p(b)`` over the integer-beat grid, so the log tempo ratio averages to zero.
* **Timing deviation** of a position or note: ``r`` in seconds (``dev_sec``) and normalized by
  the local beat period (``dev_beats = r / p(b)``, a fraction of a beat), since timing scales
  with tempo (Hu et al., TISMIR 2026).
* **Jitter** (tier B input): the spread of position residuals, ignoring flagged outliers.
  ``jitter_rms_ms`` is the RMS corrected for the fit's effective degrees of freedom,
  ``sqrt(sum r^2 / (n - edf))``; ``jitter_mad_ms`` is 1.4826 * MAD times the same
  ``sqrt(n / (n - edf))`` factor (also applied to per-bar RMS). The ``_beats`` variants
  use ``dev_beats``. The residual also holds intentional beat- and note-level timing (plan
  section 1.2: metric micro-timing, agogic accents), not only motor noise.

Smoothing parameter
-------------------
Default (``smoothing="cutoff"``): the curve is a low-pass filter whose half-gain period is
``cutoff_bars`` bars (default 1.5 bars, converted to beats with the score's time signature). For
a P-spline with knot spacing ``h`` beats, data weights that integrate to one per beat and an
order-3 difference penalty, the transfer function is about ``1 / (1 + (P / period)^6)`` for a
sinusoid of the given period, with ``lam = (P / 2 pi)^6 / h^5`` (gain 0.5 at period ``P``;
measured in the tests: about 0.45 at ``P``, under 0.01 at ``P/2``, over 0.98 at ``2P``). It is
set in score beats, not seconds, so the same musical span counts as "phrase level" at any tempo
(timing scales with tempo: Hu et al., TISMIR 2026). Why 1.5 bars: it is about the shortest
cutoff at which a strictly bar-periodic (metrical) timing pattern leaks less than 10% into the
smooth curve (gain 1/(1+1.5^6) = 0.08), while motion over two bars or more keeps at least 85%
(phrase arcs, ritardandi: Repp 1992, timing follows grouping structure and ritardandi are smooth
parabolas). Beat-level and within-bar timing go to the residual; the recurring within-bar part
is then reported separately (``metric_profile``).
``smoothing="gcv"`` picks ``lam`` by generalized cross-validation instead; it tends to
undersmooth when the residual is autocorrelated, as expressive timing is.

Breaks (the curve is not smoothed across them)
----------------------------------------------
* ``tempo_marking`` (kink: the tempo may jump, the time map stays continuous): score tempo words
  that set a new tempo (``a tempo``, ``tempo I``, ``più mosso``, ``allegro``, ...; not
  ``tenuto`` or ``stretto``) and metronome marks that change by at least 25%.
* ``tempo_step`` (kink): detected where the robust (Theil-Sen) beat period over the next two
  bars differs from the previous two bars by at least ``step_log_threshold`` (default log 1.3).
  Reported always; the curve is split there only with ``split_on_steps=True``.
* ``fermata`` / ``pause`` (gap: the time map may jump): a score fermata, or an inter-onset
  interval at least ``pause_ratio`` times the local expectation and ``pause_min_sec`` longer.
  The held time is reported in ``breaks["excess_sec"]`` and kept out of the tempo curve.
Gross alignment errors (positions inconsistent with both neighbours) are flagged and excluded.

Citations (``docs/research/2026-09-27-landscape.md``, section 1.2 / 1.3): tempo curves from
inter-onset intervals (Repp; Hu et al., TISMIR 2026, https://doi.org/10.5334/tismir.317);
Repp 1992 (JASA 92(5), https://doi.org/10.1121/1.404425) for grouping-level timing and
parabolic ritardandi; partitura performance codec (beat_period) for the raw beat period.
P-splines: Eilers and Marx 1996, Statistical Science 11(2) (landscape section 6.4).
"""

from __future__ import annotations

import math
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np
import pandas as pd
from scipy.interpolate import BSpline
from scipy.linalg import cho_factor, cho_solve

__all__ = [
    "TempoConfig",
    "TempoCurve",
    "TimeMap",
    "fit_time_map",
    "matched_onsets",
    "phrase_arcs",
    "score_tempo_breaks",
    "tempo_model",
    "tempo_from_onsets",
]

_MAD = 1.4826


# --------------------------------------------------------------------------- configuration


@dataclass(frozen=True)
class TempoConfig:
    """Parameters of the tempo model. Defaults are documented in the module docstring.

    Attributes:
        smoothing: ``"cutoff"`` (half-gain period ``cutoff_bars``) or ``"gcv"``.
        cutoff_bars: half-gain period of the smooth curve, in bars.
        cutoff_beats: same in beats; overrides ``cutoff_bars`` when given.
        knot_spacing_beats: B-spline knot spacing (the penalty, not this, sets smoothness).
        robust_iterations: bisquare IRLS iterations (0 = plain least squares).
        bisquare_c: bisquare tuning constant, in robust standard deviations.
        window_bars: window for pause and gross-outlier detection, in bars (min 2 beats).
        step_window_bars: window on each side for tempo-step detection, in bars. Two bars
            keep ordinary rubato (a dip that recovers within a bar) from counting as a step.
        step_log_threshold: |log beat-period ratio| that counts as a tempo step.
        detect_steps: report detected tempo steps in ``breaks``.
        split_on_steps: also split the curve at them. Off by default: on (n)ASAP Chopin a
            1-bar window flagged 13-22 "steps" per performance of Op. 10 No. 12, i.e. ordinary
            rubato, which belongs in the smooth curve. Score-marked changes always split.
        use_score_markings: split at score tempo markings and fermatas.
        pause_ratio / pause_min_sec: pause detection thresholds (both must hold).
        gross_sec / gross_beats: a position is a gross outlier if it misses both one-sided
            predictions by more than ``max(gross_sec, gross_beats * local beat period)``.
    """

    smoothing: Literal["cutoff", "gcv"] = "cutoff"
    cutoff_bars: float = 1.5
    cutoff_beats: float | None = None
    knot_spacing_beats: float = 1.0
    robust_iterations: int = 6
    bisquare_c: float = 4.685
    window_bars: float = 1.0
    step_window_bars: float = 2.0
    step_log_threshold: float = math.log(1.3)
    detect_steps: bool = True
    split_on_steps: bool = False
    use_score_markings: bool = True
    pause_ratio: float = 2.5
    pause_min_sec: float = 0.3
    gross_sec: float = 0.15
    gross_beats: float = 0.5


def cutoff_to_lambda(period_beats: float, knot_spacing: float) -> float:
    """P-spline penalty for a half-gain period of ``period_beats`` (see module docstring)."""
    return (period_beats / (2 * math.pi)) ** 6 / knot_spacing**5


def lambda_to_cutoff(lam: float, knot_spacing: float) -> float:
    """Inverse of :func:`cutoff_to_lambda`: half-gain period in beats."""
    return 2 * math.pi * (lam * knot_spacing**5) ** (1 / 6)


# --------------------------------------------------------------------------- P-spline core


@dataclass
class _Segment:
    lo: float
    hi: float
    spline: BSpline | None  # None: linear fit
    coef_lin: tuple[float, float] = (0.0, 1.0)  # (intercept, slope) when spline is None
    edf: float = 0.0

    def time(self, b: np.ndarray) -> np.ndarray:
        if self.spline is None:
            return self.coef_lin[0] + self.coef_lin[1] * b
        return self.spline(np.clip(b, self.lo, self.hi)) + self._extrap(b)

    def period(self, b: np.ndarray) -> np.ndarray:
        if self.spline is None:
            return np.full(np.shape(b), self.coef_lin[1], dtype=float)
        return self.spline.derivative()(np.clip(b, self.lo, self.hi))

    def _extrap(self, b: np.ndarray) -> np.ndarray:
        # linear continuation outside [lo, hi] with the end slope
        d = self.spline.derivative()
        below = np.minimum(b - self.lo, 0) * d(self.lo)
        above = np.maximum(b - self.hi, 0) * d(self.hi)
        return below + above


def _bspline_basis(x: np.ndarray, lo: float, hi: float, n_int: int) -> tuple[np.ndarray, Any]:
    k = 3
    inner = np.linspace(lo, hi, n_int + 1)
    step = inner[1] - inner[0]
    t = np.concatenate([lo - step * np.arange(k, 0, -1), inner, hi + step * np.arange(1, k + 1)])
    xb = np.clip(x, lo, hi)
    basis = BSpline.design_matrix(xb, t, k, extrapolate=True).toarray()
    return basis, t


def _penalized_fit(
    x: np.ndarray, y: np.ndarray, w: np.ndarray, knot_spacing: float, lam: float | None,
    period_beats: float,
) -> tuple[_Segment, np.ndarray]:
    """Fit one segment. Returns the segment and its hat-matrix diagonal."""
    lo, hi = float(x.min()), float(x.max())
    n = len(x)
    if n < 4 or hi - lo < 1e-9:
        return _linear_segment(x, y, w, lo, hi)
    n_int = max(1, math.ceil((hi - lo) / knot_spacing - 1e-9))
    h = (hi - lo) / n_int
    basis, knots = _bspline_basis(x, lo, hi, n_int)
    n_coef = basis.shape[1]
    diff = np.diff(np.eye(n_coef), n=3, axis=0)
    if lam is None:
        lam = cutoff_to_lambda(period_beats, h)
    bw = basis * w[:, None]
    gram = basis.T @ bw
    a = gram + lam * diff.T @ diff + 1e-10 * np.eye(n_coef)
    # hat diagonal: h_ii = w_i * b_i A^-1 b_i'
    try:
        cf = cho_factor(a)
        coef = cho_solve(cf, bw.T @ y)
        ainv_bt = cho_solve(cf, basis.T)
    except np.linalg.LinAlgError:
        # DF-01: with a large penalty and sparse data the fixed 1e-10 jitter can be too small
        # relative to the matrix scale. Retry with a scale-aware ridge, then pseudo-inverse.
        ridge = 1e-8 * max(float(np.trace(a)) / n_coef, 1.0)
        try:
            cf = cho_factor(a + ridge * np.eye(n_coef))
            coef = cho_solve(cf, bw.T @ y)
            ainv_bt = cho_solve(cf, basis.T)
        except np.linalg.LinAlgError:
            a_pinv = np.linalg.pinv(a, hermitian=True)
            coef = a_pinv @ (bw.T @ y)
            ainv_bt = a_pinv @ basis.T
    hat = w * np.einsum("ij,ji->i", basis, ainv_bt)
    seg = _Segment(lo, hi, BSpline(knots, coef, 3, extrapolate=True), edf=float(hat.sum()))
    return seg, hat


def _linear_segment(x, y, w, lo, hi) -> tuple[_Segment, np.ndarray]:
    if len(x) >= 2 and hi - lo > 1e-9:
        sw = np.sqrt(np.maximum(w, 1e-12))
        design = np.column_stack([np.ones_like(x), x])
        coef, *_ = np.linalg.lstsq(design * sw[:, None], y * sw, rcond=None)
        return _Segment(lo, hi, None, (float(coef[0]), float(coef[1])), edf=2.0), np.full(
            len(x), 2.0 / len(x)
        )
    slope = float("nan")
    return _Segment(lo, hi, None, (float(y.mean()), slope), edf=1.0), np.ones(len(x))


def _spacing_weights(b: np.ndarray, cap: float = 4.0) -> np.ndarray:
    """Beats each position represents (trapezoid rule), so weights integrate to 1 per beat."""
    if len(b) == 1:
        return np.ones(1)
    d = np.diff(b)
    w = np.empty(len(b))
    w[1:-1] = (d[:-1] + d[1:]) / 2
    w[0], w[-1] = d[0], d[-1]
    return np.clip(w, 1e-3, cap)


def _bisquare(u: np.ndarray) -> np.ndarray:
    return np.where(np.abs(u) < 1, (1 - u**2) ** 2, 0.0)


@dataclass
class TimeMap:
    """Piecewise smooth time map ``T(b)`` (seconds as a function of score beats).

    Segments are separated by breaks; ``T`` is independent in each segment.
    """

    segments: list[_Segment]
    starts: np.ndarray  # first beat of each segment (sorted)
    lam: float | None
    period_beats: float
    knot_spacing: float
    edf: float

    def segment_of(self, b: np.ndarray) -> np.ndarray:
        """Segment index for each beat: the last segment starting at or before ``b``."""
        idx = np.searchsorted(self.starts, np.asarray(b, dtype=float), side="right") - 1
        return np.clip(idx, 0, len(self.segments) - 1)

    def _eval(self, b: np.ndarray, what: str, seg: np.ndarray | None = None) -> np.ndarray:
        b = np.atleast_1d(np.asarray(b, dtype=float))
        seg = self.segment_of(b) if seg is None else seg
        out = np.empty(len(b))
        for s in np.unique(seg):
            m = seg == s
            out[m] = getattr(self.segments[s], what)(b[m])
        return out

    def time(self, b, seg=None) -> np.ndarray:
        """Smooth performed time ``T(b)`` in seconds."""
        return self._eval(b, "time", seg)

    def period(self, b, seg=None) -> np.ndarray:
        """Smooth local beat period ``T'(b)`` in seconds per score beat."""
        return self._eval(b, "period", seg)


def fit_time_map(
    beats: np.ndarray,
    times: np.ndarray,
    *,
    segment: np.ndarray | None = None,
    period_beats: float = 4.0,
    knot_spacing: float = 1.0,
    smoothing: Literal["cutoff", "gcv"] = "cutoff",
    robust_iterations: int = 6,
    bisquare_c: float = 4.685,
    exclude: np.ndarray | None = None,
) -> tuple[TimeMap, np.ndarray]:
    """Robust piecewise P-spline fit of performed time on score beats.

    Args:
        beats: score beats of the positions, strictly increasing.
        times: performed times (s).
        segment: segment id per position (non-decreasing); positions may appear in two segments
            only via the caller duplicating them. Default: one segment.
        period_beats: half-gain period of the smoother (``smoothing="cutoff"``).
        exclude: boolean mask of positions left out of the fit (gross outliers).

    Returns:
        ``(TimeMap, robust_weight)``; ``robust_weight`` is 0 for positions the bisquare step
        rejected (and for excluded ones), else in (0, 1].
    """
    b = np.asarray(beats, dtype=float)
    t = np.asarray(times, dtype=float)
    seg = np.zeros(len(b), dtype=int) if segment is None else np.asarray(segment)
    use = np.ones(len(b), bool) if exclude is None else ~np.asarray(exclude, bool)
    seg_ids = np.unique(seg)
    rw = use.astype(float)

    def fit_all(lam: float | None) -> tuple[list[_Segment], np.ndarray, float]:
        segs, resid, edf = [], np.full(len(b), np.nan), 0.0
        for s in seg_ids:
            m = (seg == s) & (rw > 0)
            if m.sum() == 0:
                m = seg == s
            xs, ys = b[m], t[m]
            w = _spacing_weights(xs) * np.where(rw[m] > 0, rw[m], 1.0)
            sg, _ = _penalized_fit(xs, ys, w, knot_spacing, lam, period_beats)
            segs.append(sg)
            edf += sg.edf
            mm = seg == s
            resid[mm] = t[mm] - sg.time(b[mm])
        _fill_nan_slopes(segs)
        for i, s in enumerate(seg_ids):
            mm = seg == s
            resid[mm] = t[mm] - segs[i].time(b[mm])
        return segs, resid, edf

    lam: float | None = None
    segs, resid, edf = fit_all(lam)
    for _ in range(robust_iterations):
        inl = use & np.isfinite(resid)
        # MAD about zero (the fit is the location), consistent with u = resid / scale below
        scale = _MAD * float(np.median(np.abs(resid[inl]))) if inl.any() else 0.0
        scale *= _dof_factor(int(inl.sum()), edf)
        if scale <= 1e-6:
            break
        new = np.where(use, _bisquare(resid / (bisquare_c * scale)), 0.0)
        if np.allclose(new, rw, atol=1e-4):
            break
        rw = new
        segs, resid, edf = fit_all(lam)
    if smoothing == "gcv":
        lam = _gcv_lambda(b, t, seg, seg_ids, rw, knot_spacing, period_beats)
        segs, resid, edf = fit_all(lam)
    starts = np.array([sg.lo for sg in segs])
    return TimeMap(segs, starts, lam, period_beats if lam is None else
                   lambda_to_cutoff(lam, knot_spacing), knot_spacing, edf), rw


def _dof_factor(n: float, edf: float) -> float:
    """``sqrt(n / (n - edf))``: inflates residual spread for the variance the fit absorbed."""
    return math.sqrt(n / max(n - edf, 1.0)) if n > 0 else 1.0


def _fill_nan_slopes(segs: list[_Segment]) -> None:
    """Single-position segments get the slope of the nearest segment with one."""
    good = [s for s in segs if not (s.spline is None and not np.isfinite(s.coef_lin[1]))]
    for s in segs:
        if s.spline is None and not np.isfinite(s.coef_lin[1]):
            if not good:
                s.coef_lin = (s.coef_lin[0], 1.0)
                continue
            near = min(good, key=lambda g: min(abs(g.lo - s.lo), abs(g.hi - s.lo)))
            slope = float(near.period(np.array([s.lo]))[0])
            s.coef_lin = (s.coef_lin[0] - slope * s.lo, slope)


def _gcv_lambda(b, t, seg, seg_ids, rw, knot_spacing, period_beats) -> float:
    """Pick the penalty by generalized cross-validation over a log grid of cutoff periods."""
    periods = np.geomspace(0.5, 64, 36)
    best, best_score = None, np.inf
    for p in periods:
        lam = cutoff_to_lambda(p, knot_spacing)
        rss, n, edf = 0.0, 0, 0.0
        for s in seg_ids:
            m = (seg == s) & (rw > 0)
            if m.sum() == 0:
                continue
            xs, ys = b[m], t[m]
            w = _spacing_weights(xs) * rw[m]
            sg, hat = _penalized_fit(xs, ys, w, knot_spacing, lam, p)
            r = ys - sg.time(xs)
            wn = w / w.mean()
            rss += float(np.sum(wn * r**2))
            n += len(xs)
            edf += float(hat.sum())
        if n - edf <= 0:
            continue
        score = n * rss / (n - edf) ** 2
        if score < best_score:
            best, best_score = lam, score
    return best if best is not None else cutoff_to_lambda(period_beats, knot_spacing)


# --------------------------------------------------------------------------- detection


def _theil_sen(x: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    """Median-of-pairwise-slopes line; returns (intercept, slope)."""
    i, j = np.triu_indices(len(x), 1)
    dx = x[j] - x[i]
    ok = dx > 1e-9
    if not ok.any():
        return float(np.median(y)), float("nan")
    slope = float(np.median((y[j] - y[i])[ok] / dx[ok]))
    return float(np.median(y - slope * x)), slope


def _gross_outliers(b: np.ndarray, t: np.ndarray, win: float, cfg: TempoConfig) -> np.ndarray:
    """Positions that miss both one-sided (left / right) Theil-Sen predictions."""
    n = len(b)
    out = np.zeros(n, bool)
    if n < 6:
        return out
    for j in range(n):
        preds, slopes = [], []
        for side in (np.arange(j), np.arange(j + 1, n)):
            if len(side) == 0:
                continue
            near = side[np.abs(b[side] - b[j]) <= win]
            if len(near) < 3:
                near = side[np.argsort(np.abs(b[side] - b[j]))[:3]]
            if len(near) < 3:
                continue
            a, s = _theil_sen(b[near], t[near])
            if np.isfinite(s) and s > 0:
                preds.append(a + s * b[j])
                slopes.append(s)
        if not preds:
            continue
        tol = max(cfg.gross_sec, cfg.gross_beats * float(np.median(slopes)))
        if len(preds) == 1:
            tol *= 2
        out[j] = all(abs(t[j] - p) > tol for p in preds)
    return out


def _detect_pauses(b: np.ndarray, t: np.ndarray, win: float, cfg: TempoConfig) -> list[int]:
    """Indices j such that the IOI from position j to j+1 is a pause (a gap break after j)."""
    if len(b) < 3:
        return []
    ioi = np.diff(t)
    sioi = np.diff(b)
    per = ioi / sioi
    mid = (b[:-1] + b[1:]) / 2
    out = []
    for j in range(len(ioi)):
        near = np.abs(mid - mid[j]) <= win
        near[j] = False
        if near.sum() < 2:
            continue
        expected = float(np.median(per[near])) * sioi[j]
        if expected <= 0:
            continue
        if ioi[j] >= cfg.pause_ratio * expected and ioi[j] - expected >= cfg.pause_min_sec:
            out.append(j)
    return out


def _detect_steps(
    b: np.ndarray, t: np.ndarray, win: float, cfg: TempoConfig
) -> list[tuple[int, float]]:
    """(position index, log period ratio right/left) of detected tempo steps within one segment."""
    n = len(b)
    stats = np.full(n, np.nan)
    for j in range(n):
        left = (b >= b[j] - win) & (b <= b[j])
        right = (b >= b[j]) & (b <= b[j] + win)
        if left.sum() < 3 or right.sum() < 3:
            continue
        if b[j] - b[left].min() < win / 2 or b[right].max() - b[j] < win / 2:
            continue
        _, sl = _theil_sen(b[left], t[left])
        _, sr = _theil_sen(b[right], t[right])
        if sl > 0 and sr > 0:
            stats[j] = math.log(sr / sl)
    cand = np.where(np.abs(np.nan_to_num(stats)) >= cfg.step_log_threshold)[0]
    accepted: list[tuple[int, float]] = []
    for j in sorted(cand, key=lambda k: -abs(stats[k])):
        if all(abs(b[j] - b[k]) >= win for k, _ in accepted):
            accepted.append((int(j), float(stats[j])))
    return sorted(_refine_step(b, t, j, win, stats) for j, _ in accepted)


def _refine_step(
    b: np.ndarray, t: np.ndarray, j: int, win: float, stats: np.ndarray
) -> tuple[int, float]:
    """Move a step to the kink position that best fits a continuous two-line (hinge) model on
    the surrounding window (Theil-Sen windows give a plateau of equal statistics, not a peak)."""
    w = np.abs(b - b[j]) <= win
    xs, ys = b[w], t[w]
    best, best_rss = j, np.inf
    for k in np.where(np.abs(b - b[j]) <= win / 2)[0]:
        design = np.column_stack([np.ones_like(xs), xs, np.maximum(xs - b[k], 0)])
        coef, *_ = np.linalg.lstsq(design, ys, rcond=None)
        rss = float(np.sum((ys - design @ coef) ** 2))
        if rss < best_rss - 1e-12:
            best, best_rss = int(k), rss
    lr = stats[best] if np.isfinite(stats[best]) else stats[j]
    return best, float(lr)


_HARD_TEMPO_WORDS = re.compile(
    r"\b(a\s*tempo|tempo\s*(i|1|primo)|più|piu|meno|doppio|l'?istesso|largo|larghetto|lento|"
    r"adagio|adagietto|andante|andantino|moderato|allegretto|allegro|vivace|vivo|presto|"
    r"prestissimo|grave|maestoso|mosso)\b",
    re.IGNORECASE,
)


def score_tempo_breaks(score: Any) -> pd.DataFrame:
    """Tempo breaks marked in the score (needs ``score.part``, as ``align_performance`` keeps).

    Returns a DataFrame with columns ``beat`` (score beats), ``kind`` (``tempo_marking`` or
    ``fermata``) and ``text``. Tempo words that set a new tempo, ``Reset`` directions (a tempo,
    tempo I) and metronome marks changing by >= 25% count; tenuto / stretto / rit. do not
    (gradual changes are what the smooth curve is for).
    """
    rows: list[tuple[float, str, str]] = []
    part = getattr(score, "part", None)
    if part is None:
        return pd.DataFrame(rows, columns=["beat", "kind", "text"])
    import partitura as pt

    bm = part.beat_map
    for d in part.iter_all(pt.score.TempoDirection, include_subclasses=True):
        text = str(getattr(d, "raw_text", None) or getattr(d, "text", "") or "")
        reset = isinstance(d, pt.score.ResetTempoDirection)
        const = isinstance(d, pt.score.ConstantTempoDirection)
        if reset or (const and _HARD_TEMPO_WORDS.search(text)):
            rows.append((float(bm(d.start.t)), "tempo_marking", text))
    prev = None
    for tm in sorted(part.iter_all(pt.score.Tempo), key=lambda x: x.start.t):
        bpm = getattr(tm, "bpm", None)
        if bpm and prev and max(bpm / prev, prev / bpm) >= 1.25:
            rows.append((float(bm(tm.start.t)), "tempo_marking", f"metronome {bpm:g}"))
        prev = bpm or prev
    for f in part.iter_all(pt.score.Fermata):
        rows.append((float(bm(f.start.t)), "fermata", "fermata"))
    df = pd.DataFrame(rows, columns=["beat", "kind", "text"])
    return df.drop_duplicates(["beat", "kind"]).sort_values("beat").reset_index(drop=True)


# --------------------------------------------------------------------------- result


@dataclass
class TempoCurve:
    """Output of :func:`tempo_model` / :func:`tempo_from_onsets`.

    Attributes:
        positions: one row per score position: ``beat``, ``time_sec`` (median performed onset),
            ``n_notes``, ``chord_spread_sec`` (max - min onset), ``measure_idx``,
            ``measure_number``, ``beat_in_bar``, ``segment``, ``time_smooth_sec``,
            ``beat_period_sec`` (smooth), ``beat_period_raw_sec`` (IOI to the next position /
            score IOI), ``tempo_bpm``, ``tempo_log_ratio``, ``dev_sec``, ``dev_beats``,
            ``robust_weight``, ``outlier`` (gross or bisquare-rejected).
        notes: one row per matched, non-grace note: ids, ``beat``, ``pitch``, ``vel_midi``,
            ``onset_sec``, ``chord_offset_sec`` (onset minus position time), ``dev_sec``,
            ``dev_beats`` (onset minus smooth time, in s and in beats), measure fields.
        beats: the smooth curve on the integer-beat grid: ``beat``, ``time_smooth_sec``,
            ``beat_period_sec``, ``tempo_bpm``, ``tempo_log_ratio``, measure fields.
        bars: per measure (unfolded order): ``measure_idx``, ``measure_number``,
            ``n_positions``, ``n_outliers``, ``tempo_bpm`` (geometric mean over its
            positions), ``tempo_log_ratio``, ``jitter_rms_ms`` / ``jitter_rms_beats`` (plain
            RMS of inlier residuals times the global ``sqrt(n / (n - edf))`` factor),
            ``max_abs_dev_ms``. Positions also carry ``dev_metric_beats`` and
            ``dev_nometric_beats`` / ``dev_nometric_sec`` (see ``metric_profile``).
        breaks: ``beat``, ``kind`` (tempo_marking / tempo_step / fermata / pause),
            ``type`` (kink / gap / none = reported, not split), ``text``, ``log_ratio``
            (steps), ``excess_sec`` (gaps).
        summary: global descriptors (see :func:`tempo_model`).
        time_map: the fitted :class:`TimeMap`.
        metric_profile: median ``dev_beats`` per ``beat_in_bar`` (only from :func:`tempo_model`,
            which knows the bars): the recurring within-bar timing pattern.
    """

    positions: pd.DataFrame
    notes: pd.DataFrame
    beats: pd.DataFrame
    bars: pd.DataFrame
    breaks: pd.DataFrame
    summary: dict[str, Any]
    time_map: TimeMap
    metric_profile: pd.DataFrame = field(default_factory=pd.DataFrame)
    meta: dict[str, Any] = field(default_factory=dict)

    def to_beat_curve(self, performance: Any | None = None) -> Any:
        """The smooth integer-beat curve as a ``pianolens.data.types.BeatCurve``."""
        from pianolens.data.types import BeatCurve

        g = self.beats
        return BeatCurve(
            performance_id=getattr(performance, "performance_id", ""),
            piece_id=getattr(performance, "piece_id", ""),
            performer_id=getattr(performance, "performer_id", ""),
            time_sec=g["time_smooth_sec"].to_numpy(),
            tempo_bpm=g["tempo_bpm"].to_numpy(),
            measure=g["measure_number"].to_numpy(),
            beat=g["beat_in_bar"].to_numpy(),
            dataset=getattr(performance, "dataset", ""),
            provenance=getattr(performance, "provenance", None),
            meta={"source": "pianolens.features.tempo", "smoothing": self.summary["smoothing"]},
        )


# --------------------------------------------------------------------------- input


def matched_onsets(ap: Any) -> tuple[pd.DataFrame, dict[str, int]]:
    """Matched (score note, performed note) pairs usable for timing, plus skip counts.

    Keeps ``match`` pairs only (not ``interpolated``), drops grace notes and pairs whose ids are
    missing from the note arrays. Returns a DataFrame with ``score_id``, ``performance_id``,
    ``beat``, ``quarter``, ``pitch``, ``vel_midi``, ``onset_sec`` and a dict of counts.
    """
    score, perf, al = ap.score, ap.performance, ap.alignment
    if score is None or al is None:
        raise ValueError("tempo_model needs an AlignedPerformance with a score and alignment")
    pairs = al.pairs
    labels = pairs["label"]
    m = pairs[labels == "match"]
    counts = {
        "n_score_notes": len(score.notes),
        "n_perf_notes": len(perf.notes),
        "n_match": len(m),
        "n_interpolated_skipped": int((labels == "interpolated").sum()),
        "n_insertion": int((labels == "insertion").sum()),
        "n_deletion": int((labels == "deletion").sum()),
    }
    sn = pd.DataFrame({
        "score_id": score.notes["id"].astype(str),
        "beat": score.notes["onset_beat"].astype(float),
        "quarter": score.notes["onset_quarter"].astype(float),
        "is_grace": score.notes["is_grace"].astype(bool)
        if "is_grace" in (score.notes.dtype.names or ()) else False,
    }).drop_duplicates("score_id")
    pn = pd.DataFrame({
        "performance_id": perf.notes["id"].astype(str),
        "onset_sec": perf.notes["onset_sec"].astype(float),
        "pitch": perf.notes["pitch"].astype(int),
        "vel_midi": perf.notes["velocity"].astype(int),
    }).drop_duplicates("performance_id")
    df = pd.DataFrame({"score_id": m["score_id"].astype(str),
                       "performance_id": m["performance_id"].astype(str)})
    n0 = len(df)
    df = df.merge(sn, on="score_id", how="inner").merge(pn, on="performance_id", how="inner")
    counts["n_missing_ids_skipped"] = n0 - len(df)
    counts["n_grace_skipped"] = int(df["is_grace"].sum())
    df = df[~df["is_grace"]].drop(columns="is_grace")
    return df.sort_values(["beat", "onset_sec"]).reset_index(drop=True), counts


def _measure_info(score: Any) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(start_quarter, start_beat, number) per measure in unfolded time order."""
    ms = score.measures
    if len(ms) == 0:
        return np.zeros(0), np.zeros(0), np.zeros(0, int)
    part = getattr(score, "part", None)
    if part is not None:
        pms = sorted(part.measures, key=lambda x: x.start.t)
        if len(pms) == len(ms):
            sb = np.array([float(part.beat_map(x.start.t)) for x in pms])
            return ms["start_quarter"], sb, ms["number"]
    q, bt = score.notes["onset_quarter"], score.notes["onset_beat"]
    order = np.argsort(q)
    q, bt = q[order], bt[order]
    sb = np.interp(ms["start_quarter"], q, bt)
    if len(q) >= 2 and q[-1] > q[0]:  # extend linearly beyond the first / last note
        lo, hi = ms["start_quarter"] < q[0], ms["start_quarter"] > q[-1]
        k0 = (bt[1] - bt[0]) / (q[1] - q[0]) if q[1] > q[0] else 1.0
        k1 = (bt[-1] - bt[-2]) / (q[-1] - q[-2]) if q[-1] > q[-2] else 1.0
        sb[lo] = bt[0] + (ms["start_quarter"][lo] - q[0]) * k0
        sb[hi] = bt[-1] + (ms["start_quarter"][hi] - q[-1]) * k1
    return ms["start_quarter"], sb, ms["number"]


def _beats_per_bar(score: Any) -> float:
    names = score.notes.dtype.names or ()
    if "ts_beats" in names and len(score.notes):
        return float(np.median(score.notes["ts_beats"]))
    return 4.0


# --------------------------------------------------------------------------- main entry


def tempo_model(ap: Any, config: TempoConfig | None = None) -> TempoCurve:
    """Beat-level tempo curve, smooth component and residual jitter of an aligned performance.

    Args:
        ap: ``pianolens.data.types.AlignedPerformance`` whose score is the one returned by
            ``pianolens.align.align_performance`` (with ``part`` kept, for markings and bars).
        config: :class:`TempoConfig`.

    Returns:
        :class:`TempoCurve`. ``summary`` holds: ``tempo_bpm_geomean`` (60 / geometric-mean
        smooth beat period, score beats), ``tempo_bpm_overall`` (score beats / performed time
        between first and last position, pauses included), ``tempo_log_sd`` and
        ``tempo_log_p90_p10`` (spread of the smooth log tempo ratio on the beat grid),
        ``jitter_rms_ms``, ``jitter_mad_ms``, ``jitter_rms_beats``, ``jitter_mad_beats``,
        ``jitter_nometric_rms_ms`` / ``_beats`` (residual minus the performance's mean
        within-bar pattern, see ``metric_profile``), counts (positions, notes, skipped,
        outliers, breaks) and the smoothing used.
    """
    cfg = config or TempoConfig()
    notes, counts = matched_onsets(ap)
    score = ap.score
    bpb = _beats_per_bar(score)
    marks = score_tempo_breaks(score) if cfg.use_score_markings else None
    res = tempo_from_onsets(
        notes["beat"].to_numpy(), notes["onset_sec"].to_numpy(), config=cfg,
        beats_per_bar=bpb, score_breaks=marks,
    )
    # measures
    mq, mb, mnum = _measure_info(score)
    _attach_measures(res.positions, mb, mnum)
    _attach_measures(res.beats, mb, mnum)
    notes = _note_table(notes, res)
    _attach_measures(notes, mb, mnum)
    res.notes = notes
    res.bars = _bar_table(res.positions, res.summary["dof_factor"])
    res.metric_profile = _metric_profile(res.positions)
    res.summary.update(_metric_jitter(res.positions, res.summary["dof_factor"]))
    res.summary.update(counts)
    res.summary["n_notes_used"] = len(notes)
    return res


def _metric_profile(pos: pd.DataFrame, min_count: int = 3) -> pd.DataFrame:
    """Median normalized residual per metrical position (``beat_in_bar``), gross outliers out.

    This is the performance's own recurring within-bar timing pattern (the "beat / meter" layer
    of plan section 1.2). Adds ``dev_metric_beats`` (the profile value, 0 where fewer than
    ``min_count`` occurrences) and ``dev_nometric_beats`` / ``dev_nometric_sec`` (residual minus
    the profile) to ``pos`` in place and returns the profile.
    """
    key = (pos["beat_in_bar"].round(3)).fillna(-1.0)
    inl = ~pos["gross_outlier"]
    prof = (
        pos[inl].groupby(key[inl])["dev_beats"].agg(dev_metric_beats="median", n="size")
        .reset_index()
    )
    prof.columns = ["beat_in_bar", "dev_metric_beats", "n"]
    prof.loc[prof["n"] < min_count, "dev_metric_beats"] = 0.0
    lut = dict(zip(prof["beat_in_bar"], prof["dev_metric_beats"], strict=True))
    pos["dev_metric_beats"] = key.map(lut).fillna(0.0).to_numpy()
    pos["dev_nometric_beats"] = pos["dev_beats"] - pos["dev_metric_beats"]
    pos["dev_nometric_sec"] = pos["dev_nometric_beats"] * pos["beat_period_sec"]
    return prof


def _metric_jitter(pos: pd.DataFrame, dof_k: float) -> dict[str, float]:
    inl = pos[~pos["outlier"]]
    if len(inl) == 0:
        return {"jitter_nometric_rms_ms": np.nan, "jitter_nometric_rms_beats": np.nan}
    return {
        "jitter_nometric_rms_ms": 1000 * dof_k * float(np.sqrt(np.mean(inl["dev_nometric_sec"]
                                                                        ** 2))),
        "jitter_nometric_rms_beats": dof_k * float(np.sqrt(np.mean(inl["dev_nometric_beats"]
                                                                    ** 2))),
    }


def tempo_from_onsets(
    beats: np.ndarray,
    onsets_sec: np.ndarray,
    *,
    config: TempoConfig | None = None,
    beats_per_bar: float = 4.0,
    score_breaks: pd.DataFrame | None = None,
) -> TempoCurve:
    """Tempo model from note-level (score beat, performed onset) pairs, without partitura.

    Same output as :func:`tempo_model`, minus measure fields (``measure_idx`` is -1) and with
    ``notes`` holding the input pairs. ``score_breaks`` is a frame like
    :func:`score_tempo_breaks` returns.
    """
    cfg = config or TempoConfig()
    beats = np.asarray(beats, dtype=float)
    onsets = np.asarray(onsets_sec, dtype=float)
    ok = np.isfinite(beats) & np.isfinite(onsets)
    beats, onsets = beats[ok], onsets[ok]
    if len(beats) == 0:
        raise ValueError("no matched onsets")
    pos = (
        pd.DataFrame({"beat": beats, "t": onsets})
        .groupby("beat", sort=True)["t"]
        .agg(time_sec="median", n_notes="size", tmin="min", tmax="max")
        .reset_index()
    )
    pos["chord_spread_sec"] = pos["tmax"] - pos["tmin"]
    pos = pos.drop(columns=["tmin", "tmax"])
    b, t = pos["beat"].to_numpy(), pos["time_sec"].to_numpy()
    n = len(b)

    period = cfg.cutoff_beats if cfg.cutoff_beats else cfg.cutoff_bars * beats_per_bar
    win = max(2.0, cfg.window_bars * beats_per_bar)

    gross = _gross_outliers(b, t, win, cfg)
    keep = np.where(~gross)[0]
    bk, tk = b[keep], t[keep]

    break_rows: list[dict[str, Any]] = []
    gaps_after: set[int] = set()  # index into keep: gap after this position
    kinks_at: set[int] = set()  # index into keep: new segment starts here, shared position
    for j in _detect_pauses(bk, tk, win, cfg):
        gaps_after.add(j)
    if score_breaks is not None and len(score_breaks) and len(bk):
        for _, row in score_breaks.iterrows():
            if row["kind"] == "fermata":
                j = int(np.searchsorted(bk, row["beat"] + 1e-9, side="right") - 1)
                if 0 <= j < len(bk) - 1:
                    gaps_after.add(j)
            else:
                j = int(np.searchsorted(bk, row["beat"] - 1e-9, side="left"))
                if 0 < j < len(bk) - 1:
                    kinks_at.add(j)
                    break_rows.append({"beat": bk[j], "kind": "tempo_marking", "type": "kink",
                                       "text": row["text"], "log_ratio": np.nan,
                                       "excess_sec": np.nan})

    # Segment ids before step detection
    def segment_ids(gaps: set[int], kinks: set[int]) -> np.ndarray:
        seg = np.zeros(len(bk), dtype=int)
        s = 0
        for j in range(1, len(bk)):
            if (j - 1) in gaps or j in kinks:
                s += 1
            seg[j] = s
        return seg

    seg0 = segment_ids(gaps_after, kinks_at)
    if cfg.detect_steps:
        step_win = max(2.0, cfg.step_window_bars * beats_per_bar)
        for s in np.unique(seg0):
            idx = np.where(seg0 == s)[0]
            for j_local, lr in _detect_steps(bk[idx], tk[idx], step_win, cfg):
                j = int(idx[j_local])
                if j in kinks_at or j == idx[0]:
                    continue
                if cfg.split_on_steps:
                    kinks_at.add(j)
                break_rows.append({"beat": bk[j], "kind": "tempo_step",
                                   "type": "kink" if cfg.split_on_steps else "none",
                                   "text": "", "log_ratio": lr, "excess_sec": np.nan})
    seg = segment_ids(gaps_after, kinks_at)

    # Duplicate kink positions so both neighbouring segments include them
    fb, ft, fs = list(bk), list(tk), list(seg)
    for j in sorted(kinks_at):
        if (j - 1) in gaps_after:  # the time map may jump here; nothing to share
            continue
        fb.append(bk[j])
        ft.append(tk[j])
        fs.append(seg[j] - 1)
    order = np.lexsort((np.array(fb), np.array(fs)))
    fb_a, ft_a, fs_a = np.array(fb)[order], np.array(ft)[order], np.array(fs)[order]
    tmap, rw_fit = fit_time_map(
        fb_a, ft_a, segment=fs_a, period_beats=period, knot_spacing=cfg.knot_spacing_beats,
        smoothing=cfg.smoothing, robust_iterations=cfg.robust_iterations,
        bisquare_c=cfg.bisquare_c,
    )
    # map robust weights back: the right-segment copy of each position is the canonical one
    rw_keep = np.ones(len(bk))
    for k in range(len(fb_a)):
        j = int(np.searchsorted(bk, fb_a[k]))
        if fs_a[k] == seg[j]:
            rw_keep[j] = rw_fit[k]

    seg_all = np.empty(n, dtype=int)
    seg_all[keep] = seg
    if gross.any():
        seg_all[gross] = tmap.segment_of(b[gross])
    rw = np.zeros(n)
    rw[keep] = rw_keep

    # pauses: excess time over the smooth expectation
    for j in sorted(gaps_after):
        ioi = tk[j + 1] - tk[j]
        exp_ = float(tmap.period(np.array([bk[j]]), np.array([seg[j]]))[0]) * (bk[j + 1] - bk[j])
        kind = "pause"
        if score_breaks is not None and len(score_breaks):
            fer = score_breaks[score_breaks["kind"] == "fermata"]["beat"].to_numpy()
            if np.any((fer >= bk[j] - 1e-9) & (fer < bk[j + 1] - 1e-9)):
                kind = "fermata"
        break_rows.append({"beat": bk[j], "kind": kind, "type": "gap", "text": "",
                           "log_ratio": np.nan, "excess_sec": ioi - exp_})

    ts = tmap.time(b, seg_all)
    ps = tmap.period(b, seg_all)
    pos["measure_idx"] = -1
    pos["measure_number"] = -1
    pos["beat_in_bar"] = np.nan
    pos["segment"] = seg_all
    pos["time_smooth_sec"] = ts
    pos["beat_period_sec"] = ps
    raw = np.full(n, np.nan)
    if n > 1:
        raw[:-1] = np.diff(t) / np.diff(b)
    pos["beat_period_raw_sec"] = raw
    pos["dev_sec"] = t - ts
    pos["dev_beats"] = (t - ts) / ps
    pos["robust_weight"] = rw
    pos["gross_outlier"] = gross
    pos["outlier"] = gross | (rw == 0)

    # integer-beat grid
    grid = np.arange(math.ceil(b[0] - 1e-9), math.floor(b[-1] + 1e-9) + 1, dtype=float)
    if len(grid) < 2:
        grid = b.copy()
    gseg = tmap.segment_of(grid)
    gp = tmap.period(grid, gseg)
    valid = gp > 0
    p_global = float(np.exp(np.mean(np.log(gp[valid])))) if valid.any() else float("nan")
    beats_df = pd.DataFrame({
        "beat": grid, "measure_idx": -1, "measure_number": -1, "beat_in_bar": np.nan,
        "segment": gseg, "time_smooth_sec": tmap.time(grid, gseg), "beat_period_sec": gp,
    })
    with np.errstate(divide="ignore", invalid="ignore"):
        beats_df["tempo_bpm"] = 60.0 / gp
        beats_df["tempo_log_ratio"] = np.log(p_global / gp)
        pos["tempo_bpm"] = 60.0 / ps
        pos["tempo_log_ratio"] = np.log(p_global / ps)

    inl = ~pos["outlier"].to_numpy()
    r = pos["dev_sec"].to_numpy()[inl]
    rb = pos["dev_beats"].to_numpy()[inl]
    n_in = int(inl.sum())
    dof = max(n_in - tmap.edf, 1.0)
    dof_k = _dof_factor(n_in, tmap.edf)
    tl = beats_df["tempo_log_ratio"].to_numpy()
    tl = tl[np.isfinite(tl)]
    summary: dict[str, Any] = {
        "tempo_bpm_geomean": 60.0 / p_global,
        "tempo_bpm_overall": 60.0 * (b[-1] - b[0]) / (t[-1] - t[0]) if t[-1] > t[0] else np.nan,
        "tempo_log_sd": float(np.std(tl)) if len(tl) else np.nan,
        "tempo_log_p90_p10": float(np.subtract(*np.percentile(tl, [90, 10]))) if len(tl)
        else np.nan,
        "jitter_rms_ms": 1000 * float(np.sqrt(np.sum(r**2) / dof)) if n_in else np.nan,
        "jitter_mad_ms": 1000 * dof_k * _MAD * float(np.median(np.abs(r - np.median(r))))
        if n_in
        else np.nan,
        "jitter_rms_beats": float(np.sqrt(np.sum(rb**2) / dof)) if n_in else np.nan,
        "jitter_mad_beats": dof_k * _MAD * float(np.median(np.abs(rb - np.median(rb))))
        if n_in else np.nan,
        "n_positions": n,
        "n_outliers": int(pos["outlier"].sum()),
        "n_gross_outliers": int(gross.sum()),
        "n_segments": int(len(tmap.segments)),
        "n_tempo_steps": sum(1 for x in break_rows if x["kind"] == "tempo_step"),
        "n_pauses": sum(1 for x in break_rows if x["type"] == "gap"),
        "edf": float(tmap.edf),
        "dof_factor": dof_k,
        "smoothing": cfg.smoothing,
        "cutoff_beats": float(tmap.period_beats),
        "beats_per_bar": float(beats_per_bar),
    }
    breaks = pd.DataFrame(
        break_rows, columns=["beat", "kind", "type", "text", "log_ratio", "excess_sec"]
    ).sort_values("beat").reset_index(drop=True)
    notes = pd.DataFrame({"beat": beats, "onset_sec": onsets})
    res = TempoCurve(pos, notes, beats_df, pd.DataFrame(), breaks, summary, tmap)
    res.notes = _note_table(notes, res)
    res.bars = _bar_table(res.positions, dof_k)
    return res


def _note_table(notes: pd.DataFrame, res: TempoCurve) -> pd.DataFrame:
    pos = res.positions.set_index("beat")
    out = notes.copy()
    b = out["beat"].to_numpy()
    seg = pos.loc[b, "segment"].to_numpy()
    ts = res.time_map.time(b, seg)
    ps = res.time_map.period(b, seg)
    out["position_time_sec"] = pos.loc[b, "time_sec"].to_numpy()
    out["chord_offset_sec"] = out["onset_sec"] - out["position_time_sec"]
    out["dev_sec"] = out["onset_sec"] - ts
    out["dev_beats"] = out["dev_sec"] / ps
    out["position_outlier"] = pos.loc[b, "outlier"].to_numpy()
    return out


def _attach_measures(df: pd.DataFrame, start_beats: np.ndarray, numbers: np.ndarray) -> None:
    if len(start_beats) == 0 or len(df) == 0:
        return
    b = df["beat"].to_numpy()
    idx = np.clip(np.searchsorted(start_beats, b + 1e-9, side="right") - 1, 0, None)
    df["measure_idx"] = idx
    df["measure_number"] = np.asarray(numbers)[idx]
    df["beat_in_bar"] = b - start_beats[idx]


def _bar_table(pos: pd.DataFrame, dof_k: float = 1.0) -> pd.DataFrame:
    rows = []
    for mi, g in pos.groupby("measure_idx", sort=True):
        inl = g[~g["outlier"]]
        p = g["beat_period_sec"].to_numpy()
        p = p[p > 0]
        rows.append({
            "measure_idx": int(mi),
            "measure_number": int(g["measure_number"].iloc[0]),
            "start_beat": float(g["beat"].min()),
            "n_positions": len(g),
            "n_outliers": int(g["outlier"].sum()),
            "tempo_bpm": 60.0 / float(np.exp(np.mean(np.log(p)))) if len(p) else np.nan,
            "tempo_log_ratio": float(g["tempo_log_ratio"].mean()),
            "jitter_rms_ms": 1000 * dof_k * float(np.sqrt(np.mean(inl["dev_sec"] ** 2)))
            if len(inl) else np.nan,
            "jitter_rms_beats": dof_k * float(np.sqrt(np.mean(inl["dev_beats"] ** 2)))
            if len(inl) else np.nan,
            "max_abs_dev_ms": 1000 * float(inl["dev_sec"].abs().max()) if len(inl) else np.nan,
        })
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- phrase arcs


def phrase_arcs(curve: TempoCurve, boundaries_beats: Sequence[float]) -> pd.DataFrame:
    """Hook for a phrase-arc model: a parabola in phrase position fitted to the smooth log tempo.

    ``boundaries_beats`` are phrase starts in score beats (supplied externally, e.g. from an
    annotation or a segmentation model); the last phrase ends at the last grid beat. For each
    phrase, ``tempo_log_ratio ~ c0 + c1*u + c2*u^2`` with ``u`` in [-1, 1] across the phrase
    (Repp 1992: within-gesture ritardandi are parabolic). Returns ``start_beat``, ``end_beat``,
    ``n_beats``, ``c0``, ``c1``, ``c2``, ``r2`` (share of the phrase's smooth log-tempo variance
    the parabola explains).
    """
    g = curve.beats
    bnd = sorted(float(x) for x in boundaries_beats)
    ends = bnd[1:] + [float(g["beat"].max()) + 1]
    rows = []
    for s, e in zip(bnd, ends, strict=True):
        m = (g["beat"] >= s) & (g["beat"] < e)
        y = g.loc[m, "tempo_log_ratio"].to_numpy()
        x = g.loc[m, "beat"].to_numpy()
        if len(y) < 3:
            rows.append({"start_beat": s, "end_beat": e, "n_beats": len(y), "c0": np.nan,
                         "c1": np.nan, "c2": np.nan, "r2": np.nan})
            continue
        u = 2 * (x - x.min()) / max(x.max() - x.min(), 1e-9) - 1
        c2, c1, c0 = np.polyfit(u, y, 2)
        fit = c0 + c1 * u + c2 * u**2
        ss = float(np.sum((y - y.mean()) ** 2))
        r2 = 1 - float(np.sum((y - fit) ** 2)) / ss if ss > 0 else np.nan
        rows.append({"start_beat": s, "end_beat": e, "n_beats": len(y), "c0": c0, "c1": c1,
                     "c2": c2, "r2": r2})
    return pd.DataFrame(rows)
