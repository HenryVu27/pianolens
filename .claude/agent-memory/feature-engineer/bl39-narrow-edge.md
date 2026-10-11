---
name: bl39-narrow-edge
description: BL-39 narrow edge-bar policy (missed notes outside the recorded part of the edge bar) - rule variants, omission-injection harm rows, dev numbers, bite checks (2026-10-11)
metadata:
  type: project
---

# BL-39 narrow edge policy (2026-10-11)

Related: [[bl37-edge-bars]], [[bl36-partial]].

## Code
- `report.build.edge_outside_notes(score, cr, k, basis, tol)`: mask of score notes in the edge
  bar(s) outside the recorded part (start: before the first matched note; end: after the last).
  Bases: "score" (strict score position), "score_le" (boundary onset included: chord partners
  of the first matched note), "time" (expected onset vs first performed matched onset, tol).
- `ReportConfig.edge_low_confidence_rule` "bar" (BL-37) / "outside" (BL-39); union with BL-25
  fast-repeat notes counted once.
- `scripts/eval_edge_narrow_bl39.py`: injections inj_wrong (D1/D2), omit_inner (O1: 3 correct
  notes not at the boundary onset), omit_lead (O2: first / last 3 correct notes); policies
  none / k1 / nar_<variant> / nar_sab_le2 (sabotage, up to 2nd matched onset; eval-only).

## Dev smoke (88 targets)
- k1 O1 -38.9 (bites). strict score: O1 0, O2 -22, E2 +2.15 (fails 1.5): cut bars keep chord
  partners at the boundary onset (mid-chord cuts). score_le: E2 +0.28, O1 -0.6, O2 -36.6.
  time variants E2 >= +3.

## Machine load (2026-10-11)
- Load average ~140 during the BL-39 held-out was NOT thread oversubscription: 10 workers x 2
  threads at ~90% CPU on hw.ncpu = 10; the load counts many runnable macOS daemons (0% CPU)
  queued behind them. Use workers = ncpu - 2 (8) and also export OPENBLAS / MKL / VECLIB /
  NUMBA_NUM_THREADS=1. Check `ps -M -p <pid>` thread counts before blaming threads.
- CORRECTION: this Mac has 16 GB RAM (hw.memsize), not 48 GB as CLAUDE.md says; swap 7.2 GB.
  Size workers by memory too: keep ~6 GB free -> 5-6 alignment workers (0.3-0.7 GB each, more
  on long pieces). Eval scripts should write per-target results incrementally so a run can be
  stopped and resumed (BL-39's could not).

## Dev full + held-out (2026-10-11)
- Dev (258 targets, 44 pieces): candidate score_le E1 +0.41, E2 +0.91, O1 -1.69, O2 -38.0;
  k1 O1 -44.1; k2 O1 -63.9 / O2 -60.4; second-onset sabotage O1 -16.2. Reachability 74% (E2).
- Held-out (prereg 7e85dcd8...bc39, seed 3939): FAIL by rule on E2 +1.67 vs 1.5 (k0 +18.2), 4/16
  LOO drops flip it, 40% resample pass; everything else passes; no policy adopted (k = 0).
- Lesson: E2 per-piece values rest on ~67 cut bars per piece; a pooled +1.5 pt bar sits inside
  sampling noise. Residual cut-bar flags are alignment loss inside the recorded part (one bar
  inspected: Op. 22/2 bar 53), not policy. A retry needs a per-bar-robust E2 or an alignment fix.
- Run-time traps: run was cut by an API usage limit AFTER outputs were written -> write-up from
  files; eval scripts must write per-target results incrementally (resume).

## Audit (2026-10-11): Confirmed with caveats, FAIL stands
- My miss (again): I named the E2 residual's mechanism from ONE dev bar ("alignment loses notes
  inside the recorded part"). On held-out units: 46% of counted missed notes were removed by the
  cut but inside the boundary, 30% re-paired in-bar, 1 note fit my mechanism; the anchor was
  mis-paired in 32/33 bars; oracle anchor E2 -0.58. Lesson: classify ALL residual units against
  the uncut copy before naming a mechanism; one inspected unit is an anecdote.
- Pooled O2 diluted the cost (a third of bars not N's edge): on N-edge bars 8.8% vs 58.4%.
  Report harm rows on the bars the policy can act on.
- O1 (-8) does not bite for a boundary one onset too wide (sabotage -6.94 held-out).
- Retry direction: anchor robustness (reject out-of-order anchor matches), fresh draw.
