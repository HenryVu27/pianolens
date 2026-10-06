# R-10 job: H1b on the RTX 5080 (Windows, Git Bash)

Pre-registration, decision rule and piece set: `../README.md`. This folder only runs it.
Data and model weights are CC BY-NC(-SA): `outputs/` is gitignored and never committed.

## What it does

| Stage | Where | Work |
|---|---|---|
| `prep` | CPU (`WORKERS`, below-normal priority) | For each decision piece (`../pieces.csv`, `set == decision`): all tier A performances of the majority refined score from PianoCoRe v1.0, R-02 curves (`outputs/data/curves/`), the score-note beat table (`score_notes/`) and the whole-piece generation item (`gen_items/`; union of matched score notes, median conditioning). |
| `gen_frozen` | GPU | Frozen SyMuPe EncDec-base (primary): K = 32 samples per piece, as 2 chunks of 16 (seeds 100, 101), with R-07's `symupe_eval.py gen` unchanged. |
| `gen_E` | GPU | R-07 fine-tuned E (`best.pt`, step 9,000), same chunks. Reported, not deciding. Skipped if the checkpoint is absent. |
| `gen_pt_frozen` | GPU, **alone** | Frozen Pianist Transformer (secondary), same chunks, with R-07's `pt_train.py eval --job gen`. Waits until at least `PT_MIN_FREE_GB` (12) GB of VRAM is free; it never touches other processes. |
| `analyze` | CPU | Sample curves (R-02 `grid_curves` on the expert grid), per-piece statistics, the pre-registered summary (`outputs/results/`). |

Every per-piece output is skipped when it exists, so rerunning `run.sh` resumes after any stop.
Generation failures (for example CUDA out of memory) write nothing and are redone on the next
pass; each gen stage logs how many chunk outputs are still missing.

## Runtime and VRAM (from R-07's measured rates on this machine)

Decision set: 42 pieces, 98,316 score notes (whole pieces; the largest has about 12,000 notes).
R-07 R10u generation medians, K = 16: SyMuPe 0.038 s per note (frozen) and 0.041 (E); Pianist
Transformer 0.10 s per note (0.095 for pt_E in a clean run). Generation is windowed in both models,
so time is linear in notes and VRAM does not grow with piece length.

| Stage | Estimate |
|---|---|
| prep | about 20-30 min CPU (calibration prep: 11,692 performances took the time in `../README.md`) |
| gen_frozen | 98,316 x 2 x 0.038 s = about 2.1 h |
| gen_E | about 2.2 h |
| gen_pt_frozen | 98,316 x 2 x 0.10 s = about 5.5 h; 11-14 GB VRAM (R-07), must run alone |
| analyze | minutes |
| **total** | **about 10 h of GPU time**, plus prep |

SyMuPe (25 M parameters) needs a few GB at 16 samples and shares the GPU easily. Pianist
Transformer reached 14.5 GB dedicated in R-07 when another process held VRAM, and failed with
out-of-memory while a game held about 5 GB. Do not game during `gen_pt_frozen`.

## Commands

```bash
cd /c/Personal/pianolens/experiments/2026-10-05-R-10-h1b/job
bash setup.sh                                    # checks the R-07 envs, reinstalls pianolens
R07_HOME=/c/Users/Vuduc/r07 bash run.sh          # prep, gen_frozen, gen_E, gen_pt_frozen, analyze
```

One stage at a time, e.g. `STAGES="gen_pt_frozen" R07_HOME=/c/Users/Vuduc/r07 bash run.sh`.
Long runs: start from a detached shell (R-07 lost launching shells under memory pressure); the
Python processes write their own logs to `outputs/logs/`.

Dry run (CPU, 2 calibration pieces, K = 4, all stages, writes to `../artifacts/dryrun/`):

```bash
DRY_RUN=1 R07_HOME=/c/Users/Vuduc/r07 bash run.sh
```

## Files

| File | Env | Role |
|---|---|---|
| `setup.sh`, `run.sh` | Git Bash | entry points |
| `prep.py` | venv-symupe (pianolens installed) | expert curves, beat table, generation items |
| `analyze.py` | venv-symupe | sample curves, statistics, summary |
| `../r10lib.py` | venv-symupe | shared definitions (R-02 curves, envelope PA, captured shares, reading) |
| R-07 `symupe_eval.py`, `pt_train.py` | venv-symupe / venv-pt | generation, unchanged |
