"""A-01b: extra-note filter, trained and validated on PianoVAM, then applied to Henry's takes.

    uv run python scripts/a01b_extra_filter.py prep     # labels + features per transcribed note
    uv run python scripts/a01b_extra_filter.py cv       # characterise, leave-one-pianist-out CV
    uv run python scripts/a01b_extra_filter.py henry    # apply to the 5 takes (+ floor refs)
    uv run python scripts/a01b_extra_filter.py floor    # BL-13: onset / velocity floor by skill

Inputs:
* ``data/interim/pianovam_a01b/transkun/<record_time>.mid`` from
  ``scripts/a01b_transcribe_pianovam.py`` (Transkun 2.0.1 on the PianoVAM microphone audio);
* ``data/raw/pianovam/MIDI/<record_time>.mid``: Disklavier ground truth.

Label: a transcribed note with no ground-truth note of the same pitch within 50 ms (after the
median clock offset is removed) is a *false extra*. Features come from the transcription alone
(``pianolens.audio.extra_filter``).

Evaluation is leave-one-pianist-out: the rule parameters and the classifier's threshold are
chosen on the training pianists only, for the largest removal of false extras whose loss of true
notes on those pianists stays at or below ``--max-loss`` (share of true notes removed).

Outputs under ``data/interim/pianovam_a01b/`` (notes.parquet, per_file.csv, cv.json,
extra_filter.pkl) and ``data/interim/henry_takes/a01b/`` (Henry: personal data, never committed).
"""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PV = ROOT / "data" / "interim" / "pianovam_a01b"
HB = ROOT / "data" / "interim" / "henry_takes"
OUT_H = HB / "a01b"
G6 = 91
RULE_GRID = [dict(min_pitch=mp, max_dur=md, min_spike=ms, max_vel_rel=mv)
             for mp in (88, 91, 93, 96) for md in (0.08, 0.1, 0.15, 0.25, 99.0)
             for ms in (-9.0, 0.0, 0.5, 1.0) for mv in (99.0, 0.0, -10.0)]  # fmt: skip
#: Safety budget fixed before looking at held-out numbers: share of true notes removed, overall
#: and among true notes at G6 or above (removing a real note creates a false "missed" flag).
MAX_LOSS_ALL, MAX_LOSS_HIGH = 0.001, 0.05


def _pm_notes(path: Path) -> pd.DataFrame:
    import pretty_midi

    pm = pretty_midi.PrettyMIDI(str(path))
    rows = [(n.start, n.end - n.start, n.pitch, n.velocity)
            for ins in pm.instruments for n in ins.notes]
    df = pd.DataFrame(rows, columns=["onset_sec", "duration_sec", "pitch", "velocity"])
    return df.sort_values(["onset_sec", "pitch"], kind="stable").reset_index(drop=True)


def _prep_one(rt: str) -> pd.DataFrame:
    from pianolens.audio.extra_filter import label_false_extras, note_features

    est = _pm_notes(PV / "transkun" / f"{rt}.mid")
    ref = _pm_notes(ROOT / "data" / "raw" / "pianovam" / "MIDI" / f"{rt}.mid")
    y, f = label_false_extras(ref, est)
    feat = note_features(est)
    feat["y"] = y
    feat["record_time"] = rt
    feat.attrs["f"] = f
    # ground-truth notes the transcriber missed (for the recall side)
    feat["n_ref"] = f["n_ref"]
    feat["f1"] = f["f1"]
    feat["offset_sec"] = f["offset_sec"]
    # harmonic-source check against ground truth: is a *played* note a harmonic step below?
    from pianolens.audio.extra_filter import HARMONIC_STEPS

    ro, rp = ref["onset_sec"].to_numpy() + f["offset_sec"], ref["pitch"].to_numpy()
    rend = ro + ref["duration_sec"].to_numpy()
    gt_src = np.zeros(len(est))
    for i, (t, p) in enumerate(zip(est["onset_sec"], est["pitch"], strict=True)):
        m = (ro <= t + 0.05) & (rend >= t - 0.05) & np.isin(p - rp, HARMONIC_STEPS)
        gt_src[i] = float(m.any())
    feat["gt_harm_source"] = gt_src
    return feat


def prep() -> None:
    from pianolens.data.pianovam import pianovam_index

    md = pianovam_index().set_index("record_time")
    rts = sorted(p.stem for p in (PV / "transkun").glob("*.mid"))
    with ProcessPoolExecutor(10) as ex:
        parts = list(ex.map(_prep_one, rts))
    df = pd.concat(parts, ignore_index=True)
    df["pianist"] = md.loc[df["record_time"], "P1_name"].str.strip().str.lower().to_numpy()
    df["skill"] = md.loc[df["record_time"], "P1_skill"].to_numpy()
    df["split"] = md.loc[df["record_time"], "split"].to_numpy()
    df.to_parquet(PV / "notes.parquet")
    pf = df.groupby("record_time").agg(pianist=("pianist", "first"), skill=("skill", "first"),
                                       split=("split", "first"), n_est=("y", "size"),
                                       n_false=("y", "sum"), n_ref=("n_ref", "first"),
                                       f1=("f1", "first"), offset_sec=("offset_sec", "first"))
    pf["extra_rate"] = pf["n_false"] / pf["n_ref"]
    pf.to_csv(PV / "per_file.csv")
    print(pf.describe().round(3).to_string())
    print(pf.sort_values("f1").head(8).round(3).to_string())


def _eval(y: np.ndarray, drop: np.ndarray, n_ref: int) -> dict:
    tp = int((drop & (y == 1)).sum())
    fp = int((drop & (y == 0)).sum())
    n_false, n_true = int((y == 1).sum()), int((y == 0).sum())
    p0, r0 = n_true / len(y), n_true / n_ref
    kept = len(y) - int(drop.sum())
    p1, r1 = (n_true - fp) / max(1, kept), (n_true - fp) / n_ref
    return {"n_est": len(y), "n_false": n_false, "n_true": n_true, "n_ref": n_ref,
            "removed": int(drop.sum()), "removed_false": tp, "removed_true": fp,
            "removal_precision": tp / max(1, tp + fp), "removal_recall": tp / max(1, n_false),
            "true_loss": fp / max(1, n_true),
            "extra_rate_before": n_false / n_ref, "extra_rate_after": (n_false - tp) / n_ref,
            "f1_before": 2 * p0 * r0 / (p0 + r0), "f1_after": 2 * p1 * r1 / (p1 + r1)}  # fmt: skip


def _n_ref(d: pd.DataFrame) -> int:
    return int(d.groupby("record_time")["n_ref"].first().sum())


def _pick_threshold(y: np.ndarray, s: np.ndarray, max_loss: float) -> float:
    """Lowest threshold whose true-note loss is <= max_loss (most removal under the budget)."""
    n_true = max(1, int((y == 0).sum()))
    order = np.argsort(-s)
    ss, yy = s[order], y[order]
    fp = np.cumsum(yy == 0)
    ok = fp / n_true <= max_loss
    if not ok.any():
        return float("inf")
    k = int(np.nonzero(ok)[0].max())
    thr = float(ss[k])
    # ties: make sure the loss at this threshold still fits
    while ((s >= thr) & (y == 0)).sum() / n_true > max_loss and k > 0:
        k -= 1
        thr = float(np.nextafter(ss[k], np.inf)) if ss[k] == thr else float(ss[k])
    return thr


def _fit_model(d: pd.DataFrame):  # noqa: ANN202
    from sklearn.ensemble import HistGradientBoostingClassifier

    from pianolens.audio.extra_filter import FEATURES

    m = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.05, max_leaf_nodes=31,
                                       min_samples_leaf=100, random_state=0)  # fmt: skip
    return m.fit(d[FEATURES], d["y"])


def _characterise(d: pd.DataFrame) -> dict:
    ex = d[d["y"] == 1]
    hi = ex[ex["pitch"] >= G6]
    nref = _n_ref(d)
    top = hi["pitch"].value_counts()
    return {"n_files": int(d["record_time"].nunique()), "n_ref": nref, "n_est": len(d),
            "n_false": len(ex), "extra_rate": len(ex) / nref,
            "extra_rate_ge_G6": len(hi) / nref,
            "share_of_extras_ge_G6": len(hi) / max(1, len(ex)),
            "true_notes_ge_G6_share": float((d.loc[d["y"] == 0, "pitch"] >= G6).mean()),
            "extras_harm_source_gt": float(ex["gt_harm_source"].mean()),
            "extras_harm_source_est": float(((ex["harm_onset"] + ex["harm_sounding"]) > 0).mean()),
            "hi_extras_harm_source_gt": float(hi["gt_harm_source"].mean()) if len(hi) else None,
            "hi_extras_top5_pitch_share": float(top.head(5).sum() / max(1, len(hi))),
            "hi_extras_top5_pitches": [int(x) for x in top.head(5).index],
            "extras_median_vel_rel_local": float(ex["vel_rel_local"].median()),
            "true_median_vel_rel_local": float(d.loc[d["y"] == 0, "vel_rel_local"].median()),
            "extras_median_log_dur": float(ex["log_dur"].median()),
            "true_median_log_dur": float(d.loc[d["y"] == 0, "log_dur"].median()),
            "extras_by_octave": {int(k): int(v) for k, v in
                                 (ex["pitch"] // 12 - 1).value_counts().sort_index().items()}}


def _henry_features() -> pd.DataFrame:
    """Features of Henry's Transkun takes, no labels (label-free tie-break for rule choice)."""
    from pianolens.audio.extra_filter import note_features

    return pd.concat([note_features(_pm_notes(HB / "transcribed" / "transkun" / f"{k}.mid"))
                      for k in sorted(json.loads((HB / "scores" / "scores.json").read_text()))],
                     ignore_index=True)  # fmt: skip


def _rule_loss(d: pd.DataFrame, g: dict) -> dict:
    from pianolens.audio.extra_filter import rule_scores

    drop = rule_scores(d, **g) >= 0.5
    t = (d["y"] == 0).to_numpy()
    hi = t & (d["pitch"] >= G6).to_numpy()
    return {"loss_all": float((drop & t).sum() / max(1, t.sum())),
            "loss_high": float((drop & hi).sum() / max(1, hi.sum())),
            "n_true_high": int(hi.sum()), "drop": drop}  # fmt: skip


def _choose_rule(d: pd.DataFrame, henry_removed: dict) -> dict | None:
    """Among grid rules within the safety budget on ``d``, the one removing most Henry notes."""
    ok = []
    for k, g in enumerate(RULE_GRID):
        e = _rule_loss(d, g)
        if e["loss_all"] <= MAX_LOSS_ALL and e["loss_high"] <= MAX_LOSS_HIGH:
            ok.append((henry_removed[k], -e["loss_high"], k))
    return RULE_GRID[max(ok)[2]] if ok else None


def cv(max_loss: float) -> None:
    from pianolens.audio.extra_filter import FEATURES, rule_scores

    d = pd.read_parquet(PV / "notes.parquet")
    pf = pd.read_csv(PV / "per_file.csv")
    bad = set(pf.loc[pf["f1"] < 0.7, "record_time"])  # audio/MIDI sync failure, not extras
    d = d[~d["record_time"].isin(bad)].reset_index(drop=True)
    res = {"max_loss_model": max_loss, "rule_budget": [MAX_LOSS_ALL, MAX_LOSS_HIGH],
           "excluded_sync": sorted(bad), "all": _characterise(d),
           "by_skill": {s: _characterise(g) for s, g in d.groupby("skill")}}  # fmt: skip
    hf = _henry_features()
    henry_removed = {k: int((rule_scores(hf, **g) >= 0.5).sum()) for k, g in enumerate(RULE_GRID)}
    per_fold, pooled = [], {"rule": [], "model": [], "y": [], "high": [], "n_ref": 0}
    for pianist in sorted(d["pianist"].unique()):
        tr, te = d[d["pianist"] != pianist], d[d["pianist"] == pianist]
        ytr, yte = tr["y"].to_numpy(), te["y"].to_numpy()
        best = _choose_rule(tr, henry_removed)
        dr_te = (rule_scores(te, **best) >= 0.5) if best else np.zeros(len(te), bool)
        # classifier: fit on training pianists; threshold from out-of-fold scores within them
        oof = np.zeros(len(tr))
        for q in sorted(tr["pianist"].unique()):
            msk = (tr["pianist"] == q).to_numpy()
            oof[msk] = _fit_model(tr[~msk]).predict_proba(tr.loc[msk, FEATURES])[:, 1]
        thr = _pick_threshold(ytr, oof, max_loss)
        dm_te = _fit_model(tr).predict_proba(te[FEATURES])[:, 1] >= thr
        nr = _n_ref(te)
        per_fold.append({"pianist": pianist, "skill": te["skill"].iloc[0],
                         "n_files": int(te["record_time"].nunique()), "rule_params": best,
                         "model_threshold": thr, "rule": _eval(yte, dr_te, nr),
                         "model": _eval(yte, dm_te, nr)})  # fmt: skip
        for k, v in (("rule", dr_te), ("model", dm_te), ("y", yte),
                     ("high", (te["pitch"] >= G6).to_numpy())):
            pooled[k].append(v)
        pooled["n_ref"] += nr
        print(pianist, best, {m: {k: round(v, 4) for k, v in per_fold[-1][m].items()
                                  if k in ("removed_false", "removed_true", "true_loss")}
                              for m in ("rule", "model")}, flush=True)  # fmt: skip
    y, high = np.concatenate(pooled["y"]), np.concatenate(pooled["high"])
    res["cv_pooled"] = {}
    for k in ("rule", "model"):
        dr = np.concatenate(pooled[k])
        e = _eval(y, dr, pooled["n_ref"])
        th = (y == 0) & high
        e["true_loss_high"] = float((dr & th).sum() / max(1, th.sum()))
        e["n_true_high"] = int(th.sum())
        res["cv_pooled"][k] = e
    res["cv_folds"] = per_fold
    # final rule and classifier on all pianists
    best = _choose_rule(d, henry_removed)
    e = _rule_loss(d, best)
    res["final"] = {"rule_params": best, "rule_in_sample": {k: v for k, v in e.items()
                                                            if k != "drop"},
                    "henry_transkun_removed": henry_removed[RULE_GRID.index(best)]}  # fmt: skip
    oof = np.zeros(len(d))
    for q in sorted(d["pianist"].unique()):
        msk = (d["pianist"] == q).to_numpy()
        oof[msk] = _fit_model(d[~msk]).predict_proba(d.loc[msk, FEATURES])[:, 1]
    thr = _pick_threshold(d["y"].to_numpy(), oof, max_loss)
    res["final"]["model_threshold"] = thr
    from pianolens.audio.extra_filter import ExtraNoteFilter

    ExtraNoteFilter(_fit_model(d), thr, {
        "trained_on": "PianoVAM v1.2 (CC BY-NC-SA 4.0) microphone audio, Transkun 2.0.1",
        "n_files": int(d["record_time"].nunique()), "max_true_loss": max_loss,
        "cv_pooled": res["cv_pooled"]["model"]}).save(PV / "extra_filter.pkl")
    (PV / "cv.json").write_text(json.dumps(res, indent=1, default=float))
    print(json.dumps({k: res[k] for k in ("cv_pooled", "final")}, indent=1, default=float))
    print(json.dumps(res["all"], default=float))


def _henry_one(k: str, t: str, src: Path, dst: Path, mode: str, label: str) -> dict:
    """Filter one MIDI (mode none / rule / model), re-align to take ``k``'s score and measure.
    Removed notes are also looked up in the *unfiltered* alignment: were they score extras,
    correct notes or wrong pitches?"""
    sys.path.insert(0, str(ROOT / "scripts"))
    from a01_henry_baseline import _score, analyse

    from pianolens.align import align_performance
    from pianolens.audio.extra_filter import ExtraNoteFilter, filter_midi
    from pianolens.features.correctness import correctness
    from pianolens.report.io import load_performance

    if mode == "none":
        row = analyse(k, label, src, t, "transcribed")
        row.update({"mode": mode, "n_removed": 0, "removed_ge_G6": 0})
        return row
    flt = ExtraNoteFilter.load(PV / "extra_filter.pkl") if mode == "model" else None
    params = json.loads((PV / "cv.json").read_text())["final"]["rule_params"]
    # "rule" uses the parameters chosen by the cv stage (the module defaults match them)
    info = filter_midi(src, dst, flt, rule_params=params if mode == "rule" else None)
    row = analyse(k, label, dst, t, "transcribed")
    rp, ro = np.array(info["removed_pitches"], int), np.array(info["removed_onsets"], float)
    row.update({"mode": mode, "n_removed": info["n_removed"],
                "removed_ge_G6": int(np.sum(rp >= G6))})  # fmt: skip
    sc, meta = _score(k)
    nd = correctness(align_performance(sc, load_performance(src, "transcribed",
                                                            meta["piece_id"]))).notes
    lab = nd["label"].astype(str).to_numpy()
    on, pt = nd["onset_sec"].to_numpy(float), nd["pitch"].to_numpy()
    is_rem = np.zeros(len(nd), bool)
    for o, p in zip(ro, rp, strict=True):
        hit = np.nonzero((pt == p) & (np.abs(on - o) < 0.002) & ~is_rem)[0]
        if len(hit):
            is_rem[hit[0]] = True
    for name in ("extra", "correct", "wrong_pitch"):
        row[f"removed_were_{name}"] = int(((lab == name) & is_rem).sum())
    row["removed_unlocated"] = int(len(rp) - is_rem.sum())
    return row


def henry(workers: int, n_refs: int) -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    from a01_henry_baseline import floor_jobs

    OUT_H.mkdir(parents=True, exist_ok=True)
    takes = sorted(json.loads((HB / "scores" / "scores.json").read_text()))
    jobs = []
    for mode in ("none", "rule", "model"):
        for t in ("transkun", "aria_amt"):
            for k in takes:
                src = HB / "transcribed" / t / f"{k}.mid"
                dst = OUT_H / f"{t}_{mode}" / f"{k}.mid"
                jobs.append((k, t, src, dst, mode, f"henry:{t}"))
    rows = []
    with ProcessPoolExecutor(workers) as ex:
        futs = [ex.submit(_henry_one, *j) for j in jobs]
        for fu in futs:
            rows.append(fu.result())
    df = pd.DataFrame(rows)
    df.to_csv(OUT_H / "takes_filtered.csv", index=False)
    cols = ["take", "transcriber", "mode", "extra_rate", "missed_rate", "wrong_rate",
            "a_error_rate", "a_match_ratio", "n_removed", "removed_ge_G6",
            "removed_were_extra", "removed_were_correct", "removed_were_wrong_pitch",
            "removed_unlocated"]  # fmt: skip
    pd.set_option("display.width", 250)
    print(df[[c for c in cols if c in df]].sort_values(["transcriber", "take", "mode"])
          .round(3).to_string())  # fmt: skip
    # floor refs: does the filter remove correct notes from professional transcriptions?
    import tempfile
    import zipfile

    from pianolens.data.pianocore import DEFAULT_ROOT, RAW_PREFIX, RAW_ZIP

    fl = []
    with zipfile.ZipFile(DEFAULT_ROOT / RAW_ZIP) as z, tempfile.TemporaryDirectory() as td:
        fj = []
        for k, ref_id, rel, t in floor_jobs(n_refs):
            f = Path(td) / f"{k}_{t}_{ref_id.replace('/', '_')}.mid"
            f.write_bytes(z.read(RAW_PREFIX + rel))
            for mode in ("none", "rule", "model"):
                fj.append((k, t, f, Path(td) / mode / f.name, mode, f"pianocore:{ref_id}"))
        with ProcessPoolExecutor(workers) as ex:
            futs = [ex.submit(_henry_one, *j) for j in fj]
            for fu in futs:
                try:
                    fl.append(fu.result())
                except Exception as e:  # noqa: BLE001 - count failures
                    print("floor failed", repr(e)[:150])
    fl = pd.DataFrame(fl)
    fl.to_csv(OUT_H / "floor_filtered.csv", index=False)
    ok = fl[fl["a_match_ratio"] >= 0.8]
    print(ok.groupby(["transcriber", "mode"])[["extra_rate", "missed_rate", "a_error_rate",
                                               "n_removed", "removed_were_correct"]]
          .median().round(4).to_string())  # fmt: skip


def _floor_one(rt: str) -> dict:
    from pianolens.audio.transcription import match_notes, note_f1, velocity_agreement

    est = _pm_notes(PV / "transkun" / f"{rt}.mid")
    ref = _pm_notes(ROOT / "data" / "raw" / "pianovam" / "MIDI" / f"{rt}.mid")
    f = note_f1(ref, est, estimate_offset=True)
    m = match_notes(ref, est, 0.05, offset=f["offset_sec"])
    va = ref["velocity"].to_numpy(float)[[i for i, _ in m]]
    vb = est["velocity"].to_numpy(float)[[j for _, j in m]]
    return {"record_time": rt, **{k: f[k] for k in ("f1", "precision", "recall",
                                                    "onset_err_rsd_ms", "n_ref")},
            **velocity_agreement(va, vb)}  # fmt: skip


def floor() -> None:
    """BL-13: per-recording onset error and velocity fit of Transkun vs the Disklavier truth."""
    pf = pd.read_csv(PV / "per_file.csv")
    with ProcessPoolExecutor(10) as ex:
        rows = list(ex.map(_floor_one, pf["record_time"]))
    df = pf[["record_time", "pianist", "skill"]].merge(pd.DataFrame(rows), on="record_time")
    df.to_csv(PV / "floor_by_file.csv", index=False)
    cols = ["f1", "onset_err_rsd_ms", "vel_slope", "vel_spearman", "vel_resid_rsd_midi"]
    g = df.groupby("skill").agg(n=("f1", "size"), notes=("n_ref", "sum"),
                                n_pianists=("pianist", "nunique"),
                                **{c: (c, "median") for c in cols})  # fmt: skip
    print(g.round(3).to_string())
    print(df[cols].describe().round(3).to_string())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["prep", "cv", "henry", "floor"])
    ap.add_argument("--max-loss", type=float, default=0.005)
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--n-refs", type=int, default=15)
    a = ap.parse_args()
    {"prep": prep, "cv": lambda: cv(a.max_loss),
     "henry": lambda: henry(a.workers, a.n_refs), "floor": floor}[a.stage]()


if __name__ == "__main__":
    main()
