"""F-04b: validate the pedal-blur harmony-change rule and the pedal lift window.

    uv run python scripts/validate_control_f04b.py            # everything, about 3 min
    uv run python scripts/validate_control_f04b.py --part harmony
    uv run python scripts/validate_control_f04b.py --part pedal

Ground truth: DCML harmony labels (DCMLab/mozart_piano_sonatas, the ``annotations`` submodule
of Batik-plays-Mozart, CC BY-NC-SA 4.0). The Batik repo attaches each label to a score note id
(``score_parts_annotated/<stem>_spart_harmony.csv``, unfolded like the match files); chord tones
and root come from the DCML ``harmonies/*.tsv`` (fifths above the local tonic), joined on
(mn, label, globalkey, localkey). A ground-truth change is a label whose absolute root pitch
class differs from the previous label's (``root``); ``pcset`` is any change of the chord-tone
pitch-class set (inversions and suspensions do not count; V -> V7 does).

Writes ``data/interim/control_f04b/`` (gitignored): ``harmony_grid.csv`` (rule variants x
tolerance x split), ``harmony_errors.csv`` (every FN / FP with its category), ``texture.csv``,
``pedal_lifts.csv`` (lift offsets around changes), ``pedal_threshold.csv``. Results are written
up in ``docs/specs/control-validation.md``.
"""

from __future__ import annotations

import argparse
import math
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "interim" / "control_f04b"
BATIK = ROOT / "data" / "raw" / "batik_mozart"
DEV_SONATAS = ("kv279", "kv280", "kv281", "kv282", "kv283")  # the rest is the test split

_LETTER = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
_MAJOR = (0, 2, 4, 5, 7, 9, 11)
_MINOR = (0, 2, 3, 5, 7, 8, 10)
_ROMAN = {"i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6, "vii": 7}


# --------------------------------------------------------------------------- DCML labels


def key_pc(name: str) -> tuple[int, bool]:
    """'Bb' -> (10, False); 'f#' -> (6, True)."""
    pc = _LETTER[name[0].upper()] + name[1:].count("#") - name[1:].count("b")
    return pc % 12, name[0].islower()


def numeral_key(numeral: str, tonic: int, minor: bool) -> tuple[int, bool]:
    """Key named by a Roman numeral relative to (tonic, minor), e.g. 'bVI', 'V/V'."""
    for part in reversed(numeral.split("/")):
        acc = len(part) - len(part.lstrip("#b"))
        shift = part[:acc].count("#") - part[:acc].count("b")
        rom = part[acc:]
        deg = _ROMAN[rom.lower()]
        tonic = (tonic + (_MINOR if minor else _MAJOR)[deg - 1] + shift) % 12
        minor = rom.islower()
    return tonic, minor


def _fifths(s: object) -> list[int]:
    if not isinstance(s, str) or not s.strip():
        return []
    return [int(x) for x in s.split(",")]


def label_table(stem: str, score) -> pd.DataFrame:
    """Chord labels of one movement on the performed score: beat, root_pc, pcs, label, ..."""
    sp = pd.read_csv(BATIK / "score_parts_annotated" / f"{stem}_spart_harmony.csv")
    sp = sp[sp["label"].notna() & sp["chord"].notna()].copy()
    tsv = pd.read_csv(BATIK / "annotations" / "harmonies" /
                      f"{stem.replace('kv', 'K').replace('_', '-')}.tsv", sep="\t")  # fmt: skip
    tsv = tsv[tsv["chord_tones"].notna()]
    keys = ["mn", "label", "globalkey", "localkey"]
    extra = tsv[keys + ["chord_tones", "added_tones", "root", "bass_note", "figbass",
                        "pedal", "relativeroot"]].drop_duplicates(keys)  # fmt: skip
    n0 = len(sp)
    sp = sp.merge(extra, on=keys, how="inner")
    sn = score.notes
    beat_of = dict(zip(sn["id"].astype(str), sn["onset_beat"].astype(float), strict=True))
    sp["beat"] = sp["id"].map(beat_of)
    sp = sp[sp["beat"].notna()].sort_values("beat", kind="stable")
    rows = []
    for r in sp.itertuples(index=False):
        g, gmin = key_pc(r.globalkey)
        lt, _ = numeral_key(r.localkey, g, gmin)
        tones = _fifths(r.chord_tones)
        rows.append({
            "beat": float(r.beat), "label": r.label, "chord": r.chord,
            "root_pc": (lt + 7 * int(r.root)) % 12,
            "bass_pc": (lt + 7 * int(r.bass_note)) % 12,
            "pcs": frozenset((lt + 7 * f) % 12 for f in tones),
            "inversion": isinstance(r.figbass, str) or (isinstance(r.figbass, float)
                                                        and not math.isnan(r.figbass)),
            "pedal": isinstance(r.pedal, str),
        })  # fmt: skip
    out = pd.DataFrame(rows)
    out.attrs["n_labels"], out.attrs["n_joined"] = n0, len(out)
    return out.drop_duplicates("beat", keep="last").reset_index(drop=True)


def gt_changes(lab: pd.DataFrame, kind: str = "root") -> pd.DataFrame:
    col = "root_pc" if kind == "root" else "pcs"
    v = lab[col].tolist()
    keep = [i for i in range(1, len(v)) if v[i] != v[i - 1]]
    out = lab.iloc[keep].copy()
    out["prev_root_pc"] = lab["root_pc"].iloc[[i - 1 for i in keep]].to_numpy()
    out["prev_pcs"] = lab["pcs"].iloc[[i - 1 for i in keep]].to_numpy()
    out["prev_pedal"] = lab["pedal"].iloc[[i - 1 for i in keep]].to_numpy()
    return out.reset_index(drop=True)


# --------------------------------------------------------------------------- matching


def match(det: np.ndarray, gt: np.ndarray, tol: float) -> tuple[np.ndarray, np.ndarray]:
    """Greedy one-to-one matching by distance; returns (det_matched, gt_matched) masks."""
    dm, gm = np.zeros(len(det), bool), np.zeros(len(gt), bool)
    if not len(det) or not len(gt):
        return dm, gm
    d = np.abs(det[:, None] - gt[None, :])
    ii, jj = np.nonzero(d <= tol + 1e-9)
    for k in np.argsort(d[ii, jj], kind="stable"):
        i, j = ii[k], jj[k]
        if not dm[i] and not gm[j]:
            dm[i] = gm[j] = True
    return dm, gm


def prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    p = tp / (tp + fp) if tp + fp else float("nan")
    r = tp / (tp + fn) if tp + fn else float("nan")
    f = 2 * p * r / (p + r) if p + r else float("nan")
    return p, r, f


def bar_texture(score) -> np.ndarray:
    """Left-hand (staff 2) texture per measure row: broken / chordal / sparse / none.

    broken: at least 2 LH onsets per beat, mostly single notes (Alberti, broken chords, runs);
    chordal: LH onsets carry 1.5 or more notes on average (block or repeated chords);
    sparse: fewer than 2 single-note LH onsets per beat (bass line); none: no LH notes.
    """
    from pianolens.features._score_utils import score_note_frame

    sf = score_note_frame(score)
    sf = sf[~sf["is_grace"] & (sf["staff"] == 2)]
    ms = score.measures
    nb = len(ms)
    out = np.array(["none"] * nb, dtype=object)
    bar_beats = {}
    sfa = score_note_frame(score)
    for mi, g in sfa.groupby("measure_idx"):
        bar_beats[mi] = max(g["beat"].max() + g["dur_beat"].max() - g["beat"].min(), 1.0)
    for mi, g in sf.groupby("measure_idx"):
        if mi < 0:
            continue
        per_onset = g.groupby("beat").size()
        rate = len(per_onset) / bar_beats.get(mi, 1.0)
        poly = float(per_onset.mean())
        out[mi] = "chordal" if poly >= 1.5 else ("broken" if rate >= 2 else "sparse")
    return out


# --------------------------------------------------------------------------- harmony part


def load_movements():
    from pianolens.data import batik_mozart

    return list(batik_mozart.iter_aligned())


BASE = ("all", True, 0.15, "beat", 1.0)  # the F-04 rule
WINDOWS = (("beat", 0.5), ("beat", 1.0), ("beat", 2.0), ("quarter", 0.5), ("quarter", 1.0),
           ("quarter", 1.5), ("quarter", 2.0))  # fmt: skip
TOLS = (("beat", 0.5), ("beat", 1.0), ("quarter", 0.5), ("quarter", 1.0))


def _q_of_b(score) -> pd.Series:
    sn = score.notes
    return pd.Series(sn["onset_quarter"], index=sn["onset_beat"]).groupby(level=0).first()


def harmony_part(aps, chosen: tuple | None = None) -> None:
    from pianolens.features.control import harmony_changes, harmony_windows

    variants = [(t, b, mw, u, w) for t in ("all", "no_maj7", "functional", "triads")
                for b in (True, False) for mw in (0.1, 0.15, 0.25) for u, w in WINDOWS]
    grid_rows, err_rows, tex_rows, join = [], [], [], []
    detail = {BASE} | ({chosen} if chosen else set())
    for ap in aps:
        stem = ap.score.score_id.split(":")[1]
        split = "dev" if stem.split("_")[0] in DEV_SONATAS else "test"
        lab = label_table(stem, ap.score)
        join.append((stem, lab.attrs["n_labels"], lab.attrs["n_joined"]))
        gts = {k: gt_changes(lab, k) for k in ("root", "pcset")}
        ts = str(ap.score.notes["ts_beats"][0]) + "/" + str(ap.score.notes["ts_beat_type"][0])
        tex = bar_texture(ap.score)
        qob = _q_of_b(ap.score)
        wcache = {}
        for v in variants:
            tmpl, bass, mw, unit, wsz = v
            if (mw, unit, wsz) not in wcache:
                wcache[(mw, unit, wsz)] = harmony_windows(ap.score, wsz, mw, unit)
            det = harmony_changes(ap.score, wsz, mw, windows=wcache[(mw, unit, wsz)],
                                  templates=tmpl, require_bass_change=bass)  # fmt: skip
            db = det["beat"].to_numpy(float)
            for kind, gt in gts.items():
                gb = gt["beat"].to_numpy(float)
                for tu, tol in TOLS:
                    a, b = (db, gb) if tu == "beat" else (qob.reindex(db).to_numpy(float),
                                                          qob.reindex(gb).to_numpy(float))
                    dm, gm = match(a, b, tol)
                    grid_rows.append({"stem": stem, "split": split, "ts": ts, "templates": tmpl,
                                      "bass": bass, "min_weight": mw, "unit": unit,
                                      "window": wsz, "gt_kind": kind, "tol_unit": tu,
                                      "tol": tol, "tp": int(gm.sum()), "fp": int((~dm).sum()),
                                      "fn": int((~gm).sum())})  # fmt: skip
                    if v in detail and kind == "root" and (tu, tol) == ("quarter", 1.0):
                        _errors(ap, v, stem, split, ts, det, dm, gt, gm, lab,
                                wcache[(mw, unit, wsz)], tex, qob, err_rows, tex_rows)
    OUT.mkdir(parents=True, exist_ok=True)
    grid = pd.DataFrame(grid_rows)
    grid.to_csv(OUT / "harmony_grid.csv", index=False)
    errs = pd.DataFrame(err_rows)
    errs.to_csv(OUT / "harmony_errors.csv", index=False)
    tex_df = pd.DataFrame(tex_rows)
    tex_df.to_csv(OUT / "texture.csv", index=False)
    jn = pd.DataFrame(join, columns=["stem", "n_labels", "n_joined"])
    print(f"labels joined to DCML chord tones: {jn.n_joined.sum()} / {jn.n_labels.sum()}; "
          f"min per movement {(jn.n_joined / jn.n_labels).min():.3f}")
    ng = grid[(grid.templates == "all") & grid.bass & (grid.min_weight == 0.15)
              & (grid.unit == "beat") & (grid.window == 1.0) & (grid.tol == 1.0)
              & (grid.tol_unit == "quarter")]  # fmt: skip
    print("GT changes: root", int(ng[ng.gt_kind == "root"].eval("tp + fn").sum()),
          "| pcset", int(ng[ng.gt_kind == "pcset"].eval("tp + fn").sum()))
    _report_grid(grid, chosen)
    for v in sorted(detail, key=str):
        print(f"\n######## error analysis for {v} (gt root, tol 1 quarter)")
        _report_errors(errs[errs.variant == str(v)], tex_df[tex_df.variant == str(v)])


def _errors(ap, v, stem, split, ts, det, dm, gt, gm, lab, win, tex, qob, err_rows, tex_rows):
    from pianolens.features.control import _TEMPLATE_SETS
    from pianolens.features.correctness import measure_rows

    chords = _TEMPLATE_SETS[v[0]]
    unit, wsz = v[3], v[4]

    def u(b: np.ndarray) -> np.ndarray:
        return b if unit == "beat" else qob.reindex(b).to_numpy(float)

    ws = win["window_start"].to_numpy(float)
    gb, db, lb = (gt["beat"].to_numpy(float), det["beat"].to_numpy(float),
                  lab["beat"].to_numpy(float))  # fmt: skip
    gu, du, lu = u(gb), u(db), u(lb)
    for side, arr, hits in (("det", db, dm), ("gt", gb, gm)):
        mis = measure_rows(ap.score.measures, qob.reindex(arr).to_numpy(float))
        for mi, hit in zip(mis, hits, strict=True):
            tex_rows.append({"variant": str(v), "stem": stem, "split": split, "side": side,
                             "texture": tex[mi] if mi >= 0 else "none", "hit": bool(hit)})
    for j in np.nonzero(~gm)[0]:  # false negatives
        g = gt.iloc[j]
        k = int(np.searchsorted(ws, gu[j] + 1e-9, side="right")) - 1
        cat = "other"
        if k < 1:
            cat = "piece_start"
        elif ((gu < gu[j]) & (gu >= ws[k])).any():
            cat = "two_changes_in_one_window"
        else:
            cur, prev = win.iloc[k], win.iloc[k - 1]
            if cur["bass"] == prev["bass"]:
                cat = "same_bass"
            elif any((cur["pcs"] | prev["pcs"]) <= c for c in chords):
                cat = "union_fits_one_chord"
            elif len(du) and np.min(np.abs(du - gu[j])) <= 2 * wsz:
                cat = "detected_off_by_1-2_windows"
        interval = (int(g["root_pc"]) - int(g["prev_root_pc"])) % 12
        err_rows.append({"variant": str(v), "stem": stem, "split": split, "ts": ts,
                         "type": "FN", "beat": g["beat"], "label": g["label"], "category": cat,
                         "root_interval": min(interval, 12 - interval),
                         "gt_pedal": bool(g["pedal"]) or bool(g["prev_pedal"]),
                         "gt_inversion": bool(g["inversion"])})  # fmt: skip
    for i in np.nonzero(~dm)[0]:  # false positives
        k = int(np.searchsorted(lb, db[i] + 1e-9, side="right")) - 1
        act = lab.iloc[max(k, 0)]
        w = win[np.isclose(win["window_start"], det.iloc[i]["window_start"])]
        wpcs = w["pcs"].iloc[0] if len(w) else frozenset()
        if ((np.abs(lu - du[i]) <= max(wsz, 1.0) + 1e-9) & (lb > lb[0])).any():
            cat = "label_change_same_root"
        elif not wpcs <= act["pcs"]:
            cat = "non_chord_tones"
        else:
            cat = "chord_tones_only"
        err_rows.append({"variant": str(v), "stem": stem, "split": split, "ts": ts,
                         "type": "FP", "beat": db[i], "label": act["label"], "category": cat,
                         "root_interval": np.nan, "gt_pedal": bool(act["pedal"]),
                         "gt_inversion": bool(act["inversion"])})  # fmt: skip


def _pooled(df: pd.DataFrame) -> pd.Series:
    tp, fp, fn = int(df.tp.sum()), int(df.fp.sum()), int(df.fn.sum())
    p, r, f = prf(tp, fp, fn)
    return pd.Series({"tp": tp, "fp": fp, "fn": fn, "precision": p, "recall": r, "f1": f})


def _report_grid(grid: pd.DataFrame, chosen: tuple | None) -> None:
    pd.set_option("display.width", 220)
    pd.set_option("display.max_columns", 30)
    keys = ["templates", "bass", "min_weight", "unit", "window"]

    def sel(g, v):
        return g[(g.templates == v[0]) & (g.bass == v[1]) & (g.min_weight == v[2])
                 & (g.unit == v[3]) & (g.window == v[4])]  # fmt: skip

    def pooled(df, by):
        return df.groupby(by).apply(_pooled, include_groups=False).round(3)

    for name, v in (("baseline F-04 rule", BASE), ("chosen", chosen)):
        if v is None:
            continue
        b = sel(grid, v)
        print(f"\n== {name} {v} ==")
        print(pooled(b, ["gt_kind", "tol_unit", "tol"]))
        print("root, tol 1 quarter, by split:")
        rq = b[(b.gt_kind == "root") & (b.tol_unit == "quarter") & (b.tol == 1.0)]
        print(pooled(rq, "split"))
        print("root, tol 1 quarter, by time signature:")
        print(pooled(rq, "ts"))
    g = grid[(grid.gt_kind == "root") & (grid.tol_unit == "quarter") & (grid.tol == 1.0)]
    dev = pooled(g[g.split == "dev"], keys)[["precision", "recall", "f1"]]
    test = pooled(g[g.split == "test"], keys)[["precision", "recall", "f1"]]
    tab = dev.join(test, rsuffix="_test")
    print("\n== variants, gt root, tol 1 quarter: top 15 by dev F1 ==")
    print(tab.sort_values("f1", ascending=False).head(15).to_string())
    print("baseline row:", tab.loc[BASE].to_dict())
    print("\n== one factor at a time from the baseline (dev F1 / test F1) ==")
    for k_i, k in enumerate(keys):
        for val in sorted(g[k].unique(), key=str):
            v = list(BASE)
            v[k_i] = val
            if k in ("unit", "window"):
                continue
            v = tuple(v)
            if v in tab.index:
                r = tab.loc[v]
                print(f"  {k}={val}: dev {r.f1:.3f} test {r.f1_test:.3f} "
                      f"(P {r.precision_test:.3f} R {r.recall_test:.3f})")
    for unit, w in WINDOWS:
        v = BASE[:3] + (unit, w)
        r = tab.loc[v]
        print(f"  window={w} {unit}: dev {r.f1:.3f} test {r.f1_test:.3f} "
              f"(P {r.precision_test:.3f} R {r.recall_test:.3f})")


def _report_errors(errs: pd.DataFrame, tex: pd.DataFrame) -> None:
    print("\n== error categories (baseline, gt=root, tol=1) ==")
    for t in ("FN", "FP"):
        e = errs[errs.type == t]
        print(t, len(e))
        print(e.category.value_counts().to_string())
    fn = errs[errs.type == "FN"]
    print("FN in annotated pedal points:", int(fn.gt_pedal.sum()),
          "| FN at inversions:", int(fn.gt_inversion.sum()))
    print("FN root interval (union_fits_one_chord):",
          fn[fn.category == "union_fits_one_chord"].root_interval.value_counts().to_dict())
    print("\n== by LH texture of the bar ==")
    rows = []
    for tx, g in tex.groupby("texture"):
        d, gt = g[g.side == "det"], g[g.side == "gt"]
        p = d.hit.mean() if len(d) else np.nan
        r = gt.hit.mean() if len(gt) else np.nan
        rows.append({"texture": tx, "n_det": len(d), "n_gt": len(gt), "precision": p,
                     "recall": r, "f1": 2 * p * r / (p + r) if p + r else np.nan})
    print(pd.DataFrame(rows).round(3).to_string(index=False))


# --------------------------------------------------------------------------- pedal part


def lifts_and_presses(pedal: np.ndarray, thr: float) -> tuple[np.ndarray, np.ndarray]:
    p = pedal[pedal["number"] == 64]
    p = p[np.argsort(p["time_sec"], kind="stable")]
    down = p["value"].astype(float) >= thr
    t = p["time_sec"].astype(float)
    ch = np.nonzero(np.diff(down.astype(int)))[0] + 1
    return t[ch][~down[ch]], t[ch][down[ch]]


def _pedal_down_at(pedal: np.ndarray, thr: float, t: np.ndarray) -> np.ndarray:
    p = pedal[pedal["number"] == 64]
    p = p[np.argsort(p["time_sec"], kind="stable")]
    k = np.searchsorted(p["time_sec"], t, side="right") - 1
    return np.where(k >= 0, p["value"][np.maximum(k, 0)] >= thr, False)


def _offsets(times: np.ndarray, per: np.ndarray, lifts: np.ndarray, span: float = 1.0
             ) -> np.ndarray:
    """Nearest lift offset in beats within +-span beats (NaN when none)."""
    out = np.full(len(times), np.nan)
    for i, (t, p) in enumerate(zip(times, per, strict=True)):
        d = (lifts - t) / p
        d = d[np.abs(d) <= span]
        if len(d):
            out[i] = d[np.argmin(np.abs(d))]
    return out


def pedal_part(aps) -> None:
    from pianolens.data import vienna4x22
    from pianolens.features.control import ControlConfig, harmony_changes, pedal_blur
    from pianolens.features.tempo import tempo_model

    rows, thr_rows, win_rows = [], [], []
    ctrl_rng = np.random.default_rng(0)
    for ap in aps:
        stem = ap.score.score_id.split(":")[1]
        curve = tempo_model(ap)
        lab = label_table(stem, ap.score)
        gt = gt_changes(lab, "root")
        det = harmony_changes(ap.score)
        _pedal_rows(ap, curve, "batik", stem, gt["beat"].to_numpy(float), lab, rows, "gt_root")
        _pedal_rows(ap, curve, "batik", stem, det["beat"].to_numpy(float), lab, rows, "detected")
        # control: score onsets at least 1 beat from any label boundary
        lb = lab["beat"].to_numpy(float)
        ob = np.unique(ap.score.notes["onset_beat"].astype(float))
        far = ob[np.min(np.abs(ob[:, None] - lb[None, :]), axis=1) >= 1.0]
        if len(far):
            far = ctrl_rng.choice(far, size=min(len(far), len(gt)), replace=False)
            _pedal_rows(ap, curve, "batik", stem, np.sort(far), lab, rows, "control_no_label")
        g = gt[["beat"]].copy()
        for thr in (16, 32, 48, 64, 80, 96, 112):
            _, s = pedal_blur(ap, curve, ControlConfig(pedal_threshold=thr), changes=g)
            thr_rows.append({"source": "batik", "stem": stem, "thr": thr,
                             "blur_fraction": s["pedal_blur_fraction"],
                             "down_fraction": s["pedal_down_fraction"],
                             "n": s["n_harmony_changes_used"]})  # fmt: skip
        _window_sweep(ap, curve, g, "batik", stem, win_rows)
    # Vienna 4x22 Mozart K.331 theme: map the DCML labels of the Batik K.331/1 score by
    # (bar of the theme, offset in the bar); Vienna Chopin Op.10/3: detected changes only.
    k331 = next(a for a in aps if a.score.score_id.endswith("kv331_1"))
    k331_lab = label_table("kv331_1", k331.score)
    q_of_b = pd.Series(k331.score.notes["onset_quarter"],
                       index=k331.score.notes["onset_beat"]).groupby(level=0).first()
    from pianolens.features.correctness import measure_rows

    lq = q_of_b.reindex(k331_lab["beat"]).to_numpy(float)
    mrow = measure_rows(k331.score.measures, lq)
    k331_lab["bar"] = k331.score.measures["number"][mrow].astype(int)
    k331_lab["offset_q"] = lq - k331.score.measures["start_quarter"][mrow]
    theme = k331_lab[k331_lab["bar"] <= 18].drop_duplicates(["bar", "offset_q"])
    for ap in vienna4x22.iter_aligned():
        sid = ap.score.score_id
        if "K331" not in sid and "op10_no3" not in sid:
            continue
        curve = tempo_model(ap)
        pid = ap.performance.performance_id
        if "K331" in sid:
            ms = ap.score.measures
            vb = _vienna_k331_bars(len(ms))
            sn = ap.score.notes
            bq = pd.Series(sn["onset_beat"], index=sn["onset_quarter"]).groupby(level=0).first()
            beats = []
            for r, bar in enumerate(vb):
                for off in theme.loc[theme["bar"] == bar, "offset_q"]:
                    q = float(ms["start_quarter"][r] + off)
                    if q in bq.index:
                        beats.append(float(bq[q]))
            lab_v = pd.DataFrame({"beat": beats})
            roots = []
            for bar in vb:
                roots += theme.loc[theme["bar"] == bar, "root_pc"].tolist()
            vl = pd.DataFrame({"beat": beats, "root_pc": roots[:len(beats)]}).sort_values(
                "beat")
            keep = vl["root_pc"].ne(vl["root_pc"].shift())
            keep.iloc[0] = False
            ch = vl.loc[keep, "beat"].to_numpy(float)
            _pedal_rows(ap, curve, "vienna_k331", pid, ch, lab_v, rows, "gt_root")
            g = pd.DataFrame({"beat": ch})
            for thr in (16, 32, 48, 64, 80, 96, 112):
                _, s = pedal_blur(ap, curve, ControlConfig(pedal_threshold=thr), changes=g)
                thr_rows.append({"source": "vienna_k331", "stem": pid, "thr": thr,
                                 "blur_fraction": s["pedal_blur_fraction"],
                                 "down_fraction": s["pedal_down_fraction"],
                                 "n": s["n_harmony_changes_used"]})  # fmt: skip
            _window_sweep(ap, curve, g, "vienna_k331", pid, win_rows)
        else:
            ch = harmony_changes(ap.score)["beat"].to_numpy(float)
            _pedal_rows(ap, curve, "vienna_op10_3", pid, ch, None, rows, "detected")
    OUT.mkdir(parents=True, exist_ok=True)
    lifts = pd.DataFrame(rows)
    lifts.to_csv(OUT / "pedal_lifts.csv", index=False)
    thr = pd.DataFrame(thr_rows)
    thr.to_csv(OUT / "pedal_threshold.csv", index=False)
    win = pd.DataFrame(win_rows)
    win.to_csv(OUT / "pedal_window.csv", index=False)
    _report_pedal(lifts, thr)
    print("\n== blur fraction on GT root changes vs lift window [t - before, t + after] "
          "(beats; threshold 64; mean over movements / performances) ==")
    print(win.groupby(["source", "before", "after"])["blur_fraction"].mean().unstack(
        ["source", "before"]).round(3).to_string())


def _window_sweep(ap, curve, changes, source, stem, out) -> None:
    from pianolens.features.control import ControlConfig, pedal_blur

    for before in (0.0, 0.125, 0.25, 0.5):
        for after in (0.125, 0.25, 0.5, 1.0):
            cfg = ControlConfig(pedal_before_beats=before, pedal_after_beats=after)
            _, s = pedal_blur(ap, curve, cfg, changes=changes)
            out.append({"source": source, "stem": stem, "before": before, "after": after,
                        "blur_fraction": s["pedal_blur_fraction"]})


def _vienna_k331_bars(n: int) -> list[int]:
    """Unfolded Vienna K.331 bar rows -> theme bar numbers (1-8, 1-8, 9-18, 9-18)."""
    seq = list(range(1, 9)) * 2 + list(range(9, 19)) * 2
    if n != len(seq):
        raise ValueError(f"unexpected Vienna K.331 length {n}")
    return seq


def _pedal_rows(ap, curve, source, stem, beats, lab, rows, what) -> None:
    if not len(beats):
        return
    ped = ap.performance.pedal
    if ped is None or not len(ped) or not (ped["number"] == 64).any():
        return
    pos = curve.positions
    ptime = dict(zip(pos["beat"].round(6), np.where(pos["gross_outlier"], np.nan,
                                                    pos["time_sec"]), strict=True))
    tc = np.array([ptime.get(round(float(x), 6), np.nan) for x in beats])
    tc = np.where(np.isfinite(tc), tc, curve.time_map.time(beats))
    per = curve.time_map.period(beats)
    lifts, presses = lifts_and_presses(ped, 64)
    down_before = _pedal_down_at(ped, 64, tc - 1.0 * per)
    off = _offsets(tc, per, lifts)
    poff = _offsets(tc, per, presses)
    for i in range(len(beats)):
        rows.append({"source": source, "stem": stem, "what": what, "beat": beats[i],
                     "period_sec": per[i], "down_1beat_before": bool(down_before[i]),
                     "lift_offset_beats": off[i], "press_offset_beats": poff[i]})  # fmt: skip


def _report_pedal(lifts: pd.DataFrame, thr: pd.DataFrame) -> None:
    print("\n== pedal lifts relative to changes (threshold 64; nearest lift within +-1 beat) ==")
    out = []
    for (src, what), g in lifts.groupby(["source", "what"]):
        d = g[g.down_1beat_before]
        o = d["lift_offset_beats"].dropna()
        inwin = ((o >= -0.25) & (o <= 0.5)).sum()
        out.append({"source": src, "what": what, "n": len(g), "n_down_before": len(d),
                    "lift_within_1beat": len(o) / max(len(d), 1),
                    "in_default_window": inwin / max(len(d), 1),
                    "q10": o.quantile(0.1), "q25": o.quantile(0.25), "median": o.median(),
                    "q75": o.quantile(0.75), "q90": o.quantile(0.9),
                    "median_sec": (o * d.loc[o.index, "period_sec"]).median()})  # fmt: skip
    print(pd.DataFrame(out).round(3).to_string(index=False))
    g = lifts[(lifts.what == "gt_root") & lifts.down_1beat_before]
    o = g["lift_offset_beats"].dropna()
    print("\nhistogram of nearest-lift offset (beats), GT root changes, pedal down before:")
    for src, gg in g.groupby("source"):
        oo = gg["lift_offset_beats"].dropna()
        h, e = np.histogram(oo, bins=np.arange(-1.0, 1.01, 0.125))
        print(src, dict(zip(np.round(e[:-1], 3), h, strict=True)))
    print("\nwindow sweep (share of GT root changes with pedal down 1 beat before that have a "
          "lift in [-a, +b]):")
    for src, gg in g.groupby("source"):
        oo = gg["lift_offset_beats"]
        res = {}
        for a in (0.0, 0.125, 0.25, 0.5):
            for b in (0.25, 0.5, 0.75, 1.0):
                res[f"[-{a},+{b}]"] = round(float(((oo >= -a) & (oo <= b)).mean()), 3)
        print(src, res)
    c = lifts[(lifts.what == "control_no_label") & lifts.down_1beat_before]["lift_offset_beats"]
    print("control (onsets >= 1 beat from any label), share with a lift in [-0.25, 0.5]:",
          round(float(((c >= -0.25) & (c <= 0.5)).mean()), 3), "n", len(c))
    del o
    print("\n== blur fraction on GT root changes vs CC64 threshold (median over movements / "
          "performances) ==")
    print(thr.groupby(["source", "thr"])[["blur_fraction", "down_fraction"]].median()
          .unstack(0).round(3))  # fmt: skip


def cc64_value_hist(aps) -> None:
    vals = np.concatenate([a.performance.pedal["value"][a.performance.pedal["number"] == 64]
                           for a in aps])  # fmt: skip
    h, e = np.histogram(vals, bins=[0, 16, 32, 48, 64, 80, 96, 112, 128])
    print("\nBatik CC64 event values, histogram:", dict(zip(e[:-1].astype(int), h, strict=True)))


def main() -> None:
    warnings.filterwarnings("ignore")
    a = argparse.ArgumentParser()
    a.add_argument("--part", choices=("harmony", "pedal", "all"), default="all")
    a.add_argument("--chosen", default=None,
                   help="rule variant to analyse in detail: templates,bass,min_weight,unit,window")
    args = a.parse_args()
    aps = load_movements()
    print(f"Batik movements: {len(aps)}")
    chosen = tuple(x if i in (0, 3) else (x == "True" if i == 1 else float(x))
                   for i, x in enumerate(args.chosen.split(","))) if args.chosen else None
    if args.part in ("harmony", "all"):
        harmony_part(aps, chosen)
    if args.part in ("pedal", "all"):
        cc64_value_hist(aps)
        pedal_part(aps)


if __name__ == "__main__":
    main()
