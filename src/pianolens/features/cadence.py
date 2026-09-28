"""Cadence-derived phrase ends (F-05c): a score-only phrase-boundary source.

Classical phrases end on a cadence: a harmonic arrival (usually V-I in the bass, or an arrival
on V for a half cadence) on a strong beat, followed by rhythmic closure (a long note, a rest,
a thinner texture). DCML places a phrase end on that cadential arrival note, not on the last
note of the phrase (``pianolens.data.batik_mozart``). This module scores every score onset as
a candidate arrival with a small logistic model of interpretable cues, then picks peaks.

Cues (one row per distinct score onset, ``cadence_candidates``)
---------------------------------------------------------------
Pitch content is measured in quarter notes (meter-independent, as the F-04b harmony rule).
``A`` = pitch classes sounding in ``[q, q + window)`` after the onset at quarter ``q``,
``B`` = those in ``[q - window, q)`` (a pitch class counts when it holds at least
``min_weight`` of the window's sounding note-time), ``bass_A`` = lowest pitch sounding at
``q``, ``bass_B`` = lowest pitch sounding just before ``q`` (or at the last onset before a
rest). Intervals are in semitones mod 12.

* ``bass_fifth_down``: ``bass_A - bass_B == 5`` (down a fifth / up a fourth: V-I).
* ``bass_step_up``: 1 or 2 (e.g. IV-V, #IV-V into a half cadence).
* ``bass_step_down``: 10 or 11 (e.g. VI-V).
* ``bass_same``: 0 (e.g. a cadential 6/4 resolving to V over the same bass).
* ``root_triad``: ``A`` is a subset of the major or minor triad on ``bass_A`` (a consonant
  root-position arrival).
* ``major_triad``: ``A`` is a subset of the major triad on ``bass_A``.
* ``dominant_before``: ``B`` holds the leading tone of ``bass_A`` (+11) and lies within the
  dominant seventh on ``bass_A + 7`` plus ``bass_A`` itself (V, V7, vii, with a held root).
* ``leading_tone_before``: ``B`` holds the leading tone of ``bass_A`` (melody notes and
  suspensions allowed).
* ``cad64_before``: ``bass_B == bass_A`` and ``B`` holds the fourth and sixth above it (+5,
  +9): a 6/4 chord over the arrival bass.
* ``harmony_change``: the F-04b bass-plus-template harmony-change rule fires at this onset
  (``pianolens.features.control.harmony_changes``, its defaults).
* ``metrical_strength`` (1 downbeat, 0.75, 0.5, 0.25, 0) and ``is_downbeat``.
* ``melody_long``: ``log2`` of the skyline melody's IOI from this onset over the median melody
  IOI within 2 bars, clipped to [-2, 3] (0 when the onset starts no melody note).
* ``ioi_next_log``: ``log2`` of the IOI to the next onset over the median IOI within 2 bars,
  clipped to [-2, 3].
* ``rest_after``: longest silence (nothing sounding) within the next bar, in bars (0 to 1).
* ``density_drop``: ``log2((onsets in the bar before + 1) / (onsets in the bar after + 1))``.
* ``stable_after``: ``A`` over ``2 * window`` (the arrival harmony is held) is a subset of
  the triad on ``bass_A`` (major or minor).
* ``melody_step_down``: the melody arrives by a descending step (1-2 semitones), e.g. 2-1.
* ``melody_on_root``: the melody pitch class equals ``bass_A`` (the root on top, as in a PAC).
* ``bass_tonic`` / ``bass_dominant``: ``bass_A`` is the tonic / dominant of the key
  (``score_basis`` meta: key signature, else a key estimate).

``prob`` = logistic(``intercept + sum w_i * cue_i``) with ``CadenceConfig.weights``. The
default weights and thresholds were fitted on Batik K.279-K.283 (15 movements; DCML phrase
ends as labels) by ``scripts/check_phrase_f05c.py fit``; all other Batik movements are held
out. Results are in ``docs/specs/phrase-coherence-validation.md`` (F-05c): on the 21 held-out
movements, phrase-end F1 0.46 at +-1 beat (0.59 at +-1 bar) against 0.29 for the proxy's
phrase ends; phrase-start F1 0.44 vs 0.35. That is not enough for tempo coherence: with these
boundaries and ``phrase_detail``, Batik tempo R² is below the proxy's.

Picking ends (``cadence_phrase_ends``)
--------------------------------------
Onsets with ``prob >= threshold`` are accepted greedily by decreasing ``prob``, at least
``min_gap_bars`` bars apart. Phrase starts are derived from the ends: the first onset after
the arrival that follows the longest silence or IOI within ``start_window_bars`` bars
(``start_rule="gap"``), the next onset (``"next"``) or the arrival itself (``"elision"``);
the piece's first onset is always a start.

Citations: cadence as the marker of phrase closure and the DCML cadence labels
(https://github.com/DCMLab/standards, method reference, not in the landscape doc); the
harmony-change rule is F-04b's (``docs/specs/control-validation.md``). Phrase boundaries
drive the phrase-final lengthening in Repp 1992 (https://doi.org/10.1121/1.404425; landscape
section 1.2).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from pianolens.features._score_utils import score_note_frame
from pianolens.features.control import harmony_changes

__all__ = [
    "CUES",
    "DEFAULT_WEIGHTS",
    "CadenceConfig",
    "CadenceResult",
    "cadence_candidates",
    "cadence_phrase_ends",
]

_EPS = 1e-6

CUES: tuple[str, ...] = (
    "bass_fifth_down", "bass_step_up", "bass_step_down", "bass_same",
    "root_triad", "major_triad", "dominant_before", "leading_tone_before", "cad64_before",
    "harmony_change", "metrical_strength", "is_downbeat",
    "melody_long", "ioi_next_log", "rest_after", "density_drop", "stable_after",
    "melody_step_down", "melody_on_root", "bass_tonic", "bass_dominant",
)  # fmt: skip

# Fitted on Batik K.279-K.283 by scripts/check_phrase_f05c.py fit (see the module docstring).
DEFAULT_WEIGHTS: Mapping[str, float] = {
    "intercept": -8.752, "bass_fifth_down": 1.226, "bass_step_up": 0.316,
    "bass_step_down": -0.404, "bass_same": -0.778, "root_triad": -0.380, "major_triad": 0.881,
    "dominant_before": -0.123, "leading_tone_before": 0.454, "cad64_before": 0.813,
    "harmony_change": 0.677, "metrical_strength": 3.207, "is_downbeat": 0.751,
    "melody_long": 0.027, "ioi_next_log": 0.340, "rest_after": -0.960, "density_drop": 0.747,
    "stable_after": 0.775, "melody_step_down": 1.144, "melody_on_root": -0.022,
    "bass_tonic": 0.600, "bass_dominant": 1.418,
}  # fmt: skip


@dataclass(frozen=True)
class CadenceConfig:
    """Parameters (see the module docstring).

    Attributes:
        window_quarters: harmony window before / after the onset, in quarter notes.
        min_weight: share of sounding note-time a pitch class needs to count in a window.
        weights: logistic weights per cue plus ``intercept``.
        threshold: minimum ``prob`` of an accepted end.
        min_gap_bars: minimum distance between accepted ends, in bars.
        start_rule: ``gap`` / ``next`` / ``elision`` (how starts follow ends).
        start_window_bars: search window of the ``gap`` start rule, in bars.
    """

    window_quarters: float = 1.0
    min_weight: float = 0.15
    weights: Mapping[str, float] = field(default_factory=lambda: dict(DEFAULT_WEIGHTS))
    threshold: float = 0.2
    min_gap_bars: float = 1.5
    start_rule: str = "gap"
    start_window_bars: float = 2.0


@dataclass
class CadenceResult:
    """Output of :func:`cadence_phrase_ends`.

    Attributes:
        ends: accepted phrase ends: ``beat``, ``quarter``, ``measure_number``, ``prob``,
            and the cues.
        starts: phrase-start beats (sorted; the first onset included).
        candidates: every onset with its cues and ``prob`` (:func:`cadence_candidates`).
        bars: per bar (``measure_idx`` order): ``measure_idx``, ``measure_number``,
            ``max_prob``, ``is_end`` (an accepted end falls in the bar).
        meta: ``beats_per_bar``, ``key_fifths``, ``key_mode``, ``n_onsets``.
    """

    ends: pd.DataFrame
    starts: list[float]
    candidates: pd.DataFrame
    bars: pd.DataFrame
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def end_beats(self) -> list[float]:
        return sorted(self.ends["beat"].astype(float).tolist())


_TRIADS = {"maj": (0, 4, 7), "min": (0, 3, 7)}


def _pc_weights(on: np.ndarray, off: np.ndarray, pc: np.ndarray, lo: float, hi: float
                ) -> dict[int, float]:
    ov = np.minimum(off, hi) - np.maximum(on, lo)
    m = ov > _EPS
    if not m.any():
        return {}
    w = pd.Series(ov[m]).groupby(pc[m]).sum()
    return (w / w.sum()).to_dict()


def _pcs(weights: dict[int, float], min_weight: float) -> frozenset[int]:
    return frozenset(int(k) for k, v in weights.items() if v >= min_weight - _EPS)


def _subset_triad(pcs: frozenset[int], root: int, kinds: tuple[str, ...]) -> bool:
    if not pcs:
        return False
    return any(pcs <= {(root + i) % 12 for i in _TRIADS[k]} for k in kinds)


def _local_median(x: np.ndarray, v: np.ndarray, half: float) -> np.ndarray:
    """Median of ``v`` over points within ``half`` of each ``x`` (x sorted)."""
    lo = np.searchsorted(x, x - half - _EPS, side="left")
    hi = np.searchsorted(x, x + half + _EPS, side="right")
    return np.array([np.median(v[a:b]) if b > a else np.nan for a, b in zip(lo, hi, strict=True)])


def cadence_candidates(score: Any, config: CadenceConfig | None = None,
                       basis: Any | None = None) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Cue table of every distinct score onset (module docstring) and meta.

    ``basis``: a precomputed :class:`pianolens.features.score_basis.ScoreBasis` of ``score``
    (only its onset table, measures and key are used). Returns ``(candidates, meta)``;
    ``candidates`` has ``beat``, ``quarter``, ``measure_idx``, ``measure_number``, every cue in
    ``CUES`` and ``prob``.
    """
    from pianolens.features.score_basis import BasisConfig, score_basis

    cfg = config or CadenceConfig()
    if basis is None:
        basis = score_basis(score, config=BasisConfig(include_tension=False))
    bpb = float(basis.meta["beats_per_bar"])
    fifths, mode = int(basis.meta.get("key_fifths", 0)), int(basis.meta.get("key_mode", 1))
    tonic = (7 * fifths) % 12 if mode != -1 else (7 * fifths + 9) % 12
    ons = basis.onsets.sort_values("beat").reset_index(drop=True)

    sf = score_note_frame(score)
    sf = sf[~sf["is_grace"] & (sf["dur_quarter"] > 0)].sort_values("quarter")
    nq = sf["quarter"].to_numpy(float)
    nqo = nq + sf["dur_quarter"].to_numpy(float)
    npitch = sf["pitch"].to_numpy(int)
    npc = npitch % 12
    nb = sf["beat"].to_numpy(float)
    nbo = nb + sf["dur_beat"].to_numpy(float)
    q_of_beat = sf.groupby("beat")["quarter"].min()

    b = ons["beat"].to_numpy(float)
    q = q_of_beat.reindex(b).to_numpy(float)
    n = len(b)
    W = cfg.window_quarters
    # the skyline melody (score_basis ``melody_new`` onsets carry ``is_top``; recompute simply)
    top = sf.groupby("beat")["pitch"].max().reindex(b).to_numpy(float)
    held = np.full(n, -1.0)
    for k in range(n):
        m = (nb < b[k] - _EPS) & (nbo > b[k] + _EPS)
        held[k] = npitch[m].max() if m.any() else -1.0
    mel_new = top >= held
    mel_b, mel_p = b[mel_new], top[mel_new]
    mel_ioi = np.append(np.diff(mel_b), np.nan)
    mel_med = _local_median(mel_b, np.nan_to_num(mel_ioi, nan=np.nanmedian(mel_ioi)
                                                  if np.isfinite(mel_ioi).any() else 1.0),
                            2 * bpb)
    mel_long = pd.Series(np.clip(np.log2(np.nan_to_num(mel_ioi / mel_med, nan=1.0)
                                         .clip(1e-3)), -2, 3), index=mel_b)
    mel_prev = pd.Series(np.concatenate([[np.nan], mel_p[:-1]]), index=mel_b)
    ioi = np.append(np.diff(b), np.nan)
    ioi_med = _local_median(b, np.nan_to_num(ioi, nan=np.nanmedian(ioi) if n > 1 else 1.0),
                            2 * bpb)
    ioi_next = np.clip(np.log2(np.nan_to_num(ioi / ioi_med, nan=1.0).clip(1e-3)), -2, 3)
    hc = harmony_changes(score)
    hc_beats = set(np.round(hc["beat"].astype(float), 6)) if len(hc) else set()

    rows = []
    for k in range(n):
        qk, bk = q[k], b[k]
        at = (nq <= qk + _EPS) & (nqo > qk + _EPS)
        bass_a = int(npitch[at].min()) if at.any() else int(npitch[np.argmin(np.abs(nq - qk))])
        before = (nq < qk - _EPS) & (nqo > qk - 0.01)
        if before.any():
            bass_b = int(npitch[before].min())
        else:
            prev = nq < qk - _EPS
            bass_b = int(npitch[prev][nq[prev] == nq[prev].max()].min()) if prev.any() else bass_a
        near = (nq < qk + 2 * W) & (nqo > qk - W)
        a_w = _pc_weights(nq[near], nqo[near], npc[near], qk, qk + W)
        b_w = _pc_weights(nq[near], nqo[near], npc[near], qk - W, qk)
        a2_w = _pc_weights(nq[near], nqo[near], npc[near], qk, qk + 2 * W)
        A, B, A2 = (_pcs(x, cfg.min_weight) for x in (a_w, b_w, a2_w))
        ra, rb = bass_a % 12, bass_b % 12
        iv = (ra - rb) % 12
        lt, dom = (ra + 11) % 12, (ra + 7) % 12
        dom_set = {dom, lt, (ra + 2) % 12, (ra + 5) % 12, ra}
        # rest within the next bar: gaps in the union of sounding intervals (beats)
        hi = bk + bpb
        m = (nb < hi) & (nbo > bk)
        iv_s = sorted(zip(np.maximum(nb[m], bk), np.minimum(nbo[m], hi), strict=True))
        gap, cur = 0.0, bk
        for s0, e0 in iv_s:
            if s0 > cur + _EPS:
                gap = max(gap, s0 - cur)
            cur = max(cur, e0)
        gap = max(gap, hi - cur) if cur < hi - _EPS and bk + bpb <= b[-1] else gap
        n_before = int(np.sum((b >= bk - bpb - _EPS) & (b < bk - _EPS)))
        n_after = int(np.sum((b > bk + _EPS) & (b <= bk + bpb + _EPS)))
        mp = top[k] if mel_new[k] else np.nan
        mprev = float(mel_prev.get(bk, np.nan)) if mel_new[k] else np.nan
        step = mp - mprev if np.isfinite(mp) and np.isfinite(mprev) else np.nan
        ms = float(ons["metrical_strength"].iloc[k])
        rows.append({
            "bass_fifth_down": float(iv == 5), "bass_step_up": float(iv in (1, 2)),
            "bass_step_down": float(iv in (10, 11)), "bass_same": float(iv == 0),
            "root_triad": float(_subset_triad(A, ra, ("maj", "min"))),
            "major_triad": float(_subset_triad(A, ra, ("maj",))),
            "dominant_before": float(lt in B and B <= dom_set),
            "leading_tone_before": float(lt in B),
            "cad64_before": float(rb == ra and {(ra + 5) % 12, (ra + 9) % 12} <= B),
            "harmony_change": float(round(bk, 6) in hc_beats),
            "metrical_strength": ms, "is_downbeat": float(ms >= 1.0 - _EPS),
            "melody_long": float(mel_long.get(bk, 0.0)) if mel_new[k] else 0.0,
            "ioi_next_log": float(ioi_next[k]),
            "rest_after": float(min(gap / bpb, 1.0)),
            "density_drop": float(np.log2((n_before + 1) / (n_after + 1))),
            "stable_after": float(_subset_triad(A2, ra, ("maj", "min"))),
            "melody_step_down": float(np.isfinite(step) and -2 <= step <= -1),
            "melody_on_root": float(np.isfinite(mp) and int(mp) % 12 == ra),
            "bass_tonic": float(ra == tonic), "bass_dominant": float(ra == (tonic + 7) % 12),
        })  # fmt: skip
    cues = pd.DataFrame(rows, columns=list(CUES))
    out = pd.concat([ons[["beat", "measure_idx", "measure_number"]].reset_index(drop=True)
                     .assign(quarter=q), cues], axis=1)
    out["prob"] = cadence_prob(out, cfg.weights)
    meta = {"beats_per_bar": bpb, "key_fifths": fifths, "key_mode": mode, "n_onsets": n}
    return out, meta


def cadence_prob(cues: pd.DataFrame, weights: Mapping[str, float]) -> np.ndarray:
    """Logistic probability from cue columns and ``weights`` (``intercept`` plus cues)."""
    z = np.full(len(cues), float(weights.get("intercept", 0.0)))
    for c, w in weights.items():
        if c != "intercept" and c in cues:
            z = z + float(w) * cues[c].to_numpy(float)
    return 1.0 / (1.0 + np.exp(-z))


def pick_ends(cand: pd.DataFrame, bpb: float, threshold: float, min_gap_bars: float
              ) -> pd.DataFrame:
    """Greedy peak picking: highest ``prob`` first, at least ``min_gap_bars`` apart."""
    c = cand[cand["prob"] >= threshold].sort_values(["prob", "beat"], ascending=[False, True])
    gap = min_gap_bars * bpb
    acc: list[int] = []
    taken: list[float] = []
    for i, bt in zip(c.index, c["beat"], strict=True):
        if all(abs(bt - t) >= gap - _EPS for t in taken):
            acc.append(i)
            taken.append(float(bt))
    return cand.loc[sorted(acc, key=lambda i: cand.loc[i, "beat"])].reset_index(drop=True)


def starts_from_ends(onset_beats: np.ndarray, max_end: np.ndarray, ends: list[float],
                     bpb: float, rule: str = "gap", window_bars: float = 1.0) -> list[float]:
    """Phrase starts implied by phrase ends (module docstring). ``onset_beats`` sorted,
    ``max_end[k]`` = latest offset of the notes starting at onset ``k`` (beats)."""
    b = np.asarray(onset_beats, float)
    if len(b) == 0:
        return []
    starts = {float(b[0])}
    run_end = np.maximum.accumulate(np.asarray(max_end, float))
    for e in ends:
        if rule == "elision":
            starts.add(float(e))
            continue
        j = int(np.searchsorted(b, e + _EPS, side="right"))
        if j >= len(b):
            continue
        if rule == "next":
            starts.add(float(b[j]))
            continue
        hi = e + window_bars * bpb
        idx = [i for i in range(j, len(b)) if b[i] <= hi + _EPS]
        if not idx:
            starts.add(float(b[j]))
            continue
        # silence before onset i (nothing sounding), else IOI before it; earliest on ties
        score = [(max(b[i] - run_end[i - 1], 0.0), b[i] - b[i - 1]) for i in idx]
        best = max(range(len(idx)), key=lambda t: (round(score[t][0], 6),
                                                   round(score[t][1], 6), -t))
        starts.add(float(b[idx[best]]))
    return sorted(starts)


def cadence_phrase_ends(score: Any, config: CadenceConfig | None = None,
                        basis: Any | None = None) -> CadenceResult:
    """Phrase ends (cadential arrivals) and implied starts of a score (module docstring).

    Args:
        score: ``pianolens.data.types.Score`` (markings are not needed).
        config: :class:`CadenceConfig`; the defaults are the weights and thresholds fitted on
            Batik K.279-K.283.
        basis: optional precomputed ``ScoreBasis`` of ``score``.
    """
    cfg = config or CadenceConfig()
    cand, meta = cadence_candidates(score, cfg, basis)
    bpb = meta["beats_per_bar"]
    ends = pick_ends(cand, bpb, cfg.threshold, cfg.min_gap_bars)
    sf = score_note_frame(score)
    sf = sf[~sf["is_grace"]]
    me = (sf["beat"] + sf["dur_beat"]).groupby(sf["beat"]).max().sort_index()
    starts = starts_from_ends(me.index.to_numpy(float), me.to_numpy(float),
                              ends["beat"].tolist(), bpb, cfg.start_rule, cfg.start_window_bars)
    g = cand.groupby("measure_idx", sort=True)
    bars = pd.DataFrame({"measure_number": g["measure_number"].first(),
                         "max_prob": g["prob"].max()}).reset_index()
    bars["is_end"] = bars["measure_idx"].isin(set(ends["measure_idx"]))
    return CadenceResult(ends, starts, cand, bars, meta)
