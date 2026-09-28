"""MAESTRO v3.0.0 loader, MIDI only (no audio on this Mac).

Source: https://magenta.tensorflow.org/datasets/maestro, ``maestro-v3.0.0-midi.zip``
extracted under ``data/raw/maestro_v3_midi``. License CC BY-NC-SA 4.0. Disklavier MIDI from
the International Piano-e-Competition. MAESTRO publishes no performer names, so every
performance gets its own ``maestro_v3:unknown/<file>`` performer id (never pooled). Piece
ids are ``maestro_v3:<composer>/<title>`` prefixed ids: the titles are free text and are not
mapped to catalogue numbers here.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from pianolens.data.midi_io import performance_from_midi
from pianolens.data.piece_ids import prefixed_piece_id
from pianolens.data.types import Performance, PerformerId

log = logging.getLogger(__name__)

DATASET = "maestro_v3"
DEFAULT_ROOT = (
    Path(__file__).resolve().parents[3] / "data" / "raw" / "maestro_v3_midi" / "maestro-v3.0.0"
)


def data_available(root: Path | str = DEFAULT_ROOT) -> bool:
    return (Path(root) / "maestro-v3.0.0.csv").is_file()


def maestro_index(root: Path | str = DEFAULT_ROOT) -> pd.DataFrame:
    md = pd.read_csv(Path(root) / "maestro-v3.0.0.csv")
    md["performance_id"] = DATASET + ":" + md["midi_filename"].str.removesuffix(".midi")
    md["piece_id"] = [
        prefixed_piece_id(DATASET, f"{c}/{t}")
        for c, t in zip(md["canonical_composer"], md["canonical_title"], strict=True)
    ]
    return md


@dataclass
class MaestroStats:
    loaded: int = 0
    failed: int = 0
    failures: list[tuple[str, str]] = field(default_factory=list)


def iter_performances(
    root: Path | str = DEFAULT_ROOT,
    split: str | None = None,
    limit: int | None = None,
    stats: MaestroStats | None = None,
) -> Iterator[Performance]:
    root = Path(root)
    stats = stats if stats is not None else MaestroStats()
    md = maestro_index(root)
    if split is not None:
        md = md[md["split"] == split]
    for row in md.head(limit).itertuples() if limit else md.itertuples():
        try:
            yield performance_from_midi(
                root / row.midi_filename,
                dataset=DATASET,
                performance_id=row.performance_id,
                piece_id=row.piece_id,
                performer_id=PerformerId(f"{DATASET}:unknown/{Path(row.midi_filename).stem}"),
                provenance="disklavier",
                meta={"composer": row.canonical_composer, "title": row.canonical_title,
                      "split": row.split, "year": int(row.year)},
            )  # fmt: skip
            stats.loaded += 1
        except Exception as e:  # noqa: BLE001 - count and continue
            stats.failed += 1
            stats.failures.append((row.midi_filename, repr(e)))
            log.warning("maestro %s failed: %r", row.midi_filename, e)
