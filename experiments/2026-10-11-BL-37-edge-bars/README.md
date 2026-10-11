# BL-37: edge bars of a trimmed span
Ticket: BL-37 (from the BL-36 audit)    Hypothesis: none from the plan (alignment and report rule)    Status: Confirmed with caveats (eval-auditor 2026-10-11); flags off pending Henry's choice between k = 0 and k = 1, and BL-39

## Question
With `align(..., partial=True)` (BL-36), the first or last recorded bar of a trimmed span was
tiered strong 12.3% of the time, against 1.1% for the same bar in the uncut recording (BL-36
audit, held-out). Two code defects fed it:
- `_align_partial` filtered the widened alignment after the shrink instead of realigning.
- `restrict_to_score` turned a reference's notes outside the span into extras of the edge bars.

After fixing both, does a gap remain? If it does, does a pre-registered edge-bar policy close it
without hiding injected wrong notes in edge bars, and without regressing what BL-36 established?
(Corrected after the audit: the registered detection rows inject wrong pitches only. Omitted
notes in the edge bar are not ranked under the adopted policy; see "Omissions" in Results.)

## Pre-registration

Written 2026-10-11 after dev runs on the BL-36 dev and BL-36 held-out pieces (both seen; 28
pieces), before any BL-37 held-out piece was drawn or aligned. The anchor hash is recorded in
"Falsified if".

**What changed in the code (all behind `partial=True`; whole recordings untouched).**

1. **Realign after the shrink** (`align/core._align_partial`). BL-36 filtered the widened
   alignment, which left a note tied across the new edge unmatched (missed) and its performed
   note extra.
2. **Optional tie tails** (`partial.trim_part` records them). A note tied in from before the
   span start stays only if the performance matched it. A learner who starts at that bar strikes
   it again; a recording cut after the tie head does not, and the uncut score counts the note in
   the bar before.
3. **Margin only when needed** (`partial.margin_needed`). BL-36 always aligned a span widened by
   2 bars / 16 notes. On dev, the anchored note alignment then pulled the first (last) performed
   notes into the unplayed margin bars, and the real edge bar was reported missed.
   - Measured: in the 49 newly strong edge bars, 597 of 668 lost correct notes were matched one
     or two bars outward, 648 of them into not-heard bars.
   - Now the DTW span and the widened span are both aligned. On each trimmed side, the margin
     bars the widened alignment keeps are used only when they explain performed notes that the
     DTW-span alignment leaves unmatched: at least `MARGIN_EXPLAINS_NOTES` = 3 of them, and at
     least `MARGIN_EXPLAINS_SHARE` = 0.5 of the notes matched there.
4. **`report.io.restrict_to_score`.** A reference's notes outside the span no longer become
   extras of the edge bars:
   - notes matched outside the span are removed;
   - unmatched notes outside the in-span time window are removed;
   - a tie tail is matched to the reference's tie head.
5. **parangonar 3.3.3 ornament-step crash fallback** (`align/core.align_note_arrays`). Disclosed
   under "Fallback check" below.
6. **Candidate edge policy, off by default** (`ReportConfig.edge_low_confidence_bars`). In the
   first (last) k graded bars of a trimmed side, missed notes are low confidence: shown, but not
   counted towards tiers. Wrong pitches still count.

**Methods compared.**
- **C:** today's full alignment.
- **N:** `align(..., partial=True)` with the changes above. The truncation copies use the clean
  repeat path, as in BL-36.
- **Na:** N with repeat path "auto".

Tiers are rule P as in BL-36 (R1(0), 15 same-family experts, extras not counted, "passage not
heard" runs untiered). The edge policies act on the tiers only; runs use the real missed
counts.

**Data.**
- **Data layer:** the committed data layer at 35be26c (BL-35 raw-MIDI guard, BL-38 score fixes)
  or later; the commit at launch is recorded in the Run record.
- **Pool:** PianoCoRe pieces with at least 25 transcriptions per family and exactly one score in
  the archive. Excluded pieces (union, 71 pieces):
  - A-01 (Henry's 5);
  - BL-18 T2 (6);
  - BL-18b = DF-13 dev = BL-27 dev = BL-36 dev (12);
  - DF-13 held-out (16);
  - BL-27 held-out (16);
  - BL-36 held-out (16);
  - plus every piece in `piece_ids.SCORE_VERSION_MISMATCH` (BL-38).
- **Excluded transcription ids:** every id used by the A-01 floor, BL-18, BL-18b, DF-13, BL-27
  or BL-36.
- **Draw** (`scripts/eval_edge_bars_bl37.py`, `heldout_jobs`, seed 3737): as BL-36.
  - The eligible pieces, sorted by id, are permuted. The first 8 with the literal-repeat flag and
    the first 8 without it are taken (flagged pieces fill in if fewer than 8 are unflagged).
  - Per piece and family, the remaining transcriptions are sorted by id and permuted with the
    same generator: 15 experts, then 10 targets.
  - **Then** `pianocore.guard_jobs` (BL-35) drops raw MIDI files that hold far more than the
    score. It runs after the seeded draw, so the draw does not shift; the number of guarded jobs
    is reported.
  - Targets and experts whose clean C alignment is suspect (match ratio below 0.8) are dropped.

**Truncation control.** As BL-36: four kinds per target (`start`, `end`, `both`, `excerpt` of
8-32 bars), the same seeds and truth. Added:
- **Information kind `short`:** excerpts of 4-7 bars at bar boundaries. Not in any registered
  row.
- **Injected copy:** each copy's edge bars (definition below) that the clean copy found with at
  least 3 correct notes and no wrong pitch get 3 wrong pitches (BL-18b's deltas; seed
  `[37, crc32(id)]`) and are realigned by N. Only bars where every expert has at most 1 wrong
  pitch count, so the injection is unambiguous.

**Bars.** For a copy:
- the **first / last recorded bar** (edge bar, `d = 0`) is the played bar next to a removed side
  (truth heard, found by the clean copy), the first fully heard bar after a start cut or the
  last before an end cut;
- **cut bars** are the bars holding a cut point (truth `cut`: partly played), a separate row;
- `d` counts played bars inward from the edge.

The policies use only what a report knows: the first (last) k graded bars of N's score on a
trimmed side.

**Statistics.** Every row is a mean over pieces of a per-piece value (the BL-36 / DF-13 rule),
with a piece bootstrap (2,000, seed 0) and leave-one-piece-out reported. For E1 and E2 the
per-piece value is the mean over its bars of (strong under N with the policy) - (strong in the
uncut clean copy), in percentage points.

**Registered rows** (kinds start / end / both / excerpt; "short" is information):

| Row | Statistic | Bar |
|---|---|---|
| E1 | first / last recorded bars (`d = 0`, no performed note lost to the cut): strong rate under N + policy minus the same bars uncut | within [-1.0, +1.5] pt |
| E2 | cut bars: strong rate under N + policy minus the same bars uncut | at most +1.5 pt (one-sided: a partly played bar has fewer notes to get wrong; hiding real errors is D1 / D2's job) |
| D1 | injected edge bars: strong rate under N + policy minus under N without a policy | at least -5.0 pt |
| D2 | the same for notable or strong | at least -8.0 pt |
| W1 | natural targets whose span is whole and unrefined: C (computed separately) and N identical in alignment pairs, score notes, measures, bar labels and correctness tables and summary | all of them |
| B | the BL-36 rows on N (T1-T3, F, R1-R3, H1, H2), with BL-36's bars | all pass |

**Policy selection** (stated before any held-out result exists):
- The policies, in this order (least intervention first):
  1. **none**;
  2. **missed notes low confidence in the first / last graded bar** (k = 1);
  3. **the same in the first / last two graded bars** (k = 2).
- The adopted policy is the first one in this order whose E1, E2, D1 and D2 all pass on
  held-out. No choosing among several that pass.
- **If none of the three passes E1, E2, D1 and D2:** no policy is adopted
  (`edge_low_confidence_bars` stays 0), the verdict is FAIL, and the failing rows are reported.
- **PASS** needs an adopted policy, and W1 and every B row passing.
- **FAIL** otherwise; there is no partial outcome.
- Either way `PARTIAL_DEFAULT` stays False until the audit and the lead's (and Henry's) decision.
  On PASS the recommendation is `partial=True` with `edge_low_confidence_bars` = the adopted k
  (0 for "none").

**Information, not deciding:**
- everything per kind (including "short"), per family and per `d` (0, 1, 2-5, over 5);
- C and Na for the same bars;
- the mechanism counts;
- edge bars that N's span also calls an edge, and cut bars that are N's first or last graded bar;
- the wrong-piece probe: for each held-out piece, one Transkun V2 target as the full take, a
  4-7-bar and an 8-bar excerpt, aligned with `partial` off and on to its own score and to every
  other held-out score with the same key signature. The output is the Dice match ratio against
  the app's stop threshold of 0.5.

**Dev (design data; disclosed).** BL-36 dev and BL-36 held-out pieces (28, both seen): 5 targets
per piece and family, 270 usable targets (10 suspect), 15 experts each from the BL-36 caches.
The dev processes imported the data layer before BL-35 / BL-38 (35be26c); the BL-35 guard
would drop `PianoCoRe_145175`, which was already a suspect dev target, so no dev rate moves.

- **Sequence of designs, all on dev:**
  1. **Smoke run (1 target per piece and family).** Fixes 1, 2 and 4 alone gave edge strong
     3.35% vs uncut 1.34%. BL-36's held-out audit had 12.3% vs 1.1%.
  2. **Dev run 1 (fixes 1, 2, 4).** Edge minus uncut was +2.95 pt with no policy, and cut bars
     +12.45 pt.
     - Mechanism: see code change 3 (597 of 668 lost notes went into unplayed margin bars).
     - The 2-bar policy then passed E1 by a hair (+1.43 against +1.5) and was adopted in only
       51% of resamples. Too fragile to register; the cause was alignment-level, so it was fixed
       there (change 3).
     - 2 targets crashed in parangonar's ornament step, which led to change 5. They were rerun
       and merged.
  3. **Smoke run 2, then dev v2** (the registered code, `data/interim/bl37/dev_v2_*`). Two
     things were set after seeing smoke run 2:
     - E2 became one-sided (it had been [-2.0, +1.5]; the policies fell just under -2.0 because
       partly played bars lose real errors with their unplayed notes);
     - the policy order became least-intervention first.
- **Dev v2 values** (points; mean over 28 pieces):

  | Policy | E1 | E2 | D1 | D2 |
  |---|---|---|---|---|
  | none | +0.79 | **+17.39** | 0 | 0 |
  | k = 1 | **+0.22** | -1.27 | -0.80 | -3.68 |
  | k = 2 | -0.29 | -1.27 | -1.44 | -5.01 |

  - Under the k = 1 policy the edge strong rate is 0.91% vs 0.69% uncut, and cut bars 0.66% vs
    1.93% (no policy: 19.3%).
  - Injected edge bars are caught strong 58.9% vs 59.7% with no policy (notable+ 76.9% vs
    80.6%).
  - Adopted: k = 1 (none fails E2).
  - W1: 265 of 265 whole targets identical (C computed separately).
  - B: every BL-36 row passes and improves on BL-36 itself (T1 0.9978, T2 0.0041, T3 0.9990,
    R3 0.9992).
  - Information: in short excerpts (4-7 bars) the edge strong rate is 1.40% without a policy and
    0.62% with k = 1 (uncut 1.57%).
- **Mechanism after the changes:** 12 newly strong edge bars remain (no policy). Their lost
  notes split evenly between notes still matched in the bar to another score note (53) and notes
  matched to another bar (53).
- **Reachability** (2,000 resamples of 16 dev pieces): k = 1 adopted in 99.5% (none 0.5%).
  - Lowest rows for k = 1: E2 0.9965, E1 0.9985.
  - Leave-one-piece-out adopts k = 1 for every drop.
- **Bite checks on dev v2:**
  - **E1:** fails for dev run 1's code (+2.95).
  - **E2:** fails for "none" (+17.4).
  - **D1:** fails for capping at notable (-42.2 for k = 1, -58.5 for k = 2) and for untiering
    (the same).
  - **D2:** fails for untiering (-57.6 / -79.1). Capping keeps notable+ by construction (D2 0).
  - The E1 lower bound (-1.0) does not stop untiering (-0.07); D1 does.
  - **W1** is an equality check on whole recordings: no sabotage was run, and it fails on any
    change to the whole-recording path.

**Fallback check (code change 5).** `scripts/check_ornament_fallback_bl37.py` aligned each of
1,623 items twice in one process, with the pre-BL-37 `align_note_arrays` and with the current
one (default `align()`, repeat path "auto"). Items: every nASAP performance with a ground-truth
alignment (1,063), the D-08 key-sensor mistake set (400: the F-08 / BL-28 calibration inputs),
the A-01 floor transcriptions (150; BL-28 floor tables) and Henry's 10 A-01 takes. Results:
- 0 crashed before;
- all 1,623 are identical (alignment list, repeat path, candidate ratios, score note array).

The crash appeared only on trimmed partial spans: 2 BL-37 dev targets
(`PianoCoRe_041852`, `PianoCoRe_061861`). No registered experiment's stored outputs came from
runs that crashed and were dropped: BL-27 and BL-36 report 0 failed jobs.


**Run.**
```
OMP_NUM_THREADS=1 uv run python scripts/eval_edge_bars_bl37.py --set heldout --workers 10
OMP_NUM_THREADS=1 uv run python scripts/eval_edge_bars_bl37.py --set heldout --probe --workers 10
```
Outputs go to `data/interim/bl37/heldout_*` (gitignored); summaries are copied to `artifacts/`.

End of the BL-37 pre-registration.

## Falsified if
See the pre-registration above (policy selection by E1, E2, D1, D2 in the registered order; W1
and every BL-36 row must pass).

Anchor hash, computed with
`awk '/^## Pre-registration$/{f=1} f{print} /^End of the BL-37 pre-registration\.$/{exit}' README.md | shasum -a 256`:
`4b1e7374037cb3abf6e69968114a083b03a33be3abce35a5e80820c44aeba86c` (also in `artifacts/prereg_sha256.txt`), recorded 2026-10-11 13:20 UTC, before any BL-37 held-out piece was drawn or aligned. Code and data layer: HEAD 805f681 (contains 35be26c and 805f681) plus the uncommitted BL-37 changes: `git diff HEAD -- src/pianolens/align src/pianolens/report` sha256 prefix 93009ee8680b080e; untracked `scripts/eval_edge_bars_bl37.py` 2feeff274280beba; `scripts/eval_partial_bl36.py` (committed) 010b7f479cd03f5a.

## Data
PianoCoRe (DATASETS.md) tier A transcriptions: Transkun V2 (PERiScoPe) and Aria-AMT
(Aria-MIDI). Scores come from the PianoCoRe archive; data layer at 805f681 (BL-35 guard, BL-38
score fixes).

**Held-out draw** (seed 3737, as pre-registered):
- 193 eligible pieces, 129 of them with the literal-repeat flag; 800 jobs drawn; the BL-35 guard
  dropped 0.
- **Literal repeats (8):** Beethoven Op. 28/2 (16 repeat paths); Chopin Op. 10 No. 8, Op. 25
  No. 2; Debussy L. 100 No. 3, Children's Corner No. 5; Albéniz Iberia No. 3 (El Corpus en
  Sevilla); Schubert D. 899 No. 3; Tchaikovsky Op. 37a No. 10.
- **No literal repeats (8):** Bach BWV 846 Prelude; Beethoven Op. 22/2, Op. 2 No. 1/2, Op. 31
  No. 2/2, Op. 81a/2; Chopin Op. 28 No. 2, Op. 29; Debussy L. 136 No. 9.

## Splits
- No model is fitted. The code changes, the policy candidates, their order and every bar were set
  on the dev pieces: BL-36 dev and BL-36 held-out, 28 pieces.
- The BL-37 held-out pieces are disjoint by piece id from every earlier draw (listed in the
  pre-registration) and from the score-version-mismatch pieces. No transcription id was used
  before.
- Sibling movements of earlier pieces are in the draw (Op. 2 No. 1/2 next to BL-36's Op. 2
  No. 1/1, Op. 28 No. 2 next to other preludes). They are different scores.
- Statistics are means over pieces of per-piece values, with piece bootstrap (2,000, seed 0),
  t-intervals over pieces and leave-one-piece-out.

## Baselines
- **C:** today's full alignment, on the same copies.
- **N with no edge policy:** the first policy in the order, which is the policy baseline.
- **The uncut clean copy:** the reference rate for the same bars.

## Method
`scripts/eval_edge_bars_bl37.py`, built on `scripts/eval_partial_bl36.py`. Code changes and rows
as in the pre-registration.

## Command
```
# design (dev)
OMP_NUM_THREADS=1 uv run python scripts/eval_edge_bars_bl37.py --set dev --workers 10 --limit-targets 1 --tag smoke
OMP_NUM_THREADS=1 uv run python scripts/eval_edge_bars_bl37.py --set dev --workers 10 --limit-targets 5        # dev run 1
OMP_NUM_THREADS=1 uv run python scripts/eval_edge_bars_bl37.py --set dev --workers 10 --limit-targets 1 --tag smoke2
OMP_NUM_THREADS=1 uv run python scripts/eval_edge_bars_bl37.py --set dev --workers 10 --limit-targets 5 --tag v2 --reachability 2000
OMP_NUM_THREADS=1 uv run python scripts/check_ornament_fallback_bl37.py --workers 10
# held-out
OMP_NUM_THREADS=1 uv run python scripts/eval_edge_bars_bl37.py --set heldout --workers 10
OMP_NUM_THREADS=1 uv run python scripts/eval_edge_bars_bl37.py --set heldout --probe --workers 10
```

## Run record
- **Pre-registration:** hashed 2026-10-11 13:20 UTC (`4b1e7374...a86c`).
- **First held-out launch (13:20 UTC) crashed before drawing anything.**
  - Cause: `heldout_jobs` submitted `bl36.literal_repeat_flag` (and the expert worker
    `bl36.expert_one`) to spawned workers, which cannot import a module loaded by path.
  - No draw output, flag or alignment had been written; `data/interim/bl37/` held no held-out
    file.
  - **Deviation:** two module-level wrappers (`_flag`, `_expert`) were added to the script after
    the hash. Its sha256 prefix changed from 2feeff274280beba to e73068ae59142171. No logic,
    seed, row or bar changed.
  - Relaunched at 13:21 UTC.
- **Dev disclosures:** in the pre-registration (dev processes used the data layer before 35be26c;
  `PianoCoRe_145175` was a suspect dev target, dropped anyway).
- **The dev changes did not decide the held-out result** (added after the audit, fix 6; audit
  section 1):
  - k = 1 also passes the original two-sided E2 bar [-2.0, +1.5] (-0.63).
  - Under the original order (k = 2, k = 1, none) k = 2 passes all four rows and would have been
    adopted. The reorder picked the smaller intervention.
  - The script deviation (two wrappers) was reversed by the audit and hashes to the registered
    `2feeff274280beba`; it is plumbing only.
- **Held-out run:** outputs written at 14:23 UTC. 800 jobs, 0 failed.
  - 1 target was suspect, leaving 319 usable (160 Transkun V2, 159 Aria-AMT).
  - 1,264 truncation copies: 319 each of start, end and both, and 307 excerpts. Plus 319
    information-only excerpts of 4-7 bars.
- **Wrong-piece probe:** run afterwards on the cached jobs, with no code change (script sha256
  prefix still e73068ae59142171).

## Results

**Held-out: PASS. The adopted policy is k = 1**: missed notes are low confidence in the first or
last graded bar of a trimmed side.
- "none" fails E2, so it is not adopted.
- Points are means over 16 pieces, with the piece-bootstrap 95% interval and the t-interval.
- "Pass share" is the share of piece resamples in which the row passes.
- Leave-one-piece-out adopts k = 1 for every drop.

| Row | none | **k = 1 (adopted)** | k = 2 | Bar |
|---|---|---|---|---|
| E1 first / last recorded bar minus uncut (1,862 bars) | +0.27 [0.00, 0.59] | **-0.05** [-0.37, 0.22], t [-0.36, 0.26]; pass share 1.00; LOO -0.11 to +0.06; worst piece L. 100 No. 3 -1.69 | -0.44 | [-1.0, +1.5] |
| E2 cut bars minus uncut (1,091 bars) | **+19.52** [17.37, 21.65] (fails) | **-0.63** [-1.26, -0.17], t [-1.25, -0.01]; pass share 1.00; LOO -0.67 to -0.38 | -0.63 | at most +1.5 |
| D1 injected edge bars, strong, vs none (1,508 bars) | 0 | **-0.51** [-0.96, -0.14], t [-0.98, -0.05]; pass share 1.00; worst piece Op. 29 -2.44 | -1.51 | at least -5.0 |
| D2 the same, notable or strong | 0 | **-3.82** [-5.53, -2.27], t [-5.73, -1.92]; pass share 1.00; LOO -4.08 to -3.26; worst piece Op. 29 -12.2 | -5.38 (pass share 0.99) | at least -8.0 |

Absolute rates (mean over pieces):

| Policy | Edge bars strong | Cut bars strong | Injected strong / notable+ |
|---|---|---|---|
| none | 0.82% | 20.4% | 59.6% / 82.0% |
| k = 1 | 0.49% | 0.27% | 59.1% / 78.2% |
| uncut | 0.54% | 0.90% | |

**W1: 304 of 304** natural targets whose span was whole and unrefined are identical between C
(computed separately) and N: alignment, score notes, measures, bar labels, correctness tables
and summary. 2 more targets were whole only after refinement (both edges reached), so W1 does not
cover them.

**B (BL-36 rows on N): all pass by the registered point estimates.**
- Truncation rows:
  - T1 0.9973, T2 0.0007, T3 0.9974;
  - F: Transkun V2 0.9977 / 0.0007 / 0.9973, Aria-AMT 0.9969 / 0.0008 / 0.9975;
  - R1-R3 0.9952 / 0.0008 / 0.9979.
- Natural rows:
  - H1 Transkun V2 -0.081 / -0.051 pt;
  - H1 Aria-AMT **-0.1446** / -0.197 pt (bars ±0.15 / ±0.30);
  - H2 0.981 / 0.0004.
- **H1 Aria-AMT strong is fragile:**
  - it sits 0.005 pt inside its bar;
  - dropping any of 10 of the 16 pieces flips it;
  - 55% of piece resamples pass it, and the whole B block passes in 53%;
  - H1 Transkun V2 strong passes in 74%.
- **Its sign is mostly a correction** (corrected after the audit, fix 3).
  - 13 natural targets were trimmed (12 Aria-AMT, 1 Transkun V2). 10 of them lost strong or
    notable flags on bars N marks not recorded; 3 kept the same counts.
  - 7 of the 13 are not evidently full: segments that start or end inside the piece.
  - The other 6 are evidently full by the proxy (Op. 31 No. 2/2, Op. 10 No. 8, three of
    Op. 29, L. 136 No. 9). 1-5 of their edge bars were marked not recorded.
  - Most bars N marks not recorded were at least half missed under C as well (audit section 5).
  - Three were mostly found under C, so a correction cannot be shown for them:
    - Op. 28 No. 2 Transkun V2, bar 2: 5 of 16 missed, strong;
    - Op. 29 PianoCoRe_097532, bar 126: 3 of 10 missed, strong;
    - Op. 29 PianoCoRe_097409, bar 125: 0 of 5 missed.
- **B with the adopted policy applied** (information, added after the audit, fix 2; the
  registered B was run on N without a policy and passes):
  - H1 Aria-AMT strong is **-0.1548**, outside its ±0.15 bar. Its pass share is 0.48, and 3 of 16
    leave-one-out drops flip it back.
  - H1 Aria-AMT notable+ is -0.207 (passes); Transkun V2 is unchanged (-0.081).
  - The policy removes 2 strong flags in the last graded bar of two evidently-full Op. 29
    Aria-AMT targets (PianoCoRe_097361 3 to 2, _097409 5 to 4). Audit measurement.
  - C's baseline rows: T1 0.617, T2 0.110, T3 0.947.

**By distance from the edge** (strong rate, mean over pieces, all kinds incl. short; played bars
that lost no notes):

| Bars | Uncut | C | N, none | N, k = 1 |
|---|---|---|---|---|
| Cut bar (partly played) | 0.89% | 36.5% | 20.4% | 0.27% |
| d = 0 | 0.57% | 25.2% | 0.82% | 0.41% |
| d = 1 | 0.72% | 17.9% | 0.68% | 0.64% |
| d = 2-5 | 0.64% | 7.5% | 0.62% | 0.62% |
| d > 5 | 0.72% | 1.1% | 0.68% | 0.68% |

- BL-36's N had 12.3% (edge) vs 1.1% (uncut) on its own held-out pieces (audit).
- The k = 1 edge rate by kind: start 0.95, end 0.31, both 0.63, excerpt 0.16, short (4-7 bars)
  0.17; by family Aria-AMT 0.50, Transkun V2 0.33.
- 77% of edge bars are also N's own first / last graded bar; a cut bar is N's edge in 43% of cases
  (otherwise it was shrunk away).

**Omissions** (added after the audit, fix 1; audit section 3).
- **What the audit ran:** 128 held-out targets, 285 registered-kind copies, 342 eligible first /
  last recorded bars per level. It deleted correct notes, realigned with N and measured the rate
  of notable or strong. The same bars without a deletion are notable or strong 1.5% of the time.

| Deleted | Uncut recording | N, none | N, k = 1 | k = 1 minus none (mean over pieces) |
|---|---|---|---|---|
| 3 notes (the bars have a median of 16 correct notes) | 69.0% (strong 17.5%) | 60.2% (strong 12.3%) | **17.3%** (strong 5.8%) | -41.6 pt [-50.5, -32.5]; strong -9.6 [-15.2, -4.8] |
| half the correct notes (median 8 of 16) | 99.4% (strong 98.5%) | 36.0% (strong 34.8%) | 26.3% (strong 25.7%) | -10.9 pt [-17.1, -6.0] |

- **Measured the way D1 / D2 are,** both rows would fail (-5.0 / -8.0). The registered D1 / D2
  inject wrong pitches only, which the policy cannot hide by construction.
- **When the bar is N's own edge** (233 of 342), the policy hides 3 omitted notes from the
  tiers completely: 0.0% vs 63.1% with no policy.
  - Excerpts aligned to bar lines (a learner who starts at a bar line) are always N's edge:
    0.0% vs 65.1%.
  - The notes are still listed, shown but not ranked.
- **Half-bar omissions are lost without any policy:** N's shrink rule (`SHRINK_SHARE` 0.5)
  marks 63.7% of those bars "not recorded". This comes from BL-36's design.

**Mechanism** (no policy). 9 newly strong edge bars remain, 2 of them with a note lost to the
cut. Of their lost correct notes, 43 went to another bar and 26 to another note in the same
bar. Too few to name one cause.

**Wrong-piece probe** (information).
- Every pair whose key signature (number of sharps or flats; mode not read) matches is used:
  10 pairs from 4 groups.
- **Wrong score, `partial` on:** the highest Dice ratio is 0.39 (an 8-bar excerpt of Chopin Op. 10
  No. 8 on Tchaikovsky Op. 37a No. 10). Many wrong-score alignments shrink to one unmatched bar
  (ratio 0).
- **Wrong score, `partial` off:** at most 0.26.
- **Right score, `partial` on:** excerpts score 0.81-1.0 (with it off, 0.006-0.57).
- **Full takes:** the same with either setting.
- With the app's stop at 0.5, `partial` on removes the false stop on real excerpts and lets none
  of these 10 same-key pairs through (margin 0.11).
- **That margin does not hold over all pairs** (corrected after the audit, fix 4; audit section 7).
  The audit aligned the 16 probe excerpts with `partial` on to every other held-out score and
  every dev score (1,376 wrong-score alignments).
  - 2 reached the stop at 0.5, both 4-7-bar excerpts: Chopin Op. 25 No. 2 on Beethoven Op. 2
    No. 1/1 at 0.524, and Op. 29 on Op. 54 at 0.504.
  - 8 were at or above 0.45, and 28 at or above 0.40.
  - Same-key pairs are not the hard case.
- No sibling-movement or quotation pair was in the draw.
- **Fallback (corrected after the audit, fix 5):**
  - For calls that do not crash, the new `align_note_arrays` makes the same matcher call as the
    old one. Identity on non-crashing calls therefore holds by construction, and the 1,623-item
    check measures "0 crashes on full scores".
  - The crash path was verified on the two dev targets (`PianoCoRe_041852`, `_061861`). Only
    their 4-7-bar "short" copies crashed the old code. There the new result equals the alignment
    with `process_ornaments=False` and has 0 unmatched performed notes (audit section 6).

## Verdict: Confirmed with caveats (eval-auditor 2026-10-11); flags off pending Henry's choice between k = 0 and k = 1, and BL-39
**PASS by the pre-registered rule.** The adopted edge policy is k = 1: missed notes in the first
or last graded bar of a trimmed side are low confidence. W1 and every BL-36 row pass.

- **The two BL-36 defects are fixed and tested** (the former strict xfails pass).
- **The edge gap has an alignment cause.** BL-36's margin let the anchored note alignment pull
  edge notes into unplayed bars. The DTW-span alignment with a margin only where needed brings
  first / last recorded bars to 0.82% strong vs 0.54% uncut without any policy (BL-36: 12.3% vs
  1.1%).
- **What the policy is for:** cut bars (partly played), which N still flagged 20.4% of the time.
  - With k = 1 they are 0.27% (uncut 0.90%), and edge bars 0.49%.
  - Injected wrong notes in edge bars are still caught: strong 59.1% vs 59.6%, notable+ 78.2% vs
    82.0%.
- **Omitted notes in the edge bar are not ranked** (added after the audit, fix 1).
  - 3 omitted notes in a first or last recorded bar are ranked 60.2% of the time with no policy
    and 17.3% under k = 1. When the bar is N's own edge, the rate is 0%.
  - The notes stay listed as low confidence. k = 1 is a trade: fewer false strong flags on
    partly played bars against hidden omissions in the edge bar. It is not a pure gain.
  - With k = 1 applied, H1 Aria-AMT strong is -0.155 (information; outside ±0.15).
- **Whole recordings** stay identical: 304 of 304, measured.
- **The fallback** changed none of 1,623 full-score alignments.

Recommendation on the registered action, as worded before the audit: `partial=True` with
`edge_low_confidence_bars = 1`. After the audit:
- `partial=True` with the BL-37 fixes is supported on its own (k = 0 passes E1, +0.27 pt).
- The choice between k = 0 and k = 1 is Henry's.
- A narrower policy is the next ticket (BL-39).
- `PARTIAL_DEFAULT` stays False and `edge_low_confidence_bars` stays 0.

## Threats to validity
- **The truncation control is synthetic.** Real takes have false starts, noodling and skips; none
  is covered.
- **The dev design was iterated four times on seen pieces** (disclosed in the pre-registration):
  the margin rule, E2 made one-sided and the policy order were all set on dev. Held-out passed
  with wider margins than dev on every E / D row.
- **H1 Aria-AMT strong** passed by 0.005 pt with 10 of 16 flipping drops, and the B block passes
  in 53% of resamples. Its direction is fewer strong flags on bars marked not recorded, and the
  row is two-sided by registration (BL-36 audit point 6). It cannot tell a correction from harm.
- **D1 / D2 measure detection of 3 injected wrong pitches only.** Omissions are what the policy
  hides by design. The audit sized it: 3 omitted notes in an edge bar are ranked 60.2% with no
  policy and 17.3% under k = 1, and 0% when the bar is N's own edge. A learner who drops notes
  in their first recorded bar loses that flag (see "Omissions").
- **The probe is small:** 10 same-key pairs, matched by key signature, no sibling movements.
- **The policy is evaluated offline** on the cached bar tables with the BL-37 script's tier
  function (corrected after the audit, fix 7). The audit tiered 70 reconstructed held-out cut
  copies with the production `report.build._correctness_section` at k = 0 and k = 1 (fast
  repeats off, as in rule P):
  - 0 of 3,611 graded bars differ from the eval function;
  - the policy changes the same 51 tiers.

  With the production default for transcribed input (fast-repeat low confidence on, BL-25),
  48 bars differ from rule P. That gap predates BL-37.
- **Family equals corpus** (Transkun V2 = PERiScoPe, Aria-AMT = Aria-MIDI).

## For the lead
1. **Adoption of `partial=True` with `edge_low_confidence_bars = 1`,** after the audit, with
   Henry. The app's quick wrong-piece check uses the same flag (probe above).
2. **H1 is two-sided and counts corrections as change.** Its fragility here (and in BL-36) comes
   from trimmed natural segments. A future registration could restrict H1 to evidently-full
   targets (BL-36 audit point 6).
3. **SCORING_MODEL** needs the "not recorded" paragraph and the edge low-confidence sentence if
   adopted (not edited: both flags are off).
4. **The fallback** (`align_note_arrays`) touches every alignment path but changed nothing on
   1,623 full-score alignments. It only rescues calls that crash today.

## Audit (eval-auditor, 2026-10-11)

**Verdict: Confirmed with caveats.** PASS by the pre-registered rule is the correct reading, and
every registered number reproduces exactly from the cache. There is no pre-registration drift, no
leakage and no selection on held-out data. The adoption recommendation (`partial=True` with
`edge_low_confidence_bars = 1`) does not follow from the table as written, for two reasons:
- D1 / D2 inject wrong pitches only, which the policy cannot hide by construction. Injected
  omissions show the harm the policy does create: 3 omitted notes in a first / last recorded bar
  are flagged notable or strong 60.2% of the time without the policy and 17.3% with it.
- With the adopted policy switched on, H1 Aria-AMT strong is -0.155 pt against its ±0.15 bar. B
  was registered and run on N without a policy, so the registered PASS stands.

**1. Pre-registration, timeline, drift.**
- The anchor recomputes to `4b1e7374...a86c`, as in `artifacts/prereg_sha256.txt`.
- Transcript `subagents/agent-a9af24a6302e4c775.jsonl`:
  - hash 13:20:36Z, first launch in the same call;
  - the first launch crashed at 13:20:58Z in the literal-repeat flags (`ModuleNotFoundError:
    bl36` in spawned workers), with no file written;
  - wrapper edit and relaunch 13:21:14Z, then `heldout_draw.json` written 13:21:59Z.
  - No earlier tool call reads a held-out file, the draw or seed 3737; the only matches are
    edits that write `heldout_jobs`.
- **Script deviation.** The audit reversed the 13:21:14Z edit on the committed script. The
  result hashes to `2feeff274280beba`, the hashed value. The diff is the two module-level
  wrappers plus the two call sites that use them, so it is plumbing only.
- **src.** `git diff 805f681 d71a3f4 -- src/pianolens/align src/pianolens/report` hashes to
  `93009ee8680b080e`, the hashed diff. No src file changed between the hash and the commit.
- **Disjointness.**
  - 0 of the 16 held-out pieces are in the 72 excluded pieces (71 plus the 1
    `SCORE_VERSION_MISMATCH` piece) or in the 28 dev pieces.
  - 0 of the 800 transcription ids are among the 4,320 earlier ids.
- **Dev changes made before the hash** (disclosed) did not decide the held-out result:
  - k = 1 also passes the original two-sided E2 bar [-2.0, +1.5] (-0.63).
  - Under the original order (k = 2, k = 1, none; transcript 10:40Z) k = 2 passes all four
    rows and would have been adopted. The reorder chose the smaller intervention.
  - Smoke run 2 failed every policy on the old E2 lower bound (-2.04). That was the reason to
    make E2 one-sided, and it was on dev.

**2. Reproduction.**
- `evaluate()` on `data/interim/bl37/heldout_rows.pkl` (read-only import, 311 s) reproduces
  every value exactly:
  - E1 / E2 / D1 / D2 for all three policies;
  - W1 304 of 304;
  - all 21 BL-36 values;
  - the bar counts 1,862 / 1,091 / 1,508.
- Piece bootstrap with another seed: E1 [-0.32, 0.22], E2 [-1.25, -0.17], D1 [-0.95, -0.14],
  D2 [-5.58, -2.17]. The t-intervals match the README.
- **Re-run alignments.**
  - 128 targets (4 per piece and family): C tables 128 of 128 equal the cache, cut windows 285
    of 285, N on the start copies 61 of 61.
  - 70 more cut copies: N 70 of 70.
  - W1 run independently on one whole, unrefined target per piece and family, with C and N
    aligned separately: 32 of 32 identical.

**3. Harm criteria: omissions (the main caveat).** The audit ran its own probe (scratch, not
kept) on the same 128 targets and their 285 registered-kind copies.
- **Method.**
  - Bars: each first / last recorded bar (d = 0, no note lost to the cut) where the clean copy
    has at least 4 correct notes and no wrong pitch, and where every expert has at most 1
    missed note.
  - Deletion: correct performed notes are deleted, then the copy is realigned with N.
  - Compared: N with no policy, N with k = 1, and the same deletion in the uncut recording (C).
  - Rate is notable or strong; 342 bars per level, all 16 pieces. Without any deletion the same
    bars are notable or strong 1.5% of the time.

| Deleted | Uncut recording | N, none | N, k = 1 | k = 1 minus none, mean over pieces |
|---|---|---|---|---|
| 3 notes (median of 16 correct) | 69.0% (strong 17.5%) | 60.2% (strong 12.3%) | **17.3%** (strong 5.8%) | -41.6 pt [-50.5, -32.5]; strong -9.6 [-15.2, -4.8] |
| half the correct notes (median 8 of 16) | 99.4% (strong 98.5%) | 36.0% (strong 34.8%) | 26.3% (strong 25.7%) | -10.9 pt [-17.1, -6.0] |

- **Measured as D1 / D2 are**, both rows would fail D1 (-5.0) and D2 (-8.0).
- **When the bar is N's own edge, the policy hides 3 omitted notes completely.**
  - That is 233 of 342 bars: 0.0% under k = 1, 63.1% under none.
  - Bar-aligned excerpts (a learner who starts at a bar line) are always N's edge: 0.0% vs
    65.1%.
  - The notes are still listed, "shown but not ranked".
- **Half-bar omissions are already lost without any policy.** N's shrink rule
  (`SHRINK_SHARE` 0.5) marks 63.7% of those bars "not recorded". This comes from BL-36's design,
  not from BL-37.
- **The bite checks** (capping, untiering) show that D1 / D2 can fail other policies. They
  cannot show harm for a policy that acts on missed notes only. The author's Threats section
  names the hole; the numbers above size it.

**4. Production code and the eval tier function.** The audit reconstructed 70 held-out cut copies:
40 with a tier changed by the policy and 30 random copies with an N edge. Each was realigned
with N and tiered by `report.build._correctness_section`, with the same inputs `build_report`
gets and `edge_low_confidence_bars` 0 and 1, fast repeats off as in rule P.
- 0 of 3,611 graded bars differ from the eval tier function at k = 0 and at k = 1.
- The edge bars are identical in 70 of 70 copies, and the policy changes the same 51 tiers.
- With the production default for transcribed input (fast-repeat low confidence on), 48 bars
  differ from rule P. That gap predates BL-37 (BL-25).

**5. H1.**
- The author's fragility figures reproduce: pass share 0.55, 10 of 16 leave-one-out drops flip
  it.
- With k = 1 applied to the natural targets: Aria-AMT strong **-0.1548** (fails ±0.15).
  - Pass share 0.48; 3 of 16 drops flip it back.
  - Notable or strong -0.207 (passes ±0.30). Transkun V2 is unchanged (-0.081).
  - The policy removes 2 strong flags in the last graded bar of two evidently-full Op. 29
    Aria-AMT targets (PianoCoRe_097361 3 to 2, _097409 5 to 4).
- **"Correction" on the units.** Most bars N marks not recorded were at least half missed under
  C too: the openings of BWV 846, Op. 10 No. 8, Op. 31 No. 2/2, Op. 37a No. 10 and Iberia No. 3
  bars 0-42. This supports a correction there.
- Three bars were mostly found under C, so a correction cannot be shown for them:
  - Op. 28 No. 2 Transkun V2 bar 2: 5 of 16 missed, strong;
  - Op. 29 _097532 bar 126: 3 of 10 missed, strong;
  - Op. 29 _097409 bar 125: 0 of 5 missed.

**6. Ornament fallback.**
- For calls that do not crash, the new code makes the same matcher call as the old code (the
  copies are only kept for the retry), so identity holds by construction. The 1,623-item check
  therefore measures "0 crashes on full scores".
- A 102-item sample (every 16th item) gives 0 crashes and 102 identical.
- **Crash path.** In both dev targets, only the 4-7-bar "short" copy crashes the old code. There
  the new result equals the alignment with `process_ornaments=False`, with 0 unmatched performed
  notes, which is what the comment says.
- parangonar's `na_within` returns a plain list for an empty input, and that list cannot join a
  structured array. The fallback is sensible.

**7. Wrong-piece probe.** Same-key pairs are not the hard case. The audit aligned the probe's own
16 excerpts with `partial` on to every other held-out score (15) and every dev score (28): 1,376
wrong-score alignments.
- Highest ratios: 0.524 (Chopin Op. 25 No. 2, 4-7 bars, on Beethoven Op. 2 No. 1/1) and 0.504
  (Op. 29, 4-7 bars, on Op. 54).
- 2 are at or above the app's stop of 0.5, 8 at or above 0.45, and 28 at or above 0.40.
- Right-score excerpts score 0.81-1.0 (the author's 32).
- So "lets no probed wrong piece through, margin 0.11" holds only for the 10 same-key pairs. A
  stop between 0.53 and 0.81 would separate the sets observed here, but that needs its own
  ticket.

**8. Claim against evidence.**
- Supported:
  - the alignment-level fix of the BL-36 edge gap: edge bars 0.82% vs 0.54% uncut, with no
    policy;
  - whole recordings unchanged;
  - the cut-bar fix;
  - "injected wrong pitches are still caught".
- Not supported as worded:
  - The Question's "without hiding real mistakes in edge bars". Omissions in N's edge bar are
    hidden from the tiers by design.
  - "Its sign is a correction". That holds for most of the units, not all.
  - The probe margin.

**Required fixes (author).**
1. Add the omission result (section 3) to Results, Verdict and Threats. Reword the Question /
   Verdict to say wrong pitches are kept and omissions in N's edge bar are not ranked, with
   the numbers.
2. Report B under the adopted policy (section 5: H1 Aria-AMT strong -0.155, pass share 0.48),
   labelled as information. The registered B (no policy) passes.
3. Change "Its sign is a correction" to "mostly a correction" and list the three
   mostly-found bars.
4. Replace the probe's margin sentence with the all-pairs result (2 of 1,376 at or above 0.5,
   both 4-7-bar excerpts), or report both.
5. Fallback: say that identity on non-crashing calls holds by construction, that the check
   measures 0 crashes, and that the crash path was verified on the two dev short excerpts.
6. In the Run record, note that the dev changes did not decide held-out: the original E2 bar
   also passes, and the original order would have adopted k = 2.
7. Add the production-vs-eval agreement (section 4) to the Threats item that says the
   production policy is tested on synthetic scores only, and note the fast-repeat difference.

**For the lead (adoption).**
- `partial=True` (BL-36 plus the BL-37 fixes) is supported on its own: k = 0 passes E1 (+0.27
  pt), whole recordings are identical, and the BL-36 rows hold.
- k = 1 is a trade, not a pure gain. A partly played first bar is falsely strong 20.4% of the
  time under k = 0 and 0.27% under k = 1. But 3 notes a learner omits in the first / last
  recorded bar are ranked 60% of the time under k = 0 and 17% under k = 1 (never when the bar
  is N's edge), and H1 under k = 1 misses its bar by 0.005 pt.
- Missed notes stay listed as low confidence, which limits the harm.
- **Suggested next step** (new ticket, pre-registered): a narrower policy that makes low
  confidence only the missed notes expected before the first performed note of the edge bar
  (after the last, at the end), with a registered omission-injection row next to D1 / D2.
- Until then the choice between k = 0 and k = 1 is Henry's.
- The app's wrong-piece stop at 0.5 should be revisited before `partial` goes on in the app
  (section 7).

### Corrections after the audit (2026-10-11)

By `feature-engineer`, applying the audit's author fixes 1-7.
- The pre-registration is not edited. Its anchor hash was re-checked after every edit and is
  still `4b1e7374037cb3abf6e69968114a083b03a33be3abce35a5e80820c44aeba86c`.
- Status: Confirmed with caveats (eval-auditor 2026-10-11). The flags stay off pending Henry's
  choice between k = 0 and k = 1, and BL-39.
- The numbers below are the audit's measurements, copied from its sections. I did not re-run
  them.

1. **Omissions** (fix 1). Added a Results subsection "Omissions" with the audit's deletion table:
   - 3 omitted notes are ranked 60.2% with no policy, 17.3% under k = 1, and 0% when the bar is
     N's own edge;
   - half-bar omissions are 36.0% vs 26.3%, and 63.7% of those bars are shrunk to "not
     recorded".

   Also reworded the Question (the detection rows inject wrong pitches only), and added an
   omissions bullet to the Verdict and to Threats.
2. **B under the adopted policy** (fix 2), labelled as information: H1 Aria-AMT strong -0.1548
   (pass share 0.48, 3 of 16 drops flip it back), notable+ -0.207, Transkun V2 -0.081. The
   registered B (no policy) passes.
3. **"Mostly a correction"** (fix 3), listing the three bars N marks not recorded that were
   mostly found under C:
   - Op. 28 No. 2 Transkun V2, bar 2;
   - Op. 29 _097532, bar 126;
   - Op. 29 _097409, bar 125.
4. **Probe** (fix 4). Both results are reported. No same-key pair reached 0.5, but over all
   1,376 wrong-score alignments 2 did (0.524 and 0.504, both 4-7-bar excerpts), 8 were at or
   above 0.45 and 28 at or above 0.40.
5. **Fallback** (fix 5). Identity on non-crashing calls holds by construction, so the 1,623-item
   check measures 0 crashes on full scores. The crash path was verified on the two dev short
   excerpts. The pre-registration paragraph "Fallback check" stays as registered.
6. **Run record** (fix 6). The dev changes did not decide held-out: the original two-sided E2
   bar also passes (-0.63), and the original order would have adopted k = 2. The script
   deviation is plumbing only, and reverting it gives the registered hash.
7. **Production vs eval** (fix 7). Threats now gives the audit's agreement check (0 of 3,611
   graded bars differ; the same 51 tiers change). It also notes the 48-bar fast-repeat
   difference against rule P under the production default for transcribed input (BL-25).
