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
  owner: feature-engineer. status: in progress.
  - Suppress correctness flags at bars where expert transcriptions of the same score also show
    errors, as in Op. 64 No. 2 bars 78-79.
- **A-01b Phone-audio extra-note filter** (M). blocked_by: A-01. owner: audio-engineer. status: in progress
  (2026-09-28).
  - Uses register, fixed repeated pitches and the absence of a plausible source note.
  - Validate on audio with ground truth first (BL-13 / PianoVAM).
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
- **P-02 Local web app** (L). blocked_by: P-01, F-08c. owner: feature-engineer. status: in progress
  (2026-09-28).
  - Upload audio or MIDI, choose a supported piece (searchable list of PianoCoRe/ASAP pieces with
    scores and at least 50 references), run the pipeline with progress, and show the report with an
    embedded A/B player (loop, instant A/B switch, curves for the window).
  - Runs on localhost only, no external calls. Module: `src/pianolens/app/`.
- **O-01 OWNER: Henry records MIDI** (S). Three takes each of one or two passages from a piece in
  (n)ASAP / PianoCoRe. Needs a piece choice and MIDI out.

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
- **S-05 Pairwise study app + adaptive pair selection** (L). Watch Bramley's caveat: adaptive pair
  selection can inflate reliability.
- **S-06 BT analysis + feature regression** (M) (H7).
- **O-02 OWNER: recruiting and consent** for Phases 3 and 4.

## Phases 5-7

- **R-06 Expression model survey + choice** (M). owner: lit-scout (survey), ml-researcher (frozen head-to-head). status: done, verdict Confirmed with caveats (audited 2026-09-28); SyMuPe primary, PT secondary. ml-researcher: frozen SyMuPe EncDec-base vs Pianist Transformer, `experiments/2026-09-27-R-06-expression-model-h2h/`: quality tie on unseen pieces, SyMuPe chosen by the pre-registered tie-break; likelihood prefers deadpans. Pianist Transformer vs ScorePerformer vs DExter:
  code status, license, fit on a 5080.
- **R-07 Train or fine-tune the expression model** (L). blocked_by: R-06, D-03, O-03.
  owner: ml-researcher. status: in progress (job prep done 2026-09-28; the run waits for O-03).
  Pre-registered in `experiments/2026-09-28-R-07-symupe-finetune/` (SyMuPe EncDec-base primary,
  flat model F for the likelihood-ratio score, Pianist Transformer secondary arm). Split fixed by
  work in `split/pieces.csv` (test = P, V, A, R10u = 76 R-02 pieces unseen by SyMuPe pretraining,
  R10s; val 59 works; quarantine 81 alias ids). Job folder `job/` ran end to end on the Mac CPU
  (dry run: prep with leakage check, train, stop, resume, F, PT, calibrate, eval on 2 held-out
  pieces). Typicality pass criteria are written (R1 deadpan battery, R2 noise, R3 Vienna).
  paths: `experiments/2026-09-28-R-07-symupe-finetune/`, `src/pianolens/models/expression_split.py`,
  `src/pianolens/models/expression_data.py`, `tests/models/`.
- **R-10 H1b: score-conditioned predictability of expert expression** (L). blocked_by: R-06, R-02 audit.
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
- 2026-09-28: R-05 (ml-researcher), Provisional, awaiting eval-auditor. H8 substitute design: 1,500 MAJEPPA clips (250 per level), first 30 s of the Transkun MIDI rendered with the S-02 piano, 4 simulated contexts (clean / phone_room / recital_phone / concert_hall: `audio.phone.simulate_phone` + AAC), frozen MuQ L9-12, logistic regression, piece-grouped 5-fold CV. Beginner vs advanced AUC: context fixed 0.870; confounded as in MAJEPPA 0.943 (delta +0.073 [+0.055, +0.092]); confounded model with test contexts permuted 0.730 (delta +0.214 [+0.196, +0.232]); contexts swapped 0.475; negative control +0.002. Context decodable at 0.997. Supported by the pre-registered rule; holds for fold seeds 1-2 and layer 6. Pre-registration hash 7add1490...f0c5; reachability simulated first (falsified reachable only at score correlation about 0.9; observed 0.8). Build 36 min on MPS. pytest 470 passed, 1 skipped; ruff clean. Not committed.
