# R-02 (H1 expression dimensionality, PianoCoRe tier A) audit facts, 2026-09-27

- Prereg: README Write at 00:34 UTC in agent-acef4d73a9db1c5c6.jsonl; sha256 of the Write content
  3ae426a9... == `head -144 README.md | shasum -a 256`. Amendments appended 00:54 (after 8-piece
  dry run, before full run 01:57). Keep lines 1-144 untouched.
- Rerun recipe: import `analyze` from the experiment dir (sys.path), call `load_blocks` + `joint`
  on `artifacts/curves/<slug>.npz`; slug via `pianocore_cache.piece_slug`. Phase null reproduces
  exactly with `rng=default_rng(0)` consumed as in `analyse_set` (phase_joint first). Run with
  OMP/VECLIB threads = 1; 698 pieces x (5 seeds + 40 surrogates) took a few minutes on 10 workers.
- Phase-randomized null is weak: it removes both cross-performer alignment and the per-beat
  variance envelope. Envelope null (phase surrogate then rescale each column to real column SD)
  gives k80 24 vs phase 25 vs real 19. Parallel analysis (eig > 95th pct of 20 surrogates):
  median 5 above phase, 3 above envelope; those carry 0.46 / 0.35 of between-performer variance.
  So the 80%-criterion count mostly counts individual variation. Relevant for H1b / tier D.
- Robustness measured: subsample seeds 0-4 share>20 = 0.345-0.364; tempo weight 25/50/75% ->
  k80 20/19/18; strict QC (>=99% observed) does not lower count; no near-duplicate rows.
- Disklavier control: k80 at d~10 is capped at 9, so only PC1/top3/LOO carry information. No
  Disklavier-transcribed twins (corr > 0.95). Vienna `_curves_matrix` applies beat QC separately
  per set (possible beat mismatch, unchecked, small).
- Generic lesson: for any "real vs surrogate null" count claim, ask for a parallel-analysis count
  and an envelope-preserving null; "below null on 100%" is usually near-trivial.
