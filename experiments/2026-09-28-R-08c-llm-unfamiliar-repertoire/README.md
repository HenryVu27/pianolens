# R-08c: does the LLM phrase annotator work on repertoire it does not know? (J. C. Bach sonatas)
Ticket: R-08c    Hypothesis: gate for R-08 beyond famous Classical sonatas (Phase 7; feeds H4 / R-09 phrase boundaries)    Status: Provisional (pre-registered 2026-09-28; no annotation exists yet)

Prepared by `ml-researcher`. The annotators are separate, blind agents run by the lead. Nothing
in this header may be edited after any annotation is produced. Corrections go in new sections at
the end.

## Question

R-08a and R-08b found that an in-session Claude annotator marks DCML phrase ends on 5 famous
Mozart sonata movements at mean end F1 about 0.80 (±1 beat), against 0.565 for the F-05c cadence
detector, and that a disguise that stops it naming the piece does not lower the score (both
Confirmed with caveats). A disguise hides the surface, not the structure, so it cannot rule out
familiarity with these particular pieces (R-08b audit, section 4). This experiment asks:

**On DCML-labelled keyboard movements the model is unlikely to know (J. C. Bach, op. 5 and
op. 17), does the annotator reach the 0.70 go bar, and does it beat the F-05c detector on the
same movements?**

Secondary: how much does F1 move between two independent runs on the same movement?

## Go bar and falsification

- **Per-movement score:** phrase-end F1 at ±1 beat (R-08a's primary metric: the F-05c
  convention, one beat = the time signature's denominator; one-to-one matching, closest pairs
  first), averaged over the two runs R1 and R2 of that movement.
- **Primary:** the mean of the per-movement scores over the 5 movements.
- **GO:** primary ≥ 0.70 (point estimate, as in R-08a and R-08b).
- **NO-GO:** primary < 0.70. This includes the case where the annotator beats the detector but
  stays below 0.70.
- **Beats the detector** (reported, not the go bar): mean paired per-movement difference
  (LLM − detector) > 0 **and** its t-interval (4 df) excludes 0 → "shown"; otherwise "not
  shown". The percentile bootstrap (10,000 resamples over movements, seed 20260930) is reported
  next to it. The t-interval decides, because with 5 groups the bootstrap is optimistic (R-08a
  audit lesson).
- **Intervals.** For the primary and every paired difference: the t-interval (4 df) and the
  percentile bootstrap. "The interval lies above 0.70" is claimed only if the t-interval's lower
  end is above 0.70.
- The 0.70 bar comes from `DECISIONS.md` (2026-09-27 after F-05b; restated 2026-09-28 after
  D-12). It is copied, not changed.
- **Consequence (DECISIONS 2026-09-28, R-08b confirmed):** before LLM phrase boundaries are used
  on repertoire other than the validated Classical sonatas, or described as a general phrase
  annotator, this test is required. What follows a GO or a NO-GO is the lead's decision.

### Can each branch be reached? (R-09 audit lesson)

- On R-08a, the per-movement LLM F1 had SD about 0.10 over movements. R-08b measured a
  within-movement run-to-run SD of 0.031. With 5 movements, the expected t half-width of the
  primary is about 2.78 × 0.10 / √5 ≈ 0.12. So both GO and NO-GO are reachable. "The interval lies
  above 0.70" needs a primary of about 0.82 or more, and is not expected.
- The detector's mean end F1 over all 29 J. C. Bach movements is 0.427 (D-12). R-08a's paired
  differences had SD about 0.16, so a t half-width of about 0.20. "Beats the detector shown" is
  therefore expected if the annotator is near the go bar (difference about 0.27), and not
  expected if it is near 0.55.

## Recognition (within-movement analysis only)

Each annotation has `recognised_piece`. The lead or the auditor classifies each of the 10
strings, by reading the string only, as:

- **correct:** names J. C. Bach and the right sonata (op. and number); the movement may be
  approximate;
- **composer:** names J. C. Bach ("J. C. Bach", "Johann Christian Bach", "the London Bach"),
  but no work or the wrong work;
- **wrong:** names another composer or work (for example Mozart, Haydn, or "Bach" without
  a first name that says J. C.);
- **none:** null, or no named composer or work.

The hand-back text of each annotator is also read, and any guess there that the string lacks is
recorded as "borderline" next to `recognition.json` (R-08b lesson: self-report is a lower
bound). It does not change the class.

Analysis rules, fixed now:

- **Never pooled across movements.** Recognition is not randomised and tracks the movement
  (R-08b audit). The only recognition contrast reported is within a movement: when R1 and R2 of
  the same movement fall in different classes, both F1 values are shown side by side.
- **Premise check.** "Unfamiliar" holds for a movement if both of its runs are `none` or
  `wrong`. If any movement is `correct` or `composer` in either run, the primary is also
  reported without those movements (sensitivity). If 3 or more of the 5 movements are `correct`
  or `composer` in at least one run, the verdict reads "unfamiliarity not achieved": GO / NO-GO
  is still computed and reported, but it does not count as the unfamiliar-repertoire test.

## Data

- DCML `jc_bach_sonatas` v2.4, commit `ac9fd07` (`DATASETS.md`; CC BY-NC-SA 4.0), under
  `data/raw/dcml_jc_bach/`. Loader `pianolens.data.dcml_jc_bach` (D-12):
  - scores: `load_score(stem, unfold=True, tempo_word=False)`, built only from the label-free
    `notes`, `measures` and `chords` TSVs (never `harmonies/`, `MS3/*.mscx` or `reviewed/`,
    which carry the labels);
  - ground truth: `phrase_annotations(score)`: phrase ends (`}`, `}{`) and starts (`{`, `}{`),
    cadences PAC, IAC, HC, EC, DC and PC, mapped onto every pass of each bar of the unfolded
    score. The 3 `\\` labels of the corpus are dropped.
- Detector inputs: D-12's cache `data/interim/dcml_jc_bach/cands.pkl` (F-05c layout) and
  `comparators.csv`. The F-05c detector was fitted on Batik K.279-K.283, so every J. C. Bach
  movement is held out for it.
- **Eligible movements.** All 29 movements except op. 5 nos. 2-4 (`wa02*`, `wa03*`, `wa04*`: 9
  movements). Mozart arranged those three sonatas as the K.107 concertos, which adds a
  familiarity route (DECISIONS 2026-09-28 after D-12, item 1). 21 movements remain. No other
  exclusion.

## Movement selection (fixed before any annotation exists)

1. **Size.** Each eligible movement is rendered with R-08a's renderer on the
   `tempo_word=False` score, with the placeholder id `X`. Its size is the number of characters of
   that rendering.
2. **Strata.** The 21 movements are sorted by size (ties by stem) and cut into 5 contiguous
   strata with `numpy.array_split` (sizes 5, 4, 4, 4, 4); S1 is the smallest. Rendered size is
   used instead of bar count so that the middle stratum has candidates (DECISIONS after D-12,
   item 2).
3. **Draw.** One movement per stratum. `numpy.random.default_rng(20260930)`, strata in the order
   S1..S5, each stratum's members sorted by stem, `rng.choice(len(stratum))`. Ids `Q1`..`Q5` in
   stratum order. Code: `draw.py` (writes `artifacts/selection.json`). The result is appended
   below under "Selection outcome", unchanged by anything that follows.

Two movements of the same sonata may be drawn; each annotator sees only one movement, so this is
allowed.

## Rendering (the annotator's only input)

`build.py` renders each drawn movement with R-08a's `common.render` (imported, not copied or
changed) to `blind_input/Q#.txt`. Layout, beat labels, pointer bars ("same notes and markings as
bar k") and the bar table are exactly R-08a's. Differences from the Batik renderings, all
disclosed here before the draw (DECISIONS after D-12, items 3 and 4):

- **No fermatas.** The TSV facets do not carry them (15 in the `.mscx` files, in 8 movements).
  The legend still explains `FERMATA`; none will appear.
- **Rests are derived** (gaps in each staff's notes, split at bar lines), not engraved rests.
- **No hairpins** (the few crescendo lines are not read). Dynamics (`f`, `p`) and staff texts
  from the `chords` facet are kept, as printed words. Before the draw, the staff texts of the 21
  eligible movements were listed: "Var. 1".."Var. 5", "Min. D.C.", "Segue", "Siegue subito", a
  page-turn note ("Volti fubito"), "Arpeggio", "..." and one heading of the following movement
  ("2. Allegro Moderato", at the end of op. 5 no. 6 i). They are kept as printed; none names a
  composer or catalogue number.
- **No movement-title tempo word** (`tempo_word=False`), as in the R-08b disguise. R-08a kept its
  tempo words.
- No key mode (the renderer prints only the key signature, as in R-08a).
- Slurs, beams and clefs are not rendered (as in R-08a).
- Meters include 3/8 and 12/8, where one beat is an eighth note, so ±1 beat is narrow there (the
  F-05c convention). A ±1 quarter-note sensitivity is reported.

### Leakage and identity check (`build.py --check`; must pass before any annotator runs)

For every `Q#.txt`, and for `INSTRUCTIONS.md` and `SCHEMA.json`:

- R-08a's banned annotation vocabulary (`BANNED_WORDS`) and Roman-numeral tokens (`ROMAN`),
  imported from R-08a's `render.py`;
- the movement's DCML label strings (`dcml_jc_bach.label_strings`, length ≥ 3, not purely
  numeric; for `INSTRUCTIONS.md` and `SCHEMA.json`, length ≥ 4 over all 5 movements, because the
  cadence names are part of the task);
- identity: composer names (Bach, Christian, Johann, London, Mozart, Haydn and R-08b's list),
  catalogue patterns (op., K., KV, Wq, Hob., Warb), the file-stem patterns (`wa01`..`wa12`,
  `op05`, `op17`), "sonata" and "sonatina", the movement's own metadata title (for example
  "Allegro Assai"), and provenance words (DCML, jc_bach, pianolens, `/Users/`, `experiments/`);
- no stray ids of earlier runs (`M1`..`M5`, `D1`..`D5`).

The check must be shown to fire on planted cues (a label string, `V7`, `PAC`, `Bach`, `op. 5`,
`wa05`, the movement title).

## Instructions and schema

`INSTRUCTIONS.md` and `SCHEMA.json` are R-08a's, with only the ids changed (`M` → `Q` in file
names, ids and the schema pattern). **The period wording stays "piano movements from the
Classical period".** Decision and reason: J. C. Bach's op. 5 (published 1766) and op. 17 (about
1779) are galant / early Classical keyboard sonatas, printed "for the harpsichord or piano
forte", so the sentence is accurate. Keeping it word for word means that any difference from
R-08a / R-08b cannot come from the instructions. "18th-century keyboard" would add a harpsichord
or Baroque cue that could shift the annotator's stylistic expectations, for no gain in accuracy.

- The schema keeps R-08a's cadence types (PAC, IAC, HC, EC, DC, none). Plagal cadences (PC; 9 in
  the unfolded corpus) cannot be typed by the annotator; their recall via phrase ends is still
  reported.
- **Worked example.** R-08a's example uses bar 3 beat 2 (start) and bar 6 beat 2 (end and
  start). If either position lies within 1 beat of a DCML phrase end or start in any drawn
  movement, both bar numbers are moved up together (4 and 7, then 5 and 8, ...) to the first
  pair that is clear in all 5, and the change is recorded in the preparation record. Nothing
  else in the instructions changes.

## Conditions and blinding (R-08a / R-08b protocol and audit lessons)

- **Two runs**, R1 and R2. Each run has one fresh annotator per movement: 10 annotators in all.
  Same model and agent type as R-08a / R-08b (in-session `claude-opus-5-5`, general-purpose,
  background). The lead records model, agent ids and times.
- The lead copies `blind_input/` to two folders **outside the repo** (one per run) and gives each
  annotator only that path, its one file `Q#.txt`, and where to write `out/Q#.json`. The prompt
  template is R-08b's. It does not say composer, corpus, period beyond the instructions, or that
  the music is unfamiliar.
- An annotator may read only `INSTRUCTIONS.md`, `SCHEMA.json` and its own `Q#.txt`. No web search,
  no other files. One pass, no feedback. A technical failure (malformed JSON, truncation) may be
  rerun once, before scoring, and is disclosed. If a run is still missing, that movement's score
  uses the run that exists, and this is disclosed.
- **Each JSON is copied verbatim into this folder at once** (`annotations_R1/Q#.json`,
  `annotations_R2/Q#.json`), before scoring. Transcripts are kept for the auditor's file-access
  check.

## Metrics (`score.py`)

R-08a's scoring functions are loaded from R-08a's `score.py` (importlib, not copied or
changed): `map_events` (snap to the nearest onset within ±0.5 beat; events in a printed bar are
copied to the pointer bars that repeat it), `score_movement`, `boundary_prf` (from
`scripts/check_phrase_f05b.py`), `summarise`. The cadence-type list is extended with PC so that
PC recall is counted. Per run and movement:

- **Primary input:** phrase-end P / R / F1 at ±1 beat.
- End F1 at ±1 bar; start F1 at ±1 beat and ±1 bar; DCML cadence F1.
- Cadence recall by type at ±1 beat via phrase ends (the detector comparison), and via all
  cadence marks (LLM only); cadence-type agreement.
- Confidence ≥ 0.5 variant (descriptive).
- Sensitivities: exact-onset end F1 (±0); end F1 at ±1 quarter note in every meter; end F1
  counting each repeated passage once (pointer bars dropped from prediction and truth, the fair
  check from the R-08a audit).

Aggregation and reporting:

- The go rule, the paired LLM − detector test and both intervals, as above.
- **Run-to-run:** per movement R1, R2, |R1 − R2| and SD; mean within-movement SD (next to
  R-08b's 0.031); the run-level means of R1 and R2.
- **HC recall** via phrase ends at ±1 beat, pooled over movements, per run, against the
  detector's pooled HC recall and the DCML-ends reference (not a ceiling; R-08a audit).
- Per-movement table: LLM R1, R2, mean; detector; proxy; grid4.
- Descriptive only: this primary next to R-08b's disguised 0.802 and undisguised 0.789. No test
  across corpora.

## Comparators (same 5 movements, computed before any annotation)

- `cadence`: the F-05c detector (`pianolens.features.cadence.cadence_phrase_ends`, shipped
  defaults), ends and starts, computed on the `tempo_word=False` score.
- `proxy_last_onset` (ends), `proxy` (starts), `grid4` (every 4th downbeat), and
  `oracle_dcml_ends`: taken from D-12's `comparators.csv`.

## Harness checks (`score.py --harness`; must pass before any annotator runs)

1. **True labels give F1 1.0.** The DCML ends and starts, written as (bar, beat) events through
   the bar table and scored through the annotator path (propagation off): end and start F1 =
   1.000 at ±1 beat, every movement. Also reported: the same events written only in printed bars,
   then propagated (1.000 expected if the labels are identical in both passes of every repeated
   bar; a lower value is recorded, not a failure).
2. **Detector reproduces D-12.** The detector's ends and starts, written as (bar, beat) events
   and scored through the annotator path with propagation off, equal D-12's `cadence` rows in
   `data/interim/dcml_jc_bach/comparators.csv` (tp, n_pred, n_true and F1, for every target and
   tolerance, and every per-type row), for all 5 movements. Also reported with propagation on.
3. The detector's ends are identical on the `tempo_word=True` and `tempo_word=False` scores, and
   the ground truth equals the D-12 cache.
4. **End-to-end dry run** (scratch folder, nothing written to `artifacts/`): the oracle written
   as an annotation JSON gives primary 1.000; the detector written as an annotation JSON gives
   the detector's mean **with propagation on** (the annotation path copies printed-bar events
   into pointer bars; where the detector makes different calls in the two passes of a repeat,
   this differs from its own score). The comparator for the go rule and the paired test stays the
   detector's own score on every performed bar, as in R-08a.

## Method

1. `draw.py` → `artifacts/selection.json` (sizes, strata, picks).
2. `build.py` → `blind_input/Q#.txt`, `INSTRUCTIONS.md`, `SCHEMA.json`, `artifacts/bars_Q#.csv`,
   `artifacts/ground_truth/Q#.json`, `artifacts/render_sizes.csv`; then `build.py --check`.
3. `score.py --comparators` → `artifacts/comparators.csv`, `artifacts/comparators_summary.txt`;
   `score.py --harness` → `artifacts/harness.txt`.
4. (Lead) run the 10 blind annotators; save the JSON files as above.
5. `score.py --llm-dir annotations_R1 --run R1`, `score.py --llm-dir annotations_R2 --run R2`.
6. (Lead or auditor) fill `recognition.json`; `score.py --compare` →
   `artifacts/r08c_summary.txt`. Results are appended to this README.

## Command

```
uv run python experiments/2026-09-28-R-08c-llm-unfamiliar-repertoire/draw.py
uv run python experiments/2026-09-28-R-08c-llm-unfamiliar-repertoire/build.py
uv run python experiments/2026-09-28-R-08c-llm-unfamiliar-repertoire/build.py --check
uv run python experiments/2026-09-28-R-08c-llm-unfamiliar-repertoire/score.py --comparators
uv run python experiments/2026-09-28-R-08c-llm-unfamiliar-repertoire/score.py --harness
uv run python experiments/2026-09-28-R-08c-llm-unfamiliar-repertoire/score.py --llm-dir experiments/2026-09-28-R-08c-llm-unfamiliar-repertoire/annotations_R1 --run R1
uv run python experiments/2026-09-28-R-08c-llm-unfamiliar-repertoire/score.py --llm-dir experiments/2026-09-28-R-08c-llm-unfamiliar-repertoire/annotations_R2 --run R2
uv run python experiments/2026-09-28-R-08c-llm-unfamiliar-repertoire/score.py --compare
```

Seeds: draw 20260930, bootstrap 20260930. Code state: uncommitted (the repo has no commits);
sha256 of the scripts and blind inputs go in the preparation record.

## Threats to validity (known before running)

- n = 5 movements, one composer, one annotation standard. The DCML J. C. Bach labels were made by
  different annotators (op. 5: A. Nagel with E. Mohagheghi Fard, D. Krkljus or H. Becker; op. 17:
  A. Brey or D. Krkljus) than the Mozart labels. Their conventions for phrase level may differ,
  so a lower score may reflect the standard as much as the annotator.
- **Unfamiliarity is assumed, not proven.** Self-reported recognition is a lower bound, and the
  model may know these sonatas without naming them. Galant cadence and phrase schemata are
  generic to the style; knowing them is the skill being tested, not a leak.
- The renderings carry less than Batik's (no fermatas, no tempo word, derived rests, few dynamics),
  which makes the task harder, so a NO-GO may partly reflect the input.
- ±1 beat is an eighth note in 3/8 and 12/8.
- The detector's J. C. Bach mean (0.427) is lower than on the R-08a pilot (0.565); the gap to beat
  is larger, and the go bar is unchanged.
- Two runs per movement estimate run-to-run variance only roughly.

## Selection outcome (draw.py, seed 20260930, run 2026-09-28 before any rendering of blind inputs or annotation)

| Id | Movement (stem) | Work | Stratum (rendered size) | Time signature | Characters (id `X`) |
|---|---|---|---|---|---|
| Q1 | wa06op05no6a_Grave | op. 5 no. 6, i | S1 (20,815-30,393) | 3/4 | 30,393 |
| Q2 | wa06op05no6b_Allegro_Moderato | op. 5 no. 6, ii | S2 (30,586-34,230) | 4/4 | 34,230 |
| Q3 | wa07op17no1a_Minuetto_Con_Variatione | op. 17 no. 1, i | S3 (35,593-41,556) | 3/4 | 41,231 |
| Q4 | wa10op17no4a_Allegro | op. 17 no. 4, i | S4 (45,567-55,930) | 4/4 | 47,409 |
| Q5 | wa12op17no6a_Allegro | op. 17 no. 6, i | S5 (57,876-64,973) | 4/4 | 64,973 |

Strata members are in `artifacts/selection.json`. Q1 and Q2 are two movements of the same
sonata (allowed above). Q1 is the movement whose last bar carries the printed heading of the next
movement ("2. Allegro Moderato"); it is kept as printed (see "Rendering"). No 3/8 or 12/8
movement was drawn.

## Preparation record (2026-09-28, ml-researcher; no annotation exists yet)

Everything above this section is the pre-registration. Its sha256 (the file up to, not
including, the line `## Preparation record`) is given at the end of this section.

### Edits to the header before hashing (disclosed)

- The "Selection outcome" table was appended after `draw.py` ran, as in R-08a.
- Harness check 4 first said the detector written as an annotation "gives the detector's mean".
  The dry run showed that this holds only with propagation off: on Q4 and Q5 the detector makes
  different calls in the two passes of some repeated bars, so the annotation path (which copies
  printed-bar events into pointer bars) scores it 0.560 instead of 0.541 (Q4) and 0.522 instead of
  0.527 (Q5). The wording of check 4 was corrected to "with propagation on" before the hash was
  taken and before any annotator existed. No rule, metric or comparator changed: the comparator
  is still the detector's own score on every performed bar (mean 0.437).

### Renderings (`blind_input/`)

| Id | Time | Performed bars | Pointer bars | Characters | Words | Tokens (rough, chars / 3) | DCML ends | Cadences |
|---|---|---|---|---|---|---|---|---|
| Q1 | 3/4 | 62 | 0 | 30,395 | 7,070 | ~10k | 13 | 14 |
| Q2 | 4/4 | 77 | 0 | 34,232 | 8,148 | ~11k | 26 | 22 |
| Q3 | 3/4 | 216 | 104 | 41,233 | 9,608 | ~14k | 24 | 24 |
| Q4 | 4/4 | 200 | 100 | 47,411 | 11,051 | ~16k | 46 | 40 |
| Q5 | 4/4 | 240 | 118 | 64,975 | 15,123 | ~22k | 44 | 32 |

All five lie inside the R-08a size range (22,992-88,116 characters). No label sits off an onset
in these movements. Printed markings (`build.py --check` output, `artifacts/leakage_check.txt`):
Q1 "Siegue subito" and the next-movement heading "[2. Allegro Moderato]"; Q2 "Arpeggio"; Q3 "Var.
1".."Var. 5", "Min. D.C.", f, p; Q4 none; Q5 f, p.

**Worked example moved (pre-registered rule).** R-08a's example positions (bar 3 and bar 6, beat
2) lie within 1 beat of a DCML boundary in at least one drawn movement, and so does every pair up
to (24, 27). The first clear pair is **(25, 28)**. `INSTRUCTIONS.md` differs from R-08a's only in
the ids (M → Q) and these two bar numbers; `SCHEMA.json` only in the id pattern and its
description.

### Checks (all PASSED)

- `build.py --check`: for Q1..Q5, no R-08a banned word, no Roman-numeral token, none of the
  movement's DCML label strings (75, 102, 24, 67, 48 checked), no identity or provenance word,
  no word of the movement's own title, no old id. `INSTRUCTIONS.md` and `SCHEMA.json` pass the
  label (length ≥ 4, all 5 movements), identity, title and old-id checks. The check fires on
  every planted cue (a label string, `V7`, `PAC`, `Bach`, `op. 5`, `wa05`, the title `Grave`,
  `M3`). Re-rendering gives byte-identical files.
- `score.py --harness` (`artifacts/harness.txt`):
  1. DCML ends and starts as (bar, beat) events: end and start F1 1.000 in all 5 movements; also
     1.000 when written only in printed bars and propagated (the labels are identical in both
     passes of every repeated bar).
  2. The detector through the annotator path (propagation off) equals D-12's `cadence` rows in
     `data/interim/dcml_jc_bach/comparators.csv`: 12 of 12 rows per movement, 0 mismatches.
  3. The detector's ends and starts are identical with and without the tempo word; the ground
     truth equals D-12's cache.
  4. Dry run in the session scratchpad: oracle as annotation → primary 1.000; detector as
     annotation → 0.440, equal to the detector with propagation (0.4398). Nothing was written to
     `artifacts/` except `harness.txt`.
- R-08a's `common.py`, `render.py` and `score.py` hash to the values in R-08a's preparation record
  (272d81dd..., 82785dc0..., b73b1b7e...), so they are unchanged.

### Comparators on the 5 movements (`artifacts/comparators.csv`, `comparators_summary.txt`)

| Method | Q1 | Q2 | Q3 | Q4 | Q5 | Mean end F1 ±1 beat | t-interval (4 df) |
|---|---|---|---|---|---|---|---|
| cadence (F-05c detector) | 0.300 | 0.333 | 0.484 | 0.541 | 0.527 | **0.437** | [0.297, 0.577] |
| proxy_last_onset | 0.353 | 0.255 | 0.082 | 0.128 | 0.265 | 0.217 | [0.080, 0.353] |
| grid4 | 0.071 | 0.178 | 0.462 | 0.250 | 0.212 | 0.234 | [0.057, 0.412] |

- Detector sensitivities: exact onset 0.437; each repeated passage once 0.439; ±1 bar 0.603.
  All drawn movements have quarter-note beats, so ±1 quarter note equals ±1 beat here.
- Recall of DCML cadences by type at ±1 beat via phrase ends (pooled): detector PAC 38/71, IAC
  4/11, HC 13/31, EC 0/11, DC 0/7, PC 0/1. DCML ends (reference): PAC 67/71, IAC 11/11, HC
  31/31, EC 11/11, DC 0/7, PC 1/1. Unlike the Mozart pilot (HC 38/62), every HC here sits on a
  DCML phrase end.
- The drawn set is close to the corpus for the detector (0.437 here, 0.427 over all 29).

### For the lead

- **Copy this folder, and nothing else, outside the repo, once per run:**
  `experiments/2026-09-28-R-08c-llm-unfamiliar-repertoire/blind_input/` (7 files:
  `INSTRUCTIONS.md`, `SCHEMA.json`, `Q1.txt`..`Q5.txt`) → for example
  `<session scratchpad>/r08c_R1/` and `<session scratchpad>/r08c_R2/`, each with an empty `out/`.
- **Ids per movement:** `Q1`, `Q2`, `Q3`, `Q4`, `Q5`. Run R1: one fresh annotator per id in
  `r08c_R1`; run R2: one fresh annotator per id in `r08c_R2` (10 in all). Use R-08b's prompt
  template (folder, the one file to annotate, write `out/Q#.json`). Never pass a repo path or
  `artifacts/selection.json` (the id → movement map).
- Save at once: `annotations_R1/Q#.json`, `annotations_R2/Q#.json`. Record agent ids and times in
  DECISIONS. Then `score.py --llm-dir .../annotations_R1 --run R1`, the same for R2, fill
  `recognition.json` (`{"R1": {"Q1": "correct"|"composer"|"wrong"|"none", ...}, "R2": {...}}`)
  from the strings, note any hand-back guesses as borderline, and run `score.py --compare`.

### Files and code state

- `blind_input/`: the annotators' only input. `artifacts/` (gitignored): `selection.json`
  (id → movement, sizes, strata), `bars_Q#.csv`, `ground_truth/Q#.json`, `render_sizes.csv`,
  `example_bars.json`, `comparators.csv`, `comparators_summary.txt`, `harness.txt`,
  `leakage_check.txt`.
- Code state: uncommitted (no commits in the repo). sha256 (`build.py --hashes`): `draw.py`
  0ba8c1b2..., `build.py` 05ad71e8..., `score.py` 212a6096..., `INSTRUCTIONS.md` 8ddc36ff...,
  `SCHEMA.json` b23bce72..., `Q1.txt` 269f5080..., `Q2.txt` 73f46ab6..., `Q3.txt` 4afb83cb...,
  `Q4.txt` 69e50a43..., `Q5.txt` 66c61f7b....
- Data: DCML `jc_bach_sonatas` v2.4 (commit ac9fd07); D-12 cache `data/interim/dcml_jc_bach/`
  (`cands.pkl`, `comparators.csv`, 2026-09-28 run). Draw wall time 10 s.
- Pre-registration sha256 (README up to `## Preparation record`): `ef24309683759c6e8accd5bbb3dfaa4c27d4c4ed3dbfa801e3def08599987796`.
