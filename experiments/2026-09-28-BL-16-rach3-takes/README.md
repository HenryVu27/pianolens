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
