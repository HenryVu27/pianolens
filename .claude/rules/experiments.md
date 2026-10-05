---
paths:
  - "experiments/**"
  - "src/pianolens/models/**"
  - "src/pianolens/eval/**"
  - "configs/**"
  - "EXPERIMENTS.md"
---

# Experiment rules

- Use the `run-experiment` skill. Write the hypothesis and the falsification criterion before
  running anything.
- **Leave-piece-out is mandatory** for any quality or preference claim. Leave-performer-out is
  reported separately.
- Every results table has:
  - a trivial baseline (predict the train mean; distance to the corpus mean),
  - the model,
  - rater parity when per-rater labels exist,
  - bootstrap 95% CIs.
- Set seeds and record them. Record the git commit (or "uncommitted" plus a diff hash), the data
  versions from `DATASETS.md`, and the exact command.
- **No tuning on test folds.** Use nested CV, or a fixed validation piece set.
- **Audio results:** state the renderer or recording source. Rendered-audio results do not
  transfer to real recordings until tested (H8).
- The verdict starts as **Provisional**. It becomes **Confirmed** only after `eval-auditor` signs
  it off. Report negative results as plainly as positive ones.

## factor-analyzer 0.5.1 traps (from the R-01 audit, 2026-09-27)

- After an oblique rotation it re-sorts the loadings but **not** `phi_` (the factor correlations).
  Re-order `phi_` to match the loadings before reporting.
- `get_communalities()` sums squared pattern loadings. Under an oblique rotation that is not the
  communality. Compute it as `diag(L @ Phi @ L.T)`.
- Its scikit-learn version check fails on sklearn 1.9, which needs a keyword shim. The shim does not
  change results (verified against sklearn 1.5.2).
- Report a factor count as a range across criteria (PCA-PA, FA-PA, MAP), and show how sensitive it
  is to item merges, not a single number.

## Lessons from the R-01 to R-04 audits (2026-09-27)

- **Ceilings for a panel-mean target.** Split-half (half-panel vs half-panel) agreement is *not*
  the ceiling. Extrapolate with Spearman-Brown to the full panel, and report both the single-rater
  level and the full-panel ceiling.
- **Report per-group deltas, not only pooled ones.** With few held-out groups (e.g. 4 PercePiano
  works), a pooled "matches" can hide a significant loss on one group. Always add the per-group
  paired table and the unweighted mean over groups.
- **Margin sensitivity.** For any non-inferiority claim, report the tightest margins at which it
  still holds.
- **Anything added after results are seen** (features, variants, filters) is disclosed in the run
  record, and the claim is refit without it.
- **Keep the pre-registration hash-checkable.** Don't edit the pre-registered header. Record the
  audited status in the Verdict section.
- **Surrogate nulls.** Any claim that a real count beats a surrogate also reports a parallel-analysis
  count (eigenvalues above the 95th percentile of surrogates) against a surrogate that *keeps the
  per-position variance profile*. Phase randomization alone is a weak null (R-02 audit).

## Lessons from the R-06 audit (2026-09-28)

- **Apply the pre-registered reading word for word.** Check where the whole CI lies. An AUC whose
  CI is entirely below 0.5 is a "fail", not "inconclusive".
- **Test every likelihood or typicality score against deadpan variants**, not only an exact
  deadpan: velocity offset from the conditioning, a different tempo, deadpan plus small noise,
  and half-deadpans (flat timing with human velocity, and the reverse). R-06: a per-note
  likelihood prefers all of them to the human performance.
- **Bootstrap PercePiano by performer as well as by passage.** D960 has overlapping 8- and 16-bar
  segmentations, and the same performers play every passage of a work.

## Lessons from the R-08a audit (2026-09-28)

- **Six or fewer groups:** report a t-interval next to the percentile bootstrap. The bootstrap is
  optimistic with few groups.
- **LLM annotation of famous repertoire requires a memorisation control:** disguised or transposed
  renderings, or unfamiliar repertoire, plus run-to-run variance. Record `recognised_piece`, and
  break results down by it.
- **Blind annotators never receive a repo path.** Their inputs are copied outside the repo, and
  their transcripts are audited for file access. Save annotations into the experiment folder
  immediately; scratchpads do not persist.

## Lessons from the R-09 audit (2026-09-28)

- **Check that every verdict branch can be reached.** Before running, simulate or reason out the
  chance of each outcome at a true effect of 0. If the smallest effect of interest is smaller than
  the expected CI half-width, "falsified" is effectively unreachable, and "inconclusive" is the
  expected result. Say so in the pre-registration.
- **Contrasts that also drop levels:** when a pooled-vs-matched comparison also removes part of the
  range (for example, the top skill levels), also report the pooled model restricted to the levels
  in the matched sample.
- **The bootstrap unit must be a real cluster.** Check that the cluster id groups more than one row
  (MAJEPPA `recording_id` is one video per row).

## Lessons from the R-08b audit (2026-09-28)

- **Compare recognised with unrecognised runs within an item, never pooled across items.**
  Whether the model recognises a piece is not randomised, and it tracks the item. In R-08b the
  easiest movement was never named, so the pooled means made named runs look worse. Within each
  movement, named runs scored higher.
- **Self-reported recognition is a lower bound.** Subagent thinking is not in the transcripts. A
  `null` string can sit next to a half-recognition in the hand-back text. A disguise control
  rules out explicit recall, not structural familiarity. Only unfamiliar repertoire rules out
  both.

## Lesson from the F-07 audit (2026-09-28)

- **Any "shared part vs difference part" contrast needs a cross-unit positive control.** For
  example, compare same-pianist pairs with different-pianist pairs. Otherwise "the shared part is
  structured" is nearly guaranteed whenever single-unit structure exists, and says nothing specific
  to the unit.

## Lessons from the R-08c audit (2026-09-28)

- **Unfamiliar is not unseen.** Public label sets (DCML and others) released before the model's
  training cutoff may have been seen. Unfamiliar repertoire rules out recall that depends on
  recognising the piece. It does not rule out exposure to the labels. Only ground truth made
  after the cutoff excludes that. Check whether the errors follow the label standard's
  conventions (a model recalling the labels would copy the standard's phrase level).
- **A point-estimate GO near the bar with n = 5:** report leave-one-group-out means, the
  worst-run variant, and the one-sided p against the bar next to the t-interval.

## Lessons from the R-08d audit (2026-09-28)

- **Sparse ground truth and level mismatch.** When a movement has few labelled boundaries (about 5
  or fewer), F1 is driven by the phrase level, and a tolerance sensitivity cannot detect it. For
  each low-scoring movement, list every miss and extra with its distance to the nearest true
  boundary, and separate "finer subdivisions" (extras) from "placement misses" (recall loss).
  Seen in R-08c Q3 and R-08d R5.
- **A level-match check is one-sided.** Predicted/true ratios near 1 with high P and R are what a
  label recaller would show and also what a good annotator shows, so they say nothing about
  exposure. Only a level mismatch argues against recall.
- **Check the reachability assumption after the run.** If the observed between-group SD is much
  larger than the one assumed in the pre-registration, say so in the results: the interval is
  then uninformative, and only the point-estimate rule decided.

## Lesson from the F-05e audit (2026-09-28)

- **Any boundary-based measure gets two controls:** random boundaries at the same density, and
  the reference boundaries with each segment halved. The first shows density alone does not inflate
  the measure. The second shows how the measure treats correct but finer segmentation. Report the
  predicted-to-reference boundary-count ratio next to the measure.

## Lessons from the R-05 audit (2026-09-28)

- **Shortcut size needs an explicit-label ceiling.** When the nuisance variable (context) can be
  decoded almost perfectly, compare the confounded model with a stacked model: the matched
  model's score plus the one-hot nuisance label, fitted on inner out-of-fold scores. Do not just
  append the label to a high-dimensional embedding under the same L2 penalty, which shrinks it.
  If the confounded model is near that ceiling, the size reflects the confound strength, not the
  encoder. Claim direction and mechanism only.
- **When repertoire tracks the label, also report a within-piece AUC** (pairs from the same piece
  only). Repertoire difficulty lifts a matched baseline towards the ceiling, so a pooled delta can
  understate the effect. In R-05 it was +0.073 pooled and +0.122 within piece.

## Lesson from the BL-16 audit (2026-09-28)

- **A cross-unit control must match the within-unit pair on the nuisance axes.** Examples are
  time separation (same sitting vs other days), tempo, and noise level. Add a same-unit pair at
  the cross pair's separation. In BL-16 a same-pianist pair from another day was nearly as
  structured as a cross-pianist pair (0.011 [-0.015, 0.034]).
- **R² gaps between pairs scale with each pair's noise.** Report the variance ratio or the
  explained variance next to them.

## Lessons from the BL-17 audit (2026-09-29)

- **Before explaining why a replication came out lower, test whether it is lower.** Report the
  difference between the two studies with its interval (Welch). In BL-17 vs R-08d it was +0.103
  [-0.189, +0.394], so sampling noise alone was enough. Also compare how each study weights its
  groups (one per corpus vs pool-proportional).
- **A wider tolerance needs its own controls.** Report grid, proxy and random-at-same-count
  scores at that tolerance too. At ±1 bar a 4-bar grid rose from 0.171 to 0.405, more than the
  annotator gained.
- **Split misses by distance.** Before calling misses "placement convention", count how many
  fall within the wider window. In BL-17 it was only 21-26 of 88 per run.
- **Duplicated agent launches:** check each launch's result for refusals (concurrency limit)
  before you accept "no rerun".

## Lessons from the BL-19 / BL-20 audits (2026-09-29)

- **An oracle control that is zero by construction is not evidence.** Before you cite "0 with the
  ground truth", check whether the oracle path can produce the outcome at all. Attribute a deficit
  from the *other* outcome shares in both modes, and apply the pre-registered threshold to the
  oracle mode too.
- **An injection's "detected" must be measured against a clean unit.** When a unit (bar) can
  already carry errors, report detection and "silent" shares conditional on the unit being
  error-free before the injection.
- **An absolute threshold needs the baseline cell checked.** If the sparse or easy cell also
  breaches it, the criterion is not specific to the factor under test.
- **Proxy-only measurements get a recall check against any labels the data already carries**
  (for example engraver hand marks), and "pass" is worded as a pass on the proxy.
- **Per-unit shares need a minimum denominator.** Units with 0 events must be treated the same
  way in the median and in the tail share.

## Lessons from the BL-18 audit

- A calibration to a nominal rate needs a **two-sided** tolerance and a **detection floor**. One-sided "at most X%" criteria reward rules that make the tier unreachable.
- Before selecting a rule on dev data, separate out cases no candidate can change (for example runs of fully missed bars); otherwise the selection overcorrects everything else to compensate.
- A per-family limit can measure the corpus, not the family: check whether the family is confounded with source (Aria-AMT = Aria-MIDI YouTube segments; Transkun V2 = PERiScoPe).

## Lessons from the BL-21 / BL-22 audits (2026-09-29)

- **A ratio-to-null threshold has a ceiling of 1/q.** When the null hit rate q is high (wide
  windows), "at least 1.5x the null" can be unreachable even for a positive control. BL-22's 2 s
  window had 1/q = 1.37-1.47 on its rendered controls. Before running, compute 1/q for the controls.
  Report the implied share f = (h - q) / (1 - q) with an interval, not only the ratio verdict.
- **Before explaining unexplained events acoustically, check them for sequence structure.** Look
  at step sizes between consecutive events against a pitch-permutation null, regular timing, and
  n-grams that recur across recordings. BL-22's "fixed-pitch phantom extras" were a recurring
  C-major melody, a second sound source, which no per-note test had shown.
- **Near-threshold effects on sensor ground truth:** check whether the events near the cut-off are
  physical artefacts of the sensor (see `rules/audio.md` on Disklavier echoes), and report the
  result with and without them.

## Lessons from the BL-23 audit (2026-09-29)

- **A correction step gets a precision check on the real pipeline path.** Score every change it
  makes against ground truth on real data, not only its net effect on a synthetic metric. Report
  repairs vs breaks. Its drop under an oracle alignment is its false-change rate. BL-23 post-pass:
  230 repairs, 35 breaks of 291 swaps on clean expert copies.
- **A no-harm denominator can be one piece.** Break a "genuine cases" check down by piece and by
  recurrence across performers before explaining it. Flags that recur at the same bar across
  performers are systematic (notation or realisation), not hidden slips. BL-23 N3: 45% of the
  denominator and 66% of the flags were unexpanded tremolo abbreviations in one Schubert score.
- **A check downstream of a component can be zero by construction.** Before reporting "0 fired",
  read what the upstream component can emit (BL-23: parangonar only makes different-pitch
  matches where the legacy rule already allows them).

## Lessons from the BL-18b audit (2026-09-29)

- **A detection floor on injected mistakes can measure the checker, not the rule.** Before
  registering it, compute what each candidate rule gives on injected bars where the checker
  sees the whole injection. If that is fixed by construction (BL-18b: 100% for every margin-0
  rule, because experts had at most 1 wrong note and the global limit is 2), the unconditional
  floor measures the checker. Register a rule-relative criterion (candidate vs baseline on the
  same bars) and report the end-to-end share as a measurement.
- **Check the premise of a pre-registered fallback action in the same run.** If the fallback
  fails the same criteria or worse, do not apply the action mechanically. Keep the verdict as
  registered, and record the deviation from the action, with numbers, in DECISIONS.
- **Start / end statistics for runs need merged fragments and an edge tolerance.** A bar just
  under the threshold splits a run, and the last bars of a cut recording are often still
  partly found. BL-18b: 0 of 19 runs at the start, 3 at the end as runs; merged, the gap was the
  ending in 8 of 10 targets.

## Lessons from the R-07 audit (2026-10-05)

- **A subspace or "captured share" statistic needs an expert oracle before thresholds are set.**
  Replace the model's K samples with K held-out real performances, estimating the subspace
  without them. In R-07 that oracle was about 0.25, so the 0.50 bar was unreachable.
- **When a statistic is cited "as in R-0x", diff the formula.** R-07's log IOI R²c dropped R-06's
  centering of the predicted curve.
- **A likelihood ratio against a flat model passes deadpan batteries nearly by construction** when
  every deadpan has one field at the flat model's mode. Test it on non-flat wrong expression and
  against a combined trivial baseline before using it.
- **Report a model-change effect per data source or transcriber** when training and test share a
  dominant source (R-07: E's gain sat entirely in Aria-AMT, 77% of its training data).

## Lesson from the R-10 dry run (2026-10-05)

- **Check that a sampling parameter reaches the sampler.** SyMuPe EncDec-base ignores `perform_score(lm_top_p=...)` and samples at top-p 0.95 (it reads `top_p`), so every R-06 / R-07 SyMuPe sample was top-p 0.95, including R-07 S-TYP "top-p 1.0" references. When a setting matters to a claim, generate two settings on one item and confirm the samples differ.


## Lessons from the R-10 pre-run review (2026-10-05)

- **"Unseen" needs a content check, not only ids and titles.** Whole-set piece ids (for example
  a suite or a pair of Arabesques without a movement) get their own R-07 work key, so work-mate
  and catalogue-alias rules miss paired movements inside them. Before calling pieces unseen,
  match score content: 12-onset pitch-set n-grams against every held score (R-10: 3 hits at most
  for unrelated pieces, 114 or more for real overlap). The R-10 review flagged Debussy 2
  Arabesques, the whole Ravel Tombeau and a Bartók dance this way. R-07's R10u "unseen" set had 5 such pieces.
- **De-duplicate performers before any held-out expert oracle.** PianoCoRe `is_duplicate`
  misses cross-corpus copies (the same recording in ATEPP and PERiScoPe) and re-uploads. A copy
  in the held-out group and its twin in the reference inflate the oracle (R-10 captured share
  0.389 -> 0.256 on one piece). Flag within-piece pairs whose deviations from the consensus
  correlate above 0.9.
- **Report R²c with its amplitude ratio.** For centered curves R²c = 2rb - b², with b = sd(pred) /
  sd(target). A negative R²c with a positive r is amplitude miscalibration, not wrong shape.
