"""BL-26: MusicXML tremolo abbreviations are written out before alignment."""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

import numpy as np
import partitura as pt
import pytest

from pianolens.align._adapters import load_notes, to_part
from pianolens.align.tremolo import load_musicxml_expanded, read_musicxml_root, read_tremolos

REPO = Path(__file__).resolve().parents[2]
D899 = REPO / "data" / "raw" / "asap" / "Schubert" / "Impromptu_op.90_D.899" / "1"

_STEP = dict(enumerate([("C", 0), ("C", 1), ("D", 0), ("D", 1), ("E", 0), ("F", 0), ("F", 1),
                        ("G", 0), ("G", 1), ("A", 0), ("A", 1), ("B", 0)]))


def _note(midi: int, dur: int, typ: str, nid: str, *, chord: bool = False, dots: int = 0,
          tremolo: tuple[str, int] | None = None, time_mod: tuple[int, int] | None = None,
          tie: str | None = None, voice: int = 1) -> str:  # fmt: skip
    step, alter = _STEP[midi % 12]
    octave = midi // 12 - 1
    xml = [f'<note id="{nid}">']
    if chord:
        xml.append("<chord/>")
    xml.append(f"<pitch><step>{step}</step>" + (f"<alter>{alter}</alter>" if alter else "")
               + f"<octave>{octave}</octave></pitch>")  # fmt: skip
    xml.append(f"<duration>{dur}</duration>")
    if tie:
        xml.append(f'<tie type="{tie}"/>')
    xml.append(f"<voice>{voice}</voice><type>{typ}</type>" + "<dot/>" * dots)
    if time_mod:
        xml.append(f"<time-modification><actual-notes>{time_mod[0]}</actual-notes>"
                   f"<normal-notes>{time_mod[1]}</normal-notes></time-modification>")
    notations = []
    if tie:
        notations.append(f'<tied type="{tie}"/>')
    if tremolo:
        notations.append(f'<ornaments><tremolo type="{tremolo[0]}">{tremolo[1]}</tremolo>'
                         "</ornaments>")  # fmt: skip
    if notations:
        xml.append("<notations>" + "".join(notations) + "</notations>")
    xml.append("</note>")
    return "".join(xml)


def _rest(dur: int, typ: str) -> str:
    return f"<note><rest/><duration>{dur}</duration><voice>1</voice><type>{typ}</type></note>"


def _score(tmp_path: Path, measures: list[list[str]], divisions: int, beats: int = 4) -> Path:
    body = []
    for i, notes in enumerate(measures, start=1):
        attrs = ""
        if i == 1:
            attrs = (f"<attributes><divisions>{divisions}</divisions><key><fifths>0</fifths></key>"
                     f"<time><beats>{beats}</beats><beat-type>4</beat-type></time>"
                     "<clef><sign>G</sign><line>2</line></clef></attributes>")  # fmt: skip
        body.append(f'<measure number="{i}">{attrs}{"".join(notes)}</measure>')
    xml = ('<?xml version="1.0" encoding="UTF-8"?><score-partwise version="3.1"><part-list>'
           '<score-part id="P1"><part-name>Piano</part-name></score-part></part-list>'
           f'<part id="P1">{"".join(body)}</part></score-partwise>')  # fmt: skip
    path = tmp_path / "score.musicxml"
    path.write_text(xml)
    return path


def _notes(part: pt.score.Part) -> list[tuple[str, float, float, int]]:
    na = part.note_array()
    order = np.lexsort((na["pitch"], na["onset_quarter"]))
    return [(str(r["id"]), float(r["onset_quarter"]), float(r["duration_quarter"]),
             int(r["pitch"])) for r in na[order]]  # fmt: skip


def test_single_note_two_marks_is_four_sixteenths(tmp_path):
    # quarter C5 with 2 marks -> 16ths: 4 strokes; then a dotted half rest-free filler note
    path = _score(tmp_path, [[_note(72, 4, "quarter", "n1", tremolo=("single", 2)),
                              _note(60, 12, "half", "n2", dots=1)]], divisions=4)  # fmt: skip
    score, rep = load_musicxml_expanded(path)
    part = score.parts[0]
    assert (rep.n_groups, rep.n_expanded, rep.n_notes_added) == (1, 1, 3)
    got = _notes(part)
    assert got[:4] == [("n1", 0.0, 0.25, 72), ("n1tr1", 0.25, 0.25, 72),
                       ("n1tr2", 0.5, 0.25, 72), ("n1tr3", 0.75, 0.25, 72)]  # fmt: skip
    assert got[4] == ("n2", 1.0, 3.0, 60)
    # an expanded stroke is a written note: no tremolo mark left
    assert not any("tremolo" in (n.ornaments or []) for n in part.notes_tied)


def test_single_note_chord_expands_every_chord_note(tmp_path):
    # the XML mark sits on the chord's first note only (as in every catalogue score)
    m = [_note(60, 2, "quarter", "a", tremolo=("single", 1)), _note(64, 2, "quarter", "b",
         chord=True), _note(67, 6, "half", "c", dots=1)]  # fmt: skip
    score, rep = load_musicxml_expanded(_score(tmp_path, [m], divisions=2))
    got = _notes(score.parts[0])
    assert ("a", 0.0, 0.5, 60) in got and ("atr1", 0.5, 0.5, 60) in got
    assert ("b", 0.0, 0.5, 64) in got and ("btr1", 0.5, 0.5, 64) in got
    assert rep.n_notes_added == 2


def test_two_note_tremolo_alternates_over_one_written_value(tmp_path):
    # two half notes, each written at half its value (time-modification 2/1), 2 marks -> 16ths:
    # 2 quarters / 0.25 = 8 strokes C G C G ...
    m = [_note(60, 4, "half", "x", tremolo=("start", 2), time_mod=(2, 1)),
         _note(67, 4, "half", "y", tremolo=("stop", 2), time_mod=(2, 1)),
         _note(72, 8, "half", "z")]  # fmt: skip
    score, rep = load_musicxml_expanded(_score(tmp_path, [m], divisions=4))
    got = _notes(score.parts[0])
    strokes = [g for g in got if g[1] < 2.0]
    assert [g[3] for g in strokes] == [60, 67] * 4
    assert [g[1] for g in strokes] == [0.25 * k for k in range(8)]
    assert {g[2] for g in strokes} == {0.25}
    assert strokes[0][0] == "x" and strokes[1][0] == "y" and strokes[2][0] == "xtr1"
    assert (rep.n_expanded, rep.n_notes_added) == (1, 6)


def test_triplet_stroke_count_uses_written_value(tmp_path):
    # Schubert D.899/1 pattern: dotted quarter in a 12:8 tuplet, 1 mark -> 3 triplet eighths
    m = [_note(51, 12, "quarter", "t", dots=1, time_mod=(12, 8), tremolo=("single", 1)),
         _note(60, 36, "half", "u", dots=1)]  # fmt: skip
    score, rep = load_musicxml_expanded(_score(tmp_path, [m], divisions=12))
    got = _notes(score.parts[0])
    assert [round(g[1], 4) for g in got[:3]] == [0.0, 0.3333, 0.6667]
    assert rep.n_notes_added == 2


def test_unmeasured_and_fast_tremolos_are_kept_with_marks_on_every_chord_note(tmp_path):
    m1 = [_note(60, 4, "quarter", "a", tremolo=("unmeasured", 0)),
          _note(64, 4, "quarter", "b", chord=True), _rest(12, "half")]  # fmt: skip
    m2 = [_note(62, 4, "quarter", "c", tremolo=("single", 3)),  # 32nds: unmeasured by convention
          _note(65, 4, "quarter", "d", chord=True), _rest(12, "half")]  # fmt: skip
    path = _score(tmp_path, [m1, m2], divisions=4)
    root = read_musicxml_root(path)
    skips = [g.skip for g in read_tremolos(root)]
    assert skips == ["unmeasured", "unmeasured (32nds or faster)"]
    score, rep = load_musicxml_expanded(path)
    part = score.parts[0]
    assert rep.n_expanded == 0 and rep.n_notes_added == 0
    assert len(part.notes_tied) == 4
    assert all("tremolo" in (n.ornaments or []) for n in part.notes_tied)


def test_tied_tremolo_is_not_expanded(tmp_path):
    m1 = [_rest(12, "half"), _note(60, 4, "quarter", "a", tremolo=("single", 1), tie="start")]
    m2 = [_note(60, 4, "quarter", "b", tie="stop"), _rest(12, "half")]
    score, rep = load_musicxml_expanded(_score(tmp_path, [m1, m2], divisions=4))
    assert rep.kept["tied"] == 1 and rep.n_notes_added == 0


def test_divisions_are_scaled_when_a_stroke_is_not_whole(tmp_path):
    # divisions 1: a half note with 2 marks has 16th strokes of 0.25 divisions -> factor 4
    m = [_note(60, 2, "half", "h", tremolo=("single", 2)), _note(67, 2, "half", "k")]
    score, rep = load_musicxml_expanded(_score(tmp_path, [m], divisions=1))
    assert rep.scale == {"P1": 4}
    got = _notes(score.parts[0])
    assert [g[1] for g in got[:8]] == [0.25 * k for k in range(8)]
    assert got[8] == ("k", 2.0, 2.0, 67)


def test_to_part_expands_and_records_a_load_note(tmp_path):
    m = [_note(72, 4, "quarter", "n1", tremolo=("single", 2)), _note(60, 12, "half", "n2",
         dots=1)]  # fmt: skip
    path = _score(tmp_path, [m], divisions=4)
    part = to_part(path)
    assert len(part.notes_tied) == 5
    assert load_notes(part) == ["tremolo: 1 marks, 1 expanded into 3 added notes"]
    off = to_part(path, expand_tremolos=False)
    assert len(off.notes_tied) == 2 and load_notes(off) == []
    # a parsed partitura score has lost the tremolo type: not expanded
    assert len(to_part(pt.load_score(str(path))).notes_tied) == 2


@pytest.mark.skipif(not (D899 / "xml_score.musicxml").is_file(), reason="ASAP not downloaded")
def test_schubert_d899_1_matches_the_asap_score_midi():
    """The 172 tremolo marks (all single, 1 mark, in triplets) expand into 1,191 notes, and the
    unfolded score then matches ASAP's own score MIDI almost note for note."""
    warnings.simplefilter("ignore")
    sys.setrecursionlimit(max(sys.getrecursionlimit(), 100_000))
    mna = pt.load_score_midi(str(D899 / "midi_score.mid")).note_array()
    mo, mp = mna["onset_quarter"].astype(float), mna["pitch"].astype(int)
    unmatched = {}
    for expand in (False, True):
        score, rep = load_musicxml_expanded(D899 / "xml_score.musicxml", expand=expand)
        if expand:
            assert (rep.n_groups, rep.n_expanded, rep.n_notes_added) == (172, 172, 1191)
        part = score.parts[0] if len(score.parts) == 1 else pt.score.merge_parts(score.parts)
        na = pt.score.unfold_part_maximal(part).note_array(include_grace_notes=True)
        na = na[~na["is_grace"].astype(bool)]
        used = np.zeros(len(mna), bool)
        for o, p in zip(na["onset_quarter"].astype(float), na["pitch"].astype(int), strict=True):
            c = np.flatnonzero((mp == p) & (np.abs(mo - o) < 0.06) & ~used)
            if len(c):
                used[c[0]] = True
        unmatched[expand] = int((~used).sum())
    assert unmatched[False] > 1000  # measured 1,218 score-MIDI notes with no XML note
    assert unmatched[True] < 50  # measured 27
