# H1b: is the shared part of expert expression predictable from the score?
Ticket: R-10    Hypothesis: H1b    Status: Provisional (pre-registered 2026-10-05; job prepared, not run)

Pre-registered 2026-10-05 before any R-10 model sample exists. Everything below "Run record" is
added later. The piece list is fixed in `pieces.csv` (sha256 `a1c0e7c9...4b5f`, written by
`select_pieces.py --k 32`).

## What had been seen before this was written (disclosure)

1. **R-07's H1b preview (`2026-09-28-R-07-symupe-finetune/results/R10u|R10s/summary.json`), every
   arm.** It used a different representation (note-level velocity and log IOI, first 3,000 notes,
   up to 50 renditions, 100 surrogates) and an unadjusted span statistic at K = 16. Medians over
   R10u pieces: captured share frozen 0.118, E 0.098, pt_frozen 0.101, pt_E 0.124 (random
   15-dim subspace 0.012); R²c velocity / log IOI frozen 0.325 / 0.142, E 0.413 / 0.065,
   pt_frozen 0.251 / −0.024, pt_E 0.492 / 0.260. R10s: captured 0.086-0.110, R²c velocity
   0.325-0.523. The R-07 audit's expert-sampler ceiling: 16 held-out real renditions capture
   0.273; frozen 0.114 (0.46 of it), E 0.097 (0.39), pt_E 0.119 (0.48); the mean of 16 real
   renditions reaches R²c 0.90 on both targets.
2. **Every one of the 42 decision pieces was in that R-07 R10u evaluation** (all had at least 20
   renditions). This is unavoidable: no other PianoCoRe piece is unseen by SyMuPe pretraining and
   has enough performances. Checked from the metadata: the R10u role holds every R-02 piece
   with no score-paired PERiScoPe performance and no possible alias (76); outside R10u only 7
   such pieces have at least 50 tier A performances, and only one of them (bach_bwv871_prelude,
   52) has at least 50 on its majority score, so none can give a reference of 50 plus held-out
   performers. R-07's per-piece numbers are in its `results/R10u/h1b.csv`; I did not read the
   per-piece values for this design.
3. **Expert-only data on non-decision pieces:** the reachability simulation below, on 40
   calibration pieces (R-02 pieces of R-07's train / val roles; no model samples). It was used to
   choose K and the statistic. No R-10 model sample and no expert curve of a decision piece had
   been computed when this was written.
4. Metadata counts of the R10u pieces (performances per majority score; score note counts),
   used to set the eligibility rule and the compute estimate.

**Why the deciding statistic is not a re-reading of R-07 with a moved bar.**
- The representation is new and is the one DECISIONS fixes for H1b (R-02 curves: whole piece,
  smooth tempo + smooth velocity per beat; reference n = 50; envelope null; 20 surrogates).
- The samples are new: K = 32 per piece, seeds 100 and 101 (R-07 used seed 0, K = 16), on
  whole-piece generation items.
- The statistic is adjusted for a structure-free sampler. The simulation shows why this matters:
  on these curves an envelope-surrogate sampler (no cross-performer structure) already reaches
  0.58 of the expert-sampler ceiling on the unadjusted span statistic at K = 32, and reads
  "supported" in 80% of draws. An unadjusted ratio near 0.46, like R-07's, therefore does not
  show any shared structure on this representation, and R-07's numbers do not predict the
  adjusted ratio. I have no informative prior on where the models will land.
- The 0.50 / 0.20 thresholds are the plan's, unchanged. Only their reference (the expert-sampler
  ceiling above the structure-free null) is new, as the R-07 audit required.

## Question

On pieces unseen by the model, does a score-conditioned expression model reproduce the *shared*
expert components (the R-02 audit's above-null components), measured against what the same
number of real held-out performances reproduce? Secondary (the ticket's split): how much of the
mean curve and of the individual (non-shared) variation does it reproduce?

## Falsified if (decision rule)

**Deciding statistic (primary arm, frozen SyMuPe EncDec-base):** the null-adjusted captured share

ρ = Σ_pieces (C_model − C_null) / Σ_pieces (C_expert − C_null),

over decision pieces that pass QC with at least 82 kept performances and have k > 0 shared
components, where for each piece:
- **C_model**: the share of the reference experts' shared-component variance that lies in the
  span of the model's K = 32 sample curves, centred on their own mean (31 dimensions; the R-07
  (b) statistic, on R-02 curves);
- **C_expert** (expert-as-sampler ceiling): the same statistic for K = 32 held-out real
  performances (disjoint from the reference), averaged over 5 draws;
- **C_null**: the same statistic for envelope surrogates of those held-out performances (each
  curve's spectrum and the per-beat s.d. kept, cross-performer alignment destroyed), averaged over
  the same 5 draws.

ρ = 1 means the model's samples carry the shared components as well as 32 real pianists do; ρ = 0
means no better than smooth curves with the right per-beat spread.

**95% CI:** percentile bootstrap resampling works (each decision piece is its own work: 42 works),
2,000 resamples, seed 0.

**Reading (the plan's thresholds, applied to ρ, whole-CI rule as in R-07 (a) and the R-06 lesson):**
- **supported** (H1b holds): the whole CI is at or above 0.50;
- **falsified**: the whole CI is at or below 0.20;
- otherwise **inconclusive**, reported with the side of the point estimate ("point above 0.50",
  "point at or below 0.20", or between).

Pianist Transformer (secondary) gets the same reading, reported, not deciding. E (R-07
fine-tune) is reported only. If the secondary or the magnitude-aware statistic below disagrees
with the primary reading, the disagreement is reported next to the verdict; it does not change it.

## Reachability check (R-09 lesson; `simulate.py`, `artifacts/sim/`)

On 40 calibration pieces (R-02 pieces of R-07's train / val roles with at least 98 majority-score
performances; seeded draw, seed 20261005), experts only. A synthetic sampler of K curves: a share
f of real held-out performances, the rest replaced by their own envelope surrogates. 10
independent draws per f, each with the reading above (1,000 work resamples). 31 of 40 pieces have
k > 0 (9 have k = 0; median k 3, shared share median 0.37: the R-02 audit's 3 and 0.35 reproduce).

| K = 32 | f = 0 | 0.25 | 0.5 | 0.75 | 1 |
|---|---|---|---|---|---|
| ρ (mean over draws) | 0.00 | 0.48 | 0.74 | 0.90 | 1.01 |
| CI half-width | 0.05 | 0.08 | 0.06 | 0.05 | 0.05 |
| P(supported) | 0.0 | 0.0 | 1.0 | 1.0 | 1.0 |
| P(falsified) | 1.0 | 0.0 | 0.0 | 0.0 | 0.0 |

- Every branch is reachable. A structure-free sampler is read "falsified" every time, a perfect
  sampler "supported" every time, and a sampler at true ρ ≈ 0.48 "inconclusive" every time.
- With a CI half-width of about 0.05-0.08, "supported" needs a true ρ of about 0.56 or more and
  "falsified" a true ρ of about 0.13 or less. True values between are expected to read
  inconclusive. I state this now: an inconclusive result is likely if the model sits near either
  bar.
- The unadjusted ratio is not usable: its structure-free floor is 0.58 at K = 32 (0.47 at K = 16,
  0.64 at K = 48), and "falsified" is unreachable for it at every K.
- **What 0.50 means here.** The span statistic is lenient: f = 0.25 (a quarter of the samples
  carry real shared structure) already gives ρ ≈ 0.48. The magnitude-aware variant (the share
  in the sampler's own top-k principal subspace, null-adjusted the same way) gives 0.32 at
  f = 0.25 and 0.66 at f = 0.5, with wider CIs (about 0.12; P(supported) 0.7 at f = 0.5). It is
  pre-registered as the secondary statistic.
- K: 16, 24, 32 and 48 were simulated. K = 32 is the largest K for which at least 40 unseen
  R10u pieces have N_REF + K performances (42 pieces). It narrows the CI relative to K = 16
  (0.05-0.08 vs 0.07-0.11) and keeps the compute near 10 GPU hours. K = 48 would leave 29 pieces.

## Data

- **PianoCoRe v1.0** (Zenodo 19186016; CC BY-NC-SA 4.0), tier A, refined scores and RAScoP
  alignments, read with `pianolens.data.pianocore` from the R-07 download
  (`C:/Users/Vuduc/r07/data/pianocore`, checksums verified by R-07's `fetch_data.sh`). Majority
  refined score per piece (R-02 rule), all sources (as R-02's cache).
- **Decision set (`pieces.csv`, `set == decision`):** the R10u pieces R-07's split calls unseen (R-02
  piece, no score-paired PERiScoPe v1.0 performance, no possible alias) with at least 82 (= 50 +
  K) tier A performances on the majority score: 42 pieces, 42 works, 6,479 performances, 98,316
  score notes (median 114 performances per piece). Final eligibility is after QC (at least 82
  kept performances); pieces that fail are listed.
- **Calibration set** (`set == calibration`): 40 pieces for the simulation only. **Dry-run set**:
  the two shortest calibration pieces (debussy_l117_no6, chopin_op28_no9).
- Exposure: none of the decision pieces has a score-paired performance in PERiScoPe (SyMuPe's
  training data). Unpaired PERiScoPe performances may exist. Pianist Transformer's pretraining
  corpus is large unpaired MIDI; whether it contains performances of these pieces is not known.
  Neither model was trained with these scores paired, which is what "unseen" means here. E (the
  R-07 fine-tune) never saw R10u.

## Splits

- Pieces: every decision piece is unseen by both frozen models (leave-piece-out by
  construction; there is no training).
- Within a piece: the reference (n = 50, R-02 seed 0) and the held-out ceiling performers (5
  draws of 32 from the remaining kept performances, seeds 1000-1004) are disjoint. The model never
  sees either.
- Performers: PianoCoRe performer ids are mostly unknown (Aria-MIDI transcriptions; in the dry-run
  pieces 18 of 108 and 78 of 160 rows have a known performer). A leave-performer-out analysis is
  therefore not possible here, and none is claimed. The held-out draws are performances.
- Seeds: reference 0; surrogates 0 (PA), 1000-1004 (ceiling and null draws); generation 100, 101;
  bootstrap 0; calibration draw 20261005; simulation draws 5000-5009.

## Baselines and ceilings

- **Ceiling:** the expert-as-sampler C_expert (32 held-out real performances), for the shared
  share, the individual share and the mean-curve R²c.
- **Trivial / null samplers:** envelope surrogates (C_null, used in ρ); smooth noise (Whittaker,
  1.5 bars, no envelope); a random 31-dimensional subspace ((K − 1) / d, exact in expectation).
- **Arm comparison:** pt_frozen − frozen and E − frozen on ρ, paired by piece, same bootstrap.

## Method

Per piece (`r10lib.py`, `job/prep.py`, `job/analyze.py`):
1. **Expert curves exactly as R-02:** note columns as in the PianoCoRe cache
   (`pianocore_cache.aligned_columns`), `match` rows, grace notes excluded; R-02 `curves.py`
   `score_grids` and `grid_curves` (F-03 tempo, 1.5-bar cutoff; raw per-beat velocity).
2. **QC exactly as R-02 `load_blocks`** on all kept performances: beats unobserved in more than
   10% of performances dropped, then performances unobserved on more than 10% of the remaining
   beats; nearest fill; rows centred; velocity Whittaker-smoothed at 1.5 bars.
3. **Reference:** n = 50 kept performances (seed 0). Joint block = [tempo / s_T, velocity / s_V],
   column-centred, s = root mean total variance of each reference block (R-02 `joint`).
4. **Shared components (R-02 audit):** 20 envelope surrogates (phase randomisation with shared
   phases for a row's two blocks, then each beat rescaled to the real per-beat s.d.); k = number of
   leading eigenvalue ratios above the surrogates' 95th percentile. Shared part D_s = projection
   of the reference on its first k components; individual part D_i = the rest.
5. **Model samples:** the whole-piece generation item is the union of matched score notes over all
   majority-score performances, with the median conditioning tempo and velocity (the R-07 rule
   without the 3,000-note cap). Frozen SyMuPe EncDec-base (R-06 adapter via R-07's
   `symupe_eval.py gen`, top-p 0.95), frozen Pianist Transformer (R-07 `pt_train.py eval --job
   gen`, top-p 0.95) and E (R-07 `best.pt`): 2 chunks of 16 samples, seeds 100 and 101,
   concatenated in chunk order. Each sample's onsets and velocities become R-02 curves on the
   expert grid (same function) and the same kept beats, fill and smoothing.
6. **Statistics for every sampler** (model arms, ceiling draws, null draws), in the reference's
   joint units: C_shared (span share of D_s, deciding), C_shared_topk (share in the sampler's own
   top-k principal subspace; secondary), C_ind (span share of D_i; the individual part), and the
   mean-curve centred R² of the sampler's mean against the reference mean, per block (tempo,
   velocity).
7. **Summary** (`job/analyze.py`): ρ and its CI and reading per arm; the same for C_shared_topk;
   unadjusted ratios; arm differences; leave-one-work-out range of ρ; the shared / individual /
   mean-curve table (each as a ratio to the ceiling, with CIs); the null levels; per-piece table.

**Shared vs individual (the ticket's split), reported for every arm, not deciding:**
- mean curve: R²c ratio to the ceiling's R²c (negative R²c clipped at 0 in the ratio);
- shared components: ρ (deciding) and the magnitude-aware variant;
- individual part: null-adjusted C_ind ratio. A model is not expected to reproduce individuality;
  a high value would mean its samples vary in the same non-shared directions as real pianists.

## Command

On the RTX 5080 box (Windows, Git Bash; details and estimates in `job/README.md`):
```
cd /c/Personal/pianolens/experiments/2026-10-05-R-10-h1b/job
bash setup.sh
R07_HOME=/c/Users/Vuduc/r07 bash run.sh      # prep, gen_frozen, gen_E, gen_pt_frozen, analyze
```
Piece list: `python select_pieces.py --pianocore C:/Users/Vuduc/r07/data/pianocore --k 32`.
Simulation: `python job/prep.py --set calibration --out artifacts/calib ...` then
`python simulate.py --boot 1000` (venv-symupe python).

## Compute estimate (RTX 5080, from R-07's measured rates)

- R-07 R10u generation medians at K = 16 on this machine: SyMuPe 0.038 s per note (frozen), 0.041
  (E); Pianist Transformer 0.10 s per note. Both generate in windows, so time is linear in notes
  and VRAM does not depend on piece length.
- 98,316 notes x 2 chunks: frozen about 2.1 h, E about 2.2 h, Pianist Transformer about 5.5 h.
  **About 10 GPU hours in all.** prep about 35 min of CPU at 3 workers (measured: 11,692
  calibration performances took 64 min), analyze minutes.
- VRAM: SyMuPe a few GB; Pianist Transformer 11-14 GB at 16 samples (R-07), so it runs alone. The
  job waits for 12 GB of free VRAM before starting it and never touches other processes. No
  cloud needed.

## Threats to validity

- **Transcribed MIDI.** Nearly all decision performances are audio transcriptions; transcription
  noise inflates the individual part of real performances but not of model samples. That can
  make model samples look *more* concentrated than real ones; ρ above 1 is possible.
- **Single conditioning.** All samples use one median tempo and velocity; real performers differ
  in global tempo. The curves are tempo ratios and centred velocities, so the global level drops
  out, but tempo-dependent shaping does not.
- **Span leniency.** C_shared asks whether the shared directions are present in the samples at
  all, not in what proportion (see the simulation). The top-k variant is reported for this reason.
- **Selection by performance count.** Pieces with at least 82 performances are popular pieces;
  the result may not hold for rarely recorded repertoire.
- **Exposure.** "Unseen" means no score-paired training data; unpaired performances of these
  pieces may have been in either model's pretraining.
- **k = 0 pieces** (about 22% in calibration) drop out of ρ; their count is reported.

## Dry run (CPU, 2026-10-05; pipeline check, not results)

The pre-registration is everything above this heading: sha256
`f3ebdd9f20a2909bd46345977dae50c23de9fbd3c0946c1ceccdb4f94a1571ed` (`head -n <line before
"## Dry run"> README.md | sha256sum`).

`DRY_RUN=1 R07_HOME=/c/Users/Vuduc/r07 bash job/run.sh` on the CPU: the 2 dry-run calibration
pieces (not decision pieces), K = 4 as 2 chunks of 2, 200 bootstrap resamples, output in
`artifacts/dryrun/`. Stages: prep (16 s) -> gen frozen, E, pt_frozen (about 1.5, 1.5 and 3 min
per chunk on CPU) -> analyze. Checks that passed:
- every arm wrote both chunks for both pieces ("missing chunk outputs after this pass: 0");
- a second `gen_frozen` pass skipped everything ("0 items"), so the job resumes;
- model sample curves have no missing tempo beats (Tobs 1.000) and plausible scales (tempo
  log-ratio s.d. 0.08-0.33 against 0.11 for the experts of chopin_op28_no9; velocity s.d. 6-14
  MIDI units against 13);
- `per_piece.csv` and `summary.json` hold every statistic, every arm and the reading;
- `job/setup.sh` ran: both venvs torch 2.7.1+cu128 with CUDA, E checkpoint found;
- `select_pieces.py` rerun reproduces `pieces.csv` byte for byte.

Bug found and fixed: `analyze.py` assumed 16 samples per chunk, so with chunks of 2 it read only
the first chunk (2 samples instead of 4). It now takes `--chunk` from `run.sh` and treats an arm
with fewer than K samples as missing. With the full run's chunks of 16 the old code read the
right samples; the fix changes no definition above.

Disclosure: the dry-run summary printed toy numbers (K = 4, 2 calibration pieces, 2 works, so the
"CIs" are meaningless). They are not results and changed nothing.

## Run record


- **2026-10-05 22:13 UTC: full run started** on the RTX 5080 after the lead approved the
  pre-registration (DECISIONS 2026-10-05). Detached driver (setup.sh, then run.sh) at BelowNormal
  CPU priority, with `R07_HOME=C:/Users/Vuduc/r07`, plus a keep-awake helper that exits when the
  R-10 processes end. Setup check: pt venv torch 2.7.1+cu128, CUDA available; E checkpoint found.
  Logs: `C:/Users/Vuduc/r07/logs/r10_*.log`, `r10.status`; job logs in `job/outputs/logs/`.
