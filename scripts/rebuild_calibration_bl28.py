"""BL-28: rebuild the cached expert tables and recompute the report's calibration constants with
the current correctness checker.

Run (after ``scripts/eval_duplicate_matches_df15.py --set keysensor|asap|floor``):
``OMP_NUM_THREADS=1 uv run python scripts/rebuild_calibration_bl28.py [--workers 10]
[--from-cache] [--write-floor]``

Current checker: DF-15 duplicate resolution on, its same-pitch re-match off, BL-26 / BL-33 score
loading (tremolo expansion, left-hand chord move), BL-25 fast-repeat counts in every table. The
per-bar tables come from the DF-15 caches (``data/interim/df15/<set>_rows.pkl``, setting "on"),
which align with exactly this code; only what those sets lack is aligned here (ASAP performances
without an nASAP alignment, needed as F-08c experts, and the D-08 mistake copies of rates 0.02 /
0.05 / 0.10 for the F-08c recall).

Recomputed, old (constants in ``report/calibration.py`` and the cached
``f08c_floor_tables.pkl``) vs new:

* F-08 (``calibrate_report_f08.py``): every ``CORRECTNESS_EXPERT_BARS`` value, including the
  missed-only limits, from the 100 clean D-08 copies;
* F-08c (``calibrate_expert_check_f08c.py``): key-sensor expert bars global -> checked
  (q80 / q99), D-08 recall at rate 0.05, transcribed floor global -> checked (extras not counted);
* A-01 floor: ``TRANSCRIBED_STRONG_LIMITS`` (family q99), rule P and P + BL-25 clean strong /
  notable+ per family (leave-one-out), "passage not heard" run counts.

``--write-floor`` replaces ``data/interim/reports/calibration/f08c_floor_tables.pkl`` with the
new tables (the old file is kept as ``f08c_floor_tables_pre_bl28.pkl``). Outputs (gitignored):
``data/interim/bl28/``.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import pickle
import shutil
import sys
import warnings
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
CAL = REPO / "data" / "interim" / "reports" / "calibration"
DF15 = REPO / "data" / "interim" / "df15"
OUT = REPO / "data" / "interim" / "bl28"
MISTAKES = REPO / "data" / "processed" / "mistakes_v1"


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


# ----------------------------------------------------------------------------- tables


def _asap_extra_one(perf_id: str) -> dict:
    f08c = _mod("f08c", "calibrate_expert_check_f08c.py")
    return f08c.asap_one(perf_id)


def _d08_one(key: str, clean_key: str) -> dict:
    f08c = _mod("f08c", "calibrate_expert_check_f08c.py")
    if "get" not in f08c._STATE:
        f08c._d08_init()
    return f08c.d08_one(key, clean_key)


def build_tables(workers: int) -> dict:
    """Per-bar tables of every set, current checker."""
    from pianolens.data import asap
    from pianolens.report import calibration as cal

    ks = pickle.loads((DF15 / "keysensor_rows.pkl").read_bytes())
    ar = pickle.loads((DF15 / "asap_rows.pkl").read_bytes())
    fl = pickle.loads((DF15 / "floor_rows.pkl").read_bytes())
    aidx = asap.asap_index()
    midi = dict(zip(aidx["performance_id"], aidx["midi_performance"], strict=True))
    asap_rows = [{"performance_id": r["key"], "piece_id": r["piece"], "midi": midi[r["key"]],
                  "suspect": r["suspect"], "table": r["tables"]["on"]} for r in ar]
    index = pd.read_csv(MISTAKES / "index.csv", keep_default_na=False)
    per_piece = aidx.groupby("piece_id").size()
    clean = index[index["rate"].astype(float) == 0.0]
    covered = clean[clean["piece_id"].map(per_piece).fillna(0) >= cal.EXPERT_CHECK_MIN_REFS + 1]
    pieces = sorted(covered["piece_id"].unique())
    have = {r["performance_id"] for r in asap_rows}
    missing = [p for p in aidx[aidx["piece_id"].isin(pieces)]["performance_id"] if p not in have]
    ck = dict(zip(clean["performance_id"], clean["key"], strict=True))
    d08_jobs = [(k, ck[p]) for k, p, rt in zip(index["key"], index["performance_id"],
                                               index["rate"].astype(float), strict=True)
                if p in set(covered["performance_id"]) and rt > 0]
    print(len(missing), "ASAP performances without ground truth;", len(d08_jobs), "D-08 copies",
          flush=True)
    d08_rows, failed = [], []
    with ProcessPoolExecutor(workers) as ex:
        futs = {ex.submit(_asap_extra_one, p): ("asap", p) for p in missing}
        futs.update({ex.submit(_d08_one, k, c): ("d08", k) for k, c in d08_jobs})
        for fu in as_completed(futs):
            kind, k = futs[fu]
            try:
                r = fu.result()
            except Exception as e:  # noqa: BLE001 - count failures
                failed.append((kind, k, repr(e)[:200]))
                continue
            (asap_rows if kind == "asap" else d08_rows).append(r)
    # clean D-08 copies (rate 0) from the DF-15 keysensor set
    k_idx = index.set_index("key")
    for r in ks:
        d08_rows.append({"key": r["key"], "performance_id": k_idx.loc[r["key"], "performance_id"],
                         "piece_id": r["piece"], "rate": 0.0, "suspect": r["suspect"],
                         "table": r["tables"]["on"], "injected_bars": []})
    floor_rows = [{"take": r["take"], "transcriber": r["transcriber"], "ref_id": r["ref_id"],
                   "suspect": r["suspect"], "table": r["tables"]["on"],
                   "n_wrong": r["counts"]["on"]["n_wrong_pitch"],
                   "n_graded": r["counts"]["on"]["n_score_notes"]} for r in fl]
    return {"asap": asap_rows, "d08": d08_rows, "floor": floor_rows, "pieces": pieces,
            "keysensor_clean": [{"key": r["key"], "suspect": r["suspect"],
                                 "table": r["tables"]["on"]} for r in ks],
            "failed": failed}


# ----------------------------------------------------------------------------- constants


def f08_constants(rows: list[dict]) -> dict:
    """``calibrate_report_f08.py`` quantities from clean expert tables (bars with graded notes)."""
    bars = pd.concat([r["table"].assign(key=r["key"]) for r in rows if not r["suspect"]],
                     ignore_index=True)
    bars = bars[bars["n_score_notes"] > 0].copy()
    bars["n_missed_extra"] = bars["n_missed"] + bars["n_extra"]
    bars["n_errors"] = bars["n_wrong_pitch"] + bars["n_missed_extra"]
    me = bars["n_missed_extra"] / bars["n_score_notes"]
    mo = bars["n_missed"] / bars["n_score_notes"]
    per = bars.groupby("key")[["n_errors", "n_score_notes"]].sum()
    er = per["n_errors"] / per["n_score_notes"]
    share = bars.groupby("key")["n_errors"].apply(lambda x: (x > 0).mean())
    return {"n_performances": int(bars["key"].nunique()), "n_bars": int(len(bars)),
            "wrong_pitch_q95": float(np.quantile(bars["n_wrong_pitch"], 0.95)),
            "wrong_pitch_q99": float(np.quantile(bars["n_wrong_pitch"], 0.99)),
            "missed_extra_per_note_q95": float(np.quantile(me, 0.95)),
            "missed_extra_per_note_q99": float(np.quantile(me, 0.99)),
            "share_bars_with_error_median": float(np.median(share)),
            "error_rate_q50": float(np.quantile(er, 0.5)),
            "error_rate_q95": float(np.quantile(er, 0.95)),
            "error_rate_q99": float(np.quantile(er, 0.99)),
            "missed_per_note_q95": float(np.quantile(mo, 0.95)),
            "missed_per_note_q99": float(np.quantile(mo, 0.99)),
            "wrong_share_ge1": float((bars["n_wrong_pitch"] >= 1).mean()),
            "wrong_share_ge2": float((bars["n_wrong_pitch"] >= 2).mean()),
            "wrong_share_ge3": float((bars["n_wrong_pitch"] >= 3).mean()),
            "share_bars_with_missed": float((bars["n_missed"] > 0).mean())}


def _with_limits(f08: dict):
    """Context: tier with the given global limits instead of calibration.py's."""
    from pianolens.report import calibration as cal

    class Ctx:
        def __enter__(self):
            self.old = dict(cal.CORRECTNESS_EXPERT_BARS)
            cal.CORRECTNESS_EXPERT_BARS.update({k: v for k, v in f08.items()
                                                if k in self.old})
            return self

        def __exit__(self, *a):
            cal.CORRECTNESS_EXPERT_BARS.clear()
            cal.CORRECTNESS_EXPERT_BARS.update(self.old)

    return Ctx()


def f08c_keysensor(asap_rows: list[dict], d08_rows: list[dict]) -> dict:
    f08c = _mod("f08c", "calibrate_expert_check_f08c.py")
    from pianolens.report import calibration as cal

    by_piece: dict[str, list[dict]] = {}
    for r in sorted(asap_rows, key=lambda r: r["midi"]):
        if not r["suspect"]:
            by_piece.setdefault(r["piece_id"], []).append(r)
    maxr, minr = cal.EXPERT_CHECK_MAX_REFS, cal.EXPERT_CHECK_MIN_REFS
    parts = []
    for r in d08_rows:
        if r["suspect"] or r["piece_id"] not in by_piece:
            continue
        ex = [e["table"] for e in by_piece[r["piece_id"]]
              if e["performance_id"] != r["performance_id"]][:maxr]
        if len(ex) < minr:
            continue
        t = f08c.tiers(r["table"], ex, True, cal.EXPERT_CHECK_Q, minr)
        t["rate"], t["injected"] = r["rate"], t["label"].isin(r["injected_bars"])
        parts.append(t)
    df = pd.concat(parts, ignore_index=True)
    cl = df[df["rate"] == 0.0]
    inj = df[(df["rate"] == 0.05) & df["injected"]]
    tiered_g = inj[inj["global"] != "none"]
    return {"n_clean_copies": int(sum(1 for r in d08_rows if r["rate"] == 0.0
                                      and r["piece_id"] in by_piece and not r["suspect"])),
            "expert_bars": int(len(cl)),
            "global": f08c.rates(cl, "global"), "checked": f08c.rates(cl, "checked"),
            "d08_005_kept_tiered": float((tiered_g["checked"] != "none").mean())
            if len(tiered_g) else float("nan")}


def floor_rates(floor_rows: list[dict]) -> dict:
    """A-01 floor, leave-one-out within piece and family, extras not counted: F-08c global /
    checked, rule P and P + BL-25 (fast repeats dropped on both sides where tables have the
    column), family q99 limits, run counts."""
    f08c = _mod("f08c", "calibrate_expert_check_f08c.py")
    b18 = _mod("bl18", "calibrate_strong_tier_bl18.py")
    b18b = _mod("bl18b", "calibrate_strong_tier_bl18b.py")
    from pianolens.report import calibration as cal

    ok = [r for r in floor_rows if not r["suspect"]]
    out: dict = {}
    parts, p_parts, p25_parts, bars, runs = [], [], [], [], []
    for r in ok:
        ex = [e["table"] for e in ok if e["take"] == r["take"]
              and e["transcriber"] == r["transcriber"] and e["ref_id"] != r["ref_id"]]
        t = f08c.tiers(r["table"], ex, False, cal.EXPERT_CHECK_Q, cal.EXPERT_CHECK_MIN_REFS)
        parts.append(t.assign(transcriber=r["transcriber"]))
        p = b18b.rule_tiers(b18, r["table"], ex, "P", r["transcriber"])
        p_parts.append(p[~p["in_run"]].assign(transcriber=r["transcriber"]))
        p2 = b18b.rule_tiers(b18, r["table"], ex, "P+BL25", r["transcriber"])
        p25_parts.append(p2[~p2["in_run"]].assign(transcriber=r["transcriber"]))
        tb = r["table"][r["table"]["n_score_notes"] > 0]
        bars.append(pd.DataFrame({"transcriber": r["transcriber"],
                                  "wrong": tb["n_wrong_pitch"].to_numpy(int),
                                  "mpn": (tb["n_missed"] / tb["n_score_notes"]).to_numpy(float)}))
        _, rr, _ = b18b.run_labels(r["table"])
        runs.append({"transcriber": r["transcriber"], "n_runs": len(rr),
                     "n_run_bars": sum(len(x) for x in rr)})
    df, pdf, p25, bdf, rdf = (pd.concat(parts, ignore_index=True),
                              pd.concat(p_parts, ignore_index=True),
                              pd.concat(p25_parts, ignore_index=True),
                              pd.concat(bars, ignore_index=True), pd.DataFrame(runs))
    for tr in sorted(df["transcriber"].unique()):
        d, p, q, b, ru = (x[x["transcriber"] == tr] for x in (df, pdf, p25, bdf, rdf))
        out[tr] = {"n_refs": int(len(ru)), "n_bars": int(len(d)),
                   "f08c_global": f08c.rates(d, "global"), "f08c_checked": f08c.rates(d, "checked"),
                   "P_strong": float((p["tier"] == "strong").mean()),
                   "P_notable_plus": float((p["tier"] != "none").mean()),
                   "P_BL25_strong": float((q["tier"] == "strong").mean()),
                   "P_BL25_notable_plus": float((q["tier"] != "none").mean()),
                   "family_wrong_q99": float(np.quantile(b["wrong"], 0.99)),
                   "family_missed_per_note_q99": float(np.quantile(b["mpn"], 0.99)),
                   "runs": int(ru["n_runs"].sum()), "run_bars": int(ru["n_run_bars"].sum()),
                   "refs_with_run": int((ru["n_runs"] > 0).sum())}
    out["pooled"] = {"f08c_global": f08c.rates(df, "global"),
                     "f08c_checked": f08c.rates(df, "checked")}
    return out


def evaluate(tabs: dict) -> dict:
    from pianolens.report import calibration as cal

    old_floor = pickle.loads((CAL / "f08c_floor_tables.pkl").read_bytes()) \
        if not (CAL / "f08c_floor_tables_pre_bl28.pkl").exists() \
        else pickle.loads((CAL / "f08c_floor_tables_pre_bl28.pkl").read_bytes())
    old_c = dict(cal.CORRECTNESS_EXPERT_BARS)
    new_c = f08_constants(tabs["keysensor_clean"])
    with _with_limits(new_c):  # tiers below use the new global limits
        ks_new = f08c_keysensor(tabs["asap"], tabs["d08"])
        fl_new = floor_rates(tabs["floor"])
    fl_old = floor_rates(old_floor)  # old tables, current limits (as Henry's reports today)
    fl_new_oldlim = floor_rates(tabs["floor"])  # new tables, current limits (tables effect only)
    rel = {k: (new_c[k] - old_c[k]) / old_c[k] for k in old_c
           if k in new_c and isinstance(old_c[k], float) and old_c[k]}
    fam_old = {k: v["me_q99"] for k, v in cal.TRANSCRIBED_STRONG_LIMITS.items()}
    fam_map = {"Transkun V2": "transkun", "Aria-AMT": "aria_amt"}
    fam_new = {k: fl_new[v]["family_missed_per_note_q99"] for k, v in fam_map.items()}
    rel.update({f"TRANSCRIBED_STRONG_LIMITS[{k}].me_q99": (fam_new[k] - fam_old[k]) / fam_old[k]
                for k in fam_old})
    p_delta = {f"{tr}:{k}": 100 * (fl_new[tr][k] - fl_old[tr][k])
               for tr in ("transkun", "aria_amt")
               for k in ("P_strong", "P_notable_plus", "P_BL25_strong", "P_BL25_notable_plus")}
    stop = {"constants_over_10pct": {k: v for k, v in rel.items() if abs(v) > 0.10},
            "P_rates_over_025pt": {k: v for k, v in p_delta.items()
                                   if k.split(":")[1].startswith("P_")
                                   and "BL25" not in k and abs(v) > 0.25}}
    return {"f08_old": old_c, "f08_new": new_c, "relative_change": rel,
            "family_me_q99_old": fam_old, "family_me_q99_new": fam_new,
            "f08c_keysensor_new": ks_new, "floor_old_tables": fl_old, "floor_new_tables": fl_new,
            "floor_new_tables_old_limits": fl_new_oldlim,
            "P_rate_delta_pt": p_delta, "stop": stop,
            "n": {k: len(v) for k, v in tabs.items() if isinstance(v, list)}}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--from-cache", action="store_true")
    ap.add_argument("--write-floor", action="store_true")
    args = ap.parse_args()
    _quiet()
    OUT.mkdir(parents=True, exist_ok=True)
    cache = OUT / "tables.pkl"
    if args.from_cache:
        tabs = pickle.loads(cache.read_bytes())
    else:
        tabs = build_tables(args.workers)
        cache.write_bytes(pickle.dumps(tabs))
    summ = evaluate(tabs)
    summ["failed"] = tabs.get("failed", [])
    (OUT / "summary.json").write_text(json.dumps(summ, indent=1, default=float))
    print(json.dumps({k: summ[k] for k in ("f08_old", "f08_new", "relative_change",
                                           "P_rate_delta_pt", "stop", "n")},
                     indent=1, default=float))
    if args.write_floor:
        dst = CAL / "f08c_floor_tables.pkl"
        bak = CAL / "f08c_floor_tables_pre_bl28.pkl"
        if not bak.exists():
            shutil.copy2(dst, bak)
        dst.write_bytes(pickle.dumps([{k: r[k] for k in ("take", "transcriber", "ref_id",
                                                         "suspect", "table")}
                                      for r in tabs["floor"]]))
        print("wrote", dst, "(old kept as", bak.name + ")")


if __name__ == "__main__":
    main()
