"""BL-23: tight ornament whitelist and same-pitch reassignment, validated.

Run::

    OMP_NUM_THREADS=1 uv run python scripts/eval_correctness_bl23.py --part all [--workers 12]

Pre-registration: ``docs/specs/correctness-validation.md``, section "Pre-registration BL-23"
(copy and sha256 in ``experiments/2026-09-29-BL-23-aligner-ornaments/artifacts/``).

Every performance is aligned once; the four labeller variants (``VARIANTS``) are applied to the
same alignment. Jobs:

* ``f02``: the F-02 set (``mistakes_v1``, 400 copies), per bar and per injected wrong pitch, both
  modes; bar tables for the calibration; the legacy-tolerated ornament notes of the clean copies.
* ``stress``: the BL-20 Part B stress copies (``eval_correctness_density.stress_copy``, same
  seeds), both modes, with the clean copy labelled by the same variant.
* ``asap`` / ``floor``: the F-08c expert sets (``calibrate_expert_check_f08c``), aligned mode.

``--part summary`` computes every pre-registered quantity from the cached rows. Outputs go to
``--out`` (default the experiment's ``artifacts/``, gitignored).
"""

from __future__ import annotations

import argparse
import json
import logging
import pickle
import sys
import time
import warnings
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import calibrate_expert_check_f08c as F  # noqa: E402
import eval_correctness_density as D  # noqa: E402

log = logging.getLogger("eval_correctness_bl23")

VARIANTS: dict[str, dict] = {
    "L": {"ornament_rule": "legacy", "reassign": False},
    "T": {"ornament_rule": "tight", "reassign": False},
    "R": {"ornament_rule": "legacy", "reassign": True},
    "TR": {"ornament_rule": "tight", "reassign": True},
}
MODES = ("aligned", "gt_alignment")
WINDOW = 0.1
SEED = 20260929
DEFAULT_OUT = Path("experiments/2026-09-29-BL-23-aligner-ornaments/artifacts")


# --------------------------------------------------------------------------- workers


def _init(root: str) -> None:
    D._init(root)
    F._quiet()


def _label_all(ap_by_mode: dict) -> dict[tuple[str, str], object]:
    from pianolens.features.correctness import correctness

    return {(m, v): correctness(a, wrong_pitch_window_sec=WINDOW, **kw)
            for m, a in ap_by_mode.items() for v, kw in VARIANTS.items()}  # fmt: skip


def _outcomes(res, lab, d_ioi: dict) -> list[dict]:
    s_bar = dict(zip(res.score_notes["score_id"], res.score_notes["measure_index"], strict=True))
    rows = D._wrong_outcomes(res, lab, d_ioi)
    for d in rows:
        d["bar"] = int(s_bar.get(d["score_id"], -1))
    return rows


def f02_one(key: str) -> dict:
    from pianolens.align import align_performance
    from pianolens.data import asap
    from pianolens.data.types import AlignedPerformance
    from pianolens.report.build import bar_error_table, bar_labels

    warnings.filterwarnings("ignore")
    perf, lab = D._STATE["get"](key)
    r = D._STATE["index"].loc[key]
    src = str(r["performance_id"])
    d_ioi, _, s2p = D._source_density(src)
    arow = D._STATE["asap"].loc[src]
    ap = align_performance(asap.load_asap_score(arow), perf)
    res = _label_all({"aligned": ap,
                      "gt_alignment": AlignedPerformance(perf, ap.score, lab.alignment)})
    base = {"key": key, "source": src, "piece_id": arow["piece_id"], "rate": float(r["rate"]),
            "composer": r["composer"]}  # fmt: skip
    bar_d = D._bar_density(res[("aligned", "L")], s2p, d_ioi)
    out: dict = {"bars": [], "wrong": [], "summ": [], "tables": [], "orn": []}
    labels = bar_labels(ap.score)
    for (mode, v), cr in res.items():
        g, p, n = D.bar_sets(cr, lab)
        tag = {**base, "mode": mode, "variant": v}
        b = cr.bars
        for mi, ne in zip(b["measure_index"].tolist(), b["n_errors"].tolist(), strict=True):
            out["bars"].append({**tag, "measure_index": int(mi), "ioi": bar_d.get(int(mi), np.nan),
                                "gt": mi in g, "pred": mi in p, "dont_care": mi in n,
                                "n_errors": int(ne)})  # fmt: skip
        out["wrong"] += [{**tag, **d} for d in _outcomes(cr, lab, d_ioi)]
        out["summ"].append({**tag, **{k: cr.summary[k] for k in (
            "n_pitch_dissolved", "n_ornament_matches", "n_reassigned", "n_ornament",
            "n_wrong_pitch", "n_missed", "n_extra", "match_ratio")}})
        if mode == "aligned":
            out["tables"].append({**tag, "suspect": bool(cr.summary["alignment_suspect"]),
                                  "table": bar_error_table(cr, labels)})  # fmt: skip
    if float(r["rate"]) == 0.0:  # N3: legacy-tolerated ornament notes, aligned mode
        ln = res[("aligned", "L")].notes
        tol = ln[(ln["label"] == "ornament")
                 | ((ln["label"] == "correct") & (ln["pitch"] != ln["score_pitch"]))]
        for v in VARIANTS:
            vn = res[("aligned", v)].notes.set_index("performance_id")
            for pid, bar, kind in zip(tol["performance_id"], tol["measure_index"],
                                      np.where(tol["label"] == "ornament", "extra_tolerated",
                                               "match_kept"), strict=True):  # fmt: skip
                out["orn"].append({**base, "variant": v, "performance_id": pid,
                                   "bar_legacy": int(bar), "kind": str(kind),
                                   "label": str(vn.loc[pid, "label"]),
                                   "bar": int(vn.loc[pid, "measure_index"])})  # fmt: skip
    return out


def stress_one(args: tuple[int, str]) -> dict:
    from pianolens.align import align_performance
    from pianolens.data import asap
    from pianolens.data.types import AlignedPerformance

    warnings.filterwarnings("ignore")
    i_src, src = args
    ckey = D._STATE["clean_key"][src]
    perf, lab = D._STATE["get"](ckey)
    r = D._STATE["index"].loc[ckey]
    arow = D._STATE["asap"].loc[src]
    score = asap.load_asap_score(arow)
    ap0 = align_performance(score, perf)
    clean = _label_all({"aligned": ap0,
                        "gt_alignment": AlignedPerformance(perf, ap0.score, lab.alignment)})
    ref = clean[("aligned", "L")].score_notes
    s_bar = dict(zip(ref["score_id"], ref["measure_index"], strict=True))
    d_ioi, _, _ = D._source_density(src)
    rows, summ = [], []
    for j, cell in enumerate(D.CELLS):
        rng = np.random.default_rng([D.SEED, i_src, j])
        sp, sl = D.stress_copy(perf, lab, cell, rng, s_bar)
        if sp is None:
            continue
        ap = align_performance(score, sp)
        res = _label_all({"aligned": ap,
                          "gt_alignment": AlignedPerformance(sp, ap.score, sl.alignment)})
        for (mode, v), cr in res.items():
            c0 = clean[(mode, v)].bars.set_index("measure_index")["n_errors"]
            c1 = cr.bars.set_index("measure_index")["n_errors"]
            for d in D._wrong_outcomes(cr, sl, d_ioi):
                b = s_bar.get(d["score_id"], -1)
                d.update(key=sp.performance_id, source=src, piece_id=arow["piece_id"],
                         composer=r["composer"], cell=cell, mode=mode, variant=v, bar=b,
                         bar_err_clean=int(c0.get(b, 0)), bar_err=int(c1.get(b, 0)))  # fmt: skip
                rows.append(d)
            summ.append({"key": sp.performance_id, "source": src, "cell": cell, "mode": mode,
                         "variant": v, "n_pitch_dissolved": cr.summary["n_pitch_dissolved"],
                         "n_reassigned": cr.summary["n_reassigned"]})  # fmt: skip
    return {"stress": rows, "stress_summ": summ}


def asap_one(perf_id: str) -> dict:
    from pianolens.align import align_performance
    from pianolens.data import asap
    from pianolens.report.build import bar_error_table, bar_labels

    F._quiet()
    row = D._STATE["asap"].loc[perf_id]
    ap = align_performance(asap.load_asap_score(row), asap.load_asap_performance(row))
    res = _label_all({"aligned": ap})
    labels = bar_labels(ap.score)
    return {"asap": [{"performance_id": perf_id, "piece_id": row["piece_id"],
                      "midi": row["midi_performance"], "variant": v,
                      "suspect": bool(cr.summary["alignment_suspect"]),
                      "table": bar_error_table(cr, labels)}
                     for (_, v), cr in res.items()]}  # fmt: skip


def floor_one(job: tuple) -> dict:
    import tempfile
    import zipfile

    from pianolens.align import align_performance
    from pianolens.data.pianocore import DEFAULT_ROOT, RAW_PREFIX, RAW_ZIP
    from pianolens.report.build import bar_error_table, bar_labels
    from pianolens.report.io import load_performance, load_score

    F._quiet()
    k, ref_id, rel, t = job
    meta = json.loads((F.HENRY / "scores" / "scores.json").read_text())[k]
    sc = load_score(F.HENRY / "scores" / f"{k}_score.mxl", meta["piece_id"])
    with zipfile.ZipFile(DEFAULT_ROOT / RAW_ZIP) as z, tempfile.TemporaryDirectory() as td:
        f = Path(td) / "ref.mid"
        f.write_bytes(z.read(RAW_PREFIX + rel))
        ap = align_performance(sc, load_performance(f, "transcribed", meta["piece_id"],
                                                    performance_id=ref_id))
    res = _label_all({"aligned": ap})
    labels = bar_labels(ap.score)
    return {"floor": [{"take": k, "transcriber": t, "ref_id": ref_id, "variant": v,
                       "suspect": bool(cr.summary["alignment_suspect"]),
                       "table": bar_error_table(cr, labels)}
                      for (_, v), cr in res.items()]}  # fmt: skip


# --------------------------------------------------------------------------- summary


def _prf(tp: float, fp: float, fn: float) -> tuple[float, float, float]:
    p = tp / (tp + fp) if tp + fp else np.nan
    r = tp / (tp + fn) if tp + fn else np.nan
    f = 2 * p * r / (p + r) if p + r else np.nan
    return p, r, f


def _boot_gap(df: pd.DataFrame, grp: str, a: str, b: str, col: str, cluster: str,
              n_boot: int, seed: int) -> tuple[float, float, float]:
    """Point estimate and percentile CI of mean(col | grp == a) - mean(col | grp == b),
    resampling ``cluster`` units."""
    per = df.groupby([cluster, grp])[col].agg(["sum", "count"])
    full = per.groupby(level=1).sum()
    if a not in full.index or b not in full.index:
        return np.nan, np.nan, np.nan
    est = full.loc[a, "sum"] / full.loc[a, "count"] - full.loc[b, "sum"] / full.loc[b, "count"]
    units = per.index.get_level_values(0).unique().to_numpy()
    rng = np.random.default_rng(seed)
    draws = []
    for _ in range(n_boot):
        cnt = pd.Series(rng.choice(units, size=len(units), replace=True)).value_counts()
        w = per.index.get_level_values(0).map(cnt).fillna(0).to_numpy()
        s = per.mul(w, axis=0).groupby(level=1).sum()
        if a in s.index and b in s.index and s.loc[a, "count"] and s.loc[b, "count"]:
            draws.append(s.loc[a, "sum"] / s.loc[a, "count"] - s.loc[b, "sum"] / s.loc[b, "count"])
    lo, hi = np.nanpercentile(draws, [2.5, 97.5])
    return float(est), float(lo), float(hi)


def expert_limits(tables: list[pd.DataFrame]) -> dict[str, float]:
    """``CORRECTNESS_EXPERT_BARS`` quantities from clean D-08 bar tables, as
    ``scripts/calibrate_report_f08.py`` computes them."""
    b = pd.concat(tables, ignore_index=True)
    b = b[b["n_score_notes"] > 0]
    me = (b["n_missed"] + b["n_extra"]) / b["n_score_notes"]
    mi = b["n_missed"] / b["n_score_notes"]
    return {"n_bars": len(b),
            "wrong_pitch_q95": float(np.quantile(b["n_wrong_pitch"], 0.95)),
            "wrong_pitch_q99": float(np.quantile(b["n_wrong_pitch"], 0.99)),
            "missed_extra_per_note_q95": float(np.quantile(me, 0.95)),
            "missed_extra_per_note_q99": float(np.quantile(me, 0.99)),
            "missed_per_note_q95": float(np.quantile(mi, 0.95)),
            "missed_per_note_q99": float(np.quantile(mi, 0.99)),
            "share_wrong_ge1": float((b["n_wrong_pitch"] >= 1).mean()),
            "share_wrong_ge2": float((b["n_wrong_pitch"] >= 2).mean()),
            "share_wrong_ge3": float((b["n_wrong_pitch"] >= 3).mean()),
            "share_missed_ge1": float((b["n_missed"] >= 1).mean())}  # fmt: skip


def expert_quantiles_f08(tables: list[dict]) -> dict:
    """The full ``calibrate_report_f08.py`` output for one variant (clean D-08, aligned)."""
    parts = []
    for t in tables:
        x = t["table"].copy()
        x["key"] = t["key"]
        parts.append(x)
    bars = pd.concat(parts, ignore_index=True)
    bars = bars[bars["n_score_notes"] > 0].copy()
    bars["n_errors"] = bars["n_wrong_pitch"] + bars["n_missed"] + bars["n_extra"]
    bars["n_missed_extra"] = bars["n_missed"] + bars["n_extra"]
    out: dict = {"n_performances": int(bars["key"].nunique()), "n_bars": len(bars)}
    for col in ("n_errors", "n_missed_extra", "n_wrong_pitch"):
        out[col] = {f"q{int(q * 100)}": float(np.quantile(bars[col], q))
                    for q in (0.5, 0.9, 0.95, 0.99)}  # fmt: skip
        out[col]["share_nonzero"] = float((bars[col] > 0).mean())
    rate = bars["n_missed_extra"] / bars["n_score_notes"]
    out["missed_extra_per_note"] = {f"q{int(q * 100)}": float(np.quantile(rate, q))
                                    for q in (0.5, 0.9, 0.95, 0.99)}  # fmt: skip
    mrate = bars["n_missed"] / bars["n_score_notes"]
    out["missed_per_note"] = {f"q{int(q * 100)}": float(np.quantile(mrate, q))
                              for q in (0.5, 0.9, 0.95, 0.99)}  # fmt: skip
    for k in (1, 2, 3):
        out["n_wrong_pitch"][f"share_ge{k}"] = float((bars["n_wrong_pitch"] >= k).mean())
    share = bars.groupby("key")["n_errors"].apply(lambda x: (x > 0).mean())
    out["share_bars_any_error_per_performance"] = {
        f"q{int(q * 100)}": float(np.quantile(share, q)) for q in (0.05, 0.5, 0.95)}
    per = bars.groupby("key")[["n_errors", "n_score_notes"]].sum()
    er = per["n_errors"] / per["n_score_notes"]
    out["error_rate_per_performance"] = {f"q{int(q * 100)}": float(np.quantile(er, q))
                                         for q in (0.05, 0.5, 0.95, 0.99)}  # fmt: skip
    return out


def _calibration(tables: list[dict], asap_rows: list[dict], floor_rows: list[dict]) -> dict:
    from pianolens.data import asap
    from pianolens.report import calibration as cal

    orig = dict(cal.CORRECTNESS_EXPERT_BARS)
    aidx = asap.asap_index()
    per_piece = aidx.groupby("piece_id").size()
    out: dict = {}
    minr, maxr = cal.EXPERT_CHECK_MIN_REFS, cal.EXPERT_CHECK_MAX_REFS
    try:
        for v in VARIANTS:
            clean = [t for t in tables if t["variant"] == v and t["rate"] == 0.0]
            lim = expert_limits([t["table"] for t in clean])
            full = expert_quantiles_f08(clean)
            cal.CORRECTNESS_EXPERT_BARS.update({k: lim[k] for k in (
                "wrong_pitch_q95", "wrong_pitch_q99", "missed_extra_per_note_q95",
                "missed_extra_per_note_q99", "missed_per_note_q95", "missed_per_note_q99")})
            res: dict = {"limits": lim, "f08_quantiles": full}
            by_piece: dict[str, list[dict]] = {}
            for r in sorted((r for r in asap_rows if r["variant"] == v), key=lambda r: r["midi"]):
                if not r["suspect"]:
                    by_piece.setdefault(r["piece_id"], []).append(r)
            covered = [t for t in clean
                       if per_piece.get(t["piece_id"], 0) >= minr + 1 and not t["suspect"]]
            for qname, q in (("global", None), ("q80/q99", cal.EXPERT_CHECK_Q)):
                parts = []
                for t in covered:
                    ex = [e["table"] for e in by_piece.get(t["piece_id"], [])
                          if e["performance_id"] != t["source"]][:maxr]
                    parts.append(F.tiers(t["table"], ex, True, q, minr))
                df = pd.concat(parts, ignore_index=True)
                res[f"keysensor/{qname}"] = {"n_copies": len(covered), "bars": len(df),
                                             **F.rates(df, "checked")}  # fmt: skip
                fl = [r for r in floor_rows if r["variant"] == v and not r["suspect"]]
                parts = []
                for r in fl:
                    ex = [e["table"] for e in fl if e["take"] == r["take"]
                          and e["transcriber"] == r["transcriber"] and e["ref_id"] != r["ref_id"]]
                    t2 = F.tiers(r["table"], ex, False, q, minr)
                    t2["transcriber"] = r["transcriber"]
                    parts.append(t2)
                df = pd.concat(parts, ignore_index=True)
                res[f"transcribed/{qname}"] = {"n_refs": len(fl), "bars": len(df),
                                               **F.rates(df, "checked"),
                                               "by_transcriber": {tr: F.rates(g, "checked")
                                                                  for tr, g in
                                                                  df.groupby("transcriber")}}
            out[v] = res
    finally:
        cal.CORRECTNESS_EXPERT_BARS.clear()
        cal.CORRECTNESS_EXPERT_BARS.update(orig)
    return out


def summarise(out: Path, n_boot: int = 2000) -> dict:
    res: dict = {}
    # ---------------- stress set
    sb = pd.read_parquet(out / "stress.parquet")
    sb["hit"] = sb["outcome"] == "paired_intended"
    sb["detected"] = sb["bar_err"] > 0
    sb["clean_bar"] = sb["bar_err_clean"] == 0
    # reproduction of BL-20 Part B (L, aligned, all injections)
    bl20 = pd.read_csv("experiments/2026-09-29-BL-20-density/artifacts/b_stress_summary.csv")
    bl20 = bl20[(bl20["mode"] == "aligned") & (bl20["window"] == 0.1)
                & bl20["cell"].isin(D.CELLS)].set_index("cell")  # fmt: skip
    rep = sb[(sb["variant"] == "L") & (sb["mode"] == "aligned")].groupby("cell").agg(
        n=("hit", "size"), strict=("hit", "mean"),
        absorbed=("outcome", lambda s: (s == "absorbed").mean()))
    rep["bl20_n"] = bl20["n"]
    rep["bl20_strict"] = bl20["strict_recall"]
    rep["bl20_absorbed"] = bl20["absorbed"]
    res["reproduction_bl20"] = rep.reset_index().to_dict("records")
    rows = []
    for (mode, v, cell), g in sb.groupby(["mode", "variant", "cell"]):
        c = g[g["clean_bar"]]
        oc = c["outcome"].value_counts(normalize=True)
        rows.append({"mode": mode, "variant": v, "cell": cell, "n_all": len(g),
                     "strict_all": g["hit"].mean(), "n_clean": len(c),
                     "strict_clean": c["hit"].mean(), "detected_clean": c["detected"].mean(),
                     "silent_clean": (c["bar_err"] <= c["bar_err_clean"]).mean(),
                     **{f"share_{k}": float(oc.get(k, 0.0)) for k in (
                         "paired_intended", "paired_other", "absorbed", "extra", "ornament")}})
    st = pd.DataFrame(rows)
    gaps = []
    for (mode, v), g in sb[sb["clean_bar"]].groupby(["mode", "variant"]):
        g = g[g["cell"].isin(["dense-N", "sparse-O"])]
        for cl in ("source", "piece_id"):
            e, lo, hi = _boot_gap(g, "cell", "dense-N", "sparse-O", "hit", cl, n_boot, SEED)
            gaps.append({"mode": mode, "variant": v, "cluster": cl, "gap": e, "lo": lo, "hi": hi})
    st.to_csv(out / "stress_clean_summary.csv", index=False)
    pd.DataFrame(gaps).to_csv(out / "stress_gap_boot.csv", index=False)
    res["stress"] = rows
    res["stress_gap"] = gaps
    # N1: sparse-O on bars clean under both L and TR
    a = sb[(sb["mode"] == "aligned") & (sb["cell"] == "sparse-O")]
    piv = a.pivot_table(index=["key", "performance_id"], columns="variant",
                        values=["hit", "clean_bar"], aggfunc="first")  # fmt: skip
    both = piv[piv[("clean_bar", "L")].astype(bool) & piv[("clean_bar", "TR")].astype(bool)]
    res["N1"] = {v: {"n": len(both), "strict": float(both[("hit", v)].astype(float).mean())}
                 for v in VARIANTS}  # fmt: skip
    # DF-10: the BL-20 different-pitch absorptions
    lA = sb[(sb["variant"] == "L") & (sb["mode"] == "aligned")]
    dp = lA[(lA["outcome"] == "absorbed") & (lA["partner_pitch"] != lA["pitch"])]
    ids = set(zip(dp["key"], dp["performance_id"], strict=True))
    in_ids = np.array([k in ids for k in zip(sb["key"], sb["performance_id"], strict=True)])
    df10 = sb[(sb["mode"] == "aligned").to_numpy() & in_ids]
    res["DF10_diffpitch_absorbed"] = {
        "n": len(ids), "by_variant": {v: g["outcome"].value_counts().to_dict()
                                      for v, g in df10.groupby("variant")}}  # fmt: skip
    ss = pd.read_parquet(out / "stress_summ.parquet")
    res["stress_dissolved"] = ss.groupby(["mode", "variant"])[
        ["n_pitch_dissolved", "n_reassigned"]].sum().reset_index().to_dict("records")

    # ---------------- F-02 set
    bars = pd.read_parquet(out / "f02_bars.parquet")
    bars["tp"] = bars["gt"] & bars["pred"]
    bars["fp"] = bars["pred"] & ~bars["gt"] & ~bars["dont_care"]
    bars["fn"] = bars["gt"] & ~bars["pred"]
    agg = bars.groupby(["mode", "variant", "rate"])[["tp", "fp", "fn"]].sum().reset_index()
    agg[["precision", "recall", "f1"]] = [list(_prf(*x)) for x in
                                          agg[["tp", "fp", "fn"]].to_numpy()]  # fmt: skip
    agg.to_csv(out / "f02_bar_any.csv", index=False)
    res["f02_bar_any"] = agg.to_dict("records")
    # C2: rate 0.05, injected wrong pitches in clean bars, dense vs sparse
    wr = pd.read_parquet(out / "f02_wrong.parquet")
    wr["bin"] = D.density_bin(wr["ioi"].to_numpy())
    wr["grp"] = np.where(wr["bin"].isin(["<60", "60-100"]), "dense",
                         np.where(wr["bin"] == ">200", "sparse", "mid"))  # fmt: skip
    wr["hit"] = wr["outcome"] == "paired_intended"
    clean_err = bars[bars["rate"] == 0.0].set_index(["source", "mode", "variant",
                                                     "measure_index"])["n_errors"]  # fmt: skip
    idx = pd.MultiIndex.from_arrays([wr["source"], wr["mode"], wr["variant"], wr["bar"]])
    wr["clean_bar"] = clean_err.reindex(idx).fillna(1).to_numpy() == 0
    c2 = []
    for (mode, v, rate), g in wr.groupby(["mode", "variant", "rate"]):
        for sub, name in ((g, "all"), (g[g["clean_bar"]], "clean")):
            s = sub[sub["grp"].isin(["dense", "sparse"])]
            e, lo, hi = _boot_gap(s, "grp", "dense", "sparse", "hit", "source", n_boot, SEED)
            c2.append({"mode": mode, "variant": v, "rate": rate, "bars": name,
                       "n_dense": int((s["grp"] == "dense").sum()),
                       "n_sparse": int((s["grp"] == "sparse").sum()),
                       "strict_dense": float(s.loc[s["grp"] == "dense", "hit"].mean()),
                       "strict_sparse": float(s.loc[s["grp"] == "sparse", "hit"].mean()),
                       "gap": e, "lo": lo, "hi": hi,
                       **{f"share_{k}": float((sub["outcome"] == k).mean()) for k in (
                           "absorbed", "ornament", "extra", "paired_other")}})  # fmt: skip
    pd.DataFrame(c2).to_csv(out / "f02_wrong_dense_sparse.csv", index=False)
    res["C2"] = c2
    fs = pd.read_parquet(out / "f02_summ.parquet")
    res["f02_dissolved"] = fs.groupby(["mode", "variant", "rate"])[
        ["n_pitch_dissolved", "n_ornament_matches", "n_reassigned", "n_ornament",
         "n_wrong_pitch", "n_missed", "n_extra"]].sum().reset_index().to_dict("records")
    # ---------------- N3: legacy-tolerated ornament notes on the clean copies
    orn = pd.read_parquet(out / "f02_orn.parquet")
    orn["error"] = orn["label"].isin(["extra", "wrong_pitch"])
    b0 = bars[(bars["rate"] == 0.0) & (bars["mode"] == "aligned")]
    err = b0.set_index(["source", "variant", "measure_index"])["n_errors"]
    n3 = {}
    for v, g in orn.groupby("variant"):
        bl = g[["source", "bar_legacy"]].drop_duplicates()
        bl = bl[bl["bar_legacy"] >= 0]
        e_l = err.reindex(pd.MultiIndex.from_arrays([bl["source"], ["L"] * len(bl),
                                                     bl["bar_legacy"]])).to_numpy()
        e_v = err.reindex(pd.MultiIndex.from_arrays([bl["source"], [v] * len(bl),
                                                     bl["bar_legacy"]])).to_numpy()
        ok = e_l == 0
        n3[v] = {"n_notes": len(g), "share_error": float(g["error"].mean()),
                 "labels": g["label"].value_counts().to_dict(),
                 "by_kind": g.groupby("kind")["error"].agg(["size", "mean"]).to_dict("index"),
                 "n_bars_errorfree_legacy": int(ok.sum()),
                 "share_bars_flagged": float((e_v[ok] > 0).mean()) if ok.any() else np.nan}
    res["N3"] = n3
    # ---------------- N4: calibration
    with open(out / "tables.pkl", "rb") as f:
        tabs = pickle.load(f)
    if tabs["asap"] and tabs["floor"]:
        res["N4"] = _calibration(tabs["f02"], tabs["asap"], tabs["floor"])
    (out / "summary.json").write_text(json.dumps(res, indent=1, default=float))
    return res


# --------------------------------------------------------------------------- main


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--part", choices=("run", "summary", "all"), default="all")
    ap.add_argument("--root", default="data/processed/mistakes_v1")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--limit", type=int, default=0, help="first N source performances only")
    ap.add_argument("--no-calibration", action="store_true", help="skip the asap/floor jobs")
    ap.add_argument("--n-boot", type=int, default=2000)
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    a.out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    if a.part in ("run", "all"):
        from pianolens.data import asap
        from pianolens.report import calibration as cal

        index = pd.read_csv(Path(a.root) / "index.csv", keep_default_na=False)
        srcs = index["performance_id"].drop_duplicates()
        if a.limit:
            srcs = srcs.iloc[: a.limit]
            index = index[index["performance_id"].isin(srcs)]
        aidx = asap.asap_index()
        per_piece = aidx.groupby("piece_id").size()
        clean = index[index["rate"].astype(float) == 0.0]
        covered = clean[clean["piece_id"].map(per_piece).fillna(0)
                        >= cal.EXPERT_CHECK_MIN_REFS + 1]  # fmt: skip
        pieces = sorted(covered["piece_id"].unique())
        acc: dict[str, list] = {k: [] for k in ("bars", "wrong", "summ", "tables", "orn",
                                                "stress", "stress_summ", "asap", "floor")}
        failed = []
        with ProcessPoolExecutor(a.workers, initializer=_init, initargs=(a.root,)) as ex:
            futs = {ex.submit(f02_one, k): f"f02:{k}" for k in index["key"]}
            futs.update({ex.submit(stress_one, (i, s)): f"stress:{s}"
                         for i, s in enumerate(srcs)})  # fmt: skip
            if not a.no_calibration:
                perf_ids = aidx[aidx["piece_id"].isin(pieces)]["performance_id"].tolist()
                futs.update({ex.submit(asap_one, p): f"asap:{p}" for p in perf_ids})
                futs.update({ex.submit(floor_one, j): f"floor:{j[1]}" for j in F.floor_jobs()})
            for n, fu in enumerate(as_completed(futs), 1):
                try:
                    for k, v in fu.result().items():
                        acc[k].extend(v)
                except Exception as e:  # noqa: BLE001 - count and continue
                    failed.append((futs[fu], repr(e)[:300]))
                if n % 100 == 0:
                    log.info("%d / %d (%.0f s)", n, len(futs), time.time() - t0)
        for k in ("bars", "wrong", "summ", "orn"):
            pd.DataFrame(acc[k]).to_parquet(a.out / f"f02_{k}.parquet", index=False)
        pd.DataFrame(acc["stress"]).to_parquet(a.out / "stress.parquet", index=False)
        pd.DataFrame(acc["stress_summ"]).to_parquet(a.out / "stress_summ.parquet", index=False)
        with open(a.out / "tables.pkl", "wb") as f:
            pickle.dump({"f02": acc["tables"], "asap": acc["asap"], "floor": acc["floor"]}, f)
        pd.DataFrame(failed, columns=["job", "error"]).to_csv(a.out / "failed.csv", index=False)
        log.info("failed: %d %s", len(failed), failed[:3])
    if a.part in ("summary", "all"):
        summarise(a.out, a.n_boot)
    log.info("done in %.0f s", time.time() - t0)


if __name__ == "__main__":
    main()
