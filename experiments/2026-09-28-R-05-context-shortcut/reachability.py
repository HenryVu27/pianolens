"""R-05 pre-registration: can each verdict branch be reached? (rules/experiments.md, R-09 lesson)

Synthetic classifier scores on the real sample's labels and CV groups (no embeddings, no real
scores). Every condition's out-of-fold score is  s_k = d * y + u + v_group + sd_e * e_k  with a
shared clip term u, a shared group term v and an independent condition term e_k, so conditions are
exchangeable (true delta 0) unless a shift is added to the confounded condition. The two
pre-registered deltas are computed as in analyze.py (CC minus the mean of 4 matched; CC minus the
mean of K shuffled tests), with a group bootstrap, and the verdict rule is applied.

Usage: uv run python experiments/2026-09-28-R-05-context-shortcut/reachability.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from common import ADVANCED, BEGINNER, auc, cv_groups

HERE = Path(__file__).resolve().parent
MARGIN = 0.02
N_SIM, N_BOOT, K_SHUF = 200, 400, 5


def one(y, g, d, sd_e, shift, rng):
    n = len(y)
    u = rng.standard_normal(n)
    v = rng.standard_normal(g.max() + 1)[g] * 0.3
    base = d * y + u + v
    m = [base + sd_e * rng.standard_normal(n) for _ in range(4)]
    cc = base + sd_e * rng.standard_normal(n) + shift * y  # shift: AUC gain from the shortcut
    cs = [base + sd_e * rng.standard_normal(n) for _ in range(K_SHUF)]
    members = [np.flatnonzero(g == k) for k in range(g.max() + 1)]

    def deltas(idx):
        a_cc = auc(y[idx], cc[idx])
        return (a_cc - np.mean([auc(y[idx], s[idx]) for s in m]),
                a_cc - np.mean([auc(y[idx], s[idx]) for s in cs]))

    est = deltas(np.arange(n))
    reps = []
    for _ in range(N_BOOT):
        pick = rng.integers(0, len(members), len(members))
        reps.append(deltas(np.concatenate([members[i] for i in pick])))
    lo, hi = np.quantile(np.array(reps), [0.025, 0.975], axis=0)
    supported = bool(lo[0] > 0 and lo[1] > 0)
    falsified = bool(np.all(lo > -MARGIN) and np.all(hi < MARGIN))
    verdict = "supported" if supported else "falsified" if falsified else "inconclusive"
    return est, (hi - lo) / 2, verdict


def main() -> None:
    s = pd.read_csv(HERE / "artifacts" / "sample.csv")
    s = s[s.expertise_level.isin(BEGINNER + ADVANCED)].reset_index(drop=True)
    y = s.expertise_level.isin(ADVANCED).to_numpy().astype(int)
    g = cv_groups(s)
    out = {"n": len(y), "n_groups": int(g.max() + 1), "margin": MARGIN, "cases": []}
    rng = np.random.default_rng(20260928)
    # d = 0.95 gives AUC about 0.72 with u (var 1) + v (var 0.09); sd_e sets the correlation
    # between conditions' scores (rho = 1.09 / (1.09 + sd_e^2)).
    for sd_e in (0.35, 0.7):
        for shift in (0.0, 0.1, 0.2):
            res = [one(y, g, 0.95, sd_e, shift, rng) for _ in range(N_SIM)]
            verdicts = pd.Series([r[2] for r in res]).value_counts(normalize=True).to_dict()
            hw = np.mean([r[1] for r in res], axis=0)
            dl = np.mean([r[0] for r in res], axis=0)
            case = {"sd_e": sd_e, "rho": round(1.09 / (1.09 + sd_e**2), 2), "shift_d": shift,
                    "mean_delta_infl": round(float(dl[0]), 4),
                    "mean_delta_short": round(float(dl[1]), 4),
                    "half_width_infl": round(float(hw[0]), 4),
                    "half_width_short": round(float(hw[1]), 4),
                    "P": {k: round(v, 3) for k, v in verdicts.items()}}
            out["cases"].append(case)
            print(json.dumps(case), flush=True)
    (HERE / "artifacts" / "reachability.json").write_text(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
