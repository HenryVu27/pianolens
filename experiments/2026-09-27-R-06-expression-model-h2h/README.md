# Frozen head-to-head: SyMuPe EncDec-base vs Pianist Transformer
Ticket: R-06    Hypothesis: model choice for R-07 / R-10; preview of H1b    Status: Provisional

Pre-registered 2026-09-27. Written after installing both models and one smoke test (disclosed
below), before any evaluation set was scored. Sections below "Results" were added afterwards.

## Question

Two score-conditioned expression models with released weights are shortlisted (DECISIONS.md,
2026-09-27): **SyMuPe EncDec-base** (25.1M parameters, CC BY-NC-SA 4.0 weights) and **Pianist
Transformer** `pianist-transformer-rendering` (135.7M, Apache-2.0). Frozen, on pieces neither saw
paired with a score in training:

1. How well does each predict per-note expression (velocity, timing, articulation) of real expert
   performances from the score alone?
2. How much of the across-performer mean expression curve does each predict (H1b preview)?
3. Does each model's likelihood of a performance separate real expert performances from the same
   performances with timing / velocity jitter, and from deadpan renditions?
4. What do they cost to run on this Mac and to fine-tune on a 16 GB RTX 5080?

## Disclosure: smoke test before this pre-registration

To check the adapters, both models scored one Vienna 4x22 performance (Chopin Op. 10/3, pianist
p01) and its 6 jittered and 1 deadpan versions, and each generated 8 samples of that excerpt.
Seen: for both models the teacher-forced log-probability was **higher for the deadpan** than for
the real performance, and fell monotonically with timing and velocity jitter. That observation is
why criterion (c2) below (a generation-based score) is added next to the likelihood (c1). Nothing
else was looked at. The item is part of set V and is not excluded.

## Falsified if / decision rules (fixed before results)

Primary set is **P** (unseen by both, below). A and V are secondary and do not decide.

- **(a) Per-note prediction.** For each real rendition: Pearson r between the model's predicted
  expression (mean of K = 8 samples) and the actual, for velocity (per note), log IOI ratio (per
  score onset) and log articulation (per note, notes of at least 1/16 quarter). Summary: mean
  over renditions per work, then the unweighted mean over the 3 works; 95% CI by cluster bootstrap
  over passages within works (2,000 resamples, seed 0). Composite = mean of the three targets.
- **Model choice (R-07 / R-10).** Recommend the model with the higher (a) composite on P if the
  paired bootstrap CI of the difference excludes 0. Otherwise recommend the higher mean (c1)
  jitter AUC (below) if its paired CI excludes 0. Otherwise recommend SyMuPe (smaller, cheaper to
  fine-tune, same tokenisation and alignment tooling as PianoCoRe). Either model must also beat
  the ridge baseline's (a) composite; if neither does, the recommendation is "neither frozen;
  fine-tune (R-07) and re-test".
- **(b) H1b preview, not the H1b verdict (R-10 owns that).** Per passage with at least 6 human
  renditions: the across-performer mean curve over score onsets (velocity, log IOI ratio;
  onsets observed in at least half the renditions). Statistic: centered R² of the model's
  predicted curve (mean of its K samples' curves) against the mean curve, no refit; also r². Median
  over passages per work. Reading, using the plan's H1b thresholds: at least 0.50 "consistent with
  H1b", at most 0.20 "at the H1b falsification level for a frozen model", otherwise
  inconclusive. Ceiling: split-half (performers) correlation of the mean curve, Spearman-Brown
  corrected to the full panel.
  - (b2, exploratory, added at the lead's request) Shared components: per passage with at least
    10 renditions, parallel analysis against an envelope-preserving surrogate (R-02 audit
    method) gives k shared components of the between-performer deviations; report the share of
    the expert variance in those k components that lies in the span of the model's sample
    deviations (K - 1 dimensions), against the share for a random subspace of the same size.
- **(c1) Likelihood discrimination.** Score = mean teacher-forced log-probability per matched note
  of the timing + velocity + duration fields (SyMuPe: TimeShift, Velocity, TimeDuration; Pianist
  Transformer: interval, velocity, duration); pedal fields reported separately. Paired AUC = share
  of real renditions scoring higher than their own perturbed version, per level (timing jitter
  s.d. 10 / 20 / 40 ms; velocity jitter s.d. 4 / 8 / 16), and than their synthetic deadpan. On P
  also against the PercePiano `Score` renditions of the same passage (all human x Score pairs).
  **Separates** if AUC is at least 0.75 and the CI lower bound is above 0.5; **fails** if the CI
  includes 0.5 or AUC is below 0.5.
- **(c2) Generation-based typicality.** Score = minus the mean squared z-distance between the
  rendition's per-note expression and the model's K-sample mean (per-note sample s.d., floored at
  the median s.d. of that target), averaged over the three targets. Same AUCs and reading as c1.
- **(d) Cost.** Wall time per note for scoring and for generation on this Mac (CPU and MPS),
  parameter count, and peak memory of one AdamW training step at each model's training context
  (MPS allocator figure, as a proxy for CUDA memory on the 5080), plus the arithmetic estimate.

## Data

Training-data overlap was checked per piece (details in "Overlap" below).

- **P (primary): PercePiano** (D-02, commit e672299) segments of Beethoven WoO 80 and Schubert
  D960 mv2 and mv3, human performers only (e-competition Disklavier MIDI). Pieces with no aligned
  pair in PERiScoPe v1.0 (SyMuPe's training set: WoO 80 and all four D960 movements appear only
  as raw, unaligned performances) and absent from (n)ASAP (Pianist Transformer's only supervised
  data). D935 no. 3 is excluded (in both). Alignment: `pianolens.align.align_performance`
  (parangonar DualDTW, F-01 default), not human-verified; segments whose matched share of score
  notes is below 0.8 are dropped. External deadpans: the PercePiano `Score` / `Score2` renditions
  of the same segments.
- **A (secondary): (n)ASAP** (D-01, commit 4097b45) performances of the 23 score folders in
  Pianist Transformer's shipped test set (`data/midis/testset/score/0..22.mid`, matched note for
  note to ASAP `midi_score.mid`), minus folders whose piece has another ASAP folder in its
  training split (Beethoven 32-1_no_repeat, Chopin Sonata 2/2nd, Schumann Kreisleriana 1) and
  folders with no robust ground-truth alignment; first 800 score notes. Unseen by Pianist
  Transformer's fine-tuning. All of (n)ASAP is in PERiScoPe; SyMuPe's 90/10 split is by
  composition but the split list is not published, so each piece is in SyMuPe's training set
  with probability about 0.9.
- **V (secondary): Vienna 4x22** (commit 1033ade), 22 pianists x 4 excerpts, sensor MIDI,
  ground-truth alignment. Chopin Op. 10/3, Op. 38 and Mozart K331 mv1 have aligned pairs in
  PERiScoPe; Schubert D783 no. 15 does not (only D783 no. 7 is there). Chopin Op. 10/3 and Op. 38
  are in Pianist Transformer's ASAP training split; K331 mv1 and D783 are not in ASAP. So D783
  no. 15 is unseen by both, K331 mv1 by Pianist Transformer only, the two Chopin excerpts by
  neither. V results are reported per excerpt with this status.
- Batik-plays-Mozart is not used: one performer per movement (no across-performer analysis) and
  all 36 movements are in PERiScoPe.
- Pretraining exposure that cannot be excluded: Pianist Transformer pretrained on 10B tokens of
  unpaired MIDI (Aria-MIDI transcriptions of YouTube, GiantMIDI, PDMX scores, ...), which very
  likely contains performances and scores of every piece here, possibly including transcriptions
  of the same e-competition recordings. This is exposure without the score pairing.

Per real rendition the items are: real; 6 jittered copies (`pianolens.data.perturb`, rate 0,
seeds recorded); a synthetic deadpan (`expression_io.deadpan`: score timing at the rendition's
global tempo, constant velocity at its median, 0.95 legato). Only matched notes are scored
(deletions, insertions and interpolated pairs dropped on both sides).

## Conditioning (both models, identical)

The score MIDI given to each model carries one tempo and one velocity for all notes: the
rendition's own global seconds-per-quarter (least-squares slope of chord onset on score onset)
and median velocity. Generation items use the medians over the passage's human renditions (a
one-number-per-passage use of test performances, disclosed). No dynamics or tempo markings.
Time signatures come from the score; bar lines start at tick 0 (pickups end an empty first bar).

## Splits

Frozen models, no training on test data. Baseline (ridge) trained on (n)ASAP performances of
pieces outside A, P and V (up to 3 robust-alignment performances per score folder). CIs cluster
by passage (P) or piece (A, V). Seeds: generation seed 0 for both models; jitter seeds
20260927 + 1000 x level + crc32(item) mod 997; bootstrap seed 0.

## Baselines

- (a), (b): **ridge on score features** (pitch, chord role and size, metrical phase, note and IOI
  durations, local density and register; Basis-Mixer-lite), predicting velocity minus the
  conditioning velocity, log IOI ratio and log articulation. For (a) also the **leave-one-out
  mean of the other performers** of the same passage (a typicality reference, not available for
  a new piece).
- (c): the same ridge as a Gaussian likelihood; and a **smoothness** rule (minus the mean squared
  first difference of velocity and log IOI ratio), which prefers deadpans and penalises jitter
  without any score knowledge.

## Method

- `prepare.py` (project env): items and manifest. `adapters/symupe_adapter.py` (envs/symupe-venv:
  symupe 1.1.0 at commit 13cc57d, torch 2.14, numba) and `adapters/pt_adapter.py` (envs/pt-venv:
  torch 2.7.1, transformers 4.54.0, repo commit 747df2d) score and generate.
- Teacher forcing: SyMuPe windows of 256 notes, hop 128 (SOS only on the first window, as in its
  training data); Pianist Transformer windows of 512 notes (4096 tokens, its maximum), hop 256.
  Each note is scored once, in the window where it has at least half a window of left context.
- Generation: each package's own sampler, top-p 0.95, temperature 1, K = 8, seed 0.
- `baseline.py`, `analyze.py` (project env) compute features with
  `pianolens.models.expression_io.note_expression` for every rendition and sample alike.

## Command

```
OMP_NUM_THREADS=1 uv run python experiments/2026-09-27-R-06-expression-model-h2h/prepare.py --sets P A V
E=experiments/2026-09-27-R-06-expression-model-h2h
$E/envs/symupe-venv/bin/python $E/adapters/symupe_adapter.py score    --items $E/artifacts/items/<S> --out $E/artifacts/symupe/score/<S>
$E/envs/symupe-venv/bin/python $E/adapters/symupe_adapter.py generate --items $E/artifacts/gen_items/<S> --out $E/artifacts/symupe/gen/<S> --k 8 --seed 0
$E/envs/pt-venv/bin/python $E/adapters/pt_adapter.py score    --device mps --items $E/artifacts/items/<S> --out $E/artifacts/pt/score/<S>
$E/envs/pt-venv/bin/python $E/adapters/pt_adapter.py generate --items $E/artifacts/gen_items/<S> --out $E/artifacts/pt/gen/<S> --k 8 --seed 0
uv run python $E/baseline.py
uv run python $E/analyze.py
```

## Run record

- Run 2026-09-28 (UTC) on the M4 Pro. Not a git repository: code hash (sha256 of the experiment
  `.py`/`.sh` files plus `src/pianolens/models/expression_io.py`) `a08c083f...0013c32`.
  Pre-registration: `head -n 160 README.md | shasum -a 256` = `d9ee9eac...8a43cfa` =
  `artifacts/prereg_sha256.txt` (copy in `artifacts/prereg_README.md`).
- Items: P 981 human renditions in 86 passages (1 dropped for matched share < 0.8), 103 external
  deadpans; A 80 renditions in 16 pieces (7 of the 23 folders excluded: 3 for piece overlap with
  PT training, 4 without robust alignment; `artifacts/A_overlap.csv`); V 88 renditions in 4
  excerpts. Each real rendition has 6 jittered copies and a deadpan (9,295 items scored per
  model).
- Baseline ridge: 375 ASAP performances of 156 pieces, 284,561 notes; leave-piece-out CV r
  inside the training set: velocity 0.41, log IOI 0.15, log articulation 0.30.
- Everything ran; no item failed in the final outputs.

### Deviations from the pre-registration (disclosed)

1. **SyMuPe note order.** For one P passage (WoO 80 var. 18) and two A pieces (Beethoven 5-1, 7-1)
   SyMuPe's grid quantisation reorders a few notes (3 in var. 18). The adapter first raised an
   error; it now maps tokens to notes through the tokenizer's own `token_to_note` permutation
   (round-trip self-test exact, onset error < 0.001 ms). ~~Mechanical fix, done before any result
   was looked at.~~ *[Corrected post-audit, 2026-09-28]* The generation-side part of this fix
   (02:57 UTC) came after a partial trial `analyze.py` run (02:44) had printed some summary
   numbers. Mechanical, no outcome-dependent choice: var. 18 raised an error before. The onset
   error < 0.001 ms held for the items tested then; in general it is up to 0.51 ms (tick
   quantisation, 1 tick = 1.04 ms; see Audit).
2. **Bootstrap for A and V.** In these sets a "work" is one piece, so the within-work cluster
   resampling of the pre-registered procedure is degenerate. CIs for A and V resample pieces
   instead. ~~(fixed after the first trial run printed zero-width CIs, before reading effects)~~
   *[Corrected post-audit, 2026-09-28]* Changed at 02:51 UTC, after a partial trial run (02:44)
   had printed some summary numbers, including zero-width CIs. Mechanical, no outcome-dependent
   choice: zero-width CIs are degenerate.
3. **Ridge alpha grid** widened to 1e4 / 1e5 after the first fit hit the upper edge (training
   data only).
4. **SyMuPe cost on MPS** cannot be measured: symupe 1.1.0 moves a float64 tensor to MPS in
   `prepare_sequence` and crashes. Its training-step cost is measured on CPU (process RSS).
5. **Runtime logs** of the first passes were overwritten by the gap-filling reruns; the per-note
   runtimes below come from the pre-registration smoke test on an idle machine (V, Op. 10/3,
   451 notes) plus the medians of the surviving logs (4 jobs in parallel).

## Results

All r are Pearson correlations, mean over renditions per work, then the unweighted mean over
works; 95% CI by cluster bootstrap (2,000 resamples).

### (a) Per-note prediction from the score (frozen, K = 8 samples averaged)

**P (primary; unseen by both):**

| Predictor | velocity | log IOI | log articulation | composite |
|---|---|---|---|---|
| ridge (baseline) | 0.427 [0.384, 0.469] | 0.050 [0.014, 0.085] | 0.022 [-0.028, 0.073] | 0.166 [0.139, 0.193] |
| **SyMuPe EncDec** | 0.512 [0.464, 0.557] | 0.333 [0.291, 0.373] | 0.319 [0.270, 0.369] | **0.388 [0.359, 0.416]** |
| **Pianist Transformer** | 0.533 [0.496, 0.570] | 0.274 [0.221, 0.327] | 0.372 [0.318, 0.423] | **0.393 [0.365, 0.421]** |
| other performers, LOO mean (reference) | 0.755 [0.733, 0.774] | 0.651 [0.615, 0.685] | 0.753 [0.725, 0.777] | 0.720 [0.700, 0.738] |

Paired composite difference SyMuPe minus PT: **-0.005 [-0.025, 0.016]** (per work: WoO 80
-0.005, D960 mv2 +0.028, D960 mv3 -0.038). Both beat the ridge: +0.222 [0.198, 0.247] and
+0.227 [0.202, 0.255]; per work every model-minus-ridge difference is positive (0.11 to 0.30).
Per work composite, SyMuPe / PT: WoO 80 0.428 / 0.432, D960 mv2 0.416 / 0.389, D960 mv3
0.320 / 0.358. SyMuPe is better on timing (log IOI), PT on articulation and slightly on velocity.

*[Added post-audit, 2026-09-28; auditor's figures, 1,000 passage-cluster resamples, seed 0]*
The composite tie hides significant differences. Paired SyMuPe minus PT:

| Split | SyMuPe - PT |
|---|---|
| WoO 80 (composite) | -0.005 [-0.053, 0.039] |
| D960 mv2 (composite) | +0.028 [-0.003, 0.055] |
| **D960 mv3 (composite)** | **-0.038 [-0.069, -0.007]** (PT better) |
| velocity | -0.021 [-0.050, 0.007] |
| **log IOI** | **+0.059 [0.017, 0.101]** (SyMuPe better) |
| **log articulation** | **-0.053 [-0.094, -0.015]** (PT better) |

With a performer-cluster bootstrap the composite difference is -0.005 [-0.012, 0.002], so step 1
of the rule (no separation) holds under either unit.

**Secondary sets (composite; paired SyMuPe minus PT):**

| Set | ridge | SyMuPe | PT | LOO others | SyMuPe - PT |
|---|---|---|---|---|---|
| A (16 pieces, PT-unseen, ~0.9 chance SyMuPe-seen) | 0.240 [0.202, 0.281] | 0.581 [0.520, 0.635] | 0.425 [0.342, 0.493] | 0.699 [0.637, 0.751] | +0.156 [0.092, 0.227] |
| V (4 excerpts) | 0.320 [0.278, 0.357] | 0.657 [0.614, 0.701] | 0.555 [0.528, 0.581] | 0.822 [0.806, 0.842] | +0.102 [0.042, 0.162] |

V per excerpt (SyMuPe / PT; training status): Chopin Op. 10/3 0.705 / 0.560 (seen by both),
Op. 38 0.696 / 0.517 (seen by both), Mozart K331 mv1 0.626 / 0.554 (SyMuPe-seen, PT-unseen),
**Schubert D783 no. 15 0.601 / 0.591 (unseen by both)**. SyMuPe's large lead on A and V shrinks to
nothing where neither model saw the piece (P and D783). The lead on A and V is at least partly
training-set exposure (memorisation of seen pieces), so it does not count for the choice.

### (b) H1b preview: across-performer mean curve

Per passage with at least 6 human renditions (P: 81 passages, median 12 performers). Median
over passages of the centered R² (no refit) and of r²; reliability = Spearman-Brown corrected
split-half correlation of the mean curve (its ceiling).

| Set / target | ridge R²c / r² | SyMuPe R²c / r² | PT R²c / r² | reliability |
|---|---|---|---|---|
| P velocity | 0.090 / 0.200 | 0.096 / 0.369 | 0.302 / 0.354 | 0.929 |
| P log IOI | -0.049 / 0.031 | -0.054 / 0.208 | -0.039 / 0.146 | 0.931 |
| A velocity (5 pieces) | 0.130 / 0.130 | 0.755 / 0.756 | 0.477 / 0.482 | 0.956 |
| A log IOI | -0.055 / 0.030 | 0.528 / 0.552 | -0.142 / 0.090 | 0.934 |
| V velocity (4) | 0.150 / 0.211 | 0.545 / 0.570 | 0.413 / 0.510 | 0.979 |
| V log IOI | -0.002 / 0.050 | 0.610 / 0.650 | 0.344 / 0.416 | 0.988 |

On P (unseen) the frozen models explain at most about 30% of the mean velocity curve without
refit (PT) and nothing of the mean timing curve (negative centered R²: right shape in part,
r² 0.15-0.21, but wrong amplitude). The mean curve itself is reliable (0.93), so this is the
models' limit, not noise. V D783 (unseen by both): SyMuPe 0.399 / 0.530 and PT 0.355 / 0.240
centered R² for velocity / timing.

**(b2, exploratory) shared components.** P: parallel analysis against the envelope null finds
k = 0 shared components in 40 of 81 passages (k = 1: 24, 2: 12, 3: 5; median share of
between-performer variance in them 0.20). With 12 performers this has little power. Where k > 0,
the span of the model's 7 sample-deviation directions holds a median 0.17 (SyMuPe) and 0.20 (PT)
of the expert shared-component variance, against 0.07 for a random 7-dimensional subspace; above
the random 95th percentile in 68% (SyMuPe) and 78% (PT) of passages. V (22 performers): k = 0, 2,
3, 5; captured 0.12 / 0.10 vs 0.02 random. So the models' sample variation points partly along the
experts' shared interpretive axes, but covers a small part of them. The proper analysis with 50+
performers per piece belongs to R-10.

### (c) Does the score separate real from perturbed and deadpan renditions? Paired AUC

P (primary). "core" = teacher-forced log-probability of timing + velocity + duration;
"gen" = generation-based typicality (c2).

| Score | T 10 ms | T 20 | T 40 | V 4 | V 8 | V 16 | synthetic deadpan | PercePiano Score renditions |
|---|---|---|---|---|---|---|---|---|
| SyMuPe core (c1) | 0.984 | 1.000 | 1.000 | 0.998 | 1.000 | 1.000 | **0.000** | **0.000** |
| PT core (c1) | 0.946 | 0.996 | 1.000 | 0.995 | 1.000 | 1.000 | **0.000** | **0.000** |
| SyMuPe gen (c2) | 0.790 | 0.906 | 0.959 | 0.870 | 0.977 | 0.999 | 0.313 [0.229, 0.389] | 0.649 [0.562, 0.728] |
| PT gen (c2) | 0.803 | 0.909 | 0.954 | 0.929 | 0.995 | 1.000 | 0.365 [0.276, 0.455] | 0.663 [0.576, 0.743] |
| ridge Gaussian (baseline) | 0.789 | 0.880 | 0.959 | 0.946 | 0.996 | 1.000 | 0.005 | 0.257 |
| smoothness (baseline) | 0.784 | 0.894 | 0.958 | 0.907 | 0.977 | 0.999 | 0.000 | 0.122 |

CIs for the jitter cells are all within ±0.05 of the point and above 0.5. The mean jitter AUC
paired difference SyMuPe minus PT: core +0.008 [0.004, 0.011]; gen -0.015 [-0.022, -0.008]. A and
V give the same pattern (core jitter AUC 0.99-1.00, deadpan 0.00; gen deadpan 0.49-0.76 with CIs
spanning 0.5).

- **(c1) jitter: separates**, for both models, at every level (AUC ≥ 0.94, CI lower bound at least
  0.92), better than the two baselines (0.78-0.96). Per field, timing jitter is caught by the
  timing field and velocity jitter by the velocity field, as expected.
- **(c1) deadpan: fails, emphatically.** Both models give every deadpan (synthetic and
  PercePiano's) a *higher* likelihood than the real expert performance (AUC 0.00). The
  teacher-forced likelihood rewards predictability: once the model has seen a few flat notes it
  predicts flat notes. The same happens to the smoothness and ridge baselines.
- **(c2) generation-based typicality: separates jitter** (0.79-1.00), about as well as the
  baselines. ~~and is **inconclusive against deadpans** (0.31-0.66, CIs straddle 0.5 or stay below
  0.75).~~ *[Corrected post-audit, 2026-09-28]* Against the synthetic deadpan on P it **fails**:
  AUC 0.313 [0.229, 0.389] (SyMuPe) and 0.365 [0.276, 0.455] (PT), with the whole CI below 0.5,
  so it prefers the deadpan, significantly. It is inconclusive only against PercePiano's Score
  renditions (0.65-0.66, CI above 0.5 but AUC below 0.75) and on A / V (CIs span 0.5).

### (d) Cost

| | SyMuPe EncDec-base | Pianist Transformer |
|---|---|---|
| Parameters | 25.1M | 135.7M |
| Teacher-forced scoring, 451 notes (idle machine) | 0.09 s CPU (0.2 ms/note); MPS unusable (float64 crash) | 0.37 s CPU, 0.13 s MPS (0.3 ms/note; MPS vs CPU max diff 3e-5 nats) |
| Generation, 8 samples x 454 notes (idle) | 16.6 s CPU (37 ms/note) | 96 s CPU (212 ms/note); 204 s on MPS (slower) |
| Median under 4 parallel jobs | score 0.38 ms/note, generate 80 ms/note | score 0.59 ms/note, generate 168 ms/note |
| One AdamW step, fp32, authors' context | 256 notes: batch 8 0.9 s / 2.4 GB, batch 32 2.7 s / 6.5 GB, batch 128 (paper) 10.9 s / 23 GB (CPU process RSS) | 4096 tokens: batch 1 1.6 s / 8.9 GB, batch 2 1.6 s / 15.4 GB, batch 4 (authors' per-GPU) 2.1 s / 27.3 GB (MPS driver) |
| 16 GB RTX 5080 estimate | Weights + grads + Adam = 0.4 GB. Paper batch 128 needs bf16 or 2 x 64 accumulation; batch 32-64 fp32 fits | Weights + grads + Adam = 2.2 GB. Batch 1 fp32 fits; batch 2 is at the limit in fp32 and should fit in bf16; the authors' batch 4 needs bf16 + gradient checkpointing or accumulation |

The 5080 figures are extrapolated from MPS / CPU memory, not measured on CUDA. Both are
feasible; SyMuPe is about 5x smaller and ~~about 5x~~ *[corrected post-audit, 2026-09-28]*
5.7x faster to sample on an idle machine (37 vs 212 ms/note) and 2.1x under 4 parallel jobs
(80 vs 168 ms/note).

## Verdict (Provisional; audited 2026-09-28: Confirmed with caveats, see Audit)

- **Model choice (pre-registered rule): SyMuPe EncDec-base for R-07 / R-10.** Step 1: the (a)
  composite on P does not separate them (SyMuPe minus PT -0.005 [-0.025, 0.016]). Step 2: the
  mean (c1) jitter AUC does, narrowly, in SyMuPe's favour (+0.008 [0.004, 0.011]); this decides.
  *[Added post-audit, 2026-09-28]* Robust to the bootstrap unit: +0.0075 [0.0038, 0.0113] by
  passage, [0.0050, 0.0099] by performer, **[0.0027, 0.0129] resampling both** (the honest figure,
  since D960 passages overlap and the same performers play every passage of a work). It is carried
  by the 10 ms timing level (+0.037); only 6% of renditions differ between the models at all.
  The margin is tiny and the (c2) version of the same difference favours PT (-0.015
  [-0.022, -0.008]), so read it as a tie on quality broken toward the cheaper model; the step-3
  default (SyMuPe) would have chosen the same. Both beat the ridge baseline by a wide margin
  (composite +0.22).
- Where each is better, on unseen pieces: SyMuPe on timing (log IOI r 0.33 vs 0.27), PT on
  articulation (0.37 vs 0.32) and the mean velocity curve. *[Added post-audit]* Paired: log IOI
  +0.059 [0.017, 0.101] for SyMuPe, articulation +0.053 [0.015, 0.094] for PT, and D960 mv3
  composite +0.038 [0.007, 0.069] for PT (see (a)).
- ~~**H1b preview: at the falsification level for frozen models.**~~ *[Corrected post-audit,
  2026-09-28: split by target and model, per the pre-registered thresholds (R²c at least 0.50
  consistent, at most 0.20 falsification level, else inconclusive)]* **H1b preview on unseen
  pieces (P), frozen, centered R² without refit:**
  - timing (log IOI): **at the falsification level for both** (-0.054 SyMuPe, -0.039 PT);
  - velocity: **at the falsification level for SyMuPe** (0.096, no better than the ridge at
    0.090); **inconclusive for PT** (0.302).
  - The velocity shape is partly right: r² 0.37 (SyMuPe) / 0.35 (PT) against 0.20 for the ridge.
    The low R²c comes from the amplitude. Curve reliability is 0.93.

  This is not the H1b verdict: R-10 must test a fine-tuned model (R-07) and the shared-component
  version with 50+ performers.
- **Likelihood as a quality score: fails the deadpan test.** The teacher-forced likelihood of
  either model detects added noise (AUC ≥ 0.94) but ranks deadpans above every expert. It cannot
  be used on its own as a typicality or quality score. The generation-based typicality is no
  better than a smoothness rule on jitter and ~~is inconclusive on deadpans~~ *[corrected
  post-audit]* **fails** against the synthetic deadpan on P (AUC 0.31 / 0.37, CI wholly below
  0.5); it is inconclusive only against PercePiano Score renditions and on A / V. Any use in tier D
  needs a correction for predictability (for example a likelihood ratio against a model of flat
  playing, or scoring the expressive deviation only), to be designed in R-07 / R-10.

## Threats to validity

- **Training exposure.** P pieces have no aligned pair in PERiScoPe v1.0 and are not in ASAP, but
  Pianist Transformer's pretraining corpus (Aria-MIDI transcriptions of YouTube and others) very
  likely contains performances of them, possibly transcriptions of the same e-competition
  recordings; SyMuPe's raw (unaligned) PERiScoPe has 54 D960 and 5 WoO 80 performances, not used
  for training by its own description. A and most of V are seen by SyMuPe; A's large SyMuPe lead
  is therefore not evidence of better generalisation.
- **P alignment is automatic** (parangonar), not human-verified; noisy matches lower all
  correlations equally. A and V use ground-truth alignments and agree in direction.
- **Conditioning uses test information**: each rendition's global tempo and median velocity (for
  likelihoods), and the passage medians (for generation). This removes global tempo and loudness
  from all comparisons by design; it is not available unchanged for a new piece without a
  performance.
- **Short segments.** P segments are 4-16 bars (median 93 notes). Phrase-level shaping and the
  models' longer context are under-used; long-range results come only from A and V (seen pieces).
- **K = 8 samples** makes the predicted mean noisy; the r values are lower bounds for the models'
  expected rendering.
- **Deadpan conditioning.** Deadpans get their own global tempo and a velocity equal to the
  conditioning velocity, which makes them maximally predictable; a louder or softer deadpan may
  score differently. The PercePiano Score renditions (not constructed by us) behave the same
  way under (c1).
- **Seed and small-n effects** in (b2): 12 performers per passage give low parallel-analysis power.
- The 5080 memory figures are extrapolations from Apple MPS / CPU, not CUDA measurements.

## Audit (2026-09-28, eval-auditor)

**Verdict: Confirmed with caveats.** The model choice (SyMuPe) follows the pre-registered rule and
every number reruns exactly. Two readings in the Results / Verdict text do not follow the
pre-registered thresholds and must be corrected (items 1 and 2). The deadpan finding is stronger
than stated (item 5).

### What I checked and reran

- **Pre-registration.** `head -n 160 README.md | shasum -a 256` = `d9ee9eac...8a43cfa` =
  `artifacts/prereg_sha256.txt`. Transcript timeline (ml-researcher, UTC): README written
  02:27:17 and hashed 02:27:32; P and A prepared from 02:27:48; the tie-break code in `analyze.py`
  added 02:33:47; P scoring after that. The smoke test (V, Op. 10/3 p01, 02:17-02:22) and the
  added c2 are disclosed accurately.
- **Reproduction.** Full `analyze.py` rerun to scratch: all four CSVs and `summary.json`
  byte-identical. I re-scored the real item of 86 P renditions (one per passage) with both
  adapters: SyMuPe per-item core log-prob max |diff| 1.3e-6, PT 0.0 against the artifacts.
- **Training overlap (P unseen by both).** Verified. PERiScoPe v1.0 metadata (the version named
  on the EncDec-base model card): D960 has 216 performances (mv1-4: 49 / 54 / 54 / 59) and WoO 80
  has 5, all with an empty `score` field (no aligned pair). These are ATEPP-style commercial
  recording transcriptions, so the works are in PERiScoPe, just not paired with a score. (n)ASAP
  has no D960 and no WoO 80 folder (242 folders checked). V D783 no. 15: only D783 no. 7 has a
  score in PERiScoPe; not in ASAP. Not verifiable: whether SyMuPe used unpaired performances in any
  way (the paper and card describe pair training only), and Pianist Transformer's Aria-MIDI
  pretraining exposure (disclosed).
- **Adapters.** SyMuPe's encoder does not see the target: `mask_token_dims = {'performance':
  [4, 5, 6, 7]}` masks Velocity, TimeShift, TimeDuration and TimeDurationSustain in `init_seq`
  (checked on a P item). Window-to-note mapping is correct for windows with and without SOS; each
  note is scored once (overlapping tail windows overwrite, never average). PT's labels follow the
  authors' shift-right T5 convention (`labels` -> `_shift_right`), so logits[t] and labels[t]
  line up. Round trips on 86 P items: SyMuPe onset MAE up to 0.51 ms (1 tick = 1.04 ms, so this is
  tick quantisation; the "< 0.001 ms" in Deviation 1 holds for the items tested then, not in
  general), velocity exact, up to 3 notes permuted. PT onset MAE up to 0.28 ms, velocity exact.
  Its duration differs by 29-267 ms (mean per note) on 11 of 86 items, all D960 mv2 (repeated
  notes): the authors' rule that cuts a note at the next onset of the same pitch. This is by design
  and applies equally to real and perturbed items.
- **Pairing and units.** `performance_id` is unique within each set; every real item has exactly
  one item of each alternative kind; ties count 0.5. "Other performers" is a true leave-one-out
  mean over the other human renditions of the passage (no performer repeats within a passage). It
  is correctly labelled a reference, not a ceiling.
- **Deadpans.** Synthetic deadpans use the same matched notes and the same conditioning as their
  real rendition. PercePiano `Score` renditions have exact score timing (log IOI s.d. 0.000
  median) but some velocity variation (s.d. 6.7 vs 13.2 for humans).

### Findings

1. **(c2) against the synthetic deadpan on P is a "fail", not "inconclusive".** AUC 0.313
   [0.229, 0.389] (SyMuPe) and 0.365 [0.276, 0.455] (PT). The pre-registered rule says "fails if
   the CI includes 0.5 or AUC is below 0.5", and here the whole CI is below 0.5: the
   generation-based score also prefers the synthetic deadpan, significantly. It is inconclusive only
   against the PercePiano Score renditions (0.65-0.66; CI above 0.5 but AUC below 0.75) and on A / V
   (CIs span 0.5). The same mechanism is at work: a distance to the model's sample mean rewards
   anything close to the smoothed mean.
2. **(b) reading.** By the pre-registered thresholds (at least 0.50 consistent, at most 0.20
   falsification level, else inconclusive), P centered R² gives: timing at the falsification level
   for both models (-0.05 / -0.04). For velocity, SyMuPe is at the falsification level (0.096, no
   better than the ridge at 0.090). PT's 0.302 is **inconclusive**, not at the falsification level.
   The blanket Verdict bullet "at the falsification level for frozen models" should be split this
   way. Also report that the velocity shape is partly right: r² 0.37 / 0.35 against ridge 0.20.
   The low R²c comes from the amplitude.
3. **The composite tie hides significant differences** (per-work and per-target paired CIs, 1,000
   passage-cluster resamples, seed 0). By work: WoO 80 -0.005 [-0.053, 0.039], D960 mv2 +0.028
   [-0.003, 0.055], **D960 mv3 -0.038 [-0.069, -0.007] (PT better)**. By target: **log IOI
   SyMuPe +0.059 [0.017, 0.101], log articulation PT +0.053 [0.015, 0.094]**, velocity PT
   +0.021 [-0.007, 0.050]. Add these to the (a) section (R-01..R-04 lesson: per-group deltas).
4. **Tie-break.** It is exactly as pre-registered and correctly implemented: per rendition, the
   mean of the six paired jitter indicators, then the SyMuPe minus PT difference, then a cluster
   bootstrap. It is robust to the bootstrap unit: +0.0075, CI [0.0038, 0.0113] by passage,
   [0.0050, 0.0099] by performer, [0.0027, 0.0129] with both resampled. PercePiano passages
   overlap (D960 has 8- and 16-bar segmentations of the same music) and the same 12 performers
   play every passage of a work, so the two-way figure is the honest one. But the difference comes
   almost entirely from the 10 ms timing level (+0.037). The 20 ms level gives +0.004, velocity
   4 gives +0.003, and the other three give 0. Only 6% of renditions differ between the models at
   all. It is a procedural decision between near-ceiling AUCs, not evidence that SyMuPe is better.
   The step-3 default gives the same answer. Step 1 is also robust: with a performer-cluster
   bootstrap, the composite difference is -0.005 [-0.012, 0.002], so it still includes 0.
5. **Deadpan AUC 0.00 is not an artifact of conditioning or velocity scale.** I re-scored 86 P
   renditions (one per passage) against modified deadpans. The deadpan still wins against every
   real rendition (AUC 0.00, both models) when its velocity is the conditioning velocity ±12 and
   when it is played 15% slower than the conditioning tempo. It also wins field by field: the
   timing, velocity, duration and pedal fields separately give AUC 0.00-0.08 on P. A deadpan with
   random noise (10 ms timing s.d., 4 velocity s.d.) still beats the human in 91-92% of
   renditions (AUC 0.08 SyMuPe, 0.09 PT). Human velocities on deadpan timing, or human timing with
   constant velocity, also beat the real rendition (AUC 0.00-0.01). So any flattening of either
   dimension raises the likelihood. This is the general mode-versus-typical-set property of a
   per-note likelihood, which the ridge Gaussian and smoothness baselines share. It is not a
   quirk of these models or of the adapters. Scratch scripts: `make_dp.py`, `dp_auc.py` (not in
   the repo).
6. **Disclosure accuracy (minor).** Deviations 1 and 2 were not made "before any result was looked
   at". The generation-side permutation fix (02:57) and the A/V bootstrap change (02:51) came after
   a trial `analyze.py` run on partial outputs (02:44) that printed the last 40 lines of the
   summary, including one P per-work composite and the A LOO values. Both are mechanical fixes
   with no outcome-dependent choice (var18 raised an error before; zero-width CIs are degenerate),
   so this changes nothing but the wording.
7. **Ridge baseline is fair but weak.** It is trained on (n)ASAP only. Within a rendition its P r
   is 0.05 for log IOI and 0.02 for articulation. Its in-training CV r (0.41 / 0.15 / 0.30) is
   pooled across pieces, so it is not comparable with the per-rendition r and should not be read
   as a domain-shift drop. "Far above ridge" is true, but the leave-one-out other-performers mean
   (0.720) is the informative reference.
8. **Smaller points.** The (b) predicted curve averages only K = 8 samples, which adds noise
   variance and penalises R²c. This is disclosed as a lower bound. Cost: DECISIONS.md says "6x
   faster generation", but the README measures 5.7x on an idle machine and 2.1x under 4 parallel
   jobs.

### Required text fixes (no rerun needed)

- Results (c2) bullet and Verdict: c2 **fails** against the synthetic deadpan on P (AUC below 0.5,
  CI below 0.5); it is inconclusive only against PercePiano Score renditions and on A / V.
- Verdict H1b bullet: timing at the falsification level for both; velocity at the falsification
  level for SyMuPe (and ridge-level), inconclusive for PT (0.30); report r² 0.35-0.37.
- (a): add the per-work and per-target paired CIs from finding 3.
- Deviations 1 and 2: replace "before any result was looked at" with "after a partial trial run
  had printed some summary numbers; mechanical, no outcome-dependent choice".

### For the lead

- The pre-registered rule selects SyMuPe, and the selection is valid. The lead's current decision
  ("keep both") departs from the rule. That is legitimate only on grounds outside it (Apache-2.0
  licence, PT's better articulation and mean velocity curve, PT better on D960 mv3), and it should
  be recorded as such in DECISIONS.md.
- Tier D implication (strengthened): a per-note likelihood rewards flattening of any dimension.
  The F-06 "too flat" flag and the deadpan known-answer test are necessary, not optional. A
  likelihood ratio against a flat model, or scoring the deviation only, must itself be tested
  against these deadpan variants (e.g. noisy deadpan, half-deadpan).

## Post-audit corrections (2026-09-28)

By `ml-researcher`, applying the auditor's "Required text fixes". Text only: no number was
recomputed here; the new figures are the auditor's (Audit, findings 1-4 and 8). The pre-registered
header (first 160 lines) is unchanged (sha256 re-verified: `d9ee9eac...8a43cfa`). In-place edits
above are marked *[Corrected post-audit]* or *[Added post-audit]*; replaced wording is struck
through.

1. **c2 against the synthetic deadpan on P is a fail** (finding 1). Corrected in the (c2) bullet
   and the likelihood Verdict bullet: AUC 0.313 [0.229, 0.389] (SyMuPe) and 0.365 [0.276, 0.455]
   (PT), CI wholly below 0.5. The pre-registered rule reads "fails if the CI includes 0.5 or AUC
   is below 0.5". Inconclusive only against PercePiano Score renditions and on A / V.
2. **H1b Verdict bullet split** (finding 2). Timing at the falsification level for both models;
   velocity at the falsification level for SyMuPe (ridge-level), inconclusive for PT (0.30);
   velocity r² 0.35-0.37 vs ridge 0.20, so shape is partly right and amplitude is off.
3. **Per-work and per-target paired CIs added to (a)** (finding 3): D960 mv3 composite PT better
   (-0.038 [-0.069, -0.007] SyMuPe minus PT), log IOI SyMuPe better (+0.059 [0.017, 0.101]),
   log articulation PT better (-0.053 [-0.094, -0.015]). Composite step 1 still holds with a
   performer-cluster bootstrap (-0.005 [-0.012, 0.002]).
4. **Tie-break bootstrap units added to the Verdict** (finding 4): +0.0075, two-way (passages and
   performers) CI [0.0027, 0.0129]. The choice of SyMuPe is unchanged; it is procedural, carried by
   the 10 ms timing level, and not a quality difference.
5. **Deviations 1 and 2 reworded** (finding 6). Both fixes came after a partial trial `analyze.py`
   run at 02:44 UTC had printed some summary numbers (one P per-work composite and the A LOO
   values): the A/V bootstrap change at 02:51, the generation-side permutation fix at 02:57. Both
   were forced by the failure they fixed (an error on var. 18; degenerate zero-width CIs), not
   chosen on outcomes. Deviation 1's "< 0.001 ms" is qualified (up to 0.51 ms in general).
6. **Speed figure** (finding 8). SyMuPe generation is 5.7x faster than PT on an idle machine and
   2.1x under 4 parallel jobs, not "about 5x" (README) or "6x" (earlier DECISIONS wording, already
   corrected by the lead).
