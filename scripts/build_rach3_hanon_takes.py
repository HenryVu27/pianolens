"""BL-16: split every Rach3 Hanon session into takes of Part I exercises and align them.

    uv run python scripts/build_rach3_hanon_takes.py

Method: :mod:`pianolens.data.rach3_takes` (generated one-pass exercise scores, fitting
alignment of each exercise against the session's event sequence, greedy non-overlapping
takes). Candidates from different exercises that overlap in a session are resolved by keeping
the higher normalised DP score (score / perfect). Then ``TakeQC`` is applied.

Writes ``data/interim/rach3_hanon_takes/``:
* ``scores/hanon_NN.musicxml`` (Nos. 1-20, one pass);
* ``takes.parquet``: one row per kept candidate (QC fields, ``qc_ok``);
* ``take_notes.parquet``: performed notes of each take (session times, session note ids);
* ``alignments.parquet``: note alignment rows per take (label, score_id, performance_id);
* ``summary.txt``: counts.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from pianolens.align import load_score_part
from pianolens.data import rach3
from pianolens.data import rach3_takes as rt
from pianolens.data.midi_io import performance_from_midi
from pianolens.data.types import PerformerId

OUT = Path(__file__).resolve().parents[1] / "data" / "interim" / "rach3_hanon_takes"
# Onset grouping thresholds tried per session; the one whose kept takes (normalised DP score
# >= 0.85) have the highest total DP score wins (hand asynchrony differs by player: p3 often
# plays the hands 40-50 ms apart).
CHORD_MS = (40.0, 60.0, 80.0)


def _resolve(cands: list[dict], n_events: int) -> tuple[list[dict], int]:
    """Across exercises, keep non-overlapping candidates, best normalised DP score first."""
    cands = sorted(cands, key=lambda d: -d["score"] / d["perfect"])
    used = np.zeros(n_events, dtype=bool)
    kept, dropped = [], 0
    for c in cands:
        if used[c["ev0"] : c["ev1"] + 1].any():
            dropped += 1
            continue
        used[c["ev0"] : c["ev1"] + 1] = True
        kept.append(c)
    return kept, dropped


def main() -> None:
    warnings.filterwarnings("ignore")
    (OUT / "scores").mkdir(parents=True, exist_ok=True)
    cfg, qc = rt.TakeConfig(), rt.TakeQC()
    book = rt.load_book(rach3.DEFAULT_ROOT / "scores" / "hanoncexercs.musicxml")
    ex = {}
    for n in range(1, rt.N_PART1 + 1):
        p = OUT / "scores" / f"hanon_{n:02d}.musicxml"
        p.write_text(rt.hanon_exercise_xml(book, n), encoding="utf-8")
        na = load_score_part(p).note_array()
        ex[n] = (na, rt.score_events(na["onset_div"], na["pitch"]))

    idx = rach3.rach3_index()
    idx = idx[idx["piece_code"] == "hanoncexercs"].reset_index(drop=True)
    take_rows, note_frames, al_frames = [], [], []
    n_candidates = n_overlap_dropped = 0
    session_cov = []
    for r in idx.itertuples():
        perf = performance_from_midi(
            r.path, dataset="rach3", performance_id=r.performance_id, piece_id=r.piece_id,
            performer_id=PerformerId(r.performer_id), provenance="sensor")  # fmt: skip
        notes = perf.notes
        best = None
        for chord_ms in CHORD_MS:
            pev = rt.perf_events(notes["onset_sec"], notes["pitch"], chord_ms)
            cands = [{**t, "exercise": n} for n, (_na, sev) in ex.items()
                     for t in rt.find_takes(sev, pev, cfg)]  # fmt: skip
            kept, n_drop = _resolve(cands, len(pev))
            total = sum(c["score"] for c in kept if c["score"] >= 0.85 * c["perfect"])
            if best is None or total > best[0]:
                best = (total, chord_ms, pev, cands, kept, n_drop)
        _, chord_ms, pev, cands, kept, n_drop = best
        n_candidates += len(cands)
        n_overlap_dropped += n_drop
        kept.sort(key=lambda d: d["ev0"])
        in_takes = 0
        for order, c in enumerate(kept):
            na, sev = ex[c["exercise"]]
            rows, cnt = rt.note_alignment(c["pairs"], sev, pev, na, notes, (c["ev0"], c["ev1"]))
            paired = [(s, e) for s, e in c["pairs"] if s >= 0 and e >= 0]
            gap = rt.max_gap_ratio(sev["t"].to_numpy()[[s for s, _ in paired]],
                                   pev["t"].to_numpy()[[e for _, e in paired]])  # fmt: skip
            take_id = f"{r.performance_id}#{order:02d}"
            nidx = np.concatenate([np.asarray(pev.at[e, "idx"]) for e in
                                   range(c["ev0"], c["ev1"] + 1)])  # fmt: skip
            fields = ("id", "onset_sec", "duration_sec", "pitch", "velocity")
            tn = pd.DataFrame({k: notes[k][nidx] for k in fields})
            tn.insert(0, "take_id", take_id)
            note_frames.append(tn)
            al = pd.DataFrame(rows, columns=["label", "score_id", "performance_id"])
            al.insert(0, "take_id", take_id)
            al_frames.append(al)
            row = {
                "take_id": take_id, "session_file": r.path.name,
                "performance_id": r.performance_id, "pianist": r.pianist, "level": r.level,
                "date": r.date, "session": r.session, "exercise": c["exercise"],
                "chord_ms": chord_ms,
                "order_in_session": order,
                "t0_sec": float(pev.at[c["ev0"], "t"]), "t1_sec": float(pev.at[c["ev1"], "t"]),
                "dp_score": c["score"], "dp_perfect": c["perfect"], "max_gap_ratio": gap,
                "n_perf_notes": len(tn), **cnt,
            }  # fmt: skip
            row["dur_sec"] = row["t1_sec"] - row["t0_sec"]
            row["qc_ok"] = qc.ok(row)
            take_rows.append(row)
            in_takes += cnt["n_match"]
        session_cov.append({"performance_id": r.performance_id, "pianist": r.pianist,
                            "n_notes": len(notes), "n_matched_in_takes": in_takes})  # fmt: skip

    takes = pd.DataFrame(take_rows)
    takes.to_parquet(OUT / "takes.parquet", index=False)
    pd.concat(note_frames).to_parquet(OUT / "take_notes.parquet", index=False)
    pd.concat(al_frames).to_parquet(OUT / "alignments.parquet", index=False)
    cov = pd.DataFrame(session_cov)

    lines = [f"sessions: {len(idx)}; candidates: {n_candidates}; dropped as overlapping another "
             f"exercise: {n_overlap_dropped}; kept: {len(takes)}; qc_ok: {int(takes.qc_ok.sum())}",
             "coverage (matched notes in kept takes / session notes), per pianist:",
             cov.groupby("pianist")[["n_notes", "n_matched_in_takes"]].sum()
             .assign(frac=lambda d: d.n_matched_in_takes / d.n_notes).round(3).to_string(),
             "", "takes per pianist x qc_ok:",
             takes.groupby(["pianist", "qc_ok"]).size().unstack(fill_value=0).to_string(),
             "", "qc_ok takes per pianist x exercise:",
             takes[takes.qc_ok].groupby(["pianist", "exercise"]).size().unstack(fill_value=0)
             .to_string()]  # fmt: skip
    ok = takes[takes.qc_ok]
    g = ok.groupby(["pianist", "exercise", "date"]).size()
    lines += ["", "same-day groups with k >= 2 qc_ok takes (pianist: groups, takes):",
              g[g >= 2].groupby(level=0).agg(["size", "sum"]).to_string()]
    lines += ["", "QC failure reasons (all kept candidates):"]
    for name, col, op, thr in (("event_match_frac", "event_match_frac", "<",
                                qc.min_event_match_frac),
                               ("note_match_frac", "note_match_frac", "<", qc.min_note_match_frac),
                               ("insert_frac", "insert_frac", ">", qc.max_insert_frac),
                               ("max_gap_ratio", "max_gap_ratio", ">", qc.max_gap_ratio)):
        bad = takes[col] < thr if op == "<" else takes[col] > thr
        lines.append(f"  {name} {op} {thr}: {int(bad.sum())}")
    text = "\n".join(lines)
    (OUT / "summary.txt").write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
