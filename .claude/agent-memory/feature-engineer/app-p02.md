# P-02 local web app (2026-09-28)

Code: `src/pianolens/app/` (catalog, jobs, pipeline = worker, results, pages, server,
static/app.{css,js}), launcher `scripts/pianolens_app.py`, tests `tests/app/test_app.py`
(6, ~19 s incl. an end-to-end smoke on ASAP SunMeiting08 with max_windows=1), doc `docs/APP.md`.
Data: `data/interim/app/{catalog.json,scores/,jobs/<id>/}`. PERSONAL: jobs hold uploads.

## Design (why)
- Stdlib `ThreadingHTTPServer`, no deps. Multipart via `email.parser.BytesParser(policy=HTTP)`
  (cgi is deprecated). Guards: Host must be 127.0.0.1/localhost:port (DNS rebinding); POST
  with a foreign Origin refused; strict CSP (report iframe gets its own inline-style CSP).
- Worker = subprocess `python -m pianolens.app.pipeline <dir>` in its own session, so cancel =
  killpg (kills Transkun/FluidSynth too). Server writes `worker.pid`; worker owns
  status.json (writing pid into status from the server raced the worker's first write).
  Liveness: `Popen.poll()` when we own the child (os.kill(pid,0) is True for zombies).
- Job id = sha256(spec minus title + upload hashes)[:16]; done/running jobs are reused.
- report_from_files is monolithic, so progress steps are transcribe / align (separate quick
  align as a wrong-piece check) / report / clips. Clip progress parsed from build_comparison's
  log lines ("N windows", "wNN ...").
- Catalog: PianoCoRe cache pieces with n_performances >= 50 (584) + all ASAP (221); one
  score.mxl per PianoCoRe piece in the RAW zip (RAW_PREFIX), copied to app/scores on use.
  ASAP pieces keep the ASAP score (find_score) but take the PianoCoRe title/count. 3 s build,
  cached in catalog.json keyed by source mtimes.
- Player: own JS (template logic copied: bar-anchored position mapping), clips fetched by URL
  and decoded with Web Audio (P-01's player_html embeds base64, not reused). Practise item ->
  window by max bar overlap (indices, not labels). Curves: interpretation.curves
  measure_index == bar index; labels from rep["bars"].
- Audio input: Transkun via the A-01 venv binary (pianolens.audio.transcription has no runner;
  only onset_sanity used), expert check with capture model "Transkun V2". For audio the
  headline is wrong+missed rate (extras dominate error_rate: take 04 39% vs 9.9%).

## Measured
- F-08 (c) MIDI via API: ~20 s total (3 windows). Uploaded-score (no piece) path works: 0 refs,
  user-render clips only (0 windows on deadpan). Cancel mid-report: worker gone, state
  cancelled.
- Henry take 04 (Op. posth) wav via the app: Transkun 10 s (MPS), align 82% matched, report
  20 s, 8 windows / 30 clips in 20 s; ~1 min total. Practise bars 27/41/51 = A-01 report's.

## DF-05 fixes (2026-09-29)
- Job id includes `jobs.code_version()` (sha256 of src/pianolens/**/*.py minus app/server.py,
  app/pages.py, plus `PIPELINE_VERSION`); `ignore_wrong_piece`, title, composer not hashed.
- MIDI can be marked `transcribed:transkun` / `transcribed` (spec.capture_model); pipeline uses
  `transcribed = audio or provenance == "transcribed"` for notes, filter, expert capture model;
  results/JS/history key the wrong+missed headline on `transcribed`, not input_kind.
- Wrong-piece stop: Dice < `pipeline.WRONG_PIECE_MATCH` (0.5) -> state `stopped`,
  `wrong_piece`; POST /api/jobs/<id>/override sets spec flag in job.json and reruns. Measured:
  right 0.818-0.939 (Henry Transkun takes), 0.960-0.984 (ASAP); wrong 0.083-0.314 (32 pairs).
  Scripts in the session scratchpad only (not kept).
- Same-score refs: only key-captured MIDI + n_references == 0 + >= 10 ASAP perfs (4 pieces).
  Trap: PianoCoRe holds all 978 ASAP perfs and build merges same_score_refs into tier D ->
  double count for other pieces; adding ASAP_<stem> to exclude_references would also strip
  them from the expert-check fallback and the correctness refs. Needs a report/ change.
  Haydn 50/1: 17 refs, evenness 5/150 bars tiered, pedal 0; expert check reuses the alignments.
- In-process `pipeline.run(job_dir)` works for tests (needs catalog.json copied into the root).
