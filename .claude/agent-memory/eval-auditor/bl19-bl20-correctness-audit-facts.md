# BL-19 / BL-20 audit facts (2026-09-29)

- Prereg: both sections in `docs/specs/correctness-validation.md` (BL-20 lines 179-228, BL-19 229-264);
  `sed -n 'a,bp' | shasum -a 256` reproduces. Author transcript: session 9591b65d, subagent
  agent-ad92e8997db2cfccc.jsonl (appended 20:44:00Z, hashed 20:44:06Z, scripts written after).
- BL-20 rerun: `scripts/eval_correctness_density.py --part all --workers 10 --out <scratch>` (830 s),
  byte-identical CSVs/summary. Sources: 100 performances / 62 pieces (index.csv piece_id).
- BL-20 traps: (1) `gt_alignment` absorbed = 0 by construction (labels_to_alignment makes wrong pitch
  = del + ins). (2) Pre-registered "bar detected" = bar_err > 0 counts pre-existing clean errors;
  condition on bar_err_clean == 0 (dense-N aligned 0.932). (3) "no error at all" = 1 - detected.
  (4) correctness trusts aligner "match" without pitch check: 26/194 absorbed are pitch-mismatched.
  (5) ornament whitelist runs BEFORE wrong-pitch pairing; drives gt dense-N gap (-0.137).
- BL-19 rerun: `scripts/staff_hand_proxies.py --out <scratch>` 95 s; bootstrap depends on
  as_completed row order (4th decimal). Partitura ignores <arpeggiate>; parse XML yourself.
- BL-19 checks that worked: hand-word recall (contradicting m.d./m.g. measures, 57% zero flagged);
  heavy split voices (17.8% of P1); arpeggiate-marked P3 (9%); NaN zero-event pieces counted in
  the >20% denominator; Mozart 1/3 scores with 2-13 stray events enter the tail.
- Scratch scripts (not persistent): audit/bl20_audit.py, audit/bl19_diag.py, audit/bl19_var.py.
