"""Practice sessions split into takes of a score: local alignment, then a parangonar note match.

A practice session (PianoVAM, Rach3) is one long MIDI file with fragments, restarts, repeated
passages and pauses. ``pianolens.align.align`` (parangonar DualDTW) aligns a score end to end
with a performance end to end, so it cannot be given a whole session. This module finds the
**takes**: maximal stretches of the session that play one contiguous region of a score, in
score order, and then runs parangonar on each take against that region only.

Step 1, locate (:func:`find_local_takes`)
-----------------------------------------
Score notes are grouped into onsets and performed notes into events (``chord_ms``), each a
pitch set; the similarity of a score onset and a performed event is ``match`` (equal sets),
``partial`` (they share a pitch) or ``mismatch`` (``pianolens.data.rach3_takes.similarity``).
A *local* alignment (Smith and Waterman 1981; both sequences free at both ends) gives the best
pair of a score region and a session region. The session is then cut at that region and the
search repeats on the parts to its left and right (recursive, so takes never overlap in the
session; they may overlap in the score, as restarts and repeats do). Several candidate scores
(movements of one work) compete for each region; the higher DP score wins. A take must reach
``min_score`` DP points.

Exact pitch sets make a bar-level slip unlikely except in sequences, and a jump back (restart,
repeat) ends a take, because a local path is monotone in both sequences.

Step 2, match notes (:func:`match_take`)
----------------------------------------
The take's performed notes are aligned with ``pianolens.align.align_note_arrays`` (parangonar
``DualDTWNoteMatcher``) to the score notes whose onsets lie between the first and the last
score onset the local path paired. Ornament processing is off, so a match always has equal
pitch. QC per take: the Dice ratio of the parangonar match inside the crop, and the agreement
of parangonar's matches with the local path (the share of parangonar-matched notes whose
performed event the local path paired with the matched note's score onset).

Nothing here reads hand labels or any other annotation of the performance.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from pianolens.data.rach3_takes import TakeConfig, perf_events, score_events, similarity

__all__ = [
    "LocalTakeConfig",
    "find_local_takes",
    "local_alignment",
    "local_traceback",
    "match_take",
    "path_score",
    "perf_events",
    "score_events",
    "split_at_gaps",
]


@dataclass(frozen=True)
class LocalTakeConfig:
    """Parameters of :func:`find_local_takes` (similarity values as in BL-16's ``TakeConfig``).

    ``min_score``: DP points a take needs (``match`` = 2 per exactly matched onset), so the
    default asks for the equivalent of about 15 exact onsets net of gaps and mismatches.
    ``max_gap_run``: a local path is cut where more than this many consecutive steps skip
    one side (a restart, a jump, a skipped passage); each piece is a take of its own if it
    still reaches ``min_score``, and the skipped session events are searched again.
    """

    chord_ms: float = 50.0
    match: int = 2
    partial: int = 1
    mismatch: int = -2
    gap: int = 1
    min_score: int = 30
    max_gap_run: int = 6

    def take_config(self) -> TakeConfig:
        return TakeConfig(chord_ms=self.chord_ms, match=self.match, partial=self.partial,
                          mismatch=self.mismatch, gap=self.gap)  # fmt: skip


def local_alignment(S: np.ndarray, gap: int) -> np.ndarray:
    """Smith-Waterman matrix ``H`` of shape ``(m + 1, n + 1)`` (int32) for similarity ``S``
    (``m`` score onsets x ``n`` performed events) and a linear gap cost ``gap``.

    ``H[i, j] = max(0, H[i-1, j-1] + S[i-1, j-1], H[i-1, j] - gap, H[i, j-1] - gap)``; the
    horizontal term is computed for a whole row at once with the running-maximum identity
    ``max_k (T[k] - (j - k) gap) = max_k (T[k] + k gap) - j gap``."""
    m, n = S.shape
    H = np.zeros((m + 1, n + 1), dtype=np.int32)
    ar = np.arange(n + 1, dtype=np.int32) * np.int32(gap)
    T = np.zeros(n + 1, dtype=np.int32)
    for i in range(1, m + 1):
        T[0] = 0
        np.maximum(H[i - 1, :-1] + S[i - 1], H[i - 1, 1:] - gap, out=T[1:])
        np.maximum(T, 0, out=T)
        H[i] = np.maximum.accumulate(T + ar) - ar
    return H


def local_traceback(H: np.ndarray, S: np.ndarray, gap: int, i_end: int, j_end: int
                    ) -> list[tuple[int, int]]:
    """Pairs ``(score onset, performed event)`` of the local path ending at ``H[i_end, j_end]``,
    in order; ``-1`` marks the unpaired side of a gap. Starts and ends on a paired step."""
    i, j = i_end, j_end
    out: list[tuple[int, int]] = []
    while i > 0 and j > 0 and H[i, j] > 0:
        if H[i, j] == H[i - 1, j - 1] + S[i - 1, j - 1]:
            out.append((i - 1, j - 1))
            i, j = i - 1, j - 1
        elif H[i, j] == H[i - 1, j] - gap:
            out.append((i - 1, -1))
            i -= 1
        elif H[i, j] == H[i, j - 1] - gap:
            out.append((-1, j - 1))
            j -= 1
        else:  # pragma: no cover - the recurrence guarantees one branch
            raise RuntimeError("traceback failed")
    out = out[::-1]
    while out and (out[0][0] < 0 or out[0][1] < 0):
        out.pop(0)
    return out


def split_at_gaps(pairs: list[tuple[int, int]], max_run: int) -> list[list[tuple[int, int]]]:
    """Cut a path where more than ``max_run`` consecutive steps leave one side unpaired. Each
    piece starts and ends on a paired step."""
    pieces: list[list[tuple[int, int]]] = []
    cur: list[tuple[int, int]] = []
    run: list[tuple[int, int]] = []
    for s, e in pairs:
        if s >= 0 and e >= 0:
            if len(run) > max_run and cur:
                pieces.append(cur)
                cur = []
            elif cur:
                cur.extend(run)
            run = []
            cur.append((s, e))
        else:
            run.append((s, e))
    if cur:
        pieces.append(cur)
    return pieces


def path_score(pairs: list[tuple[int, int]], S: np.ndarray, gap: int) -> int:
    """DP points of a path: similarity of paired steps minus ``gap`` per unpaired step."""
    return int(sum(int(S[s, e]) if s >= 0 and e >= 0 else -gap for s, e in pairs))


def _best_local(S: np.ndarray, gap: int) -> tuple[int, list[tuple[int, int]]]:
    if S.size == 0:
        return 0, []
    H = local_alignment(S, gap)
    flat = int(np.argmax(H))
    i, j = divmod(flat, H.shape[1])
    return int(H[i, j]), local_traceback(H, S, gap, i, j)


def find_local_takes(
    scores: dict[str, pd.DataFrame], pev: pd.DataFrame, cfg: LocalTakeConfig | None = None
) -> list[dict[str, Any]]:
    """Non-overlapping takes of any of ``scores`` (name -> :func:`score_events`) in the session
    events ``pev`` (:func:`perf_events`), in session order.

    Each take: ``score`` (candidate name), ``dp`` (local DP points), ``pairs`` (score onset,
    session event; session indices are global), ``ev0`` / ``ev1`` (first / last paired event),
    ``on0`` / ``on1`` (first / last paired score onset), ``n_pairs`` (paired steps) and
    ``n_exact`` (paired steps with equal pitch sets)."""
    cfg = cfg or LocalTakeConfig()
    tc = cfg.take_config()
    sims = {k: similarity(sev, pev, tc).astype(np.int32) for k, sev in scores.items()}
    out: list[dict[str, Any]] = []
    stack = [(0, len(pev))]
    while stack:
        a, b = stack.pop()
        if b - a < 2:
            continue
        best: tuple[int, str, list[tuple[int, int]]] | None = None
        for k, S in sims.items():
            dp, pairs = _best_local(S[:, a:b], cfg.gap)
            if best is None or dp > best[0]:
                best = (dp, k, pairs)
        if best is None or best[0] < cfg.min_score or not best[2]:
            continue
        _, k, pairs = best
        pairs = [(s, e + a if e >= 0 else -1) for s, e in pairs]
        sev, S = scores[k], sims[k]
        used: list[tuple[int, int]] = []
        for piece in split_at_gaps(pairs, cfg.max_gap_run):
            both = [(s, e) for s, e in piece if s >= 0 and e >= 0]
            e0, e1 = both[0][1], both[-1][1]
            dp = path_score(piece, S, cfg.gap)
            if dp < cfg.min_score:
                continue
            n_exact = sum(int(sev.at[s, "lo"] == pev.at[e, "lo"]
                              and sev.at[s, "hi"] == pev.at[e, "hi"]) for s, e in both)  # fmt: skip
            out.append({"score": k, "dp": dp, "pairs": piece, "ev0": e0, "ev1": e1,
                        "on0": both[0][0], "on1": both[-1][0], "n_pairs": len(both),
                        "n_exact": n_exact})  # fmt: skip
            used.append((e0, e1))
        if not used:
            # the best path broke into pieces that are all too short: search its parts again
            # without it, so the loop always shrinks the column range
            both = [e for s, e in pairs if s >= 0 and e >= 0]
            mid = (both[0] + both[-1]) // 2
            stack += [(a, mid), (mid + 1, b)] if b - a > 2 else []
            continue
        used.sort()
        edges = [a] + [x for u in used for x in (u[0], u[1] + 1)] + [b]
        for lo, hi in zip(edges[::2], edges[1::2], strict=True):
            stack.append((lo, hi))
    return sorted(out, key=lambda d: d["ev0"])


def match_take(
    take: dict[str, Any],
    sev: pd.DataFrame,
    pev: pd.DataFrame,
    score_na: np.ndarray,
    perf_na: np.ndarray,
) -> tuple[pd.DataFrame, dict[str, float]]:
    """Parangonar note match of one take against its score region.

    ``score_na``: the folded score's note array (``part.note_array(include_grace_notes=True)``,
    the array ``sev`` was built from, same row order). ``perf_na``: the session's performance
    note array (``onset_sec``, ``duration_sec``, ``pitch``, ``velocity``, ``id``), the array
    ``pev`` was built from. Returns the matched pairs (``score_idx``, ``perf_idx`` row indices
    into those arrays, ``consensus``: the local path paired the performed note's event with
    the score note's onset) and QC values: ``n_score_crop``, ``n_perf_take``, ``n_match``,
    ``dice``, ``consensus_frac``."""
    from pianolens.align import align_note_arrays  # read-only use of the shared aligner

    t0, t1 = float(sev.at[take["on0"], "t"]), float(sev.at[take["on1"], "t"])
    od = score_na["onset_div"].astype(float)
    s_idx = np.flatnonzero((od >= t0) & (od <= t1))
    p_idx = np.concatenate([np.asarray(pev.at[e, "idx"], dtype=np.int64)
                            for e in range(take["ev0"], take["ev1"] + 1)])  # fmt: skip
    p_idx = np.sort(p_idx)
    qc = {"n_score_crop": len(s_idx), "n_perf_take": len(p_idx), "n_match": 0, "dice": 0.0,
          "consensus_frac": float("nan")}  # fmt: skip
    empty = pd.DataFrame({"score_idx": pd.Series(dtype=int), "perf_idx": pd.Series(dtype=int),
                          "consensus": pd.Series(dtype=bool)})  # fmt: skip
    if len(s_idx) == 0 or len(p_idx) == 0:
        return empty, qc
    sna, pna = score_na[s_idx], perf_na[p_idx]
    al = align_note_arrays(sna, pna, score_part=None, process_ornaments=False)
    s_pos = {str(x): i for i, x in enumerate(sna["id"])}
    p_pos = {str(x): i for i, x in enumerate(pna["id"])}
    rows = [(s_idx[s_pos[a["score_id"]]], p_idx[p_pos[a["performance_id"]]])
            for a in al if a["label"] == "match"]  # fmt: skip
    rows = [(s, p) for s, p in rows if int(score_na["pitch"][s]) == int(perf_na["pitch"][p])]
    if not rows:
        return empty, qc
    df = pd.DataFrame(rows, columns=["score_idx", "perf_idx"])
    # local-path consensus: performed note's event paired with the score note's onset
    s_onset_of = np.empty(len(score_na), dtype=np.int64)
    for k, idx in enumerate(sev["idx"]):
        s_onset_of[np.asarray(idx, dtype=np.int64)] = k
    p_event_of = np.full(len(perf_na), -1, dtype=np.int64)
    for e in range(take["ev0"], take["ev1"] + 1):
        p_event_of[np.asarray(pev.at[e, "idx"], dtype=np.int64)] = e
    paired = {(s, e) for s, e in take["pairs"] if s >= 0 and e >= 0}
    df["consensus"] = [(int(s_onset_of[s]), int(p_event_of[p])) in paired
                       for s, p in zip(df["score_idx"], df["perf_idx"], strict=True)]  # fmt: skip
    qc.update(n_match=len(df), dice=2 * len(df) / (len(s_idx) + len(p_idx)),
              consensus_frac=float(df["consensus"].mean()))  # fmt: skip
    return df, qc
