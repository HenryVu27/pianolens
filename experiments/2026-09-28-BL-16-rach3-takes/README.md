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
