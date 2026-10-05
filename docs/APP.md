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
2. **Upload.** Audio (wav, mp3, m4a, flac, aac, ogg; anything ffmpeg reads with one of these
   extensions) or MIDI (.mid, .midi). Several files are several takes of the same piece; the
   first is analysed in detail, the others feed the repeated-take checks. For MIDI, say how it
   was recorded. MIDI that a transcriber made from audio can be marked "transcribed" (Transkun
   or another transcriber): it is then read like an audio upload (extra notes low confidence,
   wrong and missed notes checked against expert transcriptions, the optional extra-note
   filter), without the transcription step.
3. **Run.** A background worker per upload: transcribe (audio only) -> quick alignment check ->
   features, references and report -> comparison clips. Progress is shown per step, and the run
   can be cancelled. The same files with the same settings reuse the stored result, as long as
   the analysis code is unchanged: the job id includes a hash of the Python source under
   `src/pianolens` (page-serving modules excepted) and a manual `PIPELINE_VERSION`
   (`app/jobs.py`), so after a code change the same upload runs again. Bump `PIPELINE_VERSION`
   for a change the hash cannot see (a new calibration data file or transcriber).
4. **Wrong-piece check.** The quick alignment of the first take stops the run when fewer than
   half of the notes match the chosen score (Dice match ratio below 0.5), with a message and an
   **Analyse anyway** button; the upload form also has an override for short excerpts. Between
   0.5 and 0.8 the run continues and the report carries a warning. Why 0.5 (measured
   2026-09-29): Henry's five Transkun takes scored 0.818-0.939 on their own score and
   0.163-0.280 on the 20 wrong-score pairs; one ASAP performance each of Chopin Op. 10/3, 10/4,
   10/12 and Beethoven Op. 53/1 scored 0.960-0.984 and 0.083-0.314. An excerpt of a long piece
   also scores low, hence the override.
5. **Results.** What to practise, each item with the A/B player of the passage that covers its
   bars (your recording, you on the reference piano, a typical expert, another expert) and the
   tempo and loudness curves of those bars against the expert band; all passages; and the full
   F-08 report.
6. **History.** Past analyses, with delete.

## What to trust

| Input | Trust | Read with care | Low confidence |
|---|---|---|---|
| Phone or room audio, or MIDI marked transcribed | Timing, tempo | Wrong and missed notes (read against expert recordings transcribed the same way) | Extra notes, dynamics, voicing, pedal |
| Disklavier or key-sensor MIDI | Notes, timing, tempo | Control and shaping measures (not yet validated as skill measures, D-10) | Dynamics when the references for the piece are transcriptions (the report says so) |

Why: A-01 found that phone transcriptions keep onset timing but add many spurious high notes
(extras of 15-29% of score notes on three of Henry's five takes; 3.0-29.3% across all five),
and that velocity from audio is relative only.
For audio input the app shows wrong plus missed notes instead of the overall error rate. See
`docs/specs/phone-audio-baseline.md` and DECISIONS 2026-09-28 (after A-01).

## Why pedal blur and evenness are usually not tiered

The report tiers pedal blur and evenness per bar only against other performances aligned to the
*same* score file on the same repeat path (`same_score_refs` in `report/build.py`, at least 10
of them: `calibration.MIN_TIER_REFERENCES`). PianoCoRe references cannot serve: they are
aligned to PianoCoRe's own scores and carry no pedal. So for most pieces these two measures
are shown with their values but never tiered and never become practise items.

The app supplies same-score references only where that is clean:

- the input is key-captured MIDI (Disklavier, digital piano, unknown or hand-written), because
  the references are ASAP Disklavier MIDI and pedal and velocity from a transcription are not
  comparable with them (A-01);
- the piece has no PianoCoRe references, because the report merges same-score references into
  the tier D expert set and PianoCoRe already contains the ASAP performances (978 of them): for
  any other piece they would be counted twice;
- at least 10 ASAP performances of the piece remain after leaving out excluded ids and any file
  identical to the upload.

Today that is four catalogue pieces: Beethoven Op. 110 mv. 3-4 (11 ASAP performances), Haydn
Sonata 50/1 (18), Liszt's Mephisto Waltz (14) and Ravel's Alborada del gracioso (10, so not
when the upload is one of those ten). Only performances on the upload's repeat path are used, so a piece can still
end up untiered. On Haydn 50/1 (an ASAP performance uploaded as MIDI, 17 references) evenness
tiered 5 of 150 bars and pedal none; the run took no longer than without them, because the
expert check reuses the same alignments. Doing this for every ASAP piece needs a report
change first: skip or de-duplicate PianoCoRe performances whose source is an ASAP performance
already passed as a same-score reference (DEFECTS DF-05).

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
