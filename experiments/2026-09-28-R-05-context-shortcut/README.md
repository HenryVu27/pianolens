# Recording-context shortcut check on simulated recordings of MAJEPPA MIDI
Ticket: R-05    Hypothesis: H8    Status: Provisional

## Question

H8 (plan): audio-model skill accuracy partly reflects recording context. MAJEPPA has skill and
context labels but no audio (fetching it from YouTube is an OWNER decision), so this is the
substitute design in WORKBOARD R-05: render MAJEPPA's MIDI with one fixed piano, apply simulated
recording contexts, and ask whether a frozen-MuQ skill classifier's accuracy moves with context
when context is confounded with skill the way it is in MAJEPPA.

What this can and cannot show:

- Every clip exists in every context, rendered from the same MIDI. Any skill signal in the
  matched datasets comes from the MIDI (notes, timing, velocity, repertoire). Any extra accuracy
  in the confounded dataset comes from the simulated context alone.
- So a positive result shows that frozen MuQ embeddings *can* carry the context shortcut at
  MAJEPPA's confound strength, and how large it is for these simulated contexts. It does not
  measure the size of the shortcut in real YouTube audio: real contexts differ in pianos,
  rooms, microphones, audience noise and video codecs far more than four simulated contexts.
  A negative result would say the shortcut needs more than room, band limit, noise and codec.

## Falsified if

Primary metric: out-of-fold ROC AUC for beginner vs advanced, pooled over folds.

- delta_infl = AUC(CC) - mean over the 4 contexts of AUC(M_ctx): how much the confounded
  dataset inflates the estimate relative to context-matched datasets.
- delta_short = AUC(CC) - AUC(CS): how much the confounded model loses when test contexts are
  made independent of skill (permuted within the test fold; mean over K = 20 permutations).

Verdict (group bootstrap, 2,000 replicates, 95% percentile CI):

- **Supported:** the CI lower ends of both delta_infl and delta_short are above 0.
- **Falsified:** both CIs lie entirely inside (-0.02, +0.02) AUC (accuracy unchanged when context
  is held fixed, within 0.02).
- **Inconclusive:** anything else.

Validity check (negative control, not part of the verdict): RR (context permuted over the whole
set, independent of skill, for train and test) should not beat the matched mean. If
AUC(RR) - mean AUC(M) has a CI lower end above +0.02, the design is broken (the classifier gains
from context diversity itself) and the verdict is withheld.

## Reachability (run before any embedding was analysed)

`reachability.py`: synthetic scores on the real sample's labels and CV groups; conditions share a
clip term and a group term and differ by an independent term (score correlation rho between
conditions), true AUC about 0.72; 200 simulations x 400 bootstrap replicates.

| score correlation rho | true shift (mean delta) | mean CI half-width | P(supported) | P(falsified) | P(inconclusive) |
|---|---|---|---|---|---|
| 0.90 | 0 (0.000) | 0.010 | 0.02 | 0.85 | 0.13 |
| 0.90 | 0.1 d (+0.020) | 0.010 | 0.975 | 0.005 | 0.02 |
| 0.90 | 0.2 d (+0.041) | 0.010 | 1.00 | 0 | 0 |
| 0.69 | 0 (0.000) | 0.019 | 0.005 | 0.015 | 0.98 |

The rho 0.69 cases with a shift were still running when this README was written; they are
appended to `artifacts/reachability.json` and do not change the rule. **Reading:** with
rho 0.69, a zero effect almost always ends "inconclusive" (falsified 1.5%), so "falsified" is
reachable only if the conditions' scores are highly correlated (about 0.9). An effect of about
+0.02 AUC or more is detected almost surely at rho 0.9.

So "falsified" is reachable (most likely outcome at zero effect when conditions' scores are highly
correlated, as they are when the same clips are scored by similar models) and a false "supported"
is rare. If the scores of different conditions correlate less (rho 0.69), the CIs widen and
"inconclusive" becomes more likely at zero effect. The observed correlation between M and CC
scores is reported with the results.

## Data

- MAJEPPA (HF commit 7a462f4, DATASETS.md), Transkun-transcribed MIDI. Performances with a score
  id (for piece grouping), at least 10 s between first and last onset, a known expertise level and
  a recording type in the mapping below.
- Sample (`build.py`, seed 0): 250 per expertise level, drawn uniformly within level (so each
  level keeps its real mix of recording types). 1,500 clips, 626 pieces, 1,392 source videos.
- Excerpt: the first 30 s from the first onset (shorter clips kept whole; pedal state carried in).
- Primary set: beginners (child + adult beginner, 500) vs advanced (child professional + piano
  teacher + virtuoso, 750); intermediate (250) is used only in the 3-group secondary.

Real MAJEPPA recording type -> simulated context (the confound; same mapping for every clip):

| recording_type | context |
|---|---|
| demo_class, slow_demo, fast_demo | clean (close mic, small treated room) |
| practice, sight_read | phone_room (phone in a living room) |
| performance | recital_phone (phone in the audience of a recital hall) |
| concert_performance | concert_hall (good microphones at a distance, large hall) |

Contexts in the sample:

| level | clean | concert_hall | phone_room | recital_phone |
|---|---|---|---|---|
| child_beginner | 5 | 0 | 125 | 120 |
| adult_beginner | 6 | 0 | 221 | 23 |
| adult_intermediate | 11 | 0 | 197 | 42 |
| child_professional | 3 | 0 | 79 | 168 |
| piano_teacher | 192 | 43 | 8 | 7 |
| virtuoso | 0 | 250 | 0 | 0 |

## Audio

- Render: S-02 fixed renderer, `pianolens.audio.render.CRESCENDAI_SALAMANDER` (Salamander C5
  Light, FluidSynth 2.6.1 settings pinned, 24 kHz mono), rendered once per clip and cut to 30 s.
- Context: `pianolens.audio.phone.simulate_phone` (synthetic room IR with RT60 and
  direct-to-reverberant ratio, 2nd-order high/low-pass, pink noise at an SNR, peak -3 dBFS),
  then an AAC round trip with ffmpeg (all MAJEPPA audio came from YouTube). Parameters are drawn
  uniformly per clip and context, seeded by (clip, context):

| context | RT60 s | DRR dB | high-pass Hz | low-pass Hz | SNR dB | AAC kbps |
|---|---|---|---|---|---|---|
| clean | 0.20-0.35 | 10-15 | 30-40 | none | 50-60 | 160 |
| phone_room | 0.40-0.80 | 0-6 | 100-200 | 7,000-10,000 | 25-40 | 96 |
| recital_phone | 1.2-1.8 | -6-0 | 100-200 | 7,000-10,000 | 25-40 | 96 |
| concert_hall | 1.6-2.4 | -3-3 | 30-40 | none | 45-60 | 160 |

  These ranges are my judgement of typical settings, not measurements. Every context is
  peak-normalised, so absolute level carries no context information.
- Embeddings: MuQ-large-msd-iter, fp32, 24 kHz, MPS, whole 30 s excerpt, mean || population
  std pooling as in R-03. Primary layer: L9-12 average (R-03's choice). All 13 hidden states are
  cached.

## Splits

- Outer: 5-fold grouped CV, `pianolens.eval.group_kfold(groups, 5, seed=0)`. Groups are the
  connected components of (piece_id, recording_id), so neither a piece nor a source video
  straddles train and test (in this sample they coincide with pieces: 626 groups in the full sample, 559 in the binary set).
- Leave-performer-out: performer identity is not released; recording_id is a video, nearly one
  per clip (1,392 videos for 1,500 clips), and videos are already inside the groups. No separate
  leave-performer-out split is possible.
- Inner: C of the logistic regression chosen from {1e-4, 1e-3, 1e-2, 1e-1} by grouped 4-fold CV
  AUC on the training rows only.
- Robustness (not in the verdict): fold seeds 1 and 2; layer 6 instead of L9-12.

## Baselines

- Trivial: constant score, AUC 0.5.
- Context label only (`ctx_oracle`): logistic regression on the one-hot real context. The AUC a
  pure shortcut reaches.
- Symbolic MIDI stats of the excerpt (`symbolic`): log note rate, mean and SD velocity, mean
  pitch, log note count. How much skill signal simple MIDI statistics carry.
- No rater ceiling: labels are self-reported categories, not ratings.

## Method

Classifier: StandardScaler + L2 logistic regression (sklearn 1.9.1). Conditions (every clip in
every condition; only its audio context changes):

| condition | train contexts | test contexts |
|---|---|---|
| M_ctx (x4) | all ctx | all ctx |
| CC | real mapping | real mapping |
| CS | real mapping | permuted within test fold (K = 20) |
| CA | real mapping | drawn from the other class's context mix (K = 20) |
| Cm_ctx (x4) | real mapping | all ctx |
| RR (negative control) | one global permutation | same permutation |

Also reported: AUC of each advanced level against all beginners (CC, CS, M mean); 3-group
(beginner / intermediate / advanced) balanced accuracy for M mean, CC and CS; context decoding
(4-class, every clip in every context, grouped by clip group, fixed C = 1e-2, balanced accuracy).

Seeds: sample 0; folds 0; RR permutation, CS permutations and CA draws from
`default_rng(1)`; bootstrap `default_rng(2)`; context parameters from sha256("R-05|clip|context").

## Command

```
OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 uv run python experiments/2026-09-28-R-05-context-shortcut/build.py --workers 6
uv run python experiments/2026-09-28-R-05-context-shortcut/reachability.py
uv run python experiments/2026-09-28-R-05-context-shortcut/analyze.py
uv run python experiments/2026-09-28-R-05-context-shortcut/analyze.py --fold-seed 1 --skip-secondary
uv run python experiments/2026-09-28-R-05-context-shortcut/analyze.py --fold-seed 2 --skip-secondary
uv run python experiments/2026-09-28-R-05-context-shortcut/analyze.py --layer 6 --skip-secondary
```

Git: HEAD 3af124d plus uncommitted changes (this folder is new).

## Disclosures (before results)

- An 8-clip timing pilot of `build.py` ran before this README (1.96 s per clip for 4 contexts,
  MuQ 1.45 s). Its embeddings are reused (deterministic). No labels or scores were looked at.
- `analyze.py` was smoke-tested on random synthetic embeddings (scratchpad copy; no real
  embeddings) to check that it runs; the synthetic case with decodable context gave "supported"
  and the negative control stayed near 0.
- The full `build.py` run (embedding extraction only) was started before this README was written,
  to overlap with the reachability simulation. `analyze.py` had not been run on any embedding when
  this README was written.

## Results

Pre-registration header (everything above) sha256 `7add1490...f0c5` at 2026-09-28 19:13 CDT,
before `analyze.py` first ran on real embeddings. Build: 1,500 clips x 4 contexts, 2,178 s
(1.46 s per clip, nearly all MuQ), render config `fc5f24d36e3e`, FluidSynth 2.6.1, torch 2.14.0,
MPS fp32.

### Primary: beginner vs advanced, MuQ L9-12, fold seed 0

n = 1,250 clips (500 beginner, 750 advanced), 559 groups, OOF ROC AUC, 95% group-bootstrap CI
(2,000 replicates). Contexts by class: beginner clean 11 / phone_room 346 / recital_phone 143 /
concert_hall 0; advanced 195 / 87 / 175 / 293.

| Condition | AUC [95% CI] |
|---|---|
| Trivial (constant) | 0.500 |
| Symbolic MIDI stats of the excerpt | 0.760 [0.729, 0.791] |
| Context label only (pure shortcut) | 0.867 [0.842, 0.892] |
| M_clean | 0.876 [0.854, 0.896] |
| M_phone_room | 0.872 [0.848, 0.892] |
| M_recital_phone | 0.868 [0.844, 0.889] |
| M_concert_hall | 0.865 [0.839, 0.887] |
| **M mean (context held fixed)** | **0.870 [0.847, 0.891]** |
| **CC (confounded, as in MAJEPPA)** | **0.943 [0.928, 0.957]** |
| **CS (trained confounded, test contexts permuted)** | **0.730 [0.708, 0.750]** |
| CA (trained confounded, contexts swapped between classes) | 0.475 [0.446, 0.503] |
| Cm_clean / phone_room / recital_phone / concert_hall | 0.800 / 0.821 / 0.810 / 0.800 |
| RR (negative control: random contexts, train and test) | 0.872 [0.850, 0.893] |

| Delta | Estimate [95% CI] |
|---|---|
| **delta_infl = CC - M mean** | **+0.073 [+0.055, +0.092]** |
| **delta_short = CC - CS** | **+0.214 [+0.196, +0.232]** |
| CC - CA | +0.469 [+0.442, +0.495] |
| Negative control RR - M mean | +0.002 [-0.004, +0.008] |

Context decoding (4 classes, every clip in every context, 6,000 rows, fixed C): balanced accuracy
0.997 (chance 0.25); 18 of 6,000 rows misclassified, all phone_room / recital_phone /
concert_hall confusions.

Per advanced level against all beginners (descriptive):

| Advanced level | CC | CS | M mean |
|---|---|---|---|
| child_professional (mostly recital / phone) | 0.879 | 0.765 | 0.901 |
| piano_teacher (mostly clean demos) | 0.958 | 0.628 | 0.778 |
| virtuoso (all concert) | 0.994 | 0.795 | 0.932 |

Secondary, 3 groups (beginner / intermediate / advanced, 1,500 clips), balanced accuracy (chance
0.333; 500 bootstrap replicates): M mean 0.550 [0.528, 0.570], CC 0.677 [0.648, 0.706], CS 0.485
[0.469, 0.502]; delta_infl +0.127 [+0.103, +0.154], delta_short +0.191 [+0.172, +0.211].

### Robustness (pre-registered, not in the verdict)

| Variant | M mean | CC | CS | delta_infl | delta_short | RR - M |
|---|---|---|---|---|---|---|
| L9-12, fold seed 0 (primary) | 0.870 | 0.943 | 0.730 | +0.073 [+0.055, +0.092] | +0.214 [+0.196, +0.232] | +0.002 [-0.004, +0.008] |
| L9-12, fold seed 1 | 0.865 | 0.943 | 0.731 | +0.078 [+0.061, +0.098] | +0.212 [+0.195, +0.231] | -0.000 [-0.006, +0.006] |
| L9-12, fold seed 2 | 0.863 | 0.942 | 0.727 | +0.079 [+0.061, +0.098] | +0.215 [+0.197, +0.234] | -0.009 [-0.016, -0.001] |
| Layer 6, fold seed 0 | 0.858 | 0.947 | 0.730 | +0.089 [+0.070, +0.110] | +0.217 [+0.200, +0.235] | -0.005 [-0.014, +0.004] |

Chosen C (inner CV): 1e-3 in nearly every fold of every matched and random-context model; 1e-2
in 4 of 5 confounded folds.

### Post-hoc checks (added after results; not in the verdict)

`artifacts/posthoc_checks.log`.

- **Late reachability cases** (finished after the header was written; `artifacts/reachability.json`):
  rho 0.69 with shift 0.1 d (+0.020): supported 0.455, inconclusive 0.545; shift 0.2 d (+0.038):
  supported 0.98.
- **Reachability assumption.** Spearman correlation between CC and M_ctx out-of-fold scores
  0.79-0.80, between the two assumed cases (0.69 and 0.90). Observed CI half-widths about 0.018,
  close to the rho 0.69 simulation. The effects are 4 to 12 times the half-width, so the
  verdict does not depend on this assumption.
- **Within one real context, the confounded model is a worse skill model.** AUC among the clips
  of one context: phone_room 0.889 (CC) vs 0.901 (M_phone_room); recital_phone 0.825 vs 0.885;
  clean 0.594 vs 0.666 (11 beginners only). concert_hall has no beginners.

## Verdict (Provisional)

**Supported by the pre-registered rule** (both CI lower ends above 0), in all four robustness
variants. The negative control passes (random contexts do not help: RR - M within +/-0.01).

In plain terms, for rendered MAJEPPA MIDI with four simulated recording contexts:

1. **MuQ embeddings identify the simulated context almost perfectly** (0.997 balanced accuracy).
2. **With MAJEPPA's real context mix, the estimated skill AUC rises from 0.870 to 0.943.** That
   is +0.073, even though the audio carries no more skill information. For 3 groups, balanced
   accuracy rises from 0.550 to 0.677.
3. **The confounded model depends on context.** Once test contexts are independent of skill, it
   falls to 0.730, 0.14 below a model trained with context held fixed. With the contexts swapped
   between classes it is at chance (0.475).
4. **The inflation sits where the confound is strongest.** Piano teachers (mostly clean demos)
   against beginners: 0.778 matched vs 0.958 confounded. Child professionals, whose recital and
   phone contexts resemble the beginners', are slightly *harder* to separate once confounded
   (0.901 vs 0.879).

So a skill classifier trained and tested on MAJEPPA-like audio would report an accuracy that is
partly recording context, and its accuracy on context-independent audio would be lower than the
confounded estimate suggests. This extends CLAUDE.md rule 3 from a caution to a demonstrated
mechanism for frozen MuQ features.

## Threats to validity

- **Simulation, not real audio.** The four contexts are my parameter ranges for a synthetic
  room, band limits, pink noise and AAC. They are not calibrated to MAJEPPA's YouTube videos.
  Real contexts also differ in piano, microphone, audience noise and video codec. The *size* of
  the shortcut here does not transfer. Real contexts are probably more varied (harder to decode
  perfectly) and also carry cues the simulation lacks (instrument quality). The direction and
  the mechanism are what this shows. Rendered-audio results do not transfer to real recordings
  until tested (rules/experiments.md).
- **Contexts are more separable than real ones.** Their parameter ranges do not overlap in RT60
  or band limit (except recital_phone vs concert_hall RT60). Overlapping ranges would lower
  context decoding and probably the inflation. Not tested.
- **The matched AUC (0.87) is not a clean skill measure either.** Even with context fixed, the
  rendered MIDI carries repertoire: beginners play easier, slower pieces. Simple note-rate and
  velocity statistics alone reach 0.760. Piece-held-out CV removes piece identity, not
  difficulty. The deltas are unaffected (every condition shares the same clips and MIDI), but
  0.87 must not be read as MuQ's skill accuracy.
- **Transcribed MIDI.** MAJEPPA is Transkun output. Velocity is compressed (D-10: slope 0.64)
  and transcription artefacts are in every render. This is shared by all conditions.
- **One renderer, one piano.** The S-02 Salamander render already includes FluidSynth reverb and
  chorus. The "clean" context is therefore not dry.
- **Leave-performer-out is not possible.** Performer identity is not released; videos (1,392 for
  1,500 clips) are inside the CV groups.
- **Labels.** Beginner/advanced groups follow D-10. Intermediate is used only in the 3-group
  secondary.
- **Disclosed runs.** 8-clip timing pilot, a synthetic smoke test of `analyze.py`, and the build
  started before the README (all listed above). The robustness runs were pre-registered. The
  post-hoc checks are labelled.

## Audit (2026-09-28)

Auditor: `eval-auditor`. Verdict: **Confirmed with caveats.** H8 is supported by the
pre-registered rule on simulated contexts, and every number in the Results reproduces exactly.
The claim holds as a mechanism and a direction. Its size is close to what handing the classifier
the context label would give, so it measures MAJEPPA's confound strength more than anything
specific to MuQ. Three statements must be reworded (required fixes 1-3). Audit scripts and logs:
the auditor's scratchpad (`r05_audit/checks1-6.py`), not kept in the repo.

### Reproduction

- `analyze.py` rerun on copies of `embeddings.npz`, `sample.csv` and `excerpt_stats.csv` (only
  `ART` redirected): the primary log is identical line for line, and `results_*.json` for the
  primary, fold seeds 1 and 2 and layer 6 are identical to the stored files (except `wall_s`).
  That covers the 3-group secondary and the context decoding (0.997).
- Within-context post-hoc numbers reproduce (phone_room 0.889 vs 0.901, recital_phone 0.825 vs
  0.885, clean 0.594 vs 0.666).

### Pre-registration and timeline (subagent transcript, UTC)

- 23:37 `build.py` written, 8-clip pilot (this draws `sample.csv`); 23:38 full build started,
  `reachability.py` started; 23:49 `analyze.py` written (mtime unchanged since); 23:50 README draft
  in the scratchpad and the synthetic smoke test (random embeddings, the real `sample.csv` only
  for ids and labels). No command read real embeddings or scores before the header.
- 00:13:54 README written; `shasum` printed `7add1490...f0c5` at 19:13:55 CDT, and the current
  header (the 186 lines before `## Results`, minus the blank separator) still hashes to it.
  00:15:01 build finished; 00:15:18 first `analyze.py` run. Header before results: verified.
- **Undisclosed, harmless:** at 00:15:27 (after the header and the first analyze launch) the
  docstring of `build.py` and one `return` line of `reachability.py` were rewrapped for ruff E501.
  No behaviour change. Add one line to the Disclosures in the Results section.
- The rho 0.69 reachability cases with a shift finished at 19:18:56 CDT, after the first analysis,
  as the README says. They do not bear on the rule; observed effects are 4-12 half-widths.

### Splits and leakage

- Folds rebuilt for fold seeds 0, 1, 2: 5 x 250 clips, no `piece_id`, no `recording_id` and no
  `youtube_url` in two folds (1,149 videos = 1,149 recording ids in the binary set). No
  normalised composer + title maps to two piece ids. No two clips have identical excerpt stats.
- **Context copies cannot cross.** In every binary condition each clip enters once (in one
  context); train rows are `emb[tr, ctx_train[tr]]` and test rows `emb[te, a[te]]`, with `tr` and
  `te` group-disjoint, so a clip's other renderings are never in the training set of its own test
  fold. In the context-decoding run all 4 copies share a fold: the clip-major reshape matches
  `np.repeat(g3, 4)` (checked element-wise).
- Scaler and C are fit inside the training fold; C by inner grouped CV. Layer and seeds were
  pre-registered. No selection on test.
- Pooled out-of-fold AUC vs mean per-fold AUC: M mean 0.870 vs 0.872, CC 0.943 vs 0.944, CS 0.730
  vs 0.733; deltas +0.072 / +0.212. Pooling does not drive the result.

### Bootstrap unit

Groups are real clusters: 559 groups for 1,250 clips; 320 groups hold more than one clip (1,011
clips), largest 10. The bootstrap resamples pieces (with their videos), which is the right unit.
Performers are not identifiable (as disclosed).

### Is "matched" the right comparator?

Yes. The 4 matched sets agree within 0.011 (0.865-0.876), so the mean hides nothing, and RR (same
context diversity as CC, but independent of skill) gives the same 0.872. The negative control
passes in all four variants (fold seed 2 is slightly negative, -0.009 [-0.016, -0.001], so
diversity does not help; the withhold rule is one-sided).

### Separability: how large "should" the shortcut be?

The contexts' parameter ranges barely overlap, so MuQ decodes them at 0.997. With the context
effectively observed, the inflation should be what giving the classifier the context label
gives. Benchmark (auditor, post-hoc): in each outer fold, fit the matched MuQ model, take its
inner out-of-fold scores, and stack them with the one-hot real context in a low-regularised
logistic regression.

| Model | AUC | Test contexts permuted |
|---|---|---|
| Matched MuQ (M mean) | 0.870 | - |
| Matched MuQ score + explicit context label (stacked, mean over 4 contexts) | 0.959 | 0.705 |
| CC (context only in the audio) | 0.943 | 0.730 |

So CC reaches about 80% of the explicit-label inflation (+0.073 of +0.089) and of the
explicit-label shortcut (+0.214 of +0.254). (Appending the one-hot to the 2,048-d embedding under
the same L2 penalty gives only 0.916, because the penalty shrinks 4 columns among 2,052; the
stacked version is the fair ceiling.)

What survives:

- **Direction and mechanism:** a linear probe on frozen MuQ uses recording context when context
  and skill are confounded. It gains most of what an explicit label would give, and loses more
  than a matched model once the confound is broken (CS 0.730 vs matched 0.870).
- **Not the size.** +0.073 is close to a ceiling fixed by the confound strength (context label
  alone 0.867) and the MIDI signal. It is not a measure of how susceptible MuQ is. Real contexts
  are less separable (which lowers it) but carry extra cues such as the instrument (which could
  raise it). The README's first threat already says the size does not transfer. The results
  should also say that here the size is near the context-label ceiling (fix 1).

### Repertoire difficulty and its interaction with context

- Within the advanced class, context tracks difficulty: clean (teachers' demos) has a median of
  7.0 notes/s, and teachers' `slow_demo` clips 2.9 notes/s (the beginners' practice median is
  4.4-7.9). Teachers are the advanced level that simple MIDI statistics separate worst (symbolic
  AUC 0.702 vs 0.79 for the others), and the one with a nearly exclusive context (context-only
  AUC 0.956). So the confound adds most where the MIDI is most ambiguous.
- **Within-piece AUC** (only beginner-advanced pairs of the same piece; 138 pieces, 398 pairs;
  piece bootstrap): M mean 0.800 [0.740, 0.858], CC 0.922 [0.888, 0.953], CS 0.664, symbolic
  0.711, context label alone 0.915. delta_infl **+0.122 [+0.066, +0.182]**, delta_short +0.258
  [+0.213, +0.302]. When repertoire is held fixed, the inflation is larger, not smaller. The
  pooled +0.073 is conservative, because repertoire difficulty lifts the matched baseline towards
  the AUC ceiling. The Threats statement "the deltas are unaffected" is too strong (fix 3).

### Per-level claim ("teachers carry the inflation")

CC - M mean against all beginners, group bootstrap (1,000): piano_teacher **+0.180 [+0.145,
+0.215]**, virtuoso **+0.061 [+0.047, +0.079]**, child_professional **-0.022 [-0.041, -0.003]**.
Teachers carry most of it, but not all: virtuosos (all concert_hall, context-only AUC 1.000) add
a significant part. Child professionals lose slightly (fix 2).

### Required fixes (text only; the header is unchanged)

1. Verdict point 2 and the plain-terms summary: add that with near-perfectly decodable contexts
   the inflation is close to that of an explicit context label (stacked benchmark 0.959 / 0.705 vs
   CC 0.943 / 0.730). So +0.073 reflects the confound strength, not a MuQ-specific size. Claim
   direction and mechanism only.
2. Verdict point 4: "concentrated in teachers" becomes "largest for teachers (+0.180 [+0.145,
   +0.215]), also present for virtuosos (+0.061 [+0.047, +0.079]), slightly negative for child
   professionals (-0.022 [-0.041, -0.003])". Add the mechanism: clean demos (including slow
   demos) are nearly exclusive to teachers and have the most beginner-like MIDI.
3. Threats, "matched AUC is not a clean skill measure": replace "The deltas are unaffected" with
   the within-piece result: repertoire difficulty shares the deltas' MIDI signal and makes the
   pooled inflation conservative (within-piece +0.122 [+0.066, +0.182]).
4. Disclose the post-header lint rewrap of `build.py` and `reachability.py` (no behaviour change).

### Not verified

- The audio pipeline itself (renderer, `simulate_phone`, AAC) was not re-executed; the embeddings
  were taken as given. Context versions differ per clip (min L2 distance 2.73), so no copy is
  duplicated.
- Overlapping context ranges (the second threat) were not tested. That needs a re-render.
- Transfer to real YouTube audio (H8 proper) remains untested (OWNER decision on D-05).

## Post-audit corrections (lead, 2026-09-28)

1. **Claim direction and mechanism only.** When recording context is confounded with skill, a
   frozen-MuQ linear probe uses context about as much as it would use an explicit context label.
   The confounded result reaches about 80% of the stacked explicit-label ceiling: inflation +0.073
   of +0.089, shortcut +0.214 of +0.254. The +0.073 is not a measure of MuQ's own susceptibility,
   and it does not transfer to real audio. The simulated contexts are more separable than real
   ones.
2. **Per-level inflation** (confounded minus matched, vs beginners):
   - teachers +0.180 [0.145, 0.215];
   - virtuosos +0.061 [0.047, 0.079];
   - child professionals −0.022.

   The mechanism: teachers' slow demos (median 2.9 notes/s) coincide with the clean context.
3. **Repertoire:** within-piece AUC gives inflation +0.122 [+0.066, +0.182]. The pooled +0.073 is
   therefore conservative, not inflated by repertoire.
4. **Disclosure:** `build.py` and `reachability.py` were re-wrapped for lint after the header was
   hashed. Behaviour did not change.
