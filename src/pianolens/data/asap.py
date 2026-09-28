"""(n)ASAP loader: scores, Disklavier performances and ground-truth note alignments.

Source: https://github.com/CPJKU/asap-dataset (data under ``data/raw/asap``). Every row of
``metadata.csv`` is one performance MIDI with its MusicXML score, a note alignment TSV and a
match file. See DATASETS.md for counts and quirks.

Score handling: the MusicXML score is loaded with partitura, parts are merged, and repeats are
unfolded maximally (``unfold_part_maximal``), which gives note ids with a ``-<pass>`` suffix
(``n22-1``, ``n22-2``). This is what the (n)ASAP alignments refer to. Folders ending in
``_no_repeat`` etc. hold separately edited scores for performances that skip repeats.

Known quirk: a few alignment score ids name tied-continuation notes, which partitura's note
array merges into the first note of the tie, so those ids are absent from ``Score.notes``.
``AsapStats`` counts them.
"""

from __future__ import annotations

import logging
import re
import sys
from collections.abc import Iterator
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
import partitura as pt

from pianolens.data.piece_ids import (
    BEETHOVEN_SONATA_OPUS,
    MOZART_SONATA_K,
    make_piece_id,
    prefixed_piece_id,
)
from pianolens.data.types import (
    AlignedPerformance,
    Alignment,
    Performance,
    PerformerId,
    PieceId,
    Score,
    performance_from_partitura,
    score_from_partitura,
)

log = logging.getLogger(__name__)

DATASET = "asap"
DEFAULT_ROOT = Path(__file__).resolve().parents[3] / "data" / "raw" / "asap"


def data_available(root: Path | str = DEFAULT_ROOT) -> bool:
    return (Path(root) / "metadata.csv").is_file()


# --------------------------------------------------------------------------- ids

_EXPLICIT: dict[tuple[str, str], tuple[str, int | None, int | str | None]] = {
    # (composer, title) -> (catalogue, number, movement)
    ("Balakirev", "Islamey"): ("op18", None, None),
    ("Brahms", "Six_Pieces_op_118_2"): ("op118", 2, None),
    ("Chopin", "Ballades_1"): ("op23", None, None),
    ("Chopin", "Ballades_2"): ("op38", None, None),
    ("Chopin", "Ballades_3"): ("op47", None, None),
    ("Chopin", "Ballades_4"): ("op52", None, None),
    ("Chopin", "Barcarolle"): ("op60", None, None),
    ("Chopin", "Berceuse_op_57"): ("op57", None, None),
    ("Chopin", "Polonaises_53"): ("op53", None, None),
    ("Chopin", "Scherzos_20"): ("op20", None, None),
    ("Chopin", "Scherzos_31"): ("op31", None, None),
    ("Chopin", "Scherzos_39"): ("op39", None, None),
    ("Liszt", "Annees_de_pelerinage_2_1_Gondoliera"): ("s162", 1, None),
    ("Liszt", "Ballade_2"): ("s171", None, None),
    ("Liszt", "Concert_Etude_S145_1"): ("s145", 1, None),
    ("Liszt", "Concert_Etude_S145_2"): ("s145", 2, None),
    # ASAP files La campanella as "2"; it is No. 3 of S141 (see DATASETS.md quirks)
    ("Liszt", "Gran_Etudes_de_Paganini_2_La_campanella"): ("s141", 3, None),
    ("Liszt", "Gran_Etudes_de_Paganini_6_Theme_and_Variations"): ("s141", 6, None),
    ("Liszt", "Hungarian_Rhapsodies_6"): ("s244", 6, None),
    ("Liszt", "Sonata"): ("s178", None, None),
    ("Mozart", "Fantasie_475"): ("k475", None, None),
    ("Prokofiev", "Toccata"): ("op11", None, None),
    ("Schubert", "Wanderer_fantasie"): ("d760", None, None),
    ("Schubert", "Moment_Musical_no_1"): ("d780", 1, None),
    ("Schubert", "Moment_musical_no_3"): ("d780", 3, None),
    ("Schumann", "Arabeske"): ("op18", None, None),
    ("Schumann", "Toccata"): ("op7", None, None),
    ("Schumann", "Toccata_repeat"): ("op7", None, None),
    ("Scriabin", "Sonatas_5"): ("op53", None, None),
}

_CHOPIN_SONATA = {"2": "op35", "3": "op58"}
_ORDINAL = {"1st": 1, "2nd": 2, "3rd": 3, "4th": 4}


def asap_piece_id(composer: str, title: str) -> PieceId:
    """Canonical piece id for an ASAP (composer, title); dataset-prefixed if not confident."""
    if (composer, title) in _EXPLICIT:
        cat, no, mv = _EXPLICIT[(composer, title)]
        return make_piece_id(composer, cat, no, mv)
    m = None
    if composer == "Bach":
        m = re.fullmatch(r"(Prelude|Fugue)_bwv_(\d+)", title)
        if m:
            return make_piece_id("Bach", f"bwv{m[2]}", None, m[1].lower())
    elif composer == "Beethoven":
        m = re.fullmatch(r"Piano_Sonatas_(\d+)-(\d+)(?:_(\d+))?", title)
        if m and int(m[1]) in BEETHOVEN_SONATA_OPUS:
            op, no = BEETHOVEN_SONATA_OPUS[int(m[1])]
            mv: int | str = int(m[2]) if m[3] is None else f"mv{m[2]}to{m[3]}"
            return make_piece_id("Beethoven", op, no, mv)
    elif composer == "Chopin":
        m = re.fullmatch(r"Etudes_op_(\d+)_(\d+)", title)
        if m:
            return make_piece_id("Chopin", f"op{m[1]}", int(m[2]))
        m = re.fullmatch(r"Sonata_(\d)_(1st|2nd|3rd|4th)", title)
        if m and m[1] in _CHOPIN_SONATA:
            return make_piece_id("Chopin", _CHOPIN_SONATA[m[1]], None, _ORDINAL[m[2]])
    elif composer == "Liszt":
        m = re.fullmatch(r"Transcendental_Etudes_(\d+)", title)
        if m:
            return make_piece_id("Liszt", "s139", int(m[1]))
    elif composer == "Mozart":
        m = re.fullmatch(r"Piano_Sonatas_(\d+)-(\d+)", title)
        if m and int(m[1]) in MOZART_SONATA_K:
            return make_piece_id("Mozart", MOZART_SONATA_K[int(m[1])], None, int(m[2]))
    elif composer == "Rachmaninoff":
        m = re.fullmatch(r"Preludes_op_(\d+)_(\d+)", title)
        if m:
            return make_piece_id("Rachmaninoff", f"op{m[1]}", int(m[2]))
    elif composer == "Schubert":
        m = re.fullmatch(r"Impromptu_op\.90_D\.899_(\d)", title)
        if m:
            return make_piece_id("Schubert", "d899", int(m[1]))
        m = re.fullmatch(r"Impromptu_op142_(\d)", title)
        if m:
            return make_piece_id("Schubert", "d935", int(m[1]))
        m = re.fullmatch(r"Piano_Sonatas_(\d+)-(\d+)", title)
        if m:
            return make_piece_id("Schubert", f"d{m[1]}", None, int(m[2]))
    elif composer == "Schumann":
        m = re.fullmatch(r"Kreisleriana_(\d)", title)
        if m:
            return make_piece_id("Schumann", "op16", int(m[1]))
    elif composer == "Scriabin":
        m = re.fullmatch(r"Etudes_op_(\d+)_(\d+)", title)
        if m:
            return make_piece_id("Scriabin", f"op{m[1]}", int(m[2]))
    return prefixed_piece_id(DATASET, f"{composer}/{title}")


_PERFORMER_TAIL = re.compile(r"(?<=\d)M$")


def asap_performer_id(midi_path: str) -> PerformerId:
    """Heuristic performer id from the performance file name.

    ASAP names files ``<Name><yy>[M]`` (e.g. ``SunMeiting08``, ``Shi05M``, ``Na_2009_02``).
    We drop the trailing ``M`` marker, digits, ``_`` and ``-`` and lowercase the rest. This is
    not a verified identity: different pianists with the same surname key merge (e.g. ``huang``).
    """
    base = Path(midi_path).stem
    base = _PERFORMER_TAIL.sub("", base)
    key = re.sub(r"[\d_\-]+", "", base).lower()
    return PerformerId(f"{DATASET}:{key}")


# --------------------------------------------------------------------------- index


def asap_index(root: Path | str = DEFAULT_ROOT) -> pd.DataFrame:
    """``metadata.csv`` plus ``performance_id``, ``score_id``, ``piece_id``, ``performer_id``."""
    root = Path(root)
    md = pd.read_csv(root / "metadata.csv")
    md["performance_id"] = DATASET + ":" + md["midi_performance"].str.removesuffix(".mid")
    md["score_id"] = DATASET + ":" + md["folder"]
    md["piece_id"] = [
        asap_piece_id(c, t) for c, t in zip(md["composer"], md["title"], strict=True)
    ]
    md["performer_id"] = [asap_performer_id(p) for p in md["midi_performance"]]
    return md


# --------------------------------------------------------------------------- loading


@lru_cache(maxsize=16)
def _load_unfolded_part(xml_path: str):
    score = pt.load_score(xml_path)
    part = pt.score.merge_parts(score.parts) if len(score.parts) > 1 else score.parts[0]
    old = sys.getrecursionlimit()
    sys.setrecursionlimit(max(old, 10_000))
    try:
        return pt.score.unfold_part_maximal(part, update_ids=True)
    finally:
        sys.setrecursionlimit(old)


def load_asap_score(row: pd.Series, root: Path | str = DEFAULT_ROOT, keep_part: bool = False
                    ) -> Score:
    """Maximally unfolded MusicXML score for one index row."""
    path = Path(root) / row["xml_score"]
    part = _load_unfolded_part(str(path))
    return score_from_partitura(
        part,
        score_id=row["score_id"],
        piece_id=PieceId(row["piece_id"]),
        source_path=path,
        meta={"composer": row["composer"], "title": row["title"], "unfolded": "maximal"},
        keep_part=keep_part,
    )


def load_asap_performance(row: pd.Series, root: Path | str = DEFAULT_ROOT) -> Performance:
    path = Path(root) / row["midi_performance"]
    perf = pt.load_performance_midi(str(path))
    return performance_from_partitura(
        perf,
        performance_id=row["performance_id"],
        piece_id=PieceId(row["piece_id"]),
        performer_id=PerformerId(row["performer_id"]),
        provenance="disklavier",
        dataset=DATASET,
        source_path=path,
        meta={
            "composer": row["composer"],
            "title": row["title"],
            "robust_note_alignment": row["robust_note_alignment"],
            "maestro_midi": None if pd.isna(row["maestro_midi_performance"])
            else row["maestro_midi_performance"],
        },
    )


def asap_alignment_path(row: pd.Series, root: Path | str = DEFAULT_ROOT) -> Path:
    """Note alignment TSV path, derived from the MIDI path.

    ``metadata.csv`` has a mangled ``note_alignments`` value for the Schubert D.899 rows
    (``Schubert/Impromptu_op_note_alignments/...``: the dots in the folder name broke it), so we
    do not trust that column.
    """
    midi = Path(root) / row["midi_performance"]
    return midi.with_name(f"{midi.stem}_note_alignments") / "note_alignment.tsv"


def load_asap_alignment(row: pd.Series, root: Path | str = DEFAULT_ROOT) -> Alignment | None:
    """Ground-truth alignment, or None if the performance has none (e.g. Lisiecki10M)."""
    path = asap_alignment_path(row, root)
    if not path.is_file():
        return None
    al = pt.io.importparangonada.load_alignment_from_ASAP(str(path))
    return Alignment.from_partitura(
        al, row["score_id"], row["performance_id"], ground_truth=True, source="nasap"
    )


@dataclass
class AsapStats:
    """Counts from one pass over the dataset."""

    rows: int = 0
    loaded: int = 0
    failed: list[tuple[str, str]] = field(default_factory=list)
    scores: set[str] = field(default_factory=set)
    pieces: set[str] = field(default_factory=set)
    performers: set[str] = field(default_factory=set)
    matches: int = 0
    insertions: int = 0
    deletions: int = 0
    other_labels: int = 0
    no_alignment: list[str] = field(default_factory=list)
    align_score_ids_missing: int = 0
    align_perf_ids_missing: int = 0
    score_notes_unaligned: int = 0
    perf_notes_unaligned: int = 0

    def update(self, ap: AlignedPerformance) -> None:
        self.loaded += 1
        p, s, a = ap.performance, ap.score, ap.alignment
        self.pieces.add(p.piece_id)
        self.performers.add(p.performer_id)
        if s is not None:
            self.scores.add(s.score_id)
        if a is None:
            self.no_alignment.append(p.performance_id)
            return
        labels = a.pairs["label"]
        self.matches += int((labels == "match").sum())
        self.insertions += int((labels == "insertion").sum())
        self.deletions += int((labels == "deletion").sum())
        self.other_labels += int(
            (~np.isin(labels, ["match", "insertion", "deletion"])).sum()
        )
        sids = a.pairs["score_id"][a.pairs["score_id"] != ""]
        pids = a.pairs["performance_id"][a.pairs["performance_id"] != ""]
        self.align_perf_ids_missing += int((~np.isin(pids, p.notes["id"])).sum())
        self.perf_notes_unaligned += int((~np.isin(p.notes["id"], pids)).sum())
        if s is not None:
            self.align_score_ids_missing += int((~np.isin(sids, s.notes["id"])).sum())
            self.score_notes_unaligned += int((~np.isin(s.notes["id"], sids)).sum())


def iter_asap(
    root: Path | str = DEFAULT_ROOT,
    *,
    with_score: bool = True,
    with_alignment: bool = True,
    index: pd.DataFrame | None = None,
    stats: AsapStats | None = None,
) -> Iterator[AlignedPerformance]:
    """Yield every (n)ASAP performance with its score and ground-truth alignment.

    Bad files are logged and recorded in ``stats.failed``; they never stop the iteration.
    Rows sharing a score folder are grouped so each score is parsed once.
    """
    root = Path(root)
    md = asap_index(root) if index is None else index
    md = md.sort_values("xml_score", kind="stable")
    for _, row in md.iterrows():
        if stats is not None:
            stats.rows += 1
        try:
            perf = load_asap_performance(row, root)
            score = load_asap_score(row, root) if with_score else None
            al = load_asap_alignment(row, root) if with_alignment else None
        except Exception as e:  # noqa: BLE001 - count and continue
            log.warning("asap: failed %s: %r", row["midi_performance"], e)
            if stats is not None:
                stats.failed.append((row["midi_performance"], repr(e)))
            continue
        ap = AlignedPerformance(perf, score, al)
        if stats is not None:
            stats.update(ap)
        yield ap
