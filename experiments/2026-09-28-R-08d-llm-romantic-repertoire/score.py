"""R-08d scoring. Reuses R-08a's scoring functions (``map_events``, ``score_movement``,
``summarise``, ``as_events``, ``pointer_map``, ``boundary_prf``, ``match_pairs``) unchanged,
loaded from R-08a's ``score.py`` with importlib. The aggregation follows R-08c's ``score.py``
(two runs per movement), plus the near-the-bar reporting of the R-08c audit, the
cadenced / uncadenced recall split and the granularity table (README "Metrics").

    uv run python .../score.py --comparators
    uv run python .../score.py --harness [--scratch DIR]
    uv run python .../score.py --llm-dir <dir with R#.json> --run A
    uv run python .../score.py --compare

Runs are named A and B (R1..R5 are movement ids).
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
from scipy import stats as st

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
R08A = ROOT / "experiments" / "2026-09-28-R-08a-llm-phrase-pilot"
sys.path.insert(0, str(R08A))
sys.path.insert(0, str(ROOT / "scripts"))
warnings.filterwarnings("ignore")
logging.disable(logging.WARNING)

_spec = importlib.util.spec_from_file_location("r08a_score", R08A / "score.py")
S = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(S)  # R-08a scoring module; this private copy is re-pointed below

from pianolens.data import dcml  # noqa: E402

ART = HERE / "artifacts"
BLIND = HERE / "blind_input"
D13 = ROOT / "data" / "interim" / "dcml_romantic"
S.BLIND = BLIND  # pointer_map parses the R-08d renderings
S.TYPES = tuple(dcml.CADENCE_TYPES)  # adds PC to the per-type rows
SEED = 20261001
N_BOOT = 10_000
BAR = 0.70
RUNS = ("A", "B")
VARIANTS = {"llm": {}, "llm_unsnapped": {"snap": False}, "llm_conf50": {"min_conf": 0.5}}
# earlier primaries (artifacts/r08c_summary.txt, r08b_summary.txt), descriptive only
R08C, R08B_A, R08B_U = 0.750, 0.802, 0.789


# --------------------------------------------------------------------------- inputs


def selection() -> list[dict]:
    return json.loads((ART / "selection.json").read_text())["picks"]


def movement_inputs() -> dict[str, dict]:
    """Per R id: corpus, stem, bar table, ground truth, D-13 cached arrays, pointer map."""
    D = pd.read_pickle(D13 / "cands.pkl")
    out = {}
    for p in selection():
        mid, corpus, stem = p["id"], p["corpus"], p["stem"]
        gt = json.loads((ART / "ground_truth" / f"{mid}.json").read_text())
        d = D[gt["score_id"]]
        assert np.allclose(sorted(d["ends"]), gt["ends"]) and np.allclose(
            sorted(d["starts"]), gt["starts"]), mid
        out[mid] = {"corpus": corpus, "stem": stem,
                    "bars": pd.read_csv(ART / f"bars_{mid}.csv", dtype={"written": str}),
                    "gt": gt, "d": d, "pointers": S.pointer_map(mid)}
    return out


def detector(corpus: str, stem: str, tempo_word: bool = False
             ) -> tuple[list[float], list[float]]:
    from pianolens.features.cadence import cadence_phrase_ends

    res = cadence_phrase_ends(dcml.load_score(corpus, stem, tempo_word=tempo_word))
    return [float(x) for x in res.end_beats], [float(x) for x in res.starts]


def prev_onset(onsets: np.ndarray, beats) -> list[float]:
    out = []
    for b in beats:
        i = int(np.searchsorted(onsets, b - 1e-6)) - 1
        if i >= 0:
            out.append(float(onsets[i]))
    return out


def comparator_predictions(mv: dict) -> dict[str, tuple[list | None, list | None]]:
    """As D-13's ``scripts/check_dcml_romantic.py`` (detector on the tempo_word=False score)."""
    d = mv["d"]
    ob = np.asarray(d["onset_beats"], float)
    db = np.asarray(d["downbeats"], float)
    return {
        "cadence": detector(mv["corpus"], mv["stem"]),
        "proxy_last_onset": (prev_onset(ob, d["proxy"][1:]) + [float(ob[-1])], None),
        "proxy": (None, list(d["proxy"])),
        "grid4": (db[3::4].tolist(), db[::4].tolist()),
        "oracle_dcml_ends": (list(mv["gt"]["ends"]), list(mv["gt"]["starts"])),
    }


# --------------------------------------------------------------------------- extra metrics


def to_quarters(mv: dict, beats) -> list[float]:
    """Beats (unit = each bar's time-signature denominator) -> quarter notes from the start,
    bar by bar, so that +-1 quarter is right in movements that change meter."""
    bars = mv["bars"]
    starts = bars["start"].to_numpy(float)
    den = bars["ts"].astype(str).str.split("/").str[1].astype(int).to_numpy()
    q0 = np.concatenate([[0.0], np.cumsum((bars["end"] - bars["start"]).to_numpy() * 4 / den)])
    out = []
    for x in beats:
        i = max(int(np.searchsorted(starts, x + 1e-9, "right")) - 1, 0)
        out.append(float(q0[i] + (x - starts[i]) * 4 / den[i]))
    return out


def printed_only(beats: list[float], mv: dict) -> list[float]:
    """Drop beats that fall in a pointer bar (each repeated passage counted once)."""
    bars = mv["bars"].set_index("bar")
    spans = [(bars.loc[b, "start"], bars.loc[b, "end"]) for b in mv["pointers"]]
    return [x for x in beats if not any(a - 1e-6 <= x < e - 1e-6 for a, e in spans)]


def cadenced_ends(mv: dict) -> tuple[list[float], list[float]]:
    """DCML phrase ends with / without a DCML cadence label at the same beat."""
    cad = {round(float(c["beat"]), 6) for c in mv["gt"]["cadences"]}
    ends = mv["gt"]["ends"]
    return ([x for x in ends if round(x, 6) in cad], [x for x in ends if round(x, 6) not in cad])


def extra_rows(mid: str, mv: dict, ends: list[float], method: str) -> list[dict]:
    """Sensitivities of the primary (exact onset, +-1 quarter note, each repeat once), the
    cadenced / uncadenced recall split and the granularity numbers."""
    gt = mv["gt"]["ends"]
    base = {"id": mid, "movement": mv["stem"], "method": method}
    rows = [
        {**base, "target": "end", "tol": "0beat", **S.boundary_prf(ends, gt, 1e-4, -np.inf)},
        {**base, "target": "end", "tol": "1quarter",
         **S.boundary_prf(to_quarters(mv, ends), to_quarters(mv, gt), 1.0, -np.inf)},
        {**base, "target": "end_once", "tol": "1beat",
         **S.boundary_prf(printed_only(ends, mv), printed_only(gt, mv), 1.0, -np.inf)},
    ]
    matched = {round(t, 6) for _, t in S.match_pairs(ends, gt, 1.0, -np.inf)}
    for name, xs in zip(("end_cadenced", "end_uncadenced"), cadenced_ends(mv), strict=True):
        rows.append({**base, "target": name, "tol": "1beat", "n_true": len(xs),
                     "tp": sum(round(x, 6) in matched for x in xs), "n_pred": len(ends)})
    return rows


# --------------------------------------------------------------------------- comparators


def run_comparators(out: Path = ART) -> pd.DataFrame:
    M = movement_inputs()
    rows = []
    for mid, mv in M.items():
        for m, (en, stt) in comparator_predictions(mv).items():
            rows += S.score_movement(mid, mv, en, stt, None, m)
            if en is not None and m in ("cadence", "grid4", "proxy_last_onset",
                                        "oracle_dcml_ends"):
                rows += extra_rows(mid, mv, en, m)
    B = pd.DataFrame(rows)
    B.to_csv(out / "comparators.csv", index=False)
    txt = S.summarise(B[~B.target.str.startswith("end_")])
    (out / "comparators_summary.txt").write_text(txt + "\n")
    print(txt)
    return B


# --------------------------------------------------------------------------- LLM runs


def score_events(M: dict[str, dict], ann_by_id: dict[str, dict], run: str,
                 variants=VARIANTS) -> tuple[pd.DataFrame, dict]:
    rows, info = [], {}
    for mid, mv in M.items():
        ann = ann_by_id.get(mid)
        if ann is None:
            info[mid] = {"missing": True}
            continue
        assert ann.get("movement") == mid, (mid, ann.get("movement"))
        for vname, kw in variants.items():
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
                rows += extra_rows(mid, mv, e["beat"].tolist(), vname)
            info[f"{mid} {vname}"] = stats
        info[f"{mid} recognised_piece"] = ann.get("recognised_piece")
    B = pd.DataFrame(rows)
    B["run"] = run
    return B, info


def load_dir(folder: Path) -> dict[str, dict]:
    return {f.stem: json.loads(f.read_text()) for f in sorted(folder.glob("R*.json"))}


def run_llm(folder: Path, run: str, out: Path = ART) -> pd.DataFrame:
    M = movement_inputs()
    B, info = score_events(M, load_dir(folder), run)
    B.to_csv(out / f"scores_{run}.csv", index=False)
    comp = pd.read_csv(ART / "comparators.csv")
    comp = comp[comp["method"].isin(["cadence", "proxy_last_onset", "proxy", "grid4"])]
    both = pd.concat([B.drop(columns=["run"]), comp], ignore_index=True)
    txt = S.summarise(both[~both.target.str.startswith("end_")])
    txt += f"\n\nrun {run}; mapping stats and recognised_piece:\n"
    txt += json.dumps(info, indent=1, ensure_ascii=False)
    (out / f"summary_{run}.txt").write_text(txt + "\n")
    print(txt)
    return B


# --------------------------------------------------------------------------- compare


def t_interval(x) -> tuple[float, float]:
    x = np.asarray(x, float)
    n = len(x)
    if n < 2:
        return (np.nan, np.nan)
    h = st.t.ppf(0.975, n - 1) * x.std(ddof=1) / np.sqrt(n)
    return float(x.mean() - h), float(x.mean() + h)


def one_sided_p(x, bar: float) -> float:
    """p of H1: mean > bar (t-test, n - 1 df)."""
    x = np.asarray(x, float)
    return float(st.ttest_1samp(x, bar, alternative="greater").pvalue)


def boot(x, rng) -> tuple[float, float, float]:
    x = np.asarray(x, float)
    idx = rng.integers(0, len(x), size=(N_BOOT, len(x)))
    bs = x[idx].mean(axis=1)
    return float(x.mean()), float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))


def _fmt(name: str, x, rng) -> str:
    m, lo, hi = boot(x, rng)
    tl, th = t_interval(x)
    return f"{name}: {m:+.3f}  bootstrap [{lo:+.3f}, {hi:+.3f}]  t [{tl:+.3f}, {th:+.3f}]"


def _f1(df: pd.DataFrame, method: str, target: str = "end", tol: str = "1beat") -> pd.Series:
    g = df[(df.method == method) & (df.target == target) & (df.tol == tol)]
    return g.set_index("movement")["F1"].astype(float)


def _col(df: pd.DataFrame, method: str, col: str, target: str = "end",
         tol: str = "1beat") -> pd.Series:
    g = df[(df.method == method) & (df.target == target) & (df.tol == tol)]
    return g.set_index("movement")[col].astype(float)


def compare(art: Path = ART, ann_root: Path = HERE) -> str:
    rng = np.random.default_rng(SEED)
    runs = {r: pd.read_csv(art / f"scores_{r}.csv") for r in RUNS
            if (art / f"scores_{r}.csv").exists()}
    if not runs:
        print("no run scores yet (scores_A.csv, scores_B.csv)")
        return ""
    comp = pd.read_csv(ART / "comparators.csv")
    picks = selection()
    stems = [p["stem"] for p in picks]
    rid = {p["stem"]: p["id"] for p in picks}
    corpus = {p["stem"]: p["corpus"] for p in picks}
    tab = pd.DataFrame({r: _f1(v, "llm") for r, v in runs.items()}).reindex(stems)
    llm = tab.mean(axis=1, skipna=True)  # per movement: mean of the runs that exist
    det = _f1(comp, "cadence").reindex(stems)
    out = [f"R-08d comparison. Runs: {list(runs)}; movements: {len(stems)}"]
    missing = tab.isna().sum().sum()
    if missing:
        out.append(f"DISCLOSE: {int(missing)} run x movement cells missing; those movements use "
                   "the runs that exist.")
    t = tab.copy()
    t.insert(0, "corpus", [corpus[s] for s in stems])
    t.insert(0, "id", [rid[s] for s in stems])
    t["LLM_mean"] = llm
    if tab.shape[1] > 1:
        t["abs_A_B"] = tab.max(axis=1) - tab.min(axis=1)
    t["detector"] = det
    t["proxy_last_onset"] = _f1(comp, "proxy_last_onset").reindex(stems)
    t["grid4"] = _f1(comp, "grid4").reindex(stems)
    out.append("\nPer movement end F1 at +-1 beat\n" + t.round(3).to_string())
    prim = float(llm.mean())
    out.append("\n" + _fmt("PRIMARY mean LLM end F1 (mean of runs per movement)", llm, rng))
    out.append(_fmt("mean(LLM - detector), paired", llm - det, rng))
    tl, _ = t_interval(llm)
    dl, _ = t_interval(llm - det)
    out.append(f"\nGO RULE: primary {prim:.3f} >= {BAR} -> "
               + ("GO" if prim >= BAR else "NO-GO")
               + ("; the t-interval lies above 0.70" if tl > BAR else
                  "; the t-interval does not lie above 0.70 (not claimed)"))
    out.append("Beats the detector: " + ("shown" if dl > 0 and (llm - det).mean() > 0
                                         else "not shown") + " (t-interval decides)")
    # near-the-bar reporting (R-08c audit lesson); descriptive, does not change the verdict
    loo = {rid[s]: float(llm.drop(s).mean()) for s in stems}
    loo_d = {rid[s]: float((llm - det).drop(s).mean()) for s in stems}
    out.append("\nNear the bar (descriptive):")
    out.append("  leave-one-movement-out primary: " + ", ".join(
        f"without {k} {v:.3f}" for k, v in loo.items()) + f"; min {min(loo.values()):.3f}")
    out.append("  leave-one-movement-out paired LLM - detector: " + ", ".join(
        f"without {k} {v:+.3f}" for k, v in loo_d.items()))
    worst = tab.min(axis=1, skipna=True)
    out.append(f"  worst-run variant (lower run per movement): {worst.mean():.3f}"
               f" ({'>=' if worst.mean() >= BAR else '<'} {BAR})")
    out.append(f"  one-sided t-test primary > {BAR}: p = {one_sided_p(llm, BAR):.3f} (4 df)")
    # run-to-run
    if tab.shape[1] > 1:
        sd = tab.std(axis=1, ddof=1)
        out.append("\nRun-to-run: run-level means " + ", ".join(
            f"{k} {v:.3f}" for k, v in tab.mean().items())
            + f"; mean within-movement SD {sd.mean():.3f} (R-08c: 0.027; R-08b: 0.031); "
            f"max |A-B| {(tab.max(axis=1) - tab.min(axis=1)).max():.3f}")
        for r in tab.columns:
            out.append(_fmt(f"run {r} mean end F1", tab[r].dropna(), rng))
    # sensitivities
    out.append("\nSensitivities (mean over movements; LLM = mean of runs per movement)")
    for target, tol, label in (("end", "0beat", "exact onset"),
                               ("end", "1quarter", "+-1 quarter note"),
                               ("end_once", "1beat", "each repeated passage once"),
                               ("end", "1bar", "+-1 bar")):
        lv = pd.DataFrame({r: _f1(v, "llm", target, tol) for r, v in runs.items()}) \
            .reindex(stems).mean(axis=1)
        dv = _f1(comp, "cadence", target, tol).reindex(stems)
        out.append(f"  {label:28s} LLM {lv.mean():.3f}  detector {dv.mean():.3f}  "
                   f"paired {(lv - dv).mean():+.3f} t [{t_interval(lv - dv)[0]:+.3f}, "
                   f"{t_interval(lv - dv)[1]:+.3f}]")
    for r, v in runs.items():
        c50 = _f1(v, "llm_conf50").reindex(stems)
        out.append(f"  confidence >= 0.5 ({r}): {c50.mean():.3f}")
    # cadenced vs uncadenced DCML ends
    out.append("\nRecall of DCML phrase ends at +-1 beat, split by a DCML cadence label at the "
               "same beat (pooled tp/n)")

    def split_line(df, method):
        g = df[(df.method == method) & df.target.isin(["end_cadenced", "end_uncadenced"])]
        s = g.groupby("target")[["tp", "n_true"]].sum()
        return "  ".join(f"{k[4:]} {int(x.tp)}/{int(x.n_true)}" for k, x in s.iterrows())

    for r, v in runs.items():
        out.append(f"  {r:18s} {split_line(v, 'llm')}")
    out.append(f"  {'detector':18s} {split_line(comp, 'cadence')}")
    # granularity (label-exposure check)
    out.append("\nGranularity per movement and run (P, R at +-1 beat; predicted / DCML ends)")
    n_true = _col(comp, "oracle_dcml_ends", "n_true").reindex(stems)
    for r, v in runs.items():
        P, R = _col(v, "llm", "P").reindex(stems), _col(v, "llm", "R").reindex(stems)
        npred = _col(v, "llm", "n_pred").reindex(stems)
        out.append(f"  run {r}: " + "; ".join(
            f"{rid[s]} P {P[s]:.2f} R {R[s]:.2f} ratio {npred[s] / n_true[s]:.2f}"
            for s in stems))
    # cadence recall by type via phrase ends; types given at DCML PC positions
    out.append("\nRecall of DCML cadences by type at +-1 beat via phrase ends (pooled tp/n)")

    def recall_line(df, method):
        g = df[(df.method == method) & df.target.str.startswith("cad_")]
        s = g.groupby("target")[["tp", "n_true"]].sum()
        return "  ".join(f"{k[4:]} {int(x.tp)}/{int(x.n_true)}" for k, x in s.iterrows())

    for r, v in runs.items():
        out.append(f"  {r:18s} {recall_line(v, 'llm')}")
        out.append(f"  {r + '+cad_marks':18s} {recall_line(v, 'llm+cad_marks')}")
    out.append(f"  {'detector':18s} {recall_line(comp, 'cadence')}")
    out.append(f"  {'oracle_dcml_ends':18s} {recall_line(comp, 'oracle_dcml_ends')} "
               "(reference, not a ceiling)")
    for r, v in runs.items():
        tp = v[(v.method == "llm") & (v.target == "type_pair")]
        if len(tp):
            agree = (tp["dcml"] == tp["pred_type"]).mean()
            pc = tp[tp["dcml"] == "PC"]["pred_type"].value_counts().to_dict()
            out.append(f"  type agreement ({r}, ends matched to DCML cadences): {agree:.3f} "
                       f"(n {len(tp)}); types given at DCML PC: {pc}")
    # recognition: within movement only
    rec_f = ann_root / "recognition.json"
    recog = json.loads(rec_f.read_text()) if rec_f.exists() else {}
    out.append("\nRecognition (strings; classes from recognition.json; within-movement only)")
    rows = []
    for r in runs:
        for qf in sorted((ann_root / f"annotations_{r}").glob("R*.json")):
            a = json.loads(qf.read_text())
            stem = next(p["stem"] for p in picks if p["id"] == qf.stem)
            rows.append({"run": r, "id": qf.stem, "corpus": corpus[stem],
                         "class": recog.get(r, {}).get(qf.stem, "unclassified"),
                         "F1": round(float(tab.loc[stem, r]), 3),
                         "recognised_piece": a.get("recognised_piece")})
    Rt = pd.DataFrame(rows)
    if len(Rt):
        out.append(Rt.to_string(index=False))
        id_stem = {p["id"]: p["stem"] for p in picks}
        known = [id_stem[i] for i in
                 Rt[Rt["class"].isin(["correct", "composer"])]["id"].unique().tolist()]
        for i, g in Rt.groupby("id"):
            if g["class"].nunique() > 1:
                out.append(f"  within {i}: " + ", ".join(
                    f"{x.run} {x['class']} F1 {x.F1:.3f}" for _, x in g.iterrows()))
        if (Rt["class"] == "unclassified").any():
            out.append("RECOGNITION: UNDETERMINED (fill recognition.json)")
        else:
            out.append(f"RECOGNITION: {len(known)} of {len(stems)} movements recognised "
                       f"(correct or composer) in at least one run: "
                       f"{[rid[s] for s in known]}"
                       + (" -> verdict is 'on largely recognised pieces'"
                          if len(known) >= 3 else ""))
            if known:
                keep = [s for s in stems if s not in known]
                out.append(f"  sensitivity without them ({len(keep)} movements): LLM "
                           f"{llm[keep].mean():.3f}, detector {det[keep].mean():.3f}")
    out.append(f"\nDescriptive (no test across corpora): R-08c J. C. Bach {R08C}; R-08b Mozart "
               f"disguised {R08B_A}, undisguised {R08B_U}; this primary {prim:.3f}.")
    txt = "\n".join(out)
    (art / "r08d_summary.txt").write_text(txt + "\n")
    print(txt)
    return txt


# --------------------------------------------------------------------------- harness


def harness(scratch: Path | None = None) -> bool:
    M = movement_inputs()
    ref = pd.read_csv(D13 / "comparators.csv")
    ok, lines = True, []
    det_prop: list[float] = []
    for mid, mv in M.items():
        gt = mv["gt"]
        ends, starts = list(gt["ends"]), list(gt["starts"])
        # 1. true labels -> (bar, beat) events -> annotator path: F1 1.0
        ev = S.as_events(mv, ends, starts)
        df, _ = S.map_events(ev, mv, propagate=False)
        r = pd.DataFrame(S.score_movement(mid, mv, df.loc[df.type == "phrase_end", "beat"]
                                          .tolist(), df.loc[df.type == "phrase_start", "beat"]
                                          .tolist(), None, "oracle"))
        f_all = r[(r.tol == "1beat") & r.target.isin(["end", "start"])]["F1"].round(4).tolist()
        o_ok = all(np.isclose(f, 1.0) for f in f_all)
        ev_p = [e for e in ev if e["bar"] not in mv["pointers"]]
        df, _ = S.map_events(ev_p, mv, propagate=True)
        r = pd.DataFrame(S.score_movement(mid, mv, df.loc[df.type == "phrase_end", "beat"]
                                          .tolist(), df.loc[df.type == "phrase_start", "beat"]
                                          .tolist(), None, "oracle_printed"))
        f_pr = r[(r.tol == "1beat") & r.target.isin(["end", "start"])]["F1"].round(4).tolist()
        # 2. detector -> events -> annotator path (propagation off) == D-13 comparators.csv
        en, stt = detector(mv["corpus"], mv["stem"])
        df, _ = S.map_events(S.as_events(mv, en, stt), mv, propagate=False)
        pe = df.loc[df.type == "phrase_end", "beat"].tolist()
        ps = df.loc[df.type == "phrase_start", "beat"].tolist()
        same_beats = np.allclose(pe, sorted(en)) and np.allclose(ps, sorted(set(stt)))
        mine = pd.DataFrame(S.score_movement(mid, mv, pe, ps, None, "cadence_via_events"))
        rr = ref[(ref["corpus"] == mv["corpus"]) & (ref["movement"] == mv["stem"])
                 & (ref["method"] == "cadence")]
        n_cmp, n_bad = 0, 0
        for _, row in rr.iterrows():
            o = mine[(mine["target"] == row["target"]) & (mine["tol"] == row["tol"])]
            if o.empty:
                continue
            o = o.iloc[0]
            cols = ["tp", "n_pred", "n_true"] + ([] if row["target"].startswith("cad_")
                                                 else ["F1"])
            n_cmp += 1
            n_bad += not all(np.isclose(o[c], row[c], equal_nan=True) for c in cols)
        d_ok = same_beats and n_bad == 0 and n_cmp == len(rr) and n_cmp > 0
        df, _ = S.map_events(S.as_events(mv, en, stt), mv, propagate=True)
        f_det_prop = S.boundary_prf(df.loc[df.type == "phrase_end", "beat"].tolist(),
                                    gt["ends"], 1.0, -np.inf)["F1"]
        f_det = mine[(mine.target == "end") & (mine.tol == "1beat")]["F1"].iloc[0]
        det_prop.append(float(f_det_prop))
        # 3. detector identical with the tempo word (D-13's score); ground truth == D-13 cache
        #    (asserted in movement_inputs)
        en_t, st_t = detector(mv["corpus"], mv["stem"], tempo_word=True)
        tw_ok = np.allclose(en_t, en) and np.allclose(st_t, stt)
        good = o_ok and d_ok and tw_ok
        ok &= good
        lines.append(f"{mid}: oracle end/start F1 {f_all} -> "
                     f"{'OK' if o_ok else 'FAIL'}; printed bars + propagation {f_pr}; "
                     f"detector via events {n_cmp}/{len(rr)} D-13 rows compared, {n_bad} "
                     f"mismatches -> {'OK' if d_ok else 'FAIL'} (end F1 {f_det:.4f}; with "
                     f"propagation {f_det_prop:.4f}); detector same with tempo word -> "
                     f"{'OK' if tw_ok else 'FAIL'}")
    # 4. end-to-end dry run of --llm-dir and --compare in a scratch folder
    tmp_ctx = None
    if scratch is None:
        tmp_ctx = tempfile.TemporaryDirectory()
        scratch = Path(tmp_ctx.name)
    scratch.mkdir(parents=True, exist_ok=True)
    det_mean = float(np.mean(det_prop))
    for kind in ("oracle", "detector"):
        root = scratch / kind
        art = root / "artifacts"
        art.mkdir(parents=True, exist_ok=True)
        for run in RUNS:
            d = root / f"annotations_{run}"
            d.mkdir(exist_ok=True)
            for mid, mv in M.items():
                en, stt = ((mv["gt"]["ends"], mv["gt"]["starts"]) if kind == "oracle"
                           else detector(mv["corpus"], mv["stem"]))
                ann = {"movement": mid, "recognised_piece": None, "notes": "",
                       "events": S.as_events(mv, list(en), list(stt))}
                (d / f"{mid}.json").write_text(json.dumps(ann))
            run_llm(d, run, out=art)
        (root / "recognition.json").write_text(json.dumps(
            {r: {m: "none" for m in M} for r in RUNS}))
        txt = compare(art=art, ann_root=root)
        prim = float(txt.split("PRIMARY mean LLM end F1 (mean of runs per movement): ")[1]
                     .split()[0])
        want = 1.0 if kind == "oracle" else det_mean
        e_ok = np.isclose(prim, want, atol=5e-4)
        ok &= e_ok
        lines.append(f"dry run ({kind} as annotation, 2 runs): primary {prim:.4f} vs expected "
                     f"{want:.4f}" + (" (detector with propagation)" if kind == "detector"
                                      else "") + f" -> {'OK' if e_ok else 'FAIL'}")
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
        assert run in RUNS, "runs are named A and B"
        run_llm(Path(argv[argv.index("--llm-dir") + 1]), run)
    if "--compare" in argv:
        compare()
