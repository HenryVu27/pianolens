"""BL-18b: confirmation of the interim strong rule R1(0) + run rule on transcribed input.

Run: ``OMP_NUM_THREADS=1 uv run python scripts/calibrate_strong_tier_bl18b.py [--workers 10]
[--from-cache]``

Pre-registration: ``docs/specs/report-validation.md``, section 6 (SHA-256 recorded there),
following the BL-18 audit's specification. Rules:

* P (primary): R1(0) (strong above every expert at the bar, margin 0) + run rule (runs of >= 3
  consecutive graded bars with >= 80% missed are "passage not heard": no tier, and out of the
  clean denominator; ``build.not_heard_runs``);
* information: R0, R1(0) without the run rule, R1(2) + R2s (returned rule), R1(0) + R2s with the
  run-free Aria-AMT missed limit 0.422, and P + BL-25 (fast same-pitch repeats not counted).

Data: 12 new PianoCoRe pieces (seed 1802; >= 25 transcriptions per family and one score; not
Henry's 5 or the BL-18 T2 pieces), 15 experts and 10 targets per piece and family, never used
before. Per target: the clean transcription, one D-08 copy (rate 0.05, seed 1) and one targeted
copy (up to 10 spaced bars, each with exactly 3 wrong pitches, seed 2).

Phase 1 aligns the experts; phase 2 aligns each target with its experts' tables (needed to pick
the targeted bars). Outputs (gitignored) in ``data/interim/reports/calibration/``:
``bl18b_tables.pkl`` and ``bl18b_summary.json``.
"""

from __future__ import annotations

import argparse
import importlib.util
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
SEED = 1802
D08_SEED = 1
TARGETED_SEED = 2
N_PIECES = 12
N_EXPERTS = 15
N_TARGETS = 10
MIN_PER_FAMILY = 25
D08_RATE = 0.05
N_TARGETED_BARS = 10
TARGETED_WRONG = 3
TARGETED_GAP = 3  # chosen bar indices differ by at least 3 (2 untouched bars between)
TARGETED_DELTAS = ((-1, 0.3), (1, 0.3), (-2, 0.15), (2, 0.15))
ARIA_LIMIT_NO_RUNS = 0.422  # BL-18 audit: dev floor Aria-AMT missed/note q99 without run bars
C1 = (0.003, 0.0125)
C3_MIN = 0.75
C4_MIN = 0.95


def _bl18():
    spec = importlib.util.spec_from_file_location(
        "bl18", REPO / "scripts" / "calibrate_strong_tier_bl18.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _quiet() -> None:
    import logging

    warnings.filterwarnings("ignore")
    logging.disable(logging.WARNING)


# ----------------------------------------------------------------------------- draw


def used_ids() -> set[str]:
    """Every transcription id of the A-01 floor, BL-18 T1 and T2."""
    floor = pickle.loads((OUT / "f08c_floor_tables.pkl").read_bytes())
    b18 = pickle.loads((OUT / "bl18_tables.pkl").read_bytes())
    return {str(r["ref_id"]) for r in floor} | {str(r["id"]) for r in b18}


def draw_jobs() -> list[dict]:
    import zipfile

    from pianolens.data.pianocore import DEFAULT_ROOT, RAW_PREFIX, RAW_ZIP, PianoCoRe

    idx = PianoCoRe().index
    tr = idx[idx["is_transcription"].astype(bool) & idx["capture_model"].isin(FAMILIES)]
    meta = json.loads((HENRY / "scores" / "scores.json").read_text())
    henry = {m["piece_id"] for m in meta.values()}
    t2 = set(json.loads((OUT / "bl18_summary.json").read_text())["t2_pieces"])
    used = used_ids()
    with zipfile.ZipFile(DEFAULT_ROOT / RAW_ZIP) as z:
        names = set(z.namelist())
    cnt = tr.groupby(["piece_id", "capture_model"]).size().unstack(fill_value=0)
    elig = []
    for pid, row in cnt.iterrows():
        if pid in henry or pid in t2 or min(row.get(cm, 0) for cm in FAMILIES) < MIN_PER_FAMILY:
            continue
        sx = tr.loc[tr["piece_id"] == pid, "score_xml_path"].dropna().astype(str)
        sx = [s for s in sorted(set(sx)) if RAW_PREFIX + s in names]
        if len(sx) == 1:
            elig.append((pid, sx[0]))
    elig.sort()
    rng = np.random.default_rng(SEED)
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
    return jobs, len(elig)


# ----------------------------------------------------------------------------- workers


def _load(job: dict):
    import tempfile
    import zipfile

    from pianolens.data.pianocore import DEFAULT_ROOT, RAW_PREFIX, RAW_ZIP
    from pianolens.report.io import load_performance, load_score

    with zipfile.ZipFile(DEFAULT_ROOT / RAW_ZIP) as z, tempfile.TemporaryDirectory() as td:
        sp = Path(td) / Path(job["score"]).name
        sp.write_bytes(z.read(RAW_PREFIX + job["score"]))
        sc = load_score(sp, job["piece_id"])
        f = Path(td) / "perf.mid"
        f.write_bytes(z.read(RAW_PREFIX + job["midi"]))
        perf = load_performance(f, "transcribed", job["piece_id"], performance_id=job["id"])
    return sc, perf


def align_expert(job: dict) -> dict:
    _quiet()
    from pianolens.align import align_performance
    from pianolens.features.correctness import correctness
    from pianolens.report.build import bar_error_table, bar_labels

    sc, perf = _load(job)
    ap = align_performance(sc, perf)
    cr = correctness(ap)
    return {**job, "suspect": bool(cr.summary["alignment_suspect"]),
            "table": bar_error_table(cr, bar_labels(ap.score))}


def targeted_copy(ap, cr, labels: list[str], table: pd.DataFrame, experts: list[pd.DataFrame],
                  seed: int):
    """Up to N_TARGETED_BARS spaced eligible bars, each with exactly 3 wrong pitches (section 6).
    Returns (performance copy, chosen bar labels)."""
    import dataclasses

    from pianolens.data.perturb import _PIANO_HI, _PIANO_LO, _same_pitch_busy, chord_clusters
    from pianolens.report import calibration as cal
    from pianolens.report.build import not_heard_runs

    rng = np.random.default_rng(seed)
    notes = ap.performance.notes.copy()
    pos = {str(p): i for i, p in enumerate(notes["id"].astype(str))}
    chord = chord_clusters(notes["onset_sec"].astype(float), 0.05)
    lab_count = pd.Series(labels).value_counts()
    runs = not_heard_runs(table["n_missed"].to_numpy(int), table["n_score_notes"].to_numpy(int))
    in_run = {i for r in runs for i in r}
    ex_wrong: dict[str, list[int]] = {}
    for t in experts:
        for r in t.itertuples(index=False):
            if r.n_score_notes > 0:
                ex_wrong.setdefault(r.label, []).append(int(r.n_wrong_pitch))
    n = cr.notes
    corr = n[(n["label"] == "correct") & (n["measure_index"] >= 0)]
    by_bar = {int(b): [pos[str(p)] for p in g["performance_id"] if str(p) in pos]
              for b, g in corr.groupby("measure_index")}
    elig = []
    for i, lab in enumerate(labels):
        w = ex_wrong.get(lab, [])
        if (lab_count[lab] == 1 and len(w) >= cal.EXPERT_CHECK_MIN_REFS and max(w) <= 1
                and table["n_score_notes"].iat[i] > 0 and table["n_wrong_pitch"].iat[i] == 0
                and i not in in_run and len(by_bar.get(i, [])) >= TARGETED_WRONG):
            elig.append(i)
    deltas = np.array([d for d, _ in TARGETED_DELTAS])
    pw = np.array([w for _, w in TARGETED_DELTAS])
    pw = pw / pw.sum()
    chosen = []
    for i in rng.permutation(elig):
        if len(chosen) >= N_TARGETED_BARS:
            break
        if any(abs(int(i) - c) < TARGETED_GAP for c in chosen):
            continue
        done = {}
        for k in rng.permutation(by_bar[int(i)]):
            if len(done) >= TARGETED_WRONG:
                break
            cp = set(notes["pitch"][chord == chord[k]].tolist())
            t0 = float(notes["onset_sec"][k])
            t1 = t0 + float(notes["duration_sec"][k])
            for _ in range(20):
                new = int(notes["pitch"][k]) + int(rng.choice(deltas, p=pw))
                if (_PIANO_LO <= new <= _PIANO_HI and new not in cp
                        and not _same_pitch_busy(notes, new, t0, t1)):
                    done[int(k)] = (int(notes["pitch"][k]), new)
                    notes["pitch"][k] = new
                    break
        if len(done) == TARGETED_WRONG:
            chosen.append(int(i))
        else:  # revert a bar that cannot take exactly 3 wrong pitches
            for k, (old, _) in done.items():
                notes["pitch"][k] = old
    perf = dataclasses.replace(ap.performance, notes=notes,
                               performance_id=f"{ap.performance.performance_id}#targeted")
    return perf, [labels[i] for i in sorted(chosen)]


def align_target(job: dict, experts: list[pd.DataFrame]) -> dict:
    _quiet()
    from pianolens.align import align_performance
    from pianolens.data.perturb import MistakeSpec, perturb
    from pianolens.features.correctness import correctness
    from pianolens.report.build import bar_error_table, bar_labels

    sc, perf = _load(job)
    ap = align_performance(sc, perf)
    cr = correctness(ap)
    labels = bar_labels(ap.score)
    table = bar_error_table(cr, labels)
    out = {**job, "suspect": bool(cr.summary["alignment_suspect"]), "table": table}
    if out["suspect"]:
        return out
    # D-08 copy
    pp, lab = perturb(ap.performance, ap.alignment, MistakeSpec(rate=D08_RATE), seed=D08_SEED,
                      require_exact_timing=False)
    sn = cr.score_notes
    bar_of = dict(zip(sn["score_id"].astype(str), sn["measure_index"].astype(int), strict=True))
    ids = set(lab.notes.loc[lab.notes["injected"] & (lab.notes["label"] == "wrong_pitch"),
                            "score_id"].astype(str))
    ids |= set(lab.missed.loc[lab.missed["injected"], "score_id"].astype(str))
    out["injected_bars"] = sorted({labels[bar_of[s]] for s in ids if bar_of.get(s, -1) >= 0})
    ap2 = align_performance(ap.score, pp)
    cr2 = correctness(ap2)
    out["injected_table"] = bar_error_table(cr2, bar_labels(ap2.score))
    out["injected_suspect"] = bool(cr2.summary["alignment_suspect"])
    out["n_injected"] = lab.counts()
    # targeted copy
    tp, tbars = targeted_copy(ap, cr, labels, table, experts, TARGETED_SEED)
    out["targeted_bars"] = tbars
    if tbars:
        ap3 = align_performance(ap.score, tp)
        cr3 = correctness(ap3)
        out["targeted_table"] = bar_error_table(cr3, bar_labels(ap3.score))
        out["targeted_suspect"] = bool(cr3.summary["alignment_suspect"])
    return out


# ----------------------------------------------------------------------------- rules


def run_labels(table: pd.DataFrame) -> tuple[set[int], list[list[int]], pd.DataFrame]:
    """Run rule on a table's graded bars (graded-row indices of each run)."""
    from pianolens.report.build import not_heard_runs

    t = table[table["n_score_notes"] > 0].reset_index(drop=True)
    runs = not_heard_runs(t["n_missed"].to_numpy(int), t["n_score_notes"].to_numpy(int))
    return {i for r in runs for i in r}, runs, t


def _drop_fast(t: pd.DataFrame) -> pd.DataFrame:
    t = t.copy()
    if "n_missed_fast_repeat" in t.columns:
        t["n_missed"] = t["n_missed"] - t["n_missed_fast_repeat"]
    return t


RULES = ("P", "R0", "R1(0)", "R1(2)+R2s", "R1(0)+R2s[0.422]", "P+BL25")


def rule_tiers(b18, table: pd.DataFrame, experts: list[pd.DataFrame], rule: str,
               family: str) -> pd.DataFrame:
    """Tier per graded bar under ``rule``; ``in_run`` marks run bars (target's own table)."""
    from pianolens.report import calibration as cal

    runs, _, _ = run_labels(table)
    if rule == "R1(2)+R2s":
        fam = {v: k for k, v in FAMILIES.items()}[family]
        t = b18.tiers(table, experts, rule, dict(cal.TRANSCRIBED_STRONG_LIMITS[fam]))
    elif rule == "R1(0)+R2s[0.422]":
        lim = {"wrong_q99": 2.0, "me_q99": ARIA_LIMIT_NO_RUNS if family == "aria_amt"
               else cal.TRANSCRIBED_STRONG_LIMITS["Transkun V2"]["me_q99"]}
        t = b18.tiers(table, experts, "R1(0)+R2s", lim)
    elif rule == "P+BL25":
        t = b18.tiers(_drop_fast(table), [_drop_fast(e) for e in experts], "R1(0)", None)
    else:
        t = b18.tiers(table, experts, "R1(0)" if rule == "P" else rule, None)
    t["in_run"] = [i in runs for i in range(len(t))]
    if rule in ("P", "P+BL25"):
        t.loc[t["in_run"], "tier"] = "none"
    return t


# ----------------------------------------------------------------------------- evaluation


def _ratio_boot(g: pd.DataFrame, num: str, den: str, seed: int = 0) -> list[float]:
    rng = np.random.default_rng(seed)
    per = g.groupby("piece")[[num, den]].sum()
    out = []
    for _ in range(2000):
        s = per.iloc[rng.integers(0, len(per), len(per))]
        out.append(s[num].sum() / s[den].sum() if s[den].sum() else np.nan)
    return [float(np.nanquantile(out, 0.025)), float(np.nanquantile(out, 0.975))]


def evaluate(rows: list[dict], b18) -> dict:
    experts: dict[tuple, list] = {}
    for r in sorted((r for r in rows if r["role"] == "expert" and not r["suspect"]),
                    key=lambda r: r["order"]):
        experts.setdefault((r["piece"], r["family"]), []).append(r["table"])
    targets = [r for r in rows if r["role"] == "target" and not r["suspect"]]
    clean, inj, tgt = {k: [] for k in RULES}, {k: [] for k in RULES}, {k: [] for k in RULES}
    runinfo = []
    for r in targets:
        ex = experts.get((r["piece"], r["family"]), [])
        _, runs, tg = run_labels(r["table"])
        for run in runs:
            runinfo.append({"piece": r["piece"], "family": r["family"], "id": r["id"],
                            "n_bars": len(run), "at_start": run[0] == 0,
                            "at_end": run[-1] == len(tg) - 1})
        for rule in RULES:
            t = rule_tiers(b18, r["table"], ex, rule, r["family"])
            t["piece"], t["family"], t["id"] = r["piece"], r["family"], r["id"]
            clean[rule].append(t)
            if not r.get("injected_suspect", True):
                ti = rule_tiers(b18, r["injected_table"], ex, rule, r["family"])
                ti = ti[ti["label"].isin(r["injected_bars"])].copy()
                ti["piece"], ti["family"], ti["id"] = r["piece"], r["family"], r["id"]
                inj[rule].append(ti)
            if r.get("targeted_bars") and not r.get("targeted_suspect", True):
                tt = rule_tiers(b18, r["targeted_table"], ex, rule, r["family"])
                tab = r["targeted_table"]
                nw = dict(zip(tab["label"], tab["n_wrong_pitch"], strict=True))
                tt = tt[tt["label"].isin(r["targeted_bars"])].copy()
                tt["checker_wrong"] = tt["label"].map(nw).astype(int)
                tt["piece"], tt["family"], tt["id"] = r["piece"], r["family"], r["id"]
                tgt[rule].append(tt)
    cat = {k: {n: pd.concat(v[k], ignore_index=True) for n, v in
               (("clean", clean), ("inj", inj), ("tgt", tgt))} for k in RULES}
    out: dict = {"n_targets": {f: sum(r["family"] == f for r in targets)
                               for f in FAMILIES.values()},
                 "n_targets_suspect": sum(r["role"] == "target" and r["suspect"] for r in rows),
                 "n_experts_suspect": sum(r["role"] == "expert" and r["suspect"] for r in rows),
                 "n_experts": {f"{k[0]}|{k[1]}": len(v) for k, v in experts.items()},
                 "n_injected_suspect": sum(bool(r.get("injected_suspect")) for r in targets),
                 "n_targeted_suspect": sum(bool(r.get("targeted_suspect")) for r in targets),
                 "n_targeted_bars": {f: int(sum(len(r.get("targeted_bars") or [])
                                                for r in targets if r["family"] == f))
                                     for f in FAMILIES.values()},
                 "rates": {}, "criteria": {}}
    for rule in RULES:
        res = {}
        for fam in ("pooled", *FAMILIES.values()):
            sel = (lambda d: d) if fam == "pooled" else (lambda d, f=fam: d[d["family"] == f])
            c = sel(cat[rule]["clean"])
            if rule in ("P", "P+BL25"):
                c = c[~c["in_run"]]
            c = c.assign(strong=(c["tier"] == "strong").astype(int),
                         notable_plus=(c["tier"] != "none").astype(int))
            i = sel(cat[rule]["inj"]).assign(
                strong=lambda d: (d["tier"] == "strong").astype(int),
                notable_plus=lambda d: (d["tier"] != "none").astype(int))
            t = sel(cat[rule]["tgt"]).assign(strong=lambda d: (d["tier"] == "strong").astype(int))
            t3 = t[t["checker_wrong"] >= TARGETED_WRONG]
            rng = np.random.default_rng(0)
            res[fam] = {"clean_strong": b18._interval(c, "strong", rng),
                        "clean_notable_plus": b18._interval(c, "notable_plus", rng),
                        "injected_strong": b18._interval(i, "strong", rng),
                        "injected_notable_plus": b18._interval(i, "notable_plus", rng),
                        "targeted_strong": b18._interval(t, "strong", rng) if len(t) else None,
                        "targeted_strong_checker3": b18._interval(t3, "strong", rng)
                        if len(t3) else None,
                        "targeted_checker3_share": float(len(t3) / len(t)) if len(t) else None}
        out["rates"][rule] = res
    # criteria
    for fam in FAMILIES.values():
        p, r0 = out["rates"]["P"][fam], out["rates"]["R0"][fam]
        c1 = p["clean_strong"]["rate"]
        pi = cat["P"]["inj"][cat["P"]["inj"]["family"] == fam]
        ri = cat["R0"]["inj"][cat["R0"]["inj"]["family"] == fam]
        both = pi[["piece"]].assign(p=(pi["tier"] == "strong").astype(int).to_numpy(),
                                    r=(ri["tier"] == "strong").astype(int).to_numpy())
        ratio = p["injected_strong"]["rate"] / r0["injected_strong"]["rate"] \
            if r0["injected_strong"]["rate"] else float("nan")
        # C2: notable+ equal to R0 outside runs (clean and injected)
        diffs = 0
        for kind in ("clean", "inj"):
            a = cat["P"][kind]
            b = cat["R0"][kind]
            m = (a["family"] == fam).to_numpy() & ~a["in_run"].to_numpy()
            diffs += int(((a["tier"] != "none").to_numpy()[m]
                          != (b["tier"] != "none").to_numpy()[m]).sum())
        c4 = p["targeted_strong"]["rate"] if p["targeted_strong"] else float("nan")
        crit = {"C1": {"value": c1, "pass": bool(C1[0] <= c1 <= C1[1])},
                "C2": {"n_differing_bars": diffs, "pass": diffs == 0},
                "C3": {"ratio": ratio, "boot95": _ratio_boot(both, "p", "r"),
                       "pass": bool(ratio >= C3_MIN)},
                "C4": {"value": c4, "pass": bool(c4 >= C4_MIN)}}
        crit["all"] = all(v["pass"] for v in crit.values())
        out["criteria"][fam] = crit
    npass = sum(out["criteria"][f]["all"] for f in FAMILIES.values())
    out["verdict"] = {2: "PASS", 1: "PARTIAL", 0: "FAIL"}[npass]
    # C5
    ri = pd.DataFrame(runinfo, columns=["piece", "family", "id", "n_bars", "at_start", "at_end"])
    c5 = {}
    for fam in FAMILIES.values():
        g = ri[ri["family"] == fam]
        cl = cat["R0"]["clean"]
        n_graded = int((cl["family"] == fam).sum())
        edge = g["at_start"] | g["at_end"]
        c5[fam] = {"n_runs": len(g), "n_run_bars": int(g["n_bars"].sum()),
                   "share_of_graded_bars": float(g["n_bars"].sum() / n_graded)
                   if n_graded else None,
                   "n_targets_with_run": int(g["id"].nunique()),
                   "n_runs_at_start": int(g["at_start"].sum()),
                   "n_runs_at_end": int(g["at_end"].sum()),
                   "share_runs_at_start_or_end": float(edge.mean()) if len(g) else None,
                   "share_run_bars_at_start_or_end": float(g.loc[edge, "n_bars"].sum()
                                                           / g["n_bars"].sum())
                   if len(g) else None}
    out["C5_runs"] = c5
    return out


# ----------------------------------------------------------------------------- main


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--from-cache", action="store_true")
    args = ap.parse_args()
    _quiet()
    b18 = _bl18()
    cache = OUT / "bl18b_tables.pkl"
    summ: dict = {"prereg": "docs/specs/report-validation.md section 6", "seed": SEED}
    if args.from_cache:
        blob = pickle.loads(cache.read_bytes())
        rows, summ["n_eligible_pieces"] = blob["rows"], blob["n_eligible_pieces"]
    else:
        jobs, n_elig = draw_jobs()
        summ["n_eligible_pieces"] = n_elig
        print(len(jobs), "jobs;", n_elig, "eligible pieces", flush=True)
        rows, failed = [], []
        with ProcessPoolExecutor(args.workers) as ex:
            futs = {ex.submit(align_expert, j): j for j in jobs if j["role"] == "expert"}
            for k, fu in enumerate(as_completed(futs)):
                try:
                    rows.append(fu.result())
                except Exception as e:  # noqa: BLE001 - count failures
                    failed.append((futs[fu]["id"], repr(e)[:200]))
                if k % 50 == 0:
                    print("experts", k, flush=True)
            exp: dict[tuple, list] = {}
            for r in sorted((r for r in rows if not r["suspect"]), key=lambda r: r["order"]):
                exp.setdefault((r["piece"], r["family"]), []).append(r["table"])
            futs = {ex.submit(align_target, j, exp.get((j["piece"], j["family"]), [])): j
                    for j in jobs if j["role"] == "target"}
            for k, fu in enumerate(as_completed(futs)):
                try:
                    rows.append(fu.result())
                except Exception as e:  # noqa: BLE001
                    failed.append((futs[fu]["id"], repr(e)[:200]))
                if k % 20 == 0:
                    print("targets", k, flush=True)
        summ["failed"] = failed
        cache.write_bytes(pickle.dumps({"rows": rows, "n_eligible_pieces": n_elig}))
    summ["pieces"] = sorted({r["piece"] for r in rows})
    summ["n_jobs_ok"] = len(rows)
    summ.update(evaluate(rows, b18))
    (OUT / "bl18b_summary.json").write_text(json.dumps(summ, indent=1, default=float))
    print(json.dumps({k: summ[k] for k in ("pieces", "n_targets", "verdict", "criteria",
                                           "C5_runs", "n_targeted_bars")},
                     indent=1, default=float))


if __name__ == "__main__":
    main()
