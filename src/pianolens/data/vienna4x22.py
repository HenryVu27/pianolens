"""Vienna 4x22 loader: 4 excerpts x 22 pianists, Boesendorfer SE MIDI with note alignments.

Source: https://github.com/CPJKU/vienna4x22 (match files v1.0.0), under
``data/raw/vienna4x22``. License CC BY 4.0. Performances were recorded on a
computer-monitored Boesendorfer SE290 grand, so provenance is ``sensor``. The ``pNN``
number identifies the same pianist across the four excerpts. ``midi/*-average.mid`` files
are averaged performances, not played ones, and are ignored.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

from pianolens.data.match_corpus import load_match_file
from pianolens.data.piece_ids import make_piece_id
from pianolens.data.types import AlignedPerformance, PerformerId, PieceId

log = logging.getLogger(__name__)

DATASET = "vienna4x22"
DEFAULT_ROOT = Path(__file__).resolve().parents[3] / "data" / "raw" / "vienna4x22"

PIECE_IDS: dict[str, PieceId] = {
    "Chopin_op10_no3": make_piece_id("Chopin", "op10", 3),
    "Chopin_op38": make_piece_id("Chopin", "op38"),
    "Mozart_K331_1st-mov": make_piece_id("Mozart", "k331", None, 1),
    "Schubert_D783_no15": make_piece_id("Schubert", "d783", 15),
}


def data_available(root: Path | str = DEFAULT_ROOT) -> bool:
    return (Path(root) / "match").is_dir()


@dataclass
class ViennaStats:
    loaded: int = 0
    failed: int = 0
    failures: list[tuple[str, str]] = field(default_factory=list)


def match_files(root: Path | str = DEFAULT_ROOT) -> list[Path]:
    return sorted((Path(root) / "match").glob("*_p[0-9][0-9].match"))


def iter_aligned(
    root: Path | str = DEFAULT_ROOT, stats: ViennaStats | None = None
) -> Iterator[AlignedPerformance]:
    stats = stats if stats is not None else ViennaStats()
    for path in match_files(root):
        excerpt, pianist = path.stem.rsplit("_", 1)
        try:
            yield load_match_file(
                path,
                dataset=DATASET,
                performance_id=f"{DATASET}:{path.stem}",
                score_id=f"{DATASET}:{excerpt}",
                piece_id=PIECE_IDS[excerpt],
                performer_id=PerformerId(f"{DATASET}:{pianist}"),
                provenance="sensor",
                meta={"excerpt": excerpt},
            )
            stats.loaded += 1
        except Exception as e:  # noqa: BLE001 - count and continue
            stats.failed += 1
            stats.failures.append((path.name, repr(e)))
            log.warning("vienna4x22 %s failed: %r", path.name, e)
