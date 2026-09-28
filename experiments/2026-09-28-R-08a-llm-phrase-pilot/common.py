"""R-08a shared code: performed score -> bar table and label-free text rendering.

Only these partitura objects are read: notes (via ``Score.notes`` plus pitch spelling from the
part), rests, time and key signatures, loudness and tempo directions, a few free words,
fermatas and barlines. ``ChordSymbol`` objects (the MusicXML ``<harmony>`` elements, which
carry the DCML labels) are never touched.
"""

from __future__ import annotations

import json
import logging
import re
import warnings
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ART = HERE / "artifacts"
BLIND = HERE / "blind_input"
EPS = 1e-6

# free words that may name the piece or are not performance directions
_DROP_WORDS = re.compile(r"k(ö|oe)chel|verzeichnis|\bkv\b|\bnr\b|sonat|mozart|other-dynamics",
                         re.I)


def selection() -> list[dict]:
    return json.loads((ART / "selection.json").read_text())["picks"]


def load_score(stem: str):
    warnings.filterwarnings("ignore")
    logging.disable(logging.WARNING)
    from pianolens.data import batik_mozart as bm

    return bm.load_aligned(stem, musicxml_score=True).score


# --------------------------------------------------------------------------- bar table


def bar_table(score) -> pd.DataFrame:
    """One row per performed bar: ``bar`` (running number, 1..N), ``written`` (score bar
    number), ``start``/``end`` (performed-score beats), ``nominal`` (beats per full bar),
    ``shift`` (beats added to the printed beat label: the anacrusis bar is right-aligned),
    ``ts`` ("3/4"), ``fifths`` (key signature)."""
    import partitura as pt

    part = score.part
    bmap = part.beat_map
    tss = sorted(part.iter_all(pt.score.TimeSignature), key=lambda o: o.start.t)
    kss = sorted(part.iter_all(pt.score.KeySignature), key=lambda o: o.start.t)
    pm = sorted(part.iter_all(pt.score.Measure), key=lambda o: o.start.t)
    ms = score.measures
    assert len(pm) == len(ms)
    rows = []
    for i, (m, pmm) in enumerate(zip(ms, pm, strict=True)):
        t0, t1 = pmm.start.t, pmm.end.t
        assert abs(float(part.quarter_map(t0)) - float(m["start_quarter"])) < 1e-6
        ts = [o for o in tss if o.start.t <= t0][-1]
        ks = [o for o in kss if o.start.t <= t0]
        rows.append({"bar": i + 1, "written": str(m["name"]),
                     "start": float(bmap(t0)), "end": float(bmap(t1)),
                     "nominal": float(ts.beats), "ts": f"{ts.beats}/{ts.beat_type}",
                     "fifths": int(ks[-1].fifths) if ks else 0})
    df = pd.DataFrame(rows)
    assert (np.diff(df["start"]) > 0).all()
    first = df["written"].iloc[0]
    length = df["end"] - df["start"]
    pickup = (df["written"] == first) & (length < df["nominal"] - EPS)
    df["shift"] = np.where(pickup, df["nominal"] - length, 0.0)
    return df


def beat_label(x: float) -> str:
    """Beat position in the bar (1-based) as ``2``, ``2+1/2``, ``1+1/3``."""
    fr = Fraction(x).limit_denominator(96)
    whole = fr.numerator // fr.denominator
    rest = fr - whole
    return str(whole) if rest == 0 else f"{whole}+{rest.numerator}/{rest.denominator}"


def dur_label(x: float) -> str:
    fr = Fraction(x).limit_denominator(96)
    return str(fr.numerator) if fr.denominator == 1 else f"{fr.numerator}/{fr.denominator}"


def parse_beat(v) -> float:
    """Inverse of :func:`beat_label`; also accepts numbers and decimals as strings."""
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    s = str(v).strip().replace(" ", "")
    m = re.fullmatch(r"(\d+)\+(\d+)/(\d+)", s)
    if m:
        return int(m[1]) + int(m[2]) / int(m[3])
    m = re.fullmatch(r"(\d+)/(\d+)", s)
    if m:
        return int(m[1]) / int(m[2])
    return float(s)


def to_perf_beat(bars: pd.DataFrame, bar: int, beat: float) -> float | None:
    """(running bar, printed beat) -> performed-score beat; None if the bar does not exist."""
    r = bars.loc[bars["bar"] == int(bar)]
    if r.empty:
        return None
    r = r.iloc[0]
    return float(r["start"] + (beat - 1.0) - r["shift"])


def to_bar_beat(bars: pd.DataFrame, x: float) -> tuple[int, str]:
    """performed-score beat -> (running bar, printed beat label)."""
    i = int(np.searchsorted(bars["start"].to_numpy(), x + EPS, side="right")) - 1
    i = max(i, 0)
    r = bars.iloc[i]
    return int(r["bar"]), beat_label(x - r["start"] + r["shift"] + 1.0)


# --------------------------------------------------------------------------- rendering


_ACC = {-2: "bb", -1: "b", 0: "", 1: "#", 2: "##"}


def _spelling(part) -> dict[str, str]:
    import partitura as pt

    out = {}
    for n in part.iter_all(pt.score.Note, include_subclasses=True):
        out[str(n.id)] = f"{n.step}{_ACC.get(n.alter or 0, '?')}{n.octave}"
    return out


def _key_text(fifths: int) -> str:
    if fifths == 0:
        return "no sharps or flats"
    n = abs(fifths)
    return f"{n} {'sharp' if fifths > 0 else 'flat'}{'s' if n > 1 else ''}"


@dataclass
class Rendering:
    text: str
    bars: pd.DataFrame
    n_pointer_bars: int


def _events(score, bars: pd.DataFrame) -> dict[int, dict]:
    """Per running bar: onsets -> {staff: [(label, dur)], ...}, rests, fermatas, marks."""
    import partitura as pt

    part = score.part
    bmap = part.beat_map
    sp = _spelling(part)
    starts = bars["start"].to_numpy()

    def bar_of(b: float) -> int:
        return int(bars["bar"].iloc[max(int(np.searchsorted(starts, b + EPS, "right")) - 1, 0)])

    ev: dict[int, dict] = {int(b): {"notes": [], "rests": [], "ferm": [], "marks": []}
                           for b in bars["bar"]}
    na = score.notes
    for n in na:
        b = float(n["onset_beat"])
        ev[bar_of(b)]["notes"].append((b, int(n["staff"]), sp.get(str(n["id"]), "?"),
                                       float(n["duration_beat"]), bool(n["is_grace"]),
                                       int(n["pitch"])))
    for r in part.iter_all(pt.score.Rest):
        b0, b1 = float(bmap(r.start.t)), float(bmap(r.end.t))
        ev[bar_of(b0)]["rests"].append((b0, int(r.staff or 1), b1 - b0))
    for f in part.iter_all(pt.score.Fermata):
        b = float(bmap(f.start.t))
        ev[bar_of(b)]["ferm"].append(b)
    for d in part.iter_all(pt.score.LoudnessDirection, include_subclasses=True):
        txt = str(getattr(d, "text", "") or "").strip()
        if isinstance(d, pt.score.IncreasingLoudnessDirection):
            txt = "cresc."
        elif isinstance(d, pt.score.DecreasingLoudnessDirection):
            txt = "dim."
        if txt:
            b = float(bmap(d.start.t))
            ev[bar_of(b)]["marks"].append((b, txt))
    for cls in (pt.score.TempoDirection, pt.score.Words):
        for d in part.iter_all(cls, include_subclasses=True):
            txt = str(getattr(d, "text", "") or "").strip()
            if txt and not _DROP_WORDS.search(txt):
                b = float(bmap(d.start.t))
                ev[bar_of(b)]["marks"].append((b, txt))
    for bl in part.iter_all(pt.score.Barline):
        style = getattr(bl, "style", None)
        if style in ("light-light", "light-heavy", "heavy-light", "heavy-heavy"):
            b = float(bmap(bl.start.t))
            # a barline belongs to the bar that ends there
            i = int(np.searchsorted(starts, b - EPS, "left")) - 1
            if 0 <= i < len(bars):
                ev[int(bars["bar"].iloc[i])]["marks"].append((np.inf, "double barline"))
    return ev


def _bar_lines(bar_row, e, sounding: tuple[np.ndarray, np.ndarray]) -> tuple[list[str], tuple]:
    sounding_notes, names = sounding
    start, shift = float(bar_row["start"]), float(bar_row["shift"])

    def lab(b):
        return beat_label(b - start + shift + 1.0)

    pos: dict[str, dict] = {}

    def slot(b):
        k = lab(b)
        return pos.setdefault(k, {"b": b, 1: [], 2: [], "gr": {1: [], 2: []}, "rest": {},
                                  "ferm": False, "marks": []})

    for b, st, name, dur, grace, _pitch in sorted(e["notes"], key=lambda t: (t[0], t[5])):
        s = slot(b)
        st = st if st in (1, 2) else 1
        if grace:
            s["gr"][st].append(name)
        else:
            s[st].append((name, dur))
    for b, st, dur in e["rests"]:
        slot(b)["rest"][st if st in (1, 2) else 1] = dur
    for b in e["ferm"]:
        slot(b)["ferm"] = True
    tail = []
    for b, txt in e["marks"]:
        if np.isinf(b):
            tail.append(txt)
        else:
            slot(b)["marks"].append(txt)
    lines = []
    for k, s in sorted(pos.items(), key=lambda kv: kv[1]["b"]):
        parts = []
        for st, hand in ((1, "RH"), (2, "LH")):
            toks = []
            if s["gr"][st]:
                toks.append("grace(" + " ".join(s["gr"][st]) + ")")
            by_dur: dict[str, list[str]] = {}
            for name, dur in s[st]:
                by_dur.setdefault(dur_label(dur), []).append(name)
            toks += [" ".join(v) + " " + d for d, v in by_dur.items()]
            if st in s["rest"] and not s[st]:
                toks.append("rest " + dur_label(s["rest"][st]))
            if toks:
                parts.append(f"{hand} " + "; ".join(toks))
        b = s["b"]
        on = (sounding_notes[:, 0] <= b + EPS) & (sounding_notes[:, 1] > b + EPS)
        bass = names[on][int(np.argmin(sounding_notes[on, 2]))] if on.any() else "-"
        line = f"  {k:>7}  " + " | ".join(parts) + f" | bass {bass}"
        if s["ferm"]:
            line += " | FERMATA"
        if s["marks"]:
            line += " | [" + ", ".join(s["marks"]) + "]"
        lines.append(line)
    if tail:
        lines.append("  (" + ", ".join(sorted(set(tail))) + " at end of bar)")
    sig = tuple(lines)
    return lines, sig


def render(score, mid: str) -> Rendering:
    bars = bar_table(score)
    ev = _events(score, bars)
    na = score.notes
    ng = na[na["is_grace"] == 0]
    sp = _spelling(score.part)
    names = np.array([sp.get(str(i), "?") for i in ng["id"]], dtype=object)
    sounding = (np.column_stack([ng["onset_beat"], ng["onset_beat"] + ng["duration_beat"],
                                 ng["pitch"]]).astype(float), names)
    out = [LEGEND.format(mid=mid).rstrip(), ""]
    first = bars.iloc[0]
    out.append(f"MOVEMENT {mid}: time {first['ts']}, key signature {_key_text(first['fifths'])}, "
               f"{len(bars)} bars as performed (repeats written out).")
    out.append("")
    seen: dict[tuple, int] = {}
    prev_ts, prev_key = first["ts"], first["fifths"]
    pointer_run: list[tuple[int, int, str]] = []
    n_pointer = 0

    def flush():
        if not pointer_run:
            return
        a, b = pointer_run[0], pointer_run[-1]
        consecutive = all(pointer_run[i + 1][1] == pointer_run[i][1] + 1
                          for i in range(len(pointer_run) - 1))
        if len(pointer_run) > 1 and consecutive:
            out.append(f"BARS {a[0]}-{b[0]} (score {a[2]}-{b[2]}): same notes and markings "
                       f"as bars {a[1]}-{b[1]}")
        else:
            for x in pointer_run:
                out.append(f"BAR {x[0]} (score {x[2]}): same notes and markings as bar {x[1]}")
        pointer_run.clear()

    for _, r in bars.iterrows():
        e = ev[int(r["bar"])]
        lines, sig = _bar_lines(r, e, sounding)
        length = r["end"] - r["start"]
        key = (r["written"], sig, r["ts"], r["fifths"], round(length, 4))
        head_extra = []
        if r["ts"] != prev_ts:
            head_extra.append(f"time {r['ts']}")
        if r["fifths"] != prev_key:
            head_extra.append(f"key signature {_key_text(r['fifths'])}")
        prev_ts, prev_key = r["ts"], r["fifths"]
        if key in seen and not head_extra:
            pointer_run.append((int(r["bar"]), seen[key], r["written"]))
            n_pointer += 1
            continue
        flush()
        seen.setdefault(key, int(r["bar"]))
        h = f"BAR {int(r['bar'])} (score {r['written']})"
        if length < r["nominal"] - EPS:
            h += (f" short bar: {dur_label(length)} beats, from beat "
                  f"{beat_label(r['shift'] + 1)}")
        if head_extra:
            h += " | " + ", ".join(head_extra)
        out.append(h)
        out.extend(lines if lines else ["  (empty)"])
    flush()
    out.append("END")
    return Rendering("\n".join(out) + "\n", bars, n_pointer)


LEGEND = """\
SCORE RENDERING {mid} (piano, two staves; one movement)

How to read this file
- Bars are numbered 1, 2, 3, ... in the order they are played; repeats are written out, so a
  repeated section appears twice. "(score N)" is the bar number printed in the score; "X1",
  "X2", ... are score bars without a printed number (e.g. alternative endings).
- The anacrusis (upbeat) bar at the start is shorter; its beats are counted from the end of
  the bar, as in the score.
- Beat unit = the lower number of the time signature (3/4: quarter-note beats 1-3; 2/2:
  half-note beats 1-2; 2/4: quarter-note beats 1-2; 4/4: quarter-note beats 1-4).
- Each line is one onset time in the bar: its beat position (e.g. 2, 2+1/2, 1+1/3), then the
  notes that START there in each staff: RH = upper staff, LH = lower staff.
- Notes are written as pitch name + octave (C4 = middle C; # sharp, b flat, e.g. Bb3, F#5).
  The number after a group of notes is their written duration in beats (tied notes are
  merged). Notes already sounding from earlier onsets are not repeated.
- "grace(X Y)" = grace notes before the main note(s) at that beat.
- "rest d" = a rest of d beats in that staff.
- "bass X" = the lowest pitch sounding at that moment (including held notes).
- "FERMATA" = a fermata at that onset.
- [ ... ] = markings printed at that onset: dynamics (pp, p, mf, f, fp, sf), cresc./dim.,
  tempo and expression words.
- "same notes and markings as bars a-b" = those bars are an exact repeat of earlier bars and
  are not printed again.
- "double barline" = a double or final barline at the end of the bar.
"""
