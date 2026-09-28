---
name: fetch-dataset
description: Procedure for downloading and registering a dataset in PianoLens. Use whenever you add data under data/raw, write a loader, or touch DATASETS.md.
---

# Fetch and register a dataset

1. **Find the canonical source.** Prefer the authors' GitHub, Zenodo or HF over mirrors. Note the
   exact version, tag, commit or record id.
2. **Check the size first.**
   - Use `curl -sIL <url> | grep -i content-length`, the HF API, or the Zenodo record API.
   - Compare with `du -sh data/raw` and the 60 GB budget.
   - Over 5 GB: write the estimate in the ticket and download only the subset you need (MIDI
     rather than audio).
3. **Read the license.** Copy its name into `DATASETS.md`. If it is unclear, write "unclear" and
   add a BACKLOG item. Do not guess.
4. **Download** into `data/raw/<name>/`.
   - Git sources: shallow clone.
   - Archives: keep the archive's sha256 in `DATASETS.md`, then extract.
   - Never modify raw files.
5. **Write the loader** in `src/pianolens/data/<name>.py`.
   - Return the common types.
   - Fill `PieceId`, `PerformerId` and `provenance`.
   - Log (don't crash) on bad files, and count them.
6. **Smoke test** in `tests/data/test_<name>.py`. Skip with a clear reason if the data is absent:
   `pytest.importorskip`-style, with a `data_available` helper.
7. **Register.** Fill the `DATASETS.md` row with counts from the loader, not from the paper.
   Add quirks under per-dataset notes.
8. **Report** what the paper claims vs what you actually loaded, if they differ.
