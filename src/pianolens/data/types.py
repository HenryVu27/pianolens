"""Common data types shared by every PianoLens dataset loader.

This module is the contract between the data layer and everything downstream (alignment,
features, models, eval). Keep it small. Notes are partitura structured note arrays
(``numpy`` structured arrays), not a new format:

* score notes come from ``partitura`` ``Part.note_array()``;
* performance notes come from ``partitura`` ``PerformedPart.note_array()``;
* alignments use partitura's label vocabulary (``match`` / ``insertion`` / ``deletion``) plus
  ``interpolated`` (see ``ALIGNMENT_LABELS``);
* beat-level curves (beat times, tempo, loudness) without notes use ``BeatCurve``.

Conventions
-----------
* ``Performance.notes["duration_sec"]`` is the **key-down** duration (note_on to note_off).
  partitura's default note array extends durations to the sustain-pedal release; loaders must
  switch that off (see ``performance_from_partitura``). Pedal lives in ``Performance.pedal``.
* Note ids are strings. Alignment ``score_id`` values refer to ``Score.notes["id"]`` and
  ``performance_id`` values refer to ``Performance.notes["id"]``.
* ``Score.measures["number"]`` is partitura's ``Measure.number`` (document numbering). After
  repeat unfolding a measure number appears once per pass, so it is not unique; the rows stay
  in time order. ``Score.measures["name"]`` is the printed label when the source has one.
* Onsets in quarters may be negative for a pickup measure (partitura puts beat 0 at the first
  downbeat).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, NewType

import numpy as np
import pandas as pd

__all__ = [
    "ALIGNMENT_DTYPE",
    "ALIGNMENT_LABELS",
    "MEASURE_DTYPE",
    "PEDAL_DTYPE",
    "PERFORMANCE_NOTE_FIELDS",
    "PROVENANCES",
    "RATING_COLUMNS",
    "compact_ids",
    "SCORE_NOTE_FIELDS",
    "AlignedPerformance",
    "Alignment",
    "BeatCurve",
    "Performance",
    "PerformerId",
    "PieceId",
    "Provenance",
    "Ratings",
    "Score",
    "performance_from_partitura",
    "measures_from_partitura",
    "score_from_partitura",
    "tempo_from_beat_times",
]

PieceId = NewType("PieceId", str)
"""Canonical piece id, shared across datasets (e.g. ``chopin_op10_no3``).

Built from composer + catalogue number + movement. Items without a canonical match keep a
dataset-prefixed id such as ``asap:Balakirev/Islamey``.
"""

PerformerId = NewType("PerformerId", str)
"""Performer id, dataset-prefixed unless identity is known across datasets
(e.g. ``asap:SunMeiting08``, ``percepiano:3``)."""

Provenance = Literal["disklavier", "transcribed", "sensor", "synthetic"]
PROVENANCES: tuple[str, ...] = ("disklavier", "transcribed", "sensor", "synthetic")

# Fields every Score.notes / Performance.notes array is guaranteed to have. Loaders may add more
# (partitura adds e.g. voice, onset_div, track, channel).
SCORE_NOTE_FIELDS: tuple[str, ...] = (
    "onset_beat",
    "duration_beat",
    "onset_quarter",
    "duration_quarter",
    "pitch",
    "id",
)
PERFORMANCE_NOTE_FIELDS: tuple[str, ...] = (
    "onset_sec",
    "duration_sec",
    "pitch",
    "velocity",
    "id",
)

PEDAL_DTYPE = np.dtype([("time_sec", "f8"), ("number", "i4"), ("value", "i4")])
"""MIDI pedal control changes: number 64 = sustain, 66 = sostenuto, 67 = soft (una corda)."""

MEASURE_DTYPE = np.dtype(
    [("number", "i4"), ("name", "U16"), ("start_quarter", "f8"), ("end_quarter", "f8")]
)
"""One row per measure; start / end are in the same quarter units as the score note array."""

ALIGNMENT_DTYPE = np.dtype([("label", "U12"), ("score_id", "U64"), ("performance_id", "U64")])
"""``label`` is one of ``ALIGNMENT_LABELS``: ``match`` / ``interpolated`` (both ids),
``insertion`` (performance_id only) or ``deletion`` (score_id only). The missing side is the
empty string. Ids longer than 64 characters are rejected. Other partitura labels (e.g.
``ornament``) are kept as they are when an alignment is imported."""

ALIGNMENT_LABELS: tuple[str, ...] = ("match", "interpolated", "insertion", "deletion")
"""Official alignment labels.

* ``match``: a score note and the performed note that realises it.
* ``interpolated``: a score note paired with a *synthetic* performance note that a dataset
  pipeline filled in (PianoCoRe's RAScoP refinement); nobody played it. Timing and velocity
  analyses may use it with care; correctness metrics must exclude it (DECISIONS.md 2026-09-27).
* ``insertion``: a performed note with no score note (extra note).
* ``deletion``: a score note with no performed note (missed note).
"""

_PEDAL_NUMBERS = (64, 66, 67)


def compact_ids(arr: np.ndarray) -> np.ndarray:
    """Return ``arr`` with its ``id`` field narrowed to the longest id present.

    partitura uses ``U256`` ids (1 KB per note); narrowing cuts note-array memory by ~10x.
    """
    names = arr.dtype.names or ()
    if "id" not in names or len(arr) == 0:
        return arr
    width = max(1, int(np.char.str_len(arr["id"]).max()))
    descr = [(n, f"U{width}" if n == "id" else arr.dtype[n]) for n in names]
    return arr.astype(np.dtype(descr))


def _require_fields(arr: np.ndarray, fields: tuple[str, ...], what: str) -> None:
    names = arr.dtype.names or ()
    missing = [f for f in fields if f not in names]
    if missing:
        raise ValueError(f"{what} note array lacks fields {missing}")


@dataclass(eq=False)
class Score:
    """A notated score (or score excerpt) as a partitura note array plus a measure map.

    Attributes:
        score_id: unique id of this score file within its dataset, dataset-prefixed.
        piece_id: canonical piece id.
        notes: partitura score note array; has at least ``SCORE_NOTE_FIELDS``.
        measures: structured array with ``MEASURE_DTYPE``, sorted by ``start_quarter``.
        source_path: file the score was loaded from, if any.
        meta: free-form metadata (composer, title, catalogue, unfolded, ...).
        part: the partitura ``Part`` the arrays came from, when kept (for markings, dynamics).
    """

    score_id: str
    piece_id: PieceId
    notes: np.ndarray
    measures: np.ndarray
    source_path: Path | None = None
    meta: dict[str, Any] = field(default_factory=dict)
    part: Any = field(default=None, repr=False)

    def __post_init__(self) -> None:
        _require_fields(self.notes, SCORE_NOTE_FIELDS, "Score")

    def note_measures(self) -> np.ndarray:
        """Measure number (``measures["number"]``) of each note, by onset; -1 if outside."""
        if len(self.measures) == 0:
            return np.full(len(self.notes), -1, dtype=int)
        starts = self.measures["start_quarter"]
        idx = np.searchsorted(starts, self.notes["onset_quarter"], side="right") - 1
        out = np.full(len(self.notes), -1, dtype=int)
        ok = idx >= 0
        ok[ok] &= self.notes["onset_quarter"][ok] < self.measures["end_quarter"][idx[ok]]
        out[ok] = self.measures["number"][idx[ok]]
        return out


@dataclass(eq=False)
class Performance:
    """A performance as a partitura performance note array plus pedal events.

    Attributes:
        performance_id: unique id within PianoLens, dataset-prefixed (e.g.
            ``asap:Chopin/Etudes_op_10/3/SunMeiting08``).
        piece_id: canonical piece id.
        performer_id: performer id.
        provenance: how the MIDI was captured (see ``PROVENANCES``).
        notes: partitura performance note array; has at least ``PERFORMANCE_NOTE_FIELDS``.
            ``duration_sec`` is key-down duration, not pedal-extended.
        pedal: structured array with ``PEDAL_DTYPE``, sorted by time.
        dataset: dataset name (``asap``, ``percepiano``, ...).
        span: inclusive (first, last) score measure numbers covered, or None for the whole piece.
            For excerpts; numbers refer to the printed measure numbers of the source.
        source_path: MIDI file the performance was loaded from, if any.
        meta: free-form metadata.
    """

    performance_id: str
    piece_id: PieceId
    performer_id: PerformerId
    provenance: Provenance
    notes: np.ndarray
    pedal: np.ndarray
    dataset: str
    span: tuple[int, int] | None = None
    source_path: Path | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_fields(self.notes, PERFORMANCE_NOTE_FIELDS, "Performance")
        if self.provenance not in PROVENANCES:
            raise ValueError(f"unknown provenance {self.provenance!r}")
        if self.pedal.dtype != PEDAL_DTYPE:
            raise ValueError("pedal must use PEDAL_DTYPE")

    @property
    def duration_sec(self) -> float:
        """Time from 0 to the last key release."""
        if len(self.notes) == 0:
            return 0.0
        return float(np.max(self.notes["onset_sec"] + self.notes["duration_sec"]))


@dataclass(eq=False)
class Alignment:
    """A note-level score-to-performance alignment.

    Attributes:
        pairs: structured array with ``ALIGNMENT_DTYPE``.
        score_id: ``Score.score_id`` this refers to.
        performance_id: ``Performance.performance_id`` this refers to.
        ground_truth: True for curated alignments (e.g. (n)ASAP), False for automatic ones.
        source: who produced it (``nasap``, ``parangonar-dualdtw``, ...).
    """

    pairs: np.ndarray
    score_id: str
    performance_id: str
    ground_truth: bool
    source: str

    def __post_init__(self) -> None:
        if self.pairs.dtype != ALIGNMENT_DTYPE:
            raise ValueError("pairs must use ALIGNMENT_DTYPE")

    @classmethod
    def from_partitura(
        cls,
        alignment: list[dict[str, Any]],
        score_id: str,
        performance_id: str,
        ground_truth: bool,
        source: str,
    ) -> Alignment:
        """Build from partitura's list-of-dicts alignment (``label``, ``score_id``,
        ``performance_id``). Labels other than match/insertion/deletion (e.g. ornament)
        are kept as-is."""
        rows = [
            (str(a["label"]), str(a.get("score_id", "")), str(a.get("performance_id", "")))
            for a in alignment
        ]
        if any(len(r[1]) > 64 or len(r[2]) > 64 for r in rows):
            raise ValueError("alignment note ids longer than 64 characters")
        return cls(np.array(rows, dtype=ALIGNMENT_DTYPE), score_id, performance_id,
                   ground_truth, source)

    def to_partitura(self) -> list[dict[str, str]]:
        """Inverse of ``from_partitura``: the format parangonar and partitura functions take."""
        out: list[dict[str, str]] = []
        for label, sid, pid in self.pairs.tolist():
            d = {"label": label}
            if sid:
                d["score_id"] = sid
            if pid:
                d["performance_id"] = pid
            out.append(d)
        return out

    def _of(self, label: str) -> np.ndarray:
        return self.pairs[self.pairs["label"] == label]

    @property
    def matches(self) -> np.ndarray:
        """Played notes paired with a score note. Excludes ``interpolated`` pairs."""
        return self._of("match")

    @property
    def interpolated(self) -> np.ndarray:
        """Score notes paired with a synthetic (not played) performance note."""
        return self._of("interpolated")

    @property
    def paired(self) -> np.ndarray:
        """``match`` plus ``interpolated`` pairs, in alignment order (both ids present)."""
        return self.pairs[np.isin(self.pairs["label"], ("match", "interpolated"))]

    @property
    def insertions(self) -> np.ndarray:
        """Performed notes with no score note (extra notes)."""
        return self._of("insertion")

    @property
    def deletions(self) -> np.ndarray:
        """Score notes with no performed note (missed notes)."""
        return self._of("deletion")


@dataclass(eq=False)
class AlignedPerformance:
    """A performance together with its score and (optionally) a note alignment."""

    performance: Performance
    score: Score | None
    alignment: Alignment | None = None


@dataclass(eq=False)
class BeatCurve:
    """Beat-level expressive curve of one performance: one entry per score beat.

    For sources that give beat times but no notes (MazurkaBL, Expert-Novice beat alignments),
    or for curves derived from a note alignment. Arrays are 1-D and have the same length.

    Attributes:
        performance_id: dataset-prefixed performance id.
        piece_id: canonical piece id.
        performer_id: performer id.
        time_sec: onset time of each beat in seconds; NaN where a beat was not annotated.
        loudness: loudness at each beat in ``loudness_unit``, or None if the source has none.
        tempo_bpm: local tempo at each beat in beats per minute. If not given it is derived
            from ``time_sec``: ``60 / (time_sec[i+1] - time_sec[i])`` (inter-beat interval to
            the next beat), NaN for the last beat and wherever a time is missing or not
            increasing.
        measure: score measure label of each beat (int), or None.
        beat: 0-based position of each beat within its measure (0 = downbeat), or None.
        loudness_unit: e.g. ``"sone_norm"`` (MazurkaBL normalised sones), ``"vel_midi"``.
        dataset: dataset name.
        provenance: capture provenance, or None when the times are annotations of audio
            (no ``PROVENANCES`` value applies).
        meta: free-form metadata.
    """

    performance_id: str
    piece_id: PieceId
    performer_id: PerformerId
    time_sec: np.ndarray
    loudness: np.ndarray | None = None
    tempo_bpm: np.ndarray | None = None
    measure: np.ndarray | None = None
    beat: np.ndarray | None = None
    loudness_unit: str = ""
    dataset: str = ""
    provenance: Provenance | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.time_sec = np.asarray(self.time_sec, dtype=float)
        if self.time_sec.ndim != 1:
            raise ValueError("time_sec must be 1-D")
        n = len(self.time_sec)
        for name, dtype in (("loudness", float), ("tempo_bpm", float), ("measure", int),
                            ("beat", float)):  # fmt: skip
            v = getattr(self, name)
            if v is None:
                continue
            v = np.asarray(v, dtype=dtype)
            if v.shape != (n,):
                raise ValueError(f"{name} has shape {v.shape}, expected ({n},)")
            setattr(self, name, v)
        if self.tempo_bpm is None:
            self.tempo_bpm = tempo_from_beat_times(self.time_sec)
        if self.provenance is not None and self.provenance not in PROVENANCES:
            raise ValueError(f"unknown provenance {self.provenance!r}")

    def __len__(self) -> int:
        return len(self.time_sec)

    def to_frame(self) -> pd.DataFrame:
        """One row per beat: ``measure``, ``beat``, ``time_sec``, ``tempo_bpm``, ``loudness``
        (label and loudness columns are omitted when absent)."""
        cols: dict[str, np.ndarray] = {}
        if self.measure is not None:
            cols["measure"] = self.measure
        if self.beat is not None:
            cols["beat"] = self.beat
        cols["time_sec"] = self.time_sec
        cols["tempo_bpm"] = np.asarray(self.tempo_bpm)
        if self.loudness is not None:
            cols["loudness"] = self.loudness
        return pd.DataFrame(cols)


def tempo_from_beat_times(time_sec: np.ndarray) -> np.ndarray:
    """Local tempo in BPM from beat onset times: ``60 / (t[i+1] - t[i])``; NaN for the last beat
    and wherever the interval is missing or not positive."""
    t = np.asarray(time_sec, dtype=float)
    out = np.full(len(t), np.nan)
    if len(t) > 1:
        ibi = np.diff(t)
        ok = np.isfinite(ibi) & (ibi > 0)
        out[:-1][ok] = 60.0 / ibi[ok]
    return out


RATING_COLUMNS: tuple[str, ...] = ("performance_id", "rater_id", "dimension", "value")


@dataclass(eq=False)
class Ratings:
    """Human ratings of performances, one row per (performance, rater, dimension).

    Attributes:
        table: long-format DataFrame with columns ``RATING_COLUMNS``. ``rater_id`` is a
            dataset-prefixed string; ``value`` is float on the dataset's native scale.
        dimensions: rating dimensions in the dataset's canonical order.
        scale: (min, max) of the native scale.
        dataset: dataset name.
    """

    table: pd.DataFrame
    dimensions: tuple[str, ...]
    scale: tuple[float, float]
    dataset: str

    def __post_init__(self) -> None:
        missing = [c for c in RATING_COLUMNS if c not in self.table.columns]
        if missing:
            raise ValueError(f"ratings table lacks columns {missing}")

    def matrix(self, dimension: str) -> pd.DataFrame:
        """Performance x rater matrix for one dimension (NaN where a rater did not rate)."""
        sub = self.table[self.table["dimension"] == dimension]
        return sub.pivot_table(
            index="performance_id", columns="rater_id", values="value", aggfunc="mean"
        )

    def mean(self) -> pd.DataFrame:
        """Performance x dimension matrix of the mean over raters."""
        m = self.table.pivot_table(
            index="performance_id", columns="dimension", values="value", aggfunc="mean"
        )
        return m[[d for d in self.dimensions if d in m.columns]]


def performance_from_partitura(
    performed: Any,
    *,
    performance_id: str,
    piece_id: PieceId,
    performer_id: PerformerId,
    provenance: Provenance,
    dataset: str,
    span: tuple[int, int] | None = None,
    source_path: Path | None = None,
    meta: dict[str, Any] | None = None,
) -> Performance:
    """Build a ``Performance`` from a partitura ``Performance`` or ``PerformedPart``.

    Disables partitura's pedal-extended durations (so ``duration_sec`` is key-down time) and
    collects sustain / sostenuto / soft pedal control changes from every performed part.
    Mutates the pedal threshold of the partitura object passed in. Note ids are unique: when
    several performed parts (MIDI tracks) repeat ids, all notes are renumbered ``n0..`` in onset
    order.
    """
    parts = list(getattr(performed, "performedparts", [performed]))
    note_arrays = []
    pedal_rows: list[tuple[float, int, int]] = []
    for pp in parts:
        # threshold 128 is above any MIDI value, so sound_off == note_off (key release)
        pp.sustain_pedal_threshold = 128
        note_arrays.append(pp.note_array())
        for c in pp.controls:
            if c["number"] in _PEDAL_NUMBERS:
                pedal_rows.append((float(c["time"]), int(c["number"]), int(c["value"])))
    notes = note_arrays[0] if len(note_arrays) == 1 else np.concatenate(note_arrays)
    notes = notes[np.argsort(notes["onset_sec"], kind="stable")]
    if len(note_arrays) > 1 and len(np.unique(notes["id"])) < len(notes):
        # partitura numbers note ids per performed part (one per MIDI track), so a multi-track
        # file repeats ids ("n0" in every track). Renumber in onset order so ids stay unique;
        # single-part files keep partitura's ids.
        notes = notes.copy()
        notes["id"] = [f"n{i}" for i in range(len(notes))]
    notes = compact_ids(notes)
    pedal = np.array(sorted(pedal_rows), dtype=PEDAL_DTYPE)
    return Performance(
        performance_id=performance_id,
        piece_id=piece_id,
        performer_id=performer_id,
        provenance=provenance,
        notes=notes,
        pedal=pedal,
        dataset=dataset,
        span=span,
        source_path=source_path,
        meta=dict(meta or {}),
    )


_DEFAULT_SCORE_NOTE_ARRAY_KW = {
    "include_time_signature": True,
    "include_staff": True,
    "include_grace_notes": True,
}


def measures_from_partitura(part: Any) -> np.ndarray:
    """Measure map (``MEASURE_DTYPE``) of a partitura ``Part``, in quarter units."""
    qmap = part.quarter_map
    rows = []
    for m in part.measures:
        name = getattr(m, "name", None)
        rows.append(
            (
                int(m.number) if m.number is not None else -1,
                "" if name is None else str(name),
                float(qmap(m.start.t)),
                float(qmap(m.end.t)),
            )
        )
    arr = np.array(rows, dtype=MEASURE_DTYPE)
    return arr[np.argsort(arr["start_quarter"], kind="stable")]


def score_from_partitura(
    part: Any,
    *,
    score_id: str,
    piece_id: PieceId,
    source_path: Path | None = None,
    meta: dict[str, Any] | None = None,
    keep_part: bool = False,
    **note_array_kw: Any,
) -> Score:
    """Build a ``Score`` from a single partitura ``Part`` (merge / unfold it first).

    The note array includes time signature, staff and grace-note fields by default; pass
    partitura ``note_array`` keywords to change that. Do not pass
    ``include_metrical_position=True``: it crashes in partitura 1.9.0 with numpy 2
    (``np.row_stack`` was removed).
    """
    kw = {**_DEFAULT_SCORE_NOTE_ARRAY_KW, **note_array_kw}
    notes = part.note_array(**kw)
    notes = compact_ids(notes[np.lexsort((notes["pitch"], notes["onset_div"]))])
    return Score(
        score_id=score_id,
        piece_id=piece_id,
        notes=notes,
        measures=measures_from_partitura(part),
        source_path=source_path,
        meta=dict(meta or {}),
        part=part if keep_part else None,
    )
