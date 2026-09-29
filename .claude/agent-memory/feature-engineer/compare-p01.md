# P-01 A/B comparison engine (2026-09-28)

Code: `src/pianolens/compare/` (windows, timemap, experts, clips, engine, player +
`player_template.html`), tests `tests/compare/test_compare.py` (10, ~17 s), runner
`scripts/build_compare_p01.py [--only 01,a] [--no-henry] [--summarize-only]` ->
`data/interim/compare/<name>/{manifest.json,clips/*.mp3,player.html}` + `checks.json`.
PERSONAL: `henry_*` folders hold Henry's audio. Never commit.

## Design (why)
- Depends on the report JSON only (issues, bars[start_beat,label], input.paths,
  excluded_references), never on report code, so F-08c edits do not break it.
  `inputs_from_report` re-aligns (deterministic) and checks the bar grid vs `_measure_info`.
- Windows: tier, eligible, category, magnitude; merge touching bars up to 4; coalesce after every
  placement (a growing window could reach a later one: overlap bug seen on sample a).
- Time map: chord median -> isotonic -> drop worst knot one at a time (isotonic pooling spreads
  one late knot over neighbours, so a one-shot MAD filter dropped 3 knots for 1 outlier).
- Expert choice: tempo shape + velocity shape (row-centred in window) + tempo level vs column
  median over pre..post bars; contrast = distance nearest the q90.
- Render only an excerpt (6 s lookback, pedal state carried): whole-piece FluidSynth render
  was ~22 s per performance (under load), made sample (a) take 7.8 min; now ~2 min.
- PianoCoRe expert MIDI: `pianolens.data.pianocore.PianoCoRe().load(index row)` (class is
  `PianoCoRe`, not a Loader); ref id `pianocore:<row id>`; refined MIDI carries pedal CCs.
  metadata `performer` is often NaN.
- Score-span check needs a beat tolerance: PDMX MusicXML vs refined MIDI quantise irregular
  tuplets differently (354.9 vs 354.917); exact keys failed bar 60 of Op.27/2 (0.56).
- MP3 via ffmpeg libmp3lame: ffmpeg decode length within 0.7 ms of the clip (gapless header).
- Onset-strength based lags have a constant ~+20 ms bias on renders too (envelope/attack
  latency): judge user audio against the user render (0 ms), not against 0.
- Single nearest-onset checks can pick a neighbouring louder onset (outliers up to 139 ms);
  the onset-train cross-correlation over the whole clip is the robust proxy.
- Headless Chrome screenshot works for the player; `node --check` on the extracted script.
