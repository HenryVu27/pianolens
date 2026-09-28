# Annotation task: phrase boundaries and cadences

You will read five text renderings of piano movements (`R1.txt` to `R5.txt`). For each movement, mark where each phrase starts and ends, and name the cadence that
closes each phrase. You may also mark cadences that do not end a phrase. Work from the music in the rendering alone.

## Rules

- Read only the files in this folder: this file, `SCHEMA.json` and `R1.txt`..`R5.txt`.
  Do not open any other file on the computer, do not search the web, and do not use any tool
  that looks up the music. If you recognise a piece, say so in `recognised_piece`, but still
  annotate from the rendering, not from memory of an analysis.
- Do one pass per movement. There is no feedback and no second attempt.
- Each file starts with a legend that explains the format. Read it first.

## What to mark

- **Phrase:** a musical unit that closes with a cadence (or, rarely, a clear arrival without a
  standard cadence). Mark phrases at this level. Do not mark shorter segments, such as
  motives or sub-phrases, that do not close with a cadence or arrival.
- **phrase_end:** the onset where the phrase reaches its goal: the arrival of the cadence's
  final chord (for example, the onset of the tonic chord in a dominant-to-tonic cadence, or of
  the dominant chord in a half cadence). Mark the arrival onset, not the last note of the
  phrase and not the end of the bar, even if notes continue after the arrival.
- **phrase_start:** the first onset of the phrase, including any upbeat (anacrusis) notes
  that lead into it.
- **Overlap (elision):** when the arrival of one phrase is also the first onset of the next,
  put a `phrase_end` and a `phrase_start` at the same bar and beat.
- **Cadence types** (for `phrase_end` events):
  - `PAC` perfect authentic cadence: dominant to tonic, both chords in root position, and the
    top voice ends on the tonic note.
  - `IAC` imperfect authentic cadence: dominant to tonic, but the top voice ends on the third
    or fifth of the chord, or one of the two chords is inverted.
  - `HC` half cadence: the phrase ends on the dominant chord.
  - `DC` deceptive cadence: the dominant resolves to a chord other than the tonic (e.g. the
    submediant) where a tonic arrival was expected.
  - `EC` evaded cadence: the expected cadential arrival is avoided, and the music restarts or
    moves on at the moment the arrival was due. Mark the event where the arrival was due.
  - `none`: the phrase ends without one of the above.
  Keys change during a movement. Judge each cadence in the key that is in force at that point.
- **cadence (without a phrase end):** a cadence after which the phrase does not end but goes
  on to a later cadence (deceptive and evaded cadences often work this way). Mark it as a
  `cadence` event with its type, at the onset where the arrival happens or was due. Do not
  add a `cadence` event at a position where you already put a `phrase_end`.
- **Repeated bars.** The rendering prints some bars as "same notes and markings as bar(s) ...".
  Annotate only the bars that are printed in full: every event you place in a printed bar is
  copied automatically to the bars that repeat it. If a boundary falls in a repeated bar but
  **not** in the bar it repeats (for example, where a repeat joins the following music), add
  that event at the repeated bar's own number.
- **Positions.** `bar` is the running number after `BAR` in the rendering (not the "score"
  number). `beat` is the beat position exactly as printed at the start of the onset line
  (e.g. `1`, `"2+1/2"`, or `2.5`). Events should sit on onsets that appear in the rendering.
- **confidence:** your probability, from 0 to 1, that the event is correct at this position.

## How to work

1. Read the legend and the whole movement once, to get the keys, sections and repeats.
2. Then go through it in order and write the events. Keep the list sorted by bar and beat.
3. Check: every phrase start (after the first) should follow a phrase end, and every phrase
   end should close a phrase that started earlier. The first onset of the movement starts
   the first phrase.

## Output

For each movement, write one JSON file named `R1.json` .. `R5.json` that follows
`SCHEMA.json`, for example:

```json
{
  "movement": "R1",
  "recognised_piece": null,
  "notes": "",
  "events": [
    {"bar": 4, "beat": 2, "type": "phrase_start", "cadence": "none", "confidence": 0.9},
    {"bar": 7, "beat": 2, "type": "phrase_end", "cadence": "IAC", "confidence": 0.6},
    {"bar": 7, "beat": 2, "type": "phrase_start", "cadence": "none", "confidence": 0.6}
  ]
}
```

The example shows the format only. Its positions and types are made up and say nothing about
any of the movements.
