"""Expand MusicXML tremolo abbreviations into the notes they stand for (BL-26).

A tremolo mark is notation shorthand: a dotted quarter with one slash in a triplet passage means
three re-struck triplet eighths, and two half notes joined by two beams mean eight alternating
sixteenths. partitura 1.9 keeps only the name ``"tremolo"`` in ``Note.ornaments`` and loses its
type and number of marks, so the score the aligner sees has one note where the pianist plays
several. The extra strokes then become insertions or ornament matches (BL-23: 124 of the 188 notes
the tight ornament rule re-flagged came from the 172 unexpanded tremolos of Schubert D.899/1).

This module reads the marks from the MusicXML itself and rewrites the loaded partitura parts.

**Stroke value.** MusicXML ``<tremolo>`` text is the number of marks; the beams the note already
has (an eighth has 1, a 16th 2, ...) are not included (MusicXML 4.0, ``tremolo`` element). The
stroke level is ``beams(type) + marks``: level 1 strokes are eighths, 2 sixteenths, 3 32nds.
The number of strokes is the written value (type and dots, before any tuplet ratio) divided by
the stroke value; the strokes split the note's actual duration evenly, so tuplets carry over.

* ``single``: one note (or chord) re-struck ``n`` times.
* ``start`` / ``stop`` (two-note, fingered): the pair lasts one written value of either note
  (MusicXML writes each at half its duration); its ``n`` strokes alternate first, second, first...

**Convention for unmeasured tremolos** (``TREMOLO_MAX_MEASURED_LEVEL``). A tremolo is expanded
only when it is measured: type ``single`` / ``start``+``stop`` with at least one mark and a stroke
level of at most 2 (sixteenths). Type ``unmeasured``, and strokes of 32nds or faster (level 3+),
are read as unmeasured: engraving practice uses three or more strokes for an unmeasured tremolo
("as fast as possible"; Gould, *Behind Bars*, 2011, chapter on tremolos), and the number of notes
a pianist plays is then not written. Those keep their written notes, and the ``"tremolo"`` mark is
copied to every note of the chord, so the correctness ornament rule tolerates the re-strikes of
each chord note (before, only the note carrying the XML mark, usually the chord's first, did).
Expanded strokes drop the ``"tremolo"`` mark: they are ordinary written notes now.

Not expanded (and counted): tied tremolo notes, grace notes, rests, two-note tremolos whose
partner is missing or not adjacent, and non-integer stroke counts.

Note ids: the original note keeps its id and becomes the first stroke (or the first of its
alternation); added strokes get ``"<id>tr<k>"`` (k = 1, 2, ...), which still unfolds to
``"<id>tr<k>-1"``. When a stroke does not fit the score's divisions, every duration of that part
is multiplied by an integer factor first (MusicXML level), which changes ``onset_div`` values but
no beat or quarter positions.
"""

from __future__ import annotations

import io
import math
import zipfile
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import partitura as pt
from lxml import etree

__all__ = [
    "MUSICXML_SUFFIXES",
    "TREMOLO_MAX_MEASURED_LEVEL",
    "TremoloGroup",
    "TremoloReport",
    "expand_tremolos",
    "load_musicxml_expanded",
    "read_musicxml_root",
    "read_tremolos",
]

MUSICXML_SUFFIXES = (".xml", ".musicxml", ".mxl")

TREMOLO_MAX_MEASURED_LEVEL = 2
"""Highest stroke level (beams + marks) read as a measured tremolo; 2 = sixteenth strokes.
Level 3+ (32nds and faster) and type ``unmeasured`` are kept as written (see module docstring)."""

_TYPE_QUARTERS = {
    "maxima": 32.0, "long": 16.0, "breve": 8.0, "whole": 4.0, "half": 2.0, "quarter": 1.0,
    "eighth": 0.5, "16th": 0.25, "32nd": 0.125, "64th": 0.0625, "128th": 0.03125,
    "256th": 0.015625,
}  # fmt: skip
_TYPE_BEAMS = {"eighth": 1, "16th": 2, "32nd": 3, "64th": 4, "128th": 5, "256th": 6}


@dataclass
class TremoloGroup:
    """One tremolo in the MusicXML: a note or chord (``single``), or two of them (``double``).

    ``first`` / ``second`` are the ``doc_order`` values (document order of ``<note>`` elements in
    the part, partitura's ``Note.doc_order``) of the chord's notes; ``second`` is empty for a
    single-note tremolo. ``span_divs`` is the XML duration the strokes share.
    """

    part_id: str
    measure: str
    kind: str  # "single" or "double"
    xml_type: str  # "single", "start" or "unmeasured"
    marks: int
    level: int
    n_strokes: float
    span_divs: int
    first: list[int] = field(default_factory=list)
    second: list[int] = field(default_factory=list)
    skip: str = ""  # why it is not expanded ("" = expand)

    @property
    def measured(self) -> bool:
        return self.skip == ""


@dataclass
class TremoloReport:
    """What :func:`expand_tremolos` did to one score."""

    n_groups: int = 0
    n_expanded: int = 0
    n_notes_added: int = 0
    kept: Counter = field(default_factory=Counter)  # reason -> groups not expanded
    scale: dict[str, int] = field(default_factory=dict)  # part id -> divisions factor (> 1)

    def describe(self) -> str:
        kept = ", ".join(f"{k} {v}" for k, v in sorted(self.kept.items()))
        out = (f"tremolo: {self.n_groups} marks, {self.n_expanded} expanded into "
               f"{self.n_notes_added} added notes")  # fmt: skip
        if kept:
            out += f"; kept as written: {kept}"
        if self.scale:
            out += f"; divisions scaled {self.scale}"
        return out


def read_musicxml_root(path: Path | str | bytes) -> Any:
    """The ``<score-partwise>`` element of a MusicXML file (``.xml``, ``.musicxml``, compressed
    ``.mxl``) or of its bytes."""
    data = path if isinstance(path, bytes) else Path(path).read_bytes()
    if data[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            cont = etree.fromstring(z.read("META-INF/container.xml"))
            name = cont.find(".//{*}rootfile").get("full-path")
            data = z.read(name)
    parser = etree.XMLParser(resolve_entities=False, huge_tree=True, remove_comments=True,
                             remove_blank_text=True)  # fmt: skip
    return etree.fromstring(data, parser)


def _written_quarters(e: Any) -> float | None:
    q = _TYPE_QUARTERS.get((e.findtext("type") or "").strip())
    if q is None:
        return None
    dots = len(e.findall("dot"))
    return q * (2.0 - 0.5**dots)


def _duration(e: Any) -> int:
    t = e.findtext("duration")
    return int(float(t)) if t else 0


def _tremolo(e: Any) -> Any:
    return e.find("notations/ornaments/tremolo")


def read_tremolos(root: Any) -> list[TremoloGroup]:
    """Every tremolo of every part, in document order, with its stroke count and whether it is
    expanded (``skip == ""``) or kept as written (``skip`` says why)."""
    out: list[TremoloGroup] = []
    for part_el in root.iter("part"):
        pid = part_el.get("id", "P1")
        doc = 0
        for m in part_el.xpath("measure"):
            chords: list[list[tuple[int, Any]]] = []
            for e in m:
                if e.tag != "note":
                    continue
                if e.find("chord") is not None and chords:
                    chords[-1].append((doc, e))
                else:
                    chords.append([(doc, e)])
                doc += 1
            used: set[int] = set()
            for ci, chord in enumerate(chords):
                if ci in used:
                    continue
                marked = [e for _, e in chord if _tremolo(e) is not None]
                if not marked:
                    continue
                tr = _tremolo(marked[0])
                xml_type = tr.get("type", "single")
                if xml_type == "stop":
                    out.append(_group(pid, m, "single", xml_type, chord, [], "unpaired stop"))
                    continue
                if xml_type == "start":
                    voice = chord[0][1].findtext("voice")
                    partner = None
                    for cj in range(ci + 1, len(chords)):
                        if chords[cj][0][1].findtext("voice") != voice:
                            continue
                        partner = cj
                        break
                    pt_tr = [_tremolo(e) for _, e in chords[partner]] if partner is not None else []
                    if partner is None or not any(
                        t is not None and t.get("type") == "stop" for t in pt_tr
                    ):
                        out.append(_group(pid, m, "single", xml_type, chord, [],
                                          "unpaired start"))  # fmt: skip
                        continue
                    used.add(partner)
                    out.append(_group(pid, m, "double", xml_type, chord, chords[partner], ""))
                    continue
                out.append(_group(pid, m, "single", xml_type, chord, [], ""))
    return out


def _group(pid: str, m: Any, kind: str, xml_type: str, first: list[tuple[int, Any]],
           second: list[tuple[int, Any]], skip: str) -> TremoloGroup:  # fmt: skip
    head = first[0][1]
    tr = next(_tremolo(e) for _, e in first if _tremolo(e) is not None)
    try:
        marks = int((tr.text or "0").strip() or 0)
    except ValueError:
        marks = 0
    ntype = (head.findtext("type") or "").strip()
    level = _TYPE_BEAMS.get(ntype, 0) + marks
    wq = _written_quarters(head)
    n = wq / 2.0**-level if (wq is not None and marks > 0) else 0.0
    span = _duration(head) + (_duration(second[0][1]) if second else 0)
    members = [e for _, e in first + second]
    if not skip:
        if xml_type == "unmeasured":
            skip = "unmeasured"
        elif marks <= 0:
            skip = "no marks"
        elif level > TREMOLO_MAX_MEASURED_LEVEL:
            skip = "unmeasured (32nds or faster)"
        elif any(e.find("grace") is not None or e.find("rest") is not None for e in members):
            skip = "grace or rest"
        elif any(e.find("tie") is not None for e in members):
            skip = "tied"
        elif wq is None or abs(n - round(n)) > 1e-9 or round(n) < 2:
            skip = "stroke count not an integer >= 2"
        elif span <= 0:
            skip = "no duration"
    return TremoloGroup(pid, str(m.get("number")), kind, xml_type, marks, level, n, span,
                        [d for d, _ in first], [d for d, _ in second], skip)  # fmt: skip


def _scale_factors(groups: list[TremoloGroup]) -> dict[str, int]:
    """Per part, the smallest integer factor that makes every stroke a whole number of divisions."""
    out: dict[str, int] = {}
    for g in groups:
        if not g.measured:
            continue
        n = round(g.n_strokes)
        need = n // math.gcd(g.span_divs, n)
        if need > 1:
            out[g.part_id] = math.lcm(out.get(g.part_id, 1), need)
    return out


def _scale_part_durations(root: Any, factors: dict[str, int]) -> None:
    for part_el in root.iter("part"):
        f = factors.get(part_el.get("id", "P1"), 1)
        if f == 1:
            continue
        for tag in ("divisions", "duration", "offset"):
            for el in part_el.iter(tag):
                if el.text and el.text.strip():
                    el.text = str(int(round(float(el.text) * f)))


def load_musicxml_expanded(path: Path | str, expand: bool = True) -> tuple[Any, TremoloReport]:
    """Load a MusicXML score with partitura and expand its measured tremolos.

    Same as ``partitura.load_score(path)`` (note ids kept) when the score has no tremolo, and the
    divisions are only rescaled when a stroke needs it. ``expand=False`` loads it unchanged and
    only reports what would be expanded. Returns the partitura ``Score`` and a
    :class:`TremoloReport`.
    """
    root = read_musicxml_root(path)
    groups = read_tremolos(root)
    factors = _scale_factors(groups) if expand else {}
    if factors:
        _scale_part_durations(root, factors)
        for g in groups:
            g.span_divs *= factors.get(g.part_id, 1)
        buf = io.BytesIO(etree.tostring(root, xml_declaration=True, encoding="UTF-8"))
        score = pt.load_musicxml(buf, force_note_ids="keep")
    else:
        score = pt.load_score(str(path))
    if not expand:
        rep = TremoloReport(n_groups=len(groups))
        rep.kept.update("not expanded (expand=False)" for _ in groups)
        return score, rep
    rep = expand_tremolos(score, groups)
    rep.scale = factors
    return score, rep


def _notes_by_doc_order(part: Any) -> dict[int, Any]:
    out: dict[int, Any] = {}
    seen: set[int] = set()
    for n in part.iter_all(pt.score.GenericNote, include_subclasses=True):
        if id(n) in seen:
            continue
        seen.add(id(n))
        if getattr(n, "doc_order", None) is not None:
            out[int(n.doc_order)] = n
    return out


def _copy_note(n: Any, new_id: str) -> Any:
    return pt.score.Note(step=n.step, octave=n.octave, alter=n.alter, id=new_id, voice=n.voice,
                         staff=n.staff, doc_order=n.doc_order,
                         stem_direction=n.stem_direction)  # fmt: skip


def _drop_tremolo_mark(n: Any) -> None:
    if n.ornaments:
        n.ornaments = [o for o in n.ornaments if o != "tremolo"] or None


def _mark_tremolo(n: Any) -> None:
    orn = list(n.ornaments or [])
    if "tremolo" not in orn:
        orn.append("tremolo")
    n.ornaments = orn


def expand_tremolos(score: Any, groups: list[TremoloGroup]) -> TremoloReport:
    """Rewrite the parts of a partitura ``Score`` loaded from the MusicXML that ``groups`` came
    from (:func:`read_tremolos`): measured tremolos become their strokes, the rest keep their
    written notes with the ``"tremolo"`` mark on every chord note. In place; returns the counts.

    The strokes split the written span evenly (an integer number of divisions each, see
    :func:`load_musicxml_expanded`); a stroke that would not be whole is not expanded.
    """
    rep = TremoloReport(n_groups=len(groups))
    parts = {p.id: p for p in pt.score.iter_parts(getattr(score, "parts", score))}
    cache: dict[str, dict[int, Any]] = {}
    for g in groups:
        part = parts.get(g.part_id)
        if part is None:
            rep.kept["part not loaded"] += 1
            continue
        by_doc = cache.setdefault(g.part_id, _notes_by_doc_order(part))
        first = [by_doc.get(d) for d in g.first]
        second = [by_doc.get(d) for d in g.second]
        members = first + second
        if any(n is None or not isinstance(n, pt.score.Note) for n in members):
            rep.kept["note not found"] += 1
            continue
        skip = g.skip
        if not skip:
            s = first[0].start.t
            end = (second[0] if second else first[0]).end.t
            n_str = round(g.n_strokes)
            span = end - s
            if any(n.start.t != s for n in first) or (
                second and any(n.start.t != first[0].end.t for n in second)
            ):
                skip = "chord notes not aligned"
            elif span <= 0 or span % n_str:
                skip = "stroke not a whole number of divisions"
        if skip:
            rep.kept[skip] += 1
            for n in members:
                _mark_tremolo(n)
            continue
        d = span // n_str
        layers = [first, second] if second else [first]
        count: Counter = Counter()
        for k in range(n_str):
            layer = layers[k % len(layers)]
            for n in layer:
                if k < len(layers):  # the written note itself becomes this stroke
                    part.remove(n)
                    _drop_tremolo_mark(n)
                    part.add(n, s + k * d, s + (k + 1) * d)
                else:
                    count[n.id] += 1
                    c = _copy_note(n, f"{n.id}tr{count[n.id]}")
                    part.add(c, s + k * d, s + (k + 1) * d)
                    rep.n_notes_added += 1
        rep.n_expanded += 1
    return rep
