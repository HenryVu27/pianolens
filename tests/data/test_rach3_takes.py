"""BL-16: Rach3 Hanon take splitting on synthetic data (no Rach3 files needed)."""

from __future__ import annotations

import numpy as np
import pytest

from pianolens.data import rach3_takes as rt


def _book(n_ex: int = 21, bars: int = 2) -> str:
    head = ('<?xml version="1.0"?><score-partwise><part-list><score-part id="P1">'
            '<part-name>Piano</part-name></score-part></part-list><part id="P1">')  # fmt: skip
    ms = []
    for e in range(n_ex):
        for b in range(1, bars + 1):
            full = ("<attributes><divisions>4</divisions><key><fifths>0</fifths></key>"
                    "<time><beats>2</beats><beat-type>4</beat-type></time></attributes>")
            short = "<attributes><divisions>4</divisions></attributes>"
            attrs = full if (e == 0 and b == 1) else short if b == 1 else ""
            rep = '<barline><repeat direction="backward"/></barline>' if b == bars else ""
            ms.append(f'<measure number="{b}">{attrs}<note><pitch><step>C</step>'
                      f"<octave>{e % 5 + 2}</octave></pitch><duration>8</duration></note>"
                      f"{rep}</measure>")  # fmt: skip
    return head + "".join(ms) + "</part></score-partwise>"


def test_exercise_xml_cuts_one_exercise():
    book = _book()
    ranges = rt.part1_measure_ranges(book)
    assert len(ranges) == 20 and ranges[0] == (0, 1) and ranges[1] == (2, 3)
    x = rt.hanon_exercise_xml(book, 2)
    assert x.count("<measure ") == 2
    assert "<repeat" not in x
    assert "<fifths>0</fifths>" in x  # the book's first attributes are copied in
    assert "<octave>3</octave>" in x and "<octave>2</octave>" not in x
    with pytest.raises(ValueError):
        rt.hanon_exercise_xml(book, 21)


def _score(m: int = 40):
    """Hanon-like: two hands an octave apart, a diatonic-ish rising line."""
    steps = np.cumsum(np.tile([2, 2, 1, 2, -3, -2, 2, 1], m // 8 + 1))[:m] + 48
    onset_div = np.repeat(np.arange(m), 2)
    pitch = np.column_stack([steps, steps + 12]).ravel()
    ids = np.array([f"s{k}" for k in range(2 * m)])
    na = np.zeros(2 * m, dtype=[("onset_div", "i4"), ("pitch", "i4"), ("id", "U8")])
    na["onset_div"], na["pitch"], na["id"] = onset_div, pitch, ids
    return na


def _perf(score_na, passes, rng, ioi=0.12, noise_len=30, wrong=()):
    """Noise, then each pass of the score (with optional wrong-note positions), then noise."""
    on, pi = [], []
    t = 0.0
    def noise():
        nonlocal t
        for _ in range(noise_len):
            on.append(t)
            pi.append(int(rng.integers(90, 100)))
            t += ioi
    noise()
    for _ in range(passes):
        for d in np.unique(score_na["onset_div"]):
            for k, p in enumerate(score_na["pitch"][score_na["onset_div"] == d]):
                on.append(t + 0.01 * k)
                pi.append(int(p) + (1 if d in wrong and k == 0 else 0))
            t += ioi
        t += 2.0
        noise()
    na = np.zeros(len(on), dtype=[("onset_sec", "f8"), ("pitch", "i4"), ("id", "U8")])
    na["onset_sec"], na["pitch"] = on, pi
    na["id"] = [f"p{k}" for k in range(len(on))]
    return na


def test_find_takes_recovers_passes_and_alignment():
    rng = np.random.default_rng(0)
    sna = _score()
    pna = _perf(sna, passes=2, rng=rng, wrong=(5,))
    sev = rt.score_events(sna["onset_div"], sna["pitch"])
    pev = rt.perf_events(pna["onset_sec"], pna["pitch"], 40.0)
    takes = rt.find_takes(sev, pev)
    assert len(takes) == 2
    assert takes[0]["ev1"] < takes[1]["ev0"]
    for t in takes:
        rows, c = rt.note_alignment(t["pairs"], sev, pev, sna, pna, (t["ev0"], t["ev1"]))
        # one wrong note: 79 of 80 score notes match, one deletion, one insertion
        assert c["n_match"] == 79 and c["n_deletion"] == 1 and c["n_insertion"] == 1
        assert c["event_match_frac"] == pytest.approx(39 / 40)
        al = rt.alignment_from_rows(rows, "sc", "pf")
        assert len(al.matches) == 79
        paired = [(s, e) for s, e in t["pairs"] if s >= 0 and e >= 0]
        g = rt.max_gap_ratio(sev["t"].to_numpy()[[s for s, _ in paired]],
                             pev["t"].to_numpy()[[e for _, e in paired]])  # fmt: skip
        assert g == pytest.approx(1.0, abs=0.01)


def test_partial_pass_scores_low_and_stop_raises_gap():
    rng = np.random.default_rng(1)
    sna = _score()
    half = sna[sna["onset_div"] < 20]
    pna = _perf(half, passes=1, rng=rng)
    sev = rt.score_events(sna["onset_div"], sna["pitch"])
    pev = rt.perf_events(pna["onset_sec"], pna["pitch"], 40.0)
    assert rt.find_takes(sev, pev) == []  # half a pass never reaches 0.6 of the perfect score
    st = np.arange(10.0)
    pt_ = st * 0.1
    pt_[6:] += 1.0  # a one-second stop between onsets 5 and 6
    assert rt.max_gap_ratio(st, pt_) == pytest.approx(11.0)


def test_fit_alignment_known_small_case():
    S = np.array([[2, -2, -2], [-2, 2, -2]], dtype=np.int32)
    H = rt.fit_alignment(S, gap=1)
    assert H[2, 2] == 4  # both score rows matched to columns 0 and 1
    assert rt.traceback(H, S, 1, 2) == [(0, 0), (1, 1)]


def test_qc_rule():
    qc = rt.TakeQC()
    good = {"event_match_frac": 0.95, "note_match_frac": 0.97, "insert_frac": 0.05,
            "max_gap_ratio": 2.0}  # fmt: skip
    assert qc.ok(good)
    assert not qc.ok({**good, "max_gap_ratio": 20.0})
    assert not qc.ok({**good, "event_match_frac": 0.8})
