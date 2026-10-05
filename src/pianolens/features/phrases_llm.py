"""Cached LLM phrase boundaries per piece (DF-02; protocol R-08a-d, validation F-05e).

Phrase boundaries marked by a language model (Claude) reading a label-free text rendering of the
score, produced once per piece by ``scripts/build_llm_phrases.py`` with the R-08 protocol: R-08a's
renderer, R-08d's instructions (no period cue), one blind annotator per piece per run, two runs.
F-05e (``docs/specs/phrase-coherence-validation.md``, DECISIONS 2026-09-28) found that per-phrase
tempo shaping (``concave_excess``) with these boundaries recovers the DCML-annotation level on
Classical sonatas and beats the cadence detector on Romantic pieces without reaching the DCML
level there. Consumers must report the phrase-count ratio next to ``concave_excess`` and the
Romantic caveat where it applies.

Cache file: ``<root>/<safe piece id>.json`` (:func:`cache_path`), ``root`` =
``$PIANOLENS_PHRASES_LLM_DIR`` or ``data/interim/phrases_llm``. Contents (schema
``pianolens.phrases_llm/1``):

* ``piece_id``;
* ``provenance``: ``model``, ``date``, ``protocol``, ``score_file``, ``score_sha256`` (bytes of the
  score file), ``score_hash`` (:func:`score_hash` of the rendered, unfolded score),
  ``edition_hash`` (:func:`edition_hash`), ``style`` (``classical`` / ``romantic`` / ...),
  ``meters``, plus free fields (agent ids, rendering and instruction hashes, recognition);
* ``runs``: one entry per independent annotator run: ``run``, ``starts`` and ``ends`` (score beats
  of the rendered score, partitura units: time-signature denominator), ``start_anchors`` /
  ``end_anchors`` (per boundary: ``beat``, ``note_ids`` = base note ids sounding from that onset,
  ``repeat`` = repeat index), ``map_stats``.

Loading onto a score (:func:`resolve_llm_phrases`): the boundaries are used as stored when the
score's :func:`score_hash` equals the cached one; when only the edition matches (same notes, a
different repeat path), each boundary is moved onto every onset of the target that starts one
of its anchor notes (all repeats of a passage share its phrase structure); otherwise nothing is
returned and the reason says why, so callers can fall back and disclose it.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

__all__ = ["CACHE_ENV", "CACHE_SCHEMA", "LLMPhraseRun", "LLMPhraseSet", "cache_path",
           "default_root", "edition_hash", "load_cache", "resolve_llm_phrases", "score_hash",
           "write_cache"]

CACHE_SCHEMA = "pianolens.phrases_llm/1"
CACHE_ENV = "PIANOLENS_PHRASES_LLM_DIR"
_REPO = Path(__file__).resolve().parents[3]
_EPS = 1e-4
_SUFFIX = re.compile(r"-(\d+)$")
REQUIRED_PROVENANCE = ("model", "date", "protocol", "score_hash", "edition_hash")


def default_root() -> Path:
    """``$PIANOLENS_PHRASES_LLM_DIR`` if set, else ``<repo>/data/interim/phrases_llm``."""
    env = os.environ.get(CACHE_ENV)
    return Path(env) if env else _REPO / "data" / "interim" / "phrases_llm"


def cache_path(piece_id: str, root: Path | str | None = None) -> Path:
    """File of one piece: the piece id made file-safe plus a short hash of the exact id."""
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", str(piece_id)).strip("_")[:120]
    h = hashlib.sha1(str(piece_id).encode()).hexdigest()[:10]
    return Path(root if root is not None else default_root()) / f"{safe}-{h}.json"


def _base(note_id: str) -> tuple[str, int]:
    m = _SUFFIX.search(note_id)
    return (note_id[: m.start()], int(m.group(1))) if m else (note_id, 0)


def _non_grace(score: Any) -> np.ndarray:
    na = score.notes
    names = na.dtype.names or ()
    return na[~na["is_grace"].astype(bool)] if "is_grace" in names else na


def score_hash(score: Any) -> str:
    """sha256 of the exact score variant: every (note id, onset beat, pitch), sorted."""
    na = score.notes
    rows = sorted((str(i), round(float(b), 4), int(p))
                  for i, b, p in zip(na["id"], na["onset_beat"], na["pitch"], strict=True))
    return hashlib.sha256(json.dumps(rows).encode()).hexdigest()


def edition_hash(score: Any) -> str:
    """sha256 of the written notes, independent of the repeat path: the set of (base note id,
    pitch), with partitura's repeat suffix (``-1``, ``-2``) removed."""
    na = score.notes
    rows = sorted({(_base(str(i))[0], int(p)) for i, p in zip(na["id"], na["pitch"],
                                                               strict=True)})
    return hashlib.sha256(json.dumps(rows).encode()).hexdigest()


def anchors(score: Any, beats: Sequence[float]) -> list[dict[str, Any]]:
    """Per boundary beat: the base ids of the non-grace notes starting there (empty if the
    boundary is not on an onset) and their repeat index."""
    na = _non_grace(score)
    ob = na["onset_beat"].astype(float)
    out = []
    for x in beats:
        on = np.abs(ob - float(x)) <= _EPS
        ids = [_base(str(i)) for i in na["id"][on]]
        out.append({"beat": float(x), "note_ids": sorted({b for b, _ in ids}),
                    "repeat": int(max((r for _, r in ids), default=0))})
    return out


@dataclass
class LLMPhraseRun:
    """One annotator run on the target score: phrase ``starts`` and ``ends`` in score beats."""

    run: str
    starts: list[float]
    ends: list[float]
    n_unmapped: int = 0


@dataclass
class LLMPhraseSet:
    """LLM phrase boundaries resolved onto one score.

    Attributes:
        piece_id: the cache's piece id.
        provenance: the cache's provenance block (model, date, protocol, hashes, style, ...).
        runs: one :class:`LLMPhraseRun` per annotator run, in cache order.
        mapping: ``exact`` (same score variant) or ``note_ids`` (same edition, other repeat
            path; boundaries moved by anchor notes).
        path: the cache file.
    """

    piece_id: str
    provenance: dict[str, Any]
    runs: list[LLMPhraseRun]
    mapping: str
    path: Path | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def style(self) -> str:
        return str(self.provenance.get("style", "unknown"))


def write_cache(piece_id: str, provenance: dict[str, Any], runs: Sequence[dict[str, Any]],
                root: Path | str | None = None) -> Path:
    """Validate and write one piece's cache; returns the path. Each run needs ``run``,
    ``starts``, ``ends`` (and should have ``start_anchors`` / ``end_anchors``)."""
    missing = [k for k in REQUIRED_PROVENANCE if not provenance.get(k)]
    if missing:
        raise ValueError(f"provenance lacks {missing}")
    if not runs:
        raise ValueError("no runs")
    for r in runs:
        for k in ("run", "starts", "ends"):
            if k not in r:
                raise ValueError(f"run lacks {k!r}")
    doc = {"schema": CACHE_SCHEMA, "piece_id": str(piece_id), "provenance": dict(provenance),
           "runs": [dict(r) for r in runs]}
    p = cache_path(piece_id, root)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n")
    return p


def load_cache(piece_id: str, root: Path | str | None = None) -> tuple[dict | None, str]:
    """The raw cache document of ``piece_id`` and ``""``, or ``None`` and the reason."""
    p = cache_path(piece_id, root)
    if not p.exists():
        return None, "no LLM phrase cache for this piece"
    try:
        doc = json.loads(p.read_text())
    except (OSError, ValueError) as e:
        return None, f"LLM phrase cache unreadable ({type(e).__name__})"
    if doc.get("schema") != CACHE_SCHEMA:
        return None, f"LLM phrase cache has schema {doc.get('schema')!r}, not {CACHE_SCHEMA!r}"
    if str(doc.get("piece_id")) != str(piece_id):
        return None, "LLM phrase cache belongs to another piece id"
    prov = doc.get("provenance") or {}
    missing = [k for k in REQUIRED_PROVENANCE if not prov.get(k)]
    if missing:
        return None, f"LLM phrase cache provenance lacks {missing}"
    if not doc.get("runs"):
        return None, "LLM phrase cache has no runs"
    return doc, ""


def _map_anchor(anc: dict[str, Any], by_base: dict[str, np.ndarray]) -> list[float]:
    """Target onsets that start any of the anchor's notes (every repeat of them)."""
    hits: set[float] = set()
    for b in anc.get("note_ids") or ():
        for x in by_base.get(str(b), ()):
            hits.add(round(float(x), 6))
    return sorted(hits)


def resolve_llm_phrases(score: Any, piece_id: str | None = None,
                        root: Path | str | None = None) -> tuple[LLMPhraseSet | None, str]:
    """LLM phrase boundaries for ``score`` (a performed, unfolded ``Score``) from the cache.

    Args:
        score: the score the boundaries are wanted on; its ``piece_id`` finds the cache.
        piece_id: overrides ``score.piece_id``.
        root: cache folder (default :func:`default_root`).

    Returns:
        ``(LLMPhraseSet, "")`` or ``(None, reason)``; the reason is written for a report reader.
    """
    pid = str(piece_id if piece_id is not None else getattr(score, "piece_id", "") or "")
    if not pid:
        return None, "score has no piece id"
    doc, why = load_cache(pid, root)
    if doc is None:
        return None, why
    prov = doc["provenance"]
    if score_hash(score) == prov["score_hash"]:
        mapping = "exact"
        runs = [LLMPhraseRun(str(r["run"]), sorted(float(x) for x in r["starts"]),
                             sorted(float(x) for x in r["ends"])) for r in doc["runs"]]
    elif edition_hash(score) == prov["edition_hash"]:
        mapping = "note_ids"
        na = _non_grace(score)
        by_base: dict[str, list[float]] = {}
        for i, b in zip(na["id"], na["onset_beat"], strict=True):
            by_base.setdefault(_base(str(i))[0], []).append(float(b))
        bb = {k: np.asarray(v) for k, v in by_base.items()}
        runs = []
        for r in doc["runs"]:
            out: dict[str, list[float]] = {}
            lost = 0
            for kind in ("start", "end"):
                xs: set[float] = set()
                for a in r.get(f"{kind}_anchors") or ():
                    m = _map_anchor(a, bb)
                    lost += int(not m)
                    xs.update(m)
                out[kind] = sorted(xs)
            runs.append(LLMPhraseRun(str(r["run"]), out["start"], out["end"], lost))
    else:
        return None, ("the score differs from the one the LLM annotated (edition hash "
                      "mismatch)")
    runs = [r for r in runs if r.starts]
    if not runs:
        return None, "no LLM phrase starts map onto this score"
    return LLMPhraseSet(pid, dict(prov), runs, mapping, cache_path(pid, root)), ""
