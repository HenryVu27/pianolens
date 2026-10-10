"""Synthetic sessions with known takes for ``pianolens.data.session_takes``."""

from __future__ import annotations

import numpy as np
import pytest

from pianolens.data import session_takes as st


def _score(n_onsets: int, seed: int = 0) -> np.ndarray:
    """A score note array: one or two notes per onset, random pitches, 480 divs per onset."""
    rng = np.random.default_rng(seed)
    rows = []
    k = 0
    for i in range(n_onsets):
        ps = rng.choice(np.arange(40, 90), size=1 + (i % 3 == 0), replace=False)
        for p in ps:
            rows.append((i * 480, 480, i * 1.0, 1.0, i * 1.0, 1.0, int(p), 1, f"n{k}", False))
            k += 1
    na = np.zeros(len(rows), dtype=[("onset_div", "i8"), ("duration_div", "i8"),
                                    ("onset_beat", "f8"), ("duration_beat", "f8"),
                                    ("onset_quarter", "f8"), ("duration_quarter", "f8"),
                                    ("pitch", "i4"), ("voice", "i4"), ("id", "U16"),
                                    ("is_grace", "?")])  # fmt: skip
    for j, r in enumerate(rows):
        na[j] = r
    return na


def _play(score_na: np.ndarray, onsets: list[range], gap_sec: float = 3.0) -> np.ndarray:
    """Perform the given score-onset ranges one after another (0.25 s per onset)."""
    od = score_na["onset_div"]
    t, rows, k = 0.0, [], 0
    for rg in onsets:
        for i in rg:
            for j in np.flatnonzero(od == i * 480):
                rows.append((t + 0.002 * (k % 2), 0.2, int(score_na["pitch"][j]), 64, f"p{k}"))
                k += 1
            t += 0.25
        t += gap_sec
    dt = [("onset_sec", "f8"), ("duration_sec", "f8"), ("pitch", "i4"), ("velocity", "i4"),
          ("id", "U16")]
    pna = np.zeros(len(rows), dtype=dt)
    for j, r in enumerate(rows):
        pna[j] = r
    return pna


def test_local_alignment_finds_embedded_region():
    S = np.full((5, 9), -2, dtype=np.int32)
    for i in range(5):
        S[i, i + 3] = 2
    H = st.local_alignment(S, 1)
    assert H.max() == 10
    i, j = np.unravel_index(int(np.argmax(H)), H.shape)
    pairs = st.local_traceback(H, S, 1, i, j)
    assert pairs == [(k, k + 3) for k in range(5)]


def test_split_at_gaps_cuts_long_skips_only():
    path = [(0, 0), (1, 1), (-1, 2), (2, 3)] + [(-1, 4 + k) for k in range(8)] + [(3, 12)]
    pieces = st.split_at_gaps(path, max_run=6)
    assert len(pieces) == 2
    assert pieces[0] == [(0, 0), (1, 1), (-1, 2), (2, 3)]
    assert pieces[1] == [(3, 12)]


@pytest.mark.parametrize("gap_sec", [3.0, 0.3])
def test_fragments_and_restart_become_separate_takes(gap_sec):
    sna = _score(120)
    plan = [range(10, 30), range(10, 60), range(80, 110)]  # fragment, restart, later passage
    pna = _play(sna, plan, gap_sec=gap_sec)
    cfg = st.LocalTakeConfig()
    sev = st.score_events(sna["onset_div"], sna["pitch"])
    pev = st.perf_events(pna["onset_sec"], pna["pitch"], cfg.chord_ms)
    takes = st.find_local_takes({"s": sev}, pev, cfg)
    spans = [(t["on0"], t["on1"]) for t in takes]
    assert spans == [(10, 29), (10, 59), (80, 109)]
    for t in takes:
        m, qc = st.match_take(t, sev, pev, sna, pna)
        assert qc["dice"] == 1.0 and qc["consensus_frac"] == 1.0
        assert (sna["pitch"][m["score_idx"]] == pna["pitch"][m["perf_idx"]]).all()


def test_wrong_score_gives_no_take():
    sna = _score(120, seed=1)
    other = _score(120, seed=2)
    pna = _play(sna, [range(0, 100)])
    cfg = st.LocalTakeConfig()
    sev = st.score_events(other["onset_div"], other["pitch"])
    pev = st.perf_events(pna["onset_sec"], pna["pitch"], cfg.chord_ms)
    assert st.find_local_takes({"other": sev}, pev, cfg) == []


def test_candidate_scores_compete():
    a, b = _score(80, seed=3), _score(80, seed=4)
    pna = _play(b, [range(5, 70)])
    cfg = st.LocalTakeConfig()
    pev = st.perf_events(pna["onset_sec"], pna["pitch"], cfg.chord_ms)
    cands = {"a": st.score_events(a["onset_div"], a["pitch"]),
             "b": st.score_events(b["onset_div"], b["pitch"])}
    takes = st.find_local_takes(cands, pev, cfg)
    assert [t["score"] for t in takes] == ["b"]
    assert (takes[0]["on0"], takes[0]["on1"]) == (5, 69)
