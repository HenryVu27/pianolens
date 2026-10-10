# DF-13: wrong-pitch pairing window on transcribed input
Ticket: DF-13 (root cause of DF-12)    Hypothesis: none from the plan (checker defect)    Status: Provisional

## Question
On transcribed input, 16-19% of injected wrong notes are not counted as wrong (DF-12). Does a
wider or onset-adaptive wrong-pitch pairing window, used for transcribed input only, recover a
useful share of them without creating false pairings on clean transcriptions or in dense
passages?

## Falsified if
Pre-registered in `docs/specs/correctness-validation.md`, section "Pre-registration DF-13"
(lines 338-451). SHA-256 of that section, computed with
`awk '/^## Pre-registration DF-13/{f=1} f{print} /^End of the DF-13 pre-registration\.$/{exit}' docs/specs/correctness-validation.md | shasum -a 256`:
`44bd842e6182f60be8d883bbe219ffc54552f18e1d22f050bd94c6d321fb771f` (also in
`artifacts/prereg_sha256.txt`), recorded 2026-10-10 20:42 UTC, before any held-out piece was
drawn or aligned.

In short, per family (Transkun V2, Aria-AMT), candidate minus the 100 ms baseline: B1 strict
recall of targeted injected notes +1.5 to +10 pt; M1 mispair increase at most +1.5 pt and at
most a third of B1; F1 clean wrong-pitch rate up at most 15%; R1 clean strong (rule P) within
±0.25 pt; R2 clean notable+ within ±0.5 pt; E1 strong share of targeted 3-wrong bars +2 to
+20 pt; D1 fast runs: strict at least -1 pt, mispair at most +1.5 pt, clean fast-run rate up at
most 25%. PASS = all in both families. Candidates in order: `tempo` (primary), `error`, `wide`.

## Data
PianoCoRe (DATASETS.md), tier A transcriptions, Transkun V2 (PERiScoPe) and Aria-AMT
(Aria-MIDI), scores from the PianoCoRe archive.
- Dev: the BL-18b set (12 pieces, 360 experts, 240 targets, 238 usable), already seen.
- Held-out: 16 new pieces (seed 1010) of 241 eligible, 15 experts + 10 targets per piece and
  family, no transcription used before.

## Splits
No model is fitted. Constants were chosen on dev; held-out pieces are disjoint from dev, the
A-01 floor, BL-18 T1/T2 and BL-18b. Piece bootstrap (2,000, seed 0) and t-intervals over pieces.

## Baselines
The deployed 100 ms window (`fixed`) on the same alignments. Ceiling: the window-reachable share
of injected notes (unpaired with the intended score note missed under `fixed`).

## Method
See the pre-registration. Each expert and each target copy (clean, D-08, targeted) is aligned
once; `correctness(..., wrong_pitch_window=rule)` labels it under every rule; targets are
checked against expert tables labelled with the same rule (rule P = R1(0) + run rule, extras
not counted). Dev exploration (scratch, disclosed in the pre-registration): outcome split of the
6,765 BL-18b injected notes, the clean-vs-targeted expected-onset error, a robust time map
(worse), and a sweep of window rules.

## Command
```
OMP_NUM_THREADS=1 uv run python scripts/eval_pairing_window_df13.py --set dev --workers 10
OMP_NUM_THREADS=1 uv run python scripts/eval_pairing_window_df13.py --set dev --from-cache --reachability
OMP_NUM_THREADS=1 uv run python scripts/eval_pairing_window_df13.py --set heldout --workers 10
```
Outputs: `data/interim/df13/{dev,heldout}_{rows.pkl,summary.json,piece_sums.csv}`.

## Run record
- Dev: 600 jobs (BL-18b job list), 0 failed; 238 usable targets (2 suspect), 1,130 / 1,125
  targeted bars (Transkun V2 / Aria-AMT). The `fixed` rule reproduces BL-18b exactly where they
  overlap: targeted 3-wrong bars strong 71.5% / 68.4% (BL-18b C4), P clean strong 0.58% / 1.04%
  (BL-18b C1), and the audit's note split (counted in the same bar 83.4 / 80.4%).
- Held-out: drawn and run 2026-10-10 20:42-21:30 UTC (after the hash), 800 jobs, 0 failed,
  15 suspect experts and 7 suspect targets dropped; 157 / 156 usable targets, 1,439 / 1,443
  targeted bars, 4,287 / 4,239 injected notes, 0 collisions (by construction). 8 D-08 copies and
  4 targeted copies suspect. Pieces (seed 1010, 241 eligible): Beethoven Op. 106/1, Op. 111/2,
  Op. 14 No. 2/1; Chopin Op. 25 No. 5, Op. 28 Nos. 6 and 13, Op. 35/3, Op. 66; Debussy L. 123
  Nos. 4 and 9; Mozart K. 331/2; Mussorgsky Pictures, "The Old Castle"; Ravel Gaspard, "Scarbo";
  Satie Gymnopedie No. 3, Gnossienne No. 1; Schumann Op. 16 No. 2.
- Code: uncommitted on top of 10403a5; sha256 of (diff of `correctness.py` and its test + the
  script) at launch `7bf82ad7...4490`. Seeds: draw 1010, D-08 1, targeted 2, bootstrap 0.
- Wall time: dev about 35 min, held-out 48 min, both at machine loads of 8-65 (other agents).

## Results

Held-out, per family (Transkun V2 / Aria-AMT). Rates in %, deltas in percentage points
(candidate minus `fixed`), piece bootstrap 95% CI [t-interval over 16 pieces].

| Measure | `fixed` (baseline) | `tempo` (primary) | delta |
|---|---|---|---|
| Targeted notes, strict recall (B1) | 82.0 / 79.6 | 85.6 / 84.3 | +3.6 [2.6, 4.7] [2.5, 4.9] / +4.7 [3.1, 6.3] [3.0, 6.4] |
| Targeted notes, mispair (M1) | 1.7 / 2.0 | 2.4 / 2.7 | +0.75 [0.45, 1.07] / +0.68 [0.29, 1.17] |
| Targeted notes, unpaired | 11.4 / 13.7 | 7.0 / 8.3 | |
| Targeted notes, absorbed / ornament | 2.2 / 2.5 ; 2.8 / 2.3 | same | |
| Window-reachable loss (unpaired, intended missed) | 6.3 / 7.8 | recovered 58% / 61% | |
| Clean wrong-pitch labels per 1,000 graded notes (F1) | 6.62 / 10.10 | 7.61 / 11.79 | +0.99 [0.38, 1.72] [0.24, 1.05] / +1.69 [0.55, 3.31] [0.24, 2.07]; relative **+15.02% / +16.8%** |
| P clean strong (R1) | 1.49 / 1.86 | 1.52 / 1.92 | +0.03 / +0.06 |
| P clean notable+ (R2) | 7.28 / 9.38 | 7.42 / 9.57 | +0.14 / +0.19 |
| Targeted 3-wrong bars strong under P (E0 -> E1) | 73.0 / 69.0 | 78.5 / 76.2 | +5.5 [3.2, 7.7] [2.8, 8.1] / +7.2 [4.0, 11.1] [3.2, 11.1] |
| Fast runs: strict / mispair (D1) | | | +3.6 / +1.0 ; +5.5 / +1.2 |
| Fast runs: clean wrong-pitch rate (D1) | | | relative +21% / +24% |
| D-08 injected bars strong (information) | 3.4 / 4.9 | 3.8 / 5.2 | |

Criteria (point estimates), held-out:

| Candidate | Transkun V2 | Aria-AMT | Verdict |
|---|---|---|---|
| `tempo` (primary) | all pass except **F1** (15.02% > 15%) | all pass except **F1** (16.8%) | **FAIL** |
| `error` (fallback 1) | fails F1 (15.7%), D1 (mispair +1.6 pt) | fails F1 (18.2%), D1 (clean fast +27%) | FAIL |
| `wide` (fallback 2) | all pass (F1 14.7%) | fails F1 (16.8%), D1 (clean fast +26%) | PARTIAL |

Dev (the same table on the BL-18b set): every candidate passes every criterion; `tempo` B1
+3.3 / +3.7, M1 +0.8 / +0.5, F1 +8.9% / +9.5%, E1 +5.8 / +6.2.

## Verdict (Provisional)
**FAIL by the pre-registered rule.** No candidate PASSes: `tempo` and `error` fail in both
families, `wide` is PARTIAL (Transkun V2 only). The pre-registered action is "`fixed` stays and
the lead decides". Nothing was implemented: the transcribed path is unchanged, so the Henry
reports, the A-01 floor tables and every calibration constant are unchanged.

What the data say, without changing the verdict:
- The benefit is real and replicates: `tempo` recovers about 60% of the window-reachable loss,
  adds 3.6 / 4.7 pt of correctly paired wrong notes, and raises the end-to-end share of
  3-wrong-note bars that are strong from 73.0 / 69.0% to 78.5 / 76.2%. All its other harms pass
  (mispair, report-level clean strong and notable+, fast runs).
- The single failing criterion is F1, the clean false-pairing proxy, and it fails narrowly in
  Transkun V2 (15.02% against 15%). F1 counts every new pair on a clean transcription as false,
  so it is an upper bound: some new pairs are real transcriber pitch errors (a wrong pitch read
  from audio is labelled missed + extra under `fixed`). No ground truth here separates them.
- One piece drives it. Ravel's "Scarbo" holds 51% (Transkun V2) and 55% (Aria-AMT) of the added
  clean pairs; its clean baseline is 15.7 / 28.3 wrong-pitch labels per 1,000 notes (others
  0.3-12.8). Leaving it out gives F1 +11.9% / +11.8% (pass). Leave-one-piece-out over all 16
  pieces: 11.9-18.4% (Transkun V2), 11.8-20.6% (Aria-AMT). This is information, not a re-reading
  of the verdict.
- The ceiling of any window rule is small: only 6.3 / 7.8% of injected notes are
  window-reachable on held-out (4.3 / 6.4% on dev). The other unpaired half is the aligner
  re-matching the intended score note to another same-pitch note after the injection. With the
  collision fix, absorption fell from 4.9 / 4.1% (dev) to 2.2 / 2.5%, yet the baseline
  end-to-end share stayed at 73.0 / 69.0%: collisions were not the main loss.

**What `tempo` would move if adopted (information only; nothing applied).**
`scripts/rebuild_floor_tables_df13.py --rule tempo` relabelled the 150 A-01 floor
transcriptions (leave-one-out within piece and family, extras not counted; outputs
`data/interim/df13/floor_tables_{fixed,tempo}.pkl`, `floor_calibration_tempo.json`):
- F-08c checked rates quoted in `calibration.py` ("transcribed ... 5.3/1.4%"): 5.25 / 1.41% ->
  5.00 / 1.46% pooled (Transkun V2 2.98 / 0.58 -> 2.68 / 0.58; Aria-AMT 7.52 / 2.25 -> 7.32 /
  2.34).
- Rule P strong on the floor: Transkun V2 0.40 -> 0.40%, Aria-AMT 1.48 -> 1.55%.
- `TRANSCRIBED_STRONG_LIMITS` (not used by default): wrong-pitch q99 2 -> 2 in both families;
  missed per note q99 0.308 -> 0.308 (Transkun V2), 0.771 -> 0.769 (Aria-AMT).
- Floor wrong-pitch labels per 1,000 graded notes: 7.61 -> 8.50 (Transkun V2), 10.15 -> 11.45.
- Key-sensor constants (`CORRECTNESS_EXPERT_BARS`) are not affected by construction.
- Side finding: the cached `f08c_floor_tables.pkl` (used by Henry's reports) no longer matches
  the current checker exactly: relabelled with `fixed` today, 9 bars in 150 tables differ (10
  wrong-pitch and 10 missed counts), and the cache lacks `n_missed_fast_repeat` (known, BL-18b
  audit item 7).

**Other finding (information, BL-18b).** On these 16 pieces the interim rule P (R1(0) + run
rule) gives clean strong 1.49% [0.52, 2.59] (Transkun V2) and 1.86% [0.66, 3.19] (Aria-AMT)
under `fixed`, above BL-18b's band [0.30, 1.25]% by point estimate. "Scarbo" is the driver
(4.1% / 5.1% of its bars strong); without it 0.74% / 1.00%. BL-18b's C1 pass was one sample of 12
pieces; this second sample does not confirm it unconditionally.

## Threats to validity
- F1 has no ground truth on transcribed input; the new pairs it counts are an upper bound on
  false pairings. A precision check needs transcriptions of key-sensor recordings (Disklavier
  MIDI as truth), for example the A-01 controlled check or MAESTRO audio on the GPU box.
- Injected wrong pitches are synthetic (±1 / ±2, same timing as the original note). Real slips
  may sit further from the expected onset (or nearer).
- The criteria's thresholds were set after the dev run (disclosed in the pre-registration);
  the held-out repertoire differs from dev (higher baseline clean wrong-pitch rates: 6.6 / 10.1
  vs 4.6 / 7.5 per 1,000), so the dev reachability for F1 (0.99) was optimistic. After the run,
  F1's leave-one-piece-out range straddles the 15% bar, so the F1 reading is sample-dependent.
- Fallback multiplicity: three candidates were checked in order; only `wide` reached PARTIAL.
- Family equals corpus (Transkun V2 = PERiScoPe, Aria-AMT = Aria-MIDI).

## For the lead
1. **Apply the registered outcome** (default): keep 100 ms on all input. Code keeps the
   `wrong_pitch_window` option (default `"fixed"`), so no behaviour changes.
2. **Or adopt `tempo` for transcribed input as a disclosed deviation.** Arguments: F1 is an
   upper-bound proxy without ground truth, it misses by 0.02 pt of its 15% bar in Transkun V2,
   half of it comes from one piece, and every report-level harm criterion passes. Against: the
   Aria-AMT miss (16.8%) is not marginal, the bar was set before the run, and the R-06 / BL-18b
   lessons say to apply the reading word for word. If chosen, it needs a DECISIONS entry and the
   eval-auditor, then the wiring (provenance `transcribed` -> `tempo`, key-sensor unchanged), the
   floor-table rebuild (values above) and a Henry rerun into `henry_df13/`.
3. **Better next experiment:** a precision check of new clean pairs against ground truth
   (transcriptions of Disklavier recordings), which would replace F1's upper bound with a
   measured false-pairing rate; and the aligner re-match (the unreachable half), e.g. a
   cross-pitch variant of the BL-23 post-pass, pre-registered with its own repair / break check.
4. **BL-18b C1 on a second sample:** P clean strong is 1.49 / 1.86% here, above 1.25%; worth a
   look at "Scarbo"-like pieces (high transcription error) before calling R1(0) + run rule
   confirmed.
