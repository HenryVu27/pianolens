"""Rach3 Hanon practice sessions split into takes of one exercise, with a note alignment (BL-16).

Each Rach3 Hanon file is one practice session: many minutes of playing, with repeats, stops
and passes through several exercises. This module turns a session into **takes**: complete
passes through one Part I exercise (Hanon, *The Virtuoso Pianist*, Nos. 1-20), each aligned
note by note to a score generated for that exercise.

Exercise scores (generated, not hand-made)
------------------------------------------
``scores/hanoncexercs.musicxml`` is the whole book in one part (1,433 measures). Part I is
measures 0-582 (0-based): 20 exercises, each restarting its printed measure numbers at 1, each
ending with a ``light-heavy`` repeat barline and a final one-chord bar. Part II (Nos. 21-43,
measures 583-1432) has no separators and is not split here. :func:`hanon_exercise_xml` cuts
one exercise out of the MusicXML text, copies the book's first ``<attributes>`` (divisions,
key, time, staves, clefs) into its first measure and removes the ``<repeat>`` elements, so the
exercise score is **one pass** (about 28 bars of sixteenths plus the final chord).

Segmentation and alignment (score-informed, exact pitch)
--------------------------------------------------------
Performed notes are grouped into **events** (onsets closer than ``chord_ms`` to the previous
note of the event); score notes into onsets. Each event is a pitch set. The similarity of a
score onset and a performed event is ``match`` when the sets are equal, ``partial`` when they
share a pitch and ``mismatch`` otherwise; skipping either side costs ``gap``.

:func:`fit_alignment` computes a *fitting* alignment (Sellers 1980; the score is aligned end to
end, the session is free at both ends): dynamic programming with rows = score onsets and
columns = session events, row recurrence vectorised with the running-maximum form of the
horizontal gap. Every column of the last row is the score of a complete pass ending there.
:func:`find_takes` picks ends greedily from the highest score down, traces each back, and
keeps it if its session span does not overlap a take already kept. The traceback gives the
event pairs; notes inside a paired event are matched by pitch. Everything unpaired inside the
span is an insertion (performed) or a deletion (score).

Hanon exercises are diatonic sequences: bar ``b+1`` is bar ``b`` a step higher, so a pitch-
exact match cannot slip by a bar the way a pitch-free or pitch-class matcher could.

QC fields per take (thresholds applied by the caller, see ``TakeQC``): ``event_match_frac``
(score onsets paired with an equal pitch set), ``note_match_frac``, ``insert_frac`` (performed
notes in the span not matched, per score note), ``max_gap_ratio`` (longest onset-to-onset gap
in the take divided by its median score-onset IOI: a stop), ``dur_sec``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from pianolens.data.types import ALIGNMENT_DTYPE, Alignment

N_PART1 = 20


@dataclass(frozen=True)
class TakeConfig:
    """Scoring and grouping parameters for :func:`find_takes`."""

    chord_ms: float = 40.0
    match: int = 2
    partial: int = 1
    mismatch: int = -2
    gap: int = 1
    min_score_frac: float = 0.6  # a candidate needs this share of the perfect score (2 x m)


@dataclass(frozen=True)
class TakeQC:
    """Acceptance rules for a take (BL-16; fixed before any take statistic was computed)."""

    min_event_match_frac: float = 0.90
    min_note_match_frac: float = 0.90
    max_insert_frac: float = 0.15
    max_gap_ratio: float = 8.0

    def ok(self, row: dict[str, Any] | pd.Series) -> bool:
        return bool(row["event_match_frac"] >= self.min_event_match_frac
                    and row["note_match_frac"] >= self.min_note_match_frac
                    and row["insert_frac"] <= self.max_insert_frac
                    and row["max_gap_ratio"] <= self.max_gap_ratio)  # fmt: skip


# --------------------------------------------------------------------------- exercise scores


def _measures(xml: str) -> tuple[str, list[str], str]:
    """Split the one-part book into (text before the first measure, measures, tail)."""
    start = xml.index("<measure ")
    end = xml.rindex("</measure>") + len("</measure>")
    body = xml[start:end]
    measures = re.findall(r"<measure .*?</measure>", body, re.S)
    return xml[:start], measures, xml[end:]


def part1_measure_ranges(xml: str) -> list[tuple[int, int]]:
    """0-based [first, last] measure index of each Part I exercise (Nos. 1-20).

    An exercise starts where the printed measure number restarts at 1 and ends at the measure
    before the next restart; the 21st restart opens Part II."""
    _, ms, _ = _measures(xml)
    starts = [i for i, m in enumerate(ms)
              if re.match(r'<measure [^>]*number="1"', m)]  # fmt: skip
    if len(starts) < N_PART1 + 1:
        raise ValueError(f"expected >= {N_PART1 + 1} measure-number restarts, got {len(starts)}")
    return [(starts[k], starts[k + 1] - 1) for k in range(N_PART1)]


def hanon_exercise_xml(book_xml: str, number: int) -> str:
    """Standalone MusicXML of Part I exercise ``number`` (1-20), one pass, no repeat signs."""
    if not 1 <= number <= N_PART1:
        raise ValueError("Part I exercises are Nos. 1-20")
    head, ms, tail = _measures(book_xml)
    a, b = part1_measure_ranges(book_xml)[number - 1]
    attrs = re.search(r"<attributes>.*?</attributes>", ms[0], re.S)
    if attrs is None:
        raise ValueError("first measure has no <attributes>")
    sel = [re.sub(r"<repeat [^>]*/>", "", m) for m in ms[a : b + 1]]
    first = sel[0]
    if re.search(r"<attributes>.*?</attributes>", first, re.S):
        first = re.sub(r"<attributes>.*?</attributes>", lambda _: attrs.group(0), first,
                       count=1, flags=re.S)  # fmt: skip
    else:
        first = re.sub(r"(<measure [^>]*>)", lambda mm: mm.group(1) + attrs.group(0), first,
                       count=1)  # fmt: skip
    sel[0] = first
    # drop page-level credits (they name the book, not this exercise)
    head = re.sub(r"<credit .*?</credit>", "", head, flags=re.S)
    return head + "\n".join(sel) + tail


# --------------------------------------------------------------------------- events


def _mask(pitches: np.ndarray) -> tuple[int, int]:
    lo = hi = 0
    for p in pitches.tolist():
        if p < 64:
            lo |= 1 << p
        else:
            hi |= 1 << (p - 64)
    return lo, hi


def perf_events(onset_sec: np.ndarray, pitch: np.ndarray, chord_ms: float) -> pd.DataFrame:
    """Group performed notes (any order) into events. Returns one row per event: ``t`` (first
    onset, s), ``lo`` / ``hi`` (pitch-set bitmasks), ``idx`` (note indices into the input)."""
    order = np.argsort(onset_sec, kind="stable")
    on = np.asarray(onset_sec, float)[order]
    starts = np.r_[0, np.flatnonzero(np.diff(on) * 1000.0 > chord_ms) + 1]
    ends = np.r_[starts[1:], len(on)]
    rows = []
    for s, e in zip(starts, ends, strict=True):
        idx = order[s:e]
        lo, hi = _mask(np.asarray(pitch)[idx])
        rows.append((float(on[s]), lo, hi, idx))
    return pd.DataFrame(rows, columns=["t", "lo", "hi", "idx"])


def score_events(onset_div: np.ndarray, pitch: np.ndarray) -> pd.DataFrame:
    """Group score notes by onset. Same columns as :func:`perf_events` (``t`` in divs)."""
    order = np.lexsort((pitch, onset_div))
    od = np.asarray(onset_div)[order]
    starts = np.r_[0, np.flatnonzero(np.diff(od) != 0) + 1]
    ends = np.r_[starts[1:], len(od)]
    rows = []
    for s, e in zip(starts, ends, strict=True):
        idx = order[s:e]
        lo, hi = _mask(np.asarray(pitch)[idx])
        rows.append((float(od[s]), lo, hi, idx))
    return pd.DataFrame(rows, columns=["t", "lo", "hi", "idx"])


def _u64(x: pd.Series) -> np.ndarray:
    return np.array([int(v) for v in x], dtype=np.uint64)


def similarity(sev: pd.DataFrame, pev: pd.DataFrame, cfg: TakeConfig) -> np.ndarray:
    """``m x n`` int32 similarity of score onsets (rows) and performed events (columns)."""
    slo, shi = _u64(sev["lo"])[:, None], _u64(sev["hi"])[:, None]
    plo, phi = _u64(pev["lo"])[None, :], _u64(pev["hi"])[None, :]
    eq = (slo == plo) & (shi == phi)
    ov = ((slo & plo) != 0) | ((shi & phi) != 0)
    out = np.full(eq.shape, cfg.mismatch, dtype=np.int32)
    out[ov] = cfg.partial
    out[eq] = cfg.match
    return out


# --------------------------------------------------------------------------- alignment


def fit_alignment(S: np.ndarray, gap: int) -> np.ndarray:
    """Fitting-alignment DP matrix ``H`` of shape ``(m + 1, n + 1)``: rows (score) aligned end
    to end, columns (session) free at both ends. ``H[m, j]`` is the best score of a complete
    pass ending at session event ``j - 1``."""
    m, n = S.shape
    H = np.empty((m + 1, n + 1), dtype=np.int64)
    H[0, :] = 0
    ar = np.arange(n + 1, dtype=np.int64) * gap
    for i in range(1, m + 1):
        T = np.empty(n + 1, dtype=np.int64)
        T[0] = -gap * i
        T[1:] = np.maximum(H[i - 1, :-1] + S[i - 1], H[i - 1, 1:] - gap)
        H[i] = np.maximum.accumulate(T + ar) - ar
    return H


def traceback(H: np.ndarray, S: np.ndarray, gap: int, j_end: int) -> list[tuple[int, int]]:
    """Pairs (score onset, session event) on the path ending at ``H[m, j_end]``; a -1 marks the
    unpaired side. Returns them in order."""
    i, j = H.shape[0] - 1, j_end
    out: list[tuple[int, int]] = []
    while i > 0:
        if j > 0 and H[i, j] == H[i - 1, j - 1] + S[i - 1, j - 1]:
            out.append((i - 1, j - 1))
            i, j = i - 1, j - 1
        elif H[i, j] == H[i - 1, j] - gap:
            out.append((i - 1, -1))
            i -= 1
        elif j > 0 and H[i, j] == H[i, j - 1] - gap:
            out.append((-1, j - 1))
            j -= 1
        else:  # pragma: no cover - the recurrence guarantees one branch
            raise RuntimeError("traceback failed")
    return out[::-1]


def find_takes(sev: pd.DataFrame, pev: pd.DataFrame, cfg: TakeConfig | None = None
               ) -> list[dict[str, Any]]:
    """Complete passes of the score in the session, non-overlapping, best first.

    Returns dicts with ``score`` (DP score), ``perfect`` (``match x m``), ``pairs`` (event
    pairs), ``ev0`` / ``ev1`` (first / last paired session event)."""
    cfg = cfg or TakeConfig()
    m = len(sev)
    if m == 0 or len(pev) == 0:
        return []
    S = similarity(sev, pev, cfg)
    H = fit_alignment(S, cfg.gap)
    last = H[m, 1:]
    thr = cfg.min_score_frac * cfg.match * m
    cand = np.flatnonzero(last >= thr)
    cand = cand[np.argsort(-last[cand], kind="stable")]
    taken = np.zeros(len(pev), dtype=bool)
    out: list[dict[str, Any]] = []
    for j in cand:
        if taken[j]:
            continue
        pairs = traceback(H, S, cfg.gap, int(j) + 1)
        evs = [e for s, e in pairs if s >= 0 and e >= 0]
        if not evs:
            continue
        e0, e1 = min(evs), max(evs)
        if taken[e0 : e1 + 1].any():
            continue
        taken[e0 : e1 + 1] = True
        out.append({"score": int(last[j]), "perfect": cfg.match * m, "pairs": pairs,
                    "ev0": int(e0), "ev1": int(e1)})  # fmt: skip
    return sorted(out, key=lambda d: d["ev0"])


def note_alignment(
    pairs: list[tuple[int, int]],
    sev: pd.DataFrame,
    pev: pd.DataFrame,
    score_notes: np.ndarray,
    perf_notes: np.ndarray,
    span: tuple[int, int],
) -> tuple[list[tuple[str, str, str]], dict[str, float]]:
    """Note-level (label, score_id, performance_id) rows for one take, plus counts.

    Inside a paired event, notes match by pitch (each performed note once). Performed notes
    of events in ``span`` (inclusive event range) that are not matched are insertions."""
    rows: list[tuple[str, str, str]] = []
    used_perf: set[int] = set()
    n_ev_eq = 0
    for s, e in pairs:
        if s < 0:
            continue
        sidx = list(sev.at[s, "idx"])
        if e < 0:
            rows += [("deletion", str(score_notes["id"][k]), "") for k in sidx]
            continue
        if sev.at[s, "lo"] == pev.at[e, "lo"] and sev.at[s, "hi"] == pev.at[e, "hi"]:
            n_ev_eq += 1
        pidx = [int(k) for k in pev.at[e, "idx"]]
        free = {k: int(perf_notes["pitch"][k]) for k in pidx}
        for k in sidx:
            p = int(score_notes["pitch"][k])
            hit = next((q for q, pp in free.items() if pp == p), None)
            if hit is None:
                rows.append(("deletion", str(score_notes["id"][k]), ""))
            else:
                del free[hit]
                used_perf.add(hit)
                rows.append(("match", str(score_notes["id"][k]), str(perf_notes["id"][hit])))
    for ev in range(span[0], span[1] + 1):
        for q in pev.at[ev, "idx"]:
            if int(q) not in used_perf:
                rows.append(("insertion", "", str(perf_notes["id"][int(q)])))
    n_score = len(score_notes)
    n_match = sum(r[0] == "match" for r in rows)
    n_ins = sum(r[0] == "insertion" for r in rows)
    return rows, {
        "n_score_notes": n_score, "n_match": n_match, "n_insertion": n_ins,
        "n_deletion": sum(r[0] == "deletion" for r in rows),
        "event_match_frac": n_ev_eq / max(len(sev), 1),
        "note_match_frac": n_match / max(n_score, 1),
        "insert_frac": n_ins / max(n_score, 1),
    }  # fmt: skip


def alignment_from_rows(rows: list[tuple[str, str, str]], score_id: str, performance_id: str
                        ) -> Alignment:
    return Alignment(np.array(rows, dtype=ALIGNMENT_DTYPE), score_id, performance_id,
                     ground_truth=False, source="bl16-fitting-dp")  # fmt: skip


def max_gap_ratio(score_t: np.ndarray, perf_t: np.ndarray) -> float:
    """Longest pause inside a take: over consecutive paired events (score onset in divs,
    performed onset in s), the largest seconds-per-div divided by the median. A steady pass
    is about 1-2; a stop of several beats is much larger."""
    st, pt_ = np.asarray(score_t, float), np.asarray(perf_t, float)
    ds, dp = np.diff(st), np.diff(pt_)
    ok = ds > 0
    if ok.sum() < 3:
        return float("nan")
    rate = dp[ok] / ds[ok]
    med = float(np.median(rate))
    return float(rate.max() / med) if med > 0 else float("nan")


def load_book(path: Path | str) -> str:
    return Path(path).read_text(encoding="utf-8")


# --------------------------------------------------------------------------- loading built takes

DEFAULT_TAKES_DIR = Path(__file__).resolve().parents[3] / "data" / "interim" / "rach3_hanon_takes"


class HanonTakes:
    """Takes built by ``scripts/build_rach3_hanon_takes.py``, as ``AlignedPerformance`` objects.

    ``takes`` is the index (``takes.parquet``). :meth:`aligned` returns one
    ``AlignedPerformance`` per take id: the exercise ``Score`` (with its partitura part, shared
    by all takes of that exercise), a ``Performance`` holding the take's notes (session times
    and note ids; provenance ``sensor``; no pedal) and the fitting-DP ``Alignment``."""

    def __init__(self, root: Path | str = DEFAULT_TAKES_DIR) -> None:
        self.root = Path(root)
        self.takes = pd.read_parquet(self.root / "takes.parquet")
        self._notes = pd.read_parquet(self.root / "take_notes.parquet")
        self._al = pd.read_parquet(self.root / "alignments.parquet")
        self._scores: dict[int, Any] = {}

    def score(self, exercise: int) -> Any:
        from pianolens.align import load_score_part
        from pianolens.data.types import PieceId, score_from_partitura

        if exercise not in self._scores:
            p = self.root / "scores" / f"hanon_{exercise:02d}.musicxml"
            self._scores[exercise] = score_from_partitura(
                load_score_part(p), score_id=f"rach3:hanon_{exercise:02d}",
                piece_id=PieceId(f"rach3:hanon_no{exercise:02d}"), source_path=p,
                meta={"exercise": exercise, "generated_from": "hanoncexercs.musicxml"},
                keep_part=True)  # fmt: skip
        return self._scores[exercise]

    def aligned(self, take_ids: list[str]) -> list[Any]:
        from pianolens.data.types import (
            PEDAL_DTYPE,
            AlignedPerformance,
            Performance,
            PerformerId,
            PieceId,
        )

        out = []
        meta = self.takes.set_index("take_id")
        for tid in take_ids:
            r = meta.loc[tid]
            n = self._notes[self._notes["take_id"] == tid].sort_values("onset_sec")
            na = np.zeros(len(n), dtype=[("onset_sec", "f8"), ("duration_sec", "f8"),
                                         ("pitch", "i4"), ("velocity", "i4"),
                                         ("id", f"U{max(1, n['id'].str.len().max())}")])
            for k in ("onset_sec", "duration_sec", "pitch", "velocity", "id"):
                na[k] = n[k].to_numpy()
            perf = Performance(
                performance_id=f"rach3:{tid}", piece_id=PieceId(f"rach3:hanon_no{r.exercise:02d}"),
                performer_id=PerformerId(f"rach3:{r.pianist}"), provenance="sensor", notes=na,
                pedal=np.zeros(0, dtype=PEDAL_DTYPE), dataset="rach3",
                meta={"level": r.level, "date": str(pd.Timestamp(r.date).date()),
                      "exercise": int(r.exercise), "session_file": r.session_file})  # fmt: skip
            a = self._al[self._al["take_id"] == tid]
            rows = list(zip(a["label"], a["score_id"], a["performance_id"], strict=True))
            sc = self.score(int(r.exercise))
            out.append(AlignedPerformance(perf, sc, alignment_from_rows(
                rows, sc.score_id, perf.performance_id)))  # fmt: skip
        return out
