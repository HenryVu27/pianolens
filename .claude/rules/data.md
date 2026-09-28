---
paths:
  - "data/**"
  - "src/pianolens/data/**"
  - "scripts/download_*"
  - "DATASETS.md"
---

# Data rules

- Every dataset goes under `data/raw/<name>/` and gets a row in `DATASETS.md`. The row records:
  source URL, version or commit or date, license, size on disk, loader, contents and status.
  Use the `fetch-dataset` skill.
- **Size check before download.** Raw data must stay under 60 GB on this Mac (run `du -sh data/raw`).
  Anything over 5 GB needs a note in the ticket before it starts. Audio corpora do not come here.
- Loaders return the types in `src/pianolens/data/types.py`. They never return dataset-specific
  shapes to callers.
- **IDs:** `PieceId` is canonical across datasets, so the same Chopin étude from ASAP and from
  PianoCoRe gets the same id. Build the mapping with composer + catalogue number (opus, BWV, K,
  D, WoO) + movement. Keep an explicit mapping table in `data/processed/piece_ids.parquet`.
  Unmatched items keep a dataset-prefixed id.
- **Much of the "MIDI" is transcribed from audio.** Tag every performance with
  `provenance: {disklavier, transcribed, sensor, synthetic}`. Validation that needs exact timing
  uses Disklavier or sensor MIDI only.
- Never modify files under `data/raw/`. Derived data goes to `data/interim/` or `data/processed/`,
  and a script in `scripts/` regenerates it.
- Tests use tiny fixtures under `tests/fixtures/`. Commit those only after checking that the
  license allows redistribution of a short excerpt; otherwise generate synthetic fixtures.
