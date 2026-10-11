"""DF-15: effect of resolving duplicate aligner matches in ``correctness()`` (fix off vs on).

Run: ``OMP_NUM_THREADS=1 uv run python scripts/eval_duplicate_matches_df15.py --set <set>
[--workers 10] [--from-cache]`` with ``<set>`` one of

* ``keysensor``: the F-08 calibration set (the 100 clean D-08 copies of (n)ASAP performances,
  ``mistakes_v1`` rate 0). Every resolution is also scored against the nASAP ground-truth
  alignment (repair / break, as in BL-23).
* ``asap``: every ASAP performance with an nASAP ground-truth alignment (raw MIDI); repair /
  break of every resolution against the ground truth, split by the parangonar step.
* ``floor``: the 150 A-01 floor transcriptions (``calibrate_expert_check_f08c.floor_jobs``).
* ``dev``: the BL-18b pieces (``eval_pairing_window_df13.dev_jobs``): experts clean, targets
  clean and targeted (3 wrong pitches in up to 10 bars, seed 2, as BL-18b).
* ``heldout``: the DF-13 held-out pieces (``heldout_jobs``, seed 1010), collision-free targeted
  copies as in DF-13.

Every performance is aligned once (production path); ``correctness`` labels it with
``resolve_duplicates=False`` ("off", the labels before DF-15), with the defaults ("on":
resolution on, re-match off) and with ``duplicate_rematch=True`` ("on_rematch"); everything else
is the same. Targeted bars are chosen on the "off" labels, so both settings see the same
copies. Targets are tiered against expert tables labelled with the same setting (rule P =
R1(0) + run rule, extras not counted, as BL-18b / DF-13). Each duplicate is attributed to the
parangonar step that made it (per-pitch DTW or ornament step) by re-running parangonar's note
matcher without the ornament step on the same onset alignment (the final alignment is unchanged).

Outputs (gitignored): ``data/interim/df15/<set>_rows.pkl`` and ``<set>_summary.json``.
"""

from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import pickle
import warnings
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "data" / "interim" / "df15"
MISTAKES = REPO / "data" / "processed" / "mistakes_v1"
SETTINGS = {"off": {"resolve_duplicates": False}, "on": {},
            "on_rematch": {"duplicate_rematch": True}}  # "on" = the default (re-match off)
_STATE: dict = {}


def _mod(name: str, file: str):
    spec = importlib.util.spec_from_file_location(name, REPO / "scripts" / file)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _quiet() -> None:
    import logging

    warnings.filterwarnings("ignore")
    logging.disable(logging.WARNING)


# ----------------------------------------------------------------------------- attribution


def _install_recorder() -> list:
    """Make ``align`` use a note matcher that also records the pitch-step alignment."""
    from parangonar import DualDTWNoteMatcher
    from parangonar.match.matchers import CleanOrnamentMatcher

    import pianolens.align.core as core

    calls: list = []

    class Recording(CleanOrnamentMatcher):
        def __call__(self, full, no_grace, grace, orn, perf, oa, oar, onset_threshold=None,
                     process_ornaments=False):
            pitch_only = super().__call__(*(copy.deepcopy(x) for x in
                                            (full, no_grace, grace, orn, perf, oa, oar)),
                                          onset_threshold=onset_threshold,
                                          process_ornaments=False)
            final = super().__call__(full, no_grace, grace, orn, perf, oa, oar,
                                     onset_threshold=onset_threshold,
                                     process_ornaments=process_ornaments)
            calls.append((pitch_only, final))
            return final

    core.DualDTWNoteMatcher = lambda: DualDTWNoteMatcher(note_matcher=Recording())
    return calls


def _matches(al) -> set[tuple[str, str]]:
    return {(str(a["score_id"]), str(a["performance_id"])) for a in al if a["label"] == "match"}


def duplicate_groups(ap, calls: list) -> list[dict]:
    """Duplicate groups of the final alignment: direction (``perf``: one performed note, several
    score notes; ``score``: the reverse), size and source step."""
    fm = {(s, p) for lab, s, p in ap.alignment.pairs.tolist() if lab == "match"}
    pitch = set()
    for po, fin in calls:
        if _matches(fin) == fm:
            pitch = _matches(po)
    out = []
    for direction, key in (("perf", 1), ("score", 0)):
        by = defaultdict(list)
        for m in fm:
            by[m[key]].append(m)
        for k, ms in by.items():
            if len(ms) > 1:
                src = "pitch_step" if all(m in pitch for m in ms) else "ornament_step"
                out.append({"direction": direction, "key": k, "pairs": sorted(ms),
                            "source": src})
    return out


# ----------------------------------------------------------------------------- labelling


def label_both(ap) -> dict:
    from pianolens.features.correctness import correctness

    return {k: correctness(ap, **kw) for k, kw in SETTINGS.items()}


def counts(cr) -> dict:
    s = cr.summary
    return {k: int(s[k]) for k in ("n_score_notes", "n_correct", "n_wrong_pitch", "n_missed",
                                   "n_extra", "n_duplicate_matches_resolved",
                                   "n_duplicate_rematched")}


def _tables(ap, crs) -> dict:
    from pianolens.report.build import bar_error_table, bar_labels

    labels = bar_labels(ap.score)
    return {k: bar_error_table(c, labels) for k, c in crs.items()}


def _correct_pairs(cr) -> set[tuple[str, str]]:
    """(score id, performed id) of every correct match, from both the score and the performed
    side (with duplicates "off" a note lists only its last partner on one side)."""
    sn, pn = cr.score_notes, cr.notes
    a = sn[sn["label"] == "correct"]
    b = pn[pn["label"] == "correct"]
    return ({(str(x), str(y)) for x, y in zip(a["score_id"], a["performance_id"], strict=True)}
            | {(str(x), str(y)) for x, y in zip(b["score_id"], b["performance_id"],
                                                strict=True)})  # fmt: skip


def gt_check(crs: dict, gt_pairs: set[tuple[str, str]], groups: list[dict]) -> dict:
    """Repair / break of the resolution against the ground-truth matches (BL-23 style): a
    correct pair lost from "off" to "on" is a break when it is a ground-truth match and a repair
    when it is not; a correct pair gained is a repair when it is a ground-truth match. Also the
    final "on" label of every score note in a duplicate group against the ground truth."""
    off_c, on_c = _correct_pairs(crs["off"]), _correct_pairs(crs["on"])
    out = Counter()
    src_of: dict[str, str] = {}
    for g in groups:
        for x, y in g["pairs"]:
            src_of.setdefault("s:" + x, g["source"])
            src_of.setdefault("p:" + y, g["source"])

    def src(pair: tuple[str, str]) -> str:
        return src_of.get("s:" + pair[0]) or src_of.get("p:" + pair[1]) or "other"

    for pair in off_c - on_c:
        k = "lost_in_gt (break)" if pair in gt_pairs else "lost_not_gt (repair)"
        out[k] += 1
        out[f"{src(pair)}:{k}"] += 1
    for pair in on_c - off_c:
        k = "gained_in_gt (repair)" if pair in gt_pairs else "gained_not_gt"
        out[k] += 1
        out[f"{src(pair)}:{k}"] += 1
    gt_s = {x for x, _ in gt_pairs}
    lab = dict(zip(crs["on"].score_notes["score_id"].astype(str),
                   crs["on"].score_notes["label"].astype(str), strict=True))
    involved = {x for g in groups for x, _ in g["pairs"]}
    for x in involved:
        out[f"final_{lab.get(x, '?')}_{'gt_played' if x in gt_s else 'gt_unmatched'}"] += 1
    for g in groups:
        out["group_pairs"] += len(g["pairs"])
        out["group_pairs_in_gt"] += sum(pr in gt_pairs for pr in g["pairs"])
    return dict(out)


# ----------------------------------------------------------------------------- workers


def keysensor_one(key: str) -> dict:
    _quiet()
    calls = _install_recorder()
    from pianolens.align import align_performance
    from pianolens.data import asap
    from pianolens.data.perturb import load_mistake_set

    if "get" not in _STATE:
        index, get = load_mistake_set(MISTAKES)
        _STATE.update(get=get, index=index.set_index("key"),
                      asap=asap.asap_index().set_index("performance_id", drop=False))
    perf, lab = _STATE["get"](key)
    r = _STATE["index"].loc[key]
    arow = _STATE["asap"].loc[r["performance_id"]]
    ap = align_performance(asap.load_asap_score(arow), perf)
    crs = label_both(ap)
    groups = duplicate_groups(ap, calls)
    gt = {(str(s), str(p)) for lb, s, p in lab.alignment.pairs.tolist() if lb == "match"}
    return {"key": key, "piece": arow["piece_id"], "family": "key_sensor", "role": "expert",
            "suspect": bool(crs["off"].summary["alignment_suspect"]),
            "counts": {k: counts(c) for k, c in crs.items()}, "tables": _tables(ap, crs),
            "groups": groups, "gt": gt_check(crs, gt, groups)}


def asap_one(perf_id: str) -> dict:
    """Any ASAP performance with an nASAP ground-truth alignment (raw MIDI, production path)."""
    _quiet()
    calls = _install_recorder()
    from pianolens.align import align_performance
    from pianolens.data import asap

    row = asap.asap_index().set_index("performance_id", drop=False).loc[perf_id]
    ap = align_performance(asap.load_asap_score(row), asap.load_asap_performance(row))
    crs = label_both(ap)
    groups = duplicate_groups(ap, calls)
    gal = asap.load_asap_alignment(row)
    gt = {(str(s_), str(p)) for lb, s_, p in gal.pairs.tolist() if lb == "match"}
    return {"key": perf_id, "piece": row["piece_id"], "family": "key_sensor", "role": "expert",
            "robust": bool(pd.notna(row["robust_note_alignment"])
                           and int(row["robust_note_alignment"]) == 1),
            "suspect": bool(crs["off"].summary["alignment_suspect"]),
            "counts": {k: counts(c) for k, c in crs.items()}, "groups": groups,
            "tables": _tables(ap, crs), "gt": gt_check(crs, gt, groups)}


def floor_one(k: str, ref_id: str, rel: str, t: str) -> dict:
    _quiet()
    calls = _install_recorder()
    f08c = _mod("f08c", "calibrate_expert_check_f08c.py")
    import tempfile
    import zipfile

    from pianolens.align import align_performance
    from pianolens.data.pianocore import DEFAULT_ROOT, RAW_PREFIX, RAW_ZIP
    from pianolens.report.io import load_performance, load_score

    meta = json.loads((f08c.HENRY / "scores" / "scores.json").read_text())[k]
    sc = load_score(f08c.HENRY / "scores" / f"{k}_score.mxl", meta["piece_id"])
    with zipfile.ZipFile(DEFAULT_ROOT / RAW_ZIP) as z, tempfile.TemporaryDirectory() as td:
        f = Path(td) / "ref.mid"
        f.write_bytes(z.read(RAW_PREFIX + rel))
        ap = align_performance(sc, load_performance(f, "transcribed", meta["piece_id"],
                                                    performance_id=ref_id))
    crs = label_both(ap)
    tabs = _tables(ap, crs)
    return {"take": k, "transcriber": t, "ref_id": ref_id, "piece": meta["piece_id"],
            "family": t, "role": "expert",
            "suspect": bool(crs["off"].summary["alignment_suspect"]),
            "counts": {s: counts(c) for s, c in crs.items()}, "tables": tabs,
            "groups": duplicate_groups(ap, calls)}


def expert_one(job: dict) -> dict:
    _quiet()
    calls = _install_recorder()
    from pianolens.align import align_performance

    sc, perf = _mod("bl18b", "calibrate_strong_tier_bl18b.py")._load(job)
    ap = align_performance(sc, perf)
    crs = label_both(ap)
    return {**job, "suspect": bool(crs["off"].summary["alignment_suspect"]),
            "counts": {k: counts(c) for k, c in crs.items()}, "tables": _tables(ap, crs),
            "groups": duplicate_groups(ap, calls)}


def target_one(job: dict, experts_off: list[pd.DataFrame], avoid: bool) -> dict:
    _quiet()
    calls = _install_recorder()
    from pianolens.align import align_performance
    from pianolens.report.build import bar_labels

    df13 = _mod("df13", "eval_pairing_window_df13.py")
    sc, perf = _mod("bl18b", "calibrate_strong_tier_bl18b.py")._load(job)
    ap = align_performance(sc, perf)
    crs = label_both(ap)
    out = {**job, "suspect": bool(crs["off"].summary["alignment_suspect"]),
           "counts": {k: counts(c) for k, c in crs.items()}, "tables": _tables(ap, crs),
           "groups": duplicate_groups(ap, calls)}
    if out["suspect"]:
        return out
    labels = bar_labels(ap.score)
    tp, tbars = df13.targeted_copy(ap, crs["off"], labels, out["tables"]["off"], experts_off,
                                   df13.TARGETED_SEED, avoid)
    out["targeted_bars"] = tbars
    if tbars:
        old = ap.performance.notes
        chg = np.flatnonzero(old["pitch"] != tp.notes["pitch"])
        partner = dict(zip(crs["off"].notes["performance_id"].astype(str),
                           crs["off"].notes["score_id"].astype(str), strict=True))
        inj = {str(old["id"][k]): (partner[str(old["id"][k])], int(tp.notes["pitch"][k]))
               for k in chg}
        calls.clear()
        ap3 = align_performance(ap.score, tp)
        crs3 = label_both(ap3)
        out["targeted_tables"] = _tables(ap3, crs3)
        out["targeted_counts"] = {k: counts(c) for k, c in crs3.items()}
        out["targeted_suspect"] = bool(crs3["off"].summary["alignment_suspect"])
        out["targeted_notes"] = _copy_outcomes(df13, crs3, inj, crs["off"])
        out["targeted_groups"] = duplicate_groups(ap3, calls)
    return out


def _copy_outcomes(df13, crs3: dict, inj: dict, cr_clean) -> pd.DataFrame:
    """``eval_pairing_window_df13._copy_outcomes`` with the settings as the rules (fast runs
    from the "off" labels)."""
    from pianolens.report.build import fast_run_notes

    sn = cr_clean.score_notes
    bar_p = {int(b): set(g["pitch"].astype(int)) for b, g in sn.groupby("measure_index")}
    ib = dict(zip(sn["score_id"].astype(str), sn["measure_index"].astype(int), strict=True))
    n = crs3["off"].notes
    fast = dict(zip(n["performance_id"].astype(str), fast_run_notes(n), strict=True))
    return df13.note_outcomes(crs3, inj, bar_p, ib, fast)


# ----------------------------------------------------------------------------- evaluation


def _boot_delta(per: pd.DataFrame, a: str, b: str, den: str, n: int = 2000) -> list[float]:
    rng = np.random.default_rng(0)
    vals = []
    for _ in range(n):
        s = per.iloc[rng.integers(0, len(per), len(per))]
        vals.append((s[a].sum() - s[b].sum()) / s[den].sum() if s[den].sum() else np.nan)
    return [float(np.nanquantile(vals, 0.025)), float(np.nanquantile(vals, 0.975))]


def count_summary(rows: list[dict], key: str = "counts") -> dict:
    """Summed counts per family (rows not suspect), per 1,000 graded score notes."""
    out = {}
    fams = sorted({r["family"] for r in rows})
    for fam in ("pooled", *fams):
        rr = [r for r in rows if key in r and not r["suspect"]
              and (fam == "pooled" or r["family"] == fam)]
        d = {}
        for s in SETTINGS:
            tot = Counter()
            for r in rr:
                tot.update(r[key][s])
            d[s] = dict(tot)
        g = d["off"].get("n_score_notes", 0)
        d["delta_per_1k"] = {k: 1000 * (d["on"].get(k, 0) - d["off"].get(k, 0)) / max(1, g)
                             for k in ("n_correct", "n_wrong_pitch", "n_missed", "n_extra")}
        d["n_perfs"] = len(rr)
        d["perfs_with_dropped"] = sum(r[key]["on"]["n_duplicate_matches_resolved"] > 0
                                      for r in rr)
        out[fam] = d
    return out


def group_summary(rows: list[dict], key: str = "groups") -> dict:
    out = {}
    fams = sorted({r["family"] for r in rows})
    for fam in ("pooled", *fams):
        c = Counter()
        sizes = Counter()
        for r in rows:
            if key in r and (fam == "pooled" or r["family"] == fam):
                for g in r[key]:
                    c[f"{g['direction']}:{g['source']}"] += 1
                    sizes[len(g["pairs"])] += 1
        out[fam] = {"by_direction_source": dict(c), "group_sizes": dict(sizes)}
    return out


def keysensor_eval(rows: list[dict]) -> dict:
    """F-08 quantities from the clean expert bars (``calibrate_report_f08``), off vs on, and the
    share of expert bars tiered under the global limits (extras counted, key-sensor input)."""
    from pianolens.report.build import _correctness_tier, global_correctness_limits

    glim = global_correctness_limits(True)
    out: dict = {}
    for s in SETTINGS:
        bars = pd.concat([r["tables"][s].assign(key=r["key"]) for r in rows],
                         ignore_index=True)
        bars = bars[bars["n_score_notes"] > 0].copy()
        bars["n_missed_extra"] = bars["n_missed"] + bars["n_extra"]
        bars["n_errors"] = bars["n_wrong_pitch"] + bars["n_missed_extra"]
        rate = bars["n_missed_extra"] / bars["n_score_notes"]
        per = bars.groupby("key")[["n_errors", "n_score_notes"]].sum()
        er = per["n_errors"] / per["n_score_notes"]
        tiers = [_correctness_tier(int(w), int(me), int(n), glim)[0] for w, me, n in
                 zip(bars["n_wrong_pitch"], bars["n_missed_extra"], bars["n_score_notes"],
                     strict=True)]
        tiers = np.array(tiers)
        out[s] = {"n_bars": int(len(bars)),
                  "missed_extra_per_note": {f"q{int(q * 100)}": float(np.quantile(rate, q))
                                            for q in (0.95, 0.99)},
                  "n_wrong_pitch": {f"q{int(q * 100)}": float(np.quantile(
                      bars["n_wrong_pitch"], q)) for q in (0.95, 0.99)},
                  "wrong_share_ge": {k: float((bars["n_wrong_pitch"] >= k).mean())
                                     for k in (1, 2, 3)},
                  "error_rate_per_performance": {f"q{int(q * 100)}": float(np.quantile(er, q))
                                                 for q in (0.5, 0.95, 0.99)},
                  "share_bars_any_error_median": float(np.median(bars.groupby("key")[
                      "n_errors"].apply(lambda x: (x > 0).mean()))),
                  "global_notable_plus": float((tiers != "none").mean()),
                  "global_strong": float((tiers == "strong").mean())}
    gt = Counter()
    for r in rows:
        gt.update(r["gt"])
    out["gt_check"] = dict(gt)
    return out


def report_eval(rows: list[dict]) -> dict:
    """Rule P clean strong / notable+ (targets' clean bars outside runs) and the strong share of
    targeted 3-wrong bars, off vs on, per family, with piece-bootstrap CIs of the deltas; plus
    the outcome of every injected wrong note."""
    b18 = _mod("bl18", "calibrate_strong_tier_bl18.py")
    m = _mod("bl18b", "calibrate_strong_tier_bl18b.py")
    experts: dict[tuple, dict[str, list]] = {}
    for r in sorted((r for r in rows if not r["suspect"]), key=lambda r: r["order"]):
        if r["role"] == "expert":
            for s in SETTINGS:
                experts.setdefault((r["piece"], r["family"]), {}).setdefault(s, []).append(
                    r["tables"][s])
    acc: dict[tuple, Counter] = defaultdict(Counter)
    for r in rows:
        if r["role"] != "target" or r["suspect"]:
            continue
        key = (r["family"], r["piece"])
        for s in SETTINGS:
            ex = experts.get((r["piece"], r["family"]), {}).get(s, [])
            t = m.rule_tiers(b18, r["tables"][s], ex, "P", r["family"])
            t = t[~t["in_run"]]
            acc[key][f"strong_{s}"] += int((t["tier"] == "strong").sum())
            acc[key][f"np_{s}"] += int((t["tier"] != "none").sum())
            acc[key][f"n_{s}"] += len(t)
            if r.get("targeted_bars") and not r.get("targeted_suspect", True):
                tt = m.rule_tiers(b18, r["targeted_tables"][s], ex, "P", r["family"])
                tt = tt[tt["label"].isin(r["targeted_bars"])]
                acc[key][f"tstrong_{s}"] += int((tt["tier"] == "strong").sum())
                acc[key][f"tn_{s}"] += len(tt)
                nd = r["targeted_notes"]
                g = nd[nd["rule"] == s]
                acc[key][f"strict_{s}"] += int(((g["label"] == "wrong_pitch")
                                                & g["partner_ok"]).sum())
                acc[key][f"intended_missed_{s}"] += int((g["intended_label"] == "missed").sum())
                acc[key][f"inj_{s}"] += len(g)
    per = pd.DataFrame([{"family": k[0], "piece": k[1], **v} for k, v in acc.items()]).fillna(0)
    out: dict = {}
    for fam in ("pooled", *sorted(per["family"].unique())):
        g = per if fam == "pooled" else per[per["family"] == fam]
        gp = g.groupby("piece").sum(numeric_only=True)
        s = gp.sum()
        d = {"n_pieces": int(len(gp))}
        for name, num, den in (("P_clean_strong", "strong", "n"),
                               ("P_clean_notable_plus", "np", "n"),
                               ("targeted_3wrong_strong", "tstrong", "tn"),
                               ("injected_strict", "strict", "inj"),
                               ("injected_intended_missed", "intended_missed", "inj")):
            off = float(s[f"{num}_off"] / s[f"{den}_off"]) if s[f"{den}_off"] else float("nan")
            on = float(s[f"{num}_on"] / s[f"{den}_on"]) if s[f"{den}_on"] else float("nan")
            rm = (float(s[f"{num}_on_rematch"] / s[f"{den}_on_rematch"])
                  if s.get(f"{den}_on_rematch", 0) else float("nan"))
            d[name] = {"off": off, "on": on, "on_rematch": rm, "delta_pt": 100 * (on - off),
                       "n_off": int(s[f"{den}_off"]), "n_on": int(s[f"{den}_on"]),
                       "count_off": int(s[f"{num}_off"]), "count_on": int(s[f"{num}_on"])}
            if s[f"{den}_off"] and s[f"{den}_off"] == s[f"{den}_on"]:
                d[name]["delta_boot95_pt"] = [100 * x for x in
                                              _boot_delta(gp, f"{num}_on", f"{num}_off",
                                                          f"{den}_off")]
        out[fam] = d
    out["per_piece"] = per.to_dict(orient="records")
    return out


def floor_eval(rows: list[dict]) -> dict:
    fl = _mod("fl", "rebuild_floor_tables_df13.py")
    out = {}
    for s in SETTINGS:
        rr = [{"take": r["take"], "transcriber": r["transcriber"], "ref_id": r["ref_id"],
               "suspect": r["suspect"], "table": r["tables"][s],
               "n_wrong": r["counts"][s]["n_wrong_pitch"],
               "n_graded": r["counts"][s]["n_score_notes"]} for r in rows]
        out[s] = fl.calibration(rr)
    return out


# ----------------------------------------------------------------------------- main


def run(set_name: str, workers: int) -> list[dict]:
    rows, failed = [], []
    with ProcessPoolExecutor(workers) as ex:
        if set_name == "keysensor":
            from pianolens.data.perturb import load_mistake_set

            index, _ = load_mistake_set(MISTAKES)
            keys = [str(r["key"]) for _, r in index.iterrows() if float(r["rate"]) == 0.0]
            futs = {ex.submit(keysensor_one, k): k for k in keys}
        elif set_name == "asap":
            from pianolens.data import asap

            idx = asap.asap_index()
            ids = [str(r["performance_id"]) for _, r in idx.iterrows()
                   if asap.asap_alignment_path(r).is_file()]
            futs = {ex.submit(asap_one, k): k for k in ids}
        elif set_name == "floor":
            f08c = _mod("f08c", "calibrate_expert_check_f08c.py")
            futs = {ex.submit(floor_one, *j): j[1] for j in f08c.floor_jobs()}
        else:
            df13 = _mod("df13", "eval_pairing_window_df13.py")
            jobs = df13.dev_jobs() if set_name == "dev" else df13.heldout_jobs()[0]
            futs = {ex.submit(expert_one, j): j["id"] for j in jobs if j["role"] == "expert"}
        for k, fu in enumerate(as_completed(futs)):
            try:
                rows.append(fu.result())
            except Exception as e:  # noqa: BLE001 - count failures
                failed.append((futs[fu], repr(e)[:200]))
            if k % 50 == 0:
                print(set_name, "first phase", k, flush=True)
        if set_name in ("dev", "heldout"):
            exp: dict[tuple, list] = {}
            for r in sorted((r for r in rows if not r["suspect"]), key=lambda r: r["order"]):
                exp.setdefault((r["piece"], r["family"]), []).append(r["tables"]["off"])
            futs = {ex.submit(target_one, j, exp.get((j["piece"], j["family"]), []),
                              set_name == "heldout"): j["id"]
                    for j in jobs if j["role"] == "target"}
            for k, fu in enumerate(as_completed(futs)):
                try:
                    rows.append(fu.result())
                except Exception as e:  # noqa: BLE001
                    failed.append((futs[fu], repr(e)[:200]))
                if k % 20 == 0:
                    print(set_name, "targets", k, flush=True)
    if failed:
        print("FAILED", failed, flush=True)
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", required=True,
                    choices=("keysensor", "asap", "floor", "dev", "heldout"))
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--from-cache", action="store_true")
    args = ap.parse_args()
    _quiet()
    OUT.mkdir(parents=True, exist_ok=True)
    cache = OUT / f"{args.set}_rows.pkl"
    if args.from_cache:
        rows = pickle.loads(cache.read_bytes())
    else:
        rows = run(args.set, args.workers)
        cache.write_bytes(pickle.dumps(rows))
    summ: dict = {"set": args.set, "n_rows": len(rows),
                  "n_suspect": sum(bool(r["suspect"]) for r in rows),
                  "counts_clean": count_summary(rows), "groups_clean": group_summary(rows)}
    if args.set == "keysensor":
        summ["f08"] = keysensor_eval([r for r in rows if not r["suspect"]])
    elif args.set == "floor":
        summ["floor"] = floor_eval(rows)
    elif args.set == "asap":
        gt = Counter()
        for r in rows:
            if not r["suspect"]:
                gt.update(r["gt"])
        summ["gt_check"] = dict(gt)
    else:
        summ["counts_targeted"] = count_summary(rows, "targeted_counts")
        summ["groups_targeted"] = group_summary(rows, "targeted_groups")
        summ["report"] = report_eval(rows)
    (OUT / f"{args.set}_summary.json").write_text(json.dumps(summ, indent=1, default=float))
    print(json.dumps({k: v for k, v in summ.items() if k != "report"}, indent=1,
                     default=float)[:6000])
    if "report" in summ:
        print(json.dumps({k: v for k, v in summ["report"].items() if k != "per_piece"},
                         indent=1, default=float))


if __name__ == "__main__":
    main()
