"""Known-answer tests for pianolens.features.cadence (F-05c)."""

from __future__ import annotations

import numpy as np
import partitura as pt

from pianolens.data import types
from pianolens.features.cadence import (
    CadenceConfig,
    cadence_candidates,
    cadence_phrase_ends,
    pick_ends,
    starts_from_ends,
)
from pianolens.features.score_basis import BasisConfig, score_basis

Q = 4
_SPELL = {0: ("C", None), 2: ("D", None), 4: ("E", None), 5: ("F", None), 7: ("G", None),
          9: ("A", None), 11: ("B", None)}  # fmt: skip
# chord = (bass, upper voices); C major
I_, IV, II, V, VI = ((48, (64, 67, 72)), (53, (65, 69, 72)), (50, (65, 69, 74)),
                     (43, (62, 67, 71)), (45, (64, 69, 72)))  # fmt: skip


def chord_score(bars):
    """``bars``: list of bars, each a list of (chord, duration in quarters); 4/4, C major."""
    part = pt.score.Part("P0", "piano", quarter_duration=Q)
    part.add(pt.score.TimeSignature(4, 4), 0)
    part.add(pt.score.KeySignature(0, "major"), 0)
    t, k = 0.0, 0
    for bar in bars:
        for (bass, upper), d in bar:
            for p in (bass, *upper):
                step, alter = _SPELL[p % 12]
                n = pt.score.Note(step=step, octave=p // 12 - 1, alter=alter, id=f"n{k}", voice=1)
                part.add(n, start=int(round(t * Q)), end=int(round((t + d) * Q)))
                k += 1
            t += d
    pt.score.add_measures(part)
    return types.score_from_partitura(part, score_id="synth:c", piece_id=types.PieceId("c"),
                                      keep_part=True)


def phrase(cadence="PAC"):
    """A 4-bar phrase of quarter chords ending with a whole-note arrival in bar 4:
    I on the downbeat after V (PAC), or V after IV (HC)."""
    body = [[(I_, 1), (IV, 1), (II, 1), (V, 1)], [(VI, 1), (IV, 1), (I_, 1), (II, 1)]]
    if cadence == "PAC":
        return [*body, [(IV, 1), (II, 1), (I_, 1), (V, 1)], [(I_, 4)]]
    return [*body, [(I_, 1), (VI, 1), (II, 1), (IV, 1)], [(V, 4)]]


def test_cues_at_a_v_i_arrival():
    s = chord_score([*phrase("PAC"), *phrase("PAC")])
    cand, meta = cadence_candidates(s)
    assert meta["beats_per_bar"] == 4.0 and meta["key_fifths"] == 0
    c = cand.set_index("beat")
    a = c.loc[12.0]  # bar 4 downbeat: I after V
    assert a["bass_fifth_down"] == 1 and a["root_triad"] == 1 and a["major_triad"] == 1
    assert a["leading_tone_before"] == 1 and a["dominant_before"] == 1
    assert a["is_downbeat"] == 1 and a["harmony_change"] == 1 and a["bass_tonic"] == 1
    assert a["melody_long"] > 1.5  # a whole note after quarters
    assert a["stable_after"] == 1
    m = c.loc[2.0]  # ii after IV (F -> D bass: down a third) on beat 3
    assert m["bass_fifth_down"] == 0 and m["is_downbeat"] == 0 and m["bass_same"] == 0
    assert c.loc[11.0, "bass_dominant"] == 1  # V on beat 4 of bar 3
    assert a["prob"] > m["prob"]


def test_detector_finds_authentic_and_half_cadences():
    bars = [*phrase("PAC"), *phrase("HC"), *phrase("PAC"), *phrase("PAC")]
    s = chord_score(bars)
    res = cadence_phrase_ends(s)
    ends = res.end_beats
    for e in (12.0, 28.0, 44.0, 60.0):
        assert any(abs(x - e) < 1e-6 for x in ends), (e, ends)
    assert len(ends) <= 6
    # starts: the first onset, and the onset after each arrival
    assert res.starts[0] == 0.0 and 16.0 in res.starts and 32.0 in res.starts
    assert res.bars["is_end"].sum() == len(res.ends)
    assert set(res.candidates.columns) >= {"prob", "bass_fifth_down", "melody_long"}


def test_pick_ends_respects_gap_and_threshold():
    import pandas as pd

    c = pd.DataFrame({"beat": [0.0, 4.0, 5.0, 12.0, 16.0], "prob": [0.9, 0.8, 0.95, 0.4, 0.7],
                      "measure_idx": [0, 1, 1, 3, 4]})
    # 4.0 lies within a bar of the stronger 5.0; 12.0 is below the threshold
    got = pick_ends(c, bpb=4.0, threshold=0.5, min_gap_bars=1.0)["beat"].tolist()
    assert got == [0.0, 5.0, 16.0]
    got = pick_ends(c, bpb=4.0, threshold=0.5, min_gap_bars=3.0)["beat"].tolist()
    assert got == [5.0]


def test_starts_from_ends_rules():
    onsets = np.array([0.0, 1.0, 2.0, 4.0, 6.0, 7.0, 8.0])
    max_end = np.array([1.0, 2.0, 3.0, 5.0, 7.0, 8.0, 9.0])
    # end at 4 (held to 5), rest until 6: the gap rule starts at 6
    assert starts_from_ends(onsets, max_end, [4.0], 4.0, "gap", 1.0) == [0.0, 6.0]
    assert starts_from_ends(onsets, max_end, [4.0], 4.0, "next", 1.0) == [0.0, 6.0]
    assert starts_from_ends(onsets, max_end, [2.0], 4.0, "next", 1.0) == [0.0, 4.0]
    assert starts_from_ends(onsets, max_end, [2.0], 4.0, "elision", 1.0) == [0.0, 2.0]
    # gap rule prefers the onset after the silence (3 -> 4) over the next onset
    assert starts_from_ends(onsets, max_end, [1.0], 4.0, "gap", 1.0) == [0.0, 4.0]


def test_basis_phrase_source_option_is_off_by_default():
    s = chord_score([*phrase("PAC"), *phrase("PAC")])
    assert BasisConfig().phrase_source == "proxy"
    b = score_basis(s, config=BasisConfig(phrase_source="cadence", phrase_detail=True))
    assert set(b.phrases["source"]) <= {"cadence", "split"}
    assert 16.0 in b.phrases["start_beat"].tolist()
    assert "pre_end_k1" in b.groups["phrase_detail"]
    assert CadenceConfig().threshold > 0
