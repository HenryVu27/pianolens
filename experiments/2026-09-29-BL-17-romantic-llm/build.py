"""BL-17: write the disguised renderings (blind_input/P##.txt, R-08b's disguise on R-08d's DCML
scores), the undisguised renderings of the U subset (blind_input_U/P##.txt, R-08d's rendering),
bar tables and hidden ground truth (artifacts/), INSTRUCTIONS.md and SCHEMA.json for both, then
run the leakage, identity, disguise and structure checks.

    uv run python .../build.py            # build + check
    uv run python .../build.py --check    # check only
    uv run python .../build.py --hashes   # sha256 list

Reuse (imported, never changed): R-08a ``common.render`` (renderer), R-08b ``disguise.py``
(``disguised`` context manager, line-of-fifths respelling, ``choose_k``, ``parse_pointers``,
``DYNAMICS``, ``NOTE_TOKEN``), R-08d ``build.py`` (``load`` with the identity rule for printed
text, ``hits``, ``text_hits``, ``label_strings``, ``TITLES``), R-08a ``render.py`` vocabulary.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import logging
import re
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
EXP = ROOT / "experiments"
R08A = EXP / "2026-09-28-R-08a-llm-phrase-pilot"
R08B = EXP / "2026-09-28-R-08b-llm-memorisation-control"
R08D = EXP / "2026-09-28-R-08d-llm-romantic-repertoire"
sys.path.insert(0, str(R08A))
warnings.filterwarnings("ignore")
logging.disable(logging.WARNING)

import common as C  # noqa: E402  (R-08a renderer, unchanged)


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


DG = _load("r08b_disguise", R08B / "disguise.py")  # writes nothing at import
BD = _load("r08d_build", R08D / "build.py")  # writes nothing at import

from pianolens.data import dcml  # noqa: E402

ART = HERE / "artifacts"
BLIND = HERE / "blind_input"  # disguised: INSTRUCTIONS.md, SCHEMA.json, P##.txt
BLIND_U = HERE / "blind_input_U"  # undisguised subset
OLD_IDS = re.compile(r"\b[MQR][1-9]\b")  # D1..D5 are note names in a rendering


def selection() -> list[dict]:
    return json.loads((ART / "selection.json").read_text())["picks"]


def params() -> dict[str, dict]:
    return json.loads((ART / "disguise.json").read_text())


# --------------------------------------------------------------------------- disguise


def choose_k(score, s: int, fifths: list[int]) -> tuple[int, list[int]]:
    """R-08b's k rule; if its k would need a triple accidental somewhere in the movement, the
    other candidate k (7k = s mod 12, |k| <= 11) is used (README "Disguise")."""
    import partitura as pt

    k0 = DG.choose_k(s, fifths)
    cands = [k0] + [k for k in ((7 * s) % 12, (7 * s) % 12 - 12) if k != k0 and -11 <= k <= 11]
    notes = list(score.part.iter_all(pt.score.Note, include_subclasses=True))
    tried = []
    for k in cands:
        try:
            for n in notes:
                DG.transpose_spelling(n.step, int(n.alter or 0), int(n.midi_pitch), s, k)
            return k, tried
        except ValueError:
            tried.append(k)
    raise ValueError(f"no k without triple accidentals for s={s} (tried {tried})")


def render_disguised(score, mid: str, s: int, k: int, c: int) -> C.Rendering:
    with DG.disguised(s, k, c):
        r = C.render(score, mid)
    text = r.text.replace("same notes and markings as", "same notes as")
    return C.Rendering(text, r.bars, r.n_pointer_bars)


# --------------------------------------------------------------------------- instructions

R08D_TEXT = [
    ("five text renderings of piano movements (`R1.txt` to `R5.txt`). For each movement, mark",
     "a text rendering of one piano movement (the `.txt` file in this folder). Mark"),
    ("this file, `SCHEMA.json` and `R1.txt`..`R5.txt`.",
     "this file, `SCHEMA.json` and the one `.txt` rendering."),
    ("For each movement, write one JSON file named `R1.json` .. `R5.json` that follows",
     "Write one JSON file, named after the rendering (`P01.txt` -> `P01.json`), that follows"),
    ('"movement": "R1"', '"movement": "P01"'),
]


def write_instructions(folder: Path, disguised: bool, pair: tuple[int, int]) -> None:
    t = (R08D / "blind_input" / "INSTRUCTIONS.md").read_text()
    subs = list(R08D_TEXT)
    if disguised:
        subs.append(('"same notes and markings as bar(s) ..."', '"same notes as bar(s) ..."'))
    for a, b in subs:
        assert t.count(a) == 1, a
        t = t.replace(a, b)
    r08d_pair = tuple(json.loads((R08D / "artifacts" / "example_bars.json").read_text())["bars"])
    if pair != r08d_pair:
        for old, new in zip(r08d_pair, pair, strict=True):
            a = f'"bar": {old},'
            assert a in t, a
            t = t.replace(a, f'"bar": {new},')
    assert not re.search(r"\bR\d\b", t), re.findall(r".{20}\bR\d\b.{20}", t)
    folder.mkdir(exist_ok=True)
    (folder / "INSTRUCTIONS.md").write_text(t)
    sch = json.loads((R08D / "blind_input" / "SCHEMA.json").read_text())
    sch["properties"]["movement"]["pattern"] = "^P[0-9]{2}$"
    sch["properties"]["movement"]["description"] = ("The id in the rendering's first line, "
                                                    "e.g. P01.")
    (folder / "SCHEMA.json").write_text(json.dumps(sch, indent=2) + "\n")


# --------------------------------------------------------------------------- build


def main() -> None:
    BLIND.mkdir(exist_ok=True)
    BLIND_U.mkdir(exist_ok=True)
    (ART / "ground_truth").mkdir(parents=True, exist_ok=True)
    sizes, removed_all, disg = [], {}, {}
    bars_u, gt_u = {}, {}
    for p in selection():
        mid = p["id"]
        score, removed = BD.load(p)
        removed_all[mid] = removed
        plain = C.bar_table(score)
        fifths = sorted({int(x) for x in plain["fifths"]})
        s, c = p["semitones"], p["bar_offset"]
        k, tried = choose_k(score, s, fifths)
        disg[mid] = {"semitones": s, "fifths_shift": k, "bar_offset": c, "fifths_orig": fifths,
                     "fifths_new": [f + k for f in fifths], "k_rejected": tried}
        r = render_disguised(score, mid, s, k, c)
        (BLIND / f"{mid}.txt").write_text(r.text)
        r.bars.to_csv(ART / f"bars_{mid}.csv", index=False)
        ann = dcml.phrase_annotations(score)
        ct = ann.cadence_table()
        gt = {"id": mid, "corpus": p["corpus"], "stem": p["stem"], "score_id": score.score_id,
              "starts": ann.starts, "ends": ann.ends, "cadences": ct.to_dict(orient="records"),
              "n_unmapped": ann.n_unmapped, "n_off_onset": ann.n_off_onset,
              "n_other": ann.n_other}
        (ART / "ground_truth" / f"{mid}.json").write_text(json.dumps(gt, indent=1))
        row = {"id": mid, "stratum": p["stratum"], "corpus": p["corpus"], "stem": p["stem"],
               "timesig": " ".join(dict.fromkeys(r.bars["ts"])), "bars": len(r.bars),
               "pointer_bars": r.n_pointer_bars, "chars": len(r.text),
               "lines": r.text.count("\n"), "words": len(r.text.split()),
               "ends": len(ann.ends), "starts": len(ann.starts), "cadences": len(ct),
               "labels_off_onset": ann.n_off_onset, "texts_removed": len(removed),
               "semitones": s, "fifths_shift": k, "bar_offset": c,
               "double_accidental_tokens": len(re.findall(r"[A-G](##|bb)-?\d", r.text)),
               "note_tokens": len(DG.NOTE_TOKEN.findall(r.text))}
        if p["undisguised_run"]:
            ru = C.render(score, mid)
            (BLIND_U / f"{mid}.txt").write_text(ru.text)
            ru.bars.to_csv(ART / f"bars_U_{mid}.csv", index=False)
            bars_u[mid], gt_u[mid] = ru.bars, gt
            row.update({"U_chars": len(ru.text), "U_pointer_bars": ru.n_pointer_bars})
        sizes.append(row)
        print(row, flush=True)
    pd.DataFrame(sizes).to_csv(ART / "render_sizes.csv", index=False)
    (ART / "identity_removals.json").write_text(json.dumps(removed_all, indent=1,
                                                           ensure_ascii=False))
    (ART / "disguise.json").write_text(json.dumps(disg, indent=1))
    # disguised: bar numbers start at c + 1 >= 21, so R-08d's example bars (4, 7) never exist
    r08d_pair = tuple(json.loads((R08D / "artifacts" / "example_bars.json").read_text())["bars"])
    write_instructions(BLIND, True, r08d_pair)
    # U: R-08d's collision rule on the U movements, starting from R-08d's pair
    pair = r08d_pair
    while not BD.example_clear(bars_u, gt_u, pair):
        pair = (pair[0] + 1, pair[1] + 1)
    print(f"U worked example bars: {pair} ({'unchanged' if pair == r08d_pair else 'MOVED'})")
    (ART / "example_bars_U.json").write_text(json.dumps({"bars": list(pair)}))
    write_instructions(BLIND_U, False, pair)


# --------------------------------------------------------------------------- check


def _note_lines(text: str) -> list[str]:
    return [re.sub(r" \| \[.*\]$", "", ln) for ln in text.splitlines() if re.match(r"^\s+\d", ln)]


def disguise_check(p: dict, txt: str, score) -> tuple[bool, str]:
    """Token-by-token transposition against the same renderer with s = k = c = 0 (markings
    dropped the same way), structure against the plain bar table, pointers shifted by c."""
    d = params()[p["id"]]
    s, k, c = d["semitones"], d["fifths_shift"], d["bar_offset"]
    neutral = render_disguised(score, p["id"], 0, 0, 0).text
    bd = pd.read_csv(ART / f"bars_{p['id']}.csv", dtype={"written": str})
    bp = C.bar_table(score)
    bp["written"] = bp["written"].astype(str)
    struct = (len(bd) == len(bp) and (bd["bar"] == bp["bar"] + c).all()
              and np.allclose(bd[["start", "end", "shift", "nominal"]],
                              bp[["start", "end", "shift", "nominal"]])
              and (bd["ts"] == bp["ts"]).all() and (bd["fifths"] == bp["fifths"] + k).all()
              and all((w1 == str(int(w0) + c)) if w0.isdigit() else (w1 == w0)
                      for w0, w1 in zip(bp["written"], bd["written"], strict=True)))
    pd_, pn = DG.parse_pointers(txt), DG.parse_pointers(neutral)
    pointers_ok = pd_ == {a + c: b + c for a, b in pn.items()}
    ld, ln = _note_lines(txt), _note_lines(neutral)
    n_tok = bad = 0
    lines_ok = len(ld) == len(ln)
    if lines_ok:
        for a, b in zip(ld, ln, strict=True):
            ta, tb = DG.NOTE_TOKEN.findall(a), DG.NOTE_TOKEN.findall(b)
            if len(ta) != len(tb):
                bad += 1
                continue
            for (s1, a1, o1), (s0, a0, o0) in zip(ta, tb, strict=True):
                n_tok += 1
                f1 = DG.spell_fifths(s1, DG.ACC_INV[a1 or ""])
                f0 = DG.spell_fifths(s0, DG.ACC_INV[a0 or ""])
                m1 = DG.token_midi(s1, DG.ACC_INV[a1 or ""], int(o1))
                m0 = DG.token_midi(s0, DG.ACC_INV[a0 or ""], int(o0))
                bad += (f1 - f0 != k) or (m1 - m0 != s)
    kd, kn = DG._key_fifths(txt), DG._key_fifths(neutral)
    keys_ok = len(kd) == len(kn) and all(a == b + k for a, b in zip(kd, kn, strict=True))
    same_lines = sum(a == b for a, b in zip(ld, ln, strict=False))
    ok = struct and pointers_ok and lines_ok and bad == 0 and keys_ok and n_tok > 0
    return ok, (f"bar table {'OK' if struct else 'MISMATCH'}, pointers "
                f"{'OK' if pointers_ok else 'MISMATCH'} ({len(pd_)}), onset lines {len(ld)} vs "
                f"{len(ln)}, note tokens {n_tok} checked, {bad} bad, {same_lines} lines identical "
                f"to untransposed, keys {'OK' if keys_ok else 'MISMATCH'}")


def check() -> bool:
    ok = True
    picks = selection()
    for p in picks:
        mid = p["id"]
        score, _ = BD.load(p)
        for folder, kind in ((BLIND, "disguised"), (BLIND_U, "undisguised")):
            f = folder / f"{mid}.txt"
            if not f.exists():
                continue
            txt = f.read_text()
            h = BD.hits(txt, p["corpus"], p["stem"])
            h["old_ids"] = sorted(set(OLD_IDS.findall(txt)))
            if kind == "disguised":
                h["bracketed_marking"] = ["["] if ("[" in txt or "]" in txt) else []
                h["dynamics"] = sorted({m.group(0) for m in DG.DYNAMICS.finditer(txt)})
                good, msg = disguise_check(p, txt, score)
            else:
                good, msg = True, ""
            passed = good and not any(h.values())
            ok &= passed
            print(f"{mid} {kind}: {len(txt):,} chars; "
                  + "; ".join(f"{k} {v[:6]}" for k, v in h.items())
                  + (f"; {msg}" if msg else "") + f" -> {'PASS' if passed else 'FAIL'}")
            if kind == "undisguised":
                marks = sorted({m.strip() for g in re.findall(r"\| \[(.*)\]$", txt, re.M)
                                for m in g.split(", ")})
                print(f"   printed markings: {marks}")
    for folder in (BLIND, BLIND_U):
        for extra in ("INSTRUCTIONS.md", "SCHEMA.json"):
            t = (folder / extra).read_text()
            h = BD.text_hits(t, picks)
            h["old_ids_R"] = sorted(set(re.findall(r"\bR[1-9]\b", t)))
            print(f"{folder.name}/{extra}: " + "; ".join(f"{k} {v[:8]}" for k, v in h.items()))
            ok &= not any(h.values())
    # the check must fire on planted cues (every disguised rendering)
    for p in picks:
        base = (BLIND / f"{p['id']}.txt").read_text()
        lab = sorted(BD.label_strings(p["corpus"], p["stem"], 3), key=lambda v: (len(v), v))[-1]
        md = dcml.metadata(p["corpus"]).set_index("piece").loc[p["stem"]]
        own = [w.lower() for col in ("movementTitle", "workTitle")
               for w in re.findall(r"[^\W\d_]{4,}", str(md[col])) if w.lower() in BD.TITLES]
        plants = {"label": f"\n  1  RH {lab} 1\n", "roman": " V7 ", "banned": " PAC ",
                  "composer": " Chopin ", "composer2": " Grieg ", "catalogue": " op. 68 ",
                  "stem": f" {p['stem']} ", "old id": " R3 ", "marking": " [p] "}
        if own:
            plants["title"] = f" {own[0].capitalize()} "

        def fires(t: str, p: dict = p) -> bool:
            h = BD.hits(t, p["corpus"], p["stem"])
            return (any(h.values()) or bool(OLD_IDS.search(t)) or "[" in t
                    or bool(DG.DYNAMICS.search(t)))

        fired = {k: fires(base + v) for k, v in plants.items()}
        if not all(fired.values()):
            print(f"planted cues in {p['id']}: {fired}")
        ok &= all(fired.values())
    print(f"planted cues checked in {len(picks)} disguised renderings")
    print("LEAKAGE CHECK", "PASSED" if ok else "FAILED")
    return ok


def hashes() -> dict[str, str]:
    files = [HERE / n for n in ("power.py", "draw.py", "build.py", "score.py")]
    files += sorted(BLIND.iterdir()) + sorted(BLIND_U.iterdir())
    files += [R08A / "common.py", R08A / "render.py", R08A / "score.py", R08B / "disguise.py",
              R08D / "build.py", R08D / "draw.py", R08D / "score.py"]
    out = {str(f.relative_to(ROOT)): hashlib.sha256(f.read_bytes()).hexdigest() for f in files
           if f.is_file()}
    for k, v in out.items():
        print(v, k)
    return out


if __name__ == "__main__":
    if "--hashes" in sys.argv:
        hashes()
        sys.exit(0)
    if "--check" not in sys.argv:
        main()
    sys.exit(0 if check() else 1)
