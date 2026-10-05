# R-07 audit (2026-10-05, eval-auditor)

For the lead: move this into the R-07 README as `## Audit (2026-10-05)` after merging origin/main
(881f9f9). Audited from a read-only checkout of origin/main. The box-only outputs (`job/outputs/`)
were not available. Every number below was measured in this audit from committed files, or from
items rebuilt on the Mac with R-07's own code. Box-only checks are listed in section 10 with
commands.

## Verdict: Confirmed with caveats (scoped)

- **(a) per-note prediction: Confirmed.** E − frozen on P is "harms", and it reproduces exactly.
  **Pre-registered consequence: R-10 uses the frozen SyMuPe model.**
- **Reproduction gate: Confirmed as missed.** The pre-registered consequence was followed.
- **(c) typicality: Confirmed as registered** (S-LR pass, S-DEV flatness detector only, S-TYP
  fail), but scoped. S-LR has passed this battery and nothing more. It is not yet shown to be a
  typicality or quality score (section 5).
- **(b) H1b preview: the reading "at the H1b falsification level" is withdrawn.** The captured
  share was pre-registered with these thresholds, but the metric's own ceiling is below the
  "consistent" bar. Sixteen real held-out experts reach a median of about 0.25. The log IOI R²c
  also departs from the pre-registered R-06 definition. Corrected reading: "uninformative for
  H1b" (section 4).
- **Text fixes are required** before the README and REPORT are merged as final (section 9).

## 1. Pre-registration and order

- `head -n 300 README.md` (origin/main) hashes to `17dfca04...083b`. That equals
  `artifacts/prereg_sha256.txt` and `artifacts/prereg_README.md` in the Mac tree (file dated
  2026-09-27 23:46 local). README lines 1-300 are identical in e4becf8 (2026-09-28 00:13 −0500)
  and 881f9f9. Training started 2026-09-29 21:15 UTC. The pre-registration therefore predates
  the run and was not changed afterwards.
- The code changes since pre-registration are platform fixes only:
  - `job/{eval,run,setup}.sh`: `wpwd`/`vpy` helpers and the Windows `resource` stub;
  - `src/pianolens/data/pianocore.py`: the temp-file close.

  Between e4becf8 and 881f9f9 nothing changed in `summarize_eval.py`, `make_eval_items.py`,
  `prep_data.py`, `symupe_*.py`, `pt_train.py`, `trainlib.py`, `src/pianolens/models/` or
  `src/pianolens/eval/`.
- Disclosed but not pre-registered: the tokenizer order-guard skips (636 / 9 items) and the
  post-hoc pt_E − pt_frozen script (section 6). Neither changes a decision.

## 2. Split and leakage

- In the committed `split/pieces.csv`, no work spans two splits, and no work of P, V, A, R10u or
  R10s is in train.
- A prefix-alias scan over test and validation ids against train ids finds one pair. Train
  `schumann_op10` is a Scherzo with 0 tier A performances; val `schumann_op10_no3` is an Etude.
  It is harmless.
- The prep selection rebuilt on the Mac with R-07's own `prep_data.select_pianocore` and
  `_pianocore_piece` gives 6,402 rows and 6,025 test items, exactly as in the run record.
- Early stopping and checkpoint selection used the validation pieces only. No test score
  selected anything.

## 3. Statistics reproduce exactly

The summariser's own `boot_ci` and `t_interval` were run on the committed `a_per_rendition.csv`
files. Every paired composite difference in `summary.json` and in `pt_E_vs_pt_frozen*.json`
reproduces to 4 decimals, on P, V, A, R10u and R10s.

| Set | Comparison | Result |
|---|---|---|
| P | E − frozen | −0.0509 [−0.0720, −0.0287]; t over 3 works [−0.178, 0.076] |
| P | pt_E − pt_frozen | +0.0128 [−0.0133, 0.0394] |
| R10u | E − frozen | +0.0408 [0.0279, 0.0508] |
| R10u | pt_E − pt_frozen | +0.1003 [0.0888, 0.1143] |
| R10s | E − frozen | +0.0015 [−0.0156, 0.0153] |
| R10s | pt_E − pt_frozen | +0.0592 [0.0373, 0.0833] |

Every AUC row has its full n: 981 on P, 88 on V, 80 on A, 3,808 on R10u and 1,812 on R10s,
including S-TYP for frozen and E. That closes REPORT gap "frozen typset not checked".

### Reproduction gate (lead question 3)

- R-06's unrounded P composite for SyMuPe is **0.3882** (work mean of R-06 `a_per_rendition.csv`).
  The re-run gives **0.3987**. The difference, **+0.0105**, is above the 0.01 tolerance, so the
  gate is **missed** (by 0.0005; by 0.0007 against the rounded 0.388).
- The pre-registered consequence ("first finding; the comparison uses the re-run frozen numbers,
  R-06 shown alongside") **was followed**: REPORT 4b opens with it, and (a) is paired with the
  re-run.
- Paired per rendition against R-06, the composite difference is +0.0105 [−0.0001, 0.0206], with
  correlation 0.951 between runs. By target:
  - velocity +0.003 [−0.007, 0.013];
  - log IOI −0.003 [−0.023, 0.017];
  - **log articulation +0.032 [0.014, 0.049]**.

  So the miss is mostly a shift in articulation. Pure re-sampling noise would not shift it.
  Possible causes are the items rebuilt on Windows or GPU sampling. Other sets do not shift the
  same way: V frozen −0.013 [−0.027, 0.001], A +0.010 [−0.006, 0.021], pt_frozen P +0.002. This
  does not affect (a), which is paired within one pipeline. Box check B3 settles the item side.
- The phrase "missed by 0.001" in the README and REPORT should become "missed: 0.3987 vs 0.3882
  (R-06 unrounded), +0.0105 against a 0.01 tolerance".

### (a) on P and the R-10 model decision

- The reading is **harms**: the whole bootstrap CI is below 0.
- Per work: WoO 80 −0.045, D960 mv2 −0.105, D960 mv3 −0.003. By target: timing and articulation
  are worse, velocity shows no detectable change.
- Leave one work out: −0.054, −0.024, −0.075.
- The 3-work t-interval includes 0, as the rules require it to be shown. The reading uses the
  bootstrap, as pre-registered.
- Secondary sets point the same way on sensor MIDI: V −0.098 [−0.135, −0.063], A −0.094
  [−0.145, −0.053].
- **Decision rule, plainly: E's validation condition holds, but P is "harms". So E is not used
  downstream, and R-10 (and tier D) use the frozen SyMuPe EncDec-base.** The rule is followed
  correctly.

## 4. H1b preview: metric validity (lead question 1)

**Was it pre-registered?**
- Yes. README (b) names the captured share as the statistic, with the plan's thresholds (≥ 0.50
  consistent, ≤ 0.20 falsification level), and applies the same thresholds to the mean-curve R²c.
  The run applied them as written.
- But it registered no ceiling for the captured share. R-06 (b2) had introduced it as
  exploratory, without thresholds. That breaks hard rule 2 ("no claim without a baseline and a
  ceiling") and the R-09 reachability lesson.

**What the captured share measures.**
- The expert matrix J is the between-performer deviation from the expert mean curve. The model
  side is the span of the model's 16 samples, centered on the model's own mean.
- So the statistic asks whether the directions in which the model's samples differ from each
  other line up with the directions in which performers differ. It is a property of the model's
  sample *diversity*, not of what it predicts.
- A model that predicts the expert mean exactly with no sample spread scores 0.
- The plan's H1b says "explains at least 50% of the held-out variance in the shared expert
  components". A score-only model cannot predict an individual performer's position on those
  components. Captured share is one defensible reading (do the model's alternatives span the
  interpretive axes), but only against an oracle.

**Expert oracle (measured here).**
- The R10u and R10s expert curves were rebuilt on the Mac with R-07's prep and summariser code.
  For all 85 R10u and all 39 R10s pieces, n_perf, n_onsets, k and var_shared match the committed
  `h1b.csv` exactly.
- The model's 16 samples were then replaced by 16 real performances of the same piece (5 random
  draws per piece).

| Set | 16 experts, in-sample subspace (upper bound) | 16 experts held out, subspace from the other n − 16 (pieces with n ≥ 36) | Models on the same pieces: frozen / E / pt_frozen / pt_E | Median per-piece ratio, model / held-out oracle |
|---|---|---|---|---|
| R10u (72 of 85) | 0.61 | **0.253** | 0.120 / 0.098 / 0.103 / 0.126 | 0.52 / 0.44 / 0.44 / 0.54 |
| R10s (29 of 39) | 0.57 | **0.233** | 0.135 / 0.109 / 0.118 / 0.153 | 0.60 / 0.43 / 0.47 / 0.65 |

- The held-out oracle rises with the size of the reference group: on 42 R10u pieces with
  n ≥ 48, it is 0.208 / 0.236 / 0.260 at reference sizes 16 / 24 / 32. At the full panel it
  would be roughly 0.3, which is still far below 0.50.
- The held-out oracle itself is ≤ 0.20 on 23 of 72 R10u pieces and ≥ 0.50 on only 8.

**Consequences.**
- The "consistent with H1b" bar (0.50) is out of reach for real performers held out from the
  subspace estimate. The "falsification" bar (0.20) sits close to their level.
- "At the H1b falsification level" is therefore **not a supported reading**. The supported
  statement: every arm's samples span about 0.10-0.12 of the shared variance, about 8-10× a
  random 15-dimensional subspace and about half of what 16 held-out experts span. The roughly
  equal values on R10u and R10s, and across arms, fit a metric dominated by its own ceiling and
  sampling noise.
- One further limit: generation used top-p 0.95, which narrows the model's spread. A
  diversity metric should use top-p 1.0.

**Mean-curve R²c.**
- R-06 (b), which R-07 (b) cites as the definition, centers both curves:
  `mc = m - m.mean(); pc = p - p.mean()`.
- R-07's `h1b_passage` centers only the target, in the denominator. For velocity this changes
  nothing, because both curves are already centered per rendition. For **log IOI**, any constant
  offset between the model's mean curve and the experts' lowers R²c.
- The expert-side offset is small (median offset² / variance 0.023 on R10u, 0.045 on R10s). The
  model's offset is unknown (box check B2).
- The log IOI R²c values (−0.24 to 0.26) are therefore lower bounds of the pre-registered
  statistic. This is a bug against the pre-registration, not a choice.
- The R²c ceiling is reachable. The mean of 16 held-out experts against the mean of the others
  gives median R²c velocity 0.893 and log IOI 0.892 on R10u (0.887 / 0.837 on R10s). The
  split-half reliability is 0.98.
- Measured against that ceiling, the models reach velocity 0.31-0.55 of it on R10u and log IOI
  −0.03 to 0.30 (before the centering fix). R²c is the closer match to "explains variance", and
  its ceiling is known.

**Piece set.**
- The H1b median is taken over 85 R10u pieces. That includes 7 pieces paired in PERiScoPe (Bach
  WTC work-mates; Mozart K. 545 mv1-3) and 4 non-R-02 work-mates.
- The README says the 3 paired R-02 pieces are "reported separately". That was not done.
- On the 74 unseen pieces, the median captured share is E 0.096, frozen 0.112, pt_E 0.124 and
  pt_frozen 0.100. R²c is:

  | Arm | Velocity | Log IOI |
  |---|---|---|
  | E | 0.439 | 0.053 |
  | frozen | 0.328 | 0.127 |
  | pt_E | 0.495 | 0.259 |
  | pt_frozen | 0.303 | −0.021 |

  The 7 paired pieces read the same as the rest. Leaving them in barely moves the median, but
  the "unseen" label must be accurate.

**What R-10 should measure instead.** This needs a pre-registration, and a DECISIONS entry that
fixes the H1b operationalisation first.
1. **Consensus predictability (primary):**
   - mean-curve R²c computed with the R-06 formula, per target, on the 74 unseen pieces;
   - reported against the K-matched expert oracle (the mean of K held-out experts against the
     rest) and the Spearman-Brown reliability;
   - H1b thresholds applied to R²c, or to R²c divided by the oracle, chosen before the run.
2. **Interpretive-axis coverage (co-primary or secondary):**
   - captured share as a ratio to the held-out expert oracle, using the same reduced subspace for
     model and oracle (as in box script B2);
   - samples drawn at top-p 1.0, with K at least 16;
   - thresholds set on the ratio.
3. **Exploratory, closest to "explains held-out variance in the components":**
   - condition on part of a performance (its first bars, or its global tempo and dynamics);
   - predict that performer's component scores in the rest of the piece;
   - compare with a performer-mean baseline.

## 5. S-LR AUC 1.000 on every deadpan variant (lead question 2)

**Is the pass by construction?** In effect, yes for R1. Every R1 variant contains a field at F's
training mode, where the real rendition is far from it:
- all deadpans use durations 0.95 × nominal (`expression_data.LEGATO`), inside F's U(0.85, 1.0)
  family;
- the deadpans' velocity is the conditioning velocity (F's mode);
- half_flat_timing has flat durations;
- half_flat_velocity has constant velocity at the conditioning value.

F learned the flat durations almost deterministically (validation TimeDuration loss 0.044 nats).
Two consequences:
- −ℓ_F is very low for any human rendition and high for any variant with a flat field.
- The pre-registered claim that vel±12 and slow15 "test generalisation, not memorisation" is
  weak: their durations are still in F's family. The REPORT's "including the half-flat ones
  outside F's training family" is wrong. Each half-flat variant's flat half is inside F's family
  on the field that differs.

**What the committed files show.**
- The trivial **B-amount** baseline also scores 1.000 on all 7 R1 variants on P, V, A, R10u and
  R10s.
- **B-smooth** scores 0.877 / 0.943 / 0.990 / 0.999 on the P R2 variants (jitT20, jitT40, jitV8,
  jitV16). Those are above 0.75, though R2 also needs the CI.
- So R1 is solved by the amount of expression alone, and R2 nearly by smoothness alone. S-LR
  passes both in one score, which neither baseline does. But no combined trivial baseline was
  pre-registered, and its pass is not yet shown to beat one (box check B1).
- **Two-sidedness is partial.** For scale0.5 (real deviations halved), S-LR's AUC is **0.491**
  [0.397, 0.591] on P, 0.545 on V and 0.388 on A. S-LR cannot tell a real performance from the
  same performance with half the expression. It does prefer real to exaggerated (scale1.5: 0.915
  on P).
- The [1, 1] CI is degenerate: a perfect AUC resamples to 1. It carries no information about
  margin.
- S-DEV's flatness pass is also near construction: `zero_if_flat` gives every flat target r = 0.
  B-amount does the same job model-free.

**Reading.**
- "S-LR pass" stands as the pre-registered result of this battery.
- It should be worded as: "passes the deadpan and jitter battery; R1 is matched by the
  amount-of-expression baseline; at chance against halved expression (P 0.491); not tested
  against non-flat wrong expression".
- **Until box check B1 and a new, pre-registered non-flat battery are run, S-LR should not be
  used as a typicality or quality score.** That battery would include:
  - phase-randomised expression with the real spectrum;
  - deviations transplanted from another passage;
  - time-reversed or phrase-shuffled deviation curves.

  This is stricter than the letter of DECISIONS 2026-09-28 ("a score that passes may be used
  anywhere"), so it is a lead decision.
- For the F-06 "too flat" flag, B-amount is as good as S-DEV and needs no model.

## 6. pt_E vs pt_frozen (lead question 4)

- It was **pre-registered as secondary**: Question 4, and Baselines ("Pianist Transformer frozen
  vs fine-tuned (pt_E), same (a) and (b)").
- It was computed the same way. The JSONs are reproduced exactly with the summariser's `boot_ci`
  and `t_interval` (section 3).
- Fix: the script that wrote `results/pt_E_vs_pt_frozen*.json` is not committed. Commit it, or
  add a `--pair` option to `summarize_eval.py`.
- A's "improves" (+0.031 [0.0013, 0.064]) clears 0 by 0.001, on Pianist Transformer's own test
  folders. Read it as fragile.
- Context the README omits, pt_E − frozen SyMuPe:

  | Set | Difference [95% CI] |
  |---|---|
  | P | +0.009 [−0.015, 0.034] |
  | V | −0.160 [−0.294, −0.027] |
  | A | −0.131 [−0.200, −0.070] |
  | R10u | +0.052 [0.037, 0.064] |
  | R10s | −0.043 [−0.068, −0.012] |

## 7. pt_E R10u OOM retry (lead question 5)

- The committed R10u summary has every arm with 3,808 renditions and 85 H1b pieces. pt_E has
  model_dims 15, i.e. K = 16.
- Every non-pt_E number recorded in the run record *before* the retry is identical in the final
  summary:
  - captured share and R²c for E 0.098 / 0.413 / 0.065, frozen 0.118 / 0.325 / 0.142 and
    pt_frozen 0.101 / 0.251 / −0.024;
  - E − frozen +0.041 [0.028, 0.051];
  - pt_frozen − frozen −0.048 [−0.062, −0.039].
- Failed items are never written (save follows success), and per-item seeds are fixed (`--seed
  0` per item). So the retry cannot change other arms, and it is clean as far as the committed
  files show.
- The checkpoint used and the file timestamps need the box (B4). The first run's `_log_gen.json`
  was overwritten by the retry.

## 8. E harms on P but improves on R10u (lead question 6)

- REPORT 4b labels the "transcription characteristics" reading "one possible reading (not tested
  here)". It is correctly marked untested.
- A first test is possible from committed files. PianoCoRe source metadata was joined to the R10
  rows, and E − frozen was recomputed per capture model with the summariser's statistic. This is
  post hoc and exploratory.

  | Set | Aria-AMT | Transkun V2 | ATEPP |
  |---|---|---|---|
  | R10u | +0.044 [0.031, 0.055], n 3,540 | −0.012 [−0.027, 0.004], n 204 | −0.014 [−0.036, 0.014], n 54 |
  | R10s | +0.019 [0.001, 0.028] | −0.061 [−0.081, −0.027] | −0.051 [−0.076, −0.012] |

- E's training data were 77% Aria-AMT (17.6% Transkun V2, 5.1% ATEPP, by selected rows). So E's
  R10u gain sits entirely in the Aria-MIDI/Aria-AMT corpus that dominates its training. Within
  the same pieces, on other transcribers, it is absent or negative.
- That fits adaptation to the dominant corpus or transcriber rather than to expert expression.
- Transcriber and source are confounded here: Transkun V2 is PERiScoPe and Aria-AMT is Aria-MIDI
  (BL-18 lesson). Neither can be separated from the other.
- pt_E gains on every stratum, most on Aria-AMT. In the README this belongs under "exploratory,
  post hoc".

## 9. Required fixes (author: ml-researcher; lead to merge)

1. **README line 2** still says "Status: Provisional (pre-registered; job prepared, not run)".
   Line 2 is inside the hashed header, so changing it breaks `17dfca04...`. Leave it, and record
   the status in a Verdict section plus EXPERIMENTS.md (rules: "Record the audited status in the
   Verdict section").
2. **REPORT.md is stale:**
   - The header still says "while the job was still running".
   - Section 4 is titled "Results so far (training only; no evaluation results yet)", and says
     "Only step 1 had been logged" for pt_E.
   - Section 5 ("What is still running") is entirely out of date.
   - "Gaps" still says "No evaluation numbers exist yet" and "frozen typset not checked" (the
     latter is now checked complete).
   - Rewrite these sections, then regenerate `report.html`.
3. **The reproduction-gate wording** should give the exact numbers (section 3).
4. **H1b reading:**
   - Replace "at the H1b falsification level" in the README run record and the REPORT with
     "uninformative for H1b: the metric's held-out expert ceiling is about 0.25 (this audit)".
   - Report the 74 unseen pieces as the headline and the 7 paired pieces separately.
   - Recompute R²c with the R-06 centering (B2) and report both.
   - Nothing about H1b goes into STATUS.md or the plan from R-07.
5. **S-LR wording** (section 5). Correct "outside F's training family" in REPORT 4b.
6. **Commit the pt_E − pt_frozen script**, or add the option to the summariser.
7. **Add a per-transcriber table** to the R10 secondary results (section 8), labelled post hoc.
8. **REPORT line 36** reads "R10u (76 R-02 pieces ...)". R10u has 91 evaluated pieces, of which
   75 are unseen R-02 pieces in (a) and 74 in H1b.

## 10. Box-only checks (a session on the RTX 5080 box)

All commands run from `experiments/2026-09-28-R-07-symupe-finetune/job/` with the SyMuPe venv's
python. The two scripts (B1, B2) are in the appendix. Both were tested here on the Mac dry-run
outputs; the toy numbers are not reported.

- **B1 (S-LR field dominance and baselines).** Run `python box_slr_audit.py --set P`, then the
  same with `V` and `A`.
  - It reports the per-variant AUC of S-LR and of its per-field parts (E − F on TimeShift,
    Velocity, TimeDuration), of −ℓ_F alone, and of a model-free rank combination of B-amount
    and B-smooth.
  - It also reports the S-LR margin (minimum real minus maximum variant, and the median paired
    gap).
  - Expected if R1 is carried by F: LR_D alone at 1.000 on every deadpan, and −ℓ_F alone
    passing R1.
- **B2 (H1b with the pre-registered R²c and the matched oracle).** Run
  `python box_h1b_audit.py --set R10u`, then `--set R10s`. It writes
  `outputs/results/<set>/h1b_audit.csv` and checks that the as-run captured share equals the
  committed `h1b.csv`. It adds:
  - R²c by the R-06 formula, and the model's log IOI offset;
  - each arm's captured share and a 16-held-out-expert oracle in the *same* reduced subspace,
    with their ratio (5 draws).
- **B3 (P/V/A items identical to the Mac's R-06 items).** Run the digest script (appendix) from
  the repo root on the box. On the Mac it prints:
  - items: P 7951 `789c7a5da54f463f`, V 704 `88c33f07919b5e60`, A 640 `f62963a7d6d1fc42`;
  - gen_items: P 86 `39d9b376a0435eca`, V 4 `f7e82e10000187ad`, A 16 `c0160645c338e7f6`.

  If P differs, diff the items one by one on `perf_dur_sec`. That would explain the articulation
  shift behind the gate miss. Optional: `python symupe_eval.py gen --items
  outputs/eval_sets/P/gen_items --out <scratch>/frozen_cpu_P --device cpu --k 8`, then summarise
  against R-06, to separate CPU from GPU sampling.
- **B4 (outputs integrity and the pt_E retry).**
  - For each arm × set, count `outputs/eval/<arm>/<set>/{score,gen}/*.npz` against the manifest.
  - Load every npz (`np.load` and touch every array).
  - List `error` entries in each `_log_*.json`.
  - For pt_E R10u: confirm 91 gen files, all with modification times in the retry window
    (2026-10-05 04:22-08:29 UTC), `_log_gen.json` "ckpt" = `outputs/pt_E/ckpt/best.pt`, and the
    `best.pt` timestamp (2026-10-01, step 8,000) earlier than every pt_E eval output.

## 11. Proposed text for other files (the lead edits them)

**EXPERIMENTS.md, R-07 row (verdict cell):**

```
Confirmed with caveats (eval-auditor 2026-10-05). (a) E - frozen on P harms, -0.051
[-0.072, -0.029] (t over 3 works [-0.178, 0.076]); V and A also harm; R-10 uses frozen SyMuPe.
E improves only on R10u Aria-AMT transcriptions (post hoc). Reproduction gate missed (0.3987 vs
0.3882). (c) S-LR passes the deadpan/jitter battery, but R1 is matched by B-amount and S-LR is
at chance against halved expression (0.491): not a validated typicality score. S-DEV flatness
detector only; S-TYP fails. (b) H1b preview uninformative: captured share 0.10-0.12 is about
half a 16-expert held-out oracle (about 0.25), so the 0.50 bar is unreachable for real experts;
log IOI R2c formula deviates from R-06.
```

**Proposed lessons for `.claude/rules/experiments.md`:**
- Any subspace or "captured share" statistic needs an expert oracle before thresholds are set:
  replace the model's K samples with K held-out real performances, and estimate the subspace
  without them. In R-07 that oracle was about 0.25, so a 0.50 bar was unreachable.
- When a later experiment cites an earlier statistic "as in R-0x", diff the formula. R-07's
  log IOI R²c dropped R-06's centering of the predicted curve.
- A likelihood ratio against a flat model passes deadpan batteries nearly by construction when
  every deadpan has one field at the flat model's mode. Test it on non-flat wrong expression, and
  against a combined trivial baseline, before using it.
- Report a model-change effect per data source or transcriber when training and test share a
  dominant source.

## 12. Lead decisions

1. **R-10 model:** frozen SyMuPe, per the rule (confirmed).
   - Whether Pianist Transformer (pt_E) gets a role in R-10 is not covered by any R-07 rule.
   - pt_E is best on R10u, (a) +0.052 against frozen SyMuPe, but worse on V, A and R10s.
   - Using it needs a new pre-registered rule.
2. **H1b operationalisation** before R-10 is pre-registered (section 4). Make it a DECISIONS
   entry, and possibly a plan amendment to the H1b row ("explains variance" against a stated
   oracle).
3. **S-LR use:** keep it unused until B1 and a non-flat battery are run (stricter than DECISIONS
   2026-09-28), or allow it with the scoped wording.
4. **The F-06 "too flat" flag:** B-amount (model-free) vs S-DEV.

## Appendix: audit scripts

Mac-side oracle (`oracle.py`, abbreviated). It rebuilds R10 items with `prep_data.select_pianocore` and
`_pianocore_piece` (roles R10u / R10s only, 10 workers, 108 s). Then, per piece, it builds V and
T exactly as `summarize_eval` does (majority score, first 3,000 notes, `_cap`, at least 16 notes,
onsets observed in at least half), checks `h1b_passage` k / var_shared against `h1b.csv`, and
replaces the model curves by 16 random experts (5 draws, `default_rng(1)`). The full scripts were
in the audit scratchpad. The box versions below contain the same oracle logic.

`box_h1b_audit.py` (B2):

```python
import argparse, sys
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent))
import summarize_eval as se
from pianolens.models.expression_data import load_item

def basis(V, T, k):
    Vf, Tf = se._fill(V), se._fill(T); Vf = Vf - Vf.mean(1, keepdims=True)
    sv, st = np.std(Vf - Vf.mean(0)), np.std(Tf - Tf.mean(0))
    J = np.hstack([(Vf - Vf.mean(0)) / sv, (Tf - Tf.mean(0)) / st])
    return J, np.linalg.svd(J, full_matrices=False)[2][:k], sv, st

def capture(J, Vk, Vs, Ts, sv, st):
    Ds = J @ Vk.T @ Vk
    Sv, St = se._fill(Vs), se._fill(Ts); Sv = Sv - Sv.mean(1, keepdims=True)
    M = np.hstack([(Sv - Sv.mean(0)) / sv, (St - St.mean(0)) / st])
    _, s, Wt = np.linalg.svd(M, full_matrices=False)
    Q = Wt[s > 1e-9 * s.max()].T
    return float(np.sum((Ds @ Q) ** 2) / np.sum(Ds ** 2))

def r2(m, p, centered):
    ok = np.isfinite(m) & np.isfinite(p); m, p = m[ok], p[ok]
    if centered:
        m, p = m - m.mean(), p - p.mean()
        return float(1 - np.sum((m - p) ** 2) / np.sum(m ** 2))
    return float(1 - np.sum((m - p) ** 2) / np.sum((m - m.mean()) ** 2))

ap = argparse.ArgumentParser()
ap.add_argument("--set", required=True); ap.add_argument("--out-root", default="outputs")
ap.add_argument("--arms", nargs="+", default=["frozen", "E", "pt_frozen", "pt_E"])
ap.add_argument("--min-renditions", type=int, default=20)
ap.add_argument("--n-hold", type=int, default=16); ap.add_argument("--min-ref", type=int, default=20)
ap.add_argument("--draws", type=int, default=5)
a = ap.parse_args()
root = Path(a.out_root); set_dir = root / "eval_sets" / a.set
man = pd.read_csv(set_dir / "manifest.csv"); real = man[man["kind"] == "real"]
H = pd.read_csv(root / "results" / a.set / "h1b.csv").set_index(["arm", "passage"])
rows = []
for passage, g in real.groupby("passage"):
    if len(g) < a.min_renditions:
        continue
    fname = se._slug(passage) + ".npz"
    gi = load_item(set_dir / "gen_items" / fname)
    idx = pd.Index(np.unique(np.round(gi["score_onset_q"], 6)))
    V, T = [], []
    for st_ in g["stem"]:
        c = se.feats(load_item(set_dir / "items" / f"{st_}__real.npz")).groupby("onset_q")[
            ["velocity", "log_ioi"]].mean().reindex(idx)
        V.append(c["velocity"].to_numpy()); T.append(c["log_ioi"].to_numpy())
    V, T = np.array(V), np.array(T)
    keep = (np.isfinite(V).mean(0) >= 0.5) & (np.isfinite(T).mean(0) >= 0.5)
    V, T = V[:, keep], T[:, keep]
    for arm in a.arms:
        pr = se.gen_prediction(set_dir, root / "eval" / arm / a.set, fname)
        if pr is None:
            continue
        curves = [c.reindex(idx)[keep] for c in pr["curves"]]
        ref = se.h1b_passage(V, T, curves)
        Sv = np.array([c["velocity"].to_numpy() for c in curves])
        St = np.array([c["log_ioi"].to_numpy() for c in curves])
        Vf = se._fill(V); Vf = Vf - Vf.mean(1, keepdims=True)
        Svf = se._fill(Sv); Svf = Svf - Svf.mean(1, keepdims=True)
        m_t, p_t = se._fill(T).mean(0), se._fill(St).mean(0)
        row = {"arm": arm, "passage": passage, "n": len(V), "k": ref["k"],
               "captured_as_run": ref.get("captured"),
               "captured_committed": H.loc[(arm, passage), "captured"] if (arm, passage) in H.index else np.nan,
               "r2c_vel_r07": ref["r2c_velocity"], "r2c_vel_r06": r2(Vf.mean(0), Svf.mean(0), True),
               "r2c_ioi_r07": ref["r2c_log_ioi"], "r2c_ioi_r06": r2(m_t, p_t, True),
               "ioi_offset": float(p_t.mean() - m_t.mean())}
        if ref["k"] > 0 and len(V) >= a.n_hold + a.min_ref:
            rng = np.random.default_rng(1); cm, ce = [], []
            for _ in range(a.draws):
                perm = rng.permutation(len(V)); hold, rest = perm[:a.n_hold], perm[a.n_hold:]
                J, Vk, sv, st = basis(V[rest], T[rest], ref["k"])
                cm.append(capture(J, Vk, Sv, St, sv, st))
                ce.append(capture(J, Vk, V[hold], T[hold], sv, st))
            row.update(cap_model_reduced=np.mean(cm), cap_oracle_reduced=np.mean(ce),
                       ratio=np.mean(cm) / np.mean(ce))
        rows.append(row)
R = pd.DataFrame(rows)
R.to_csv(root / "results" / a.set / "h1b_audit.csv", index=False)
print("as-run captured equals committed:",
      np.allclose(R.captured_as_run, R.captured_committed, equal_nan=True))
print(R.groupby("arm").median(numeric_only=True).round(3).to_string())
```

`box_slr_audit.py` (B1):

```python
import argparse
import numpy as np, pandas as pd

def auc(real, alt):
    j = pd.concat([real, alt], axis=1, keys=["r", "a"]).dropna()
    return float(((j.r > j.a) + 0.5 * (j.r == j.a)).mean()) if len(j) else np.nan

ap = argparse.ArgumentParser(); ap.add_argument("--set", required=True)
ap.add_argument("--root", default="outputs/results")
a = ap.parse_args()
S = pd.read_csv(f"{a.root}/{a.set}/scores.csv")
E = S[S.arm == "E"].set_index(["stem", "kind"]); F = S[S.arm == "F"].set_index(["stem", "kind"])
X = pd.DataFrame({"S-LR": E["S-LR"], "-lF_core": -F["S-RAW"],
                  "LR_T": E["ll_T"] - F["ll_T"], "LR_V": E["ll_V"] - F["ll_V"],
                  "LR_D": E["ll_D"] - F["ll_D"], "B-amount": E["B-amount"], "B-smooth": E["B-smooth"]})
X["B-combo"] = (X["B-amount"].rank(pct=True) + X["B-smooth"].rank(pct=True)) / 2
r = X.xs("real", level="kind")
out = []
for v in sorted(set(X.index.get_level_values("kind")) - {"real", "ext_deadpan"}):
    alt = X.xs(v, level="kind")
    row = {"variant": v, **{c: auc(r[c], alt[c]) for c in X.columns}}
    d = pd.concat([r["S-LR"], alt["S-LR"]], axis=1, keys=["r", "a"]).dropna()
    row["SLR_min_real_minus_max_alt"] = float(d.r.min() - d.a.max())
    row["SLR_median_gap"] = float((d.r - d.a).median())
    out.append(row)
print(pd.DataFrame(out).round(3).to_string(index=False))
print("S-LR quantiles, real:", np.round(r["S-LR"].quantile([.01, .5, .99]).values, 3))
```

Item digest (B3), run from the repo root:

```python
import hashlib
from pathlib import Path
import numpy as np
ART = Path("experiments/2026-09-27-R-06-expression-model-h2h/artifacts")
for kind in ("items", "gen_items"):
    for s in ("P", "V", "A"):
        h, n = hashlib.sha256(), 0
        for p in sorted((ART / kind / s).glob("*.npz")):
            z = np.load(p, allow_pickle=True); h.update(p.name.encode())
            for k in sorted(z.files):
                a = np.asarray(z[k])
                if a.dtype.kind in "fc":
                    a = np.round(a.astype(np.float64), 9)
                h.update(k.encode()); h.update(str(a.shape).encode())
                h.update(a.tobytes() if a.dtype != object else repr(a.tolist()).encode())
            n += 1
        print(kind, s, n, h.hexdigest()[:16])
```

## Lead addendum (2026-10-05, after the R-10 dry run)

SyMuPe EncDec-base ignores `perform_score(lm_top_p=...)` and samples at top-p 0.95 by default
(R-10 `job/symupe_gen.py`; DECISIONS 2026-10-05). All SyMuPe samples in R-07 were drawn at 0.95,
including the S-TYP reference samples registered at 1.0. S-TYP failed, so the reading stands; the
README run record needs a correction line, and section 4's "a diversity metric should use top-p
1.0" also applies to every SyMuPe arm here (the captured shares were measured at 0.95).

R10u content check (R-10 pre-run review, 2026-10-05): 5 of the 74 "unseen" R10u pieces contain
PERiScoPe-paired content inside whole-set piece ids. Without them the frozen dev medians are R²c
velocity 0.330 and log IOI 0.142 (0.328 / 0.127 with them). The README and REPORT should say
"74 pieces, 5 with paired content" wherever "unseen" is used.
