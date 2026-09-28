"""DCML J. C. Bach keyboard sonatas: label-free scores plus phrase and cadence tables (D-12).

Source: https://github.com/DCMLab/jc_bach_sonatas (v2.4, commit ``COMMIT``) under
``data/raw/dcml_jc_bach``, license CC BY-NC-SA 4.0. Op. 5 and op. 17: 12 sonatas, 29
movements. Score-only corpus: no performances.

Label-free score path
---------------------
The corpus ships MuseScore 3 files (``MS3/*.mscx``) with the DCML harmony, cadence and phrase
labels embedded as ``<Harmony>`` elements, plus ms3-exported TSV facets. There is no MusicXML
and no MuseScore binary on this machine, so partitura's ``load_musescore`` is not usable.
:func:`load_score` instead builds a partitura ``Part`` from three facets only:

* ``notes/<stem>.notes.tsv``: every note head (pitch spelling, onset, duration, staff, voice,
  ties, grace notes);
* ``measures/<stem>.measures.tsv``: measure lengths, time and key signatures, repeat structure
  (``next``), barlines;
* ``chords/<stem>.chords.tsv``: dynamics (``Dynamic`` events) and staff text (``StaffText``).

These facets carry no harmony labels (the labels are only in ``harmonies/`` and the
``.mscx``), and the loader never opens ``harmonies/``, ``reviewed/`` or ``MS3/`` for a score
(:data:`LABEL_FREE_FACETS`, ``Score.meta["source_files"]``). The movement title of
``metadata.tsv`` (e.g. "Allegretto") is added as a tempo word at the first onset, as a printed
score shows it (``tempo_word=False`` drops it).

Differences from an engraved score (not in the three facets): no fermatas (15 in the
``.mscx``, in 8 movements), no hairpins (the few ``crescendo_line`` rows are not read), no
printed rests (:func:`load_score` derives rests
as the gaps in each staff, ``meta["rests"] = "derived"``), no key mode (the key signature has
``mode=None``). Ties are merged. ``unfold=True`` writes repeats out along the ``next`` column
(first visit takes the first target, the second visit the second, ``-1`` ends); the unfolded
bar count and length equal ``metadata.tsv`` for all 29 movements (tested). Note ids are
``n<row>`` (row of the notes TSV of the first tied head) with an ``-<k>`` suffix for the
k-th pass (1-based) when unfolded, like partitura's unfolded ids.

Phrase and cadence tables
-------------------------
:func:`phrase_annotations` reads ``harmonies/`` (``phraseend`` and ``cadence`` columns) and
maps every label (``mc``, ``mc_onset``) to the beat of each pass of that measure in the score,
returning a ``batik_mozart.PhraseAnnotations`` so R-08a's scoring functions apply unchanged.
``{`` starts a phrase, ``}`` ends one, ``}{`` both. The three ``\\\\`` labels in the corpus
are not a start or end and are dropped (counted in ``n_other``). Cadences: PAC, IAC, HC, EC, DC,
PC (plagal). Labels whose position is not a note onset keep their exact beat (counted in
``n_off_onset``); ``id`` is the lowest note starting there, or ``""``.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from fractions import Fraction
from math import lcm
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from pianolens.data.batik_mozart import PHRASE_LABELS, PhraseAnnotations
from pianolens.data.piece_ids import make_piece_id
from pianolens.data.types import PieceId, Score, score_from_partitura

log = logging.getLogger(__name__)

DATASET = "dcml_jc_bach"
DEFAULT_ROOT = Path(__file__).resolve().parents[3] / "data" / "raw" / "dcml_jc_bach"
COMMIT = "ac9fd07905eb62c3d8cfbd96811491170a216232"  # tag v2.4, 2025-04-27
LICENSE = "CC BY-NC-SA 4.0"
LABEL_FREE_FACETS = ("notes", "measures", "chords")
LABEL_FACETS = ("harmonies",)
CADENCE_TYPES = ("PAC", "IAC", "HC", "EC", "DC", "PC")
# columns of harmonies/*.tsv that hold label text (used by the leakage checks)
LABEL_TEXT_COLUMNS = ("label", "globalkey", "localkey", "pedal", "chord", "numeral", "form",
                      "figbass", "changes", "relativeroot", "cadence", "phraseend",
                      "chord_type", "chord_tones", "added_tones", "special", "pedalend",
                      "regex_match")


def data_available(root: Path | str = DEFAULT_ROOT) -> bool:
    return (Path(root) / "notes").is_dir() and (Path(root) / "metadata.tsv").is_file()


def metadata(root: Path | str = DEFAULT_ROOT) -> pd.DataFrame:
    return pd.read_csv(Path(root) / "metadata.tsv", sep="\t", dtype=str)


def pieces(root: Path | str = DEFAULT_ROOT) -> list[str]:
    """Movement stems, e.g. ``wa01op05no1a_Allegretto`` (29)."""
    return sorted(metadata(root)["piece"])


def piece_id(stem: str) -> PieceId:
    """``wa02op05no2b_Andante_di_molto`` -> ``jcbach_op5_no2_mv2``."""
    m = re.fullmatch(r"wa\d+op(\d+)no(\d+)([a-z])", stem.split("_")[0])
    if m is None:
        raise ValueError(f"unexpected stem {stem!r}")
    op, no, mv = int(m[1]), int(m[2]), ord(m[3]) - ord("a") + 1
    return make_piece_id("JC Bach", f"op{op}", no, mv)


def _frac(x: Any) -> Fraction:
    if isinstance(x, float) and np.isnan(x):
        return Fraction(0)
    return Fraction(str(x).strip())


def read_facet(stem: str, facet: str, root: Path | str = DEFAULT_ROOT) -> pd.DataFrame:
    path = Path(root) / facet / f"{stem}.{facet}.tsv"
    return pd.read_csv(path, sep="\t", dtype=str, keep_default_na=False)


def _read_label_free(stem: str, facet: str, root: Path | str, used: list[str]) -> pd.DataFrame:
    if facet not in LABEL_FREE_FACETS:
        raise ValueError(f"{facet!r} is not a label-free facet {LABEL_FREE_FACETS}")
    used.append(f"{facet}/{stem}.{facet}.tsv")
    return read_facet(stem, facet, root)


# --------------------------------------------------------------------------- unfolding


def playthrough(measures: pd.DataFrame, unfold: bool = True) -> list[int]:
    """Measure counts (``mc``) in playing order. ``unfold=False``: each ``mc`` once."""
    mcs = [int(x) for x in measures["mc"]]
    if not unfold:
        return mcs
    nxt = {int(r["mc"]): [int(v) for v in str(r["next"]).split(",") if v.strip()]
           for _, r in measures.iterrows()}
    visits: dict[int, int] = {}
    out, mc = [], mcs[0]
    while mc != -1:
        out.append(mc)
        visits[mc] = visits.get(mc, 0) + 1
        if len(out) > 20 * len(mcs):
            raise RuntimeError("unfolding does not terminate")
        targets = nxt.get(mc) or [-1]
        mc = targets[min(visits[mc] - 1, len(targets) - 1)]
    return out


# --------------------------------------------------------------------------- score


@dataclass
class _Pass:
    mc: int
    k: int  # pass number of this mc (1-based)
    start: Fraction  # quarters
    length: Fraction  # quarters


def _passes(measures: pd.DataFrame, order: list[int]) -> list[_Pass]:
    act = {int(r["mc"]): _frac(r["act_dur"]) * 4 for _, r in measures.iterrows()}
    seen: dict[int, int] = {}
    out, t = [], Fraction(0)
    for mc in order:
        seen[mc] = seen.get(mc, 0) + 1
        out.append(_Pass(mc, seen[mc], t, act[mc]))
        t += act[mc]
    return out


@dataclass
class _Note:
    id: str
    onset: Fraction
    dur: Fraction
    midi: int
    step: str
    alter: int
    octave: int
    staff: int
    voice: int
    grace: str
    tied: str


def _spelling(name: str) -> tuple[str, int]:
    step, acc = name[0], name[1:].rstrip("-0123456789")
    return step, acc.count("#") - acc.count("b")


def _linear_notes(notes: pd.DataFrame, passes: list[_Pass], suffix: bool
                  ) -> tuple[list[_Note], int]:
    """Notes placed on the linear (unfolded) timeline with ties merged; also the count of
    tie continuations that found no start (kept as notes)."""
    by_mc: dict[int, list[tuple[int, pd.Series]]] = {}
    for i, r in notes.iterrows():
        by_mc.setdefault(int(r["mc"]), []).append((int(i), r))
    raw: list[_Note] = []
    for p in passes:
        for i, r in by_mc.get(p.mc, []):
            step, alter = _spelling(str(r["name"]))
            raw.append(_Note(
                id=f"n{i}" + (f"-{p.k}" if suffix else ""),
                onset=p.start + _frac(r["mc_onset"]) * 4,
                dur=_frac(r["duration"]) * 4 if not r.get("gracenote") else Fraction(0),
                midi=int(r["midi"]), step=step, alter=alter, octave=int(r["octave"]),
                staff=int(r["staff"]), voice=int(r["voice"]),
                grace=str(r.get("gracenote", "") or ""), tied=str(r.get("tied", "") or "")))
    # merge ties: a head with tied 1 / 0 continues into a head with tied 0 / -1 at its end
    cont: dict[tuple[int, int, Fraction], list[int]] = {}
    for j, n in enumerate(raw):
        if n.tied in ("-1", "0"):
            cont.setdefault((n.midi, n.staff, n.onset), []).append(j)
    absorbed: set[int] = set()
    out = []
    for j, n in enumerate(raw):
        if j in absorbed:
            continue
        cur = n
        while cur.tied in ("1", "0"):
            c = [x for x in cont.get((cur.midi, cur.staff, cur.onset + cur.dur), [])
                 if x not in absorbed]
            if not c:
                break
            absorbed.add(c[0])
            nxt = raw[c[0]]
            n.dur += nxt.dur
            cur = nxt
        out.append(n)
    orphans = sum(1 for n in out if n.tied in ("-1", "0"))
    return out, orphans


_GRACE = {"acciaccatura": "acciaccatura"}


def load_score(stem: str, root: Path | str = DEFAULT_ROOT, *, unfold: bool = True,
               tempo_word: bool = True) -> Score:
    """Label-free score of one movement (module docstring), ``part`` kept.

    ``meta``: ``source_files`` (the only files read), ``divs`` (partitura divs per quarter),
    ``playthrough`` (list of ``(mc, pass, start)``; ``start`` is a fraction string in
    quarters from the first onset, not partitura's ``quarter_map``, which puts the first full
    bar at 0), ``unfolded``, ``rests`` ("derived"), ``n_orphan_ties``,
    ``title``.
    """
    import partitura as pt

    root = Path(root)
    used: list[str] = []
    md = metadata(root).set_index("piece").loc[stem]
    used.append("metadata.tsv[piece, movementTitle]")
    ms = _read_label_free(stem, "measures", root, used)
    na = _read_label_free(stem, "notes", root, used)
    ch = _read_label_free(stem, "chords", root, used)
    order = playthrough(ms, unfold)
    passes = _passes(ms, order)
    notes, orphans = _linear_notes(na, passes, suffix=unfold)
    total = passes[-1].start + passes[-1].length

    fracs = [p.start for p in passes] + [p.length for p in passes]
    fracs += [n.onset for n in notes] + [n.dur for n in notes]
    divs = 1
    for f in fracs:
        divs = lcm(divs, f.denominator)

    def T(q: Fraction) -> int:
        v = q * divs
        assert v.denominator == 1
        return int(v)

    part = pt.score.Part("P1", "Piano", quarter_duration=divs)
    mrow = {int(r["mc"]): r for _, r in ms.iterrows()}
    prev_ts, prev_ks = None, None
    for idx, p in enumerate(passes):
        r = mrow[p.mc]
        t0, t1 = T(p.start), T(p.start + p.length)
        part.add(pt.score.Measure(number=idx + 1, name=str(r["mn"])), t0, t1)
        ts = str(r["timesig"])
        if ts != prev_ts:
            b, bt = (int(x) for x in ts.split("/"))
            part.add(pt.score.TimeSignature(b, bt), t0)
            prev_ts = ts
        ks = int(r["keysig"]) if str(r["keysig"]).strip() else 0
        if ks != prev_ks:
            part.add(pt.score.KeySignature(ks, None), t0)
            prev_ks = ks
        # repeat and final barlines, placed as a MusicXML import places them
        rep = str(r.get("repeats", ""))
        if rep in ("start",) and idx > 0:
            part.add(pt.score.Barline("heavy-light"), t0)
        if rep in ("end", "lastMeasure") or str(r.get("barline", "")) in ("end", "double"):
            part.add(pt.score.Barline("light-heavy"), t1)
    for n in notes:
        v = (n.staff - 1) * 4 + n.voice
        if n.grace:
            obj = pt.score.GraceNote(grace_type=_GRACE.get(n.grace, "appoggiatura"),
                                     step=n.step, octave=n.octave, alter=n.alter or None,
                                     id=n.id, voice=v, staff=n.staff)
            part.add(obj, T(n.onset), T(n.onset))
        else:
            obj = pt.score.Note(step=n.step, octave=n.octave, alter=n.alter or None, id=n.id,
                                voice=v, staff=n.staff)
            part.add(obj, T(n.onset), T(n.onset + n.dur))
    # derived rests: gaps in each staff's coverage, split at bar lines
    for staff in (1, 2):
        iv = sorted((n.onset, n.onset + n.dur) for n in notes if n.staff == staff and n.dur > 0)
        for p in passes:
            a, b = p.start, p.start + p.length
            cur = a
            for s, e in iv:
                if e <= cur or s >= b:
                    continue
                if s > cur:
                    part.add(pt.score.Rest(staff=staff), T(cur), T(min(s, b)))
                cur = max(cur, e)
                if cur >= b:
                    break
            if cur < b:
                part.add(pt.score.Rest(staff=staff), T(cur), T(b))
    # dynamics and staff text from the chords facet
    starts_by_mc: dict[int, list[Fraction]] = {}
    for p in passes:
        starts_by_mc.setdefault(p.mc, []).append(p.start)
    for _, r in ch.iterrows():
        ev = r.get("event", "")
        if ev not in ("Dynamic", "StaffText"):
            continue
        txt = str(r.get("dynamics" if ev == "Dynamic" else "staff_text", "") or "").strip()
        if not txt:
            continue
        txt = txt.replace("<b>", "").replace("</b>", "")
        for s in starts_by_mc.get(int(r["mc"]), []):
            t = T(s + _frac(r["mc_onset"]) * 4)
            obj = (pt.score.ConstantLoudnessDirection(txt, staff=int(r["staff"]))
                   if ev == "Dynamic" else pt.score.Words(txt, staff=int(r["staff"])))
            part.add(obj, t)
    title = str(md.get("movementTitle", "") or "").strip()
    if tempo_word and title:
        part.add(pt.score.ConstantTempoDirection(title), 0)
    return score_from_partitura(
        part, score_id=f"{DATASET}:{stem}", piece_id=piece_id(stem),
        source_path=root / "notes" / f"{stem}.notes.tsv",
        meta={"source_files": used, "divs": divs, "unfolded": unfold, "rests": "derived",
              "n_orphan_ties": orphans, "title": title, "commit": COMMIT,
              "length_quarters": float(total),
              "playthrough": [(p.mc, p.k, str(p.start)) for p in passes]},
        keep_part=True)


def iter_scores(root: Path | str = DEFAULT_ROOT, stats: LoadStats | None = None, *,
                unfold: bool = True) -> Iterator[Score]:
    stats = stats if stats is not None else LoadStats()
    for stem in pieces(root):
        try:
            yield load_score(stem, root, unfold=unfold)
            stats.loaded += 1
        except Exception as e:  # noqa: BLE001 - count and continue
            stats.failed += 1
            stats.failures.append((stem, repr(e)))
            log.warning("jc_bach %s failed: %r", stem, e)


@dataclass
class LoadStats:
    loaded: int = 0
    failed: int = 0
    failures: list[tuple[str, str]] = field(default_factory=list)


def stem_of(score_or_id: Any) -> str:
    sid = getattr(score_or_id, "score_id", score_or_id)
    return str(sid).split(":")[-1]


# --------------------------------------------------------------------------- labels


def load_labels(stem: str, root: Path | str = DEFAULT_ROOT) -> pd.DataFrame:
    """The DCML label table (``harmonies/``). Never pass this to a renderer."""
    return read_facet(stem, "harmonies", root)


def label_strings(stem: str, root: Path | str = DEFAULT_ROOT, min_len: int = 1) -> set[str]:
    """Distinct label-text values of the movement (for leakage checks)."""
    df = load_labels(stem, root)
    out: set[str] = set()
    for c in LABEL_TEXT_COLUMNS:
        if c in df.columns:
            out |= {v.strip() for v in df[c].astype(str) if len(v.strip()) >= min_len}
    return out


@dataclass
class DcmlPhraseAnnotations(PhraseAnnotations):
    """``PhraseAnnotations`` plus ``n_off_onset`` (label placements not on a note onset) and
    ``n_other`` (``phraseend`` values other than ``{``, ``}``, ``}{``, dropped)."""

    n_off_onset: int = 0
    n_other: int = 0


def phrase_annotations(score: Score, root: Path | str = DEFAULT_ROOT) -> DcmlPhraseAnnotations:
    """Phrase and cadence tables of ``score`` (from :func:`load_score`, unfolded or not) in its
    beats; a ``batik_mozart.PhraseAnnotations``. ``n_unmapped`` counts labels whose
    measure is not in the playthrough (0 expected)."""
    stem = stem_of(score)
    lab = load_labels(stem, root)
    part = score.part
    bmap, qmap, divs = part.beat_map, part.quarter_map, int(score.meta["divs"])
    starts: dict[int, list[str]] = {}
    for mc, _k, s in score.meta["playthrough"]:
        starts.setdefault(int(mc), []).append(s)
    na = score.notes
    ob = na["onset_beat"].astype(float)
    order = np.lexsort((na["pitch"], ob))
    first_note: dict[float, str] = {}
    for i in order:
        first_note.setdefault(round(float(ob[i]), 6), str(na["id"][i]))
    nm = dict(zip(score.measures["start_quarter"].round(6), score.measures["name"],
                  strict=False))
    mstarts = np.sort(score.measures["start_quarter"])
    unmapped, off = 0, 0
    rows_p, rows_c = [], []
    for _, r in lab.iterrows():
        pe = str(r.get("phraseend", "")).strip()
        cad = str(r.get("cadence", "")).strip()
        if not pe and not cad:
            continue
        ss = starts.get(int(r["mc"]), [])
        if not ss:
            unmapped += 1
            continue
        for s in ss:
            t = (Fraction(s) + _frac(r["mc_onset"]) * 4) * divs
            assert t.denominator == 1, (stem, r["mc"], r["mc_onset"])
            beat, q = float(bmap(int(t))), float(qmap(int(t)))
            key = round(beat, 6)
            nid = first_note.get(key, "")
            off += nid == ""
            mq = mstarts[max(int(np.searchsorted(mstarts, q + 1e-9)) - 1, 0)]
            base = {"id": nid, "beat": beat, "quarter": q,
                    "measure_number": nm.get(round(float(mq), 6), "")}
            if pe:
                rows_p.append({**base, "label": pe})
            if cad:
                rows_c.append({**base, "cadence": cad})
    ph = pd.DataFrame(rows_p, columns=["id", "beat", "quarter", "measure_number", "label"])
    n_other = int((~ph["label"].isin(PHRASE_LABELS)).sum())
    ph = ph[ph["label"].isin(PHRASE_LABELS)].sort_values(["beat", "id"]).reset_index(drop=True)
    ph["is_start"] = ph["label"].map(lambda x: PHRASE_LABELS[x][0]).astype(bool)
    ph["is_end"] = ph["label"].map(lambda x: PHRASE_LABELS[x][1]).astype(bool)
    ca = pd.DataFrame(rows_c, columns=["id", "beat", "quarter", "measure_number", "cadence"])
    ca = ca.sort_values(["beat", "id"]).reset_index(drop=True)
    return DcmlPhraseAnnotations(ph, ca, unmapped, n_off_onset=off, n_other=n_other)
