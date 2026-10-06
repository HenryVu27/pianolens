#!/usr/bin/env bash
# R-10 env check. R-10 reuses the R-07 environments unchanged (same torch 2.7.1+cu128, SyMuPe
# 13cc57d + EncDec-base 1b942f28, Pianist Transformer 747df2d + weights 8f156820) and the R-07
# data download. If they do not exist yet, create them with the R-07 scripts:
#   bash ../../2026-09-28-R-07-symupe-finetune/job/setup.sh
#   bash ../../2026-09-28-R-07-symupe-finetune/job/setup.sh pt
#   bash ../../2026-09-28-R-07-symupe-finetune/job/fetch_data.sh
# This script only (re)installs the current pianolens into the SyMuPe venv (no dependency
# changes) and prints what will be used.
set -euo pipefail
wpwd() { pwd -W 2>/dev/null || pwd; }
vpy() { if [ -x "$1/bin/python" ]; then echo "$1/bin/python"; else echo "$1/Scripts/python.exe"; fi; }
HERE=$(cd "$(dirname "$0")" && wpwd)
REPO=$(cd "$HERE/../../.." && wpwd)
R07_HOME=${R07_HOME:-$HOME/r07}
R07_OUT=${R07_OUT:-$HERE/../../2026-09-28-R-07-symupe-finetune/job/outputs}
PY=$(vpy "$R07_HOME/venv-symupe")
PYPT=$(vpy "$R07_HOME/venv-pt")
for p in "$PY" "$PYPT" "$R07_HOME/models/EncDec-base" "$R07_HOME/models/pianist-transformer-rendering" \
         "$R07_HOME/src/PianistTransformer" "$R07_HOME/data/pianocore/PianoCoRe-1.0-refined.zip"; do
  [ -e "$p" ] || { echo "missing $p: run the R-07 setup / fetch scripts first" >&2; exit 1; }
done
uv pip install --python "$PY" --no-deps --reinstall-package pianolens "$REPO"
"$PY" -c "import torch, pianolens, symupe; print('symupe venv: torch', torch.__version__, 'cuda', torch.cuda.is_available())"
"$PYPT" -c "import torch; print('pt venv: torch', torch.__version__, 'cuda', torch.cuda.is_available())"
if [ -f "$R07_OUT/symupe_E/ckpt/best.pt" ]; then echo "E checkpoint: $R07_OUT/symupe_E/ckpt/best.pt"
else echo "E checkpoint not found ($R07_OUT/symupe_E/ckpt/best.pt): gen_E will be skipped"; fi
command -v nvidia-smi >/dev/null && nvidia-smi --query-gpu=name,memory.used,memory.total --format=csv
echo "setup check done"
