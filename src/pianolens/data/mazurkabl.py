"""MazurkaBL loader: beat times and beat loudness for recordings of Chopin mazurkas.

Source: https://github.com/katkost/MazurkaBL under ``data/raw/mazurkabl``, license
CC BY-NC-SA 4.0 (stated in the README; there is no LICENSE file). No audio and no notes:
per score beat, the onset time (``beat_time/M<op>-<no>beat_time.csv``) and normalised
loudness in sones (``beat_dyn/M<op>-<no>beat_dynNORM.csv``) of each recording. Columns are
recording ids ``pid<NNNN>-<NN>``; the ``pid`` number before the dash identifies the pianist
(``pianistID_name.csv``). Beat times are annotations of commercial recordings (CHARM
Mazurka project), so they are neither Disklavier nor transcribed MIDI.

``load_beat_curves`` / ``iter_beat_curves`` return one ``types.BeatCurve`` per recording
(``beat`` is MazurkaBL's 0-based ``beat_number``, loudness unit ``sone_norm``, provenance
None). ``load_mazurka`` / ``load_all`` keep the long-DataFrame view (columns
``BEAT_COLUMNS``).
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

import pandas as pd

from pianolens.data.piece_ids import make_piece_id
from pianolens.data.types import BeatCurve, PerformerId, PieceId

DATASET = "mazurkabl"
DEFAULT_ROOT = Path(__file__).resolve().parents[3] / "data" / "raw" / "mazurkabl"
BEAT_COLUMNS = (
    "performance_id", "piece_id", "performer_id", "mazurka", "measure", "beat", "time_sec",
    "loudness",
)  # fmt: skip
LOUDNESS_UNIT = "sone_norm"
_MAZ = re.compile(r"^M(\d+)-(\d+)")


def data_available(root: Path | str = DEFAULT_ROOT) -> bool:
    return (Path(root) / "beat_time").is_dir()


def mazurkas(root: Path | str = DEFAULT_ROOT) -> list[str]:
    """Mazurka keys such as ``M06-1`` (op. 6 no. 1)."""
    files = (Path(root) / "beat_time").glob("M*beat_time.csv")
    return sorted(m[0] for p in files if (m := _MAZ.match(p.name)))


def mazurka_piece_id(key: str) -> PieceId:
    m = _MAZ.match(key)
    if m is None:
        raise ValueError(key)
    return make_piece_id("Chopin", f"op{int(m[1])}", int(m[2]))


def pianists(root: Path | str = DEFAULT_ROOT) -> dict[str, str]:
    """pid number -> pianist surname."""
    df = pd.read_csv(Path(root) / "pianistID_name.csv", header=None, names=["name", "pid"],
                     encoding="utf-8-sig", dtype=str)  # fmt: skip
    return {pid.strip(): name.strip() for name, pid in zip(df["name"], df["pid"], strict=True)}


def _wide_to_long(path: Path, value: str) -> pd.DataFrame:
    df = pd.read_csv(path, index_col=0)
    long = df.melt(id_vars=["measure_number", "beat_number"], var_name="recording",
                   value_name=value)  # fmt: skip
    return long.rename(columns={"measure_number": "measure", "beat_number": "beat"})


def load_mazurka(key: str, root: Path | str = DEFAULT_ROOT) -> pd.DataFrame:
    """All recordings of one mazurka, one row per (recording, score beat)."""
    root = Path(root)
    t = _wide_to_long(root / "beat_time" / f"{key}beat_time.csv", "time_sec")
    dyn_path = root / "beat_dyn" / f"{key}beat_dynNORM.csv"
    if dyn_path.is_file():
        d = _wide_to_long(dyn_path, "loudness")
        t = t.merge(d, on=["recording", "measure", "beat"], how="left")
    else:
        t["loudness"] = float("nan")
    names = pianists(root)
    pid_num = t["recording"].str.extract(r"^pid(\d+)[a-z]?-")[0]  # "pid9070b-01" occurs
    t["performer_id"] = [f"{DATASET}:{names.get(p, 'pid' + p)}" for p in pid_num]
    t["performance_id"] = f"{DATASET}:{key}/" + t["recording"]
    t["piece_id"] = mazurka_piece_id(key)
    t["mazurka"] = key
    return t[list(BEAT_COLUMNS)]


def load_all(root: Path | str = DEFAULT_ROOT) -> pd.DataFrame:
    return pd.concat([load_mazurka(k, root) for k in mazurkas(root)], ignore_index=True)


def load_beat_curves(key: str, root: Path | str = DEFAULT_ROOT) -> list[BeatCurve]:
    """One ``BeatCurve`` per recording of one mazurka, beats in score order."""
    df = load_mazurka(key, root)
    curves = []
    for pid, g in df.groupby("performance_id", sort=True):
        curves.append(
            BeatCurve(
                performance_id=str(pid),
                piece_id=PieceId(g["piece_id"].iat[0]),
                performer_id=PerformerId(g["performer_id"].iat[0]),
                time_sec=g["time_sec"].to_numpy(float),
                loudness=g["loudness"].to_numpy(float),
                measure=g["measure"].to_numpy(int),
                beat=g["beat"].to_numpy(float),
                loudness_unit=LOUDNESS_UNIT,
                dataset=DATASET,
                provenance=None,
                meta={"mazurka": key},
            )
        )
    return curves


def iter_beat_curves(root: Path | str = DEFAULT_ROOT) -> Iterator[BeatCurve]:
    for key in mazurkas(root):
        yield from load_beat_curves(key, root)
