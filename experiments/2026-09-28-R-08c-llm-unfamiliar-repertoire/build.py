"""R-08c: write the label-free J. C. Bach renderings (blind_input/Q#.txt) with R-08a's renderer,
the bar tables and hidden ground truth (artifacts/), INSTRUCTIONS.md and SCHEMA.json (R-08a's,
ids M -> Q), then run the leakage and identity check.

    uv run python .../build.py            # build + check
    uv run python .../build.py --check    # check only
    uv run python .../build.py --hashes   # sha256 list

Nothing here reads ``harmonies/`` for a rendering: scores come from
``dcml_jc_bach.load_score(stem, tempo_word=False)`` (label-free TSV facets only). The labels
are read only for the hidden ground truth and for the leakage check.
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

from pianolens.data import dcml_jc_bach as jc  # noqa: E402

ART = HERE / "artifacts"
BLIND = HERE / "blind_input"
EXAMPLE_BARS = (3, 6)  # R-08a's worked example: bar 3 beat 2 start; bar 6 beat 2 end + start

IDENTITY = [
    # composers (R-08b's list plus J. C. Bach's names)
    r"\bbach\b", r"christian", r"johann", r"london", r"\bJ\.\s?C\.", r"mozart", r"wolfgang",
    r"amadeus", r"haydn", r"beethoven", r"clementi", r"schubert", r"ko(ž|z)eluc?h", r"dussek",
    r"pleyel", r"scarlatti", r"h(a|ä)ndel", r"chopin", r"schumann", r"mendelssohn", r"salieri",
    r"hummel", r"vanhal", r"cramer", r"abel\b",
    # catalogue numbers and file stems
    r"\bop\.?\s?\d", r"\bopus\b", r"k(ö|oe)chel", r"verzeichnis", r"\bKV?\.?\s?\d{2,3}",
    r"\bKV\b", r"\bwq\b", r"\bhob\b", r"\bwarb", r"\bwa\d\d", r"op0?5", r"op17",
    # genre words that name the work
    r"sonat",
    # provenance
    r"dcml", r"jc_?bach", r"pianolens", r"batik", r"/users/", r"experiments/", r"\bms3\b",
    r"mscx", r"harmonies",
]
OLD_IDS_RENDER = re.compile(r"\bM[1-9]\b")  # D1..D5 are also note names, so not checked here
OLD_IDS_TEXT = re.compile(r"\b[MD][1-9]\b")


def selection() -> list[dict]:
    return json.loads((ART / "selection.json").read_text())["picks"]


def title_of(stem: str) -> str:
    return str(jc.metadata().set_index("piece").loc[stem, "movementTitle"]).strip()


def label_strings(stem: str, min_len: int) -> set[str]:
    return {v for v in jc.label_strings(stem, min_len=min_len)
            if not re.fullmatch(r"[\d.,\s-]+", v)}


def title_patterns(stem: str) -> list[str]:
    t = title_of(stem)
    words = [w for w in re.split(r"[\s_]+", t) if len(w) >= 4]
    return [re.escape(t)] + [r"\b" + re.escape(w) + r"\b" for w in words]


def hits(text: str, stem: str) -> dict[str, list[str]]:
    labels = label_strings(stem, 3)
    return {
        "banned": [w for w in R8.BANNED_WORDS if re.search(w, text, re.I)],
        "roman": sorted({m.group(0) for m in R8.ROMAN.finditer(text)}),
        "labels": sorted(v for v in labels
                         if re.search(r"(?<![\w.])" + re.escape(v) + r"(?![\w])", text)),
        "identity": [w for w in IDENTITY if re.search(w, text, re.I)],
        "title": [w for w in title_patterns(stem) if re.search(w, text, re.I)],
        "old_ids": sorted(set(OLD_IDS_RENDER.findall(text))),
    }


def text_hits(text: str, stems: list[str]) -> dict[str, list[str]]:
    """INSTRUCTIONS.md / SCHEMA.json: label strings of length >= 4 over all movements (the
    cadence names are part of the task), identity words, titles, old ids."""
    labels = set().union(*(label_strings(s, 4) for s in stems))
    return {
        "labels": sorted(v for v in labels
                         if re.search(r"(?<![\w.])" + re.escape(v) + r"(?![\w])", text)),
        "identity": [w for w in IDENTITY if re.search(w, text, re.I)],
        "title": sorted({w for s in stems for w in title_patterns(s)
                         if re.search(w, text, re.I)}),
        "old_ids": sorted(set(OLD_IDS_TEXT.findall(text))),
    }


# --------------------------------------------------------------------------- build


def example_clear(bars_by_id: dict[str, pd.DataFrame], gt_by_id: dict[str, dict],
                  pair: tuple[int, int]) -> bool:
    """True if (pair[0], beat 2) and (pair[1], beat 2) are > 1 beat from every DCML phrase end
    and start of every drawn movement."""
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
    for a, b in (("(`M1.txt` to\n`M5.txt`)", "(`Q1.txt` to\n`Q5.txt`)"),
                 ("`M1.txt`..`M5.txt`", "`Q1.txt`..`Q5.txt`"),
                 ("`M1.json` .. `M5.json`", "`Q1.json` .. `Q5.json`"),
                 ('"movement": "M1"', '"movement": "Q1"')):
        assert t.count(a) == 1, a
        t = t.replace(a, b)
    if pair != EXAMPLE_BARS:
        for old, new in zip(EXAMPLE_BARS, pair, strict=True):
            a = f'"bar": {old},'
            assert a in t, a
            t = t.replace(a, f'"bar": {new},')
    assert not re.search(r"\bM\d\b", t), re.findall(r".{20}\bM\d\b.{20}", t)
    (BLIND / "INSTRUCTIONS.md").write_text(t)
    sch = json.loads((C.BLIND / "SCHEMA.json").read_text())
    sch["properties"]["movement"]["pattern"] = "^Q[1-9]$"
    sch["properties"]["movement"]["description"] = "The id in the rendering's first line, e.g. Q1."
    (BLIND / "SCHEMA.json").write_text(json.dumps(sch, indent=2) + "\n")


def main() -> None:
    BLIND.mkdir(exist_ok=True)
    (ART / "ground_truth").mkdir(parents=True, exist_ok=True)
    sizes, bars_by_id, gt_by_id = [], {}, {}
    for p in selection():
        mid, stem = p["id"], p["stem"]
        score = jc.load_score(stem, tempo_word=False)
        r = C.render(score, mid)
        (BLIND / f"{mid}.txt").write_text(r.text)
        r.bars.to_csv(ART / f"bars_{mid}.csv", index=False)
        ann = jc.phrase_annotations(score)
        gt = {"id": mid, "stem": stem, "starts": ann.starts, "ends": ann.ends,
              "cadences": ann.cadence_table().to_dict(orient="records"),
              "n_unmapped": ann.n_unmapped, "n_off_onset": ann.n_off_onset,
              "n_other": ann.n_other}
        (ART / "ground_truth" / f"{mid}.json").write_text(json.dumps(gt, indent=1))
        bars_by_id[mid], gt_by_id[mid] = r.bars, gt
        sizes.append({"id": mid, "stem": stem, "timesig": r.bars["ts"].iloc[0],
                      "bars": len(r.bars), "pointer_bars": r.n_pointer_bars,
                      "chars": len(r.text), "lines": r.text.count("\n"),
                      "words": len(r.text.split()),
                      "tokens_est_chars_div_3": round(len(r.text) / 3),
                      "ends": len(ann.ends), "starts": len(ann.starts),
                      "cadences": len(ann.cadence_table()), "labels_off_onset": ann.n_off_onset})
        print(sizes[-1], flush=True)
    pd.DataFrame(sizes).to_csv(ART / "render_sizes.csv", index=False)
    # worked example: keep R-08a's bars unless they touch a DCML boundary (README rule)
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
    stems = [p["stem"] for p in picks]
    for p in picks:
        txt = (BLIND / f"{p['id']}.txt").read_text()
        h = hits(txt, p["stem"])
        n_lab = len(label_strings(p["stem"], 3))
        print(f"{p['id']} ({p['stem']}): {len(txt):,} chars; "
              + "; ".join(f"{k} {v[:8]}" for k, v in h.items())
              + f" (of {n_lab} label strings checked)")
        ok &= not any(h.values())
        marks = sorted({m.strip() for g in re.findall(r"\| \[(.*)\]$", txt, re.M)
                        for m in g.split(", ")})
        print(f"   printed markings: {marks}")
    for extra in ("INSTRUCTIONS.md", "SCHEMA.json"):
        h = text_hits((BLIND / extra).read_text(), stems)
        print(f"{extra}: " + "; ".join(f"{k} {v[:8]}" for k, v in h.items()))
        ok &= not any(h.values())
    # the check must fire on planted cues
    p0 = picks[0]
    base = (BLIND / f"{p0['id']}.txt").read_text()
    lab = sorted(label_strings(p0["stem"], 3), key=lambda v: (len(v), v))[-1]
    plants = {"label": f"\n  1  RH {lab} 1\n", "roman": " V7 ", "banned": " PAC ",
              "composer": " Bach ", "catalogue": " op. 5 ", "stem": " wa05 ",
              "title": f" {title_of(p0['stem'])} ", "old id": " M3 "}
    fired = {k: any(hits(base + v, p0["stem"]).values()) for k, v in plants.items()}
    print(f"planted cues in {p0['id']} (label {lab!r}): {fired}")
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
