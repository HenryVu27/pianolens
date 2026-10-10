"""BL-19b ``score`` stage: join the hand labels and compute the pre-registered statistics.

Written after the pre-registration was hashed (README, "Pre-registration hash"). Reads the
``align`` stage outputs in ``artifacts/`` and writes ``notes_labelled.parquet``,
``per_piece.csv``, ``summary.json`` and ``tables.txt``.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

import numpy as np
import pandas as pd

from pianolens.features import hand_proxies as hp

HERE = Path(__file__).resolve().parent
ART = HERE / "artifacts"
SEED = 20261010
NB = 2000
MIN_NOTES = 200
MIN_EVENTS = 50
log = logging.getLogger("bl19b")

QC = {"dice": 0.6, "exact_frac": 0.3, "consensus_frac": 0.5}
FLAGS = ["cross_voice", "cross_pitch", "cross_pitch_loose", "capacity", "at_risk"]


# --------------------------------------------------------------------------- data


def load_matched() -> tuple[pd.DataFrame, dict]:
    t = pd.read_parquet(ART / "takes.parquet")
    t["exact_frac"] = t["n_exact"] / t["n_pairs"]
    t["qc"] = ((t["dice"] >= QC["dice"]) & (t["exact_frac"] >= QC["exact_frac"])
               & (t["consensus_frac"] >= QC["consensus_frac"]))  # fmt: skip
    m = pd.read_parquet(ART / "matched.parquet")
    m = m.merge(t[["record_time", "take", "qc", "exact_frac", "performer_id", "skill"]],
                on=["record_time", "take"])  # fmt: skip
    info = {"n_takes": len(t), "n_takes_qc": int(t["qc"].sum()), "n_matched": len(m)}
    dup = (m.duplicated(["record_time", "perf_idx"], keep=False)
           | m.duplicated(["record_time", "take", "note_id"], keep=False))  # fmt: skip
    info["n_dup_rows"] = int(dup.sum())
    m = m[m["qc"] & ~dup & ~m["is_grace"] & m["staff"].isin([1, 2])].reset_index(drop=True)
    info["n_N0"] = len(m)
    return m, info


def join_labels(m: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Video and manual hand per matched note, by performance note (loader join)."""
    from pianolens.data import pianovam as pv

    want = set(m["record_time"])
    m = m.copy()
    m["hand"] = ""
    m["hand_manual"] = ""
    n_check = 0
    for perf in pv.iter_performances():
        rt = pv.record_time(perf)
        if rt not in want:
            continue
        sel = (m["record_time"] == rt).to_numpy()
        pidx = m.loc[sel, "perf_idx"].to_numpy()
        # the align stage loaded the same MIDI with the same reader: check ids and pitch
        assert (perf.notes["id"][pidx].astype(str) == m.loc[sel, "perf_note_id"].to_numpy()).all()
        assert (perf.notes["pitch"][pidx] == m.loc[sel, "perf_pitch"].to_numpy()).all()
        n_check += int(sel.sum())
        v = pv.hand_labels(perf, "video")
        m.loc[sel, "hand"] = v["hand"][pidx]
        g = pv.hand_labels(perf, "manual")
        if g is not None:
            m.loc[sel, "hand_manual"] = g["hand"][pidx]
    return m, {"n_label_checked": n_check}


def label_noise() -> dict:
    """Video vs manual hand on every manually labelled note (all 11 recordings)."""
    from pianolens.data import pianovam as pv

    k = n = n_man = 0
    for perf, g in pv.iter_hand_labels("manual"):
        v = pv.hand_labels(perf, "video")
        both = np.isin(g["hand"], ["L", "R"])
        n_man += int(both.sum())
        lab = both & np.isin(v["hand"], ["L", "R"])
        n += int(lab.sum())
        k += int((v["hand"][lab] != g["hand"][lab]).sum())
    lo, hi = hp.wilson(k, n)
    return {"e": k / n, "e_lo": lo, "e_hi": hi, "errors": k, "n_both": n, "n_manual": n_man}


# --------------------------------------------------------------------------- statistics


def piece_counts(d: pd.DataFrame, rule: str, by: str = "score_pid") -> pd.DataFrame:
    bad = (d[rule] != d["hand"]).astype(int)
    return (pd.DataFrame({by: d[by], "bad": bad}).groupby(by)["bad"].agg(["sum", "size"])
            .rename(columns={"sum": "bad", "size": "n"}))  # fmt: skip


def rate_block(d: pd.DataFrame, rule: str, seed: int = SEED, by: str = "score_pid") -> dict:
    pc = piece_counts(d, rule, by)
    est, lo, hi = hp.cluster_ratio_ci(pc["bad"].to_numpy(), pc["n"].to_numpy(), NB, seed)
    big = pc[pc["n"] >= MIN_NOTES]
    share = big["bad"] / big["n"]
    mean, mlo, mhi = hp.cluster_mean_ci(share.to_numpy(), NB, seed)
    _, tlo, thi = hp.t_interval(share.to_numpy())
    med, medlo, medhi = hp.cluster_mean_ci(share.to_numpy(), NB, seed, stat=np.median)
    return {"pooled": est, "pooled_ci": [lo, hi], "n_notes": int(pc["n"].sum()),
            "n_units": len(pc), "n_units_min": len(big), "mean_unit": mean,
            "mean_unit_ci_boot": [mlo, mhi], "mean_unit_ci_t": [tlo, thi],
            "median_unit": med, "median_unit_ci": [medlo, medhi],
            "share_units_gt10": float((share > 0.10).mean()) if len(share) else float("nan")}  # fmt: skip


def paired_delta(d: pd.DataFrame, a: str, b: str) -> dict:
    """Pooled M(a) - M(b) with a paired piece bootstrap, and the per-piece deltas."""
    pa, pb = piece_counts(d, a), piece_counts(d, b)
    na, nb_, n = pa["bad"].to_numpy(float), pb["bad"].to_numpy(float), pa["n"].to_numpy(float)
    est = (na.sum() - nb_.sum()) / n.sum()
    rng = np.random.default_rng(SEED)
    idx = rng.integers(0, len(n), size=(NB, len(n)))
    bt = (na[idx].sum(1) - nb_[idx].sum(1)) / n[idx].sum(1)
    lo, hi = np.percentile(bt, [2.5, 97.5])
    per = (pa["bad"] - pb["bad"]) / pa["n"]
    big = per[pa["n"] >= MIN_NOTES]
    return {"pooled_delta": float(est), "ci": [float(lo), float(hi)],
            "pieces_a_worse": int((big > 0).sum()), "pieces_b_worse": int((big < 0).sum()),
            "pieces_equal": int((big == 0).sum()), "per_piece": per.round(5).to_dict()}  # fmt: skip


def detection(d: pd.DataFrame, flag: str) -> dict:
    bad = (d["STAFF"] != d["hand"]).astype(int)
    f = d[flag].astype(int)
    g = pd.DataFrame({"p": d["score_pid"], "tp": bad * f, "f": f, "bad": bad, "n": 1}) \
        .groupby("p").sum()
    prec = hp.cluster_ratio_ci(g["tp"].to_numpy(), g["f"].to_numpy(), NB, SEED)
    rec = hp.cluster_ratio_ci(g["tp"].to_numpy(), g["bad"].to_numpy(), NB, SEED)
    # lift = precision / base rate, bootstrapped jointly
    rng = np.random.default_rng(SEED)
    idx = rng.integers(0, len(g), size=(NB, len(g)))
    with np.errstate(invalid="ignore", divide="ignore"):
        lb = ((g["tp"].to_numpy()[idx].sum(1) / g["f"].to_numpy()[idx].sum(1))
              / (g["bad"].to_numpy()[idx].sum(1) / g["n"].to_numpy()[idx].sum(1)))  # fmt: skip
    base = g["bad"].sum() / g["n"].sum()
    lift = prec[0] / base if base > 0 else float("nan")
    lo, hi = np.nanpercentile(lb, [2.5, 97.5])
    return {"n_flagged": int(g["f"].sum()), "flag_share": float(g["f"].sum() / g["n"].sum()),
            "precision": prec[0], "precision_ci": list(prec[1:]), "recall": rec[0],
            "recall_ci": list(rec[1:]), "lift": float(lift), "lift_ci": [float(lo), float(hi)]}  # fmt: skip


def events_block(d: pd.DataFrame) -> tuple[dict, pd.DataFrame]:
    ev = hp.event_mismatch(d, ["record_time", "take", "score_pid", "onset"], rule="STAFF")
    pc = ev.groupby("score_pid")["affected"].agg(["sum", "size"])
    est, lo, hi = hp.cluster_ratio_ci(pc["sum"].to_numpy(), pc["size"].to_numpy(), NB, SEED)
    big = pc[pc["size"] >= MIN_EVENTS]
    share = big["sum"] / big["size"]
    med, mlo, mhi = hp.cluster_mean_ci(share.to_numpy(), NB, SEED, stat=np.median)
    gt20, g_lo, g_hi = hp.cluster_mean_ci((share > 0.20).astype(float).to_numpy(), NB, SEED)
    out = {"n_events": int(pc["size"].sum()), "pooled": est, "pooled_ci": [lo, hi],
           "n_pieces_min": len(big), "median_piece": med, "median_piece_ci": [mlo, mhi],
           "share_pieces_gt20": gt20, "share_pieces_gt20_ci": [g_lo, g_hi],
           "pieces_gt20": share[share > 0.20].round(4).to_dict()}  # fmt: skip
    out["D2"] = "pass" if (med <= 0.05 and gt20 <= 0.10) else "concern"
    return out, pc.rename(columns={"sum": "ev_affected", "size": "n_events"})


def bar_reading(lo: float, hi: float, bar: float) -> str:
    return "below" if hi < bar else ("above" if lo > bar else "inconclusive")


def noinfo_block(n0: pd.DataFrame, n: pd.DataFrame) -> dict:
    d = n0.assign(noinfo=~n0["hand"].isin(["L", "R"]))
    g = d.groupby(["score_pid", "at_risk"])["noinfo"].agg(["sum", "size"]).unstack(fill_value=0)
    a_num, a_den = g[("sum", True)].to_numpy(float), g[("size", True)].to_numpy(float)
    b_num, b_den = g[("sum", False)].to_numpy(float), g[("size", False)].to_numpy(float)
    rng = np.random.default_rng(SEED)
    idx = rng.integers(0, len(g), size=(NB, len(g)))
    with np.errstate(invalid="ignore", divide="ignore"):
        r = ((a_num[idx].sum(1) / a_den[idx].sum(1)) / (b_num[idx].sum(1) / b_den[idx].sum(1)))
    ra, rb = a_num.sum() / a_den.sum(), b_num.sum() / b_den.sum()
    lo, hi = np.nanpercentile(r, [2.5, 97.5])
    # inverse-probability weights by (piece, at_risk, staff)
    cell = ["score_pid", "at_risk", "staff"]
    p_lab = (1 - d.groupby(cell)["noinfo"].mean()).rename("p_lab")
    w = 1.0 / n.join(p_lab, on=cell)["p_lab"]
    bad = (n["STAFF"] != n["hand"]).astype(float)
    ipw = float((w * bad).sum() / w.sum())
    by_staff = d.groupby("staff")["noinfo"].mean().round(4).to_dict()
    return {"noinfo_overall": float(d["noinfo"].mean()), "noinfo_at_risk": float(ra),
            "noinfo_not_at_risk": float(rb), "ratio": float(ra / rb), "ratio_ci": [lo, hi],
            "D5": "lower bound" if lo > 1.5 else "no adjustment",
            "M_staff_ipw": ipw, "noinfo_by_staff": by_staff}  # fmt: skip


def words_block(n: pd.DataFrame, n0: pd.DataFrame) -> dict:
    w = pd.read_parquet(ART / "hand_words.parquet")
    if w.empty:
        return {"n_words": 0}
    c = w[w["contradicts"]][["score_pid", "measure_name", "staff", "text"]].drop_duplicates(
        ["score_pid", "measure_name", "staff"])
    key = ["score_pid", "measure_name", "staff"]
    mk = n.merge(c, on=key, how="inner")
    mk0 = n0.merge(c, on=key, how="inner")
    bad = mk["STAFF"] != mk["hand"]
    played = mk0.groupby(key).size()
    out = {"n_contradicting_words": int(len(c)), "n_marked_measures_played": int(len(played)),
           "n_notes_labelled": int(len(mk)), "n_notes_matched": int(len(mk0)),
           "noinfo_share": float((~mk0["hand"].isin(["L", "R"])).mean()) if len(mk0) else None,
           "mismatch": float(bad.mean()) if len(mk) else None,
           "n_mismatch": int(bad.sum()),
           "at_risk_among_mismatch": float(mk.loc[bad, "at_risk"].mean()) if bad.any() else None,
           "at_risk_among_all": float(mk["at_risk"].mean()) if len(mk) else None}  # fmt: skip
    rows = []
    for k_, g in mk.groupby(key):
        b = g["STAFF"] != g["hand"]
        rows.append({"score_pid": k_[0][-40:], "measure": k_[1], "staff": k_[2],
                     "n": len(g), "mismatch": round(float(b.mean()), 3),
                     "at_risk_mismatched": int((b & g["at_risk"]).sum())})  # fmt: skip
    out["per_measure"] = rows
    # piece base rate on the same staff, for comparison
    base = []
    for pid, st in {(r["score_pid"], r["staff"]) for _, r in c.iterrows()}:
        s = n[(n["score_pid"] == pid) & (n["staff"] == st)]
        if len(s):
            base.append({"score_pid": pid[-40:], "staff": st,
                         "base_mismatch": round(float((s["STAFF"] != s["hand"]).mean()), 4)})  # fmt: skip
    out["piece_staff_base"] = base
    return out


def manual_block(n0: pd.DataFrame) -> dict:
    d = n0[n0["hand_manual"].isin(["L", "R"])]
    lab = d["hand"].isin(["L", "R"])
    return {"n_manual_matched": len(d), "recordings": sorted(set(d["record_time"])),
            "M_staff_vs_manual": hp.mismatch(d["STAFF"].to_numpy(), d["hand_manual"].to_numpy()),
            "n_mismatch_manual": int((d["STAFF"] != d["hand_manual"]).sum()),
            "video_labelled": int(lab.sum()),
            "video_vs_manual_disagree": int((d.loc[lab, "hand"] != d.loc[lab, "hand_manual"]).sum()),
            "M_staff_vs_video_same_notes": hp.mismatch(d.loc[lab, "STAFF"].to_numpy(),
                                                       d.loc[lab, "hand"].to_numpy())}  # fmt: skip


def performer_block(n: pd.DataFrame) -> dict:
    r = rate_block(n, "STAFF", by="performer_id")
    pc = piece_counts(n, "STAFF", by="performer_id")
    r["per_performer"] = {k.split(":")[1]: {"n": int(v["n"]), "M": round(v["bad"] / v["n"], 4)}
                          for k, v in pc.iterrows()}  # fmt: skip
    return r


# --------------------------------------------------------------------------- stage


def stage_score() -> None:
    t0 = time.time()
    n0, info = load_matched()
    n0, info2 = join_labels(n0)
    info.update(info2)
    sn = pd.read_parquet(ART / "score_notes.parquet")
    vh = pd.concat([hp.voice_hand(g).rename("VOICE").to_frame().assign(note_id=g["note_id"],
                    score_pid=pid) for pid, g in sn.groupby("score_pid")])  # fmt: skip
    n0 = n0.merge(vh, on=["score_pid", "note_id"], how="left")
    n0["STAFF"] = hp.staff_hand(n0["staff"])
    n0["PITCH"] = hp.pitch_split_hand(n0["pitch"])
    n0["ravel_debussy"] = n0["score_pid"].str.contains("Ravel|debussy", case=False)
    n0.to_parquet(ART / "notes_labelled.parquet")
    n = n0[n0["hand"].isin(["L", "R"])].reset_index(drop=True)
    info.update(n_N=len(n), n_pieces=int(n["score_pid"].nunique()),
                n_performers=int(n["performer_id"].nunique()),
                n_recordings=int(n["record_time"].nunique()))  # fmt: skip
    noise = label_noise()
    res: dict = {"info": info, "label_noise": noise}
    s1 = rate_block(n, "STAFF")
    s1["noise_corrected_pooled"] = hp.noise_corrected(s1["pooled"], noise["e"])
    s1["noise_corrected_pooled_ci"] = [hp.noise_corrected(x, noise["e"]) for x in s1["pooled_ci"]]
    res["S1_staff"] = s1
    res["D1"] = {f"bar_{int(b * 100)}pct": bar_reading(*s1["pooled_ci"], b) for b in (0.02, 0.05)}
    res["S1_voice"] = rate_block(n, "VOICE")
    res["S1_pitch"] = rate_block(n, "PITCH")
    s2, ev_pc = events_block(n)
    res["S2_events"] = s2
    res["S3_pitch_minus_staff"] = paired_delta(n, "PITCH", "STAFF")
    res["S3_voice_minus_staff"] = paired_delta(n, "VOICE", "STAFF")
    res["D3"] = "staff beats pitch" if res["S3_pitch_minus_staff"]["ci"][0] > 0 else "not shown"
    res["S4_detection"] = {f: detection(n, f) for f in FLAGS}
    ar = res["S4_detection"]["at_risk"]
    res["D4"] = "useful" if (ar["lift_ci"][0] > 2 and ar["recall"] >= 0.5) else "not useful"
    res["S5_words"] = words_block(n, n0)
    res["S6_noinfo"] = noinfo_block(n0, n)
    res["S7_manual"] = manual_block(n0)
    # subsets (descriptive)
    sub = {}
    for f in ["cross_voice", "cross_pitch", "capacity", "at_risk", "sync_event"]:
        sub[f"flag_{f}"] = rate_block(n[n[f]], "STAFF")
        sub[f"not_{f}"] = rate_block(n[~n[f]], "STAFF")
    sub["ravel_debussy"] = rate_block(n[n["ravel_debussy"]], "STAFF")
    sub["other_composers"] = rate_block(n[~n["ravel_debussy"]], "STAFF")
    for s in sorted(n["skill"].unique()):
        sub[f"skill_{s}"] = rate_block(n[n["skill"] == s], "STAFF")
    sub["consensus_only"] = rate_block(n[n["consensus"]], "STAFF")
    sub["takes_exact_ge_0.7"] = rate_block(n[n["exact_frac"] >= 0.7], "STAFF")
    sub["performer_cluster"] = performer_block(n)
    res["subsets"] = sub
    # per piece table
    pp = (n.groupby("score_pid").agg(n=("hand", "size"), recs=("record_time", "nunique"),
                                     performers=("performer_id", "nunique"),
                                     at_risk=("at_risk", "mean"))  # fmt: skip
          .join(piece_counts(n, "STAFF")["bad"].rename("bad_staff"))
          .join(piece_counts(n, "VOICE")["bad"].rename("bad_voice"))
          .join(piece_counts(n, "PITCH")["bad"].rename("bad_pitch"))
          .join(ev_pc))  # fmt: skip
    noinfo = n0.groupby("score_pid")["hand"].apply(lambda s: float((~s.isin(["L", "R"])).mean()))
    pp = pp.join(noinfo.rename("noinfo"))
    for c in ("staff", "voice", "pitch"):
        pp[f"M_{c}"] = pp[f"bad_{c}"] / pp["n"]
    pp["ev_share"] = pp["ev_affected"] / pp["n_events"]
    pp.sort_values("M_staff", ascending=False).to_csv(ART / "per_piece.csv")
    rho = pp[["at_risk", "M_staff"]].corr(method="spearman").iloc[0, 1]
    res["piece_spearman_at_risk_vs_M"] = float(rho)
    res["wall_sec"] = round(time.time() - t0, 1)
    (ART / "summary.json").write_text(json.dumps(res, indent=1, default=float))
    log.info("%s", json.dumps({k: res[k] for k in ("info", "label_noise", "D1", "D3", "D4")},
                              indent=1, default=float))  # fmt: skip
