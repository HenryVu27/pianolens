"""PercePiano loader: segment MIDI, segment scores, per-rater and mean perceptual labels.

Source: https://github.com/JonghoKimSNU/PercePiano (data under ``data/raw/percepiano``).

File names are ``<work>_<N>bars_<player>_<segment>.mid``. The README says
``<segment>_<player>``, but the repo code (``get_performer_id`` = second-to-last token,
``get_segment`` = last token) and the data use ``<player>_<segment>``.

Quirks handled here (see DATASETS.md for counts):

* One MIDI file name starts with a space (`` Schubert_D935_no.3_4bars_2_1.mid``); ids strip it.
* ``labels/total_2rounds.csv`` has 20 question columns; the 19 PercePiano dimensions are the
  first 19 (``Question_9_2_1`` and ``message`` are dropped, as in ``map_midi_to_label.py``).
* The authors' label script renames rated ``_Score_`` files to ``_Score2_`` for Beethoven WoO 80
  segments 5-16 and Schubert D.935 segment 1, and lowercase ``_score`` to ``_Score``. We apply
  the same renames, so those ``_Score_`` MIDI files end up with no labels.
* Rows with any value above 7.1 (values 8 and 9 occur) are dropped whole, as the authors do.
  Blank and 0 answers are "I don't know" and are dropped per dimension.
* The CSV repeats some rows verbatim (same ``dataID``); ``load_percepiano_ratings`` drops those
  by default. The same rater rating the same segment under different ``dataID`` s is kept.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
import partitura as pt

from pianolens.data.piece_ids import make_piece_id
from pianolens.data.types import (
    AlignedPerformance,
    Performance,
    PerformerId,
    PieceId,
    Ratings,
    Score,
    performance_from_partitura,
    score_from_partitura,
)

log = logging.getLogger(__name__)

DATASET = "percepiano"
_REPO = Path(__file__).resolve().parents[3]
DEFAULT_ROOT = _REPO / "data" / "raw" / "percepiano"
DEFAULT_SPANS = _REPO / "data" / "processed" / "percepiano_spans.csv"

# Order of the 19 label columns in the CSV and in the authors' mean-label JSON, named as in the
# PercePiano README table.
DIMENSIONS: tuple[str, ...] = (
    "Timing_Stable_Unstable",
    "Articulation_Short_Long",
    "Articulation_Soft_cushioned_Hard_solid",
    "Pedal_Sparse/dry_Saturated/wet",
    "Pedal_Clean_Blurred",
    "Timbre_Even_Colorful",
    "Timbre_Shallow_Rich",
    "Timbre_Bright_Dark",
    "Timbre_Soft_Loud",
    "Dynamic_Sophisticated/mellow_Raw/crude",
    "Dynamic_Little_dynamic_range_Large_dynamic_range",
    "Music_Making_Fast_paced_Slow_paced",
    "Music_Making_Flat_Spacious",
    "Music_Making_Disproportioned_Balanced",
    "Music_Making_Pure_Dramatic/expressive",
    "Emotion_&_Mood_Optimistic/pleasant_Dark",
    "Emotion_&_Mood_Low_Energy_High_Energy",
    "Emotion_&_Mood_Honest_Imaginative",
    "Interpretation_Unsatisfactory/doubtful_Convincing",
)
SCALE = (1.0, 7.0)

_WORK_PIECE: dict[str, PieceId] = {
    "Beethoven_WoO80": make_piece_id("Beethoven", "WoO80"),
    "Schubert_D935_no.3": make_piece_id("Schubert", "D935", 3),
    "Schubert_D960_mv2": make_piece_id("Schubert", "D960", None, 2),
    "Schubert_D960_mv3": make_piece_id("Schubert", "D960", None, 3),
}
_NAME = re.compile(r"^(?P<work>.+)_(?P<bars>\d+)bars_(?P<player>[^_]+)_(?P<segment>\d+)$")


def data_available(root: Path | str = DEFAULT_ROOT) -> bool:
    return (Path(root) / "labels" / "total_2rounds.csv").is_file()


@dataclass(frozen=True)
class SegmentName:
    """Parsed segment file stem ``<work>_<N>bars_<player>_<segment>``."""

    stem: str
    work: str  # e.g. Beethoven_WoO80_var10, Schubert_D960_mv2
    bars: int
    player: str  # raw token: "1", "01", "Score", "Score2"
    segment: int

    @property
    def piece_key(self) -> str:
        return "Beethoven_WoO80" if self.work.startswith("Beethoven_WoO80") else self.work

    @property
    def is_score_rendition(self) -> bool:
        return self.player.startswith("Score")

    @property
    def score_stem(self) -> str:
        """Stem of the segment's MusicXML under ``virtuoso/data/score_xml``."""
        return f"{self.work}_{self.bars}bars_Score_{self.segment_token}"

    @property
    def segment_token(self) -> str:
        return self.stem.rsplit("_", 1)[1]


def parse_segment_name(name: str) -> SegmentName:
    stem = Path(name.strip()).stem if name.strip().endswith((".mid", ".wav")) else name.strip()
    m = _NAME.match(stem)
    if not m:
        raise ValueError(f"not a PercePiano segment name: {name!r}")
    return SegmentName(stem, m["work"], int(m["bars"]), m["player"], int(m["segment"]))


def percepiano_performance_id(stem: str) -> str:
    return f"{DATASET}:{stem.strip()}"


def percepiano_performer_id(seg: SegmentName) -> PerformerId:
    """Performer id. Beethoven and Schubert players are numbered separately.

    Inference, not documented upstream: the paper reports 25 human pianists. Beethoven uses 12
    player numbers and the two Schubert works together use 13, which gives 25 only if the
    numbering is per composer (``01`` == ``1``). Score renditions get ``percepiano:score`` and
    ``percepiano:score2``.
    """
    if seg.is_score_rendition:
        return PerformerId(f"{DATASET}:{seg.player.lower()}")
    group = "beethoven" if seg.work.startswith("Beethoven") else "schubert"
    return PerformerId(f"{DATASET}:{group}:{int(seg.player)}")


def _read_spans(path: Path | None) -> dict[tuple[str, int, int], tuple[int, int, str]]:
    if path is None or not Path(path).is_file():
        return {}
    df = pd.read_csv(path, dtype={"first_bar": "Int64", "last_bar": "Int64"})
    out = {}
    for r in df.itertuples():
        if pd.notna(r.first_bar):
            out[(r.work, int(r.bars), int(r.segment))] = (int(r.first_bar), int(r.last_bar),
                                                          r.method)
    return out


# --------------------------------------------------------------------------- index


def percepiano_index(root: Path | str = DEFAULT_ROOT,
                     spans_path: Path | None = DEFAULT_SPANS) -> pd.DataFrame:
    """One row per segment MIDI file, with parsed ids and bar range (if known)."""
    root = Path(root)
    spans = _read_spans(spans_path)
    rows = []
    for f in sorted((root / "virtuoso" / "data" / "all_2rounds").glob("*.mid")):
        seg = parse_segment_name(f.name)
        span = spans.get((seg.work, seg.bars, seg.segment))
        rows.append(
            {
                "performance_id": percepiano_performance_id(seg.stem),
                "file": str(f.relative_to(root)),
                "work": seg.work,
                "piece_id": _WORK_PIECE[seg.piece_key],
                "performer_id": percepiano_performer_id(seg),
                "player": seg.player,
                "bars": seg.bars,
                "segment": seg.segment,
                "provenance": "synthetic" if seg.is_score_rendition else "disklavier",
                "score_xml": f"virtuoso/data/score_xml/{seg.score_stem}.musicxml",
                "first_bar": None if span is None else span[0],
                "last_bar": None if span is None else span[1],
                "span_method": None if span is None else span[2],
            }
        )
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- labels


def _rated_stem(filename: str) -> str:
    """Map a CSV ``filename`` to the MIDI stem it was rated as, following the authors."""
    stem = filename.strip().rsplit(".", 1)[0].replace("_score", "_Score")
    seg = int(stem.rsplit("_", 1)[1])
    if ("Beethoven_WoO80" in stem and "Score" in stem and 5 <= seg <= 16) or (
        "Schubert_" in stem and "_no.3_4bars" in stem and "_Score_" in stem and seg == 1
    ):
        stem = stem.replace("_Score_", "_Score2_")
    return stem


def load_percepiano_ratings(root: Path | str = DEFAULT_ROOT,
                            drop_exact_duplicates: bool = True) -> Ratings:
    """Per-rater labels from ``labels/total_2rounds.csv`` on the native 1-7 scale.

    ``Ratings.table`` has ``RATING_COLUMNS`` plus ``rating_id`` (the CSV ``dataID``).
    """
    root = Path(root)
    df = pd.read_csv(root / "labels" / "total_2rounds.csv", dtype=str, keep_default_na=False)
    qcols = list(df.columns[3:22])
    vals = df[qcols].replace("", np.nan).astype(float)
    keep = ~(vals > 7.1).any(axis=1)
    df, vals = df[keep], vals[keep]
    if drop_exact_duplicates:
        dup = df.duplicated(["user", "dataID"] + qcols)
        df, vals = df[~dup], vals[~dup]
    vals.columns = list(DIMENSIONS)
    vals["performance_id"] = [percepiano_performance_id(_rated_stem(f)) for f in df["filename"]]
    vals["rater_id"] = DATASET + ":" + df["user"]
    vals["rating_id"] = df["dataID"].to_numpy()
    long = vals.melt(
        id_vars=["performance_id", "rater_id", "rating_id"], var_name="dimension",
        value_name="value",
    )
    long = long[long["value"].notna() & (long["value"] != 0)].reset_index(drop=True)
    long = long[["performance_id", "rater_id", "dimension", "value", "rating_id"]]
    return Ratings(long, DIMENSIONS, SCALE, DATASET)


def load_percepiano_official_means(root: Path | str = DEFAULT_ROOT) -> pd.DataFrame:
    """The authors' published mean labels (``label_2round_mean_reg_19_with0_rm_highstd0.json``).

    Index ``performance_id``, columns ``DIMENSIONS``, values on the authors' 0-1 scale (mean/7).
    These are the targets prior work reports against. They count verbatim-duplicate CSV rows
    twice, so they differ slightly from ``load_percepiano_ratings().mean() / 7``.
    """
    path = Path(root) / "labels" / "label_2round_mean_reg_19_with0_rm_highstd0.json"
    raw = json.loads(path.read_text())
    df = pd.DataFrame.from_dict({k: v[:19] for k, v in raw.items()}, orient="index",
                                columns=list(DIMENSIONS))
    df.index = [percepiano_performance_id(k) for k in df.index]
    df.index.name = "performance_id"
    return df


# --------------------------------------------------------------------------- performances


def load_percepiano_performance(row: pd.Series, root: Path | str = DEFAULT_ROOT) -> Performance:
    path = Path(root) / row["file"]
    perf = pt.load_performance_midi(str(path))
    span = None
    if row["first_bar"] is not None and pd.notna(row["first_bar"]):
        span = (int(row["first_bar"]), int(row["last_bar"]))
    return performance_from_partitura(
        perf,
        performance_id=row["performance_id"],
        piece_id=PieceId(row["piece_id"]),
        performer_id=PerformerId(row["performer_id"]),
        provenance=row["provenance"],
        dataset=DATASET,
        span=span,
        source_path=path,
        meta={"work": row["work"], "bars": int(row["bars"]), "segment": int(row["segment"]),
              "player": row["player"], "span_method": row["span_method"]},
    )


def load_percepiano_score(row: pd.Series, root: Path | str = DEFAULT_ROOT) -> Score | None:
    """Segment score (bars renumbered from 1 in the file); None if the file is missing."""
    path = Path(root) / row["score_xml"]
    if not path.is_file():
        return None
    s = pt.load_score(str(path))
    part = pt.score.merge_parts(s.parts) if len(s.parts) > 1 else s.parts[0]
    return score_from_partitura(
        part,
        score_id=f"{DATASET}:{path.stem}",
        piece_id=PieceId(row["piece_id"]),
        source_path=path,
        meta={"work": row["work"], "segment": int(row["segment"]),
              "first_bar_in_piece": row["first_bar"]},
    )


@dataclass
class PercePianoStats:
    rows: int = 0
    loaded: int = 0
    failed: list[tuple[str, str]] = field(default_factory=list)
    missing_score: list[str] = field(default_factory=list)


def iter_percepiano(
    root: Path | str = DEFAULT_ROOT,
    *,
    with_score: bool = True,
    index: pd.DataFrame | None = None,
    stats: PercePianoStats | None = None,
) -> Iterator[AlignedPerformance]:
    """Yield every segment as an ``AlignedPerformance`` (no alignment ships with PercePiano)."""
    root = Path(root)
    idx = percepiano_index(root) if index is None else index
    for _, row in idx.iterrows():
        if stats is not None:
            stats.rows += 1
        try:
            perf = load_percepiano_performance(row, root)
            score = load_percepiano_score(row, root) if with_score else None
        except Exception as e:  # noqa: BLE001 - count and continue
            log.warning("percepiano: failed %s: %r", row["file"], e)
            if stats is not None:
                stats.failed.append((row["file"], repr(e)))
            continue
        if stats is not None:
            stats.loaded += 1
            if with_score and score is None:
                stats.missing_score.append(row["performance_id"])
        yield AlignedPerformance(perf, score, None)
