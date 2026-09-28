"""R-08b scoring. Reuses R-08a's scoring functions (``map_events``, ``score_movement``,
``boot_mean``, ``summarise``) unchanged; only the movement inputs differ by condition.

    uv run python .../score.py --harness
    uv run python .../score.py --llm-dir <dir with D#.json> --condition A [--run A]
    uv run python .../score.py --llm-dir <dir with M#.json> --condition B --run B1
    uv run python .../score.py --compare

Condition A: the disguised bar table (``artifacts/bars_D#.csv``) is R-08a's with bar numbers
shifted by ``c``; onset beats are unchanged, so a disguised (bar, beat) maps to the same
performed-score beat, and the same DCML ground truth applies. Pointer bars are parsed from the
disguised rendering. Condition B: R-08a's inputs, unchanged.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats as st

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
R08A = ROOT / "experiments" / "2026-09-28-R-08a-llm-phrase-pilot"
sys.path.insert(0, str(R08A))
sys.path.insert(0, str(HERE))

import disguise as DG  # noqa: E402

_spec = importlib.util.spec_from_file_location("r08a_score", R08A / "score.py")
S = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(S)  # R-08a scoring module (reads R-08a artifacts, writes nothing here)

ART = HERE / "artifacts"
SEED = 20260929
N_BOOT = 10_000
BAR = 0.70
MARGIN = 0.10
VARIANTS = {"llm": {}, "llm_conf50": {"min_conf": 0.5}}


# --------------------------------------------------------------------------- inputs


def inputs_B() -> dict[str, dict]:
    return S.movement_inputs()  # keyed by M id


def inputs_A() -> dict[str, dict]:
    """Keyed by D id; stem, disguised bar table, R-08a ground truth, F-05c cache, pointers."""
    base = S.movement_inputs()
    out = {}
    for p in DG.params():
        mv = dict(base[p["m_id"]])
        mv["bars"] = pd.read_csv(ART / f"bars_{p['d_id']}.csv", dtype={"written": str})
        mv["pointers"] = DG.parse_pointers((DG.BLIND / f"{p['d_id']}.txt").read_text())
        mv["param"] = p
        out[p["d_id"]] = mv
    return out


# --------------------------------------------------------------------------- scoring


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
            r = S.score_movement(mid, mv, e["beat"].tolist(), s["beat"].tolist(), types, vname,
                                 marks if vname == "llm" else None)
            # exact-onset end F1 (secondary)
            if vname == "llm":
                r.append({"id": mid, "movement": mv["stem"], "method": vname, "target": "end",
                          "tol": "0beat",
                          **S.boundary_prf(e["beat"].tolist(), mv["gt"]["ends"], 1e-4,
                                           -np.inf)})
            rows += r
            info[f"{mid} {vname}"] = stats
        info[f"{mid} recognised_piece"] = ann.get("recognised_piece")
    B = pd.DataFrame(rows)
    B["run"] = run
    return B, info


def load_dir(folder: Path) -> dict[str, dict]:
    return {f.stem: json.loads(f.read_text()) for f in sorted(folder.glob("*.json"))}


def run_llm(folder: Path, condition: str, run: str) -> None:
    M = inputs_A() if condition == "A" else inputs_B()
    B, info = score_events(M, load_dir(folder), run)
    B["condition"] = condition
    B.to_csv(ART / f"scores_{run}.csv", index=False)
    comp = pd.read_csv(S.ART / "comparators.csv")
    comp = comp[comp["method"].isin(["cadence", "proxy_last_onset", "proxy", "grid4"])]
    txt = S.summarise(pd.concat([B.drop(columns=["run", "condition"]), comp], ignore_index=True))
    txt += f"\n\nrun {run} (condition {condition}); mapping stats and recognised_piece:\n"
    txt += json.dumps(info, indent=1, ensure_ascii=False)
    (ART / f"summary_{run}.txt").write_text(txt + "\n")
    print(txt)


# --------------------------------------------------------------------------- harness


def harness() -> bool:
    A = inputs_A()
    ok = True
    lines = []
    ref = pd.read_csv(S.F05C / "boundaries.csv")
    r08a = pd.read_csv(S.ART / "llm_scores.csv")
    r08a_ann = load_dir(R08A / "annotations")
    for did, mv in A.items():
        p = mv["param"]
        gt = mv["gt"]
        ends, starts = list(gt["ends"]), list(gt["starts"])
        # 1. oracle through the disguised bar table, all bars, propagation off
        ev = S.as_events(mv, ends, starts)
        assert all(e["bar"] > p["bar_offset"] for e in ev)
        df, _ = S.map_events(ev, mv, propagate=False)
        rows = pd.DataFrame(S.score_movement(did, mv, df.loc[df.type == "phrase_end", "beat"]
                                             .tolist(), df.loc[df.type == "phrase_start", "beat"]
                                             .tolist(), None, "oracle"))
        f_all = rows[(rows.tol == "1beat") & rows.target.isin(["end", "start"])]["F1"].tolist()
        # 1b. oracle written only in printed bars, then propagated
        ev_p = [e for e in ev if e["bar"] not in mv["pointers"]]
        df, _ = S.map_events(ev_p, mv, propagate=True)
        rows = pd.DataFrame(S.score_movement(did, mv, df.loc[df.type == "phrase_end", "beat"]
                                             .tolist(), df.loc[df.type == "phrase_start", "beat"]
                                             .tolist(), None, "oracle_printed"))
        f_pr = rows[(rows.tol == "1beat") & rows.target.isin(["end", "start"])]["F1"].tolist()
        o_ok = all(np.isclose(f, 1.0) for f in f_all + f_pr)
        # 2. detector through the disguised path vs F-05c
        en, stt = S.comparator_predictions(mv)["cadence"]
        df, _ = S.map_events(S.as_events(mv, en, stt), mv, propagate=False)
        pe = df.loc[df.type == "phrase_end", "beat"].tolist()
        ps = df.loc[df.type == "phrase_start", "beat"].tolist()
        mine = pd.DataFrame(S.score_movement(did, mv, pe, ps, None, "cadence_via_events"))
        r = ref[(ref["movement"] == mv["stem"]) & (ref["method"] == "cadence")]
        n_cmp, n_bad = 0, 0
        for _, row in r.iterrows():
            o = mine[(mine["target"] == row["target"]) & (mine["tol"] == row["tol"])]
            if o.empty:
                continue
            o = o.iloc[0]
            cols = ["tp", "n_pred", "n_true"] + ([] if row["target"].startswith("cad_")
                                                 else ["F1"])
            n_cmp += 1
            n_bad += not all(np.isclose(o[c], row[c], equal_nan=True) for c in cols)
        d_ok = n_bad == 0 and n_cmp > 0
        # 3. replay R-08a's annotation with bars shifted and the id renamed
        a = json.loads(json.dumps(r08a_ann[p["m_id"]]))
        a["movement"] = did
        for e in a["events"]:
            e["bar"] = int(e["bar"]) + p["bar_offset"]
        B, _ = score_events({did: mv}, {did: a}, "replay", {"llm": {}})
        got = B[(B.target == "end") & (B.tol == "1beat")].iloc[0]
        want = r08a[(r08a.movement == mv["stem"]) & (r08a.method == "llm")
                    & (r08a.target == "end") & (r08a.tol == "1beat")].iloc[0]
        rp_ok = all(np.isclose(got[c], want[c]) for c in ("tp", "n_pred", "n_true", "F1"))
        # also every per-type cadence row
        for t in S.TYPES:
            g = B[(B.target == f"cad_{t}") & (B.method == "llm")].iloc[0]
            w = r08a[(r08a.movement == mv["stem"]) & (r08a.method == "llm")
                     & (r08a.target == f"cad_{t}")].iloc[0]
            rp_ok &= bool(g["tp"] == w["tp"] and g["n_true"] == w["n_true"])
        good = o_ok and d_ok and rp_ok
        ok &= good
        lines.append(f"{did} ({mv['stem']}): oracle end/start F1 all bars {f_all}, printed+"
                     f"propagated {f_pr} -> {'OK' if o_ok else 'FAIL'}; detector {n_cmp} F-05c "
                     f"rows, {n_bad} mismatches -> {'OK' if d_ok else 'FAIL'}; R-08a replay end "
                     f"F1 {got['F1']:.4f} vs {want['F1']:.4f} (tp/pred/true {int(got['tp'])}/"
                     f"{int(got['n_pred'])}/{int(got['n_true'])}) -> {'OK' if rp_ok else 'FAIL'}")
    # 4. condition B path reproduces R-08a
    Bm = inputs_B()
    B, _ = score_events(Bm, r08a_ann, "replay_B", {"llm": {}})
    got = B[(B.target == "end") & (B.tol == "1beat")].set_index("movement")["F1"]
    want = r08a[(r08a.method == "llm") & (r08a.target == "end")
                & (r08a.tol == "1beat")].set_index("movement")["F1"]
    b_ok = np.allclose(got.sort_index(), want.sort_index())
    ok &= b_ok
    lines.append(f"condition B path on R-08a annotations: mean end F1 {got.mean():.4f} vs R-08a "
                 f"{want.mean():.4f} -> {'OK' if b_ok else 'FAIL'}")
    txt = "\n".join(lines) + f"\nHARNESS {'PASSED' if ok else 'FAILED'}"
    ART.mkdir(exist_ok=True)
    (ART / "harness.txt").write_text(txt + "\n")
    print(txt)
    return ok


# --------------------------------------------------------------------------- compare


def t_interval(x: np.ndarray) -> tuple[float, float]:
    x = np.asarray(x, float)
    n = len(x)
    if n < 2:
        return (np.nan, np.nan)
    h = st.t.ppf(0.975, n - 1) * x.std(ddof=1) / np.sqrt(n)
    return float(x.mean() - h), float(x.mean() + h)


def boot(x: np.ndarray, rng) -> tuple[float, float, float]:
    x = np.asarray(x, float)
    idx = rng.integers(0, len(x), size=(N_BOOT, len(x)))
    bs = x[idx].mean(axis=1)
    return float(x.mean()), float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))


def _fmt(name: str, x: np.ndarray, rng) -> str:
    m, lo, hi = boot(x, rng)
    tl, th = t_interval(x)
    return f"{name}: {m:+.3f}  bootstrap [{lo:+.3f}, {hi:+.3f}]  t [{tl:+.3f}, {th:+.3f}]"


def compare() -> None:
    rng = np.random.default_rng(SEED)
    runs = {}
    r08a = pd.read_csv(S.ART / "llm_scores.csv")
    r08a["run"] = "R08a"
    runs["R08a"] = r08a[r08a["method"].isin(["llm", "llm_conf50"])]
    for f in sorted(ART.glob("scores_*.csv")):
        runs[f.stem[len("scores_"):]] = pd.read_csv(f)
    if "A" not in runs:
        print("no condition A scores yet (scores_A.csv)")
        return
    comp = pd.read_csv(S.ART / "comparators.csv")

    def end_f1(df, tol="1beat"):
        return df[(df.method == "llm") & (df.target == "end") & (df.tol == tol)].set_index(
            "movement")["F1"]

    A = end_f1(runs["A"])
    U_runs = {k: end_f1(v) for k, v in runs.items() if k == "R08a" or k.startswith("B")}
    Utab = pd.DataFrame(U_runs)
    U = Utab.mean(axis=1)
    det = comp[(comp.method == "cadence") & (comp.target == "end") & (comp.tol == "1beat")] \
        .set_index("movement")["F1"]
    mv = sorted(A.index)
    A, U, det, Utab = A[mv], U[mv], det[mv], Utab.loc[mv]
    out = [f"R-08b comparison. Undisguised runs used for U: {list(U_runs)}"]
    a_mean, d_mean = A.mean(), (A - U).mean()
    pass_a, pass_d = a_mean >= BAR, d_mean >= -MARGIN
    out.append("\nPer movement end F1 at +-1 beat")
    tab = Utab.copy()
    tab["U_mean"] = U
    tab["U_sd"] = Utab.std(axis=1, ddof=1) if Utab.shape[1] > 1 else np.nan
    tab["A"] = A
    tab["A-U"] = A - U
    tab["A_vs_U_range"] = ["inside" if Utab.loc[m].min() - 1e-9 <= A[m] <= Utab.loc[m].max()
                           + 1e-9 else ("above" if A[m] > Utab.loc[m].max() else "below")
                           for m in mv]
    tab["detector"] = det
    out.append(tab.round(3).to_string())
    out.append("\n" + _fmt("mean A (disguised)", A.to_numpy(), rng))
    out.append(_fmt("mean U (undisguised, mean of runs)", U.to_numpy(), rng))
    out.append(_fmt("mean(A - U), paired", (A - U).to_numpy(), rng))
    out.append(_fmt("mean(A - R08a), paired (sensitivity)", (A - Utab["R08a"]).to_numpy(), rng))
    out.append(_fmt("mean(A - detector), paired", (A - det).to_numpy(), rng))
    tl, _ = t_interval((A - U).to_numpy())
    _, blo, _ = boot((A - U).to_numpy(), np.random.default_rng(SEED))
    out.append(f"\nPASS RULE: mean A {a_mean:.3f} >= {BAR} -> {pass_a}; mean(A-U) {d_mean:+.3f} "
               f">= -{MARGIN} -> {pass_d}  => {'PASS' if pass_a and pass_d else 'FAIL'}")
    out.append(f"non-inferiority at {MARGIN}: "
               + ("shown (t-interval lower end > -0.10)" if tl > -MARGIN else "point pass only"
                  if pass_d else "not shown"))
    out.append(f"margin sensitivity: holds for margins >= {max(-d_mean, 0.0) + 0.0:.3f} "
               f"(point), >= {max(-blo, 0.0) + 0.0:.3f} (bootstrap lower), "
               f">= {max(-tl, 0.0) + 0.0:.3f} (t lower)")
    # variance
    if Utab.shape[1] > 1:
        out.append("\nRun-to-run variance (undisguised): run-level means "
                   + ", ".join(f"{k} {v:.3f}" for k, v in Utab.mean().items())
                   + f"; mean within-movement SD {Utab.std(axis=1, ddof=1).mean():.3f}; "
                   f"max within-movement range {(Utab.max(axis=1) - Utab.min(axis=1)).max():.3f}")
    # exact onset
    ex = {k: v[(v.method == "llm") & (v.target == "end") & (v.tol == "0beat")]
          .set_index("movement")["F1"] for k, v in runs.items() if k != "R08a"}
    if ex:
        out.append("Exact-onset end F1 (mean): " + ", ".join(f"{k} {v.mean():.3f}"
                                                              for k, v in ex.items()))
    # HC recall
    hc = []
    for k, v in runs.items():
        g = v[(v.method == "llm") & (v.target == "cad_HC")]
        hc.append(f"{k} {int(g.tp.sum())}/{int(g.n_true.sum())}")
    out.append("HC recall via phrase ends, pooled: " + ", ".join(hc) + "; detector 18/62")
    # recognition
    rec_f = HERE / "recognition.json"
    recog = json.loads(rec_f.read_text()) if rec_f.exists() else {}
    out.append("\nRecognition (recognised_piece strings; classes from recognition.json)")
    stems = {p["d_id"]: p["stem"] for p in DG.params()}
    mids = {p["m_id"]: p["stem"] for p in DG.params()}
    rows = []
    for run in runs:
        folder = {"R08a": R08A / "annotations"}.get(run, HERE / f"annotations_{run}")
        for f in sorted(folder.glob("*.json")) if folder.exists() else []:
            a = json.loads(f.read_text())
            stem = stems.get(f.stem) or mids.get(f.stem)
            cls = recog.get(run, {}).get(f.stem, "unclassified")
            f1 = end_f1(runs[run]).get(stem, np.nan)
            rows.append({"run": run, "id": f.stem, "movement": stem, "class": cls,
                         "F1": round(float(f1), 3), "recognised_piece": a.get("recognised_piece")})
    R = pd.DataFrame(rows)
    if len(R):
        out.append(R.to_string(index=False))
        out.append("\nMean end F1 by run and class:\n"
                   + R.groupby(["run", "class"])["F1"].agg(["mean", "count"]).round(3).to_string())
        a_cls = R[R.run == "A"]["class"]
        n_corr = int((a_cls == "correct").sum())
        done = not (a_cls == "unclassified").any()
        eff = ("effective" if n_corr <= 1 else "partly effective" if n_corr == 2
               else "INEFFECTIVE (a pass is inconclusive on memorisation)")
        out.append(f"\nDisguise: {n_corr} of {len(a_cls)} condition A movements correctly "
                   f"recognised -> " + (eff if done else "UNDETERMINED (fill recognition.json)"))
        nr = R[(R.run == "A") & (R["class"] != "correct")]["movement"].tolist()
        if nr and done:
            out.append(f"Not-correctly-recognised subset ({len(nr)}): mean A {A[nr].mean():.3f}, "
                       f"mean U {U[nr].mean():.3f}")
    txt = "\n".join(out)
    (ART / "r08b_summary.txt").write_text(txt + "\n")
    print(txt)


if __name__ == "__main__":
    argv = sys.argv
    if "--harness" in argv:
        sys.exit(0 if harness() else 1)
    if "--llm-dir" in argv:
        cond = argv[argv.index("--condition") + 1]
        assert cond in ("A", "B")
        run = argv[argv.index("--run") + 1] if "--run" in argv else cond
        assert cond == "A" or run.startswith("B"), "condition B runs are named B1, B2, ..."
        run_llm(Path(argv[argv.index("--llm-dir") + 1]), cond, run)
    if "--compare" in argv:
        compare()
