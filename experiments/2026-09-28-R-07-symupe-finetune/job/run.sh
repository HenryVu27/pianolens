#!/usr/bin/env bash
# R-07 training entry point. Resumable: every stage writes a done marker; `train*` stages resume
# from their last checkpoint. Re-run the same command after any interruption.
#
#   bash run.sh                      # primary arm: prep, tokenize, train E, tokenize F, train F
#   STAGES="calibrate" bash run.sh   # 30 timed steps on the GPU -> projected hours (do first)
#   STAGES="tokenize_pt train_pt" bash run.sh   # secondary arm (Pianist Transformer)
#   DRY_RUN=1 bash run.sh            # tiny CPU run (Mac): prep -> train 3 steps -> stop ->
#                                    # resume to 6 -> F 4 steps -> PT 2 steps
# Env: R07_HOME ($HOME/r07), R07_DATA ($R07_HOME/data), OUT (job/outputs), WORKERS (8)
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
R07_HOME=${R07_HOME:-$HOME/r07}
R07_DATA=${R07_DATA:-$R07_HOME/data}
OUT=${OUT:-$HERE/outputs}
WORKERS=${WORKERS:-8}
PY=${PY:-$R07_HOME/venv-symupe/bin/python}
PYPT=${PYPT:-$R07_HOME/venv-pt/bin/python}
export R07_SYMUPE_MODEL=${R07_SYMUPE_MODEL:-$R07_HOME/models/EncDec-base}
export R07_PT_MODEL=${R07_PT_MODEL:-$R07_HOME/models/pianist-transformer-rendering}
export R07_PT_REPO=${R07_PT_REPO:-$R07_HOME/src/PianistTransformer}
export PYTHONUNBUFFERED=1 OMP_NUM_THREADS=${OMP_NUM_THREADS:-1}
DRY_RUN=${DRY_RUN:-0}
mkdir -p "$OUT/logs"

if [ "$DRY_RUN" = 1 ]; then
  STAGES=${STAGES:-"prep tokenize train tokenize_flat train_flat tokenize_pt train_pt"}
  PREP_ARGS="--dry-run --workers 4"
  E_ARGS="--device cpu --fp32 --workers 1 --max-steps 6 --micro-batch 2 --accum 2 --eval-every 3 \
    --ckpt-every 2 --log-every 1 --max-val-windows 8 --warmup 2"
  F_ARGS="$E_ARGS --max-steps 4"
  PT_ARGS="--device cpu --fp32 --workers 0 --max-steps 2 --micro-batch 1 --accum 1 --eval-every 2 \
    --ckpt-every 1 --log-every 1 --max-val-windows 2 --warmup 1"
  TOK_WORKERS=2
else
  STAGES=${STAGES:-"prep tokenize train tokenize_flat train_flat"}
  PREP_ARGS="--workers $WORKERS"
  # Pre-registered recipe (README): 30k steps max, 64 windows x 256 notes per step, bf16,
  # AdamW lr 1e-4, 500 warmup, cosine to 10%, eval every 1k on the val pieces, patience 5.
  E_ARGS="--max-steps 30000 --micro-batch 32 --accum 2 --workers 6 --eval-every 1000 --ckpt-every 500"
  F_ARGS="--max-steps 5000 --micro-batch 32 --accum 2 --workers 6 --eval-every 500 --ckpt-every 250"
  PT_ARGS="--max-steps 8000 --micro-batch 2 --accum 16 --workers 4 --eval-every 500 --ckpt-every 250"
  TOK_WORKERS=$WORKERS
fi

stage() {  # name command...
  local name=$1; shift
  if [ -f "$OUT/.done_$name" ]; then echo "== $name: done (skip)"; return; fi
  echo "== $name: $(date -u +%FT%TZ)"
  "$@" 2>&1 | tee -a "$OUT/logs/$name.log"
  touch "$OUT/.done_$name"
}

for S in $STAGES; do
  case $S in
    prep) stage prep "$PY" "$HERE/prep_data.py" --pianocore "$R07_DATA/pianocore" \
            --asap "$R07_DATA/asap" --out "$OUT/data" $PREP_ARGS ;;
    tokenize) stage tokenize "$PY" "$HERE/symupe_train.py" tokenize --data "$OUT/data" \
            --tokens "$OUT/tokens" --workers "$TOK_WORKERS" ;;
    calibrate) "$PY" "$HERE/symupe_train.py" calibrate --tokens "$OUT/tokens" \
            --out "$OUT/calibrate" $E_ARGS 2>&1 | tee -a "$OUT/logs/calibrate.log" ;;
    train)
      if [ "$DRY_RUN" = 1 ] && [ ! -f "$OUT/symupe_E/ckpt/last.pt" ]; then
        echo "== dry run: train 3 steps, stop (simulated interruption), then resume"
        "$PY" "$HERE/symupe_train.py" train --tokens "$OUT/tokens" --out "$OUT/symupe_E" \
          $E_ARGS --stop-after 3 2>&1 | tee -a "$OUT/logs/train.log"
      fi
      stage train "$PY" "$HERE/symupe_train.py" train --tokens "$OUT/tokens" \
        --out "$OUT/symupe_E" $E_ARGS ;;
    tokenize_flat) stage tokenize_flat "$PY" "$HERE/symupe_train.py" tokenize --flat \
            --data "$OUT/data" --tokens "$OUT/tokens_flat" --workers "$TOK_WORKERS" ;;
    train_flat) stage train_flat "$PY" "$HERE/symupe_train.py" train --tokens "$OUT/tokens_flat" \
            --out "$OUT/symupe_F" $F_ARGS ;;
    tokenize_pt) stage tokenize_pt "$PYPT" "$HERE/pt_train.py" tokenize --data "$OUT/data" \
            --tokens "$OUT/tokens_pt" --workers "$TOK_WORKERS" ;;
    calibrate_pt) "$PYPT" "$HERE/pt_train.py" calibrate --tokens "$OUT/tokens_pt" \
            --out "$OUT/calibrate_pt" $PT_ARGS 2>&1 | tee -a "$OUT/logs/calibrate_pt.log" ;;
    train_pt) stage train_pt "$PYPT" "$HERE/pt_train.py" train --tokens "$OUT/tokens_pt" \
            --out "$OUT/pt_E" $PT_ARGS ;;
    *) echo "unknown stage $S" >&2; exit 2 ;;
  esac
done
echo "run.sh finished: $(date -u +%FT%TZ)"
