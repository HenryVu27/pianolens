---
name: bl36-partial
description: BL-36 partial recordings - subsequence onset DTW span detection design, dev numbers, snap/margin tuning, bite check, eval script layout and traps (2026-10-11)
metadata:
  type: project
---

# BL-36 align partial recordings (2026-10-11)

Related: [[df15-bl27]], [[df13-pairing-window]], [[partitura-parangonar-traps]].

## Design (`align/partial.py`, `align(..., partial=True)`, flag `PARTIAL_DEFAULT = False`)
- Subsequence version of parangonar's onset DTW (pitch vs onset pitch set, 0/1). Rows in closed
  form: horizontal chains = prefix min of (A - cumsum) -> numpy per row, two rows of memory,
  start column tracked; ~0.2-0.4 s on Op. 54 (5.7k notes x 967 bars). Checked vs naive.
- Run on every repeat path; whole (snap <= 8 notes per side, cost within 2% of best) -> plain
  `align` output (byte-identical). Else widen trimmed sides by >= 2 bars and >= 16 notes, trim
  (fresh unfolding, `part.remove`), parangonar, shrink edge bars >= 50% missed.
- Score meta: `recorded_span` record + `bar_labels` (pass suffix kept; `report.build.bar_labels`
  honours it). Report adds `rep["recorded_span"]` + one confidence note "Not recorded: ...".
- `report_from_files(partial=)`: same-score / correctness refs cut with `restrict_to_score`.

## Dev (BL-27 dev pieces; `data/interim/bl36/dev_v2_*`)
- N vs C (means over pieces): span acc 0.994 vs 0.600; never-played tiered 0.011 vs 0.160;
  strict agreement 0.997 vs 0.942. Excerpts inside literal repeats go to the earlier identical
  occurrence (Op. 54, Op. 58/2): use content-equivalent agreement to see it.
- Snap trade-off (offline grid over DTW spans, scratch only): snap 24 graded 2-bar cuts of
  Op. 28/20 (13 bars); snap 8 + note margin fixes most. 32-note margin slightly worse.
- Harm bars must be checked to bite: edge-happy sabotage (`--natural-only --override ...`)
  moved Aria H1 -0.18/-0.36 pt (passes ±0.25/±0.5!) -> registered ±0.15/±0.30 and not-recorded
  share <= 0.002. Transkun H1 cannot bite (natural Transkun copies all whole).
- Reachability 0.9935 (2,000 x 16 pieces).

## Traps
- Eval: `--from-cache` re-reads the script's BARS, so re-scoring after a bar change rewrites
  the summary; the running process keeps the old code (Python loaded it at start).
- Henry A-01 reruns: all 10 takes whole; only diff 03 Aria float noise (5e-9, known).
- Prereg sha 10d50146...51ae (07:16 UTC); held-out seed 3636, 8 literal-repeat + 8 other pieces.
- HELD-OUT (07:52 UTC, 35 min): PASS every row, 0 LOO flips. N vs C: acc 0.997 vs 0.610,
  never-played tiered 0.0027 vs 0.121, strict agreement 0.996 vs 0.950 (excerpts 0.976).
  Fragile row: H1 Aria strong -0.089 (pass share 0.79) = Op. 28/16 truncated Aria segment whose
  unrecorded bars C tiered strong (a correction, not harm). Transkun natural all whole.
- Residual: 280 of 332 extra strong played bars sit next to the cut (truth by expected onset,
  removal by actual onset). Excerpts in literal repeats -> earliest occurrence.
- Readout helper (CIs, pass share, LOO) was a scratch script; per-row values in
  `artifacts/heldout_readout.json`.
