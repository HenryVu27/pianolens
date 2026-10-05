#!/usr/bin/env bash
# R-07 job env setup. Idempotent. Needs: git, curl, uv (https://docs.astral.sh/uv/), NVIDIA driver
# with CUDA 12.8+ support (RTX 5080 = Blackwell sm_120; older CUDA wheels fail with
# "no kernel image is available").
#
#   bash setup.sh            # SyMuPe env (primary arm) + pinned model weights
#   bash setup.sh pt         # Pianist Transformer env (secondary arm)
#
# Paths (override with env vars):
#   R07_HOME   work dir outside the repo          default: $HOME/r07
#   REPO       the pianolens repo checkout        default: three levels above this file
#   TORCH_INDEX  torch wheel index                default: https://download.pytorch.org/whl/cu128
#                (the Mac dry run sets TORCH_INDEX=pypi: CPU wheels from PyPI)
set -euo pipefail
# Windows (Git Bash) support: native Windows paths for Python, and uv venvs keep python in Scripts/.
wpwd() { pwd -W 2>/dev/null || pwd; }
vpy() { if [ -x "$1/bin/python" ]; then echo "$1/bin/python"; else echo "$1/Scripts/python.exe"; fi; }
ARM=${1:-symupe}
HERE=$(cd "$(dirname "$0")" && wpwd)
REPO=${REPO:-$(cd "$HERE/../../.." && wpwd)}
R07_HOME=${R07_HOME:-$HOME/r07}
TORCH_INDEX=${TORCH_INDEX:-https://download.pytorch.org/whl/cu128}
TORCH_VERSION=2.7.1          # cu128 wheel verified by the Pianist Transformer authors
SYMUPE_COMMIT=13cc57d483d300923cffd70f053581cb0397843c   # symupe 1.1.0, as in R-06
SYMUPE_MODEL_REV=1b942f28c786c62d7b128d752ebccb72c9ddd5d7 # HF SyMuPe/EncDec-base, as in R-06
PT_COMMIT=747df2d12291e37f6638b39f1b71517e579ad48c
PT_MODEL_REV=8f1568201d1ec035c73939d5a67c5168c0b80221     # HF yhj137/pianist-transformer-rendering
mkdir -p "$R07_HOME/src" "$R07_HOME/models"

torch_install() {  # $1 = python of the venv
  if [ "$TORCH_INDEX" = "pypi" ]; then
    uv pip install --python "$1" "torch==$TORCH_VERSION"
  else
    uv pip install --python "$1" "torch==$TORCH_VERSION" --index-url "$TORCH_INDEX"
  fi
}

clone_at() {  # url dir commit
  if [ ! -d "$2/.git" ]; then git clone --quiet "$1" "$2"; fi
  git -C "$2" fetch --quiet origin
  git -C "$2" checkout --quiet "$3"
  echo "$2 at $(git -C "$2" rev-parse HEAD)"
}

hf_snapshot() {  # python repo_id revision dest
  "$1" - "$2" "$3" "$4" <<'PY'
import sys
from huggingface_hub import snapshot_download
p = snapshot_download(sys.argv[1], revision=sys.argv[2], local_dir=sys.argv[3])
print("model", sys.argv[1], "@", sys.argv[2], "->", p)
PY
}

if [ "$ARM" = symupe ]; then
  V="$R07_HOME/venv-symupe"
  [ -d "$V" ] || uv venv --python 3.12 "$V"
  PY=$(vpy "$V")
  torch_install "$PY"
  clone_at https://github.com/ilya16/SyMuPe.git "$R07_HOME/src/SyMuPe" "$SYMUPE_COMMIT"
  # symupe 1.1.0 imports numba without declaring it (R-06)
  uv pip install --python "$PY" --reinstall-package pianolens -e "$R07_HOME/src/SyMuPe" numba "$REPO"
  hf_snapshot "$PY" SyMuPe/EncDec-base "$SYMUPE_MODEL_REV" "$R07_HOME/models/EncDec-base"
  # Windows: symupe imports the Unix-only `resource` module (only to cap memory in its parangonar
  # aligner, which this job never calls). Install a no-op stub instead of patching symupe.
  case "$(uname -s)" in MINGW*|MSYS*|CYGWIN*)
    "$PY" - <<'PY'
import pathlib, sysconfig
p = pathlib.Path(sysconfig.get_paths()["purelib"]) / "resource.py"
p.write_text('"""No-op stub of the Unix `resource` module (R-07 setup.sh, Windows only)."""\n'
             "RLIMIT_AS = 9\nRLIM_INFINITY = -1\n\n\n"
             "def getrlimit(_):\n    return (RLIM_INFINITY, RLIM_INFINITY)\n\n\n"
             "def setrlimit(_, __):\n    pass\n")
print("resource stub ->", p)
PY
  ;; esac
elif [ "$ARM" = pt ]; then
  V="$R07_HOME/venv-pt"
  [ -d "$V" ] || uv venv --python 3.12 "$V"
  PY=$(vpy "$V")
  torch_install "$PY"
  clone_at https://github.com/yhj137/PianistTransformer.git "$R07_HOME/src/PianistTransformer" "$PT_COMMIT"
  uv pip install --python "$PY" "transformers==4.54.0" "miditoolkit==1.0.1" "accelerate==1.10.1" \
    "huggingface_hub>=0.30,<1" numpy pandas pyarrow
  hf_snapshot "$PY" yhj137/pianist-transformer-rendering "$PT_MODEL_REV" \
    "$R07_HOME/models/pianist-transformer-rendering"
else
  echo "unknown arm $ARM" >&2; exit 2
fi

mkdir -p "$R07_HOME/env"
uv pip freeze --python "$PY" > "$R07_HOME/env/freeze-$ARM.txt"
"$PY" - <<'PY'
import torch
print("torch", torch.__version__, "cuda", torch.version.cuda, "available", torch.cuda.is_available())
if torch.cuda.is_available():
    print("device", torch.cuda.get_device_name(0), "capability", torch.cuda.get_device_capability(0))
    x = torch.randn(1024, 1024, device="cuda", dtype=torch.bfloat16)
    print("bf16 matmul ok", float((x @ x).float().abs().mean()) > 0)
PY
echo "setup $ARM done: $PY"
