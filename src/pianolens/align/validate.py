"""Validate :func:`pianolens.align.align` against (n)ASAP ground-truth note alignments.

Run:  ``uv run python -m pianolens.align.validate [--asap data/raw/asap] [--workers 10]``

For every performance in ``metadata.csv`` that has a match file, this aligns the MusicXML score
to the performance MIDI with automatic repeat selection, scores it against the match file with
:func:`pianolens.align.evaluate.evaluate_alignment`, and writes one CSV row per performance plus
a per-composer summary.

For scores with more than one repeat path it also identifies the ground-truth variant (the path
whose note ids best cover the ground-truth score ids) and, if the automatic choice differs,
re-aligns with the ground-truth variant ("oracle") so repeat errors and matching errors can be
told apart.

Caveat: (n)ASAP note alignments were themselves produced semi-automatically (Peter et al.,
TISMIR 2023) with parangonar-family matchers; ``robust_note_alignment == 1`` marks the ones the
authors consider reliable. Agreement with them is agreement with a strong reference, not with
hand-checked truth. Summaries are reported for all rows and for robust rows only.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import time
import warnings
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import partitura as pt

from pianolens.align._adapters import to_part
from pianolens.align.core import _variants_with_paths, align, unfold_variant
from pianolens.align.evaluate import evaluate_alignment


def variant_note_ids(part: Any, path: Any) -> set[str]:
    """Unfolded note ids (``<id>-<k>``) of a repeat path, computed without building the part.

    Mirrors partitura's ``update_note_ids_after_unfolding``: the k-th time a note is traversed
    it gets suffix ``-k``.
    """
    segments = pt.score.get_segments(part)
    notes = [(n.start.t, n.id) for n in part.notes_tied]
    seen: Counter[str] = Counter()
    out: set[str] = set()
    for sid in path.path:
        s = segments[sid]
        for t, nid in notes:
            if s.start.t <= t < s.end.t:
                seen[nid] += 1
                out.add(f"{nid}-{seen[nid]}")
    return out


def ground_truth_variant(part: Any, gt_score_ids: set[str]) -> tuple[str, float]:
    """The repeat path whose ids best match the ground truth (Jaccard), and that Jaccard."""
    best, best_j = "", -1.0
    for v, _, p in _variants_with_paths(part):
        ids = variant_note_ids(part, p)
        j = len(ids & gt_score_ids) / max(1, len(ids | gt_score_ids))
        if j > best_j:
            best, best_j = v, j
    return best, best_j


@lru_cache(maxsize=4)
def _load_part(score_path: str) -> tuple[Any, float]:
    t0 = time.perf_counter()
    part = to_part(pt.load_score(score_path))
    return part, time.perf_counter() - t0


def load_ground_truth(asap_root: Path, row: dict[str, str]) -> list[dict[str, str]]:
    """(n)ASAP ground truth for one metadata row: the note_alignment TSV, else the match file.

    The TSV path is derived from the MIDI name because the metadata column is mangled for the
    Schubert D.899 rows. The TSV and the match file carry the same alignment where both are
    complete, but some match files are empty stubs (Debussy/Pour_le_Piano/1/MunA12M.match).
    """
    midi = asap_root / row["midi_performance"]
    tsv = midi.with_name(f"{midi.stem}_note_alignments") / "note_alignment.tsv"
    if tsv.is_file():
        return pt.io.importparangonada.load_alignment_from_ASAP(str(tsv))
    return pt.load_match(str(asap_root / row["match_file"]))[1]


def _eval_row(
    asap_root: str,
    r: dict[str, str],
    nakamura_dir: str | None = None,
) -> dict[str, Any]:
    warnings.filterwarnings("ignore")
    logging.disable(logging.WARNING)
    root = Path(asap_root)
    try:
        part, score_load_s = _load_part(str(root / r["folder"] / "xml_score.musicxml"))
        perf = pt.load_performance_midi(str(root / r["midi_performance"]))
        gt = load_ground_truth(root, r)
        n_variants = len(_variants_with_paths(part))
        t1 = time.perf_counter()
        res = align(part, perf)
        align_s = time.perf_counter() - t1
        scores = evaluate_alignment(res, gt).as_flat_dict()
        gt_ids = {str(a["score_id"]) for a in gt if "score_id" in a}
        row: dict[str, Any] = {
            **_base(r),
            "n_score_notes": len(res.score_note_array),
            "n_perf_notes": len(res.performance_note_array),
            "n_gt_match": sum(1 for a in gt if a["label"] == "match"),
            "n_variants": n_variants,
            "variant": res.variant,
            "n_candidates": len(res.candidates),
            "gt_ids_missing_from_score": len(gt_ids - set(res.score_note_array["id"])),
            "score_load_s": round(score_load_s, 3),
            "align_s": round(align_s, 3),
            **scores,
            "error": "",
        }
        if n_variants > 1:
            gt_v, jac = ground_truth_variant(part, gt_ids)
            row["gt_variant"], row["gt_variant_jaccard"] = gt_v, round(jac, 4)
            row["variant_correct"] = gt_v == res.variant
            row["candidate_ratios"] = ";".join(f"{k}:{v:.4f}" for k, v in res.candidates.items())
            if gt_v != res.variant:
                oracle = align(part, perf, repeats=gt_v)
                row["oracle_match_f1"] = evaluate_alignment(oracle, gt).match.f1
                row["oracle_ratio"] = round(oracle.candidates[gt_v], 4)
        elif nakamura_dir:
            from pianolens.align.nakamura import nakamura_align

            try:
                t2 = time.perf_counter()
                nak = nakamura_align(
                    root / r["folder"] / "xml_score.musicxml",
                    root / r["midi_performance"],
                    nakamura_dir,
                    part=part,
                )
                row["nakamura_s"] = round(time.perf_counter() - t2, 3)
                ns = evaluate_alignment(nak, gt)
                row["nakamura_match_f1"] = ns.match.f1
                row["nakamura_perf_note_accuracy"] = ns.perf_note_accuracy
            except Exception as e:  # noqa: BLE001
                row["nakamura_error"] = repr(e)[:200]
        return row
    except Exception as e:  # noqa: BLE001 - one bad file must not stop the run
        return _error_row(r, repr(e))


def beat_consistency(
    part: Any, alignment: Any, perf_na: np.ndarray, annotation: dict[str, Any], tol: float = 0.25
) -> tuple[float, int]:
    """Independent check of an alignment against ASAP's manual downbeat annotations.

    For a score with a single repeat path, each matched note belongs to a score measure; ASAP's
    ``downbeats_score_map`` gives that measure's performed downbeat, so the note's performed
    onset should fall between that downbeat and the next one (``tol`` seconds slack). Returns
    (fraction of matched notes that do, number of matched notes checked). Returns (nan, 0) when
    the annotation's score and performance downbeats are not one-to-one.
    """
    db = np.asarray(annotation["performance_downbeats"], dtype=float)
    dmap = annotation["downbeats_score_map"]
    if len(dmap) != len(db):
        return float("nan"), 0
    span: dict[int, tuple[float, float]] = {}
    for k, m in enumerate(dmap):
        end = db[k + 1] if k + 1 < len(db) else np.inf
        for mm in str(m).split("-"):
            span[int(float(mm))] = (db[k], end)
    upart = unfold_variant(part)
    starts = np.array([m.start.t for m in upart.measures])
    onset_t = {n.id: n.start.t for n in upart.notes_tied}
    perf_on = dict(zip(perf_na["id"].tolist(), perf_na["onset_sec"].tolist(), strict=True))
    ok = total = 0
    for a in getattr(alignment, "alignment", alignment):
        if a["label"] != "match" or a["score_id"] not in onset_t:
            continue
        i = int(np.searchsorted(starts, onset_t[a["score_id"]], side="right") - 1)
        if i not in span:
            continue
        total += 1
        lo, hi = span[i]
        ok += lo - tol <= perf_on[a["performance_id"]] <= hi + tol
    return (ok / total if total else float("nan")), total


def _beat_row(asap_root: str, rec: dict[str, Any], midi_rel: str) -> dict[str, Any]:
    warnings.filterwarnings("ignore")
    logging.disable(logging.WARNING)
    root = Path(asap_root)
    ann = _annotations(asap_root)[midi_rel]
    part, _ = _load_part(str(root / rec["folder"] / "xml_score.musicxml"))
    perf = pt.load_performance_midi(str(root / midi_rel))
    gt = load_ground_truth(root, {"midi_performance": midi_rel, "match_file": ""})
    ours = align(part, perf)
    g, ng = beat_consistency(part, gt, ours.performance_note_array, ann)
    o, no = beat_consistency(part, ours, ours.performance_note_array, ann)
    return {"folder": rec["folder"], "performance": rec["performance"],
            "gt_beat_consistency": g, "gt_beat_n": ng,
            "ours_beat_consistency": o, "ours_beat_n": no}  # fmt: skip


@lru_cache(maxsize=1)
def _annotations(asap_root: str) -> dict[str, Any]:
    with open(Path(asap_root) / "asap_annotations.json") as f:
        return json.load(f)


def beat_check(asap_root: str, out: Path, below: float, workers: int) -> pd.DataFrame:
    """Add annotation flags to ``per_performance.csv`` and, for single-path rows with match F1
    below ``below``, the beat consistency of the ground truth and of our alignment."""
    df = pd.read_csv(out / "per_performance.csv")
    ann = _annotations(asap_root)
    with open(Path(asap_root) / "metadata.csv", newline="") as f:
        midi_of = {(r["folder"], Path(r["midi_performance"]).stem): r["midi_performance"]
                   for r in csv.DictReader(f)}  # fmt: skip
    df["beats_aligned"] = [
        bool(ann.get(midi_of.get((fo, pe), ""), {}).get("score_and_performance_aligned", False))
        for fo, pe in zip(df["folder"], df["performance"], strict=True)
    ]
    todo = df[(df["match_f1"] < below) & (df["n_variants"] == 1)]
    rows = []
    with ProcessPoolExecutor(workers) as ex:
        futs = [
            ex.submit(_beat_row, asap_root, rec, midi_of[(rec["folder"], rec["performance"])])
            for rec in todo.to_dict("records")
        ]
        for fut in as_completed(futs):
            try:
                rows.append(fut.result())
            except Exception as e:  # noqa: BLE001
                print("beat check failed:", repr(e)[:200])
    df = df.drop(columns=[c for c in df.columns if "beat_consistency" in c or "beat_n" in c])
    if rows:
        df = df.merge(pd.DataFrame(rows), on=["folder", "performance"], how="left")
    df.to_csv(out / "per_performance.csv", index=False)
    return df


def _base(r: dict[str, str]) -> dict[str, Any]:
    return {
        "composer": r["composer"],
        "title": r["title"],
        "folder": r["folder"],
        "performance": Path(r["midi_performance"]).stem,
        "robust": r["robust_note_alignment"] == "1.0",
    }


def _error_row(r: dict[str, str], msg: str) -> dict[str, Any]:
    return {**_base(r), "error": msg[:300]}


def summarize(df: pd.DataFrame) -> pd.DataFrame:
    """Per-composer table: counts, mean match F1, insertion/deletion F1, runtime."""
    ok = df[df["error"].fillna("") == ""]

    def agg(g: pd.DataFrame) -> pd.Series:
        return pd.Series(
            {
                "n_perf": len(g),
                "n_robust": int(g["robust"].sum()),
                "match_f1_mean": g["match_f1"].mean(),
                "match_f1_median": g["match_f1"].median(),
                "match_f1_robust": g.loc[g["robust"], "match_f1"].mean(),
                "match_f1_beats_aligned": (
                    g.loc[g["beats_aligned"].astype(bool), "match_f1"].mean()
                    if "beats_aligned" in g
                    else float("nan")
                ),
                "match_f1_pooled": _pooled(g),
                "ins_f1_mean": g["insertion_f1"].mean(),
                "del_f1_mean": g["deletion_f1"].mean(),
                "perf_note_acc": g["perf_note_accuracy"].mean(),
                "align_s_median": g["align_s"].median(),
                "align_s_max": g["align_s"].max(),
            }
        )

    per = ok.groupby("composer").apply(agg, include_groups=False)
    per.loc["ALL"] = agg(ok)
    return per


def _pooled(g: pd.DataFrame) -> float:
    """Match F1 pooled over notes (micro average) instead of over performances."""
    c, p, t = g["match_n_correct"].sum(), g["match_n_pred"].sum(), g["match_n_true"].sum()
    if p == 0 or t == 0:
        return float("nan")
    prec, rec = c / p, c / t
    return 2 * prec * rec / (prec + rec) if prec + rec else 0.0


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--asap", default="data/raw/asap")
    ap.add_argument("--out", default="data/interim/alignment_validation")
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--per-composer", type=int, default=0, help="sample N per composer (0=all)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument(
        "--nakamura",
        default=None,
        help="Nakamura AlignmentTool folder; cross-check single-path scores with it",
    )
    ap.add_argument(
        "--beat-check-below",
        type=float,
        default=None,
        help="skip aligning; annotate an existing per_performance.csv with ASAP beat flags and "
        "check GT vs ours against downbeats for rows with match F1 below this",
    )
    args = ap.parse_args(argv)
    pd.set_option("display.width", 200)

    if args.beat_check_below is not None:
        out = Path(args.out)
        df = beat_check(args.asap, out, args.beat_check_below, args.workers)
        summ = summarize(df)
        summ.to_csv(out / "per_composer.csv")
        print(summ.round(4).to_string())
        return

    root = Path(args.asap)
    with open(root / "metadata.csv", newline="") as f:
        rows = [r for r in csv.DictReader(f) if r["match_file"] or r["note_alignments"]]
    if args.per_composer:
        rng = np.random.default_rng(args.seed)
        by_c: dict[str, list] = defaultdict(list)
        for r in rows:
            by_c[r["composer"]].append(r)
        rows = []
        for c in sorted(by_c):
            idx = rng.permutation(len(by_c[c]))[: args.per_composer]
            rows += [by_c[c][i] for i in sorted(idx)]

    # biggest scores first so the slowest work starts early
    rows.sort(key=lambda r: -(root / r["folder"] / "xml_score.musicxml").stat().st_size)

    results: list[dict[str, Any]] = []
    t0 = time.perf_counter()
    with ProcessPoolExecutor(args.workers) as ex:
        futs = [
            ex.submit(_eval_row, str(root), r, args.nakamura)
            for r in rows
        ]
        for i, fut in enumerate(as_completed(futs), 1):
            results.append(fut.result())
            if i % 50 == 0 or i == len(futs):
                el = time.perf_counter() - t0
                print(f"{i}/{len(futs)} performances, {el:.0f}s", flush=True)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(results).sort_values(["composer", "folder", "performance"])
    df.to_csv(out / "per_performance.csv", index=False)
    summ = summarize(df)
    summ.to_csv(out / "per_composer.csv")
    pd.set_option("display.width", 200)
    print(summ.round(4).to_string())
    n_err = int((df["error"].fillna("") != "").sum())
    print(f"errors: {n_err}; wall {time.perf_counter() - t0:.0f}s")


if __name__ == "__main__":
    main()
