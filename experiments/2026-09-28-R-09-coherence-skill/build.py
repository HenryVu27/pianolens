"""R-09: structural coherence (F-05) and per-phrase tempo shaping (F-05c) of MAJEPPA performances.

    OMP_NUM_THREADS=1 uv run python experiments/2026-09-28-R-09-coherence-skill/build.py --workers 8

Selection is D-10's (``scripts/build_skill_control_d10.py::select``). Per performance:
``align_performance`` -> ``majeppa.prepare_aligned`` -> F-02 ``correctness`` (match ratio gate) ->
F-03 ``tempo_model`` -> ``score_basis`` -> ``structural_coherence`` (all four channels) ->
``cadence_phrase_ends`` + ``phrase_tempo_shaping``. Gates are applied in ``analyze.py``, not here,
so the counts per gate can be reported. Writes ``artifacts/coherence.csv`` and ``failures.csv``.
"""

from __future__ import annotations

import argparse
import importlib.util
import time
import warnings
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / "artifacts"


def _d10():
    spec = importlib.util.spec_from_file_location(
        "d10", ROOT / "scripts" / "build_skill_control_d10.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def coherence_row(ap, tc, basis) -> dict:
    """Coherence and phrase-tempo summary of one aligned performance (shared with noise_floor)."""
    from pianolens.features.cadence import cadence_phrase_ends
    from pianolens.features.shaping import phrase_tempo_shaping, structural_coherence

    out: dict = {}
    co = structural_coherence(ap, basis, tc)
    for r in co.summary.to_dict("records"):
        ch = r["channel"]
        for k in ("n", "n_blocks", "y_sd", "r2", "r2_no_markings"):
            out[f"{ch}_{k}"] = float(r.get(k, np.nan)) if r.get(k) is not None else np.nan
    try:
        cad = cadence_phrase_ends(ap.score, basis=basis)
        pt = phrase_tempo_shaping(ap, cad.starts, tempo=tc, basis=basis)
        for k in ("n_phrases", "concave_share", "null_concave_share", "concave_excess",
                  "arc_r2_within", "arc_r2_excess"):
            out[f"pts_{k}"] = float(pt.summary[k])
        out["pts_n_cadence_starts"] = len(cad.starts)
    except Exception as e:  # noqa: BLE001
        out["pts_error"] = repr(e)
    return out


def run_score(score_id: str, rows: list[dict]) -> tuple[list[dict], list[tuple[str, str]]]:
    warnings.filterwarnings("ignore")
    import logging

    logging.disable(logging.WARNING)
    from pianolens.align import align_performance
    from pianolens.data import majeppa
    from pianolens.data.midi_io import performance_from_midi, score_from_midi
    from pianolens.data.types import PerformerId
    from pianolens.features.correctness import correctness
    from pianolens.features.score_basis import score_basis
    from pianolens.features.tempo import tempo_model

    root = majeppa.DEFAULT_ROOT
    try:
        score = score_from_midi(root / "extracted" / "score" / f"{score_id}.mid",
                                score_id=f"majeppa:{score_id}", piece_id=rows[0]["piece_id"])
    except Exception as e:  # noqa: BLE001
        return [], [(score_id, f"score: {e!r}")]
    sq = score.notes["onset_quarter"].astype(float)
    offgrid = float((np.abs(sq * 48 - np.round(sq * 48)) > 0.05).mean())
    out, fails = [], []
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
            ap, _ = majeppa.prepare_aligned(ap, score_id)
            cr = correctness(ap)
            tc = tempo_model(ap)
            basis = score_basis(ap.score)
            pn = ap.performance.notes
            span = float(pn["onset_sec"].max() - pn["onset_sec"].min()) if len(pn) > 1 else np.nan
            row = {
                **{k: r[k] for k in ("performance_id", "recording_id", "score_id", "piece_id",
                                     "composer", "piece_title", "expertise_level",
                                     "skill_group", "recording_type", "score_coverage")},
                "score_offgrid_share": offgrid,
                "match_ratio": float(cr.summary["match_ratio"]),
                "alignment_suspect": bool(cr.summary["alignment_suspect"]),
                "n_perf_notes": len(pn),
                "duration_s": span,
                "note_rate_nps": len(pn) / span if span and span > 0 else np.nan,
                "n_score_bars": int(basis.notes["measure_number"].nunique()),
                **coherence_row(ap, tc, basis),
                "seconds": time.time() - t0,
            }
            out.append(row)
        except Exception as e:  # noqa: BLE001
            fails.append((pid, repr(e)))
    return out, fails


def main() -> None:
    warnings.filterwarnings("ignore")
    from pianolens.data import majeppa

    p = argparse.ArgumentParser()
    p.add_argument("--workers", type=int, default=8)
    p.add_argument("--limit-scores", type=int, default=None)
    a = p.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    sel = _d10().select(majeppa.majeppa_index())
    groups = {s: g.to_dict("records") for s, g in sel.groupby("score_id")}
    order = sorted(groups, key=lambda s: -len(groups[s]))[: a.limit_scores]
    print(f"{len(sel)} performances, {len(groups)} scores; running {len(order)} scores",
          flush=True)
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
            if i % 25 == 0 or i == len(futs):
                print(f"{i}/{len(futs)} scores, {len(rows)} perfs, {len(fails)} failures, "
                      f"{time.time() - t0:.0f} s", flush=True)
    pd.DataFrame(rows).to_csv(OUT / "coherence.csv", index=False)
    pd.DataFrame(fails, columns=["id", "error"]).to_csv(OUT / "failures.csv", index=False)
    print(f"done: {len(rows)} rows, {len(fails)} failures, {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
