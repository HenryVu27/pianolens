"""DCML J. C. Bach keyboard sonatas: label-free scores plus phrase and cadence tables (D-12).

Source: https://github.com/DCMLab/jc_bach_sonatas (v2.4, commit ``COMMIT``) under
``data/raw/dcml_jc_bach``, license CC BY-NC-SA 4.0. Op. 5 and op. 17: 12 sonatas, 29
movements. Score-only corpus: no performances.

Thin wrapper around the shared DCML loader :mod:`pianolens.data.dcml` (D-13), which documents
the label-free score path and the phrase and cadence tables. The D-12 API and its outputs are
unchanged: the score is built from ``notes/``, ``measures/`` and ``chords/`` only; the
movement title of ``metadata.tsv`` (e.g. "Allegretto") is the tempo word at the first onset
(``tempo_word=False`` drops it); hairpins and ``crescendo_line`` rows are not read; no
fermatas, derived rests, no key mode. Unfolding follows ``next`` and equals ``metadata.tsv``
for all 29 movements (tested). :func:`phrase_annotations` returns a
``batik_mozart.PhraseAnnotations``; the three ``\\\\`` labels of the corpus are dropped
(``n_other``). Cadences: PAC, IAC, HC, EC, DC, PC.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pandas as pd

from pianolens.data import dcml
from pianolens.data.dcml import (
    CADENCE_TYPES,
    LABEL_FACETS,
    LABEL_FREE_FACETS,
    LABEL_TEXT_COLUMNS,
    LICENSE,
    DcmlPhraseAnnotations,
    LoadStats,
    _frac,
    _linear_notes,
    _Note,
    _Pass,
    _passes,
    _spelling,
    playthrough,
    stem_of,
)
from pianolens.data.types import PieceId, Score

__all__ = [
    "CADENCE_TYPES", "COMMIT", "CORPUS", "DATASET", "DEFAULT_ROOT", "LABEL_FACETS",
    "LABEL_FREE_FACETS", "LABEL_TEXT_COLUMNS", "LICENSE", "DcmlPhraseAnnotations", "LoadStats",
    "_Note", "_Pass", "_frac", "_linear_notes", "_passes", "_read_label_free", "_spelling",
    "data_available", "iter_scores", "label_strings", "load_labels", "load_score", "metadata",
    "phrase_annotations", "piece_id", "pieces", "playthrough", "read_facet", "stem_of",
]  # fmt: skip

CORPUS = dcml.CORPORA["jc_bach"]
DATASET = CORPUS.dataset
DEFAULT_ROOT = CORPUS.root
COMMIT = CORPUS.commit  # tag v2.4, 2025-04-27


def data_available(root: Path | str = DEFAULT_ROOT) -> bool:
    return dcml.data_available(CORPUS, root)


def metadata(root: Path | str = DEFAULT_ROOT) -> pd.DataFrame:
    return dcml.metadata(CORPUS, root)


def pieces(root: Path | str = DEFAULT_ROOT) -> list[str]:
    """Movement stems, e.g. ``wa01op05no1a_Allegretto`` (29)."""
    return dcml.pieces(CORPUS, root)


def piece_id(stem: str) -> PieceId:
    """``wa02op05no2b_Andante_di_molto`` -> ``jcbach_op5_no2_mv2``."""
    return CORPUS.id_fn(stem)


def read_facet(stem: str, facet: str, root: Path | str = DEFAULT_ROOT) -> pd.DataFrame:
    return dcml.read_facet(CORPUS, stem, facet, root)


def _read_label_free(stem: str, facet: str, root: Path | str, used: list[str]) -> pd.DataFrame:
    return dcml._read_label_free(CORPUS, stem, facet, root, used)


def load_score(stem: str, root: Path | str = DEFAULT_ROOT, *, unfold: bool = True,
               tempo_word: bool = True) -> Score:
    """Label-free score of one movement (see :func:`pianolens.data.dcml.load_score`)."""
    return dcml.load_score(CORPUS, stem, root, unfold=unfold, tempo_word=tempo_word)


def iter_scores(root: Path | str = DEFAULT_ROOT, stats: LoadStats | None = None, *,
                unfold: bool = True) -> Iterator[Score]:
    return dcml.iter_scores(CORPUS, root, stats, unfold=unfold)


def load_labels(stem: str, root: Path | str = DEFAULT_ROOT) -> pd.DataFrame:
    """The DCML label table (``harmonies/``). Never pass this to a renderer."""
    return dcml.load_labels(CORPUS, stem, root)


def label_strings(stem: str, root: Path | str = DEFAULT_ROOT, min_len: int = 1) -> set[str]:
    """Distinct label-text values of the movement (for leakage checks)."""
    return dcml.label_strings(CORPUS, stem, root, min_len)


def phrase_annotations(score: Score, root: Path | str = DEFAULT_ROOT) -> DcmlPhraseAnnotations:
    """Phrase and cadence tables of ``score`` in its beats (see
    :func:`pianolens.data.dcml.phrase_annotations`)."""
    return dcml.phrase_annotations(score, root, corpus=CORPUS)
