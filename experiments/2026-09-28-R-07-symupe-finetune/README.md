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

## Audit (2026-10-05, eval-auditor)

**Verdict: Confirmed with caveats.** Every pre-registered reading follows from the outputs, and
every audited number reruns exactly from the local outputs. The readings are: (a) **harms** on P,
so R-10 uses the frozen model; (c) S-LR **pass**, S-DEV **flatness detector only**, S-TYP
**fail**; (b) E **at the H1b falsification level**. Four caveats change what the readings
license, and the REPORT must state them (see "Required corrections"):
1. (b) cannot reach 0.50 at K = 16. Sixteen held-out *real* performances, scored as if they were
   model samples, capture a median of only 0.273 of the shared variance.
2. S-LR's pass is real, but it is the sum of two parts: a flatness detector (F) and a
   noise-sensitive likelihood (E). Among human performances its ranking is mostly "distance from
   flat".
3. "Harms" on P holds across the 3 works as fixed groups. The 3-work t-interval includes 0, and
   one work shows no change.
4. Ten of the 91 R10u pieces were seen paired in pretraining. The REPORT calls all of R10u
   unseen.

Read-only audit, CPU only. Nothing was run on the GPU, and no process was started or stopped.
Audit scripts are in the session scratchpad (`a.py`, `half.py`, `slr.py`, `slr2.py`, `pt.py`,
`h.py`, `au.py`, `ceil2.py`, `sty.py`, `tf.py`). They import `job/summarize_eval.py` unchanged
and run with `C:/Users/Vuduc/r07/venv-symupe/Scripts/python.exe`. Nothing in `src/`, `job/` or
`results/` was changed.

### 0. Pre-registration and code

- The README up to `## Run record` is byte-identical to the version committed in `e4becf8`
  (2026-09-28 00:13 -0500, before the run on 2026-09-29). Checked with `diff` of
  `git show e4becf8:README.md` against the working copy, both cut at `## Run record`.
- `summarize_eval.py`, `symupe_eval.py`, `make_eval_items.py`, `pt_train.py`,
  `symupe_train.py`, `prep_data.py` and `trainlib.py` are unchanged since `e4becf8`.
  `git diff e4becf8 HEAD --stat` lists only `eval.sh`, `run.sh`, `setup.sh` and
  `src/pianolens/data/pianocore.py`, and the diffs are the platform fixes described in the run
  record. The analysis code was therefore fixed before any result existed.
- The committed `results/<set>/{summary.json, auc.csv, a_per_rendition.csv}` are byte-identical
  to `job/outputs/results/<set>/` for all five sets (`cmp`).

### 1. (a) "harms" on P: Confirmed with caveats

- **The bootstrap is as pre-registered.** `two_way_weights` multiplies passage and performer
  resampling multiplicities (pigeonhole two-way). Each resample's statistic is the per-work
  weighted mean, then the unweighted mean of the 3 works. 2,000 resamples, seed 0. Rerun from
  `a_per_rendition.csv` with the script's own `boot_ci`:
  - composite −0.0509 [−0.0720, −0.0287];
  - velocity +0.027 [−0.001, 0.056], log IOI −0.063 [−0.102, −0.026], log articulation −0.116
    [−0.152, −0.082].

  All identical to `summary.json`. Pairing is an inner join on `stem`: n = 981, 0 NaN. The
  cluster structure is real: 86 passages and 24 performers (12 per work, 12 of them span 2
  works), median 40.5 rows per performer. In 2,000 resamples no work ever got zero weight, so
  the estimand never changed.
- **Per work** (E − frozen): WoO 80 −0.045, D960 mv2 −0.105, D960 mv3 −0.003 (516 of the 981
  renditions).
  - Leaving one work out: −0.054 (without WoO 80), −0.024 (without mv2), −0.075 (without mv3).
    All are negative.
  - **Per target and work:** articulation −0.121 / −0.210 / −0.018 and log IOI −0.056 / −0.118 /
    −0.014. Velocity is +0.042 / +0.014 / +0.024: E is slightly better on velocity in every work.
  - The t-interval over the 3 works, [−0.178, 0.076], includes 0, as the REPORT says.
  - The bootstrap holds the 3 works fixed. "Harms" is therefore a statement about these three
    works. Whether it generalises to other works rests on the secondary sets, which agree:
    V −0.098 [−0.135, −0.063], with all 4 excerpts negative (t-interval [−0.171, −0.026]), and
    A −0.094 [−0.145, −0.053].
- **Robustness to the K = 8 sample draw** (my addition). The composite was recomputed from the
  first and second halves of each arm's 8 samples (K = 4 each):
  - E − frozen = −0.041 [−0.064, −0.019] and −0.063 [−0.086, −0.039];
  - crossed halves: −0.039 [−0.064, −0.017] and −0.065 [−0.088, −0.043].

  Every sample split keeps the whole CI below 0.
- **Reproduction gate: applied correctly.**
  - Frozen P composite 0.3987 vs R-06's 0.388. The difference is 0.0107 > 0.01, so the gate is
    missed. The paired comparison uses the re-run frozen arm (`summarize_eval` joins on this
    run's frozen rows), and R-06's value is shown alongside in REPORT 4b, as the rule requires.
  - The shift is in all three works: per work 0.436 / 0.424 / 0.336 against R-06's
    0.428 / 0.416 / 0.320. It is mostly in articulation (0.351 vs 0.319); velocity (0.515 vs
    0.512) and log IOI (0.330 vs 0.333) reproduce.
  - The size is within sample-draw variability. The two K = 4 halves of this same frozen run
    differ by up to 0.025 in a single work (D960 mv2 0.393 vs 0.413).
  - R-06's per-item generations are not on this machine, so GPU-vs-CPU sampling cannot be
    separated from item rebuilding. The rebuilt items have the counts of R-06's prepare, and its
    `prepare.py` and its (a) code (`analyze.py` `target_r`, `passage_predictions`) compute the
    same quantities as `summarize_eval.py`.
- **Downstream rule:** "harms" means E is not used, so R-10 uses the frozen model. This is
  correctly applied.

### 2. (c) S-LR "pass": Confirmed with caveats (genuine, but it is a flatness detector plus a noise penalty)

- **The rules are applied as pre-registered.** `pass_fail.json` checks the following:
  - R1: AUC ≥ 0.75, lower CI > 0.5 and per-work point AUC ≥ 0.5, on the 7 required variants;
  - R2: the same rule on jitT20, jitT40, jitV8 and jitV16;
  - R3: point AUC ≥ 0.75 on V for the 7 R1 variants, no CI required.

  E:S-LR results:
  - R1 on P: every variant 1.000 [1.000, 1.000], minimum work AUC 1.000.
  - R2 on P: 0.946 / 0.949 / 0.927 / 0.916, CIs above 0.87, minimum work AUC 0.880.
  - R3 on V: all 1.000.
- **The separations are not knife-edge.** No paired comparison is tied.
  - The smallest paired margin (S-LR real − S-LR variant, nats per note) over all 7 R1 variants
    on P is 1.26 (half_flat_velocity). Median margins run from 3.1 to 8.3.
  - Every real P rendition has S-LR ≥ 1.42.
  - The same holds on V (minimum margin 0.45), A (1.94), R10u (0.95) and R10s (2.22).
- **What does the separating:** whichever field is flat. No single field dominates.
  - Per-field log ratios (ℓ_E − ℓ_F per field) on P:
    - deadpans: TimeShift, Velocity and TimeDuration each separate at 1.000 on their own;
    - half_flat_timing: TimeShift 1.000, TimeDuration 1.000, Velocity 0.443;
    - half_flat_velocity: Velocity 1.000, TimeShift 0.629, TimeDuration 0.536.
  - F assigns near-certainty to any constant field. Median ℓ_F of the core fields on exact
    deadpans is −0.09 to −0.27 nats per field, against −3.7 to −5.0 on real renditions.
- **The two halves of S-LR.**
  - **−ℓ_F alone** passes R1: AUC 1.000 on every R1 variant on P and V. It fails R2 completely
    (0.000-0.033), because jitter makes a rendition slightly *less* F-like.
  - **ℓ_E alone** (S-RAW) passes R2 (1.000) and fails R1, as in R-06.
  - S-LR passes both because the F gap on flat variants is large (median 4-12 nats) while E's
    jitter penalty is small and has the right sign (0.3-1.5 nats). This is the intended
    construction, not an artefact. But it means S-LR's R1 result tests F, and its R2 result
    tests E.
- **F's "narrow family" did not make the offset variants a generalisation test.** F scores
  deadpan_vel+12, vel−12 and slow15 as well as the exact deadpan (core ℓ_F −0.50 to −0.56 vs
  −0.53 on P). Being autoregressive, F detects *constancy* and copies the previous velocity and
  IOI, whatever the conditioning token says. Only deadpan_noise20_8 is genuinely out of family
  (ℓ_F −7.3, against about −13 on real). It is still separated at 1.000, through its flat
  durations.
- **No construction artefact found.**
  - Real and variant share notes, note count, conditioning tempo and conditioning velocity
    (`item_variants` uses `_with` on the same item).
  - S-LR is a per-note mean, so note count cannot enter.
  - The exact deadpan's velocity equals the conditioning velocity, but vel±12 (not equal to it)
    behaves identically, so equality with the conditioning token is not what separates.
  - Deadpans drop the pedal, but TimeDurationSustain is not in the core score.
  - The PercePiano Score renditions (different notes) give 0.988 [0.971, 0.998].
- **Caveats for any use of S-LR.**
  - Among real renditions, S-LR rank-correlates 0.83 (P) and 0.95 (V) with −ℓ_F. As a ranking
    of human performances it is mostly "how far from flat under F", not typicality.
  - It does not prefer the real rendition to the same rendition with its expression halved:
    scale0.5 AUC 0.491 (P), 0.545 (V), 0.388 (A). It does penalise exaggeration: scale1.5 0.915
    (P).
  - Passing is the pre-registered condition for use, not evidence that S-LR tracks quality.
    Any quality use needs its own test.

### 3. S-DEV "flatness detector only" and S-TYP "fail": Confirmed

- **S-DEV.**
  - R1 on P is met: AUCs 0.852-0.990, lowest CI 0.793 (half_flat_timing), minimum work AUC
    0.775.
  - R2 on P is not met: jitT20 0.660 and jitT40 0.678, below 0.75.
  - R3 on V is met: all 1.000.

  So the reading is "flatness detector only". R2 is required on P only; S-DEV happens to meet R2
  on V, which does not change the reading.
  - Caveat: the trivial baseline B-amount meets R1 (1.000 on all 7) and R3 as well, with higher
    AUCs than S-DEV. For the F-06 "too flat" flag, S-DEV adds nothing over B-amount.
  - S-DEV cannot penalise exaggeration (scale1.5 0.474), as the threats section anticipated.
- **S-TYP.**
  - R1 on P fails: half_flat_velocity 0.236 [0.175, 0.302]. The whole CI is below 0.5, and the
    minimum work AUC is 0.023.
  - R3 on V fails: half_flat_velocity 0.239.

  So the reading is "fail". The frozen model's S-TYP happens to pass R1 and R3 on V but fails
  R1 on P. It is reference only, by the pre-registration.

### 4. (b) H1b preview on R10u: Confirmed with caveats (the 0.50 bar is unreachable at K = 16)

- **The implementation matches the pre-registration.**
  - Inputs: majority score; first 3,000 distinct score notes; onsets kept if observed in at
    least half of the renditions; velocity centred per rendition.
  - Shared components:
    - velocity and log IOI blocks, each scaled to unit s.d.;
    - envelope-preserving surrogate: rows phase-randomised per block, columns rescaled to the
      real s.d.;
    - 100 surrogates, 95th percentile, seed 0;
    - k = leading eigenvalues above the null.
  - Captured share: the share of the expert variance in the k components that lies in the
    model's sample-deviation span. That span has 15 dimensions (median `model_dims` 15).
  - Random 15-dim subspace baseline: 200 draws.
  - The summary is the median over pieces with k > 0. One piece has k = 0, so the median is over
    84 of the 85 pieces with ≥ 20 renditions. Six R10u pieces have fewer than 20 renditions
    (3-17) and are excluded, as pre-registered.
  - Numbers reproduce: E 0.098 (random 0.012 / p95 0.015), median k 6, reliability 0.981 /
    0.980.
- **The unseen-only subset does not change the reading.**
  - The 85 H1b pieces are:
    - 74 of the 76 pre-registered "unseen" pieces;
    - 3 R-02 work-mates paired in PERiScoPe (Mozart K. 545 mv1-3);
    - 4 non-R-02 work-mates paired in PERiScoPe;
    - 4 unpaired non-R-02 work-mates.
  - Unseen only (74):
    - E: captured 0.096, R²c velocity 0.439, R²c log IOI 0.053;
    - frozen: 0.112 / 0.328 / 0.127;
    - pt_E: 0.124 / 0.495 / 0.259.

    Every threshold reading is the same as in the pooled summary.
  - Of the 76 unseen pieces, Glinka *La séparation* has no evaluation item, and one has fewer
    than 20 renditions.
- **Ceiling (my addition; CLAUDE.md rule 2 asks for one).**
  - Method: on the 72 R10u pieces with ≥ 36 renditions, I held out 16 real renditions as
    "samples". The shared components were computed from the remaining 20-34 renditions (median
    k 4.3), with the summariser's own `h1b_passage`, 3 random splits, seed 1.
  - Result: 16 real performances capture a median of **0.273** of the shared variance.
  - On the same splits and the same components:
    - E: 0.097, about 0.39 of the expert level;
    - frozen: 0.114 (0.46);
    - pt_E: 0.119 (0.48).
  - Consequences:
    - "Consistent with H1b" (≥ 0.50) was unreachable for any model with K = 16 under this
      statistic. Even a perfect sampler of the performer distribution would read "inconclusive",
      close to the 0.20 falsification line.
    - E's 0.098 is at the falsification level as worded. Against the reachable level, the
      correct summary is: E captures about 40% of what 16 real performances capture.
  - R²c is not affected in the same way. The mean of 16 real performances reaches R²c 0.90
    (velocity) and 0.90 (log IOI) against the other performers. E's 0.41 / 0.07 is therefore a
    real gap, and the R²c readings stand.
  - This is the R-09 lesson (check that every verdict branch can be reached). R-10 must
    calibrate the captured-share thresholds against this expert-sampler ceiling, or use larger
    K, before using them for the H1b verdict.

### 5. Post-hoc pt_E − pt_frozen: Confirmed, and properly disclosed

- I recomputed it with `boot_ci` and `t_interval` from `summarize_eval.py` on the committed
  `a_per_rendition.csv`. Results:
  - P +0.0128 [−0.0133, 0.0394], t [−0.086, 0.111];
  - V −0.072 [−0.240, 0.095];
  - A +0.031 [0.001, 0.064];
  - R10u +0.100 [0.089, 0.114];
  - R10s +0.059 [0.037, 0.083].

  All identical to `results/pt_E_vs_pt_frozen*.json`, with n matching (981 / 88 / 80 / 3,808 /
  1,812).
- The run record and REPORT state that the pre-registered secondary comparison was missing from
  the summariser and was computed afterwards with its own functions. No other statistic was
  added.
- Unseen-only R10u gives +0.101 [0.088, 0.114].

### 6. R10u (+0.041) vs P / V / A ("harms"), and the "transcription style" reading: Confirmed as labelled (possible, untested); must not be upgraded

- E − frozen on R10u reruns as +0.041 [0.028, 0.051]; unseen only it is +0.042 [0.030, 0.055].
  The gain is mostly articulation (+0.085), velocity +0.023, log IOI +0.014 (CI includes 0).
- **Descriptive support (my addition).** These are medians over renditions of each rendition's
  median log articulation (`sty.py`; 150 real renditions per set, 4 samples x 40 passages per
  arm, up to 40 passages).

  | | P | R10u |
  |---|---|---|
  | real performances | −0.69 | +0.02 |
  | frozen samples | −0.56 | −0.30 |
  | E samples | **+0.15** | ≈ 0.00 |

  - E's samples on P have transcription-like articulation (V: E −0.05 vs real −0.70).
  - E's sampled log IOI s.d. on P is 0.30, against 0.23 for the P performances and 0.31 for R10u
    performances.
  - Pearson r ignores a constant offset, so this does not by itself explain the r loss. But it
    shows E's sampled durations are in the transcribed regime.
- **Against, or confounded.**
  - R10s is also transcribed PianoCoRe, yet shows no change (+0.002 [−0.016, 0.015]). Its
    frozen baseline is higher (0.511 vs 0.431), consistent with pretraining exposure.
  - The R10 sets also differ from P / V / A in repertoire, segment length (up to 3,000 notes vs
    8-16 bars) and K (16 vs 8).
- The REPORT words this correctly ("one possible reading (not tested here)"). It is plausible
  for articulation and remains untested. A test would compare E's articulation error on
  Disklavier vs transcribed renditions of the *same* pieces.

### 7. Data and leakage: Confirmed

- `leakage_report.json`: `ok: true`, 0 unknown ids, 0 held-out pieces or works in train, 0
  performances in two splits, 37,295 rows on 1,285 training pieces. The tokenizers' re-check is
  also `ok`.
- **Split hash.**
  - `git show HEAD:.../split/pieces.csv | sha256sum` = `3341bfa5...296b86`.
  - The checked-out file hashes to `d7ec539c...` with CRLF and to `3341bfa5...296b86` with CR
    stripped.

  Same split, different line endings, as stated.
- **Token-order guard.** The 636 skipped training items fall in 21 pieces.
  - 8 pieces lose every item: Chopin Op. 60, Debussy L. 136/8, L. 123/1 and /12, Schubert D935
    no. 4, Beethoven Op. 31/1 mv2, Ravel Alborada, Lyapunov Op. 8.
  - The skipped items are long (median 3,694 notes vs 1,338 overall). They are 3.5% of training
    notes (1.7% of items).
  - They are 586 PianoCoRe and 50 (n)ASAP items, with capture models roughly in proportion to the
    training set.
  - Effects:
    - The guard is score-dependent, removes training data only, and cannot leak.
    - It slightly narrows E's and F's training repertoire.
    - pt_E had 0 failures, so the two arms' training sets differ by these 636 items.
    - No evaluation item failed scoring in any set.
- **`pianocore.py` fix: behaviour-neutral.** The bytes are written, the file is closed (flushed)
  on leaving the `with` block, then loaded by name and deleted in `finally`. On POSIX the loader
  reads the same bytes as before; only the deletion moves.

### 8. Run integrity: Confirmed

- **Counts.** For every arm x set, `score/` holds exactly the eval set's item count:
  P 16,780; V 1,496; A 1,360; R10u 64,736; R10s 30,804.
  - `gen/` holds every generation item: 86 / 4 / 16 / 91 / 48 for frozen, E, pt_frozen and
    pt_E. F has no generations, by design.
  - `typset/` holds every real item for frozen and E on P (981) and V (88).
  - `scores.csv` has equal rows per arm in every set.
  - S-LR is NaN only for non-E arms. S-TYP is NaN for E only on the 103 PercePiano Score items,
    which have no typset, by design (all five sets). `a_per_rendition.csv` has 0 NaN.
- **Checkpoints.** No E, F or pt_E output is older than that arm's final `best.pt` (`find !
  -newer`: 0 of 116,490, 115,176 and 115,421 files). pt_E's `best.pt` is dated 2026-10-01 09:39
  UTC (step 8,000). No output from an intermediate pt_E checkpoint entered any summary.
- **Partial files.** Every summary is newer than all of its inputs. `summarize_eval.py` loads
  every score, generation and typset file it uses (`np.load` raises on a truncated archive). The
  rebuilt summaries (P / V / A on 2026-10-01, R10s on 10-05 04:22, R10u on 10-05 08:29) therefore
  read every output without error.
- **pt_E resume.** `train_log.jsonl` has one `resume` event at step 1,500 and no duplicated
  steps. Validation loss falls monotonically to 0.9762 at step 8,000.
- **`_log_*.json` is weak evidence.** Each run overwrites it with only the items that run
  processed, and most were rewritten by later runs that skipped everything ("0 items, 0 errors").
  The informative ones:
  - pt_E P / V / A: 16,780 / 1,496 / 1,360 scored, 86 / 4 / 16 generated, 0 errors;
  - pt_E R10u generation retry: 91 items, 0 errors;
  - R10s, every arm: full item counts logged, 0 errors.

  Completeness rests on the counts above, not on the logs.

### Required corrections

To `REPORT.md`. The factual errors were corrected in place and each is marked "[audit
2026-10-05]":
1. Section 1 "Secondary sets" and the R10u heading in 4b called R10u "76 R-02 pieces unseen" and
   "unseen by pretraining and fine-tuning". The R10u evaluation set has 91 pieces:
   - 75 of the 76 unseen pieces;
   - 3 R-02 work-mates paired in PERiScoPe;
   - 7 non-R-02 work-mates paired in PERiScoPe;
   - 6 unpaired non-R-02 work-mates.

   So 10 of the 91 were seen paired in pretraining.
2. The pt_E section said "The only set with a detectable change is A". That was written before
   R10u and R10s; both now improve. Now limited to P, V and A.
3. R10s section: "the same level as on R10u (0.098-0.118)". With pt_E it is 0.098-0.124.
4. "Gaps": the bullet "No evaluation numbers exist yet" is marked as superseded by section 4b.

For the lead (interpretation; not edited by me):
- (b): add the expert-sampler ceiling (0.273) next to E's 0.098. State that 0.50 was unreachable
  at K = 16. R-10 must calibrate before its H1b verdict.
- (c): state that S-LR's R1 result comes from F and its R2 result from E. Among human
  renditions it ranks mostly by distance from flat (ρ 0.83 / 0.95 with −ℓ_F). It is indifferent
  to halved expression (scale0.5 0.49 on P).
- (a): give the per-target split, which shows velocity slightly better in every work. Add the
  leave-one-work-out values and the K-half robustness next to "harms".
- S-DEV: the trivial B-amount meets R1 and R3 at least as well, so prefer it for the F-06 "too
  flat" flag, or justify S-DEV over it.
- The README header line still says "Status: Provisional (pre-registered; job prepared, not
  run)". It is part of the hashed pre-registration and was left as is. The audited status is
  this section.

## Second audit (Mac, committed statistics only; full text in `AUDIT.md`)

**Confirmed with caveats (scoped)**, eval-auditor 2026-10-05. Full audit, box-only checks B1-B4
and their scripts: `AUDIT.md` in this folder. The status in line 2 is inside the hashed header and
is left as written.

- (a) on P: harms, as registered; R-10 uses frozen SyMuPe. Reproduction gate missed: 0.3987 vs
  0.3882 (+0.0105, tolerance 0.01), not "by 0.001".
- (b) H1b preview: **uninformative for H1b**, not "at the falsification level". Captured share
  measures sample diversity; 16 held-out real experts reach only about 0.25, so the 0.50 bar was
  unreachable. Log IOI R²c omits R-06's centering of the predicted curve (lower bounds). 5 of the
  74 "unseen" R10u pieces contain paired content.
- (c) S-LR "pass" stands as registered, but R1 is matched by B-amount and S-LR is at chance
  against halved expression (P 0.491); not used anywhere (DECISIONS 2026-10-05). The REPORT's
  "outside F's training family" is wrong.
- SyMuPe samples here were drawn at top-p 0.95 (EncDec-base ignores `lm_top_p`), including the
  S-TYP reference samples registered at 1.0; S-TYP failed regardless.
- Author fixes still pending after the box audit's REPORT corrections: AUDIT.md section 9 (REPORT
  sections 4 and 5 are stale; commit the pt_E - pt_frozen script; per-transcriber table, post hoc).

### Reconciling the two audits (lead, 2026-10-05)

The two audits were independent: the box audit had the full per-item outputs, the Mac audit only
the committed statistics. Both reach **Confirmed with caveats**, and every number they share agrees.

- **(b) wording.** The box audit keeps "at the falsification level as worded" and adds that E
  reaches about 0.39 of the expert-sampler level (0.273). The Mac audit reads the preview as
  uninformative (oracle about 0.25). The lead's reading (DECISIONS 2026-10-05) is
  **uninformative for H1b**: a bar that real performers cannot reach cannot falsify. R-10 uses
  mean-curve R²c against an expert oracle as the primary statistic.
- **Box-only checks B1-B4 (AUDIT.md section 10).** B1 is answered by the box audit section 2
  (S-LR per-field decomposition and margins), B4 by section 8 (counts, checkpoints, partial
  files). B3 is answered in part by section 1: the gate miss is within sample-draw variability and
  sits in articulation; R-06's generations are not on the box, so item rebuild vs GPU sampling
  stays unseparated. B2 (log IOI R²c with R-06's centering) was not run; R-10's `dev_r07` stage
  recomputes it.
- **R10u composition.** The box audit counts 10 of 91 pieces seen paired by id; the Mac audit and
  the R-10 pre-run review add 5 of the 74 "unseen" pieces with paired content inside whole-set ids.
  Neither changes a reading.
