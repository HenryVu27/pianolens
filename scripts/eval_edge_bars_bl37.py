"""BL-37: edge bars of a trimmed span (partial recordings, ``align(..., partial=True)``).

Run: ``OMP_NUM_THREADS=1 uv run python scripts/eval_edge_bars_bl37.py --set dev|heldout
[--workers 10] [--from-cache] [--tag NAME] [--draw-only]``

Pre-registration: ``experiments/2026-10-11-BL-37-edge-bars/README.md`` (hash by anchor).

Builds on ``scripts/eval_partial_bl36.py`` (same truncation control, truth, methods C / N /
Na, same per-target layout so its ``criteria`` give the BL-36 rows as no-regression rows) and
adds, per truncation copy:

* a **played-bar table**: every played bar (truth ``heard`` and found by the clean copy) with
  its distance ``d`` from the recorded edge (0 = the first / last fully heard bar next to a
  removed side), whether the cut removed any performed note the clean copy matched in it, and
  its counts (score notes, missed, wrong pitch, extra) in the clean copy and under C, N and Na;
* **note-level detail** for bars with ``d <= 1`` (mechanism): every score note's label and
  performed partner, every performed note's label and bar, in the clean copy and under N;
* an **injected copy**: 3 wrong pitches (BL-18b's deltas) in each edge bar (``d = 0``) that the
  clean copy found with at least 3 correct notes and no wrong pitch, realigned by N. Detection
  of a known mistake at the edge, to check that an edge policy does not hide real errors.

Whole recordings: C is always computed separately (not reused from N) and compared with N
(alignment pairs, score notes, measures, correctness bar table); ``whole_identical`` records it.

Sets: ``dev`` = BL-36 dev + BL-36 held-out (28 pieces, both seen); ``heldout`` = a new draw
(seed 3737) disjoint from every earlier draw.
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
OUT = REPO / "data" / "interim" / "bl37"
BL36 = REPO / "data" / "interim" / "bl36"
CAL = REPO / "data" / "interim" / "reports" / "calibration"
HELDOUT_SEED = 3737
INJECT_SEED = 37
N_PIECES = 16
N_REPEAT_PIECES = 8
SHORT_EXCERPT_BARS = (4, 7)  # information: excerpts under 8 bars
NEAR = 1  # note-level detail for played bars with d <= NEAR


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


def b18b():
    return _mod("bl18b", "calibrate_strong_tier_bl18b.py")


def _flag(job: dict) -> dict:
    """``bl36.literal_repeat_flag`` via a function of this module (spawned workers cannot
    import a module that was loaded by path)."""
    return b36().literal_repeat_flag(job)


def _expert(job: dict) -> dict:
    """``bl36.expert_one`` via a function of this module (see :func:`_flag`)."""
    return b36().expert_one(job)


def _quiet() -> None:
    import logging

    warnings.filterwarnings("ignore")
    logging.disable(logging.WARNING)


# ----------------------------------------------------------------------------- jobs


def dev_jobs() -> tuple[list[dict], list[dict]]:
    """BL-36 dev + BL-36 held-out targets, and their cached expert rows (same code path)."""
    keys = ("piece", "piece_id", "family", "role", "order", "id", "midi", "score")
    jobs, experts = [], []
    for f in ("dev_v2_rows.pkl", "heldout_rows.pkl"):
        rows = pickle.loads((BL36 / f).read_bytes())["rows"]
        for r in rows:
            if r["role"] == "expert":
                experts.append({**{k: r[k] for k in keys}, "suspect": r["suspect"],
                                "table": r["table"]})
            else:
                jobs.append({k: r[k] for k in keys})
    return jobs, experts


def heldout_jobs(workers: int) -> tuple[list[dict], dict]:
    """A new draw (seed 3737) disjoint from every earlier draw; layout as BL-36."""
    import zipfile

    from pianolens.data.pianocore import DEFAULT_ROOT, RAW_PREFIX, RAW_ZIP, PianoCoRe

    m = b36()
    b27 = m.bl27()
    idx = PianoCoRe().index
    tr = idx[idx["is_transcription"].astype(bool) & idx["capture_model"].isin(m.FAMILIES)]
    sets = exclusion_sets()
    excl = set().union(*sets["pieces"].values())
    from pianolens.data.piece_ids import SCORE_VERSION_MISMATCH

    excl |= set(SCORE_VERSION_MISMATCH)  # BL-38: score is not the version people play
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
    n_rep = max(N_REPEAT_PIECES, N_PIECES - len(non))
    chosen = sorted(rep[:n_rep] + non[:N_PIECES - n_rep])
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
    del b27
    # BL-35 raw-MIDI guard, applied after the seeded draw so the draw itself does not shift
    from pianolens.data.pianocore import guard_jobs

    drawn = jobs
    jobs = guard_jobs(drawn, idx, label="BL-37 held-out")
    guarded = sorted({j["id"] for j in drawn} - {j["id"] for j in jobs})
    return jobs, {"n_drawn_jobs": len(drawn), "guarded_ids": guarded,
                  "n_guarded": len(guarded),
                  "n_eligible": len(elig), "n_literal_repeats_eligible": len(rep),
                  "flags": {p: flags[p] for p, _ in chosen}, "all_flags": flags,
                  "exclusions": {**{k: sorted(v) for k, v in sets["pieces"].items()},
                                 "SCORE_VERSION_MISMATCH": sorted(SCORE_VERSION_MISMATCH)},
                  "n_excluded_ids": {k: len(v) for k, v in sets["ids"].items()}}


def exclusion_sets() -> dict[str, dict[str, set]]:
    """Every earlier draw: piece ids and transcription ids, by source."""
    m = b36()
    b27 = m.bl27()
    meta = json.loads((b27.HENRY / "scores" / "scores.json").read_text())
    floor = pickle.loads((CAL / "f08c_floor_tables.pkl").read_bytes())
    b18 = pickle.loads((CAL / "bl18_tables.pkl").read_bytes())
    b18b_rows = pickle.loads((CAL / "bl18b_tables.pkl").read_bytes())["rows"]
    d13 = pickle.loads((b27.DF13 / "heldout_rows.pkl").read_bytes())["rows"]
    r27 = pickle.loads((b27.OUT / "heldout_rows.pkl").read_bytes())["rows"]
    r36h = pickle.loads((BL36 / "heldout_rows.pkl").read_bytes())["rows"]
    r36d = pickle.loads((BL36 / "dev_v2_rows.pkl").read_bytes())["rows"]
    pieces = {
        "A-01 (Henry's 5)": {v["piece_id"] for v in meta.values()},
        "BL-18 T2": set(json.loads((CAL / "bl18_summary.json").read_text())["t2_pieces"]),
        "BL-18b = DF-13 dev = BL-27 dev = BL-36 dev": {r["piece"] for r in b18b_rows}
        | {r["piece"] for r in r36d},
        "DF-13 held-out": {r["piece"] for r in d13},
        "BL-27 held-out": {r["piece"] for r in r27},
        "BL-36 held-out": {r["piece"] for r in r36h},
    }
    ids = {"A-01 floor": {str(r["ref_id"]) for r in floor},
           "BL-18": {str(r["id"]) for r in b18}, "BL-18b": {str(r["id"]) for r in b18b_rows},
           "DF-13": {str(r["id"]) for r in d13}, "BL-27": {str(r["id"]) for r in r27},
           "BL-36": {str(r["id"]) for r in r36h} | {str(r["id"]) for r in r36d}}
    return {"pieces": pieces, "ids": ids}


# ----------------------------------------------------------------------------- workers


def _same(a, b, ca, cb) -> bool:
    """Whole-recording identity of two aligned performances (and their correctness)."""
    from pianolens.report.build import bar_labels

    pa = [tuple(x) for x in a.alignment.pairs.tolist()]
    pb = [tuple(x) for x in b.alignment.pairs.tolist()]
    return (pa == pb and np.array_equal(a.score.notes, b.score.notes)
            and np.array_equal(a.score.measures, b.score.measures)
            and bar_labels(a.score) == bar_labels(b.score)
            and ca.bars.equals(cb.bars) and ca.notes.equals(cb.notes)
            and ca.score_notes.equals(cb.score_notes)
            and json.dumps(ca.summary, sort_keys=True, default=str)
            == json.dumps(cb.summary, sort_keys=True, default=str))


def _note_detail(cr, labels: list[str], keep: set[str]) -> dict:
    """Score and performed notes in the bars ``keep`` (labels)."""
    sn = cr.score_notes
    sl = sn["measure_index"].map(lambda i: labels[i] if 0 <= i < len(labels) else "")
    s = sn[sl.isin(keep)]
    pn = cr.notes
    pl = pn["measure_index"].map(lambda i: labels[i] if 0 <= i < len(labels) else "")
    p = pn[pl.isin(keep)]
    return {"score": list(zip(s["score_id"].astype(str), s["label"].astype(str),
                              s["performance_id"].astype(str), sl[s.index], strict=True)),
            "perf": list(zip(p["performance_id"].astype(str), p["label"].astype(str),
                             p["score_id"].astype(str), pl[p.index], strict=True))}


def _bars_counts(table: pd.DataFrame) -> dict[str, tuple]:
    t = table[table["n_score_notes"] > 0]
    return {r.label: (int(r.n_score_notes), int(r.n_missed), int(r.n_wrong_pitch),
                      int(r.n_extra)) for r in t.itertuples(index=False)}


def inject_edges(perf, cr, labels: list[str], bars: list[str], rng):
    """3 wrong pitches (BL-18b deltas) in each of ``bars`` among the clean copy's correct notes
    that are in ``perf`` (the cut copy). Returns (performance copy, injected bar labels)."""
    from pianolens.data.perturb import _PIANO_HI, _PIANO_LO, _same_pitch_busy, chord_clusters

    m18 = b18b()
    notes = perf.notes.copy()
    pos = {str(p): i for i, p in enumerate(notes["id"].astype(str))}
    chord = chord_clusters(notes["onset_sec"].astype(float), 0.05)
    n = cr.notes
    corr = n[(n["label"] == "correct") & (n["measure_index"] >= 0)]
    deltas = np.array([d for d, _ in m18.TARGETED_DELTAS])
    pw = np.array([w for _, w in m18.TARGETED_DELTAS])
    pw = pw / pw.sum()
    done_bars = []
    for lab in bars:
        i = labels.index(lab)
        ks = [pos[str(p)] for p in corr.loc[corr["measure_index"] == i, "performance_id"]
              if str(p) in pos]
        if len(ks) < m18.TARGETED_WRONG:
            continue
        done = {}
        for k in rng.permutation(ks):
            if len(done) >= m18.TARGETED_WRONG:
                break
            cp = set(notes["pitch"][chord == chord[k]].tolist())
            t0 = float(notes["onset_sec"][k])
            t1 = t0 + float(notes["duration_sec"][k])
            for _ in range(20):
                new = int(notes["pitch"][k]) + int(rng.choice(deltas, p=pw))
                if (_PIANO_LO <= new <= _PIANO_HI and new not in cp
                        and not _same_pitch_busy(notes, new, t0, t1)):
                    done[int(k)] = (int(notes["pitch"][k]), new)
                    notes["pitch"][k] = new
                    break
        if len(done) == m18.TARGETED_WRONG:
            done_bars.append(lab)
        else:
            for k, (old, _) in done.items():
                notes["pitch"][k] = old
    return dataclasses.replace(perf, notes=notes,
                               performance_id=f"{perf.performance_id}#inject"), done_bars


def played_table(labels, truth, found, removed_pids, clean_pb) -> dict[str, dict]:
    """Played bars of a copy: distance to the recorded edge, side, lost-notes flag."""
    idx = {lab: i for i, lab in enumerate(labels)}
    heard = sorted(idx[b] for b, s in truth.items() if s == "heard" and b in idx)
    gone = sorted(idx[b] for b, s in truth.items() if s in ("not_heard", "cut") and b in idx)
    if not heard:
        return {}
    first, last = heard[0], heard[-1]
    start_side = any(g < first for g in gone)
    end_side = any(g > last for g in gone)
    by_bar: dict[str, list[str]] = {}
    for pid, lab in clean_pb.items():
        by_bar.setdefault(lab, []).append(pid)
    out = {}
    for b, s in truth.items():
        if s != "heard" or not found.get(b, False) or b not in idx:
            continue
        i = idx[b]
        ds = []
        if start_side:
            ds.append((i - first, "start"))
        if end_side:
            ds.append((last - i, "end"))
        d, side = min(ds) if ds else (10**6, "none")
        lost = any(p in removed_pids for p in by_bar.get(b, []))
        out[b] = {"d": int(d), "side": side, "lost": bool(lost)}
    return out


def target_one(job: dict) -> dict:
    _quiet()
    from pianolens.align import align_performance
    from pianolens.features.correctness import correctness

    m = b36()
    sc, perf = b18b()._load(job)
    apc = align_performance(sc, perf)
    crc = correctness(apc)
    apn = align_performance(sc, perf, partial=True)
    crn = correctness(apn)
    rs = apn.score.meta["recorded_span"]
    out = {**job, "C": m._summ(apc, crc), "N": m._summ(apn, crn),
           "whole_N": bool(rs["whole"]), "refined_N": bool(rs.get("refined")),
           "whole_identical": bool(rs["whole"] and not rs.get("refined")
                                   and _same(apc, apn, crc, crn))}
    out["suspect"] = out["C"]["suspect"]
    if out["suspect"]:
        return out
    labels = out["C"]["labels"]
    out["bar_class"] = m.bar_classes(apc.score)
    found = m._found(out["C"]["table"])
    variant = out["C"]["variant"] or "auto"
    rng = np.random.default_rng([m.TRUNC_SEED, zlib.crc32(job["id"].encode())])
    irng = np.random.default_rng([INJECT_SEED, zlib.crc32(job["id"].encode())])
    out["cuts"] = {}
    notes = apc.performance.notes
    kinds = list(m.KINDS) + (["short"] if job.get("short_excerpts") else [])
    for kind in kinds:
        if kind == "short":
            win = short_window(crc, rng)
        else:
            win = m.cut_window(crc, kind, rng)
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
        pt_ = played_table(labels, tr, found, removed, out["C"]["perf_bar"])
        c = {"t_lo": lo, "t_hi": hi, "n_kept": int(keep.sum()), "n_removed": int((~keep).sum()),
             "truth": tr, "played": pt_}
        near = {b for b, v in pt_.items() if v["d"] <= NEAR}
        c["detail_clean"] = _note_detail(crc, labels, near)
        for meth, kw in (("C", {"repeats": variant}), ("N", {"repeats": variant, "partial": True}),
                         ("Na", {"partial": True})):
            ap2 = align_performance(sc, tp, **kw)
            cr2 = correctness(ap2)
            c[meth] = m._summ(ap2, cr2)
            if meth == "N":
                from pianolens.report.build import bar_labels

                c["detail_N"] = _note_detail(cr2, bar_labels(ap2.score), near)
        edge = [b for b, v in pt_.items() if v["d"] == 0]
        ok = [b for b in edge if _bars_counts(out["C"]["table"]).get(b, (0, 0, 1, 0))[2] == 0]
        if ok:
            ip, done = inject_edges(tp, crc, labels, ok, irng)
            if done:
                api = align_performance(sc, ip, repeats=variant, partial=True)
                c["inject"] = {"bars": done, "N": m._summ(api, correctness(api))}
        out["cuts"][kind] = c
    return out


def short_window(cr, rng):
    """Information: an excerpt of 4-7 graded bars at bar boundaries."""
    m = b36()
    fl = m._graded_first_last(cr)
    n = len(fl)
    length = int(rng.integers(SHORT_EXCERPT_BARS[0], SHORT_EXCERPT_BARS[1] + 1))
    if n < length + 2:
        return None
    k0 = int(rng.integers(1, n - length))
    return m._bar_boundary(fl, k0), m._bar_boundary(fl, k0 + length)


# ----------------------------------------------------------------------------- wrong-piece probe


def _key(score) -> tuple:
    import partitura as pt

    part = getattr(score, "part", None)
    ks = sorted(part.iter_all(pt.score.KeySignature), key=lambda k: k.start.t) if part else []
    return (int(ks[0].fifths), str(ks[0].mode or "")) if ks else (0, "")


def probe_one(args: tuple) -> list[dict]:
    """Information (BL-36 audit section 7, extended): one take of piece A as the full take, a
    4-7-bar and an 8-bar excerpt (bar boundaries), aligned with ``partial`` off and on to A's
    score and to each score in ``others`` (same key signature). Dice match ratio per pair."""
    _quiet()
    from pianolens.align import align
    from pianolens.align.core import match_ratio

    job, others = args
    m = b36()
    sc, perf = b18b()._load(job)
    from pianolens.align import align_performance
    from pianolens.features.correctness import correctness

    ap = align_performance(sc, perf)
    cr = correctness(ap)
    rng = np.random.default_rng([HELDOUT_SEED, zlib.crc32(job["id"].encode())])
    fl = m._graded_first_last(cr)
    notes = ap.performance.notes
    takes = {"full": notes}
    for name, length in (("4-7 bars", int(rng.integers(4, 8))), ("8 bars", 8)):
        if len(fl) >= length + 2:
            k0 = int(rng.integers(1, len(fl) - length))
            lo, hi = m._bar_boundary(fl, k0), m._bar_boundary(fl, k0 + length)
            takes[name] = notes[(notes["onset_sec"] >= lo) & (notes["onset_sec"] < hi)]
    scores = [("right", job["piece"], sc)] + [
        ("wrong", o["piece"], b18b()._load(o)[0]) for o in others]
    out = []
    for name, na in takes.items():
        p = dataclasses.replace(perf, notes=na.copy())
        for rel, piece, s in scores:
            for partial in (False, True):
                try:
                    res = align(s, p, partial=partial)
                    ratio = match_ratio(res.alignment, len(res.score_note_array), len(na))
                except Exception as e:  # noqa: BLE001 - a failed probe is recorded
                    ratio = float("nan")
                    piece = f"{piece} ({type(e).__name__})"
                out.append({"source": job["piece"], "take": name, "relation": rel,
                            "score_piece": piece, "partial": partial, "ratio": ratio})
    return out


def wrong_piece_probe(jobs: list[dict], workers: int) -> pd.DataFrame:
    by_piece: dict[str, dict] = {}
    for j in jobs:
        if j["role"] == "target" and j["family"] == "transkun":
            by_piece.setdefault(j["piece"], j)
    keys = {}
    for pc, j in by_piece.items():
        keys[pc] = _key(b18b()._load(j)[0])
    args = [(j, [by_piece[o] for o in by_piece if o != pc and keys[o] == keys[pc]])
            for pc, j in sorted(by_piece.items())]
    rows = []
    with ProcessPoolExecutor(workers) as ex:
        for r in ex.map(probe_one, args):
            rows.extend(r)
    df = pd.DataFrame(rows)
    df.attrs["keys"] = {k: list(v) for k, v in keys.items()}
    return df


# ----------------------------------------------------------------------------- evaluation


def _tiers(table: pd.DataFrame, experts: list[pd.DataFrame], drop_missed: set[str] | None = None,
           cap: set[str] | None = None, untier: set[str] | None = None) -> dict[str, str]:
    """Rule P tiers (runs untiered) of a bar table, with an edge policy applied to the bars
    named: ``drop_missed`` (missed notes do not count), ``cap`` (at most notable), ``untier``."""
    tr = b36().bl27().tiers_runs(table, experts, 0)  # runs from the real missed counts
    tiers = dict(zip(tr["label"], tr["tier"], strict=True))
    if drop_missed:  # tiers of the policy bars without their missed notes (runs unchanged)
        t = table.copy()
        t.loc[t["label"].isin(drop_missed), "n_missed"] = 0
        b18 = b36().bl27()._mod("bl18", "calibrate_strong_tier_bl18.py")
        tm = b18.tiers(t, experts, "R1(0)", None)
        in_run = dict(zip(tr["label"], tr["in_run"], strict=True))
        for lab, tier in zip(tm["label"], tm["tier"], strict=True):
            if lab in drop_missed and not in_run.get(lab, False):
                tiers[lab] = tier
    for b in cap or ():
        if tiers.get(b) == "strong":
            tiers[b] = "notable"
    for b in untier or ():
        if b in tiers:
            tiers[b] = "none"
    return tiers


def span_edges(summ: dict, k: int = 1) -> set[str]:
    """Edge bars as the report would know them: the first (last) ``k`` graded bars of N's score
    when the span left out bars before (after) it."""
    sp = summ.get("span") or {}
    labels = summ["labels"]
    if sp.get("whole", True) or not labels:
        return set()
    t = summ["table"]
    graded = [r.label for r in t.itertuples(index=False) if r.n_score_notes > 0]
    out = set()
    pos = {d.get("position") for d in sp.get("not_recorded", [])}
    if "start" in pos:
        out |= set(graded[:k])
    if "end" in pos:
        out |= set(graded[-k:])
    return out


POLICIES = ("none", "missed_low_conf", "cap_notable", "untier", "missed_low_conf_k2",
            "cap_notable_k2", "untier_k2")


def policy_tiers(summ: dict, experts, policy: str) -> dict[str, str]:
    k = 2 if policy.endswith("_k2") else 1
    base = policy.removesuffix("_k2")
    e = span_edges(summ, k)
    if base == "none" or not e:
        return _tiers(summ["table"], experts)
    if base == "missed_low_conf":
        return _tiers(summ["table"], experts, drop_missed=e)
    if base == "cap_notable":
        return _tiers(summ["table"], experts, cap=e)
    return _tiers(summ["table"], experts, untier=e)


def bar_rows(rows: list[dict]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Per played bar of every copy: d, side, lost, tiers (clean, C, Na, N under each policy);
    and per injected edge bar: tier under each policy."""
    experts: dict[tuple, list] = {}
    for r in sorted((r for r in rows if r["role"] == "expert" and not r["suspect"]),
                    key=lambda r: r["order"]):
        experts.setdefault((r["piece"], r["family"]), []).append(r["table"])
    out, inj = [], []
    for r in rows:
        if r["role"] != "target" or r["suspect"]:
            continue
        ex = experts.get((r["piece"], r["family"]), [])
        clean = _tiers(r["C"]["table"], ex)
        for kind, c in (r.get("cuts") or {}).items():
            tC = _tiers(c["C"]["table"], ex)
            tNa = _tiers(c["Na"]["table"], ex)
            tN = {p: policy_tiers(c["N"], ex, p) for p in POLICIES}
            edgesN = span_edges(c["N"])
            for b, st in c["truth"].items():
                if st != "cut":
                    continue
                d = {"piece": r["piece"], "family": r["family"], "id": r["id"], "kind": kind,
                     "label": b, "d": -1, "side": "cut", "lost": True, "n_edge": b in edgesN,
                     "clean": clean.get(b, "none"), "C": tC.get(b, "none"),
                     "Na": tNa.get(b, "none")}
                for p in POLICIES:
                    d[f"N_{p}"] = tN[p].get(b, "none")
                out.append(d)
            for b, v in c["played"].items():
                d = {"piece": r["piece"], "family": r["family"], "id": r["id"], "kind": kind,
                     "label": b, "d": v["d"], "side": v["side"], "lost": v["lost"],
                     "n_edge": b in edgesN, "clean": clean.get(b, "none"),
                     "C": tC.get(b, "none"), "Na": tNa.get(b, "none")}
                for p in POLICIES:
                    d[f"N_{p}"] = tN[p].get(b, "none")
                out.append(d)
            if "inject" in c:
                s = c["inject"]["N"]
                ti = {p: policy_tiers(s, ex, p) for p in POLICIES}
                e = span_edges(s)
                for b in c["inject"]["bars"]:
                    d = {"piece": r["piece"], "family": r["family"], "id": r["id"],
                         "kind": kind, "label": b, "n_edge": b in e,
                         "max_expert_wrong": max([int(t.loc[t["label"] == b, "n_wrong_pitch"]
                                                      .max()) if (t["label"] == b).any() else 0
                                                  for t in ex] or [0])}
                    for p in POLICIES:
                        d[f"N_{p}"] = ti[p].get(b, "none")
                    inj.append(d)
    return pd.DataFrame(out), pd.DataFrame(inj)


def _bucket(d: int) -> str:
    return "cut" if d < 0 else "0" if d == 0 else "1" if d == 1 else "2-5" if d <= 5 else ">5"


def _per_piece_rate(df: pd.DataFrame, col: str, val=("strong",)) -> pd.Series:
    g = df.assign(x=df[col].isin(val)).groupby("piece")["x"].agg(["sum", "count"])
    return g["sum"] / g["count"]


def _summ_rate(df: pd.DataFrame, col: str, val=("strong",)) -> dict:
    per = _per_piece_rate(df, col, val)
    m = b36()
    return {"mean_over_pieces": float(per.mean()) if len(per) else np.nan,
            "pooled": float(df[col].isin(val).mean()) if len(df) else np.nan,
            "n_bars": int(len(df)), "n_pieces": int(len(per)), "boot95": m._boot(per)}


def edge_report(bars: pd.DataFrame, inj: pd.DataFrame) -> dict:
    out: dict = {}
    bars = bars.assign(bucket=bars["d"].map(_bucket))
    cols = ["clean", "C", "Na"] + [f"N_{p}" for p in POLICIES]
    for lost in ("all", "no_loss"):
        g0 = bars if lost == "all" else bars[~bars["lost"]]
        for bk in ("cut", "0", "1", "2-5", ">5"):
            g = g0[g0["bucket"] == bk]
            out[f"{lost}:d={bk}"] = {c: _summ_rate(g, c) for c in cols}
        e = g0[g0["bucket"] == "0"]
        for kind in sorted(e["kind"].unique()):
            out[f"{lost}:d=0:kind={kind}"] = {c: _summ_rate(e[e["kind"] == kind], c)
                                              for c in cols}
        for fam in sorted(e["family"].unique()):
            out[f"{lost}:d=0:family={fam}"] = {c: _summ_rate(e[e["family"] == fam], c)
                                               for c in cols}
    if len(inj):
        out["inject"] = {f"N_{p}": {"strong": _summ_rate(inj, f"N_{p}"),
                                    "notable_plus": _summ_rate(inj, f"N_{p}",
                                                               ("strong", "notable"))}
                         for p in POLICIES}
        out["inject"]["n_edge_known_to_N"] = float(inj["n_edge"].mean())
    out["edge_known_to_N"] = float(bars.loc[bars["d"] == 0, "n_edge"].mean())
    out["cut_bar_is_N_edge"] = float(bars.loc[bars["d"] < 0, "n_edge"].mean()) \
        if (bars["d"] < 0).any() else np.nan
    return out


def mechanism(rows: list[dict], bars: pd.DataFrame) -> dict:
    """Edge bars (d = 0) strong under N (no policy) and not in the clean copy: what their notes
    did. Score notes: N label; for notes correct in the clean copy and not correct under N,
    where the clean performed note went under N (same bar / other bar / extra / removed by the
    cut). Performed notes N puts in the bar as extra: their clean status."""
    sel = bars[(bars["d"] == 0) & (bars["N_none"] == "strong") & (bars["clean"] != "strong")]
    sel = sel[sel["kind"] != "short"]
    want = set(zip(sel["id"], sel["kind"], sel["label"], strict=True))
    cnt: dict[str, int] = {}

    def add(k: str, n: int = 1) -> None:
        cnt[k] = cnt.get(k, 0) + n

    for r in rows:
        if r["role"] != "target" or r["suspect"]:
            continue
        for kind, c in (r.get("cuts") or {}).items():
            bs = {b for (i, k, b) in want if i == r["id"] and k == kind}
            if not bs:
                continue
            n_pb = c["N"]["perf_bar"]
            clean_s = {sid: (lab, pid, bar) for sid, lab, pid, bar in c["detail_clean"]["score"]}
            n_s = {sid: (lab, pid, bar) for sid, lab, pid, bar in c["detail_N"]["score"]}
            n_p = {pid: (lab, sid, bar) for pid, lab, sid, bar in c["detail_N"]["perf"]}
            clean_p = {pid: (lab, sid, bar) for pid, lab, sid, bar in c["detail_clean"]["perf"]}
            for b in bs:
                add("bars")
                lost_flag = bool(c["played"][b]["lost"])
                add(f"bars_lost_notes={lost_flag}")
                for sid, (lab, _pid, bar) in n_s.items():
                    if bar != b:
                        continue
                    add(f"score_N_{lab}")
                    if sid not in clean_s:
                        add("score_not_in_clean_bar")
                        continue
                    clab, cpid, _ = clean_s[sid]
                    if clab == "correct" and lab != "correct":
                        if cpid in n_pb:
                            add("lost_correct:clean_note_matched_to_other_bar"
                                if n_pb[cpid] != b else "lost_correct:clean_note_matched_in_bar")
                        elif cpid in n_p:
                            add(f"lost_correct:clean_note_{n_p[cpid][0]}_under_N")
                        else:
                            add("lost_correct:clean_note_unmatched_elsewhere_or_cut")
                    elif clab != "correct":
                        add(f"score_clean_{clab}")
                for pid, (lab, _sid, bar) in n_p.items():
                    if bar != b or lab == "correct":
                        continue
                    add(f"perf_N_{lab}")
                    if pid in clean_p:
                        cl, _, cb = clean_p[pid]
                        add(f"perf_N_{lab}:clean_{cl}" + ("_same_bar" if cb == b else "_other"))
                    else:
                        add(f"perf_N_{lab}:clean_outside_near_bars")
    return cnt


# ----------------------------------------------------------------------------- main


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", choices=("dev", "heldout"), required=True)
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--from-cache", action="store_true")
    ap.add_argument("--tag", default="")
    ap.add_argument("--draw-only", action="store_true")
    ap.add_argument("--limit-targets", type=int, default=0)
    ap.add_argument("--reachability", type=int, default=0)
    ap.add_argument("--probe", action="store_true",
                    help="held-out: run the wrong-piece probe (information) on the cached jobs")
    args = ap.parse_args()
    _quiet()
    OUT.mkdir(parents=True, exist_ok=True)
    stem = args.set + (f"_{args.tag}" if args.tag else "")
    cache = OUT / f"{stem}_rows.pkl"
    if args.probe:
        blob = pickle.loads(cache.read_bytes())
        jobs = [{k: r[k] for k in ("piece", "piece_id", "family", "role", "order", "id", "midi",
                                   "score")} for r in blob["rows"] if r["role"] == "target"]
        df = wrong_piece_probe(jobs, args.workers)
        df.to_csv(OUT / f"{stem}_probe.csv", index=False)
        g = df.groupby(["take", "relation", "partial"])["ratio"].agg(["min", "max", "count"])
        print(g.to_string())
        return
    if args.from_cache:
        blob = pickle.loads(cache.read_bytes())
    else:
        info: dict = {}
        if args.set == "dev":
            jobs, rows = dev_jobs()
            if args.limit_targets:
                seen: dict[tuple, int] = {}
                keep = []
                for j in jobs:
                    k = (j["piece"], j["family"])
                    if seen.get(k, 0) < args.limit_targets:
                        keep.append(j)
                        seen[k] = seen.get(k, 0) + 1
                jobs = keep
        else:
            jobs, info = heldout_jobs(args.workers)
            (OUT / "heldout_draw.json").write_text(json.dumps(
                {k: v for k, v in info.items() if k != "all_flags"}, indent=1, default=str))
            (OUT / "heldout_repeat_flags.json").write_text(
                json.dumps(info["all_flags"], indent=1, default=str))
            if args.draw_only:
                print(json.dumps({k: v for k, v in info.items() if k not in ("all_flags",)},
                                 indent=1, default=str))
                return
            rows = []
        for j in jobs:
            j["short_excerpts"] = True
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
    rows = blob["rows"]
    res = evaluate(rows)
    for k, t in res.pop("_tables").items():
        t.to_csv(OUT / f"{stem}_{k}.csv", index=False)
    if args.reachability:
        res["reachability"] = reachability(pd.read_csv(OUT / f"{stem}_bars.csv"),
                                           pd.read_csv(OUT / f"{stem}_inject.csv"),
                                           args.reachability)
    summ = {"set": args.set, "tag": args.tag, "failed": blob.get("failed", []),
            "info": blob.get("info"), "pieces": sorted({r["piece"] for r in rows}), **res}
    (OUT / f"{stem}_summary.json").write_text(json.dumps(summ, indent=1, default=float))
    print(json.dumps({k: summ[k] for k in ("set", "tag", "failed", "verdict", "whole")},
                     indent=1, default=float))


def evaluate(rows: list[dict]) -> dict:
    m = b36()
    targets = [r for r in rows if r["role"] == "target"]
    ok = [r for r in targets if not r["suspect"]]
    # BL-36 rows (no regression): drop the information kind "short" from the copies
    rows36 = []
    for r in rows:
        if r["role"] == "target" and r.get("cuts"):
            r = {**r, "cuts": {k: v for k, v in r["cuts"].items() if k != "short"}}
        rows36.append(r)
    e36 = m.evaluate(rows36)
    bars, inj = bar_rows(rows)
    out = {"n_targets": len(ok), "n_targets_suspect": len(targets) - len(ok),
           "whole": {"n_whole_N": sum(r["whole_N"] for r in ok),
                     "n_whole_unrefined": sum(r["whole_N"] and not r["refined_N"] for r in ok),
                     "n_whole_identical": sum(r["whole_identical"] for r in ok)},
           "bl36_criteria": e36["criteria"], "bl36_verdict": e36["verdict"],
           "bl36_natural": e36["natural"],
           "edge": edge_report(bars, inj), "mechanism": mechanism(rows, bars)}
    out["criteria"] = criteria(bars, inj, e36, out["whole"])
    cr = out["criteria"]
    failed = [k for k in ("W1_whole_identical", "B_bl36_rows") if not cr[k]["pass"]]
    if cr["adopted_policy"] is None:
        failed.append("no policy passes E1, E2, D1, D2")
    out["verdict"] = {"pass": not failed, "failed": failed, "policy": cr["adopted_policy"]}
    out["loo"] = loo_policy(bars, inj)
    short = [d for r in ok for k, c in (r.get("cuts") or {}).items() if k == "short"
             for d in [c]]
    out["n_short_excerpts"] = len(short)
    out["_tables"] = {"bars": bars, "inject": inj, **e36["_tables"]}
    return out


#: Pre-registered (README "Pre-registration"): policies in fallback order and the bars.
POLICY_ORDER = ("none", "missed_low_conf", "missed_low_conf_k2")  # least intervention first
REG_KINDS = ("start", "end", "both", "excerpt")  # "short" (4-7 bars) is information
E1_BAND = (-1.0, 1.5)  # edge bar strong rate minus the same bar uncut, points
E2_BAND = (None, 1.5)  # cut bar strong rate minus the same bar uncut, points (one-sided: a
# partly played bar has fewer notes to get wrong; hiding real errors is D1 / D2's job)
D1_MIN = -5.0  # injected edge bars strong under the policy minus under no policy, points
D2_MIN = -8.0  # the same for notable or strong


def loo_policy(bars: pd.DataFrame, inj: pd.DataFrame) -> dict:
    """Leave-one-piece-out: the adopted policy (and its row values) for each dropped piece."""
    out = {}
    for pc in sorted(set(bars["piece"])):
        b = bars[bars["piece"] != pc]
        i = inj[inj["piece"] != pc] if len(inj) else inj
        adopted = None
        vals = {}
        for p in POLICY_ORDER:
            rows = policy_rows(b, i, p)
            vals[p] = {k: v["value"] for k, v in rows.items() if k != "info"}
            if adopted is None and all(v["pass"] for k, v in rows.items() if k != "info"):
                adopted = p
        out[pc] = {"adopted": adopted, "values": vals}
    return out


def reachability(bars: pd.DataFrame, inj: pd.DataFrame, n: int = 2000, n_pieces: int = 16,
                 seed: int = 0) -> dict:
    """Share of resamples of ``n_pieces`` pieces in which each policy's rows pass, and which
    policy is adopted."""
    rng = np.random.default_rng(seed)
    pieces = sorted(set(bars["piece"]))
    adopted: dict[str, int] = {}
    row_pass: dict[str, int] = {}
    bp = {pc: g for pc, g in bars.groupby("piece")}
    ip = {pc: g for pc, g in inj.groupby("piece")} if len(inj) else {}
    for _ in range(n):
        pick = rng.choice(pieces, n_pieces, replace=True)
        b = pd.concat([bp[p].assign(piece=f"{p}#{k}") for k, p in enumerate(pick)])
        i = pd.concat([ip[p].assign(piece=f"{p}#{k}") for k, p in enumerate(pick) if p in ip])
        ad = None
        for p in POLICY_ORDER:
            rows = policy_rows(b, i, p)
            for k, v in rows.items():
                if k != "info":
                    row_pass[f"{p}:{k}"] = row_pass.get(f"{p}:{k}", 0) + int(v["pass"])
            if ad is None and all(v["pass"] for k, v in rows.items() if k != "info"):
                ad = p
        adopted[str(ad)] = adopted.get(str(ad), 0) + 1
    return {"n": n, "adopted": {k: v / n for k, v in adopted.items()},
            "row_pass": {k: v / n for k, v in sorted(row_pass.items())}}


def _diff_per_piece(df: pd.DataFrame, a: str, b: str, val=("strong",)) -> pd.Series:
    g = df.assign(x=df[a].isin(val).astype(float) - df[b].isin(val).astype(float))
    return 100 * g.groupby("piece")["x"].mean()


def policy_rows(bars: pd.DataFrame, inj: pd.DataFrame, policy: str) -> dict:
    col = f"N_{policy}"
    e = bars[(bars["d"] == 0) & (~bars["lost"]) & bars["kind"].isin(REG_KINDS)]
    cut = bars[(bars["d"] < 0) & bars["kind"].isin(REG_KINDS)]
    i = inj[inj["kind"].isin(REG_KINDS) & (inj["max_expert_wrong"] <= 1)] if len(inj) else inj
    out = {}

    def put(name, per, lo=None, hi=None):
        v = float(per.mean()) if len(per) else np.nan
        ok = (lo is None or v >= lo) and (hi is None or v <= hi)
        out[name] = {"value": v, "pass": bool(ok), "n_pieces": int(len(per)),
                     "bar": f"[{lo}, {hi}]", "per_piece": {k: float(x) for k, x in per.items()}}

    put("E1_edge_minus_uncut_pt", _diff_per_piece(e, col, "clean"), *E1_BAND)
    put("E2_cut_minus_uncut_pt", _diff_per_piece(cut, col, "clean"), *E2_BAND)
    put("D1_inject_strong_vs_none_pt", _diff_per_piece(i, col, "N_none"), D1_MIN, None)
    put("D2_inject_notable_vs_none_pt",
        _diff_per_piece(i, col, "N_none", ("strong", "notable")), D2_MIN, None)
    # information: absolute rates
    out["info"] = {"edge_strong": float(_per_piece_rate(e, col).mean()),
                   "edge_strong_uncut": float(_per_piece_rate(e, "clean").mean()),
                   "cut_strong": float(_per_piece_rate(cut, col).mean()) if len(cut) else np.nan,
                   "cut_strong_uncut": float(_per_piece_rate(cut, "clean").mean())
                   if len(cut) else np.nan,
                   "inject_strong": float(_per_piece_rate(i, col).mean()) if len(i) else np.nan,
                   "inject_notable_plus": float(_per_piece_rate(i, col, ("strong", "notable"))
                                                .mean()) if len(i) else np.nan}
    return out


def criteria(bars: pd.DataFrame, inj: pd.DataFrame, e36: dict,
             whole: dict | None = None) -> dict:
    """Registered rows: the first policy in ``POLICY_ORDER`` whose E1, E2, D1, D2 rows pass is
    adopted; W1 and the BL-36 rows (no regression) must pass whatever the policy."""
    out: dict = {"policies": {p: policy_rows(bars, inj, p) for p in POLICY_ORDER}}
    adopted = None
    for p in POLICY_ORDER:
        rows = out["policies"][p]
        if all(v["pass"] for k, v in rows.items() if k != "info"):
            adopted = p
            break
    out["adopted_policy"] = adopted
    if whole is not None:
        n_w = whole["n_whole_unrefined"]
        out["W1_whole_identical"] = {"value": whole["n_whole_identical"] / max(1, n_w),
                                     "n": n_w, "pass": whole["n_whole_identical"] == n_w}
    out["B_bl36_rows"] = {"pass": bool(e36["verdict"]["pass"]),
                          "failed": e36["verdict"]["failed"]}
    return out


if __name__ == "__main__":
    main()
