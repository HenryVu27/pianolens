# PianoLens research program

Written 2026-09-27. Owner: Henry. This is the plan. `WORKBOARD.md` breaks it into tickets.
Sources for every claim below are in `docs/research/2026-09-27-landscape.md`.

## 1. The core idea

### 1.1 Piano is the most constrained instrument

After the hammer leaves the string, the player cannot touch the sound. Per note the player controls
onset time, velocity (which sets loudness and brightness together), and release time. Across the
performance they control three pedals (sustain depth, una corda, sostenuto). Disklavier playback of
recorded MIDI is close to indistinguishable from the original; "touch" research finds only small
residual differences (finger-key noise). So **MIDI + score is a near-complete description**.

### 1.2 Expressive deviations are hierarchical

| Layer | What varies | Rough free parameters |
|---|---|---|
| Global | tempo, dynamic level, legato bias, pedal density | about 4 |
| Phrase | tempo arcs, dynamic arcs | 2-4 per phrase |
| Beat / meter | accent patterns, metric micro-timing | a few per meter type |
| Note | melody lead, voicing, chord spread, accents on dissonance | mostly predictable from score |
| Noise | unintended motor variation | not interpretation |

Evidence: Repp (1998) found "at least four" timing strategies, plus idiosyncratic variation, across 115 recordings of Chopin Op. 10 No. 3, bars 1-5. Repp (1992) found that final ritardandi are parabolic, with one degree of freedom. The KTH rule
system generates acceptable performances from about 30 parameterized rules. Basis Mixer models
expression as a weighted sum of score features. Timing patterns scale with tempo (TISMIR 2026).
Judges' rubric dimensions are highly intercorrelated (Thompson and Williamon 2003).

### 1.3 Two regimes

- **Skill** (amateur vs expert): models reach about 93% pairwise, but the skill groups in that dataset also
  differ in repertoire and recording setup, so 93% is a confounded upper bound. The hypothesis is that
  the true signal is motor control, and heuristics should be enough here.
- **Taste** (expert vs expert): about 60% on Chopin Competition entrants. Humans disagree here too.
  This is the research frontier.

Most learners live in the skill regime. The tool must be excellent there first.

## 2. Hypotheses

| ID | Hypothesis | Tested in | Falsified if |
|---|---|---|---|
| H1 | Expressive variation across expert performances of one piece (PianoCoRe tier A pieces with 50 or more performances; D-03 measures how many there are) is low-dimensional: at most 10 components explain at least 80% of variance in normalized per-beat tempo + velocity curves. | Phase 2 | Needs more than 20 components for 80% on most pieces |
| H1b | (Added 2026-09-27 after R-02.) Given the score, the *shared* part of expert expression is predictable: a score-conditioned expression model explains at least 50% of the held-out variance in the *shared* expert components (the 3-5 above-null parallel-analysis components per piece from the R-02 audit, about 35-46% of between-performer variance), on unseen pieces. | Phase 5 | Explains 20% or less on unseen pieces |
| H2 | PercePiano's 19 rating dimensions collapse to 3-5 latent factors. | Phase 2 | Parallel analysis retains more than 8 factors |
| H3 | A score-aligned symbolic feature model matches or beats MuQ audio embeddings on PercePiano under leave-piece-out evaluation. PercePiano audio is rendered from its MIDI, so audio carries no extra information. | Phase 2 | Symbolic model is worse than MuQ by more than 0.05 R² (averaged over dimensions) with overlapping-free CIs |
| H4 | Structural coherence (the fraction of a performer's own expressive variance explained by score features) separates skill levels and correlates with rated quality. | Phases 1-2 | No monotone relationship with skill level in MAJEPPA / Expert-Novice / PianoCoRe |
| H5 | Repeated takes separate intent from noise: the between-take-consistent part of timing correlates with score structure; the inconsistent part does not. | Phase 1 | Consistent and inconsistent parts are equally explained by score features |
| H6 | Each expressive dimension has a measurable perceptual cost curve, and the curves differ enough to justify non-uniform feature weights. | Phase 3 | Cost curves are indistinguishable across dimensions |
| H7 | Among expert performances, blind pairwise preference is explained substantially by interpretable features (beyond "closeness to the mean"). | Phase 4 | Features explain no more than distance-to-mean alone |
| H8 | Audio-model skill accuracy partly reflects recording context. | Phase 2/6 | Accuracy unchanged when recording context is held fixed. MAJEPPA has context labels but MIDI only; its audio would have to be re-fetched from YouTube (OWNER decision), or another design used. |

## 3. Phases

Each phase lists its deliverables and exit criterion. Phases 0-2 need no GPU and no human subjects.

### Phase 0: infrastructure
- Datasets downloaded and registered (`DATASETS.md`), loaders returning common types.
- Note alignment (parangonar DualDTW, Nakamura as cross-check) validated against (n)ASAP ground truth.
- Evaluation harness: grouped splits (piece, performer), bootstrap CIs, rater-parity metric.
- **Exit:** alignment accuracy on (n)ASAP reported. `uv run pytest` green.

### Phase 1: scorer v1 (symbolic)
- Tier A correctness: correct / extra / missed / wrong-pitch, ±50 ms, ornament whitelist.
- Tier B control: residual timing jitter after smooth tempo fit, evenness in passages the score
  marks as even, hand synchrony, tempo stability, pedal-over-harmony-change blur.
- Tier C shaping: structural coherence (H4), repeated-material consistency, voicing ratio,
  dynamic-marking compliance.
- Tier D interpretation: likelihood under the expert distribution (not distance to the mean). Use
  windowed or per-phrase expert subspaces and a score-conditioned expression model, not a single
  whole-piece PCA basis (R-02: whole-piece expert expression needs about 19 components for 80%).
- Repeated-take analysis (H5).
- Report generator: per-bar flags, curves against the expert band.
- **Exit:** runs end to end on a (n)ASAP performance and on a MIDI recording of Henry's playing.

### Phase 2: is it low-dimensional? (first paper)
- H1: PCA / functional PCA of expert curves across PianoCoRe pieces with 50+ performances.
- H2: factor analysis of PercePiano ratings (per-rater data is in `labels/total_2rounds.csv`).
- H3: symbolic features vs MuQ (frozen, layer-wise linear probes) vs both, leave-piece-out, with
  rater parity as the ceiling. Reproduce the published MuQ number first.
- H8: shortcut check on skill classification with recording context controlled.
- **Exit:** each hypothesis gets a verdict audited by `eval-auditor`.

### Phase 3: perceptual cost curves (second paper candidate)
- Degrade expert MIDI along one dimension at a time (timing jitter, flattened dynamics, pedal blur,
  voicing inversion, wrong notes, articulation stretch), at graded levels.
- Render with one fixed piano model. Listening test: detection threshold and preference cost.
- Also produces unlimited synthetic training pairs for per-dimension detectors.
- **Exit:** cost curves with CIs for each dimension (H6).

### Phase 4: pairwise preference dataset (the missing dataset)
- Stimuli: same passages across skill levels (PianoCoRe experts, aligned Aria-MIDI amateurs,
  Expert-Novice, Henry). All rendered with one piano model so audio quality is constant.
- Blind, audio only, order counterbalanced, no performer labels, musicians and non-musicians
  separately, at least 20 comparisons per item (judgements at least 10 x items), SSR at least .8, plus split-half
  reliability (corrected 2026-09-28; the earlier "12-17" was unsupported).
- Bradley-Terry scale, then regress on features (H7).
- **Exit:** released dataset + analysis. Needs IRB-style consent text and recruiting (OWNER).

### Phase 5: expression model
- Train or fine-tune a score-conditioned expression model (Pianist Transformer or ScorePerformer
  lineage) on PianoCoRe-A. Uses: typicality likelihood, synthetic expert bands for pieces not in
  the corpus, the expected expression that tier C compares against.
- Compute: RTX 5080 first. Cloud only if it does not fit.

### Phase 6: audio front end
- Fine-tune Transkun / Aria-AMT on synthetic phone-like audio: rendered MIDI, room impulse
  responses, phone mic EQ, noise.
- Per-device loudness calibration (user plays one note at pp, mf, ff).
- Score-informed velocity refinement.
- **Exit:** phone recording to scorer with measured degradation vs MIDI input.

### Phase 7: feedback layer and user study
- An LLM turns measured features into teacher language, strictly grounded in the numbers.
- LLM score analysis (phrases, cadences, melody voice), validated against Batik annotations first.
- Longitudinal: does feedback speed improvement? Henry is subject zero.

## 4. Metrics

| What | Metric |
|---|---|
| Correctness | Precision / recall / F1 of extra, missed, wrong-pitch labels vs human-labeled mistakes (MAESTRO-E, Burgmüller) |
| Alignment | Note-match accuracy vs (n)ASAP ground truth |
| Quality prediction | R², Spearman, and rater parity. The model's correlation with the panel mean is compared with each held-out rater's correlation with the mean of the others. |
| Preference | Held-out pairwise accuracy against the Bradley-Terry scale |
| Localization | Correlation with teacher-marked problem bars (Profy reports r = 0.61) |
| Usefulness | Rate of improvement with vs without feedback (Phase 7) |

Always: leave-piece-out, bootstrap 95% CIs, and a trivial baseline in the same table.

## 5. Risks

- **Licenses:** nearly all data is non-commercial. Research only until data is replaced.
- **Coverage:** PianoCoRe covers only public-domain repertoire.
- **Transcribed "MIDI":** much of the reference data is transcribed from audio. Validate on
  human-verified subsets such as (n)ASAP.
- **Structural coherence could reward formulaic playing.** Phase 4 checks this against human
  preference.
- **Human subjects:** Phases 3-4 need consent and recruiting. They are OWNER-gated.
