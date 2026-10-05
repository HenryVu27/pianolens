# BL-23: ornament whitelist and same-pitch reassignment

Ticket: BL-23 (with DF-10)    Hypothesis: none (validation of two labelling changes)    Status: Provisional

## Question

BL-20 found that in dense runs tier A misnames wrong keys: the aligner absorbs a wrong key that
equals a nearby written pitch, and the ornament whitelist (which ran before wrong-pitch pairing)
tolerates wrong keys near trills and grace notes. Do (a) a tighter ornament whitelist and (b) a
same-pitch reassignment post-pass close the dense/sparse gap without hiding genuine ornaments or
raising expert false flags?

## Pre-registration

`docs/specs/correctness-validation.md`, section "Pre-registration BL-23" (to end of file). sha256
`1444e93457d654dfdf977806b33f4329be9812ecc136afdd5063017af5b72146`, hashed 2026-09-29 16:58 CDT
before any variant was run on real data. Copy and hash in `artifacts/prereg_section.md` and
`artifacts/prereg_sha256.txt`. What was seen before the hash is listed in the section.

Variants (DF-10 pitch check on in all): `L` legacy; `T` tight whitelist (pair first, ornament's
own pitches only); `R` legacy plus the reassignment post-pass; `TR` both (the candidate).
Criteria for `TR`: C1 stress dense-N minus sparse-O clean-bar strict recall within ±0.10; C2 the
same on F-02 rate 0.05 (< 100 ms vs > 200 ms); C3 dense-N clean-bar detection >= 0.95; N1 sparse-O
not more than 0.02 below `L`; N2 F-02 bar precision and recall not more than 0.005 below `L` at
each rate; N3 at most 5% of legacy-tolerated ornament notes on clean expert copies become errors,
and at most 5% of their error-free bars become flagged; N4 expert false flags (F-08c, limits
recomputed per variant) within [-1.0, +0.5] points notable-or-strong and [-0.5, +0.25] strong.
Decision: `TR` becomes the default if N1-N4 hold; otherwise `T`, then `R`, by the same test.

## Data

- `data/processed/mistakes_v1` (D-08): 100 (n)ASAP performances, 62 pieces, rates 0 / 0.02 /
  0.05 / 0.10 (400 copies).
- BL-20 stress copies, rebuilt with the BL-20 generator and seeds (identical copies, see the
  reproduction check).
- F-08c calibration sets: 354 ASAP expert performances of the 28 covered pieces (40 covered clean
  copies), and the 150 A-01 floor transcriptions (Transkun V2 and Aria-AMT, 5 Chopin pieces).

## Method

`scripts/eval_correctness_bl23.py` (new) aligns every performance once and applies the four
variants to the same alignment, window 100 ms, modes `aligned` (primary) and `gt_alignment`.
It reuses `eval_correctness_density.py` (bar sets, outcomes, stress generator) and
`calibrate_expert_check_f08c.py` (tiers, rates, floor draw) unchanged. Code under test:
`features/correctness.py` (`ornament_rule`, `reassign`, DF-10 pitch check) and
`align/postpass.py` (new). Cluster bootstrap by source performance and by piece, 2,000
resamples, seed 20260929.

## Command

```
OMP_NUM_THREADS=1 uv run python scripts/eval_correctness_bl23.py --part run --workers 12
uv run python scripts/eval_correctness_bl23.py --part summary
```

## Run record

- 2026-09-29, M4 Pro, 1,004 jobs, 0 failures, 725 s (summary 83 s).
- Code: git `dd13ab2` plus uncommitted work. Script sha256 prefix `b04f0c26d876b846`,
  `postpass.py` `8de83ba3ac6fd6fa`. The run passed every variant's arguments explicitly; the
  default of `correctness` was changed only after the run (so `correctness.py` now hashes
  differently, `bec8a62abe3be634`).
- Outputs in `artifacts/` (gitignored): `f02_*.parquet`, `stress*.parquet`, `tables.pkl`,
  `summary.json`, `stress_clean_summary.csv`, `stress_gap_boot.csv`, `f02_bar_any.csv`,
  `f02_wrong_dense_sparse.csv`, `run.log`.

## Results

**Reproduction.** `L`, `aligned`, all injections reproduces BL-20 Part B exactly in every cell
(n 874 / 914 / 893 / 909; dense-N strict recall 0.681, absorbed 0.157; sparse-O 0.904 / 0.011).
So the DF-10 pitch check changes nothing under the legacy ornament rule (0 matches dissolved in
any set).

**Stress set, bars clean in the clean copy (`aligned`).**

| Variant | dense-N n | dense-N strict | dense-N detected | sparse-O strict | gap dense-N minus sparse-O [CI by source; by piece] |
|---|---|---|---|---|---|
| L | 370 | 0.786 | 0.932 | 0.942 | -0.156 [-0.219, -0.092]; [-0.228, -0.082] |
| T | 370 | 0.811 | 0.932 | 0.946 | -0.135 [-0.198, -0.074]; [-0.213, -0.063] |
| R | 373 | 0.807 | 0.930 | 0.942 | -0.135 [-0.197, -0.073]; [-0.210, -0.060] |
| TR | 373 | 0.836 | 0.930 | 0.946 | -0.109 [-0.168, -0.050]; [-0.187, -0.034] |

Dense-N outcome shares (clean bars): absorbed 0.114 (`L`, `T`) and 0.086 (`R`, `TR`); ornament
0.057 (`L`) / 0.067 (`R`) / 0.032 (`T`) / 0.038 (`TR`). With the ground-truth alignment the
gap is -0.126 (`L`), -0.058 (`T`), -0.139 (`R`), -0.072 (`TR`): the post-pass slightly hurts
there (it moves 2.2% of dense-N injections onto a written note, absorbed 0 -> 0.022).

**F-02 set, rate 0.05, injected wrong pitches in clean bars (`aligned`).** Strict recall
< 100 ms vs > 200 ms: `L` 0.860 vs 0.923, gap -0.063 [-0.113, -0.015]; `R` -0.048 [-0.096,
-0.003]; `T` -0.056; `TR` 0.881 vs 0.923, -0.042 [-0.089, 0.003].

**F-02 bar any-error (`aligned`), precision / recall.**

| Rate | L | R | T | TR |
|---|---|---|---|---|
| 0.02 | 0.9784 / 0.9766 | 0.9789 / 0.9771 | 0.9784 / 0.9789 | 0.9789 / 0.9795 |
| 0.05 | 0.9897 / 0.9837 | 0.9900 / 0.9836 | 0.9895 / 0.9850 | 0.9898 / 0.9848 |
| 0.10 | 0.9931 / 0.9856 | 0.9935 / 0.9855 | 0.9927 / 0.9860 | 0.9931 / 0.9859 |

**N3, genuine ornaments.** On the 100 clean copies `L` tolerates 2,895 performed notes (2,694
ornament extras, 201 different-pitch matches). `TR` labels 6.5% of them as errors (98 extra, 90
wrong pitch), `T` 6.7%, `R` 0%. Of the 252 bars error-free under `L` that hold such notes, `TR`
flags 9.9%, `T` 10.3%, `R` 0%. The different-pitch matches are hit hardest: 28.4% of them become
errors under the tight rule (58 matches dissolved per clean-copy set; mordents, inverted mordents
and tremolos realised on the side the rule excludes).

**N4, expert false flags (F-08c q80 / q99; limits recomputed per variant), notable-or-strong /
strong.**

| Variant | Key-sensor (5,482 bars) | Transcribed floor (extras not counted) |
|---|---|---|
| L | 3.67% / 0.67% | 5.26% / 1.41% |
| R | 3.68% / 0.69% | 5.25% / 1.41% |
| T | 3.65% / 0.69% | 5.22% / 1.40% |
| TR | 3.68% / 0.71% | 5.20% / 1.41% |

`L` reproduces the published F-08c row (3.7% / 0.67%; 5.3% / 1.4%). The recomputed expert limits
are identical for `L` and `R` (wrong pitch q95 1, q99 2; missed+extra per note 0.267 / 0.634;
missed per note 0.158 / 0.286); `T`/`TR` raise missed+extra q99 to 0.642.

**DF-10.** The 26 BL-20 absorptions at a different pitch are all parangonar ornament matches
within ±2 semitones of a trill, turn, mordent, inverted mordent, wavy line or tremolo, so the
documented legacy ornament rule keeps them correct: under `L` and `R` all 26 stay absorbed; under
the tight rule 3 change (2 paired with the intended note, 1 with another). The post-pass moved
291 matches on the 100 clean copies and 1,232 in the stress copies (`aligned`).

## Verdict (Provisional): candidate fails; fallback `R` adopted, partial improvement

Against the pre-registered criteria for `TR`: C1 **fails** narrowly (-0.109, outside -0.10);
C2 passes (-0.042); C3 **fails** (0.930); N1 passes (+0.002 on 534 bars clean under both);
N2 passes (no drop, largest change +0.003); N3 **fails** (6.5% of notes, 9.9% of bars, both above
5%); N4 passes (all changes within ±0.1 point). `T` also fails N3 (6.7%, 10.3%).

By the pre-registered decision rule, `R` is checked next: N1 +0.000, N2 all changes within
[-0.0001, +0.0005], N3 0% / 0%, N4 +0.01 / +0.02 points (key-sensor), -0.01 / 0.00
(transcribed); it improves dense-N clean-bar strict recall (0.786 -> 0.807). **`R` is now the
default** (`correctness(reassign=True)`, `ornament_rule="legacy"`). None of C1-C3 hold for `R`
(gap -0.135, detection 0.930).

What it means: the post-pass removes about a quarter of dense-N absorption (0.114 -> 0.086) at no
measured cost, but the dense/sparse naming gap stays above 0.10, and in about 1 in 14 clean dense
bars an injected wrong key that equals a nearby written pitch is still not flagged. Tightening
the whitelist would help (`TR` gets closest) but it flags real ornament playing in expert
performances, mostly ornaments played on the side that the MusicXML ornament name does not
predict. BL-20 proposal 3 (bar-level wording in runs under 100 ms) remains the product-side
mitigation.

## Changes made

- `features/correctness.py`: DF-10 pitch check on matches (with forced wrong-pitch pairing of a
  dissolved match); `ornament_rule` ("legacy" default, "tight" available); `reassign` (default
  True); summary counters `n_ornament_matches`, `n_pitch_dissolved`, `n_reassigned`.
- `align/postpass.py`: `reassign_same_pitch`, `loo_expected_onsets`.
- `report/calibration.py`: `share_bars_with_error_median` 0.421 -> 0.420 (the only label-dependent
  constant that moved at its precision). BL-18 constants untouched.
- Tests in `tests/features/test_correctness.py`.

## Threats to validity

- Synthetic isolated wrong keys on expert Disklavier playing (as BL-20).
- N3 treats every note the legacy rule tolerates as a genuine ornament. Some are real slips that
  the legacy whitelist hides, so N3 overstates the tight rule's cost by an unknown amount. No
  labels separate them.
- The tight pitch sets use semitone ranges by MusicXML ornament name, not the key-aware diatonic
  auxiliary, and engravers use mordent / inverted mordent inconsistently.
- The post-pass has two fixed constants (30 ms, 100 ms), not tuned; other values were not tried.
- Clean-bar sets differ slightly between variants (N1 uses the intersection).

## Audit (2026-09-29)

Auditor: eval-auditor. **Verdict: Confirmed with caveats.** The candidate `TR` fails, the
pre-registered fallback was applied correctly, and `R` as the default is supported. The caveats
change how the result is explained, not the decision.

**Pre-registration and order.** The section from `## Pre-registration BL-23` to EOF hashes to
`1444e934...2146` (the file on disk and `artifacts/prereg_section.md` are identical). Author
transcript (session 9591b65d, subagent `agent-acbc9f10b77284aba`): the section was appended at
21:58:46Z and hashed at 21:58:52Z. `scripts/eval_correctness_bl23.py` was written at 22:00:42Z
and run at 22:01:34Z. Before the hash, the author looked at BL-20 artifacts (the 26
different-pitch absorptions), counted ornament names, and ran the DF-09 catalogue and one
Gondoliera control-features call. All of this is disclosed or unrelated to the labeller. No
labeller variant ran on real data before the hash. The fallback is pre-registered word for word:
"If `TR` fails any of N1-N4, `T` and then `R` are checked against N1-N4 in that order and the
first that passes and improves dense-N strict recall becomes the default". `TR` fails N3, `T`
fails N3, and `R` passes N1-N4, so `R` is the correct outcome of the rule. C1-C3 are not
required for the default, and the README says that they fail for `R`.

**Reproduction.** Hashes match the run record (script `b04f0c26d876b846`, `postpass.py`
`8de83ba3ac6fd6fa`, `correctness.py` `bec8a62abe3be634`). A full rerun (`--part all --workers
12 --out <scratch>`, 755 s, 0 failures) gives a byte-identical `summary.json`,
`stress_clean_summary.csv`, `stress_gap_boot.csv`, `f02_bar_any.csv` and
`f02_wrong_dense_sparse.csv`. Every number in the Results section matches `summary.json`, with
one exception: `R`'s key-sensor N4 change is +0.02 points for notable-or-strong as well
(3.667% -> 3.685%), not +0.01.

**R vs L, paired.** On the 370 dense-N injections whose bar is clean under both `L` and `R`
(`aligned`), strict recall rises by +0.022 [0.008, 0.037] (bootstrap by source, 2,000, seed
20260929): 9 gains and 1 loss. Over all 874 dense-N injections, 27 go from absorbed to paired
with the intended note and 4 lose strict pairing (2 become absorbed, 2 become extra). So the
gain is real, but small.

**Over-reassignment on real data (the `gt_alignment` drop).** Under the ground-truth alignment,
every swap moves a correct match by construction, so the fall from 0.840 to 0.827 (absorbed 0 to
0.022, 8 of 369) shows the rule's false-move rate, not a flaw special to that mode. Bar detection
is unchanged there (0.973 for both). To measure false moves on real alignments, I recorded every
swap on the clean expert copies (`aligned`) and checked each one against the nASAP ground truth:

| Set | Swaps | New partner = ground truth ("fix") | Old partner = ground truth ("break") | Neither | Score note unmatched in ground truth |
|---|---|---|---|---|---|
| Clean copies (rate 0) | 291 | 230 | 35 | 23 | 3 |
| Rate 0.05 copies | 382 | 302 | 46 | 32 | 2 |
| Clean copies, `gt_alignment` | 147 | 0 | 147 | 0 | 0 |

About 79% of swaps on real alignments repair an aligner error. About 12% move a correct match,
6.6 repairs for every break. On clean playing a swap rarely changes the error count (bar
precision/recall, N3 and N4 are all unchanged). So over-reassignment is real: about 1 swap in 8,
and about 35 per 100 expert performances. It is outweighed, and it mostly misnames which note
was played rather than creating or hiding flagged bars. Report this rate next to the gain.

**N3: real harm, not hidden slips.** The failure is robust and mostly comes from one piece:
- **Schubert D899/1** (2 performances). It supplies 1,309 of the 2,895 legacy-tolerated notes
  (45%) and 124 of the 188 notes that `TR` re-flags, including 47 of the 57 dissolved
  different-pitch matches. Its score carries 172 `tremolo` marks, which are unexpanded
  repeated-chord abbreviations. The tight rule allows a tremolo only its own pitch, so it flags
  the other re-struck chord notes that are written as abbreviations.
- **Recurring flags elsewhere.** Of the other 64 flags, 34 recur at the same bar in at least 2
  performers of the same piece (Haydn 31-1 and 50-1, Liszt S.139/5). That is systematic ornament
  realisation.
- **Possible slips.** At most 30 flags (1.0% of 2,895) are single-performer cases that could be
  real slips.

Even if all 30 are counted as slips, at least 158 / 2,895 = 5.5% remain, which is above 5%.
Without Schubert D899/1, the note share is 4.0% (64 / 1,586), which passes, but the bar share
is 8.4% (19 / 225), which still fails. The README's explanation ("mostly ornaments played on the
side that the MusicXML ornament name does not predict") is wrong for the note share. The main
cause is unexpanded tremolo notation. The "28.4% of different-pitch matches" is 47 / 48 in
Schubert D899/1 and 10 / 153 elsewhere. The threat that "some are real slips" is bounded above by
1.0% of notes.

**DF-10: zero by construction, not an empirical zero.** parangonar creates a different-pitch
match only in its ornament step. That step is limited to score notes with a partitura
`ornaments` entry and pitches within ±2 (`parangonar/match/matchers.py` about line 1401), and
`align.core.align_note_arrays` turns it on only when a score part is passed. The legacy rule
allows exactly those matches (ornamented or grace, |dp| <= 2). So under the default the pitch
check cannot dissolve anything, and "0 dissolved in any set" follows from the code. It is not a
finding about real data. It becomes active only under the tight rule or with another aligner.
Also, the calibration jobs (`asap_one`, `floor_one`) do not record `n_pitch_dissolved`, so for
the 354 experts and 150 transcriptions the zero comes from this argument, not from a count. The
defect's symptom, 26 wrong keys labelled correct, is unchanged under the default (26 / 26 remain
absorbed under `L` and `R`).

**Calibration.** The `R` limits equal `L`'s at the precision stored in `report/calibration.py`
(`summary.json` N4):
- share of bars with an error, median: 0.4210 -> 0.4202;
- `error_rate` q95: 0.16410 -> 0.16392;
- `error_rate` q99: 0.20664 -> 0.20691;
- `missed_extra_per_note_q95`: 0.26675 -> 0.26667;
- `missed_per_note_q95`: 0.15800 -> 0.15789.

Only one comment changes: bars with >= 3 wrong pitches go from 0.850% to 0.858%, so the comment
"0.85%" would now round to 0.86%. The app's result cache key (`app/jobs.code_version`) hashes
all of `src/pianolens`, so old results are not reused. Not done: the pre-registration says the
BL-18 transcribed strong-tier constants are "reported". The README says only "untouched" and
gives no recomputed values. The N4 transcribed rows per transcriber are identical for `L` and
`R` to 4 decimals, except Transkun notable-or-strong (2.994% -> 2.982%), so a change is
unlikely.

**DF-09 (catalogue rerun).**
- **Reproduction.** An independent rerun of `staff_hand_proxies.py` (137 s) reproduces the
  author's scratch output exactly: 805 scores, 0 with zero events (was 25 plus 3 unreadable),
  314,448 events, 0 notes off staves 1 and 2. Against the BL-19 artifact, 73 pieces change (70
  plus the 3 now readable): 66 up, 4 down.
- **The 4 pieces that went down.**
  - Scriabin Op. 53 (731 -> 726) has an extra 1-staff part (47 bass notes), which now joins the
    lower staff. This is correct.
  - The other three are **piano four-hands duets**, each with two 2-staff parts: Fauré Dolly
    Op. 56/1 (parts "Prima" and "Seconda"), Dvořák Op. 72/2, and Ravel *Ma mère l'Oye* 5 (parts
    "Piano 1" and "Piano 2"). The "two fullest staves" rule splits them three different ways:
    - Dvořák: upper = primo (both hands), lower = secondo.
    - Fauré: upper = primo plus secondo right hand, lower = secondo left hand only.
    - Ravel: upper = primo right hand only, lower = primo left hand plus secondo.

    Hand synchrony between two "hands" means nothing for four hands under either numbering. The
    fix is right for solo scores and arbitrary for duets.
- **Other multi-part checks.** Rachmaninoff Op. 3/2 (4 staves in 2 parts) now puts the lower
  system on staff 2, which is correct (212 -> 278). Bach three-voice fugues put the middle voice
  with the bass. In Chopin Op. 29, a part named "Flauta" (959 notes) sits above the piano, and
  the piano's upper staff is assigned by a mean-pitch margin of 0.1 semitone. The result is the
  same as before (482 events), but the rule is fragile there.

**Required fixes (text only; no rerun needed).**
1. N3 paragraph and "What it means": replace "mostly ornaments played on the side ... does not
   predict" with the breakdown above (Schubert D899/1 tremolo abbreviations 124 / 188, recurring
   Haydn and Liszt ornaments 34, possible slips at most 30). State that N3 still fails without
   Schubert on the bar share (8.4%).
2. DF-10 paragraph and reproduction line: "0 dissolved" is structural under the legacy rule
   (parangonar makes different-pitch matches only for ornamented notes within ±2), and the
   calibration sets were not counted.
3. Add the post-pass precision table (79% repairs, 12% breaks on real alignments) and the paired
   R - L interval (+0.022 [0.008, 0.037]) to the Results. Treat the `gt_alignment` drop as the
   false-move rate.
4. N4 for `R`, key-sensor: +0.02 / +0.02 points. Report the recomputed BL-18 transcribed limits,
   or say that they were not recomputed.
5. Threats: add that the N3 denominator is 45% one piece, and that four-hands duets in the
   catalogue get arbitrary hand splits under DF-09.

**Follow-ups for the lead (not blocking).**
- Expand tremolo abbreviations, or exclude them from the ornament rule, before any tight-rule
  retest. The tight rule without Schubert D899/1 passes the N3 note share and fails only the bar
  share.
- Flag four-hands scores (two parts, each with 2 staves, or part names Primo/Secondo/Piano 1/2)
  in the app catalogue, since per-hand features do not apply to them.
- The C1 gap (-0.135 for `R`) is still open; BL-20 proposal 3 (bar-level wording in fast runs)
  remains the product mitigation.
