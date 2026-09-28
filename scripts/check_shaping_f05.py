"""F-05 sanity run: tier C shaping on several (n)ASAP performances of one piece, plus a
descriptive MAJEPPA skill contrast (not an experiment).

    uv run python scripts/check_shaping_f05.py [asap_folder] [n_performances] [majeppa_score_id]

Defaults: Schubert/Impromptu_op.90_D.899/3, 6 performances; MAJEPPA S_0077 (Chopin Nocturne
Op. 9 No. 2, all six expertise levels). Pass ``-`` as the MAJEPPA id to skip it. Writes to
``data/interim/shaping_f05/``: ``<tag>_summary.csv`` (one row per performance),
``<tag>_coherence_bars.csv``, ``<tag>_pooled.csv`` and ``majeppa_<id>_summary.csv``.
"""

from __future__ import annotations

import sys
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from pianolens.align import align_performance
from pianolens.data.asap import asap_index, load_asap_performance, load_asap_score
from pianolens.features.score_basis import score_basis
from pianolens.features.shaping import ShapingConfig, pooled_structural_coherence, shaping
from pianolens.features.tempo import tempo_model

OUT = Path(__file__).resolve().parents[1] / "data" / "interim" / "shaping_f05"


def _row(name: str, res, extra: dict | None = None) -> dict:
    return {"performance": name, **(extra or {}),
            **{k: (round(float(v), 4) if isinstance(v, (int, float, np.floating)) else v)
               for k, v in res.summary.items()}}


def run_asap(folder: str, n_max: int) -> None:
    md = asap_index()
    rows = md[md["folder"] == folder].head(n_max)
    cfg = ShapingConfig(by_group=True)
    out, aps, bases, tcs, bars = [], [], [], [], []
    for _, row in rows.iterrows():
        t0 = time.time()
        ap = align_performance(load_asap_score(row), load_asap_performance(row))
        t1 = time.time()
        res = shaping(ap, config=cfg)
        t2 = time.time()
        name = Path(row["midi_performance"]).stem
        print(f"{name}: align {t1 - t0:.1f}s, shaping {t2 - t1:.1f}s, "
              f"variant {ap.score.meta.get('unfolded')!r}")
        print(res.coherence.summary.round(3).to_string(index=False))
        print("  repeats:", res.repeats.summary[["channel", "n_runs", "n_pairs", "r_mean"]]
              .round(3).values.tolist())
        print("  voicing:", {k: round(v, 3) for k, v in res.voicing.summary.items()})
        print("  dynamics:", {k: round(v, 3) for k, v in res.dynamics.summary.items()})
        out.append(_row(name, res))
        b = res.coherence.bars.copy()
        b["performance"] = name
        bars.append(b)
        aps.append(ap)
        bases.append(score_basis(ap.score))
        tcs.append(tempo_model(ap))
    tag = folder.replace("/", "_")
    OUT.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(out)
    df.to_csv(OUT / f"{tag}_summary.csv", index=False)
    pd.concat(bars).to_csv(OUT / f"{tag}_coherence_bars.csv", index=False)
    keys = [c for c in df.columns if c.startswith("coherence_") or c.endswith("_r_mean")]
    print("\nper-performance summary (mean, min, max):")
    print(df[keys].agg(["mean", "min", "max"]).T.round(3).to_string())
    for scale in (False, True):
        pooled = pooled_structural_coherence(aps, bases, tcs, cfg, scale=scale)
        print(f"\npooled over {len(aps)} performances (scale={scale}):")
        print(pooled.summary.round(3).to_string(index=False))
        pp = pooled.per_performance.pivot(index="performance", columns="channel",
                                          values="r2_pooled_model")
        print("per-performance R² under the pooled model:\n", pp.round(3).to_string())
        pooled.summary.assign(scale=scale).to_csv(
            OUT / f"{tag}_pooled{'_scaled' if scale else ''}.csv", index=False)


def run_majeppa(score_id: str) -> None:
    from pianolens.data.majeppa import DEFAULT_ROOT, majeppa_index
    from pianolens.data.midi_io import performance_from_midi, score_from_midi
    from pianolens.data.types import PerformerId

    md = majeppa_index()
    rows = md[md["score_id"] == score_id]
    score = score_from_midi(DEFAULT_ROOT / "extracted" / "score" / f"{score_id}.mid",
                            score_id=f"majeppa:{score_id}", piece_id=rows["piece_id"].iloc[0])
    print(f"\nMAJEPPA {score_id}: {rows['piece_title'].iloc[0]} ({len(rows)} performances)")
    out = []
    for r in rows.itertuples():
        perf = performance_from_midi(
            DEFAULT_ROOT / "extracted" / "performance" / f"{r.performance_id}.mid",
            dataset="majeppa", performance_id=f"majeppa:{r.performance_id}",
            piece_id=r.piece_id, performer_id=PerformerId(f"majeppa:recording/{r.recording_id}"),
            provenance="transcribed",
        )
        try:
            ap = align_performance(score, perf)
            res = shaping(ap)
        except Exception as e:  # noqa: BLE001 - descriptive run, keep going
            print(f"  {r.performance_id} failed: {e!r}")
            continue
        n_match = int((ap.alignment.pairs["label"] == "match").sum())
        extra = {"expertise_level": r.expertise_level, "recording_type": r.recording_type,
                 "score_coverage": r.score_coverage,
                 "match_frac_score": round(n_match / len(ap.score.notes), 3)}
        out.append(_row(r.performance_id, res, extra))
    df = pd.DataFrame(out)
    OUT.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT / f"majeppa_{score_id}_summary.csv", index=False)
    keys = ["match_frac_score", "coherence_velocity_r2", "coherence_velocity_r2_no_markings",
            "coherence_timing_r2", "coherence_tempo_r2", "coherence_articulation_r2",
            "voicing_vel_diff_mean_midi", "voicing_lead_mean_ms", "repeat_velocity_r_mean",
            "repeat_timing_r_mean"]
    order = ["child_beginner", "adult_beginner", "adult_intermediate", "child_professional",
             "piano_teacher", "virtuoso"]
    df["expertise_level"] = pd.Categorical(df["expertise_level"], order, ordered=True)
    print(df.sort_values("expertise_level")[["performance", "expertise_level", *keys]]
          .round(3).to_string(index=False))


def main() -> None:
    warnings.filterwarnings("ignore")
    folder = sys.argv[1] if len(sys.argv) > 1 else "Schubert/Impromptu_op.90_D.899/3"
    n_max = int(sys.argv[2]) if len(sys.argv) > 2 else 6
    maj = sys.argv[3] if len(sys.argv) > 3 else "S_0077"
    run_asap(folder, n_max)
    if maj != "-":
        run_majeppa(maj)


if __name__ == "__main__":
    main()
