"""Hand from the score: staff, voice and pitch rules, and their agreement with hand labels.

Hand synchrony (``control.hand_synchrony``) and any per-hand feedback read the score staff as
the hand: staff 1 (upper, after ``align._adapters.normalise_piano_staves``) is the right hand,
staff 2 the left. BL-19 measured how often score-only proxies flag that rule as doubtful; BL-19b
scores the rules against per-note hand labels from video (PianoVAM, ``pianovam.hand_labels``).

Rules (each returns ``"R"``, ``"L"`` or ``""`` per note):

* :func:`staff_hand`: staff 1 -> R, staff 2 -> L, any other staff -> "".
* :func:`voice_hand`: the hand of the most common staff of the note's MusicXML voice within the
  score (ties: the note's own staff). This turns BL-19's P1 flag (cross-staff voice) into a rule:
  a voice that dips into the other staff keeps its hand.
* :func:`pitch_split_hand`: pitch at or above ``split`` (default 60, middle C) -> R. The simplest
  score-free baseline.

Agreement statistics: :func:`mismatch` (share of labelled notes where a rule differs from the
label, in [0, 1]), :func:`event_mismatch` (hand-sync events with any mismatched note, the unit
hand synchrony averages), and cluster-bootstrap helpers (:func:`cluster_ratio_ci`,
:func:`cluster_mean_ci`, :func:`t_interval`), resampling whole pieces as the project's hard
rule 1 asks.

Citations (``docs/research/2026-09-27-landscape.md``): hand labels from PianoVAM (ISMIR 2025,
arXiv 2509.08800; dataset table); between-hand asynchrony, the measure that depends on the hand
assignment, Goebl 2001 and Goebl, Flossmann, Widmer 2009 ("Hand and chord asynchrony"). Units:
shares in [0, 1]; pitch in MIDI numbers.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pandas as pd

__all__ = [
    "cluster_mean_ci",
    "cluster_ratio_ci",
    "event_mismatch",
    "mismatch",
    "noise_corrected",
    "pitch_split_hand",
    "staff_hand",
    "t_interval",
    "voice_hand",
    "wilson",
]


def staff_hand(staff: np.ndarray | pd.Series) -> np.ndarray:
    """Staff 1 -> ``"R"``, staff 2 -> ``"L"``, anything else -> ``""``."""
    s = np.asarray(staff)
    return np.where(s == 1, "R", np.where(s == 2, "L", ""))


def pitch_split_hand(pitch: np.ndarray | pd.Series, split: int = 60) -> np.ndarray:
    """MIDI pitch >= ``split`` -> ``"R"``, else ``"L"`` (baseline rule)."""
    return np.where(np.asarray(pitch) >= split, "R", "L")


def voice_hand(score_notes: pd.DataFrame) -> pd.Series:
    """Hand of the modal staff of each note's voice, for one score.

    ``score_notes``: every note of one score with ``voice`` and ``staff`` (grace notes and
    staves other than 1 / 2 are ignored when counting). Returns a Series aligned with
    ``score_notes`` (``""`` for notes not on staff 1 or 2). Ties keep the note's own staff."""
    d = score_notes
    s12 = d["staff"].isin([1, 2])
    cnt_mask = s12 & ~d.get("is_grace", pd.Series(False, index=d.index)).astype(bool)
    counts = (d[cnt_mask].groupby(["voice", "staff"]).size().unstack(fill_value=0)
              .reindex(columns=[1, 2], fill_value=0))  # fmt: skip
    n1 = d["voice"].map(counts[1]).fillna(0).to_numpy()
    n2 = d["voice"].map(counts[2]).fillna(0).to_numpy()
    own = d["staff"].to_numpy()
    modal = np.where(n1 > n2, 1, np.where(n2 > n1, 2, own))
    out = staff_hand(modal)
    out[~s12.to_numpy()] = ""
    return pd.Series(out, index=d.index)


def mismatch(rule: np.ndarray, label: np.ndarray) -> float:
    """Share of notes with a label (``"L"`` / ``"R"``) whose rule hand differs. NaN if none."""
    rule, label = np.asarray(rule), np.asarray(label)
    ok = np.isin(label, ["L", "R"]) & np.isin(rule, ["L", "R"])
    return float((rule[ok] != label[ok]).mean()) if ok.any() else float("nan")


def event_mismatch(notes: pd.DataFrame, event_cols: list[str], rule: str = "rule",
                   label: str = "hand") -> pd.DataFrame:
    """Hand-sync events and whether each is affected.

    ``notes``: labelled notes with ``staff``, a rule-hand column and a label column. An event
    is a group of ``event_cols`` (for example recording, take, score onset) with at least one
    note on staff 1 and one on staff 2. It is affected when any of its notes has rule != label.
    Returns one row per event with ``affected`` (bool), plus the ``event_cols``."""
    d = notes[notes["staff"].isin([1, 2])].copy()
    d["_bad"] = d[rule].to_numpy() != d[label].to_numpy()
    g = d.groupby(event_cols, sort=False).agg(n_st=("staff", "nunique"), affected=("_bad", "any"))
    return g[g["n_st"] == 2].drop(columns="n_st").reset_index()


def noise_corrected(m: float, e: float) -> float:
    """Observed mismatch ``m`` corrected for a symmetric label error ``e``: (m - e) / (1 - 2e).
    Assumes label errors are independent of rule errors."""
    return (m - e) / (1.0 - 2.0 * e)


def wilson(k: int, n: int, z: float = 1.959964) -> tuple[float, float]:
    """Wilson score interval for a binomial share ``k / n``."""
    if n == 0:
        return float("nan"), float("nan")
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return float(c - h), float(c + h)


def cluster_ratio_ci(num: np.ndarray, den: np.ndarray, n_boot: int = 2000, seed: int = 0,
                     paired: Callable[[np.ndarray], float] | None = None
                     ) -> tuple[float, float, float]:
    """Pooled ratio sum(num) / sum(den) over clusters, with a cluster-bootstrap 95% interval.

    ``num`` / ``den``: one value per cluster (piece). Returns (estimate, low, high)."""
    num, den = np.asarray(num, float), np.asarray(den, float)
    est = num.sum() / den.sum() if den.sum() > 0 else float("nan")
    rng = np.random.default_rng(seed)
    k = len(num)
    idx = rng.integers(0, k, size=(n_boot, k))
    dn = den[idx].sum(1)
    with np.errstate(invalid="ignore", divide="ignore"):
        b = num[idx].sum(1) / dn
    lo, hi = np.nanpercentile(b, [2.5, 97.5])
    return float(est), float(lo), float(hi)


def cluster_mean_ci(values: np.ndarray, n_boot: int = 2000, seed: int = 0,
                    stat: Callable[[np.ndarray], float] = np.mean
                    ) -> tuple[float, float, float]:
    """``stat`` over clusters (default the unweighted mean) with a bootstrap 95% interval."""
    v = np.asarray(values, float)
    v = v[~np.isnan(v)]
    if len(v) == 0:
        return float("nan"), float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    b = np.array([stat(v[rng.integers(0, len(v), len(v))]) for _ in range(n_boot)])
    lo, hi = np.percentile(b, [2.5, 97.5])
    return float(stat(v)), float(lo), float(hi)


def t_interval(values: np.ndarray, conf: float = 0.95) -> tuple[float, float, float]:
    """Mean of ``values`` with a Student-t interval (NaNs dropped)."""
    from scipy import stats

    v = np.asarray(values, float)
    v = v[~np.isnan(v)]
    if len(v) < 2:
        return (float(v.mean()) if len(v) else float("nan")), float("nan"), float("nan")
    m, se = v.mean(), v.std(ddof=1) / np.sqrt(len(v))
    h = se * stats.t.ppf(0.5 + conf / 2, len(v) - 1)
    return float(m), float(m - h), float(m + h)
