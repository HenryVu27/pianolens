#!/bin/sh
# R-06: run one model job over all sets. Usage: run_models.sh symupe|pt score|generate [device]
set -e
E=$(cd "$(dirname "$0")" && pwd)
M=$1; J=$2; DEV=${3:-cpu}
if [ "$M" = symupe ]; then PY=$E/envs/symupe-venv/bin/python; AD=$E/adapters/symupe_adapter.py
else PY=$E/envs/pt-venv/bin/python; AD=$E/adapters/pt_adapter.py; fi
for S in P A V; do
  if [ "$J" = score ]; then IN=$E/artifacts/items/$S; else IN=$E/artifacts/gen_items/$S; fi
  $PY $AD $J --device $DEV --items $IN --out $E/artifacts/$M/$J/$S --k 8 --seed 0
done
