"""R-11 part (b): does the report's tempo / loudness channel flag the removal of a teacher-marked
effect in the marked bars? Implements README "Method, (b)". Imported by run.py.

The report's interpretation section (``pianolens.report.build._interpretation_section``, the
per-bar tempo- and loudness-shape tiers) is run on targets built with ``target_from_notes`` from
a tier A performance's matched notes, against the PianoCoRe references without that
performance. Original, degraded and null-degraded versions go through the same code.
"""

from __future__ import annotations

import logging
import warnings

import numpy as np
import pandas as pd
import part_a as pa

ROWS_B = {  # (b) rows: channel, degradation kind
    "NOC-A-011": ("tempo", "lengthen"), "NOC-A-039": ("tempo", "lengthen"),
    "NOC-A-027": ("tempo", "slower"), "NOC-A-015": ("velocity", "flatten"),
    "WAL-A-041": ("tempo", "lengthen_into"), "WAL-A-052": ("velocity", "contrast"),
    "ETU-A-014": ("velocity", "contrast"), "NOC-A-004": ("velocity", "contrast"),
    "NOC-A-037": ("velocity", "contrast"),
    # voicing rows: loudness channel, indirect
    "WAL-A-023": ("velocity", "contrast"), "WAL-A-055": ("velocity", "contrast"),
    "ETU-A-040": ("velocity", "contrast"), "NOC-A-018": ("velocity", "contrast"),
}


def sets_for(aid: str, P: pa.Piece, A: pd.DataFrame, d: int) -> dict | None:
    """Target / reference note indices (S index) or positions for a row at shift d, following
    the same frozen rules as part (a)."""
    S = P.S
    a = A[A["ann_id"] == aid].iloc[0]
    specs, _ = pa.parse_targets(P, a["targets"]) if a["targets"] else ([], [])
    if aid in ("NOC-A-011", "NOC-A-039"):
        T, hit = pa.realise(P, specs, d)
        if hit < np.ceil(len(specs) / 2):
            return None
        return {"tpos": sorted({int(p) for p in S.loc[T, "pos"] if p >= 0}),
                "measures": {s.m + d for s in specs}}
    if aid == "NOC-A-027":
        return {"measures": {19 + d}}
    if aid == "NOC-A-015":
        T, hit = pa.realise(P, specs, d)
        return {"T": T, "measures": {s.m + d for s in specs}} \
            if hit >= np.ceil(len(specs) / 2) else None
    if aid == "WAL-A-041":
        up = S[(S["staff"] == 1) & ~S["grace"]]
        tops = up.loc[up.groupby(np.round(up["oq"], 4))["pitch"].idxmax()].sort_values("oq")
        tops = tops.reset_index()
        ms = {66 + d, 67 + d, 68 + d}
        tpos = [int(tops.loc[i, "pos"]) for i in range(1, len(tops))
                if tops.loc[i, "m"] in ms and abs(tops.loc[i, "pitch"]
                                                  - tops.loc[i - 1, "pitch"]) >= 5]
        return {"tpos": tpos, "measures": ms} if tpos else None
    if aid == "WAL-A-052":
        def low(m):
            df = pa.find_notes(P, m, 0.0)
            return [df["pitch"].idxmin()] if len(df) else []
        T, R = low(93 + d), low(92 + d) + low(94 + d)
        return {"T": T, "R": R, "measures": {93 + d}} if T and R else None
    if aid == "ETU-A-014":
        T = list(S[(S["m"] == 2 + d) & (S["staff"] == 1) & (S["q"] > pa.EPS) & ~S["grace"]].index)
        R = list(S[(S["m"] == 1 + d) & (S["staff"] == 1) & (S["q"] >= 3 - pa.EPS)
                   & ~S["grace"]].index)
        return {"T": T, "R": R, "measures": {2 + d}} if T and R else None
    if aid == "ETU-A-040":
        df = S[S["m"].isin({34 + d, 35 + d}) & ~S["grace"]]
        T, R = [], []
        for _, g in df.groupby(np.round(df["oq"], 4)):
            if (g["staff"] == 1).any() and (g["staff"] == 2).any():
                T += list(g.index[g["staff"] == 2])
                R += list(g.index[g["staff"] == 1])
        return {"T": T, "R": R, "measures": {34 + d, 35 + d}} if T and R else None
    if aid == "NOC-A-037":
        T, hit = pa.realise(P, specs, d)
        R = [r for r in S[(S["m"] == 30 + d) & (S["staff"] == 2) & (S["q"] >= 3 - pa.EPS)
                          & ~S["grace"]].index if r not in T]
        return {"T": T, "R": R, "measures": {30 + d}} \
            if hit >= np.ceil(len(specs) / 2) and R else None
    if aid in ("WAL-A-023", "WAL-A-055"):
        T, R = [], []
        for cl in pa.clusters([s.m for s in specs]):
            sp = [s for s in specs if s.m in cl]
            t, hit = pa.realise(P, sp, d)
            if hit < np.ceil(len(sp) / 2):
                return None
            ms = {s.m + d for s in sp}
            r = [i for i in S[S["m"].isin(ms) & (S["staff"] == 2) & ~S["grace"]].index
                 if i not in t]
            if not r:
                return None
            T += t
            R += r
        return {"T": T, "R": R, "measures": {s.m + d for s in specs}}
    # generic velocity rows (NOC-A-004, NOC-A-018)
    T, hit = pa.realise(P, specs, d)
    if hit < np.ceil(len(specs) / 2):
        return None
    R = pa.ref_notes(P, T, a["reference"])
    return {"T": T, "R": R, "measures": {s.m + d for s in specs}} if R else None


def degrade(kind: str, st: dict, n: pd.DataFrame, P: pa.Piece, pidx: int) -> pd.DataFrame | None:
    """Return a degraded copy of one performance's notes (columns sidx, beat, onset, vel), or
    None when the row's notes are not matched in it."""
    n = n.copy()
    S = P.S
    if kind in ("contrast", "flatten"):
        T = n["sidx"].isin(st["T"])
        if T.sum() == 0:
            return None
        if kind == "contrast":
            R = n["sidx"].isin(st["R"])
            if R.sum() == 0:
                return None
            n.loc[T, "vel"] = n.loc[R, "vel"].mean()
        else:
            n.loc[T, "vel"] = n.loc[T, "vel"].mean()
        return n
    pos_of = S["pos"].to_dict()
    n["pos"] = n["sidx"].map(pos_of)
    if kind in ("lengthen", "lengthen_into"):
        into = kind == "lengthen_into"
        # local reference log(IOI/notated) exactly as in (a)
        ref = []
        tpos = st["tpos"]
        ks = [k - 1 if into else k for k in tpos]
        pos_m = S[S["pos"] >= 0].groupby("pos")["m"].first()
        ms = set()
        for k in tpos:
            mm = int(pos_m[k])
            ms |= {mm - 1, mm, mm + 1}
        refp = [k for k in pa.positions_in(P, ms) if k not in ks and k not in tpos]
        if into:
            refp = [k - 1 for k in refp if k - 1 not in ks]
        po = P.PO[pidx]
        for k in refp:
            if 0 <= k < len(P.pos_oq) - 1 and np.isfinite(po[k]) and np.isfinite(po[k + 1]) \
                    and po[k + 1] > po[k]:
                ref.append(np.log((po[k + 1] - po[k]) / (P.pos_oq[k + 1] - P.pos_oq[k])))
        if not ref:
            return None
        lr = float(np.median(ref))
        changed = False
        for k in sorted(ks, reverse=True):
            if not (0 <= k < len(P.pos_oq) - 1):
                continue
            cur = n.loc[n["pos"] == k, "onset"].median()
            nxt = n.loc[n["pos"] == k + 1, "onset"].median()
            if not (np.isfinite(cur) and np.isfinite(nxt)):
                continue
            new = np.exp(lr) * (P.pos_oq[k + 1] - P.pos_oq[k])
            if nxt - cur > new:
                n.loc[n["pos"] >= k + 1, "onset"] -= (nxt - cur) - new
                changed = True
        return n if changed else n  # unchanged when there was no lengthening to remove
    if kind == "slower":
        m = min(st["measures"])
        ms = P.meas.set_index("number")
        if m - 1 not in ms.index or m + 1 not in ms.index:
            return None
        sp = {k: pa.spq_measures(P, [k])[pidx] for k in (m - 1, m, m + 1)}
        if not all(np.isfinite(v) and v > 0 for v in sp.values()):
            return None
        ratio = ((sp[m - 1] + sp[m + 1]) / 2) / sp[m]
        a, b = ms.loc[m, "start"], ms.loc[m, "end"]
        oq = n["sidx"].map(S["oq"])
        t0 = n.loc[np.abs(oq - a) < pa.EPS, "onset"].median()
        if not np.isfinite(t0):
            return None
        block = (oq >= a - pa.EPS) & (oq < b - pa.EPS)
        after = oq >= b - pa.EPS
        dur = sp[m] * (b - a)
        n.loc[block, "onset"] = t0 + (n.loc[block, "onset"] - t0) * ratio
        n.loc[after, "onset"] += dur * (ratio - 1)
        return n
    raise ValueError(kind)


def target_on_grid(pid, prov, beats, onsets, vels, refs, icfg):
    """``target_from_notes`` on the reference grid (a performance whose matched notes do not
    span the whole score would otherwise get a shorter grid, which ``interpret`` rejects
    without a beat map). Same arithmetic: ``beat_grid_curves`` + ``_smooth_velocity_rows``."""
    from pianolens.features.interpretation import (
        TargetCurves,
        _smooth_velocity_rows,
        beat_grid_curves,
    )

    c = beat_grid_curves(beats, onsets, vels, refs.grid, refs.pos_grid, refs.beats_per_bar,
                         icfg.tempo)
    return TargetCurves(
        performance_id=str(pid), provenance=str(prov), grid=refs.grid,
        bar_starts=refs.bar_starts, bar_numbers=np.arange(1, len(refs.bar_starts) + 1),
        tempo=c["T"], velocity=c["V"],
        velocity_smooth=_smooth_velocity_rows(c["V"], icfg.velocity_cutoff_bars
                                              * refs.beats_per_bar)[0],
        pos_grid=refs.pos_grid, timing=c["R"], tempo_bpm=c["tempo_bpm"], score_notes=None,
        source_id="")


def run_b(tags=("NOC", "WAL", "ETU"), K: int = 20, seed: int = 20261005, a_rows=None,
          log=print) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    warnings.filterwarnings("ignore")
    logging.disable(logging.WARNING)
    from run import INTERIM, load_rows

    from pianolens.data.pianocore_cache import load_piece_notes
    from pianolens.features.interpretation import load_pianocore_references
    from pianolens.report.build import ReportConfig, ReportInputs, _interpretation_section

    cfg = ReportConfig(shaping=False)
    rng = np.random.default_rng(seed)
    out, origin_bars, meta = [], [], {}
    for tag in tags:
        P = pa.load_piece(tag)
        A = load_rows("A", tag)
        ops_df = pd.read_csv(INTERIM / "encoder_A" / "operationalisation_A.csv",
                             dtype=str).fillna("")
        U = pa.unannotated(A)
        ar = a_rows[a_rows["piece"] == tag]
        sel = ar[(ar["ann_id"].isin(ROWS_B)) & (ar["set"] == "primary") & (ar["status"] == "ok")
                 & (ar["f_marked"] > 0.5)]
        rows = list(sel["ann_id"])
        if not rows:
            continue
        refs = load_pianocore_references(pa.PIECES[tag], config=cfg.interpretation)
        nb = len(refs.bar_starts)
        N = load_piece_notes(pa.PIECES[tag], columns=["performance_id", "s_id", "s_onset_beat",
                                                      "s_is_grace", "p_onset_sec", "p_velocity",
                                                      "s_onset_quarter"],
                             labels=("match",))
        # PianoCoRe measure -> report bar index, by start beat (empty measures have no bar)
        u = N[["s_onset_quarter", "s_onset_beat"]].drop_duplicates()
        fac, off = np.polyfit(u["s_onset_quarter"].astype(float), u["s_onset_beat"].astype(float),
                              1)
        bar_of = {}
        for _, mr in P.meas.iterrows():
            b0 = fac * mr["start"] + off
            k = np.flatnonzero(np.isclose(refs.bar_starts, b0, atol=1e-3))
            if len(k):
                bar_of[int(mr["number"])] = int(k[0])
        N = N[N["s_is_grace"] == 0]
        sidx = {s: i for i, s in enumerate(P.S["id"])}
        N = N[N["s_id"].isin(sidx)]
        N["sidx"] = N["s_id"].map(sidx)
        perf_ids = [str(x) for x in refs.performance_ids]
        prov = dict(zip(P.perf["performance_id"], P.perf["provenance"], strict=True))
        sensor = [p for p in perf_ids if prov.get(p) != "transcribed"]
        trans = [p for p in perf_ids if prov.get(p) == "transcribed"]
        pick = list(rng.permutation(sensor))[:K]
        if len(pick) < K:
            pick += list(rng.choice(trans, K - len(pick), replace=False))
        meta[tag] = {"n_bars_refs": nb, "n_measures": int(len(P.meas)),
                     "n_measures_with_bar": len(bar_of), "beat_per_quarter": float(fac),
                     "K": len(pick), "n_sensor": int(sum(prov.get(p) != "transcribed"
                                                         for p in pick)),
                     "n_refs": len(refs), "rows": rows}
        built = pa.build_rows(P, A, ops_df)
        rowobj = {r.ann_id: r for r in built}
        # admissible null shifts per row (same checks as part (a))
        ts = P.S.groupby("m")[["ts_b", "ts_t"]].first()
        maxm = int(P.meas["number"].max())
        adm = {}
        for aid in rows:
            win = sorted(rowobj[aid].window)
            sig = [tuple(ts.loc[m]) for m in win]
            ds = []
            for d in range(-maxm, maxm + 1):
                w = [m + d for m in win]
                if d == 0 or min(w) < 1 or max(w) > maxm:
                    continue
                if any(m in U or m in pa.EXCLUDED_REGIONS[tag] for m in w):
                    continue
                if any((tuple(ts.loc[m]) if m in ts.index else None) != s
                       for m, s in zip(w, sig, strict=True)):
                    continue
                if sets_for(aid, P, A, d) is not None:
                    ds.append(d)
            adm[aid] = ds
        pidx_of = {p: i for i, p in enumerate(P.perf["performance_id"])}

        def tiers(n: pd.DataFrame, pid: str, prov=prov, refs=refs, nb=nb) -> dict:
            n = n.sort_values("onset")
            tg = target_on_grid(pid, prov.get(pid, ""), n["s_onset_beat"].to_numpy(float),
                                n["onset"].to_numpy(float), n["vel"].to_numpy(float), refs,
                                cfg.interpretation)
            it = _interpretation_section(ReportInputs(ap=None), tg, refs.exclude([pid]), None,
                                         cfg, nb)
            return {ch: it["bars"][ch]["tier"].to_numpy() for ch in ("tempo", "velocity")} | \
                {"vconf": it["velocity_confidence"],
                 "defined": {ch: np.isfinite(it["bars"][ch]["q95"].to_numpy())
                             for ch in ("tempo", "velocity")}}

        for j, pid in enumerate(pick):
            n0 = N[N["performance_id"] == pid][["sidx", "s_onset_beat", "p_onset_sec",
                                                "p_velocity"]]
            n0 = n0.rename(columns={"p_onset_sec": "onset", "p_velocity": "vel"})
            n0["vel"] = n0["vel"].astype(float)
            t0 = tiers(n0, pid)
            for ch in ("tempo", "velocity"):
                d_ = t0["defined"][ch]
                origin_bars.append({"piece": tag, "perf": pid, "channel": ch,
                                    "n_bars": int(d_.sum()),
                                    "n_flag": int((t0[ch][d_] != "none").sum()),
                                    "vconf": t0["vconf"]})
            pidx = pidx_of[pid]
            for aid in rows:
                ch, kind = ROWS_B[aid]
                st = sets_for(aid, P, A, 0)
                rec = {"piece": tag, "ann_id": aid, "perf": pid, "channel": ch,
                       "provenance": prov.get(pid), "vconf": t0["vconf"]}
                mi = [bar_of[m] for m in st["measures"] if m in bar_of]
                if len(mi) < len(st["measures"]):
                    raise RuntimeError(f"{aid}: marked measure without a report bar")
                rec["fa"] = bool(np.any(t0[ch][mi] != "none"))
                dn = degrade(kind, st, n0, P, pidx)
                if dn is not None:
                    td = tiers(dn, pid)
                    rec["hit"] = bool(np.any(td[ch][mi] != "none"))
                if adm[aid]:
                    d = int(rng.choice(adm[aid]))
                    sn = sets_for(aid, P, A, d)
                    dn2 = degrade(kind, sn, n0, P, pidx)
                    if dn2 is not None and all(m in bar_of for m in sn["measures"]):
                        tn = tiers(dn2, pid)
                        mi2 = [bar_of[m] for m in sn["measures"] if m in bar_of]
                        rec["null_hit"] = bool(np.any(tn[ch][mi2] != "none"))
                        rec["null_fa"] = bool(np.any(t0[ch][mi2] != "none"))
                        rec["null_d"] = d
                out.append(rec)
            log(tag, j + 1, "/", len(pick))
    return pd.DataFrame(out), pd.DataFrame(origin_bars), meta
