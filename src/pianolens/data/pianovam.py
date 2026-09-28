"""PianoVAM loader, MIDI only (no audio, video or hand skeletons on this Mac).

Source: https://huggingface.co/datasets/PianoVAM/PianoVAM_v1 (ISMIR 2025, arXiv 2509.08800),
v1.2, commit ``1f039ab9``; ``MIDI/*.mid`` and ``metadata.json`` under ``data/raw/pianovam``.
License CC BY-NC-SA 4.0 (dataset card). The MIDI was captured live from a Disklavier during
daily practice by 10 amateur pianists (none music majors), so provenance is ``disklavier``.

Labels: ``P1_skill`` is self-reported (Beginner / Intermediate / Advanced). No scores are
released, and the piece names are free text (70 pieces, some improvisations), so piece ids are
``pianovam:<composer>/<piece>`` prefixed ids. Performer ids use the first name given
(``pianovam:<name>``, lower-cased). One four-hands recording has a second performer (P2_*),
kept in ``meta``.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from pianolens.data.midi_io import performance_from_midi
from pianolens.data.piece_ids import prefixed_piece_id
from pianolens.data.types import Performance, PerformerId

log = logging.getLogger(__name__)

DATASET = "pianovam"
DEFAULT_ROOT = Path(__file__).resolve().parents[3] / "data" / "raw" / "pianovam"
SKILLS = ("Beginner", "Intermediate", "Advanced")


def data_available(root: Path | str = DEFAULT_ROOT) -> bool:
    root = Path(root)
    return (root / "metadata.json").is_file() and (root / "MIDI").is_dir()


def _slug(x: object) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(x).lower()).strip("_")


def pianovam_index(root: Path | str = DEFAULT_ROOT) -> pd.DataFrame:
    """One row per recording: metadata.json fields plus ``performance_id``, ``piece_id``,
    ``performer_id`` and ``midi_path``."""
    root = Path(root)
    md = pd.DataFrame(json.loads((root / "metadata.json").read_text()).values())
    md["performance_id"] = DATASET + ":" + md["record_time"]
    md["piece_id"] = [prefixed_piece_id(DATASET, f"{_slug(c)}/{_slug(p)}")
                      for c, p in zip(md["composer"], md["piece"], strict=True)]  # fmt: skip
    md["performer_id"] = DATASET + ":" + md["P1_name"].str.strip().str.lower()
    md["midi_path"] = [root / "MIDI" / f"{t}.mid" for t in md["record_time"]]
    return md


@dataclass
class PianoVAMStats:
    loaded: int = 0
    failed: int = 0
    missing: int = 0
    failures: list[tuple[str, str]] = field(default_factory=list)


def iter_performances(
    root: Path | str = DEFAULT_ROOT,
    limit: int | None = None,
    stats: PianoVAMStats | None = None,
) -> Iterator[Performance]:
    """Yield every recording as a ``Performance`` (no score exists)."""
    stats = stats if stats is not None else PianoVAMStats()
    md = pianovam_index(root)
    for r in (md.head(limit) if limit else md).itertuples():
        if not Path(r.midi_path).is_file():
            stats.missing += 1
            continue
        try:
            yield performance_from_midi(
                Path(r.midi_path), dataset=DATASET, performance_id=r.performance_id,
                piece_id=r.piece_id, performer_id=PerformerId(r.performer_id),
                provenance="disklavier",
                meta={"skill": r.P1_skill, "composer": r.composer, "piece": r.piece,
                      "performance_method": r.performance_method, "split": r.split,
                      "age": r.P1_age, "p2_name": r.P2_name, "p2_skill": r.P2_skill})  # fmt: skip
            stats.loaded += 1
        except Exception as e:  # noqa: BLE001 - count and continue
            stats.failed += 1
            stats.failures.append((r.record_time, repr(e)))
            log.warning("pianovam %s failed: %r", r.record_time, e)
