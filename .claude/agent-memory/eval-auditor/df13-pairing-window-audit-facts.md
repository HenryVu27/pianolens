---
name: df13-pairing-window-audit-facts
description: DF-13 (wrong-pitch pairing window) audit, 2026-10-10 - prereg/timeline recipe, read-only recompute from piece sums, probe recipe, parangonar duplicate matches behind the "re-match" half, collision fix neutral on bars, F1 interval, BL-18b C1 second sample
metadata:
  type: project
---

- Prereg anchor: `awk '/^## Pre-registration DF-13/{f=1} f{print} /^End of the DF-13 pre-registration\.$/{exit}' docs/specs/correctness-validation.md | shasum -a 256`
  = 44bd842e...771f. Pre-edit hash 39d99e92...1214 (20:41:37Z); the DEFECTS row, commit
  message and feature-engineer memory cite a hybrid "44bd842e...1214". Author transcript
  session 73c389dd, subagents/agent-a4ea7f2f6dc000885.jsonl: append 20:41:36Z, edit 20:41:44Z,
  hash file 20:41:50Z, held-out launch 20:42:09Z (code hash 7bf82ad7 = committed f5761c9).
- Read-only recompute: everything decisive is in `data/interim/df13/heldout_piece_sums.csv`
  (criteria = ratio of sums per family) and `heldout_summary.json`. `heldout_jobs()` reproduces
  the draw exactly (241 eligible, 800 jobs) in seconds.
- Probe recipe (scratch df13a/probe.py): import the script by path WITH `sys.modules[name] = m`
  before exec (dataclasses fail otherwise); per target: `_bl18b()._load`, align, `correctness`,
  `targeted_copy(..., avoid)`, realign. 320 targets ~25-40 min at load 20-100. Stored fixed
  outcomes reproduced 8,526 / 8,526; old (10403a5) vs new correctness identical on 320 clean target +
  303 targeted transcriptions and 40 ASAP Disklavier mistake copies x 2 alignment modes.
- Trap: pandas `.mean()` on an object column of np.bool_ / bool mixes gave 0.004 instead of 1.0.
  Cast with `.astype(bool)` before averaging probe flags.
- parangonar-dualdtw emits duplicate matches (one performed note matched to two same-pitch
  score notes, e.g. a repeated note a quarter apart); `correctness()` accepts both as correct
  (no uniqueness check in the pairs loop). Held-out: 30/188 (Transkun) and 16/225 (Aria) of the
  "re-matched" intended notes; dev 1 and 2. Clean copies: 0.4-0.54 per 1,000 graded score notes,
  20-30% of copies. BL-19b saw the same on PianoVAM. Not in DEFECTS as of this audit.
- Dev "re-match" half overlaps collisions: 43% / 30% of the re-matching notes are injected notes.
  Re-matching note was an extra in the clean copy in 39-44% (held-out), 19-28% (dev).
- Collision fix (avoid pitches written in the bar) leaves the chosen bars unchanged
  (1441/1443, 1438/1439 shared) and the ±1/±2 mix about equal; only the pitch retry changes.
- F1 relative piece bootstrap held-out [6.5, 21.5]% / [7.1, 23.3]%; dev-heldout difference CI
  includes 0. Only dropping Scarbo flips it (11/16 and 15/16 LOO drops still fail).
- Rule P clean strong (BL-18b C1 measure) on DF-13 held-out 1.49 / 1.86%; 4/16 and 6/16 pieces
  above 1.25%; A-01 floor Aria-AMT 1.48% (LOO 14 refs). Cached f08c floor tables: 9 bars differ
  in wrong/missed, 44 bars in n_extra (25 tables); floor P rates move <= 0.03 pt.
