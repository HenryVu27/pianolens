---
name: bl27-not-heard-merge-audit-facts
description: BL-27 ("passage not heard" merge) audit, 2026-10-11 - prereg/timeline recipe, read-only recompute, probe recipe for cut copies, Op. 20 116-bar repeat shift, C already swallows heard bars, P1 knife edge, untiered-under-C criterion is near-vacuous, render guard untested
metadata:
  type: project
---

- Prereg anchor: `awk '/^## Pre-registration$/{f=1} f{print} /^End of the BL-27 pre-registration\.$/{exit}' README.md | shasum -a 256`
  = 78a9a04c...c594. Author transcript session 73c389dd `subagents/agent-a90d10a79fa6d5e53.jsonl`:
  README Write 04:05:59Z, hash 04:06:03Z, launch 04:06:12Z (same call that edited "Falsified if").
  Pre-hash script runs were dev only (smoke uses `dev_jobs()`).
- Read-only recompute: import `scripts/eval_not_heard_merge_bl27.py` (sys.modules first), call
  `evaluate(rows)` on `data/interim/bl27/heldout_rows.pkl` (~40 s); 0 diffs vs summary. Do not run
  main `--from-cache` (overwrites summary/csv).
- Per-bar frame: `tiers_runs(c["table"], experts, gap)` + `c["truth"]`; clean table for clean miss.
  Scratch `bl27a/added.py` built 105,843 bars in ~35 s.
- Probe: replicate `target_one` keeping ap/cr (cr objects not picklable: RecursionError); match
  clean vs cut performed notes by (onset rounded, pitch); compare measure_index. ~45 s per Op. 20
  target. Cached tables reproduce exactly.
- Op. 20 start cuts: kept bars ~126-285 realigned onto pitch-identical material 116 bars earlier
  (99-100% still "correct"); C already puts 96-109 heard bars per copy in runs (522 Op. 20, 1,393
  all). Dev had the same pattern in Op. 54 (16 of 24 heard additions; 230 heard bars in C runs).
- P1 knife edge: Aria 44/289 (bar 43.35), pooled 62/589 (bar 58.9). Truth "heard" ignores whether
  the clean copy found the bar; 5 of 62 heard additions >=50% missed in clean.
- M only adds bars >=50% missed, so 581/589 were tiered under C: a "heard and untiered under C"
  criterion is nearly pass by construction.
- render.py takes-row guard untested (mutant passes all report tests); build guard test real.
- Side finding: cut copies, C strong on 1,966 unplayed bars vs 1,268 played (577 in clean); per
  piece 3.6-19.3%; median 17 bars from the cut.
