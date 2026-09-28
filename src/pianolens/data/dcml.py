"""DCML corpora (ms3 TSV layout): label-free scores plus phrase and cadence tables (D-12, D-13).

One loader for every DCMLab corpus that ships ms3 TSV facets. :data:`CORPORA` lists the
registered ones: ``jc_bach`` (D-12, the J. C. Bach sonatas) and the five R-08d Romantic corpora
(D-13): ``chopin_mazurkas``, ``grieg_lyric_pieces``, ``tchaikovsky_seasons``,
``schumann_kinderszenen``, ``liszt_pelerinage``. Each lives in ``data/raw/dcml_<name>`` (a
sparse clone of the release tag in :class:`Corpus`), license CC BY-NC-SA 4.0. Score-only: no
performances. ``pianolens.data.dcml_jc_bach`` is a thin wrapper around this module.

Label-free score path
---------------------
The corpora ship MuseScore files (``MS3/*.mscx``, not downloaded for D-13) with the DCML
harmony, cadence and phrase labels embedded, plus ms3-exported TSV facets. :func:`load_score`
builds a partitura ``Part`` from three facets only:

* ``notes/<stem>.notes.tsv``: every note head (pitch spelling, onset, duration, staff, voice,
  ties, grace notes; ``octave`` / ``midi`` are sounding pitch, ottavas applied);
* ``measures/<stem>.measures.tsv``: measure lengths, time and key signatures, repeat
  structure (``next``, ``markers``, ``jump_bwd``, ``play_until``), barlines;
* ``chords/<stem>.chords.tsv``: dynamics, staff and system text, tempo marks and (for the
  Romantic corpora, :attr:`Corpus.spanners`) hairpins and text lines.

These facets carry no harmony labels (the labels are only in ``harmonies/`` and the
``.mscx``), and the loader never opens ``harmonies/``, ``reviewed/`` or ``MS3/`` for a score
(:data:`LABEL_FREE_FACETS`, ``Score.meta["source_files"]``). Column sets differ between
corpora and files (e.g. ``volta``, ``tremolo``, ``lyrics_1``, ``Ottava:8va``,
``HairPin:2_poco cresc.``), so every optional column is read with ``.get``.

Text: markup (``<font .../>``, ``<i>``, ``<b>``) and private-use glyphs are stripped; texts
with no letter or digit (``♮``, ``.``) are dropped. Two spellings that R-08a's leakage check
reads as labels are normalised (:func:`clean_text`): "Tempo I" / "Temp. I." -> "Tempo primo"
(a Roman numeral otherwise) and Liszt's "una chorda" / "tres chorde" -> "una corda" /
"tres corde" ("chord" otherwise). ``lyrics_1`` is never read.

Tempo: ``jc_bach`` puts the ``metadata.tsv`` movement title (e.g. "Allegretto") at the first
onset, as D-12 did. The Romantic corpora instead use the ``Tempo`` events of the chords facet
(tempo words and metronome marks, the latter spelled e.g. ``quarter=144``), because their
movement titles name the piece ("Träumerei", "Gondoliera"). ``tempo_word=False`` drops both.

Differences from an engraved score: no fermatas, no slurs, no pedal marks, no printed rests
(derived as the gaps in each staff, ``meta["rests"] = "derived"``), no key mode
(``KeySignature(mode=None)``). Ties are merged. ``unfold=True`` writes repeats out along the
``next`` column (first visit takes the first target, the second the second, ``-1`` ends). Two
Chopin mazurkas carry a *dal segno* that ms3 itself does not unfold (metadata
``last_mc_unfolded`` is empty): after a backward jump (``jump_bwd``) with ``play_until``
``fine`` the loader takes the ending that holds the ``fine`` and stops after it (op. 17/3),
and it stops at the jump measure if that is reached again (*senza fine*, op. 7/5).
``meta["unfold_validated"]`` says whether the unfolded bar count and length equal
``metadata.tsv``. Note ids are ``n<row>`` (row
of the notes TSV of the first tied head) with ``-<k>`` for the k-th pass when unfolded.

Phrase and cadence tables
-------------------------
:func:`phrase_annotations` reads ``harmonies/`` (``phraseend`` and ``cadence``) and maps
every label (``mc``, ``mc_onset``) to the beat of each pass of that measure, via divs
(``t = quarters * divs``, then ``beat_map``; never ``inv_quarter_map``, which is off by the
anacrusis). It returns a ``batik_mozart.PhraseAnnotations`` so R-08a's scoring functions
apply unchanged. ``{`` starts a phrase, ``}`` ends one, ``}{`` both; the deprecated ``\\\\``
is dropped (``n_other``). Cadences: PAC, IAC, HC, EC, DC, PC.
"""

from __future__ import annotations

import html
import logging
import re
import unicodedata
from collections.abc import Callable, Iterator
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

RAW = Path(__file__).resolve().parents[3] / "data" / "raw"
LICENSE = "CC BY-NC-SA 4.0"
LABEL_FREE_FACETS = ("notes", "measures", "chords")
LABEL_FACETS = ("harmonies",)
CADENCE_TYPES = ("PAC", "IAC", "HC", "EC", "DC", "PC")
# columns of harmonies/*.tsv that hold label text (used by the leakage checks)
LABEL_TEXT_COLUMNS = ("label", "alt_label", "globalkey", "localkey", "pedal", "chord",
                      "numeral", "form", "figbass", "changes", "relativeroot", "cadence",
                      "phraseend", "chord_type", "chord_tones", "added_tones", "special",
                      "pedalend", "regex_match")


# --------------------------------------------------------------------------- piece ids


def _jc_bach_id(stem: str) -> PieceId:
    """``wa02op05no2b_Andante_di_molto`` -> ``jcbach_op5_no2_mv2``."""
    m = re.fullmatch(r"wa\d+op(\d+)no(\d+)([a-z])", stem.split("_")[0])
    if m is None:
        raise ValueError(f"unexpected stem {stem!r}")
    op, no, mv = int(m[1]), int(m[2]), ord(m[3]) - ord("a") + 1
    return make_piece_id("JC Bach", f"op{op}", no, mv)


def _chopin_id(stem: str) -> PieceId:
    """``BI105-2op30-2`` -> ``chopin_op30_no2``; no opus: ``BI16-1`` -> ``chopin_b16_no1``,
    ``BI134`` -> ``chopin_b134`` (Brown index, as the corpus names it). Opus numbers are the
    corpus's (Sapp's chopin-mazurkas numbering, the one MazurkaBL uses)."""
    m = re.fullmatch(r"BI(\d+)(?:-(\d+))?(?:op(\d+)-(\d+))?", stem)
    if m is None:
        raise ValueError(f"unexpected stem {stem!r}")
    if m[3]:
        return make_piece_id("Chopin", f"op{int(m[3])}", int(m[4]))
    return make_piece_id("Chopin", f"b{int(m[1])}", int(m[2]) if m[2] else None)


def _grieg_id(stem: str) -> PieceId:
    """``op12n01`` -> ``grieg_op12_no1``."""
    m = re.fullmatch(r"op(\d+)n(\d+)", stem)
    if m is None:
        raise ValueError(f"unexpected stem {stem!r}")
    return make_piece_id("Grieg", f"op{int(m[1])}", int(m[2]))


def _tchaikovsky_id(stem: str) -> PieceId:
    """``op37a01`` -> ``tchaikovsky_op37a_no1``."""
    m = re.fullmatch(r"op37a(\d+)", stem)
    if m is None:
        raise ValueError(f"unexpected stem {stem!r}")
    return make_piece_id("Tchaikovsky", "op37a", int(m[1]))


def _schumann_id(stem: str) -> PieceId:
    """``n07`` -> ``schumann_op15_no7``."""
    m = re.fullmatch(r"n(\d+)", stem)
    if m is None:
        raise ValueError(f"unexpected stem {stem!r}")
    return make_piece_id("Schumann", "op15", int(m[1]))


def _liszt_id(stem: str) -> PieceId:
    """``162.01_Gondoliera`` -> ``liszt_s162_no1``."""
    m = re.match(r"(16[012])\.(\d+)_", stem)
    if m is None:
        raise ValueError(f"unexpected stem {stem!r}")
    return make_piece_id("Liszt", f"S{m[1]}", int(m[2]))


# --------------------------------------------------------------------------- corpora


@dataclass(frozen=True)
class Corpus:
    """A registered DCML corpus. ``title_tempo``: the movement title is the tempo word
    (J. C. Bach); otherwise ``Tempo`` events are read. ``spanners``: read hairpins and text
    lines from the chords facet."""

    name: str
    repo: str
    tag: str
    commit: str
    composer: str
    id_fn: Callable[[str], PieceId]
    title_tempo: bool = False
    spanners: bool = True

    @property
    def dataset(self) -> str:
        return f"dcml_{self.name}"

    @property
    def root(self) -> Path:
        return RAW / self.dataset

    @property
    def url(self) -> str:
        return f"https://github.com/DCMLab/{self.repo}"


CORPORA: dict[str, Corpus] = {c.name: c for c in (
    Corpus("jc_bach", "jc_bach_sonatas", "v2.4", "ac9fd07905eb62c3d8cfbd96811491170a216232",
           "J. C. Bach", _jc_bach_id, title_tempo=True, spanners=False),
    Corpus("chopin_mazurkas", "chopin_mazurkas", "v3.2",
           "5931135e614985023b96de2a291c74b7ef90b287", "Chopin", _chopin_id),
    Corpus("grieg_lyric_pieces", "grieg_lyric_pieces", "v2.3",
           "91a304563521f3f273b8c0aadec1ce2ede2d1384", "Grieg", _grieg_id),
    Corpus("tchaikovsky_seasons", "tchaikovsky_seasons", "v2.3",
           "281afa3c6637b7f881fc18928f074f3f9d7dbfcf", "Tchaikovsky", _tchaikovsky_id),
    Corpus("schumann_kinderszenen", "schumann_kinderszenen", "v2.3",
           "ee929c1556bc937fe1ea7303cac4476e37caa4d1", "Schumann", _schumann_id),
    Corpus("liszt_pelerinage", "liszt_pelerinage", "v2.3",
           "f1cfd308adba5763aad3a18885eac48d42449fc4", "Liszt", _liszt_id),
)}
ROMANTIC = ("chopin_mazurkas", "grieg_lyric_pieces", "tchaikovsky_seasons",
            "schumann_kinderszenen", "liszt_pelerinage")


def get_corpus(corpus: str | Corpus) -> Corpus:
    if isinstance(corpus, Corpus):
        return corpus
    name = corpus.removeprefix("dcml_")
    if name not in CORPORA:
        raise KeyError(f"unknown DCML corpus {corpus!r}; known: {sorted(CORPORA)}")
    return CORPORA[name]


def _root(c: Corpus, root: Path | str | None) -> Path:
    return Path(root) if root is not None else c.root


def data_available(corpus: str | Corpus, root: Path | str | None = None) -> bool:
    r = _root(get_corpus(corpus), root)
    return (r / "notes").is_dir() and (r / "metadata.tsv").is_file()


def metadata(corpus: str | Corpus, root: Path | str | None = None) -> pd.DataFrame:
    return pd.read_csv(_root(get_corpus(corpus), root) / "metadata.tsv", sep="\t", dtype=str)


def pieces(corpus: str | Corpus, root: Path | str | None = None, *,
           labelled: bool = False) -> list[str]:
    """Movement stems of ``metadata.tsv`` that have a notes TSV; ``labelled=True``: only those
    with a ``harmonies/`` table too (Chopin op. 30/1 has none)."""
    c = get_corpus(corpus)
    r = _root(c, root)
    out = [s for s in sorted(metadata(c, r)["piece"])
           if (r / "notes" / f"{s}.notes.tsv").is_file()]
    if labelled:
        out = [s for s in out if (r / "harmonies" / f"{s}.harmonies.tsv").is_file()]
    return out


def piece_id(corpus: str | Corpus, stem: str) -> PieceId:
    return get_corpus(corpus).id_fn(stem)


def _frac(x: Any) -> Fraction:
    if isinstance(x, float) and np.isnan(x):
        return Fraction(0)
    return Fraction(str(x).strip())


def read_facet(corpus: str | Corpus, stem: str, facet: str,
               root: Path | str | None = None) -> pd.DataFrame:
    path = _root(get_corpus(corpus), root) / facet / f"{stem}.{facet}.tsv"
    return pd.read_csv(path, sep="\t", dtype=str, keep_default_na=False)


def _read_label_free(corpus: str | Corpus, stem: str, facet: str, root: Path | str | None,
                     used: list[str]) -> pd.DataFrame:
    if facet not in LABEL_FREE_FACETS:
        raise ValueError(f"{facet!r} is not a label-free facet {LABEL_FREE_FACETS}")
    used.append(f"{facet}/{stem}.{facet}.tsv")
    return read_facet(corpus, stem, facet, root)


# --------------------------------------------------------------------------- unfolding


def _col(r: Any, name: str) -> str:
    return str(r.get(name, "") or "").strip()


def playthrough(measures: pd.DataFrame, unfold: bool = True) -> list[int]:
    """Measure counts (``mc``) in playing order. ``unfold=False``: each ``mc`` once.

    Follows ``next``. After a backward jump (``jump_bwd``, D.C. / D.S.) with ``play_until``
    ``fine``, a repeat with several targets takes the one that holds the ``fine`` and the
    playthrough ends after the ``fine`` measure; after any backward jump it ends at the jump
    measure if that is reached again (*senza fine*). ms3 already writes these exits into
    ``next`` for most pieces; the rules only matter where it does not (module docstring)."""
    mcs = [int(x) for x in measures["mc"]]
    if not unfold:
        return mcs
    nxt, jump, until, fine = {}, {}, {}, set()
    markers: dict[str, int] = {}
    for _, r in measures.iterrows():
        mc = int(r["mc"])
        nxt[mc] = [int(v) for v in str(r["next"]).split(",") if v.strip()]
        jump[mc] = _col(r, "jump_bwd")
        until[mc] = _col(r, "play_until")
        mk = _col(r, "markers").lower()
        if "fine" in mk:
            fine.add(mc)
        for m in (x.strip() for x in mk.split(",") if x.strip()):
            markers.setdefault(m, mc)
    to_fine = any(until[m] == "fine" for m in mcs if jump[m])
    following = dict(zip(mcs, [*mcs[1:], -1], strict=True))

    def destination(mc: int) -> int | None:
        j = jump[mc].lower()
        return mcs[0] if j == "start" else markers.get(j)

    visits: dict[int, int] = {}
    out, mc = [], mcs[0]
    jumped: str | None = None
    while mc != -1:
        out.append(mc)
        visits[mc] = visits.get(mc, 0) + 1
        if len(out) > 20 * len(mcs):
            raise RuntimeError("unfolding does not terminate")
        if jumped is not None and ((jumped == "fine" and mc in fine) or jump[mc]):
            break
        targets = nxt.get(mc) or [-1]
        if jumped is None and to_fine and mc in fine:
            # a Fine only ends the piece after the D.C. / D.S.; ms3 sometimes ends it here
            targets = [t for t in targets if t != -1] or [following[mc]]
        nx = targets[min(visits[mc] - 1, len(targets) - 1)]
        if jumped == "fine" and len(targets) > 1:
            nx = next((t for t in targets if t in fine), nx)
        if jump[mc] and jumped is None and nx != -1 and nx == destination(mc):
            jumped = until[mc] or "/"
        mc = nx
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


_GAP_TIE = Fraction(4)  # quarters: how far after a tie head its continuation may start


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
                  ) -> tuple[list[_Note], int, int]:
    """Notes placed on the linear (unfolded) timeline with ties merged; also the count of
    tie continuations that found no start (kept as notes) and of ties merged across a gap or
    a staff change (the head ends before its continuation starts, as ms3 exports some ties
    in Romantic scores; ms3's ``n_onsets`` counts these as tied)."""
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
    by_pitch: dict[int, list[int]] = {}
    for j, n in enumerate(raw):
        if n.tied in ("-1", "0"):
            cont.setdefault((n.midi, n.staff, n.onset), []).append(j)
            by_pitch.setdefault(n.midi, []).append(j)
    absorbed: set[int] = set()
    out = []
    gap_ties = 0
    for j, n in enumerate(raw):
        if j in absorbed:
            continue
        cur = n
        while cur.tied in ("1", "0"):
            end = cur.onset + cur.dur
            c = [x for x in cont.get((cur.midi, cur.staff, end), []) if x not in absorbed]
            if not c:
                # the continuation starts after a gap or on the other staff: take the
                # earliest free one of the same pitch within one whole note of the end
                c = sorted((x for x in by_pitch.get(cur.midi, []) if x not in absorbed
                            and cur.onset < raw[x].onset <= end + _GAP_TIE),
                           key=lambda x: (raw[x].onset, raw[x].staff != cur.staff))[:1]
                gap_ties += bool(c)
            if not c:
                break
            absorbed.add(c[0])
            nxt = raw[c[0]]
            n.dur = nxt.onset + nxt.dur - n.onset
            cur = nxt
        out.append(n)
    orphans = sum(1 for n in out if n.tied in ("-1", "0"))
    return out, orphans, gap_ties


_GRACE = {"acciaccatura": "acciaccatura"}
_TAG = re.compile(r"<[^>]*>")
# metronome-mark glyphs after NFC (notehead + stem [+ flag]), longest first
_METRO = (("\U0001D158\U0001D165\U0001D16F", "16th"), ("\U0001D158\U0001D165\U0001D16E", "eighth"),
          ("\U0001D158\U0001D165", "quarter"), ("\U0001D157\U0001D165", "half"),
          ("\U0001D15D", "whole"), ("\U0001D16D", "."))


def clean_text(txt: str) -> str:
    """Score text without markup, private-use glyphs or metronome glyphs (spelled
    ``quarter=144``); "Tempo I" / "Temp. I." is spelled "Tempo primo", and "una chorda" /
    "tres chorde" as "una corda" / "tres corde"; ``""`` if nothing with a letter or digit is
    left."""
    t = html.unescape(_TAG.sub("", str(txt)))
    t = unicodedata.normalize("NFC", t)
    for glyph, word in _METRO:
        t = t.replace(glyph, word)
    t = "".join(ch for ch in t if unicodedata.category(ch) not in ("Co", "Cc", "Cf"))
    t = re.sub(r"\s+", " ", t.replace("space", "")).strip()
    # spellings that R-08a's leakage check would read as labels: "Tempo I" / "Temp. I." as a
    # Roman numeral, Liszt's "una chorda" / "tres chorde" (= una corda / tre corde) as "chord"
    t = re.sub(r"\b[Tt]emp(?:o|\.)\s*I\b\.?°?", "Tempo primo", t)
    t = re.sub(r"\b(una|tre|tres)\s+chord([ae])\b", lambda m: f"{m[1]} cord{m[2]}", t,
               flags=re.I)
    return t if re.search(r"[^\W_]", t) else ""


def _spans(ch: pd.DataFrame, col: str) -> list[tuple[int, Fraction, int, Fraction, int]]:
    """Spanner ``col`` of the chords facet: ``(mc0, onset0, mc1, end1, staff)`` per spanner id,
    from its ``Spanner`` row to the end of the last chord that carries the id."""
    first: dict[str, tuple[int, Fraction, int]] = {}
    last: dict[str, tuple[int, Fraction]] = {}
    for _, r in ch.iterrows():
        v = str(r.get(col, "") or "")
        if not v:
            continue
        mc, on = int(r["mc"]), _frac(r["mc_onset"])
        dur = _frac(r.get("duration", "0") or "0")
        for sid in (x.strip() for x in v.split(",") if x.strip()):
            if r.get("event") == "Spanner" and sid not in first:
                first[sid] = (mc, on, int(r["staff"]))
            elif r.get("event") != "Spanner":
                end = (mc, on + dur)
                if sid not in last or end > last[sid]:
                    last[sid] = end
    out = []
    for sid, (mc0, on0, st) in first.items():
        mc1, e1 = last.get(sid, (mc0, on0))
        out.append((mc0, on0, mc1, e1, st))
    return out


def load_score(corpus: str | Corpus, stem: str, root: Path | str | None = None, *,
               unfold: bool = True, tempo_word: bool = True) -> Score:
    """Label-free score of one movement (module docstring), ``part`` kept.

    ``meta``: ``source_files`` (the only files read), ``divs`` (partitura divs per quarter),
    ``playthrough`` (list of ``(mc, pass, start)``; ``start`` is a fraction string in
    quarters from the first onset, not partitura's ``quarter_map``, which puts the first full
    bar at 0), ``unfolded``, ``unfold_validated``, ``rests`` ("derived"), ``n_orphan_ties``,
    ``title`` (metadata only; rendered only for ``jc_bach``), ``corpus``, ``commit``.
    """
    import partitura as pt

    c = get_corpus(corpus)
    root = _root(c, root)
    used: list[str] = []
    md = metadata(c, root).set_index("piece").loc[stem]
    used.append("metadata.tsv[piece, movementTitle]" if c.title_tempo
                else "metadata.tsv[piece]")
    ms = _read_label_free(c, stem, "measures", root, used)
    na = _read_label_free(c, stem, "notes", root, used)
    ch = _read_label_free(c, stem, "chords", root, used)
    order = playthrough(ms, unfold)
    passes = _passes(ms, order)
    notes, orphans, gap_ties = _linear_notes(na, passes, suffix=unfold)
    total = passes[-1].start + passes[-1].length
    validated = None
    if unfold:
        lm, lq = str(md.get("last_mc_unfolded", "")), str(md.get("length_qb_unfolded", ""))
        validated = (lm not in ("", "nan") and len(order) == int(float(lm))
                     and abs(float(total) - float(lq)) < 0.01)

    fracs = [p.start for p in passes] + [p.length for p in passes]
    fracs += [n.onset for n in notes] + [n.dur for n in notes]
    folded_start: dict[int, Fraction] = {}
    t_fold = Fraction(0)
    for _, r in ms.iterrows():
        folded_start[int(r["mc"])] = t_fold
        t_fold += _frac(r["act_dur"]) * 4
    spans: list[tuple[str, str, int, Fraction, Fraction, int]] = []
    if c.spanners:
        for col in ch.columns:
            if col in ("crescendo_hairpin", "crescendo_line"):
                kind, txt = "inc", ""
            elif col in ("decrescendo_hairpin", "diminuendo_line"):
                kind, txt = "dec", ""
            elif col.startswith("HairPin:"):
                kind, txt = "words", col.split("_", 1)[1] if "_" in col else ""
            elif col.startswith("TextLine_"):
                kind, txt = "words", col.split("_", 1)[1]
            else:
                continue
            for mc0, on0, mc1, e1, st in _spans(ch, col):
                length = max(folded_start[mc1] + e1 * 4 - folded_start[mc0] - on0 * 4,
                             Fraction(0))
                spans.append((kind, txt, mc0, on0 * 4, length, st))
                fracs += [on0 * 4, length]
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
    staves = sorted({1, 2} | {n.staff for n in notes})
    for staff in staves:
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
    # dynamics, staff / system text and tempo marks from the chords facet
    starts_by_mc: dict[int, list[Fraction]] = {}
    for p in passes:
        starts_by_mc.setdefault(p.mc, []).append(p.start)
    end_t = T(total)
    for _, r in ch.iterrows():
        ev = r.get("event", "")
        if ev == "Dynamic":
            col = "dynamics"
        elif ev == "StaffText":
            col = "staff_text"
        elif ev == "SystemText" and not c.title_tempo:
            col = "system_text"
        elif ev == "Tempo" and tempo_word and not c.title_tempo:
            col = "tempo"
        else:
            continue
        txt = clean_text(r.get(col, "") or "")
        if not txt:
            continue
        staff = int(r["staff"]) if str(r.get("staff", "")).strip() else None
        for s in starts_by_mc.get(int(r["mc"]), []):
            t = T(s + _frac(r["mc_onset"]) * 4)
            if ev == "Dynamic":
                obj = pt.score.ConstantLoudnessDirection(txt, staff=staff)
            elif ev == "Tempo":
                obj = pt.score.ConstantTempoDirection(txt, staff=staff)
            else:
                obj = pt.score.Words(txt, staff=staff)
            part.add(obj, t)
    for kind, txt, mc0, on0, length, st in spans:
        for s in starts_by_mc.get(mc0, []):
            t0 = T(s + on0)
            t1 = min(T(s + on0 + length), end_t)
            if kind == "words":
                if txt := clean_text(txt):
                    part.add(pt.score.Words(txt, staff=st), t0)
                continue
            cls = (pt.score.IncreasingLoudnessDirection if kind == "inc"
                   else pt.score.DecreasingLoudnessDirection)
            obj = cls(wedge=True, staff=st)
            if t1 > t0:
                part.add(obj, t0, t1)
            else:
                part.add(obj, t0)
    title = str(md.get("movementTitle", "") or "").strip()
    if title == "nan":
        title = ""
    if c.title_tempo and tempo_word and title:
        part.add(pt.score.ConstantTempoDirection(title), 0)
    meta = {"source_files": used, "divs": divs, "unfolded": unfold, "rests": "derived",
            "n_orphan_ties": orphans, "title": title, "commit": c.commit,
            "length_quarters": float(total),
            "playthrough": [(p.mc, p.k, str(p.start)) for p in passes]}
    if c.name != "jc_bach":
        meta.update(corpus=c.name, unfold_validated=validated, n_gap_ties=gap_ties)
    return score_from_partitura(
        part, score_id=f"{c.dataset}:{stem}", piece_id=c.id_fn(stem),
        source_path=root / "notes" / f"{stem}.notes.tsv", meta=meta, keep_part=True)


@dataclass
class LoadStats:
    loaded: int = 0
    failed: int = 0
    failures: list[tuple[str, str]] = field(default_factory=list)


def iter_scores(corpus: str | Corpus, root: Path | str | None = None,
                stats: LoadStats | None = None, *, unfold: bool = True) -> Iterator[Score]:
    c = get_corpus(corpus)
    stats = stats if stats is not None else LoadStats()
    for stem in pieces(c, root):
        try:
            yield load_score(c, stem, root, unfold=unfold)
            stats.loaded += 1
        except Exception as e:  # noqa: BLE001 - count and continue
            stats.failed += 1
            stats.failures.append((stem, repr(e)))
            log.warning("%s %s failed: %r", c.dataset, stem, e)


def split_score_id(score_or_id: Any) -> tuple[str, str]:
    """``(corpus name, stem)`` of a score or ``score_id`` (``dcml_<corpus>:<stem>``)."""
    sid = str(getattr(score_or_id, "score_id", score_or_id))
    ds, _, stem = sid.partition(":")
    return ds.removeprefix("dcml_"), stem


def stem_of(score_or_id: Any) -> str:
    sid = getattr(score_or_id, "score_id", score_or_id)
    return str(sid).split(":")[-1]


# --------------------------------------------------------------------------- labels


def load_labels(corpus: str | Corpus, stem: str, root: Path | str | None = None
                ) -> pd.DataFrame:
    """The DCML label table (``harmonies/``). Never pass this to a renderer."""
    return read_facet(corpus, stem, "harmonies", root)


def label_strings(corpus: str | Corpus, stem: str, root: Path | str | None = None,
                  min_len: int = 1) -> set[str]:
    """Distinct label-text values of the movement (for leakage checks)."""
    df = load_labels(corpus, stem, root)
    out: set[str] = set()
    for col in LABEL_TEXT_COLUMNS:
        if col in df.columns:
            out |= {v.strip() for v in df[col].astype(str) if len(v.strip()) >= min_len}
    return out


@dataclass
class DcmlPhraseAnnotations(PhraseAnnotations):
    """``PhraseAnnotations`` plus ``n_off_onset`` (label placements not on a note onset) and
    ``n_other`` (``phraseend`` values other than ``{``, ``}``, ``}{``, dropped)."""

    n_off_onset: int = 0
    n_other: int = 0


def phrase_annotations(score: Score, root: Path | str | None = None, *,
                       corpus: str | Corpus | None = None) -> DcmlPhraseAnnotations:
    """Phrase and cadence tables of ``score`` (from :func:`load_score`, unfolded or not) in its
    beats; a ``batik_mozart.PhraseAnnotations``. The corpus comes from ``score_id`` unless
    given. ``n_unmapped`` counts labels whose measure is not in the playthrough (0 expected
    unless a *fine* cuts the unfolded score short)."""
    name, stem = split_score_id(score)
    c = get_corpus(corpus if corpus is not None else name)
    lab = load_labels(c, stem, root)
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
