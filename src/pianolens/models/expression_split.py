"""Piece-disjoint train / validation / test splits for expression-model training (R-07).

The unit of the split is the *work*: all movements of a sonata, a prelude with its fugue, and all
pieces that share a canonical piece id go to the same side. Assignment is made per work and then
expanded to every canonical piece id of that work (``pianolens.data.piece_ids`` ids, shared across
datasets). Three safeguards:

* :func:`work_key` groups movements of one work (``beethoven_op27_no2_mv1`` ->
  ``beethoven_op27_no2``; ``bach_bwv846_prelude`` -> ``bach_bwv846``).
* :func:`alias_conflicts` finds pieces whose ids differ but whose composer and catalogue numbers
  say they may be the same music (PianoCoRe keeps some ids prefixed, e.g. global nocturne
  numbers). Such pieces are *quarantined*: used neither for training nor for evaluation.
* :func:`leakage_check` verifies that every piece used for training is assigned ``train`` and
  that no held-out work reaches the training set. It raises on any violation.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

import numpy as np
import pandas as pd

__all__ = [
    "SPLITS",
    "LeakageError",
    "alias_conflicts",
    "assign_split",
    "catalogue_tokens",
    "composer_surname",
    "leakage_check",
    "work_key",
]

SPLITS = ("train", "val", "test", "quarantine")

_CANON_SUFFIX = re.compile(r"_(mv\d+(?:to\d+)?|prelude|fugue)$")
_ASAP_MOVEMENT = re.compile(r"(_\d+)-\d+$")  # asap:Haydn/Keyboard_Sonatas_48-2 -> ..._48
_MULTI_MOVEMENT = re.compile(r"Sonat|Concert|Suite|Partita|Symphon|Fantasie_in", re.I)
_CAT = re.compile(
    r"(?<![A-Za-z])(op|bwv|k|d|s|l|woo|hob)\.?[\s_.]*((?:[ivxlc]+[:.]?[\s_]*)?\d+[a-z]?)", re.I
)
_NO = re.compile(r"(?<![A-Za-z])no\.?[\s_]*(\d+)", re.I)
# a catalogue range such as "BWV_846-869" names a collection, not a piece
_RANGE = re.compile(r"(?<![A-Za-z])(op|bwv|k|d|s|l|woo)\.?[\s_.]*\d+[a-z]?[\s_]*-[\s_]*\d+", re.I)


def _fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def work_key(piece_id: str, composition: str | None = None) -> str:
    """Group key of the work a piece belongs to.

    Canonical ids drop a trailing movement / prelude / fugue suffix. ``pianocore:`` ids
    (``pianocore:<composer>/<composition>/<movement>``) keep only composer and composition when
    the composition is a multi-movement form (sonata, suite, concerto, partita, ...); otherwise
    each movement string is its own work (sets such as Préludes or Lyric Pieces).
    ``asap:`` ids drop a trailing ``-<movement>``.
    """
    if piece_id.startswith("pianocore:"):
        parts = piece_id.split(":", 1)[1].split("/")
        comp = composition if composition is not None else (parts[1] if len(parts) > 1 else "")
        if len(parts) >= 3 and _MULTI_MOVEMENT.search(comp or ""):
            return "pianocore:" + "/".join(parts[:2])
        return piece_id
    if piece_id.startswith("asap:"):
        return _ASAP_MOVEMENT.sub(r"\1", piece_id)
    if ":" in piece_id:
        return piece_id
    return _CANON_SUFFIX.sub("", piece_id)


def composer_surname(composer: str) -> str:
    """``"Chopin,_Frédéric"`` / ``"Chopin"`` / ``"Frederic_Chopin"`` -> ``"chopin"``."""
    c = _fold(str(composer)).replace("_", " ").strip()
    if "," in c:
        return c.split(",")[0].strip().split()[-1]
    return c.split()[-1] if c.split() else ""


def catalogue_tokens(text: str) -> frozenset[str]:
    """Catalogue numbers (``op10``, ``bwv846``, ``k331``, ``d960``, ``hobxvi34``) and ``no<n>``
    tokens found in a title string."""
    t = _RANGE.sub(" ", _fold(str(text)))
    toks = {m.group(1) + re.sub(r"[\s_.:]", "", m.group(2)) for m in _CAT.finditer(t)}
    toks |= {"no" + m.group(1) for m in _NO.finditer(t)}
    return frozenset(toks)


def alias_conflicts(held: pd.DataFrame, cand: pd.DataFrame) -> pd.DataFrame:
    """Candidate pieces that may be the same music as a held-out piece under another id.

    Both frames need ``piece_id``, ``composer`` and ``text`` (composition + movement title).
    A pair conflicts when the surnames match, they share at least one catalogue token (not a bare
    ``no<n>``), and one token set contains the other. Returns rows ``(piece_id, held_piece_id)``.
    """
    def prep(df: pd.DataFrame) -> pd.DataFrame:
        out = df[["piece_id"]].copy()
        out["surname"] = df["composer"].map(composer_surname)
        out["toks"] = df["text"].map(catalogue_tokens)
        out["cat"] = out["toks"].map(lambda s: frozenset(x for x in s if not x.startswith("no")))
        return out[out["cat"].map(len) > 0]

    h, c = prep(held), prep(cand)
    rows = []
    for sur, hg in h.groupby("surname"):
        cg = c[c["surname"] == sur]
        if cg.empty:
            continue
        for hp, ht, hc in hg[["piece_id", "toks", "cat"]].itertuples(index=False):
            for cp, ctok, cc in cg[["piece_id", "toks", "cat"]].itertuples(index=False):
                if cp == hp or not (hc & cc):
                    continue
                if ht <= ctok or ctok <= ht:
                    rows.append((cp, hp))
    return pd.DataFrame(rows, columns=["piece_id", "held_piece_id"]).drop_duplicates()


def assign_split(pieces: pd.DataFrame, forced: dict[str, str], val_frac: float,
                 seed: int, val_pool: set[str] | None = None) -> pd.Series:
    """Assign every piece to ``train`` / ``val`` / ``test`` by work.

    Args:
        pieces: one row per piece id with columns ``piece_id`` and ``work``.
        forced: ``{work: "test" | "val"}`` for works fixed in advance.
        val_frac: share of the remaining works drawn (seeded, uniformly) into ``val``.
        seed: numpy seed for the validation draw.
        val_pool: if given, only these works can be drawn into ``val`` (``val_frac`` applies
            to the free works in the pool); the rest go to ``train``.

    Returns:
        ``pd.Series`` indexed by piece id.
    """
    works = sorted(set(pieces["work"]))
    side = {w: forced[w] for w in works if w in forced}
    free = [w for w in works if w not in side]
    pool = [w for w in free if val_pool is None or w in val_pool]
    rng = np.random.default_rng(seed)
    n_val = int(round(val_frac * len(pool)))
    val: set[str] = set()
    if n_val:
        val = set(rng.choice(np.array(pool, dtype=object), size=n_val, replace=False))
    for w in free:
        side[w] = "val" if w in val else "train"
    return pd.Series([side[w] for w in pieces["work"]], index=pieces["piece_id"].to_numpy(),
                     name="split")


class LeakageError(RuntimeError):
    """A held-out piece or work would be used for training."""


@dataclass
class LeakageReport:
    n_used: int
    n_pieces: int
    unknown: list[str]
    not_train: list[str]
    held_work_in_train: list[str]

    @property
    def ok(self) -> bool:
        return not (self.unknown or self.not_train or self.held_work_in_train)

    def as_dict(self) -> dict:
        return {"ok": self.ok, "n_used_rows": self.n_used, "n_train_pieces": self.n_pieces,
                "unknown_piece_ids": self.unknown, "held_out_piece_ids_in_train": self.not_train,
                "held_out_works_in_train": self.held_work_in_train}


def leakage_check(split: pd.DataFrame, train_piece_ids: pd.Series | list[str],
                  raise_on_error: bool = True) -> LeakageReport:
    """Check that training rows use only ``train`` pieces and no held-out work.

    Args:
        split: the split table (columns ``piece_id``, ``work``, ``split``).
        train_piece_ids: piece id of every training row (one entry per performance).
    """
    ids = pd.Series(list(train_piece_ids), dtype=object)
    by_piece = split.set_index("piece_id")
    uniq = sorted(set(ids))
    unknown = [p for p in uniq if p not in by_piece.index]
    known = [p for p in uniq if p in by_piece.index]
    not_train = [p for p in known if by_piece.at[p, "split"] != "train"]
    held_works = set(split.loc[split["split"] != "train", "work"])
    held_work_in_train = sorted({by_piece.at[p, "work"] for p in known} & held_works)
    rep = LeakageReport(len(ids), len(uniq), unknown, not_train, held_work_in_train)
    if raise_on_error and not rep.ok:
        raise LeakageError(str(rep.as_dict()))
    return rep
