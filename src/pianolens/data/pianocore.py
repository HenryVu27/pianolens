"""PianoCoRe loader: tier A / A* performances note-aligned to refined score MIDI.

Source: Zenodo 19186016 v1.0 (https://doi.org/10.5281/zenodo.19186016), files under
``data/raw/pianocore``: ``metadata.csv`` (one row per performance, 250,046 rows),
``PianoCoRe-1.0-refined.zip`` (refined score MIDI, refined performance MIDI and
``*_refined_align.npz`` for every ``is_refined`` row) and ``PianoCoRe-1.0-raw-midi.zip``
(raw performance MIDI and score MusicXML). Files are read straight from the zips; nothing is
extracted.

Refined alignment format (checked on disk, not documented beyond the dataset card): the npz
holds ``perf_idx`` (int32, one entry per refined score note) and ``interpolated`` (bool, same
length). Entry ``i`` refers to the i-th score note in MIDI order sorted by (tick, pitch), and
``perf_idx[i]`` to a performance note in the same order. partitura's note ids do NOT follow
that order for score MIDI (it groups by voice), so the loader sorts both note arrays by
(tick, pitch) and maps positions to partitura ids. Pitch agreement is checked per file. The refined
performance has exactly one note per score note; ``interpolated`` notes were synthesised by
the RAScoP pipeline, not played. They are labelled ``interpolated`` in the ``Alignment`` (not
``match``) and listed in ``Performance.meta["interpolated_ids"]``.

Provenance: ``is_transcription`` False rows (the 1,066 ASAP rows) are Disklavier; every other
row is transcribed from audio (Aria-AMT, Transkun V2, ATEPP, ByteDance).
"""

from __future__ import annotations

import io
import logging
import os
import re
import tempfile
import warnings
import zipfile
from collections.abc import Iterator
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path

import mido
import numpy as np
import pandas as pd
import partitura as pt

from pianolens.data.piece_ids import (
    PARTIAL_SCORES,
    SCORE_VERSION_MISMATCH,
    fold_accents,
    make_piece_id,
    prefixed_piece_id,
    score_movement,
)
from pianolens.data.types import (
    ALIGNMENT_DTYPE,
    AlignedPerformance,
    Alignment,
    PerformerId,
    PieceId,
    Score,
    performance_from_partitura,
    score_from_partitura,
)

log = logging.getLogger(__name__)

DATASET = "pianocore"
DEFAULT_ROOT = Path(__file__).resolve().parents[3] / "data" / "raw" / "pianocore"
REFINED_ZIP = "PianoCoRe-1.0-refined.zip"
RAW_ZIP = "PianoCoRe-1.0-raw-midi.zip"
REFINED_PREFIX = "PianoCoRe/refined/"
RAW_PREFIX = "PianoCoRe/raw/"

_META_COLS = [
    "id", "composer", "composition", "movement", "performance_id", "split", "tier_b", "tier_a",
    "tier_a_star", "score_id", "score_xml_path", "performance_dataset", "performance_midi_path",
    "performer", "is_transcription", "capture_model", "quality_label", "is_refined",
    "refined_score_midi_path", "refined_performance_midi_path", "refined_alignment_path",
    "refined_recall", "refined_performance_interpolated_note_count",
    # raw-MIDI guard (BL-35)
    "score_note_count", "performance_note_count", "performance_duration",
    "refined_performance_duration",
]  # fmt: skip


def data_available(root: Path | str = DEFAULT_ROOT) -> bool:
    root = Path(root)
    return (root / "metadata.csv").is_file() and (root / REFINED_ZIP).is_file()


# --------------------------------------------------------------------------- raw-MIDI guard

# BL-35. Raw performance MIDI (``performance_midi_path``) can hold more music than its score:
# a whole concerto against one movement, a recording that plays the work twice, a sonatina's
# two movements against a one-movement score. The refined files the loader reads are cropped
# to the score, so the loader and the cache are not affected; code that reads the raw files is.
# Thresholds were measured on all 157,207 tier A raw files (DATASETS.md, PianoCoRe notes):
SCORE_NOTES_TABLE = DEFAULT_ROOT.parents[1] / "processed" / "pianocore_score_notes.parquet"
"""Per score MusicXML: folded and longest-repeat note counts.

Built by ``scripts/build_pianocore_score_notes.py``."""
RAW_NOTE_RATIO_MAX = 1.65
"""Raw performance notes / notes of the score's longest repeat reading. The ratio's density
falls from the main mode at 1.0 to its minimum in (1.65, 1.70] and rises again to a second
mode at 1.75-2.0 (raw precision about 1 / ratio: the score is found once, the rest is extra)."""
RAW_SPAN_RATIO_MAX = 1.3
"""For pieces in :data:`SPAN_RULE_PIECES` only: raw duration / refined (cropped) duration.
The note ratio cannot see Op. 22's Andante spianato (about 21% more notes); this ratio is
bimodal for both partial-score pieces, with no file between 1.262 and 1.326 (Op. 22) or
between 1.215 and 2.513 (BWV 971)."""

RAW_NOTE_RULE_EXEMPT: dict[str, str] = {
    # BL-38: the score writes 48 measured tremolos at the 32nd-note level, which the score count
    # leaves unexpanded (BL-26 expands levels 1-2 only), so every one of the 33 tier A
    # performances has 3.3-4.7 times the score's 321 notes in about the score's duration. 24
    # are the piece alone (raw / refined duration 0.91-1.16); 9 also hold other material
    # (1.66-2.46; in the files checked it comes before the score's span), which the duration
    # rule catches.
    "pianocore:Mussorgsky,_Modest/Pictures_at_an_Exhibition/Cum_mortuis_in_lingua_mortua":
        "48 unexpanded 32nd-note tremolos in the score",
}
"""Piece id -> why the note rule cannot judge its raw files; the duration rule applies instead."""

SPAN_RULE_PIECES = frozenset(PARTIAL_SCORES) | frozenset(RAW_NOTE_RULE_EXEMPT)
"""Pieces whose raw files get the duration rule (:data:`RAW_SPAN_RATIO_MAX`)."""

_OP78_PATHETIQUE = (
    "whole-title Op. 78 score is 'Adagio cantabile from Piano Sonata No. 8, Pathetique' and "
    "the performances are Pathetique ii (A flat), not Op. 78")
MISLABELLED_ROWS: dict[str, str] = {f"PianoCoRe_0557{i}": _OP78_PATHETIQUE for i in range(80, 87)}
"""PianoCoRe row id -> why the row's title names a different work from its score and
performance (BL-38). ``pianocore_index`` drops these rows unless asked to keep them, and the
cache readers skip them. The 7 rows are the whole of ``beethoven_op78`` in PianoCoRe (score
``Beethoven,_Ludwig_van/Piano_Sonata_No.24_in_F_sharp_major,_Op.78_("A_Thérèse")/score.mxl``).
They are not relabelled ``beethoven_op13_mv2``: that would give the piece a second score and
remove it from every sampler's single-score eligibility, shifting their seeded draws."""


class RawLongerThanScore(ValueError):
    """A raw performance MIDI holds much more than its score (``raw_guard_reason``)."""


def raw_guard_reason(
    perf_notes: float,
    score_notes: float,
    *,
    raw_duration: float | None = None,
    refined_duration: float | None = None,
    span_rule: bool = False,
    note_rule: bool = True,
) -> str:
    """Why a raw performance must not be aligned to its score, or ``""`` when it may.

    ``score_notes`` should count the score's longest repeat reading (``unfolded_max`` in
    :data:`SCORE_NOTES_TABLE`), so a performance that plays every repeat is not flagged.
    ``span_rule`` (the piece is in :data:`SPAN_RULE_PIECES`) adds the duration rule, which needs
    the refined duration (tier A rows have it); ``note_rule=False`` for
    :data:`RAW_NOTE_RULE_EXEMPT` pieces."""
    if (note_rule and score_notes and score_notes > 0
            and perf_notes > RAW_NOTE_RATIO_MAX * score_notes):
        return (f"raw notes {int(perf_notes)} > {RAW_NOTE_RATIO_MAX} x score notes "
                f"{int(score_notes)} (ratio {perf_notes / score_notes:.2f})")  # fmt: skip
    if (span_rule and raw_duration and refined_duration and refined_duration > 0
            and raw_duration > RAW_SPAN_RATIO_MAX * refined_duration):
        return (f"span rule: raw duration {raw_duration:.0f} s > {RAW_SPAN_RATIO_MAX} x "
                f"refined duration {refined_duration:.0f} s "
                f"(ratio {raw_duration / refined_duration:.2f})")  # fmt: skip
    return ""


_score_notes_cache: dict[str, pd.DataFrame | None] = {}


def score_note_table(path: Path | str = SCORE_NOTES_TABLE) -> pd.DataFrame | None:
    """The score note-count table, or None (with a warning) when it has not been built."""
    key = str(path)
    if key not in _score_notes_cache:
        if Path(path).is_file():
            _score_notes_cache[key] = pd.read_parquet(path)
        else:
            log.warning("%s missing: raw guard falls back to metadata score_note_count "
                        "(run scripts/build_pianocore_score_notes.py)", path)  # fmt: skip
            _score_notes_cache[key] = None
    return _score_notes_cache[key]


def raw_guard(index: pd.DataFrame, score_notes: pd.DataFrame | None = None) -> pd.Series:
    """One reason string per row of a PianoCoRe index (``""``: the raw MIDI may be used).

    ``index`` needs the columns of :func:`pianocore_index`. The note rule divides
    ``performance_note_count`` (equal to the raw file's note-on count in 98.9% of tier A rows,
    at most 13 notes apart) by ``unfolded_max`` from ``score_notes`` (default
    :func:`score_note_table`); rows whose score is missing there, or failed to load, use the
    metadata ``score_note_count``. Rows of ``piece_ids.SCORE_VERSION_MISMATCH`` pieces and
    :data:`MISLABELLED_ROWS` are always flagged (BL-38)."""
    table = score_note_table() if score_notes is None else score_notes
    den = index["score_note_count"].astype(float)
    if table is not None:
        ok = table[table["unfolded_max"] > 0]
        unf = index["score_xml_path"].map(
            dict(zip(ok["score_xml_path"], ok["unfolded_max"], strict=True)))
        den = unf.astype(float).fillna(den)
    pids = index["piece_id"].astype(str)
    reasons = [
        (f"score version mismatch: {SCORE_VERSION_MISMATCH[p]}" if p in SCORE_VERSION_MISMATCH
         else f"mislabelled row: {MISLABELLED_ROWS[i]}" if i in MISLABELLED_ROWS
         else raw_guard_reason(n, s, raw_duration=d, refined_duration=rd,
                               span_rule=p in SPAN_RULE_PIECES,
                               note_rule=p not in RAW_NOTE_RULE_EXEMPT))
        for i, p, n, s, d, rd in zip(index["id"].astype(str), pids,
                                     index["performance_note_count"].astype(float), den,
                                     index["performance_duration"].astype(float),
                                     index["refined_performance_duration"].astype(float),
                                     strict=True)
    ]  # fmt: skip
    return pd.Series(reasons, index=index.index, name="raw_guard", dtype=object)


def guard_jobs(
    jobs: list, index: pd.DataFrame, *, id_key: str | int = "id", label: str = ""
) -> list:
    """Drop drawn jobs whose raw MIDI fails :func:`raw_guard`, logging each one.

    Call it after a seeded draw, not before: filtering the pool first would shift every later
    draw of the same generator. ``jobs`` are dicts (``id_key`` = ``"id"``) or tuples
    (``id_key`` = the position of the PianoCoRe row id); ids not in ``index`` are kept."""
    ids = {str(j[id_key]) for j in jobs}
    rows = index[index["id"].astype(str).isin(ids)]
    bad = {str(i): r for i, r in zip(rows["id"], raw_guard(rows), strict=True) if r}
    kept = [j for j in jobs if str(j[id_key]) not in bad]
    for i, r in sorted(bad.items()):
        log.warning("raw guard%s: skipped %s: %s", f" ({label})" if label else "", i, r)
    if bad:
        log.warning("raw guard%s: %d of %d jobs skipped", f" ({label})" if label else "",
                    len(jobs) - len(kept), len(jobs))  # fmt: skip
    return kept


def read_raw_performance(
    row: pd.Series, z: zipfile.ZipFile | None = None, *, guard: bool = True,
    root: Path | str = DEFAULT_ROOT,
) -> bytes:
    """Raw performance MIDI bytes of one index row; raises :class:`RawLongerThanScore` when
    the row fails :func:`raw_guard` (pass ``guard=False`` to read it anyway)."""
    if guard:
        reason = raw_guard(row.to_frame().T).iloc[0]
        if reason:
            raise RawLongerThanScore(f"{row['id']}: {reason}")
    if z is None:
        with zipfile.ZipFile(Path(root) / RAW_ZIP) as zz:
            return zz.read(RAW_PREFIX + str(row["performance_midi_path"]))
    return z.read(RAW_PREFIX + str(row["performance_midi_path"]))


# --------------------------------------------------------------------------- piece ids

# Catalogue systems by composer, tried first; then generic Op. / WoO.
_COMPOSER_CATALOGUE = {
    "Bach": r"BWV[\s_.]*(\d+[a-z]?)",
    "Mozart": r"(?<![A-Za-z])K\.[\s_]*(\d+[a-z]?)",
    "Schubert": r"(?<![A-Za-z])D\.[\s_]*(\d+)",
    "Liszt": r"(?<![A-Za-z])S\.[\s_]*(\d+)",
    "Debussy": r"(?<![A-Za-z])L\.[\s_]*(\d+)",
    "Haydn": r"Hob\.[\s_]*(XVI+)[:.]?(\d+)",
    "Scarlatti": r"(?<![A-Za-z])K\.[\s_]*(\d+)",
}
_CAT_PREFIX = {
    "Bach": "bwv", "Mozart": "k", "Schubert": "d", "Liszt": "s", "Debussy": "l",
    "Haydn": "hob", "Scarlatti": "k",
}  # fmt: skip
# "(?<![A-Za-z])" not "\b": titles use "_" as a space, and "_" is a word character.
_OPUS = re.compile(r"(?<![A-Za-z])Op\.[\s_]*(\d+[a-z]?)(?:[\s_,]*No\.[\s_]*(\d+))?", re.I)
_WOO = re.compile(r"(?<![A-Za-z])WoO[\s_.]*(\d+)", re.I)
_MOVEMENT_NUM = re.compile(r"^(\d+)\.")
# Only a bare leading "No.N": in "Nocturne_No.8_..." under "Nocturnes,_Op.27" the 8 is the
# global nocturne number, not the number within Op.27, so such movements stay prefixed.
_MOVEMENT_NO = re.compile(r"^No\.[\s_]*(\d+)")
_MULTI_MOVEMENT = re.compile(r"Sonat|Concert|Suite|Partita|Symphon|Fantasie_in", re.I)
_RANGE = re.compile(r"_-_\d+\.")
_PRELUDE_FUGUE = re.compile(r"(Prelude|Fugue)", re.I)


def _nan_to_str(x: object) -> str:
    return "" if x is None or (isinstance(x, float) and np.isnan(x)) else str(x)


def pianocore_piece_id(composer: str, composition: str, movement: str | None) -> PieceId:
    """Canonical piece id from PianoCoRe's composer / composition / movement strings.

    Conservative: only emits a canonical id when a catalogue number is found; otherwise a
    ``pianocore:`` prefixed id. Numbered items of a multi-movement form (sonata, suite,
    concerto, partita) become ``mv<k>``; numbered items of a set (études, nocturnes, pieces)
    become ``no<k>``, matching the (n)ASAP convention in ``piece_ids``.
    """
    composer = _nan_to_str(composer)
    composition = _nan_to_str(composition)
    movement = _nan_to_str(movement)
    # fold accents so "Dvořák" matches the plain-ASCII catalogue table keys
    surname = fold_accents(composer.split(",")[0].strip("_ "))
    fallback = prefixed_piece_id(
        DATASET, "/".join(p for p in (composer, composition, movement) if p)
    )
    if not surname:
        return fallback

    # Bach WTC-style: catalogue and prelude/fugue live in the movement string.
    if surname == "Bach":
        m = re.search(_COMPOSER_CATALOGUE["Bach"], movement)
        if m:
            pf = _PRELUDE_FUGUE.search(movement.split(m.group(0))[-1])
            return make_piece_id("Bach", f"bwv{m[1]}", None, pf[1].lower() if pf else None)

    catalogue: str | None = None
    number: str | None = None
    pat = _COMPOSER_CATALOGUE.get(surname)
    if pat:
        m = re.search(pat, composition)
        if m:
            catalogue = _CAT_PREFIX[surname] + "".join(g for g in m.groups() if g)
    if catalogue is None:
        m = _OPUS.search(composition)
        if m:
            catalogue, number = f"op{m[1]}", m[2]
        else:
            m = _WOO.search(composition)
            if m:
                catalogue = f"woo{m[1]}"
    if catalogue is None:
        return fallback
    multi = bool(_MULTI_MOVEMENT.search(composition))
    # A "No.N" in the composition title is NOT used: for "Ballade_No.1,_Op.23" it is not a
    # number within the opus. Sets such as "Hungarian_Rhapsody_No.6,_S.244" therefore collide
    # and are demoted to prefixed ids by pianocore_index.
    if _RANGE.search(movement):  # "3._Adagio_-_4._Allegro": a merged movement pair
        return fallback

    mv: str | None = None
    if movement:
        m_num = _MOVEMENT_NUM.match(movement)
        m_no = _MOVEMENT_NO.match(movement)
        if m_num:
            if multi:
                mv = m_num[1]
            elif number is None:
                number = m_num[1]
            else:
                return fallback
        elif m_no and number is None:
            number = m_no[1]
        else:
            return fallback  # a movement we cannot number: don't guess
    return make_piece_id(surname, catalogue, number, mv)


def pianocore_performer_id(row: pd.Series) -> PerformerId:
    """``pianocore:<name>`` when the performer is known, else one id per performance, so that
    unknown performers are never pooled into a single group."""
    name = _nan_to_str(row.get("performer"))
    if name:
        return PerformerId(f"{DATASET}:{re.sub(r'\s+', '_', name.strip())}")
    return PerformerId(f"{DATASET}:unknown/{row['id']}")


# --------------------------------------------------------------------------- index


def pianocore_index(
    root: Path | str = DEFAULT_ROOT, tier: str = "a", split: str | None = None,
    keep_mislabelled: bool = False,
) -> pd.DataFrame:
    """Metadata rows for a tier (``c``, ``b``, ``a`` or ``a_star``), with ``piece_id`` added.

    Piece ids are computed over all 250k rows (tier C) before filtering, so a piece gets the
    same id whichever tier or split is loaded. :data:`MISLABELLED_ROWS` (7 rows, 4 tier A) are
    dropped after that unless ``keep_mislabelled``."""
    md = pd.read_csv(Path(root) / "metadata.csv", usecols=_META_COLS, low_memory=False)
    md["piece_id"] = _piece_ids(md)
    if not keep_mislabelled:
        md = md[~md["id"].astype(str).isin(set(MISLABELLED_ROWS))]
    if tier != "c":
        md = md[md[f"tier_{tier}"].astype(bool)]
    if split is not None:
        md = md[md["split"] == split]
    return md.reset_index(drop=True)


def _piece_ids(md: pd.DataFrame) -> list[PieceId]:
    keys = md[["composer", "composition", "movement"]].astype(object)
    uniq = keys.drop_duplicates()
    ids = {
        tuple(map(_nan_to_str, k)): pianocore_piece_id(*k)
        for k in uniq.itertuples(index=False, name=None)
    }
    # two different (composition, movement) strings on one canonical id means the parse is
    # ambiguous (e.g. sources number suite movements differently): demote all of them
    by_id: dict[str, int] = {}
    for pid in ids.values():
        by_id[pid] = by_id.get(pid, 0) + 1
    for k, pid in ids.items():
        if by_id[pid] > 1 and not pid.startswith(f"{DATASET}:"):
            ids[k] = prefixed_piece_id(DATASET, "/".join(p for p in k if p))
    return [ids[tuple(map(_nan_to_str, k))] for k in keys.itertuples(False, None)]


# --------------------------------------------------------------------------- loading


@dataclass
class PianoCoReStats:
    loaded: int = 0
    failed: int = 0
    pitch_mismatch: int = 0
    notes_dropped: int = 0
    perfs_with_dropped_notes: int = 0
    failures: list[tuple[str, str]] = field(default_factory=list)


def _midi_from_bytes(data: bytes, loader):
    # Closed before loading: Windows cannot reopen a NamedTemporaryFile that is still open.
    with tempfile.NamedTemporaryFile(suffix=".mid", delete=False) as f:
        f.write(data)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return loader(f.name)
    finally:
        os.unlink(f.name)


def _midi_note_keys(data: bytes) -> list[tuple[int, int]]:
    """(absolute tick, pitch) of every note-on in a MIDI file, sorted by (tick, pitch).

    This is the note order the PianoCoRe ``*_refined_align.npz`` indices refer to."""
    mf = mido.MidiFile(file=io.BytesIO(data))
    keys: list[tuple[int, int]] = []
    for track in mf.tracks:
        tick = 0
        for msg in track:
            tick += msg.time
            if msg.type == "note_on" and msg.velocity > 0:
                keys.append((tick, msg.note))
    keys.sort()
    return keys


def _ids_by_key(keys: list[tuple[int, int]], notes: np.ndarray, tick_field: str) -> list[str]:
    """Map each (tick, pitch) key to a partitura note id; "" when partitura has no such note."""
    pool: dict[tuple[int, int], list[str]] = {}
    order = np.lexsort((notes["id"], notes["pitch"], notes[tick_field]))
    for k in order:
        pool.setdefault((int(notes[tick_field][k]), int(notes["pitch"][k])), []).append(
            str(notes["id"][k])
        )
    out = []
    for key in keys:
        bucket = pool.get(key)
        out.append(bucket.pop(0) if bucket else "")
    return out


class PianoCoRe:
    """Lazy reader over tier A (default) or A* of PianoCoRe.

    ``PianoCoRe().iter_aligned(limit=10)`` yields ``AlignedPerformance`` objects. Scores are
    the refined single-track score MIDI (the alignment refers to it), so the measure map comes
    from MIDI time signatures, not from MusicXML.
    """

    def __init__(self, root: Path | str = DEFAULT_ROOT, tier: str = "a", split: str | None = None):
        if tier not in ("a", "a_star"):
            raise ValueError("only tiers a and a_star carry note alignments")
        self.root = Path(root)
        self.tier = tier
        self.split = split
        self.stats = PianoCoReStats()
        self._zip: zipfile.ZipFile | None = None
        self._score_cache: dict[str, Score] = {}

    @cached_property
    def index(self) -> pd.DataFrame:
        return pianocore_index(self.root, self.tier, self.split)

    @property
    def zip(self) -> zipfile.ZipFile:
        if self._zip is None:
            self._zip = zipfile.ZipFile(self.root / REFINED_ZIP)
        return self._zip

    def _read(self, rel: str) -> bytes:
        return self.zip.read(REFINED_PREFIX + rel)

    def load_score(self, row: pd.Series) -> Score:
        rel = row["refined_score_midi_path"]
        if rel not in self._score_cache:
            if len(self._score_cache) > 64:
                self._score_cache.clear()
            score = _midi_from_bytes(self._read(rel), pt.load_score_midi)
            part = score.parts[0] if len(score.parts) == 1 else pt.score.merge_parts(score.parts)
            self._score_cache[rel] = score_from_partitura(
                part,
                score_id=f"{DATASET}:{rel}",
                piece_id=row["piece_id"],
                meta={"composer": row["composer"], "composition": row["composition"],
                      "movement": score_movement(row["piece_id"], _nan_to_str(row["movement"])),
                      "format": "refined_midi"},
            )  # fmt: skip
        return self._score_cache[rel]

    def load(self, row: pd.Series) -> AlignedPerformance:
        score = self.load_score(row)
        perf_pt = _midi_from_bytes(self._read(row["refined_performance_midi_path"]),
                                   pt.load_performance_midi)  # fmt: skip
        npz = np.load(io.BytesIO(self._read(row["refined_alignment_path"])))
        perf_idx, interp = npz["perf_idx"], npz["interpolated"].astype(bool)
        performance = performance_from_partitura(
            perf_pt,
            performance_id=f"{DATASET}:{row['id']}",
            piece_id=row["piece_id"],
            performer_id=pianocore_performer_id(row),
            provenance="transcribed" if bool(row["is_transcription"]) else "disklavier",
            dataset=DATASET,
            meta={
                "source_dataset": row["performance_dataset"],
                "source_performance_id": row["performance_id"],
                "capture_model": row["capture_model"],
                "split": row["split"],
                "tier_a_star": bool(row["tier_a_star"]),
                "quality_label": row["quality_label"],
                "refined_recall": float(row["refined_recall"]),
            },
        )
        s_keys = _midi_note_keys(self._read(row["refined_score_midi_path"]))
        p_keys = _midi_note_keys(self._read(row["refined_performance_midi_path"]))
        if len(s_keys) != len(perf_idx) or perf_idx.max(initial=-1) >= len(p_keys):
            raise ValueError(
                f"alignment length {len(perf_idx)} vs score {len(s_keys)} / perf {len(p_keys)}"
            )
        s_ids = _ids_by_key(s_keys, score.notes, "onset_div")
        p_ids_all = _ids_by_key(p_keys, performance.notes, "onset_tick")
        rows = []
        mismatches = 0
        lost = 0
        interpolated_ids = []
        for i, (j, is_interp) in enumerate(zip(perf_idx.tolist(), interp.tolist(), strict=True)):
            sid, pid = s_ids[i], p_ids_all[j]
            if s_keys[i][1] != p_keys[j][1]:
                mismatches += 1
            if not sid and not pid:
                lost += 1
                continue
            if not sid or not pid:  # a note partitura dropped on import
                lost += 1
                rows.append(("deletion", sid, "") if sid else ("insertion", "", pid))
                continue
            rows.append(("interpolated" if is_interp else "match", sid, pid))
            if is_interp:
                interpolated_ids.append(pid)
        performance.meta["interpolated_ids"] = interpolated_ids
        performance.meta["notes_dropped_on_import"] = lost
        if lost:
            self.stats.notes_dropped += lost
            self.stats.perfs_with_dropped_notes += 1
        if mismatches:
            self.stats.pitch_mismatch += 1
            log.warning("%s: %d aligned pairs disagree on pitch", row["id"], mismatches)
        alignment = Alignment(np.array(rows, dtype=ALIGNMENT_DTYPE), score.score_id,
                              performance.performance_id, ground_truth=False,
                              source="pianocore-rascop")  # fmt: skip
        return AlignedPerformance(performance, score, alignment)

    def iter_aligned(
        self, limit: int | None = None, piece_ids: set[str] | None = None
    ) -> Iterator[AlignedPerformance]:
        idx = self.index
        if piece_ids is not None:
            idx = idx[idx["piece_id"].isin(piece_ids)]
        idx = idx.sort_values("refined_score_midi_path", kind="stable")  # score cache hits
        n = 0
        for _, row in idx.iterrows():
            if limit is not None and n >= limit:
                return
            try:
                ap = self.load(row)
            except Exception as e:  # noqa: BLE001 - count and continue
                self.stats.failed += 1
                self.stats.failures.append((row["id"], repr(e)))
                log.warning("pianocore %s failed: %r", row["id"], e)
                continue
            self.stats.loaded += 1
            n += 1
            yield ap

    def close(self) -> None:
        if self._zip is not None:
            self._zip.close()
            self._zip = None
