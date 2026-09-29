# PianoLens local app (P-02)

A small web app that runs on this computer. Pick a piece, upload a recording or MIDI, and read
the practice report with an A/B player for each flagged passage.

## Run it

```
uv sync --extra audio          # soundfile, soxr, pyloudnorm for the clips
uv run python scripts/pianolens_app.py              # opens http://127.0.0.1:8765
uv run python scripts/pianolens_app.py --port 9000 --no-browser
```

Needs on the machine:

- `ffmpeg` and `fluidsynth` (Homebrew) and the S-02 SoundFont, for the comparison clips.
- The PianoCoRe tier A cache (`data/processed/pianocore_A`) and raw zips, and ASAP, for the
  piece list, scores and expert references.
- For audio input only: the Transkun 2.0.1 venv from A-01 at `data/interim/envs/transkun`
  (or set `PIANOLENS_TRANSKUN` to the `transkun` executable). MIDI input does not need it.

No new Python dependencies: the server is the standard library (`http.server`).

## What it does

1. **Piece.** A searchable list of supported pieces: PianoCoRe tier A pieces with at least 50
   cached reference performances (584), plus every ASAP piece (221), with the reference count.
   A piece that is not listed can still be analysed by uploading its MusicXML score; the report
   then has no expert comparison (tier D) and no expert clips.
2. **Upload.** Audio (wav, mp3, m4a, flac) or MIDI. Several files are several takes of the
   same piece; the first is analysed in detail, the others feed the repeated-take checks.
3. **Run.** A background worker per upload: transcribe (audio only) -> align -> features,
   references and report -> comparison clips. Progress is shown per step, and the run can be
   cancelled. The same files with the same settings reuse the stored result.
4. **Results.** What to practise, each item with the A/B player of the passage that covers its
   bars (your recording, you on the reference piano, a typical expert, another expert) and the
   tempo and loudness curves of those bars against the expert band; all passages; and the full
   F-08 report.
5. **History.** Past analyses, with delete.

## What to trust

| Input | Trust | Read with care | Low confidence |
|---|---|---|---|
| Phone or room audio | Timing, tempo | Wrong and missed notes (read against expert recordings transcribed the same way) | Extra notes, dynamics, voicing, pedal |
| Disklavier or key-sensor MIDI | Notes, timing, tempo | Control and shaping measures (not yet validated as skill measures, D-10) | Dynamics when the references for the piece are transcriptions (the report says so) |

Why: A-01 found that phone transcriptions keep onset timing but add many spurious high notes
(15-29% extras on three of Henry's five takes), and that velocity from audio is relative only.
For audio input the app shows wrong plus missed notes instead of the overall error rate. See
`docs/specs/phone-audio-baseline.md` and DECISIONS 2026-09-28 (after A-01).

## Privacy

- The server binds `127.0.0.1` only and makes no network requests; pages, scripts and clips come
  from the server itself (no CDN, no fonts from the web). Requests with a foreign `Host` header
  and cross-site POSTs are refused.
- Uploads, transcriptions, reports and clips live only under `data/interim/app/` (gitignored):
  `jobs/<id>/` per analysis, `scores/` for copied PianoCoRe scores, `catalog.json`.
  Delete an analysis from History to remove its files.
- Reference data (PianoCoRe, ASAP) is non-commercial research data and Henry's recordings are
  personal: never commit, upload or share anything under `data/interim/app/`. Hosting the app
  is a separate owner decision (DECISIONS 2026-09-28, the platform; BL-01).
