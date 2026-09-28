"""Synthetic known-answer tests for pianolens.align."""

from __future__ import annotations

import numpy as np
import partitura as pt
import pytest

from pianolens.align import (
    align,
    align_performance,
    evaluate_alignment,
    is_unfolded,
    match_ratio,
    repeat_variants,
    unfold_variant,
)

_SPELL = {
    0: ("C", None), 1: ("C", 1), 2: ("D", None), 3: ("D", 1), 4: ("E", None), 5: ("F", None),
    6: ("F", 1), 7: ("G", None), 8: ("G", 1), 9: ("A", None), 10: ("A", 1), 11: ("B", None),
}  # fmt: skip

SCALE = [60, 62, 64, 65, 67, 69, 71, 72, 71, 69, 67, 65, 64, 62, 60, 55]
PERF_DTYPE = [
    ("onset_sec", "f8"),
    ("duration_sec", "f8"),
    ("pitch", "i4"),
    ("velocity", "i4"),
    ("id", "U32"),
]


def make_part(events, repeat=None, quarter=4):
    """events: list of (onset_quarter, [pitches]); every note lasts one quarter.

    Note ids are n0, n1, ... in event order. ``repeat=(start_q, end_q)`` adds a repeat.
    """
    part = pt.score.Part("P0", "piano", quarter_duration=quarter)
    part.add(pt.score.TimeSignature(4, 4), 0)
    k = 0
    for onset, pitches in events:
        for p in pitches:
            step, alter = _SPELL[p % 12]
            note = pt.score.Note(step=step, octave=p // 12 - 1, alter=alter, id=f"n{k}", voice=1)
            part.add(note, start=int(onset * quarter), end=int((onset + 1) * quarter))
            k += 1
    if repeat:
        part.add(pt.score.Repeat(), repeat[0] * quarter, repeat[1] * quarter)
    pt.score.add_measures(part)
    return part


def melody(pitches):
    return [(i, [p]) for i, p in enumerate(pitches)]


def make_perf(onsets, pitches):
    na = np.zeros(len(pitches), dtype=PERF_DTYPE)
    na["onset_sec"] = onsets
    na["duration_sec"] = 0.4
    na["pitch"] = pitches
    na["velocity"] = 64
    na["id"] = [f"p{i}" for i in range(len(pitches))]
    return na


def by_label(alignment, label):
    return [a for a in alignment if a["label"] == label]


def test_deadpan_melody_matches_every_note():
    part = make_part(melody(SCALE))
    perf = make_perf(np.arange(len(SCALE)) * 0.5, SCALE)
    res = align(part, perf)
    assert res.n_match == len(SCALE)
    assert res.n_insertion == res.n_deletion == 0
    assert sorted(res.match_pairs()) == sorted((f"n{i}-1", f"p{i}") for i in range(len(SCALE)))
    assert res.variant == "A" and res.n_variants == 1
    assert res.candidates == {"A": 1.0}


def test_one_deleted_and_one_inserted_note():
    """Skip score note n5 (A4) and add an extra F#6 between notes 9 and 10."""
    part = make_part(melody(SCALE))
    played = [(i * 0.5, p) for i, p in enumerate(SCALE) if i != 5]
    played.append((9.5 * 0.5, 90))
    played.sort()
    onsets, pitches = zip(*played, strict=True)
    perf = make_perf(onsets, pitches)
    extra_id = perf["id"][list(pitches).index(90)]

    res = align(part, perf)
    assert [a["score_id"] for a in by_label(res.alignment, "deletion")] == ["n5-1"]
    assert [a["performance_id"] for a in by_label(res.alignment, "insertion")] == [extra_id]
    assert res.n_match == len(SCALE) - 1

    pid_of = {p: i for i, p in enumerate(perf["id"])}
    for s, p in res.match_pairs():
        assert perf["pitch"][pid_of[p]] == SCALE[int(s[1:].split("-")[0])]


def test_rubato_and_chords():
    """Chords of three notes with a slowing tempo and 15 ms chord spread still match fully."""
    chords = [[48, 60, 64], [50, 62, 65], [52, 64, 67], [53, 65, 69], [55, 67, 71], [48, 60, 72]]
    part = make_part([(2 * i, c) for i, c in enumerate(chords)])
    onsets, pitches = [], []
    t = 0.0
    for i, c in enumerate(chords):
        for j, p in enumerate(c):
            onsets.append(t + 0.015 * j)
            pitches.append(p)
        t += 0.8 * (1.15**i)  # ritardando
    perf = make_perf(onsets, pitches)
    res = align(part, perf)
    assert res.n_match == len(pitches)
    pid_pitch = dict(zip(perf["id"], perf["pitch"], strict=True))
    sid_pitch = dict(zip(res.score_note_array["id"], res.score_note_array["pitch"], strict=True))
    assert all(pid_pitch[p] == sid_pitch[s] for s, p in res.match_pairs())


def test_wrong_pitch_is_a_deletion_plus_an_insertion():
    part = make_part(melody(SCALE))
    played = list(SCALE)
    played[7] = 73  # C#5 instead of C5
    perf = make_perf(np.arange(len(SCALE)) * 0.5, played)
    res = align(part, perf)
    assert [a["score_id"] for a in by_label(res.alignment, "deletion")] == ["n7-1"]
    assert [a["performance_id"] for a in by_label(res.alignment, "insertion")] == ["p7"]


@pytest.mark.parametrize("times, expected", [(2, "AA"), (1, "A")])
def test_repeat_variant_follows_the_performance(times, expected):
    phrase = SCALE[:8]
    part = make_part(melody(phrase), repeat=(0, 8))
    assert sorted(repeat_variants(part)) == [("A", 8), ("AA", 16)]
    unfold_variant(part, "AA")
    # partitura's get_paths is stateful; repeated calls must still see every path
    assert sorted(repeat_variants(part)) == [("A", 8), ("AA", 16)]
    perf = make_perf(np.arange(8 * times) * 0.5, phrase * times)
    res = align(part, perf)
    assert res.variant == expected
    assert res.n_match == 8 * times and res.n_insertion == res.n_deletion == 0
    if times == 2:
        # the second pass maps to the "-2" copies, in order
        second = sorted((s, p) for s, p in res.match_pairs() if s.endswith("-2"))
        assert len(second) == 8
        assert dict(second)["n3-2"] == "p11"


def test_explicit_and_bad_repeat_choice():
    part = make_part(melody(SCALE[:8]), repeat=(0, 8))
    perf = make_perf(np.arange(16) * 0.5, SCALE[:8] * 2)
    forced = align(part, perf, repeats="minimal")
    assert forced.variant == "A"
    # half the performance has no score counterpart; DTW may also drop a few edge matches
    assert forced.n_insertion >= 8
    assert forced.n_match + forced.n_insertion == 16
    assert align(part, perf, repeats="maximal").variant == "AA"
    with pytest.raises(ValueError):
        align(part, perf, repeats="ABBA")
    assert len(unfold_variant(part, "AA").notes_tied) == 16
    with pytest.raises(ValueError):
        unfold_variant(part)


def test_accepts_partitura_objects():
    part = make_part(melody(SCALE))
    score = pt.score.Score(partlist=[part])
    perf_na = make_perf(np.arange(len(SCALE)) * 0.5, SCALE)
    performed = pt.performance.PerformedPart.from_note_array(perf_na)
    performance = pt.performance.Performance(performedparts=[performed])
    res = align(score, performance)
    assert res.n_match == len(SCALE)
    with pytest.raises(TypeError):
        align(42, perf_na)


def test_match_ratio():
    al = [
        {"label": "match", "score_id": "a", "performance_id": "x"},
        {"label": "deletion", "score_id": "b"},
        {"label": "insertion", "performance_id": "y"},
    ]
    assert match_ratio(al, 2, 2) == pytest.approx(0.5)
    assert match_ratio([], 0, 0) == 1.0


class TestEvaluate:
    GT = [
        {"label": "match", "score_id": "s1", "performance_id": "p1"},
        {"label": "match", "score_id": "s2", "performance_id": "p2"},
        {"label": "match", "score_id": "s3", "performance_id": "p3"},
        {"label": "match", "score_id": "s4", "performance_id": "p4"},
        {"label": "deletion", "score_id": "s5"},
        {"label": "insertion", "performance_id": "p5"},
    ]

    def test_identical_is_perfect(self):
        sc = evaluate_alignment(self.GT, self.GT)
        assert sc.match.f1 == sc.insertion.f1 == sc.deletion.f1 == 1.0
        assert sc.perf_note_accuracy == sc.score_note_accuracy == 1.0

    def test_known_errors(self):
        pred = [
            {"label": "match", "score_id": "s1", "performance_id": "p1"},
            {"label": "match", "score_id": "s2", "performance_id": "p2"},
            {"label": "match", "score_id": "s3", "performance_id": "p4"},  # wrong partner
            {"label": "deletion", "score_id": "s4"},  # missed
            {"label": "deletion", "score_id": "s5"},
            {"label": "insertion", "performance_id": "p3"},
            {"label": "insertion", "performance_id": "p5"},
        ]
        sc = evaluate_alignment(pred, self.GT)
        # match: 2 correct of 3 predicted, of 4 true
        assert sc.match.precision == pytest.approx(2 / 3)
        assert sc.match.recall == pytest.approx(2 / 4)
        assert sc.match.f1 == pytest.approx(2 * (2 / 3) * 0.5 / (2 / 3 + 0.5))
        assert (sc.deletion.precision, sc.deletion.recall) == (0.5, 1.0)
        assert (sc.insertion.precision, sc.insertion.recall) == (0.5, 1.0)
        # performance notes p1, p2, p5 right; p3, p4 wrong -> 3/5
        assert sc.perf_note_accuracy == pytest.approx(3 / 5)
        # score notes s1, s2, s5 right; s3, s4 wrong -> 3/5
        assert sc.score_note_accuracy == pytest.approx(3 / 5)

    def test_empty_types_count_as_perfect(self):
        gt = [{"label": "match", "score_id": "s", "performance_id": "p"}]
        sc = evaluate_alignment(gt, gt)
        assert sc.insertion.f1 == 1.0 and sc.deletion.f1 == 1.0
        assert set(sc.as_flat_dict()) >= {"match_f1", "insertion_recall", "perf_note_accuracy"}

    def test_accepts_align_result(self):
        part = make_part(melody(SCALE))
        res = align(part, make_perf(np.arange(len(SCALE)) * 0.5, SCALE))
        assert evaluate_alignment(res, res.alignment).match.f1 == 1.0


def test_already_unfolded_part_is_used_as_is():
    part = make_part(melody(SCALE[:8]), repeat=(0, 8))
    unfolded = unfold_variant(part, "AA")
    assert is_unfolded(unfolded) and not is_unfolded(part)
    perf = make_perf(np.arange(16) * 0.5, SCALE[:8] * 2)
    res = align(unfolded, perf)
    assert res.n_match == 16
    assert {s for s, _ in res.match_pairs()} == {f"n{i}-{k}" for i in range(8) for k in (1, 2)}


def test_project_types_round_trip():
    types = pytest.importorskip("pianolens.data.types")
    part = make_part(melody(SCALE[:8]), repeat=(0, 8))
    score = types.score_from_partitura(
        part, score_id="synth:s", piece_id=types.PieceId("synth"), keep_part=True
    )
    perf_na = make_perf(np.arange(8) * 0.5, SCALE[:8])  # repeat not taken
    performed = pt.performance.PerformedPart.from_note_array(perf_na)
    perf = types.performance_from_partitura(
        performed,
        performance_id="synth:p",
        piece_id=types.PieceId("synth"),
        performer_id=types.PerformerId("synth:x"),
        provenance="synthetic",
        dataset="synth",
    )
    ap = align_performance(score, perf)
    assert isinstance(ap, types.AlignedPerformance)
    assert ap.alignment.score_id == "synth:s" and ap.alignment.performance_id == "synth:p"
    assert not ap.alignment.ground_truth
    assert len(ap.alignment.matches) == 8
    assert ap.score.meta["unfolded"] == "A"
    assert set(ap.alignment.matches["score_id"]) <= set(ap.score.notes["id"])
    assert set(ap.alignment.matches["performance_id"]) <= set(perf.notes["id"])
    # evaluate accepts the project Alignment type too
    assert evaluate_alignment(ap.alignment, ap.alignment).match.f1 == 1.0


def test_nakamura_cross_check_when_tool_is_built(tmp_path):
    """Runs only if PIANOLENS_NAKAMURA_DIR points at a compiled AlignmentTool."""
    from pianolens.align import nakamura

    tool = nakamura.find_tool()
    if tool is None:
        pytest.skip("Nakamura AlignmentTool not available")
    part = make_part(melody(SCALE))
    xml = tmp_path / "s.musicxml"
    pt.save_musicxml(part, str(xml))
    perf_na = make_perf(np.arange(len(SCALE)) * 0.5, SCALE)
    mid = tmp_path / "p.mid"
    pt.save_performance_midi(pt.performance.PerformedPart.from_note_array(perf_na), str(mid))
    al = nakamura.nakamura_align(xml, mid, tool)
    assert sum(a["label"] == "match" for a in al) == len(SCALE)
