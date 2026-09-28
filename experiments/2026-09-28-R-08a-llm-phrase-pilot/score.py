"""R-08a scoring: annotator (bar, beat) events -> performed-score beats -> F-05c metrics against
the DCML annotations, plus the comparators (F-05c cadence detector, proxy, 4-bar grid).

    uv run python experiments/2026-09-28-R-08a-llm-phrase-pilot/score.py --comparators
    uv run python experiments/2026-09-28-R-08a-llm-phrase-pilot/score.py --llm <dir with M*.json>

``--comparators`` also runs the harness check: the detector's ends and starts are written as
annotator events (bar, printed beat), scored through the same path as the LLM (propagation
off), and must equal F-05c's per-movement rows in ``data/interim/phrase_f05c/boundaries.csv``.
Matching is ``boundary_prf`` from ``scripts/check_phrase_f05b.py`` (one-to-one, closest pairs
first; the first onset is excluded for starts). See README "Metrics".
"""

from __future__ import annotations

import json
import re
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from common import ART, BLIND, parse_beat, selection, to_bar_beat, to_perf_beat

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
warnings.filterwarnings("ignore")

from check_phrase_f05b import boundary_prf  # noqa: E402

F05C = ROOT / "data" / "interim" / "phrase_f05c"
SEED = 20260928
N_BOOT = 10_000
TYPES = ("PAC", "IAC", "HC", "EC", "DC")
SNAP = 0.5  # beats


# --------------------------------------------------------------------------- inputs


def movement_inputs() -> dict[str, dict]:
    """Per pilot id: stem, bar table, ground truth, F-05c cached candidates."""
    D = pd.read_pickle(F05C / "cands.pkl")
    out = {}
    for p in selection():
        mid, stem = p["id"], p["stem"]
        gt = json.loads((ART / "ground_truth" / f"{mid}.json").read_text())
        d = D[stem]
        # the F-05c cache and the D-11 ground truth are the same labels
        assert np.allclose(sorted(d["ends"]), gt["ends"]) and np.allclose(
            sorted(d["starts"]), gt["starts"]), mid
        out[mid] = {"stem": stem, "bars": pd.read_csv(ART / f"bars_{mid}.csv",
                                                      dtype={"written": str}),
                    "gt": gt, "d": d, "pointers": pointer_map(mid)}
    return out


def pointer_map(mid: str) -> dict[int, int]:
    """pointer bar -> the printed bar it repeats, parsed from the rendering itself."""
    txt = (BLIND / f"{mid}.txt").read_text()
    m: dict[int, int] = {}
    for a, b, c, d in re.findall(r"^BARS (\d+)-(\d+) .*as bars (\d+)-(\d+)$", txt, re.M):
        a, b, c, d = map(int, (a, b, c, d))
        assert b - a == d - c
        for k in range(b - a + 1):
            m[a + k] = c + k
    for a, c in re.findall(r"^BAR (\d+) .*same notes and markings as bar (\d+)$", txt, re.M):
        m[int(a)] = int(c)
    return m


# --------------------------------------------------------------------------- mapping


def map_events(events: list[dict], mv: dict, *, snap: bool = True, propagate: bool = True,
               min_conf: float = 0.0) -> tuple[pd.DataFrame, dict]:
    """Annotator events -> DataFrame (beat, type, cadence, confidence) on performed beats."""
    bars, onsets = mv["bars"], np.asarray(mv["d"]["onset_beats"], float)
    stats = {"n_in": len(events), "dropped_bad": 0, "dropped_conf": 0, "snapped": 0,
             "unsnapped_far": 0, "propagated": 0}
    by_src: dict[int, list[int]] = {}
    for p, src in mv["pointers"].items():
        by_src.setdefault(src, []).append(p)
    rows = []
    for e in events:
        try:
            bar, beat = int(e["bar"]), parse_beat(e["beat"])
            typ = str(e["type"])
            assert typ in ("phrase_end", "phrase_start", "cadence")
        except Exception:  # noqa: BLE001
            stats["dropped_bad"] += 1
            continue
        conf = float(e.get("confidence", 1.0) or 0.0)
        if conf < min_conf:
            stats["dropped_conf"] += 1
            continue
        targets = [bar] + (by_src.get(bar, []) if propagate else [])
        for i, b in enumerate(targets):
            x = to_perf_beat(bars, b, beat)
            if x is None or x < bars["start"].iloc[0] - 1e-6 or x > bars["end"].iloc[-1] + 1e-6:
                stats["dropped_bad"] += int(i == 0)
                continue
            if snap:
                j = int(np.argmin(np.abs(onsets - x)))
                if abs(onsets[j] - x) <= SNAP + 1e-9:
                    # float32 onset beats: differences below 1e-4 are rounding, not snapping
                    stats["snapped"] += int(abs(onsets[j] - x) > 1e-4)
                    x = float(onsets[j])
                else:
                    stats["unsnapped_far"] += 1
            stats["propagated"] += int(i > 0)
            rows.append({"beat": round(x, 6), "type": typ,
                         "cadence": str(e.get("cadence", "none")), "confidence": conf})
    df = pd.DataFrame(rows, columns=["beat", "type", "cadence", "confidence"])
    df = (df.sort_values("confidence", ascending=False).drop_duplicates(["beat", "type"])
          .sort_values("beat").reset_index(drop=True))
    return df, stats


def match_pairs(pred, true, tol: float, first: float) -> list[tuple[float, float]]:
    """The (pred, true) pairs of ``boundary_prf``'s matching."""
    pred = sorted(p for p in pred if p > first + 1e-6)
    true = sorted(t for t in true if t > first + 1e-6)
    pairs = sorted((abs(p - t), i, j) for i, p in enumerate(pred) for j, t in enumerate(true)
                   if abs(p - t) <= tol + 1e-6)
    ui, uj, out = set(), set(), []
    for _, i, j in pairs:
        if i not in ui and j not in uj:
            ui.add(i)
            uj.add(j)
            out.append((pred[i], true[j]))
    return out


# --------------------------------------------------------------------------- metrics


def score_movement(mid: str, mv: dict, ends: list[float], starts: list[float],
                   end_types: dict[float, str] | None, method: str,
                   cad_marks: dict[float, str] | None = None) -> list[dict]:
    """F-05c rows for one movement. ``end_types``: predicted cadence type per end beat.
    ``cad_marks``: every predicted cadence mark (phrase ends plus ``cadence`` events) with its
    type, for the ``all marks`` cadence recall and type agreement (LLM only)."""
    gt, d = mv["gt"], mv["d"]
    bpb = d["meta"]["beats_per_bar"]
    first = float(d["onset_beats"][0])
    cad = pd.DataFrame(gt["cadences"])
    rows = []
    base = {"id": mid, "movement": mv["stem"], "method": method}
    for tol, tn in ((1.0, "1beat"), (bpb, "1bar")):
        if ends is not None:
            rows.append({**base, "target": "end", "tol": tn,
                         **boundary_prf(ends, gt["ends"], tol, -np.inf)})
            rows.append({**base, "target": "cadence", "tol": tn,
                         **boundary_prf(ends, cad["beat"].tolist(), tol, -np.inf)})
        if starts is not None:
            rows.append({**base, "target": "start", "tol": tn,
                         **boundary_prf(starts, gt["starts"], tol, first)})
    if ends is not None:
        for typ in TYPES:
            g = cad[cad["cadence"] == typ]
            r = boundary_prf(ends, g["beat"].tolist(), 1.0, -np.inf)
            rows.append({**base, "target": f"cad_{typ}", "tol": "1beat", "tp": r["tp"],
                         "n_true": r["n_true"], "n_pred": r["n_pred"]})
    cmap = dict(zip(cad["beat"].round(6), cad["cadence"], strict=False))
    if ends is not None and end_types is not None:
        # type agreement on the DCML cadences matched by a predicted end (+-1 beat)
        for p, t in match_pairs(ends, cad["beat"].tolist(), 1.0, -np.inf):
            rows.append({**base, "target": "type_pair", "tol": "1beat",
                         "dcml": cmap[round(t, 6)], "pred_type": end_types[round(p, 6)]})
    if cad_marks is not None:
        marks = sorted(cad_marks)
        m_all = {**base, "method": method + "+cad_marks"}
        for typ in TYPES:
            g = cad[cad["cadence"] == typ]
            r = boundary_prf(marks, g["beat"].tolist(), 1.0, -np.inf)
            rows.append({**m_all, "target": f"cad_{typ}", "tol": "1beat", "tp": r["tp"],
                         "n_true": r["n_true"], "n_pred": r["n_pred"]})
        rows.append({**m_all, "target": "cadence", "tol": "1beat",
                     **boundary_prf(marks, cad["beat"].tolist(), 1.0, -np.inf)})
        for p, t in match_pairs(marks, cad["beat"].tolist(), 1.0, -np.inf):
            rows.append({**m_all, "target": "type_pair", "tol": "1beat",
                         "dcml": cmap[round(t, 6)], "pred_type": cad_marks[p]})
    return rows


def boot_mean(x: np.ndarray, rng: np.random.Generator) -> tuple[float, float, float]:
    x = np.asarray(x, float)
    idx = rng.integers(0, len(x), size=(N_BOOT, len(x)))
    bs = np.nanmean(x[idx], axis=1)
    return float(np.nanmean(x)), float(np.nanpercentile(bs, 2.5)), float(np.nanpercentile(bs, 97.5))


def summarise(B: pd.DataFrame) -> str:
    rng = np.random.default_rng(SEED)
    out = []
    main = B[B["target"].isin(["end", "start", "cadence"])]
    out.append("Mean over movements (95% bootstrap CI over movements), and pooled counts")
    out.append(f"{'target':8s} {'tol':6s} {'method':18s} {'P':>6s} {'R':>6s} {'F1':>6s} "
               f"{'F1 CI':>15s} {'pooled P/R/F1':>20s}")
    for (t, tol, m), g in main.groupby(["target", "tol", "method"], sort=True):
        f, lo, hi = boot_mean(g["F1"].to_numpy(), rng)
        tp, npred, ntrue = g["tp"].sum(), g["n_pred"].sum(), g["n_true"].sum()
        pp, pr = tp / npred if npred else np.nan, tp / ntrue
        pf = 2 * pp * pr / (pp + pr) if pp + pr > 0 else 0.0
        out.append(f"{t:8s} {tol:6s} {m:18s} {g['P'].mean():6.3f} {g['R'].mean():6.3f} "
                   f"{f:6.3f} [{lo:5.3f}, {hi:5.3f}] {pp:6.3f}/{pr:5.3f}/{pf:5.3f}")
    ct = B[B["target"].str.startswith("cad_")]
    if len(ct):
        out.append("\nRecall of DCML cadences by type at +-1 beat (pooled tp / n)")
        for m, g in ct.groupby("method"):
            s = g.groupby("target")[["tp", "n_true"]].sum()
            out.append(f"  {m:18s} " + "  ".join(
                f"{k[4:]} {int(r.tp)}/{int(r.n_true)} ({r.tp / r.n_true:.2f})"
                if r.n_true else f"{k[4:]} 0/0" for k, r in s.iterrows()))
    tp = B[B["target"] == "type_pair"]
    if len(tp):
        for m, g in tp.groupby("method"):
            out.append(f"\nCadence-type confusion ({m}; rows DCML, cols predicted), "
                       f"matched +-1 beat")
            out.append(pd.crosstab(g["dcml"], g["pred_type"]).to_string())
            acc = (g["dcml"] == g["pred_type"]).groupby(g["dcml"]).mean().round(3)
            out.append("per-type accuracy: " + ", ".join(f"{k} {v}" for k, v in acc.items()))
    per = main[(main["tol"] == "1beat") & (main["target"] == "end")].pivot(
        index="movement", columns="method", values="F1")
    out.append("\nPer-movement end F1 at +-1 beat\n" + per.round(3).to_string())
    return "\n".join(out)


# --------------------------------------------------------------------------- comparators


def comparator_predictions(mv: dict) -> dict[str, tuple[list | None, list | None]]:
    from check_phrase_f05c import _cfg_from_fit, _prev_onset, cadence_bounds

    d = mv["d"]
    cst, cen = cadence_bounds(d, _cfg_from_fit())
    ob = d["onset_beats"]
    db = np.asarray(d["downbeats"], float)
    proxy_st = d["proxy"]
    return {
        "cadence": (cen, cst),
        "proxy_last_onset": (_prev_onset(ob, proxy_st[1:]) + [float(ob[-1])], None),
        "proxy": (None, proxy_st),
        "grid4": (db[3::4].tolist(), db[::4].tolist()),
        # ceiling of the phrase-end-based cadence recall: the DCML phrase ends themselves
        "oracle_dcml_ends": (list(mv["gt"]["ends"]), list(mv["gt"]["starts"])),
    }


def as_events(mv: dict, ends: list[float], starts: list[float]) -> list[dict]:
    ev = []
    for typ, xs in (("phrase_end", ends), ("phrase_start", starts)):
        for x in xs:
            bar, lab = to_bar_beat(mv["bars"], float(x))
            ev.append({"bar": bar, "beat": lab, "type": typ, "cadence": "none",
                       "confidence": 1.0})
    return ev


def run_comparators() -> None:
    M = movement_inputs()
    rows = []
    for mid, mv in M.items():
        for m, (en, st) in comparator_predictions(mv).items():
            rows += score_movement(mid, mv, en, st, None, m)
    B = pd.DataFrame(rows)
    B.to_csv(ART / "comparators.csv", index=False)
    txt = summarise(B)
    # harness check: detector -> (bar, beat) events -> scoring path -> F-05c rows
    ref = pd.read_csv(F05C / "boundaries.csv")
    bad = 0
    chk = []
    for mid, mv in M.items():
        en, st = comparator_predictions(mv)["cadence"]
        df, stats = map_events(as_events(mv, en, st), mv, propagate=False)
        pe = df.loc[df["type"] == "phrase_end", "beat"].tolist()
        ps = df.loc[df["type"] == "phrase_start", "beat"].tolist()
        assert np.allclose(pe, sorted(en)) and np.allclose(ps, sorted(set(st))), mid
        mine = pd.DataFrame(score_movement(mid, mv, pe, ps, None, "cadence_via_events"))
        r = ref[(ref["movement"] == mv["stem"]) & (ref["method"] == "cadence")]
        for _, row in r.iterrows():
            o = mine[(mine["target"] == row["target"]) & (mine["tol"] == row["tol"])]
            if o.empty:
                continue
            o = o.iloc[0]
            cols = ["tp", "n_pred", "n_true"] + (["F1"] if not row["target"].startswith("cad_")
                                                  else [])
            same = all(np.isclose(o[c], row[c], equal_nan=True) for c in cols)
            bad += not same
            chk.append(f"{mid} {mv['stem']} {row['target']:8s} {row['tol']:5s} "
                       f"F-05c tp/pred/true {int(row['tp'])}/{int(row['n_pred'])}/"
                       f"{int(row['n_true'])} here {int(o['tp'])}/{int(o['n_pred'])}/"
                       f"{int(o['n_true'])} {'OK' if same else 'MISMATCH'}")
        chk.append(f"{mid} mapping stats {stats}")
    txt += ("\n\nHarness check (detector via (bar, beat) events vs F-05c boundaries.csv): "
            + ("PASSED" if bad == 0 else f"FAILED ({bad} rows)") + "\n" + "\n".join(chk))
    (ART / "comparators_summary.txt").write_text(txt + "\n")
    print(txt)
    if bad:
        sys.exit(1)


# --------------------------------------------------------------------------- LLM


def run_llm(folder: Path, prefix: str = "llm") -> None:
    M = movement_inputs()
    comp = pd.read_csv(ART / "comparators.csv")
    rows, stats_all = [], {}
    variants = {"llm": {}, "llm_unsnapped": {"snap": False},
                "llm_conf50": {"min_conf": 0.5}, "llm_no_propagation": {"propagate": False}}
    for mid, mv in M.items():
        f = folder / f"{mid}.json"
        if not f.exists():
            print(f"missing {f}")
            continue
        ann = json.loads(f.read_text())
        assert ann.get("movement") == mid, f
        for vname, kw in variants.items():
            df, stats = map_events(ann.get("events", []), mv, **kw)
            e = df[df["type"] == "phrase_end"]
            s = df[df["type"] == "phrase_start"]
            types = dict(zip(e["beat"].round(6), e["cadence"], strict=True))
            cm = df[(df["type"] == "cadence")
                    | ((df["type"] == "phrase_end") & (df["cadence"] != "none"))]
            cm = cm.sort_values("confidence", ascending=False).drop_duplicates("beat")
            marks = dict(zip(cm["beat"].astype(float), cm["cadence"], strict=True))
            rows += score_movement(mid, mv, e["beat"].tolist(), s["beat"].tolist(), types, vname,
                                   marks if vname == "llm" else None)
            stats_all[f"{mid} {vname}"] = stats
        stats_all[f"{mid} recognised_piece"] = ann.get("recognised_piece")
    B = pd.concat([pd.DataFrame(rows), comp[comp["method"].isin(
        ["cadence", "proxy_last_onset", "proxy", "grid4", "oracle_dcml_ends"])]],
        ignore_index=True)
    B.to_csv(ART / f"{prefix}_scores.csv", index=False)
    txt = summarise(B)
    # primary + paired difference vs the detector
    rng = np.random.default_rng(SEED)
    e1 = B[(B["target"] == "end") & (B["tol"] == "1beat")].pivot(
        index="movement", columns="method", values="F1")
    prim, lo, hi = boot_mean(e1["llm"].to_numpy(), rng)
    dd, dlo, dhi = boot_mean((e1["llm"] - e1["cadence"]).to_numpy(), rng)
    verdict = "GO (>= 0.70)" if prim >= 0.70 else "NO-GO (< 0.70)"
    txt += (f"\n\nPRIMARY end F1 +-1 beat, mean over {len(e1)} movements: {prim:.3f} "
            f"[{lo:.3f}, {hi:.3f}] -> {verdict}\nLLM - detector: {dd:+.3f} [{dlo:+.3f}, "
            f"{dhi:+.3f}] ({'shown' if dlo > 0 else 'not shown'})\n"
            f"mapping stats: {json.dumps(stats_all, indent=1)}")
    (ART / f"{prefix}_summary.txt").write_text(txt + "\n")
    print(txt)


if __name__ == "__main__":
    if "--comparators" in sys.argv:
        run_comparators()
    if "--llm" in sys.argv:
        prefix = sys.argv[sys.argv.index("--prefix") + 1] if "--prefix" in sys.argv else "llm"
        run_llm(Path(sys.argv[sys.argv.index("--llm") + 1]), prefix)
