# Practice report validation (F-08, F-08b, F-08c)

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

## 4. Per-bar expert check for single-take correctness (F-08c)

**Question.** A single-take report ranks a bar's flagged notes against global expert limits. Some
bars are flagged for every expert as well: the score, the edition or the checker disagrees with
what pianists play there. In A-01, a practise item in Op. 64 No. 2 sat in such bars. Can the
report recognise these bars without losing real mistakes?

**Rule** (`build.expert_bar_limits`, constants `calibration.EXPERT_CHECK_*`).
- **Experts:** performances of the same score with the same capture method as the target.
  Key-sensor input uses ASAP (Disklavier) performances, or same-score references when there are
  enough. Transcribed input uses PianoCoRe transcriptions, from the same transcriber family when it
  is known, as in the A-01 floor. Up to 15 are used; suspect alignments (match ratio below 0.8) are
  left out.
- **Per bar:** bars are keyed by label, so experts on another repeat path still line up. With at
  least 5 experts at a bar, a quantity must exceed both the global limit and the experts' per-bar
  quantile: the 80th percentile for "notable", the 99th for "strong". The two quantities are the
  wrong-pitch count and missed (+ extra) notes per score note, as before.
- **Output:** a bar within the expert range is not ranked. The timeline and the correctness card
  say it "matches expert transcriptions here (likely score/edition artefact)", or "expert
  recordings" for key-sensor experts. A strong bar that is only notable against the experts is
  down-tiered and says so. With fewer than 5 experts the bar keeps its global tier, and the header
  says no per-bar check was possible.

**Extra notes on transcribed input** (A-01, `rules/audio.md`). Extra notes no longer count
towards the tier of transcribed input. They stay in the timeline, marked low confidence, and never
become practise items. Missed notes are then judged against missed-only limits from the same F-08
expert set: 0.158 per note (95th percentile) and 0.286 (99th).

**Calibration.** `scripts/calibrate_expert_check_f08c.py` (about 40 minutes on a loaded machine,
10 workers; `--from-cache` re-scores in seconds). Outputs are in
`data/interim/reports/calibration/f08c_*`.
- **Key-sensor.** The F-08 expert set is the clean D-08 copies. 40 of its 100 performances
  (28 pieces) have at least 5 other ASAP performances, which serve as experts, leaving the
  source performance out. 354 ASAP performances were aligned; none was suspect.
- **Recall.** The same 40 performances with D-08 mistakes injected at rates 0.02, 0.05 and 0.10.
  A bar with an injected mistake counts as caught when it is tiered.
- **Transcribed.** The 150 A-01 floor transcriptions: 5 Chopin pieces, 15 per piece and
  transcriber family, with the same seeded draw. Each is scored against the other 14 of its piece
  and family (leave-one-out), with extras not counted.

Share of expert bars that are notable-or-strong / strong:

| Experts | Bars | Global limits only | Per-bar q80 / q99 (chosen) | Per-bar q95 / q99 |
|---|---|---|---|---|
| Key-sensor, clean D-08 copies | 5,482 | 6.8% / 1.7% | 3.7% / 0.67% | 2.8% / 0.67% |
| Transcribed, A-01 floor, extras not counted | 17,370 | 11.8% / 3.0% | 5.3% / 1.4% | 3.7% / 1.4% |
| of which Transkun V2 | | 9.4% / 1.9% | 3.0% / 0.58% | 2.1% / 0.58% |
| of which Aria-AMT | | 14.2% / 4.1% | 7.5% / 2.3% | 5.2% / 2.3% |

Bars with injected mistakes that are tiered (notable-or-strong / strong):

| D-08 rate | Bars with injected mistakes | Global only | q80 / q99 | q95 / q99 |
|---|---|---|---|---|
| 0.02 | 1,712 | 13.8% / 3.3% | 11.0% / 2.2% | 9.1% / 2.2% |
| 0.05 | 3,242 | 18.1% / 3.7% | 15.5% / 2.6% | 13.5% / 2.6% |
| 0.10 | 4,360 | 28.2% / 6.9% | 26.2% / 5.7% | 23.9% / 5.7% |

At rate 0.05, 85.5% of the injected bars tiered without the check stay tiered (74.9% with q95).

**Reading.**
- **Why q80.** A bar must exceed both limits, so the joint rate is below either limit alone.
  The per-bar 80th percentile keeps notable nearest the nominal 5% (3.7% key-sensor, 5.3%
  transcribed) and loses the fewest injected bars. The 95th percentile, the ticket's example,
  undershoots on both (2.8%, 3.7%). The 50th percentile was also tried: 4.5% key-sensor, but
  6.8% transcribed.
- **Recall.** The recall numbers are low in absolute terms because a single wrong note is never
  tiered by design (F-08). The check costs about 2-3 points of recall at every rate.
- **Strong on transcribed input stays above 1%** (1.4%; Aria-AMT 2.3%). With 14 experts, the
  per-bar 99th percentile is close to the per-bar maximum. A target that is the worst of 15 at a
  bar is then strong, which happens more often than 1 in 100 bars. More references per bar, or a
  larger per-bar margin, would be needed; this is not fixed here.
- **Caveats.**
  - The key-sensor calibration covers only pieces with 6 or more ASAP performances, so 40 of 100.
  - The transcribed calibration covers 5 Chopin pieces.
  - Neither covers phone audio: the takes' extra-note problem is handled by the extras rule, not
    by this check.

**Sample reports** (section 3), regenerated.
- (a), (c) and (d) (Op. 10 No. 3) have no per-bar check. The piece has one ASAP performance, and
  it is the target's own source. Their practise items are unchanged, and (c) still flags every
  injected bar (bar recall 1.0 for any error, 0.91 for more errors than (a)).
- (b) is checked against the 21 other Vienna pianists (sensor). It has no tiered correctness bar.
- (e) is checked against 15 ASAP experts. Bar 66 (3 injected wrong notes) is confirmed strong,
  bar 30 is still the only recurring bar and the first practise item, and no slip is promoted.

**Henry's 5 phone takes** (A-01 reports, both transcribers; aggregate only, personal data).
- Checked against the 15 floor transcriptions of the same piece and transcriber.
- Tiered correctness bars per report: before 6-76, after 3-30. Strong bars: before 0-30, after 0-2.
- In the old top-3 lists, 25 of 30 practise items were correctness items, and in 19 of them
  extra notes outnumbered wrong plus missed notes. Now 15 of 30 are correctness items, and none
  counts extra notes.
- Op. 64 No. 2, bar 78 (5 wrong notes, previously strong): 14 of 15 Transkun expert transcriptions
  show 4 or more wrong notes there (median 5). It is now suppressed as a likely edition artefact.
  Bar 79 (2 wrong notes, experts at most 1) stays notable. The new first item is bar 84 (4 wrong
  notes, experts 0), confirmed strong.
- Transkun vs Aria-AMT agreement on correctness bars falls on two takes (Jaccard 0.24 and 0.17,
  from 0.75 and 0.68), because only 3-15 bars remain tiered.
