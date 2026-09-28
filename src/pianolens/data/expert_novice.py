"""Expert-Novice loader (Jiang et al. 2023): 83 amateur recordings of 7 easy pieces, rated by
4 instructors and by novice raters, with beat-level audio-to-score alignments.

Source: Zenodo 8392772 under ``data/raw/expert_novice`` (zips extracted to ``extracted/``).
License CC BY-NC-SA 4.0. Audio only (48 kHz WAV), no MIDI, so there is no ``Performance``;
the loader returns ``Ratings`` plus an index of recordings with WAV and alignment paths.

Ratings: ``Instructor{1-4}_rating`` (experts) and ``Rater{1-6}_rating`` with
``Rater{k}_id`` (novices; ids go up to 21, the same range as ``Player_id``: whether raters are
the players themselves is not stated in the files). Scale 1-5, one "overall" dimension; the
free-text comments are kept in ``Ratings.table["text"]``.

Alignment files ``<Piece>.<NNN>.txt``: one row per score beat, ``<bar>+<beat fraction>`` and
the time in seconds.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from pianolens.data.types import RATING_COLUMNS, Ratings

DATASET = "expert_novice"
DEFAULT_ROOT = Path(__file__).resolve().parents[3] / "data" / "raw" / "expert_novice"
_REC_DIR = "extracted/Recordings and Alignments"


def data_available(root: Path | str = DEFAULT_ROOT) -> bool:
    root = Path(root)
    return (root / "evaluation_data_anonymous.csv").is_file() and (root / _REC_DIR).is_dir()


def _read_eval(root: Path) -> pd.DataFrame:
    return pd.read_csv(root / "evaluation_data_anonymous.csv", encoding="utf-8",
                       encoding_errors="replace", dtype=str)  # fmt: skip


def _perf_id(piece_id: str, rec: str) -> str:
    return f"{DATASET}:{int(piece_id)}_{int(rec):02d}"


def recordings_index(root: Path | str = DEFAULT_ROOT) -> pd.DataFrame:
    """One row per recording: performance_id, piece, player (performer_id), skill level,
    wav_path, alignment_path (None when the file is missing)."""
    root = Path(root)
    ev = _read_eval(root)
    skills = pd.read_csv(root / "self-identified_skill_levels.txt", sep="\t", dtype=str)
    skill = dict(zip(skills["Player_id"], skills["Level"], strict=True))
    rows = []
    for r in ev.itertuples():
        folder = root / _REC_DIR / re.sub(r"[^A-Za-z0-9]", "", r.Piece_name)
        n = int(r.Recording_number)
        wavs = sorted(folder.glob(f"*-{n:02d}.wav"))
        align = folder / f"{folder.name}.{n:03d}.txt"
        rows.append({
            "performance_id": _perf_id(r.Piece_id, r.Recording_number),
            "piece_id": f"{DATASET}:{folder.name}",
            "piece_name": r.Piece_name,
            "performer_id": f"{DATASET}:player{int(r.Player_id)}",
            "skill_level": skill.get(r.Player_id),
            "sample_rate_khz": int(r.Sample_rate),
            "wav_path": wavs[0] if len(wavs) == 1 else None,
            "alignment_path": align if align.is_file() else None,
        })  # fmt: skip
    return pd.DataFrame(rows)


def load_ratings(root: Path | str = DEFAULT_ROOT) -> Ratings:
    ev = _read_eval(Path(root))
    rows = []
    for r in ev.to_dict("records"):
        pid = _perf_id(r["Piece_id"], r["Recording_number"])
        for k in range(1, 5):
            v = r.get(f"Instructor{k}_rating")
            if isinstance(v, str) and v.strip():
                rows.append((pid, f"{DATASET}:instructor{k}", "overall", float(v), "expert",
                             r.get(f"Instructor{k}_text")))  # fmt: skip
        for k in range(1, 7):
            v, rid = r.get(f"Rater{k}_rating"), r.get(f"Rater{k}_id")
            if isinstance(v, str) and v.strip() and isinstance(rid, str) and rid.strip():
                rows.append((pid, f"{DATASET}:novice{int(rid)}", "overall", float(v), "novice",
                             r.get(f"Rater{k}_text")))  # fmt: skip
    table = pd.DataFrame(rows, columns=[*RATING_COLUMNS, "rater_group", "text"])
    return Ratings(table=table, dimensions=("overall",), scale=(1.0, 5.0), dataset=DATASET)


def load_beat_alignment(path: Path | str) -> pd.DataFrame:
    """Beat alignment file -> columns ``bar``, ``beat_frac`` (fraction of the bar), ``time_sec``."""
    rows = []
    for line in Path(path).read_text().splitlines():
        if not line.strip():
            continue
        pos, t = line.split()
        bar, frac = pos.split("+")
        num, den = frac.split("/")
        rows.append((int(bar), int(num) / int(den), float(t)))
    return pd.DataFrame(rows, columns=["bar", "beat_frac", "time_sec"])
