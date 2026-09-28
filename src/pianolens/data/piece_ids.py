"""Canonical piece ids shared across datasets.

Format: ``<composer>_<catalogue>[_no<n>][_<movement>]``, lowercase ASCII, for example
``chopin_op10_no3``, ``bach_bwv846_fugue``, ``beethoven_op31_no2_mv1``, ``mozart_k331_mv3``.

* ``catalogue`` is the catalogue prefix plus number with no separator: ``op10``, ``bwv846``,
  ``k331``, ``d899``, ``s139``, ``hobxvi48``.
* ``movement`` is ``mv<k>`` for numbered movements, or a word for named parts of a pair
  (``prelude`` / ``fugue``).
* Accented letters are folded to ASCII first (``Dvořák`` -> ``dvorak``), then anything that is
  not a lowercase letter or digit is dropped.
* Items with no confident catalogue match keep a dataset-prefixed id, e.g.
  ``asap:Haydn/Keyboard_Sonatas_31-1``. Never guess a catalogue number.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import pandas as pd

from pianolens.data.types import PieceId

PIECE_ID_TABLE = Path(__file__).resolve().parents[3] / "data" / "processed" / "piece_ids.parquet"
"""Cross-dataset mapping built by ``scripts/build_piece_ids.py``."""
PIECE_ID_COLUMNS: tuple[str, ...] = (
    "dataset", "source_key", "piece_id", "canonical", "composer", "title", "movement",
    "n_performances", "n_tier_a",
)  # fmt: skip

_SLUG = re.compile(r"[^a-z0-9]+")


def fold_accents(s: str) -> str:
    """ASCII-fold ``s`` via Unicode NFKD: ``"Dvořák"`` -> ``"Dvorak"``, ``"Für"`` -> ``"Fur"``.

    Characters with no ASCII decomposition (e.g. ``ß``, ``ø``) are dropped."""
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")


def _slug(s: str) -> str:
    return _SLUG.sub("", fold_accents(s).lower())


def make_piece_id(
    composer: str,
    catalogue: str,
    number: int | str | None = None,
    movement: int | str | None = None,
) -> PieceId:
    """Build a canonical ``PieceId``.

    Args:
        composer: surname, e.g. ``"Chopin"``.
        catalogue: catalogue prefix + number, e.g. ``"op10"``, ``"BWV 846"``, ``"K.331"``.
        number: number within an opus (``op10 no3``), if any.
        movement: movement number (becomes ``mv<k>``) or a movement word (``fugue``).
    """
    parts = [_slug(composer), _slug(catalogue)]
    if not parts[0] or not parts[1]:
        raise ValueError("composer and catalogue are required")
    if number is not None and str(number) != "":
        parts.append(f"no{_slug(str(number))}")
    if movement is not None and str(movement) != "":
        mv = str(movement)
        parts.append(f"mv{int(mv)}" if mv.isdigit() else _slug(mv))
    return PieceId("_".join(parts))


def prefixed_piece_id(dataset: str, local_id: str) -> PieceId:
    """Fallback id for items without a canonical match."""
    return PieceId(f"{dataset}:{local_id}")


def load_piece_id_table(path: Path | str = PIECE_ID_TABLE) -> pd.DataFrame:
    """The cross-dataset piece-id table: one row per (dataset, source_key) with the
    ``PieceId`` the loader assigns (columns ``PIECE_ID_COLUMNS``). ``canonical`` is False for
    dataset-prefixed ids."""
    return pd.read_parquet(path)


def datasets_by_piece(table: pd.DataFrame | None = None) -> pd.Series:
    """Canonical piece id -> sorted tuple of datasets that contain it."""
    t = load_piece_id_table() if table is None else table
    t = t[t["canonical"]]
    return t.groupby("piece_id")["dataset"].agg(lambda s: tuple(sorted(set(s))))


# Beethoven piano sonata number -> (opus, number within opus). Standard numbering 1-32.
BEETHOVEN_SONATA_OPUS: dict[int, tuple[str, int | None]] = {
    1: ("op2", 1), 2: ("op2", 2), 3: ("op2", 3), 4: ("op7", None),
    5: ("op10", 1), 6: ("op10", 2), 7: ("op10", 3), 8: ("op13", None),
    9: ("op14", 1), 10: ("op14", 2), 11: ("op22", None), 12: ("op26", None),
    13: ("op27", 1), 14: ("op27", 2), 15: ("op28", None), 16: ("op31", 1),
    17: ("op31", 2), 18: ("op31", 3), 19: ("op49", 1), 20: ("op49", 2),
    21: ("op53", None), 22: ("op54", None), 23: ("op57", None), 24: ("op78", None),
    25: ("op79", None), 26: ("op81a", None), 27: ("op90", None), 28: ("op101", None),
    29: ("op106", None), 30: ("op109", None), 31: ("op110", None), 32: ("op111", None),
}  # fmt: skip

# Mozart piano sonata number (standard 1-18 numbering) -> Koechel number, only those in use.
MOZART_SONATA_K: dict[int, str] = {8: "k310", 11: "k331", 12: "k332"}
