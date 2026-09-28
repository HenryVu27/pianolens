"""PSyllabus loader: 7,901 piano pieces with syllabus difficulty levels (0-10) and MIDI.

Source: Zenodo 14794592 (Ramoneda et al., IEEE TASLP 2025) under ``data/raw/psyllabus``:
``new_clean_data.json`` (labels, keyed by "<Composer>.<Title>"), ``split_audio.json``
(5 folds, each train / validation / test) and ``mid.zip`` extracted to ``extracted/mid``.
The large ``cqt5.zip`` (2 GB) is not downloaded. The MIDI is transcribed from the YouTube
recordings (provenance ``transcribed``); each file is one recording of one piece.

Used here as the open substitute for CIPI, whose Zenodo record (8037327) is access-restricted.
Difficulty is a property of the piece, not a rating of the performance, so it lives in
``Performance.meta["difficulty"]`` and in ``psyllabus_index``, not in ``Ratings``.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from pianolens.data.midi_io import performance_from_midi
from pianolens.data.piece_ids import prefixed_piece_id
from pianolens.data.types import Performance, PerformerId

log = logging.getLogger(__name__)

DATASET = "psyllabus"
DEFAULT_ROOT = Path(__file__).resolve().parents[3] / "data" / "raw" / "psyllabus"


def data_available(root: Path | str = DEFAULT_ROOT) -> bool:
    root = Path(root)
    return (root / "new_clean_data.json").is_file() and (root / "extracted" / "mid").is_dir()


def psyllabus_index(root: Path | str = DEFAULT_ROOT, fold: int = 0) -> pd.DataFrame:
    """One row per piece: key, composer, title, difficulty (int 0-10), syllabus, split."""
    root = Path(root)
    labels = json.loads((root / "new_clean_data.json").read_text())
    splits = json.loads((root / "split_audio.json").read_text())[str(fold)]
    split_of = {k: s for s, keys in splits.items() for k in keys}
    rows = [
        {
            "key": k,
            "composer": v.get("composer"),
            "title": v.get("PS_title"),
            "difficulty": int(v["ps"]),
            "syllabus": v.get("syllabus"),
            "period": v.get("period"),
            "youtube_link": v.get("youtube_link"),
            "split": split_of.get(k),
        }
        for k, v in labels.items()
    ]
    return pd.DataFrame(rows)


@dataclass
class PsyllabusStats:
    loaded: int = 0
    failed: int = 0
    missing_midi: int = 0
    failures: list[tuple[str, str]] = field(default_factory=list)


def iter_performances(
    root: Path | str = DEFAULT_ROOT,
    fold: int = 0,
    limit: int | None = None,
    stats: PsyllabusStats | None = None,
) -> Iterator[Performance]:
    root = Path(root)
    stats = stats if stats is not None else PsyllabusStats()
    idx = psyllabus_index(root, fold)
    for r in (idx.head(limit) if limit else idx).itertuples():
        path = root / "extracted" / "mid" / f"{r.key}.mid"
        if not path.is_file():
            stats.missing_midi += 1
            continue
        try:
            yield performance_from_midi(
                path,
                dataset=DATASET,
                performance_id=f"{DATASET}:{r.key}",
                piece_id=prefixed_piece_id(DATASET, r.key),
                performer_id=PerformerId(f"{DATASET}:unknown/{r.key}"),
                provenance="transcribed",
                meta={"difficulty": r.difficulty, "syllabus": r.syllabus, "split": r.split,
                      "composer": r.composer, "title": r.title},
            )  # fmt: skip
            stats.loaded += 1
        except Exception as e:  # noqa: BLE001 - count and continue
            stats.failed += 1
            stats.failures.append((r.key, repr(e)))
            log.warning("psyllabus %s failed: %r", r.key, e)
