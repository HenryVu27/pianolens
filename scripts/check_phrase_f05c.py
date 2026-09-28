"""F-05c: cadence-derived phrase ends and per-phrase tempo shaping, validated on Batik DCML.

    OMP_NUM_THREADS=1 uv run python scripts/check_phrase_f05c.py [cands] [fit] [eval] \
        [coherence] [vienna]

With no argument every part runs, in that order. Writes to ``data/interim/phrase_f05c/``:

* ``cands.pkl``: per movement, the cue table of every onset (default config), annotated phrase
  starts / ends / cadences, proxy phrase starts, onset ends (for start derivation).
* ``fit.json``: logistic weights and picking parameters fitted on K.279-K.283 (``TRAIN``);
  paste them into ``pianolens.features.cadence.DEFAULT_WEIGHTS`` / ``CadenceConfig``.
* ``boundaries.csv``: phrase-end / start / cadence P, R, F1 per movement, method, tolerance.
* ``coherence.csv``: structural-coherence R² per movement, boundary variant and channel.
* ``phrase_tempo.csv``: per-phrase tempo measures per movement and boundary source.
* ``vienna.csv``: Vienna 4x22 K.331/1 (22 pianists; held out) with the detector run on its
  own score.

Batik scores come from the D-11 loader (``iter_aligned(musicxml_score=True)``).
"""

from __future__ import annotations

import json
import sys
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_phrase_f05b import (  # noqa: E402
    NOSPLIT,
    boundary_prf,
    feature_cols,
    shifted,
    vienna_k331,
)

from pianolens.data import batik_mozart as bm  # noqa: E402
from pianolens.features.cadence import (  # noqa: E402
    CUES,
    CadenceConfig,
    cadence_candidates,
    cadence_phrase_ends,
    cadence_prob,
    pick_ends,
    starts_from_ends,
)
from pianolens.features.score_basis import BasisConfig, score_basis  # noqa: E402
from pianolens.features.shaping import (  # noqa: E402
    ShapingConfig,
    _cv_ridge,
    channel_data,
    phrase_tempo_shaping,
    pooled_structural_coherence,
)
from pianolens.features.tempo import tempo_model  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "data" / "interim" / "phrase_f05c"
TRAIN = {f"kv{k}_{m}" for k in (279, 280, 281, 282, 283) for m in (1, 2, 3)}
CFG = ShapingConfig(clip_to_train=True)
warnings.filterwarnings("ignore")


def split_of(stem: str) -> str:
    return "train" if stem in TRAIN else "heldout"


# --------------------------------------------------------------------------- candidates


def run_cands() -> None:
    out = {}
    for ap in bm.iter_aligned(musicxml_score=True):
        t0 = time.time()
        stem = bm.stem_of(ap.score)
        ann = bm.phrase_annotations(ap.score)
        bp = score_basis(ap.score, config=BasisConfig(include_tension=False))
        cand, meta = cadence_candidates(ap.score, basis=bp)
        me = (bp.notes["beat"] + bp.notes["duration_beat"]).groupby(bp.notes["beat"]).max()
        ph = bp.phrases
        ms = np.unique((bp.notes["beat"] - bp.notes["beat_in_bar"]).to_numpy())
        out[stem] = {"cand": cand, "meta": meta, "starts": ann.starts, "ends": ann.ends,
                     "cadences": ann.cadence_table(),
                     "proxy": ph.loc[ph["source"] == "proxy", "start_beat"].tolist(),
                     "proxy_split": ph["start_beat"].tolist(), "downbeats": ms.tolist(),
                     "onset_beats": me.index.to_numpy(float), "max_end": me.to_numpy(float)}
        print(f"{stem}: {time.time() - t0:.1f}s, {len(cand)} onsets", flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    pd.to_pickle(out, OUT / "cands.pkl")


def _label(cand: pd.DataFrame, ends: list[float]) -> np.ndarray:
    e = np.round(np.asarray(ends, float), 6)
    return np.isin(np.round(cand["beat"].to_numpy(float), 6), e).astype(int)


# --------------------------------------------------------------------------- fit


def _ends_f1(D: dict, stems, weights, thr, gap, tol_bars: float | None = None) -> float:
    f = []
    for s in stems:
        d = D[s]
        c = d["cand"].assign(prob=cadence_prob(d["cand"], weights))
        bpb = d["meta"]["beats_per_bar"]
        pred = pick_ends(c, bpb, thr, gap)["beat"].tolist()
        tol = 1.0 if tol_bars is None else tol_bars * bpb
        f.append(boundary_prf(pred, d["ends"], tol, -np.inf)["F1"])
    return float(np.mean(f))


def run_fit() -> None:
    from sklearn.linear_model import LogisticRegression

    D = pd.read_pickle(OUT / "cands.pkl")
    tr = sorted(s for s in D if s in TRAIN)
    X = np.vstack([D[s]["cand"][list(CUES)].to_numpy(float) for s in tr])
    y = np.concatenate([_label(D[s]["cand"], D[s]["ends"]) for s in tr])
    print(f"train: {len(tr)} movements, {len(y)} onsets, {y.sum()} annotated ends")
    lr = LogisticRegression(C=1.0, max_iter=5000).fit(X, y)
    w = {"intercept": float(lr.intercept_[0]),
         **{c: float(v) for c, v in zip(CUES, lr.coef_[0], strict=True)}}
    for k, v in w.items():
        print(f"  {k:18s} {v:+.3f}")
    best = None
    for thr in (0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.5, 0.6):
        for gap in (1.0, 1.5, 2.0, 3.0):
            f = _ends_f1(D, tr, w, thr, gap)
            if best is None or f > best[0]:
                best = (f, thr, gap)
            print(f"  thr {thr:.2f} gap {gap:.1f}: train end F1 +-1 beat {f:.3f}")
    f, thr, gap = best
    # start rule, on train
    srule = None
    for rule in ("gap", "next", "elision"):
        for win in (0.5, 1.0, 2.0) if rule == "gap" else (1.0,):
            fs = []
            for s in tr:
                d = D[s]
                c = d["cand"].assign(prob=cadence_prob(d["cand"], w))
                bpb = d["meta"]["beats_per_bar"]
                ends = pick_ends(c, bpb, thr, gap)["beat"].tolist()
                st = starts_from_ends(d["onset_beats"], d["max_end"], ends, bpb, rule, win)
                fs.append(boundary_prf(st, d["starts"], 1.0, float(d["onset_beats"][0]))["F1"])
            print(f"  start rule {rule} window {win}: train start F1 +-1 beat {np.mean(fs):.3f}")
            if srule is None or np.mean(fs) > srule[0]:
                srule = (float(np.mean(fs)), rule, win)
    res = {"weights": w, "threshold": thr, "min_gap_bars": gap, "start_rule": srule[1],
           "start_window_bars": srule[2], "train_end_f1": f, "train_start_f1": srule[0]}
    print(json.dumps(res, indent=1))
    (OUT / "fit.json").write_text(json.dumps(res, indent=1))


# --------------------------------------------------------------------------- eval


def _cfg_from_fit() -> CadenceConfig:
    """The shipped module defaults (``fit.json`` rounded to 3 decimals and pasted in).
    ``FIT_JSON=1`` uses ``fit.json`` directly instead (after refitting)."""
    import os

    p = OUT / "fit.json"
    if not (os.environ.get("FIT_JSON") and p.exists()):
        return CadenceConfig()
    r = json.loads(p.read_text())
    return CadenceConfig(weights=r["weights"], threshold=r["threshold"],
                         min_gap_bars=r["min_gap_bars"], start_rule=r["start_rule"],
                         start_window_bars=r["start_window_bars"])


def cadence_bounds(d: dict, cfg: CadenceConfig) -> tuple[list[float], list[float]]:
    c = d["cand"].assign(prob=cadence_prob(d["cand"], cfg.weights))
    bpb = d["meta"]["beats_per_bar"]
    ends = pick_ends(c, bpb, cfg.threshold, cfg.min_gap_bars)["beat"].tolist()
    starts = starts_from_ends(d["onset_beats"], d["max_end"], ends, bpb, cfg.start_rule,
                              cfg.start_window_bars)
    return starts, ends


def _prev_onset(onsets: np.ndarray, beats) -> list[float]:
    out = []
    for b in beats:
        i = int(np.searchsorted(onsets, b - 1e-6)) - 1
        if i >= 0:
            out.append(float(onsets[i]))
    return out


def run_eval() -> None:
    D = pd.read_pickle(OUT / "cands.pkl")
    cfg = _cfg_from_fit()
    rows = []
    for s, d in D.items():
        bpb = d["meta"]["beats_per_bar"]
        first = float(d["onset_beats"][0])
        cst, cen = cadence_bounds(d, cfg)
        ob = d["onset_beats"]
        db = np.asarray(d["downbeats"], float)
        proxy_st = d["proxy"]
        preds_end = {
            "cadence": cen,
            # proxy ends: last onset before each proxy start (phrase_detail default), and the
            # downbeat one bar before each proxy start
            "proxy_last_onset": _prev_onset(ob, proxy_st[1:]) + [float(ob[-1])],
            "proxy_prev_downbeat": [float(db[i - 1]) for i in np.searchsorted(db, proxy_st)
                                    if i >= 1],
            "grid4": db[3::4].tolist(),
        }
        preds_start = {"cadence": cst, "proxy": proxy_st, "proxy_split": d["proxy_split"],
                       "grid4": db[::4].tolist()}
        cad = d["cadences"]
        for tol, tn in ((1.0, "1beat"), (bpb, "1bar")):
            for m, p in preds_end.items():
                rows.append({"movement": s, "split": split_of(s), "target": "end", "tol": tn,
                             "method": m, **boundary_prf(p, d["ends"], tol, -np.inf)})
                rows.append({"movement": s, "split": split_of(s), "target": "cadence",
                             "tol": tn, "method": m,
                             **boundary_prf(p, cad["beat"].tolist(), tol, -np.inf)})
            for m, p in preds_start.items():
                rows.append({"movement": s, "split": split_of(s), "target": "start", "tol": tn,
                             "method": m, **boundary_prf(p, d["starts"], tol, first)})
        # recall per DCML cadence type (+-1 beat) of the detected ends
        for typ, g in cad.groupby("cadence"):
            r = boundary_prf(cen, g["beat"].tolist(), 1.0, -np.inf)
            rows.append({"movement": s, "split": split_of(s), "target": f"cad_{typ}",
                         "tol": "1beat", "method": "cadence", "tp": r["tp"],
                         "n_true": r["n_true"], "n_pred": r["n_pred"]})
    B = pd.DataFrame(rows)
    OUT.mkdir(parents=True, exist_ok=True)
    B.to_csv(OUT / "boundaries.csv", index=False)
    report_eval()


def report_eval() -> None:
    B = pd.read_csv(OUT / "boundaries.csv")
    main = B[~B["target"].str.startswith("cad_")]
    print("\nmean over movements (P, R, F1):")
    print(main.groupby(["target", "tol", "split", "method"])[["P", "R", "F1"]].mean()
          .round(3).to_string())
    tot = main.groupby(["target", "tol", "split", "method"])[["tp", "n_pred", "n_true"]].sum()
    tot["P"], tot["R"] = tot["tp"] / tot["n_pred"], tot["tp"] / tot["n_true"]
    tot["F1"] = 2 * tot["P"] * tot["R"] / (tot["P"] + tot["R"])
    print("\npooled:\n", tot.round(3).to_string())
    ct = B[B["target"].str.startswith("cad_")].groupby(["split", "target"])[
        ["tp", "n_true"]].sum()
    ct["recall"] = ct["tp"] / ct["n_true"]
    print("\nrecall of detected ends per DCML cadence type (+-1 beat):\n", ct.round(3).to_string())


# --------------------------------------------------------------------------- coherence


def run_coherence() -> None:
    D = pd.read_pickle(OUT / "cands.pkl")
    cfg = _cfg_from_fit()
    R, P = [], []
    for ap in bm.iter_aligned(musicxml_score=True):
        t0 = time.time()
        stem = bm.stem_of(ap.score)
        d = D[stem]
        s = ap.score
        tc = tempo_model(ap)
        bp = score_basis(s)
        bpb = bp.meta["beats_per_bar"]
        lo, hi = float(bp.notes["beat"].min()), float(bp.notes["beat"].max()) + 1
        sh = 2 * bpb
        cst, cen = cadence_bounds(d, cfg)
        # sanity: the library path gives the same boundaries as the cached candidates
        if cfg.weights == CadenceConfig().weights:
            lib = cadence_phrase_ends(s)
            assert np.allclose(lib.end_beats, cen), stem
        detail = BasisConfig(phrase_detail=True, phrase_max_bars=NOSPLIT)
        detail_split = BasisConfig(phrase_detail=True)
        variants = {
            "proxy": bp,
            "proxy_detail": score_basis(s, config=detail_split),
            "ann_detail": score_basis(s, phrase_boundaries_beats=d["starts"],
                                      phrase_ends_beats=d["ends"], config=detail),
            "cad_detail": score_basis(s, phrase_boundaries_beats=cst, phrase_ends_beats=cen,
                                      config=detail),
            "cad_detail_split": score_basis(s, phrase_boundaries_beats=cst,
                                            phrase_ends_beats=cen, config=detail_split),
            "shift_cad_detail": score_basis(s, phrase_boundaries_beats=shifted(cst, sh, lo, hi),
                                            phrase_ends_beats=shifted(cen, sh, lo, hi),
                                            config=detail),
        }
        for vname, b in variants.items():
            data = channel_data(ap, b, tc, CFG)
            for ch, df in data.items():
                y, m = df["y"].to_numpy(float), df["measure_number"].to_numpy()
                row = {"movement": stem, "split": split_of(stem), "variant": vname,
                       "channel": ch, "n": len(y)}
                for mk, key in ((True, "r2"), (False, "r2_nm")):
                    X = df[feature_cols(b.groups, mk)].to_numpy(float)
                    row[key] = _cv_ridge(X, y, m, CFG)[1]
                R.append(row)
        for src, st in (("ann", d["starts"]), ("cadence", cst), ("proxy_split", d["proxy_split"]),
                        ("grid4", np.asarray(d["downbeats"])[::4].tolist())):
            pts = phrase_tempo_shaping(ap, st, tempo=tc)
            p2 = phrase_tempo_shaping(ap, st, tempo=tc, null_shifts_bars=(2.0,))
            P.append({"movement": stem, "split": split_of(stem), "bounds": src, **pts.summary,
                      "null2_concave_share": p2.summary["null_concave_share"],
                      "null2_arc_r2_within": p2.summary["null_arc_r2_within"]})
        print(f"{stem}: {time.time() - t0:.1f}s, {len(cst)} cadence starts, "
              f"{len(d['starts'])} annotated", flush=True)
    pd.DataFrame(R).to_csv(OUT / "coherence.csv", index=False)
    pd.DataFrame(P).to_csv(OUT / "phrase_tempo.csv", index=False)
    report_coherence()


def report_coherence() -> None:
    from scipy.stats import wilcoxon

    R = pd.read_csv(OUT / "coherence.csv")
    P = pd.read_csv(OUT / "phrase_tempo.csv")
    for split in ("all", "train", "heldout"):
        r = R if split == "all" else R[R["split"] == split]
        n = r["movement"].nunique()
        for key in ("r2_nm", "r2"):
            print(f"\n{split} ({n} movements) coherence {key}, mean:")
            print(r.pivot_table(index="channel", columns="variant", values=key, aggfunc="mean")
                  .round(3).to_string())
        piv = r[r["channel"] == "tempo"].pivot(index="movement", columns="variant",
                                               values="r2_nm")
        for a, b in (("cad_detail", "proxy"), ("cad_detail", "shift_cad_detail"),
                     ("ann_detail", "cad_detail"), ("cad_detail_split", "proxy"),
                     ("cad_detail", "proxy_detail")):
            dd = piv[a] - piv[b]
            print(f"tempo r2_nm {a} - {b}: mean {dd.mean():+.3f}, median {dd.median():+.3f}, "
                  f"{int((dd > 0).sum())}/{len(dd)} better, wilcoxon p {wilcoxon(dd).pvalue:.2g}")
        p = P if split == "all" else P[P["split"] == split]
        cols = ["n_phrases", "concave_share", "null_concave_share", "null2_concave_share",
                "concave_excess", "arc_r2_within", "null_arc_r2_within", "null2_arc_r2_within",
                "arc_r2_excess", "between_share", "depth_median_log"]
        print(f"\n{split} per-phrase tempo (mean over movements):")
        print(p.groupby("bounds")[cols].mean().round(3).T.to_string())


# --------------------------------------------------------------------------- Vienna


def run_vienna() -> None:
    """Vienna K.331/1 theme, 22 pianists: the detector runs on the Vienna score itself; bars
    renumbered to written bars (Batik's kv331_1 numbering, as F-05b) for the CV folds."""
    cfg = _cfg_from_fit()
    s_batik = next(bm.iter_aligned(musicxml_score=True, stems={"kv331_1"})).score
    src = score_basis(s_batik).notes
    ann = bm.phrase_annotations(s_batik)
    u = src.drop_duplicates("beat")
    written = u.set_index(u["beat"].round(6))["measure_number"]
    aps = list(vienna_k331())
    variants: dict[str, list] = {"proxy": [], "ann_detail": [], "cad_detail": [],
                                 "shift_cad_detail": []}
    tcs, P = [], []
    cad_res = cadence_phrase_ends(aps[0].score, cfg)
    last = float(aps[0].score.notes["onset_beat"].max())
    st_ann = [b for b in ann.starts if b <= last]
    en_ann = [b for b in ann.ends if b <= last]
    bpb = cad_res.meta["beats_per_bar"]
    first = float(aps[0].score.notes["onset_beat"].min())
    brow = {"cad_end_F1_1beat": boundary_prf(cad_res.end_beats, en_ann, 1.0, -np.inf)["F1"],
            "cad_end_F1_1bar": boundary_prf(cad_res.end_beats, en_ann, bpb, -np.inf)["F1"],
            "cad_start_F1_1beat": boundary_prf(cad_res.starts, st_ann, 1.0, first)["F1"],
            "n_cad_ends": len(cad_res.end_beats), "n_ann_ends": len(en_ann)}
    print("vienna boundaries:", brow, flush=True)
    lo, hi = first, last + 1
    detail = BasisConfig(phrase_detail=True, phrase_max_bars=NOSPLIT)
    for ap in aps:
        tc = tempo_model(ap)
        cst, cen = cad_res.starts, cad_res.end_beats
        bases = {
            "proxy": score_basis(ap.score),
            "ann_detail": score_basis(ap.score, phrase_boundaries_beats=st_ann,
                                      phrase_ends_beats=en_ann, config=detail),
            "cad_detail": score_basis(ap.score, phrase_boundaries_beats=cst,
                                      phrase_ends_beats=cen, config=detail),
            "shift_cad_detail": score_basis(
                ap.score, phrase_boundaries_beats=shifted(cst, 2 * bpb, lo, hi),
                phrase_ends_beats=shifted(cen, 2 * bpb, lo, hi), config=detail),
        }
        for b in [*bases.values(), tc]:
            for df in ((b.notes, b.onsets) if hasattr(b, "onsets") else (b.positions,)):
                start = (df["beat"] - df["beat_in_bar"]).round(6)
                df["measure_number"] = written.reindex(start).to_numpy()
        for k, b in bases.items():
            variants[k].append(b)
        tcs.append(tc)
        for srcn, st in (("ann", st_ann), ("cadence", cst),
                         ("proxy_split", bases["proxy"].phrases["start_beat"].tolist())):
            P.append({"performance": ap.performance.performance_id, "bounds": srcn,
                      **phrase_tempo_shaping(ap, st, tempo=tc).summary})
    rows = []
    for v, bs in variants.items():
        pooled = pooled_structural_coherence(aps, bs, tcs, CFG)
        for ch in ("velocity", "timing", "tempo", "articulation"):
            rows.append({"variant": v, "channel": ch, "pooled_r2_nm":
                         pooled.r2(ch, "r2_no_markings"), "pooled_r2": pooled.r2(ch), **brow})
    R = pd.DataFrame(rows)
    R.to_csv(OUT / "vienna.csv", index=False)
    pd.DataFrame(P).to_csv(OUT / "vienna_phrase_tempo.csv", index=False)
    print(R.pivot_table(index="channel", columns="variant", values="pooled_r2_nm")
          .round(3).to_string())
    print(pd.DataFrame(P).groupby("bounds")[["n_phrases", "concave_share", "null_concave_share",
                                             "concave_excess", "arc_r2_within",
                                             "null_arc_r2_within", "arc_r2_excess"]]
          .mean().round(3).T.to_string())


if __name__ == "__main__":
    parts = sys.argv[1:] or ["cands", "fit", "eval", "coherence", "vienna"]
    for name, fn in (("cands", run_cands), ("fit", run_fit), ("eval", run_eval),
                     ("report_eval", report_eval), ("coherence", run_coherence),
                     ("report_coherence", report_coherence), ("vienna", run_vienna)):
        if name in parts:
            fn()
