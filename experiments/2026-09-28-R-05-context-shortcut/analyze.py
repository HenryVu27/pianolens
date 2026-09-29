"""R-05 step 2: skill classifiers on context-matched vs confounded simulated recordings (H8).

Reads artifacts/embeddings.npz + sample.csv + excerpt_stats.csv (build.py). Writes
artifacts/results.json, artifacts/oof_scores.npz and prints the tables for the README.

Primary (pre-registered): binary beginner (child + adult beginner) vs advanced (child
professional + piano teacher + virtuoso), MuQ L9-12 mean||std, StandardScaler + L2 logistic
regression with C chosen by inner grouped CV on AUC, outer 5-fold grouped CV (groups = connected
components of piece and recording), fold seed 0, group bootstrap 2,000.

Conditions (every clip is in every condition; only the context of its audio changes):
  M_<ctx>   train and test with every clip in one context (4 matched datasets)
  CC        confounded: each clip in the context mapped from its real MAJEPPA recording_type
  CS        trained on confounded, tested with contexts permuted among the test fold (K = 20)
  CA        trained on confounded, test contexts drawn from the other class's context mix (K = 20)
  Cm_<ctx>  trained on confounded, every test clip in one context
  RR        negative control: contexts permuted over the whole set once (independent of skill)
            for train and test

Usage: uv run python experiments/2026-09-28-R-05-context-shortcut/analyze.py [--layer 13]
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
from common import ADVANCED, BEGINNER, LEVEL_GROUP3, auc, cv_groups
from joblib import Parallel, delayed
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score
from sklearn.preprocessing import StandardScaler

from pianolens.eval.splits import check_disjoint, group_kfold

HERE = Path(__file__).resolve().parent
ART = HERE / "artifacts"
C_GRID = (1e-4, 1e-3, 1e-2, 1e-1)
K_PERM = 20
N_BOOT = 2000
MARGIN = 0.02
SEED = 0


def fit_lr(x, y, c, multi=False):
    sc = StandardScaler().fit(x)
    m = LogisticRegression(C=c, max_iter=3000)
    m.fit(sc.transform(x), y)
    return sc, m


def score(sc, m, x, multi=False):
    z = sc.transform(x)
    return m.predict(z) if multi else m.decision_function(z)


def choose_c(x, y, g, multi=False):
    """Inner grouped 4-fold CV on the training rows only."""
    best, best_c = -np.inf, C_GRID[0]
    for c in C_GRID:
        vals = []
        for tr, va in group_kfold(g, 4, seed=SEED):
            sc, m = fit_lr(x[tr], y[tr], c, multi)
            s = score(sc, m, x[va], multi)
            vals.append(balanced_accuracy_score(y[va], s) if multi else auc(y[va], s))
        if np.mean(vals) > best:
            best, best_c = float(np.mean(vals)), c
    return best_c


def run_fold(fold, tr, te, emb, y, g, ctx_train, test_sets, multi=False):
    """Train on emb[tr, ctx_train[tr]]; score every named test context assignment."""
    xtr = emb[tr, ctx_train[tr]]
    c = choose_c(xtr, y[tr], g[tr], multi)
    sc, m = fit_lr(xtr, y[tr], c, multi)
    out = {name: [score(sc, m, emb[te, a[te]], multi) for a in assigns]
           for name, assigns in test_sets.items()}
    return fold, c, out


def oof(emb, y, g, folds, ctx_train, test_sets, multi=False, n_jobs=5):
    """Out-of-fold scores: {name: (K, n)} plus the chosen C per fold."""
    n = len(y)
    res = Parallel(n_jobs=n_jobs)(
        delayed(run_fold)(f, tr, te, emb, y, g, ctx_train, test_sets, multi)
        for f, (tr, te) in enumerate(folds))
    scores = {name: np.full((len(a), n), np.nan) for name, a in test_sets.items()}
    cs = {}
    for f, c, out in res:
        te = folds[f][1]
        cs[f] = c
        for name, lst in out.items():
            for k, s in enumerate(lst):
                scores[name][k, te] = s
    return scores, cs


def perm_within_folds(ctx, folds, rng):
    a = ctx.copy()
    for _, te in folds:
        a[te] = ctx[te][rng.permutation(len(te))]
    return a


def anti_assign(ctx, y, rng, n_ctx):
    """Each clip gets a context drawn from the other class's empirical context distribution."""
    a = np.empty_like(ctx)
    for cls in (0, 1):
        p = np.bincount(ctx[y != cls], minlength=n_ctx) / np.sum(y != cls)
        idx = np.flatnonzero(y == cls)
        a[idx] = rng.choice(n_ctx, size=len(idx), p=p)
    return a


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--layer", type=int, default=13, help="13 = L9-12 average (primary)")
    ap.add_argument("--fold-seed", type=int, default=SEED)
    ap.add_argument("--skip-secondary", action="store_true")
    args = ap.parse_args()
    t0 = time.time()
    z = np.load(ART / "embeddings.npz")
    contexts = [str(c) for c in z["contexts"]]
    emb_all = (z["l912"] if args.layer == 13 else z["layers"][:, :, args.layer].astype(np.float32))
    sample = pd.read_csv(ART / "sample.csv")
    assert list(z["ids"]) == sample.performance_id.tolist()
    stats = pd.read_csv(ART / "excerpt_stats.csv").set_index("performance_id").loc[
        sample.performance_id].reset_index()
    ctx_all = sample.context_real.map({c: i for i, c in enumerate(contexts)}).to_numpy()
    n_ctx = len(contexts)
    tag = f"layer{args.layer}_seed{args.fold_seed}"
    results: dict = {"layer": args.layer, "fold_seed": args.fold_seed, "contexts": contexts}

    # ---------------------------------------------------------------- primary: binary
    b = sample.expertise_level.isin(BEGINNER + ADVANCED).to_numpy()
    emb, ctx = emb_all[b], ctx_all[b]
    y = sample.expertise_level[b].isin(ADVANCED).to_numpy().astype(int)
    sb = sample[b].reset_index(drop=True)
    g = cv_groups(sb)
    folds = group_kfold(g, 5, seed=args.fold_seed)
    check_disjoint(g, folds)
    rng = np.random.default_rng(1)
    ctx_rand = ctx[rng.permutation(len(ctx))]
    perms = [perm_within_folds(ctx, folds, rng) for _ in range(K_PERM)]
    antis = [anti_assign(ctx, y, rng, n_ctx) for _ in range(K_PERM)]
    const = {c: np.full(len(y), i) for i, c in enumerate(contexts)}
    results["n_binary"] = int(len(y))
    results["n_advanced"] = int(y.sum())
    results["n_groups"] = int(g.max() + 1)
    results["context_by_class"] = {
        cls: {c: int(np.sum((y == k) & (ctx == i))) for i, c in enumerate(contexts)}
        for k, cls in enumerate(("beginner", "advanced"))}

    scores: dict[str, np.ndarray] = {}
    chosen_c: dict[str, dict] = {}
    for c in contexts:
        s, cs = oof(emb, y, g, folds, const[c], {f"M_{c}": [const[c]]})
        scores.update(s)
        chosen_c[f"M_{c}"] = cs
    s, cs = oof(emb, y, g, folds, ctx, {"CC": [ctx], "CS": perms, "CA": antis,
                                         **{f"Cm_{c}": [const[c]] for c in contexts}})
    scores.update(s)
    chosen_c["C"] = cs
    s, cs = oof(emb, y, g, folds, ctx_rand, {"RR": [ctx_rand]})
    scores.update(s)
    chosen_c["R"] = cs
    results["chosen_C"] = chosen_c

    # baselines: context label only (the pure shortcut), symbolic MIDI stats, trivial
    onehot = np.eye(n_ctx)[ctx]
    sym = np.column_stack([np.log(stats.note_rate[b]), stats.vel_mean[b], stats.vel_sd[b],
                           stats.pitch_mean[b], np.log(stats.n_notes[b])])
    for name, x in (("ctx_oracle", onehot), ("symbolic", sym)):
        sc_ = np.full(len(y), np.nan)
        for tr, te in folds:
            scl, m = fit_lr(x[tr], y[tr], 1.0)
            sc_[te] = score(scl, m, x[te])
        scores[name] = sc_[None]

    # point estimates and group bootstrap of every AUC and the deltas, same resample
    names = list(scores)
    members = [np.flatnonzero(g == k) for k in range(g.max() + 1)]

    def summary(idx):
        a = {nm: float(np.mean([auc(y[idx], s[idx]) for s in scores[nm]])) for nm in names}
        m_mean = float(np.mean([a[f"M_{c}"] for c in contexts]))
        a["M_mean"] = m_mean
        a["d_infl"] = a["CC"] - m_mean
        a["d_short"] = a["CC"] - a["CS"]
        a["d_anti"] = a["CC"] - a["CA"]
        a["d_negctrl"] = a["RR"] - m_mean
        return a

    est = summary(np.arange(len(y)))
    brng = np.random.default_rng(2)
    reps = []
    for _ in range(N_BOOT):
        pick = brng.integers(0, len(members), len(members))
        reps.append(summary(np.concatenate([members[i] for i in pick])))
    reps_df = pd.DataFrame(reps)
    table = {k: {"est": round(est[k], 4),
                 "lo": round(float(reps_df[k].quantile(0.025)), 4),
                 "hi": round(float(reps_df[k].quantile(0.975)), 4)} for k in est}
    results["binary_auc"] = table
    lo_i, hi_i = table["d_infl"]["lo"], table["d_infl"]["hi"]
    lo_s, hi_s = table["d_short"]["lo"], table["d_short"]["hi"]
    if lo_i > 0 and lo_s > 0:
        verdict = "supported"
    elif all(-MARGIN < v < MARGIN for v in (lo_i, hi_i, lo_s, hi_s)):
        verdict = "falsified"
    else:
        verdict = "inconclusive"
    results["verdict_rule"] = verdict
    np.savez(ART / f"oof_scores_{tag}.npz", y=y, groups=g, ctx=ctx,
             **{k: v for k, v in scores.items()})
    print(f"[{tag}] binary n={len(y)} groups={g.max() + 1}  verdict rule: {verdict}")
    for k, v in table.items():
        print(f"  {k:16s} {v['est']:+.4f} [{v['lo']:+.4f}, {v['hi']:+.4f}]")

    # per-level mean CC vs M_mean score is not comparable across models; report advanced-level
    # AUC against beginners, per advanced level, for CC and M_mean (descriptive)
    lv = sb.expertise_level.to_numpy()
    per_level = {}
    for level in ADVANCED:
        idx = np.flatnonzero((lv == level) | (y == 0))
        per_level[level] = {
            "CC": round(auc(y[idx], scores["CC"][0][idx]), 4),
            "CS": round(float(np.mean([auc(y[idx], s[idx]) for s in scores["CS"]])), 4),
            "M_mean": round(float(np.mean([auc(y[idx], scores[f"M_{c}"][0][idx])
                                           for c in contexts])), 4)}
    results["per_advanced_level_vs_beginners"] = per_level
    print("  per advanced level vs beginners:", json.dumps(per_level))

    if not args.skip_secondary:
        # ------------------------------------------------------------ secondary: 3 groups
        y3 = sample.expertise_level.map(LEVEL_GROUP3).to_numpy()
        g3 = cv_groups(sample)
        folds3 = group_kfold(g3, 5, seed=args.fold_seed)
        rng3 = np.random.default_rng(3)
        perms3 = [perm_within_folds(ctx_all, folds3, rng3) for _ in range(K_PERM)]
        const3 = {c: np.full(len(y3), i) for i, c in enumerate(contexts)}
        s3: dict[str, np.ndarray] = {}
        for c in contexts:
            s3.update(oof(emb_all, y3, g3, folds3, const3[c], {f"M_{c}": [const3[c]]},
                          multi=True)[0])
        s3.update(oof(emb_all, y3, g3, folds3, ctx_all, {"CC": [ctx_all], "CS": perms3},
                      multi=True)[0])
        members3 = [np.flatnonzero(g3 == k) for k in range(g3.max() + 1)]

        def bal(idx):
            a = {nm: float(np.mean([balanced_accuracy_score(y3[idx], s[idx].astype(int))
                                    for s in v])) for nm, v in s3.items()}
            a["M_mean"] = float(np.mean([a[f"M_{c}"] for c in contexts]))
            a["d_infl"] = a["CC"] - a["M_mean"]
            a["d_short"] = a["CC"] - a["CS"]
            return a

        est3 = bal(np.arange(len(y3)))
        r3 = []
        for _ in range(500):
            pick = brng.integers(0, len(members3), len(members3))
            r3.append(bal(np.concatenate([members3[i] for i in pick])))
        r3 = pd.DataFrame(r3)
        results["group3_balanced_acc"] = {
            k: {"est": round(est3[k], 4), "lo": round(float(r3[k].quantile(0.025)), 4),
                "hi": round(float(r3[k].quantile(0.975)), 4)} for k in est3}
        print("  3-group balanced accuracy (chance 0.333):")
        for k, v in results["group3_balanced_acc"].items():
            print(f"    {k:16s} {v['est']:+.4f} [{v['lo']:+.4f}, {v['hi']:+.4f}]")

        # ------------------------------------------------------------ context decodability
        # 4-class context from embeddings: every clip in every context (6,000 rows), grouped
        # by the clip's group so a clip's 4 versions share a fold. Fixed C = 1e-2 (no tuning).
        n = len(sample)
        xc = emb_all.reshape(n * n_ctx, -1)
        yc = np.tile(np.arange(n_ctx), n)
        gc = np.repeat(g3, n_ctx)
        pred = np.full(len(yc), -1)
        for tr, te in group_kfold(gc, 5, seed=args.fold_seed):
            scl, m = fit_lr(xc[tr], yc[tr], 1e-2, multi=True)
            pred[te] = score(scl, m, xc[te], multi=True)
        conf = pd.crosstab(pd.Series(yc, name="true").map(dict(enumerate(contexts))),
                           pd.Series(pred, name="pred").map(dict(enumerate(contexts))))
        results["context_decoding"] = {
            "balanced_acc": round(float(balanced_accuracy_score(yc, pred)), 4),
            "chance": 1 / n_ctx, "confusion": conf.to_dict()}
        print(f"  context decoding balanced acc {results['context_decoding']['balanced_acc']}"
              f" (chance {1 / n_ctx:.2f})")
        print(conf.to_string())

    results["wall_s"] = round(time.time() - t0, 1)
    (ART / f"results_{tag}.json").write_text(json.dumps(results, indent=2))
    print(f"wall {results['wall_s']} s")


if __name__ == "__main__":
    main()
