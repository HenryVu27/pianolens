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
  3. *[Added post-audit, 2026-09-28.]* **Smoke run.** At 04:09:01Z-04:09:26Z, after the header
     was registered (04:08:20Z), a smoke run (`run.py --limit 8`) printed real pair R² for 8
     groups. Nothing in the header changed afterwards. It was not disclosed in the first version
     of this record.

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
take's residual timing variance repeats in the other take. *[Corrected post-audit, 2026-09-28;
the first version said "about a fifth (0.12 / 0.60)", which mixes denominators.]* R²(sum) is a
share of half-sum variance, and half-sum variance is (ICC + (1 - ICC) / 2), about 0.8, of one
take's variance. So structure explains about 0.123 x 0.8 / 0.60, roughly 0.16, of the repeatable
part, and about 0.10 of one take's variance. Both are rough (ratios of group means).

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

### Cross-pianist positive control (eval-auditor, post-hoc, not pre-registered)

*[Added post-audit, 2026-09-28.]* For each of 411 pieces, one eligible group gives a same-pianist
pair (a1, a2). A random take b1 by another pianist on the same refined score gives a
cross-pianist pair (a1, b1) that shares take a1. Both pairs are scored with `take_structure`.
Timing, means with a 95% bootstrap over pieces (2,000 replicates, seed 0):

| Timing (411 pieces) | R²(sum) | R²(diff) | delta | mean pair r |
|---|---|---|---|---|
| Same pianist (a1, a2) | 0.132 [0.119, 0.144] | 0.011 [0.006, 0.016] | 0.121 [0.109, 0.132] | 0.59 |
| Different pianists (a1, b1) | 0.146 [0.132, 0.159] | 0.049 [0.040, 0.057] | 0.097 [0.085, 0.109] | 0.36 |
| Paired difference (different minus same) | +0.014 [0.007, 0.021] | **+0.038 [0.030, 0.046]** | | |

R²(diff), same vs different pianists, other channels: articulation 0.017 vs 0.037, smooth tempo
-0.026 vs -0.010, velocity 0.019 vs 0.036. Script and rows: `artifacts/audit/cross.py`,
`artifacts/audit/cross.jsonl`. Details in the Audit section, part 3.

Two takes by *different* pianists pass the pre-registered test too. The half-sum R² therefore
measures score-typical timing that any two performances of the piece share, not one pianist's
repeated intent. The informative contrast is R²(diff): a pianist's own take-to-take changes are
less structured (0.011) than the differences between two pianists (0.049).

## Verdict: Confirmed with caveats (eval-auditor, 2026-09-28)

*[Reworded post-audit, 2026-09-28, per DECISIONS 2026-09-28 "F-07 / H5 is Confirmed with caveats,
and reinterpreted". The first version was headed "Verdict (Provisional)" and read the
consistent part as what the pianist repeats.]*

**H5 passes its pre-registered test for timing.** The whole CI of mean delta, 0.118 [0.110,
0.126], lies above 0. The whole CI of R²(diff), [0.003, 0.008], lies below the 0.02 qualifier,
so the "partly supported" qualifier does not apply. The result reproduces exactly.

**The take-consistent part is not personal intent.** The cross-pianist control (post-hoc, see
Results) passes the same test: delta 0.097 [0.085, 0.109] for two different pianists, against
0.121 [0.109, 0.132] for the same pianist. The score-explained consistent part is timing that
any two performances of the piece share. Once single-take R² > 0, this test was nearly certain to
pass, so the pass says little about intent.

**What F-07 supports:** a pianist's own take-to-take variation is mostly unstructured by the
score basis. R²(diff) is 0.011 within a pianist against 0.049 between pianists (paired gap 0.038
[0.030, 0.046]). The take-specific part can therefore be read as noise for tier B, subject to
O-01 / BL-16 (same-day practice takes). Tier B/D must not read "take-consistent" as "intent" on
this evidence.

The pre-registered result holds under every sensitivity check: de-duplication at 0.95 and 0.90,
the piece bootstrap, the pianist-level mean, and k = 2 only. It also holds in all three secondary
channels, and in the small Disklavier set, where the timing delta is smaller (0.075).
Articulation and velocity R²(diff) CIs lie above 0 but below 0.03. Only a trace of the
take-to-take change is structured.

## Threats to validity

- **Shared transcription bias.** Every PianoCoRe take is transcribed, usually by the same system
  per source. A systematic transcriber error that depends on score context (chords, register,
  offsets of bass notes) is common to both takes. It therefore lands in the half-sum and inflates
  R²(sum). This matters most for articulation (offsets) and velocity. The Disklavier check has
  no transcription and still shows the effect in every channel. For timing it is smaller (0.075
  vs 0.118), which is consistent with part of the PianoCoRe timing delta being shared transcriber
  bias. It is also consistent with different repertoire and players; the check cannot separate
  the two. *[Added post-audit, 2026-09-28.]* Nor is the score basis the same: ASAP scores are
  MusicXML (`load_asap_score`) with the F-05 marking groups, while PianoCoRe scores are MIDI
  without markings. A richer basis should raise ASAP R², yet ASAP R²(sum) is lower (0.078 vs
  0.123). That fits some transcriber inflation in PianoCoRe but does not show it, and the size of
  the transcriber share remains unbounded.
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
  MusicXML-based F-05 numbers, nor with the ASAP Disklavier check in this README, which uses
  MusicXML scores with markings *[added post-audit, 2026-09-28]*.
- **No cross-pianist control in the pre-registration** *[added post-audit, 2026-09-28]*. The
  half-difference has no shared component by construction, so delta is about R²(sum) whenever
  take-to-take changes are unstructured. The "falsified" branch was close to unreachable (R-09
  lesson). The post-hoc control above covers this only in part: one pair per piece, not
  pre-registered.
- **Heuristic performer ids** (ASAP name codes; PianoCoRe `performer` strings, e.g. "Scott
  Joplin" is a piano-roll attribution with ICC 0.19).
- **Rach3 not used.** Its Hanon practice files are long sessions over the whole book. Using them
  needs a session-to-take segmentation and alignment step first (a candidate BACKLOG item). The
  repeated-practice setting it would test (the same day, the same player, a non-expert) is the
  one closest to Henry's own use (O-01). This experiment says nothing about it.

## Post-audit corrections (2026-09-28)

Made by feature-engineer after the eval-auditor review (Audit section, "Required changes") and
DECISIONS 2026-09-28. The pre-registered header (first 98 lines) is unchanged; its SHA-256 is
still `b1f57ae2…40ae`. Every edit below is flagged in place with *[... post-audit, 2026-09-28]*.
No number was recomputed by feature-engineer; the new numbers are the auditor's.

1. **Results:** added the cross-pianist positive control table (same pianist delta 0.121
   [0.109, 0.132] vs different pianists 0.097 [0.085, 0.109]; R²(diff) 0.011 vs 0.049; paired
   gap 0.038 [0.030, 0.046]).
2. **Verdict:** reworded. H5 passes its pre-registered test, but the take-consistent part is
   piece-shared timing, not personal intent. What is supported is that a pianist's take-to-take
   variation is mostly unstructured.
3. **Arithmetic:** "about a fifth (0.12 / 0.60)" corrected to about 0.16 of the repeatable part
   (about 0.10 of one take's variance).
4. **Run record:** disclosed the 8-group smoke run after registration (change 3).
5. **Threats:** added the ASAP (MusicXML with markings) vs PianoCoRe (MIDI, no markings)
   score-basis difference, and the missing cross-pianist control.
6. **Wording in the frozen header** that no longer holds: the folder name ("intent-vs-noise")
   and the Baselines line "how much of it anything could call intent". Read "intent" there as
   "the take-consistent part"; F-07 does not show that part is the pianist's intent.
7. **Code wording:** the `pianolens.features.takes` module docstring now says the consistent
   part is not shown to be player-specific intent. No logic changed.

## Audit (2026-09-28)

Auditor: eval-auditor. **Verdict: Confirmed with caveats.** H5 is supported by the
pre-registered reading, and every headline number reruns exactly. The claim that the repeated
part is the pianist's *intent* does not follow. A positive control run for this audit shows that
two takes by *different* pianists pass the same test (timing delta 0.097 [0.085, 0.109]). The
score-explained "consistent" part is mostly timing that any two performances of the piece share.
What F-07 does show is narrower and still useful: a pianist's take-to-take changes are almost
unstructured by the score basis. They are less structured than the differences between two
pianists.

### 1. Pre-registration

- The header (`head -98 README.md`) hashes to `b1f57ae2…40ae`. It is byte-identical to the
  `cat > README.md` heredoc in the feature-engineer transcript
  (`~/.claude/projects/-Users-vuducdung-personal/9591b65d-…/subagents/agent-a5dbb818429903ca6.jsonl`,
  04:08:20Z). That was before `run.py` existed (04:08:56Z) and before any real take was
  loaded. It is also identical to the committed `e4becf8` version. That commit is later than the
  results (00:13 local), so the transcript is the evidence of order, not the commit.
- Before registration the agent counted groups in the metadata and ran synthetic tests.
  Both are disclosed.
- **Not disclosed (harmless):** at 04:09:01Z-04:09:26Z a smoke run (`--limit 8`) printed real
  pair R² for 8 groups. This was after registration. Nothing in the header changed afterwards.
- **The killed first run.** It started at 04:09:33Z. At 04:10:49Z `takes.py` was edited: a
  loop variable was renamed from `l` to `jj` for ruff E741. This does not change any result. At
  04:11:15Z the run was killed because the load average was 46 (R-09 was running). 84 groups had
  been written, and nobody looked at an R² from them. The second run resumed from those 84 lines
  and fed only `groups_v1_rangeblocks.jsonl`. The reported `groups.jsonl` comes from a fresh
  third run with the final `takes.py` (F-05d rule). It has 1,728 lines, all `ok`.
- **ASAP summary line.** It was added at 04:31:26Z. That was after the agent had seen the
  per-group rows of 26 partial ASAP groups (in the v1 analysis). It is descriptive and outside
  the verdict. Disclosure is adequate.
- **The v1 and final analyses.** Apart from the `meta` line, `analysis_v1_rangeblocks.txt` and
  `analysis.txt` are identical up to the ASAP block. The ASAP block differs because 26 groups
  had finished in v1 and 48 in the final run. This confirms "no H5 number changed".

### 2. Reproduction

I copied `groups.jsonl`, `asap_groups.jsonl` and `meta.json` to a scratch folder and reran
`analyze.py` on the copy. The output is **byte-identical** to `artifacts/analysis.txt`. That
covers timing delta 0.118 [0.110, 0.126], R²(sum) 0.123 [0.114, 0.132], R²(diff) 0.005
[0.003, 0.008], 88 of 91 pianists, 1,390 groups / 91 pianists / 415 pieces, the piece bootstrap,
k = 2 only, the 0.95 / 0.90 thresholds and ASAP timing 0.075 [0.053, 0.098]. The pair counts
also check out: 5,472 pairs, 168 with timing r > 0.98 and 752 with tempo r > 0.98 only.
`pytest tests/features/test_takes.py`: 10 passed. `ruff` on the F-07 files: clean.

### 3. The half-sum / half-difference construction

- **Noise averaging is handled.** Take y_j = s + n_j, where n_j is independent noise with
  variance σ². Then the half-sum is s + (n_j + n_l)/2 and the half-difference is (n_j - n_l)/2.
  Both carry noise variance σ²/2. So averaging does not favour the sum in this comparison.
  Two further checks agree: the k = 2-only result (0.120 [0.111, 0.129]) and the k-mean view
  (0.128 vs 0.005).
  - Averaging does raise R²(sum) above the R² of one take. At ICC 0.6 the factor is about
    1/(0.6 + 0.2) = 1.25. That does not affect the sum-versus-difference comparison.
- **What is left is close to a tautology.** The half-difference contains no shared component
  by construction. Suppose the between-take changes are unstructured. Then delta is
  approximately R²(sum). A positive delta then only needs timing to be score-predictable in a
  way that stays stable across takes. F-05 had already shown per-take R² > 0. So the
  "falsified" branch was close to unreachable: this repeats the R-09 lesson, which the
  pre-registration does not discuss.
  - The informative half of H5 is the second one: whether R²(diff) is about 0. That half needs
    a positive control: can the method see structured differences where they exist?
- **Positive control (audit, not pre-registered).** For each of 411 pieces I took one eligible
  group: one pair from the same pianist (a1, a2), with a2 the second kept take after
  de-duplication. I also took a random take b1 by another pianist on the same refined score,
  and formed a cross-pianist pair (a1, b1) that shares take a1. Both pairs were scored with
  `take_structure`. The table shows means, with a 95% bootstrap over pieces (2,000 replicates,
  seed 0).

| Timing (411 pieces) | R²(sum) | R²(diff) | delta | mean pair r |
|---|---|---|---|---|
| Same pianist (a1, a2) | 0.132 [0.119, 0.144] | 0.011 [0.006, 0.016] | 0.121 [0.109, 0.132] | 0.59 |
| Different pianists (a1, b1) | 0.146 [0.132, 0.159] | 0.049 [0.040, 0.057] | 0.097 [0.085, 0.109] | 0.36 |
| Paired difference (different minus same) | +0.014 [0.007, 0.021] | **+0.038 [0.030, 0.046]** | | |

  Other channels, as R²(diff), same pianist vs different pianists:
  - articulation: 0.017 vs 0.037;
  - smooth tempo: -0.026 vs -0.010;
  - velocity: 0.019 vs 0.036.

  Two conclusions follow:
  - **The consistent part is not specific to the pianist.** The score explains the half-sum of
    two *different* pianists' takes at least as well (0.146 vs 0.132). By the pre-registered
    reading, H5 would be "supported" for cross-pianist pairs too. The half-sum R² measures shared
    score-typical timing, not one player's repeated intent.
  - **The low R²(diff) is informative.** The method does detect structured differences
    (0.049 between pianists). A pianist's own take-to-take changes are much less structured
    (0.011, paired gap 0.038 [0.030, 0.046]).
  - This supports a narrower claim: the take-specific part behaves like unstructured variation.
    That is the part tier B uses as "noise". The support stays subject to the limits of the
    basis (see Threats).
- Arithmetic fix: "Structure explains about a fifth of that repeatable part (0.12 / 0.60)" mixes
  denominators. R²(sum) is a share of half-sum variance, and half-sum variance is (ICC + (1 -
  ICC)/2) of one take's variance. So the explained share of the repeatable part is about
  0.123 × 0.8 / 0.6 ≈ 0.16. This is rough: it uses a ratio of group means. The explained share of
  one take's variance is about 0.10.

### 4. De-duplication

- Over-merging is confirmed. In ASAP the 8 merged groups have tempo r 0.981-0.990 and timing
  r 0.53-0.84. No ASAP pair exceeds timing r 0.922. Over-merging drops real takes. It does not
  create a false effect.
- Residual duplicates in PianoCoRe: 93 of 1,390 eligible groups keep a pair with timing r
  above 0.92, the ASAP maximum (39 above 0.95). Dropping them gives 0.116 [0.107, 0.124] over
  1,297 groups. Keeping only groups whose most-correlated pair has r ≤ 0.80 gives 0.108
  [0.100, 0.115] over 1,084 groups.
- Direction: a surviving duplicate makes the half-sum equal to a single take, which has more
  noise. That lowers R²(sum), so duplicates deflate delta rather than inflate it.
- Delta rises with pair correlation:

| Mean pair timing r | Groups | Delta |
|---|---|---|
| 0.2-0.4 | 103 | 0.056 |
| 0.4-0.6 | 556 | 0.091 |
| 0.6-0.8 | 528 | 0.144 |
| 0.8-0.9 | 117 | 0.184 |

  This is expected if delta tracks the shared score-predictable part.
  - Exception: 18 groups have mean pair r ≤ 0.2. Their R²(diff) is 0.088, about equal to their
    R²(sum). These are probably misaligned or non-comparable takes. Too few to matter.
- Files: `artifacts/audit/dups.py`, `artifacts/audit/eligible_pairs_r.csv`.

### 5. Transcription confound

- Shared transcriber errors that depend on score context land in the half-sum. The positive
  control cannot separate them: different pianists are usually transcribed by the same system
  too.
- The Disklavier check establishes that the effect **exists without transcription**:
  ASAP timing delta 0.075 [0.053, 0.098], above 0 in 35 of 40 groups. So the sign of H5 does not
  depend on transcription.
- It does **not** bound how much of the PianoCoRe delta (0.118) is transcriber bias. ASAP
  differs in four ways at once:
  - players and repertoire;
  - its score basis: MusicXML (`load_asap_score`), which has the F-05 marking groups, while
    PianoCoRe scores are MIDI without them;
  - no transcription;
  - n = 40 groups over 28 heuristic ids.
- A richer basis should raise ASAP R², yet ASAP is lower (0.078 vs 0.123 for the sum). That is
  compatible with some transcriber inflation, but it does not show it.
- The README's statement that the check "cannot separate the two" is correct. Add the
  difference in score basis to it.

### 6. Statistics and the F-05d rule

- The cluster bootstrap resamples whole pianists with replacement (`eval.bootstrap`, 91
  clusters). That is correct.
- Pieces are crossed with pianists. A two-way bootstrap would widen the interval, but even
  that interval would stay far from 0:
  - piece bootstrap: [0.107, 0.130];
  - pianist-level mean: [0.106, 0.139].
- Weighting: the unweighted group mean is dominated by a few pianists (Richter 131 groups,
  Arrau 118). The pianist-level mean (0.122) agrees.
- The F-05d rule is applied correctly. `take_structure` uses the same `n_written_bars` /
  `ceil(bars / 4)` / 12-bar / 3-block rule as `shaping._coherence`, and `analyze.eligible`
  filters on `undefined_reason`.
- Folds are written-bar blocks with a 1-bar buffer. Repeats collapse to the first occurrence of
  each score key, so a repeated passage never predicts itself.

### Required changes (for the lead / feature-engineer)

1. **Reword the verdict and the DECISIONS entry.** Say "supported by the pre-registered reading;
   the consistent part is not shown to be player-specific intent". Add the cross-pianist control
   table above. The DECISIONS 2026-09-28 plan ("tier B/D switches to take-consistent = intent
   after the audit and O-01") should not cite F-07 as evidence for "intent". F-07 supports only
   reading the take-specific part as mostly unstructured variation.
2. Fix the "about a fifth (0.12 / 0.60)" sentence (about 0.16; see section 3).
3. Disclose the 8-group smoke run (04:09Z) in the run record.
4. In Threats, add that the ASAP and PianoCoRe score bases differ (with vs without marking
   features).
5. Pre-registration lesson for future tests of this kind: a delta whose difference term has no
   shared component by construction needs a cross-performer control. Without one, "supported"
   is close to guaranteed whenever single-take R² > 0.

### What I could not verify

- Whether PianoCoRe performer strings merge or split real pianists (heuristic ids).
- Whether any residual duplicates have r below 0.92. No metadata identifies re-issues.
- How much of the PianoCoRe timing delta is transcriber bias. This needs either the same
  performances in both Disklavier and transcribed form, or ASAP rerun with `no_markings` on
  matched repertoire. I did not do either.
- The positive control is post-hoc, uses one pair per piece, and was not pre-registered. Treat
  it as an audit finding, not a new result.
  - Its command: `uv run python artifacts/audit/cross.py <out.jsonl>` with BLAS threads set to
    1. Its output is in `artifacts/audit/cross.jsonl`.
