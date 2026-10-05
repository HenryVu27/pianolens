"""BL-22: where do the high fixed-pitch extras on the phone takes come from? (data analysis only)

    uv run python scripts/bl22_phantom_extras.py labels     # align + label the takes (cached)
    uv run python scripts/bl22_phantom_extras.py analyse    # tests (a)-(c) + positive controls
    uv run python scripts/bl22_phantom_extras.py spectro    # test (d), numbers + images

Pre-registration: ``docs/specs/phone-audio-baseline.md``, section "BL-22 pre-registration".

PERSONAL DATA. The takes, their transcriptions, labels and every per-note output stay under
``data/interim/henry_takes/bl22/`` (gitignored). Only aggregate numbers are copied to the
experiment README, by hand.

A *high extra* is a transcribed note that the A-01 score alignment labels ``extra`` at G6 (MIDI
91) or above. Pedal = the transcriber's own sustain track (CC64 >= 64), unvalidated.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
HB = ROOT / "data" / "interim" / "henry_takes"
OUT = HB / "bl22"
PV = ROOT / "data" / "interim" / "pianovam_a01b"
CTRL = HB / "controlled"
G6 = 91
AFFECTED = ("03", "04", "05")
TAKES = ("01", "02", "03", "04", "05")
SEED = 0
N_NULL = 1000
B_INH = 0.001
PARTIALS = (2, 3, 4, 5, 6)


# ---- loading ------------------------------------------------------------------------------

def _pm(path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    import pretty_midi

    pm = pretty_midi.PrettyMIDI(str(path))
    rows = [(n.start, n.end - n.start, n.pitch, n.velocity)
            for ins in pm.instruments for n in ins.notes]
    df = pd.DataFrame(rows, columns=["onset_sec", "duration_sec", "pitch", "velocity"])
    df = df.sort_values(["onset_sec", "pitch"], kind="stable").reset_index(drop=True)
    cc = pd.DataFrame([(c.time, c.number, c.value) for ins in pm.instruments
                       for c in ins.control_changes], columns=["time_sec", "number", "value"])
    return df, cc.sort_values("time_sec", kind="stable").reset_index(drop=True)


def _label_take(k: str, model: str) -> pd.DataFrame:
    sys.path.insert(0, str(ROOT / "scripts"))
    from a01_henry_baseline import _quiet, _score

    from pianolens.align import align_performance
    from pianolens.features.correctness import correctness
    from pianolens.report.io import load_performance

    _quiet()
    sc, meta = _score(k)
    perf = load_performance(HB / "transcribed" / model / f"{k}.mid", "transcribed",
                            meta["piece_id"])
    nd = correctness(align_performance(sc, perf)).notes
    pn = pd.DataFrame({"performance_id": perf.notes["id"].astype(str),
                       "duration_sec": perf.notes["duration_sec"].astype(float),
                       "velocity": perf.notes["velocity"].astype(float)})
    nd = nd.assign(performance_id=nd["performance_id"].astype(str))
    d = nd.merge(pn, on="performance_id", how="left")
    d = d[d["onset_sec"].notna()].copy()
    d["take"], d["model"] = k, model
    return d[["take", "model", "label", "onset_sec", "duration_sec", "pitch", "velocity",
              "measure_index"]]  # fmt: skip


def labels() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    parts = [_label_take(k, m) for m in ("transkun", "aria_amt") for k in TAKES]
    d = pd.concat(parts, ignore_index=True)
    d.to_parquet(OUT / "labels.parquet")
    print(d.groupby(["model", "take", "label"]).size().unstack().to_string())


def _pedal_intervals(model: str, k: str) -> list[tuple[float, float]]:
    _, cc = _pm(HB / "transcribed" / model / f"{k}.mid")
    c = cc[cc["number"] == 64]
    iv, down = [], None
    for t, v in zip(c["time_sec"], c["value"], strict=True):
        if v >= 64 and down is None:
            down = float(t)
        elif v < 64 and down is not None:
            iv.append((down, float(t)))
            down = None
    if down is not None:
        iv.append((down, 1e9))
    return iv


def _down(t: np.ndarray, iv: list[tuple[float, float]]) -> np.ndarray:
    out = np.zeros(len(t), bool)
    for a, b in iv:
        out |= (t >= a) & (t < b)
    return out


# ---- (a) pedal ----------------------------------------------------------------------------

def _pedal_counts(d: pd.DataFrame, iv, t0: float, t1: float, shift: float = 0.0) -> dict:
    span = t1 - t0
    tt = ((d["onset_sec"].to_numpy() - t0 - shift) % span) + t0
    dn = _down(tt, iv)
    grid = np.linspace(t0, t1, 20001)
    frac = float(_down(grid, iv).mean())
    lab, p = d["label"].to_numpy(), d["pitch"].to_numpy()
    he, me, ch = (lab == "extra") & (p >= G6), (lab == "extra") & (p < G6), \
        (lab == "correct") & (p >= G6)
    ok = lab == "correct"
    return {"T_down": frac * span, "T_up": (1 - frac) * span, "down_frac": frac,
            "he_down": int((he & dn).sum()), "he_up": int((he & ~dn).sum()),
            "me_down": int((me & dn).sum()), "me_up": int((me & ~dn).sum()),
            "ch_down": int((ch & dn).sum()), "ch_up": int((ch & ~dn).sum()),
            "ok_down": int((ok & dn).sum()), "ok_up": int((ok & ~dn).sum())}


def _rr(c: dict, key: str) -> tuple[float, float]:
    def div(a: float, b: float) -> float:
        return a / b if b > 0 else np.nan

    rt = div(div(c[f"{key}_down"], c["T_down"]), div(c[f"{key}_up"], c["T_up"]))
    rd = div(div(c[f"{key}_down"], c["ok_down"]), div(c[f"{key}_up"], c["ok_up"]))
    return rt, rd


def pedal_test(lab: pd.DataFrame, model: str) -> dict:
    rng = np.random.default_rng(SEED)
    res, per = {}, {}
    info = {}
    for k in TAKES:
        d = lab[(lab["model"] == model) & (lab["take"] == k)]
        t0 = float(d["onset_sec"].min())
        t1 = float((d["onset_sec"] + d["duration_sec"]).max())
        iv = _pedal_intervals(model, k)
        info[k] = (d, iv, t0, t1)
        c = _pedal_counts(d, iv, t0, t1)
        per[k] = {**c, **{f"RR_{nm}_{key}": v for key in ("he", "me", "ch")
                          for nm, v in zip(("time", "density"), _rr(c, key), strict=True)}}
    keys = ["T_down", "T_up", "he_down", "he_up", "me_down", "me_up", "ch_down", "ch_up",
            "ok_down", "ok_up"]  # fmt: skip
    for group, ks in (("affected_all", AFFECTED),
                      ("affected_upge10", tuple(k for k in AFFECTED
                                                if per[k]["down_frac"] <= 0.9))):
        if not ks:
            res[group] = {"takes": []}
            continue
        pooled = {x: sum(per[k][x] for k in ks) for x in keys}
        obs = {key: _rr(pooled, key) for key in ("he", "me", "ch")}
        null = {key: [] for key in ("he", "me", "ch")}
        for _ in range(N_NULL):
            cs = []
            for k in ks:
                d, iv, t0, t1 = info[k]
                sh = rng.uniform(10.0, (t1 - t0) - 10.0)
                cs.append(_pedal_counts(d, iv, t0, t1, sh))
            pc = {x: sum(c[x] for c in cs) for x in keys}
            for key in null:
                null[key].append(_rr(pc, key)[1])
        res[group] = {"takes": list(ks), "pooled": pooled}
        for key in ("he", "me", "ch"):
            nl = np.array(null[key], float)
            res[group][key] = {"RR_time": obs[key][0], "RR_density": obs[key][1],
                               "null_mean": float(np.nanmean(nl)),
                               "null_q95": float(np.nanpercentile(nl, 95)),
                               "p": float(np.mean(nl >= obs[key][1]))}
        he = res[group]["he"]
        res[group]["verdict"] = ("pedal-linked" if he["RR_density"] >= 1.5 and he["p"] < 0.05
                                 else "not pedal-linked" if he["RR_density"] < 1.2
                                 or he["p"] >= 0.05 else "inconclusive")  # fmt: skip
    res["per_take"] = per
    return res


# ---- (b) harmonic -------------------------------------------------------------------------

def _harm_hits(pe: np.ndarray, te: np.ndarray, src_p: np.ndarray, src_t: np.ndarray,
               back: float, fwd: float = 0.05) -> np.ndarray:
    """For each extra (pitch pe, time te): is its pitch within the partial-k window of a
    source note starting in [te - back, te + fwd]? k in PARTIALS, inharmonicity allowance
    B_INH on the sharp side."""
    ks = np.array(PARTIALS, float)
    lo_k = 12 * np.log2(ks) - 0.5
    hi_k = 12 * np.log2(ks) + 0.5 + 6 * np.log2((1 + B_INH * ks**2) / (1 + B_INH))
    order = np.argsort(src_t)
    st, sp = src_t[order], src_p[order]
    a = np.searchsorted(st, te - back, "left")
    b = np.searchsorted(st, te + fwd, "right")
    out = np.zeros(len(pe), bool)
    for i in range(len(pe)):
        s = sp[a[i]:b[i]]
        if len(s) == 0:
            continue
        diff = pe[i] - s[:, None]
        out[i] = bool(np.any((diff >= lo_k) & (diff <= hi_k)))
    return out


def harmonic_test(groups: list[tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]],
                  uni_range: tuple[int, int] | None, back: float) -> dict:
    """groups: per recording (extra pitches, extra times, source pitches, source times).
    Pooled hit rate vs (1) pitch permutation within recording, (2) uniform pitch."""
    rng = np.random.default_rng(SEED)
    obs = np.concatenate([_harm_hits(pe, te, sp, st, back) for pe, te, sp, st in groups])
    n = len(obs)
    if n == 0:
        return {"n": 0}
    perm, uni = [], []
    for _ in range(N_NULL):
        perm.append(np.concatenate([_harm_hits(rng.permutation(pe), te, sp, st, back)
                                    for pe, te, sp, st in groups]).mean())  # fmt: skip
        if uni_range is not None:
            lo, hi = uni_range
            uni.append(np.concatenate([_harm_hits(rng.integers(lo, hi + 1, len(pe)), te, sp,
                                                  st, back) for pe, te, sp, st in groups]).mean())
        else:  # uniform within each recording's own extra-pitch range
            uni.append(np.concatenate([_harm_hits(rng.integers(pe.min(), pe.max() + 1, len(pe)),
                                                  te, sp, st, back) if len(pe) else np.zeros(0)
                                       for pe, te, sp, st in groups]).mean())  # fmt: skip
    perm, uni = np.array(perm), np.array(uni)
    o = float(obs.mean())
    res = {"n": n, "hit_rate": o,
           "perm_mean": float(perm.mean()), "perm_q95": float(np.percentile(perm, 95)),
           "perm_p": float(np.mean(perm >= o)), "ratio_perm": o / perm.mean(),
           "uni_mean": float(uni.mean()), "uni_q95": float(np.percentile(uni, 95)),
           "uni_p": float(np.mean(uni >= o)), "ratio_uni": o / uni.mean()}
    both_hi = (o >= 1.5 * perm.mean() and o > np.percentile(perm, 95)
               and o >= 1.5 * uni.mean() and o > np.percentile(uni, 95))
    either_lo = o < 1.2 * perm.mean() or o < 1.2 * uni.mean()
    res["verdict"] = "harmonic" if both_hi else "not harmonic" if either_lo else "inconclusive"
    return res


def _take_groups(lab: pd.DataFrame, model: str, takes) -> list:  # noqa: ANN001
    g = []
    for k in takes:
        d = lab[(lab["model"] == model) & (lab["take"] == k)]
        he = (d["label"] == "extra") & (d["pitch"] >= G6)
        src = d[~he]
        g.append((d.loc[he, "pitch"].to_numpy(int), d.loc[he, "onset_sec"].to_numpy(float),
                  src["pitch"].to_numpy(int), src["onset_sec"].to_numpy(float)))
    return g


def _pv_groups() -> tuple[list, list]:
    """PianoVAM Transkun false extras (label vs Disklavier truth), all registers and >= G6."""
    from pianolens.audio.extra_filter import label_false_extras

    allg, hig = [], []
    for p in sorted((PV / "transkun").glob("*.mid")):
        est, _ = _pm(p)
        ref, _ = _pm(ROOT / "data" / "raw" / "pianovam" / "MIDI" / p.name)
        y, _ = label_false_extras(ref, est)
        y = y.astype(bool)
        src = est[~y]
        ex = est[y]
        sp, st = src["pitch"].to_numpy(int), src["onset_sec"].to_numpy(float)
        allg.append((ex["pitch"].to_numpy(int), ex["onset_sec"].to_numpy(float), sp, st))
        h = ex[ex["pitch"] >= G6]
        hig.append((h["pitch"].to_numpy(int), h["onset_sec"].to_numpy(float), sp, st))
    return [g for g in allg if len(g[0])], [g for g in hig if len(g[0])]


def _ctrl_groups(model: str) -> list:
    from pianolens.audio.extra_filter import label_false_extras

    g = []
    for pc in sorted(p for p in CTRL.iterdir() if p.is_dir()):
        for cond in ("clean", "phone"):
            est, _ = _pm(pc / f"{cond}_{model}.mid")
            ref, _ = _pm(pc / "gt.mid")
            y = label_false_extras(ref, est)[0].astype(bool)
            src, ex = est[~y], est[y]
            if len(ex):
                g.append((ex["pitch"].to_numpy(int), ex["onset_sec"].to_numpy(float),
                          src["pitch"].to_numpy(int), src["onset_sec"].to_numpy(float)))
    return g


# ---- (c) fixed pitch and silence ----------------------------------------------------------

def _take_audio(k: str) -> tuple[np.ndarray, int]:
    import soundfile as sf

    wav = next((ROOT / "data" / "raw" / "henry_takes").glob(f"{k}_*.wav"))
    y, sr = sf.read(str(wav), always_2d=True)
    return y.mean(axis=1), sr


def _rms_db(y: np.ndarray, sr: int, t: np.ndarray, win: float = 0.1) -> np.ndarray:
    n = int(win * sr)
    frames = np.sqrt(np.mean(y[: len(y) // n * n].reshape(-1, n) ** 2, axis=1)) + 1e-12
    med = np.median(frames)
    out = []
    for ti in t:
        a = int(max(0, ti) * sr)
        seg = y[a:a + n]
        out.append(20 * np.log10((np.sqrt(np.mean(seg**2)) + 1e-12) / med) if len(seg) else np.nan)
    return np.array(out)


def fixed_and_silence(lab: pd.DataFrame, model: str, with_audio: bool) -> dict:
    rng = np.random.default_rng(SEED)
    res = {"per_take": {}}
    tops = {}
    for k in TAKES:
        d = lab[(lab["model"] == model) & (lab["take"] == k)]
        he = (d["label"] == "extra") & (d["pitch"] >= G6)
        hp = d.loc[he, "pitch"].astype(int)
        vc = hp.value_counts()
        top4 = vc.head(4)
        tops[k] = list(top4.index)
        played = set(d.loc[d["label"] == "correct", "pitch"].astype(int))
        te = d.loc[he, "onset_sec"].to_numpy(float)
        other = np.sort(d.loc[~he, "onset_sec"].to_numpy(float))
        t0 = float(d.loc[d["label"] == "correct", "onset_sec"].min())
        t1 = float(d.loc[d["label"] == "correct", "onset_sec"].max())
        s0, s1 = float(d["onset_sec"].min()), float((d["onset_sec"] + d["duration_sec"]).max())

        def isolated(t: np.ndarray, other: np.ndarray = other) -> np.ndarray:
            a = np.searchsorted(other, t - 0.5, "left")
            b = np.searchsorted(other, t + 0.1, "right")
            return (b - a) == 0

        rnd = rng.uniform(s0, s1, N_NULL)
        row = {"n_high_extra": int(he.sum()),
               "n_score_notes_proxy": int((d["label"] == "correct").sum()),
               "top4": {int(p): int(c) for p, c in top4.items()},
               "top4_share": float(top4.sum() / max(1, he.sum())),
               "share_never_played_correctly": float(np.mean([p not in played for p in hp]))
               if len(hp) else np.nan,
               "isolated_share": float(isolated(te).mean()) if len(te) else np.nan,
               "isolated_share_random": float(isolated(rnd).mean()),
               "before_first_played": int((te < t0).sum()),
               "after_last_played": int((te > t1).sum())}  # fmt: skip
        if with_audio and len(te):
            y, sr = _take_audio(k)
            row["rms_db_at_extras_median"] = float(np.nanmedian(_rms_db(y, sr, te)))
            row["rms_db_at_random_median"] = float(np.nanmedian(_rms_db(y, sr, rnd)))
            ch = d.loc[(d["label"] == "correct") & (d["pitch"] >= G6), "onset_sec"].to_numpy()
            row["rms_db_at_correct_high_median"] = float(np.nanmedian(_rms_db(y, sr, ch))) \
                if len(ch) else np.nan
            row["share_extras_rms_below_random_median"] = float(np.mean(
                _rms_db(y, sr, te) < row["rms_db_at_random_median"]))
        res["per_take"][k] = row
    shared = {}
    for k in AFFECTED:
        for p in tops[k]:
            shared[int(p)] = shared.get(int(p), 0) + 1
    res["top4_pitch_count_over_affected"] = dict(sorted(shared.items()))
    n_all3 = sum(1 for v in shared.values() if v == len(AFFECTED))
    top_ok = all(res["per_take"][k]["top4_share"] >= 0.5 for k in AFFECTED)
    res["n_pitches_in_top4_of_all_affected"] = n_all3
    res["verdict_fixed"] = "fixed-pitch" if top_ok and n_all3 >= 3 else "not fixed-pitch"
    iso = [res["per_take"][k] for k in AFFECTED]
    num = (sum(r["isolated_share"] * r["n_high_extra"] for r in iso)
           / sum(r["n_high_extra"] for r in iso))
    den = float(np.mean([r["isolated_share_random"] for r in iso]))
    res["isolated_pooled"] = num
    res["isolated_random_pooled"] = den
    res["verdict_silence"] = "in silence" if num >= 1.5 * den else "not in silence"
    return res


def analyse() -> None:
    lab = pd.read_parquet(OUT / "labels.parquet")
    res: dict = {}
    for model in ("transkun", "aria_amt"):
        r: dict = {"a_pedal": pedal_test(lab, model)}
        for win, back in (("recent_2s", 2.0), ("concurrent_50ms", 0.05)):
            r[f"b_harmonic_{win}_affected"] = harmonic_test(
                _take_groups(lab, model, AFFECTED), (G6, 108), back)
            r[f"b_harmonic_{win}_unaffected"] = harmonic_test(
                _take_groups(lab, model, ("01", "02")), (G6, 108), back)
        r["c_fixed_silence"] = fixed_and_silence(lab, model, with_audio=True)
        res[model] = r
    # positive controls (public data)
    pv_all, pv_hi = _pv_groups()
    res["control_pianovam_transkun_all_extras_recent_2s"] = harmonic_test(pv_all, None, 2.0)
    res["control_pianovam_transkun_all_extras_concurrent"] = harmonic_test(pv_all, None, 0.05)
    res["control_pianovam_transkun_ge_G6_recent_2s"] = harmonic_test(pv_hi, (G6, 108), 2.0)
    for model in ("transkun", "aria_amt"):
        cg = _ctrl_groups(model)
        res[f"control_rendered_{model}_all_extras_recent_2s"] = harmonic_test(cg, None, 2.0)
        res[f"control_rendered_{model}_all_extras_concurrent"] = harmonic_test(cg, None, 0.05)
    json.dump(res, open(OUT / "analyse.json", "w"), indent=1, default=float)
    print(json.dumps(res, indent=1, default=lambda x: round(float(x), 4)))


# ---- (d) spectrogram ----------------------------------------------------------------------

def _band_db(S_db: np.ndarray, freqs: np.ndarray, f: float, cents: float = 50.0) -> np.ndarray:
    lo, hi = f * 2 ** (-cents / 1200), f * 2 ** (cents / 1200)
    m = (freqs >= lo) & (freqs <= hi)
    return S_db[m].mean(axis=0) if m.any() else np.full(S_db.shape[1], np.nan)


def _hz(p: float) -> float:
    return 440.0 * 2 ** ((p - 69) / 12)


def _note_measures(S_db, freqs, times, t: float, p: int, band_med: dict) -> dict:  # noqa: ANN001
    def mean_in(x: np.ndarray, a: float, b: float) -> float:
        m = (times >= t + a) & (times < t + b)
        return float(np.nanmean(x[m])) if m.any() else np.nan

    f0 = _hz(p)
    b0 = _band_db(S_db, freqs, f0)
    nb = [_band_db(S_db, freqs, f0 * 2 ** (s / 12)) for s in (-2, -1, 1, 2)]
    nbm = np.nanmean(np.vstack(nb), axis=0)
    b2 = _band_db(S_db, freqs, 2 * f0)
    nb2 = np.nanmean(np.vstack([_band_db(S_db, freqs, 2 * f0 * 2 ** (s / 12))
                                for s in (-2, -1, 1, 2)]), axis=0)  # fmt: skip
    hf = (freqs >= 4000) & (freqs <= 10000)
    hfe = S_db[hf].mean(axis=0)
    i = int(np.searchsorted(times, t))
    j = int(np.searchsorted(times, t - 0.02))
    if p not in band_med:
        band_med[p] = float(np.nanmedian(b0))
    return {"prominence_f0_db": mean_in(b0 - nbm, 0, 0.1),
            "rise_f0_db": mean_in(b0, 0, 0.05) - mean_in(b0, -0.1, -0.05),
            "pre_level_vs_median_db": mean_in(b0, -0.3, -0.1) - band_med[p],
            "prominence_2f0_db": mean_in(b2 - nb2, 0, 0.1),
            "hf_flux_db": float(hfe[min(i, len(hfe) - 1)] - hfe[max(j, 0)])}


def spectro() -> None:
    import librosa

    lab = pd.read_parquet(OUT / "labels.parquet")
    lab = lab[lab["model"] == "transkun"]
    rows, wins = [], {}
    for k in AFFECTED:
        d = lab[lab["take"] == k]
        he = d[(d["label"] == "extra") & (d["pitch"] >= G6)]
        ch = d[(d["label"] == "correct") & (d["pitch"] >= G6)]
        te = np.sort(he["onset_sec"].to_numpy())
        cnt = np.searchsorted(te, te + 10.0, "right") - np.arange(len(te))
        w0 = float(te[int(np.argmax(cnt))])
        wins[k] = (w0, int(cnt.max()))
        y, sr = _take_audio(k)
        S = np.abs(librosa.stft(y, n_fft=4096, hop_length=240, center=True))
        S_db = librosa.amplitude_to_db(S, ref=np.max)
        freqs = librosa.fft_frequencies(sr=sr, n_fft=4096)
        times = librosa.frames_to_time(np.arange(S.shape[1]), sr=sr, hop_length=240)
        band_med: dict = {}
        for kind, sub in (("high_extra", he), ("correct_ge_G6", ch)):
            for t, p in zip(sub["onset_sec"], sub["pitch"], strict=True):
                m = _note_measures(S_db, freqs, times, float(t), int(p), band_med)
                m.update({"take": k, "kind": kind, "in_window": w0 <= t < w0 + 10.0,
                          "pitch": int(p)})
                rows.append(m)
        # random-time, random-high-pitch reference
        rng = np.random.default_rng(SEED)
        for t in rng.uniform(times[10], times[-10], 300):
            m = _note_measures(S_db, freqs, times, float(t), int(rng.integers(G6, 109)), band_med)
            m.update({"take": k, "kind": "random_time_pitch", "in_window": False})
            rows.append(m)
        try:
            import matplotlib

            matplotlib.use("Agg")
            import matplotlib.pyplot as plt

            a, b = np.searchsorted(times, w0 - 0.5), np.searchsorted(times, w0 + 10.5)
            fm = freqs <= 12000
            fig, ax = plt.subplots(figsize=(14, 6))
            ax.pcolormesh(times[a:b], freqs[fm], S_db[fm][:, a:b], shading="auto", vmin=-90)
            w = he[(he["onset_sec"] >= w0 - 0.5) & (he["onset_sec"] < w0 + 10.5)]
            ax.scatter(w["onset_sec"], [_hz(p) for p in w["pitch"]], s=12, c="r", marker="x")
            ax.set_ylabel("Hz")
            fig.savefig(OUT / f"spectro_{k}.png", dpi=110)
            plt.close(fig)
        except ImportError:
            pass
    df = pd.DataFrame(rows)
    df.to_parquet(OUT / "spectro_notes.parquet")
    cols = ["prominence_f0_db", "rise_f0_db", "pre_level_vs_median_db", "prominence_2f0_db",
            "hf_flux_db"]  # fmt: skip
    summ = df.groupby(["kind", "in_window"])[cols].median().round(2)
    cnt = df.groupby(["kind", "in_window"]).size().rename("n")
    out = summ.join(cnt)
    print(out.to_string())
    print(df.groupby(["take", "kind"])[cols].median().round(2).to_string())
    print({k: {"n_high_extras_in_window": v[1]} for k, v in wins.items()})
    # 2nd partial only where 2 f0 stays below the ~3.3 kHz roll-off seen in the takes (G6-A#6)
    low = df[df["pitch"].between(G6, 94)]
    print("G6-A#6 only (2f0 < 3.8 kHz):")
    print(low.groupby("kind")[["prominence_f0_db", "prominence_2f0_db"]].agg(["median", "size"])
          .round(2).to_string())
    json.dump({"summary": out.reset_index().to_dict(orient="records"),
               "windows_n": {k: v[1] for k, v in wins.items()}},
              open(OUT / "spectro.json", "w"), indent=1, default=float)


# ---- post hoc (added after (a)-(d) were seen; disclosed in the README) ---------------------

def _missed_notes(k: str, model: str) -> pd.DataFrame:
    sys.path.insert(0, str(ROOT / "scripts"))
    from a01_henry_baseline import _quiet, _score

    from pianolens.align import align_performance
    from pianolens.features.correctness import correctness
    from pianolens.report.io import load_performance

    _quiet()
    sc, meta = _score(k)
    perf = load_performance(HB / "transcribed" / model / f"{k}.mid", "transcribed",
                            meta["piece_id"])
    s = correctness(align_performance(sc, perf)).score_notes
    return s[(s["label"] == "missed") & s["expected_onset_sec"].notna()]


def _displaced(pe, te, mp, mt, steps, tol: float = 0.15) -> np.ndarray:  # noqa: ANN001
    out = np.zeros(len(pe), bool)
    for i in range(len(pe)):
        near = mp[np.abs(mt - te[i]) <= tol]
        out[i] = bool(np.isin(pe[i] - near, steps).any()) if len(near) else False
    return out


def posthoc() -> None:
    """(1) Octave / partial displacement: is a high extra within 150 ms of a *missed* score
    note (expected time from the alignment) lying a harmonic step below it (12, 19, 24, 28,
    31)? And any missed note within 150 ms at all? Null: permute extra pitches within take.
    (2) Long-term spectrum of each take vs PianoVAM and the rendered clean / phone audio."""
    import librosa
    import soundfile as sf

    lab = pd.read_parquet(OUT / "labels.parquet")
    rng = np.random.default_rng(SEED)
    res: dict = {}
    for model in ("transkun", "aria_amt"):
        groups = []
        for k in AFFECTED:
            d = lab[(lab["model"] == model) & (lab["take"] == k)]
            he = d[(d["label"] == "extra") & (d["pitch"] >= G6)]
            m = _missed_notes(k, model)
            groups.append((he["pitch"].to_numpy(int), he["onset_sec"].to_numpy(float),
                           m["pitch"].to_numpy(int), m["expected_onset_sec"].to_numpy(float)))
        steps = np.array([12, 19, 24, 28, 31])
        obs = np.concatenate([_displaced(*g, steps) for g in groups])
        null = [np.concatenate([_displaced(rng.permutation(g[0]), g[1], g[2], g[3], steps)
                                for g in groups]).mean() for _ in range(N_NULL)]  # fmt: skip
        near_any = np.concatenate([_displaced(g[0], g[1], g[2], g[3], np.arange(-128, 129))
                                   for g in groups])  # fmt: skip
        res[model] = {"n_high_extras": int(len(obs)),
                      "n_missed_notes": int(sum(len(g[2]) for g in groups)),
                      "harmonic_step_above_missed": float(obs.mean()),
                      "null_mean": float(np.mean(null)), "null_q95": float(np.percentile(null, 95)),
                      "p": float(np.mean(np.array(null) >= obs.mean())),
                      "any_missed_within_150ms": float(near_any.mean())}  # fmt: skip

    def ltas(path: Path, maxsec: float | None = None) -> dict:
        y, sr = sf.read(str(path), always_2d=True)
        y = y.mean(axis=1).astype(np.float32)
        if maxsec:
            y = y[: int(maxsec * sr)]
        S = np.abs(librosa.stft(y, n_fft=4096, hop_length=2048)) ** 2
        f = librosa.fft_frequencies(sr=sr, n_fft=4096)
        P = S.mean(axis=1)
        ref = P[(f >= 1000) & (f <= 2000)].mean()
        return {b: float(10 * np.log10(P[(f >= lo) & (f < hi)].mean() / ref))
                for b, (lo, hi) in {"3-4k": (3000, 4000), "4-6k": (4000, 6000),
                                    "6-10k": (6000, 10000)}.items()}  # fmt: skip

    bw = {f"take_{k}": ltas(next((ROOT / "data" / "raw" / "henry_takes").glob(f"{k}_*.wav")))
          for k in TAKES}  # fmt: skip
    pv = sorted((ROOT / "data" / "raw" / "pianovam" / "Audio").glob("*.wav"))
    pv_rows = [ltas(p, 300) for p in pv[:: max(1, len(pv) // 10)][:10]]
    bw["pianovam_10_files_median"] = {b: float(np.median([r[b] for r in pv_rows]))
                                      for b in pv_rows[0]}  # fmt: skip
    for c in ("clean", "phone"):
        rows = [ltas(pc / f"{c}.wav") for pc in sorted(CTRL.iterdir()) if pc.is_dir()]
        bw[f"rendered_{c}_median"] = {b: float(np.median([r[b] for r in rows])) for b in rows[0]}
    res["ltas_db_rel_1_2k"] = bw
    json.dump(res, open(OUT / "posthoc.json", "w"), indent=1)
    print(json.dumps(res, indent=1, default=lambda x: round(float(x), 3)))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["labels", "analyse", "spectro", "posthoc"])
    a = ap.parse_args()
    {"labels": labels, "analyse": analyse, "spectro": spectro, "posthoc": posthoc}[a.stage]()


if __name__ == "__main__":
    main()
