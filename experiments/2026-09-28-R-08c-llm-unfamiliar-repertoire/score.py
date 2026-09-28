"""R-08c scoring. Reuses R-08a's scoring functions (``map_events``, ``score_movement``,
``summarise``, ``as_events``, ``pointer_map``, ``boundary_prf``) unchanged, loaded from R-08a's
``score.py`` with importlib. Only the movement inputs (J. C. Bach, D-12) and the aggregation over
two runs are new.

    uv run python .../score.py --comparators
    uv run python .../score.py --harness [--scratch DIR]
    uv run python .../score.py --llm-dir <dir with Q#.json> --run R1
    uv run python .../score.py --compare

See README "Metrics", "Harness checks" and "Go bar and falsification".
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

from pianolens.data import dcml_jc_bach as jc  # noqa: E402

ART = HERE / "artifacts"
BLIND = HERE / "blind_input"
D12 = ROOT / "data" / "interim" / "dcml_jc_bach"
S.BLIND = BLIND  # pointer_map parses the R-08c renderings
S.TYPES = tuple(jc.CADENCE_TYPES)  # adds PC to the per-type rows
SEED = 20260930
N_BOOT = 10_000
BAR = 0.70
VARIANTS = {"llm": {}, "llm_unsnapped": {"snap": False}, "llm_conf50": {"min_conf": 0.5}}
# R-08b results (experiments/2026-09-28-R-08b-llm-memorisation-control/artifacts/r08b_summary.txt)
R08B_A, R08B_U = 0.802, 0.789


# --------------------------------------------------------------------------- inputs


def selection() -> list[dict]:
    return json.loads((ART / "selection.json").read_text())["picks"]


def movement_inputs() -> dict[str, dict]:
    """Per Q id: stem, bar table, ground truth, D-12 cached arrays, pointer map."""
    D = pd.read_pickle(D12 / "cands.pkl")
    out = {}
    for p in selection():
        mid, stem = p["id"], p["stem"]
        gt = json.loads((ART / "ground_truth" / f"{mid}.json").read_text())
        d = D[stem]
        assert np.allclose(sorted(d["ends"]), gt["ends"]) and np.allclose(
            sorted(d["starts"]), gt["starts"]), mid
        out[mid] = {"stem": stem, "bars": pd.read_csv(ART / f"bars_{mid}.csv",
                                                      dtype={"written": str}),
                    "gt": gt, "d": d, "pointers": S.pointer_map(mid)}
    return out


def detector(stem: str, tempo_word: bool = False) -> tuple[list[float], list[float]]:
    from pianolens.features.cadence import cadence_phrase_ends

    res = cadence_phrase_ends(jc.load_score(stem, tempo_word=tempo_word))
    return [float(x) for x in res.end_beats], [float(x) for x in res.starts]


def prev_onset(onsets: np.ndarray, beats) -> list[float]:
    out = []
    for b in beats:
        i = int(np.searchsorted(onsets, b - 1e-6)) - 1
        if i >= 0:
            out.append(float(onsets[i]))
    return out


def comparator_predictions(mv: dict) -> dict[str, tuple[list | None, list | None]]:
    """As D-12's ``scripts/check_dcml_jc_bach.py`` (detector on the tempo_word=False score)."""
    d = mv["d"]
    ob = np.asarray(d["onset_beats"], float)
    db = np.asarray(d["downbeats"], float)
    return {
        "cadence": detector(mv["stem"]),
        "proxy_last_onset": (prev_onset(ob, d["proxy"][1:]) + [float(ob[-1])], None),
        "proxy": (None, list(d["proxy"])),
        "grid4": (db[3::4].tolist(), db[::4].tolist()),
        "oracle_dcml_ends": (list(mv["gt"]["ends"]), list(mv["gt"]["starts"])),
    }


# --------------------------------------------------------------------------- extra metrics


def quarter_tol(mv: dict) -> float:
    """One quarter note in beats (beat = the time signature's denominator)."""
    den = int(str(mv["bars"]["ts"].iloc[0]).split("/")[1])
    return den / 4.0


def printed_only(beats: list[float], mv: dict) -> list[float]:
    """Drop beats that fall in a pointer bar (each repeated passage counted once)."""
    bars = mv["bars"].set_index("bar")
    spans = [(bars.loc[b, "start"], bars.loc[b, "end"]) for b in mv["pointers"]]
    return [x for x in beats if not any(a - 1e-6 <= x < e - 1e-6 for a, e in spans)]


def extra_rows(mid: str, mv: dict, ends: list[float], method: str) -> list[dict]:
    """Sensitivities of the primary: exact onset, +-1 quarter note, each repeat once."""
    gt = mv["gt"]["ends"]
    base = {"id": mid, "movement": mv["stem"], "method": method}
    return [
        {**base, "target": "end", "tol": "0beat", **S.boundary_prf(ends, gt, 1e-4, -np.inf)},
        {**base, "target": "end", "tol": "1quarter",
         **S.boundary_prf(ends, gt, quarter_tol(mv), -np.inf)},
        {**base, "target": "end_once", "tol": "1beat",
         **S.boundary_prf(printed_only(ends, mv), printed_only(gt, mv), 1.0, -np.inf)},
    ]


# --------------------------------------------------------------------------- comparators


def run_comparators(out: Path = ART) -> pd.DataFrame:
    M = movement_inputs()
    rows = []
    for mid, mv in M.items():
        for m, (en, stt) in comparator_predictions(mv).items():
            rows += S.score_movement(mid, mv, en, stt, None, m)
            if en is not None and m in ("cadence", "grid4", "proxy_last_onset"):
                rows += extra_rows(mid, mv, en, m)
    B = pd.DataFrame(rows)
    B.to_csv(out / "comparators.csv", index=False)
    txt = S.summarise(B)
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
    return {f.stem: json.loads(f.read_text()) for f in sorted(folder.glob("Q*.json"))}


def run_llm(folder: Path, run: str, out: Path = ART) -> pd.DataFrame:
    M = movement_inputs()
    B, info = score_events(M, load_dir(folder), run)
    B.to_csv(out / f"scores_{run}.csv", index=False)
    comp = pd.read_csv(ART / "comparators.csv")
    comp = comp[comp["method"].isin(["cadence", "proxy_last_onset", "proxy", "grid4"])]
    txt = S.summarise(pd.concat([B.drop(columns=["run"]), comp], ignore_index=True))
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
    return g.set_index("movement")["F1"]


def compare(art: Path = ART, ann_root: Path = HERE) -> str:
    rng = np.random.default_rng(SEED)
    runs = {f.stem[len("scores_"):]: pd.read_csv(f) for f in sorted(art.glob("scores_R*.csv"))}
    if not runs:
        print("no run scores yet (scores_R1.csv, scores_R2.csv)")
        return ""
    comp = pd.read_csv(ART / "comparators.csv")
    stems = [p["stem"] for p in selection()]
    qid = {p["stem"]: p["id"] for p in selection()}
    tab = pd.DataFrame({r: _f1(v, "llm") for r, v in runs.items()}).reindex(stems)
    llm = tab.mean(axis=1, skipna=True)  # per movement: mean of the runs that exist
    det = _f1(comp, "cadence").reindex(stems)
    out = [f"R-08c comparison. Runs: {list(runs)}; movements: {len(stems)}"]
    missing = tab.isna().sum().sum()
    if missing:
        out.append(f"DISCLOSE: {int(missing)} run x movement cells missing; those movements use "
                   "the runs that exist.")
    t = tab.copy()
    t.insert(0, "id", [qid[s] for s in stems])
    t["LLM_mean"] = llm
    if tab.shape[1] > 1:
        t["abs_R1_R2"] = (tab.max(axis=1) - tab.min(axis=1))
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
    # run-to-run
    if tab.shape[1] > 1:
        sd = tab.std(axis=1, ddof=1)
        out.append("\nRun-to-run: run-level means " + ", ".join(
            f"{k} {v:.3f}" for k, v in tab.mean().items())
            + f"; mean within-movement SD {sd.mean():.3f} (R-08b: 0.031); max |R1-R2| "
            f"{(tab.max(axis=1) - tab.min(axis=1)).max():.3f}")
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
    # cadence recall by type via phrase ends
    out.append("\nRecall of DCML cadences by type at +-1 beat via phrase ends (pooled tp/n)")

    def recall_line(df, method):
        g = df[(df.method == method) & df.target.str.startswith("cad_")]
        s = g.groupby("target")[["tp", "n_true"]].sum()
        return "  ".join(f"{k[4:]} {int(r.tp)}/{int(r.n_true)}" for k, r in s.iterrows())

    for r, v in runs.items():
        out.append(f"  {r:18s} {recall_line(v, 'llm')}")
        out.append(f"  {r + '+cad_marks':18s} {recall_line(v, 'llm+cad_marks')}")
    out.append(f"  {'detector':18s} {recall_line(comp, 'cadence')}")
    out.append(f"  {'oracle_dcml_ends':18s} {recall_line(comp, 'oracle_dcml_ends')} "
               "(reference, not a ceiling)")
    # recognition: within movement only
    rec_f = ann_root / "recognition.json"
    recog = json.loads(rec_f.read_text()) if rec_f.exists() else {}
    out.append("\nRecognition (strings; classes from recognition.json; within-movement only)")
    rows = []
    for r in runs:
        for qf in sorted((ann_root / f"annotations_{r}").glob("Q*.json")):
            a = json.loads(qf.read_text())
            stem = next(p["stem"] for p in selection() if p["id"] == qf.stem)
            rows.append({"run": r, "id": qf.stem, "movement": stem,
                         "class": recog.get(r, {}).get(qf.stem, "unclassified"),
                         "F1": round(float(tab.loc[stem, r]), 3),
                         "recognised_piece": a.get("recognised_piece")})
    R = pd.DataFrame(rows)
    if len(R):
        out.append(R.to_string(index=False))
        known = R[R["class"].isin(["correct", "composer"])]["movement"].unique().tolist()
        differ = [m for m, g in R.groupby("movement") if g["class"].nunique() > 1]
        for m in differ:
            g = R[R.movement == m]
            out.append(f"  within {qid[m]}: " + ", ".join(
                f"{x.run} {x['class']} F1 {x.F1:.3f}" for _, x in g.iterrows()))
        if (R["class"] == "unclassified").any():
            out.append("PREMISE: UNDETERMINED (fill recognition.json)")
        else:
            out.append(f"PREMISE: {len(known)} of {len(stems)} movements recognised "
                       f"(correct or composer) in at least one run: {known}"
                       + (" -> UNFAMILIARITY NOT ACHIEVED" if len(known) >= 3 else ""))
            if known:
                keep = [s for s in stems if s not in known]
                out.append(f"  sensitivity without them ({len(keep)} movements): LLM "
                           f"{llm[keep].mean():.3f}, detector {det[keep].mean():.3f}")
    out.append(f"\nDescriptive (no test across corpora): R-08b Mozart disguised {R08B_A}, "
               f"undisguised {R08B_U}; this primary {prim:.3f}.")
    txt = "\n".join(out)
    (art / "r08c_summary.txt").write_text(txt + "\n")
    print(txt)
    return txt


# --------------------------------------------------------------------------- harness


def harness(scratch: Path | None = None) -> bool:
    M = movement_inputs()
    ref = pd.read_csv(D12 / "comparators.csv")
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
        # 2. detector -> events -> annotator path (propagation off) == D-12 comparators.csv
        en, stt = detector(mv["stem"])
        df, _ = S.map_events(S.as_events(mv, en, stt), mv, propagate=False)
        pe = df.loc[df.type == "phrase_end", "beat"].tolist()
        ps = df.loc[df.type == "phrase_start", "beat"].tolist()
        same_beats = np.allclose(pe, sorted(en)) and np.allclose(ps, sorted(set(stt)))
        mine = pd.DataFrame(S.score_movement(mid, mv, pe, ps, None, "cadence_via_events"))
        rr = ref[(ref["movement"] == mv["stem"]) & (ref["method"] == "cadence")]
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
        # 3. detector identical with the tempo word; ground truth == D-12 cache (asserted in
        #    movement_inputs)
        en_t, st_t = detector(mv["stem"], tempo_word=True)
        tw_ok = np.allclose(en_t, en) and np.allclose(st_t, stt)
        good = o_ok and d_ok and tw_ok
        ok &= good
        lines.append(f"{mid} ({mv['stem']}): oracle end/start F1 {f_all} -> "
                     f"{'OK' if o_ok else 'FAIL'}; printed bars + propagation {f_pr}; "
                     f"detector via events {n_cmp}/{len(rr)} D-12 rows compared, {n_bad} "
                     f"mismatches -> {'OK' if d_ok else 'FAIL'} (end F1 {f_det:.4f}; with "
                     f"propagation {f_det_prop:.4f}); detector same with tempo word -> "
                     f"{'OK' if tw_ok else 'FAIL'}")
    # 4. end-to-end dry run of --llm-dir and --compare in a scratch folder
    tmp_ctx = None
    if scratch is None:
        tmp_ctx = tempfile.TemporaryDirectory()
        scratch = Path(tmp_ctx.name)
    scratch.mkdir(parents=True, exist_ok=True)
    # the annotation path propagates printed-bar events into pointer bars, so the detector
    # written as an annotation scores its propagated F1 (equal to its own F1 only where it makes
    # the same calls in both passes of every repeat)
    det_mean = float(np.mean(det_prop))
    for kind in ("oracle", "detector"):
        root = scratch / kind
        art = root / "artifacts"
        art.mkdir(parents=True, exist_ok=True)
        for run in ("R1", "R2"):
            d = root / f"annotations_{run}"
            d.mkdir(exist_ok=True)
            for mid, mv in M.items():
                en, stt = ((mv["gt"]["ends"], mv["gt"]["starts"]) if kind == "oracle"
                           else detector(mv["stem"]))
                ann = {"movement": mid, "recognised_piece": None, "notes": "",
                       "events": S.as_events(mv, list(en), list(stt))}
                (d / f"{mid}.json").write_text(json.dumps(ann))
            run_llm(d, run, out=art)
        (root / "recognition.json").write_text(json.dumps(
            {r: {m: "none" for m in M} for r in ("R1", "R2")}))
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
        assert run.startswith("R"), "runs are named R1, R2"
        run_llm(Path(argv[argv.index("--llm-dir") + 1]), run)
    if "--compare" in argv:
        compare()
