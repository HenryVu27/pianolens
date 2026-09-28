# Repeated takes: is the repeatable part of timing the score-driven part?
Ticket: F-07    Hypothesis: H5    Status: Provisional

Pre-registered 2026-09-27, after `pianolens.features.takes` passed its synthetic tests and after
counting candidate groups in the PianoCoRe metadata (1,897 (piece, named performer) groups with
at least two tier A takes; 102 pianists, 524 pieces), but before any take was loaded, any
duplicate check was run, or any R² was computed on real data. Sections below "Results" are added
afterwards.

## Question

When the same pianist plays the same piece more than once, split each expressive curve into the
part that repeats across takes and the part that changes. Does score structure explain the
repeatable part more than the part that changes? (Plan H5: "the between-take-consistent part of
timing correlates with score structure; the inconsistent part does not".)

## Falsified if

Plan H5 row: falsified if "consistent and inconsistent parts are equally explained by score
features". Refined here (fixed before results):

- Unit: a group = (piece, pianist) with k >= 2 distinct takes after QC and de-duplication.
- Per group and channel, for every pair of takes (j, l): half-sum `s = (y_j + y_l) / 2` (the
  consistent part of the pair) and half-difference `d = (y_j - y_l) / 2` (the inconsistent part),
  each take centered on its own mean first. For exchangeable takes `s` and `d` carry the same
  noise variance, so only structure can make their R² differ. (The k-take mean against per-take
  deviations is not balanced for k > 2, and a pooled regression of deviations on shared score
  features is 0 by construction; see `takes.py`.)
- R² = F-05 structural coherence: out-of-fold R² of a ridge regression on the score basis (all
  groups except `position`; the PianoCoRe scores are MIDI, so marking groups are empty), folds
  = 4-written-bar blocks, 1-bar buffer, nested penalty (`ShapingConfig` defaults).
- Group statistic: `delta = mean over pairs of (R²(s) - R²(d))`.
- Primary: **timing** channel (`dev_beats`, F-03 residual per score position). Summary = the
  unweighted mean of `delta` over groups, with a 95% cluster bootstrap CI resampling **pianists**
  (2,000 replicates, seed 0).
- Reading (applied word for word):
  - **Supported** if the whole CI of mean `delta` (timing) is above 0.
  - **Falsified** if the whole CI is below 0, or the whole CI lies inside [-0.02, +0.02]
    (equally explained).
  - **Inconclusive** otherwise.
  - Qualifier on the second half of H5 ("the inconsistent part does not"): if the whole CI of the
    mean `R²(d)` (timing) lies above 0.02, the verdict is reported as "supported for the
    consistent part; the inconsistent part is also score-structured" (partly supported).
- Secondary channels, same statistics, not deciding the verdict: articulation
  (`art_log_ratio`), smooth tempo (`tempo_log_ratio`), velocity (`vel_midi`; transcribed MIDI,
  low confidence per D-10, reported last).

## Data

- PianoCoRe tier A (Zenodo 19186016 v1.0; `pianolens.data.pianocore.PianoCoRe`, refined score
  MIDI + refined alignments). Rows with a named performer (`performer` not empty); groups by
  (`piece_id`, `performer_id`). All rows are transcriptions (ATEPP, PERiScoPe / Transkun V2).
  Each group shares one refined score (checked: 1 `score_id` per group).
- Take QC: `n_match / n_score_notes >= 0.80` (interpolated notes are not matches); the load and
  the F-03 tempo model must succeed.
- **Duplicates.** ATEPP and PERiScoPe can hold the same recording twice (re-issues, the same
  track in both corpora, two uploads). Within a group, two takes whose timing curves
  (`dev_beats`) or smooth tempo curves correlate above **r = 0.98** on their common positions
  are the same recording: takes are linked, connected components collapse to one take (the one
  with most matched notes). Counts are reported. Sensitivity: thresholds 0.95 and 0.90.
- At most 6 takes per group after de-duplication (random, seed 0), so all pairs (at most 15).
- A group enters if it keeps k >= 2 takes, at least 100 complete timing observations and at
  least 3 written-bar blocks (12 written bars).
- Disklavier check (descriptive only): ASAP same-performer repeats (47 (piece, name-code) groups,
  many of which are the same competition performance filed twice: the de-duplication rule
  decides), aligned with `align_performance`.
- Not used: Vienna 4x22 (no repeated takes); Rach3 Hanon (practice sessions of the whole book
  with no alignment to the exercise score; splitting sessions into takes and aligning them is
  its own ticket, see Threats).

## Splits

No quality prediction is made, so there is no leave-piece-out split. Held-out evaluation is
within each performance: written-bar-block CV (a repeated passage never predicts itself).
Bootstrap: pianists (primary), pieces (secondary).

## Baselines

- Trivial baseline: predicting each curve's mean (R² = 0 by definition of out-of-fold R²).
- Context for the size of `R²(s)`: the take-consistency reliability (ICC(3,1) / Spearman-Brown
  for the pair mean, `takes.decompose_takes`) of each channel, reported per group; the repeatable
  share of a channel bounds how much of it anything could call intent.
- The k-take mean vs per-take deviation R² (`r2_consistent`, `r2_specific`) are reported as a
  secondary, unbalanced view.

## Method

`run.py`: per group, load takes with the PianoCoRe loader, one `score_basis` per group, F-03
`tempo_model` per take, `takes.decompose_takes` (all four channels), de-duplicate, cap, re-run
`decompose_takes` on the kept takes, `takes.take_structure` (pairs), save per-group rows.
`analyze.py`: QC, aggregation, bootstrap, sensitivity tables.

## Command

```
uv run python experiments/2026-09-27-F-07-H5-intent-vs-noise/run.py --workers 8
uv run python experiments/2026-09-27-F-07-H5-intent-vs-noise/analyze.py
```
