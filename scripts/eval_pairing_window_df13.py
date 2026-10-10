"""DF-13: wrong-pitch pairing window rules on transcribed input (dev and held-out).

Run: ``OMP_NUM_THREADS=1 uv run python scripts/eval_pairing_window_df13.py --set dev|heldout
[--workers 10] [--from-cache]``

Pre-registration: ``docs/specs/correctness-validation.md``, section "Pre-registration DF-13"
(SHA-256 in ``experiments/2026-10-10-DF-13-pairing-window/artifacts/prereg_sha256.txt``).

Window rules (``features.correctness``, ``wrong_pitch_window``): ``fixed`` (100 ms, baseline),
``wide`` (200 ms), ``tempo`` (0.4 quarter at the local tempo, 0.1-0.3 s), ``error`` (2 x the
local onset-estimate error, 0.1-0.3 s). Every job is aligned once per copy; every rule labels the
same alignment, and each target is checked against expert tables labelled with the same rule.

Sets:

* ``dev``: the BL-18b pieces, experts and targets (``bl18b_tables.pkl`` job list), with the
  BL-18b D-08 copy (seed 1) and targeted copy (seed 2; injections may collide with pitches
  written in the same bar; collisions are flagged).
* ``heldout``: a new draw (seed 1010) of 16 PianoCoRe pieces with at least 25 transcriptions in
  each family and one score, excluding Henry's 5, the BL-18 T2 and the BL-18b pieces; 15 experts
  and 10 targets per piece and family, excluding every transcription id used before. Targeted
  copies avoid pitches written in the injected bar (collision fix).

Outputs (gitignored): ``data/interim/df13/<set>_rows.pkl`` and ``<set>_summary.json``.
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
CAL = REPO / "data" / "interim" / "reports" / "calibration"
OUT = REPO / "data" / "interim" / "df13"
HENRY = REPO / "data" / "interim" / "henry_takes"
FAMILIES = {"Transkun V2": "transkun", "Aria-AMT": "aria_amt"}
RULES = ("fixed", "wide", "tempo", "error")
CANDIDATES = ("tempo", "error", "wide")  # pre-registered order: primary first
HELDOUT_SEED = 1010
N_PIECES = 16  # held-out draw (dev keeps the 12 BL-18b pieces)
N_EXPERTS = 15
N_TARGETS = 10
MIN_PER_FAMILY = 25
D08_SEED = 1
TARGETED_SEED = 2


def _load_module(name: str, file: str):
    spec = importlib.util.spec_from_file_location(name, REPO / "scripts" / file)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _bl18b():
    return _load_module("bl18b", "calibrate_strong_tier_bl18b.py")


def _quiet() -> None:
    import logging

    warnings.filterwarnings("ignore")
    logging.disable(logging.WARNING)


# ----------------------------------------------------------------------------- draw


def dev_jobs() -> list[dict]:
    rows = pickle.loads((CAL / "bl18b_tables.pkl").read_bytes())["rows"]
    keys = ("piece", "piece_id", "family", "role", "order", "id", "midi", "score")
    return [{k: r[k] for k in keys} for r in rows]


def heldout_jobs() -> tuple[list[dict], int]:
    import zipfile

    from pianolens.data.pianocore import DEFAULT_ROOT, RAW_PREFIX, RAW_ZIP, PianoCoRe

    idx = PianoCoRe().index
    tr = idx[idx["is_transcription"].astype(bool) & idx["capture_model"].isin(FAMILIES)]
    meta = json.loads((HENRY / "scores" / "scores.json").read_text())
    excl_pieces = {m["piece_id"] for m in meta.values()}
    excl_pieces |= set(json.loads((CAL / "bl18_summary.json").read_text())["t2_pieces"])
    b18b = pickle.loads((CAL / "bl18b_tables.pkl").read_bytes())["rows"]
    excl_pieces |= {r["piece"] for r in b18b}
    floor = pickle.loads((CAL / "f08c_floor_tables.pkl").read_bytes())
    b18 = pickle.loads((CAL / "bl18_tables.pkl").read_bytes())
    used = ({str(r["ref_id"]) for r in floor} | {str(r["id"]) for r in b18}
            | {str(r["id"]) for r in b18b})
    with zipfile.ZipFile(DEFAULT_ROOT / RAW_ZIP) as z:
        names = set(z.namelist())
    cnt = tr.groupby(["piece_id", "capture_model"]).size().unstack(fill_value=0)
    elig = []
    for pid, row in cnt.iterrows():
        if pid in excl_pieces or min(row.get(cm, 0) for cm in FAMILIES) < MIN_PER_FAMILY:
            continue
        sx = tr.loc[tr["piece_id"] == pid, "score_xml_path"].dropna().astype(str)
        sx = [s for s in sorted(set(sx)) if RAW_PREFIX + s in names]
        if len(sx) == 1:
            elig.append((pid, sx[0]))
    elig.sort()
    rng = np.random.default_rng(HELDOUT_SEED)
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


# ----------------------------------------------------------------------------- labelling


def label_all(ap) -> dict:
    """``correctness`` of one alignment under every rule."""
    from pianolens.features.correctness import correctness

    return {r: correctness(ap, wrong_pitch_window=r) for r in RULES}


def clean_counts(cr, fast: np.ndarray) -> dict:
    """Wrong-pitch labels on a clean transcription (false-pairing proxy)."""
    w = cr.notes["label"].astype(str).to_numpy() == "wrong_pitch"
    return {"n_wrong": int(w.sum()), "n_wrong_fast": int((w & fast).sum()),
            "n_fast": int(fast.sum()), "n_graded": int(cr.summary["n_score_notes"])}


def note_outcomes(crs: dict, injected: dict[str, tuple[str, int]], bar_pitches: dict[int, set],
                  intended_bar: dict[str, int], fast: dict[str, bool]) -> pd.DataFrame:
    """Per injected wrong note (performed id -> (intended score id, new pitch)) and rule: label,
    partner, intended score note's label, collision and fast-run flags."""
    rows = []
    for rule, cr in crs.items():
        n = cr.notes.set_index("performance_id")
        s = cr.score_notes.set_index("score_id")
        for pid, (sid, newp) in injected.items():
            if pid not in n.index:
                continue
            r = n.loc[pid]
            ib = intended_bar.get(sid, -1)
            rows.append({"rule": rule, "pid": pid, "sid": sid, "label": str(r["label"]),
                         "partner_ok": str(r["score_id"]) == sid,
                         "same_bar": int(r["measure_index"]) == ib,
                         "intended_label": str(s.loc[sid, "label"]) if sid in s.index else "?",
                         "collision": newp in bar_pitches.get(ib, set()),
                         "fast": bool(fast.get(pid, False))})
    return pd.DataFrame(rows)


def targeted_copy(ap, cr, labels, table, experts, seed: int, avoid_bar_pitches: bool):
    """Targeted copy of BL-18b (``calibrate_strong_tier_bl18b.targeted_copy``: up to 10 spaced
    eligible bars, each with exactly 3 wrong pitches ±1 / ±2). With ``avoid_bar_pitches`` (DF-13
    collision fix) a new pitch may also not be any pitch written in that bar of the score; the
    rest of the procedure is unchanged. Returns (performance copy, chosen bar labels)."""
    m = _bl18b()
    if not avoid_bar_pitches:
        return m.targeted_copy(ap, cr, labels, table, experts, seed)
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
    sn = cr.score_notes
    written = {int(b): set(g["pitch"].astype(int)) for b, g in sn.groupby("measure_index")}
    n = cr.notes
    corr = n[(n["label"] == "correct") & (n["measure_index"] >= 0)]
    by_bar = {int(b): [pos[str(p)] for p in g["performance_id"] if str(p) in pos]
              for b, g in corr.groupby("measure_index")}
    elig = []
    for i, lab in enumerate(labels):
        w = ex_wrong.get(lab, [])
        if (lab_count[lab] == 1 and len(w) >= cal.EXPERT_CHECK_MIN_REFS and max(w) <= 1
                and table["n_score_notes"].iat[i] > 0 and table["n_wrong_pitch"].iat[i] == 0
                and i not in in_run and len(by_bar.get(i, [])) >= m.TARGETED_WRONG):
            elig.append(i)
    deltas = np.array([d for d, _ in m.TARGETED_DELTAS])
    pw = np.array([w for _, w in m.TARGETED_DELTAS])
    pw = pw / pw.sum()
    chosen = []
    for i in rng.permutation(elig):
        if len(chosen) >= m.N_TARGETED_BARS:
            break
        if any(abs(int(i) - c) < m.TARGETED_GAP for c in chosen):
            continue
        done = {}
        for k in rng.permutation(by_bar[int(i)]):
            if len(done) >= m.TARGETED_WRONG:
                break
            cp = set(notes["pitch"][chord == chord[k]].tolist())
            t0 = float(notes["onset_sec"][k])
            t1 = t0 + float(notes["duration_sec"][k])
            for _ in range(20):
                new = int(notes["pitch"][k]) + int(rng.choice(deltas, p=pw))
                if (_PIANO_LO <= new <= _PIANO_HI and new not in cp
                        and new not in written.get(int(i), set())
                        and not _same_pitch_busy(notes, new, t0, t1)):
                    done[int(k)] = (int(notes["pitch"][k]), new)
                    notes["pitch"][k] = new
                    break
        if len(done) == m.TARGETED_WRONG:
            chosen.append(int(i))
        else:  # revert a bar that cannot take exactly 3 wrong pitches
            for k, (old, _) in done.items():
                notes["pitch"][k] = old
    perf = dataclasses.replace(ap.performance, notes=notes,
                               performance_id=f"{ap.performance.performance_id}#targeted")
    return perf, [labels[i] for i in sorted(chosen)]


# ----------------------------------------------------------------------------- workers


def run_expert(job: dict) -> dict:
    _quiet()
    from pianolens.align import align_performance
    from pianolens.report.build import bar_error_table, bar_labels, fast_run_notes

    sc, perf = _bl18b()._load(job)
    ap = align_performance(sc, perf)
    crs = label_all(ap)
    labels = bar_labels(ap.score)
    fast = fast_run_notes(crs["fixed"].notes)
    return {**job, "suspect": bool(crs["fixed"].summary["alignment_suspect"]),
            "tables": {r: bar_error_table(c, labels) for r, c in crs.items()},
            "clean": {r: clean_counts(c, fast) for r, c in crs.items()}}


def _copy_outcomes(ap_copy, crs_copy, injected, cr_clean) -> pd.DataFrame:
    from pianolens.report.build import fast_run_notes

    sn = cr_clean.score_notes
    bar_p = {int(b): set(g["pitch"].astype(int)) for b, g in sn.groupby("measure_index")}
    ib = dict(zip(sn["score_id"].astype(str), sn["measure_index"].astype(int), strict=True))
    fr = fast_run_notes(crs_copy["fixed"].notes)
    fast = dict(zip(crs_copy["fixed"].notes["performance_id"].astype(str), fr, strict=True))
    return note_outcomes(crs_copy, injected, bar_p, ib, fast)


def run_target(job: dict, experts_fixed: list[pd.DataFrame], avoid: bool) -> dict:
    _quiet()
    from pianolens.align import align_performance
    from pianolens.data.perturb import MistakeSpec, perturb
    from pianolens.report.build import bar_error_table, bar_labels, fast_run_notes

    m = _bl18b()
    sc, perf = m._load(job)
    ap = align_performance(sc, perf)
    crs = label_all(ap)
    cr = crs["fixed"]
    labels = bar_labels(ap.score)
    fast = fast_run_notes(cr.notes)
    out = {**job, "suspect": bool(cr.summary["alignment_suspect"]),
           "tables": {r: bar_error_table(c, labels) for r, c in crs.items()},
           "clean": {r: clean_counts(c, fast) for r, c in crs.items()}}
    if out["suspect"]:
        return out
    # D-08 copy (as BL-18b)
    pp, lab = perturb(ap.performance, ap.alignment, MistakeSpec(rate=m.D08_RATE), seed=D08_SEED,
                      require_exact_timing=False)
    sn = cr.score_notes
    bar_of = dict(zip(sn["score_id"].astype(str), sn["measure_index"].astype(int), strict=True))
    wn = lab.notes[lab.notes["injected"] & (lab.notes["label"] == "wrong_pitch")]
    ids = set(wn["score_id"].astype(str))
    ids |= set(lab.missed.loc[lab.missed["injected"], "score_id"].astype(str))
    out["injected_bars"] = sorted({labels[bar_of[s]] for s in ids if bar_of.get(s, -1) >= 0})
    ap2 = align_performance(ap.score, pp)
    crs2 = label_all(ap2)
    l2 = bar_labels(ap2.score)
    out["injected_tables"] = {r: bar_error_table(c, l2) for r, c in crs2.items()}
    out["injected_suspect"] = bool(crs2["fixed"].summary["alignment_suspect"])
    pitch_of = dict(zip(pp.notes["id"].astype(str), pp.notes["pitch"].astype(int), strict=True))
    inj = {str(p): (str(s), pitch_of[str(p)]) for p, s in
           zip(wn["performance_id"], wn["score_id"], strict=True)}
    out["d08_notes"] = _copy_outcomes(ap2, crs2, inj, cr)
    # targeted copy (bars chosen on the baseline tables)
    tp, tbars = targeted_copy(ap, cr, labels, out["tables"]["fixed"], experts_fixed,
                              TARGETED_SEED, avoid)
    out["targeted_bars"] = tbars
    if tbars:
        old = ap.performance.notes
        chg = np.flatnonzero(old["pitch"] != tp.notes["pitch"])
        partner = dict(zip(cr.notes["performance_id"].astype(str),
                           cr.notes["score_id"].astype(str), strict=True))
        inj_t = {str(old["id"][k]): (partner[str(old["id"][k])], int(tp.notes["pitch"][k]))
                 for k in chg}
        ap3 = align_performance(ap.score, tp)
        crs3 = label_all(ap3)
        l3 = bar_labels(ap3.score)
        out["targeted_tables"] = {r: bar_error_table(c, l3) for r, c in crs3.items()}
        out["targeted_suspect"] = bool(crs3["fixed"].summary["alignment_suspect"])
        out["targeted_notes"] = _copy_outcomes(ap3, crs3, inj_t, cr)
    return out


# ----------------------------------------------------------------------------- evaluation


def _boot_ratio(per: pd.DataFrame, num: str, den: str, seed: int = 0, n: int = 2000):
    """Piece bootstrap 95% CI of sum(num) / sum(den); ``per`` has one row per piece."""
    rng = np.random.default_rng(seed)
    vals = []
    for _ in range(n):
        s = per.iloc[rng.integers(0, len(per), len(per))]
        vals.append(s[num].sum() / s[den].sum() if s[den].sum() else np.nan)
    return [float(np.nanquantile(vals, 0.025)), float(np.nanquantile(vals, 0.975))]


def _t_interval(x: np.ndarray) -> list[float]:
    from scipy import stats

    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    if len(x) < 2:
        return [float("nan"), float("nan")]
    h = stats.t.ppf(0.975, len(x) - 1) * x.std(ddof=1) / np.sqrt(len(x))
    return [float(x.mean() - h), float(x.mean() + h)]


def _diff_stat(df: pd.DataFrame, num_c: str, num_b: str, den: str) -> dict:
    """Candidate minus baseline of a ratio of sums, with piece bootstrap and t over pieces."""
    per = df.groupby("piece")[[num_c, num_b, den]].sum()
    per["d"] = per[num_c] - per[num_b]
    val = float(per["d"].sum() / per[den].sum()) if per[den].sum() else float("nan")
    rate_p = (per["d"] / per[den].replace(0, np.nan)).to_numpy(float)
    return {"value": val, "boot95": _boot_ratio(per, "d", den), "t95": _t_interval(rate_p),
            "n_den": int(per[den].sum()), "n_pieces": int(len(per))}


def evaluate(rows: list[dict], heldout: bool) -> dict:
    b18 = _load_module("bl18", "calibrate_strong_tier_bl18.py")
    m = _bl18b()
    experts: dict[tuple, dict[str, list]] = {}
    clean_rows = []
    for r in sorted((r for r in rows if not r["suspect"]), key=lambda r: r["order"]):
        if r["role"] == "expert":
            for rule in RULES:
                experts.setdefault((r["piece"], r["family"]), {}).setdefault(rule, []).append(
                    r["tables"][rule])
        for rule in RULES:
            clean_rows.append({"piece": r["piece"], "family": r["family"], "rule": rule,
                               **r["clean"][rule]})
    targets = [r for r in rows if r["role"] == "target" and not r["suspect"]]
    out: dict = {"n_targets": {f: sum(r["family"] == f for r in targets)
                               for f in FAMILIES.values()},
                 "n_targets_suspect": sum(r["role"] == "target" and r["suspect"] for r in rows),
                 "n_experts_suspect": sum(r["role"] == "expert" and r["suspect"] for r in rows),
                 "n_injected_suspect": sum(bool(r.get("injected_suspect")) for r in targets),
                 "n_targeted_suspect": sum(bool(r.get("targeted_suspect")) for r in targets),
                 "n_targeted_bars": {f: int(sum(len(r.get("targeted_bars") or [])
                                                for r in targets if r["family"] == f))
                                     for f in FAMILIES.values()}}
    # ---- note level
    tn, dn = [], []
    for r in targets:
        for key, acc, ok in (("targeted_notes", tn, not r.get("targeted_suspect", True)),
                             ("d08_notes", dn, not r.get("injected_suspect", True))):
            if ok and key in r and len(r[key]):
                acc.append(r[key].assign(piece=r["piece"], family=r["family"], id=r["id"]))
    tn = pd.concat(tn, ignore_index=True)
    dn = pd.concat(dn, ignore_index=True)

    def note_table(nd: pd.DataFrame) -> pd.DataFrame:
        nd = nd.copy()
        nd["strict"] = ((nd["label"] == "wrong_pitch") & nd["partner_ok"]).astype(int)
        nd["mispair"] = ((nd["label"] == "wrong_pitch") & ~nd["partner_ok"]).astype(int)
        nd["unpaired"] = (nd["label"] == "extra").astype(int)
        nd["absorbed"] = (nd["label"] == "correct").astype(int)
        nd["ornament"] = (nd["label"] == "ornament").astype(int)
        wide = nd.pivot_table(index=["piece", "family", "id", "pid"], columns="rule",
                              values=["strict", "mispair", "unpaired", "absorbed", "ornament"],
                              aggfunc="first")
        wide.columns = [f"{a}_{b}" for a, b in wide.columns]
        meta = nd[nd["rule"] == "fixed"].set_index(["piece", "family", "id", "pid"])[
            ["collision", "fast", "intended_label", "same_bar"]]
        wide = wide.join(meta).reset_index()
        wide["one"] = 1
        # window-reachable baseline loss: unpaired with the intended score note missed
        wide["reach"] = ((wide["unpaired_fixed"] == 1)
                         & (wide["intended_label"] == "missed")).astype(int)
        return wide

    tw, dw = note_table(tn), note_table(dn)
    out["note_level"] = {}
    for name, w in (("targeted", tw), ("d08", dw)):
        res = {}
        for fam in ("pooled", *FAMILIES.values()):
            g = w if fam == "pooled" else w[w["family"] == fam]
            sub = {"all": g, "no_collision": g[~g["collision"]], "fast": g[g["fast"]],
                   "not_fast": g[~g["fast"]]}
            fr: dict = {}
            for sname, h in sub.items():
                if not len(h):
                    continue
                d: dict = {"n": int(len(h)), "n_collision": int(h["collision"].sum()),
                           "n_reach": int(h["reach"].sum())}
                for rule in RULES:
                    d[rule] = {k: float(h[f"{k}_{rule}"].mean()) for k in
                               ("strict", "mispair", "unpaired", "absorbed", "ornament")}
                for rule in CANDIDATES:
                    d[f"{rule}_vs_fixed"] = {
                        "strict": _diff_stat(h, f"strict_{rule}", "strict_fixed", "one"),
                        "mispair": _diff_stat(h, f"mispair_{rule}", "mispair_fixed", "one"),
                        "recovered_of_reach": float(h.loc[h["reach"] == 1, f"strict_{rule}"]
                                                    .mean()) if h["reach"].sum() else None}
                fr[sname] = d
            res[fam] = fr
        out["note_level"][name] = res
    # ---- clean false pairing
    cl = pd.DataFrame(clean_rows)
    cw = cl.pivot_table(index=["piece", "family"], columns="rule",
                        values=["n_wrong", "n_wrong_fast"], aggfunc="sum")
    cw.columns = [f"{a}_{b}" for a, b in cw.columns]
    den = cl[cl["rule"] == "fixed"].groupby(["piece", "family"])[["n_graded", "n_fast"]].sum()
    cw = cw.join(den).reset_index()
    out["clean"] = {}
    for fam in ("pooled", *FAMILIES.values()):
        g = cw if fam == "pooled" else cw[cw["family"] == fam]
        d = {"n_graded": int(g["n_graded"].sum()), "n_fast": int(g["n_fast"].sum())}
        for rule in RULES:
            d[rule] = {"wrong_per_1k": 1000 * float(g[f"n_wrong_{rule}"].sum()
                                                    / g["n_graded"].sum()),
                       "wrong_fast_per_1k_fast": 1000 * float(g[f"n_wrong_fast_{rule}"].sum()
                                                              / max(1, g["n_fast"].sum()))}
        for rule in CANDIDATES:
            a = _diff_stat(g, f"n_wrong_{rule}", "n_wrong_fixed", "n_graded")
            b = _diff_stat(g, f"n_wrong_fast_{rule}", "n_wrong_fast_fixed", "n_fast")
            d[f"{rule}_vs_fixed"] = {"wrong_per_1k": {k: (np.array(v) * 1000).tolist()
                                                      if isinstance(v, list) else
                                                      (v * 1000 if k == "value" else v)
                                                      for k, v in a.items()},
                                     "wrong_fast_per_1k_fast": {
                                         k: (np.array(v) * 1000).tolist() if isinstance(v, list)
                                         else (v * 1000 if k == "value" else v)
                                         for k, v in b.items()}}
        out["clean"][fam] = d
    # ---- report level (P = R1(0) + run rule, experts labelled with the same rule)
    rep_rows = {"clean": [], "inj": [], "tgt": []}
    for r in targets:
        for rule in RULES:
            ex = experts.get((r["piece"], r["family"]), {}).get(rule, [])
            t = m.rule_tiers(b18, r["tables"][rule], ex, "P", r["family"])
            t["row"] = np.arange(len(t))
            t = t[~t["in_run"]]
            rep_rows["clean"].append(t.assign(rule=rule, piece=r["piece"], family=r["family"],
                                              id=r["id"]))
            if not r.get("injected_suspect", True):
                ti = m.rule_tiers(b18, r["injected_tables"][rule], ex, "P", r["family"])
                ti["row"] = np.arange(len(ti))
                ti = ti[ti["label"].isin(r["injected_bars"])]
                rep_rows["inj"].append(ti.assign(rule=rule, piece=r["piece"],
                                                 family=r["family"], id=r["id"]))
            if r.get("targeted_bars") and not r.get("targeted_suspect", True):
                tab = r["targeted_tables"][rule]
                tt = m.rule_tiers(b18, tab, ex, "P", r["family"])
                tt["row"] = np.arange(len(tt))
                nw = dict(zip(tab["label"], tab["n_wrong_pitch"], strict=True))
                tt = tt[tt["label"].isin(r["targeted_bars"])].copy()
                tt["checker_wrong"] = tt["label"].map(nw).astype(int)
                rep_rows["tgt"].append(tt.assign(rule=rule, piece=r["piece"],
                                                 family=r["family"], id=r["id"]))
    rep = {k: pd.concat(v, ignore_index=True) for k, v in rep_rows.items()}
    for k in rep:
        rep[k]["strong"] = (rep[k]["tier"] == "strong").astype(int)
        rep[k]["notable_plus"] = (rep[k]["tier"] != "none").astype(int)
        rep[k]["one"] = 1
    out["report"] = {}
    for fam in ("pooled", *FAMILIES.values()):
        d: dict = {}
        for kind, cols in (("clean", ("strong", "notable_plus")),
                           ("inj", ("strong", "notable_plus")), ("tgt", ("strong",))):
            x = rep[kind] if fam == "pooled" else rep[kind][rep[kind]["family"] == fam]
            key = ["piece", "family", "id", "row"]
            if kind == "tgt":
                x = x.assign(all3=(x["checker_wrong"] >= 3).astype(int))
                cols = ("strong", "all3")
            wide = x.pivot_table(index=key, columns="rule", values=list(cols), aggfunc="first")
            wide.columns = [f"{a}_{b}" for a, b in wide.columns]
            wide = wide.reset_index()
            wide["one"] = 1
            dd: dict = {"n_bars": int(len(wide))}
            for rule in RULES:
                dd[rule] = {c: float(wide[f"{c}_{rule}"].mean()) for c in cols}
            for rule in CANDIDATES:
                dd[f"{rule}_vs_fixed"] = {c: _diff_stat(wide, f"{c}_{rule}", f"{c}_fixed", "one")
                                          for c in cols}
            d[kind] = dd
        out["report"][fam] = d
    return out


# ----------------------------------------------------------------------------- criteria

#: Pre-registered criteria (docs/specs/correctness-validation.md, "Pre-registration DF-13").
#: Rates are fractions (0.01 = 1 percentage point); clean rates are relative to the baseline.
B1_GAIN = (0.015, 0.10)       # targeted strict recall, candidate - fixed
M1_MAX = 0.015                # targeted mispair increase, absolute ...
M1_MAX_SHARE_OF_GAIN = 1 / 3  # ... and at most this share of the strict gain
F1_MAX_REL = 0.15             # clean wrong-pitch label rate increase / baseline rate
R1_DELTA = 0.0025             # |candidate - fixed| P clean strong rate
R1_BAND = (0.003, 0.0125)     # P clean strong rate band (information only, BL-18b C1)
R2_DELTA = 0.005              # |candidate - fixed| P clean notable+ rate
E1_GAIN = (0.02, 0.20)        # targeted 3-wrong bars strong under P, candidate - fixed
D1_STRICT_MIN = -0.010        # fast-run targeted strict recall change
D1_MISPAIR_MAX = 0.015        # fast-run targeted mispair increase
D1_CLEAN_MAX_REL = 0.25       # clean fast-run wrong-pitch rate increase / baseline rate


def piece_sums(rows: list[dict]) -> pd.DataFrame:
    """Per (family, piece) numerators and denominators of every criterion, for every rule."""
    b18 = _load_module("bl18", "calibrate_strong_tier_bl18.py")
    m = _bl18b()
    acc: dict[tuple, dict] = {}

    def add(fam, piece, key, v):
        d = acc.setdefault((fam, piece), {})
        d[key] = d.get(key, 0) + v

    experts: dict[tuple, dict[str, list]] = {}
    for r in sorted((r for r in rows if not r["suspect"]), key=lambda r: r["order"]):
        f, pc = r["family"], r["piece"]
        if r["role"] == "expert":
            for rule in RULES:
                experts.setdefault((pc, f), {}).setdefault(rule, []).append(r["tables"][rule])
        add(f, pc, "cl_graded", r["clean"]["fixed"]["n_graded"])
        add(f, pc, "cl_fast", r["clean"]["fixed"]["n_fast"])
        for rule in RULES:
            add(f, pc, f"cl_wrong_{rule}", r["clean"][rule]["n_wrong"])
            add(f, pc, f"cl_wrongfast_{rule}", r["clean"][rule]["n_wrong_fast"])
    for r in rows:
        if r["role"] != "target" or r["suspect"]:
            continue
        f, pc = r["family"], r["piece"]
        add(f, pc, "n_targets", 1)
        if r.get("targeted_bars") and not r.get("targeted_suspect", True):
            nd = r["targeted_notes"]
            for rule in RULES:
                g = nd[nd["rule"] == rule]
                wp = g["label"] == "wrong_pitch"
                add(f, pc, f"tn_strict_{rule}", int((wp & g["partner_ok"]).sum()))
                add(f, pc, f"tn_mis_{rule}", int((wp & ~g["partner_ok"]).sum()))
                add(f, pc, f"tn_fstrict_{rule}", int((wp & g["partner_ok"] & g["fast"]).sum()))
                add(f, pc, f"tn_fmis_{rule}", int((wp & ~g["partner_ok"] & g["fast"]).sum()))
            g = nd[nd["rule"] == "fixed"]
            add(f, pc, "tn_n", len(g))
            add(f, pc, "tn_fast", int(g["fast"].sum()))
        for rule in RULES:
            ex = experts.get((pc, f), {}).get(rule, [])
            t = m.rule_tiers(b18, r["tables"][rule], ex, "P", f)
            t = t[~t["in_run"]]
            add(f, pc, f"rc_strong_{rule}", int((t["tier"] == "strong").sum()))
            add(f, pc, f"rc_np_{rule}", int((t["tier"] != "none").sum()))
            if rule == "fixed":
                add(f, pc, "rc_n", len(t))
            if not r.get("injected_suspect", True):
                ti = m.rule_tiers(b18, r["injected_tables"][rule], ex, "P", f)
                ti = ti[ti["label"].isin(r["injected_bars"])]
                add(f, pc, f"ri_strong_{rule}", int((ti["tier"] == "strong").sum()))
                add(f, pc, f"ri_np_{rule}", int((ti["tier"] != "none").sum()))
                if rule == "fixed":
                    add(f, pc, "ri_n", len(ti))
            if r.get("targeted_bars") and not r.get("targeted_suspect", True):
                tt = m.rule_tiers(b18, r["targeted_tables"][rule], ex, "P", f)
                tt = tt[tt["label"].isin(r["targeted_bars"])]
                add(f, pc, f"rt_strong_{rule}", int((tt["tier"] == "strong").sum()))
                if rule == "fixed":
                    add(f, pc, "rt_n", len(tt))
    df = pd.DataFrame([{"family": k[0], "piece": k[1], **v} for k, v in acc.items()])
    return df.fillna(0)


def criteria(ps: pd.DataFrame, cand: str) -> dict:
    """Pre-registered criteria for one family's piece sums (point estimates)."""
    s = ps.sum(numeric_only=True)

    def r(num, den):
        return float(s[num] / s[den]) if s[den] else float("nan")

    base_c = r("cl_wrong_fixed", "cl_graded")
    base_f = r("cl_wrongfast_fixed", "cl_fast")
    v = {
        "B1": r(f"tn_strict_{cand}", "tn_n") - r("tn_strict_fixed", "tn_n"),
        "M1": r(f"tn_mis_{cand}", "tn_n") - r("tn_mis_fixed", "tn_n"),
        "F1_rel": (r(f"cl_wrong_{cand}", "cl_graded") - base_c) / base_c,
        "F1_per_1k": 1000 * (r(f"cl_wrong_{cand}", "cl_graded") - base_c),
        "R1_rate": r(f"rc_strong_{cand}", "rc_n"),
        "R1_rate_fixed": r("rc_strong_fixed", "rc_n"),
        "R1_delta": r(f"rc_strong_{cand}", "rc_n") - r("rc_strong_fixed", "rc_n"),
        "R2_delta": r(f"rc_np_{cand}", "rc_n") - r("rc_np_fixed", "rc_n"),
        "E0_fixed": r("rt_strong_fixed", "rt_n"),
        "E0_cand": r(f"rt_strong_{cand}", "rt_n"),
        "E1": r(f"rt_strong_{cand}", "rt_n") - r("rt_strong_fixed", "rt_n"),
        "D1_strict": r(f"tn_fstrict_{cand}", "tn_fast") - r("tn_fstrict_fixed", "tn_fast"),
        "D1_mispair": r(f"tn_fmis_{cand}", "tn_fast") - r("tn_fmis_fixed", "tn_fast"),
        "D1_clean_rel": (r(f"cl_wrongfast_{cand}", "cl_fast") - base_f) / base_f,
    }
    ok = {
        "B1": B1_GAIN[0] <= v["B1"] <= B1_GAIN[1],
        "M1": v["M1"] <= min(M1_MAX, M1_MAX_SHARE_OF_GAIN * v["B1"]),
        "F1": v["F1_rel"] <= F1_MAX_REL,
        "R1": abs(v["R1_delta"]) <= R1_DELTA,
        "R2": abs(v["R2_delta"]) <= R2_DELTA,
        "E1": E1_GAIN[0] <= v["E1"] <= E1_GAIN[1],
        "D1": (v["D1_strict"] >= D1_STRICT_MIN and v["D1_mispair"] <= D1_MISPAIR_MAX
               and v["D1_clean_rel"] <= D1_CLEAN_MAX_REL),
    }
    v["R1_band_info"] = bool(R1_BAND[0] <= v["R1_rate"] <= R1_BAND[1])
    return {"values": v, "pass": {k: bool(x) for k, x in ok.items()},
            "all": bool(all(ok.values()))}


def verdicts(ps: pd.DataFrame) -> dict:
    """Criteria per candidate and family, the verdict of each candidate, and the decision."""
    out: dict = {"by_candidate": {}}
    for cand in CANDIDATES:
        fams = {f: criteria(ps[ps["family"] == f], cand) for f in FAMILIES.values()}
        n = sum(v["all"] for v in fams.values())
        out["by_candidate"][cand] = {"families": fams,
                                     "verdict": {2: "PASS", 1: "PARTIAL", 0: "FAIL"}[n]}
    out["selected"] = next((c for c in CANDIDATES
                            if out["by_candidate"][c]["verdict"] == "PASS"), None)
    return out


def reachability(ps: pd.DataFrame, n_pieces: int = N_PIECES, n_boot: int = 2000,
                 seed: int = 0) -> dict:
    """P(each criterion and each verdict) when ``n_pieces`` pieces are resampled from ``ps``
    (per family, with replacement)."""
    rng = np.random.default_rng(seed)
    out: dict = {}
    for cand in CANDIDATES:
        hits: dict[str, list] = {}
        for _ in range(n_boot):
            fam_all = []
            for f in FAMILIES.values():
                g = ps[ps["family"] == f]
                s = g.iloc[rng.integers(0, len(g), n_pieces)]
                c = criteria(s, cand)
                for k, x in c["pass"].items():
                    hits.setdefault(f"{f}:{k}", []).append(x)
                hits.setdefault(f"{f}:all", []).append(c["all"])
                fam_all.append(c["all"])
            n = sum(fam_all)
            for name, val in (("PASS", n == 2), ("PARTIAL", n == 1), ("FAIL", n == 0)):
                hits.setdefault(name, []).append(val)
        out[cand] = {k: float(np.mean(v)) for k, v in hits.items()}
    return out


# ----------------------------------------------------------------------------- main


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", choices=("dev", "heldout"), required=True)
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--from-cache", action="store_true")
    ap.add_argument("--limit-pieces", type=int, default=0, help="smoke test only")
    ap.add_argument("--reachability", action="store_true",
                    help="dev only: resample pieces and report P(criterion), P(verdict)")
    args = ap.parse_args()
    _quiet()
    OUT.mkdir(parents=True, exist_ok=True)
    cache = OUT / f"{args.set}_rows.pkl"
    summ: dict = {"set": args.set, "rules": list(RULES), "candidates": list(CANDIDATES),
                  "prereg": "docs/specs/correctness-validation.md, Pre-registration DF-13"}
    heldout = args.set == "heldout"
    if args.from_cache:
        blob = pickle.loads(cache.read_bytes())
        rows, summ["n_eligible_pieces"] = blob["rows"], blob.get("n_eligible_pieces")
    else:
        if heldout:
            jobs, n_elig = heldout_jobs()
        else:
            jobs, n_elig = dev_jobs(), None
        if args.limit_pieces:
            keep = sorted({j["piece"] for j in jobs})[:args.limit_pieces]
            jobs = [j for j in jobs if j["piece"] in keep]
        summ["n_eligible_pieces"] = n_elig
        print(len(jobs), "jobs;", n_elig, "eligible pieces", flush=True)
        rows, failed = [], []
        with ProcessPoolExecutor(args.workers) as ex:
            futs = {ex.submit(run_expert, j): j for j in jobs if j["role"] == "expert"}
            for k, fu in enumerate(as_completed(futs)):
                try:
                    rows.append(fu.result())
                except Exception as e:  # noqa: BLE001 - count failures
                    failed.append((futs[fu]["id"], repr(e)[:200]))
                if k % 50 == 0:
                    print("experts", k, flush=True)
            exp: dict[tuple, list] = {}
            for r in sorted((r for r in rows if not r["suspect"]), key=lambda r: r["order"]):
                exp.setdefault((r["piece"], r["family"]), []).append(r["tables"]["fixed"])
            futs = {ex.submit(run_target, j, exp.get((j["piece"], j["family"]), []), heldout): j
                    for j in jobs if j["role"] == "target"}
            for k, fu in enumerate(as_completed(futs)):
                try:
                    rows.append(fu.result())
                except Exception as e:  # noqa: BLE001
                    failed.append((futs[fu]["id"], repr(e)[:200]))
                if k % 20 == 0:
                    print("targets", k, flush=True)
        summ["failed"] = failed
        if not args.limit_pieces:
            cache.write_bytes(pickle.dumps({"rows": rows, "n_eligible_pieces": n_elig}))
    summ["pieces"] = sorted({r["piece"] for r in rows})
    summ["n_jobs_ok"] = len(rows)
    summ.update(evaluate(rows, heldout))
    ps = piece_sums(rows)
    ps.to_csv(OUT / f"{args.set}_piece_sums.csv", index=False)
    summ["criteria"] = verdicts(ps)
    if args.reachability:
        summ["reachability"] = reachability(ps)
    name = f"{args.set}_summary.json" if not args.limit_pieces else f"{args.set}_smoke.json"
    (OUT / name).write_text(json.dumps(summ, indent=1, default=float))
    print(json.dumps({k: summ[k] for k in ("pieces", "n_targets", "n_targeted_bars")},
                     indent=1, default=float))


if __name__ == "__main__":
    main()
