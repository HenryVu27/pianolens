"""Interchange items for expression-model training and evaluation (R-07), plus the flat
("deadpan") and noisy variants that any typicality score must be tested against.

An *interchange item* is a flat dict of numpy arrays, saved as ``.npz``, that the model adapters
(own virtual environments) turn into MIDI. It extends the R-06 format
(``experiments/2026-09-27-R-06-expression-model-h2h/prepare.py``) and is read by the same
adapters:

``score_onset_q, score_dur_q, pitch, perf_onset_sec, perf_dur_sec, velocity, pedal``
    matched notes in score order (:func:`pianolens.models.expression_io.matched_pairs`);
``spq_cond, vel_cond``
    the conditioning: global seconds per quarter and median velocity of the rendition;
``origin, ts``
    bar grid (:func:`pianolens.models.expression_io.time_signature_events`);
``score_id``
    score note ids.

:func:`item_variants` builds, from one real item, the variants pre-registered in R-07: exact
deadpan, velocity-shifted deadpans, a 15% slower deadpan, deadpan plus small noise, the two
half-deadpans, timing / velocity jitter, and scaled (exaggerated / damped) expression. Every
variant keeps the real item's conditioning and note set, so a score compares like with like.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from pianolens.models.expression_io import (
    NotePairs,
    global_seconds_per_quarter,
    matched_pairs,
    time_signature_events,
)

__all__ = [
    "FLAT_TRAIN",
    "VARIANTS",
    "flat_training_rendition",
    "interchange_from_aligned",
    "item_variants",
    "load_item",
    "pairs_from_item",
    "save_item",
    "score_side",
]

LEGATO = 0.95
GRACE_Q = 1 / 16

# name: (description, parameters). Order is the reporting order.
VARIANTS: dict[str, dict] = {
    "deadpan": {"kind": "deadpan"},
    "deadpan_vel+12": {"kind": "deadpan", "vel_shift": 12},
    "deadpan_vel-12": {"kind": "deadpan", "vel_shift": -12},
    "deadpan_slow15": {"kind": "deadpan", "tempo_factor": 1.15},
    "deadpan_noise10_4": {"kind": "deadpan", "t_sd": 0.010, "v_sd": 4.0},
    "deadpan_noise20_8": {"kind": "deadpan", "t_sd": 0.020, "v_sd": 8.0},
    "half_flat_timing": {"kind": "half", "flat": "timing"},
    "half_flat_velocity": {"kind": "half", "flat": "velocity"},
    "jitT10": {"kind": "jitter", "t_sd": 0.010},
    "jitT20": {"kind": "jitter", "t_sd": 0.020},
    "jitT40": {"kind": "jitter", "t_sd": 0.040},
    "jitV4": {"kind": "jitter", "v_sd": 4.0},
    "jitV8": {"kind": "jitter", "v_sd": 8.0},
    "jitV16": {"kind": "jitter", "v_sd": 16.0},
    "scale1.5": {"kind": "scale", "a": 1.5},
    "scale0.5": {"kind": "scale", "a": 0.5},
}


def score_side(score) -> dict:
    """Score notes (first of each (onset, pitch)) and the bar grid of a ``Score``."""
    n = score.notes
    n = n[np.lexsort((n["pitch"], n["onset_quarter"]))]
    key = np.round(n["onset_quarter"] * 1e6).astype(np.int64) * 128 + n["pitch"]
    _, first = np.unique(key, return_index=True)
    n = n[np.sort(first)]
    origin, ts = time_signature_events(score.measures, score.notes)
    return {"notes": n, "origin": origin, "ts": np.array(ts, dtype=float).reshape(-1, 3)}


def interchange_from_aligned(ap, min_notes: int = 16) -> tuple[dict | None, dict]:
    """Interchange item of an ``AlignedPerformance`` (matched notes only).

    Returns ``(item or None, info)``; ``info`` has ``n_notes``, ``n_score`` (distinct score notes)
    and ``match_share`` = matched / distinct score notes. The item is None when fewer than
    ``min_notes`` notes are matched or the global tempo is not positive.
    """
    perf = ap.performance
    ss = score_side(ap.score)
    pairs = matched_pairs(ap.score.notes, perf.notes, ap.alignment.pairs, perf.pedal)
    n_score = len(ss["notes"])
    info = {"n_notes": len(pairs), "n_score": n_score,
            "match_share": len(pairs) / max(1, n_score)}
    if len(pairs) < min_notes:
        return None, {**info, "excluded": "too_few_notes"}
    spq = global_seconds_per_quarter(pairs.score_onset_q, pairs.perf_onset_sec)
    if not np.isfinite(spq) or spq <= 0:
        return None, {**info, "excluded": "bad_tempo"}
    item = {**pairs.to_npz_dict(), "score_id": pairs.score_id.astype(str),
            "spq_cond": float(spq), "vel_cond": float(round(float(np.median(pairs.velocity)))),
            "origin": float(ss["origin"]), "ts": ss["ts"]}
    return item, {**info, "excluded": ""}


def save_item(path: Path | str, item: dict, **extra) -> None:
    np.savez_compressed(path, **item, **{k: np.asarray(v) for k, v in extra.items()})


def load_item(path: Path | str) -> dict:
    z = np.load(path, allow_pickle=False)
    return {k: z[k] for k in z.files}


# ------------------------------------------------------------------------------ variants


def _nominal_dur(item: dict, spq: float) -> np.ndarray:
    d = np.where(item["score_dur_q"] > 0, item["score_dur_q"], GRACE_Q)
    return d * spq


def _flat_onsets(item: dict, spq: float) -> np.ndarray:
    so = item["score_onset_q"] - item["score_onset_q"].min()
    return so * spq


def _tempo_line(item: dict) -> np.ndarray:
    """Least-squares straight line of performed onset on score onset, evaluated per note."""
    so = item["score_onset_q"].astype(float)
    po = item["perf_onset_sec"].astype(float)
    spq = float(item["spq_cond"])
    b = float(np.mean(po) - spq * np.mean(so))
    return b + spq * so


def _with(item: dict, onset=None, dur=None, vel=None, pedal=None) -> dict:
    out = dict(item)
    if onset is not None:
        out["perf_onset_sec"] = np.asarray(onset, float)
    if dur is not None:
        out["perf_dur_sec"] = np.maximum(np.asarray(dur, float), 1e-3)
    if vel is not None:
        out["velocity"] = np.clip(np.round(np.asarray(vel, float)), 1, 127).astype(int)
    if pedal is not None:
        out["pedal"] = np.asarray(pedal, float).reshape(-1, 2)
    return out


def item_variants(item: dict, seed: int, names: list[str] | None = None) -> dict[str, dict]:
    """Variants of a real item (see :data:`VARIANTS`), all with the item's own conditioning.

    * ``deadpan*``: exact score timing at ``spq_cond`` (times ``tempo_factor``), constant
      velocity ``vel_cond`` (+ ``vel_shift``), durations 0.95 x nominal, no pedal; optional
      independent Gaussian noise on onsets (``t_sd`` s) and velocities (``v_sd``).
    * ``half_flat_timing``: deadpan onsets and durations with the human velocities (no pedal).
      ``half_flat_velocity``: human onsets, durations and pedal with constant ``vel_cond``.
    * ``jit*``: Gaussian noise on the human onsets (durations kept) or velocities.
    * ``scale<a>``: human deviations from the flat rendition multiplied by ``a``: velocity
      around ``vel_cond``, onsets around the least-squares tempo line, log articulation around
      the nominal duration. Onset order can change for ``a > 1``.
    """
    rng = np.random.default_rng(seed)
    spq = float(item["spq_cond"])
    vc = float(item["vel_cond"])
    n = len(item["pitch"])
    human_on = item["perf_onset_sec"].astype(float)
    human_du = item["perf_dur_sec"].astype(float)
    human_ve = item["velocity"].astype(float)
    empty = np.zeros((0, 2))
    out = {}
    for name in names or list(VARIANTS):
        p = VARIANTS[name]
        k = p["kind"]
        if k == "deadpan":
            f = p.get("tempo_factor", 1.0)
            on = _flat_onsets(item, spq * f)
            du = _nominal_dur(item, spq * f) * LEGATO
            ve = np.full(n, vc + p.get("vel_shift", 0.0))
            if p.get("t_sd"):
                on = on + rng.normal(0, p["t_sd"], n)
            if p.get("v_sd"):
                ve = ve + rng.normal(0, p["v_sd"], n)
            out[name] = _with(item, on, du, ve, empty)
        elif k == "half":
            if p["flat"] == "timing":
                out[name] = _with(item, _flat_onsets(item, spq), _nominal_dur(item, spq) * LEGATO,
                                  human_ve, empty)
            else:
                out[name] = _with(item, vel=np.full(n, vc))
        elif k == "jitter":
            on = human_on + rng.normal(0, p.get("t_sd", 0.0), n) if p.get("t_sd") else None
            ve = human_ve + rng.normal(0, p.get("v_sd", 0.0), n) if p.get("v_sd") else None
            out[name] = _with(item, on, None, ve)
        elif k == "scale":
            a = p["a"]
            line = _tempo_line(item)
            nom = _nominal_dur(item, spq)
            ok = item["score_dur_q"] >= GRACE_Q
            du = human_du.copy()
            du[ok] = nom[ok] * np.exp(a * np.log(np.maximum(human_du[ok], 1e-3) / nom[ok]))
            out[name] = _with(item, line + a * (human_on - line), du, vc + a * (human_ve - vc))
        else:  # pragma: no cover - VARIANTS is fixed
            raise ValueError(k)
    return out


# The flat-playing model F of R-07 is trained on these renditions. The family is deliberately
# narrower than the test variants: no velocity offset, no tempo change, noise up to 10 ms / 4.
FLAT_TRAIN = {"t_sd_max": 0.010, "v_sd_max": 4.0, "legato": (0.85, 1.0)}


def flat_training_rendition(item: dict, rng: np.random.Generator) -> dict:
    """One random flat rendition of an item for training the flat model F.

    Score timing at ``spq_cond``, velocity ``vel_cond``, durations ``legato`` x nominal with
    ``legato ~ U(0.85, 1.0)``, plus Gaussian noise with s.d. ``U(0, 10 ms)`` on onsets and
    ``U(0, 4)`` on velocities (s.d. drawn once per rendition). No pedal.
    """
    spq = float(item["spq_cond"])
    n = len(item["pitch"])
    lo, hi = FLAT_TRAIN["legato"]
    t_sd = rng.uniform(0, FLAT_TRAIN["t_sd_max"])
    v_sd = rng.uniform(0, FLAT_TRAIN["v_sd_max"])
    on = _flat_onsets(item, spq) + rng.normal(0, 1, n) * t_sd
    du = _nominal_dur(item, spq) * rng.uniform(lo, hi)
    ve = float(item["vel_cond"]) + rng.normal(0, 1, n) * v_sd
    return _with(item, on, du, ve, np.zeros((0, 2)))


def pairs_from_item(item: dict) -> NotePairs:
    """``NotePairs`` view of an item (for :func:`expression_io.note_expression`)."""
    ids = item.get("score_id", np.arange(len(item["pitch"])).astype(str))
    return NotePairs(item["score_onset_q"], item["score_dur_q"], item["pitch"],
                     item["perf_onset_sec"], item["perf_dur_sec"], item["velocity"], ids, ids,
                     item.get("pedal", np.zeros((0, 2))))
