"""DF-09: staff numbers are normalised to upper = 1, lower = 2 when a score part is built."""

from __future__ import annotations

import warnings
from collections import Counter
from pathlib import Path

import partitura as pt
import pytest

from pianolens.align._adapters import normalise_piano_staves, to_part

REPO = Path(__file__).resolve().parents[2]
ASAP = REPO / "data" / "raw" / "asap"
GONDOLIERA = ASAP / "Liszt" / "Annees_de_pelerinage_2" / "1_Gondoliera"


def _part(staff_pitches: dict[int, list[int]], pid: str = "P1") -> pt.score.Part:
    """One quarter note per pitch, all staves sounding together on each beat."""
    part = pt.score.Part(pid, "piano", quarter_duration=4)
    part.add(pt.score.TimeSignature(4, 4), 0)
    k = 0
    for staff, pitches in staff_pitches.items():
        for q, p in enumerate(pitches):
            note = pt.score.Note(step="C", octave=p // 12 - 1, alter=None, id=f"{pid}n{k}",
                                 voice=1, staff=staff)  # fmt: skip
            part.add(note, start=4 * q, end=4 * (q + 1))
            k += 1
    pt.score.add_measures(part)
    return part


def _staves(part: pt.score.Part) -> Counter:
    return Counter(int(n.staff) for n in part.notes_tied)


def test_two_staves_numbered_3_4():
    part = _part({3: [72] * 4, 4: [48] * 4})
    assert normalise_piano_staves(part) == {3: 1, 4: 2}
    assert _staves(part) == Counter({1: 4, 2: 4})


def test_two_staves_numbered_1_3_and_idempotent():
    part = _part({1: [72] * 3, 3: [48] * 3})
    normalise_piano_staves(part)
    assert _staves(part) == Counter({1: 3, 2: 3})
    assert normalise_piano_staves(part) == {1: 1, 2: 2}


def test_one_staff_per_part_merges_upper_then_lower():
    """Bach inventions, the Minute Waltz: two parts of one staff each merged onto staff 1."""
    score = [_part({1: [72] * 4}, "P1"), _part({1: [48] * 4}, "P2")]
    merged = to_part(score)
    na = merged.note_array(include_staff=True)
    assert Counter(zip(na["staff"].tolist(), na["pitch"].tolist(), strict=True)) == Counter(
        {(1, 72): 4, (2, 48): 4})


def test_three_staves():
    """Main pair = the two fullest staves; a small staff above them joins the upper one, a
    staff below joins the lower one, one in between goes to the nearer by mean pitch."""
    part = _part({1: [84], 2: [72] * 4, 3: [48] * 4, 4: [36] * 2})
    assert normalise_piano_staves(part) == {1: 1, 2: 1, 3: 2, 4: 2}
    between = _part({1: [72] * 4, 2: [50], 3: [48] * 4})
    assert normalise_piano_staves(between) == {1: 1, 2: 2, 3: 2}


@pytest.mark.skipif(not (GONDOLIERA / "LeungM08M.mid").is_file(), reason="needs ASAP")
def test_affected_asap_score_gives_hand_sync_events():
    """ASAP Liszt S.162 No. 1 (Gondoliera) numbers its staves 3 and 4, so hand synchrony had
    no events (BL-19). After normalisation it has cross-staff onsets."""
    from pianolens.align import align_performance
    from pianolens.features.control import control_features
    from pianolens.report.io import load_performance, load_score

    raw = pt.load_score(str(GONDOLIERA / "xml_score.musicxml"))
    assert {int(n.staff) for p in raw.parts for n in p.notes_tied} == {3, 4}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        score = load_score(GONDOLIERA / "xml_score.musicxml", "liszt_s162_no1")
        assert set(score.notes["staff"].tolist()) == {1, 2}
        perf = load_performance(GONDOLIERA / "LeungM08M.mid", "disklavier", "liszt_s162_no1")
        ap = align_performance(score, perf)
        res = control_features(ap)
    assert res.summary["n_cross_staff_onsets"] > 50
