"""Cached, note-aligned PianoCoRe tier A: one parquet file per piece (D-07, BL-09).

``scripts/build_pianocore_cache.py`` runs the ``pianolens.data.pianocore`` loader over every
tier A performance once (in parallel) and writes the result under ``data/processed/pianocore_A``:

``notes/<slug>.parquet``
    One row per alignment pair of every performance of one piece (columns ``NOTE_COLUMNS``).
    Score-note fields are prefixed ``s_``, performance-note fields ``p_``. A ``deletion`` row has
    no performance note (``p_*`` floats NaN, ints -1, id ""); an ``insertion`` row has no score
    note (``s_*`` likewise). Rows keep the loader's alignment order within a performance
    (score notes by (tick, pitch), then insertions). Times are float32, as partitura returns
    them for MIDI. ``s_measure`` is the measure number from the refined score MIDI's time
    signatures (``Score.note_measures``), not the printed bar number.
``performances.parquet``
    One row per cached performance (columns ``PERFORMANCE_COLUMNS``): ids, provenance, source
    metadata and per-label pair counts.
``pieces.parquet``
    One row per piece: ``piece_id``, ``slug``, ``file``, ``n_performances``, ``n_failed``,
    ``n_rows``.
``failures.parquet``
    ``pianocore_row_id``, ``piece_id``, ``error`` for every performance the loader could not read.
``_state/<slug>.json``
    Per-piece completion marker; the build skips pieces that have one (resumable).

The cache stores key-down durations and no pedal events; use the loader for pedal.
Labels are ``match``, ``interpolated`` (a synthetic RAScoP note, not played), ``insertion``
and ``deletion`` (see ``types.ALIGNMENT_LABELS``).
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from pianolens.data.piece_ids import fold_accents
from pianolens.data.types import AlignedPerformance

DEFAULT_CACHE = Path(__file__).resolve().parents[3] / "data" / "processed" / "pianocore_A"

# (column, arrow type, source array field, fill value for the missing side)
_SCORE_FIELDS: tuple[tuple[str, pa.DataType, str, Any], ...] = (
    ("s_id", pa.string(), "id", ""),
    ("s_onset_beat", pa.float32(), "onset_beat", np.nan),
    ("s_duration_beat", pa.float32(), "duration_beat", np.nan),
    ("s_onset_quarter", pa.float32(), "onset_quarter", np.nan),
    ("s_duration_quarter", pa.float32(), "duration_quarter", np.nan),
    ("s_pitch", pa.int16(), "pitch", -1),
    ("s_voice", pa.int16(), "voice", -1),
    ("s_staff", pa.int16(), "staff", -1),
    ("s_is_grace", pa.int8(), "is_grace", -1),
    ("s_ts_beats", pa.int16(), "ts_beats", -1),
    ("s_ts_beat_type", pa.int16(), "ts_beat_type", -1),
    ("s_measure", pa.int32(), "measure", -1),
)
_PERF_FIELDS: tuple[tuple[str, pa.DataType, str, Any], ...] = (
    ("p_id", pa.string(), "id", ""),
    ("p_onset_sec", pa.float32(), "onset_sec", np.nan),
    ("p_duration_sec", pa.float32(), "duration_sec", np.nan),
    ("p_pitch", pa.int16(), "pitch", -1),
    ("p_velocity", pa.int16(), "velocity", -1),
)
_ID_FIELDS: tuple[tuple[str, pa.DataType], ...] = (
    ("performance_id", pa.dictionary(pa.int32(), pa.string())),
    ("piece_id", pa.dictionary(pa.int32(), pa.string())),
    ("performer_id", pa.dictionary(pa.int32(), pa.string())),
    ("provenance", pa.dictionary(pa.int8(), pa.string())),
    ("label", pa.dictionary(pa.int8(), pa.string())),
)
NOTE_SCHEMA = pa.schema(
    [pa.field(n, t) for n, t in _ID_FIELDS]
    + [pa.field(c, t) for c, t, _, _ in _SCORE_FIELDS + _PERF_FIELDS]
)
NOTE_COLUMNS: tuple[str, ...] = tuple(NOTE_SCHEMA.names)

PERFORMANCE_COLUMNS: tuple[str, ...] = (
    "performance_id", "pianocore_row_id", "piece_id", "performer_id", "provenance", "score_id",
    "source_dataset", "source_performance_id", "capture_model", "split", "tier_a_star",
    "quality_label", "refined_recall", "n_score_notes", "n_perf_notes", "n_match",
    "n_interpolated", "n_insertion", "n_deletion", "notes_dropped_on_import",
    "pitch_mismatch", "duration_sec",
)  # fmt: skip

_UNSAFE = re.compile(r"[^a-z0-9]+")


def piece_slug(piece_id: str) -> str:
    """File-system-safe, unique name for a piece id.

    Canonical ids (``chopin_op10_no3``) are used as they are; prefixed ids are ASCII-folded,
    squeezed to ``[a-z0-9_]``, cut to 80 characters and suffixed with 8 hex digits of their
    SHA-1, so two ids never share a file."""
    if re.fullmatch(r"[a-z0-9_]+", piece_id):
        return piece_id
    base = _UNSAFE.sub("_", fold_accents(piece_id).lower()).strip("_")[:80]
    return f"{base}_{hashlib.sha1(piece_id.encode()).hexdigest()[:8]}"


def aligned_columns(ap: AlignedPerformance) -> dict[str, np.ndarray]:
    """Flatten one aligned performance into the note-table columns (plain numpy arrays)."""
    perf, score, al = ap.performance, ap.score, ap.alignment
    if score is None or al is None:
        raise ValueError("a score and an alignment are required")
    pairs = al.pairs
    n = len(pairs)
    s_notes = score.notes
    s_extra = {"measure": score.note_measures()}
    s_pos = {sid: i for i, sid in enumerate(s_notes["id"].tolist())}
    p_pos = {pid: i for i, pid in enumerate(perf.notes["id"].tolist())}
    si = np.array([s_pos.get(s, -1) if s else -1 for s in pairs["score_id"].tolist()], dtype=int)
    pi = np.array(
        [p_pos.get(p, -1) if p else -1 for p in pairs["performance_id"].tolist()], dtype=int
    )
    cols: dict[str, np.ndarray] = {
        "performance_id": np.full(n, perf.performance_id, dtype=object),
        "piece_id": np.full(n, str(perf.piece_id), dtype=object),
        "performer_id": np.full(n, str(perf.performer_id), dtype=object),
        "provenance": np.full(n, perf.provenance, dtype=object),
        "label": pairs["label"].astype(object),
    }
    for fields, notes, idx, extra in (
        (_SCORE_FIELDS, s_notes, si, s_extra),
        (_PERF_FIELDS, perf.notes, pi, {}),
    ):
        ok = idx >= 0
        for col, typ, src, fill in fields:
            source = extra[src] if src in extra else notes[src]
            if pa.types.is_string(typ):
                out = np.full(n, fill, dtype=object)
                out[ok] = source[idx[ok]].astype(str)
            else:
                out = np.full(n, fill, dtype=typ.to_pandas_dtype())
                out[ok] = source[idx[ok]]
            cols[col] = out
    return cols


def columns_to_table(cols: dict[str, np.ndarray]) -> pa.Table:
    arrays = []
    for field in NOTE_SCHEMA:
        a = cols[field.name]
        if pa.types.is_dictionary(field.type):
            arrays.append(pa.array(a, type=pa.string()).dictionary_encode().cast(field.type))
        else:
            arrays.append(pa.array(a, type=field.type))
    return pa.Table.from_arrays(arrays, schema=NOTE_SCHEMA)


def performance_record(ap: AlignedPerformance, row: pd.Series, pitch_mismatch: bool) -> dict:
    """The ``performances.parquet`` row for one aligned performance."""
    perf, score, al = ap.performance, ap.score, ap.alignment
    assert score is not None and al is not None
    labels = al.pairs["label"]
    meta = perf.meta
    return {
        "performance_id": perf.performance_id,
        "pianocore_row_id": str(row["id"]),
        "piece_id": str(perf.piece_id),
        "performer_id": str(perf.performer_id),
        "provenance": perf.provenance,
        "score_id": score.score_id,
        "source_dataset": str(meta.get("source_dataset", "")),
        "source_performance_id": str(meta.get("source_performance_id", "")),
        "capture_model": str(meta.get("capture_model", "")),
        "split": str(meta.get("split", "")),
        "tier_a_star": bool(meta.get("tier_a_star", False)),
        "quality_label": str(meta.get("quality_label", "")),
        "refined_recall": float(meta.get("refined_recall", np.nan)),
        "n_score_notes": len(score.notes),
        "n_perf_notes": len(perf.notes),
        "n_match": int((labels == "match").sum()),
        "n_interpolated": int((labels == "interpolated").sum()),
        "n_insertion": int((labels == "insertion").sum()),
        "n_deletion": int((labels == "deletion").sum()),
        "notes_dropped_on_import": int(meta.get("notes_dropped_on_import", 0)),
        "pitch_mismatch": bool(pitch_mismatch),
        "duration_sec": perf.duration_sec,
    }


# --------------------------------------------------------------------------- reading


def cache_available(root: Path | str = DEFAULT_CACHE) -> bool:
    return (Path(root) / "pieces.parquet").is_file()


def load_pieces(root: Path | str = DEFAULT_CACHE) -> pd.DataFrame:
    """The piece manifest (``pieces.parquet``)."""
    return pd.read_parquet(Path(root) / "pieces.parquet")


def load_performances(root: Path | str = DEFAULT_CACHE) -> pd.DataFrame:
    """One row per cached performance (``PERFORMANCE_COLUMNS``)."""
    return pd.read_parquet(Path(root) / "performances.parquet")


def load_piece_notes(
    piece_id: str,
    root: Path | str = DEFAULT_CACHE,
    columns: list[str] | None = None,
    labels: tuple[str, ...] | None = None,
) -> pd.DataFrame:
    """Aligned note rows of every cached performance of one piece.

    Args:
        piece_id: canonical or ``pianocore:`` prefixed piece id.
        columns: subset of ``NOTE_COLUMNS`` to read (all by default).
        labels: keep only these alignment labels, e.g. ``("match",)`` to drop interpolated
            (synthetic) notes and unmatched rows.
    """
    path = Path(root) / "notes" / f"{piece_slug(piece_id)}.parquet"
    if not path.is_file():
        raise KeyError(f"piece {piece_id!r} is not in the cache at {root}")
    filters = [("label", "in", list(labels))] if labels else None
    cols = columns
    if cols is not None and labels and "label" not in cols:
        cols = [*cols, "label"]
    df = pq.read_table(path, columns=cols, filters=filters).to_pandas()
    if columns is not None and cols != columns:
        df = df[columns]
    return df
