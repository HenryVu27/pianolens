# BL-18 strong tier on transcribed input: audit facts (2026-09-29)

- Prereg in `docs/specs/report-validation.md` section 5: `sed -n 216,281p | shasum -a 256` =
  2274b56b...f60c; amendment `sed -n 288,308p` = 37d1100a...1664. Author transcript:
  subagents/agent-aa4fc30e04c32f8c1.jsonl (session 9591b65d). Prereg 20:41:55Z, amendment
  20:46:22Z, first held-out draw 20:47:20Z, full run 20:50:15Z (took ~30 min, not 55).
- Read-only rerun: import `scripts/calibrate_strong_tier_bl18.py` as module, call `dev_eval`
  and `heldout_eval` on `bl18_tables.pkl` (do NOT run main with --from-cache: it overwrites
  bl18_summary.json). About 6 min; identical to the summary.
- Per-bar frames under each rule: `m.tiers(table, experts, rule, fam_lim)`; Henry bars can be
  rebuilt from report JSON `bars[*].correctness` + floor tables keyed (take '01'..'05',
  transcriber); R0 reproduces old tiers bar for bar.
- PianoCoRe: capture_model == corpus. Aria-AMT only on Aria-MIDI (YouTube segments, ids
  Aria_<video>_<seg>), Transkun V2 only on PERiScoPe; no performance in both. Any "per
  transcriber" limit from PianoCoRe is a per-corpus limit.
- Runs (3+ consecutive graded bars with >=80% missed): dev Aria 55 bars / 6 of 75 targets,
  held-out 15 / 4 of 109; half at piece start or end (truncated segments). Immune to every
  candidate (0.8 > 0.771), which forced R1(2)+R2s to cut non-run strong to 0.29% on dev.
  Aria me_q99 0.771 with runs, 0.422 without.
- Learner cost metric that worked: injected bars with dw >= 3 (injected minus clean wrong
  count). Strong share R0 96.5, R1(0) 92.9, R1(2)+R2s 52.9 (85 bars); expert max <= 1:
  100 / 100 / 76.8 (56 bars).
- Recurring errors across takes are promoted to strong independently of limits; tier changes
  only hurt single-take reports (strong of any category outranks notable correctness).
- Transkun per-piece strong under R1(0) is mostly < 0.5% (one piece 1.63%): a lower tolerance
  of 0.5% is a coin flip; used 0.30% in the BL-18b spec.
