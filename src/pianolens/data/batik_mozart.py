"""Batik-plays-Mozart loader: 12 Mozart sonatas (36 movements) by Roland Batik.

Source: https://github.com/huispaty/batik_plays_mozart under ``data/raw/batik_mozart``,
license CC BY-NC-SA 4.0. Performances were recorded on a computer-monitored Boesendorfer
(provenance ``sensor``); match files give ground-truth note alignments. The ``annotations``
submodule is DCMLab/mozart_piano_sonatas (harmony, cadence, phrase labels). The repo also
ships per-note score annotations in ``score_parts_annotated/<kvNNN_M>_spart_*.csv`` whose
``id`` column uses the match-file score note ids (e.g. ``n15-1``).

Performed score with markings (D-11)
------------------------------------
The match files rebuild the score without markings (no slurs, dynamics, barlines, tempo
words). ``iter_aligned(musicxml_score=True)`` / :func:`performed_score` instead unfold the
edited MusicXML ``scores_edited/<stem>.musicxml`` to the repeat path whose note ids equal the
match-file ids (every match id resolves in all 36 movements; id Jaccard 1.0 in 35, 0.9996 in
kv281_3 where the MusicXML has one extra note), so the ground-truth alignment
still applies and the markings can be read (``Score.part`` is kept). Only the four repeat
paths with note counts closest to the match score are built: K.284/3 (variations) has many
paths and building all of them took over 30 minutes and 18 GB. The chosen path and its
id agreement are in ``Score.meta`` (``unfolded``, ``id_coverage``, ``id_jaccard``).

Phrase and cadence tables
-------------------------
:func:`phrase_annotations` reads the DCML labels of ``score_parts_annotated`` and maps them to
the beats of a performed score (either score: the ids are the same). ``phraseend`` ``{``
starts a phrase, ``}`` ends it (on the cadential arrival note, not the last note), ``}{`` does
both (elision). Cadences: PAC, IAC, HC, EC (evaded), DC (deceptive). DCML annotations:
DCMLab/mozart_piano_sonatas, CC BY-NC-SA 4.0 (``annotations/LICENSE``).
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from pianolens.data.match_corpus import load_match_file
from pianolens.data.piece_ids import make_piece_id
from pianolens.data.types import (
    AlignedPerformance,
    PerformerId,
    PieceId,
    Score,
    score_from_partitura,
)

log = logging.getLogger(__name__)

DATASET = "batik_mozart"
DEFAULT_ROOT = Path(__file__).resolve().parents[3] / "data" / "raw" / "batik_mozart"
PERFORMER = PerformerId(f"{DATASET}:RolandBatik")
ANNOTATION_KINDS = ("annotated", "cadence", "harmony", "phrases")


def data_available(root: Path | str = DEFAULT_ROOT) -> bool:
    return (Path(root) / "match").is_dir()


def movement_piece_id(stem: str) -> PieceId:
    """``kv279_1`` -> ``mozart_k279_mv1``."""
    kv, mv = stem.split("_")
    return make_piece_id("Mozart", "k" + kv.removeprefix("kv"), None, int(mv))


@dataclass
class BatikStats:
    loaded: int = 0
    failed: int = 0
    failures: list[tuple[str, str]] = field(default_factory=list)


def match_files(root: Path | str = DEFAULT_ROOT) -> list[Path]:
    return sorted((Path(root) / "match").glob("kv*.match"))


def _load_match(path: Path) -> AlignedPerformance:
    return load_match_file(
        path,
        dataset=DATASET,
        performance_id=f"{DATASET}:{path.stem}",
        score_id=f"{DATASET}:{path.stem}",
        piece_id=movement_piece_id(path.stem),
        performer_id=PERFORMER,
        provenance="sensor",
    )


def iter_aligned(
    root: Path | str = DEFAULT_ROOT,
    stats: BatikStats | None = None,
    *,
    musicxml_score: bool = False,
    stems: set[str] | None = None,
) -> Iterator[AlignedPerformance]:
    """Every movement with its ground-truth alignment.

    ``musicxml_score=True`` replaces the match-built score (no markings) by the performed
    score unfolded from the edited MusicXML (:func:`performed_score`); ids, beats and the
    alignment are unchanged. ``stems`` (e.g. ``{"kv331_1"}``) restricts the movements.
    """
    stats = stats if stats is not None else BatikStats()
    for path in match_files(root):
        if stems is not None and path.stem not in stems:
            continue
        try:
            ap = _load_match(path)
            if musicxml_score:
                ap = AlignedPerformance(ap.performance, performed_score(ap.score, root=root),
                                        ap.alignment)
            yield ap
            stats.loaded += 1
        except Exception as e:  # noqa: BLE001 - count and continue
            stats.failed += 1
            stats.failures.append((path.name, repr(e)))
            log.warning("batik %s failed: %r", path.name, e)


def load_note_annotations(
    stem: str, kind: str = "annotated", root: Path | str = DEFAULT_ROOT
) -> pd.DataFrame:
    """Per-score-note annotations for one movement (``kind`` in ``ANNOTATION_KINDS``)."""
    if kind not in ANNOTATION_KINDS:
        raise ValueError(f"kind must be one of {ANNOTATION_KINDS}")
    return pd.read_csv(Path(root) / "score_parts_annotated" / f"{stem}_spart_{kind}.csv")


def load_aligned(stem: str, root: Path | str = DEFAULT_ROOT, *, musicxml_score: bool = False
                 ) -> AlignedPerformance:
    """One movement (``stem`` like ``kv331_1``); see :func:`iter_aligned`."""
    path = Path(root) / "match" / f"{stem}.match"
    if not path.is_file():
        raise FileNotFoundError(path)
    ap = _load_match(path)
    if musicxml_score:
        ap = AlignedPerformance(ap.performance, performed_score(ap.score, root=root), ap.alignment)
    return ap


def stem_of(score_or_id: Any) -> str:
    """Movement stem (``kv331_1``) of a Batik ``Score`` / score id / performance id."""
    sid = getattr(score_or_id, "score_id", score_or_id)
    return str(sid).split(":")[-1]


def _unfold_like(part: Any, ids: set[str], n_candidates: int = 4
                 ) -> tuple[float, float, str, Any]:
    """(id coverage, id Jaccard, variant string, unfolded part) of the repeat path whose note
    ids best match ``ids`` (coverage = share of ``ids`` present, then Jaccard), among the
    ``n_candidates`` paths whose note counts are closest to ``len(ids)``."""
    from pianolens.align.core import _build, _variants_with_paths

    variants = _variants_with_paths(part)
    closest = sorted(variants, key=lambda t: abs(t[1] - len(ids)))[:n_candidates]
    best: tuple[float, float, str, Any] | None = None
    for v, _, p in closest:
        up = _build(part, p, len(variants))
        u = set(up.note_array(include_grace_notes=True)["id"].astype(str))
        cov = len(u & ids) / len(ids) if ids else 0.0
        j = len(u & ids) / len(u | ids) if u | ids else 0.0
        if best is None or (cov, j) > best[:2]:
            best = (cov, j, v, up)
    assert best is not None
    return best


def performed_score(match_score: Score, root: Path | str = DEFAULT_ROOT, *,
                    edited: bool = True) -> Score:
    """The MusicXML-based performed score of a Batik movement, with markings.

    ``match_score`` is the score of a loaded Batik performance (its note ids define the repeat
    path the pianist took). The MusicXML (``scores_edited`` by default, ``scores`` with
    ``edited=False``: same ids, more repeat paths, slower) is merged and unfolded to the path
    whose note ids best match. ``part`` is kept; ``meta`` gets ``unfolded`` (path string),
    ``id_coverage`` (share of match-score ids present: 1.0 for all 36 movements, so every
    alignment id resolves), ``id_jaccard`` (1.0 except kv281_3, 0.9996: the MusicXML has one
    note, ``n636-1``, that the match score lacks) and ``score_source``. Logs a warning when
    the coverage is below 1.
    """
    from pianolens.align.core import _raise_recursion_limit, load_score_part

    _raise_recursion_limit()
    stem = stem_of(match_score)
    folder = "scores_edited" if edited else "scores"
    path = Path(root) / folder / f"{stem}.musicxml"
    part = load_score_part(path)
    cov, j, v, up = _unfold_like(part, set(match_score.notes["id"].astype(str)))
    if cov < 1.0:
        log.warning("batik %s: only %.4f of the match-score ids are in the MusicXML", stem, cov)
    return score_from_partitura(
        up, score_id=match_score.score_id, piece_id=match_score.piece_id, source_path=path,
        meta={"unfolded": v, "id_coverage": cov, "id_jaccard": j,
              "score_source": "musicxml_edited" if edited else "musicxml"},
        keep_part=True)


PHRASE_LABELS = {"{": (True, False), "}": (False, True), "}{": (True, True)}


@dataclass
class PhraseAnnotations:
    """DCML phrase and cadence labels of one movement, in a performed score's beats.

    Attributes:
        phrases: one row per labelled onset: ``id`` (score note id), ``beat`` (performed
            score ``onset_beat``), ``quarter``, ``measure_number``, ``label`` (``{`` / ``}`` /
            ``}{``), ``is_start``, ``is_end``.
        cadences: ``id``, ``beat``, ``quarter``, ``measure_number``, ``cadence`` (PAC, IAC,
            HC, EC, DC).
        n_unmapped: labels whose id is not in the score (0 for every Batik movement).
    """

    phrases: pd.DataFrame
    cadences: pd.DataFrame
    n_unmapped: int = 0

    @property
    def starts(self) -> list[float]:
        """Sorted distinct phrase-start beats (``{`` and ``}{``)."""
        return sorted(set(self.phrases.loc[self.phrases["is_start"], "beat"].astype(float)))

    @property
    def ends(self) -> list[float]:
        """Sorted distinct phrase-end beats (``}`` and ``}{``: the cadential arrivals)."""
        return sorted(set(self.phrases.loc[self.phrases["is_end"], "beat"].astype(float)))

    def cadence_table(self) -> pd.DataFrame:
        """``beat``, ``cadence`` (distinct, sorted): the ``cadences`` argument of
        ``pianolens.features.score_basis``."""
        return (self.cadences[["beat", "cadence"]].drop_duplicates().sort_values("beat")
                .reset_index(drop=True))


def phrase_annotations(score: Score, root: Path | str = DEFAULT_ROOT) -> PhraseAnnotations:
    """Phrase and cadence tables of a Batik movement mapped to ``score``'s beats (module
    docstring). ``score`` is either the match-built or the MusicXML performed score."""
    stem = stem_of(score)
    na = score.notes
    nm = score.note_measures()
    lut = pd.DataFrame({"id": na["id"].astype(str), "beat": na["onset_beat"].astype(float),
                        "quarter": na["onset_quarter"].astype(float),
                        "measure_number": nm}).drop_duplicates("id").set_index("id")
    unmapped = 0

    def mapped(df: pd.DataFrame, col: str) -> pd.DataFrame:
        nonlocal unmapped
        df = df[df[col].notna()][["id", col]].copy()
        df["id"] = df["id"].astype(str)
        ok = df["id"].isin(lut.index)
        unmapped += int((~ok).sum())
        df = df[ok]
        df = df.join(lut, on="id")
        return df.sort_values(["beat", "id"]).reset_index(drop=True)

    ph = mapped(load_note_annotations(stem, "phrases", root), "phraseend")
    ph = ph.rename(columns={"phraseend": "label"})
    ph["label"] = ph["label"].astype(str).str.strip()
    ph = ph[ph["label"].isin(PHRASE_LABELS)].reset_index(drop=True)
    ph["is_start"] = ph["label"].map(lambda x: PHRASE_LABELS[x][0]).astype(bool)
    ph["is_end"] = ph["label"].map(lambda x: PHRASE_LABELS[x][1]).astype(bool)
    ca = mapped(load_note_annotations(stem, "cadence", root), "cadence")
    ca["cadence"] = ca["cadence"].astype(str).str.strip()
    cols_p = ["id", "beat", "quarter", "measure_number", "label", "is_start", "is_end"]
    cols_c = ["id", "beat", "quarter", "measure_number", "cadence"]
    return PhraseAnnotations(ph[cols_p], ca[cols_c], unmapped)
