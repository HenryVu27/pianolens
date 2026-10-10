"""DF-13: rebuild the A-01 floor expert tables with a wrong-pitch window rule, and report what
moves in the transcribed calibration.

Run: ``OMP_NUM_THREADS=1 uv run python scripts/rebuild_floor_tables_df13.py --rule tempo
[--workers 10]``

The 150 A-01 floor transcriptions (``calibrate_expert_check_f08c.floor_jobs``: Henry's 5 Chopin
pieces x 2 transcriber families x 15) are aligned once and labelled with ``fixed`` and with
``--rule``. Outputs (gitignored) in ``data/interim/df13/``:

* ``floor_tables_<rule>.pkl`` and ``floor_tables_fixed.pkl``: same row schema as
  ``f08c_floor_tables.pkl`` (``take``, ``transcriber``, ``ref_id``, ``suspect``, ``table``), for
  ``a01_henry_reports.py --floor-tables``;
* ``floor_calibration_<rule>.json``: per family, leave-one-out within piece and family, extras
  not counted: F-08c checked notable+ / strong (q80 / q99, the values quoted in
  ``calibration.py``), rule P (R1(0) + run rule) strong, the family q99 limits behind
  ``TRANSCRIBED_STRONG_LIMITS`` (wrong-pitch count, missed per note), wrong-pitch labels per
  1,000 graded notes, and whether the ``fixed`` tables reproduce the cached F-08c tables.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import pickle
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "data" / "interim" / "df13"
CAL = REPO / "data" / "interim" / "reports" / "calibration"


def _mod(name: str, file: str):
    spec = importlib.util.spec_from_file_location(name, REPO / "scripts" / file)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def floor_one(k: str, ref_id: str, rel: str, t: str, rule: str) -> dict:
    f08c = _mod("f08c", "calibrate_expert_check_f08c.py")
    f08c._quiet()
    import tempfile
    import zipfile

    from pianolens.align import align_performance
    from pianolens.data.pianocore import DEFAULT_ROOT, RAW_PREFIX, RAW_ZIP
    from pianolens.features.correctness import correctness
    from pianolens.report.io import load_performance, load_score

    meta = json.loads((f08c.HENRY / "scores" / "scores.json").read_text())[k]
    sc = load_score(f08c.HENRY / "scores" / f"{k}_score.mxl", meta["piece_id"])
    with zipfile.ZipFile(DEFAULT_ROOT / RAW_ZIP) as z, tempfile.TemporaryDirectory() as td:
        f = Path(td) / "ref.mid"
        f.write_bytes(z.read(RAW_PREFIX + rel))
        ap = align_performance(sc, load_performance(f, "transcribed", meta["piece_id"],
                                                    performance_id=ref_id))
    out = {}
    for r in ("fixed", rule):
        cr = correctness(ap, wrong_pitch_window=r)
        out[r] = {"take": k, "transcriber": t, "ref_id": ref_id,
                  "suspect": bool(cr.summary["alignment_suspect"]),
                  "table": f08c._table(ap, cr),
                  "n_wrong": int(cr.summary["n_wrong_pitch"]),
                  "n_graded": int(cr.summary["n_score_notes"])}
    return out


def calibration(rows: list[dict]) -> dict:
    """Leave-one-out floor rates per family (extras not counted)."""
    f08c = _mod("f08c", "calibrate_expert_check_f08c.py")
    b18 = _mod("bl18", "calibrate_strong_tier_bl18.py")
    b18b = _mod("bl18b", "calibrate_strong_tier_bl18b.py")
    from pianolens.report import calibration as cal

    ok = [r for r in rows if not r["suspect"]]
    parts, p_parts, bars = [], [], []
    for r in ok:
        ex = [e["table"] for e in ok if e["take"] == r["take"]
              and e["transcriber"] == r["transcriber"] and e["ref_id"] != r["ref_id"]]
        t = f08c.tiers(r["table"], ex, False, cal.EXPERT_CHECK_Q, cal.EXPERT_CHECK_MIN_REFS)
        parts.append(t.assign(transcriber=r["transcriber"]))
        p = b18b.rule_tiers(b18, r["table"], ex, "P", r["transcriber"])
        p_parts.append(p[~p["in_run"]].assign(transcriber=r["transcriber"]))
        tb = r["table"][r["table"]["n_score_notes"] > 0]
        bars.append(pd.DataFrame({"transcriber": r["transcriber"],
                                  "wrong": tb["n_wrong_pitch"].to_numpy(int),
                                  "mpn": (tb["n_missed"] / tb["n_score_notes"]).to_numpy(float)}))
    df, pdf, bdf = (pd.concat(x, ignore_index=True) for x in (parts, p_parts, bars))
    out = {}
    for tr in sorted(df["transcriber"].unique()):
        d, p, b = (x[x["transcriber"] == tr] for x in (df, pdf, bdf))
        rr = [r for r in ok if r["transcriber"] == tr]
        out[tr] = {"n_refs": len(rr), "n_bars": len(d),
                   "f08c_checked_notable_plus": float((d["checked"] != "none").mean()),
                   "f08c_checked_strong": float((d["checked"] == "strong").mean()),
                   "P_strong": float((p["tier"] == "strong").mean()),
                   "P_notable_plus": float((p["tier"] != "none").mean()),
                   "family_wrong_q99": float(np.quantile(b["wrong"], 0.99)),
                   "family_missed_per_note_q99": float(np.quantile(b["mpn"], 0.99)),
                   "wrong_per_1k": 1000 * sum(r["n_wrong"] for r in rr)
                   / max(1, sum(r["n_graded"] for r in rr))}
    d = df
    out["pooled"] = {"f08c_checked_notable_plus": float((d["checked"] != "none").mean()),
                     "f08c_checked_strong": float((d["checked"] == "strong").mean())}
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rule", required=True)
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--from-cache", action="store_true")
    args = ap.parse_args()
    f08c = _mod("f08c", "calibrate_expert_check_f08c.py")
    f08c._quiet()
    OUT.mkdir(parents=True, exist_ok=True)
    paths = {r: OUT / f"floor_tables_{r}.pkl" for r in ("fixed", args.rule)}
    if args.from_cache:
        rows = {r: pickle.loads(p.read_bytes()) for r, p in paths.items()}
    else:
        rows = {r: [] for r in paths}
        with ProcessPoolExecutor(args.workers) as ex:
            futs = [ex.submit(floor_one, *j, args.rule) for j in f08c.floor_jobs()]
            for fu in as_completed(futs):
                res = fu.result()
                for r in rows:
                    rows[r].append(res[r])
        for r, p in paths.items():
            p.write_bytes(pickle.dumps(rows[r]))
    cached = {(r["take"], r["transcriber"], r["ref_id"]): r["table"]
              for r in pickle.loads((CAL / "f08c_floor_tables.pkl").read_bytes())}
    same = sum(1 for r in rows["fixed"]
               if (k := (r["take"], r["transcriber"], r["ref_id"])) in cached
               and cached[k].drop(columns=["n_missed_fast_repeat"], errors="ignore")
               .equals(r["table"].drop(columns=["n_missed_fast_repeat"], errors="ignore")))
    summ = {"rule": args.rule, "n_tables": len(rows["fixed"]),
            "fixed_equals_cached_f08c": same,
            "calibration": {r: calibration(rows[r]) for r in rows}}
    (OUT / f"floor_calibration_{args.rule}.json").write_text(
        json.dumps(summ, indent=1, default=float))
    print(json.dumps(summ, indent=1, default=float))


if __name__ == "__main__":
    main()
