"""BL-21: transcription recall on fast same-pitch repeats, by inter-onset interval (IOI).

    uv run python scripts/bl21_repeated_notes.py subset     # Aria-AMT PianoVAM subset (truth only)
    uv run python scripts/bl21_repeated_notes.py run        # recall tables, all sources

Pre-registration: ``docs/specs/phone-audio-baseline.md``, section "BL-21 pre-registration".

Sources:
* PianoVAM microphone audio, Transkun 2.0.1 (``data/interim/pianovam_a01b/transkun``, A-01b), and
  Aria-AMT on a pre-registered subset (``data/interim/pianovam_bl21/aria_amt``);
* the A-01 controlled check: MAESTRO Disklavier MIDI rendered with the S-02 renderer, ``clean``
  and ``phone`` (``data/interim/henry_takes/controlled/<piece>/``; public data only).

A *repeat* is a true note whose previous same-pitch true note started < 500 ms before. Recall =
matched by a transcribed note of the same pitch within 50 ms after removing the per-file clock
offset (``pianolens.audio.transcription``). Outputs under ``data/interim/pianovam_bl21/``; the
summary tables are copied into the experiment README by hand.
"""

from __future__ import annotations

import argparse
import json
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PV_RAW = ROOT / "data" / "raw" / "pianovam"
PV_A01B = ROOT / "data" / "interim" / "pianovam_a01b"
OUT = ROOT / "data" / "interim" / "pianovam_bl21"
CTRL = ROOT / "data" / "interim" / "henry_takes" / "controlled"
BINS = [(0.0, 0.080, "<80"), (0.080, 0.120, "80-120"), (0.120, 0.200, "120-200"),
        (0.200, 0.500, "200-500")]  # fmt: skip
REF = "ref(>500/none)"
TOL = 0.05
SEED = 0
N_BOOT = 2000


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


def _pedal_down_at(cc: pd.DataFrame, t: np.ndarray, number: int = 64) -> np.ndarray:
    c = cc[cc["number"] == number]
    if len(c) == 0:
        return np.zeros(len(t), bool)
    ct, cv = c["time_sec"].to_numpy(), c["value"].to_numpy()
    i = np.searchsorted(ct, t, "right") - 1
    return np.where(i >= 0, cv[np.clip(i, 0, None)] >= 64, False)


def repeat_table(ref: pd.DataFrame, ref_cc: pd.DataFrame, est: pd.DataFrame) -> pd.DataFrame:
    """One row per true note: IOI to the previous same-pitch onset (NaN if none), matched?,
    previous same-pitch note matched?, any est note of that pitch within TOL (merge check),
    pedal and relative velocity."""
    from pianolens.audio.transcription import match_notes, note_f1

    f = note_f1(ref, est, onset_tol=TOL, estimate_offset=True)
    off = f["offset_sec"]
    m = match_notes(ref, est, onset_tol=TOL, offset=off)
    hit = np.zeros(len(ref), bool)
    hit[[i for i, _ in m]] = True
    on, p = ref["onset_sec"].to_numpy(), ref["pitch"].to_numpy()
    ioi = np.full(len(ref), np.nan)
    prev = np.full(len(ref), -1)
    last: dict[int, int] = {}
    for i in np.argsort(on, kind="stable"):
        j = last.get(int(p[i]))
        if j is not None:
            ioi[i], prev[i] = on[i] - on[j], j
        last[int(p[i])] = i
    e_on = est["onset_sec"].to_numpy() - off
    e_p = est["pitch"].to_numpy()
    any_est = np.array([bool(np.any((e_p == pi) & (np.abs(e_on - ti) <= TOL)))
                        for ti, pi in zip(on, p, strict=True)])  # fmt: skip
    vel = ref["velocity"].to_numpy()
    return pd.DataFrame({
        "pitch": p, "onset_sec": on, "ioi": ioi, "hit": hit,
        "prev_hit": np.where(prev >= 0, hit[np.clip(prev, 0, None)], False),
        "any_est": any_est, "pedal": _pedal_down_at(ref_cc, on),
        "vel_hi": vel >= np.median(vel), "velocity": vel, "f1": f["f1"], "offset_sec": off})


def bin_of(ioi: np.ndarray) -> np.ndarray:
    out = np.full(len(ioi), "", dtype=object)
    out[np.isnan(ioi) | (ioi >= 0.5)] = REF
    for lo, hi, name in BINS:
        out[(ioi >= lo) & (ioi < hi)] = name
    return out


def summarise(d: pd.DataFrame, unit: str = "rec") -> pd.DataFrame:
    """Recall per bin, with the difference to the reference and recording-bootstrap CIs."""
    d = d.copy()
    d["bin"] = bin_of(d["ioi"].to_numpy())
    names = [b[2] for b in BINS] + [REF]
    g = d.groupby([unit, "bin"])["hit"].agg(["sum", "size"]).unstack("bin")
    g = g.reindex(columns=pd.MultiIndex.from_product([["sum", "size"], names])).fillna(0)
    units = g.index.to_numpy()
    rng = np.random.default_rng(SEED)
    boots = {n: [] for n in names}
    diffs = {n: [] for n in names}
    for _ in range(N_BOOT):
        s = g.loc[rng.choice(units, len(units), replace=True)].sum()
        r = {n: s[("sum", n)] / s[("size", n)] if s[("size", n)] > 0 else np.nan for n in names}
        for n in names:
            boots[n].append(r[n])
            diffs[n].append(r[REF] - r[n])
    rows = []
    for n in names:
        sub = d[d["bin"] == n]
        miss = sub[~sub["hit"]]
        rec = sub["hit"].mean() if len(sub) else np.nan
        row = {"bin": n, "n": len(sub), "n_missed": len(miss), "recall": rec,
               "ci_lo": np.nanpercentile(boots[n], 2.5), "ci_hi": np.nanpercentile(boots[n], 97.5)}
        if n != REF:
            row.update({"drop_pts": 100 * (d.loc[d["bin"] == REF, "hit"].mean() - rec),
                        "drop_lo": 100 * np.nanpercentile(diffs[n], 2.5),
                        "drop_hi": 100 * np.nanpercentile(diffs[n], 97.5),
                        "merged_share_of_missed":
                            float((miss["prev_hit"] & ~miss["any_est"]).mean())
                            if len(miss) else np.nan,  # fmt: skip
                        "n_lt50": int((sub["ioi"] < 0.05).sum()),
                        "recall_lt50": float(sub.loc[sub["ioi"] < 0.05, "hit"].mean())
                        if (sub["ioi"] < 0.05).any() else np.nan})  # fmt: skip
            row["matters"] = ("too few" if len(sub) < 30 else
                              bool(row["drop_pts"] >= 2.0 and row["drop_lo"] > 0))
        rows.append(row)
    return pd.DataFrame(rows)


VEL_EDGES = [0, 20, 30, 40, 50, 60, 70, 80, 128]


def velocity_adjusted(d: pd.DataFrame, unit: str = "rec") -> pd.DataFrame:
    """POST HOC (added after the first results, disclosed in the README): repeats are much
    softer than reference notes, and soft notes are missed even when not repeated. Indirect
    standardisation: expected recall of a bin = mean over its notes of the reference recall in
    the note's velocity band (VEL_EDGES). Adjusted drop = expected - observed, in points, with a
    recording bootstrap (same seed and count as the primary table)."""
    d = d.copy()
    d["bin"] = bin_of(d["ioi"].to_numpy())
    d["vb"] = np.digitize(d["velocity"].to_numpy(), VEL_EDGES[1:-1])
    names = [b[2] for b in BINS]

    def stat(x: pd.DataFrame) -> dict:
        r = x[x["bin"] == REF].groupby("vb")["hit"].mean()
        out = {}
        for n in names:
            sub = x[x["bin"] == n]
            if len(sub) == 0:
                out[n] = (np.nan, np.nan)
                continue
            e = sub["vb"].map(r).astype(float)
            ok = e.notna()
            out[n] = (float(e[ok].mean()), float(sub.loc[ok, "hit"].mean()))
        return out

    base = stat(d)
    groups = {k: g for k, g in d.groupby(unit)}
    keys = np.array(list(groups))
    rng = np.random.default_rng(SEED)
    bd = {n: [] for n in names}
    for _ in range(N_BOOT):
        x = pd.concat([groups[k] for k in rng.choice(keys, len(keys), replace=True)])
        st = stat(x)
        for n in names:
            bd[n].append(100 * (st[n][0] - st[n][1]))
    rows = []
    for n in names:
        e, o = base[n]
        rows.append({"bin": n, "n": int((d["bin"] == n).sum()), "observed": o,
                     "expected_at_same_velocity": e, "adj_drop_pts": 100 * (e - o),
                     "adj_lo": np.nanpercentile(bd[n], 2.5),
                     "adj_hi": np.nanpercentile(bd[n], 97.5)})
    return pd.DataFrame(rows)


def strata(d: pd.DataFrame) -> pd.DataFrame:
    d = d.copy()
    d["bin"] = bin_of(d["ioi"].to_numpy())
    return (d.groupby(["bin", "pedal", "vel_hi"])["hit"].agg(["size", "mean"])
            .rename(columns={"size": "n", "mean": "recall"}).reset_index())


# ---- PianoVAM ----------------------------------------------------------------------------

def _pv_one(args: tuple[str, str]) -> pd.DataFrame:
    rt, est_dir = args
    ref, cc = _pm(PV_RAW / "MIDI" / f"{rt}.mid")
    est, _ = _pm(Path(est_dir) / f"{rt}.mid")
    t = repeat_table(ref, cc, est)
    t["rec"] = rt
    return t


def _pv_meta() -> pd.DataFrame:
    from pianolens.data.pianovam import pianovam_index

    md = pianovam_index().set_index("record_time")
    return pd.DataFrame({"pianist": md["P1_name"].str.strip().str.lower(),
                         "skill": md["P1_skill"]})


def subset() -> None:
    """Aria-AMT subset, from the truth MIDI only (pre-registered rule)."""
    import soundfile as sf

    md = _pv_meta()
    rows = []
    for p in sorted((PV_A01B / "transkun").glob("*.mid")):
        ref, _ = _pm(PV_RAW / "MIDI" / f"{p.stem}.mid")
        on, pt = ref["onset_sec"].to_numpy(), ref["pitch"].to_numpy()
        n = 0
        for q in np.unique(pt):
            o = np.sort(on[pt == q])
            n += int(np.sum(np.diff(o) < 0.2))
        dur = sf.info(str(PV_RAW / "Audio" / f"{p.stem}.wav")).duration
        rows.append({"rec": p.stem, "pianist": md.loc[p.stem, "pianist"], "n_rep200": n,
                     "audio_sec": dur})
    d = pd.DataFrame(rows)
    pick = d.sort_values(["pianist", "n_rep200"], ascending=[True, False]) \
        .groupby("pianist").head(1).sort_values("audio_sec")
    while pick["audio_sec"].sum() > 2 * 3600:
        pick = pick.iloc[:-1]
    OUT.mkdir(parents=True, exist_ok=True)
    pick.to_csv(OUT / "aria_subset.csv", index=False)
    print(pick.to_string(index=False))
    print("total h", pick["audio_sec"].sum() / 3600)


def run() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    md = _pv_meta()
    res: dict = {}
    rts = sorted(p.stem for p in (PV_A01B / "transkun").glob("*.mid"))
    with ProcessPoolExecutor(10) as ex:
        tk = pd.concat(ex.map(_pv_one, [(r, str(PV_A01B / "transkun")) for r in rts]),
                       ignore_index=True)
    tk["pianist"] = md.loc[tk["rec"], "pianist"].to_numpy()
    tk.to_parquet(OUT / "pianovam_transkun_notes.parquet")
    out = {"pianovam_transkun": summarise(tk)}
    out["pianovam_transkun_by_pianist_cluster"] = summarise(tk, unit="pianist")
    out["POSTHOC_velocity_adjusted_pianovam_transkun"] = velocity_adjusted(tk)
    res["strata_pianovam_transkun"] = strata(tk)
    aria_dir = OUT / "aria_amt"
    ar_rts = sorted(p.stem for p in aria_dir.glob("*.mid")) if aria_dir.exists() else []
    if ar_rts:
        with ProcessPoolExecutor(10) as ex:
            ar = pd.concat(ex.map(_pv_one, [(r, str(aria_dir)) for r in ar_rts]),
                           ignore_index=True)
        out["pianovam_aria_subset"] = summarise(ar)
        out["POSTHOC_velocity_adjusted_pianovam_aria_subset"] = velocity_adjusted(ar)
        with ProcessPoolExecutor(10) as ex:
            tks = pd.concat(ex.map(_pv_one, [(r, str(PV_A01B / "transkun")) for r in ar_rts]),
                            ignore_index=True)
        out["pianovam_transkun_same_subset"] = summarise(tks)
        out["POSTHOC_velocity_adjusted_pianovam_transkun_same_subset"] = velocity_adjusted(tks)
    # rendered path
    for cond in ("clean", "phone"):
        for model in ("transkun", "aria_amt"):
            parts = []
            for pc in sorted(p for p in CTRL.iterdir() if p.is_dir()):
                ref, cc = _pm(pc / "gt.mid")
                est, _ = _pm(pc / f"{cond}_{model}.mid")
                t = repeat_table(ref, cc, est)
                t["rec"] = pc.name
                parts.append(t)
            rd = pd.concat(parts, ignore_index=True)
            out[f"rendered_{cond}_{model}"] = summarise(rd)
            out[f"POSTHOC_velocity_adjusted_rendered_{cond}_{model}"] = velocity_adjusted(rd)
    with pd.option_context("display.width", 200, "display.max_columns", 30):
        for k, v in out.items():
            print(f"\n== {k}")
            print(v.round(4).to_string(index=False))
        print("\n== strata (PianoVAM Transkun): bin x pedal x velocity>=median")
        print(res["strata_pianovam_transkun"].round(4).to_string(index=False))
    json.dump({k: v.to_dict(orient="records") for k, v in out.items()},
              open(OUT / "summary.json", "w"), indent=1, default=str)
    res["strata_pianovam_transkun"].to_csv(OUT / "strata.csv", index=False)
    # recording-level counts
    print("\nrecordings", tk["rec"].nunique(), "true notes", len(tk),
          "pianists", tk["pianist"].nunique())


def takes() -> None:
    """POST HOC context (added after the audit asked for it to be reproducible): how often the
    owner's phone takes contain same-pitch score repeats, and how many of those the report counts
    as missed. The expected time of each score note comes from the A-01 Transkun alignment;
    pairs closer than 30 ms (voice unisons) are skipped. Prints aggregate counts only (personal
    data; nothing is written)."""
    import sys

    sys.path.insert(0, str(ROOT / "scripts"))
    from a01_henry_baseline import _quiet, _score

    from pianolens.align import align_performance
    from pianolens.features.correctness import correctness
    from pianolens.report.io import load_performance

    _quiet()
    hb = ROOT / "data" / "interim" / "henry_takes"
    keys = sorted(json.loads((hb / "scores" / "scores.json").read_text()))
    tot = {"score_notes": 0, "missed": 0}
    bins = {"30-120": (0.03, 0.12), "120-200": (0.12, 0.2), ">=200": (0.2, np.inf)}
    for b in bins:
        tot[f"rep_{b}"] = tot[f"missed_{b}"] = 0
    for k in keys:
        sc, meta = _score(k)
        perf = load_performance(hb / "transcribed" / "transkun" / f"{k}.mid", "transcribed",
                                meta["piece_id"])
        s = correctness(align_performance(sc, perf)).score_notes
        s = s[s["expected_onset_sec"].notna()].sort_values("expected_onset_sec")
        t, p = s["expected_onset_sec"].to_numpy(float), s["pitch"].to_numpy(int)
        mis = s["label"].to_numpy().astype(str) == "missed"
        ioi = np.full(len(s), np.nan)
        last: dict[int, int] = {}
        for i in range(len(s)):
            j = last.get(int(p[i]))
            if j is not None and t[i] - t[j] >= 0.03:
                ioi[i] = t[i] - t[j]
            if j is None or t[i] - t[j] >= 0.03:
                last[int(p[i])] = i
        tot["score_notes"] += len(s)
        tot["missed"] += int(mis.sum())
        for b, (lo, hi) in bins.items():
            m = (ioi >= lo) & (ioi < hi)
            tot[f"rep_{b}"] += int(m.sum())
            tot[f"missed_{b}"] += int((m & mis).sum())
    print(tot)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["subset", "run", "takes"])
    a = ap.parse_args()
    {"subset": subset, "run": run, "takes": takes}[a.stage]()


if __name__ == "__main__":
    main()
