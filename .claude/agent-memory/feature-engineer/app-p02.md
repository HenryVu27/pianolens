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
