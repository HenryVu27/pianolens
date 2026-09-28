"""NeuroPiano loader: 104 student recordings of piano exercises rated by teachers on 13
questions, with free-text answers (Japanese and English).

Source: https://huggingface.co/datasets/anusfoil/NeuroPiano-data under
``data/raw/neuropiano`` (parquet, audio embedded as WAV bytes). License MIT per the dataset
card. Audio only, no MIDI, so there is no ``Performance``: the loader returns ``Ratings``
and ``load_audio_bytes``.

One parquet row = (recording ``fname``, rater ``subject``, question). ``score`` is on 0-6.
Dimensions are ``q<question_id>``; ``QUESTIONS`` gives the English text. Questions 1 and 2
("what's good / bad") also carry a score. A few (recording, rater, question) triples occur
twice; ``Ratings.matrix`` averages them.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from pianolens.data.types import RATING_COLUMNS, Ratings

DATASET = "neuropiano"
DEFAULT_ROOT = Path(__file__).resolve().parents[3] / "data" / "raw" / "neuropiano"
_COLS = ["subject", "piece", "user_id", "playdata_id", "fname", "good_or_bad", "mean",
         "question_id", "q_eng", "a_eng", "score", "split"]  # fmt: skip


def data_available(root: Path | str = DEFAULT_ROOT) -> bool:
    return any((Path(root) / "data").glob("*.parquet"))


def _files(root: Path | str) -> list[Path]:
    return sorted((Path(root) / "data").glob("*.parquet"))


def load_table(root: Path | str = DEFAULT_ROOT) -> pd.DataFrame:
    """All rows without audio; ``hf_split`` is the parquet file split (train / eval)."""
    parts = [
        pd.read_parquet(f, columns=_COLS).assign(hf_split=f.name.split("-")[0])
        for f in _files(root)
    ]
    df = pd.concat(parts, ignore_index=True)
    df["performance_id"] = DATASET + ":" + df["fname"].str.removesuffix(".wav")
    df["performer_id"] = DATASET + ":" + df["user_id"]
    return df


def questions(root: Path | str = DEFAULT_ROOT) -> dict[str, str]:
    df = load_table(root)
    return {f"q{q}": t for q, t in df.groupby("question_id")["q_eng"].first().items()}


def load_ratings(root: Path | str = DEFAULT_ROOT) -> Ratings:
    df = load_table(root)
    table = pd.DataFrame({
        "performance_id": df["performance_id"],
        "rater_id": DATASET + ":" + df["subject"],
        "dimension": "q" + df["question_id"].astype(str),
        "value": df["score"].astype(float),
        "answer_en": df["a_eng"],
        "piece": df["piece"],
        "performer_id": df["performer_id"],
    })  # fmt: skip
    dims = tuple(f"q{q}" for q in sorted(df["question_id"].unique()))
    assert list(table.columns[:4]) == list(RATING_COLUMNS)
    return Ratings(table=table, dimensions=dims, scale=(0.0, 6.0), dataset=DATASET)


def load_audio_bytes(performance_id: str, root: Path | str = DEFAULT_ROOT) -> bytes:
    """WAV bytes of one recording (the same audio is repeated on every row of that file)."""
    fname = performance_id.removeprefix(f"{DATASET}:") + ".wav"
    for f in _files(root):
        df = pd.read_parquet(f, columns=["fname", "audio_path"], filters=[("fname", "==", fname)])
        if len(df):
            return df.iloc[0]["audio_path"]["bytes"]
    raise KeyError(performance_id)
