"""Rach3 MIDI loader: rehearsal sessions of four pianists (three advanced, one beginner).

Source: https://github.com/Rach3Project/rach3_midi_dataset (ISMIR 2025), commit ``a9519492``.
License CC BY-NC-SA 4.0 (repo LICENSE). D-10 downloaded only the Hanon subset
(``hanoncexercs``: p1 124 files, p2 36, p3 87, plus ``scores/hanoncexercs.musicxml``); the
full repo holds 3,160 MIDI files.

File names: ``p<k><YYMMDD><session><NN><12-char piece id>mi.mid`` (the README describes 25
characters; every file also ends in ``mi`` before ``.mid``). Levels come from the README:
p1, p2, p4 advanced, p3 beginner. Each file is one piece within one practice session, often
many minutes long with repeats, stops and partial passes: not a single take.

Provenance: the README says "MIDI recordings" of rehearsals but does not name the instrument.
It is keyboard MIDI, not transcribed from audio, so it is tagged ``sensor`` with
``meta["instrument"] = "not stated"`` (D-10; to be confirmed).
"""

from __future__ import annotations

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

DATASET = "rach3"
DEFAULT_ROOT = Path(__file__).resolve().parents[3] / "data" / "raw" / "rach3"
LEVELS = {"p1": "advanced", "p2": "advanced", "p3": "beginner", "p4": "advanced"}
_NAME = re.compile(r"^(p\d)(\d{6})(\d|r)(\d{2})([a-z0-9]{12})(?:mi)?$")


def data_available(root: Path | str = DEFAULT_ROOT) -> bool:
    return (Path(root) / "rehearsals").is_dir()


def rach3_index(root: Path | str = DEFAULT_ROOT) -> pd.DataFrame:
    """One row per MIDI file on disk: pianist, level, date, session, piece_no, piece_code."""
    rows = []
    for f in sorted(Path(root).glob("re*/**/*.mid")):
        m = _NAME.match(f.stem)
        if not m:
            log.warning("rach3: unexpected file name %s", f.name)
            continue
        p, date, session, no, code = m.groups()
        rows.append({
            "path": f, "pianist": p, "level": LEVELS.get(p, "unknown"),
            "date": pd.Timestamp(f"20{date[:2]}-{date[2:4]}-{date[4:]}"),
            "session": session, "piece_no": int(no), "piece_code": code,
            "performance_id": f"{DATASET}:{f.stem}",
            "piece_id": prefixed_piece_id(DATASET, code),
            "performer_id": f"{DATASET}:{p}",
        })  # fmt: skip
    return pd.DataFrame(rows)


@dataclass
class Rach3Stats:
    loaded: int = 0
    failed: int = 0
    failures: list[tuple[str, str]] = field(default_factory=list)


def iter_performances(
    root: Path | str = DEFAULT_ROOT,
    piece_code: str | None = None,
    limit: int | None = None,
    stats: Rach3Stats | None = None,
) -> Iterator[Performance]:
    stats = stats if stats is not None else Rach3Stats()
    md = rach3_index(root)
    if piece_code is not None:
        md = md[md["piece_code"] == piece_code]
    for r in (md.head(limit) if limit else md).itertuples():
        try:
            yield performance_from_midi(
                r.path, dataset=DATASET, performance_id=r.performance_id,
                piece_id=r.piece_id, performer_id=PerformerId(r.performer_id),
                provenance="sensor",
                meta={"level": r.level, "date": str(r.date.date()), "session": r.session,
                      "piece_no": r.piece_no, "piece_code": r.piece_code,
                      "instrument": "not stated"})  # fmt: skip
            stats.loaded += 1
        except Exception as e:  # noqa: BLE001 - count and continue
            stats.failed += 1
            stats.failures.append((str(r.path), repr(e)))
            log.warning("rach3 %s failed: %r", r.path, e)
