---
name: bl37-edge-bars-audit-facts
description: BL-37 (edge bars of a trimmed span, k=1 missed-low-confidence policy) audit 2026-10-11 - prereg/deviation reconstruction recipe, read-only recompute, omission-injection probe (the policy's real harm), prod-vs-eval tier check, H1 with policy fails, all-pairs wrong-piece probe, fallback crash path
metadata:
  type: project
---

- Prereg anchor `awk '/^## Pre-registration$/{f=1} f{print} /^End of the BL-37 pre-registration\.$/{exit}'`
  = 4b1e7374...a86c. Same author transcript as BL-36 (`agent-a9af24a6302e4c775.jsonl`, session
  73c389dd): hash 13:20:36Z, crash 13:20:58Z, relaunch 13:21:14Z, draw 13:21:59Z.
- Deviation check recipe: take the committed script, reverse the python-replace edit shown in the
  transcript tool call, sha256 -> must equal the hashed prefix (2feeff... matched). src hash:
  `git diff <HEAD-at-hash> <commit> -- src/pianolens/align src/pianolens/report | shasum -a 256`
  reproduces the `git diff HEAD` hash taken at prereg time.
- Read-only recompute: import scripts/eval_edge_bars_bl37.py as module `e37`, `evaluate(rows)` on
  `data/interim/bl37/heldout_rows.pkl` (~5 min). Do NOT run main (overwrites csv/summary) or
  --probe (overwrites probe csv). check_ornament_fallback_bl37 main writes ornament_fallback.json;
  import `one()` instead.
- Spawned-worker scratch scripts: put a module in scratch, run with PYTHONPATH=scratch and
  `uv run python -c "import mod; mod.main()"`; load e37 by path inside each worker.
- Cut copies are reproducible from cache: `perf.notes` onset in [t_lo, t_hi) from `cuts[kind]`;
  N re-run equals cache (131 of 131).
- Main finding: D1/D2 inject wrong pitches only; k=1 drops missed notes only. Omission probe
  (delete 3 correct notes in d=0 bar, realign N): ranked notable+ 60.2% none -> 17.3% k=1 (0% when
  bar is N's edge, 68% of bars); half-bar deletions are shrunk to "not recorded" 64% even w/o policy.
- Production `_correctness_section` with edge_low_confidence_bars=1 equals eval `_tiers` on 3,611
  bars (fast repeats off). Production default fast-repeat on differs from rule P (pre-existing).
- B rows are computed WITHOUT the policy; H1 Aria-AMT strong with k=1 = -0.1548 (fails 0.15).
- All-pairs wrong-piece probe (16 excerpts x 43 scores x 2): max 0.524, 2 of 1,376 >= 0.5.
- Ornament fallback: non-crash path identical by construction; crash only on dev "short" copies.
- Verdict: Confirmed with caveats; adoption of k=1 left to Henry (suggested time-based policy).
