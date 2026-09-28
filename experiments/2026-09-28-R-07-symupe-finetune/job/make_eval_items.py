"""R-07 evaluation sets (runs in any env with pianolens installed).

Each set directory gets:
  items/<stem>__real.npz, items/<stem>__<variant>.npz   real rendition + every pre-registered
                                                        variant (expression_data.VARIANTS),
                                                        same conditioning and notes
  items/<stem>__ext_deadpan.npz                         P only: PercePiano Score renditions
  gen_items/<passage>.npz                               score-only generation items
  manifest.csv                                          stem, kind, passage, work, performer

Two sources:
  --from-r06 DIR --set P|V|A   the R-06 artifacts (small derived data; copy
                               experiments/2026-09-27-R-06-expression-model-h2h/artifacts/{items,
                               gen_items,manifest.parquet} if running on the GPU box)
  --from-prep DATA --roles R10u R10s   test pieces built by prep_data.py; majority score per
                               piece; first --max-notes distinct score notes (default 3000)

    python make_eval_items.py --from-r06 R06_ART --set P --out OUT/eval_sets/P
    python make_eval_items.py --from-prep OUT/data --roles R10u --out OUT/eval_sets/R10u
"""

from __future__ import annotations

import argparse
import json
import shutil
import zlib
from pathlib import Path

import numpy as np
import pandas as pd

from pianolens.models.expression_data import VARIANTS, item_variants, load_item, save_item

SEED = 20260928


def _slug(s: str) -> str:
    return "".join(c if c.isalnum() or c in "-." else "_" for c in s)


def write_variants(real: dict, stem: str, items: Path, base: dict, names) -> list[dict]:
    rows = []
    save_item(items / f"{stem}__real.npz", real)
    rows.append({**base, "stem": stem, "kind": "real"})
    seed = SEED + zlib.crc32(stem.encode()) % 1_000_003
    for name, v in item_variants(real, seed, names).items():
        save_item(items / f"{stem}__{name}.npz", v)
        rows.append({**base, "stem": stem, "kind": name})
    return rows


def from_r06(art: Path, set_name: str, out: Path, names, limit: int) -> list[dict]:
    man = pd.read_parquet(art / "manifest.parquet")
    man = man[(man["set"] == set_name) & man["item"].notna() & (man["item"] != "")]
    if limit:
        keep = sorted(man["passage"].unique())[:limit]
        man = man[man["passage"].isin(keep)]
    items = out / "items"
    rows = []
    for r in man[man["kind"] == "real"].itertuples():
        it = load_item(art / "items" / set_name / f"{r.item}.npz")
        stem = r.item[: -len("__real")]
        base = {"set": set_name, "passage": r.passage, "work": r.piece_id,
                "performer": r.performer_id, "piece_id": r.piece_id}
        rows += write_variants(it, stem, items, base, names)
    for r in man[man["kind"] == "ext_deadpan"].itertuples():
        stem = r.item[: -len("__ext_deadpan")]
        shutil.copy(art / "items" / set_name / f"{r.item}.npz", items / f"{stem}__ext_deadpan.npz")
        rows.append({"set": set_name, "passage": r.passage, "work": r.piece_id,
                     "performer": r.performer_id, "piece_id": r.piece_id, "stem": stem,
                     "kind": "ext_deadpan"})
    (out / "gen_items").mkdir(parents=True, exist_ok=True)
    for p in sorted(man["passage"].unique()):
        src = art / "gen_items" / set_name / f"{_slug(p)}.npz"
        if src.exists():
            shutil.copy(src, out / "gen_items" / src.name)
    return rows


def _cap(it: dict, cutoff: float) -> dict:
    k = it["score_onset_q"] <= cutoff + 1e-9
    out = dict(it)
    for key in ("score_onset_q", "score_dur_q", "pitch", "perf_onset_sec", "perf_dur_sec",
                "velocity", "score_id"):
        out[key] = it[key][k]
    return out


def from_prep(data: Path, roles, out: Path, names, max_notes: int, limit: int) -> list[dict]:
    man = pd.read_parquet(data / "manifest.parquet")
    man = man[(man["item"] != "") & (man["split"] == "test") & man["role"].isin(roles)]
    pieces = sorted(man["piece_id"].unique())[: limit or None]
    items = out / "items"
    (out / "gen_items").mkdir(parents=True, exist_ok=True)
    rows = []
    for pid in pieces:
        g = man[man["piece_id"] == pid]
        key = g["score_key"].value_counts().idxmax()  # majority score (R-02 rule)
        g = g[g["score_key"] == key]
        its = [load_item(data / p) for p in g["item"]]
        # union of matched score notes over renditions -> the generation score
        sid = np.concatenate([i["score_id"] for i in its])
        on = np.concatenate([i["score_onset_q"] for i in its])
        du = np.concatenate([i["score_dur_q"] for i in its])
        pi = np.concatenate([i["pitch"] for i in its])
        _, first = np.unique(sid, return_index=True)
        order = first[np.lexsort((pi[first], on[first]))]
        cutoff = float(on[order][min(len(order), max_notes) - 1])
        order = order[on[order] <= cutoff + 1e-9]
        z = np.zeros(len(order))
        gen = {"score_onset_q": on[order], "score_dur_q": du[order], "pitch": pi[order],
               "perf_onset_sec": z, "perf_dur_sec": z, "velocity": z.astype(int),
               "pedal": np.zeros((0, 2)), "score_id": sid[order],
               "spq_cond": float(np.median([i["spq_cond"] for i in its])),
               "vel_cond": float(np.median([i["vel_cond"] for i in its])),
               "origin": float(its[0]["origin"]), "ts": its[0]["ts"]}
        save_item(out / "gen_items" / f"{_slug(pid)}.npz", gen)
        for it, r in zip(its, g.itertuples(), strict=True):
            it = _cap(it, cutoff)
            if len(it["pitch"]) < 16:
                continue
            stem = _slug(f"{pid}__{r.row_id}")[:150]
            base = {"set": ",".join(roles), "passage": pid, "work": r.work,
                    "performer": r.source_performance_id, "piece_id": pid}
            rows += write_variants(it, stem, items, base, names)
    return rows


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-r06")
    ap.add_argument("--set")
    ap.add_argument("--from-prep")
    ap.add_argument("--roles", nargs="+", default=["R10u"])
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-notes", type=int, default=3000)
    ap.add_argument("--variants", nargs="+", default=list(VARIANTS))
    ap.add_argument("--limit", type=int, default=0, help="first N passages / pieces (dry run)")
    a = ap.parse_args(argv)
    out = Path(a.out)
    (out / "items").mkdir(parents=True, exist_ok=True)
    if a.from_r06:
        rows = from_r06(Path(a.from_r06), a.set, out, a.variants, a.limit)
    else:
        rows = from_prep(Path(a.from_prep), a.roles, out, a.variants, a.max_notes, a.limit)
    man = pd.DataFrame(rows)
    man.to_csv(out / "manifest.csv", index=False)
    info = {"items": len(man), "by_kind": man["kind"].value_counts().to_dict(),
            "passages": int(man["passage"].nunique()),
            "gen_items": len(list((out / "gen_items").glob("*.npz")))}
    (out / "make_meta.json").write_text(json.dumps({**vars(a), **info}, indent=1))
    print(json.dumps(info), flush=True)


if __name__ == "__main__":
    main()
