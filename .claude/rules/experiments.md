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
