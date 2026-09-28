"""R-08a: write the label-free score renderings (blind_input/M*.txt), the bar tables and the
hidden ground truth (artifacts/), then run the leakage check.

    uv run python experiments/2026-09-28-R-08a-llm-phrase-pilot/render.py          # render + check
    uv run python experiments/2026-09-28-R-08a-llm-phrase-pilot/render.py --check  # check only
"""

from __future__ import annotations

import json
import re
import sys

import pandas as pd
from common import ART, BLIND, load_score, render, selection

# vocabulary of the annotation files that must never appear in a rendering
BANNED_WORDS = [r"\bPAC\b", r"\bIAC\b", r"\bHC\b", r"\bEC\b", r"\bDC\b", r"cadenc", r"phrase",
                r"[{}]", r"harmon", r"chord", r"tonic", r"dominant", r"\broot\b",
                r"\bmajor\b", r"\bminor\b", r"\bkey of\b", r"modulat", r"\bKV?\s?\d{3}",
                r"k(ö|oe)chel", r"mozart", r"sonat"]
# Roman-numeral chord labels (DCML style: V7, I64, viio7, V/V, #viio, It6, Ger65 ...)
ROMAN = re.compile(r"(?<![A-Za-z])(#|b)?(i{1,3}|iv|vi{0,2}|I{1,3}|IV|VI{0,2})"
                   r"(o|%|\+|M)?(\d{1,2})?(/[#b]?(i{1,3}|iv|vi{0,2}|I{1,3}|IV|VI{0,2}))?"
                   r"(?![A-Za-z#])")
# words of the rendering that legitimately match ROMAN (none expected)
ROMAN_OK: set[str] = set()


def dcml_label_strings(stem: str) -> set[str]:
    """Distinct DCML harmony / cadence / phrase label strings of the movement (length >= 3,
    so that short strings like 'I' are covered by ROMAN instead)."""
    from pianolens.data import batik_mozart as bm

    out: set[str] = set()
    for kind in ("harmony", "cadence", "phrases", "annotated"):
        df = bm.load_note_annotations(stem, kind)
        for c in df.columns:
            if c in ("id", "onset_beat", "duration_beat", "onset_quarter", "duration_quarter",
                     "pitch", "voice", "staff", "onset_div", "duration_div", "mn", "xml_mn",
                     "divs_pq", "ts_beats", "ts_beat_type", "ts_mus_beats", "is_grace",
                     "grace_type", "steal_proportion", "local_grace_order", "step", "alter",
                     "octave", "ks_fifths", "ks_mode", "timesig", "globalkey", "quarterbeats",
                     "duration_qb", "mc", "mc_onset", "mn_onset"):
                continue
            if not pd.api.types.is_numeric_dtype(df[c]):
                for v in df[c].dropna().astype(str):
                    v = v.strip()
                    if len(v) >= 3 and not re.fullmatch(r"[\d.\s-]+", v):
                        out.add(v)
    return out


def check() -> bool:
    ok = True
    for p in selection():
        txt = (BLIND / f"{p['id']}.txt").read_text()
        body = txt
        hits = [w for w in BANNED_WORDS if re.search(w, body, re.I)]
        roman = sorted({m.group(0) for m in ROMAN.finditer(body)} - ROMAN_OK)
        labels = dcml_label_strings(p["stem"])
        lab_hits = sorted(v for v in labels if re.search(r"(?<![\w.])" + re.escape(v)
                                                         + r"(?![\w])", body))
        print(f"{p['id']}: {len(txt):,} chars, banned {hits}, roman {roman[:10]}, "
              f"dcml-label strings {lab_hits[:10]} (of {len(labels)} checked)")
        ok &= not hits and not roman and not lab_hits
    for extra in ("INSTRUCTIONS.md", "SCHEMA.json"):
        f = BLIND / extra
        if f.exists():
            t = f.read_text()
            lab_hits = [v for p in selection() for v in dcml_label_strings(p["stem"])
                        if len(v) >= 4 and re.search(r"(?<![\w.])" + re.escape(v) + r"(?![\w])", t)]
            print(f"{extra}: dcml-label strings {sorted(set(lab_hits))[:10]}")
    print("LEAKAGE CHECK", "PASSED" if ok else "FAILED")
    return ok


def main() -> None:
    from pianolens.data import batik_mozart as bm

    BLIND.mkdir(exist_ok=True)
    (ART / "ground_truth").mkdir(parents=True, exist_ok=True)
    sizes = []
    for p in selection():
        mid, stem = p["id"], p["stem"]
        score = load_score(stem)
        r = render(score, mid)
        (BLIND / f"{mid}.txt").write_text(r.text)
        r.bars.to_csv(ART / f"bars_{mid}.csv", index=False)
        ann = bm.phrase_annotations(score)
        gt = {"id": mid, "stem": stem, "starts": ann.starts, "ends": ann.ends,
              "cadences": ann.cadence_table().to_dict(orient="records"),
              "n_unmapped": ann.n_unmapped}
        (ART / "ground_truth" / f"{mid}.json").write_text(json.dumps(gt, indent=1))
        sizes.append({"id": mid, "stem": stem, "bars": len(r.bars),
                      "pointer_bars": r.n_pointer_bars, "chars": len(r.text),
                      "lines": r.text.count("\n"), "words": len(r.text.split()),
                      "tokens_est_chars_div_3": round(len(r.text) / 3)})
        print(sizes[-1], flush=True)
    pd.DataFrame(sizes).to_csv(ART / "render_sizes.csv", index=False)


if __name__ == "__main__":
    if "--check" not in sys.argv:
        main()
    sys.exit(0 if check() else 1)
