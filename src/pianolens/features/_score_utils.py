"""Shared score helpers for feature extractors: note tables with staff / voice / bar fields.

Created by F-04 (tier B control). Kept small and dependency-free so tier C / D code can reuse it.

* :func:`score_note_frame`: one row per score note with ``staff`` and ``voice`` (1 when the
  note array lacks them), durations, grace flag and ``measure_idx`` (row of
  ``Score.measures``, -1 outside).
* :func:`matched_note_frame`: :func:`pianolens.features.tempo.matched_onsets` (``match`` pairs,
  no grace notes, no ``interpolated``) joined with the score fields above.
* :func:`beat_to_quarter`: score beats to score quarters, piecewise linear through the notes.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from pianolens.features.correctness import measure_rows

__all__ = ["beat_to_quarter", "matched_note_frame", "score_note_frame"]


def score_note_frame(score: Any) -> pd.DataFrame:
    """Score notes as a DataFrame.

    Columns: ``score_id``, ``beat``, ``quarter``, ``dur_beat``, ``dur_quarter``, ``pitch``,
    ``staff``, ``voice``, ``is_grace``, ``measure_idx``. Sorted by (quarter, pitch).
    """
    sn = score.notes
    names = sn.dtype.names or ()
    n = len(sn)

    def col(name: str, default: Any) -> np.ndarray:
        return sn[name] if name in names else np.full(n, default)

    df = pd.DataFrame({
        "score_id": sn["id"].astype(str),
        "beat": sn["onset_beat"].astype(float),
        "quarter": sn["onset_quarter"].astype(float),
        "dur_beat": sn["duration_beat"].astype(float),
        "dur_quarter": sn["duration_quarter"].astype(float),
        "pitch": sn["pitch"].astype(int),
        "staff": col("staff", 1).astype(int),
        "voice": col("voice", 1).astype(int),
        "is_grace": col("is_grace", False).astype(bool),
    })  # fmt: skip
    df["measure_idx"] = measure_rows(score.measures, df["quarter"].to_numpy())
    return df.sort_values(["quarter", "pitch"], kind="stable").reset_index(drop=True)


def matched_note_frame(ap: Any) -> tuple[pd.DataFrame, dict[str, int]]:
    """Matched, non-grace (score note, performed note) pairs with score staff / voice / bar.

    Returns ``(df, counts)``: ``df`` has the columns of ``tempo.matched_onsets`` (``score_id``,
    ``performance_id``, ``beat``, ``quarter``, ``pitch``, ``vel_midi``, ``onset_sec``) plus
    ``dur_beat``, ``dur_quarter``, ``staff``, ``voice``, ``measure_idx``; ``counts`` are the
    skip counts of ``matched_onsets``.
    """
    from pianolens.features.tempo import matched_onsets

    df, counts = matched_onsets(ap)
    sf = score_note_frame(ap.score).drop_duplicates("score_id")
    extra = sf[["score_id", "dur_beat", "dur_quarter", "staff", "voice", "measure_idx"]]
    return df.merge(extra, on="score_id", how="left"), counts


def beat_to_quarter(score: Any, beats: np.ndarray) -> np.ndarray:
    """Map score beats to score quarters by linear interpolation through the note onsets."""
    b = np.asarray(beats, dtype=float)
    sb, sq = score.notes["onset_beat"].astype(float), score.notes["onset_quarter"].astype(float)
    if len(sb) == 0:
        return np.full(len(b), np.nan)
    df = pd.DataFrame({"b": sb, "q": sq}).groupby("b", sort=True)["q"].min()
    return np.interp(b, df.index.to_numpy(float), df.to_numpy(float))
