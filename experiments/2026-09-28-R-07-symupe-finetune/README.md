# Fine-tuned SyMuPe EncDec-base on piece-disjoint PianoCoRe, with a corrected typicality score
Ticket: R-07    Hypothesis: Phase 5 (expression model); H1b preview    Status: Provisional (pre-registered; job prepared, not run)

Pre-registered 2026-09-28, before any training on real data. The run waits for O-03 (Henry's RTX
5080 box). Everything below "Run record" is added later. The split is fixed and committed in
`split/pieces.csv` (sha256 `3341bfa5...86`, `split/summary.json`).

What had been seen before this was written: all R-06 results (they motivate the design), the
split counts in `split/summary.json`, and a pipeline dry run on the Mac (6 training pieces, 3
performances each, 2 to 6 optimizer steps; see "Dry run"). The dry run's losses and scores are
pipeline checks on toy data. They are not results and nothing below was chosen from them.

## Question

1. Does fine-tuning SyMuPe EncDec-base on PianoCoRe tier A (+ (n)ASAP), with whole works held out,
   predict per-note expression of unseen pieces better than the frozen model did in R-06?
2. H1b preview: how much of the *shared* expert variation (R-02 audit method) does the fine-tuned
   model's sample variation span on pieces unseen by pretraining and fine-tuning?
3. Can a corrected typicality score (likelihood ratio against a flat-playing model; typical-set
   distance; deviation-only agreement) prefer real expert performances to every deadpan variant
   of the R-06 audit? Only a score that passes may be used anywhere (DECISIONS 2026-09-28).
4. Secondary arm (pre-registered, DECISIONS 2026-09-28): the same fine-tune for Pianist
   Transformer, for questions 1 and 2.
5. What does it cost on the 16 GB RTX 5080, and on a rented GPU if it does not fit?

## Falsified if / decision rules (fixed before results)

Primary set is **P** (PercePiano WoO 80, D960 mv2, D960 mv3 segments; 981 human renditions in
86 passages; unseen by SyMuPe pretraining, and held out here). Everything else is secondary.

**(a) Per-note prediction (question 1).** Metric exactly as R-06 (a): per rendition, Pearson r
between the rendition's per-note expression and the mean of K = 8 model samples (velocity; log IOI
ratio per score onset; log articulation), composite = mean of the three; summary = mean over
renditions per work, then the unweighted mean over works.
- Statistic: paired per-rendition difference fine-tuned (E) minus frozen, composite.
- 95% CI: two-way cluster bootstrap resampling passages and performers together (2,000
  resamples, seed 0; R-06 audit lesson). With 3 works, also a t-interval over the per-work means
  (R-08a audit lesson). The reading uses the bootstrap CI.
- Reading: **improves** if the whole CI is above 0; **harms** if the whole CI is below 0;
  otherwise **no detectable change**. Always reported with per-work and per-target paired tables.
- Reproduction gate: the frozen model is re-run through this pipeline (same items, K = 8, seed 0).
  Its P composite must be within 0.01 of R-06's 0.388. If it is not, that is the first finding and
  the comparison uses the re-run frozen numbers, with R-06's shown alongside.
- Secondary sets, same statistic, not deciding: R10u (unseen by pretraining and by fine-tuning;
  transcribed MIDI; the headline for generalisation to new repertoire), R10s (held out here but seen
  in pretraining), V (Vienna 4x22), A ((n)ASAP, PT test folders).
- Minimum for use downstream (R-10, tier D): E is used instead of the frozen model only if (a) on P
  is "improves" or "no detectable change" **and** the validation loss at the best checkpoint is
  below the frozen model's validation loss (step 0). Otherwise R-10 uses the frozen model.

**(b) H1b preview (question 2), not the H1b verdict (R-10 owns that).** On R10u pieces with at
least 20 renditions (cap 50), first 3,000 score notes, majority score:
- Curves: per rendition and score onset, velocity (centered per rendition) and log IOI ratio;
  onsets observed in at least half of the renditions.
- Shared components: parallel analysis of the between-performer deviations (velocity and log IOI
  blocks each scaled to unit s.d.) against an envelope-preserving surrogate (phase-randomised rows,
  columns rescaled to the real s.d.; 100 surrogates, 95th percentile, seed 0). k = number of
  leading eigenvalues above the null.
- Statistic: share of the expert variance in those k components that lies in the span of the
  model's K = 16 sample deviations (15 dimensions); median over pieces with k > 0. Reported
  against a random 15-dimensional subspace (mean and 95th percentile, 200 draws). Also the
  mean-curve centered R² (R-06 (b)) and the split-half reliability (Spearman-Brown).
- Reading, with the plan's H1b thresholds: median captured share at least 0.50 "consistent with
  H1b"; at most 0.20 "at the H1b falsification level"; otherwise inconclusive. Same thresholds for
  the mean-curve R²c, per target.
- The R10u pieces that R-10 may call "unseen" are the 76 with no score-paired performance in
  PERiScoPe v1.0 (`n_periscope_paired == 0` and `r02` in `split/pieces.csv`); 3 more R-02 pieces
  in R10u are work-mates that are paired in PERiScoPe and are reported separately.

**(c) Corrected typicality (question 3).** Four scores per rendition x, all computed with the
fine-tuned model E unless stated. Core log-probability ℓ(x) = mean over matched notes of the
teacher-forced log-probabilities of TimeShift + Velocity + TimeDuration (R-06 c1 "core").
- **S-RAW** = ℓ_E(x). Reference only: R-06 showed it prefers deadpans (AUC 0.00).
- **S-LR** (likelihood ratio against a flat-playing model) = ℓ_E(x) − ℓ_F(x). F is SyMuPe
  EncDec-base fine-tuned with the same recipe (5,000 steps max) on one random flat rendition per
  training item (`pianolens.models.expression_data.flat_training_rendition`): score timing at the
  item's own conditioning tempo, velocity equal to the conditioning velocity, durations U(0.85,
  1.0) x nominal, onset noise s.d. U(0, 10 ms), velocity noise s.d. U(0, 4), no pedal. F's family is deliberately narrower than the
  test battery: it never sees a velocity offset, a tempo change or noise above 10 ms / 4, so those
  variants test generalisation, not memorisation.
- **S-TYP** (typical-set distance; the mode-versus-typical-set correction). For each field
  f in {TimeShift, Velocity, TimeDuration}: z_f = (ℓ_f(x) − mean_k ℓ_f(y_k)) / sd_k ℓ_f(y_k),
  where y_1..y_16 are samples of E under x's own conditioning at temperature 1 and top-p 1.0 (the
  full model distribution), each scored by teacher forcing. S-TYP = −sqrt(mean_f z_f²). Two-sided:
  a performance more predictable than the model's own samples is as atypical as a less
  predictable one. Computed on P and V only (cost).
- **S-DEV** (deviation-only agreement) = the (a) composite r of x against E's K = 8 sample mean,
  except that a target with zero variance in x (a flat target) scores 0 instead of undefined. It
  scores only the shape of the expressive deviation, not its size.
- Baselines under the same battery: **B-smooth** (minus the mean squared first difference of
  velocity and log IOI, R-06) and **B-amount** (mean over the three targets of the rendition's
  s.d., each divided by the median over real renditions).

The battery (`expression_data.VARIANTS`; every variant keeps the real rendition's notes and
conditioning, seed 20260928 + crc32(item)): exact deadpan; deadpan with velocity +12 and −12;
deadpan 15% slower; deadpan + noise (10 ms, 4 velocity) and (20 ms, 8); half-deadpans (flat
timing and durations with human velocity; human timing with constant velocity); jitter on the human
rendition (timing 10 / 20 / 40 ms, velocity 4 / 8 / 16); expression scaled by 1.5 and by 0.5; and
on P the PercePiano `Score` renditions (all human x Score pairs within a passage).

Paired AUC per variant = share of real renditions whose score exceeds their own variant's (ties
0.5); 95% CI by the two-way passage x performer bootstrap (2,000, seed 0).

**Pass criteria for a typicality score (all must hold, E, on P):**
- **R1 (deadpan battery):** for each of deadpan, deadpan_vel+12, deadpan_vel−12, deadpan_slow15,
  deadpan_noise10_4, half_flat_timing, half_flat_velocity: AUC at least 0.75, **and** the whole CI
  above 0.5, **and** the point AUC at least 0.5 within each of the 3 P works.
- **R2 (still detects noise):** jitT20, jitT40, jitV8, jitV16: AUC at least 0.75 and the whole CI
  above 0.5 (and per work at least 0.5).
- **R3 (replication on V):** point AUC at least 0.75 for every R1 variant on Vienna 4x22
  (88 renditions; CIs by piece are reported but not required: 4 excerpts).

Reading: **pass** = R1 and R2 and R3. A score that passes R1 and R3 but fails R2 is a **flatness
detector only**: it may feed the F-06 "too flat" flag and nothing else. Any other outcome is
**fail**: the score is not used anywhere. Reported but not required: deadpan_noise20_8, jitT10,
jitV4, scale1.5, scale0.5 (two-sidedness), the PercePiano Score renditions, sets A / R10u / R10s,
and the frozen model's S-TYP and S-DEV. The four scores and the battery are fixed here; no score
is tuned on any test set. A new candidate needs a new pre-registration, developed on the
validation pieces only.

**(d) Cost (question 5).** Median seconds per optimizer step and peak CUDA memory from `STAGES=
calibrate` (30 steps) on the 5080 before the full run, and wall time of every stage.

## Data

- **PianoCoRe v1.0** (Zenodo 19186016; D-03; CC BY-NC-SA 4.0): `metadata.csv` (sha256 `b26abcd1...5a70`)
  and `PianoCoRe-1.0-refined.zip` (sha256 `68f1b182...ef0f`), tier A, loaded with
  `pianolens.data.pianocore` (refined score + performance + RAScoP alignment).
- **(n)ASAP v2.1** (commit 4097b45; D-01): ground-truth alignments, robust ones only.
- **PERiScoPe v1.0 metadata** (HF `SyMuPe/PERiScoPe`, dataset commit 5a637bd9) to mark which pieces
  SyMuPe saw paired with a score in pretraining: 46,012 of its 46,473 rows match a PianoCoRe
  `performance_id`; 287 score-paired rows do not, and their 70 titles flag possible aliases
  (`periscope_possible`), which are kept out of R10u.
- **R-06 evaluation items** for P / V / A (`experiments/2026-09-27-R-06-expression-model-h2h/
  artifacts/`: matched notes, conditioning, generation items).
- Items: matched notes only (`expression_io.matched_pairs`; interpolated, deleted and inserted
  notes dropped), conditioning = the rendition's global seconds-per-quarter and median velocity
  (R-06). An item is dropped if fewer than 16 notes match or the matched share of score notes is
  below 0.8.
- Training selection: tier A performances of train pieces, excluding PianoCoRe rows whose source
  is ASAP (the (n)ASAP ground-truth versions are used instead); at most 50 per piece (seeded draw
  per piece). Measured from the metadata before the match filter: 1,307 train pieces, 38,902
  performances, 70.6 M non-interpolated notes; validation 79 pieces, 2,428 performances; (n)ASAP
  robust performances on train pieces: 609 (32 on validation pieces, 193 on test pieces).
- Test items for R10u / R10s: up to 50 performances per piece (6,402 over 141 pieces), same rules.

## Splits

Fixed by `make_split.py` (seed 20260928) and committed as `split/pieces.csv` (one row per piece id
across datasets: `work`, `split`, `role`, PERiScoPe status, R-02 membership).
- **Unit: the work.** All movements of a sonata, a prelude with its fugue, and all canonical ids
  that share a work key go to one side (`expression_split.work_key`). Hand-mapped aliases: ASAP's
  Italian Concerto -> BWV 971; ASAP Haydn sonatas -> Hob. XVI numbers; ASAP Ravel Miroirs 3 / 4 ->
  PianoCoRe ids.
- **Test (257 piece ids in 129 works; never trained on):** P (3 works: Beethoven WoO 80, Schubert
  D935 no. 3, all of D960), V (4: Chopin Op. 10/3, Op. 38, Mozart K. 331, Schubert D783), A (the 23
  works of Pianist Transformer's shipped ASAP test folders), R10u (75 works: every R-02 piece with
  at least 50 tier A performances that has no score-paired PERiScoPe performance and no possible
  alias, plus their work-mates), R10s (24 R-02 works that are paired in PERiScoPe; seeded draw; an
  exposure contrast for R-10). These are **all R-10 evaluation pieces**: R-10 must choose its
  pieces from R10u (unseen by both) and may use R10s for the exposure contrast.
- **Validation (91 piece ids, 59 works):** 5% of the remaining works that have tier A
  performances (seeded). Used for early stopping and nothing else; never reported as a result.
- **Quarantine (81 piece ids):** works of training pieces whose composer and catalogue numbers
  may alias a test or validation piece under another id (`expression_split.alias_conflicts`;
  e.g. prefixed English Suite BWV 808 movements, Clementi Op. 36 No. 1). Used for nothing.
- **Train:** everything else (5,740 piece ids; 118,243 tier A performances before the cap).
- **Leakage checks, twice:** `prep_data.py` fails if any training item's piece is not `train`,
  if any held-out work reaches training, or if a source performance appears in two splits
  (`leakage_report.json`); the tokenizer re-checks the training items against the committed split
  before writing shards.
- Seeds: split 20260928; per-piece cap 20260928 + crc32(piece) mod 100,003; training 20260928;
  variants 20260928 + crc32(item) mod 1,000,003; generation 0; bootstrap 0.

## Baselines

- (a): the **frozen** SyMuPe EncDec-base (R-06 and its re-run here); the R-06 **ridge** and the
  **leave-one-out other performers** mean as references (P, from R-06).
- (b): the frozen model's captured share and a random subspace of the same dimension.
- (c): S-RAW (the R-06 failure), B-smooth, B-amount.
- Secondary arm: Pianist Transformer frozen vs fine-tuned (pt_E), same (a) and (b).

## Method

- **E (primary).** SyMuPe EncDec-base (HF commit 1b942f28, symupe 1.1.0 at 13cc57d) fine-tuned
  from the released weights with the model's own loss (cross-entropy over the performance token
  fields, as the package computes it). Windows of 256 notes, random start, SOS / EOS only at the
  true start / end (as the R-06 adapter scores); encoder input = the package's
  `prepare_sequence` with the performance fields masked. AdamW, lr 1e-4, weight decay 0.01,
  500 warmup steps, cosine decay to 10%, gradient clip 1.0, 64 windows per step (32 x 2
  accumulation), bf16 autocast, at most 30,000 steps (about 7 passes over the ~66 M training
  notes). Validation loss every 1,000 steps on up to 2,048 fixed windows of the validation pieces;
  early stop after 5 evaluations without a 0.1% relative improvement; the best checkpoint
  (possibly step 0 = the pretrained weights) is the model.
- **F (flat model for S-LR).** Same recipe on the flat renditions, at most 5,000 steps, eval
  every 500.
- **pt_E (secondary).** Pianist Transformer rendering (HF 8f156820, code 747df2d) fine-tuned from
  the released SFT weights with its own seq2seq loss; tokens exactly as the R-06 adapter (the
  authors' SFT label format with our alignment); windows of 512 notes (4,096 tokens, the authors'
  context); lr 1e-4, 200 warmup, cosine to 10%, 32 windows per step (2 x 16), bf16, at most 8,000
  steps (about 2 passes, as the authors' SFT), eval every 500, same early stopping.
- If the loss is non-finite or the validation loss rises above 1.5x its step-0 value within the
  first 1,000 steps, the run restarts once at half the learning rate (disclosed). No other
  hyperparameter is tuned.
- **Evaluation** (`job/eval.sh`): items and all variants (`make_eval_items.py`); teacher-forced
  scores for every item and arm; K = 8 samples per passage for P / V / A (top-p 0.95, seed 0, as
  R-06) and K = 16 per piece for R10u / R10s; S-TYP samples (K = 16, top-p 1.0) for P and V;
  `summarize_eval.py` computes everything above.
- Resume semantics: a resumed run restores weights, optimizer, scheduler, step and early-stopping
  state exactly; the data stream is re-seeded from (seed, step), so it differs from an
  uninterrupted run after the resume point. Interruptions are listed in the run record.

## Command

On the GPU box (Henry; details in `job/README.md`):
```
bash job/setup.sh && bash job/setup.sh pt
bash job/fetch_data.sh
STAGES=prep bash job/run.sh && STAGES=tokenize bash job/run.sh
STAGES=calibrate bash job/run.sh                 # record s/step and peak memory first
bash job/run.sh                                  # E, then F
STAGES="tokenize_pt calibrate_pt train_pt" bash job/run.sh
bash job/eval.sh
```
The split: `uv run python experiments/2026-09-28-R-07-symupe-finetune/make_split.py`.

## Cost and time estimate

Measured anchors (R-06 README (d), this Mac): SyMuPe one fp32 AdamW step at 32 windows x 256
notes: 2.7 s and 6.5 GB (CPU); 128 windows: 10.9 s and 23 GB. Pianist Transformer at 4,096 tokens:
batch 1 8.9 GB, batch 2 15.4 GB, batch 2 1.6 s per step (MPS, fp32). Window construction here:
0.6 ms per 256-note window on one CPU core (measured on this Mac, so the data loader is not the
bottleneck).

| Stage | Work | 5080 time | Mac CPU upper bound (from the anchors) |
|---|---|---|---|
| fetch + prep + tokenize | 3.8 GB download; ~48 k items; disk about 40 GB in all (token shards measured in the dry run at 180 / 175 / 65 bytes per note for E / F / PT, items about 44: about 13 + 12 + 5 + 3 GB for ~70 M notes) | download-bound; prep about 30 min at 12 workers (the tier A cache build took 29 min for 157 k) | same |
| calibrate | 30 steps | minutes | - |
| E | 30,000 steps x 64 windows | 30,000 x (s/step from calibrate) | 2 x 2.7 s x 30,000 = 45 h |
| F | 5,000 steps x 64 windows | 5,000 x (s/step) | 7.5 h |
| pt_E | 8,000 steps x 32 windows of 4,096 tokens | 8,000 x (s/step from calibrate_pt) | 16 x 1.6 s x 8,000 = 57 h (MPS) |
| eval, P / V / A | 17 items per rendition x 1,149 renditions (220,777 real notes); typset 16 samples x (P + V: 160,284 notes) | minutes to hours | at R-06's CPU rates (scoring 0.2 ms/note, sampling 37 ms/note per 8 samples): about 4 h per SyMuPe arm, mostly typset |
| eval, R10u / R10s | 6,402 renditions x 17 items, at most 3,000 notes each (median score 1,731 notes); 141 pieces x 16 samples | hours | about 15 h per arm at the same rates; run it on the GPU |

- **VRAM on the 16 GB 5080.** SyMuPe: weights + gradients + Adam = 0.4 GB; 32 windows used 6.5 GB
  in fp32 on CPU, so 32 per micro-batch in bf16 should fit; if `calibrate` reports more than
  14 GB peak, use `--micro-batch 16 --accum 4` (same 64 windows per step). Pianist Transformer:
  2.2 GB of weights, gradients and Adam; micro-batch 2 in bf16 (fp32 measured 15.4 GB on MPS);
  fallback micro-batch 1 x 32 accumulation, then `--grad-ckpt`. sm_120 needs CUDA 12.8+ wheels:
  `setup.sh` pins torch 2.7.1 from the cu128 index (the version the Pianist Transformer authors
  used with cu128).
- **Fits on the 5080**, so no cloud is expected. **Cloud fallback** (only after O-04 approval;
  no provider chosen): hours = steps x (s/step measured by `calibrate` on the rented GPU), cost =
  price per GPU-hour x hours. For E + F + pt_E: (30,000 + 5,000) x t_SyMuPe + 8,000 x t_PT hours
  / 3,600, times $P per hour. The Mac bound above (about 110 h for E + F + pt_E, CPU and MPS) is
  an upper bound for any recent CUDA GPU.

## Dry run (Mac CPU, 2026-09-28; pipeline check, not results)

`DRY_RUN=1 bash job/run.sh` then `DRY_RUN=1 bash job/eval.sh` with `R07_HOME=artifacts/dryrun/home`
(`setup.sh` run with `TORCH_INDEX=pypi`: torch 2.7.1 CPU), data read from the Mac's `data/raw`.
Stages: prep (6 train, 2 val, 2 R10u pieces, 3 performances each, + 1 (n)ASAP performance; leakage
check OK) -> tokenize -> train E 3 steps -> stop -> resume from step 3 to 6 -> tokenize flat ->
train F 4 steps -> tokenize PT -> train PT 2 steps -> calibrate (both arms) -> eval on the 2 R10u
pieces (all five arms: score, generate K = 2, typical-set samples) -> summarize, including the H1b
code path (run separately with the 20-rendition minimum lowered to 3). Outputs in
`artifacts/dryrun/` (gitignored). Checks that passed:
- The resumed run logs "resumed from step 3" and ends at step 6 with the same best validation loss
  as a second, independent stop-and-resume run (3.35077...), so resume is deterministic.
- Shards store ids as int16 and values as float32; the step-0 validation loss is identical to the
  uncompacted shards to all printed digits (3.4084803263346353).
- Every arm wrote scores for all 85 items (5 renditions x 17), and `summarize_eval.py` produced
  every table and the pass / fail reading.

Disclosure: the dry-run summary printed toy numbers (per-note r and AUCs over 5 renditions of 2
R10u pieces, from models trained for 2 to 6 steps on 18 performances). They were printed after the
decision rules above were written and changed nothing. The two pieces (`scarlatti_k32` and a
Notebook for Anna Magdalena minuet) stay in R10u.

## Threats to validity

- **Pretraining exposure.** SyMuPe was pretrained on PERiScoPe, which overlaps PianoCoRe heavily;
  most held-out PianoCoRe pieces (R10s, A, V) were seen paired in pretraining. Only P, the 76 R10u
  pieces with no paired PERiScoPe performance, and D783 no. 15 are unseen by both steps. Unpaired
  (raw) PERiScoPe performances of R10u pieces may exist; SyMuPe's own description says it trains
  on pairs only.
- **Aliases.** Piece ids differ across sources; the work key, the hand map and the catalogue-number
  quarantine catch the cases we could find, not necessarily all (e.g. arrangements, titles with no
  catalogue number).
- **Transcribed MIDI.** Almost all PianoCoRe performances are audio transcriptions; transcribed
  velocity is compressed and noisy (D-10). R10u results inherit this; P, V and A do not.
- **Flat model family.** S-LR depends on F's training family; it is narrower than the battery by
  design, but a different family could change the result. It is fixed here.
- **S-DEV is shape-only.** It cannot penalise exaggeration (scale1.5 is reported for this reason).
- **K samples.** K = 8 / 16 makes predicted means and typical-set moments noisy; the r values are
  lower bounds, and S-TYP's z uses a 16-sample s.d.
- **Resume changes the data order** after an interruption (weights and optimizer are exact).
- **GPU vs CPU sampling** differ numerically; the frozen re-run on the same device is the paired
  reference.

## Run record

Run 1, started 2026-09-29 by a lead session on Henry's RTX 5080 box.

- **Machine.** Windows 11 (native, no WSL), Git Bash, RTX 5080 16 GB (sm_120), driver 616.56;
  24 CPU threads. torch 2.7.1+cu128 in both venvs (`setup.sh`: "cuda 12.8 available True",
  capability (12, 0), bf16 matmul ok). The GPU is shared with the desktop (games, browser):
  about 7 GB of VRAM was in use by other processes during the run.
- **Code.** Commit dd13ab2 plus uncommitted changes, diff sha256 `c71b7d83be77...` at launch. The
  changes are platform fixes only; no recipe, split, selection or decision rule changed:
  - `job/*.sh`: LF line endings; `wpwd` (native Windows paths for Python) and `vpy` (a uv venv
    on Windows keeps python in `Scripts/`); `setup.sh` reinstalls pianolens on every run and, on
    Windows only, installs a no-op stub of the Unix `resource` module into the SyMuPe venv
    (symupe imports it only to cap memory in its parangonar aligner, which this job never calls).
  - `src/pianolens/data/pianocore.py` `_midi_from_bytes`: the temp MIDI file is closed before
    loading and deleted after. On Windows the old code failed every load (a NamedTemporaryFile
    cannot be reopened while open). A first prep run with the old code recorded 47,732
    `load_error` rows; it was discarded (logs kept in `job/outputs/logs_failed_run1/`).
- **Data.** `fetch_data.sh`: all three PianoCoRe checksums OK; (n)ASAP at 4097b45.
- **Split.** `prep_data.py` hashed the checked-out `split/pieces.csv` as `d7ec539c...` because git
  (`core.autocrlf=true`) checked it out with CRLF endings. With LF endings the file hashes to
  `3341bfa5...86`, identical to the committed blob: same split, different line endings.
- **prep** (12 workers, 784 s): 48,373 rows, 45,670 items, 2,703 excluded for matched share
  < 0.8. Train 36,686 PianoCoRe items (1,280 pieces) + 609 (n)ASAP (118 pieces); val 2,318 + 32
  (78 + 11 pieces); test 6,025 PianoCoRe items (139 pieces). Leakage check OK (0 held-out pieces
  or works in train, 0 performances in two splits).
- **tokenize** (E): train 37,295 items -> 146 shards, 636 failed (1.7%); val 2,350 -> 10 shards,
  9 failed. Every failure is the R-06 adapter's guard "performance token order differs from
  interchange order"; those items are skipped. The rate was not anticipated in the
  pre-registration and is disclosed here.
- **R-06 evaluation items (P / V / A)** were not on this machine (gitignored, on the Mac). They
  were rebuilt here with the unchanged R-06 `prepare.py` from PercePiano e672299, Vienna 4x22
  1033ade and (n)ASAP 4097b45. Counts match the R-06 README exactly: P 981 renditions in 86
  passages (1 excluded for matched share) and 103 external deadpans, A 80, V 88. The
  reproduction gate in (a) is the numeric check.
- **calibrate** (`outputs/calibrate/calibrate.json`): 0.150 s per step (median of 25 timed),
  64 windows per step, peak 2.77 GB, projected 1.25 h for 30,000 steps. No cloud GPU needed.
- **train E** (21:15-21:47 UTC, no interruptions): step-0 validation loss (the pretrained
  weights) 3.2450 on 2,048 windows; 2.4675 at step 1,000; best 2.4395 at step 9,000; early stop at
  step 11,000 (5 evaluations without a 0.1% relative improvement). `best.pt` = step 9,000. The
  "minimum for use downstream" validation-loss condition (best below step 0) holds; the P
  condition is decided by (a).
- **tokenize_flat**: same 636 / 9 skipped items as tokenize (same guard), so E and F see the
  same item set.
- **train F** (21:49-22:06 UTC): step-0 validation loss 2.0242 (flat validation renditions);
  best 0.9327 at step 5,000 (the cap; not stopped early).
- **tokenize_pt**: 37,295 / 2,350 items, 0 failures.
- **calibrate_pt**: 3.14 s per step (32 windows of 4,096 tokens, micro-batch 2 x 16), peak
  8.32 GB, projected 6.98 h for 8,000 steps. Measured while the frozen evaluation shared the GPU,
  so the time is an upper bound. Fits without the fallbacks.
- **eval**: frozen and pt_frozen started 21:21 UTC while E trained (they do not depend on E; the
  recipe and decision rules were fixed before); E and F started 22:08 UTC.
- **train_pt** started 22:08 UTC alongside both evaluations (7.2 s per step while sharing the GPU,
  against 3.14 calibrated). Validation loss: step 0 1.6420, 500 1.0578, 1,000 1.0294, 1,500 1.0176.
- **Interruption (about 23:50 UTC).** With three GPU jobs and their CPU workers running, the machine
  ran low on RAM (4.1 of 31.7 GB free) and the Claude Code session stopped the three launching
  shells; the Python jobs kept running without them. They were stopped deliberately at 00:01 UTC,
  right after pt_E saved `last.pt` at step 1,500 (`last.pt` and `best.pt` both step 1,500, checked
  by loading them). All 5,212 evaluation outputs written in the preceding hour load cleanly (the
  writes are not atomic, so this was checked). Nothing was recomputed or discarded.
- **Restart (00:03 UTC), one job at a time**, from a detached driver: eval (frozen, E, F,
  pt_frozen; existing per-item outputs are skipped), then train_pt resumed from step 1,500, then
  eval of all arms including pt_E. pt_E's data order after the resume follows the documented
  resume rule (re-seeded from (seed, step)).
- **results/P** written 00:58 UTC (arms frozen, E, F, pt_frozen). Provisional readings, before any
  audit: reproduction gate missed by 0.001 (frozen P composite 0.3987 vs 0.388; pt_frozen 0.3948
  vs 0.393); (a) E − frozen −0.0509 [−0.0720, −0.0287] = **harms**, so R-10 uses the frozen model;
  (c) on P, S-LR meets R1 and R2 (R3 on V pending), S-DEV and B-amount meet R1 only, S-TYP and
  S-RAW fail R1. Details in `REPORT.md` section 4b.
- **results/V** written 01:58 UTC. Provisional: R3 met for S-LR and S-DEV (every R1 variant AUC
  1.000), not for S-TYP (half_flat_velocity 0.239). Pre-registered readings, before audit: S-LR
  **pass**; S-DEV **flatness detector only**; S-TYP **fail**. Secondary (a) on V: E − frozen
  −0.098 [−0.135, −0.063].
- **results/A** written about 03:00 UTC. Secondary: E − frozen −0.094 [−0.145, −0.053];
  pt_frozen − frozen −0.162 [−0.229, −0.100]; S-LR AUC 1.000 on every R1 variant.
- **Pause, about 06:03-17:01 UTC 2026-09-30.** The PC entered a low-power state (Kernel-Power
  events) despite AC sleep and hibernate being set to "never"; the jobs were suspended, not killed,
  and resumed on wake. No outputs lost. R10u frozen scoring was at 25,197 of 64,736 items on
  resume. The R-07 processes run at BelowNormal CPU priority so the machine stays usable; this
  changes speed only.
- **train_pt resumed 04:30 UTC 2026-10-01** from `last.pt` (step 1,500), in a second detached
  process running in parallel with the evaluation driver (same `run.sh` stage and arguments,
  including 4 data workers; it writes `.done_train_pt` on completion, so the driver's later
  train_pt stage skips). 2.78 s per step at step 1,525, peak 8.33 GB, while sharing the GPU.
- **train_pt finished 09:40 UTC 2026-10-01** at the 8,000-step cap (not stopped early; 4 bad
  evaluations at the end). Validation loss: step 0 1.6420, 1,500 1.0176, 6,500 0.9786, 8,000 0.9762
  (best; `best.pt` = step 8,000). No sleep events during the night.
- **eval pt_E on P / V / A** started 11:02 UTC 2026-10-01 in parallel with the driver (which was
  on F for R10u), listing all five arms so the P / V / A summaries are rebuilt with every arm.
  Finished 12:05 UTC. `summarize_eval.py` only differences against frozen SyMuPe, so the
  pre-registered secondary pt_E − pt_frozen was computed afterwards with its own `boot_ci` and
  `t_interval` on `a_per_rendition.csv` (`results/pt_E_vs_pt_frozen.json`). Provisional: P +0.013
  [−0.013, 0.039] no detectable change; V −0.072 [−0.240, 0.095] no detectable change; A +0.031
  [0.001, 0.064] improves.
- **Paused 21:30 UTC 2026-10-01** at the owner's request (machine running hot): the R-07 python
  processes were suspended in place (NtSuspendProcess), during pt_frozen generation on R10u (61 of
  91 pieces). Done at that point on R10u: frozen, E, F (all), pt_frozen scoring. Resuming continues
  from the same item; nothing is recomputed.
- **Resumed 2026-10-02** at the owner's request (NtResumeProcess), still at BelowNormal priority;
  pt_frozen R10u generation continued from 64 of 91 pieces. Paused again later on 2026-10-02 at
  the owner's request, at 71 of 91 pieces.
- **Stopped 2026-10-02** at the owner's request to free VRAM (a suspended process keeps its GPU
  memory): the driver and all R-07 processes were terminated. The 71 completed generation outputs
  load cleanly (newest three checked). To finish, rerun the driver script; eval.sh skips every
  existing per-item output, so only the in-progress piece is redone. Remaining: pt_frozen R10u
  generation (20 pieces), pt_E on R10u, all arms on R10s.
- **Restarted 05:30 UTC 2026-10-03** (owner asleep; full resources, Normal priority) as two
  per-set streams (`SETS=R10u` and `SETS=R10s`, all arms). Running both at once oversubscribed
  VRAM (the Pianist Transformer generation process alone reached 14.5 GB dedicated) and both
  crawled, so the R10s stream was stopped after 2 items and queued to start when the R10u stream
  exits. R10s eval set: 1,812 renditions in 48 passages (30,804 items).
- **results/R10u** written 00:18 UTC 2026-10-04. pt_E generation on R10u failed for all 91 items
  with CUDA out of memory (a game held about 5 GB of VRAM at the time); pt_E is therefore absent from
  this summary, and a retry is queued after R10s. Provisional readings: (b) H1b preview for E,
  median captured share 0.098 (random 0.012 / p95 0.015) → "at the H1b falsification level"; R²c
  velocity 0.413 (inconclusive), log IOI 0.065 (falsification level); frozen reads the same
  (0.118, 0.325, 0.142). Secondary (a) E − frozen +0.041 [0.028, 0.051] (improves on R10u, unlike
  P / V / A).
- **Paused 03:19 UTC 2026-10-04** at the owner's request (processes suspended in place) during
  frozen scoring of R10s; last output written 22:19:30 local, none after. Resumed later at the
  owner's request; frozen R10s scoring continued from where it stopped.
- **2026-10-04 ~00:20 local**, owner asleep, "make use of everything": R-07 processes set to Normal
  priority, and a keep-awake helper (SetThreadExecutionState, ES_SYSTEM_REQUIRED) started that
  exits when no R-07 process remains, after two nights were lost to sleep (about 11 h each).
  Power settings unchanged. Execution environment only; no effect on results.
- **Paused 20:20 UTC 2026-10-04** at the owner's request (suspended in place) during pt_E
  generation on R10s; frozen, E, F and pt_frozen are complete on R10s. Resumed later at the
  owner's request (43 of 48 pieces done at the pause).
- **results/R10s** written 04:22 UTC 2026-10-05 (all five arms; 0 generation errors). Provisional:
  captured share E 0.086, frozen 0.110, pt_E 0.107, pt_frozen 0.103 (random p95 0.010); R²c
  velocity E 0.523; (a) E − frozen +0.002 [−0.016, 0.015], pt_E − pt_frozen +0.059 [0.037, 0.083]
  (computed afterwards with the summariser's `boot_ci`). The R10u retry of pt_E generation started
  at the same time.
- **Run complete 08:29 UTC 2026-10-05.** pt_E R10u generation retry: 91 of 91, 0 errors; R10u
  re-summarised with all five arms (E and frozen unchanged). Provisional: pt_E captured share
  0.124, R²c velocity 0.492, log IOI 0.260; (a) pt_E − pt_frozen on R10u +0.100 [0.089, 0.114].
  Every planned arm x set now has outputs. Verdict: Provisional, awaiting `eval-auditor`.
- **Committed artefacts** (for review on another machine): `results/<set>/` holds copies of each
  set's `summary.json`, `pass_fail.json`, `auc.csv`, `h1b.csv` and `a_per_rendition.csv`
  (statistics only, about 6 MB), plus `results/pt_E_vs_pt_frozen*.json`. The full outputs
  (`job/outputs/`: per-item scores, generations, token shards, checkpoints) stay local on the RTX
  5080 box and are not in git (license and size).
