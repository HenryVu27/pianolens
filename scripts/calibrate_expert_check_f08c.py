"""F-08c calibration: the per-bar expert check for single-take correctness flags.

Run: ``uv run python scripts/calibrate_expert_check_f08c.py [--workers 10] [--from-cache]``

The practice report tiers a bar's correctness errors against global expert limits
(``calibration.CORRECTNESS_EXPERT_BARS``). F-08c adds a per-bar check: a bar must also exceed
the ``EXPERT_CHECK_Q`` quantiles of the same quantity over expert performances of the same score
at that bar (``build.expert_bar_limits``), with experts of the target's capture method.

**A. Key-sensor input (the F-08 expert calibration set).** The clean (rate 0) D-08 copies whose
piece has at least 6 ASAP performances, so that at least 5 *other* ASAP performances are the
experts (leave the source performance out; the first ``EXPERT_CHECK_MAX_REFS`` in file order, as
``report_from_files`` does). Share of expert bars that are notable-or-strong and strong, without
and with the check, for several quantile choices. **Recall:** the rate 0.02 / 0.05 / 0.10 D-08
copies of the same performances; a bar with an injected mistake is caught when it is tiered.

**B. Transcribed input (the A-01 floor).** The 150 PianoCoRe transcriptions of A-01's 5 Chopin
pieces (15 per piece and transcriber family, the same seeded draw as
``scripts/a01_henry_baseline.py``), aligned to the same PianoCoRe scores. Each is a target
against the other transcriptions of its piece by the same transcriber (leave-one-out), with
extra notes not counted (A-01). The per-bar tables are cached for ``a01_henry_reports.py``.

Outputs (gitignored) in ``data/interim/reports/calibration/``: ``f08c_asap_tables.pkl``,
``f08c_d08_tables.pkl``, ``f08c_floor_tables.pkl``, ``f08c_summary.json``.
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
MISTAKES = REPO / "data" / "processed" / "mistakes_v1"
HENRY = REPO / "data" / "interim" / "henry_takes"
PC_TRANSCRIBER = {"Aria-AMT": "aria_amt", "Transkun V2": "transkun"}
Q_VARIANTS = {"q50/q90": (0.50, 0.90), "q80/q99": (0.80, 0.99), "q90/q99": (0.90, 0.99),
              "q95/q99": (0.95, 0.99), "max/max": (1.0, 1.0)}
_STATE: dict = {}


def _quiet() -> None:
    import logging

    warnings.filterwarnings("ignore")
    logging.disable(logging.WARNING)


def _table(ap, cr) -> pd.DataFrame:  # noqa: ANN001
    from pianolens.report.build import bar_error_table, bar_labels

    return bar_error_table(cr, bar_labels(ap.score))


# ----------------------------------------------------------------------------- workers


def asap_one(perf_id: str) -> dict:
    _quiet()
    from pianolens.align import align_performance
    from pianolens.data import asap
    from pianolens.features.correctness import correctness

    idx = asap.asap_index().set_index("performance_id", drop=False)
    row = idx.loc[perf_id]
    ap = align_performance(asap.load_asap_score(row), asap.load_asap_performance(row))
    cr = correctness(ap)
    return {"performance_id": perf_id, "piece_id": row["piece_id"],
            "midi": row["midi_performance"], "suspect": bool(cr.summary["alignment_suspect"]),
            "table": _table(ap, cr)}  # fmt: skip


def _d08_init() -> None:
    _quiet()
    from pianolens.data.perturb import load_mistake_set

    index, get = load_mistake_set(MISTAKES)
    _STATE["get"] = get
    _STATE["index"] = index.set_index("key")


def d08_one(key: str, clean_key: str) -> dict:
    """Align one D-08 copy; per-bar table and the bar labels of its injected mistakes."""
    from pianolens.align import align_performance
    from pianolens.data import asap
    from pianolens.features.correctness import correctness
    from pianolens.report.build import bar_labels

    perf, labs = _STATE["get"](key)
    r = _STATE["index"].loc[key]
    arow = asap.asap_index().set_index("performance_id", drop=False).loc[r["performance_id"]]
    ap = align_performance(asap.load_asap_score(arow), perf)
    cr = correctness(ap)
    labels = bar_labels(ap.score)
    inj = set()
    n = labs.notes
    bar_of = dict(zip(cr.notes["performance_id"].astype(str), cr.notes["measure_index"],
                      strict=True))
    for pid in n.loc[n["injected"] & n["label"].isin(["wrong_pitch", "extra"]),
                     "performance_id"].astype(str):
        b = int(bar_of.get(pid, -1))
        if b >= 0:
            inj.add(labels[b])
    miss = labs.missed[labs.missed["injected"]]
    if len(miss):
        src = _STATE["get"](clean_key)[0].notes
        on = dict(zip(src["id"].astype(str), src["onset_sec"].astype(float), strict=True))
        sn = cr.score_notes.dropna(subset=["expected_onset_sec"])
        sid = sn["score_id"].astype(str).to_numpy()
        base = np.array([s.split("-")[0] for s in sid])
        for s, op in zip(miss["score_id"].astype(str), miss["original_performance_id"].astype(str),
                         strict=True):
            t = on.get(op)
            if t is None or not len(sn):
                continue
            cand = np.flatnonzero((sid == s) | (base == s.split("-")[0]))
            if not len(cand):
                cand = np.arange(len(sn))
            j = cand[np.argmin(np.abs(sn["expected_onset_sec"].to_numpy()[cand] - t))]
            b = int(sn["measure_index"].iloc[j])
            if b >= 0:
                inj.add(labels[b])
    return {"key": key, "performance_id": r["performance_id"], "piece_id": arow["piece_id"],
            "rate": float(r["rate"]), "suspect": bool(cr.summary["alignment_suspect"]),
            "table": _table(ap, cr), "injected_bars": sorted(inj)}  # fmt: skip


def floor_jobs(n_refs: int = 15, seed: int = 0) -> list[tuple]:
    """The same draw as ``scripts/a01_henry_baseline.py`` (``floor_jobs``)."""
    from pianolens.data.pianocore import PianoCoRe

    idx = PianoCoRe().index
    meta = json.loads((HENRY / "scores" / "scores.json").read_text())
    rng = np.random.default_rng(seed)
    jobs = []
    for k, m in meta.items():
        rows = idx[idx["piece_id"] == m["piece_id"]]
        for cm, t in PC_TRANSCRIBER.items():
            r = rows[rows["capture_model"] == cm]
            take = rng.choice(len(r), size=min(n_refs, len(r)), replace=False)
            for i in sorted(take):
                jobs.append((k, str(r.iloc[i]["id"]), str(r.iloc[i]["performance_midi_path"]), t))
    return jobs


def floor_one(k: str, ref_id: str, rel: str, t: str) -> dict:
    _quiet()
    import tempfile
    import zipfile

    from pianolens.align import align_performance
    from pianolens.data.pianocore import DEFAULT_ROOT, RAW_PREFIX, RAW_ZIP
    from pianolens.features.correctness import correctness
    from pianolens.report.io import load_performance, load_score

    meta = json.loads((HENRY / "scores" / "scores.json").read_text())[k]
    sc = load_score(HENRY / "scores" / f"{k}_score.mxl", meta["piece_id"])
    with zipfile.ZipFile(DEFAULT_ROOT / RAW_ZIP) as z, tempfile.TemporaryDirectory() as td:
        f = Path(td) / "ref.mid"
        f.write_bytes(z.read(RAW_PREFIX + rel))
        ap = align_performance(sc, load_performance(f, "transcribed", meta["piece_id"],
                                                    performance_id=ref_id))
    cr = correctness(ap)
    return {"take": k, "transcriber": t, "ref_id": ref_id,
            "suspect": bool(cr.summary["alignment_suspect"]), "table": _table(ap, cr)}


# ----------------------------------------------------------------------------- evaluation


def tiers(table: pd.DataFrame, experts: list[pd.DataFrame], extras: bool,
          q: tuple[float, float] | None, min_refs: int) -> pd.DataFrame:
    """Global and checked tier per bar of ``table`` (bars with graded notes only)."""
    from pianolens.report.build import (
        _correctness_tier,
        expert_bar_limits,
        global_correctness_limits,
    )

    t = table[table["n_score_notes"] > 0].reset_index(drop=True)
    glim = global_correctness_limits(extras)
    me = t["n_missed"] + (t["n_extra"] if extras else 0)
    g = [_correctness_tier(int(w), int(m), int(n), glim)[0]
         for w, m, n in zip(t["n_wrong_pitch"], me, t["n_score_notes"], strict=True)]
    out = pd.DataFrame({"label": t["label"], "global": g})
    if q is None:
        out["checked"] = g
        out["n_experts"] = 0
        return out
    lim = expert_bar_limits(experts, list(t["label"]), extras, q, min_refs)
    ch = []
    for i in range(len(t)):
        e = lim.iloc[i]
        if not np.isfinite(e["wrong_q95"]):
            ch.append(g[i])
            continue
        ll = {k: max(glim[k], float(e[k])) for k in glim}
        ch.append(_correctness_tier(int(t["n_wrong_pitch"].iat[i]), int(me.iat[i]),
                                    int(t["n_score_notes"].iat[i]), ll)[0])
    out["checked"] = ch
    out["n_experts"] = lim["n_experts"].to_numpy(int)
    return out


def rates(df: pd.DataFrame, col: str) -> dict:
    n = len(df)
    return {"notable_plus": float((df[col] != "none").mean()) if n else np.nan,
            "strong": float((df[col] == "strong").mean()) if n else np.nan}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--from-cache", action="store_true")
    args = ap.parse_args()
    _quiet()
    from pianolens.data import asap
    from pianolens.report import calibration as cal

    OUT.mkdir(parents=True, exist_ok=True)
    index = pd.read_csv(MISTAKES / "index.csv", keep_default_na=False)
    aidx = asap.asap_index()
    per_piece = aidx.groupby("piece_id").size()
    clean = index[index["rate"].astype(float) == 0.0]
    covered = clean[clean["piece_id"].map(per_piece).fillna(0) >= cal.EXPERT_CHECK_MIN_REFS + 1]
    pieces = sorted(covered["piece_id"].unique())
    c_asap, c_d08, c_floor = (OUT / "f08c_asap_tables.pkl", OUT / "f08c_d08_tables.pkl",
                              OUT / "f08c_floor_tables.pkl")
    if args.from_cache:
        asap_rows = pickle.loads(c_asap.read_bytes())
        d08_rows = pickle.loads(c_d08.read_bytes())
        floor_rows = pickle.loads(c_floor.read_bytes())
    else:
        perf_ids = aidx[aidx["piece_id"].isin(pieces)]["performance_id"].tolist()
        keys = index[index["performance_id"].isin(covered["performance_id"])]
        ck = dict(zip(clean["performance_id"], clean["key"], strict=True))
        asap_rows, d08_rows, floor_rows = [], [], []
        with ProcessPoolExecutor(args.workers, initializer=_d08_init) as ex:
            futs = {ex.submit(asap_one, p): "asap" for p in perf_ids}
            futs.update({ex.submit(d08_one, k, ck[p]): "d08"
                         for k, p in zip(keys["key"], keys["performance_id"], strict=True)})
            futs.update({ex.submit(floor_one, *j): "floor" for j in floor_jobs()})
            for fu in as_completed(futs):
                try:
                    r = fu.result()
                except Exception as e:  # noqa: BLE001 - count failures
                    print(futs[fu], "failed:", repr(e)[:200])
                    continue
                {"asap": asap_rows, "d08": d08_rows, "floor": floor_rows}[futs[fu]].append(r)
        c_asap.write_bytes(pickle.dumps(asap_rows))
        c_d08.write_bytes(pickle.dumps(d08_rows))
        c_floor.write_bytes(pickle.dumps(floor_rows))

    # ---- A: key-sensor experts and D-08 recall
    by_piece: dict[str, list[dict]] = {}
    for r in sorted(asap_rows, key=lambda r: r["midi"]):
        if not r["suspect"]:
            by_piece.setdefault(r["piece_id"], []).append(r)
    maxr, minr = cal.EXPERT_CHECK_MAX_REFS, cal.EXPERT_CHECK_MIN_REFS
    summ: dict = {"A": {"n_pieces": len(pieces), "n_asap_performances": len(asap_rows),
                        "n_asap_suspect": sum(r["suspect"] for r in asap_rows),
                        "min_refs": minr, "max_refs": maxr}}
    variants: dict[str, tuple | None] = {"global": None, **Q_VARIANTS}
    res: dict[str, list] = {v: [] for v in variants}
    for r in d08_rows:
        if r["suspect"]:
            continue
        ex = [e["table"] for e in by_piece.get(r["piece_id"], [])
              if e["performance_id"] != r["performance_id"]][:maxr]
        for v, q in variants.items():
            t = tiers(r["table"], ex, True, q, minr)
            t["key"], t["rate"] = r["key"], r["rate"]
            t["injected"] = t["label"].isin(r["injected_bars"])
            t["n_refs_perf"] = len(ex)
            res[v].append(t)
    A = summ["A"]
    A["n_d08_copies"] = {str(rt): int(sum(1 for r in d08_rows if r["rate"] == rt
                                          and not r["suspect"])) for rt in (0.0, .02, .05, .1)}
    for v in variants:
        df = pd.concat(res[v], ignore_index=True)
        cl = df[df["rate"] == 0.0]
        A[v] = {"expert_bars": len(cl), "expert_bars_checked": int((cl["n_experts"] >= minr).sum()),
                "expert_rate_global": rates(cl, "global"), "expert_rate_checked":
                rates(cl, "checked")}  # fmt: skip
        for rt in (0.02, 0.05, 0.1):
            p = df[(df["rate"] == rt)]
            inj, non = p[p["injected"]], p[~p["injected"]]
            A[v][f"rate_{rt}"] = {
                "injected_bars": len(inj),
                "recall_global": rates(inj, "global"), "recall_checked": rates(inj, "checked"),
                "non_injected_global": rates(non, "global"),
                "non_injected_checked": rates(non, "checked")}  # fmt: skip
    # ---- B: transcribed (A-01 floor), leave-one-out within piece x transcriber
    B: dict = {"n_refs": len(floor_rows), "n_suspect": sum(r["suspect"] for r in floor_rows)}
    for extras in (False, True):
        for v, q in variants.items():
            parts = []
            for r in floor_rows:
                if r["suspect"]:
                    continue
                ex = [e["table"] for e in floor_rows if not e["suspect"] and e["take"] == r["take"]
                      and e["transcriber"] == r["transcriber"] and e["ref_id"] != r["ref_id"]]
                t = tiers(r["table"], ex, extras, q, minr)
                t["transcriber"] = r["transcriber"]
                parts.append(t)
            df = pd.concat(parts, ignore_index=True)
            B[f"{'with' if extras else 'no'}_extras/{v}"] = {
                "bars": len(df), "bars_checked": int((df["n_experts"] >= minr).sum()),
                "rate_global": rates(df, "global"), "rate_checked": rates(df, "checked"),
                "by_transcriber": {tr: rates(g, "checked") for tr, g in
                                   df.groupby("transcriber")}}  # fmt: skip
    summ["B"] = B
    (OUT / "f08c_summary.json").write_text(json.dumps(summ, indent=1, default=float))
    print(json.dumps(summ, indent=1, default=float))


if __name__ == "__main__":
    main()
