"""R-08b condition A: disguised renderings of the R-08a pilot movements.

Reuses R-08a's renderer (``common.py`` of R-08a, imported). Inside :func:`disguised`, four of its
module-level functions are wrapped, so every other line of the rendering comes from the same code:

- ``bar_table``: running bar and numeric score bar + ``c``; key signature fifths + ``k``;
- ``_spelling``: every note moved by ``s`` semitones and ``k`` fifths (consistent respelling);
- ``_events``: all loudness / tempo / word markings dropped (fermatas and double barlines kept);
- ``LEGEND``: no markings lines; bar numbers start at an arbitrary number.

    uv run python <this folder>/disguise.py            # draw + render + check
    uv run python <this folder>/disguise.py --check    # check only
    uv run python <this folder>/disguise.py --check --hashes
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from contextlib import contextmanager
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
R08A = ROOT / "experiments" / "2026-09-28-R-08a-llm-phrase-pilot"
sys.path.insert(0, str(R08A))

import common as C  # noqa: E402  (R-08a)
import render as R08R  # noqa: E402  (R-08a leakage vocabulary and DCML label strings)

ART = HERE / "artifacts"
BLIND = HERE / "blind_input_disguised"
SEED = 20260929
SEMITONES = [-6, -5, -4, -3, -2, -1, 1, 2, 3, 4, 5, 6]
OFFSET_RANGE = (20, 480)  # integers(20, 480): 20..479

# line of fifths
BASE_F = {"F": -1, "C": 0, "G": 1, "D": 2, "A": 3, "E": 4, "B": 5}
F_BASE = {v: k for k, v in BASE_F.items()}
PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
ACC = {-2: "bb", -1: "b", 0: "", 1: "#", 2: "##"}
ACC_INV = {v: k for k, v in ACC.items()}
NOTE_TOKEN = re.compile(r"(?<![A-Za-z#])([A-G])(##|#|bb|b)?(-?\d)(?![\w#])")


def spell_fifths(step: str, alter: int) -> int:
    return BASE_F[step] + 7 * alter


def from_fifths(f: int) -> tuple[str, int]:
    alter = (f + 1) // 7
    return F_BASE[f - 7 * alter], alter


def token_midi(step: str, alter: int, octave: int) -> int:
    return (octave + 1) * 12 + PC[step] + alter


def transpose_spelling(step: str, alter: int, midi: int, s: int, k: int) -> str:
    st, al = from_fifths(spell_fifths(step, alter) + k)
    if al not in ACC:
        raise ValueError(f"{step}{alter} +{k} fifths needs alter {al}")
    new_midi = midi + s
    base = PC[st] + al
    assert (new_midi - base) % 12 == 0, (step, alter, midi, s, k)
    octave = (new_midi - base) // 12 - 1
    return f"{st}{ACC[al]}{octave}"


def choose_k(s: int, fifths: list[int]) -> int:
    k0 = (7 * s) % 12
    cands = [k for k in (k0, k0 - 12) if -11 <= k <= 11]
    return min(cands, key=lambda k: (max(abs(f + k) for f in fifths), abs(k), k > 0))


# --------------------------------------------------------------------------- draw


def draw() -> dict:
    rng = np.random.default_rng(SEED)
    picks = C.selection()
    rows = []
    for p in picks:
        s = int(rng.choice(SEMITONES))
        c = int(rng.integers(*OFFSET_RANGE))
        rows.append({"m_id": p["id"], "stem": p["stem"], "semitones": s, "bar_offset": c})
    perm = rng.permutation(len(picks))
    for r, j in zip(rows, perm, strict=True):
        r["d_id"] = f"D{int(j) + 1}"
        bars = pd.read_csv(C.ART / f"bars_{r['m_id']}.csv", dtype={"written": str})
        fifths = sorted(set(int(x) for x in bars["fifths"]))
        r["fifths_orig"] = fifths
        r["fifths_shift"] = choose_k(r["semitones"], fifths)
        r["fifths_new"] = [f + r["fifths_shift"] for f in fifths]
    out = {"seed": SEED, "semitones_choices": SEMITONES, "offset_range": list(OFFSET_RANGE),
           "picks": sorted(rows, key=lambda r: r["d_id"])}
    ART.mkdir(parents=True, exist_ok=True)
    (ART / "disguise.json").write_text(json.dumps(out, indent=1))
    return out


def params() -> list[dict]:
    return json.loads((ART / "disguise.json").read_text())["picks"]


# --------------------------------------------------------------------------- rendering

LEGEND = """\
SCORE RENDERING {mid} (piano, two staves; one movement)

How to read this file
- Bars are numbered consecutively in the order they are played, starting from an arbitrary
  number (the first bar is not bar 1). Repeats are written out, so a repeated section appears
  twice. "(score N)" is the score's own number for that bar, which differs from the running
  number when a section is repeated; "X1", "X2", ... are score bars without a number (e.g.
  alternative endings).
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
- "same notes as bars a-b" = those bars are an exact repeat of earlier bars and are not
  printed again.
- "double barline" = a double or final barline at the end of the bar.
"""


@contextmanager
def disguised(s: int, k: int, c: int):
    import partitura as pt

    orig = (C.bar_table, C._spelling, C._events, C.LEGEND)

    def bar_table(score):
        df = orig[0](score).copy()
        df["bar"] = df["bar"] + c
        df["written"] = [str(int(w) + c) if str(w).isdigit() else str(w) for w in df["written"]]
        df["fifths"] = df["fifths"] + k
        return df

    def _spelling(part):
        out = {}
        for n in part.iter_all(pt.score.Note, include_subclasses=True):
            out[str(n.id)] = transpose_spelling(n.step, int(n.alter or 0), int(n.midi_pitch), s, k)
        return out

    def _events(score, bars):
        ev = orig[2](score, bars)
        for e in ev.values():
            e["marks"] = [(b, t) for b, t in e["marks"] if np.isinf(b)]  # double barlines only
        return ev

    C.bar_table, C._spelling, C._events, C.LEGEND = bar_table, _spelling, _events, LEGEND
    try:
        yield
    finally:
        C.bar_table, C._spelling, C._events, C.LEGEND = orig


def render_one(p: dict) -> C.Rendering:
    score = C.load_score(p["stem"])
    with disguised(p["semitones"], p["fifths_shift"], p["bar_offset"]):
        r = C.render(score, p["d_id"])
    # the pointer wording without "and markings" (there are none)
    text = r.text.replace("same notes and markings as", "same notes as")
    return C.Rendering(text, r.bars, r.n_pointer_bars)


def write_instructions() -> None:
    src = C.BLIND
    t = (src / "INSTRUCTIONS.md").read_text()
    for a, b in (("(`M1.txt` to\n`M5.txt`)", "(`D1.txt` to\n`D5.txt`)"),
                 ("`M1.txt`..`M5.txt`", "`D1.txt`..`D5.txt`"),
                 ("`M1.json` .. `M5.json`", "`D1.json` .. `D5.json`"),
                 ('"movement": "M1"', '"movement": "D1"'),
                 ('"same notes and markings as bar(s) ..."', '"same notes as bar(s) ..."')):
        assert a in t, a
        t = t.replace(a, b)
    assert not re.search(r"\bM\d\b", t), re.findall(r".{20}\bM\d\b.{20}", t)
    (BLIND / "INSTRUCTIONS.md").write_text(t)
    sch = json.loads((src / "SCHEMA.json").read_text())
    sch["properties"]["movement"]["pattern"] = "^D[1-9]$"
    sch["properties"]["movement"]["description"] = "The id in the rendering's first line, e.g. D1."
    (BLIND / "SCHEMA.json").write_text(json.dumps(sch, indent=2) + "\n")


def main() -> None:
    d = draw()
    BLIND.mkdir(exist_ok=True)
    sizes = []
    for p in d["picks"]:
        r = render_one(p)
        (BLIND / f"{p['d_id']}.txt").write_text(r.text)
        r.bars.to_csv(ART / f"bars_{p['d_id']}.csv", index=False)
        sizes.append({"d_id": p["d_id"], "m_id": p["m_id"], "bars": len(r.bars),
                      "pointer_bars": r.n_pointer_bars, "chars": len(r.text),
                      "lines": r.text.count("\n"), "words": len(r.text.split())})
        print(sizes[-1], flush=True)
    pd.DataFrame(sizes).to_csv(ART / "render_sizes.csv", index=False)
    write_instructions()


# --------------------------------------------------------------------------- checks

IDENTITY = [
    # composers
    r"mozart", r"wolfgang", r"amadeus", r"haydn", r"beethoven", r"clementi", r"\bbach\b",
    r"schubert", r"ko(ž|z)eluc?h", r"dussek", r"pleyel", r"scarlatti", r"h(a|ä)ndel", r"chopin",
    r"schumann", r"mendelssohn", r"salieri", r"hummel", r"vanhal", r"cramer",
    # catalogue numbers
    r"k(ö|oe)chel", r"verzeichnis", r"\bKV?\.?\s?\d{2,3}", r"\bKV\b", r"\bop\.?\s?\d", r"\bwq\b",
    r"\bhob\b",
    # titles and genres
    r"sonat", r"rondo", r"rondeau", r"menuet", r"minuet", r"variation", r"fantasi", r"turca",
    r"\btheme\b", r"\bthema\b",
    # tempo and expression words
    r"allegr", r"andant", r"adagio", r"largo", r"larghetto", r"presto", r"moderato", r"vivace",
    r"assai", r"molto", r"cantabile", r"dolce", r"calando", r"piacere", r"agitato", r"grazioso",
    r"maestoso", r"espress", r"legato", r"staccato", r"sotto", r"cresc", r"\bdim\b", r"decresc",
    r"rinf", r"tempo\b", r"\bmarkings?\b",
    # provenance
    r"batik", r"dcml", r"pianolens", r"experiments/", r"/users/",
]
DYNAMICS = re.compile(r"(?<![\w#])(ppp|pp|p|mp|mf|f|ff|fff|sf|sfz|fp|fz)(?![\w#])")


def parse_pointers(text: str) -> dict[int, int]:
    m: dict[int, int] = {}
    for a, b, c, d in re.findall(r"^BARS (\d+)-(\d+) .*as bars (\d+)-(\d+)$", text, re.M):
        a, b, c, d = map(int, (a, b, c, d))
        assert b - a == d - c
        for i in range(b - a + 1):
            m[a + i] = c + i
    for a, c in re.findall(r"^BAR (\d+) .*same notes (?:and markings )?as bar (\d+)$", text, re.M):
        m[int(a)] = int(c)
    return m


def _key_fifths(text: str) -> list[int]:
    out = []
    for m in re.finditer(r"key signature (no sharps or flats|(\d+) (sharp|flat)s?)", text):
        out.append(0 if m[2] is None else int(m[2]) * (1 if m[3] == "sharp" else -1))
    return out


def _note_lines(text: str) -> list[str]:
    """The onset lines (they start with spaces and a beat label), markings stripped."""
    out = []
    for ln in text.splitlines():
        if re.match(r"^\s+\d", ln):
            out.append(re.sub(r" \| \[.*\]$", "", ln))
    return out


def check() -> bool:
    ok = True
    ps = params()
    for p in ps:
        did, mid, s, k, c = p["d_id"], p["m_id"], p["semitones"], p["fifths_shift"], p["bar_offset"]
        txt = (BLIND / f"{did}.txt").read_text()
        orig = (C.BLIND / f"{mid}.txt").read_text()
        # R-08a leakage check
        hits = [w for w in R08R.BANNED_WORDS if re.search(w, txt, re.I)]
        roman = sorted({m.group(0) for m in R08R.ROMAN.finditer(txt)} - R08R.ROMAN_OK)
        labels = R08R.dcml_label_strings(p["stem"])
        lab_hits = sorted(v for v in labels
                          if re.search(r"(?<![\w.])" + re.escape(v) + r"(?![\w])", txt))
        # extended identity check
        ident = [w for w in IDENTITY if re.search(w, txt, re.I)]
        dyn = sorted({m.group(0) for m in DYNAMICS.finditer(txt)})
        other = []
        if "[" in txt or "]" in txt:
            other.append("bracketed marking")
        if re.search(r"\bM[1-9]\b", txt):
            other.append("original id")
        # structure: bar table and pointer map
        bd = pd.read_csv(ART / f"bars_{did}.csv", dtype={"written": str})
        bm_ = pd.read_csv(C.ART / f"bars_{mid}.csv", dtype={"written": str})
        struct = (len(bd) == len(bm_)
                  and (bd["bar"] == bm_["bar"] + c).all()
                  and np.allclose(bd[["start", "end", "shift", "nominal"]],
                                  bm_[["start", "end", "shift", "nominal"]])
                  and (bd["ts"] == bm_["ts"]).all()
                  and (bd["fifths"] == bm_["fifths"] + k).all()
                  and all((w1 == str(int(w0) + c)) if w0.isdigit() else (w1 == w0)
                          for w0, w1 in zip(bm_["written"], bd["written"], strict=True)))
        pd_, pm_ = parse_pointers(txt), parse_pointers(orig)
        pointers_ok = pd_ == {a + c: b + c for a, b in pm_.items()}
        # transposition, token by token
        ld, lm = _note_lines(txt), _note_lines(orig)
        n_tok, bad_tok = 0, 0
        same_lines = 0
        if len(ld) == len(lm):
            for a, b in zip(ld, lm, strict=True):
                same_lines += a == b
                ta, tb = NOTE_TOKEN.findall(a), NOTE_TOKEN.findall(b)
                if len(ta) != len(tb):
                    bad_tok += 1
                    continue
                for (s1, a1, o1), (s0, a0, o0) in zip(ta, tb, strict=True):
                    n_tok += 1
                    f1 = spell_fifths(s1, ACC_INV[a1 or ""])
                    f0 = spell_fifths(s0, ACC_INV[a0 or ""])
                    m1 = token_midi(s1, ACC_INV[a1 or ""], int(o1))
                    m0 = token_midi(s0, ACC_INV[a0 or ""], int(o0))
                    bad_tok += (f1 - f0 != k) or (m1 - m0 != s)
            lines_ok = True
        else:
            lines_ok = False
        kd, km = _key_fifths(txt), _key_fifths(orig)
        keys_ok = len(kd) == len(km) and all(a == b + k for a, b in zip(kd, km, strict=True))
        passed = (not hits and not roman and not lab_hits and not ident and not dyn
                  and not other and struct and pointers_ok and lines_ok and bad_tok == 0
                  and keys_ok)
        ok &= passed
        print(f"{did}: {len(txt):,} chars; banned {hits}, roman {roman[:8]}, dcml {lab_hits[:8]} "
              f"(of {len(labels)}), identity {ident}, dynamics {dyn}, other {other}; "
              f"bar table {'OK' if struct else 'MISMATCH'}, pointers "
              f"{'OK' if pointers_ok else 'MISMATCH'} ({len(pd_)}), onset lines "
              f"{len(ld)} vs {len(lm)}, note tokens {n_tok} checked, {bad_tok} bad, "
              f"{same_lines} onset lines identical to R-08a, key signatures "
              f"{'OK' if keys_ok else 'MISMATCH'} -> {'PASS' if passed else 'FAIL'}")
    for extra in ("INSTRUCTIONS.md", "SCHEMA.json"):
        t = (BLIND / extra).read_text()
        ident = [w for w in IDENTITY if re.search(w, t, re.I)]
        lab = sorted({v for p in ps for v in R08R.dcml_label_strings(p["stem"])
                      if len(v) >= 4 and re.search(r"(?<![\w.])" + re.escape(v) + r"(?![\w])", t)})
        mids = re.findall(r"\bM[1-9]\b", t)
        good = not ident and not lab and not mids
        ok &= good
        print(f"{extra}: identity {ident}, dcml-label strings {lab[:8]}, original ids {mids} -> "
              f"{'PASS' if good else 'FAIL'}")
    print("DISGUISE CHECK", "PASSED" if ok else "FAILED")
    return ok


def hashes() -> dict[str, str]:
    files = [HERE / "disguise.py", HERE / "score.py", *sorted(BLIND.iterdir())]
    return {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in files if f.is_file()}


if __name__ == "__main__":
    if "--check" not in sys.argv:
        main()
    ok = check()
    if "--hashes" in sys.argv:
        print(json.dumps(hashes(), indent=1))
    sys.exit(0 if ok else 1)
