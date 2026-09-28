"""Build the synthetic mistake set ``data/processed/mistakes_v1`` (D-08).

Run: ``uv run python scripts/build_mistake_set.py [--n 100] [--workers 12]``

Selection (fixed, seed 0): (n)ASAP performances with a ground-truth note alignment flagged
robust, whose MusicXML score has a single repeat path (so ground-truth score ids equal the ids
``align_performance`` produces and measure numbers are unique), and at most ``--max-notes``
performed notes (keeps the F-02 evaluation under ~10 min). Composers are sampled round-robin,
one performance per piece before any second performance of the same piece.

Each selected performance gets one clean copy (rate 0) and one perturbed copy per rate in
``RATES``, seeds ``1000 * i + j``, with ``pianolens.data.perturb.MistakeSpec`` defaults otherwise.

Outputs (gitignored, regenerate with this script):
  index.csv       one row per (performance, rate): key, source ids, rate, seed, counts
  notes.parquet   perturbed note arrays + per-note ground-truth labels
  missed.parquet  missed score notes (injected and natural)
  pedal.parquet   pedal events (unchanged copies)
  spec.json       the specs, selection rules and the generator version
Load with ``pianolens.data.perturb.load_mistake_set``.
"""

from __future__ import annotations

import argparse
import json
import logging
import warnings
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

from pianolens.align import load_score_part, repeat_variants
from pianolens.data import asap
from pianolens.data.perturb import MistakeSpec, perturb

RATES = (0.0, 0.02, 0.05, 0.10)
VERSION = "mistakes_v1 (perturb.py 2026-09-27)"
log = logging.getLogger("build_mistake_set")


def _n_paths(xml: str) -> tuple[str, int]:
    warnings.filterwarnings("ignore")
    try:
        return xml, len(repeat_variants(load_score_part(Path(asap.DEFAULT_ROOT) / xml)))
    except Exception:  # noqa: BLE001 - unreadable score: exclude
        return xml, -1


def select(md: pd.DataFrame, n: int, max_notes: int, workers: int) -> pd.DataFrame:
    md = md[md["robust_note_alignment"] == 1.0].copy()
    md = md[[asap.asap_alignment_path(r).is_file() for _, r in md.iterrows()]]
    with ProcessPoolExecutor(workers) as ex:
        paths = dict(ex.map(_n_paths, sorted(md["xml_score"].unique())))
    md["n_paths"] = md["xml_score"].map(paths)
    md = md[md["n_paths"] == 1]
    n_notes = []
    for _, r in md.iterrows():
        n_notes.append(len(asap.load_asap_performance(r).notes))
    md["n_notes"] = n_notes
    md = md[md["n_notes"] <= max_notes]
    rng = np.random.default_rng(0)
    md = md.iloc[rng.permutation(len(md))]
    queues: dict[str, list[list[int]]] = {}
    for comp, g in md.groupby("composer", sort=True):
        by_piece = [list(gg.index) for _, gg in g.groupby("folder", sort=False)]
        queues[comp] = by_piece
    chosen: list[int] = []
    while len(chosen) < n and any(any(q) for q in queues.values()):
        for comp in sorted(queues):
            pieces = queues[comp]
            # next piece with a performance left, cycling so pieces are used once per round
            for _ in range(len(pieces)):
                piece = pieces.pop(0)
                if piece:
                    chosen.append(piece.pop(0))
                    pieces.append(piece)
                    break
                pieces.append(piece)
            if len(chosen) >= n:
                break
    return md.loc[chosen]


def build_one(args: tuple[int, dict]) -> tuple[list[dict], list[pd.DataFrame], ...]:
    warnings.filterwarnings("ignore")
    i, row = args
    r = pd.Series(row)
    perf = asap.load_asap_performance(r)
    al = asap.load_asap_alignment(r)
    idx, notes, missed, pedal = [], [], [], []
    for j, rate in enumerate(RATES):
        seed = 1000 * i + j
        q, lab = perturb(perf, al, MistakeSpec(rate=rate), seed=seed)
        key = q.performance_id
        nd = pd.DataFrame({c: q.notes[c] for c in ("onset_sec", "duration_sec", "pitch",
                                                  "velocity")})  # fmt: skip
        nd["id"] = q.notes["id"].astype(str)
        nd = pd.concat([nd, lab.notes.reset_index(drop=True)], axis=1)
        assert (nd["id"] == nd["performance_id"]).all()
        nd.insert(0, "key", key)
        notes.append(nd)
        m = lab.missed.copy()
        m.insert(0, "key", key)
        missed.append(m)
        p = pd.DataFrame(q.pedal)
        p.insert(0, "key", key)
        pedal.append(p)
        ci, cn = lab.counts(True), lab.counts(False)
        idx.append({
            "key": key, "performance_id": perf.performance_id, "piece_id": perf.piece_id,
            "performer_id": perf.performer_id, "composer": r["composer"], "title": r["title"],
            "folder": r["folder"], "xml_score": r["xml_score"],
            "midi_performance": r["midi_performance"], "score_id": r["score_id"],
            "rate": rate, "seed": seed, "n_notes": len(q.notes),
            "n_source_notes": len(perf.notes),
            "n_wrong_pitch": ci["wrong_pitch"], "n_extra": ci["extra"], "n_missed": ci["missed"],
            "n_natural_extra": cn["extra"], "n_natural_missed": cn["missed"],
        })  # fmt: skip
    return idx, notes, missed, pedal


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--max-notes", type=int, default=6000)
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--out", type=Path, default=Path("data/processed/mistakes_v1"))
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    warnings.filterwarnings("ignore")

    sel = select(asap.asap_index(), a.n, a.max_notes, a.workers)
    log.info("selected %d performances: %s", len(sel), sel["composer"].value_counts().to_dict())
    jobs = [(i, r.to_dict()) for i, (_, r) in enumerate(sel.iterrows())]
    with ProcessPoolExecutor(a.workers) as ex:
        results = list(ex.map(build_one, jobs))
    a.out.mkdir(parents=True, exist_ok=True)
    index = pd.DataFrame([x for res in results for x in res[0]])
    index.to_csv(a.out / "index.csv", index=False)
    for k, name in ((1, "notes"), (2, "missed"), (3, "pedal")):
        pd.concat([x for res in results for x in res[k]], ignore_index=True).to_parquet(
            a.out / f"{name}.parquet", index=False
        )
    spec = {
        "version": VERSION,
        "rates": list(RATES),
        "specs": {str(rate): MistakeSpec(rate=rate).to_dict() for rate in RATES},
        "seeds": "1000 * performance_index + rate_index",
        "selection": {"source": "(n)ASAP", "robust_note_alignment": 1, "repeat_paths": 1,
                      "max_notes": a.max_notes, "n": a.n, "rng_seed": 0,
                      "order": "composer round-robin, one performance per piece first"},
    }  # fmt: skip
    (a.out / "spec.json").write_text(json.dumps(spec, indent=2))
    summ = index.groupby("rate")[["n_notes", "n_wrong_pitch", "n_extra", "n_missed"]].sum()
    log.info("wrote %s\n%s", a.out, summ.to_string())


if __name__ == "__main__":
    main()
