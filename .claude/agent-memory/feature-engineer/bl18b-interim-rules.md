# BL-18 interim rules + BL-25 + BL-20 prop. 3 + BL-18b (2026-09-29)

## Report code (report/build.py, calibration.py, text.py, render.py)
- Interim default (DECISIONS "lead: BL-18 after audit"): `EXPERT_CHECK_STRONG_MARGIN_TRANSCRIBED = 0`,
  `ReportConfig.transcribed_strong_limits = False` (R2s kept only for comparison).
- "Passage not heard": `build.not_heard_runs` (>= 3 consecutive graded bars, >= 80% missed;
  ungraded bars skipped). Transcribed only (`ReportConfig.not_heard` None = auto). Run bars:
  tier none, `expert_check = "not_heard"`, `correctness.not_heard` list (at_start/at_end),
  confidence note + correctness-card finding via `text.not_heard_text`. Target only; expert
  tables are not run-filtered (open option).
- BL-25: `build.fast_repeat_notes(score_notes, 0.1)` keys on the SCORE same-pitch predecessor
  (strictly earlier onset_quarter, so unisons are not repeats) using `expected_onset_sec`.
  `bar_error_table` now has `n_missed_fast_repeat`; `expert_bar_limits(drop_fast_repeats=)`
  subtracts it where the column exists (old caches, e.g. f08c_floor_tables.pkl, lack it ->
  experts not reduced, conservative). Bar fields `n_missed_fast_repeat`,
  `n_missed_low_confidence`.
- BL-20 prop. 3: `build.local_ioi` (same as BL-20 script: 30 ms chords, median of up to 4 gaps),
  `fast_run_notes`; bar field `n_wrong_fast_run`; issue text "N wrong notes in this fast run";
  recurring `_describe_error` -> "a wrong note in this fast run". Tiers unchanged.
- Test trap: moving a performed note +30 semitones in scale_texture pairs LH notes as octave
  wrong pitches with RH score notes; +47 avoids every octave there.

## BL-18b (docs/specs/report-validation.md section 6, sha 3a151ec7...04b8db, lines 527-607)
- Script `scripts/calibrate_strong_tier_bl18b.py` (imports BL-18 script's `tiers`/`_interval`
  by path). Two phases: experts first, then targets with their experts' tables (targeted bars
  need them). 600 jobs, 12 pieces (seed 1802, 253 eligible). Cache `bl18b_tables.pkl`
  ({"rows", "n_eligible_pieces"}), `--from-cache` re-scores.
- Reachability before draw (BL-18 cache, runs removed, 12-piece resample): C1 0.92 Aria / 0.73
  Transkun; C3 1.00 / 0.89.
- Results (spec 6.1): 600 jobs 0 failed, ~70 min at load ~14. P clean strong 0.58 / 1.04%
  (Transkun / Aria) pass C1; C3 0.81 / 0.84 pass; C4 71.5 / 68.4% FAIL, identical under R0,
  100% when the checker counts all 3 -> checker loses 16-19% of injected wrong notes on
  transcribed input (DF-12). Verdict FAIL by rule; revert-to-R0 left to the lead.
- Lesson: my reachability note estimated C4 from Disklavier (BL-20) loss rates; transcribed
  input loses far more. For any detection criterion, estimate reachability on the same capture
  chain, and pre-register the checker-conditional share as a co-criterion or the absolute
  threshold measures the checker, not the rule.
- Aria-AMT runs in BL-18b are mostly mid-piece (0 at start, 3 of 19 at end), not truncation.

## Henry rerun (henry_v2/)
- Strong correctness bars 14 (orig R0) -> 11 (same as the audit's R1(0) count); 3 moved to
  notable by R1(0); BL-25 moved 2 notable bars to none; no "passage not heard" run; checker
  counts identical to the originals. 25 of 1,152 missed notes are fast repeats.
