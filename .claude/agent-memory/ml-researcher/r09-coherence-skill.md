# R-09 H4 coherence vs MAJEPPA skill (2026-09-28, Confirmed with caveats: inconclusive)

Folder `experiments/2026-09-28-R-09-coherence-skill/` (build.py, noise_floor.py, analyze.py).
Cache: `artifacts/coherence.csv` = per-performance coherence (4 channels, n, n_blocks, y_sd,
r2, r2_no_markings) + phrase-tempo (cadence starts) for all 1,604 D-10 performances, plus
match_ratio / alignment_suspect / offgrid / note rate / duration / n_score_bars. Reuse it for
any MAJEPPA shaping question (build = 632 s at 8 workers).

## Facts
- D-10 gates reproduce exactly: 1,081 tier-B perfs; matched-context (practice+performance) 331
  (3-group pieces) / 388 (6-level pieces). No virtuosos, 9 teachers in matched contexts.
- MIDI scores -> r2_no_markings == r2 (no marking groups).
- `n_blocks >= 3` is gamed by bar numbering: Czerny Op.101 8-bar etudes (bars 0-8) give 3 blocks,
  R² down to -80 (velocity) even with clip_to_train. Also require >= 12 distinct score bars.
- Noise floor (65 D-10 pairs): on Aria-AMT, timing coherence robust (|diff| 0.008, rho 0.95),
  articulation NOT (|diff| 0.080, rho 0.36): transcribed offsets. Transkun (6 pairs) is
  unresolved (timing rho 0.58 [0.00, 1.00]); never claim "survives Transkun" from it.
- Note rate alone predicts skill rank leave-piece-out (Spearman 0.52); coherence adds nothing
  (-0.032 [-0.074, +0.012] with >= 12 bars). The registered "-0.061, hurts" came from 3 short
  Czerny rows: check S8-type claims for a few extreme-feature rows.
- Pooled timing effect lives in teacher/virtuoso clips (levels 1-4: +0.018 [-0.020, 0.062]);
  A3 -> A1 drops context AND the top levels, so never write "it vanishes with context".
- Power: 97.5% half-widths 0.027 / 0.018 > SESOI 0.01 -> P(falsified | slope 0) ~8% / 16%.
- Mistakes I made (audit): hash prefixes attached to the wrong files; Command said workers 6 for
  noise_floor (ran 4); did not disclose the post-prereg 2-score build test and boot-20 smoke test.
  Disclose every post-prereg run, and compute hashes with a filename-labelled command.
- 2026-09-28 post-audit text fixes applied (README "Post-audit corrections"; header hash
  c44a4b74...8517 unchanged; D-10 spec got a post-audit note on the same confound).
- PSyllabus difficulty join (surname + op/no/BWV tokens) covers 51% of gated MAJEPPA perfs.
- Fast FE OLS: within-piece demean via np.bincount; 2,000 cluster-bootstrap refits take seconds.
