"""PianoJudges repo labels (Zhang et al. 2024, "From Audio Encoders to Piano Judges").

Source: https://github.com/anusfoil/PianoJudges under ``data/raw/pianojudges`` (code repo,
no LICENSE file: license unclear). No audio or MIDI is distributed. What the repo holds:

* ``data_collection/index.json`` + ``splits.json``: the CIPI difficulty index (652 works,
  Henle levels 1-9, 5 folds of train / val / test). The scores themselves are not in the repo
  and the CIPI Zenodo record (8037327) is access-restricted.
* ``data_collection/{novice,advanced}_channels.txt``: YouTube channel lists per expertise
  level for the Pianism-Labelling dataset (``#`` lines are commented out in the source).
* ``technique_groups.txt`` (YouTube URLs under ``# <technique>`` headers),
  ``mikrokosmos.txt``, ``preliminary_round_url.txt``.

These are labels and links only; building the audio set means scraping YouTube, which is out
of scope (see DATASETS.md).
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

DATASET = "pianojudges"
DEFAULT_ROOT = Path(__file__).resolve().parents[3] / "data" / "raw" / "pianojudges"
_DC = "data_collection"


def data_available(root: Path | str = DEFAULT_ROOT) -> bool:
    return (Path(root) / _DC / "index.json").is_file()


def load_cipi_index(root: Path | str = DEFAULT_ROOT, fold: int = 0) -> pd.DataFrame:
    """One row per CIPI work: key, composer, work_name, book, henle (1-9), n_movements,
    split (for ``fold``)."""
    root = Path(root) / _DC
    index = json.loads((root / "index.json").read_text())
    split = json.loads((root / "splits.json").read_text())[str(fold)]
    split_of = {k: s for s, keys in split.items() for k in keys}
    return pd.DataFrame([
        {"key": k, "composer": v.get("composer"), "work_name": v.get("work_name"),
         "book": v.get("book"), "henle": int(v["henle"]), "n_movements": len(v.get("path", {})),
         "split": split_of.get(k)}
        for k, v in index.items()
    ])  # fmt: skip


def load_channel_lists(root: Path | str = DEFAULT_ROOT) -> pd.DataFrame:
    """YouTube channels per expertise level: columns level, url, active (False if commented)."""
    rows = []
    for level in ("novice", "advanced"):
        for line in (Path(root) / _DC / f"{level}_channels.txt").read_text().splitlines():
            s = line.strip()
            if not s:
                continue
            active = not s.startswith("#")
            url = s.lstrip("# ").strip()
            if url.startswith("http"):
                rows.append({"level": level, "url": url, "active": active})
    return pd.DataFrame(rows)


def load_technique_urls(root: Path | str = DEFAULT_ROOT) -> pd.DataFrame:
    """YouTube URLs grouped by technique header: columns technique, url."""
    rows, tech = [], None
    for line in (Path(root) / _DC / "technique_groups.txt").read_text().splitlines():
        s = line.strip()
        if s.startswith("#"):
            tech = s.lstrip("# ").strip()
        elif s.startswith("http"):
            rows.append({"technique": tech, "url": s})
    return pd.DataFrame(rows)
