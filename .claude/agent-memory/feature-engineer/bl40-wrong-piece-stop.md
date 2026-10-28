---
name: bl40-wrong-piece-stop
description: BL-40 app quick-check stop under partial=True - cost of the app-path probe, dev ratio distributions, registered rule (0.625 / 75 notes / confirm), correctness empty-score crash, orphan-worker trap (2026-10-27)
metadata:
  type: project
---

# BL-40 wrong-piece stop with partial alignment (2026-10-27)

Related: [[bl36-partial]], [[bl37-edge-bars]], [[bl39-narrow-edge]], [[app-p02]].

## Cost (measured, 5 workers, 16 GB Mac)
- App-path quick check (`load_score` + `align_performance(partial=True)` + `correctness`):
  0.3-1.4 s per excerpt, 2-6 s per whole take (up to 18 s); `partial=True` builds EVERY repeat
  variant per call, so scores with many repeats are slow. All ordered pairs of 60 pieces x 2
  families x 5 takes ~ 3.6 h; 32 pieces ~ 44 min wall. Plan probes at <= ~32 pieces.
- Dev whole takes on wrong scores dominate time: sample them on dev.

## Dev numbers (32 pieces = BL-37 + BL-39 held-out; `data/interim/bl40/dev_*`)
- Right excerpts min 0.687 (Aria, 545 notes); wrong max 0.748 (49 notes). Among takes with
  >= 75 notes: wrong max 0.578, right min 0.687. Below ~75 notes the sets overlap.
- Today's stop 0.5 with partial on passes 1.86% of wrong 2-4-bar excerpts (per-piece mean).
- Registered: trimmed span -> confirm below 75 notes (mode all), stop below 0.625.
  Confirm cost: 75% of 2-4-bar and 15.6% of 5-8-bar right excerpts.
- Sibling pairs are not the hard case (dev max 0.48); same key slightly higher than other.

## Traps
- `correctness` crashed (IndexError) when partial alignment trims a wrong score to a span with
  no notes (Debussy Little Shepherd). Fixed with `_at` guard; test in test_correctness.
- `pkill -f <main script>` leaves ProcessPool spawn workers orphaned (ppid 1): kill them by PID.
- Reachability from dev subsets was 1.0 for every row: uninformative; report tail margins.

## Held-out (prereg bab3e6e3...d656, seed 4040, 24 pieces): PASS, Provisional
- H 0 of 4,370; F 1 of 190 (17-32 2.17% vs 2.5%, resample pass 0.74) = BL-36 span miss on
  Op. 49/2 i Aria (21-bar excerpt given rows 3-12; the next-lowest right unit is the same take).
- Confirm cost rose vs dev (85% / 33% of 2-4 / 5-8-bar right excerpts): sparse repertoire.
- Rejected dev alternative (0.65, no minimum) also passed held-out: data cannot separate them.
- Second empty-span crash: parangonar `join_by` on an empty score array -> guard in
  `align_note_arrays` (all insertions). Henry's 10 takes: all whole under partial, decisions
  identical; A-01 reports identical old vs new except input paths.
