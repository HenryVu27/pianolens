"""Piano four-hands detection (DF-11): synthetic MusicXML known answers, the report gate on
per-hand features, and the real app catalogue count."""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import pytest

from pianolens.report import ReportInputs, build_report, render_html, to_jsonable
from pianolens.report.four_hands import (
    KNOWN_FOUR_HANDS,
    PER_HAND_KEYS,
    classify,
    detect_four_hands,
    read_layout,
)

REPO = Path(__file__).resolve().parents[2]
N_BARS = 8


def _note(step: str, octave: int, staff: int, *, grace: bool = False, cue: bool = False) -> str:
    return ("<note>" + ("<grace/>" if grace else "") + ("<cue/>" if cue else "")
            + f"<pitch><step>{step}</step><octave>{octave}</octave></pitch>"
            + ("" if grace else "<duration>4</duration>") + f"<staff>{staff}</staff></note>")


def _part(pid: str, n_staves: int, bars_with_notes: dict[int, set[int]],
          extra: str = "") -> str:
    """One part of ``N_BARS`` 4/4 bars; ``bars_with_notes[staff]`` = bar numbers with a note;
    other bars get a whole-bar rest on that staff."""
    out = [f'<part id="{pid}">']
    for b in range(N_BARS):
        out.append(f'<measure number="{b + 1}">')
        if b == 0:
            out.append(f"<attributes><divisions>1</divisions><staves>{n_staves}</staves>"
                       "<time><beats>4</beats><beat-type>4</beat-type></time></attributes>")
        for s in range(1, n_staves + 1):
            if s > 1:
                out.append("<backup><duration>4</duration></backup>")
            if b in bars_with_notes.get(s, set()):
                out.append(_note("C", 6 - s, s))
            else:
                out.append(f'<note><rest measure="yes"/><duration>4</duration><staff>{s}</staff>'
                           "</note>")
            if b == 0 and extra:
                out.append(extra)
        out.append("</measure>")
    out.append("</part>")
    return "".join(out)


def _score(parts: list[tuple[str, str, str]]) -> bytes:
    """``parts``: (part name, abbreviation, <part> xml)."""
    pl = "".join(f'<score-part id="P{i + 1}"><part-name>{n}</part-name>'
                 + (f"<part-abbreviation>{a}</part-abbreviation>" if a else "") + "</score-part>"
                 for i, (n, a, _) in enumerate(parts))
    body = "".join(x for *_, x in parts)
    return (f'<?xml version="1.0" encoding="UTF-8"?><score-partwise version="3.1">'
            f"<part-list>{pl}</part-list>{body}</score-partwise>").encode()


ALL = set(range(N_BARS))
DUET = _score([("Piano", "I", _part("P1", 2, {1: ALL, 2: ALL})),
               ("Piano", "II", _part("P2", 2, {1: ALL, 2: ALL - {0}}))])
SOLO = _score([("Piano", "", _part("P1", 2, {1: ALL, 2: ALL}))])
OSSIA = _score([("Piano", "", _part("P1", 2, {1: ALL, 2: ALL})),  # 2nd system in 3 of 8 bars
                ("Piano", "", _part("P2", 2, {1: {5, 6, 7}, 2: {5, 6, 7}}))])
ONE_PART_FOUR = _score([("Piano", "", _part("P1", 4, {s: ALL for s in (1, 2, 3, 4)}))])
PRIMO_ONE_STAFF = _score([("Primo", "", _part("P1", 1, {1: ALL})),
                          ("Secondo", "", _part("P2", 1, {1: ALL}))])
PIANO_2_ONE_STAFF = _score([("Piano", "", _part("P1", 1, {1: ALL})),  # Chopin Op. 15/3 layout
                            ("Piano 2", "", _part("P2", 1, {1: ALL}))])
FLUTE_AND_PIANO = _score([("Flauta", "", _part("P1", 1, {1: ALL})),  # Chopin Op. 29 layout
                          ("Piano", "", _part("P2", 2, {1: ALL, 2: ALL}))])
# a second system holding only grace and cue notes is not a second player
GRACE = _part("P2", 2, {}, extra=_note("D", 5, 1, grace=True) + _note("E", 4, 2, cue=True))
GRACE_ONLY = _score([("Piano", "", _part("P1", 2, {1: ALL, 2: ALL})), ("Piano", "", GRACE)])


def _mxl(xml: bytes) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("META-INF/container.xml",
                   '<container><rootfiles><rootfile full-path="score.xml"/></rootfiles>'
                   "</container>")
        z.writestr("score.xml", xml)
    return buf.getvalue()


@pytest.mark.parametrize("xml, four, evidence, n_full", [
    (DUET, True, "structure", 4),
    (SOLO, False, "", 2),
    (OSSIA, False, "", 2),
    (ONE_PART_FOUR, True, "structure", 4),
    (PRIMO_ONE_STAFF, True, "part names", 0),
    (PIANO_2_ONE_STAFF, False, "", 0),
    (FLUTE_AND_PIANO, False, "", 2),
    (GRACE_ONLY, False, "", 2),
])  # fmt: skip
def test_known_answers_full_and_quick(xml, four, evidence, n_full):
    full = detect_four_hands(xml)
    assert (full.is_four_hands, full.evidence, full.n_full_staves) == (four, evidence, n_full)
    quick = detect_four_hands(xml, quick=True)
    assert (quick.is_four_hands, quick.evidence) == (four, evidence)
    assert detect_four_hands(_mxl(xml)).is_four_hands == four  # compressed MusicXML


def test_layout_counts_bars_per_staff():
    lay = read_layout(DUET)
    assert [p.n_bars for p in lay] == [N_BARS, N_BARS]
    assert lay[1].staff_bars == {1: N_BARS, 2: N_BARS - 1}
    assert [p.abbreviation for p in lay] == ["I", "II"]
    assert classify(lay) == (True, "structure", 4)


def test_files_and_fallback_list(tmp_path):
    f = tmp_path / "duet.musicxml"
    f.write_bytes(DUET)
    assert detect_four_hands(f).is_four_hands
    mid = tmp_path / "score.mid"
    mid.write_bytes(b"MThd")
    pid = "faure_op56_mv1"
    assert pid in KNOWN_FOUR_HANDS
    r = detect_four_hands(mid, pid)  # not MusicXML: the known list decides
    assert (r.is_four_hands, r.evidence, r.n_full_staves) == (True, "known list", -1)
    assert not detect_four_hands(mid, "chopin_op10_no3").is_four_hands
    assert detect_four_hands(None, pid).evidence == "known list"
    bad = tmp_path / "bad.xml"
    bad.write_bytes(b"<score-partwise><part")
    assert not detect_four_hands(bad).is_four_hands  # unreadable, never raises
    assert detect_four_hands(f).as_report()["skipped"] == list(PER_HAND_KEYS)
    assert detect_four_hands(SOLO).as_report() is None


def test_report_leaves_out_per_hand_features_for_duets():
    from tests.report.test_report import CFG, _target

    solo = to_jsonable(build_report(ReportInputs(ap=_target(), piece_id="synth"), CFG))
    assert "four_hands" not in solo["piece"]
    assert solo["control"]["hand_async_median_ms"] is not None
    assert not any("four hands" in n for n in solo["confidence"]["notes"])
    # known duet id, no score path: detected from the fallback list
    duet = to_jsonable(build_report(ReportInputs(ap=_target(), piece_id="faure_op56_mv1"), CFG))
    assert duet["piece"]["four_hands"]["evidence"] == "known list"
    assert all(duet["control"][k] is None for k in PER_HAND_KEYS)
    assert any(n.startswith("Piano four hands:") for n in duet["confidence"]["notes"])
    card = next(c for c in duet["summary"] if c["title"] == "Control")
    assert any(s.startswith("Hands together: not measured") for s in card["findings"])
    assert "Piano four hands" in render_html(duet)
    # everything that is not per hand is unchanged
    for k in ("correctness", "tempo", "bars", "issues", "practise", "evenness_runs"):
        assert duet[k] == solo[k]
    # an explicit False skips detection
    forced = to_jsonable(build_report(ReportInputs(ap=_target(), piece_id="faure_op56_mv1",
                                                   four_hands=False), CFG))
    assert "four_hands" not in forced["piece"]
    assert forced["control"]["hand_async_median_ms"] == solo["control"]["hand_async_median_ms"]


def _datasets_available() -> bool:
    from pianolens.data import asap, pianocore, pianocore_cache

    return (pianocore.data_available() and pianocore_cache.cache_available()
            and asap.data_available())


@pytest.mark.skipif(not _datasets_available(), reason="PianoCoRe / ASAP not on this machine")
def test_real_catalogue_has_exactly_the_three_duets():
    from pianolens.app.catalog import build_catalog

    cat = build_catalog()
    duets = {p.piece_id for p in cat if p.four_hands}
    assert len(cat) == 805
    assert duets == set(KNOWN_FOUR_HANDS)
    # and the structure rule alone finds them (the list is only a fallback)
    from pianolens.data import pianocore

    with zipfile.ZipFile(pianocore.DEFAULT_ROOT / pianocore.RAW_ZIP) as z:
        for p in cat:
            if p.four_hands:
                r = detect_four_hands(z.read(pianocore.RAW_PREFIX + p.score))
                assert (r.evidence, r.n_full_staves) == ("structure", 4)
    assert json.loads(json.dumps([p.__dict__ for p in cat]))  # JSON-ready for /api/pieces
