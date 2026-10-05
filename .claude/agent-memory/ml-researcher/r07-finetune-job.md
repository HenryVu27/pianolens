# R-07 fine-tune job prep (2026-09-28)

Folder: `experiments/2026-09-28-R-07-symupe-finetune/` (README = pre-registration; first 300 lines
hashed: artifacts/prereg_sha256.txt `17dfca04...083b`). Status: prepared, not run (O-03).

## Split (committed `split/pieces.csv`, sha256 3341bfa5...86; `make_split.py`, seed 20260928)
- Unit = work (`expression_split.work_key`: strips _mvN / _prelude / _fugue; pianocore multi-movement
  compositions grouped; asap Haydn -> haydn_hobxviN; hand map Italian concerto -> bach_bwv971, Ravel
  Miroirs 3/4 -> pianocore ids).
- Roles: P, V, A (23 PT test folders' works), R10u (75 works; 76 R-02 pieces with n_periscope_paired==0
  and no alias among 287 unmatched paired PERiScoPe rows), R10s (24 paired R-02 works), val 59 works
  (5% of works with tier A), quarantine 81 ids (catalogue-number aliases of held-out pieces).
- Trap fixed: catalogue ranges ("BWV_846-869") polluted tokens; and a piece's text must be the union
  over datasets + the id itself, or ASAP titles ("Etudes_op_10/3") alias every Op.10 etude.
- PERiScoPe v1.0 metadata: downloaded to artifacts/periscope/ (HF dataset sha 5a637bd9). 46,012/46,473
  rows join PianoCoRe by performance_id (PERiScoPe_<n>, ATEPP_, ASAP_ ids are shared). PianoCoRe
  metadata has its own train/test `split` column (unused).
- Training counts (metadata, before match filter): 1,307 train pieces, 38,902 perfs (cap 50), 70.6 M
  non-interpolated notes; 609 (n)ASAP robust perfs on train pieces. Tier A has no is_duplicate rows;
  exclude performance_dataset=="ASAP" rows (use (n)ASAP GT instead).

## Job (job/): setup.sh (uv, torch 2.7.1 from cu128; TORCH_INDEX=pypi on the Mac), fetch_data.sh,
run.sh (stages, done markers, DRY_RUN=1), eval.sh, trainlib.py (resumable), symupe_train.py,
pt_train.py, symupe_eval.py, make_eval_items.py, summarize_eval.py, prep_data.py.
- SyMuPe training = own loop around gen.prepare_sequence windows (256 notes, SOS/EOS only at true
  ends) + model(**batch).loss with enc_mask/dec_mask and labels padded -100. The package's Trainer
  needs unreleased recipes (scripts/train.py points to ../recipes).
- TokSequence ids int64 / values float64 by default (~460 B/note pickled); int16/float32 compaction
  is lossless for the loss (step-0 val identical) -> 180 B/note.
- DataLoader over an endless IterableDataset hangs the process at exit: call it._shutdown_workers()
  and os._exit(0) at the end of train/calibrate.
- PianoT5GemmaConfig.from_pretrained fails on transformers 4.54 ("multiple values for 'decoder'"):
  load the model and take .config; pass the config to tokenizer workers.
- pt_adapter inserts the R-06 envs repo on sys.path; pre-import src.model.* from R07_PT_REPO first.
- symupe works with torch 2.7.1 + transformers 5.17 (dry run).
- make_window (prepare_sequence) = 0.6 ms per 256-note window on one core: not a bottleneck.

## Typicality scores (pre-registered)
S-RAW (reference), S-LR = l_E - l_F (F trained on flat renditions: legato U(.85,1), noise <=10 ms/4,
no vel offset / tempo change), S-TYP = -sqrt(mean_f z_f^2) vs 16 top-p-1.0 samples under the item's
own conditioning, S-DEV = composite r with flat targets scored 0. Battery = expression_data.VARIANTS.
Pass = R1 (7 deadpan variants: AUC>=.75, CI lb>.5, per-work >=.5 on P) + R2 (jitT20/40, jitV8/16)
+ R3 (point AUC>=.75 on V). R1+R3 without R2 = flatness detector only.
- 2026-10-05 (R-10 dry run): the S-TYP "top-p 1.0" typset samples were really top-p 0.95, because SyMuPe EncDec ignores `lm_top_p` (see library-gotchas). Reported to the lead.
