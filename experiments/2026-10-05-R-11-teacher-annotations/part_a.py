"""R-11 part (a): expert consensus at teacher-marked bars vs shuffled (transplanted) positions.

Implements README "Method, (a)" and the frozen row rules in
data/interim/tonebase_annotations/encoder_A/operationalisation_A.csv. Imported by run.py.
"""

from __future__ import annotations

import logging
import os
import re
import tempfile
import warnings
import zipfile
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

PIECES = {
    "NOC": "pianocore:Chopin,_Frédéric/Nocturnes,_Op.9/Nocturne_No.2_in_E_flat_major,_Andante",
    "WAL": 'pianocore:Chopin,_Frédéric/Waltzes,_Op.64/Waltz_No.6_in_D_flat_major,_"Minute_Waltz",'
           "_Molto_vivace",
    "ETU": "chopin_op10_no4",
}  # fmt: skip
EXCLUDED_REGIONS = {"NOC": set(range(33, 39)), "WAL": set(range(85, 89)), "ETU": set()}
NAMES = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]
MIN_PERF, MIN_PERF_SENSOR, MIN_NULL = 50, 10, 10
EPS = 1e-3


def midi_of(name: str) -> int:
    m = re.fullmatch(r"([A-G][b#]?)(-?\d)", name)
    assert m, name
    return NAMES.index(m.group(1)) + 12 * (int(m.group(2)) + 1)


# ----------------------------------------------------------------------------- piece data
@dataclass
class Piece:
    tag: str
    S: pd.DataFrame  # score notes: id m q oq pitch dur_q grace staff ts_b ts_t pos
    meas: pd.DataFrame  # number start end
    pos_oq: np.ndarray  # onset (quarters) of each position (non-grace onsets)
    perf: pd.DataFrame  # performance_id provenance
    V: np.ndarray  # perf x note velocity
    D: np.ndarray  # perf x note key-down seconds
    PO: np.ndarray  # perf x position onset seconds (median of matched notes)
    T: np.ndarray  # perf x note onset seconds
    staff_log: dict = field(default_factory=dict)


def _xml_staffs(tag: str, score) -> tuple[np.ndarray, dict]:
    """Staff (1 upper, 2 lower) per refined-score note from the PianoCoRe MusicXML."""
    import partitura as pt

    from pianolens.data.pianocore import DEFAULT_ROOT, PianoCoRe

    idx = PianoCoRe().index
    xp = idx[idx["piece_id"] == PIECES[tag]].iloc[0]["score_xml_path"]
    z = zipfile.ZipFile(DEFAULT_ROOT / "PianoCoRe-1.0-raw-midi.zip")
    data = z.read("PianoCoRe/raw/" + xp)
    with tempfile.NamedTemporaryFile(suffix=os.path.splitext(xp)[1], delete=False) as f:
        f.write(data)
        fn = f.name
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        logging.disable(logging.CRITICAL)
        sc = pt.load_score(fn)
        logging.disable(logging.NOTSET)
    rows = []
    for k, part in enumerate(sc.parts):
        up = pt.score.unfold_part_maximal(part)
        na = up.note_array(include_staff=True)
        st = na["staff"] if len(np.unique(na["staff"])) > 1 else np.full(len(na), k + 1)
        rows.append(pd.DataFrame({"oq": na["onset_quarter"], "pitch": na["pitch"], "staff": st}))
    X = pd.concat(rows, ignore_index=True)
    mn = score.notes
    keys: dict = {}
    best = None
    s = set(zip(np.round(mn["onset_quarter"], 3), mn["pitch"], strict=True))
    for off in np.arange(-8, 8.01, 0.125):  # constant offset (padded upbeat)
        hit = sum((round(q + off, 3), p) in s for q, p in zip(X["oq"], X["pitch"], strict=True))
        if best is None or hit > best[1]:
            best = (off, hit)
    off = best[0]
    for q, p, s in zip(X["oq"] + off, X["pitch"], X["staff"], strict=True):
        keys.setdefault((round(q, 3), int(p)), int(s))
    staff = np.array([keys.get((round(q, 3), int(p)), 0) for q, p in
                      zip(mn["onset_quarter"], mn["pitch"], strict=True)])
    n_unmatched = int((staff == 0).sum())
    oq = np.asarray(mn["onset_quarter"], float)
    pitch = np.asarray(mn["pitch"], int)
    meas = score.note_measures()
    for i in np.where(staff == 0)[0]:
        same = np.where((np.abs(oq - oq[i]) < EPS) & (staff > 0))[0]
        if len(same) == 0:
            same = np.where((meas == meas[i]) & (staff > 0))[0]
        if len(same) == 0:
            same = np.where(staff > 0)[0]
        staff[i] = staff[same[np.argmin(np.abs(pitch[same] - pitch[i]))]]
    return staff, {"xml_offset_q": float(off), "matched": int(len(mn) - n_unmatched),
                   "unmatched_fallback": n_unmatched, "n_notes": int(len(mn))}


def load_piece(tag: str) -> Piece:
    from pianolens.data.pianocore import PianoCoRe
    from pianolens.data.pianocore_cache import load_performances, load_piece_notes

    pc = PianoCoRe()
    idx = pc.index
    score = pc.load_score(idx[idx["piece_id"] == PIECES[tag]].iloc[0])
    n = score.notes
    m = score.note_measures()
    ms = pd.DataFrame({"number": score.measures["number"], "start": score.measures["start_quarter"],
                       "end": score.measures["end_quarter"]})
    start = dict(zip(ms["number"], ms["start"], strict=True))
    staff, log = _xml_staffs(tag, score)
    S = pd.DataFrame({"id": n["id"].astype(str), "m": m, "oq": n["onset_quarter"].astype(float),
                      "pitch": n["pitch"].astype(int), "dur_q": n["duration_quarter"].astype(float),
                      "grace": n["is_grace"].astype(bool), "staff": staff,
                      "ts_b": n["ts_beats"].astype(int), "ts_t": n["ts_beat_type"].astype(int)})
    S["q"] = S["oq"] - S["m"].map(start)
    pos_oq = np.unique(np.round(S.loc[~S["grace"], "oq"].to_numpy(), 4))
    S["pos"] = np.searchsorted(pos_oq, np.round(S["oq"], 4))
    S.loc[S["grace"], "pos"] = -1
    cols = ["performance_id", "s_id", "p_onset_sec", "p_duration_sec", "p_velocity"]
    N = load_piece_notes(PIECES[tag], columns=cols, labels=("match",))
    perfs = load_performances()
    perfs = perfs[perfs["piece_id"] == PIECES[tag]][["performance_id", "provenance"]]
    perfs = perfs.reset_index(drop=True)
    pi = {p: i for i, p in enumerate(perfs["performance_id"])}
    ni = {s: i for i, s in enumerate(S["id"])}
    N = N[N["s_id"].isin(ni) & N["performance_id"].isin(pi)]
    r = N["performance_id"].map(pi).to_numpy()
    c = N["s_id"].map(ni).to_numpy()
    shape = (len(perfs), len(S))
    V = np.full(shape, np.nan, np.float32)
    D = np.full(shape, np.nan, np.float32)
    T = np.full(shape, np.nan, np.float64)
    V[r, c] = N["p_velocity"].to_numpy(float)
    D[r, c] = N["p_duration_sec"].to_numpy(float)
    T[r, c] = N["p_onset_sec"].to_numpy(float)
    PO = np.full((len(perfs), len(pos_oq)), np.nan)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        for k, g in S[S["pos"] >= 0].groupby("pos").groups.items():
            PO[:, k] = np.nanmedian(T[:, list(g)], axis=1)
    log["n_perf"] = len(perfs)
    log["provenance"] = perfs["provenance"].value_counts().to_dict()
    return Piece(tag, S, ms, pos_oq, perfs, V, D, PO, T, log)


# ----------------------------------------------------------------------------- helpers
def beat_len(ts_b: int, ts_t: int) -> float:
    return 1.5 if ts_t == 8 and ts_b % 3 == 0 else 4.0 / ts_t


def find_notes(P: Piece, m: int, q: float, staff: int | None = None) -> pd.DataFrame:
    S = P.S
    sel = (S["m"] == m) & (np.abs(S["q"] - q) < EPS) & ~S["grace"]
    if staff is not None:
        sel &= S["staff"] == staff
    return S[sel]


def ranked(df: pd.DataFrame, staff: int) -> pd.DataFrame:
    """Order notes of one staff at one onset: from the top for staff 1, the bottom for 2."""
    return df.sort_values("pitch", ascending=(staff != 1))


@dataclass
class TargetSpec:
    kind: str  # note | chord | chord_all
    m: int
    q: float
    staff: int | None = None
    rank: int = 0


def parse_targets(P: Piece, targets: str) -> tuple[list[TargetSpec], list[str]]:
    specs, notes = [], []
    for t in [t for t in targets.split(";") if t]:
        hand, rest = t.split(":", 1)
        what, where = rest.split("@")
        m, q = where.split(":")
        m, q = int(m), float(q)
        if what == "chord":
            if hand == "RH+LH":
                specs.append(TargetSpec("chord_all", m, q))
            else:
                specs.append(TargetSpec("chord", m, q, 1 if hand == "RH" else 2))
            continue
        cand = find_notes(P, m, q)
        hit = cand[cand["pitch"] == midi_of(what)]
        if hit.empty:
            notes.append(f"{t}: not found")
            continue
        st = int(hit.iloc[0]["staff"])
        if (hand == "RH") != (st == 1):
            notes.append(f"{t}: XML staff {st}")
        order = ranked(cand[cand["staff"] == st], st)
        rank = int(np.where(order["id"].to_numpy() == hit.iloc[0]["id"])[0][0])
        specs.append(TargetSpec("note", m, q, st, rank))
    return specs, notes


def realise(P: Piece, specs: list[TargetSpec], d: int) -> tuple[list[int], int]:
    """Indices of transplanted target notes at measure shift d; also how many specs hit."""
    out, hit = [], 0
    for s in specs:
        if s.kind == "chord_all":
            df = find_notes(P, s.m + d, s.q)
        elif s.kind == "chord":
            df = find_notes(P, s.m + d, s.q, s.staff)
        else:
            df = find_notes(P, s.m + d, s.q, s.staff)
            df = ranked(df, s.staff)
            df = df.iloc[[s.rank]] if len(df) > s.rank else df.iloc[[]]
        if len(df):
            hit += 1
            out += list(df.index)
    return sorted(set(out)), hit


# ----------------------------------------------------------------------------- statistics
def vel_contrast(P: Piece, T: list[int], R: list[int], sign: float = 1.0,
                 groups: list[list[int]] | None = None) -> np.ndarray:
    """Per performance mean v(T) - mean v(R); NaN unless >= half of T and >= 1 of R matched."""
    def one(t, r):
        vt, vr = P.V[:, t], P.V[:, r]
        ok = (np.isfinite(vt).sum(1) >= np.ceil(len(t) / 2)) & (np.isfinite(vr).sum(1) >= 1)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            e = np.nanmean(vt, 1) - np.nanmean(vr, 1)
        return np.where(ok, e, np.nan)
    if not T or not R:
        return np.full(len(P.perf), np.nan)
    if groups:
        es = [one(*g) for g in groups if g[0] and g[1]]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            return sign * np.nanmean(np.vstack(es), 0) if es else np.full(len(P.perf), np.nan)
    return sign * one(T, R)


def slope(P: Piece, T: list[int]) -> np.ndarray:
    x = P.S.loc[T, "oq"].to_numpy()
    out = np.full(len(P.perf), np.nan)
    v = P.V[:, T].astype(float)
    for i in range(len(P.perf)):
        ok = np.isfinite(v[i])
        if ok.sum() >= max(2, int(np.ceil(len(T) / 2))) and np.ptp(x[ok]) > 0:
            out[i] = np.polyfit(x[ok], v[i, ok], 1)[0]
    return out


def log_ioi_norm(P: Piece, k: int) -> np.ndarray:
    """log(IOI from position k to k+1 / notated) per performance."""
    if k < 0 or k + 1 >= len(P.pos_oq):
        return np.full(len(P.perf), np.nan)
    dt = P.PO[:, k + 1] - P.PO[:, k]
    nq = P.pos_oq[k + 1] - P.pos_oq[k]
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(dt > 0, np.log(dt / nq), np.nan)


def positions_in(P: Piece, measures: set[int]) -> list[int]:
    S = P.S
    return sorted(set(S.loc[S["m"].isin(measures) & (S["pos"] >= 0), "pos"].astype(int)))


def lengthen(P: Piece, tpos: list[int], into: bool = False) -> np.ndarray:
    """Mean over target positions of log(IOI/notated) minus the median of the other positions
    within +-1 measure. ``into``: the IOI arriving at the target (from the previous position)."""
    if not tpos:
        return np.full(len(P.perf), np.nan)
    S = P.S
    pos_m = S[S["pos"] >= 0].groupby("pos")["m"].first()
    ms = set()
    for k in tpos:
        mm = int(pos_m[k])
        ms |= {mm - 1, mm, mm + 1}
    ks = [k - 1 if into else k for k in tpos]
    ref = [k for k in positions_in(P, ms) if k not in ks and k not in tpos]
    if into:
        ref = [k - 1 for k in ref if k - 1 not in ks]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        tv = np.nanmean(np.vstack([log_ioi_norm(P, k) for k in ks]), 0)
        rv = np.nanmedian(np.vstack([log_ioi_norm(P, k) for k in ref]), 0) if ref else np.nan
    return tv - rv


def spq_measures(P: Piece, measures: list[int]) -> np.ndarray:
    """Seconds per notated quarter over a contiguous block of measures."""
    ms = P.meas.set_index("number")
    a, b = min(measures), max(measures)
    if a not in ms.index or b not in ms.index:
        return np.full(len(P.perf), np.nan)
    qa, qb = ms.loc[a, "start"], ms.loc[b, "end"]
    ka = np.searchsorted(P.pos_oq, qa - EPS)
    kb = np.searchsorted(P.pos_oq, qb - EPS)
    if ka >= len(P.pos_oq) or kb >= len(P.pos_oq) or abs(P.pos_oq[ka] - qa) > EPS \
            or abs(P.pos_oq[kb] - qb) > EPS:
        return np.full(len(P.perf), np.nan)
    dt = P.PO[:, kb] - P.PO[:, ka]
    with np.errstate(invalid="ignore"):
        return np.where(dt > 0, dt / (qb - qa), np.nan)


def local_spq(P: Piece, m: int) -> np.ndarray:
    ks = positions_in(P, {m - 1, m, m + 1})
    vals = []
    for k in ks:
        if k + 1 < len(P.pos_oq):
            dt = P.PO[:, k + 1] - P.PO[:, k]
            with np.errstate(invalid="ignore"):
                vals.append(np.where(dt > 0, dt / (P.pos_oq[k + 1] - P.pos_oq[k]), np.nan))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        return np.nanmedian(np.vstack(vals), 0) if vals else np.full(len(P.perf), np.nan)


def dur_ratio(P: Piece, T: list[int]) -> np.ndarray:
    S = P.S
    rs = []
    for t in T:
        sp = local_spq(P, int(S.loc[t, "m"]))
        rs.append(P.D[:, t] / (S.loc[t, "dur_q"] * sp))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        r = np.vstack(rs)
        ok = np.isfinite(r).sum(0) >= np.ceil(len(T) / 2)
        return np.where(ok, np.nanmedian(r, 0), np.nan)


def share(e: np.ndarray, kind: str = "sign") -> tuple[float, int]:
    e = e[np.isfinite(e)]
    if len(e) == 0:
        return float("nan"), 0
    if kind == "short":
        return float(np.mean(e < 0.75)), len(e)
    if kind == "long":
        return float(np.mean(e >= 0.90)), len(e)
    return float((np.sum(e > 0) + 0.5 * np.sum(e == 0)) / len(e)), len(e)


# ----------------------------------------------------------------------------- rows
@dataclass
class Row:
    ann_id: str
    tag: str
    set: str
    direction: str
    reference: str
    quantity: str
    category: str
    restates: str
    window: set[int]  # anchor measures (shifted by d for null positions)
    fn: object  # fn(P, d) -> (E vector, n_hit_ok: bool) or None
    kind: str = "sign"  # sign | short | long | descriptive
    sensor_only: bool = False
    null_ok: bool = True
    notes: list[str] = field(default_factory=list)


def clusters(ms: list[int], gap: int = 4) -> list[set[int]]:
    out: list[set[int]] = []
    for m in sorted(set(ms)):
        if out and m - max(out[-1]) <= gap:
            out[-1].add(m)
        else:
            out.append({m})
    return out


def ref_notes(P: Piece, T: list[int], code: str) -> list[int]:
    S = P.S
    ng = S[~S["grace"]]
    Tset = set(T)
    if code == "same_onset":
        oqs = set(np.round(S.loc[T, "oq"], 4))
        R = ng[np.round(ng["oq"], 4).isin(oqs)].index
    elif code == "same_beat_same_hand":
        R = []
        for t in T:
            r = S.loc[t]
            b = beat_len(int(r["ts_b"]), int(r["ts_t"]))
            sel = ng[(ng["staff"] == r["staff"]) & (ng["m"] == r["m"])
                     & (np.floor(ng["q"] / b + EPS) == np.floor(r["q"] / b + EPS))]
            R += list(sel.index)
    elif code == "same_bar":
        R = ng[ng["staff"].isin(set(S.loc[T, "staff"])) & ng["m"].isin(set(S.loc[T, "m"]))].index
    elif code == "neighbour_bars":
        R = []
        for t in T:
            r = S.loc[t]
            sel = ng[(ng["staff"] == r["staff"]) & ng["m"].isin({r["m"] - 1, r["m"] + 1})
                     & (np.abs(ng["q"] - r["q"]) < EPS)]
            R += list(sel.index)
    else:
        raise ValueError(code)
    return sorted(set(R) - Tset)


def generic_velocity(specs: list[TargetSpec], code: str, sign: float):
    def fn(P: Piece, d: int):
        groups = []
        for cl in clusters([s.m for s in specs]):
            sp = [s for s in specs if s.m in cl]
            T, hit = realise(P, sp, d)
            if hit < np.ceil(len(sp) / 2):
                return None
            R = ref_notes(P, T, code)
            if not R:
                return None
            groups.append((T, R))
        return vel_contrast(P, groups[0][0], groups[0][1], sign, groups=groups)
    return fn


def build_rows(P: Piece, A: pd.DataFrame, ops_df: pd.DataFrame) -> list[Row]:
    rows = []
    S = P.S
    tag = P.tag
    ops = ops_df.set_index("ann_id")
    for _, a in A.iterrows():
        if a["ann_id"] not in ops.index:
            continue
        o = ops.loc[a["ann_id"]]
        if o["set"] == "excluded":
            continue
        aid, dr, ref = a["ann_id"], a["direction"], a["reference"]
        specs, pnotes = parse_targets(P, a["targets"]) if a["targets"] else ([], [])
        pcm = {int(x) for x in a["pc_measures"].split(";") if x}
        base = dict(ann_id=aid, tag=tag, set=o["set"], direction=dr, reference=ref,
                    quantity=a["quantity"], category=a["category"], restates=a["restates_print"],
                    notes=pnotes)
        sign = -1.0 if dr.startswith("SOFTER") else 1.0
        fn, window, kind, sensor, null_ok = None, set(), "sign", False, True
        spec_ms = {s.m for s in specs}

        # ---- row-specific frozen rules
        if aid == "NOC-A-015":
            window = spec_ms

            def fn(P, d, specs=specs):
                T, hit = realise(P, specs, d)
                return slope(P, T) if hit >= np.ceil(len(specs) / 2) else None
        elif aid == "NOC-A-021":
            qs = [s.q for s in specs]
            window = {13}

            def fn(P, d, qs=qs):
                T, R, hit = [], [], 0
                for q in qs:
                    df = find_notes(P, 13 + d, q).sort_values("pitch")
                    if len(df) >= 3:
                        hit += 1
                        T += list(df.index[1:-1])
                        R += [df.index[0], df.index[-1]]
                return vel_contrast(P, T, R) if hit >= np.ceil(len(qs) / 2) else None
        elif aid in ("NOC-A-023", "NOC-A-031"):
            m1, m0 = (14, 6) if aid == "NOC-A-023" else (22, 14)
            window = {m1, m0}

            def contrast(P, m):
                df = S[(S["m"] == m) & (S["staff"] == 2) & ~S["grace"]]
                lo, hi = [], []
                for _, g in df.groupby(np.round(df["oq"], 4)):
                    g = g.sort_values("pitch")
                    lo.append(g.index[0])
                    hi += list(g.index[1:])
                return vel_contrast(P, hi, lo) if lo and hi else None

            def fn(P, d, m1=m1, m0=m0, contrast=contrast):
                a1, a0 = contrast(P, m1 + d), contrast(P, m0 + d)
                return None if a1 is None or a0 is None else a1 - a0
        elif aid == "NOC-A-037":
            window = {30}

            def fn(P, d, specs=specs):
                T, hit = realise(P, specs, d)
                R = list(S[(S["m"] == 30 + d) & (S["staff"] == 2) & (S["q"] >= 3 - EPS)
                           & ~S["grace"]].index)
                R = [r for r in R if r not in T]
                return vel_contrast(P, T, R) if hit >= np.ceil(len(specs) / 2) and R else None
        elif aid == "NOC-A-040":
            window = {32}

            def fn(P, d):
                df = S[(S["m"] == 32 + d) & (S["staff"] == 1) & ~S["grace"]]
                T, R = [], []
                for _, g in df.groupby(np.round(df["oq"], 4)):
                    if len(g) >= 2:
                        g = g.sort_values("pitch")
                        T.append(g.index[-1])
                        R += list(g.index[:-1])
                return vel_contrast(P, T, R) if T else None
        elif aid == "NOC-A-041":
            window, null_ok = {34, 35}, False

            def fn(P, d):
                df = S[S["m"].isin({34 + d, 35 + d}) & ~S["grace"]].sort_values("oq")
                if len(df) < 48:
                    return None
                firsts = list(df.index[::4][:12])
                T = [firsts[i] for i in (0, 3, 6, 9)]
                R = [f for i, f in enumerate(firsts) if i not in (0, 3, 6, 9)]
                return vel_contrast(P, T, R)
        elif aid in ("WAL-A-005", "WAL-A-050", "ETU-A-049"):
            Sx, Px = {"WAL-A-005": ((1, 4), (5, 8)), "WAL-A-050": ((89, 92), (93, 96)),
                      "ETU-A-049": ((52, 59), (2, 9))}[aid]
            window = set(range(Sx[0], Sx[1] + 1)) | set(range(Px[0], Px[1] + 1))
            faster = aid == "ETU-A-049"

            def fn(P, d, Sx=Sx, Px=Px, faster=faster):
                ls = np.log(spq_measures(P, [Sx[0] + d, Sx[1] + d]))
                lp = np.log(spq_measures(P, [Px[0] + d, Px[1] + d]))
                return (lp - ls) if faster else (ls - lp)
        elif aid in ("WAL-A-023", "WAL-A-031", "WAL-A-055"):
            window = spec_ms

            def fn(P, d, specs=specs):
                groups = []
                for cl in clusters([s.m for s in specs]):
                    sp = [s for s in specs if s.m in cl]
                    T, hit = realise(P, sp, d)
                    if hit < np.ceil(len(sp) / 2):
                        return None
                    ms = {s.m + d for s in sp}
                    R = [i for i in S[S["m"].isin(ms) & (S["staff"] == 2) & ~S["grace"]].index
                         if i not in T]
                    if not R:
                        return None
                    groups.append((T, R))
                return vel_contrast(P, groups[0][0], groups[0][1], groups=groups)
        elif aid == "WAL-A-041":
            window = {66, 67, 68}

            def fn(P, d):
                up = S[(S["staff"] == 1) & ~S["grace"]]
                tops = up.loc[up.groupby(np.round(up["oq"], 4))["pitch"].idxmax()].sort_values("oq")
                tops = tops.reset_index()
                tpos = []
                for i in range(1, len(tops)):
                    if tops.loc[i, "m"] in {66 + d, 67 + d, 68 + d} and \
                            abs(tops.loc[i, "pitch"] - tops.loc[i - 1, "pitch"]) >= 5:
                        tpos.append(int(tops.loc[i, "pos"]))
                return lengthen(P, tpos, into=True) if tpos else None
        elif aid == "WAL-A-052":
            window = {93}

            def fn(P, d):
                def low(m):
                    df = find_notes(P, m, 0.0)
                    return [df["pitch"].idxmin()] if len(df) else []
                T, R = low(93 + d), low(92 + d) + low(94 + d)
                return vel_contrast(P, T, R) if T and R else None
        elif aid == "WAL-A-053":
            window = {99, 97}

            def fn(P, d):
                def pos_of(m):
                    df = find_notes(P, m, 0.0, 1)
                    return [int(df["pos"].iloc[0])] if len(df) else []
                a1, a0 = pos_of(99 + d), pos_of(97 + d)
                return lengthen(P, a1) - lengthen(P, a0) if a1 and a0 else None
        elif aid == "WAL-A-037":
            window, kind, null_ok = {60}, "descriptive", False

            def fn(P, d):
                ks = positions_in(P, {60 + d})
                v = np.vstack([log_ioi_norm(P, k) for k in ks[:-1]]) if len(ks) > 2 else None
                return None if v is None else np.nanstd(v, 0)
        elif aid == "WAL-A-045":
            window, kind, null_ok = set(range(70, 80)), "descriptive", False

            def fn(P, d):
                g = S[S["grace"] & S["m"].isin(set(range(70 + d, 80 + d)))]
                leads = []
                for i, r in g.iterrows():
                    main = S[(~S["grace"]) & (np.abs(S["oq"] - r["oq"]) < EPS)]
                    if len(main):
                        leads.append(P.T[:, main.index].min(1) - P.T[:, i])
                if len(leads) < 3:
                    return None
                L = np.vstack(leads)
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", RuntimeWarning)
                    return np.nanstd(L, 0) / np.abs(np.nanmean(L, 0))
        elif aid == "ETU-A-014":
            window = {1, 2}

            def fn(P, d):
                T = list(S[(S["m"] == 2 + d) & (S["staff"] == 1) & (S["q"] > EPS)
                           & ~S["grace"]].index)
                R = list(S[(S["m"] == 1 + d) & (S["staff"] == 1) & (S["q"] >= 3 - EPS)
                           & ~S["grace"]].index)
                return vel_contrast(P, T, R, -1.0) if T and R else None
        elif aid == "ETU-A-021":
            window = {5}

            def fn(P, d):
                lo, hi = [], []
                for q in (0.5, 1.0, 1.5, 2.0, 2.5):
                    a1 = find_notes(P, 5 + d, q, 1)
                    b1 = find_notes(P, 5 + d, q + 0.25, 1)
                    if len(a1) and len(b1):
                        lo.append(a1["pitch"].idxmin())
                        hi.append(b1["pitch"].idxmax())
                return vel_contrast(P, hi, lo) if len(lo) >= 3 else None
        elif aid == "ETU-A-040":
            window = {34, 35}

            def fn(P, d):
                df = S[S["m"].isin({34 + d, 35 + d}) & ~S["grace"]]
                T, R = [], []
                for _, g in df.groupby(np.round(df["oq"], 4)):
                    if (g["staff"] == 1).any() and (g["staff"] == 2).any():
                        T += list(g.index[g["staff"] == 2])
                        R += list(g.index[g["staff"] == 1])
                return vel_contrast(P, T, R, -1.0) if T and R else None
        # ---- generic rules by direction
        elif dr in ("LOUDER_THAN_REF", "SOFTER_THAN_REF") and specs:
            window = spec_ms
            fn = generic_velocity(specs, ref, sign)
        elif dr == "LENGTHEN_IOI_AT" and specs:
            window = spec_ms

            def fn(P, d, specs=specs):
                T, hit = realise(P, specs, d)
                if hit < np.ceil(len(specs) / 2):
                    return None
                return lengthen(P, sorted(set(int(p) for p in S.loc[T, "pos"] if p >= 0)))
        elif dr == "SLOWER_THAN_REF" and ref == "neighbour_bars":
            window = pcm

            def fn(P, d, pcm=pcm):
                ms = sorted(m + d for m in pcm)
                lm = np.log(spq_measures(P, ms))
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", RuntimeWarning)
                    ln = np.nanmean(np.vstack([np.log(spq_measures(P, [ms[0] - 1])),
                                               np.log(spq_measures(P, [ms[-1] + 1]))]), 0)
                return lm - ln
        elif dr in ("SHORTER_DURATION", "LONGER_DURATION") and specs:
            window = spec_ms
            kind = "short" if dr.startswith("SHORTER") else "long"
            sensor = tag == "ETU"

            def fn(P, d, specs=specs):
                T, hit = realise(P, specs, d)
                return dur_ratio(P, T) if hit >= np.ceil(len(specs) / 2) else None
        else:
            base["notes"] = pnotes + [f"no implementation for {dr}/{ref}"]
            rows.append(Row(**base, window=pcm, fn=None))
            continue
        rows.append(Row(**base, window=window, fn=fn, kind=kind, sensor_only=sensor,
                        null_ok=null_ok))
    return rows


def unannotated(A: pd.DataFrame) -> set[int]:
    U: set[int] = set()
    for _, a in A[A["observable"].isin(["yes", "partly"])].iterrows():
        for col in ("pc_measures", "pc_measures_ext"):
            U |= {int(x) for x in a[col].split(";") if x}
    return U


def evaluate_row(P: Piece, row: Row, U: set[int], subset: np.ndarray | None = None) -> dict:
    out = {"ann_id": row.ann_id, "piece": row.tag, "set": row.set, "direction": row.direction,
           "category": row.category, "quantity": row.quantity, "restates_print": row.restates,
           "kind": row.kind, "sensor_only": row.sensor_only, "notes": "; ".join(row.notes)}
    if row.fn is None:
        out["status"] = "not implemented"
        return out
    mask = np.ones(len(P.perf), bool) if subset is None else subset
    if row.sensor_only:
        mask = mask & (P.perf["provenance"].to_numpy() != "transcribed")
    e0 = row.fn(P, 0)
    if e0 is None:
        out["status"] = "anchor not computable"
        return out
    e0 = np.where(mask, e0, np.nan)
    f0, n0 = share(e0, row.kind)
    out.update(f_marked=f0, n_perf=n0, median_E=float(np.nanmedian(e0)) if n0 else np.nan)
    min_perf = MIN_PERF_SENSOR if row.sensor_only or subset is not None else MIN_PERF
    if row.kind == "descriptive":
        out["status"] = "descriptive"
        return out
    if n0 < min_perf:
        out["status"] = f"too few performances ({n0})"
        return out
    if not row.null_ok:
        out["status"] = "no null (excluded region)"
        return out
    ts = P.S.groupby("m")[["ts_b", "ts_t"]].first()
    maxm = int(P.meas["number"].max())
    win = sorted(row.window)
    sig = [tuple(ts.loc[m]) if m in ts.index else None for m in win]
    fnull = []
    for d in range(-maxm, maxm + 1):
        if d == 0:
            continue
        w = [m + d for m in win]
        if min(w) < 1 or max(w) > maxm:
            continue
        if any(m in U or m in EXCLUDED_REGIONS[P.tag] for m in w):
            continue
        if any((tuple(ts.loc[m]) if m in ts.index else None) != s for m, s in zip(w, sig,
                                                                                  strict=True)):
            continue
        e = row.fn(P, d)
        if e is None:
            continue
        f, n = share(np.where(mask, e, np.nan), row.kind)
        if n == 0:
            continue
        fnull.append(f)
    fnull = np.array(fnull)
    out["n_null"] = len(fnull)
    if len(fnull) < MIN_NULL:
        out["status"] = f"too few null positions ({len(fnull)})"
        return out
    out["r"] = float((np.sum(fnull < f0) + 0.5 * np.sum(fnull == f0)) / len(fnull))
    out["f_null_median"] = float(np.median(fnull))
    out["status"] = "ok"
    return out
