"""A-01: transcription quality proxies for Henry's phone takes (no ground truth).

    uv run python scripts/a01_henry_baseline.py [--workers 10] [--n-refs 15]

Inputs (all gitignored, personal data stays in data/):
* ``data/interim/henry_takes/transcribed/{transkun,aria_amt}/<k>.mid``: the two transcriptions
  of take ``k`` (01-05), made by ``transkun`` and ``scripts/transcribe_aria_amt_mac.py``;
* ``data/interim/henry_takes/scores/<k>_score.mxl`` and ``scores.json``: the PianoCoRe score
  (MusicXML from the raw zip) and piece id of each take.

Per take and transcriber: alignment to the score, F-02 correctness (error rate, wrong / missed /
extra), onset sanity, sustain and soft pedal usage, and a breakdown of the extra notes (quiet,
near-duplicate of a played note, octave / 12th above a played note). Between the transcribers:
note-level F1, velocity and onset agreement on common notes, and agreement of per-score-note error
labels.

**Floor:** the same measures for expert recordings through transcription. Up to ``--n-refs``
PianoCoRe tier A performances of each piece per transcriber (Aria-AMT and Transkun V2; PianoCoRe
transcribed these from mostly professional YouTube/CD audio), raw MIDI aligned to the same
MusicXML score with the same code. That is the error rate a note-perfect expert would get through
the same kind of pipeline, piece by piece, instead of D-10's pooled 0.080.

Writes ``data/interim/henry_takes/a01/{takes.csv,floor.csv,agreement.csv,summary.json}``.
Only aggregate numbers leave this folder.
"""

from __future__ import annotations

import argparse
import json
import tempfile
import warnings
import zipfile
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data" / "interim" / "henry_takes"
OUT = BASE / "a01"
TRANSCRIBERS = ("transkun", "aria_amt")
PC_TRANSCRIBER = {"Aria-AMT": "aria_amt", "Transkun V2": "transkun"}
A_KEYS = ["error_rate", "match_ratio", "n_score_notes", "n_performed_notes", "n_wrong_pitch",
          "n_missed", "n_extra", "n_bars", "n_bars_with_errors"]  # fmt: skip


def _quiet() -> None:
    import logging

    warnings.filterwarnings("ignore")
    logging.disable(logging.WARNING)


def _score(k: str):  # noqa: ANN202
    from pianolens.report.io import load_score

    meta = json.loads((BASE / "scores" / "scores.json").read_text())[k]
    return load_score(BASE / "scores" / f"{k}_score.mxl", meta["piece_id"]), meta


def extra_breakdown(ap, cr) -> dict[str, float]:  # noqa: ANN001
    """Where do the extra notes sit? Shares of extras that are quiet (velocity < 30), within
    150 ms of a correct note of the same pitch (split / re-struck), or within 50 ms of a correct
    note 12 or 19 semitones below (octave / twelfth: a harmonic read as a note)."""
    pn = ap.performance.notes
    vel_of = dict(zip(pn["id"].astype(str), pn["velocity"].astype(float), strict=True))
    nd = cr.notes
    lab = nd["label"].to_numpy().astype(str)
    ex, ok = lab == "extra", lab == "correct"
    n_ex = int(ex.sum())
    if n_ex == 0:
        return {"extra_quiet": np.nan, "extra_near_same_pitch": np.nan,
                "extra_harmonic": np.nan}  # fmt: skip
    on, pitch = nd["onset_sec"].to_numpy(float), nd["pitch"].to_numpy(int)
    vel = np.array([vel_of.get(str(i), np.nan) for i in nd["performance_id"]])
    on_ok, p_ok = on[ok], pitch[ok]
    near_same = harmonic = 0
    for t, p in zip(on[ex], pitch[ex], strict=True):
        d = np.abs(on_ok - t)
        near_same += bool(np.any((d < 0.15) & (p_ok == p)))
        harmonic += bool(np.any((d < 0.05) & np.isin(p - p_ok, (12, 19))))
    return {"extra_quiet": float(np.mean(vel[ex] < 30)), "extra_near_same_pitch": near_same / n_ex,
            "extra_harmonic": harmonic / n_ex}  # fmt: skip


def analyse(k: str, label: str, midi: Path, transcriber: str, provenance: str) -> dict:
    """Align one MIDI to take ``k``'s score and measure it."""
    _quiet()
    from pianolens.align import align_performance
    from pianolens.audio.transcription import onset_sanity, pedal_summary
    from pianolens.features.correctness import correctness
    from pianolens.report.io import load_performance

    sc, meta = _score(k)
    perf = load_performance(midi, provenance, meta["piece_id"], performance_id=label)
    ap = align_performance(sc, perf)
    cr = correctness(ap)
    pn = perf.notes
    t0, t1 = float(pn["onset_sec"].min()), float((pn["onset_sec"] + pn["duration_sec"]).max())
    row = {"take": k, "label": label, "transcriber": transcriber, "n_perf_notes_raw": len(pn),
           "duration_sec": t1 - t0}  # fmt: skip
    row.update({f"a_{x}": float(cr.summary[x]) for x in A_KEYS})
    g = max(1.0, cr.summary["n_score_notes"])
    row.update({"wrong_rate": cr.summary["n_wrong_pitch"] / g,
                "missed_rate": cr.summary["n_missed"] / g, "extra_rate": cr.summary["n_extra"] / g})
    row.update({f"on_{a}": b for a, b in onset_sanity(pn).items()})
    for num, name in ((64, "sus"), (67, "soft")):
        row.update({f"{name}_{a}": b for a, b in pedal_summary(perf.pedal, t0, t1, num).items()})
    row.update(extra_breakdown(ap, cr))
    return row


def agreement(k: str) -> dict:
    """Transkun vs Aria-AMT on the same take."""
    _quiet()
    from pianolens.align import align_performance
    from pianolens.audio.transcription import note_f1, robust_sd, velocity_agreement
    from pianolens.features.correctness import correctness
    from pianolens.report.io import load_performance

    sc, meta = _score(k)
    perfs, crs, aps = {}, {}, {}
    for t in TRANSCRIBERS:
        perfs[t] = load_performance(BASE / "transcribed" / t / f"{k}.mid", "transcribed",
                                    meta["piece_id"], performance_id=t)  # fmt: skip
        aps[t] = align_performance(sc, perfs[t])
        crs[t] = correctness(aps[t])
    a, b = perfs["transkun"].notes, perfs["aria_amt"].notes
    out = {"take": k}
    for tol in (0.05, 0.1):
        f = note_f1(a, b, onset_tol=tol, estimate_offset=True)
        out[f"f1_{int(tol * 1000)}ms"] = f["f1"]
        if tol == 0.05:
            out.update({"offset_ms": 1000 * f["offset_sec"], "onset_diff_rsd_ms":
                        f["onset_err_rsd_ms"], "p_aria_given_tk": f["recall"],
                        "p_tk_given_aria": f["precision"]})  # fmt: skip
    from pianolens.audio.transcription import match_notes

    m = match_notes(a, b, 0.05, offset=out["offset_ms"] / 1000)
    va = np.array([a["velocity"][i] for i, _ in m], float)
    vb = np.array([b["velocity"][j] for _, j in m], float)
    out.update({f"tk_vs_aria_{x}": y for x, y in velocity_agreement(va, vb).items()})
    # per score note labels (same unfolded score ids when both took the same repeat path)
    sa = crs["transkun"].score_notes.set_index("score_id")["label"].astype(str)
    sb = crs["aria_amt"].score_notes.set_index("score_id")["label"].astype(str)
    common = sa.index.intersection(sb.index)
    out["same_score_path"] = bool(len(common) == len(sa) == len(sb))
    ea = sa.loc[common].isin(["wrong_pitch", "missed"])
    eb = sb.loc[common].isin(["wrong_pitch", "missed"])
    out["n_score_notes_common"] = len(common)
    out["score_err_tk"] = int(ea.sum())
    out["score_err_aria"] = int(eb.sum())
    out["score_err_both"] = int((ea & eb).sum())
    out["score_err_jaccard"] = float((ea & eb).sum() / max(1, (ea | eb).sum()))
    # per bar total errors (wrong + missed + extra) agreement
    ba = crs["transkun"].bars.set_index("measure_index")["n_errors"]
    bb = crs["aria_amt"].bars.set_index("measure_index")["n_errors"]
    ci = ba.index.intersection(bb.index)
    out["bar_err_spearman"] = float(ba.loc[ci].corr(bb.loc[ci], method="spearman"))
    fa, fb = ba.loc[ci] >= 2, bb.loc[ci] >= 2
    out["bar2_jaccard"] = float((fa & fb).sum() / max(1, (fa | fb).sum()))
    # onset of the same score note in both transcriptions (timing agreement after alignment)
    def onsets(ap):  # noqa: ANN001, ANN202
        pn = ap.performance.notes
        pos = {str(i): float(t) for i, t in zip(pn["id"], pn["onset_sec"], strict=True)}
        return pd.Series({s: pos[q] for lab, s, q in ap.alignment.pairs.tolist()
                          if lab == "match" and q in pos})  # fmt: skip
    oa, ob = onsets(aps["transkun"]), onsets(aps["aria_amt"])
    ci = oa.index.intersection(ob.index)
    d = 1000 * (ob.loc[ci] - oa.loc[ci]).to_numpy()
    out["score_onset_diff_rsd_ms"] = robust_sd(d - np.median(d))
    return out


def floor_jobs(n_refs: int, seed: int = 0) -> list[tuple]:
    from pianolens.data.pianocore import PianoCoRe

    idx = PianoCoRe().index
    meta = json.loads((BASE / "scores" / "scores.json").read_text())
    rng = np.random.default_rng(seed)
    jobs = []
    for k, m in meta.items():
        rows = idx[idx["piece_id"] == m["piece_id"]]
        for cm, t in PC_TRANSCRIBER.items():
            r = rows[rows["capture_model"] == cm]
            take = rng.choice(len(r), size=min(n_refs, len(r)), replace=False)
            for i in sorted(take):
                jobs.append((k, str(r.iloc[i]["id"]), str(r.iloc[i]["performance_midi_path"]), t))
    return jobs


def floor_one(k: str, ref_id: str, rel: str, t: str) -> dict:
    from pianolens.data.pianocore import DEFAULT_ROOT, RAW_PREFIX, RAW_ZIP

    with zipfile.ZipFile(DEFAULT_ROOT / RAW_ZIP) as z, tempfile.TemporaryDirectory() as td:
        f = Path(td) / "ref.mid"
        f.write_bytes(z.read(RAW_PREFIX + rel))
        row = analyse(k, f"pianocore:{ref_id}", f, t, "transcribed")
    return row


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--n-refs", type=int, default=15)
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    takes = sorted(json.loads((BASE / "scores" / "scores.json").read_text()))
    rows, agr, floor = [], [], []
    with ProcessPoolExecutor(args.workers) as ex:
        futs = {ex.submit(analyse, k, f"henry:{t}", BASE / "transcribed" / t / f"{k}.mid", t,
                          "transcribed"): "take" for k in takes for t in TRANSCRIBERS}
        futs.update({ex.submit(agreement, k): "agr" for k in takes})
        futs.update({ex.submit(floor_one, *j): "floor" for j in floor_jobs(args.n_refs)})
        for fu in as_completed(futs):
            kind = futs[fu]
            try:
                r = fu.result()
            except Exception as e:  # noqa: BLE001 - count and report failures
                print(kind, "failed:", repr(e)[:200])
                continue
            {"take": rows, "agr": agr, "floor": floor}[kind].append(r)
    tk = pd.DataFrame(rows).sort_values(["take", "transcriber"])
    fl = pd.DataFrame(floor).sort_values(["take", "transcriber", "label"])
    ag = pd.DataFrame(agr).sort_values("take")
    tk.to_csv(OUT / "takes.csv", index=False)
    fl.to_csv(OUT / "floor.csv", index=False)
    ag.to_csv(OUT / "agreement.csv", index=False)
    cols = ["a_error_rate", "wrong_rate", "missed_rate", "extra_rate", "a_match_ratio",
            "on_share_double_trigger", "sus_down_fraction", "soft_down_fraction"]  # fmt: skip
    # floor: drop failed alignments (match ratio < 0.8 = alignment suspect, as in F-02)
    ok = fl[fl["a_match_ratio"] >= 0.8]
    summ = {"n_floor": int(len(fl)), "n_floor_ok": int(len(ok)), "per_take": {}}
    for (k, t), g in tk.groupby(["take", "transcriber"]):
        f = ok[(ok["take"] == k) & (ok["transcriber"] == t)]
        d = {"take": {c: float(g[c].iloc[0]) for c in cols}, "n_floor": int(len(f))}
        for c in cols:
            v = f[c].to_numpy(float)
            d[f"floor_{c}"] = {"median": float(np.nanmedian(v)) if len(v) else None,
                               "q90": float(np.nanquantile(v, 0.9)) if len(v) else None,
                               "pct_of_take": float(np.mean(v <= g[c].iloc[0])) if len(v)
                               else None}  # fmt: skip
        summ["per_take"][f"{k}:{t}"] = d
    (OUT / "summary.json").write_text(json.dumps(summ, indent=1))
    pd.set_option("display.width", 250)
    print(tk[["take", "transcriber", "a_error_rate", "wrong_rate", "missed_rate", "extra_rate",
              "a_match_ratio", "on_share_double_trigger", "sus_down_fraction",
              "extra_quiet", "extra_near_same_pitch", "extra_harmonic"]].round(3).to_string())
    print(ok.groupby(["take", "transcriber"])[["a_error_rate", "wrong_rate", "missed_rate",
                                               "extra_rate", "sus_down_fraction"]]
          .median().round(3).to_string())  # fmt: skip
    print(f"floor: {len(ok)} of {len(fl)} with match ratio >= 0.8")
    print(ag.round(3).T.to_string())


if __name__ == "__main__":
    main()
