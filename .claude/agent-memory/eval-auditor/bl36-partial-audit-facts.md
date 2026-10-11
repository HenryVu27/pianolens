---
name: bl36-partial-audit-facts
description: BL-36 (partial recordings, subsequence DTW span) audit 2026-10-11 - prereg/timeline recipe, read-only recompute, re-run probes (identity, wrong piece, restrict_to_score, edge bars), the edge-bar false strong flags, C reused as N for whole targets, Schumann Op. 16/7 variant-relabel branch
metadata:
  type: project
---

- Prereg anchor `awk '/^## Pre-registration$/{f=1} f{print} /^End of the BL-36 pre-registration\.$/{exit}'`
  = 10d50146...51ae. Author transcript session 73c389dd `subagents/agent-a9af24a6302e4c775.jsonl`:
  hash+launch 07:16:51Z, draw files 07:17:43Z (file mtimes are CDT = UTC-5). Dump tool calls with
  jq to a scratch file and grep "heldout|3636|eligible" with timestamps.
- Read-only recompute: import `scripts/eval_partial_bl36.py` as module (sys.modules first), call
  `evaluate(rows)` on `data/interim/bl36/heldout_rows.pkl` (~60 s). Do NOT run main `--from-cache`
  (overwrites summary/csv); do NOT run `--draw-only` (overwrites heldout_draw.json).
- `target_one` sets C := N when the span is whole, so whole-target C rows are N by construction.
  Audit re-ran 93 whole natural targets with partial off/on: identical pairs, notes, tables.
- `best.variant != span.variant` branch fires on all 20 Schumann Op. 16/7 natural targets
  (detection picks the path without the C-B repeat). Probe: wrap `pianolens.align.partial.detect_span`.
- Edge finding: first/last fully heard bar strong under N 12.3% (clean 1.1%, C 23.3%); 327 of 332
  extra strong bars lost no notes (onset blur explanation wrong). Needs perf onsets: reload MIDI
  via `report.io.load_performance` from the PianoCoRe zip (no alignment, fast).
- Wrong-piece probe (app check, WRONG_PIECE_MATCH 0.5): partial on, wrong-score Dice max 0.367,
  right-score 8-bar excerpts 0.779-1.0. Scripts in scratch only (bl36a/), not kept.
- restrict_to_score has no test; real-data probe equal except first span bar (+1-3 extras).
- Dev Transkun natural targets were NOT all whole (v2 1/119; sabotage 20/119).
- Iterating per-bar with `perf_bar` dict scans is slow (minutes); precompute bar -> pids once.
