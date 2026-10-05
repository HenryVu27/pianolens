"""BL-17 scoring. R-08a's scoring functions (``map_events``, ``score_movement``,
``boundary_prf``, ``match_pairs``, ``as_events``, ``summarise``) and R-08d's helpers
(``detector``, ``prev_onset``, ``extra_rows``, ``to_quarters``, ``t_interval``, ``one_sided_p``)
are imported unchanged (R-08d's ``score.py`` via importlib, which itself loads R-08a's).

    uv run python .../score.py --comparators
    uv run python .../score.py --harness [--scratch DIR]
    uv run python .../score.py --llm-dir <dir with P##.json> --run A|B|U
    uv run python .../score.py --compare

Runs A and B are disguised (blind_input/, bars_P##.csv); run U is undisguised
(blind_input_U/, bars_U_P##.csv) on the U subset only.
"""

from __future__ import annotations

import importlib.util
import json
import logging
import sys
import tempfile
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
EXP = ROOT / "experiments"
R08B = EXP / "2026-09-28-R-08b-llm-memorisation-control"
R08D = EXP / "2026-09-28-R-08d-llm-romantic-repertoire"
warnings.filterwarnings("ignore")
logging.disable(logging.WARNING)


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


D = _load("r08d_score", R08D / "score.py")  # R-08d scoring (loads R-08a's as D.S)
S = D.S  # R-08a scoring functions; S.TYPES includes PC (set by R-08d)
DG = _load("r08b_disguise_s", R08B / "disguise.py")  # parse_pointers (both wordings)

ART = HERE / "artifacts"
BLIND = HERE / "blind_input"
BLIND_U = HERE / "blind_input_U"
D13 = ROOT / "data" / "interim" / "dcml_romantic"
SEED = 20261002
N_BOOT = 10_000
N_RANDOM = 200
BAR = 0.70
RUNS = ("A", "B", "U")
PRIMARY_RUNS = ("A", "B")
VARIANTS = {"llm": {}, "llm_unsnapped": {"snap": False}, "llm_conf50": {"min_conf": 0.5}}
# earlier primaries (R-08d / R-08c artifacts), descriptive only
R08D_PRIMARY, R08C_PRIMARY = 0.737, 0.750


# --------------------------------------------------------------------------- inputs


def selection() -> list[dict]:
    return json.loads((ART / "selection.json").read_text())["picks"]


def movement_inputs(run: str = "A") -> dict[str, dict]:
    """Per P id: corpus, stem, stratum, bar table and pointers of the rendering the run saw,
    ground truth, D-13 cached arrays. Run U only covers the U subset."""
    Dc = pd.read_pickle(D13 / "cands.pkl")
    out = {}
    for p in selection():
        mid = p["id"]
        if run == "U" and not p["undisguised_run"]:
            continue
        gt = json.loads((ART / "ground_truth" / f"{mid}.json").read_text())
        d = Dc[gt["score_id"]]
        assert np.allclose(sorted(d["ends"]), gt["ends"]) and np.allclose(
            sorted(d["starts"]), gt["starts"]), mid
        bars_f = ART / (f"bars_U_{mid}.csv" if run == "U" else f"bars_{mid}.csv")
        txt = ((BLIND_U if run == "U" else BLIND) / f"{mid}.txt").read_text()
        out[mid] = {"corpus": p["corpus"], "stem": p["stem"], "stratum": p["stratum"],
                    "bars": pd.read_csv(bars_f, dtype={"written": str}), "gt": gt, "d": d,
                    "pointers": DG.parse_pointers(txt)}
    return out


def comparator_predictions(mv: dict) -> dict[str, tuple[list | None, list | None]]:
    d = mv["d"]
    ob = np.asarray(d["onset_beats"], float)
    db = np.asarray(d["downbeats"], float)
    return {
        "cadence": D.detector(mv["corpus"], mv["stem"]),
        "proxy_last_onset": (D.prev_onset(ob, d["proxy"][1:]) + [float(ob[-1])], None),
        "proxy": (None, list(d["proxy"])),
        "grid4": (db[3::4].tolist(), db[::4].tolist()),
        "oracle_dcml_ends": (list(mv["gt"]["ends"]), list(mv["gt"]["starts"])),
    }


# --------------------------------------------------------------------------- controls


def halved_ends(mv: dict) -> list[float]:
    """DCML ends plus, inside every DCML phrase-end segment (from the first onset to the first
    end, and between consecutive ends), the onset nearest to its midpoint (F-05e control)."""
    ob = np.asarray(mv["d"]["onset_beats"], float)
    ends = sorted(mv["gt"]["ends"])
    edges = [float(ob[0])] + ends
    mids = []
    for a, b in zip(edges[:-1], edges[1:], strict=True):
        inside = ob[(ob > a + 1e-6) & (ob < b - 1e-6)]
        if len(inside):
            mids.append(float(inside[np.argmin(np.abs(inside - (a + b) / 2))]))
    return sorted(ends + mids)


def random_f1(mv: dict, n_pred: int, rng) -> float:
    """Mean end F1 (+-1 beat) of n_pred ends drawn at random from the movement's onsets
    (F-05e control: density alone)."""
    ob = np.unique(np.asarray(mv["d"]["onset_beats"], float))
    n = min(n_pred, len(ob))
    f = [S.boundary_prf(sorted(rng.choice(ob, n, replace=False).tolist()), mv["gt"]["ends"],
                        1.0, -np.inf)["F1"] for _ in range(N_RANDOM)]
    return float(np.mean(f))


# --------------------------------------------------------------------------- comparators


def run_comparators(out: Path = ART) -> pd.DataFrame:
    M = movement_inputs("A")
    rng = np.random.default_rng(SEED)
    rows = []
    for mid, mv in M.items():
        for m, (en, stt) in comparator_predictions(mv).items():
            rows += S.score_movement(mid, mv, en, stt, None, m)
            if en is not None and m in ("cadence", "grid4", "proxy_last_onset",
                                        "oracle_dcml_ends"):
                rows += D.extra_rows(mid, mv, en, m)
        h = halved_ends(mv)
        rows.append({"id": mid, "movement": mv["stem"], "method": "halved_dcml", "target": "end",
                     "tol": "1beat", **S.boundary_prf(h, mv["gt"]["ends"], 1.0, -np.inf)})
        rows.append({"id": mid, "movement": mv["stem"], "method": "random_at_dcml_count",
                     "target": "end", "tol": "1beat",
                     "F1": random_f1(mv, len(mv["gt"]["ends"]), rng)})
    B = pd.DataFrame(rows)
    B.to_csv(out / "comparators.csv", index=False)
    main = B[B.method.isin(["cadence", "proxy_last_onset", "proxy", "grid4", "oracle_dcml_ends"])
             & ~B.target.str.startswith("end_") & B.tol.isin(["1beat", "1bar"])]
    txt = S.summarise(main)
    (out / "comparators_summary.txt").write_text(txt + "\n")
    print(txt)
    return B


# --------------------------------------------------------------------------- LLM runs


def score_events(M: dict[str, dict], ann_by_id: dict[str, dict], run: str
                 ) -> tuple[pd.DataFrame, dict]:
    rows, info = [], {}
    rng = np.random.default_rng(SEED + {"A": 1, "B": 2, "U": 3}.get(run, 0))
    for mid, mv in M.items():
        ann = ann_by_id.get(mid)
        if ann is None:
            info[mid] = {"missing": True}
            continue
        assert ann.get("movement") == mid, (mid, ann.get("movement"))
        for vname, kw in VARIANTS.items():
            df, stats = S.map_events(ann.get("events", []), mv, **kw)
            e = df[df["type"] == "phrase_end"]
            s = df[df["type"] == "phrase_start"]
            types = dict(zip(e["beat"].round(6), e["cadence"], strict=True))
            cm = df[(df["type"] == "cadence")
                    | ((df["type"] == "phrase_end") & (df["cadence"] != "none"))]
            cm = cm.sort_values("confidence", ascending=False).drop_duplicates("beat")
            marks = dict(zip(cm["beat"].astype(float), cm["cadence"], strict=True))
            rows += S.score_movement(mid, mv, e["beat"].tolist(), s["beat"].tolist(), types,
                                     vname, marks if vname == "llm" else None)
            if vname == "llm":
                ends = e["beat"].tolist()
                rows += D.extra_rows(mid, mv, ends, vname)
                rows.append({"id": mid, "movement": mv["stem"], "method": "random_at_llm_count",
                             "target": "end", "tol": "1beat",
                             "F1": random_f1(mv, len(ends), rng), "n_pred": len(ends)})
            info[f"{mid} {vname}"] = stats
        info[f"{mid} recognised_piece"] = ann.get("recognised_piece")
    B = pd.DataFrame(rows)
    B["run"] = run
    return B, info


def load_dir(folder: Path) -> dict[str, dict]:
    return {f.stem: json.loads(f.read_text()) for f in sorted(folder.glob("P*.json"))}


def run_llm(folder: Path, run: str, out: Path = ART) -> pd.DataFrame:
    M = movement_inputs(run)
    B, info = score_events(M, load_dir(folder), run)
    B.to_csv(out / f"scores_{run}.csv", index=False)
    txt = S.summarise(B[B.method.isin(list(VARIANTS)) & B.target.isin(["end", "start",
                                                                       "cadence"])
                        & B.tol.isin(["1beat", "1bar"])].drop(columns=["run"]))
    txt += f"\n\nrun {run}; mapping stats and recognised_piece:\n"
    txt += json.dumps(info, indent=1, ensure_ascii=False)
    (out / f"summary_{run}.txt").write_text(txt + "\n")
    print(txt[:3000])
    return B


# --------------------------------------------------------------------------- compare


def boot(x, rng) -> tuple[float, float, float]:
    x = np.asarray(x, float)
    idx = rng.integers(0, len(x), size=(N_BOOT, len(x)))
    bs = x[idx].mean(axis=1)
    return float(x.mean()), float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))


def fmt(name: str, x, rng) -> str:
    x = np.asarray(x, float)
    m, lo, hi = boot(x, rng)
    tl, th = D.t_interval(x)
    return (f"{name}: {m:+.3f}  bootstrap [{lo:+.3f}, {hi:+.3f}]  t [{tl:+.3f}, {th:+.3f}] "
            f"(n {len(x)}, {len(x) - 1} df, half-width {(th - tl) / 2:.3f})")


def verdict(x) -> str:
    tl, th = D.t_interval(x)
    if tl > BAR:
        return "MADE (t lower end above 0.70)"
    if th < BAR:
        return "REJECTED (t upper end below 0.70)"
    return "INCONCLUSIVE (t-interval contains 0.70)"


def f1(df: pd.DataFrame, method: str, target: str = "end", tol: str = "1beat",
       col: str = "F1") -> pd.Series:
    g = df[(df.method == method) & (df.target == target) & (df.tol == tol)]
    return g.set_index("id")[col].astype(float)


def misses_extras(mv: dict, ann: dict) -> list[str]:
    """Every unmatched predicted end (extra) and unmatched DCML end (miss) at +-1 beat, with the
    distance in bars to the nearest DCML end (extras) or predicted end (misses)."""
    df, _ = S.map_events(ann.get("events", []), mv)
    pred = sorted(df.loc[df.type == "phrase_end", "beat"].tolist())
    true = sorted(mv["gt"]["ends"])
    pairs = S.match_pairs(pred, true, 1.0, -np.inf)
    mp = {round(a, 6) for a, _ in pairs}
    mt = {round(b, 6) for _, b in pairs}
    bpb = float(mv["d"]["meta"]["beats_per_bar"])
    bars = mv["bars"]

    def where(x):
        b, beat = S.to_bar_beat(bars, x)
        return f"bar {b} beat {beat}"

    out = []
    for x in pred:
        if round(x, 6) not in mp:
            dist = min(abs(x - t) for t in true) / bpb
            out.append(f"extra {where(x)} ({dist:.1f} bars from nearest DCML end)")
    for t in true:
        if round(t, 6) not in mt:
            dist = min((abs(t - x) for x in pred), default=np.inf) / bpb
            out.append(f"miss  {where(t)} ({dist:.1f} bars from nearest predicted end)")
    return out


def compare(art: Path = ART, ann_root: Path = HERE) -> str:
    rng = np.random.default_rng(SEED)
    runs = {r: pd.read_csv(art / f"scores_{r}.csv") for r in RUNS
            if (art / f"scores_{r}.csv").exists()}
    if not any(r in runs for r in PRIMARY_RUNS):
        print("no primary run scores yet")
        return ""
    comp = pd.read_csv(ART / "comparators.csv")
    picks = selection()
    ids = [p["id"] for p in picks]
    info = {p["id"]: p for p in picks}
    simple = [i for i in ids if info[i]["stratum"] == "simple"]
    comp_ids = [i for i in ids if info[i]["stratum"] == "compound"]
    tab = pd.DataFrame({r: f1(runs[r], "llm") for r in PRIMARY_RUNS if r in runs}).reindex(ids)
    llm = tab.mean(axis=1, skipna=True)
    det = f1(comp, "cadence").reindex(ids)
    out = [f"BL-17 comparison. Runs: {list(runs)}; movements: {len(ids)} "
           f"({len(simple)} simple, {len(comp_ids)} compound)"]
    missing = int(tab.isna().sum().sum())
    if missing:
        out.append(f"DISCLOSE: {missing} run x movement cells missing in A/B; those movements "
                   "use the run that exists.")
    t = tab.copy()
    t.insert(0, "stem", [info[i]["stem"] for i in ids])
    t.insert(0, "corpus", [info[i]["corpus"].split("_")[0] for i in ids])
    t.insert(0, "stratum", [info[i]["stratum"] for i in ids])
    t["LLM"] = llm
    t["abs_A_B"] = tab.max(axis=1) - tab.min(axis=1)
    if "U" in runs:
        t["U"] = f1(runs["U"], "llm").reindex(ids)
    t["detector"] = det
    t["proxy_last"] = f1(comp, "proxy_last_onset").reindex(ids)
    t["grid4"] = f1(comp, "grid4").reindex(ids)
    t["halved_dcml"] = f1(comp, "halved_dcml").reindex(ids)
    t["n_dcml_ends"] = f1(comp, "oracle_dcml_ends", col="n_true").reindex(ids).astype(int)
    out.append("\nPer movement end F1 at +-1 beat (LLM = mean of A and B)\n"
               + t.sort_values(["stratum", "corpus", "stem"], ascending=[False, True, True])
               .round(3).to_string())

    # ---------------- primary: simple stratum
    x = llm[simple]
    out.append(f"\n=== PRIMARY (simple meters, n = {len(simple)})")
    out.append(fmt("mean LLM end F1 (mean of A and B per movement)", x, rng))
    out.append(fmt("mean(LLM - detector), paired", x - det[simple], rng))
    out.append(f"VERDICT (claim 'mean above 0.70'): {verdict(x)}")
    tl, th = D.t_interval(x)
    out.append(f"usable interval (t half-width <= 0.10): {'yes' if (th - tl) / 2 <= 0.10 else 'no'}"
               f" ({(th - tl) / 2:.3f})")
    out.append(f"R-08 point-estimate rule (continuity): {x.mean():.3f} "
               f"{'>=' if x.mean() >= BAR else '<'} 0.70 -> "
               f"{'GO' if x.mean() >= BAR else 'NO-GO'}")
    dl, _ = D.t_interval(x - det[simple])
    out.append("Beats the detector: " + ("shown" if dl > 0 else "not shown")
               + f" (t lower end {dl:+.3f}); LLM ahead on "
               f"{int((x > det[simple]).sum())} of {len(simple)}")
    out.append(f"observed between-movement SD {x.std(ddof=1):.3f} (assumed in the "
               "reachability check: 0.130 / 0.240 / empirical)")
    worst = tab.loc[simple].min(axis=1)
    best = tab.loc[simple].max(axis=1)
    loo = {i: float(x.drop(i).mean()) for i in simple}
    out.append(f"near the bar: one-sided p (mean > 0.70) {D.one_sided_p(x, BAR):.4f}; worst-run "
               f"{worst.mean():.3f} (t [{D.t_interval(worst)[0]:.3f}, "
               f"{D.t_interval(worst)[1]:.3f}]); best-run {best.mean():.3f}; LOO min "
               f"{min(loo.values()):.3f} (without {min(loo, key=loo.get)}), max "
               f"{max(loo.values()):.3f}")
    for r in PRIMARY_RUNS:
        if r in tab:
            out.append(fmt(f"run {r} alone", tab.loc[simple, r].dropna(), rng))
    out.append("per corpus (descriptive): " + "; ".join(
        f"{c.split('_')[0]} n {len(g)} mean {x[g].mean():.3f}"
        + (f" t [{D.t_interval(x[g])[0]:.3f}, {D.t_interval(x[g])[1]:.3f}]" if len(g) > 2 else "")
        for c in dict.fromkeys(info[i]["corpus"] for i in simple)
        for g in [[i for i in simple if info[i]["corpus"] == c]]))
    out.append(f"movements below 0.50: {[i for i in simple if x[i] < 0.5]}; "
               f"below 0.70: {int((x < BAR).sum())} of {len(simple)}")

    # ---------------- compound stratum
    y = llm[comp_ids]
    out.append(f"\n=== COMPOUND METERS (n = {len(comp_ids)}; reported separately)")
    out.append(fmt("mean LLM end F1", y, rng))
    out.append(fmt("mean(LLM - detector), paired", y - det[comp_ids], rng))
    out.append(f"same verdict rule, descriptive: {verdict(y)}; point estimate "
               f"{'>=' if y.mean() >= BAR else '<'} 0.70")
    all30 = llm[ids]
    out.append(fmt(f"\nALL {len(ids)} movements pooled (descriptive)", all30, rng))

    # ---------------- sensitivities
    out.append("\nSensitivities (LLM = mean of A and B per movement; detector alongside)")
    for target, tol, label in (("end", "0beat", "exact onset"),
                               ("end", "1quarter", "+-1 quarter note"),
                               ("end_once", "1beat", "each repeated passage once"),
                               ("end", "1bar", "+-1 bar")):
        lv = pd.DataFrame({r: f1(runs[r], "llm", target, tol) for r in PRIMARY_RUNS
                           if r in runs}).reindex(ids).mean(axis=1)
        dv = f1(comp, "cadence", target, tol).reindex(ids)
        for name, g in (("simple", simple), ("compound", comp_ids)):
            out.append(f"  {label:28s} {name:8s} LLM {lv[g].mean():.3f} "
                       f"t [{D.t_interval(lv[g])[0]:.3f}, {D.t_interval(lv[g])[1]:.3f}]  "
                       f"detector {dv[g].mean():.3f}")
    for r in PRIMARY_RUNS:
        if r in runs:
            c50 = f1(runs[r], "llm_conf50").reindex(ids)
            out.append(f"  confidence >= 0.5 ({r}): simple {c50[simple].mean():.3f}, "
                       f"compound {c50[comp_ids].mean():.3f}")

    # ---------------- controls (F-05e lesson)
    out.append("\nBoundary controls (F-05e): random ends at the LLM's count (mean of 200 draws) "
               "and halved DCML phrases")
    for name, g in (("simple", simple), ("compound", comp_ids)):
        rnd = pd.DataFrame({r: f1(runs[r], "random_at_llm_count") for r in PRIMARY_RUNS
                            if r in runs}).reindex(ids).mean(axis=1)
        out.append(f"  {name:8s} LLM {llm[g].mean():.3f}; random at LLM count "
                   f"{rnd[g].mean():.3f}; random at DCML count "
                   f"{f1(comp, 'random_at_dcml_count').reindex(g).mean():.3f}; halved DCML "
                   f"(correct but 2x finer) {f1(comp, 'halved_dcml').reindex(g).mean():.3f}; "
                   f"LLM - random paired {(llm[g] - rnd[g]).mean():+.3f} "
                   f"t [{D.t_interval(llm[g] - rnd[g])[0]:+.3f}, "
                   f"{D.t_interval(llm[g] - rnd[g])[1]:+.3f}]")

    # ---------------- run-to-run
    sd = tab.std(axis=1, ddof=1)
    out.append(f"\nRun-to-run (A vs B): run means A {tab['A'].mean():.3f}, B {tab['B'].mean():.3f}"
               f"; mean within-movement SD {sd.mean():.3f} (R-08d 0.056, R-08c 0.027); max |A-B| "
               f"{(tab.max(axis=1) - tab.min(axis=1)).max():.3f}")

    # ---------------- disguise effect (U subset)
    if "U" in runs:
        u = f1(runs["U"], "llm")
        uid = [i for i in ids if i in u.index]
        dlt = u[uid] - llm[uid]
        out.append(f"\nDisguise effect on the U subset (n {len(uid)}; descriptive): U "
                   f"{u[uid].mean():.3f} vs disguised mean(A,B) {llm[uid].mean():.3f}")
        out.append("  " + fmt("U - disguised, paired", dlt, rng))
        out.append("  per movement: " + ", ".join(
            f"{i} U {u[i]:.3f} / A {tab.loc[i, 'A']:.3f} / B {tab.loc[i, 'B']:.3f}" for i in uid))
        inside = sum(min(tab.loc[i, 'A'], tab.loc[i, 'B']) <= u[i] <= max(tab.loc[i, 'A'],
                                                                         tab.loc[i, 'B'])
                     for i in uid)
        out.append(f"  U inside the A-B range in {inside} of {len(uid)}; above "
                   f"{int((u[uid] > tab.loc[uid].max(axis=1)).sum())}, below "
                   f"{int((u[uid] < tab.loc[uid].min(axis=1)).sum())}")

    # ---------------- cadenced vs uncadenced, granularity
    out.append("\nRecall of DCML phrase ends at +-1 beat split by a DCML cadence label at the "
               "same beat (pooled tp/n)")

    def split_line(df, method, g):
        h = df[(df.method == method) & df.target.isin(["end_cadenced", "end_uncadenced"])
               & df.id.isin(g)]
        s = h.groupby("target")[["tp", "n_true"]].sum()
        return "  ".join(f"{k[4:]} {int(v.tp)}/{int(v.n_true)}" for k, v in s.iterrows())

    for name, g in (("simple", simple), ("compound", comp_ids)):
        for r in runs:
            out.append(f"  {name:8s} {r:9s} {split_line(runs[r], 'llm', g)}")
        out.append(f"  {name:8s} detector  {split_line(comp, 'cadence', g)}")
    out.append("\nGranularity per movement and run (P, R at +-1 beat; predicted / DCML ends)")
    n_true = f1(comp, "oracle_dcml_ends", col="n_true")
    for r in runs:
        P, R = f1(runs[r], "llm", col="P"), f1(runs[r], "llm", col="R")
        npred = f1(runs[r], "llm", col="n_pred")
        out.append(f"  run {r}: " + "; ".join(
            f"{i} P {P[i]:.2f} R {R[i]:.2f} x{npred[i] / n_true[i]:.2f}" for i in ids
            if i in P.index))
        ratio = (npred / n_true.reindex(npred.index))
        out.append(f"    median ratio {ratio.median():.2f}; ratio > 1.5 in "
                   f"{int((ratio > 1.5).sum())}, < 0.67 in {int((ratio < 0.67).sum())} of "
                   f"{len(ratio)}; mean P {P.mean():.3f}, mean R {R.mean():.3f}")

    # ---------------- cadence recall by type
    out.append("\nRecall of DCML cadences by type at +-1 beat via phrase ends (pooled tp/n)")

    def recall_line(df, method):
        g = df[(df.method == method) & df.target.str.startswith("cad_")]
        s = g.groupby("target")[["tp", "n_true"]].sum()
        return "  ".join(f"{k[4:]} {int(v.tp)}/{int(v.n_true)}" for k, v in s.iterrows())

    for r in runs:
        out.append(f"  {r:18s} {recall_line(runs[r], 'llm')}")
    out.append(f"  {'detector':18s} {recall_line(comp, 'cadence')}")
    out.append(f"  {'oracle_dcml_ends':18s} {recall_line(comp, 'oracle_dcml_ends')}")

    # ---------------- low scorers: misses and extras (R-08d audit lesson)
    out.append("\nMisses and extras of every movement with LLM < 0.50 (per run)")
    for r in PRIMARY_RUNS:
        M = movement_inputs(r)
        for i in ids:
            if llm[i] < 0.5 and (ann_root / f"annotations_{r}" / f"{i}.json").exists():
                ann = json.loads((ann_root / f"annotations_{r}" / f"{i}.json").read_text())
                out.append(f"  {r} {i} ({info[i]['stem']}, F1 {tab.loc[i, r]:.3f}):")
                out += [f"     {m}" for m in misses_extras(M[i], ann)]

    # ---------------- recognition (within movement only)
    rec_f = ann_root / "recognition.json"
    recog = json.loads(rec_f.read_text()) if rec_f.exists() else {}
    out.append("\nRecognition (strings; classes from recognition.json)")
    rows = []
    for r in runs:
        for qf in sorted((ann_root / f"annotations_{r}").glob("P*.json")):
            a = json.loads(qf.read_text())
            v = f1(runs[r], "llm").get(qf.stem, np.nan)
            rows.append({"run": r, "id": qf.stem, "class": recog.get(r, {}).get(qf.stem,
                                                                                 "unclassified"),
                         "F1": round(float(v), 3), "recognised_piece": a.get("recognised_piece")})
    Rt = pd.DataFrame(rows)
    if len(Rt):
        named = Rt[Rt["recognised_piece"].notna()]
        out.append(named.to_string(index=False) if len(named) else "  (no non-null strings)")
        known = sorted(Rt[Rt["class"].isin(["correct", "composer"])]["id"].unique().tolist())
        out.append("  class counts: " + json.dumps(Rt.groupby(["run", "class"]).size()
                                                   .unstack(fill_value=0).to_dict()))
        for i, g in Rt.groupby("id"):
            if g["class"].nunique() > 1:
                out.append(f"  within {i}: " + ", ".join(
                    f"{x.run} {x['class']} F1 {x.F1:.3f}" for _, x in g.iterrows()))
        if (Rt["class"] == "unclassified").any():
            out.append("RECOGNITION: UNDETERMINED (fill recognition.json)")
        else:
            ks = [i for i in known if i in simple]
            out.append(f"RECOGNITION: {len(ks)} of {len(simple)} simple-stratum movements "
                       f"recognised (correct or composer) in at least one run: {known}"
                       + (" -> verdict is 'on largely recognised pieces'"
                          if len(ks) >= 8 else ""))
            if ks:
                keep = [i for i in simple if i not in ks]
                out.append(f"  sensitivity without them ({len(keep)}): "
                           + fmt("LLM", llm[keep], rng))
    out.append(f"\nDescriptive only (different pieces, not a test): R-08d primary {R08D_PRIMARY}"
               f", R-08c {R08C_PRIMARY}; this primary {x.mean():.3f}.")
    txt = "\n".join(out)
    (art / "bl17_summary.txt").write_text(txt + "\n")
    print(txt)
    return txt


# --------------------------------------------------------------------------- harness


def harness(scratch: Path | None = None) -> bool:
    ref = pd.read_csv(D13 / "comparators.csv")
    ok, lines = True, []
    det_prop, det_own = {}, {}
    for run in ("A", "U"):
        M = movement_inputs(run)
        for mid, mv in M.items():
            gt = mv["gt"]
            ends, starts = list(gt["ends"]), list(gt["starts"])
            ev = S.as_events(mv, ends, starts)
            df, _ = S.map_events(ev, mv, propagate=False)
            r = pd.DataFrame(S.score_movement(mid, mv, df.loc[df.type == "phrase_end", "beat"]
                                              .tolist(), df.loc[df.type == "phrase_start",
                                                                "beat"].tolist(), None, "o"))
            f_all = r[(r.tol == "1beat") & r.target.isin(["end", "start"])]["F1"].round(4)
            o_ok = bool(np.allclose(f_all, 1.0))
            ev_p = [e for e in ev if e["bar"] not in mv["pointers"]]
            df, _ = S.map_events(ev_p, mv, propagate=True)
            r = pd.DataFrame(S.score_movement(mid, mv, df.loc[df.type == "phrase_end", "beat"]
                                              .tolist(), df.loc[df.type == "phrase_start",
                                                                "beat"].tolist(), None, "o"))
            f_pr = r[(r.tol == "1beat") & r.target.isin(["end", "start"])]["F1"].round(4)
            bar_min = int(mv["bars"]["bar"].min())
            line = (f"{run} {mid} ({mv['stratum']}): first bar {bar_min}; oracle end/start F1 "
                    f"{f_all.tolist()} -> {'OK' if o_ok else 'FAIL'}; printed bars + "
                    f"propagation {f_pr.tolist()}")
            good = o_ok
            if run == "A":
                en, stt = D.detector(mv["corpus"], mv["stem"])
                df, _ = S.map_events(S.as_events(mv, en, stt), mv, propagate=False)
                pe = df.loc[df.type == "phrase_end", "beat"].tolist()
                ps = df.loc[df.type == "phrase_start", "beat"].tolist()
                same = np.allclose(pe, sorted(en)) and np.allclose(ps, sorted(set(stt)))
                mine = pd.DataFrame(S.score_movement(mid, mv, pe, ps, None, "cadence_ev"))
                rr = ref[(ref["corpus"] == mv["corpus"]) & (ref["movement"] == mv["stem"])
                         & (ref["method"] == "cadence")]
                n_cmp = n_bad = 0
                for _, row in rr.iterrows():
                    o = mine[(mine["target"] == row["target"]) & (mine["tol"] == row["tol"])]
                    if o.empty:
                        continue
                    o = o.iloc[0]
                    cols = ["tp", "n_pred", "n_true"] + ([] if row["target"].startswith("cad_")
                                                         else ["F1"])
                    n_cmp += 1
                    n_bad += not all(np.isclose(o[c], row[c], equal_nan=True) for c in cols)
                d_ok = same and n_bad == 0 and n_cmp == len(rr) and n_cmp > 0
                df, _ = S.map_events(S.as_events(mv, en, stt), mv, propagate=True)
                det_prop[mid] = S.boundary_prf(df.loc[df.type == "phrase_end", "beat"].tolist(),
                                               gt["ends"], 1.0, -np.inf)["F1"]
                det_own[mid] = float(mine[(mine.target == "end") & (mine.tol == "1beat")]
                                     ["F1"].iloc[0])
                en_t, st_t = D.detector(mv["corpus"], mv["stem"], tempo_word=True)
                tw_ok = np.allclose(en_t, en) and np.allclose(st_t, stt)
                good &= d_ok and tw_ok
                line += (f"; detector via events {n_cmp}/{len(rr)} D-13 rows, {n_bad} mismatches"
                         f" -> {'OK' if d_ok else 'FAIL'} (own {det_own[mid]:.4f}, propagated "
                         f"{det_prop[mid]:.4f}); same with tempo word -> "
                         f"{'OK' if tw_ok else 'FAIL'}")
            ok &= good
            lines.append(line)
    n_incons = sum(not np.isclose(det_own[m], det_prop[m]) for m in det_own)
    lines.append(f"detector pass-consistency: propagated F1 differs from own in {n_incons} of "
                 f"{len(det_own)} movements")
    # end-to-end dry run of --llm-dir and --compare in a scratch folder
    tmp_ctx = None
    if scratch is None:
        tmp_ctx = tempfile.TemporaryDirectory()
        scratch = Path(tmp_ctx.name)
    scratch.mkdir(parents=True, exist_ok=True)
    simple = [p["id"] for p in selection() if p["stratum"] == "simple"]
    for kind in ("oracle", "detector"):
        root = scratch / kind
        art = root / "artifacts"
        art.mkdir(parents=True, exist_ok=True)
        for run in RUNS:
            M = movement_inputs(run)
            d = root / f"annotations_{run}"
            d.mkdir(exist_ok=True)
            for mid, mv in M.items():
                en, stt = ((mv["gt"]["ends"], mv["gt"]["starts"]) if kind == "oracle"
                           else D.detector(mv["corpus"], mv["stem"]))
                ann = {"movement": mid, "recognised_piece": None, "notes": "",
                       "events": S.as_events(mv, list(en), list(stt))}
                (d / f"{mid}.json").write_text(json.dumps(ann))
            run_llm(d, run, out=art)
        (root / "recognition.json").write_text(json.dumps(
            {r: {m: "none" for m in movement_inputs(r)} for r in RUNS}))
        txt = compare(art=art, ann_root=root)
        prim = float(txt.split("mean LLM end F1 (mean of A and B per movement): ")[1].split()[0])
        want = 1.0 if kind == "oracle" else float(np.mean([det_prop[m] for m in simple]))
        e_ok = bool(np.isclose(prim, want, atol=5e-4))
        ok &= e_ok
        lines.append(f"dry run ({kind} as annotation, runs A, B, U): primary {prim:.4f} vs "
                     f"expected {want:.4f} -> {'OK' if e_ok else 'FAIL'}")
    if tmp_ctx is not None:
        tmp_ctx.cleanup()
    txt = "\n".join(lines) + f"\nHARNESS {'PASSED' if ok else 'FAILED'}"
    (ART / "harness.txt").write_text(txt + "\n")
    print("\n" + txt)
    return ok


if __name__ == "__main__":
    argv = sys.argv
    if "--comparators" in argv:
        run_comparators()
    if "--harness" in argv:
        sc = Path(argv[argv.index("--scratch") + 1]) if "--scratch" in argv else None
        sys.exit(0 if harness(sc) else 1)
    if "--llm-dir" in argv:
        run = argv[argv.index("--run") + 1]
        assert run in RUNS, "runs are A, B, U"
        run_llm(Path(argv[argv.index("--llm-dir") + 1]), run)
    if "--compare" in argv:
        compare()
