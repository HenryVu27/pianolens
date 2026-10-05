"""BL-17 reachability check (run before any annotation; README "Can each branch be reached?").

Reads the per-movement LLM end F1 (+-1 beat) of R-08a, R-08c and R-08d from their artifacts,
then simulates the BL-17 verdict for n movements x 2 runs under two models:

- normal: true movement means ~ N(mu, sd_b) clipped to [0, 1], each run adds N(0, sd_w);
- empirical: the 15 observed R-08a/c/d movement values, centred, resampled with replacement and
  shifted to mean mu (keeps the heavy lower tail of R-08d's R5), plus the same run noise.

Verdict per simulated study: MADE if the t lower end > 0.70, REJECTED if the t upper end < 0.70,
else INCONCLUSIVE; also P(point >= 0.70) and the mean t half-width.

    uv run python experiments/2026-09-29-BL-17-romantic-llm/power.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats as st

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
SEED = 20261002
N_SIM = 20_000
BAR = 0.70


def observed() -> pd.DataFrame:
    rows = []
    a = pd.read_csv(EXP / "2026-09-28-R-08a-llm-phrase-pilot/artifacts/llm_scores.csv")
    a = a[(a.method == "llm") & (a.target == "end") & (a.tol == "1beat")]
    rows += [{"exp": "R-08a", "movement": m, "F1": f}
             for m, f in zip(a.movement, a.F1, strict=True)]
    for exp, folder, runs in (("R-08c", "2026-09-28-R-08c-llm-unfamiliar-repertoire", ("R1", "R2")),
                              ("R-08d", "2026-09-28-R-08d-llm-romantic-repertoire", ("A", "B"))):
        per = []
        for r in runs:
            s = pd.read_csv(EXP / folder / "artifacts" / f"scores_{r}.csv")
            s = s[(s.method == "llm") & (s.target == "end") & (s.tol == "1beat")]
            per.append(s.set_index("movement")["F1"].rename(r))
        t = pd.concat(per, axis=1)
        rows += [{"exp": exp, "movement": m, "F1": float(v), "within_sd": float(t.loc[m].std())}
                 for m, v in t.mean(axis=1).items()]
    return pd.DataFrame(rows)


def simulate(n: int, mu: float, sd_b: float | None, sd_w: float, pool: np.ndarray | None,
             rng) -> dict:
    if pool is None:
        true = np.clip(rng.normal(mu, sd_b, size=(N_SIM, n)), 0, 1)
    else:
        c = pool - pool.mean()
        true = np.clip(mu + c[rng.integers(0, len(c), size=(N_SIM, n))], 0, 1)
    runs = np.clip(true[..., None] + rng.normal(0, sd_w, size=(N_SIM, n, 2)), 0, 1)
    x = runs.mean(axis=2)
    m = x.mean(axis=1)
    h = st.t.ppf(0.975, n - 1) * x.std(axis=1, ddof=1) / np.sqrt(n)
    return {"P_made": float(np.mean(m - h > BAR)), "P_rejected": float(np.mean(m + h < BAR)),
            "P_inconclusive": float(np.mean((m - h <= BAR) & (m + h >= BAR))),
            "P_point_ge_bar": float(np.mean(m >= BAR)), "half_width": float(np.mean(h))}


def main() -> None:
    obs = observed()
    print(obs.round(3).to_string(index=False))
    sd_all = float(obs.F1.std(ddof=1))
    sd_d = float(obs[obs.exp == "R-08d"].F1.std(ddof=1))
    sd_c = float(obs[obs.exp == "R-08c"].F1.std(ddof=1))
    sd_w = float(obs.within_sd.dropna().mean())
    print(f"\nbetween-movement SD: R-08d {sd_d:.3f}, R-08c {sd_c:.3f}, all 15 {sd_all:.3f}; "
          f"mean within-movement run SD (R-08c, R-08d) {sd_w:.3f}; mean of all 15 "
          f"{obs.F1.mean():.3f}")
    rng = np.random.default_rng(SEED)
    rows = []
    for n in (12, 18, 24, 30):
        for model, sd_b, pool in (("normal", sd_c, None), ("normal", sd_d, None),
                                  ("empirical15", None, obs.F1.to_numpy())):
            for mu in (0.55, 0.60, 0.65, 0.70, 0.737, 0.75, 0.80, 0.85):
                r = simulate(n, mu, sd_b, sd_w, pool, rng)
                rows.append({"n": n, "model": model if sd_b is None else f"{model} sd {sd_b:.3f}",
                             "mu": mu, **r})
    R = pd.DataFrame(rows)
    txt = (obs.round(3).to_string(index=False)
           + f"\n\nbetween-movement SD: R-08d {sd_d:.3f}, R-08c {sd_c:.3f}, all 15 {sd_all:.3f}; "
           f"within-movement run SD {sd_w:.3f}\n\n" + R.round(3).to_string(index=False))
    (HERE / "artifacts" / "power.txt").write_text(txt + "\n")
    print(R[R.n.isin([24])].round(3).to_string(index=False))


if __name__ == "__main__":
    main()
