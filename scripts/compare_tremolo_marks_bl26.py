"""BL-26 follow-up: copy the tremolo mark of an unexpanded tremolo to every chord note, or not?

Run: ``OMP_NUM_THREADS=1 uv run python scripts/compare_tremolo_marks_bl26.py [--workers 10]
[--from-cache]``

``align.tremolo.TREMOLO_MARK_CHORD`` True (BL-26 convention: every note of an unmeasured or 32nd+
tremolo chord gets the ``"tremolo"`` mark) vs False (the mark stays where the score wrote it,
usually the chord's first note). Marked notes go through parangonar's ornament step and the
legacy ornament whitelist (``.claude/rules/features.md``), so the setting changes matches.

* ``asap``: every ASAP performance with an nASAP reference alignment whose score has at least
  one note that gains the mark by copying. Each is aligned under both settings and labelled with
  the current ``correctness`` defaults. Switching from copy on to copy off: a correct pair lost is
  a break when it is a reference match, a repair when it is not; a correct pair gained is a
  repair when it is a reference match. Also the change in tolerated (``ornament``) and extra
  performed notes.
* ``counts``: notes that gain the mark by copying in the A-01 floor scores and the DF-13 dev /
  held-out scores, and for the pieces with any, the label changes over their transcriptions.

Outputs (gitignored): ``data/interim/bl26_marks/``.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import pickle
import sys
import warnings
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "data" / "interim" / "bl26_marks"
HENRY = REPO / "data" / "interim" / "henry_takes"


def _mod(name: str, file: str):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, REPO / "scripts" / file)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


def _quiet() -> None:
    import logging

    warnings.filterwarnings("ignore")
    logging.disable(logging.WARNING)


def _set(copy: bool) -> None:
    import pianolens.align.tremolo as tr

    tr.TREMOLO_MARK_CHORD = copy


def gained_marks(path: str) -> int:
    """Notes of the loaded score that carry the tremolo mark only because of copying."""
    _quiet()
    from pianolens.align._adapters import to_part

    ids = {}
    for copy in (True, False):
        _set(copy)
        part = to_part(Path(path))
        ids[copy] = {n.id for n in part.notes_tied if "tremolo" in (n.ornaments or [])}
    _set(True)
    return len(ids[True] - ids[False])


def _label(ap) -> object:
    from pianolens.features.correctness import correctness

    return correctness(ap)


def _pairs(cr) -> set[tuple[str, str]]:
    sn, pn = cr.score_notes, cr.notes
    a = sn[sn["label"] == "correct"]
    b = pn[pn["label"] == "correct"]
    return ({(str(x), str(y)) for x, y in zip(a["score_id"], a["performance_id"], strict=True)}
            | {(str(x), str(y)) for x, y in zip(b["score_id"], b["performance_id"],
                                                strict=True)})  # fmt: skip


def asap_one(perf_id: str) -> dict:
    _quiet()
    from pianolens.align import align_performance
    from pianolens.data import asap

    row = asap.asap_index().set_index("performance_id", drop=False).loc[perf_id]
    sc, perf = asap.load_asap_score(row), asap.load_asap_performance(row)
    crs = {}
    for copy in (True, False):
        _set(copy)
        crs[copy] = _label(align_performance(sc, perf))
    _set(True)
    gal = asap.load_asap_alignment(row)
    gt = {(str(s), str(p)) for lb, s, p in gal.pairs.tolist() if lb == "match"}
    on, off = _pairs(crs[True]), _pairs(crs[False])
    out = Counter()
    for pr in on - off:
        out["lost_in_gt (break)" if pr in gt else "lost_not_gt (repair)"] += 1
    for pr in off - on:
        out["gained_in_gt (repair)" if pr in gt else "gained_not_gt (break)"] += 1
    for copy, k in ((True, "on"), (False, "off")):
        s = crs[copy].summary
        for c in ("n_correct", "n_missed", "n_wrong_pitch", "n_extra", "n_ornament",
                  "n_duplicate_matches_resolved"):
            out[f"{k}:{c}"] = int(s[c])
    return {"performance_id": perf_id, "piece_id": row["piece_id"],
            "suspect": bool(crs[True].summary["alignment_suspect"]), "counts": dict(out)}


def job_one(job: dict) -> dict:
    """A PianoCoRe transcription (DF-13 / floor job dict): label changes copy on -> off."""
    _quiet()
    from pianolens.align import align_performance

    labs = {}
    for copy in (True, False):
        # the score file lives in a temporary folder that _load deletes, so the loaded part is
        # what align uses: load it under each setting
        _set(copy)
        sc, perf = _mod("bl18b", "calibrate_strong_tier_bl18b.py")._load(job)
        cr = _label(align_performance(sc, perf))
        labs[copy] = cr
    _set(True)
    a = labs[True].score_notes.set_index("score_id")["label"]
    b = labs[False].score_notes.set_index("score_id")["label"]
    common = a.index.intersection(b.index)
    out = {"id": job["id"], "piece": job["piece"], "family": job["family"],
           "n_score_labels_changed": int((a[common] != b[common]).sum())}
    for copy, k in ((True, "on"), (False, "off")):
        s = labs[copy].summary
        for c in ("n_correct", "n_missed", "n_wrong_pitch", "n_extra", "n_ornament"):
            out[f"{k}:{c}"] = int(s[c])
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--from-cache", action="store_true")
    args = ap.parse_args()
    _quiet()
    OUT.mkdir(parents=True, exist_ok=True)
    cache = OUT / "rows.pkl"
    if args.from_cache:
        blob = pickle.loads(cache.read_bytes())
    else:
        import tempfile
        import zipfile

        from pianolens.data import asap
        from pianolens.data.pianocore import DEFAULT_ROOT, RAW_PREFIX, RAW_ZIP

        df13 = _mod("df13", "eval_pairing_window_df13.py")
        aidx = asap.asap_index()
        scores = sorted(set(aidx["xml_score"].astype(str)))
        jobs = df13.dev_jobs() + df13.heldout_jobs()[0]
        pc_scores = sorted({j["score"] for j in jobs})
        meta = json.loads((HENRY / "scores" / "scores.json").read_text())
        henry = {k: str(HENRY / "scores" / f"{k}_score.mxl") for k in meta}
        td = Path(tempfile.mkdtemp(prefix="bl26marks_"))
        pc_paths = {}
        with zipfile.ZipFile(DEFAULT_ROOT / RAW_ZIP) as z:
            for i, s in enumerate(pc_scores):
                p = td / f"{i}_{Path(s).name}"
                p.write_bytes(z.read(RAW_PREFIX + s))
                pc_paths[s] = str(p)
        gained: dict[str, int] = {}
        with ProcessPoolExecutor(args.workers) as ex:
            paths = {**{f"asap:{s}": str(Path(asap.DEFAULT_ROOT) / s) for s in scores},
                     **{f"pc:{s}": p for s, p in pc_paths.items()},
                     **{f"henry:{k}": p for k, p in henry.items()}}
            futs = {ex.submit(gained_marks, p): k for k, p in paths.items()}
            for fu in as_completed(futs):
                try:
                    gained[futs[fu]] = fu.result()
                except Exception as e:  # noqa: BLE001
                    gained[futs[fu]] = -1
                    print("score failed", futs[fu], repr(e)[:150], flush=True)
            hit = {s for s in scores if gained.get(f"asap:{s}", 0) > 0}
            perfs = [str(r["performance_id"]) for _, r in aidx.iterrows()
                     if str(r["xml_score"]) in hit and asap.asap_alignment_path(r).is_file()]
            pc_hit = {s for s in pc_scores if gained.get(f"pc:{s}", 0) > 0}
            pjobs = [j for j in jobs if j["score"] in pc_hit]
            print(len(hit), "ASAP scores,", len(perfs), "performances;", len(pc_hit),
                  "PianoCoRe scores,", len(pjobs), "transcriptions", flush=True)
            rows, jrows, failed = [], [], []
            futs = {ex.submit(asap_one, p): ("asap", p) for p in perfs}
            futs.update({ex.submit(job_one, j): ("job", j["id"]) for j in pjobs})
            for fu in as_completed(futs):
                kind, k = futs[fu]
                try:
                    (rows if kind == "asap" else jrows).append(fu.result())
                except Exception as e:  # noqa: BLE001
                    failed.append((kind, k, repr(e)[:200]))
        blob = {"gained": gained, "asap": rows, "jobs": jrows, "failed": failed,
                "henry_scores": list(henry)}
        cache.write_bytes(pickle.dumps(blob))
    tot = Counter()
    for r in blob["asap"]:
        if not r["suspect"]:
            tot.update(r["counts"])
    g = blob["gained"]
    summ = {"asap_scores_with_gained_marks": {k: v for k, v in g.items()
                                              if k.startswith("asap:") and v},
            "pianocore_scores_with_gained_marks": {k: v for k, v in g.items()
                                                   if k.startswith("pc:") and v},
            "henry_scores_gained": {k: v for k, v in g.items() if k.startswith("henry:")},
            "n_asap_performances": len(blob["asap"]),
            "n_asap_suspect": sum(r["suspect"] for r in blob["asap"]),
            "asap_totals": dict(tot), "failed": blob["failed"]}
    jt = Counter()
    for r in blob["jobs"]:
        jt.update({k: v for k, v in r.items() if isinstance(v, int)})
    summ["pianocore_job_totals"] = dict(jt)
    summ["pianocore_jobs_by_piece"] = dict(Counter(r["piece"] for r in blob["jobs"]))
    (OUT / "summary.json").write_text(json.dumps(summ, indent=1, default=float))
    print(json.dumps(summ, indent=1, default=float))


if __name__ == "__main__":
    main()
