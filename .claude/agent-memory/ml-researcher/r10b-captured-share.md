---
name: r10b-captured-share
description: R-10 H1b prep facts - span captured share has a high structure-free floor on R-02 curves, null-adjusted ratio design, calibration set, prep speed, piece availability
metadata:
  type: project
---

R-10 pre-registered 2026-10-05 in `experiments/2026-10-05-R-10-h1b/` (prereg sha256 f3ebdd9f...71ed,
lines above "## Dry run"). Job prepared and dry-run on the CPU; GPU run waits for the lead's review.

- **Span captured share is lenient on R-02 beat curves.** An envelope-surrogate sampler (no
  cross-performer structure) reaches 0.47 / 0.53 / 0.58 / 0.64 of the expert-sampler ceiling at
  K = 16 / 24 / 32 / 48 (40 calibration pieces). The unadjusted ratio cannot reach "falsified".
  The deciding statistic is therefore null-adjusted: rho = sum(C_model - C_null) / sum(C_expert - C_null).
  This probably also applies to R-07's 0.46 "of expert level" (it had no envelope null).
- Mixture sim at K = 32: f = 0 / 0.25 / 0.5 / 1 real samples -> rho 0.00 / 0.48 / 0.74 / 1.01,
  CI half-width 0.05-0.08. Top-k (magnitude-aware) variant: 0.32 at f = 0.25, wider CIs.
- R-02 audit numbers reproduce on calibration pieces: median k 3, 22% k = 0, shared share 0.37.
- No fresh unseen pieces exist: the only unpaired non-R10u piece with >= 50 majority-score
  performances is bach_bwv871_prelude (52). R10u unseen with >= 82: 42 pieces (K = 32).
- Prep speed on the 5080 box: 11,692 performances in 64 min at 3 workers (PianoCoRe load +
  F-03 tempo); decision set 6,479 performances.
- PianoCoRe performer ids: `pianocore:unknown/<row>` for most Aria rows; no leave-performer-out.
- Git Bash trap: `python - 2>/dev/null || venv/python - <<EOF` hangs (heredoc goes to the second
  command; bare `python -` waits on the terminal). Call the venv python directly.
- Pre-existing failing test (not mine): tests/compare/test_compare.py::test_match_loudness_equalises_and_respects_peak.

**Why:** R-07 audit required a calibrated ceiling; this note keeps the null-floor finding.
**How to apply:** any subspace "captured share" claim needs an envelope-null sampler, not only a
random isotropic subspace. See [[r07-finetune-job]], [[r02-dimensionality]].

**Superseded (2026-10-05, lead):** this was written on the RTX box without seeing the Mac session's R-10 pre-registration. The official R-10 is the Mac one (experiments/2026-10-05-R-10-h1b, R²c primary). This work lives on as exploratory R-10b (experiments/2026-10-05-R-10b-h1b-captured-share), non-deciding.
