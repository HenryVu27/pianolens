"""BL-39: a narrower edge-bar policy for partial recordings.

Run: ``OMP_NUM_THREADS=1 uv run python scripts/eval_edge_narrow_bl39.py --set dev|heldout
[--workers 10] [--from-cache] [--tag NAME] [--limit-targets N] [--reachability N]``

Pre-registration: ``experiments/2026-10-11-BL-39-narrow-edge-policy/README.md`` (hash by anchor).

Builds on ``scripts/eval_edge_bars_bl37.py`` (truncation control, truth, played-bar table,
wrong-pitch injection) and ``scripts/eval_partial_bl36.py`` (no-regression rows). New here:

* every N / Na alignment carries, per bar, the number of missed notes that
  ``report.build.edge_outside_notes`` puts outside the recorded part of the edge bar, for each
  rule variant in ``VARIANTS``;
* two omission injections per copy, each realigned by N: ``omit_inner`` (3 correct notes of an
  edge bar that are not at the bar's first onset on a start side, or its last onset on an end
  side) and ``omit_lead`` (the bar's first 3 correct notes in score order on a start side, its
  last 3 on an end side);
* policies scored offline from the same tables: ``none`` (k = 0), ``k1`` (BL-37: every missed
  note in the first / last graded bar of a trimmed side is low confidence) and ``nar_<variant>``
  (only the outside missed notes).

Sets: ``dev`` = 3 targets per piece and family from the BL-36 dev, BL-36 held-out and BL-37
held-out pieces (44, all seen; experts from their caches); ``heldout`` = a new draw (seed 3939)
disjoint from every earlier draw, ``guard_jobs`` after the draw.
"""

from __future__ import annotations

import argparse
import dataclasses
import importlib.util
import json
import pickle
import sys
import warnings
import zlib
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "data" / "interim" / "bl39"
BL36 = REPO / "data" / "interim" / "bl36"
BL37 = REPO / "data" / "interim" / "bl37"
HELDOUT_SEED = 3939
OMIT_SEED = 39
N_OMIT = 3
MIN_CORRECT = 4  # an edge bar takes an injection when the clean copy has this many correct notes
DEV_TARGETS = 3
VARIANTS = {"score": ("score", 0.0), "score_le": ("score_le", 0.0), "time0": ("time", 0.0),
            "time05": ("time", 0.05), "time10": ("time", 0.10)}
REG_KINDS = ("start", "end", "both", "excerpt")
INJ = ("inj_wrong", "omit_inner", "omit_lead")


def _mod(name: str, file: str):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, REPO / "scripts" / file)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


def b36():
    return _mod("bl36", "eval_partial_bl36.py")


def b37():
    return _mod("bl37", "eval_edge_bars_bl37.py")


def _quiet() -> None:
    import logging

    warnings.filterwarnings("ignore")
    logging.disable(logging.WARNING)


# ----------------------------------------------------------------------------- jobs


def dev_jobs(limit: int = DEV_TARGETS) -> tuple[list[dict], list[dict]]:
    keys = ("piece", "piece_id", "family", "role", "order", "id", "midi", "score")
    jobs, experts = [], []
    for f in (BL36 / "dev_v2_rows.pkl", BL36 / "heldout_rows.pkl", BL37 / "heldout_rows.pkl"):
        for r in pickle.loads(f.read_bytes())["rows"]:
            if r["role"] == "expert":
                experts.append({**{k: r[k] for k in keys}, "suspect": r["suspect"],
                                "table": r["table"]})
            else:
                jobs.append({k: r[k] for k in keys})
    seen: dict[tuple, int] = {}
    keep = []
    for j in sorted(jobs, key=lambda j: (j["piece"], j["family"], j["order"], j["id"])):
        k = (j["piece"], j["family"])
        if seen.get(k, 0) < limit:
            keep.append(j)
            seen[k] = seen.get(k, 0) + 1
    return keep, experts


def exclusion_sets() -> dict[str, dict[str, set]]:
    sets = b37().exclusion_sets()
    r37 = pickle.loads((BL37 / "heldout_rows.pkl").read_bytes())["rows"]
    sets["pieces"]["BL-37 held-out"] = {r["piece"] for r in r37}
    sets["ids"]["BL-37"] = {str(r["id"]) for r in r37}
    return sets


def _flag(job: dict) -> dict:
    return b36().literal_repeat_flag(job)


def _expert(job: dict) -> dict:
    return b36().expert_one(job)


def heldout_jobs(workers: int) -> tuple[list[dict], dict]:
    import zipfile

    from pianolens.data.pianocore import DEFAULT_ROOT, RAW_PREFIX, RAW_ZIP, PianoCoRe, guard_jobs
    from pianolens.data.piece_ids import SCORE_VERSION_MISMATCH

    m = b36()
    idx = PianoCoRe().index
    tr = idx[idx["is_transcription"].astype(bool) & idx["capture_model"].isin(m.FAMILIES)]
    sets = exclusion_sets()
    excl = set().union(*sets["pieces"].values()) | set(SCORE_VERSION_MISMATCH)
    used = set().union(*sets["ids"].values())
    with zipfile.ZipFile(DEFAULT_ROOT / RAW_ZIP) as z:
        names = set(z.namelist())
    cnt = tr.groupby(["piece_id", "capture_model"]).size().unstack(fill_value=0)
    elig = []
    for pid, row in cnt.iterrows():
        if pid in excl or min(row.get(cm, 0) for cm in m.FAMILIES) < m.MIN_PER_FAMILY:
            continue
        sx = tr.loc[tr["piece_id"] == pid, "score_xml_path"].dropna().astype(str)
        sx = [s for s in sorted(set(sx)) if RAW_PREFIX + s in names]
        if len(sx) == 1:
            elig.append((pid, sx[0]))
    elig.sort()
    rng = np.random.default_rng(HELDOUT_SEED)
    order = [elig[i] for i in rng.permutation(len(elig))]
    probe = []
    for pid, sx in order:
        r0 = tr[(tr["piece_id"] == pid)].sort_values("id").iloc[0]
        probe.append({"piece": pid, "piece_id": pid, "score": sx,
                      "any_midi": str(r0["performance_midi_path"])})
    flags: dict[str, dict] = {}
    with ProcessPoolExecutor(workers) as ex:
        for f in ex.map(_flag, probe):
            flags[f["piece"]] = f
    rep = [p for p in order if flags[p[0]]["literal_repeats"]]
    non = [p for p in order if not flags[p[0]]["literal_repeats"]]
    n_rep = max(8, 16 - len(non))
    chosen = sorted(rep[:n_rep] + non[:16 - n_rep])
    jobs = []
    for pid, sx in chosen:
        for cm, fam in m.FAMILIES.items():
            r = tr[(tr["piece_id"] == pid) & (tr["capture_model"] == cm)
                   & ~tr["id"].astype(str).isin(used)].sort_values("id")
            perm = rng.permutation(len(r))
            for j, i in enumerate(perm[:m.N_EXPERTS + m.N_TARGETS]):
                jobs.append({"piece": pid, "piece_id": pid, "family": fam,
                             "role": "expert" if j < m.N_EXPERTS else "target", "order": j,
                             "id": str(r.iloc[i]["id"]),
                             "midi": str(r.iloc[i]["performance_midi_path"]), "score": sx})
    drawn = jobs
    jobs = guard_jobs(drawn, idx, label="BL-39 held-out")  # BL-35: after the seeded draw
    return jobs, {"n_eligible": len(elig), "n_literal_repeats_eligible": len(rep),
                  "n_drawn_jobs": len(drawn),
                  "guarded_ids": sorted({j["id"] for j in drawn} - {j["id"] for j in jobs}),
                  "flags": {p: flags[p] for p, _ in chosen}, "all_flags": flags,
                  "exclusions": {**{k: sorted(v) for k, v in sets["pieces"].items()},
                                 "SCORE_VERSION_MISMATCH": sorted(SCORE_VERSION_MISMATCH)}}


# ----------------------------------------------------------------------------- workers


def summ_n(ap, cr) -> dict:
    """``bl36._summ`` plus, per rule variant, missed notes outside the recorded part of each edge
    bar (label -> count)."""
    from pianolens.report.build import bar_labels, edge_outside_notes

    s = b36()._summ(ap, cr)
    labels = bar_labels(ap.score)
    sn = cr.score_notes
    mi = sn["measure_index"].to_numpy(int)
    miss = (sn["label"].astype(str).to_numpy() == "missed") & (mi >= 0)
    lc = {}
    for v, (basis, tol) in VARIANTS.items():
        out = edge_outside_notes(ap.score, cr, 1, basis, tol)
        cnt = np.bincount(mi[miss & out], minlength=len(labels))[:len(labels)]
        lc[v] = {labels[i]: int(n) for i, n in enumerate(cnt) if n}
    sab = _outside_second(ap.score, cr)
    cnt = np.bincount(mi[miss & sab], minlength=len(labels))[:len(labels)]
    lc["sab_le2"] = {labels[i]: int(n) for i, n in enumerate(cnt) if n}
    s["lc"] = lc
    return s


def _outside_second(score, cr) -> np.ndarray:
    """Sabotage (evaluation only, harm bite check): like ``score_le`` but up to the SECOND
    distinct matched onset of the edge bar (start side; the second-last on an end side)."""
    from pianolens.report.build import edge_bars

    sn = cr.score_notes
    out = np.zeros(len(sn), bool)
    n_notes = cr.bars["n_score_notes"].to_numpy(int)
    rows = edge_bars(score, n_notes, 1)
    if not rows:
        return out
    rs = (getattr(score, "meta", None) or {}).get("recorded_span") or {}
    pos = {d.get("position") for d in rs.get("not_recorded") or []}
    graded = [i for i, n in enumerate(n_notes) if n > 0]
    mi = sn["measure_index"].to_numpy(int)
    lab = sn["label"].astype(str).to_numpy()
    q = sn["onset_quarter"].to_numpy(float)
    for r in rows:
        inb = mi == r
        matched = inb & np.isin(lab, ("correct", "wrong_pitch"))
        if not matched.any():
            out |= inb
            continue
        u = np.unique(q[matched])
        if "start" in pos and r == graded[0]:
            out |= inb & (q <= u[min(1, len(u) - 1)]) & ~matched
        if "end" in pos and r == graded[-1]:
            out |= inb & (q >= u[max(len(u) - 2, 0)]) & ~matched
    return out


def omit_edges(perf, cr, labels: list[str], edges: list[tuple[str, str]], rng, mode: str):
    """Delete ``N_OMIT`` correct performed notes in each edge bar (label, side): ``inner`` = notes
    not at the bar's first onset (start side) or last onset (end side), chosen at random;
    ``lead`` = the first (last) ``N_OMIT`` correct notes in score order. Only notes still in
    ``perf`` (the cut copy) count. Returns (performance copy, injected bar labels)."""
    sn = cr.score_notes
    ids = set(perf.notes["id"].astype(str))
    corr = sn[(sn["label"] == "correct") & (sn["measure_index"] >= 0)]
    corr = corr[corr["performance_id"].astype(str).isin(ids)]
    drop, done = set(), []
    for lab, side in edges:
        i = labels.index(lab)
        g = corr[corr["measure_index"] == i]
        if len(g) < MIN_CORRECT:
            continue
        q = g["onset_quarter"].to_numpy(float)
        pids = g["performance_id"].astype(str).to_numpy()
        if mode == "lead":
            order = np.lexsort((pids, q if side == "start" else -q))
            pick = pids[order[:N_OMIT]]
        else:
            bound = q.min() if side == "start" else q.max()
            cand = pids[q != bound]
            if len(cand) < N_OMIT:
                continue
            pick = rng.choice(np.sort(cand), N_OMIT, replace=False)
        drop |= set(pick.tolist())
        done.append(lab)
    notes = perf.notes[~np.isin(perf.notes["id"].astype(str), sorted(drop))]
    return dataclasses.replace(perf, notes=notes.copy(),
                               performance_id=f"{perf.performance_id}#omit_{mode}"), done


def target_one(job: dict) -> dict:
    _quiet()
    from pianolens.align import align_performance
    from pianolens.features.correctness import correctness

    m, m37 = b36(), b37()
    sc, perf = m37.b18b()._load(job)
    apc = align_performance(sc, perf)
    crc = correctness(apc)
    apn = align_performance(sc, perf, partial=True)
    crn = correctness(apn)
    rs = apn.score.meta["recorded_span"]
    out = {**job, "C": m._summ(apc, crc), "N": summ_n(apn, crn),
           "whole_N": bool(rs["whole"]), "refined_N": bool(rs.get("refined")),
           "whole_identical": bool(rs["whole"] and not rs.get("refined")
                                   and m37._same(apc, apn, crc, crn))}
    out["suspect"] = out["C"]["suspect"]
    if out["suspect"]:
        return out
    labels = out["C"]["labels"]
    out["bar_class"] = m.bar_classes(apc.score)
    found = m._found(out["C"]["table"])
    cnts = m37._bars_counts(out["C"]["table"])
    variant = out["C"]["variant"] or "auto"
    rng = np.random.default_rng([m.TRUNC_SEED, zlib.crc32(job["id"].encode())])
    irng = np.random.default_rng([m37.INJECT_SEED, zlib.crc32(job["id"].encode())])
    orng = np.random.default_rng([OMIT_SEED, zlib.crc32(job["id"].encode())])
    out["cuts"] = {}
    notes = apc.performance.notes
    for kind in list(m.KINDS) + ["short"]:
        win = m37.short_window(crc, rng) if kind == "short" else m.cut_window(crc, kind, rng)
        if win is None:
            continue
        lo, hi = win
        keep = (notes["onset_sec"] >= lo) & (notes["onset_sec"] < hi)
        if keep.sum() < 20:
            continue
        tp = dataclasses.replace(apc.performance, notes=notes[keep].copy(),
                                 performance_id=f"{apc.performance.performance_id}#{kind}")
        tr = m.truth(crc, labels, lo, hi)
        removed = set(notes["id"][~keep].astype(str))
        played = m37.played_table(labels, tr, found, removed, out["C"]["perf_bar"])
        c = {"t_lo": lo, "t_hi": hi, "truth": tr, "played": played}
        for meth, kw in (("C", {"repeats": variant}), ("N", {"repeats": variant, "partial": True}),
                         ("Na", {"partial": True})):
            ap2 = align_performance(sc, tp, **kw)
            cr2 = correctness(ap2)
            c[meth] = m._summ(ap2, cr2) if meth == "C" else summ_n(ap2, cr2)
        if kind in REG_KINDS:
            edges = [(b, v["side"]) for b, v in played.items() if v["d"] == 0]
            ok = [b for b, _ in edges if cnts.get(b, (0, 0, 1, 0))[2] == 0]
            if ok:
                ip, done = m37.inject_edges(tp, crc, labels, ok, irng)
                if done:
                    api = align_performance(sc, ip, repeats=variant, partial=True)
                    c["inj_wrong"] = {"bars": done, "N": summ_n(api, correctness(api))}
            okside = [(b, s) for b, s in edges if b in ok]
            for mode in ("inner", "lead"):
                op, done = omit_edges(tp, crc, labels, okside, orng, mode)
                if done:
                    apo = align_performance(sc, op, repeats=variant, partial=True)
                    c[f"omit_{mode}"] = {"bars": done, "N": summ_n(apo, correctness(apo))}
        out["cuts"][kind] = c
    return out


# ----------------------------------------------------------------------------- evaluation


def tiers_lc(summ: dict, experts, policy: str) -> dict[str, str]:
    """Rule P tiers of a summary's bar table under an edge policy: ``none``; ``k1`` (every
    missed note of N's first / last graded bar on a trimmed side is low confidence);
    ``nar_<variant>`` (only the outside missed notes). Runs use the real missed counts."""
    m37 = b37()
    table = summ["table"]
    tr = b36().bl27().tiers_runs(table, experts, 0)
    tiers = dict(zip(tr["label"], tr["tier"], strict=True))
    if policy == "none":
        return tiers
    if policy in ("k1", "k2"):
        lc = {b: int(table.loc[table["label"] == b, "n_missed"].iat[0])
              for b in m37.span_edges(summ, int(policy[1]))}
    else:
        lc = (summ.get("lc") or {}).get(policy.removeprefix("nar_"), {})
    lc = {b: n for b, n in lc.items() if n}
    if not lc:
        return tiers
    t = table.copy()
    for b, n in lc.items():
        sel = t["label"] == b
        t.loc[sel, "n_missed"] = (t.loc[sel, "n_missed"] - n).clip(lower=0)
    b18 = b36().bl27()._mod("bl18", "calibrate_strong_tier_bl18.py")
    tm = b18.tiers(t, experts, "R1(0)", None)
    in_run = dict(zip(tr["label"], tr["in_run"], strict=True))
    for lab, tier in zip(tm["label"], tm["tier"], strict=True):
        if lab in lc and not in_run.get(lab, False):
            tiers[lab] = tier
    return tiers


def policies() -> list[str]:
    return ["none", "k1", "k2"] + [f"nar_{v}" for v in VARIANTS] + ["nar_sab_le2"]


def _experts(rows: list[dict]) -> dict[tuple, list]:
    ex: dict[tuple, list] = {}
    for r in sorted((r for r in rows if r["role"] == "expert" and not r["suspect"]),
                    key=lambda r: r["order"]):
        ex.setdefault((r["piece"], r["family"]), []).append(r["table"])
    return ex


def _max_expert(ex: list[pd.DataFrame], lab: str, col: str) -> int:
    v = [int(t.loc[t["label"] == lab, col].max()) for t in ex if (t["label"] == lab).any()]
    return max(v) if v else 0


def tables(rows: list[dict]) -> dict[str, pd.DataFrame]:
    """bars (played, cut and not-heard bars of every copy, tiers per policy for N and Na; tiers
    of C and the clean copy), inject (per injected bar and type, tiers per policy) and natural
    (per natural target, strong / notable+ counts per policy outside runs)."""
    experts = _experts(rows)
    pols = policies()
    bars, inj, nat = [], [], []
    for r in rows:
        if r["role"] != "target" or r["suspect"]:
            continue
        ex = experts.get((r["piece"], r["family"]), [])
        clean = tiers_lc(r["C"], ex, "none")
        # natural (untouched) copy
        tC = b36().bl27().tiers_runs(r["C"]["table"], ex, 0)
        d = {"piece": r["piece"], "family": r["family"], "id": r["id"],
             "whole_N": r["whole_N"], "evidently_full": _evidently_full(r["C"]["table"])}
        outC = tC[~tC["in_run"]]
        d["n_C"], d["strong_C"] = len(outC), int((outC["tier"] == "strong").sum())
        d["np_C"] = int((outC["tier"] != "none").sum())
        trN = b36().bl27().tiers_runs(r["N"]["table"], ex, 0)
        out_lab = set(trN.loc[~trN["in_run"], "label"])
        for p in pols:
            t = tiers_lc(r["N"], ex, p)
            vals = [t[b] for b in out_lab if b in t]
            d[f"n_N_{p}"] = len(vals)
            d[f"strong_N_{p}"] = sum(v == "strong" for v in vals)
            d[f"np_N_{p}"] = sum(v != "none" for v in vals)
        nat.append(d)
        for kind, c in (r.get("cuts") or {}).items():
            tC2 = tiers_lc(c["C"], ex, "none")
            tN = {p: tiers_lc(c["N"], ex, p) for p in pols}
            tNa = {p: tiers_lc(c["Na"], ex, p) for p in pols}
            for b, st in c["truth"].items():
                if st == "heard" and b in c["played"]:
                    v = c["played"][b]
                    dd, lost = v["d"], v["lost"]
                elif st == "cut":
                    dd, lost = -1, True
                elif st == "not_heard":
                    dd, lost = -2, True
                else:
                    continue
                row = {"piece": r["piece"], "family": r["family"], "id": r["id"], "kind": kind,
                       "label": b, "d": dd, "lost": lost, "clean": clean.get(b, "none"),
                       "C": tC2.get(b, "none")}
                for p in pols:
                    row[f"N_{p}"] = tN[p].get(b, "none")
                    row[f"Na_{p}"] = tNa[p].get(b, "none")
                bars.append(row)
            for typ in INJ:
                if typ not in c:
                    continue
                s = c[typ]["N"]
                ti = {p: tiers_lc(s, ex, p) for p in pols}
                col = "n_wrong_pitch" if typ == "inj_wrong" else "n_missed"
                for b in c[typ]["bars"]:
                    row = {"piece": r["piece"], "family": r["family"], "id": r["id"],
                           "kind": kind, "type": typ, "label": b,
                           "max_expert": _max_expert(ex, b, col),
                           "n_edge": b in b37().span_edges(s, 1)}
                    for p in pols:
                        row[f"N_{p}"] = ti[p].get(b, "none")
                    inj.append(row)
    return {"bars": pd.DataFrame(bars), "inject": pd.DataFrame(inj), "natural": pd.DataFrame(nat)}


def _evidently_full(table: pd.DataFrame) -> bool:
    g = table[table["n_score_notes"] > 0]
    fr = (g["n_missed"] / g["n_score_notes"]).to_numpy(float)
    k = max(3, int(np.ceil(0.05 * len(fr))))
    return bool(len(fr) >= 2 * k and np.mean(fr[:k] < 0.5) > 0.5
                and np.mean(fr[-k:] < 0.5) > 0.5)


# ----------------------------------------------------------------------------- rows

#: Registered (README "Pre-registration"). The candidate and its bars; k = 0 / k = 1 are shown.
CANDIDATE = "nar_score_le"
E1_BAND = (-1.0, 1.5)
E2_MAX = 1.5
D1_MIN, D2_MIN = -5.0, -8.0
O1_MIN = -8.0  # inner omissions, notable or strong, candidate minus none
O2_MIN = -50.0  # lead omissions (the disclosed cost), notable or strong, candidate minus none
T2_MAX = 0.03
H1_STRONG, H1_NP = 0.15, 0.30


def _diff(df: pd.DataFrame, a: str, b: str, val=("strong",)) -> pd.Series:
    if not len(df):
        return pd.Series(dtype=float)
    g = df.assign(x=df[a].isin(val).astype(float) - df[b].isin(val).astype(float))
    return 100 * g.groupby("piece")["x"].mean()


def _rate(df: pd.DataFrame, a: str, val=("strong",)) -> pd.Series:
    if not len(df):
        return pd.Series(dtype=float)
    return 100 * df.assign(x=df[a].isin(val).astype(float)).groupby("piece")["x"].mean()


def policy_rows(bars: pd.DataFrame, inj: pd.DataFrame, nat: pd.DataFrame, p: str) -> dict:
    """Every row for policy ``p`` (N): value = mean over pieces, with pass against the bars."""
    col = f"N_{p}"
    reg = bars[bars["kind"].isin(REG_KINDS)]
    e = reg[(reg["d"] == 0) & (~reg["lost"])]
    cut = reg[reg["d"] == -1]
    nh = reg[reg["d"] == -2]
    i = inj[inj["kind"].isin(REG_KINDS)] if len(inj) else inj
    iw = i[(i["type"] == "inj_wrong") & (i["max_expert"] <= 1)] if len(i) else i
    oi = i[(i["type"] == "omit_inner") & (i["max_expert"] <= 1)] if len(i) else i
    ol = i[(i["type"] == "omit_lead") & (i["max_expert"] <= 1)] if len(i) else i
    out = {}

    def put(name, per, lo=None, hi=None, absval=None):
        v = float(per.mean()) if len(per) else np.nan
        ok = (lo is None or v >= lo) and (hi is None or v <= hi) and \
            (absval is None or abs(v) <= absval)
        out[name] = {"value": v, "pass": bool(ok), "n_pieces": int(len(per)),
                     "per_piece": {k: float(x) for k, x in per.items()}}

    put("E1", _diff(e, col, "clean"), *E1_BAND)
    put("E2", _diff(cut, col, "clean"), None, E2_MAX)
    put("D1", _diff(iw, col, "N_none"), D1_MIN)
    put("D2", _diff(iw, col, "N_none", ("strong", "notable")), D2_MIN)
    put("O1", _diff(oi, col, "N_none", ("strong", "notable")), O1_MIN)
    put("O2", _diff(ol, col, "N_none", ("strong", "notable")), O2_MIN)
    g = nh.assign(x=nh[col] != "none").groupby("piece")["x"].mean() if len(nh) else \
        pd.Series(dtype=float)
    put("T2", g, None, T2_MAX)
    gna = nh.assign(x=nh[f"Na_{p}"] != "none").groupby("piece")["x"].mean() if len(nh) else \
        pd.Series(dtype=float)
    put("R2", gna, None, T2_MAX)
    ef = nat[nat["evidently_full"]]
    for fam in ("transkun", "aria_amt"):
        f = ef[ef["family"] == fam].groupby("piece")[
            ["strong_C", "n_C", "np_C", f"strong_N_{p}", f"n_N_{p}", f"np_N_{p}"]].sum()
        put(f"H1_strong:{fam}", 100 * (f[f"strong_N_{p}"] / f[f"n_N_{p}"]
                                       - f["strong_C"] / f["n_C"]), absval=H1_STRONG)
        put(f"H1_np:{fam}", 100 * (f[f"np_N_{p}"] / f[f"n_N_{p}"] - f["np_C"] / f["n_C"]),
            absval=H1_NP)
    out["info"] = {
        "edge_strong": float(_rate(e, col).mean()), "edge_strong_uncut": float(_rate(
            e, "clean").mean()), "cut_strong": float(_rate(cut, col).mean()),
        "cut_strong_uncut": float(_rate(cut, "clean").mean()),
        "inj_wrong_strong": float(_rate(iw, col).mean()),
        "inj_wrong_np": float(_rate(iw, col, ("strong", "notable")).mean()),
        "omit_inner_np": float(_rate(oi, col, ("strong", "notable")).mean()),
        "omit_inner_strong": float(_rate(oi, col).mean()),
        "omit_lead_np": float(_rate(ol, col, ("strong", "notable")).mean()),
        "omit_lead_strong": float(_rate(ol, col).mean()),
        "n_bars": {"edge": int(len(e)), "cut": int(len(cut)), "inj_wrong": int(len(iw)),
                   "omit_inner": int(len(oi)), "omit_lead": int(len(ol))}}
    return out


ROWS = ("E1", "E2", "D1", "D2", "O1", "O2", "T2", "R2", "H1_strong:transkun",
        "H1_np:transkun", "H1_strong:aria_amt", "H1_np:aria_amt")


def verdict(t: dict[str, pd.DataFrame], e36: dict, whole: dict) -> dict:
    rows = policy_rows(t["bars"], t["inject"], t["natural"], CANDIDATE)
    failed = [k for k in ROWS if not rows[k]["pass"]]
    for k in ("T1_acc_N", "T3_agree_N", "R1_acc_Na", "R3_agree_eq_Na", "H2_whole_share",
              "H2_not_recorded_share"):
        if not e36["criteria"][k]["pass"]:
            failed.append(k)
    if whole["n_whole_identical"] != whole["n_whole_unrefined"]:
        failed.append("W1")
    return {"pass": not failed, "failed": failed,
            "adopted": CANDIDATE if not failed else "none (k = 0)"}


def loo(t: dict[str, pd.DataFrame], p: str) -> dict:
    out = {}
    for pc in sorted(set(t["bars"]["piece"])):
        sub = {k: v[v["piece"] != pc] if len(v) else v for k, v in t.items()}
        r = policy_rows(sub["bars"], sub["inject"], sub["natural"], p)
        out[pc] = {k: r[k]["value"] for k in ROWS}
    return out


def reachability(t: dict[str, pd.DataFrame], p: str, n: int, n_pieces: int = 16) -> dict:
    rng = np.random.default_rng(0)
    pieces = sorted(set(t["bars"]["piece"]))
    by = {k: {pc: g for pc, g in v.groupby("piece")} for k, v in t.items() if len(v)}
    hits: dict[str, int] = {}
    allp = 0
    for _ in range(n):
        pick = rng.choice(pieces, n_pieces, replace=True)
        sub = {k: pd.concat([by[k][pc].assign(piece=f"{pc}#{j}") for j, pc in enumerate(pick)
                             if pc in by[k]]) for k in by}
        r = policy_rows(sub["bars"], sub["inject"], sub["natural"], p)
        ok = True
        for k in ROWS:
            hits[k] = hits.get(k, 0) + int(r[k]["pass"])
            ok &= r[k]["pass"]
        allp += int(ok)
    return {"n": n, "pass_all": allp / n, "rows": {k: v / n for k, v in hits.items()}}


def evaluate(rows: list[dict], reach: int = 0) -> dict:
    m = b36()
    targets = [r for r in rows if r["role"] == "target"]
    ok = [r for r in targets if not r["suspect"]]
    rows36 = [{**r, "cuts": {k: v for k, v in r["cuts"].items() if k in REG_KINDS}}
              if r["role"] == "target" and r.get("cuts") else r for r in rows]
    e36 = m.evaluate(rows36)
    t = tables(rows)
    whole = {"n_whole_N": sum(r["whole_N"] for r in ok),
             "n_whole_unrefined": sum(r["whole_N"] and not r["refined_N"] for r in ok),
             "n_whole_identical": sum(r["whole_identical"] for r in ok)}
    out = {"n_targets": len(ok), "n_targets_suspect": len(targets) - len(ok), "whole": whole,
           "bl36_criteria": {k: v["value"] for k, v in e36["criteria"].items()},
           "bl36_pass": {k: v.get("pass") for k, v in e36["criteria"].items()},
           "policies": {p: policy_rows(t["bars"], t["inject"], t["natural"], p)
                        for p in policies()},
           "verdict": verdict(t, e36, whole), "loo": loo(t, CANDIDATE)}
    if reach:
        out["reachability"] = {p: reachability(t, p, reach)
                               for p in ("none", "k1", "k2", "nar_sab_le2", CANDIDATE)}
    out["_tables"] = {**t, "copies": e36["_tables"]["copies"],
                      "natural36": e36["_tables"]["natural"]}
    return out


# ----------------------------------------------------------------------------- main


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", choices=("dev", "heldout"), required=True)
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--from-cache", action="store_true")
    ap.add_argument("--tag", default="")
    ap.add_argument("--limit-targets", type=int, default=DEV_TARGETS)
    ap.add_argument("--reachability", type=int, default=0)
    ap.add_argument("--draw-only", action="store_true")
    args = ap.parse_args()
    _quiet()
    OUT.mkdir(parents=True, exist_ok=True)
    stem = args.set + (f"_{args.tag}" if args.tag else "")
    cache = OUT / f"{stem}_rows.pkl"
    if args.from_cache:
        blob = pickle.loads(cache.read_bytes())
    else:
        info: dict = {}
        if args.set == "dev":
            jobs, rows = dev_jobs(args.limit_targets)
        else:
            jobs, info = heldout_jobs(args.workers)
            (OUT / "heldout_draw.json").write_text(json.dumps(
                {k: v for k, v in info.items() if k != "all_flags"}, indent=1, default=str))
            if args.draw_only:
                return
            rows = []
        print(len(jobs), "jobs", flush=True)
        failed = []
        with ProcessPoolExecutor(args.workers) as ex:
            futs = {ex.submit(_expert if j["role"] == "expert" else target_one, j): j
                    for j in jobs}
            for k, fu in enumerate(as_completed(futs)):
                try:
                    rows.append(fu.result())
                except Exception as e:  # noqa: BLE001 - count failures
                    failed.append((futs[fu]["id"], repr(e)[:300]))
                if k % 25 == 0:
                    print("done", k, len(failed), flush=True)
        blob = {"rows": rows, "failed": failed,
                "info": {k: v for k, v in info.items() if k != "all_flags"}}
        cache.write_bytes(pickle.dumps(blob))
    res = evaluate(blob["rows"], args.reachability)
    for k, t in res.pop("_tables").items():
        t.to_csv(OUT / f"{stem}_{k}.csv", index=False)
    summ = {"set": args.set, "tag": args.tag, "failed": blob.get("failed", []),
            "info": blob.get("info"), **res}
    (OUT / f"{stem}_summary.json").write_text(json.dumps(summ, indent=1, default=float))
    print(json.dumps({"failed": summ["failed"], "verdict": summ["verdict"],
                      "whole": summ["whole"]}, indent=1, default=float))


if __name__ == "__main__":
    main()
