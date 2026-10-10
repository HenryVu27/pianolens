"""A-01: F-08 practice reports for Henry's 5 phone takes, from both transcriptions.

    uv run python scripts/a01_henry_reports.py

Primary report: Transkun MIDI (``<k>_<slug>.html``); cross-check: Aria-AMT MIDI
(``<k>_<slug>_aria.html``). Both use the PianoCoRe MusicXML score and the piece's PianoCoRe tier A
references, provenance ``transcribed`` (so velocity is low confidence and not practise-eligible).
Each report carries a note with the per-piece transcription floor measured by
``scripts/a01_henry_baseline.py`` (run that first).

Per-bar expert check (F-08c): the same A-01 floor transcriptions (15 per piece and transcriber
family, the transcriber matching the take's), cached as per-bar tables by
``scripts/calibrate_expert_check_f08c.py`` (run that first). Extra notes are low confidence on
this input and never practise items (``rules/audio.md``).

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
HIGH_PITCH = 91  # G6
HIGH_NOTE_MIN_RATE = 0.02  # add the note when high extras exceed 2% of score notes
FLOOR_TABLES = ROOT / "data" / "interim" / "reports" / "calibration" / "f08c_floor_tables.pkl"
TR_NAME = {"transkun": "Transkun 2.0.1", "aria_amt": "Aria-AMT piano-medium-double-1.0"}
TR_FAMILY = {"transkun": "Transkun V2", "aria_amt": "Aria-AMT"}  # PianoCoRe capture_model (BL-18)


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


def high_extras(k: str, t: str, meta: dict) -> dict:
    """Extra notes at G6 (MIDI 91) or above, and above the score's highest note.

    On Henry's takes 03-05 many extras sit on a few fixed high pitches that do not follow the
    music; in the controlled check (rendered audio, simulated phone) they are at most 0.2% of
    score notes. They are counted here so the report can say which correctness flags they drive.
    """
    import numpy as np

    from pianolens.align import align_performance
    from pianolens.features.correctness import correctness
    from pianolens.report.io import load_performance, load_score

    sc = load_score(BASE / "scores" / f"{k}_score.mxl", meta[k]["piece_id"])
    perf = load_performance(BASE / "transcribed" / t / f"{k}.mid", "transcribed",
                            meta[k]["piece_id"], performance_id=k)  # fmt: skip
    cr = correctness(align_performance(sc, perf))
    nd = cr.notes
    ex = nd["label"].astype(str).to_numpy() == "extra"
    p = nd["pitch"].to_numpy(int)
    hi = ex & (p >= HIGH_PITCH)
    per_bar = nd.loc[hi, "measure_index"].value_counts()
    ex_bar = nd.loc[ex, "measure_index"].value_counts()
    return {"n_extra": int(ex.sum()), "n_high": int(hi.sum()),
            "n_above_score": int((ex & (p > int(np.max(sc.notes["pitch"])))).sum()),
            "n_score_notes": float(cr.summary["n_score_notes"]),
            "high_bars": sorted(int(b) for b, n in per_bar.items() if n >= 3 and
                                n >= 0.5 * ex_bar.get(b, 0))}  # fmt: skip


def high_note(h: dict, rep: dict) -> str | None:
    g = max(1.0, h["n_score_notes"])
    if h["n_high"] / g < HIGH_NOTE_MIN_RATE:
        return None
    labels = {int(b["index"]): b["label"] for b in rep["bars"]}
    labels[-1] = "before bar 1"
    hit = [d["bars_label"] for d in rep["practise"] if d["category"] == "correctness"
           and sum(b in h["high_bars"] for b in d["bars"]) >= 1]  # fmt: skip
    txt = (f"Suspect extra notes (A-01): {h['n_high']} of the {h['n_extra']} extra notes "
           f"({100 * h['n_high'] / g:.1f}% of score notes) are at G6 or above, "
           f"{h['n_above_score']} of them above the highest note in the score. Rendered expert "
           "performances of these pieces through a simulated phone give at most 0.2%. They may "
           "not be played notes (sound in the room, or overtones read as notes): listen to these "
           "bars before practising their notes. Bars where they are most of the extras: "
           + ", ".join(labels.get(b, str(b + 1)) for b in h["high_bars"][:20]) + ".")
    if hit:
        txt += " Treat these practise items with caution: " + "; ".join(hit) + "."
    return txt


def tiered(rep: dict) -> set[tuple]:
    out = set()
    for i in rep["issues"]:
        if i["tier"] in ("notable", "strong"):
            for b in i["bars"]:
                out.add((i["category"], i["channel"], int(b)))
    return out


def main() -> None:
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--out", type=Path, default=OUT, help="output folder (personal data)")
    p.add_argument("--floor-tables", type=Path, default=FLOOR_TABLES,
                   help="cached A-01 floor expert tables (DF-13: rebuilt with the transcribed "
                        "window rule by scripts/rebuild_floor_tables_df13.py)")
    args = p.parse_args()
    out = args.out
    warnings.filterwarnings("ignore")
    logging.basicConfig(level=logging.ERROR)
    import pickle

    from pianolens.report import report_from_files, write_report

    summ = json.loads((BASE / "a01" / "summary.json").read_text())
    floor = pickle.loads(args.floor_tables.read_bytes())
    meta = json.loads((BASE / "scores" / "scores.json").read_text())
    out.mkdir(parents=True, exist_ok=True)
    stab = {}
    reps = {}
    for k, (slug, title) in TITLES.items():
        for t, suffix in (("transkun", ""), ("aria_amt", "_aria")):
            rep = report_from_files(
                BASE / "transcribed" / t / f"{k}.mid", score=BASE / "scores" / f"{k}_score.mxl",
                piece_id=meta[k]["piece_id"], provenance="transcribed", title=title,
                notes=[floor_note(summ, k, t)], expert_capture_model=TR_FAMILY[t],
                expert_tables=[r["table"] for r in floor if r["take"] == k
                               and r["transcriber"] == t and not r["suspect"]])  # fmt: skip
            extra_note = high_note(high_extras(k, t, meta), rep)
            if extra_note:  # the header renders confidence notes; input notes keep provenance
                rep["confidence"]["notes"].append(extra_note)
                rep["input"]["notes"].append(extra_note)
            write_report(rep, out / f"{k}_{slug}{suffix}.html")
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
    (out / "stability.json").write_text(json.dumps(stab, indent=1))
    print(json.dumps(stab, indent=1))


if __name__ == "__main__":
    main()
