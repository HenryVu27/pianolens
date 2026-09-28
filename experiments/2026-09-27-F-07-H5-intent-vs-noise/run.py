"""F-07 / H5 step 1: per (piece, pianist) group of PianoCoRe tier A takes, decompose the
channels into take-consistent and take-specific parts and score both against the score basis.

Writes ``artifacts/groups.jsonl`` (one line per group, resumable), ``artifacts/pairs.jsonl``
(pairwise take correlations used for de-duplication). See README.md.

    uv run python experiments/2026-09-27-F-07-H5-intent-vs-noise/run.py --workers 8
"""

from __future__ import annotations

import argparse
import json
import os
import time
import warnings
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ART = HERE / "artifacts"
THRESHOLDS = (0.98, 0.95, 0.90)
PRIMARY_T = 0.98
MAX_TAKES = 6
MIN_COVERAGE = 0.80
SEED = 0

_PC = None


def _loader():
    global _PC
    if _PC is None:
        from pianolens.data.pianocore import PianoCoRe

        _PC = PianoCoRe()
    return _PC


def _components(ids: list[str], links: list[tuple[str, str]]) -> list[list[str]]:
    parent = {i: i for i in ids}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, b in links:
        parent[find(a)] = find(b)
    comp: dict[str, list[str]] = {}
    for i in ids:
        comp.setdefault(find(i), []).append(i)
    return list(comp.values())


def process_group(key: tuple[str, str], rows: list[dict], n_match: dict[str, int]) -> dict:
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    warnings.simplefilter("ignore")
    from pianolens.features.score_basis import score_basis
    from pianolens.features.takes import TakesConfig, decompose_takes, take_structure
    from pianolens.features.tempo import tempo_model

    t0 = time.time()
    piece, performer = key
    out: dict = {"piece_id": piece, "performer_id": performer, "n_rows": len(rows),
                 "errors": []}
    pc = _loader()
    aps, tempos, ids = [], [], []
    for r in rows:
        try:
            ap = pc.load(pd.Series(r))
            tc = tempo_model(ap)
        except Exception as e:  # noqa: BLE001 - count and continue
            out["errors"].append(f"{r['id']}: {e!r}"[:300])
            continue
        aps.append(ap)
        tempos.append(tc)
        ids.append(r["id"])
    out["n_loaded"] = len(aps)
    if len(aps) < 2:
        out["status"] = "lt2_loaded"
        return out
    basis = score_basis(aps[0].score)
    tcfg = TakesConfig()
    full = decompose_takes(aps, bases=basis, tempos=tempos, take_ids=ids)
    pr = full.pairs[full.pairs["channel"].isin(["timing", "tempo"])]
    pw = pr.pivot_table(index=["take_a", "take_b"], columns="channel", values="r").reset_index()
    out["pairs"] = pw.to_dict("records")
    idx = {t: i for i, t in enumerate(ids)}
    out["by_threshold"] = {}
    prev_kept: tuple | None = None
    prev_res: dict | None = None
    for thr in THRESHOLDS:
        links = [(a, b) for a, b, rt, rp in zip(pw["take_a"], pw["take_b"],
                                                 pw.get("timing", np.nan), pw.get("tempo", np.nan),
                                                 strict=True)
                 if (np.isfinite(rt) and rt > thr) or (np.isfinite(rp) and rp > thr)]
        comps = _components(ids, links)
        keep = sorted(max(c, key=lambda t: (n_match.get(t, 0), t)) for c in comps)
        n_after_dedup = len(keep)
        if len(keep) > MAX_TAKES:
            keep = sorted(np.random.default_rng(SEED).choice(keep, MAX_TAKES, replace=False))
        kept = tuple(keep)
        if kept == prev_kept and prev_res is not None:
            out["by_threshold"][str(thr)] = {**prev_res, "n_after_dedup": n_after_dedup}
            continue
        res: dict = {"n_after_dedup": n_after_dedup, "kept": list(kept), "k": len(kept)}
        if len(kept) >= 2:
            sub = [idx[t] for t in kept]
            dec = decompose_takes([aps[i] for i in sub], bases=basis,
                                  tempos=[tempos[i] for i in sub], take_ids=list(kept))
            st = take_structure(dec, tcfg)
            summ = dec.summary.drop(columns=[c for c in dec.summary.columns
                                             if c.startswith("level_")])
            res["summary"] = summ.to_dict("records")
            res["structure"] = st.to_dict("records")
        out["by_threshold"][str(thr)] = res
        prev_kept, prev_res = kept, res
    out["status"] = "ok"
    out["sec"] = time.time() - t0
    return out


def _jsonable(o):
    if isinstance(o, dict):
        return {str(k): _jsonable(v) for k, v in o.items()}
    if isinstance(o, list | tuple):
        return [_jsonable(v) for v in o]
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.floating | float):
        return None if not np.isfinite(o) else float(o)
    if isinstance(o, np.bool_):
        return bool(o)
    return o


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()
    ART.mkdir(parents=True, exist_ok=True)
    from pianolens.data.pianocore import pianocore_index
    from pianolens.data.pianocore_cache import load_performances

    t0 = time.time()
    perf = load_performances()
    perf["coverage"] = perf["n_match"] / perf["n_score_notes"]
    cov = dict(zip(perf["pianocore_row_id"], perf["coverage"], strict=True))
    n_match = dict(zip(perf["pianocore_row_id"], perf["n_match"].astype(int), strict=True))
    idx = pianocore_index(tier="a")
    idx = idx[idx["performer"].fillna("").str.strip() != ""].copy()
    from pianolens.data.pianocore import pianocore_performer_id

    idx["performer_id"] = [pianocore_performer_id(r) for _, r in idx.iterrows()]
    idx["coverage"] = idx["id"].map(cov)
    n_groups_all = int((idx.groupby(["piece_id", "performer_id"]).size() >= 2).sum())
    q = idx[idx["coverage"] >= MIN_COVERAGE]
    sizes = q.groupby(["piece_id", "performer_id"]).size()
    keys = [k for k, n in sizes.items() if n >= 2]
    print(f"groups with >=2 named takes: {n_groups_all}; after coverage >= {MIN_COVERAGE}: "
          f"{len(keys)} ({time.time() - t0:.0f} s)", flush=True)
    meta = {"n_groups_named_ge2": n_groups_all, "n_groups_after_coverage": len(keys),
            "n_takes_after_coverage": int(sizes[sizes >= 2].sum()),
            "min_coverage": MIN_COVERAGE, "thresholds": THRESHOLDS, "max_takes": MAX_TAKES,
            "seed": SEED}
    (ART / "meta.json").write_text(json.dumps(meta, indent=1))
    out_path = ART / "groups.jsonl"
    done = set()
    if out_path.exists():
        for line in out_path.read_text().splitlines():
            d = json.loads(line)
            done.add((d["piece_id"], d["performer_id"]))
    keys = [k for k in keys if k not in done]
    if args.limit:
        keys = keys[: args.limit]
    cols = list(q.columns)
    grouped = {k: g for k, g in q.groupby(["piece_id", "performer_id"])}
    print(f"to do: {len(keys)}", flush=True)
    n = 0
    with ProcessPoolExecutor(args.workers) as ex, out_path.open("a") as fh:
        futs = {ex.submit(process_group, k,
                          [dict(zip(cols, r, strict=True)) for r in
                           grouped[k].itertuples(index=False)],
                          {i: n_match.get(i, 0) for i in grouped[k]["id"]}): k for k in keys}
        for f in as_completed(futs):
            k = futs[f]
            try:
                d = f.result()
            except Exception as e:  # noqa: BLE001
                d = {"piece_id": k[0], "performer_id": k[1], "status": f"crash {e!r}"[:300]}
            fh.write(json.dumps(_jsonable(d)) + "\n")
            fh.flush()
            n += 1
            if n % 50 == 0:
                print(f"{n}/{len(keys)} {time.time() - t0:.0f} s", flush=True)
    print(f"done {n} in {time.time() - t0:.0f} s", flush=True)


if __name__ == "__main__":
    main()
