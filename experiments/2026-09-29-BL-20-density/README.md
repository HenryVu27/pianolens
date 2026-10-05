# BL-20: tier A correctness at high note density

Ticket: BL-20    Hypothesis: none (measurement of F-02 under dense playing)    Status: Provisional

## Question

Does tier A correctness (alignment plus wrong-pitch pairing with the 100 ms window) get worse
when notes are closely spaced? In particular, does a wrong note get paired with a neighbour,
absorbed by the aligner, or split into missed plus extra? And is the cause the window or the
aligner?

## Pre-registration

Written and hashed before any density number was computed: `docs/specs/correctness-validation.md`,
section "Pre-registration BL-20". sha256 of that section (from its header line to the newline
before the next `## ` header) is
`3cb1a49922edda51fa71e384d337d6761e3ee7807f097815d1535e7eed9d6924`, hashed 2026-09-29 15:44 CDT.
A copy and the hash are in `artifacts/prereg_section.md` and `artifacts/prereg_sha256.txt`.

In short:

- Local note rate: chords grouped within 30 ms; a chord's local IOI is the median gap among
  chords k-2..k+2. Bins: < 60, 60-100, 100-200, > 200 ms; the judged dense bin is < 100 ms.
- Part A: the F-02 evaluation (`mistakes_v1`) re-run with per-item output and stratified by bin.
- Part B: a stress set of wrong pitches in dense (< 100 ms) or sparse (> 200 ms) passages. The
  wrong key is either equal to a pitch in the neighbouring chords (N) or not (O).
- Concern if any of these holds:
  1. Part A bar any-error F1 in the dense bin is more than 0.03 below the > 200 ms bin (CI
     excludes 0).
  2. Part A: more than 5% of wrong pitches in a bin of at least 100 are paired with another note
     or absorbed.
  3. Part A strict recall in the dense bin is more than 0.10 below the > 200 ms bin.
  4. Part B: dense-N strict recall more than 0.10 below sparse-O, or dense-N bar detection below
     0.95, or a silent share above 2%.

**Added while writing the script, before any run:** Part B picks notes in different score bars
as well as at least 2 s apart, so that each bar's error count change belongs to one injection.
This is disclosed here because it came after the hash.

## Data

- `data/processed/mistakes_v1` (D-08): 100 (n)ASAP performances, single-path scores, clean copy
  plus rates 0.02 / 0.05 / 0.10. Built by `scripts/build_mistake_set.py` (unchanged).
- Part B stress copies are built from the same clean copies and their ground-truth alignment, in
  memory, with seed `[20260929, source index, cell index]`.

Performed notes (counts) by local IOI bin in the 100 clean performances
(`artifacts/a_notes_per_bin_by_composer.csv`):

| Composer | < 60 | 60-100 | 100-200 | > 200 |
|---|---|---|---|---|
| Chopin | 2,060 | 15,780 | 8,375 | 6,209 |
| Liszt | 3,693 | 22,880 | 20,161 | 3,145 |
| Beethoven | 621 | 8,798 | 13,708 | 9,338 |
| Mozart | 485 | 6,798 | 15,659 | 8,982 |
| Haydn | 760 | 5,520 | 18,209 | 4,032 |
| Schubert | 364 | 2,636 | 23,166 | 13,184 |
| Bach | 82 | 623 | 7,433 | 3,232 |
| Others (Debussy, Rachmaninoff, Ravel, Schumann, Scriabin) | 357 | 1,579 | 4,609 | 13,846 |

The < 60 ms bin is thin at bar level (93 bars), so the judged dense bin is the union < 100 ms,
as pre-registered.

## Method

`scripts/eval_correctness_density.py` (new). Part A calls `align_performance` and `correctness`
exactly as `scripts/eval_correctness.py` does, and adds per-bar and per-item rows. **Check:** its
bar "any" tp / fp / fn equal F-02's `data/interim/correctness_eval/counts.csv` on all 1,600
(performance, mode, window) rows. Wrong-pitch outcome of the injected performed note:
`paired_intended` (wrong pitch, paired with the intended score note), `paired_other` (paired
with another score note), `absorbed` (labelled correct: the aligner matched the wrong key to a
written note of that pitch), `extra`, `ornament` (tolerated by the ornament whitelist). Cluster
bootstrap by source performance, 2,000 resamples, seed 20260929. Tests of the local-IOI helper:
`tests/features/test_bl19_bl20_helpers.py`.

## Command

```
OMP_NUM_THREADS=1 uv run python scripts/eval_correctness_density.py --part all --workers 12
```

## Run record

- 2026-09-29, M4 Pro, wall time 1,131 s (Part A 419 s, Part B about 670 s). 0 failures in 400
  Part A alignments and 100 Part B sources (98 sources had eligible dense-N notes).
- Code: git `dd13ab2` plus uncommitted work. `scripts/eval_correctness_density.py` sha256 prefix
  `096c4b697178b36e`. Production code unchanged (`correctness.py`, `perturb.py`, `align/`).
- Outputs in `artifacts/` (gitignored): `a_*.parquet`, `a_*_by_bin.csv`,
  `a_bar_any_dense_vs_sparse_boot.csv`, `b_stress.parquet`, `b_stress_summary.csv`,
  `attribution.txt`, `run.log`.

## Results

### Part A: the F-02 set, stratified (window 100 ms, rate 0.05)

Bar any-error precision / recall / F1:

| Bin | Bars | `aligned` | `gt_alignment` |
|---|---|---|---|
| < 60 ms | 93 | 1.000 / 0.936 / 0.967 | 1.000 / 0.979 / 0.989 |
| 60-100 ms | 2,979 | 0.991 / 0.988 / 0.990 | 0.993 / 0.993 / 0.993 |
| 100-200 ms | 5,689 | 0.993 / 0.988 / 0.991 | 0.995 / 0.993 / 0.994 |
| > 200 ms | 4,172 | 0.983 / 0.972 / 0.977 | 0.990 / 0.986 / 0.988 |

Dense (< 100 ms) minus > 200 ms, bar any-error F1, `aligned`: +0.012 [0.006, 0.018] at rate
0.05; +0.014 [0.004, 0.025] at 0.02; +0.008 [0.002, 0.014] at 0.10. Dense bars are flagged
slightly *better* than slow ones.

Outcome of injected wrong pitches (`aligned`, share of n):

| Bin | n | paired with intended | paired with other | absorbed | extra | ornament |
|---|---|---|---|---|---|---|
| < 60 ms | 145 | 0.779 | 0.007 | 0.062 | 0.131 | 0.021 |
| 60-100 ms | 949 | 0.787 | 0.015 | 0.068 | 0.111 | 0.019 |
| 100-200 ms | 1,827 | 0.854 | 0.007 | 0.044 | 0.087 | 0.008 |
| > 200 ms | 1,001 | 0.883 | 0.010 | 0.015 | 0.089 | 0.003 |

With the ground-truth alignment (`gt_alignment`), "paired with other" is 0.007 / 0.008 / 0.007 /
0.010 and "absorbed" is 0 in every bin. Strict recall, dense minus > 200 ms: `aligned` -0.097
[-0.133, -0.057]; `gt_alignment` -0.025 [-0.055, 0.003].

Other labels, `aligned`, rate 0.05, 100 ms (`artifacts/a_other_by_bin.csv`): injected missed
notes whose score note the aligner still labels correct (it matched another performed note to
it) are 13 of 139 (< 60), 92 of 1,050 (60-100), 156 of 1,836 (100-200) and 35 of 838
(> 200). Injected extras merged into a wrong pitch: 5 / 44 / 35 / 20 by bin.

### Part B: dense stress set (up to 10 isolated wrong pitches per copy)

Window 100 ms. Strict recall with bootstrap CI; other columns are shares.

| Cell | n | Strict recall | Absorbed | Extra | Ornament | Bar detected | Bar count unchanged ("silent") | Bar with no error at all |
|---|---|---|---|---|---|---|---|---|
| `aligned` dense-N | 874 | 0.681 [0.633, 0.726] | 0.157 | 0.096 | 0.058 | 0.969 | 0.144 | 0.031 |
| `aligned` dense-O | 914 | 0.809 [0.774, 0.841] | 0.023 | 0.105 | 0.053 | 0.988 | 0.073 | 0.012 |
| `aligned` sparse-N | 893 | 0.868 [0.841, 0.893] | 0.029 | 0.092 | 0.008 | 0.993 | 0.037 | 0.007 |
| `aligned` sparse-O | 909 | 0.904 [0.879, 0.928] | 0.011 | 0.070 | 0.010 | 0.993 | 0.029 | 0.007 |
| `gt_alignment` dense-N | 874 | 0.812 [0.767, 0.854] | 0 | 0.058 | 0.126 | 0.989 | 0.024 | 0.011 |
| `gt_alignment` dense-O | 914 | 0.864 [0.831, 0.894] | 0 | 0.068 | 0.064 | 0.997 | 0.012 | 0.003 |
| `gt_alignment` sparse-N | 893 | 0.936 [0.916, 0.954] | 0 | 0.046 | 0.017 | 0.997 | 0.006 | 0.003 |
| `gt_alignment` sparse-O | 909 | 0.949 [0.928, 0.968] | 0 | 0.037 | 0.013 | 0.997 | 0.007 | 0.003 |

"Paired with other" is at most 0.011 in every cell. Dense-N minus sparse-O strict recall:
`aligned` [-0.274, -0.174]; `gt_alignment` [-0.186, -0.094]. At 50 ms, strict recall is lower
in every cell (dense-N 0.636 `aligned`, 0.755 `gt_alignment`), and the absorbed share is
unchanged, since the aligner does not see the window.

Absorbed wrong notes were matched to a written note of the played (wrong) pitch in 86.6% of
cases (194 absorbed in `aligned`, all cells). The dense-N absorbed share is highest for Scriabin
(0.308, n = 13), Schubert (0.255), Bach (0.234) and Liszt (0.167). It is lowest for Chopin
(0.067) and Rachmaninoff (0.034, n = 29).

**About "silent".** The pre-registered "silent" means the injected note's bar error count did
not rise against the clean copy. In 82% of silent cases (`aligned`, all cells) the clean bar
already had errors (vs 50% of all injections), and the injection reshuffled them rather than
adding one. The last column (added after the results, not pre-registered) is the share of bars
left with no error flag at all. In dense-N `aligned` that is 27 of 874: 16 absorbed and 11
whitelisted as ornament.

## Verdict (Provisional): concern, and the cause is the aligner, not the window

Against the pre-registered criteria:

1. Bar any-error F1, dense vs > 200 ms: **not triggered**. Dense bars score higher (+0.012
   [0.006, 0.018]).
2. Paired-with-other or absorbed above 5%: **triggered** in < 60 ms (6.9%), 60-100 ms (8.3%)
   and 100-200 ms (5.1%); > 200 ms is 2.5%. Almost all of it is absorption.
3. Strict recall gap above 0.10: **not triggered**, narrowly (-0.097 [-0.133, -0.057]).
4. Part B: **triggered**. The dense-N minus sparse-O strict recall gap is -0.22, and the silent
   share is above 2% in every `aligned` cell (dense-N 14.4%). Bar detection passes (dense-N
   0.969).

**Attribution (pre-registered rule).** Absorption is 0 with the ground-truth alignment and 6-16%
through our aligner in dense passages. It is therefore an aligner effect: the matcher pairs a
wrong key with a nearby written note of the same pitch, as the research log predicted. The
100 ms window is not the problem:

- With a perfect alignment, a wrong note is paired with the wrong score note in at most 1.1% of
  cases in any bin or cell.
- 100 ms beats 50 ms in every dense cell.

A second, smaller labelling effect: in dense passages the ornament whitelist tolerates 6-13% of
injected wrong notes (dense-N `gt_alignment` 0.126 vs 0.013-0.017 sparse). Dense passages
contain more trills and grace notes, and a wrong neighbour key near them falls inside the ±2
semitone allowance.

**What it means for the product.** Bar-level flags ("something went wrong in bar 12") hold up in
fast passages. Note-level wrong-pitch naming ("you played D instead of C") does not: in dense
runs where the wrong key equals a nearby written pitch, about 1 in 3 is not named correctly.
Mostly the wrong key is taken as correct, and the error surfaces as a missed or extra note
nearby.

## Proposals (no default was changed)

1. **Keep the 100 ms window.** Nothing here supports narrowing it or making it depend on density.
2. **Aligner post-pass for same-pitch neighbours (feature-engineer ticket).** After alignment, for
   each match whose performed onset is far from its score note's expected onset (the tier A time
   map), check whether swapping partners with an unmatched same-pitch note, or leaving the match
   as a wrong-pitch pair, lowers the total time cost. This is a local reassignment on the
   existing time map, not a new aligner. Evaluate it on this stress set (target: dense-N
   absorption from 0.157 towards the `gt_alignment` 0) and on F-02 (no loss of bar F1).
3. **Report wording in dense passages.** Until (2) exists, name pitches only for wrong-pitch
   pairs outside dense runs. In runs under 100 ms, say "a wrong or extra note around here" at
   bar level.
4. **Ornament whitelist in dense passages.** Tighten it to the ornament's own pitches (upper and
   lower auxiliary) instead of ±2 semitones, and measure on this set.

## Threats to validity

- **The mistakes are synthetic.** They are isolated single wrong keys on expert Disklavier
  playing. Real slips in fast runs come in clusters, with timing and velocity changes, and those
  are not modelled. Part B deliberately isolates injections (2 s apart, one per bar), so
  cluster effects (the other risk the research log names) are not measured.
- **Local IOI is measured on the performance.** A deliberately rolled chord or a spread melody
  lead longer than 30 ms counts as two onsets and can put a slow passage in a faster bin. The
  4-gap median limits this.
- **Bar numbers exclude bars with natural (n)ASAP mistakes (don't care), as in F-02.** Dense bars
  may be excluded more often.
- **The sources are single-path scores of at most 6,000 notes.** They lean to shorter pieces,
  and the < 60 ms bin has only 93 bars.
- **Part B's O cell** excludes pitches of chords k-2..k+2 only. A wrong key can still equal a
  pitch further away, which the aligner may also reach (sparse-O absorbed 1.1%).
- **"Silent" as pre-registered** mixes injections that added no error with ones that reshuffled
  existing errors in the same bar. The "no error at all" column separates them, but it was added
  after the results were seen.

## Audit (2026-09-29)

Auditor: eval-auditor. **Verdict: Confirmed with caveats.** The pre-registered "concern" verdict
stands and every number reruns exactly. The headline attribution ("the cause is the aligner,
not the window") overreaches and must be reworded (correction 1).

### What was checked

- **Pre-registration.** The section hash `3cb1a499...6d9924` recomputes from
  `docs/specs/correctness-validation.md` lines 179-228 and equals `artifacts/prereg_section.md`.
  Timeline from the feature-engineer transcript: the section was appended at 20:44:00 UTC and
  hashed at 20:44:06. The script was first written at 20:46:16, and the full run started at
  20:47:29. Before the hash, the agent only read code and probed staff and voice numbers and
  hand words for BL-19. No density number was computed before the hash.
- **The "different score bars" rule** was in the first `Write` of the script, before any run, as
  disclosed. Later edits to the script are formatting only (diffed against the transcript).
- **Reproduction.** A full rerun (`--part all`, 10 workers, output to scratch) gives
  byte-identical CSVs and `summary.json`. `a_bars`, `a_wrong` and `b_stress` are equal row for
  row. Script sha256 `096c4b69...` matches the run record.
- **F-02 equality.** Bar "any" tp / fp / fn equal `counts.csv` on all 1,600 (key, mode, window)
  rows (checked independently).
- **Criteria applied as written.** Criteria 1 and 3 are not triggered, and criteria 2 and 4 are
  triggered, with the values in the README.

### Findings

1. **The labelling step alone fails the Part B gap. "Not the window" holds; "the aligner, not
   labelling" does not.**
   - With the ground-truth alignment, dense-N strict recall is 0.812 against 0.949 for
     sparse-O: a gap of -0.137 [-0.186, -0.094]. That is beyond the 0.10 threshold of
     criterion 4.
   - By the pre-registered attribution rule, a deficit present in `gt_alignment` belongs to the
     labelling step.
   - The gap is mostly the ornament whitelist: 0.126 in dense-N vs 0.013 in sparse-O. Unpaired
     extras add a little (0.058 vs 0.037).
   - So a perfect aligner would lift dense-N only to about the `gt_alignment` level, and
     criterion 4 would still trigger. Proposal 4 (ornament whitelist) is co-primary with
     proposal 2, not secondary.
   - Mechanism in `correctness.py`: the whitelist relabels any extra within ±2 semitones of an
     ornamented or grace note (from 0.25 s before its expected onset to its expected offset)
     *before* wrong-pitch pairing, so those notes are never offered to the pairing step.
   - "100 ms beats 50 ms" is true in every cell. Wider windows were not tested, so "the window
     is not the problem" means "narrowing it would not help".
2. **"Absorbed is 0 with the ground-truth alignment" holds by construction.**
   `labels_to_alignment` turns every wrong pitch into a deletion plus an insertion, so no
   `gt_alignment` result can label an injected note correct. The evidence for the aligner's
   share is the contrast between the two modes in strict recall and in outcome shares, not the
   zero itself.
3. **Bar detection counts errors that were already in the bar.**
   - As pre-registered, "detected" means the bar has at least one error label after the
     injection. 58% of dense-N injections land in bars that the clean copy already flags
     (`aligned`; 42% of bars are error-free in the clean copy).
   - Among injections into bars that were error-free in the clean copy:
     - dense-N `aligned`: detection 0.932 (n = 370), below the 0.95 bar; silent share 6.8%;
     - dense-O: detection 0.971;
     - sparse-O: detection 0.989, silent 1.1%;
     - dense-N `gt_alignment`: detection 0.973.
   - The literal criterion passes (0.969). But the product sentence "bar-level flags hold up in
     fast passages" is too strong. In a clean dense-N bar, about 1 in 15 injected wrong keys
     leaves the bar unflagged.
4. **The post-hoc "no error at all" column is exactly 1 minus "bar detected"** in every cell
   (for example 0.0309 = 1 - 0.9691). It adds no information and does not separate reshuffled
   errors from added ones, as the README says it does. The conditional rates in finding 3 do.
5. **The 2% silent threshold also fires in sparse-O** (`aligned` 2.86%). As operationalised, it
   is not density-specific. Conditional on an error-free clean bar, the density contrast is
   real: 6.8% dense-N vs 1.1% sparse-O.
6. **13.4% of absorbed notes are not same-pitch matches.**
   - In 26 of 194 absorbed notes (`aligned`, window 100 ms, all cells), the aligner matched the
     wrong key to a score note of a *different* pitch. In 69% of those, the score note is the
     intended one.
   - `correctness` labels every aligner "match" correct without checking pitch.
   - A pitch check on matches is a cheap labelling fix. It would move these notes to wrong-pitch
     pairs with no aligner change.
   - The Method line "the aligner matched the wrong key to a written note of that pitch"
     describes only 86.6% of absorbed notes.
7. **Bootstrap unit.** The 100 source performances come from 62 pieces, and the bootstrap
   resamples performances. Resampled by piece (2,000 resamples), the CIs widen slightly and
   nothing changes:
   - Part A strict recall gap -0.097 [-0.142, -0.044];
   - Part A bar F1 gap +0.012 [0.005, 0.018];
   - Part B gap, `aligned` -0.224 [-0.278, -0.171];
   - Part B gap, `gt_alignment` -0.137 [-0.195, -0.084].
8. **Criterion 3 is a point-estimate rule.** Its CI, [-0.133, -0.057] by performance and
   [-0.142, -0.044] by piece, contains -0.10. "Not triggered, narrowly" is correct by the rule,
   but the data cannot tell whether the gap exceeds 0.10.

### Required corrections (append as "Post-audit corrections"; do not edit the sections above)

1. Reword the verdict heading and the attribution paragraph:
   - Part A: the aligner is the cause.
   - Part B: the aligner (absorption) and the ornament whitelist (labelling) both contribute, and
     the labelling step alone gives -0.137 [-0.186, -0.094].
   - Narrowing the window would not help; wider windows were not tested.
2. In proposal 2, state that the absorption fix alone cannot clear criterion 4. Make proposal 4
   co-primary. Add a pitch check on aligner matches (finding 6) as a separate labelling
   proposal.
3. Add the conditional bar detection and silent shares (finding 3), and soften the product
   sentence about bar-level flags in dense passages.
4. Describe the "no error at all" column as the complement of "bar detected" (finding 4), or
   replace it with the conditional rates.
5. Correct the Method description of "absorbed" (finding 6).
6. Add the piece-clustered CIs (finding 7) and the criterion 3 remark (finding 8).
