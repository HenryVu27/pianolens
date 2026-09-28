# R-08a: can an LLM reading the score find phrase ends and cadences? (pilot)
Ticket: R-08a    Hypothesis: gate for R-08 (Phase 7; feeds H4 / R-09 phrase boundaries)    Status: Provisional (pre-registered 2026-09-28; annotation not yet run)

Prepared by `ml-researcher`. The annotator is a separate, blind agent (see "Blinding"). Nothing
in this header may be edited after the annotation is produced. Corrections go in new sections at
the end.

## Question

Can an LLM that reads a compact, label-free text rendering of the score mark phrase ends (and
their cadence types) on held-out Batik-plays-Mozart movements better than the F-05c cadence
detector? The main target is half cadences, where the detector fails (HC recall 32% on the 21
held-out movements, F-05c).

## Go bar and falsification

- **Primary metric:** phrase-end F1 at ±1 beat, mean over the 5 pilot movements (the F-05c
  convention: one beat = the time signature's denominator, as in partitura; one-to-one matching,
  closest pairs first; see "Metrics").
- **Go for a full R-08:** primary F1 ≥ 0.70.
- **No-go (R-08 dropped in its current form):** primary F1 < 0.70. This includes the case where
  the LLM beats the detector but stays below 0.70.
- **Beats the detector** (reported, not the go bar): the mean paired per-movement difference
  (LLM − detector) in primary F1 is > 0 and its 95% bootstrap CI over movements excludes 0. With
  5 movements this CI is wide. A difference whose CI includes 0 is reported as "not shown".
- **Half cadences:** HC recall at ±1 beat, pooled over the 5 movements, against the detector's
  pooled HC recall on the same movements. Reported as a secondary result; no separate bar.
- The 0.70 bar was set in `WORKBOARD.md` (R-08a) and `DECISIONS.md` (2026-09-28, after D-11 /
  F-05c) before this pre-registration. It is copied, not changed.

## Data

- Batik-plays-Mozart (`DATASETS.md`), DCML phrase and cadence annotations mapped by note id onto
  the D-11 performed score (`pianolens.data.batik_mozart.performed_score`, MusicXML
  `scores_edited`, unfolded to the pianist's repeat path; `phrase_annotations`).
- Ground truth per movement: phrase starts (`{`, `}{`), phrase ends (`}`, `}{`; placed on the
  cadential arrival), cadences (PAC, IAC, HC, EC, DC), all as performed-score onset beats.
- Only the F-05c held-out set (the 21 movements outside K.279-K.283) is eligible. The detector's
  weights and settings were fitted on K.279-K.283, so every pilot movement is held out for it.

## Movement selection (fixed before any annotation exists)

1. **Exclusions (by length, before the draw):** kv284_3 (4,661 onsets) and kv331_1 (3,475) are
   both theme-and-variations movements whose renderings would be far larger than the others. 19
   movements remain. No other exclusion.
2. **Strata** (by movement position and time signature read from the MusicXML; no F-05c result
   was looked at per movement):
   - S1 middle movements (`_2`, the slow or minuet movements): kv284_2, kv330_2, kv331_2,
     kv332_2, kv333_2, kv457_2, kv533_2.
   - S2 first movements in 4/4: kv284_1, kv333_1, kv457_1.
   - S3 first movements in 2/4, 3/4 or 2/2: kv330_1 (2/4), kv332_1 (3/4), kv533_1 (2/2).
   - S4 finales in 2/4 or 2/2: kv330_3, kv331_3, kv333_3, kv533_3.
   - S5 finales in 3/4 or 6/8: kv332_3 (6/8), kv457_3 (3/4).
3. **Draw:** one movement per stratum, `numpy.random.default_rng(20260928)`, strata in the
   order S1..S5, each stratum's list sorted, `rng.choice(len(stratum))`. Code: `draw.py`
   (writes `artifacts/selection.json`). The result is appended below under "Selection outcome",
   unchanged by anything that follows.

## Rendering (the annotator's only input)

`render.py` writes one text file per movement to `blind_input/<id>.txt`, where `<id>` is an
opaque label (`M1`..`M5`, in draw order); the mapping to movements is in
`artifacts/selection.json` only. The rendering is built from the performed score's partitura
part, using only these object types: notes (pitch spelling, onset, duration, staff, grace),
rests (by staff), time signatures, key signatures, loudness directions (dynamics, cresc./dim.
words, sf/fp), tempo directions and words (e.g. Allegro, calando), fermatas, and barlines.
Per performed bar: the running bar number, the written bar number, time and key signature
(when they change), markings, and per onset (beat position in bar) the new notes of each staff
with durations in beats, rests, fermatas and the lowest sounding pitch (bass). A bar that
repeats an earlier bar note for note (same written bar, same content) is printed as a pointer
("same as bar k"). Excluded on purpose:

- the MusicXML `<harmony>` elements: they carry the DCML harmony, cadence and phrase labels
  (e.g. `.F.V{`), so they are **label leakage** and never read;
- slurs (Mozart's slurs are articulation-level and the task spec lists no slurs; a variant with
  slurs is not part of this pilot), beams, clefs, performance data (MusicXML `dynamics=`
  attributes on notes);
- the movement's title, catalogue number and any text that would identify the piece. Tempo
  words are kept, because a reader of the score sees them; a word that names the piece (e.g.
  "Köchel-Verzeichnis") is dropped.

A leakage check (`render.py --check`) greps every rendering for the annotation vocabulary
(PAC, IAC, HC, EC, DC, cadence, phrase, `{`, `}`, Roman-numeral chord labels such as `V7`,
`I64`, `viio`, the DCML label strings of the movement's `harmony` CSV) and fails on any hit.

## Blinding protocol

- The annotator is a fresh agent that receives only the files in `blind_input/`
  (`INSTRUCTIONS.md`, `SCHEMA.json`, `M1.txt`..`M5.txt`). The lead copies that folder to a
  directory outside the repo and starts the annotator there.
- The annotator must not read anything else: not this README, not `artifacts/`, not
  `data/raw/batik_mozart` (the annotation CSVs **and the MusicXML**, which embeds the labels),
  not `docs/`, `DECISIONS.md`, `WORKBOARD.md`, agent memories or the source code. It must not
  use web search (the DCML Mozart sonata annotations are public).
- The movement identity is hidden (opaque ids, no title or catalogue number). The annotator may
  still recognise the piece from the notes; this is a known limit (see "Threats"), and it is
  asked to state whether it recognised a piece. Recognition does not give access to the DCML
  labels.
- One pass, no feedback, no retries after scoring. If a run fails for a technical reason
  (malformed JSON, truncated output), the annotator may be rerun on that movement only, before
  anything is scored, and the rerun is disclosed.
- The annotator's JSON is saved verbatim to `annotations/<id>.json` before scoring.
- The worked example in `INSTRUCTIONS.md` uses positions checked to be more than 1 beat from
  every DCML phrase end and start of all five movements. (A first draft's example happened to
  sit on an M1 phrase end; it was replaced before any annotator existed.)

## Annotation schema

`blind_input/SCHEMA.json`: per movement a JSON object `{"movement": "M1", "recognised_piece":
str|null, "notes": str, "events": [{"bar": int, "beat": number|string, "type":
"phrase_end"|"phrase_start"|"cadence", "cadence": "PAC"|"IAC"|"HC"|"EC"|"DC"|"none",
"confidence": 0..1}]}`. `bar` is the running bar number of the rendering; `beat` is the beat
position as printed (e.g. `2`, `"2+1/2"`, `2.5`). `cadence` gives the type on `phrase_end` and
`cadence` events; it is ignored on `phrase_start`.

The `cadence` event type (a cadence that does not end a phrase) extends the ticket's schema.
Reason: DCML places many cadences away from phrase ends. On the training movements K.279-K.283
(not the pilot set), the share of DCML cadences that sit exactly on a phrase end is PAC
168/198, HC 71/139, EC 20/38, IAC 9/12, DC 0/23. Deceptive and evaded cadences usually extend
the phrase, which is standard (textbook) cadence theory, so the instructions say so in general
terms. Without this event type an annotator could not express those cadences. The primary
metric uses `phrase_end` events only, so this does not touch the go bar.

## Metrics (score.py)

Mapping of an event onto the performed score:

1. `(bar, beat)` → performed-score beat through the rendering's bar table (bar start beat plus
   the printed beat offset; the anacrusis bar is right-aligned exactly as printed).
2. Snap to the nearest score onset within ±0.5 beat; otherwise keep the raw beat. (The DCML
   labels and the detector's ends all lie on onsets.) Sensitivity: unsnapped.
3. Events in a "same as bar k" pointer bar are kept as given. In addition, every event in a
   printed bar k is copied to each pointer bar that repeats k (the annotator cannot place
   events inside a pointer bar it cannot see). Duplicates at the same beat are merged.
4. Events outside the movement or with an unparseable beat are dropped and counted.
5. Onset beats are float32 in the score arrays; differences below 1e-4 beat are rounding and are
   not counted as snapping.

Then, per movement, with `boundary_prf` from `scripts/check_phrase_f05b.py` (one-to-one,
closest pairs first; first onset excluded for starts, as in F-05c):

- **Primary:** phrase-end P / R / F1 at ±1 beat.
- End F1 at ±1 bar; start F1 at ±1 beat and ±1 bar.
- DCML cadence recall by type at ±1 beat, two ways:
  (a) `llm`: the share of DCML cadences of each type matched by a predicted **phrase end**
  (type-agnostic matching, exactly as F-05c computes it for the detector; this is the
  comparison with the detector). HC recall (a) is the key secondary.
  (b) `llm+cad_marks`: matched by any predicted cadence mark (phrase ends with a type other
  than `none`, plus `cadence` events). LLM only.
  The DCML phrase ends themselves (`oracle_dcml_ends`) bound (a): even perfect phrase ends
  recover only part of the DCML cadences (see Comparators).
- Cadence-type agreement: among DCML cadences matched at ±1 beat by an LLM end (a) or mark
  (b), the confusion table of LLM type vs DCML type, and the per-type accuracy.
- Confidence: end F1 when only events with confidence ≥ 0.5 are kept (descriptive).

Aggregation: the mean over the 5 movements (primary, as F-05c) and pooled counts. 95% CIs by a
bootstrap over movements (10,000 resamples, seed 20260928). Paired LLM − detector per
movement, with the same bootstrap.

## Comparators (same 5 movements, computed now, before the annotation)

- `cadence`: the F-05c detector (`pianolens.features.cadence`, shipped `CadenceConfig()`
  defaults), ends and starts.
- `proxy_last_onset` (ends) and `proxy` (starts): the F-05 proxy, as in F-05c.
- `grid4`: every 4th downbeat (ends from the 4th, starts from the 1st).
- `oracle_dcml_ends`: the DCML phrase ends and starts themselves. F1 is 1 by construction; its
  cadence-type recall is the ceiling of recall (a).
- Harness check: the detector's ends are converted to `(bar, beat)` through the bar table and
  scored by `score.py`. They must reproduce F-05c's per-movement rows in
  `data/interim/phrase_f05c/boundaries.csv` exactly (propagation step 3 off for this check,
  since the detector sees every performed bar).

## Method

1. `draw.py` → `artifacts/selection.json`.
2. `render.py` → `blind_input/M*.txt`, `artifacts/bars_M*.csv` (bar tables),
   `artifacts/ground_truth/M*.json` (hidden DCML ends, starts, cadences), leakage check.
3. `blind_input/INSTRUCTIONS.md`, `blind_input/SCHEMA.json` (written by hand, musically
   neutral).
4. `score.py --comparators` → `artifacts/comparators.csv`, `artifacts/comparators_summary.txt`
   and the harness check.
5. (Later, lead) run the blind annotator; save `annotations/M*.json`.
6. `score.py --llm annotations/` → `artifacts/llm_scores.csv`, summary appended to this README.

## Command

```
uv run python experiments/2026-09-28-R-08a-llm-phrase-pilot/draw.py
uv run python experiments/2026-09-28-R-08a-llm-phrase-pilot/render.py
uv run python experiments/2026-09-28-R-08a-llm-phrase-pilot/render.py --check
uv run python experiments/2026-09-28-R-08a-llm-phrase-pilot/score.py --comparators
uv run python experiments/2026-09-28-R-08a-llm-phrase-pilot/score.py --llm experiments/2026-09-28-R-08a-llm-phrase-pilot/annotations
```

Seeds: draw 20260928, bootstrap 20260928. Code state: uncommitted (the repo has no commits);
the sha256 of the four scripts is recorded under "Run record".

## Threats to validity (known before running)

- n = 5 movements, one composer, one annotation standard (DCML). The DCML reading is one
  analyst's; disagreements with it are not all errors.
- The LLM may know these sonatas (they are famous) and may recall published analyses. Blinding
  hides ids and labels, not the music.
- ±1 beat depends on the meter (2/2: a half note; 6/8: an eighth), as in F-05c.
- The rendering choices (no slurs, pointer bars) shape what the annotator can see.
- The annotator is Claude in-session, one pass; its variance across runs is not measured.

## Selection outcome (draw.py, seed 20260928, run 2026-09-28 before any rendering or annotation)

| Id | Movement | Stratum | Time signature |
|---|---|---|---|
| M1 | kv330_2 | S1 middle | 3/4 |
| M2 | kv333_1 | S2 first, 4/4 | 4/4 |
| M3 | kv533_1 | S3 first, other | 2/2 |
| M4 | kv330_3 | S4 finale, duple | 2/4 |
| M5 | kv457_3 | S5 finale, triple | 3/4 |

## Preparation record (2026-09-28, ml-researcher; no annotation exists yet)

Everything above this section is the pre-registration. Its sha256 (the file up to, not
including, the line `## Preparation record`) is given at the end of this section.

### Renderings (`blind_input/`)

| Id | Performed bars | Bars printed as repeats | Characters | Lines | Words | Tokens (rough, chars / 3) |
|---|---|---|---|---|---|---|
| M1 | 110 | 39 | 22,992 | 577 | 5,440 | ~7.7k |
| M2 | 231 | 63 | 75,037 | 2,051 | 17,749 | ~25k |
| M3 | 344 | 97 | 88,116 | 2,483 | 20,758 | ~29k |
| M4 | 239 | 65 | 59,284 | 1,648 | 14,088 | ~20k |
| M5 | 320 | 0 | 61,587 | 1,717 | 14,892 | ~21k |

The token column is an estimate (no tokenizer was run). Leakage check (`render.py --check`):
PASSED. No banned word, no Roman-numeral token, and none of the movement's DCML label strings
(55-135 distinct strings per movement from the harmony / cadence / phrase CSVs) occur in any
rendering, `INSTRUCTIONS.md` or `SCHEMA.json`. Checked that the check fires on planted
`V7`, `ii6`, `viio7/V`, `PAC`, `F.V{`, `phrase` and `It6`.

### Scoring harness

- **Detector reproduction: PASSED.** The detector's ends and starts, written as (bar, beat)
  events and scored through the annotator path, equal F-05c's per-movement rows (tp, n_pred,
  n_true, F1) for all 5 movements, all targets (end, start, DCML cadence) at ±1 beat and ±1 bar,
  and all per-type rows. Output in `artifacts/comparators_summary.txt`.
- **Oracle check.** The DCML ends and starts written as events: F1 1.000 for every variant.
  Written **only in printed bars** (the propagation path): still 1.000 for ends and starts at
  ±1 beat. So the pointer compression loses nothing, and the DCML labels are identical in the
  two passes of every repeated bar in these movements. With propagation off, the same input
  gives end F1 0.874 (the repeats' share).

### Comparators on the 5 pilot movements (mean over movements, 95% bootstrap CI over movements; pooled)

| Target | Tol | cadence (F-05c detector) | proxy (ends: last onset) | grid4 |
|---|---|---|---|---|
| end | ±1 beat | **0.565** [0.427, 0.754]; pooled 0.515 | 0.271 [0.168, 0.389]; 0.251 | 0.181 [0.123, 0.258]; 0.174 |
| end | ±1 bar | 0.687 [0.546, 0.823]; 0.677 | 0.467 [0.402, 0.542]; 0.450 | 0.513 [0.383, 0.602]; 0.496 |
| start | ±1 beat | 0.491 [0.352, 0.709]; 0.442 | 0.340 [0.306, 0.376]; 0.336 | 0.171 [0.107, 0.261]; 0.172 |
| start | ±1 bar | 0.610 [0.475, 0.779]; 0.571 | 0.516 [0.444, 0.595]; 0.496 | 0.410 [0.317, 0.504]; 0.391 |
| DCML cadence | ±1 beat | 0.588 [0.467, 0.759]; 0.541 | 0.298 [0.193, 0.412]; 0.286 | 0.180 [0.121, 0.267]; 0.180 |

Per-movement detector end F1 at ±1 beat: kv330_2 0.919, kv333_1 0.613, kv533_1 0.400,
kv330_3 0.456, kv457_3 0.439. The pilot set is easier for the detector than the 21 held-out
movements as a whole (0.565 vs 0.46), mostly because of kv330_2.

Recall of DCML cadences by type at ±1 beat (pooled over the 5 movements):

| Method | PAC | IAC | HC | EC | DC |
|---|---|---|---|---|---|
| cadence (detector) | 68/86 (0.79) | 6/13 (0.46) | **18/62 (0.29)** | 0/3 | 0/7 |
| proxy_last_onset | 33/86 (0.38) | 3/13 (0.23) | 29/62 (0.47) | 0/3 | 2/7 |
| grid4 | 22/86 (0.26) | 1/13 (0.08) | 18/62 (0.29) | 0/3 | 2/7 |
| oracle_dcml_ends (ceiling for phrase ends) | 80/86 (0.93) | 4/13 (0.31) | 38/62 (0.61) | 3/3 | 0/7 |

So on these movements, a perfect phrase-end annotator would find at most 61% of the HCs (and no
DC) by phrase ends alone. That is why recall (b) exists.

### Files and code state

- `blind_input/`: `INSTRUCTIONS.md`, `SCHEMA.json`, `M1.txt`..`M5.txt` (the only files the
  annotator gets).
- `artifacts/` (gitignored): `selection.json` (id -> movement), `bars_M*.csv`,
  `ground_truth/M*.json`, `render_sizes.csv`, `comparators.csv`, `comparators_summary.txt`,
  `oracle_full_*`, `oracle_printed_*` (harness checks).
- Code state: uncommitted (no commits in the repo). sha256: `draw.py` 1b7dc5ef...,
  `common.py` 272d81dd..., `render.py` 82785dc0..., `score.py` b73b1b7e...,
  `INSTRUCTIONS.md` 9c548117..., `SCHEMA.json` 98e36507..., `M1.txt` 21a13518...,
  `M2.txt` 7fb1cef4..., `M3.txt` 967e5a61..., `M4.txt` 726e925c..., `M5.txt` 5a950918...
- Data: Batik-plays-Mozart as in `DATASETS.md`; F-05c cache `data/interim/phrase_f05c/cands.pkl`
  and `boundaries.csv` (2026-09-27 run). Wall time: rendering 16 s, comparators 4 s.
- Pre-registration sha256 (README up to `## Preparation record`): `45b24f8dfc3ad5d2c0ca3e48b2b7e2c7163197fa2d60006a6aba0b3caa800724`.

## Audit (2026-09-28, eval-auditor)

**Verdict: Confirmed with caveats. GO for a full R-08 by the pre-registered rule, qualified:
the evidence is for famous Mozart sonatas that the annotator recognised in 4 of 5 cases, and
the first step of R-08 must be a memorisation control (below).**

Audited: pre-registration, draw, blinding (transcripts), the scoring code and its outputs, the
paired test, propagation, tolerance, and the n = 5 inference. Audit scripts live in the session
scratchpad (`r08a_audit/audit.py`); nothing in `src/` or the experiment scripts was changed.

### 1. Pre-registration and inputs: intact

- README up to `## Preparation record` hashes to `45b24f8d...0724`, as recorded. The go bar
  (mean end F1 at ±1 beat ≥ 0.70, point estimate), the primary metric and the paired
  "beats the detector" test are unchanged.
- The sha256 of `draw.py`, `common.py`, `render.py`, `score.py`, `INSTRUCTIONS.md`,
  `SCHEMA.json` and `M1.txt`..`M5.txt` match the Preparation record. The copies in the scratchpad
  folder the annotators used (`r08a_blind/`) are byte-identical to `blind_input/`.
- The draw reproduces (seed 20260928): kv330_2, kv333_1, kv533_1, kv330_3, kv457_3.
- None of the renderings or `INSTRUCTIONS.md` contains "Mozart", "Köchel" or a "K. nnn"
  catalogue number.

### 2. Blinding: clean, by transcript

I extracted every tool call from the five annotator transcripts (agent ids a33339eeb837e3fcb
M1, ad67de032c72956d2 M2, a2ca0f44e8ed94a9a M3, a2ed58304e4b5f5d9 M4, a0bd7a40c75aeb920 M5).

- Each annotator made the same calls: Read `INSTRUCTIONS.md`, Read `SCHEMA.json`, Read its own
  `M#.txt`, then one write to `r08a_blind/out/M#.json`, then its hand-back. For long files, the
  Read was split into 2 or 3 parts with offsets; together the parts cover the whole file.
- There were no Glob, Grep, WebSearch or WebFetch calls, and no reads of any other file. M1, M3
  and M5 wrote their JSON with a `python3` heredoc (json.dump to `out/M#.json`); M1 then read
  its own output back to count events. No Bash command touched any other path.
- M2 and M4 used Write. The written content equals the file on disk (compared as JSON).
- The annotators got no project instructions: the only instruction file loaded was the user's
  global CLAUDE.md. Their environment block did show the working directory
  `/Users/vuducdung/personal/pianolens`. That is a project name only, not labels or a piece.
- The lead's prompt names only the blind folder and the three files. It does not say composer,
  corpus or piece.
- No other agent's tool calls touched `r08a_blind/`. Only the five annotators and this audit
  did.
- Enforcement was by instruction, not by sandbox (disclosed in DECISIONS). The transcripts show
  that the instruction was followed.

Deviation found: the pre-registration says the annotations are "saved verbatim to
`annotations/<id>.json` before scoring". They were scored from the scratchpad, which is
temporary. The auditor copied them verbatim to `annotations/` (sha256 M1 6677a0d6..., M2
3ebb07d9..., M3 8fbcde90..., M4 77b62afc..., M5 bbe19d08...). They were not changed.

### 3. Reproduction and the paired test

- `score.py --llm` rerun on the saved annotations, into a scratch copy of `artifacts/`:
  `llm_summary.txt` is byte-identical and `llm_scores.csv` is equal.
- The pre-registered paired test **is** in the `score.py` output (the last lines of
  `llm_summary.txt`). LLM − detector = **+0.252 [+0.118, +0.382]**, so "beats the detector" is
  **shown**. The LLM is ahead on all 5 movements: kv330_2 +0.033, kv333_1 +0.170, kv533_1
  +0.473, kv330_3 +0.321, kv457_3 +0.261. An exact sign test gives one-sided p = 1/32.

### 4. Scoring correctness

- **Propagation is pre-registered** (Metrics step 3, inside the hashed header). The annotator
  was told about it (INSTRUCTIONS "Repeated bars"). It is not a post-hoc choice.
- **`llm_no_propagation` (0.720) is not a fair sensitivity.** The annotator was told not to
  annotate pointer bars, but that row still keeps the ground truth in those bars. Its lower
  recall is built in: the oracle written only in printed bars drops to 0.874 the same way.
  The fair check counts each repeated passage once: drop the pointer bars from both the
  predictions and the ground truth. That gives LLM **0.822 [0.749, 0.899]** and detector
  0.579; paired +0.243 [0.124, 0.353]. So propagation does not inflate the result.
- **The detector is not disadvantaged.** Its headline 0.565 is scored from its own beats, which
  cover every performed bar. Fed through the event path with propagation on, it scores 0.565.
  Its events written in printed bars only and then propagated also give 0.565. The detector
  makes the same calls in both passes of every repeat, so propagation cannot change its score.
  The harness check (propagation off, equal to F-05c) is in `comparators_summary.txt`.
- **Snapping has no effect:** `llm_unsnapped` equals `llm`, because every LLM event already
  sits on an onset. No events were dropped as unparseable or out of range (mapping stats).
- **Tolerance.** The ±1 beat window is widest in 2/2 (a half note, kv533_1). Mean LLM F1 is:
  - 0.810 at ±1 quarter note in every meter;
  - **0.793 [0.713, 0.884] for exact onset matches (±0)**;
  - 0.793 at ±0.5 beat.

  The detector scores 0.565 / 0.560 / 0.560 on the same three checks. The go holds even at
  exact onsets.
- **Density null.** Two checks show the LLM ends are not just dense enough to hit by chance:
  - the same LLM ends shifted by ±1 or ±2 bars: F1 0.046;
  - the same number of ends placed on random onsets: F1 0.117 (200 draws).
- **Precision and recall.** The LLM over-segments a little: pooled P 0.741, R 0.903, with
  39-52 predicted ends against 30-33 true ones in kv333_1 and kv330_3. Recall is the gain. On
  kv533_1 the LLM gets 48/57 true ends, the detector 23/57.
- **Per-type recall.**
  - HC: LLM 35/62, detector 18/62. By movement, the LLM equals the oracle's HC count on 4 of 5
    movements (kv330_2 8 vs 8, kv330_3 8 vs 8, kv333_1 7 vs 7, kv457_3 5 vs 5); on kv533_1 it
    is 7 vs 10. All 35 matched HCs are also
    typed HC.
  - Caution on the "oracle ceiling". `oracle_dcml_ends` bounds recall (a) only for an
    annotator that puts ends where DCML does. The LLM puts ends at cadences that DCML does not
    treat as phrase ends. IAC shows this: LLM 13/13, oracle 4/13. So 38/62 is a reference
    point for HC, not a hard ceiling.
  - DC: 0/7 by phrase ends. With `cadence` marks it is 7/7, and 5 of the 7 are typed DC.
  - EC: 3/3, but all 3 are typed PAC.

### 5. Memorisation: not excluded; the verdict is qualified

- Four annotators named the piece correctly (K. 333/i, K. 533/i, K. 330/iii "tentative",
  K. 457/iii). M1 (K. 330/ii) was described as a "Minuet in F" and not recognised.
- **"The unrecognised movement scored highest" is weak evidence against recall.** kv330_2 is the
  easiest movement for every method: the detector scores 0.919 there, and the LLM's gain is only
  +0.033. The LLM's large gains (+0.17 to +0.47) are all on recognised movements. On the
  recognised four alone, mean LLM F1 is 0.783 (0.786 counting each repeat once). That is still
  above 0.70, but it tests nothing about recall.
- **What recall could mean.** The DCML Mozart sonata annotations are public
  (TSV/MuseScore on GitHub), and so are many textbook and Caplin-style analyses of these
  sonatas. Reproducing DCML's exact onset positions for 30-57 phrase ends per movement from
  memory seems unlikely. But familiarity with a piece's form (where the half cadences, medial
  caesuras and closing sections fall) can guide attention without verbatim recall. The
  annotators' notes are written as reasoning from the rendering and cite no source.
  Transcripts cannot show whether knowledge was used.
- **Required control (the first pre-registered step of R-08, before any API spend):**
  1. *Disguised rerun on the same movements.* Transpose by a non-trivial interval (e.g. +3
     semitones, respelled). Drop all tempo words and dynamics. Start bar numbers at an offset.
     Present the movements in a fresh order. Ask for recognition as before. If recognition
     drops and F1 stays within about 0.05 of this run, memorisation is not what drives it. If
     recognition persists, go to (2).
  2. *Unfamiliar repertoire in the same annotation standard.* Use Classical-era keyboard
     movements the model is unlikely to know by heart, with DCML-style phrase and cadence
     labels. Candidates to be checked by data-engineer / lit-scout: DCML corpora of lesser
     composers, such as Koželuch or J. C. Bach sonatas, if they exist with phrase labels. Use
     the same go bar, and compare against the F-05c detector on the same movements.
  3. *Run-to-run variance.* Rerun 2-3 annotators per movement. The pre-registration lists
     single-pass variance as unmeasured.
- Until (1) or (2) is run, the claim reads: "on recognised famous Mozart sonatas, an in-session
  Claude annotator marks DCML phrase ends at F1 0.82". It does not yet read: "an LLM can read
  phrase structure from an unfamiliar score".

### 6. Does n = 5 support "go"?

- By the rule, yes. The bar is on the point estimate: 0.817 ≥ 0.70. Several other readings also
  clear it:
  - every leave-one-out mean is ≥ 0.783;
  - the lowest single movement is exactly 0.700 (kv457_3, 21/35 predicted, 21/25 true);
  - the exact-onset mean is 0.793;
  - the paired difference is shown.
- **The CI [0.747, 0.901] is optimistic.** With 5 units, the percentile bootstrap understates
  the width. A t-interval on the same 5 values is [0.696, 0.938], and its lower end touches
  the bar. The honest reading: the point estimate is clearly above 0.70, and the lower bound
  is at the bar. The pre-registration makes the go depend on the point estimate, so the go
  stands. But "CI above 0.70" should not be claimed.
- **The set is not representative.** It is one composer, one annotation standard and five
  movements. The pilot set is easier for the detector than the 21 held-out movements (0.565 vs
  0.46), mostly because of kv330_2. The LLM's margin is largest where the detector is weakest,
  which is encouraging, but the full R-08 must use more movements.

### Required fixes (text; none changes the verdict)

1. Append the Results / run record (method step 6): annotation times, agent ids, the protocol
   deviation (5 agents), the `llm_summary.txt` headline and the paired test. The header's
   Status line stays as registered; put the status in the Verdict.
2. Describe `llm_no_propagation` as a construction check, not a sensitivity, and report the
   printed-bars-only scoring (0.822 vs 0.579) in its place.
3. Do not call `oracle_dcml_ends` a strict ceiling for LLM cadence recall (see IAC 13/13 vs
   4/13).
4. Record the memorisation qualification and the control in the Verdict and in DECISIONS
   before R-08 is scoped.
5. Keep `annotations/` (copied by the auditor), since the scratchpad is temporary.

## Post-audit corrections (2026-09-28, ml-researcher, ticket R-08b)

This section applies the text fixes the audit requires. The pre-registered header (above
`## Preparation record`) is unchanged and still hashes to `45b24f8d...0724`. The header's
Status line stays as registered; the audited status is in "Verdict" below.

### Results and run record (method step 6)

- **Annotators.** Five independent in-session agents (model `claude-opus-5-5`,
  general-purpose, background, non-interactive), one movement each. Agent ids and transcript
  time spans (UTC, 2026-09-28): M1 a33339eeb837e3fcb 04:14:58-04:16:13; M2 ad67de032c72956d2
  04:14:58-04:18:24; M3 a2ca0f44e8ed94a9a 04:14:58-04:19:18; M4 a2ed58304e4b5f5d9
  04:14:58-04:18:45; M5 a0bd7a40c75aeb920 04:14:58-04:17:44.
- **Protocol deviation (disclosed in DECISIONS 2026-09-28).** The pre-registration planned one
  annotator reading all five files. The lead ran five annotators, one per movement, each told
  to annotate only its own file. `INSTRUCTIONS.md` still says "five files".
- **Input copy.** The annotators read a copy of `blind_input/` outside the repo (session
  scratchpad `r08a_blind/`), byte-identical to `blind_input/` (audit, section 1).
- **Saved annotations.** `annotations/M*.json` (copied verbatim by the auditor; sha256 M1
  6677a0d6..., M2 3ebb07d9..., M3 8fbcde90..., M4 77b62afc..., M5 bbe19d08...). No rerun, no
  retry, no technical failure.
- **Command.** `uv run python experiments/2026-09-28-R-08a-llm-phrase-pilot/score.py --llm
  <annotations dir>` → `artifacts/llm_scores.csv`, `artifacts/llm_summary.txt`. The auditor's
  rerun from `annotations/` gives a byte-identical summary.
- **Headline (`llm_summary.txt`).** Primary phrase-end F1 at ±1 beat, mean over the 5
  movements: **LLM 0.817**, percentile bootstrap CI [0.747, 0.901], **t-interval (4 df)
  [0.696, 0.938]**; pooled P / R / F1 0.741 / 0.903 / 0.814. Detector 0.565 on the same
  movements. Per movement (LLM / detector): kv330_2 0.952 / 0.919, kv333_1 0.783 / 0.613,
  kv533_1 0.873 / 0.400, kv330_3 0.776 / 0.456, kv457_3 0.700 / 0.439.
- **Paired test (pre-registered).** LLM − detector = **+0.252**, bootstrap [+0.118, +0.382],
  t-interval [+0.047, +0.456]. Both exclude 0, so "beats the detector" is shown. The LLM is
  ahead on all 5 movements.
- **Half cadences (secondary).** HC recall via phrase ends at ±1 beat: LLM 35/62 (0.56),
  detector 18/62 (0.29). With `cadence` marks: 38/62.
- **recognised_piece.** M1 null; M2, M3, M4 (tentative), M5 named the piece correctly.

### Interval: use the t-interval

With 5 movements the percentile bootstrap is optimistic. The t-interval on the same 5 values
is [0.696, 0.938]; its lower end touches the 0.70 bar. The go rests on the point estimate, as
pre-registered. "The CI lies above 0.70" is **not** claimed.

### `llm_no_propagation` is a construction check, not a sensitivity

The annotator was told not to annotate pointer bars ("same notes and markings as ..."), and
that variant keeps the ground truth in those bars. Its lower score (0.720) is built in: the
DCML oracle written only in printed bars drops to 0.874 in the same way. The fair check counts
each repeated passage once (pointer bars dropped from both prediction and truth). The auditor
measured it: LLM **0.822** [0.749, 0.899], detector **0.579**, paired +0.243 [0.124, 0.353]. So
propagation does not inflate the result. Read the `llm_no_propagation` rows in
`llm_summary.txt` as a check that the propagation path is active, nothing more.

### `oracle_dcml_ends` is not a strict ceiling for cadence recall

The Preparation record calls the oracle's cadence recall a "ceiling" for recall (a). That
holds only for an annotator that puts its phrase ends where DCML does. The LLM also places
ends at cadences that DCML does not treat as phrase ends: IAC recall is LLM 13/13 vs oracle
4/13. So the oracle's HC 38/62 is a reference point for HC recall, not a bound on it.

### Verdict

**Confirmed with caveats (eval-auditor, 2026-09-28). GO for a full R-08 by the pre-registered
rule, conditional on the memorisation control R-08b.** The evidence is for famous Mozart
sonatas; the annotator recognised 4 of 5. All large gains over the detector are on recognised
movements, and the unrecognised one (kv330_2) is the easiest for every method. Until R-08b is
run, the claim reads: "on recognised famous Mozart sonatas, an in-session Claude annotator
marks DCML phrase ends at F1 0.82". It does not yet read: "an LLM can read phrase structure
from an unfamiliar score". LLM phrase boundaries feed tempo coherence only if R-08b passes
(DECISIONS 2026-09-28).
