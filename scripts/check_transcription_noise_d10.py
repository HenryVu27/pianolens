"""D-10: how much timing noise does audio transcription add? Paired Disklavier vs transcription.

    uv run python scripts/check_transcription_noise_d10.py [--workers 10]

PianoCoRe marks transcriptions of the same recording as duplicates (``is_duplicate``,
``lead_performance``). 65 transcribed rows (Aria-AMT 59, Transkun V2 / PERiScoPe 6) name an
ASAP Disklavier file as their lead, and 3 ASAP rows name an Aria-AMT transcription: the same
performance twice, once as Disklavier MIDI and once transcribed from (YouTube) audio. MAJEPPA
is Transkun (paper, arXiv 2608.11026), so the PERiScoPe pairs are the closest match.

Per pair, the ASAP row is found by file name, nearest note count and length
(PianoCoRe's copy is trimmed by a few notes, not byte-identical to data/raw/asap).
Both renditions are aligned to the ASAP score with ``align_performance``. Then:

* note level: score notes matched in both renditions give (Disklavier onset, transcribed onset,
  velocities). A straight-line fit maps one clock to the other (the audio may be offset or
  resampled); ``onset_err_local_*`` also removes a 21-note running median of the residual, so
  slow drift is not counted. Robust SD = 1.4826 * MAD;
* feature level: F-02 correctness, F-03 jitter and F-04 control features on both renditions
  (no timing references: the fallback ``jitter_nometric`` is the timing measure).

Writes ``data/interim/skill_control_d10/transcription_pairs.csv``.
"""

from __future__ import annotations

import argparse
import tempfile
import warnings
import zipfile
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "interim" / "skill_control_d10"
PC = ROOT / "data" / "raw" / "pianocore"
RAW_ZIP = PC / "PianoCoRe-1.0-raw-midi.zip"
KEYS = [
    "jitter_nometric_rms_ms", "jitter_nometric_rms_beats", "even_ioi_cv", "even_vel_sd_midi",
    "even_note_rate_nps", "even_strict_ioi_cv", "even_strict_vel_sd_midi",
    "even_strict_note_rate_nps", "hand_async_sd_ms", "hand_async_resid_sd_ms",
    "hand_async_resid_sd_beats", "hand_async_mean_ms", "tempo_instability_log_sd",
    "tempo_drift_log", "pedal_blur_fraction", "pedal_down_fraction", "pedal_available",
]  # fmt: skip
A_KEYS = ["accuracy", "error_rate", "n_wrong_pitch", "n_missed", "n_extra", "n_score_notes",
          "match_ratio"]  # fmt: skip


def pairs() -> pd.DataFrame:
    md = pd.read_csv(PC / "metadata.csv", usecols=[
        "performance_dataset", "performance_id", "is_duplicate", "lead_performance",
        "performance_midi_path", "capture_model"])  # fmt: skip
    d = md[md["is_duplicate"].eq(True)]
    a = d[d["lead_performance"].str.contains("/ASAP_", na=False)
          & d["performance_dataset"].ne("ASAP")]  # fmt: skip
    rows = [{"trans_path": r.performance_midi_path, "asap_path": r.lead_performance,
             "capture_model": r.capture_model, "direction": "trans->asap"}
            for r in a.itertuples()]  # fmt: skip
    cm = dict(zip(md["performance_midi_path"], md["capture_model"], strict=True))
    for r in d[d["performance_dataset"].eq("ASAP")].itertuples():
        rows.append({"trans_path": r.lead_performance, "asap_path": r.performance_midi_path,
                     "capture_model": cm.get(r.lead_performance, "?"),
                     "direction": "asap->trans"})  # fmt: skip
    return pd.DataFrame(rows)


def _robust_sd(x: np.ndarray) -> float:
    x = x[np.isfinite(x)]
    return float(1.4826 * np.median(np.abs(x - np.median(x)))) if len(x) else np.nan


def run_pair(p: dict, asap_row: dict) -> dict:
    warnings.filterwarnings("ignore")
    import logging

    logging.disable(logging.WARNING)
    from pianolens.align import align_performance
    from pianolens.data.asap import load_asap_performance, load_asap_score
    from pianolens.data.midi_io import performance_from_midi
    from pianolens.features.control import control_features
    from pianolens.features.correctness import correctness
    from pianolens.features.tempo import tempo_model

    row = pd.Series(asap_row)
    score = load_asap_score(row)
    disk = load_asap_performance(row)
    with zipfile.ZipFile(RAW_ZIP) as z, tempfile.TemporaryDirectory() as td:
        f = Path(td) / "t.mid"
        f.write_bytes(z.read("PianoCoRe/raw/" + p["trans_path"]))
        trans = performance_from_midi(f, dataset="pianocore", performance_id="trans",
                                      piece_id=row["piece_id"], performer_id=row["performer_id"],
                                      provenance="transcribed")  # fmt: skip
    out = {**p, "asap_performance_id": row["performance_id"], "piece_id": row["piece_id"]}
    aps = {}
    for tag, perf in (("disk", disk), ("trans", trans)):
        ap = align_performance(score, perf)
        aps[tag] = ap
        cr = correctness(ap)
        tc = tempo_model(ap)
        cf = control_features(ap, tc)
        pn = perf.notes
        span = float(pn["onset_sec"].max() - pn["onset_sec"].min())
        out[f"{tag}_n_notes"] = len(pn)
        out[f"{tag}_note_rate_nps"] = len(pn) / span if span > 0 else np.nan
        out[f"{tag}_n_score_notes_aligned"] = len(ap.score.notes)
        out[f"{tag}_jitter_rms_ms"] = float(tc.summary["jitter_rms_ms"])
        out[f"{tag}_n_pedal_events"] = 0 if perf.pedal is None else len(perf.pedal)
        for k in A_KEYS:
            out[f"{tag}_a_{k}"] = float(cr.summary[k])
        for k in KEYS:
            v = cf.summary.get(k, np.nan)
            out[f"{tag}_{k}"] = float(v) if v is not None else np.nan
    # note level: score notes matched in both renditions (same unfolded score ids)
    out["same_variant"] = len(aps["disk"].score.notes) == len(aps["trans"].score.notes)
    frames = {}
    for tag, ap in aps.items():
        pr = [(s, q) for lab, s, q in ap.alignment.pairs.tolist() if lab == "match"]
        pn = ap.performance.notes
        pos = {str(i): k for k, i in enumerate(pn["id"].astype(str))}
        frames[tag] = pd.DataFrame({
            "sid": [s for s, _ in pr],
            f"{tag}_on": [float(pn["onset_sec"][pos[q]]) for _, q in pr],
            f"{tag}_vel": [float(pn["velocity"][pos[q]]) for _, q in pr],
            f"{tag}_pitch": [int(pn["pitch"][pos[q]]) for _, q in pr],
        }).drop_duplicates("sid")  # fmt: skip
    j = frames["disk"].merge(frames["trans"], on="sid")
    j = j[j["disk_pitch"] == j["trans_pitch"]].sort_values("disk_on")
    out["n_common_notes"] = len(j)
    out["common_share_of_disk_matches"] = len(j) / max(1, len(frames["disk"]))
    if len(j) >= 50:
        x, y = j["disk_on"].to_numpy(), j["trans_on"].to_numpy()
        keep = np.ones(len(x), bool)
        for _ in range(3):  # trimmed least squares
            b, a = np.polyfit(x[keep], y[keep], 1)
            r = y - (a + b * x)
            keep = np.abs(r - np.median(r[keep])) < 5 * max(_robust_sd(r[keep]), 1e-3)
        r_ms = 1000 * (y - (a + b * x))
        loc = r_ms - pd.Series(r_ms).rolling(21, center=True, min_periods=5).median().to_numpy()
        out.update({
            "clock_slope": float(b), "clock_offset_s": float(a),
            "onset_err_rsd_ms": _robust_sd(r_ms),
            "onset_err_local_rsd_ms": _robust_sd(loc),
            "onset_err_local_rms_ms": float(np.sqrt(np.nanmean(
                np.clip(loc, -100, 100) ** 2))),
            "onset_err_local_share_gt30ms": float(np.nanmean(np.abs(loc) > 30)),
            "onset_err_local_p90_abs_ms": float(np.nanpercentile(np.abs(loc), 90)),
        })  # fmt: skip
        # IOI error: difference of consecutive (onset-sorted) common notes' local errors, which
        # is what evenness reads; for independent errors its SD is sqrt(2) * onset SD
        dl = np.diff(loc)
        out["ioi_err_rsd_ms"] = _robust_sd(dl)
        dv, tv = j["disk_vel"].to_numpy(), j["trans_vel"].to_numpy()
        vb, va = np.polyfit(dv, tv, 1)
        out.update({
            "vel_spearman": float(pd.Series(dv).corr(pd.Series(tv), method="spearman")),
            "vel_fit_slope": float(vb),
            "vel_resid_rsd_midi": _robust_sd(tv - (va + vb * dv)),
            "vel_resid_sd_midi": float(np.std(tv - (va + vb * dv), ddof=2)),
        })  # fmt: skip
    return out


def main() -> None:
    warnings.filterwarnings("ignore")
    from pianolens.data.asap import DEFAULT_ROOT as ASAP_ROOT
    from pianolens.data.asap import asap_index

    ap_ = argparse.ArgumentParser()
    ap_.add_argument("--workers", type=int, default=10)
    a = ap_.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    pr = pairs()
    idx = asap_index()
    # PianoCoRe's copies of ASAP files are trimmed by a few notes (not byte-identical): match on
    # the file name, then the nearest note count (within 2%) and MIDI length (within 10 s)
    def stats(data: bytes) -> tuple[int, float]:
        import io

        import mido

        m = mido.MidiFile(file=io.BytesIO(data))
        n = sum(x.type == "note_on" and x.velocity > 0 for t in m.tracks for x in t)
        return n, float(m.length)

    base = idx["midi_performance"].str.split("/").str[-1]
    todo, unmatched = [], []
    with zipfile.ZipFile(RAW_ZIP) as z:
        for p in pr.to_dict("records"):
            name = p["asap_path"].split("/")[-1].removeprefix("ASAP_")
            n, length = stats(z.read("PianoCoRe/raw/" + p["asap_path"]))
            best, err = None, np.inf
            for r in idx[base == name].to_dict("records"):
                m, ml = stats((Path(ASAP_ROOT) / r["midi_performance"]).read_bytes())
                e = abs(m - n) / max(n, 1)
                if e < 0.02 and abs(ml - length) < 10 and e < err:
                    best, err = r, e
            if best is not None:
                todo.append(({**p, "asap_note_diff_rel": err}, best))
            else:
                unmatched.append(p)
    print(f"{len(pr)} pairs; {len(todo)} matched to ASAP (name, notes, length); "
          f"{len(unmatched)} unmatched")
    rows, fails = [], []
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        futs = {ex.submit(run_pair, p, r): p for p, r in todo}
        for f in as_completed(futs):
            try:
                rows.append(f.result())
            except Exception as e:  # noqa: BLE001
                fails.append({**futs[f], "error": repr(e)})
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "transcription_pairs.csv", index=False)
    if fails or unmatched:
        pd.DataFrame(fails + [{**u, "error": "no unique ASAP match"} for u in unmatched]).to_csv(
            OUT / "transcription_pairs_failures.csv", index=False)
    print(f"{len(df)} pairs done, {len(fails)} failures")
    if df.empty:
        return
    pd.set_option("display.width", 250)
    cols = [c for c in df.columns if c.startswith(("onset_err", "ioi_err", "vel_", "clock"))]
    print(df.groupby("capture_model")[cols].median().T.round(3))


if __name__ == "__main__":
    main()
