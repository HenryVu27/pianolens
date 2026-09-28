# PianoLens status

Last updated 2026-09-28 by the lead session. Details live in `EXPERIMENTS.md`, `DECISIONS.md`
and `WORKBOARD.md`. This page is the short version.

## What we have learned (audited results only)

| Exp | Question | Answer | Verdict |
|---|---|---|---|
| R-01 | Do PercePiano's 19 rating scales reduce to a few factors? | Yes: 3-5 factors, with one dominant "general quality" factor. Individual raters are noisy but not simpler than the panel. | Confirmed w/ caveats |
| R-02 | Is expert expression low-dimensional (H1)? | Not as stated: whole-piece curves need about 19 components for 80% of variance. But the part experts *share* is low-rank (3-5 components, about 35-46% of variance). The rest is individuality. | Confirmed w/ caveats |
| R-03 | Does CrescendAI's audio (MuQ) result hold? | It reproduces (0.509 vs 0.536) but collapses on unseen works (pooled R² below 0). Within-passage ranking is 59-62%. | Confirmed w/ caveats |
| R-04 | Can interpretable MIDI features match MuQ (H3)? | Yes, non-inferior on unseen works in all 4 variants. Pedalling, dynamics, tempo shape and voicing drive it. Both models sit at single-rater level; the ceiling (about 0.74 WP rho) is far higher. | Confirmed w/ caveats |
| R-06 | Which expression model: SyMuPe or Pianist Transformer? | They tie on unseen pieces, and the pre-registered tie-break picks SyMuPe. Raw model likelihood rates deadpan playing above every expert, so it can never be used as a quality score. | Confirmed w/ caveats |

## What we have built

- **Data:** 11 GB raw, 3.8 GB processed. PianoCoRe tier A cache holds 157k aligned performances.
  - Cross-dataset piece ids.
  - Loaders for 16 datasets.
  - A synthetic mistake set.
- **Alignment:**
  - Mean F1 0.964 on (n)ASAP.
  - Picks the repeat path automatically.
- **Tier A, correctness:**
  - Bar-level any-error F1 0.99 on synthetic mistakes.
  - Missed notes are reported per bar.
- **Tier B, control:** timing noise net of expert consensus, broad and strict evenness, hand
  sync, tempo stability, and pedal blur (validated against DCML harmony, F1 0.75).
- **Tier D, interpretation:** expert band, windowed shared core, two-sided typicality with a
  too-flat guard, and notable/strong per-bar flags (F-06).
- **Tier C, shaping:**
  - Structural coherence (velocity and articulation are primary).
  - Per-phrase tempo arcs.
  - Repeated material, voicing, dynamics compliance, cadence detector.
- **Report card (F-08):** MIDI in, a self-contained HTML report out.
  - Sections: correctness, control, shaping, interpretation, a bar-by-bar timeline and "What to
    practise".
  - Samples are in `data/interim/reports/`; the CLI is `scripts/pianolens_report.py`.
  - Timing flags are still experimental (F-08b).
- **Listening study (S-01/S-03):** a graded degradation generator (7 dimensions, in physical units
  and threshold units), a protocol with power analysis (about 96-160 listeners), and a local-only web
  app that passes a headless smoke test.
- **Evaluation harness:** grouped splits, cluster bootstrap, rater parity, Bradley-Terry,
  dimensionality nulls.
- **Audio:** a deterministic fixed-piano renderer (Salamander).

## Open caveats that shape the plan

- **Skill validity of tier B is unproven.** MAJEPPA's apparent skill effect disappears within
  matched recording contexts (D-10). Clean, context-matched data is needed.
- **Velocity from transcribed MIDI is not trustworthy for skill claims** (D-10).
- **Tempo coherence needs beat-precise phrase boundaries.** Annotations work; the automatic
  detectors do not yet (F-05b, F-05c).

## More audited results

- **R-09 (H4, coherence vs skill): inconclusive, Confirmed with caveats.** Within matched contexts
  from beginner to advanced-student levels there is no trend. Top levels are confounded with
  concert/demo context. The design had low power to falsify. Articulation coherence fails Aria-AMT
  transcription; timing coherence survives.

## Provisional or conditional results

- **R-08a (LLM phrase analysis, blind pilot):** Claude reading a text rendering of the score marks
  phrase ends at F1 0.817 [0.747, 0.901] (±1 beat), against the rule-based detector's 0.565, on 5
  held-out Mozart movements. This clears the pre-registered 0.70 go bar.
  - Half cadences: 35/62 found, against an oracle ceiling of 38.
  - Caveat: 4 of 5 pieces were recognised by name. The one unrecognised piece scored highest (0.952).
  - **Audited: Confirmed with caveats.** Blinding was clean, and the LLM is ahead on all 5 (paired +0.25).
    The t-interval is [0.696, 0.938]. Memorisation is not excluded, so R-08 is GO only after the
    R-08b control (disguised scores).
- **R-08b (memorisation control): PASS, Provisional and under audit.**
  - With disguised scores (transposed, words stripped, bars offset; 0 of 5 recognised), LLM end F1
    is 0.802, against 0.789 for the undisguised mean of 3 runs.
  - Paired A-U is +0.014 [t -0.029, +0.056]. Run-to-run SD is 0.031.
  - **Audited: Confirmed with caveats.** It rules out explicit recall; familiarity with the
    structure is not excluded.
  - LLM boundaries are approved for Classical sonatas. Other repertoire needs R-08c (J.C. Bach).

- **R-08c (unfamiliar repertoire, J.C. Bach): GO, Confirmed with caveats.**
  - LLM end F1 is 0.750 (t [0.588, 0.912]), against the detector's 0.437. Paired difference +0.313.
  - Blinding was clean. 0 of 10 runs recognised.
  - Scope: Classical sonata-type movements. Label exposure is not excluded.
  - Romantic repertoire needs R-08d.
- **F-07 (H5): Confirmed with caveats, reinterpreted.** The pre-registered test passes, but a
  cross-pianist control passes too. So the take-consistent part is shared piece timing, not personal
  intent. Supported: a pianist's own take-to-take variation is mostly unstructured, which justifies
  treating it as noise.
- **F-08b:** timing flags are no longer experimental. The recurring-error rule is narrowed to wrong
  pitches that pass the expert filter.

- **R-08d (Romantic repertoire): fragile GO, Confirmed with caveats.**
  - LLM 0.737 (t [0.44, 1.04]), against the detector's 0.389. Paired difference +0.348.
  - 0 of 10 runs recognised a piece.
  - Licensed at the mean level for Romantic character pieces in simple meters. Per-piece risk is
    real, and the LLM segments more finely than DCML.
  - Across the four R-08 tests the LLM holds at about 0.74-0.82, while the detector falls from 0.57
    to 0.39.

## In flight

- F-07: separating intent from noise across repeated takes (H5).
- R-08b: memorisation control for the LLM phrase analysis (disguised scores, reruns).
- F-08b: report fixes (timing-flag provenance check, recurring-error tiering).
- F-05d: coherence minimum-length fix.
- R-09: coherence vs skill (H4), with recording context controlled.

## Waiting on Henry (OWNER)

| Ticket | What | Unblocks |
|---|---|---|
| O-01 | Your own MIDI takes (3 takes of 1-2 passages; a piece in ASAP/PianoCoRe) | Clean tier B validation, H5 on a real learner, the first real report |
| O-03 | RTX 5080: CUDA 12.8+ PyTorch, plus a job transfer method. **The R-07 job folder is ready**: `experiments/2026-09-28-R-07-symupe-finetune/job/` (setup.sh, fetch_data.sh, run.sh calibrate, then train, then eval) | R-07 fine-tune, R-10 (H1b), audio front end |
| O-04 | A cloud GPU budget (if any) | Runs too large for the 5080 |
| O-02 | Listening study S-03 is **built** (app in `study/app/`, protocol in `study/protocol-S03.md`, 592 pilot clips). Decisions needed: N (96 / 160 / B2), format, consent and payment, ethics. **First step: you do the pilot** (about 75 min, protocol section 8) | Phases 3-4 (H6) |
| Optional | Email the SKY-Piano authors; Globus access for MAESTRO-E; Zenodo request for CIPI | Better validation data |
| Git | Nothing is committed yet | A baseline commit |

## How to resume (for the next lead session)

1. Read this file, then `DECISIONS.md` (the most recent entries) and the `WORKBOARD.md` log.
2. Check each in-flight ticket's folder for results. Agents write a README/spec plus a WORKBOARD log
   line when they finish. Any experiment with a Provisional verdict and no `## Audit` section needs
   `eval-auditor`.
3. Agents that were interrupted: their tickets show "in progress" in WORKBOARD with no finished log
   line. Re-dispatch the role agent with the ticket id and tell it to check existing artifacts before
   recomputing anything.
4. The R-08a blind annotations are already saved in
   `experiments/2026-09-28-R-08a-llm-phrase-pilot/artifacts/llm_annotations/`. To rescore, run
   `score.py --llm` on that folder.
