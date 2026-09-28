"""D-10: tier A + tier B features of MAJEPPA performances, by expertise level.

    uv run python scripts/build_skill_control_d10.py [--workers 10] [--limit-scores N]

Selection (DECISIONS 2026-09-27, F-05 follow-ups): performances with a score and
``score_coverage >= 0.85``, of scores that have performances in at least two skill groups
(beginner = child/adult beginner, intermediate = adult intermediate, advanced = child
professional, piano teacher, virtuoso). One worker per score:

1. ``align_performance`` (our aligner; MAJEPPA's DTW path is not note-level), then
   ``majeppa.with_track_staff`` (staff 1/2 from the score MIDI's two tracks, for hand sync);
2. F-02 ``correctness``, F-03 ``tempo_model``;
3. F-04 ``control_features``. Timing-noise references are the *advanced* performances of the
   same score whose alignment is trusted (match ratio >= 0.8, the F-01 rule; expert
   consensus, leave-one-out; at least 3). A second consensus from all other
   performances of the score is reported as ``allref_*`` (sensitivity). Where coverage is
   below 0.5, ``timing_noise_best_*`` falls back to ``jitter_nometric_*``.

Writes ``data/interim/skill_control_d10/majeppa_features.csv`` (one row per performance) and
``failures.csv``. Analysis: ``scripts/analyze_skill_control_d10.py``.
"""

from __future__ import annotations

import argparse
import time
import warnings
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parents[1] / "data" / "interim" / "skill_control_d10"
COVERAGE_MIN = 0.85
GROUP = {
    "child_beginner": "beginner", "adult_beginner": "beginner",
    "adult_intermediate": "intermediate",
    "child_professional": "advanced", "piano_teacher": "advanced", "virtuoso": "advanced",
}  # fmt: skip


def select(md: pd.DataFrame) -> pd.DataFrame:
    c = md[(md["score_coverage"] >= COVERAGE_MIN) & md["score_id"].notna()].copy()
    c["skill_group"] = c["expertise_level"].map(GROUP)
    ng = c.groupby("score_id")["skill_group"].nunique()
    return c[c["score_id"].isin(ng[ng >= 2].index)]


def _num(v):
    if isinstance(v, (bool, np.bool_)):
        return bool(v)
    if isinstance(v, (int, float, np.integer, np.floating)):
        return float(v)
    return v


def run_score(score_id: str, rows: list[dict]) -> tuple[list[dict], list[tuple[str, str]]]:
    warnings.filterwarnings("ignore")
    import logging

    logging.disable(logging.WARNING)
    from pianolens.align import align_performance
    from pianolens.data import majeppa
    from pianolens.data.midi_io import performance_from_midi, score_from_midi
    from pianolens.data.types import PerformerId
    from pianolens.features.control import control_features, reference_residuals, timing_noise
    from pianolens.features.correctness import correctness
    from pianolens.features.tempo import tempo_model

    root = majeppa.DEFAULT_ROOT
    fails: list[tuple[str, str]] = []
    try:
        score = score_from_midi(root / "extracted" / "score" / f"{score_id}.mid",
                                score_id=f"majeppa:{score_id}", piece_id=rows[0]["piece_id"])
    except Exception as e:  # noqa: BLE001
        return [], [(score_id, f"score: {e!r}")]
    done = []
    for r in rows:
        pid = r["performance_id"]
        try:
            t0 = time.time()
            perf = performance_from_midi(
                root / "extracted" / "performance" / f"{pid}.mid", dataset="majeppa",
                performance_id=f"majeppa:{pid}", piece_id=r["piece_id"],
                performer_id=PerformerId(f"majeppa:recording/{r['recording_id']}"),
                provenance="transcribed")  # fmt: skip
            ap = align_performance(score, perf)
            ap, staff_counts = majeppa.prepare_aligned(ap, score_id)
            cr = correctness(ap)
            tc = tempo_model(ap)
            done.append((r, ap, cr, tc, staff_counts, time.time() - t0))
        except Exception as e:  # noqa: BLE001
            fails.append((pid, repr(e)))
    ok = [d for d in done if not d[2].summary["alignment_suspect"]]
    refs_adv = {d[1].performance.performance_id: reference_residuals(d[3])
                for d in ok if d[0]["skill_group"] == "advanced"}  # fmt: skip
    refs_all = {d[1].performance.performance_id: reference_residuals(d[3]) for d in ok}
    sq = score.notes["onset_quarter"].astype(float)
    offgrid = float((np.abs(sq * 48 - np.round(sq * 48)) > 0.05).mean())
    out = []
    for r, ap, cr, tc, staff_counts, dt in done:
        try:
            res = control_features(ap, tc, references=refs_adv)
            _, s_all = timing_noise(tc, refs_all, leave_out=ap.performance.performance_id)
            pn = ap.performance.notes
            m = tc.positions
            span = float(pn["onset_sec"].max() - pn["onset_sec"].min()) if len(pn) > 1 else np.nan
            row = {
                **{k: r[k] for k in ("performance_id", "recording_id", "score_id", "piece_id",
                                     "composer", "piece_title", "expertise_level",
                                     "skill_group", "recording_type", "score_coverage",
                                     "alignment_cost")},
                "n_refs_adv_available": len(refs_adv)
                - (ap.performance.performance_id in refs_adv),
                "score_offgrid_share": offgrid,
                "bar_play_share": float((cr.bars["accuracy"] >= 0.5).mean()),
                "perf_note_rate_nps": len(pn) / span if span and span > 0 else np.nan,
                "n_positions": len(m),
                **{f"staff_{k}": v for k, v in staff_counts.items()},
                **{f"a_{k}": _num(v) for k, v in cr.summary.items()},
                **{f"t_{k}": _num(v) for k, v in tc.summary.items()},
                **{k: _num(v) for k, v in res.summary.items()},
                **{f"allref_{k}": _num(v) for k, v in s_all.items()},
                "seconds": dt,
            }
            out.append(row)
        except Exception as e:  # noqa: BLE001
            fails.append((r["performance_id"], f"control: {e!r}"))
    return out, fails


def main() -> None:
    warnings.filterwarnings("ignore")
    from pianolens.data import majeppa

    ap_ = argparse.ArgumentParser()
    ap_.add_argument("--workers", type=int, default=10)
    ap_.add_argument("--limit-scores", type=int, default=None)
    a = ap_.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    sel = select(majeppa.majeppa_index())
    groups = {s: g.to_dict("records") for s, g in sel.groupby("score_id")}
    order = sorted(groups, key=lambda s: -len(groups[s]))
    if a.limit_scores:
        order = order[: a.limit_scores]
    print(f"{len(sel)} performances, {len(groups)} scores; running {len(order)} scores")
    rows, fails = [], []
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        futs = {ex.submit(run_score, s, groups[s]): s for s in order}
        for i, f in enumerate(as_completed(futs), 1):
            try:
                o, fl = f.result()
            except Exception as e:  # noqa: BLE001
                o, fl = [], [(futs[f], f"worker: {e!r}")]
            rows += o
            fails += fl
            if i % 20 == 0 or i == len(futs):
                print(f"{i}/{len(futs)} scores, {len(rows)} perfs, {len(fails)} failures, "
                      f"{time.time() - t0:.0f} s", flush=True)
    pd.DataFrame(rows).to_csv(OUT / "majeppa_features.csv", index=False)
    pd.DataFrame(fails, columns=["id", "error"]).to_csv(OUT / "failures.csv", index=False)
    print(f"done: {len(rows)} rows, {len(fails)} failures, {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
