# S-04 design notes (2026-09-29)

- Protocol draft: `study/protocol-S04.md` (not frozen). Sim: `src/pianolens/study/power_s04.py`,
  `scripts/power_s04.py --n-rep 200` (about 25 min) -> `data/interim/study_s04/power/`.
- Stimulus pool measured with `asap_index()` + robust alignment + heuristic performer ids: 20 ASAP
  pieces with >= 10 distinct performers, 31 with >= 8; 11 of the 20 are Chopin. Plus Vienna 4x22 (4 x 22).
- PianoCoRe is ~99.6% transcribed: never a stimulus source; only the tempo reference for d2m.
- BT gotcha: with ~20 comparisons/item, all-win/all-lose items are common -> plain MLE (l2=1e-4)
  gives SE ~28 and negative SSR. Use ridge l2 = 0.1 (`BT_L2`) for scores and SEs.
- Held-out H7 gain is negative under H7-false (M1 overfits 7 coefs), so "falsified" is easy when
  features truly add nothing; the power problem is on the "supported" side (items, not listeners).
- App reuse: S-03 Part B runner is already a 2-clip preference trial; a `study=S04` flag + new
  `design_s04.js` + offline pair schedule in the manifest is enough (S-05).
- Sim results (n_rep 200, assumed params; protocol-S04 section 6): 24x10, N=96 -> P(supported | r2_feat .2) 0.87,
  pooled SSR 0.88, one-stratum SSR 0.78; exactly 20 comps/item gave SSR median 0.79 (only 14% >= .8), so the
  20-per-item rule does not guarantee SSR .8. Power scales with passages; 12 passages cap at ~0.5. 0 false positives.
