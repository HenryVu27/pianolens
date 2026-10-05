# BL-18b strong-tier confirmation audit facts (2026-09-29)

- Prereg: `sed -n 527,607p docs/specs/report-validation.md | shasum -a 256` = 3a151ec7...04b8db.
  Author transcript subagents/agent-a3ffbd0c9ed754a0b.jsonl (session 9591b65d): prereg
  22:32:47Z, hash 22:32:52Z, script 22:34:36Z, smoke test (first draw) 22:34:47Z, run 22:35:17Z.
- Read-only rerun: import `scripts/calibrate_strong_tier_bl18b.py`, call
  `evaluate(rows, b._bl18())` on `bl18b_tables.pkl["rows"]` (80 s). Do not run main
  `--from-cache` (overwrites the summary). Matches the summary in every field.
- Targeted copies regenerate exactly: `_load(job)` -> align -> correctness -> `bar_error_table`
  -> `targeted_copy(ap, cr, labels, table, experts, 2)`, experts = cached tables sorted by
  order. `perf.notes` is a numpy structured array (no pandas methods). Probe script:
  scratchpad `bl18b_audit/probe.py` (238 targets, 10 workers, about 7 min).
- C4 is 100% by construction for margin-0 rules (experts <= 1 wrong, global wrong_q99 = 2).
  Only margin > 0 lowers it (R1(2) + R2s 83.4 / 58.9%). Any "C4'" conditional on checker = 3
  is not evidence.
- DF-12 split (Transkun V2 / Aria-AMT): counted 83.5 / 80.4%; unpaired extra 10.1 / 13.3%
  (75 / 84% of them > 100 ms from expected onset: pairing window); score collision 4.7 / 4.1%;
  ornament 1.5 / 2.0%.
- Run fragments: merge gaps <= 2 bars; 8 of 10 run targets lose the ending, 1 the opening,
  1 mid (Aria_771468_0 Op. 54, 85 bars). All are Aria-MIDI segments.
- `f08c_floor_tables.pkl` (150 tables) lacks `n_missed_fast_repeat`: BL-25 is target-only in
  Henry's reports (fewer flags; Aria-AMT clean strong 0.92 vs 1.04% on BL-18b).
- Lead decision: keep R1(0) + run rule as a disclosed deviation; conditions in the spec,
  "BL-18b audit" item 6.
