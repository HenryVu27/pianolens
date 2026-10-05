---
name: r07-symupe-finetune-audit-facts
description: R-07 audits 2026-10-05, two independent ones. Mac (committed stats, origin checkout, R10 expert-curve rebuild, oracle 0.25, S-LR by construction, gate miss) and RTX box (full outputs, prereg diff vs e4becf8, S-LR decomposition, ceiling 0.273, R10u composition, _log json trap)
metadata:
  type: project
---

## Mac audit (committed statistics only)

- Context: results were committed on the RTX 5080 box (origin/main 881f9f9). The main tree had not
  merged them, so the audit read a read-only checkout in the session scratchpad. The audit went
  into a new `AUDIT.md` (the lead moves it into the README).
- Prereg: `head -n 300 README.md` = 17dfca04...083b = Mac `artifacts/prereg_sha256.txt`. Line 2
  (the stale status) is inside the hashed header.
- Rerun recipe: `sys.path.insert(job dir)`, `import summarize_eval as se`, then `se.boot_ci(j,
  "d_composite", pooled=False)` on the paired `a_per_rendition.csv`. Everything reproduces to 4
  decimals. The per-item `scores.csv` was NOT committed, so per-field S-LR needs the box.
- R10u/R10s expert curves can be rebuilt on the Mac:
  - `prep_data.select_pianocore` then `_pianocore_piece`, roles R10u/R10s, 10 workers, 108 s,
    6,025 items;
  - mirror `make_eval_items.from_prep` (majority score, first 3,000 notes, `_cap`, at least 16
    notes);
  - `h1b_passage` k/var_shared then match `h1b.csv` exactly.

  The R-02 cached curves are not needed.
- Captured share has an expert-oracle ceiling. Sixteen held-out experts reach a median of 0.25
  (R10u) / 0.23 (R10s); in-sample 16 reach 0.61. It rises with the reference size (0.21 / 0.24 /
  0.26 at 16 / 24 / 32). Models reach 0.10-0.12, about half. A 0.50 bar is unreachable.
  Mean-curve R²c oracle (16 experts vs the rest) is about 0.89.
- R-07 `h1b_passage` R²c does not center the predicted log IOI curve; R-06 did. It is a lower
  bound. Velocity is unaffected.
- S-LR (ℓ_E − ℓ_F) R1 is near construction:
  - every deadpan uses durations 0.95 × nominal, inside F's U(0.85, 1);
  - half_flat_velocity sits at F's velocity mode;
  - B-amount also scores 1.000.

  scale0.5 AUC is 0.491 on P.
- Gate: R-06 unrounded 0.3882 vs 0.3987. The paired shift is mostly log articulation +0.032.
  Mac digests of the R-06 P/V/A items are listed in AUDIT.md B3.
- E's R10u gain is Aria-AMT only (77% of training). It is absent or negative on Transkun V2/ATEPP
  (join `a_per_rendition.performer` = `source_performance_id` to the prep manifest's
  `capture_model`).
- R10 a_per_rendition `performer` is unique per row, so the two-way bootstrap is effectively
  passage × row.
- Box scripts B1 (S-LR fields + combined baseline) and B2 (centered R²c + reduced-subspace oracle
  ratio) are in AUDIT.md. They were tested on `artifacts/dryrun/outputs` (rerun the summariser
  with `--min-h1b-renditions 3` first).

Related: [[r06-expression-h2h-audit-facts]], [[r02-dimensionality-audit-facts]], [[bl18-strong-tier-audit-facts]] (Aria-AMT = Aria-MIDI corpus confound).

## RTX box audit (full outputs)

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
