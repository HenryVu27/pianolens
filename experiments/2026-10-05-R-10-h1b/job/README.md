# R-10 GPU job: frozen SyMuPe samples on fresh PianoCoRe pieces (H1b)

Self-contained job for Henry's RTX 5080 box. The pre-registration, piece list and decision rules
are in `../README.md`. Nothing here trains a model, spends money or needs credentials. The data
is CC BY-NC-SA 4.0 (research only): keep `outputs/` off git.

It reuses R-07's environments, weights and data on the box (`~/r07`): same pins (torch 2.7.1
cu128, symupe `13cc57d`, `SyMuPe/EncDec-base` at `1b942f28`, Pianist Transformer `747df2d` /
`8f156820`), same PianoCoRe v1.0 copy. Code copied from R-07 (`../../2026-09-28-R-07-symupe-
finetune/job/`, not edited): `setup.sh` (header only changed), `fetch_data.sh` (without (n)ASAP),
the item rules of `prep_data.py` + `make_eval_items.py` (in `build_set.py`), `symupe_eval.py gen`
(in `symupe_gen.py`, top-p passed as `top_p`: SyMuPe ignores `lm_top_p`, see
`../README.md`, Method), `pt_train.py eval` (in `pt_gen.py`), the H1b functions of
`summarize_eval.py` and the audit's B2 script (in `summarize_h1b.py`).

## Before running: the checkout

- The box needs this folder **and** a pianolens checkout that contains origin/main's
  `src/pianolens/data/pianocore.py` temp-file fix (commit 881f9f9). Without it every PianoCoRe
  load fails on Windows (R-07 run record). The Mac tree did not have that fix on 2026-10-05.
- R-06's adapters (`experiments/2026-09-27-R-06-expression-model-h2h/adapters/`) are tracked in
  git and are used unchanged.
- `bash setup.sh` reinstalls the checkout's pianolens into the R-07 venv.

## Stages (`run.sh`; resumable, done markers in `outputs/`)

| Stage | What | Default |
|---|---|---|
| `meta` | `outputs/run_meta.json`: git HEAD, diff hash, torch / CUDA / GPU | yes |
| `sets` | `build_set.py`: fresh set (65 pieces, 1,895 renditions); **digest check against `../pieces/fresh_digest.json`, the job stops on a mismatch** (override `ALLOW_DIGEST_MISMATCH=1`, disclosed); R10u and R10s development sets, digests compared with `../pieces/dev_reference.json` (logged, not fatal; amendment R4) | yes |
| `ridge` | `train_ridge.py`: score-feature ridge on R10u + R10s; compared with the Mac reference (R4, logged) | yes |
| `gen_frozen_p95` | **H1b-consensus arm**: frozen SyMuPe, K = 16, top-p 0.95, seed 0, 65 generation items | yes |
| `gen_frozen_p100` | **H1b-axes arm**: same at top-p 1.0 | yes |
| `dev_r07` | R-10 statistics on R-07's own R10u frozen samples (`R07_OUT`, top-p 0.95), no generation; also `results/r10u_r07_no_overlap` without the R3 pieces | yes, if R-07 outputs exist |
| `summarize` | `summarize_h1b.py` -> `outputs/results/fresh/` (**pre-run amendments A1 + A2 applied: the registered reading**, `summary.json` "headline") and `outputs/results/fresh_as_registered/` (no exclusions, sensitivity); `results/r10u_dev[_no_overlap]/` if `dev_gen` ran | yes |
| `gen_pt` | secondary, non-deciding: frozen Pianist Transformer, K = 16, top-p 1.0 (needs `bash setup.sh pt`) | optional |
| `dev_gen` | development: frozen SyMuPe top-p 1.0 on R10u (91 items) | optional |

Generation stages skip finished items and are marked done only when every item has an output;
rerun the same command after any stop. Failures are listed in `outputs/gen/<arm>/<set>/_log_gen.json`.

## Commands (on the box, Git Bash)

```bash
cd ~/pianolens/experiments/2026-10-05-R-10-h1b/job     # the repo checkout on the box
bash setup.sh                     # R-07 SyMuPe venv; prints "cuda 12.8 available True"
bash fetch_data.sh                # checksums only if ~/r07/data/pianocore is there
bash run.sh                       # default stages; logs in outputs/logs/
# optional, in this order, after the default run:
bash setup.sh pt && STAGES="gen_pt summarize" bash run.sh
STAGES="dev_gen summarize" bash run.sh
```
Set `R07_OUT` if R-07's outputs are not at `../../2026-09-28-R-07-symupe-finetune/job/outputs`.
Close games and other GPU programs before `gen_pt` (R-07: Pianist Transformer generation ran out
of memory while a game held about 5 GB).

Copy back to the Mac (small: results, samples, logs):
```bash
rsync -a gpu-box:~/pianolens/experiments/2026-10-05-R-10-h1b/job/outputs/{results,gen,logs,ridge,run_meta.json} \
  ~/personal/pianolens/experiments/2026-10-05-R-10-h1b/artifacts/outputs/
rsync -a gpu-box:~/pianolens/experiments/2026-10-05-R-10-h1b/job/outputs/sets/ \
  --include='*/' --include='*.json' --include='*.csv' --exclude='*' \
  ~/personal/pianolens/experiments/2026-10-05-R-10-h1b/artifacts/outputs/sets/
```

## Runtime and memory (estimates; the logs give the real rate per item)

Work: 74,262 score notes in the 65 fresh generation items (65,979 in the 59 primary pieces); R10u
development items 131,674 notes. Every item is generated with 16 samples in one batch.

| Stage | Basis of the estimate | Estimate on the 5080 |
|---|---|---|
| `sets` + `ridge` | Mac: fresh set 43 s, R10u 71 s (10 workers); ridge seconds | a few minutes |
| `gen_frozen_p95` | see below | 0.4-3.6 h |
| `gen_frozen_p100` | same | 0.4-3.6 h |
| `dev_r07`, `summarize` | Mac: expert side of the fresh set 22 s | minutes |
| `gen_pt` | R-07 run record: pt_E generation of R10u (91 items, K = 16) took 4.1 h alone on this GPU, about 113 ms per note | about 2.3 h |
| `dev_gen` | 1.8x one fresh sample set | 0.7-6.5 h |

- SyMuPe generation on the GPU was not timed in R-07 (no rate in the committed run record).
  Lower end: the R-06 CPU ratio of Pianist Transformer to SyMuPe generation time (5.7x) applied
  to the box's PT rate gives about 20 ms per note, about 25 min per SyMuPe stage. Upper end: the
  Mac CPU rate measured in the dry run, 130-175 ms per note (one thread), with no GPU
  speed-up: 2.7-3.6 h per stage.
- VRAM: SyMuPe (25 M parameters) with a batch of 16 samples needs little memory (well under the
  2.8 GB its training peak used in R-07). Pianist Transformer generation used up to 14.5 GB in
  R-07 when two evaluation streams shared the card; run it alone.
- Default run (sets, ridge, two SyMuPe stages, summaries): about 1-7 h. With `gen_pt` add about
  2.3 h; with `dev_gen` add 0.7-6.5 h.

## Dry run (Mac CPU)

```bash
cd experiments/2026-10-05-R-10-h1b
export R07_HOME=$PWD/artifacts/dryrun/home TORCH_INDEX=pypi
bash job/setup.sh && bash job/setup.sh pt
export R07_DATA=$HOME/personal/pianolens/data/raw OUT=$PWD/artifacts/dryrun/outputs DRY_RUN=1 \
  R07_OUT=$PWD/../2026-09-28-R-07-symupe-finetune/artifacts/dryrun/outputs
STAGES="meta sets ridge gen_frozen_p95 gen_frozen_p100 gen_pt dev_r07 summarize" bash job/run.sh
```
`DRY_RUN=1` replaces the fresh list with `dryrun_pieces.csv` (2 R10u development pieces, the
same two R-07's dry run used), skips the digest check and the R10u set, trains the ridge on R10s
only, and uses K = 4 for Pianist Transformer. No fresh piece is touched.

## Files

| File | Env | Role |
|---|---|---|
| `setup.sh`, `fetch_data.sh`, `run.sh` | shell | entry points |
| `build_set.py` | symupe venv (pianolens) | PianoCoRe -> evaluation set + digest |
| `symupe_gen.py` | symupe venv | frozen SyMuPe samples, top-p parameter |
| `pt_gen.py` | pt venv | frozen Pianist Transformer samples, top-p parameter |
| `train_ridge.py` | symupe venv (scikit-learn via pianolens) | score-feature ridge baseline |
| `summarize_h1b.py` | symupe venv | every pre-registered statistic and reading; amendment flags `--exclude-pieces`, `--exclude-renditions`, `--sibling-flag` |
| `dryrun_pieces.csv`, `dev_pieces_r10u.csv`, `dev_pieces_r10s.csv` | - | piece lists (from the R-07 split) |
