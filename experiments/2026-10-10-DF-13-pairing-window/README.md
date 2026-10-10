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

## Audit (eval-auditor, 2026-10-10)

**Verdict: Confirmed with caveats.** Every headline number reproduces, and "FAIL by the
pre-registered rule" is the correct reading. Keeping 100 ms with no deviation is the registered
outcome. The required fixes below are wording only and do not touch the verdict. Scratch work is
in the session scratchpad (`df13a/`). No code or data were changed.

**1. Pre-registration, ordering and the held-out draw (verified).**
- The anchor command in "Falsified if" gives `44bd842e6182f60be8d883bbe219ffc54552f18e1d22f050bd94c6d321fb771f`,
  which matches `artifacts/prereg_sha256.txt`.
- Timeline from the author transcript (`subagents/agent-a4ea7f2f6dc000885.jsonl`, UTC):
  - 20:12-20:40: dev runs and dev-only sweeps.
  - 20:40:56: eligible-pool count. The script counts only; it draws nothing.
  - 20:41:36: section appended. Its first hash ended `...1214`.
  - 20:41:44: one sentence of the dev description reworded. This produced the final hash.
  - 20:41:50: hash file written.
  - 20:42:09: held-out launched. The code hash at launch, `7bf82ad7...4490`, equals the
    committed `f5761c9` diff plus script, so nothing in the evaluation changed after the launch.
  - Outputs: `heldout_rows.pkl` was written at 21:27 and `heldout_summary.json` at 21:29. No
    later held-out re-evaluation.
- `heldout_jobs()` re-run today reproduces the draw exactly: 241 eligible, 800 jobs, the same
  ids, roles and order.
- Disjointness: no piece id is shared with the BL-18b dev set, Henry's 5 A-01 floor pieces
  (BL-18 T1), BL-18 T2 or BL-18b. 0 of the 800 transcription ids appear in the floor, BL-18 or
  BL-18b tables. Two held-out movements are siblings of earlier pieces (Beethoven Op. 14 No. 2
  i vs dev ii; Op. 106 i vs T2 iv), which is acceptable. This was checked by id only, not by
  score content. Nothing is fitted, and the constants were chosen on dev only.

**2. Criteria recomputed (all reproduce).**
- All of B1, M1, F1, R1, R2, E1 and D1 were recomputed independently from
  `heldout_piece_sums.csv` (ratio of summed counts per family). They equal `heldout_summary.json`
  and the README table to the printed precision.
- Selected values (Transkun V2 / Aria-AMT):

  | Criterion | Value |
  |---|---|
  | B1 | +3.64 / +4.69 pt |
  | M1 | +0.75 / +0.68 pt |
  | F1 | +15.02% / +16.78% (+0.99 / +1.69 per 1,000) |
  | R1 | +0.03 / +0.06 pt |
  | R2 | +0.14 / +0.19 pt |
  | E0 -> E1 | 73.0 -> 78.4 / 69.0 -> 76.2% |
  | D1 | strict +3.6 / +5.5 pt, mispair +1.04 / +1.19 pt, clean fast +21.3 / +24.4% |
  | `error` | F1 15.7 / 18.2%; D1 mispair 1.63 pt; D1 clean fast 26.7% |
  | `wide` | F1 14.72 / 16.78%; D1 clean fast 26.0% (Aria-AMT) |

- Code checks:
  - Denominators: B1 and M1 use injected notes in non-suspect targeted copies (4,287 / 4,239).
    F1 uses graded score notes of all non-suspect experts and targets (1,129,224 / 1,056,965).
    R1 and R2 use targets' clean bars outside runs (27,224 / 26,634). E1 uses targeted bars of
    non-suspect copies (1,429 / 1,413). The README's 1,439 / 1,443 counts bars before 4 suspect
    copies were dropped.
  - Families are never pooled for a verdict. Each target's expert tables are relabelled with
    the same rule.
  - Tolerances are as registered: two-sided for R1 and R2, floor and ceiling for B1 and E1. The
    verdict logic (PASS in both families / PARTIAL / FAIL) matches the text.
  - The Aria-AMT F1 for `tempo` and `wide` is identical (16.78%) because both add 1,791 clean
    pairs in total. The per-piece counts differ, so this is a coincidence, not a bug.
- CIs are piece bootstraps over 16 pieces, with t-intervals. One caveat: the t-interval is on
  the unweighted mean of per-piece rates, while the point value is a ratio of sums. They are
  different estimands, which is why Transkun V2 F1 is +0.99 with t [0.24, 1.05].

**3. The dev "re-match" finding (computed correctly; the mechanism needs two qualifiers).**
- Regeneration: I rebuilt every targeted copy from the raw transcriptions with the script's own
  functions (dev 238, held-out 303 non-suspect copies). The stored `fixed` outcomes reproduce
  6,765 / 6,765 (dev) and 8,526 / 8,526 (held-out): label, partner and intended-note label.
- Dev counts reproduce: of the unpaired injected notes, 146 / 342 and 215 / 449 have the
  intended score note missed.
- The intended note is the injected note's partner in the clean alignment, which is the right
  definition. In every "re-matched" case the performed note that now holds the intended score
  note has the intended note's pitch (100%, both sets). The author's 0.28 / 0.37 s is the
  distance to the leave-one-out expected onset in the targeted copy (author transcript,
  20:04:56).
- **Qualifier (a), dev collisions.** On dev, 43% (Transkun V2) / 30% (Aria-AMT) of the notes
  that took the intended score note are themselves injected notes, whose new pitch equals the
  intended note's pitch. That is the collision mechanism, so the dev "re-match half" partly
  overlaps with collisions. On held-out (collision-free) the share is 0, and the
  window-reachable share of unpaired notes rises from 43 / 48% to 55 / 57%.
- **Qualifier (b), held-out duplicate matches.** On held-out, 30 of 188 (Transkun V2) and 16 of
  225 (Aria-AMT) "re-matched" intended notes are not re-matched at all. parangonar-dualdtw
  matched one performed note to two same-pitch score notes, and `correctness()` labels both
  correct, so the performed note keeps its own score note and the intended note is never
  marked missed. On dev this happens in 1 and 2 cases.
  - It also happens on clean data: 0.41 / 0.54 per 1,000 graded score notes on held-out clean
    transcriptions are in such shared groups (0.42 / 0.40 on dev), and 20-30% of clean copies
    have at least one.
  - This is a small, separate correctness defect (it hides missed notes). It is not registered
    in DEFECTS. DF-07 covers a different parangonar ornament case. The BL-19b author saw the
    same duplicates on PianoVAM today.
- "In the clean copy that note was mostly matched to another score note" holds on dev (79% /
  69%). On held-out it was an extra in the clean copy in 39% / 44% of cases.
- "Intended not missed" also includes intended notes paired as a wrong pitch with another note
  (14 / 22 dev, 23 / 23 held-out) and grace notes (`ornament_skipped`). These are a minority,
  not re-matches.

**4. Collision fix (real, and it does not change bar selection).**
- 0 collisions on held-out, both in the stored outputs and recomputed against the clean score
  bar's written pitches.
- With the same seed, I ran `targeted_copy` with and without the fix on the same targets:
  - Chosen bars: held-out 1,438 / 1,439 and 1,441 / 1,443 shared; dev 1,130 / 1,130 and
    1,124 / 1,125 shared.
  - Bars per piece: identical.
  - Share of ±1 deltas: unchanged within 0.4 pt.
  - Sign: shifts by up to 3.7 pt (dev Transkun V2 upward share 45.7 -> 49.4%).
- So the fix changes only which pitch the retry picks. It does narrow the error model: an
  injected pitch is never written in its bar. That excluded 17.3 / 10.3% of held-out injections
  under the old rule (23.7 / 15.3% on dev). E0 = 73.0 / 69.0% is therefore the end-to-end share
  for out-of-bar slips only. Within dev, the collision-free notes still lose 14.5 / 19.1% of
  strict recall (absorbed 0.7 / 0.7%), so "collisions were not the main loss" holds without
  the cross-set comparison.
- Held-out absorption of 2.2 / 2.5% is concentrated in Debussy L. 123 No. 4 (18.5 / 22.0% of
  its injected notes). The mechanism was not checked.

**5. Default behaviour unchanged (verified).**
- The pre-DF-13 `correctness.py` (10403a5) and the current default return identical notes,
  score notes, bars and summary on:
  - all 320 held-out and 240 dev target transcriptions (clean) and all 541 non-suspect
    targeted copies (transcribed path);
  - 40 ASAP Disklavier mistake copies (12 sources, rates 0-0.1), both under the aligner and
    under the ground-truth alignment (key-sensor path).
- `params` gains one key, which nothing in `src` or `scripts` reads. No caller passes
  `wrong_pitch_window` except the two DF-13 scripts.
- Gates: `uv run pytest -q`: 565 passed, 8 skipped. `uv run ruff check src tests`: all checks
  passed.

**6. The side findings and what they mean for BL-18b's interim R1(0) + run rule.**
- **F1 and "Scarbo".**
  - Reproduced: "Scarbo" holds 51 / 55% of the added clean pairs and 38 / 36% of the baseline
    labels. Leave-one-piece-out ranges are 11.9-18.4% and 11.8-20.6%.
  - The range hides the structure. Only dropping "Scarbo" brings F1 under 15%: 11 of 16
    (Transkun V2) and 15 of 16 (Aria-AMT) single-piece drops still fail.
  - The piece bootstrap of the relative F1 is [6.5, 21.5]% / [7.1, 23.3]%. Only 48% / 36% of
    resamples are at or under 15%.
  - The held-out-minus-dev difference is +6.2 [-3.9, +14.1] / +7.2 [-4.0, +15.9] pt, so the
    held-out rise over dev (8.9 / 9.5%) is within piece-sampling noise.
  - Reading: F1 is not resolved in either direction, and the FAIL rests on the point
    estimate, exactly as registered. This has no bearing on BL-18b.
  - The pre-registered reachability (F1 passes with 0.99) came from resampling 12 dev pieces,
    none with a baseline above 10.5 per 1,000 ("Scarbo": 15.7 / 28.3), so it could not anticipate a "Scarbo".
- **P clean strong 1.49 / 1.86% (bootstrap [0.52, 2.59] / [0.66, 3.19]).**
  - This is the same measurement as BL-18b C1: dev under `fixed` reproduces C1 exactly. So it
    is a second sample, and on it C1 would fail by point estimate in both families. The
    intervals include the band, so the sample does not show that C1 is false either.
  - "Scarbo" holds 250 of 405 and 284 of 494 strong bars. But it is not the only piece above
    the band: 4 of 16 (Transkun V2) and 6 of 16 (Aria-AMT) pieces exceed 1.25%, against 0 of 12
    and 3 of 12 on BL-18b. The others are Chopin Op. 66 (2.1 / 3.6%), Op. 35/3 (2.6 / 3.9%),
    Op. 25 No. 5 (1.5%, Aria-AMT), Schumann Op. 16 No. 2 (1.4%, Transkun V2), Debussy L. 123
    No. 4 (1.4%, Aria-AMT) and Gnossienne No. 1 (3.6% on 110 bars, Aria-AMT).
  - The rebuilt A-01 floor (Henry's 5 Chopin pieces, leave-one-out) gives Aria-AMT 1.48%, also
    above the band.
  - Meaning for R1(0) + run rule: it stays interim. The BL-18b audit wording "meets C1-C3 on
    one new sample of 12 pieces" must now add "not met by point estimate on DF-13's 16 pieces
    (1.49 / 1.86%)". The clean strong rate is piece-dependent, most of all for Aria-AMT. This
    does not argue for R0, which was worse on C1 in BL-18b. It argues against calling the
    rule confirmed, and for a piece-difficulty-aware limit or more references.
- **Cached `f08c_floor_tables.pkl`.**
  - Recomputed: 9 bars in 8 tables differ in wrong-pitch or missed counts (sum of absolute
    differences 10 and 10), as stated. The README omits that 44 bars in 25 tables differ in
    `n_extra`.
  - Effect on the floor: rule P strong is 0.40 / 1.51% from the cache against 0.40 / 1.48%
    rebuilt. F-08c checked notable+ (pooled) is 5.26 vs 5.25%. Every move is 0.03 pt or less.
  - So the staleness does not matter for the tier rule. It only means Henry's reports are not
    exactly reproducible from today's checker. Rebuild the cache (with `n_missed_fast_repeat`)
    the next time the floor is touched.

**7. Overreach and required fixes (author; text only).**
1. **Hash typo.** `DEFECTS.md` DF-13 row cites `44bd842e...1214`. The hash is
   `44bd842e...771f`; `...1214` is the tail of the pre-edit hash. The same typo is in the
   feature-engineer memory note and the commit message (the commit cannot be changed; note it
   in the next one).
2. **Fast runs.** The `EXPERIMENTS.md` row says "no added harm in fast runs". Replace with
   "fast-run criteria within tolerance (mispair +1.0 / +1.2 pt against 1.5; clean fast-run
   labels +21 / +24% against 25%)".
3. **F1 interval.** In the README (Verdict and Threats) and the EXPERIMENTS row, add the
   relative F1 bootstrap interval ([6.5, 21.5]% / [7.1, 23.3]%). Say that only removing
   "Scarbo" flips it (1 of 16 drops in each family), instead of "straddles". "One piece drives
   it" is fine for the share of added pairs.
4. **Re-match wording.** In the README, the DF-12 and DF-13 rows, and the pre-registration
   echo in "DF-13 results": the "aligner re-match" half includes collisions on dev (30-43% of
   the re-matching notes are injected notes) and duplicate matches on held-out (16% / 7%). Add
   one sentence. "Next lever is the aligner re-match" should name both: a cross-pitch re-pair
   post-pass, and rejecting duplicate matches in `correctness()`.
5. **"Scarbo is the driver" of P clean strong.** Add that 4 / 16 and 6 / 16 pieces are above
   1.25% without "Scarbo" (item 6), so the excess is not one piece.
6. **Floor side finding.** Add the 44 `n_extra` bars, and that floor P rates move by 0.03 pt or
   less.
7. **"F1 is an upper bound."** It bounds false pairings of the MIDI. For the learner, a
   transcriber pitch error labelled wrong pitch on a clean expert is still a false alarm. It
   was already a false missed + extra under `fixed`. R1 and R2 measure the learner-facing
   effect directly, and they passed. Reword so it does not read as "the real harm is smaller
   than F1".

**For the lead.** Applying the registered outcome is correct. Decide whether to open a defect
for duplicate matches in `correctness()` (item 3b). Update the BL-18b interim-rule wording with
the second-sample result (item 6).

### Corrections after the audit (2026-10-10)

By `feature-engineer`, applying the audit's item 7 (text only). The audit section, the run record
and the pre-registration are not edited; the anchor hash of the pre-registration was re-checked
after these corrections and is still `44bd842e...771f`.

1. **Hash tail.** The pre-registration hash is `44bd842e...771f`. `...1214` (the tail of the
   hash before a one-sentence reword at 20:41:44, ahead of the 20:42:09 held-out launch) was
   wrongly cited in `DEFECTS.md`, the `WORKBOARD.md` log line and the author's memory; all three
   are fixed. Commit `f5761c9`'s message carries the wrong tail too; history is not rewritten.
2. **Fast runs.** The fast-run criteria are within tolerance, not free of harm: mispair +1.0 /
   +1.2 pt (bar 1.5) and clean fast-run wrong-pitch labels +21 / +24% (bar 25%). The
   `EXPERIMENTS.md` row now says so.
3. **F1 interval (Verdict and Threats).** The piece-bootstrap 95% interval of the relative F1
   is [6.5, 21.5]% (Transkun V2) and [7.1, 23.3]% (Aria-AMT); only 48% / 36% of resamples are at
   or under 15%. Of the 16 leave-one-piece-out drops, only removing "Scarbo" brings F1 under 15%
   (1 of 16 in each family). This replaces "straddles the 15% bar". "One piece drives it"
   stays for the share of added pairs. F1 is not resolved in either direction; the FAIL rests
   on the point estimate, as registered.
4. **The "aligner re-match" half needs two qualifiers.** (a) On dev, 43% (Transkun V2) / 30%
   (Aria-AMT) of the performed notes that took the intended score note are themselves injected
   notes whose new pitch equals the intended pitch: that is the collision mechanism, so the dev
   "re-match half" overlaps with collisions. On held-out (collision-free) the share is 0 and the
   window-reachable share of unpaired notes is 55 / 57% (dev 43 / 48%). (b) On held-out, 30 of
   188 (Transkun V2) and 16 of 225 (Aria-AMT) "re-matched" intended notes are duplicate matches:
   parangonar-dualdtw matched one performed note to two same-pitch score notes and
   `correctness()` labels both correct, so the intended note is never marked missed. Next levers,
   both pre-registered on their own: a cross-pitch re-pair post-pass (the BL-23 post-pass
   extended to wrong pitches, with a repair / break check), and rejecting duplicate matches in
   `correctness()` (new defect DF-15).
5. **P clean strong is not one piece.** Besides "Scarbo", 4 of 16 (Transkun V2) and 6 of 16
   (Aria-AMT) pieces exceed 1.25% (0 of 12 and 3 of 12 on BL-18b); the rebuilt A-01 floor gives
   Aria-AMT 1.48%. The second-sample reading for BL-18b is added to its audit part in
   `docs/specs/report-validation.md`: C1 fails by point estimate on these 16 pieces, the
   intervals include the band, and R1(0) + run rule stays interim.
6. **Floor side finding.** Besides the 9 bars in 8 tables with different wrong-pitch or missed
   counts, 44 bars in 25 tables differ in `n_extra`. Floor rule P and F-08c rates move by 0.03 pt
   or less between the cache and today's checker, so the staleness does not matter for the tier
   rule; it only makes Henry's reports not exactly reproducible.
7. **What F1 bounds.** F1 is an upper bound on false pairings *of the MIDI* (some new pairs are
   real transcriber pitch errors). It is not a bound on learner-facing false alarms: a
   transcriber pitch error on a clean expert is a false alarm for the learner either way (a
   false missed + extra under `fixed`, a false wrong pitch under `tempo`). R1 and R2 measure the
   learner-facing effect directly, and both passed. The Verdict's "F1 ... is an upper bound"
   sentence and the "For the lead" item 2 should be read this way.

**Lead decision (2026-10-10):** the registered outcome is applied. 100 ms stays on all input; no
deviation. The `wrong_pitch_window` option stays in `correctness()` with default `"fixed"`.
