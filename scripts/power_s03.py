"""S-03 power analysis by simulation: how many listeners does the perceptual cost study need?

Runs :func:`pianolens.study.power.power_table` over designs, listener counts and true slope
ratios, plus sensitivity runs on the assumptions, and writes

    data/interim/study_s03/power/power_grid.csv
    data/interim/study_s03/power/summary.md

Usage: uv run python scripts/power_s03.py [--n-rep 200] [--seed 0]

All parameters are assumptions (see pianolens.study.power.Assumptions); the output says how
the design behaves *if* they hold.
"""

from __future__ import annotations

import argparse
import dataclasses
import time
from pathlib import Path

import pandas as pd

from pianolens.study.power import Assumptions, power_table, session_minutes

OUT = Path(__file__).resolve().parents[1] / "data" / "interim" / "study_s03" / "power"

# Clip lengths: medians of the built pilot stimuli (det 7.3 s, pref 13.8 s, release and tail
# included; data/interim/study_s03/manifest.json). They only affect the minutes column.
_CLIPS = {"det_clip_sec": 7.3, "pref_clip_sec": 13.8, "response_sec": 3.0}
DESIGNS = {
    # one session per part: 3 detection trials per level (4 levels), 2 preference trials per level
    "A1_one_session_pref124": Assumptions(det_reps=3, pref_reps=2,
                                          pref_levels_rel=(1.0, 2.0, 4.0), **_CLIPS),
    "A2_one_session_pref248": Assumptions(det_reps=3, pref_reps=2,
                                          pref_levels_rel=(2.0, 4.0, 8.0), **_CLIPS),
    # two sessions per part: double the trials
    "B2_two_sessions_pref248": Assumptions(det_reps=6, pref_reps=4, pref_identical=14,
                                           pref_levels_rel=(2.0, 4.0, 8.0), **_CLIPS),
}
N_GRID = [16, 24, 32, 48, 64, 96, 128, 160]
RATIOS = [1.0, 2.0, 3.0]
SENSITIVITY = {
    "tau_0.25": {"det_tau_log2": 0.25},
    "tau_0.75": {"det_tau_log2": 0.75},
    "beta_0.2": {"pref_beta": 0.2},
    "beta_0.8": {"pref_beta": 0.8},
    "beta_sd_0.4": {"pref_beta_sd": 0.4},
    "ladder_off_x2": {"ladder_error_log2": 1.0},
    "slope_1": {"det_slope": 1.0},
    "margin_1.5": {"margin": 1.5},
}


def md_table(df: pd.DataFrame) -> list[str]:
    """Markdown table without the optional ``tabulate`` dependency."""
    def fmt(v: object) -> str:
        return f"{v:.3f}" if isinstance(v, float) else str(v)

    out = ["| " + " | ".join(df.columns) + " |", "|" + "---|" * len(df.columns)]
    out += ["| " + " | ".join(fmt(v) for v in row) + " |" for row in df.itertuples(index=False)]
    return out


def min_n(df: pd.DataFrame, col: str, target: float = 0.8) -> int | None:
    ok = df[df[col] >= target]
    return int(ok["n_listeners"].min()) if len(ok) else None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-rep", type=int, default=200)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    frames = []
    for name, a in DESIGNS.items():
        df = power_table(a, N_GRID, RATIOS, args.n_rep, seed=args.seed)
        df.insert(0, "design", name)
        df.insert(1, "variant", "base")
        frames.append(df)
        print(name, f"{time.time() - t0:.0f}s", flush=True)
    base_name = "A2_one_session_pref248"
    for vname, over in SENSITIVITY.items():
        for name in (base_name, "B2_two_sessions_pref248"):
            df = power_table(DESIGNS[name], N_GRID, [1.0, 3.0], args.n_rep, seed=args.seed,
                             **over)
            df.insert(0, "design", name)
            df.insert(1, "variant", vname)
            frames.append(df)
        print(vname, f"{time.time() - t0:.0f}s", flush=True)
    grid = pd.concat(frames, ignore_index=True)
    grid.to_csv(OUT / "power_grid.csv", index=False)

    lines = ["# S-03 power analysis (simulation)", "",
             f"n_rep = {args.n_rep} per cell, seed = {args.seed}, wall time "
             f"{time.time() - t0:.0f} s. Command: `uv run python scripts/power_s03.py "
             f"--n-rep {args.n_rep} --seed {args.seed}`.", "",
             "## Designs", "", "| design | detection trials | preference trials | "
             "Part A minutes | Part B minutes | pref levels (x threshold) |",
             "|---|---|---|---|---|---|"]
    for name, a in DESIGNS.items():
        s = session_minutes(a)
        lines.append(f"| {name} | {s['n_det_trials']} | {s['n_pref_trials']} | "
                     f"{s['det_min']:.0f} | {s['pref_min']:.0f} | {a.pref_levels_rel} |")
    lines += ["", "## Smallest N (total listeners) reaching 80%", "",
              "| design | variant | P(supported) >= .8 at ratio 2 | at ratio 3 | "
              "P(falsified) >= .8 at ratio 1 | P(supported) at ratio 1 (max over N) |",
              "|---|---|---|---|---|---|"]
    for (d, v), g in grid.groupby(["design", "variant"], sort=False):
        r1, r2, r3 = (g[g["ratio"] == r] for r in (1.0, 2.0, 3.0))
        lines.append(
            f"| {d} | {v} | {min_n(r2, 'p_supported') if len(r2) else 'n/a'} | "
            f"{min_n(r3, 'p_supported')} | {min_n(r1, 'p_falsified')} | "
            f"{r1['p_supported'].max():.3f} |")
    lines += ["", "(None = not reached within N <= 160.)", "", "## Full grid (base variants)", ""]
    base = grid[grid["variant"] == "base"]
    lines += md_table(base.drop(columns=["variant", "n_rep"]))
    lines += ["", "## Assumptions (base)", ""]
    for k, v in dataclasses.asdict(DESIGNS[base_name]).items():
        lines.append(f"- `{k}` = {v}")
    (OUT / "summary.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines[:40]))


if __name__ == "__main__":
    main()
