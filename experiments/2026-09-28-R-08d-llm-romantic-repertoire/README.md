# R-08d: does the LLM phrase annotator work on Romantic piano repertoire? (5 DCML corpora)
Ticket: R-08d    Hypothesis: gate for R-08 on PianoLens's target repertoire (Phase 7; feeds H4 / R-09 phrase boundaries)    Status: Provisional (pre-registered 2026-09-28; no annotation exists yet)

Prepared by `ml-researcher`. The annotators are separate, blind agents run by the lead. Nothing
in this header may be edited after any annotation is produced. Corrections go in new sections at
the end.

## Question

R-08a, R-08b and R-08c found that an in-session Claude annotator marks DCML phrase ends on
Classical / galant sonata movements at a mean end F1 of about 0.75-0.80 (±1 beat), and beats the
F-05c cadence detector (all three Confirmed with caveats). R-08c's audit licensed this only for
galant / Classical sonata-type movements in simple meters. PianoLens's target repertoire is
mostly Romantic, where phrase rhythm is less schematic and more often elided, and where many
phrase ends carry no standard cadence. This experiment asks:

**On 5 DCML-labelled Romantic piano pieces (one each from Chopin's mazurkas, Grieg's Lyric
Pieces, Tchaikovsky's The Seasons, Schumann's Kinderszenen and Liszt's Années de pèlerinage),
does the annotator reach the 0.70 go bar, and does it beat the F-05c detector on the same
pieces?**

Secondary: run-to-run variation (2 runs per movement); whether the misses are phrase ends that
DCML marks without a cadence; whether the annotator marks phrases at a finer or coarser level
than DCML.

## Go bar and falsification

- **Per-movement score:** phrase-end F1 at ±1 beat (R-08a's primary metric: the F-05c
  convention, one beat = the time signature's denominator; one-to-one matching, closest pairs
  first), averaged over the two runs A and B of that movement.
- **Primary:** the mean of the per-movement scores over the 5 movements.
- **GO:** primary ≥ 0.70 (point estimate, as in R-08a, R-08b and R-08c).
- **NO-GO:** primary < 0.70. This includes the case where the annotator beats the detector but
  stays below 0.70.
- **Beats the detector** (reported, not the go bar): mean paired per-movement difference
  (LLM − detector) > 0 **and** its t-interval (4 df) excludes 0 → "shown"; otherwise "not
  shown". The percentile bootstrap (10,000 resamples over movements, seed 20261001) is reported
  next to it; the t-interval decides (R-08a audit lesson).
- **Intervals.** For the primary and every paired difference: the t-interval (4 df) and the
  percentile bootstrap. "The interval lies above 0.70" is claimed only if the t-interval's lower
  end is above 0.70.
- **Near-the-bar reporting (R-08c audit lesson), always reported next to the verdict:** the
  leave-one-movement-out primary (5 values and their minimum), the worst-run variant (the lower
  of A and B in every movement), and the one-sided t-test p-value of primary > 0.70 (4 df). These
  describe how robust the verdict is. They do not change it.
- The 0.70 bar comes from `DECISIONS.md` (2026-09-27 after F-05b; restated after D-12). It is
  copied, not changed.
- **Consequence (DECISIONS 2026-09-28, R-08c confirmed):** before LLM phrase boundaries feed
  PianoLens's target repertoire or H4 / R-09, this test is required. What follows a GO or a NO-GO
  is the lead's decision.

### Can each branch be reached? (R-09 audit lesson)

- R-08c's between-movement SD of the per-movement LLM F1 was about 0.13, and Romantic pieces
  from 5 composers are likely to spread at least as much. With 5 movements the expected t
  half-width of the primary is about 2.78 × 0.13 / √5 ≈ 0.16. GO and NO-GO are both reachable.
  "The interval lies above 0.70" needs a primary of about 0.86 or more and is not expected.
- The detector's mean end F1 on the eligible movements of each corpus (D-13) is 0.341 (Chopin),
  0.307 (Grieg), 0.181 (Tchaikovsky), 0.420 (Schumann), 0.227 (Liszt): about 0.30 on average,
  lower than on J. C. Bach (0.427). With a paired SD of about 0.15-0.20 the t half-width is
  about 0.19-0.25, so "beats the detector shown" is expected if the annotator is near the go bar
  and not expected if it is near 0.45.

## Recognition (within-movement analysis only)

Unlike R-08c, this is **not** an unfamiliar-repertoire test. Several of these pieces are
famous (e.g. Kinderszenen, The Seasons), and recognition is expected for some. The question is
style, not familiarity. Each annotation has `recognised_piece`; the lead or the auditor
classifies each of the 10 strings, by reading the string only, as:

- **correct:** names the right composer and the right piece (opus and number, or its title);
- **composer:** names the right composer, but no piece or the wrong piece;
- **wrong:** names another composer or piece;
- **none:** null, or no named composer or piece.

The hand-back text of each annotator is also read; any guess there that the string lacks is
recorded as "borderline" next to `recognition.json` (R-08b lesson: self-report is a lower
bound). It does not change the class.

Analysis rules, fixed now:

- **Never pooled across movements** (R-08b audit). The only recognition contrast is within a
  movement: when A and B of the same movement fall in different classes, both F1 values are shown
  side by side.
- **Sensitivity:** if any movement is `correct` or `composer` in either run, the primary is also
  reported without those movements. Recognition does not gate the verdict (R-08b found no effect
  of a disguise that removed naming on Mozart, A − U +0.014, t [−0.029, +0.056]). If 3 or more
  movements are recognised in at least one run, the verdict is stated as "on largely recognised
  pieces" and the scope in the lead's decision must say so.
- **Label exposure (R-08c audit lesson).** The DCML Romantic labels were released on 2025-04-27,
  before the model's cutoff, so exposure to them is not excluded. The granularity analysis below
  is the pre-registered check of whether errors follow DCML's own conventions.

## Data

- DCML corpora (`DATASETS.md`, D-13; all CC BY-NC-SA 4.0), sparse clones under
  `data/raw/dcml_<corpus>/`: `chopin_mazurkas` v3.2, `grieg_lyric_pieces` v2.3,
  `tchaikovsky_seasons` v2.3, `schumann_kinderszenen` v2.3, `liszt_pelerinage` v2.3 (commits in
  `pianolens.data.dcml.CORPORA`). Loader `pianolens.data.dcml` (D-13):
  - scores: `load_score(corpus, stem, unfold=True, tempo_word=False)`, built only from the
    label-free `notes`, `measures` and `chords` TSVs (never `harmonies/`, which carries the
    labels; the `.mscx` files were not downloaded);
  - ground truth: `phrase_annotations(score)`: phrase ends (`}`, `}{`) and starts (`{`, `}{`),
    cadences PAC, IAC, HC, EC, DC, PC, mapped onto every pass of each bar of the unfolded score.
- Detector inputs: D-13's cache `data/interim/dcml_romantic/cands.pkl` (F-05c layout, keyed by
  `score_id`) and `comparators.csv`. The F-05c detector was fitted on Batik K.279-K.283, so
  every Romantic movement is held out for it.

## Movement selection (fixed before any annotation exists)

**Eligible** (DECISIONS 2026-09-28, R-08d design and draw details): a labelled movement of one of
the 5 corpora with

1. at least 5 phrase ends in the folded DCML labels (`}` or `}{`; D-13's `eligible`);
2. only simple meters (numerators 2, 3, 4; a movement that changes between simple meters is
   allowed);
3. `unfold_validated=True` (this excludes the 4 hand-unfolded Chopin mazurkas: BI16-2, BI73,
   BI61-5, BI77-3);
4. at most 120,000 characters when rendered with R-08a's renderer, on the `tempo_word=False`
   score, with the placeholder id `X`.

**Draw** (`draw.py`, seed 20261001, `numpy.random.default_rng`):

1. Within each corpus, the eligible movements are sorted by rendered size (ties by stem) and
   cut into 3 contiguous tertiles with `numpy.array_split` (T1 smallest). Strata are within a
   corpus, not an absolute size window, because Kinderszenen pieces are all small.
2. Tertile per corpus: two distinct extra tertiles are drawn (`rng.choice(3, 2,
   replace=False) + 1`) and added to (1, 2, 3); the 5 values are shuffled (`rng.permutation`)
   and assigned to the corpora in the order chopin_mazurkas, grieg_lyric_pieces,
   tchaikovsky_seasons, schumann_kinderszenen, liszt_pelerinage. So every tertile is used at
   least once and at most twice.
3. One movement per corpus: that tertile's members sorted by stem, `rng.choice(len)`.
4. Blind ids `R1`..`R5` are assigned by `rng.permutation(5)`, so an id does not encode the
   corpus.

The pool, before the draw (`draw.py --sizes`, no random numbers used): eligible Chopin 49,
Grieg 45, Tchaikovsky 9, Schumann 10, Liszt 7 (one simple-meter Liszt piece exceeds 120,000
characters). The draw writes `artifacts/selection.json`; the outcome is appended below under
"Selection outcome", unchanged by anything that follows.

## Rendering (the annotator's only input)

`build.py` renders each drawn movement with R-08a's `common.render` (imported, not copied or
changed) to `blind_input/R#.txt`. Layout, beat labels, pointer bars and the bar table are
exactly R-08a's. Differences from Batik renderings, disclosed before the draw:

- **No `Tempo` events** (`tempo_word=False`, as in R-08b's disguise and R-08c): the tempo marks
  and metronome marks that the scores enter as tempo objects are dropped. Tempo words that a score
  enters as staff or system text (e.g. "Andante placido", "Più lento") are kept as printed, like
  any other staff text. The Romantic corpora's movement titles are never rendered (they name the
  piece).
- **Kept:** dynamics, hairpins (`cresc.` / `dim.`), staff and system text, with D-13's text
  normalisations: "Tempo I" / "Temp. I." is printed "Tempo primo" (R-08a's Roman-numeral check
  would read it as a label), and Liszt's "una chorda" / "tres chorde" as "una corda" / "tres
  corde" (the check would read "chord").
- **Identity rule for printed text.** If any printed text item of a drawn movement hits the
  identity check below (composer, piece, title or corpus words), that whole text item is removed
  from the score before rendering, and each removal is listed in the preparation record. No other
  text is removed.
- No fermatas, no slurs, no pedal marks, rests derived from gaps, no key mode (D-13 loader).
- A third staff (Liszt) is printed as RH by R-08a's renderer; disclosed if drawn.

### Leakage and identity check (`build.py --check`; must pass before any annotator runs)

For every `R#.txt`, and for `INSTRUCTIONS.md` and `SCHEMA.json`:

- R-08a's banned annotation vocabulary (`BANNED_WORDS`) and Roman-numeral tokens (`ROMAN`),
  imported from R-08a's `render.py`;
- the movement's DCML label strings (`dcml.label_strings`, length ≥ 3, not purely numeric; for
  `INSTRUCTIONS.md` and `SCHEMA.json`, length ≥ 4 over all 5 movements, because the cadence names
  are part of the task);
- identity: composer names and first names of the 5 composers and R-08c's list; catalogue
  patterns (op., opus, BI, S. / Searle, TH, KK, LW); the file-stem patterns of the 5 corpora
  (`BI\d`, `op\d\d`, `op37a`, `n\d\d`, `16[012]\.\d\d`); corpus words (mazurka, lyric /
  lyrische, seasons, kinderszenen, pèlerinage, années, suisse, italie, venezia, napoli, the 12
  month names); **every title word** (4+ letters, case-insensitive, minus a short list of
  generic words fixed in `build.py`) from `workTitle`, `movementTitle`, `title_text` and
  `subtitle_text` of every movement of the 5 corpora, and from every stem; provenance words
  (DCML, pianolens, `/Users/`, `experiments/`, ms3, harmonies);
- no stray ids of earlier runs (`M1`..`M5`, `Q1`..`Q5`; `D1`..`D5` only in the text files,
  because they are note names in a rendering).

The check must be shown to fire on planted cues (a label string, `V7`, `PAC`, a composer name,
`op. 68`, a stem, the movement's own title word, `Q3`).

## Instructions and schema

`INSTRUCTIONS.md` and `SCHEMA.json` are R-08a's, with the ids changed (`M` → `R`) and **one
wording change: the period phrase is dropped.** R-08a's first sentence reads "five text
renderings of piano movements from the Classical period"; R-08d's reads "five text renderings
of piano movements". Decision and reasons:

- "Classical period" is false for all five pieces and would cue galant schemata that these
  pieces do not follow, so a NO-GO could come from the wrong cue rather than the annotator.
- A replacement period ("Romantic", "19th-century") names a style and narrows the composer
  pool (with a 3/4 dance texture, "Romantic" points at Chopin), which raises recognition, which
  this test does not need. "19th-century" is also not exact for every candidate (Grieg's op. 71
  is from 1901).
- Dropping it is accurate for every candidate, adds no cue, and makes this test at least as hard
  as R-08a-c on this point: R-08a-c's annotators got a correct period cue and these get none.
  A deployed annotator that is told the period would face an easier task, so a GO here is a
  conservative result; a NO-GO near the bar would justify a follow-up with a period cue.

**Cadence types stay R-08a's set** (PAC, IAC, HC, EC, DC, none). The primary metric does not use
the types, and adding a definition would change the instructions for a secondary metric. DCML
marks plagal cadences (PC; 50 in the unfolded pool corpora, vs 1 in R-08c's draw) that the
annotator cannot type; PC recall via phrase ends is still reported, and the types the annotator
gives at DCML PC positions are listed.

The instructions' phrase definition ("closes with a cadence (or, rarely, a clear arrival
without a standard cadence)") is kept word for word, although DCML's Romantic phrase ends often
carry no cadence label. This may push the annotator to miss those ends; the split below
measures it.

- **Worked example.** R-08a's example uses bar 3 beat 2 (start) and bar 6 beat 2 (end and
  start). If either position lies within 1 beat of a DCML phrase end or start in any drawn
  movement, both bar numbers are moved up together (4 and 7, then 5 and 8, ...) to the first
  pair that is clear in all 5, as in R-08c, and the change is recorded in the preparation
  record. A position that does not exist in a movement counts as clear.

## Conditions and blinding (R-08a / R-08b / R-08c protocol and audit lessons)

- **Two runs**, A and B (not "R1"/"R2", which are now movement ids). Each run has one fresh
  annotator per movement: 10 annotators in all. Same model and agent type as R-08a-c (in-session
  `claude-opus-5-5`, general-purpose, background). The lead records model, agent ids and times.
- The lead copies `blind_input/` to two folders **outside the repo** (one per run) and gives each
  annotator only that path, its one file `R#.txt`, and where to write `out/R#.json`. The prompt
  template is R-08b's / R-08c's. It does not say composer, corpus, period or that any piece is
  famous or unfamiliar.
- An annotator may read only `INSTRUCTIONS.md`, `SCHEMA.json` and its own `R#.txt`. No web
  search, no other files. One pass, no feedback. A technical failure (malformed JSON,
  truncation) may be rerun once, before scoring, and is disclosed. If a run is still missing,
  that movement's score uses the run that exists, and this is disclosed.
- **Each JSON is copied verbatim into this folder at once** (`annotations_A/R#.json`,
  `annotations_B/R#.json`), before scoring. Transcripts are kept for the auditor's file-access
  check.

## Metrics (`score.py`)

R-08a's scoring functions are loaded from R-08a's `score.py` (importlib, not copied or
changed): `map_events`, `score_movement`, `boundary_prf`, `match_pairs`, `summarise`,
`as_events`, `pointer_map`. The cadence-type list is extended with PC. Per run and movement:

- **Primary input:** phrase-end P / R / F1 at ±1 beat.
- End F1 at ±1 bar; start F1 at ±1 beat and ±1 bar; DCML cadence F1; cadence recall by type at
  ±1 beat via phrase ends and via all cadence marks; confidence ≥ 0.5 variant (descriptive).
- Sensitivities: exact-onset end F1; end F1 at ±1 quarter note; end F1 counting each repeated
  passage once.
- **Cadenced vs uncadenced ends (new, descriptive):** recall at ±1 beat, pooled over movements,
  of DCML phrase ends that carry a DCML cadence label at the same position vs those that do not,
  for the LLM (per run) and the detector.
- **Granularity (new, descriptive; the label-exposure check):** per movement and run, P − R at
  ±1 beat and the ratio of predicted to DCML phrase ends. A ratio above 1 with P < R means finer
  phrases than DCML's; below 1 with P > R, coarser. A model recalling DCML's labels would show
  ratios near 1 with high P and R; a systematic level mismatch in both runs (as R-08c's Q3) argues
  against recall.

Aggregation: the go rule, the paired LLM − detector test, both intervals and the near-the-bar
reporting, as above; run-to-run (per movement A, B, |A − B|, mean within-movement SD, run
means); HC and PC recall via phrase ends, pooled, per run, against the detector and the DCML-ends
reference; per-movement table (LLM A, B, mean; detector; proxy; grid4); per-corpus rows are the
per-movement rows (one movement per corpus), so no corpus-level claim is made. Descriptive only:
this primary next to R-08c's 0.750 and R-08b's 0.802 / 0.789. No test across corpora.

## Comparators (same 5 movements, computed before any annotation)

- `cadence`: the F-05c detector (`pianolens.features.cadence.cadence_phrase_ends`, shipped
  defaults), ends and starts, computed on the `tempo_word=False` score.
- `proxy_last_onset` (ends), `proxy` (starts), `grid4` (every 4th downbeat), `oracle_dcml_ends`:
  as in D-13 / D-12.
- The comparator for the go rule and the paired test is the detector's own score on every
  performed bar (as in R-08a / R-08c), not its score through the annotation path.

## Harness checks (`score.py --harness`; must pass before any annotator runs)

1. **True labels give F1 1.0.** The DCML ends and starts, written as (bar, beat) events through
   the bar table and scored through the annotator path (propagation off): end and start F1 =
   1.000 at ±1 beat, every movement. Also reported: the same events written only in printed bars,
   then propagated (a value below 1.000 is recorded, not a failure).
2. **Detector reproduces D-13.** The detector's ends and starts, written as (bar, beat) events
   and scored through the annotator path with propagation off, equal D-13's `cadence` rows in
   `data/interim/dcml_romantic/comparators.csv` (tp, n_pred, n_true and F1, for every target and
   tolerance, and every per-type row), for all 5 movements.
3. The detector's ends and starts are identical on the `tempo_word=True` score (D-13's) and the
   `tempo_word=False` score (R-08d's), and the ground truth equals D-13's cache.
4. **End-to-end dry run** (scratch folder, nothing written to `artifacts/` except
   `harness.txt`): the oracle written as an annotation JSON gives primary 1.000; the detector
   written as an annotation JSON gives the detector's mean with propagation on.

## Method

1. `draw.py` → `artifacts/selection.json`.
2. `build.py` → `blind_input/R#.txt`, `INSTRUCTIONS.md`, `SCHEMA.json`, `artifacts/bars_R#.csv`,
   `artifacts/ground_truth/R#.json`, `artifacts/render_sizes.csv`; then `build.py --check`.
3. `score.py --comparators`; `score.py --harness`.
4. (Lead) run the 10 blind annotators; save the JSON files as above.
5. `score.py --llm-dir annotations_A --run A`, `score.py --llm-dir annotations_B --run B`.
6. (Lead or auditor) fill `recognition.json`; `score.py --compare` →
   `artifacts/r08d_summary.txt`. Results are appended to this README.

## Command

```
uv run python experiments/2026-09-28-R-08d-llm-romantic-repertoire/draw.py
uv run python experiments/2026-09-28-R-08d-llm-romantic-repertoire/build.py
uv run python experiments/2026-09-28-R-08d-llm-romantic-repertoire/build.py --check
uv run python experiments/2026-09-28-R-08d-llm-romantic-repertoire/score.py --comparators
uv run python experiments/2026-09-28-R-08d-llm-romantic-repertoire/score.py --harness
uv run python experiments/2026-09-28-R-08d-llm-romantic-repertoire/score.py --llm-dir experiments/2026-09-28-R-08d-llm-romantic-repertoire/annotations_A --run A
uv run python experiments/2026-09-28-R-08d-llm-romantic-repertoire/score.py --llm-dir experiments/2026-09-28-R-08d-llm-romantic-repertoire/annotations_B --run B
uv run python experiments/2026-09-28-R-08d-llm-romantic-repertoire/score.py --compare
```

Seeds: draw 20261001, bootstrap 20261001. Code state: uncommitted (the repo has no commits);
sha256 of the scripts and blind inputs go in the preparation record.

## Threats to validity (known before running)

- n = 5 movements from 5 composers, one per corpus: breadth over depth. No per-composer claim is
  possible; one hard corpus can decide the verdict (hence leave-one-out).
- **Annotation standard.** Each DCML corpus has its own annotators. Romantic phrase ends are
  often uncadenced and the level (sub-phrase vs phrase vs period) is more a matter of judgement
  than in galant music, so a low score may reflect the standard as much as the annotator.
- **Familiarity and label exposure.** Some pieces are famous; recognition is recorded, not
  prevented. The DCML labels predate the model's cutoff. Only post-cutoff labels (OWNER task)
  would exclude label exposure.
- **Input.** No tempo words, no fermatas, no pedal, no slurs, derived rests. Romantic phrasing
  leans on slurs, fermatas and tempo changes more than galant phrasing does, so the renderings
  withhold more of the relevant information than in R-08c, and a NO-GO may partly reflect the
  input.
- **Instructions.** No period cue (conservative, above); the phrase definition leans on
  cadences.
- The detector is weak on these corpora (about 0.30); beating it is a low bar.
- Two runs per movement estimate run-to-run variance only roughly.
- Compound meters (6/8, 12/8 in Grieg, Tchaikovsky, Liszt) are excluded, so the result says
  nothing about them.

## Selection outcome (draw.py, seed 20261001, run 2026-09-28 before any blind input was built or any annotation existed)

Tertile assignment: Chopin T1, Grieg T3, Tchaikovsky T2, Schumann T2, Liszt T1.

| Id | Corpus | Movement (stem) | Tertile | Time signature | Characters (id `X`) |
|---|---|---|---|---|---|
| R1 | tchaikovsky_seasons | op37a06 | T2 of 9 | 4/4, 3/4 | 32,069 |
| R2 | chopin_mazurkas | BI61-4op07-4 | T1 of 49 | 3/4 | 13,780 |
| R3 | schumann_kinderszenen | n07 | T2 of 10 | 4/4 | 9,195 |
| R4 | grieg_lyric_pieces | op57n01 | T3 of 45 | 3/4 | 48,097 |
| R5 | liszt_pelerinage | 160.02_Au_Lac_de_Wallenstadt | T1 of 7 | 3/8, 2/4 | 33,752 |

The pool, the tertile members and the picks are in `artifacts/selection.json` (the id → movement
map; never given to an annotator). R1 changes between two simple meters (allowed). R5 is mostly
in 3/8 (101 of 112 bars): numerator 3 counts as simple under the registered rule (as in D-13),
so one beat is an eighth note there and ±1 beat is narrow; the ±1 quarter-note sensitivity is
reported. R3 is Kinderszenen no. 7 (Träumerei), among the most famous piano pieces; recognition
is expected there (see "Recognition").

## Preparation record (2026-09-28, ml-researcher; no annotation exists yet)

Everything above this section is the pre-registration. Its sha256 (the file up to, not
including, the line `## Preparation record`) is given at the end of this section.

### Edits to the header before hashing (disclosed)

- The "Selection outcome" section was appended after `draw.py` ran, as in R-08a and R-08c.
- **Rendering, tempo words.** The first wording said "No tempo words or metronome marks". The
  build showed that R4 and R5 carry tempo words as staff or system text ("Adagio", "Allegro
  vivace", "Andantino", "Molto vivo", "Più lento"; "Andante placido"), which `tempo_word=False`
  does not drop (it drops `Tempo` events only, as in D-13's loader). The bullet was corrected to
  describe what the loader does; the rendering rule itself did not change, and no text was
  removed because of it. Tempo words do not name the piece.
- **Identity check.** The first run of `build.py --check` hit R-08a's own `INSTRUCTIONS.md` text
  on two generic English words: "may" ("You may also mark", matched as the month) and "event" (a
  Kinderszenen title word, "An Important Event"). The month pattern was made case-sensitive
  (`May`) and "event" was added to the generic-word list in `build.py`. The renderings passed
  before and after this change. A planted "May" still fires.
- `draw.py`: one print line was re-wrapped after the draw to pass `ruff` (no logic change); the
  draw was rerun and `selection.json` is byte-identical.

### Renderings (`blind_input/`)

| Id | Time | Performed bars | Pointer bars | Characters | Words | Tokens (rough, chars / 3) | DCML ends | Cadences |
|---|---|---|---|---|---|---|---|---|
| R1 | 4/4, 3/4 | 99 | 0 | 32,071 | 7,783 | ~11k | 20 | 16 |
| R2 | 3/4 | 61 | 16 | 13,782 | 3,216 | ~5k | 13 | 11 |
| R3 | 4/4 | 33 | 7 | 9,197 | 2,161 | ~3k | 8 | 8 |
| R4 | 3/4 | 153 | 0 | 48,099 | 11,489 | ~16k | 22 | 16 |
| R5 | 3/8, 2/4 | 112 | 0 | 33,754 | 7,585 | ~11k | 5 | 5 |

- R2 and R3 are shorter than any R-08a / R-08c rendering (R-08a range 22,992-88,116). All five
  have two staves. One R1 label sits off a note onset (`labels_off_onset` 1); none in the others.
- No printed text hit the identity rule (`artifacts/identity_removals.json`: none removed).
- Printed markings (`build.py --check`): R1 dynamics, cresc./dim., "ma poco a poco cresc.",
  "più", "poco più", "un poco cresc."; R2 "a tempo", "dolciss.", "molto rallent.", "riten.",
  "scherz.", "sempre legato", "smorz.", "sotto voce", "staccato", dynamics; R3 "rit.",
  "ritard.", "ritardando", cresc., p; R4 "Adagio", "Allegro vivace", "Andantino", "Molto vivo",
  "Più lento", "(longa)", "dolce e leggiero", "molto cresc. e stretto", "poco dim. e molto
  rit.", "una corda", "tre corde", dynamics, and one "other-dynamics" (a MuseScore placeholder
  dynamic that R-08a's renderer prints through its dynamics path; not an identity cue); R5
  "Andante placido", "Tempo primo", "cantabile", "dolcissimo egualmente", "più forte la mano
  destra", "un poco più animatoil tempo" (spacing as in the source), "una corda", "perdendosi",
  "raddolcente", "smorzando" and others, dynamics. None names a composer, piece or catalogue
  number.
- DCML annotators (metadata `annotators`): R1 A. Nagel, J. Heilig; R2 W. Bitzan, A. Nagel,
  D. Krkljus; R3 T. Soker, J. Heilig; R4 A. Nagel, J. Heilig; R5 A. Nagel, A. Brey.

**Worked example moved (pre-registered rule).** R-08a's example bars (3, 6) lie within 1 beat of
a DCML boundary in at least one drawn movement; the first clear pair is **(4, 7)**.
`INSTRUCTIONS.md` differs from R-08a's only in the ids (M → R), the dropped period phrase
(first sentence: "five text renderings of piano movements (`R1.txt` to `R5.txt`)") and these two
bar numbers; `SCHEMA.json` only in the id pattern and its description (checked with `diff`).

### Checks (all PASSED)

- `build.py --check` (output in `artifacts/leakage_check.txt`): for
  R1..R5, no R-08a banned word, no Roman-numeral token, none of the movement's DCML label strings
  (97, 31, 41, 146, 35 checked), no identity, title (all 5 corpora, 193 words after the
  generic list) or provenance word, no old id. `INSTRUCTIONS.md` and `SCHEMA.json` pass the label
  (length ≥ 4, all 5 movements), identity and old-id checks. In every rendering the check fires on
  every planted cue (a label string, `V7`, `PAC`, `Chopin`, `Liszt`, `op. 68`, the stem, the
  movement's own title word, `Q3`, `May`).
- `score.py --harness` (`artifacts/harness.txt`):
  1. DCML ends and starts as (bar, beat) events: end and start F1 1.000 in all 5 movements; also
     1.000 when written only in printed bars and propagated.
  2. The detector through the annotator path (propagation off) equals D-13's `cadence` rows in
     `data/interim/dcml_romantic/comparators.csv`: 12 of 12 rows per movement, 0 mismatches.
  3. The detector's ends and starts are identical with and without the tempo word; the ground
     truth equals D-13's cache.
  4. Dry run in the session scratchpad: oracle as annotation → primary 1.000; detector as
     annotation → 0.3890, equal to the detector with propagation (0.3889). Here the detector is
     pass-consistent (its propagated F1 equals its own in every movement), unlike on J. C. Bach.
- R-08a's `common.py`, `render.py` and `score.py` hash to the values in R-08a's preparation record
  (272d81dd..., 82785dc0..., b73b1b7e...), so they are unchanged.

### Comparators on the 5 movements (`artifacts/comparators.csv`, `comparators_summary.txt`)

| Method | R1 | R2 | R3 | R4 | R5 | Mean end F1 ±1 beat | t-interval (4 df) |
|---|---|---|---|---|---|---|---|
| cadence (F-05c detector) | 0.581 | 0.364 | 0.500 | 0.500 | 0.000 | **0.389** | [0.102, 0.676] |
| proxy_last_onset | 0.226 | 0.606 | 0.118 | 0.411 | 0.000 | 0.272 | |
| grid4 | 0.227 | 0.000 | 0.000 | 0.233 | 0.061 | 0.104 | |

- The detector marks 3 ends on R5 (Liszt, 5 DCML ends in 112 bars) and hits none. Its drawn-set
  mean (0.389) is above the mean of its per-corpus eligible means (about 0.30, D-13).
- Detector sensitivities: exact onset 0.364; ±1 quarter note 0.389; ±1 bar 0.414.
- Recall of DCML cadences by type at ±1 beat via phrase ends (pooled): detector PAC 15/31, IAC
  5/8, HC 1/16, PC 1/1 (no EC or DC in the draw). DCML ends (reference): all 56 cadences sit on a
  DCML phrase end. Of the 68 DCML phrase ends, 40 carry a cadence label at the same beat and 28
  do not; the detector recalls 14/40 and 11/28.

### For the lead

- **Copy this folder, and nothing else, outside the repo, once per run:**
  `/Users/vuducdung/personal/pianolens/experiments/2026-09-28-R-08d-llm-romantic-repertoire/blind_input/`
  (7 files: `INSTRUCTIONS.md`, `SCHEMA.json`, `R1.txt`..`R5.txt`) → for example
  `<session scratchpad>/r08d_A/` and `<session scratchpad>/r08d_B/`, each with an empty `out/`.
- **Ids per movement:** `R1`, `R2`, `R3`, `R4`, `R5`. Run A: one fresh annotator per id in
  `r08d_A`; run B: one fresh annotator per id in `r08d_B` (10 in all). Use R-08c's prompt
  template with `Q#` → `R#` (folder, the one file to annotate, write `out/R#.json`). Never pass a
  repo path or `artifacts/selection.json`.
- Save at once: `annotations_A/R#.json`, `annotations_B/R#.json`. Record agent ids and times in
  DECISIONS. Then `score.py --llm-dir .../annotations_A --run A`, the same for B, fill
  `recognition.json` (`{"A": {"R1": "correct"|"composer"|"wrong"|"none", ...}, "B": {...}}`)
  from the strings, note hand-back guesses as borderline, and run `score.py --compare`.

### Files and code state

- `blind_input/`: the annotators' only input. `artifacts/` (gitignored): `selection.json`,
  `bars_R#.csv`, `ground_truth/R#.json`, `render_sizes.csv`, `example_bars.json`,
  `identity_removals.json`, `leakage_check.txt`, `comparators.csv`, `comparators_summary.txt`, `harness.txt`.
- Code state: uncommitted (no commits in the repo). sha256 (`build.py --hashes`): `draw.py`
  5f5bd518..., `build.py` c3db78ae..., `score.py` 2dbdf97d..., `INSTRUCTIONS.md` de6d8da7...,
  `SCHEMA.json` 97d1dbe2..., `R1.txt` ba4f84f1..., `R2.txt` a3df9ec2..., `R3.txt` 7e1213ee...,
  `R4.txt` d951adea..., `R5.txt` 475b4383....
- Data: DCML Romantic corpora at the D-13 tags; D-13 cache `data/interim/dcml_romantic/`
  (`cands.pkl`, `comparators.csv`, 2026-09-28 run). Draw wall time about 40 s.
- Pre-registration sha256 (README up to `## Preparation record`): `dbef84aee6cd1ba92464a3f58dea61698389f80b5dabaecae9d288efbc577708`.


## Results (lead, 2026-09-28; audited, see the Audit section)

The full tables are in `artifacts/r08d_summary.txt`, reproduced byte-identically by the auditor.

**Headline: GO by the pre-registered point-estimate rule, fragile.**
- Primary 0.737, with t-interval [0.439, 1.036]. The one-sided p against 0.70 is 0.373.
- The worst-run variant is 0.698. The leave-one-out minimum is 0.687 (without R3).
- The observed between-movement SD is 0.241, against the 0.13 assumed for reachability, so only
  the point-estimate rule decides.
- **Beats the detector:** detector 0.389, paired +0.348 (t [+0.267, +0.430]). The LLM is ahead
  on 5 of 5 movements.
- Run-to-run SD within a movement is 0.056.

Per movement (mean of runs A and B):

| Id | Piece | LLM | Detector |
|---|---|---|---|
| R1 | Tchaikovsky op. 37a/6 | 0.866 | 0.581 |
| R2 | Chopin op. 7/4 | 0.760 | 0.364 |
| R3 | Schumann Kinderszenen 7 | 0.938 | 0.500 |
| R4 | Grieg op. 57/1 | 0.798 | 0.500 |
| R5 | Liszt S.160/2 | 0.325 | 0.000 |

**R5 is granularity plus two real misses.**
- Both runs hit 3 of 5 DCML ends, so recall is 0.60 and precision about 0.22.
- The extras are subdivisions of DCML's 16-31-bar phrases.
- Both runs miss the same two ends: the HC at bar 59 (they placed it at 53) and the final end at
  bar 108.

**The granularity (level-match) check is informative on R5 only.** On R1-R4 the ratios are near 1,
which is consistent with either real annotation or recall.

**Recognition:** 0 of 10 runs recognised a piece. There were two wrong-composer guesses
("Beethoven"). Silent recognition cannot be audited.

## Audit (2026-09-28, eval-auditor)

**Verdict: Confirmed with caveats. GO by the pre-registered rule (primary 0.737 ≥ 0.70, point
estimate), and "beats the detector" is shown (paired +0.348, t [+0.267, +0.430], 5 of 5
positive). The GO is fragile: the t-interval [0.439, 1.036] is uninformative about the bar, the
worst-run variant is 0.698, leaving out Träumerei (R3) gives 0.687, and the one-sided p of
primary > 0.70 is 0.373. What it licenses: on DCML-style phrase ends in Romantic character pieces
in simple meters, the annotator is usable on average and clearly better than the F-05c detector,
but per piece it ranges from 0.325 to 0.938, so a single piece can be poor. It does not show that
the annotator reaches 0.70 on Romantic repertoire in general.**

Audited: pre-registration hash and timeline, rule application, the draw, the renderings and the
leakage check, blinding in all 10 transcripts, the scorer and harness, recognition, and the
interpretation (R5 granularity, tolerance in 3/8, label exposure). Audit scripts are in the
session scratchpad (`r08d_audit/rerun.py`, `redraw.py`). Nothing in `src/`, the experiment
scripts, `blind_input/`, `annotations_*` or `artifacts/` was changed.

### 1. Pre-registration: intact, rule applied word for word

- README up to `## Preparation record` hashes to `dbef84ae...7708`, as recorded. The README was
  last modified at 04:37:12 (local); the first annotator's first event is 04:39:09 (09:39:09Z in
  the transcript), so the whole README, not only the header, predates every annotation.
- `draw.py`, `build.py`, `score.py`, `INSTRUCTIONS.md`, `SCHEMA.json` and `R1..R5.txt` hash to the
  prefixes in the preparation record. R-08a's `common.py`, `render.py`, `score.py` hash to
  `272d81dd`, `82785dc0`, `b73b1b7e` (unchanged).
- `INSTRUCTIONS.md` differs from R-08a's only in M → R, the dropped period phrase and the moved
  worked example (4, 7) (checked with `diff`), as registered.
- The rule in `score.compare` is the registered one: mean of A and B per movement, mean over 5;
  GO at ≥ 0.70 on the point estimate; "interval above 0.70" not claimed (t lower end 0.439);
  "shown" because the paired mean is > 0 and its 4-df t-interval excludes 0; the comparator is
  the detector's own score (0.389). Near-the-bar numbers are reported next to the verdict and do
  not change it, as registered.
- The two disclosed pre-hash edits (the tempo-word bullet corrected to describe what the loader
  does; "May" made case-sensitive and "event" added to the generic list) were made before any
  annotation existed and change no rule, metric or comparator. I accept them. The first is a
  wording correction after seeing the build output, and it matters for item 3 below.
- The reachability paragraph assumed a between-movement SD of about 0.13. The observed SD of the
  per-movement means is 0.241, so the t half-width is 0.299, not 0.16. With this spread the
  experiment cannot separate 0.70 from 0.45 or from 1.0; only the point-estimate rule decides.

### 2. Blinding: clean in all 10 transcripts

- Each of the 10 agents (ids in DECISIONS, R-08d annotation run) made only these calls: Read
  `INSTRUCTIONS.md`, Read `SCHEMA.json`, Read its own `R#.txt`, one write of `out/R#.json` (Bash
  heredoc, Python `json.dump` to that one path, or the Write tool), an optional `json.load` of its
  own output, and the hand-back. No `ls`, `find`, `glob`, `cat` of another file, web tool or repo
  path. Every Read was inside `r08d_A/` or `r08d_B/`.
- Both R4 annotators (A and B) hit the read-size limit and read R4 in two Reads (offset 797); the
  second read's tool result ends with the `END` line in both, so both saw the whole rendering. No
  other truncation notice.
- The 10 prompts are identical after normalising the run folder and the id (one sha). They name
  no composer, corpus, period or familiarity.
- Context: the user's global `CLAUDE.md` and personal `MEMORY.md` only. The environment block
  shows the cwd (`.../pianolens`) and a public GitHub remote name, as in R-08a-c. With cwd fields
  removed, no transcript contains "DCML" (one base64 hit), a corpus word or any of the 5 composers;
  the only composer names are the annotators' own guesses (A/R2 and B/R5, "Beethoven").
- Model `claude-opus-5-5` in every transcript. Scratchpad inputs are byte-identical to
  `blind_input/`; the 10 repo annotations are byte-identical to the scratchpad `out/` files.
- Thinking blocks are empty (redacted), as in R-08b/c, so silent recognition cannot be audited.

### 3. Renderings, leakage check, scorer and harness: reproduced

- Draw: replicated from the pool in `selection.json` with seed 20261001 (eligibility, tertiles,
  tertile assignment, picks and blind ids all equal). Re-rendering the 5 picks with the build's
  own loader gives byte-identical `R1..R5.txt`, with no identity removals.
- `build.py --check` (read-only) passes, and its output is identical to `leakage_check.txt`.
- Printed text that remains, as disclosed: R5 "Andante placido" (Liszt's own heading for this
  piece), "Tempo primo" (rewritten from "Tempo I"), "una corda" (rewritten from Liszt's "una
  chorda"), "perdendosi", "raddolcente", "mancando"; R4 "Andantino", "Allegro vivace", "Molto
  vivo", "Più lento", "Adagio", "tre corde" (not rewritten; Grieg's spelling), one
  "other-dynamics" placeholder; R1-R3 dynamics and rit./cresc. words only. None names a composer,
  piece, title or catalogue number. "Andante placido" is the one piece-specific cue: an expert who
  knows the score could use it. It did not lead to recognition (B/R5 read the markings as
  "late-Beethoven-style"). The "una chorda" → "una corda" rewrite removes a Liszt spelling
  fingerprint, so it is conservative. "Tempo primo" is neutral. Tempo words were in no earlier
  R-08c rendering, so R-08d's input carries more tempo information than R-08c's; this is
  disclosed in the header and I do not count it as a leak.
- Harness rerun against a scratch copy of `artifacts/`: PASSED, `harness.txt` byte-identical.
  Scoring rerun to scratch (`run_llm` A and B, `compare`, `run_comparators`): `scores_A.csv`,
  `scores_B.csv`, `summary_A.txt`, `summary_B.txt`, `r08d_summary.txt`, `comparators.csv` and
  `comparators_summary.txt` are byte-identical to `artifacts/`.
- Independent recomputation from `scores_*.csv`: primary 0.7372, t [0.4387, 1.0357]; one-sided p
  0.3734; LOO 0.705 / 0.732 / 0.687 / 0.722 / 0.840; worst-run 0.698, best-run 0.777; paired
  per movement +0.285, +0.396, +0.438, +0.298, +0.325; within-movement SD 0.056. All equal the
  summary.

### 4. Interpretation

**R5 (Liszt, Au lac de Wallenstadt; 0.316 / 0.333).** Both runs hit 3 of 5 DCML ends exactly
(bars 19, 35, 77, all at 0 beats distance), so recall is 0.60 in both runs, and precision is
0.21 / 0.23 (14 and 13 predicted ends). The low score has two parts:

- *Granularity (most of the precision loss).* Of the 11 (A) and 10 (B) unmatched predictions,
  8 in each run are finer subdivisions of DCML phrases: ends 7-8 bars before a DCML end (bars
  11/12, 27/28, 69), bar 85 (A), and cadences inside DCML's single 31-bar closing phrase (bars 89,
  93, 95, 104, and 111 in B). The rest are the middle-section ends at bars 44 (A) and 48 and the
  early HC at bar 53.
  DCML phrases here are 16-31 bars of 3/8; the annotator's are mostly 8 bars. This is the same
  pattern as R-08c's Q3, and it is a disagreement about level, not a failure to find phrase ends.
- *Two real placement disagreements (all of the recall loss).* Both runs miss the same two DCML
  ends: the HC at bar 59 (both annotators put the HC at bar 53 and read 53-62 as standing on the
  dominant) and the final end at bar 108 (both put it at 104, B also at 111). These are 4-6 bars
  away, so no tolerance fixes them.
- So "R5 is only a granularity mismatch" overstates it: granularity explains the extras, not the
  two misses. With the confidence ≥ 0.5 filter, R5 is 0.600 (A) / 0.545 (B), because the
  subdivisions carry low confidence; the filter lowers the overall mean (0.651 / 0.689), so it is
  not a fix.

**Is ±1 beat fair in 3/8?** One beat is an eighth note there, the narrowest tolerance in the
draw. It makes no difference: R5's F1 is identical at ±1 beat, ±1 quarter note and ±1 bar in
both runs, because the 3 hits are exact and every miss or extra is 3+ bars away. The metric's
real sensitivity on R5 is the sparse ground truth: with 5 DCML ends, each extra or miss moves F1
a lot, and F1 cannot credit a nested (finer) segmentation. The overall ±1 bar sensitivity is
0.805 and exact onset 0.679.

**Precision/recall and cadence split.** R1-R4 are balanced (P 0.65-1.00, R 0.73-1.00, ratio
predicted/DCML 0.90-1.31). Recall of DCML ends with a cadence label is 37/40 (A) and 35/40 (B);
without one, 19/28 and 23/28. So the cadence-leaning phrase definition costs recall on
uncadenced Romantic ends, as the header predicted.

**Label exposure.** The registered granularity check argues against recall only where the
levels differ, which is R5 alone. In R1-R4 the ratios are near 1 with high P and R, which is what
the header says a recaller would show; it is also what a good annotator would show. So for 4 of 5
movements this check is uninformative about exposure; it does not argue against it. DCML's
Romantic labels predate the cutoff. Only post-cutoff labels would exclude exposure.

**Recognition.** 0 of 10 strings name a piece or composer; `recognition.json` (all "none", two
borderline hand-back guesses) matches the strings and hand-backs exactly. The two guesses (A/R2
"Beethoven, perhaps a bagatelle"; B/R5 "late-Beethoven-style markings") are wrong-composer, not
half-recognitions. Träumerei unnamed in both runs is plausible but not proven: the rendering is
untransposed (F major, the melody C4 | F4 ... E4 F4 A4 C5 F5 in bars 1-3), and naming rates in
R-08a/b on undisguised Mozart were 2-4 of 5 per run, so 0 of 10 here is lower than before. One
difference is that these instructions give no period cue. Thinking is redacted, so silent
recognition cannot be excluded (self-report is a lower bound). R3's 1.000 / 0.875 does not by
itself suggest recall: its 4-bar phrases with HC/PAC ends are textbook, and both runs describe the
form without any title cue.

**What a fragile GO licenses.** For the lead's decision:

- Supported: on Romantic character pieces in simple meters (one piece each by Tchaikovsky,
  Chopin, Schumann, Grieg, Liszt), the annotator's mean end F1 against DCML is at the 0.70 bar by
  the registered point-estimate rule, and it beats the F-05c detector by a clear margin on every
  piece. Recall of DCML phrase ends is high (cadenced about 0.9); the main error is level
  (finer phrases than DCML) on sparsely labelled pieces.
- Not supported: that the mean is above 0.70 (p 0.37; worst run below the bar; one movement
  decides it), any per-composer claim (one piece each), compound meters, mazurkas beyond one
  short T1 piece, transcribed MIDI, or long Chopin forms (ballades, sonatas).
- Downstream (H4 / R-09): a consumer that uses phrase boundaries must tolerate over-segmentation
  (for example, a per-phrase measure that is stable when a phrase is split in two), or it should
  check the phrase level per piece. A consumer that needs DCML's exact level is not licensed.

### Required fixes (text only; the verdict does not depend on them)

1. Add a `## Results` section to this README (the summary lives only in `artifacts/`): the
   per-movement table, primary with both intervals, paired test, the near-the-bar numbers, run-to-
   run, sensitivities, cadenced/uncadenced split, granularity, recognition.
2. In Results, state that the observed between-movement SD (0.241) was nearly twice the 0.13
   assumed in "Can each branch be reached?", so the interval is uninformative.
3. Describe R5 as "granularity (the extras) plus two placement disagreements at bars 59 and 108
   (the misses)", not as a granularity mismatch only, and say that ±1 bar gives the same R5 score.
4. State that the granularity check argues against label recall on R5 only; in R1-R4 it is
   uninformative.
5. Header status line: leave it (hash); the audited status is recorded here and in
   `EXPERIMENTS.md`.
