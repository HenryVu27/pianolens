---
name: r07-symupe-finetune-audit-facts
description: R-07 audit (2026-10-05) - Windows/RTX box paths, read-only rerun recipe, prereg diff vs e4becf8, S-LR decomposition, H1b expert-sampler ceiling 0.273, R10u composition, _log json trap
metadata:
  type: project
---

R-07 audited 2026-10-05: Confirmed with caveats. Facts the docs lack:

- **Machine.** Windows 11 RTX 5080 box. Use `C:/Users/Vuduc/r07/venv-symupe/Scripts/python.exe`, with
  `sys.path.insert(0, ".../job")` before `import summarize_eval as se`. It brings `boot_ci`,
  `t_interval`, `h1b_passage`, `gen_prediction`, `feats` and `target_r`; pianolens imports work.
- **Bash tool trap.** `ls -t` on 64k-file dirs exceeds 120 s, so use `find ! -newer`.
- **Line endings.** The repo files are CRLF in the working tree (autocrlf). The Edit tool rewrote
  REPORT.md as LF, so convert back with `sed -i 's/$/\r/'`, and append to README with CRLF.
- **Pre-registration check.** Diff `git show e4becf8:README.md` against the working copy, both
  cut at `## Run record`. They are identical. The analysis scripts are unchanged since e4becf8.
- **`_log_<job>.json`** is overwritten by every invocation with only the items processed then.
  "0 errors" in a log is vacuous after a resume, so check completeness with file counts per
  arm x set.
- **(a) on P.** The K = 4 sample-half split is a cheap robustness check for the generation-based
  r: the halves of the frozen run differ by up to 0.025 per work.
- **S-LR.**
  - −ℓ_F alone gives R1 = 1.000 and fails R2.
  - ℓ_E alone gives R2 and fails R1.
  - Among humans, ρ(S-LR, −ℓ_F) is 0.83 on P and 0.95 on V.
  - scale0.5 AUC is 0.49.
  - F (autoregressive) treats vel±12 and slow15 as in-family.
- **H1b captured share.** Hold out 16 real renditions as "samples" and pass them to
  `h1b_passage` as curves: the median is 0.273 on 72 R10u pieces with ≥ 36 renditions. E reaches
  0.097 on the same splits, about 0.39 of that. The 0.50 bar is unreachable at K = 16. The
  16-expert R²c is 0.90.
- **R10u eval set composition** (91 pieces):
  - 75 of the 76 unseen (Glinka *La séparation* has no item);
  - 3 R-02 Mozart K. 545 paired;
  - 7 non-R-02 paired (WTC work-mates);
  - 6 non-R-02 unpaired.

  In R10 sets, `performer` = `source_performance_id`, so it is one row per cluster.
- **Articulation regime.** Median log articulation is −0.69 for P performances and +0.02 for
  R10u transcriptions. E's samples on P sit at +0.15: E learned the transcribed regime.

Related: [[r06-expression-h2h-audit-facts]], [[r02-dimensionality-audit-facts]]
