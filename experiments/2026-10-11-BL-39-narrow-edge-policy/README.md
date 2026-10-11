# BL-39: narrower edge-bar policy for partial recordings
Ticket: BL-39 (from the BL-37 audit)    Hypothesis: none from the plan (report rule)    Status: Provisional

## Question
With `align(..., partial=True)` and BL-37's fixes, the first or last recorded bar of a trimmed
span is graded about as often as the same bar uncut. But a partly played cut bar is still
tiered strong about 20% of the time with no policy (k = 0).

BL-37's k = 1 policy removes those flags but hides real omissions in the edge bar: 3 omitted
notes are ranked 60.2% of the time at k = 0, 17.3% at k = 1, and never on the aligner's own
edge bar.

The narrower policy tested here makes low confidence only the missed notes that lie outside the
recorded part of the edge bar: due before the first note matched in it on a start side, or
after the last on an end side. Does it:
- remove the false flags on cut bars,
- keep omissions that lie inside the recorded part,
- and disclose, with a registered bar, the cost on omissions of the bar's own first (last)
  notes?

## Pre-registration

Written 2026-10-11 after dev runs on 44 seen pieces (BL-36 dev, BL-36 held-out, BL-37
held-out), before any BL-39 held-out piece was drawn or aligned. The anchor hash is recorded in
"Falsified if".

**Candidate (one; no fallback).** `ReportConfig(edge_low_confidence_bars=1,
edge_low_confidence_rule="outside", edge_outside_basis="score_le")`
(`report.build.edge_outside_notes`). In N's first graded bar on a trimmed start side, the
missed notes due at or before the score position of the first matched note (correct or wrong
pitch) are low confidence: shown, not counted towards the tier. "At or before" includes the
matched note's chord partners. On a trimmed end side, the same applies to notes at or after the
last matched note. A bar with no matched note is outside entirely. Wrong pitches always count.

**Comparators, shown in every table:**
- **k = 0:** no policy.
- **k = 1:** BL-37: every missed note of that bar is low confidence.

**Sabotage variants (bite checks only, never adoptable):**
- **k = 2:** every missed note of the first or last two graded bars.
- **"up to the second matched onset":** the candidate rule extended past the first matched
  onset to the second.

**Methods and truth.**
- **Tiers:** rule P as in BL-36 / BL-37 (R1(0), 15 same-family experts, extras not counted,
  "passage not heard" runs untiered, computed from the real missed counts).
- **The policy changes tiers only.** The offline evaluation reduces each edge bar's missed
  count by the candidate's low-confidence count before tiering, which equals what
  `_correctness_section` does for rule P (fast repeats off).
- **N:** `align(..., partial=True)` with the clean repeat path. **Na:** N with repeat path
  "auto". **C:** today's full alignment, computed separately.
- **Truncation kinds:** start, end, both and excerpt, as BL-36 / BL-37, with the same seeds and
  truth. The 4-7-bar kind "short" is information only.

**Injections.** Every one targets a first or last recorded bar (`d = 0`: the played bar next to
a removed side, found by the clean copy, with at least 4 correct notes and no wrong pitch). The
modified cut copy is realigned by N.
- **Wrong pitches** (BL-37 D1 / D2): 3 correct notes get BL-18b's wrong-pitch deltas. Counted
  where every expert has at most 1 wrong pitch in the bar.
- **Inner omissions (O1):** 3 correct notes are deleted, chosen at random among those not at
  the bar's first onset on a start side (not at its last onset on an end side), seed
  `[39, crc32(id)]`. The candidate should still catch them.
- **Lead omissions (O2):** the bar's first 3 correct notes in score order (last 3 on an end
  side) are deleted. The candidate hides these by design; this row is the disclosed cost.
- O1 and O2 count where every expert has at most 1 missed note in the bar.

**Statistics.** Every row is the mean over pieces of a per-piece value. Values are in points:
the per-piece mean of (tier under the policy) - (reference) over the row's bars. Piece
bootstrap (2,000, seed 0) and leave-one-piece-out are reported.

**Registered rows (all must pass for the candidate):**

| Row | Statistic (candidate) | Bar |
|---|---|---|
| E1 | first / last recorded bars (no note lost to the cut): strong, minus the same bars uncut | within [-1.0, +1.5] |
| E2 | partly played cut bars: strong, minus the same bars uncut | at most +1.5 |
| D1 | wrong-pitch edge bars: strong, minus k = 0 | at least -5.0 |
| D2 | the same, notable or strong | at least -8.0 |
| O1 | inner-omission edge bars: notable or strong, minus k = 0 | at least -8.0 |
| O2 | lead-omission edge bars: notable or strong, minus k = 0 (disclosed cost) | at least -50.0 |
| T2 | never-played bars tiered (notable or strong) under the candidate, per-piece share | at most 0.03 |
| R2 | the same on Na | at most 0.03 |
| H1 | evidently-full natural targets only: rule P strong / notable+ under N with the candidate, minus C, per family (BL-36 definition of "evidently full") | within ±0.15 / ±0.30 pt |
| T1, T3, R1, R3, H2 | BL-36 rows (alignment level; unaffected by the policy), BL-36 bars | as BL-36 |
| W1 | natural targets whose span is whole and unrefined: C and N identical (alignment pairs, score notes, measures, labels, correctness tables and summary), C computed separately | all |

**Outcome.**
- **PASS** = every row passes. Then the recommendation is `partial=True` with the candidate
  configuration, after the audit and the lead's and Henry's decision.
- **FAIL** otherwise. Then **no policy is adopted** (k = 0); there is no fallback to k = 1,
  whose harm is already measured (BL-37 audit). The failing rows are reported.
- Either way the flags stay off (`PARTIAL_DEFAULT` False, `edge_low_confidence_bars` 0) until
  then.

**Information, not deciding:** the rows for k = 0, k = 1 and the two sabotages; absolute rates
(edge, cut, injected strong and notable or strong); "short" excerpts; per family and per kind.

**Dev (design data; disclosed).**
- **Data:** 3 targets per piece and family from 44 seen pieces (BL-36 dev, BL-36 held-out,
  BL-37 held-out), 258 usable targets (6 suspect), experts from those runs' caches.
- **Choices made on dev after seeing results:**
  - the boundary basis among five variants;
  - the k = 2 and second-onset sabotage variants for the bite checks;
  - the O2 bar (-45 tried first, then -50, chosen by resample pass share).
- **Dev values (points; mean over 44 pieces):**

  | Policy | E1 | E2 | D1 | D2 | O1 | O2 |
  |---|---|---|---|---|---|---|
  | k = 0 | +0.60 | **+16.53** | 0 | 0 | 0 | 0 |
  | k = 1 | +0.21 | -1.04 | -0.70 | -4.07 | **-44.10** | -41.33 |
  | candidate | +0.41 | +0.91 | -0.39 | -1.48 | -1.69 | -38.01 |
  | score position, strict | +0.53 | **+3.26** | -0.15 | -0.41 | -0.99 | -27.50 |
  | expected onset (tolerance 0 / 0.05 / 0.10 s) | +0.53 | **+4.3 to +4.6** | | | -0.9 to -1.0 | -26 to -27 |
  | sabotage, up to the second matched onset | +0.41 | -0.44 | -0.52 | -2.47 | **-16.21** | -41.16 |
  | sabotage, k = 2 | -0.18 | -1.04 | -1.53 | -5.33 | **-63.86** | **-60.43** |

  - Candidate absolute rates: edge bars strong 1.11% (uncut 0.71%); cut bars 2.28% (uncut 1.37%,
    k = 0 17.9%).
  - Inner omissions are caught (notable or strong) 62.5% vs 64.1% at k = 0 and 20.1% at k = 1.
  - Lead omissions are caught 23.2% vs 61.2% at k = 0 and 19.9% at k = 1.
- **No-regression rows on dev under the candidate:**
  - T2 0.003, R2 0.003;
  - H1 (evidently full): Transkun V2 0 / 0, Aria-AMT -0.018 / -0.016;
  - T1 0.9979, T3 0.9986, R1 0.9942, R3 0.9990, H2 0.992 / 0.0001;
  - W1 251 of 251.
- **Bite checks (dev):**
  - E2 fails for k = 0.
  - O1 fails for k = 1 and for both sabotages.
  - O2 fails for k = 2 (and passes for k = 1, which O1 already rejects).
  - D1 / D2 are kept for continuity with BL-37: a missed-note policy cannot fail them by
    construction (BL-37 audit). They fail for capping or untiering edge bars (BL-37 dev, -42 to
    -59 pt).
- **What E2's residual is:** 19 dev cut bars are still strong under the candidate.
  - 17 of them are N's edge bar, and most of their missed notes lie inside the recorded part
    (for example 17 missed, 4 outside).
  - One was inspected note by note (Beethoven Op. 22/2, bar 53, end cut). There the cut copy's
    alignment lost notes due before the cut that the clean copy had matched.
  - The narrow rule cannot reach such notes without hiding inner omissions. The other 18 were
    not inspected one by one.
- **Reachability (2,000 resamples of 16 dev pieces):** the candidate passes every row in **74%**
  of resamples. The lowest rows are E2 0.75, O2 0.98 and O1 0.999.
  - So FAIL on held-out is a live outcome (about 1 in 4 by dev resampling, and more if
    held-out pieces differ from dev).
  - Leave-one-piece-out over dev: E2 0.70 to 1.14, O1 -1.73 to -0.90, O2 -38.96 to -37.19.

**Data.**
- **Pool:** PianoCoRe pieces with at least 25 transcriptions in each family and exactly one
  score in the archive.
- **Excluded pieces (every earlier draw):**
  - A-01 (Henry's 5);
  - BL-18 T2;
  - BL-18b = DF-13 dev = BL-27 dev = BL-36 dev;
  - DF-13 held-out, BL-27 held-out, BL-36 held-out, BL-37 held-out;
  - every piece in `piece_ids.SCORE_VERSION_MISMATCH`.
- **Excluded transcription ids:** every id used by the A-01 floor, BL-18, BL-18b, DF-13, BL-27,
  BL-36 or BL-37.
- **Draw** (`scripts/eval_edge_narrow_bl39.py`, `heldout_jobs`, seed 3939): as BL-36 / BL-37.
  - The eligible pieces are permuted. The first 8 with the literal-repeat flag and the first 8
    without it are taken.
  - Per piece and family: 15 experts and 10 targets.
  - **Then** `pianocore.guard_jobs` (after the seeded draw; the guarded count is reported).
  - Suspect alignments (match ratio below 0.8) are dropped.
- **Code at the hash:** HEAD 87be183 plus the uncommitted BL-39 diff (hashes in "Falsified
  if").

**Wrong-piece probe:** not run. An all-pairs probe would cost about as much as the main run, and
BL-40 owns the stop threshold.

**Run.**
```
OMP_NUM_THREADS=1 uv run python scripts/eval_edge_narrow_bl39.py --set heldout --workers 10
```
Outputs go to `data/interim/bl39/heldout_*` (gitignored); summaries are copied to `artifacts/`.

End of the BL-39 pre-registration.

## Falsified if
See the pre-registration above (every registered row must pass; one candidate, no fallback).

Anchor hash, computed with
`awk '/^## Pre-registration$/{f=1} f{print} /^End of the BL-39 pre-registration\.$/{exit}' README.md | shasum -a 256`:
`7e85dcd87100537462d3705cb1dbb02e44ab2672c6247fc9a934dee7a36ebc39` (also in `artifacts/prereg_sha256.txt`), recorded 2026-10-11 18:02 UTC, before any BL-39 held-out piece was drawn or aligned. Code: HEAD 87be183 plus the uncommitted BL-39 diff: `git diff HEAD -- src/pianolens/report` sha256 prefix fcef2308f4cc87be; untracked `scripts/eval_edge_narrow_bl39.py` b7e7493f15fd2a97.

## Data
PianoCoRe (DATASETS.md) tier A transcriptions: Transkun V2 (PERiScoPe) and Aria-AMT
(Aria-MIDI). Scores come from the PianoCoRe archive; data layer at HEAD 87be183.

**Held-out draw** (seed 3939, as pre-registered):
- 177 eligible pieces, 121 of them with the literal-repeat flag; 800 jobs drawn.
- The BL-35 guard dropped 1 job (`PianoCoRe_141888`), leaving 799.
- **Literal repeats (8):** Beethoven Op. 10 No. 2/1 (4 repeat paths), Op. 13/1, Op. 7/2; Chopin
  Op. 10 No. 1, Op. 47, Op. 58/3; Debussy L. 110 No. 1; Schumann Op. 17/2.
- **No literal repeats (8):** Beethoven Op. 110/1; Chopin Op. 10 No. 7, Op. 25 No. 8, Op. 61;
  Debussy L. 117 No. 1; Ravel Miroirs No. 2 (Oiseaux tristes); Schubert D. 760/1; Schumann
  Op. 17/3.

## Splits
- No model is fitted. The candidate, the sabotages and every bar were set on 44 seen dev pieces.
- The held-out pieces are disjoint by piece id from every earlier draw (listed in the
  pre-registration) and from the score-version-mismatch piece. No transcription id was used
  before.
- Sibling movements of earlier pieces are in the draw, for example Op. 10 Nos. 1 and 7 next to
  earlier Op. 10 etudes, and Op. 58/3 next to Op. 58/1-2. They are different scores.

## Baselines
- **k = 0:** no policy, the baseline for every harm row.
- **k = 1:** the BL-37 policy, the comparator.
- **The uncut clean copy:** the reference for E1 and E2.
- **C:** today's full alignment, for W1 and H1.

## Method
`scripts/eval_edge_narrow_bl39.py` (built on `eval_edge_bars_bl37.py` and `eval_partial_bl36.py`).
The rule lives in `report.build.edge_outside_notes`, selected by
`ReportConfig.edge_low_confidence_rule="outside"` and `edge_outside_basis="score_le"`.

## Command
```
# design (dev, 44 seen pieces, 3 targets per piece and family)
OMP_NUM_THREADS=1 uv run python scripts/eval_edge_narrow_bl39.py --set dev --workers 10 --limit-targets 1 --tag smoke
OMP_NUM_THREADS=1 uv run python scripts/eval_edge_narrow_bl39.py --set dev --workers 10 --reachability 1000
OMP_NUM_THREADS=1 uv run python scripts/eval_edge_narrow_bl39.py --set dev --from-cache --reachability 2000
# held-out
OMP_NUM_THREADS=1 uv run python scripts/eval_edge_narrow_bl39.py --set heldout --workers 10
```

## Run record
- **Pre-registration:** hashed 2026-10-11 18:02 UTC (`7e85dcd8...bc39`); the held-out launch
  followed in the same step.
- **Code:** HEAD 87be183 plus the uncommitted BL-39 diff (hashes in "Falsified if"); no code or
  criterion changed after the launch.
- **Before the hash:**
  - the dev smoke (88 targets) and the dev run (258 targets);
  - rescoring the dev cache after adding the k = 2 sabotage, setting the candidate, and setting
    the O2 bar (-45, then -50);
  - one cut copy realigned by hand to inspect a residual cut bar (Op. 22/2 bar 53, a dev piece).
- **Held-out run:** 799 jobs, 0 failed, 0 targets suspect, so 319 usable targets (160 Transkun
  V2, 159 Aria-AMT) and 480 experts. Rows were written at 20:36 UTC and summaries at 20:55 UTC.
  There are 1,274 truncation copies (319 each of start, end and both, 317 excerpts), plus
  4-7-bar "short" copies as information.
- **Machine load and memory** (plumbing only; results do not depend on them):
  - **Load:** the load average reached about 140 while the 10 workers ran. Each worker had 2
    threads at about 90% CPU on 10 cores, so this was not thread oversubscription. The load
    counted many runnable macOS daemons queued behind the workers.
  - **Memory:** the Mac has 16 GB of RAM (not the 48 GB in CLAUDE.md). During the run, swap
    stayed at 5.6 of 7.2 GB, free memory at 44-51%, and worker RSS at about 4.4 GB. It was
    checked every few minutes against a stop rule (swap above 6.5 GB, or critical pressure),
    which never fired.
  - The script cannot resume (it writes rows only at the end), so the run was not restarted
    with fewer workers.
- **API usage limit:** the agent session was cut off by an API usage limit after the run had
  finished writing its outputs. The write-up was done afterwards from the written outputs; the
  held-out set was not re-run.

## Results

**Held-out: FAIL by the registered rule; no policy is adopted (k = 0).** Only E2 fails.
- Values are means over the 16 pieces, in points, with the piece-bootstrap 95% interval and the
  t-interval.
- "LOO" is the leave-one-piece-out range.

| Row | k = 0 | k = 1 | **Candidate** | Candidate bootstrap / t | LOO | Bar |
|---|---|---|---|---|---|---|
| E1 edge minus uncut (1,889 bars) | +0.49 | -0.11 | **+0.05** | [-0.39, 0.49] / [-0.44, 0.54] | -0.07 to +0.17 | [-1.0, +1.5] |
| E2 cut bars minus uncut (1,073 bars) | **+18.22 (fails)** | -1.05 | **+1.67 (fails)** | [0.32, 2.97] / [0.19, 3.15] | +1.37 to +2.01 | at most +1.5 |
| D1 wrong pitches, strong, vs k = 0 (1,449 bars) | 0 | -0.88 | **-0.52** | [-1.10, -0.06] | -0.56 to -0.32 | at least -5 |
| D2 the same, notable or strong | 0 | -3.73 | **-1.60** | [-2.35, -0.96] | -1.71 to -1.34 | at least -8 |
| O1 inner omissions vs k = 0 (427 bars) | 0 | **-36.48 (fails)** | **-1.10** | [-2.50, 0.00] | -1.18 to -0.60 | at least -8 |
| O2 lead omissions vs k = 0 (443 bars; disclosed cost) | 0 | -34.18 | **-29.72** | [-37.48, -21.54] | -31.84 to -27.88 | at least -50 |
| T2 never-played bars tiered | 0.001 | 0.001 | **0.001** | | | at most 0.03 |
| R2 the same on Na | 0.001 | 0.001 | **0.001** | | | at most 0.03 |
| H1 Transkun V2 strong / notable+ (evidently full) | 0 / 0 | 0 / 0 | **0 / 0** | | | ±0.15 / ±0.30 |
| H1 Aria-AMT strong / notable+ (evidently full) | -0.023 / -0.032 | -0.025 / -0.034 | **-0.025 / -0.032** | | | ±0.15 / ±0.30 |

- **BL-36 rows (alignment level):** T1 0.9982, T3 0.9988, R1 0.9966, R3 0.9997, H2 0.987 /
  0.0001. All pass.
- **W1:** 310 of 310 whole, unrefined natural targets are identical between C (computed
  separately) and N. 2 more were whole only after refinement and are not covered.
- **Absolute rates** (mean over pieces):

  | | Uncut | k = 0 | k = 1 | Candidate |
  |---|---|---|---|---|
  | edge bars strong | 0.87% | 1.35% | 0.76% | 0.91% |
  | cut bars strong | 1.33% | 19.6% | 0.28% | 3.0% |
  | inner omissions caught (notable or strong) | | 51.6% | 15.1% | 50.5% |
  | lead omissions caught | | 50.5% | 16.3% | 20.8% |
  | injected wrong pitches caught strong | | 61.1% | 60.2% | 60.6% |

- **E2 is fragile both ways.**
  - Dropping any one of 4 pieces would make it pass: Chopin Op. 10 No. 7, Op. 25 No. 8, Schubert
    D. 760/1 (worst piece, +6.25) and Schumann Op. 17/3.
  - Joint resampling of held-out pieces passes every row in 40% of resamples (E2 is the only
    row below 1).
  - Dev resampling had said 74%, and the pre-registration called FAIL a live outcome.
- **Sabotages (information):**
  - k = 2 fails O1 (-50.8); O2 -47.0 passes this time.
  - The second-onset sabotage passes every row on held-out (O1 -6.9 against -8; E2 +0.15). This
    is post hoc and does not change the verdict; on dev it failed O1 (-16.2).
- **No wrong-piece probe** (not cheap; BL-40).

## Verdict (Provisional)
**FAIL by the pre-registered rule.** The candidate fails E2: partly played cut bars are +1.67 pt
above uncut, against a bar of +1.5. Every harm row and every no-regression row passes. The
registered outcome applies:
- no edge policy is adopted;
- k = 0 stays the recommendation for `partial=True`, as the BL-37 audit already supported;
- there is no fallback to k = 1;
- the flags stay off (`PARTIAL_DEFAULT` False, `edge_low_confidence_bars` 0).

What the data show, without changing the verdict:
- **The narrow rule does what it was built to do on omissions.** Inner omissions are caught
  about as often as at k = 0 (50.5% vs 51.6%; k = 1 15.1%).
- **The cost is concentrated on the bar's own first or last notes, as disclosed** (lead
  omissions 20.8% vs 50.5% at k = 0).
- **Cut bars fall from 19.6% to 3.0% strong,** but not to the uncut 1.33%. The residual is notes
  the cut copy's alignment loses inside the recorded part, which this rule cannot reach (dev
  inspection, one bar in detail).
- The E2 failure margin is 0.17 pt, and 4 single-piece drops flip it.

## Threats to validity
- **The truncation control is synthetic.** Its start and end cuts fall at a random time inside a
  bar, and that is where E2's partly played cut bars come from. A learner's take that starts or
  stops at a bar line has no such bar. How often real takes do either is not measured.
- **E2's per-piece values come from few cut bars** (about 67 per piece). A single strong bar
  moves a piece by 1.5-6 pt, so the pooled bar of +1.5 sits inside the sampling noise (40%
  resample pass on held-out, 74% on dev).
- **O1 / O2 inject 3 omitted notes per edge bar.** Other omission sizes were not tested.
  "Lead" and "inner" are defined by score onset in the clean copy.
- **The sabotage variants** were chosen on dev to make the harm rows bite. On held-out, the
  second-onset sabotage would have passed. O1's bar (-8) admits a rule that hides some inner
  omissions; it bit for that sabotage on dev only.
- **The policy is evaluated offline** with the script's tier function. BL-37's audit checked
  that this function equals `report.build._correctness_section` for the "bar" rule; the
  "outside" rule in production is tested on synthetic scores only.
- **Family equals corpus** (Transkun V2 = PERiScoPe, Aria-AMT = Aria-MIDI).

## For the lead
1. **Registered outcome:** no edge policy. `partial=True` at k = 0 remains the configuration to
   put to Henry (BL-37 audit). The code for the "outside" rule stays in `report.build`, off by
   default (`edge_low_confidence_rule="bar"`, `edge_low_confidence_bars` 0).
2. **If a later ticket retries:**
   - E2 needs either a per-bar statistic robust to small cut-bar counts, or a fix for the
     alignment loss inside the recorded part of a cut bar. The residual is alignment, not policy
     (dev inspection).
   - Any retry needs a fresh held-out draw: BL-39's held-out set is now seen.
3. **Machine:** the Mac has 16 GB of RAM, not 48 GB (CLAUDE.md says 48). Alignment runs should
   use 5-6 workers. Eval scripts should write per-target results incrementally so a run can be
   stopped and resumed (BL-39's could not).
