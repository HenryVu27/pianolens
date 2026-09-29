"""Local web app (P-02): upload a performance, run the pipeline, read the report with A/B clips.

* :mod:`pianolens.app.catalog`: supported pieces (PianoCoRe tier A with at least 50 references,
  plus ASAP) and their scores.
* :mod:`pianolens.app.jobs`: one folder per upload under ``data/interim/app/jobs/``, a worker
  process per run (cancellable), results cached by upload hash.
* :mod:`pianolens.app.pipeline`: the worker (transcribe -> align -> report -> clips).
* :mod:`pianolens.app.results`: practise items joined to comparison clips by bar overlap.
* :mod:`pianolens.app.server`: standard-library HTTP server bound to 127.0.0.1.

Launcher: ``uv run python scripts/pianolens_app.py``. How to run and what to trust:
``docs/APP.md``. Everything stays on this computer: personal recordings and non-commercial
reference data are never uploaded (DECISIONS 2026-09-28, the platform).
"""

from pianolens.app.catalog import Piece, build_catalog, load_catalog
from pianolens.app.jobs import JobSpec, JobStore, Upload, default_root
from pianolens.app.server import App, make_server, serve

__all__ = ["App", "JobSpec", "JobStore", "Piece", "Upload", "build_catalog", "default_root",
           "load_catalog", "make_server", "serve"]
