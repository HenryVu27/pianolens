# BL-36: align partial recordings
Ticket: BL-36    Hypothesis: none from the plan (alignment and report change)    Status: Provisional

## Question
When a learner records only part of a piece, today's aligner stretches the recording over the
whole score. Unplayed bars are aligned, graded and tiered: on BL-27's truncation control, 12.9%
of never-played bars were strong under the deployed rule. After a start cut, the played part can
also land on an earlier occurrence of repeated material (Chopin Op. 20, 116 bars early).

Does the following do better? Detect the recorded span (subsequence onset DTW over the repeat
paths), align to the score trimmed to that span, and list the bars outside it once as "not
recorded". The check is whether it:
- grades only the recorded bars;
- puts the played bars on the right score bars;
- leaves untouched full recordings as they are.

## Pre-registration

Written 2026-10-11 after dev runs on the BL-27 dev pieces (= BL-18b = DF-13 dev, 12 pieces;
design data, described below), before any held-out piece was drawn or aligned. The anchor hash
is recorded in "Falsified if".

**Methods.**
- **C (baseline, deployed):** `align_performance(score, perf)`, which is parangonar DualDTW over
  the whole unfolded score, followed by `correctness()`. On transcribed input, "passage not
  heard" runs apply (`report.build.not_heard_runs`, merge gap 0).
- **N (candidate):** `align_performance(score, perf, partial=True)` (`align/partial.py`).
  1. For every repeat path, run a subsequence DTW of the performed pitches against the score
     onset pitch sets (parangonar's onset DTW cost, with both score ends open). This gives the
     cheapest covering span.
  2. A side snaps to the piece edge when it leaves out at most `SNAP_NOTES` = 8 score notes.
  3. A path whose span is whole and whose cost is within `WHOLE_TOL` = 0.02 x performed notes
     of the best cost wins. Then the output is exactly C's (byte-identical alignment).
  4. Otherwise the cheapest span wins. Near ties go to fewer bars left out, then to "auto"'s
     ranking.
  5. Each trimmed side is widened by at least `MARGIN_BARS` = 2 bars and `MARGIN_NOTES` = 16
     score notes. The score is trimmed to that span and aligned by parangonar.
  6. Each trimmed side is shrunk while its edge bar has no score notes or at least
     `SHRINK_SHARE` = 0.5 of them missed.
  7. Bars outside the final span are not graded. They are listed once as "not recorded".
  The same "passage not heard" runs apply inside the span.
- **Checker, constants, tiers:** the current code: DF-15 duplicate resolution (re-match off),
  BL-26 tremolo expansion (mark copy off), BL-33 hand split, and the BL-28 constants in
  `report/calibration.py` (unchanged). Rule P is as in BL-18b / DF-13 / BL-27: R1(0) against the
  15 same-family experts, extras not counted. Each method's own run bars are untiered.

**Data.**
- **Pool:** PianoCoRe pieces with at least 25 transcriptions in each family (Transkun V2,
  Aria-AMT) and exactly one score in the archive. Excluded pieces:
  - Henry's 5 (A-01);
  - BL-18 T2;
  - BL-18b (= BL-27 dev = DF-13 dev);
  - DF-13 held-out;
  - BL-27 held-out.
- **Excluded transcription ids:** every id used by the A-01 floor, BL-18, BL-18b, DF-13 or
  BL-27.
- **Literal-repeat flag:** the score has more than one repeat path, or its fully repeated
  unfolding has two disjoint 4-bar windows with identical written content (same pitches at the
  same offsets).
- **Draw:**
  - The eligible pieces, sorted by id, are permuted with `numpy.random.default_rng(3636)`.
  - The first 8 flagged pieces and the first 8 unflagged pieces in that order are taken. If
    fewer than 8 are unflagged, flagged pieces fill the 16.
  - Per piece and family, the remaining transcriptions are sorted by id and permuted with the
    same generator: the first 15 are experts and the next 10 are targets.
  - Experts and targets whose clean C alignment is suspect (match ratio below 0.8) are dropped.
  - Code: `scripts/eval_partial_bl36.py`, `heldout_jobs`.

**Truncation control (known answer).** Each target gets four copies. Every performed note with
an onset outside a window is removed (seed `[36, crc32(target id)]`):
- `start`: T inside a graded bar drawn from 5-50% of the graded bars; notes before T are
  removed.
- `end`: the bar is drawn from 50-95%; notes from T on are removed.
- `both`: the start bar is drawn from 5-25% and the end bar from 75-95%.
- `excerpt`: 8-32 consecutive graded bars are kept, cut at bar boundaries, with at least one
  graded bar removed on each side.

Each copy is aligned three ways:
- by C with the clean alignment's repeat path (`repeats=<clean variant>`, so bar truth is
  defined, as in BL-27);
- by N with the same path;
- by N with repeat path "auto" (**Na**, what a learner gets).

Truth per bar label of the clean C alignment comes from its expected onsets: `heard`,
`not_heard` or `cut` (BL-27). A heard bar is **played** when the clean copy found it (under half
of its graded notes missed).

**Statistics** (per copy, then per piece):
- **Span accuracy:** among the heard and not-heard bars (cut bars excluded), the share whose
  presence in the method's graded score equals "heard". For C, every bar of its score is
  present.
- **Never-played bars tiered:** the share of not-heard bars with a rule P tier (notable or
  strong). Bars in a "passage not heard" run or outside the span are untiered.
- **Agreement (strict):** a played bar agrees when at least half of the performed notes the
  clean copy matched in it are matched, in the copy, to a score note of the same bar label.
- **Agreement (equivalent):** the same, but a bar of identical written content (a literal
  repeat) also counts.

Every statistic is a per-piece ratio of sums over that piece's copies (all four kinds, both
families unless a family is named), then the **mean over pieces**. This is the DF-13 / BL-27
lesson: no ratio of sums across pieces.

**Natural (untouched) copies:**
- **H1:** per family, the mean over pieces of the per-piece difference N - C in rule P clean
  strong and notable+ rates. Rates are over graded bars outside each method's runs and inside
  its span.
- **H2:** on evidently-full targets, the share of targets whose span is whole, and the share of
  their bars marked "not recorded". A target is evidently full when, in the first and in the
  last 5% of graded bars (at least 3 each), more than half the bars are under 50% missed under
  C.

**Criteria** (point estimates decide; piece-bootstrap 95% CIs, 2,000 resamples, seed 0, and
leave-one-piece-out flips are reported):

| Id | Statistic (N unless stated) | Bar |
|---|---|---|
| T1 | span accuracy, pooled | >= 0.97 |
| T2 | never-played bars tiered, pooled | <= 0.03 |
| T3 | played-bar agreement (strict), pooled | >= 0.97 |
| F | T1 / T2 / T3 in each family | >= 0.95 / <= 0.05 / >= 0.95 |
| R1 | Na span accuracy, pooled | >= 0.95 |
| R2 | Na never-played bars tiered, pooled | <= 0.03 |
| R3 | Na played-bar agreement (equivalent), pooled | >= 0.97 |
| H1 | rule P clean strong / notable+ change N - C, per family | within ±0.15 / ±0.30 pt |
| H2 | evidently-full targets: share whole / share of bars not recorded | >= 0.95 / <= 0.002 |

- **PASS** = every row passes. **FAIL** otherwise; there is no partial outcome.
- On PASS, N is recommended as the report default (`align.partial.PARTIAL_DEFAULT = True`)
  once the eval-auditor signs off and the lead accepts it. Until then the flag stays off.
- On FAIL the flag stays off, and the failing rows say what to fix.
- Information, not deciding: everything per kind and per family; C's values for every row
  (baseline); bars dropped from or added to the span; cut bars tiered; played bars tiered strong
  under N, under C and in the clean copy; Na's repeat-path agreement with the clean path; the
  share of natural targets detected as partial, by family; runs under C and N.

**Dev (design data, BL-27 dev pieces; disclosed).**
- **Data:** 238 usable targets (2 suspect); experts from the DF-15 dev run, as in BL-27; 935
  copies.
- **Design changes made after seeing dev results:**
  - (1) A RecursionError (`copy.deepcopy` of long parts) failed 2 targets in a smoke run. Trimming
    now mutates a freshly unfolded part.
  - (2) The first full dev run (v1: snap at 24 notes, margin 2 bars) let 2-bar cuts of the
    13-bar Chopin Op. 28 No. 20 snap to the edge, so they were graded. An offline grid over the
    DTW spans of all dev copies, and the natural copies, gave the snap at 8 notes plus the
    16-note margin (v2). A 32-note margin was slightly worse on every statistic.
  - (3) Thresholds were set after v2.
  - (4) The H1 and H2 bars were tightened (from ±0.25 / ±0.50 pt and 0.01) after the bite check
    below showed the looser bars could not bite.
- **v2 values** (the registered configuration):
  - T1 0.994 (C 0.600);
  - T2 0.0106 (C 0.160);
  - T3 0.997 (C 0.942);
  - F: Transkun V2 0.994 / 0.015 / 0.997, Aria-AMT 0.994 / 0.007 / 0.997;
  - R1-R3 0.987 / 0.0115 / 0.998;
  - H1: Transkun V2 -0.018 / -0.018 pt, Aria-AMT -0.044 / -0.077 pt;
  - H2 0.992 / 0.0002.
- **By kind (N; C in brackets):**

  | Kind | Accuracy | Never-played tiered | Strict agreement |
  |---|---|---|---|
  | start | 0.996 (0.729) | 0.004 (0.174) | 0.999 (0.961) |
  | end | 0.998 (0.718) | 0.005 (0.171) | 0.999 (0.961) |
  | both | 0.994 (0.710) | 0.017 (0.170) | 0.999 (0.972) |
  | excerpt | 0.983 (0.247) | 0.039 (0.161) | 0.953 (0.543) |

  The excerpts' strict agreement is the low cell. Excerpts that lie inside literal repeats go to
  the earlier identical occurrence (equivalent agreement 0.989), for example Chopin Op. 54 and
  Op. 58/2. No method can tell those occurrences apart from the recording alone.
- **Concentration:** T2's heaviest dev piece is Op. 28 No. 20 (0.106, 1-bar cuts on a 13-bar
  piece). The leave-one-piece-out range is 0.002-0.012, and no row flips on any drop.
- **Reachability** (dev, 2,000 resamples of 16 pieces with replacement): every row passes in
  99.35% of resamples. The lowest rows are R2 0.9935, T2 0.9945 and F T2 Transkun V2 0.9975. Dev
  resampling cannot produce pieces unlike dev (DF-13 lesson). The binding rows are expected to be
  T2 / R2 (short pieces, cut bars of repeated material), T3 (excerpts inside literal repeats)
  and H2 (natural Aria-AMT segments that start or end mid-piece but look full).
- **Bite check (harm rows):** dev natural targets were realigned with a sabotaged, edge-happy
  N: `SNAP_NOTES=0 MARGIN_NOTES=0 MARGIN_BARS=0 SHRINK_SHARE=0.2 WHOLE_TOL=0`
  (`--natural-only --tag bite`). Results:
  - H2 whole share 0.784 (fails);
  - share of bars not recorded 0.0035 (fails at 0.002);
  - H1 Aria-AMT -0.18 / -0.36 pt (fails at ±0.15 / ±0.30; it would have passed at the earlier
    ±0.25 / ±0.50);
  - H1 Transkun V2 -0.027 / -0.025 pt (cannot bite there: Transkun natural targets are almost
    all whole even under the sabotage).
  The T rows bite on C, which fails T1, T2 and T3.

**Run.** `OMP_NUM_THREADS=1 uv run python scripts/eval_partial_bl36.py --set heldout --workers
10`. Outputs go to `data/interim/bl36/heldout_*` (gitignored); summaries are copied to
`artifacts/`.

End of the BL-36 pre-registration.

## Falsified if
See the pre-registration above (rows T1-T3, F, R1-R3, H1, H2; PASS needs all).

Anchor hash, computed with
`awk '/^## Pre-registration$/{f=1} f{print} /^End of the BL-36 pre-registration\.$/{exit}' README.md | shasum -a 256`:
`10d5014637b555a3ce07e44e34b0c0ad944bf32693a254e67eefbe96055d51ae` (also in `artifacts/prereg_sha256.txt`), recorded 2026-10-11 07:16 UTC, before any held-out piece was drawn or aligned. Code: HEAD 765e5a5 plus uncommitted changes: `git diff HEAD -- src/pianolens/align/core.py src/pianolens/report src/pianolens/app` sha256 prefix 092afabc47818304; untracked `src/pianolens/align/partial.py` 72626e149757743b, `scripts/eval_partial_bl36.py` 010b7f479cd03f5a.

## Data
PianoCoRe (DATASETS.md) tier A transcriptions: Transkun V2 (PERiScoPe) and Aria-AMT (Aria-MIDI).
Scores come from the PianoCoRe archive.

**Held-out draw** (as pre-registered, seed 3636). 209 pieces were eligible and 137 of them carry
the literal-repeat flag. The 16 drawn pieces:
- **Literal repeats (8):**
  - Beethoven Op. 109/3, Op. 2 No. 1/1 (repeat signs, 4 paths), Op. 2 No. 3/2, Op. 31 No. 1/3;
  - Chopin Op. 35/4, Op. 38;
  - Debussy L. 61;
  - Schumann Op. 16 No. 7 (repeat signs, 4 paths).
- **No literal repeats (8):**
  - Beethoven Op. 53/2;
  - Chopin Op. 28 Nos. 8 and 16;
  - Debussy L. 117 No. 2, L. 136 No. 3;
  - Albéniz Iberia No. 6 (Triana);
  - Ravel Pavane M. 19;
  - Schumann Op. 16 No. 4.

**Usable units.** 800 jobs ran and none failed. 9 experts and 8 targets were suspect (match
ratio below 0.8) and dropped, leaving 312 usable targets (160 Transkun V2, 152 Aria-AMT). The
truncation control gives 1,242 copies: 312 each of start, end and both, and 306 excerpts (6
targets are too short for an excerpt with bars removed on both sides).

## Splits
- No model is fitted. The method, its five constants and every bar were set on the dev pieces
  (BL-27 dev = BL-18b, 12 pieces).
- The held-out pieces are disjoint by piece id from those and from the A-01, BL-18, DF-13 and
  BL-27 sets. Transcription ids used before are excluded.
- Sibling movements of earlier pieces are in the draw: Op. 16 No. 4 and No. 7 next to BL-27's
  Nos. 5 and 6, and Op. 28 Nos. 8 and 16 next to dev No. 20. They are different scores.
- The statistics are means over pieces of per-piece ratios, with piece-bootstrap CIs (2,000
  resamples, seed 0), a t-interval over pieces and leave-one-piece-out flips.

## Baselines
- **C:** the deployed alignment and report rule, on the same copies, experts and truth.
- **Ceiling:** 1 for accuracy and agreement, 0 for never-played bars tiered. No other ceiling
  applies, since the truth is known by construction.

## Method
`scripts/eval_partial_bl36.py`; the method is `src/pianolens/align/partial.py` plus
`align(..., partial=True)` in `align/core.py` (pre-registration above).

## Command
```
# dev (design data)
OMP_NUM_THREADS=1 uv run python scripts/eval_partial_bl36.py --set dev --workers 10 --limit-targets 1 --tag smoke
OMP_NUM_THREADS=1 uv run python scripts/eval_partial_bl36.py --set dev --workers 10                 # v1
OMP_NUM_THREADS=1 uv run python scripts/eval_partial_bl36.py --set dev --workers 10 --tag v2        # registered config
OMP_NUM_THREADS=1 uv run python scripts/eval_partial_bl36.py --set dev --workers 10 --tag v2m32 --override MARGIN_NOTES=32
OMP_NUM_THREADS=1 uv run python scripts/eval_partial_bl36.py --set dev --workers 10 --natural-only --tag bite \
    --override SNAP_NOTES=0 MARGIN_NOTES=0 MARGIN_BARS=0 SHRINK_SHARE=0.2 WHOLE_TOL=0
OMP_NUM_THREADS=1 uv run python scripts/eval_partial_bl36.py --set dev --tag v2 --from-cache --reachability 2000
# held-out
OMP_NUM_THREADS=1 uv run python scripts/eval_partial_bl36.py --set heldout --workers 10
# A-01 information run (personal data, gitignored)
uv run python scripts/a01_henry_reports.py --out data/interim/reports/henry_bl36_off
uv run python scripts/a01_henry_reports.py --partial --out data/interim/reports/henry_bl36
```

## Run record
- **Pre-registration:** hashed 2026-10-11 07:16 UTC (`10d50146...51ae`). The held-out run was
  launched seconds later, and its outputs were written at 07:52 UTC.
  - Machine load was 20-80 from other agents.
  - Code: HEAD 765e5a5 plus the uncommitted BL-36 changes, hashed in "Falsified if".
  - No code or criterion changed after the launch.
- **Before the hash:**
  - The dev runs: smoke, v1, v2, v2m32 and bite.
  - The criteria code and the H1 / H2 tightening.
  - An offline snap simulation over the dev DTW spans (scratch, not kept).
- **No held-out data before the hash.** The literal-repeat flags of the eligible pool were
  computed inside the held-out draw, after the hash.
- **Dev run times:** about 23 min each for 240 targets (14 alignments per target, 10 workers).

## Results

**Held-out: every registered row passes.** Point estimates decide. Brackets give the piece
bootstrap 95% CI. "Pass share" is the share of piece resamples that pass. LOO is the
leave-one-piece-out range; no row flips on any single drop.

| Row | N | Bar | C (baseline) | Bootstrap 95% | Pass share | LOO range |
|---|---|---|---|---|---|---|
| T1 span accuracy | **0.9967** | >= 0.97 | 0.610 | [0.9953, 0.9979] | 1.00 | 0.9965-0.9971 |
| T2 never-played bars tiered | **0.0027** | <= 0.03 | 0.121 | [0.0013, 0.0043] | 1.00 | 0.0021-0.0029 |
| T3 played-bar agreement (strict) | **0.9958** | >= 0.97 | 0.950 | [0.9940, 0.9972] | 1.00 | 0.9956-0.9963 |
| F Transkun V2 (T1 / T2 / T3) | 0.9969 / 0.0023 / 0.9956 | 0.95 / 0.05 / 0.95 | | | 1.00 | |
| F Aria-AMT (T1 / T2 / T3) | 0.9965 / 0.0032 / 0.9959 | 0.95 / 0.05 / 0.95 | | | 1.00 | |
| R1 Na span accuracy | **0.9949** | >= 0.95 | | [0.9922, 0.9971] | 1.00 | 0.9946-0.9959 |
| R2 Na never-played bars tiered | **0.0028** | <= 0.03 | | [0.0014, 0.0044] | 1.00 | 0.0022-0.0030 |
| R3 Na agreement (equivalent) | **0.9968** | >= 0.97 | | [0.9951, 0.9980] | 1.00 | 0.9966-0.9973 |
| H1 Transkun V2 strong / notable+ (pt) | **0 / 0** | ±0.15 / ±0.30 | | [0, 0] | 1.00 | 0 |
| H1 Aria-AMT strong (pt) | **-0.089** | ±0.15 | | [-0.234, -0.004] | **0.79** | -0.095 to -0.023 |
| H1 Aria-AMT notable+ (pt) | **-0.098** | ±0.30 | | [-0.236, -0.008] | 1.00 | -0.105 to -0.038 |
| H2 evidently full: share whole | **0.9969** | >= 0.95 | | [0.9906, 1] | 1.00 | 0.9967-1 |
| H2 evidently full: share of bars not recorded | **0.00004** | <= 0.002 | | [0, 0.00013] | 1.00 | 0-0.00005 |

**By kind** (pooled families; N, with C in brackets; Na is within 0.01 of N in every cell):

| Kind | Copies | Span accuracy | Never-played tiered | Strict agreement | Equivalent agreement |
|---|---|---|---|---|---|
| start | 312 | 0.998 (0.733) | 0.003 (0.130) | 0.998 (0.975) | 0.999 (0.977) |
| end | 312 | 0.998 (0.715) | 0.002 (0.110) | 0.998 (0.968) | 0.998 (0.972) |
| both | 312 | 0.997 (0.709) | 0.003 (0.142) | 0.996 (0.973) | 0.997 (0.977) |
| excerpt (8-32 bars) | 306 | 0.993 (0.286) | 0.004 (0.119) | 0.976 (0.635) | 0.983 (0.652) |

Information:
- **Never-played bars tiered strong** (the BL-27 side finding):
  - pooled bars: C 10.2% vs N 0.15%;
  - mean over pieces: C 11.4% vs N 0.21%.

  BL-27 found 12.9% for 5-25% start / end cuts on other pieces.
- **Copies where strong flags on never-played bars outnumber those on played bars:** C 660 of
  1,242, N 22.
- **Span boundary errors (N):**
  - played bars left out of the span: 166 of 79,675;
  - not-heard bars kept in the span: 164 of 59,026;
  - 3 copies have span accuracy under 0.9.
- **Played bars tiered strong:** clean copies 721, C 2,496, N 1,046.
  - Of the 332 bars N tiers strong that the clean copy did not, 280 sit right next to the cut
    and 33 two bars away (post hoc).
  - The synthetic cut removes notes by actual onset while truth uses expected onsets, so a
    neighbouring bar can lose notes that were played early.
  - In the other direction, 7 bars are strong in the clean copy but not under N.
- **Cut bars** (partly played) tiered: C 433, N 294.
- **Na's repeat path:** it equals the clean path in 93.5% of copies. Where it differs, the bars
  are content-equivalent (R3 0.997, strict 0.994).
- **N alignments with match ratio below 0.8:** 1.2% of copies (C: 64.7%).
- **Natural targets:**
  - Transkun V2: all 160 whole, so C and N are byte-identical.
  - Aria-AMT: 146 of 152 whole. The 6 trimmed targets are Aria-MIDI segments whose first bars
    are 71-100% missed or whose last bars are 83-100% missed (C's alignment).
  - "Passage not heard" runs: 6 under C, 3 under N.
  - Rule P pooled strong 1.095% to 1.070%, notable+ 6.27% to 6.24%.

**H1 Aria-AMT strong is the fragile row** (pass share 0.79), and its sign is a correction, not
harm:
- One piece carries it: Chopin Op. 28 No. 16, -1.09 pt.
- Its target PianoCoRe_088533 is an Aria-MIDI segment that starts and ends inside the piece:
  bars 1-3 are 97 / 96 / 71% missed, and bars 45-46 are 83 / 100% missed.
- Under C those bars were strong flags (6 strong). They are too short and too mixed to form a
  "passage not heard" run.
- Under N they are "not recorded", leaving 1 strong flag.
- Of the 6 trimmed natural targets, 5 changed rates, and all 5 lost strong or notable flags on
  bars that were not recorded. The sixth (PianoCoRe_088563, last 5 bars 97-100% missed) kept its
  rates.

**Henry's A-01 takes** (information; `data/interim/reports/henry_bl36/`, flag off in
`henry_bl36_off/`):
- All 10 reports (5 takes x 2 transcribers) detect the whole piece.
- 9 are identical to the flag-off reports apart from the added `recorded_span` record and the
  date.
- The tenth, 03 Op. 9 No. 3 Aria-AMT, differs only by float noise of at most 5.4e-9 in tier B/C
  values. That report is known not to be run-to-run deterministic (BL-27 report check).
- So his takes are not partial recordings, and his reports do not change.

## Verdict (Provisional)
**PASS by the pre-registered rule.** Every row passes on held-out (T1-T3, F, R1-R3, H1, H2).

- On the truncation control, N grades almost only the recorded bars:
  - span accuracy 0.997 vs 0.610;
  - never-played bars tiered 0.27% vs 12.1%.
- It aligns played bars to the same bars as the uncut copy (strict agreement 0.996 vs 0.950,
  excerpts 0.976 vs 0.635).
- It leaves full recordings as they are: byte-identical whenever the span is whole, which held
  for every Transkun V2 natural target and 96% of Aria-AMT ones.

The pre-registered action applies: N is recommended as the report default, but only after the
eval-auditor signs off and the lead accepts it. Until then `align.partial.PARTIAL_DEFAULT` stays
False, and reports use it only with `--partial` (CLI), `partial=True` (`report_from_files`) or a
job spec `"partial": true` (app).

## Threats to validity
- **The truncation control is synthetic.**
  - Notes are removed by performance time at one or two cut points.
  - Real partial takes may start with noodling or a false start, stop mid-phrase, or skip
    inside the piece; skips are not covered.
  - Truth uses expected onsets while removal uses actual onsets. This blurs the bar next to each
    cut, and that is where N's remaining extra strong flags sit.
- **Literal repeats.** An excerpt inside literally repeated material cannot be placed by the
  recording alone.
  - N picks the earliest identical occurrence, which is why the excerpts' strict agreement is
    0.976 vs equivalent 0.983 here (0.953 vs 0.989 on dev).
  - The learner then sees the earlier occurrence's bar numbers. Asking for the bar range
    (BL-36 option) would remove that.
- **Repeat signs:** only 2 held-out pieces have them (Op. 2 No. 1/1, Op. 16 No. 7). The
  literal-repeat stratum is mostly written-out repetition.
- **H1 for Transkun V2 cannot bite:** every natural Transkun V2 target is whole, here and on
  dev, even under the sabotage. The sabotage moved H2 and H1 Aria-AMT only.
- **"Evidently full" is a proxy** from C's own edge bars. It called Triana PianoCoRe_000900
  full although its first two bars are 100% and 91% missed; N trimmed them, which is probably
  correct.
- **Design choices made on dev after seeing dev results:** the snap and margin constants, and
  the tightened H1 / H2 bars (disclosed above). Dev resampling said 99% pass; held-out passed
  with larger margins than dev on T2 / R2.
- **Family equals corpus** (Transkun V2 = PERiScoPe, Aria-AMT = Aria-MIDI).
- **The report wiring is tested on synthetic scores only.** Same-score and correctness
  references are cut to the target's bars by `restrict_to_score`, which has no real-data run
  here: the A-01 takes were all whole, and the evaluation scores alignment and rule P tiers,
  not full reports.

## For the lead
1. Accept or reject making `partial=True` the default (`align.partial.PARTIAL_DEFAULT`) after
   the audit. The CLI flag, `report_from_files(partial=)` and the app job key `partial` are in
   place. The app's quick wrong-piece check uses the same flag, so short excerpts would no
   longer be stopped as "probably another piece" when it is on. That is a behaviour change to
   review.
2. If adopted, `docs/SCORING_MODEL.md` needs a "not recorded" paragraph (not edited: the flag is
   off).
3. Possible follow-ups (not run):
   - a real partial-take check, for example PianoVAM session takes cut by the BL-19b splitter;
   - an optional learner-given bar range for excerpts inside literal repeats;
   - skip detection (a performer jumping inside the piece), which this method does not handle.
