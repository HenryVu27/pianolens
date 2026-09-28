"""F-04 sanity run: tier B control features on a few real performances.

    uv run python scripts/check_control_f04.py [--n 6]

ASAP: the first ``n`` performances of Chopin Op. 10 No. 12, Bach WTC I Prelude BWV 848 and
Schubert D.899 No. 3, aligned with ``align_performance``. Vienna 4x22: all 22 performances of
Chopin Op. 10 No. 3 and Mozart K.331 (match-file alignments). Batik: the first performance.
Timing-noise references are the other performances of the same piece (leave-one-out); a piece
whose performers took different repeat paths only shares the positions they have in common.
Writes ``data/interim/control_f04/summary.csv`` and ``bars.csv`` and prints ranges.
"""

from __future__ import annotations

import argparse
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parents[1] / "data" / "interim" / "control_f04"
ASAP_FOLDERS = ["Chopin/Etudes_op_10/12", "Bach/Prelude/bwv_848",
                "Schubert/Impromptu_op.90_D.899/3"]  # fmt: skip
KEYS = [
    "timing_noise_rms_ms", "timing_noise_coverage", "timing_noise_n_refs_median",
    "timing_consensus_r2", "jitter_nometric_rms_ms", "even_ioi_cv", "even_vel_sd_midi",
    "even_n_runs", "even_share_of_onsets", "hand_async_mean_ms", "hand_async_sd_ms",
    "hand_async_vel_slope_ms", "hand_async_resid_sd_ms", "hand_async_equalvel_sd_ms",
    "n_cross_staff_onsets", "tempo_instability_log_sd", "tempo_section_log_sd",
    "tempo_phrase_log_sd", "tempo_drift_log", "n_stability_sections", "n_harmony_changes",
    "pedal_blur_fraction", "pedal_blur_beats", "pedal_down_fraction",
    # F-04b
    "even_note_rate_nps", "even_strict_ioi_cv", "even_strict_vel_sd_midi", "even_strict_n_runs",
    "even_strict_share_of_onsets", "even_strict_note_rate_nps",
]  # fmt: skip


def _asap_one(args):
    warnings.filterwarnings("ignore")
    from pianolens.align import align_performance
    from pianolens.data.asap import load_asap_performance, load_asap_score

    row = args
    return align_performance(load_asap_score(row), load_asap_performance(row))


def groups(n: int) -> dict[str, list]:
    from pianolens.data import batik_mozart, vienna4x22
    from pianolens.data.asap import asap_index

    md = asap_index()
    out: dict[str, list] = {}
    for folder in ASAP_FOLDERS:
        rows = [r for _, r in md[md["folder"] == folder].head(n).iterrows()]
        # sequential: aligned scores keep their partitura part, which does not pickle
        out[f"asap:{folder}"] = [_asap_one(r) for r in rows]
    vienna: dict[str, list] = {}
    for ap in vienna4x22.iter_aligned():
        vienna.setdefault(ap.score.score_id, []).append(ap)
    for k in ("vienna4x22:Chopin_op10_no3", "vienna4x22:Mozart_K331_1st-mov"):
        out[k] = vienna.get(k, [])
    out["batik:first"] = [next(iter(batik_mozart.iter_aligned()))]
    return out


def main() -> None:
    warnings.filterwarnings("ignore")
    from pianolens.features.control import control_features, reference_residuals
    from pianolens.features.tempo import tempo_model

    ap_ = argparse.ArgumentParser()
    ap_.add_argument("--n", type=int, default=6)
    a = ap_.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    rows, bars = [], []
    for name, aps in groups(a.n).items():
        curves = {x.performance.performance_id: tempo_model(x) for x in aps}
        refs = {k: reference_residuals(c) for k, c in curves.items()}
        for x in aps:
            pid = x.performance.performance_id
            res = control_features(x, curves[pid], references=refs if len(aps) > 3 else None)
            rows.append({"group": name, "performance_id": pid,
                         **{k: res.summary.get(k) for k in KEYS}})  # fmt: skip
            b = res.bars.copy()
            b.insert(0, "performance_id", pid)
            bars.append(b)
            print(pid, {k: (round(float(res.summary[k]), 3) if isinstance(
                res.summary[k], (int, float, np.floating)) else res.summary[k])
                for k in KEYS[:1] + KEYS[4:8] + KEYS[11:13] + KEYS[15:16] + KEYS[21:23]})
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "summary.csv", index=False)
    pd.concat(bars).to_csv(OUT / "bars.csv", index=False)
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 50)
    num = df.drop(columns=["performance_id"]).groupby("group")
    print("\nmedian per group:\n", num.median(numeric_only=True).T.round(3))
    print("\nmin per group:\n", num.min(numeric_only=True).T.round(3))
    print("\nmax per group:\n", num.max(numeric_only=True).T.round(3))


if __name__ == "__main__":
    main()
