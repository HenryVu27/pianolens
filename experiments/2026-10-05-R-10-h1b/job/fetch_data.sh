#!/usr/bin/env bash
# R-10: fetch PianoCoRe v1.0 from Zenodo on the GPU box (copy of R-07 job/fetch_data.sh without
# (n)ASAP, which R-10 does not use). Idempotent; verifies sizes and checksums. About 3.8 GB.
# If R-07 already ran on this machine, the files are in $R07_DATA/pianocore and nothing is
# downloaded. License: CC BY-NC-SA 4.0, research use only. Keep off git.
#   R07_DATA  default $HOME/r07/data (shared with R-07)
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
du -sh "$R07_DATA"/pianocore
