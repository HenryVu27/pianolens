"""Simulation-based design check for the S-04 pairwise preference study (H7). DRAFT.

The design (``study/protocol-S04.md``): ``n_passages`` passages, ``n_perf`` expert performances
of each (exact-capture MIDI rendered with the one fixed piano). Every trial is a blind pair of
two performances *of the same passage*, "which do you prefer?". Pairs are scheduled
non-adaptively so that every within-passage pair is judged about equally often across listeners;
the position of each performance is counterbalanced.

The pre-registered analysis (protocol section 7) that :func:`simulate_once` reproduces:

1. **Scale.** A Bradley-Terry fit per passage (:func:`pianolens.eval.bradley_terry
   .fit_bradley_terry`), scores centred within the passage. Reliability: scale separation
   reliability (SSR, from the Fisher-information standard errors, :func:`bt_standard_errors`)
   and split-half reliability over listeners, Spearman-Brown stepped up (SHR).
2. **H7.** Leave-one-passage-out regression of the BT scores on
   * M0: distance to the expert mean (``d2m``) alone, and
   * M1: ``d2m`` plus ``n_features`` interpretable features,
   with predictors and scores centred within passage. The statistic is the gain in held-out
   R^2 (pooled over held-out passages) divided by SSR: the share of the *reliable* between-
   performance variance that the features explain beyond ``d2m``. A passage bootstrap gives
   its 95% CI.
3. **Reading** with margin ``delta`` (:func:`h7_verdict`): *supported* if the lower CI bound is
   above 0 and the estimate is at least ``delta``; *falsified* if the upper CI bound is below
   ``delta`` (the features add less than ``delta`` of the reliable variance); *inconclusive*
   otherwise.

Every number in :class:`S04Assumptions` is an **assumption**, not a measurement. Nothing here
has been run on a listener; the truth model (how much of preference ``d2m`` and the features
explain, how much listeners disagree) is exactly what the study is meant to measure.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.special import expit

from pianolens.eval.bradley_terry import fit_bradley_terry

__all__ = ["BT_L2", "H7_DELTA", "S04Assumptions", "bt_standard_errors", "h7_verdict",
           "power_table_s04", "schedule_pairs", "session_minutes_s04", "simulate_once"]

#: Ridge on the BT scores (a Gaussian prior with s.d. about 3.2 logits). With about 20
#: comparisons per item an expert who wins or loses every comparison is common, and its plain
#: MLE is infinite; this weak prior keeps it finite and barely moves the other scores.
BT_L2: float = 0.1

#: Draft H7 margin: the features must add at least this share of the reliable BT variance
#: beyond distance-to-mean to count as "substantially". A design choice for the lead (protocol
#: section 11), not a measured value.
H7_DELTA: float = 0.10


@dataclass(frozen=True)
class S04Assumptions:
    """Design and truth-model parameters. Strength units are logits of pairwise preference."""

    # design
    n_passages: int = 12
    n_perf: int = 10  # performances (distinct pianists) per passage
    trials_per_listener: int = 50
    musician_share: float = 0.5
    # truth model (all assumptions)
    sigma_q: float = 1.0  # s.d. of population-mean strength within a passage
    r2_d2m: float = 0.15  # share of var(q) explained by distance-to-mean alone
    r2_feat: float = 0.0  # extra share explained by the features (H7 effect; 0 = H7 false)
    n_features: int = 7  # interpretable features in M1
    n_active: int = 3  # of which carry the effect
    feat_corr: float = 0.3  # correlation among features
    feat_d2m_corr: float = 0.3  # correlation of each feature with d2m
    feat_reliability: float = 1.0  # measurement reliability of the computed features
    tau_listener: float = 0.5  # s.d. of listener-specific strength offsets (taste)
    position_bias: float = 0.3  # logit bias toward the second item (as in S-03, assumed)
    lapse: float = 0.02
    # analysis
    delta: float = H7_DELTA
    n_boot: int = 500
    # timing (seconds)
    clip_sec: float = 20.0
    response_sec: float = 3.0
    gap_sec: float = 0.6


def session_minutes_s04(a: S04Assumptions) -> float:
    """Listening minutes per listener (excludes consent, checks, practice and breaks)."""
    return a.trials_per_listener * (2 * a.clip_sec + a.gap_sec + a.response_sec) / 60


def schedule_pairs(n_passages: int, n_perf: int, n_listeners: int, trials: int,
                   rng: np.random.Generator) -> pd.DataFrame:
    """Non-adaptive schedule: every within-passage unordered pair is judged about equally often.

    The global sequence is a concatenation of shuffled permutations of all pairs; listener ``l``
    takes trials ``l*T .. (l+1)*T - 1``. The first item of each occurrence of a pair alternates,
    so position is balanced per pair. Returns columns ``listener, passage, i, j`` (``i`` is
    played first).
    """
    iu, ju = np.triu_indices(n_perf, 1)
    pairs = np.array([(p, i, j) for p in range(n_passages) for i, j in zip(iu, ju, strict=True)])
    need = n_listeners * trials
    reps = int(np.ceil(need / len(pairs)))
    seq = np.vstack([pairs[rng.permutation(len(pairs))] for _ in range(reps)])[:need]
    occ = np.zeros(len(pairs), dtype=int)
    key = {tuple(r): k for k, r in enumerate(pairs)}
    first, second = seq[:, 1].copy(), seq[:, 2].copy()
    for t, r in enumerate(seq):
        k = key[tuple(r)]
        if occ[k] % 2 == 1:
            first[t], second[t] = second[t], first[t]
        occ[k] += 1
    return pd.DataFrame({"listener": np.repeat(np.arange(n_listeners), trials),
                         "passage": seq[:, 0], "i": first, "j": second})  # fmt: skip


def bt_standard_errors(scores: np.ndarray, winners: np.ndarray, losers: np.ndarray,
                       l2: float = BT_L2) -> np.ndarray:
    """Fisher-information standard errors of centred BT scores (pseudo-inverse)."""
    n = len(scores)
    p = expit(scores[winners] - scores[losers])
    w = p * (1 - p)
    H = np.zeros((n, n))
    np.add.at(H, (winners, winners), w)
    np.add.at(H, (losers, losers), w)
    np.add.at(H, (winners, losers), -w)
    np.add.at(H, (losers, winners), -w)
    H += l2 * np.eye(n)
    C = np.eye(n) - 1.0 / n  # centring
    cov = C @ np.linalg.pinv(H) @ C
    return np.sqrt(np.clip(np.diag(cov), 0, None))


def _fit_scores(df: pd.DataFrame, n_passages: int, n_perf: int) -> tuple[np.ndarray, np.ndarray]:
    """BT scores and SEs per passage from judgements (columns passage, winner, loser)."""
    s = np.zeros((n_passages, n_perf))
    se = np.full((n_passages, n_perf), np.nan)
    for p, g in df.groupby("passage"):
        w, lo = g["winner"].to_numpy(), g["loser"].to_numpy()
        bt = fit_bradley_terry(list(zip(w, lo, strict=True)), items=list(range(n_perf)),
                               l2=BT_L2)
        s[p] = bt.scores
        se[p] = bt_standard_errors(bt.scores, w, lo, l2=BT_L2)
    return s, se


def _ssr(s: np.ndarray, se: np.ndarray) -> float:
    """Scale separation reliability pooled over passages (scores centred per passage)."""
    obs = float(np.mean(s**2)) * s.shape[1] / (s.shape[1] - 1)
    err = float(np.nanmean(se**2))
    return (obs - err) / obs if obs > 0 else float("nan")


def _pooled_r(a: np.ndarray, b: np.ndarray) -> float:
    a = a - a.mean(axis=1, keepdims=True)
    b = b - b.mean(axis=1, keepdims=True)
    return float(np.sum(a * b) / np.sqrt(np.sum(a**2) * np.sum(b**2)))


def h7_verdict(estimate: float, lo: float, hi: float, delta: float = H7_DELTA) -> str:
    """Draft H7 reading of the reliable-variance gain and its 95% CI (protocol section 2)."""
    if lo > 0 and estimate >= delta:
        return "supported"
    if hi < delta:
        return "falsified"
    return "inconclusive"


def _truth(a: S04Assumptions, rng: np.random.Generator) -> tuple[np.ndarray, ...]:
    """True strengths q, d2m and the features (as computed) per passage x performance."""
    P, n, k = a.n_passages, a.n_perf, a.n_features
    S = np.full((k + 1, k + 1), a.feat_corr)
    S[0, 1:] = S[1:, 0] = a.feat_d2m_corr
    np.fill_diagonal(S, 1.0)
    Z = rng.multivariate_normal(np.zeros(k + 1), S, size=(P, n))  # (P, n, k+1)
    d2m, F = Z[..., 0], Z[..., 1:]
    w = np.zeros(k)
    w[: a.n_active] = 1.0
    lin = F @ w
    # the feature signal orthogonal to d2m (population regression)
    beta = (S[0, 1:] @ w) / S[0, 0]
    perp = lin - beta * d2m
    var_perp = float(w @ S[1:, 1:] @ w - beta**2)
    u = rng.normal(0, 1, (P, n))
    r_u = max(1.0 - a.r2_d2m - a.r2_feat, 0.0)
    q = a.sigma_q * (np.sqrt(a.r2_d2m) * d2m + np.sqrt(a.r2_feat / var_perp) * perp
                     + np.sqrt(r_u) * u)  # fmt: skip
    if a.feat_reliability < 1.0:  # measurement error in the computed features and d2m
        e = np.sqrt(1 / a.feat_reliability - 1)
        d2m = d2m + rng.normal(0, e, d2m.shape)
        F = F + rng.normal(0, e, F.shape)
    return q, d2m, F


def _center(x: np.ndarray) -> np.ndarray:
    return x - x.mean(axis=1, keepdims=True)


def _lopo(y: np.ndarray, X: np.ndarray) -> np.ndarray:
    """Leave-one-passage-out OLS predictions (no intercept; everything centred per passage)."""
    P = y.shape[0]
    pred = np.zeros_like(y)
    for p in range(P):
        tr = np.arange(P) != p
        Xt, yt = X[tr].reshape(-1, X.shape[-1]), y[tr].ravel()
        coef, *_ = np.linalg.lstsq(Xt, yt, rcond=None)
        pred[p] = X[p] @ coef
    return pred


def simulate_once(a: S04Assumptions, n_listeners: int, rng: np.random.Generator
                  ) -> dict[str, float | str]:
    """Simulate one study with ``n_listeners`` (both strata) and analyse it as pre-registered."""
    P, n = a.n_passages, a.n_perf
    q, d2m, F = _truth(a, rng)
    sch = schedule_pairs(P, n, n_listeners, a.trials_per_listener, rng)
    off = rng.normal(0, a.tau_listener, (n_listeners, P, n))
    li, pp, i, j = (sch[c].to_numpy() for c in ("listener", "passage", "i", "j"))
    z = (q[pp, i] + off[li, pp, i]) - (q[pp, j] + off[li, pp, j]) - a.position_bias
    p_first = a.lapse / 2 + (1 - a.lapse) * expit(z)  # P(first item preferred)
    first_wins = rng.random(len(z)) < p_first
    sch = sch.assign(winner=np.where(first_wins, i, j), loser=np.where(first_wins, j, i))
    musician = np.arange(n_listeners) < int(round(a.musician_share * n_listeners))

    s, se = _fit_scores(sch, P, n)
    ssr = _ssr(s, se)
    # split-half over listeners (one random split here; 1,000 in the real analysis)
    half = rng.permutation(n_listeners) < n_listeners // 2
    s1, _ = _fit_scores(sch[half[sch["listener"]]], P, n)
    s2, _ = _fit_scores(sch[~half[sch["listener"]]], P, n)
    r_half = _pooled_r(s1, s2)
    shr = 2 * r_half / (1 + r_half)
    # one stratum alone (musicians): reliability of a per-group scale
    sm, sem = _fit_scores(sch[musician[sch["listener"]]], P, n)
    ssr_mus = _ssr(sm, sem)

    # H7: leave-one-passage-out, M0 = d2m, M1 = d2m + features
    y = _center(s)
    X0 = _center(d2m)[..., None]
    X1 = np.concatenate([X0, np.stack([_center(F[..., f]) for f in range(a.n_features)], -1)],
                        axis=-1)  # fmt: skip
    pr0, pr1 = _lopo(y, X0), _lopo(y, X1)
    sst = np.sum(y**2, axis=1)
    sse0, sse1 = np.sum((y - pr0) ** 2, axis=1), np.sum((y - pr1) ** 2, axis=1)

    def gain(idx: np.ndarray) -> float:
        t = sst[idx].sum()
        return float((sse0[idx].sum() - sse1[idx].sum()) / t) / ssr if t > 0 else np.nan

    est = gain(np.arange(P))
    boots = np.array([gain(rng.integers(0, P, P)) for _ in range(a.n_boot)])
    lo, hi = np.nanpercentile(boots, [2.5, 97.5])
    r2_0 = 1 - sse0.sum() / sst.sum()
    r2_1 = 1 - sse1.sum() / sst.sum()

    # held-out pairwise accuracy of judgements (secondary metric)
    def acc(pred: np.ndarray) -> float:
        d = pred[sch["passage"], sch["winner"]] - pred[sch["passage"], sch["loser"]]
        return float(np.mean(np.where(d > 0, 1.0, np.where(d == 0, 0.5, 0.0))))

    comps = 2 * n_listeners * a.trials_per_listener / (P * n)
    return {
        "verdict": h7_verdict(est, lo, hi, a.delta),
        "gain_rel": est, "gain_lo": float(lo), "gain_hi": float(hi),
        "r2_m0": float(r2_0), "r2_m1": float(r2_1),
        "ssr": ssr, "shr": float(shr), "ssr_musicians": ssr_mus,
        "acc_m0": acc(pr0), "acc_m1": acc(pr1), "acc_true": acc(q),
        "comparisons_per_item": comps,
    }  # fmt: skip


def power_table_s04(base: S04Assumptions, n_grid: list[int], r2_feats: list[float], n_rep: int,
                    seed: int = 0, **overrides: object) -> pd.DataFrame:
    """Operating characteristics over listener counts and true feature effects."""
    a0 = dataclasses.replace(base, **overrides) if overrides else base
    out = []
    for r in r2_feats:
        a = dataclasses.replace(a0, r2_feat=r)
        for n in n_grid:
            rng = np.random.default_rng([seed, n, int(r * 1000), a.n_passages, a.n_perf])
            sims = pd.DataFrame([simulate_once(a, n, rng) for _ in range(n_rep)])
            out.append({
                "r2_feat": r, "n_listeners": n, "n_rep": n_rep,
                "comparisons_per_item": float(sims["comparisons_per_item"].iloc[0]),
                "p_supported": float((sims["verdict"] == "supported").mean()),
                "p_falsified": float((sims["verdict"] == "falsified").mean()),
                "p_inconclusive": float((sims["verdict"] == "inconclusive").mean()),
                "gain_rel_median": float(sims["gain_rel"].median()),
                "ssr_median": float(sims["ssr"].median()),
                "p_ssr_ge_0.8": float((sims["ssr"] >= 0.8).mean()),
                "shr_median": float(sims["shr"].median()),
                "ssr_musicians_median": float(sims["ssr_musicians"].median()),
                "acc_m0_median": float(sims["acc_m0"].median()),
                "acc_m1_median": float(sims["acc_m1"].median()),
                "acc_true_median": float(sims["acc_true"].median()),
            })  # fmt: skip
    return pd.DataFrame(out)
