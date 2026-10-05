# R-10 pre-run review (eval-auditor, 2026-10-05)

This is a design review before the box run, not a results audit. No model or baseline output on
the fresh pieces existed when it was written, and none was produced by it. Everything below was
measured on expert renditions, development data, PERiScoPe / PianoCoRe metadata and scores, and
the author's transcript.

## Verdict: ready after the listed amendments

The design is sound and the hashed pre-registration is intact:
- the statistic matches R-06;
- the analytic oracle is derived correctly and validated;
- the ridge cannot see the fresh pieces;
- every primary branch can be reached.

Four amendments are required before the run:
- **A1:** one primary piece (Debussy, 2 Arabesques) is not unseen.
- **A2:** near-duplicate renditions inflate the H1b-axes oracle.
- **A3:** the top-p disclosure is incomplete.
- **A4:** the claim's scope needs two sentences.

None of them changes a threshold, the model or the primary statistic. Five further amendments are
recommended.

| # | Finding | Severity | Amendment |
|---|---|---|---|
| F1 | 3 fresh pieces contain music that was held out (2 seen paired by SyMuPe, 1 evaluated in R-07) | **High** | A1 (required) |
| F2 | 25 near-duplicate renditions (same recording or same player) in 15 of 59 primary pieces | Medium | A2 (required) |
| F3 | The primary arm was registered as top-p 1.0 first, then switched to 0.95 after both arms' R²c on 2 dev pieces had been printed. The README says the switch used no R²c | Medium (disclosure) | A3 (required) |
| F4 | "Given only the score" omits two panel-derived scalars. About half the primary pieces have a paired sibling in the same opus or collection | Low-medium (scope) | A4 (required) |
| F5 | R²c without refit mixes shape and amplitude. Dry run: r 0.56 but R²c -1.62 on one dev piece | Low | R1 (recommended) |
| F6 | Work clusters are nearly pieces. Opus and composer clustering is not in the CI | Low | R2 (recommended) |
| F7 | 5 of the 74 R10u "unseen" development pieces contain paired content | Low | R3 (recommended) |
| F8 | The development sets (ridge training) have no digest check on the box | Low | R4 (recommended) |
| F9 | `symupe_gen.py` docstring still says the primary uses top-p 1.0 | Cosmetic | R5 (recommended) |

## What was verified (no finding)

**Hash.**
- `head -n 409 README.md | shasum -a 256` gives `d679394f...5f09`.
- This equals `artifacts/prereg_sha256.txt` and `artifacts/prereg_README.md`.

**Order (author transcript `subagents/agent-a69b0bd85886c19a8.jsonl`).**
- The first README Write (16:46:59Z) already holds the primary thresholds (0.50 / 0.20) and the
  axes thresholds (0.80 / 0.40).
- The first R²c printed by any dry-run stage came after that: `dev_r07` in `artifacts/dryrun/run2.log`,
  stage start 16:50:55Z.
- The fresh pieces have never been touched by a model or the ridge:
  - `artifacts/dryrun` holds only the 2 R10u dry-run pieces;
  - the author's scratch run `r10_out` (12:05 local) built sets and trained the ridge on R10u + R10s, with
    `gen/` and `results/` empty.

**Expert-side numbers reproduce exactly.**
- I reran `summarize_h1b.py --experts-only` on the committed fresh set into scratch.
- `experts_per_piece.csv` is byte-identical to `artifacts/prereg_experts/fresh/`.
- `a_oracle_validation.csv`, `b_primary_oc.csv`, `c_axes_oc.csv` and `reachability.json` match the
  README tables and text:
  - median |empirical - analytic| is 0.0045 / 0.0090 (fresh) and 0.0032 / 0.0032 (R10u);
  - r is 0.989-0.998;
  - the OC rows and the 1.5x spread rows match;
  - the equivalent-experts scale is 0.09 / 0.24 / 0.56 / 0.80;
  - the random floor is 0.064.

**1. Analytic K-matched oracle.**
- Under exchangeable, independent performers with per-onset variance s²_j, the difference between
  a new K-expert mean and the n_j-expert panel mean has expected squared size s²_j (1/K + 1/n_j)
  at each onset. The expected SS of the centered target is the observed SS(m_c). That gives
  `1 - sum s²_j (1/16 + 1/n_j) / SS(m_c)`.
- It ignores the (1 - 1/J) centering factor and the Jensen gap of a ratio, both negligible at
  J = hundreds of onsets. The validation confirms this. `reachability.analytic_at` re-targets
  correctly: signal = SS - sum s²/n, then target n - 16.
- It estimates a slightly different quantity than DECISIONS' wording ("mean of K held-out
  experts against the rest"):
  - it is the mean of 16 new experts against the **full** panel mean;
  - the model's primary R²c is scored against that same full panel mean;
  - so this is the matched comparator, not a deviation from DECISIONS.
- The DECISIONS version (empirical, against the n - 16 rest) is also computed. It is lower
  because its reference is noisier: 15 fresh pieces, median 0.883 / 0.856 against analytic-full
  0.902 / 0.891.
- The matched empirical ratio (`r2c_vs_rest` / `oracle_emp`) is produced too. Both are fine as
  registered.
- The only violated assumption is independence: see F2. On the primary it moves the oracle by at
  most 0.001 in median.

**2. R²c formula.**
- `summarize_h1b.r2c` centers both curves over the onsets where both are finite. This is R-06
  `analyze.py` (b).
- It is applied through one loop to every arm and the ridge (`piece_rows`, `preds`).
- The empirical oracle uses the same function. The analytic oracle uses the same centered target
  and the same onset mask (>= 50% coverage).
- Velocity is centered per rendition (experts) and per sample (model). The ridge's added
  `vel_cond` constant is removed by centering.
- `r2c_r07` is kept only for continuity.

**3. Selection.**
- The majority score is taken before the cap:
  - `build_set.select_rows` keeps the majority refined score (by metadata, ties by path), then
    draws the cap;
  - `build_piece`'s second majority step is then a no-op;
  - this is the R-02 rule, it introduces no bias I can see, and it is disclosed.
- `run.sh` `check_digest` exits 3 on a mismatch inside a `set -euo pipefail` pipeline, so `.done_sets`
  is not written. The author's Mac scratch rebuild printed "MATCHES".
- PERiScoPe version: the HF model card of `SyMuPe/EncDec-base` at `1b942f28` says "Trained ... on
  PERiScoPe v1.0". R-07's v1.0 pairing basis is therefore the right one. v1.1 (January 2026)
  has 1,162 fewer pairs.
- No fresh-piece PERiScoPe performance is score-paired in v1.0: 40 of the 106 tier-C
  PERiScoPe ids of fresh pieces are in the v1.0 metadata, and 0 of them are paired.

**5. Baselines.**
- Flat = 0 is exact: a constant prediction centers to zero.
- The ridge:
  - trains only on R10u + R10s pieces with at least 6 renditions;
  - shares no work key with the fresh set (checked against R-07 `split/pieces.csv`);
  - picks alpha by GroupKFold by work inside its own data.
- The only content overlap with its training lists is the Bartók whole set (F1), which has 3
  renditions and is therefore skipped by the `>= 6` rule.

**Top-p for the primary (lead question).**
- I see no concrete reason the lead's decision is wrong:
  - the development numbers and the reachability spread are both at 0.95;
  - the 1.0 arm is generated and reported.
- One imprecision in the rationale: the mean of nucleus-truncated samples estimates neither the
  mode nor the mean of the model's predictive distribution. It trades tail bias for lower
  variance. That is an empirical trade-off, so reporting both arms is what makes it safe. The
  disclosure problem is F3.

## Findings

### F1 (High): three fresh pieces contain held-out music

Steps 2-4 of the selection match PERiScoPe pairs by performance id and by catalogue tokens. R-07's
work key gives a whole-set piece id (no movement) a different key from its movements. So a
whole-set piece passes every step even when its movements are paired.

A content check catches this. For each fresh majority score, I took every 12-onset pitch-set n-gram
(first 1,500 onsets) and looked it up against all refined scores of every PERiScoPe-paired, possibly
paired, or R-06 / R-07 evaluation piece (1,530 score files).

| Fresh piece | n (primary?) | Shared n-grams | Held piece | Why it matters |
|---|---|---|---|---|
| `pianocore:Debussy,_Claude/2_Arabesques` | 32 (primary) | 628 of 1,189 | `.../2_Arabesques/1._Andantino_con_moto_(E_major)`, **48 score-paired PERiScoPe v1.0 performances** | The score holds both Arabesques (3,256 notes). Arabesque No. 1 (1,451 notes) is about half of the 3,000-note generation item. SyMuPe saw it paired. |
| `pianocore:Ravel,_Maurice/Le_Tombeau_de_Couperin,_M.68` | 17 (generated, not analysed) | 653 of 1,011 | `.../M.68/1._Prelude` (22 pairs); the Fugue (29) follows | Whole suite. The first 3,000 notes are the Prélude and the start of the Fugue, both seen paired. |
| `pianocore:Bartók,_Béla/Romanian_Folk_Dances,_Sz.56/3._Pe_loc` | 23 (primary) | 114 of 151 | `pianocore:Bartók,_Béla/Romanian_Folk_Dances,_Sz.56` (R-07 role R10u) | The movement is contained in an R-07 evaluation piece: step 5 in substance. It is not a SyMuPe exposure, since the whole set is unpaired and its movements 1-2 are paired 2 + 2. |

- Every other fresh piece shares at most 3 n-grams with any held piece (generic patterns), so the
  separation is clean: 3 against 114 or more.
- A manual title search of all 1,182 paired v1.0 folders found no other same-piece match.
  Same-opus siblings are listed in F4.
- After A1 and A2 (expert data only, rerun here): primary **56 pieces, 54 works, 1,691 renditions**
  (median n 28).
  - Analytic oracle 0.877 [0.847, 0.901] / 0.881 [0.845, 0.905].
  - Empirical oracle (15 pieces) 0.883 / 0.856.
  - Reliability 0.958 / 0.958.
  - H1b-axes subset unchanged: 12 pieces.

### F2 (Medium): near-duplicate renditions

PianoCoRe's `is_duplicate` is False for all 1,788 primary renditions. Still, for some pairs of
renditions the per-rendition deviation from the consensus curve correlates above 0.9:
- the median over 28,194 within-piece pairs is 0.04, and the 99.9th percentile is 0.89;
- examples are the same Glenn Gould recording in ATEPP and in PERiScoPe (log IOI r 0.997), Aria
  re-uploads, and a Transkun/Aria copy whose velocity r is only 0.34 (transcriber velocity
  noise).

The rule used below is: drop the later rendition in manifest order of any within-piece pair with
deviation r > 0.9 in either target. It drops 25 renditions (list in the appendix).

Effect, expert data only:
- **Primary:** none of note. Analytic oracle median 0.878 -> 0.878, empirical unchanged.
  `bach_bwv913` falls from 20 to 17 renditions and leaves the primary set.
- **H1b-axes:** the 16-held-out-expert oracle is inflated whenever one copy is held out and the
  other stays in the reference. It falls on 3 of the 12 axes pieces:
  - `bach_bwv852_prelude` 0.389 -> 0.256;
  - `scarlatti_k213` 0.203 -> 0.150;
  - `bach_bwv912` 0.267 -> 0.220.

  The model's ratio on those pieces would be deflated by 1/0.66 to 1/0.82. Parallel-analysis k
  also moves (median 4 -> 3).
- The equivalent-experts scale on the amended set is 0.08 / 0.24 / 0.55 / 0.80 (K' = 2 / 4 / 8 /
  12). The meaning of the 0.80 / 0.40 thresholds therefore stands.

### F3 (Medium, disclosure): the top-p switch

Transcript and logs:
1. The first README (16:46:59Z) registered the primary on **K = 16, top-p 1.0**, with top-p 0.95 as
   an exploratory arm. This matched `symupe_gen.py`'s docstring, which still says so.
2. The sampling fix came at 16:51:41Z.
3. `run3` `summarize` (16:56:49Z) printed R²c for both arms on the 2 dev pieces. Final dry-run
   values, p95 vs p100:

   | Dev piece | Log IOI | Velocity |
   |---|---|---|
   | Anna Magdalena minuet | 0.295 vs 0.063 | 0.527 vs 0.690 |
   | scarlatti_k32 | -1.62 vs -2.04 | 0.568 vs 0.533 |

4. The primary was switched to 0.95 at 16:58:18Z.

The README says the switch "used the sample spread ... not any R²c" and that the summaries
"changed none" of the choices. The author's motive cannot be checked. The fact that both arms'
R²c were on screen, with p95 ahead on log IOI on both pieces, must be stated. The choice itself
is defensible and was confirmed by the lead. It used 2 development pieces, not test data, and it
did not change thresholds. A3 corrects the record and adds a both-arms headline rule, so the
switch cannot decide the outcome unseen.

### F4 (Low-medium, scope)

**Conditioning.**
- Every generation item carries the panel's median conditioning tempo (`spq_cond`) and velocity
  (`vel_cond`). This is the R-06 / R-07 rule.
- The targets are free of both:
  - log IOI ratio against each rendition's own tempo;
  - centered velocity;
  - R²c centers both curves.
- Global tempo can still shape the model's local timing. "Given only the score" (Question 1)
  should read "given the score and two global scalars from the panel". The ridge does not use
  them.

**Siblings.**
- About half of the 56 amended primary pieces (roughly 26-28 by a heuristic opus or collection
  match) have another number of the same opus or collection that SyMuPe saw paired.
  - Larger groups: WTC preludes and fugues (6); Bach toccatas, with BWV 914 paired (4);
    Visions fugitives Op. 22, with No. 10 paired (7).
  - Single pieces or pairs: Schumann Op. 68; Chopin Op. 33; Grieg Op. 54; Clementi Op. 36;
    C. P. E. Bach H. 1 (2); Anna Magdalena Notebook (2); Mozart K. 1 / K. 3 (K. 2 paired).
- This is not leakage of the piece, but it is collection-level familiarity. It should be visible
  in the results as an exploratory split.

### F5 (Low): amplitude versus shape

For centered curves, R²c = 2 r b - b², where b = sd(pred) / sd(target):
- it equals r² only at b = r;
- in the dry run, log IOI on scarlatti_k32 had r 0.56 and R²c -1.62, so b is far above r
  (the model over-expresses timing);
- a "falsified" log IOI reading could therefore be an amplitude-calibration failure with usable
  shape.

The registered reading is correct as defined ("explains variance", no refit). The decomposition
is needed to interpret it.

Transcriber scale is not the cause, measured on expert data. Within pieces, per-rendition velocity
s.d. relative to Aria-AMT is:

| Source | Fresh | R10u |
|---|---|---|
| Transkun V2 | 0.95 | 1.03 |
| ATEPP | 0.91 | 1.02 |
| ByteDance | 1.04 | 0.91 |

### F6 (Low): bootstrap unit

- Work clusters: 57 works for 59 pieces (54 for 56 after A1 and A2). In practice this is a piece
  bootstrap. That is the right unit under the hard rules.
- Model errors may still cluster by collection: 7 Op. 22 pieces and 13 J. S. Bach pieces.
- The per-composer and leave-one-composer-out medians are registered. A composer-cluster CI
  (25 composers) next to them would show whether the CI is optimistic.

### F7 (Low): development numbers

The content check on R-07's 74 "unseen" R10u pieces flags 5 that contain PERiScoPe-paired music:
- `bach_bwv856`, `bach_bwv857` and `bach_bwv862`: whole prelude + fugue, with the movements paired;
- `mozart_k545`: mv1 paired;
- `clementi_op36_no1`: its first movement is paired once, under a PianoCoRe piece mislabelled
  "1. Spiritoso".

Without these 5 pieces, the frozen medians move from 0.328 to 0.330 (velocity) and from 0.127 to
0.142 (log IOI, R-07 formula), on 69 pieces. The effect is negligible, but "unseen" in the
Baselines bullet is not exact.

### F8 (Low): no digest check on the development sets

The ridge's training sets are rebuilt on the box without a digest check. The Mac reference is the
author's scratch run: 138 pieces, 97 works, alpha velocity 1000 / log IOI 1, GroupKFold r 0.516 /
0.167. A different box rebuild would change only the baseline, but it should be detectable.

### F9 (Cosmetic)

`job/symupe_gen.py` line 3-4: "R-10's primary samples use top-p 1.0" is stale.

## Answers to the lead's questions

1. **The oracle** is correct (see above) and is the matched comparator for the model's primary
   R²c. DECISIONS' "against the rest" version is also reported. Validation reproduces.
2. **R²c** is identical to R-06 and is applied identically to model, ridge and oracle.
3. **Leakage:**
   - PERiScoPe pairing (v1.0 is the right version), aliases and work-mates are clean, except F1;
   - R-06 / R-07 evaluation sets: clean except Bartók (F1);
   - R-02: excluded by flag;
   - the majority-before-cap change is fine;
   - the digest check stops the job on a mismatch.
4. **Thresholds and reachability:**
   - Primary: every branch is reachable, and the numbers reproduce. At the R10u development level
     the velocity reading will most likely be inconclusive (about 0.96), and the README says so.
   - The work-cluster bootstrap is right (add R2).
   - H1b-axes with 12 pieces separates only the extremes: "at or near the floor" from "about as
     good as 12-16 experts". At a true ratio of 0.5-0.7 the reading is inconclusive with
     probability 0.74-0.94, and the CI half-width is 0.19-0.26 (`c_axes_oc.csv`, realistic
     spread).
   - That is acceptable for a non-deciding secondary once A2 removes the duplicate inflation.
     Report the 12 per-piece ratios with the median.
   - The 0.80 / 0.40 thresholds put the known development value (0.52) in the inconclusive
     band. They favour neither side.
5. **Baselines and ceiling** are fine (see above).
6. **Provenance (92% Aria-AMT).**
   - The README's threats section and the per-source tables are adequate.
   - The verdict sentence must carry the scope:
     - Aria-AMT transcriptions of YouTube recordings;
     - less-played repertoire;
     - the conditioning and the siblings (A4).
   - The transcriber velocity scale is not a confound (F5).
7. **Anything else:** F5 (amplitude) is the main remaining way a reading could be misread.
   Hence R1.

## Required amendments (append verbatim below `## Run record`; do not edit the hashed header)

Record the sha256 of the appended amendment block in `artifacts/prereg_amendment_sha256.txt`
before the box run (`sed -n '<first>,<last>p' README.md | shasum -a 256`).

```
## Pre-run amendments (2026-10-05, after the eval-auditor pre-run review, PRERUN_REVIEW.md)

Written before any model or baseline output on the fresh pieces existed. No threshold, model,
statistic or arm assignment changes.

A1. Content overlap (review F1). Steps 2-4 match PERiScoPe pairs by performance id and catalogue
tokens; R-07's work key separates a whole-set piece id from its movements, so a whole-set piece
passes even when its movements are paired. Added step 6: no fresh piece may share 10 or more
12-onset pitch-set n-grams (first 1,500 onsets of its majority refined score) with any refined
score of a PERiScoPe-paired, possibly paired, or R-06 / R-07 evaluation piece. It drops 3 pieces
(every other fresh piece shares at most 3), listed in pieces/excluded_content_overlap.csv:
- pianocore:Debussy,_Claude/2_Arabesques (contains Arabesque No. 1, 48 score-paired PERiScoPe
  v1.0 performances; was primary);
- pianocore:Ravel,_Maurice/Le_Tombeau_de_Couperin,_M.68 (whole suite; Prelude and Fugue paired
  22 and 29 times; was not primary);
- pianocore:Bartók,_Béla/Romanian_Folk_Dances,_Sz.56/3._Pe_loc (contained in the R-07 R10u piece
  pianocore:Bartók,_Béla/Romanian_Folk_Dances,_Sz.56; was primary).
They are excluded from every statistic. Their generation items may still be produced (the set
digest is unchanged); their outputs are not read.

A2. Near-duplicate renditions (review F2). Within a piece, two renditions whose deviations from
the expert mean curve (columns mean-filled, rows demeaned) correlate above 0.9 in log IOI or in
centered velocity are treated as one performance; the later one in manifest order is dropped.
This removes 25 renditions in 15 primary pieces (pieces/duplicate_renditions.csv, by
performance_id) and applies to every statistic (expert curves, oracles, k, captured shares,
conditional prediction, per-source tables). bach_bwv913 drops to 17
renditions and leaves the primary set.
Primary set after A1 and A2: 56 pieces, 54 works, 1,691 renditions (median 28). Expert-side
values (measured before any model output): analytic oracle velocity 0.877 [0.847, 0.901], log IOI
0.881 [0.845, 0.905]; empirical oracle (15 pieces) 0.883 / 0.856; reliability 0.958 / 0.958;
H1b-axes subset 12 pieces, 16-expert captured share 0.189; equivalent-experts scale 0.08 / 0.24 /
0.55 / 0.80 (K' = 2 / 4 / 8 / 12), so the 0.80 / 0.40 thresholds keep their meaning.
The as-registered set (59 pieces, no exclusions) is summarised as well, as a sensitivity
analysis (results/fresh_as_registered).

A3. Top-p record (review F3). Correction to "What had been seen" and to the dry-run disclosure:
the first draft of this README (16:46:59Z) registered the primary on top-p 1.0 samples, with top-p
0.95 exploratory. After the sampling fix, the dry-run summary (16:56:49Z) printed R²c for both
arms on the 2 development pieces (log IOI p95 vs p100: 0.295 vs 0.063 and -1.62 vs -2.04;
velocity 0.527 vs 0.690 and 0.568 vs 0.533), and the primary was then switched to top-p 0.95
(16:58:18Z). The stated reasons (development numbers and the reachability simulation are at
0.95) stand, and the lead confirmed the assignment (DECISIONS 2026-10-05), but the R²c were
visible when the switch was made. Added reporting rule: the headline gives the registered reading
(frozen_p95); if the frozen_p100 reading differs for either target, the same sentence states it.

A4. Scope (review F4). "Given only the score" means the score plus two global scalars from the
panel: the median conditioning tempo and velocity of the piece's renditions (R-06 / R-07 rule);
the targets do not contain them, the ridge does not use them. "Unseen" means: no score-paired
performance in PERiScoPe v1.0 (the EncDec-base model card states training on v1.0), checked by
performance id, catalogue alias, title search and score content (A1). About half of the primary
pieces have another number of the same opus or collection that is paired (WTC, Bach toccatas,
Visions fugitives Op. 22, Schumann Op. 68, Chopin Op. 33, Grieg Op. 54, Clementi Op. 36,
C. P. E. Bach H. 1, the Anna Magdalena Notebook, Mozart K. 2). Exploratory table: the primary
statistic split by a sibling flag (another piece with the same opus number, or the same PianoCoRe
collection title, is PERiScoPe-paired or possibly paired), the flag committed as
pieces/sibling_flag.csv before the run. The verdict sentence names the scope: frozen SyMuPe
EncDec-base, less-played repertoire, consensus of mostly Aria-AMT transcriptions of YouTube
recordings, conditioned on the panel's median tempo and loudness.
```

How to implement A1-A2 without touching the set digest:
- commit the two CSV lists, plus `pieces/sibling_flag.csv`;
- give `summarize_h1b.py` `--exclude-pieces CSV` and `--exclude-renditions CSV`, which filter
  the manifest after reading;
- have `run.sh` `summarize` call it twice: amended set to `results/fresh`, and no exclusions to
  `results/fresh_as_registered`;
- check on the Mac that `--experts-only` with the exclusions reproduces the A2 numbers above.

The duplicate rule script is in the appendix. My scratch copy of the list matches the appendix
table.

## Recommended amendments (not deciding; add to the same block if accepted)

```
R1. Amplitude decomposition (review F5): per piece, arm and target, also report r², the amplitude
ratio b = sd(pc) / sd(mc) and the identity R²c = 2 r b - b²; the same for the empirical K-matched
oracle (16 held-out experts). Medians with work-cluster CIs. Descriptive only.
R2. Composer-cluster bootstrap CI (25 composers) for the primary medians, next to the
work-cluster CI. Descriptive only.
R3. Development numbers (review F7): the R10u "unseen" development medians are also given without
the 5 pieces whose scores contain PERiScoPe-paired music (bach_bwv856, bach_bwv857, bach_bwv862,
mozart_k545, clementi_op36_no1): frozen, R-07 formula, 0.330 / 0.142 on 69 pieces (0.328 / 0.127
on 74).
R4. Development sets: run.sh compares the r10u_dev and r10s_dev digests with the Mac's
(artifacts/sets/r10u_dev/digest.json; r10s from a Mac build) and logs a mismatch (not fatal);
ridge.json is compared with the Mac reference (138 pieces, 97 works, alpha 1000 / 1, CV r 0.516 /
0.167).
R5. symupe_gen.py docstring: the primary arm is top-p 0.95, the axes arm top-p 1.0.
```

## What I could not verify

- The box rebuild and its digest (Windows). I saw only the Mac scratch rebuild match.
- GPU sampling and the `top_p` start-up guard on the box. I did not run generation.
- Pianist Transformer (`pt_gen.py`). It is secondary and non-deciding, and I did not review it.
- PERiScoPe paired folders that are not in PianoCoRe. They can only be checked by title or alias
  (done), not by content. The v1.0 "some performances correspond to incorrect compositions"
  issue is covered only to that extent.
- Whether SyMuPe also trained on unpaired PERiScoPe performances. The model card says "trained on
  PERiScoPe v1.0" without detail, and the README's threats bullet already covers it.

## Appendix: reproduction recipes (Mac, project env, expert data only)

Duplicate rule (writes the 25-row list; about 1 minute):
```python
import sys, numpy as np, pandas as pd
sys.path.insert(0, "experiments/2026-10-05-R-10-h1b/job")
import summarize_h1b as sh
from pathlib import Path
d = Path("experiments/2026-10-05-R-10-h1b/artifacts/sets/fresh")
man = pd.read_csv(d / "manifest.csv"); man = man[man.kind == "real"]
cache, rows = {}, []
for piece, g in man.groupby("passage"):
    gi = sh.load_item(d / "gen_items" / (sh._slug(piece) + ".npz"))
    idx = pd.Index(np.unique(np.round(gi["score_onset_q"], 6)))
    V, T = sh.expert_matrix(d, g.stem.tolist(), idx, cache)
    keep = (np.isfinite(V).mean(0) >= .5) & (np.isfinite(T).mean(0) >= .5)
    V, T = V[:, keep], T[:, keep]
    def nz(X):
        X = sh._fill(X); X = X - X.mean(0); X = X - X.mean(1, keepdims=True)
        return X / np.linalg.norm(X, axis=1, keepdims=True)
    C = np.maximum(nz(T) @ nz(T).T, nz(sh.center_rows(V)) @ nz(sh.center_rows(V)).T)
    pid, gone = g.performance_id.tolist(), set()
    for i in range(len(pid)):
        if i in gone: continue
        for j in range(i + 1, len(pid)):
            if j not in gone and C[i, j] > 0.9:
                gone.add(j); rows.append((piece, pid[j], pid[i], C[i, j]))
pd.DataFrame(rows, columns=["piece_id", "dropped_performance_id", "kept_performance_id", "r_max"]
             ).to_csv("duplicate_renditions.csv", index=False)
```

Content check:
- From `PianoCoRe-1.0-refined.zip`, read each refined score MIDI with mido, merge the tracks, group
  note-ons by absolute tick into sorted pitch tuples, and form 12-onset n-grams.
- Index every n-gram of every refined score of the held pieces. Held means R-07
  `split/pieces.csv` rows with `n_periscope_paired > 0`, or `periscope_possible`, or role in P /
  V / A / R10u / R10s: 1,530 files.
- Count the hits of each fresh majority score's n-grams (first 1,500 onsets).

| Piece | Dropped rendition | Kept | r log IOI | r velocity |
|---|---|---|---|---|
| bach_bwv852_prelude | PERiScoPe_106708186 (Transkun V2) | ATEPP_02682 (ATEPP) | 0.997 | 0.859 |
| bach_bwv859_fugue | PERiScoPe_106706138 (Transkun V2) | ATEPP_02552 (ATEPP) | 0.997 | 0.843 |
| bach_bwv859_fugue | Aria_346318_0 | Aria_191119_0 | 0.754 | 0.934 |
| bach_bwv910 | Aria_792976_0 | Aria_256978_0 | 0.937 | 0.850 |
| bach_bwv910 | Aria_800723_0 | Aria_256978_0 | 0.960 | 0.945 |
| bach_bwv912 | ATEPP_10605 | ATEPP_10604 | 0.945 | 0.937 |
| bach_bwv912 | Aria_664690_0 | Aria_566240_0 | 0.888 | 0.963 |
| bach_bwv912 | PERiScoPe_6290537 (Transkun V2) | Aria_749862_0 | 0.968 | 0.930 |
| bach_bwv913 | ATEPP_10582 | ATEPP_10581 | 0.974 | 0.734 |
| bach_bwv913 | Aria_171424_0 | ATEPP_10581 | 0.981 | 0.737 |
| bach_bwv913 | ATEPP_10584 | ATEPP_10583 | 0.971 | 0.942 |
| bach_bwv916 | Aria_856824_0 | Aria_049628_0 | 0.912 | 0.932 |
| Field Nocturne No. 1, H 24 | Aria_251164_0 | Aria_043770_0 | 0.964 | 0.821 |
| Gossec Gavotte in D | Aria_353121_0 | Aria_008245_0 | 0.944 | 0.766 |
| Gossec Gavotte in D | Aria_054528_0 | Aria_015681_0 | 0.933 | 0.799 |
| Gossec Gavotte in D | Aria_708706_0 | Aria_364094_0 | 0.966 | 0.822 |
| Rameau Tambourin, RCT 2/8 | Aria_667346_0 | Aria_073409_0 | 0.900 | 0.818 |
| prokofiev_op22_no17 | PERiScoPe_1087828732 | PERiScoPe_74114423 | 0.983 | 0.971 |
| scarlatti_k213 | Aria_231628_0_mini | Aria_139711_0_mini | 0.984 | 0.979 |
| scarlatti_k322 | Aria_383478_0 | ATEPP_10841 | 0.908 | 0.866 |
| scarlatti_k322 | Aria_404772_0 | Aria_375510_0 | 0.914 | 0.950 |
| scarlatti_k322 | Aria_599940_0 | Aria_375510_0 | 0.909 | 0.967 |
| scarlatti_k54 | Aria_850070_0 | Aria_405874_3 | 0.912 | 0.967 |
| schumann_op68_no14 | PERiScoPe_2115286947_mini (Transkun V2) | Aria_157490_0_mini | 0.968 | 0.342 |
| turina_op55_no5 | Aria_839769_0 | Aria_736150_0 | 0.901 | 0.918 |
