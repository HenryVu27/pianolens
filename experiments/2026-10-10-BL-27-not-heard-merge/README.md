# BL-27: merge "passage not heard" fragments and extend runs to the piece edges
Ticket: BL-27    Hypothesis: none from the plan (report rule change)    Status: Provisional

## Question
On transcribed input a recording that starts late or is cut leaves its missing passage as
several "passage not heard" runs: a bar just under 80% missed splits a run, and the last bars are
often partly found (BL-18b audit, item 5). Does merging run fragments separated by at most 2
graded bars, and extending a run to the first / last graded bar when it ends within 2 graded
bars of it, report a missing passage as one item more often, without swallowing heard bars and
without moving the clean strong / notable+ rates under rule P?

## Pre-registration

Written 2026-10-10 after a dev run on the BL-18b pieces (design data, described below) and
before any held-out piece was drawn or aligned. The anchor hash is recorded in "Falsified if".

**Rules** (`report.build.not_heard_runs`; transcribed input; rule P = R1(0) against the 15
same-family experts, extras not counted, as BL-18b / DF-13):
- **C (current):** runs of at least 3 consecutive graded bars, each at least 80% missed
  (`NOT_HEARD_MERGE_GAP = 0`).
- **M (candidate):** C, then runs separated by at most 2 graded bars merge when every bar
  between them has at least 50% of its graded notes missed; a run starting (ending) within 2
  graded bars of the first (last) graded bar extends to it under the same condition
  (`merge_gap = 2`, `NOT_HEARD_GAP_MISSED_SHARE = 0.5`). By construction no swallowed bar has more
  than half of its graded notes found; whether swallowed bars were really heard is measured by the
  truncation control.
- The guard (recurring-error promotion never overrides a "not heard" bar) is already in the code
  and is not under test here.

**Checker and constants.** The current code: DF-15 duplicate resolution (re-match off), BL-26
tremolo expansion (mark copy off), BL-33 hand split, the BL-28 calibration constants in
`report/calibration.py` (written before this section). Scoring uses exactly these.

**Data.**
- Pool: PianoCoRe pieces with at least 25 transcriptions in each family (Transkun V2, Aria-AMT)
  and exactly one score.mxl in the archive, excluding Henry's 5 pieces (A-01 floor, BL-18 T1), the
  BL-18 T2 pieces, the BL-18b pieces (= DF-13 dev) and the DF-13 held-out pieces; transcription
  ids used by the A-01 floor, BL-18, BL-18b or DF-13 are excluded.
- Draw: 16 pieces, seed 2727 (`numpy.random.default_rng`) from the pool sorted by piece id; per
  piece and family the remaining transcriptions sorted by id and permuted with the same
  generator: the first 15 are experts, the next 10 targets. Targets and experts with match ratio
  below 0.8 are dropped. (`scripts/eval_not_heard_merge_bl27.py`, `heldout_jobs`.)
- **Natural targets:** each clean target tiered under rule P with C and with M (each rule's own
  run bars untiered and left out of its clean denominator).
- **Truncation control (known answer):** per target two copies: `end` (every performed note
  with onset at or after a time T removed; T uniform inside a graded bar drawn uniformly from
  75-95% of the graded bars) and `start` (every note before T removed; bar from 5-25%); seed
  `[27, crc32(target id)]`. Each copy is realigned to the score with the clean alignment's
  repeat variant. Truth per bar from the clean alignment's expected onsets: `not_heard` (every
  graded note due on the removed side of T), `heard` (every graded note due on the kept side),
  `cut` (the bar holding T). A copy is scored when its alignment is not suspect (match ratio at
  least 0.8) and at least 3 graded bars are `not_heard`.
- "One item": exactly one run intersects the `not_heard` and `cut` bars, and that run contains
  the copy's edge bar (the last graded bar for `end`, the first for `start`).

**Criteria** (point estimates decide; piece bootstrap 95% CIs, 2,000 resamples, seed 0, are
reported; families are never pooled for S1):
- **S1 (safety, natural targets), per family:** |P clean strong (M) - P clean strong (C)| at
  most 0.25 percentage points and |P clean notable+ (M) - (C)| at most 0.50 points.
- **E1 (effectiveness, truncation control, both families and both cut sides pooled):** the
  one-item share under M minus under C is at least +10 percentage points.
- **E2 (no family left behind):** the same difference is above 0 in each family.
- **P1 (precision, truncation control):** of the graded bars that M puts in a run and C does
  not, the share that is `heard` is at most 10% pooled and at most 15% in each family.
- **PASS** = S1 in both families, E1, E2 and P1. **FAIL** otherwise; there is no partial
  outcome. On PASS `NOT_HEARD_MERGE_GAP` becomes 2 (Provisional until the eval-auditor signs
  off); on FAIL it stays 0.
- Information, not deciding: per cut side and family; the `not_heard` bars tiered strong under
  C and M (false alarms from a cut recording); natural run counts, items touching an edge, the
  correct-note share of bars M adds; the share of copies realigned with the same variant.

**Dev (design data, BL-18b pieces; disclosed).** 238 usable targets (experts from the DF-15 dev
run, same code), 421 scored truncation copies (24 suspect, 31 with a gap under 3 bars). Under
the BL-28 constants: S1 Transkun V2 0 / 0 pt, Aria-AMT -0.036 / -0.055 pt; one-item share C
47.0% -> M 70.8% (+23.8 pt, [16.3, 31.0]; Transkun V2 +23.7, Aria-AMT +23.8); added bars heard
24 of 417 (5.8%; Transkun V2 1.9%, Aria-AMT 9.9%); `not_heard` bars strong 9.9% -> 6.8%. Natural
BL-18b runs (the audit's cases): 19 runs in 10 Aria-AMT targets become 10 (one per target), 7
of them touching an edge (6 end, 1 start). The cut ranges were narrowed from 50-90% / 10-50%
after a one-target smoke test in which the wider start cut made the copy suspect; the
thresholds of S1, E1, E2 and P1 were set after the dev run.

**Reachability** (dev, 4,000 resamples of 16 pieces with replacement): E1 holds in 100% (5th
percentile of the gain +18.3 pt); E2 in 100% per family; P1 pooled in 100% (95th percentile
8.0%), Aria-AMT per family in 98% (median 9.8%, 95th percentile 14.1%), Transkun V2 in 100%. S1
has a lot of room on dev (largest |change| 0.055 pt), but held-out pieces with many truncated
Aria-MIDI segments could move it more. The binding criterion is expected to be P1 for Aria-AMT.

**Run.** `OMP_NUM_THREADS=1 uv run python scripts/eval_not_heard_merge_bl27.py --set heldout
--workers 10`; outputs `data/interim/bl27/heldout_*` (gitignored), copied summaries in
`artifacts/`.

End of the BL-27 pre-registration.

## Falsified if
See the pre-registration above (S1, E1, E2, P1; PASS needs all). Anchor hash, computed with
`awk '/^## Pre-registration$/{f=1} f{print} /^End of the BL-27 pre-registration\.$/{exit}' README.md | shasum -a 256`:
`78a9a04c8e81aee969c43b0bd04a36faf11eb51b2a8e2710d6daa6a9db02c594` (also in `artifacts/prereg_sha256.txt`), recorded 2026-10-11 04:06 UTC, before any held-out piece was drawn or aligned. Code: HEAD 2cd851a, no uncommitted change under `src/`; `scripts/eval_not_heard_merge_bl27.py` untracked, sha256 prefix 5bcd5aa2cec5b782.

## Data
PianoCoRe (DATASETS.md), tier A transcriptions, Transkun V2 (PERiScoPe) and Aria-AMT
(Aria-MIDI), scores from the PianoCoRe archive. Held-out draw as pre-registered: 225 eligible
pieces, 16 drawn (seed 2727): Bach BWV 971; Beethoven Op. 7/1, Op. 27 No. 1/4, Op. 49 No. 1/2,
Op. 57/3; Chopin Op. 10 No. 9, Op. 20, Op. 28 No. 15; Debussy L. 117 No. 6, Children's Corner
Nos. 1 and 3; Mozart K. 331/1; Ravel Miroirs No. 5; Schubert D. 780 No. 1; Schumann Op. 16
Nos. 5 and 6. 800 jobs, 0 failed; 8 experts and 4 targets suspect (match ratio < 0.8) and dropped;
316 usable targets (159 Transkun V2, 157 Aria-AMT). Truncation copies: 632, of which 45 suspect
and 15 with fewer than 3 not-heard bars, so 572 scored (287 / 285); every copy kept the clean
repeat variant.

## Splits
No model is fitted. The rule and every threshold were set on the dev pieces (BL-18b); the
held-out pieces are disjoint from the A-01 floor, BL-18, BL-18b and DF-13 by piece id, and no
transcription id was used before. Piece bootstrap (2,000, seed 0).

## Baselines
Rule C (the deployed run rule, no merging), scored on the same tables, copies and experts.

## Method
`scripts/eval_not_heard_merge_bl27.py` (pre-registration above). Natural targets are tiered under
rule P against their 15 same-family experts with each rule's runs untiered. Truncation copies
are realigned with the clean repeat variant and scored against the truth from the clean
alignment's expected onsets.

## Command
```
OMP_NUM_THREADS=1 uv run python scripts/eval_not_heard_merge_bl27.py --set dev --workers 5 --experts-from-df15
OMP_NUM_THREADS=1 uv run python scripts/eval_not_heard_merge_bl27.py --set dev --from-cache   # re-scored under BL-28
OMP_NUM_THREADS=1 uv run python scripts/eval_not_heard_merge_bl27.py --set heldout --workers 10
```

## Run record
- Pre-registration hashed 2026-10-11 04:06 UTC (`78a9a04c...c594`); held-out launched 04:06 UTC
  after the hash, outputs written 04:53 UTC (machine load 20-30 from other agents). Code: HEAD
  2cd851a with no uncommitted change under `src/`; the script untracked (sha256 prefix
  5bcd5aa2cec5b782). No change to code or criteria after the launch.
- Dev was run before BL-28 was written (old constants), then re-scored from cache under the BL-28
  constants before the pre-registration; both summaries are in `artifacts/`.

## Results

Held-out. Point estimates decide; piece bootstrap 95% CIs in brackets.

| Criterion | Transkun V2 | Aria-AMT | Pooled | Bar | Result |
|---|---|---|---|---|---|
| S1 P clean strong, M - C | -0.013 pt [-0.052, 0] | 0 pt | -0.007 | ±0.25 pt per family | pass |
| S1 P clean notable+, M - C | -0.013 pt [-0.051, 0] | 0 pt | -0.007 | ±0.50 pt per family | pass |
| E1 one-item share, M - C | +16.0 pt [12.0, 20.3] | +18.6 pt [15.0, 22.0] | **+17.3 pt** [14.1, 20.3] (40.6 -> 57.9%) | >= +10 pt pooled | pass |
| E2 one-item share M - C > 0 | +16.0 | +18.6 | | > 0 each family | pass |
| P1 added bars that are heard | 18 / 300 = **6.0%** | 44 / 289 = **15.2%** | 62 / 589 = **10.5%** | <= 15% each, <= 10% pooled | **fail** (Aria-AMT, pooled) |

Information:
- By cut side (pooled): `end` one-item 41.2 -> 60.6% (+19.4), heard share of added bars 4.9%;
  `start` 39.9 -> 55.3% (+15.4), heard share 15.9% (Aria-AMT 24.2%).
- Not-heard bars of the cut copies tiered strong: C 12.9% -> M 9.9% (Transkun V2 13.4 -> 10.1%,
  Aria-AMT 12.3 -> 9.7%); not-heard coverage by runs 80.4 -> 83.8%.
- Natural targets: runs 22 -> 19 (Transkun V2 12 -> 9; Aria-AMT 10 -> 10), runs touching an
  edge unchanged (5 end, 2 start); M adds 4 bars, all Transkun V2, correct share at most 0.30,
  all 4 strong under C.

**P1 is concentrated in one piece.** Chopin Op. 20 holds 34 of the 44 Aria-AMT heard additions
(42 of 62 pooled; its Aria-AMT share alone is 51%). Leave-one-piece-out, Aria-AMT P1 ranges
4.5-17.6% and only dropping Op. 20 brings it under 15% (1 of 16 drops); pooled 4.2-11.8%, again
only Op. 20 (1 of 16). Piece bootstrap: Aria-AMT [1.8, 30.0]%, 51% of resamples at or under 15%;
pooled [2.2, 20.8]%, 47% under 10%. Transkun V2 passes in every drop and 100% of resamples.

**What the swallowed "heard" bars are (post hoc, information).** In Op. 20, the 42 heard bars M
adds were played cleanly in the uncut copy (median 0% of notes missed, mean 3.8%), but after the
cut the realignment labels them 50-78% missed: an alignment failure caused by the truncation,
mostly after start cuts (38 of 42). Under C they are already tiered: 39 strong, 3 notable. So for
these bars M replaces false strong flags with a "not heard" item; it does not hide notes the
checker had found. This does not change the verdict.

## Verdict (Provisional)
**FAIL by the pre-registered rule.** S1, E1 and E2 pass in both families. P1 fails: added bars
that are heard are 15.2% for Aria-AMT (bar 15%) and 10.5% pooled (bar 10%). The pre-registered
action applies: `NOT_HEARD_MERGE_GAP` stays 0 (no merging). The BL-27 guard (recurring errors
never override "not heard") is unaffected.

What the data say, without changing the verdict: the merge reports a cut recording as one item
in about 17 more copies per 100, moves no clean rate, and on these pieces its only precision
loss comes from one piece whose bars were already mislabelled by the aligner after the cut and
tiered strong under the current rule. The P1 reading is not stable to one piece (1 of 16 drops
flips it; about half of the bootstrap resamples pass).

## Threats to validity
- The truncation control is synthetic: notes are removed cleanly at one time T. Real Aria-MIDI
  segments may start or end mid-note, carry silence or applause, or be cut inside a repeat. The
  copies keep the clean repeat variant; a real cut recording is aligned with the variant chosen
  for it, which this test does not cover.
- "Heard" truth comes from the clean alignment's expected onsets, so a clean-copy misalignment
  would mislabel truth; the Op. 20 bars had near-zero missed notes in the clean copies, so that
  is not what happened there.
- P1 is a ratio of sums over bars and is dominated by its heaviest piece (the DF-13 lesson). A
  per-piece-robust statistic was not registered. Thresholds were set after the dev run.
- Natural runs are few on these pieces (22 under C), so S1 has little to move.
- Family equals corpus (Transkun V2 = PERiScoPe, Aria-AMT = Aria-MIDI).

## For the lead
1. Apply the registered outcome (done in code: the default stays 0).
2. Better next test, if the merge is wanted: a P1 that counts only heard bars that were *not
   already tiered* under C (the learner-facing harm: bars that lose a correct "nothing wrong"),
   or a per-piece-robust precision statistic, pre-registered on new pieces. On this run, all 42
   Op. 20 swallowed heard bars were tiered under C, so that criterion would likely pass, but that
   reading is post hoc.
3. Separate issue found here: after a start cut, the aligner can mislabel well-played bars as
   50-78% missed (Op. 20). Cut recordings therefore produce false strong flags outside any run
   under either rule (not-heard bars tiered strong: 12.9% under C); worth a ticket on aligning
   partial recordings (subsequence alignment or trimming the score to the recorded span).

## Audit (eval-auditor, 2026-10-11)

**Verdict: Confirmed with caveats.** FAIL by the pre-registered rule is the correct reading, and
`NOT_HEARD_MERGE_GAP` stays 0. Every reported number reproduces. The post hoc "aligner damage"
reading is supported and labelled post hoc, but it understates the problem: both rules misreport
the affected passage. P1 sits on a knife edge. The author fixes below are wording plus one
missing test; none of them changes the verdict.

**1. Pre-registration and timeline.**
- The anchor recomputes to `78a9a04c...c594`, the same value as in `artifacts/prereg_sha256.txt`.
- Author transcript: session 73c389dd, `subagents/agent-a90d10a79fa6d5e53.jsonl`.
  - BL-28 constants committed (2cd851a): 04:04:54Z.
  - Dev re-score: 04:04:55Z.
  - README written: 04:05:59Z.
  - Hash: 04:06:03Z.
  - "Falsified if" line edited (outside the anchor) and held-out run launched in the same call:
    04:06:12Z.
  - `heldout_rows.pkl` written at 04:53:11Z.
- Before the hash, the script ran only on dev pieces: a one-target smoke test at 23:51Z, then the
  dev run and the dev re-score. No held-out draw happened before the hash.
- The script's sha256 (5bcd5aa2...) is unchanged from the hash time to the commit. No criterion
  changed after launch.

**2. Disjointness.**
- The 16 held-out piece ids are disjoint from Henry's 5 pieces, the BL-18 pieces (T1 and T2),
  BL-18b (= BL-27 dev = DF-13 dev), the DF-13 held-out pieces and the A-01 floor pieces (taken
  from the floor ref ids). The script's dev set is exactly the BL-18b pieces.
- 0 of the 800 transcription ids appear in any earlier set.
- Sibling movements (not the same content) sit in excluded sets: K. 331/2, D. 780/2 and Op. 16/2.
- Three held-out pieces (Op. 20, D. 780/1, Op. 16/6) appear among the DF-15 ASAP / key-sensor
  performances, which fed the BL-28 constants. Those are different recordings, and rule P here
  uses same-family experts with no family limits, so this is not a leak into M vs C.

**3. Criteria computed as registered.** `evaluate()` on the cached `heldout_rows.pkl` reproduces
`heldout_summary.json` in every field (0 differences).
- Denominators:
  - S1 runs per family over bars outside each rule's own runs.
  - E1 is the mean over scored copies, pooled over families and sides.
  - P1 is a ratio of sums: 62 / 589 = 62 heard + 5 cut + 522 not heard, with no unknown truth.
- Tolerances: S1 is two-sided; E1, E2 and P1 are one-sided, as registered.
- Scored copies: 632 copies minus 45 suspect minus 15 with fewer than 3 not-heard bars gives 572.
- Reproduced in a fresh run: the P1 bootstrap ([1.8, 30.0]% Aria-AMT, [2.2, 20.8]% pooled), the
  share of resamples that pass (51%, 47%), the leave-one-out ranges and "1 of 16 drops flips".
- Re-aligning 2 Op. 20 targets reproduced the cached clean and cut tables exactly, including the
  cut times (6 alignments).
- `not_heard_runs(merge_gap=0)` equals the pre-BL-27 function on 200,000 random inputs.
- Reports built with the old and the new function at gap 0 are identical (JSON and HTML),
  apart from the two keys added to `summary.not_heard_rule`.

**4. Truncation-control truth.**
- Truth comes from the uncut alignment, so it holds wherever that alignment is right. For the Op. 20
  bars it is right: median 0% missed in the clean copies.
- The registered "heard" truth does not require the clean copy to have found the bar. 5 of the 62
  heard additions were at least 50% missed in the clean copy (1 Aria-AMT, 4 Transkun V2).
  Counting them as not heard (post hoc) gives P1 = 43 / 288 = 14.9% Aria-AMT and 57 / 584 = 9.8%
  pooled, which would pass. So P1 fails by 1 bar (Aria-AMT; the bar is 43.35 of 289) and by
  4 bars (pooled; the bar is 58.9 of 589). This does not change the registered verdict.
- "Every copy kept the clean repeat variant" is true by construction: the copy is aligned with
  `repeats=variant`. It is not a finding.
- The 45 suspect copies (7%; 18 of them Transkun V2 end cuts) are excluded, so harm on
  cut recordings whose alignment falls below 0.8 is not measured.

**5. The post hoc Op. 20 reading: supported, but incomplete.** Facts that check out:
- 42 heard additions: 34 Aria-AMT and 8 Transkun V2; 38 after start cuts.
- 0% median missed in the clean copy; 50-78% missed in the cut copy.
- 39 strong and 3 notable under C.

The README omits three things:
- **Mechanism (two copies probed, PianoCoRe_121007 and _121487, start cuts).** The realignment
  matched the kept passage, clean bars about 126-285, onto pitch-identical material 116 bars
  earlier in the unfolded score: 99-100% of those notes are still "correct", but in the wrong
  bars. Alignment resumes at about bar 300. The unplayed opening is reported as played, and the
  played stretch as missed.
- **C already swallows most of it.** C puts 96 to 109 heard bars per copy into "not heard" runs in
  four Op. 20 start copies, and 522 heard bars of Op. 20 in total. Across all 572 copies it puts
  1,393 heard bars into runs. The 42 bars M adds are gap bars inside this misaligned stretch,
  40-176 bars after the cut. They are not at the cut boundary.
- **The warning was in the dev data.** On dev, Chopin Op. 54 held 16 of the 24 heard additions
  (13 of 20 Aria-AMT) and 230 heard bars in C runs. The pre-registration reported reachability
  percentiles but not this concentration.

So "M replaces false strong flags with a 'not heard' item" is true for these bars. But under
either rule the report misplaces the whole passage. P1 measured M's small increment on top of an
alignment failure that C already has.

**6. Ratio of sums and the DF-13 lesson.**
- P1 is a ratio of sums over bars. The DF-13 rule lesson ("report how concentrated it is on its
  heaviest pieces, and register a robust per-piece statistic") was committed (f330e13, 22:56Z)
  about five hours before this pre-registration, and the author had read DF-13.
- Not following it is a process lapse, disclosed in Threats. It does not change a registered
  verdict.
- Post hoc, the unweighted mean of per-piece heard shares (pieces with at least one addition)
  is 5.5% Aria-AMT, 3.8% Transkun V2 and 5.0% pooled; the median piece is 0%.
- Of the pieces with additions, 1 of 15 is above the bar for Aria-AMT and 3 of 15 for pooled.

**7. E1 and S1.**
- E1 is robust: leave-one-piece-out +16.5 to +18.2 pt, and 15 of 16 pieces gain (one gains 0).
- S1 for Aria-AMT is 0 because M added no natural Aria-AMT bar on these pieces. That is not
  informative about safety. Natural runs are few (22), as the README says.

**8. Guard.**
- Removing `and heard[i]` in `build_report` makes `test_recurring_error_never_overrides_not_heard`
  fail.
- The matching change in `render.py` (the takes timeline row) is not covered: mutating it leaves
  all 67 report tests passing. BACKLOG's "checked to fail without the guard" is true only for the
  build side.

**9. The 12.9% side finding (not-heard bars tiered strong under C).**
- The figure reproduces: 1,966 of 15,275 not-heard bars.
- It is general, not one piece: per piece 3.6-19.3%, unweighted mean 13.4%.
- 346 of the 572 copies have at least one such bar (median 4 among them, at most 40). Only 11%
  of them lie within 3 bars of the cut; the median distance is 17 bars.
- These bars are mostly 67-80% missed (quartiles), so they fall just under the 80% run threshold
  because the aligner pulled in a few notes from elsewhere.
- In the same copies, C tiers 1,268 heard bars strong, against 577 in the uncut copies of the
  same bars.
- In 244 of 572 copies the strong flags on unplayed bars outnumber those on played bars. M only
  lowers 1,966 to 1,515.

For a learner who records part of a piece, the current report's strong list would often be
dominated by bars they never played. When the piece repeats material, the passage they did play
can also be shifted onto the wrong occurrence. This was measured on synthetic cuts removing 5-25%
of the graded bars. Short excerpts (most of the piece missing) and real cut recordings are
untested. This supports BL-36 (subsequence alignment, or a learner-given bar range) as the
higher-priority fix.

**Required author fixes (wording and one test; the verdict is unchanged).**
1. README "What the swallowed heard bars are": add the 116-bar shift mechanism, the count of heard
   bars C already puts in runs (522 for Op. 20; 1,393 overall), and that the 42 bars lie 40-176
   bars after the cut, not at it.
2. README "For the lead" item 2: a P1 limited to bars untiered under C is nearly pass by
   construction. 581 of 589 added bars, and 61 of 62 heard additions, were already tiered under C,
   because M only adds bars at least 50% missed. Replace it with a per-piece-robust heard share,
   scored against a truth that requires the bar to be found in the clean copy.
3. README Data: "every copy kept the clean repeat variant" should say "by construction".
4. BACKLOG BL-27 cell: delete the stale "Prepared, not run ... No pre-registration written and no
   held-out data drawn." Scope "checked to fail without the guard" to `build_report`, or add a
   test on the rendered takes row.
5. EXPERIMENTS row: "already strong under the current rule" should read "already tiered (39
   strong, 3 notable)".
6. Add a `render.py` guard test: the takes timeline row must not paint a not-heard recurring bar
   strong.

**Gates.** `uv run pytest -q`: 623 passed, 8 skipped. `uv run ruff check src tests`: all
checks passed.

### Corrections after the audit (2026-10-11)

By `feature-engineer`, applying the audit's required fixes (wording and one test). The audit
section, the run record and the pre-registration are not edited; the anchor hash was re-checked
after these corrections and is still `78a9a04c...c594`. The verdict is unchanged: FAIL by the
pre-registered rule (P1), Confirmed with caveats; the merge stays off, the guard stays.

1. **What the swallowed "heard" bars are (replaces the post hoc paragraph's scope).** In the
   Op. 20 start-cut copies the auditor probed (PianoCoRe_121007, _121487), the realignment
   matched the kept passage (clean bars about 126-285) onto pitch-identical material 116 bars
   earlier in the unfolded score: 99-100% of those notes stay "correct", but in the wrong bars,
   until alignment resumes near bar 300. So the unplayed opening is reported as played and the
   played stretch as missed, under either rule. C already puts heard bars into "not heard" runs
   on a large scale: 522 heard Op. 20 bars, and 1,393 heard bars over all 572 scored copies (both
   recomputed from `heldout_truncation.csv`). The 42 bars M adds in Op. 20 are gap bars inside this
   misaligned stretch, 40-176 bars after the cut, not at the cut. P1 therefore measured M's small
   increment on top of an alignment failure C already has. The warning was in the dev data:
   Chopin Op. 54 held 16 of the 24 heard additions (13 of 20 Aria-AMT) and 230 heard bars in C
   runs (recomputed); the pre-registration reported reachability percentiles, not this
   concentration.
2. **"For the lead" item 2 (replaced).** A P1 limited to bars untiered under C would pass nearly
   by construction: 581 of 589 added bars, and 61 of 62 heard additions, were already tiered (audit counts)
   under C, because M only adds bars at least 50% missed. If the merge is retested, register a
   per-piece-robust heard share (for example the mean or median over pieces of each piece's
   heard share), scored against a truth that requires the bar to be found in the clean copy (not
   only due on the kept side of the cut), on new pieces. For scale, all post hoc: P1 fails by 1
   bar for Aria-AMT (bar 43.35 of 289, observed 44) and by 4 bars pooled (58.9 of 589, observed
   62); counting the 5 heard additions that the clean copy itself had at least 50% missed as not
   heard gives 14.9% / 9.8%; the unweighted means of per-piece heard shares (pieces with at least
   one addition) are 5.5% (Aria-AMT), 3.8% (Transkun V2) and 5.0% (pooled), median piece 0%.
   None of this changes the registered verdict. The higher-priority fix is aligning partial
   recordings (BL-36), since both rules misplace the passage.
3. **Data.** "Every copy kept the clean repeat variant" is true by construction (each copy is
   realigned with `repeats=<clean variant>`); it is not a finding.
4. **Guard test (audit item 8).** `tests/report/test_report.py::test_takes_timeline_does_not_paint_not_heard_bar_strong`
   checks the `render.py` side: the "Errors in takes" row shows the not-heard recurring bar as
   untiered, and the same bar heard is painted strong. It fails with the `render.py` guard removed
   (checked) and passes with it.
