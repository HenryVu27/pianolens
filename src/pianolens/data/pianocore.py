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
]  # fmt: skip


def data_available(root: Path | str = DEFAULT_ROOT) -> bool:
    root = Path(root)
    return (root / "metadata.csv").is_file() and (root / REFINED_ZIP).is_file()


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
    root: Path | str = DEFAULT_ROOT, tier: str = "a", split: str | None = None
) -> pd.DataFrame:
    """Metadata rows for a tier (``c``, ``b``, ``a`` or ``a_star``), with ``piece_id`` added.

    Piece ids are computed over all 250k rows (tier C) before filtering, so a piece gets the
    same id whichever tier or split is loaded."""
    md = pd.read_csv(Path(root) / "metadata.csv", usecols=_META_COLS, low_memory=False)
    md["piece_id"] = _piece_ids(md)
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
