"""S-04 design check by simulation (DRAFT): passages, performers and listeners for H7.

Runs :func:`pianolens.study.power_s04.power_table_s04` over designs (passages x performances),
listener counts and true feature effects, plus sensitivity runs, and writes

    data/interim/study_s04/power/power_grid.csv
    data/interim/study_s04/power/summary.md

Usage: uv run python scripts/power_s04.py [--n-rep 200] [--seed 0] [--out DIR]

All parameters are assumptions (see pianolens.study.power_s04.S04Assumptions); the output says
how the design behaves *if* they hold.
"""

from __future__ import annotations

import argparse
import dataclasses
import time
from pathlib import Path

import pandas as pd

from pianolens.study.power_s04 import S04Assumptions, power_table_s04, session_minutes_s04

OUT = Path(__file__).resolve().parents[1] / "data" / "interim" / "study_s04" / "power"

BASE = S04Assumptions()
DESIGNS = {
    "P12_n10": dataclasses.replace(BASE, n_passages=12, n_perf=10),
    "P24_n10": dataclasses.replace(BASE, n_passages=24, n_perf=10),
    "P36_n10": dataclasses.replace(BASE, n_passages=36, n_perf=10),
}
N_GRID = [24, 48, 96, 144]
R2_FEATS = [0.0, 0.1, 0.2, 0.3]
SENS_DESIGN = "P24_n10"
SENSITIVITY = {
    "sigma_q_0.5": {"sigma_q": 0.5},
    "tau_1.0": {"tau_listener": 1.0},
    "r2_d2m_0.3": {"r2_d2m": 0.3},
    "feat_reliability_0.7": {"feat_reliability": 0.7},
    "one_active_feature": {"n_active": 1},
    "trials_40": {"trials_per_listener": 40},
}


def md_table(df: pd.DataFrame) -> list[str]:
    """Markdown table without the optional ``tabulate`` dependency."""
    def fmt(v: object) -> str:
        return f"{v:.3f}" if isinstance(v, float) else str(v)

    out = ["| " + " | ".join(df.columns) + " |", "|" + "---|" * len(df.columns)]
    out += ["| " + " | ".join(fmt(v) for v in row) + " |" for row in df.itertuples(index=False)]
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-rep", type=int, default=200)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", type=Path, default=OUT, help="output folder (default: %(default)s)")
    args = ap.parse_args()
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    frames = []
    for name, a in DESIGNS.items():
        df = power_table_s04(a, N_GRID, R2_FEATS, args.n_rep, seed=args.seed)
        df.insert(0, "design", name)
        df.insert(1, "variant", "base")
        frames.append(df)
        print(name, f"{time.time() - t0:.0f}s", flush=True)
    for vname, over in SENSITIVITY.items():
        df = power_table_s04(DESIGNS[SENS_DESIGN], N_GRID, [0.0, 0.2], args.n_rep,
                             seed=args.seed, **over)
        df.insert(0, "design", SENS_DESIGN)
        df.insert(1, "variant", vname)
        frames.append(df)
        print(vname, f"{time.time() - t0:.0f}s", flush=True)
    grid = pd.concat(frames, ignore_index=True)
    grid.to_csv(out / "power_grid.csv", index=False)

    cols = ["design", "variant", "r2_feat", "n_listeners", "comparisons_per_item",
            "p_supported", "p_falsified", "p_inconclusive", "gain_rel_median", "ssr_median",
            "p_ssr_ge_0.8", "shr_median", "ssr_musicians_median", "acc_m0_median",
            "acc_m1_median", "acc_true_median"]
    lines = ["# S-04 design check (simulation, DRAFT)", "",
             f"n_rep = {args.n_rep} per cell, seed = {args.seed}, wall time "
             f"{time.time() - t0:.0f} s. Command: `uv run python scripts/power_s04.py "
             f"--n-rep {args.n_rep} --seed {args.seed}`.", "",
             f"Listening minutes per listener (base): {session_minutes_s04(BASE):.0f}.", "",
             "## Grid", ""]
    lines += md_table(grid[cols])
    lines += ["", "## Assumptions (base)", ""]
    for k, v in dataclasses.asdict(BASE).items():
        lines.append(f"- `{k}` = {v}")
    (out / "summary.md").write_text("\n".join(lines) + "\n")
    print(f"done {time.time() - t0:.0f}s -> {out}")


if __name__ == "__main__":
    main()
