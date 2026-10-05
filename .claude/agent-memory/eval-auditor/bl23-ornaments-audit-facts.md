# BL-23 / DF-09 / DF-10 audit facts (2026-09-29)

- Prereg: section '## Pre-registration BL-23' to EOF of docs/specs/correctness-validation.md
  (lines 266-336); `sed -n '266,$p' | shasum -a 256` = 1444e934...2146. Author transcript
  subagent agent-acbc9f10b77284aba (append 21:58:46Z, script written 22:00:42Z).
- Rerun: `OMP_NUM_THREADS=1 uv run python scripts/eval_correctness_bl23.py --part all --workers 12
  --out <scratch>` ~755 s; byte-identical summary.json and CSVs. 400/1004 progress looks stalled
  for minutes (slow asap/floor jobs); workers are busy, just wait.
- Swap precision recipe: monkeypatch `pianolens.align.postpass.reassign_same_pitch` (imported
  inside correctness at call time) to record swaps, compare with lab.alignment matches
  (script was /private/tmp/claude-502/-Users-vuducdung-personal/9591b65d-e4c5-4ea1-a251-fd7c9f357b13/scratchpad/bl23_audit/swap_precision.py, not persistent). Clean copies aligned: 230 fix / 35 break /
  23 neither / 3 of 291; gt mode: all 147 swaps are breaks by construction.
- N3 driver: schubert_d899_no1 (2 perfs) = 1,309/2,895 tolerated notes, 124/188 TR flags,
  47/57 dissolved matches; 172 'tremolo' marks = unexpanded abbreviations. f02_orn.parquet has
  per-note rows (variant, kind, label, bar_legacy) for recurrence checks across sources.
- DF-10: parangonar ornament step (matchers.py ~1401, ±2, only n.ornaments, only with score_part)
  is the only source of different-pitch matches, so the legacy pitch check is zero by construction.
- DF-09: four-hands duets in catalogue (faure_op56_mv1, dvorak_op72_no2, Ravel Ma mere l'Oye 5)
  split inconsistently; chopin_op29 has a 'Flauta' part. Rerun staff_hand_proxies 137 s.
