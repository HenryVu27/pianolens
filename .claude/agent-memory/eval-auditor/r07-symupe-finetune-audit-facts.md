---
name: r07-symupe-finetune-audit-facts
description: R-07 (SyMuPe/PT fine-tune) audit 2026-10-05 - prereg hash, read-only origin checkout, Mac rebuild of R10 expert curves, captured-share oracle, S-LR by-construction, gate miss
metadata:
  type: project
---

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
