# Same-pianist practice takes (Rach3 Hanon): is take-to-take variation less structured than between-pianist differences?
Ticket: BL-16    Hypothesis: H5 follow-up (F-07 reinterpretation; proxy for O-01)    Status: Provisional

Pre-registered 2026-09-28. Written after the takes were built and counted, after an alignment
check against parangonar, and after one smoke run of `run._group` on one real p3 group. That
run printed only the observation counts per channel (timing 224, tempo 233, velocity 464,
articulation 464), not any R², ICC or SD. No take-to-take statistic had been computed before
this header was written. Sections below "Results" are added afterwards.

## Question

F-07 (DECISIONS 2026-09-28) supports only a narrow claim: a pianist's own take-to-take changes
are less structured by the score than the differences between two pianists (R²(diff) 0.011 vs
0.049, transcribed concert recordings, often years apart). Does the same hold for **practice
takes**, played close together in time by **non-concert pianists**, for a beginner and for
advanced pianists? This is the setting closest to Henry's own use (O-01).

## Data

- Rach3 Hanon subset (DATASETS.md: commit a9519492; CC BY-NC-SA 4.0; keyboard MIDI, tagged
  `sensor`). p1 and p2 are advanced, p3 is a beginner (README levels).
- Takes: `scripts/build_rach3_hanon_takes.py`, method in `pianolens.data.rach3_takes`
  (docstring). Summary:
  - one-pass scores for Hanon Part I Nos. 1-20 are cut from the book MusicXML (repeat signs
    removed; the book's first attributes copied in). Part II has no exercise separators and
    is not used;
  - each session is grouped into onset events (chord threshold 40, 60 or 80 ms, chosen per
    session by the highest total DP score of well-matched takes);
  - a fitting alignment (score end to end, session free) with exact pitch-set scoring finds
    complete passes; non-overlapping, best first, then resolved across exercises;
  - notes are matched by pitch inside paired events.
- QC (`TakeQC`, fixed before any statistic): event match >= 0.90, note match >= 0.90,
  insertions <= 0.15 per score note, and longest pause <= 8x the median time per score onset.
- Counts (from `data/interim/rach3_hanon_takes/summary.txt`): 247 sessions, 2,038 takes kept
  after overlap resolution, 1,149 pass QC (p1 372, p2 191, p3 586). Matched notes in kept
  takes / session notes: p1 0.44, p2 0.79, p3 0.80 (p1 plays much outside Part I in C).
  QC failures (not exclusive): pause 831, insertions 217, event match 157, note match 54.
- Alignment check: on 24 QC takes (8 per pianist, seed 0), 99.5% of the DP note matches are
  also parangonar (`align_performance`) matches (minimum 95.5%).

**Feasibility finding (same-day, beginner).** p3 plays each exercise at most once per day, with
rare exceptions. Before QC there are only 11 same-day (exercise, day) groups with 2 or more takes
(23 takes). After QC there are none. One session per day, 76 days with takes. So the brief's
same-day beginner arm cannot be run. The beginner arm uses **next-day** pairs instead (below),
and the advanced pianists get the same next-day analysis for comparison.

## Units and windows

- `same_day`: group = (pianist, exercise, calendar day) with >= 2 QC takes; up to the first 8
  takes in time order; a1, a2 = the first two. Counts: p1 42 groups (13 days), p2 47 (19
  days); p3 0.
- `next_day`: per pianist and exercise, days d and d + 1 both with a QC take, paired greedily
  without reusing a day; a1 = first take on d, a2 = first take on d + 1. Counts: p1 28 groups
  (5 distinct d), p2 17 (4), p3 147 (43).
- Cross-pianist control (F-07 audit, rules/experiments.md): for each group, b1 = a random QC
  take of the same exercise by another pianist (seed 0). For an advanced group, b1 comes from
  the other advanced pianist. For p3, b1 comes from p1 or p2. The cross pair (a1, b1) shares
  take a1 with the same-pianist pair (a1, a2). p1 groups on exercises that p2 never plays have
  no advanced partner (same_day: 13 of 42; next_day: 10 of 28). They enter the descriptive
  numbers but not the gap.

## Method

`pianolens.features.takes` unchanged (as in F-07): `decompose_takes` (channels timing =
`dev_beats`, tempo, velocity, articulation; takes centered) and `take_structure` (ridge on the
score basis, 4-bar blocks, out-of-fold R², pairwise half-sum / half-difference). F-03 tempo
curves per take; median beat period per take for ms conversion (beat = quarter note, 2/4).

Per group: `all` (all k takes: ICC(3,1), take-specific SD), `same` (a1, a2) and `cross` (a1, b1).

## Hypotheses and falsification (primary channel: timing)

Primary quantity per group: **gap = R²(diff)[cross] - R²(diff)[same]**. It is the F-07 audit
contrast: can the score basis explain between-pianist differences better than one pianist's
take-to-take changes? Mean over groups, 95% cluster bootstrap over pianist-days (2,000
replicates, seed 0); a t-interval over cluster means is reported alongside.

- **A (advanced, same_day):** supported if the whole CI of the mean gap lies above 0; falsified
  if it lies wholly below 0; otherwise inconclusive.
- **B (beginner p3, next_day):** same rule.
- Secondary (not in the verdict): advanced next_day (few clusters, so the t-interval governs);
  the same rule per pianist; R²(sum) same vs cross; the other channels.

Descriptive (asked by the brief, no verdict): take-to-take timing SD (`sd_specific`, beats and
ms) and ICC(3,1) for timing, per level and per pianist and window; the same numbers for the
cross pairs (between-pianist SD and ICC).

**Reachability (R-09 lesson).** The F-07 cross-control CI (0.038 +- 0.008 over 411 pieces)
implies a per-group SD of the gap of about 0.08. For about 76 advanced same-day groups (32
clusters) and 147 beginner groups (43 clusters), the expected half-width is about 0.02 or more
(clustering widens it). So "supported" is reachable if the gap is near F-07's 0.038. At a true
gap of 0, "falsified" has a chance of about 2.5%, so it is reachable only if the true gap is
negative. "Inconclusive" is the expected outcome for a true gap below about 0.02.

**Not claimed.** One beginner and two advanced pianists: no inference about skill levels. The
beginner and advanced arms use different windows (next day vs same day), so they are not
compared as a skill effect. Hanon is a near-periodic exercise: the score basis mainly carries
metrical position and melodic direction, so R² values are not comparable with F-07's
repertoire numbers.

## Baselines

Trivial: predict the mean (R² = 0). Control: the cross-pianist pair. No leave-piece-out: this
is not a quality prediction. R² is out-of-fold within a take by written-bar blocks.

## Command

```
uv run python scripts/build_rach3_hanon_takes.py
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 uv run python experiments/2026-09-28-BL-16-rach3-takes/run.py --window same_day --workers 6
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 uv run python experiments/2026-09-28-BL-16-rach3-takes/run.py --window next_day --workers 6
uv run python experiments/2026-09-28-BL-16-rach3-takes/analyze.py
```

## Run record

- Pre-registration above: SHA-256 `f9336acc00ccc7b83e37dfc21537b8eecab604a22364c3a0264a566aee5c2c54`
  (the first 113 lines; written 2026-09-28 before `run.py` was run, at about 00:22Z).
- Code: git HEAD `3af124d`, BL-16 files uncommitted. SHA-256 prefixes at run time:
  `rach3_takes.py` ed08fd13dfeb6be8, `build_rach3_hanon_takes.py` 7211551b770bcc37,
  `takes.py` 1c2d2d4316ecfa2b, `shaping.py` 01dfd3c7ff03e16d (uncommitted edits by other
  tickets were in the working tree), `run.py` bab0f9ac89051f03. Seed 0 (cross partner, bootstrap).
- Data: Rach3 commit a9519492 (Hanon subset); takes rebuilt by the build script in about 20 min.
- Commands as in "Command" (BLAS threads pinned to 1, 6 workers): same_day 32 s (89 groups,
  all ok), next_day 68 s (192 groups, all ok).
- Changes after registration, disclosed:
  1. `analyze.py`: after the header was hashed, and before any run, it was changed to read
     both windows (`groups_<window>.jsonl`) and write `rows_<window>.csv`. No statistic changed.
  2. The per-cross-partner breakdown and the post-run gap SD below were computed after the
     results were seen. They are descriptive.

## Results

Timing channel (`dev_beats`). Means over groups; 95% cluster bootstrap over pianist-days
[percentile], t-interval over cluster means in parentheses. Full output: `artifacts/analysis.txt`.

### Take-to-take timing variation and ICC (descriptive)

| Arm | Groups (pianist-days) | Take-specific SD, beats | Take-specific SD, ms | ICC(3,1) same pianist | ICC(3,1) cross pair |
|---|---|---|---|---|---|
| Advanced, same day | 89 (32) | 0.011 [0.011, 0.012] | 7.5 [6.7, 8.3] | 0.31 [0.27, 0.34] | 0.12 [0.11, 0.15] |
| p1 | 42 (13) | 0.010 | 6.1 | 0.35 | 0.13 |
| p2 | 47 (19) | 0.013 | 8.7 | 0.27 | 0.12 |
| Beginner p3, next day | 147 (43) | 0.013 [0.012, 0.014] | 11.3 [10.9, 11.8] | 0.18 [0.16, 0.20] | 0.06 [0.04, 0.07] |
| Advanced, next day | 45 (9) | 0.010 [0.009, 0.013] | 7.0 [6.2, 8.2] | 0.32 [0.28, 0.35] | 0.08 [0.04, 0.14] |

The SD in ms scales with the beat period: p3 plays slower (median take 48 s against 36-37 s),
so the SD in beats differs less than the SD in ms. For the pair half-difference, the take-specific SD of a
cross pair is about the same as a same-pianist pair (0.013 vs 0.011 beats advanced, 0.013 vs
0.013 p3). Between-pianist differences are not larger in size, but they are more structured
(next table), and they repeat less (lower cross ICC).

### Primary: R² of the pair half-difference, same pianist vs cross pianist

| Arm | Groups with a cross pair (clusters) | R²(diff) same | R²(diff) cross | **gap (cross - same)** | Groups gap > 0 |
|---|---|---|---|---|---|
| **A: advanced, same day** | 76 (31) | 0.028 [0.013, 0.043] | 0.058 [0.040, 0.073] | **0.036 [0.013, 0.056]** (t [-0.003, 0.048]) | 49 of 76 |
| p1 (partner p2) | 29 (12) | 0.049 [0.026, 0.072] | 0.044 [0.018, 0.060] | 0.003 [-0.037, 0.028] | 16 of 29 |
| p2 (partner p1) | 47 (19) | 0.009 [-0.001, 0.021] | 0.066 [0.041, 0.086] | 0.057 [0.030, 0.076] | 33 of 47 |
| **B: beginner p3, next day** | 147 (43) | -0.000 [-0.006, 0.005] | 0.051 [0.040, 0.063] | **0.051 [0.039, 0.065]** (t [0.039, 0.078]) | 106 of 147 |
| p3 with partner p1 / p2 | 93 / 54 | | | 0.043 / 0.065 | |
| Advanced, next day (secondary) | 35 (9) | 0.030 [0.008, 0.045] | 0.059 [0.025, 0.095] | 0.027 [-0.020, 0.070] (t [-0.011, 0.059]) | 19 of 35 |

R²(sum), same vs cross (the F-07 pre-registered contrast, now known to be uninformative):
advanced same day 0.148 vs 0.146; p3 next day 0.063 vs 0.052. So as in F-07, the consistent
part is score-typical timing that any two players share.

Secondary channels, gap in R²(diff) (cross - same):
- articulation: advanced same day 0.082 [0.062, 0.106]; p3 0.073 [0.058, 0.089].
- velocity: advanced same day 0.053 [0.031, 0.074]; p3 0.097 [0.081, 0.112].
- smooth tempo: R² is strongly negative in every cell (-0.07 to -0.19). The ridge basis
  cannot predict a smooth curve out of fold here, so the tempo channel is uninformative (as in
  F-07).
- Same-pianist R²(diff) for articulation and velocity is at or below 0 in both arms: take-to-take
  changes in touch are unstructured by the score basis.

Reachability, checked after the run: the per-group SD of the timing gap was 0.094 (advanced same
day) and 0.081 (p3), close to the 0.08 assumed. The intervals are informative.

## Verdict (Provisional)

- **A (advanced, same day): supported by the pre-registered rule, weakly.** The bootstrap CI of
  the gap, [0.013, 0.056], lies above 0. The t-interval over pianist-day means just reaches 0
  ([-0.003, 0.048]). The effect comes from p2 (0.057 [0.030, 0.076]). For p1 it is absent
  (0.003 [-0.037, 0.028]): p1's same-day takes differ from each other about as structurally
  (R²(diff) 0.049) as p1 and p2 differ.
- **B (beginner p3, next day): supported.** Gap 0.051 [0.039, 0.065], t [0.039, 0.078].
  106 of 147 groups are positive. p3's day-to-day timing changes are not explained by the score
  at all (R²(diff) -0.000 [-0.006, 0.005]). The differences between p3 and an advanced pianist
  are explained (0.051).
- In plain terms: in practice sessions, most of a player's take-to-take timing change looks like
  noise to the score basis, as it did in F-07 for concert recordings (gap 0.038 there). There is
  one clear exception, p1, among the three players. The beginner arm is next-day, not same-day,
  because the beginner never repeats an exercise within a day after QC.
- Take-to-take timing SD: about 0.011 beats (7.5 ms) same-day for the advanced players, and 0.013
  beats (11 ms) next-day for the beginner. Timing ICC(3,1): 0.31 advanced, 0.18 beginner. A
  single take repeats only a minority of its residual timing, less than in F-07 (0.60). That
  fits Hanon, which has little score-driven timing shape to repeat.

## Threats to validity

- **Three pianists.** The bootstrap resamples pianist-days, not pianists. The results describe
  these three players; nothing here generalises to beginners or advanced players. The
  pianist-level heterogeneity (p1 vs p2) is as large as the effect.
- **The beginner's cross partner is always advanced.** Part of B's gap may reflect a skill-level
  difference, not a player difference. No second beginner exists to separate the two.
- **Windows differ.** A is same-day, B is next-day, so the beginner and advanced gaps are not
  like-for-like. The advanced next-day secondary (0.027 [-0.020, 0.070], 9 clusters) is too
  small to settle it.
- **Selection by QC.** 44% of kept candidate takes (889 of 2,038) fail QC, mostly for a pause over 8x the median
  onset time (often at the bar-14 turnaround). The takes kept are the steadier passes. That
  should shrink take-to-take noise, more for p3 (49% pass) than for p1 (67%).
- **p1 files.** Each p1 file is usually one take, so "same day" for p1 means different sessions
  on the same day, possibly hours apart. p2's same-day takes are mostly within one session. This
  may explain part of the p1 vs p2 difference.
- **Hanon's score basis is thin.** It carries metre, register and melodic direction, and no
  markings or phrases. The R² values are low and are not comparable with F-07's.
- **Instrument not stated** (keyboard MIDI, tagged `sensor`); velocity curves may differ by
  instrument between pianists. That would inflate cross-pair velocity differences; timing is
  not affected.
- **Alignment.** DP matches agree with parangonar on 99.5% of notes (24 takes). Exact-pitch
  matching means wrong notes are unpaired, not mis-timed.
- **Part II and transposed practice are not covered.** p1 matched only 44% of its session notes.

## Audit (2026-09-28)

Auditor: eval-auditor. Verdict: **Confirmed with caveats.** A and B are supported by the
pre-registered rule, and the numbers reproduce. But arm A's gap is not shown to be a
*pianist* effect: a same-pianist pair taken on different days is about as structured as a
cross-pianist pair. Arm B holds that control, but its cross partner is always an advanced,
faster player. The claim is narrowed below. Audit scripts and outputs are in
`artifacts/audit/` (`variants.py`, `summ.py`, `absvar.py`, `var_*.csv`).

### Pre-registration

- The first 113 lines hash to `f9336acc…2c54`. They are identical to the data-engineer's
  `Write` of this README at 00:22:09Z (subagent transcript `agent-a1d67a944b65494fc`). The
  runs started at 00:22:26Z.
- Before the header was written, only counts and alignment checks ran:
  - the same-day feasibility counts (00:17:40Z);
  - the job counts (00:18Z);
  - the smoke run (00:18:19Z). It printed only the per-channel n (224 / 233 / 464 / 464) and
    the key names. No R², ICC or SD was printed;
  - the parangonar check.
- The next-day beginner arm was added to `run.py` at 00:18:02Z, before the header, and it is in
  the header. The pivot was pre-registered.
- The `TakeQC` thresholds are in the first `Write` of `rach3_takes.py` (23:36:37Z), before the
  first build. They never changed.
- The `analyze.py` change after the hash: I diffed the original `Write` (00:07:22Z) against the
  current file. The diff is only I/O (two windows, file names) and a line split. `boot()` and
  every statistic are unchanged, as disclosed.
- The partner breakdown and the gap SD are post hoc, as disclosed. They are descriptive only.

### Reproduction

- `analyze.py`, run on copies of the artifacts: `analysis.txt` and both `rows_*.csv` are
  byte-identical.
- I re-scored every same-day pair from the built takes with the scratch copy of `run.py`.
  Maximum absolute difference in R²(diff) against the artifacts: 0 (same and cross).
- The SHA-256 prefixes of `run.py`, `rach3_takes.py`, `build_rach3_hanon_takes.py`,
  `takes.py` and `shaping.py` match the run record. `analyze.py` is now `72fed98262e1251c`
  (not recorded in the run record).
- `tests/data/test_rach3_takes.py`: 5 passed. Ruff is clean on the BL-16 files.

### Findings

1. **Deviation: "the first two takes in time order" is not what the code does on days with
   several files.**
   - `session` is `'0'` for every take: Rach3 has one sitting per day in this subset.
   - The sort `(pianist, day, session, t0_sec)` therefore orders a day's takes by onset
     *within their own file*, not by file order (the `NN` in the file name).
   - Affected groups: same-day p1 24 of 42 and p2 3 of 47; next-day p1 2 and p2 2. p3 is
     unaffected (one file per day).
   - Re-run in file order (`variants.py order_*`): A 0.034 [0.011, 0.057] (t [-0.000, 0.070]);
     p1 0.019 [-0.021, 0.075]; p2 0.043 [0.019, 0.061]; B 0.052 [0.037, 0.066]. The verdict does
     not change.
2. **Threat "p1 separate sessions, possibly hours apart" is contradicted by the dataset naming.**
   - The Rach3 README defines the digit after the date as the sitting number. It is 0 for every
     file, so all same-day takes are from one sitting.
   - p1 saves most passes as separate files within that sitting: 33 of 42 same-day (a1, a2)
     pairs are in different files, against 2 of 47 for p2.
   - So session structure does not explain p1 against p2.
3. **Time-separation confound in arm A (the main caveat).**
   - The cross partner b1 is a random take from any day. The same-pianist pair (a1, a2) is from
     one sitting. The gap therefore mixes "different pianist" with "different day".
   - Control (`variants.py otherday_*`): c1 = a random QC take of the same exercise by the
     *same* pianist on another day. The cross side is averaged over 6 partner draws.

     | | same pair | same pianist, other day (c1) | cross (6 partners) | cross - c1 |
     |---|---|---|---|---|
     | Advanced, same day | 0.028 | 0.046 | 0.061 | 0.011 [-0.015, 0.034] (t [-0.026, 0.024]) |
     | p1 | 0.049 | 0.055 | 0.050 | -0.011 [-0.059, 0.028] |
     | p2 | 0.009 | 0.038 | 0.068 | 0.024 [-0.005, 0.051] |
     | p3, next day | -0.000 | 0.017 | 0.058 | 0.041 [0.028, 0.052] (t [0.027, 0.057]) |

   - For the advanced players, a pair of the same pianist's takes on different days is nearly as
     structured as a cross-pianist pair. A shows that **same-sitting** changes are less
     structured than **across-day** changes. It does not show that they are less structured than
     *between-pianist* changes.
   - For p3 the contrast survives the control.
4. **Noise-level asymmetry in R² explains part of p1's "absent" effect.**
   - For p1 groups, the cross half-difference has 1.7 times the variance of the same pair
     (median; p2's takes are noisier). This deflates the cross R².
   - Explained variance in absolute units (R² times variance): the p1 gap is positive,
     +0.015e-4 beats² [-0.021e-4, 0.039e-4], against the R² gap of 0.003. p2 and p3 have a
     ratio near 1.
   - p1 is still not significant. "The effect is absent for p1" should read "not shown for p1".
5. **Arm B's confounds.**
   - The cross partner is always advanced and faster: the median |log duration ratio| of a
     cross pair is 0.28, against 0.02 for p3's next-day pairs.
   - |log duration ratio| predicts R²(diff): slope 0.07 [0.02, 0.12] (OLS, clusters =
     pianist-days).
   - Adjusted for it, cross minus same is still 0.039 [0.025, 0.053] for p3, and 0.028
     [0.007, 0.049] for the advanced players.
   - Skill level and player identity cannot be separated with one beginner. The p3-to-advanced
     cross R²(diff) (0.051) is no higher than the advanced-to-advanced one (0.058). So nothing
     suggests a level effect, but that is not evidence against one.
6. **The bootstrap unit.**
   - Pianist-days nest in pianists. For "between-pianist" claims the pianist is the real unit:
     A has 2 pianists with opposite results (0.003 / 0.057; unweighted mean 0.030, no interval
     possible), and B has 1.
   - The bootstrap CI describes these players' days, as the README says. The t-interval touching
     0 in A is the honest summary for A.
7. **Robustness that holds.**
   - Partner draw: over 6 seeds, the A gap is 0.036-0.048 and the B gap 0.051-0.067.
   - QC without the pause rule (142 / 379 groups): A 0.032 [0.009, 0.051] (t [0.003, 0.045]),
     B 0.064 [0.055, 0.073].
   - Stricter pause rule, at most 4x (55 / 118 groups): A 0.043 [0.017, 0.066], B 0.059
     [0.042, 0.078].
   - So QC selection does not drive the gap, and same-pianist R²(diff) stays at or below 0.016
     for p2 and p3 under every QC.
8. **Segmentation.**
   - No kept takes overlap within a file.
   - Medians for QC takes: note match 0.99-1.00, insertions 0.004-0.013 per score note.
   - The 99.5% parangonar agreement (24 takes) is recorded in the transcript output. I did not
     rerun it.
   - Exact-pitch matching leaves wrong notes unpaired, so timing is taken from correct notes
     only.
   - Durations of QC takes vary up to 4.9x within a pianist and exercise (median ratio 1.7).
     Practice tempo varies a lot, which is part of finding 5.
9. **Reachability.** The pre-registered reasoning holds, and the post-run gap SDs (0.094 /
   0.081) match the assumed value. The branches were reachable.

### What the evidence supports

- **Supported:** within one practice sitting, a player's take-to-take timing changes are
  close to unstructured by the score basis.
  - R²(diff): p2 0.009, p3 next day -0.000.
  - p1 is the exception at 0.049 (0.038 in file order).
  - These changes are less structured than changes across days by the same player (p2 0.038,
    p3 0.017) or by another player (0.05-0.07).
- **Not shown:** that advanced players' same-day variation is less structured than
  *between-pianist* differences specifically. The same-pianist other-day control removes most
  of the gap (0.011 [-0.015, 0.034]).
- **B:** holds against the other-day control for one beginner. It is confounded with skill
  level and tempo, and adjusting for tempo leaves 0.039.
- **For tier B noise estimation:** same-sitting takes (or next-day takes for the beginner) are
  a defensible noise estimate for timing. The SD is about 0.011-0.013 beats (7.5 ms advanced,
  11 ms p3).
  - Takes from different days are not. They carry structured drift, so pooling takes across
    days would count real change as noise.
  - p1 shows that some players' same-sitting changes are structured. Check this per user
    (O-01).

### Required fixes (text only)

1. Verdict A: "supported by the pre-registered rule; the gap is not shown to be a pianist
   effect. A same-pianist other-day pair gives 0.011 [-0.015, 0.034] against the cross pair."
   Replace "less structured than between-pianist differences" with "less structured than
   across-day or between-pianist changes".
2. Disclose deviation 1 (time order across files) in the run record, with the file-order
   numbers.
3. Remove the "p1 separate sessions" threat. Replace it with "p1 saves passes as separate files
   within one sitting".
4. p1: "not shown", not "absent". Add the noise-asymmetry note (variance ratio 1.7).
5. Add to the Threats for B: the tempo difference to the partner (median |log ratio| 0.28), and
   the tempo-adjusted 0.039.
6. Record the `analyze.py` hash (`72fed98262e1251c`).

## Post-audit corrections (lead, 2026-09-28)

1. **Verdict A reworded.** Same-sitting timing changes are less structured than changes across
   days. That arm A shows they are less structured than *between-pianist* differences is **not
   shown**: against a same-pianist-other-day control the gap is 0.011 [−0.015, 0.034].
2. **Time-order deviation.** Takes were ordered by their onset within each file, not by file (NN)
   order, because the Rach3 `session` digit is always 0. Re-run in file order: A 0.034, B 0.052.
   Verdict unchanged.
3. **The p1 "separate sessions" threat is withdrawn.** Every file comes from one sitting per day;
   p1 simply saves each pass as its own file.
4. **p1:** the gap is "not shown", not "absent". Its cross pairs have 1.7 times the variance of its
   same-pianist pairs (p2 is noisier).
5. **Arm B threat:** the partner is always a faster, advanced player. Adjusted for tempo ratio, the
   gap is 0.039 [0.025, 0.053]. Skill and player identity cannot be separated with one beginner.
6. `analyze.py` hash: `72fed98262e1251c`.

**What survives:** same-sitting timing changes are close to unstructured by the score, with SD
about 0.011-0.013 beats (7.5 ms advanced, 11 ms beginner). That makes them a defensible noise
estimate. Changes across days are not noise; they carry structured drift.
