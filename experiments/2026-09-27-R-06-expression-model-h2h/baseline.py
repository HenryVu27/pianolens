"""R-06 baseline (project env): ridge on score features ("Basis-Mixer-lite").

Trained on (n)ASAP performances of pieces outside sets A, P and V (up to 3 robust-alignment
performances per score folder, seed 0), first 800 score notes each, with the same conditioning
as the models (own global tempo, own median velocity). Targets: velocity minus the conditioning
velocity, log IOI ratio, log articulation. alpha chosen by GroupKFold (5 folds, by piece) inside
the training set. Saves artifacts/baseline.npz (coefficients, scaler, residual s.d.).

    OMP_NUM_THREADS=1 uv run python experiments/2026-09-27-R-06-expression-model-h2h/baseline.py
"""

from __future__ import annotations

import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from prepare import A_MAX_NOTES, A_TEST_FOLDERS, cap_pairs, score_side  # noqa: E402

from pianolens.models.expression_io import (  # noqa: E402
    global_seconds_per_quarter,
    matched_pairs,
    note_expression,
    onset_groups,
    time_signature_events,
)

ART = HERE / "artifacts"
TARGETS = ["vel_rel", "log_ioi", "log_art"]
EXCLUDE_PIECES = {"chopin_op10_no3", "chopin_op38", "mozart_k331_mv1", "schubert_d783_no15",
                  "beethoven_woo80", "schubert_d960_mv2", "schubert_d960_mv3",
                  "schubert_d935_no3"}
ALPHAS = [1.0, 10.0, 100.0, 1000.0, 1e4, 1e5]


def score_features(onset_q: np.ndarray, dur_q: np.ndarray, pitch: np.ndarray, origin: float,
                   ts: np.ndarray) -> np.ndarray:
    """Per-note score features (no performance information)."""
    on = np.asarray(onset_q, float)
    du = np.where(np.asarray(dur_q, float) > 0, dur_q, 1 / 16)
    p = np.asarray(pitch, float)
    g, uq = onset_groups(on)
    ng = len(uq)
    top = np.full(ng, -1.0)
    bot = np.full(ng, 999.0)
    np.maximum.at(top, g, p)
    np.minimum.at(bot, g, p)
    size = np.bincount(g, minlength=ng).astype(float)
    ioi_next = np.append(np.diff(uq), np.nan)
    ioi_prev = np.insert(np.diff(uq), 0, np.nan)
    med = np.nanmedian(np.diff(uq)) if ng > 1 else 1.0
    ioi_next = np.where(np.isnan(ioi_next), med, ioi_next)
    ioi_prev = np.where(np.isnan(ioi_prev), med, ioi_prev)
    # bar phase from time signature events (quarters relative to origin)
    rel = on - origin
    ts = np.asarray(ts, float).reshape(-1, 3)
    phase = np.zeros(len(on))
    beat_frac = np.zeros(len(on))
    for i, (q0, num, den) in enumerate(ts):
        q1 = ts[i + 1, 0] if i + 1 < len(ts) else np.inf
        k = (rel >= q0 - 1e-9) & (rel < q1 - 1e-9)
        bar = num * 4.0 / den
        beat = 4.0 / den
        phase[k] = ((rel[k] - q0) % bar) / bar
        beat_frac[k] = ((rel[k] - q0) % beat) / beat
    t_end = on.max()
    span = max(t_end - on.min(), 1e-6)
    dens = np.array([np.sum(np.abs(uq - t) <= 2.0) for t in uq])[g]
    loc = np.array([p[np.abs(on - t) <= 2.0].mean() for t in on])
    is_top = (p == top[g]).astype(float)
    is_bot = (p == bot[g]).astype(float)
    pz = (p - 60) / 12
    return np.column_stack([
        pz, pz**2, is_top, is_bot, is_top * pz, np.log2(size[g]),
        np.log2(du), np.log2(ioi_next[g]), np.log2(ioi_prev[g]), np.log2(du / ioi_next[g]),
        np.sin(2 * np.pi * phase), np.cos(2 * np.pi * phase), (phase < 1e-6).astype(float),
        (beat_frac < 1e-6).astype(float), (on - on.min()) / span,
        np.exp(-(t_end - on) / 4.0), np.log(dens), (p - loc) / 12,
    ])


def _rows(folder_perfs: tuple[str, list[str]]):
    from pianolens.data.asap import asap_index, iter_asap

    folder, pids = folder_perfs
    md = asap_index()
    md = md[md["performance_id"].isin(pids)]
    out = []
    for ap in iter_asap(index=md):
        if ap.alignment is None:
            continue
        ss = score_side(ap.score)
        on = ss["notes"]["onset_quarter"]
        max_on = float(on[min(len(on), A_MAX_NOTES) - 1])
        mp = cap_pairs(matched_pairs(ap.score.notes, ap.performance.notes, ap.alignment.pairs),
                       max_on)
        if len(mp) < 32:
            continue
        spq = global_seconds_per_quarter(mp.score_onset_q, mp.perf_onset_sec)
        vel = float(np.median(mp.velocity))
        origin, ts = time_signature_events(ap.score.measures, ap.score.notes)
        X = score_features(mp.score_onset_q, mp.score_dur_q, mp.pitch, origin, np.array(ts))
        ex = note_expression(mp.score_onset_q, mp.score_dur_q, mp.perf_onset_sec,
                             mp.perf_dur_sec, mp.velocity, spq)
        Y = np.column_stack([ex["velocity"] - round(vel), ex["log_ioi"],
                             ex["log_art"].clip(-3, 3)])
        out.append((ap.performance.piece_id, X, Y))
    return out


def main() -> None:
    from sklearn.linear_model import Ridge
    from sklearn.model_selection import GroupKFold

    from pianolens.data.asap import asap_index

    md = asap_index()
    md = md[(md["robust_note_alignment"] == 1) & ~md["folder"].isin(A_TEST_FOLDERS)
            & ~md["piece_id"].isin(EXCLUDE_PIECES)]
    rng = np.random.default_rng(0)
    jobs = []
    for folder, g in md.groupby("folder"):
        pids = g["performance_id"].tolist()
        pids = [pids[i] for i in sorted(rng.permutation(len(pids))[:3])]
        jobs.append((folder, pids))
    rows = []
    with ProcessPoolExecutor(12) as ex:
        for r in ex.map(_rows, jobs):
            rows.extend(r)
    groups = np.concatenate([[pid] * len(X) for pid, X, _ in rows])
    X = np.vstack([X for _, X, _ in rows])
    Y = np.vstack([Y for _, _, Y in rows])
    mu, sd = X.mean(0), X.std(0) + 1e-9
    Xs = (X - mu) / sd
    res = {"n_train_notes": {}, "alpha": {}, "cv_r": {}}
    coefs, intercepts, resid_sd = [], [], []
    for j, t in enumerate(TARGETS):
        ok = np.isfinite(Y[:, j])
        xs, y, gr = Xs[ok], Y[ok, j], groups[ok]
        best = None
        for a in ALPHAS:
            pred = np.zeros(len(y))
            for tr, te in GroupKFold(5).split(xs, y, gr):
                pred[te] = Ridge(alpha=a).fit(xs[tr], y[tr]).predict(xs[te])
            r = float(np.corrcoef(pred, y)[0, 1])
            if best is None or r > best[1]:
                best = (a, r)
        m = Ridge(alpha=best[0]).fit(xs, y)
        coefs.append(m.coef_)
        intercepts.append(m.intercept_)
        resid_sd.append(float(np.std(y - m.predict(xs))))
        res["n_train_notes"][t] = int(len(y))
        res["alpha"][t] = best[0]
        res["cv_r"][t] = best[1]
    res["n_performances"] = len(rows)
    res["n_pieces"] = int(len(set(groups)))
    np.savez(ART / "baseline.npz", mu=mu, sd=sd, coef=np.array(coefs),
             intercept=np.array(intercepts), resid_sd=np.array(resid_sd))
    (ART / "baseline_meta.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


def predict(item: dict, model: dict) -> pd.DataFrame:
    """Baseline per-note prediction for an interchange item (score side + conditioning)."""
    X = score_features(item["score_onset_q"], item["score_dur_q"], item["pitch"],
                       float(item["origin"]), item["ts"])
    Xs = (X - model["mu"]) / model["sd"]
    P = Xs @ model["coef"].T + model["intercept"]
    return pd.DataFrame({"velocity": P[:, 0] + float(item["vel_cond"]), "log_ioi": P[:, 1],
                         "log_art": P[:, 2]})


if __name__ == "__main__":
    main()
