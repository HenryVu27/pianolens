# Factor structure of PercePiano's 19 rating dimensions

Ticket: R-01    Hypothesis: H2    Status: Confirmed with caveats (audit 2026-09-27; post-audit corrections applied, see the last section)

Pre-registered 2026-09-27 by `ml-researcher`, before any correlation, eigenvalue or factor model
was computed. Only row / rater / segment counts had been looked at.

## Question

Do PercePiano's 19 perceptual rating dimensions measure 19 different things, or a few latent
factors? And do individual raters use fewer dimensions than the panel mean shows?

## Falsified if

From the plan (H2): "PercePiano's 19 rating dimensions collapse to 3-5 latent factors. Falsified if
parallel analysis retains more than 8 factors."

Refined, fixed before running:

- **Primary test:** Horn's parallel analysis on the **segment-mean** ratings (one row per segment,
  19 columns), PCA eigenvalues of the Pearson correlation matrix, compared with the 95th
  percentile of eigenvalues from 1000 column-permuted copies of the same data (seed 0). Retained
  count = number of leading observed eigenvalues above their null percentile.
- **Verdict mapping:**
  - retained > 8: **H2 falsified**;
  - retained 3-5: **H2 supported**;
  - retained 6-8: **not falsified, but outside the predicted range** (inconclusive);
  - retained 1-2: **not falsified; collapse stronger than predicted** (the 3-5 range is wrong in
    the other direction; reported as such, not as support).
- Secondary counts (FA-based parallel analysis on the reduced correlation matrix; Velicer's MAP)
  are reported but do not change the verdict.

## Data

- PercePiano, `data/raw/percepiano`, shallow clone of 2026-09-27 (DATASETS.md). License CC BY-NC-ND
  (research use).
- Per-rater file `labels/total_2rounds.csv`: 14,934 rows, 65 raters, 1,202 distinct file names,
  4-19 ratings per segment (median 14). Mean label files `labels/label_2round_mean_*.json`
  (1,189 keys) and a different top-level copy (1,202 keys) are used only as a cross-check.
- **Loader:** the D-02 loader (`src/pianolens/data/`) does not exist yet, so `run.py` parses the
  CSV itself. Cleaning follows the authors' `labels/map_midi_to_label.py` exactly:
  - file name: strip `.wav`; `_score` -> `_Score`; the authors' `Score` -> `Score2` renames;
  - the 19 items are CSV columns 4-22 (`Question_1_1_1` .. `Question_9_1_1`); `Question_9_2_1`
    and `message` are dropped (as in the authors' `row[3:-2]`);
  - a rating row with any value > 7.1 is dropped (scale is 1-7);
  - an empty cell or 0 means "not rated" for that dimension;
  - segment mean per dimension = mean of that dimension's non-missing ratings; a segment with any
    dimension rated by nobody is dropped.
- Item names: the 19 columns are mapped, in order, to the 19 names in the PercePiano README table
  (Timing, Articulation x2, Pedal x2, Timbre x4, Dynamic x2, Music making x4, Emotion x3,
  Interpretation). The question-code prefixes (Q1 = 1 item, Q2 = 2, Q3 = 2, Q4 = 4, ...) match the
  group sizes, which supports the mapping, but it is an inference.
- Ids: `<piece>_<N>bars_<player>_<segment>`. piece = prefix before `_<N>bars` (20 pieces: 17
  Beethoven WoO 80 variations/theme, Schubert D935 no.3, D960 mv2, D960 mv3). performer = the
  player token; `Score` and `Score2` (deadpan score renders) are both performer `Score`.

## Splits

No predictive model is trained, so there are no train/test folds. Grouping enters through the
cluster bootstrap (`pianolens.eval.bootstrap_indices`):

- stability of the retained count and of the loadings: 500 bootstrap replicates resampling
  **performers** (primary; about 22 clusters) and 500 resampling **pieces** (secondary; 20
  clusters, dominated by D960 mv3 and mv2). Seed 0.

## Baselines

- Null for "how many factors": the permutation null of parallel analysis (uncorrelated items with
  the same marginals).
- Noise ceiling context: split-half rater reliability of each of the 19 items and of each factor
  score (raters of each segment split at random into two halves, segment means per half,
  Spearman-Brown corrected, 100 splits, seed 0). Rater parity proper does not apply because
  nothing is predicted.

## Method

`experiments/2026-09-27-R-01-percepiano-factors/run.py`. Libraries: numpy, pandas, scipy,
factor-analyzer (EFA), `pianolens.eval`.

A. **Segment-mean level** (primary)
1. Pearson correlation matrix of the 19 items; mean |r| off-diagonal; KMO and Bartlett's test.
2. Parallel analysis (primary as above), FA-based PA (SMC-reduced matrix, same null), MAP.
3. EFA: minres extraction, oblimin rotation, k = PA-retained count. Also k = 3, 4, 5 so the
   H2 range can be read directly. Report pattern loadings, factor correlations, communalities,
   variance shares.
4. Factor reliability: (a) Cronbach's alpha and McDonald's omega (from the one-factor loadings of
   each factor's salient items; salient = |pattern loading| >= 0.40, each item assigned to its
   largest loading); (b) split-half rater reliability of factor scores (as above);
   (c) Tucker congruence between the full-sample loadings and each bootstrap replicate's
   loadings (factors matched by the Hungarian algorithm on |congruence|).
5. Sensitivity: drop the `Score`/`Score2` deadpan renders and rerun 2-3.

B. **Per-rater level** (do raters use fewer dimensions?)
1. Pooled within-rater: individual rating rows complete on all 19 items; subtract each rater's
   own per-item mean (removes leniency); correlation, PA, EFA as in A.
2. Each rater with >= 100 complete rating rows: PA on that rater's own rows (raw, their own
   centring is implicit in correlation) -> retained count, share of variance of the first
   eigenvalue.
3. Matched-N comparison: for each such rater, PA on 200 random subsamples of the segment-mean
   matrix with the same number of rows; compare the rater's retained count with the median
   subsample count. PA power depends on N, so this is the fair comparison.
4. Report: distribution of per-rater retained counts vs matched-N segment-mean counts; first
   eigenvalue share per rater vs segment-mean level.

Interpretation fixed in advance: individual ratings contain more noise, which lowers
correlations and pushes PA toward fewer factors even if raters perceive more. So "raters use
fewer dimensions" is only claimed if per-rater retained counts are lower than matched-N
segment-mean counts **and** the first-eigenvalue share per rater is at least as high as at the
segment-mean level (a halo effect, not just noise).

## Command

```
uv run python experiments/2026-09-27-R-01-percepiano-factors/run.py
```

Outputs go to `experiments/2026-09-27-R-01-percepiano-factors/artifacts/` (gitignored).

## Amendment before running (2026-09-27, still no correlations computed)

Profiling found repeated (rater, file) pairs in `total_2rounds.csv`: 3,634 rows repeat an earlier
(rater, file) pair; 2,198 of them are exact resubmissions (same rater, `dataID` and file) and the
rest are the same rater rating the same file again with a new `dataID`. The authors' script keeps
every row. Handling, fixed now:

- **A (segment means, primary):** keep every row, exactly as the authors do, so the analysed
  matrix is the one PercePiano models are trained on. Sensitivity: drop exact resubmissions and
  average repeat ratings per (rater, file) first; rerun A.1-A.2.
- **B and the split-half reliabilities:** one row per (rater, segment): drop exact resubmissions,
  then average a rater's repeat ratings of the same segment item by item.
- **Exploratory addition:** the repeat ratings (different `dataID`) give a within-rater
  test-retest correlation per item. Reported as context only; no verdict depends on it.
- Bootstrap replicates for the retained-count stability use 200 permutation-null iterations
  each (not 1000) to keep run time reasonable; the primary count uses 1000.

## Run record

- Ran 2026-09-27 on the M4 Pro Mac, wall time 432 s. Seed 0 throughout.
- Git: no commits exist in the repo yet (uncommitted). `run.py` sha256 prefix `c6a7c772d598f56f`
  (the version that produced these numbers); `total_2rounds.csv` sha256 prefix `96a61ce89a311979`.
- factor-analyzer 0.5.1 fails with scikit-learn 1.9 (`force_all_finite` keyword); `run.py` wraps
  `check_array` to translate the keyword. No dependency change.
- Full output: `artifacts/results.json`; loadings `artifacts/loadings_k*.csv`, factor
  correlations `artifacts/phi_k*.csv`, `artifacts/parallel_analysis.csv`, `artifacts/per_rater.csv`.
- Post-audit rerun 2026-09-27 (same command, seed 0, wall time 504 s), `run.py` sha256 prefix
  `5371e6da2df9a43a`: fixes the factor-correlation order and the communalities and adds three
  sensitivities. Every count, bootstrap, reliability and per-rater number is unchanged; see
  "Post-audit corrections".

## Results

### Data after cleaning

- 14,726 rating rows (208 dropped for values > 7.1), 63 raters left (2 raters had only dropped
  rows), **1,189 segments** with all 19 items rated, 20 pieces, 21 performers (incl. `Score`).
- Cross-check: segment means recomputed from the CSV equal `labels/label_2round_mean_*.json`
  (1,189 keys) exactly (max abs diff 4e-16). The top-level json (1,202 keys) is a different
  version: 1.1% of shared segments differ, by up to 1.5 scale points.

### Headline: how many factors (segment-mean level, n = 1,189)

| Criterion | Retained | Cluster bootstrap distribution (500 replicates each) |
|---|---|---|
| **PCA parallel analysis (primary, 1000 perms)** | **4** | performers: 3 (1%), 4 (79%), 5 (20%); pieces: 2 (0.2%), 3 (6%), 4 (94%) |
| FA parallel analysis (SMC-reduced) | 7 | not bootstrapped |
| Velicer MAP | 5 | not bootstrapped |
| Replicates retaining > 8 (falsifier) | | 0 / 500 (performers), 0 / 500 (pieces) |

Observed PCA eigenvalues 8.87, 3.21, 1.79, 1.36, 1.03 vs permutation 95th percentiles 1.27,
1.22, 1.18, 1.15, 1.12. The first component alone carries 47% of the variance. Mean |r| between
items 0.40 (max 0.91). KMO 0.90; Bartlett chi2 25,504, p < 1e-300.

Sensitivities: without the deadpan `Score` renders (n = 1,073) PCA-PA retains 5 (FA-PA 7, MAP 5);
with exact resubmissions dropped and repeat ratings averaged, PCA-PA retains 4 (FA-PA 7, MAP 5).
Added post-audit: both of those together (n = 1,073) give PCA-PA 5 (FA-PA 6, MAP 5). The two pedal
items correlate 0.89; averaging them into one item gives PCA-PA **3** (FA-PA 7, MAP 5), and dropping
Pedal clean-blurred gives PCA-PA 3 (FA-PA 7, MAP 3). So the 4th component rests partly on this
near-duplicate pair.

### Four-factor oblimin solution (minres; pattern loadings, |loading| >= 0.40 in bold)

| Item | F1 quality / sophistication | F2 loudness / energy | F3 pedal / legato (see note) | F4 dark mood | h2 (corrected post-audit) |
|---|---|---|---|---|---|
| Timing stable-unstable | 0.28 | -0.06 | 0.11 | 0.08 | 0.14 |
| Articulation short-long | 0.38 | -0.26 | **0.50** | 0.14 | 0.72 |
| Articulation soft-hard | **-0.45** | **0.45** | -0.37 | 0.11 | 0.74 |
| Pedal sparse-saturated | 0.15 | -0.03 | **0.90** | -0.02 | 0.96 |
| Pedal clean-blurred | -0.14 | 0.07 | **1.00** | 0.03 | 0.89 |
| Timbre even-colorful | **0.87** | 0.25 | 0.03 | -0.02 | 0.79 |
| Timbre shallow-rich | **0.75** | 0.06 | 0.34 | -0.02 | 0.91 |
| Timbre bright-dark | 0.01 | -0.08 | 0.01 | **0.88** | 0.81 |
| Timbre soft-loud | -0.20 | **0.79** | 0.04 | -0.11 | 0.75 |
| Dynamic mellow-raw | **-0.79** | **0.46** | 0.06 | 0.07 | 0.88 |
| Dynamic range little-large | **0.63** | **0.60** | -0.02 | 0.15 | 0.63 |
| Music fast-slow | 0.34 | -0.38 | 0.02 | 0.38 | 0.51 |
| Music flat-spacious | **0.90** | 0.04 | 0.07 | 0.08 | 0.88 |
| Music disproportioned-balanced | **0.84** | -0.18 | -0.04 | -0.05 | 0.75 |
| Music pure-dramatic | **0.76** | 0.31 | 0.17 | -0.05 | 0.76 |
| Emotion pleasant-dark | -0.06 | 0.03 | 0.01 | **0.94** | 0.88 |
| Emotion low-high energy | 0.10 | **0.82** | 0.01 | -0.23 | 0.79 |
| Emotion honest-imaginative | **0.84** | -0.13 | 0.09 | 0.08 | 0.86 |
| Interpretation unconvincing-convincing | **0.91** | -0.07 | -0.03 | -0.06 | 0.82 |

Factor labels are my reading, not measured. The h2 column was corrected after the audit: it is
now the true communality diag(L Phi L'). The first version reported factor-analyzer's
`get_communalities()`, which sums squared pattern loadings and is not the communality under an
oblique rotation. Mean communality (common variance explained) is 76%. Factor correlations
(corrected post-audit): F1-F3 0.49, F2-F4 -0.20, F1-F2 -0.14, the rest within +-0.10 (F3-F4 0.10,
F1-F4 0.03, F2-F3 -0.01). So the quality factor correlates with pedal / legato, not with dark
mood. Timing and fast-slow load >= 0.40 on no factor (h2 0.14 and 0.51): they are the least
redundant items. The largest communality is Pedal sparse-saturated (0.96; 0.98 at k = 5): the
solution is proper but near the boundary.

Note on F3: its items are articulation item 2 and the two pedal items. The authors' code names
item 2 `Articulation_Long_Short`; their README names it `Articulation_Short_Long`. Which pole is
7 is not documented. If it is "short", F3 reads "pedal / detached" rather than "pedal / legato".
The label is uncertain for this reason; the loadings are not.

### Factor reliability (k = 4)

| Factor | Salient items (assigned by max loading) | alpha | omega | Split-half over raters (SB) | Bootstrap congruence, median [5th pct], performers / pieces |
|---|---|---|---|---|---|
| F1 | 10 | 0.95 | 0.95 | 0.79 | 0.997 [0.985] / 0.995 [0.972] |
| F2 | 2 (soft-loud, low-high energy) | 0.84 | n/a (< 3 items) | 0.82 | 0.996 [0.977] / 0.989 [0.933] |
| F3 | 3 (articulation short-long, both pedal) | 0.89 | 0.90 | 0.89 | 0.996 [0.982] / 0.986 [0.911] |
| F4 | 2 (bright-dark, pleasant-dark) | 0.93 | n/a | 0.80 | 0.997 [0.991] / 0.982 [0.904] |

For comparison, single-item split-half reliabilities range 0.64 (dynamic range) to 0.88 (pedal
sparse-saturated), median 0.74. So factor scores are about as reliable as the best single items,
and more reliable than the median item. Articulation soft-hard is assigned to F1 by a 0.454 vs
0.446 margin; treat its assignment as arbitrary.

### Per-rater level

| Analysis | Result |
|---|---|
| Pooled within-rater (10,854 complete rater x segment rows, centred per rater) | PCA-PA 4, FA-PA 8, MAP 4; first eigenvalue 33% of variance; mean abs r 0.26 |
| Congruence of pooled within-rater k=4 loadings with segment-mean loadings | 0.97, 0.93, 0.99, 0.99 |
| Individual raters with >= 100 complete rows | 42 raters; PCA-PA retained: 1 (1 rater), 2 (8), 3 (16), 4 (16), 5 (1); median 3 |
| Same PA on segment-mean subsamples of matched n | median of medians 3; rater lower than matched in 33% of raters, higher in 24% |
| First-eigenvalue share | raters median 34% vs segment means 47%; 26% of raters at or above 47% |
| Within-rater test-retest (exploratory; 1,328 repeat pairs, 47 raters) | median item r 0.52 (range 0.42 energy to 0.69 pedal saturation) |

## Verdict (rewritten post-audit, 2026-09-27)

**H2 supported, with the range stated per criterion.** The pre-registered primary test (PCA
parallel analysis on segment means) retains **4** factors, inside the predicted 3-5 range. No
bootstrap replicate over performers or pieces retained more than 5. The falsifier (> 8) is never
met under any criterion or variant tried.

The 3-5 range itself holds under PCA-PA (4) and MAP (5), but **not under FA-PA (7)**. Under FA-PA
the pre-registered mapping would read "6-8: inconclusive". Only PCA-PA was pre-registered to
decide the verdict, so the verdict stands, but the FA-PA reading is inconclusive and is reported
as such.

The count moves with reasonable choices: merging the two near-duplicate pedal items (r = 0.89)
gives PCA-PA **3**; excluding the deadpan `Score` renders gives **5**. The claim that transfers is
therefore **3-5 factors with one dominant general factor; falsifier (> 8) never met**, not
"exactly 4".

The structure is one dominant general factor (47% of item variance on the first component;
interpretation, balance, spaciousness, colour, imagination, low rawness) plus three narrow ones:
loudness / energy, pedal / articulation, and dark mood. The general factor correlates 0.49 with
the pedal / articulation factor. Timing stability is almost unrelated to the rest.

**Do raters use fewer dimensions? Not supported** by the pre-registered rule. Individual raters
retain about as many components as segment-mean subsamples of the same size (median 3 vs 3), and
their first component is weaker, not stronger (34% vs 47%). The pooled within-rater structure
matches the panel structure (congruence 0.93-0.99). The larger general factor at the panel level
is what averaging does: rater noise, which is mostly uncorrelated across items, cancels in the
mean. It is not a sign that each rater applies a single halo judgement.

## Threats to validity

- **Near-boundary pedal items:** Pedal sparse-saturated has communality 0.96 (k = 4) to 0.98
  (k = 5), near the boundary; the two pedal items correlate 0.89. Merging them lowers PCA-PA to 3.
  (The first version reported a Heywood case here; that was a factor-analyzer reporting artifact,
  see "Post-audit corrections".)
- **FA-PA disagrees with the range:** FA-PA retains 7 (6 to 8 across variants), which the
  pre-registered mapping would call inconclusive.
- **Small, unbalanced design:** 20 pieces, two Schubert movements are 72% of segments; 21
  performers. The piece bootstrap is the weaker stability check for this reason.
- **Rated from rendered audio** of the MIDI; the structure describes what these raters heard in
  these renders.
- **Item-name mapping** (CSV column order -> README names) is inferred, not documented. The count
  of factors does not depend on it; the factor labels do.
- **Bipolar scales:** several items (dark, slow, blurred) carry valence ambiguously, which may
  make some items look like opposites of quality by construction.
- **Loader:** labels parsed in `run.py`, not the D-02 loader. Counts should be rechecked once
  D-02 lands.
- PA power depends on n; the per-rater comparison controls for this by matching n, but raters
  with 100-250 rows give noisy counts.

## Audit (2026-09-27)

Auditor: `eval-auditor`. Verdict: **Confirmed with caveats.** H2 is supported by the pre-registered
rule, and the retained-factor count reproduces exactly. The descriptive EFA tables contain three
reporting errors caused by factor-analyzer 0.5.1. They do not touch the verdict, but they must be
corrected before anyone cites the factor correlations, communalities or the "Heywood case"
(required fixes 1-3 below). Audit scripts and outputs are in the auditor's scratchpad, not in the
repo; the numbers below come from them.

### What was checked

| Check | Result |
|---|---|
| Pre-registration (no git history, so checked against the ml-researcher session transcript) | README sections Question to Command were written at 22:57:42 UTC in one `Write` and are byte-identical to the current file. The Amendment was appended at 22:58:21. The first run attempt (22:59:37) crashed in `FactorAnalyzer.fit` before printing any result; the real run started 22:59:51. Before 22:57:42 only counts, value ranges and filename parsing were profiled; no correlation or eigenvalue was computed. PCA-PA as primary, FA-PA and MAP as secondary, and the verdict mapping were all fixed before results. |
| Falsifier matches the plan | Yes. Plan H2: "Parallel analysis retains more than 8 factors". README copies it verbatim and only adds the 3-5 / 6-8 / 1-2 mapping. |
| Rerun of the recorded command (copy of `run.py` with only `ROOT`/`OUT` redirected to scratch) | Exact match. All 14 CSV artifacts are byte-identical and every field of `results.json` matches, apart from the script hash (my redirected copy) and the wall time (480 s). PCA-PA 4, FA-PA 7, MAP 5; bootstrap retained counts performers {3: 5, 4: 395, 5: 100}, pieces {2: 1, 3: 29, 4: 470}. The recorded `run.py` hash `c6a7c772d598f56f` and CSV hash `96a61ce89a311979` match the files on disk. |
| PCA-PA robustness | 4 under all of: permutation or normal null, 95th percentile or mean criterion, seeds 0-9. Margins are clear: 4th eigenvalue 1.36 vs null 1.15, 5th 1.03 vs 1.12. |
| Segment means reproduce `labels/label_2round_mean_*.json` | Confirmed with an independent parser (`csv` module, the authors' `map_midi_to_label.py` logic line by line): 1,189 segments, key set identical to the json and to `run.py`'s, max abs diff 4.4e-16 vs json, 0.0 vs `run.py`. |
| Item order (column -> dimension name) | Confirmed from the authors' code, not only inferred. `LABEL_LIST19` in `virtuoso/virtuoso/train_m2pf.py` and `virtuoso/case_study_result_comparison.py` has the same order as the README table, and the README's example segment `Beethoven_WoO80_var27_8bars_3_15` "Label" column equals that key's json vector element by element. CSV cols 4-22 -> json index -> `LABEL_LIST19` is a closed chain. One gap: the code names item 2 `Articulation_Long_Short`, the README `Articulation_Short_Long`. Its pole direction is undocumented. |
| Filename order (lead's question: player vs segment) | `run.py` parses `<piece>_<N>bars_<player>_<segment>`, which is correct; the PercePiano README (line 44, "segment number then player number") is wrong. Evidence: the authors' code takes `split("_")[-2]` as the pianist; second-to-last tokens are {0-14, 18, 19, 22, 24, 26, Score, Score2}; the last token runs 1-50 and each (piece, last token) has 8-14 distinct players. So 21 performers (20 people + `Score`) and 20 pieces are right, and both cluster bootstraps resample the right units. |
| factor-analyzer / sklearn shim | Harmless. k = 4 and k = 5 oblimin loadings are identical (max diff 0.0) to factor-analyzer 0.5.1 with scikit-learn 1.5.2 and no shim. |
| Bootstrap unit and n | Performers (21 clusters) and pieces (20), 500 each, n and counts reported. Duplicated rows in a cluster bootstrap make the permutation null slightly too narrow, which pushes toward *more* factors, so "0 of 1,000 replicates > 8" (and none > 5) is conservative. |
| Deadpan renders and duplicate ratings | All segments: 4. No `Score` (n = 1,073): 5 (10 of 10 seeds; 5th eigenvalue 1.17 vs 1.13). Deduplicated: 4. Deduplicated and no `Score` (not in the README): 5, FA-PA 6, MAP 5. All inside 3-5. |
| Near-duplicate pedal items | Not in the README. The two pedal items correlate 0.89. Averaging them, or dropping Pedal clean-blurred, gives PCA-PA **3**. So the 4th component rests partly on this doublet. Still inside 3-5. |

### Findings on the claims

1. **Primary vs FA-PA disagreement.** Handled honestly. The primary criterion was fixed in advance,
   and Horn's PCA version is the standard reading of "parallel analysis". H2's *falsifier* fails
   under every criterion (PCA-PA 4, FA-PA 7, MAP 5; FA-PA with a mean criterion gives 8, which is
   still not > 8). But the *3-5 range* holds only under PCA-PA and MAP. Under FA-PA the
   pre-registered mapping would read "6-8: inconclusive". The verdict paragraph should say this
   in so many words instead of "as it usually does". Across the variants tested here, the count
   is 3 to 5 for PCA-PA and MAP, and 6 to 8 for FA-PA.
2. **The "Heywood case" does not exist.** It is a reporting artifact. `get_communalities()` in
   factor-analyzer returns the row sum of squared *pattern* loadings. Under an oblique rotation
   that is not the communality. The true communality (row sum of squared unrotated loadings,
   same fit) of Pedal clean-blurred is 0.89 at k = 4 and 0.87 at k = 5. The largest is Pedal
   sparse-saturated: 0.96 (k = 4) and 0.98 (k = 5). The solutions are proper but close to the
   boundary. The whole `h2` column and "common variance explained 71%" are affected.
3. **The factor correlations are misassigned.** factor-analyzer 0.5.1 re-sorts `loadings_` by
   variance after rotation but does not re-sort `phi_`. `sort_factors` then permutes both the same
   way, so the mismatch stays. The correctly aligned k = 4 correlations (checked: they reproduce
   the model-implied common covariance to 1e-15) are:

   | | F1 quality | F2 loudness | F3 pedal / legato | F4 dark mood |
   |---|---|---|---|---|
   | F1 | 1 | -0.14 | **0.49** | 0.03 |
   | F2 | | 1 | -0.01 | -0.20 |
   | F3 | | | 1 | 0.10 |

   So quality correlates with **pedal / legato**, not with dark mood. A raw check agrees: the mean
   of four F1 items correlates 0.48 with the pedal-item mean and 0.00 with the dark-item mean.
   `artifacts/phi_k4.csv` and `phi_k5.csv` are wrong in the same way.
4. **The loadings themselves are correct.** Pattern loadings, salient-item assignment, alpha,
   omega, split-half factor reliabilities (`transform` uses `structure_`, which is sorted
   correctly) and congruences do not depend on `phi_`. ML extraction gives the same loadings
   (congruence 0.999-1.0 with minres).
5. **Per-rater section (B).** Not re-derived independently. The rerun reproduced it (see the rerun
   row). The conclusion "raters do not use fewer dimensions" follows the pre-registered rule.

### Required fixes (by `ml-researcher`; no re-run of the count needed)

1. Replace the `h2` column of the four-factor table with true communalities (k = 4, item order as
   in the table): 0.14, 0.72, 0.74, 0.96, 0.89, 0.79, 0.91, 0.81, 0.75, 0.88, 0.63, 0.51, 0.88,
   0.75, 0.76, 0.88, 0.79, 0.86, 0.82. Mean 0.76, so "common variance explained" is 76%, not 71%.
   Timing and fast-slow are still the least shared items (0.14 and 0.51).
2. Remove the Heywood threat (both from Threats to validity and from the ml-researcher memory
   `results-index.md`). Replace it with "Pedal sparse-saturated communality 0.96-0.98, near the
   boundary; the two pedal items correlate 0.89".
3. Correct the factor-correlation sentence to F1-F3 0.49, F2-F4 -0.20, F1-F2 -0.14, others
   |r| <= 0.10. Fix `phi_k*.csv` in `run.py` (re-sort `phi_` with the same order as the
   loadings, or compute it from the unrotated loadings) and compute communalities as
   diag(L phi L').
4. Add to the verdict: the 3-5 range holds under PCA-PA and MAP, not under FA-PA (7). Add the
   pedal-doublet sensitivity (3 factors when the pedal items are merged).
5. Note the pole-direction ambiguity of item 2 (`Articulation_Long_Short` in the authors' code)
   next to the F3 label.

### Caveats that stay with the Confirmed verdict

- "4" is the pre-registered count. Reasonable variants give 3 (pedal items merged) to 5 (deadpan
  renders removed). The claim that transfers is "3-5 factors, one dominant general factor", not
  "exactly 4".
- Labels are ratings of rendered audio, from 20 pieces dominated by two Schubert movements.

## Post-audit corrections (2026-09-27)

By `ml-researcher`, applying the audit's required fixes. The pre-registration sections (Question
to Amendment) are unchanged. `run.py` was fixed and rerun (see Run record); results tables were
edited in place and each edit is flagged there.

1. **Communalities.** `run.py` now computes h2 as diag(L Phi L'). It checks against the row sums
   of squared unrotated loadings from the same fit (max difference 5e-4, which is CSV rounding).
   The four-factor table's h2 column is replaced with these values, which equal the audit's
   exactly. Common variance explained is **76%**, not 71%. `loadings_k*.csv` now carry both `h2`
   (true) and `pattern_ss` (the old, wrong value, kept for traceability). The pattern loadings
   themselves are byte-identical to the first run.
2. **No Heywood case.** Pedal clean-blurred's true communality is 0.89 (k = 4) and 0.87 (k = 5).
   The Heywood threat is removed. It is replaced by "Pedal sparse-saturated 0.96-0.98, near the
   boundary; pedal items r = 0.89".
3. **Factor correlations.** factor-analyzer 0.5.1 re-sorts `loadings_` and `structure_` after
   rotation but not `phi_`. `run.py` now recovers the permutation of `phi_` that satisfies
   structure = loadings @ phi (residual asserted < 1e-8) before `sort_factors`, so
   `phi_k*.csv` are in loading order. Corrected k = 4: F1-F3 0.49, F2-F4 -0.20, F1-F2 -0.14,
   F3-F4 0.10, F1-F4 0.03, F2-F3 -0.01. This matches the audit's table. The first version said
   "F1-F4 0.49, F2-F3 -0.20", which was wrong. Corrected k = 5 (for the record): F1-F3 0.59, F1-F2 0.42,
   F2-F3 0.48, F4-F5 -0.25, F1-F4 -0.23, the rest within +-0.10.
4. **Verdict wording.** Rewritten to say that the 3-5 range holds under PCA-PA and MAP but FA-PA
   (7) reads inconclusive. It adds the pedal-merge result (PCA-PA 3; FA-PA 7, MAP 5; dropping
   Pedal clean-blurred instead gives 3 / 7 / 3) and the Score-excluded result (5). Also added:
   dedup plus no Score gives 5 (FA-PA 6, MAP 5). All reproduce the audit's counts. Headline: "3-5
   factors with one dominant general factor; falsifier (> 8) never met".
5. **Item 2 pole direction** noted next to the F3 label: `Articulation_Long_Short` in the authors'
   code, `Articulation_Short_Long` in their README. `run.py` keeps the README name.

The verdict stays **Confirmed with caveats**. None of the fixes changes a retained count, a
bootstrap distribution, a reliability or a per-rater result. Those fields of `results.json` are
identical to the first run.

