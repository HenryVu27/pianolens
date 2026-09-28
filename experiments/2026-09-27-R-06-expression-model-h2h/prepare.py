"""R-06 step 1 (project env): build the interchange items both model adapters read.

Sets (see README):
  P  PercePiano human segments of Beethoven WoO 80 and Schubert D960 mv2 / mv3 (pieces absent
     from both models' score-conditioned training data); parangonar alignment; plus the
     PercePiano ``Score`` renditions of the same segments as external deadpans.
  A  (n)ASAP performances of the score folders Pianist Transformer held out (its shipped
     test set, 23 folders), minus folders whose piece has another ASAP folder in its training
     split, robust ground-truth alignment only, first 800 score notes.
  V  Vienna 4x22 (sensor, ground-truth alignment).

Per real rendition it writes: the real item, 6 jittered items (pianolens.data.perturb, rate 0:
timing s.d. 10 / 20 / 40 ms, velocity s.d. 4 / 8 / 16) and a synthetic deadpan. Per passage it
writes one score-only generation item. Conditioning: spq_cond / vel_cond = the rendition's own
global seconds-per-quarter and median velocity (generation items: medians over the passage's
human renditions).

    OMP_NUM_THREADS=1 uv run python experiments/2026-09-27-R-06-expression-model-h2h/prepare.py \
        --sets P A V --workers 12
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import time
import zlib
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

from pianolens.data.perturb import MistakeSpec, perturb
from pianolens.models.expression_io import (
    NotePairs,
    deadpan,
    global_seconds_per_quarter,
    matched_pairs,
    time_signature_events,
)

HERE = Path(__file__).resolve().parent
ART = HERE / "artifacts"
SEED = 20260927
JITTERS = {  # name: (timing sd s, velocity sd)
    "jitT10": (0.010, 0.0), "jitT20": (0.020, 0.0), "jitT40": (0.040, 0.0),
    "jitV4": (0.0, 4.0), "jitV8": (0.0, 8.0), "jitV16": (0.0, 16.0),
}
P_WORKS = ("beethoven_woo80", "schubert_d960_mv2", "schubert_d960_mv3")
A_TEST_FOLDERS = [  # Pianist Transformer testset/score/0..22.mid, matched note-for-note to ASAP
    "Bach/Fugue/bwv_854", "Bach/Fugue/bwv_864", "Bach/Italian_concerto", "Bach/Prelude/bwv_885",
    "Beethoven/Piano_Sonatas/1-1", "Beethoven/Piano_Sonatas/2-1",
    "Beethoven/Piano_Sonatas/32-1_no_repeat", "Beethoven/Piano_Sonatas/4-1",
    "Beethoven/Piano_Sonatas/5-1", "Beethoven/Piano_Sonatas/7-1", "Chopin/Etudes_op_25/4",
    "Chopin/Etudes_op_25/8", "Chopin/Sonata_2/2nd", "Chopin/Sonata_3/4th",
    "Haydn/Keyboard_Sonatas/48-2", "Haydn/Keyboard_Sonatas/49-1", "Liszt/Transcendental_Etudes/1",
    "Liszt/Transcendental_Etudes/10", "Mozart/Fantasie_475", "Mozart/Piano_Sonatas/12-2",
    "Mozart/Piano_Sonatas/8-1", "Ravel/Miroirs/3_Une_Barque", "Schumann/Kreisleriana/1",
]
A_MAX_NOTES = 800
P_MIN_MATCH = 0.8

log = logging.getLogger("r06.prepare")


def _slug(s: str) -> str:
    return "".join(c if c.isalnum() or c in "-." else "_" for c in s)


def score_side(score) -> dict:
    """All score notes (dedup by onset, pitch), with the bar grid."""
    n = score.notes
    n = n[np.lexsort((n["pitch"], n["onset_quarter"]))]
    key = np.round(n["onset_quarter"] * 1e6).astype(np.int64) * 128 + n["pitch"]
    _, first = np.unique(key, return_index=True)
    n = n[np.sort(first)]
    origin, ts = time_signature_events(score.measures, score.notes)
    return {"notes": n, "origin": origin, "ts": np.array(ts, dtype=float).reshape(-1, 3)}


def write_item(path: Path, pairs: NotePairs, spq: float, vel: float, origin: float,
               ts: np.ndarray, **extra) -> None:
    np.savez_compressed(
        path, **pairs.to_npz_dict(), score_id=pairs.score_id.astype(str),
        spq_cond=float(spq), vel_cond=float(round(vel)), origin=float(origin), ts=ts,
        **{k: np.asarray(v) for k, v in extra.items()},
    )


def cap_pairs(pairs: NotePairs, max_onset: float | None) -> NotePairs:
    if max_onset is None:
        return pairs
    k = pairs.score_onset_q <= max_onset + 1e-9
    return NotePairs(pairs.score_onset_q[k], pairs.score_dur_q[k], pairs.pitch[k],
                     pairs.perf_onset_sec[k], pairs.perf_dur_sec[k], pairs.velocity[k],
                     pairs.score_id[k], pairs.perf_id[k], pairs.pedal, pairs.meta)


def renditions_for(set_name: str, passage: str, aps: list, is_ext_deadpan: list[bool],
                   max_onset: float | None, out_items: Path) -> list[dict]:
    """Write all items of one passage; return manifest rows."""
    rows = []
    human = [ap for ap, ext in zip(aps, is_ext_deadpan, strict=True) if not ext]
    for ap, ext in zip(aps, is_ext_deadpan, strict=True):
        perf = ap.performance
        ss = score_side(ap.score)
        pairs = cap_pairs(matched_pairs(ap.score.notes, perf.notes, ap.alignment.pairs,
                                        perf.pedal), max_onset)
        n_score_region = int(np.sum(ss["notes"]["onset_quarter"] <= (max_onset or np.inf) + 1e-9))
        match_share = len(pairs) / max(1, n_score_region)
        base = {"set": set_name, "passage": passage, "piece_id": perf.piece_id,
                "performer_id": perf.performer_id, "performance_id": perf.performance_id,
                "n_notes": len(pairs), "match_share": match_share,
                "ground_truth_alignment": bool(ap.alignment.ground_truth)}
        if set_name == "P" and match_share < P_MIN_MATCH:
            rows.append({**base, "item": None, "kind": "real" if not ext else "ext_deadpan",
                         "excluded": "match_share"})
            continue
        if len(pairs) < 16:
            rows.append({**base, "item": None, "kind": "real", "excluded": "too_few_notes"})
            continue
        spq = global_seconds_per_quarter(pairs.score_onset_q, pairs.perf_onset_sec)
        vel = float(np.median(pairs.velocity))
        stem = _slug(perf.performance_id)
        kinds = [("ext_deadpan" if ext else "real", pairs)]
        if not ext:
            for j, (name, (tsd, vsd)) in enumerate(JITTERS.items()):
                spec = MistakeSpec(rate=0.0, timing_jitter_sd_sec=tsd, velocity_jitter_sd=vsd)
                seed = SEED + 1000 * j + (zlib.crc32(stem.encode()) % 997)
                p2, _ = perturb(perf, ap.alignment, spec, seed=seed)
                pp = cap_pairs(matched_pairs(ap.score.notes, p2.notes, ap.alignment.pairs,
                                             p2.pedal), max_onset)
                kinds.append((name, pp))
            kinds.append(("deadpan", deadpan(pairs, spq, vel)))
        for kind, pp in kinds:
            item = f"{stem}__{kind}"
            write_item(out_items / f"{item}.npz", pp, spq, vel, ss["origin"], ss["ts"])
            rows.append({**base, "item": item, "kind": kind, "spq_cond": spq, "vel_cond": vel,
                         "excluded": ""})
    # generation item: the passage's score, conditioned on human medians
    hum = [r for r in rows if r["kind"] == "real" and r["item"]]
    if hum and human:
        ss = score_side(human[0].score)
        n = ss["notes"]
        if max_onset is not None:
            n = n[n["onset_quarter"] <= max_onset + 1e-9]
        z = np.zeros(len(n))
        gp = NotePairs(n["onset_quarter"].astype(float), n["duration_quarter"].astype(float),
                       n["pitch"].astype(int), z, z, z.astype(int), n["id"].astype(str),
                       n["id"].astype(str))
        spq = float(np.median([r["spq_cond"] for r in hum]))
        vel = float(np.median([r["vel_cond"] for r in hum]))
        gdir = out_items.parent.parent / "gen_items" / set_name
        gdir.mkdir(parents=True, exist_ok=True)
        write_item(gdir / f"{_slug(passage)}.npz", gp, spq, vel, ss["origin"], ss["ts"])
    return rows


# ------------------------------------------------------------------------------- sets

def _p_passage(args):
    passage, rows = args
    from pianolens.align import align_performance
    from pianolens.data.percepiano import load_percepiano_performance, load_percepiano_score

    out_items = ART / "items" / "P"
    aps, ext = [], []
    score = load_percepiano_score(rows.iloc[0])
    for _, row in rows.iterrows():
        try:
            perf = load_percepiano_performance(row)
            ap = align_performance(score, perf)
        except Exception as e:  # noqa: BLE001
            log.warning("P align failed %s: %r", row["performance_id"], e)
            continue
        is_score = row["player"].startswith("Score")
        aps.append(ap)
        ext.append(is_score)
    return renditions_for("P", passage, aps, ext, None, out_items)


def build_P(workers: int) -> list[dict]:
    from pianolens.data.percepiano import percepiano_index

    idx = percepiano_index()
    idx = idx[idx["piece_id"].isin(P_WORKS)].copy()
    idx["passage"] = idx["score_xml"]
    jobs = list(idx.groupby("passage"))
    (ART / "items" / "P").mkdir(parents=True, exist_ok=True)
    rows = []
    with ProcessPoolExecutor(workers) as ex:
        for r in ex.map(_p_passage, jobs):
            rows.extend(r)
    return rows


def _a_folder(folder: str) -> list[dict]:
    from pianolens.data.asap import asap_index, iter_asap

    md = asap_index()
    md = md[(md["folder"] == folder) & (md["robust_note_alignment"] == 1)]
    aps = [ap for ap in iter_asap(index=md) if ap.alignment is not None]
    if not aps:
        return []
    ss = score_side(aps[0].score)
    on = ss["notes"]["onset_quarter"]
    max_onset = float(on[min(len(on), A_MAX_NOTES) - 1])
    return renditions_for("A", folder, aps, [False] * len(aps), max_onset,
                          ART / "items" / "A")


def build_A(workers: int) -> tuple[list[dict], pd.DataFrame]:
    from pianolens.data.asap import asap_index

    md = asap_index()
    keep, overlap = [], []
    for f in A_TEST_FOLDERS:
        pid = md.loc[md["folder"] == f, "piece_id"].iloc[0]
        others = sorted(set(md.loc[(md["piece_id"] == pid)
                                   & ~md["folder"].isin(A_TEST_FOLDERS), "folder"]))
        n_robust = int(((md["folder"] == f) & (md["robust_note_alignment"] == 1)).sum())
        use = not others and n_robust > 0
        overlap.append({"folder": f, "piece_id": pid, "other_folders_in_pt_train": ";".join(others),
                        "n_robust": n_robust, "used": use})
        if use:
            keep.append(f)
    (ART / "items" / "A").mkdir(parents=True, exist_ok=True)
    rows = []
    with ProcessPoolExecutor(workers) as ex:
        for r in ex.map(_a_folder, keep):
            rows.extend(r)
    return rows, pd.DataFrame(overlap)


def build_V() -> list[dict]:
    from pianolens.data.vienna4x22 import iter_aligned

    by = {}
    for ap in iter_aligned():
        by.setdefault(ap.score.score_id, []).append(ap)
    (ART / "items" / "V").mkdir(parents=True, exist_ok=True)
    rows = []
    for sid, aps in by.items():
        rows.extend(renditions_for("V", sid, aps, [False] * len(aps), None, ART / "items" / "V"))
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sets", nargs="+", default=["P", "A", "V"])
    ap.add_argument("--workers", type=int, default=12)
    a = ap.parse_args()
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    logging.basicConfig(level=logging.WARNING)
    t0 = time.time()
    rows = []
    for s in a.sets:
        t1 = time.time()
        if s == "P":
            rows += build_P(a.workers)
        elif s == "A":
            r, ov = build_A(a.workers)
            rows += r
            ov.to_csv(ART / "A_overlap.csv", index=False)
        elif s == "V":
            rows += build_V()
        print(s, "done", round(time.time() - t1, 1), "s", flush=True)
    man = pd.DataFrame(rows)
    old = ART / "manifest.parquet"
    if old.exists():
        prev = pd.read_parquet(old)
        man = pd.concat([prev[~prev["set"].isin(a.sets)], man], ignore_index=True)
    man.to_parquet(old)
    (ART / "prepare_meta.json").write_text(json.dumps(
        {"sets": a.sets, "seconds": time.time() - t0, "seed": SEED, "jitters": JITTERS,
         "a_max_notes": A_MAX_NOTES, "p_min_match": P_MIN_MATCH}, indent=1))
    print(man.groupby(["set", "kind"]).size())


if __name__ == "__main__":
    main()
