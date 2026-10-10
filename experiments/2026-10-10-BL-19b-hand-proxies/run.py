"""BL-19b: staff-vs-hand proxies against PianoVAM video hand labels.

Stages (outputs in ``artifacts/``, gitignored)::

    OMP_NUM_THREADS=1 uv run python experiments/2026-10-10-BL-19b-hand-proxies/run.py align
    OMP_NUM_THREADS=1 uv run python experiments/2026-10-10-BL-19b-hand-proxies/run.py score

``align`` (development; reads no hand label): split each of the 44 catalogue-candidate
recordings into takes against its candidate score(s) (``pianolens.data.session_takes``), match
notes with parangonar, compute the BL-19 score proxies per score note, and run the same take
finder against a wrong score (the null) to set the take QC. Writes ``takes.parquet``,
``matched.parquet``, ``null_takes.parquet``, ``score_notes.parquet``, ``hand_words.parquet``.

``score`` (after the pre-registration is hashed): joins ``pianovam.hand_labels`` by performance
note (pitch and onset, inside the loader) and computes the pre-registered statistics.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import logging
import re
import sys
import time
import warnings
import zipfile
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
ART = HERE / "artifacts"
CATALOG = ROOT / "data" / "interim" / "app" / "catalog.json"
log = logging.getLogger("bl19b")


def _load_script(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# --------------------------------------------------------------------------- candidates

# Development decisions (made before any hand label was read; see README "Development"):
# * whole-work duplicates are dropped where movement scores exist (K. 545, Clementi No. 1);
# * the ASAP "Italian concerto" score is the 2nd movement (49 bars of 3/4), and PianoVAM has
#   the 1st and 3rd only, so BWV 971 (PianoCoRe, the whole concerto) is the one candidate;
# * Ondine uses the ASAP score only (one engraving per piece).
_OP17 = ["schumann_op17_mv1", "schumann_op17_mv2", "schumann_op17_mv3"]
_K545 = ["mozart_k545_mv1", "mozart_k545_mv2", "mozart_k545_mv3"]
_TOMBEAU = [f"pianocore:Ravel,_Maurice/Le_Tombeau_de_Couperin,_M.68/{m}"
            for m in ("1._Prelude", "2._Fugue", "3._Forlane", "4._Rigaudon", "5._Menuet",
                      "6._Toccata")]  # fmt: skip
CANDIDATES_OVERRIDE: dict[str, list[str]] = {
    "pianovam:r_schumann/fantasie_op_17": _OP17,
    "pianovam:w_a_mozart/sonata_k_545": _K545,
    "pianovam:w_a_mozart/sonata_no_15_k_545": _K545,
    "pianovam:w_a_mozart/sonata_k_310": ["mozart_k310_mv1", "mozart_k310_mv3"],
    "pianovam:m_clementi/sonatine_op_36": ["clementi_op36_no1", "clementi_op36_no3"],
    "pianovam:m_ravel/le_tombeau_de_couperin": _TOMBEAU,
    "pianovam:j_s_bach/italian_concerto_mvt_1": ["bach_bwv971"],
    "pianovam:j_s_bach/italian_concerto_mvt_3": ["bach_bwv971"],
    "pianovam:m_ravel/gaspard_de_la_nuit_ondine": ["asap:Ravel/Gaspard_de_la_Nuit_1_Ondine"],
}


def candidates(piece_id: str) -> list[str]:
    from pianolens.data import pianovam as pv

    if piece_id in CANDIDATES_OVERRIDE:
        return CANDIDATES_OVERRIDE[piece_id]
    return list(pv.SCORE_CANDIDATES[piece_id][0])


def score_path(pid: str, cat: dict, cache: Path) -> Path:
    from pianolens.data import pianocore

    p = cat[pid]
    if p["source"] == "asap":
        return ROOT / "data" / "raw" / "asap" / p["score"]
    suffix = Path(p["score"]).suffix or ".mxl"
    dst = cache / (re.sub(r"[^A-Za-z0-9]+", "_", pid)[-100:] + suffix)
    dst.parent.mkdir(parents=True, exist_ok=True)
    if not dst.is_file() and not dst.with_suffix(".musicxml").is_file():
        with zipfile.ZipFile(pianocore.DEFAULT_ROOT / pianocore.RAW_ZIP) as z:
            dst.write_bytes(z.read(pianocore.RAW_PREFIX + p["score"]))
    if dst.suffix == ".mxl" and dst.is_file() and not zipfile.is_zipfile(dst):
        dst = dst.rename(dst.with_suffix(".musicxml"))  # a few .mxl files are plain XML
    if not dst.is_file():
        dst = dst.with_suffix(".musicxml")
    return dst


# --------------------------------------------------------------------------- scores


def load_score(pid: str, cat: dict, cache: Path) -> dict:
    """Folded, parts-merged score (DF-09 staves) with BL-19 proxy flags per note and measure."""
    import partitura as pt

    from pianolens.align import load_score_part
    from pianolens.align._adapters import normalise_piano_staves

    shp = _load_script("staff_hand_proxies")
    path = score_path(pid, cat, cache)
    raw = pt.load_score(str(path))
    n_parts = len(raw.parts)
    part = load_score_part(path)
    na = part.note_array(include_grace_notes=True, include_staff=True)
    df = pd.DataFrame({
        "note_id": na["id"].astype(str), "onset": na["onset_quarter"].astype(float),
        "duration": na["duration_quarter"].astype(float), "onset_div": na["onset_div"],
        "pitch": na["pitch"].astype(int), "voice": na["voice"].astype(int),
        "staff": na["staff"].astype(int), "is_grace": na["is_grace"].astype(bool),
    })  # fmt: skip
    fl = shp.note_flags(df[~df["is_grace"]][["onset", "duration", "pitch", "voice", "staff"]]
                        .reset_index(drop=True))  # fmt: skip
    flag_cols = ["cross_voice", "cross_pitch", "cross_pitch_loose", "capacity", "at_risk"]
    for c in flag_cols:
        df[c] = False
        df.loc[~df["is_grace"], c] = fl[c].to_numpy()
    # hand-sync events (BL-19 definition: score onsets where staff 1 and 2 both start a note)
    ng = df[~df["is_grace"] & df["staff"].isin([1, 2])]
    both = ng.groupby("onset")["staff"].nunique()
    df["sync_event"] = df["onset"].isin(both.index[both.to_numpy() == 2]) & ~df["is_grace"]
    # measure of each note (row of part.measures) and its printed label
    ms = part.measures
    starts = np.array([m.start.t for m in ms], dtype=np.int64)
    k = np.clip(np.searchsorted(starts, df["onset_div"].to_numpy(), side="right") - 1, 0, None)
    df["measure_idx"] = k
    df["measure_name"] = [str(ms[i].name) for i in k] if len(ms) else ""
    # engraver hand words: single-part scores only, staff mapped like DF-09 does
    words = []
    if n_parts == 1:
        mapping = normalise_piano_staves(raw.parts[0])
        for w in shp.hand_words(path):
            if w["kind"] not in ("LH", "RH") or w["staff"] is None:
                continue
            st = mapping.get(int(w["staff"]), int(w["staff"]))
            words.append({"score_pid": pid, "text": w["text"], "kind": w["kind"],
                          "measure_name": str(w["measure"]), "staff": st,
                          "contradicts": (w["kind"] == "LH" and st == 1)
                          or (w["kind"] == "RH" and st == 2)})  # fmt: skip
    df["score_pid"] = pid
    return {"pid": pid, "path": str(path), "na": na, "notes": df, "words": words,
            "n_parts": n_parts}  # fmt: skip


# --------------------------------------------------------------------------- stage 1


def align_recording(job: dict) -> dict:
    """Takes and parangonar matches of one recording against ``job['pids']``."""
    warnings.filterwarnings("ignore")
    sys.setrecursionlimit(100_000)
    from pianolens.data import pianovam as pv
    from pianolens.data import session_takes as st
    from pianolens.data.midi_io import performance_from_midi

    cat = {p["piece_id"]: p for p in json.loads(CATALOG.read_text())["pieces"]}
    cache = ART / "scores"
    r = job["row"]
    perf = performance_from_midi(
        r["midi_path"], dataset=pv.DATASET, performance_id=r["performance_id"],
        piece_id=r["piece_id"], performer_id=r["performer_id"], provenance="disklavier")  # fmt: skip
    pna = perf.notes
    cfg = st.LocalTakeConfig()
    pev = st.perf_events(pna["onset_sec"], pna["pitch"], cfg.chord_ms)
    scores = {pid: load_score(pid, cat, cache) for pid in job["pids"]}
    sevs = {pid: st.score_events(s["na"]["onset_div"], s["na"]["pitch"])
            for pid, s in scores.items()}  # fmt: skip
    takes = st.find_local_takes(sevs, pev, cfg)
    trows, mrows = [], []
    for t_i, tk in enumerate(takes):
        s = scores[tk["score"]]
        m, qc = st.match_take(tk, sevs[tk["score"]], pev, s["na"], pna)
        on = pna["onset_sec"]
        trows.append({"record_time": r["record_time"], "take": t_i, "score_pid": tk["score"],
                      "dp": tk["dp"], "ev0": tk["ev0"], "ev1": tk["ev1"], "on0": tk["on0"],
                      "on1": tk["on1"], "n_pairs": tk["n_pairs"], "n_exact": tk["n_exact"],
                      "t0_sec": float(pev.at[tk["ev0"], "t"]),
                      "t1_sec": float(pev.at[tk["ev1"], "t"]), **qc,
                      "null": job["null"]})  # fmt: skip
        if job["null"] or m.empty:
            continue
        notes = s["notes"]
        sub = notes.iloc[m["score_idx"].to_numpy()].reset_index(drop=True)
        sub["perf_idx"] = m["perf_idx"].to_numpy()
        sub["perf_note_id"] = pna["id"][m["perf_idx"].to_numpy()].astype(str)
        sub["perf_onset_sec"] = on[m["perf_idx"].to_numpy()].astype(float)
        sub["perf_pitch"] = pna["pitch"][m["perf_idx"].to_numpy()].astype(int)
        sub["consensus"] = m["consensus"].to_numpy()
        sub["record_time"] = r["record_time"]
        sub["take"] = t_i
        mrows.append(sub)
    out = {"takes": trows, "n_notes": len(pna), "record_time": r["record_time"],
           "null": job["null"]}  # fmt: skip
    if not job["null"]:
        out["matched"] = pd.concat(mrows, ignore_index=True) if mrows else pd.DataFrame()
        out["score_notes"] = {pid: s["notes"] for pid, s in scores.items()}
        out["words"] = [w for s in scores.values() for w in s["words"]]
    return out


def stage_align(workers: int) -> None:
    from pianolens.data import pianovam as pv

    idx = pv.pianovam_index()
    rec = idx[idx["piece_id"].isin(pv.SCORE_CANDIDATES)].sort_values("record_time")
    rows = [{k: (str(v) if k == "midi_path" else v) for k, v in r.items()}
            for r in rec[["record_time", "performance_id", "piece_id", "performer_id",
                          "midi_path", "P1_skill"]].to_dict("records")]  # fmt: skip
    titles = sorted({r["piece_id"] for r in rows})
    jobs = []
    for r in rows:
        pids = candidates(r["piece_id"])
        jobs.append({"row": r, "pids": pids, "null": False})
        # null: the candidates of the title 7 places further in the sorted title list,
        # skipping titles that share a candidate score (a wrong piece, same machinery)
        k = titles.index(r["piece_id"])
        for off in range(7, 7 + len(titles)):
            other = titles[(k + off) % len(titles)]
            wrong = candidates(other)
            if not set(wrong) & set(pids):
                break
        jobs.append({"row": r, "pids": wrong, "null": True, "null_title": other})
    ART.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    takes, null_takes, matched, words, snotes = [], [], [], [], {}
    with ProcessPoolExecutor(workers) as ex:
        futs = {ex.submit(align_recording, j): j for j in jobs}
        for n, f in enumerate(as_completed(futs), 1):
            j = futs[f]
            res = f.result()
            for t in res["takes"]:
                t.update(piece_id=j["row"]["piece_id"], performer_id=j["row"]["performer_id"],
                         skill=j["row"]["P1_skill"], n_notes_session=res["n_notes"],
                         null_title=j.get("null_title", ""))  # fmt: skip
            (null_takes if j["null"] else takes).extend(res["takes"])
            if not j["null"]:
                if not res["matched"].empty:
                    matched.append(res["matched"])
                words.extend(res["words"])
                snotes.update(res["score_notes"])
            log.info("%d/%d %s null=%s takes=%d (%.0f s)", n, len(jobs), j["row"]["record_time"],
                     j["null"], len(res["takes"]), time.time() - t0)  # fmt: skip
    pd.DataFrame(takes).to_parquet(ART / "takes.parquet")
    pd.DataFrame(null_takes).to_parquet(ART / "null_takes.parquet")
    pd.concat(matched, ignore_index=True).to_parquet(ART / "matched.parquet")
    pd.concat(snotes.values(), ignore_index=True).to_parquet(ART / "score_notes.parquet")
    wd = pd.DataFrame(words).drop_duplicates() if words else pd.DataFrame()
    wd.to_parquet(ART / "hand_words.parquet")
    (ART / "align_run.json").write_text(json.dumps({
        "wall_sec": round(time.time() - t0, 1), "n_jobs": len(jobs), "workers": workers}))
    log.info("done in %.0f s", time.time() - t0)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("stage", choices=["align", "score"])
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if a.stage == "align":
        stage_align(a.workers)
    else:
        from score_stage import stage_score  # noqa: PLC0415 - written after the pre-registration

        stage_score()


if __name__ == "__main__":
    main()
