"""F-05b: validate the F-05 phrase proxy against Batik-plays-Mozart DCML phrase annotations and
measure structural coherence with proxy vs annotated phrases (Batik, Vienna 4x22, ASAP).

    OMP_NUM_THREADS=1 uv run python scripts/check_phrase_f05b.py [batik] [lomo] [transfer]

With no argument every part runs. Writes to ``data/interim/phrase_f05b/``:

* ``batik_boundaries.csv``: proxy / grid boundary precision, recall, F1 per movement.
* ``batik_coherence.csv``: structural-coherence R² per movement, phrase variant and channel.
* ``batik_arcs.csv``: per-phrase parabola fits of the smooth tempo (F-03 ``phrase_arcs``).
* ``batik_lomo.csv``: one model over all 36 movements, leave-movement-out.
* ``transfer_coherence.csv`` / ``transfer_boundaries.csv``: Vienna K.331/1 (22 pianists) and
  ASAP K.331/3, K.332/1-3 with the Batik annotations transferred by bar and beat.

Batik scores: the match-built score has no markings, so the loader's
``iter_aligned(musicxml_score=True)`` (D-11) unfolds the edited MusicXML to the repeat path
whose note ids equal the match-file ids, so markings are read and the ground-truth alignment
still applies. K.284/3 takes about 5 minutes to unfold (unfolded parts do not pickle: recursion).
Use ``OMP_NUM_THREADS=1``: the GBM check otherwise oversubscribes a busy machine.

Phrase annotations (DCML ``phraseend`` in ``score_parts_annotated/*_spart_phrases.csv``): ``{``
starts a phrase, ``}`` ends it (on the cadential arrival), ``}{`` does both (elision).
"""

from __future__ import annotations

import sys
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from pianolens.align import align_performance
from pianolens.align.core import (
    _build,
    _variants_with_paths,
    load_score_part,
)
from pianolens.data import batik_mozart as bm
from pianolens.data import vienna4x22 as vn
from pianolens.data.asap import asap_index, load_asap_performance, load_asap_score
from pianolens.data.types import AlignedPerformance, score_from_partitura
from pianolens.features.score_basis import MARKING_GROUPS, BasisConfig, score_basis
from pianolens.features.shaping import (
    ShapingConfig,
    _buffered_train,
    _cv_ridge,
    _folds,
    channel_data,
    pooled_structural_coherence,
    structural_coherence,
)
from pianolens.features.tempo import phrase_arcs, tempo_model

OUT = Path(__file__).resolve().parents[1] / "data" / "interim" / "phrase_f05b"
CFG = ShapingConfig(clip_to_train=True)
CFG_F05 = ShapingConfig()
NOSPLIT = 1e6  # phrase_max_bars that never splits
ASAP_TARGETS = {"Mozart/Piano_Sonatas/12-1": "kv332_1", "Mozart/Piano_Sonatas/12-2": "kv332_2",
                "Mozart/Piano_Sonatas/12-3": "kv332_3", "Mozart/Piano_Sonatas/11-3": "kv331_3"}
warnings.filterwarnings("ignore")


# --------------------------------------------------------------------------- data


def unfold_like(part, ids: set[str]):
    """Unfolded variant of ``part`` whose note ids best match ``ids`` (Jaccard), among the four
    variants whose note counts are closest to ``len(ids)``."""
    variants = _variants_with_paths(part)
    # building a part per variant is slow (K.284/3 has many): try the 4 closest note counts
    closest = sorted(variants, key=lambda t: abs(t[1] - len(ids)))[:4]
    best = None
    for v, _, p in closest:
        up = _build(part, p, len(variants))
        u = set(up.note_array(include_grace_notes=True)["id"].astype(str))
        j = len(u & ids) / len(u | ids)
        if best is None or j > best[0]:
            best = (j, v, up)
    return best


def batik_performances(stems: set[str] | None = None):
    """(stem, AlignedPerformance with the MusicXML-based performed score); D-11 loader."""
    for ap in bm.iter_aligned(musicxml_score=True, stems=stems):
        yield bm.stem_of(ap.score), ap


def batik_annotations(stem: str, score) -> tuple[list[float], list[float], pd.DataFrame]:
    """Annotated phrase starts, phrase ends and cadences (``beat``, ``cadence``) in the
    performed score's beats (D-11 ``phrase_annotations``)."""
    ann = bm.phrase_annotations(score)
    return ann.starts, ann.ends, ann.cadence_table()


# --------------------------------------------------------------------------- metrics


def boundary_prf(pred, true, tol: float, first: float) -> dict:
    """One-to-one matching of boundaries within ``tol`` beats (closest pairs first); the
    piece's first onset is excluded from both sets."""
    pred = sorted(p for p in pred if p > first + 1e-6)
    true = sorted(t for t in true if t > first + 1e-6)
    pairs = sorted((abs(p - t), i, j) for i, p in enumerate(pred) for j, t in enumerate(true)
                   if abs(p - t) <= tol + 1e-6)
    ui, uj = set(), set()
    for _, i, j in pairs:
        if i not in ui and j not in uj:
            ui.add(i)
            uj.add(j)
    tp = len(ui)
    p = tp / len(pred) if pred else np.nan
    r = tp / len(true) if true else np.nan
    f = 2 * p * r / (p + r) if p + r > 0 else 0.0
    return {"tp": tp, "n_pred": len(pred), "n_true": len(true), "P": p, "R": r, "F1": f}


def feature_cols(groups: dict, markings: bool, drop: tuple[str, ...] = ()) -> list[str]:
    return [c for g, cs in groups.items() if g != "position" and g not in drop
            and (markings or g not in MARKING_GROUPS) for c in cs]


def cv_gbm(X, y, measure, cfg: ShapingConfig) -> float:
    """Gradient boosting with the same written-bar folds and buffer as the ridge."""
    from sklearn.ensemble import HistGradientBoostingRegressor

    fold = _folds(measure, cfg.block_bars, cfg.n_folds)
    oof = np.full(len(y), np.nan)
    for f in np.unique(fold):
        te = fold == f
        tr = _buffered_train(measure, te, cfg.buffer_bars, None)
        if tr.sum() < 20:
            continue
        g = HistGradientBoostingRegressor(max_iter=200, learning_rate=0.05, max_leaf_nodes=15,
                                          min_samples_leaf=20, l2_regularization=1.0)
        oof[te] = g.fit(X[tr], y[tr]).predict(X[te])
    ok = np.isfinite(oof)
    return float(1 - np.sum((y[ok] - oof[ok]) ** 2) / np.sum((y[ok] - y[ok].mean()) ** 2))


def arc_stats(tc, starts) -> dict:
    """Per-phrase parabolas of the smooth log tempo (F-03 ``phrase_arcs``): share of tempo
    variance between phrase means, in-sample R² of the parabolas within phrases, fraction of
    phrases with c2 < 0 (slower at both edges than in the middle)."""
    a = phrase_arcs(tc, starts)
    x, y = tc.beats["beat"].to_numpy(), tc.beats["tempo_log_ratio"].to_numpy()
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    ssw = ssres = 0.0
    for r in a.itertuples():
        m = (x >= r.start_beat) & (x < r.end_beat)
        w = float(np.sum((y[m] - y[m].mean()) ** 2)) if m.any() else 0.0
        ssw += w
        if np.isfinite(r.r2):
            ssres += (1 - r.r2) * w
        else:
            ssres += w
    ok = a[np.isfinite(a["c2"])]
    return {"n_phrases": len(ok), "between_share": 1 - ssw / ss_tot if ss_tot else np.nan,
            "arc_r2_within": 1 - ssres / ssw if ssw else np.nan,
            "c2_neg_frac": float((ok["c2"] < 0).mean()) if len(ok) else np.nan}


def shifted(beats, shift: float, lo: float, hi: float) -> list[float]:
    """Circular shift of boundaries inside [lo, hi): keeps their number and spacing."""
    return sorted(lo + np.mod(np.asarray(beats, float) - lo + shift, hi - lo))


def tempo_seg(data: dict, tc) -> pd.DataFrame:
    """Smooth tempo centred within each F-03 tempo segment (between marked tempo changes)."""
    te = data["tempo"].copy()
    seg = tc.positions.set_index(tc.positions["beat"].round(6))["segment"]
    te["seg"] = seg.reindex(te["beat"].round(6)).to_numpy()
    te["y"] = te["y"] - te.groupby("seg")["y"].transform("mean")
    return te


# --------------------------------------------------------------------------- Batik


def batik_variants(ap, starts, ends, cad):
    s = ap.score
    bp = score_basis(s)
    beats = bp.notes["beat"]
    lo, hi = float(beats.min()), float(beats.max()) + 1
    shift = 2 * bp.meta["beats_per_bar"]
    detail = BasisConfig(phrase_detail=True, phrase_max_bars=NOSPLIT)
    sh_cad = cad.assign(beat=shifted(cad["beat"], shift, lo, hi)) if len(cad) else cad
    return bp, {
        "proxy": (bp, ()),
        "no_phrase": (bp, ("phrase",)),
        "ann": (score_basis(s, phrase_boundaries_beats=starts), ()),
        "ann_nosplit": (score_basis(s, phrase_boundaries_beats=starts,
                                    config=BasisConfig(phrase_max_bars=NOSPLIT)), ()),
        "proxy_detail": (score_basis(s, config=BasisConfig(phrase_detail=True)), ()),
        "ann_detail": (score_basis(s, phrase_boundaries_beats=starts, phrase_ends_beats=ends,
                                   config=detail), ()),
        "ann_detail_cad": (score_basis(s, phrase_boundaries_beats=starts,
                                       phrase_ends_beats=ends, cadences=cad, config=detail), ()),
        "shift_detail_cad": (score_basis(s, phrase_boundaries_beats=shifted(starts, shift, lo, hi),
                                         phrase_ends_beats=shifted(ends, shift, lo, hi),
                                         cadences=sh_cad, config=detail), ()),
    }


GBM_VARIANTS = ("proxy", "ann_detail_cad", "shift_detail_cad")


def run_batik() -> None:
    B, R, A = [], [], []
    lomo = []
    for stem, ap in batik_performances():
        t0 = time.time()
        starts, ends, cad = batik_annotations(stem, ap.score)
        tc = tempo_model(ap)
        bp, variants = batik_variants(ap, starts, ends, cad)
        bpb = bp.meta["beats_per_bar"]
        first = float(bp.notes["beat"].min())
        ph = bp.phrases
        ms = np.unique((bp.notes["beat"] - bp.notes["beat_in_bar"]).to_numpy())
        preds = {"proxy": ph.loc[ph["source"] == "proxy", "start_beat"].tolist(),
                 "proxy_split": ph["start_beat"].tolist(),
                 "grid4": ms[::4].tolist(), "grid2": ms[::2].tolist()}
        for tol, tn in ((1.0, "1beat"), (bpb, "1bar")):
            for name, pred in preds.items():
                B.append({"movement": stem, "tol": tn, "method": name,
                          **boundary_prf(pred, starts, tol, first)})
        for vname, (b, drop) in variants.items():
            data = channel_data(ap, b, tc, CFG)
            data["tempo_seg"] = tempo_seg(data, tc)
            for ch, df in data.items():
                y, m = df["y"].to_numpy(float), df["measure_number"].to_numpy()
                row = {"movement": stem, "variant": vname, "channel": ch, "n": len(y),
                       "y_sd": float(np.std(y))}
                for mk, key in ((True, "r2"), (False, "r2_nm")):
                    X = df[feature_cols(b.groups, mk, drop)].to_numpy(float)
                    row[key] = _cv_ridge(X, y, m, CFG)[1]
                    if vname in ("proxy", "ann") and not mk:
                        row["r2_nm_noclip"] = _cv_ridge(X, y, m, CFG_F05)[1]
                if ch in ("tempo", "tempo_seg") and vname in GBM_VARIANTS:
                    X = df[feature_cols(b.groups, False, drop)].to_numpy(float)
                    row["r2_nm_gbm"] = cv_gbm(X, y, m, CFG)
                R.append(row)
            if vname in ("proxy", "proxy_detail", "ann_detail_cad", "shift_detail_cad"):
                d = data["tempo"].copy()
                d["y"] = d["y"] - d["y"].mean()
                d["movement"] = stem
                d["variant"] = vname
                lomo.append(d[["movement", "variant", "y",
                               *feature_cols(b.groups, False, drop)]])
        lo, hi = first, float(bp.notes["beat"].max()) + 1
        for name, st in (("ann", starts), ("proxy_split", preds["proxy_split"]),
                         ("shift", shifted(starts, 2 * bpb, lo, hi)), ("grid4", preds["grid4"])):
            A.append({"movement": stem, "bounds": name, **arc_stats(tc, st)})
        print(f"{stem}: {time.time() - t0:.1f}s, {len(starts)} starts, {len(cad)} cadences",
              flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(B).to_csv(OUT / "batik_boundaries.csv", index=False)
    pd.DataFrame(R).to_csv(OUT / "batik_coherence.csv", index=False)
    pd.DataFrame(A).to_csv(OUT / "batik_arcs.csv", index=False)
    pd.concat(lomo, ignore_index=True).to_pickle(OUT / "batik_lomo_data.pkl")
    report_batik()


def report_batik() -> None:
    B = pd.read_csv(OUT / "batik_boundaries.csv")
    R = pd.read_csv(OUT / "batik_coherence.csv")
    A = pd.read_csv(OUT / "batik_arcs.csv")
    print("\nboundaries (mean over movements):")
    print(B.groupby(["tol", "method"])[["P", "R", "F1"]].mean().round(3).to_string())
    tot = B.groupby(["tol", "method"])[["tp", "n_pred", "n_true"]].sum()
    tot["P"], tot["R"] = tot["tp"] / tot["n_pred"], tot["tp"] / tot["n_true"]
    tot["F1"] = 2 * tot["P"] * tot["R"] / (tot["P"] + tot["R"])
    print("pooled counts:\n", tot.round(3).to_string())
    for key in ("r2_nm", "r2", "r2_nm_noclip", "r2_nm_gbm"):
        print(f"\ncoherence {key}, mean over 36 movements:")
        print(R.pivot_table(index="channel", columns="variant", values=key, aggfunc="mean")
              .round(3).to_string())
    print("\ncoherence r2_nm, median:")
    print(R.pivot_table(index="channel", columns="variant", values="r2_nm", aggfunc="median")
          .round(3).to_string())
    from scipy.stats import wilcoxon

    piv = R[R["channel"] == "tempo"].pivot(index="movement", columns="variant", values="r2_nm")
    for a, b in (("ann_detail_cad", "proxy"), ("ann_detail_cad", "shift_detail_cad"),
                 ("ann", "proxy"), ("ann_nosplit", "proxy"), ("proxy_detail", "proxy"),
                 ("ann_detail", "proxy_detail")):
        d = piv[a] - piv[b]
        print(f"tempo r2_nm {a} - {b}: mean {d.mean():.3f}, median {d.median():.3f}, "
              f"{int((d > 0).sum())}/{len(d)} better, wilcoxon p {wilcoxon(d).pvalue:.2g}")
    print("\narcs (mean over movements):")
    print(A.groupby("bounds")[["n_phrases", "between_share", "arc_r2_within", "c2_neg_frac"]]
          .mean().round(3).to_string())


# --------------------------------------------------------------------------- leave-movement-out


def run_lomo() -> None:
    """One model per phrase variant over all 36 movements (Batik's own tempo rules),
    6-fold grouped by movement: ridge (standardized; RidgeCV picks the penalty by
    leave-one-row-out, which favors small penalties) and GBM."""
    from sklearn.ensemble import HistGradientBoostingRegressor
    from sklearn.linear_model import RidgeCV
    from sklearn.model_selection import GroupKFold
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    D = pd.read_pickle(OUT / "batik_lomo_data.pkl")
    rows = []
    for v, d in D.groupby("variant"):
        d = d.dropna(axis=1, how="all").fillna(0.0)
        cols = [c for c in d.columns if c not in ("movement", "variant", "y")]
        X, y, g = d[cols].to_numpy(float), d["y"].to_numpy(float), d["movement"].to_numpy()
        for name, make in (
            ("ridge", lambda: make_pipeline(StandardScaler(),
                                            RidgeCV(alphas=np.logspace(-2, 4, 13)))),
            ("gbm", lambda: HistGradientBoostingRegressor(
                max_iter=300, learning_rate=0.05, max_leaf_nodes=31, min_samples_leaf=50,
                l2_regularization=1.0)),
        ):
            oof = np.full(len(y), np.nan)
            for tr, te in GroupKFold(6).split(X, y, g):
                oof[te] = make().fit(X[tr], y[tr]).predict(X[te])
            per = pd.DataFrame({"g": g, "y": y, "p": oof}).groupby("g").apply(
                lambda q: 1 - np.sum((q.y - q.p) ** 2) / np.sum((q.y - q.y.mean()) ** 2))
            rows.append({"variant": v, "model": name, "n": len(y),
                         "r2_pooled": 1 - np.sum((y - oof) ** 2) / np.sum((y - y.mean()) ** 2),
                         "r2_movement_mean": float(per.mean()),
                         "r2_movement_median": float(per.median())})
            print(rows[-1], flush=True)
    pd.DataFrame(rows).to_csv(OUT / "batik_lomo.csv", index=False)


# --------------------------------------------------------------------------- transfer


def _keys(notes: pd.DataFrame, beats) -> list[tuple[int, float]]:
    n = notes.drop_duplicates("beat")
    n = n.set_index(n["beat"].round(6))
    return [(int(n.loc[round(b, 6), "measure_number"]),
             round(float(n.loc[round(b, 6), "beat_in_bar"]), 3)) for b in beats]


def _pitchsets(notes: pd.DataFrame) -> pd.Series:
    return notes.groupby(notes["beat"].round(6))["pitch"].apply(frozenset)


def transfer_beats(src, tgt, beats, offset: int = 0) -> tuple[list[float], float]:
    """Map beats of the Batik performed score to every onset of the target performed score
    with the same written bar (+ ``offset``) and beat in bar; also return the share of mapped
    onsets whose starting pitch set is identical in both scores."""
    sp, tp = _pitchsets(src), _pitchsets(tgt)
    tn = tgt.drop_duplicates("beat")
    lut: dict[tuple[int, float], list[float]] = {}
    for b, mn, bib in zip(tn["beat"], tn["measure_number"], tn["beat_in_bar"].round(3),
                          strict=True):
        lut.setdefault((int(mn), float(bib)), []).append(float(b))
    out, ok = [], []
    for b, (mn, bib) in zip(beats, _keys(src, beats), strict=True):
        for x in lut.get((mn + offset, bib), []):
            out.append(x)
            ok.append(sp.get(round(b, 6)) == tp.get(round(x, 6)))
    return sorted(set(out)), float(np.mean(ok)) if ok else np.nan


def vienna_k331():
    part = load_score_part(vn.DEFAULT_ROOT / "musicxml" / "Mozart_K331_1st-mov.musicxml")
    for ap in vn.iter_aligned():
        if "Mozart" not in ap.score.score_id:
            continue
        j, v, up = unfold_like(part, set(ap.score.notes["id"].astype(str)))
        s = score_from_partitura(up, score_id=ap.score.score_id, piece_id=ap.score.piece_id,
                                 meta={"unfolded": v, "id_jaccard": j}, keep_part=True)
        yield AlignedPerformance(ap.performance, s, ap.alignment)


def transfer_set(name: str, stem: str, aps, by_beat: bool) -> tuple[list, list]:
    """``by_beat``: the target is Batik's performed score from beat 0 with bars numbered in
    performed order (Vienna); bars are renumbered to Batik's written bars so repeat passes share
    a CV fold."""
    s_batik = next(batik_performances({stem}))[1].score
    src = score_basis(s_batik).notes
    starts, ends, cad = batik_annotations(stem, s_batik)
    written = src.drop_duplicates("beat").set_index(src.drop_duplicates("beat")["beat"]
                                                    .round(6))["measure_number"]
    variants: dict[str, list] = {"proxy": [], "ann": [], "proxy_detail": [], "ann_detail_cad": []}
    tcs, brows, info = [], [], {}
    for ap in aps:
        bp = score_basis(ap.score)
        tgt = bp.notes
        tc = tempo_model(ap)
        last = float(tgt["beat"].max())
        if by_beat:
            st = [b for b in starts if b <= last]
            en = [b for b in ends if b <= last]
            cb = cad[cad["beat"] <= last]
            sp, tp = _pitchsets(src), _pitchsets(tgt)
            rate, off = float(np.mean([sp.get(round(b, 6)) == tp.get(round(b, 6))
                                       for b in st])), "beat"
        else:
            best = max(((transfer_beats(src, tgt, starts, o), o) for o in (-1, 0, 1)),
                       key=lambda t: (np.nan_to_num(t[0][1]), len(t[0][0])))
            (st, rate), off = best
            en = transfer_beats(src, tgt, ends, off)[0]
            cb = pd.DataFrame([(b, typ) for typ, g in cad.groupby("cadence")
                               for b in transfer_beats(src, tgt, g["beat"].tolist(), off)[0]],
                              columns=["beat", "cadence"])
        info = {"offset": off, "pitch_match": rate, "n_starts": len(st)}
        detail = BasisConfig(phrase_detail=True, phrase_max_bars=NOSPLIT)
        bases = {"proxy": bp,
                 "ann": score_basis(ap.score, phrase_boundaries_beats=st),
                 "proxy_detail": score_basis(ap.score, config=BasisConfig(phrase_detail=True)),
                 "ann_detail_cad": score_basis(ap.score, phrase_boundaries_beats=st,
                                               phrase_ends_beats=en, cadences=cb,
                                               config=detail)}
        if by_beat:
            for b in [*bases.values(), tc]:
                for df in ((b.notes, b.onsets) if hasattr(b, "onsets") else (b.positions,)):
                    start = (df["beat"] - df["beat_in_bar"]).round(6)
                    df["measure_number"] = written.reindex(start).to_numpy()
        for k, b in bases.items():
            variants[k].append(b)
        tcs.append(tc)
        ph = bp.phrases
        for tol, tn in ((1.0, "1beat"), (bp.meta["beats_per_bar"], "1bar")):
            brows.append({"set": name, "tol": tn, "performance": ap.performance.performance_id,
                          **info, **boundary_prf(ph.loc[ph["source"] == "proxy", "start_beat"],
                                                 st, tol, float(tgt["beat"].min()))})
        print(name, ap.performance.performance_id, info, flush=True)
    rows = []
    for v, bs in variants.items():
        pooled = pooled_structural_coherence(aps, bs, tcs, CFG) if len(aps) > 1 else None
        singles = [structural_coherence(ap, b, t, CFG).summary.set_index("channel")
                   for ap, b, t in zip(aps, bs, tcs, strict=True)]
        for ch in ("velocity", "timing", "tempo", "articulation"):
            rows.append({"set": name, "variant": v, "channel": ch, "n_perf": len(aps), **info,
                         "pooled_r2": pooled.r2(ch) if pooled else np.nan,
                         "pooled_r2_nm": pooled.r2(ch, "r2_no_markings") if pooled else np.nan,
                         "single_r2_nm_mean": float(np.mean(
                             [s.loc[ch, "r2_no_markings"] for s in singles]))})
    return rows, brows


def run_transfer() -> None:
    R, B = [], []
    r, b = transfer_set("vienna_k331_1", "kv331_1", list(vienna_k331()), by_beat=True)
    R += r
    B += b
    md = asap_index()
    for folder, stem in ASAP_TARGETS.items():
        aps = [align_performance(load_asap_score(row), load_asap_performance(row))
               for _, row in md[md["folder"] == folder].iterrows()]
        r, b = transfer_set(f"asap_{stem}", stem, aps, by_beat=False)
        R += r
        B += b
    R, B = pd.DataFrame(R), pd.DataFrame(B)
    R.to_csv(OUT / "transfer_coherence.csv", index=False)
    B.to_csv(OUT / "transfer_boundaries.csv", index=False)
    for key in ("pooled_r2_nm", "single_r2_nm_mean"):
        print(f"\n{key}:")
        print(R.pivot_table(index=["set", "channel"], columns="variant", values=key)
              .round(3).to_string())
    print(B.groupby(["set", "tol"])[["pitch_match", "P", "R", "F1"]].mean().round(3).to_string())


if __name__ == "__main__":
    parts = sys.argv[1:] or ["batik", "lomo", "transfer"]
    if "batik" in parts:
        run_batik()
    if "report" in parts:
        report_batik()
    if "lomo" in parts:
        run_lomo()
    if "transfer" in parts:
        run_transfer()
