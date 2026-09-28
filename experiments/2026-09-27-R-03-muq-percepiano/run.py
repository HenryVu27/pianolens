"""R-03 step 2: MLP head (CrescendAI's MuQStatsModel) and linear probes on pooled MuQ features.

Protocols (see README): (a) CrescendAI folds, selection on the evaluated fold; (b) same folds,
inner passage-grouped validation; (b-test) folds 0-3 -> the 181-key test set; (c) leave-work-out;
(d) leave-performer-out. Sensitivity: 300 frames; de-duplicated means. Layer sweep with ridge
probes chosen on inner validation. Rater parity and within-passage metrics on out-of-fold preds.

    uv run --extra torch --extra audio python experiments/2026-09-27-R-03-muq-percepiano/run.py
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from sklearn.linear_model import Ridge
from sklearn.model_selection import GroupShuffleSplit
from torch import nn

from pianolens.data.percepiano import (
    DIMENSIONS,
    load_percepiano_official_means,
    load_percepiano_ratings,
    percepiano_index,
)
from pianolens.eval import (
    bootstrap_ci,
    group_kfold,
    loo_means,
    pairwise_accuracy,
    r2,
    rater_parity,
    spearman,
)

HERE = Path(__file__).resolve().parent
ART = HERE / "artifacts"
SEEDS = (42, 123, 456, 789, 1337)
L912 = 13  # layer-axis index of the hidden_states[9:13] average
CFG = {"hidden_dim": 512, "dropout": 0.2, "lr": 1e-4, "wd": 1e-5, "clip": 1.0, "batch": 64,
       "max_epochs": 200, "patience": 15, "eta_min": 1e-6}
N_BOOT = 2000
torch.set_num_threads(4)


# --------------------------------------------------------------------------- metrics
# Predictions are (N, S, D): rows x seeds x dimensions; every metric is averaged over seeds and
# dimensions. Vectorised because the within-passage metrics run inside a cluster bootstrap.


def _as3(P):
    P = np.asarray(P, dtype=float)
    return P[:, None, :] if P.ndim == 2 else P


def r2_mean(y, p) -> float:
    """Mean over dimensions (and seeds) of per-dimension R² (= sklearn uniform_average)."""
    y = np.asarray(y, dtype=float)
    P = _as3(p)
    sst = ((y - y.mean(0)) ** 2).sum(0)  # (D,)
    sse = ((P - y[:, None, :]) ** 2).sum(0)  # (S, D)
    return float(np.mean(1 - sse / sst))


def _inv(groups):
    _, inv, cnt = np.unique(groups, return_inverse=True, return_counts=True)
    return inv, cnt


def _center(a, inv, k):
    sums = np.zeros((k,) + a.shape[1:])
    np.add.at(sums, inv, a)
    cnt = np.bincount(inv, minlength=k).reshape((k,) + (1,) * (a.ndim - 1))
    return a - (sums / cnt)[inv]


def within_r2(y, p, groups) -> float:
    inv, cnt = _inv(groups)
    m = cnt[inv] >= 2
    inv2, cnt2 = _inv(inv[m])
    y = np.asarray(y, dtype=float)[m]
    P = _as3(p)[m]
    return r2_mean(_center(y, inv2, len(cnt2)), _center(P, inv2, len(cnt2)))


def _pairs(groups):
    inv, cnt = _inv(groups)
    order = np.argsort(inv, kind="stable")
    bounds = np.concatenate([[0], np.cumsum(cnt)])
    a, b = [], []
    for g in range(len(cnt)):
        n = cnt[g]
        if n < 2:
            continue
        mem = order[bounds[g]:bounds[g + 1]]
        i, j = np.triu_indices(n, 1)
        a.append(mem[i])
        b.append(mem[j])
    return np.concatenate(a), np.concatenate(b)


def within_pairacc(y, p, groups) -> float:
    """Pairwise ordering accuracy over same-passage pairs; truth ties skipped, pred ties 0.5.
    Pooled over all pairs (like ``pianolens.eval.pairwise_accuracy(groups=)``), then averaged
    over dimensions and seeds."""
    a, b = _pairs(groups)
    y = np.asarray(y, dtype=float)
    P = _as3(p)
    t = np.sign(y[a] - y[b])  # (n_pairs, D)
    q = np.sign(P[a] - P[b])  # (n_pairs, S, D)
    valid = (t != 0)[:, None, :]
    score = np.where(q == 0, 0.5, (q == t[:, None, :]).astype(float))
    acc = (score * valid).sum(0) / valid.sum(0)
    return float(np.mean(acc))


def within_spearman(y, p, groups) -> float:
    """Spearman within each passage with >= 3 segments, averaged over passages, dims, seeds."""
    from scipy.stats import rankdata

    inv, cnt = _inv(groups)
    y = np.asarray(y, dtype=float)
    P = _as3(p)
    vals = []
    for g in np.flatnonzero(cnt >= 3):
        m = inv == g
        ry = rankdata(y[m], axis=0)  # (n, D)
        rp = rankdata(P[m], axis=0)  # (n, S, D)
        ry = ry - ry.mean(0)
        rp = rp - rp.mean(0)
        num = (rp * ry[:, None, :]).sum(0)
        den = np.sqrt((rp**2).sum(0) * (ry**2).sum(0)[None, :])
        with np.errstate(invalid="ignore", divide="ignore"):
            vals.append(num / den)
    return float(np.nanmean(np.stack(vals)))


def selfcheck() -> None:
    """The vectorised metrics must equal pianolens.eval's on random data."""
    rng = np.random.default_rng(0)
    g = rng.integers(0, 12, 90)
    y = rng.integers(1, 6, (90, 3)).astype(float)
    p = y + rng.normal(0, 2, (90, 3))
    assert np.isclose(r2_mean(y, p), np.mean([r2(y[:, d], p[:, d]) for d in range(3)]))
    ref = np.mean([pairwise_accuracy(y[:, d], p[:, d], groups=g) for d in range(3)])
    assert np.isclose(within_pairacc(y, p, g), ref)
    sp = [spearman(y[g == k, d], p[g == k, d]) for k in np.unique(g) if (g == k).sum() >= 3
          for d in range(3)]
    assert np.isclose(within_spearman(y, p, g), np.nanmean(sp))
    yc = y - pd.DataFrame(y).groupby(g).transform("mean").to_numpy()
    pc = p - pd.DataFrame(p).groupby(g).transform("mean").to_numpy()
    assert np.isclose(within_r2(y, p, g), np.mean([r2(yc[:, d], pc[:, d]) for d in range(3)]))


def summarize(y, P, passage, seed=0) -> dict:
    """Pooled and within-passage metrics, seed-averaged, with passage-cluster bootstrap CIs."""
    P = _as3(P)
    out = {}
    for name, fn, needs_g, nb in [("r2", r2_mean, False, N_BOOT),
                                  ("within_r2", within_r2, True, N_BOOT),
                                  ("within_pairacc", within_pairacc, True, 1000),
                                  ("within_spearman", within_spearman, True, 500)]:
        res = bootstrap_ci(fn, y, P, groups=passage, n_boot=nb, seed=seed, pass_groups=needs_g)
        out[name] = [round(res.estimate, 4), round(res.low, 4), round(res.high, 4)]
    out["r2_per_seed"] = [round(r2_mean(y, P[:, s]), 4) for s in range(P.shape[1])]
    return out


# --------------------------------------------------------------------------- head


class Head(nn.Module):
    def __init__(self, d_in: int, h: int, drop: float, n_out: int = 19):
        super().__init__()
        self.clf = nn.Sequential(nn.Linear(d_in, h), nn.GELU(), nn.Dropout(drop),
                                 nn.Linear(h, h), nn.GELU(), nn.Dropout(drop),
                                 nn.Linear(h, n_out), nn.Sigmoid())

    def forward(self, x):
        return self.clf(x)


def predict(model, X) -> np.ndarray:
    model.eval()
    with torch.no_grad():
        return model(torch.from_numpy(X)).numpy()


def train_head(Xtr, Ytr, Xval, Yval, seed: int) -> tuple[nn.Module, int]:
    """CrescendAI's training loop; returns the best-validation-R² model and its epoch."""
    torch.manual_seed(seed)
    g = torch.Generator().manual_seed(seed)
    model = Head(Xtr.shape[1], CFG["hidden_dim"], CFG["dropout"], Ytr.shape[1])
    opt = torch.optim.AdamW(model.parameters(), lr=CFG["lr"], weight_decay=CFG["wd"])
    sch = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=CFG["max_epochs"],
                                                     eta_min=CFG["eta_min"])
    Xt, Yt = torch.from_numpy(Xtr), torch.from_numpy(Ytr)
    loss_fn = nn.MSELoss()
    best, best_ep, best_state, bad = -np.inf, -1, None, 0
    for ep in range(CFG["max_epochs"]):
        model.train()
        perm = torch.randperm(len(Xt), generator=g)
        for i in range(0, len(Xt), CFG["batch"]):
            b = perm[i:i + CFG["batch"]]
            opt.zero_grad()
            loss = loss_fn(model(Xt[b]), Yt[b])
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), CFG["clip"])
            opt.step()
        sch.step()
        v = r2_mean(Yval, predict(model, Xval))
        if v > best:
            best, best_ep, bad = v, ep, 0
            best_state = {k: t.clone() for k, t in model.state_dict().items()}
        else:
            bad += 1
            if bad >= CFG["patience"]:
                break
    model.load_state_dict(best_state)
    return model, best_ep


def inner_split(groups, seed: int, frac: float = 0.15):
    gss = GroupShuffleSplit(n_splits=1, test_size=frac, random_state=seed)
    tr, va = next(gss.split(np.zeros(len(groups)), groups=groups))
    return tr, va


def run_protocol(X, Y, passage, folds, mode: str, seeds=SEEDS):
    """folds: list of (train_idx, test_idx). mode 'paper' (val = test fold) or 'inner'.

    Returns OOF preds (N, S, 19) (NaN outside the test folds) and best epochs.
    """
    P = np.full((len(Y), len(seeds), Y.shape[1]), np.nan, dtype=np.float32)
    epochs = []
    for si, seed in enumerate(seeds):
        for fi, (tr, te) in enumerate(folds):
            if mode == "paper":
                model, ep = train_head(X[tr], Y[tr], X[te], Y[te], seed + fi)
            else:
                itr, iva = inner_split(passage[tr], seed + fi)
                model, ep = train_head(X[tr[itr]], Y[tr[itr]], X[tr[iva]], Y[tr[iva]], seed + fi)
            P[te, si] = predict(model, X[te])
            epochs.append(ep)
    return P, epochs


# --------------------------------------------------------------------------- probes


def ridge_sweep(Z, Y, passage, folds, alphas, seed=42):
    """Per outer fold: choose (layer, alpha) on an inner passage split; refit on the full
    training part; score the outer fold. Also per-layer OOF preds (alpha chosen on inner val
    per layer), for the descriptive table."""
    n_layers = Z.shape[1]
    P_sel = np.full(Y.shape, np.nan)
    P_layer = np.full((n_layers,) + Y.shape, np.nan)
    chosen = []
    for fi, (tr, te) in enumerate(folds):
        itr, iva = inner_split(passage[tr], seed + fi)
        scores = np.full((n_layers, len(alphas)), -np.inf)
        for k in range(n_layers):
            X = Z[:, k, :].astype(np.float64)
            mu, sd = X[tr[itr]].mean(0), X[tr[itr]].std(0) + 1e-8
            Xs = (X - mu) / sd
            for ai, a in enumerate(alphas):
                m = Ridge(alpha=a).fit(Xs[tr[itr]], Y[tr[itr]])
                scores[k, ai] = r2_mean(Y[tr[iva]], m.predict(Xs[tr[iva]]))
            # per-layer refit with that layer's best alpha
            mu, sd = X[tr].mean(0), X[tr].std(0) + 1e-8
            a = alphas[int(np.argmax(scores[k]))]
            P_layer[k, te] = Ridge(alpha=a).fit((X[tr] - mu) / sd, Y[tr]).predict((X[te] - mu) / sd)
        k, ai = np.unravel_index(int(np.argmax(scores)), scores.shape)
        chosen.append({"fold": fi, "layer": int(k), "alpha": float(alphas[ai]),
                       "inner_r2": round(float(scores[k, ai]), 4)})
        P_sel[te] = P_layer[k, te]
    return P_sel, P_layer, chosen


# --------------------------------------------------------------------------- rater parity


def parity_tables(pids, pred, ratings, passage):
    """Per dimension: rater parity (Pearson vs leave-one-rater-out mean) and within-passage
    pairwise parity. pred: (N, 19) on any scale."""
    rows = []
    for d, dim in enumerate(DIMENSIONS):
        M = ratings.matrix(dim).reindex(pids)
        R = M.to_numpy(dtype=float)
        rp = rater_parity(R, pred[:, d], method="pearson", min_segments=10, n_boot=1000, seed=d)
        s = rp.summary
        # within-passage pairwise parity
        T = loo_means(R)
        acc_r, acc_m = [], []
        for j in range(R.shape[1]):
            ok = np.isfinite(R[:, j]) & np.isfinite(T[:, j])
            if ok.sum() < 2:
                continue
            idx = np.flatnonzero(ok)
            g = passage[idx]
            same = g[:, None] == g[None, :]
            iu = np.triu_indices(len(idx), 1)
            same = same[iu]
            if same.sum() < 10:
                continue
            a, b = iu[0][same], iu[1][same]
            t = np.sign(T[idx[a], j] - T[idx[b], j])
            keep = t != 0
            if keep.sum() < 10:
                continue
            rr = np.sign(R[idx[a], j] - R[idx[b], j])[keep]
            mm = np.sign(pred[idx[a], d] - pred[idx[b], d])[keep]
            t = t[keep]
            acc_r.append(np.mean(np.where(rr == 0, 0.5, rr == t)))
            acc_m.append(np.mean(np.where(mm == 0, 0.5, mm == t)))
        acc_r, acc_m = np.array(acc_r), np.array(acc_m)
        rng = np.random.default_rng(d)
        picks = rng.integers(0, len(acc_r), size=(1000, len(acc_r)))
        dci = np.quantile((acc_m - acc_r)[picks].mean(1), [0.025, 0.975])
        rows.append({
            "dimension": dim, "n_raters": s["n_raters"],
            "rater_r": round(s["rater_r_mean_fisher"], 3),
            "model_r": round(s["model_r_mean_fisher"], 3),
            "diff": round(s["diff_mean"], 3),
            "diff_ci": [round(x, 3) for x in s["diff_mean_ci"]],
            "wp_n_raters": int(len(acc_r)),
            "wp_rater_acc": round(float(acc_r.mean()), 3),
            "wp_model_acc": round(float(acc_m.mean()), 3),
            "wp_diff_ci": [round(float(x), 3) for x in dci],
        })
    return pd.DataFrame(rows)


def verdict_counts(df, col_ci):
    lo = df[col_ci].map(lambda c: c[0])
    hi = df[col_ci].map(lambda c: c[1])
    return {"model_above": int((lo > 0).sum()), "model_below": int((hi < 0).sum()),
            "tied": int(((lo <= 0) & (hi >= 0)).sum())}


# --------------------------------------------------------------------------- main


def code_hash() -> str:
    repo = HERE.parents[1]
    h = hashlib.sha256()
    for p in sorted(list((repo / "src").rglob("*.py")) + [HERE / "run.py", HERE / "extract.py"]):
        h.update(p.read_bytes())
    return h.hexdigest()[:12]


def main() -> None:
    selfcheck()
    t0 = time.time()
    Z = np.load(ART / "muq_pooled.npz")
    stems = list(Z["stems"])
    idx = percepiano_index().set_index("performance_id")
    pids = np.array([f"percepiano:{s}" for s in stems])
    meta = idx.loc[pids]
    passage_all = (meta.work + "_" + meta.bars.astype(str) + "b_" + meta.segment.astype(str)
                   ).to_numpy()
    work_all = meta.piece_id.to_numpy()
    perf_all = meta.performer_id.to_numpy()

    official = load_percepiano_official_means()
    ratings = load_percepiano_ratings()
    dedup = ratings.mean()[list(DIMENSIONS)] / 7.0
    lab = np.isin(pids, official.index)
    print("labeled segments:", lab.sum())

    folds_json = json.loads((ART / "audio_fold_assignments.json").read_text())
    fold_of = {}
    for f in range(4):
        for k in folds_json[f"fold_{f}"]:
            fold_of[k] = f
    test_keys = set(folds_json["test"])

    def targets(which, rows):
        src = official if which == "official" else dedup
        return src.loc[pids[rows], list(DIMENSIONS)].to_numpy(dtype=np.float32)

    results: dict = {"code_hash": code_hash(), "seeds": SEEDS, "cfg": CFG}
    oof: dict = {}

    # ---------- CV universe for (a), (b): labeled keys in folds 0-3
    cv = np.flatnonzero(lab & np.isin(stems, list(fold_of)))
    fold_cv = np.array([fold_of[stems[i]] for i in cv])
    pas_cv = passage_all[cv]
    folds_cv = [(np.flatnonzero(fold_cv != f), np.flatnonzero(fold_cv == f)) for f in range(4)]
    assert not (set(pas_cv[folds_cv[0][0]]) & set(pas_cv[folds_cv[0][1]]))
    results["n_cv"] = int(len(cv))

    def fold_r2(Y, P):
        return [round(r2_mean(Y[te], P[te]), 4) for _, te in folds_cv]

    for trunc in (1000, 300):
        X = Z[f"pooled_{trunc}"][:, L912, :]
        for tgt in (["official", "dedup"] if trunc == 1000 else ["official"]):
            Y = targets(tgt, cv)
            for mode, name in (("paper", "a"), ("inner", "b")):
                key = f"{name}_{tgt}_{trunc}"
                P, eps = run_protocol(X[cv], Y, pas_cv, folds_cv, mode)
                res = summarize(Y, P, pas_cv)
                res["fold_r2"] = fold_r2(Y, P)
                res["fold_r2_seed42"] = [round(r2_mean(Y[te], P[te, 0]), 4) for _, te in folds_cv]
                res["best_epoch_median"] = float(np.median(eps))
                results[key] = res
                oof[key] = P
                print(key, res["r2"], res["fold_r2"], f"{time.time() - t0:.0f}s", flush=True)

    # paired difference (a) - (b), primary config
    Y = targets("official", cv)
    Pa, Pb = oof["a_official_1000"], oof["b_official_1000"]

    def diff(y, pa, pb):
        return r2_mean(y, pa) - r2_mean(y, pb)
    d = bootstrap_ci(diff, Y, Pa, Pb, groups=pas_cv, n_boot=N_BOOT)
    results["a_minus_b"] = [round(d.estimate, 4), round(d.low, 4), round(d.high, 4)]

    # baselines on the CV universe
    base_tm = np.zeros_like(Y)
    for tr, te in folds_cv:
        base_tm[te] = Y[tr].mean(0)
    results["baseline_trainmean_cv"] = summarize(Y, base_tm, pas_cv)
    loo_pm = np.zeros_like(Y)
    for i in range(len(Y)):
        m = (pas_cv == pas_cv[i])
        m[i] = False
        loo_pm[i] = Y[m].mean(0) if m.any() else Y.mean(0)
    results["reference_loo_passage_mean_cv"] = summarize(Y, loo_pm, pas_cv)

    # ---------- (b-test): folds 0-3 -> test keys
    X = Z["pooled_1000"][:, L912, :]
    te_rows = np.flatnonzero(lab & np.isin(stems, list(test_keys)))
    Ytr, Yte = targets("official", cv), targets("official", te_rows)
    Pt = np.zeros((len(te_rows), len(SEEDS), 19), dtype=np.float32)
    for si, seed in enumerate(SEEDS):
        itr, iva = inner_split(pas_cv, seed)
        model, _ = train_head(X[cv][itr], Ytr[itr], X[cv][iva], Ytr[iva], seed)
        Pt[:, si] = predict(model, X[te_rows])
    results["n_test"] = int(len(te_rows))
    results["btest_official_1000"] = summarize(Yte, Pt, passage_all[te_rows])
    results["baseline_trainmean_test"] = summarize(Yte, np.repeat(Ytr.mean(0, keepdims=True),
                                                                  len(Yte), 0),
                                                   passage_all[te_rows])
    print("b-test", results["btest_official_1000"]["r2"], flush=True)

    # ---------- (c) leave-work-out and (d) leave-performer-out on all labeled segments
    al = np.flatnonzero(lab)
    pas_al, work_al, perf_al = passage_all[al], work_all[al], perf_all[al]
    works = sorted(set(work_al))
    folds_lwo = [(np.flatnonzero(work_al != w), np.flatnonzero(work_al == w)) for w in works]
    folds_lpo = group_kfold(perf_al, 4, seed=0)
    results["n_all"] = int(len(al))
    results["works"] = works
    for tgt in ("official", "dedup"):
        Y = targets(tgt, al)
        for name, folds in (("c", folds_lwo), ("d", folds_lpo)):
            key = f"{name}_{tgt}_1000"
            P, eps = run_protocol(X[al], Y, pas_al, folds, "inner")
            res = summarize(Y, P, pas_al)
            res["best_epoch_median"] = float(np.median(eps))
            if name == "c":
                res["per_work"] = {}
                for w, (tr, te) in zip(works, folds_lwo, strict=True):
                    r = summarize(Y[te], P[te], pas_al[te], seed=1)
                    bt = np.repeat(Y[tr].mean(0, keepdims=True), len(te), 0)
                    r["trainmean_r2"] = round(r2_mean(Y[te], bt), 4)
                    r["n"] = int(len(te))
                    res["per_work"][w] = r
            results[key] = res
            oof[key] = P
            print(key, res["r2"], f"{time.time() - t0:.0f}s", flush=True)
    Y = targets("official", al)
    for name, folds in (("c", folds_lwo), ("d", folds_lpo)):
        bt = np.zeros_like(Y)
        for tr, te in folds:
            bt[te] = Y[tr].mean(0)
        results[f"baseline_trainmean_{name}"] = summarize(Y, bt, pas_al)

    # ---------- layer sweep: ridge probes, chosen on inner validation
    alphas = np.logspace(-1, 4, 11)
    Zall = Z["pooled_1000"]
    sweep = {}
    for name, rows, folds, pas in (("b", cv, folds_cv, pas_cv), ("c", al, folds_lwo, pas_al)):
        Y = targets("official", rows)
        P_sel, P_layer, chosen = ridge_sweep(Zall[rows], Y, pas, folds, alphas)
        sweep[name] = {"selected": summarize(Y, P_sel, pas), "chosen": chosen,
                       "per_layer_r2": [round(r2_mean(Y, P_layer[k]), 4)
                                        for k in range(P_layer.shape[0])],
                       "per_layer_within_pairacc": [round(within_pairacc(Y, P_layer[k], pas), 4)
                                                    for k in range(P_layer.shape[0])]}
        oof[f"ridge_{name}"] = P_sel
        print("ridge", name, sweep[name]["selected"]["r2"], chosen, flush=True)
    results["ridge_sweep"] = sweep

    # ---------- rater parity on (b) and (c) OOF predictions (seed-averaged)
    for key, rows, pas in (("b_official_1000", cv, pas_cv), ("c_official_1000", al, pas_al)):
        pred = np.nanmean(oof[key], axis=1)
        tab = parity_tables(pids[rows], pred, ratings, pas)
        tab.to_csv(ART / f"parity_{key}.csv", index=False)
        results[f"parity_{key}"] = {
            "mean_rater_r": round(float(tab.rater_r.mean()), 3),
            "mean_model_r": round(float(tab.model_r.mean()), 3),
            "pearson_counts": verdict_counts(tab, "diff_ci"),
            "mean_wp_rater_acc": round(float(tab.wp_rater_acc.mean()), 3),
            "mean_wp_model_acc": round(float(tab.wp_model_acc.mean()), 3),
            "within_passage_counts": verdict_counts(tab, "wp_diff_ci"),
        }
        print("parity", key, results[f"parity_{key}"], flush=True)

    # per-dimension pooled and within-passage numbers for (a), (b), (c)
    perdim = []
    for key, rows, pas in (("a_official_1000", cv, pas_cv), ("b_official_1000", cv, pas_cv),
                           ("c_official_1000", al, pas_al)):
        Y = targets("official", rows)
        P = oof[key]
        for d, dim in enumerate(DIMENSIONS):
            perdim.append({"protocol": key, "dimension": dim,
                           "r2": r2_mean(Y[:, [d]], P[:, :, [d]]),
                           "within_pairacc": within_pairacc(Y[:, [d]], P[:, :, [d]], pas)})
    pd.DataFrame(perdim).round(4).to_csv(ART / "per_dimension.csv", index=False)

    results["wall_sec"] = round(time.time() - t0, 1)
    try:
        results["fluidsynth"] = subprocess.run(["fluidsynth", "--version"], capture_output=True,
                                               text=True).stdout.split("\n")[0]
    except OSError:
        pass
    (ART / "results.json").write_text(json.dumps(results, indent=1, default=str))
    np.savez_compressed(ART / "oof_predictions.npz", pids=pids, **oof)
    print("done", results["wall_sec"])


if __name__ == "__main__":
    main()
