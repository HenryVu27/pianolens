"""Thin input adapters so :mod:`pianolens.align` accepts partitura objects, file paths, note
arrays, or the project's common types (``pianolens.data.types``) without importing them.

The common types are duck-typed on purpose: this module must not depend on the loader code
that another agent owns. Anything with a ``.part`` / ``.score`` attribute is unwrapped as a
score; anything with a ``.note_array`` (array or method) is read as a performance.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import numpy as np
import partitura as pt

from pianolens.align.tremolo import MUSICXML_SUFFIXES, load_musicxml_expanded

_PERF_FIELDS = ("onset_sec", "duration_sec", "pitch", "id")
_LOG = logging.getLogger(__name__)

EXPAND_TREMOLOS = True
"""Default of ``to_part(expand_tremolos=...)`` (BL-26). A switch for before/after measurements."""

SPLIT_WIDE_UPPER_CHORDS = True
"""Default of ``to_part(split_wide_chords=...)`` (BL-33). A switch for before/after measurements."""

MAX_HAND_SPAN = 12
"""Semitones one hand is taken to cover at one onset (an octave), for BL-33's chord split."""

MIN_SPLIT_GAP = 8
"""Smallest pitch gap (semitones) inside an upper-staff chord at which BL-33 splits it."""

STAFF_MARGIN_WARN = 1.0
"""DF-09 in-between staff: warn when its mean pitch is within this many semitones of the
midpoint of the two main staves (Chopin Op. 29's "Flauta" part: 0.11)."""

LOAD_NOTES_ATTR = "pianolens_load_notes"


def load_notes(part: Any) -> list[str]:
    """Notes :func:`to_part` recorded while building ``part`` (tremolos expanded, chord notes
    moved to the lower staff, fragile staff choices). ``align`` copies them to the aligned
    score's ``meta["load_notes"]``."""
    return list(getattr(part, LOAD_NOTES_ATTR, None) or [])


def _add_load_note(part: Any, msg: str) -> None:
    notes = getattr(part, LOAD_NOTES_ATTR, None)
    if notes is None:
        notes = []
        setattr(part, LOAD_NOTES_ATTR, notes)
    if msg not in notes:
        notes.append(msg)


_STAFFED = (pt.score.GenericNote, pt.score.Clef, pt.score.Words, pt.score.Direction)


def _set_staves(part: Any, mapping: dict[int, int]) -> None:
    # collect first: an object can match several classes, and a mapping must apply only once
    objs = {id(e): e for e in part.iter_all(_STAFFED, include_subclasses=True)}
    for e in objs.values():
        st = getattr(e, "staff", None)
        if st is not None and int(st) in mapping:
            e.staff = mapping[int(st)]


def _number_parts_consecutively(parts: list[Any]) -> None:
    """Give each part's staves global numbers in part order (part 1: 1..n1, part 2: n1+1..).
    ``merge_parts`` (reassign="voice") keeps staff numbers, so one-staff-per-part scores would
    otherwise merge onto staff 1."""
    offset = 0
    for p in parts:
        staves = sorted({int(n.staff) if n.staff is not None else 1 for n in p.notes_tied})
        if not staves:
            continue
        _set_staves(p, {s: offset + k + 1 for k, s in enumerate(staves)})
        for n in p.iter_all(pt.score.GenericNote, include_subclasses=True):
            if n.staff is None:
                n.staff = offset + 1
        offset += len(staves)


def normalise_piano_staves(part: Any) -> dict[int, int]:
    """Renumber a merged piano part's staves to 1 (upper) and 2 (lower), in place (DF-09).

    Hand synchrony and the even-run streams read staff 1 as the upper and staff 2 as the lower
    staff; some scores number them 3/4, 2/3 or 1/3, or add small extra staves. Rule:

    - One staff: unchanged (1).
    - Two staves: the lower number (the upper staff on the page) -> 1, the other -> 2.
    - Three or more: the two staves with the most notes are the main pair (ties: lower number
      first); the one printed higher -> 1, the other -> 2. Any other staff printed above the
      pair -> 1, below it -> 2, between them -> the main staff whose mean pitch is nearer.
      When that staff's mean pitch is within ``STAFF_MARGIN_WARN`` semitones of the midpoint of
      the two main staves, the choice is fragile: a warning is logged and recorded in
      :func:`load_notes` (the rule itself is unchanged).

    Notes, clefs, words and directions are renumbered. Returns the mapping (old -> new).
    """
    notes = list(part.notes_tied)
    count: dict[int, int] = {}
    psum: dict[int, float] = {}
    for n in notes:
        st = int(n.staff) if n.staff is not None else 1
        count[st] = count.get(st, 0) + 1
        psum[st] = psum.get(st, 0.0) + float(n.midi_pitch)
    staves = sorted(count)
    if len(staves) <= 1:
        mapping = {s: 1 for s in staves}
    elif len(staves) == 2:
        mapping = {staves[0]: 1, staves[1]: 2}
    else:
        main = sorted(sorted(staves, key=lambda s: (-count[s], s))[:2])
        up, lo = main
        mean = {s: psum[s] / count[s] for s in staves}
        mapping = {}
        for s in staves:
            if s == up or s < up:
                mapping[s] = 1
            elif s == lo or s > lo:
                mapping[s] = 2
            else:
                mapping[s] = 1 if abs(mean[s] - mean[up]) <= abs(mean[s] - mean[lo]) else 2
                margin = abs(mean[s] - (mean[up] + mean[lo]) / 2)
                if margin < STAFF_MARGIN_WARN:
                    msg = (f"staves: in-between staff {s} (mean pitch {mean[s]:.2f}) joins the "
                           f"{'upper' if mapping[s] == 1 else 'lower'} staff by a margin of "
                           f"{margin:.2f} semitone from the midpoint of staves {up} "
                           f"({mean[up]:.2f}) and {lo} ({mean[lo]:.2f}); hand assignment of its "
                           f"{count[s]} notes is fragile")
                    _LOG.warning(msg)
                    _add_load_note(part, msg)
    if any(k != v for k, v in mapping.items()):
        _set_staves(part, mapping)
    return mapping


def split_wide_upper_chords(
    part: Any, max_span: int = MAX_HAND_SPAN, min_gap: int = MIN_SPLIT_GAP
) -> tuple[int, int]:
    """Move the low notes of too-wide upper-staff chords to the lower staff, in place (BL-33).

    Some encodings write left-hand notes into the upper staff or upper part with no cross-staff
    mark. Chopin's Waltz Op. 64/1 in PianoCoRe (two one-staff parts "rh" / "lh", every note in
    voice 1) puts the left hand's chords in the "rh" part as members of the melody's chords, in 19
    measures (29-33, 45-49, 117-121, 133-136): no staff, voice or cross-staff element marks them.
    Schumann Op. 17 i mm. 41-49 (BL-19b) writes a left-hand voice on the upper staff. Rule:

    Group the upper staff's (staff 1, after :func:`normalise_piano_staves`) non-grace notes by
    onset. A group that spans more than ``max_span`` semitones (more than one hand covers) is
    split at its largest pitch gap, if that gap is at least ``min_gap`` semitones. The notes
    below the gap move to staff 2 when all of these hold:

    - each side spans at most ``max_span``;
    - with the lower staff's notes that start at the same onset, the moved notes still span at
      most ``max_span`` (the left hand can take them);
    - the moved notes are in voices that no remaining note of the group uses, or the upper staff
      has a single voice throughout (no voice information, as in the waltz).

    Tied continuations move with their note. Why these conditions: an octave is the usual limit
    for an unrolled chord in one hand; the gap guard keeps close-spaced chords; a low part of a
    one-voice chord in a multi-voice staff is mostly played by the right hand. Checked against
    PianoVAM video hand labels (BL-19b notes, 30 pieces; the conditions were chosen with them in
    view, so this is in-sample): 99.7% of 344 labelled played notes on moved score notes are
    left-hand (98.1% of 53 without Schumann Op. 17 i); same-voice moves in multi-voice staves,
    now excluded, were left-hand for 25% of 20. No voiceless staff in BL-19b had a wide chord, so
    the voiceless case is checked on the waltz only. Returns (notes moved, chords split).
    """
    notes = [n for n in part.notes_tied if not isinstance(n, pt.score.GraceNote)]
    upper_voices = {n.voice for n in notes if n.staff is None or int(n.staff) == 1}
    voiceless = len(upper_voices) <= 1
    upper: dict[int, list[Any]] = {}
    lower: dict[int, list[int]] = {}
    for n in notes:
        st = int(n.staff) if n.staff is not None else 1
        if st == 1:
            upper.setdefault(n.start.t, []).append(n)
        elif st == 2:
            lower.setdefault(n.start.t, []).append(int(n.midi_pitch))
    if not upper or not lower:
        return 0, 0
    moved = chords = 0
    for t, chord in upper.items():
        ps = sorted(int(n.midi_pitch) for n in chord)
        if ps[-1] - ps[0] <= max_span:
            continue
        gaps = np.diff(ps)
        k = int(np.argmax(gaps))
        if gaps[k] < min_gap:
            continue
        low, up = ps[: k + 1], ps[k + 1 :]
        if up[-1] - up[0] > max_span or low[-1] - low[0] > max_span:
            continue
        lh = lower.get(t, [])
        if lh and max(lh + low) - min(lh + low) > max_span:
            continue
        move = [n for n in chord if int(n.midi_pitch) <= low[-1]]
        stay_voices = {n.voice for n in chord if int(n.midi_pitch) > low[-1]}
        if not voiceless and stay_voices & {n.voice for n in move}:
            continue
        for n in move:
            x = n
            while x is not None:
                x.staff = 2
                x = x.tie_next
        moved += len(move)
        chords += 1
    return moved, chords


def _merged_part(score: Any) -> Any:
    if isinstance(score, pt.score.Part):
        normalise_piano_staves(score)
        return score
    parts = score.parts if hasattr(score, "parts") else score
    if len(parts) == 1 and isinstance(parts[0], pt.score.Part):
        normalise_piano_staves(parts[0])
        return parts[0]
    _number_parts_consecutively(list(parts))
    merged = pt.score.merge_parts(parts)
    normalise_piano_staves(merged)
    return merged


def to_part(
    score: Any, *, expand_tremolos: bool | None = None, split_wide_chords: bool | None = None
) -> Any:
    """Return a single merged partitura ``Part`` from a score-like input.

    This is the one place every aligned score is built (``align_performance`` re-reads the score
    file through it), so every consumer sees the same score:

    - **Tremolos** (BL-26): a MusicXML file has its measured tremolo abbreviations written out
      (:mod:`pianolens.align.tremolo`). Only a file path can be expanded; partitura objects
      passed in have lost the tremolo type and marks.
    - **Staves** are numbered upper = 1, lower = 2 (:func:`normalise_piano_staves`, DF-09;
      multi-part scores first get consecutive staff numbers in part order), so tier B's hand
      synchrony and even runs see the same numbering for every score.
    - **Left-hand chords written in the upper staff** move to the lower staff
      (:func:`split_wide_upper_chords`, BL-33).

    What changed is recorded on the part (:func:`load_notes`). ``expand_tremolos`` /
    ``split_wide_chords`` default to ``EXPAND_TREMOLOS`` / ``SPLIT_WIDE_UPPER_CHORDS``. A
    partitura ``Part`` or ``Score`` passed in is changed in place.
    """
    expand = EXPAND_TREMOLOS if expand_tremolos is None else expand_tremolos
    split = SPLIT_WIDE_UPPER_CHORDS if split_wide_chords is None else split_wide_chords
    notes: list[str] = []
    if isinstance(score, str | Path):
        path = Path(score)
        if expand and path.suffix.lower() in MUSICXML_SUFFIXES:
            score, rep = load_musicxml_expanded(path)
            if rep.n_groups:
                notes.append(rep.describe())
        else:
            score = pt.load_score(str(path))
    if isinstance(score, pt.score.Part | pt.score.Score | pt.score.PartGroup | list):
        part = _merged_part(score)
        for msg in notes:
            _add_load_note(part, msg)
        if split:
            moved, chords = split_wide_upper_chords(part)
            if moved:
                _add_load_note(part, f"hands: {moved} notes of {chords} upper-staff chords wider "
                                     "than an octave moved to the lower staff")  # fmt: skip
        return part
    kw = {"expand_tremolos": expand, "split_wide_chords": split}
    # pianolens.data.types.Score: prefer the source file (folded, so repeats can be chosen)
    src = getattr(score, "source_path", None)
    if src is not None and Path(src).is_file():
        return to_part(Path(src), **kw)
    for attr in ("part", "score", "partitura_score"):
        inner = getattr(score, attr, None)
        if inner is not None and inner is not score:
            return to_part(inner, **kw)
    raise TypeError(
        f"cannot read a score from {type(score).__name__}; a pianolens Score needs a "
        "source_path or a kept partitura part (keep_part=True)"
    )


def to_performance_note_array(performance: Any) -> np.ndarray:
    """Return a performance note array with at least ``onset_sec, duration_sec, pitch, id``."""
    if isinstance(performance, str | Path):
        performance = pt.load_performance_midi(str(performance))
    if isinstance(performance, np.ndarray):
        na = performance
    elif isinstance(getattr(performance, "notes", None), np.ndarray):
        na = performance.notes  # pianolens.data.types.Performance
    else:
        attr = getattr(performance, "note_array", None)
        if attr is None:
            for name in ("performance", "performed_part", "partitura_performance"):
                inner = getattr(performance, name, None)
                if inner is not None and inner is not performance:
                    return to_performance_note_array(inner)
            raise TypeError(f"cannot read a performance from {type(performance).__name__}")
        na = attr() if callable(attr) else attr
    missing = [f for f in _PERF_FIELDS if f not in (na.dtype.names or ())]
    if missing:
        raise ValueError(f"performance note array lacks fields {missing}")
    return na
