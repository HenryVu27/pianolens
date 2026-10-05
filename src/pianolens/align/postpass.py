"""Post-alignment reassignment of same-pitch matches (BL-23).

parangonar's ``DualDTWNoteMatcher`` matches notes pitch by pitch along an onset time map. In a
dense run, a wrong key that equals a nearby written pitch can take that written note's match
("absorption", BL-20): the score note of pitch *y* is matched to the wrong key at the wrong
time, and the performed note that really played it is left unmatched. This module moves such
matches to the better-timed partner.

Rule (:func:`reassign_same_pitch`). For every matched score note *s* (performed partner *p*,
same pitch) that is not a grace note or an ornamented note, the expected onset ``e`` of *s* is
estimated **without** its own match: the median performed onset of its matched chord-mates (same
score onset), or else linear interpolation between the neighbouring score onsets' median matched
onsets. If an unmatched performed note *p'* of the same pitch lies within ``window_sec`` of
``e``, and ``|t(p) - e| - |t(p') - e| > margin_sec``, *s* is re-matched to *p'* and *p* becomes
unmatched (it can then be labelled as a wrong pitch or extra). Candidates are applied greedily,
largest gain first; each score and performed note moves at most once. One pass.

The alignment returned by ``align_performance`` is not changed: the post-pass is applied inside
``features.correctness`` (tier A labels), so validated tier B-D features keep their inputs.

Citation: the absorption mechanism and the proposal are in
``experiments/2026-09-29-BL-20-density/README.md`` (proposal 2); the aligner is parangonar's
DualDTW (Peter et al., TISMIR 2023, landscape section 1.1).
"""

from __future__ import annotations

import numpy as np

__all__ = ["REASSIGN_MARGIN_SEC", "REASSIGN_WINDOW_SEC", "loo_expected_onsets",
           "reassign_same_pitch"]  # fmt: skip

REASSIGN_MARGIN_SEC = 0.03
"""A swap must bring the match at least this much closer to its expected onset (seconds). Equal
to the 30 ms chord window used for local note rates (BL-20), so chord spread alone never
triggers a swap."""

REASSIGN_WINDOW_SEC = 0.1
"""The new partner must lie within this distance of the expected onset (seconds); the same value
as the default wrong-pitch window (``features.correctness.WRONG_PITCH_WINDOW_SEC``)."""


def loo_expected_onsets(
    s_quarter: np.ndarray, s_partner: np.ndarray, p_onset: np.ndarray, idx: np.ndarray
) -> np.ndarray:
    """Expected performed onset (seconds) of score notes ``idx``, leaving their own match out.

    ``s_partner[i]`` is the performed index matched to score note ``i`` (-1 if none). A note with
    matched chord-mates (same ``s_quarter``) gets their median onset; otherwise the value is
    interpolated linearly (``np.interp``, clamped at the ends) between the per-onset median
    matched onsets of the other score onsets. NaN when no other match exists.
    """
    s_quarter = np.asarray(s_quarter, dtype=float)
    m = np.flatnonzero(s_partner >= 0)
    out = np.full(len(idx), np.nan)
    if len(m) == 0:
        return out
    mq = s_quarter[m]
    mt = np.asarray(p_onset, dtype=float)[s_partner[m]]
    uq, inv = np.unique(mq, return_inverse=True)
    groups: dict[int, list[tuple[int, float]]] = {}
    for k, i, t in zip(inv.tolist(), m.tolist(), mt.tolist(), strict=True):
        groups.setdefault(k, []).append((i, t))
    med = np.maximum.accumulate(np.array([np.median([t for _, t in groups[k]])
                                          for k in range(len(uq))]))  # fmt: skip
    for n, i in enumerate(idx):
        q = s_quarter[i]
        k = int(np.searchsorted(uq, q))
        if k < len(uq) and uq[k] == q:
            mates = [t for j, t in groups[k] if j != i]
            if mates:
                out[n] = float(np.median(mates))
                continue
            xp, fp = np.delete(uq, k), np.delete(med, k)
        else:
            xp, fp = uq, med
        if len(xp):
            out[n] = float(np.interp(q, xp, fp))
    return out


def reassign_same_pitch(
    s_quarter: np.ndarray,
    s_pitch: np.ndarray,
    p_onset: np.ndarray,
    p_pitch: np.ndarray,
    s_partner: np.ndarray,
    p_free: np.ndarray,
    s_frozen: np.ndarray | None = None,
    *,
    margin_sec: float = REASSIGN_MARGIN_SEC,
    window_sec: float = REASSIGN_WINDOW_SEC,
) -> list[tuple[int, int, int]]:
    """Swaps ``(score index, old performed index, new performed index)`` by the module rule.

    Args:
        s_quarter, s_pitch: score onsets (quarters) and MIDI pitches.
        p_onset, p_pitch: performed onsets (seconds) and MIDI pitches.
        s_partner: performed index matched to each score note (-1 if none); only same-pitch
            matches are considered.
        p_free: boolean mask of unmatched performed notes that may take a match (for example
            notes currently labelled extra; not interpolated or ornament notes).
        s_frozen: boolean mask of score notes never moved (grace and ornamented notes).
        margin_sec, window_sec: see :data:`REASSIGN_MARGIN_SEC`, :data:`REASSIGN_WINDOW_SEC`.

    The inputs are not modified; apply the swaps with the returned indices.
    """
    s_pitch = np.asarray(s_pitch, dtype=int)
    p_pitch = np.asarray(p_pitch, dtype=int)
    p_onset = np.asarray(p_onset, dtype=float)
    frozen = np.zeros(len(s_pitch), bool) if s_frozen is None else np.asarray(s_frozen, bool)
    free = np.flatnonzero(p_free)
    if len(free) == 0:
        return []
    matched = np.flatnonzero((s_partner >= 0) & ~frozen)
    matched = matched[p_pitch[s_partner[matched]] == s_pitch[matched]]
    free_pitches = set(p_pitch[free].tolist())
    cand_s = np.array([i for i in matched if int(s_pitch[i]) in free_pitches], dtype=int)
    if len(cand_s) == 0:
        return []
    exp = loo_expected_onsets(s_quarter, s_partner, p_onset, cand_s)
    options: list[tuple[float, int, int, int]] = []
    for i, e in zip(cand_s.tolist(), exp.tolist(), strict=True):
        if not np.isfinite(e):
            continue
        j = int(s_partner[i])
        d_old = abs(p_onset[j] - e)
        same = free[p_pitch[free] == s_pitch[i]]
        d_new = np.abs(p_onset[same] - e)
        ok = (d_new <= window_sec) & (d_old - d_new > margin_sec)
        for k in np.flatnonzero(ok):
            options.append((-(d_old - float(d_new[k])), i, j, int(same[k])))
    options.sort()
    used_s: set[int] = set()
    used_p: set[int] = set()
    swaps = []
    for _, i, j, jn in options:
        if i in used_s or jn in used_p or j in used_p:
            continue
        swaps.append((i, j, jn))
        used_s.add(i)
        used_p.update((j, jn))
    return swaps
