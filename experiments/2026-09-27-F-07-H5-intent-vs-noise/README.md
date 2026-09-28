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

## Run record

- Pre-registration above: SHA-256 `b1f57ae2dc038c25624f8d816ec8910375a3db8c447c2316190dd372c91a40ae`
  (header unchanged since registration).
- Code: git HEAD `e4becf88`, F-07 files uncommitted. SHA-256 prefixes: `takes.py` 3f0692a8975865dc,
  `shaping.py` 39b6afbc5d980b62 (includes F-05d), `run.py` 9e67ab1d9b93e108, `asap.py`
  bafab0d517dec9e8, `analyze.py` 32d30056cba365a9. Seeds: 0 (take cap, bootstrap).
- Data: PianoCoRe v1.0 (Zenodo 19186016) tier A, D-07 cache for coverage counts; ASAP commit per
  `DATASETS.md`.
- Commands actually run (worker count lowered because R-09 was using the machine; BLAS threads
  pinned to 1 after the first attempt oversubscribed the CPU):
  `OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 MKL_NUM_THREADS=1 uv run python experiments/2026-09-27-F-07-H5-intent-vs-noise/run.py --workers 6`
  (963 s for 1,728 groups), `uv run python .../asap.py` (about 50 min, 48 groups, sequential),
  `uv run python .../analyze.py` (output in `artifacts/analysis.txt`).
- Changes after registration, disclosed:
  1. **F-05d minimum-length rule.** While this ran, F-05d changed `n_blocks` in `shaping.py` to
     `ceil(distinct written bars / 4)` and made R² undefined below 3 blocks or 12 written bars.
     `take_structure` now uses the same rule (`n_written_bars`, `undefined_reason`) and the
     PianoCoRe run was repeated with it. **No H5 number changed**: all 1,400 k >= 2 timing rows
     have at least 12 written bars (10 are excluded by the pre-registered 100-observation
     minimum, as before); `artifacts/analysis_v1_rangeblocks.txt` (old rule) and
     `artifacts/analysis.txt` are identical apart from the ASAP line (which was still running
     during the first analysis). All 40 ASAP groups used have 21 or more written bars.
  2. The ASAP summary line (means with a performer bootstrap) was added to `analyze.py` after the
     per-group ASAP rows were seen. It is descriptive and does not enter the verdict.

## Results

### Sample and de-duplication

| Step | Groups | Takes |
|---|---|---|
| (piece, named pianist) with >= 2 tier A takes | 1,897 | |
| after take coverage >= 0.80 | 1,728 | 4,690 |
| k >= 2 after de-duplication at r > 0.98 (primary) | 1,400 (328 groups were all one recording) | 3,562 |
| eligible (>= 100 timing observations, >= 12 written bars) | 1,390 (91 pianists, 415 pieces) | |
| k >= 2 at r > 0.95 / 0.90 | 1,210 / 887 | 2,993 / 2,107 |

Takes per eligible group (primary): k = 2: 923, 3: 280, 4: 116, 5: 36, 6: 35.

Duplicates are common: over the 5,472 within-group take pairs, 168 have timing r > 0.98 and 752
more have smooth-tempo r > 0.98 only. There is no clean gap in the r distribution. The ASAP
Disklavier check shows the tempo part of the rule over-merges. 8 of its 48 same-name groups have
tempo r 0.981-0.990 but timing r 0.53-0.84, which look like distinct performances: no ASAP pair
exceeds timing r 0.92. The rule is therefore conservative (it drops real takes), and the
stricter thresholds move the result by at most 0.01.

### Primary: timing (`dev_beats`), pairwise half-sum vs half-difference

Out-of-fold R² on the score basis. Unweighted mean over groups, 95% cluster bootstrap CI
(2,000 replicates). The trivial baseline (predict the mean) is R² = 0.

| Dedup r | Groups | R²(sum): consistent | R²(diff): inconsistent | delta | Share of groups with delta > 0 |
|---|---|---|---|---|---|
| 0.98 (primary; pianist bootstrap) | 1,390 | 0.123 [0.114, 0.132] | 0.005 [0.003, 0.008] | **0.118 [0.110, 0.126]** | 93% |
| 0.98 (piece bootstrap) | 1,390 | 0.123 [0.112, 0.135] | 0.005 [0.003, 0.007] | 0.118 [0.107, 0.130] | |
| 0.98, pianist-level mean (each pianist weighs once) | 91 pianists | | | 0.122 [0.106, 0.139] | 88 of 91 pianists |
| 0.98, k = 2 groups only | 923 | 0.126 [0.115, 0.137] | 0.005 [0.002, 0.009] | 0.120 [0.111, 0.129] | |
| 0.95 | 1,204 | 0.129 [0.119, 0.138] | 0.006 [0.003, 0.010] | 0.123 [0.114, 0.131] | 94% |
| 0.90 | 884 | 0.136 [0.125, 0.146] | 0.008 [0.005, 0.012] | 0.128 [0.118, 0.136] | 94% |

Context: the single-take reliability of timing is ICC(3,1) 0.60 [0.58, 0.63]. About 60% of a
take's residual timing variance repeats in the other take. Structure explains about a fifth of
that repeatable part (0.12 / 0.60).

### Secondary channels (dedup 0.98, pianist bootstrap)

| Channel | R²(sum) | R²(diff) | delta | ICC(3,1) |
|---|---|---|---|---|
| articulation (`art_log_ratio`) | 0.242 [0.231, 0.255] | 0.013 [0.008, 0.019] | 0.229 [0.219, 0.241] | 0.65 |
| smooth tempo (`tempo_log_ratio`) | 0.082 [0.072, 0.094] | -0.020 [-0.029, -0.010] | 0.103 [0.092, 0.114] | 0.82 |
| velocity (`vel_midi`, transcribed: low confidence, D-10) | 0.280 [0.263, 0.300] | 0.021 [0.014, 0.028] | 0.259 [0.244, 0.277] | 0.81 |

Unbalanced view (k-take mean vs per-take deviation): timing 0.128 vs 0.005, articulation 0.249
vs 0.013, tempo 0.084 vs -0.020, velocity 0.284 vs 0.021. It gives the same picture.

### Disklavier check (ASAP, descriptive)

40 same-name groups keep k = 2 after de-duplication (28 heuristic performer ids; competition
performances from different rounds or years). Means with a performer bootstrap:

| Channel | R²(sum) | R²(diff) | delta | Groups with delta > 0 |
|---|---|---|---|---|
| timing | 0.078 [0.053, 0.107] | 0.003 [-0.002, 0.010] | 0.075 [0.053, 0.098] | 35 of 40 |
| articulation | 0.313 [0.261, 0.362] | 0.024 [0.010, 0.041] | 0.289 [0.237, 0.336] | 40 of 40 |
| smooth tempo | 0.155 [0.099, 0.215] | -0.023 [-0.047, 0.004] | 0.178 [0.122, 0.237] | 35 of 40 |
| velocity | 0.286 [0.253, 0.316] | 0.010 [-0.004, 0.025] | 0.276 [0.247, 0.303] | 39 of 40 |

Per-group rows: `artifacts/asap_rows.csv`. Per-pianist PianoCoRe table:
`artifacts/per_pianist_timing.csv`.

## Verdict (Provisional)

**H5 supported for timing, by the pre-registered reading.** The whole CI of mean delta,
0.118 [0.110, 0.126], lies above 0. The whole CI of R²(diff), [0.003, 0.008], lies below the
0.02 qualifier, so the "partly supported" qualifier does not apply. Score structure explains
the part of timing a pianist repeats across recordings (R² about 0.12). It explains almost none
of the part that changes between recordings (R² about 0.005).

The result holds under every sensitivity check: de-duplication at 0.95 and 0.90, the piece
bootstrap, the pianist-level mean, and k = 2 only. It also holds in all three secondary channels,
and in the small Disklavier set, where the timing delta is smaller (0.075). Articulation and
velocity R²(diff) CIs lie above 0 but below 0.03. Only a trace of the take-to-take change is
structured.

## Threats to validity

- **Shared transcription bias.** Every PianoCoRe take is transcribed, usually by the same system
  per source. A systematic transcriber error that depends on score context (chords, register,
  offsets of bass notes) is common to both takes. It therefore lands in the half-sum and inflates
  R²(sum). This matters most for articulation (offsets) and velocity. The Disklavier check has
  no transcription and still shows the effect in every channel. For timing it is smaller (0.075
  vs 0.118), which is consistent with part of the PianoCoRe timing delta being shared transcriber
  bias. It is also consistent with different repertoire and players; the check cannot separate
  the two.
- **"Take-specific" is not only motor noise.** Recordings are often years apart (studio vs live).
  The half-difference contains changes of interpretation as well as noise. R²(diff) near 0 says
  those changes are not organized by the score features used here. It does not say they are
  random: they may follow structure that the basis misses, such as phrase-level shaping without
  annotated phrases (F-05b: the proxy phrases are weak).
- **Duplicates.** The de-duplication rule is a heuristic, and no metadata identifies re-issues.
  Surviving duplicates would push both R²(sum) up and R²(diff) toward noise. That would inflate
  delta, but the stricter thresholds do not reduce it (0.118 -> 0.128).
- **Score basis.** PianoCoRe scores are MIDI: no markings, and phrase features come from the
  proxy. R² values are lower bounds on what structure explains. They are not comparable with
  MusicXML-based F-05 numbers.
- **Heuristic performer ids** (ASAP name codes; PianoCoRe `performer` strings, e.g. "Scott
  Joplin" is a piano-roll attribution with ICC 0.19).
- **Rach3 not used.** Its Hanon practice files are long sessions over the whole book. Using them
  needs a session-to-take segmentation and alignment step first (a candidate BACKLOG item). The
  repeated-practice setting it would test (the same day, the same player, a non-expert) is the
  one closest to Henry's own use (O-01). This experiment says nothing about it.
