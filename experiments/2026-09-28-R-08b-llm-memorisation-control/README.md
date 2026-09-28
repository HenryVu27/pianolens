# R-08b: does the LLM phrase annotator still work when it cannot recognise the piece? (memorisation control)
Ticket: R-08b    Hypothesis: gate for R-08 (Phase 7; feeds H4 / R-09 phrase boundaries)    Status: Provisional (pre-registered 2026-09-28; no annotation exists yet)

Prepared by `ml-researcher`. The annotators are separate, blind agents run by the lead. Nothing
in this header may be edited after any annotation is produced. Corrections go in new sections at
the end.

## Question

R-08a found that an in-session Claude annotator marks DCML phrase ends on 5 held-out Batik Mozart
movements at mean end F1 0.817 (±1 beat), against 0.565 for the F-05c cadence detector (audited:
Confirmed with caveats). But the annotator named the piece in 4 of 5 movements, and every large
gain was on a recognised movement. Two questions:

1. **Memorisation.** Does the annotator keep that level when the same movements are disguised so
   that it is harder to recognise them (transposed and respelled, no tempo words or dynamics, bar
   numbers offset, fresh ids and order)?
2. **Run-to-run variance.** How much does end F1 move between independent undisguised runs of the
   same movement? R-08a had one run per movement.

## Pass rule (fixed in `WORKBOARD.md` R-08b before this pre-registration; copied, not changed)

- **A** = disguised end F1 at ±1 beat (R-08a's primary metric), mean over the 5 movements.
- **U** = undisguised end F1 at ±1 beat. Per movement, U is the mean over every undisguised run:
  the R-08a run plus the 2 condition B reruns (3 runs). If a B rerun is missing for a technical
  reason after one retry, U uses the runs that exist, and this is disclosed.
- **Pass:** mean A ≥ 0.70 **and** mean(A − U) ≥ −0.10 (paired per movement). Both are on point
  estimates, as in R-08a.
- **Fail:** either condition fails.
- Reported next to the rule, not part of it:
  - for mean A and for mean(A − U): the percentile bootstrap 95% CI over movements (10,000
    resamples, seed 20260929) **and** the t-interval (4 df), because n = 5 (R-08a audit lesson);
  - "non-inferiority at 0.10 shown" only if the t-interval of mean(A − U) lies entirely above
    −0.10; otherwise "point pass only";
  - margin sensitivity: the smallest margin m for which mean(A − U) ≥ −m holds, and the same for
    the lower ends of both intervals;
  - mean(A − R08a), the difference to the single R-08a run, as a sensitivity;
  - A − detector, paired, with both intervals (the detector's input is not changed by the
    disguise, so its scores equal R-08a's).
- **Consequence (from DECISIONS 2026-09-28):** LLM phrase boundaries may feed tempo coherence only
  if R-08b passes. What happens after a fail is the lead's decision.

## Recognition (reported, and it changes how a pass is read)

Each annotation has `recognised_piece`. The lead or the auditor classifies every disguised
annotation, by reading the string only, as **correct** (names the right work, the movement may be
approximate), **wrong** (names another work) or **none** (null or no named work). Results are
broken down by this class, for A and for B.

- **Disguise effective:** at most 1 of the 5 disguised movements is recognised correctly.
- **Disguise partly effective:** 2 correct.
- **Disguise ineffective:** 3 or more correct. Then a pass does **not** exclude memorisation: the
  verdict reads "inconclusive on memorisation", and step 3 below (unfamiliar repertoire) becomes
  the required control. The pass rule is still computed and reported.
- Descriptive: mean A on the movements not correctly recognised, next to their U.

## Conditions

- **A (disguised).** One fresh annotator per movement (5 annotators), each given one disguised
  rendering `D#.txt` plus `INSTRUCTIONS.md` and `SCHEMA.json` from `blind_input_disguised/`.
- **B (undisguised reruns).** Two more fresh annotators per movement (10 annotators), each given
  one R-08a rendering `M#.txt` plus R-08a's `INSTRUCTIONS.md` and `SCHEMA.json`, unchanged, from
  R-08a's `blind_input/`. Runs are labelled B1 and B2.
- Same model and agent type as R-08a (in-session `claude-opus-5-5`, general-purpose, background).
  The lead records the model, agent ids and times for all 15.
- Each annotator is told only: the folder it may read, the one file it must annotate, and where to
  write the JSON. It is not told that the piece is disguised, transposed or famous, nor the
  composer or corpus.

## The disguise (condition A)

`disguise.py` renders the same D-11 performed scores with R-08a's own renderer (`common.py` of
R-08a, imported, not copied, so bar layout, onsets, durations, pointer bars and the bar table are
built by the same code). Only these things change:

1. **Transposition.** Each movement is transposed by a seeded random interval `s` drawn uniformly
   from {−6, …, −1, +1, …, +6} semitones (never 0 or an octave). Every MIDI pitch moves by `s`.
2. **Consistent respelling.** Each spelled pitch moves along the line of fifths by `k` fifths,
   with `7k ≡ s (mod 12)`. Of the two candidates (k in −6..5 and k − 12 or k + 12, whichever is in
   −11..11), the one that minimises the largest |fifths| of the movement's shifted key signatures
   is used (ties: the smaller |k|). Key signatures shift by the same `k`. The octave follows from
   the new MIDI pitch. So the whole movement is written in the new key, with the same relations
   between spellings.
3. **No words or dynamics.** All loudness directions (p, f, sf, fp, cresc., dim., …), tempo
   directions and free words (Allegro, dolce, calando, a piacere, …) are removed. Fermatas are kept
   (printed `FERMATA`; they carry structure and no identity), and so are double barlines.
4. **Bar numbers offset.** The running bar number and the numeric score bar number both get a
   seeded constant `c` from 20..479 added. Unnumbered score bars (`X1`, …) keep their labels.
5. **Fresh ids and order.** Movement ids D1..D5 by a seeded permutation, so D-order differs from
   M-order in general.
6. **Legend.** The legend drops the lines on markings and says bar numbers start at an arbitrary
   number. `INSTRUCTIONS.md` and `SCHEMA.json` are R-08a's, with only `M` → `D` in file names and
   ids (the worked example's bar numbers are kept; the example says its positions are made up).

Seeds: `numpy.random.default_rng(20260929)`. For M1..M5 in order: `s`, then `c`; after that the
permutation for the D ids. The draw is written to `artifacts/disguise.json` (id map, `s`, `k`,
`c`), which annotators never see. The values are recorded in the preparation record only as a
pointer to that file.

**Scoring maps back exactly.** The disguised bar table is R-08a's bar table with `bar` and the
numeric `written` shifted by `c`; onset beats are unchanged by transposition. So a disguised
(bar, beat) maps to the same performed-score beat as (bar − c, beat) in R-08a. Pointer bars are
parsed from the disguised rendering itself. Then R-08a's `map_events` and `score_movement` are used
unchanged against the same DCML ground truth.

## Leakage and harness checks (all must pass before any annotator runs)

`disguise.py --check`:

- R-08a's check on every `D#.txt`, `INSTRUCTIONS.md` and `SCHEMA.json`: banned annotation
  vocabulary, Roman-numeral tokens, and the movement's DCML label strings.
- **Extended identity check:** no composer name (Mozart, Wolfgang, Amadeus, Haydn, Beethoven,
  Clementi, Bach, Schubert, Koželuch, and others in the code), no Köchel / catalogue pattern (K.,
  KV, K 333, "Köchel"), no title or genre word (sonata, sonatina, rondo, menuetto / minuet,
  variation, movement names), no tempo or expression word (allegro, andante, adagio, presto,
  allegretto, andantino, moderato, assai, molto, cantabile, dolce, calando, a piacere, agitato,
  …), no dynamic token in brackets, no `[` marking at all, no original id `M1`..`M5`, no
  reference to Batik, DCML or the repo.
- **Transposition check:** every note token of every printed onset line equals the R-08a token at
  the same place, moved by `s` semitones (MIDI) with the letter name moved by the matching number
  of steps; the key signature line moved by `k`.
- **Structure check:** the disguised bar table equals R-08a's (start, end, shift, ts) with bar
  numbers shifted by `c`, and the pointer map equals R-08a's shifted by `c`.

`score.py --harness` (through the condition A path):

1. **Oracle:** the DCML phrase ends and starts written as disguised (bar, beat) events: end and
   start F1 = 1.000 at ±1 beat, every movement. Written only in printed bars and propagated:
   still 1.000.
2. **Detector:** the F-05c detector's ends and starts written as disguised events, propagation off:
   equal to F-05c's per-movement rows in `data/interim/phrase_f05c/boundaries.csv`.
3. **Replay:** R-08a's saved annotations, with bars shifted by `c` and ids renamed, scored as
   condition A: per-movement end F1 equal to R-08a's `llm` rows.
4. Condition B path: R-08a's saved annotations scored as a B run reproduce R-08a's `llm` rows.

## Metrics and analysis (`score.py`)

- Per run and movement: R-08a's rows (end / start / DCML cadence at ±1 beat and ±1 bar, cadence
  recall by type, type agreement, the confidence ≥ 0.5 variant), same mapping (snap ±0.5 beat,
  pointer propagation).
- **Primary:** the pass rule above.
- **Run-to-run variance (B):** per movement, the three undisguised F1 values (R-08a, B1, B2),
  their range and SD; the mean within-movement SD; the three run-level means. Whether each A
  value lies inside, above or below its movement's undisguised range.
- **Secondary:** HC recall via phrase ends at ±1 beat, pooled, for A, for U (each run) and for the
  detector (18/62). Exact-onset (±0) end F1 for A and U.
- **By recognition:** A and U by the recognition class, per movement and as group means.
- Everything is reported per movement (n = 5); no claim beyond these movements.

## Data

Batik-plays-Mozart (`DATASETS.md`), the same 5 movements, performed scores and DCML ground truth
as R-08a (`experiments/2026-09-28-R-08a-llm-phrase-pilot/artifacts/`: `selection.json`,
`bars_M*.csv`, `ground_truth/M*.json`), and the F-05c cache `data/interim/phrase_f05c/`.

## Blinding protocol (from R-08a, plus its audit lessons)

- The lead copies `blind_input_disguised/` (condition A) and R-08a's `blind_input/` (condition B)
  to folders **outside the repo** and gives each annotator only that path. Annotators never get a
  repo path.
- An annotator may read only its folder's three files. No web search, no other files. One pass,
  no feedback, no retry after scoring. A technical failure (malformed JSON, truncation) may be
  rerun once, before scoring, and is disclosed.
- **Each JSON is copied verbatim into this folder immediately** (`annotations_A/D#.json`,
  `annotations_B1/M#.json`, `annotations_B2/M#.json`), before scoring. Scratchpads do not persist.
- Transcripts are kept for the auditor's file-access check.
- A condition A annotator never sees an `M#.txt` and vice versa; every annotator is a fresh agent.

## Method

1. `disguise.py` → `artifacts/disguise.json`, `blind_input_disguised/D#.txt`, `INSTRUCTIONS.md`,
   `SCHEMA.json`, `artifacts/bars_D#.csv`; then `disguise.py --check`.
2. `score.py --harness`.
3. (Lead) run the 15 annotators; save the JSON files as above.
4. `score.py --llm-dir annotations_A --condition A`,
   `score.py --llm-dir annotations_B1 --condition B --run B1`,
   `score.py --llm-dir annotations_B2 --condition B --run B2`.
5. (Lead or auditor) fill `recognition.json` (class per annotation), then `score.py --compare` →
   `artifacts/r08b_summary.txt` with the pass rule, intervals, variance and recognition tables.
   Results are appended to this README.

## Command

```
uv run python experiments/2026-09-28-R-08b-llm-memorisation-control/disguise.py
uv run python experiments/2026-09-28-R-08b-llm-memorisation-control/disguise.py --check
uv run python experiments/2026-09-28-R-08b-llm-memorisation-control/score.py --harness
uv run python experiments/2026-09-28-R-08b-llm-memorisation-control/score.py --llm-dir experiments/2026-09-28-R-08b-llm-memorisation-control/annotations_A --condition A
uv run python experiments/2026-09-28-R-08b-llm-memorisation-control/score.py --llm-dir experiments/2026-09-28-R-08b-llm-memorisation-control/annotations_B1 --condition B --run B1
uv run python experiments/2026-09-28-R-08b-llm-memorisation-control/score.py --llm-dir experiments/2026-09-28-R-08b-llm-memorisation-control/annotations_B2 --condition B --run B2
uv run python experiments/2026-09-28-R-08b-llm-memorisation-control/score.py --compare
```

Seeds: disguise 20260929, bootstrap 20260929. Code state: uncommitted (the repo has no commits);
sha256 of the scripts and blind inputs go in the preparation record.

## Threats to validity (known before running)

- **The disguise hides the surface, not the music.** Rhythm, texture, bar count and the melodic
  contour are unchanged. A model that knows these sonatas well may still recognise them; that is
  what the recognition class measures. Transposition also moves pitch and register, which may make
  the reading harder for reasons other than memory (unusual keys, more accidentals). A drop under
  disguise is therefore not proof of memorisation; a hold is good evidence against it only when
  the disguise is effective.
- Tempo words and dynamics are removed. They carry phrase cues (e.g. a `p` at a new phrase,
  `calando` before a cadence), so condition A has less information than R-08a. That makes the
  test conservative for the annotator.
- n = 5 movements, one composer, one annotation standard. R-08a's movements are easier than the
  21 held-out ones for the detector.
- U has 3 runs per movement and A has 1, so A − U carries A's run noise. The B variance shows its
  size.
- R-08a's run is reused as one of the three undisguised runs; it was seen before this rule was
  written (0.817). The rule was set in `WORKBOARD.md` after that result, which is why the
  comparison is relative (A vs U), not only absolute.

## Preparation record (2026-09-28, ml-researcher; no annotation exists yet)

Everything above this section is the pre-registration. Its sha256 (the file up to, not including,
the line `## Preparation record`) is
`dfa87f4f283547c83994df4460551409259aea4fb9ac33e7e2ba8f712e45aa80`.

### Draw and renderings

- `disguise.py` ran once (seed 20260929). The id map, `s`, `k` and `c` per movement are in
  `artifacts/disguise.json` only. Every `s` is non-zero and not an octave; every `c` is in 20..479;
  the D order differs from the M order. No tie in the choice of `k` occurred.
- Sizes (`artifacts/render_sizes.csv`):

| Id | Performed bars | Pointer bars | Characters | Words |
|---|---|---|---|---|
| D1 | 320 | 0 | 61,809 | 14,634 |
| D2 | 239 | 65 | 60,402 | 13,951 |
| D3 | 344 | 97 | 88,670 | 20,652 |
| D4 | 110 | 39 | 23,730 | 5,305 |
| D5 | 231 | 63 | 77,206 | 17,691 |

- **Reading burden (disclosed, not changed).** The pre-registered `k` rule put D4 in a 7-sharp
  signature (a middle section in 4 sharps) and D5 in 5 sharps. The R-08a renderings have no double
  accidentals; the disguised ones have D1 9, D2 20, D3 0, D4 57 (4.0% of note tokens), D5 102
  (2.2%). This is part of the "transposition may make reading harder" threat. The draw was not
  repeated.
- **Wording change not listed in the header:** pointer lines read "same notes as bar(s) ..."
  instead of "same notes and markings as ...", because there are no markings. `INSTRUCTIONS.md`
  quotes the same wording. The scorer parses both forms.

### Checks (all PASSED)

- `disguise.py --check`: for D1..D5, no R-08a banned word, no Roman-numeral token, none of the
  movement's DCML label strings (55-135 per movement), no identity / tempo / dynamic / bracket /
  `M#` hit; bar table equal to R-08a's with bars shifted by `c`; pointer map equal to R-08a's
  shifted by `c` (0, 65, 97, 39, 63 pointer bars: the same as R-08a, so removing markings merged
  no bars); onset lines equal in number; every note token (1,413-5,384 per movement, 18,454 in
  all) moved by exactly `s` semitones and `k` fifths; key signatures moved by `k`. The only onset
  lines identical to R-08a's are rest-only lines (no note tokens). `INSTRUCTIONS.md` and
  `SCHEMA.json` pass the same checks. The identity check was shown to fire on planted `Mozart`,
  `K. 333`, `KV 457`, `Allegro`, `[p]`, ` f `, `Sonata`, `dolce`, `M2`, `V7`, `PAC`, `cresc.`.
- `score.py --harness` (`artifacts/harness.txt`), for all 5 movements through the condition A
  path: oracle end and start F1 1.000 (all bars, and printed bars plus propagation); the detector
  equals F-05c's rows (8-11 rows per movement, 0 mismatches); R-08a's annotations, bars shifted
  and ids renamed, reproduce R-08a's `llm` end F1 exactly (0.700, 0.776, 0.873, 0.952, 0.783)
  and every per-type cadence recall row. The condition B path reproduces R-08a's mean 0.817.
- End-to-end dry run of `--llm-dir` and `--compare` in a scratch folder (R-08a annotations as a
  stand-in for A and B1): all tables print; nothing was written to `artifacts/`.

### For the lead

- Condition A input: `blind_input_disguised/` (`INSTRUCTIONS.md`, `SCHEMA.json`, `D1.txt`..
  `D5.txt`). Condition B input: R-08a's `blind_input/`, unchanged (sha256 prefixes match the
  R-08a preparation record: `M1.txt` 21a13518, `M2.txt` 7fb1cef4, `M3.txt` 967e5a61, `M4.txt`
  726e925c, `M5.txt` 5a950918, `INSTRUCTIONS.md` 9c548117, `SCHEMA.json` 98e36507).
- Save annotations to `annotations_A/D#.json`, `annotations_B1/M#.json`, `annotations_B2/M#.json`.
- `recognition.json` format: `{"A": {"D1": "correct"|"wrong"|"none", ...}, "B1": {"M1": ...},
  "B2": {...}, "R08a": {"M1": "none", ...}}`, filled by reading the `recognised_piece` strings
  (the compare step prints them).

### Files and code state

- Code state: uncommitted (no commits in the repo). sha256: `disguise.py` af854024...,
  `score.py` ef6c8b68..., `D1.txt` fd612d61..., `D2.txt` d8183a22..., `D3.txt` c2f470ec...,
  `D4.txt` a4d048fb..., `D5.txt` 91959867..., `INSTRUCTIONS.md` 1ea77331..., `SCHEMA.json`
  8033a42a... (full values: `disguise.py --check --hashes`).
- R-08a code is imported, not changed (`common.py`, `render.py`, `score.py` of R-08a).
- Wall time: rendering and check 23 s; harness 6 s.

### Lesser-known DCML-style phrase-labelled corpora (item 3 of the control; metadata only)

Checked on 2026-09-28 through the GitHub API and one to all `harmonies/*.tsv` files per corpus
(small TSVs, kept in the session scratchpad only, not in `data/`). "Phrase ends" counts `}` and
`}{` in the `phraseend` column on the `main` branch. Licenses are from each repo's
`.zenodo.json`; GitHub shows no SPDX license for most of them.

| Repo (DCMLab) | Music | Pieces | Phrase ends | Cadence labels | License |
|---|---|---|---|---|---|
| `jc_bach_sonatas` | J. C. Bach keyboard sonatas (Classical, galant) | 29 | 442 | 406 | CC BY-NC-SA 4.0 (v2.4) |
| `wf_bach_sonatas` | W. F. Bach keyboard sonatas | 9 | 167 | 109 | CC BY-NC-SA 4.0 (v2.3) |
| `cpe_bach_keyboard` | C. P. E. Bach keyboard works | 66 | 968 | 796 | CC BY-NC-SA 4.0 (v1.0) |
| `scarlatti_sonatas` | D. Scarlatti keyboard sonatas | 69 | 999 | 809 | CC BY-NC-SA 4.0 (v2.4) |
| `handel_keyboard` | Handel keyboard pieces | 6 | 28 | 28 | CC BY-NC-SA 4.0 (v2.4) |
| `pleyel_quartets` | Pleyel string quartets (not keyboard) | 6 | 128 | 115 | CC BY-NC-SA 4.0 (v2.5) |
| `kozeluh_sonatas` | Koželuch keyboard sonatas | 49 | **0** | **0** | CC BY-NC-SA 4.0 (v2.4) |

- **Koželuch has harmony labels but no phrase or cadence labels on `main`**, so it cannot serve
  as the unfamiliar-repertoire test as it stands.
- **Best candidate: `jc_bach_sonatas`** (Classical-era keyboard sonatas, lesser known, phrase and
  cadence labels present). Next: `wf_bach_sonatas` and `cpe_bach_keyboard` (later Baroque /
  empfindsam, so a style shift from Mozart).
- These are score-only corpora (MuseScore files plus TSVs; no performances). An LLM test needs a
  score loader and a renderer path that does not go through Batik; the F-05c detector needs the
  same arrays. The MuseScore files embed the DCML labels, as the Batik MusicXML does, so the same
  leakage rule applies. Adding one is a `data-engineer` ticket (`DATASETS.md` entry, license
  record).

## Audit (2026-09-28, eval-auditor)

**Verdict: Confirmed with caveats. PASS by the pre-registered rule; the disguise was effective
(0 of 5 named); non-inferiority at 0.10 shown.** What this rules out is an explicit-recall
explanation of R-08a's gain. It does not rule out piece-specific familiarity with the structure
that survives the disguise (see 4).

### 1. Blinding (all 15 transcripts)

- The 15 agent ids in DECISIONS (2026-09-28, R-08b annotation run) all have transcripts. Every
  one ran `claude-opus-5-5`. All were launched at 04:41Z, after the README (04:37Z) and the
  scripts (04:36Z) were last changed. There is one transcript per id, so there was no retry.
- **Tool calls, listed in full with jq.** Each agent read `INSTRUCTIONS.md`, `SCHEMA.json` and its
  own `D#.txt` / `M#.txt` in its own folder (`r08b_A`, `r08b_B1`, `r08b_B2`). Some read the
  file in 2-3 offset chunks. No agent read, listed or globbed anything else.
  - Writes: a `Write` of `out/<id>.json` (D2 and D3; the content equals the repo file under
    `jq -S`), or one Bash heredoc/python script.
  - The only `open(` calls are `json.dump` to `out/<id>.json`. The two M1 agents also re-read
    their own output to count events.
  - No web calls, no `ls`, no `cat` of inputs.
  - The sibling folders `r08a_blind/` and `r08a/` in the same scratchpad were never touched.
- **Prompts.** All 15 use the same template (identical sha after normalising folder and id). They
  do not say that anything is disguised, famous or by a named composer.
  - Context loaded: the user's global CLAUDE.md and the user's personal memory index. The project
    CLAUDE.md was not loaded.
  - The workspace name appears only in the environment/cwd fields, as in R-08a.
  - Grepping the A transcripts for "Mozart", Köchel, "Batik", "disguis" or "transpos" finds
    nothing (the single "dCml" hit is inside a base64 signature).
- **Inputs and outputs are byte-identical to the repo.**
  - All 7 files in `r08b_A` match `blind_input_disguised/`. All 7 in each of `r08b_B1` and
    `r08b_B2` match R-08a's `blind_input/`.
  - All 15 `out/*.json` match `annotations_A/B1/B2/` (`cmp`).
  - The sha256 prefixes of `disguise.py`, `score.py`, D1-D5, `INSTRUCTIONS.md` and `SCHEMA.json`
    match the preparation record.
- Enforcement was by instruction, not sandbox. For example, `r08b_A` held all five D files. The
  transcripts show that no agent strayed.

### 2. Pre-registration, pass rule, recognition

- The sha256 of the header up to `## Preparation record` is `dfa87f4f…aa80`, which matches.
  The file times give the order: README, then annotation. The rule in `score.py` is the one
  written in the header:
  - `BAR = 0.70` and `MARGIN = 0.10`, applied to point estimates;
  - U = mean of R08a, B1 and B2 per movement (3 runs each, none missing);
  - t-interval with 4 df;
  - bootstrap with 10,000 resamples, seed 20260929.
- **Reproduced byte-identically in a scratch copy of `artifacts/`:**
  - `disguise.py --check`: PASSED.
  - `score.py --harness`: PASSED. The oracle scores 1.000, the detector equals F-05c, the R-08a
    replay is exact, and the B path gives 0.8168.
  - The re-render of D1-D5 is identical to `blind_input_disguised/`.
  - `scores_A/B1/B2.csv` and `r08b_summary.txt` are IDENTICAL to the repo files.
- **Results:**
  - Mean A 0.802; mean(A − U) +0.014, bootstrap [−0.015, +0.038], t [−0.029, +0.056]. So PASS.
  - The t-interval of A − U lies entirely above −0.10, so "non-inferiority at 0.10 shown" is the
    correct reading.
  - Margin sensitivity: the claim holds for margins ≥ 0.000 (point), ≥ 0.015 (bootstrap lower
    end) and ≥ 0.029 (t lower end).
- **`recognition.json`: every string was checked by hand, and all 20 classes are correct under
  the string-only rule.**
  - A: all five `null`, so none.
  - R08a: M1 `null` (none). M2 K. 333 i, M3 K. 533 i, M4 K. 330 iii and M5 K. 457 iii are all
    correct.
  - B1: M2, M3 ("Probably ... K. 533/494") and M4 ("Possibly ... K. 330, finale ... tentative")
    are correct: each names the right work, and the rule allows hedging. M1 and M5 are none.
  - B2: M2 and M3 are correct; M1, M4 and M5 are `null`, so none.
- **Two borderline cases:** the strings are `null`, but the hand-back texts give guesses. Neither
  guess changes a class under the pre-registered rule.
  - D4 (kv330_2): "vaguely ... a Haydn C# minor/major minuet". That names the wrong composer.
  - B2 M4 (kv330_3): "possibly an early Mozart finale". That is a partial recognition. If it
    counted as correct, the B2 class means become 0.724 (3) vs 0.826 (2). The pass is not
    affected.

### 3. The disguise and the mapping back

- Spot check, D5 vs M2 (kv333_1): the key signature and all pitches are moved (+1 semitone,
  B major). The bar and score numbers start at 381/380. The legend drops the `[ ]` markings line
  and says the numbering starts at an arbitrary number. There are no words or brackets.
  `INSTRUCTIONS.md` differs from R-08a's only in M→D and the pointer wording. The check fires on
  planted cues (per the preparation record).
- **Left in by design, and shared with condition B:**
  - rhythm, texture, meter, anacrusis, bar count and form;
  - melodic intervals: for example, D5 still opens with the K. 333 grace-note figure, a semitone
    higher;
  - the sentence "piano movements from the Classical period" in `INSTRUCTIONS.md`.
- Mapping back: the harness replays R-08a's own annotations through the condition A path (bars
  +c, ids renamed). It reproduces every per-movement F1 exactly. The oracle scores 1.000 on every
  movement, including with pointer propagation. The `k` choices in `disguise.json` follow the
  pre-registered rule (checked by hand for all 5).

### 4. Interpretation

- **What the result shows.** On these 5 movements, the annotator scores the same whether or not
  it can name the piece, at the level of the run-to-run noise.
  - The within-movement run SD is 0.031. The SD of A − U across movements is 0.034.
  - Against the named undisguised runs only, A − mean(named runs) is +0.008 over the 4 movements
    that were ever named.
  - The gain over the detector survives the disguise: A − detector is +0.237, t [+0.051, +0.423].
    It is largest where the detector is weakest: kv533_1 0.807 vs 0.400, kv330_3 0.786 vs 0.456,
    kv457_3 0.712 vs 0.439.
  - So the R-08a gain does not come from naming the piece and recalling a stored analysis. A
    recall benefit larger than about 0.03 F1 (the t lower end) is excluded on these movements.
- **What it does not show.**
  1. Recognition is measured by self-report only. The thinking blocks are empty in the
     transcripts, so implicit or unstated recognition cannot be audited. B2 M4 shows that the
     model can half-recognise a piece while writing `null`.
  2. The disguise hides the surface, not the structure (README threat 1). A model with
     structural familiarity that it cannot name would pass this test too. Only unfamiliar
     repertoire (`jc_bach_sonatas`, per the preparation record) separates "reads phrase
     structure" from "remembers these pieces without naming them". Under the pre-registered rule
     that step is not required, because the disguise was effective. It is still needed before
     any claim about repertoire beyond these five famous movements.
  3. The reading-burden threat (transposition, double accidentals, no dynamics) would bias
     toward a fail, not a pass. It did not bite. D4, with 57 double accidentals and a 7-sharp
     key, scored 0.952, the same as U. D5, with 102 double accidentals, scored 0.754 vs U 0.720.
- **"Runs where the piece was recognised score no higher, even lower."** This is a composition
  artefact. Do not cite it as evidence against memorisation.
  - kv330_2, the easiest movement (every run 0.952, detector 0.919), is never recognised. It
    lifts every "none" mean.
  - Without kv330_2, the undisguised recognised runs average 0.769 (9 runs) and the unrecognised
    ones 0.684 (3 runs).
  - Within a movement, the recognised runs are higher: kv330_3 0.763 vs 0.674, and kv457_3 0.700
    vs 0.689 (the only two movements with both classes).
  - Recognition in the undisguised runs is not randomised. It may simply track how carefully a
    run reads. The only valid contrast is A vs U within the same movement, which is the
    pre-registered one.

### 5. n = 5 and intervals

- Both intervals are reported for every quantity. With 5 movements, the percentile bootstrap is
  narrower than the t-interval, as in R-08a. The t-intervals are the ones to quote: A
  [0.689, 0.916]; A − U [−0.029, +0.056]; A − detector [+0.051, +0.423].
- Mean A's t-interval reaches below 0.70. The pass is on the point estimate, as pre-registered.
  "A ≥ 0.70 with confidence" is not claimed.
- A is one run per movement. The A − U difference is inside ±1 run SD on every movement:
  - kv533_1's −0.037 is the largest drop, and it lies below that movement's undisguised range
    (0.822-0.873);
  - kv330_3 (+0.052) and kv457_3 (+0.019) lie above their ranges.
- Everything is limited to 5 movements, one composer, one model (`claude-opus-5-5`
  in-session) and one annotation standard (DCML).

### Required fixes (documentation only; none changes the verdict)

1. Append the results section that Method step 5 requires. The README currently ends at the
   preparation record, and the numbers live only in `artifacts/r08b_summary.txt`. Include the
   per-movement table, both intervals, run variance and the recognition breakdown. Label the
   "recognised runs score lower" pattern as between-movement composition (section 4).
2. Record the two borderline recognitions (D4 "Haydn", B2 M4 "possibly an early Mozart
   finale") next to `recognition.json`.

### For the lead

- The R-08 condition "LLM phrase boundaries may feed tempo coherence only if R-08b holds" is met
  **for this repertoire**.
- Before LLM boundaries are used on anything other than famous Classical sonatas, or presented as
  a general phrase annotator, run the unfamiliar-repertoire step (`jc_bach_sonatas`). It needs a
  data-engineer ticket first.

## Results (lead, 2026-09-28; audited, see the Audit section)

The full tables are in `artifacts/r08b_summary.txt`, reproduced byte-identically by the auditor.

**Headline:**
- Disguised (A) mean end F1 is 0.802 (t [0.689, 0.916]), with 0 of 5 recognised.
- Undisguised mean of 3 runs (U) is 0.789.
- A-U is +0.014 (t [-0.029, +0.056]). **PASS** under the pre-registered rule, on point estimates.
- A-detector is +0.237 (t [+0.051, +0.423]).
- Run-to-run within-movement SD is 0.031.

**Borderline recognitions**, not counted as "correct" under the string-only rule in `recognition.json`:
- D4's hand-back said it was "vaguely" reminded of a Haydn minuet (wrong composer, string null).
- B2 M4's hand-back said "possibly an early Mozart finale" (string null).

**Corrected interpretation:** the pooled "recognised runs score lower" comparison is a
mix-of-movements artifact. Within a movement, named runs score slightly higher. Only the
same-movement disguised-vs-undisguised comparison is valid evidence.
