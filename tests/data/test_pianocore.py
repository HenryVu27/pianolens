import io

import mido
import numpy as np
import pytest

from pianolens.data.pianocore import (
    PianoCoRe,
    _ids_by_key,
    _midi_note_keys,
    data_available,
    pianocore_piece_id,
)

needs_data = pytest.mark.skipif(not data_available(), reason="data/raw/pianocore not downloaded")


@pytest.mark.parametrize(
    ("composer", "composition", "movement", "expected"),
    [
        ("Chopin,_Frédéric", "12_Études,_Op.10", "No.12_in_C_minor_\"Revolutionary\"",
         "chopin_op10_no12"),
        ("Beethoven,_Ludwig_van",
         "Piano_Sonata_No.14_in_C_sharp_minor,_Op.27_No.2_(\"Moonlight\")",
         "1._Adagio_sostenuto", "beethoven_op27_no2_mv1"),
        ("Chopin,_Frédéric", "Ballade_No.1_in_G_minor,_Op.23", None, "chopin_op23"),
        ("Schubert,_Franz", "4_Impromptus,_Op.90,_D.899", "3._Andante", "schubert_d899_no3"),
        ("Mozart,_Wolfgang_Amadeus", "Piano_Sonata_No.11_in_A_major,_K.331",
         "3._Alla_Turca._Allegretto", "mozart_k331_mv3"),
        ("Bach,_Johann_Sebastian", "The_Well-Tempered_Clavier,_Book_I,_BWV_846-869",
         "No.1_in_C_major,_BWV_846:_Prelude", "bach_bwv846_prelude"),
        ("Liszt,_Franz", "Grandes_études_de_Paganini,_S.141", "3._La_campanella",
         "liszt_s141_no3"),
        ("Dvořák,_Antonín", "6_Piano_Pieces,_Op.52", "2._Intermezzo", "dvorak_op52_no2"),
    ],
)  # fmt: skip
def test_piece_id_canonical(composer, composition, movement, expected):
    assert pianocore_piece_id(composer, composition, movement) == expected


@pytest.mark.parametrize(
    ("composition", "movement"),
    [
        ("Nocturnes,_Op.27", "Nocturne_No.8_in_D_flat_major"),  # global number, not in-opus
        ("Waltz_No.19_in_A_minor,_Op.posth.", None),  # no catalogue
        ("Piano_Sonata_No.31,_Op.110", "3._Adagio_-_4._Allegro"),  # merged movements
    ],
)
def test_piece_id_falls_back(composition, movement):
    assert pianocore_piece_id("Chopin,_Frédéric", composition, movement).startswith("pianocore:")


def _midi_bytes(notes):
    mf = mido.MidiFile(ticks_per_beat=480)
    tr = mido.MidiTrack()
    mf.tracks.append(tr)
    events = []
    for tick, pitch in notes:
        events += [(tick, "note_on", pitch, 64), (tick + 100, "note_off", pitch, 0)]
    now = 0
    for tick, kind, pitch, vel in sorted(events):
        tr.append(mido.Message(kind, note=pitch, velocity=vel, time=tick - now))
        now = tick
    buf = io.BytesIO()
    mf.save(file=buf)
    return buf.getvalue()


def test_note_keys_sorted_by_tick_then_pitch():
    keys = _midi_note_keys(_midi_bytes([(480, 60), (0, 67), (0, 55)]))
    assert keys == [(0, 55), (0, 67), (480, 60)]


def test_ids_by_key_marks_missing_notes():
    notes = np.array([(0, 55, "a"), (480, 60, "b")],
                     dtype=[("onset_tick", "i8"), ("pitch", "i4"), ("id", "U4")])  # fmt: skip
    assert _ids_by_key([(0, 55), (0, 67), (480, 60)], notes, "onset_tick") == ["a", "", "b"]


@needs_data
def test_loads_aligned_performances():
    pc = PianoCoRe()
    aps = list(pc.iter_aligned(limit=3))
    assert len(aps) == 3 and pc.stats.failed == 0 and pc.stats.pitch_mismatch == 0
    for ap in aps:
        perf, score, al = ap.performance, ap.score, ap.alignment
        assert perf.provenance in ("transcribed", "disklavier")
        assert perf.piece_id == score.piece_id and perf.performer_id.startswith("pianocore:")
        paired = al.pairs[(al.pairs["score_id"] != "") & (al.pairs["performance_id"] != "")]
        s_pitch = dict(zip(score.notes["id"], score.notes["pitch"], strict=True))
        p_pitch = dict(zip(perf.notes["id"], perf.notes["pitch"], strict=True))
        assert all(s_pitch[s] == p_pitch[p] for _, s, p in paired.tolist())
        assert len(al.matches) > 0.5 * len(score.notes)
