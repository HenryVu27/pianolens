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

## 5. BL-18: strong correctness tier on transcribed input (pre-registration)

**Problem** (section 4). On transcribed input the per-bar check leaves "strong" above its nominal
1% of expert bars: 1.4% on the A-01 floor (Transkun V2 0.58%, Aria-AMT 2.3%). With 14-15 experts,
the linearly interpolated per-bar 99th percentile lies between the two largest expert values, so
a target that only *equals* a unique expert maximum is already strong.

**Candidate rules** (strong only; notable keeps the per-bar q80 and the global limits; every rule
still requires the global limit as well):
- **R0** (current): strong above the per-bar q99 (linear interpolation), at least 5 experts.
- **R1(k)**, finite-sample order statistic: with n experts at a bar, the per-bar strong limit is
  the order statistic of rank r = ceil(0.99 (n + 1)), the smallest rank for which "above it"
  has probability at most 1% for an exchangeable target. When r > n (n < 99, always here), the
  limit is the per-bar maximum plus k units, k in {0, 1}; a unit is 1 note for the wrong-pitch
  count and 1 / (graded score notes of the target bar) for missed notes per note. k = 0 means
  "more than every expert".
- **R2**, per-transcriber-family global limits: for transcribed input, the global q95 / q99
  limits (wrong-pitch count, missed per note) are re-estimated on the family's expert
  transcriptions (A-01 floor bars, extras not counted), and the per-bar q80 / q99 check is kept.
  Needs the target's transcriber family.
- **R1(0) + R2** together.
- **R3**, more references: R0 and R1(0) with 30 same-family experts instead of 15. Reported on
  the held-out pieces only, as information: many pieces, including 4 of Henry's 5, have fewer
  than 30 Transkun transcriptions, so R3 cannot be the app's rule.

**Where the rule applies.** Transcribed input only (experts transcribed). Key-sensor input keeps
R0: its strong rate is 0.67% (section 4). What R1 would do on the key-sensor cache is reported as
information.

**Data.**
- *Dev*: the 150 A-01 floor transcriptions, leave-one-out within piece and family (14 experts),
  as in section 4. These were already seen at F-08c.
- *Held-out targets*, never used before:
  - *T1*, Henry's 5 pieces: up to 10 PianoCoRe transcriptions per piece and family that are not
    in the floor draw (seed 18), checked against the 15 cached floor experts of their family.
  - *T2*, 6 new pieces: seeded draw (seed 18) among PianoCoRe pieces with at least 45 Transkun
    V2 and 45 Aria-AMT transcriptions and a score.mxl, excluding Henry's 5. Per piece and family:
    30 experts and 10 targets, disjoint, seeded; the first 15 experts in draw order are the
    15-expert set.
  - Alignments with match ratio below 0.8 are dropped, as in the report.
- *Injected mistakes*: one D-08 copy (`perturb`, `MistakeSpec(rate=0.05)`, default mix, seed 0,
  `require_exact_timing=False`) of every held-out target. An injected bar is a bar with an
  injected wrong pitch or missed note (extras are not counted on transcribed input).

**Metrics.** Per family and pooled, on bars with graded notes:
- false notable-or-strong and false strong rate of the clean held-out targets;
- detection: share of injected bars tiered notable-or-strong, and share tiered strong.
Intervals: bootstrap 95% CI by piece (2,000 resamples, seed 0) and a t-interval over pieces.

**Selection (dev only).** In this order, the first candidate whose dev strong rate is at most
1.0% in both families is chosen: R1(0), R2, R1(0) + R2, R1(1). Ties cannot occur.

**Acceptance (held-out, T1 and T2 together).**
- A1: the chosen rule's false-strong rate is at most 1.25% (point estimate) in each family.
- A2: its false notable-or-strong rate is not higher than R0's in either family.
- A3: its notable-or-strong detection of injected bars is at most 2.0 points below R0's in each
  family. The drop in strong detection is reported (some drop is expected and is the point).
- PASS: A1-A3 in both families. PARTIAL: in one family. FAIL: in neither.

**Reachability.** A1 is decided by the point estimate. R1(0) cannot raise any rate and cannot
move a bar out of notable, so A2 and A3 hold for it by construction; its risk is A1 (still hot)
or an excessive drop in strong detection. R2 can fail A3, because it raises the notable limit.

**Not changed.** Notable, the global key-sensor limits, the recurring-error rule, and how the
CLI picks experts (mixing families when `expert_capture_model` is not given) are outside this
rule; the last is reported as a gap.

**Pre-registration record.** Lines 216-     281 of this file, from the "## 5. BL-18" heading to the line
above, hash to SHA-256 `2274b56b8ffff6dcf4239ecc53554f70cbc1b1270c27ec250f0e210dc5d8f60c`
(`awk` from the heading to that line, piped to `shasum -a 256`). Written 2026-09-29, before
any candidate rule was evaluated and before the held-out data were drawn.

**Amendment 1** (2026-09-29, after the dev run, before any held-out transcription was drawn or
aligned). No pre-registered candidate met the dev selection bar (strong at most 1.0% in both
families). Dev strong rate, Aria-AMT / Transkun V2 (R0 reproduces section 4):
R0 2.25% / 0.58%, R1(0) 2.13 / 0.55, R1(1) 1.75 / 0.46, R2 1.16 / 0.53, R1(0) + R2 1.14 / 0.51.
- *Diagnosis (dev only).* 166 of the 195 Aria-AMT strong bars are strong on missed notes, not
  wrong pitches. The Aria-AMT floor's missed-per-note 99th percentile is 0.771, against 0.286 for
  the key-sensor limit (Transkun V2: 0.308). 55 of the 195 bars lie in runs of 3 or more bars
  with at least 80% of the notes missed (a passage not played or not transcribed). The wrong-pitch
  limits of both families equal the key-sensor ones (1 and 2).
- *Added candidates.* R2s: the family limits replace the global limits for strong only (notable
  keeps the key-sensor limits, so R2s cannot change notable-or-strong rates or detection); and
  R1(k) + R2s, k in {0, 1, 2}. The selection order continues after the original four with:
  R2s, R1(0) + R2s, R1(1) + R2s, R1(2) + R2s, R1(1) + R2, R1(2) + R2.
- *Dev variants computed while diagnosing* (all disclosed), strong Aria-AMT / Transkun V2:
  R2s 1.16 / 0.53; R1(0) + R2s 1.14 / 0.51; R1(1) + R2s 1.05 / 0.46; R1(2) + R2s 0.97 / 0.36;
  R1(1) + R2 1.05 / 0.46; R1(2) + R2 0.97 / 0.36; R1(2) 1.53 / 0.36; R1(3) 1.27 / 0.36.
  So the selection rule picks **R1(2) + R2s**, which clears the dev bar by 0.03 points.
- *Held-out.* Acceptance A1-A3 unchanged, applied to R1(2) + R2s. Also reported as information:
  R2s and R1(1) + R2s (the near misses); R3 (30 experts) with R0, R1(0) and R1(2) + R2s; and
  R1(2) + R2s with the larger of the two families' limits applied to every target, which is what
  a report can use when the transcriber is not known.
- Lines 288-308 (this amendment) hash to SHA-256
  `37d1100a554b2e9dd77e7c138189eadc4fccb8158a48859e7433fa4b77461664`.

### 5.1 BL-18 results (Provisional, awaiting eval-auditor)

`scripts/calibrate_strong_tier_bl18.py` (570 alignments, 0 failed; about 55 minutes at load
~90 from other agents), outputs `data/interim/reports/calibration/bl18_{tables.pkl,summary.json}`.
- **Held-out data.** T1: 40 Transkun V2 and 50 Aria-AMT new targets of Henry's 5 pieces. T2:
  Beethoven Op. 106/4, Op. 109/1, Op. 27 No. 2/1, Op. 31 No. 3/1, Chopin Op. 23, Op. 28 No. 21;
  27-30 usable experts per piece and family. 207 usable targets (98 Transkun, 109 Aria-AMT;
  3 suspect alignments dropped), 32,740 clean bars, 12,956 injected bars (no suspect D-08 copy).
- **Selection (dev).** No pre-registered candidate met the bar; after amendment 1 the rule picks
  R1(2) + R2s (dev strong 0.97% Aria-AMT, 0.36% Transkun V2).

Held-out, 15 experts, rate in % with piece-bootstrap 95% CI (11 pieces). "Clean" = expert bars
(false rates); "injected" = bars with an injected wrong or missed note (detection).

| Rule | Family | Clean notable+ | Clean strong | Injected notable+ | Injected strong |
|---|---|---|---|---|---|
| R0 (F-08c) | Transkun V2 | 4.16 [2.44, 5.84] | 0.90 [0.27, 1.57] | 19.4 [15.7, 23.9] | 3.77 [2.54, 5.17] |
| R0 (F-08c) | Aria-AMT | 6.39 [4.66, 7.90] | 1.36 [0.75, 2.09] | 23.2 [20.6, 27.3] | 4.46 [2.88, 6.11] |
| R1(0) | Transkun V2 | 4.16 | 0.62 [0.19, 1.11] | 19.4 | 3.35 |
| R1(0) | Aria-AMT | 6.39 | 1.01 [0.55, 1.51] | 23.2 | 3.54 |
| R1(0) + R2s | Transkun V2 | 4.16 | 0.56 [0.11, 1.07] | 19.4 | 2.98 |
| R1(0) + R2s | Aria-AMT | 6.39 | 0.39 [0.19, 0.58] | 23.2 | 1.96 |
| R1(1) + R2s | Transkun V2 | 4.16 | 0.35 [0.06, 0.66] | 19.4 | 1.62 |
| R1(1) + R2s | Aria-AMT | 6.39 | 0.29 [0.12, 0.47] | 23.2 | 1.01 |
| **R1(2) + R2s (chosen)** | Transkun V2 | 4.16 | **0.17** [0.00, 0.39] | 19.4 | 0.83 [0.59, 1.08] |
| **R1(2) + R2s (chosen)** | Aria-AMT | 6.39 | **0.19** [0.05, 0.35] | 23.2 | 0.54 [0.21, 0.99] |
| R2 (notable limits too) | Aria-AMT | 4.39 | 0.49 | 17.3 | 2.20 |
| R1(2) + R2s, family unknown | Transkun V2 | 4.16 | 0.06 | 19.4 | 0.45 |

R2s never changes notable-or-strong, so the notable+ columns equal R0's for every R1 / R2s rule.
Pooled over families, the chosen rule gives 0.18% clean strong and 0.68% injected strong
(R0 1.14% and 4.13%).

**Verdict by the pre-registered rule: PASS** (A1: 0.17% and 0.19%, at most 1.25%; A2 and A3:
notable+ identical to R0 in both families). **But the rule overshoots.** The pre-registration
set only an upper tolerance. Strong on expert bars is now about 0.2%, a fifth of nominal, and
strong detection of injected bars falls by about 84% (4.13% to 0.68% pooled). That is the
price of the dev choice; on held-out data R1(0) alone (0.62% / 1.01%, strong detection 3.45%)
is the rule nearest nominal. Choosing it now would be selection on the held-out set, so it
needs its own fresh confirmation (lead decision, below).

**Other findings.**
- *Dev overstated the problem.* R0 on the held-out targets: Transkun V2 0.90%, Aria-AMT 1.36%
  (T1, Henry's pieces against the same 15 floor experts: 0.28% and 1.04%; T2: 1.14% and 1.52%).
  The floor leave-one-out gave 0.58% and 2.25%.
- *More references (R3, T2 only).* 30 instead of 15 experts: R0 strong 1.33% -> 0.89% pooled
  (Aria-AMT 1.52 -> 1.07, Transkun V2 1.14 -> 0.70), strong detection 4.28 -> 3.56%; R1(0) with
  30 experts 0.64% (detection 2.94%). 4 of Henry's 5 pieces have fewer than 30 Transkun
  transcriptions, so this helps the command line (Aria-AMT) more than the app.
- *Unknown family* (Aria-AMT limits for every target, the command-line default): Transkun
  targets drop to 0.06% strong, with detection 0.45%.
- *Key-sensor input, information only (unchanged in code).* R0 vs R1(0) on the F-08c cache:
  expert strong 0.67% -> 0.57%; injected strong at D-08 rate 0.05 2.59% -> 2.31%;
  notable+ identical (3.67%, 15.5%).

**Implemented** (`calibration.EXPERT_CHECK_STRONG_MARGIN_TRANSCRIBED = 2`,
`TRANSCRIBED_STRONG_LIMITS`, `build.expert_bar_limits(strong_margin=)`,
`ReportInputs.transcriber`, set from `expert_capture_model` by `report_from_files`). Applies only
when the input (family limits) or the experts (margin) are transcribed. Setting the margin to 0
and `ReportConfig.transcribed_strong_limits=False` gives R1(0) without a code change.

**Henry's 5 phone takes** (10 reports, both transcribers, rerun into
`data/interim/reports/henry_bl18/`; originals in `henry/` untouched; aggregate only).
- The same bars are tiered in every report; only strong becomes notable. Strong correctness bars
  over the 10 reports: 14 before, 3 after (per report 0-2 before, 0-1 after).
- Correctness practise items in the top-3 lists: 15 of 30 before, 7 of 30 after. Control items
  take the freed places.
- Op. 64 No. 2, bar 84 (4 wrong notes, experts 0) stays strong and first in the Transkun report.
  In the Aria-AMT report it is now notable and out of the top 3.
- Other report sections were not compared: another agent (DF-02) was editing them at the same
  time.

## BL-18 audit

eval-auditor, 2026-09-29. Scratch work in the session scratchpad (`bl18/`); no repo file other
than this section, `BACKLOG.md`, `WORKBOARD.md` and the auditor memory was changed.

**Verdict.** The measurement is **Confirmed**: PASS by the pre-registered rule reproduces
exactly. The implemented rule, R1(2) + R2s, is **Returned**. It meets only an upper tolerance
that was set too loosely, it costs learners real mistakes, and its Aria-AMT limit measures a
corpus artefact, not the transcriber. Recommendation: do not revert to R0; make R1(0) without
R2s the interim default, handle runs of fully missed bars separately, and confirm on new data
with a two-sided criterion (below).

**1. Pre-registration and ordering (verified).**
- Hashes: lines 216-281 give `2274b56b...f60c`, lines 288-308 give `37d1100a...1664`. Both
  match. The section 5 header and amendment were not edited after they were written.
- Timeline, from the feature-engineer transcript (`subagents/agent-aa4fc30e04c32f8c1.jsonl`,
  UTC): pre-registration appended 20:41:55 and hashed 20:42:01; script written 20:44:03; first
  dev evaluation 20:44:10 (`--dev-only`); dev diagnosis 20:45:17; amendment appended 20:46:22
  and hashed 20:46:36; first held-out draw and alignment 20:47:20; full run 20:50:15; tables
  written 21:18 and summary 21:20 (file times). So no held-out transcription was drawn or
  aligned before the amendment. The run took about 30 minutes, not the "about 55" in 5.1.
- The amendment extended the margin to k = 2 after k = 1 missed the dev bar (R1(1) + R2s
  1.05% Aria-AMT). That is disclosed and legitimate on dev, but the chosen rule is the first
  one to clear a noisy threshold, by 0.03 points.

**2. Held-out data and intervals (verified).**
- `--from-cache` rerun of `dev_eval` and `heldout_eval` (read-only, in scratch): the dev rates,
  the selection (R1(2) + R2s) and every held-out entry of `bl18_summary.json` are identical.
  Every number in the 5.1 table matches the summary.
- The 210 drawn targets are unique. None is a floor transcription or a T2 expert. None shares
  a source video (Aria-MIDI base id) or a named performer with an expert of its own set (68%
  of targets have no performer name, so a same-pianist overlap cannot be ruled out fully).
- The bootstrap resamples the 11 pieces (T1 keys `01`-`05`, T2 piece ids) and takes the ratio
  of summed counts; this is the right unit. The t-intervals are in the summary but not in the
  table. For R3 (6 pieces) they are wide, e.g. R0 injected strong with 30 experts 3.56%, t
  [-0.27, 8.74], so the R3 detection comparison is weak.
- A small dilution: an injected bar is matched by label, so a repeated label counts every
  instance as injected. This affects R0 and every candidate alike.

**3. Why the dev set overstated the problem, and why the choice overcorrects.**
- The claim "dev overstated the problem" holds for Aria-AMT only. R0 strong: Aria-AMT dev
  2.25% vs held-out 1.36%; Transkun V2 dev 0.58% vs held-out 0.90%. The pieces differ a lot:
  Transkun T1 0.28% and T2 1.14%; per piece under R1(0), Transkun ranges from 0 to 1.63%.
- The Aria-AMT gap comes from runs of fully missed bars (3 or more consecutive graded bars with
  at least 80% of notes missed). On dev they are 55 bars (0.63% of Aria-AMT bars) in 6 of 75
  targets. On held-out they are 15 bars (0.09%) in 4 of 109 targets. Transkun: 13 dev bars
  (2 targets), 0 held-out.
- No candidate can remove these bars: at least 80% missed is above every candidate limit,
  including the Aria-AMT family limit of 0.771. Under the chosen rule, 55 of the 80 dev
  Aria-AMT strong bars are run bars. To reach 1.0% overall, the rule had to cut every other
  strong bar to 0.29%. That is how the overcorrection happened. Without run bars, dev Aria-AMT
  strong is R0 1.62%, R1(0) 1.51%, R1(0) + R2s 0.46%, R1(2) + R2s 0.29%.

**4. The Aria-AMT missed-note excess is not a transcriber property.**
- In PianoCoRe, transcriber family and source corpus are the same thing. Every Aria-AMT
  transcription is from Aria-MIDI (YouTube audio, 127,620 rows). Every Transkun V2 one is from
  PERiScoPe (21,833). No performance was transcribed by both, so a family limit cannot
  separate the transcriber from the corpus.
- Most runs sit at the very start or end of the piece (5 of 10 Aria-AMT targets with runs,
  e.g. the first 11 bars). That fits truncated Aria-MIDI segments (ids end in `_0`, `_1`), and
  the other runs fit cuts or skipped passages. It does not fit transcriber failure.
- The family limit is set by these runs. The dev Aria-AMT 99th percentile of missed per note is
  0.771 with them and 0.422 without them (0.374 without the targets that have runs). Transkun
  V2: 0.308 and 0.301.
- Runs should therefore be handled by their own rule, not by a higher per-bar limit. A report
  would say "passage not heard: not played, or not captured"; the passage would not count as a
  correctness practise item or in the strong rate. Nothing in the data says that Aria-AMT on
  Henry's phone audio misses 77% of a bar's notes. Under R2s, a learner who drops half of a
  bar can never be strong in an Aria-AMT report.
- The held-out targets' own 99th percentiles (information only, these are targets) are 0.447
  for Aria-AMT and 0.429 for Transkun V2. Any family limit is piece-dependent as well.

**5. Learner safety (a real mistake demoted from strong to notable).**
- Notable-or-strong is unchanged under every R1 and R2s rule; verified column by column. The
  cost is in ordering only, but it is real. `collect_issues` ranks every strong item (timing,
  interpretation) above every notable correctness item. A recurring error across takes is still
  promoted to strong (`_takes_section`, independent of these limits), so multi-take learned
  mistakes are safe. Single-take reports are not.
- Injected mistakes (held-out, pooled): 535 bars are strong under R0, 447 under R1(0) and 88
  under R1(2) + R2s. Of the 447 that R1(2) + R2s loses, 88 are already lost under R1(0), 129 are
  lost to the family limits, and 230 only to the +2 margin.
- Unambiguous mistakes: bars with at least 3 injected wrong notes (85 bars). Share strong:
  R0 96.5%, R1(0) 92.9%, R1(0) + R2s 92.9%, R1(1) + R2s 74.1%, R1(2) + R2s 52.9%. Where every
  expert has at most 1 wrong note (56 bars), R0, R1(0) and R1(0) + R2s keep 100% and
  R1(2) + R2s keeps 76.8%. With experts at most 1, the +2 margin needs 4 wrong notes, so
  3 wrong notes at a clean bar are no longer strong. Only 7 bars have 50% or more of their notes
  missed by injection, too few to judge.
- Injected strong detection relative to R0: R1(0) 0.84 (Aria-AMT 0.79, Transkun V2 0.89);
  R1(2) + R2s 0.16.
- Henry's 10 reports, recomputed from the report bars against the same 15 floor experts (R0
  reproduces the old tiers and R1(2) + R2s the new ones, bar for bar). Strong correctness bars:
  R0 14, R1(0) 11, R2s 9, R1(0) + R2s 8, R1(1) + R2s 5, R1(2) + R2s 3. Of the 6 strong bars
  with 3 or more wrong notes, R1(0) keeps 5 and R1(2) + R2s keeps 3. Correctness items that
  leave the top 3 land at rank 4-19 of the practise-eligible list. Whether
  Henry's missed notes are real or phone-audio artefacts is not known (BL-22 is related).

**6. Recommendation.**
- **Not R1(2) + R2s.** It is far below nominal (0.17% / 0.19%). It demotes about half of the
  clear 3-wrong-note mistakes. Its Aria-AMT limit comes from corpus truncation.
- **Not R0.** The flaw it has is real: an interpolated q99 below the per-bar maximum makes "equal
  to the worst expert" strong. R0 runs above nominal on Aria-AMT held-out (1.36%).
- **Interim: R1(0), no R2s** (`EXPERT_CHECK_STRONG_MARGIN_TRANSCRIBED = 0`,
  `transcribed_strong_limits=False`; no other code change). Held-out: 0.62% / 1.01%, injected
  strong 3.45% pooled, 100% of 3-wrong-note bars at clean bars kept. This choice uses the
  held-out set, so it stays Provisional until the confirmation below. The BL-18 unit tests
  that assume margin 2 must follow the default.
- **Add the run rule** (3 or more consecutive graded bars with at least 80% missed become one
  "passage not heard" note, not a correctness tier), for all transcribed input.
- **R2s later, if at all:** only with limits estimated without run bars, on transcriptions
  whose corpus matches the app's capture chain (phone audio through the same transcriber), not
  a YouTube corpus.

**7. Confirmation run (BL-18b), to be pre-registered and hashed before any draw.**
- *Primary rule:* R1(0) + run rule, transcribed input, 15 same-family experts. *Reported as
  information, not selectable:* R0, R1(0) without the run rule, R1(2) + R2s (current code),
  and R1(0) + R2s with the Aria-AMT missed limit estimated on the dev floor without run bars
  (0.422).
- *Data:* 12 new pieces, drawn with a new seed among PianoCoRe pieces with at least 25
  transcriptions per family and one score, excluding Henry's 5 and the 6 T2 pieces; per piece
  and family, 15 experts and 10 targets, disjoint. Exclude every transcription id used in the
  floor, T1 or T2. Drop suspect alignments (match ratio below 0.8) as before.
- *Mistakes:* one D-08 copy of each target (rate 0.05, new seed). Also a targeted set: on each
  target, 10 clean bars where every expert has at most 1 wrong note, each given exactly 3 wrong
  pitches (one bar per copy, or spaced so bars do not interact).
- *Criteria, per family (point estimates; piece bootstrap 95% CI and t-interval reported):*
  - C1: clean strong rate between 0.30% and 1.25%, both limits included.
  - C2: notable-or-strong identical to R0 (true by construction; checked).
  - C3: D-08 injected strong detection at least 0.75 of R0's on the same bars.
  - C4: at least 95% of the targeted 3-wrong-note bars are strong.
  - C5: run bars are reported per family, with the share at the start or end of the piece.
  - PASS: C1-C4 in both families. PARTIAL: in one family (then the family needs its own rule,
    estimated on its own capture chain). FAIL: in neither, and R1(0) is reverted to R0 until
    more references (R3) are available.
- *Reachability,* from BL-18 per-piece rates under R1(0) with run bars removed, resampling 12
  pieces: C1 holds with probability about 0.92 for Aria-AMT and 0.73 for Transkun V2. Transkun
  pieces mostly sit below 0.5% (one piece is at 1.63%), which is why the lower limit is 0.30%
  and not 0.50%. Recompute this in the pre-registration.

**Lesson for `rules/experiments.md` (proposed to the lead).** Any calibration to a nominal rate
needs a two-sided tolerance, and a detection floor for real mistakes. Before selecting on dev,
separate the bars that no candidate can move (here, runs of fully missed bars). Otherwise the
selection rule overcorrects everything else to make up for them.

## 6. BL-18b: confirmation of the interim strong rule on transcribed input (pre-registration)

**Why.** The BL-18 audit returned R1(2) + R2s and the lead set the interim default to R1(0)
without R2s, plus a "passage not heard" rule (DECISIONS 2026-09-29, "lead: BL-18 after audit").
R1(0) was chosen after seeing the BL-18 held-out data, so it needs a fresh confirmation. This
section follows the audit's specification (section "BL-18 audit", item 7) and was written before
any BL-18b transcription was drawn or aligned.

**Rules** (transcribed input, 15 same-family experts, extras never counted; notable keeps the
per-bar q80 and the global key-sensor limits under every rule):
- **P (primary): R1(0) + run rule.** Strong needs more than every expert at the bar (margin 0)
  and more than the global key-sensor limit. Run rule: a run of at least 3 consecutive graded
  bars of the target, each with at least 80% of its graded notes missed (bars without graded
  notes are skipped; `build.not_heard_runs`), is one "passage not heard" item. Its bars get no
  correctness tier and are left out of the clean-bar denominator. The run rule looks at the
  target only; expert tables are used as they are.
- *Information, not selectable:* R0 (F-08c q99, no run rule); R1(0) without the run rule;
  R1(2) + R2s (the returned rule: margin 2, family strong limits Transkun V2 0.308, Aria-AMT
  0.771); R1(0) + R2s with the Aria-AMT missed limit estimated on the dev floor without run
  bars (0.422; Transkun V2 keeps 0.308); and P + BL-25 (the report default after this change:
  missed notes on same-pitch repeats due less than 100 ms after the previous one are not
  counted, for the target and the experts).

**Data.**
- Pool: PianoCoRe pieces with at least 25 transcriptions in each family (Transkun V2, Aria-AMT)
  and exactly one score.mxl in the archive, excluding Henry's 5 pieces and the 6 BL-18 T2
  pieces. 253 pieces qualify (count only, computed before the draw).
- Draw: 12 pieces, seed 1802 (`numpy.random.default_rng`), from the pool sorted by piece id.
  Per piece and family, the transcriptions sorted by id minus every id used in the A-01 floor,
  BL-18 T1 or T2, permuted with the same generator: the first 15 are experts, the next 10
  targets. Targets whose clean alignment has match ratio below 0.8 are dropped; so are experts.
- *D-08 copies:* one per target, `perturb(..., MistakeSpec(rate=0.05), seed=1,
  require_exact_timing=False)`. An injected bar is a bar label holding an injected wrong pitch
  or missed note (as in BL-18). A copy with match ratio below 0.8 is dropped from C3.
- *Targeted copies:* one per target, seed 2. Eligible bars: the label occurs once in the
  performed score; at least 5 experts cover it and every one has at most 1 wrong note there; the
  target's clean bar has no wrong note, is not in a run and has at least 3 aligner-matched
  notes. Up to 10 bars are taken in a seeded random order, keeping at least 2 untouched bars
  between chosen bars. In each, exactly 3 matched notes (seeded) get a wrong pitch drawn as in
  D-08 (`MistakeSpec().wrong_pitch_deltas` without the octave entries, i.e. ±1 / ±2; in piano
  range, not a pitch of the same chord, not the same key already sounding). The copy is
  realigned to the score. A copy with match ratio below 0.8 is dropped from C4.

**Criteria, per family** (point estimates decide; piece bootstrap 95% CI, 2,000 resamples,
seed 0, ratio of summed counts, and a t-interval over per-piece rates are reported):
- **C1:** P's clean strong rate (strong bars / graded bars outside runs) is between 0.30% and
  1.25%, both limits included.
- **C2:** P's notable-or-strong tier equals R0's on every clean and injected bar outside runs
  (true by construction; checked, count of differing bars reported).
- **C3:** P's strong share of D-08 injected bars is at least 0.75 of R0's on the same bars.
  Injected bars inside a run of the injected copy count as not strong under P.
- **C4:** at least 95% of the targeted 3-wrong-note bars are strong under P. The share among
  targeted bars where the checker reports at least 3 wrong notes is reported as information.
- **C5:** run bars reported per family: count, share of graded bars, targets with a run, and
  the share of runs (and of run bars) that touch the first or last graded bar.
- **PASS:** C1-C4 in both families. **PARTIAL:** C1-C4 in one family only (that family keeps
  R1(0); the other needs its own rule, estimated on its own capture chain). **FAIL:** neither,
  and R1(0) is reverted to R0 on transcribed input until more references (R3) are available.

**Reachability** (recomputed before the draw from the BL-18 held-out cache,
`bl18_tables.pkl`: per-piece R1(0) clean strong rates with run bars removed, 11 pieces,
10,000 resamples of 12 pieces with replacement, seed 0):
- C1: P(holds) = 0.92 for Aria-AMT (per-piece 0.13-1.88%, pooled 0.93%) and 0.73 for
  Transkun V2 (per-piece 0-1.63%, pooled 0.62%; three pieces at 0). So a Transkun V2 miss of
  C1, below or above, has a real chance even if R1(0) is right, and the verdict is read with
  that in mind.
- C3: pooled R1(0) / R0 strong detection in BL-18 was 0.89 (Transkun V2) and 0.79 (Aria-AMT);
  P(ratio >= 0.75) = 1.00 and 0.89.
- C4: in the BL-18 audit, 56 of 56 bars with at least 3 injected wrong notes where every expert
  had at most 1 were strong under R1(0). The risk is the aligner: BL-20 measured 2.5% of wrong
  pitches absorbed or mispaired in slow passages and 6.9-8.3% under 100 ms; if a bar keeps
  only 2 of its 3 wrong notes it cannot be strong. If each of the 3 notes is lost
  independently at 2.5%, about 93% of bars keep all 3, below 95%. So C4 can fail for an
  aligner reason; the conditional share (checker sees at least 3) separates that from the rule.
- The run rule changes C1 only through run bars. In BL-18 held-out data there were 15 such
  bars (Aria-AMT) and 0 (Transkun V2).

**Script:** `scripts/calibrate_strong_tier_bl18b.py`; outputs (gitignored)
`data/interim/reports/calibration/bl18b_{tables.pkl,summary.json}`. Verdict: Provisional until
the eval-auditor signs off.

**Pre-registration record.** The lines from the "## 6. BL-18b" heading to the line above hash
to the SHA-256 given in the next paragraph (`awk` from the heading to the line above this
paragraph, piped to `shasum -a 256`).
Lines 527-607 hash to SHA-256
`3a151ec72d30eb4b377582ca309581ab0fee98c83166123d70bbb6463d04b8db`. Written 2026-09-29
(22:33 UTC), before any BL-18b piece or transcription was drawn or aligned.

### 6.1 BL-18b results (Provisional, awaiting eval-auditor)

`OMP_NUM_THREADS=1 uv run python scripts/calibrate_strong_tier_bl18b.py --workers 10`
(uncommitted tree; 600 jobs, 0 failed; 360 experts, 240 targets, each target aligned 3 times).
Outputs: `data/interim/reports/calibration/bl18b_{tables.pkl,summary.json}`; `--from-cache`
re-scores. Pieces (seed 1802, 253 eligible): Beethoven Op. 10 No. 1/2, Op. 14 No. 2/2,
Op. 31 No. 3/2, Op. 110/3-4; Chopin Op. 10 No. 6, Op. 28 No. 20, Op. 54, Op. 58/1, Op. 58/2;
Debussy L. 123 No. 7, L. 136 No. 11; Schubert D. 780 No. 2. 15 usable experts in every piece and
family (0 suspect). 238 usable targets (119 per family; 2 suspect dropped), 0 suspect D-08 or
targeted copies. Targeted bars: 1,130 Transkun V2, 1,125 Aria-AMT.

Rates in %, piece bootstrap 95% CI [t-interval over the 12 pieces in the summary JSON].

| Rule | Family | Clean notable+ | Clean strong | D-08 injected strong | Targeted 3-wrong strong |
|---|---|---|---|---|---|
| **P = R1(0) + run rule** | Transkun V2 | 4.22 | **0.58** [0.18, 0.81] | 3.42 [1.93, 4.87] | **71.5** [66.1, 77.2] |
| **P = R1(0) + run rule** | Aria-AMT | 6.04 | **1.04** [0.68, 1.28] | 4.28 [2.77, 5.84] | **68.4** [63.3, 73.6] |
| R0 | Transkun V2 | 4.22 | 0.89 [0.33, 1.19] | 4.22 [2.00, 6.50] | 71.6 |
| R0 | Aria-AMT | 6.75 | 2.09 [1.08, 2.74] | 5.09 [3.05, 7.11] | 68.6 |
| R1(0), no run rule | Aria-AMT | 6.75 | 1.55 [0.90, 2.02] | 4.31 | 68.4 |
| R1(2) + R2s (returned) | Transkun V2 | 4.22 | 0.10 | 0.87 | 58.1 |
| R1(2) + R2s (returned) | Aria-AMT | 6.75 | 0.52 | 0.66 | 39.2 |
| R1(0) + R2s, Aria 0.422 | Aria-AMT | 6.75 | 1.08 | 2.78 | 67.9 |
| P + BL-25 | Transkun V2 | 3.95 | 0.53 | 3.28 | 71.4 |
| P + BL-25 | Aria-AMT | 5.95 | 1.04 | 4.22 | 68.4 |

(Transkun V2 has no run bars, so R1(0) without the run rule equals P there. P's clean
denominator leaves out the 176 Aria-AMT run bars.)

**Criteria (pre-registered, point estimates).**
- C1 clean strong in [0.30, 1.25]%: Transkun V2 0.58 **pass**; Aria-AMT 1.04 **pass**.
- C2 notable+ equal to R0 outside runs: 0 differing bars in either family, **pass**.
- C3 D-08 strong detection vs R0: Transkun V2 0.81 [0.75, 0.97], Aria-AMT 0.84 [0.81, 0.92];
  both at least 0.75, **pass**.
- C4 targeted 3-wrong-note bars strong at least 95%: Transkun V2 71.5, Aria-AMT 68.4, **fail**
  in both.
- C5 run bars: Transkun V2 none. Aria-AMT 19 runs, 176 bars (0.81% of graded bars) in 10 of 119
  targets; 0 runs at the start, 3 at the end (16% of runs, 20% of run bars). So on these pieces
  the runs are mostly inside the piece, unlike the dev set.

**Verdict by the pre-registered rule: FAIL** (C4 fails in both families). The pre-registered
consequence is "R1(0) is reverted to R0 until more references (R3) are available". This is
not applied in code: it is for the lead to decide, for the reason below.

**Why C4 fails: the note checker, not the strong rule (post hoc diagnosis, disclosed).**
- Among targeted bars where the checker reports all 3 wrong notes (69% Transkun V2, 66%
  Aria-AMT), P makes 100% strong in both families (782 and 744 bars).
- R0 fails C4 by the same amount (71.6 / 68.6%). When the checker counts 2 wrong notes or
  fewer, a bar can be strong only through its missed notes, under any rule. The criterion is not specific to the rule (the
  BL-19/20 lesson on absolute thresholds: the baseline cell breaches it too).
- In the targeted bars, the checker's wrong-note count is 0 / 1 / 2 / 3 in 36 / 133 / 179 / 782
  bars (Transkun V2) and 68 / 135 / 178 / 744 (Aria-AMT). So 16% (Transkun V2) and 19%
  (Aria-AMT) of injected wrong notes are not counted as wrong, against 2.5-8.3% in BL-20 on
  Disklavier playing. Per bar, 0.49 (Transkun V2) and 0.58 (Aria-AMT) wrong notes are lost,
  while the injection adds on average 0.27 / 0.31 missed and 0.23 / 0.27 extra notes. So part of the loss becomes missed plus
  extra (an unpaired or absorbed wrong key), and the rest is labelled correct or tolerated, or
  lands in a neighbouring bar. This run does not separate these.
- The reachability note in the pre-registration expected about 93% of bars to keep all 3
  wrong notes, from the BL-20 rates. That was an underestimate for transcribed input.

**Other findings.**
- The run rule matters for Aria-AMT: without it R1(0) is at 1.55%, above C1's upper limit.
- The returned R1(2) + R2s rule again sits below the C1 floor (0.10% Transkun V2) and keeps
  39% (Aria-AMT) of targeted bars strong. Its rejection stands.
- R0 on Aria-AMT is 2.09%, above the tolerance. Reverting to R0 would restore that flaw and
  change nothing on C4.
- BL-25 lowers clean notable+ by 0.1-0.3 points and D-08 strong detection by 0.06-0.14 points.

**For the lead.** (1) Apply the pre-registered FAIL (revert to R0), or record that C4 measured
the checker and keep R1(0) + run rule. The data say R1(0) + run rule meets C1-C3 in both
families, and R0 fails C1 on Aria-AMT. (2) Wrong-pitch loss on transcribed input (16-19% of injected
wrong notes not counted as wrong) is a checker / aligner issue (BL-23 area), not a tier issue.

## BL-18b audit

eval-auditor, 2026-09-29. Scratch work in the session scratchpad (`bl18b_audit/`). No code was
changed. Files changed: this section, `EXPERIMENTS.md`, `BACKLOG.md`, `DEFECTS.md` (DF-12
note), `WORKBOARD.md`, `.claude/rules/experiments.md` and the auditor memory.

**Verdict.** The measurement is **Confirmed**: every number in 6.1 reproduces exactly, and FAIL
is the correct reading of the pre-registered rule. It stays the recorded verdict. The lead's
proposal (keep R1(0) + run rule, do not revert to R0) is **legitimate as a disclosed deviation
from the pre-registered consequence, not as a new reading of the verdict**, under the conditions
in item 6. The optional C4' (bars where the checker counts all 3 wrong notes) is **not** a valid
confirmation criterion: it is 100% by construction for any margin-0 rule (item 3).

**1. Pre-registration and ordering (verified).**
- `sed -n 527,607p docs/specs/report-validation.md | shasum -a 256` gives
  `3a151ec72d30eb4b377582ca309581ab0fee98c83166123d70bbb6463d04b8db`. It matches. The section 5
  hashes (lines 216-281, 288-308) still match too.
- Timeline, from the feature-engineer transcript (`subagents/agent-a3ffbd0c9ed754a0b.jsonl`,
  UTC): report code changes 22:26-22:30; reachability computed on the BL-18 cache only 22:31:06;
  eligible-piece count (count only, no draw) 22:32:11; section 6 appended 22:32:47 and hashed
  22:32:52; the time note edited 22:32:58 (below line 607, so the hash is unchanged); script
  written 22:34:36; a one-piece smoke test 22:34:47 (the first draw); full run 22:35:17; results
  written from 22:53:21. No draw or alignment came before the hash, and the script was not
  edited between the smoke test and the full run.
- Nothing in section 6 was edited after the run. The post hoc analysis in 6.1 is labelled as
  such.

**2. Reproduction (verified).**
- `evaluate()` imported from the script and run on `bl18b_tables.pkl` (read-only; `main
  --from-cache` would overwrite the summary): **0 differences** against every field of
  `bl18b_summary.json`. Every number in the 6.1 table and criteria list matches.
- The targeted copies were regenerated from the raw data with the script's own functions
  (clean alignment, then `targeted_copy` with seed 2) for all 238 usable targets: the chosen
  bars are identical in 238 of 238. So the selection is deterministic and C4's input is what
  6.1 says.
- Code checks: `tiers` returns graded bars in order, so the run mask (graded-row indices from
  `run_labels`) lines up; the C3 paired frame is built from identically filtered tables; the
  bootstrap resamples the 12 pieces. Gates: `uv run pytest -q` 555 passed, 1 skipped;
  `ruff check src tests scripts/calibrate_strong_tier_bl18b.py` clean.
- Intervals the table does not show: Transkun V2 C1 t-interval is [0.09, 0.59]%, so its lower
  end is below the 0.30% tolerance (the bootstrap is [0.18, 0.81]). Aria-AMT C1 t is [0.66,
  1.14]%. C3 Transkun V2 bootstrap [0.747, 0.966] touches the 0.75 floor. Point estimates
  decide by the pre-registration, so C1 and C3 pass, but on one sample of 12 pieces with no
  margin on the Transkun V2 lower side.

**3. C4 cannot tell the rules apart (this is the design error, and it is partly the
auditor's).**
- Targeted bars are chosen where every expert (at least 5) has at most 1 wrong note. The global
  strong limit for wrong notes is 2 (`CORRECTNESS_EXPERT_BARS["wrong_pitch_q99"]`). So under
  R0 and under R1(0), a targeted bar where the checker counts 3 wrong notes is strong **by
  construction**: 3 > max(2, expert max <= 1). Measured: 100% in both families for P, R0,
  R1(0), R1(0) + R2s and P + BL-25. Only a positive margin can lower it: R1(2) + R2s gives
  83.4% (Transkun V2) and 58.9% (Aria-AMT) on those bars.
- So for P against its fallback R0, C4 = the share of bars where the checker counts all 3
  (69.2% / 66.1%) plus the few bars that turn strong through missed notes. P and R0 differ on
  C4 by 1 bar of 1,130 (Transkun V2) and 3 of 1,125 (Aria-AMT). C4 measured the note checker,
  as 6.1 says.
- The pre-registration saw this coming and did not fix it. Its own reachability note estimated
  about 93% of bars keeping all 3 wrong notes at the BL-20 rate, which is **below** the 95%
  bar. By the R-09 lesson, PASS was not reachable as registered even if the rule were perfect.
  The criterion came from the BL-18 audit (item 7), which aimed C4 at the +2 margin and did not
  notice that for margin 0 its rule-dependent part is fixed.
- The optional **C4'** (bars where the checker counts all 3) has the same problem: 100% for any
  margin-0 rule by construction. It only catches an implementation bug or a positive margin. It
  belongs in a unit test, not in a confirmation criterion (BL-19/20 lesson: "an oracle control
  that is zero by construction is not evidence").

**4. Where the lost wrong notes go (new, for DF-12).**
Note-level probe on the regenerated targeted copies: 6,765 injected wrong pitches (3,390
Transkun V2, 3,375 Aria-AMT). Share of injected notes by label in the realigned copy:

| Outcome | Transkun V2 | Aria-AMT |
|---|---|---|
| wrong pitch, same bar (counted) | 83.5% | 80.4% |
| extra (left unpaired; the intended score note shows as missed) | 10.1% | 13.3% |
| correct (matched to another score note of the new pitch) | 4.7% | 4.1% |
| ornament (tolerated by the legacy whitelist) | 1.5% | 2.0% |
| wrong pitch, other bar | 0.1% | 0.2% |

- The main loss is **unpaired**: 75% (Transkun V2) and 84% (Aria-AMT) of the unpaired notes sit
  more than 100 ms from their score note's expected onset (median 141 ms and 180 ms), against a
  median of 12-13 ms for the notes that were counted. This is the wrong-pitch pairing window
  (`WRONG_PITCH_WINDOW_SEC`, 100 ms) meeting worse expected-onset estimates on these
  transcriptions. It is not aligner absorption. Why the expected onsets are worse here
  (rolled chords, rubato, transcriber onset noise) was not measured.
- The "correct" group is mostly a collision: in 90% / 85% of these, the new pitch is written in
  the same bar, and the aligner matched the injected note to that score note. Only 8% / 12% of
  those score notes had been missed in the clean transcription. So the injection's "not a pitch
  of the same (performed) chord" check does not stop collisions with the score.
- Loss by local tempo (`fast_run_notes`): 20.7% / 23.8% in fast runs and 16.0% / 19.1% outside
  them. So the loss is broad, not a fast-run effect. Per piece it ranges from 0.8% to 25.7%
  (Transkun V2) and 3.5% to 29.0% (Aria-AMT).
- Consequence for DF-12: first test a wider or tempo-scaled pairing window against clean-copy
  false pairings, then the score-collision case. Ornament tolerance is a small share.

**5. C5 and the truncation explanation.**
- C5's "0 at the start, 3 at the end" is right as defined (a run touching the first or last
  graded bar), but the definition understates edges. Runs fragment: a bar just under 80% missed
  splits a run, and the last 1-3 bars are often still found (72-86% missed; possibly the final
  chord matched). Merging runs separated by at most 2 bars gives 10 gaps in the 10 targets. 8
  of them are within 3 graded bars of the start or end (the 9th ends 11 bars before the end,
  and the bars after it are 83% missed). Only one is a true mid-piece gap: Aria_771468_0,
  Chopin Op. 54, graded bars 410-494 of 932 (85 bars; 8 of the 19 runs). In 8 of the 10
  targets the missing passage is the ending; in 1 it is the opening.
- Every run target is an Aria-MIDI segment (`Aria_<video>_<seg>`, segment numbers 0-5). So the
  data do not undermine the truncation explanation; they support it once fragments are merged.
  The one mid-piece gap could be a cut in the video; that was not checked.
- Product consequence (not a verdict issue): a truncated ending shows up as 2-3 separate
  "passage not heard" items without the "at the end" note, and the bars between the fragments
  can be tiered. 11 of the 226 Aria-AMT strong bars under P lie within 3 bars of a run (10 of
  them with at least 50% missed). Without them the Aria-AMT C1 rate is 1.00% instead of 1.04%.
  Suggested (new rule, to be fixed before its own check): merge runs separated by at most 2
  graded bars, and extend a run to the edge when the remaining edge bars are at least 50%
  missed.

**6. The lead's proposed decision: yes, with conditions.**
Is it goalpost-moving? Changing a verdict after seeing the data is. Declining a pre-registered
*action* is not, when the pre-registered comparison shows the action would not do what it was
for, and the change is disclosed. Here:
- (a) holds, and more strongly than stated: C4's rule-dependent part is fixed by construction
  for both P and R0, so C4 could not favour R0 over P. The FAIL says nothing against R1(0).
- (b) holds: R0 fails C1 on Aria-AMT (2.09% by point estimate; bootstrap [1.08, 2.74], so not
  entirely above 1.25) and equals P on C4. Reverting improves no criterion and worsens C1.
- The pre-registered branch was written assuming a FAIL would be the rule's fault. The
  pre-registered information (the conditional share, and the reachability note) shows it was
  not.

Conditions:
1. **The verdict stays "FAIL by the pre-registered rule"** everywhere (6.1, EXPERIMENTS,
   BACKLOG, research log). No "PASS on C1-C3" headline without it.
2. **A DECISIONS.md entry by the lead** that names the pre-registered consequence, says it is
   not applied, and gives the reasons (a) and (b) with the numbers above, plus the design error
   in C4 (item 3).
3. **R1(0) + run rule stays interim / Provisional**, described as "meets C1-C3 on one new
   sample of 12 pieces". It is not "confirmed". Mention that Transkun V2 C1 passes only by the
   point estimate (t-interval lower end 0.09%).
4. **The learner-facing number is disclosed** in `docs/SCORING_MODEL.md` and the research log:
   on transcribed input, about 7 in 10 bars with 3 wrong notes become strong (71.5% / 68.4%),
   because the checker does not count 16-19% of wrong notes (DF-12). The tier rule is not the
   limit.
5. **C4 is reclassified as an end-to-end detection measurement feeding DF-12.** Do not
   register C4' as a confirmation criterion. For a future confirmation (after a DF-12 fix, on
   new pieces), register instead: (i) a rule-relative criterion on targeted bars, P's strong
   share at least 0.95 of R0's (information on this data: 0.999 and 0.996, post hoc, not
   evidence); (ii) the end-to-end targeted share as a tracked DF-12 measurement, with a floor
   derived from the measured loss, not 95% by default.
6. Text that says the checker finds wrong notes "reliably per bar" (item 7) must not be shown
   as a reliability claim on transcribed input.

**7. BL-25 and fast-run wording (code review).**
- BL-25 logic is sound: fast repeats are keyed on the score (expected onsets at the played
  tempo), NaN intervals are not flagged, the run rule uses raw missed counts as pre-registered,
  and `P + BL-25` in the script drops fast repeats on both sides.
- **Expert side missing in cached floor tables:** all 150 `f08c_floor_tables.pkl` tables lack
  `n_missed_fast_repeat`, so reports that use them (Henry's) reduce the target only. Measured
  on BL-18b, target-only vs both sides: clean notable+ 3.89 vs 3.95% (Transkun V2) and 5.69 vs
  5.95% (Aria-AMT); clean strong 0.51 vs 0.53% and 0.92 vs 1.04%; D-08 injected strong 3.25 vs
  3.28% and 4.12 vs 4.22%. So it errs toward fewer flags (conservative on false alarms, slightly
  lower detection), and C1 stays in range. Not blocking. Rebuild the floor tables, or record in
  the report summary whether the experts were reduced (today it is silent).
- **Fast-run wording:** the bar-level wording is sound as a statement about which note
  (BL-20). But the parenthesis "the checker finds them reliably per bar" is not supported on
  transcribed input: 21-24% of injected wrong notes in fast runs were not counted (item 4).
  Suggest "the checker is more reliable about the bar than about which notes". Minor:
  "this fast run" / "these fast runs" is chosen by the number of bars, not of runs.
- Edge case: a recurring wrong note across takes promotes a bar to strong after the run rule,
  so it can override "not heard". Rare (the bar is at least 80% missed); worth one line in the
  code or a guard.

**Lessons (added to `rules/experiments.md`).**
- Before registering a detection floor on injected mistakes, compute what each candidate rule
  gives when the checker sees the injection. If that is fixed by construction (here 100% for
  every margin-0 rule), the unconditional floor measures the checker, not the rule. Register a
  rule-relative criterion instead, and report the end-to-end figure as a measurement.
- A pre-registered fallback action needs its premise checked in the same run: if the fallback
  fails the same criteria or worse, the action cannot be applied mechanically. Keep the FAIL
  verdict, and record the deviation from the action in DECISIONS.
- Position statistics for runs (start / end / middle) need fragments merged and a tolerance at
  the edges, or they understate truncation.
