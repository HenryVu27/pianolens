#!/usr/bin/env bash
# R-07 evaluation. Builds the evaluation sets, runs every arm over them, summarises.
# Runs on the GPU box or the Mac (CPU is enough for P / V / A; R10 sets are heavier).
#
#   bash eval.sh                     # all sets, all arms that have a checkpoint
#   SETS="P" ARMS="frozen E F" bash eval.sh
#   DRY_RUN=1 bash eval.sh           # 2 R10u pieces from the dry-run data, K=2
#
# P / V / A items come from the R-06 artifacts (small derived data; set R06_ART, default the
# repo copy). R10u / R10s items are built from OUT/data (prep_data.py test pieces).
set -euo pipefail
# Windows (Git Bash) support: native Windows paths for Python, and uv venvs keep python in Scripts/.
wpwd() { pwd -W 2>/dev/null || pwd; }
vpy() { if [ -x "$1/bin/python" ]; then echo "$1/bin/python"; else echo "$1/Scripts/python.exe"; fi; }
HERE=$(cd "$(dirname "$0")" && wpwd)
R07_HOME=${R07_HOME:-$HOME/r07}
OUT=${OUT:-$HERE/outputs}
PY=${PY:-$(vpy "$R07_HOME/venv-symupe")}
PYPT=${PYPT:-$(vpy "$R07_HOME/venv-pt")}
R06_ART=${R06_ART:-$HERE/../../2026-09-27-R-06-expression-model-h2h/artifacts}
export R07_SYMUPE_MODEL=${R07_SYMUPE_MODEL:-$R07_HOME/models/EncDec-base}
export R07_PT_MODEL=${R07_PT_MODEL:-$R07_HOME/models/pianist-transformer-rendering}
export R07_PT_REPO=${R07_PT_REPO:-$R07_HOME/src/PianistTransformer}
export PYTHONUNBUFFERED=1 OMP_NUM_THREADS=${OMP_NUM_THREADS:-1}
DEV=${DEV:-$("$PY" -c 'import torch;print("cuda" if torch.cuda.is_available() else "cpu")')}
DRY_RUN=${DRY_RUN:-0}
if [ "$DRY_RUN" = 1 ]; then
  SETS=${SETS:-"R10u"}; ARMS=${ARMS:-"frozen E F pt_frozen pt_E"}; K=2; KT=3; KR=2; LIMIT=2
else
  SETS=${SETS:-"P V A R10u R10s"}; ARMS=${ARMS:-"frozen E F pt_frozen pt_E"}; K=8; KT=16; KR=16
  LIMIT=0
fi
ES="$OUT/eval_sets"; EV="$OUT/eval"; RS="$OUT/results"
mkdir -p "$ES" "$EV" "$RS" "$OUT/logs"

build_set() {
  local s=$1
  [ -f "$ES/$s/manifest.csv" ] && return
  case $s in
    P|V|A) "$PY" "$HERE/make_eval_items.py" --from-r06 "$R06_ART" --set "$s" --out "$ES/$s" \
             --limit "$LIMIT" ;;
    R10u|R10s) "$PY" "$HERE/make_eval_items.py" --from-prep "$OUT/data" --roles "$s" \
             --out "$ES/$s" --limit "$LIMIT" ;;
  esac
}

ckpt_of() {  # arm -> checkpoint path ("" = frozen pretrained)
  case $1 in
    frozen|pt_frozen) echo "" ;;
    E) echo "$OUT/symupe_E/ckpt/best.pt" ;;
    F) echo "$OUT/symupe_F/ckpt/best.pt" ;;
    pt_E) echo "$OUT/pt_E/ckpt/best.pt" ;;
  esac
}

for s in $SETS; do
  build_set "$s" 2>&1 | tee -a "$OUT/logs/eval_build.log"
  # R10 sets: K = 16 samples per piece (H1b preview); P / V / A: K = 8 (as R-06)
  case $s in R10*) KG=$KR ;; *) KG=$K ;; esac
  ARGS=""
  for arm in $ARMS; do
    c=$(ckpt_of "$arm")
    if [ -n "$c" ] && [ ! -f "$c" ]; then echo "skip $arm (no $c)"; continue; fi
    CK=${c:+--ckpt $c}
    D="$EV/$arm/$s"
    case $arm in
      pt*)
        "$PYPT" "$HERE/pt_train.py" eval --job score --items "$ES/$s/items" --out "$D/score" \
          --device "$DEV" $CK
        "$PYPT" "$HERE/pt_train.py" eval --job gen --items "$ES/$s/gen_items" --out "$D/gen" \
          --device "$DEV" --k "$KG" $CK ;;
      F)  # the flat model is only needed for S-LR (teacher-forced scores)
        "$PY" "$HERE/symupe_eval.py" score --items "$ES/$s/items" --out "$D/score" --device "$DEV" $CK ;;
      *)
        "$PY" "$HERE/symupe_eval.py" score --items "$ES/$s/items" --out "$D/score" --device "$DEV" $CK
        "$PY" "$HERE/symupe_eval.py" gen --items "$ES/$s/gen_items" --out "$D/gen" --device "$DEV" \
          --k "$KG" $CK
        # S-TYP reference samples: pre-registered for P and V (and the dry run)
        case $s in P|V) "$PY" "$HERE/symupe_eval.py" typset --items "$ES/$s/items" --out "$D/typset" \
          --device "$DEV" --k "$KT" $CK ;; esac
        if [ "$DRY_RUN" = 1 ]; then "$PY" "$HERE/symupe_eval.py" typset --items "$ES/$s/items" \
          --out "$D/typset" --device "$DEV" --k "$KT" --limit 2 $CK; fi ;;
    esac 2>&1 | tee -a "$OUT/logs/eval_${arm}_$s.log"
    ARGS="$ARGS --arm $arm=$D"
  done
  "$PY" "$HERE/summarize_eval.py" --set "$ES/$s" $ARGS --out "$RS/$s" --primary-arm E \
    2>&1 | tee -a "$OUT/logs/summarize_$s.log"
done
echo "eval.sh finished: $(date -u +%FT%TZ)"
