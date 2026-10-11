---
name: bl37-edge-bars
description: BL-37 edge bars of a trimmed span - fixes (realign after shrink, optional tie tails, restrict_to_score), dev design, edge-bar policy candidates, injection check, guard (2026-10-11)
metadata:
  type: project
---

# BL-37 edge bars (2026-10-11)

Related: [[bl36-partial]], [[bl18b-interim-rules]], [[df13-pairing-window]].

## Fixes (code)
- `align/core._align_partial`: realign on the final trimmed part when the shrink moved an edge
  (BL-36 filtered). `partial.trim_part` records tie tails cut from their head
  (`EDGE_TAILS_ATTR`); an unmatched tail at the start edge is dropped (optional tail).
- `report.io.restrict_to_score`: drops the reference's notes matched outside the span from the
  performance (not extras), drops unmatched notes outside the in-span time window, maps a tie
  tail to the performed tie head (via `ap.score.part`).
- Policy behind `ReportConfig.edge_low_confidence_bars` (default 0): missed notes in the first /
  last k graded bars of a trimmed side are low confidence (`report.build.edge_bars`).

## Dev (BL-36 dev + held-out, 5 targets per piece-family; `data/interim/bl37/dev_v2_*`)
- Fixes 1-2 alone: edge minus uncut +2.95 pt (BL-36 audit 12.3 vs 1.1). Mechanism on units:
  597/668 lost notes of newly strong edge bars matched 1-2 bars OUTWARD into unplayed margin
  bars (the BL-36 margin + anchored DualDTW). Fix: `margin_needed` (align DTW span AND widened
  span; keep margin only if it explains notes the DTW-span alignment leaves unmatched). The DTW
  start itself is exact (cut bar or first full bar) in 98.6% of start sides.
- Dev v2: none E1 +0.79 but cut bars +17.4 -> policy k=1 (missed low-conf in first/last graded
  bar) adopted: E1 +0.22, E2 -1.27, D1 -0.80, D2 -3.68; reachability 99.5%; W1 265/265.
- Bites: cap/untier lose 42-59 pt strong detection (D1); untier fails D2; none fails E2.
- Policy-only fixes were fragile (k=2 E1 +1.43 vs bar 1.5, 51% adoption) before the margin fix:
  fix the alignment cause first.
- parangonar 3.3.3 ornament step crashes (DTypePromotionError) when NO performed note is
  unmatched and an ornamented note is matched -> fallback in `align_note_arrays`; checked on
  1,623 items (nASAP, D-08, floor, Henry) by `scripts/check_ornament_fallback_bl37.py`.

## Traps
- `scripts/eval_edge_bars_bl37.py` offline policy must change tiers only, not "not heard" runs.
- BL-35 guard: call `pianocore.guard_jobs` AFTER the seeded draw (draw must not shift).
- `src/pianolens/data/pianocore.py` had ruff errors from the data-engineer's in-progress BL-35.

## Held-out (2026-10-11, prereg 4b1e7374...a86c, seed 3737): PASS, policy k=1
- E1 -0.05, E2 -0.63 (none +19.5), D1 -0.51, D2 -3.82 pt; W1 304/304; B pass but H1 Aria strong
  -0.1446 vs 0.15 (10/16 LOO flips, 55% resamples) -- correction direction again (trimmed Aria
  segments). Lesson for next registration: H1 only on evidently-full targets.
- Fallback check: 0 crashes / 1,623 identical on full scores; crash only on trimmed spans.
- Traps: spawned workers cannot unpickle functions of a path-loaded module (`bl36.*`) -> wrap in
  the script's own module-level functions (first launch crashed, disclosed as deviation).
  Readout JSON printed after warnings: read the written file, not stdout.

## Audit (2026-10-11): Confirmed with caveats; flags off, Henry chooses k=0 vs k=1, BL-39 next
- My miss: the detection rows injected WRONG PITCHES, which a missed-note policy cannot hide by
  construction. Omissions (the thing k=1 hides) were not injected: 3 omitted notes in an edge
  bar ranked 60.2% (k=0) vs 17.3% (k=1), 0% on N's own edge. Lesson: a harm row must inject the
  error type the candidate acts on (here missed notes), else it is zero by construction.
- B was registered on N without the policy; with k=1 applied H1 Aria strong -0.1548 (fails).
  Register no-regression rows under the candidate itself.
- Wrong-piece probe: same-key pairs are not the hard case; all-pairs gave 2/1,376 >= 0.5
  (4-7-bar excerpts). Probe all pairs.
- Fallback "identical" was by construction for non-crashing calls; say what the check measures.

## BL-38 parts 1-2 (2026-10-11)
- `report/io.pianocore_expert_midis`: `raw_guard` BEFORE the seeded choice (app, not an
  experiment), `SCORE_VERSION_MISMATCH` -> []. Op. 22 keeps 15 of 123 accepted files.
- Henry check recipe: his A-01 reports use cached floor tables, so `pianocore_expert_midis` is
  not on that path; verify the function directly (expert draws for his 5 pieces x 3
  transcriber settings) plus a before/after report diff.
- `eval_partial_bl36.py` held-out now calls `guard_jobs` after the draw (1 suspect expert).
