# Practice report validation (F-08, F-08b)

What the practice report's tiers were checked against, with the numbers measured in this repo.
The report code is `src/pianolens/report/`. Tiers follow DECISIONS 2026-09-28 (after F-06):
"notable" means beyond the expert 95th percentile and "strong" beyond the 99th, so about 5% and 1%
of expert bars by construction.

## 1. Timing flags and reference provenance (F-08b)

**Question.** PianoCoRe references are nearly all transcriptions (156,229 transcribed vs 978
Disklavier rows). In F-08 sample (a), a Disklavier target (SunMeiting08, Op. 10 No. 3) was flagged
on about 20% of bars. Are Disklavier targets over-flagged against transcribed references?

**Method.** `scripts/check_timing_provenance_f08b.py` writes to `data/interim/timing_provenance_f08b/`.
- **Pairs:** 64 of D-10's 65 same-performance pairs. Each pair is an ASAP Disklavier recording and
  an Aria-AMT or Transkun transcription of the same recording; 43 pieces, 53 distinct Disklavier
  performances. The Haydn pair is skipped because it has no canonical piece id.
- **Scoring:** both versions are aligned to the ASAP score with `align_performance` and scored with
  the report's own code (`_interpretation_section` at both tiers, and `timing_noise_bars`). Both
  use the same PianoCoRe references, with both versions of the performance left out.
- **Baselines, reference as target (leave-one-out):** up to 20 random transcribed references per
  piece (860 in total) and all Disklavier references (329, across 38 pieces).
- **Rate:** the share of tier-defined bars that are notable-or-strong, and the share that are strong.

| Targets | Tempo notable+ | Tempo strong | Timing notable+ | Timing strong |
|---|---|---|---|---|
| Pairs, Disklavier version (64) | 4.3% | 0.9% | 4.2% | 1.2% |
| Pairs, transcribed version (64) | 4.5% | 1.0% | 4.7% | 1.3% |
| PianoCoRe Disklavier refs as targets (329) | 3.5% | 0.6% | 3.6% | 0.8% |
| PianoCoRe transcribed refs as targets (860) | 5.4% | 1.5% | 5.2% | 1.4% |

Paired difference, Disklavier minus transcribed, with bootstrap 95% CIs over pairs:

| Tier | Difference (points) | 95% CI |
|---|---|---|
| Tempo notable+ | -0.2 | [-0.5, +0.1] |
| Tempo strong | -0.1 | [-0.3, +0.0] |
| Timing notable+ | -0.5 | [-1.0, +0.0] |
| Timing strong | -0.1 | [-0.4, +0.3] |

The flagged bars overlap between the two versions with Jaccard 0.74 for tempo and 0.51 for timing.

**Reading.**
- Disklavier targets are not over-flagged. If anything, transcription adds flags.
- On expert playing the tiers are near nominal: strong is 0.9-1.2%.
- Sample (a)'s high rate comes from the performance itself. SunMeiting08 is flagged on 23% (tempo)
  and 21% (timing) of bars as a Disklavier recording, and 29% and 32% as a transcription.
- No correction was added, since there is no measured mismatch to fix.

**Decision.** Timing flags are no longer "experimental" with respect to reference provenance.
- Control measures remain unvalidated as skill measures (D-10 / R-09).
- Velocity stays low-confidence when the input or the references are transcribed.

## 2. Recurring errors across takes (F-08b)

**Calibration.** `scripts/calibrate_recurring_f08b.py` writes
`data/interim/reports/calibration/recurring_{summary.json,bars.parquet}`.
- **Expert pseudo-takes:** 30 random ASAP pieces, with 3 pianists on one repeat path treated as 3
  takes. Their slips are independent, so any recurrence is a checker or score artefact.
- **Error key per bar:** wrong pitch (score note, played pitch), missed (score note), or extra
  (pitch).
- **Expert filter:** drop keys the checker also reports for another expert recording of the same
  score. Tested on 15 pieces with at least 5 performances; median 6 other experts.

Share of expert bars that each rule would mark strong:

| Rule | 2 takes, both | 3 takes, at least 2 |
|---|---|---|
| Any kind, no filter | 24% | 31% |
| Wrong pitch only, no filter | 3.3% | 4.2% |
| Any kind, filter | 4.1% | 9.9% |
| Wrong + extra, filter | 1.6% | 3.8% |
| Wrong + missed, filter | 2.8% | 7.1% |
| Wrong pitch only, filter (all other experts) | 0.18% | 0.51% |
| Wrong pitch only, filter (2 experts) | 0.5% | 1.0% |

**Implemented.** Constants: `calibration.RECURRING_KINDS = ("wrong_pitch",)`,
`RECURRING_MIN_TAKES = 2`, `RECURRING_MIN_EXPERTS = 2`.
- A recurring error is the same wrong pitch at the same score note in at least 2 takes, not reported
  for any expert recording of that score.
- It promotes its bar to "strong" only when at least 2 expert recordings were checked. Otherwise it
  is listed and not promoted.
- `report_from_files` loads up to 6 ASAP performances of the piece as the expert check when takes
  are given. They can also be passed as `correctness_reference_midis`; `same_score_refs` count too.
- Missed and extra recurrences are never promoted, because missed notes are reported per bar (F-01).

**Caveat.** The pseudo-takes are different pianists. One player's habits recur more across their own
takes, so O-01 is the real test.

**"What to practise" order:**
1. tier;
2. within a tier: correctness, then control, then shaping / interpretation;
3. recurring errors first;
4. then magnitude.

## 3. Sample reports

`scripts/build_report_samples_f08.py`, about 80 s.

- **(a) SunMeiting08:** error rate 7.0%; 5 correctness bars and 16 timing bars tiered.
- **(c) (a) plus 5% D-08 mistakes and 30 ms jitter:**
  - 56 bars had mistakes injected;
  - recall is 1.0 for any error, and 0.91 for more errors than in (a);
  - 2 bars gain errors without any injection;
  - timing noise goes from 67.7 to 72.7 ms.
- **(d) deadpan:** every tempo and velocity window is "too flat" at strong; tempo typicality is at
  most 0.006.
- **(e) 3 synthetic takes of Op. 10 No. 4** (Op. 10 No. 3 has only one ASAP performance):
  - Base: a note-perfect ASAP performance. Re-checked, it still shows 0 wrong, 40 missed and 1
    extra note.
  - Each take gets its own 2% D-08 slips (15 wrong, 15 extra, 14 missed, 10 ms jitter), plus Bb5
    for A5 in bar 30. 6 ASAP experts were checked.
  - Bar 30 is the only recurring bar: strong, in 3 of 3 takes, and the first practise item.
  - No bar with a random slip is promoted.
  - Of the main take's other 39 flagged bars, 38 are untiered and 1 (bar 66, 3 wrong notes) is
    strong under the single-take rule.
