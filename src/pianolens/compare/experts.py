"""Choosing the expert recordings a window is compared with (P-01).

**Typical expert.** Within the window, each reference's curves are compared with the expert
median, on the F-06 channels (``pianolens.features.interpretation``):

* tempo shape: the smooth log tempo ratio at the target's integer beats mapped onto the
  reference score (``map_score_beats``), centred within the window per reference;
* velocity shape: the smooth velocity (MIDI), centred the same way;
* tempo level: the mean absolute log tempo in the window, so the chosen expert also plays at a
  typical speed there.

Each term is the RMS over columns of ``(reference - column median) / scale``; the scale is the
median over columns of the column MAD (x 1.4826) for the shapes and the MAD of the levels for
the level. The distance is the root mean square of the three terms (velocity weighted by
``velocity_weight``). The typical expert is the reference with the smallest distance.

**Contrasting expert** ("far but in band"): the reference whose distance is closest to the
``contrast_quantile`` of all distances. It is a different but still ordinary expert reading.

References need at least ``min_coverage`` of the window's columns observed in both channels.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass

import numpy as np

from pianolens.features.interpretation import BeatMap, ReferenceSet, _interp_rows

__all__ = ["ExpertChoice", "rank_experts"]

_MAD = 1.4826


@dataclass(frozen=True)
class ExpertChoice:
    """Distances of every eligible reference in one window, best first.

    Attributes:
        rows: indices into the reference set, sorted by distance.
        distance, tempo_shape, velocity_shape, tempo_level: per row (same order).
        n_eligible / n_references: counts.
        contrast_quantile: used for :meth:`contrast_order`.
    """

    rows: np.ndarray
    distance: np.ndarray
    tempo_shape: np.ndarray
    velocity_shape: np.ndarray
    tempo_level: np.ndarray
    n_eligible: int
    n_references: int
    contrast_quantile: float = 0.9

    def typical_order(self) -> np.ndarray:
        return self.rows

    def contrast_order(self) -> np.ndarray:
        """Rows ordered by closeness of their distance to the contrast quantile (fallbacks
        when the first MIDI cannot be loaded)."""
        if not len(self.rows):
            return self.rows
        q = float(np.quantile(self.distance, self.contrast_quantile))
        return self.rows[np.argsort(np.abs(self.distance - q), kind="stable")]

    def percentile(self, row: int) -> float:
        """Share of eligible references closer to the median than ``row``."""
        d = self.distance[self.rows == row]
        return float(np.mean(self.distance < d[0])) if len(d) else float("nan")

    def info(self, row: int) -> dict[str, float]:
        k = np.flatnonzero(self.rows == row)
        if not len(k):
            return {}
        i = int(k[0])
        return {"distance": float(self.distance[i]), "tempo_shape": float(self.tempo_shape[i]),
                "velocity_shape": float(self.velocity_shape[i]),
                "tempo_level": float(self.tempo_level[i]),
                "distance_percentile": self.percentile(row)}  # fmt: skip


def _shape_term(X: np.ndarray) -> np.ndarray:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        Xc = X - np.nanmean(X, axis=1, keepdims=True)
        med = np.nanmedian(Xc, axis=0)
        mad = np.nanmedian(np.abs(Xc - med), axis=0) * _MAD
        scale = float(np.nanmedian(mad))
        if not np.isfinite(scale) or scale <= 1e-12:
            scale = 1.0
        return np.sqrt(np.nanmean(((Xc - med) / scale) ** 2, axis=1))


def rank_experts(
    refs: ReferenceSet,
    target_beats: np.ndarray,
    beat_map: BeatMap | None,
    min_coverage: float = 0.8,
    velocity_weight: float = 1.0,
    contrast_quantile: float = 0.9,
) -> ExpertChoice:
    """Rank the references of one window by closeness to the expert median.

    Args:
        refs: the tier D reference set (target already excluded).
        target_beats: the target's integer score beats inside the window.
        beat_map: target -> reference score beats (None = same score).
    """
    tb = np.asarray(target_beats, float)
    rb = beat_map(tb) if beat_map is not None else tb
    n = len(refs)
    empty = np.array([], dtype=int)
    if n == 0 or not np.isfinite(rb).any():
        z = np.array([], float)
        return ExpertChoice(empty, z, z, z, z, 0, n, contrast_quantile)
    T = _interp_rows(refs.tempo, refs.grid, rb)
    V = _interp_rows(refs.velocity_smooth, refs.grid, rb)
    cov = np.minimum(np.isfinite(T).mean(axis=1), np.isfinite(V).mean(axis=1))
    ok = cov >= min_coverage
    if ok.sum() < 3:
        z = np.array([], float)
        return ExpertChoice(empty, z, z, z, z, int(ok.sum()), n, contrast_quantile)
    idx = np.flatnonzero(ok)
    T, V = T[ok], V[ok]
    ts = _shape_term(T)
    vs = _shape_term(V)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        lvl = np.log(refs.tempo_bpm[ok]) + np.nanmean(T, axis=1)
        med = np.nanmedian(lvl)
        s = float(np.nanmedian(np.abs(lvl - med)) * _MAD)
        tl = np.abs(lvl - med) / (s if np.isfinite(s) and s > 1e-12 else 1.0)
    w = np.array([1.0, velocity_weight, 1.0])
    D = np.sqrt((ts ** 2 * w[0] + vs ** 2 * w[1] + tl ** 2 * w[2]) / w.sum())
    good = np.isfinite(D)
    idx, D, ts, vs, tl = idx[good], D[good], ts[good], vs[good], tl[good]
    o = np.argsort(D, kind="stable")
    return ExpertChoice(idx[o], D[o], ts[o], vs[o], tl[o], len(idx), n, contrast_quantile)
