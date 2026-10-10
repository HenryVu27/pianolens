"""BL-33: left-hand chord notes written in the upper staff move to the lower staff; DF-11 note:
a fragile in-between staff choice (Chopin Op. 29 "Flauta") is logged and recorded."""

from __future__ import annotations

import logging
import warnings
import zipfile
from collections import Counter
from pathlib import Path

import numpy as np
import partitura as pt
import pytest

from pianolens.align._adapters import (
    load_notes,
    normalise_piano_staves,
    split_wide_upper_chords,
    to_part,
)

WALTZ = ('Chopin,_Frédéric/Waltzes,_Op.64/Waltz_No.6_in_D_flat_major,_"Minute_Waltz",'
         "_Molto_vivace/score.mxl")  # fmt: skip
OP29 = "Chopin,_Frédéric/Impromptu_No.1_in_A_flat_major,_Op.29/score.mxl"


def _pianocore_score(rel: str, tmp_path: Path) -> Path:
    from pianolens.data import pianocore

    raw = pianocore.DEFAULT_ROOT / pianocore.RAW_ZIP
    if not raw.is_file():
        pytest.skip("PianoCoRe raw zip not downloaded")
    dst = tmp_path / "score.mxl"
    with zipfile.ZipFile(raw) as z:
        dst.write_bytes(z.read(pianocore.RAW_PREFIX + rel))
    return dst


def _with_pitches(events: list[tuple[int, int, int, int]]) -> pt.score.Part:
    part = pt.score.Part("P1", "piano", quarter_duration=4)
    part.add(pt.score.TimeSignature(4, 4), 0)
    for k, (q, staff, voice, p) in enumerate(events):
        step, alter = [("C", 0), ("C", 1), ("D", 0), ("D", 1), ("E", 0), ("F", 0), ("F", 1),
                       ("G", 0), ("G", 1), ("A", 0), ("A", 1), ("B", 0)][p % 12]  # fmt: skip
        n = pt.score.Note(step=step, octave=p // 12 - 1, alter=alter or None, id=f"n{k}",
                          voice=voice, staff=staff)  # fmt: skip
        part.add(n, start=4 * q, end=4 * (q + 1))
    pt.score.add_measures(part)
    return part


def _staff(part: pt.score.Part) -> dict[str, int]:
    return {n.id: int(n.staff) for n in part.notes_tied}


def test_waltz_like_chord_in_a_one_voice_upper_staff_moves_down():
    # beat 0: RH E5 over LH Eb4+F4 written in the RH (one voice); LH holds nothing new
    # beat 1: same, but the lower staff starts A3 (still within an octave of Eb4-F4)
    # beat 2: a narrow RH chord stays
    part = _with_pitches([(0, 1, 1, 63), (0, 1, 1, 65), (0, 1, 1, 76),
                          (1, 1, 1, 63), (1, 1, 1, 65), (1, 1, 1, 76), (1, 2, 1, 57),
                          (2, 1, 1, 67), (2, 1, 1, 72), (2, 1, 1, 76)])  # fmt: skip
    moved, chords = split_wide_upper_chords(part)
    assert (moved, chords) == (4, 2)
    st = _staff(part)
    assert [st[f"n{k}"] for k in range(10)] == [2, 2, 1, 2, 2, 1, 2, 1, 1, 1]
    # applying it again changes nothing
    assert split_wide_upper_chords(part) == (0, 0)


def test_guards_keep_chords_the_left_hand_cannot_take():
    part = _with_pitches([
        (0, 1, 1, 63), (0, 1, 1, 76), (0, 2, 1, 40),  # LH busy two octaves below
        (1, 1, 1, 70), (1, 1, 1, 72), (1, 1, 1, 78), (1, 1, 1, 84), (1, 2, 1, 50),  # gap 6 < 8
        (2, 1, 1, 60), (2, 1, 1, 64), (2, 1, 1, 68), (2, 1, 1, 84), (2, 1, 1, 98),  # top > octave
    ])  # fmt: skip
    assert split_wide_upper_chords(part) == (0, 0)


def test_voice_condition_in_a_multi_voice_upper_staff():
    part = _with_pitches([
        (0, 1, 1, 79), (0, 1, 5, 64), (0, 2, 5, 55),  # LH voice crossing up: moves
        (1, 1, 1, 79), (1, 1, 1, 64), (1, 2, 5, 52),  # same voice as the top note: stays
        (2, 1, 2, 60),  # (makes the upper staff multi-voice regardless)
    ])  # fmt: skip
    assert split_wide_upper_chords(part) == (1, 1)
    st = _staff(part)
    assert st["n1"] == 2 and st["n4"] == 1


def test_single_staff_score_is_untouched():
    part = _with_pitches([(0, 1, 1, 48), (0, 1, 1, 76)])
    assert split_wide_upper_chords(part) == (0, 0)


def test_waltz_op64_1_left_hand_chords_move_to_the_lower_staff(tmp_path):
    """PianoCoRe's Op. 64/1: parts "rh" / "lh" (one staff each, voice 1 throughout); the "rh"
    part holds the left hand's chords as members of the melody's chords in 19 measures (R-11)."""
    warnings.simplefilter("ignore")
    path = _pianocore_score(WALTZ, tmp_path)
    off = to_part(path, split_wide_chords=False)
    on = to_part(path)
    assert Counter(_staff(off).values()) == Counter({1: 753, 2: 617})
    assert Counter(_staff(on).values()) == Counter({1: 688, 2: 682})
    so, sn = _staff(off), _staff(on)
    moved = [n for n in off.notes_tied if sn[n.id] != so[n.id]]
    ms = list(on.measures)
    starts = np.array([m.start.t for m in ms])
    bars = {ms[np.searchsorted(starts, n.start.t, side="right") - 1].number for n in moved}
    assert bars == {29, 30, 31, 32, 33, 45, 46, 47, 48, 49, 117, 118, 119, 120, 121, 133, 134,
                    135, 136}  # fmt: skip
    assert all(so[n.id] == 1 and sn[n.id] == 2 for n in moved)
    assert max(int(n.midi_pitch) for n in moved) <= 70
    assert load_notes(on) == ["hands: 65 notes of 31 upper-staff chords wider than an octave "
                              "moved to the lower staff"]  # fmt: skip


def test_fragile_in_between_staff_is_logged_and_recorded(caplog):
    # staves 1 (mean 74) and 3 (mean 54) are the main pair; staff 2 (mean 64.4) is 0.4 from the
    # midpoint 64 -> joins the upper staff, with a warning
    ev = [(q, 1, 1, 74) for q in range(4)] + [(q, 3, 1, 54) for q in range(4)]
    ev += [(0, 2, 1, 64), (1, 2, 1, 65), (2, 2, 1, 64)]
    part = _with_pitches(ev)
    with caplog.at_level(logging.WARNING, logger="pianolens.align._adapters"):
        assert normalise_piano_staves(part) == {1: 1, 2: 1, 3: 2}
    assert any("fragile" in r.getMessage() for r in caplog.records)
    assert load_notes(part) and "margin of 0.33 semitone" in load_notes(part)[0]
    # a clear choice (mean 70) is silent
    ev2 = [(q, 1, 1, 74) for q in range(4)] + [(q, 3, 1, 54) for q in range(4)]
    part2 = _with_pitches(ev2 + [(0, 2, 1, 70)])
    caplog.clear()
    with caplog.at_level(logging.WARNING, logger="pianolens.align._adapters"):
        normalise_piano_staves(part2)
    assert not caplog.records and load_notes(part2) == []


def test_chopin_op29_flauta_margin_is_recorded(tmp_path, caplog):
    warnings.simplefilter("ignore")
    path = _pianocore_score(OP29, tmp_path)
    with caplog.at_level(logging.WARNING, logger="pianolens.align._adapters"):
        part = to_part(path)
    notes = [n for n in load_notes(part) if n.startswith("staves:")]
    assert len(notes) == 1 and "margin of 0.11 semitone" in notes[0]
    assert "joins the upper staff" in notes[0]
    assert any("fragile" in r.getMessage() for r in caplog.records)
