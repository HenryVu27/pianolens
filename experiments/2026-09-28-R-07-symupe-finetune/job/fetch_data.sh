#!/usr/bin/env bash
# R-07: fetch the training data from its public sources on the GPU box (do not copy raw data
# from the Mac). Idempotent; verifies sizes and checksums. About 3.8 GB.
#   PianoCoRe v1.0 (Zenodo 19186016): metadata.csv, composers.csv, PianoCoRe-1.0-refined.zip
#   (n)ASAP v2.1 (GitHub CPJKU/asap-dataset @ 4097b45)
# License: both CC BY-NC-SA 4.0, research use only. Keep off git.
#   R07_DATA  default $HOME/r07/data
set -euo pipefail
R07_DATA=${R07_DATA:-$HOME/r07/data}
mkdir -p "$R07_DATA/pianocore"
Z=https://zenodo.org/records/19186016/files
fetch() {  # name size sha256
  local f="$R07_DATA/pianocore/$1"
  if [ -f "$f" ] && [ "$(wc -c < "$f" | tr -d ' ')" = "$2" ]; then echo "have $1"; else
    curl -L --fail --retry 5 -C - -o "$f" "$Z/$1?download=1"
  fi
  local got
  got=$( (command -v sha256sum >/dev/null && sha256sum "$f" || shasum -a 256 "$f") | cut -d' ' -f1)
  [ "$got" = "$3" ] || { echo "CHECKSUM MISMATCH $1: $got" >&2; exit 1; }
  echo "ok $1"
}
fetch metadata.csv 205846408 b26abcd173bc738fb6b76f76050ec05ab01f790c68870b826d21e75cafdb5a70
fetch composers.csv 14718 a95f928c8e6934f520f1a53fbbf44cbf2db99bf859f2c677f66cfbdc1062fa86
fetch PianoCoRe-1.0-refined.zip 3581508325 68f1b182741387eb8c74d98a5805bc382435136e8c9228dabe351627cc74ef0f
A="$R07_DATA/asap"
[ -d "$A/.git" ] || git clone --quiet https://github.com/CPJKU/asap-dataset.git "$A"
git -C "$A" fetch --quiet origin
git -C "$A" checkout --quiet 4097b45757bed854818cf87e77b92323ebf90615
echo "asap at $(git -C "$A" rev-parse HEAD)"
du -sh "$R07_DATA"/*
