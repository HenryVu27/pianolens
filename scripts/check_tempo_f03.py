"""F-03 sanity run: tempo model on a few (n)ASAP performances of one piece.

    uv run python scripts/check_tempo_f03.py [asap_folder] [n_performances]

Default: Chopin/Etudes_op_10/12, 6 performances. Aligns each with ``align_performance``, fits
``tempo_model`` (default and GCV smoothing), prints the summaries, the detected breaks and the
mean pairwise correlation of the smooth log-tempo curves, and writes to
``data/interim/tempo_f03/``: ``<folder>_tempo.png`` (smooth curves and residuals),
``<folder>_bars.csv`` (per-bar table) and ``<folder>_summary.csv``.
"""

from __future__ import annotations

import sys
import time
import warnings
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

from pianolens.align import align_performance
from pianolens.data.asap import asap_index, load_asap_performance, load_asap_score
from pianolens.features.tempo import TempoConfig, tempo_model

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "data" / "interim" / "tempo_f03"
KEYS = [
    "tempo_bpm_geomean", "tempo_bpm_overall", "tempo_log_sd", "jitter_rms_ms", "jitter_mad_ms",
    "jitter_rms_beats", "jitter_nometric_rms_ms", "n_positions", "n_outliers",
    "n_gross_outliers", "n_segments", "n_tempo_steps", "n_pauses", "edf", "n_match",
]  # fmt: skip


def main(folder: str = "Chopin/Etudes_op_10/12", n_max: int = 6) -> None:
    warnings.filterwarnings("ignore")
    OUT.mkdir(parents=True, exist_ok=True)
    md = asap_index()
    rows = md[md["folder"] == folder].head(n_max)
    res = {}
    for _, row in rows.iterrows():
        t0 = time.time()
        ap = align_performance(load_asap_score(row), load_asap_performance(row))
        t_align = time.time() - t0
        t0 = time.time()
        tc = tempo_model(ap)
        t_tempo = time.time() - t0
        gcv = tempo_model(ap, TempoConfig(smoothing="gcv"))
        name = Path(row["midi_performance"]).stem
        res[name] = tc
        summ = {k: round(float(tc.summary[k]), 3) for k in KEYS}
        print(f"{name}: align {t_align:.1f}s, tempo {t_tempo:.1f}s, {summ}; "
              f"gcv cutoff {gcv.summary['cutoff_beats']:.2f} beats, "
              f"gcv jitter {gcv.summary['jitter_rms_ms']:.1f} ms")
        br = tc.breaks[["beat", "kind", "text", "log_ratio", "excess_sec"]].round(3)
        print("  breaks:", br.values.tolist())

    tag = folder.replace("/", "_")
    fig, ax = plt.subplots(2, 1, figsize=(10, 6), sharex=True)
    for name, tc in res.items():
        ax[0].plot(tc.beats["beat"], tc.beats["tempo_bpm"], lw=1, label=name)
        p = tc.positions[~tc.positions["outlier"]]
        ax[1].plot(p["beat"], 1000 * p["dev_sec"], lw=0.5)
    ax[0].set_ylabel("smooth tempo (BPM, score beats)")
    ax[0].legend(fontsize=7, ncol=3)
    ax[1].set_ylabel("residual (ms)")
    ax[1].set_xlabel("score beat (unfolded)")
    ax[0].set_title(f"{folder} (n)ASAP: smooth tempo (1.5-bar cutoff) and residual")
    fig.tight_layout()
    fig.savefig(OUT / f"{tag}_tempo.png", dpi=110)

    names = list(res)
    grid = pd.concat(
        [res[n].beats.set_index("beat")["tempo_log_ratio"].rename(n) for n in names], axis=1
    ).dropna()
    corr = grid.corr().to_numpy()
    iu = np.triu_indices(len(names), 1)
    print(f"pairwise corr of smooth log tempo: mean {corr[iu].mean():.3f} "
          f"min {corr[iu].min():.3f} max {corr[iu].max():.3f}; grid beats {len(grid)}")
    pd.concat([res[n].bars.assign(perf=n) for n in names]).to_csv(
        OUT / f"{tag}_bars.csv", index=False
    )
    pd.DataFrame({n: res[n].summary for n in names}).T.to_csv(OUT / f"{tag}_summary.csv")


if __name__ == "__main__":
    main(*(sys.argv[1:2] or []), *([int(sys.argv[2])] if len(sys.argv) > 2 else []))
