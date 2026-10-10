# Workboard

Tickets for `docs/plans/2026-09-27-research-program.md`. IDs are stable; cite them in experiment
READMEs, memory notes and commit messages. Written 2026-09-27.

## How to claim

1. Every ticket in `blocked_by` must be Done. Set `owner:` to your agent name and `status: in progress`.
2. One ticket in flight per agent.
3. Work only inside the ticket's `paths`. If you must touch a shared file (`pyproject.toml`,
   `src/pianolens/data/types.py`), keep the change minimal and say so in your report.
4. **OWNER** tickets need Henry: money, credentials, recruiting people, playing the piano,
   decisions. An agent prepares them and asks.
5. **Done** means all of these:
   - every `gate` passes;
   - `uv run pytest -q` and `uv run ruff check src tests` are green;
   - tests exist for the new code;
   - any doc the ticket names is updated;
   - the status table below is updated;
   - one line under "Log" at the bottom of this file.
6. **Experiment tickets** follow the `run-experiment` skill. Their verdict is only "Confirmed"
   after `eval-auditor` signs off.

Sizes: **S** ≤ half a day of agent work, **M** ≤ 2 days, **L** longer.

## Status

| Phase | Tickets | Done |
|---|---|---|
| 0 Infrastructure | D-01..D-08, F-01, E-01 | 7 (E-01, D-01, D-02, D-03, F-01, D-07, D-08) |
| 1 Scorer v1 | F-02..F-08 | 6 (F-02, F-03, F-05, F-06, F-07, F-08) |
| 2 Low-dimensionality | R-01..R-05 | 1 (R-01, Confirmed with caveats) |
| 3 Perceptual cost | S-01..S-03 | 3 (S-02, S-01, S-03 design/build; pilot and O-02 pending) |
| 4 Preference study | S-04..S-06 | 0 |
| 5 Expression model | R-06..R-07 | 0 |
| 6 Audio front end | A-01..A-03 | 0 |
| 7 Feedback | R-08, O-05 | 0 |
| Literature | L-01..L-03 | 2 (L-01, L-02) |

## Phase 0: infrastructure

**D-01 Common data types and ASAP loader** (M)
- owner: data-engineer. status: done. blocked_by: none.
- paths: `src/pianolens/data/`, `tests/data/`, `DATASETS.md`, `scripts/`.
- Define `types.py`:
  - `Score` (note array + metadata + measure map)
  - `Performance` (note array: onset_sec, duration_sec, pitch, velocity, plus pedal events)
  - `Alignment` (match / insertion / deletion list)
  - `PieceId` and `PerformerId`: stable string ids shared across datasets
- Build on partitura's note arrays; do not reinvent them.
- Loader for (n)ASAP. It is already at `data/raw/asap`; the note alignments come from the repo
  or from the (n)ASAP release.
- gate: load every ASAP performance + score + ground-truth alignment. Report counts in
  `DATASETS.md`.

**D-02 PercePiano loader** (S)
- owner: data-engineer. status: done. blocked_by: D-01.
- Already at `data/raw/percepiano`.
- Load MIDI segments, the 19-dimension mean labels, and **per-rater labels** from
  `labels/total_2rounds.csv`. The per-rater labels are needed for rater parity and for H2.
- Map each segment to its piece, performer and bar range.
- gate: 1,202 segments (or the documented count), each with a piece id and a performer id.

**D-03 PianoCoRe download + loader** (M)
- owner: data-engineer (instance 2). status: done. blocked_by: D-01.
- Download subset A (and A* if separate) from GitHub or HF `SyMuPe/PianoCoRe`. Check the size
  first; stay inside the 60 GB budget.
- Loader yields performances aligned to scores.
- gate: a per-piece performance-count table. List the top 50 pieces by count in `DATASETS.md`.
- size note (2026-09-27, data-engineer 2): Zenodo 19186016 v1.0 has metadata.csv 206 MB, refined.zip 3.58 GB
  (A/A* refined MIDI + alignments), raw-midi.zip 2.87 GB, raw-alignments.zip 5.22 GB. Fetching metadata +
  refined + raw-midi (~6.7 GB); raw-alignments deferred. data/raw was ~1.9 GB before.

**D-04 Small labeled sets** (M)
- owner: data-engineer (instance 2). status: review (lead: accept CIPI labels + PSyllabus in place of gated CIPI scores?). blocked_by: D-01.
- Expert-Novice (zenodo 8392772), NeuroPiano (HF), Vienna 4x22, Batik-plays-Mozart, MazurkaBL,
  PianoJudges labels, MAESTRO v3 **MIDI only**, CIPI.
- For each: download, write a loader, and record the license and size.
- gate: each loads in a smoke test.

**D-05 MAJEPPA and mistake sets** (S)
- owner: data-engineer (instance 2). status: blocked on OWNER (MAESTRO-E needs a Globus login; MAJEPPA done). blocked_by: D-01.
- Find the MAJEPPA release. If it is not public, log that in `DATASETS.md` and `BACKLOG.md`.
- Get the MAESTRO-E / Polytune mistake data (MIDI or labels only; skip large audio).

**D-06 Aria-MIDI amateur mining (scoping)** (M)
- owner: none. status: open. blocked_by: D-03.
- Estimate how many Aria-MIDI files match PianoCoRe pieces and look amateur. Use metadata and
  heuristics, not audio.
- Output: a scoping note plus a candidate list. Do not bulk-download without a size estimate.

**D-07 Types extension + PianoCoRe cache** (M)
- owner: data-engineer (instance 3). status: done. blocked_by: D-03.
- paths: `src/pianolens/data/`, `tests/data/`, `scripts/`, `DATASETS.md`, `BACKLOG.md`,
  `data/processed/`.
- Add a `BeatCurve` type (per-beat time, tempo, loudness; used by MazurkaBL and beat alignments).
- Make `interpolated` an official alignment label.
- Fix accent folding in `make_piece_id` (Dvořák must not become `dvok`).
- Merge `pianocore_piece_map.csv` and the ASAP ids into `data/processed/piece_ids.parquet`.
- Parallel full pass over PianoCoRe tier A, all 14 cores, into a cached parquet of aligned note
  arrays for R-02. Resolves BL-09.
- gate: the full tier A cache is built; the failure count is reported; the load time from cache is
  measured.

**D-08 Synthetic mistake set** (M)
- owner: feature-engineer. status: done 2026-09-27. blocked_by: D-01.
- result: `data/processed/mistakes_v1` (DATASETS.md row), `scripts/build_mistake_set.py`.
- MAESTRO-E-style wrong, extra and missed notes injected into aligned MAESTRO/ASAP MIDI, with
  exact ground truth.
- Share the perturbation code with S-01 (`src/pianolens/data/perturb.py`).
- gate: the F-02 evaluation can run on it.

**D-09 SKY-Piano: expert vs amateur control check** (S)
- owner: data-engineer. status: blocked 2026-09-27 (data not released, license unclear; see
  DATASETS.md SKY-Piano note and BACKLOG BL-11). blocked_by: F-04, BL-11.
- SKY-Piano (ISMIR 2026) has Disklavier recordings of 7 professionals and 12 amateurs, including
  a slow C-major scale and 11 shared exercises.
- Check the license first, then download the MIDI and aligned MusicXML only (no video or mocap).
- Run the F-04 `even_*` and hand-sync features; compare with the literature ranges in landscape
  section 1.5.
- This is the first real expert-vs-amateur validation of tier B.

**D-10 Expert vs amateur control check: open-data substitute for D-09** (M)
- owner: data-engineer. status: done 2026-09-27 (result: `docs/specs/skill-control-check.md`; lead to review). blocked_by: F-04b (done).
- Data:
  - MAJEPPA: transcribed MIDI with 6 skill levels, the same pieces played at several levels, and
    the at-least-85% coverage filter.
  - PianoVAM: amateur MIDI, CC BY-NC.
  - Rach3: advanced vs beginner rehearsal MIDI, if its license and access allow.
- Run tier B (F-04) and tier A (F-02) by skill level at matched note rate. Compare with the
  literature ranges in landscape section 1.5.
- Caveat: transcribed MIDI adds timing noise, so check effect sizes against a transcription-noise
  estimate (e.g. from the ASAP pieces that are both Disklavier and transcribed in PianoCoRe).

**D-11 Batik loader: MusicXML performed score + phrase and cadence tables** (S)
- owner: feature-engineer. status: done 2026-09-27 (`iter_aligned(musicxml_score=True)`,
  `load_aligned`, `performed_score`, `phrase_annotations`; every match id resolves in 36/36,
  id Jaccard 1.0 in 35, kv281_3 0.9996 = one extra MusicXML note). blocked_by: none.
- Wrap F-05b's re-unfold of `scores_edited/<stem>.musicxml` to the match-file repeat path (id
  Jaccard 1.0) into `pianolens.data.batik_mozart`.
- Return phrase and cadence tables mapped to performed-score beats.
- See the feature-engineer memory `batik-annotations.md`.

**F-01 Alignment pipeline + validation** (M)
- owner: feature-engineer. status: done 2026-09-27 (dispatched by the lead in parallel with
  D-01; adapts to `data/types.py` by duck typing). blocked_by: D-01.
- result: `docs/specs/alignment-validation.md`.
- paths: `src/pianolens/align/`, `tests/align/`.
- parangonar DualDTWNoteMatcher. Nakamura's tool as a cross-check if its binaries build on
  macOS arm64; if they don't, note it.
- Handle repeats (partitura unfold) and ornaments.
- gate: match accuracy vs (n)ASAP ground truth, reported per composer in the ticket log.

**E-01 Evaluation harness** (M)
- owner: ml-researcher. status: done. blocked_by: D-01 (lead waived: harness is generic arrays).
- paths: `src/pianolens/eval/`, `tests/eval/`.
- Contents:
  - Grouped K-fold by piece and by performer.
  - Bootstrap CIs.
  - Metrics: R², Spearman, Kendall, pairwise accuracy.
  - Rater parity: given a per-rater label matrix, compute each held-out rater's correlation with
    the mean of the other raters, and the model's correlation with the same mean.
  - Bradley-Terry fit from a list of comparisons.
- gate: unit tests on synthetic data with known answers.

## Phase 1: scorer v1

- **F-02 Tier A correctness** (M). owner: feature-engineer. status: done 2026-09-27 (result:
  `docs/specs/correctness-validation.md`; lead to decide the pairing window, 50 vs 100 ms). blocked_by: F-01. Correct / extra / missed / wrong-pitch labels,
  ±50 ms, ornament whitelist, per-bar summary.
  - gate: F1 against the mistake set from D-05.
- **F-02b Wrong-pitch window to 100 ms** (S). blocked_by: F-02. owner: feature-engineer. status: done 2026-09-27
  (`correctness.WRONG_PITCH_WINDOW_SEC`; results in `docs/specs/correctness-validation.md`).
  - Make wrong-pitch pairing default to 100 ms, separate from the 50 ms onset tolerance.
  - Fix the ornament-test interaction.
  - Rerun `scripts/eval_correctness.py`.
  - See DECISIONS 2026-09-27.
- **F-03 Tempo model** (M). blocked_by: F-01. owner: feature-engineer. status: done 2026-09-27
  (API: `pianolens.features.tempo_model`; sanity run: `scripts/check_tempo_f03.py`). paths: `src/pianolens/features/tempo.py`, `tests/features/`. Beat-level tempo curve; smooth (phrase-level) fit;
  residual jitter.
  - Consider a penalized spline or a phrase-arc model.
- **F-04 Tier B control features** (M). blocked_by: F-03. owner: feature-engineer. status: done 2026-09-27
  (API: `pianolens.features.control_features`; sanity run: `scripts/check_control_f04.py`). paths: `src/pianolens/features/control.py`, `tests/features/`. Evenness in passages the score marks as
  even, hand synchrony, tempo stability, pedal-over-harmony-change blur.
- **F-04b Evenness variants + harmony-rule validation** (S). blocked_by: F-04. owner: feature-engineer. status: done (2026-09-27; results in `docs/specs/control-validation.md`). paths: `src/pianolens/features/control.py`, `tests/features/test_control.py`, `scripts/`, `docs/specs/control-validation.md`.
  - Add the strict evenness variant (DECISIONS 2026-09-27).
  - Validate the pedal-blur harmony-change detector against the Batik DCML harmony annotations.
    Report precision and recall of detected changes.
  - Tune the pedal lift window on Batik/Vienna (sensor pedal data) if the evidence supports it.
- **F-05 Tier C shaping** (L). blocked_by: F-03. owner: feature-engineer. status: done 2026-09-27 (API: `pianolens.features.shaping`, `score_basis`; sanity run: `scripts/check_shaping_f05.py`). paths: `src/pianolens/features/shaping.py`, `src/pianolens/features/score_basis.py`, `tests/features/`.
  - Structural coherence: regress the performer's deviations on score basis features and report
    R² (H4).
  - Repeated-material consistency, voicing ratio, dynamic-marking compliance.
- **F-05b Phrase boundaries and tempo coherence** (S). blocked_by: F-05. owner: feature-engineer. status: done 2026-09-27 (spec `docs/specs/phrase-coherence-validation.md`; proxy F1 0.34 at ±1 beat; Batik tempo R² 0.07 proxy -> 0.14 annotated + phrase_detail; boundary AND model problem; lead decisions pending). paths: `src/pianolens/features/shaping.py`, `src/pianolens/features/score_basis.py`, `tests/features/`, `scripts/check_phrase_f05b.py`, `docs/specs/phrase-coherence-validation.md`.
  - Use the Batik-plays-Mozart phrase (and cadence) annotations as ground-truth boundaries.
  - Compare structural coherence (tempo, velocity, timing) using the proxy boundaries vs the
    annotated ones, on Batik and on any other annotated set.
  - Measure proxy boundary precision and recall against the annotations.
  - This decides whether R-08 (LLM phrase analysis) is worth its cost.
- **F-05c Per-phrase tempo shaping + cadence-derived phrase ends** (M). blocked_by: F-05b, F-04b. owner: feature-engineer. status: done 2026-09-27 (spec
  `docs/specs/phrase-coherence-validation.md`, F-05c section; held-out end F1 0.46 vs proxy 0.29
  at ±1 beat, but tempo coherence with them is below the proxy's; `phrase_tempo_shaping`
  concave excess works without annotations). paths: `src/pianolens/features/cadence.py`,
  `shaping.py`, `score_basis.py`, `tests/features/`, `scripts/check_phrase_f05c.py`.
  - Per-phrase tempo measures: the share of concave (slow-edge) arcs; parabola fit R² per phrase vs
    a shifted-boundary null.
  - Phrase ends inferred from cadence detection (bass motion + harmony-change rule), measured
    against Batik DCML phrase ends and cadences.
  - If ±1-beat phrase-end F1 is high enough, use it in place of the proxy.
  - See DECISIONS 2026-09-27 (after F-05b).
- **F-05d Coherence minimum-length fix** (S). blocked_by: R-09. owner: feature-engineer. status: done 2026-09-28. paths: `src/pianolens/features/shaping.py`, `src/pianolens/features/extract.py`, `tests/features/test_shaping.py`, `data/interim/f05d_check/`.
  - Define `n_blocks` from distinct written bars, and also require at least 12 distinct written bars
    (DECISIONS 2026-09-28).
  - Add a regression test on an 8-bar score numbered 0-8.
  - Check that R-04 and R-09 outputs are unaffected, or report the difference.
  - Result: R-04 11 timing-coherence rows -> NaN, H3 verdicts unchanged; R-09 23-24 analysis rows
    per channel -> NaN, verdicts unchanged (velocity secondary effect 0.142 -> 0.019). Details in
    `.claude/agent-memory/feature-engineer/coherence-f05d.md`. `takes.py` n_blocks not changed.
- **F-05e Phrase measures with LLM boundaries** (M). blocked_by: R-08d. owner: feature-engineer. status: done 2026-09-28, verdict Provisional (needs eval-auditor; experiment `experiments/2026-09-28-F-05e-llm-phrase-measures/`, spec F-05e section). LLM starts recover DCML concave_excess by point estimate (-0.055 over 8 units; Batik -0.014, Romantic -0.124 on 3); the 4-bar merge does not help (-0.090) and hurts on Romantic pieces; use raw LLM starts; coherence R2 not validatable (DCML ~ proxy here). paths: `src/pianolens/features/shaping.py`, `tests/features/`, `experiments/2026-09-28-F-05e-llm-phrase-measures/`, `docs/specs/phrase-coherence-validation.md`.
  - Validate `phrase_tempo_shaping` (`concave_excess`) and phrase-aware coherence using LLM
    boundaries against DCML boundaries on Batik, J.C. Bach and the Romantic corpora where
    performances exist (MazurkaBL / PianoCoRe mazurkas).
  - Make the measures robust to over-segmentation (merge nested phrases). See DECISIONS 2026-09-28
    (R-08d).
- **F-06 Tier D interpretation** (M). blocked_by: F-03, D-03. owner: feature-engineer. status: done (2026-09-27). paths: `src/pianolens/features/interpretation.py`, `tests/features/test_interpretation.py`. Per-piece PCA of expert curves;
  likelihood under the expert distribution; per-bar out-of-band flags.
  - Add reference-based features (R-04's S1 set; DECISIONS 2026-09-27): distance of this
    performance's curves to other performers of the same passage or piece, leave-one-out.
  - Reuse `src/pianolens/features/extract.py` (`reference_features`).
- **F-07 Repeated-take analysis** (S). blocked_by: F-03. owner: feature-engineer. status: done 2026-09-28 (API: `pianolens.features.takes`: `decompose_takes`, `take_structure`, `takes_from_files` for O-01; H5 experiment `experiments/2026-09-27-F-07-H5-intent-vs-noise/`, Provisional, needs eval-auditor). paths: `src/pianolens/features/takes.py`, `tests/features/test_takes.py`, `experiments/2026-09-27-F-07-H5-intent-vs-noise/`. Split timing into the part consistent
  across takes and the residual (H5).
- **F-08 Report generator** (M). blocked_by: F-02..F-06. owner: feature-engineer. status: done 2026-09-28
  (API `pianolens.report`; CLI `scripts/pianolens_report.py`; samples `scripts/build_report_samples_f08.py`).
  paths: `src/pianolens/report/`, `scripts/pianolens_report.py`, `tests/report/`,
  `data/interim/reports/`. An HTML report: per-bar flags, curves against the expert band.
- **F-08b Report: provenance check for timing flags, plus recurring-error tiering** (S). blocked_by: F-08.
  owner: feature-engineer. status: done 2026-09-28 except the spec doc (lead to write `docs/specs/report-validation.md` from the report). paths: `src/pianolens/report/`, `tests/report/`,
  `scripts/build_report_samples_f08.py`, `scripts/check_timing_provenance_f08b.py`, `scripts/calibrate_recurring_f08b.py`,
  `data/interim/reports/`, `data/interim/timing_provenance_f08b/`, `docs/specs/report-validation.md`.
  - Score D-10's Disklavier/transcribed same-performance pairs against PianoCoRe references. Is the
    Disklavier version flagged more often? If so, match reference provenance or calibrate before
    timing flags leave "experimental".
  - Implement the recurring-error promotion and correctness-first ranking (DECISIONS 2026-09-28,
    after F-08).
- **F-08c Per-bar expert check for single-take reports** (S). blocked_by: A-01.
  owner: feature-engineer. status: done (2026-09-28). Spec: `docs/specs/report-validation.md` section 4.
  - Suppress correctness flags at bars where expert transcriptions of the same score also show
    errors, as in Op. 64 No. 2 bars 78-79.
- **A-01b Phone-audio extra-note filter** (M). blocked_by: A-01. owner: audio-engineer.
  status: done (2026-09-28; not committed). Spec: `docs/specs/phone-audio-baseline.md`, A-01b.
  - Uses register, fixed repeated pitches and the absence of a plausible source note.
  - Validate on audio with ground truth first (BL-13 / PianoVAM).
  - Result: PianoVAM microphone audio (84 recordings, Transkun) has 0.26% false extras, and only
    0.007% at G6 or above. It does not reproduce the phone-take artefact.
  - The signature rule is safe: held-out true-note loss is 0.10% (4.3% at G6 or above), and it
    removes 0.04% of the notes of professional references. It removes 141 extras and 1 correct
    note on the takes, cutting extra rates from 19.5/29.3/15.5% to 17.6/22.2/14.1%.
  - It is optional (`--filter-extras rule`) and off by default. Extras stay low confidence.
  - A PianoVAM-trained classifier was net harmful and is not used.
- **P-01 Audible A/B comparison engine** (M). blocked_by: F-08, A-01. owner: feature-engineer.
  status: done (2026-09-28; not committed). Integration into the report/app is P-02.
  - For each flagged bar or passage in a report, produce aligned audio clips:
    - the user's original audio cut to those bars (from alignment timestamps);
    - the user's performance re-rendered with the fixed S-02 piano;
    - a "typical expert": the reference whose curves are closest to the expert median in that
      window, rendered with the same piano;
    - optionally a second, contrasting expert.
  - Clips get loudness matching, short fades, and pre- and post-roll of about 1 bar.
  - Module: `src/pianolens/compare/`.
  - Outputs are local only (DECISIONS: personal data and non-commercial reference data).
- **P-02 Local web app** (L). blocked_by: P-01, F-08c. owner: feature-engineer. status: done
  (2026-09-28; not committed). Run: `uv run python scripts/pianolens_app.py`; see `docs/APP.md`.
  - Upload audio or MIDI, choose a supported piece (searchable list of PianoCoRe/ASAP pieces with
    scores and at least 50 references), run the pipeline with progress, and show the report with an
    embedded A/B player (loop, instant A/B switch, curves for the window).
  - Runs on localhost only, no external calls. Module: `src/pianolens/app/`.
- **O-01 OWNER: Henry records MIDI** (S). Three takes each of one or two passages from a piece in
  (n)ASAP / PianoCoRe. Needs a piece choice and MIDI out.
  - Option (2026-10-01): a passage from a piece with a teacher's annotated score (D-14, for
    example Chopin Nocturne Op. 9 No. 2) lets R-11 check the report on Henry's own playing.
- **D-14 tonebase lesson export: register and extract** (S). owner: lead. status: done 2026-10-01
  (not committed). paths: `data/raw/tonebase/`, `data/interim/tonebase_audio/`,
  `src/pianolens/data/tonebase.py`, `tests/data/test_tonebase.py`, `scripts/extract_tonebase.py`,
  `scripts/build_piece_ids.py`, `DATASETS.md`.
  - Result: 28 zips (57.4 GB, sha256 recorded) hold 567 videos (497 unique) and 166 PDFs (155
    unique). Extracted all PDFs (0.84 GB) and the audio of the 190 unique piece-lesson videos
    (4.8 GB, 67.8 h; an exception recorded in DECISIONS). 21 teachers' annotated scores, matched
    by title page; 18 share a PianoCoRe piece id (17 with tier A performances, 79 to 2,011).
    `piece_ids.parquet` rebuilt: 21 rows added, the other 7,018 identical.
  - License unclear (BL-29): nothing from it is committed. Content left in the zips: BL-30.
- **BL-19b Validate the staff-vs-hand proxies against PianoVAM hand labels** (M). blocked_by: BL-24
  (done 2026-10-10), DF-13 (shares align/ code; run after it). owner: feature-engineer. status:
  done 2026-10-10, Confirmed with caveats (eval-auditor 2026-10-10; D2 pass at the boundary, not
  stable to one piece); `experiments/2026-10-10-BL-19b-hand-proxies/`.
  Pre-register before scoring any proxy. Scope in DECISIONS 2026-10-10 (BL-24): split sessions into
  takes, align to catalogue scores, matched notes only, resolve or exclude the 15 ambiguous
  movements, `Noinfo` policy, video-label hand error (about 0.8%) as noise floor, engraver
  hand-mark recall (BL-19 audit). Loader: `pianovam.hand_labels(perf, "video" | "manual")`; join by
  pitch and onset, never by row position.
- **R-11 Teacher annotations vs the expert band and the report (pilot)** (M). blocked_by: D-14.
  owner: ml-researcher. status: in progress (2026-10-05: gate passed, (a)-(c) run, verdict
  Provisional; waiting for eval-auditor).
  paths:
  `experiments/<date>-R-11-teacher-annotations/`, `data/interim/tonebase_annotations/`.
  - Why: the plan's localization metric (teacher-marked problem bars, section 4) has no data on
    real pieces. The annotated scores are bar- and note-level teacher marks on pieces with
    hundreds of expert performances.
  - Pieces: Chopin Nocturne Op. 9 No. 2 (Huangci, 2,011 tier A), Waltz Op. 64 No. 1 (Laude, 832),
    Etude Op. 10 No. 4 (Lomazov, 846): three teachers and three kinds of demand.
  - Step 1, encode, blind to expert data and report output. One row per annotation: piece_id,
    PianoCoRe score measures (map the edition's bar numbers first), highlighted notes if any,
    category (voicing, dynamics, timing, articulation, pedal, evenness, character,
    fingering/physical), MIDI-observable (yes / partly / no) and, when observable, the expected
    direction (for example boxed bass notes louder than the other notes on the same beat). A
    second blind encoding of one piece measures encoding agreement.
  - Step 2, pre-register (`run-experiment`) before computing anything. Suggested questions:
    (a) does the expert consensus do what the teacher marks, more often than in matched
    unannotated bars (baseline: the same test at shuffled bar positions)? (b) when the marked
    effect is removed from expert performances in the marked bars only (S-01 degradations), does
    the report flag those bars, and stay quiet on the untouched originals? (c) descriptive: the
    share of annotations MIDI can observe, by category.
  - Threats to name in the pre-registration: tier A for Op. 9 No. 2 and Op. 64 No. 1 has no
    Disklavier performances (D-03 table), so velocity categories rest on transcribed velocity;
    use (n)ASAP / MAESTRO Disklavier performances of these pieces where they exist and report
    provenance separately. Three pieces and three teachers make a pilot, not a general claim.
  - Out of scope: lesson transcripts (BL-30); the other 18 annotated scores until the pilot reads
    out. Encodings stay in `data/interim/` and the README carries counts and statistics only
    (BL-29).
  - Gate: encodings for all three pieces plus the agreement check; pre-registration in the README
    before any analysis; verdict Provisional until eval-auditor signs off.

## Phase 2: low-dimensionality

- **R-01 H2: factor structure of PercePiano ratings** (S). blocked_by: D-02 (lead waived; labels
  parsed in the experiment folder). owner: ml-researcher. status: done, verdict Confirmed with caveats
  (audited 2026-09-27; post-audit fixes applied). Headline: 3-5 factors with one dominant general
  factor; the falsifier (>8) is never met. Parallel analysis;
  EFA; the loadings table.
- **R-02 H1: dimensionality of expert expression** (M). blocked_by: D-03, F-03. PCA or functional
  PCA per piece; components needed for 80% variance; stability across pieces.
  owner: ml-researcher. status: done, verdict Confirmed with caveats (audited 2026-09-27; H1 not supported, shared structure 3-5 comps).
  `experiments/2026-09-27-R-02-expression-dimensionality/`: joint k80 19 in-sample at n = 50 (3% of pieces ≤ 10,
  35% > 20); held-out R² 0.31 at k = 10; below the phase null on every piece; not transcription noise.
- **R-03 H3a: reproduce the MuQ baseline on PercePiano** (M). blocked_by: D-02, E-01.
  owner: ml-researcher. status: done, verdict Confirmed with caveats (audited 2026-09-27; post-audit fixes applied).
  `experiments/2026-09-27-R-03-muq-percepiano/`: (a) 0.509 reproduces 0.536 at the low edge; (b) 0.460;
  (c) leave-work-out -0.087 pooled, within-passage pair acc 0.620.
  - Spec: `docs/research/2026-09-27-crescendai.md`, "reproduce" section.
    - Render with Salamander; the target is 0.536 on the clean 4-fold run.
    - Use their paper-era fold file (commit `d8b603fd`), which is leave-passage-out.
    - Do not use their later "fixed" folds: those are grouped by performer and leak.
  - Frozen MuQ-large-msd-iter with layer-wise probes.
  - Report:
    - their protocol as published;
    - the same with an inner validation split for early stopping;
    - leave-work-out (4 works);
    - a passage-mean baseline and a within-passage ranking metric.
  - Raters actually heard Logic Pro's "Yamaha Grand Piano". A Logic render is optional and OWNER.
- **R-04 H3b: symbolic feature model on PercePiano** (M). blocked_by: D-02, E-01, F-03, F-04,
  F-05. owner: ml-researcher. status: done, verdict Confirmed with caveats (audited 2026-09-27)
  `experiments/2026-09-27-R-04-symbolic-percepiano/`. GBM / GAM / small MLP on features. Compare with R-03 and rater parity.
  - **H3 is judged under leave-work-out** (audited R-03, frozen MuQ; each cell is pooled R² /
    within-passage R² / within-passage pair accuracy):

    | Variant | MuQ |
    |---|---|
    | All segments, 4 works (D960 mv2 and mv3 separate) | -0.087 / 0.155 / 0.620 |
    | Deadpan "Score" renditions excluded from scoring | -0.163 / 0.063 / 0.590 |
    | D960 mv2 and mv3 merged into one work | -0.031 / 0.046 / 0.618 |
    | D960 merged, Score excluded | -0.084 / 0.068 / 0.586 |

  - **Co-primary metrics:** within-passage pair accuracy and within-passage Spearman. Within-passage
    R² is fragile.
  - Report every variant.
  - Use paired tests against R-03's per-segment out-of-fold predictions (`artifacts/oof_predictions.npz` and
    `artifacts/oof_predictions_postaudit.npz` for the merged and no-Score variants).
  - Required baselines:
    - train mean;
    - performer prior (0.570 pair accuracy);
    - deadpan indicator (0.541).
  - An inner validation split grouped by work is recommended.
  - Report two ceilings:
    - single-rater parity, on non-tied pairs; MuQ roughly matches one rater under leave-work-out;
    - panel-level split-half reliability of the mean.
- **R-05 H8: recording-context shortcut check** (M). blocked_by: D-05 or a substitute design.
  owner: ml-researcher. status: done, Provisional, awaiting eval-auditor (2026-09-28; substitute design: MAJEPPA MIDI rendered under simulated contexts). paths: `experiments/2026-09-28-R-05-context-shortcut/`.
  - Result: H8 supported in simulation. Confounded AUC 0.943 vs 0.870 with context fixed (+0.073); 0.730 when test contexts are permuted; negative control +0.002.
  - MAJEPPA is public on Hugging Face (`kkwsts/MAJEPPA-Dataset`): MIDI plus context labels, no audio.
  - Getting audio means fetching it from YouTube. That is an OWNER decision.
  - Substitute: render MAJEPPA MIDI through several room and mic simulations, then test whether an
    audio classifier's skill accuracy moves with the simulated context.
  - MAJEPPA's MIDI is also usable for H4 (structural coherence vs skill).

- **R-09 H4: structural coherence vs skill** (M). blocked_by: F-05, F-05b.
  - Data: MAJEPPA (skill levels, coverage filter of at least 85%) and Expert-Novice (needs
    transcription, so later).
  - Test: is coherence without markings monotone in skill? Hold out pieces; control for piece
    difficulty (PSyllabus / CIPI) and clip length.
  - **It must control for recording context** (MAJEPPA `recording_type`; D-10 found tier B's
    apparent skill effect disappears within matched contexts). Use timing features only; no velocity
    on transcribed MIDI.
  - owner: ml-researcher. status: run, verdict Provisional (inconclusive); needs eval-auditor.
    Experiment `experiments/2026-09-28-R-09-coherence-skill/`.

## Phase 3 and Phase 4: listening studies

- **S-01 Degradation generator** (M). Perturb aligned expert MIDI along one dimension at graded
  levels.
  - owner: study-designer. status: done 2026-09-27. paths: `src/pianolens/study/`, `tests/study/`.
    API: `pianolens.study.degrade(ap, dimension, level)` (7 dimensions; `DegradeResult.physical`
    in ms / MIDI / beats and threshold ratios vs landscape 1.5), `pianolens.study.excerpt`.
- **S-02 Fixed-piano rendering pipeline** (S). One piano sound for every stimulus. Candidates:
  Pianoteq (OWNER if a license is needed), Salamander via FluidSynth, or a SFZ player.
  - owner: ml-researcher (dispatched by the lead as the R-03 prerequisite). status: done.
    Salamander C5 Light SF2 (the file CrescendAI used) via FluidSynth 2.6.1, settings pinned;
    24 kHz mono, no loudness normalisation by default (peak/LUFS options for stimuli only).
    `scripts/render_percepiano.py` rendered 1,202/1,202 PercePiano segments.
    paths: `src/pianolens/audio/render.py`, `tests/audio/`, `DATASETS.md`, `data/interim/renders/`.
- **S-03 Perceptual cost study design + web app** (L). Protocol, consent text, power analysis,
  and the app. O-02 is needed to run it.
  - owner: study-designer. status: done 2026-09-27 (design and build only; nothing run on a listener).
    Protocol `study/protocol-S03.md` (draft pre-registration, frozen after the pilot), app `study/app/`,
    stimuli `data/interim/study_s03/`. Next: the Henry pilot (protocol section 8), then O-02. blocked_by: S-01, S-02.
    paths: `study/`, `src/pianolens/study/`, `scripts/build_study_s03.py`, `scripts/power_s03.py`,
    `tests/study/`, `data/interim/study_s03/`.
- **S-04 Pairwise stimulus selection** (M). Same passages across skill levels, rendered by S-02.
  - owner: study-designer. status: design drafted 2026-09-29 (not frozen; no stimulus built, nothing run on a listener).
    `study/protocol-S04.md` (experts only, exact-capture ASAP + Vienna; 24 passages x 10; H7 = leave-piece-out
    reliable-variance gain of features over distance-to-mean, draft margin 0.10); sim `src/pianolens/study/power_s04.py`,
    `scripts/power_s04.py` -> `data/interim/study_s04/power/`. Cross-skill stimulus set proposed as a separate S-04b.
    Next: lead/Henry decisions (protocol section 11), then stimulus build, S-05 (S-03 app + `study=S04` flag).
- **S-05 Pairwise study app + adaptive pair selection** (L). Watch Bramley's caveat: adaptive pair
  selection can inflate reliability.
- **S-06 BT analysis + feature regression** (M) (H7).
- **O-02 OWNER: recruiting and consent** for Phases 3 and 4.

## Phases 5-7

- **R-06 Expression model survey + choice** (M). owner: lit-scout (survey), ml-researcher (frozen head-to-head). status: done, verdict Confirmed with caveats (audited 2026-09-28); SyMuPe primary, PT secondary. ml-researcher: frozen SyMuPe EncDec-base vs Pianist Transformer, `experiments/2026-09-27-R-06-expression-model-h2h/`: quality tie on unseen pieces, SyMuPe chosen by the pre-registered tie-break; likelihood prefers deadpans. Pianist Transformer vs ScorePerformer vs DExter:
  code status, license, fit on a 5080.
- **R-07 Train or fine-tune the expression model** (L). blocked_by: R-06, D-03, O-03.
  owner: ml-researcher. status: done, verdict Confirmed with caveats (audited 2026-10-05; run on the
  RTX 5080, results in origin/main 881f9f9; author fixes AUDIT section 9 after the merge; box
  checks B1-B4 are OWNER). Pre-registered in `experiments/2026-09-28-R-07-symupe-finetune/` (SyMuPe EncDec-base primary,
  flat model F for the likelihood-ratio score, Pianist Transformer secondary arm). Split fixed by
  work in `split/pieces.csv` (test = P, V, A, R10u = 76 R-02 pieces unseen by SyMuPe pretraining,
  R10s; val 59 works; quarantine 81 alias ids). Job folder `job/` ran end to end on the Mac CPU
  (dry run: prep with leakage check, train, stop, resume, F, PT, calibrate, eval on 2 held-out
  pieces). Typicality pass criteria are written (R1 deadpan battery, R2 noise, R3 Vienna).
  paths: `experiments/2026-09-28-R-07-symupe-finetune/`, `src/pianolens/models/expression_split.py`,
  `src/pianolens/models/expression_data.py`, `tests/models/`.
- **R-10 H1b: score-conditioned predictability of expert expression** (L). blocked_by: R-06, R-02 audit, R-07 (all done).
  owner: ml-researcher. status: pre-registered 2026-10-05, job prepared and dry-run on the Mac;
  status 2026-10-06: done, verdict Confirmed with caveats (scoped): H1b falsified for frozen SyMuPe (DECISIONS 2026-10-06); author text fixes in progress.
  status 2026-10-10: box run COMPLETE (gen_pt and dev_gen finished 06:24 UTC after a pause and a
  reboot; 0 errors; headline unchanged). Secondary outputs and box logs in `results_box/`; run
  record entry added. Open: post-audit correction 6 (author reports the gen_pt / dev_gen columns).
  Model: frozen SyMuPe;
  metric and fresh-piece design fixed in DECISIONS 2026-10-05 (R-07 after audit).
  paths: `experiments/2026-10-05-R-10-h1b/`.
  - Pre-register.
  - Using R-02's curve cache and a frozen or fine-tuned expression model (SyMuPe / Pianist
    Transformer), measure the held-out variance of expert curves that the model explains, on
    unseen pieces.
  - Split it into the part shared across performers and the individual part.
- **A-01 Transcription baseline on phone-like audio** (M). owner: audio-engineer. status: done (2026-09-28, resumed after pause; spec `docs/specs/phone-audio-baseline.md`; reports in `data/interim/reports/henry/`, gitignored). Transkun vs Aria-AMT, on rendered +
  convolved MIDI.
- **A-02 Synthetic phone-audio augmentation + fine-tune** (L). blocked_by: A-01, O-03.
- **A-03 Loudness calibration protocol** (M).
- **R-08 LLM score analysis validated on Batik annotations** (M). blocked_by: D-04.
- **R-08a LLM phrase-analysis pilot** (S). blocked_by: D-11, F-05c. owner: ml-researcher. status: in progress (preparation done 2026-09-28: pre-registered, blind inputs, scorer; waiting for the blind annotator run, then `score.py --llm`). paths: `experiments/2026-09-28-R-08a-llm-phrase-pilot/`.
  - Pre-registered. A subagent (Claude, in-session, no API spend) reads a compact score rendering
    (bars, voices, harmony-relevant pitches, durations, markings) of about 5 held-out Batik
    movements and marks phrase ends and cadence types.
  - Score against the DCML annotations with the F-05c harness (±1 beat / ±1 bar, per cadence type).
    Compare with the cadence detector's 0.46 and the proxy's 0.29 on the same movements.
  - The go bar for a full R-08 is 0.7 end F1 at ±1 beat.
  - The annotator must be blind to the DCML labels: it may not read the annotation files.
- **R-08b LLM phrase analysis: memorisation control** (S). blocked_by: R-08a. owner: ml-researcher. status: in progress (preparation done 2026-09-28: R-08a post-audit corrections appended; R-08b pre-registered; disguised blind inputs in `blind_input_disguised/` pass the leakage, identity and transposition checks; `score.py --harness` PASSED. Waiting for the lead to run 5 condition A + 10 condition B blind annotators, then `score.py --llm-dir ... --condition A|B`, `recognition.json`, `score.py --compare`). paths: `experiments/2026-09-28-R-08a-llm-phrase-pilot/README.md` (post-audit section), `experiments/2026-09-28-R-08b-llm-memorisation-control/`.
  - Pre-registered. Covers: README text fixes from the R-08a audit; disguised renderings of the same
    5 movements (transpose to a random key and respell; remove tempo words and dynamics; offset bar
    numbers; keep the leakage check); 2 independent blind reruns per movement for variance; a
    lit-scout/data-engineer check for lesser-known DCML-style phrase-labelled corpora.
  - Pass rule, fixed in advance: disguised mean end F1 of at least 0.70, and no more than 0.10
    below the undisguised run.
- **D-12 DCML jc_bach_sonatas loader + leakage-safe renderer path** (S). blocked_by: R-08b. owner: data-engineer. status: done 2026-09-28 (not committed). paths: `data/raw/dcml_jc_bach/`, `src/pianolens/data/dcml_jc_bach.py`, `tests/data/test_dcml_jc_bach.py`, `scripts/check_dcml_jc_bach.py`, `scripts/build_piece_ids.py`, `DATASETS.md`.
  - Result: v2.4 commit ac9fd07, 38 MB, 29/29 movements load. The score is built from the label-free ms3 TSVs (notes, measures, chords) only;
    the R-08a renderer on all 29 contains no label string (`scripts/check_dcml_jc_bach.py`: LEAKAGE CHECK PASSED, plus tests with a planted-label control).
    `phrase_annotations` returns Batik's `PhraseAnnotations`. 442 phrase ends / 406 cadences folded. F-05c detector runs: mean end F1 +-1 beat 0.427
    (grid4 0.273); comparators and a `cands.pkl` in F-05c layout are in `data/interim/dcml_jc_bach/`. Pilot-size candidates per stratum: DATASETS.md notes and the D-12 report.
  - Not in the TSVs: fermatas (15), hairpins, engraved rests (derived), key mode.
  - Metadata and small TSVs; CC BY-NC-SA 4.0.
  - The MuseScore files embed labels, so the renderer must never read label elements.
  - Register the dataset in DATASETS.md.
- **R-08c LLM phrase analysis on unfamiliar repertoire** (S). blocked_by: D-12. owner: ml-researcher. status: in progress (preparation done 2026-09-28: pre-registered, sha256 ef243096...; blind inputs Q1-Q5 in `blind_input/` pass the leakage and identity check; `score.py --harness` PASSED. Waiting for the lead to run 2 x 5 blind annotators from copies of `blind_input/` outside the repo, then `score.py --llm-dir ... --run R1|R2`, `recognition.json`, `score.py --compare`). paths: `experiments/2026-09-28-R-08c-llm-unfamiliar-repertoire/`.
  - Pre-registered, same protocol as R-08a/b: blind annotators, detector comparator, the same 0.70
    go bar, and a within-piece recognition analysis only.
  - This is required before LLM boundaries are generalized beyond Classical sonatas.
- **D-13 DCML Romantic corpora loader** (S). blocked_by: D-12. owner: data-engineer. status: done 2026-09-28 (not committed). paths: `data/raw/dcml_{chopin_mazurkas,grieg_lyric_pieces,tchaikovsky_seasons,schumann_kinderszenen,liszt_pelerinage}/`, `src/pianolens/data/dcml.py`, `src/pianolens/data/dcml_jc_bach.py`, `tests/data/test_dcml.py`, `scripts/check_dcml_romantic.py`, `scripts/build_piece_ids.py`, `DATASETS.md`.
  - Result: 5 sparse clones at release tags (1.4-12 MB each, TSVs only). Shared loader `pianolens.data.dcml`; `dcml_jc_bach` is a wrapper with byte-identical outputs. 166/166 movements load (165 labelled). Leakage check PASSED on all 165 R-08a renderings (after normalising "Tempo I" and Liszt's "una chorda"); planted-label control per corpus.
    Per-movement table with eligibility (>= 5 phrase ends; simple meter) and F-05c comparators in `data/interim/dcml_romantic/`: eligible 52 / 53 / 12 / 10 / 19, of which simple meter 52 / 45 / 9 / 10 / 8 (Chopin / Grieg / Tchaikovsky / Schumann / Liszt). Detector end F1 +-1 beat on eligible: 0.341 / 0.307 / 0.181 / 0.420 / 0.227.
  - ms3 unfolds 2 mazurkas wrongly (stops at the Fine before the D.C.) and 2 not at all; the loader handles them (hand-checked, flagged `unfold_validated=False`).
  - Generalise `dcml_jc_bach` to the 5 R-08d corpora: handle extra TSV columns such as `special`.
  - Keep the label-free path, and re-run the leakage test per corpus.
  - Register in DATASETS.md.
  - Compute detector comparators per movement.
- **R-08d LLM phrase analysis on Romantic repertoire** (S). blocked_by: R-08c. owner: ml-researcher. status: in progress (preparation done 2026-09-28: pre-registered, sha256 dbef84ae...; blind inputs R1-R5 in `blind_input/` pass the leakage and identity check; `score.py --harness` PASSED. Waiting for the lead to run 2 x 5 blind annotators (runs A and B) from copies of `blind_input/` outside the repo, then `score.py --llm-dir ... --run A|B`, `recognition.json`, `score.py --compare`). paths: `experiments/2026-09-28-R-08d-llm-romantic-repertoire/`. step 1 done 2026-09-28 (lit-scout): 9 DCML Romantic piano corpora carry `}` phrase ends and cadences, all released 2025-04-27 (pre-cutoff), CC BY-NC-SA 4.0; none post-cutoff. Recommended pool and draw: `docs/research/2026-09-27-landscape.md` section 2.1.
  - First, lit-scout / data-engineer checks which DCML (or other) Romantic corpora carry phrase
    labels.
  - If none do, labels made after the cutoff are an OWNER task.
  - Same protocol as R-08a-c. It is required before LLM boundaries feed H4/R-09 on target repertoire.
- **O-03 OWNER: GPU box ready.** CUDA 12.8+ PyTorch on the 5080; SSH or a sync method agreed.
  For R-07 (details in `experiments/2026-09-28-R-07-symupe-finetune/job/README.md`), Henry needs:
  an NVIDIA driver that supports CUDA 12.8+, `git`, `curl`, `uv`; about 40 GB free disk; `tmux`;
  then copy the repo code (no data) to the box, run `setup.sh`, `setup.sh pt`, `fetch_data.sh`,
  `STAGES="prep tokenize" run.sh`, `STAGES=calibrate run.sh`, and send `calibrate.json` to the lead
  before the full `run.sh` (and to decide whether the sync method is SSH from the Mac or manual).
- **O-04 OWNER: approve any cloud GPU spend.**
- **O-05 OWNER: longitudinal practice log** (Phase 7).

## Literature

- **L-01 Verify the [U] items in the landscape doc** (M). owner: lit-scout. status: done. Fix or remove each one.
- **L-02 CrescendAI deep dive** (S). owner: lit-scout. status: done. What exactly they built, their splits, results and gaps.
  Where do we differ?
- **L-04 Evenness and pedalling literature** (S). owner: lit-scout. status: done 2026-09-27 (landscape section 1.5, including the F-04 citation map; the docstring edits are for feature-engineer). Sources on scale and Alberti evenness (e.g.
  MIDI studies of scale playing by Jabusch, Furuya, Goebl) and on pedalling technique relative to
  harmony changes. Add them to the landscape doc; give the F-04 docstrings citations to update.
- **L-03 Watch list** (S, recurring). owner: lit-scout. methods pass 2026-09-28 (landscape section 6; CJ line in 1.4 corrected). last watch pass 2026-09-27: SKY-Piano, Profy, Delta-VA, MuSP-Bench and a dual transcription evaluation added. New 2026 papers on piano assessment; add them to the
  landscape doc.

## Log

- 2026-09-27: board created by the lead session. ASAP and PercePiano cloned to `data/raw/`.
- 2026-09-27: E-01 done (ml-researcher). `pianolens.eval`: grouped K-fold, cluster bootstrap,
  R2/Spearman/Kendall/pairwise accuracy, rater parity, Bradley-Terry; 23 tests in `tests/eval/`.
- 2026-09-27: R-01 run (ml-researcher). H2 Provisional supported: PCA-PA retains 4 factors on
  PercePiano segment means. Needs eval-auditor.
- 2026-09-27: D-01 done (data-engineer). `pianolens.data.types` + `pianolens.data.asap`: 1,066/1,066
  ASAP performances + scores loaded, 1,063 with ground-truth alignment (3 have none); counts and
  quirks in DATASETS.md; `scripts/check_asap.py` reproduces them.
- 2026-09-27: L-01, L-02 Done (lit-scout).
  - Corrections applied by the lead to the plan (Repp citation, the 93% confound, the H1 count,
    H8 and MAJEPPA) and to R-03 and R-05.
  - R-06 survey written; the shortlist is recorded in DECISIONS.md.
- 2026-09-27: D-02 done (data-engineer). `pianolens.data.percepiano`: 1,202/1,202 segments + segment
  scores; per-rater ratings (63 raters, 1,189 rated segments) and the authors' mean labels
  (reproduced exactly); 25 human performer ids; bar ranges for 337 segments. Quirks in DATASETS.md.
- 2026-09-27: R-01 post-audit fixes (ml-researcher). `run.py` re-orders factor-analyzer's `phi_`
  and computes communalities as diag(L Phi L'); rerun reproduces all counts. README: h2 corrected
  (mean 76%), no Heywood case, k=4 F1-F3 r 0.49, verdict now "3-5 factors, one dominant general
  factor, falsifier never met" (FA-PA 7 inconclusive; pedal merge 3; no Score 5). Still
  Confirmed with caveats.
- 2026-09-27: D-03 done (data-engineer 2). PianoCoRe Zenodo v1.0 (6.2 GB: metadata + refined +
  raw-midi zips); `pianolens.data.pianocore` yields tier A/A* performances with RAScoP note
  alignments (index order is (tick, pitch), not partitura ids). Per-piece table in
  `data/processed/pianocore_piece_counts.csv`, top 50 in DATASETS.md. Tier A: 157,207 perfs,
  1,591 pieces, 730 with 50+.
- 2026-09-27: D-04 review / D-05 blocked (data-engineer 2). Downloaded and loaders + smoke tests for
  Expert-Novice, NeuroPiano, Vienna 4x22, Batik, MazurkaBL, PianoJudges labels, MAESTRO v3 MIDI,
  PSyllabus, MAJEPPA (found on HF, 4,449 perfs). Gated: CIPI scores (Zenodo restricted; labels
  are in the PianoJudges repo), MAESTRO-E (Globus login). BACKLOG BL-04..BL-09.
- 2026-09-27: F-01 done (feature-engineer). `pianolens.align.align` = parangonar DualDTW +
  automatic repeat-variant choice; validated on all 1063 (n)ASAP performances with ground truth
  (3 have no TSV). Match F1 per composer (mean / robust-only; n): Bach 0.988/0.988 (169),
  Balakirev 0.972/0.972 (10), Beethoven 0.970/0.984 (268), Brahms 0.972 (1), Chopin 0.978/0.986
  (289), Debussy 0.960/0.982 (3), Glinka 0.884/n.a. (2), Haydn 0.990/0.993 (44), Liszt
  0.920/0.951 (121), Mozart 0.992/0.994 (16), Prokofiev 0.964/n.a. (8), Rachmaninoff 0.947/0.997
  (8), Ravel 0.886/0.983 (22), Schubert 0.951/0.970 (61), Schumann 0.938/0.953 (28), Scriabin
  0.782/0.961 (13); all 0.964 mean, 0.987 median, 0.981 robust. Insertion F1 0.855, deletion F1
  0.752. Repeat variant right in 86/99 multi-path performances. Align time median 11.3 s, max
  202 s per performance. Nakamura's tool builds on arm64; cross-check on 879 single-path
  performances: 0.954 vs DualDTW 0.968 (it crashed on 85). Downbeat-annotation check shows
  most F1 < 0.9 cases are ground-truth errors. Details: `docs/specs/alignment-validation.md`.
- 2026-09-27: D-07 done (data-engineer 3). `types.BeatCurve` (MazurkaBL `load_beat_curves`),
  `ALIGNMENT_LABELS` with `interpolated`, `Alignment.interpolated` / `.paired` (`matches` still
  excludes interpolated). `make_piece_id` folds accents (0 existing ids changed). MAJEPPA scores
  now get canonical ids (655 of 886). `data/processed/piece_ids.parquet` (6,823 rows, 515
  canonical ids in 2+ datasets). PianoCoRe tier A cache `data/processed/pianocore_A/`: 157,207
  performances, 0 failures, 377.8 M rows, 4.1 GB, 29 min on 12 workers, ~0.03 s to load the
  largest piece. BL-08, BL-09 resolved.
- 2026-09-27: S-02 done (ml-researcher). `pianolens.audio.render`: Salamander C5 Light SF2 (CrescendAI's file) via
  FluidSynth 2.6.1 with pinned settings, 24 kHz mono, deterministic; 8 tests in `tests/audio/`. 1,202 PercePiano renders in
  `data/interim/renders/salc5light2-fc5f24d36e3e/percepiano/`. pyproject: `muq`, `transformers>=4.45,<5` (torch extra), `soxr` (audio extra).
- 2026-09-27: R-03 run (ml-researcher). H3a Provisional: CrescendAI protocol reproduced at R² 0.509 (vs 0.536); honest
  inner-validation 0.460; leave-work-out pooled R² -0.087, within-passage pair acc 0.620. Needs eval-auditor.
- 2026-09-27: D-08 done (feature-engineer). `pianolens.data.perturb.perturb(performance, alignment, spec, seed)`
  injects wrong-pitch (±1/±2, ±12), extra (neighbour-key slips, short and soft) and missed notes (biased to
  inner voices / fast passages), plus optional timing / velocity / tempo perturbation for S-01. Exact
  per-note ground truth. The mistake model follows the MAESTRO-E generator (differences are in the docstring).
  `data/processed/mistakes_v1`: 100 robust single-path (n)ASAP performances x (clean, 0.02, 0.05, 0.10),
  12 composers, 21 MB, 53 s build. 15 tests.
- 2026-09-27: F-02 done (feature-engineer). `pianolens.features.correctness.correctness(aligned)`: per-note
  correct / extra / missed / wrong_pitch (ins+del pair within 50 ms of the expected onset, ≤2 semitones or an
  octave), ornament / grace whitelist, interpolated excluded, per-bar table, summary. 14 tests. On
  mistakes_v1 through `align_performance` (P / R / F1, pooled; don't care = natural (n)ASAP ins/del):

  | Level | Type | rate 0.02 | rate 0.05 | rate 0.10 |
  |---|---|---|---|---|
  | note | wrong pitch | .939/.838/.886 | .956/.813/.879 | .965/.774/.859 |
  | note | extra | .587/.922/.717 | .718/.922/.808 | .753/.895/.818 |
  | note | missed | .378/.910/.535 | .568/.902/.697 | .669/.876/.759 |
  | bar | wrong pitch | 1.00/.866/.928 | .998/.858/.922 | .999/.847/.917 |
  | bar | extra | .872/.925/.898 | .909/.938/.924 | .931/.940/.936 |
  | bar | missed | .902/.960/.930 | .928/.959/.943 | .946/.962/.954 |
  | bar | any | .978/.977/.977 | .989/.984/.987 | .993/.986/.989 |

  Noise floor on the clean copies: 3.1 extra, 0.26 wrong-pitch and 8.4 missed false positives per
  1,000 notes; 7.2 / 6.3 / 0 bars per 1,000 flagged for extra / missed / wrong pitch. Per-note missed
  labels are unreliable (repeated-pitch ambiguity), so report them per bar. The 100 ms window raises
  bar wrong-pitch F1 to 0.942 at rate 0.05. Caveats: the mistakes are synthetic; bar metrics exclude the
  46% of bars that hold natural ground-truth mistakes. Details: `docs/specs/correctness-validation.md`.
- 2026-09-27: F-03 done (feature-engineer). `pianolens.features.tempo_model(ap)`: chords collapse to
  the median matched onset; robust P-spline time map (order-3 penalty, so constant tempo and linear
  rit./accel. are unpenalized) with a 1.5-bar half-gain cutoff; residual = jitter, also reported
  net of the performance's own within-bar pattern; per-position, per-note, per-beat-grid and
  per-bar tables. Breaks: score tempo words / a tempo / metronome jumps (split), fermatas and
  detected pauses (gap), detected tempo steps (reported, split on request); gross misalignments
  flagged. Synthetic tests: deadpan 0 ms, linear ritardando recovered to 1e-5 s/beat, 20 ms noise
  -> 17-23 ms, 60->90 BPM step located exactly. (n)ASAP Op. 10 No. 12, 6 performances: smooth
  tempo 133-147 BPM (quarter), log-tempo SD 0.14-0.17, jitter RMS 46-67 ms / MAD 32-46 ms, curves
  correlate 0.56-0.75 across performers. Residuals also correlate across performers (about 0.59
  mean), so they hold shared, score-driven timing, not only noise. Figure and CSVs:
  `data/interim/tempo_f03/`.
- 2026-09-27: R-03 post-audit corrections applied (ml-researcher), reporting only, no re-extraction.
  README gains fold-mean R² for (a) (0.491 vs their 0.530), D960-merged rows (-0.031 / 0.046 / 0.618,
  reproducing the auditor), no-Score rows (-0.163 / 0.063 / 0.590 under (c)), and the parity rewording
  ("roughly matches a single rater" under leave-work-out; ties and seed-ensembling stated). New
  `postaudit.py`; merged and no-Score OOF predictions for R-04 paired tests in
  `artifacts/oof_predictions_postaudit.npz`.
- 2026-09-27: F-05 done (feature-engineer). `score_basis(score)`: Basis-Mixer-style features in
  10 groups (metrical, pitch/skyline melody, duration, dynamics, articulation, tempo marks,
  fermata, phrase proxy or external boundaries, tonal tension, position). `shaping(ap)`:
  structural coherence (ridge, nested CV on 4-written-bar blocks + 1-bar buffer; R2 with and
  without markings; pooled version), repeated-material consistency, voicing (vel diff + lead),
  dynamic-marking compliance; all per bar + summary. D.899/3, 6 ASAP perfs: velocity R2 0.41
  (0.33 without markings), timing 0.12, smooth tempo 0.05, articulation 0.20; repeats velocity
  r 0.77; melody +20 vel. CSVs: `data/interim/shaping_f05/`.
- 2026-09-27: L-04 done (lit-scout). Landscape section 1.5: scale-evenness, velocity, pedalling and hand-asynchrony sources with reference ranges, plus the F-04 citation map. No published pedal-timing norms were found. L-03 pass: 5 new items.
- 2026-09-27: R-04 run (ml-researcher). H3 Provisional **supported (matches, not beats)**: under leave-work-out
  the own-performance symbolic model (S0) is non-inferior to frozen MuQ on WP pair acc and WP Spearman in all
  four variants (4/3 works x with/without Score): WP acc 0.624 vs 0.623, 0.614 vs 0.619, 0.595 vs 0.594,
  0.585 vs 0.587. Transductive S1 0.635 / 0.630; late fusion 0.638 / 0.633 (beats both). New
  `pianolens.features.extract` (batch helper, 6 tests). Bug fix in `data/types.py`: multi-track MIDI had
  duplicate performance note ids (all 124 PercePiano Score renditions); test added. Features use F-04b
  `control.py`. Needs eval-auditor.
- 2026-09-27: R-04 post-audit corrections applied (ml-researcher), text only, no reruns. README gains a
  "Post-audit corrections" section: headroom claim withdrawn (single-rater level; Spearman-Brown ceiling WP
  rho about 0.74 vs about 0.35), note-rate deviation disclosed with the auditor's 60-feature refit (still
  non-inferior in 8/8 cells), per-work paired S0 − MuQ table (D935 −0.023 [−0.043, −0.004]) and margin
  sensitivity (holds at 0.015/0.035, fails at 0.01/0.03), DECISIONS headline wording verbatim. In-place edits
  flagged; pre-registered first 217 lines unchanged (sha256 re-verified).
- 2026-09-27: R-02 run (ml-researcher). H1 Provisional: not supported, not falsified. 730 pieces / 137,517 PianoCoRe
  tier A performances, curves via F-03 `tempo_from_onsets`. Joint tempo + velocity at n = 50 (698 pieces): 19 components
  for 80% in-sample (tempo 13, velocity 16); held-out R² 0.31 / 0.42 at k = 10 / 20; phase-randomized null 25. Disklavier
  and Vienna 4x22 controls are not lower-dimensional. New `pianolens.eval.dimensionality` (+9 tests). Needs eval-auditor.
- 2026-09-28: R-06 head-to-head run (ml-researcher). Provisional. Frozen, on PercePiano WoO 80 / D960 segments unseen by both (981 renditions): per-note composite r SyMuPe 0.388 vs Pianist Transformer 0.393 (diff -0.005 [-0.025, 0.016]), both far above the ridge (0.166); SyMuPe chosen by the pre-registered tie-break (jitter AUC +0.008). SyMuPe's lead on seen sets (ASAP, Vienna) vanishes on unseen pieces. H1b preview: frozen models explain at most ~30% of the mean velocity curve and ~0% of timing. Teacher-forced likelihood catches jitter (AUC ≥ 0.94) but ranks deadpans above every expert (AUC 0.00). New `pianolens.models.expression_io` (+6 tests); model envs gitignored (`.gitignore` gains `experiments/*/envs/`); weights recorded in DATASETS.md. Needs eval-auditor.
- 2026-09-28: R-06 post-audit corrections applied (ml-researcher), text only, no reruns. README gains a "Post-audit corrections (2026-09-28)" section: c2 vs synthetic deadpan on P is a fail (CI wholly below 0.5), not inconclusive; H1b bullet split (timing at falsification level for both, velocity at falsification level for SyMuPe and inconclusive for PT, r² 0.35-0.37 vs ridge 0.20); per-work / per-target paired CIs added to (a); two-way tie-break CI [0.0027, 0.0129]; Deviations 1-2 reworded (fixes followed a partial trial run at 02:44, forced not outcome-driven); speed 5.7x idle / 2.1x loaded. In-place edits flagged; pre-registered first 160 lines unchanged (sha256 re-verified). EXPERIMENTS.md row result text updated.
- 2026-09-27: D-11 + F-05c done (feature-engineer). D-11: Batik loader returns the MusicXML performed score
  (markings, same ids/beats) and DCML phrase/cadence tables in performed-score beats (+3 tests); F-05b script uses it.
  F-05c: new `features/cadence.py` (21-cue logistic cadence detector fitted on K.279-283), `shaping.phrase_tempo_shaping`
  (per-phrase parabolas, concave share, arc R², ±2-bar shifted null, per-bar/per-phrase), opt-in
  `BasisConfig.phrase_source="cadence"` (default unchanged). Held out (21 mvts): end F1 0.46 vs 0.29 proxy (±1 beat);
  tempo R² cad 0.067 vs proxy 0.097 vs annotated 0.149, Vienna -0.40 vs -0.27 vs 0.375: tempo coherence still needs
  annotations. Concave excess over null: annotated +0.42, cadence +0.21, proxy +0.24, grid -0.01. +7 tests.
- 2026-09-27: F-06 done (feature-engineer). `features/interpretation.py`: reference sets (R-02 curve cache or
  rebuilt from PianoCoRe; LOO by performance or source id; Disklavier/sensor-only velocity refs when >= 8, else
  flagged low-confidence), piecewise score-beat mapping (repeats, pickups), per-16-bar-window shared core (Horn PA vs
  envelope null at n = 50), typicality = likelihood of shared coords + log magnitude (deadpan-safe), too_flat /
  too_extreme, per-bar out-of-band flags vs cross-fitted refs, expert band, S1 ref features (`curve_agreement`
  promoted from extract). Op.10/3 LOO calibration (40 refs x 5 windows): typicality < 0.05 in 6.0% / 6.5% of
  windows, bar flag rate 5.2% / 6.1% (tempo / velocity); deadpans: tempo typicality <= 0.004, too_flat 100%. +26 tests.
- 2026-09-28: R-08a preparation (ml-researcher). Pre-registered; seeded draw kv330_2, kv333_1, kv533_1,
  kv330_3, kv457_3 (M1-M5); label-free renderings in `blind_input/` (leakage check passed); `score.py`
  reproduces F-05c's detector rows exactly. Detector on these 5: end F1 ±1 beat 0.565, HC recall 18/62.
  Annotation not yet run.
- 2026-09-28: lead. R-08a blind annotations were collected from 5 independent annotators (copied to
  `artifacts/llm_annotations/`) and scored: LLM end F1 0.817 vs detector 0.565 (Provisional, under
  audit). Still in flight: F-08, R-09, F-07, S-01/S-03, R-07 prep, R-08a audit. See STATUS.md "How
  to resume".
- 2026-09-28: R-09 run (ml-researcher). H4 on MAJEPPA Provisional **inconclusive** by the pre-registered rule. Matched
  contexts (practice + performance, 388 perfs / 106 pieces, piece + context FE, note rate + duration): coherence R² per
  skill-level step articulation +0.008 (97.5% CI -0.019 to 0.034), timing residual +0.005 (-0.014 to 0.021); not
  monotone (advanced below beginners in both). The only CI excluding 0 is timing in the context-confounded pooled model
  (advanced - beginner +0.037, 0.010 to 0.059); it vanishes with context control, as in D-10. Leave-piece-out: coherence
  lowers skill-rank pair accuracy vs note-rate covariates (-0.061, -0.106 to -0.017). Noise floor (65 D-10 pairs):
  timing coherence survives transcription (median |diff| 0.008, Spearman 0.95), articulation does not (0.080, 0.36).
  `n_blocks >= 3` admits 8-bar scores numbered 0-8 (R² down to -80); verdict unchanged without them. Needs eval-auditor.
- 2026-09-28: F-08 done (feature-engineer). `pianolens.report` + `scripts/pianolens_report.py`: MIDI (+ score or
  piece id, + same-score refs, + takes) -> self-contained HTML (inline SVG, light/dark, no URLs) + JSON. Correctness tiers
  calibrated on clean D-08 copies (`scripts/calibrate_report_f08.py`: 42% of expert bars have a flagged note; notable = 2
  wrong notes or missed+extra > 0.27/note, strong = 3 or > 0.63). Samples in `data/interim/reports/`: (c) D-08 5% + 30 ms
  jitter: error rate 7.0% -> 11.5%, 100% of 56 injected bars flagged, 91% show more errors than (a); (d) deadpan: tempo
  and velocity too flat (strong) in all 5 windows, practise item 1 = "too flat". Open: SunMeiting08 (Disklavier) has 20%
  of bars outside the transcribed-reference timing range vs 6.7% for references as targets (lead to review).
- 2026-09-28: R-08b preparation (ml-researcher). R-08a README: `## Post-audit corrections` (run record, t-interval, `llm_no_propagation` as a construction check, oracle not a strict ceiling, verdict); header hash unchanged. R-08b pre-registered (pass: disguised mean end F1 ≥ 0.70 and ≥ undisguised − 0.10). `disguise.py` (imports R-08a's renderer) and `score.py`; all checks and the harness pass. DCMLab phrase-labelled corpora: `jc_bach_sonatas` (29 pieces, 442 phrase ends) is the best unfamiliar-repertoire candidate; `kozeluh_sonatas` has no phrase or cadence labels.
- 2026-09-27: S-01 done (study-designer). `pianolens.study.degrade`: timing jitter (per score position, s.d. in ms or
  relative to the local IOI), smooth-tempo flattening (F-03 time-map warp, residual kept in beats), dynamics flattening
  and voicing scaling (velocity = mean + dynamics + voicing term, skyline melody, local gap), pedal blur (F-04b harmony
  changes; graded by share of changes or by a late pedal change), articulation scaling, wrong notes (via D-08
  `perturb`). Every result reports the change in physical units and, for timing and velocity, the ratio to the
  landscape 1.5 thresholds (IOI CV 0.08; JND 2.71-4.48). `perturb.py` unchanged. 23 known-answer tests.
- 2026-09-27: S-03 design and build done (study-designer). Protocol `study/protocol-S03.md` (H6 reading: cost per
  detection-threshold unit, margin 2; consent DRAFT; pilot plan). 592 pilot clips (8 excerpts from Vienna 4x22,
  Batik, (n)ASAP x 7 dimensions x 5 levels x 2 spans), -23 LUFS, peak <= 0.674, 94 s build. Static app `study/app/`
  (headphone check, practice, catch trials, balanced positions, seeded order, JSON export, no network); headless
  Chrome smoke test passes (main, pilot, parts A/B). Power simulation (assumed parameters): 96 listeners (one pass,
  ~75 min each) give 0.92 power for a three-fold cost difference; falsifying H6 needs ~160 (or 96 doing it twice).
  DATASETS.md gains the study_s03 row.
- 2026-09-28: lead. DISPATCHED (was pending on the 20-agent concurrency cap): R-09 post-audit text fixes.
  These are the 6 fixes in the R-09 README Audit section, plus a post-audit note in
  `docs/specs/skill-control-check.md` about the top-level/context confound.
- 2026-09-28: R-09 post-audit text fixes done (ml-researcher). README: the 6 fixes applied in place, flagged
  *[Post-audit fix N]*, and listed under `## Post-audit corrections (2026-09-28)` (S8 "adds nothing", -0.032
  [-0.074, +0.012] at >= 12 bars; pooled timing effect = teacher/virtuoso clips, levels 1-4 +0.018 [-0.020, 0.062];
  noise-floor claims qualified as Aria-AMT, Transkun unresolved; power note 8% / 16%; post-prereg smoke tests
  disclosed; code hash prefixes and noise_floor worker count corrected). Header hash c44a4b74...8517 re-verified.
  `docs/specs/skill-control-check.md` gains a post-audit note; EXPERIMENTS R-09 row updated. Text only, no rerun.
- 2026-09-28: R-07 job prep (ml-researcher). Status in progress, blocked on O-03. Pre-registered fine-tune of SyMuPe EncDec-base on PianoCoRe tier A + (n)ASAP with a work-level split (`split/pieces.csv`; 129 test works incl. all PercePiano and Vienna works, the R-06 A folders, 75 R10u works holding the 76 R-02 pieces with no paired PERiScoPe performance, 24 R10s; alias quarantine; leakage check fails the prep). Corrected typicality scores S-LR (vs a flat model F), S-TYP (typical-set z), S-DEV (deviation-only r) with exact pass criteria against the R-06 auditor's deadpan variants. Job folder (setup / fetch / run / eval, torch 2.7.1 cu128) dry-ran end to end on the Mac CPU, incl. stop and resume. New `pianolens.models.expression_split` and `expression_data` (+13 tests).
- 2026-09-28: lead. R-08b: all 15 blind annotations are saved in `annotations_A/B1/B2`,
  `recognition.json` is filled, and `score.py --compare` was run. Result: PASS (disguised 0.802 vs
  undisguised 0.789; 0 of 5 disguised recognised). Provisional; eval-auditor dispatched.
- 2026-09-28: L-03 methods pass (lit-scout). Landscape section 6 "Methods references": Woods 2017, Milne 2021, Bradley-Terry 1952, Wichmann-Hill 2001, Cameron-Miller 2015, Schuirmann 1987, Berger 1982, Spearman/Brown 1910, McGraw-Wong 1996, Shrout-Fleiss 1979, Horn 1965, Green et al. 2012, Ledoit-Wolf 2004, Theiler 1992, Eilers-Marx 1996, Eilers 2003. **Correction:** the CJ "12 comparisons give .70, 17 give .80" is in neither Kinnear 2025 nor Verhavert 2019; `rules/study.md` and plan Phase 4 ("12-17 comparisons per item") rest on it. Lead to decide the new target.
- 2026-09-28: F-08b (feature-engineer). Timing provenance: 64 D-10 pairs, Disklavier not over-flagged (tempo notable+/strong 4.3/0.9% vs transcribed twin 4.5/1.0%; timing 4.2/1.2% vs 4.7/1.3%; paired CIs include 0); timing flags leave "experimental", no correction. Recurring errors: naive rule fires on 24-31% of expert bars; implemented wrong-pitch-only + expert-artefact filter (0.18%/0.51%), needs >= 2 expert recordings. Correctness-first ranking. Sample (e) passes. pytest 372 passed, ruff clean.
- 2026-09-28: F-07 (feature-engineer). `features/takes.py`: take-consistent vs take-specific split per channel (ICC(3,1), Spearman-Brown), per-bar + per-take-bar output, pairwise half-sum/half-difference structure test, `takes_from_files` for Henry's MIDI; +10 tests. H5 on PianoCoRe A (1,390 same-pianist groups, 91 pianists, dedup r > 0.98): timing R² sum 0.123 vs diff 0.005, delta 0.118 [0.110, 0.126]: supported (Provisional); ASAP Disklavier timing delta 0.075 [0.053, 0.098].
- 2026-09-28: R-08c preparation (ml-researcher). Pre-registered (README hash ef243096...7796). 21 eligible J. C. Bach movements (op. 5 nos. 2-4 excluded), 5 rendered-size strata, seeded draw 20260930: Q1 wa06op05no6a, Q2 wa06op05no6b, Q3 wa07op17no1a, Q4 wa10op17no4a, Q5 wa12op17no6a. Renderings via R-08a `common.render` on `load_score(tempo_word=False)`; INSTRUCTIONS/SCHEMA = R-08a's with ids M->Q and the worked example moved to bars 25/28 (pre-registered collision rule; 'Classical period' wording kept). Leakage + identity check PASSED (planted cues fire); harness PASSED (oracle 1.000; detector via events = D-12 rows; dry run). Detector on the 5: 0.437. Finding: the detector is not pass-consistent on Q4/Q5, so it scores 0.560/0.522 through the annotation path vs 0.541/0.527 on its own; comparator stays its own score. Not committed.
- 2026-09-28: F-07 post-audit corrections (feature-engineer), text only. README: new "Post-audit corrections (2026-09-28)" section; flagged in-place edits: cross-pianist control table in Results (delta same 0.121 vs different 0.097; R²(diff) 0.011 vs 0.049; paired gap 0.038 [0.030, 0.046]), verdict reworded per DECISIONS (pre-registered H5 passes; take-consistent = piece-shared timing, not intent; supported: take-to-take variation mostly unstructured), "a fifth" -> about 0.16, smoke run disclosed, ASAP/PianoCoRe score-basis threat. Header hash b1f57ae2... unchanged. `takes.py` docstring reworded (no logic change; 10 tests pass, ruff clean). EXPERIMENTS row updated.
- 2026-09-28: D-13 (data-engineer). DCML Romantic corpora downloaded (chopin_mazurkas v3.2, grieg / tchaikovsky / schumann / liszt v2.3; CC BY-NC-SA 4.0) and loaded through the new shared `pianolens.data.dcml` (jc_bach wrapper, outputs identical). 166 movements; notes = ms3 n_onsets in 162/166 after merging gap ties; unfolding = metadata 162/166 (4 mazurkas where ms3 is wrong or empty, hand-checked). LEAKAGE CHECK PASSED on 165 renderings; eligibility and detector comparators per movement in `data/interim/dcml_romantic/`. Piece ids added to `piece_ids.parquet` (all 46 MazurkaBL mazurkas map). pytest 430 passed, 1 skipped; ruff clean. Not committed.
- 2026-09-28: lead. **A-01 PAUSED at Henry's request.** The audio-engineer was stopped mid-run while
  writing the report script. Resume by re-dispatching A-01 with "check existing work first". Look in
  `data/interim/henry_takes/` and any new scripts or `src/pianolens/audio/` files. No other agents
  are running.
- 2026-09-28: A-01 (audio-engineer), resumed; reused all transcriptions and the baseline run. Controlled check (3 MAESTRO Disklavier perfs, S-02 render, phone sim + AAC): transcription adds +1.7 to +3.3 pts F-02 error rate, the phone sim under 1 pt; onset rsd 2.3 ms Transkun / 4.4 ms Aria. Floor (150 PianoCoRe refs): Transkun median error 6.7%, extras 1.3%. Henry's takes: wrong/missed near floor, extras 15-29% on 3 of 5 takes (both models agree), up to 19.5% of score notes at >= G6 on fixed pitches; not reproduced by the phone sim, cause unverified. 10 F-08 reports (Transkun + Aria cross-check) with floor and suspect-extras notes. Timing/tempo tiers stable across transcribers, velocity not. Spec `docs/specs/phone-audio-baseline.md`. pytest 439 passed, 1 skipped; ruff clean. Not committed.
- 2026-09-28: P-01 (feature-engineer). `src/pianolens/compare/` (windows, timemap, experts, clips, engine, player + template), `scripts/build_compare_p01.py`, `tests/compare/` (+10). Reads only the report JSON. Up to 8 windows per report (strong first, merged to <= 4 bars, 1 bar pre/post), clips: user audio cut by isotonic alignment time map, user re-render (S-02, 44.1 kHz), typical expert (closest to window median on tempo/velocity shape + tempo level), contrasting expert (q90 distance); loudness-matched, 20 ms fades, mono MP3 96k; self-contained A/B player (bar-synced switching, loop, light/dark, no requests). Run on Henry's 5 Transkun reports + F-08 (a), (c): 56 windows, 208 clips, all 4 kinds in every Henry window; clip length error < 0.02 ms, ffmpeg decode within 0.9 ms; expert score-span match 1.0 (112/112); original audio vs render lag 0 ms (r 0.78-0.88) on all 5 takes; onset-train lag within 50 ms for 100% of clips (constant ~20 ms detector bias, same on exact renders). Outputs `data/interim/compare/` only. pytest 470 passed, 1 skipped; ruff clean. Not committed.
- 2026-09-28: P-02 (feature-engineer). `src/pianolens/app/` (catalog, jobs, pipeline worker, results, pages, server, static css/js), `scripts/pianolens_app.py`, `tests/app/` (+6), `docs/APP.md`. Stdlib HTTP server on 127.0.0.1 (Host and Origin guards, strict CSP, no external assets or requests); no new dependencies. Piece picker: 584 PianoCoRe tier A pieces with >= 50 refs + 221 ASAP pieces; MusicXML upload for others (no tier D). Upload audio (Transkun 2.0.1 via the A-01 venv) or MIDI, multiple takes; subprocess worker per upload (transcribe -> align check -> report -> clips) with progress and cancel; results cached by upload hash under `data/interim/app/` only. Results: practise items with the A/B player of the best-overlapping window (clips served as files) and window tempo/velocity curves, all passages, full report in an iframe; history with delete. Henry take 04 end to end ~1 min (8 windows, 30 clips; practise bars match the A-01 report). pytest 476 passed, 1 skipped; ruff clean. Not committed.
- 2026-09-28: R-05 (ml-researcher), Provisional, awaiting eval-auditor. H8 substitute design: 1,500 MAJEPPA clips (250 per level), first 30 s of the Transkun MIDI rendered with the S-02 piano, 4 simulated contexts (clean / phone_room / recital_phone / concert_hall: `audio.phone.simulate_phone` + AAC), frozen MuQ L9-12, logistic regression, piece-grouped 5-fold CV. Beginner vs advanced AUC: context fixed 0.870; confounded as in MAJEPPA 0.943 (delta +0.073 [+0.055, +0.092]); confounded model with test contexts permuted 0.730 (delta +0.214 [+0.196, +0.232]); contexts swapped 0.475; negative control +0.002. Context decodable at 0.997. Supported by the pre-registered rule; holds for fold seeds 1-2 and layer 6. Pre-registration hash 7add1490...f0c5; reachability simulated first (falsified reachable only at score correlation about 0.9; observed 0.8). Build 36 min on MPS. pytest 470 passed, 1 skipped; ruff clean. Not committed.
- 2026-09-28: F-08c done (feature-engineer). Per-bar expert check for single-take correctness: a bar must exceed both the global limit and the per-bar q80 (notable) / q99 (strong) of >= 5 same-score experts with the same capture method (ASAP / same-score refs for key-sensor, PianoCoRe transcriptions for transcribed); within-range bars say "matches expert transcriptions here (likely score/edition artefact)". Transcribed input: extras never count toward tiers or practise items (timeline only, low confidence). Calibration `scripts/calibrate_expert_check_f08c.py`: key-sensor expert bars 6.8/1.7% -> 3.7/0.67% (40 clean D-08 copies, 28 pieces); transcribed A-01 floor LOO 11.8/3.0% -> 5.3/1.4%; D-08 rate 0.05 tiered injected bars 18.1% -> 15.5%. Samples (a)-(e) unchanged in practise, (e) passes. Henry: correctness tiered bars 6-76 -> 3-30 per report; Op. 64/2 bar 78 suppressed (experts median 5 wrong), bar 84 new top. pytest 470 passed, 1 skipped; ruff clean. Not committed.
- 2026-09-28: BL-16 (data-engineer), Provisional, awaiting eval-auditor. `src/pianolens/data/rach3_takes.py` (Hanon Part I exercise scores cut from the book MusicXML; exact-pitch fitting DP splits sessions into complete passes and aligns notes; `HanonTakes` loader returns AlignedPerformance), `scripts/build_rach3_hanon_takes.py` -> `data/interim/rach3_hanon_takes/` (2,038 takes, 1,149 QC; 99.5% agreement with parangonar on 24 takes), `tests/data/test_rach3_takes.py` (+5). Beginner same-day infeasible (p3 never repeats an exercise within a day after QC), so the beginner arm is next-day. Experiment `experiments/2026-09-28-BL-16-rach3-takes/` (prereg f9336acc...): timing R²(diff) gap, cross minus same pianist: advanced same day 0.036 [0.013, 0.056] (t [-0.003, 0.048]; p2 0.057, p1 0.003); p3 next day 0.051 [0.039, 0.065]. Take-to-take timing SD 7.5 ms (advanced) vs 11.3 ms (p3); ICC 0.31 vs 0.18. pytest 470 passed, 1 skipped; ruff clean on BL-16 files (4 E501 in `src/pianolens/app/` belong to another in-flight ticket). Not committed.
- 2026-09-29: R-07 started by Henry on the RTX 5080 (another Claude session on that machine runs the job folder). Lead does not touch R-07 files here; results come back via the job's eval outputs.
- 2026-09-29: research-log restructure (lead). `docs/RESEARCH_LOG.md` rewritten as 5 parts + appendix (methods chapters by 7 agents, checked against code); new `docs/SCORING_MODEL.md` (scoring model explainer, second tab); builder makes both pages. Found DF-02..DF-08 and BL-19..BL-22. Wave dispatched: DF-02 (LLM phrase source in report), BL-18 (strong tier on transcribed input), BL-19/BL-20 (tier A gaps), BL-21/BL-22 (audio gaps), BL-17 (Romantic LLM test), DF-03/DF-04 + S-04 design (study), DF-05/DF-06/DF-08 (fixes and stale docs).
- 2026-09-29: DF-02 done (feature-engineer), awaiting lead review. LLM phrase source for the report: `features/phrases_llm.py` (cache + loader + fallback), `score_basis` `phrase_source="llm"`, `scripts/build_llm_phrases.py` (R-08d protocol; 10 blind annotators, file access audited, `data/interim/phrases_llm/_build/`), report `_shaping_section` / shaping text / methods footer disclose source, phrase-count ratio vs detector and caveats. Tests: `tests/features/test_phrases_llm.py`, `tests/report/test_report_llm_phrases.py`; full suite 518 passed. Henry reports rerun to `data/interim/reports/henry_llm/`: concave_excess changes a lot on takes 01 and 05, little on 02-04; no practise item depends on it.
- 2026-09-29: DF-05 / DF-06 / DF-08 (feature-engineer), awaiting lead review. DF-05 (app only): job id includes a code-version hash (`jobs.code_version()`, `PIPELINE_VERSION`); MIDI can be marked transcribed (Transkun or other; read like audio input, optional A-01b filter); the quick alignment check stops the run below Dice 0.5 (state `stopped`, "Analyse anyway" override, upload-form override), threshold from a measurement (right score 0.818-0.984, wrong score 0.083-0.314 over 32 pairs; Henry's Transkun takes + 4 ASAP performances); same-score ASAP references only for key-captured MIDI of pieces with no PianoCoRe refs and >= 10 ASAP performances (4 pieces; Haydn 50/1: evenness tiered 5/150 bars, no extra runtime), with the double-counting reason and a report/ follow-up in DEFECTS and docs/APP.md; APP.md formats (aac, ogg) and upload hint fixed; 127.0.0.1 binding, Host/Origin guards and CSP unchanged. DF-06: code is the intended estimator; `control.py` docstrings fixed (pooled evenness form, 4-beat pedal blur cap), no code change. DF-08: phrase-coherence spec, F-05e README (appended correction; prereg untouched), DECISIONS correction entry (mistake set is (n)ASAP), `pianovam.py` docstring, `rules/audio.md` extras wording, 3 feature-engineer memories, STATUS.md refreshed; `render.py` footer left to the report/ owners. pytest 518 passed, 1 skipped; ruff clean. Not committed.
- 2026-09-29: DF-03 / DF-04 fixed, DF-08 study items fixed, S-04 design drafted (study-designer), awaiting lead review. DF-03: `power.H6_MARGIN` = 2 is the `h6_verdict` default, `Assumptions` defaults = design A2, `power_s03.py` derives A1/B2 from them; full rerun gives a byte-identical `power_grid.csv`. DF-04 confirmed by running (hold 1.25 came back as level 1.0 / "fraction"); fixed in `pedal_blur`, test added, 80 manifest rows relabelled `hold_beats` (levels were already right; audio untouched). DF-08: `excerpt.py` docstring (cut before degrading), protocol-S03 4.3 (at least 20, not 12-17). S-04: `study/protocol-S04.md` draft + `power_s04.py` sim (24 passages x 10, N = 96: power 0.87 at a features effect of 0.2, SSR 0.88; 0 false positives; all under assumed parameters). Tests: tests/study 38 passed.
- 2026-09-29: BL-20 and BL-19 (feature-engineer), both Provisional, awaiting eval-auditor. Pre-registered in `docs/specs/correctness-validation.md` (section hashes in each experiment's `artifacts/prereg_sha256.txt`). BL-20 `scripts/eval_correctness_density.py`, `experiments/2026-09-29-BL-20-density/`: reproduces F-02's bar counts exactly (1,600 rows). Bar F1 is not worse in dense passages; note-level wrong-pitch naming is (aligner absorption 6-16% under 100 ms, 0 with the GT alignment; window mispairing at most 1.1%). Verdict concern; keep 100 ms; aligner post-pass proposed. BL-19 `scripts/staff_hand_proxies.py`, `experiments/2026-09-29-BL-19-staff-hand/`: 802 catalogue scores, 5.2% of notes and 3.9% of hand-sync events at risk, median piece 0.9%; pass for pooled hand sync; not validated (PianoVAM `Fingering/` hand labels exist upstream, not fetched). New finding: 25 catalogue scores give hand synchrony zero events (staff numbering). Tests `tests/features/test_bl19_bl20_helpers.py` (+6). No production code changed.
- 2026-09-29: BL-17 (ml-researcher), Provisional, awaiting eval-auditor. `experiments/2026-09-29-BL-17-romantic-llm/` (prereg sha256 c3803f83...; power.py reachability first). 24 simple + 6 compound DCML Romantic movements (R-08d's excluded), R-08b disguise, runs A/B + undisguised U on 8; 68 blind annotators launched by ml-researcher, transcripts clean. Simple-meter mean end F1 0.635, t [0.549, 0.720] -> INCONCLUSIVE (R-08 point label NO-GO); beats detector +0.327 t [+0.237, +0.418]; +-1 bar 0.702; compound 0.654; disguise cost not shown (+0.032, n 8). R-08d's 0.737 not confirmed; better Romantic estimate about 0.64. Lead decides follow-up (tolerance, arrival rule, post-cutoff labels). No src changes; ruff clean on new scripts. Not committed.
- 2026-09-29: BL-17 audited (eval-auditor): **Confirmed with caveats**, INCONCLUSIVE stands (0.635, t [0.549, 0.720]); beats detector shown. Prereg hash/timeline, draw, hashes, blinding (68 transcripts) and all scoring/harness reruns verified byte-identical. Text fixes required (README Audit): R-08d vs BL-17 not detectably different (Welch p 0.41; noise, corpus weighting, disguise); errors two-sided (88/314 misses per run, only 21-26 within 1 bar); P19 1-bar pattern run A only; +-1 bar also contains 0.70 and is lenient; blinding wording (env cwd); 14 concurrency refusals disclosed. Lead: DF-02 report text should cite BL-17 boundary accuracy (about 0.64, 0.14-0.92 per piece), nocturnes and compound meters untested, and F-05e's Romantic shortfall; SCORING_MODEL Shaping row stale. Not committed.
- 2026-09-29: BL-18 (feature-engineer), Provisional, awaiting eval-auditor. Pre-registered in `docs/specs/report-validation.md` section 5 (hash 2274b56b...f60c; amendment 1 hash 37d1100a...1664, written after dev, before the held-out draw, because no pre-registered candidate met the dev bar). Implemented for transcribed input only: per-bar strong limit = finite-sample rank ceil(0.99(n+1)), else worst expert + 2 notes (`expert_bar_limits(strong_margin=)`), plus per-family strong global limits (`calibration.TRANSCRIBED_STRONG_LIMITS`; `ReportInputs.transcriber` from `expert_capture_model`). `scripts/calibrate_strong_tier_bl18.py`: held-out 207 new targets, 11 pieces: strong 0.90/1.36% -> 0.17/0.19% (Transkun/Aria), notable+ and its detection unchanged -> PASS, but overshoots (injected-bar strong detection 4.13 -> 0.68%); R1(0) alone 0.62/1.01% is nearest nominal (not the pre-registered pick; lead decides). Key-sensor unchanged. Henry rerun in `data/interim/reports/henry_bl18/`: strong correctness bars 14 -> 3 across 10 reports, same tiered bars. Also touched `report/io.py` (1 line) and `scripts/a01_henry_reports.py` (`--out`, family). Not committed.
- 2026-09-29: BL-20 and BL-19 audited (eval-auditor), both **Confirmed with caveats**; Audit sections appended to both READMEs, rows added to `EXPERIMENTS.md`. Prereg hashes and timelines verified from the feature-engineer transcript; BL-20 full rerun byte-identical, BL-19 per-piece outputs identical. BL-20: concern stands, but the attribution overreaches. The labelling step alone fails the Part B gap (`gt_alignment` dense-N minus sparse-O -0.137 [-0.186, -0.094]), mostly the ornament whitelist, so an aligner fix alone cannot clear criterion 4. Bar detection in clean dense-N bars is 0.932. The post-hoc "no error" column equals 1 minus bar detected. 13.4% of absorbed notes are pitch-mismatched aligner matches that `correctness` labels correct. BL-19: pass holds under the over-count checks, but the proxies flag nothing on the marked staff in 57% of measures with a contradicting engraver hand mark, so it is a pass on the proxy only. DF-09 pieces add tiny-denominator noise to the tail (tail 4.38% over pieces with events). Text fixes for the authors are listed in each Audit; proposals for the lead: a pitch check on aligner matches and an ornament-whitelist tightening (feature-engineer).
- 2026-09-29: BL-18 audited (eval-auditor): measurement **Confirmed** (PASS reproduces exactly from cache; hashes 2274b56b...f60c and 37d1100a...1664 match; transcript shows amendment at 20:46Z, first held-out draw at 20:47Z), implemented rule R1(2) + R2s **Returned**. Audit appended to `docs/specs/report-validation.md` ("BL-18 audit"). Findings: dev selection was forced by 55 run bars (3+ bars with 80%+ missed, 6 Aria-AMT targets) that no candidate can remove, so all other strong bars had to drop to 0.29%; the Aria-AMT limit 0.771 is set by those runs (0.422 without) and family equals corpus (Aria-MIDI vs PERiScoPe), so it is not a transcriber property; learner cost: bars with 3+ injected wrong notes strong 96.5% R0 / 92.9% R1(0) / 52.9% R1(2) + R2s, Henry strong bars 14 / 11 / 3; "dev overstated" holds for Aria-AMT only (Transkun dev 0.58% vs held-out 0.90%). Lead decides: interim R1(0) without R2s (margin 0, `transcribed_strong_limits=False`; BL-18 tests follow), a separate "passage not heard" rule for runs, and BL-18b confirmation (spec'd in the audit, two-sided C1 0.30-1.25%). Proposed lesson for `rules/experiments.md`. No code changed. Not committed.
- 2026-09-29: BL-17 post-audit text fixes (ml-researcher): README Results/Verdict/Threats/run record corrected in place plus `## Post-audit corrections` (R-08d not detectably different, three unseparated candidates; recall 0.71-0.73 and 88/314 misses with only 21-26 within 1 bar; P19 run A only; +-1 bar interval contains 0.70 and lenient; 14 refused launches; env cwd disclosure; recognition additions). Prereg sha256 rechecked: still c3803f83...2462. EXPERIMENTS R-08d row: GO not confirmed by BL-17. DF-02 disclosure (feature-engineer): report phrase-tempo text and methods footer cite BL-17 accuracy, untested nocturnes/waltzes and compound meters, F-05e shortfall, recognition from cache, detector value and run spread, "undetermined" on sign disagreement, no practice item depends on it; tests added; henry_llm rerun (01 and 04 undetermined, practise unchanged). Gates: 521 passed, 1 skipped; ruff clean. Not committed. SCORING_MODEL Shaping row still stale (lead).
- 2026-09-29: BL-21 and BL-22 (audio-engineer), both Provisional, awaiting eval-auditor. Pre-registered in `docs/specs/phone-audio-baseline.md` (BL-21 5b9508aa...d11f, BL-22 9e2a41ec...bccd). **BL-21** (`experiments/2026-09-29-BL-21-repeated-notes/`, `scripts/bl21_repeated_notes.py`): PianoVAM, Transkun, 84 recordings. Same-pitch repeat recall is 0.33 at IOI < 80 ms (n 434) and 0.89 at 80-120 ms (n 1,775), against a reference of 0.976. Bins < 120 ms "matter" (drops 64.9 [59.9, 70.7] and 8.7 [5.5, 12.5] points); 120 ms and slower do not. Aria-AMT on an 8-recording subset agrees. Post hoc: fast repeats are soft (median velocity 25 vs 65); velocity-adjusted drops are 35.2 and 4.3 points. The rendered path has no fast repeats. They matter for sixteenth-note repeats faster than about 125 bpm, and merged repeats become report "missed" notes. In the takes, fast repeats are 19 of 575 missed notes. Suggestion for feature-engineer: low-confidence missed flags for same-pitch repeats under 120 ms on transcribed input. **BL-22** (`experiments/2026-09-29-BL-22-phantom-extras/`, `scripts/bl22_phantom_extras.py`; per-note outputs only in `data/interim/henry_takes/bl22/`): (a) pedal test not evaluable (transcriber reads the pedal as down 87-97% of every take); (b) not harmonic (2 s window 0.628 vs null 0.609; concurrent window Transkun n.s., Aria-AMT a small overtone minority); (c) fixed pitch G6/C7/D7/E7, top 4 in all 3 affected takes; weakly "in silence" (7.3% isolated vs 3.4%); (d) real narrow-band tone at the reported pitch (10 dB prominence), abrupt, with no 2nd partial (0.4 vs 5.6 dB for real notes). Post hoc: not octave-displaced missed notes; all takes band-limited (3-6 kHz 6-13 dB below PianoVAM), unaffected takes too. Pre-registered mapping favours a room/phone (or fixed instrument-side) artefact over sympathetic resonance and a transcription artefact. The OWNER listening check is still what settles it. Gates: ruff clean on new scripts, src and tests; no src changes. Not committed.
- 2026-09-29: BL-21 and BL-22 audited (eval-auditor). Prereg hashes (5b9508aa...d11f, 9e2a41ec...bccd) and order verified from the audio-engineer transcript (prereg 20:41:10Z; scripts after). All stages rerun: BL-21 `summary.json` byte-identical; BL-22 labels/analyse/spectro/posthoc identical (rerun in `data/interim/henry_takes/bl22/audit/`). **BL-21 Confirmed with caveats:** alignment is not a confound (robust SD about 3 ms; local drift correction changes nothing); 79% of repeats under 80 ms start within 5 ms of the previous release (isolated soft echoes, possibly Disklavier re-triggers); without bounce-like pairs, 80-120 ms drops 2.1 [0.5, 4.3] points; the loss sits below about 100 ms (about 150 bpm sixteenths), not 120 ms; drop "trills". **BL-22 Returned (reading):** the 2 s harmonic rule could not reach "harmonic" for the rendered controls (1/q 1.37-1.47); overtone share 0.01-0.08 (50 ms window). The 2nd partial is missing at G6 (0.8 vs 5.6 dB, level-matched too), but this does not argue against sympathetic strings. New: the high extras are a recurring melody (97% white keys G6-G7, stepwise at about 3 notes/s, same 4-5 note phrases in all three takes vs null about 0, not locked to strikes, stretch-tuned like a piano). Reading: a second, independent musical sound in the recordings, not a phone or room artefact. Listening targets (personal) in `data/interim/henry_takes/bl22/audit/listening_targets.txt`. Lessons added to `rules/experiments.md` and `rules/audio.md`. Lead: rewrite the BL-22 verdict text (author), the A-01 audio rule wording, the BL-25 cut-off (100 vs 120 ms), and the OWNER listening check. Not committed.
- 2026-09-29: DF-10, DF-09, BL-23 (feature-engineer). **DF-10** fixed: `correctness` checks pitch on aligner matches; a different-pitch match is correct only under the documented ornament rule, else dissolved and labelled wrong pitch; measured no-op under the legacy rule (all such matches are parangonar ornament matches within ±2), BL-20 Part B reproduces exactly. **DF-09** fixed in `align/_adapters.to_part` (`normalise_piano_staves`, consecutive numbering across parts before merging): catalogue scores with zero hand-sync events 25 -> 0 (805/805 analysed); tests `tests/align/test_staves.py` incl. ASAP Gondoliera (351 events). **BL-23** Provisional, awaiting eval-auditor: prereg `docs/specs/correctness-validation.md` (sha256 1444e934...2146), `experiments/2026-09-29-BL-23-aligner-ornaments/`, `scripts/eval_correctness_bl23.py`, `align/postpass.py`. Candidate tight whitelist + post-pass fails C1 (-0.109), C3 (0.930) and the genuine-ornament check (6.5% > 5%); fallback post-pass alone passes all no-harm checks and is now the default (`reassign=True`); dense/sparse gap still -0.135. `report/calibration.py`: only `share_bars_with_error_median` 0.421 -> 0.420; tier limits and BL-18 constants unchanged. Gates: 544 passed, 1 skipped; ruff clean. Not committed.
- 2026-09-29: BL-21 / BL-22 post-audit fixes (audio-engineer). **BL-22** is now Confirmed with caveats after the rewrite: the verdict and BACKLOG now take the auditor's reading. The high extras are a second, independent musical sound (a recurring stepwise C-major melody G6-G7, the same phrases in all three affected takes), not a phone-chain artefact, room resonance or transcriber hallucination. The source (in the room vs added in the edit) is undetermined. The harmonic-ratio framing is replaced by the implied overtone share (Transkun 0.01, Aria-AMT 0.08 on the 50 ms window), plus the 1/q reachability limit. The 2nd-partial argument against resonance is dropped, (c) is noted as a re-measurement, and the auditor's listening-check list is in the README. Old A-01/A-01b wording in `.claude/rules/audio.md` and `docs/specs/phone-audio-baseline.md` is marked *Superseded* (kept); both pre-registration hashes were re-verified unchanged. **BL-21** is Confirmed with caveats: the wording is now "loss below about 100 ms, i.e. sixteenth-note repeats faster than about 150 bpm"; the trills example is removed; the key-bounce finding and bounce-excluded drops are in Limitations; the take-level counts are now the `takes` stage of `scripts/bl21_repeated_notes.py` (reproduces 57 / 19 / 575; 234 / 8,172 vs 233 / 8,173 inline, one boundary note). BACKLOG BL-25 cut-off set to 100 ms, citing the audit. Ruff clean. Not committed.
- 2026-09-29: BL-23 audited (eval-auditor), **Confirmed with caveats**. Prereg 1444e934...2146 and order checked against the author transcript (appended 21:58:46Z, hashed 21:58:52Z, script 22:00:42Z). The fallback rule was pre-registered and applied correctly (`TR` and `T` fail N3; `R` passes N1-N4). A full rerun gives byte-identical summary files. R - L paired dense-N strict +0.022 [0.008, 0.037]. Post-pass swaps checked against nASAP ground truth on clean copies: 230 repairs, 35 breaks, 23 neither out of 291. So over-reassignment is real (about 1 in 8 swaps) but outweighed. N3 fail is real harm: 124/188 re-flags are Schubert D899/1 tremolo abbreviations, 34 recur across performers, at most 30 could be slips. DF-10's zero is by construction under the legacy rule. Calibration is unchanged at the stored precision; BL-18 limits were not reported. DF-09 rerun reproduces; 3 of the 4 pieces whose counts went down are four-hands duets with arbitrary hand splits. Notes appended to DEFECTS DF-09/DF-10. Author text fixes are listed in the README Audit. Lead: tremolo expansion before any tight-rule retest; flag duets in the catalogue. Not committed.
- 2026-09-29: BL-18 interim + BL-25 + BL-20 proposal 3 + BL-18b (feature-engineer). Interim default per DECISIONS: R1(0) without R2s (`EXPERT_CHECK_STRONG_MARGIN_TRANSCRIBED = 0`, `transcribed_strong_limits=False`) plus a "passage not heard" rule (>= 3 graded bars with >= 80% missed: no tier, one low-confidence item, start/end noted; transcribed only). BL-25: missed notes on same-pitch repeats due < 100 ms after the previous one are low confidence on transcribed input (not tiered; target and experts with the new `n_missed_fast_repeat` column). BL-20 proposal 3: wrong notes in runs with local IOI < 100 ms are worded per bar ("in this fast run"), never pitch-named. BL-18b pre-registered (`docs/specs/report-validation.md` section 6, sha256 3a151ec7...04b8db, before the draw), run with `scripts/calibrate_strong_tier_bl18b.py` (600 jobs, 0 failed): C1 0.58 / 1.04% pass, C2 pass, C3 0.81 / 0.84 pass, C4 71.5 / 68.4% fail (R0 identical; 100% when the checker sees all 3 wrong notes) -> FAIL by rule, Provisional; revert to R0 not applied, lead decides. New DF-12 (16-19% of injected wrong notes lost on transcribed input). Henry rerun `data/interim/reports/henry_v2/`: strong correctness bars 14 -> 11 vs the original reports, 2 bars notable -> none from BL-25, no passage-not-heard runs, top-3 lists 27 of 30 items unchanged. Tests +11 (`tests/report/test_report.py`); pytest 555 passed, 1 skipped; ruff clean. Not committed.
- 2026-09-29: BL-18b audited (eval-auditor). Hash 3a151ec7...04b8db and order verified from the feature-engineer transcript (prereg 22:32:47Z, first draw 22:34:47Z). `evaluate()` on `bl18b_tables.pkl` matches `bl18b_summary.json` in every field; targeted bars regenerate identically. **Measurement Confirmed; verdict FAIL stands.** C4 cannot separate the rules: where the checker counts 3 wrong notes a targeted bar is strong by construction under R0 and R1(0), so C4 measured the checker; the proposed C4' is also 100% by construction. Lead's proposal (keep R1(0) + run rule) is acceptable as a disclosed deviation from the pre-registered action, with conditions (spec "BL-18b audit" item 6: DECISIONS entry, FAIL kept, rule stays interim, learner-facing 7-in-10 disclosed, rule-relative C4 for any future run). DF-12 split: mostly unpaired wrong notes outside the 100 ms pairing window, plus score collisions. C5: merged run fragments put the gap at the ending in 8 of 10 targets (supports truncation). BL-25 expert side missing in cached floor tables (errs toward fewer flags). Lessons added to `rules/experiments.md`.
- 2026-10-01: D-14 (lead). Henry's tonebase export registered: 28 zips (57.4 GB, outside the repo), 166 PDFs + audio of 190 unique piece-lesson videos extracted (0.84 GB raw, 4.8 GB interim), 0 errors; loader `pianolens.data.tonebase`, `scripts/extract_tonebase.py`, 3 tests. 21 annotated scores mapped by title page, 18 to PianoCoRe ids; `piece_ids.parquet` +21 rows, other rows identical. `uv run pytest -q` 558 passed, 1 skipped; ruff clean. Opened R-11 (pilot), BL-29 (OWNER: license), BL-30.
- 2026-10-05: R-07 audited (eval-auditor) from origin/main 881f9f9 (read-only checkout; box outputs unavailable). **Confirmed with caveats (scoped).** Audit in `experiments/2026-09-28-R-07-symupe-finetune/AUDIT.md` (lead moves it into the README after the merge). Prereg `head -n 300` = 17dfca04...083b, matches `artifacts/prereg_sha256.txt`, unchanged since e4becf8; only platform fixes in code. Every paired CI in `summary.json` and `pt_E_vs_pt_frozen*.json` reproduces exactly from `a_per_rendition.csv`. (a) E − frozen on P harms −0.051 [−0.072, −0.029] -> R-10 uses frozen SyMuPe (rule followed). Gate missed: 0.3987 vs R-06 unrounded 0.3882 (+0.0105), mostly articulation +0.032 [0.014, 0.049]; consequence followed. (b) "At H1b falsification level" withdrawn: R10u/R10s expert curves rebuilt on the Mac (k, var_shared exact for all 124 pieces); 16 held-out experts reach captured share 0.25 / 0.23 (in-sample 0.61), so the 0.50 bar is unreachable; models are about half the oracle; log IOI R²c drops R-06's centering of the predicted curve; the median includes 7 PERiScoPe-paired pieces (74 unseen: E 0.096, frozen 0.112). (c) S-LR pass stands as registered but R1 is matched by B-amount (1.000 everywhere) and scale0.5 AUC is 0.491 on P; not a validated typicality score. Post hoc: E's R10u gain is Aria-AMT only (+0.044); Transkun V2 −0.012 (R10u), −0.061 (R10s). Box-only checks B1-B4 (scripts in AUDIT.md). Lead: H1b operationalisation before R-10, S-LR use, PT role in R-10. No code changed. Not committed.
- 2026-10-05: R-11 steps 1-2 (ml-researcher). Encoding protocol `data/interim/tonebase_annotations/PROTOCOL.md` (v1.2; v1.1 fixed before any row). Encoder A, blind to expert data and report output (only the PianoCoRe score MIDI loaded): 154 rows (NOC 44, WAL 58, ETU 52; 24 grouped digit/label rows), observable yes/partly/no 35/15/104; bar maps checked by pitch content at every system start and annotated bar (nocturne cadenza = m33-36 with bar lines shifted a quarter after it; waltz repeat unfolded, both endings numbered 36; etude and nocturne upbeat +1). Every target note verified against the score dump. Frozen operationalisation: 23 primary (a) rows, 15 secondary, 12 excluded. Pre-registration in `experiments/2026-10-05-R-11-teacher-annotations/README.md`, prereg section sha256 390903481b69...29ca (all input hashes in `artifacts/prereg_sha256.txt`). Next: lead dispatches the blind second encoding (recommended: nocturne) for the gate; no analysis run. Licence BL-29: README holds counts only. Not committed.
- 2026-10-05: R-10 pre-registered (ml-researcher). `experiments/2026-10-05-R-10-h1b/`, prereg `head -n 409 README.md` sha256 d679394f...5f09 (`artifacts/prereg_sha256.txt`). Fresh set (`select_pieces.py`): 1,023 PianoCoRe pieces with >= 20 majority-score tier A performances -> 158 unpaired in PERiScoPe -> 142 without paired work-mates -> 127 without catalogue aliases -> 65 not in R-06 / R-07 evaluation sets, quarantine or R-02 (63 works, 28 composers; R-07 train/val, irrelevant to frozen weights). Built on the Mac: 1,895 renditions (digest `pieces/fresh_digest.json`); 59 primary pieces with >= 20 renditions (57 works), 15 with n >= 36, 12 with n >= 36 and k > 0. Expert-only checks: analytic K-matched oracle velocity 0.878 / log IOI 0.882 (validated against the empirical hold-out oracle, median |diff| <= 0.009); reliability 0.960 / 0.963; 16-expert captured share 0.196, random floor ratio 0.064. Primary H1b-consensus: median R²c of frozen SyMuPe (K = 16, top-p 0.95) per target, consistent >= 0.50 with CI lb > 0.20, falsified <= 0.20 with CI ub < 0.50; reachability: all branches reachable (CI half-width 0.10-0.13); expected velocity reading at the R10u development level is inconclusive. Secondary H1b-axes (top-p 1.0): ratio to the 16-expert oracle, consistent >= 0.80 (= about 12 experts) with lb > 0.40, floor <= 0.40 with ub < 0.80. Baselines: flat (0), score-feature ridge trained on R10u + R10s, R10u development numbers. Dry run (2 R10u pieces, Mac CPU) passed every stage. **Found: SyMuPe EncDec-base ignores `perform_score(lm_top_p=...)` (the seq2seq generator reads `top_p`, default 0.95), so all R-06 / R-07 SyMuPe samples, including R-07 S-TYP "top-p 1.0" references, were top-p 0.95**; R-10 passes `top_p` with a start-up guard. Box: default run about 1-7 h (SyMuPe GPU rate unlogged). Not committed.
- 2026-10-05: R-10 pre-run review (eval-auditor), `experiments/2026-10-05-R-10-h1b/PRERUN_REVIEW.md`. **Ready after amendments A1-A4** (no threshold, model, statistic or arm change). Hash d679394f...5f09 verified; thresholds predate every dry-run R²c (README 16:46:59Z, first R²c 16:50:55Z); expert-side summary reruns byte-identical; analytic oracle derivation and validation reproduce (median |diff| 0.0045 / 0.0090). A1: content check (12-onset n-grams vs 1,530 held scores) finds Debussy 2 Arabesques (contains Arabesque 1, 48 PERiScoPe v1.0 pairs; primary), Ravel Tombeau whole suite (Prelude/Fugue paired; not primary) and Bartók Sz.56/3 (inside R-07 R10u piece) -> exclude; whole-set ids escape R-07 work keys. A2: 25 near-duplicate renditions (deviation r > 0.9; e.g. the same Gould recording in ATEPP and PERiScoPe) inflate the H1b-axes oracle on 3 of 12 pieces (0.389 -> 0.256) -> drop; primary after A1+A2 56 pieces / 54 works, oracle 0.877 / 0.881. A3: primary was registered top-p 1.0 first and switched to 0.95 after both arms' dev R²c were printed; disclosure corrected, both-arms headline rule; lead decision stands. A4: scope (panel median tempo/velocity conditioning; about half of primary pieces have a paired opus sibling, exploratory split). Model card confirms PERiScoPe v1.0. Recommended R1-R5 (amplitude decomposition, composer CI, dev-number caveat, dev digests, docstring). No code changed. Not committed.
- 2026-10-05: R-10 pre-run amendments (ml-researcher), after the eval-auditor pre-run review (`experiments/2026-10-05-R-10-h1b/PRERUN_REVIEW.md`) and the lead decisions. Appended below `## Run record` (hashed header untouched, still d679394f...5f09); amendment block lines 417-517 sha256 6215a0577f79...4089 (`artifacts/prereg_amendment_sha256.txt`). New `amend_pieces.py` writes the committed lists in `pieces/`: A1 score-content check (12-onset n-grams vs 1,530 held refined scores) reproduces the 3 exclusions (Debussy 2 Arabesques 628 hits, Ravel Tombeau 653, Bartók Sz.56/3 114; others at most 3 per held piece); A2 duplicate list identical to the review appendix (25 renditions, 15 pieces); A4 sibling flag (28 of 56 primary; one hand rule for Mozart K. 1-5); R3 list (5 R10u pieces + Bartók whole set). Summariser flags `--exclude-pieces`, `--exclude-renditions`, `--sibling-flag`; r² and amplitude ratio b for every arm and the empirical oracle; composer-cluster CI; per-piece axes ratios; A3 headline rule. run.sh: `results/fresh` (amended, registered) + `results/fresh_as_registered`; `_no_overlap` dev summaries; R4 dev digest and ridge checks (logged). Checks: experts-only with A1 + A2 reproduces 56 pieces / 54 works / 1,691 renditions, oracle 0.877 [0.847, 0.901] / 0.881 [0.845, 0.905], empirical 0.883 / 0.856, reliability 0.958 / 0.958, 12 axes pieces, cap 0.189; R3 medians 0.330 / 0.142 on 69 reproduce; full scratch rebuild matched the fresh digest, both dev digests and the ridge reference; dry run on the 2 R10u pieces ran every stage. No fresh-piece model or ridge output. Not committed.
- 2026-10-05: R-11 gate + analysis (ml-researcher). Prereg hash 390903481b69...29ca verified before any expert data; encoder B hashes appended. Gate (nocturne, A 44 vs B 45 rows): 41 matched (0.93/0.91), category kappa 0.970, observable weighted kappa 0.865, bar map 35/35 identical: PASS; vertical-gap anchor rule ambiguous for text between systems (3 rows, incl. primary NOC-A-027). (a) 18 of 23 primary rows evaluable (4 nocturne rows < 10 null positions, 1 waltz row lost its reference set to MusicXML staffs): mean null percentile 0.634 [0.503, 0.750] -> INCONCLUSIVE (bar 0.65); print-restating rows carry most of it. Encoder B sensitivity 0.588. (b) 6 rows: hit - original flag 0.057 [-0.001, 0.116] -> DOES NOT NOTICE; originals 0.050 [0.023, 0.105] -> stays quiet (point estimate); degraders checked to take effect, note-level removals stay in the smoothed band. (c) 0.325 of rows observable at least in part (0.377 without digit/label rows). Deviations listed in the README (gate digit-row matching, bar-map key bug, B-sensitivity set bug, MAESTRO nocturne dropped, report-grid target, measure->bar map by beat). Code run.py/part_a.py/part_b.py; README counts/statistics only (BL-29). Not committed. Next: eval-auditor.
- 2026-10-05: R-11 audit (eval-auditor): **Confirmed with caveats**. Prereg hash 390903481b69...29ca and all 18 input hashes verified; order checked in the transcript (B hashed 16:48:51Z, gate 16:50:00Z, B notes read after it; encoder B accessed no repo path). Gate, (a), (c) and (b) reruns byte-identical. Labels stand: gate pass, (a) inconclusive, (b) does not notice / stays quiet. Findings: (a) is fragile above 0.5. The t-interval over rows is [0.489, 0.779]. Moving the waltz LH chords that sit in the upper MusicXML part (19 measures) gives 0.598 [0.471, 0.714], and WAL-A-031 becomes evaluable at r 0.176. Rows that do not restate the print give 0.573 [0.426, 0.701]. (b): a gain sweep shows 4 of 6 rows stay at 0.15 or less even when the effect is reversed at 4x (unreachable by the per-bar channels). The bar-level rows are flagged 0.75-0.95 when reversed at 2x. Window tiers changed in 0 of 117 degradations. Dev. 2 was fixed after the first gate printed fail, not before. Dev. 3's first result (0.504, 7 rows) was not disclosed. README text fixes 1-6 are listed in the Audit section; the EXPERIMENTS.md row proposal is in the audit.
- 2026-10-05: R-11 post-audit text fixes (ml-researcher). Applied the six fixes from the README Audit (Confirmed with caveats): Dev. 2 timing (fix 8 s after a printed gate fail; auditor 35/35), Dev. 3 pre-fix B sensitivity 0.504 [0.248, 0.766] and NOC-B-038 move, Deviations retitled as disclosed after the run, (a) verdict without a direction claim (t over rows [0.489, 0.779]; no-restate 0.573 [0.426, 0.701]; waltz-hands 0.598, null-pool 0.589, both 0.576), waltz hand threat quantified (19 measures, 62 notes), (b) gain sweep + t [-0.095, 0.212] + scope to tempo/loudness tiers + 'a majority of experts show'. Added `## Post-audit corrections`. Prereg hash and Audit section unchanged; no rerun; README counts/statistics only (4-gram scan clean). Not committed.
- 2026-10-06: R-10 audit (eval-auditor): **Confirmed with caveats (scoped)**. Audit appended to `experiments/2026-10-05-R-10-h1b/README.md` (`## Audit (2026-10-06, eval-auditor)`); new `audit_checks.py` (Mac, about 2 min). Prereg head -n 409 d679394f...5f09 and amendment block 6215a057...4089 unchanged since 4047183 (block moved to lines 445-545; stored `sed -n '417,517p'` command is stale). Run from 28c5a01, clean tree, job/pieces hashes, three set digests and ridge match; no fresh-piece model output before the run; R-10b used only R-02 pieces (0 piece/work overlap). Every summary median/CI reproduces from the committed CSVs. Registered reading exact: velocity 0.150 [0.022, 0.283], log IOI 0.073 [0.032, 0.180] = falsified (top-p 1.0 and as-registered same). Post hoc: shape same as dev (velocity r 0.672 vs 0.665); drop is amplitude on a flatter consensus (b 1.10 vs 0.94); dev-chosen scale gives 0.362 / 0.271 = inconclusive; no scaling reaches 0.50 (r² 0.45 / 0.31); model beats ridge on r (+0.13 / +0.25) though not on R²c; velocity flips to inconclusive without J. S. Bach; H1b-axes 0.437 vs envelope-surrogate floor 0.363 (null-adjusted 0.16). B2: dev log IOI 0.144 (R-06) vs 0.127 (R-07). Six text fixes, six box checks, proposed EXPERIMENTS row and DECISIONS text in the audit. Not committed.
- 2026-10-06: R-10 post-audit text fixes 1-5 (ml-researcher). README `## Post-audit corrections (2026-10-06)` appended; one pointer bullet in the run record; hashed header (d679394f...) and amendment block (anchor-form sha256 6215a057...4089, re-checked) untouched; the Audit section untouched. Fixes: headline with r / b / R²c at b = 1 / best scale / dev-chosen scale (0.362 / 0.271, inconclusive; no scaling reaches 0.50); anchor hash command (also appended to `artifacts/prereg_amendment_sha256.txt`); `results_box/` holds no logs (box to push); H1b-axes against the envelope floor (0.363 of the oracle; null-adjusted 0.16 [0.01, 0.33]); scope: the ridge reads inconclusive on velocity (0.246). All numbers re-run with `audit_checks.py` (including the envelope null) and match the Audit. Fix 6 (gen_pt / dev_gen) waits for the box. Not committed.
- 2026-10-10: R-10 secondary-arms audit addendum (eval-auditor): verdict unchanged (Confirmed with caveats, scoped). `### Addendum (secondary arms, 2026-10-10)` appended at the end of the README Audit section; new `audit_addendum.py`; `audit_checks.py` envelope null now also scores pt_frozen (earlier output unchanged). gen_pt restart clean: 65/65 items once each (12 before the pause + 53 after, the in-progress item redone; atomic writes), 0 errors, primary rows identical to 2e90db7. pt / dev numbers reproduce exactly. Fix 6 columns: PT r 0.650 / 0.391, b 1.073 / 0.830, R²c at b = 1 0.301 / -0.218 (log IOI a shape failure; beats ridge on r); dev_gen r 0.679 / 0.524, b 0.974 / 1.124, at b = 1 0.357 / 0.049. Fresh vs dev at top-p 1.0: velocity r 0.652 vs 0.681 (p 0.10), b 1.089 vs 0.962, so the drop is mostly amplitude; a dev_gen scale gives 0.350 / 0.242 (inconclusive). Run record: the PT JSON covers only the 53 post-restart items, and the 12 pre-pause items' checkpoint is unrecorded (box-only). Correction 3 closed.
- 2026-10-10: R-10 post-audit correction 6 closed (ml-researcher). Dated sub-entry appended to `## Post-audit corrections (2026-10-06)`: it cites the Audit Addendum table for the Pianist Transformer and dev_gen r / b / R²c / R²c-at-b=1 (re-run with `audit_addendum.py`, all match); headline lines PT 0.061 / -0.045 (r 0.65 / 0.39), dev_gen 0.324 / -0.173; fresh-vs-dev velocity drop at top-p 1.0 mostly amplitude (about 0.06 of 0.23 is shape); dev_gen negative log IOI is the top-p 1.0 effect (b +0.2), not comparable with R-07 0.144; PT below the ridge on velocity is ridge shrinkage, PT beats it on r (+0.13 / +0.16); the dev summary headline word "registered" is template wording; run-record imprecisions noted (PT log covers 53 items; exit codes and box git state at the restart unrecorded; block now at line 480). Hashes rechecked: head -n 409 d679394f...5f09, anchor 6215a057...4089. Not committed.
- 2026-10-10: BL-24 data ready (data-engineer). Fetched PianoVAM v1.2 `Fingering/` (106), `Fingering_GT/` (11) and `TSV/` (107), 43 MB, HF commit 1f039ab9, CC BY-NC-SA 4.0, per-file sha256 in `data/raw/pianovam/Fingering_TSV_SHA256SUMS.txt`. New: `HAND_LABEL_DTYPE` in `data/types.py`; `pianovam.hand_labels` / `iter_hand_labels` / `hand_label_summary` / `SCORE_CANDIDATES`; synthetic fixture `tests/fixtures/pianovam/` (+ `make_fixture.py`); `tests/data/test_pianovam.py` (+8 tests). Video labels map onto all 106 solo recordings (0 failures, 525,483 notes, 80.1% labelled); the card's 99.2% hand accuracy reproduces from the files (1,800 manual notes; opening 150 notes only). Catalogue candidates by title: 44 recordings / 29 titles (29 / 21 unambiguous); 5 have manual labels. The BL-19 proxy validation was not run: it needs take splitting, score alignment, movement resolution and a Noinfo policy (BACKLOG BL-24). Gates: ruff clean, pytest 559 passed / 8 skipped.
- 2026-10-10: R-07 remaining author fixes (ml-researcher; AUDIT.md section 9 + reconciliation note). REPORT.md: header, section 3 row 15, section 4 ("Training, data and cost (final)": pt_E full curve 1.6420 -> 0.9762 at the 8,000 cap, resume at 1,500, wall times), section 4b retitled with dated "[author fix 2026-10-10]" corrections (gate 0.3987 vs 0.3882 = +0.0105; H1b uninformative, 74-unseen headline + 7 paired separately, R-06-formula log IOI from R-10 B2; S-LR "outside F's family" corrected), new post-hoc per-transcriber subsection, section 5 rewritten to the final state (arms x sets, decisions, still-open B1-B3), Gaps updated; "[audit 2026-10-05]" corrections kept; report.html regenerated. New `pair_ci.py` reproduces all three `results/pt_E_vs_pt_frozen*.json` byte for byte from `a_per_rendition.csv` with the summariser's `boot_ci` / `t_interval` (asserts equality; 40 s). New `posthoc_tables.py` (transcriber: E - frozen equals AUDIT section 8, plus pt_E - pt_frozen and a ByteDance n = 10 stratum; h1b_groups: 74-unseen medians equal AUDIT section 4). README: `### Corrections and additions after the audits` appended at the end of the run record (top-p 0.95 line per DECISIONS 2026-10-05, gate and H1b wording, pair script, post-hoc transcriber table labelled exploratory); `head -n 300` still 17dfca04...083b; both audit sections untouched (README diff is additions only). Not committed.
- 2026-10-10: BL-31 done (ml-researcher). R-11 encoding protocol v1.3 (`data/interim/tonebase_annotations/PROTOCOL.md`, gitignored): vertical gap measured only within the text's own columns (first-line top edge up, bottom edge down); tie margin max(one staff space, 15% of the smaller gap), near ties still to the system below; near-tie rows carry both gaps and the alternative anchor (4 new trailing columns) and are double-coded blind; revision log cites the R-11 gate finding (3 nocturne texts one system apart, B always one system earlier; 106 vs 109 px, 21 vs 25 px). R-11 v1.2 encodings not recoded. No annotation text in tracked files. BACKLOG BL-31 marked done. Not committed.
- 2026-10-10: DF-13 done, Provisional (feature-engineer). Wrong-pitch pairing window on transcribed input. Prereg `docs/specs/correctness-validation.md` "Pre-registration DF-13" (anchor sha256 44bd842e...1214, also in `experiments/2026-10-10-DF-13-pairing-window/artifacts/prereg_sha256.txt`), written after a dev run on the BL-18b set and before the held-out draw. New `correctness(..., wrong_pitch_window="fixed"|"wide"|"tempo"|"error")` (default `fixed`, behaviour unchanged), `scripts/eval_pairing_window_df13.py`, `scripts/rebuild_floor_tables_df13.py`, `a01_henry_reports.py --floor-tables`. Dev finding: only half of the DF-12 unpaired loss is window-reachable (4.3 / 6.4% of injected notes); the rest is aligner re-matching after the injection. Held-out (16 new pieces, 800 jobs, 0 failed): **FAIL by rule** - `tempo` passes all but F1 (clean wrong-pitch labels +15.02% / +16.8%, bar 15%), `error` FAIL, `wide` PARTIAL; 100 ms stays, nothing wired, no calibration or Henry report changed. `tempo` would give strict +3.6 / +4.7 pt and 3-wrong bars strong 73.0 -> 78.5 / 69.0 -> 76.2%. P clean strong under 100 ms 1.49 / 1.86% on these pieces (above BL-18b's band; "Scarbo"). Lead decides (README "For the lead"); needs eval-auditor. Tests +6. Not committed.
- 2026-10-10: BL-19b done, Provisional (feature-engineer). Staff vs PianoVAM video hand on 42 recordings aligned by take (new `pianolens.data.session_takes`: local alignment + parangonar per take; 518/560 takes kept, 0/6 null takes), 117,238 labelled notes, 31 pieces. Prereg sha256 a2b4f597...0577 (README anchor). STAFF mismatch 6.66% [3.51, 9.00] pooled (median piece 3.35%; label noise 0.76%); pitch split 23.4%; VOICE rule no better (-0.47 pt [-2.29, +1.96]). D1: above 2%, inconclusive at 5%. D2 hand synchrony pass at the boundary, not stable to one piece (median piece 3.65% of events; 3/30 pieces > 20%; any one sub-20% piece removed or an event minimum of 100 gives a concern; passes in 59% of piece-bootstrap resamples). D4: BL-19 at-risk flags precision 42%, recall 39%, lift 6.3 (not useful as a filter by the rule). Italian Concerto excluded: both catalogue scores are the 2nd movement only. New `pianolens.features.hand_proxies`; tests in `tests/data/test_session_takes.py`, `tests/features/test_hand_proxies.py`.
- 2026-10-10: BL-19b audited, Confirmed with caveats (eval-auditor); author fixes 1-7 applied by feature-engineer as "Corrections after the audit" in the README: D2 pass at the boundary, not stable to one piece; mismatches systematic per score note (recur 90% vs base 6.8%; Op. 17 i mm. 41-49 engraving); Toccata 86% same-pitch alternation (4.5% outside); performer t-interval 5.32% [0.68, 9.96]; label-error and Noinfo uncertainties named; pre-hash disclosure corrected; posthoc stable sort (n_runs 4,249). Prereg hash unchanged.
- 2026-10-10: DF-11 and DF-08 fixed (feature-engineer; awaiting lead review). DF-11: new `report/four_hands.py` (duets from the MusicXML layout: >= 4 staves in multi-staff parts with notes in >= half the bars, or primo/secondo part names; 3-id known list only as fallback); app catalogue `four_hands` flag (`CATALOG_VERSION` 2; exactly Fauré Op. 56/1, Dvořák Op. 72/2, Ravel Ma mère l'Oye 5 of 805); duet reports drop `hand_async_*` with a plain-language confidence note and control-card line. Chopin Op. 29 "Flauta" staff choice unchanged (0.11 semitone from the midpoint; not a duet). BL-23 README: 5 audit text fixes as a dated correction section. DF-08: `render.py` footer states the 2-expert-recording condition for recurring mistakes; SCORING_MODEL already correct; its hand-synchrony text updated for DF-11 and pages rebuilt. Solo reports byte-identical old vs new apart from the footer (4 pieces). Tests +12 (`tests/report/test_four_hands.py`); pytest 591 passed, 8 skipped; ruff clean. No correctness/align/tier logic touched. Not committed.
