"""BL-18: the strong correctness tier on transcribed input (pre-registered rules).

Run: ``uv run python scripts/calibrate_strong_tier_bl18.py [--workers 10] [--from-cache]``

Pre-registration: ``docs/specs/report-validation.md``, section 5 (SHA-256 recorded there). The
candidate rules differ only in the per-bar strong limit (``build.expert_bar_limits``,
``strong_margin``) and, for R2, in the global limits of transcribed input:

* R0 (F-08c): per-bar q80 / q99 (linear interpolation), global key-sensor limits.
* R1(k): strong above the finite-sample order statistic of rank ceil(0.99 (n + 1)); with fewer
  than 99 experts, above the per-bar maximum plus k notes.
* R2: per-transcriber-family global q95 / q99 limits from the A-01 floor bars (leave-piece-out
  on the dev set), per-bar q80 / q99 as in R0.
* R1(0) + R2; R3: R0 and R1(0) with 30 experts (held-out T2 only).

Data (extras never counted, as for any transcribed input):

* dev: the 150 A-01 floor transcriptions, leave-one-out within piece and family
  (``f08c_floor_tables.pkl`` from ``scripts/calibrate_expert_check_f08c.py``);
* T1: up to 10 new PianoCoRe transcriptions per Henry piece and family (not in the floor draw),
  against the 15 cached floor experts;
* T2: 6 new pieces (seeded draw), 30 experts + 10 targets per family;
* every held-out target also gets one D-08 copy (rate 0.05, seed 0) for detection.

Outputs (gitignored) in ``data/interim/reports/calibration/``: ``bl18_tables.pkl`` (aligned
per-bar tables) and ``bl18_summary.json``.
"""

from __future__ import annotations

import argparse
import json
import pickle
import warnings
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "data" / "interim" / "reports" / "calibration"
HENRY = REPO / "data" / "interim" / "henry_takes"
FAMILIES = {"Transkun V2": "transkun", "Aria-AMT": "aria_amt"}
SEED = 18
N_T2_PIECES = 6
N_TARGETS = 10
N_EXPERTS_T2 = 30
N_EXPERTS = 15
MIN_PER_FAMILY_T2 = 45
D08_RATE = 0.05
RULES = ("R0", "R1(0)", "R1(1)", "R2", "R1(0)+R2",
         # amendment 1 (docs/specs/report-validation.md, section 5)
         "R2s", "R1(0)+R2s", "R1(1)+R2s", "R1(2)+R2s", "R1(1)+R2", "R1(2)+R2")
SELECTION_ORDER = ("R1(0)", "R2", "R1(0)+R2", "R1(1)",
                   "R2s", "R1(0)+R2s", "R1(1)+R2s", "R1(2)+R2s", "R1(1)+R2", "R1(2)+R2")


def _quiet() -> None:
    import logging

    warnings.filterwarnings("ignore")
    logging.disable(logging.WARNING)


# ----------------------------------------------------------------------------- draws


def draw_jobs() -> list[dict]:
    """All alignment jobs (pre-registered draws, seed 18)."""
    import zipfile

    from pianolens.data.pianocore import DEFAULT_ROOT, RAW_PREFIX, RAW_ZIP, PianoCoRe

    idx = PianoCoRe().index
    tr = idx[idx["is_transcription"].astype(bool) & idx["capture_model"].isin(FAMILIES)]
    meta = json.loads((HENRY / "scores" / "scores.json").read_text())
    floor = pickle.loads((OUT / "f08c_floor_tables.pkl").read_bytes())
    floor_ids = {r["ref_id"] for r in floor}
    rng = np.random.default_rng(SEED)
    jobs = []
    # T1: Henry's pieces, new targets only
    for k in sorted(meta):
        pid = meta[k]["piece_id"]
        for cm, fam in FAMILIES.items():
            r = tr[(tr["piece_id"] == pid) & (tr["capture_model"] == cm)
                   & ~tr["id"].isin(floor_ids)].sort_values("id")
            pick = np.sort(rng.choice(len(r), size=min(N_TARGETS, len(r)), replace=False))
            for i in pick:
                jobs.append({"set": "T1", "piece": k, "piece_id": pid, "family": fam,
                             "role": "target", "id": str(r.iloc[i]["id"]),
                             "midi": str(r.iloc[i]["performance_midi_path"]),
                             "score": str(HENRY / "scores" / f"{k}_score.mxl"),
                             "score_in_zip": False})  # fmt: skip
    # T2: new pieces
    with zipfile.ZipFile(DEFAULT_ROOT / RAW_ZIP) as z:
        names = set(z.namelist())
    cnt = tr.groupby(["piece_id", "capture_model"]).size().unstack(fill_value=0)
    henry_pids = {m["piece_id"] for m in meta.values()}
    elig = []
    for pid, row in cnt.iterrows():
        if pid in henry_pids or min(row.get(cm, 0) for cm in FAMILIES) < MIN_PER_FAMILY_T2:
            continue
        sx = tr.loc[tr["piece_id"] == pid, "score_xml_path"].dropna().astype(str)
        sx = [s for s in sorted(set(sx)) if RAW_PREFIX + s in names]
        if len(sx) == 1:
            elig.append((pid, sx[0]))
    elig.sort()
    chosen = [elig[i] for i in sorted(rng.choice(len(elig), size=N_T2_PIECES, replace=False))]
    for pid, sx in chosen:
        for cm, fam in FAMILIES.items():
            r = tr[(tr["piece_id"] == pid) & (tr["capture_model"] == cm)].sort_values("id")
            perm = rng.permutation(len(r))
            for j, i in enumerate(perm[:N_EXPERTS_T2 + N_TARGETS]):
                role = "expert" if j < N_EXPERTS_T2 else "target"
                jobs.append({"set": "T2", "piece": pid, "piece_id": pid, "family": fam,
                             "role": role, "order": j, "id": str(r.iloc[i]["id"]),
                             "midi": str(r.iloc[i]["performance_midi_path"]), "score": sx,
                             "score_in_zip": True})  # fmt: skip
    return jobs


# ----------------------------------------------------------------------------- worker


def align_job(job: dict) -> dict:
    """Align one transcription; for a target also a D-08 copy and its injected bar labels."""
    _quiet()
    import tempfile
    import zipfile

    from pianolens.align import align_performance
    from pianolens.data.perturb import MistakeSpec, perturb
    from pianolens.data.pianocore import DEFAULT_ROOT, RAW_PREFIX, RAW_ZIP
    from pianolens.features.correctness import correctness
    from pianolens.report.build import bar_error_table, bar_labels
    from pianolens.report.io import load_performance, load_score

    with zipfile.ZipFile(DEFAULT_ROOT / RAW_ZIP) as z, tempfile.TemporaryDirectory() as td:
        if job["score_in_zip"]:
            sp = Path(td) / Path(job["score"]).name
            sp.write_bytes(z.read(RAW_PREFIX + job["score"]))
        else:
            sp = Path(job["score"])
        sc = load_score(sp, job["piece_id"])
        f = Path(td) / "perf.mid"
        f.write_bytes(z.read(RAW_PREFIX + job["midi"]))
        perf = load_performance(f, "transcribed", job["piece_id"], performance_id=job["id"])
    ap = align_performance(sc, perf)
    cr = correctness(ap)
    labels = bar_labels(ap.score)
    out = {**job, "suspect": bool(cr.summary["alignment_suspect"]),
           "table": bar_error_table(cr, labels)}
    if job["role"] != "target" or out["suspect"]:
        return out
    pp, lab = perturb(ap.performance, ap.alignment, MistakeSpec(rate=D08_RATE), seed=0,
                      require_exact_timing=False)
    sn = cr.score_notes
    bar_of = dict(zip(sn["score_id"].astype(str), sn["measure_index"].astype(int), strict=True))
    ids = set(lab.notes.loc[lab.notes["injected"] & (lab.notes["label"] == "wrong_pitch"),
                            "score_id"].astype(str))
    ids |= set(lab.missed.loc[lab.missed["injected"], "score_id"].astype(str))
    inj = sorted({labels[bar_of[s]] for s in ids if bar_of.get(s, -1) >= 0})
    ap2 = align_performance(ap.score, pp)
    cr2 = correctness(ap2)
    out["injected_table"] = bar_error_table(cr2, bar_labels(ap2.score))
    out["injected_suspect"] = bool(cr2.summary["alignment_suspect"])
    out["injected_bars"] = inj
    out["n_injected"] = lab.counts()
    return out


# ----------------------------------------------------------------------------- rules


def family_limits(tables: list[pd.DataFrame]) -> dict[str, float]:
    """R2: q95 / q99 of wrong-pitch count and missed notes per note over graded expert bars."""
    t = pd.concat(tables, ignore_index=True)
    t = t[t["n_score_notes"] > 0]
    w = t["n_wrong_pitch"].to_numpy(float)
    m = (t["n_missed"] / t["n_score_notes"]).to_numpy(float)
    return {"wrong_q95": float(np.quantile(w, 0.95)), "wrong_q99": float(np.quantile(w, 0.99)),
            "me_q95": float(np.quantile(m, 0.95)), "me_q99": float(np.quantile(m, 0.99))}


def tiers(table: pd.DataFrame, experts: list[pd.DataFrame], rule: str,
          fam_lim: dict[str, float] | None) -> pd.DataFrame:
    """Checked tier per graded bar of ``table`` under ``rule`` (extras not counted)."""
    from pianolens.report import calibration as cal
    from pianolens.report.build import (
        _checked_correctness_tier,
        _correctness_tier,
        expert_bar_limits,
        global_correctness_limits,
    )

    t = table[table["n_score_notes"] > 0].reset_index(drop=True)
    glim = global_correctness_limits(False)
    if "R2s" in rule:  # family limits for strong only (amendment 1)
        glim.update({k: fam_lim[k] for k in ("wrong_q99", "me_q99")})
    elif "R2" in rule:
        glim = dict(fam_lim)
    margin = int(rule[3]) if rule.startswith("R1(") else None
    lim = expert_bar_limits(experts, list(t["label"]), False, cal.EXPERT_CHECK_Q,
                            cal.EXPERT_CHECK_MIN_REFS, strong_margin=margin)
    out = []
    for i in range(len(t)):
        w, me, n = int(t["n_wrong_pitch"].iat[i]), int(t["n_missed"].iat[i]), \
            int(t["n_score_notes"].iat[i])
        e = lim.iloc[i]
        if np.isfinite(e["wrong_q95"]):
            out.append(_checked_correctness_tier(w, me, n, glim, e)[0])
        else:
            out.append(_correctness_tier(w, me, n, glim)[0])
    return pd.DataFrame({"label": t["label"], "tier": out,
                         "n_experts": lim["n_experts"].to_numpy(int)})


def _interval(df: pd.DataFrame, col: str, rng: np.random.Generator) -> dict:
    """Pooled rate, piece-cluster bootstrap 95% CI and t-interval over per-piece rates."""
    from scipy import stats

    g = df.groupby("piece")[col].agg(["sum", "count"])
    pooled = float(g["sum"].sum() / g["count"].sum()) if g["count"].sum() else np.nan
    boot = []
    for _ in range(2000):
        s = g.iloc[rng.integers(0, len(g), len(g))]
        boot.append(s["sum"].sum() / s["count"].sum())
    per = (g["sum"] / g["count"]).to_numpy(float)
    m, se = float(per.mean()), float(per.std(ddof=1) / np.sqrt(len(per))) if len(per) > 1 else 0
    tq = float(stats.t.ppf(0.975, max(1, len(per) - 1)))
    return {"rate": pooled, "n_bars": int(g["count"].sum()), "n_pieces": len(g),
            "boot95": [float(np.quantile(boot, 0.025)), float(np.quantile(boot, 0.975))],
            "piece_mean": m, "t95": [m - tq * se, m + tq * se]}  # fmt: skip


def summarise(df: pd.DataFrame, seed: int = 0) -> dict:
    """Rates per family and pooled for one rule's tier frame (columns piece, family, tier)."""
    df = df.assign(notable_plus=(df["tier"] != "none").astype(int),
                   strong=(df["tier"] == "strong").astype(int))
    out = {}
    for fam, g in [("pooled", df), *df.groupby("family")]:
        rng = np.random.default_rng(seed)
        out[fam] = {"notable_plus": _interval(g, "notable_plus", rng),
                    "strong": _interval(g, "strong", rng)}
    return out


# ----------------------------------------------------------------------------- main


def dev_eval(floor: list[dict]) -> dict:
    """Dev: floor LOO within piece and family (R2 limits leave the piece out)."""
    ok = [r for r in floor if not r["suspect"]]
    res: dict = {}
    for rule in RULES:
        parts = []
        for r in ok:
            ex = [e["table"] for e in ok if e["take"] == r["take"]
                  and e["transcriber"] == r["transcriber"] and e["ref_id"] != r["ref_id"]]
            fl = family_limits([e["table"] for e in ok if e["take"] != r["take"]
                                and e["transcriber"] == r["transcriber"]]) \
                if "R2" in rule else None
            t = tiers(r["table"], ex, rule, fl)
            t["piece"], t["family"] = r["take"], r["transcriber"]
            parts.append(t)
        res[rule] = summarise(pd.concat(parts, ignore_index=True))
    fam_lims = {f: family_limits([r["table"] for r in ok if r["transcriber"] == f])
                for f in FAMILIES.values()}
    return {"rates": res, "family_limits_all_floor": fam_lims}


def select(dev: dict) -> str:
    for rule in SELECTION_ORDER:
        r = dev["rates"][rule]
        if all(r[f]["strong"]["rate"] <= 0.01 for f in FAMILIES.values()):
            return rule
    return "none"


def heldout_eval(rows: list[dict], floor: list[dict], fam_lims: dict, chosen: str) -> dict:
    ok_floor = [r for r in floor if not r["suspect"]]
    experts: dict[tuple, list] = {}
    for r in ok_floor:
        experts.setdefault((r["take"], r["transcriber"]), []).append(r["table"])
    ex30: dict[tuple, list] = {}
    for r in sorted((r for r in rows if r["role"] == "expert" and not r["suspect"]),
                    key=lambda r: r["order"]):
        ex30.setdefault((r["piece"], r["family"]), []).append(r["table"])
    for k, v in ex30.items():
        experts[k] = v[:N_EXPERTS]
    targets = [r for r in rows if r["role"] == "target" and not r["suspect"]]
    variants = {rule: (rule, experts, None) for rule in RULES}
    t2_15 = {k: experts[k] for k in ex30}
    for rule in ("R0", "R1(0)", chosen):
        variants[f"R3:{rule} (30 experts, T2)"] = (rule, ex30, None)
        variants[f"R3 ref:{rule} (15 experts, T2)"] = (rule, t2_15, None)
    mx = {k: max(v[k] for v in fam_lims.values()) for k in next(iter(fam_lims.values()))}
    variants[f"{chosen} [family unknown: max limits]"] = (chosen, experts, mx)
    out: dict = {"n_targets": {f: sum(1 for r in targets if r["family"] == f)
                               for f in FAMILIES.values()},
                 "n_targets_suspect": sum(1 for r in rows if r["role"] == "target"
                                          and r["suspect"]),
                 "n_experts_t2": {f"{k[0]}|{k[1]}": len(v) for k, v in ex30.items()},
                 "n_injected_suspect": sum(1 for r in targets if r.get("injected_suspect"))}
    for name, (rule, ex, fixed_lim) in variants.items():
        clean, inj = [], []
        for r in targets:
            key = (r["piece"], r["family"])
            if key not in ex:
                continue
            fl = fixed_lim or (fam_lims[r["family"]] if "R2" in rule else None)
            t = tiers(r["table"], ex[key], rule, fl)
            t["piece"], t["family"] = r["piece"], r["family"]
            clean.append(t)
            if not r["injected_suspect"]:
                ti = tiers(r["injected_table"], ex[key], rule, fl)
                ti = ti[ti["label"].isin(r["injected_bars"])]
                ti["piece"], ti["family"] = r["piece"], r["family"]
                inj.append(ti)
        out[name] = {"clean": summarise(pd.concat(clean, ignore_index=True)),
                     "injected": summarise(pd.concat(inj, ignore_index=True))}
    return out


def keysensor_info() -> dict:
    """R0 vs R1(0) on the F-08c key-sensor cache (information only; key-sensor keeps R0)."""
    from pianolens.report import calibration as cal
    from pianolens.report.build import (
        _checked_correctness_tier,
        _correctness_tier,
        expert_bar_limits,
        global_correctness_limits,
    )

    asap_rows = pickle.loads((OUT / "f08c_asap_tables.pkl").read_bytes())
    d08 = pickle.loads((OUT / "f08c_d08_tables.pkl").read_bytes())
    by_piece: dict[str, list] = {}
    for r in sorted(asap_rows, key=lambda r: r["midi"]):
        if not r["suspect"]:
            by_piece.setdefault(r["piece_id"], []).append(r)
    glim = global_correctness_limits(True)
    res = {}
    for name, margin in (("R0", None), ("R1(0)", 0)):
        acc = {"expert": [0, 0, 0], **{f"inj_{rt}": [0, 0, 0] for rt in (0.02, 0.05, 0.1)}}
        for r in d08:
            if r["suspect"]:
                continue
            ex = [e["table"] for e in by_piece.get(r["piece_id"], [])
                  if e["performance_id"] != r["performance_id"]][:cal.EXPERT_CHECK_MAX_REFS]
            t = r["table"][r["table"]["n_score_notes"] > 0].reset_index(drop=True)
            lim = expert_bar_limits(ex, list(t["label"]), True, cal.EXPERT_CHECK_Q,
                                    cal.EXPERT_CHECK_MIN_REFS, strong_margin=margin)
            key = "expert" if r["rate"] == 0 else f"inj_{r['rate']}"
            for i in range(len(t)):
                if key != "expert" and t["label"].iat[i] not in r["injected_bars"]:
                    continue
                w, n = int(t["n_wrong_pitch"].iat[i]), int(t["n_score_notes"].iat[i])
                me = int(t["n_missed"].iat[i] + t["n_extra"].iat[i])
                e = lim.iloc[i]
                tr = (_checked_correctness_tier(w, me, n, glim, e)[0]
                      if np.isfinite(e["wrong_q95"]) else _correctness_tier(w, me, n, glim)[0])
                acc[key][0] += 1
                acc[key][1] += tr != "none"
                acc[key][2] += tr == "strong"
        res[name] = {k: {"bars": v[0], "notable_plus": v[1] / v[0], "strong": v[2] / v[0]}
                     for k, v in acc.items()}
    return res


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--from-cache", action="store_true")
    ap.add_argument("--dev-only", action="store_true")
    args = ap.parse_args()
    _quiet()
    floor = pickle.loads((OUT / "f08c_floor_tables.pkl").read_bytes())
    summ: dict = {"prereg": "docs/specs/report-validation.md section 5"}
    dev = dev_eval(floor)
    summ["dev"] = dev
    summ["chosen"] = select(dev)
    print("dev strong:", {r: {f: round(100 * v[f]["strong"]["rate"], 2) for f in v}
                          for r, v in dev["rates"].items()}, "chosen:", summ["chosen"])
    if args.dev_only:
        print(json.dumps(summ, indent=1, default=float))
        return
    cache = OUT / "bl18_tables.pkl"
    if args.from_cache:
        rows = pickle.loads(cache.read_bytes())
    else:
        jobs = draw_jobs()
        print(len(jobs), "alignment jobs")
        rows = []
        with ProcessPoolExecutor(args.workers) as ex:
            futs = {ex.submit(align_job, j): j for j in jobs}
            for k, fu in enumerate(as_completed(futs)):
                try:
                    rows.append(fu.result())
                except Exception as e:  # noqa: BLE001 - count failures
                    j = futs[fu]
                    print("failed:", j["set"], j["piece"], j["id"], repr(e)[:200])
                if k % 50 == 0:
                    print(k, "done", flush=True)
        cache.write_bytes(pickle.dumps(rows))
    summ["n_jobs_ok"] = len(rows)
    summ["t2_pieces"] = sorted({r["piece"] for r in rows if r["set"] == "T2"})
    summ["heldout"] = heldout_eval(rows, floor, dev["family_limits_all_floor"], summ["chosen"])
    summ["keysensor_info"] = keysensor_info()
    (OUT / "bl18_summary.json").write_text(json.dumps(summ, indent=1, default=float))
    print(json.dumps(summ, indent=1, default=float))


if __name__ == "__main__":
    main()
