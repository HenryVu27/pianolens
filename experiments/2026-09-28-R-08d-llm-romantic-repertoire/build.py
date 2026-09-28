"""R-08d: write the label-free Romantic renderings (blind_input/R#.txt) with R-08a's renderer,
the bar tables and hidden ground truth (artifacts/), INSTRUCTIONS.md and SCHEMA.json (R-08a's,
ids M -> R, period phrase dropped), then run the leakage and identity check.

    uv run python .../build.py            # build + check
    uv run python .../build.py --check    # check only
    uv run python .../build.py --hashes   # sha256 list

Scores come from ``dcml.load_score(corpus, stem, tempo_word=False)`` (label-free TSV facets
only). The labels are read only for the hidden ground truth and for the leakage check.
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

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
R08A = ROOT / "experiments" / "2026-09-28-R-08a-llm-phrase-pilot"
sys.path.insert(0, str(R08A))
warnings.filterwarnings("ignore")
logging.disable(logging.WARNING)

import common as C  # noqa: E402  (R-08a renderer, unchanged)

_spec = importlib.util.spec_from_file_location("r08a_render", R08A / "render.py")
R8 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(R8)  # R-08a leakage vocabulary (BANNED_WORDS, ROMAN); writes nothing

from pianolens.data import dcml  # noqa: E402

ART = HERE / "artifacts"
BLIND = HERE / "blind_input"
EXAMPLE_BARS = (3, 6)  # R-08a's worked example: bar 3 beat 2 start; bar 6 beat 2 end + start
CORPORA = ("chopin_mazurkas", "grieg_lyric_pieces", "tchaikovsky_seasons",
           "schumann_kinderszenen", "liszt_pelerinage")
MONTHS = ("january", "february", "march", "april", r"(?-i:\bMay\b)", "june", "july", "august",
          "september", "october", "november", "december")
IDENTITY = [
    # composers of the 5 corpora, then R-08c's list
    r"chopin", r"fryderyk", r"fr(e|é)d(e|é)ric", r"grieg", r"edvard",
    r"t(s)?cha(i|j)kovsk", r"tschaikowsk", r"(c|č)ajkovsk", r"pyotr", r"ill?y?ich",
    r"schumann", r"robert", r"clara", r"liszt", r"\bfranz\b", r"ferenc",
    r"\bbach\b", r"mozart", r"haydn", r"beethoven", r"clementi", r"schubert", r"mendelssohn",
    r"brahms", r"field\b", r"hummel", r"scarlatti",
    # catalogue numbers
    r"\bop\.?\s?\d", r"\bopus\b", r"\bBI\s?\d", r"\bS\.\s?\d{2,3}", r"searle", r"\bTH\s?\d",
    r"\bKK\b", r"\bLW\b", r"\bB\.\s?\d",
    # file-stem patterns of the 5 corpora
    r"\bop\d\d", r"op37a", r"\bn\d\d\b", r"\b16[012]\.\d\d",
    # corpus words
    r"mazurk", r"lyric", r"lyrisch", r"season", r"kinderszen", r"p(e|è)l(e|è)rinage",
    r"ann(e|é)es", r"suisse", r"italie", r"venezia", r"napoli", *MONTHS,
    # genre word R-08a bans in its drop list
    r"sonat",
    # provenance
    r"dcml", r"pianolens", r"batik", r"/users/", r"experiments/", r"\bms3\b", r"mscx",
    r"harmonies",
]
# generic words that occur in titles but also in ordinary score text or in the renderer's
# template ("1 flat", "quasi", "presto", ...); fixed before any rendering was checked
# ("event" and a lower-case "may" were added after they hit R-08a's own INSTRUCTIONS.md text)
TITLE_STOP = {"from", "flat", "sharp", "minor", "quasi", "presto", "fast", "event"}
OLD_IDS_RENDER = re.compile(r"\b[MQ][1-9]\b")  # D1..D5 are note names, so not checked here
OLD_IDS_TEXT = re.compile(r"\b[MDQ][1-9]\b")


def selection() -> list[dict]:
    return json.loads((ART / "selection.json").read_text())["picks"]


def title_words() -> list[str]:
    """Every title word (4+ letters, lower case) of every movement of the 5 corpora, from the
    metadata titles and the stems, minus TITLE_STOP."""
    words: set[str] = set()
    for c in CORPORA:
        md = dcml.metadata(c)
        for col in ("workTitle", "movementTitle", "title_text", "subtitle_text"):
            if col in md:
                for v in md[col].dropna().astype(str):
                    words |= {w.lower() for w in re.findall(r"[^\W\d_]{4,}",
                                                            re.sub(r"<[^>]*>", "", v))}
        for s in dcml.pieces(c):
            words |= {w.lower() for w in re.findall(r"[^\W\d_]{4,}", s)}
    return sorted(words - TITLE_STOP)


TITLES = title_words()


def identity_hits(text: str) -> list[str]:
    out = [w for w in IDENTITY if re.search(w, text, re.I)]
    out += [w for w in TITLES if re.search(r"(?<![^\W\d_])" + re.escape(w) + r"(?![^\W\d_])",
                                          text, re.I)]
    return out


def label_strings(corpus: str, stem: str, min_len: int) -> set[str]:
    return {v for v in dcml.label_strings(corpus, stem, min_len=min_len)
            if not re.fullmatch(r"[\d.,\s-]+", v)}


def hits(text: str, corpus: str, stem: str) -> dict[str, list[str]]:
    labels = label_strings(corpus, stem, 3)
    return {
        "banned": [w for w in R8.BANNED_WORDS if re.search(w, text, re.I)],
        "roman": sorted({m.group(0) for m in R8.ROMAN.finditer(text)}),
        "labels": sorted(v for v in labels
                         if re.search(r"(?<![\w.])" + re.escape(v) + r"(?![\w])", text)),
        "identity": identity_hits(text),
        "old_ids": sorted(set(OLD_IDS_RENDER.findall(text))),
    }


def text_hits(text: str, picks: list[dict]) -> dict[str, list[str]]:
    """INSTRUCTIONS.md / SCHEMA.json: label strings of length >= 4 over all movements (the
    cadence names are part of the task), identity and title words, old ids."""
    labels = set().union(*(label_strings(p["corpus"], p["stem"], 4) for p in picks))
    return {
        "labels": sorted(v for v in labels
                         if re.search(r"(?<![\w.])" + re.escape(v) + r"(?![\w])", text)),
        "identity": identity_hits(text),
        "old_ids": sorted(set(OLD_IDS_TEXT.findall(text))),
    }


# --------------------------------------------------------------------------- build


def load(p: dict):
    """The drawn score with every printed text item that hits the identity check removed
    (README "Identity rule for printed text"). Returns (score, removed texts)."""
    import partitura as pt

    score = dcml.load_score(p["corpus"], p["stem"], tempo_word=False)
    part = score.part
    removed, seen = [], set()
    for cls in (pt.score.Words, pt.score.Direction):
        for d in list(part.iter_all(cls, include_subclasses=True)):
            if id(d) in seen:
                continue
            seen.add(id(d))
            txt = str(getattr(d, "text", "") or "").strip()
            if txt and identity_hits(txt):
                removed.append({"text": txt, "hits": identity_hits(txt),
                                "t": int(d.start.t)})
                part.remove(d)
    return score, removed


def example_clear(bars_by_id: dict[str, pd.DataFrame], gt_by_id: dict[str, dict],
                  pair: tuple[int, int]) -> bool:
    """True if (pair[0], beat 2) and (pair[1], beat 2) are > 1 beat from every DCML phrase end
    and start of every drawn movement (a position that does not exist counts as clear)."""
    for mid, bars in bars_by_id.items():
        gt = gt_by_id[mid]
        for b in pair:
            x = C.to_perf_beat(bars, b, 2.0)
            if x is None:
                continue
            if any(abs(x - y) <= 1.0 + 1e-6 for y in gt["ends"] + gt["starts"]):
                return False
    return True


def write_instructions(pair: tuple[int, int]) -> None:
    t = (C.BLIND / "INSTRUCTIONS.md").read_text()
    for a, b in (("piano movements from the Classical period (`M1.txt` to\n`M5.txt`)",
                  "piano movements (`R1.txt` to `R5.txt`)"),
                 ("`M1.txt`..`M5.txt`", "`R1.txt`..`R5.txt`"),
                 ("`M1.json` .. `M5.json`", "`R1.json` .. `R5.json`"),
                 ('"movement": "M1"', '"movement": "R1"')):
        assert t.count(a) == 1, a
        t = t.replace(a, b)
    if pair != EXAMPLE_BARS:
        for old, new in zip(EXAMPLE_BARS, pair, strict=True):
            a = f'"bar": {old},'
            assert a in t, a
            t = t.replace(a, f'"bar": {new},')
    assert not re.search(r"\bM\d\b", t), re.findall(r".{20}\bM\d\b.{20}", t)
    assert "Classical" not in t and "period" not in t
    (BLIND / "INSTRUCTIONS.md").write_text(t)
    sch = json.loads((C.BLIND / "SCHEMA.json").read_text())
    sch["properties"]["movement"]["pattern"] = "^R[1-9]$"
    sch["properties"]["movement"]["description"] = "The id in the rendering's first line, e.g. R1."
    (BLIND / "SCHEMA.json").write_text(json.dumps(sch, indent=2) + "\n")


def main() -> None:
    BLIND.mkdir(exist_ok=True)
    (ART / "ground_truth").mkdir(parents=True, exist_ok=True)
    sizes, bars_by_id, gt_by_id, removed_all = [], {}, {}, {}
    for p in selection():
        mid, corpus, stem = p["id"], p["corpus"], p["stem"]
        score, removed = load(p)
        removed_all[mid] = removed
        r = C.render(score, mid)
        (BLIND / f"{mid}.txt").write_text(r.text)
        r.bars.to_csv(ART / f"bars_{mid}.csv", index=False)
        ann = dcml.phrase_annotations(score)
        ct = ann.cadence_table()
        gt = {"id": mid, "corpus": corpus, "stem": stem, "score_id": score.score_id,
              "starts": ann.starts, "ends": ann.ends,
              "cadences": ct.to_dict(orient="records"),
              "n_unmapped": ann.n_unmapped, "n_off_onset": ann.n_off_onset,
              "n_other": ann.n_other}
        (ART / "ground_truth" / f"{mid}.json").write_text(json.dumps(gt, indent=1))
        bars_by_id[mid], gt_by_id[mid] = r.bars, gt
        staves = sorted({int(x) for x in score.notes["staff"]})
        sizes.append({"id": mid, "corpus": corpus, "stem": stem,
                      "timesig": " ".join(dict.fromkeys(r.bars["ts"])),
                      "bars": len(r.bars), "pointer_bars": r.n_pointer_bars,
                      "chars": len(r.text), "lines": r.text.count("\n"),
                      "words": len(r.text.split()),
                      "tokens_est_chars_div_3": round(len(r.text) / 3),
                      "staves": " ".join(map(str, staves)),
                      "ends": len(ann.ends), "starts": len(ann.starts),
                      "cadences": len(ct), "labels_off_onset": ann.n_off_onset,
                      "texts_removed": len(removed)})
        print(sizes[-1], flush=True)
    pd.DataFrame(sizes).to_csv(ART / "render_sizes.csv", index=False)
    (ART / "identity_removals.json").write_text(json.dumps(removed_all, indent=1,
                                                           ensure_ascii=False))
    print("identity removals:", json.dumps(removed_all, ensure_ascii=False))
    pair = EXAMPLE_BARS
    while not example_clear(bars_by_id, gt_by_id, pair):
        pair = (pair[0] + 1, pair[1] + 1)
    print(f"worked example bars: {pair} ({'unchanged' if pair == EXAMPLE_BARS else 'MOVED'})")
    (ART / "example_bars.json").write_text(json.dumps({"bars": list(pair)}))
    write_instructions(pair)


# --------------------------------------------------------------------------- check


def check() -> bool:
    ok = True
    picks = selection()
    for p in picks:
        txt = (BLIND / f"{p['id']}.txt").read_text()
        h = hits(txt, p["corpus"], p["stem"])
        n_lab = len(label_strings(p["corpus"], p["stem"], 3))
        print(f"{p['id']}: {len(txt):,} chars; "
              + "; ".join(f"{k} {v[:8]}" for k, v in h.items())
              + f" (of {n_lab} label strings checked)")
        ok &= not any(h.values())
        marks = sorted({m.strip() for g in re.findall(r"\| \[(.*)\]$", txt, re.M)
                        for m in g.split(", ")})
        print(f"   printed markings: {marks}")
    for extra in ("INSTRUCTIONS.md", "SCHEMA.json"):
        h = text_hits((BLIND / extra).read_text(), picks)
        print(f"{extra}: " + "; ".join(f"{k} {v[:8]}" for k, v in h.items()))
        ok &= not any(h.values())
    # the check must fire on planted cues, in every rendering
    for p in picks:
        base = (BLIND / f"{p['id']}.txt").read_text()
        lab = sorted(label_strings(p["corpus"], p["stem"], 3), key=lambda v: (len(v), v))[-1]
        md = dcml.metadata(p["corpus"]).set_index("piece").loc[p["stem"]]
        own = [w.lower() for c in ("movementTitle", "workTitle")
               for w in re.findall(r"[^\W\d_]{4,}", str(md[c])) if w.lower() in TITLES]
        plants = {"label": f"\n  1  RH {lab} 1\n", "roman": " V7 ", "banned": " PAC ",
                  "composer": " Chopin ", "composer2": " Liszt ", "catalogue": " op. 68 ",
                  "stem": f" {p['stem']} ", "title": f" {own[0].capitalize()} ",
                  "old id": " Q3 ", "month": " May "}
        fired = {k: any(hits(base + v, p["corpus"], p["stem"]).values())
                 for k, v in plants.items()}
        print(f"planted cues in {p['id']} (label {lab!r}, title word {own[0]!r}): {fired}")
        ok &= all(fired.values())
    print("LEAKAGE CHECK", "PASSED" if ok else "FAILED")
    return ok


def hashes() -> dict[str, str]:
    files = [HERE / n for n in ("draw.py", "build.py", "score.py")]
    files += [BLIND / n for n in ("INSTRUCTIONS.md", "SCHEMA.json")]
    files += [BLIND / f"{p['id']}.txt" for p in selection()]
    files += [R08A / n for n in ("common.py", "render.py", "score.py")]
    out = {str(f.relative_to(ROOT)): hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
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
