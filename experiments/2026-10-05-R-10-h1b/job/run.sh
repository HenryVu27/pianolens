#!/usr/bin/env bash
# R-10 job entry point (H1b on fresh PianoCoRe pieces, frozen SyMuPe EncDec-base).
# Resumable: every stage writes a done marker; generation stages skip finished items and are
# marked done only when every item has an output. Re-run the same command after any stop.
#
#   bash run.sh                         # default stages (below)
#   STAGES="gen_pt summarize" bash run.sh   # optional secondary arm, then re-summarise
#   DRY_RUN=1 bash run.sh               # Mac CPU: 2 R10u (development) pieces, no fresh piece
#
# Default STAGES: meta sets ridge gen_frozen_p95 gen_frozen_p100 dev_r07 summarize
# Optional:       gen_pt (Pianist Transformer, frozen, top-p 1.0; secondary, non-deciding)
#                 dev_gen (frozen SyMuPe top-p 1.0 on the R10u development set; then summarize)
# Env: R07_HOME ($HOME/r07, the R-07 envs and models), R07_DATA ($R07_HOME/data), OUT
#      (job/outputs), R07_OUT (R-07 job/outputs, for dev_r07), WORKERS (8), DEV (cuda|cpu)
set -euo pipefail
# Windows (Git Bash) support, as R-07: native Windows paths for Python; uv venvs keep python in
# Scripts/.
wpwd() { pwd -W 2>/dev/null || pwd; }
vpy() { if [ -x "$1/bin/python" ]; then echo "$1/bin/python"; else echo "$1/Scripts/python.exe"; fi; }
HERE=$(cd "$(dirname "$0")" && wpwd)
EXP=$(cd "$HERE/.." && wpwd)
R07_HOME=${R07_HOME:-$HOME/r07}
R07_DATA=${R07_DATA:-$R07_HOME/data}
R07_OUT=${R07_OUT:-$EXP/../2026-09-28-R-07-symupe-finetune/job/outputs}
OUT=${OUT:-$HERE/outputs}
WORKERS=${WORKERS:-8}
PY=${PY:-$(vpy "$R07_HOME/venv-symupe")}
PYPT=${PYPT:-$(vpy "$R07_HOME/venv-pt")}
export R07_SYMUPE_MODEL=${R07_SYMUPE_MODEL:-$R07_HOME/models/EncDec-base}
export R07_PT_MODEL=${R07_PT_MODEL:-$R07_HOME/models/pianist-transformer-rendering}
export R07_PT_REPO=${R07_PT_REPO:-$R07_HOME/src/PianistTransformer}
export PYTHONUNBUFFERED=1 OMP_NUM_THREADS=${OMP_NUM_THREADS:-1}
DEV=${DEV:-$("$PY" -c 'import torch;print("cuda" if torch.cuda.is_available() else "cpu")')}
DRY_RUN=${DRY_RUN:-0}
K=16          # pre-registered: K = 16 samples per piece (= the oracle's 16 held-out experts)
SEED=0        # generation seed per item (as R-06 / R-07)
STAGES=${STAGES:-"meta sets ridge gen_frozen_p95 gen_frozen_p100 dev_r07 summarize"}
if [ "$DRY_RUN" = 1 ]; then
  PIECES="$HERE/dryrun_pieces.csv"   # R10u development pieces (R-07 dry-run pieces), not fresh
  RIDGE_SETS="$OUT/sets/r10s_dev"    # disjoint from the dry-run pieces
  KPT=4
else
  PIECES="$EXP/pieces/fresh_pieces.csv"
  RIDGE_SETS="$OUT/sets/r10u_dev $OUT/sets/r10s_dev"
  KPT=$K
fi
SETS="$OUT/sets"; GEN="$OUT/gen"; RES="$OUT/results"
mkdir -p "$OUT/logs" "$SETS" "$GEN" "$RES"

stage() {  # name command...
  local name=$1; shift
  if [ -f "$OUT/.done_$name" ]; then echo "== $name: done (skip)"; return; fi
  echo "== $name: $(date -u +%FT%TZ)"
  "$@" 2>&1 | tee -a "$OUT/logs/$name.log"
  touch "$OUT/.done_$name"
}

gen_complete() {  # items_dir out_dir -> 0 if every item has an output
  local n_in n_out
  n_in=$(ls "$1"/*.npz 2>/dev/null | wc -l | tr -d ' ')
  n_out=$(ls "$2"/*.npz 2>/dev/null | grep -v '\.tmp\.npz$' | wc -l | tr -d ' ')
  echo "items $n_in, outputs $n_out"
  [ "$n_in" -gt 0 ] && [ "$n_in" = "$n_out" ]
}

gen_stage() {  # name python script items out extra-args...
  local name=$1 py=$2 script=$3 items=$4 out=$5; shift 5
  if [ -f "$OUT/.done_$name" ]; then echo "== $name: done (skip)"; return; fi
  echo "== $name: $(date -u +%FT%TZ)" | tee -a "$OUT/logs/$name.log"
  "$py" "$HERE/$script" --items "$items" --out "$out" --device "$DEV" --seed "$SEED" "$@" \
    2>&1 | tee -a "$OUT/logs/$name.log"
  if gen_complete "$items" "$out"; then touch "$OUT/.done_$name"
  else echo "!! $name incomplete (failed items are listed in $out/_log_gen.json); rerun" >&2; fi
}

build() {  # name pieces_csv
  [ -f "$SETS/$1/digest.json" ] && { echo "have set $1"; return; }
  "$PY" "$HERE/build_set.py" --pieces "$2" --pianocore "$R07_DATA/pianocore" \
    --out "$SETS/$1" --workers "$WORKERS"
}

check_digest() {
  "$PY" - "$SETS/fresh/digest.json" "$EXP/pieces/fresh_digest.json" <<'PY'
import json, sys
got, want = (json.load(open(p)) for p in sys.argv[1:3])
ok = got == want
print("fresh set digest", "MATCHES" if ok else "DIFFERS", "the Mac pre-registration copy")
if not ok:
    print("got ", json.dumps(got)); print("want", json.dumps(want))
    sys.exit(0 if __import__("os").environ.get("ALLOW_DIGEST_MISMATCH") == "1" else 3)
PY
}

dev_check() {  # amendment R4: development-set digests and ridge vs the Mac reference (not fatal)
  "$PY" - "$EXP/pieces/dev_reference.json" "$SETS" "$OUT/ridge/ridge.json" "$1" <<'PY'
import json, os, sys
ref = json.load(open(sys.argv[1])); sets, ridge, what = sys.argv[2], sys.argv[3], sys.argv[4]
if what == "sets":
    for name in ("r10u_dev", "r10s_dev"):
        p = os.path.join(sets, name, "digest.json")
        if os.path.exists(p):
            ok = json.load(open(p)) == ref[f"{name}_digest"]
            print(f"R4: {name} digest", "MATCHES" if ok else "DIFFERS (logged, not fatal)",
                  "the Mac reference")
else:
    got = {k: v for k, v in json.load(open(ridge)).items() if k != "sets"}
    want = ref["ridge"]
    ok = (got["n_pieces"] == want["n_pieces"] and got["n_works"] == want["n_works"]
          and got["alpha"] == want["alpha"]
          and all(abs(got["cv_r"][t] - want["cv_r"][t]) < 1e-6 for t in want["cv_r"]))
    print("R4: ridge", "MATCHES" if ok else "DIFFERS (logged, not fatal)", "the Mac reference")
    if not ok:
        print("got ", json.dumps(got)); print("want", json.dumps(want))
PY
}

# Pre-run amendments A1 / A2 / A4 (README, below "Run record"): applied by the summariser.
AMEND="--exclude-pieces $EXP/pieces/excluded_content_overlap.csv \
  --exclude-renditions $EXP/pieces/duplicate_renditions.csv"
SIB="--sibling-flag $EXP/pieces/sibling_flag.csv"
R3X="--exclude-pieces $EXP/pieces/r10u_dev_content_overlap_exclude.csv"

for S in $STAGES; do
  case $S in
    meta) stage meta "$PY" - "$OUT/run_meta.json" "$EXP" "$DEV" <<'PY'
import datetime, hashlib, json, platform, subprocess, sys
import torch
out, exp, dev = sys.argv[1:4]
def git(*a):
    try:
        return subprocess.run(["git", "-C", exp, *a], capture_output=True, text=True,
                              check=True).stdout
    except Exception as e:  # noqa: BLE001
        return f"n/a ({e!r})"
meta = {"utc": datetime.datetime.now(datetime.UTC).isoformat(), "platform": platform.platform(),
        "python": sys.version.split()[0], "torch": torch.__version__,
        "cuda": torch.version.cuda, "device": dev,
        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "git_head": git("rev-parse", "HEAD").strip(),
        "git_diff_sha256": hashlib.sha256(git("diff", "HEAD").encode()).hexdigest(),
        "job_files_sha256": {f.name: hashlib.sha256(f.read_bytes()).hexdigest()
                             for f in sorted(__import__("pathlib").Path(exp, "job").iterdir())
                             if f.suffix in (".py", ".sh", ".csv")},
        "pieces_sha256": {f.name: hashlib.sha256(f.read_bytes()).hexdigest()
                          for f in sorted(__import__("pathlib").Path(exp, "pieces").iterdir())}}
open(out, "w").write(json.dumps(meta, indent=1)); print(json.dumps(meta, indent=1))
PY
      ;;
    sets) if [ ! -f "$OUT/.done_sets" ]; then
            echo "== sets: $(date -u +%FT%TZ)"
            { build fresh "$PIECES"
              [ "$DRY_RUN" = 1 ] || check_digest
              [ "$DRY_RUN" = 1 ] || build r10u_dev "$HERE/dev_pieces_r10u.csv"
              build r10s_dev "$HERE/dev_pieces_r10s.csv"
              [ "$DRY_RUN" = 1 ] || dev_check sets; } 2>&1 | tee -a "$OUT/logs/sets.log"
            touch "$OUT/.done_sets"
          else echo "== sets: done (skip)"; fi ;;
    ridge) stage ridge "$PY" "$HERE/train_ridge.py" --sets $RIDGE_SETS \
             --out "$OUT/ridge/ridge.npz"
           [ "$DRY_RUN" = 1 ] || dev_check ridge 2>&1 | tee -a "$OUT/logs/ridge.log" ;;
    # primary H1b-consensus samples: top-p 0.95 (R-06 / R-07, package default)
    gen_frozen_p95) gen_stage gen_frozen_p95 "$PY" symupe_gen.py "$SETS/fresh/gen_items" \
                      "$GEN/frozen_p95/fresh" --k "$K" --top-p 0.95 ;;
    # H1b-axes samples: top-p 1.0 (DECISIONS 2026-10-05)
    gen_frozen_p100) gen_stage gen_frozen_p100 "$PY" symupe_gen.py "$SETS/fresh/gen_items" \
                       "$GEN/frozen_p100/fresh" --k "$K" --top-p 1.0 ;;
    gen_pt) gen_stage gen_pt "$PYPT" pt_gen.py "$SETS/fresh/gen_items" \
              "$GEN/pt_frozen_p100/fresh" --k "$KPT" --top-p 1.0 ;;
    dev_gen) gen_stage dev_gen "$PY" symupe_gen.py "$SETS/r10u_dev/gen_items" \
               "$GEN/frozen_p100/r10u_dev" --k "$K" --top-p 1.0 ;;
    dev_r07)  # R-07's own R10u frozen samples (top-p 0.95, K = 16) under the R-10 statistics
      if [ -d "$R07_OUT/eval/frozen/R10u/gen" ]; then
        MINR=20; [ "$DRY_RUN" = 1 ] && MINR=3
        stage dev_r07 "$PY" "$HERE/summarize_h1b.py" --set "$R07_OUT/eval_sets/R10u" \
          --arm "frozen_r07_p95=$R07_OUT/eval/frozen/R10u/gen" --primary-arm frozen_r07_p95 \
          --min-renditions "$MINR" --out "$RES/r10u_r07"
        # amendment R3: without the R10u pieces whose scores contain PERiScoPe-paired music
        stage dev_r07_no_overlap "$PY" "$HERE/summarize_h1b.py" \
          --set "$R07_OUT/eval_sets/R10u" $R3X \
          --arm "frozen_r07_p95=$R07_OUT/eval/frozen/R10u/gen" --primary-arm frozen_r07_p95 \
          --min-renditions "$MINR" --out "$RES/r10u_r07_no_overlap"
      else echo "== dev_r07: no R-07 outputs at $R07_OUT (skip)"; fi ;;
    summarize)
      ARMS="--arm frozen_p95=$GEN/frozen_p95/fresh"
      [ -d "$GEN/frozen_p100/fresh" ] && ARMS="$ARMS --arm frozen_p100=$GEN/frozen_p100/fresh"
      [ -d "$GEN/pt_frozen_p100/fresh" ] && ARMS="$ARMS --arm pt_frozen=$GEN/pt_frozen_p100/fresh"
      rm -f "$OUT/.done_summarize" "$OUT/.done_summarize_as_registered"
      # registered reading, with the pre-run amendments A1 + A2 applied
      stage summarize "$PY" "$HERE/summarize_h1b.py" --set "$SETS/fresh" $ARMS $AMEND $SIB \
        --ridge "$OUT/ridge/ridge.npz" --primary-arm frozen_p95 --meta "$PIECES" \
        --out "$RES/fresh"
      # sensitivity: the set as registered (no exclusions)
      stage summarize_as_registered "$PY" "$HERE/summarize_h1b.py" --set "$SETS/fresh" $ARMS \
        $SIB --ridge "$OUT/ridge/ridge.npz" --primary-arm frozen_p95 --meta "$PIECES" \
        --out "$RES/fresh_as_registered"
      if [ -d "$GEN/frozen_p100/r10u_dev" ]; then
        rm -f "$OUT/.done_summarize_dev" "$OUT/.done_summarize_dev_no_overlap"
        stage summarize_dev "$PY" "$HERE/summarize_h1b.py" --set "$SETS/r10u_dev" \
          --arm "frozen_p100=$GEN/frozen_p100/r10u_dev" --primary-arm frozen_p100 \
          --out "$RES/r10u_dev"
        stage summarize_dev_no_overlap "$PY" "$HERE/summarize_h1b.py" --set "$SETS/r10u_dev" \
          $R3X --arm "frozen_p100=$GEN/frozen_p100/r10u_dev" --primary-arm frozen_p100 \
          --out "$RES/r10u_dev_no_overlap"
      fi
      grep -h '"headline"' "$RES/fresh/summary.json" || true ;;
    *) echo "unknown stage $S" >&2; exit 2 ;;
  esac
done
echo "run.sh finished: $(date -u +%FT%TZ)"
