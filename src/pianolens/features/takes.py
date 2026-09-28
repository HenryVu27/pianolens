"""Repeated-take analysis (F-07, H5): split each expressive channel into the part a player
repeats across takes and the part that changes from take to take.

Input: two or more takes of the same passage by the same player, each an ``AlignedPerformance``
whose score is the one ``pianolens.align.align_performance`` returned. Takes may follow
different repeat paths: observations are matched across takes by score-note identity, and only
observations present in every take are used (the intersection; counts are reported).

Channels (definitions and units from :mod:`pianolens.features.shaping`)
-----------------------------------------------------------------------
* ``timing``: F-03 timing residual per score position, ``dev_beats`` (fraction of the local
  beat period, so it scales with tempo). Tier B reads the take-specific part of it.
* ``tempo``: F-03 smooth log tempo ratio per score position, ``tempo_log_ratio`` (natural log).
* ``velocity``: MIDI velocity per matched note, ``vel_midi``. Low confidence on transcribed
  MIDI (DECISIONS D-10): report, do not base claims on it.
* ``articulation``: ``art_log_ratio`` per matched note, log(key-down duration / notated
  duration at the local smooth tempo).

Matching keys: notes by ``score_id``; score positions by the smallest ``score_id`` of the
non-grace notes that start there (a note has one onset, so the key follows the note even when
two takes unfold repeats differently and the position's beat differs).

Decomposition
-------------
Per channel, with ``Y`` the ``n x k`` matrix of ``n`` observations in ``k`` takes, each take
centered on its own mean when ``center=True`` (the level offsets are reported separately in
``level_<j>``):

* take-consistent part ``c_i = mean_j Y_ij`` (the curve the player repeats);
* take-specific part ``e_ij = Y_ij - c_i`` (how take ``j`` departs from it).

Variance components come from the two-way (observation x take) ANOVA without replication
(McGraw and Wong 1996, "consistency" model, ICC(3,1) / ICC(3,k)):

    ``MSR = k * sum_i (c_i - g)^2 / (n - 1)``,
    ``MSE = SSE / ((n - 1)(k - 1))`` (observation-by-take interaction, i.e. residual),

* ``var_specific = MSE``: the variance of one take around the true repeated curve;
* ``var_consistent = (MSR - MSE) / k``: variance of the true repeated curve (noise-corrected;
  may be negative in small samples, reported unclipped);
* ``icc_single = (MSR - MSE) / (MSR + (k - 1) MSE)``: reliability of one take, the share of a
  take's (level-free) variance that the player repeats;
* ``icc_mean = (MSR - MSE) / MSR``: reliability of the k-take mean, which equals the
  Spearman-Brown prophecy ``k r / (1 + (k - 1) r)`` of ``icc_single`` (Spearman 1910, Brown 1910);
* ``icc_single_ci_lo`` / ``_hi``: the F-based 95% interval (McGraw and Wong 1996, Table 7).
  It assumes independent observations; smooth channels (``tempo``) are strongly autocorrelated,
  so treat that interval as far too narrow there.

Known answer: if ``Y_ij = s_i + noise_ij`` with ``var(s) = a`` and ``var(noise) = b``, then
``var_consistent -> a``, ``var_specific -> b`` and ``icc_single -> a / (a + b)``.

Structure (H5): :func:`take_structure` regresses the consistent and the specific parts on the
score basis with the F-05 structural-coherence cross-validation (ridge, written-bar blocks,
out-of-fold R²). Pooled regressions of ``e_ij`` on score features are 0 by construction
(``sum_j e_ij = 0`` and every take shares the features), so the specific part is scored per
take. Because ``c`` averages the noise over ``k`` takes and ``e_j`` does not, their R² are not
directly comparable for ``k > 2``; the balanced contrast is per pair of takes ``(j, l)``: the
half-sum ``(Y_j + Y_l) / 2`` and the half-difference ``(Y_j - Y_l) / 2`` carry equal noise
variance when takes are exchangeable, so only structure can separate their R².

Interpretation (F-07 audit, DECISIONS 2026-09-28): the take-consistent part is not shown to be
the player's own intent. Pairs of takes by *different* players pass the same half-sum vs
half-difference test, so a structured consistent part mostly reflects timing that any two
performances of the piece share. What the H5 run supports is narrower: a player's take-specific
part is mostly unstructured by the score basis, so it can be read as noise. Do not label the
consistent part "intent" on this evidence.

Per-bar output: ``bars`` (per channel and bar: mean and SD of the consistent part, RMS of the
take-specific part scaled to a one-take SD, local ICC) and ``bars_by_take`` (signed mean and RMS
of each take's departure: where take 2 rushed or dragged against the others).

Citations: consistent vs take-specific expressive timing across takes: Repp 1992
(grouping-structure timing is highly reproducible within pianists,
https://doi.org/10.1121/1.404425); landscape doc section 1.2-1.3 (expressive timing hierarchy;
Basis Mixer score features). ICC / Spearman-Brown:
McGraw and Wong 1996 (https://doi.org/10.1037/1082-989X.1.1.30) and Shrout and Fleiss 1979
(https://doi.org/10.1037/0033-2909.86.2.420): method references, not in the landscape doc.
"""

from __future__ import annotations

import itertools
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

from pianolens.features.score_basis import MARKING_GROUPS, ScoreBasis, score_basis
from pianolens.features.shaping import (
    CHANNEL_UNITS,
    CHANNELS,
    ShapingConfig,
    _cv_ridge,
    channel_data,
)
from pianolens.features.tempo import TempoCurve, tempo_model

__all__ = [
    "TakesConfig",
    "TakesResult",
    "align_takes",
    "decompose_takes",
    "take_structure",
    "takes_from_files",
    "variance_components",
]

_NOTE_CHANNELS = ("velocity", "articulation")


@dataclass(frozen=True)
class TakesConfig:
    """Parameters.

    Attributes:
        channels: channels to decompose (subset of ``shaping.CHANNELS``).
        center: subtract each take's own mean per channel before decomposing (level
            differences between takes, e.g. one take louder overall, go to ``level_<j>``).
        min_bar_obs: bars with fewer complete observations get NaN local ICC.
        shaping: F-05 config (tempo model, articulation clip, CV folds for
            :func:`take_structure`).
        features: basis columns for :func:`take_structure`: ``"all"`` (every group but
            ``position``) or ``"no_markings"`` (also drops ``MARKING_GROUPS``).
        max_pairs: at most this many take pairs in :func:`take_structure` (the first ones in
            ``itertools.combinations`` order).
    """

    channels: tuple[str, ...] = CHANNELS
    center: bool = True
    min_bar_obs: int = 4
    shaping: ShapingConfig | None = None
    features: str = "all"
    max_pairs: int = 15


@dataclass
class TakesResult:
    """Output of :func:`decompose_takes`.

    Attributes:
        summary: one row per channel: ``channel``, ``unit``, ``k`` (takes), ``n`` (complete
            observations), ``n_dropped`` (observations missing from some take), ``var_total``
            (mean over takes of each take's variance), ``var_consistent``, ``var_specific``,
            ``icc_single`` (+ ``_ci_lo`` / ``_ci_hi``), ``icc_mean`` (Spearman-Brown),
            ``sd_consistent`` / ``sd_specific`` (square roots, channel unit, NaN if negative),
            ``level_<j>`` (take mean minus the mean over takes, before centering).
        bars: per channel and bar (``measure_idx``, ``measure_number``): ``n``,
            ``consistent_mean``, ``consistent_sd``, ``specific_rms`` (one-take SD around the
            consistent curve: sqrt(sum e^2 / (n (k - 1)))), ``icc_local``.
        bars_by_take: per channel, take and bar: ``specific_mean`` (signed) and
            ``specific_rms``.
        pairs: per channel and take pair: ``n``, ``r`` (Pearson of the two takes).
        observations: channel -> one row per complete observation: ``key``, ``beat``,
            ``measure_idx``, ``measure_number``, ``y_<j>`` (centered if ``center``),
            ``consistent``, ``specific_<j>``.
        features: channel -> basis feature columns for the rows of ``observations`` (from the
            first take's score; the same notes in every take).
        feature_groups: basis groups of those columns.
        take_ids: performance ids, in take order.
    """

    summary: pd.DataFrame
    bars: pd.DataFrame
    bars_by_take: pd.DataFrame
    pairs: pd.DataFrame
    observations: dict[str, pd.DataFrame] = field(default_factory=dict)
    features: dict[str, pd.DataFrame] = field(default_factory=dict)
    feature_groups: dict[str, list[str]] = field(default_factory=dict)
    take_ids: list[str] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)


# --------------------------------------------------------------------------- statistics


def variance_components(Y: np.ndarray, alpha: float = 0.05) -> dict[str, float]:
    """Two-way (rows = observations, columns = takes) consistency variance components.

    ``Y`` is ``n x k`` without missing values. Returns ``n``, ``k``, ``ms_rows``, ``ms_error``,
    ``var_consistent``, ``var_specific``, ``icc_single`` (ICC(3,1)), ``icc_single_ci_lo`` /
    ``_ci_hi`` (F-based, independent observations assumed) and ``icc_mean`` (ICC(3,k) =
    Spearman-Brown of ICC(3,1)). Definitions in the module docstring.
    """
    Y = np.asarray(Y, float)
    n, k = Y.shape
    out: dict[str, float] = {"n": float(n), "k": float(k)}
    nan_keys = ("ms_rows", "ms_error", "var_consistent", "var_specific", "icc_single",
                "icc_single_ci_lo", "icc_single_ci_hi", "icc_mean")  # fmt: skip
    if n < 3 or k < 2 or not np.all(np.isfinite(Y)):
        return {**out, **{kk: float("nan") for kk in nan_keys}}
    g = Y.mean()
    rm = Y.mean(axis=1)
    cm = Y.mean(axis=0)
    ssr = k * float(np.sum((rm - g) ** 2))
    ssc = n * float(np.sum((cm - g) ** 2))
    sse = float(np.sum((Y - g) ** 2)) - ssr - ssc
    msr = ssr / (n - 1)
    mse = max(sse, 0.0) / ((n - 1) * (k - 1))
    out["ms_rows"], out["ms_error"] = msr, mse
    out["var_specific"] = mse
    out["var_consistent"] = (msr - mse) / k
    denom = msr + (k - 1) * mse
    out["icc_single"] = (msr - mse) / denom if denom > 0 else float("nan")
    out["icc_mean"] = (msr - mse) / msr if msr > 0 else float("nan")
    if mse > 0:
        f = msr / mse
        df1, df2 = n - 1, (n - 1) * (k - 1)
        fl = f / stats.f.ppf(1 - alpha / 2, df1, df2)
        fu = f * stats.f.ppf(1 - alpha / 2, df2, df1)
        out["icc_single_ci_lo"] = (fl - 1) / (fl + k - 1)
        out["icc_single_ci_hi"] = (fu - 1) / (fu + k - 1)
    else:
        out["icc_single_ci_lo"] = out["icc_single_ci_hi"] = float("nan")
    return out


def spearman_brown(r: float, k: float) -> float:
    """Reliability of the mean of ``k`` parallel measurements with single reliability ``r``."""
    return k * r / (1 + (k - 1) * r)


# --------------------------------------------------------------------------- matching


def _position_keys(basis: ScoreBasis) -> pd.Series:
    """beat (rounded 1e-6) -> smallest score id starting there."""
    b = basis.notes[["beat", "score_id"]].copy()
    b["_k"] = b["beat"].round(6)
    return b.groupby("_k")["score_id"].min()


def _keyed(df: pd.DataFrame, channel: str, pos_keys: pd.Series) -> pd.DataFrame:
    df = df.copy()
    if channel in _NOTE_CHANNELS:
        df["key"] = df["score_id"].astype(str)
    else:
        df["key"] = pos_keys.reindex(df["beat"].round(6).to_numpy()).to_numpy()
        df = df[df["key"].notna()]
    return df.drop_duplicates("key", keep="first")


def _feature_cols(groups: dict[str, list[str]], which: str) -> list[str]:
    if which == "all":
        drop: tuple[str, ...] = ("position",)
    elif which == "no_markings":
        drop = ("position", *MARKING_GROUPS)
    else:
        raise ValueError(f"unknown feature set {which!r}")
    return [c for g, cols in groups.items() if g not in drop for c in cols]


# --------------------------------------------------------------------------- decomposition


def decompose_takes(
    aps: Sequence[Any],
    bases: Sequence[ScoreBasis | None] | ScoreBasis | None = None,
    tempos: Sequence[TempoCurve | None] | None = None,
    config: TakesConfig | None = None,
    take_ids: Sequence[str] | None = None,
) -> TakesResult:
    """Split each channel of ``k >= 2`` takes into a take-consistent and a take-specific part.

    Args:
        aps: the takes (``AlignedPerformance``; same passage, same player).
        bases: one :class:`ScoreBasis` shared by all takes (same performed score), or one per
            take, or None (computed; takes sharing one ``Score`` object share one basis).
        tempos: F-03 tempo curves per take (computed if None).
        config: :class:`TakesConfig`.
        take_ids: labels for the takes (default: performance ids, made unique).

    Returns:
        :class:`TakesResult` (definitions in the module docstring). Unmatched, interpolated and
        grace notes are skipped by the F-03 / F-05 channel code and counted in ``meta``.
    """
    cfg = config or TakesConfig()
    scfg = cfg.shaping or ShapingConfig()
    k = len(aps)
    if k < 2:
        raise ValueError("need at least two takes")
    bad = [c for c in cfg.channels if c not in CHANNELS]
    if bad:
        raise ValueError(f"unknown channels {bad}")
    if isinstance(bases, ScoreBasis):
        bases_l: list[ScoreBasis | None] = [bases] * k
    else:
        bases_l = list(bases) if bases is not None else [None] * k
    tempos_l = list(tempos) if tempos is not None else [None] * k
    cache: dict[int, ScoreBasis] = {}
    per_take: list[dict[str, pd.DataFrame]] = []
    first_basis: ScoreBasis | None = None
    skipped: list[dict[str, Any]] = []
    for ap, b, t in zip(aps, bases_l, tempos_l, strict=True):
        if ap.score is None or ap.alignment is None:
            raise ValueError("every take needs a score and an alignment")
        if b is None:
            b = cache.get(id(ap.score))
            if b is None:
                b = cache[id(ap.score)] = score_basis(ap.score)
        if t is None:
            t = tempo_model(ap, scfg.tempo)
        first_basis = first_basis or b
        pk = _position_keys(b)
        data = channel_data(ap, b, t, scfg)
        per_take.append({ch: _keyed(data[ch], ch, pk) for ch in cfg.channels})
        skipped.append({kk: t.summary.get(kk) for kk in ("n_match", "n_interpolated_skipped",
                                                          "n_insertion", "n_deletion",
                                                          "n_grace_skipped")})
    assert first_basis is not None
    ids = list(take_ids) if take_ids is not None else [str(ap.performance.performance_id)
                                                        for ap in aps]
    if len(set(ids)) < k:
        ids = [f"{x}#{j}" for j, x in enumerate(ids)]
    groups = {g: list(c) for g, c in first_basis.groups.items()}
    feat_all = [c for cols in groups.values() for c in cols]

    rows, bars, bars_take, pairs = [], [], [], []
    obs_out: dict[str, pd.DataFrame] = {}
    feat_out: dict[str, pd.DataFrame] = {}
    for ch in cfg.channels:
        frames = [pt[ch] for pt in per_take]
        common = set(frames[0]["key"])
        for f in frames[1:]:
            common &= set(f["key"])
        union = set().union(*(set(f["key"]) for f in frames))
        base = frames[0][frames[0]["key"].isin(common)].sort_values("beat").reset_index(drop=True)
        Y = np.column_stack([f.set_index("key").loc[base["key"], "y"].to_numpy(float)
                             for f in frames]) if len(base) else np.zeros((0, k))
        row: dict[str, Any] = {"channel": ch, "unit": CHANNEL_UNITS[ch], "k": k, "n": len(base),
                               "n_dropped": len(union) - len(common)}
        levels = Y.mean(axis=0) if len(base) else np.full(k, np.nan)
        if cfg.center and len(base):
            Y = Y - levels
        vc = variance_components(Y)
        row["var_total"] = float(np.mean(Y.var(axis=0, ddof=1))) if len(base) > 1 else np.nan
        for key in ("var_consistent", "var_specific", "icc_single", "icc_single_ci_lo",
                    "icc_single_ci_hi", "icc_mean"):
            row[key] = vc[key]
        with np.errstate(invalid="ignore"):
            row["sd_consistent"] = float(np.sqrt(vc["var_consistent"])) \
                if vc["var_consistent"] >= 0 else np.nan
            row["sd_specific"] = float(np.sqrt(vc["var_specific"]))
        lv = levels - np.mean(levels) if len(base) else levels
        for j in range(k):
            row[f"level_{j}"] = float(lv[j])
        rows.append(row)

        c = Y.mean(axis=1) if len(base) else np.zeros(0)
        E = Y - c[:, None] if len(base) else np.zeros((0, k))
        obs = base[["key", "beat", "measure_idx", "measure_number"]].copy()
        for j in range(k):
            obs[f"y_{j}"] = Y[:, j]
        obs["consistent"] = c
        for j in range(k):
            obs[f"specific_{j}"] = E[:, j]
        obs_out[ch] = obs
        feat_out[ch] = base[[x for x in feat_all if x in base.columns]].reset_index(drop=True)

        for j, jj in itertools.combinations(range(k), 2):
            r = float(np.corrcoef(Y[:, j], Y[:, jj])[0, 1]) if len(base) > 2 and \
                Y[:, j].std() > 0 and Y[:, jj].std() > 0 else np.nan
            pairs.append({"channel": ch, "take_a": ids[j], "take_b": ids[jj], "n": len(base),
                          "r": r})
        if len(base) == 0:
            continue
        for mi, ii in obs.groupby("measure_idx", sort=True).indices.items():
            Yb, Eb = Y[ii], E[ii]
            nb = len(ii)
            loc = variance_components(Yb) if nb >= cfg.min_bar_obs else {"icc_single": np.nan}
            bars.append({
                "channel": ch, "measure_idx": int(mi),
                "measure_number": int(obs["measure_number"].iloc[ii[0]]), "n": nb,
                "consistent_mean": float(c[ii].mean()),
                "consistent_sd": float(c[ii].std()) if nb > 1 else np.nan,
                "specific_rms": float(np.sqrt(np.sum(Eb**2) / (nb * (k - 1)))),
                "icc_local": loc["icc_single"],
            })
            for j in range(k):
                bars_take.append({
                    "channel": ch, "take": ids[j], "measure_idx": int(mi),
                    "measure_number": int(obs["measure_number"].iloc[ii[0]]), "n": nb,
                    "specific_mean": float(Eb[:, j].mean()),
                    "specific_rms": float(np.sqrt(np.mean(Eb[:, j] ** 2))),
                })
    return TakesResult(
        summary=pd.DataFrame(rows), bars=pd.DataFrame(bars), bars_by_take=pd.DataFrame(bars_take),
        pairs=pd.DataFrame(pairs), observations=obs_out, features=feat_out,
        feature_groups=groups, take_ids=ids,
        meta={"skipped": skipped, "center": cfg.center, "basis_meta": first_basis.meta},
    )


# --------------------------------------------------------------------------- structure (H5)


def _r2(X: np.ndarray, y: np.ndarray, measure: np.ndarray, scfg: ShapingConfig) -> float:
    if len(y) < 20 or float(np.std(y)) < 1e-12:
        return float("nan")
    return _cv_ridge(X, y, measure, scfg)[1]


def take_structure(res: TakesResult, config: TakesConfig | None = None) -> pd.DataFrame:
    """How much of the consistent and of the take-specific part score structure explains.

    Per channel, out-of-fold R² (F-05 structural-coherence CV: ridge on the score basis,
    written-bar blocks, nested penalty) of:

    * ``r2_consistent``: the take-consistent curve ``c``;
    * ``r2_specific``: each take's departure ``e_j``, fitted per take, averaged over takes;
    * ``r2_pair_sum`` / ``r2_pair_diff``: per pair of takes, the half-sum and half-difference
      (balanced noise; see the module docstring), averaged over at most ``max_pairs`` pairs;
      ``delta_pair = r2_pair_sum - r2_pair_diff``.

    Also ``var_pair_sum`` / ``var_pair_diff`` (mean variances, channel unit squared), ``n``,
    ``k``, ``n_pairs``, ``n_written_bars``, ``n_blocks`` (``ceil(n_written_bars / block_bars)``).
    R² is about 0 or below when the score says nothing. Minimum length as in F-05 structural
    coherence: R² is NaN unless ``n_blocks >= min_blocks`` and ``n_written_bars >=
    min_written_bars`` (``ShapingConfig``); ``undefined_reason`` says why (empty if defined).
    """
    cfg = config or TakesConfig()
    scfg = cfg.shaping or ShapingConfig()
    cols = _feature_cols(res.feature_groups, cfg.features)
    rows = []
    for ch, obs in res.observations.items():
        k = len(res.take_ids)
        row: dict[str, Any] = {"channel": ch, "unit": CHANNEL_UNITS[ch], "n": len(obs), "k": k}
        if len(obs) < 20:
            rows.append({**row, "undefined_reason": "too_few_rows"})
            continue
        F = res.features[ch]
        X = F[[c for c in cols if c in F.columns]].to_numpy(float)
        m = obs["measure_number"].to_numpy()
        # same minimum-length rule as F-05d structural coherence (shaping._coherence)
        n_bars = int(len(np.unique(m.astype(int))))
        row["n_written_bars"] = n_bars
        row["n_blocks"] = -(-n_bars // max(scfg.block_bars, 1))
        reason = ("too_few_bars" if n_bars < scfg.min_written_bars
                  else "too_few_blocks" if row["n_blocks"] < scfg.min_blocks else "")
        row["undefined_reason"] = reason
        if reason:
            rows.append(row)
            continue
        row["r2_consistent"] = _r2(X, obs["consistent"].to_numpy(float), m, scfg)
        row["r2_specific"] = float(np.nanmean([
            _r2(X, obs[f"specific_{j}"].to_numpy(float), m, scfg) for j in range(k)]))
        s2, d2, vs, vd = [], [], [], []
        for j, jj in list(itertools.combinations(range(k), 2))[: cfg.max_pairs]:
            a, b = obs[f"y_{j}"].to_numpy(float), obs[f"y_{jj}"].to_numpy(float)
            s, d = (a + b) / 2, (a - b) / 2
            s2.append(_r2(X, s, m, scfg))
            d2.append(_r2(X, d, m, scfg))
            vs.append(float(np.var(s)))
            vd.append(float(np.var(d)))
        row["n_pairs"] = len(s2)
        row["r2_pair_sum"] = float(np.nanmean(s2))
        row["r2_pair_diff"] = float(np.nanmean(d2))
        row["delta_pair"] = row["r2_pair_sum"] - row["r2_pair_diff"]
        row["var_pair_sum"] = float(np.mean(vs))
        row["var_pair_diff"] = float(np.mean(vd))
        rows.append(row)
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- Henry's takes


def align_takes(score: Any, performances: Sequence[Any], **kwargs: Any) -> list[Any]:
    """Align each take to the same score (``pianolens.align.align_performance``).

    Each take picks its own repeat path; :func:`decompose_takes` then matches notes across takes
    by score-note id, so takes that skip different repeats still line up on the notes they
    share. ``kwargs`` go to ``align`` (e.g. ``repeats="minimal"`` to force one path)."""
    from pianolens.align import align_performance

    return [align_performance(score, p, **kwargs) for p in performances]


def takes_from_files(
    score_path: str | Path,
    midi_paths: Sequence[str | Path],
    *,
    performer: str = "henry",
    piece_id: str | None = None,
    provenance: str = "sensor",
    **align_kwargs: Any,
) -> list[Any]:
    """Load a score (MusicXML / MEI / MIDI) and MIDI takes from disk and align every take.

    Returns aligned takes ready for :func:`decompose_takes`. ``provenance``: ``sensor`` for a
    digital piano's MIDI out, ``transcribed`` for MIDI transcribed from audio (D-10: then read
    velocity as low confidence)."""
    from pianolens.align import load_score_part
    from pianolens.data.midi_io import performance_from_midi, score_from_midi
    from pianolens.data.types import PerformerId, PieceId, score_from_partitura

    sp = Path(score_path)
    pid = PieceId(piece_id or sp.stem)
    if sp.suffix.lower() in (".mid", ".midi"):
        score = score_from_midi(sp, score_id=f"local:{sp.name}", piece_id=pid)
    else:
        score = score_from_partitura(load_score_part(sp), score_id=f"local:{sp.name}",
                                     piece_id=pid, source_path=sp, keep_part=True)
    perfs = [performance_from_midi(Path(p), dataset="local", performance_id=f"local:{Path(p).stem}",
                                   piece_id=pid, performer_id=PerformerId(f"local:{performer}"),
                                   provenance=provenance)  # type: ignore[arg-type]
             for p in midi_paths]
    return align_takes(score, perfs, **align_kwargs)
