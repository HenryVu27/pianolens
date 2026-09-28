#!/usr/bin/env bash
# Download the small labeled sets for D-04 / D-05 into data/raw/<name>/.
# Sizes and licenses were checked on 2026-09-27; see DATASETS.md.
# Idempotent: skips anything already present. Never edits existing raw files.
#
# Usage: bash scripts/download_labeled_sets.sh [name ...]
#   names: expert_novice neuropiano vienna4x22 batik_mozart mazurkabl pianojudges
#          maestro_v3_midi psyllabus majeppa pianocore

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RAW="$ROOT/data/raw"
mkdir -p "$RAW"

zenodo_get() {  # record file dest
  local rec="$1" key="$2" dest="$3"
  if [[ -s "$dest" ]]; then echo "skip $dest"; return; fi
  curl -sSL --retry 5 -C - -o "$dest" \
    "https://zenodo.org/api/records/$rec/files/$(python3 -c 'import sys,urllib.parse;print(urllib.parse.quote(sys.argv[1]))' "$key")/content"
}

shallow_clone() {  # url dest
  if [[ -d "$2/.git" ]]; then echo "skip $2"; return; fi
  git clone --depth 1 "$1" "$2"
}

hf_dataset() {  # repo dest
  if [[ -d "$2" && -n "$(ls -A "$2" 2>/dev/null)" ]]; then echo "skip $2"; return; fi
  uv run --with huggingface_hub python - "$1" "$2" <<'EOF'
import sys
from huggingface_hub import snapshot_download
p = snapshot_download(repo_id=sys.argv[1], repo_type="dataset", local_dir=sys.argv[2])
print("downloaded", p)
EOF
}

do_expert_novice() {  # zenodo 8392772, CC BY-NC-SA 4.0, ~588 MB (WAV + alignments)
  local d="$RAW/expert_novice"; mkdir -p "$d"
  for f in "Recordings and Alignments.zip" "Scores.zip" "self-identified_skill_levels.txt" \
           "evaluation_data_anonymous.csv"; do
    zenodo_get 8392772 "$f" "$d/$f"
  done
  [[ -d "$d/extracted" ]] || { mkdir -p "$d/extracted"; \
    unzip -q "$d/Recordings and Alignments.zip" -d "$d/extracted"; \
    unzip -q "$d/Scores.zip" -d "$d/extracted"; }
}

do_neuropiano() { hf_dataset anusfoil/NeuroPiano-data "$RAW/neuropiano"; }          # MIT, ~205 MB
do_vienna4x22() { shallow_clone https://github.com/CPJKU/vienna4x22 "$RAW/vienna4x22"; }  # CC BY 4.0
do_batik_mozart() {  # CC BY-NC-SA 4.0; annotations submodule = DCMLab/mozart_piano_sonatas
  shallow_clone https://github.com/huispaty/batik_plays_mozart "$RAW/batik_mozart"
  (cd "$RAW/batik_mozart" && git submodule update --init --depth 1)
}
do_mazurkabl() { shallow_clone https://github.com/katkost/MazurkaBL "$RAW/mazurkabl"; }  # CC BY-NC-SA 4.0 (README)
do_pianojudges() { shallow_clone https://github.com/anusfoil/PianoJudges "$RAW/pianojudges"; }  # no license file

do_maestro_v3_midi() {  # CC BY-NC-SA 4.0, MIDI-only zip 58 MB
  local d="$RAW/maestro_v3_midi"; mkdir -p "$d"
  local z="$d/maestro-v3.0.0-midi.zip"
  [[ -s "$z" ]] || curl -sSL --retry 5 -o "$z" \
    https://storage.googleapis.com/magentadata/datasets/maestro/v3.0.0/maestro-v3.0.0-midi.zip
  [[ -d "$d/maestro-v3.0.0" ]] || unzip -q "$z" -d "$d"
}

do_psyllabus() {  # zenodo 14794592, CC BY 4.0; MIDI + labels only (cqt5.zip, 2 GB, skipped)
  local d="$RAW/psyllabus"; mkdir -p "$d"
  for f in new_clean_data.json split_audio.json mid.zip; do zenodo_get 14794592 "$f" "$d/$f"; done
  [[ -d "$d/extracted" ]] || { mkdir -p "$d/extracted"; unzip -q "$d/mid.zip" -d "$d/extracted"; }
}

do_majeppa() {  # HF kkwsts/MAJEPPA-Dataset, license "other / mixed-see-description", ~88 MB
  hf_dataset kkwsts/MAJEPPA-Dataset "$RAW/majeppa"
  local d="$RAW/majeppa"
  [[ -d "$d/extracted" ]] || { mkdir -p "$d/extracted"; \
    unzip -q "$d/performance.zip" -d "$d/extracted"; unzip -q "$d/score.zip" -d "$d/extracted"; }
}

do_pianocore() {  # zenodo 19186016 v1.0, CC BY-NC-SA 4.0. raw-alignments.zip (5.2 GB) skipped.
  local d="$RAW/pianocore"; mkdir -p "$d"
  for f in metadata.csv composers.csv PianoCoRe-1.0-refined.zip PianoCoRe-1.0-raw-midi.zip; do
    zenodo_get 19186016 "$f" "$d/$f"
  done
}

ALL=(expert_novice neuropiano vienna4x22 batik_mozart mazurkabl pianojudges maestro_v3_midi
     psyllabus majeppa pianocore)
for n in "${@:-${ALL[@]}}"; do echo "== $n"; "do_$n"; done
du -sh "$RAW"
