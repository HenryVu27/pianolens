"""F-08b calibration: how often does the recurring-error rule fire on expert playing?

Run: ``uv run python scripts/calibrate_recurring_f08b.py [--workers 10] [--n-pieces 30]``

The practice report promotes a bar to a "strong" correctness item when the same error (same
kind, same score note or same extra pitch; ``pianolens.report.build.error_signatures``) is found
in the same bar in at least ``min_takes`` takes. "Strong" means beyond the 99th percentile of
expert bars (DECISIONS 2026-09-28, after F-06), so on clean expert takes the rule must fire in
about 1% of bars or less.

Expert pseudo-takes: for ASAP pieces with at least three performances that take the same repeat
path (same performed-score note count) and align cleanly (not ``alignment_suspect``), three
different pianists stand in for three takes. Their real slips are independent, while alignment
and checker artefacts that depend on the score (ornaments, chords, trills) recur, as they would
across one player's takes. A single player's habits (e.g. the same extra note every time) are
not covered; see the caveat in ``docs/specs/report-validation.md``.

For each rule variant (kinds x min_takes, with 2 or 3 takes; without and with the expert
filter, ``build.expert_error_keys`` over the piece's other ASAP performances on the same repeat
path) it reports the share of bars promoted.
Output: ``data/interim/reports/calibration/recurring_{bars.parquet,summary.json}``.
"""

from __future__ import annotations

import argparse
import itertools
import json
import pickle
import warnings
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "data" / "interim" / "reports" / "calibration"
KIND_SETS = {"all": ("wrong_pitch", "missed", "extra"), "wrong_pitch": ("wrong_pitch",),
             "wrong+extra": ("wrong_pitch", "extra"), "wrong+missed": ("wrong_pitch", "missed")}


def run_piece(piece_id: str, rows: list[dict]) -> list[dict]:
    """Align up to 10 performances of one piece; keep those on the most common repeat path
    (at least 3); signatures."""
    warnings.filterwarnings("ignore")
    import logging

    logging.disable(logging.WARNING)
    from pianolens.align import align_performance
    from pianolens.data import asap
    from pianolens.features.correctness import correctness
    from pianolens.report.build import bar_labels, error_signatures

    score = asap.load_asap_score(pd.Series(rows[0]))
    got: dict[int, list] = {}
    for r in rows[:10]:
        r = pd.Series(r)
        ap = align_performance(score, asap.load_asap_performance(r))
        cr = correctness(ap)
        if cr.summary["alignment_suspect"]:
            continue
        labels = bar_labels(ap.score)
        n = len(ap.score.notes)
        got.setdefault(n, []).append((str(r["performance_id"]), labels,
                                      error_signatures(cr, labels), cr.summary["error_rate"]))
    best = max(got.values(), key=len) if got else []
    if len(best) < 3:
        return []
    return [{"piece_id": piece_id, "performance_id": pid, "labels": labels, "sig": sig,
             "error_rate": er} for pid, labels, sig, er in best]


def promoted_share(takes: list[dict], kinds: tuple[str, ...], min_takes: int,
                   experts: list[dict] = ()) -> tuple[int, int]:
    from pianolens.report.build import expert_error_keys, recurring_errors

    ex = expert_error_keys([e["sig"] for e in experts]) if experts else None
    rec = recurring_errors([t["sig"] for t in takes], min_takes, kinds, exclude=ex)
    labels = takes[0]["labels"]
    return sum(lab in rec for lab in labels), len(labels)


def main() -> None:
    warnings.filterwarnings("ignore")
    from pianolens.data import asap

    a = argparse.ArgumentParser()
    a.add_argument("--workers", type=int, default=10)
    a.add_argument("--n-pieces", type=int, default=30)
    a.add_argument("--from-cache", action="store_true")
    args = a.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    idx = asap.asap_index()
    cnt = idx.groupby("piece_id").size()
    pieces = sorted(cnt[cnt >= 3].index)
    rng = np.random.default_rng(0)
    pieces = list(rng.choice(pieces, min(args.n_pieces, len(pieces)), replace=False))
    cache = OUT / "recurring_signatures.pkl"
    if args.from_cache and cache.is_file():
        groups = pickle.loads(cache.read_bytes())
    else:
        groups = []
        with ProcessPoolExecutor(max_workers=args.workers) as ex:
            futs = {}
            for p in pieces:
                rows = idx[idx["piece_id"] == p].sample(frac=1, random_state=0).to_dict(
                    "records")
                futs[ex.submit(run_piece, p, rows)] = p
            for f in as_completed(futs):
                try:
                    g = f.result()
                except Exception as e:  # noqa: BLE001
                    print("FAIL", futs[f], repr(e)[:200])
                    continue
                if g:
                    groups.append(g)
        cache.write_bytes(pickle.dumps(groups))
    out_rows = []
    for g in groups:
        takes3, experts = g[:3], g[3:]
        filters = {"none": []}
        if len(experts) >= 2:
            filters["experts_2"] = experts[:2]
            filters["experts_all"] = experts
        for fname, ex_list in filters.items():
            for name, kinds in KIND_SETS.items():
                for mt, nt in ((2, 2), (2, 3), (3, 3)):
                    # every choice of takes (same repeat path, so the same bar labels)
                    for combo in itertools.combinations(range(3), nt):
                        k, n = promoted_share([takes3[i] for i in combo], kinds, mt, ex_list)
                        out_rows.append({"piece_id": g[0]["piece_id"], "filter": fname,
                                         "n_experts": len(ex_list), "kinds": name,
                                         "min_takes": mt, "n_takes": nt,
                                         "n_promoted": k, "n_bars": n})
    df = pd.DataFrame(out_rows)
    df.to_parquet(OUT / "recurring_bars.parquet")
    n_ex = [len(g) - 3 for g in groups]
    summ = {"n_pieces": len(groups), "n_pieces_with_expert_filter": int(sum(x >= 2 for x in n_ex)),
            "n_experts_median": float(np.median([x for x in n_ex if x >= 2] or [0])),
            "error_rate_median": float(np.median([t["error_rate"] for g in groups for t in g])),
            "variants": {}}
    fp = set(df.loc[df["filter"] != "none", "piece_id"])
    for (fname, name, mt, nt), d in df.groupby(["filter", "kinds", "min_takes", "n_takes"]):
        per_piece = d.groupby("piece_id").apply(lambda x: x["n_promoted"].sum() /
                                                x["n_bars"].sum())
        v = {"share_bars_promoted": float(d["n_promoted"].sum() / d["n_bars"].sum()),
             "piece_median": float(per_piece.median()), "piece_max": float(per_piece.max()),
             "n_pieces": len(per_piece),
             "n_pieces_above_1pct": int((per_piece > 0.01).sum())}
        if fname == "none":  # same pieces as the filtered variants, for a like-for-like view
            dd = d[d["piece_id"].isin(fp)]
            v["share_bars_promoted_filter_pieces"] = float(dd["n_promoted"].sum() /
                                                           max(dd["n_bars"].sum(), 1))
        summ["variants"][f"{fname}|{name}|min{mt}|of{nt}"] = v
    (OUT / "recurring_summary.json").write_text(json.dumps(summ, indent=1))
    print(json.dumps(summ, indent=1))


if __name__ == "__main__":
    main()
