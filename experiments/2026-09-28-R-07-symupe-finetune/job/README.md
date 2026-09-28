# R-07 GPU job: fine-tune SyMuPe EncDec-base (and Pianist Transformer) on piece-disjoint PianoCoRe

Self-contained job for Henry's RTX 5080 box (O-03). The pre-registration, split and decision rules
are in `../README.md`. Nothing here spends money or needs credentials. The data is CC BY-NC-SA 4.0
(research only): keep `outputs/` and the weights off git.

## What it does

1. `setup.sh`: two uv venvs under `$R07_HOME` (default `~/r07`), torch 2.7.1 from the **cu128**
   index (the 5080 is Blackwell sm_120 and needs CUDA 12.8+ wheels; older wheels fail with "no
   kernel image is available"), SyMuPe pinned at commit `13cc57d`, Pianist Transformer at
   `747df2d`, model weights pinned by Hugging Face revision. Prints the GPU and runs a bf16 matmul.
2. `fetch_data.sh`: PianoCoRe v1.0 (metadata + refined zip, 3.8 GB, sha256-checked) from Zenodo and
   (n)ASAP at commit `4097b45` from GitHub, into `$R07_DATA` (default `~/r07/data`). Do not copy
   raw data from the Mac.
3. `run.sh`: resumable stages, each logged to `outputs/logs/<stage>.log`, each with a done marker.
   - `prep`: `prep_data.py` builds interchange items with the committed split and **fails on any
     leakage** (`outputs/data/leakage_report.json`).
   - `tokenize`, `train`: SyMuPe fine-tune E (checkpoints `outputs/symupe_E/ckpt/{last,best}.pt`).
   - `tokenize_flat`, `train_flat`: the flat model F for the likelihood-ratio score.
   - `tokenize_pt`, `calibrate_pt`, `train_pt`: Pianist Transformer (secondary arm).
   - `calibrate`: 30 timed steps; writes `outputs/calibrate/calibrate.json` (s/step, peak GB,
     projected hours). Run it first.
4. `eval.sh`: builds the evaluation sets (P / V / A from the R-06 items; R10u / R10s from
   `outputs/data`), runs frozen, E, F, pt_frozen and pt_E, and summarises into `outputs/results/`.

Training is resumable: rerun the same command after any stop (Ctrl-C and SIGTERM checkpoint
first). Every `ckpt_every` steps `last.pt` is replaced atomically.

## Runtime and memory (estimates; `calibrate` replaces them)

| Stage | Size | Expected on the 5080 |
|---|---|---|
| fetch_data | 3.8 GB | download-bound |
| prep | ~48 k items, 12 workers | about 30 min (CPU) |
| tokenize (E, F, PT) | ~66 M notes | CPU; disk: see `outputs/tokens*/` |
| train E | up to 30,000 steps x 64 windows of 256 notes, bf16 | 30,000 x s/step; early stop likely earlier |
| train F | up to 5,000 steps | 5,000 x s/step |
| train PT | up to 8,000 steps x 32 windows of 4,096 tokens, bf16 | 8,000 x s/step (PT) |
| eval | all sets, all arms | hours |

- **VRAM.** SyMuPe (25 M parameters): 32 windows per micro-batch used 6.5 GB fp32 on the Mac CPU
  (R-06), so bf16 at 32 should fit in 16 GB. If `calibrate` shows a peak above 14 GB, add
  `--micro-batch 16 --accum 4` to `E_ARGS` in `run.sh` (same 64 windows per step).
  Pianist Transformer (136 M): batch 2 at 4,096 tokens was 15.4 GB fp32 on MPS; bf16 micro-batch
  2 should fit; fallbacks: `--micro-batch 1 --accum 32`, then `--grad-ckpt`.
- Upper bound from the Mac (R-06 measurements): E 45 h, F 7.5 h on CPU; PT 57 h on MPS. The 5080
  should be much faster; if `calibrate` projects more than about 24 h for E, tell the lead
  (cloud needs O-04 approval).

## Commands (on the GPU box)

```bash
# 0. Copy the repo code (no data): from the Mac
rsync -a --exclude data --exclude '.venv' --exclude 'experiments/*/envs' \
  --exclude 'experiments/*/artifacts' ~/personal/pianolens/ gpu-box:~/pianolens/
# P / V / A evaluation items (small derived data, 97 MB), only if eval runs on the box:
rsync -a ~/personal/pianolens/experiments/2026-09-27-R-06-expression-model-h2h/artifacts/{items,gen_items,manifest.parquet} \
  gpu-box:~/pianolens/experiments/2026-09-27-R-06-expression-model-h2h/artifacts/

# 1. On the box
cd ~/pianolens/experiments/2026-09-28-R-07-symupe-finetune/job
bash setup.sh            # SyMuPe env; prints "cuda 12.8 available True", device, bf16 ok
bash setup.sh pt         # Pianist Transformer env
bash fetch_data.sh
STAGES="prep tokenize" bash run.sh
STAGES=calibrate bash run.sh          # send outputs/calibrate/calibrate.json to the lead
bash run.sh                           # E then F; resumable, safe to rerun
STAGES="tokenize_pt calibrate_pt train_pt" bash run.sh
bash eval.sh                          # or run it on the Mac after copying outputs back

# 2. Copy results back to the Mac
rsync -a gpu-box:~/pianolens/experiments/2026-09-28-R-07-symupe-finetune/job/outputs/ \
  ~/personal/pianolens/experiments/2026-09-28-R-07-symupe-finetune/artifacts/outputs/
```

Use `tmux` or `nohup` for `run.sh` so a dropped SSH session does not stop it.

## Dry run (proves the pipeline end to end on a Mac CPU)

```bash
cd experiments/2026-09-28-R-07-symupe-finetune
export R07_HOME=$PWD/artifacts/dryrun/home TORCH_INDEX=pypi
bash job/setup.sh && bash job/setup.sh pt
export R07_DATA=$HOME/personal/pianolens/data/raw OUT=$PWD/artifacts/dryrun/outputs DRY_RUN=1
bash job/run.sh     # prep (10 pieces) -> tokenize -> train 3 steps -> stop -> resume to 6 -> F -> PT
bash job/eval.sh    # 2 held-out pieces, all arms, K = 2 -> outputs/results/R10u
```

## Files

| File | Env | Role |
|---|---|---|
| `setup.sh`, `fetch_data.sh`, `run.sh`, `eval.sh` | shell | entry points |
| `prep_data.py` | symupe venv (pianolens installed) | PianoCoRe / (n)ASAP -> interchange items; split + leakage check |
| `symupe_train.py` | symupe venv | tokenize / train / calibrate (reuses the R-06 SyMuPe adapter) |
| `pt_train.py` | pt venv | tokenize / train / calibrate / eval for Pianist Transformer (R-06 PT adapter) |
| `trainlib.py` | both | resumable training loop, checkpoints, early stopping |
| `symupe_eval.py` | symupe venv | score / gen / typset with a checkpoint |
| `make_eval_items.py` | symupe venv | evaluation sets with every deadpan / noise variant |
| `summarize_eval.py` | symupe venv | metrics, AUCs, pass / fail reading, H1b preview |
