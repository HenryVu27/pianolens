"""Build the cross-dataset piece-id table data/processed/piece_ids.parquet (D-07).

One row per (dataset, source_key): the dataset's own name for a piece and the PianoLens
``PieceId`` its loader assigns. Canonical ids (no ``<dataset>:`` prefix) are shared across
datasets; that is the point of the table. Sources: (n)ASAP (composer/title), PianoCoRe
(``data/processed/pianocore_piece_map.csv`` + counts), PercePiano (work), MAJEPPA (score id),
Vienna 4x22 (excerpt), Batik-plays-Mozart (movement), MazurkaBL (mazurka), DCML J. C. Bach
sonatas and the five DCML Romantic corpora of D-13 (movement; score only), and the tonebase
annotated scores of D-14 (PDF path; no performances). MAESTRO, PSyllabus,
Expert-Novice and NeuroPiano have free-text or local ids only and are not included.

Columns: dataset, source_key, piece_id, canonical, composer, title, movement, n_performances.
For PianoCoRe ``n_performances`` is the tier C row count and ``n_tier_a`` the tier A count
(NaN for other datasets).

Usage: uv run python scripts/build_piece_ids.py
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from pianolens.data import (
    asap,
    batik_mozart,
    dcml,
    dcml_jc_bach,
    majeppa,
    mazurkabl,
    percepiano,
    tonebase,
    vienna4x22,
)
from pianolens.data.piece_ids import PIECE_ID_COLUMNS, PIECE_ID_TABLE

ROOT = Path(__file__).resolve().parents[1]
PC_COUNTS = ROOT / "data/processed/pianocore_piece_counts.csv"


def _asap() -> pd.DataFrame:
    md = asap.asap_index()
    g = md.groupby(["composer", "title", "piece_id"]).size().reset_index(name="n_performances")
    g["source_key"] = g["composer"] + "/" + g["title"]
    g["movement"] = ""
    return g


def _pianocore() -> pd.DataFrame:
    t = pd.read_csv(PC_COUNTS, keep_default_na=False)
    return pd.DataFrame({
        "source_key": t["composer"] + "/" + t["composition"] + "/" + t["movement"],
        "piece_id": t["piece_id"], "composer": t["composer"], "title": t["composition"],
        "movement": t["movement"], "n_performances": t["n_c"], "n_tier_a": t["n_a"],
    })  # fmt: skip


def _percepiano() -> pd.DataFrame:
    idx = percepiano.percepiano_index()
    idx["key"] = idx["work"].str.replace(r"_(var\d+|thema?)$", "", regex=True)
    g = idx.groupby(["key", "piece_id"]).size().reset_index(name="n_performances")
    return pd.DataFrame({
        "source_key": g["key"], "piece_id": g["piece_id"],
        "composer": g["key"].str.split("_").str[0], "title": g["key"], "movement": "",
        "n_performances": g["n_performances"],
    })  # fmt: skip


def _majeppa() -> pd.DataFrame:
    md = majeppa.majeppa_index().dropna(subset=["score_id"])
    g = md.groupby("score_id").agg(
        piece_id=("piece_id", "first"), composer=("composer", "first"),
        title=("piece_title", "first"), n_performances=("performance_id", "size"),
    ).reset_index()  # fmt: skip
    g["composer"] = g["composer"].fillna("")
    return g.rename(columns={"score_id": "source_key"}).assign(movement="")


def _vienna() -> pd.DataFrame:
    stems = [p.stem.rsplit("_", 1)[0] for p in vienna4x22.match_files()]
    counts = pd.Series(stems).value_counts()
    return pd.DataFrame([
        {"source_key": k, "piece_id": pid, "composer": k.split("_")[0], "title": k,
         "movement": "", "n_performances": int(counts.get(k, 0))}
        for k, pid in vienna4x22.PIECE_IDS.items()
    ])  # fmt: skip


def _batik() -> pd.DataFrame:
    return pd.DataFrame([
        {"source_key": p.stem, "piece_id": batik_mozart.movement_piece_id(p.stem),
         "composer": "Mozart", "title": p.stem.split("_")[0], "movement": p.stem.split("_")[1],
         "n_performances": 1}
        for p in batik_mozart.match_files()
    ])  # fmt: skip


def _mazurkabl() -> pd.DataFrame:
    rows = []
    for key in mazurkabl.mazurkas():
        df = pd.read_csv(mazurkabl.DEFAULT_ROOT / "beat_time" / f"{key}beat_time.csv", nrows=1)
        n = sum(c.startswith("pid") for c in df.columns)
        rows.append({"source_key": key, "piece_id": mazurkabl.mazurka_piece_id(key),
                     "composer": "Chopin", "title": key, "movement": "", "n_performances": n})
    return pd.DataFrame(rows)


def _jc_bach() -> pd.DataFrame:
    """Score-only corpus (D-12): ``n_performances`` is 0."""
    md = dcml_jc_bach.metadata()
    return pd.DataFrame([
        {"source_key": r.piece, "piece_id": dcml_jc_bach.piece_id(r.piece),
         "composer": "J. C. Bach", "title": r.workTitle, "movement": r.movementTitle,
         "n_performances": 0}
        for r in md.itertuples()
    ])  # fmt: skip


def _dcml(corpus: str) -> pd.DataFrame:
    """A DCML Romantic corpus (D-13), score only: ``n_performances`` is 0. ``title`` is the
    corpus's subtitle (e.g. "Mazurka in b, Op. 30, no. 2")."""
    c = dcml.get_corpus(corpus)
    md = dcml.metadata(c).set_index("piece")
    return pd.DataFrame([
        {"source_key": stem, "piece_id": dcml.piece_id(c, stem), "composer": c.composer,
         "title": str(md.loc[stem, "subtitle_text"] if "subtitle_text" in md else stem),
         "movement": str(md.loc[stem].get("movementTitle", "") or ""), "n_performances": 0}
        for stem in dcml.pieces(c)
    ])  # fmt: skip


def _tonebase() -> pd.DataFrame:
    """Teachers' annotated scores (D-14), no performances: ``n_performances`` is 0."""
    return pd.DataFrame([
        {"source_key": r.path, "piece_id": r.piece_id, "composer": r.title.split()[0],
         "title": r.title, "movement": "", "n_performances": 0}
        for r in tonebase.annotated_scores().itertuples()
    ])  # fmt: skip


def main() -> None:
    parts = {
        "asap": _asap, "pianocore": _pianocore, "percepiano": _percepiano,
        "majeppa": _majeppa, "vienna4x22": _vienna, "batik_mozart": _batik,
        "mazurkabl": _mazurkabl, "dcml_jc_bach": _jc_bach,
        **{f"dcml_{c}": (lambda c=c: _dcml(c)) for c in dcml.ROMANTIC},
        "tonebase": _tonebase,
    }  # fmt: skip
    frames = []
    for name, fn in parts.items():
        df = fn()
        df["dataset"] = name
        frames.append(df)
    table = pd.concat(frames, ignore_index=True)
    table["canonical"] = ~table["piece_id"].str.contains(":", regex=False)
    if "n_tier_a" not in table:
        table["n_tier_a"] = pd.NA
    table = table[list(PIECE_ID_COLUMNS)].astype({"n_performances": "int64"})
    dup = table.duplicated(["dataset", "source_key"])
    if dup.any():
        raise SystemExit(f"duplicate (dataset, source_key): {table[dup].head()}")
    PIECE_ID_TABLE.parent.mkdir(parents=True, exist_ok=True)
    table.to_parquet(PIECE_ID_TABLE, index=False)

    print(f"wrote {PIECE_ID_TABLE}: {len(table)} rows")
    for ds, g in table.groupby("dataset", sort=False):
        print(f"  {ds:13s} {len(g):5d} keys, {g['piece_id'].nunique():5d} piece ids, "
              f"{g.loc[g.canonical, 'piece_id'].nunique():5d} canonical")  # fmt: skip
    canon = table[table.canonical]
    per_id = canon.groupby("piece_id")["dataset"].agg(lambda s: tuple(sorted(set(s))))
    shared = per_id[per_id.map(len) > 1]
    print(f"canonical ids: {len(per_id)}; in 2+ datasets: {len(shared)}")
    for ds in parts:
        if ds == "pianocore":
            continue
        ids = set(canon.loc[canon.dataset == ds, "piece_id"])
        pc = set(canon.loc[canon.dataset == "pianocore", "piece_id"])
        print(f"  {ds} canonical ids also in PianoCoRe: {len(ids & pc)} of {len(ids)}")


if __name__ == "__main__":
    main()
