---
name: r10-h1b-audit-facts
description: R-10 H1b audit 2026-10-06 - hash recipes (amendment block moved), Mac-only recompute from committed CSVs via audit_checks.py, shape vs amplitude (r same as dev, b overshoot on flatter fresh consensus), dev-scale flips to inconclusive, envelope-surrogate floor 0.36 for axes, R-10b separation
metadata:
  type: project
---

R-10 audited 2026-10-06: Confirmed with caveats (scoped). Facts the docs lack:

- **Hashes.**
  - Prereg: `head -n 409 README.md` = d679394f...5f09.
  - The amendment block moved from 417-517 to 445-545 when the box inserted the run record
    above it. Use the anchor command `awk '/^## Pre-run amendments/{f=1} f&&n<101{print;n++}'`,
    which gives 6215a057...4089.
  - Both are identical at 4047183 (18:25 UTC 2026-10-05).
- **Run integrity, from the committed files.** `run_meta.json` records git_head, a
  git_diff_sha256 equal to e3b0c442... (the hash of an empty diff, i.e. a clean tree), job file
  hashes and pieces hashes. Compare them with `git show 28c5a01:<path> | shasum`.
- **Mac recompute.** `experiments/2026-10-05-R-10-h1b/audit_checks.py`:
  - it imports `job/summarize_h1b.py` and uses `cluster_boot_median`, `reading`, `capture` and
    so on;
  - every summary.json median and CI reproduces exactly from `arms_per_piece.csv` filtered to
    `experts_per_piece` with n >= 20;
  - the box summary uses the `fresh_pieces.csv` composer column, while `composer_of` without
    meta splits names like "bach" and "Bach,_Johann_Sebastian".
- **Dev comparison.** Use `results_box/results/r10u_r07`, restricted to the R-07 unseen 74
  (`artifacts/r10u_pieces.csv`, n_periscope_paired == 0 & r02). It reproduces R-07's 0.328 /
  0.127 (velocity 0.329 here; log IOI 0.127 with the R-07 formula, 0.144 with R-06).
- **Core finding.**
  - Shape is the same on dev and fresh: velocity r 0.665 vs 0.672, log IOI 0.516 vs 0.553.
  - The velocity R²c halves through amplitude: b 0.94 -> 1.10, because the fresh consensus is
    flatter (target s.d. 7.3 vs 9.3) and the model only partly follows.
  - A dev-chosen global scale (about 0.63) gives 0.362 / 0.271 on fresh, inconclusive on both.
  - The best per-piece r² is 0.45 / 0.31, never 0.50.
- **Envelope-surrogate sampler on the H1b-axes.** It reaches 0.363 of the 16-expert oracle
  (random subspace 0.064). The model's 0.437 is null-adjusted to 0.16. The Mac fresh set
  reproduces k and cap_oracle exactly.
- **R-10b** used only R-02 pieces (42 decision + 40 calibration + 2 dry-run), with 0 overlap
  with the fresh set. Its README reports an envelope floor of 0.47 at K = 16 on R-02 per-beat
  curves.
- **Box-only checks** (K = 16 sample noise in b, stacking, mtimes, R-10b outputs, determinism,
  overshoot vs conditioning) are listed in the README Audit section 10.
- `results_box/` has no logs, although the run record says it does.

Related: [[r10-h1b-prerun-review-facts]], [[r07-symupe-finetune-audit-facts]], [[r02-dimensionality-audit-facts]] (envelope null).
