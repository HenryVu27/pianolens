"""Piano four-hands (duet) scores, detected from the score's structure (DF-11).

A duet has two players at one keyboard, each written on a two-staff system (primo and secondo).
PianoLens assigns hands by staff (upper staff = right hand; ``align._adapters.
normalise_piano_staves``, DF-09). For a duet that rule keeps the two fullest of four staves as
the "hands" and splits the four real hands arbitrarily, so hand synchrony between "left" and
"right" hand has no meaning. Reports on duets therefore leave out every per-hand output
(currently hand synchrony, the ``hand_async_*`` values) and say why; everything else treats the
two players' notes as one performance.

Detection reads the MusicXML itself (``.mxl``, ``.musicxml``, ``.xml``), not the merged partitura
part, because merging erases the part structure. Rules, in order:

1. **Structure** (``evidence="structure"``): at least ``MIN_FULL_STAVES`` (4) staves are *full*.
   A staff is full when it belongs to a part written on two or more staves and holds a pitched,
   non-grace, non-cue note in at least ``MIN_BAR_SHARE`` (half) of that part's written bars.
   Two parts of two full staves each, or one part of four, qualify. Solo scores with an extra
   part fail it: an ossia or climax system (Rachmaninoff Op. 3/2: 17 of 62 bars), single-staff
   parts per hand or per voice (Bach inventions and fugues, a part named "Flauta" in Chopin
   Op. 29), or a few cue bars (Scriabin Op. 53, Ravel *Ondine*).
2. **Part names** (``evidence="part names"``): two or more parts whose name or abbreviation
   starts with primo, prima, secondo or seconda. "Piano 1" / "Piano 2" alone is not evidence:
   the catalogue's Chopin Op. 15/3 is a solo score with parts "Piano" and "Piano 2".
3. **Known list** (``evidence="known list"``): ``KNOWN_FOUR_HANDS`` piece ids, a fallback used
   only when rules 1 and 2 do not fire, meant for score files whose structure cannot be read
   (other formats, unreadable files). The three catalogue duets that DF-11 names are all found
   by rule 1, so the list is not needed for them.

On the app catalogue (805 scores, 2026-10-10) rule 1 finds exactly the three duets: Fauré
Op. 56/1, Dvořák Op. 72/2 and Ravel *Ma mère l'Oye* 5 (``tests/report/test_four_hands.py``).
"""

from __future__ import annotations

import io
import re
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

__all__ = ["KNOWN_FOUR_HANDS", "MIN_BAR_SHARE", "MIN_FULL_STAVES", "FourHands", "PartLayout",
           "classify", "detect_four_hands", "read_layout"]  # fmt: skip

MIN_BAR_SHARE = 0.5
MIN_FULL_STAVES = 4
#: Fallback only (rule 3): piece ids of known duets, used when the score cannot be read.
KNOWN_FOUR_HANDS: frozenset[str] = frozenset({
    "faure_op56_mv1",
    "dvorak_op72_no2",
    "pianocore:Ravel,_Maurice/Ma_mère_l'Oye,_M.60/5._Le_jardin_féerique",
})  # fmt: skip
#: Per-hand outputs that a four-hands report leaves out (control summary keys).
PER_HAND_KEYS: tuple[str, ...] = ("hand_async_mean_ms", "hand_async_median_ms", "hand_async_sd_ms",
                                  "hand_async_vel_slope_ms", "hand_async_resid_sd_ms")  # fmt: skip
_DUET_NAME = re.compile(r"^\s*(primo|prima|secondo|seconda)\b", re.IGNORECASE)
_XML_SUFFIXES = (".mxl", ".musicxml", ".xml")


@dataclass(frozen=True)
class PartLayout:
    """One MusicXML part: its names, written bars, and bars with notes per staff."""

    part_id: str
    name: str = ""
    abbreviation: str = ""
    n_bars: int = 0
    staff_bars: dict[int, int] = field(default_factory=dict)  # staff -> bars with notes


@dataclass(frozen=True)
class FourHands:
    """Result of :func:`detect_four_hands`.

    ``evidence``: ``"structure"``, ``"part names"``, ``"known list"`` or ``""`` (solo).
    ``n_full_staves``: staves counted by rule 1 (-1 when the layout could not be read, 0 when
    ``quick`` skipped the full read).
    """

    is_four_hands: bool
    evidence: str = ""
    part_names: tuple[str, ...] = ()
    n_full_staves: int = -1

    def as_report(self) -> dict[str, Any] | None:
        """The record stored in a report (``piece.four_hands``), or None for a solo score."""
        if not self.is_four_hands:
            return None
        return {"evidence": self.evidence, "part_names": list(self.part_names),
                "n_full_staves": self.n_full_staves, "skipped": list(PER_HAND_KEYS)}


def _musicxml_bytes(src: Path | str | bytes) -> bytes | None:
    """The score's MusicXML document (unzipped for ``.mxl``), or None for other formats."""
    if isinstance(src, bytes):
        data = src
    else:
        p = Path(src)
        if p.suffix.lower() not in _XML_SUFFIXES or not p.is_file():
            return None
        data = p.read_bytes()
    if data[:2] != b"PK":
        return data
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        names = z.namelist()
        root = None
        if "META-INF/container.xml" in names:
            rf = ET.fromstring(z.read("META-INF/container.xml")).find(".//{*}rootfile")
            root = rf.get("full-path") if rf is not None else None
        if root is None:
            cand = [n for n in names if n.lower().endswith((".xml", ".musicxml"))
                    and not n.startswith("META-INF")]  # fmt: skip
            if not cand:
                return None
            root = cand[0]
        return z.read(root)


_PART_TAG = re.compile(rb"<part\s[^>]*>")
_STAFF_NUM = re.compile(rb"<staff>\s*(\d+)\s*</staff>|<staves>\s*(\d+)\s*</staves>")


def _quick_layout(xml: bytes) -> list[PartLayout] | None:
    """Part names only, when rule 1 cannot fire: fewer than two parts use two or more staves and
    no part uses ``MIN_FULL_STAVES``, judged by a byte scan of ``<staff>`` / ``<staves>``. None
    when a full read is needed."""
    starts = [m.end() for m in _PART_TAG.finditer(xml)]
    most = []
    for i, a in enumerate(starts):
        b = starts[i + 1] if i + 1 < len(starts) else len(xml)
        nums = [int(x or y) for x, y in _STAFF_NUM.findall(xml, a, b)]
        most.append(max(nums, default=1))
    if sum(1 for k in most if k >= 2) >= 2 or any(k >= MIN_FULL_STAVES for k in most):
        return None
    out = []
    for _, el in ET.iterparse(io.BytesIO(xml), events=("end",)):
        if el.tag == "score-part":
            out.append(PartLayout(el.get("id", ""), (el.findtext("part-name") or "").strip(),
                                  (el.findtext("part-abbreviation") or "").strip()))
        elif el.tag == "part-list":
            break
    return out


def read_layout(src: Path | str | bytes) -> list[PartLayout] | None:
    """Parts of a MusicXML score with bars-with-notes per staff; None if not MusicXML."""
    xml = _musicxml_bytes(src)
    if xml is None:
        return None
    names: dict[str, tuple[str, str]] = {}
    out = []
    for _, el in ET.iterparse(io.BytesIO(xml), events=("end",)):
        if el.tag == "score-part":
            names[el.get("id", "")] = ((el.findtext("part-name") or "").strip(),
                                       (el.findtext("part-abbreviation") or "").strip())
        elif el.tag == "part":
            pid = el.get("id", "")
            n_bars, staff_bars = 0, {}
            for m in el.iter("measure"):
                n_bars += 1
                seen = set()
                for n in m.iter("note"):
                    if n.find("pitch") is None or n.find("grace") is not None \
                            or n.find("cue") is not None:
                        continue
                    seen.add(int(n.findtext("staff") or 1))
                for s in seen:
                    staff_bars[s] = staff_bars.get(s, 0) + 1
            nm, ab = names.get(pid, ("", ""))
            out.append(PartLayout(pid, nm, ab, n_bars, staff_bars))
            el.clear()
    return out


def classify(parts: list[PartLayout]) -> tuple[bool, str, int]:
    """Rules 1 and 2 on a layout: ``(is_four_hands, evidence, n_full_staves)``."""
    full = 0
    for p in parts:
        if len(p.staff_bars) >= 2 and p.n_bars:
            full += sum(1 for v in p.staff_bars.values() if v >= MIN_BAR_SHARE * p.n_bars)
    if full >= MIN_FULL_STAVES:
        return True, "structure", full
    named = sum(1 for p in parts if _DUET_NAME.match(p.name) or _DUET_NAME.match(p.abbreviation))
    if named >= 2:
        return True, "part names", full
    return False, "", full


def detect_four_hands(score: Path | str | bytes | None, piece_id: str | None = None,
                      quick: bool = False) -> FourHands:
    """Is this a piano four-hands score? Never raises.

    ``score``: a MusicXML file (path or bytes); other formats or None fall back to the known
    list. ``quick``: skip the full read when a byte scan of the staff numbers shows that rule 1
    cannot fire (the catalogue build); the answer is the same, only faster.
    """
    parts = None
    try:
        if score is not None:
            xml = _musicxml_bytes(score)
            if xml is not None and quick:
                parts = _quick_layout(xml)
            if xml is not None and parts is None:
                parts = read_layout(xml)
    except (OSError, ET.ParseError, zipfile.BadZipFile, ValueError, KeyError):
        parts = None
    if parts:
        ok, ev, full = classify(parts)
        names = tuple(p.name or p.abbreviation or p.part_id for p in parts)
        if ok:
            return FourHands(True, ev, names, full)
    else:
        names, full = (), (-1 if parts is None else 0)
    if piece_id is not None and str(piece_id) in KNOWN_FOUR_HANDS:
        return FourHands(True, "known list", names, full)
    return FourHands(False, "", names, full)
