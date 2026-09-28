"""R-03 post-audit corrections (2026-09-27). Reporting only: no MuQ re-extraction.

Reuses run.py unchanged (imported) and the cached `muq_pooled.npz` / `oof_predictions.npz`.

1. (a) fold-mean R² next to the pooled number.
2. (c) with D960 mv2 + mv3 merged into one work (3 folds): retrains the MLP head (5 seeds, same
   recipe and inner split rule as (c)) on the cached pooled embeddings.
3. No-Score rows: the same OOF predictions evaluated without the deadpan Score/Score2 renditions.
4. Rater parity: seed-ensembled vs seed-averaged metrics, and within-passage parity restricted to
   pairs the rater did not tie.

Writes `artifacts/postaudit.json` and `artifacts/oof_predictions_postaudit.npz`.

    uv run --extra torch --extra audio python \
        experiments/2026-09-27-R-03-muq-percepiano/postaudit.py
"""

from __future__ import annotations

import importlib.util
import json
import time
from pathlib import Path

import numpy as np

from pianolens.data.percepiano import (
    DIMENSIONS,
    load_percepiano_official_means,
    load_percepiano_ratings,
    percepiano_index,
)
from pianolens.eval import loo_means

HERE = Path(__file__).resolve().parent
ART = HERE / "artifacts"
_spec = importlib.util.spec_from_file_location("r03run", HERE / "run.py")
R = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(R)


def wp_parity(pids, pred, ratings, passage, keep_rows=None, untied=False):
    """Within-passage pairwise parity as in run.parity_tables, optionally only on rows in
    keep_rows and only on pairs the held-out rater did not tie. Returns per-dim rater/model acc
    and the share of the rater's same-passage pairs (with an untied target) that the rater tied."""
    out = []
    for d, dim in enumerate(DIMENSIONS):
        Rm = ratings.matrix(dim).reindex(pids).to_numpy(dtype=float)
        T = loo_means(Rm)
        acc_r, acc_m, n_tie, n_all = [], [], 0, 0
        for j in range(Rm.shape[1]):
            ok = np.isfinite(Rm[:, j]) & np.isfinite(T[:, j])
            if keep_rows is not None:
                ok &= keep_rows
            if ok.sum() < 2:
                continue
            idx = np.flatnonzero(ok)
            g = passage[idx]
            iu = np.triu_indices(len(idx), 1)
            same = (g[:, None] == g[None, :])[iu]
            if same.sum() < 10:
                continue
            a, b = iu[0][same], iu[1][same]
            t = np.sign(T[idx[a], j] - T[idx[b], j])
            keep = t != 0
            if keep.sum() < 10:
                continue
            rr = np.sign(Rm[idx[a], j] - Rm[idx[b], j])[keep]
            mm = np.sign(pred[idx[a], d] - pred[idx[b], d])[keep]
            t = t[keep]
            n_tie += int((rr == 0).sum())
            n_all += len(rr)
            if untied:
                k2 = rr != 0
                if k2.sum() < 10:
                    continue
                rr, mm, t = rr[k2], mm[k2], t[k2]
            acc_r.append(np.mean(np.where(rr == 0, 0.5, rr == t)))
            acc_m.append(np.mean(np.where(mm == 0, 0.5, mm == t)))
        out.append((float(np.mean(acc_r)), float(np.mean(acc_m)), n_tie / max(n_all, 1)))
    a = np.array(out)
    return {"rater_acc": round(float(a[:, 0].mean()), 3),
            "model_acc": round(float(a[:, 1].mean()), 3),
            "dims_model_ahead": int((a[:, 1] > a[:, 0]).sum()),
            "rater_tie_share": round(float(a[:, 2].mean()), 3)}


def main() -> None:
    R.selfcheck()
    t0 = time.time()
    Z = np.load(ART / "muq_pooled.npz")
    stems = list(Z["stems"])
    idx = percepiano_index().set_index("performance_id")
    pids = np.array([f"percepiano:{s}" for s in stems])
    meta = idx.loc[pids]
    passage_all = (meta.work + "_" + meta.bars.astype(str) + "b_" + meta.segment.astype(str)
                   ).to_numpy()
    work_all = meta.piece_id.to_numpy()
    score_all = meta.player.astype(str).str.lower().str.startswith("score").to_numpy()
    official = load_percepiano_official_means()
    ratings = load_percepiano_ratings()
    lab = np.isin(pids, official.index)

    OOF = np.load(ART / "oof_predictions.npz")
    folds_json = json.loads((ART / "audio_fold_assignments.json").read_text())
    fold_of = {k: f for f in range(4) for k in folds_json[f"fold_{f}"]}
    cv = np.flatnonzero(lab & np.isin(stems, list(fold_of)))
    al = np.flatnonzero(lab)
    assert (OOF["pids_cv"] == pids[cv]).all() and (OOF["pids_all_labeled"] == pids[al]).all()
    fold_cv = np.array([fold_of[stems[i]] for i in cv])
    folds_cv = [(np.flatnonzero(fold_cv != f), np.flatnonzero(fold_cv == f)) for f in range(4)]
    pas_cv, pas_al = passage_all[cv], passage_all[al]

    def Y_of(rows):
        return official.loc[pids[rows], list(DIMENSIONS)].to_numpy(dtype=np.float32)

    Ycv, Yal = Y_of(cv), Y_of(al)
    res: dict = {"code_hash": R.code_hash(), "seeds": R.SEEDS}

    # 1. (a) fold-mean R²
    Pa = OOF["a_official_1000"]
    per_seed_fold_mean = [float(np.mean([R.r2_mean(Ycv[te], Pa[te, s]) for _, te in folds_cv]))
                          for s in range(Pa.shape[1])]
    res["a_fold_mean_r2"] = round(float(np.mean(per_seed_fold_mean)), 4)
    res["a_fold_mean_r2_per_seed"] = [round(x, 4) for x in per_seed_fold_mean]
    res["a_pooled_r2_per_seed"] = [round(R.r2_mean(Ycv, Pa[:, s]), 4) for s in range(Pa.shape[1])]
    print("a fold mean", res["a_fold_mean_r2"], flush=True)

    # 2. (c) with D960 merged: 3 works
    work_m = np.where(np.char.startswith(work_all[al].astype(str), "schubert_d960"),
                      "schubert_d960", work_all[al])
    works3 = sorted(set(work_m))
    folds3 = [(np.flatnonzero(work_m != w), np.flatnonzero(work_m == w)) for w in works3]
    for tr, te in folds3:
        assert not (set(pas_al[tr]) & set(pas_al[te]))
    X = Z["pooled_1000"][:, R.L912, :]
    P3, eps = R.run_protocol(X[al], Yal, pas_al, folds3, "inner")
    c3 = R.summarize(Yal, P3, pas_al)
    c3["best_epoch_median"] = float(np.median(eps))
    c3["per_work"] = {}
    bt3 = np.zeros_like(Yal)
    for w, (tr, te) in zip(works3, folds3, strict=True):
        bt3[te] = Yal[tr].mean(0)
        r = R.summarize(Yal[te], P3[te], pas_al[te], seed=1)
        r["trainmean_r2"] = round(R.r2_mean(Yal[te], bt3[te]), 4)
        r["n"] = int(len(te))
        c3["per_work"][w] = r
    res["c3_official_1000"] = c3
    res["baseline_trainmean_c3"] = R.summarize(Yal, bt3, pas_al)
    print("c3", c3["r2"], c3["within_r2"], c3["within_pairacc"], f"{time.time() - t0:.0f}s",
          flush=True)

    # 3. No-Score evaluation (same OOF predictions, Score/Score2 rows dropped)
    ns_cv, ns_al = ~score_all[cv], ~score_all[al]
    res["n_score_cv"], res["n_score_all"] = int((~ns_cv).sum()), int((~ns_al).sum())
    Pc = OOF["c_official_1000"]
    bt4 = np.zeros_like(Yal)
    for w in sorted(set(work_all[al])):
        bt4[work_all[al] == w] = Yal[work_all[al] != w].mean(0)
    noscore = {
        "b": (Ycv, OOF["b_official_1000"], pas_cv, ns_cv),
        "c": (Yal, Pc, pas_al, ns_al),
        "c3": (Yal, P3, pas_al, ns_al),
        "trainmean_c": (Yal, bt4, pas_al, ns_al),
        "trainmean_c3": (Yal, bt3, pas_al, ns_al),
    }
    res["noscore"] = {k: R.summarize(y[m], p[m], g[m]) for k, (y, p, g, m) in noscore.items()}
    for k, v in res["noscore"].items():
        print("noscore", k, v["r2"], v["within_r2"], v["within_pairacc"], flush=True)

    # 4. Seed-ensembled vs seed-averaged metrics, and untied within-passage parity
    ens = {}
    for key, y, P, g in (("b", Ycv, OOF["b_official_1000"], pas_cv), ("c", Yal, Pc, pas_al),
                         ("c3", Yal, P3, pas_al)):
        Pm = np.nanmean(P, axis=1)
        ens[key] = {"seed_avg": {"r2": round(R.r2_mean(y, P), 4),
                                 "within_pairacc": round(R.within_pairacc(y, P, g), 4)},
                    "seed_ensemble": {"r2": round(R.r2_mean(y, Pm), 4),
                                      "within_pairacc": round(R.within_pairacc(y, Pm, g), 4)}}
    res["seed_ensemble_vs_avg"] = ens
    par = {}
    for key, rows, P, g, ns in (("b", cv, OOF["b_official_1000"], pas_cv, ns_cv),
                                ("c", al, Pc, pas_al, ns_al), ("c3", al, P3, pas_al, ns_al)):
        pm = np.nanmean(P, axis=1)
        par[key] = {
            "ties_half": wp_parity(pids[rows], pm, ratings, g),
            "untied": wp_parity(pids[rows], pm, ratings, g, untied=True),
            "untied_noscore": wp_parity(pids[rows], pm, ratings, g, keep_rows=ns, untied=True),
        }
        print("parity", key, par[key], flush=True)
    res["wp_parity"] = par
    tab3 = R.parity_tables(pids[al], np.nanmean(P3, axis=1), ratings, pas_al)
    res["parity_c3_official_1000"] = {
        "mean_rater_r": round(float(tab3.rater_r.mean()), 3),
        "mean_model_r": round(float(tab3.model_r.mean()), 3),
        "pearson_counts": R.verdict_counts(tab3, "diff_ci"),
        "mean_wp_rater_acc": round(float(tab3.wp_rater_acc.mean()), 3),
        "mean_wp_model_acc": round(float(tab3.wp_model_acc.mean()), 3),
        "within_passage_counts": R.verdict_counts(tab3, "wp_diff_ci"),
    }
    tab3.to_csv(ART / "parity_c3_official_1000.csv", index=False)
    print("parity c3", res["parity_c3_official_1000"], flush=True)

    res["wall_sec"] = round(time.time() - t0, 1)
    (ART / "postaudit.json").write_text(json.dumps(res, indent=1, default=str))
    np.savez_compressed(
        ART / "oof_predictions_postaudit.npz",
        c3_official_1000=P3, pids_all_labeled=pids[al], works_c3=np.array(works3),
        work_c3=work_m.astype(str),
        noscore_mask_cv=ns_cv, noscore_mask_all_labeled=ns_al,
        pids_cv_noscore=pids[cv][ns_cv], pids_all_labeled_noscore=pids[al][ns_al],
        b_official_1000_noscore=OOF["b_official_1000"][ns_cv],
        c_official_1000_noscore=Pc[ns_al],
        c3_official_1000_noscore=P3[ns_al],
    )
    print("done", res["wall_sec"])


if __name__ == "__main__":
    main()
