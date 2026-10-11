"""BL-27: merge "passage not heard" run fragments and extend runs to the piece edges.

Run: ``OMP_NUM_THREADS=1 uv run python scripts/eval_not_heard_merge_bl27.py --set dev|heldout
[--workers 10] [--from-cache]``

Pre-registration: ``experiments/2026-10-10-BL-27-not-heard-merge/README.md``, section
"Pre-registration" (hash by anchor in that README).

Rules (``report.build.not_heard_runs``): ``C`` = the BL-18 run rule (no merging, the default
before BL-27); ``M`` = ``merge_gap`` 2 graded bars, every bar in between at least 50% missed
(``calibration.NOT_HEARD_GAP_MISSED_SHARE``), runs within 2 graded bars of the first / last
graded bar extended to it.

Per piece and transcriber family: 15 experts (clean tables) and 10 targets. For each target:

* **natural**: the clean transcription, tiered under rule P (R1(0) against the 15 same-family
  experts, extras not counted, as BL-18b / DF-13) with each rule's own runs left untiered;
* **truncation control** (known answer): two copies with the recording cut, ``end`` (every
  performed note from a time T on removed; T inside a graded bar drawn uniformly from 75-95% of
  the graded bars) and ``start`` (every note before T removed; bar from 5-25%). The copy is
  realigned with the clean alignment's repeat variant. Truth per bar from the clean alignment's
  expected onsets: ``not_heard`` (every graded note due on the removed side of T), ``heard``
  (every graded note due on the kept side), ``cut`` (the bar holding T). A copy is scored when
  its alignment is not suspect (match ratio at least 0.8) and at least 3 graded bars are not
  heard (a shorter gap cannot form a run under either rule).

Sets: ``dev`` = the BL-18b pieces (design data); ``heldout`` = a new draw (seed 2727) of 16
PianoCoRe pieces with at least 25 transcriptions per family and one score, excluding Henry's 5,
the BL-18 T2, BL-18b and DF-13 held-out pieces, and every transcription id used before.

Outputs (gitignored): ``data/interim/bl27/<set>_rows.pkl``, ``<set>_summary.json``.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import pickle
import sys
import warnings
import zlib
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "data" / "interim" / "bl27"
CAL = REPO / "data" / "interim" / "reports" / "calibration"
DF13 = REPO / "data" / "interim" / "df13"
HENRY = REPO / "data" / "interim" / "henry_takes"
FAMILIES = {"Transkun V2": "transkun", "Aria-AMT": "aria_amt"}
RULES = {"C": 0, "M": 2}  # merge gap in graded bars
HELDOUT_SEED = 2727
TRUNC_SEED = 27
N_PIECES = 16
N_EXPERTS = 15
N_TARGETS = 10
MIN_PER_FAMILY = 25
END_RANGE = (0.75, 0.95)
START_RANGE = (0.05, 0.25)
MIN_NOT_HEARD = 3  # a copy is scored when at least this many graded bars are not heard


def _mod(name: str, file: str):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, REPO / "scripts" / file)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


def _quiet() -> None:
    import logging

    warnings.filterwarnings("ignore")
    logging.disable(logging.WARNING)


# ----------------------------------------------------------------------------- draw


def heldout_jobs() -> tuple[list[dict], int]:
    import zipfile

    from pianolens.data.pianocore import DEFAULT_ROOT, RAW_PREFIX, RAW_ZIP, PianoCoRe

    idx = PianoCoRe().index
    tr = idx[idx["is_transcription"].astype(bool) & idx["capture_model"].isin(FAMILIES)]
    meta = json.loads((HENRY / "scores" / "scores.json").read_text())
    excl = {m["piece_id"] for m in meta.values()}
    excl |= set(json.loads((CAL / "bl18_summary.json").read_text())["t2_pieces"])
    b18b = pickle.loads((CAL / "bl18b_tables.pkl").read_bytes())["rows"]
    excl |= {r["piece"] for r in b18b}
    d13 = pickle.loads((DF13 / "heldout_rows.pkl").read_bytes())["rows"]
    excl |= {r["piece"] for r in d13}
    floor = pickle.loads((CAL / "f08c_floor_tables.pkl").read_bytes())
    b18 = pickle.loads((CAL / "bl18_tables.pkl").read_bytes())
    used = ({str(r["ref_id"]) for r in floor} | {str(r["id"]) for r in b18}
            | {str(r["id"]) for r in b18b} | {str(r["id"]) for r in d13})
    with zipfile.ZipFile(DEFAULT_ROOT / RAW_ZIP) as z:
        names = set(z.namelist())
    cnt = tr.groupby(["piece_id", "capture_model"]).size().unstack(fill_value=0)
    elig = []
    for pid, row in cnt.iterrows():
        if pid in excl or min(row.get(cm, 0) for cm in FAMILIES) < MIN_PER_FAMILY:
            continue
        sx = tr.loc[tr["piece_id"] == pid, "score_xml_path"].dropna().astype(str)
        sx = [s for s in sorted(set(sx)) if RAW_PREFIX + s in names]
        if len(sx) == 1:
            elig.append((pid, sx[0]))
    elig.sort()
    rng = np.random.default_rng(HELDOUT_SEED)
    chosen = [elig[i] for i in sorted(rng.choice(len(elig), size=N_PIECES, replace=False))]
    jobs = []
    for pid, sx in chosen:
        for cm, fam in FAMILIES.items():
            r = tr[(tr["piece_id"] == pid) & (tr["capture_model"] == cm)
                   & ~tr["id"].astype(str).isin(used)].sort_values("id")
            perm = rng.permutation(len(r))
            for j, i in enumerate(perm[:N_EXPERTS + N_TARGETS]):
                jobs.append({"piece": pid, "piece_id": pid, "family": fam,
                             "role": "expert" if j < N_EXPERTS else "target", "order": j,
                             "id": str(r.iloc[i]["id"]),
                             "midi": str(r.iloc[i]["performance_midi_path"]), "score": sx})
    from pianolens.data.pianocore import guard_jobs  # BL-35: after the draw, not before

    return guard_jobs(jobs, idx, label="BL-27 held-out"), len(elig)


def dev_jobs() -> list[dict]:
    return _mod("df13", "eval_pairing_window_df13.py").dev_jobs()


# ----------------------------------------------------------------------------- workers


def _table(ap, cr) -> pd.DataFrame:
    from pianolens.report.build import bar_error_table, bar_labels

    t = bar_error_table(cr, bar_labels(ap.score))
    t["n_correct"] = cr.bars["n_correct"].to_numpy(int)
    return t


def expert_one(job: dict) -> dict:
    _quiet()
    from pianolens.align import align_performance
    from pianolens.features.correctness import correctness

    sc, perf = _mod("bl18b", "calibrate_strong_tier_bl18b.py")._load(job)
    ap = align_performance(sc, perf)
    cr = correctness(ap)
    return {**job, "suspect": bool(cr.summary["alignment_suspect"]), "table": _table(ap, cr)}


def _truth(cr, labels: list[str], t_cut: float, side: str) -> dict[str, str]:
    """Bar label -> heard / cut / not_heard for a recording cut at ``t_cut`` (``side`` = the
    removed side: ``end`` removes onsets >= t_cut, ``start`` removes onsets < t_cut)."""
    sn = cr.score_notes
    g = sn[sn["label"].isin(["correct", "wrong_pitch", "missed"]) & (sn["measure_index"] >= 0)]
    out = {}
    for b, grp in g.groupby("measure_index"):
        e = grp["expected_onset_sec"].to_numpy(float)
        e = e[np.isfinite(e)]
        if not len(e):
            continue
        removed = e >= t_cut if side == "end" else e < t_cut
        out[labels[int(b)]] = ("not_heard" if removed.all() else "heard" if not removed.any()
                               else "cut")
    return out


def _cut_time(cr, side: str, rng: np.random.Generator) -> float | None:
    """A time inside a graded bar drawn uniformly from the side's range of graded bars."""
    sn = cr.score_notes
    g = sn[sn["label"].isin(["correct", "wrong_pitch", "missed"]) & (sn["measure_index"] >= 0)]
    first = g.groupby("measure_index")["expected_onset_sec"].min().dropna().sort_index()
    if len(first) < 10:
        return None
    lo, hi = END_RANGE if side == "end" else START_RANGE
    k = int(rng.integers(int(lo * len(first)), int(hi * len(first))))
    t0, t1 = float(first.iloc[k]), float(first.iloc[min(k + 1, len(first) - 1)])
    if t1 <= t0:
        return t0
    return float(rng.uniform(t0, t1))


def target_one(job: dict) -> dict:
    _quiet()
    import dataclasses

    from pianolens.align import align_performance
    from pianolens.features.correctness import correctness
    from pianolens.report.build import bar_labels

    sc, perf = _mod("bl18b", "calibrate_strong_tier_bl18b.py")._load(job)
    ap = align_performance(sc, perf)
    cr = correctness(ap)
    out = {**job, "suspect": bool(cr.summary["alignment_suspect"]), "table": _table(ap, cr)}
    if out["suspect"]:
        return out
    labels = bar_labels(ap.score)
    variant = str(ap.score.meta.get("unfolded") or "") or "auto"
    rng = np.random.default_rng([TRUNC_SEED, zlib.crc32(job["id"].encode())])
    out["cuts"] = {}
    for side in ("end", "start"):
        t_cut = _cut_time(cr, side, rng)
        if t_cut is None:
            continue
        notes = ap.performance.notes
        keep = notes["onset_sec"] < t_cut if side == "end" else notes["onset_sec"] >= t_cut
        if keep.sum() < 20:
            continue
        tp = dataclasses.replace(ap.performance, notes=notes[keep].copy(),
                                 performance_id=f"{ap.performance.performance_id}#{side}")
        ap2 = align_performance(sc, tp, repeats=variant)
        cr2 = correctness(ap2)
        same_variant = bar_labels(ap2.score) == labels
        out["cuts"][side] = {"t_cut": t_cut, "table": _table(ap2, cr2),
                             "truth": _truth(cr, labels, t_cut, side),
                             "same_variant": bool(same_variant),
                             "suspect": bool(cr2.summary["alignment_suspect"]),
                             "n_removed": int((~keep).sum()), "n_kept": int(keep.sum())}
    return out


# ----------------------------------------------------------------------------- evaluation


def tiers_runs(table: pd.DataFrame, experts: list[pd.DataFrame], gap: int) -> pd.DataFrame:
    """Rule P tiers per graded bar (R1(0), extras not counted), with the bars of this rule's
    runs untiered; columns label, tier, in_run, run_id."""
    from pianolens.report.build import not_heard_runs

    b18 = _mod("bl18", "calibrate_strong_tier_bl18.py")
    t = b18.tiers(table, experts, "R1(0)", None)
    g = table[table["n_score_notes"] > 0].reset_index(drop=True)
    runs = not_heard_runs(g["n_missed"].to_numpy(int), g["n_score_notes"].to_numpy(int),
                          merge_gap=gap)
    rid = np.full(len(t), -1)
    for k, r in enumerate(runs):
        rid[r] = k
    t["run_id"] = rid
    t["in_run"] = rid >= 0
    t.loc[t["in_run"], "tier"] = "none"
    for c in ("n_score_notes", "n_missed", "n_wrong_pitch", "n_correct"):
        t[c] = g[c].to_numpy(int)
    return t


def _ratio_boot(per: pd.DataFrame, num: str, den: str, num2: str, den2: str,
                n: int = 2000) -> list[float]:
    """Piece bootstrap 95% CI of num/den - num2/den2 (percentage points)."""
    rng = np.random.default_rng(0)
    vals = []
    for _ in range(n):
        s = per.iloc[rng.integers(0, len(per), len(per))]
        vals.append(100 * (s[num].sum() / s[den].sum() - s[num2].sum() / s[den2].sum()))
    return [float(np.nanquantile(vals, 0.025)), float(np.nanquantile(vals, 0.975))]


def evaluate(rows: list[dict]) -> dict:
    experts: dict[tuple, list] = {}
    for r in sorted((r for r in rows if r["role"] == "expert" and not r["suspect"]),
                    key=lambda r: r["order"]):
        experts.setdefault((r["piece"], r["family"]), []).append(r["table"])
    targets = [r for r in rows if r["role"] == "target" and not r["suspect"]]
    nat, cut_rows, added = [], [], []
    for r in targets:
        ex = experts.get((r["piece"], r["family"]), [])
        tr = {k: tiers_runs(r["table"], ex, g) for k, g in RULES.items()}
        d = {"piece": r["piece"], "family": r["family"], "id": r["id"]}
        for k, t in tr.items():
            out = t[~t["in_run"]]
            d[f"n_{k}"] = len(out)
            d[f"strong_{k}"] = int((out["tier"] == "strong").sum())
            d[f"np_{k}"] = int((out["tier"] != "none").sum())
            d[f"runs_{k}"] = int(t["run_id"].max() + 1)
            d[f"runbars_{k}"] = int(t["in_run"].sum())
            n = len(t)
            d[f"run_end_{k}"] = int(n > 0 and bool(t["in_run"].iat[-1]))
            d[f"run_start_{k}"] = int(n > 0 and bool(t["in_run"].iat[0]))
        nat.append(d)
        a = tr["M"][tr["M"]["in_run"] & ~tr["C"]["in_run"]]
        for x in a.itertuples(index=False):
            added.append({"piece": r["piece"], "family": r["family"], "id": r["id"],
                          "label": x.label, "n_score_notes": x.n_score_notes,
                          "n_missed": x.n_missed, "n_correct": x.n_correct,
                          "tier_C": str(tr["C"].loc[tr["C"]["label"] == x.label, "tier"].iat[0])})
        for side, c in (r.get("cuts") or {}).items():
            if c["suspect"]:
                cut_rows.append({"piece": r["piece"], "family": r["family"], "id": r["id"],
                                 "side": side, "suspect": True})
                continue
            cr = {"piece": r["piece"], "family": r["family"], "id": r["id"], "side": side,
                  "suspect": False, "same_variant": c["same_variant"]}
            truth = c["truth"]
            for k, g in RULES.items():
                t = tiers_runs(c["table"], ex, g)
                st = t["label"].map(truth).fillna("unknown")
                nh = st == "not_heard"
                gone = st.isin(["not_heard", "cut"])
                ids = set(t.loc[gone & t["in_run"], "run_id"])
                edge_row = len(t) - 1 if side == "end" else 0
                edge_run = int(t["run_id"].iat[edge_row]) if len(t) else -1
                cr[f"one_item_{k}"] = int(len(ids) == 1 and edge_run in ids)
                cr[f"n_items_{k}"] = len(ids)
                cr[f"nh_{k}"] = int(nh.sum())
                cr[f"nh_in_run_{k}"] = int((nh & t["in_run"]).sum())
                cr[f"nh_strong_{k}"] = int((nh & (t["tier"] == "strong")).sum())
                cr[f"nh_tiered_{k}"] = int((nh & (t["tier"] != "none")).sum())
                cr[f"heard_in_run_{k}"] = int(((st == "heard") & t["in_run"]).sum())
                cr[f"heard_{k}"] = int((st == "heard").sum())
                cr[f"heard_strong_{k}"] = int(((st == "heard") & (t["tier"] == "strong")).sum())
                cr[f"in_run_{k}"] = int(t["in_run"].sum())
                cr[f"_in_run_mask_{k}"] = t["in_run"].to_numpy()
                cr["_status"] = st.to_numpy()
            m_add = cr.pop("_in_run_mask_M") & ~cr.pop("_in_run_mask_C")
            stt = cr.pop("_status")
            cr["added_bars"] = int(m_add.sum())
            cr["added_heard"] = int((m_add & (stt == "heard")).sum())
            cr["added_cut"] = int((m_add & (stt == "cut")).sum())
            cr["added_not_heard"] = int((m_add & (stt == "not_heard")).sum())
            cut_rows.append(cr)
    nat_df, cut_df, add_df = pd.DataFrame(nat), pd.DataFrame(cut_rows), pd.DataFrame(added)
    out: dict = {"n_targets": len(targets),
                 "n_targets_suspect": sum(r["role"] == "target" and r["suspect"] for r in rows),
                 "n_experts_suspect": sum(r["role"] == "expert" and r["suspect"] for r in rows)}
    # ---- natural: rule P rates, runs
    out["natural"] = {}
    for fam in ("pooled", *FAMILIES.values()):
        g = nat_df if fam == "pooled" else nat_df[nat_df["family"] == fam]
        per = g.groupby("piece").sum(numeric_only=True)
        s = per.sum()
        d: dict = {"n_targets": int(len(g)), "n_pieces": int(len(per))}
        for k in RULES:
            d[k] = {"P_strong": float(s[f"strong_{k}"] / s[f"n_{k}"]),
                    "P_notable_plus": float(s[f"np_{k}"] / s[f"n_{k}"]),
                    "n_bars_outside_runs": int(s[f"n_{k}"]), "n_runs": int(s[f"runs_{k}"]),
                    "n_run_bars": int(s[f"runbars_{k}"]),
                    "targets_with_run": int((g[f"runs_{k}"] > 0).sum()),
                    "runs_touching_end": int(s[f"run_end_{k}"]),
                    "runs_touching_start": int(s[f"run_start_{k}"])}
        d["delta_strong_pt"] = 100 * (d["M"]["P_strong"] - d["C"]["P_strong"])
        d["delta_notable_plus_pt"] = 100 * (d["M"]["P_notable_plus"] - d["C"]["P_notable_plus"])
        d["delta_strong_boot95_pt"] = _ratio_boot(per, "strong_M", "n_M", "strong_C", "n_C")
        d["delta_np_boot95_pt"] = _ratio_boot(per, "np_M", "n_M", "np_C", "n_C")
        a = add_df if fam == "pooled" or not len(add_df) else add_df[add_df["family"] == fam]
        d["added_bars"] = int(len(a))
        if len(a):
            sh = a["n_correct"] / a["n_score_notes"]
            d["added_correct_share"] = {"max": float(sh.max()), "median": float(sh.median()),
                                        "mean": float(sh.mean())}
            d["added_tier_C"] = a["tier_C"].value_counts().to_dict()
        out["natural"][fam] = d
    # ---- truncation control
    out["truncation"] = {}
    ok = cut_df[~cut_df["suspect"]] if len(cut_df) else cut_df
    out["truncation"]["n_copies"] = int(len(cut_df))
    out["truncation"]["n_suspect_copies"] = int(cut_df["suspect"].sum()) if len(cut_df) else 0
    if len(ok):
        out["truncation"]["n_short_gap_copies"] = int((ok["nh_C"] < MIN_NOT_HEARD).sum())
        ok = ok[ok["nh_C"] >= MIN_NOT_HEARD]
    for side in ("end", "start", "both"):
        for fam in ("pooled", *FAMILIES.values()):
            g = ok if side == "both" else ok[ok["side"] == side]
            g = g if fam == "pooled" else g[g["family"] == fam]
            if not len(g):
                continue
            d = {"n_copies": int(len(g)), "same_variant": float(g["same_variant"].mean())}
            for k in RULES:
                d[k] = {"one_item": float(g[f"one_item_{k}"].mean()),
                        "n_items_dist": g[f"n_items_{k}"].value_counts().sort_index()
                        .to_dict(),
                        "not_heard_coverage": float(g[f"nh_in_run_{k}"].sum()
                                                    / max(1, g[f"nh_{k}"].sum())),
                        "not_heard_strong": float(g[f"nh_strong_{k}"].sum()
                                                  / max(1, g[f"nh_{k}"].sum())),
                        "not_heard_tiered": float(g[f"nh_tiered_{k}"].sum()
                                                  / max(1, g[f"nh_{k}"].sum())),
                        "heard_in_run": int(g[f"heard_in_run_{k}"].sum()),
                        "heard_bars": int(g[f"heard_{k}"].sum()),
                        "heard_strong": int(g[f"heard_strong_{k}"].sum())}
            d["added_bars"] = int(g["added_bars"].sum())
            d["added_heard"] = int(g["added_heard"].sum())
            d["added_cut"] = int(g["added_cut"].sum())
            d["added_not_heard"] = int(g["added_not_heard"].sum())
            d["delta_one_item_pt"] = 100 * (d["M"]["one_item"] - d["C"]["one_item"])
            per = g.groupby("piece")[["one_item_M", "one_item_C"]].sum()
            per["n"] = g.groupby("piece").size()
            d["delta_one_item_boot95_pt"] = _ratio_boot(per, "one_item_M", "n", "one_item_C", "n")
            out["truncation"][f"{side}:{fam}"] = d
    out["_tables"] = {"natural": nat_df, "truncation": cut_df, "added": add_df}
    return out


# ----------------------------------------------------------------------------- main


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", choices=("dev", "heldout"), required=True)
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--from-cache", action="store_true")
    ap.add_argument("--experts-from-df15", action="store_true",
                    help="dev only: expert tables from data/interim/df15/dev_rows.pkl (the same "
                         "pipeline with duplicate resolution on) instead of realigning them")
    args = ap.parse_args()
    _quiet()
    OUT.mkdir(parents=True, exist_ok=True)
    cache = OUT / f"{args.set}_rows.pkl"
    if args.from_cache:
        blob = pickle.loads(cache.read_bytes())
    else:
        jobs, n_elig = (dev_jobs(), None) if args.set == "dev" else heldout_jobs()
        print(len(jobs), "jobs;", n_elig, "eligible pieces", flush=True)
        rows, failed = [], []
        if args.experts_from_df15 and args.set == "dev":
            d15 = pickle.loads((REPO / "data" / "interim" / "df15" / "dev_rows.pkl").read_bytes())
            keys = ("piece", "piece_id", "family", "role", "order", "id", "midi", "score")
            rows = [{**{k: r[k] for k in keys}, "suspect": r["suspect"], "table": r["tables"]["on"]}
                    for r in d15 if r["role"] == "expert"]
            jobs = [j for j in jobs if j["role"] == "target"]
        with ProcessPoolExecutor(args.workers) as ex:
            futs = {ex.submit(expert_one if j["role"] == "expert" else target_one, j): j
                    for j in jobs}
            for k, fu in enumerate(as_completed(futs)):
                try:
                    rows.append(fu.result())
                except Exception as e:  # noqa: BLE001 - count failures
                    failed.append((futs[fu]["id"], repr(e)[:200]))
                if k % 50 == 0:
                    print("done", k, flush=True)
        blob = {"rows": rows, "n_eligible_pieces": n_elig, "failed": failed}
        cache.write_bytes(pickle.dumps(blob))
    rows = blob["rows"]
    res = evaluate(rows)
    tabs = res.pop("_tables")
    for k, t in tabs.items():
        t.to_csv(OUT / f"{args.set}_{k}.csv", index=False)
    summ = {"set": args.set, "n_eligible_pieces": blob.get("n_eligible_pieces"),
            "failed": blob.get("failed", []), "pieces": sorted({r["piece"] for r in rows}),
            "n_rows": len(rows), **res}
    (OUT / f"{args.set}_summary.json").write_text(json.dumps(summ, indent=1, default=float))
    print(json.dumps({k: v for k, v in summ.items() if k != "pieces"}, indent=1,
                     default=float))


if __name__ == "__main__":
    main()
