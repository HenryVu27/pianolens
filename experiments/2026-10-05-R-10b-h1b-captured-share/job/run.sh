#!/usr/bin/env bash
# R-10 (H1b) job. Resumable: every per-piece output is skipped if it exists; rerun the same
# command after any stop, crash or out-of-memory failure (failed items are simply redone).
#
#   bash run.sh                         # all stages: prep gen_frozen gen_E gen_pt_frozen analyze
#   STAGES="gen_frozen" bash run.sh     # one stage
#   DRY_RUN=1 bash run.sh               # CPU: 2 calibration pieces, K = 4, every stage
#
# Env: R07_HOME (default $HOME/r07: venv-symupe, venv-pt, models, src, data from R-07),
#      R07_OUT (R-07 job outputs, for the fine-tuned E checkpoint), OUT (default job/outputs),
#      DEV (cuda if available), WORKERS (CPU workers for prep / analyze, default 4),
#      PT_MIN_FREE_GB (free VRAM required before Pianist Transformer starts, default 12).
set -euo pipefail
wpwd() { pwd -W 2>/dev/null || pwd; }
vpy() { if [ -x "$1/bin/python" ]; then echo "$1/bin/python"; else echo "$1/Scripts/python.exe"; fi; }
HERE=$(cd "$(dirname "$0")" && wpwd)
EXP=$(cd "$HERE/.." && wpwd)
R07_JOB=$(cd "$HERE/../../2026-09-28-R-07-symupe-finetune/job" && wpwd)
R07_HOME=${R07_HOME:-$HOME/r07}
R07_DATA=${R07_DATA:-$R07_HOME/data}
R07_OUT=${R07_OUT:-$R07_JOB/outputs}
OUT=${OUT:-$HERE/outputs}
WORKERS=${WORKERS:-4}
PT_MIN_FREE_GB=${PT_MIN_FREE_GB:-12}
PY=${PY:-$(vpy "$R07_HOME/venv-symupe")}
PYPT=${PYPT:-$(vpy "$R07_HOME/venv-pt")}
export R07_SYMUPE_MODEL=${R07_SYMUPE_MODEL:-$R07_HOME/models/EncDec-base}
export R07_PT_MODEL=${R07_PT_MODEL:-$R07_HOME/models/pianist-transformer-rendering}
export R07_PT_REPO=${R07_PT_REPO:-$R07_HOME/src/PianistTransformer}
export PYTHONUNBUFFERED=1 OMP_NUM_THREADS=${OMP_NUM_THREADS:-1}
DEV=${DEV:-$("$PY" -c 'import torch;print("cuda" if torch.cuda.is_available() else "cpu")')}
DRY_RUN=${DRY_RUN:-0}

# Pre-registered (README): K = 32 samples per piece and arm, as 2 chunks of 16 (seeds 100, 101;
# fresh draws, R-07 used seed 0); the decision set of ../pieces.csv.
if [ "$DRY_RUN" = 1 ]; then
  K=4; CHUNK=2; SET=dryrun; OUT=${OUT_DRY:-$EXP/artifacts/dryrun}; DEV=cpu; BOOT=200
else
  K=32; CHUNK=16; SET=decision; BOOT=2000
fi
NCH=$(( (K + CHUNK - 1) / CHUNK ))
SEED0=100
STAGES=${STAGES:-"prep gen_frozen gen_E gen_pt_frozen analyze"}
mkdir -p "$OUT/logs"
GI="$OUT/data/gen_items"

log() { echo "[$(date -u +%FT%TZ)] $*" | tee -a "$OUT/logs/run.log"; }

count_missing() {  # arm -> number of missing chunk outputs
  local arm=$1 n=0 c f
  for f in "$GI"/*.npz; do
    for ((c = 0; c < NCH; c++)); do
      [ -f "$OUT/gen/$arm/c$c/$(basename "$f")" ] || n=$((n + 1))
    done
  done
  echo $n
}

gen_symupe() {  # arm ckpt-or-empty
  local arm=$1 ck=${2:-} c
  if [ -n "$ck" ] && [ ! -f "$ck" ]; then log "skip $arm: no checkpoint $ck"; return; fi
  for ((c = 0; c < NCH; c++)); do
    log "gen $arm chunk $c (k=$CHUNK seed $((SEED0 + c)))"
    "$PY" "$R07_JOB/symupe_eval.py" gen --items "$GI" --out "$OUT/gen/$arm/c$c" \
      --device "$DEV" --k "$CHUNK" --seed $((SEED0 + c)) ${ck:+--ckpt "$ck"} \
      2>&1 | tee -a "$OUT/logs/gen_${arm}_c$c.log"
  done
  log "$arm: missing chunk outputs after this pass: $(count_missing "$arm")"
}

wait_vram() {  # Pianist Transformer needs about 11-14 GB at 16 samples (R-07); run it alone
  [ "$DEV" = cuda ] || return 0
  command -v nvidia-smi >/dev/null || return 0
  while true; do
    local free
    free=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits | head -1 | tr -d ' ')
    if [ "$free" -ge $((PT_MIN_FREE_GB * 1024)) ]; then log "free VRAM ${free} MiB: start PT"; return; fi
    log "free VRAM ${free} MiB < ${PT_MIN_FREE_GB} GB: waiting 5 min (nothing else is touched)"
    sleep 300
  done
}

gen_pt() {
  local c
  wait_vram
  for ((c = 0; c < NCH; c++)); do
    log "gen pt_frozen chunk $c (k=$CHUNK seed $((SEED0 + c)))"
    "$PYPT" "$R07_JOB/pt_train.py" eval --job gen --items "$GI" --out "$OUT/gen/pt_frozen/c$c" \
      --device "$DEV" --k "$CHUNK" --seed $((SEED0 + c)) 2>&1 | tee -a "$OUT/logs/gen_pt_frozen_c$c.log"
  done
  log "pt_frozen: missing chunk outputs after this pass: $(count_missing pt_frozen)"
}

for S in $STAGES; do
  case $S in
    prep)
      log "prep set=$SET"
      "$PY" "$HERE/prep.py" --pianocore "$R07_DATA/pianocore" --pieces "$EXP/pieces.csv" \
        --set "$SET" --out "$OUT/data" --workers "$WORKERS" 2>&1 | tee -a "$OUT/logs/prep.log" ;;
    gen_frozen) gen_symupe frozen ;;
    gen_E) gen_symupe E "$R07_OUT/symupe_E/ckpt/best.pt" ;;
    gen_pt_frozen) gen_pt ;;
    analyze)
      log "analyze K=$K"
      "$PY" "$HERE/analyze.py" --data "$OUT/data" --gen "$OUT/gen" --pieces "$EXP/pieces.csv" \
        --set "$SET" --arms frozen pt_frozen E --k "$K" --chunk "$CHUNK" --out "$OUT/results" \
        --workers "$WORKERS" --boot "$BOOT" 2>&1 | tee -a "$OUT/logs/analyze.log" ;;
    *) echo "unknown stage $S" >&2; exit 2 ;;
  esac
done
log "run.sh finished: stages=$STAGES"
