"""BL-20: tier A correctness at high note density.

Run::

    uv run python scripts/eval_correctness_density.py --part all [--workers 12] [--limit N]

Pre-registration: ``docs/specs/correctness-validation.md``, section "Pre-registration BL-20"
(copy and sha256 in ``experiments/2026-09-29-BL-20-density/artifacts/``).

* Part A (``--part a``): the F-02 synthetic evaluation (``data/processed/mistakes_v1``, built by
  ``scripts/build_mistake_set.py``) re-run with per-item output, so every bar and every injected
  mistake carries the local note rate of its neighbourhood (:func:`local_ioi`).
* Part B (``--part b``): a stress set of wrong pitches injected only in dense (< 100 ms) or sparse
  (> 200 ms) passages, either equal to a pitch played in the neighbouring chords ("N") or not
  ("O"); see :func:`stress_copy`.
* ``--part summary``: tables and cluster-bootstrap CIs from the per-item files.

Everything is written to ``--out`` (default the experiment's ``artifacts/``, gitignored).
Nothing here changes a production default: ``correctness`` is called with the windows under test.
"""

from __future__ import annotations

import argparse
import json
import logging
import time
import warnings
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd

log = logging.getLogger("eval_correctness_density")

CHORD_WINDOW_SEC = 0.03
"""Onsets within this window of a chord's first onset form one chord (local-IOI grouping)."""
BIN_EDGES = (0.0, 0.06, 0.10, 0.20, np.inf)
BIN_LABELS = ("<60", "60-100", "100-200", ">200")
WINDOWS = (0.05, 0.1)
MODES = ("aligned", "gt_alignment")
SEED = 20260929
STRESS_PER_COPY = 10
STRESS_MIN_GAP_SEC = 2.0
STRESS_CUT_SEC = 0.005
DEFAULT_OUT = Path("experiments/2026-09-29-BL-20-density/artifacts")
_STATE: dict = {}


# --------------------------------------------------------------------------- helpers


def chord_index(onsets: np.ndarray, window: float = CHORD_WINDOW_SEC) -> np.ndarray:
    """Chord index per onset (input order): sorted onsets within ``window`` of a chord's first
    onset share an index. Same rule as ``perturb.chord_clusters``."""
    from pianolens.data.perturb import chord_clusters

    return chord_clusters(np.asarray(onsets, dtype=float), window)


def local_ioi(onsets: np.ndarray, window: float = CHORD_WINDOW_SEC
              ) -> tuple[np.ndarray, np.ndarray]:
    """Local inter-onset interval (seconds) of each note, and its chord index.

    Chords are formed with :func:`chord_index`. The local IOI of chord k is the median of the
    gaps between consecutive chord onsets among chords k-2..k+2 (up to 4 gaps; NaN for a
    one-chord performance). Every note takes its chord's value.
    """
    onsets = np.asarray(onsets, dtype=float)
    if len(onsets) == 0:
        return np.empty(0), np.empty(0, dtype=int)
    ch = chord_index(onsets, window)
    n = ch.max() + 1
    first = np.full(n, np.inf)
    np.minimum.at(first, ch, onsets)
    gaps = np.diff(first)  # gap g_j between chord j and j+1
    val = np.full(n, np.nan)
    for k in range(n):
        lo, hi = max(0, k - 2), min(len(gaps), k + 2)  # gaps g_{k-2} .. g_{k+1}
        if hi > lo:
            val[k] = float(np.median(gaps[lo:hi]))
    return val[ch], ch


def density_bin(ioi: np.ndarray | float) -> np.ndarray:
    """Bin label per local IOI (seconds); ``"none"`` for NaN."""
    x = np.atleast_1d(np.asarray(ioi, dtype=float))
    idx = np.digitize(x, BIN_EDGES[1:-1], right=False)
    out = np.array(BIN_LABELS, dtype=object)[np.clip(idx, 0, len(BIN_LABELS) - 1)]
    out[~np.isfinite(x)] = "none"
    return out


# --------------------------------------------------------------------------- workers


def _init(root: str) -> None:
    warnings.filterwarnings("ignore")
    from pianolens.data import asap
    from pianolens.data.perturb import load_mistake_set

    index, get = load_mistake_set(root)
    _STATE["get"] = get
    _STATE["index"] = index.set_index("key")
    _STATE["clean_key"] = (index[index["rate"] == 0.0].set_index("performance_id")["key"]
                           .to_dict())  # fmt: skip
    _STATE["asap"] = asap.asap_index().set_index("performance_id", drop=False)
    _STATE["density"] = {}


def _source_density(source_id: str) -> tuple[dict, dict, dict]:
    """(note id -> local IOI, note id -> chord index, score id -> source note id) from the
    clean copy of a source performance."""
    if source_id in _STATE["density"]:
        return _STATE["density"][source_id]
    perf, lab = _STATE["get"](_STATE["clean_key"][source_id])
    ioi, ch = local_ioi(perf.notes["onset_sec"])
    ids = perf.notes["id"].astype(str).tolist()
    d_ioi = dict(zip(ids, ioi.tolist(), strict=True))
    d_ch = dict(zip(ids, ch.tolist(), strict=True))
    cor = lab.notes[lab.notes["label"] == "correct"]
    s2p = dict(zip(cor["score_id"], cor["performance_id"], strict=True))
    _STATE["density"][source_id] = (d_ioi, d_ch, s2p)
    return d_ioi, d_ch, s2p


def _bar_density(res, s2p: dict, d_ioi: dict) -> dict[int, float]:
    sn = res.score_notes
    vals: dict[int, list[float]] = {}
    for sid, mi in zip(sn["score_id"], sn["measure_index"], strict=True):
        if mi < 0 or sid not in s2p:
            continue
        v = d_ioi.get(s2p[sid], np.nan)
        if np.isfinite(v):
            vals.setdefault(int(mi), []).append(v)
    return {k: float(np.median(v)) for k, v in vals.items()}


def bar_sets(res, lab) -> tuple[set, set, set]:
    """(ground-truth, predicted, don't-care) bar sets for "any", exactly as
    ``scripts/eval_correctness.py`` ``score_one`` builds them."""
    gn = lab.notes
    inj = gn[gn["injected"]]
    nat = gn[~gn["injected"]]
    g_wrong = set(inj.loc[inj["label"] == "wrong_pitch", "performance_id"])
    g_missed = set(lab.missed.loc[lab.missed["injected"], "score_id"])
    nat_extra = set(nat.loc[nat["label"] == "extra", "performance_id"])
    nat_missed = set(lab.missed.loc[~lab.missed["injected"], "score_id"])
    pn, sn = res.notes, res.score_notes
    p_wrong = set(pn.loc[pn["label"] == "wrong_pitch", "performance_id"])
    p_extra = set(pn.loc[pn["label"] == "extra", "performance_id"])
    p_missed = set(sn.loc[sn["label"] == "missed", "score_id"])
    s_bar = dict(zip(sn["score_id"], sn["measure_index"], strict=True))
    p_bar = dict(zip(pn["performance_id"], pn["measure_index"], strict=True))
    gn_sid = dict(zip(gn["performance_id"], gn["score_id"], strict=True))

    def bs(ids):
        return {s_bar[i] for i in ids if s_bar.get(i, -1) >= 0}

    def bp(ids):
        return {p_bar[i] for i in ids if p_bar.get(i, -1) >= 0}

    g = (bs(gn_sid[i] for i in g_wrong)
         | bs(gn_sid.get(a, "") for a in inj.loc[inj["label"] == "extra", "anchor_id"])
         | bs(g_missed))  # fmt: skip
    p = bp(p_wrong) | bp(p_extra) | bs(p_missed)
    n = bp(nat_extra) | bs(nat_missed)
    return g, p, n


def _wrong_outcomes(res, lab, d_ioi: dict) -> list[dict]:
    """Outcome of every injected wrong pitch (performed note and intended score note)."""
    gn = lab.notes
    inj = gn[gn["injected"] & (gn["label"] == "wrong_pitch")]
    pn = res.notes.set_index("performance_id")
    sn = res.score_notes.set_index("score_id")
    out = []
    for pid, sid, orig in inj[["performance_id", "score_id", "original_pitch"]].itertuples(
            index=False):  # fmt: skip
        r = pn.loc[pid]
        lab_p, partner = str(r["label"]), str(r["score_id"])
        if lab_p == "wrong_pitch":
            outcome = "paired_intended" if partner == sid else "paired_other"
        elif lab_p == "correct":
            outcome = "absorbed"
        elif lab_p == "extra":
            outcome = "extra"
        else:
            outcome = lab_p
        s_lab = str(sn.loc[sid, "label"]) if sid in sn.index else "unknown"
        out.append({"performance_id": pid, "score_id": sid, "outcome": outcome,
                    "score_label": s_lab, "partner_score_id": partner,
                    "pitch": int(r["pitch"]), "orig_pitch": int(orig),
                    "partner_pitch": int(r["score_pitch"]),
                    "ioi": d_ioi.get(pid, np.nan)})  # fmt: skip
    return out


def _pred_wrong(res, lab, d_ioi: dict) -> list[dict]:
    """Every predicted wrong pitch with the ground-truth label of its performed note."""
    gn = lab.notes.set_index("performance_id")
    pn = res.notes[res.notes["label"] == "wrong_pitch"]
    out = []
    for pid, partner in pn[["performance_id", "score_id"]].itertuples(index=False):
        g = gn.loc[pid]
        gl = str(g["label"])
        kind = ("injected_" if bool(g["injected"]) else "natural_") + gl
        anchor = str(g["anchor_id"]) if gl == "extra" and bool(g["injected"]) else pid
        out.append({"performance_id": pid, "gt": kind,
                    "gt_intended_match": gl == "wrong_pitch" and str(g["score_id"]) == partner,
                    "ioi": d_ioi.get(anchor, np.nan)})  # fmt: skip
    return out


def _other_outcomes(res, lab, d_ioi: dict) -> list[dict]:
    """Labels given to injected extras (performed side) and injected missed notes (score side)."""
    gn = lab.notes
    pn = dict(zip(res.notes["performance_id"], res.notes["label"], strict=True))
    sn = dict(zip(res.score_notes["score_id"], res.score_notes["label"], strict=True))
    out = []
    ex = gn[gn["injected"] & (gn["label"] == "extra")]
    for pid, anc in ex[["performance_id", "anchor_id"]].itertuples(index=False):
        out.append({"type": "extra", "label": pn.get(pid, "unknown"),
                    "ioi": d_ioi.get(anc, np.nan)})  # fmt: skip
    mi = lab.missed[lab.missed["injected"]]
    for sid, opid in mi[["score_id", "original_performance_id"]].itertuples(index=False):
        out.append({"type": "missed", "label": sn.get(sid, "unknown"),
                    "ioi": d_ioi.get(opid, np.nan)})  # fmt: skip
    return out


def run_a(key: str) -> dict[str, list[dict]]:
    from pianolens.align import align_performance
    from pianolens.data import asap
    from pianolens.data.types import AlignedPerformance
    from pianolens.features.correctness import correctness

    warnings.filterwarnings("ignore")
    perf, lab = _STATE["get"](key)
    r = _STATE["index"].loc[key]
    src = str(r["performance_id"])
    d_ioi, _, s2p = _source_density(src)
    score = asap.load_asap_score(_STATE["asap"].loc[src])
    ap = align_performance(score, perf)
    base = {"key": key, "source": src, "rate": float(r["rate"]), "composer": r["composer"]}
    out: dict[str, list[dict]] = {"bars": [], "wrong": [], "pred_wrong": [], "other": []}
    modes = {"aligned": ap, "gt_alignment": AlignedPerformance(perf, ap.score, lab.alignment)}
    bar_d = None
    for mode, a in modes.items():
        for w in WINDOWS:
            res = correctness(a, wrong_pitch_window_sec=w)
            if bar_d is None:
                bar_d = _bar_density(res, s2p, d_ioi)
            g, p, n = bar_sets(res, lab)
            tag = {**base, "mode": mode, "window": w}
            for mi in res.bars["measure_index"].tolist():
                out["bars"].append({**tag, "measure_index": int(mi),
                                    "ioi": bar_d.get(int(mi), np.nan), "gt": mi in g,
                                    "pred": mi in p, "dont_care": mi in n})  # fmt: skip
            out["wrong"] += [{**tag, **d} for d in _wrong_outcomes(res, lab, d_ioi)]
            out["pred_wrong"] += [{**tag, **d} for d in _pred_wrong(res, lab, d_ioi)]
            out["other"] += [{**tag, **d} for d in _other_outcomes(res, lab, d_ioi)]
    return out


# --------------------------------------------------------------------------- part B


def stress_copy(perf, lab, cell: str, rng: np.random.Generator, s_bar: dict[str, int]):
    """Inject up to ``STRESS_PER_COPY`` wrong pitches into a clean copy for one stress cell.

    ``cell`` is ``"<dense|sparse>-<N|O>"``. Eligible notes are ground-truth ``correct`` notes
    whose local IOI is < 100 ms (dense) or > 200 ms (sparse). N: the new pitch is 1-2
    semitones from the true pitch and equals a pitch played in chords k-2..k+2 (not its own
    chord). O: 1-2 semitones away and equal to no pitch in chords k-2..k+2 (own chord included).
    Picked notes are at least ``STRESS_MIN_GAP_SEC`` apart and in different score bars
    (``s_bar``: score id -> bar row). A same-pitch note still sounding at the wrong onset is cut
    to end ``STRESS_CUT_SEC`` before it; the wrong note is cut to end that long before the next
    same-pitch onset.

    Returns ``(performance, labels)`` in the ``perturb`` conventions, or ``(None, None)`` when
    no note is eligible.
    """
    import dataclasses

    from pianolens.data.perturb import MistakeLabels, labels_to_alignment

    dens, kind = cell.split("-")
    notes = perf.notes.copy()
    on = notes["onset_sec"].astype(float)
    pitch = notes["pitch"].astype(int)
    ioi, ch = local_ioi(on)
    ids = notes["id"].astype(str)
    gl = lab.notes.set_index("performance_id")
    correct = np.array([gl.loc[i, "label"] == "correct" for i in ids])
    sids = np.array([str(gl.loc[i, "score_id"]) for i in ids], dtype=object)
    ok = correct & (ioi < 0.10 if dens == "dense" else ioi > 0.20)
    chord_p: dict[int, set] = {}
    for c, p in zip(ch.tolist(), pitch.tolist(), strict=True):
        chord_p.setdefault(c, set()).add(p)
    picks: list[tuple[int, int]] = []
    used_bars: set[int] = set()
    for i in rng.permutation(np.flatnonzero(ok)):
        if len(picks) >= STRESS_PER_COPY:
            break
        b = s_bar.get(sids[i], -1)
        if b < 0 or b in used_bars or any(abs(on[i] - on[j]) < STRESS_MIN_GAP_SEC
                                           for j, _ in picks):  # fmt: skip
            continue
        k = ch[i]
        near = set().union(*(chord_p.get(c, set()) for c in (k - 2, k - 1, k + 1, k + 2)))
        own = chord_p[k]
        cands = [pitch[i] + d for d in (-2, -1, 1, 2) if 21 <= pitch[i] + d <= 108]
        if kind == "N":
            cands = [q for q in cands if q in near and q not in own]
        else:
            cands = [q for q in cands if q not in near and q not in own]
        if not cands:
            continue
        picks.append((int(i), int(rng.choice(cands))))
        used_bars.add(b)
    if not picks:
        return None, None
    dur = notes["duration_sec"].astype(float).copy()
    for i, q in picks:
        same = np.flatnonzero(pitch == q)
        before = same[(on[same] < on[i]) & (on[same] + dur[same] > on[i] - STRESS_CUT_SEC)]
        for j in before:
            dur[j] = max(0.005, on[i] - STRESS_CUT_SEC - on[j])
        after = same[on[same] > on[i]]
        if len(after):
            nxt = on[after].min()
            dur[i] = max(0.005, min(dur[i], nxt - STRESS_CUT_SEC - on[i]))
        notes["pitch"][i] = q
    notes["duration_sec"] = dur
    ln = lab.notes.copy()
    pos = {p: k for k, p in enumerate(ln["performance_id"])}
    for i, _q in picks:
        k = pos[ids[i]]
        ln.loc[k, "label"] = "wrong_pitch"
        ln.loc[k, "injected"] = True
        ln.loc[k, "original_pitch"] = int(pitch[i])
    missed = lab.missed.copy()
    new_id = f"{perf.performance_id}#stress-{cell}"
    al = labels_to_alignment(ln, missed, lab.alignment.score_id, new_id)
    new_perf = dataclasses.replace(perf, performance_id=new_id, notes=notes)
    return new_perf, MistakeLabels(ln, missed, al, lab.spec, lab.seed)


CELLS = ("dense-N", "dense-O", "sparse-N", "sparse-O")


def run_b(args: tuple[int, str]) -> list[dict]:
    from pianolens.align import align_performance
    from pianolens.data import asap
    from pianolens.data.types import AlignedPerformance
    from pianolens.features.correctness import correctness

    warnings.filterwarnings("ignore")
    i_src, src = args
    ckey = _STATE["clean_key"][src]
    perf, lab = _STATE["get"](ckey)
    r = _STATE["index"].loc[ckey]
    score = asap.load_asap_score(_STATE["asap"].loc[src])
    ap0 = align_performance(score, perf)
    clean = {}
    for mode, a in {"aligned": ap0,
                    "gt_alignment": AlignedPerformance(perf, ap0.score, lab.alignment)}.items():
        for w in WINDOWS:
            clean[(mode, w)] = correctness(a, wrong_pitch_window_sec=w)
    s_bar = dict(zip(clean[("aligned", 0.1)].score_notes["score_id"],
                     clean[("aligned", 0.1)].score_notes["measure_index"], strict=True))
    d_ioi, _, _ = _source_density(src)
    rows = []
    for j, cell in enumerate(CELLS):
        rng = np.random.default_rng([SEED, i_src, j])
        sp, sl = stress_copy(perf, lab, cell, rng, s_bar)
        if sp is None:
            continue
        ap = align_performance(score, sp)
        for mode, a in {"aligned": ap,
                        "gt_alignment": AlignedPerformance(sp, ap.score, sl.alignment)}.items():
            for w in WINDOWS:
                res = correctness(a, wrong_pitch_window_sec=w)
                c0 = clean[(mode, w)].bars.set_index("measure_index")["n_errors"]
                c1 = res.bars.set_index("measure_index")["n_errors"]
                for d in _wrong_outcomes(res, sl, d_ioi):
                    b = s_bar.get(d["score_id"], -1)
                    d.update(key=sp.performance_id, source=src, composer=r["composer"],
                             cell=cell, mode=mode, window=w, bar=b,
                             bar_err_clean=int(c0.get(b, 0)), bar_err=int(c1.get(b, 0)),
                             match_ratio=res.summary["match_ratio"])  # fmt: skip
                    rows.append(d)
    return rows


# --------------------------------------------------------------------------- summary


def _prf(tp: float, fp: float, fn: float) -> tuple[float, float, float]:
    p = tp / (tp + fp) if tp + fp else np.nan
    r = tp / (tp + fn) if tp + fn else np.nan
    f = 2 * p * r / (p + r) if p + r else np.nan
    return p, r, f


def _boot_idx(groups: np.ndarray, n_boot: int, seed: int) -> list[np.ndarray]:
    rng = np.random.default_rng(seed)
    u = np.unique(groups)
    return [rng.choice(u, size=len(u), replace=True) for _ in range(n_boot)]


def summarise(out: Path, n_boot: int = 2000) -> dict:
    res: dict = {}
    bars = pd.read_parquet(out / "a_bars.parquet")
    bars["bin"] = density_bin(bars["ioi"].to_numpy())
    bars["dense"] = bars["bin"].isin(["<60", "60-100"])
    bars["tp"] = bars["gt"] & bars["pred"]
    bars["fp"] = bars["pred"] & ~bars["gt"] & ~bars["dont_care"]
    bars["fn"] = bars["gt"] & ~bars["pred"]
    # 1. bar any-error per bin
    agg = (bars.groupby(["mode", "window", "rate", "bin"])[["tp", "fp", "fn"]].sum()
           .reset_index())  # fmt: skip
    nb = bars.groupby(["mode", "window", "rate", "bin"]).size().rename("n_bars").reset_index()
    agg = agg.merge(nb)
    agg[["precision", "recall", "f1"]] = [list(_prf(*x)) for x in
                                          agg[["tp", "fp", "fn"]].to_numpy()]  # fmt: skip
    agg.to_csv(out / "a_bar_any_by_bin.csv", index=False)
    # pooled check against F-02 (must equal counts.csv "any")
    pooled = bars.groupby(["mode", "window", "rate"])[["tp", "fp", "fn"]].sum().reset_index()
    pooled.to_csv(out / "a_bar_any_pooled.csv", index=False)

    # bootstrap: dense (<100) minus >200, primary cell and gt_alignment
    boot_rows = []
    for mode in MODES:
        for rate in (0.02, 0.05, 0.10):
            b = bars[(bars["mode"] == mode) & (bars["window"] == 0.1) & (bars["rate"] == rate)]
            per = (b.assign(grp=np.where(b["dense"], "dense",
                                         np.where(b["bin"] == ">200", "sparse", "mid")))
                   .groupby(["source", "grp"])[["tp", "fp", "fn"]].sum())  # fmt: skip
            srcs = per.index.get_level_values(0).unique().to_numpy()
            full = per.groupby(level=1).sum()
            f_d = _prf(*full.loc["dense"])[2] if "dense" in full.index else np.nan
            f_s = _prf(*full.loc["sparse"])[2] if "sparse" in full.index else np.nan
            diffs = []
            for idx in _boot_idx(srcs, n_boot, SEED):
                cnt = pd.Series(idx).value_counts()
                w = per.index.get_level_values(0).map(cnt).fillna(0).to_numpy()
                s = (per.mul(w, axis=0)).groupby(level=1).sum()
                if "dense" in s.index and "sparse" in s.index:
                    diffs.append(_prf(*s.loc["dense"])[2] - _prf(*s.loc["sparse"])[2])
            lo, hi = np.nanpercentile(diffs, [2.5, 97.5])
            boot_rows.append({"mode": mode, "window": 0.1, "rate": rate, "f1_dense": f_d,
                              "f1_sparse": f_s, "diff": f_d - f_s, "ci_lo": lo, "ci_hi": hi,
                              "n_boot": len(diffs)})  # fmt: skip
    pd.DataFrame(boot_rows).to_csv(out / "a_bar_any_dense_vs_sparse_boot.csv", index=False)
    res["a_boot"] = boot_rows

    # 2. injected wrong pitch outcomes per bin
    wr = pd.read_parquet(out / "a_wrong.parquet")
    wr["bin"] = density_bin(wr["ioi"].to_numpy())
    wr_d = wr.assign(bin=np.where(wr["bin"].isin(["<60", "60-100"]), "<100", wr["bin"]))
    tabs = []
    for w_df, tag in ((wr, "bins"), (wr_d[wr_d["bin"] == "<100"], "dense")):
        t = (w_df.groupby(["mode", "window", "rate", "bin", "outcome"]).size()
             .unstack("outcome", fill_value=0))  # fmt: skip
        t["n"] = t.sum(axis=1)
        tabs.append(t.reset_index().assign(table=tag))
    wt = pd.concat(tabs, ignore_index=True)
    wt.to_csv(out / "a_wrong_outcomes_by_bin.csv", index=False)

    # score-side label of the intended note when the wrong pitch was not paired with it
    ws = (wr[wr["outcome"] != "paired_intended"]
          .groupby(["mode", "window", "rate", "outcome", "score_label"]).size()
          .rename("n").reset_index())  # fmt: skip
    ws.to_csv(out / "a_wrong_unpaired_score_label.csv", index=False)

    # 3. predicted wrong pitches: false merges per bin
    pw = pd.read_parquet(out / "a_pred_wrong.parquet")
    pw["bin"] = density_bin(pw["ioi"].to_numpy())
    pt_ = (pw.groupby(["mode", "window", "rate", "bin", "gt"]).size()
           .unstack("gt", fill_value=0).reset_index())  # fmt: skip
    pt_.to_csv(out / "a_pred_wrong_by_bin.csv", index=False)
    oth = pd.read_parquet(out / "a_other.parquet")
    oth["bin"] = density_bin(oth["ioi"].to_numpy())
    ot = (oth.groupby(["mode", "window", "rate", "type", "bin", "label"]).size()
          .unstack("label", fill_value=0).reset_index())  # fmt: skip
    ot.to_csv(out / "a_other_by_bin.csv", index=False)

    # note counts per bin (how much of the corpus is dense)
    if (out / "a_note_density.parquet").is_file():
        nd = pd.read_parquet(out / "a_note_density.parquet")
        nd["bin"] = density_bin(nd["ioi"].to_numpy())
        nd.groupby(["composer", "bin"]).size().unstack(fill_value=0).to_csv(
            out / "a_notes_per_bin_by_composer.csv")

    # 4. part B
    if (out / "b_stress.parquet").is_file():
        sb = pd.read_parquet(out / "b_stress.parquet")
        sb["delta"] = sb["bar_err"] - sb["bar_err_clean"]
        sb["detected"] = sb["bar_err"] > 0
        sb["delta_cat"] = np.select([sb["delta"] <= 0, sb["delta"] == 1, sb["delta"] == 2],
                                    ["0_silent", "+1", "+2"], "+3_or_more")  # fmt: skip
        g = sb.groupby(["mode", "window", "cell"])
        tb = pd.DataFrame({
            "n": g.size(),
            "n_sources": g["source"].nunique(),
            "strict_recall": g["outcome"].apply(lambda s: (s == "paired_intended").mean()),
            "lenient_recall": g["outcome"].apply(
                lambda s: s.isin(["paired_intended", "paired_other", "extra"]).mean()),
            "paired_other": g["outcome"].apply(lambda s: (s == "paired_other").mean()),
            "absorbed": g["outcome"].apply(lambda s: (s == "absorbed").mean()),
            "extra": g["outcome"].apply(lambda s: (s == "extra").mean()),
            "bar_detected": g["detected"].mean(),
        })  # fmt: skip
        dc = (sb.groupby(["mode", "window", "cell", "delta_cat"]).size()
              .unstack("delta_cat", fill_value=0))  # fmt: skip
        dc = dc.div(dc.sum(axis=1), axis=0).add_prefix("delta_")
        tb = tb.join(dc).reset_index()
        # bootstrap CIs for strict recall and the dense-N minus sparse-O gap
        ci = []
        for (mode, w), gg in sb.groupby(["mode", "window"]):
            per = (gg.assign(hit=gg["outcome"] == "paired_intended")
                   .groupby(["source", "cell"])["hit"].agg(["sum", "count"]))  # fmt: skip
            srcs = per.index.get_level_values(0).unique().to_numpy()
            draws = {c: [] for c in CELLS}
            gap = []
            for idx in _boot_idx(srcs, n_boot, SEED + 1):
                cnt = pd.Series(idx).value_counts()
                wts = per.index.get_level_values(0).map(cnt).fillna(0).to_numpy()
                s = per.mul(wts, axis=0).groupby(level=1).sum()
                rec = s["sum"] / s["count"]
                for c in CELLS:
                    draws[c].append(rec.get(c, np.nan))
                gap.append(rec.get("dense-N", np.nan) - rec.get("sparse-O", np.nan))
            for c in CELLS:
                lo, hi = np.nanpercentile(draws[c], [2.5, 97.5])
                ci.append({"mode": mode, "window": w, "cell": c, "strict_ci_lo": lo,
                           "strict_ci_hi": hi})  # fmt: skip
            lo, hi = np.nanpercentile(gap, [2.5, 97.5])
            ci.append({"mode": mode, "window": w, "cell": "gap dense-N minus sparse-O",
                       "strict_ci_lo": lo, "strict_ci_hi": hi})  # fmt: skip
        tb = tb.merge(pd.DataFrame(ci), on=["mode", "window", "cell"], how="outer")
        tb.to_csv(out / "b_stress_summary.csv", index=False)
        # what the absorbed / paired_other notes were paired with
        sb["partner_delta"] = sb["partner_pitch"] - sb["orig_pitch"]
        sb.groupby(["mode", "window", "cell", "outcome"]).size().rename("n").reset_index().to_csv(
            out / "b_stress_outcomes.csv", index=False)
        res["b_rows"] = len(sb)
    (out / "summary.json").write_text(json.dumps(res, indent=2, default=float))
    return res


# --------------------------------------------------------------------------- main


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--part", choices=("a", "b", "summary", "all"), default="all")
    ap.add_argument("--root", default="data/processed/mistakes_v1")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--limit", type=int, default=0, help="first N source performances only")
    ap.add_argument("--n-boot", type=int, default=2000)
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    a.out.mkdir(parents=True, exist_ok=True)
    index = pd.read_csv(Path(a.root) / "index.csv", keep_default_na=False)
    srcs = index["performance_id"].drop_duplicates()
    if a.limit:
        srcs = srcs.iloc[: a.limit]
        index = index[index["performance_id"].isin(srcs)]
    t0 = time.time()
    if a.part in ("a", "all"):
        acc: dict[str, list] = {"bars": [], "wrong": [], "pred_wrong": [], "other": []}
        failed = []
        with ProcessPoolExecutor(a.workers, initializer=_init, initargs=(a.root,)) as ex:
            futs = {ex.submit(run_a, k): k for k in index["key"]}
            for n, f in enumerate(as_completed(futs), 1):
                try:
                    for k, v in f.result().items():
                        acc[k].extend(v)
                except Exception as e:  # noqa: BLE001 - count and continue
                    failed.append((futs[f], repr(e)))
                if n % 50 == 0:
                    log.info("A %d / %d (%.0f s)", n, len(futs), time.time() - t0)
        for k, v in acc.items():
            pd.DataFrame(v).to_parquet(a.out / f"a_{k}.parquet", index=False)
        log.info("A failed: %d %s", len(failed), failed[:3])
        # note-level density of the clean copies (corpus description)
        _init(a.root)
        rows = []
        for s in srcs:
            d_ioi, _, _ = _source_density(s)
            comp = index.loc[index["performance_id"] == s, "composer"].iloc[0]
            rows += [{"source": s, "composer": comp, "ioi": v} for v in d_ioi.values()]
        pd.DataFrame(rows).to_parquet(a.out / "a_note_density.parquet", index=False)
    if a.part in ("b", "all"):
        rows, failed = [], []
        with ProcessPoolExecutor(a.workers, initializer=_init, initargs=(a.root,)) as ex:
            futs = {ex.submit(run_b, (i, s)): s for i, s in enumerate(srcs)}
            for n, f in enumerate(as_completed(futs), 1):
                try:
                    rows.extend(f.result())
                except Exception as e:  # noqa: BLE001
                    failed.append((futs[f], repr(e)))
                if n % 20 == 0:
                    log.info("B %d / %d (%.0f s)", n, len(futs), time.time() - t0)
        pd.DataFrame(rows).to_parquet(a.out / "b_stress.parquet", index=False)
        log.info("B failed: %d %s", len(failed), failed[:3])
    if a.part in ("summary", "all"):
        summarise(a.out, a.n_boot)
    log.info("done in %.0f s", time.time() - t0)


if __name__ == "__main__":
    main()
