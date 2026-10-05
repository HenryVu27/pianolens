"""R-10 score-only baseline: ridge on score features (any env with pianolens + scikit-learn).

Features: R-06 ``baseline.score_features`` (copied below: pitch, chord role and size, durations,
IOIs, metrical phase, position, local density and register), computed on the generation item of
each piece (the full capped score), so they use no performance information.
Targets: per score note, the mean over the piece's expert renditions of (velocity - the
rendition's conditioning velocity) and of the log IOI ratio (``note_expression``, rendition's own
global tempo), notes observed in at least half the renditions.
Training pieces: every piece of the given sets (R-10: the R10u and R10s development sets, which
share no piece, work or alias with the fresh set). alpha per target by 5-fold GroupKFold by work
(max Pearson r), then refit on all.

    python train_ridge.py --sets OUT/sets/r10u_dev OUT/sets/r10s_dev --out OUT/ridge/ridge.npz
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from pianolens.models.expression_data import load_item
from pianolens.models.expression_io import note_expression, onset_groups

ALPHAS = [1.0, 10.0, 100.0, 1000.0, 1e4, 1e5]
TARGETS = ("velocity", "log_ioi")


def score_features(onset_q, dur_q, pitch, origin: float, ts) -> np.ndarray:
    """Copied from R-06 baseline.py (unchanged)."""
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


def piece_rows(set_dir: Path, piece: str, stems: list[str]):
    slug = "".join(c if c.isalnum() or c in "-." else "_" for c in piece)
    gi = load_item(set_dir / "gen_items" / f"{slug}.npz")
    X = score_features(gi["score_onset_q"], gi["score_dur_q"], gi["pitch"], float(gi["origin"]),
                       gi["ts"])
    sid = pd.Index(gi["score_id"])
    Y = np.full((len(stems), len(sid), 2), np.nan)
    for i, st in enumerate(stems):
        it = load_item(set_dir / "items" / f"{st}__real.npz")
        ex = note_expression(it["score_onset_q"], it["score_dur_q"], it["perf_onset_sec"],
                             it["perf_dur_sec"], it["velocity"])
        pos = sid.get_indexer(it["score_id"])
        ok = pos >= 0
        Y[i, pos[ok], 0] = ex["velocity"].to_numpy()[ok] - float(it["vel_cond"])
        Y[i, pos[ok], 1] = ex["log_ioi"].to_numpy()[ok]
    obs = np.isfinite(Y).mean(0) >= 0.5
    with np.errstate(invalid="ignore"):
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            m = np.nanmean(Y, 0)
    m[~obs] = np.nan
    return X, m


def train(sets: list[Path]) -> tuple[dict, dict]:
    from sklearn.linear_model import Ridge
    from sklearn.model_selection import GroupKFold

    Xs, Ys, G = [], [], []
    for d in sets:
        man = pd.read_csv(d / "manifest.csv")
        man = man[man["kind"] == "real"]
        for piece, g in man.groupby("passage"):
            if len(g) < 6:
                continue
            X, Y = piece_rows(d, piece, g["stem"].tolist())
            Xs.append(X)
            Ys.append(Y)
            G += [str(g["work"].iloc[0])] * len(X)
    X, Y, G = np.vstack(Xs), np.vstack(Ys), np.array(G)
    mu, sd = X.mean(0), X.std(0) + 1e-9
    Z = (X - mu) / sd
    meta = {"n_notes": {}, "alpha": {}, "cv_r": {}, "n_pieces": len(Xs),
            "n_works": int(len(set(G)))}
    coef, icpt = [], []
    for j, t in enumerate(TARGETS):
        ok = np.isfinite(Y[:, j])
        z, y, gr = Z[ok], Y[ok, j], G[ok]
        best = None
        for a in ALPHAS:
            pred = np.zeros(len(y))
            for tr, te in GroupKFold(min(5, len(set(gr)))).split(z, y, gr):
                pred[te] = Ridge(alpha=a).fit(z[tr], y[tr]).predict(z[te])
            r = float(np.corrcoef(pred, y)[0, 1])
            if best is None or r > best[1]:
                best = (a, r)
        m = Ridge(alpha=best[0]).fit(z, y)
        coef.append(m.coef_)
        icpt.append(m.intercept_)
        meta["n_notes"][t], meta["alpha"][t], meta["cv_r"][t] = int(len(y)), best[0], best[1]
    return {"mu": mu, "sd": sd, "coef": np.array(coef), "intercept": np.array(icpt)}, meta


def predict(item: dict, model: dict) -> pd.DataFrame:
    X = score_features(item["score_onset_q"], item["score_dur_q"], item["pitch"],
                       float(item["origin"]), item["ts"])
    P = ((X - model["mu"]) / model["sd"]) @ np.asarray(model["coef"]).T + model["intercept"]
    return pd.DataFrame({"velocity": P[:, 0] + float(item["vel_cond"]), "log_ioi": P[:, 1]})


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sets", nargs="+", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    model, meta = train([Path(s) for s in a.sets])
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    np.savez(out, **model)
    meta["sets"] = a.sets
    out.with_suffix(".json").write_text(json.dumps(meta, indent=1))
    print(json.dumps(meta, indent=1), flush=True)


if __name__ == "__main__":
    main()
