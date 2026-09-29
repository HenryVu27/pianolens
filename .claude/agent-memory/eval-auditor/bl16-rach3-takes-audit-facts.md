# BL-16 Rach3 Hanon takes audit facts (2026-09-28)

- Prereg `head -113 README.md` sha f9336acc...2c54. It equals the data-engineer `Write` (not a
  heredoc) in subagents/agent-a1d67a944b65494fc.jsonl at 00:22:09Z. Runs started at 00:22:26Z.
  Extract it with jq `.input.content` of the Write whose file_path matches BL-16.*README.
- Rach3 file name `p<k><YYMMDD><sitting digit><NN>...`: the sitting digit is 0 for EVERY Hanon
  file (one sitting per day), and NN (chars [9:11]) is the file order. The `session` column is
  therefore constant, and a sort on (day, session, t0_sec) orders takes by the onset inside
  their own file. p1 saves each pass as its own file (33/42 same-day pairs span files); p2 and
  p3 play many passes per file.
- Rerun recipe: copy run.py and analyze.py plus the artifacts' groups_*.jsonl into
  scratch/bl16/, and run analyze.py there (byte-identical, 1 s). variants.py (in
  artifacts/audit/) imports the scratch copy of run.py and re-scores pairs from the built takes
  (data/interim/rach3_hanon_takes). Same-day in 16 s, and it matches the artifacts exactly.
  Set BLAS threads to 1 and use 6 workers.
- KEY FINDING: the cross partner comes from a random day, and the same pair from one sitting.
  The same-pianist other-day control (c1) removes most of the advanced gap: cross - c1 is
  0.011 [-0.015, 0.034]; p2 same 0.009 / c1 0.038 / cross 0.068. p3 holds: 0.041 [0.028, 0.052].
  General pattern: a cross-unit control must also match the time separation (or the other
  nuisance) of the within-unit pair.
- R²(diff) scales with the noise level of the pair: p1's cross pairs have 1.7x the variance of
  its same pairs, which deflates the cross R². Check var_pair_diff (in the structure records)
  before reading per-pianist R² gaps.
- The |log duration ratio| of a pair predicts R²(diff) (slope 0.05-0.07). p3 vs its advanced
  partners: 0.28 median. The tempo-adjusted B gap is 0.039.
