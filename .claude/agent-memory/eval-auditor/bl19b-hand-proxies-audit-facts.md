---
name: bl19b-hand-proxies-audit-facts
description: BL-19b audit (staff vs PianoVAM video hand) - prereg timeline source, rerun recipe, pandas `take` column trap, recurrence check, D2 knife-edge numbers, Toccata/Op.17 findings
metadata:
  type: project
---

BL-19b audit, 2026-10-10. Verdict: Confirmed with caveats. Numbers are in the README "Audit" section.

- **Author transcript:** subagent `agent-a9cb3724bc0fa75cc.jsonl` under session
  `73c389dd-...`. The run ID is in the `.meta.json` description ("BL-19b hand proxy validation").
  Timeline: QC applied 21:51:11Z, hash 21:52:50Z, score run 21:55:44Z (local mtimes are UTC-5).
  One pre-hash call printed `pv.hand_label_summary()`: per-recording `n_noinfo` and `n_manual`
  only. Check whether a similar summary call reveals any per-note label in future PianoVAM work.
- **Rerun recipe:** copy `run.py`, `score_stage.py` and `posthoc.py` to scratch, and set
  `ROOT = Path("/Users/henryvu/personal/pianolens")` and `ART = HERE / "art"` in the copies.
  `run.py` must have an absolute ROOT because it uses `parents[2]`. Then
  `OMP_NUM_THREADS=1 uv run python $SP/run.py align --workers 10` (about 100 s), then `score`,
  then `posthoc.py`. Align parquets come out identical. The summary differs only in the row
  order of `S5_words.piece_staff_base` (set iteration). Posthoc `n_runs` is 4,251 or 4,252
  (unstable sort on chord ties).
- **pandas trap:** the column `take` collides with `DataFrame.take`, so `n.take == tk` compares a
  method and is all False. Use `n["take"]`. It silently produced NaN in my residual check.
- **Recurrence check:** P(mismatch on another pass | mismatch) at the same score note = 0.90,
  against a base of 0.068. Across recordings it is 0.90 against 0.081. This is strong evidence
  that the mismatches are systematic, not random label noise or misalignment. Reuse it for any
  per-note ground-truth disagreement.
- **Same-pitch confusability:** 86% of the Tombeau Toccata's mismatches have a same-pitch note
  on the other staff within 1 quarter; outside them the rate is 4.5%. Other pieces: 4-9%.
  Parangonar matches show no same-pitch crossings within a take.
- **Op. 17 i** is a PianoCoRe engraving, not ASAP. In mm. 41-49 voice 2 sits on staff 1, and in
  m. 48 all 148 labelled notes are played by L across all 7 recordings. P1 cannot see it.
- **D2 numbers:** 3/30 = 0.10 passes. Leaving out any of 27 pieces gives a concern; a 100-event
  minimum gives a concern; the bootstrap passes in 0.59 of resamples. Noise-only event rate is
  about 2.1% at e = 0.76% (2.96 notes per event).
- **Noinfo:** across pieces, Spearman with mismatch is 0.43. The D1 2% reading is lost at
  e of about 1.57%; the S7 opening video error is 1.69%.
