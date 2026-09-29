"""Score beat -> performance time, from an alignment (P-01).

The clip cut points come from the performer's own onsets, so rubato is followed exactly where
notes are played and interpolated linearly between them.

Construction: matched, non-grace (score beat, onset) pairs (``features.tempo.matched_onsets``,
the same notes the tempo model uses); the median onset per score position (a chord or a spread
chord gives one time); an increasing isotonic fit weighted by the notes per position (a
misaligned note cannot make time run backwards); then, one at a time, the knot with the
largest residual is dropped and the fit repeated while that residual exceeds
``max(outlier_sec, 4 * MAD)`` (at most ``max_drop_share`` of the knots). One at a time because
isotonic pooling spreads a single late knot's error over its neighbours. Beyond the first and last
knot the map is extended linearly with the median seconds-per-beat of the ``edge_knots``
nearest knots.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

__all__ = ["TimeMap", "time_map_from_aligned", "time_map_from_notes"]


@dataclass(frozen=True)
class TimeMap:
    """Monotone map from score beats to seconds.

    Attributes:
        beats: knot positions (score beats, strictly increasing).
        secs: knot times (seconds, non-decreasing).
        spb_start / spb_end: seconds per beat used to extend before the first / after the last
            knot.
        n_dropped: knots removed as outliers.
    """

    beats: np.ndarray
    secs: np.ndarray
    spb_start: float
    spb_end: float
    n_dropped: int = 0

    def __call__(self, beats: Any) -> np.ndarray:
        b = np.asarray(beats, dtype=float)
        out = np.interp(b, self.beats, self.secs)
        lo, hi = b < self.beats[0], b > self.beats[-1]
        out = np.where(lo, self.secs[0] + (b - self.beats[0]) * self.spb_start, out)
        out = np.where(hi, self.secs[-1] + (b - self.beats[-1]) * self.spb_end, out)
        return out

    def at(self, beat: float) -> float:
        return float(self(np.array([beat]))[0])


def _isotonic(y: np.ndarray, w: np.ndarray) -> np.ndarray:
    from sklearn.isotonic import IsotonicRegression

    x = np.arange(len(y), dtype=float)
    return IsotonicRegression(increasing=True).fit(x, y, sample_weight=w).predict(x)


def _edge_spb(beats: np.ndarray, secs: np.ndarray, k: int, end: bool) -> float:
    b, s = (beats[-k - 1:], secs[-k - 1:]) if end else (beats[:k + 1], secs[:k + 1])
    db, ds = np.diff(b), np.diff(s)
    ok = db > 1e-9
    if not ok.any():
        return 0.5
    v = float(np.median(ds[ok] / db[ok]))
    return v if np.isfinite(v) and v > 0 else 0.5


def time_map_from_notes(beats: Any, onsets_sec: Any, outlier_sec: float = 0.25,
                        edge_knots: int = 6, max_drop_share: float = 0.1) -> TimeMap:
    """Time map from matched (score beat, onset seconds) pairs."""
    df = pd.DataFrame({"b": np.round(np.asarray(beats, float), 6),
                       "t": np.asarray(onsets_sec, float)}).dropna()
    if df.empty:
        raise ValueError("no matched notes to build a time map")
    g = df.groupby("b")["t"].agg(["median", "size"]).sort_index()
    kb, kt, kw = g.index.to_numpy(float), g["median"].to_numpy(float), g["size"].to_numpy(float)
    dropped = 0
    fit = _isotonic(kt, kw) if len(kt) > 1 else kt
    max_drop = max(1, int(max_drop_share * len(kt)))
    while len(kt) > 2 and dropped < max_drop:
        res = np.abs(kt - fit)
        mad = float(np.median(res)) * 1.4826
        i = int(np.argmax(res))
        if res[i] <= max(outlier_sec, 4 * mad):
            break
        kb, kt, kw = np.delete(kb, i), np.delete(kt, i), np.delete(kw, i)
        fit = _isotonic(kt, kw)
        dropped += 1
    if len(kb) == 1:
        return TimeMap(kb, fit, 0.5, 0.5, dropped)
    return TimeMap(kb, fit, _edge_spb(kb, fit, edge_knots, False),
                   _edge_spb(kb, fit, edge_knots, True), dropped)


def time_map_from_aligned(ap: Any, **kw: Any) -> TimeMap:
    """Time map of an ``AlignedPerformance`` (``match`` pairs, grace notes out)."""
    from pianolens.features.tempo import matched_onsets

    notes, _ = matched_onsets(ap)
    return time_map_from_notes(notes["beat"].to_numpy(float), notes["onset_sec"].to_numpy(float),
                               **kw)
