---
name: r10-h1b-prereg
description: R-10 H1b pre-registration and box job (2026-10-05) - fresh piece pool, oracle method, thresholds, dry-run home, runtime rates, Windows traps
metadata:
  type: project
---

Folder `experiments/2026-10-05-R-10-h1b/` (prereg head -n 409 sha256 d679394f...5f09; status:
pre-registered, not run, waiting for the RTX 5080 box). Related: [[r07-finetune-job]],
[[r06-expression-models]], [[r02-dimensionality]].

## Fresh pool is small
- PianoCoRe pieces unseen by SyMuPe (unpaired in PERiScoPe) are nearly all R10u already when
  n >= 50. Pool by minimum majority-score performances: >= 20: 65 pieces (after work-mate and
  alias rules); >= 36: 22 by metadata; >= 50: 1. After the match filter: 59 with >= 20 usable,
  15 with >= 36, 12 with n >= 36 and k > 0. 92% Aria-AMT; no piece has >= 10 renditions from
  any other source (per-source tables must be rendition-level).
- R-07's prep caps 50 over ALL scores and takes the majority score afterwards; R-10's
  `build_set.py` restricts to the majority score first (default; `--r07-cap-rule` for R-07's).

## Methods that worked
- Analytic K-matched oracle: 1 - sum_j s2_j (1/K + 1/n_j) / sum_j mc_j^2 (random-effects model)
  matches the empirical 16-held-out oracle to median |diff| <= 0.009 (fresh and R10u) and works
  for pieces with n < 36. Values: fresh velocity 0.878, log IOI 0.882; R10u ~0.91.
- Equivalent-experts scale for captured-share ratios: K' experts relative to 16 reach 0.09 / 0.24
  / 0.56 / 0.80 for K' = 2 / 4 / 8 / 12 (fresh and R10u agree). Expert-as-model ratio on R10u
  (16 + 16 + 18) median 1.013, log-sd 0.085; frozen captured log-sd across pieces 0.543.
- Reachability: piece-level bootstrap of the median with dev per-piece R²c shifted to mu
  (`reachability.py`); CI half-width 0.10-0.13 at 59 pieces.
- Primary decided on top-p 0.95 samples (R-06/R-07 lineage), axes on top-p 1.0 (DECISIONS).

## Running it
- Dry-run home with both venvs + models: `experiments/2026-10-05-R-10-h1b/artifacts/dryrun/home`
  (torch 2.7.1 CPU). Mac CPU generation K=16, OMP 1 thread: SyMuPe 130-175 ms/note; PT (K=4)
  148-186 ms/note. Box PT rate from R-07 run record: ~113 ms/note (K=16). No logged SyMuPe GPU rate.
- Fresh gen notes 74,262 (65 items); R10u dev 131,674.
- Windows box: folder `.gitattributes` forces LF (core.autocrlf broke R-07 .sh and hashes); the box
  checkout must have origin/main's pianocore.py temp-file fix (881f9f9).
- `stage` heredoc pattern in run.sh: `stage meta "$PY" - args <<'PY'` works (stdin passes through).

## Pre-run review amendments (2026-10-05, lead-accepted)
- What I missed, now fixed: (1) whole-set ids (2 Arabesques, Tombeau suite) and a movement inside
  an R10u whole set passed id/alias/work-mate rules -> `amend_pieces.py` score-content check
  (12-onset pitch-set n-grams vs held refined scores; exclude self!). (2) near-duplicate
  renditions (cross-corpus copies, re-uploads) inflated the 16-held-out axes oracle -> drop later
  of any pair with deviation r > 0.9. (3) My README said the top-p switch used no R²c, but run3's
  summary had printed both arms' R²c: disclose every printed number, not what I think I used.
- Amendments live below `## Run record` with their own hash (sed -n '417,517p' = 6215a057...);
  exclusions are summariser flags so the set digest stays; run.sh writes results/fresh (amended)
  and results/fresh_as_registered.
- Final counts: primary 56 pieces / 54 works / 1,691 renditions; oracle 0.877 / 0.881; axes 12.
- Dev references for the box in pieces/dev_reference.json (ridge: 138 pieces, 97 works, alpha
  1000 / 1, CV r 0.516 / 0.167).
