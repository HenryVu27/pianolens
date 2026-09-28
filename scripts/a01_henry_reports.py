"""A-01: F-08 practice reports for Henry's 5 phone takes, from both transcriptions.

    uv run python scripts/a01_henry_reports.py

Primary report: Transkun MIDI (``<k>_<slug>.html``); cross-check: Aria-AMT MIDI
(``<k>_<slug>_aria.html``). Both use the PianoCoRe MusicXML score and the piece's PianoCoRe tier A
references, provenance ``transcribed`` (so velocity is low confidence and not practise-eligible).
Each report carries a note with the per-piece transcription floor measured by
``scripts/a01_henry_baseline.py`` (run that first).

Stability: for every tiered issue (category, channel, bar) the script records whether the other
transcriber's report tiers the same bar for the same channel. Writes
``data/interim/reports/henry/`` (gitignored; personal data, never commit).
"""

from __future__ import annotations

import json
import logging
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data" / "interim" / "henry_takes"
OUT = ROOT / "data" / "interim" / "reports" / "henry"
TITLES = {"01": ("op27no2", "Chopin, Nocturne in D-flat major, Op. 27 No. 2"),
          "02": ("op64no2", "Chopin, Waltz in C-sharp minor, Op. 64 No. 2"),
          "03": ("op9no3", "Chopin, Nocturne in B major, Op. 9 No. 3"),
          "04": ("op_posth", "Chopin, Nocturne in C-sharp minor, Op. posth. (No. 20)"),
          "05": ("op9no1", "Chopin, Nocturne in B-flat minor, Op. 9 No. 1")}  # fmt: skip
TR_NAME = {"transkun": "Transkun 2.0.1", "aria_amt": "Aria-AMT piano-medium-double-1.0"}


def floor_note(summ: dict, k: str, t: str) -> str:
    d = summ["per_take"][f"{k}:{t}"]
    f, x = d["floor_a_error_rate"], d["floor_extra_rate"]
    return (f"Transcription floor (A-01): {d['n_floor']} expert recordings of this piece, "
            f"transcribed by the same model family and scored by the same checker, have a median "
            f"error rate of {100 * f['median']:.1f}% (90th percentile {100 * f['q90']:.1f}%) and "
            f"a median extra-note rate of {100 * x['median']:.1f}%. This take: "
            f"{100 * d['take']['a_error_rate']:.1f}% and {100 * d['take']['extra_rate']:.1f}%. "
            "Read correctness against this floor, not the Disklavier expert range. "
            f"Transcribed from a phone recording by {TR_NAME[t]}.")  # fmt: skip


def tiered(rep: dict) -> set[tuple]:
    out = set()
    for i in rep["issues"]:
        if i["tier"] in ("notable", "strong"):
            for b in i["bars"]:
                out.add((i["category"], i["channel"], int(b)))
    return out


def main() -> None:
    warnings.filterwarnings("ignore")
    logging.basicConfig(level=logging.ERROR)
    from pianolens.report import report_from_files, write_report

    summ = json.loads((BASE / "a01" / "summary.json").read_text())
    meta = json.loads((BASE / "scores" / "scores.json").read_text())
    OUT.mkdir(parents=True, exist_ok=True)
    stab = {}
    reps = {}
    for k, (slug, title) in TITLES.items():
        for t, suffix in (("transkun", ""), ("aria_amt", "_aria")):
            rep = report_from_files(
                BASE / "transcribed" / t / f"{k}.mid", score=BASE / "scores" / f"{k}_score.mxl",
                piece_id=meta[k]["piece_id"], provenance="transcribed", title=title,
                notes=[floor_note(summ, k, t)])  # fmt: skip
            write_report(rep, OUT / f"{k}_{slug}{suffix}.html")
            reps[(k, t)] = rep
            print(k, t, "done", [d["text"][:90] for d in rep["practise"]])
        a, b = tiered(reps[(k, "transkun")]), tiered(reps[(k, "aria_amt")])
        by = {}
        for cat_ch in sorted({(c, ch) for c, ch, _ in a | b}):
            sa = {x for x in a if x[:2] == cat_ch}
            sb = {x for x in b if x[:2] == cat_ch}
            by["/".join(cat_ch)] = {"transkun": len(sa), "aria_amt": len(sb),
                                    "both": len(sa & sb),
                                    "jaccard": len(sa & sb) / max(1, len(sa | sb))}  # fmt: skip
        prac = [(d["category"], d["channel"], tuple(d["bars"]))
                for d in reps[(k, "transkun")]["practise"]]  # fmt: skip
        prac_in_aria = [any((c, ch, bb) in b for bb in bars) for c, ch, bars in prac]
        stab[k] = {"by_channel": by, "practise_top_in_aria_report": prac_in_aria}
    (OUT / "stability.json").write_text(json.dumps(stab, indent=1))
    print(json.dumps(stab, indent=1))


if __name__ == "__main__":
    main()
