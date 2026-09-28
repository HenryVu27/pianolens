# PianoLens research log

A plain-language record of everything done in this project so far, written as source material for
a research blog post. Written 2026-09-28. Every number here comes from an experiment folder in
`experiments/` or a spec in `docs/specs/`. The technical ledger is `EXPERIMENTS.md`; the reasons
behind each choice are in `DECISIONS.md`.

---

## 1. The question

Can a computer judge piano playing the way a good teacher does? Not only "did you hit the right
notes", which apps already do, but "is the phrasing musical, is the pedalling clean, is this an
interpretation or just noise"?

The bet behind the project:

> Piano is the most constrained instrument there is. Once the hammer leaves the string, the player
> cannot change the sound. Per note, a pianist controls only when it starts, how hard it is struck
> and when it is released, plus the pedals. So a MIDI recording plus the score is a near-complete
> description of a piano performance. If that is true, quality should be explainable with a
> modest number of measurable features and a small model, without a giant audio network.

## 2. How the work was organised

- **One repo:** `github.com/HenryVu27/pianolens`, private research code.
- **An agentic setup.**
  - A lead Claude session plans the work, splits it into tickets (`WORKBOARD.md`) and dispatches
    role agents: data engineer, feature engineer, ML researcher, study designer, literature scout,
    and an **eval auditor**.
  - Each agent keeps its own memory notes.
  - Rules that load automatically keep everyone consistent.
- **Pre-registration.**
  - Every experiment writes down its question and what result would prove it wrong *before* it
    runs.
  - The pre-registration is hashed, so later edits are detectable.
- **Adversarial audit.**
  - No result counts until the eval auditor has tried to break it: rerun the numbers, check for
    leakage, check the pre-registration, and question the interpretation.
  - The auditor changed the headline of several results. Section 6 lists these, and it may be the
    most interesting part for a blog.
- **Data:** 17 public datasets, about 11 GB of MIDI and labels, all non-commercial research
  licences. Nothing is committed to git; `DATASETS.md` says how to re-fetch each one.

## 3. What was built

| Piece | What it does |
|---|---|
| Alignment | Matches every played note to its score note. It picks the repeat path the pianist actually took. Mean F1 0.964 on 1,063 (n)ASAP performances. |
| Tier A, correctness | Wrong, extra and missed notes. Any-error F1 per bar is 0.99 on synthetic mistakes. Missed notes are reported per bar because single-note labels are unreliable. |
| Tempo model | Splits timing into a smooth, intentional tempo curve and leftover jitter. It handles fermatas, tempo changes and repeats. |
| Tier B, control | Timing noise, evenness in scales and Alberti bass, hand synchrony, tempo stability, and pedal held across harmony changes. The pedal rule is validated against expert harmony annotations (F1 0.75). |
| Tier C, shaping | Structural coherence (how much of a pianist's expression the score explains), per-phrase tempo arcs, consistency across repeated passages, voicing, and obedience to dynamic markings. |
| Tier D, interpretation | Compares a performance with hundreds of expert performances of the same piece: an expert band per bar, a small "shared core", a typicality score, and a guard against flat, lifeless playing. |
| Report card | MIDI in, a self-contained HTML report out: findings in plain language, a bar-by-bar timeline, curves against the expert band, and "what to practise". There is no invented overall grade. |
| Listening-study app | A local web app to measure how much each kind of flaw bothers listeners. It is built and not yet run. |
| GPU job | Fine-tuning an expression model, packaged to run on an RTX 5080. It is ready and not yet run. |

## 4. The experiments, in order

Each entry gives the question, what was done, the result, and the verdict after audit.

### R-01. Do expert ratings of piano playing reduce to a few dimensions?
- **Data:** PercePiano, 1,202 short clips rated on 19 scales by 53 expert raters.
- **Method:** factor analysis.
- **Result:** the 19 scales collapse to **3 to 5 factors**, dominated by one general "quality" factor.
  The others are loudness/energy, pedal/legato and mood.
- **Verdict:** confirmed with caveats. The exact count depends on the method (3 to 7). The auditor
  also found a bug in a statistics library (factor correlations assigned to the wrong factors).

### R-02. Is expert *expression* low-dimensional?
- **Data:** 698 pieces with 50 expert performances each, from PianoCoRe.
- **Question:** how many independent "shapes" of tempo and loudness are there?
- **Prediction:** 10 or fewer components explain 80% of the variation.
- **Result:** **19 components**, so the prediction failed.
- **The audit's refinement:** the part experts *share* is small (3 to 5 components, about 35-46%
  of the variation). The rest is individual.
- **Takeaway:** an interpretation is a small shared core plus a large space of personal freedom.
- **Verdict:** confirmed with caveats. The original hypothesis is recorded as not supported.

### R-03. Does a published audio model's result hold up?
- **Background:** CrescendAI reported that MuQ, a large audio model, predicts expert ratings with
  R² 0.536.
- **Reproduction:** we reproduced it: 0.509.
- **Fair test:** tested on *pieces the model had never heard*, the result collapses to **R² −0.087**,
  worse than always guessing the average. The model had learned the pieces, not the playing.
- **What survives:** within a passage it still ranks pianists correctly about 59-62% of the time.
- **Also found:** their "leak fix" made the leak worse.
- **Verdict:** confirmed with caveats.

### R-04. Can simple, explainable MIDI features match the audio model?
- **Setup:** a small model on 62 measurable features, with no audio and no deep network.
- **Result:** it **matches MuQ** on unseen pieces in all four test variants (within-passage ranking
  about 62% vs 62%).
- **What drives it:** pedalling, then dynamics, then tempo shape, then voicing.
- **Audit correction:** both models sit at single-rater level. The ceiling is much higher (about
  0.74 vs 0.35), so there is plenty of headroom.
- **Verdict:** confirmed with caveats. "Matches", not "beats".

### R-06. Which expression model should we fine-tune?
- **Setup:** SyMuPe vs Pianist Transformer, both frozen, on pieces neither was trained on.
- **Result:** they **tie**; SyMuPe won the pre-registered tie-break.
- **Big finding:** the models' "how likely is this performance" score **prefers flat, expressionless
  playing to every real pianist**. A raw likelihood can never be used as a quality score.
- **Verdict:** confirmed with caveats. The lead's first "keep both models" was overruled by the
  pre-registered rule.

### R-09. Does structural coherence rise with skill?
- **Data:** MAJEPPA, 1,081 performances from beginner to virtuoso.
- **Result:** pooled, advanced players look more coherent. **Within the same recording context**
  (practice vs concert) the effect disappears.
- **Why:** in MAJEPPA, virtuosos are all concert recordings and beginners are all practice clips.
  The earlier D-10 check found the same trap for the control features.
- **Also:** articulation coherence does not survive transcription noise; timing coherence does.
- **Verdict:** confirmed with caveats. **Inconclusive**, and the design had little chance of
  reaching "falsified" in the first place.

### F-07. Does repeated timing reveal a pianist's intent?
- **Data:** 1,390 cases of the same famous pianist recording the same piece more than once.
- **Result:** the timing that repeats across recordings is explained by the score (R² 0.12). The part
  that changes is not (0.005).
- **Audit twist:** two recordings by *different* pianists pass the same test. So the repeating part
  is timing that any two performances share, not personal intent.
- **What holds:** a pianist's own take-to-take variation is mostly random, so it can be treated as
  noise.
- **Verdict:** confirmed with caveats, and **reinterpreted**.

### R-08a to R-08d. Can an LLM (Claude) read musical phrase structure from a score?

This is the most direct test of the original idea that current LLMs can help.

**Method:**
- Claude annotators receive a text rendering of a score, with no labels, no titles and no access to
  the repo.
- They mark phrase endings and cadence types.
- Their marks are scored against expert (DCML) annotations and compared with a rule-based detector
  we built.
- Every run was blind, and the auditor checked each annotator's transcript for file access.

| Test | What was tested | LLM F1 | Rule-based detector F1 |
|---|---|---|---|
| R-08a | 5 famous Mozart sonata movements | 0.82 | 0.57 |
| R-08b | The same movements disguised (new key, words removed, bars renumbered); 0 of 5 recognised | 0.80 | 0.57 |
| R-08c | 5 J.C. Bach movements the model did not recognise | 0.75 | 0.44 |
| R-08d | 5 Romantic pieces: Tchaikovsky, Chopin, Schumann (Träumerei), Grieg, Liszt | 0.74 | 0.39 |

**Takeaways:**
- **Claude reads phrase structure from the notes and beats the hand-built rules by 0.25 to 0.35 in
  every style.** It is not recalling memorised analyses: disguising the score cost nothing.
- The Romantic result passes the 0.70 bar only on the point estimate. Performance varies a lot from
  piece to piece.
- **Caveat:** the expert labels were published before the model's training cutoff, so exposure to
  them cannot be fully excluded.

## 5. Supporting checks (not headline experiments)

- **D-10:** expert vs amateur control features.
  - Pooled, advanced players look about 25% more controlled.
  - Within matched recording contexts the difference disappears.
  - Transcription noise was measured on 65 recordings that exist both as player-piano MIDI and as
    transcribed audio:
    - timing survives (about 2 ms);
    - loudness does not (about 9 MIDI units of error, above what listeners can hear).
- **F-08b:** the report's timing flags do not over-flag player-piano recordings when they are
  compared against transcribed references.
- **F-04b / F-05b / F-05c:**
  - The harmony-change detector reaches F1 0.75 against expert annotations.
  - Real phrase boundaries double how much of tempo the score explains (0.07 to 0.14).
  - 81% of real phrases are played with a slow-fast-slow tempo arc, against 44% when the
    boundaries are shifted.

## 6. Where the auditor changed our minds

The project's most useful habit was letting an independent agent try to break every result.

| Result | First claim | After audit |
|---|---|---|
| R-01 | Exactly 4 factors; "impossible value" warning | 3 to 5 factors. The warning was a library bug, and the factor correlations were mislabelled. |
| R-02 | Expression needs 19 components, so it is not low-dimensional | The *shared* part is only 3 to 5 components. The rest is individuality. |
| R-03 | Headline reproduction | Their headline averaged 3 of 4 folds, and their "leak fix" made the leak worse. About 60% of MuQ's remaining signal came from spotting flat computer renditions. |
| R-04 | "Everything is near the ceiling" | Wrong ceiling. There is large headroom. |
| R-06 | Keep both models | The pre-registered rule picks one. Also, flat playing beats experts on likelihood even when perturbed. |
| R-08a | Confidence interval above the bar | Too optimistic with 5 items. The t-interval touches the bar. |
| R-08b | "Recognised pieces scored lower" | A mix-of-movements artefact. Within a movement, recognition helped slightly. |
| R-09 / D-10 | "The effect vanishes with context fixed" | It also drops the top skill levels. Context and skill cannot be separated there. |
| F-07 | "Repeated timing = intent" | Different pianists pass the same test. It is shared piece timing, not intent. |
| Study design | "12-17 comparisons per item is enough" | Unsupported by its source. The current guidance is 20 or more. |

The pattern: first-pass analyses consistently overclaimed. Pre-registration plus an adversarial
auditor caught it every time.

## 7. What is still open

- **Does the tool measure skill, not just recording context?** This needs recordings where skill
  varies but the setting does not. Henry's own recordings are ideal.
- **H1b:** can a fine-tuned expression model predict the shared expert core from the score? The
  GPU job is ready.
- **H6:** which flaws do listeners actually mind most? The study is built, with no listeners yet.
- **H7:** what explains preference among good performances? This needs the pairwise listening study.
- **H8:** do audio skill models cheat on recording quality? This is planned.
- **Phone audio front end:** the transcription pipeline is not built yet.

## 8. Reproducing anything

Each experiment folder in `experiments/` has a README with its pre-registration, the exact command,
the results and the audit. Data is re-fetched per `DATASETS.md`. `STATUS.md` has the current state.
