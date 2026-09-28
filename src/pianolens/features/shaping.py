"""Tier C shaping (F-05): structural coherence (H4), repeated-material consistency, voicing,
dynamic-marking compliance.

All functions take an ``AlignedPerformance`` whose score is the one returned by
``pianolens.align.align_performance`` (unfolded to the performer's repeat path, ``part`` kept).
Only ``match`` pairs count; interpolated, unmatched and grace notes are skipped and counted.
Optional ``basis`` (:func:`pianolens.features.score_basis.score_basis`) and ``tempo``
(:func:`pianolens.features.tempo.tempo_model`) arguments avoid recomputing them.

Expressive channels (the performer's curves)
--------------------------------------------
* ``velocity``: MIDI velocity of each matched note (``vel_midi``, 0-127).
* ``timing``: position timing residual from the F-03 smooth tempo curve, in beats
  (``dev_beats``: fraction of the local beat period, so it scales with tempo; gross / robust
  outliers excluded).
* ``tempo``: the F-03 smooth log tempo ratio at each score position (``tempo_log_ratio``,
  natural log, positive = faster than the performance's own global tempo). Tier C reads the
  smooth part; the residual is ``timing``.
* ``articulation``: ``art_log_ratio = log(key-down duration / (notated duration in beats x
  local smooth beat period))``, natural log, clipped to +-``art_clip``; 0 = exactly the
  notated length at the local tempo. Uses key-down durations (PianoLens performances store
  those, not pedal-extended ones; see ``.claude/rules/features.md``). Articulation
  after Bresin and Battel 2000 (KOR-style ratio against the notated value).

Structural coherence (H4)
-------------------------
The fraction of a performer's own expressive variance that score structure explains. For each
channel, a ridge regression of the channel on the score basis features (standardized; ``alpha``
chosen by inner cross-validation) is evaluated out of fold, and

    ``r2 = 1 - sum (y - y_oof)^2 / sum (y - mean y)^2``

(dimensionless; <= 1; about 0 or below when the score says nothing about the curve).

Leakage control: folds are **blocks of ``block_bars`` written bars** (the score's measure
numbers, so both passes of a repeat fall in the same fold and a repeated passage can never
predict itself), blocks are dealt to folds round-robin, and training rows within
``buffer_bars`` bars of a test block are dropped (adjacent onsets share smooth-curve values).
``piece_pos`` (absolute position) is not used.

Minimum length (F-05d, DECISIONS 2026-09-28 after R-09): the summary reports
``n_written_bars`` (distinct written measure numbers among the channel's rows) and ``n_blocks``
= ``ceil(n_written_bars / block_bars)``, counted from the distinct bars, not from the range of
bar numbers. (R-09: 8-bar Czerny études numbered 0-8 spanned three 4-bar number blocks, so they
passed ``n_blocks >= 3`` and gave velocity R² down to -80.) R² is **defined only if
``n_blocks >= min_blocks`` (3) and ``n_written_bars >= min_written_bars`` (12)**; otherwise all
R² columns are NaN, no model is fitted, and ``undefined_reason`` says why (``too_few_rows``,
``constant``, ``too_few_bars``, ``too_few_blocks``, or ``cv_failed`` when the cross-validation
itself yields no R²; empty when defined). Shorter excerpts should be pooled over performances,
or scored with a smaller ``block_bars`` *and* an explicitly lowered ``min_written_bars``, and
labelled as such. ``r2`` uses every basis group; ``r2_no_markings``
drops the marking groups (dynamics, articulation, tempo marks, fermata): dynamics markings
trivially explain velocity, which is shaping but not the performer's own reading of structure.

:func:`pooled_structural_coherence` fits one model on several performances of the same piece
(each performance's curve centered on its own mean, optionally scaled), same written-bar
folds, and reports the pooled R² and each performance's R² under the shared model.

Repeated material
-----------------
Bars with identical content (same (beat in bar, pitch, notated duration) set; at least
``min_notes`` notes) are matched; maximal runs of consecutive equal bars that do not overlap
(``i + k < j``) are repetitions (repeat signs unfolded by the aligner and written-out repeats
alike). Longest runs are taken first and each bar pair is used once. For every run and
channel, corresponding notes (same position in bar and pitch) are paired and compared:
Pearson ``r`` (shape consistency), Lin's concordance ``ccc`` (1 only if identical, level and
scale included), ``mean_diff`` (repeat minus first) and ``rms_diff``. The summary averages
``r`` with Fisher z weights ``n - 3`` and pools within-run-centered pairs.

Voicing
-------
At score onsets where the melody note and at least one other (lower) note are both matched:
``vel_diff_midi`` = melody velocity minus the mean velocity of the other notes (MIDI
velocity), and ``lead_ms`` = mean onset of the other notes minus the melody onset (ms,
positive = melody early), reported together because melody lead is mostly a velocity
artifact (Goebl 2001). The melody is the skyline (``is_top`` in the basis: highest starting
note not below a held note) unless ``melody_ids`` are given.

Dynamic-marking compliance
--------------------------
Loudness of an onset = the maximum velocity of its matched notes (MIDI velocity; the loudest
note dominates what is heard, and the mean would jump whenever the texture changes, e.g. when
a melody note joins the accompaniment).

* Hairpins (and cresc. / dim. words, with the extents of the basis): Theil-Sen slope of
  onset loudness against score beat over the span, times the span length = ``change_vel``;
  ``agree`` if its sign matches the marking; ``signed_change_vel`` = change times the
  expected sign (positive = compliant).
* Successive dynamic levels (p -> f, ...): mean onset loudness in up to ``window_bars`` bars
  after the new marking minus in up to ``window_bars`` bars before it; ``agree`` if the sign
  matches the level change; ``vel_per_step`` = difference divided by the level difference
  on the ``DYNAMIC_LEVELS`` scale.
* Accents (sf / fz / accent marks): marked note velocity minus the median velocity of
  unmarked matched notes within one beat.
* ``level_velocity_spearman``: rank correlation of the marked dynamic level and onset loudness.

Citations (``docs/research/2026-09-27-landscape.md`` sections 1.2-1.3,
``docs/research/2026-09-27-expression-models.md``): Basis Mixer, expression as a function of
score basis features (Cancino-Chacón, Grachten et al., https://github.com/CPJKU/basismixer;
review https://doi.org/10.3389/fdigh.2018.00025); Repp 1992 (grouping-structure timing,
https://doi.org/10.1121/1.404425); Goebl 2001 melody lead
(https://iwk.mdw.ac.at/goebl/papers/Goebl_JASA2001_melodyLead.pdf); Bresin and Battel 2000
articulation (https://www.tandfonline.com/doi/abs/10.1076/jnmr.29.3.211.3092); Hu et al.,
TISMIR 2026 (timing scales with tempo, https://doi.org/10.5334/tismir.317). Lin 1989
(concordance correlation) is a method reference, not in the landscape doc.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

from pianolens.features.score_basis import MARKING_GROUPS, ScoreBasis, score_basis
from pianolens.features.tempo import TempoConfig, TempoCurve, _beats_per_bar, tempo_model

__all__ = [
    "CHANNELS",
    "CoherenceResult",
    "PhraseTempoResult",
    "ShapingConfig",
    "channel_data",
    "dynamic_compliance",
    "phrase_tempo_shaping",
    "pooled_structural_coherence",
    "repeated_material",
    "shaping",
    "structural_coherence",
    "voicing",
]

CHANNELS: tuple[str, ...] = ("velocity", "timing", "tempo", "articulation")
CHANNEL_UNITS = {"velocity": "vel_midi", "timing": "dev_beats", "tempo": "tempo_log_ratio",
                 "articulation": "art_log_ratio"}  # fmt: skip
_NOTE_CHANNELS = ("velocity", "articulation")


@dataclass(frozen=True)
class ShapingConfig:
    """Parameters (see the module docstring).

    Attributes:
        block_bars: written bars per cross-validation block.
        n_folds: outer folds (blocks dealt round-robin).
        inner_folds: inner folds for choosing the ridge penalty.
        buffer_bars: training rows within this many bars of a test block are dropped.
        alphas: ridge penalties per row (the penalty is ``alpha * n_train``) on standardized
            features.
        art_clip: articulation log ratios are clipped to +- this.
        by_group: also report R² with each basis group alone (``r2_<group>``).
        tempo: F-03 config used when ``tempo`` is not passed.
        clip_to_train: clip each held-out feature to the range seen in its training rows
            before predicting. Sparse features (a cadence type or phrase length that occurs
            in one block only) otherwise get huge standardized values out of fold and the
            ridge extrapolates wildly (F-05b: R² of -60 on a Vienna excerpt). On by default
            since F-05b (lead decision; it moves F-05 numbers by at most 0.001 on average).
        min_blocks: coherence R² is NaN below this many CV blocks (``n_blocks``, counted from
            distinct written bars).
        min_written_bars: coherence R² is NaN below this many distinct written bars
            (DECISIONS 2026-09-28; F-05d).
    """

    block_bars: int = 4
    n_folds: int = 5
    inner_folds: int = 4
    buffer_bars: int = 1
    alphas: tuple[float, ...] = tuple(float(a) for a in np.logspace(-4, 2, 13))
    art_clip: float = 3.0
    by_group: bool = False
    tempo: TempoConfig | None = None
    clip_to_train: bool = True
    min_blocks: int = 3
    min_written_bars: int = 12


# --------------------------------------------------------------------------- channel data


def _prep(ap: Any, basis: ScoreBasis | None, tempo: TempoCurve | None,
          cfg: ShapingConfig) -> tuple[ScoreBasis, TempoCurve]:
    if ap.score is None or ap.alignment is None:
        raise ValueError("shaping features need an AlignedPerformance with score and alignment")
    basis = basis if basis is not None else score_basis(ap.score)
    tempo = tempo if tempo is not None else tempo_model(ap, cfg.tempo)
    return basis, tempo


def _note_values(ap: Any, basis: ScoreBasis, tc: TempoCurve, cfg: ShapingConfig
                 ) -> pd.DataFrame:
    """Matched notes with velocity, timing, articulation and smooth tempo, plus basis columns."""
    pn = pd.DataFrame({
        "performance_id": ap.performance.notes["id"].astype(str),
        "duration_sec": ap.performance.notes["duration_sec"].astype(float),
    }).drop_duplicates("performance_id")
    n = tc.notes[["score_id", "performance_id", "beat", "vel_midi", "onset_sec", "dev_beats",
                  "position_outlier"]]
    # a score note matched to two performed notes (ornament handling) keeps its first match
    n = n.sort_values(["beat", "onset_sec"]).drop_duplicates("score_id", keep="first")
    n = n.merge(pn, on="performance_id", how="left")
    pos = tc.positions.set_index("beat")
    n["beat_period_sec"] = pos.loc[n["beat"].to_numpy(), "beat_period_sec"].to_numpy()
    n["tempo_log_ratio"] = pos.loc[n["beat"].to_numpy(), "tempo_log_ratio"].to_numpy()
    n = n.merge(basis.notes.drop(columns=["beat"]), on="score_id", how="inner")
    nominal = n["duration_beat"] * n["beat_period_sec"]
    with np.errstate(divide="ignore", invalid="ignore"):
        art = np.log(n["duration_sec"] / nominal)
    ok = np.isfinite(art) & (n["duration_sec"] > 0) & (nominal > 0)
    n["art_log_ratio"] = np.where(ok, np.clip(art, -cfg.art_clip, cfg.art_clip), np.nan)
    return n


def channel_data(
    ap: Any,
    basis: ScoreBasis | None = None,
    tempo: TempoCurve | None = None,
    config: ShapingConfig | None = None,
) -> dict[str, pd.DataFrame]:
    """Per channel, one row per observation: ``beat``, ``measure_idx``, ``measure_number``,
    ``y`` (the channel, units in ``CHANNEL_UNITS``) and every basis feature column.

    ``velocity`` / ``articulation`` rows are matched notes; ``timing`` / ``tempo`` rows are
    score positions (features of the position's top note, markings max over the chord).
    """
    cfg = config or ShapingConfig()
    basis, tc = _prep(ap, basis, tempo, cfg)
    feats = basis.columns(exclude_groups=())
    notes = _note_values(ap, basis, tc, cfg)
    keep = ["beat", "measure_idx", "measure_number", "score_id", *feats]
    out: dict[str, pd.DataFrame] = {}
    v = notes[keep].copy()
    v["y"] = notes["vel_midi"].astype(float)
    out["velocity"] = v
    a = notes.loc[notes["art_log_ratio"].notna(), keep].copy()
    a["y"] = notes.loc[notes["art_log_ratio"].notna(), "art_log_ratio"]
    out["articulation"] = a
    on = basis.onsets.copy()
    on["_k"] = on["beat"].round(6)
    pos = tc.positions.copy()
    pos["_k"] = pos["beat"].round(6)
    pos = pos.merge(on.drop(columns=["beat", "measure_idx", "measure_number"]), on="_k",
                    how="inner")
    pk = ["beat", "measure_idx", "measure_number", *feats]
    t = pos.loc[~pos["outlier"], pk].copy()
    t["y"] = pos.loc[~pos["outlier"], "dev_beats"]
    out["timing"] = t
    te = pos.loc[~pos["gross_outlier"], pk].copy()
    te["y"] = pos.loc[~pos["gross_outlier"], "tempo_log_ratio"]
    out["tempo"] = te
    for k in out:
        out[k] = out[k][np.isfinite(out[k]["y"])].reset_index(drop=True)
    return out


# --------------------------------------------------------------------------- ridge + CV


def _ridge_path(X: np.ndarray, y: np.ndarray, alphas: Sequence[float]
                ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Coefficients for each alpha on standardized X. Returns (coefs[a, p], x_mean, x_scale,
    y_mean); the penalty is ``alpha * n``."""
    mu = X.mean(axis=0)
    sd = X.std(axis=0)
    sd[sd < 1e-12] = np.inf  # constant columns get zero weight
    Z = (X - mu) / sd
    ym = float(y.mean())
    U, S, Vt = np.linalg.svd(Z, full_matrices=False)
    Uty = U.T @ (y - ym)
    n = len(y)
    coefs = np.stack([Vt.T @ (S / (S**2 + a * n) * Uty) for a in alphas])
    return coefs, mu, sd, np.array(ym)


def _predict(coef: np.ndarray, mu: np.ndarray, sd: np.ndarray, ym: np.ndarray,
             X: np.ndarray) -> np.ndarray:
    return ((X - mu) / sd) @ coef + float(ym)


def _clip_to(X: np.ndarray, ref: np.ndarray) -> np.ndarray:
    return np.clip(X, ref.min(axis=0), ref.max(axis=0))


def _folds(measure: np.ndarray, block_bars: int, k: int) -> np.ndarray:
    blocks = np.floor_divide(measure.astype(int), max(block_bars, 1))
    ub = np.unique(blocks)
    k = max(2, min(k, len(ub)))
    lut = {b: i % k for i, b in enumerate(ub)}
    return np.array([lut[b] for b in blocks])


def _buffered_train(measure: np.ndarray, test: np.ndarray, buffer: int,
                    group: np.ndarray | None) -> np.ndarray:
    """Training mask: not test and not within ``buffer`` bars of a test bar (same group)."""
    train = ~test
    if buffer <= 0:
        return train
    g = group if group is not None else np.zeros(len(measure), int)
    for gv in np.unique(g):
        sel = g == gv
        tm = np.unique(measure[sel & test])
        if len(tm) == 0:
            continue
        near = np.zeros(sel.sum(), bool)
        m = measure[sel]
        for d in range(1, buffer + 1):
            near |= np.isin(m - d, tm) | np.isin(m + d, tm)
        idx = np.where(sel)[0]
        train[idx[near]] = False
    return train & ~test


def _cv_ridge(X: np.ndarray, y: np.ndarray, measure: np.ndarray, cfg: ShapingConfig,
              group: np.ndarray | None = None) -> tuple[np.ndarray, float, float]:
    """Out-of-fold predictions, R² and the median chosen alpha (nested CV, written-bar blocks)."""
    fold = _folds(measure, cfg.block_bars, cfg.n_folds)
    oof = np.full(len(y), np.nan)
    chosen = []
    for f in np.unique(fold):
        test = fold == f
        train = _buffered_train(measure, test, cfg.buffer_bars, group)
        if train.sum() < max(10, X.shape[1] // 4) or test.sum() == 0:
            continue
        Xtr, ytr, mtr = X[train], y[train], measure[train]
        gtr = group[train] if group is not None else None
        ifold = _folds(mtr, cfg.block_bars, cfg.inner_folds)
        sse = np.zeros(len(cfg.alphas))
        for g in np.unique(ifold):
            te = ifold == g
            tr = _buffered_train(mtr, te, cfg.buffer_bars, gtr)
            if tr.sum() < 5 or te.sum() == 0:
                continue
            coefs, mu, sd, ym = _ridge_path(Xtr[tr], ytr[tr], cfg.alphas)
            Xte = _clip_to(Xtr[te], Xtr[tr]) if cfg.clip_to_train else Xtr[te]
            Zte = (Xte - mu) / sd
            pred = Zte @ coefs.T + float(ym)
            sse += ((pred - ytr[te, None]) ** 2).sum(axis=0)
        a = cfg.alphas[int(np.argmin(sse))]
        chosen.append(a)
        coefs, mu, sd, ym = _ridge_path(Xtr, ytr, [a])
        Xte = _clip_to(X[test], Xtr) if cfg.clip_to_train else X[test]
        oof[test] = _predict(coefs[0], mu, sd, ym, Xte)
    ok = np.isfinite(oof)
    if ok.sum() < 3:
        return oof, float("nan"), float("nan")
    ss_tot = float(np.sum((y[ok] - y[ok].mean()) ** 2))
    r2 = 1 - float(np.sum((y[ok] - oof[ok]) ** 2)) / ss_tot if ss_tot > 0 else float("nan")
    return oof, r2, float(np.median(chosen)) if chosen else float("nan")


def _local_bars(df: pd.DataFrame, y: np.ndarray, pred: np.ndarray, channel: str
                ) -> pd.DataFrame:
    ok = np.isfinite(pred)
    ym = float(y[ok].mean()) if ok.any() else np.nan
    d = pd.DataFrame({"measure_idx": df["measure_idx"].to_numpy(),
                      "measure_number": df["measure_number"].to_numpy(),
                      "sq_tot": (y - ym) ** 2, "sq_res": (y - pred) ** 2,
                      "abs_res": np.abs(y - pred), "ok": ok})
    d = d[d["ok"]]
    g = d.groupby("measure_idx", sort=True)
    out = pd.DataFrame({
        "measure_number": g["measure_number"].first(), "n": g.size(),
        "ss_tot": g["sq_tot"].sum(), "ss_res": g["sq_res"].sum(),
        "mean_abs_resid": g["abs_res"].mean(),
    }).reset_index()
    with np.errstate(divide="ignore", invalid="ignore"):
        out["r2_local"] = 1 - out["ss_res"] / out["ss_tot"]
    out.insert(0, "channel", channel)
    return out


# --------------------------------------------------------------------------- coherence


@dataclass
class CoherenceResult:
    """Output of :func:`structural_coherence` / :func:`pooled_structural_coherence`.

    Attributes:
        summary: one row per channel: ``channel``, ``unit``, ``n``, ``y_sd`` (in the
            channel's unit), ``n_written_bars`` (distinct written bars), ``n_blocks``
            (``ceil(n_written_bars / block_bars)``; see "Minimum length"), ``r2`` (all
            basis groups), ``r2_no_markings``, ``r2_<group>``
            (with ``by_group``), ``alpha``, ``undefined_reason`` (empty when R² is defined;
            else ``too_few_rows`` / ``constant`` / ``too_few_bars`` / ``too_few_blocks`` /
            ``cv_failed``); pooled results add ``n_performances``.
        bars: per channel and bar: ``n``, ``ss_tot`` / ``ss_res`` (about the channel mean,
            full model), ``r2_local`` (1 - ss_res / ss_tot inside the bar), ``mean_abs_resid``
            (how far the performer departs from the structure-predicted curve, channel unit).
        coefs: standardized ridge coefficients of the full model fitted on all rows
            (channel x feature), for interpretation only.
        predictions: channel -> rows with ``beat``, ``measure_idx``, ``y``, ``pred``,
            ``pred_no_markings`` (out of fold).
        per_performance: pooled only: R² of each performance under the pooled model.
    """

    summary: pd.DataFrame
    bars: pd.DataFrame
    coefs: pd.DataFrame
    predictions: dict[str, pd.DataFrame] = field(default_factory=dict)
    per_performance: pd.DataFrame = field(default_factory=pd.DataFrame)
    meta: dict[str, Any] = field(default_factory=dict)

    def r2(self, channel: str, which: str = "r2") -> float:
        s = self.summary.set_index("channel")
        return float(s.loc[channel, which])


def _feature_sets(groups: dict[str, list[str]], cfg: ShapingConfig) -> dict[str, list[str]]:
    base = {g: c for g, c in groups.items() if g != "position"}
    sets = {
        "r2": [c for cols in base.values() for c in cols],
        "r2_no_markings": [c for g, cols in base.items() if g not in MARKING_GROUPS
                           for c in cols],
    }
    if cfg.by_group:
        for g, cols in base.items():
            sets[f"r2_{g}"] = list(cols)
    return sets


def _coherence(data: dict[str, pd.DataFrame], groups: dict[str, list[str]],
               cfg: ShapingConfig, group_col: str | None = None) -> CoherenceResult:
    sets = _feature_sets(groups, cfg)
    rows, bars, coefs, preds = [], [], [], {}
    for ch in CHANNELS:
        df = data.get(ch)
        row: dict[str, Any] = {"channel": ch, "unit": CHANNEL_UNITS[ch],
                               "n": 0 if df is None else len(df)}
        undefined = {**{k: np.nan for k in sets}, "alpha": np.nan}
        if df is None or len(df) == 0:
            rows.append({**row, "n_written_bars": 0, "n_blocks": 0, **undefined,
                         "undefined_reason": "too_few_rows"})
            continue
        y = df["y"].to_numpy(float)
        m = df["measure_number"].to_numpy()
        grp = df[group_col].to_numpy() if group_col else None
        row["y_sd"] = float(np.std(y))
        n_bars = int(len(np.unique(m.astype(int))))
        row["n_written_bars"] = n_bars
        row["n_blocks"] = -(-n_bars // max(cfg.block_bars, 1))
        reason = ("too_few_rows" if len(df) < 20
                  else "constant" if float(df["y"].std()) < 1e-6
                  else "too_few_bars" if n_bars < cfg.min_written_bars
                  else "too_few_blocks" if row["n_blocks"] < cfg.min_blocks else "")
        if reason:
            rows.append({**row, **undefined, "undefined_reason": reason})
            continue
        p = pd.DataFrame({"beat": df["beat"].to_numpy(), "measure_idx": df["measure_idx"],
                          "y": y})
        if group_col:
            p[group_col] = grp
        for name, cols in sets.items():
            X = df[cols].to_numpy(float)
            oof, r2, alpha = _cv_ridge(X, y, m, cfg, grp)
            row[name] = r2
            if name == "r2":
                row["alpha"] = alpha
                p["pred"] = oof
                bars.append(_local_bars(df, y, oof, ch))
                a = alpha if np.isfinite(alpha) else 1.0
                c, _, sd, _ = _ridge_path(X, y, [a])
                coefs.append(pd.Series(c[0] * np.isfinite(sd), index=cols, name=ch))
            elif name == "r2_no_markings":
                p["pred_no_markings"] = oof
        row["undefined_reason"] = "" if np.isfinite(row["r2"]) else "cv_failed"
        preds[ch] = p
        rows.append(row)
    summary = pd.DataFrame(rows)
    bars_df = pd.concat(bars, ignore_index=True) if bars else pd.DataFrame()
    coef_df = pd.DataFrame(coefs) if coefs else pd.DataFrame()
    return CoherenceResult(summary, bars_df, coef_df, preds)


def structural_coherence(
    ap: Any,
    basis: ScoreBasis | None = None,
    tempo: TempoCurve | None = None,
    config: ShapingConfig | None = None,
) -> CoherenceResult:
    """Structural coherence (H4) of one performance: cross-validated R² of each expressive
    channel on the score basis (definition, folds and leakage control in the module docstring).

    Returns:
        :class:`CoherenceResult`; ``meta`` holds the alignment skip counts from F-03.
    """
    cfg = config or ShapingConfig()
    basis, tc = _prep(ap, basis, tempo, cfg)
    data = channel_data(ap, basis, tc, cfg)
    res = _coherence(data, basis.groups, cfg)
    res.meta = {k: tc.summary.get(k) for k in ("n_match", "n_interpolated_skipped",
                                               "n_insertion", "n_deletion",
                                               "n_grace_skipped", "n_missing_ids_skipped")}
    return res


def pooled_structural_coherence(
    aps: Sequence[Any],
    bases: Sequence[ScoreBasis | None] | None = None,
    tempos: Sequence[TempoCurve | None] | None = None,
    config: ShapingConfig | None = None,
    *,
    scale: bool = False,
) -> CoherenceResult:
    """Structural coherence of several performances of one piece under one shared model.

    Each performance's channel values are centered on its own mean (and divided by its own SD
    with ``scale=True``), so the pooled R² measures shared score-driven shape, not level
    differences between performers. Folds are written-bar blocks shared by all performances,
    so no bar is ever predicted from another performer's rendition of the same bar.
    ``per_performance`` holds each performance's R² under the pooled out-of-fold predictions.
    """
    cfg = config or ShapingConfig()
    bases = list(bases) if bases is not None else [None] * len(aps)
    tempos = list(tempos) if tempos is not None else [None] * len(aps)
    per_ch: dict[str, list[pd.DataFrame]] = {c: [] for c in CHANNELS}
    groups: dict[str, list[str]] = {}
    for i, (ap, b, t) in enumerate(zip(aps, bases, tempos, strict=True)):
        b, t = _prep(ap, b, t, cfg)
        for g, cols in b.groups.items():
            groups.setdefault(g, [])
            groups[g] += [c for c in cols if c not in groups[g]]
        for ch, df in channel_data(ap, b, t, cfg).items():
            if len(df) == 0:
                continue
            df = df.copy()
            df["y"] = df["y"] - df["y"].mean()
            if scale and df["y"].std() > 0:
                df["y"] = df["y"] / df["y"].std()
            df["_perf"] = i
            per_ch[ch].append(df)
    data = {ch: pd.concat(v, ignore_index=True).fillna(0.0) for ch, v in per_ch.items() if v}
    res = _coherence(data, groups, cfg, group_col="_perf")
    rows = []
    for ch, p in res.predictions.items():
        for i, g in p.groupby("_perf"):
            ok = np.isfinite(g["pred"])
            y, pr = g.loc[ok, "y"].to_numpy(), g.loc[ok, "pred"].to_numpy()
            ss = float(np.sum((y - y.mean()) ** 2))
            rows.append({"performance": int(i), "channel": ch, "n": int(ok.sum()),
                         "r2_pooled_model": 1 - float(np.sum((y - pr) ** 2)) / ss
                         if ss > 0 else np.nan})
    res.per_performance = pd.DataFrame(rows)
    res.summary.insert(1, "n_performances", len(aps))
    return res


# --------------------------------------------------------------------------- repeats


def _bar_fingerprints(bn: pd.DataFrame, min_notes: int) -> dict[int, tuple]:
    fp: dict[int, tuple] = {}
    for mi, g in bn.groupby("measure_idx", sort=True):
        if len(g) < min_notes:
            continue
        fp[int(mi)] = tuple(sorted(zip(g["beat_in_bar"].round(4), g["pitch"],
                                       g["duration_beat"].round(4), strict=True)))
    return fp


def _repeat_runs(fp: dict[int, tuple], min_bars: int) -> list[tuple[int, int, int]]:
    """Non-overlapping maximal runs (i, j, length) of equal consecutive bars, longest first,
    each bar pair used once."""
    by: dict[tuple, list[int]] = {}
    for m, f in fp.items():
        by.setdefault(f, []).append(m)
    eq = {(a, b) for ms in by.values() for x, a in enumerate(ms) for b in ms[x + 1:]}
    runs = []
    for a, b in eq:
        if (a - 1, b - 1) in eq and a - 1 < b - 1:
            continue  # not a run start
        k = 0
        while (a + k, b + k) in eq and a + k < b:
            k += 1
        if k >= min_bars:
            runs.append((a, b, k))
    runs.sort(key=lambda r: (-r[2], r[0], r[1]))
    used: set[tuple[int, int]] = set()
    out = []
    for a, b, k in runs:
        pairs = [(a + x, b + x) for x in range(k)]
        if any(p in used for p in pairs):
            continue
        used.update(pairs)
        out.append((a, b, k))
    return sorted(out)


def _ccc(x: np.ndarray, y: np.ndarray) -> float:
    vx, vy = np.var(x), np.var(y)
    den = vx + vy + (x.mean() - y.mean()) ** 2
    if den <= 0:
        return 1.0 if np.allclose(x, y) else float("nan")
    return float(2 * np.mean((x - x.mean()) * (y - y.mean())) / den)


def _pearson(x: np.ndarray, y: np.ndarray) -> float:
    if len(x) < 3 or np.std(x) < 1e-12 or np.std(y) < 1e-12:
        return float("nan")
    return float(np.corrcoef(x, y)[0, 1])


@dataclass
class RepeatResult:
    """Output of :func:`repeated_material`.

    Attributes:
        runs: one row per repetition and channel: ``first_measure_idx``,
            ``repeat_measure_idx``, ``n_bars``, ``first_measure_number``,
            ``repeat_measure_number``, ``channel``, ``n``, ``r``, ``ccc``, ``mean_diff``
            (repeat minus first, channel unit), ``rms_diff``.
        bars: per bar in any repetition: ``measure_idx``, ``measure_number``, ``role``
            (first / repeat), ``channel``, the run's ``r``, ``ccc``, ``mean_diff``.
        summary: per channel: ``n_runs``, ``n_pairs``, ``r_mean`` (Fisher-z weighted),
            ``r_pooled`` (pairs centered within run), ``ccc_pooled``, ``mean_abs_level_diff``.
    """

    runs: pd.DataFrame
    bars: pd.DataFrame
    summary: pd.DataFrame


def repeated_material(
    ap: Any,
    basis: ScoreBasis | None = None,
    tempo: TempoCurve | None = None,
    config: ShapingConfig | None = None,
    *,
    min_bars: int = 1,
    min_notes: int = 4,
) -> RepeatResult:
    """Consistency of the performer's expressive curves across repeated passages (see module
    docstring). Channels: velocity, timing (note-level ``dev_beats``), tempo (smooth log tempo
    at the note), articulation."""
    cfg = config or ShapingConfig()
    basis, tc = _prep(ap, basis, tempo, cfg)
    notes = _note_values(ap, basis, tc, cfg)
    notes["timing"] = notes["dev_beats"].where(~notes["position_outlier"].astype(bool))
    val = {"velocity": "vel_midi", "timing": "timing", "tempo": "tempo_log_ratio",
           "articulation": "art_log_ratio"}
    bn = basis.notes
    runs = _repeat_runs(_bar_fingerprints(bn, min_notes), min_bars)
    num = bn.groupby("measure_idx")["measure_number"].first()
    nv = notes.set_index("score_id")
    key = bn.assign(k=list(zip(bn["beat_in_bar"].round(4), bn["pitch"], strict=True)))
    by_bar = {int(m): dict(zip(g["k"], g["score_id"], strict=False))
              for m, g in key.groupby("measure_idx")}
    rrows, brows = [], []
    centered: dict[str, list[tuple[np.ndarray, np.ndarray]]] = {c: [] for c in val}
    for a, b, k in runs:
        ids_a, ids_b = [], []
        for x in range(k):
            ba, bb = by_bar.get(a + x, {}), by_bar.get(b + x, {})
            for kk, sid in ba.items():
                if kk in bb and sid in nv.index and bb[kk] in nv.index:
                    ids_a.append(sid)
                    ids_b.append(bb[kk])
        for ch, col in val.items():
            xa = nv.loc[ids_a, col].to_numpy(float) if ids_a else np.zeros(0)
            xb = nv.loc[ids_b, col].to_numpy(float) if ids_b else np.zeros(0)
            ok = np.isfinite(xa) & np.isfinite(xb)
            xa, xb = xa[ok], xb[ok]
            r = _pearson(xa, xb)
            c = _ccc(xa, xb) if len(xa) >= 3 else float("nan")
            md = float(np.mean(xb - xa)) if len(xa) else float("nan")
            rms = float(np.sqrt(np.mean((xb - xa) ** 2))) if len(xa) else float("nan")
            if len(xa) >= 3:
                mu = np.r_[xa, xb].mean()
                centered[ch].append((xa - mu, xb - mu))
            row = {"first_measure_idx": a, "repeat_measure_idx": b, "n_bars": k,
                   "first_measure_number": int(num.get(a, -1)),
                   "repeat_measure_number": int(num.get(b, -1)), "channel": ch,
                   "n": int(len(xa)), "r": r, "ccc": c, "mean_diff": md, "rms_diff": rms}
            rrows.append(row)
            for x in range(k):
                for role, m in (("first", a + x), ("repeat", b + x)):
                    brows.append({"measure_idx": m, "measure_number": int(num.get(m, -1)),
                                  "role": role, "channel": ch, "r": r, "ccc": c,
                                  "mean_diff": md})
    runs_df = pd.DataFrame(rrows, columns=["first_measure_idx", "repeat_measure_idx", "n_bars",
                                           "first_measure_number", "repeat_measure_number",
                                           "channel", "n", "r", "ccc", "mean_diff", "rms_diff"])
    srows = []
    for ch in val:
        d = runs_df[runs_df["channel"] == ch]
        dv = d[d["r"].notna() & (d["n"] > 3)]
        w = (dv["n"] - 3).to_numpy(float)
        z = np.arctanh(np.clip(dv["r"].to_numpy(float), -0.999999, 0.999999))
        r_mean = float(np.tanh(np.sum(w * z) / np.sum(w))) if w.sum() > 0 else float("nan")
        if centered[ch]:
            xa = np.concatenate([p[0] for p in centered[ch]])
            xb = np.concatenate([p[1] for p in centered[ch]])
            rp, cp = _pearson(xa, xb), _ccc(xa, xb)
        else:
            rp = cp = float("nan")
        srows.append({"channel": ch, "unit": CHANNEL_UNITS[ch], "n_runs": int(len(d)),
                      "n_pairs": int(d["n"].sum()), "r_mean": r_mean, "r_pooled": rp,
                      "ccc_pooled": cp,
                      "mean_abs_level_diff": float(d["mean_diff"].abs().mean())
                      if len(d) else float("nan")})
    return RepeatResult(runs_df, pd.DataFrame(brows), pd.DataFrame(srows))


# --------------------------------------------------------------------------- voicing


@dataclass
class VoicingResult:
    """Output of :func:`voicing`.

    Attributes:
        onsets: per qualifying onset: ``beat``, ``measure_idx``, ``measure_number``,
            ``melody_id``, ``melody_pitch``, ``n_accomp``, ``vel_melody``, ``vel_accomp``,
            ``vel_diff_midi``, ``lead_ms``, ``lead_beats`` (lead / local beat period).
        bars: per bar: ``n``, mean ``vel_diff_midi``, mean ``lead_ms``, mean ``lead_beats``.
        summary: ``n_onsets``, ``vel_diff_mean_midi``, ``vel_diff_median_midi``,
            ``frac_melody_louder``, ``lead_mean_ms``, ``lead_median_ms``,
            ``lead_vel_corr`` (Pearson r of lead and velocity difference, Goebl 2001),
            ``n_lead_beats_undefined`` (onsets whose smooth beat period is 0 or not finite,
            e.g. on very short segments: their ``lead_beats`` is NaN; ``lead_ms`` is kept).
    """

    onsets: pd.DataFrame
    bars: pd.DataFrame
    summary: dict[str, float]


def voicing(
    ap: Any,
    basis: ScoreBasis | None = None,
    tempo: TempoCurve | None = None,
    config: ShapingConfig | None = None,
    *,
    melody_ids: Sequence[str] | None = None,
) -> VoicingResult:
    """Melody-over-accompaniment velocity difference and melody lead at shared onsets
    (definition in the module docstring)."""
    cfg = config or ShapingConfig()
    basis, tc = _prep(ap, basis, tempo, cfg)
    notes = _note_values(ap, basis, tc, cfg)
    if melody_ids is not None:
        mel = set(map(str, melody_ids))
        notes["_mel"] = notes["score_id"].isin(mel)
    else:
        notes["_mel"] = notes["is_top"] > 0.5
    rows = []
    n_bad_period = 0
    for bt, g in notes.groupby("beat", sort=True):
        m = g[g["_mel"]]
        if len(m) == 0:
            continue
        m = m.sort_values("pitch").iloc[-1]
        acc = g[(~g["_mel"]) & (g["pitch"] < m["pitch"])]
        if len(acc) == 0:
            continue
        lead = float(acc["onset_sec"].mean() - m["onset_sec"])
        period = float(m["beat_period_sec"])
        if not (np.isfinite(period) and period > 0):  # degenerate tempo (e.g. tiny segment)
            n_bad_period += 1
            lead_beats = np.nan
        else:
            lead_beats = lead / period
        rows.append({"beat": bt, "measure_idx": m["measure_idx"],
                     "measure_number": m["measure_number"], "melody_id": m["score_id"],
                     "melody_pitch": int(m["pitch"]), "n_accomp": len(acc),
                     "vel_melody": float(m["vel_midi"]),
                     "vel_accomp": float(acc["vel_midi"].mean()),
                     "vel_diff_midi": float(m["vel_midi"] - acc["vel_midi"].mean()),
                     "lead_ms": 1000 * lead, "lead_beats": lead_beats})
    cols = ["beat", "measure_idx", "measure_number", "melody_id", "melody_pitch", "n_accomp",
            "vel_melody", "vel_accomp", "vel_diff_midi", "lead_ms", "lead_beats"]
    on = pd.DataFrame(rows, columns=cols)
    bars = on.groupby("measure_idx", sort=True).agg(
        measure_number=("measure_number", "first"), n=("beat", "size"),
        vel_diff_midi=("vel_diff_midi", "mean"), lead_ms=("lead_ms", "mean"),
        lead_beats=("lead_beats", "mean"),
    ).reset_index()
    vd, ld = on["vel_diff_midi"].to_numpy(), on["lead_ms"].to_numpy()
    summ = {
        "n_onsets": len(on),
        "vel_diff_mean_midi": float(vd.mean()) if len(vd) else np.nan,
        "vel_diff_median_midi": float(np.median(vd)) if len(vd) else np.nan,
        "frac_melody_louder": float(np.mean(vd > 0)) if len(vd) else np.nan,
        "lead_mean_ms": float(ld.mean()) if len(ld) else np.nan,
        "lead_median_ms": float(np.median(ld)) if len(ld) else np.nan,
        "lead_vel_corr": _pearson(ld, vd),
        "n_lead_beats_undefined": n_bad_period,
    }
    return VoicingResult(on, bars, summ)


# --------------------------------------------------------------------------- dynamics


@dataclass
class DynamicsResult:
    """Output of :func:`dynamic_compliance`.

    Attributes:
        events: one row per checked marking: ``kind`` (cresc / dim / level / accent),
            ``text``, ``start_beat``, ``end_beat``, ``measure_idx``, ``measure_number``,
            ``n``, ``expected_sign``, ``change_vel`` (hairpin change or level difference or
            accent excess, MIDI velocity), ``signed_change_vel`` (times the expected sign),
            ``agree``, ``vel_per_step`` (levels only).
        bars: per bar (of the event start): ``n_events``, ``n_agree``,
            ``mean_signed_change_vel``.
        summary: ``hairpin_n``, ``hairpin_agree_frac``, ``hairpin_mean_signed_change_vel``,
            ``level_n``, ``level_agree_frac``, ``level_vel_per_step``, ``accent_n``,
            ``accent_agree_frac``, ``accent_mean_excess_vel``, ``level_velocity_spearman``.
    """

    events: pd.DataFrame
    bars: pd.DataFrame
    summary: dict[str, float]


def dynamic_compliance(
    ap: Any,
    basis: ScoreBasis | None = None,
    tempo: TempoCurve | None = None,
    config: ShapingConfig | None = None,
    *,
    window_bars: float = 2.0,
    min_onsets: int = 3,
) -> DynamicsResult:
    """Does velocity follow the hairpins, dynamic levels and accents? (module docstring)."""
    cfg = config or ShapingConfig()
    basis, tc = _prep(ap, basis, tempo, cfg)
    notes = _note_values(ap, basis, tc, cfg)
    bpb = float(basis.meta.get("beats_per_bar", 4.0))
    on = notes.groupby("beat", sort=True).agg(vel=("vel_midi", "max"),
                                              dyn_level=("dyn_level", "max"),
                                              measure_idx=("measure_idx", "first"),
                                              measure_number=("measure_number", "first"))
    on = on.reset_index()
    b, v = on["beat"].to_numpy(), on["vel"].to_numpy(float)
    ev = basis.dynamics
    rows = []

    def where(beat: float) -> tuple[int, int]:
        i = int(np.clip(np.searchsorted(b, beat - 1e-6), 0, max(len(b) - 1, 0)))
        return (int(on["measure_idx"].iloc[i]), int(on["measure_number"].iloc[i])) \
            if len(b) else (-1, -1)

    for _, e in ev[ev["kind"].isin(["cresc", "dim"])].iterrows():
        s, en = float(e["start_beat"]), float(e["end_beat"])
        m = (b >= s - 1e-6) & (b <= en + 1e-6)
        sign = 1 if e["kind"] == "cresc" else -1
        mi, mn = where(s)
        if m.sum() < min_onsets or np.ptp(b[m]) <= 0:
            continue
        slope = float(stats.theilslopes(v[m], b[m]).slope)
        ch = float(slope * (en - s))
        rows.append({"kind": e["kind"], "text": e["text"], "start_beat": s, "end_beat": en,
                     "measure_idx": mi, "measure_number": mn, "n": int(m.sum()),
                     "expected_sign": sign, "change_vel": ch, "signed_change_vel": sign * ch,
                     "agree": bool(np.sign(ch) == sign), "vel_per_step": np.nan})
    lev = ev[ev["kind"] == "level"].sort_values("start_beat").reset_index(drop=True)
    w = window_bars * bpb
    for i in range(1, len(lev)):
        p, c = lev.iloc[i - 1], lev.iloc[i]
        dl = float(c["level"] - p["level"])
        if dl == 0:
            continue
        s = float(c["start_beat"])
        nxt = float(lev.iloc[i + 1]["start_beat"]) if i + 1 < len(lev) else np.inf
        before = (b >= max(float(p["start_beat"]), s - w) - 1e-6) & (b < s - 1e-6)
        after = (b >= s - 1e-6) & (b < min(nxt, s + w) - 1e-6)
        if before.sum() < min_onsets or after.sum() < min_onsets:
            continue
        ch = float(v[after].mean() - v[before].mean())
        sign = int(np.sign(dl))
        mi, mn = where(s)
        rows.append({"kind": "level", "text": f"{p['text']}->{c['text']}", "start_beat": s,
                     "end_beat": s, "measure_idx": mi, "measure_number": mn,
                     "n": int(before.sum() + after.sum()), "expected_sign": sign,
                     "change_vel": ch, "signed_change_vel": sign * ch,
                     "agree": bool(np.sign(ch) == sign), "vel_per_step": ch / dl})
    marked = (notes["sf_accent"] > 0) | (notes["accent"] > 0)
    nb, nvel = notes["beat"].to_numpy(), notes["vel_midi"].to_numpy(float)
    unmarked = ~marked.to_numpy()
    for _, r in notes[marked].iterrows():
        near = unmarked & (np.abs(nb - r["beat"]) <= 1.0)
        if near.sum() == 0:
            continue
        ch = float(r["vel_midi"] - np.median(nvel[near]))
        rows.append({"kind": "accent", "text": "sf" if r["sf_accent"] > 0 else "accent",
                     "start_beat": r["beat"], "end_beat": r["beat"],
                     "measure_idx": int(r["measure_idx"]),
                     "measure_number": int(r["measure_number"]), "n": int(near.sum()) + 1,
                     "expected_sign": 1, "change_vel": ch, "signed_change_vel": ch,
                     "agree": bool(ch > 0), "vel_per_step": np.nan})
    cols = ["kind", "text", "start_beat", "end_beat", "measure_idx", "measure_number", "n",
            "expected_sign", "change_vel", "signed_change_vel", "agree", "vel_per_step"]
    evd = pd.DataFrame(rows, columns=cols)
    bars = evd.groupby("measure_idx", sort=True).agg(
        measure_number=("measure_number", "first"), n_events=("kind", "size"),
        n_agree=("agree", "sum"), mean_signed_change_vel=("signed_change_vel", "mean"),
    ).reset_index()
    hp = evd[evd["kind"].isin(["cresc", "dim"])]
    lv = evd[evd["kind"] == "level"]
    ac = evd[evd["kind"] == "accent"]
    rho = np.nan
    if on["dyn_level"].nunique() > 1 and len(on) > 3:
        rho = float(stats.spearmanr(on["dyn_level"], on["vel"]).statistic)
    summ = {
        "hairpin_n": len(hp),
        "hairpin_agree_frac": float(hp["agree"].mean()) if len(hp) else np.nan,
        "hairpin_mean_signed_change_vel": float(hp["signed_change_vel"].mean())
        if len(hp) else np.nan,
        "level_n": len(lv),
        "level_agree_frac": float(lv["agree"].mean()) if len(lv) else np.nan,
        "level_vel_per_step": float(lv["vel_per_step"].median()) if len(lv) else np.nan,
        "accent_n": len(ac),
        "accent_agree_frac": float(ac["agree"].mean()) if len(ac) else np.nan,
        "accent_mean_excess_vel": float(ac["change_vel"].mean()) if len(ac) else np.nan,
        "level_velocity_spearman": rho,
    }
    return DynamicsResult(evd, bars, summ)


# --------------------------------------------------------------------------- per-phrase tempo


@dataclass
class PhraseTempoResult:
    """Output of :func:`phrase_tempo_shaping`.

    Attributes:
        phrases: one row per phrase: ``phrase``, ``start_beat``, ``end_beat``, ``n_beats``,
            ``c0`` / ``c1`` / ``c2`` (parabola in phrase position ``u`` in [-1, 1], natural-log
            tempo ratio), ``r2`` (in-sample, within the phrase), ``concave`` (``c2 < 0``:
            slower at both edges than in the middle), ``depth_log`` (``-c2``: middle minus
            edges of the fitted arc, log tempo ratio), ``measure_number`` (first bar).
        bars: per bar of the smooth tempo grid: ``measure_idx``, ``measure_number``,
            ``phrase`` (phrase of the bar's first beat), ``arc_fit_log`` (mean fitted arc),
            ``arc_resid_rms_log`` (RMS of smooth log tempo minus the arc), ``phrase_r2``,
            ``phrase_concave``.
        null: per circular shift of the boundaries: ``shift_bars``, ``n_phrases``,
            ``concave_share``, ``arc_r2_within``.
        summary: ``n_phrases`` (with at least ``min_beats`` grid beats), ``concave_share``,
            ``arc_r2_within``, ``arc_r2_median``, ``between_share``, ``depth_median_log``,
            ``null_concave_share`` / ``null_arc_r2_within`` (means over the shifts), and
            ``concave_excess`` / ``arc_r2_excess`` (observed minus null).
    """

    phrases: pd.DataFrame
    bars: pd.DataFrame
    null: pd.DataFrame
    summary: dict[str, float]


def _arc_table(grid: pd.DataFrame, starts: Sequence[float], min_beats: int
               ) -> tuple[pd.DataFrame, np.ndarray, dict[str, float]]:
    """Per-phrase parabolas on the integer-beat smooth tempo grid, the fitted arc per grid
    beat (NaN outside fitted phrases) and the pooled statistics."""
    x = grid["beat"].to_numpy(float)
    y = grid["tempo_log_ratio"].to_numpy(float)
    bnd = sorted(float(s) for s in starts)
    ends = [*bnd[1:], float(x.max()) + 1] if len(x) else []
    fit = np.full(len(x), np.nan)
    rows = []
    ss_tot = float(np.sum((y - y.mean()) ** 2)) if len(y) else 0.0
    ssw = ssres = 0.0
    for i, (s, e) in enumerate(zip(bnd, ends, strict=True)):
        m = (x >= s) & (x < e)
        yy, xx = y[m], x[m]
        w = float(np.sum((yy - yy.mean()) ** 2)) if m.any() else 0.0
        ssw += w
        row = {"phrase": i, "start_beat": s, "end_beat": e, "n_beats": int(m.sum()),
               "c0": np.nan, "c1": np.nan, "c2": np.nan, "r2": np.nan}
        if m.sum() >= max(min_beats, 3):
            u = 2 * (xx - xx.min()) / max(xx.max() - xx.min(), 1e-9) - 1
            c2, c1, c0 = np.polyfit(u, yy, 2)
            f = c0 + c1 * u + c2 * u**2
            fit[m] = f
            r2 = 1 - float(np.sum((yy - f) ** 2)) / w if w > 0 else np.nan
            row.update(c0=c0, c1=c1, c2=c2, r2=r2)
            ssres += (1 - r2) * w if np.isfinite(r2) else w
        else:
            ssres += w
        rows.append(row)
    ph = pd.DataFrame(rows, columns=["phrase", "start_beat", "end_beat", "n_beats", "c0", "c1",
                                     "c2", "r2"])
    ok = ph[np.isfinite(ph["c2"])]
    stats_ = {"n_phrases": float(len(ok)),
              "concave_share": float((ok["c2"] < 0).mean()) if len(ok) else np.nan,
              "arc_r2_within": 1 - ssres / ssw if ssw > 0 else np.nan,
              "between_share": 1 - ssw / ss_tot if ss_tot > 0 else np.nan}
    return ph, fit, stats_


def _shift_bounds(starts: Sequence[float], shift: float, lo: float, hi: float) -> list[float]:
    """Circular shift of boundaries inside ``[lo, hi)``: same number and spacing."""
    return sorted(float(v) for v in lo + np.mod(np.asarray(starts, float) - lo + shift, hi - lo))


def phrase_tempo_shaping(
    ap: Any,
    phrase_starts_beats: Sequence[float] | None = None,
    *,
    tempo: TempoCurve | None = None,
    basis: ScoreBasis | None = None,
    null_shifts_bars: Sequence[float] = (-2.0, 2.0),
    min_beats: int = 3,
    config: ShapingConfig | None = None,
) -> PhraseTempoResult:
    """Per-phrase tempo shaping (F-05c): does the player shape each phrase in time, whatever
    the shape of the other phrases?

    For each phrase, a parabola ``tempo_log_ratio ~ c0 + c1 u + c2 u^2`` (``u`` in [-1, 1]
    across the phrase) is fitted to the F-03 smooth log tempo on the integer-beat grid
    (Repp 1992: phrase-level ritardandi are parabolic; Todd 1992). Unlike structural
    coherence, no shape is shared between phrases. Measures (dimensionless):

    * ``concave_share``: share of phrases with ``c2 < 0`` (slower at both edges).
    * ``arc_r2_within``: pooled within-phrase R² of the parabolas,
      ``1 - sum_i (1 - r2_i) SS_i / sum_i SS_i`` (``SS_i`` = the phrase's smooth log-tempo
      sum of squares about its mean); in-sample, so it grows with the number of phrases.
    * The **shifted-boundary null** controls that: the same boundaries circularly shifted by
      each of ``null_shifts_bars`` bars (same number and spacing of phrases, wrong places).
      ``concave_excess`` and ``arc_r2_excess`` are observed minus the mean null; they are
      comparable across boundary sources and performances. F-05b (Batik, annotated phrases,
      +2 bars): 81% concave vs 44% shifted, arc R² 0.51 vs 0.40.
    * ``between_share``: share of the smooth log-tempo variance between phrase means.

    ``phrase_starts_beats``: phrase starts in score beats (annotations, the cadence detector
    of :mod:`pianolens.features.cadence`, or R-08); default the ``basis`` phrases (proxy,
    split at 8 bars), which F-05b found no better than a 4-bar grid. Phrases with fewer than
    ``min_beats`` grid beats are not fitted.

    Returns:
        :class:`PhraseTempoResult` with per-phrase, per-bar and null tables.
    """
    cfg = config or ShapingConfig()
    tc = tempo if tempo is not None else tempo_model(ap, cfg.tempo)
    if phrase_starts_beats is None:
        basis = basis if basis is not None else score_basis(ap.score)
        phrase_starts_beats = basis.phrases["start_beat"].tolist()
    grid = tc.beats
    ph, fit, st = _arc_table(grid, phrase_starts_beats, min_beats)
    ph["concave"] = ph["c2"] < 0
    ph["depth_log"] = -ph["c2"]
    x = grid["beat"].to_numpy(float)
    mnum = grid["measure_number"].to_numpy() if "measure_number" in grid else np.zeros(len(x))
    ph["measure_number"] = [mnum[np.argmax(x >= s)] if (x >= s).any() else np.nan
                            for s in ph["start_beat"]]
    # null: circularly shifted boundaries
    bpb = float(_beats_per_bar(ap.score))
    sb = ap.score.notes["onset_beat"].astype(float)
    lo, hi = float(sb.min()), float(sb.max()) + 1
    nrows = []
    for sh in null_shifts_bars:
        _, _, ns = _arc_table(grid, _shift_bounds(phrase_starts_beats, sh * bpb, lo, hi),
                              min_beats)
        nrows.append({"shift_bars": float(sh), "n_phrases": ns["n_phrases"],
                      "concave_share": ns["concave_share"], "arc_r2_within": ns["arc_r2_within"]})
    null = pd.DataFrame(nrows, columns=["shift_bars", "n_phrases", "concave_share",
                                        "arc_r2_within"])
    # per bar
    y = grid["tempo_log_ratio"].to_numpy(float)
    pidx = np.searchsorted(ph["start_beat"].to_numpy(float), x + 1e-9, side="right") - 1
    g = pd.DataFrame({"measure_idx": grid["measure_idx"].to_numpy() if "measure_idx" in grid
                      else np.zeros(len(x), int), "measure_number": mnum, "phrase": pidx,
                      "fit": fit, "res2": (y - fit) ** 2})
    gb = g.groupby("measure_idx", sort=True)
    bars = pd.DataFrame({"measure_number": gb["measure_number"].first(),
                         "phrase": gb["phrase"].first(),
                         "arc_fit_log": gb["fit"].mean(),
                         "arc_resid_rms_log": np.sqrt(gb["res2"].mean())}).reset_index()
    pr = ph.set_index("phrase")
    bars["phrase_r2"] = pr["r2"].reindex(bars["phrase"]).to_numpy()
    bars["phrase_concave"] = pr["concave"].reindex(bars["phrase"]).to_numpy()
    ok = ph[np.isfinite(ph["c2"])]
    summ = {**st, "arc_r2_median": float(ok["r2"].median()) if len(ok) else np.nan,
            "depth_median_log": float(ok["depth_log"].median()) if len(ok) else np.nan,
            "null_concave_share": float(null["concave_share"].mean()) if len(null) else np.nan,
            "null_arc_r2_within": float(null["arc_r2_within"].mean()) if len(null) else np.nan}
    summ["concave_excess"] = summ["concave_share"] - summ["null_concave_share"]
    summ["arc_r2_excess"] = summ["arc_r2_within"] - summ["null_arc_r2_within"]
    return PhraseTempoResult(ph, bars, null, summ)


# --------------------------------------------------------------------------- all together


@dataclass
class ShapingResult:
    """Output of :func:`shaping`: every tier C component, plus a flat ``summary`` dict."""

    coherence: CoherenceResult
    repeats: RepeatResult
    voicing: VoicingResult
    dynamics: DynamicsResult
    summary: dict[str, float]


def shaping(
    ap: Any,
    *,
    phrase_boundaries_beats: Sequence[float] | None = None,
    melody_ids: Sequence[str] | None = None,
    config: ShapingConfig | None = None,
) -> ShapingResult:
    """All tier C shaping features of one aligned performance (see the module docstring)."""
    cfg = config or ShapingConfig()
    basis = score_basis(ap.score, phrase_boundaries_beats=phrase_boundaries_beats)
    tc = tempo_model(ap, cfg.tempo)
    coh = structural_coherence(ap, basis, tc, cfg)
    rep = repeated_material(ap, basis, tc, cfg)
    voi = voicing(ap, basis, tc, cfg, melody_ids=melody_ids)
    dyn = dynamic_compliance(ap, basis, tc, cfg)
    summ: dict[str, float] = {}
    for _, r in coh.summary.iterrows():
        summ[f"coherence_{r['channel']}_r2"] = r["r2"]
        summ[f"coherence_{r['channel']}_r2_no_markings"] = r["r2_no_markings"]
    for _, r in rep.summary.iterrows():
        summ[f"repeat_{r['channel']}_r_mean"] = r["r_mean"]
    summ.update({f"voicing_{k}": v for k, v in voi.summary.items()})
    summ.update({f"dynamics_{k}": v for k, v in dyn.summary.items()})
    return ShapingResult(coh, rep, voi, dyn, summ)
