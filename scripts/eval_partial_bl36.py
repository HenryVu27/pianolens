"""BL-36: align partial recordings (recorded-span detection, ``align(..., partial=True)``).

Run: ``OMP_NUM_THREADS=1 uv run python scripts/eval_partial_bl36.py --set dev|heldout
[--workers 10] [--from-cache] [--limit-targets N] [--tag NAME] [--override K=V ...]``

Pre-registration: ``experiments/2026-10-11-BL-36-partial-recordings/README.md`` (hash by
anchor in that README).

Methods: ``C`` = today's pipeline (``align_performance(score, perf)``, repeat path "auto", the
BL-18 "passage not heard" runs on transcribed input); ``N`` = the same with
``align_performance(..., partial=True)`` (bars outside the recorded span are not graded).

Per piece and transcriber family: 15 experts (clean tables) and 10 targets (BL-27 layout).
For each target:

* **natural** (untouched copy): C and N on the clean transcription, rule P tiers (R1(0) against
  the 15 same-family experts, extras not counted) with each method's runs untiered;
* **truncation control** (known answer): four copies with notes removed by performance time,
  realigned by C and by N with the clean alignment's repeat path (``C``, ``N``; as BL-27, so
  bar truth is defined), and by N with repeat path "auto" (``Na``, what a learner gets):
  ``start`` (onsets before T removed; T inside a graded bar drawn from 5-50% of the graded
  bars), ``end`` (onsets from T on removed; bar from 50-95%), ``both`` (start bar from 5-25%
  and end bar from 75-95%) and ``excerpt`` (8-32 consecutive graded bars kept, cut at bar
  boundaries, at least one graded bar removed on each side). Truth per bar label of the clean
  C alignment from its expected onsets (BL-27 ``_truth``): ``heard`` / ``not_heard`` / ``cut``;
  a heard bar is ``played`` when the clean copy found it (under half its graded notes missed).

Outputs (gitignored): ``data/interim/bl36/<set>[_<tag>]_rows.pkl``, ``..._summary.json`` and
per-copy CSVs.
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
OUT = REPO / "data" / "interim" / "bl36"
CAL = REPO / "data" / "interim" / "reports" / "calibration"
FAMILIES = {"Transkun V2": "transkun", "Aria-AMT": "aria_amt"}
HELDOUT_SEED = 3636
TRUNC_SEED = 36
N_PIECES = 16
N_REPEAT_PIECES = 8  # at least this many held-out pieces with literal repeats
N_EXPERTS = 15
N_TARGETS = 10
MIN_PER_FAMILY = 25
KINDS = ("start", "end", "both", "excerpt")
START_RANGE = (0.05, 0.50)
END_RANGE = (0.50, 0.95)
BOTH_START = (0.05, 0.25)
BOTH_END = (0.75, 0.95)
EXCERPT_BARS = (8, 32)
FOUND_MAX_MISSED = 0.5  # a heard bar is "played" when the clean copy missed under half of it
AGREE_SHARE = 0.5  # a played bar agrees when at least half its clean matches land on its label
REPEAT_WINDOW = 4  # bars in a content window for the literal-repeat flag


def _mod(name: str, file: str):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, REPO / "scripts" / file)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


def bl27():
    return _mod("bl27", "eval_not_heard_merge_bl27.py")


def _quiet() -> None:
    import logging

    warnings.filterwarnings("ignore")
    logging.disable(logging.WARNING)


def _apply_overrides(over: dict[str, float]) -> None:
    from pianolens.align import partial as pa

    for k, v in over.items():
        setattr(pa, k, type(getattr(pa, k))(v))


# ----------------------------------------------------------------------------- draw


def literal_repeat_flag(score_path_job: dict) -> dict:
    """Whether the score has literal repeats: more than one repeat path, or two disjoint
    windows of ``REPEAT_WINDOW`` bars of the fully repeated unfolding with identical content
    (same pitches at the same offsets from the window start)."""
    _quiet()
    from pianolens.align.core import _build, _variants_with_paths
    from pianolens.align.partial import _measure_starts, _rows_of_divs

    sc, _ = _mod("bl18b", "calibrate_strong_tier_bl18b.py")._load(
        {**score_path_job, "midi": score_path_job["any_midi"], "id": "probe"})
    from pianolens.align._adapters import to_part

    part = to_part(sc)
    vs = _variants_with_paths(part)
    up = _build(part, max(vs, key=lambda v: v[1])[2], len(vs))
    na = up.note_array()
    starts = _measure_starts(up)
    rows = _rows_of_divs(starts, na["onset_div"])
    sig = []
    for r in range(len(starts)):
        sel = na[rows == r]
        sig.append(tuple(sorted(zip((sel["onset_div"] - starts[r]).tolist(),
                                    sel["pitch"].tolist(), strict=True))))
    seen: dict[tuple, int] = {}
    hit = 0
    for r in range(len(sig) - REPEAT_WINDOW + 1):
        w = tuple(sig[r:r + REPEAT_WINDOW])
        if not any(w):
            continue
        if w in seen and r - seen[w] >= REPEAT_WINDOW:
            hit += 1
        seen.setdefault(w, r)
    return {"piece": score_path_job["piece"], "n_variants": len(vs), "repeat_windows": hit,
            "literal_repeats": bool(len(vs) > 1 or hit > 0)}


def heldout_jobs(workers: int) -> tuple[list[dict], dict]:
    import zipfile

    from pianolens.data.pianocore import DEFAULT_ROOT, RAW_PREFIX, RAW_ZIP, PianoCoRe

    b27 = bl27()
    idx = PianoCoRe().index
    tr = idx[idx["is_transcription"].astype(bool) & idx["capture_model"].isin(FAMILIES)]
    meta = json.loads((b27.HENRY / "scores" / "scores.json").read_text())
    excl = {m["piece_id"] for m in meta.values()}
    excl |= set(json.loads((CAL / "bl18_summary.json").read_text())["t2_pieces"])
    b18b = pickle.loads((CAL / "bl18b_tables.pkl").read_bytes())["rows"]
    excl |= {r["piece"] for r in b18b}
    d13 = pickle.loads((b27.DF13 / "heldout_rows.pkl").read_bytes())["rows"]
    excl |= {r["piece"] for r in d13}
    r27 = pickle.loads((b27.OUT / "heldout_rows.pkl").read_bytes())["rows"]
    excl |= {r["piece"] for r in r27}
    floor = pickle.loads((CAL / "f08c_floor_tables.pkl").read_bytes())
    b18 = pickle.loads((CAL / "bl18_tables.pkl").read_bytes())
    used = ({str(r["ref_id"]) for r in floor} | {str(r["id"]) for r in b18}
            | {str(r["id"]) for r in b18b} | {str(r["id"]) for r in d13}
            | {str(r["id"]) for r in r27})
    with zipfile.ZipFile(DEFAULT_ROOT / RAW_ZIP) as z:
        names = set(z.namelist())
    cnt = tr.groupby(["piece_id", "capture_model"]).size().unstack(fill_value=0)
    elig = []
    for pid, row in cnt.iterrows():
        if pid in excl or min(row.get(cm, 0) for cm in FAMILIES) < MIN_PER_FAMILY:
            continue
        sx = tr.loc[tr["piece_id"] == pid, "score_xml_path"].dropna().astype(str)
        sx = [s for s in sorted(set(sx)) if RAW_PREFIX + s in names]
        if len(sx) == 1:
            elig.append((pid, sx[0]))
    elig.sort()
    rng = np.random.default_rng(HELDOUT_SEED)
    order = [elig[i] for i in rng.permutation(len(elig))]
    # literal-repeat flags in permutation order until both strata are filled
    probe_jobs = []
    for pid, sx in order:
        m = tr[(tr["piece_id"] == pid)].sort_values("id").iloc[0]
        probe_jobs.append({"piece": pid, "piece_id": pid, "score": sx,
                           "any_midi": str(m["performance_midi_path"])})
    flags: dict[str, dict] = {}
    with ProcessPoolExecutor(workers) as ex:
        for f in ex.map(literal_repeat_flag, probe_jobs):
            flags[f["piece"]] = f
    rep = [p for p in order if flags[p[0]]["literal_repeats"]]
    non = [p for p in order if not flags[p[0]]["literal_repeats"]]
    n_rep = max(N_REPEAT_PIECES, N_PIECES - len(non))
    chosen = sorted(rep[:n_rep] + non[:N_PIECES - n_rep])
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
    info = {"n_eligible": len(elig), "n_literal_repeats_eligible": len(rep),
            "flags": {p: flags[p] for p, _ in chosen},
            "all_flags": flags}
    from pianolens.data.pianocore import guard_jobs  # BL-35 / BL-38: after the draw, not before

    return guard_jobs(jobs, idx, label="BL-36 held-out"), info


def dev_jobs() -> list[dict]:
    return bl27().dev_jobs()


# ----------------------------------------------------------------------------- workers


def _label_map(ap) -> dict[str, str]:
    """Score note id -> bar label of the aligned (performed) score."""
    from pianolens.features.correctness import measure_rows
    from pianolens.report.build import bar_labels

    sn = ap.score.notes
    rows = measure_rows(ap.score.measures, sn["onset_quarter"].astype(float))
    labels = bar_labels(ap.score)
    return {str(i): (labels[r] if r >= 0 else "") for i, r in
            zip(sn["id"].astype(str), rows, strict=True)}


def _perf_bar(ap) -> dict[str, str]:
    """Performed note id -> bar label of the score note it is matched to."""
    lm = _label_map(ap)
    return {str(p): lm.get(str(s), "") for lab, s, p in ap.alignment.pairs.tolist()
            if lab == "match"}


def _summ(ap, cr) -> dict:
    from pianolens.report.build import bar_labels

    rs = ap.score.meta.get("recorded_span")
    return {"table": bl27()._table(ap, cr), "labels": bar_labels(ap.score),
            "variant": str(ap.score.meta.get("unfolded") or ""),
            "suspect": bool(cr.summary["alignment_suspect"]),
            "match_ratio": float(cr.summary.get("match_ratio", np.nan)),
            "span": rs, "perf_bar": _perf_bar(ap)}


def expert_one(job: dict) -> dict:
    _quiet()
    _apply_overrides(job.get("_over", {}))
    from pianolens.align import align_performance
    from pianolens.features.correctness import correctness

    sc, perf = _mod("bl18b", "calibrate_strong_tier_bl18b.py")._load(job)
    ap = align_performance(sc, perf)
    cr = correctness(ap)
    return {**job, "suspect": bool(cr.summary["alignment_suspect"]),
            "table": bl27()._table(ap, cr)}


def _graded_first_last(cr) -> pd.DataFrame:
    sn = cr.score_notes
    g = sn[sn["label"].isin(["correct", "wrong_pitch", "missed"]) & (sn["measure_index"] >= 0)]
    return g.groupby("measure_index")["expected_onset_sec"].agg(["min", "max"]).dropna() \
        .sort_index()


def _time_in_bar(fl: pd.DataFrame, k: int, rng: np.random.Generator) -> float:
    t0 = float(fl["min"].iloc[k])
    t1 = float(fl["min"].iloc[min(k + 1, len(fl) - 1)])
    return t0 if t1 <= t0 else float(rng.uniform(t0, t1))


def _bar_boundary(fl: pd.DataFrame, k: int) -> float:
    """A time between graded bar k-1's last expected onset and bar k's first."""
    a, b = float(fl["max"].iloc[k - 1]), float(fl["min"].iloc[k])
    return (a + b) / 2 if b > a else b - 1e-3


def cut_window(cr, kind: str, rng: np.random.Generator) -> tuple[float, float] | None:
    """(t_lo, t_hi): notes with onset in [t_lo, t_hi) are kept."""
    fl = _graded_first_last(cr)
    n = len(fl)
    if n < 12:
        return None

    def pick(lo, hi):
        return int(rng.integers(int(lo * n), max(int(lo * n) + 1, int(hi * n))))

    if kind == "start":
        return _time_in_bar(fl, pick(*START_RANGE), rng), np.inf
    if kind == "end":
        return -np.inf, _time_in_bar(fl, pick(*END_RANGE), rng)
    if kind == "both":
        return (_time_in_bar(fl, pick(*BOTH_START), rng),
                _time_in_bar(fl, pick(*BOTH_END), rng))
    if kind == "excerpt":
        length = int(rng.integers(EXCERPT_BARS[0], EXCERPT_BARS[1] + 1))
        if n < length + 2:
            return None
        k0 = int(rng.integers(1, n - length))  # at least one graded bar removed on each side
        return _bar_boundary(fl, k0), _bar_boundary(fl, k0 + length)
    raise ValueError(kind)


def truth(cr, labels: list[str], t_lo: float, t_hi: float) -> dict[str, str]:
    sn = cr.score_notes
    g = sn[sn["label"].isin(["correct", "wrong_pitch", "missed"]) & (sn["measure_index"] >= 0)]
    out = {}
    for b, grp in g.groupby("measure_index"):
        e = grp["expected_onset_sec"].to_numpy(float)
        e = e[np.isfinite(e)]
        if not len(e):
            continue
        kept = (e >= t_lo) & (e < t_hi)
        out[labels[int(b)]] = "heard" if kept.all() else "not_heard" if not kept.any() else "cut"
    return out


def bar_classes(score) -> dict[str, int]:
    """Bar label -> content class: bars with the same written notes (pitch and onset relative
    to the bar start, grace notes excluded) share a class (a literal repeat)."""
    from pianolens.features.correctness import measure_rows
    from pianolens.report.build import bar_labels

    sn = score.notes
    sn = sn[~sn["is_grace"].astype(bool)] if "is_grace" in sn.dtype.names else sn
    q = sn["onset_quarter"].astype(float)
    rows = measure_rows(score.measures, q)
    labels = bar_labels(score)
    sig: dict[int, list] = {}
    for r, qq, pp in zip(rows, q, sn["pitch"], strict=True):
        if r >= 0:
            sig.setdefault(int(r), []).append(
                (round(float(qq - score.measures["start_quarter"][r]), 4), int(pp)))
    classes: dict[tuple, int] = {}
    out = {}
    for r, lab in enumerate(labels):
        key = tuple(sorted(sig.get(r, [])))
        out[lab] = classes.setdefault(key, len(classes))
    return out


def target_one(job: dict) -> dict:
    _quiet()
    _apply_overrides(job.get("_over", {}))
    from pianolens.align import align_performance
    from pianolens.features.correctness import correctness

    sc, perf = _mod("bl18b", "calibrate_strong_tier_bl18b.py")._load(job)
    apn = align_performance(sc, perf, partial=True)
    crn = correctness(apn)
    rs = apn.score.meta["recorded_span"]
    if rs["whole"] and not rs.get("refined"):
        apc, crc = apn, crn  # identical by construction (tests/align/test_partial.py)
    else:
        apc = align_performance(sc, perf)
        crc = correctness(apc)
    out = {**job, "C": _summ(apc, crc), "N": _summ(apn, crn)}
    out["suspect"] = out["C"]["suspect"]
    if out["suspect"] or job.get("natural_only"):
        return out
    labels = out["C"]["labels"]
    out["bar_class"] = bar_classes(apc.score)
    variant = out["C"]["variant"] or "auto"
    rng = np.random.default_rng([TRUNC_SEED, zlib.crc32(job["id"].encode())])
    out["cuts"] = {}
    notes = apc.performance.notes
    for kind in KINDS:
        win = cut_window(crc, kind, rng)
        if win is None:
            continue
        lo, hi = win
        keep = (notes["onset_sec"] >= lo) & (notes["onset_sec"] < hi)
        if keep.sum() < 20:
            continue
        tp = dataclasses.replace(apc.performance, notes=notes[keep].copy(),
                                 performance_id=f"{apc.performance.performance_id}#{kind}")
        c = {"t_lo": lo, "t_hi": hi, "n_kept": int(keep.sum()), "n_removed": int((~keep).sum()),
             "truth": truth(crc, labels, lo, hi)}
        for m, kw in (("C", {"repeats": variant}), ("N", {"repeats": variant, "partial": True}),
                      ("Na", {"partial": True})):
            ap2 = align_performance(sc, tp, **kw)
            c[m] = _summ(ap2, correctness(ap2))
        out["cuts"][kind] = c
    return out


# ----------------------------------------------------------------------------- evaluation


def _found(table: pd.DataFrame) -> dict[str, bool]:
    t = table[table["n_score_notes"] > 0]
    return dict(zip(t["label"], (t["n_missed"] / t["n_score_notes"]) < FOUND_MAX_MISSED,
                    strict=True))


def _agreement(clean_pb: dict[str, str], copy_pb: dict[str, str], bars: list[str],
               cls: dict[str, int] | None = None) -> list[bool]:
    """Per played bar: at least ``AGREE_SHARE`` of the performed notes the clean copy matched in
    it are matched to the same bar label in the copy (``cls`` given: to a bar of the same
    content class, i.e. the same bar or a literal repeat of it)."""
    by_bar: dict[str, list[str]] = {}
    for pid, lab in clean_pb.items():
        by_bar.setdefault(lab, []).append(pid)
    out = []
    for b in bars:
        pids = by_bar.get(b, [])
        if not pids:
            out.append(False)
            continue
        if cls is None:
            same = sum(copy_pb.get(p) == b for p in pids)
        else:
            same = sum(copy_pb.get(p) is not None and cls.get(copy_pb[p], -1) == cls.get(b, -2)
                       for p in pids)
        out.append(same >= AGREE_SHARE * len(pids))
    return out


def copy_rows(r: dict, experts: list[pd.DataFrame]) -> list[dict]:
    b27 = bl27()
    found = _found(r["C"]["table"])
    rows = []
    for kind, c in (r.get("cuts") or {}).items():
        tr = c["truth"]
        played = [b for b, s in tr.items() if s == "heard" and found.get(b, False)]
        nh = [b for b, s in tr.items() if s == "not_heard"]
        heard = [b for b, s in tr.items() if s == "heard"]
        cut = [b for b, s in tr.items() if s == "cut"]
        d = {"piece": r["piece"], "family": r["family"], "id": r["id"], "kind": kind,
             "n_truth": len(tr), "n_not_heard": len(nh), "n_heard": len(heard),
             "n_played": len(played), "n_cut": len(cut)}
        for m in ("C", "N", "Na"):
            s = c[m]
            t = b27.tiers_runs(s["table"], experts, 0)
            tier = dict(zip(t["label"], t["tier"], strict=True))
            in_run = dict(zip(t["label"], t["in_run"], strict=True))
            graded = set(t["label"])
            in_span = set(s["labels"])
            # span accuracy over heard / not-heard bars (cut bars excluded)
            ok = [(b in in_span) == (tr[b] == "heard") for b in nh + heard]
            d[f"acc_{m}"] = float(np.mean(ok)) if ok else np.nan
            d[f"n_acc_ok_{m}"] = int(sum(ok))
            d["n_acc"] = len(ok)
            d[f"nh_in_span_{m}"] = sum(b in in_span for b in nh)
            d[f"heard_out_{m}"] = sum(b not in in_span for b in heard)
            d[f"played_out_{m}"] = sum(b not in in_span for b in played)
            d[f"nh_tiered_{m}"] = sum(tier.get(b, "none") != "none" for b in nh)
            d[f"nh_strong_{m}"] = sum(tier.get(b, "none") == "strong" for b in nh)
            d[f"nh_graded_{m}"] = sum(b in graded and not in_run.get(b, False) for b in nh)
            d[f"cut_tiered_{m}"] = sum(tier.get(b, "none") != "none" for b in cut)
            d[f"played_strong_{m}"] = sum(tier.get(b, "none") == "strong" for b in played)
            d[f"played_tiered_{m}"] = sum(tier.get(b, "none") != "none" for b in played)
            ag = _agreement(r["C"]["perf_bar"], s["perf_bar"], played)
            d[f"agree_{m}"] = float(np.mean(ag)) if ag else np.nan
            d[f"n_agree_{m}"] = int(sum(ag))
            ae = _agreement(r["C"]["perf_bar"], s["perf_bar"], played, r["bar_class"])
            d[f"n_agree_eq_{m}"] = int(sum(ae))
            d[f"suspect_{m}"] = bool(s["suspect"])
            d[f"variant_same_{m}"] = s["variant"] == r["C"]["variant"]
            d[f"strong_all_{m}"] = sum(v == "strong" for v in tier.values())
            if m == "N":
                sp = s["span"] or {}
                d["whole_N"] = bool(sp.get("whole", True))
            if m == "Na":
                d["whole_Na"] = bool((s["span"] or {}).get("whole", True))
        d["played_strong_clean"] = 0
        rows.append(d)
    # clean-copy strong on the played bars (what the uncut copy says about the same bars)
    if rows:
        t = b27.tiers_runs(r["C"]["table"], experts, 0)
        tier = dict(zip(t["label"], t["tier"], strict=True))
        for d, (_kind, c) in zip(rows, (r.get("cuts") or {}).items(), strict=True):
            played = [b for b, s in c["truth"].items() if s == "heard" and found.get(b, False)]
            d["played_strong_clean"] = sum(tier.get(b, "none") == "strong" for b in played)
    return rows


def natural_row(r: dict, experts: list[pd.DataFrame]) -> dict:
    b27 = bl27()
    d = {"piece": r["piece"], "family": r["family"], "id": r["id"]}
    for m in ("C", "N"):
        t = b27.tiers_runs(r[m]["table"], experts, 0)
        out = t[~t["in_run"]]
        d[f"n_{m}"] = len(out)
        d[f"strong_{m}"] = int((out["tier"] == "strong").sum())
        d[f"np_{m}"] = int((out["tier"] != "none").sum())
        d[f"runs_{m}"] = int(t["run_id"].max() + 1) if len(t) else 0
        d[f"graded_{m}"] = len(t)
    sp = r["N"]["span"] or {}
    d["whole_N"] = bool(sp.get("whole", True))
    d["n_not_recorded_N"] = sum(x["n_bars"] for x in sp.get("not_recorded", []))
    d["n_rows_C"] = len(r["C"]["labels"])
    # evidently full: the first and last 5% of graded bars (at least 3) mostly found under C
    t = r["C"]["table"]
    g = t[t["n_score_notes"] > 0]
    fr = (g["n_missed"] / g["n_score_notes"]).to_numpy(float)
    k = max(3, int(np.ceil(0.05 * len(fr))))
    d["evidently_full"] = bool(len(fr) >= 2 * k and np.mean(fr[:k] < 0.5) > 0.5
                               and np.mean(fr[-k:] < 0.5) > 0.5)
    d["identical_N"] = bool(d["whole_N"])
    return d


def _piece_stat(df: pd.DataFrame, col: str, weight: str | None = None) -> pd.Series:
    """Per-piece value of ``col``: mean over copies (or ratio of sums with ``weight``)."""
    if weight:
        g = df.groupby("piece")[[col, weight]].sum()
        return (g[col] / g[weight].replace(0, np.nan)).dropna()
    return df.groupby("piece")[col].mean().dropna()


def _boot(per: pd.Series, n: int = 2000) -> list[float]:
    rng = np.random.default_rng(0)
    v = per.to_numpy(float)
    if len(v) == 0:
        return [np.nan, np.nan]
    bs = [v[rng.integers(0, len(v), len(v))].mean() for _ in range(n)]
    return [float(np.quantile(bs, 0.025)), float(np.quantile(bs, 0.975))]


def _stat(df: pd.DataFrame, col: str, weight: str | None = None) -> dict:
    per = _piece_stat(df, col, weight)
    loo = [float(per.drop(p).mean()) for p in per.index] if len(per) > 1 else []
    return {"mean_over_pieces": float(per.mean()) if len(per) else np.nan,
            "median_piece": float(per.median()) if len(per) else np.nan,
            "boot95": _boot(per), "n_pieces": int(len(per)),
            "loo_min": float(min(loo)) if loo else np.nan,
            "loo_max": float(max(loo)) if loo else np.nan,
            "per_piece": {k: float(v) for k, v in per.items()}}


def evaluate(rows: list[dict]) -> dict:
    experts: dict[tuple, list] = {}
    for r in sorted((r for r in rows if r["role"] == "expert" and not r["suspect"]),
                    key=lambda r: r["order"]):
        experts.setdefault((r["piece"], r["family"]), []).append(r["table"])
    targets = [r for r in rows if r["role"] == "target" and not r["suspect"]]
    nat = pd.DataFrame([natural_row(r, experts.get((r["piece"], r["family"]), []))
                        for r in targets])
    cps = pd.DataFrame([d for r in targets
                        for d in copy_rows(r, experts.get((r["piece"], r["family"]), []))])
    out: dict = {"n_targets": len(targets),
                 "n_targets_suspect": sum(r["role"] == "target" and r["suspect"] for r in rows),
                 "n_experts_suspect": sum(r["role"] == "expert" and r["suspect"] for r in rows),
                 "n_copies": int(len(cps))}
    # ---- truncation control
    tc: dict = {}
    for fam in (("pooled", *FAMILIES.values()) if len(cps) else ()):
        for kind in ("all", *KINDS):
            g = cps if fam == "pooled" else cps[cps["family"] == fam]
            g = g if kind == "all" else g[g["kind"] == kind]
            if not len(g):
                continue
            d = {"n_copies": int(len(g)), "whole_N": float(g["whole_N"].mean())}
            for m in ("C", "N", "Na"):
                d[m] = {"acc": _stat(g, f"n_acc_ok_{m}", "n_acc"),
                        "nh_tiered": _stat(g, f"nh_tiered_{m}", "n_not_heard"),
                        "nh_strong": _stat(g, f"nh_strong_{m}", "n_not_heard"),
                        "agree": _stat(g, f"n_agree_{m}", "n_played"),
                        "agree_eq": _stat(g, f"n_agree_eq_{m}", "n_played"),
                        "copy_acc_min": float(g[f"acc_{m}"].min()),
                        "copies_acc_below_0_9": int((g[f"acc_{m}"] < 0.9).sum()),
                        "nh_tiered_pooled": float(g[f"nh_tiered_{m}"].sum()
                                                  / max(1, g["n_not_heard"].sum())),
                        "nh_strong_pooled": float(g[f"nh_strong_{m}"].sum()
                                                  / max(1, g["n_not_heard"].sum())),
                        "agree_pooled": float(g[f"n_agree_{m}"].sum()
                                              / max(1, g["n_played"].sum())),
                        "played_out": int(g[f"played_out_{m}"].sum()),
                        "nh_in_span": int(g[f"nh_in_span_{m}"].sum()),
                        "cut_tiered": int(g[f"cut_tiered_{m}"].sum()),
                        "played_strong": int(g[f"played_strong_{m}"].sum()),
                        "suspect": float(g[f"suspect_{m}"].mean()),
                        "variant_same": float(g[f"variant_same_{m}"].mean()),
                        "copies_nh_strong_gt_played_strong": int(
                            (g[f"nh_strong_{m}"] > g[f"played_strong_{m}"]).sum())}
            d["played_strong_clean"] = int(g["played_strong_clean"].sum())
            d["n_not_heard"] = int(g["n_not_heard"].sum())
            d["n_played"] = int(g["n_played"].sum())
            tc[f"{kind}:{fam}"] = d
    out["truncation"] = tc
    # ---- natural (untouched copies): harm
    nt: dict = {}
    for fam in ("pooled", *FAMILIES.values()):
        g = nat if fam == "pooled" else nat[nat["family"] == fam]
        if not len(g):
            continue
        g = g.assign(ps_C=g["strong_C"] / g["n_C"], ps_N=g["strong_N"] / g["n_N"],
                     pn_C=g["np_C"] / g["n_C"], pn_N=g["np_N"] / g["n_N"])
        per = g.groupby("piece")[["strong_C", "n_C", "strong_N", "n_N", "np_C", "np_N"]].sum()
        dstrong = 100 * (per["strong_N"] / per["n_N"] - per["strong_C"] / per["n_C"])
        dnp = 100 * (per["np_N"] / per["n_N"] - per["np_C"] / per["n_C"])
        s = per.sum()
        ef = g[g["evidently_full"]]
        nt[fam] = {
            "n_targets": int(len(g)), "n_pieces": int(len(per)),
            "P_strong_C": float(s["strong_C"] / s["n_C"]),
            "P_strong_N": float(s["strong_N"] / s["n_N"]),
            "P_np_C": float(s["np_C"] / s["n_C"]), "P_np_N": float(s["np_N"] / s["n_N"]),
            "d_strong_pt_pieces": {"mean": float(dstrong.mean()), "boot95": _boot(dstrong),
                                   "loo": [float(dstrong.drop(p).mean()) for p in dstrong.index],
                                   "per_piece": dstrong.round(4).to_dict()},
            "d_np_pt_pieces": {"mean": float(dnp.mean()), "boot95": _boot(dnp),
                               "loo": [float(dnp.drop(p).mean()) for p in dnp.index],
                               "per_piece": dnp.round(4).to_dict()},
            "d_strong_pt_pooled": float(100 * (s["strong_N"] / s["n_N"]
                                               - s["strong_C"] / s["n_C"])),
            "d_np_pt_pooled": float(100 * (s["np_N"] / s["n_N"] - s["np_C"] / s["n_C"])),
            "whole_share_all": float(g["whole_N"].mean()),
            "n_evidently_full": int(len(ef)),
            "whole_share_evidently_full": float(ef["whole_N"].mean()) if len(ef) else np.nan,
            "whole_evidently_full_pieces": _stat(ef.assign(w=ef["whole_N"].astype(float)), "w")
            if len(ef) else {},
            "not_recorded_bars_evidently_full": int(ef["n_not_recorded_N"].sum()),
            "not_recorded_share_evidently_full_pieces": _stat(ef, "n_not_recorded_N", "n_rows_C")
            if len(ef) else {},
            "runs_C": int(g["runs_C"].sum()), "runs_N": int(g["runs_N"].sum()),
        }
    out["natural"] = nt
    if len(cps):
        cr = criteria(cps, nat)
        out["criteria"] = cr
        out["verdict"] = verdict(cr)
        out["loo"] = loo_flips(cps, nat)
    else:  # natural-only runs (harm bite checks)
        out["criteria"] = natural_criteria(nat)
        out["verdict"] = verdict(out["criteria"])
    out["_tables"] = {"natural": nat, "copies": cps}
    return out


# ----------------------------------------------------------------------------- criteria

#: Pre-registered bars (README "Pre-registration"). Statistics are means over pieces of per-piece
#: ratios of sums (truncation copies of all four kinds and both families pooled unless a family
#: is named).
BARS = {
    "T1_acc_N": (">=", 0.97), "T2_nh_tiered_N": ("<=", 0.03), "T3_agree_N": (">=", 0.97),
    "F_acc_N": (">=", 0.95), "F_nh_tiered_N": ("<=", 0.05), "F_agree_N": (">=", 0.95),
    "R1_acc_Na": (">=", 0.95), "R2_nh_tiered_Na": ("<=", 0.03), "R3_agree_eq_Na": (">=", 0.97),
    "H1_d_strong_pt": ("abs<=", 0.15), "H1_d_np_pt": ("abs<=", 0.30),
    "H2_whole_share": (">=", 0.95), "H2_not_recorded_share": ("<=", 0.002),
}


def _ratio(df: pd.DataFrame, num: str, den: str) -> pd.Series:
    g = df.groupby("piece")[[num, den]].sum()
    g = g[g[den] > 0]
    return g[num] / g[den]


def criteria(cps: pd.DataFrame, nat: pd.DataFrame) -> dict[str, dict]:
    """Every registered statistic: {name: {"value", "per_piece", "bar", "pass"}} (per family
    where the name says so)."""
    out: dict[str, dict] = {}

    def put(name: str, per: pd.Series, key: str) -> None:
        op, bar = BARS[key]
        v = float(per.mean()) if len(per) else np.nan
        ok = (v >= bar) if op == ">=" else (v <= bar) if op == "<=" else (abs(v) <= bar)
        out[name] = {"value": v, "bar": f"{op} {bar}", "pass": bool(ok), "n_pieces": len(per),
                     "per_piece": {k: float(x) for k, x in per.items()}}

    put("T1_acc_N", _ratio(cps, "n_acc_ok_N", "n_acc"), "T1_acc_N")
    put("T2_nh_tiered_N", _ratio(cps, "nh_tiered_N", "n_not_heard"), "T2_nh_tiered_N")
    put("T3_agree_N", _ratio(cps, "n_agree_N", "n_played"), "T3_agree_N")
    for fam in FAMILIES.values():
        g = cps[cps["family"] == fam]
        put(f"F_acc_N:{fam}", _ratio(g, "n_acc_ok_N", "n_acc"), "F_acc_N")
        put(f"F_nh_tiered_N:{fam}", _ratio(g, "nh_tiered_N", "n_not_heard"), "F_nh_tiered_N")
        put(f"F_agree_N:{fam}", _ratio(g, "n_agree_N", "n_played"), "F_agree_N")
    put("R1_acc_Na", _ratio(cps, "n_acc_ok_Na", "n_acc"), "R1_acc_Na")
    put("R2_nh_tiered_Na", _ratio(cps, "nh_tiered_Na", "n_not_heard"), "R2_nh_tiered_Na")
    put("R3_agree_eq_Na", _ratio(cps, "n_agree_eq_Na", "n_played"), "R3_agree_eq_Na")
    for fam in FAMILIES.values():
        g = nat[nat["family"] == fam].groupby("piece")[
            ["strong_C", "n_C", "strong_N", "n_N", "np_C", "np_N"]].sum()
        put(f"H1_d_strong_pt:{fam}", 100 * (g["strong_N"] / g["n_N"] - g["strong_C"] / g["n_C"]),
            "H1_d_strong_pt")
        put(f"H1_d_np_pt:{fam}", 100 * (g["np_N"] / g["n_N"] - g["np_C"] / g["n_C"]),
            "H1_d_np_pt")
    ef = nat[nat["evidently_full"]]
    put("H2_whole_share", ef.groupby("piece")["whole_N"].mean().astype(float), "H2_whole_share")
    put("H2_not_recorded_share", _ratio(ef, "n_not_recorded_N", "n_rows_C"),
        "H2_not_recorded_share")
    # baselines (information): the same statistics for C
    for m in ("C",):
        out[f"base_T1_acc_{m}"] = {"value": float(_ratio(cps, f"n_acc_ok_{m}", "n_acc").mean())}
        out[f"base_T2_nh_tiered_{m}"] = {
            "value": float(_ratio(cps, f"nh_tiered_{m}", "n_not_heard").mean())}
        out[f"base_T3_agree_{m}"] = {
            "value": float(_ratio(cps, f"n_agree_{m}", "n_played").mean())}
    return out


def natural_criteria(nat: pd.DataFrame) -> dict[str, dict]:
    """H1 and H2 only (natural-only runs)."""
    dummy = pd.DataFrame({c: [0] for c in (
        "piece", "family", "n_acc_ok_N", "n_acc", "nh_tiered_N", "n_not_heard", "n_agree_N",
        "n_played", "n_acc_ok_Na", "nh_tiered_Na", "n_agree_eq_Na", "n_acc_ok_C",
        "nh_tiered_C", "n_agree_C")})
    return {k: v for k, v in criteria(dummy, nat).items() if k.startswith("H")}


def verdict(cr: dict[str, dict]) -> dict:
    reg = {k: v for k, v in cr.items() if "pass" in v}
    return {"pass": all(v["pass"] for v in reg.values()),
            "failed": sorted(k for k, v in reg.items() if not v["pass"])}


def reachability(cps: pd.DataFrame, nat: pd.DataFrame, n: int, n_pieces: int,
                 seed: int = 0) -> dict:
    """Share of resamples of ``n_pieces`` dev pieces (with replacement) in which each
    registered criterion passes, and the whole verdict."""
    rng = np.random.default_rng(seed)
    pieces = sorted(set(cps["piece"]) | set(nat["piece"]))
    hits: dict[str, int] = {}
    all_pass = 0
    for _ in range(n):
        pick = rng.choice(pieces, n_pieces, replace=True)
        cc, nn = [], []
        for k, pc in enumerate(pick):  # relabel so a repeated piece counts twice
            cc.append(cps[cps["piece"] == pc].assign(piece=f"{pc}#{k}"))
            nn.append(nat[nat["piece"] == pc].assign(piece=f"{pc}#{k}"))
        cr = criteria(pd.concat(cc), pd.concat(nn))
        for kk, v in cr.items():
            if "pass" in v:
                hits[kk] = hits.get(kk, 0) + int(v["pass"])
        all_pass += int(verdict(cr)["pass"])
    return {"n": n, "n_pieces": n_pieces, "pass_all": all_pass / n,
            "per_criterion": {k: v / n for k, v in sorted(hits.items())}}


def loo_flips(cps: pd.DataFrame, nat: pd.DataFrame) -> dict:
    """Leave-one-piece-out: for each registered criterion, the drops that flip it."""
    full = criteria(cps, nat)
    pieces = sorted(set(cps["piece"]) | set(nat["piece"]))
    flips: dict[str, list] = {k: [] for k, v in full.items() if "pass" in v}
    ranges: dict[str, list] = {k: [] for k in flips}
    for pc in pieces:
        cr = criteria(cps[cps["piece"] != pc], nat[nat["piece"] != pc])
        for k in flips:
            ranges[k].append(cr[k]["value"])
            if cr[k]["pass"] != full[k]["pass"]:
                flips[k].append(pc)
    return {k: {"flips": flips[k], "n_flips": len(flips[k]),
                "range": [float(np.nanmin(ranges[k])), float(np.nanmax(ranges[k]))]}
            for k in flips}


# ----------------------------------------------------------------------------- main


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", choices=("dev", "heldout"), required=True)
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--from-cache", action="store_true")
    ap.add_argument("--limit-targets", type=int, default=0,
                    help="dev only: first N targets per piece and family (design iterations)")
    ap.add_argument("--natural-only", action="store_true",
                    help="no truncation copies (harm bite checks)")
    ap.add_argument("--tag", default="")
    ap.add_argument("--override", nargs="*", default=[],
                    help="partial-module constants, e.g. SNAP_NOTES=0 (bite checks)")
    ap.add_argument("--draw-only", action="store_true")
    ap.add_argument("--reachability", type=int, default=0,
                    help="dev: resamples of 16 pieces for the criteria reachability")
    args = ap.parse_args()
    _quiet()
    OUT.mkdir(parents=True, exist_ok=True)
    stem = args.set + (f"_{args.tag}" if args.tag else "")
    cache = OUT / f"{stem}_rows.pkl"
    over = dict(kv.split("=", 1) for kv in args.override)
    if args.from_cache:
        blob = pickle.loads(cache.read_bytes())
    else:
        info: dict = {}
        if args.set == "dev":
            jobs = dev_jobs()
        else:
            jobs, info = heldout_jobs(args.workers)
            (OUT / "heldout_draw.json").write_text(json.dumps(
                {k: v for k, v in info.items() if k != "all_flags"}, indent=1, default=str))
            (OUT / "heldout_repeat_flags.json").write_text(json.dumps(info["all_flags"],
                                                                      indent=1, default=str))
            if args.draw_only:
                print(json.dumps({k: v for k, v in info.items() if k != "all_flags"},
                                 indent=1, default=str))
                return
        rows, failed = [], []
        if args.set == "dev":
            d15 = pickle.loads((REPO / "data" / "interim" / "df15" / "dev_rows.pkl").read_bytes())
            keys = ("piece", "piece_id", "family", "role", "order", "id", "midi", "score")
            rows = [{**{k: r[k] for k in keys}, "suspect": r["suspect"], "table": r["tables"]["on"]}
                    for r in d15 if r["role"] == "expert"]
            jobs = [j for j in jobs if j["role"] == "target"]
            if args.limit_targets:
                jobs = [j for j in jobs if j["order"] < N_EXPERTS + args.limit_targets]
        for j in jobs:
            j["_over"] = over
            j["natural_only"] = args.natural_only
        print(len(jobs), "jobs", flush=True)
        with ProcessPoolExecutor(args.workers) as ex:
            futs = {ex.submit(expert_one if j["role"] == "expert" else target_one, j): j
                    for j in jobs}
            for k, fu in enumerate(as_completed(futs)):
                try:
                    rows.append(fu.result())
                except Exception as e:  # noqa: BLE001 - count failures
                    failed.append((futs[fu]["id"], repr(e)[:300]))
                if k % 25 == 0:
                    print("done", k, len(failed), flush=True)
        blob = {"rows": rows, "info": {k: v for k, v in info.items() if k != "all_flags"},
                "failed": failed, "overrides": over}
        cache.write_bytes(pickle.dumps(blob))
    rows = blob["rows"]
    res = evaluate(rows)
    tabs = res.pop("_tables")
    for k, t in tabs.items():
        t.to_csv(OUT / f"{stem}_{k}.csv", index=False)
    summ = {"set": args.set, "tag": args.tag, "overrides": blob.get("overrides"),
            "failed": blob.get("failed", []), "info": blob.get("info"),
            "pieces": sorted({r["piece"] for r in rows}), "n_rows": len(rows), **res}
    if args.reachability:
        summ["reachability"] = reachability(tabs["copies"], tabs["natural"], args.reachability,
                                            N_PIECES)
    (OUT / f"{stem}_summary.json").write_text(json.dumps(summ, indent=1, default=float))
    brief = {k: summ[k] for k in ("set", "tag", "n_rows", "n_targets", "n_copies", "failed",
                                  "verdict")}
    brief["criteria"] = {k: round(v["value"], 5) for k, v in summ["criteria"].items()
                         if np.isfinite(v["value"])}
    if "reachability" in summ:
        brief["reachability"] = summ["reachability"]
    print(json.dumps(brief, indent=1, default=float))


if __name__ == "__main__":
    main()
