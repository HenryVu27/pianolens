"""Tier D interpretation: one performance relative to expert performances of the same piece (F-06).

The design follows the R-02 result and its audit (``DECISIONS.md``, 2026-09-27):

* Expert expression over a whole piece is *not* low-rank (about 19 components for 80%), but a
  small **shared** part is: about 3-5 components per piece clear a parallel-analysis null that
  keeps the per-beat variance profile, carrying about 35-46% of the between-performer variance.
  The rest is individual.
* So tier D never projects onto a single global whole-piece PCA basis. For each analysis window
  (16 bars by default, or the whole piece as an option) and each channel it fits the above-null
  shared components on the **references only**, then reports for the target: its coordinates in
  that shared space, the part of its deviation outside it (the "individual part", treated as
  legitimate freedom), and a **typicality** score, the likelihood of its shared coordinates
  under a shrinkage Gaussian fitted on the references (not a distance to the mean: Repp 1997
  found the average performance rated high in quality but low in individuality).
* Typicality is **two-sided in expressiveness**: the Gaussian also models the log magnitude of
  the curve (its RMS), so a deadpan or strongly flattened performance, which sits near the
  centre of the shared space, is *atypical*, not maximally typical (R-06: expression-model
  likelihoods rank deadpan renditions above every expert). Each window also reports the
  magnitude against the references' and flags ``too_flat`` / ``too_extreme``.
* Per-bar flags compare the target with cross-fitted (out-of-fold) reference deviations, so
  a flag means "outside the range that 95% of held-out experts stay within at this bar".

Channels (curves on a score-beat grid, one value per integer beat; beats are score beats, i.e.
time-signature denominator units, as in F-03):

* ``tempo``: smooth log tempo ratio (F-03 ``tempo_log_ratio``: log of the performance's
  geometric-mean beat period over the local smooth beat period; positive = faster than its own
  average). Computed with :func:`pianolens.features.tempo.tempo_from_onsets` and **no score
  markings**, the convention of the R-02 curve cache, so targets and cached references match.
  Re-centered per row inside each window (unit: natural log).
* ``velocity``: per-beat mean MIDI velocity of the matched notes, interpolated over beats
  without onsets inside the performance's span and Whittaker-smoothed with half gain at 1.5
  bars (R-02 "smooth velocity"). Re-centered per row inside each window (unit: MIDI velocity).
  Velocity on transcribed MIDI is low-confidence (``DECISIONS.md``, after D-10): when at least
  ``min_sensor_velocity_references`` Disklavier / sensor references exist, only those are used
  for velocity; otherwise all references are used and the output says
  ``velocity_confidence = "low"``. A transcribed target is always low-confidence.
* ``timing``: F-03 residual ``dev_beats`` per score position (onset minus smooth time map, in
  beats). Only used for the reference-agreement features, not decomposed: R-02 found it the
  highest-dimensional channel and closest to its null.

Main entry points:

* :func:`load_pianocore_references` (R-02 curve cache, or rebuilt from the PianoCoRe tier A
  cache), :func:`references_from_notes`, :func:`merge_references`: the reference set.
* :func:`target_from_aligned`, :func:`target_from_notes`, :func:`target_from_references`
  (leave-one-out for a performance that is itself a reference).
* :func:`map_score_beats`: piecewise beat offset from the target's performed score to the
  reference score (handles pickups and repeats that the two scores unfold differently).
* :func:`interpret`: everything above plus the expert band and the reference features.
* :func:`shared_core`, :func:`parallel_analysis`, :func:`envelope_surrogate`: the plain-numpy
  decomposition (usable on any curve matrix).

Citations (``docs/research/2026-09-27-landscape.md`` section 1.3 unless noted): Repp 1992 and
1998 (PCA of expert timing curves; Op. 10 No. 3 bars 1-5: "at least four independent timing
strategies" plus idiosyncratic variation), Repp 1997 (the average is rated high in quality and
low in individuality, so typicality is a likelihood, not closeness to the mean), Wöllner 2013
(individuality as deviation from many humans), Almansa and Delicado 2009 (functional data
analysis of tempo curves). Parallel analysis is Horn 1965 and the shrinkage covariance is
Ledoit and Wolf 2004 (landscape section 6.3). The null follows
the R-02 audit (phase randomization plus per-beat SD rescaling, "envelope null").
"""

from __future__ import annotations

import math
import warnings
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from pianolens.eval.dimensionality import phase_randomize, whittaker_smooth
from pianolens.features.tempo import TempoConfig, tempo_from_onsets

__all__ = [
    "BLOCKS",
    "SENSOR_PROVENANCE",
    "BeatMap",
    "Interpretation",
    "InterpretationConfig",
    "ReferenceSet",
    "SharedCore",
    "TargetCurves",
    "beat_grid_curves",
    "curve_agreement",
    "envelope_surrogate",
    "interpret",
    "load_pianocore_references",
    "map_score_beats",
    "merge_references",
    "parallel_analysis",
    "references_from_notes",
    "shared_core",
    "target_from_aligned",
    "target_from_notes",
    "target_from_references",
]

REPO = Path(__file__).resolve().parents[3]
#: R-02 per-piece curve cache (gitignored experiment artifact).
R02_CURVES = REPO / "experiments" / "2026-09-27-R-02-expression-dimensionality" / "artifacts" \
    / "curves"
#: Capture methods whose velocities are trusted (not audio transcription).
SENSOR_PROVENANCE = ("disklavier", "sensor")
#: Decomposed channels.
BLOCKS = ("tempo", "velocity")


@dataclass(frozen=True)
class InterpretationConfig:
    """Settings for :func:`interpret`.

    Attributes:
        tempo: F-03 tempo config for curves built here (default = the R-02 cache convention).
        velocity_cutoff_bars: Whittaker half-gain period of the smooth velocity, in bars.
        miss_beat: a window column is dropped when more than this share of references is
            unobserved there (R-02 QC).
        miss_ref: then a reference is dropped from the window when unobserved on more than this
            share of the kept columns.
        window_bars: bars per analysis window (non-overlapping, in the target's bars; a last
            window shorter than half of this is merged into the previous one). None = one
            window over the whole piece (the whole-piece option).
        min_window_beats: fewer kept beats -> no decomposition in that window.
        min_references: fewer references -> no decomposition (the band is still reported
            where at least this many references are observed).
        min_sensor_velocity_references: this many Disklavier / sensor references -> velocity
            uses only them.
        max_references: random subsample of transcribed references (seed ``seed``) for speed;
            sensor references are always kept. None = all.
        n_surrogates: envelope-null surrogates for parallel analysis.
        pa_quantile: eigenvalue quantile of the surrogates a component must exceed.
        pa_method: ``"horn"`` (default; the R-02 audit's count) or ``"sequential"``; see
            :func:`parallel_analysis`.
        pa_n, pa_draws: parallel analysis on ``pa_draws`` subsamples of ``pa_n`` references
            (median k); None = on all references. See :func:`shared_core`.
        max_components: cap on the number of shared components.
        n_folds: cross-fitting folds over the references for the calibration of typicality and
            of the per-bar thresholds.
        band_quantiles: expert band (low, mid, high) quantiles of the references.
        flag_quantile: per-bar flag threshold (quantile of out-of-fold reference deviations).
        min_refs_timing: references needed at a score position for the timing consensus.
        min_points: common points needed for a curve correlation.
        seed: RNG seed (surrogates, subsample, folds).
    """

    tempo: TempoConfig = field(default_factory=TempoConfig)
    velocity_cutoff_bars: float = 1.5
    miss_beat: float = 0.10
    miss_ref: float = 0.10
    window_bars: int | None = 16
    min_window_beats: int = 8
    min_references: int = 10
    min_sensor_velocity_references: int = 8
    max_references: int | None = 500
    n_surrogates: int = 40
    pa_quantile: float = 0.95
    pa_method: str = "horn"
    pa_n: int | None = 50
    pa_draws: int = 5
    max_components: int = 10
    n_folds: int = 10
    band_quantiles: tuple[float, float, float] = (0.1, 0.5, 0.9)
    flag_quantile: float = 0.95
    min_refs_timing: int = 3
    min_points: int = 5
    seed: int = 0


# =========================================================================== curves


def beat_grid_curves(
    beats: np.ndarray,
    onsets_sec: np.ndarray,
    velocities: np.ndarray,
    grid: np.ndarray,
    pos_grid: np.ndarray,
    beats_per_bar: float,
    tempo_config: TempoConfig | None = None,
) -> dict[str, Any]:
    """Curves of one performance on a score grid (promoted from R-02 ``curves.grid_curves``).

    Args:
        beats, onsets_sec, velocities: matched, non-grace notes (score beat, performed onset in
            seconds, MIDI velocity).
        grid: integer score-beat grid; pos_grid: distinct score onset positions (beats).
        beats_per_bar: for the 1.5-bar smoothing cutoff.

    Returns:
        ``T``: smooth log tempo ratio on ``grid`` (NaN outside the span and where no non-outlier
        position lies within one bar: "unobserved"); ``V``: mean MIDI velocity of the notes
        whose score onset is in [b, b + 1) (NaN where none); ``R``: ``dev_beats`` per score
        position (NaN if unmatched or outlier); ``tempo_bpm``: geometric-mean tempo (score
        beats per minute).
    """
    grid = np.asarray(grid, dtype=float)
    pos_grid = np.asarray(pos_grid, dtype=float)
    beats = np.asarray(beats, dtype=float)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        res = tempo_from_onsets(beats, np.asarray(onsets_sec, dtype=float),
                                config=tempo_config, beats_per_bar=beats_per_bar)
    g = res.beats
    t = np.full(len(grid), np.nan)
    gb = g["beat"].to_numpy(float)
    gi = np.searchsorted(grid, gb - 1e-9)
    ok = (gi < len(grid)) & np.isclose(grid[np.clip(gi, 0, len(grid) - 1)], gb)
    t[gi[ok]] = g["tempo_log_ratio"].to_numpy(float)[ok]
    pos = res.positions
    good = pos.loc[~pos["outlier"], "beat"].to_numpy(float)
    lo = np.searchsorted(good, grid - beats_per_bar - 1e-9, side="left")
    hi = np.searchsorted(good, grid + beats_per_bar + 1e-9, side="right")
    t[hi <= lo] = np.nan

    vb = np.floor(beats + 1e-6)
    vs = pd.Series(np.asarray(velocities, dtype=float)).groupby(vb).mean()
    v = np.full(len(grid), np.nan)
    vi = np.searchsorted(grid, vs.index.to_numpy() - 1e-9)
    okv = (vi < len(grid)) & np.isclose(grid[np.clip(vi, 0, len(grid) - 1)], vs.index.to_numpy())
    v[vi[okv]] = vs.to_numpy()[okv]

    r = np.full(len(pos_grid), np.nan)
    pb = pos["beat"].to_numpy(float)
    pj = np.searchsorted(pos_grid, pb - 1e-6)
    okp = (pj < len(pos_grid)) & np.isclose(pos_grid[np.clip(pj, 0, len(pos_grid) - 1)], pb,
                                             atol=1e-6)
    okp &= ~pos["outlier"].to_numpy()
    r[pj[okp]] = pos["dev_beats"].to_numpy(float)[okp]
    return {"T": t, "V": v, "R": r, "tempo_bpm": float(res.summary["tempo_bpm_geomean"])}


def _smooth_velocity_rows(v: np.ndarray, period: float) -> np.ndarray:
    """Interpolate each row over its NaNs inside its observed span, Whittaker-smooth it there;
    NaN outside the span. Rows with the same span are smoothed together."""
    v = np.atleast_2d(np.asarray(v, dtype=float))
    out = np.full_like(v, np.nan)
    fin = np.isfinite(v)
    spans: dict[tuple[int, int], list[int]] = {}
    for i in range(len(v)):
        idx = np.flatnonzero(fin[i])
        if len(idx) >= 2:
            spans.setdefault((int(idx[0]), int(idx[-1])), []).append(i)
    for (lo, hi), rows in spans.items():
        seg = v[rows, lo:hi + 1]
        x = np.arange(seg.shape[1])
        filled = np.vstack([np.interp(x, x[np.isfinite(r)], r[np.isfinite(r)]) for r in seg])
        out[rows, lo:hi + 1] = whittaker_smooth(filled, period)
    return out


def _fill_rows(x: np.ndarray) -> np.ndarray:
    """Linear interpolation over NaNs inside each row, nearest edge value outside (R-02)."""
    x = np.array(x, dtype=float, copy=True)
    idx = np.arange(x.shape[1])
    for i in range(len(x)):
        ok = np.isfinite(x[i])
        if ok.all() or not ok.any():
            continue
        x[i] = np.interp(idx, idx[ok], x[i, ok])
    return x


# =========================================================================== reference set


@dataclass(eq=False)
class ReferenceSet:
    """Expert curves of one piece on the reference score's beat grid.

    Attributes:
        piece_id: canonical piece id.
        grid: integer score beats (p,); pos_grid: score onset positions (q,).
        bar_starts: first beat of each bar (reference score), beats_per_bar: median.
        performance_ids, provenance, source_ids: (n,) per reference.
        tempo: (n, p) smooth log tempo ratio, NaN where unobserved.
        velocity: (n, p) raw per-beat mean velocity (MIDI), NaN where no onset.
        velocity_smooth: (n, p) smooth velocity (NaN outside each row's span).
        timing: (n, q) residual ``dev_beats`` per position.
        tempo_bpm: (n,) geometric-mean tempo.
        score_notes: optional reference score notes (``beat``, ``pitch``) for
            :func:`map_score_beats`.
        excluded: ids removed (leave-one-out or by request).
    """

    piece_id: str
    grid: np.ndarray
    pos_grid: np.ndarray
    bar_starts: np.ndarray
    beats_per_bar: float
    performance_ids: np.ndarray
    provenance: np.ndarray
    source_ids: np.ndarray
    tempo: np.ndarray
    velocity: np.ndarray
    velocity_smooth: np.ndarray
    timing: np.ndarray
    tempo_bpm: np.ndarray
    score_notes: pd.DataFrame | None = None
    excluded: list[str] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.performance_ids)

    def subset(self, rows: np.ndarray) -> ReferenceSet:
        rows = np.asarray(rows)
        if rows.dtype == bool:
            rows = np.flatnonzero(rows)
        dropped = [str(x) for x in np.delete(self.performance_ids, rows)]
        return replace(
            self, performance_ids=self.performance_ids[rows], provenance=self.provenance[rows],
            source_ids=self.source_ids[rows], tempo=self.tempo[rows],
            velocity=self.velocity[rows], velocity_smooth=self.velocity_smooth[rows],
            timing=self.timing[rows], tempo_bpm=self.tempo_bpm[rows],
            excluded=[*self.excluded, *dropped])  # fmt: skip

    def matching(self, ids: Iterable[str]) -> np.ndarray:
        """Boolean mask of references whose performance id or source id is in ``ids``."""
        s = {str(i) for i in ids if i}
        return np.array([str(a) in s or str(b) in s
                         for a, b in zip(self.performance_ids, self.source_ids, strict=True)],
                        dtype=bool)

    def exclude(self, ids: Iterable[str]) -> ReferenceSet:
        """Drop references whose performance id or source id is in ``ids`` (leave-one-out)."""
        return self.subset(~self.matching(ids))


def references_from_notes(
    piece_id: str,
    performances: Sequence[Mapping[str, Any]],
    grid: np.ndarray,
    pos_grid: np.ndarray,
    bar_starts: np.ndarray,
    beats_per_bar: float,
    config: InterpretationConfig | None = None,
    score_notes: pd.DataFrame | None = None,
) -> ReferenceSet:
    """Reference set from note tables already on the reference score's beats.

    ``performances``: dicts with ``performance_id``, ``provenance``, ``beats``, ``onsets_sec``,
    ``velocities`` (matched, non-grace notes) and optionally ``source_id``. Beats outside the
    grid are fine (e.g. a Vienna excerpt mapped onto a whole PianoCoRe piece): the curves are
    NaN there. Performances with fewer than 8 notes, or whose tempo fit fails, are skipped.
    """
    cfg = config or InterpretationConfig()
    grid, pos_grid = np.asarray(grid, float), np.asarray(pos_grid, float)
    rows: list[dict[str, Any]] = []
    for p in performances:
        b = np.asarray(p["beats"], float)
        if len(b) < 8:
            continue
        try:
            c = beat_grid_curves(b, p["onsets_sec"], p["velocities"], grid, pos_grid,
                                 beats_per_bar, cfg.tempo)
        except Exception:  # noqa: BLE001 - a failing reference is skipped, never fatal
            continue
        rows.append({**c, "pid": str(p["performance_id"]), "prov": str(p.get("provenance", "")),
                     "src": str(p.get("source_id", p["performance_id"]))})
    n, P, Q = len(rows), len(grid), len(pos_grid)
    T = np.array([r["T"] for r in rows]).reshape(n, P)
    V = np.array([r["V"] for r in rows]).reshape(n, P)
    R = np.array([r["R"] for r in rows]).reshape(n, Q)
    return ReferenceSet(
        piece_id=piece_id, grid=grid, pos_grid=pos_grid, bar_starts=np.asarray(bar_starts, float),
        beats_per_bar=float(beats_per_bar),
        performance_ids=np.array([r["pid"] for r in rows], dtype=object),
        provenance=np.array([r["prov"] for r in rows], dtype=object),
        source_ids=np.array([r["src"] for r in rows], dtype=object),
        tempo=T, velocity=V,
        velocity_smooth=_smooth_velocity_rows(V, cfg.velocity_cutoff_bars * beats_per_bar),
        timing=R, tempo_bpm=np.array([r["tempo_bpm"] for r in rows], float),
        score_notes=score_notes,
    )  # fmt: skip


def merge_references(a: ReferenceSet, b: ReferenceSet) -> ReferenceSet:
    """Concatenate two reference sets on the same grid (e.g. PianoCoRe + mapped Vienna)."""
    if not (np.array_equal(a.grid, b.grid) and np.array_equal(a.pos_grid, b.pos_grid)):
        raise ValueError("reference sets must share grid and pos_grid")
    cat = np.concatenate
    return replace(
        a, performance_ids=cat([a.performance_ids, b.performance_ids]),
        provenance=cat([a.provenance, b.provenance]), source_ids=cat([a.source_ids, b.source_ids]),
        tempo=np.vstack([a.tempo, b.tempo]), velocity=np.vstack([a.velocity, b.velocity]),
        velocity_smooth=np.vstack([a.velocity_smooth, b.velocity_smooth]),
        timing=np.vstack([a.timing, b.timing]), tempo_bpm=cat([a.tempo_bpm, b.tempo_bpm]),
        excluded=[*a.excluded, *b.excluded])  # fmt: skip


@lru_cache(maxsize=2)
def _performance_table(root: str | None) -> pd.DataFrame:
    from pianolens.data import pianocore_cache as pc

    P = pc.load_performances() if root is None else pc.load_performances(root)
    return P.set_index("performance_id")


def _majority_score_notes(piece_id: str, perf_id: str, root: str | None) -> pd.DataFrame:
    from pianolens.data import pianocore_cache as pc

    kw = {} if root is None else {"root": root}
    cols = ["performance_id", "s_onset_beat", "s_pitch", "s_is_grace"]
    df = pc.load_piece_notes(piece_id, columns=cols, **kw)
    df = df[(df["performance_id"] == perf_id) & (df["s_is_grace"] == 0)
            & df["s_onset_beat"].notna()]
    return pd.DataFrame({"beat": df["s_onset_beat"].astype(float).to_numpy(),
                         "pitch": df["s_pitch"].astype(int).to_numpy()})


def load_pianocore_references(
    piece_id: str,
    curves_dir: Path | str | None = None,
    exclude: Iterable[str] = (),
    config: InterpretationConfig | None = None,
    cache_root: Path | str | None = None,
    with_score_notes: bool = True,
) -> ReferenceSet:
    """PianoCoRe tier A references of one piece (majority score only, as in R-02).

    Reads the R-02 per-piece curve cache (``curves_dir``, default :data:`R02_CURVES`) when the
    piece is there; otherwise rebuilds the curves from the PianoCoRe tier A cache (``match``
    rows only, grace notes out; about 0.1 s per performance). ``exclude``: performance ids or
    source ids (e.g. ``ASAP_SunMeiting08``) to leave out.
    """
    from pianolens.data import pianocore_cache as pc

    cfg = config or InterpretationConfig()
    root = None if cache_root is None else str(cache_root)
    path = Path(curves_dir or R02_CURVES) / f"{pc.piece_slug(piece_id)}.npz"
    perf = _performance_table(root)
    if path.is_file():
        z = np.load(path, allow_pickle=False)
        ok = z["ok"]
        ids = z["perf_ids"][ok].astype(object)
        T = np.where(z["Tobs"][ok], z["T"][ok].astype(float), np.nan)
        V = z["V"][ok].astype(float)
        bpb = float(z["bpb"])
        refs = ReferenceSet(
            piece_id=piece_id, grid=z["grid"].astype(float), pos_grid=z["pos_grid"].astype(float),
            bar_starts=z["bar_starts"].astype(float), beats_per_bar=bpb, performance_ids=ids,
            provenance=perf.loc[ids, "provenance"].astype(str).to_numpy(dtype=object),
            source_ids=perf.loc[ids, "source_performance_id"].astype(str).to_numpy(dtype=object),
            tempo=T, velocity=V,
            velocity_smooth=_smooth_velocity_rows(V, cfg.velocity_cutoff_bars * bpb),
            timing=z["R"][ok].astype(float), tempo_bpm=z["s_tempo_bpm_geomean"][ok].astype(float),
        )  # fmt: skip
    else:
        refs = _build_pianocore_references(piece_id, perf, cfg, root)
    if with_score_notes and len(refs):
        refs.score_notes = _majority_score_notes(piece_id, str(refs.performance_ids[0]), root)
    ex = list(exclude)
    return refs.exclude(ex) if ex else refs


def _build_pianocore_references(piece_id: str, perf: pd.DataFrame, cfg: InterpretationConfig,
                                root: str | None) -> ReferenceSet:
    from pianolens.data import pianocore_cache as pc

    kw = {} if root is None else {"root": root}
    cols = ["performance_id", "label", "s_onset_beat", "s_is_grace", "s_ts_beats", "s_measure",
            "p_onset_sec", "p_velocity"]
    df = pc.load_piece_notes(piece_id, columns=cols, **kw)
    ids = df["performance_id"].astype(str).unique()
    P = perf.loc[perf.index.intersection(ids)]
    maj = P["score_id"].value_counts().index[0]
    keep = set(P.index[P["score_id"] == maj])
    df = df[df["performance_id"].astype(str).isin(keep) & (df["s_is_grace"] == 0)
            & df["s_onset_beat"].notna()]
    first = df[df["performance_id"] == df["performance_id"].iloc[0]]
    b = first["s_onset_beat"].to_numpy(float)
    grid = np.arange(math.ceil(b.min() - 1e-9), math.floor(b.max() + 1e-9) + 1, dtype=float)
    pos_grid = np.unique(b)
    bars = first.groupby("s_measure")["s_onset_beat"].min().sort_index().to_numpy(float)
    bpb = float(np.median(first["s_ts_beats"].to_numpy()))
    bpb = bpb if np.isfinite(bpb) and bpb > 0 else 4.0
    m = df[(df["label"] == "match") & df["p_onset_sec"].notna()]
    perfs = [{"performance_id": pid, "provenance": P.loc[pid, "provenance"],
              "source_id": P.loc[pid, "source_performance_id"],
              "beats": g["s_onset_beat"].to_numpy(float),
              "onsets_sec": g["p_onset_sec"].to_numpy(float),
              "velocities": g["p_velocity"].to_numpy(float)}
             for pid, g in m.groupby("performance_id", observed=True)]  # fmt: skip
    return references_from_notes(piece_id, perfs, grid, pos_grid, bars, bpb, cfg)


# =========================================================================== score mapping


@dataclass(eq=False)
class BeatMap:
    """Piecewise-constant beat offset from a source score to the reference score.

    Attributes:
        positions: sorted distinct source onset positions (beats).
        offsets: reference beat minus source beat at each position (NaN = unmapped).
        mapped_fraction: share of source notes found at (beat + offset, pitch) in the reference.
    """

    positions: np.ndarray
    offsets: np.ndarray
    mapped_fraction: float

    def __call__(self, beats: np.ndarray) -> np.ndarray:
        """Reference beats for source beats. A beat between two positions is mapped only if
        both have the same offset (no mapping across a segment boundary); NaN otherwise."""
        b = np.asarray(beats, dtype=float)
        p, o = self.positions, self.offsets
        j = np.searchsorted(p, b + 1e-6, side="right") - 1
        out = np.full(b.shape, np.nan)
        inside = j >= 0
        jj = np.clip(j, 0, len(p) - 1)
        exact = inside & np.isclose(p[jj], b, atol=1e-6)
        nxt = np.clip(jj + 1, 0, len(p) - 1)
        between = inside & ~exact & (jj + 1 < len(p)) & (o[jj] == o[nxt])
        ok = (exact | between) & np.isfinite(o[jj])
        out[ok] = b[ok] + o[jj][ok]
        return out

    @property
    def segments(self) -> pd.DataFrame:
        """Contiguous runs of one offset: ``src_lo``, ``src_hi``, ``offset``."""
        rows = []
        k = 0
        n = len(self.offsets)
        while k < n:
            j = k
            while j + 1 < n and (self.offsets[j + 1] == self.offsets[k]
                                 or (np.isnan(self.offsets[j + 1]) and np.isnan(self.offsets[k]))):
                j += 1
            if np.isfinite(self.offsets[k]):
                rows.append((self.positions[k], self.positions[j], self.offsets[k]))
            k = j + 1
        return pd.DataFrame(rows, columns=["src_lo", "src_hi", "offset"])


def _note_keys(beat: np.ndarray, pitch: np.ndarray) -> np.ndarray:
    return np.round(np.asarray(beat, float) * 1000).astype(np.int64) * 128 + np.asarray(pitch,
                                                                                         int)


def map_score_beats(
    source: pd.DataFrame,
    reference: pd.DataFrame,
    n_candidates: int = 8,
    switch_penalty: float = 3.0,
) -> BeatMap:
    """Map the target's performed-score beats onto the reference score's beats.

    Both frames have ``beat`` and ``pitch`` (non-grace score notes). Candidate offsets are the
    ``n_candidates`` most common (reference beat - source beat) differences over note pairs of
    the same pitch. A Viterbi pass over the source onset positions picks one offset (or
    "unmapped") per position: reward = share of the position's pitches found at the shifted
    beat minus 0.5, 0 for unmapped, ``switch_penalty`` per change of state. This follows
    repeats that one score unfolds and the other does not, and pickup offsets.
    """
    sb = source["beat"].to_numpy(float)
    sp = source["pitch"].to_numpy(int)
    rb = reference["beat"].to_numpy(float)
    rp = reference["pitch"].to_numpy(int)
    votes: dict[float, int] = {}
    for pitch in np.intersect1d(np.unique(sp), np.unique(rp)):
        d = np.round((rb[rp == pitch][None, :] - sb[sp == pitch][:, None]).ravel(), 3)
        u, c = np.unique(d, return_counts=True)
        for a, k in zip(u, c, strict=True):
            votes[float(a)] = votes.get(float(a), 0) + int(k)
    positions = np.unique(np.round(sb, 6))
    if not votes:
        return BeatMap(positions, np.full(len(positions), np.nan), 0.0)
    cands = np.array(sorted(votes, key=lambda a: -votes[a])[:n_candidates])
    rkeys = set(_note_keys(rb, rp).tolist())
    pos_idx = np.searchsorted(positions, np.round(sb, 6))
    # hit[c, note]
    hit = np.array([np.isin(_note_keys(sb + c, sp), list(rkeys)) for c in cands], dtype=float)
    npos = len(positions)
    cnt = np.bincount(pos_idx, minlength=npos).astype(float)
    frac = np.vstack([np.bincount(pos_idx, weights=h, minlength=npos) for h in hit]) / cnt
    reward = np.vstack([frac - 0.5, np.zeros((1, npos))])  # last state: unmapped
    S = len(reward)
    score = reward[:, 0].copy()
    back = np.zeros((S, npos), dtype=int)
    for j in range(1, npos):
        stay = score
        best = int(np.argmax(score))
        switch = score[best] - switch_penalty
        take_switch = switch > stay
        back[:, j] = np.where(take_switch, best, np.arange(S))
        score = np.where(take_switch, switch, stay) + reward[:, j]
    state = np.empty(npos, dtype=int)
    state[-1] = int(np.argmax(score))
    for j in range(npos - 1, 0, -1):
        state[j - 1] = back[state[j], j]
    offsets = np.where(state < len(cands), cands[np.minimum(state, len(cands) - 1)], np.nan)
    note_state = state[pos_idx]
    mapped = note_state < len(cands)
    found = np.zeros(len(sb), bool)
    found[mapped] = hit[note_state[mapped], np.flatnonzero(mapped)] > 0
    return BeatMap(positions, offsets.astype(float), float(found.mean()) if len(sb) else 0.0)


# =========================================================================== target


@dataclass(eq=False)
class TargetCurves:
    """Curves of the performance being interpreted, on its own (performed) score beats.

    Attributes:
        performance_id, provenance: ids; source_id: id used to find it among references.
        grid: integer beats of its own score (m,); bar_starts / bar_numbers: its bars.
        tempo, velocity, velocity_smooth: (m,) as in :class:`ReferenceSet`.
        pos_grid, timing: its score positions and ``dev_beats``.
        tempo_bpm: geometric-mean tempo.
        score_notes: its (performed) score notes, ``beat`` and ``pitch``, for mapping.
    """

    performance_id: str
    provenance: str
    grid: np.ndarray
    bar_starts: np.ndarray
    bar_numbers: np.ndarray
    tempo: np.ndarray
    velocity: np.ndarray
    velocity_smooth: np.ndarray
    pos_grid: np.ndarray
    timing: np.ndarray
    tempo_bpm: float
    score_notes: pd.DataFrame | None = None
    source_id: str = ""


def target_from_notes(
    performance_id: str,
    provenance: str,
    beats: np.ndarray,
    onsets_sec: np.ndarray,
    velocities: np.ndarray,
    bar_starts: np.ndarray,
    beats_per_bar: float,
    config: InterpretationConfig | None = None,
    bar_numbers: np.ndarray | None = None,
    score_notes: pd.DataFrame | None = None,
    source_id: str = "",
) -> TargetCurves:
    """Target curves from matched, non-grace (score beat, onset, velocity) notes."""
    cfg = config or InterpretationConfig()
    b = np.asarray(beats, float)
    grid = np.arange(math.ceil(b.min() - 1e-9), math.floor(b.max() + 1e-9) + 1, dtype=float)
    pos_grid = np.unique(np.round(b, 6))
    c = beat_grid_curves(b, onsets_sec, velocities, grid, pos_grid, beats_per_bar, cfg.tempo)
    bs = np.asarray(bar_starts, float)
    return TargetCurves(
        performance_id=str(performance_id), provenance=str(provenance), grid=grid,
        bar_starts=bs,
        bar_numbers=np.arange(1, len(bs) + 1) if bar_numbers is None else np.asarray(bar_numbers),
        tempo=c["T"], velocity=c["V"],
        velocity_smooth=_smooth_velocity_rows(c["V"], cfg.velocity_cutoff_bars * beats_per_bar)[0],
        pos_grid=pos_grid, timing=c["R"], tempo_bpm=c["tempo_bpm"], score_notes=score_notes,
        source_id=source_id,
    )  # fmt: skip


def target_from_aligned(ap: Any, config: InterpretationConfig | None = None,
                        source_id: str = "") -> TargetCurves:
    """Target curves from an ``AlignedPerformance`` (score = the performed score returned by
    ``pianolens.align.align_performance``). ``match`` pairs only, grace notes out.
    ``source_id`` is the id this performance has in the reference set, if any (for PianoCoRe:
    ``ASAP_<file stem>``); it is used for leave-one-out."""
    from pianolens.features.tempo import _beats_per_bar, _measure_info, matched_onsets

    notes, _ = matched_onsets(ap)
    score = ap.score
    _, mb, mnum = _measure_info(score)
    sn = score.notes
    names = sn.dtype.names or ()
    g = ~sn["is_grace"].astype(bool) if "is_grace" in names else np.ones(len(sn), bool)
    snotes = pd.DataFrame({"beat": sn["onset_beat"][g].astype(float),
                           "pitch": sn["pitch"][g].astype(int)})
    perf = ap.performance
    return target_from_notes(
        str(perf.performance_id), str(getattr(perf, "provenance", "") or ""),
        notes["beat"].to_numpy(float), notes["onset_sec"].to_numpy(float),
        notes["vel_midi"].to_numpy(float), mb, _beats_per_bar(score), config,
        bar_numbers=mnum, score_notes=snotes, source_id=source_id,
    )


def target_from_references(refs: ReferenceSet, performance_id: str
                           ) -> tuple[TargetCurves, ReferenceSet]:
    """A reference as the target, and the reference set without it (leave-one-out)."""
    mask = refs.matching([performance_id])
    if not mask.any():
        raise KeyError(f"{performance_id!r} is not in the reference set")
    i = int(np.flatnonzero(mask)[0])
    t = TargetCurves(
        performance_id=str(refs.performance_ids[i]), provenance=str(refs.provenance[i]),
        grid=refs.grid, bar_starts=refs.bar_starts,
        bar_numbers=np.arange(1, len(refs.bar_starts) + 1), tempo=refs.tempo[i].copy(),
        velocity=refs.velocity[i].copy(), velocity_smooth=refs.velocity_smooth[i].copy(),
        pos_grid=refs.pos_grid, timing=refs.timing[i].copy(), tempo_bpm=float(refs.tempo_bpm[i]),
        score_notes=refs.score_notes, source_id=str(refs.source_ids[i]),
    )  # fmt: skip
    return t, refs.subset(~mask)


# =========================================================================== decomposition


def envelope_surrogate(d: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Envelope null (R-02 audit): phase-randomize each row, then rescale every column to the
    real column SD. Keeps each row's spectrum (smoothness) *and* the per-beat variance profile;
    destroys the alignment of shapes across rows."""
    d = np.asarray(d, float)
    (s,) = phase_randomize(d, rng)
    s = s - s.mean(axis=0)
    sd_real = d.std(axis=0)
    sd_s = s.std(axis=0)
    scale = np.divide(sd_real, sd_s, out=np.zeros_like(sd_real), where=sd_s > 0)
    return s * scale


def parallel_analysis(
    x: np.ndarray, n_surrogates: int = 40, quantile: float = 0.95,
    rng: np.random.Generator | None = None, method: str = "horn",
    max_components: int | None = None,
) -> tuple[int, np.ndarray, np.ndarray]:
    """Number of leading principal components of ``x`` above an envelope null.

    Rows are observations; ``x`` is column-centered here. Two variants:

    * ``"horn"`` (default; Horn 1965; the R-02 audit's count): component j counts if its
      eigenvalue exceeds the ``quantile`` of the j-th eigenvalues of ``n_surrogates``
      :func:`envelope_surrogate` draws of ``x``, and all earlier ones did too. Strong
      components leak their power into the surrogates, so this undercounts when several
      strong components cover the window: on synthetic bump components (64 beats) it
      recovers k = 1-3 but returns 1-2 for k = 4-5 at n = 80. On PianoCoRe (8 pieces, n = 50,
      5 subsamples) it is stable: the k of one window varies by 1.3-2.5 across subsamples.
    * ``"sequential"`` (the "revised" parallel analysis idea of Green et al. 2012): the j-th
      component is tested against the top eigenvalue of envelope surrogates of the
      *residual* after removing the first j - 1 components, each surrogate projected off the
      removed row and column directions and rescaled to the residual's total variance. On
      synthetic data it recovers k = 1, 3, 5 on 95 of 96 runs (n = 80 and 200) and gives 0
      on 38 of 40 pure smooth-noise runs. **On real curves it is unstable** (k of one window
      varies by 6-7 across subsamples of 50, and runs to the cap at n = 500), probably
      because idiosyncratic local events are sparse and phase randomization spreads them
      out, so the real tail exceeds the null. Kept for research; do not use it for flags.

    Returns (k, eigenvalues, thresholds); thresholds are NaN beyond the last test."""
    rng = rng if rng is not None else np.random.default_rng(0)
    d = np.asarray(x, float)
    d = d - d.mean(axis=0)
    u, sv, vt = np.linalg.svd(d, full_matrices=False)
    ev = sv**2
    cap = len(ev) if max_components is None else min(len(ev), max_components)
    if method == "horn":
        null = np.array([np.linalg.svd(envelope_surrogate(d, rng), compute_uv=False) ** 2
                         for _ in range(n_surrogates)])
        thr = np.quantile(null, quantile, axis=0)
        above = ev > thr * (1 + 1e-9)
        k = int(np.argmin(above)) if not above.all() else len(ev)
        return min(k, cap), ev, thr
    if method != "sequential":
        raise ValueError(f"unknown method {method!r}")
    thr = np.full(len(ev), np.nan)
    k = 0
    for j in range(cap):
        if ev[j] <= 1e-12 * ev[0]:
            break
        resid = d - (u[:, :j] * sv[:j]) @ vt[:j]
        tot_j = float(ev[j:].sum())
        uj, vj = u[:, :j], vt[:j]
        top = []
        for _ in range(n_surrogates):
            sg = envelope_surrogate(resid, rng)
            # the residual is orthogonal to the removed directions in both row and column
            # space; project the surrogate the same way so its rank and spread match
            sg = sg - uj @ (uj.T @ sg)
            sg = sg - (sg @ vj.T) @ vj
            ss = float((sg**2).sum())
            sg = sg * np.sqrt(tot_j / ss) if ss > 0 else sg  # same total variance
            top.append(np.linalg.svd(sg, compute_uv=False)[0] ** 2)
        thr[j] = float(np.quantile(top, quantile))
        if ev[j] <= thr[j] * (1 + 1e-9):
            break
        k = j + 1
    return k, ev, thr


@dataclass(eq=False)
class SharedCore:
    """Shared expert components of one window and channel, fitted on references only.

    Typicality is two-sided in expressiveness. The Gaussian is fitted on
    ``u = [z_1..z_k, log(magnitude + eps)]``, where ``magnitude`` is the SD of the row's own
    curve. A deadpan row sits near the centre of the shared space (small ``z``)
    but has a tiny magnitude, so its log-magnitude coordinate lies far below the references'
    and its likelihood is low. Without that coordinate a likelihood rewards flatness (R-06:
    expression-model likelihoods rank deadpan renditions above every expert).

    Attributes:
        mean: (w,) reference mean curve; components: (k, w) orthonormal rows.
        k: number of above-null components; eigenvalues / thresholds: PA output (full fit).
        shared_share: share of the references' between-performer variance in the k components.
        cov: (k + 1, k + 1) Ledoit-Wolf covariance of the references' ``u``; cov_inv, logdet:
            its inverse and log-determinant; u_mean: mean of ``u``.
        eps: magnitude floor (1% of the references' median magnitude).
        n_refs: references used.
    """

    mean: np.ndarray
    components: np.ndarray
    k: int
    eigenvalues: np.ndarray
    thresholds: np.ndarray
    shared_share: float
    cov: np.ndarray
    cov_inv: np.ndarray
    logdet: float
    u_mean: np.ndarray
    eps: float
    n_refs: int

    def score(self, rows: np.ndarray) -> dict[str, np.ndarray]:
        """Decompose rows (curves on the same columns as the references).

        Returns ``d`` (deviation from the reference mean, after shifting the row so that its
        median deviation is zero: a robust level alignment), ``z`` (shared coordinates),
        ``shared`` (their reconstruction), ``individual`` (``d - shared``), ``magnitude``
        (SD of the row about its own mean), ``loglik`` / ``mahal2`` (Gaussian on ``u``: shared
        coordinates plus log magnitude) and ``mahal2_shared`` (shared coordinates only, using
        their block of the covariance)."""
        x = np.atleast_2d(np.asarray(rows, float))
        d = x - self.mean
        d = d - np.median(d, axis=1, keepdims=True)  # robust level alignment (_align_level)
        z = d @ self.components.T
        shared = z @ self.components
        mag = x.std(axis=1)
        u = np.column_stack([z, np.log(mag + self.eps)]) - self.u_mean
        m2 = np.einsum("ij,jk,ik->i", u, self.cov_inv, u)
        ll = -0.5 * (m2 + self.logdet + (self.k + 1) * np.log(2 * np.pi))
        if self.k:
            ci = np.linalg.inv(self.cov[: self.k, : self.k])
            uz = u[:, : self.k]
            m2s = np.einsum("ij,jk,ik->i", uz, ci, uz)
        else:
            m2s = np.full(len(x), np.nan)
        return {"d": d, "z": z, "shared": shared, "individual": d - shared, "magnitude": mag,
                "mahal2": m2, "loglik": ll, "mahal2_shared": m2s}


def _fit_core(x: np.ndarray, k: int, pa: tuple[np.ndarray, np.ndarray] | None = None
              ) -> SharedCore:
    from sklearn.covariance import LedoitWolf

    x = np.asarray(x, float)
    mu = x.mean(axis=0)
    d = x - mu
    _, s, vt = np.linalg.svd(d, full_matrices=False)
    k = int(min(k, len(s)))
    comps = vt[:k]
    tot = float((s**2).sum())
    share = float((s[:k] ** 2).sum() / tot) if tot > 0 else float("nan")
    mag = x.std(axis=1)
    eps = 0.01 * float(np.median(mag)) if np.median(mag) > 0 else 1e-12
    u = np.column_stack([d @ comps.T, np.log(mag + eps)])
    u_mean = u.mean(axis=0)
    # shrink the correlation matrix: the coordinates have very different scales (curve units
    # vs log magnitude), and Ledoit-Wolf's scaled-identity target would inflate the small ones
    sd = u.std(axis=0)
    sd = np.where(sd > 0, sd, 1.0)
    corr = LedoitWolf().fit(u / sd).covariance_ if len(u) > 1 else np.eye(k + 1)
    cov = corr * np.outer(sd, sd)
    cov = cov + np.diag(sd**2) * 1e-9
    ev, thr = pa if pa is not None else (s**2, np.full(len(s), np.nan))
    return SharedCore(mu, comps, k, ev, thr, share, cov, np.linalg.inv(cov),
                      float(np.linalg.slogdet(cov)[1]), u_mean, eps, len(x))


def shared_core(x: np.ndarray, n_surrogates: int = 40, quantile: float = 0.95,
                max_components: int = 10, rng: np.random.Generator | None = None,
                method: str = "horn", pa_n: int | None = 50, pa_draws: int = 5
                ) -> SharedCore:
    """Fit the shared (above-null) components of reference curves ``x`` (rows = references,
    already centered per row), on all rows.

    k comes from :func:`parallel_analysis` (``method``), capped at ``max_components``. With
    ``pa_n`` set and more rows than that, k is the median (rounded down) over ``pa_draws``
    random subsamples of ``pa_n`` rows: parallel-analysis counts grow with the number of rows
    (R-02), so a fixed n keeps k comparable across pieces and with the R-02 audit (n = 50).
    The eigenvalues / thresholds stored are those of the first draw."""
    rng = rng if rng is not None else np.random.default_rng(0)
    if pa_n is not None and len(x) > pa_n:
        ks, first = [], None
        for _ in range(pa_draws):
            sub = x[rng.choice(len(x), pa_n, replace=False)]
            k_, ev, thr = parallel_analysis(sub, n_surrogates, quantile, rng, method,
                                            max_components)
            ks.append(k_)
            first = first or (ev, thr)
        return _fit_core(x, int(np.floor(np.median(ks))), first)
    k, ev, thr = parallel_analysis(x, n_surrogates, quantile, rng, method, max_components)
    return _fit_core(x, k, (ev, thr))


def _crossfit(x: np.ndarray, k: int, n_folds: int, rng: np.random.Generator
              ) -> dict[str, np.ndarray]:
    """Out-of-fold decomposition of every reference with k fixed (calibration)."""
    n = len(x)
    folds = np.array_split(rng.permutation(n), min(n_folds, n))
    out = {"d": np.zeros_like(x), "shared": np.zeros_like(x), "loglik": np.full(n, np.nan),
           "mahal2": np.full(n, np.nan), "magnitude": np.full(n, np.nan)}
    for te in folds:
        tr = np.setdiff1d(np.arange(n), te)
        s = _fit_core(x[tr], k).score(x[te])
        for key in out:
            out[key][te] = s[key]
    out["individual"] = out["d"] - out["shared"]
    return out


# =========================================================================== reference features


def _agreement_arrays(target: np.ndarray, consensus: np.ndarray, min_points: int
                      ) -> tuple[float, float]:
    a, b = np.asarray(target, float), np.asarray(consensus, float)
    ok = np.isfinite(a) & np.isfinite(b)
    a, b = a[ok], b[ok]
    if len(a) < min_points:
        return np.nan, np.nan
    a, b = a - a.mean(), b - b.mean()
    rms = float(np.sqrt(np.mean((a - b) ** 2)))
    den = float(np.sqrt((a**2).sum() * (b**2).sum()))
    return (float((a * b).sum() / den) if den > 0 else np.nan), rms


def curve_agreement(target: pd.Series, refs: Sequence[pd.Series], min_refs: int,
                    min_points: int) -> tuple[float, float]:
    """Pearson r and RMS difference between a centred target curve and the centred mean of the
    references, at points with at least ``min_refs`` references (R-04 S1 features; promoted
    from ``extract._agreement``, unchanged). Units are those of the curve."""
    if not refs:
        return np.nan, np.nan
    m = pd.concat([r[~r.index.duplicated()] for r in refs], axis=1)
    cnt = m.notna().sum(axis=1)
    cons = m.mean(axis=1)[cnt >= min_refs]
    t = target[~target.index.duplicated()]
    common = t.index.intersection(cons.index)
    return _agreement_arrays(t.loc[common].to_numpy(float), cons.loc[common].to_numpy(float),
                             min_points)


def _matrix_agreement(t: np.ndarray, X: np.ndarray, min_refs: int, min_points: int
                      ) -> dict[str, float]:
    """r / RMS of target vs the reference mean, the percentile of that RMS among references
    (each against the mean of the others: leave-one-out), and the nearest-reference RMS."""
    cnt = np.isfinite(X).sum(axis=0)
    cols = (cnt >= max(min_refs, 2)) & np.isfinite(t)
    out = {"r": np.nan, "rms": np.nan, "rms_pct": np.nan, "nn_rms": np.nan, "n_refs": len(X)}
    if cols.sum() < min_points or len(X) < 2:
        return out
    Xc, tc = X[:, cols], t[cols]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        tot = np.nansum(Xc, axis=0)
        num = np.isfinite(Xc).sum(axis=0)
        r, rms = _agreement_arrays(tc, tot / num, min_points)
        out["r"], out["rms"] = r, rms
        loo = []
        for i in range(len(Xc)):
            xi = Xc[i]
            fi = np.isfinite(xi)
            cons = (tot - np.where(fi, xi, 0.0)) / (num - fi)
            loo.append(_agreement_arrays(xi, cons, min_points)[1])
        loo = np.array(loo)
        loo = loo[np.isfinite(loo)]
        if len(loo) and np.isfinite(rms):
            out["rms_pct"] = float(np.mean(loo <= rms))
        diffs = []
        for xi in Xc:
            ok = np.isfinite(xi)
            if ok.sum() >= min_points:
                a, b = tc[ok] - tc[ok].mean(), xi[ok] - xi[ok].mean()
                diffs.append(float(np.sqrt(np.mean((a - b) ** 2))))
        out["nn_rms"] = float(min(diffs)) if diffs else np.nan
    return out


# =========================================================================== interpret


@dataclass(eq=False)
class Interpretation:
    """Output of :func:`interpret`.

    Attributes:
        windows: one row per (block, window): bars, ``n_beats``, ``n_refs``, ``k_shared``,
            ``shared_share`` (of the references' between-performer variance),
            ``target_z`` (list of shared coordinates, in the channel's units times unit
            component vectors), ``individual_share`` (share of the target's squared deviation
            outside the shared space), ``loglik`` / ``mahal2`` (Gaussian on shared coordinates
            plus log magnitude, see :class:`SharedCore`), ``mahal2_shared`` (coordinates only),
            ``typicality_pct`` (share of out-of-fold references with a log-likelihood at or
            below the target's, +1 corrected: small = atypical, including too flat),
            ``magnitude`` (SD of the target's curve in the window: how much it shapes),
            ``magnitude_ref_median``, ``magnitude_pct`` (share of references at or below it),
            ``too_flat`` / ``too_extreme`` (magnitude below the ``1 - flag_quantile`` /
            above the ``flag_quantile`` quantile of the references),
            ``ref_individual_share_median``, ``n_bars_out_of_band``, ``status`` (``ok`` or why
            skipped).
        bars: one row per (block, bar): ``bar`` (index), ``bar_number``, ``window``,
            ``target_mean`` / ``band_lo`` / ``band_mid`` / ``band_hi`` (bar means; references
            row-centered in the window, the target level-aligned to their mean by the median
            difference; band = reference quantiles), ``dev_mean`` (signed target minus reference
            mean), ``dev_rms``, ``shared_rms``, ``individual_rms`` and their reference
            ``*_q`` thresholds (``flag_quantile`` of out-of-fold references), ``out_of_band``
            (dev_rms above its threshold), ``shared_out_of_band``, plus absolute-unit band
            columns ``abs_target`` / ``abs_lo`` / ``abs_mid`` / ``abs_hi`` (tempo in score beats
            per minute, velocity in MIDI).
        beats: one row per (block, target beat): ``beat``, ``ref_beat``, ``bar``, ``target``,
            ``band_lo`` / ``band_mid`` / ``band_hi`` (references row-centered over the piece,
            target level-aligned to their mean) and the
            absolute-unit columns; ``n_refs`` observed there.
        features: flat summary (``interp__*``, ``ref__*``).
        meta: ids and choices (references per block, velocity source and confidence,
            leave-one-out exclusions, beat mapping).
    """

    windows: pd.DataFrame
    bars: pd.DataFrame
    beats: pd.DataFrame
    features: dict[str, float]
    meta: dict[str, Any]


def _bar_index(beats: np.ndarray, bar_starts: np.ndarray) -> np.ndarray:
    if len(bar_starts) == 0:
        return np.zeros(len(beats), int)
    return np.maximum(np.searchsorted(bar_starts, beats + 1e-9, side="right") - 1, 0)


def _interp_rows(M: np.ndarray, grid: np.ndarray, x: np.ndarray) -> np.ndarray:
    """Rows of ``M`` (on the unit-spaced ``grid``) evaluated at ``x`` (linear, NaN-propagating;
    NaN where ``x`` is NaN or off the grid)."""
    n, p = M.shape
    out = np.full((n, len(x)), np.nan)
    pos = np.asarray(x, float) - grid[0]
    ok = np.isfinite(pos) & (pos >= -1e-9) & (pos <= p - 1 + 1e-9)
    i0 = np.clip(np.floor(pos[ok] + 1e-9).astype(int), 0, p - 1)
    fr = np.clip(pos[ok] - i0, 0.0, 1.0)
    fr[fr < 1e-9] = 0.0
    i1 = np.minimum(i0 + 1, p - 1)
    a, b = M[:, i0], M[:, i1]
    vals = np.where(fr > 0, a * (1 - fr) + b * fr, a)
    out[:, np.flatnonzero(ok)] = vals
    return out


def _windows(bar: np.ndarray, window_bars: int | None) -> np.ndarray:
    """Window id per frame column from its bar index."""
    if window_bars is None or len(bar) == 0:
        return np.zeros(len(bar), int)
    b0 = int(bar.min())
    w = (bar - b0) // window_bars
    last = int(w.max())
    n_last = len(np.unique(bar[w == last]))
    if last > 0 and n_last < window_bars / 2:
        w[w == last] = last - 1
    return w


def _center(x: np.ndarray) -> np.ndarray:
    return x - np.nanmean(x, axis=-1, keepdims=True)


def _align_level(t: np.ndarray, ref_mean: np.ndarray) -> np.ndarray:
    """Shift a row so that its median difference from the reference mean curve is zero.

    The level of a curve (own average tempo / loudness) is a nuisance. Plain mean centering
    lets one anomalous bar shift the whole row and make its other bars look off-band; the
    median difference ignores a local anomaly."""
    return t - np.nanmedian(t - ref_mean, axis=-1, keepdims=True)


def _quantiles(X: np.ndarray, qs: Sequence[float], min_n: int) -> np.ndarray:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        q = np.nanquantile(X, qs, axis=0)
    q[:, np.isfinite(X).sum(axis=0) < min_n] = np.nan
    return q


def _bar_means(X: np.ndarray, bar: np.ndarray, bars: np.ndarray) -> np.ndarray:
    X = np.atleast_2d(X)
    out = np.full((len(X), len(bars)), np.nan)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        for j, b in enumerate(bars):
            out[:, j] = np.nanmean(X[:, bar == b], axis=1)
    return out


def _bar_rms(X: np.ndarray, bar: np.ndarray, bars: np.ndarray) -> np.ndarray:
    X = np.atleast_2d(X)
    return np.sqrt(np.column_stack([np.mean(X[:, bar == b] ** 2, axis=1) for b in bars]))


def _choose_velocity_refs(refs: ReferenceSet, target_prov: str, cfg: InterpretationConfig
                          ) -> tuple[np.ndarray, str, str]:
    sensor = np.isin(refs.provenance.astype(str), SENSOR_PROVENANCE)
    if sensor.sum() >= cfg.min_sensor_velocity_references:
        rows, source = np.flatnonzero(sensor), "sensor"
    else:
        rows, source = np.arange(len(refs)), "all"
    conf = "high" if source == "sensor" and target_prov in SENSOR_PROVENANCE else "low"
    return rows, source, conf


def interpret(
    target: TargetCurves,
    refs: ReferenceSet,
    beat_map: BeatMap | None = None,
    config: InterpretationConfig | None = None,
) -> Interpretation:
    """Interpret one performance against a reference set of the same piece.

    Args:
        target: from :func:`target_from_aligned` / :func:`target_from_notes` /
            :func:`target_from_references`.
        refs: the reference set. A reference with the target's performance id or source id is
            removed first (leave-one-out) and listed in ``meta["loo_excluded"]``.
        beat_map: target score beats -> reference score beats. None = :func:`map_score_beats`
            on the two scores' notes when both are known (and not the same object, as for a
            reference taken as target); identity when neither is known and the grids match.
        config: :class:`InterpretationConfig`.

    The comparison frame is the target's own integer beats (so a repeat the target played
    twice is compared twice with the same reference bars). References are evaluated at the
    mapped beats. Per window and channel (``BLOCKS``): column and reference QC (R-02 rules),
    row centering, parallel analysis against the envelope null on the references, the shared
    core, the target's decomposition, and cross-fitted reference calibration.
    """
    cfg = config or InterpretationConfig()
    rng = np.random.default_rng(cfg.seed)
    meta: dict[str, Any] = {"target": target.performance_id, "piece_id": refs.piece_id}
    hit = refs.matching([target.performance_id, target.source_id])
    meta["loo_excluded"] = [str(x) for x in refs.performance_ids[hit]]
    refs = refs.subset(~hit) if hit.any() else refs
    if cfg.max_references is not None:
        sensor = np.isin(refs.provenance.astype(str), SENSOR_PROVENANCE)
        tr = np.flatnonzero(~sensor)
        if len(tr) > cfg.max_references:
            keep = np.sort(np.concatenate([np.flatnonzero(sensor),
                                           rng.choice(tr, cfg.max_references, replace=False)]))
            refs = refs.subset(keep)
            meta["subsampled_to"] = cfg.max_references
    meta["n_references"] = len(refs)

    # ---- frame: target beats and their reference beats
    tb = target.grid
    if beat_map is None and target.score_notes is not None and refs.score_notes is not None \
            and target.score_notes is not refs.score_notes:
        beat_map = map_score_beats(target.score_notes, refs.score_notes)
    if beat_map is None and not np.array_equal(target.grid, refs.grid):
        raise ValueError("target and reference grids differ and there are no score notes to "
                         "map them; pass beat_map")
    if beat_map is not None:
        rb = beat_map(tb)
        meta["beat_map_mapped_fraction"] = beat_map.mapped_fraction
        meta["beat_map_segments"] = beat_map.segments.to_dict("records")
    else:
        rb = tb.copy()
    bar = _bar_index(tb, target.bar_starts)
    bar_num = np.asarray(target.bar_numbers)[np.clip(bar, 0, max(len(target.bar_numbers) - 1,
                                                                0))] \
        if len(target.bar_numbers) else bar + 1
    win = _windows(bar, cfg.window_bars)

    vrows, vsource, vconf = _choose_velocity_refs(refs, target.provenance, cfg)
    meta.update(velocity_reference_source=vsource, velocity_confidence=vconf,
                n_velocity_references=len(vrows))
    blocks = {
        "tempo": (target.tempo, _interp_rows(refs.tempo, refs.grid, rb), np.arange(len(refs))),
        "velocity": (target.velocity_smooth,
                     _interp_rows(refs.velocity_smooth[vrows], refs.grid, rb), vrows),
    }
    abs_blocks = {
        "tempo": (target.tempo_bpm * np.exp(target.tempo),
                  refs.tempo_bpm[:, None] * np.exp(_interp_rows(refs.tempo, refs.grid, rb))),
        "velocity": (target.velocity_smooth, blocks["velocity"][1]),
    }
    meta["references"] = {b: [str(x) for x in refs.performance_ids[r]]
                          for b, (_, _, r) in blocks.items()}

    win_rows: list[dict[str, Any]] = []
    bar_rows: list[pd.DataFrame] = []
    beat_rows: list[pd.DataFrame] = []
    q_lo, q_mid, q_hi = cfg.band_quantiles
    for name, (t, X, _) in blocks.items():
        # ---- expert band over the whole frame (row-centered)
        Xc = _center(X)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            tc = _align_level(t, np.nanmean(Xc, axis=0))
        band = _quantiles(Xc, (q_lo, q_mid, q_hi), cfg.min_references)
        at, aX = abs_blocks[name]
        aband = _quantiles(aX, (q_lo, q_mid, q_hi), cfg.min_references)
        beat_rows.append(pd.DataFrame({
            "block": name, "beat": tb, "ref_beat": rb, "bar": bar, "bar_number": bar_num,
            "window": win, "target": tc, "band_lo": band[0], "band_mid": band[1],
            "band_hi": band[2], "abs_target": at, "abs_lo": aband[0], "abs_mid": aband[1],
            "abs_hi": aband[2], "n_refs": np.isfinite(X).sum(axis=0)}))  # fmt: skip

        for w in np.unique(win):
            cols_w = np.flatnonzero(win == w)
            bars_w = np.unique(bar[cols_w])
            row: dict[str, Any] = {"block": name, "window": int(w),
                                   "bar_lo": int(bar_num[cols_w[0]]),
                                   "bar_hi": int(bar_num[cols_w[-1]]), "status": "ok"}
            obs = np.isfinite(X[:, cols_w])
            ckeep = np.isfinite(t[cols_w]) & (obs.mean(axis=0) >= 1 - cfg.miss_beat) \
                if len(X) else np.zeros(len(cols_w), bool)
            cw = cols_w[ckeep]
            rkeep = np.isfinite(X[:, cw]).mean(axis=1) >= 1 - cfg.miss_ref if len(cw) else \
                np.zeros(len(X), bool)
            row.update(n_beats=len(cw), n_refs=int(rkeep.sum()))
            bdf = pd.DataFrame({"block": name, "bar": bars_w,
                                "bar_number": [int(bar_num[bar == b][0]) for b in bars_w],
                                "window": int(w)})
            if len(cw) < cfg.min_window_beats or rkeep.sum() < cfg.min_references:
                row["status"] = "too_few_beats" if len(cw) < cfg.min_window_beats \
                    else "too_few_references"
                win_rows.append(row)
                bar_rows.append(bdf)
                continue
            Xw = _center(_fill_rows(X[np.ix_(rkeep, cw)]))
            tw = _center(t[cw][None, :])[0]
            core = shared_core(Xw, cfg.n_surrogates, cfg.pa_quantile, cfg.max_components, rng,
                               cfg.pa_method, cfg.pa_n, cfg.pa_draws)
            ts = core.score(tw[None, :])
            cf = _crossfit(Xw, core.k, cfg.n_folds, rng)
            d2 = float((ts["d"] ** 2).sum())
            ref_ind = (cf["individual"] ** 2).sum(axis=1) / np.maximum((cf["d"] ** 2).sum(axis=1),
                                                                       1e-300)
            ll = cf["loglik"][np.isfinite(cf["loglik"])]
            typ = float((1 + np.sum(ll <= ts["loglik"][0])) / (1 + len(ll)))
            mag_t = float(ts["magnitude"][0])
            mag_r = Xw.std(axis=1)
            lo_m, hi_m = np.quantile(mag_r, (1 - cfg.flag_quantile, cfg.flag_quantile))
            row.update(
                k_shared=core.k, shared_share=core.shared_share,
                target_z=[float(v) for v in ts["z"][0]],
                individual_share=float((ts["individual"] ** 2).sum() / d2) if d2 > 0 else np.nan,
                loglik=float(ts["loglik"][0]), mahal2=float(ts["mahal2"][0]),
                mahal2_shared=float(ts["mahal2_shared"][0]), typicality_pct=typ,
                magnitude=mag_t, magnitude_ref_median=float(np.median(mag_r)),
                magnitude_pct=float(np.mean(mag_r <= mag_t)), too_flat=bool(mag_t < lo_m),
                too_extreme=bool(mag_t > hi_m),
                ref_individual_share_median=float(np.median(ref_ind)),
            )  # fmt: skip
            # ---- per bar: target vs out-of-fold references
            bw = bar[cw]
            bars_k = np.unique(bw)
            qf = cfg.flag_quantile
            stats = {}
            for key, tv, rv in (("dev", ts["d"], cf["d"]), ("shared", ts["shared"], cf["shared"]),
                                ("individual", ts["individual"], cf["individual"])):
                stats[f"{key}_rms"] = _bar_rms(tv, bw, bars_k)[0]
                stats[f"{key}_rms_q"] = np.quantile(_bar_rms(rv, bw, bars_k), qf, axis=0)
            mean_ref = core.mean
            tb_mean = _bar_means(ts["d"] + core.mean, bw, bars_k)[0]  # level-aligned target
            rb_q = np.quantile(_bar_means(Xw, bw, bars_k), (q_lo, q_mid, q_hi), axis=0)
            kdf = pd.DataFrame({
                "bar": bars_k, "target_mean": tb_mean, "band_lo": rb_q[0], "band_mid": rb_q[1],
                "band_hi": rb_q[2], "dev_mean": tb_mean - _bar_means(mean_ref[None, :], bw,
                                                                    bars_k)[0],
                "dev_rms": stats["dev_rms"], "dev_rms_q": stats["dev_rms_q"],
                "shared_rms": stats["shared_rms"], "shared_rms_q": stats["shared_rms_q"],
                "individual_rms": stats["individual_rms"],
                "individual_rms_q": stats["individual_rms_q"],
            })  # fmt: skip
            kdf["out_of_band"] = kdf["dev_rms"] > kdf["dev_rms_q"]
            kdf["shared_out_of_band"] = kdf["shared_rms"] > kdf["shared_rms_q"]
            bdf = bdf.merge(kdf, on="bar", how="left")
            row["n_bars_out_of_band"] = int(kdf["out_of_band"].sum())
            win_rows.append(row)
            bar_rows.append(bdf)

    beats_df = pd.concat(beat_rows, ignore_index=True)
    bars_df = pd.concat(bar_rows, ignore_index=True)
    # absolute-unit bar band
    abs_bar = []
    for name, (at, aX) in abs_blocks.items():
        bars_all = np.unique(bar)
        am = _bar_means(aX, bar, bars_all)
        q = _quantiles(am, (q_lo, q_mid, q_hi), cfg.min_references)
        abs_bar.append(pd.DataFrame({"block": name, "bar": bars_all,
                                     "abs_target": _bar_means(at[None, :], bar, bars_all)[0],
                                     "abs_lo": q[0], "abs_mid": q[1], "abs_hi": q[2]}))
    bars_df = bars_df.merge(pd.concat(abs_bar), on=["block", "bar"], how="left")
    for c in ("out_of_band", "shared_out_of_band"):
        if c in bars_df:
            bars_df[c] = bars_df[c].astype("boolean")
    windows_df = pd.DataFrame(win_rows)

    feats = _summary_features(windows_df, bars_df, vconf)
    feats.update(_reference_features(target, refs, blocks, beat_map, rb, cfg))
    return Interpretation(windows_df, bars_df, beats_df, feats, meta)


def _summary_features(windows: pd.DataFrame, bars: pd.DataFrame, vconf: str) -> dict[str, float]:
    out: dict[str, float] = {"interp__velocity_low_confidence": float(vconf == "low")}
    for b in BLOCKS:
        w = windows[(windows["block"] == b) & (windows["status"] == "ok")] \
            if len(windows) else windows
        br = bars[bars["block"] == b] if len(bars) else bars
        def col(df, c):
            return df[c].astype(float) if c in df and len(df) else pd.Series(dtype=float)
        typ, ind, k = col(w, "typicality_pct"), col(w, "individual_share"), col(w, "k_shared")
        oob = br["out_of_band"].dropna().astype(float) if "out_of_band" in br else pd.Series()
        out[f"interp__{b}_typicality_min"] = float(typ.min()) if typ.notna().any() else np.nan
        out[f"interp__{b}_typicality_median"] = float(typ.median()) if typ.notna().any() \
            else np.nan
        out[f"interp__{b}_individual_share_median"] = float(ind.median()) if len(ind) else np.nan
        out[f"interp__{b}_k_shared_median"] = float(k.median()) if len(k) else np.nan
        out[f"interp__{b}_frac_bars_out_of_band"] = float(oob.mean()) if len(oob) else np.nan
        out[f"interp__{b}_n_windows"] = float(len(w))
        mp = col(w, "magnitude_pct")
        out[f"interp__{b}_magnitude_pct_median"] = float(mp.median()) if mp.notna().any() \
            else np.nan
        for c in ("too_flat", "too_extreme"):
            v = col(w, c)
            out[f"interp__{b}_frac_windows_{c}"] = float(v.mean()) if len(v) else np.nan
    return out


def _reference_features(target: TargetCurves, refs: ReferenceSet, blocks: dict, beat_map,
                        rb: np.ndarray, cfg: InterpretationConfig) -> dict[str, float]:
    """R-04 S1-style reference features against the reference set (leave-one-out already
    applied): ``ref__{tempo_smooth,velocity_smooth,timing}_{r,rms,rms_pct,nn_rms}``."""
    out: dict[str, float] = {}
    for name, key in (("tempo", "tempo_smooth"), ("velocity", "velocity_smooth")):
        t, X, _ = blocks[name]
        a = _matrix_agreement(t, X, cfg.min_references, cfg.min_points)
        for s in ("r", "rms", "rms_pct", "nn_rms"):
            out[f"ref__{key}_{s}"] = a[s]
    # residual timing per score position
    tp = target.pos_grid
    mp = beat_map(tp) if beat_map is not None else tp
    j = np.searchsorted(refs.pos_grid, mp - 1e-6)
    jj = np.clip(j, 0, max(len(refs.pos_grid) - 1, 0))
    ok = np.isfinite(mp) & (j < len(refs.pos_grid))
    if len(refs.pos_grid):
        ok &= np.isclose(refs.pos_grid[jj], mp, atol=1e-6)
    Xt = np.full((len(refs), len(tp)), np.nan)
    Xt[:, ok] = refs.timing[:, jj[ok]]
    a = _matrix_agreement(target.timing, Xt, cfg.min_refs_timing, cfg.min_points)
    for s in ("r", "rms", "rms_pct", "nn_rms"):
        out[f"ref__timing_{s}"] = a[s]
    out["ref__n_references"] = float(len(refs))
    return out
