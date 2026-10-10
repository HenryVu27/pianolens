# PianoLens status

Last updated 2026-10-06 by the lead (R-10 audited: H1b falsified, scoped). Earlier refresh 2026-09-29
(feature-engineer, DEFECTS DF-08) from `EXPERIMENTS.md`,
`DECISIONS.md`, the `WORKBOARD.md` log and `docs/RESEARCH_LOG.md` Part 5). Details live in those
files. This page is the short version.

## What we have learned (audited results)

All rows are Confirmed with caveats by `eval-auditor`; the caveats are in `EXPERIMENTS.md`.

| Exp | Question | Answer |
|---|---|---|
| R-01 | Do PercePiano's 19 rating scales reduce to a few factors? | Yes: 3-5 factors, with one dominant "general quality" factor. Individual raters are noisy but not simpler than the panel. |
| R-02 | Is expert expression low-dimensional (H1)? | Not as stated: whole-piece curves need about 19 components for 80% of variance. The part experts *share* is low-rank (3-5 components, about 35-46% of variance); the rest is individuality. |
| R-03 | Does CrescendAI's audio (MuQ) result hold? | It reproduces (0.509 vs 0.536) but collapses on unseen works (pooled R² below 0). Within-passage ranking is 59-62%. |
| R-04 | Can interpretable MIDI features match MuQ (H3)? | Yes, non-inferior on unseen works in all 4 variants. Both models sit at single-rater level; the ceiling (about 0.74 WP rho) is far higher. |
| R-05 | Does an audio skill probe exploit recording context (H8)? | Yes, on simulated contexts: "A frozen-MuQ skill probe exploits recording context about as much as an explicit context label would. The size does not transfer to real audio." Beginner vs advanced AUC 0.870 with context fixed, 0.943 confounded as in MAJEPPA. |
| R-06 | SyMuPe or Pianist Transformer? | They tie on unseen pieces; the pre-registered tie-break picks SyMuPe. Raw likelihood rates deadpan playing above every expert, so it is never a quality score. |
| R-08a-d | Can Claude find phrase boundaries from a text rendering of the score? | Yes. End F1 about 0.74-0.82 across Mozart (0.817), disguised scores (0.802), J. C. Bach (0.750) and Romantic pieces (0.737, fragile), while the rule detector falls from 0.57 to 0.39. Explicit recall is ruled out; familiarity with the structure is not. |
| F-05e | Do LLM boundaries recover the per-phrase tempo measure? | Yes at the pooled level: concave_excess 0.418 (LLM) vs 0.473 (DCML), paired -0.055; LLM beats the detector by +0.221. Carried by Batik (one pianist); on Romantic pieces the LLM loses -0.124 (placement loss). Merging short phrases does not help. |
| R-09 | Does coherence rise with skill (H4)? | Inconclusive. No trend within matched contexts from beginner to advanced student; the top levels are confounded with concert/demo context. |
| F-07 | Is a pianist's take-consistent timing personal intent (H5)? | No: a cross-pianist control passes too, so the consistent part is shared piece timing. A pianist's own take-to-take variation is mostly unstructured, which justifies treating it as noise. |
| R-07 | Does fine-tuning SyMuPe on piece-disjoint PianoCoRe help, and is there a usable typicality score? | No: fine-tuning harms per-note prediction on unseen sensor/Disklavier pieces (PercePiano -0.051; Vienna and (n)ASAP agree), slightly helps on transcribed MIDI, so R-10 uses frozen SyMuPe. S-LR passes the deadpan battery but is a flatness detector plus a noise penalty, matched by a model-free amount-of-expression baseline, and blind to halved expression (AUC 0.491): not used. The H1b preview is uninformative (16 held-out real experts reach only 0.25-0.27 of the 0.50 bar); H1b is now measured by mean-curve R²c against an expert oracle (DECISIONS 2026-10-05). Two independent audits agree. |
| R-10 | Can a score-conditioned model predict what experts share (H1b)? | **No, H1b falsified (scoped to frozen SyMuPe).** On 56 fresh pieces the model's mean curve explains 0.15 of the velocity and 0.07 of the log IOI consensus (16 experts: 0.88). Shape is partly right (r 0.67 / 0.55); a perfect amplitude would still give at most 0.45 / 0.31. No better than a score-feature ridge on R²c. Interpretation stays anchored to expert recordings (DECISIONS 2026-10-06). |
| R-11 | Do expert performances and the report follow what teachers mark (3 tonebase annotated scores, pilot)? | Encoding is reliable (two blind encoders, category kappa 0.97, bar maps identical). Experts following the marks: inconclusive (0.634 [0.503, 0.750]; 0.598 with the waltz hand fix). The report does not notice a removed marked effect: its per-bar tempo/loudness channels cannot see single-note demands even at 4x (BL-32). About a third of annotations are MIDI-observable. |
| BL-16 | Can repeated takes estimate a learner's noise floor (Rach3 Hanon)? | Yes, within one sitting. Across days, takes carry structured drift, so timing noise uses same-sitting takes only (O-01 guidance: 2-3 takes in one sitting). A second beginner is still needed. |

## Engineering results accepted by the lead (tickets, not audited experiments)

- **A-01 phone-audio baseline:** transcription keeps onset timing (Transkun onset rsd 2.3 ms in the
  controlled check); Henry's takes have wrong and missed notes near the transcription floor but
  extras of 15-29% of score notes on 3 of 5 takes (3.0-29.3% across all five), cause unverified.
- **A-01b extra-note filter:** real-room microphone audio (PianoVAM) does not reproduce Henry's
  high fixed-pitch extras. The rule filter loses 0.10% of true notes and is opt-in; extras stay low
  confidence.
- **F-08b / F-08c report fixes:** timing flags are no longer experimental (Disklavier targets are
  not over-flagged); recurring errors count only for wrong pitches that pass the expert filter; a
  per-bar expert check (q80 notable, q99 strong, at least 5 same-capture experts) suppresses
  score or edition artefacts; extras never count toward tiers on transcribed input.
- **P-01 comparison engine:** A/B clips per flagged passage (your recording, you on the reference
  piano, a typical and a contrasting expert).
- **P-02 local app:** pick a piece, upload audio or MIDI, get the report and the A/B player, all on
  this Mac (`docs/APP.md`).

## What we have built

- **Data:** PianoCoRe tier A cache (157k aligned performances), loaders for every dataset in
  `DATASETS.md` (now including six DCML phrase-annotated corpora), a synthetic mistake set from
  100 (n)ASAP performances, Rach3 Hanon takes, and a 4.4 GB PianoVAM audio subset.
  Since 2026-10-01: Henry's tonebase lesson export (D-14), whose 21 teachers' annotated scores
  mark bars and notes in pieces with up to 2,011 expert performances (pilot: R-11).
- **Alignment:** mean F1 0.964 on (n)ASAP; picks the repeat path automatically.
- **Tier A, correctness:** bar-level any-error F1 0.99 on synthetic mistakes; missed notes per bar;
  per-bar expert check.
- **Tier B, control:** timing noise net of expert consensus, broad and strict evenness, hand sync,
  tempo stability, pedal blur (harmony rule F1 0.761 against DCML labels).
- **Tier C, shaping:** structural coherence (velocity and articulation primary), per-phrase tempo
  arcs, repeated material, voicing, dynamics compliance, cadence detector.
- **Tier D, interpretation:** expert band, windowed shared core, two-sided typicality with a
  too-flat guard, notable/strong per-bar flags.
- **Report card (F-08):** MIDI or transcribed audio in, a self-contained HTML report out, with
  "What to practise" (CLI `scripts/pianolens_report.py`).
- **Audio:** Transkun 2.0.1 front end on this Mac, the opt-in extra filter, a deterministic
  renderer (Salamander).
- **Comparison engine and local app** (P-01, P-02).
- **Listening study (S-01/S-03):** degradation generator (7 dimensions), protocol with power
  analysis (about 96-160 listeners), local-only study app with 592 pilot clips.
- **Evaluation harness:** grouped splits, cluster bootstrap, rater parity, Bradley-Terry,
  dimensionality nulls.
- **Research log** (`docs/RESEARCH_LOG.md`, 5 parts) and the scoring-model explainer
  (`docs/SCORING_MODEL.md`).

## Open caveats that shape the plan

- **No measure is shown to rise with skill** once recording context is matched (D-10, R-09). A
  single trustworthy quality grade does not exist yet: the best models agree with the panel about
  as well as one rater.
- **Velocity, pedal and extra notes from transcribed audio are low confidence** (D-10, A-01).
- **The report still uses the cadence detector for phrase boundaries,** not the LLM (DF-02).
- **Pedal and evenness rarely tier:** they need at least 10 same-score references; the app supplies
  them only for key-captured MIDI of pieces without PianoCoRe references (DF-05, `docs/APP.md`).
- **Known untested gaps:** staff is not hand (BL-19), dense passages (BL-20), fast repeated notes in
  phone audio (BL-21), the source of Henry's high extras (BL-22).

## In flight (2026-10-06)

- **R-10** (H1b): audited 2026-10-06 (Confirmed with caveats); the RTX box finished the
  secondary arms 2026-10-10 (audited addendum: Pianist Transformer R²c 0.061 / -0.045, worse than
  SyMuPe on timing shape; H1b reading unchanged). All post-audit fixes closed.
- **R-11:** audited (Confirmed with caveats); author README text fixes in progress. Follow-ups
  BL-31 (anchor rule), BL-32 (note-level channels, OWNER input), BL-33 (MusicXML hands).
- **R-07 follow-ups:** author text fixes (AUDIT section 9) after the origin/main merge.
- The 2026-09-29 wave from the research-log restructure: DF-02 (LLM phrase source in the report),
  BL-18 (strong tier on transcribed input), BL-19 / BL-20 (tier A gaps), BL-21 / BL-22 (audio
  gaps), BL-17 (Romantic LLM test), DF-03 / DF-04 and S-04 design (study), DF-05 / DF-06 / DF-08
  (app fixes and stale docs; see DEFECTS for their state).

## Waiting on Henry (OWNER)

Done 2026-10-05: O-03. The RTX 5080 box runs the R-07 job natively on Windows (CUDA 12.8 PyTorch; see the R-07 run record). R-10 and the audio front end can use it.

| Ticket | What | Unblocks |
|---|---|---|
| O-01 | Your own takes: 2-3 takes of 1-2 passages **in one sitting** (BL-16), ideally MIDI and phone together, of a piece in ASAP/PianoCoRe | A real learner's noise floor, ground truth for the phone extras, the first fully trustworthy report |
| BL-22 | Listen to the takes with the high extra notes (A-01b's next step) | Whether the extras are real sound or a transcription artefact |
| O-02 | Listening study S-03 is **built** (`study/app/`, `study/protocol-S03.md`). Decisions: N (96 / 160), format, consent and payment, ethics. **First step: you do the pilot** (about 75 min) | Phases 3-4 (H6) |
| R-05 | Decide whether to re-fetch MAJEPPA YouTube audio for a real-audio H8 test | H8 outside simulation |
| BL-29 | Check tonebase's terms of use for your export; until then it is personal research use only, nothing committed or published | Any publication that uses the tonebase annotations |
| O-04 | A cloud GPU budget (if any) | Runs too large for the 5080 |
| Optional | Email the SKY-Piano authors; Globus access for MAESTRO-E; Zenodo request for CIPI | Better validation data |
| CLAUDE.md research bet | R-10 falsified H1b. Proposed wording: "... a low-dimensional, piece-conditioned expressive space (anchored by expert performances of the piece; R-10: the score alone predicts only part of the expert consensus)" (DECISIONS 2026-10-06) | The project's stated bet matches the evidence |
| BL-29 tonebase files | Decide whether `src/pianolens/data/tonebase.py`, its test and `scripts/extract_tonebase.py` (code and file-to-piece metadata only) are committed | A complete repo on the box |

O-03 (GPU box) is done: R-07 ran there (2026-09-29 to 2026-10-05).

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

## 2026-09-29 wave (audited)

- **BL-17:** Claude's phrase analysis on 24 Romantic pieces averages 0.635 (0.549-0.720): inconclusive against the 0.70 bar, still far ahead of the rule detector (+0.33). R-08d's 0.737 is not confirmed.
- **DF-02:** reports now use cached Claude phrase boundaries, with accuracy disclosures and an "undetermined" label when they disagree in sign with the detector (takes 01 and 04).
- **BL-18 / BL-18b:** strong note flag on transcribed input uses the interim R1(0) rule plus "passage not heard". BL-18b is FAIL by its pre-registered rule; the revert was not applied (disclosed deviation, DECISIONS). About 7 in 10 bars with 3 wrong notes become strong on transcribed input because the checker loses notes (DF-12, cause DF-13).
- **BL-19 / BL-20 / BL-23 / DF-09 / DF-10:** staff-vs-hand proxy about 5% of notes (recall unproven); fast passages cost wrong-note naming, not bar detection; same-pitch repair pass is the default; staff numbering fixed on all 805 catalogue scores.
- **BL-21 / BL-22:** fast same-pitch repeats under about 100 ms are lost by transcription (now low confidence). The high phantom notes on the owner's phone takes are a separate recurring C-major melody, source undetermined: **OWNER listening check.**
- **Study:** DF-03 and DF-04 fixed; S-04 pairwise protocol drafted with 7 OWNER decisions (study/protocol-S04.md section 11).
- **R-07:** ran on the owner's RTX 5080 (finished 2026-10-05; audited, see the table above).
