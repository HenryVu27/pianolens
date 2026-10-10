# PianoLens: can a computer judge piano playing?

A research log of the PianoLens project, written as source material for a blog post. It explains
the question, how the system works, what the experiments found, how the results were checked, and
what is still open. Last rebuilt 2026-09-29.

Every number in this document comes from an experiment folder in `experiments/` or a spec in
`docs/specs/` in the project repository. Where something is a hypothesis or has never been tested,
the text says so.

#### How to read this

- **Part 1** sets up the question and the bets behind the project. Read it first.
- **Part 2** explains how the system works, from a recording to a report, in full technical detail.
  Each chapter stands on its own, so you can skip to the one you care about.
- **Part 3** is what we found, grouped by question rather than by date.
- **Part 4** explains how results were tested, and the cases where testing changed our minds.
- **Part 5** says what works today, what does not, and what comes next.
- The appendix has an index of every experiment, a glossary and instructions for reproducing
  anything.

Experiment ids such as R-03 or F-08c appear throughout. They are only labels for finding the
underlying records; the appendix lists what each one is.

---

## Part 1. The question

### What it would mean to score a performance

Piano apps today can tell you whether you pressed the right key at roughly the right time. That is
useful, but it is not what a teacher listens for. A teacher hears whether a run was even, whether
the melody sang over the accompaniment, whether a phrase had a shape, whether the pedal blurred two
chords together, and whether the whole thing sounded like a considered interpretation or like
someone getting through the notes.

This project treats "how good was that performance" as four layers, each harder than the last:

| Layer | The question it answers | Example of what it catches |
|---|---|---|
| Correctness | Were the right notes played? | A wrong note in bar 12, a skipped bass note |
| Control | Was the playing physically controlled? | An uneven scale, hands not quite together, a pedal held through a chord change |
| Shaping | Does the playing follow the music's structure? | No slowing into a cadence, a phrase with no rise and fall |
| Interpretation | How does it compare with how skilled pianists play this piece? | Rushing a passage that experts almost all take slowly |

The first layer is close to solved. The last is where music becomes subjective, and the central
claim of the project is that "subjective" does not mean "unmeasurable". Individual listeners
disagree, but when many of them rate the same playing, their average judgement has a structure that
can be measured and predicted. Part 3 shows what that structure looks like.

### Why the piano is the right instrument to try this on

The piano is the most constrained instrument there is. When a key is pressed, a hammer is thrown at
the string and leaves it before the note is heard. From then on the player cannot change the sound.
For each note, a pianist controls only three things: when it starts, how hard the key is struck,
and when it is released. Add the pedals and that is the complete list.

That has a big consequence. A MIDI recording of a piano, which stores exactly those things, is a
near-complete description of the performance. A violinist's vibrato or a singer's tone cannot be
reduced like this. And because a written score says what notes should be played, every difference
between the score and the performance can be measured: this note came 40 milliseconds late, this
chord was louder than the one before, this phrase slowed down at its end.

So the bet is that piano quality can be explained with a modest number of measurable features and a
small model, without a giant audio network that nobody can inspect.

### What already existed, and why it was not enough

Research on this problem goes back decades, from studies of how pianists shape tempo to recent
machine learning models trained on expert ratings. Two problems stood out when we surveyed it:

- **Models that seem to work often learned the pieces, not the playing.** The strongest published
  audio model we examined looks good when the same pieces appear in training and testing, and falls
  apart on pieces it has never heard (Part 3 covers this in detail).
- **Skill datasets mix skill with recording conditions.** Beginners tend to be recorded on phones in
  practice rooms and virtuosos in concert halls, so a model can learn to recognise the room instead
  of the playing.

Commercial products stop at note checking. Nothing we found gives trustworthy feedback on shaping or
interpretation.

### The bets we made

Before running anything, the project wrote down a set of hypotheses, each with a result that would
count as proof it was wrong. The table gives their current status; Part 3 explains each.

| Id | The bet, in plain words | Status |
|---|---|---|
| H1 | The ways experts vary their tempo and loudness in a piece come down to a few basic shapes. | Not supported as stated. The shared part is small, but individual freedom is large. |
| H1b | Given the score, a model can predict the part of expression that experts share. | Falsified for the frozen SyMuPe model (R-10, scoped): it explains 0.15 of the experts' average loudness curve and 0.07 of their timing, where 16 experts reach about 0.88. The shape is partly right. |
| H2 | The 19 scales experts use to rate playing collapse to 3 to 5 underlying judgements. | Supported. |
| H3 | Simple, explainable MIDI features match a large audio model at predicting ratings. | Supported: they match, they do not beat it. |
| H4 | How well a player's expression follows the score's structure rises with skill. | Inconclusive. Skill and recording conditions could not be separated. |
| H5 | Playing a passage several times separates deliberate choices from noise. | Reinterpreted. The repeated part turned out to be what every pianist shares. |
| H6 | Each kind of flaw has its own measurable "how much does it bother listeners" curve. | Study built, not run. |
| H7 | Among good performances, what listeners prefer can be explained by measurable features. | Needs the pairwise listening study. |
| H8 | Audio models that seem to judge skill partly judge recording quality instead. | Mechanism shown in simulation; not yet measured on real audio. |

### How the work was done

The project was run by a lead Claude session that planned the work and handed tickets to
specialised agents: a data engineer, a feature engineer, a machine learning researcher, an audio
engineer, a study designer and a literature scout. One more agent, the auditor, had a single job:
try to break every result before it counted. Part 4 describes how that worked and what it caught.

All data is public research data under non-commercial licences, and none of it is stored in the
repository. The code, the plans and every experiment record are.


## Part 2. How it works

This part follows a performance through the system, from the moment it is recorded to the report
and the side-by-side audio. Each chapter explains what a stage does, why it was built that way, the
evidence that it works, and where it is known to fail or has never been tested.

### The pipeline at a glance

A performance goes through six stages:

1. **Input.** Either a MIDI file from a digital piano, or an audio recording (for example from a
   phone). Audio is first turned into notes by a transcription model. MIDI skips that step and is
   the more reliable input.
2. **Matching to the score.** Every played note is paired with the note in the written score it was
   meant to be. This one step is what makes everything else possible: once a note is matched, the
   score tells us its hand, its beat, its harmony and its place in the phrase.
3. **Correctness.** Unmatched and mismatched notes become wrong, missed and extra notes, reported
   bar by bar.
4. **Control.** Timing is split into a smooth, deliberate tempo curve and leftover jitter. From
   those come measures of evenness, hand synchrony, tempo stability and pedal clarity.
5. **Shaping and interpretation.** The performance is read against the music's phrase structure and
   against hundreds of expert performances of the same piece.
6. **Report and comparison.** Findings become a plain-language report with a bar-by-bar timeline,
   and each flagged passage gets a player that switches between your playing and an expert's.

All of this rests on the data described in the first chapter, which provides the scores, the expert
performances and the ratings used to build and test each stage.


### Data

Everything PianoLens measures is computed from someone else's recordings, scores and ratings, plus a small amount of data the project generated itself. This chapter explains what that data is, how it gets into the code, and why it was handled the way it was. It covers the shared data types every loader returns, how the same piece and the same pianist are recognised across datasets, each dataset in turn, the synthetic mistake set, and Henry's own recordings. The experiment results are told in the sections above (R-01 to BL-16); here the focus is on the data underneath them and on what could still be wrong with it.

The facts below come from the dataset manifest `DATASETS.md`, the loaders in `src/pianolens/data/`, the data rules in `.claude/rules/data.md`, `DECISIONS.md`, the landscape review `docs/research/2026-09-27-landscape.md`, and the data engineer's notes in `.claude/agent-memory/data-engineer/`.

#### Why can a MIDI file stand in for a piano performance?

MIDI is a list of note events. For each note it stores which key was pressed (pitch), when the key went down (onset), how fast it was struck (velocity, a number from 1 to 127) and when the key came up (release). Pedal movements are stored as separate events. A score is the notated music: pitches, notated rhythms, bars, time signatures and markings. Most of this project works on MIDI plus score rather than on audio, and that choice rests on the physics of the instrument.

When a pianist presses a key, the hammer is thrown at the string and leaves it before the note is heard. From that moment the pianist cannot change the note, except by deciding when to release the key and what to do with the pedals. So each piano note is fully described by its onset, its velocity and its release, and the whole performance by those numbers plus the pedal curves. No other common instrument is this constrained: a violinist or singer keeps shaping a note while it sounds. This is why the project bets that "MIDI plus score" is a near-complete description of a piano performance, and why the first phases ran on MIDI only (DECISIONS, 2026-09-27, "symbolic first"). Audio adds the room, the instrument and the microphone, which the pianist does not control during a note.

The bet has two weak points, both visible in the data. First, the piano and the room still shape the sound: the same velocity sounds different on two instruments. Second, much of the MIDI available is not a direct record of the keys at all, which is the subject of the next question.

In the code: CLAUDE.md "Why the bet is plausible"; DECISIONS 2026-09-27.

#### How much can we trust a MIDI file?

A MIDI file can come from four very different places, and the difference matters more than anything else about a dataset. Some pianos have sensors on every key and hammer and write down exactly what the pianist did. Other MIDI is produced by a neural network that listens to an audio recording and guesses the notes, which is called transcription. Transcribed MIDI looks identical in a file but carries the network's errors. The project therefore tags every performance with how it was captured, which it calls provenance.

| Tag | Where the MIDI came from | Datasets |
|---|---|---|
| `disklavier` | A Yamaha Disklavier, a real grand piano with key and hammer sensors | (n)ASAP, MAESTRO, PercePiano human segments, PianoVAM, the (n)ASAP rows inside PianoCoRe |
| `sensor` | Another sensor-equipped instrument: a computer-monitored Bösendorfer grand, or a keyboard whose make is not stated | Vienna 4x22, Batik-plays-Mozart, Rach3 |
| `transcribed` | A transcription network run on audio | Most of PianoCoRe, MAJEPPA, PSyllabus, Henry's recordings |
| `synthetic` | Generated by a program; nobody played it | PercePiano "Score" renditions, the synthetic mistake set |

The rule that follows is simple: any validation that needs exact timing uses `disklavier` or `sensor` MIDI only. The mistake generator enforces this in code and refuses other input unless explicitly overridden.

How large is the difference? PianoCoRe happens to contain 68 performances that exist twice: once as the original Disklavier file from (n)ASAP and once as a transcription of the matching audio (62 transcribed by Aria-AMT, 6 by Transkun V2). These pairs are a natural experiment, because the same playing is recorded both ways. PianoCoRe's copies are trimmed by a few notes, so they were matched back by name, note count and length rather than by file checksum, and 66 were found. On the Transkun pairs the transcribed onsets differ from the true ones with a robust spread of about 9.3 ms. Velocity is compressed (a slope of 0.64 against the true velocity) and scattered by about 9 MIDI units, which is more than listeners can hear. Timing features change by only about 1%. The apparent rate of wrong, extra and missed notes roughly doubles, from 0.039 to 0.080 per note, even though the pianist played the same notes.

That measurement set the project's policy (DECISIONS, 2026-09-27, after D-10): timing features are trusted on transcribed MIDI; velocity features are excluded from skill claims unless the source is Disklavier or sensor; and correctness feedback on transcribed or phone input must be judged against a transcription "floor" rather than against zero. The limit of this evidence is its size: only 6 Transkun pairs exist, and all 68 pairs are competition performances on a Disklavier, which is the kind of audio the transcribers were trained on.

In the code: `Provenance` and `PROVENANCES` in `src/pianolens/data/types.py`; `.claude/rules/data.md`; D-10 notes in `DATASETS.md`.

#### How long does a note last: while the key is down, or while it sounds?

The sustain pedal lifts the dampers, so a note keeps sounding after its key is released. A note therefore has two lengths: how long the finger held the key, and how long the sound lasted. These are two different actions by the pianist. The finger length is articulation (legato, where notes join, versus staccato, where they are detached); the extra length is pedalling. Mixing them would make a well-pedalled staccato look like legato.

The partitura library, which the project uses to read MIDI and scores, reports the sounding length by default: it extends a note to the pedal release whenever the pedal value is 64 or more. Every loader switches this off by setting partitura's pedal threshold to 128, a value no MIDI pedal can reach, so the reported duration is the key-down time. partitura's own documentation suggests 127, but 127 is a common real pedal value, so 128 is the safe choice. The pedal is not lost: every sustain (controller 64), sostenuto (66) and soft or una corda (67) event is kept in a separate pedal table, so pedalling features can read it directly.

In the code: `performance_from_partitura` in `src/pianolens/data/types.py`; `partitura_traps.md` in the data engineer's notes.

#### What does every loader hand back?

The project uses more than twenty sources, each with its own file layout. If feature and model code had to know about each one, every new dataset would break something. So every loader returns the same few objects, and no dataset-specific shape is allowed past the data layer. The notes inside those objects are partitura "structured note arrays" (numpy tables with named columns) rather than a new format, so partitura and the parangonar alignment library can use them directly.

A `Score` holds a note table with at least onset and duration in beats and in quarter notes, pitch and a note id. By default it also records the time signature, the stave (which of the two staves, roughly which hand) and whether a note is a grace note. It also holds a bar table with each bar's number, printed name, start and end. Two conventions follow from partitura and trip people up. After repeats are written out ("unfolded"), a bar number appears once per pass, so bar numbers are not unique; rows stay in time order instead. And a piece that starts with an upbeat has negative onsets at the start, because partitura puts beat 0 at the first full bar. A `Score` can keep the underlying partitura object so that dynamics and tempo words can be read later.

A `Performance` holds a note table with at least onset in seconds, key-down duration, pitch, velocity and id, plus the pedal table, its provenance tag (anything outside the four tags is rejected), the piece and performer ids, and for excerpts the span of score bars it covers.

An `Alignment` pairs score notes with played notes. Each row has a label and up to two ids, and the object records whether it is curated ground truth or produced by an algorithm, and by whom. There are four labels:

- `match`: a score note and the played note that realises it.
- `insertion`: a played note with no score note, an extra note.
- `deletion`: a score note with no played note, a missed note.
- `interpolated`: a score note paired with a note that a dataset's pipeline filled in and nobody played.

The fourth label exists because of PianoCoRe (described below), where about 9% of pairs are such filled-in notes. DECISIONS (2026-09-27) made it official: timing and velocity analyses may use interpolated pairs with care, but correctness metrics must exclude them, because counting a synthetic note as "played correctly" would hide exactly the errors the project wants to find. Other partitura labels, such as `ornament`, are kept unchanged when an alignment is imported.

An `AlignedPerformance` bundles a performance with its score and alignment, either of which may be missing. A `BeatCurve` handles sources that give beat times but no notes: one entry per score beat with a time, optional loudness and optional bar and beat labels. If no tempo is given, it is derived as 60 divided by the time to the next beat, in beats per minute. Its provenance may be left empty, because hand-annotated beat times from commercial audio fit none of the four tags. `Ratings` holds human ratings in long form, one row per performance, rater, dimension and value, on the dataset's own scale; when a rater rated the same item twice the values are averaged.

Two defensive fixes live here. partitura stores every note id as a 256-character string, about 1 KB per note, so ids are narrowed to their real length, cutting note-table memory roughly tenfold. And partitura numbers notes separately in each MIDI track, so a multi-track file has an `n0` in every track; when this happens all notes are renumbered in onset order. That bug surfaced during R-04 and the fix was accepted in DECISIONS.

In the code: `src/pianolens/data/types.py` (`Score`, `Performance`, `Alignment`, `ALIGNMENT_LABELS`, `AlignedPerformance`, `BeatCurve`, `Ratings`, `compact_ids`, `performance_from_partitura`, `score_from_partitura`); `midi_io.py` for plain MIDI files; `match_corpus.py` for match files.

#### How do we know two datasets contain the same piece?

The project's first hard rule is to hold out whole pieces: a model is always tested on pieces it never saw during training, because published models collapse on unseen pieces. That rule only works if a piece has the same id in every dataset. If a Chopin étude were called one thing in PianoCoRe and another in (n)ASAP, it could sit in training under one name and in testing under the other, and the test would quietly leak.

Canonical piece ids are built from the composer, the catalogue number and the movement, in lower-case ASCII: `chopin_op10_no3`, `bach_bwv846_fugue`, `beethoven_op31_no2_mv1`, `mozart_k331_mv3`. The catalogue is the composer's standard list of works: opus numbers, BWV for Bach, K (Köchel) for Mozart, D (Deutsch) for Schubert, S (Searle) for Liszt, L for Debussy, Hob. for Haydn, WoO for Beethoven's works without opus. Movements of a multi-movement work (sonata, suite, concerto) become `mv<k>`; numbered items in a set (études, nocturnes) become `no<k>`. Accented letters are folded to plain letters first, so "Dvořák" becomes "dvorak"; recomputing every id before and after that change altered none.

The governing principle is never to guess a catalogue number. Anything the parser cannot place with confidence keeps a dataset-prefixed id, such as `asap:Haydn/Keyboard_Sonatas_31-1`, and a prefixed id is never merged with anything. When two different title strings in PianoCoRe would produce the same canonical id, the parse is treated as ambiguous and all of them are demoted to prefixed ids; this is why the Hungarian Rhapsodies are prefixed. A missed link costs some reference data. A wrong link would silently merge two pieces, which is worse.

Several title conventions forced specific rules:

- PianoCoRe titles use `_` as a space, and `_` counts as a letter in regular expressions, so the usual "word boundary" test fails. The parser tests "not preceded by a letter" instead.
- In "Nocturne No.8" filed under "Nocturnes, Op.27", the 8 is Chopin's global nocturne number, not the number within Op. 27. Only a bare leading "No.N" or "N." in the movement field is trusted. As a result some very popular pieces, such as the Op. 9 No. 2 nocturne, stay prefixed.
- In "Ballade No.1, Op.23" the "No.1" is ignored, because it is not a number within the opus.
- (n)ASAP files La campanella as Paganini étude "2". It is No. 3 of Liszt's S.141, so it is mapped by hand to `liszt_s141_no3`.
- MAJEPPA titles such as "Kreisleriana, Op. 16 - V. ..." are rewritten into PianoCoRe's form and parsed by the same function. Titles that name a sonata or suite but give no movement number stay prefixed.

The result is a table with one row per dataset item: 6,852 rows and 4,308 canonical ids, of which 515 appear in two or more datasets.

| Dataset | Canonical ids | Of those, also in PianoCoRe |
|---|---|---|
| (n)ASAP | 201 of 221 | 197 |
| PianoCoRe, tier C (all) | 3,986 of 5,625 | not applicable |
| PianoCoRe, tier A | 1,167 of 1,591 | not applicable |
| PercePiano | 4 of 4 | 4 |
| MAJEPPA | 653 of 884 | 376 |
| Vienna 4x22 | 4 of 4 | 3 |
| Batik-plays-Mozart | 36 of 36 | 33 |
| MazurkaBL | 46 of 46 | 38 |
| DCML J. C. Bach | 29 of 29 | 0 |

MAESTRO, PSyllabus, Expert-Novice and NeuroPiano are not in the table, because their titles are free text or local codes that were not parsed. All 46 MazurkaBL mazurkas share an id with the DCML Chopin corpus. The main weakness is the mirror image of the caution: a piece can be canonical in one dataset and prefixed in another, and then the hold-out rule cannot see that they are the same. This was not audited across all datasets (see the gaps below).

In the code: `src/pianolens/data/piece_ids.py` (`make_piece_id`, `fold_accents`, `load_piece_id_table`, `datasets_by_piece`); `pianocore_piece_id` in `pianocore.py`; `majeppa_piece_id` in `majeppa.py`; `scripts/build_piece_ids.py` writes `data/processed/piece_ids.parquet` after `scripts/build_pianocore_piece_counts.py`.

#### How do we know two performances are by the same pianist?

The project also reports leave-performer-out results, which need performer ids that really identify people. Most datasets make this hard, so ids follow the same caution as piece ids: they are prefixed by dataset, and when the performer is unknown each performance gets its own id, so that unknown performers are never lumped into one large "unknown" group that would straddle training and test.

In practice identity is approximate almost everywhere. (n)ASAP ids are guessed from file names (`SunMeiting08` becomes `asap:sunmeiting`), so different pianists who share a surname merge; 17 performances fall under `asap:huang`. MAESTRO publishes no names. Many PianoCoRe rows have no performer. MAJEPPA releases no identity at all, so clips cut from the same video share an id and the same person in two videos gets two. PercePiano's paper reports 25 pianists, which the files only reproduce if player numbers restart for each composer, an inference rather than documented fact. Vienna 4x22 is the clean case: the same 22 numbered pianists play all four excerpts.

In the code: `asap_performer_id` in `asap.py`; `pianocore_performer_id` in `pianocore.py`; `percepiano_performer_id` in `percepiano.py`.

#### Which datasets are there, and what is each one for?

The datasets fall into a few roles: exact recordings with hand-checked alignments that serve as ground truth; very large collections that show how many experts play the same piece; human judgements of quality; skill-labelled amateur data; expert music-theory annotations; and practice recordings. Almost all are licensed for non-commercial research only, most under CC BY-NC-SA 4.0 (credit the authors, no commercial use, share derived work under the same terms). No data is committed to git. Raw data lives under `data/raw/<name>/` and is never modified; derived data goes to `data/interim/` or `data/processed/` and is regenerated by a script.

| Dataset | What it holds | Size used | Capture | Labels | Licence | Role here |
|---|---|---|---|---|---|---|
| (n)ASAP | Competition performances with scores | 1,066 performances, 222 pieces | disklavier | Hand-checked note alignments | CC BY-NC-SA 4.0 | Alignment ground truth, mistake set, expert references |
| PianoCoRe | Very large score-aligned corpus | Tier A: 157,207 performances, 1,591 pieces | mostly transcribed | Automatic note alignments | CC BY-NC-SA 4.0 | Expert reference distributions |
| PercePiano | Short segments rated by listeners | 1,202 segments of 4 works | disklavier, plus synthetic | 19 perceptual ratings | data CC BY-NC-ND 4.0 | Rating structure and prediction (R-01, R-03, R-04) |
| MAESTRO v3 (MIDI) | Competition recordings | 1,276 performances | disklavier | none | CC BY-NC-SA 4.0 | Controlled audio checks, rendering |
| Vienna 4x22 | 22 pianists, 4 excerpts each | 88 performances | sensor | Note alignments | CC BY 4.0 | Alignment and pedal checks |
| Batik-plays-Mozart | One pianist, 12 Mozart sonatas | 36 movements | sensor | Alignments plus harmony, cadence, phrase labels | CC BY-NC-SA 4.0 | Harmony and phrase ground truth |
| DCML corpora (6) | Scores with expert annotations | 29 + 166 pieces | scores only | Phrase and cadence labels | CC BY-NC-SA 4.0 | LLM phrase tests (R-08c, R-08d) |
| MazurkaBL | Chopin mazurka recordings | 46 mazurkas, 2,098 recordings | hand-annotated audio | Beat times, loudness | CC BY-NC-SA 4.0 | Beat-level tempo curves |
| Expert-Novice | Amateur audio | 83 recordings, 7 pieces | audio only | 803 ratings, 1 to 5 | CC BY-NC-SA 4.0 | Loaded, not yet used |
| NeuroPiano | Student audio | 104 recordings | audio only | 13 questions, 0 to 6, text | MIT (card) | Loaded, not yet used |
| MAJEPPA | Amateur to virtuoso, from online video | 4,449 performances | transcribed | Expertise, recording context | unclear | Skill checks (D-10, R-09, R-05) |
| PianoVAM | Amateur practice with microphone audio | 107 recordings | disklavier | Self-rated skill | CC BY-NC-SA 4.0 | Real-room transcription floor (A-01b) |
| Rach3, Hanon subset | Years of practice sessions | 247 session files | sensor (provisional) | Pianist level | CC BY-NC-SA 4.0 | Same passage played twice (BL-16) |
| PSyllabus | Pieces with syllabus difficulty | 7,901 files | transcribed | Difficulty 0 to 10 | conflicting | Open stand-in for CIPI |
| PianoJudges | Label index and link lists | 652 works | none | Difficulty, channel lists | unclear | Label reference only |
| Henry's recordings | Phone recordings of a learner | 5 pieces, one take each | transcribed | none | personal | A-01, F-08c, P-01 |

The manifest has grown over the project (the six DCML corpora and the PianoVAM audio were added on 2026-09-28), and DECISIONS after A-01b gives total raw data as 16 GB against a 60 GB budget.

In the code: one loader per dataset in `src/pianolens/data/`; the manifest `DATASETS.md`.

#### Where does exact ground truth come from?

To test an aligner or a mistake detector you need recordings where the true pairing of played and written notes is known. Three datasets provide this: (n)ASAP, Vienna 4x22 and Batik-plays-Mozart. All three were recorded on sensor pianos and aligned by hand or hand-checked, and together they carry most of the project's validation (for example F-01's alignment score).

**(n)ASAP** holds 1,066 Yamaha e-Competition performances (the README says 1,067) with MusicXML scores (a standard digital score format), covering 222 distinct pieces, and 1,063 hand-checked alignments. Over those alignments there are 3,338,534 matches, 237,940 insertions and 259,624 deletions. The alignments refer to the score with every repeat taken, so the loader merges the score's parts and unfolds it maximally, giving note ids such as `n22-1` and `n22-2` for the first and second pass. Very long scores need Python's recursion limit raised to 10,000 to unfold. Scores are cached, and rows are processed in score order so each score is parsed once.

Several traps were found and handled. The metadata's alignment-path column is broken for all 28 Schubert D.899 rows (dots in the folder name mangled it), so the loader derives the path from the MIDI path. Three performances have no alignment and are returned without one. 636 alignment ids name the second half of tied notes, which sound as one long note; partitura folds them into the first note, so those ids do not exist in the score table. 6,362 score notes are referenced by no alignment row, and 475 played notes likewise, which was not investigated further. Twenty pieces keep prefixed ids because their catalogue numbers are uncertain (Haydn sonatas, Debussy, Ravel, Glinka, Bach's Italian Concerto, Liszt's Mephisto Waltz). Most importantly for later work, the "natural" insertions and deletions in the ground truth are a mix of real slips and annotation noise; on the clean copies of the mistake set they run at 51.7 insertions and 40.5 deletions per 1,000 played notes.

**Vienna 4x22** has 4 short excerpts (including Mozart's K.331 and Schubert's D.783 No. 15), each played by the same 22 pianists on a computer-monitored Bösendorfer. Its 88 match files (a format that stores the performance, score notes and alignment together) contain 43,472 matches, 418 deletions and 184 insertions. The `*-average.mid` files are averaged performances nobody played and are skipped. It is the only fully open licence here (CC BY 4.0). It was used in the pedal checks, where 86.5% of pedalled harmony changes in the K.331 excerpt lift inside the pedal window.

**Batik-plays-Mozart** is one pianist, Roland Batik, playing 12 Mozart sonatas (36 movements) on a monitored Bösendorfer: 98,317 matches, 4,104 insertions, 208 deletions. Its special value is the attached expert annotations from the DCMLab Mozart corpus, which label every score note with harmony, cadence and phrase information, so it is the one place where exact performances and music-theory ground truth meet. The score rebuilt from a match file has no slurs, dynamics or tempo words, so the loader can instead unfold the edited MusicXML score along the repeat path whose note ids equal the match-file ids. Every match id resolves in all 36 movements (the id sets are identical in 35, and differ by one extra MusicXML note in K.281/3), and beats agree except for 9 notes of one fast run in K.331/1. Only the four repeat paths closest in note count are tried, because a set of variations (K.284/3) has so many paths that building them all took over 30 minutes and 18 GB. The phrase labels mark a start with `{`, an end with `}` (placed on the note where the cadence arrives, not on the last note) and both with `}{`. Cadence types are PAC (perfect authentic), IAC (imperfect authentic), HC (half), EC (evaded) and DC (deceptive). All 1,068 phrase starts, 1,068 ends and 1,144 cadence rows map onto the score.

**MAESTRO v3** (MIDI only) adds 1,276 more Disklavier performances (7,040,150 notes) without alignments, performer names or parsed titles. Only the 58 MB MIDI archive was downloaded; the roughly 120 GB of audio stays off the Mac. It served in the A-01 controlled check, where three of Henry's five pieces have MAESTRO performances that could be rendered to audio, degraded like a phone recording, transcribed, and compared with the true MIDI.

In the code: `asap.py` (`iter_asap`, `AsapStats`, `asap_alignment_path`), `vienna4x22.py`, `batik_mozart.py` (`iter_aligned(musicxml_score=True)`, `performed_score`, `phrase_annotations`), `maestro.py`, `match_corpus.py`; QA script `scripts/check_asap.py`. Tickets D-01, D-04, D-05, D-11.

#### Where do hundreds of expert performances of one piece come from?

Tier D of the scoring engine compares a learner's performance with how experts play the same piece, bar by bar. That needs not a handful but hundreds of expert performances per piece, all aligned note by note to the same score. Only one corpus comes close: PianoCoRe, published in 2026, which gathers performances from Aria-MIDI, PERiScoPe, ATEPP, GiantMIDI and (n)ASAP and aligns them to scores.

PianoCoRe is organised in quality tiers, stored as yes/no columns in its metadata rather than as separate downloads:

| Tier | Meaning, per the dataset's documentation | Performances | Pieces |
|---|---|---|---|
| C | Everything | 250,046 | 5,625 |
| B | De-duplicated and quality-filtered | 214,092 | 5,591 |
| A | Note-aligned | 157,207 | 1,591 |
| A* | High quality, at least 85% aligned | 130,275 | 1,517 |

In tier A, 1,227 pieces have at least 10 performances, 730 have at least 50 and 479 have at least 100. (The landscape review's "1,104 pieces with 50 or more" turned out to be a tier C figure and was corrected.) The catch is provenance. Only 1,066 rows are Disklavier recordings, the (n)ASAP ones, of which 978 are in tier A. Everything else was transcribed from audio: 200,504 rows by Aria-AMT, 34,773 by Transkun V2, 11,564 from ATEPP and 2,139 by ByteDance's model. So the expert reference is overwhelmingly transcribed MIDI, with good timing and unreliable velocity, and every tier D comparison inherits that.

Of the downloads offered, the project took the metadata, the "refined" archive (score MIDI, performance MIDI and alignment files for 184,230 rows) and the raw MIDI archive (all 250,046 raw performances and 1,607 MusicXML scores), 6.2 GB in all. The separate 5.2 GB raw-alignment archive was skipped because the refined alignments suffice. Files are read straight out of the zip archives.

Reading the alignments correctly took some detective work. Each performance's alignment file holds, for every score note, the index of its performance note, plus a flag saying whether that performance note was filled in. The indices count notes in the order (MIDI tick, pitch), but partitura numbers score-MIDI notes by voice, so its ids follow a different order. The loader therefore reads the note order independently with the `mido` MIDI library, sorts both sides by tick and pitch, maps positions onto partitura's ids, and checks that every pair agrees on pitch. partitura also drops a few notes on import; these become a deletion or insertion and are counted.

The filled-in notes deserve emphasis. PianoCoRe's refinement pipeline (called RAScoP) gives each refined performance exactly one note per score note. Where the pianist skipped a note, or the transcriber missed it, the pipeline synthesises one. About 9% of pairs are such notes. Treated as played, they would make every PianoCoRe performance look nearly flawless and would blur timing statistics. They are therefore labelled `interpolated` and excluded from correctness metrics and from the R-02 timing analysis (DECISIONS, 2026-09-27). Note that the loader cannot tell whether a filled-in note hides a pianist's omission or a transcriber's miss.

Reading straight from the zips costs about 0.9 s per performance at random, falling to roughly 0.06 to 0.2 s when rows are sorted by score so that the score is parsed once. Loading a popular piece this way takes minutes, too slow for analysis, so every tier A performance was converted once into a per-piece cache. Each of the 1,591 pieces becomes one parquet file (a compressed column-oriented table format) with one row per aligned pair. Score-side columns are prefixed `s_` (id, onset and duration in beats and quarters, pitch, voice, stave, grace flag, time signature, bar number) and performance-side columns `p_` (id, onset, key-down duration, pitch, velocity); a deletion or insertion leaves the missing side empty. Separate tables list performances (source, transcriber, split, A* flag, label counts, a pitch-mismatch flag), pieces and failures. The cache stores no pedal events; pedal analyses use the loader. Bar numbers come from the MIDI time signatures, not the printed score, so bar-level feedback has to be mapped back to printed bars separately.

The cache was built by 12 parallel worker processes, one piece per task, largest pieces first. The build is resumable: a finished piece leaves a marker file and is skipped on restart, and each output file is written under a temporary name and renamed only when complete. Each worker needed about 0.9 GB, mostly the zip's directory of 370,000 entries; the metadata index was passed to workers as a parquet file to avoid re-reading the 206 MB metadata in each. The run took 29 minutes and loaded all 157,207 performances with no failures, producing 377,786,620 rows: 344,030,350 matches, 33,726,317 interpolated (8.9%), 29,953 deletions (all from partitura's import drops, in 7,157 performances) and no insertions. Nine performances have at least one pair whose pitches disagree. Afterwards the largest piece (1,929 performances, 2.89 million rows) loaded in about 0.03 s, a figure measured right after the build, when the files were probably still in the operating system's memory.

PianoCoRe also contains about 34,000 duplicates that are the same audio transcribed by two different models. They are unused so far but could measure how much two transcribers disagree.

In the code: `pianocore.py` (`PianoCoRe(tier="a").iter_aligned`, `pianocore_index`), `pianocore_cache.py` (`load_piece_notes`, `load_performances`, `load_pieces`), `scripts/build_pianocore_cache.py`, `scripts/build_pianocore_piece_counts.py`; output `data/processed/pianocore_A/`. Tickets D-03, D-07.

#### Where do human judgements of playing quality come from?

A model of "quality" needs something to be right about, and the only real target is human judgement. The main source is PercePiano, the only dataset here with many experts rating many dimensions of the same short passages. Two smaller audio-only sets, Expert-Novice and NeuroPiano, add ratings of real amateurs.

**PercePiano** has 1,202 segments of 4, 8 or 16 bars from four works: Beethoven's 32 Variations WoO 80 (238 segments), Schubert's D.935 No. 3 (117), and movements 2 and 3 of Schubert's D.960 (288 and 559). Listeners rated each segment on 19 dimensions covering timing, articulation, pedal, timbre, dynamics, music-making, mood and an overall "interpretation" score, on a 1 to 7 scale. They heard the MIDI played through Logic Pro's "Yamaha Grand Piano" sound, not the original recordings. The human segments came from competition MIDI and are tagged `disklavier`; computer-rendered deadpan "Score" versions are tagged `synthetic`.

The dataset's weakness for this project is that it has only four pieces. Holding out whole pieces therefore means holding out one of four works. DECISIONS (2026-09-27) fixes how this is reported: leave-work-out with 4 groups, and again with the two D.960 movements merged into 3 groups (they share all 12 human performers), and a claim must hold both ways. The authors' published mean ratings are the primary target, because published results use them.

Reading the ratings correctly required reproducing several of the authors' own cleaning steps:

- File names are `<work>_<N>bars_<player>_<segment>`; the README states the reverse order, but the authors' code and the data agree with this one. One file name starts with a space.
- The ratings file has 20 question columns, and the 19 dimensions are the first 19. Recomputing the authors' means from those columns reproduces their published file exactly, which confirms the order.
- Values of 8 and 9 occur on a 1 to 7 scale. As the authors do, any row containing a value above 7.1 is dropped (208 rows). A blank or 0 means "I don't know" and is dropped for that dimension only.
- The authors rename some "Score" files to "Score2" (WoO 80 segments 5 to 16 and D.935 segment 1). The loader applies the same renames, which leaves 13 "Score" files with no ratings and 1,189 rated segments.
- Some rows are repeated verbatim. The loader drops them by default, leaving 12,444 rating submissions (the paper reports 12,652). The authors' means count duplicates twice, so they differ from the de-duplicated means by up to 0.070 on the authors' 0 to 1 scale; the de-duplicated version is a required sensitivity check.

Some numbers do not match the paper and are recorded rather than forced: 63 raters after cleaning against the paper's 53, and between 4 and 17 raters per segment (median 10) against the paper's 5 to 12. The direction of one articulation scale is undocumented, since the code names it `Long_Short` and the README `Short_Long`.

The segment scores are renumbered from bar 1, so each segment's place in the full piece had to be recovered by matching its notes against a full score. This worked for all 238 WoO 80 segments (the theme is bars 1 to 8 and variation n is bars 8n+1 to 8n+8; 14 segments were placed by that formula because note matching failed), and approximately for 99 of 117 D.935 segments using the (n)ASAP score. No full score of D.960 was available, so its 847 segments have no position. In all, 337 of 1,202 segments have a bar range.

**Expert-Novice** has 83 recordings (48 kHz audio) of 7 easy pieces by 21 players, with 803 ratings on a 1 to 5 scale (332 from 4 instructors, 471 from novices), comments, and self-rated skill (by recording: 8 beginner, 30 intermediate, 45 advanced). Counts match the paper. There is no MIDI. Novice rater ids run 1 to 21, the same range as the player ids, and the files do not say whether the raters are the players. The "beat alignment" files turned out to give score positions in fractions of a whole note, not beats, so they are not turned into beat curves.

**NeuroPiano** has 104 student recordings from 39 students, rated by 35 teachers on 13 questions on a 0 to 6 scale, with Japanese and English text answers. Two questions ask what was good and what was bad and also carry a score; eleven ask about specific aspects. There are 2,265 rows on disk against 2,255 on the dataset card, and some rating triples appear twice and are averaged. Audio is stored as WAV bytes inside the data file.

Neither Expert-Novice nor NeuroPiano has been used in an experiment yet. They are the nearest thing on disk to ratings of real amateurs.

In the code: `percepiano.py` (`iter_percepiano`, `load_percepiano_ratings`, `load_percepiano_official_means`), `scripts/build_percepiano_spans.py`, `expert_novice.py`, `neuropiano.py`. Tickets D-02, D-04.

#### Where does skill-labelled data come from, and why is it treated with suspicion?

To test whether a feature tracks skill, you need performances labelled by skill level. The data that exists is mostly amateur video transcribed from audio, and it carries a trap: the kind of recording is tied to the skill of the player. Beginners are filmed practising at home; virtuosos are filmed in concert halls. A model can learn to recognise the setting instead of the playing. CLAUDE.md rule 3 exists because of this.

**MAJEPPA** is the main skill set. Its 4,449 performances (the paper abstract says 3,979) come from online videos, transcribed with Transkun, and are labelled with one of six expertise levels (child beginner, adult beginner, adult intermediate, child professional, piano teacher, virtuoso) and a recording context such as practice, sight-reading, demo class, slow demo or concert performance. The paper says the transcription quality was not checked. Of the 886 score MIDI files, 8 crash partitura's reader, so those performances arrive without a score. The released alignment is a time-warping curve in seconds, not a note-level pairing, so the project re-aligns note by note with its own aligner.

The context confound is stark in the data: all 156 virtuoso clips are concert performances, teachers are mostly demonstrations, and adult beginners are mostly practice and sight-reading. When D-10 compared control features within matched contexts, the apparent skill effect disappeared, and R-05 showed an audio model exploiting the setting. Alignment quality is a second trap. The metadata's `score_coverage` of at least 0.85 was the entry gate for the H4 analyses, but some clips contain several times the score's notes (one has 13,905 played notes for 1,796 written), and 28% of the 1,604 D-10 performances align with a match ratio below 0.8. That share is highest for adult beginners (36%) and lowest for child professionals (18%), so low-quality alignments are themselves correlated with skill.

MAJEPPA's score MIDI files also had two defects that silently broke features, both fixed after alignment:

- They carry no stave information, so every note sat on "stave 0" and hand-synchrony features were empty. 829 of 886 files have exactly two note tracks, so the track with the higher average pitch is assigned to the right hand and the other to the left. Notes in both tracks or in neither keep no hand and are counted.
- Their notes have playback lengths, shortened by one tick or to about 95% of the written value (an eighth note lasts 0.4979 or 0.4729 quarters instead of 0.5). Features that look for notes joined without a gap then find none. Each note is therefore extended to the next onset in its stream when the gap is at most 7% of the time between the two onsets. Real staccato gaps are much larger and survive. The 7% was chosen to cover the observed 5% shortening with a margin; it was not tuned.

Both fixes must be applied to the aligned score, because the aligner re-reads the MIDI file. In 17 of the 309 scores used in D-10, more than 10% of onsets fall off a fine rhythmic grid, meaning the score itself is not properly quantized.

**PianoVAM** is the cleaner counterpart: 107 practice recordings by 10 amateur pianists (none music students) on a Disklavier, so the MIDI is exact, with self-reported skill (Advanced 70 recordings from 3 pianists, Intermediate 27 from 4, Beginner 10 from 3). It has 527,302 notes, and 96 recordings use the pedal. No scores are released and piece names are free text (70 pieces, some improvised), so every piece id is prefixed; only Satie's first Gymnopédie is played at more than one level, once per level. Its licence is CC BY-NC-SA 4.0, checked on the dataset card after the ticket had said CC BY-NC.

PianoVAM's real value turned out to be its audio. Each recording also has a dedicated microphone track in a practice room, aligned to the MIDI by the authors. That is real-room audio with exact note ground truth, which nothing else here provides. 84 of the 107 audio files (4.4 GB, mono 44.1 kHz) were downloaded to the Mac as a documented exception to the rule that audio lives on the GPU machine; a four-hands take and the 22 largest takes of one pianist were left out to stay near a 5 GB budget, and a checksum is stored for each file. Run through Transkun, the onsets differ from the Disklavier MIDI by a constant offset of -18 to +7 ms per file, and note F1 (a 0 to 1 score combining missed and false notes) is 0.94 to 1.00. This is what showed that Henry's odd extra notes (below) are not something real rooms and microphones produce in general; a later analysis (BL-22) traced most of them to a second, independent sound in his recordings. The microphone model and placement are not stated. Video and hand-tracking data (about 38 GB) were not downloaded.

**Difficulty labels** are a different kind of skill label: they grade the piece, not the playing. The CIPI dataset (Henle difficulty levels) is access-restricted, so the project uses two open stand-ins. PSyllabus has 7,901 transcribed recordings, each with an exam-syllabus difficulty from 0 to 10, in 5 folds; 7,900 load and one file is empty. Its licence conflicts (the record says CC BY 4.0, the description says research use only). The PianoJudges repository, which has no licence file, contains the CIPI label index itself (652 works, Henle levels 1 to 9) but no audio or MIDI, only lists of video channels and links. Because difficulty belongs to the piece, it is stored with the performance's metadata rather than as a rating.

In the code: `majeppa.py` (`iter_aligned`, `load_dtw_path`, `with_track_staff`, `snap_score_durations`, `prepare_aligned`), `pianovam.py`, `psyllabus.py`, `pianojudges.py`; spec `docs/specs/skill-control-check.md`. Tickets D-05, D-10, A-01b.

#### How do we give an LLM a score without giving it the answers?

The R-08 experiments asked whether an LLM can find phrase boundaries in a score. Testing that needs expert phrase labels on music the model is less likely to have memorised (the J. C. Bach sonatas) and on Romantic repertoire. The DCMLab (Digital and Cognitive Musicology Lab) publishes scores with expert harmony, cadence and phrase annotations, and six of its corpora were added. They contain scores only, no performances.

| Corpus | Release | Pieces | Phrase ends / cadence labels |
|---|---|---|---|
| J. C. Bach sonatas, op. 5 and op. 17 | v2.4 | 29 movements | 442 / 406 |
| Chopin mazurkas | v3.2 | 56 (55 labelled) | 606 / 344 |
| Grieg Lyric Pieces | v2.3 | 66 | 559 / 433 |
| Tchaikovsky, The Seasons | v2.3 | 12 | 298 / 185 |
| Schumann, Kinderszenen | v2.3 | 13 | 87 / 79 |
| Liszt, Années de pèlerinage | v2.3 | 19 | 277 / 272 |

The central design problem was leakage. The corpora ship MuseScore files with the labels embedded, plus table exports ("facets") made by a tool called ms3. If the score given to the LLM were built from a file that contains the labels, the answers could leak into the prompt. So the loader builds the score from three facets that carry no labels: `notes` (every note head), `measures` (bar lengths, signatures, repeat structure) and `chords` (dynamics, text, tempo marks, and for the Romantic corpora hairpins and text lines). It never opens the label facet or the MuseScore files when building a score, and records which files it read. A leakage check renders every score exactly as the LLM would see it and searches for any label string, any banned word and any Roman numeral. It passed on all 29 J. C. Bach and all 165 labelled Romantic movements, and a planted label is caught in the tests.

A score built this way lacks some things an engraved score has: fermatas (the J. C. Bach MuseScore files have 15, in 8 movements), slurs, pedal marks, printed rests (derived as the gaps in each stave) and the key's mode, so major and minor are not distinguished. For J. C. Bach, hairpins are not read either.

Tempo words needed care. For J. C. Bach, the movement title from the metadata (for example "Allegretto") is placed at the first note, because that is the tempo marking. For the Romantic pieces this would leak identity, since titles are names like "Träumerei" or "Gondoliera", so tempo comes from the tempo events inside the score and titles stay in the metadata only. Liszt's file names also contain titles, so downstream code must use blind ids. Text is cleaned of formatting markup and font symbols, metronome symbols are spelled out (for example `quarter=144`), and text with no letter or digit is dropped. Two spellings are rewritten because the leakage check flagged them as false alarms: "Tempo I" becomes "Tempo primo" (otherwise it looks like a Roman-numeral harmony label) and Liszt's "una chorda" becomes "una corda" (otherwise it contains "chord"). These are the only text rewrites.

The table exports had traps of their own. The `duration_qb` column is a rounded decimal (0.333333 for a triplet), so the loader uses the exact fraction column instead. Column sets differ between files, so every optional column is read defensively. Pitches are already sounding pitches, with octave-transposition lines applied. Some tie continuations start after a gap or on the other stave; they are merged if they start within 4 quarter notes of the first note's end, and the remaining orphans are mostly grace notes wrongly coded as tie continuations. As a strong consistency check, the number of notes after merging ties matches the corpus metadata in 29 of 29 J. C. Bach movements, 56 of 56 mazurkas, all Grieg and Tchaikovsky pieces, 12 of 13 Schumann and 16 of 19 Liszt pieces.

Repeats are written out by following the `next` column, where the k-th visit to a bar takes the k-th jump target. This agrees with the corpus metadata in all 29 J. C. Bach movements and 162 of 166 Romantic pieces. The four exceptions are Chopin mazurkas where ms3 itself is wrong or gives up, and they were checked by hand: in two, ms3 stops at the *Fine* before the *da capo* has been played (the loader plays on, giving 64 and 62 bars instead of 24 and 12); one is a *dal segno senza fine*; and one is a *dal segno al Fine* whose Fine sits inside a first ending. These four are marked as not validated.

Labels are given as a bar and an offset within the bar. Because partitura puts the first full bar at beat 0, a piece with an upbeat has negative early positions, and an early version that converted positions through partitura's inverse quarter map put the labels of upbeat movements one eighth late (26 of them in op. 17 No. 2, third movement). Counting labels that do not fall on any note caught the error, and labels are now converted through the score's internal time units. After the fix, every J. C. Bach label sits on a note onset except one phrase start, and 33 Romantic placements sit on a rest or a held note and are kept at their exact beat. Label values are `{`, `}` and `}{` for phrases, plus 3 rows of a deprecated symbol in J. C. Bach that are dropped and counted, and cadences PAC, IAC, HC, EC, DC and PC (plagal).

For R-08d a movement was eligible if it is labelled and has at least 5 phrase ends, and "simple meter" meant every time signature has 2, 3 or 4 beats per bar: Chopin 52 eligible (all simple), Grieg 53 (45 simple), Tchaikovsky 12 (9), Schumann 10 (10), Liszt 19 (8). Two caveats apply to all of this. The J. C. Bach README notes that op. 5 Nos. 2 to 4 are the sonatas Mozart arranged as concertos (K.107), so they are likelier to be familiar. And all Romantic labels were released before the model's training cutoff, so exposure to them cannot be excluded; the landscape review found no DCML Romantic labels made later.

When the J. C. Bach loader was generalised into one shared loader for all six corpora, its outputs (rendered text, notes, phrase tables and metadata for 116 variants) were hashed before and after and found identical. That mattered because R-08c's pre-registered renderings depended on them.

In the code: `src/pianolens/data/dcml.py` (`load_score`, `phrase_annotations`, `playthrough`, `clean_text`, `LABEL_FREE_FACETS`), `dcml_jc_bach.py` (a thin wrapper); QA scripts `scripts/check_dcml_jc_bach.py`, `scripts/check_dcml_romantic.py`. Tickets D-12, D-13.

#### How are tempo curves from commercial recordings handled?

Some of the richest information about expert timing exists only as annotations of commercial audio. MazurkaBL, from the CHARM Mazurka project, gives for each recording of a Chopin mazurka the time of every beat and the loudness at each beat in normalised sones (a unit of perceived loudness). There are no notes and no audio. 46 mazurkas have beat data (the landscape review said 44, which is the number with MusicXML scores), with 2,098 recordings, 700,008 beat rows and 134 performer ids, 10 of them without a name.

Each recording becomes a `BeatCurve`: one entry per score beat, with tempo derived from the gaps between beats. Its provenance is left empty, because hand-marked beat times are neither sensor MIDI nor transcription. Beat numbering starts at 0 on each downbeat, and an upbeat bar can start at beat 2. Recording ids sometimes carry a letter suffix. The licence is stated only in the README, not in a licence file.

In the code: `mazurkabl.py` (`load_beat_curves`, `iter_beat_curves`, `load_all`).

#### What does "the same passage played twice" look like in data?

To tell a pianist's intentional timing from motor noise, one useful measurement is how much timing changes when the same person plays the same passage twice. That needs repeated, complete, aligned passes. Rach3 records four pianists practising over several years (p1, p2 and p4 advanced, p3 a beginner). Only the Hanon exercises were downloaded: 247 session files (p1 124, p2 36, p3 87; p4 has none), 1,396,336 notes. A Hanon exercise is a repeated finger pattern that climbs the keyboard step by step, which makes it ideal for repeated takes but, as it turned out, useless for tempo shaping.

The raw files do not contain takes. Each file is one piece within one practice session, often 7 to 30 minutes long, with repeats, stops and several exercises mixed together. And the score is the whole book in one part (1,433 bars, 22,071 notes). The first step therefore cuts one-pass scores out of the book. Part I (exercises 1 to 20) occupies the first 583 bars; each exercise restarts its bar numbers at 1 and ends with a repeat sign and a final chord. Each is cut out, given the book's opening key, time and clef settings, and stripped of its repeat signs, leaving one pass of about 28 bars plus the final chord. Part II has no separators and was not split.

Takes are then found with a "fitting" alignment (Sellers, 1980). Played notes are grouped into events (notes starting within a short window of each other form one chord), and each score onset is compared with each event: +2 if the pitch sets are equal, +1 if they share a pitch, -2 otherwise, with a cost of 1 for skipping a note on either side. Dynamic programming, a table-filling method that finds the best path, aligns the exercise end to end while leaving the session free at both ends, so every possible end point gets the score of one complete pass ending there. Ends are taken greedily from the best score down, and a take is kept if it does not overlap one already kept and reaches at least 60% of the perfect score. Across the 20 exercises, overlaps are resolved in favour of the better normalised score. Exact pitch matching matters here: each Hanon bar is the previous bar one step higher, so a matcher that ignored pitch, or used pitch class only, could slip by a whole bar.

The chord window had to adapt to the player. p3 plays the hands up to about 50 ms apart, so a fixed 40 ms window splits chords and the event match drops to about 0.85. The build tries 40, 60 and 80 ms for each session and keeps the one whose well-matched takes (at least 85% of the perfect score) add up to the highest total.

Before any take statistic was computed, quality rules were fixed: at least 90% of score onsets matched with an equal pitch set, at least 90% of notes matched, at most 15% extra notes, and no gap longer than 8 times the median beat spacing (a stop). Pauses at the turnaround in bar 14 are the main reason takes fail. Of 2,038 takes found, 1,149 pass (p1 372, p2 191, p3 586). The share of each pianist's session notes that ends up inside Part I takes is 0.44 for p1 (whose files are usually one take each), 0.79 for p2 and 0.80 for p3. The beginner practises about once a day and plays each exercise about once per day, so there are no same-day pairs of p3 takes after quality control. That is why BL-16 compared same-day takes for the advanced pianists with next-day takes for the beginner, which mixes skill with the time gap.

Rach3's provenance is provisional. The README says "MIDI recordings" but does not name the instrument. It is clearly keyboard MIDI rather than transcription, so it is tagged `sensor` with the instrument noted as "not stated" until confirmed. File names end in `mi` before `.mid`, which the README's description of the naming scheme omits.

In the code: `rach3.py` (`iter_performances`, `rach3_index`), `rach3_takes.py` (`hanon_exercise_xml`, `fit_alignment`, `find_takes`, `TakeConfig`, `TakeQC`, `HanonTakes`), `scripts/build_rach3_hanon_takes.py`; output `data/interim/rach3_hanon_takes/`. Tickets D-10, BL-16.

#### How do we test a mistake detector when real mistakes are not labelled?

The correctness tier finds wrong, extra and missed notes. Testing it needs recordings where every mistake is known. The (n)ASAP ground truth mixes real slips with annotation noise, and the public mistake dataset (MAESTRO-E) is behind a login. So the project injects known mistakes into clean, exactly timed performances and checks whether they are found. This set validated the correctness gate (DECISIONS, 2026-09-27) and underlies the per-bar error F1 of 0.99 reported in section 3.

The source performances were chosen by fixed rules with seed 0. Each is an (n)ASAP performance with a robust ground-truth alignment and a score with only one repeat path, so that the ground-truth score ids equal the ids the project's aligner produces and bar numbers are unique; performances with repeats are therefore excluded. Each has at most 6,000 played notes, to keep an evaluation run under about 10 minutes, which excludes Balakirev's Islamey entirely. Composers are sampled in turn, one performance per piece before any second one. The result is 100 performances from 12 composers (Bach, Beethoven, Chopin, Haydn, Liszt, Mozart and Schubert 12 each, Schumann 5, Rachmaninoff 4, Scriabin 3, Debussy 2, Ravel 2) with 246,324 notes. Each appears once clean and once at each mistake rate of 0.02, 0.05 and 0.10 (mistakes per correctly played note), 400 performances in all, with seed 1000 times the performance index plus the rate index so every copy can be regenerated.

What should a synthetic mistake look like? The generator started from the MAESTRO-E code, read and compared on 2026-09-27, and departed from it where the goal differed:

| Aspect | MAESTRO-E | PianoLens | Reason |
|---|---|---|---|
| How many | Random around a target of 3 to 5% | Exactly the rate times the number of correctly played notes | Clean comparison per rate |
| Which kinds | Mostly timing shifts; some drops, pitch changes and extra notes | Wrong pitch, extra and missed in equal shares by default | Timing is tested separately |
| Wrong pitch | Offset drawn from a bell curve, nearly always 1 or 2 semitones | ±1 semitone (weight 0.3 each), ±2 (0.15 each), ±12 (0.05 each); timing, length and velocity unchanged | Neighbouring keys are the usual slip; landing in the wrong octave is a real error MAESTRO-E does not model |
| Extra note | Starts anywhere up to the next note, random length | A neighbouring key (±1 at 0.35 each, ±2 at 0.15 each) caught with a played note: onset 20 ms before to 60 ms after it, 30 to 150 ms long, 40 to 80% of its velocity | A finger brushing the next key is short and soft |
| Missed note | Chosen uniformly | Twice as likely for inner notes of chords of three or more, twice as likely in fast passages (another chord within 150 ms); the top voice is never favoured | Players drop inner and fast notes, rarely the melody |
| Timing | Shifted along with most mistakes | Not attached to mistakes; timing jitter, velocity jitter and tempo scaling are separate options, off by default | The listening study needs timing and correctness varied independently |

Every injected note must be physically possible. A new pitch must lie on the 88-key piano (MIDI 21 to 108), must not already be in the same chord (notes within 50 ms), and must not overlap a sounding note of the same pitch, because one key cannot be pressed twice at once. Up to 20 draws are tried per note; if none is legal, the generator moves to another note. Only notes the source alignment labels `match` are touched. Existing insertions and deletions are carried into the output marked "not injected", and evaluations treat them as "don't care". Filled-in `interpolated` notes are never touched. By default the generator refuses anything that is not Disklavier or sensor MIDI, and its output is tagged `synthetic` with the source provenance kept in its metadata.

The ground truth it writes labels every played note `correct`, `extra` or `wrong_pitch`, lists every missed score note, and rebuilds a ground-truth alignment in which a wrong pitch counts as one deletion plus one insertion, partitura's convention. Extra notes get new ids (`x0`, `x1`, ...), while a wrong-pitch note keeps its original id. The injected totals are, for wrong, extra and missed: 1,592, 1,559 and 1,523 at rate 0.02; 3,922, 3,894 and 3,863 at 0.05; 7,813, 7,791 and 7,754 at 0.10. The whole set took 53 s to build on 12 workers.

Those totals are slightly uneven, always with wrong pitch highest and missed lowest, and the code explains why. The per-performance count is split among the three kinds by a largest-remainder rule; with equal shares all three remainders tie, and the tie-break gives the spare mistake to wrong pitch first and extra second. Over 100 performances this predicts wrong pitch about 67 above missed and extra about 33 above; the observed gaps are 59 to 69 and 31 to 37. This explanation is a reading of the code that fits the counts, not a separately tested fact. The effect is under 2%.

In the code: `src/pianolens/data/perturb.py` (`perturb`, `MistakeSpec`, `MistakeLabels`, `load_mistake_set`), `scripts/build_mistake_set.py`; output `data/processed/mistakes_v1`. Ticket D-08.

#### What about a real learner's recordings?

Everything above is either expert playing or research data collected by others. The project also needs to know whether its feedback works for an actual learner recording on a phone, which is the intended use. Henry supplied phone recordings of himself playing 5 Chopin pieces on an acoustic grand piano, one take per piece, each a few minutes long. The audio had passed through a lossy online video encoding before it reached the project.

The recordings are transcribed to MIDI by two different models (Transkun and Aria-AMT), aligned to PianoCoRe's MusicXML score of each piece, and compared with that piece's PianoCoRe tier A performances, of which there are between 221 and 1,631. Because the input is transcribed, velocity and pedal are treated as low confidence and extra notes are never counted against the player. The results are in A-01, F-08c and P-01.

This is personal data, and DECISIONS (2026-09-28) sets strict rules: it lives in a gitignored folder, reports built from it stay in `data/interim/`, and neither the audio nor any MIDI or report derived from it may be committed or uploaded. Written documentation gives only methods and aggregate numbers. Its limits are serious. With one take per piece, the repeated-take features (F-07) cannot be computed. With no ground-truth MIDI, the source of the high, fixed-pitch "extra notes" found in three recordings cannot be settled; a data analysis (BL-22) found they form a recurring high melody that is independent of the playing, but not where it comes from. A phone recording made alongside a MIDI capture of the same playing would supply that ground truth.

In the code: `docs/specs/phone-audio-baseline.md`; DECISIONS 2026-09-28 (O-01, A-01, A-01b).

#### Which data could not be used, and what else does the pipeline depend on?

Three sources were wanted but are unavailable. MAESTRO-E (synthetic mistakes in MAESTRO, from the Polytune paper) requires a login and has an unclear licence, which is why the project wrote its own mistake generator. CIPI's scores are access-restricted, which is why PSyllabus and the PianoJudges index stand in. SKY-Piano (7 professional and 12 amateur pianists on a Disklavier, with a slow C-major scale played by all 19) would have been the ideal expert-versus-amateur evenness check, but it has not been released: its page has no download link, its code link returns "not found", and its data licence is described only as "per-modality terms" that are not published. An online explorer shows 5 professional sample trials, none of them scales or amateurs. D-09 was stopped.

A few assets are not datasets but are data the pipeline depends on:

- **The Salamander C5 Light soundfont** (a 25 MB sampled Yamaha C5 grand with 7 velocity layers) turns MIDI into audio. It was chosen because CrescendAI used the same file to render PercePiano, so R-03 could reproduce their audio. Its licence forbids resale or repackaging; the underlying samples are CC BY 3.0. The file is pinned by checksum. No loudness normalisation is applied to renders, because velocity is the signal, and 8 of the 1,202 PercePiano renders clip.
- **PERiScoPe metadata** (a 13 MB table) records which pieces the SyMuPe expression model saw paired with scores during its training, for the R-07 and R-10 split.
- **Model weights** for SyMuPe EncDec-base and Pianist Transformer (R-06) sit in the model cache, never in the repo. Both were trained on non-commercial data, so both are research-only in practice.
- **Listening-study stimuli** (552 MB): 8 excerpts from Vienna, Batik and (n)ASAP/MAESTRO, each rendered as the original, as 7 kinds of degradation at 5 levels, and as a catch trial. Built, not yet listened to.

In the code: `pianolens.audio.render` for the soundfont; `DATASETS.md` rows for each asset. Tickets D-09, S-02, S-03.

#### How is the data kept honest?

The data layer follows a few habits that make errors visible rather than silent. Every dataset has a manifest row giving its source, version or commit, licence, size on disk, loader, contents and load status, with download checksums where available. Every loader counts bad files and keeps going instead of crashing, and every "loaded" figure in this chapter comes from a full pass with a check script. Counts are compared against each paper or README, and every disagreement is written down rather than quietly fixed: (n)ASAP 1,066 against 1,067, PercePiano's 63 raters against 53, MAJEPPA's 4,449 against 3,979, NeuroPiano's 2,265 against 2,255, MazurkaBL's 46 mazurkas against 44. Everything under `data/interim/` and `data/processed/` is regenerated by a script, and test fixtures are tiny, either licence-checked excerpts or synthetic. Raw data must stay under 60 GB on the Mac, anything over 5 GB needs a note before download, and audio corpora belong on the GPU machine, with the PianoVAM subset as the one documented exception.

In the code: `DATASETS.md`; `.claude/rules/data.md`; the `fetch-dataset` skill; check scripts such as `scripts/check_asap.py`, `scripts/check_percepiano.py`, `scripts/check_dcml_romantic.py`.

#### Known gaps and untested assumptions

On provenance and capture:

- Rach3's instrument is unknown. It is tagged `sensor` on the assumption that its MIDI is exact. If it came from an inexpensive keyboard, its velocities would not be comparable with Disklavier velocities.
- Disklavier and Bösendorfer MIDI are treated as exact, but nothing in this repo measures their timing or velocity accuracy, and velocity scales differ between instruments. Pooling `disklavier` and `sensor` data in one velocity analysis assumes they are comparable. Untested.
- The transcription-noise figures rest on few pairs (6 for Transkun), all competition performances on a Disklavier, the transcribers' training domain. Noise on amateur pianos in ordinary rooms is measured only through PianoVAM, one room with one microphone setup.
- PercePiano's human segments are assumed to be Disklavier recordings because the paper describes their sources that way. The files themselves were not checked.

On labels and ground truth:

- (n)ASAP's ground truth mixes real slips with annotation errors, and 636 alignment ids point at tied notes absent from the score table. Everything that uses (n)ASAP as truth inherits this.
- PianoCoRe's alignments are automatic, about 9% of pairs are synthetic, and a filled-in note cannot be traced to a pianist's omission versus a transcriber's miss. Its tier A quality is the authors' judgement, re-checked here only for pitch agreement.
- The mistake set models mistakes rather than observing them. The weights in `MistakeSpec` were chosen by hand, not fitted to real errors, and real mistakes come with hesitations and restarts that version 1 does not inject. Validation on real human mistakes remains open (BL-10).
- The mistake set excludes pieces with repeats and pieces over 6,000 notes, which is where alignment is hardest.
- One PercePiano articulation scale has an undocumented direction, the 25-pianist count depends on an inferred numbering rule, and the listeners heard a different piano sound from the one R-03 rendered with.
- Only 337 of 1,202 PercePiano segments have a known position in the piece, and none of the 847 D.960 segments. Any analysis that needs position covers mainly WoO 80 and D.935.
- Expert-Novice's novice raters may be the players themselves; the files do not say.
- MAJEPPA's `score_coverage` is not a quality gate (28% of D-10 clips have a low match ratio). Its expertise labels come from video metadata, and its authors did not check transcription quality.

On ids and grouping:

- Piece ids are deliberately conservative, so 424 of 1,591 PianoCoRe tier A pieces keep prefixed ids, including very popular ones. The same piece could be canonical in one dataset and prefixed in another, which would let it sit in both training and test. This was not audited across all datasets.
- Performer ids are approximate: (n)ASAP merges pianists who share a surname, MAJEPPA splits one person across videos, and MAESTRO and many PianoCoRe rows have no performer. Leave-performer-out results on these sets are approximate.
- PianoCoRe holds about 34,000 same-audio duplicates and 68 transcriptions of (n)ASAP performances. Tier B is described as de-duplicated, but whether tier A analyses count some performances twice was not checked here.

On scores:

- DCML scores lack fermatas, slurs, pedal marks and key mode, and their rests are derived, so the LLM in R-08 saw less than a pianist reading the printed page.
- Four DCML repeat structures were resolved by hand, and one tie continuation (Liszt S.161 No. 4) was not inspected.
- MAJEPPA's score fixes rest on a hand-chosen 7% gap threshold and a "higher track is the right hand" rule; neither was checked against engraved scores, and unisons keep no hand.
- PianoCoRe bar numbers come from MIDI time signatures, not printed bars, so bar-level feedback needs a separate mapping to the printed score.

Not yet used or not available:

- Expert-Novice and NeuroPiano, the only ratings of real amateurs on disk, are loaded but unused.
- The rest of Rach3 (other pieces, the fourth pianist, the recital) and Hanon Part II were not downloaded or split.
- Only one beginner exists in the take data, so skill and player identity cannot be separated (BL-16).
- SKY-Piano, MAESTRO-E and CIPI scores are unavailable.
- Henry's recordings have no ground-truth MIDI and only one take per piece.


### Audio: from a phone recording to notes

Everything PianoLens scores is a list of notes: which key went down, when, how hard, when it came back up, and what the pedals were doing. A learner at home rarely has a piano that records this. They have a phone. This chapter explains how a phone recording is turned into a note list, which parts of that list can be trusted and which cannot, and why. The reasons come mostly from how a piano makes sound, so the chapter starts there before turning to the models, the measurements, and the tools built to test them. The results of the individual experiments are in Part 3 (A-01, R-03, R-05); here the focus is on method and reasoning.

#### How does a phone recording become a list of notes?

The front end is a short chain. The phone records the piano in a room. An automatic music transcription model listens to the recording and writes out a MIDI file, the standard note-list format of electronic music. For every note, MIDI stores the key number, the start time, the end time, and a "velocity" from 1 to 127 that stands for how hard the key was struck. From that point on, the note list goes through exactly the same alignment and scoring code as a recording made on a digital piano, with one difference: it is tagged as transcribed, and that tag switches the report into a lower-confidence mode for everything audio cannot measure well.

Two optional steps sit between transcription and scoring. A cheap sanity check looks for gross failures, such as one note split into two or notes outside the piano's range. An extra-note filter can remove notes that look like transcription artefacts; it is off unless the user asks for it, for reasons explained further down.

The local app runs this chain with a single transcriber, Transkun. It converts any upload to a 44.1 kHz WAV file, transcribes it on the Mac's GPU (falling back to the CPU if that fails), runs the sanity check, and applies the extra-note filter only on request.

In the code: `src/pianolens/app/pipeline.py`, `src/pianolens/audio/transcription.py` (`onset_sanity`), `src/pianolens/audio/extra_filter.py`.

#### What can a microphone actually hear of piano playing?

A piano note is made by a felt hammer thrown at a string. The hammer leaves the string before the note sounds, so once the key is down the player has no further control over the tone. The only remaining decision is when the note ends, which happens when a felt damper falls back onto the string as the key comes up. The sustain pedal (the right pedal) lifts every damper at once, so while it is down no string is stopped. A piano performance is therefore fully described by when each key went down, how fast its hammer was moving, when its damper returned, and the pedal state. That is why MIDI is a near-complete description of piano playing, and why transcription is worth attempting at all. It is also why each of these four quantities reaches the microphone with very different clarity.

**Note starts survive.** A hammer strike is a sharp burst of energy spread across a wide range of frequencies at once, what acousticians call a broadband transient. The sound goes from nothing to its loudest in a few thousandths of a second. Reverberation, the sound bouncing around the room, can only add energy after the direct sound arrives. It smears what follows the strike, but it cannot move the strike earlier or soften its leading edge much. A phone microphone cuts the lowest and highest frequencies, yet the strike carries energy across the whole middle of the spectrum, so it stays visible. The measurements agree. In the controlled check described below, Transkun's onset error had a robust spread of 2.3 ms both on clean rendered audio and on the same audio passed through a simulated phone; the phone changed nothing. On real microphone recordings of a player piano (the PianoVAM dataset) the median spread was 3.1 ms. The timing variation measured in Henry's own playing is 27 to 79 ms, an order of magnitude larger. Timing is the part of phone input that can be trusted.

**Note ends do not.** With the pedal up, a key release drops a damper on the string and the sound falls away quickly, which a transcriber can see. With the pedal down, releasing the key changes nothing: the string keeps ringing until the pedal comes up, so the release is acoustically invisible. In a reverberant room, even a properly damped note's end is blurred because the room keeps sounding after the string stops. Note ends are what articulation is made of (legato, where notes join, against staccato, where they separate), so articulation measured from audio is marked low confidence throughout the project. Evidence from elsewhere agrees: when the same performances existed both as player-piano MIDI and as Aria-AMT transcriptions (R-09), a timing-based measure kept its ranking across the two versions (rank correlation 0.95) while an articulation-based one did not (0.36).

**Loudness is only relative.** Velocity belongs to the hammer, but the microphone hears loudness and tone colour, which depend on velocity and also on many things the player does not control: how far the phone is from the piano and where it points, the microphone's sensitivity and the recording app's gain, whether the room is live or carpeted, the instrument itself, and on many phones an automatic gain control that turns the level up in quiet passages and down in loud ones, squeezing the dynamic range the player actually made. A transcriber learns the mapping from sound to velocity on the kind of recordings it was trained on. On a different recording chain that mapping shifts in two ways, an overall offset and a change in spread, which appear as the intercept and slope of a straight-line fit between true and transcribed velocity.

The measured slopes vary a great deal across chains, which is the direct evidence that absolute velocity from audio cannot be trusted:

| Recording chain | Transcriber | Velocity slope (1.0 = true spread) | Residual spread (MIDI units) |
|---|---|---|---|
| Rendered piano, clean (A-01 controlled check) | Transkun | 0.96 | 6.4 |
| Rendered piano, simulated phone | Transkun | 0.99 | 6.0 |
| Rendered piano, clean | Aria-AMT | 1.23 | 5.5 |
| Rendered piano, simulated phone | Aria-AMT | 1.31 | 6.0 |
| Microphone on a player piano, practice room (PianoVAM, median per recording) | Transkun | 0.92 | 4.5 |
| Professional performances with player-piano MIDI (D-10, 6 pairs) | Transkun | 0.64 | 9.0 |
| Same design, 59 pairs (D-10) | Aria-AMT | 0.95 | 5.7 |

For scale, the smallest velocity step listeners can hear is about 2.7 to 4.5 MIDI units (as cited in the D-10 spec). Every residual in the table is at or above that. What survives is the shape of the dynamics: this phrase swells, this note stands out from its neighbours. What does not survive is the absolute level, or any comparison of loudness spread between recordings made on different chains. The plan's remedy is a per-device calibration in which the user plays one note soft, medium and loud; it has not been built yet, so velocity from phone audio is kept out of the practice recommendations.

**The pedal is barely audible.** The pedal makes almost no sound of its own, so a transcriber has to infer it from its effects. Notes keep sounding after their keys would have come up, and with all dampers lifted, strings that were not struck begin to vibrate in sympathy with the ones that were, adding a faint halo. For the note being held, a held key and a held pedal sound identical; only the halo and the behaviour of other released notes separate them. A reverberant room produces a halo very like the pedal's, because it also keeps sound going after release. Pianists add to the difficulty with partial pedal and with "legato pedalling", lifting briefly just after a new chord and pressing again, which leaves short, partial events that reverb hides. In the controlled check the true sustain pedal was down 89% of the time; Transkun read 57% (clean) and 65% (phone), Aria-AMT 78% and 79%. Both under-read it. Transkun also reports the soft pedal (the left one); that output has never been checked against ground truth, and Aria-AMT does not produce it at all.

**Fast repeated notes are the hardest case.** When a key is struck again while its string is still sounding, no new pitch appears. The transcriber must detect a fresh strike on a string that is already loud, and the only cue is the new transient. If the repeat is quick or the pedal is down, the rise in energy is small. A grand's action is designed to allow a repeat before the key has fully risen, so real repeats can be closer together than a model might expect. The two ways of failing pull in opposite directions: merging two real strikes into one produces a missed note, and splitting one strike into two produces a false extra. The sanity check counts the second kind with a crude threshold.

The first kind was measured in BL-21, on PianoVAM's microphone recordings with the player piano's own MIDI as truth. A "repeat" there is a note whose same key was last struck less than 500 ms earlier, and the gap between the two strikes is called the inter-onset interval (IOI). Transkun found 97.6% of ordinary notes but only 33% of repeats closer than 80 ms and 89% of repeats at 80 to 120 ms; from 120 ms up the loss was under 2 points. Aria-AMT, run on a subset of 8 recordings, behaved the same way. Two things shrink the headline. Fast repeats are soft (median velocity 25 against 65), and soft notes are missed more often anyway; comparing each repeat with ordinary notes of the same velocity roughly halves the loss below 80 ms and leaves 4 to 5 points at 80 to 120 ms. And the auditor found that most of the sub-80 ms "repeats" are probably not intended repeats at all: 79% start within 5 ms of the previous note's release, at about half its velocity, and 88% stand alone rather than in a run, which looks like the player piano re-triggering or the key bouncing. Nobody has listened to them. With those echoes set aside, the measurable loss sits below about 100 ms, which for repeated sixteenth notes means a tempo faster than about 150 beats per minute. When the transcriber does lose a repeat it usually writes one note for the pair: 88% of the missed sub-80 ms repeats have a transcribed note of the same pitch within 100 ms. On the owner's five phone takes such fast repeats are rare, 57 of 8,926 score notes, and they account for 19 of the 575 missed notes. The report now treats a missed note as low confidence when its same-pitch predecessor in the score is due less than 100 ms earlier (BL-25). None of this has been measured on phone audio, whose gain control and codec could make soft repeats harder still.

**Quiet notes under loud ones can vanish.** A soft inner-voice note struck while louder notes are ringing adds little energy, and the room tail masks it further. This is a general expectation rather than something measured by note type here. On Henry's recordings, the missed-note rate (median 6.9% with Transkun) sat a little above the rate for transcribed professional recordings (3.8%), which is consistent with some masking but does not isolate it.

In the code: the confidence rules that follow from all this are in `.claude/rules/audio.md`.

#### What does a transcription model do, and why use two?

Automatic music transcription (AMT) means turning audio into a note list. Modern piano transcribers are neural networks trained on paired audio and MIDI, mostly the MAESTRO dataset: competition performances on Yamaha player pianos that recorded their own keys and pedals while microphones recorded the sound. This gives them excellent accuracy on audio that sounds like MAESTRO (a good grand, a good hall, close microphones) and a known tendency to overfit to that sound. The landscape review cites one study showing transcribers overfit to MAESTRO's acoustics and another showing that velocity is more fragile than onsets under changed conditions.

PianoLens uses two transcribers. **Transkun** (version 2.0.1, pretrained model 2.0) outputs notes, velocity, sustain pedal and soft pedal, and the landscape review calls it the strongest open piano model. From its authors' descriptions (not checked in this repo), it scores whole candidate notes as time intervals rather than labelling each short slice of time separately, then picks the best consistent set. It is fast, 11 to 17 seconds for a 3 to 6 minute recording on the Mac. It is also the transcriber that produced MAJEPPA, the skill-labelled dataset behind several experiments.

**Aria-AMT** (checkpoint `piano-medium-double-1.0`) is a sequence-to-sequence model: an encoder reads a 30-second window of audio and a decoder writes out the notes as a sequence of tokens, much as a speech recogniser writes out words. The repo's driver confirms this structure, with 30-second windows advanced 10 seconds at a time on audio resampled to 16 kHz. The landscape review lists it as robust to recording conditions. Its own command-line tool requires an NVIDIA GPU, so the project wrote a Mac driver that reuses the model, the per-window decoder and the stitching unchanged and replaces only the GPU plumbing. That driver runs in full 32-bit precision where the original uses 16-bit mixed precision, and takes 80 to 160 seconds per recording.

There are three reasons for running both. The first is that agreement between two models of different design is the only uncertainty estimate available when there is no ground truth, which is always the case for a learner's recording. If they agree, a finding is more likely to be in the audio than in one model's quirks; if they disagree, it is fragile. The second is fairness. The expert reference performances (PianoCoRe tier A) were themselves made by transcribing professional audio with Aria-AMT or Transkun V2, so a learner's transcription should be compared with experts transcribed by the same model family. The third is that they fail differently: in the controlled check Aria-AMT stretched the velocity range (slope 1.23 to 1.31) while Transkun kept it (0.96 to 0.99), and Aria-AMT's false notes tend to be longer than Transkun's.

Agreement has a limit worth stating plainly. Two models trained on similar data can share a blind spot. When both transcribers report the same extra notes on a recording, that shows the extras are in the audio. It does not show that anyone played them.

On Henry's recordings the two models agreed as follows:

| Measure | Range over the 5 recordings |
|---|---|
| Note F1 at 50 ms | 0.91 to 0.97 |
| Onset difference, robust spread | 4.6 to 6.0 ms |
| Velocity slope / rank correlation / residual | 0.82 to 0.96 / 0.80 to 0.88 / 6.4 to 9.2 MIDI |
| Overlap of per-note error labels (Jaccard) | 0.55 to 0.84 |
| Overlap of bars flagged for timing | 0.17 to 1.0 |
| Overlap of bars flagged for dynamics | 0.0 to 0.67 |

Timing flags mostly agree across the models and dynamics flags do not, which is the acoustics of the previous section showing up in the report.

In the code: `scripts/transcribe_aria_amt_mac.py`; A-01 in `docs/specs/phone-audio-baseline.md`.

#### How do we measure whether a transcription is right?

A transcription is judged by matching its notes against a reference, either the true MIDI when it exists or another transcription when it does not. The matching rules decide what counts as "the same note", and small choices here change every downstream number, so they are fixed in one module and reused everywhere.

Two notes match if they are on the same key and their start times are within a tolerance, 50 ms by default, and each note may match at most once. The 50 ms tolerance is the standard of `mir_eval`, the reference evaluation library for transcription, which keeps the numbers comparable with published work. Only note starts are compared. Given what the previous sections say about note ends, an end-time criterion would mostly measure the pedal and the room rather than the transcriber. The algorithm walks each key's notes in time order and gives each reference note the earliest unused candidate within tolerance. With one fixed tolerance on a time line, this greedy rule already finds the largest possible set of one-to-one matches, so no search is needed. The outputs are precision (the share of transcribed notes that match a real one), recall (the share of real notes found), F1 (a single summary of the two), and the mean and spread of the onset errors.

The two note lists often run on clocks that differ by a constant: a recording trimmed at the start, a MIDI file whose first event is not at zero, or a transcriber with a fixed delay. So the matcher can first estimate that offset. It matches loosely at 0.2 s, takes the median time difference of those matches, subtracts it, and matches again at 50 ms. The median is used because a few wrong matches in the loose pass cannot drag it far. On PianoVAM the estimated offsets ran from -18 to +7 ms; an uncorrected 18 ms shift would eat a third of the tolerance. The step removes only a constant shift, though. D-10 found that Transkun's clock can wander over a piece (an onset-error spread of 38.5 ms overall against 9.3 ms once slow drift is removed), and such drift is not corrected here.

Spreads are reported as a robust standard deviation: 1.4826 times the median absolute deviation. For normally distributed errors this equals the usual standard deviation, but a handful of bad matches near the 50 ms edge cannot inflate it.

Velocity agreement is summarised by a straight-line fit of one velocity list on the other, over matched notes. The slope says whether the transcriber squeezes the dynamic range (below 1) or stretches it (above 1). The rank correlation says whether louder notes are at least ordered correctly, which is all that relative dynamics needs. The residual spread, in MIDI units, says how noisy individual notes are once level and range are accounted for. This split mirrors the acoustics: level and range belong to the recording chain, rank and residual to the transcriber.

The sanity check flags gross failures on any transcription:

- the share of notes whose same-key predecessor started less than 50 ms earlier, a likely split note (the code's reasoning is that a piano cannot repeat that fast; no measurement of the real limit was made);
- the share of notes shorter than 30 ms;
- the share of pitches outside the 88 keys (MIDI 21 to 108);
- notes per second, and the mean and spread of velocity.

Pedal use is summarised as the number of presses, the share of time the pedal is down, and the median press length. "Down" means a MIDI pedal value of 64 or more, the half-way point, which treats the pedal as simply on or off. Half-pedalling, which pianists use constantly, is flattened into one state or the other.

In the code: `src/pianolens/audio/transcription.py` (`match_notes`, `note_f1`, `robust_sd`, `velocity_agreement`, `onset_sanity`, `pedal_summary`); tests in `tests/audio/test_transcription.py`.

#### Why render MIDI back to audio with one fixed piano?

Several parts of the project need to turn a note list back into sound: the audio-model experiments, the controlled test of the phone chain, the stimuli for listening studies, and the app's side-by-side comparison, where a learner's playing is re-rendered next to an expert's. All of them use one fixed piano sound, rendered the same way every time.

The reason is control. If two renders differ, the difference should come from the playing and never from the instrument, the room or a software version. A fixed piano removes timbre as an explanation, which is the same logic as the recording-context problem later in this chapter: anything that varies with the label and is not the playing is a shortcut. A second reason is reproduction. CrescendAI's published audio-model results on PercePiano used this exact sample library and synthesizer call, and testing their number (R-03) required the same audio. A third is that determinism makes every audio result re-runnable bit for bit; the R-03 audit re-rendered eight files and got identical checksums.

The piano is the Salamander Grand Piano, in its "SalamanderC5-Light" SoundFont conversion: a set of recordings of a real grand at 7 loudness layers, 44.1 kHz, which a synthesizer plays back. The file's checksum is pinned in code and in `DATASETS.md`. The synthesizer is FluidSynth (tested with 2.6.1), called as CrescendAI called it with two changes. Every setting that shapes the sound (reverb, chorus, polyphony, interpolation) is passed explicitly at FluidSynth 2.6.1's defaults, so an upgrade that changes a default cannot silently change the piano; CrescendAI inherited those defaults from a version they did not record, which may explain part of R-03's small reproduction gap. And the output is written as 32-bit float rather than 16-bit, which skips a dithering step that adds random noise from run to run and keeps any peak above full scale measurable instead of clipped.

FluidSynth renders in stereo at 44.1 kHz. The module averages the channels to mono and resamples with a high-quality resampler to 24 kHz, the input rate of the MuQ audio model, which is what CrescendAI's loading code did. FluidSynth keeps rendering for about 2 to 3 seconds after the last note, so release tails are kept, and nothing is trimmed.

Loudness is not normalised by default. MIDI velocity is the performer's dynamics, and scaling every file to the same loudness would erase exactly what raters were judging. The level is set by the synthesizer gain (0.8) alone, identical for every file. Peak and perceived-loudness (LUFS) normalisation exist only for listening stimuli where a study protocol explicitly asks for level-matched clips. If a render peaks above full scale, the peak is recorded so callers can check. In R-03 eight files did (peaks 1.008 to 1.178), all of them the flat computer renditions in PercePiano, and removing them changed results only through their absence, not through the clipping.

When a performance is written to MIDI for rendering, times are rounded to 1/1920 s, about half a millisecond, far below any timing effect studied. Where a key is released and struck again at the same instant, the release is written first so the new note is not cut short.

The fixed piano has limits. It is not the piano PercePiano's raters heard (a Logic Pro instrument), so any judgement of tone colour is learned from a sound the raters never heard. FluidSynth's reverb and chorus are on, so the "clean" render is not dry. And, as far as we know, sample playback of this kind does not model strings ringing in sympathy under the pedal; the pedal only stops notes from ending. That was not checked, and it matters for one of the hypotheses below.

In the code: `src/pianolens/audio/render.py`; tests in `tests/audio/test_render.py`; S-02.

#### How was a phone simulated, and what did the simulation show?

The only way to know how much error the phone chain adds is to start from audio whose true notes are known. A render has known notes, so the project built a simple degradation that makes a render sound roughly like a phone in a room, then transcribed both versions and compared them with the truth. The module is deliberately simple and, as its own documentation says, not calibrated to any real phone or room. It asks "does this kind of degradation hurt transcription?", not "is this what Henry's phone does?".

The chain applies, in order, a room, a microphone, noise, a level change and a codec. The room is a synthetic impulse response: the direct sound followed by random noise that decays exponentially, the standard statistical model of a reverberant tail. The microphone is two gentle filters that cut low and high frequencies. The noise is pink noise, which has equal energy per octave like most room and electronic hiss. The level step scales the file to a fixed peak, a crude stand-in for automatic gain. The codec step, done outside the module with ffmpeg, encodes to AAC and decodes again, because Henry's audio came through YouTube, which delivers AAC or Opus. Every random step is seeded, so the same input and settings always give the same output. The A-01 settings and the reasoning for each were:

| Step | A-01 setting | Reasoning |
|---|---|---|
| Room | reverberation time (RT60, the time for sound to fall by 60 dB) 0.5 s; direct-to-reverberant ratio 3 dB | A domestic room, with the phone hearing slightly more direct sound than room sound. Judgement, not measurement. |
| Low cut | 2nd-order high-pass at 120 Hz | Small phone microphone capsules and voice processing cut the low end. |
| High cut | 2nd-order low-pass at 12 kHz | Lossy codecs drop the top of the spectrum. |
| Noise | pink noise 35 dB below the signal | A quiet room with some background noise. |
| Level | peak at -3 dBFS | The phone fills its range. |
| Codec | AAC at 128 kbit/s, back to mono 48 kHz | YouTube-like delivery. |

Several things a real phone does are left out: early reflections (the first distinct echoes off nearby walls, floor and the piano lid), gain control that changes over time, dynamic range compression, noise suppression, microphone distortion, the direction-dependent way a piano radiates sound, and of course a real acoustic piano.

The controlled check applied this to three MAESTRO player-piano performances of pieces Henry had also recorded (MAESTRO holds three of his five pieces). Each was rendered, transcribed clean and through the simulated phone by both models, and scored against its true MIDI:

| Condition, model | Note F1 (50 ms) | Onset error spread | Extra notes | Sustain down, read vs true |
|---|---|---|---|---|
| clean, Transkun | 0.989 | 2.3 ms | 2.3% | 0.57 vs 0.89 |
| phone, Transkun | 0.986 | 2.3 ms | 2.6% | 0.65 vs 0.89 |
| clean, Aria-AMT | 0.982 | 4.4 ms | 3.5% | 0.78 vs 0.89 |
| phone, Aria-AMT | 0.979 | 4.5 ms | 4.0% | 0.79 vs 0.89 |

The simulated phone cost less than one point of error rate and did not touch onset precision. Most of the extra notes it did produce were overtones: 39 to 75% sat an octave or another harmonic interval above a note struck at the same moment, the classic transcriber mistake of hearing a strong overtone as a separate note. What the simulation did not do was reproduce the extra notes found on Henry's real recordings. Either it leaves out whatever matters, or the cause lies outside the phone chain; BL-22 later pointed to the second (see "Where do the phantom high notes come from?"). BL-22 also measured one clear way in which the simulation differs from the real chain: the real takes carry far less energy above about 3 kHz. In the 3 to 6 kHz range all five takes sit 6 to 13 dB below PianoVAM's microphone audio and 13 to 19 dB below the rendered audio, while the simulation's high cut is at 12 kHz. Whether the phone, the YouTube encode or the room and instrument cause this cannot be told apart. Two caveats apply: MAESTRO audio is both transcribers' training domain, and one of the three MIDI files is in MAESTRO's training split (with a different piano sound here, so not an audio leak).

In the code: `src/pianolens/audio/phone.py` (`PhoneSimConfig`, `room_ir`, `pink_noise`, `simulate_phone`); `scripts/a01_controlled_check.py`; tests in `tests/audio/test_transcription.py`.

#### How good is transcription on a real learner's phone recording?

The test case is Henry's own playing: five Chopin pieces, one take each, played on a grand piano and recorded with a phone, then uploaded to YouTube, so the audio is lossy. These are personal recordings; the audio, the derived MIDI and the reports stay in private, git-ignored folders, and only aggregate numbers appear in the project's documents.

Nobody knows the true notes of these recordings, so they cannot be scored against ground truth. Instead they are compared with a transcription floor: what a professional performance of the same piece looks like after it has been transcribed. For each piece, 15 expert references per transcriber family, 150 in all, went through exactly the same alignment and correctness code. A professional's apparent error rate is not zero. It includes differences of edition and repeats, and genuine transcription errors. The median was 6.7% for Transkun references and 8.2% for Aria-AMT. Even the player-piano MIDI of the controlled-check performances, with no transcription at all, scores 7.4% with this checker. A learner's numbers are read against this floor, never against zero.

Against the floor, most of Henry's numbers look ordinary. With Transkun, the median wrong-note rate was 1.0% (floor 0.6%) and the missed-note rate 6.9% (floor 3.8%). The exception is extra notes: a median of 15.5% against 1.3% for the floor, with three of the five takes at 15 to 29%. Both transcribers agree on these extras, so they are in the audio.

Those extras have a distinctive signature. Many sit high, at G6 (MIDI 91) or above, reaching up to 19.5% of score notes, against at most 0.2% in the controlled check. They cluster on the same few pitches in every recording, G6, C7, D7 and E7 (MIDI 91, 96, 98 and 100), whatever key the piece is in. They are short (median 67 ms) and no quieter than the notes around them. Unlike the simulated phone's extras, they are mostly not overtones: only 3 to 13% sit a harmonic interval above a note struck at the same moment, and 83% of the high ones have no harmonic source at all. Nor do they repeat a note just played. The middle-register extras on the same recordings are a separate, unexplained problem; in one piece, one of the 15 expert transcriptions shows the same count in the same bars, which points to an edition or repeat difference rather than playing.

The practical conclusion was a set of trust rules for phone input. Timing and tempo are trusted: transcriber onset error is small next to real timing variation, and the two models flag mostly the same bars. Velocity and pedal are not trusted. Wrong and missed notes are trusted only relative to the per-piece floor. Extra notes are not trusted at all on transcribed input: they never count toward the correctness grade, and a report adds a warning when extras at G6 or above exceed 2% of the score's notes.

In the code: `scripts/a01_henry_baseline.py`, `scripts/a01_henry_reports.py`; A-01 in `docs/specs/phone-audio-baseline.md`.

#### Where do the phantom high notes come from?

Three explanations were on the table after A-01. The first was sympathetic string resonance with the pedal down: with every damper lifted, undamped treble strings ring along with the notes being played, and a distant phone with automatic gain might lift that halo enough for a transcriber to read it as notes. The second was something sounding in the room, such as a rattle or the piano's own action. The third was the phone and delivery chain, for example noise suppression or the YouTube re-encode creating short high artefacts. BL-22 set out to tell them apart from the existing audio and transcriptions, with the tests and their reading written down before any of them was computed. Nobody has yet listened to the passages, so this is a data analysis: it can make an explanation more or less likely, but it cannot settle the source.

Four tests were planned. Each is described here with what it found.

**Are the extras tied to the pedal?** Resonance needs the dampers lifted, so the extras should cluster where the pedal is down. The test could not run. The transcriber reads the pedal as down for 87 to 97% of every take, and the pre-registered rule needed at least 10% of pedal-up time. What can be said is weak: 26 of the 409 high extras (Transkun) fall where the pedal reads as up, about the share expected from the pedal-up time, and the transcriber's pedal reading is itself unvalidated.

**Are the extras overtones of notes being played?** An overtone (or partial) is one of the higher frequencies a string sounds above its main pitch, and transcribers sometimes report a strong one as a separate note. The test asks how often an extra sits on partial 2 to 6 of another note, and compares that with a null: the same count for pitches shuffled at random. The useful summary is the implied overtone share, f = (h - q) / (1 - q), where h is the observed hit rate and q the null's: roughly, the fraction of extras that the overtone explanation needs. Counting only notes struck within 50 ms of the extra, f is 0.01 for Transkun and 0.08 for Aria-AMT, against 0.23 for PianoVAM's ordinary false extras and 0.74 to 0.97 for the extras on rendered audio, where overtones are known to be the cause. So overtones explain at most a small minority. The pre-registered primary test, which counted every note in the previous 2 seconds, turned out to be weak: with so many candidate notes almost any high pitch is a partial of something (q about 0.61), so the largest reachable ratio to the null was 1/q, about 1.64, and even the rendered positive controls could not reach the planned "at least 1.5 times the null". The auditor flagged this as a repeat of the reachability lesson (Part 4).

**Are they fixed in pitch, and do they sound in silence?** The same four pitches, G6, C7, D7 and E7, are the top four in all three affected takes (68 to 74% of their high extras), although the pieces are in B major, C-sharp minor and B-flat minor, and half or more of the extras sit on pitches the take never plays correctly. This test is not independent, because A-01 had already described fixed pitches. The extras are not bursts in silence: 93% occur while notes are being played, and the audio at an extra is on median 1 to 1.5 dB quieter than at a random moment, which fits a quiet source running alongside the playing.

**Is there real sound at the reported pitch?** In a spectrogram (a picture of how much energy each frequency carries over time), a real extra should show energy at its pitch, while a transcriber hallucination need not. The extras' pitch stands about 10 dB above neighbouring frequencies, against 13 dB for correctly played high notes and 0 dB for random points, and it appears abruptly. So the transcribers are hearing something real. A further check found the extras are not misplaced copies of missed notes an octave or a partial lower (0.5% of them, against a null of 0.8%).

**What the auditor found: a melody.** By the letter of the pre-registered mapping, "not overtones" plus "fixed pitch" meant "room or phone artefact". The auditor confirmed every measurement but returned that reading, because the "fixed pitches" turned out to be the scale of a tune. 97% of the 422 high extras (Transkun, all five takes) are white keys of one C-major octave, G6 to G7. Consecutive extras less than 0.6 s apart move by at most 2 semitones in 71 to 76% of pairs, against 38 to 39% when the pitches are shuffled, and they come at about 3 notes per second. The same phrases recur in every affected take: 9 exact four-note sequences are shared by all three, against a null average of 0.04. The extras are no more likely than a random moment to coincide with a struck note, and they sit a median 20 to 27 semitones above the highest note played in the second before, so they are neither triggered by the strikes nor grazed neighbouring keys. Their measured pitch follows the slightly stretched tuning of this piano rather than standard tuning, which is suggestive only.

The reading adopted after the audit is that **most of the high extras are a second, independent musical sound in the recordings**: a quiet, high, stepwise C-major melody that is the same in every affected take and has nothing to do with the Chopin being played. That rules out the phone chain and a room resonance as the main cause, since neither plays a recurring tune. It rules out transcriber hallucination, since both transcribers find the notes and there is real energy at each pitch. And it makes sympathetic resonance unlikely as the main mechanism, since the pitches ignore both the key of the piece and the notes being struck. What it cannot exclude is that the piano's undamped strings ring along with an outside tone, which could explain why the melody is tuned like this piano. An earlier draft argued against resonance because the extras lack a second partial; the audit dropped that argument, because a string driven by an outside tone rings mainly at the driven pitch.

Where the melody comes from, and whether it was in the room or added when the video was edited, cannot be told from the data. Three things would settle it: the owner's listening check, which asks whether a quiet separate high tune is audible, what it sounds like, and whether it is already there in the first seconds before the playing starts; the original phone files from before the upload, if they still exist; or a second recording chain (O-01). If the melody is confirmed, the takes are contaminated by a second source, which is not a flaw of phone recording as such, and a matching filter would look for a coherent off-score stream: stepwise, regular, and not tied to the played notes.

In the code: `scripts/bl22_phantom_extras.py` (`labels`, `analyse`, `spectro`, `posthoc`); pre-registration in `docs/specs/phone-audio-baseline.md`; `experiments/2026-09-29-BL-22-phantom-extras/`; outputs stay under `data/interim/` because they are personal. Tickets BL-22 and O-01.

#### Can the phantom notes be filtered out safely?

If the extras cannot be prevented, perhaps they can be removed before scoring. The danger is asymmetric. Keeping a false note produces a false "extra note" flag, which is already ignored on transcribed input. Deleting a real note produces a false "missed note" and blames the player for something they did right. So the filter was built safety first: decide how many real notes it may cost, then see how much it can remove within that budget.

Each transcribed note is described by 13 features computed from the transcription alone, with no score and no ground truth, so the filter can run on anything. They cover the note itself (pitch, velocity, log duration), its loudness relative to what is around it (against the median of notes within 1 second and the loudest note within 50 ms), how crowded its surroundings are (notes within 50 ms and within 1 second), whether it could be an overtone, how isolated it is in pitch (its distance above the highest nearby note and to the nearest one, within half a second), the time since the same key last sounded, and a "pitch spike" score that measures how much more often this pitch occurs in the whole file than its four neighbouring keys. The overtone feature asks whether some note 12, 19, 24, 28, 31, 34 or 36 semitones below starts at the same moment or is still held. Those are the distances of overtones 2 to 8 above a fundamental, rounded to the nearest key. A real piano's overtones run slightly sharp of these ideal values because its strings are stiff, which rounding absorbs for the lower overtones. The pitch-spike score is aimed squarely at the fixed-pitch signature.

The natural move would be to train a classifier on audio with ground truth. PianoVAM provides that: a microphone on a player piano in a practice room, amateur players, with the player piano's own MIDI as truth. The project used 84 recordings from 10 pianists, 343,550 true notes, transcribed with Transkun. A transcribed note with no true note on the same key within 50 ms, after removing the clock offset, counts as a false extra. The surprise was how clean it is. False extras were 0.26% of true notes, and almost none were high (0.007% at G6 or above). They were ordinary transcriber mistakes: middle register, quiet (a median 15 velocity units below their surroundings), short, and 44% with a harmonic source. Real-room microphone audio simply does not produce the phone recordings' signature.

That is why the filter is not trained on PianoVAM. A gradient-boosting classifier on the 13 features, trained on nine pianists and tested on the tenth in turn, learned PianoVAM's own kind of extras, which are not the phone kind. Because extras are so rare there, any removal threshold catches mostly real notes: of 1,742 notes it removed, only 194 (11%) were false. It lost 0.46% of true notes and lowered note F1 from 0.9853 to 0.9833. On the professional reference floor it removed 449 Transkun notes, 365 of them correct. It is not used, and the lesson is now a project rule: do not tune a phone extra-note filter on clean real-room audio; use such audio only to check a filter's safety, counting the high register separately.

What is used instead is a transparent rule written for the signature. A note is removed only if all of the following hold:

- its pitch is C7 (MIDI 96) or higher;
- no note a harmonic step below starts with it or is still held;
- it is shorter than 100 ms;
- its pitch occurs at least as often as its neighbours (pitch spike of at least 0.5);
- any loudness.

The settings came from a fixed procedure. A safety budget was set first, measured on PianoVAM: at most 0.1% of all true notes removed, and at most 5% of true notes at G6 or above. A grid of 240 combinations of pitch floor, duration cap, spike threshold and relative loudness was searched. Among the combinations inside the budget, the tie-break was whichever removed the most notes from Henry's Transkun recordings. That tie-break uses no labels, so it does not peek at the score, but it does tune the rule on the same recordings it is then applied to.

| Check | Result |
|---|---|
| PianoVAM, held out by pianist: true notes lost | 0.10% overall (one fold chose a looser rule); 4.3% of true notes at G6 or above |
| PianoVAM: false extras removed | none, because none have the phone signature; PianoVAM tests only safety |
| Professional references, Transkun | 55 of 129,981 notes removed (0.04%), all of them correct notes |
| Henry's recordings, Transkun | 142 removed, 141 of them extras against the score; 33% of the high extras (141 of 422), 12% of all extras |
| Extra rate on the three affected recordings | still 14 to 22% after filtering, against a floor of 1 to 2% |
| Henry's recordings, Aria-AMT | 2 notes removed in total, because its artefacts are longer than 100 ms |

The rule is safe but does not solve the problem. Its floor is C7, so it never reaches the G6 extras; it keeps longer artefacts; and the middle-register extras are a different problem altogether. Its real benefit on phone audio cannot be measured without phone ground truth, and it is validated for Transkun only. It is therefore opt-in and off by default, and when it runs, the report says how many notes it removed. A test pins its default settings, because changing them would invalidate the validation numbers. BL-22 also changes what a better filter would look like: if the extras are a second melody, the thing to detect is a coherent stream of notes that moves by step at a steady rate and ignores the playing, not a property of single notes.

In the code: `src/pianolens/audio/extra_filter.py` (`note_features`, `rule_scores`, `filter_midi`, `label_false_extras`, `ExtraNoteFilter`); `scripts/a01b_extra_filter.py`, `scripts/a01b_transcribe_pianovam.py`; `scripts/pianolens_report.py --filter-extras rule`; tests in `tests/audio/test_extra_filter.py`; A-01b and BL-13.

#### What does a large audio model hear, and can we trust it?

The project's central bet is that a few interpretable features of the notes can do as well as a large audio model at judging performance. The audio model to beat is MuQ, a large neural network pretrained on a great deal of music by self-supervision, meaning it learned by predicting hidden parts of its own input without any human labels. Passing audio through it yields an embedding: a long list of numbers for each short time step, summarising what the audio sounds like. A small network trained on top of the embedding can then predict ratings. CrescendAI reported that frozen MuQ with such a head predicts the PercePiano expert ratings with R² 0.536, and R-03 set out to test that claim before comparing anything against it.

The recipe was rebuilt from CrescendAI's code rather than their paper, because the two disagree in places. The model is `OpenMuQ/MuQ-large-msd-iter`, run in full 32-bit precision on the fixed-piano render at 24 kHz mono, the whole clip in one pass. The project rule requires fp32 and 24 kHz; the reason for fp32 is not recorded. The embedding is the average of hidden layers 9 to 12, taken over the first 1,000 time steps, which is 40 seconds at 25 steps per second. CrescendAI's documentation says 300 steps, but their code and saved configurations say 1,000, and using 300 lowered results by about 0.02. Each dimension is then summarised by its mean and standard deviation over time, 2,048 numbers per clip, and a small two-hidden-layer network predicts the 19 rating dimensions.

The headline reproduced, just: 0.509 against 0.536, inside the pre-registered band. With honest validation on the same split it fell to 0.460. On works the model had never heard, the split the project requires, it collapsed to R² -0.087, worse than predicting the average rating. What survived was a modest ability to order performances of the same passage, correct about 62% of the time, roughly what a single human rater manages. Part even of that came from recognising PercePiano's flat computer renditions: without them, the within-passage R² fell from 0.155 to 0.063. A layer-by-layer probe rose to about layer 6 and was flat after that, with no single best layer. R-04 then found that 62 interpretable note features match frozen MuQ on unseen works.

The limit that matters for this chapter is that every MuQ result in the project comes from rendered audio. Rendering removes all differences of room, microphone and instrument by design, which is fair to MuQ on PercePiano, whose audio was rendered anyway. It says nothing about how MuQ behaves when those differences are present and correlated with what is being predicted. That is the next question.

In the code: `experiments/2026-09-27-R-03-muq-percepiano/` (`extract.py`, `run.py`); render config via `src/pianolens/audio/render.py`.

#### Can an audio model mistake the recording room for skill?

In skill datasets, the recording setting travels with the skill level. Beginners record practice on a phone at home; virtuosos are recorded in concert halls with good microphones. A model that can hear the room can "predict skill" without listening to the playing at all. Such a shortcut looks accurate on the dataset and fails on any new recording where the setting does not follow skill, which is exactly the situation of a learner using PianoLens. The project's hard rule 3 requires every skill claim to be checked for it. The hypothesis that audio-model skill accuracy partly reflects recording context is H8.

Audio embeddings are especially exposed, for reasons that follow from the acoustics earlier in the chapter. Reverberation, bandwidth, noise and codec change the whole spectrum all the time, so they are among the most obvious things an embedding represents. Skill lives in small differences of timing and loudness, which are the subtle part.

MAJEPPA, the skill-labelled dataset, has only transcribed MIDI and no audio, so R-05 used a substitute design that isolates the mechanism. It took 1,500 clips, 250 per skill level, and rendered the first 30 seconds of each with the fixed piano, so every clip has identical piano sound. Each clip was then degraded into four simulated recording contexts with the phone simulation plus an AAC round trip: a clean close microphone, a phone in a living room, a phone in a recital-hall audience, and a concert hall, each with settings drawn per clip from ranges chosen by judgement. Every version was peak-normalised, so loudness alone carries no context information. Frozen MuQ embeddings (layers 9 to 12) fed a simple logistic-regression classifier for beginner against advanced, with cross-validation grouped so that no piece or source video appears in both training and test. The comparison is between contexts held fixed for everyone, contexts assigned as they actually are in MAJEPPA, and the confounded model tested with contexts shuffled.

| Condition | Beginner vs advanced AUC (0.5 = chance) |
|---|---|
| Simple MIDI statistics only (note rate, velocity, pitch) | 0.760 |
| The context label alone (a pure shortcut) | 0.867 |
| MuQ, context held fixed | 0.870 |
| MuQ, contexts as in MAJEPPA | 0.943 |
| Same model, test contexts shuffled | 0.730 |
| Same model, contexts swapped between classes | 0.475 |

MuQ identifies the simulated context almost perfectly (balanced accuracy 0.997 across four contexts). With the real confound, apparent skill accuracy rises by 0.073 even though the audio holds no more skill information, and the confounded model loses 0.214 once context stops following skill. The inflation is largest where the confound is strongest: piano teachers, mostly recorded as clean demonstrations, against beginners scored 0.778 with context fixed and 0.958 confounded. A negative control, with contexts assigned at random and independent of skill, gave no gain, so the effect is not just "more varied audio helps".

The audited reading is careful about what this shows. The mechanism is demonstrated: a frozen-MuQ skill probe uses recording context about as much as it would use an explicit label naming the context. The size does not carry over to real audio. The four simulated contexts barely overlap and are easier to tell apart than real ones, while real recordings differ in more ways, such as piano quality and audience noise. Even the 0.87 with context held fixed is not a clean skill measure, because beginners play easier and slower pieces and simple note statistics alone reach 0.76. For PianoLens the result is one more reason to score notes against experts playing the same piece, rather than scoring raw audio, and to read any phone result against a floor for the same recording chain.

In the code: `experiments/2026-09-28-R-05-context-shortcut/` (`build.py`, `analyze.py`, `reachability.py`); `src/pianolens/audio/phone.py`; R-05, H8.

#### Known gaps and untested assumptions

Phone ground truth:

- No recording in the project has both a real phone capture and the true MIDI of the same playing. Every claim about the phone chain rests on a simulation, a different microphone setup (PianoVAM), or two transcribers agreeing. A simultaneous phone plus MIDI take (O-01) would fix this.
- The simulated phone is not calibrated to any phone or room and reproduces neither the level nor the kind of Henry's extra notes. It also keeps far more high-frequency energy than the real takes, which roll off steeply near 3.3 kHz (BL-22).
- The simulation's gain step is one fixed scale for the whole file. Real phone gain control varies over time and compresses dynamics; its effect on velocity was never modelled.

The phantom high notes:

- The source of the second melody is unknown, including whether it was in the room or added in the video edit. The melody reading rests on the auditor's sequence analysis, which was not pre-registered.
- The listening check has not been done, and the original phone files have not been examined.
- The pedal test could not run, because the transcribers read the pedal as down almost all the time, and their pedal reading is unvalidated.
- Sympathetic resonance is disfavoured as the main mechanism but not excluded as a contributor: undamped strings could ring along with an outside tone.
- It is one player, one piano and one recording chain.
- The middle-register extras on the same recordings are still unexplained.

The extra-note filter:

- Its usefulness was measured only on the same five recordings its tie-break was tuned on, and only against the score, not against true MIDI.
- It is validated for Transkun only and does almost nothing on Aria-AMT output.
- PianoVAM checks its safety, not its recall.
- The app and the report load the rule's settings from a cross-validation file when it exists and fall back to the code defaults otherwise. They agree today; a regenerated file with different results would silently change the rule.

Transcription measurement:

- The clock-offset step removes only a constant shift. Transkun's clock can drift over a piece (D-10), which may lower match rates on long recordings; this was not quantified for the phone takes.
- Fast repeated notes were measured only on PianoVAM's microphone audio (BL-21), not on phone audio, and the rendered check contains almost no fast repeats. Most sub-80 ms repeats in PianoVAM look like key bounces or player-piano re-triggers that nobody has listened to. The report's 100 ms low-confidence rule for missed repeats (BL-25) is not validated on phone recordings.
- The 50 ms double-trigger threshold of the sanity check is an assumption, not a measured limit of piano repetition.
- Transkun's soft-pedal output has never been checked against ground truth.
- The pedal summary treats the pedal as on or off; half-pedalling is not represented.
- The Mac driver for Aria-AMT runs in full precision instead of the original's mixed precision and was not compared file by file with the official GPU tool.
- On PianoVAM the onset spread sits at 3.089 ms in many files, which looks like time quantisation in the data; small differences in that figure should not be over-read.

Velocity and pedal:

- Per-device loudness calibration (A-03) has not been built, so velocity from any phone stays relative only.
- The controlled check's velocity fit uses a sampled piano with 7 loudness layers, whose loudness curve differs from a real grand's.
- The sustain pedal is under-read by both transcribers in the controlled check and has not been measured in real rooms.

The transcription floor:

- The floor comes from professional recordings (good pianos, microphones and halls) run through the transcribers. It is the floor for that recording chain, not for a phone, so phone-specific error is not in it.
- The controlled check uses MAESTRO performances, the transcribers' training domain.

Transcriber adaptation:

- Fine-tuning a transcriber on phone-like audio (A-02) has not been done. Its training audio should include far-field recordings of grands, not only close-miked audio.

The audio model and H8:

- MuQ has never been run on real recorded audio in this project; every result is on renders.
- The reason for the fp32 rule is not recorded.
- Only the first 40 seconds of each PercePiano clip are used; 259 of 1,202 clips are longer and are truncated.
- H8 on real audio needs MAJEPPA's YouTube audio, which is an owner decision. The R-05 context settings are judgement, not measurement.
- The app transcribes with Transkun only, so its users do not get the two-model cross-check.


### Score alignment and note correctness

Before PianoLens can say anything about a performance, it has to know which written note each played note was meant to be. That link is called an alignment: a list that pairs every note in the score with the performed note that realises it, and marks the leftovers on both sides. Everything else in the project stands on it. Tempo curves are built from the times of matched notes, evenness is measured over matched runs, hand synchrony compares matched notes on the two staves, and the expert comparison maps bars through matched notes. Tier A, note correctness, is the most direct use: once every note is paired, the unpaired ones are the mistakes.

This chapter explains how the pairing is made, how its quality was checked, how the leftovers are turned into the labels a student sees (wrong note, extra note, missed note), and where the method is known or suspected to break. The experiment results are in Part 3; this chapter is about the method and the reasoning behind it.

#### What information do we start from, and why is it enough?

A piano note is unusually easy to describe completely. The player chooses which key, when it goes down, how fast (which sets the loudness), and when it comes up, plus the pedals. Once the hammer leaves the string, nothing else the player does changes that note. A MIDI file from a key-sensing piano (a Disklavier or similar) records exactly those choices, so for the question "were the right notes played?" MIDI loses nothing that matters.

The score side is a digital score file, usually MusicXML, read with the partitura library. Each written note carries a pitch, a position in the piece (in beats and in quarter notes), a duration, a staff number (upper or lower stave), a voice number, a flag saying whether it is a grace note (a small ornamental note printed before a main note, played quickly and not counted in the bar), and any ornament signs such as trills. A piano score is often stored as two parts, one per stave; they are merged into one part first so that both hands are aligned together.

The performance side is the list of played notes: onset time in seconds, key-down duration, pitch, velocity and an id. Durations are the time the key was held, not the time the sustain pedal kept the string ringing; partitura extends durations to the pedal release by default, and the project stores key-down durations instead.

In the code: `src/pianolens/align/_adapters.py` (accepts files, partitura objects or the project's own types), `load_score_part` in `src/pianolens/align/core.py`.

#### Which repeats did the pianist play?

Scores contain repeat signs, first and second endings, and "da capo" instructions (go back to the start). A pianist may take every repeat, skip some, or skip all. The score file, however, stores each written bar once. To compare it with a performance, the score has to be "unfolded": written out as the linear sequence of bars the pianist actually went through. Choosing the wrong unfolding is not a small error. If the score is unfolded with a repeat the pianist skipped, a whole section of score notes looks missed; if a taken repeat is left out, a whole section of played notes looks extra.

partitura can list every legal path through a score's repeat structure. Each path is named by its sequence of sections, for example "AABB". When a path is built, every note gets a suffix saying which pass it belongs to, so note `n12` becomes `n12-1` on the first pass and `n12-2` on the second. This is the same naming the (n)ASAP ground truth uses, which is what makes the validation below possible.

Most scores have one path: 197 of the 242 ASAP scores do. The rest can have many; the largest has 2048 (Schubert D.935/3). Aligning against all of them would be too slow, so the choice is made in two steps:

1. Count the notes on every path without building it (a cheap sum over sections), and rank paths by how close that count is to the number of performed notes. Ties go to the longer path.
2. Build and align the 6 closest paths, and keep the one with the highest match ratio.

The match ratio is twice the number of matched notes divided by the total number of score notes plus performed notes. It is 1 when every note on both sides is matched. A path with too many repeats adds unmatched score notes, a path with too few adds unmatched performed notes, and both lower the ratio, so it is a fair referee between candidates. (Statisticians will recognise it as the Dice coefficient.)

The note-count ranking is a heuristic with an obvious weakness: a pianist who adds or drops many notes shifts the count, and paths that differ by only a short section have nearly equal counts. The final decision is made by the match ratio, which does not share that weakness, but only among the 6 finalists. The number 6 is a cost compromise (each candidate is a full alignment run); no other value was tried and there is no recorded sweep.

The caller can also force a choice: "maximal" (every repeat), "minimal" (no repeats) or an explicit path string. The ASAP loader unfolds maximally by default, which is why downstream code must always use the score returned by the alignment, not the one from the loader: the alignment ids refer to the chosen path.

Three traps in partitura shaped this code. Listing paths is stateful: a second call on the same score can silently return fewer paths (70 on the first call, 4 on the second, for one Beethoven sonata movement), so section markers are rebuilt on every call. This bug once broke the da capo sonatas in the first validation run, which scored 0.38 to 0.65 until it was fixed. Unfolding an already unfolded score crashes, so the code detects unfolded scores by their id suffixes. And unfolding recurses deeply on long sonatas, so Python's recursion limit is raised first. partitura's own automatic repeat identifier was not used because it does not work with the current numpy.

On the 99 (n)ASAP performances of scores with more than one path, the automatic choice agreed with the ground truth path in 86. The 13 misses were in three pieces (Schubert D.935/3, eight; Schumann Kreisleriana 2, three; Schumann Arabeske, two). Forcing the correct path raised the match F1 by 0.01 to 0.06 in 10 of them. Two were bad either way: in one Schubert performance the pianist's structure matches no path the score allows, and one Kreisleriana performance reaches only 0.46 even with the right path.

In the code: `align`, `repeat_variants`, `unfold_variant`, `match_ratio` in `src/pianolens/align/core.py`; validation of the choice in `ground_truth_variant` in `src/pianolens/align/validate.py`. Ticket F-01.

#### How is each played note matched to a written note?

The matching is done by parangonar's DualDTW note matcher (Peter, Cancino-Chacón, Widmer and colleagues, TISMIR 2023), the method that produced the (n)ASAP alignments. PianoLens wraps it and does not change it. Understanding it requires one idea from signal processing.

Dynamic time warping (DTW) lines up two sequences that describe the same thing at different speeds. Picture a grid with one sequence along each edge. DTW finds the cheapest path from one corner to the opposite corner, moving only forward (right, down, or diagonally), where each cell's cost says how badly those two elements disagree. Because the path can only move forward, the alignment keeps both sequences in order: if played note 10 is paired with score position 20, played note 11 cannot be paired with score position 19. Because the path can linger on one row or column, it absorbs any amount of speeding up or slowing down. That is exactly what rubato needs.

DualDTW uses DTW twice, at two levels of detail.

**Stage 1: a rough time map from pitch and order alone.** The score is reduced to its sequence of distinct onset positions, each represented by the set of pitches that start there (a chord becomes one set). The performance is the sequence of played pitches in time order. The cost of pairing a played pitch with a score position is 0 if the pitch is in that position's set and 1 if not. Timing plays no part at this stage: the path is found from which keys were pressed and in what order. This is run twice, forwards and on both sequences reversed, which is the "dual" in the name; a local mistake tends to derail a DTW path differently depending on which direction it approaches from.

From both paths the matcher picks anchor points: score positions where it is confident of the performed time. A pitch that also sounded at the previous score position is not used as an anchor, because a repeated key is ambiguous about which occurrence is which. Performed times that sit more than 0.1 s from the median of their score position are dropped as outliers, and the earliest remaining onset stands for the position (a chord's first note marks its start). A position is kept only when the forward and backward estimates agree within 0.1 s. Gaps between anchors are filled where a pitch occurs the same number of times in the score segment and in the matching stretch of performance. Straight lines between anchors, extended past the ends, give a map from score beats to performance seconds.

**Stage 2: matching pitch by pitch.** Now each pitch is handled on its own. For, say, every E4 in the score, the time map predicts when it should have sounded. Those predicted times are aligned by a small one-dimensional DTW to the actual onsets of every played E4, and the closest pairs along the path are kept, provided they are less than 1.5 s apart. Score notes left without a partner are labelled "deletion" and played notes without a partner "insertion".

Why build it this way? Pitch identity is the strongest evidence there is: a pianist can be early, late, loud or soft, but a written E4 is only ever realised by the E4 key. Matching per pitch means a note can only be paired with a note of the same pitch, and the order constraint within each pitch stops, for example, the third E4 in a bar being paired with the first. The time map from stage 1 then only has to be good enough to tell apart different occurrences of the same pitch, which it usually is, because occurrences of one pitch are normally far apart compared with timing errors.

A direct consequence shapes all of tier A: a wrong key can never be matched. Playing C sharp instead of C produces one deletion (the C) and one insertion (the C sharp). This is the standard convention in the literature (RUMAA, Chang, Dixon and Benetos, WASPAA 2025; Nakamura, Yoshii and Katayose, ISMIR 2017), and tier A later decides whether to merge the two into one "wrong pitch".

**Grace notes and ornaments.** Grace notes have no real duration in the score, so they are left out of stage 1 and would only confuse the time map. Before stage 2 they are placed just before their main note, spaced 0.1 beat apart, so they can be matched by pitch like any other note.

Trills, mordents and turns are a different problem: the score shows one note with a sign, and the pianist plays a rapid alternation of that note and its neighbour. With ornament handling on, the matcher looks at every ornamented score note that has a match, releases that match, and searches the unmatched played notes within 2 semitones of the written pitch, from 0.25 s before the written onset to its predicted end. The earliest candidate becomes the match. So an ornamented note is paired with exactly one played note, and the remaining notes of the trill stay "insertions". Tier A deals with those (see "Why ornaments are not counted as mistakes").

Two details of the library's ornament step were found while reading its code for this chapter and have not been tested. The step that is meant to prefer a candidate at the written pitch compares against a variable left over from the earlier pitch loop rather than the ornament's own pitch, so in practice it likely falls back to the earliest candidate at any of the five pitches. And an ornamented note that was not matched in the first place is skipped by this step, so a trill whose main note was never matched is not repaired. When the released match is re-matched to the same played note, the alignment list can hold that note both as an insertion and as a match; tier A reads the match (it is written last), while the validation metrics read it as an insertion. None of this has been measured.

The parameters, all parangonar defaults, none tuned in this project:

| Parameter | Value | What it does |
|---|---|---|
| Stage 1 cost | 0 if pitch in the score position's set, else 1 | Aligns by which keys were pressed, in order |
| Anchor agreement | 0.1 s | Forward and backward estimates must agree; outliers further than this from the median are dropped |
| Stage 2 threshold | 1.5 s | Largest allowed gap between predicted and played onset for a same-pitch match |
| Grace spacing | 0.1 beat | Grace notes placed before their main note |
| Ornament search | ±2 semitones, from 0.25 s before the onset to the predicted end | Played notes that may realise an ornamented note |

In the code: `align_note_arrays` and `align` in `src/pianolens/align/core.py`; the matcher itself is `DualDTWNoteMatcher`, `OnsetMatcherDTW` and `CleanOrnamentMatcher` in the installed parangonar 3.3.3 (`parangonar/match/matchers.py`). The score note array must be built with grace-note fields included, or the matcher fails.

#### How do we know the alignment is right?

The check is against (n)ASAP, a public dataset of 1,067 Disklavier performances of 222 scores whose note alignments were published by the same research group. Every performance with an alignment file was aligned from scratch with the automatic repeat choice and compared note by note. Three kinds of agreement are measured: pairs (does our aligner pair the same score note with the same played note?), insertions and deletions (does it call the same notes extra or missing?), and the share of played notes whose status is exactly right. Each is reported as an F1 score, which combines precision (how many of our calls are right) and recall (how many of the true ones we found) into one number between 0 and 1.

There is an important caveat about what "ground truth" means here. The (n)ASAP alignments were produced semi-automatically, with matchers from the same family as ours, and only some are flagged by the dataset as robust. Agreement with them is agreement with a strong reference, not with hand-checked truth. (The landscape document describes them as "human-checked"; the dataset's own robustness flag and the validation code's docstring are more cautious, and this chapter follows the cautious reading.)

Of 1,066 performances attempted, 1,063 were scored (three have no alignment file). The results:

| Measure | Value |
|---|---|
| Pair F1, mean over performances | 0.964 |
| Pair F1, median | 0.987 |
| Pair F1, robust-flagged performances only (834) | 0.981 |
| Pair F1, pooled over all notes | 0.952 |
| Performances with pair F1 of 0.95 or more | 81% (90% of robust ones) |
| Played notes given exactly the right status | 0.960 |
| Insertion F1 | 0.855 |
| Deletion F1 | 0.752 |

By composer the mean ranges from about 0.99 (Bach, Haydn, Mozart) down to 0.920 for Liszt and 0.782 for Scriabin, whose mean is pulled down by a few outliers (its median is 0.961).

Low scores do not always mean our aligner failed. For the 31 single-path performances below 0.9, both alignments were checked against something independent: ASAP's hand-made downbeat annotations. If a note belongs to bar 40, its played time should fall between the annotated downbeats of bars 40 and 41, give or take 0.25 s. By this test our alignment was more consistent than the ground truth in 16 cases, less in 5, and tied in the rest. In a Scriabin sonata performance, 18% of the ground truth's matches fell in the right bar against 99% of ours. In ten performances of a Liszt étude at F1 about 0.86, both alignments put nearly every note in the right bar; the disagreement was about which of two identical notes (an octave doubling or a repeated note) was paired, not about losing the place.

The cases where ours was worse are informative: Ravel's Alborada del gracioso and Liszt's La campanella, both built on fast repeated notes, where the DTW path slips locally. Four performances scored close to zero and are flagged non-robust by the dataset; the beat check could not run on them, so they are treated as possible real failures until checked.

The weakest number is deletion F1 at 0.75. It is weak for a structural reason: when the same pitch occurs twice close together, or in octave doublings, and one occurrence is skipped, there is often no way to tell from the MIDI which one was skipped. This single number decided how missed notes are reported (see "Why are missed notes reported per bar?").

Alignment takes a median of 11.3 s per performance on one core of the development Mac, about 310 notes per second, with a maximum of 202 s for the score with 2048 repeat paths. An earlier run without the second aligner running alongside had a median of 6.8 s.

**A second opinion: Nakamura's aligner.** To see whether a different method would do better, the check was repeated with the aligner of Nakamura, Yoshii and Katayose (ISMIR 2017). It models the performance as a hidden Markov model, a statistical model in which the "hidden" state is the current position in the score and each played note is evidence about it, and it has an explicit step for detecting errors. It is a compiled command-line tool, not a Python package, and it reads the MusicXML itself without partitura's repeat handling, so it was only run on single-path scores. A small adapter maps its output to partitura ids: score notes by (position in quarters, pitch), with one ninety-sixth of a quarter of slack, and played notes by (onset in milliseconds, pitch), with 2 ms of slack. Notes it marks as pitch errors become a deletion plus an insertion, the same convention as ours.

It crashed on 85 of 964 single-path performances. On the 879 where it ran, mean pair F1 was 0.954 against 0.968 for DualDTW; medians were 0.990 against 0.988; and it was faster (median 5.4 s against 10.1 s). On the 719 robust single-path performances, DualDTW averaged 0.982 and Nakamura 0.968. The reading is that the two are about equally good on typical playing, and Nakamura's tool fails more often and more badly. DualDTW is the default; Nakamura is an optional cross-check only.

**A cheap warning light.** In use there is no ground truth, so each alignment carries its match ratio. Below 0.8 the result is flagged as suspect and the report says that the score may not be the version that was played and every finding is unreliable. The value 0.8 is a judgement made after looking at the validation, not a calibrated threshold.

In the code: `src/pianolens/align/validate.py` (run it with `uv run python -m pianolens.align.validate`), `src/pianolens/align/evaluate.py` (set-based metrics; parangonar's own scorer is too slow on long pieces), `src/pianolens/align/nakamura.py`. Full numbers: `docs/specs/alignment-validation.md`. Ticket F-01.

#### How are mistakes labelled?

The alignment says which notes were paired. A student needs something more specific: which notes were wrong, which were added and which were left out. Tier A converts the alignment into one label for every played note and one for every written note, and then counts them per bar.

| Label | Given to | Meaning | Counts as an error? |
|---|---|---|---|
| correct | both sides | Matched to a note of the same pitch | No |
| wrong_pitch | both sides | A played note and a written note merged into one "wrong key" mistake: close in time and within 2 semitones or exactly an octave | Yes, once |
| extra | played note | Played, matched to nothing, and not explained as a wrong pitch or an ornament | Yes |
| missed | written note | Written, matched to nothing, and not explained as a wrong pitch | Yes |
| ornament | played note | An unmatched note close to a grace note or an ornamented note, within 2 semitones of it | No, tolerated |
| ornament_skipped | written note | A grace note that was not played | No, tolerated |
| interpolated | both sides | A note a dataset pipeline filled in, not played by anyone (PianoCoRe's refinement step creates these) | Excluded from every count |

The labels are assigned in a fixed order, and the order matters.

First, alignment labels are copied: matches become correct, and everything else starts as extra (played side) or missed (written side). Two checks added after BL-20 run at this point. A match whose played pitch differs from the written pitch stays correct only if the ornament rule below allows it; otherwise it is dissolved and handed to the wrong-pitch step (DF-10). And a same-pitch reassignment pass can swap a match to a better partner of the same pitch (BL-23). Both are explained under "What happens in very fast passages?".

Second, an expected time is computed for every written note. Each written position that has matched notes gets the median time of those notes; the medians are forced to never go backwards in time; and every other position is placed by straight-line interpolation between neighbours in score time (quarters), extended linearly past the ends. This answers "if this note had been played in tempo with its surroundings, when would it have sounded?"

Third, the ornament allowance runs (described below), so that trill notes are not mistaken for wrong pitches.

Fourth, wrong pitches are paired. Every still-missed written note is compared with every still-extra played note whose onset lies within 100 ms of the written note's expected time. A pair qualifies if the pitches differ by 1 or 2 semitones, or by exactly 12 (an octave). Each qualifying pair gets a cost: its time distance measured in window widths, plus its pitch distance in twelfths of an octave, with an octave error costed like a 3-semitone error so that a near neighbour in time and pitch wins over an octave. Pairs are then accepted greedily, cheapest first, each note used at most once. Pairs that do not qualify stay extra plus missed.

Fifth, every note is placed in a bar. Written notes use their score position. Matched and wrong-pitch played notes use their partner's position. Extra played notes have no partner, so their onset is mapped back into score time through the inverse of the expected-time map. Bars are identified by their row in the unfolded score, not by their printed number, because after unfolding a repeat the same bar number occurs twice.

The summary reports accuracy (correct written notes over graded written notes), error rate (wrong pitches plus missed plus extra, over graded written notes), and the match ratio. The match ratio here leaves out interpolated notes and skipped grace notes, so it can differ slightly from the aligner's own match ratio, although the code comment says they are the same.

**Why merge a deletion and an insertion into one wrong pitch?** For feedback, "you played C sharp instead of C" is one mistake, not two, and a teacher would call it that. The rule "within 2 semitones" follows the physical cause: most wrong keys are neighbours of the right one, a finger landing a key to the side. It also matches the mistake generator used by MAESTRO-E (Chou and colleagues, AAAI 2025), whose pitch offsets are almost always 1 or 2 semitones. Octaves are allowed because a hand landing in the wrong octave is a known real error. Wider jumps are not merged, because a note a fourth away at the same moment is more likely an extra note plus a separate miss.

In the code: `correctness`, `expected_onsets`, `measure_rows` in `src/pianolens/features/correctness.py`. Ticket F-02 (and F-02b for the window).

#### Why is the wrong-pitch window 100 ms, and why is it not the usual 50 ms?

Two different time limits appear in the code, and they answer different questions.

The 50 ms limit (`ONSET_TOLERANCE_SEC`) is the standard used when scoring music transcription systems (MIREX and the `mir_eval` library): a transcribed onset counts as hitting a reference onset if it is within 50 ms. It compares two measured times. In tier A it is kept only as a named reference value and is not used.

The 100 ms limit (`WRONG_PITCH_WINDOW_SEC`) compares a measured time with an estimated one. The expected time of a missed note is the median of its chord-mates or an interpolation between neighbours, and real chords are not played exactly together. The melody note is usually played slightly early and louder; louder notes also sound earlier because a faster hammer reaches the string sooner (Goebl 2001); and some chords are deliberately rolled from bottom to top. All of that spread lands in the estimate's error. The effect was measured by feeding the exact ground-truth alignment of the synthetic mistake set into tier A, which removes alignment errors and leaves only the labelling step: 9% of injected wrong pitches fell outside 50 ms of their estimated time and 5% outside 100 ms.

Widening from 50 to 100 ms at a 5% mistake rate raised the bar-level wrong-pitch F1 from 0.922 to 0.942, while wrong-pitch false alarms on clean playing rose from 64 to 85 across the whole clean set (0.26 to 0.35 per 1,000 notes). The lead chose 100 ms on the argument that for a practice tool, missing a real wrong note is worse than a rare false flag, and recorded that the choice must be revisited on real mistakes. Only the two values, 50 and 100 ms, were ever tried, and both were fixed before the first run.

Making the change exposed a boundary case that shows how the window behaves. In a unit test with ornament handling switched off, a grace note is graded as an ordinary note, and its expected time is the median of its chord-mates, 2.006 s. An extra note 1 semitone away at 1.95 s is 56 ms early. At 50 ms it misses the window by 6 ms and stays extra plus missed; at 100 ms it pairs as a wrong pitch. Both answers follow the rule; the test now checks both windows explicitly.

In the code: constants at the top of `src/pianolens/features/correctness.py`; the argument `wrong_pitch_window_sec`. Evidence in `docs/specs/correctness-validation.md`; decision in `DECISIONS.md` (2026-09-27).

#### Why are ornaments not counted as mistakes?

A trill written as one note is played as many. A grace note may be played, played differently, or left out in a light performance. Counting all of that as extra or missed notes would punish exactly the players who realise the ornaments. So, after the aligner has matched one played note to each ornamented written note, tier A tolerates the rest:

- Around a written grace note, unmatched played notes within 2 semitones of it, from 0.25 s before its expected time to 0.1 s after, become "ornament".
- Around a written trill, mordent or turn, unmatched played notes within 2 semitones, from 0.25 s before its expected onset to its expected end, become "ornament".
- A written grace note that was not played becomes "ornament_skipped", not "missed".

The 2 semitones and 0.25 s are the same values parangonar uses for trills; the 0.1 s after a grace note (`GRACE_TAIL_SEC`) allows for a grace note played on the beat rather than before it. None of these values were tuned. Two limits follow from the design: a written trill main note that was not matched at all is still "missed" (only grace notes can be "skipped"), and an ornament played wider than 2 semitones, or a long free cadenza-like flourish, is still counted as extra. The synthetic mistake set never places mistakes on ornaments on purpose, but the allowance still interacts with real mistakes nearby. Because it runs before wrong-pitch pairing, a wrong neighbouring key that happens to fall near a trill or grace note is quietly tolerated instead of being named. In the dense cells of BL-20's stress test, where passages hold more ornaments, it tolerated 6 to 13% of injected wrong notes, against about 1 to 2% in slow passages. A tighter rule that allows only the ornament's own pitches was tried and rejected, because it flagged too much genuine ornament playing in expert performances (BL-23, under "What happens in very fast passages?"), so the ±2 semitone rule remains the default.

In the code: `ORNAMENT_SEMITONES`, `ORNAMENT_LEAD_SEC`, `GRACE_TAIL_SEC` and the "ornament whitelist" block in `src/pianolens/features/correctness.py`.

#### Why are missed notes reported per bar, not per note?

Suppose a bar has two C5s close together and the student plays only one. The MIDI shows one C5; the score has two. Which one was skipped? Usually there is no way to tell, and the aligner has to pick. The same happens with octave doublings and with the same pitch in two voices. This is why deletion F1 in the alignment check was only 0.75.

The synthetic mistake set confirmed it on clean playing, where tier A reported 8.3 missed notes per 1,000 that were not in the ground truth. In three clean performances, all 133 such false "missed" notes were checked: every one was a note the ground truth had matched. In 127 cases our aligner had matched the played note to a different written note of the same pitch, and in 6 it had left it unmatched. The count was right; the choice of which duplicate was wrong. At note level, missed-note precision is only 0.39 to 0.69 depending on the mistake rate; at bar level it is 0.92 or more.

So the rule is: the number of missed notes in a bar is trusted, the identity of the missed note is not. The report presents missed notes per bar, and anything built on tier A must read the per-bar count.

In the code: the `bars` table of `CorrectnessResult` (`n_missed` per bar) in `src/pianolens/features/correctness.py`. Decision in `DECISIONS.md` after F-01; rule repeated in `.claude/rules/features.md`.

#### How well does tier A find real mistakes? The synthetic test

Validating a mistake detector needs performances where every mistake is known. No public dataset of real piano mistakes with exact labels was usable, so the project built one by injecting mistakes into expert performances whose alignment is known.

**The data.** 100 (n)ASAP Disklavier performances were chosen by a fixed seeded draw: robust ground-truth alignment, a score with a single repeat path (so ground-truth ids are directly comparable), and at most 6,000 notes, sampled round-robin across 12 composers. Each was kept as a clean copy and also perturbed at three mistake rates: 2, 5 and 10 mistakes per 100 matched notes, split equally between wrong pitches, extra notes and missed notes. Each rate holds 246,324 performed notes in 12,995 bars.

**The mistake model.** It follows the published MAESTRO-E generator in spirit, with deliberate changes:

- Wrong pitch: the note keeps its timing and loudness; the pitch moves by 1 semitone (60% of cases), 2 semitones (30%) or an octave (10%). The new pitch may not already be in the same chord, and may not be a key that is already sounding at that moment (MIDI cannot hold the same key down twice).
- Extra note: a neighbouring key (1 or 2 semitones away) caught at almost the same time as a played note, from 20 ms before to 60 ms after it, held 30 to 150 ms, at 40 to 80% of its velocity. This models a finger brushing the next key.
- Missed note: drawn with weights, twice as likely for inner notes of a chord of three or more, and twice as likely in fast passages (a neighbouring chord less than 150 ms away), because that is where real players drop notes. The top voice is never favoured.
- No timing shift is attached to mistakes, so that timing and correctness can be varied separately in other experiments.
- Mistakes are placed only on notes the ground truth matched. Insertions and deletions already present in the ground truth (51.7 and 40.5 per 1,000 notes; a mix of real slips and ground-truth noise) are treated as "don't care": neither a hit nor a false alarm.

**Two modes.** "Aligned" runs the full pipeline as deployed: our aligner on the perturbed MIDI, then tier A. "Ground-truth alignment" feeds the exact alignment into tier A, which isolates the labelling step from alignment errors.

Results at the 5% rate with the 100 ms window, precision / recall / F1, pooled over all performances:

| Level | Type | Full pipeline | Labelling only |
|---|---|---|---|
| Note | Wrong pitch | 0.944 / 0.852 / 0.896 | 0.972 / 0.952 / 0.962 |
| Note | Extra | 0.744 / 0.916 / 0.821 | 0.964 / 0.957 / 0.960 |
| Note | Missed | 0.583 / 0.894 / 0.706 | 0.897 / 0.963 / 0.929 |
| Bar | Wrong pitch | 0.997 / 0.893 / 0.942 | |
| Bar | Extra | 0.928 / 0.935 / 0.931 | |
| Bar | Missed | 0.945 / 0.953 / 0.949 | |
| Bar | Any error | 0.990 / 0.984 / 0.987 | 0.993 / 0.991 / 0.992 |

On the clean copies, the full pipeline reports, per 1,000 notes, 3.01 extra, 0.35 wrong pitch and 8.33 missed that are not in the ground truth. Per 1,000 bars, 3.4 are flagged for any error and none for a wrong pitch. Because this floor stays fixed while true mistakes grow, precision rises with the mistake rate.

The reading is that bar-level flags are usable for feedback: a bar holding an injected mistake is flagged with an F1 of 0.98 to 0.99, and a bar-level wrong-pitch flag is almost never false. Note-level missed labels are not usable, for the duplicate reason above. The weakest bar-level number is wrong-pitch recall, 0.88 to 0.90; most of the gap to the labelling-only mode is caused by the aligner, and an unpaired wrong pitch is still reported, only as an extra plus a missed. Harder repertoire scores lower: Liszt, Schumann and Scriabin are lowest at note level, as they were in the alignment check.

Four caveats limit what this proves. The mistakes are synthetic, and real slips have their own timing and pitch habits. Bar-level scores are measured only on bars without a natural ground-truth mistake (54% of bars for "any error"), which are probably easier than average, so they are optimistic. Only single-path scores were used, so repeat-choice errors are not exercised. And ornaments were never perturbed. Validating on real human mistakes is still open.

In the code: `src/pianolens/data/perturb.py` (the generator; its docstring lists every difference from MAESTRO-E), `scripts/build_mistake_set.py`, `scripts/eval_correctness.py`. Full tables: `docs/specs/correctness-validation.md`. Tickets D-08, F-02, F-02b; open follow-up BL-10.

#### What turns a mistake into feedback: expert comparison and recurring errors

Tier A counts are raw material. The report decides which bars deserve attention, and two rules there depend directly on how tier A behaves, so they are summarised here (the report chapter has the details).

The first rule is that a single wrong note in a bar is not ranked: in the clean expert set, 7.1% of bars already contain one flagged wrong note, so a single flag cannot separate a slip from checker noise. Bars are ranked only when they exceed limits calibrated on expert playing.

The second rule compares each bar with experts playing the same score. Some bars are flagged for nearly every expert, because the score file, the edition or the checker disagrees with what pianists actually play there. When at least 5 expert recordings of the same score, captured the same way as the student's (key-sensor or transcribed), are available, a bar must exceed both the global limit and the experts' own 80th percentile for that bar to be "notable", and their 99th percentile to be "strong". On one of Henry's pieces, a bar with 5 wrong notes turned out to have a median of 5 wrong notes across the expert transcriptions too, and is now suppressed as a likely edition artefact. The check keeps about 85% of the bars with injected mistakes that were ranked without it.

Recurring errors are the case a teacher cares most about: the same mistake in several takes is a learned mistake, not a slip. A naive rule ("the same error key in two or more takes") was tested by treating three different expert pianists as three takes of one player. Their slips are independent, so anything that recurs is a checker or score artefact, and the naive rule marked 24 to 31% of expert bars. The adopted rule is narrow: only a wrong pitch (the same written note played as the same wrong key) in at least 2 takes counts, it must not appear for any expert recording of the score, and it is promoted to "strong" only when at least 2 experts were checked. Under that rule 0.18 to 0.51% of expert bars qualify. Missed and extra notes are never promoted, because which note was missed is not reliable. The weakness of the calibration is that the pseudo-takes are different people; a single player's habits recur more across their own takes.

For transcribed input (audio converted to MIDI), transcription roughly doubles the apparent error rate (0.039 to 0.080 in the D-10 check), and extra notes never count toward correctness tiers.

In the code: `src/pianolens/report/build.py` (`expert_bar_limits`, recurring errors) and `src/pianolens/report/calibration.py` (`RECURRING_*`, `EXPERT_CHECK_*`). Evidence: `docs/specs/report-validation.md`. Tickets F-08, F-08b, F-08c.

#### How do we know which hand played a note?

We do not know it directly, and tier A does not try. Correctness is reported per bar and per note, never per hand. MIDI from a piano records keys, not fingers or hands, so any hand information must come from somewhere else.

Where the project does need hands, in the hand-synchrony measure of tier B (do the two hands land together on shared beats?), it borrows them from the score: staff 1 (the upper stave) is taken as the right hand and staff 2 as the left. A played note inherits the staff of the written note it was aligned to, so hand assignment rides on the alignment. Extra notes have no written partner and therefore no hand. Scores that carry no staff information (for example score MIDI files) get staff 0 or a default, and hand synchrony then comes out empty; for MAJEPPA's two-track score MIDIs the track with the higher mean pitch is labelled staff 1, and notes present in both tracks are left unassigned and counted.

Staff is not the same as hand, and the difference is not rare in piano music:

- Cross-staff writing: a single run or chord drawn across both staves, usually played by one hand.
- Hand crossings: one hand reaching over the other to play notes on the far stave.
- Redistribution: a pianist choosing to take a few notes of the other stave with the freer hand, which editions often leave unmarked.
- Inner voices and accompaniment figures split between the hands in ways the notation does not show.

In each case the staff rule assigns the note to the wrong hand. For hand synchrony this mixes notes of one hand into the other hand's average; for any future feedback such as "your left hand drops notes in bar 12" it would blame the wrong hand. The report's advice to practise "hands separately" is generic text and does not claim to know which hand erred.

**How often might it happen?** BL-19 estimated this from the scores alone, on 802 scores of the app's piece list (1.6 million notes). No note there has a known hand, so it used three proxies that mark notes whose hand *may* differ from their staff:

- a cross-staff voice: the note sits on a different staff from most notes of its written voice, as when a right-hand arpeggio dips into the bass staff;
- a pitch crossing: an upper-staff note below every lower-staff note sounding at the same moment, or the reverse;
- one-hand capacity: a staff starts more than 5 notes at once, or spans more than 16 semitones (wider than a tenth), so the other hand probably takes some of them.

About 5% of notes (5.2%) and 3.9% of the onsets that hand synchrony compares were flagged. The share is very uneven across pieces: the median piece has 0.9% of its hand-synchrony onsets flagged, while 4.2% of pieces have more than 20%. The pre-registered concern level (a median above 5%, or more than 10% of pieces above 20%) was not reached, so the proxies pass for hand synchrony pooled over a piece. Impressionist and Spanish piano writing is the exception: about 10% of notes are flagged for Debussy and Ravel, and 15% of hand-synchrony onsets for Albéniz.

The auditor added an important limit. Some scores carry the engraver's own hand marks, such as "m.g." (left hand) written in the upper staff. In 57% of the 248 bars where the engraver wrote a hand word naming the other staff's hand, the proxies flagged no note at all. The likely reason is that when one hand takes notes on the other staff while its own staff rests or holds, no proxy fires. So the 5% is a floor set by the proxies, not a bound on the true rate: the result is a pass on the proxies, and the real mismatch rate is unknown until notes with real hand labels are checked. PianoVAM supplies such labels, taken from video of the players' hands, for most of its recordings, and about 20 of its recordings match pieces in the app's list. Those labels were fetched on 2026-10-10 (BL-24) and checked in BL-19b, below.

**Measured against real hand labels (BL-19b).** PianoVAM's video hand labels were joined to 42 recordings of 31 catalogue pieces after cutting each practice session into takes and aligning every take to its score (117,238 labelled notes, 8 pianists). The rule was fixed in advance. Staff 1 = right hand is wrong for 6.66% of notes [3.51, 9.00], against a label error of about 0.76%. The median piece is at 3.35%, and 4 of 31 pieces are above 10%. The errors are systematic, not noise: when a note is played by the other hand once, it is played that way again 90% of the time. Some of it is engraving: in the first movement of Schumann's Fantasie Op. 17, bars 41 to 49 put left-hand material on the upper staff, and all 7 recordings play it with the left hand. In the worst piece, the Toccata from Ravel's *Le Tombeau de Couperin*, 86% of the mismatches are same-pitch notes the hands alternate on. Staff still beats a middle-C split by 16.7 points, in every piece. Hand synchrony passes its rule (no more than 10% of pieces with over 20% of onsets affected) exactly at the boundary: 3 of 30 pieces, and dropping any one passing piece would turn it into a concern. The BL-19 proxies catch only 39% of real mismatches. So per-hand feedback stays off, hand synchrony stays as it is but is fragile, and a model that assigns hands from the score and the playing is in the backlog (BL-34). The auditor confirmed it with caveats.

**A numbering problem found on the way.** Hand synchrony compares staff 1 with staff 2, but 25 scores in the app's list gave it no onsets at all, and more gave only some, because their staves were numbered 3 and 4, 1 and 3, or one staff per part. The fix (DF-09) renumbers the two main piano staves to 1 (upper) and 2 (lower) whenever a score is prepared for alignment. After it, no score in the list gives zero onsets, and the hand-synchrony onsets across the list rose from 297,495 to 314,448. The rule is right for solo scores and arbitrary for piano duets: the three four-hands pieces in the list are split three different ways, and hand synchrony means nothing for four hands. Since 2026-10-10 (DF-11) duets are detected from the score layout (all three in the list, and no solo look-alikes), and their reports leave hand synchrony out and say why.

In the code: `hand_synchrony` in `src/pianolens/features/control.py`; `score_note_frame` in `src/pianolens/features/_score_utils.py`; staff renumbering `normalise_piano_staves` in `src/pianolens/align/_adapters.py`; proxies in `scripts/staff_hand_proxies.py`; MAJEPPA staff assignment in `src/pianolens/data/majeppa.py`. Tickets BL-19, BL-19b, BL-24, DF-09, DF-11; hand-label check in `experiments/2026-10-10-BL-19b-hand-proxies/` (`src/pianolens/data/session_takes.py`, `src/pianolens/features/hand_proxies.py`); duet detection `src/pianolens/report/four_hands.py`.

#### What happens in very fast passages?

Fast passages stress the method in two places: the aligner and the wrong-pitch pairing. Timing precision is not the problem.

**Timing precision.** A key-sensing piano records onsets far more finely than any musical timing difference at issue here; the repo has not measured Disklavier precision itself, but it is not the limiting factor. For audio transcribed to MIDI, the project measured the added timing error at about 2 ms (A-01, expert recordings through a simulated phone) and a median robust spread of 3.1 ms (BL-13, microphone recordings against Disklavier MIDI). Both are small compared with the spacing of notes even in fast playing. What goes wrong at speed is ambiguity, not measurement.

**Why the aligner was expected to struggle.** The order constraint in stage 1 keeps the rough time map on track through a fast run, because the pitch sequence of a scale or arpeggio is distinctive. The fine matching in stage 2 is per pitch, and there the 1.5 s limit is loose compared with a fast passage: in a run, the same pitch can recur several times within 1.5 s. So a wrong key that happens to equal the pitch of a nearby written note (in a scale, the next note up is 1 or 2 semitones away) can be matched to that nearby note. The wrong key is then labelled correct, which this chapter calls *absorbed*, and the error surfaces elsewhere as a missed or extra note. The wrong-pitch pairing adds a smaller risk: when notes are closer together than its 100 ms window, a wrong note could in principle be paired with the wrong missed note.

**What BL-20 measured.** The original synthetic test (F-02) was not built for this: wrong pitches were placed uniformly and results were never split by speed. BL-20 split them. Each note gets a *local inter-onset interval*: the median gap between neighbouring chords around it (notes within 30 ms count as one chord), and passages under 100 ms count as dense. Two findings came out.

- Bar-level flags held up on the original set. The bar any-error F1 was slightly higher in dense passages than in slow ones (+0.012), so "something went wrong in this bar" does not get worse with speed.
- Naming the wrong note did get worse. Through the full pipeline, 6.9 to 8.3% of injected wrong pitches under 100 ms were absorbed or paired with the wrong written note, against 2.5% in passages slower than 200 ms. A targeted stress set made the hard case explicit: a wrong key equal to a pitch in the neighbouring chords, in a dense passage. There only 68% of wrong notes were named correctly (strict recall 0.681), against 90% for an ordinary wrong key in a slow passage, and 15.7% were absorbed.

The 100 ms window is not the cause: narrowing it to 50 ms made every dense result worse, and with a perfect alignment a wrong note was paired with the wrong written note in at most 1.1% of cases. (Wider windows were not tested.) The auditor corrected the first attribution, which blamed the aligner alone. Even with the ground-truth alignment, the hard dense case reached only 0.812 against 0.949 in the slow control, mostly because the ornament allowance swallowed wrong keys near trills and grace notes before they reached the pairing step. So the aligner and the ornament allowance both contribute. The auditor also sharpened the bar-level claim: counting only bars that had no error before the injection, a dense bar with an absorbed-type wrong key stayed unflagged about 1 time in 15 (detection 0.932).

**What was changed (BL-23 and DF-10).** Two fixes were tested against pre-registered criteria. The first is a *same-pitch reassignment* pass after alignment: for each match whose played time sits far from where the tempo map expects its written note, it checks whether swapping partners with an unmatched note of the same pitch, or turning the match into a wrong-pitch pair, lowers the total timing cost. It is a local repair on the existing time map, not a new aligner. The second is a tighter ornament allowance that pairs wrong pitches first and then allows only the ornament's own pitches. Together they got closest to closing the gap, but they failed three criteria: the dense-to-slow gap was still -0.109 against an allowed 0.10, detection in clean dense bars was 0.930 against a required 0.95, and on clean expert playing the tight rule turned 6.5% of the notes the old rule tolerated into errors, flagging 9.9% of previously clean bars, against a limit of 5%. The auditor traced most of that last failure to one Schubert score whose 172 tremolo marks are shorthand for repeated chords that the score file never writes out: it supplied 124 of the 188 new flags. Most of the rest recur at the same bar across different pianists (Haydn and Liszt ornaments played on the unexpected side), so they are systematic, and at most 30 could be real slips. Expanding tremolo shorthand before any retest is a backlog item (BL-26).

By the pre-registered fallback, the reassignment pass alone became the default, because it passed every no-harm check. It is a real but small gain: on clean dense bars, strict recall rose from 0.786 to 0.807 (paired difference +0.022, interval 0.008 to 0.037) and absorption fell from 0.114 to 0.086. The auditor also measured its precision on real alignments of clean expert playing: of 291 swaps, 230 repaired an aligner error and 35 broke a correct match, so about 1 swap in 8 is wrong. That is outweighed, and a wrong swap mostly misnames which note was played rather than adding or hiding a flagged bar. The dense-to-slow gap remains at -0.135, above the 0.10 target.

The pitch check (DF-10) came from the same audit, which found 26 absorbed wrong keys matched to a written note of a *different* pitch. It turned out to change nothing under the default. parangonar only makes a different-pitch match in its ornament step, within 2 semitones of an ornamented note, and that is exactly what the default ornament rule already allows. So "0 matches dissolved" follows from the code rather than from the data, and the 26 cases stay absorbed. The check matters only for the tight rule or for another aligner.

**What the report does about it.** Because the checker is more reliable about the bar than about which notes in a fast run, wrong notes in runs whose local inter-onset interval is under 100 ms are worded at bar level ("2 wrong notes in this fast run", or "a wrong note in this fast run" for a recurring error), never as "you played D instead of C". Tiers are unchanged. The 100 ms wrong-pitch window stays. The report's parenthesis says the checker "is more reliable about the bar than about which notes". An earlier wording ("finds them reliably per bar") overstated it: on transcribed input, 21% to 24% of injected wrong notes in fast runs were not counted at all (BL-18b audit).

The mistakes in all of this are synthetic: isolated single wrong keys on expert playing (in the stress set, at least 2 s apart). Real slips in fast runs come in clusters, with timing and loudness changes, and those were not tested. Fast repeated notes on one key are a separate problem that belongs to transcription, not alignment; the audio chapter describes it (BL-21).

In the code: `correctness` in `src/pianolens/features/correctness.py` (`reassign=True` by default, `ornament_rule="legacy"`, the pitch check and its counters); `reassign_same_pitch` in `src/pianolens/align/postpass.py`; `local_ioi` and the fast-run wording in `src/pianolens/report/build.py`; `scripts/eval_correctness_density.py`, `scripts/eval_correctness_bl23.py`. Tickets BL-20, BL-23, DF-10, BL-26.

#### What about chords and notes that sound almost together?

A written chord is several notes at one position; played, it is never perfectly together. The design handles this at every step, with some limits.

In stage 1 of the aligner, a chord is a set of pitches, so the order in which the chord's notes arrive does not matter: every one of them costs 0 against that set. The start of the chord is taken as its earliest note, after dropping any note more than 0.1 s from the chord's median. A unit test with a steady slowing and 15 ms of spread within each three-note chord matches every note.

In tier A, the expected time of a missing chord note is the median of its matched chord-mates. For a normally voiced chord this is close. For a rolled chord, whose notes are spread deliberately from bottom to top, the top note can be well after the median, and a wrong key there may fall outside the 100 ms window; it is then reported as an extra plus a missed rather than one wrong pitch. This is the main reason 5% of wrong pitches stay unpaired even with a perfect alignment.

Octave doublings and chords with repeated pitches across voices bring back the duplicate problem: when one of two identical keys is missing, which written note is "missed" is a guess, which is another reason missed notes are reported per bar.

Two chord cases are open. First, if a student strikes, as a wrong note, a key that is also part of the same chord, the piano sounds that key once; MIDI shows no extra note, only the missing correct one, so it reads as a missed note. The synthetic generator deliberately never makes this kind of wrong pitch, so its frequency and effect are unknown. Second, when two voices share a written note at the same moment (a unison between voices), the score may carry two notes where the piano can only sound one key; if partitura keeps both, one will always look missed. Whether and how often this happens in the scores used has not been checked; it is a hypothesis.

Grace notes are the other kind of near-simultaneous note. They are placed just before their main note for matching, and tolerated if skipped. Chord spread between the hands is not a correctness question at all; tier B measures it as hand synchrony.

In the code: `pitch_and_onset_wise_times_ornament` and `get_score_to_perf_map` in parangonar; `expected_onsets` in `src/pianolens/features/correctness.py`; `test_rubato_and_chords` in `tests/align/test_align.py`.

#### What if there is no score, the wrong score, or a different structure?

Tier A is entirely score-based: a note is only wrong relative to a written note. Without a score there is nothing to compare, and the pipeline refuses to run correctness (the local app raises an error when a piece has no score file). The project has score-free measures elsewhere, for example for PianoVAM and the Rach3 practice sessions, but none of them is a correctness measure.

Free improvisation over a score, added ornamentation, or a cadenza of the player's own are counted as extra notes wherever they fall outside the ornament allowance. DTW always finds a path, so the aligner will pair whatever notes it can; during an improvised stretch it produces a run of insertions, and the per-pitch 1.5 s limit keeps the damage local. The match ratio drops, and below 0.8 the report warns that the score may not be the version played. How reliably that threshold separates "wrong score" from "many mistakes" has not been tested.

Structural departures behave similarly but more sharply. If the pianist skips a section, plays a repeat the score does not have, or jumps back, and the result is not one of the score's legal repeat paths, a whole block of written notes looks missed and a block of played notes looks extra. In one (n)ASAP Schubert performance whose structure matches no path, pair F1 was 0.02 even with the best path forced. Practice recordings are the extreme case: a student stopping, going back two bars and restarting produces a sequence no repeat path describes. The aligner assumes one continuous pass through one path. Because DTW only moves forward, a replayed bar is most likely read as extra notes (or the second attempt is matched and the first becomes extras); this is a hypothesis, not a measurement. The project's answer so far is to cut long sessions into separate takes before aligning (the Rach3 take splitter), which is required before any rehearsal recording can be scored.

A different edition of the right piece shows up as bars that everyone "gets wrong"; the per-bar expert check in the report is designed to catch these. Nothing yet handles a student's arrangement or simplified version of a piece.

In the code: `alignment_suspect` in `src/pianolens/features/correctness.py` and its wording in `src/pianolens/report/text.py`; `src/pianolens/data/rach3_takes.py`. Open tickets BL-10 (includes a mistake set on scores with repeats) and BL-15 (pass segmentation for rehearsal files).

#### Known gaps and untested assumptions

- Tier A has never been validated on real human mistakes. Every accuracy number comes from synthetic mistakes injected into expert playing (BL-10).
- The (n)ASAP reference alignments are semi-automatic, made with matchers of the same family as ours. Agreement with them may overstate accuracy where both share a blind spot. The independent downbeat check covered only 31 low-scoring single-path performances.
- Four near-zero (n)ASAP alignments (Chopin, Liszt, Scriabin performances flagged non-robust) could not be checked against downbeats and may be real aligner failures.
- The repeat choice aligns only the 6 paths closest in note count. The number 6 was never varied, and the choice was wrong in 13 of 99 multi-path performances. The synthetic mistake set contains no multi-path scores, so repeat errors combined with mistakes are untested.
- The match-ratio warning threshold of 0.8 is a judgement, not a calibrated value. Its ability to separate "wrong score or structure" from "many mistakes" is untested.
- The wrong-pitch window (100 ms) and pitch limits (±2 semitones, octave) were chosen once, from two candidate windows fixed in advance. No other values were tried, and the decision itself says to revisit on real mistakes.
- The ornament allowance (±2 semitones, 0.25 s before, 0.1 s after a grace note) is untested on real mistakes. It hides some wrong neighbouring keys in dense passages (BL-20), and the tighter alternative flags genuine ornament playing (BL-23). A key-aware rule, and expanding tremolo shorthand in scores (BL-26), are untried. An unplayed ornamented main note is still counted as missed.
- parangonar's ornament step, read for this chapter, appears to compare candidates against a stale pitch variable and to skip unmatched ornamented notes. The effect on alignments is unmeasured (DF-07).
- Hands are assigned by staff. Score proxies flag about 5% of notes as possibly played by the other hand (BL-19), but they miss most bars where the engraver marked a hand swap, so the true rate is unknown until PianoVAM's video hand labels are checked (BL-24). No correctness output is per hand. Piano duets get an arbitrary staff split (DF-11).
- In fast runs, wrong notes that equal a nearby written pitch are still named less reliably than in slow passages (a gap of 0.135 in strict recall after the reassignment pass, against a target of 0.10), and about 1 clean dense bar in 14 with such a wrong key stays unflagged (BL-23). The report words these at bar level.
- The reassignment pass moves a correct match in about 1 swap in 8 on real alignments. Its two time constants (30 ms and 100 ms) were fixed, not tuned.
- The density results use isolated synthetic wrong keys. Clustered slips in fast runs, with their timing and loudness changes, were never tested, and wrong pitches equal to an already sounding key are still excluded by the generator.
- A wrong key that duplicates another note of the same chord, and unisons between voices in the score, are expected to read as missed notes. Neither has been measured.
- Rolled chords push some wrong pitches outside the window. The 5% unpaired rate is measured only on expert playing with synthetic mistakes.
- Stops, restarts and practice loops are not modelled. Long rehearsal recordings must be cut into takes first, and no correctness number exists for such recordings.
- The recurring-error rule was calibrated with different pianists standing in for one player's takes. Real repeated takes of one learner (O-01) are the needed test.
- Bar-level synthetic scores are measured on the bars without natural ground-truth mistakes, about half of all bars, and are therefore probably optimistic.
- On transcribed input, correctness inherits transcription errors (the apparent error rate roughly doubles), and extra notes are excluded from tiers. Phone recordings add artefacts that the controlled simulation did not reproduce.
- On transcribed input the checker loses more wrong notes (DF-12). When 3 wrong keys were injected into clean bars of expert transcriptions (BL-18b), 16% to 19% were not counted as wrong, against 2.5% to 8.3% on Disklavier playing. Most were left unpaired, shown as a missed note plus an extra, because they sat more than 100 ms from the expected onset (DF-13): the window was set on key-sensor playing, and onset estimates are worse on transcriptions. A smaller share collided with a written note of the new pitch in the same bar. DF-13 tested wider windows, pre-registered, on 16 new pieces with an injection that avoids pitches written in the same bar. Only about half of the loss is the window; in the other half the aligner gives the intended written note to a different played note of the same pitch, or matches one played note to two written notes (DF-15). The best window (scaled to the local tempo) counted 3.6 to 4.7 points more of the injected notes, but raised wrong-note labels on clean recordings by 15.0% and 16.8% against a 15% limit, so it failed and the 100 ms window stays.


### Tempo and control

This chapter covers two linked parts of PianoLens. The first is the tempo model, which takes the note times of a performance and splits them into a smooth tempo curve (what the pianist meant to do with the pulse) and a leftover residual (the small timing deviations around that curve). The second is the set of control features, called tier B, which read that residual and a few other signals to ask a single question: is this player in command of the instrument? The chapter explains how each measure is built, why it was built that way, what evidence supports each choice, and what has never been tested. The experiment stories themselves are told elsewhere in this log (see D-10, R-09, F-07, BL-16 and F-04b).

#### Why does timing need a model before it can be judged?

A pianist's timing is never metronomic, and most of its departures from the metronome are deliberate. The research plan describes these departures as layers, from the overall tempo down to single notes, with unintended motor variation at the bottom:

| Layer | What varies |
|---|---|
| Global | overall tempo |
| Phrase | slowing and speeding over a phrase (tempo arcs, ritardandi) |
| Beat / meter | recurring patterns inside the bar, such as a slightly late second beat in a waltz |
| Note | melody lead, chord spread, lengthening of important notes |
| Noise | unintended motor variation |

Only the last layer is a failure of control. Everything above it is interpretation. A measure of control that read raw timing would punish a pianist for a beautiful ritardando and reward a mechanical one. So the project follows a rule: tempo is modelled as a smooth component plus a residual, tier B (control) reads the residual, and tier C (shaping) reads the smooth part. The tempo model is the tool that makes this split, and every timing feature in tier B depends on it.

The split is not perfect, and the rest of this chapter is partly the story of how it was corrected. The residual turned out to hold much more than noise: it also holds beat-level and note-level timing that pianists share because the score invites it. That discovery shaped the main tier B timing measure.

In the code: `src/pianolens/features/tempo.py` (ticket F-03); the rule is in `.claude/rules/features.md`; the layer table is from `docs/plans/2026-09-27-research-program.md`, section 1.2.

#### Which notes and times go into the model?

The tempo model works on an aligned performance, in which every played note has been matched to a note in the score (the alignment chapter explains how). From that matching it builds a list of score positions, each with one performed time.

Only notes labelled as true matches are used. Score notes that were not played but received a guessed time from the aligner, grace notes, and unmatched notes are left out, and each group is counted in the output. This follows a project-wide rule that features skip what they cannot use and report how much they skipped, rather than crash or silently guess.

A score position is a distinct onset in the score, measured in score beats. The beat unit is the lower number of the time signature, because that is how the partitura library counts. In 6/8 there are six beats per bar and each is an eighth note; in 2/2 a beat is a half note. This detail matters later: anything set "in beats" behaves differently across meters, and the harmony-change rule had to be moved to quarter notes for exactly this reason.

The performed time of a position is the median onset of the notes matched to it. A chord therefore becomes one point. The median is used because one badly placed note in a chord should not move the chord's time. The spread inside each chord is kept separately (`chord_spread_sec`), so that later features can study it.

Repeats need care. Pianists often skip written repeats: at least 13 of 99 ASAP performances of scores with repeats do. The aligner picks the repeat path the pianist actually took and returns a score unfolded along that path, and the tempo model uses that performed score. A second pass through a repeat therefore has its own beat numbers. This is also what lets the expert-consensus measure later line up the same position across different pianists, but only when they took the same path.

In the code: `matched_onsets` and `tempo_from_onsets` in `src/pianolens/features/tempo.py`; the repeat rule is in `.claude/rules/features.md`.

#### Why fit a time map instead of a tempo curve?

The obvious way to get a tempo curve is to take the time between consecutive onsets (the inter-onset interval, or IOI) and divide by the written length. PianoLens does something slightly different: it fits a time map, which is performed time in seconds as a function of score beat. The tempo curve is then read off the time map.

There are two reasons. First, tempo from IOIs is a ratio of differences, so it amplifies any error in a single onset; the time map uses the onset times directly. Second, the time map gives the two things tier B needs in one step. Its slope is the local beat period (seconds per beat), so tempo is 60 divided by the slope. And the gap between a note's actual time and the smooth time map is directly that note's timing deviation.

From the smooth time map the model derives a few standard quantities. The local beat period is the slope. Tempo is reported in score beats per minute, so a 6/8 piece reports eighth-note tempo. The log tempo ratio compares the local tempo with the performance's own average (the geometric mean over the beat grid), as a natural logarithm, so that it averages to zero and positive values mean faster. Logs are used because tempo changes are felt as proportions: ten percent faster is the same gesture at any base tempo. Timing deviations are reported both in seconds and as a fraction of the local beat. The beat version is the primary one, because timing deviations scale with tempo (Hu et al., TISMIR 2026): a 20 ms deviation is large in a fast passage and small in a slow one.

In the code: `TimeMap` and `tempo_from_onsets` in `src/pianolens/features/tempo.py`.

#### How is the smooth curve fitted?

The smooth time map is a penalized spline, or P-spline (Eilers and Marx 1996). The idea is to draw the most faithful curve through the points while charging a price for wiggles, and to choose that price so that the curve keeps phrase-level motion and drops faster detail.

The curve is built from cubic B-splines: small, smooth, bell-shaped pieces, one starting at every beat, added together with adjustable heights. With one piece per beat the curve could follow the data almost exactly, so the knot spacing does not set the smoothness. The penalty does. The fit minimizes the squared misfit plus a penalty weight times the sum of squared third differences of neighbouring coefficients.

The order of the penalty was chosen for a musical reason. A third difference is zero for any quadratic curve, so quadratic time maps cost nothing. A quadratic time map is one whose beat period changes linearly with position. In musical terms: a constant tempo, and a steady ritardando or accelerando in which each beat is longer than the last by the same amount, are never penalized and are recovered exactly. A second-order penalty would leave only constant tempo free and would flatten every ritardando toward a straight line. There is a subtlety worth stating. Repp (1992) found that within-gesture ritardandi follow a parabola in tempo. A parabolic change in beat period is a cubic time map, which the third-order penalty does charge for, so such arcs stay in the smooth curve only when they are slower than the cutoff described next.

Each position is weighted by the number of beats it represents (a trapezoid rule, capped at 4 beats and floored at 0.001). Without this, a bar of sixteenth notes would pull the curve four times harder than a bar of quarter notes. With it, the weights add up to one per beat, so the smoothing is set in beats whatever the note density.

A Whittaker smoother is a close relative: the same kind of penalty, applied directly to values on a regular grid. PianoLens uses one elsewhere, for the smooth velocity curve in tier D and in the dimensionality study R-02, with the same half-gain convention. The tempo model uses a P-spline because score positions are irregularly spaced in beats, which a B-spline basis handles naturally.

The penalized equations are solved by Cholesky factorization, a fast method for symmetric systems that are positive definite, with a tiny number (`1e-10`) added to the diagonal for safety. That safety margin once proved too small; the story is told below under DF-01.

In the code: `_penalized_fit`, `_bspline_basis` and `_spacing_weights` in `src/pianolens/features/tempo.py`.

#### How smooth should "intended" tempo be?

The penalty weight decides where intention ends and residual begins, so it is the most consequential number in the model. PianoLens sets it through a cutoff period: tempo motion slower than the cutoff goes into the smooth curve, motion faster than it goes into the residual. The default cutoff is 1.5 bars.

The fit behaves like a low-pass filter. For this penalty and these weights, a sinusoidal tempo wiggle of period `P` passes into the smooth curve with gain of about `1 / (1 + (P_c / P)^6)`, where `P_c` is the cutoff. The penalty weight is computed from the cutoff as `(P_c / 2π)^6 / h^5`, with `h` the knot spacing in beats. By the formula the gain is one half at the cutoff; the tests measure about 0.45 there, under 0.01 at half the cutoff, and over 0.98 at twice the cutoff.

| Tempo motion with period | Share kept in the smooth curve (1.5-bar cutoff) |
|---|---|
| 0.75 bar | under 1% |
| 1 bar (a metrical habit) | about 8% |
| 1.5 bars | about 45 to 50% |
| 2 bars | at least 85% |
| 3 bars or longer | over 98% |

The cutoff is set in score bars and converted to beats with the time signature, not set in seconds. The same musical span should count as phrase level whether the piece is fast or slow.

The choice of 1.5 bars balances two requirements. A timing pattern that repeats every bar, such as a habitually late third beat, belongs to the beat layer and should stay out of the tempo curve; at 1.5 bars it leaks in by about 8%, while a 1-bar cutoff would let about half of it in. Motion over two bars or more, such as phrase arcs and ritardandi, should stay in the curve; at 1.5 bars it keeps at least 85%. The value of 1.5 is roughly the shortest cutoff that meets both, and the lead accepted it as the default after F-03.

An automatic alternative exists: generalized cross-validation, a standard method that picks the penalty by how well each point is predicted from the rest. It is available but not the default, because it undersmooths when neighbouring residuals resemble each other, which is exactly the case for expressive timing. On Chopin's Etude Op. 10 No. 12 it chose cutoffs of only 1.3 to 2.0 beats, which pushed genuine rubato into the smooth curve and left a residual of 26 to 39 ms, against 46 to 67 ms with the default. It would make every performance look cleaner than it is.

In the code: `cutoff_to_lambda`, `_gcv_lambda` and `TempoConfig.cutoff_bars` in `src/pianolens/features/tempo.py`; the decision is in `DECISIONS.md` ("after F-03").

#### How does the fit avoid being bent by a few bad notes?

Real alignments contain mistakes, and real performances contain a few wildly placed notes. A least-squares curve would bend toward them. The tempo model defends against this in two stages.

The first stage removes gross outliers before any fitting. For each position, a straight line is fitted separately to its neighbours on the left and on the right, within one bar (at least two beats and three points). The lines use Theil-Sen regression, which takes the median of all pairwise slopes and so ignores a minority of bad points. A position is a gross outlier only if it misses both one-sided predictions by more than 0.15 s or half a local beat, whichever is larger; the tolerance doubles at the edges of the piece, where only one side exists. Requiring both sides to disagree protects genuine tempo changes, since after a sudden change one side still agrees. Gross outliers stay in the output with their deviation, flagged, and every timing statistic ignores them.

The second stage is robust fitting. After each fit, positions with large residuals get lower weight and very large ones get none, using Tukey's bisquare weight function with the standard textbook tuning constant of 4.685, for up to six rounds. The scale that defines "large" is 1.4826 times the median absolute residual (the factor turns a median absolute deviation into a standard deviation for normally distributed data), multiplied by a degrees-of-freedom correction. That correction is needed because a flexible curve absorbs some of the noise and makes the residual look smaller than the truth. The effective degrees of freedom (edf) count roughly how many free numbers the curve used, and the factor `sqrt(n / (n - edf))` undoes the shrinkage. One bug was found and fixed here: measuring the spread around the median residual, rather than around zero, collapsed every weight to zero when the residual was a periodic pattern.

In the code: `_gross_outliers`, `_theil_sen`, `_bisquare` and `fit_time_map` in `src/pianolens/features/tempo.py`; the bug is recorded in the feature-engineer memory (`tempo-model-f03.md`).

#### Where is the curve allowed to jump?

A smooth curve would smear a sudden "a tempo" across the neighbouring bars and turn a held fermata into a false slowdown. So the model cuts the performance into segments at breaks and fits each segment separately. There are two kinds of break. At a kink, the tempo may change instantly but time stays continuous, so the position at the break is shared by both segments and they meet there. At a gap, time itself may jump, as during a held note, so the two sides are fitted independently and the extra time is recorded.

Kinks come from the score. Words that set a new tempo count: "a tempo", "tempo I", "più", "meno", "mosso", and the standard tempo names from grave and largo to prestissimo. "Tenuto" and "stretto" are excluded because partitura parses them as tempo directions although they do not set a new tempo. Gradual words such as rit. and accel. are deliberately not breaks: gradual change is what the smooth curve is for. Metronome marks count only when they change by at least 25%, because ASAP scores contain many hidden metronome marks that are playback artefacts; Chopin's Op. 10 No. 3 has 20 of them, about 10% apart.

The model can also detect tempo steps that the score does not mark. At each position it estimates the beat period over the two bars before and the two bars after, again with Theil-Sen, and reports a step when their log ratio is at least `log 1.3`. Because these windows produce a flat plateau of equal values around a step, the exact point is refined by fitting a two-line "hinge" model and choosing the best bend. By default these steps are only reported, not used to split the curve. On Chopin's Op. 10 No. 12 a one-bar window flagged 13 to 22 "steps" per performance, and a two-bar window still 4 to 9; these were ordinary rubato, which belongs in the smooth curve. Splitting can be switched on for pieces known to change tempo without a marking.

Gaps come from fermatas in the score and from detected pauses. A pause is an inter-onset interval at least 2.5 times the local expectation and at least 0.3 s longer than expected. Both conditions are needed: the ratio alone would fire on short notes at slow tempi, and the absolute margin alone would fire on ordinary long notes. The held time is kept out of the tempo curve but still counts in the overall tempo (total beats divided by total time). On Op. 10 No. 12 the model found 6 to 11 pauses per performance, mostly just before a downbeat, which are breaths. If a segment ends up with a single position, it borrows the slope of its nearest neighbour.

In the code: `score_tempo_breaks`, `_detect_steps`, `_refine_step` and `_detect_pauses` in `src/pianolens/features/tempo.py`; step splitting is `TempoConfig.split_on_steps`.

#### What does the tempo model hand on to other features?

The model returns tables at several levels. Per score position it gives the performed and smooth times, the raw and smooth beat period, tempo, log tempo ratio, deviation in seconds and beats, robust weight, outlier flags, bar number and position in the bar. Per note it gives the same deviation plus the note's offset from its chord's median. Per integer beat it gives the smooth curve on a regular grid, which is what tier C, tier D and the report card read. Per bar it gives tempo, residual size and the largest deviation.

The summary holds two overall tempi (one that ignores pauses and one that includes them), the spread of the smooth log tempo, and the size of the residual, called jitter. Jitter is given as a root-mean-square value corrected for degrees of freedom, `sqrt(sum r^2 / (n - edf))`, and as a robust version based on the median absolute deviation, each in milliseconds and in beats.

One more product matters for tier B: the metric profile. For every position within the bar that occurs at least three times, it takes the median deviation, for example "the second beat is 0.07 beat late on average". This is the performance's own recurring beat-level habit, the "beat and meter" layer of the plan. Subtracting it from the residual gives a cleaner noise measure, `jitter_nometric_rms_ms`, which tier B uses when no expert references are available.

The model also offers a hook, `phrase_arcs`, that fits a parabola to the smooth log tempo inside given phrases, following Repp (1992). Tier C uses it; tier B does not.

Two conventions for the curve coexist in the code. Control features use the fit that respects score markings. Tier D and the report card use a fit without score markings, so that each target matches a cached set of reference curves computed that way. The two residuals for the same performance are therefore close but not identical.

In the code: `TempoCurve`, `_metric_profile` and `phrase_arcs` in `src/pianolens/features/tempo.py`; the second convention is described in `src/pianolens/features/interpretation.py`.

#### Does the tempo model do what it claims?

The model was first checked on synthetic performances whose answers are known:

| Test | Expected | Result |
|---|---|---|
| Perfectly metronomic performance | zero jitter, constant 120 BPM | jitter under 0.001 ms |
| Steady linear ritardando | recovered exactly by the smooth curve | beat period within 1e-5 s, jitter under 0.01 ms |
| 20 ms random onset noise | about 20 ms jitter | 17 to 23 ms (0.034 to 0.046 beats at a 500 ms beat) |
| Sudden change from 60 to 90 BPM | one reported step at the right beat | found at beat 64; splitting there removes the residual |
| Score tempo marking | a kink at the marking | curve exactly 60 then 90 |
| Fermata or detected pause | a gap, not a tempo dip | held time of 1.2 s recovered; tempo stays 120 |
| One grossly misplaced position | flagged and ignored | only that position is an outlier |
| Chords spread by 30 ms | one time per chord, spread kept | spread 0.030 s |
| A pattern repeating every bar | captured by the metric profile | about 0.07 beat at the pattern position |
| Cross-validated smoothing on pure noise | a very smooth curve | cutoff over 16 beats, jitter 17 to 23 ms |

On six ASAP performances of Chopin's Op. 10 No. 12 with default settings, the average tempo ranged from 132.5 to 147.0 quarter-note beats per minute, the spread of the smooth log tempo from 0.139 to 0.167, and jitter from 46 to 67 ms (32 to 46 ms robust, 37 to 51 ms after removing the metric profile). The model runs in about 0.2 to 0.5 s for a performance of about 1,300 positions.

The most important finding came from comparing residuals across pianists. If the residual were pure motor noise, different pianists' residuals on the same piece would be unrelated. They were not:

| Cutoff | Residual correlation across performers | After removing each performer's metric profile |
|---|---|---|
| 1 bar | 0.52 | 0.31 |
| 1.5 bars | 0.59 | 0.42 |
| 2 bars | 0.58 | 0.48 |

A large part of the residual is timing the score invites and many pianists share: lengthened important notes, breaths, fine phrasing. The lead therefore decided that tier B must not read raw jitter as motor noise, which led to the consensus-based measure described below.

In the code: `tests/features/test_tempo.py`; the real-data numbers are from `scripts/check_tempo_f03.py` as recorded in the feature-engineer memory; the decision is in `DECISIONS.md` ("after F-03").

#### What went wrong numerically, and how was it fixed?

During the transcription check in D-10, one of 66 performance pairs crashed inside the tempo-stability feature with a Cholesky error. The case was an Aria-AMT transcription of the first movement of Beethoven's Appassionata. The error was logged as defect DF-01.

Cholesky factorization only works on matrices that are positive definite, meaning, loosely, that the system has one well-defined best solution. The penalized system is the data part plus the penalty part plus the tiny safety term. The penalty part is singular by design, because it does not charge for quadratic curves. When part of a segment has few data points and the penalty weight is large, the entries of the matrix become huge, and a fixed safety term of `1e-10` is too small relative to them. Rounding errors then make the matrix look not quite positive definite, and the factorization fails. The failing fit was the one with a 4-bar cutoff used by tempo stability, whose penalty is much larger than the default fit's.

The fix tries progressively safer methods. If the factorization fails, the model retries with a ridge (an extra diagonal term) scaled to the matrix: `1e-8` times the average diagonal entry, and at least `1e-8`. If that also fails, it uses the pseudo-inverse, which always exists. A regression test forces the factorization to fail once, and then always, and checks that the result is finite. The real failing performance has not been rerun since the fix. The error never appeared on the 1,604 MAJEPPA performances.

In the code: `_penalized_fit` in `src/pianolens/features/tempo.py`; test `test_penalized_fit_survives_cholesky_failure`; defect DF-01 in `DEFECTS.md`.

#### What does "control" mean, and how is it measured?

Tier B tries to measure whether a player can make the instrument do what they intend, separately from what they intend. The strategy is to look where the score or common practice fixes the answer, so that departures are more likely to be lack of control than interpretation. Five feature families follow this strategy:

| Feature family | What the score or practice fixes | Sign of weak control |
|---|---|---|
| Timing noise | the fine timing that experts share for this piece | onsets scattered around what experts do |
| Evenness | notes of equal written length in scales and figures | uneven spacing or loudness in those passages |
| Hand synchrony | notes written to sound together | hands that do not land together, beyond what loudness explains |
| Tempo stability | tempo within a section without tempo markings | wobble faster than a phrase but slower than a beat |
| Pedal blur | changes of harmony | the sustain pedal held across a change of chord |

All five share some conventions. Each gives a value per bar of the performed score as well as summary values, so the report card can point at bars. Unmatched, interpolated and grace notes are skipped and counted, and positions the tempo model flagged as gross outliers are left out of timing statistics. All parameters sit in one configuration object, and the values used are stored with each result.

In the code: `control_features` and `ControlConfig` in `src/pianolens/features/control.py` (tickets F-04 and F-04b).

#### How much of a player's timing is noise?

Because the tempo residual contains shared, intended timing, PianoLens estimates noise as the part of the residual that differs from what other expert pianists do at the same spot. For each score position, the consensus is the average normalized deviation of the reference performances there, leaving out the target itself. At least three references must have a usable value at the position. The noise is the target's deviation minus the consensus, in beats and in milliseconds. As with jitter, the summary is corrected for the tempo fit's degrees of freedom.

The idea mirrors a classic study of scale playing. Van Vugt, Jabusch and Altenmüller (2012) split each note's deviation into a systematic part, the average over many trials, which they called irregularity, and a trial-to-trial part, which they called instability and read as motor noise. Here the expert consensus plays the role of irregularity and the leftover plays the role of instability. As a reference point for expert noise, Tominaga et al. (2016) found that prize-winning pianists varied by 7.9 ms per keystroke from trial to trial at a 250 ms interval.

Two supporting numbers are reported with it. The consensus R² is the share of the residual that the consensus explains. Coverage is the share of positions that have a consensus. When coverage is at least one half, the headline value (`timing_noise_best_*`) uses the consensus; otherwise it falls back to the residual minus the performance's own metric profile. The output always names which source was used.

There is a known bias. With K references, the consensus contains their own noise, so the measured noise is inflated by roughly `sqrt(1 + 1/K)`. This is not corrected; the median number of references is reported so a reader can judge.

On a synthetic test with 30 references that share a 30 ms random timing pattern plus 3 ms of their own noise, and a target with the same pattern plus 10 ms, the measure recovers about 10 ms and the consensus explains over 80% of the residual. The fallback, which cannot see the shared pattern, stays above 25 ms. On real performances, with 5 leave-one-out references for ASAP and 21 for the Vienna 4x22 set, the group medians were:

| Piece | Noise against consensus (ms) | Fallback (ms) |
|---|---|---|
| Bach, Prelude BWV 848 | 8.9 | 8.1 |
| Chopin, Op. 10 No. 12 | 36.8 | 43.7 |
| Schubert, D.899/3 | 54.0 | 65.9 |
| Chopin, Op. 10 No. 3 (Vienna) | 42.1 | 73.2 |
| Mozart, K.331 theme (Vienna) | 29.2 | 35.4 |

The consensus explained from 8% (Bach) to 70% (Vienna Op. 10 No. 3) of the residual. Its lowest value was -0.64, meaning that for some performances subtracting the consensus added variance: that pianist's fine timing ran against the group.

This negative value points to the measure's main limit. A pianist who departs from the expert habit on purpose is scored as noisy; the measure cannot tell an unusual intention from poor control. It also depends on references that took the same repeat path. On MAJEPPA the consensus was available for only 32% of performances, and the rest used the fallback. The batch feature extractor used in R-04 runs without references, so R-04's timing measure is the fallback.

A different route to noise is to compare a player with themselves. F-07 and BL-16 found that a pianist's own take-to-take variation is mostly unstructured, so it can be read as noise; in BL-16's Rach3 Hanon data it was 7.5 ms for the advanced players on the same day and 11.3 ms for the beginner. Two rules follow from that work. Take-based noise uses takes from the same sitting only, because takes on different days carry structured drift. And timing that stays consistent across takes must not be read as a pianist's intent, because F-07's audit showed that two different pianists pass the same test: the consistent part is timing any two performances of the piece share.

In the code: `timing_noise`, `fine_timing_consensus` and `reference_residuals` in `src/pianolens/features/control.py`; decisions in `DECISIONS.md` ("after F-03", "F-07 / H5 is Confirmed with caveats", "BL-16 is Confirmed with caveats").

#### Are scales and accompaniment figures played evenly?

In a scale or an Alberti bass the notes are written with equal lengths, and a controlled player spaces them evenly in time and loudness unless shaping them on purpose. Unevenness in such passages is one of the oldest measured signs of motor skill. Jabusch, Vauth and Altenmüller (2004) introduced MIDI-based scale analysis, and Jabusch et al. (2009) found that scale evenness improved with the amount of practice.

The first problem is finding the passages. The broad rule takes any stretch of at least six consecutive onsets in one staff-and-voice stream of the score, all with the same written length and no rests between them; where several notes start together, the shortest counts. This rule turned out to cover most onsets in figurative music (82 to 99% in the sanity set), including melodies whose uneven timing is expressive. So a strict rule was added. A strict run lies inside a broad run, uses notes shorter than one beat, and consists only of monotone stretches, in which every step moves in the same pitch direction (scales, arpeggios), or repeated figures, in which the same set of pitches recurs with a period of one to four onsets at least twice. The second kind catches the Alberti bass (the classical left-hand pattern of low, high, middle, high notes of a chord, such as C-G-E-G) and repeated-note or broken-chord accompaniment. The lead decided to keep both rules and choose by evidence rather than taste; R-04 could not separate them on PercePiano, so both remain, and the report card uses the strict one.

Timing evenness is measured on tempo-normalized intervals. Each interval between consecutive run onsets is divided by the interval the smooth time map expects there, so a scale played under a smooth ritardando counts as perfectly even and only departures from the local tempo count. Only intervals whose two onsets are both matched and in the same tempo segment are used, and a run needs at least four. The measure is the coefficient of variation (standard deviation divided by mean) of these ratios.

Loudness evenness uses MIDI velocity, the recorded key speed, which sets loudness on a scale from 0 to 127. Before measuring spread, a trend in score position is removed: a straight line, or a parabola for runs of twelve or more notes. A crescendo or a hairpin shape therefore does not count as unevenness. The measure is the standard deviation of what remains.

Both measures are reported with the note rate of the runs, in notes per second, because unevenness rises with speed for timing and for loudness (MacKenzie and Van Eerd 1990). D-10 measured this on MAJEPPA as a slope of +0.58 on a log scale. Values are only comparable at similar rates, and the report uses a window of plus or minus 20% in note rate when comparing with published values.

The published values give a sense of scale, though all come from instructed, metronomic scales:

| Reference | Value |
|---|---|
| Professionals, scale timing spread at 8 notes/s | 8.4 ms right hand, 9.2 ms left hand; coefficient of variation about 0.07 |
| Music students at 10.7 notes/s | 10.4 and 12.3 ms; about 0.11 to 0.13 |
| Listeners notice unevenness at 8 notes/s | about 10.2 ms; about 0.08 (van Vugt 2013) |
| Expert trial-to-trial velocity spread | 4.1 MIDI units (Tominaga 2016) |
| Smallest audible velocity step between consecutive notes | 2.7 to 4.5 MIDI units (Slade 2023) |

Most professionals' unevenness lies below what listeners can hear. The values in real repertoire also contain expressive micro-timing and alignment noise, so the published values are a floor, not a norm. No study of Alberti bass evenness with reported values was found.

The synthetic tests check each part. A perfectly even scale under a ritardando has a coefficient of variation below 1e-4. Onset noise of 10 ms on a scale of 250 ms notes gives the expected value of about `sqrt(2) × 10 / 250`, since interval noise is the difference of two onset noises. A velocity noise of 6 laid over a crescendo from 40 to 100 is recovered as about 6. In a mixed texture the broad rule finds five runs and the strict rule three (the scale, the Alberti bass and the repeated-note bass), and noise added only to a zigzag melody moves the broad measure but not the strict one. On real performances:

| Group | Broad share of onsets | Strict share | Broad timing CV | Strict timing CV | Strict velocity SD | Strict rate (notes/s) |
|---|---|---|---|---|---|---|
| Bach BWV 848 prelude (6 ASAP) | 0.84 | 0.34 | 0.099 | 0.110 | 4.27 | 8.7 |
| Chopin Op. 10 No. 12 (6 ASAP) | 0.97 | 0.37 | 0.299 | 0.302 | 7.03 | 9.2 |
| Schubert D.899/3 (6 ASAP) | 0.82 | 0.07 | 0.242 | 0.347 | 7.89 | 8.3 |
| Batik K.279/1 | 0.83 | 0.39 | 0.156 | 0.146 | 5.57 | 7.8 |
| Vienna Chopin Op. 10 No. 3 (22) | 0.99 | 0.46 | 0.142 | 0.147 | 6.00 | 2.1 |
| Vienna Mozart K.331 theme (22) | 0.24 | 0.00 | 0.095 | n/a | n/a | n/a |

The nearest comparison with published work is the Bach prelude at about 8 notes per second: a strict value of 0.11 against the professional scale floor of 0.07. In the Rach3 Hanon data, recorded on a keyboard without transcription, the advanced pianist p1 reached 0.061 to 0.067 at 4 to 8 notes per second, close to van Vugt's professional value.

The measure has known weaknesses. Part of real scale unevenness is systematic and neuromuscular, such as late notes at the thumb passage and a peak at the octave boundary (van Vugt 2012 and 2014), and the coefficient of variation pools it with random noise. Velocity spread is not a skill measure on its own: in Rach3 the beginner had a lower velocity spread than the advanced pianists, probably because a softer, flatter player uses a narrower range. And score MIDI files often store playback lengths (an eighth note lasting 0.4979 quarters), which breaks the "no rests" rule; for MAJEPPA, lengths are extended to the next onset when the gap is at most 7% of the interval.

In the code: `even_runs`, `strict_runs` and `_evenness` in `src/pianolens/features/control.py`; validation in `docs/specs/control-validation.md`; decisions in `DECISIONS.md` ("F-04 follow-ups", "after R-04", "after F-08").

#### Do the hands play together, and how do we know which hand played a note?

When notes in both hands are written at the same moment, a controlled player sounds them together, or leads with one hand consistently for a musical reason. Scattered, inconsistent gaps between the hands are a sign of weak coordination. The measure takes every score onset where both staves have matched notes and computes two differences: the mean onset of the upper-staff notes minus the mean onset of the lower-staff notes, in milliseconds, and the same difference in mean velocity.

MIDI does not record which hand played a note, so PianoLens assumes the upper staff is the right hand and the lower staff the left hand, as notation intends. For MAJEPPA, whose score files carry no staff information, the higher of the two note tracks becomes the upper staff; 829 of 886 score files have exactly two tracks, and in a 40-score check only 0.14% of notes could not be placed. This assumption fails for hand crossings, for notes written in the other staff, and when one hand takes notes from both staves. None of these cases is detected. Score-only proxies suggest they touch a small share of the onsets hand synchrony compares in most pieces (median 0.9%), but more than 20% in about 1 piece in 25, and the proxies miss most engraver-marked hand swaps (BL-19). Against real video hand labels the staff is wrong for 6.66% of notes, and hand synchrony passes its rule only at the boundary (BL-19b; see "How do we know which hand played a note?" in the alignment chapter). Piano duets are detected and get no hand synchrony (DF-11). Since DF-09, the two main staves of every score are renumbered to 1 and 2 before alignment, so scores that numbered them differently no longer give an empty result.

The sign convention is that a positive value means the left hand came first. This is the opposite of Goebl, Flossmann and Widmer (2009, 2010), whose values must be negated before comparison.

The central difficulty is a physical artefact. A MIDI onset is the moment the hammer strikes the string, not the moment the finger starts moving. A louder note is a faster key press, so its hammer reaches the string sooner. If both hands start together and one plays louder, the louder hand still sounds first. Goebl (2001) showed that the familiar melody lead of about 30 ms is mostly this effect, and Repp (1996) found that leads follow the velocity difference. PianoLens therefore fits the asynchrony against the velocity difference with a straight line, using only points within three robust standard deviations of the median, and treats what the line does not explain as the coordination signal. The slope captures the artefact. On real performances it is negative, as the physics predicts (right hand louder, right hand earlier): between -0.14 and -1.08 ms per velocity unit in the sanity set. As a cross-check, the spread is also computed only over onsets where the two hands' velocities differ by at most 5 units.

Spreads use a robust standard deviation: 1.4826 times the median absolute deviation from the median. The distribution has heavy tails from arpeggiated chords, deliberate bass anticipations and alignment errors, and a plain standard deviation would be dominated by a few such events. The robust version describes the typical onset. Notated arpeggios are not removed, although Goebl, Flossmann and Widmer did remove them (with ornaments, trills and grace notes, about 10% of their events); the robust spread limits their effect without eliminating it.

The mean asynchrony is reported but not treated as noise, because a consistent lead may be a style: Repp (1996) found that some pianists lead with the left hand consistently, independent of velocity. The motor-noise measure is the robust spread after the velocity fit (`hand_async_resid_sd_ms`), with a version in beats.

For scale, Magaloff's complete Chopin (163,208 events) showed a mean of 4.4 ms and a most common value of 13 ms with the right hand early in Goebl's sign, and faster pieces were more synchronous. Goebl uses plus or minus 30 ms as the limit of audibility, citing a source the project has not read directly. The only expert against amateur figure found is Kim et al. (2021): a between-hand spread of 0.008 against 0.014, with no unit stated (probably seconds).

A synthetic test with a constant 20 ms left-hand lead gives a mean of exactly 20 ms and zero residual spread. When the right hand is made earlier by 2 ms per unit of extra loudness, the fit recovers a slope of -2.0 and zero residual, while the raw spread exceeds 5 ms. On real performances the residual spread was 10 to 32 ms, with a maximum of 91 ms in Schubert. In Rach3 Hanon the beginner's octave onset spread was 21.6 to 22.4 ms against 13.9 to 16.2 ms for both advanced pianists, in every shared speed range. That is the cleanest separation of any control measure seen so far, but with three pianists it is an illustration, not evidence.

In the code: `hand_synchrony` in `src/pianolens/features/control.py`; the MAJEPPA staff heuristic is `with_track_staff` in `pianolens.data.majeppa`; sources in `docs/research/2026-09-27-landscape.md`, section 1.5.

#### Does the player hold a steady tempo?

Within a section that has no tempo marking, a controlled player keeps a steady pulse apart from deliberate phrase shaping. The difficulty is separating unsteadiness from shaping. PianoLens does this by comparing two smooth curves of the same performance. The tempo model's own curve keeps motion slower than 1.5 bars. A second, stiffer curve with a 4-bar cutoff keeps only motion slower than about four bars, which is treated as the phrase-level allowance: phrase arcs and long ritardandi, which Repp (1992) and van Vugt et al. (2014) show are expected. The difference between the two curves is tempo wobble at the scale of 1.5 to 4 bars, too fast to be phrasing and too slow to be beat-level timing, which already sits in the residual.

Sections are the tempo model's segments, so the curve is already split at tempo markings, fermatas and pauses. Spans of gradual markings (rit., accel.) are excluded, up to the marking's end or two bars when no end is given. A section must span at least two bars and six positions. The main value is the root-mean-square difference between the two curves, pooled over sections and weighted by the number of beats used. The output also gives the total spread of tempo in each section, the spread of the phrase curve, and the drift: the average absolute net change of a straight line through each section, which captures rushing or dragging.

The 4-bar allowance is the project's own choice; no published source measures tempo wobble beyond the phrase level. In a synthetic test, constant tempo gives zero instability, a tempo wobble repeating every two bars keeps about 82% of its size in the measure, and an arc over eight bars keeps about 16%, being absorbed into the phrase curve. On real performances the value ranged from 0.033 to 0.088 on the natural-log scale.

Real phrases are not all four bars long, so a genuine 2-bar phrase arc counts as instability and an 8-bar wobble counts as phrasing. The drift is an absolute value, so rushing and dragging are not told apart. And this feature showed no separation between skill levels even in the pooled MAJEPPA data (advanced to beginner ratio 0.91, 95% confidence interval 0.75 to 1.13).

In the code: `tempo_stability` and `_gradual_spans` in `src/pianolens/features/control.py`; the decision to accept the 4-bar allowance is in `DECISIONS.md` ("F-04 follow-ups").

#### How are harmony changes found in the score?

Clean pedalling means changing the pedal when the harmony changes, so the pedal feature first needs to know where the harmony changes. PianoLens finds these from the score with a simple, validated rule rather than a full harmonic analysis.

The score is cut into windows of one quarter note. In each window, the rule keeps the pitch classes (note names regardless of octave) that fill at least 15% of the window's sounding note-time, plus the bass, the pitch class of the lowest sounding note. A window starts a new harmony when its bass differs from the previous window's bass and the two windows' pitch classes together do not fit inside one chord template. The templates are the major, minor, diminished and augmented triads and the dominant, half-diminished and diminished seventh chords, in all twelve keys. The change time is the performed time of the first note in the window. By design, Alberti figuration inside one chord is not a change, because both bass and chord tones stay inside one template. Also by design, a pedal point (a held bass under changing chords) hides a change, because the bass never moves.

The rule was checked against expert harmony labels from the DCML corpus (Hentschel, Neuwirth and Rohrmeier, TISMIR 2021) for the Batik-plays-Mozart recordings: 36 movements with 11,675 changes of chord root. A detection counted as correct if it fell within one quarter note of a label, matched one to one. Variants were chosen on 15 movements and checked on the other 21. Performance is summarized with precision (the share of detections that are real), recall (the share of real changes found) and F1 (their balance).

| Rule | Precision | Recall | F1 | F1 on held-out movements |
|---|---|---|---|---|
| Original (1-beat window, all 9 templates) | 0.759 | 0.696 | 0.726 | 0.710 |
| Adopted (1-quarter window, 7 templates) | 0.749 | 0.774 | 0.761 | 0.752 |

Two changes produced this gain, and both have a musical reason. The original window was one beat, which made the rule depend on the meter: in 2/2 two chords often fell into one half-note window (recall 0.56), and in 6/8 passing notes in eighth-note windows started false harmonies (precision 0.60). A quarter-note window removes that dependence; F1 by meter now ranges from 0.743 (3/4) to 0.794 (2/4). The original templates also included the major and minor seventh chords, which two incomplete neighbouring chords can fill: C-E followed by G-B makes C major seventh, and A-C-E followed by C-E-G makes A minor seventh. Dropping them stops a tonic and dominant, or a submediant and tonic, from merging into one "chord". In all, 168 variants were tried; a lower 10% threshold did better on the development movements but gained nothing on the held-out ones and was not adopted.

The remaining 2,640 misses are mostly pedal points and common-bass progressions (1,145), two changes within one quarter note (846), and pairs of chords whose notes together fit one template (592). Of the 3,020 false alarms, 2,297 are bass moves under one root, such as a chord moving to its first inversion. For pedalling these are arguably real events, since holding the pedal over a new bass note does blur two bass notes. Bars with no left hand are poor (F1 0.407), because the lowest melody note acts as a false bass.

In the code: `harmony_windows` and `harmony_changes` in `src/pianolens/features/control.py`; validation in `docs/specs/control-validation.md`, section 2; decision in `DECISIONS.md` ("accept the F-04b harmony rule").

#### Is the pedal changed cleanly when the harmony changes?

The sustain pedal lifts all the dampers off the strings, so notes keep ringing after the keys are released. If the pedal stays down through a change of harmony, the old chord keeps sounding under the new one, and the result is blur. The standard technique is legato, or syncopated, pedalling: play the new chord, lift the pedal immediately after it sounds, then press it again (Liang, Fazekas and Sandler, EUSIPCO 2018). Doing this cleanly is a basic control skill.

MIDI records the sustain pedal as controller number 64 (CC64), a value from 0 to 127. PianoLens counts the pedal as down when the value is at least 64. A harmony change at time `t` is blurred if the pedal is down a quarter of a beat before the change and is not lifted until half a beat after it (the beat length being the local smooth beat period). The summary gives the fraction of changes that are blurred and the average time the pedal stays down after a blurred change, in beats, capped at the next change and at four beats. The share of the whole performance with the pedal down is reported as context. When a performance has no pedal data, every pedal value is missing and the output says so.

The window is asymmetric for a reason. A lift just after the new chord is correct legato pedalling, so the window must reach past the change. A lift just before the chord is also clean, so the pedal must already be down shortly before the change for blur to count. No published norm exists for the timing of pedal lifts relative to harmony changes, so the window was checked on sensor pedal data:

| Source | Changes | Pedal down 1 beat before | Lift inside the window | Median lift time (beats from the change) |
|---|---|---|---|---|
| Batik, annotated root changes | 11,675 | 2,625 | 0.529 | -0.21 |
| Batik, control onsets away from changes | 8,286 | 2,178 | 0.427 | -0.17 |
| Vienna K.331, annotated root changes | 1,320 | 406 | 0.865 | -0.02 |
| Vienna Op. 10 No. 3, detected changes | 396 | 211 | 0.962 | +0.01 |

The 22 Vienna pianists lift within about a quarter beat of the change, the behaviour the rule assumes. Batik pedals little in Mozart and tends to lift before the change, which the window correctly treats as clean. With the default window, expert blur is at most 1% (0.6% for Batik, 0.8% for Vienna K.331). Narrowing the window after the change to a quarter beat would flag 3% of the Vienna experts' clean changes; removing the margin before the change would flag 2.8% of Batik's. Widening the window barely lowers these numbers and would let real blur pass as clean. The threshold hardly matters for blur: the blurred fraction is flat for thresholds from 32 to 112, and only 16 differs, because it falls in the range where a resting foot sits (49% of Batik's pedal events are below 32). The pedal-down share, however, depends strongly on the threshold for the Vienna pianists, who use partial depths a lot. On the sanity set the median blurred fraction was 0.24 for Chopin's Op. 10 No. 12, 0.062 for Schubert's D.899/3, 0.020 for Vienna K.331, and 0 elsewhere.

The feature has clear limits. Pedal depth is continuous and pianists use half and quarter pedal on purpose (Bernays and Traube 2014); a single threshold turns this into on and off. Pedal markings in the score are not read, so a wash of sound the composer asked for is scored as blur. The feature needs real pedal data: PianoCoRe has none, while ASAP, MAESTRO, Vienna 4x22 and Batik do. Pedal from audio transcription is not usable yet (see below). The harmony ground truth is one annotation style on one composer. And no student pedalling has been measured, so whether the feature separates skill levels is untested.

In the code: `pedal_blur` in `src/pianolens/features/control.py`; validation in `docs/specs/control-validation.md`, section 3; sources in `docs/research/2026-09-27-landscape.md`, section 1.5.

#### Do these features actually measure skill?

Every feature above was designed to reflect control. Whether it separates players of different skill is an empirical question, and the answer so far is that it has not been shown.

The main test, D-10, ran all tier B features on 1,604 MAJEPPA performances, transcribed from video with Transkun, at six skill levels. Each piece was compared only with itself (piece fixed effects), and a term for note rate was included because faster playing changes these measures. Pooled over all recordings, advanced performances showed about 25% less timing noise, unevenness and between-hand spread than beginners, with confidence intervals that excluded no difference. Loudness evenness showed a smaller effect, and tempo instability and pedal blur showed none.

| Feature | Advanced / beginner, all recordings (95% CI) | Practice and performance recordings only |
|---|---|---|
| Timing noise (ms) | 0.75 (0.69 to 0.81) | 0.93 (0.80 to 1.08) |
| Strict timing evenness | 0.68 (0.60 to 0.78) | 0.92 (0.72 to 1.19) |
| Hand-sync residual spread (ms) | 0.75 (0.68 to 0.83) | 0.98 (0.83 to 1.18) |
| Tempo instability | 0.91 (0.75 to 1.13) | 0.99 (0.80 to 1.29) |

The problem is recording context. Every virtuoso clip in MAJEPPA is a concert recording and nearly every piano-teacher clip is a class demonstration, while beginners are mostly practice and sight-reading clips. When the comparison is restricted to practice and performance clips, which both groups recorded the same way, every tier B ratio lies between 0.92 and 1.05 and every confidence interval includes 1.

The audit narrowed this conclusion further. Restricting to practice and performance clips removes the context difference, but it also removes the top two skill levels. So the data cannot tell "the effect is context" from "the effect only appears at the top of the scale". The honest reading is that tier B separation is not shown between beginner and advanced-student levels, and that the top levels are confounded with concert and demonstration context. R-09 found the same structure for timing coherence, a tier C measure.

Several other features of the data weaken the test. The alignment quality gate depends on skill: 31 to 36% of beginner performances were excluded as untrusted, so the remaining beginners are the more fluent ones, which favours finding no difference. MAJEPPA identifies videos, not people, so the confidence intervals may be too narrow. The matched subset is too small to detect effects below about 20%. And speed interacts with units: timing in milliseconds shrinks as tempo rises (a slope of -0.72 on the log scale), and advanced players play faster, so without the rate term the timing-noise ratio would have been 0.57. Measures in beats depend much less on rate.

The lead's conclusion is that tier B skill validity is unproven, not disproven. A clean test needs recordings in which skill varies while the setting does not: Henry's own takes, PianoVAM audio run through a transcriber and compared with its keyboard MIDI, or the stimuli of the planned listening study.

In the code: `docs/specs/skill-control-check.md` (with its post-audit note); `experiments/2026-09-28-R-09-coherence-skill/README.md`; decisions in `DECISIONS.md` ("after D-10", "R-09 is Confirmed with caveats").

#### What survives when the notes come from an audio recording?

For a phone recording, the notes come from an automatic transcriber rather than from a MIDI piano, and the transcriber adds its own errors. D-10 measured how much this matters by running tier B on performances that exist both as Disklavier MIDI and as a transcription of the same performance's audio.

| Measure | Aria-AMT (59 pairs) | Transkun (6 pairs) |
|---|---|---|
| Local onset error, robust spread | 4.5 ms | 9.3 ms |
| Velocity: fitted slope, residual spread | 0.95, 5.7 MIDI units | 0.64, 9.0 MIDI units |
| Timing jitter, transcription / Disklavier | 1.02 | 1.01 |
| Broad timing evenness | 1.02 | 0.85 |
| Strict loudness evenness | 0.95 | 0.86 |
| Hand-sync residual spread | 1.02 | 0.98 |
| Tempo instability | 1.00 | 1.20 |
| Pedal-down share (Disklavier to transcription) | 0.75 to 0.71 | 0.59 to 0.35 |

Timing survives. An independent error of about 9 ms adds only 2 to 3 ms, in quadrature, to the 15 to 35 ms of expressive residual in these performances; the median added jitter on the Transkun pairs was 2.2 ms. Transkun also compresses rather than adds noise: it lowered timing unevenness by 15% and velocity spread by 10 to 14%. Velocity does not survive: a residual of 9 MIDI units is two to three times the smallest audible step, while the pooled skill effect on loudness evenness was only 0.5 to 0.8 units. Velocity features on transcribed input are therefore excluded from skill claims unless the source is a sensor piano or the velocity has been calibrated. Pedal does not survive either, since Transkun roughly halves the pedal-down time. The practical rule is that reports built from phone recordings trust timing and tempo only.

These pairs are fast expert performances on a competition piano. The transcription error on phone recordings of home upright pianos, which make up much of MAJEPPA's beginner material, has not been measured and is likely larger. It would push beginners' timing features up, in the same direction as a real skill effect, which is a second way that recording context can imitate skill.

In the code: `scripts/check_transcription_noise_d10.py`; results in `docs/specs/skill-control-check.md`, section 1; decisions in `DECISIONS.md` ("after D-10", "after A-01").

#### Where are these features used?

In R-04, the symbolic model on PercePiano, the batch extractor adds the tempo summaries and sixteen control summaries: broad and strict evenness with their note rates, hand-sync mean, spread in beats, velocity slope and residual spread, tempo instability, phrase spread, drift, and the three pedal values. It runs without references, so timing noise there is the fallback. The report card uses strict evenness runs and computes timing noise on the tier D curve convention, flagging a bar only when it lies outside the range of expert performances at that bar. Tier C and tier D read the smooth curve and residual from the same tempo model.

In the code: `_CTRL_KEYS` and `segment_features` in `src/pianolens/features/extract.py`; the report is in `src/pianolens/report/`.

#### Known gaps and untested assumptions

- **Skill validity.** Tier B separation of skill is unproven within any matched recording context. The top MAJEPPA levels cannot be separated from concert and demonstration context.
- **Unusual intent read as noise.** Timing noise scores any departure from the expert consensus as noise. How often good players are penalized for deliberate choices is untested.
- **Consensus inflation.** The `sqrt(1 + 1/K)` inflation from noisy references is not corrected, so values with few references are biased upward.
- **Repeat paths.** References that took a different repeat path drop out silently; the effect on coverage outside ASAP and Vienna is not measured.
- **The 1.5-bar cutoff** rests on filter reasoning and residual correlations from one piece. Metrical patterns spanning two bars, and very long or very short bars, are untested.
- **The 4-bar phrase allowance** in tempo stability has no source. Real phrase lengths vary.
- **Tempo words.** Breaks come from a fixed word list applied to what partitura parses as tempo directions. Whether this creates false breaks in some scores is untested.
- **Unmarked tempo changes** are reported but not split by default, so a genuine unmarked change is smoothed over two bars and shows up as instability.
- **DF-01.** The fix is tested synthetically; the real failing performance has not been rerun.
- **Two tempo-curve conventions** (with and without score markings) coexist; their disagreement has not been measured.
- **Systematic unevenness.** Evenness pools neuromuscular patterns (thumb passage, octave boundary) with random noise. Whether separating them would help is untested.
- **Note-rate dependence.** Evenness comparisons across pieces or players need rate matching; the only rule in use is the plus or minus 20% window in the report.
- **Velocity evenness** is not a skill measure without a dynamics reference, and velocity features on transcribed input are low confidence.
- **Hand assignment by staff** is an assumption. Hand crossings, cross-staff writing and shared notes are not detected, and notated arpeggios are not excluded. Against PianoVAM's video hand labels the staff is wrong for 6.66% of notes, systematically (BL-19b); hand synchrony passes only at the boundary, and dropping flagged onsets would barely help (5.49% to 5.34% of onsets affected). Piano duets are now detected and skipped (DF-11).
- **Unverified reference points.** The plus or minus 30 ms audibility band for asynchrony comes from a source not read directly, and Kim (2021) gives no unit for its hand-sync values.
- **Part-pedalling** is invisible to the CC64 threshold, and the pedal-down share depends strongly on that threshold.
- **Score pedal markings** are ignored, so requested washes of sound count as blur.
- **Harmony rule scope.** It is validated only on Mozart with one annotation style. Romantic repertoire, right-hand-only passages and pedal points are weak spots.
- **No student pedal data** exist in the project, so pedal blur has never been tested for separating skill.
- **Pedal from audio** is not usable with current transcribers, and pedal detection from audio is not built.
- **Phone transcription noise** on home pianos is not measured; only competition recordings were checked.


### Shaping, phrasing and interpretation

This chapter covers the two upper tiers of the PianoLens feature set. Tier C, "shaping", asks whether a performance has musical shape of its own: whether loudness and timing follow the structure of the score, whether each phrase is given a curve in time, whether the melody is brought out, and whether the written dynamics are obeyed. Tier D, "interpretation", asks how a performance sits among expert performances of the same piece: where it follows what experts share, where it takes a personal path, and where it goes outside anything the experts do. The chapter also explains the phrase-boundary machinery that tier C depends on (a rule-based cadence detector and a blind Claude annotator), the analysis of repeated takes, and the neural expression models that are meant, eventually, to predict what the score "expects".

The experiment results are in Part 3. This chapter explains methods, parameters and reasoning, and refers to experiments by id (for example "see R-08a"); the appendix index says where each is discussed.

#### What do "shaping" and "interpretation" mean, and what does music psychology say about them?

Music psychology has long described expressive performance as layered. The research plan (`docs/plans/2026-09-27-research-program.md`, section 1.2) writes it as a hierarchy: a global layer (overall tempo, loudness level, legato habit, pedal density), a phrase layer (tempo arcs and loudness arcs, about 2 to 4 parameters per phrase), a beat and metre layer (accent patterns and small metric timing habits), a note layer (melody lead, voicing, chord spread) and a noise layer (unintended motor variation). Tier B of PianoLens reads the noise layer. Tier C reads the phrase and note layers. Tier D compares all of the smooth layers with experts.

Several findings from the literature shape the design. Each is cited in the landscape doc (`docs/research/2026-09-27-landscape.md`, sections 1.2 and 1.3) unless noted.

- **Timing follows grouping structure.** Repp (1992) measured inter-onset intervals (the time from one note's start to the next) in 28 recordings of Schumann's Träumerei. Global timing followed the grouping structure of the music, and the slowing at the end of a gesture followed a parabola "with a single degree of freedom". This is the basis for fitting a parabola to the tempo inside each phrase.
- **Phrase-final lengthening.** Performers slow down as a phrase approaches its end and then recover at the start of the next phrase. The code cites Repp 1992 and Todd 1992 for this. Todd 1992 is listed in the code as a method reference that is not in the landscape doc, so its specific claims were not checked in this repo. The general idea used here is only the shape: slower at the edges of a phrase, faster in the middle.
- **Experts share a few strategies and add personal variation.** Repp (1998) analysed bars 1 to 5 of 115 recordings of Chopin's Etude Op. 10 No. 3 and found "at least four independent timing strategies", with each pianist's timing a weighted mix of them plus idiosyncratic variation.
- **The average is good but not interesting.** Repp (1997) found that the average of several student performances of Träumerei was rated second-highest in quality and second-lowest in individuality, and that rated quality and individuality were negatively correlated. This is why tier D never scores a performance by its distance to the expert average: being close to the average is not the same as being good, and being far from it is not the same as being bad.
- **Individuality is deviation from many humans.** Wöllner (2013) measured individuality as deviation from the average of many performers, which is the frame tier D uses for its "individual part".
- **Melody lead is mostly a loudness effect.** Goebl (2001) found that the melody note of a chord tends to sound about 30 ms before the accompaniment, and that this is mostly because louder keys are struck faster. So PianoLens always reports melody lead next to the loudness difference.
- **Articulation is a ratio against the notated length.** Bresin and Battel (2000) describe legato and staccato by how long a key is held relative to the written value. Tier C measures articulation that way.
- **Timing scales with tempo.** Hu et al. (TISMIR 2026) show that expressive timing patterns scale with the local tempo, so timing features are expressed in fractions of a beat, not milliseconds.

The project's own measurements add one more fact that governs tier D (see R-02). Across 50 expert performances of each of 698 pieces, only about 3 to 5 components of tempo and loudness variation are clearly shared across performers (they rise above a strict surrogate null), and they carry about 35 to 46% of the between-performer variation. The remaining 55 to 65% cannot be told apart from smooth personal curves. Before any of this, the piece's mean curve already carries a median of 0.62 of each performance's own normalised variation. So an interpretation is best described as a small shared core plus a large space of personal freedom, and the tier D design follows from that.

#### Which parts of a performance are measured?

A piano note is fully described by when it starts, how hard it is struck (MIDI velocity, 0 to 127) and when the key is released, plus the pedals. Tier C turns these into four "channels", each a curve over the score.

- **Velocity** (`vel_midi`): the MIDI velocity of each matched note. It stands in for loudness. On MIDI transcribed from audio it is low confidence, because transcription adds about 9 velocity units of error and compresses the spread (DECISIONS, after D-10).
- **Timing** (`dev_beats`): how early or late each score position is played relative to the smooth tempo curve, in fractions of the local beat. This is the fine, note-to-note part of timing. Outlier positions are excluded.
- **Tempo** (`tempo_log_ratio`): the smooth tempo curve itself, as the natural log of the performance's own average beat period divided by the local beat period. Zero means "at this performance's own average tempo"; positive means faster. The smooth curve comes from the F-03 tempo model, a robust penalised spline whose smoothing has half gain at a period of 1.5 bars (DECISIONS, after F-03).
- **Articulation** (`art_log_ratio`): the natural log of the key-down duration divided by the notated duration at the local smooth tempo, clipped to plus or minus 3. Zero means the note was held exactly as long as written. Key-down durations are used, not durations extended by the sustain pedal, because partitura extends durations to the pedal release by default and that would confuse pedalling with touch (`.claude/rules/features.md`).

Log ratios are used for tempo and articulation because these are multiplicative quantities: playing twice as fast and half as fast should be equal and opposite. The split into a smooth tempo curve and a residual timing curve follows the rule "separate intent from noise": tier B reads the residual, tier C reads the smooth part. The split is a modelling choice. F-03 found that residuals correlate across performers (about 0.59), so part of the fine timing is shared and intended, which is why tier B subtracts an expert consensus before calling anything noise.

Only notes that the aligner labels a true `match` enter these channels. Interpolated, unmatched and grace notes are skipped and counted. When one score note is matched to two played notes (as in some ornaments), the first match is kept.

In the code: `src/pianolens/features/shaping.py` (`channel_data`, `_note_values`), `src/pianolens/features/tempo.py`.

#### How is the score described so that a model can read it?

To ask whether expression "follows the score", the score must be turned into numbers. PianoLens uses "basis functions" in the sense of the Basis Mixer (Grachten and Widmer 2012; Cancino-Chacón, Grachten and colleagues): numeric descriptors attached to each score note, such as its position in the bar, its pitch, its written duration and the markings that apply to it. Expression models of this family write velocity, timing and articulation as functions of these descriptors. PianoLens uses them the other way round: to measure how much of a real performer's expression they can account for.

The basis is computed from the performed score, which is the score unfolded along the repeat path the pianist actually took. Grace notes are dropped, because they have no metrical position. A score built from MIDI rather than MusicXML has no markings, so its marking columns are zero. The feature groups are:

| Group | What it describes | Notes on the design |
|---|---|---|
| metrical | How strong the beat is (1 on the downbeat, 0.75 on the secondary strong beat, 0.5 on other beats, 0.25 on half beats, 0 below), downbeat and offbeat flags, position in the bar as sine and cosine | Computed from bar lines and beat positions, because partitura's own metrical feature crashes with numpy 2. The sine and cosine pair avoids a jump at the bar line. A short first bar is treated as an upbeat and aligned to its end. |
| pitch | Pitch relative to the piece's median, whether the note is the top ("skyline") or bass note, rank in the chord, chord size, the melody's pitch, its step from the previous melody note, and whether it is a local peak | The skyline melody is the highest note starting at an onset that is not below a note still held from before. Without the "held note" rule an accompaniment note under a sustained melody note would be taken as the melody. |
| duration | log2 of the written duration and of the gaps to the next and previous onsets | Floored at 1/64 beat. |
| dynamics | The current dynamic level on an ordinal scale (ppp -3, pp -2, p -1, mp -0.5, mf 0.5, f 1, ff 2, fff 3; 0 before any marking), crescendo and diminuendo ramps, and sudden accents (sf, fz, fp and others) | A hairpin is a ramp from 0 at its start to 1 at its end. A "cresc." word with no end lasts until the next level marking, at most 4 bars. |
| articulation | Staccato, accent, tenuto, and slur ramps | ASAP MusicXML has no slurs. |
| tempo_marks | rit. and accel. ramps, and notes just after a hard tempo marking | |
| fermata | A note at a fermata, and notes just before one | |
| phrase | Position inside the phrase from -1 to 1 and its square (the parabolic arc), phrase start and end flags, and the strength of the boundary | Phrases come from outside (annotations or Claude) or from a crude proxy, explained below. |
| harmony | Tonal tension from the spiral array (Herremans and Chew 2016): how dissonant the local pitch cloud is, how far it is from the key, how fast the harmony moves, plus the share of pitch classes outside the key | A method reference, not in the landscape doc. |
| position | Position in the piece from 0 to 1 | Excluded from every coherence regression, because it is time, not structure. |

Two optional groups were added in F-05b and are off by default so older results do not change. The `phrase_detail` group describes the approach to a phrase end with exponential kernels that are 1 at the end and fade over 0.5, 1 or 2 bars, plus the recovery after a phrase end, the time since the phrase start, the log phrase length, and the phrase length times the arc (so longer phrases can have deeper arcs). The kernels encode phrase-final lengthening directly: they let a linear model put a slowing just before each end. The `cadence` group adds similar approach kernels for each cadence type when cadence labels exist.

When no phrase boundaries are supplied, a proxy guesses them. It scores each onset: 1.5 for a silence of at least half a beat before it, 1 or 1.5 for a long melody note (at least twice the local median melody gap and at least one beat; 1.5 at four times and two beats), 1 where one slur ends and another begins, 2 after a fermata, 1 at a double bar line or tempo marking, and 1 after a cadence-like bass move (down a fifth onto a strong beat, held at least a beat). Onsets scoring at least 1 become boundaries, strongest first, at least 2 bars apart. Any phrase longer than 8 bars is split evenly. The split exists so that "position in the phrase" never turns into a slow trend across a whole section. The proxy is weak: against expert phrase labels on the Batik Mozart set it reaches F1 0.34 at plus or minus 1 beat, fires about 1.75 times as often as a phrase actually starts, and at bar tolerance is no better than putting a boundary on every fourth downbeat (F1 0.51 against 0.50). On Schubert D.899/3 its long-note cue fires about every 2 bars. It is kept because it costs nothing and gives a usable default, and every downstream result says which boundary source it used.

In the code: `src/pianolens/features/score_basis.py` (`score_basis`, `BasisConfig`, `FEATURE_GROUPS`, `OPTIONAL_GROUPS`, `MARKING_GROUPS`).

#### How much of a pianist's expression follows the score?

"Structural coherence" is the share of a performer's own expressive variation that the score structure explains. The idea behind it is hypothesis H4: a musical performance is one whose loudness and timing are organised by the music (phrases, metre, harmony, melody), while an unmusical one varies in ways the score does not account for. It is measured per performance, per channel, as a cross-validated R²: how well a model trained on some bars of the performance predicts other bars of the same performance from the score basis alone. An R² near 0 or below means the score says nothing about the curve. Coherence is a description of the performance, not a quality score, and it has not been shown to track skill (see R-09).

**The model.** For each channel, a ridge regression (a linear regression with a penalty that shrinks the weights, which keeps it stable when features are many and correlated) predicts the channel from the standardised basis features. The penalty is `alpha` times the number of training rows, with `alpha` chosen from 13 values spaced evenly on a log scale from 0.0001 to 100. It is chosen by an inner cross-validation with 4 folds inside each of 5 outer folds, so the penalty is never tuned on the bars it is tested on. The score is `r2 = 1 - sum((y - y_oof)^2) / sum((y - mean y)^2)`, where `y_oof` are the out-of-fold predictions.

**Why out-of-fold.** A regression with dozens of features fits some of any curve in sample, including pure noise. Testing on held-out bars removes that inflation. The measure is conservative: on a synthetic smooth random walk with no structure, velocity R² comes out between -0.07 and -0.36, and on independent noise about -0.01 (feature-engineer notes).

**Leakage control.** Adjacent notes share smooth-curve values, and a repeated passage is nearly identical to its first playing, so naive random folds would let the model "predict" a bar from its own twin. Three rules prevent this.

- Folds are blocks of 4 written bars, using the bar numbers printed in the score. Both passes of a repeat carry the same written numbers, so they always fall in the same fold, and a repeat can never predict itself.
- Blocks are dealt to folds in turn (round robin), so every fold spans the whole piece.
- Training rows within 1 bar of a test block are dropped, so smooth curves cannot leak across the fold edge.

The value of the written-bar rule was measured on the Vienna 4x22 Mozart K.331 theme, whose MusicXML numbers bars in performed order. Before renumbering to written bars, the proxy's pooled tempo R² was 0.19; after, it was -0.27. The whole apparent effect was a repeat predicting itself.

**Clipping held-out features.** A sparse feature (for example one cadence type or one phrase length that occurs in a single block) can take a value in the test fold that is far outside anything seen in training. After standardisation this becomes a huge number, and the ridge extrapolates wildly. F-05b saw R² of -60 on a Vienna excerpt and about -70 in one variant. So each held-out feature is clipped to the range seen in its training rows before predicting. This became the default after F-05b; it moves typical results by at most 0.001 on average. One consequence: R-04's audited feature file was built before the change and reproduces only with clipping turned off (DECISIONS, after F-05d).

**Minimum length.** A coherence R² is defined only when the channel's rows cover at least 12 distinct written bars and at least 3 blocks, where the block count is the number of distinct written bars divided by 4, rounded up. Otherwise every R² is left undefined and the output says why (`too_few_rows` below 20 rows, `constant`, `too_few_bars`, `too_few_blocks`, or `cv_failed`). The first version counted blocks from the range of bar numbers. In R-09, 8-bar Czerny études numbered 0 to 8 spanned three number blocks, passed the old rule and produced velocity R² as low as -80. At the default block size the 12-bar rule is the binding one. Shorter segments (such as PercePiano's 8-bar clips) can be scored with 1-bar blocks and a lowered minimum, but that output is labelled "short-segment coherence" and is never used as the H4 measure.

**With and without markings.** `r2` uses every group; `r2_no_markings` drops the dynamics, articulation, tempo-mark and fermata groups. The reason is that a written "f" trivially explains loud playing. Obeying markings is part of shaping, but it is not the performer's own reading of structure, which is what H4 is about. The H4 primary measure is therefore the version without markings (DECISIONS, F-05 follow-ups).

**Which channels count.** The primary channels have changed as evidence came in.

- After F-05b: velocity and articulation are primary. Tempo coherence is secondary and only with validated phrase boundaries, the `phrase_detail` features and clipping on, because with proxy phrases it is near zero for reasons that have nothing to do with the performer.
- After R-09: on transcribed MIDI, articulation coherence is dropped, because transcription changes it by more than the whole effect of interest (median change 0.08, rank correlation 0.36 on Aria-AMT transcriptions). Timing-residual coherence survives transcription (median change 0.008, rank correlation 0.95) and carries H4 on transcribed data. Velocity is low confidence on transcribed MIDI in any case.

**Per bar and pooled views.** For each bar the code reports a local R² and the mean absolute residual, which says where the performer departs from the structure-predicted curve. Standardised ridge weights are reported for interpretation only. A pooled version fits one model to several performances of the same piece: each performance's curve is centred on its own mean (and optionally scaled), so the model learns shared score-driven shape rather than differences in overall level, and folds are shared written-bar blocks, so no bar is ever predicted from another pianist's playing of the same bar. It also reports each performance's R² under the shared model.

**What the numbers look like.** On Schubert D.899/3 (6 ASAP performances) mean R² was 0.41 for velocity (0.33 without markings), 0.12 for timing, 0.05 for smooth tempo and 0.20 for articulation. Pitch, dynamics and harmony features carried velocity; metrical features carried timing. Over 36 Batik Mozart movements without markings: velocity 0.376, timing 0.122, tempo 0.070, articulation 0.195. So the score explains roughly a third of loudness shaping and much less of timing, and very little of the smooth tempo curve under a single linear model. The next sections explain why tempo is the hard case.

**What is and is not validated.** Synthetic tests confirm the plumbing: a phrase-final ritardando over irregular phrases gives tempo R² 0.77 with the phrase-end features and 0.50 without, and the clipping test goes from below 0 unclipped to above 0.8 clipped. Whether coherence rises with skill is not established: R-09 found no effect within matched recording contexts, and the top skill levels in MAJEPPA are confounded with concert recording context. In R-04, coherence features had about zero importance for predicting expert ratings. In the practice report, coherence is shown for velocity and articulation only when at least 3 blocks exist, and tempo coherence is not shown at all.

In the code: `src/pianolens/features/shaping.py` (`structural_coherence`, `pooled_structural_coherence`, `_cv_ridge`, `_folds`, `_buffered_train`, `ShapingConfig`), `src/pianolens/features/extract.py` (short-segment override). Tickets: F-05, F-05b, F-05d; experiments R-04, R-09.

#### Why does tempo need real phrase boundaries?

Tempo coherence was near zero with the proxy phrases, and F-05b asked whether that was a boundary problem or a model problem. It used the Batik-plays-Mozart set: 36 movements played by one pianist on a sensor-equipped piano, with ground-truth alignments and expert phrase and cadence labels from the DCML annotation standard. In DCML, a phrase end is placed on the cadential arrival, the note where the cadence's final chord arrives, not on the last note of the phrase. The set holds 1,068 annotated phrase starts and 1,144 cadences over the performed scores.

The answer was "both". Tempo does follow the annotated phrases: 81% of annotated phrases have a concave tempo arc (slower at both edges), against 44% when the same boundaries are shifted by two bars. But feeding the annotated boundaries into the plain phrase features barely helped (tempo R² 0.070 to 0.090, not significant). Only annotated boundaries plus the phrase-end kernels doubled it, to 0.141 (paired test over movements, p 0.007), and the same features on shifted boundaries gave 0.074. On the Vienna K.331 theme with 22 pianists, pooled tempo R² went from -0.27 with the proxy to 0.42 with annotated phrases and phrase-end features. Two lessons followed. First, the gain comes from knowing exactly where phrases end, not from knowing the cadence type (adding DCML cadence types changed 0.143 to 0.141). Second, even the best within-movement tempo R² (0.14 with ridge, 0.24 with a boosted-tree model) stays far below velocity, and a model trained on other movements does not transfer at all (leave-movement-out R² about 0). How deep and how shaped each arc is varies from phrase to phrase, so one global linear map can only learn the average arc. That motivated a per-phrase measure that does not assume a shared shape, described below.

In the code: `scripts/check_phrase_f05b.py`; spec `docs/specs/phrase-coherence-validation.md` (F-05b section).

#### Can simple music-theory rules find where phrases end?

In Classical music a phrase usually closes with a cadence: a harmonic arrival, most often dominant to tonic (V to I) in the bass, or an arrival on the dominant for a half cadence, placed on a strong beat and followed by rhythmic closure such as a long note, a rest or a thinner texture. The cadence detector turns this textbook description into 21 measurable cues per score onset and a small logistic model that weighs them. It was built as the cheaper alternative to an LLM: if rules could find phrase ends well enough, no language model would be needed.

The cues are measured in quarter notes so they do not depend on the metre. "After" means the pitch classes sounding in the quarter note from the onset; "before" means the quarter note before it. A pitch class counts in a window if it holds at least 15% of the sounding note-time there.

| Cue | Meaning |
|---|---|
| bass_fifth_down, bass_step_up, bass_step_down, bass_same | The bass interval into the onset: down a fifth (V to I), up a step (into a half cadence), down a step, or the same note (as when a cadential six-four resolves over the same bass) |
| root_triad, major_triad | The arrival harmony is a root-position major or minor triad; major only |
| dominant_before, leading_tone_before, cad64_before | The window before holds the leading tone within a dominant-seventh collection; holds the leading tone at all; holds a six-four chord over the arrival bass |
| harmony_change | The F-04b harmony-change rule fires here |
| metrical_strength, is_downbeat | Metrical position |
| melody_long, ioi_next_log | The melody note and the next gap are long compared with the local median (log2, clipped to -2 to 3) |
| rest_after, density_drop | Longest silence in the next bar; fewer onsets in the bar after than before |
| stable_after | The arrival harmony is held for two quarter notes |
| melody_step_down, melody_on_root | The melody arrives by a descending step (as in scale degrees 2 to 1); the melody lands on the bass's pitch class |
| bass_tonic, bass_dominant | The bass is the tonic or dominant of the key signature's key |

The weights were fitted on 15 Batik movements (K.279 to K.283; 21,006 onsets, 397 annotated ends) and tested on the other 21. The largest weights are metrical strength (+3.2), bass on the dominant (+1.4), bass down a fifth (+1.2) and melody step down (+1.1). Some fitted weights run against intuition: a rest after the onset (-0.96), a root-position triad (-0.38) and a dominant before (-0.12) are negative. These cues overlap heavily with others (for example with stable_after and major_triad), so the signs are probably an artefact of correlated inputs rather than music theory; this was not investigated. The interval cue is an interval class, so "down a fifth" also fires on I to IV (up a fourth); the model leans on metrical strength and bass-on-dominant to tell them apart.

Ends are picked greedily: onsets with probability at least 0.2, highest first, at least 1.5 bars apart. A start follows each end: the first onset after the longest silence or gap within 2 bars after the arrival. The first onset of the piece is always a start. All four settings were chosen on the training movements.

On the 21 held-out movements, phrase-end F1 at plus or minus 1 beat was 0.46 (against 0.29 for the proxy's ends and 0.18 for a 4-bar grid), 0.59 at plus or minus 1 bar, and start F1 was 0.44. Recall of DCML cadences by type was 65% for perfect authentic cadences, 35% imperfect, 32% half cadences, 19% evaded and 0% deceptive. Half cadences are the main miss: an arrival on V has no V to I bass, and a deceptive cadence is by definition not V to I. On the Vienna K.331 theme in 6/8, the detector found 7 ends for 10 annotated: F1 0.82 at plus or minus a bar but 0.12 at plus or minus a beat, because one beat there is an eighth note.

This was not good enough. With detector boundaries and the phrase-end kernels, held-out tempo coherence (0.067) fell below the proxy's (0.097) and barely above its own shifted null (0.052), and on Vienna it fell to -0.40. Phrase-end kernels need ends placed to the beat; an end off by a beat puts a ritardando where there is none. The detector is kept as an opt-in boundary source and as the comparator every later phrase experiment had to beat. The weights are Mozart-specific (for example the bass-on-dominant cue) and were never refitted for other repertoire; on the Romantic pieces of R-08d the detector's mean end F1 was 0.389, and on BL-17's 24 Romantic character pieces 0.307.

In the code: `src/pianolens/features/cadence.py` (`cadence_candidates`, `cadence_phrase_ends`, `pick_ends`, `starts_from_ends`, `CadenceConfig`, `DEFAULT_WEIGHTS`); `BasisConfig(phrase_source="cadence")` in `score_basis.py`. Ticket: F-05c.

#### Can Claude read phrase structure from a score?

The project rule is that an LLM is never the judge of a performance (DECISIONS, 2026-09-27): it may analyse the score, once validated, and it may word feedback. Phrase analysis is exactly such a score task, and the gap left by the detector (especially half cadences) made it worth testing. The design problem was to measure what the model reads from the notes, not what it remembers about famous pieces or published analyses. The protocol was built up over four experiments, each closing a loophole the previous audit found.

**How the score is rendered as text.** Each movement becomes one plain-text file. A legend explains the format. Each performed bar is printed with its running number and its written number, and each onset line gives its beat position in the bar, the notes that start there in each staff (pitch name, octave and written duration in beats, tied notes merged), rests, fermatas, grace notes, the lowest sounding pitch ("bass", including held notes) and any markings at that point (dynamics, cresc. and dim., tempo and expression words). An upbeat bar is right-aligned as in the score. A bar that exactly repeats an earlier bar is printed as a pointer ("same notes and markings as bar k"), which keeps long movements readable; renderings ran from about 23,000 to 88,000 characters for the Mozart movements. Some things are left out on purpose:

- The MusicXML `<harmony>` elements, because in the Batik files they carry the DCML harmony, cadence and phrase labels themselves. Reading them would be label leakage.
- Slurs (Mozart's are articulation-level), beams, clefs and any recorded performance data.
- The title, catalogue number and any text that names the piece.

A leakage check fails the build if any rendering contains annotation vocabulary (PAC, cadence, phrase, braces), Roman-numeral chord labels, or any of the movement's own DCML label strings. It was shown to fire on planted cues.

**What the annotator is asked.** The instructions define a phrase as a unit that closes with a cadence (or rarely a clear arrival without one), and tell the annotator not to mark motives or sub-phrases. A `phrase_end` goes on the arrival of the cadence's final chord, not on the last note of the phrase, which is the DCML convention. A `phrase_start` includes any upbeat. An elision (one phrase's arrival is the next phrase's first note) gets both events at the same place. Each end gets a cadence type (PAC, IAC, HC, DC, EC or none), each defined in a sentence of standard theory. A separate `cadence` event type exists for cadences that do not end a phrase, because DCML places many cadences away from phrase ends (for example 0 of 23 deceptive cadences in the training movements sit on a phrase end). Each event carries a confidence. The annotator annotates only printed bars; events are copied to the pointer bars automatically.

**Blinding.** Each annotator is a fresh in-session Claude agent (`claude-opus-5-5`) that receives only a folder copied outside the repo, holding the instructions, the schema and one rendering. It is told not to read any other file, not to search the web, and to say whether it recognises the piece. One agent per movement keeps contexts independent. There is one pass, no feedback and no retry. Enforcement is by instruction, not by sandbox, so the auditor extracted every tool call from every transcript and checked that each annotator read only its three files and wrote only its output.

**Scoring.** Each event's bar and beat are mapped to a beat in the performed score, snapped to the nearest onset within half a beat, and copied into pointer bars. Predicted and true ends are matched one to one, closest pairs first, and F1 is computed at plus or minus 1 beat, where a beat is the time signature's lower number (an eighth note in 6/8, a half note in 2/2). The harness was checked by feeding the detector's own ends through the annotator path, which reproduced the detector's earlier scores exactly, and by feeding the DCML labels, which gave F1 1.

**The steps.** The go bar for using Claude's boundaries was set before any run: mean end F1 of at least 0.70 on the point estimate. With only 5 movements per test, a t-interval is reported next to the bootstrap because the bootstrap is too narrow with so few groups. The first four steps each used 5 movements; the fifth, BL-17, was sized to answer the question the fourth left open.

| Step | What it rules out | Design | Result (mean end F1, LLM vs detector) |
|---|---|---|---|
| R-08a pilot | Nothing yet | 5 held-out Batik Mozart movements, one drawn per stratum by seed | 0.817 vs 0.565; t-interval 0.696 to 0.938; 4 of 5 pieces named |
| R-08b disguise | Recall by naming the piece | The same movements transposed by a random 1 to 6 semitones up or down and respelled consistently along the circle of fifths, all words and dynamics removed, bar numbers offset by a random constant between 20 and 479, fresh ids; plus two undisguised reruns to measure run-to-run noise | Disguised 0.802, undisguised 0.789; 0 of 5 named; within-movement run spread (SD) 0.031 |
| R-08c unfamiliar repertoire | Familiarity with these particular pieces | 5 DCML-labelled J. C. Bach sonata movements, two runs each, no tempo words | 0.750 vs 0.437; t-interval 0.588 to 0.912; 0 of 10 named |
| R-08d Romantic repertoire | Style limited to the Classical period | One piece each by Tchaikovsky, Chopin, Schumann, Grieg and Liszt, simple metres, no period cue in the instructions | 0.737 vs 0.389; t-interval 0.439 to 1.036; per piece 0.325 to 0.938 |
| BL-17 larger Romantic test | A lucky draw of 5 pieces | 24 simple-metre character pieces drawn in proportion to the five Romantic corpora (10 Chopin mazurkas, 8 Grieg Lyric Pieces, 2 each of Tchaikovsky, Schumann and Liszt), all disguised as in R-08b, two blind runs each; plus 6 compound-metre pieces and an undisguised run on 8 | 0.635 vs 0.307; t-interval 0.549 to 0.720; per piece 0.138 to 0.917; 0 of 68 annotations named the right piece |

**The larger Romantic test.** R-08d's interval ran from 0.44 to 1.04, which could neither support nor reject the 0.70 bar. BL-17 was planned to settle that. Before any annotation existed, a simulation checked which outcomes were reachable with 24 pieces: "above 0.70" was likely only if the true mean was 0.80 or more, "below 0.70" if it was 0.60 or less, and near R-08d's 0.737 the most likely outcome was "inconclusive". Its verdict by the pre-registered rule is **inconclusive**: the t-interval [0.549, 0.720] contains 0.70, so "the mean is above 0.70" is not made, and the upper end is just too high for "below 0.70" to be shown. The interval was as narrow as planned (half-width 0.085), and the point estimate sits 0.065 below the bar; the weaker of the two runs per piece gives an interval wholly below it. The auditor confirmed every number and corrected four readings:

- R-08d's GO is not confirmed, but the two studies do not differ detectably either (R-08d minus BL-17 +0.103, interval -0.189 to +0.394, p 0.41). Sampling noise in R-08d's 5 pieces is enough to explain the gap on its own. Two other differences may add to it: R-08d took one piece per corpus, while BL-17 weights the corpora by size, so Chopin and Grieg make up 18 of its 24 pieces (weighting the corpora equally gives 0.687); and the disguise, whose cost on the 8 undisguised reruns was not shown (+0.032, interval -0.082 to +0.147). None of the three is separated from the others. BL-17's 0.635 is the better estimate for this pool.
- Both kinds of error are substantial. Recall is 0.71 to 0.73 and precision 0.59 to 0.63. Each run misses 88 of 314 expert phrase ends, and only 21 to 26 of those misses are within one bar of a predicted end, so about a quarter to a third of the misses are a one-bar difference over which onset counts as the arrival; the rest are real misses or a different phrase level. Extra, finer phrase ends are the larger error, but finer phrasing alone does not explain the score: DCML's own ends with every phrase split in half would score 0.667.
- Widening the tolerance to one bar gives 0.702, but its interval (0.625 to 0.778) also contains 0.70, and a mechanical 4-bar grid gains more from the wider window than Claude does (0.171 to 0.405). Adopting it now would be changing the metric after seeing the result.
- The disguise stopped Claude naming the right piece (0 of 68) but not naming the style: "Chopin" was guessed, always on Chopin movements, in 2 answers and 5 hand-back notes, and one answer paired it with "mazurka" on a transposed rendering with no markings.

Claude still beats the rule detector clearly on this repertoire, by +0.327 (interval +0.237 to +0.418), on 23 of 24 pieces. The 6 compound-metre pieces look similar (0.654, interval 0.460 to 0.849) but are too few to be more than descriptive, and include no 6/4 and no Chopin. Accuracy on a single piece varies widely: 5 of 24 pieces score below 0.50, three of them by Grieg.

The results and audits are also summarised in Part 3. Three points matter for how the boundaries may be used.

- **Where the errors come from.** Claude tends to segment more finely than DCML. On a J. C. Bach variation movement both runs marked 4-bar phrases where DCML marks 8- or 10-bar halves, and on the Liszt piece most extra ends were subdivisions of DCML's 16- to 31-bar phrases. That is a disagreement about phrase level, not a failure to hear phrase ends, and it is also evidence against recalling the labels (a recaller would copy DCML's level). The Liszt piece also has two real placement misses, 4 to 6 bars away, in both runs. On Romantic music the cadence-based phrase definition costs recall on phrase ends that DCML marks without a cadence.
- **What is licensed.** Classical and galant sonata-type movements in simple metres, including unrecognised pieces. On Romantic character pieces the boundaries are the best source available, clearly better than the rule detector, but their accuracy (about 0.64, plausibly 0.55 to 0.72) is below the project's 0.70 bar as a point estimate, and single pieces range from 0.14 to 0.92, so any use must disclose that. Not licensed: compound metres, nocturnes and waltzes (never tested), long Chopin forms, per-composer claims, other models or prompts, and renderings made from transcribed performance MIDI rather than a score.
- **What cannot be excluded.** The DCML labels were published before the model's training cutoff, so exposure to them cannot be ruled out by any of these designs. Recognition is self-reported, and thinking is not visible in the transcripts, so silent recognition is also not excluded. Only phrase labels made after the cutoff would close this.

In the code: the renderer, scorer and instructions live in the experiment folders (`experiments/2026-09-28-R-08a-llm-phrase-pilot/` with `common.py`, `render.py`, `score.py`, `blind_input/INSTRUCTIONS.md`; R-08b to R-08d and `experiments/2026-09-29-BL-17-romantic-llm/` import them unchanged). The product's LLM phrase source is `src/pianolens/features/phrases_llm.py` (a per-piece cache with its provenance), built by `scripts/build_llm_phrases.py` with the R-08d protocol and read through `BasisConfig(phrase_source="llm")` (DF-02).

#### Does the pianist shape each phrase in time?

Structural coherence asks one linear model to explain every phrase, so it can only learn the average arc. The per-phrase tempo measure asks a looser question: whatever the depth and shape of each phrase, is the tempo inside it slower at both edges than in the middle? This is the phrase-final lengthening pattern, measured phrase by phrase.

**How it works.** For each phrase, a parabola `tempo_log_ratio = c0 + c1*u + c2*u^2` is fitted to the smooth log tempo on the integer-beat grid, where `u` runs from -1 at the phrase start to 1 at its end. A negative `c2` means the arc is concave: slower at both edges. `c1` absorbs any tilt, such as a phrase that speeds up throughout. `-c2` is the depth of the arc. Phrases with fewer than 3 grid beats are not fitted. The summary measures are:

- `concave_share`: the share of fitted phrases with `c2 < 0`.
- `arc_r2_within`: the pooled within-phrase fit, `1 - sum_i (1 - r2_i) SS_i / sum_i SS_i`, where `SS_i` is phrase i's tempo variation about its own mean. It is in-sample, so it grows with the number of phrases.
- `between_share`: the share of tempo variation that lies between phrase means rather than inside phrases.

**Why a null is essential.** A raw concave share is not interpretable on its own: random boundaries already give about 0.50 to 0.53, and a smooth curve cut into more pieces fits parabolas better. So every measure is compared with a "shifted-boundary null": the same boundaries moved circularly by -2 and +2 bars (same number and spacing of phrases, wrong places), averaged. The reported quantities are `concave_excess` and `arc_r2_excess`, observed minus null. They answer "do the arcs line up with these particular boundaries?" and are comparable across performances, though not across boundary sources.

**What it shows.** On Batik, annotated phrases gave a concave share of 0.813 against 0.453 for the null, an excess of +0.360 over all 36 movements and +0.418 on the 21 held-out movements (positive in 21 of 21). On the Vienna theme with 22 pianists the excess was +0.734. The measure works with imperfect boundaries: on held-out Batik the cadence detector gave +0.207 and the proxy +0.243, while a 4-bar grid gave -0.009. That tolerance is why it, rather than tempo coherence, became the secondary tempo channel for H4 (DECISIONS, after D-11 and F-05c).

**Feeding it Claude's boundaries.** F-05e tested whether Claude's phrase starts recover the value obtained with DCML starts, on the 8 movements that have both blind annotations and aligned performances (5 Batik movements, and 3 Romantic pieces with 18 to 30 transcribed PianoCoRe performances each). The pre-registered rule counted a loss of up to 0.10 as recovered, because that keeps more than half of the annotation's advantage over the detector. The mean paired difference (Claude minus DCML) was -0.055, recovered by the rule, and Claude beat the detector on all 8 (+0.221). On Batik it matched DCML (-0.014). On the 3 Romantic pieces it lost 0.124, and the auditor showed that this is a placement loss: it is worse than DCML plus random extra boundaries at Claude's density. See F-05e.

The audit also settled how the measure treats boundary density, which matters because Claude over-segments.

| Boundary set (mean of 8 units) | concave_excess |
|---|---|
| DCML | 0.473 |
| Claude | 0.418 |
| Random onsets at Claude's density | -0.032 |
| Random downbeats at Claude's density | +0.006 |
| DCML with every phrase halved | 0.140 |
| DCML plus random extras up to Claude's count | 0.409 |
| DCML starts each moved to a random onset within 2 bars | 0.096 |

Density alone does not inflate the measure. Finer segmentation is penalised: halving every DCML phrase costs about a third, because half of a concave arc keeps its curvature sign (so the raw share stays high) but a 2-bar shift of 2-bar phrases lands on true boundaries, which raises the null. So `concave_excess` depends on the phrase level, and "recovered" means "recovers the DCML-level signal". The phrase-count ratio must be reported next to it.

**Merging short phrases did not help.** Because the R-08d audit warned about over-segmentation, `merge_short_phrases` was written and tested. While more than one phrase remains and some phrase is shorter than the minimum, it takes the shortest phrase (earliest on ties) and merges it with its shorter neighbour (the following one on ties) by deleting the boundary between them; the first phrase can only merge forward and the last only backward. Merging to 4 bars left Batik unchanged (+0.011) but lowered the Romantic mean by 0.111; merging to 8 bars destroyed the signal (-0.265 against DCML). An "oracle" grouping that keeps, for each DCML start, the nearest Claude start within a bar recovered DCML almost exactly (-0.009), which shows that the loss comes from where the extra and missing boundaries fall, which no length rule can find. The merge stays available but off by default, and Claude's boundaries are used raw. The piece it was designed for (the over-segmented Liszt, about 2.7 times DCML's phrase count) has no aligned performances, so that case is untested.

**Where it is used.** DECISIONS (after F-05e) makes Claude's phrase starts the boundary source for the H4 and R-09 secondary tempo channel, with Romantic values disclosed as not recovering the DCML signal. The practice report now uses Claude's boundaries too, for pieces that have a cached set, and falls back to the cadence detector otherwise (DF-02; the report chapter explains what it discloses). Only the owner's five pieces have a cache so far, and on them the source matters: one take's value goes from about -0.29 with detector boundaries to +0.31 with Claude's, and the two blind runs differ by up to 0.26.

In the code: `src/pianolens/features/shaping.py` (`phrase_tempo_shaping`, `_arc_table`, `_shift_bounds`, `merge_short_phrases`), `src/pianolens/features/tempo.py` (`phrase_arcs`), `src/pianolens/report/build.py` (`_shaping_section`). Tickets: F-05c, F-05e.

#### Is a repeated passage played the same way?

When music repeats, a performer may shape the repeat the same way (consistency) or vary it on purpose (a softer second time is a classic choice). Tier C reports how similar the two playings are, channel by channel, without judging which is better.

Two bars count as identical when they have the same set of (beat in bar, pitch, notated duration) and at least 4 notes. Maximal runs of consecutive identical bars that do not overlap are repetitions; this catches both repeat signs unfolded by the aligner and written-out repeats. Longest runs are taken first and each bar pair is used once. Within a run, notes at the same position in the bar and the same pitch are paired, and each channel is compared with four numbers:

- Pearson r, which measures whether the shape is the same regardless of level or size;
- Lin's concordance correlation, which is 1 only if the two playings are identical, level and scale included (a method reference, not in the landscape doc);
- the mean difference (repeat minus first), which catches "softer the second time";
- the root-mean-square difference.

The summary averages r across runs with Fisher z weights of n minus 3 (the standard way to average correlations, giving larger runs more weight) and also pools all pairs after centring each run. On Schubert D.899/3 (14 runs), the mean r was 0.77 for velocity, 0.87 for timing, 0.72 for tempo and 0.86 for articulation.

This measure is descriptive only. There is no null for how consistent a repeat "should" be, no link to listener judgments, and it is not shown in the practice report. The exact-content rule misses varied or transposed repeats, and sequences.

In the code: `src/pianolens/features/shaping.py` (`repeated_material`, `_bar_fingerprints`, `_repeat_runs`).

#### Does the melody sing above the accompaniment?

Voicing, bringing out one line by playing it louder than the rest, is one of the most taught piano skills. At every score onset where the melody note and at least one lower note are both matched, tier C reports the melody's velocity minus the mean velocity of the other notes, and the melody lead: the mean onset of the other notes minus the melody onset, in milliseconds (positive means the melody sounds first) and in fractions of the local beat. Following Goebl (2001), lead is always reported with the velocity difference, and their correlation is reported too, because a melody that is struck harder will sound earlier for mechanical reasons.

The melody is the skyline (the highest starting note not below a held note) unless melody notes are supplied. On D.899/3 the melody was about 20 velocity units louder (18.8 to 22.3 across performances) and louder at 98.7% of onsets, while the mean lead was -12 ms (range -39 to 24), so the melody did not systematically sound first in that piece.

The limits are plain. An inner-voice or bass melody is invisible to the skyline rule. On transcribed MIDI the velocity difference is low confidence. No threshold separates good from poor voicing; the numbers are descriptive.

In the code: `src/pianolens/features/shaping.py` (`voicing`).

#### Does the playing follow the written dynamics?

This checks obedience to dynamic markings, which the H4 measure deliberately leaves out. Loudness at an onset is taken as the maximum velocity of its matched notes, because the loudest note dominates what is heard and a mean would jump whenever the texture changes (for example when a melody note joins the accompaniment). Three kinds of marking are checked.

- **Hairpins and cresc. or dim. words.** A robust slope (Theil-Sen, the median of all pairwise slopes, so a single loud note cannot tip it) of onset loudness against score beat over the marking's span, times the span length, gives the change in velocity. It agrees if its sign matches the marking. At least 3 onsets are needed.
- **Changes of dynamic level** (p to f and so on). Mean loudness in up to 2 bars after the new marking minus up to 2 bars before, not crossing the previous or next marking. It agrees if the sign matches, and the change is also divided by the size of the step on the ordinal scale.
- **Accents** (sf, fz and accent marks). The marked note's velocity minus the median velocity of unmarked notes within one beat.

A rank correlation between the marked level and onset loudness summarises the whole piece. On D.899/3 hairpins agreed 61% of the time, level changes 63%, accents 76%, and the level-to-velocity rank correlation was 0.23. In ASAP MusicXML, "cresc." and "dim." words often have no end, so their extent is taken as "until the next level marking, at most 4 bars", which is a guess.

MIDI velocity is not perceived loudness (register, pedal and the instrument all intervene), levels are relative to each other rather than absolute, and on transcribed input velocity is low confidence. The measure has not been checked against listeners.

In the code: `src/pianolens/features/shaping.py` (`dynamic_compliance`), `src/pianolens/features/score_basis.py` (`DYNAMIC_LEVELS`, dynamics events).

#### How does one performance compare with hundreds of experts?

Tier D places a performance among expert performances of the same piece. The design is fixed by the R-02 result and by Repp (1997). There is no single "right" curve: the average performance is rated high on quality but low on individuality, and most of the variation between experts is personal. So tier D separates three things. The expert band says what range experts cover at each bar. The shared core says which few directions of variation experts have in common, and where this performance sits along them. The individual part is everything outside the shared core, treated as legitimate freedom, not error.

**The reference set.** References are PianoCoRe tier A performances of the same piece (mostly transcribed from audio), loaded from the R-02 curve cache, plus any Disklavier or ASAP performances. At most 500 transcribed references are used (a seeded random subsample, for speed); sensor references are always kept. A reference with the target's own performance or source id is removed first (leave-one-out), so a reference scored as a target is never compared with itself. For velocity, only Disklavier or sensor references are used when at least 8 exist; otherwise all references are used and velocity is marked low confidence. A transcribed target is always low confidence for velocity.

**Putting two scores on one grid.** The target's performed score and the reference score may unfold repeats differently or place an upbeat differently. `map_score_beats` finds a piecewise-constant beat offset: candidate offsets are the most common reference-minus-source beat differences over notes of the same pitch, and a Viterbi pass (a dynamic-programming search for the best sequence of states) picks one offset or "unmapped" per onset, rewarding the share of the onset's pitches found at the shifted beat minus 0.5 and charging 3 per change of offset. The comparison frame is the target's own beats, so a repeat the target played twice is compared twice with the same reference bars. Equal grid lengths do not imply equal content (one Chopin piece had equal grids but a 32-beat gap), so mapping is always run when both scores are known.

**The curves.** Tempo is the smooth log tempo ratio, computed with no score markings, which is the convention of the R-02 cache, so targets and references are measured the same way. Velocity is the per-beat mean velocity, interpolated over beats with no onset and smoothed with a Whittaker smoother (a penalised smoother) with half gain at 1.5 bars, the same period as the tempo curve. Residual timing is used only for agreement features, not decomposed, because R-02 found it the highest-dimensional channel and the closest to its null.

**The expert band.** At each beat the band is the 10th, 50th and 90th percentile of the references, after each reference curve is centred on its own mean. The target is shifted so that the median of its difference from the reference mean is zero. The median is used because a mean would let one anomalous bar shift the whole curve and make other bars look off-band. The band is also given in absolute units (beats per minute and MIDI velocity) for display. At least 10 references must be observed at a point for the band to exist.

##### What is shared among experts, and what is personal?

The decomposition runs in non-overlapping windows of 16 bars (a last window shorter than 8 bars is merged into the previous one), separately for tempo and velocity. Windows are used because R-02 found that a whole-piece count grows with length, and because the plan's phrase layer predicts a few parameters per phrase group. There is no joint tempo-plus-velocity decomposition, because the reference sets differ by channel (DECISIONS, after F-06).

Inside a window, beats unobserved in more than 10% of references are dropped, then references unobserved on more than 10% of the remaining beats are dropped (the R-02 quality rules). At least 8 beats and 10 references must remain.

The number of shared components comes from parallel analysis: a component counts if its eigenvalue (the variance it carries) exceeds the 95th percentile of the same eigenvalue in 40 surrogate data sets, and all earlier components did too (Horn 1965, adapted). The surrogates are "envelope" surrogates: each reference curve's Fourier phases are randomised, which keeps its smoothness but destroys any alignment across performers, and then each beat is rescaled to the real spread at that beat. Keeping the per-beat spread matters. The R-02 audit showed that plain phase randomisation also removes the fact that experts differ more at some places than others, which alone makes real data look structured, so "beats the phase null" was close to guaranteed. Because parallel-analysis counts grow with the number of references, the count is taken as the median (rounded down) over 5 random subsamples of 50 references, capped at 10.

Parallel analysis in this form undercounts when several strong components cover the window: on synthetic data it recovers 1 to 3 components correctly but returns 1 to 2 when there are really 4 or 5. A "sequential" variant that tests each component against a null built from the residual (after Green et al. 2012) recovered the synthetic counts on 95 of 96 runs, but on real curves its count for a window moved by 6 to 7 between subsamples of 50, so it is kept for research only. With the default, a 16-bar window typically gets 1 to 2 shared components per channel. This is deliberately a different number from the 3 to 5 whole-piece components that H1b uses, and neither is substituted for the other (DECISIONS, after F-06). The report does not depend on the exact count.

With `k` components found, the target's deviation from the reference mean is projected onto them. The projection is the target's position in the shared space (`target_z`) and its reconstruction is the "shared" part; the remainder is the "individual" part, and `individual_share` is its fraction of the target's squared deviation.

##### How is typicality scored, and how is flat playing caught?

Typicality is the likelihood of the target's shared coordinates under a Gaussian fitted to the references, not a distance to the mean, because of Repp (1997). The Gaussian also includes one more coordinate: the log of the curve's overall size (its standard deviation in the window, plus a floor of 1% of the references' median). This makes typicality two-sided in expressiveness. A deadpan performance sits near the centre of the shared space, so without this coordinate it would be the most "typical" performance of all, which is exactly the failure R-06 found in neural likelihoods (below). With it, a flat curve has a log size far below every expert's and a low likelihood.

The covariance is estimated with Ledoit-Wolf shrinkage (a method that pulls a noisy covariance estimate towards a simpler target so it stays well-behaved with few samples). It is applied to the correlation matrix and then rescaled. Applying it to the raw covariance was a real bug: the coordinates have very different scales (velocity units against log size), shrinkage towards a scaled identity inflated the small-scale variance, and a velocity curve flattened to 25% of its size scored typicality 0.72.

`typicality_pct` is the share of references whose likelihood is at or below the target's, with the references scored out-of-fold (10-fold cross-fitting, so no reference is scored by a model that saw it) and a +1 correction. Small means atypical. Its floor is 1 divided by the number of references plus 1, so with about 20 sensor velocity references it cannot go below about 0.05. That is why a separate size check exists: `too_flat` and `too_extreme` fire when the target's size is below or above the chosen quantile of the references' sizes.

**Per-bar flags.** For each bar, the root-mean-square of the target's deviation is compared with the same quantity for the references, computed out-of-fold. A bar is out of band if the target exceeds the chosen quantile of the references, which reads as "outside the range that 95% of held-out experts stay within at this bar". A flag on the shared part alone is computed but only informational, because a global projection smears a local anomaly across the window.

**Tiers in the practice report.** The report runs the analysis twice, at the 95th and 99th percentiles. Beyond the 95th is "notable" ("outside the usual expert range"), beyond the 99th is "strong" ("well outside the expert range"); about 5% and 1% of genuine expert bars reach them, and only "strong" is highlighted. The too-flat check uses the same two tiers. At least 10 references are needed before any tier-D tiering. Low-confidence velocity issues are shown but never enter "what to practise".

**Agreement features.** Separately from the decomposition, tier D reports how well the target's curve correlates with the reference mean, the root-mean-square difference, where that difference ranks among the references (each scored against the mean of the others), and the difference to the nearest single reference. These came from R-04, where they added a little predictive value for expert ratings.

**Validation.** There are 26 known-answer tests. On Chopin Op. 10 No. 3 with PianoCoRe references scored leave-one-out (40 targets, 5 windows each), typicality fell below 0.05 in 6.0% of tempo windows and 6.5% of velocity windows, and bars were flagged at 5.2% and 6.1%, close to the nominal 5%. A deadpan scored tempo typicality at most 0.004 and was flagged too flat every time; deadpan plus noise stayed at or below 0.036. An ASAP performance aligned from scratch reproduced its PianoCoRe row exactly. F-08b showed that Disklavier targets are not over-flagged against transcribed references. A known weakness: a performance flattened to 50% of its size was not flagged (typicality 0.23).

In the code: `src/pianolens/features/interpretation.py` (`interpret`, `shared_core`, `parallel_analysis`, `envelope_surrogate`, `SharedCore`, `map_score_beats`, `InterpretationConfig`), `src/pianolens/report/build.py` (`_interpretation_section`, `_tier`), `src/pianolens/report/calibration.py`. Tickets: R-02, F-06, F-08, F-08b.

#### What do repeated takes of the same passage reveal?

The plan's hypothesis H5 was that playing a passage more than once separates intent from noise: what a pianist repeats is intended, and what changes from take to take is noise. PianoLens can analyse any set of takes of the same passage by the same player, and the results changed how the product uses them.

**How takes are decomposed.** Takes may unfold repeats differently, so observations are matched across takes by score-note identity (score positions by the smallest note id starting there), and only observations present in every take are used. Each take is centred on its own mean, with the overall level differences reported separately. The take-consistent part is the mean over takes at each observation; the take-specific part is each take's departure from it. Variance components come from a two-way analysis of variance of observations by takes (McGraw and Wong 1996). From them come the variance of the repeated curve, the variance of one take around it, and the intraclass correlation ICC(3,1), which is the share of one take's variation that the player repeats. The reliability of the k-take mean follows from the Spearman-Brown formula. The confidence interval for the ICC assumes independent observations, which smooth channels such as tempo badly violate, so there it is far too narrow.

**Why a balanced contrast.** The obvious test, regressing the per-take departures on score features, gives R² of zero or below by construction, because the departures sum to zero across takes and every take shares the same features. And comparing the k-take mean with single-take departures is unbalanced for k above 2, because the mean averages away noise. So H5 was tested per pair of takes: the half-sum and the half-difference of two exchangeable takes carry the same noise variance, so only structure can make their out-of-fold R² differ. The R² is the structural coherence machinery above, with the same written-bar folds and the same minimum-length rule.

**What F-07 found, and the twist.** On 1,390 same-pianist groups of transcribed concert recordings (after removing duplicate recordings of the same performance), the half-sum's timing R² was 0.123 and the half-difference's 0.005, so H5 passed its pre-registered test. But the auditor's cross-pianist control showed that two takes by different pianists pass the same test (0.097 against 0.121 for the same pianist). The repeated part is timing that any two performances of the piece share, not personal intent; once a single take has any structure, the test was nearly bound to pass. What survived is narrower: a pianist's own take-to-take change is less structured by the score (0.011) than the difference between two pianists (0.049). See F-07. The lesson is now a rule: any "shared part versus difference part" contrast needs a cross-unit control.

**Practice takes.** BL-16 asked the same question of practice sessions from the Rach3 set (three pianists playing Hanon exercises, cut automatically into takes). Within one sitting, advanced players' take-to-take timing changes were close to unstructured, with a spread of about 0.011 beats (7.5 ms); the beginner, who never repeated an exercise within a day, was measured on next-day pairs at about 0.013 beats (11 ms). Takes from different days carry structured drift, so they are not noise. The auditor also showed that a same-pianist pair from another day is nearly as structured as a cross-pianist pair, so the advanced result shows "same sitting is less structured than across days", not a pianist effect. See BL-16.

**How this is used.** Tier B estimates timing noise from same-sitting takes only, never pooled across days (DECISIONS, after BL-16), and Henry is asked to record 2 to 3 takes in one sitting. Tier B and D must not label the take-consistent part as "intent". In the report, a wrong pitch at the same score note in 2 or more takes, which no expert recording shows, is promoted to a "strong" correctness item, because an error that recurs is a learned mistake rather than a slip (narrowed after F-08b, where a broader rule would have marked 24 to 31% of expert bars strong).

In the code: `src/pianolens/features/takes.py` (`decompose_takes`, `variance_components`, `take_structure`, `TakesConfig`), `src/pianolens/report/build.py` (`_takes_section`, `recurring_errors`). Tickets: F-07, BL-16, F-08b.

#### Can a neural model say what the score "expects"?

Tier D compares a performance with real experts, which needs many recordings of the same piece. A score-conditioned expression model could supply an "expected expression" for any score, including pieces nobody has recorded, and could test H1b: that the shared part of expert expression is predictable from the score. H1b, added after R-02, says a score-conditioned model should explain at least 50% of the held-out variance in the 3 to 5 shared components on unseen pieces, and is falsified at 20% or less.

Two models with released weights were shortlisted: SyMuPe EncDec-base (25.1 million parameters, weights under a non-commercial licence, trained on the PERiScoPe score-performance pairs) and Pianist Transformer (135.7 million parameters, Apache-2.0, pretrained on about 10 billion MIDI tokens and fine-tuned on ASAP). R-06 compared them frozen, on PercePiano passages that neither had seen paired with a score. They tied on per-note prediction (composite correlation 0.388 against 0.393, both far above a ridge baseline at 0.166 but below the 0.720 reached by averaging the other performers of the same passage). SyMuPe won the pre-registered tie-break by a tiny margin and was chosen; Pianist Transformer is kept as a documented secondary arm for its licence and better articulation. On the across-performer mean curve, the frozen models explained at most about 30% of velocity and nothing of timing (negative centred R²), although the shape was partly right. Their large lead on pieces they had seen in training vanished on unseen pieces, which is a warning about memorisation. See R-06.

The shared plumbing lives in `src/pianolens/models/`. `expression_io` turns an aligned performance into matched score and performance notes (deletions, insertions and interpolated pairs dropped), computes the one global tempo and one velocity a rendition is conditioned on (the least-squares slope of chord onset time on score time, and the median velocity), computes the per-note targets used everywhere (velocity, log inter-onset ratio per score onset, log articulation) identically for real, perturbed, deadpan and generated renditions, and renders deadpans. `expression_data` builds the perturbation battery and the flat training renditions. `expression_split` builds work-level splits.

In the code: `src/pianolens/models/expression_io.py`, `expression_data.py`, `expression_split.py`; `experiments/2026-09-27-R-06-expression-model-h2h/`.

#### Why can a model's likelihood never be used as a quality score?

A generative model assigns each performance a probability. It is tempting to read a high probability as "typical expert playing" and a low one as "unusual". R-06 showed this fails completely. Scored by teacher forcing (the model predicts each note given the true previous notes), both models gave every deadpan rendition a higher likelihood than the real expert performance of the same passage, an AUC of 0.00 for both synthetic deadpans and PercePiano's own mechanical "Score" renditions. They did detect added jitter well (AUC at least 0.94).

The auditor then tried to break the finding and could not. The deadpan still won with its velocity 12 units above or below the conditioning velocity, when played 15% slower, and field by field (timing, velocity, duration and pedal each gave AUC 0.00 to 0.08). A deadpan with random noise added still beat the human 91 to 92% of the time. Half-deadpans (human velocities with flat timing, or human timing with constant velocity) also won. Two simple baselines, a ridge model used as a Gaussian likelihood and a smoothness rule, fail the same way. A generation-based alternative (distance to the mean of 8 model samples) also preferred the synthetic deadpan, with its whole confidence interval below 0.5.

The reason is general, not a quirk of these models. In a high-dimensional distribution, the single most probable outcome (the mode) is not a typical outcome; typical outcomes are less probable one by one but vastly more numerous. A flat performance is the most predictable continuation at every note, especially once the model has seen a few flat notes, so any flattening of any dimension raises the likelihood. Real expression is by nature a departure from the most predictable path.

Two design rules follow (DECISIONS, after R-06). Raw likelihood is never used as a typicality or quality score. Any typicality score must be two-sided, penalising too little expression as well as too much, and must pass a battery of deadpan variants before use. Tier D's log-size coordinate and too-flat flag are the non-neural answer to the same problem.

In the code: `src/pianolens/models/expression_data.py` (`VARIANTS`, `item_variants`). Experiment R-06.

#### How will the fine-tuned model be tested?

R-07 is a pre-registered GPU job that fine-tunes SyMuPe on PianoCoRe with whole works held out, and tests whether a corrected typicality score can survive the deadpan battery. It ran on Henry's RTX 5080 from 2026-09-29 to 2026-10-05 and was audited on 2026-10-05; the results are in "What R-07 found" below.

**The split.** The unit is the work: all movements of a sonata, a prelude with its fugue, and every dataset id of the same piece go to one side. Pieces whose composer and catalogue numbers might alias a held-out piece under another id are quarantined (81 ids) and used for nothing. The test side (257 piece ids in 129 works) holds the R-06 sets plus two sets for H1b: R10u, the 76 R-02 pieces with no score-paired PERiScoPe performance (unseen by SyMuPe's pretraining and by fine-tuning), and R10s, R-02 pieces that were seen in pretraining (an exposure contrast). Validation takes 5% of remaining works and is used only for early stopping. Leakage is checked twice, when items are built and again before tokenising, and the job fails on any violation. The split file is committed and frozen.

**The models.** E is SyMuPe fine-tuned with its own loss on windows of 256 notes: AdamW, learning rate 0.0001, 500 warm-up steps, cosine decay to 10%, 64 windows per step, bf16 precision, at most 30,000 steps (about 7 passes over the roughly 66 million training notes), validation every 1,000 steps, early stopping after 5 evaluations without a 0.1% improvement. The best checkpoint may be step 0, the pretrained weights. F is the same model fine-tuned for at most 5,000 steps on flat renditions (score timing at the item's own tempo, constant velocity, durations 0.85 to 1.0 of nominal, onset noise up to 10 ms and velocity noise up to 4, no pedal). F's family is deliberately narrower than the test battery, so the battery tests generalisation, not memorisation. A secondary arm fine-tunes Pianist Transformer with its own recipe. No other hyperparameter is tuned; a single restart at half the learning rate is allowed if training diverges early, and must be disclosed.

**The decision rules.** On PercePiano (the primary set), per-note prediction is compared with the frozen model, rendition by rendition, and read as improves, harms or no detectable change from a two-way bootstrap over passages and performers. The fine-tuned model replaces the frozen one downstream only if it does not harm and its validation loss beats step 0. A reproduction gate requires the frozen model re-run through this pipeline to land within 0.01 of R-06's 0.388. The H1b preview measures, on R10u pieces with at least 20 renditions, the share of the experts' shared-component variance that lies in the span of 16 model samples, against a random subspace of the same size, with the plan's 50% and 20% thresholds.

**The typicality candidates.** Four scores are tested.

- S-RAW, the raw likelihood, as the known failure.
- S-LR, a likelihood ratio: the fine-tuned model's likelihood minus the flat model's. It asks "how much more expert-like than flat-like is this?"
- S-TYP, a typical-set distance: for each field, how far the performance's likelihood is from the likelihoods of 16 samples drawn from the model under the same conditioning, in standard units, combined as a root mean square. A performance more predictable than the model's own samples is as atypical as a less predictable one.
- S-DEV, deviation-only agreement: the correlation of the performance with the model's sample mean, with a flat target scoring 0. It scores shape only, so it cannot penalise exaggeration.

A score passes only if it prefers the real performance to each of seven deadpan variants (exact, velocity plus and minus 12, 15% slower, deadpan plus small noise, and the two half-deadpans) with AUC at least 0.75, the whole interval above 0.5, and at least 0.5 in each of the 3 works; still detects added jitter (timing noise of 20 and 40 ms, velocity noise of 8 and 16) at the same standard; and replicates on the Vienna set. A score that catches flatness but not jitter may only feed the too-flat flag. Anything else is not used anywhere, and a new candidate needs a new pre-registration.

**What R-07 found** (Confirmed with caveats, 2026-10-05).

- **Fine-tuning did not help.** On PercePiano the fine-tuned SyMuPe predicted each note's expression worse than the frozen model (paired difference -0.051, interval -0.072 to -0.029), and it was also worse on the Vienna and (n)ASAP sets. Its one gain, on held-out PianoCoRe pieces, sat entirely in recordings transcribed by Aria-AMT, which made up 77% of its training data. The likely reading is that it learned the habits of that corpus, not more about expert expression; transcriber and source cannot be separated here. So R-10 uses the frozen model. Fine-tuning Pianist Transformer did help on held-out PianoCoRe pieces, but it stays a secondary arm.
- **The re-run frozen model landed 0.0105 above R-06** (0.3987 against 0.3882), just outside the 0.01 gate. The comparison used the re-run numbers, as registered.
- **The likelihood ratio S-LR passed the battery, but the battery was too easy.** Every deadpan variant has one field exactly where the flat model is most confident, so S-LR separates them perfectly almost by construction, and the model-free "amount of expression" baseline does too. S-LR cannot tell a real performance from the same performance with half its expression (AUC 0.491). It is not used anywhere until it survives non-flat wrong expression. S-DEV is a flatness detector only; S-TYP fails. The report's too-flat check stays model-free.
- **The H1b preview turned out to be uninformative.** The registered statistic asked how much of the experts' shared variation the spread of 16 model samples covers. The models reached about 0.10-0.12. The audit then put 16 real held-out experts in the model's place: they reach only about 0.25. A 0.50 bar was out of reach for real pianists, so the preview cannot falsify H1b. It measures how varied the samples are, not what the model predicts. The better-matched measure, how well the model's average curve matches the experts' average curve (centred R²), has a reachable ceiling of about 0.89. The models reach about 0.30-0.50 for dynamics and close to nothing for timing (a lower bound, because the timing formula dropped one centring step).

**R-10.** H1b now has a fixed definition (DECISIONS 2026-10-05). It ran on 2026-10-06 and H1b is falsified for frozen SyMuPe (scoped; Part 5). The primary measure is the mean-curve centred R² per target against a held-out expert oracle, with the plan's 0.50 / 0.20 thresholds. The secondary measure is the sample-spread coverage as a ratio to the expert oracle. It uses the frozen SyMuPe model on a fresh draw of pieces that neither SyMuPe nor R-07 has seen, because R-07 has already shown these numbers on R10u.

In the code: `experiments/2026-09-28-R-07-symupe-finetune/` (README, `make_split.py`, `split/pieces.csv`, `job/` with `setup.sh`, `fetch_data.sh`, `run.sh`, `eval.sh`, `symupe_train.py`, `pt_train.py`, `summarize_eval.py`), `src/pianolens/models/expression_split.py`. Tickets: R-07, R-10.

#### Known gaps and untested assumptions

Structural coherence and the score basis:

- H4 itself is unsettled. Coherence has not been shown to track skill within matched recording contexts (R-09), and the matched MAJEPPA sample has no virtuosos. A clean test needs context-matched recordings across the full skill range, ideally on a sensor piano.
- Coherence is linear. A boosted-tree model gained about 0.1 tempo R² over ridge whatever the boundaries, so part of the "incoherence" is the model's form, not the performer.
- Tempo coherence transfers across nothing: a model fitted on other movements, even by the same pianist and composer, predicts about zero. That analysis used untuned models and should be treated as a floor.
- The 4-bar block, 1-bar buffer, 12-bar minimum and the alpha grid are conventions, not tuned. The 12-bar minimum was set after one failure case.
- The proxy phrase detector was never validated beyond Mozart and Vienna; it is known to be crude.
- The harmony tension features rely on the key signature and partitura's tension estimate, which were not validated here.
- Batik, the main validation set for phrase work, is one pianist. Paired tests over its movements treat them as independent although they share that pianist's style.

Phrase boundaries:

- The cadence detector's weights are fitted on one composer's cadence idiom and include counter-intuitive signs that were not investigated.
- Claude's phrase annotation is validated only for one model, one prompt, one renderer, simple metres and scores (not transcribed MIDI). On Romantic character pieces it is below the 0.70 bar as a point estimate and the interval does not settle the bar (BL-17). Compound metres (6 pieces, descriptive), nocturnes, waltzes and long Romantic forms are untested. Two ideas for doing better, a rule for where the cadence arrival sits when bass and chord land at different moments, and a period cue in the instructions, have not been tried.
- DCML labels predate the model's training cutoff for every set tested, so exposure to the labels is not excluded. Recognition is self-report only. Only phrase labels made after the cutoff would close this.
- DCML is one analyst team's reading. Agreement between human analysts was never measured, so the ceiling for any annotator is unknown.
- The practice report uses Claude's boundaries only where a cached set exists (the owner's five pieces), and 9 of those 10 annotators recognised the piece, so how far remembered analyses shaped them is not measured. Four of the five are nocturnes and three are in compound or mixed metres, none of which BL-17 tested.

Per-phrase tempo arcs:

- The plus or minus 2-bar null is weaker for long phrases (for 8-bar phrases a 2-bar shift is not maximally out of phase), so `concave_excess` is not strictly comparable across phrase lengths or boundary sources.
- The measure penalises correct but finer segmentation, so it measures "shaping at the DCML level", not shaping at any valid level.
- Untested assumption: the arc is fitted to a tempo curve already smoothed at a 1.5-bar period. For short phrases this smoothing may itself impose or remove curvature. Its effect on `concave_share` was not measured.
- `concave_share` ignores depth. A barely concave phrase counts the same as a deep one, and a performer who overshapes is not distinguished from one who shapes well.
- On Romantic music, Claude's boundaries lose a real part of the signal (n = 3 pieces, transcribed performances), consistent with BL-17's finding that about a fifth of expert phrase ends have no predicted end within a bar. On the owner's pieces the sign of the phrase-tempo value can depend on the boundary source. The over-segmented case the merge rule was built for has no aligned performances.
- Whether per-phrase arcs relate to rated quality or skill is untested.

Repeats, voicing and dynamics:

- None of these three has a validated norm, a null, or a link to listener judgments. They are descriptive.
- Repeated-material matching requires identical bar content, so varied, transposed or sequential repeats are missed.
- Voicing uses the skyline melody, so inner and bass melodies are missed.
- Dynamics compliance treats MIDI velocity as loudness, and hairpin extents in ASAP MusicXML are guessed.

Tier D:

- The references are mostly transcribed recordings, so velocity bands are low confidence unless at least 8 sensor references exist.
- Horn parallel analysis undercounts shared components when several are strong; the windowed count (about 1 to 2) and the whole-piece count (3 to 5) are different objects.
- Moderate flattening (to 50% of the expert size) is not flagged.
- The typicality floor depends on the number of references, so with few references it cannot express strong atypicality.
- The notable and strong rates were calibrated as about 5% and 1% of expert bars on the references themselves; on transcribed input, the related correctness "strong" tier ran above its nominal 1% (BL-18), because a 99th percentile over 14 or 15 experts is close to the maximum; the report chapter describes the interim fix. Tier D uses larger reference sets, but its own rate on small sets was not rechecked.
- Whether being outside the expert band is audible or matters to listeners is untested (H6, H7, listening studies not yet run).

Repeated takes:

- F-07's data are transcribed concert recordings often years apart; a shared transcriber bias may inflate the consistent part, and its size is unbounded.
- BL-16 rests on three pianists, effectively two for the advanced arm and one beginner whose partner is always a faster advanced player, so skill and player identity cannot be separated.
- The claim that same-sitting take-to-take variation is noise must be checked per user (O-01).

Expression models:

- R-07 and R-10 have run. Fine-tuning did not help, no typicality score is validated, and H1b is falsified for frozen SyMuPe (scoped; see R-10 above).
- Pretraining exposure: most PianoCoRe pieces were seen paired by SyMuPe; only PercePiano, the 76 R10u pieces and one Vienna excerpt are unseen by both steps. Unpaired PERiScoPe performances of R10u pieces may exist.
- The flat model defines what the likelihood ratio measures; a different flat family could change the result.
- The R-07 H1b preview measures shared components on per-onset velocity and log inter-onset curves, not on R-02's smoothed per-beat curves, so its shared components are not the same object as the "3 to 5" in the H1b wording. R-10 must use the R-02 procedure itself.
- The 16 GB GPU memory figures are extrapolated from Mac CPU and MPS measurements, not measured on CUDA.


### The report, the comparison player and the app

The earlier chapters explain how PianoLens measures a performance: which notes were right, how the tempo moved, how steady the timing was, how the playing compares with hundreds of expert recordings. Measurements alone do not help a learner. Someone has to decide which of them are worth attention, say so in plain words, and let the learner hear what the difference sounds like. This chapter covers the three layers that do that.

- The **practice report** judges every measurement against experts, ranks the findings, and writes a page with a bar-by-bar timeline and a short "What to practise" list.
- The **audible comparison** cuts short clips of each flagged passage: the learner, the learner replayed on a neutral piano, and experts on that same piano.
- The **local app** wraps both behind a web page that runs only on this computer.

The experiment results behind these layers are in Part 3 (F-08c and P-01). This chapter explains how the layers work, why they were designed this way, and where they are known to fall short.

#### Words used in this chapter

- **MIDI**: a list of notes, each with a start time, an end time, a pitch and a "velocity" (how hard the key was struck, from 1 to 127). Pedal presses are stored as controller events.
- **Provenance** or **capture method**: how a MIDI file was made. It can come from a Disklavier (an acoustic piano with key sensors), a digital piano or other key sensors ("sensor"), a transcription, or it can be written by hand ("synthetic").
- **Transcription**: MIDI guessed from audio by a model. PianoLens uses Transkun on phone audio. Most expert references in the PianoCoRe dataset are transcriptions made with Transkun or Aria-AMT.
- **Alignment**: matching each played note to its note in the score. The report works on the *performed score*, the score unfolded along the repeat path the pianist actually took, so a repeated bar appears twice.
- **Percentile** or **quantile**: the 95th percentile of a set of values is the value that 95% of them stay at or below. In the code, `q95` means the 95th percentile.
- **Reference** or **expert**: another performance of the same piece, used to define what is normal. "Tier D references" are the large PianoCoRe sets, often hundreds of performances per piece. "Same-score references" are performances aligned to exactly the same score and repeat path, such as the 22 pianists of the Vienna 4x22 set.
- **Leave-one-out**: when a reference is itself being scored, it is removed from the set it is compared with.

#### What does the report contain, and what does it leave out?

The report is the single place where every measurement about one performance comes together. It takes one aligned performance and, when available, three other inputs: the learner's other takes of the same passage, reference performances, and error tables from expert performances of the same score. It produces two files side by side. One is a JSON file with every number (schema `pianolens.report/1`). The other is an HTML page for reading.

Everything in the report is organised by bar. A bar is one row of the performed score's list of measures, and its label is the printed bar number. The second pass through a repeated bar gets a suffix, so it reads "12 (2)". Every feature module (correctness, control, expert comparison) indexes bars by the same row, so their findings line up without translation.

Every sentence on the page is a template filled with measured numbers. No language model writes any of the text; that is deferred to a later phase. The report is also built never to fail once a performance has aligned. If one component crashes (for example, the shaping analysis on an unusual score), the error is recorded under `errors` and that section is left empty, while the rest of the report is still produced.

The report deliberately leaves out one thing: an overall grade. The reasons are given in the section "Why is there no overall grade?" below.

In the code: `src/pianolens/report/build.py` (`build_report`, `bar_labels`), `text.py` (templates), `io.py` (`report_from_files`, `write_report`); ticket F-08.

#### When is a finding "notable" or "strong"?

A measurement means little until it is compared with what good pianists do at the same place. The report uses one rule for every channel. A value is **notable** when it is beyond the 95th percentile of the matching expert values. It is **strong** when it is beyond the 99th percentile. Otherwise it is not tiered. By construction, about 5% of genuine expert bars are notable and about 1% are strong. A flag therefore means "rarer than this among experts here". It does not mean "wrong".

This rule was chosen over hand-set thresholds for two reasons. First, the limits come from what experts actually do at that spot, not from someone's opinion of what "too uneven" means. Second, because every channel uses the same two percentiles, a strong timing bar and a strong note bar are equally rare among experts. That lets them sit on one ranked list. The comparison is strict: a value must be *greater than* the percentile. This detail matters for whole-number counts such as wrong notes, as the next section shows.

A value is only tiered when at least 10 reference values exist at that bar or run. With fewer, the value is shown but not judged. The figure of 10 was confirmed as a decision after F-08. No alternative was tested. On the page, strong findings are shown in solid colour and notable ones are only tinted.

What "the matching expert values" means differs by channel. The table lists, for each channel, which population the percentiles are taken from.

| Channel | Compared against | Percentiles are computed over |
|---|---|---|
| Correctness (notes) | What the same note checker reports on clean expert playing | All 12,940 bars of 100 clean expert performances, pooled across 62 pieces. The per-bar expert check (below) adds the experts of the same score at that bar. |
| Tempo and loudness shape | Tier D references | The deviations of held-out references at that bar. The references are fitted in 10 folds, so each one is scored by a model that did not see it. |
| Too flat (tempo, loudness) | Tier D references | The amount of shaping in each 16-bar window across references. "Too flat" means in the low tail. |
| Timing steadiness | Tier D references, with same-score references merged in | Each reference's own leave-one-out timing noise at that bar |
| Pedal blur, evenness | Same-score references only | Their value per bar (pedal) or per run of fast notes (evenness) |
| Whole-performance error rate | Clean expert performances | Error rate per performance (95th percentile 0.164, 99th percentile 0.207) |

The tempo, loudness and too-flat flags are computed by the expert-comparison module (F-06), which the report simply runs twice, once at each percentile. Timing steadiness, by contrast, is computed inside the report itself, and the reason is consistency.

The report takes the learner's fine-timing residual (what is left after the smooth tempo curve is removed) and subtracts the average residual of the references at the same score positions. That average is the "consensus", and it is only used where at least 3 references have a value. Each reference's own noise is measured the same way, against the consensus of the *other* references.

Both target and references are measured on the curve convention of the cached expert data: a tempo fit that ignores printed tempo markings. The control module's own timing measure uses a fit that respects markings, which would not match the cached references. The result is converted from beats to milliseconds with the median beat length in each bar.

In the code: `src/pianolens/report/calibration.py` (`NOTABLE_Q`, `STRONG_Q`, `MIN_TIER_REFERENCES`); `build.py` (`_tier`, `_interpretation_section`, `timing_noise_bars`, `_control_section`); DECISIONS 2026-09-28, after F-06 and after F-08.

#### How are note errors judged, when experts also get flagged?

The note checker is not perfect. Even on expert playing it flags notes, partly for real slips and partly for alignment mistakes and errors in the reference data. So the useful question is not "did the checker flag a note?" but "did it flag more than it flags on experts?". To answer that, the production aligner and checker were run on the clean copies (no mistakes injected) of the D-08 mistake set: 100 (n)ASAP expert performances, 62 pieces, 12,940 bars. Whatever the checker reports on these is the baseline.

The baseline is not small:

- In a typical expert performance, 42% of bars have at least one flagged note (median per performance; the 5th to 95th percentile range is 11% to 82%).
- 7.1% of expert bars have at least one wrong-pitch note, 2.1% have at least two, and 0.85% have at least three.
- The per-performance error rate (wrong plus missed plus extra notes, per graded note) has a median of 4.65%, a 95th percentile of 16.4% and a 99th percentile of 20.7%.

A bar is judged on the two quantities the checker reports most reliably. The first is the number of wrong-pitch notes, whose bar-level precision is 0.996 or higher on D-08. The second is missed plus extra notes per graded score note. Missed notes enter as a rate per bar because they are only reliable at the bar level, not note by note (a decision after F-01). The bar's tier is the higher of the two tiers.

The wrong-pitch limits work out to 1 (95th percentile) and 2 (99th). With the strict comparison, one wrong note is never tiered, two are notable, and three are strong. A single wrong note still shows in the timeline. This was a deliberate decision after F-08: marking any wrong note as strong would put about 7% of expert bars in the strong tier, which breaks the definition of the tier. For missed plus extra notes, the limits are 0.267 per note (notable) and 0.634 (strong).

Every tiered item also carries a *magnitude*: how many times over its notable limit it is. For correctness this is the larger of two ratios: wrong notes over the wrong-note limit, and the missed-plus-extra rate over its limit. With a limit of 1, the wrong-note magnitude is simply the number of wrong notes. Magnitude is only used to order the list; it is never shown as a score.

Separately, the summary card compares the whole performance's error rate with the expert median and 95th percentile. It says "higher than 95% (or 99%) of expert performances" when that applies. This line never becomes a practice item.

Two narrower rules follow from later measurements of where the checker and the transcriber are weak. In fast runs, where neighbouring notes are less than 100 ms apart, the checker is more reliable about the bar than about which notes were wrong (BL-20 and BL-23, in the alignment chapter), so wrong notes there are worded per bar ("2 wrong notes in this fast run") and never as "D instead of C"; their tiers do not change. And on transcribed input, a missed note whose same-pitch predecessor in the score is due less than 100 ms earlier is shown on the timeline but not counted towards any tier, because transcribers often merge such fast repeats into one note (BL-21, BL-25). On the owner's takes this set aside 25 of 1,152 missed notes and removed the tier from 2 notable bars.

In the code: `calibration.py` (`CORRECTNESS_EXPERT_BARS`, `FAST_RUN_MAX_IOI_SEC`, `FAST_REPEAT_MAX_IOI_SEC`), `build.py` (`_correctness_tier`, `global_correctness_limits`, `local_ioi`, `fast_repeat_notes`), `scripts/calibrate_report_f08.py`.

#### What if the score, not the player, is the problem?

Pooling bars from 62 pieces hides a problem that only shows up piece by piece. At some bars, *every* expert gets flagged. The printed score, the edition, or the checker disagrees with what pianists actually play there, often around ornaments or edition differences. In one of Henry's phone takes, the top practice item sat in such a bar: 14 of 15 expert transcriptions of the same piece also showed 4 or more wrong notes there, with a median of 5. The report was blaming the player for the score. The per-bar expert check (F-08c) fixes this by also comparing each bar with experts playing the same bar.

The rule works as follows. The report collects per-bar error counts from expert performances of the same score, recorded the same way as the learner's (next paragraph). Bars are matched by label, so an expert who took a different repeat path still lines up bar by bar. At every bar covered by at least 5 experts, it takes the experts' 80th and 99th percentiles of the two correctness quantities. It then raises each limit to whichever is larger: the global limit or the per-bar expert percentile. To be notable, a bar must now beat both the global 95th-percentile limit and the per-bar 80th percentile. To be strong, it must beat both the global 99th-percentile limit and the per-bar 99th percentile. With fewer than 5 experts at a bar, the global tier stands.

The experts must match the learner's capture method because transcription changes what the checker sees. On transcribed MIDI the apparent error rate roughly doubles, from 0.039 to 0.080 (D-10). A phone transcription checked against Disklavier experts would be judged against cleaner data than transcription can produce. So transcribed input is checked only against transcribed experts, and key-sensor input only against key-sensor experts. The experts are found in this order:

- expert tables or expert MIDI files the caller supplies;
- same-score references of the same capture class, if there are at least 5;
- for transcribed input, up to 15 PianoCoRe transcriptions of the piece, drawn with a fixed seed and optionally restricted to one transcriber family (the app uses "Transkun V2", its own transcriber);
- for other input, up to 15 ASAP (Disklavier) performances of the piece.

Experts whose alignment is suspect (under 80% of notes matched) are left out, and the learner's own source recording is always excluded.

The cut-off of the 80th percentile rather than the 95th came from calibration. A script measured two things under several rules: the share of expert bars still tiered, and how many bars with injected mistakes stay tiered. The table shows the expert-bar side (notable-or-strong / strong).

| Expert bars | Global limits only | Per-bar 80th / 99th (chosen) | Per-bar 95th / 99th |
|---|---|---|---|
| Key-sensor: 40 clean D-08 copies, 28 pieces | 6.8% / 1.7% | 3.7% / 0.67% | 2.8% / 0.67% |
| Transcribed: 150 expert transcriptions of 5 Chopin pieces, leave-one-out, extras not counted | 11.8% / 3.0% | 5.3% / 1.4% | 3.7% / 1.4% |

A bar must now beat two limits, so the joint rate falls below either one alone. The per-bar 95th percentile (the ticket's first idea) undershoots the nominal 5% on both capture classes. The per-bar 80th percentile keeps notable nearest 5% and loses the fewest mistake bars. A per-bar 50th percentile was also tried; it gave 4.5% on key-sensor input but 6.8% on transcribed input.

The price is some recall. At a mistake-injection rate of 0.05, 85.5% of the injected-mistake bars that were tiered without the check stay tiered (74.9% with the 95th percentile), and the tiered share of injected bars falls from 18.1% to 15.5%. Absolute recall is low at every setting, by design: a bar with a single injected wrong note is never tiered.

The reader sees what the check did. A suppressed bar keeps its counts in the timeline with the note that it "matches expert transcriptions here (likely score/edition artefact)", or "expert recordings" when the experts are key-sensor. A strong bar that is only notable against the experts is moved down a tier, and its sentence says that experts of this score also show errors there. When no bar reached 5 experts, the header says no per-bar check was possible, so flagged bars may include score or edition artefacts.

On Henry's five phone takes the change was large (aggregate figures only):

- Tiered correctness bars per report fell from 6 to 76 before the check to 3 to 30 after.
- Strong correctness bars fell from 0 to 30 per report to 0 to 2.
- In the old top-3 lists, 25 of 30 practice items were about notes, and in 19 of them extra notes outnumbered wrong plus missed notes. Afterwards, 15 of 30 were about notes and none counted extra notes.

The limits of this evidence are stated in the spec. The key-sensor calibration covers only pieces with 6 or more ASAP performances (40 of the 100), the transcribed calibration covers 5 Chopin pieces, and neither covers phone audio.

In the code: `build.py` (`expert_bar_limits`, `bar_error_table`, `_correctness_section`), `io.py` (`report_from_files`, `expert_bar_tables`, `pianocore_expert_midis`, `_capture_class`), `calibration.py` (`EXPERT_CHECK_MIN_REFS = 5`, `EXPERT_CHECK_Q = (0.80, 0.99)`, `EXPERT_CHECK_MAX_REFS = 15`), `scripts/calibrate_expert_check_f08c.py`; spec `docs/specs/report-validation.md` section 4; ticket F-08c.

#### Why are extra notes ignored on phone recordings?

Phone recordings brought a specific problem. The A-01 study found that phone transcriptions keep note timing well but add many spurious high notes, with 15% to 29% extra notes on three of Henry's five takes. Real-room microphone recordings from the PianoVAM dataset do not show it. A later analysis (BL-22, in the audio chapter) found that most of the high extras are a second, independent sound in those recordings, a quiet high melody unrelated to the piece, whose source is still unknown. Left alone, these notes dominated the practice list. Transcribed extras are unreliable in general anyway, so the rule below does not depend on that explanation.

So on transcribed input, extra notes do not count towards any correctness tier. They stay visible in the timeline, marked low confidence, and the practice sentences count them as zero. This happens automatically when the provenance is `transcribed`, which the app always sets for audio uploads and for MIDI the user marks as transcribed. Missed notes are then judged against missed-only limits from the same clean expert set: 0.158 per note for notable and 0.286 for strong (27% of expert bars have at least one missed note).

A rule-based filter from A-01b can also remove some of the phantom notes before scoring. It is optional and off by default; see the command-line section for what it removes and why.

In the code: `ReportConfig.extras_low_confidence` in `build.py`; `CORRECTNESS_EXPERT_BARS["missed_per_note_q95"]` in `calibration.py`; `docs/specs/phone-audio-baseline.md`; DECISIONS 2026-09-28, after A-01 and after F-08c.

#### How does the report tell a learned mistake from a slip?

When a learner uploads several takes of the same passage, a mistake that appears in more than one take is probably learned rather than accidental. That is exactly what a student most needs to see (a decision after F-08).

To compare takes, each take's errors are turned into keys, one set per bar label:

- ("wrong_pitch", score note, played pitch);
- ("missed", score note);
- ("extra", played pitch).

Takes on the same repeat path share score note identifiers, so an identical key in two takes means the same mistake at the same spot.

The first rule, "the same key in 2 or more takes", failed its calibration. It was tested on *expert pseudo-takes*: 3 ASAP pianists per piece, for 30 pieces, treated as if they were 3 takes by one player. Their slips are independent, so any error that "recurs" is really a checker or score artefact. The naive rule marked 24% (2 takes) to 31% (3 takes) of expert bars as strong. Most of the recurrences were missed notes in chords and ornaments that the checker reports for every pianist.

The rule now in the code is much narrower:

1. Only wrong pitches count: the same wrong pitch at the same score note in at least 2 takes, with the main performance counting as a take.
2. Any key the checker also reports for *any* expert recording of the same score and repeat path is removed, because it is probably an artefact.
3. The bar is promoted to strong only when at least 2 expert recordings were checked. With fewer, recurring errors are listed but not promoted, and the correctness card says why.
4. Missed and extra recurrences are never promoted.

The table shows the share of expert bars each rule would promote.

| Rule | 2 takes | 3 takes |
|---|---|---|
| Any kind, no filter | 24% | 31% |
| Wrong pitch only, no filter | 3.3% | 4.2% |
| Wrong pitch only, filtered against 2 experts | 0.5% | 1.0% |
| Wrong pitch only, filtered against all other experts (median 6) | 0.18% | 0.51% |

The experts for the filter are found automatically. When takes are given, the report loads up to 6 ASAP performances of the piece, excluding the learner's own source, and keeps those on the same repeat path. Same-score references count too.

A known-answer test (sample (e)) shows the rule behaving as intended. It uses three synthetic takes of Chopin Op. 10 No. 4. Each take has its own 2% random slips, plus the same wrong note in bar 30 in every take. Bar 30 came out as the only recurring bar, marked strong, and first on the practice list, and no random slip was promoted.

The main limitation is that the calibration used different pianists as pseudo-takes. One player's own habits may recur more across their takes than independent slips do, so the real test needs one player's repeated takes. Those recordings (O-01) do not exist yet.

In the code: `build.py` (`error_signatures`, `expert_error_keys`, `recurring_errors`, `_takes_section`), `calibration.py` (`RECURRING_KINDS = ("wrong_pitch",)`, `RECURRING_MIN_TAKES = 2`, `RECURRING_MIN_EXPERTS = 2`), `scripts/calibrate_recurring_f08b.py`, `scripts/build_report_samples_f08.py`; DECISIONS 2026-09-28, after F-08b.

#### When is loudness trusted?

Transcription estimates how hard a key was struck poorly, and loudness from a phone is only relative. So loudness findings are treated as low confidence unless both the learner's MIDI and the loudness references come from key sensors. The expert-comparison module uses only Disklavier or sensor references for loudness when at least 8 of them exist; otherwise it uses all references and marks velocity low confidence. A transcribed or unknown-provenance target is always low confidence. Low-confidence loudness findings still appear in the timeline and charts, and the loudness chart is titled "(low confidence)", but they never enter "What to practise".

In the code: `SENSOR_PROVENANCE` and `min_sensor_velocity_references` in `src/pianolens/features/interpretation.py`; `confidence_notes` in `text.py`; DECISIONS, after D-10.

#### Where do the report's phrase boundaries come from, and what does it say about them?

The shaping section reports whether the tempo inside each phrase is slower at the edges than in the middle (the per-phrase measure `concave_excess`, explained in the shaping chapter). That needs to know where phrases begin and end. The experiments showed that Claude reads phrase boundaries from a score much better than the rule-based cadence detector, so the report now uses Claude's boundaries wherever a cached set exists for the piece, and the detector otherwise. The cache is built once per piece with the same blind protocol as the R-08d experiment: two independent readings by fresh annotators that see only a text rendering of the score, a check that no label leaked into the rendering, and a record of the model, the date and the exact score used. The report uses the average over the two readings. So far caches exist only for the owner's five pieces.

Because these boundaries are not validated for this use, the report says so in the shaping card and in the methods footer. It states:

- the source, and how many of the readings recognised the piece;
- their measured accuracy against expert annotations on Romantic character pieces (BL-17): about 0.64 on average (plausibly 0.55 to 0.72), below the project's 0.70 bar, and from 0.14 to 0.92 on single pieces, against 0.31 for the cadence detector;
- that nocturnes and waltzes were never tested, and that compound metres such as 6/8 and 6/4 are not validated (6 pieces, descriptive only);
- that the measure itself fell short of its expert-boundary level on Romantic pieces (F-05e).

Next to the value from Claude's boundaries, the report always shows the value from the detector's boundaries and the value from each of the two readings, plus the phrase count against the detector's, because the measure penalises correct but finer phrasing. When the Claude-based and detector-based values point in opposite directions, the finding is labelled **undetermined**: the report cannot say whether the player shaped the phrases or not. No practice item depends on this measure. On the owner's pieces, the finding is undetermined for two of the five takes, under both transcribers; nothing else in those reports changed.

In the code: `_shaping_section` in `src/pianolens/report/build.py`; `PHRASE_CAVEATS` in `text.py`; the methods text in `render.py`; `src/pianolens/features/phrases_llm.py`; `scripts/build_llm_phrases.py`; DF-02 in `DEFECTS.md`.

#### How do bar flags become a short practice list?

A full report can hold dozens of tiered bars across eight channels: notes, tempo shape, loudness shape, too flat (tempo), too flat (loudness), timing, pedal and evenness. A learner needs a handful of concrete things to work on. The report gets there in two steps: it groups bars into issues, then ranks the issues.

Grouping is simple. Consecutive tiered bars in one channel become one issue, whose tier is the highest in the span and whose magnitude is the largest. For "too flat", the magnitude is the expert median amount of shaping divided by this performance's amount.

An issue can be listed but kept off the practice list for two reasons. The first is low-confidence loudness. The second concerns a tempo or loudness shape issue that overlaps a too-flat window in the same channel. That issue is treated as explained by the flatness. Without this rule, a deadpan rendition's top items were per-bar shape flags such as "you move ahead 67%", when the real finding is that the whole section is flat.

Each issue gets one template sentence with its bar numbers, the measured value, the expert range and a short fixed piece of advice. For notes the advice is "play these bars slowly, hands separately, until every note is secure". For timing it is "practise with a slow, steady inner pulse".

Ranking uses these keys, in order:

1. tier: strong before notable;
2. category: notes first, then control (timing, pedal, evenness), then shaping and interpretation (tempo and loudness shape, too flat);
3. recurring errors first;
4. magnitude, largest first;
5. earlier bar first, to break ties.

The category order is a teaching choice: notes first, then control, then the music. It replaced the first version's ranking by magnitude alone, which let a bar of timing jitter outrank three wrong notes. The list shows the top 3 eligible issues. If there are none, the page says "Nothing here is beyond the expert range". The number 3 and the category order are judgements, not measurements.

In the code: `build.py` (`collect_issues`, `_group_spans`, `CATEGORY_RANK`, `ReportConfig.n_practise = 3`), `text.py` (`issue_text`); DECISIONS 2026-09-28, after F-08 and after F-08b.

#### Why is there no overall grade?

The report never adds its measures into a single score. How wrong notes, control, shaping and interpretation combine into perceived quality is an open research question. It is meant to be answered by the rating model (R-04) and the listening studies (Phase 3), not by invented weights. The rating model is still only at single-rater reliability, so the page says that model-based ratings are not included. A single grade would also blur the confidence differences between channels: timing from a phone is trustworthy, loudness from a phone is not, and one number cannot say which parts to believe.

In the code: the module docstring of `build.py`; `_interp_card` in `text.py`; the methods section written by `render.py`.

#### What does the report page look like?

The report page is a single self-contained HTML file: inline styles and drawings, no scripts and no external requests, with light and dark themes that follow the system setting. That keeps it private and lets it open anywhere. It is laid out from overview to detail:

1. **Header.** The piece and input, then the confidence notes. These cover: why velocity may be low confidence; that transcription roughly doubles the apparent error rate; a suspect alignment; missing references; how much of the score could be mapped to the reference edition (noted when under 90%); that extras are not counted; whether the per-bar expert check ran; that 42% of expert bars have a flagged note; and that the control measures are not validated as skill measures (D-10).
2. **Summary cards** for notes, control, shaping and interpretation, each a few sentences with numbers. The notes card includes a table of takes when there are several.
3. **Bar-by-bar timeline**: one row per channel and one column per bar. Strong cells are solid and notable cells are tinted, with a separate colour for too flat. Numbers in cells count flagged notes, and hovering shows the values. With several takes, an extra row shows how many takes had errors in each bar.
4. **Charts**: tempo and loudness curves against the expert band (10th, 50th and 90th percentile), with flagged bars shaded. Evenness is plotted per run of fast notes against note rate, with published values from instructed scales drawn as boxes. The page only compares with published values at a note rate within 20%, a presentation choice.
5. **What to practise.**
6. **Methods and limitations**, with links to the validation specs and the licence note.

In the code: `src/pianolens/report/render.py` (`render_html`, `timeline_svg`, `curve_svg`), `text.py` (`confidence_notes`, `summary_findings`).

#### How do you run the report from the command line?

The command-line tool is the simplest way to get a report, and the one used for the validation samples. It loads the files, aligns them, builds the report, writes the HTML and JSON, and prints the practice list and any component errors. Its options map directly onto the report's inputs.

| Option | What it does |
|---|---|
| performance (positional) | The performance MIDI file |
| `--score` | The score (MusicXML, MEI). Without it, `--piece-id` looks the score up in ASAP. |
| `--piece-id` | The canonical piece id. Also loads that piece's PianoCoRe references. |
| `--title` | Header title |
| `--provenance` | `disklavier`, `sensor`, `transcribed`, `synthetic`, or `unknown` (the default). It sets velocity confidence and the extras rule, and `transcribed` also selects transcribed experts for the per-bar check. `unknown` is loaded like `synthetic` but labelled `unknown`, so velocity is low confidence. |
| `--take` | More takes of the same passage. Turns on the recurring-error section and loads up to 6 ASAP experts for its filter. |
| `--reference-midi` | Same-score references. Only those on the learner's repeat path are used. With at least 5 of the same capture class, they also serve as the per-bar expert check. |
| `--reference-provenance` | Capture method of those references |
| `--exclude-reference` | PianoCoRe ids to leave out. The learner's ASAP source is excluded automatically when the file sits in an `asap` folder. |
| `--no-pianocore` | Do not load tier D references |
| `--note` | An extra note for the header (can be repeated) |
| `--filter-extras {off,rule}` | Remove likely transcription extras before scoring. Off by default, and refused unless `--provenance transcribed`. |
| `--out` | Output HTML path; the JSON goes beside it |

The extras filter (A-01b) removes a note only when it meets all of these conditions:

- it is at or above C7;
- it is shorter than 0.1 s;
- no note a harmonic step below it starts with it or is still held, so it has no plausible harmonic source;
- its pitch recurs at least as often as its neighbours.

These settings were chosen as the grid point that removed the most notes from Henry's Transkun takes while staying within a safety budget on PianoVAM: at most 0.1% of true notes removed overall and at most 5% of true notes at G6 or above. The filter is validated for Transkun output only. It stays off by default because its effect on the phone artefact cannot be measured without ground truth for phone audio. When used, it filters every take and adds a header note with the number of notes removed. The app uses the same settings.

The tool does not expose the per-bar expert check's settings: turning it off, choosing a transcriber family, or supplying expert files. As a result, transcribed input from the command line is checked against a seeded draw of PianoCoRe transcriptions from any transcriber, although the calibration was done per transcriber family.

In the code: `scripts/pianolens_report.py`; `src/pianolens/audio/extra_filter.py` (`rule_scores`, `filter_midi`); DECISIONS, after A-01b.

#### Why add sound, and which passages get it?

A flag says "unusual here". It cannot tell the learner whether the difference matters to the ear. Hearing the passage next to a typical expert on the same piano lets the learner judge that directly, so the platform decision requires an audible comparison for every flagged passage. The comparison module reads only the report's JSON file, never its code, so changes to the report cannot silently break it. Before cutting anything, it re-runs the alignment, which is deterministic, and refuses to continue if the report's bars do not match the aligned score.

The first job is to turn issues into short listening windows. Every tiered issue is a candidate, including low-confidence ones that are not practice items. Candidates are ordered by:

1. tier;
2. practice-eligible before low-confidence;
3. category, in the report's order;
4. magnitude.

Each issue then either joins an existing window or starts a new one. It joins when its bars touch or overlap that window (at most 1 bar apart) and the merged window stays within 4 bars. An issue longer than 4 bars, such as a 16-bar too-flat finding, is cut to its first 4 bars and marked as truncated, and the player says so. At most 8 windows are made by default (the app lets the user choose between 1 and 12). Once the cap is reached, later issues can still join an existing window but cannot start a new one.

After each placement, windows that have grown into each other are merged if the result still fits in 4 bars. Otherwise the overlap is removed from the lower-priority window. This clean-up fixed an overlap bug seen on a sample report.

The 4-bar limit, the 1-bar gap and the 8-window cap are listening-length choices. They were not tested with listeners.

In the code: `src/pianolens/compare/windows.py` (`select_windows`, `_coalesce`); `engine.py` (`inputs_from_report`, `_bar_grid`); ticket P-01.

#### How are two performances lined up in time?

To cut every performance at the same musical place, the engine needs, for each performer, a map from score beat to seconds. The map is built from that performer's own notes, so it follows their rubato exactly where notes are played and interpolates in a straight line between them.

It is built in four steps:

1. **Take the matched notes.** Use the matched notes that are not grace notes, the same ones the tempo model uses. At each score position, take the median onset, so a chord or a spread chord gives one time.
2. **Keep time moving forward.** Fit the closest curve that never goes backwards (isotonic regression), weighting each position by its number of notes. One misaligned note then cannot make time run backwards.
3. **Remove outliers one at a time.** Refit after dropping the position furthest from the curve. Keep going while that distance is more than the larger of 0.25 s and four times the typical distance. The typical distance is a robust spread measure: the median absolute deviation scaled by 1.4826. At most 10% of positions may be dropped. They go one at a time because the fit spreads a single late note's error over its neighbours; an earlier filter that dropped outliers all at once removed 3 positions for 1 bad note.
4. **Extend past the ends.** Before the first position and after the last, continue the map in a straight line, using the median seconds per beat of the 6 nearest positions (or 0.5 s per beat if that cannot be computed).

In the code: `src/pianolens/compare/timemap.py` (`time_map_from_notes`: `outlier_sec=0.25`, `edge_knots=6`, `max_drop_share=0.1`).

#### Which expert does the learner hear?

The comparison should sound like an ordinary expert reading of this passage, not an eccentric one. So for each window the engine ranks the references by how close they are to the expert median *in that window*, and picks the closest.

The ranking looks at the learner's score beats from the bar before the window to the bar after it, mapped onto each reference's score. A reference is eligible only if at least 80% of those beats are observed in both tempo and loudness, and at least 3 must be eligible or no expert clip is made. Each eligible reference is scored on three terms:

- tempo shape (the smooth tempo curve, centred within the window);
- loudness shape (the smooth velocity curve, centred the same way);
- tempo level (the average speed in the window), so the chosen expert also plays at a typical speed there.

Each term measures how far the reference sits from the median of all references, in units of the references' own robust spread. The three terms are combined with equal weight.

The closest reference becomes the "typical expert". A second, "contrasting expert" is the reference whose distance is nearest the 90th percentile of all distances. The idea is a clearly different reading that is still inside the expert range, not an outlier.

A chosen reference can still be unusable. The engine tries up to 8 candidates per clip and skips any whose MIDI cannot be loaded. It also skips any where fewer than 60% of the window's notes are found in its score within 0.125 beats. The tolerance is needed because different score sources round irregular groupings (tuplets) differently; an exact match failed on a bar of a real piece. The contrasting expert must be a different performance from the typical one. Each expert clip uses a single beat offset for the whole window: the most common offset between the two scores over the window's notes.

In the code: `src/pianolens/compare/experts.py` (`rank_experts`: `min_coverage=0.8`, `velocity_weight=1.0`, `contrast_quantile=0.9`); `engine.py` (`expert_clip`, `_span_match`, `_offset_to`; `CompareConfig.max_expert_tries=8`, `min_span_match=0.6`).

#### How are the clips cut, rendered and levelled?

Each window gets up to four clips that cover the same stretch of the score:

| Clip | What it is | When it is made |
|---|---|---|
| Your recording | The original audio, cut at the learner's alignment times | Audio input only. The MIDI must share the audio's time base, which a transcription of that audio does. |
| You, same piano | The learner's MIDI or transcription, played back through the fixed S-02 piano (a Salamander grand SoundFont, a sampled-piano sound bank, rendered with FluidSynth at 44.1 kHz) | Always |
| Typical expert | The typical expert on the same piano, cut at its own alignment times | When references exist |
| Another expert | The contrasting expert, treated the same way | Optional, on by default |

Replaying everyone on one piano removes differences in instrument, room and microphone. What is left to hear is timing, dynamics and notes.

A clip runs from the start of the bar before the window to the end of the bar after it, in each performer's own time. At the first bar of a piece the lead-in is 0.6 s instead of a bar. At the last bar, the clip ends 0.6 s after the last key is released. Every clip extends at least 0.25 s past the window.

Only the needed stretch is rendered, starting 6 s early so that notes struck in that lead-in are still ringing when the clip starts. The pedal position at the start is carried into the excerpt. Rendering whole pieces had taken about 22 s per performance under load, and this change cut one sample run from 7.8 minutes to about 2. Cuts are exact to the sample. A span that runs past the end of the audio is padded with silence, so a clip's timeline always matches its record.

Within a window, all clips are brought to the same loudness. Loudness is measured with the broadcast standard ITU-R BS.1770, whose unit is the LUFS. The target is -20 LUFS. It is lowered for all the clips together if any clip would otherwise peak above -1 dBFS, so the clips stay matched. Clips shorter than 0.4 s cannot be measured and keep their level. Each clip fades in and out over 20 ms to avoid clicks. Clips are saved as mono MP3 at 96 kbit/s through ffmpeg, whose header lets players remove the encoder's start-up delay.

A record of the run, `manifest.json`, lists for every clip:

- its start and end in the source;
- where the window starts and ends inside the clip;
- the time of every bar line inside the clip;
- which expert it is and how close that expert is to the median;
- the checks described in the next section.

In the code: `src/pianolens/compare/engine.py` (`build_comparison`, `_span`, `render_span`, `excerpt_performance`; `CompareConfig`: `pre_bars=1`, `post_bars=1`, `edge_pad_sec=0.6`, `render_lookback_sec=6.0`, `target_lufs=-20.0`, `max_peak_dbfs=-1.0`), `clips.py` (`cut`, `apply_fades`, `match_loudness`, `encode_mp3`; `FADE_MS=20`, `MP3_BITRATE="96k"`).

#### How do we know the clips are cut in the right place?

No listener has checked the clips yet, so every clip carries measurable proxies for "this sounds right":

- the clip's length against the requested span;
- the cut error: when a note falls exactly on the window start, the gap between when that note sounds in the clip and where the window was meant to start;
- the onset-train lag: how far the clip's audio onsets are shifted from a pulse train built from the notes the clip should contain. This checks the timing of the whole clip at once;
- for the learner's own audio, its lag against the replayed transcription. This is measured once on a 60 s stretch starting 30% into the piece and again per clip. It is recorded, not corrected;
- for experts, the share of the window's notes found in the expert's score.

These proxies were run on Henry's five phone reports and two sample reports: 56 windows and 208 clips in total. They show the cutting to be accurate:

- Every window of Henry's reports had all four kinds of clip.
- Clip lengths were within 0.02 ms of the request, and within 0.9 ms after decoding the MP3.
- Every one of the 112 expert clips matched the window's notes fully.
- On all five takes, the original audio sat at 0 ms lag from its replayed transcription (correlation 0.78 to 0.88).
- The onset-train lag was within 50 ms for every clip. It carried a constant bias of about 20 ms that also appears on exact renders, so the bias comes from the onset detector, not from the cuts.

A simpler check, finding the one detected onset nearest the window start, turned out to be fragile. It sometimes picked a louder neighbouring note, with outliers up to 139 ms. That is why the whole-clip check is the main one.

In the code: `engine.py` (`_cut_check`, the audio checks in `build_comparison`), `clips.py` (`estimate_lag`, `onset_train_lag`, `nearest_onset`), `scripts/build_compare_p01.py`; WORKBOARD P-01 entry.

#### How does the player keep your place when you switch?

A comparison is only useful if you can flip between versions at the same musical spot. But the performers take different amounts of time over each bar. The player solves this with the bar-line times from the manifest. When you switch, it finds which two bar lines the current position lies between, and how far between them. It then jumps to the same fraction between the same two bar lines in the new clip. That follows each performer's rubato. Audio is decoded in the browser with the Web Audio interface, so the switch is instant.

The controls are simple. Buttons or keys 1 to 4 choose the version, space plays and pauses, and L toggles looping, which is on by default. Clicking the timeline jumps, and the timeline shades the flagged bars and draws the bar lines. Each window lists the report sentences that caused it, and each expert clip shows the performer (when known), the dataset, the transcriber, and how close it is to the expert median.

The standalone player is one HTML file per report, with every clip embedded in the page. A strict content security policy (a browser rule that limits what a page may load) forbids all network access. Because the clips are inside the file, it is as private as the recordings and stays under `data/interim/`. The app does not reuse this file. It has its own player with the same bar-anchored switching, and it fetches clips from the local server instead of embedding them.

In the code: `src/pianolens/compare/player.py`, `player_template.html`; `src/pianolens/app/static/app.js` (`anchors`, `mapPos`).

#### What does the app do with an upload?

The app is where all of the above becomes one action: pick a piece, upload a recording or a MIDI file, wait about a minute, read the result. It runs only on this computer, a decision explained in the next section.

**Choosing a piece.** The piece list has two parts. The first is PianoCoRe pieces with at least 50 cached expert performances (584 pieces). The second is every ASAP piece (221), even those with few or no PianoCoRe references, because ASAP provides their score and the Disklavier experts for the per-bar check. For a PianoCoRe-only piece, the score is the piece's MusicXML from the PianoCoRe archive, copied into the app's folder the first time it is needed. A piece that is not listed can still be analysed by uploading its score. The report then covers notes, timing and shaping, but it has no expert comparison and no expert clips. The threshold of 50 references was not tuned for the app.

**Uploading.** Files must be all audio (wav, mp3, m4a, flac, aac or ogg) or all MIDI. Several files are treated as several takes: the first is analysed in detail and the rest feed the recurring-error check. Up to 6 files are kept, and an upload may be at most 1 GiB. Under "Advanced", the user can list references to leave out, choose the number of comparison passages (1 to 12), or ask for the report without clips.

**Running.** Each upload becomes a job with its own folder. A separate worker process runs four steps and reports progress after each. The table shows how the steps differ for MIDI and audio.

| Step | MIDI upload | Audio upload |
|---|---|---|
| Provenance | Chosen by the user: Disklavier, digital piano or sensor, written by hand, "not sure", or transcribed from audio (by Transkun or by another transcriber), which is then read like an audio upload without the transcription step | Always transcribed |
| 1. Transcribe | Skipped | ffmpeg converts the file to 44.1 kHz WAV. Transkun 2.0.1, the A-01 transcriber, writes MIDI, trying the Apple GPU first and then the CPU. A sanity check looks for gross timing failures, and the optional extras filter can run. |
| 2. Quick alignment | The first take is aligned once to measure the share of notes matched. Below a match ratio of 0.5 the run stops as a likely wrong piece, with an "Analyse anyway" override (the upload form has one too, for short excerpts). Between 0.5 and 0.8 it continues with a warning in the report. | Same |
| 3. Report | The full report, with the chosen provenance | The same, plus a header note on what phone audio supports, and a per-bar expert check against Transkun transcriptions only |
| 4. Clips | Replayed and expert clips | Also clips of the original audio, from the first take |
| Headline error figure | The overall error rate | Wrong plus missed notes per score note. Extras distort the overall rate: on one of Henry's takes it was 39%, against a wrong-plus-missed rate of 9.9%. |

The job's identifier is a hash of the uploaded bytes, the chosen options and the code version, but not the title. The code version is a hash of the analysis source code plus a manual pipeline version number, bumped for changes the hash cannot see, such as a new calibration file. Uploading the same files with the same settings therefore reuses the finished (or running) job, but only while the analysis code is unchanged. Because the worker runs in its own process group, cancelling also stops the transcriber and the renderer. A job whose worker died without finishing is shown as "interrupted", and failed, cancelled or interrupted jobs can be retried from their stored inputs.

**Reading the result.** The results page opens with notes on what to trust for this kind of input:

| Input | Trust | Read with care | Low confidence |
|---|---|---|---|
| Phone or room audio | Timing, tempo | Wrong and missed notes (read against expert transcriptions made the same way) | Extra notes, dynamics, voicing, pedal |
| Disklavier or key-sensor MIDI | Notes, timing, tempo | Control and shaping measures (not validated as skill measures, D-10) | Dynamics when the piece's references are transcriptions |

Below the trust notes come the practice items. Each one has the A/B player of the comparison window that shares the most bars with it, plus small tempo and loudness curves for those bars (and one bar either side) against the expert band. Then come all the other passages, and the full report in a frame. A History page lists past analyses and deletes them.

The app has been checked end to end. One of Henry's phone takes took about a minute:

- transcription, 10 s;
- the quick alignment, 82% of notes matched;
- the report, 20 s;
- 8 windows and 30 clips, in another 20 s.

Its practice bars matched the earlier A-01 report for the same take. A MIDI sample took about 20 s. The uploaded-score path worked without references, and cancelling during the report stopped the worker. Six automated tests cover the upload parsing, the job identifier, matching practice items to windows, the curves, the security checks and a full MIDI run.

In the code: `src/pianolens/app/catalog.py` (`MIN_REFERENCES = 50`), `server.py` (`App.create_job`), `jobs.py` (`JobStore`, `job_id`), `pipeline.py` (`run`), `results.py` (`results_data`, `best_window`, `trust_notes`), `pages.py`, `static/app.js`, `scripts/pianolens_app.py`, `tests/app/test_app.py`; `docs/APP.md`; ticket P-02.

#### How is the learner's data kept private?

Two kinds of data pass through the app, and neither may leave the computer. Henry's recordings are personal. The reference data (PianoCoRe and ASAP) is licensed for non-commercial research and must not be redistributed. So the decision was to build a local-only app first, with no hosting. Hosting is a separate owner decision tied to licensing (BL-01).

The protections are layered:

- **Local only.** The server listens only on 127.0.0.1, so no other machine can reach it. It makes no outgoing requests, and every page, script, style and clip comes from the server itself: no web fonts and no external libraries.
- **Wrong host name refused.** Requests whose `Host` header is not `127.0.0.1` or `localhost` with the right port are refused. This blocks DNS rebinding, a trick in which an outside web page gets the browser to talk to a local server under a foreign name.
- **Cross-site actions refused.** Requests that change state, sent from another site's page (a foreign `Origin` header), are refused. So a web page elsewhere cannot start or delete analyses.
- **Browser rules.** Every response carries a strict content security policy and tells the browser not to cache it or send it on as a referrer.
- **No file names in logs.** The server's request log is switched off. This matters because an earlier incident committed a log that contained recording names. Uploaded files are stored as `take1`, `take2` and so on; the original names are kept only in the job's own record.
- **One place, easy to delete.** Everything lives under `data/interim/app/`, which git ignores. Deleting a job from History removes its whole folder. Uploads, reports and clips must never be committed, uploaded or shared.

These measures stop other machines and other websites. They do not stop other programs or users on the same computer, since the app has no login.

In the code: `server.py` (`make_server`, `_host_ok`, `_origin_ok`, `CSP_APP`, `CSP_REPORT`, `log_message`), `jobs.py` (`default_root`, `create`, `delete`); `docs/APP.md` (Privacy); DECISIONS 2026-09-28, the platform, and after A-01.

#### Where does a tier fire more often than it should?

The tier rule promises that about 1% of genuine expert bars are strong. The calibrations show several places where that promise is not kept. One of them, strong note flags on transcribed input, has an interim fix that failed its confirmation run by the pre-registered rule and is kept, as a disclosed deviation, until the note checker is fixed.

**BL-18: strong notes on transcribed input.** On transcribed input, strong correctness bars appeared more often than 1%: 1.4% overall on the expert transcriptions used for calibration, 0.58% for Transkun V2 and 2.3% for Aria-AMT. The cause is small numbers. With only 14 or 15 experts at a bar, their 99th percentile lies between the two largest expert values, so a learner who merely *equals* the worst expert at a bar is already strong.

BL-18 tested replacement rules on transcribed performances never used before (207 of them, from 11 pieces). The family of rules that matters requires a bar to have more errors than every expert at that bar, plus a margin of k extra notes; it is written R1(k). Another candidate replaces the global strong limits with limits estimated separately for each transcriber. No candidate met the pre-registered bar on the development data, so the candidate list was extended (disclosed as an amendment before any held-out data was touched), and the rule chosen was the strictest variant: more than the worst expert plus 2, with per-transcriber limits. On held-out data it passed its pre-registered test, with strong at 0.17% and 0.19% for the two transcribers.

The auditor confirmed the numbers and returned the rule. The test had set only an upper limit on the strong rate, and the chosen rule overshot it: strong fell to about a fifth of its nominal 1%, strong flags on injected mistakes fell to 0.16 of the old rule's, and bars with three injected wrong notes were strong only 52.9% of the time, against 96.5% before. The auditor traced the overshoot to runs of bars in which 80% or more of the notes are missed, three or more bars in a row. No candidate rule could move them, so to bring the overall rate down to 1% the selection had to suppress everything else. Most such runs sit at the very start or end of Aria-AMT transcriptions, which fits truncated source videos rather than transcriber failure; in the reference corpus each transcriber was only ever run on one source collection, so a per-transcriber limit really measures the collection.

The interim default, set by the lead after the audit, is R1(0) with no per-transcriber limits: on transcribed input a bar is strong only when it has more errors than every expert at that bar, as well as exceeding the global limit. On the held-out data that gives 0.62% (Transkun V2) and 1.01% (Aria-AMT), keeps 0.84 of the old rule's strong flags on injected mistakes, and keeps every bar with three injected wrong notes where no expert had more than one. Runs of mostly missed bars get their own rule: three or more consecutive bars with at least 80% of notes missed become one low-confidence item, "passage not heard (not played, or not in the recording)", and get no correctness tier. Key-sensor input is unchanged. On the owner's ten reports, strong correctness bars number 14 under the old rule and 11 under the interim one (3 under the returned rule).

R1(0) was picked after seeing the held-out data, so it needed a fresh confirmation. That run, BL-18b, used 12 new pieces and 238 expert transcriptions treated as learners, with criteria written before any of them was drawn. This time they were two-sided.

| Criterion | Transkun V2 | Aria-AMT | Result |
|---|---|---|---|
| C1: clean strong rate between 0.30% and 1.25% | 0.58% | 1.04% | pass |
| C2: same notable-or-strong bars as the old rule | 0 bars differ | 0 bars differ | pass |
| C3: strong on injected mistakes at least 0.75 of the old rule's | 0.81 | 0.84 | pass |
| C4: at least 95% of bars given exactly 3 wrong notes strong | 71.5% | 68.4% | fail |

**The verdict is FAIL by the pre-registered rule.** The rule registered for a FAIL was to go back to the old rule, R0. The lead did not apply it, and recorded the deviation in DECISIONS. The auditor accepted this as a disclosed deviation from a pre-registered action, not as a new reading of the verdict. The reasons are two. First, C4 could not tell the rules apart. The tested bars were chosen where every expert had at most 1 wrong note, and the global strong limit is 2, so whenever the checker counts all 3 wrong notes the bar is strong under R0 and R1(0) alike (100% in both families). R0 scored the same on C4 (71.6% and 68.6%); the two rules differ on 1 of 1,130 and 3 of 1,125 bars. So C4 measured the note checker, not the rule. Second, R0 fails C1 on Aria-AMT (2.09%), so going back would restore the original flaw and fix nothing. The design error in C4 was shared by the BL-18 audit that proposed it.

So R1(0) plus "passage not heard" stays the interim default, **Provisional**: it meets C1 to C3 on one new sample of 12 pieces, which is not a confirmation. Transkun V2 passes C1 on the point estimate only (its t-interval runs from 0.09% to 0.59%), and its C3 bootstrap interval touches the 0.75 floor. The run rule mattered: without it, Aria-AMT would have been at 1.55% strong, above the band.

The number a learner should know follows from this: **on transcribed input, about 7 in 10 bars with 3 wrong notes become strong**, because of the note checker (DF-12), not the tier rule. The checker did not count 16% (Transkun V2) and 19% (Aria-AMT) of the injected wrong notes as wrong, against 2.5% to 8.3% on Disklavier playing in BL-20. The auditor followed all 6,765 injected notes. About 80% to 84% were counted. Most of the rest were left unpaired and shown as an extra note plus a missed one, and 75% to 84% of those sat more than 100 ms from the time the checker expected the written note (median 141 and 180 ms, against 12 to 13 ms for counted notes). So the main cause is the 100 ms wrong-pitch window meeting worse onset estimates on transcriptions (DF-13), not aligner absorption. A smaller group, 4% to 5%, was matched as correct to another written note of the new pitch in the same bar, a collision the injection did not avoid. The loss is broad: 21% to 24% in fast runs and 16% to 19% elsewhere.

The auditor also merged the "not heard" fragments: in 8 of the 10 transcriptions with runs, the missing passage is the ending, which supports truncated source videos. Unmerged, a cut ending shows as two or three separate items (BL-27). A future confirmation will come after a DF-12 fix, on new pieces, with a rule-relative criterion (the strong share on targeted bars at least 0.95 of R0's) and the end-to-end share tracked as a measurement of the checker.

**Other places the sources show rates above nominal:**

- **Bars without the expert check.** Where fewer than 5 experts cover a bar, the global limits apply, and on these calibration sets they run hot. Key-sensor expert bars came out at 6.8% notable-or-strong and 1.7% strong; transcribed ones at 11.8% and 3.0%. This applies to pieces with a single ASAP performance (such as Chopin Op. 10 No. 3, which is why three of the sample reports had no check), to key-sensor input on PianoCoRe-only pieces, and to any thinly covered bar.
- **Timing and tempo on transcribed references.** When PianoCoRe transcribed references were scored as if they were learners, they came out at 5.4% / 1.5% for tempo and 5.2% / 1.4% for timing, slightly above nominal. Disklavier references scored this way were at or below nominal. An earlier leave-one-out check on one piece, with 40 references as targets, gave 6.7% notable-or-strong and 2.2% strong for timing.
- **Recurring errors with few experts.** With only 2 experts in the filter and 3 takes, 1.0% of expert pseudo-take bars were promoted. That equals the strong rate itself, although promotion is meant to catch something rarer than chance.

There is also a consequence of the rule itself. These rates are per bar and per channel, and a long piece has hundreds of bars and eight channels. So even a genuine expert performance should expect some tiered bars and a non-empty practice list. The F-08b table shows 4% to 5% of expert bars notable-or-strong in tempo and timing alone. This follows from the definition. It was not measured separately for the practice list.

In the code: `calibration.py` (`EXPERT_CHECK_STRONG_MARGIN_TRANSCRIBED = 0`, `NOT_HEARD_MIN_BARS`, `NOT_HEARD_MISSED_SHARE`), `build.py` (`expert_bar_limits`, `not_heard_runs`, `ReportConfig.transcribed_strong_limits`); `scripts/calibrate_strong_tier_bl18.py`; `scripts/calibrate_strong_tier_bl18b.py`; `docs/specs/report-validation.md` sections 1, 2, 4, 5 ("BL-18 audit") and 6 (BL-18b, with "BL-18b audit"); DECISIONS 2026-09-28, after F-08c, and 2026-09-29, "BL-18 after audit" and "BL-18b after audit"; DEFECTS DF-12, DF-13.

#### Known gaps and untested assumptions

Report:

- **No learner or teacher evaluation.** No study checks that the practice items are the ones a teacher would choose, or that learners find them useful.
- **Mistakes and takes are simulated.** Correctness validation uses synthetic D-08 mistakes, and the recurring-error rule was calibrated on different pianists standing in for one player's takes (O-01 not yet recorded).
- **Design choices that were never tested.** These were set by judgement, not measured:
  - the 3-item list;
  - the category order;
  - ranking across channels by magnitude, which is relative to each channel's own limit and has no common unit;
  - the minimum of 10 references;
  - the 20% note-rate window for published evenness values.
- **Narrow calibration coverage.** The global correctness limits come from 62 pieces of (n)ASAP. The per-bar check was calibrated on 40 key-sensor performances and 5 Chopin pieces for transcribed input. Nothing is calibrated on phone audio.
- **Rates above nominal.** The BL-18 rule for transcribed input is an interim default. It met C1 to C3 on one new sample of 12 pieces but failed BL-18b by the pre-registered rule, and it is kept as a disclosed deviation. On a second sample (DF-13's 16 pieces) its clean strong rate is 1.49% and 1.86%, above the 1.25% band by point estimate, and not because of one piece, so it stays interim. The other cases listed above are not fixed.
- **Wrong notes lost on transcribed input (DF-12, DF-13, DF-15).** 16% to 19% of injected wrong notes are not counted as wrong on transcriptions, so about 7 in 10 bars with 3 wrong notes become strong. A wider pairing window was tested (DF-13) and failed: it reaches only half of the loss and adds wrong-note labels on clean playing. The rest is the aligner (re-matching and duplicate matches, DF-15), which is the next fix.
- **Phrase boundaries.** Claude's boundaries in the report are below the project's accuracy bar on Romantic pieces, untested on nocturnes, waltzes and compound metres, and cached only for the owner's five pieces, whose annotators mostly recognised the piece. The phrase-tempo finding is therefore shown with its caveats and never becomes a practice item.
- **Fast runs and fast repeats.** The bar-level wording in fast runs and the low-confidence rule for missed fast repeats rest on synthetic mistakes and on microphone recordings of a player piano; neither is validated on a learner's phone recording.
- **Command-line transcriber mix.** From the command line, transcribed input is checked against experts from any transcriber, but the calibration was per transcriber family, and Aria-AMT runs hot.
- **Mixed capture in the recurring filter.** The recurring-error filter always uses ASAP Disklavier experts, even for transcribed takes. The per-bar check deliberately avoids this mismatch; whether this filter needs the same was not tested.
- **Pieces outside ASAP.** They get no automatic expert filter, so their recurring errors are listed but never promoted unless same-score references are supplied.
- **Pedal and evenness in the app.** These are only tiered against same-score references. The app now supplies ASAP performances as same-score references, but only in limited cases: key-captured MIDI, a piece with no PianoCoRe references, and at least 10 ASAP performances left (four catalogue pieces today). For every other piece, timing steadiness is the only control finding that can be tiered. Extending this to all ASAP pieces first needs the report to stop counting a PianoCoRe copy of the same ASAP performance twice (DF-05 follow-up).

Comparison:

- **No listening test.** Nobody has confirmed by ear that the cuts are musically aligned, that switching feels seamless, or that the "typical expert" sounds typical. All checks are signal proxies.
- **Untested expert-choice settings.** These are design choices: the equal weights of tempo shape, loudness shape and tempo level; the 90th-percentile contrast; the 80% coverage rule; and the 60% note-match rule.
- **Unreliable loudness in the choice.** Loudness shape enters the expert choice even when velocity is low confidence, which is the usual case, because most references are transcriptions.
- **Rendered transcriptions.** Most expert clips are renderings of transcriptions, so their dynamics and pedalling carry transcription error, and they do not sound like the original recordings.
- **Loudness matching hides level.** A learner who plays a whole passage too loudly or too softly will not hear it in the comparison; only the shape inside the clip survives. This is deliberate, for fair listening, but it is a blind spot.
- **Render lead-in.** Notes struck more than 6 s before a clip are not rendered, so very long pedalled resonance can be cut short.
- **Assumed time base.** The learner's audio is cut on the assumption that the transcription shares its time base. The measured lag is recorded but not corrected (it was 0 ms on the five takes tested).
- **Window limits.** Windows are capped at 4 bars, so a 16-bar too-flat finding is heard only through its first 4 bars. When the window cap is reached, some practice items may have no player.

App:

- **Wrong-piece threshold.** The run stops below a match ratio of 0.5. That value rests on 5 phone takes and 4 ASAP performances, each tried against its own score and against wrong ones; an excerpt of a long piece also scores low, which is why there is an override.
- **No login.** Other programs and users on the same computer can reach the server.
- **Unscrubbed worker log.** The worker's log keeps its output, including error messages that can contain file paths. It is deleted with the job but not cleaned.
- **Only the first take has clips.** For audio input, the other takes are transcribed and used only for the recurring-error check.
- **Thin coverage for some listed pieces.** The list includes ASAP pieces with fewer than 10 PianoCoRe references. Their reports have no expert-shape findings, no timing tiers and no expert clips, although the per-bar note check may still run.
- **No hosting design.** Hosting waits on the licensing question (BL-01).


## Part 3. What we found

The experiments are grouped here by the question they answer, not by when they ran. Each result
carries its verdict after audit. "Confirmed with caveats" means the result held up under an
adversarial check but has limits that are stated alongside it.

### What do listeners actually judge?

If quality were a single number, rating it would be easy. It is not, but it is not endlessly
complicated either.

**Ratings reduce to a handful of judgements (R-01).** PercePiano is a dataset of 1,202 short clips,
each rated on 19 scales (tempo, dynamics, pedal, mood and so on) by a pool of expert raters (63 in the released data after cleaning; the paper reports 53). A
factor analysis asks how many independent judgements are hiding behind those 19 scales. The answer
is 3 to 5, depending on the method. One dominant factor behaves like general quality. The others are
loudness and energy, pedal and legato, and mood. Individual raters are noisy, but they are not using
a simpler scheme than the panel as a whole.

**Expression has a small shared core and a lot of freedom (R-02).** We took 698 pieces with 50
expert performances each and asked how many basic shapes of tempo and loudness it takes to describe
how those experts differ. The prediction was 10 or fewer. It took 19, so the hypothesis failed as
stated. But the audit found a better way to read the result. The part of expression that experts
*share*, the part that goes beyond chance, takes only 3 to 5 shapes and covers about 35 to 46
percent of the variation. The rest is individuality.

This is the most important idea in the project. An interpretation is a small shared core that
almost every skilled pianist respects, plus a large space of personal freedom. A good scoring
system should hold players to the core and leave the freedom alone.

| Experiment | Question | Answer | Verdict |
|---|---|---|---|
| R-01 | Do 19 rating scales reduce to a few? | Yes, to 3 to 5 judgements, led by general quality | Confirmed with caveats |
| R-02 | Is expert expression low-dimensional? | The shared part is (3 to 5 shapes); the whole is not (19) | Confirmed with caveats; H1 not supported |

### Can a machine predict quality on pieces it has never heard?

This is where most published work quietly fails.

**A published audio model collapses on new pieces (R-03).** CrescendAI reported that MuQ, a large
audio model, predicts expert ratings with an R² of 0.536 (R² is the share of variation in the
ratings a model explains; 0 means no better than always guessing the average). We reproduced it at
0.509. Then we tested it fairly, on pieces it had never heard in training. The score dropped to
negative 0.087: worse than guessing the average. The model had learned the pieces, not the playing.
Within a single passage it still ranks pianists correctly about 59 to 62 percent of the time, so
some real signal survives. The audit also found that the original authors' fix for this leak made
it worse, and that much of the remaining signal came from spotting flat, computer-generated
renditions.

**Simple MIDI features do as well (R-04).** A small model on 62 measurable features, with no audio
and no deep network, matches MuQ on unseen pieces in all four test variants. What drives it is
pedalling, then dynamics, then tempo shape, then voicing. The honest framing is "matches", not
"beats": both models agree with the panel only about as well as a single human rater does, and the
audit showed the achievable ceiling is much higher. There is a lot of room left.

**Expression models cannot be used as judges directly (R-06).** Expression models are trained to
generate human-like playing from a score. The obvious idea is to ask one how likely a performance
is. We compared two, SyMuPe and Pianist Transformer, on unseen pieces. They tied, and the
pre-registered tie-break chose SyMuPe for fine-tuning. The striking finding was that both models
rate flat, expressionless playing as more likely than any real pianist. Likelihood rewards the
average, and the average is lifeless. Any use of these models has to measure something else.

**Fine-tuning did not fix it (R-07).** Fine-tuning SyMuPe on thousands of PianoCoRe performances
made its predictions worse on the recordings that matter most (PercePiano, Vienna, (n)ASAP). A
likelihood ratio against a "flat playing" model looked like a working judge, until the audit showed
the test was too easy: it cannot tell a real performance from the same one with half the
expression. The preview of H1b, our bet that the score predicts what experts share, used a yardstick
that even real pianists could not reach, so it said nothing. The question moves to R-10 with a
measure whose ceiling is known.

**The score alone does not predict what experts share (R-10).** This was the project's central
bet: given the score, the part of expression that experts agree on should be predictable. We
tested it on 56 pieces the model had never seen, against a yardstick that 16 real experts reach
easily (about 0.88). The model's average performance explains only 0.15 of the experts' average
loudness curve and 0.07 of their timing. It gets the shape partly right (correlations of about 0.67
and 0.55), but even with its loudness range corrected it would explain under half. It also does no
better than a small model on simple score features, by this measure. A second model, Pianist
Transformer, did no better: it matched SyMuPe on the shape of loudness and did worse on timing. The consequence is practical:
judging interpretation needs real expert recordings of the same piece, which is how the report
already works. A model's prediction can at most be a weak hint for pieces nobody has recorded.

**Audio models can cheat on recording quality (R-05).** We rendered 1,250 performances in four
simulated recording settings. When the setting was tied to skill, as it is in real datasets, an
audio skill classifier's score rose from 0.87 to 0.94. Shuffling the settings at test time dropped
it to 0.73. The model was using the recording setting about as much as it would use a label naming
it outright. The mechanism is shown; how large the effect is on real recordings is not yet known.

| Experiment | Question | Answer | Verdict |
|---|---|---|---|
| R-03 | Does the published audio result hold? | Reproduces, then collapses on unseen pieces | Confirmed with caveats |
| R-04 | Can MIDI features match it? | Yes, on unseen pieces; both far below the ceiling | Confirmed with caveats |
| R-06 | Which expression model, and can likelihood judge quality? | SyMuPe; no, likelihood prefers flat playing | Confirmed with caveats |
| R-07 | Does fine-tuning help, and is there a usable typicality score? | No and not yet; H1b preview uninformative | Confirmed with caveats |
| R-10 | Can the score predict what experts share (H1b)? | No: 0.15 of loudness and 0.07 of timing, where experts reach 0.88 | Confirmed with caveats (H1b falsified, scoped) |
| R-05 | Do audio models use recording context? | Yes, in simulation | Mechanism shown |

### Does anything here actually measure skill?

A score is only useful if a better player gets a better one. This turned out to be the hardest thing
to show, for a reason that has nothing to do with the features.

**Pooled data says yes; matched data says "can't tell" (D-10, R-09).** In MAJEPPA, a dataset of
performances from beginner to virtuoso, advanced players look about 25 percent more controlled and
their expression follows the score's structure more closely. But every virtuoso recording is a
concert and most beginner recordings are practice clips. Compare players recorded in the same kind
of setting and no difference is shown between beginners and advanced students. The top skill levels
cannot be tested that way at all, because they only appear in concert recordings, so for them skill
and setting cannot be separated in this data. The honest verdict
is inconclusive, and the design never had much chance of reaching a firm "no".

The same checks measured what survives turning audio into notes, on 65 competition performances
that exist both as player-piano MIDI and as transcribed audio. Individual note onsets come back a
few milliseconds off (the exact spread depends on the transcription model), but the timing
*measures* built from them barely move, by about 1 percent. The reason is that expert playing
already varies by 15 to 35 milliseconds from beat to beat, and a small independent error adds very
little on top of that. Loudness is different: with the transcription model MAJEPPA uses, it is off by
about 9 MIDI units, which is at the scale of the skill effects themselves. Articulation-based
measures also fail under transcription; timing-based ones survive.

**Repeated takes: noise, not intent (F-07, BL-16).** We hoped that when a pianist plays something
twice, the part that repeats is their intent and the part that changes is noise. Across 1,390 cases
of a famous pianist recording the same piece more than once, the repeating part is indeed explained
by the score and the changing part is not. But the audit ran the same test on two recordings by
*different* pianists, and it passed too. The repeating part is timing that any two performances of
the piece share, not personal intent. What does hold is that a pianist's own take-to-take variation
is mostly random. Practice sessions from the Rach3 dataset, cut into separate takes, agree: within
one sitting the changes are close to random, about 7.5 milliseconds for advanced players and 11 for
the beginner, while across days they drift in structured ways. The practical rule is to record
repeated takes in one sitting and use their spread as a noise floor.

| Experiment | Question | Answer | Verdict |
|---|---|---|---|
| D-10 / R-09 | Do control and coherence rise with skill? | Not shown once recording context is matched | Inconclusive |
| F-07 | Do repeated takes reveal intent? | They reveal shared piece timing; own variation is noise | Confirmed with caveats, reinterpreted |
| BL-16 | What do same-sitting takes tell us? | A usable noise estimate | Confirmed with caveats |

### Can an LLM read the structure of music?

This is the most direct test of the idea that started the project: that current language models can
help with the parts of music judgement that rules cannot capture.

Phrase structure matters because almost every shaping measure needs to know where phrases begin and
end. Our hand-built rule detector was not good enough for that. So we gave Claude a text rendering of
a score, with no title, no labels and no access to the project, and asked it to mark phrase endings
and cadence types. Its marks were scored against expert annotations from the DCML corpora, and every
run was checked for leaks.

| Test | What was tested | Claude | Rule detector |
|---|---|---|---|
| R-08a | 5 well-known Mozart sonata movements | 0.82 | 0.57 |
| R-08b | The same movements disguised (new key, words removed, bars renumbered); none recognised | 0.80 | 0.57 |
| R-08c | 5 J.C. Bach movements the model did not recognise | 0.75 | 0.44 |
| R-08d | 5 Romantic pieces: Tchaikovsky, Chopin, Schumann, Grieg, Liszt | 0.74 | 0.39 |
| BL-17 | 24 Romantic character pieces, mostly Chopin mazurkas and Grieg Lyric Pieces, all disguised; no piece named | 0.64 | 0.31 |

The scores are F1 within one beat, where 1.0 means every phrase ending found with no false alarms.
Claude beats the rules by 0.25 to 0.35 in every style, and disguising the score cost it nothing, so
it is reading the notes rather than recalling a memorised analysis. On Classical and galant sonata
movements it clears the project's 0.70 target.

**Romantic music is harder than the first test suggested (BL-17).** R-08d's 0.74 rested on 5 pieces
and cleared 0.70 only on its average; its uncertainty range ran from 0.44 to 1.04. BL-17 repeated
the test on 24 pieces with two blind readings each. The verdict by its pre-registered rule is
inconclusive: the mean is 0.635, and the range the data allow, 0.549 to 0.720, still just contains
0.70, so the claim "above 0.70 on Romantic repertoire" is not made, and "below 0.70" is not shown
either. R-08d's pass is therefore not confirmed. BL-17's estimate is the better one for this kind of
music, and the two studies do not differ detectably: 5 pieces is few enough for R-08d's higher
number to be luck, and the studies also weighted composers differently. Claude still beats the rule
detector clearly, on 23 of the 24 pieces. Its errors run both ways: it tends to mark finer phrases
than the experts, and it also misses real ones: about a fifth of the expert phrase ends have no
predicted end within a bar. Single pieces range from 0.14 to 0.92. Six pieces in compound metres (6/8, 12/8) look
similar but are too few to count. And the expert labels were published before the model's training
cutoff, so exposure to them cannot be ruled out entirely.

| Experiment | Question | Answer | Verdict |
|---|---|---|---|
| R-08a to R-08d | Can Claude read phrase structure from a score? | Yes on Classical music; above the rules everywhere | Confirmed with caveats |
| BL-17 | Is it above 0.70 on Romantic repertoire? | Not shown: 0.635, range 0.549 to 0.720; clearly above the rules | Confirmed with caveats; inconclusive by its rule |

**The boundaries work downstream, with limits (F-05e).** With Claude's phrase boundaries, the
measure of whether a player shapes each phrase as slow, faster, slow again matches the result from
expert annotations on Mozart, and beats the rule detector everywhere. On Romantic pieces it loses
some accuracy to misplaced boundaries. Random boundaries at the same density score about zero,
which shows the measure is not rewarding boundaries just for existing. Claude's boundaries were
adopted for the research measure used in the skill study, and the practice report now uses them too
for pieces with a cached set (DF-02). Because they fall short of the accuracy bar on Romantic music,
the report states their measured accuracy, shows the rule detector's value beside them, and calls
the finding undetermined when the two disagree in direction. On the owner's pieces that happened for
two of the five takes. No practice item depends on this finding.

### Does it work on a real learner's phone recordings?

The final test was the project owner's own playing: five Chopin pieces recorded on a phone at a
grand piano.

**Timing is trustworthy; extra notes are not (A-01).** First we played expert recordings through a
simulated phone and transcribed them: 98 to 99 percent of notes come back, with about 2 milliseconds
of timing error. On the real recordings, the two transcription models agree closely with each other,
and wrong and missed notes sit near the level transcription alone produces. But three recordings
show 15 to 29 percent "extra" notes, many on a few fixed high pitches with no plausible source, and
neither the simulation nor real-room recordings from another dataset reproduce them.

**The phantom notes are a second melody (BL-22).** A closer look found that the high extras are not
noise at all. Almost all of them are white keys in one high octave, they move by step at about three
notes a second, and the same short phrases recur in all three affected recordings, although the
pieces are in other keys and the phrases ignore what is being played. Both transcription models hear
them, and there is real sound at each pitch. So most of these "extra notes" are a quiet, separate tune
in the recordings. Neither the phone nor the room could play a tune, and the pitches ignore the notes
being struck, which makes sympathetic ringing of the piano's strings unlikely as the main cause. The
first reading of the pre-registered tests ("a room or phone artefact") was returned by the auditor
for this reason. Where the tune comes from, in the room or added when the video was edited, is still
open, and a listening check by the owner comes next (Part 5).

**Fast repeated notes can vanish in transcription (BL-21).** On microphone recordings of a player
piano, where the true notes are known, a key struck again within about a tenth of a second is often
merged into one note by the transcriber: only a third of repeats closer than 80 milliseconds were
found, against 98 percent of other notes. Part of this is because such repeats are soft, and many of
the fastest ones look like the player piano's own key bounces rather than intended notes. Such
repeats are rare in the owner's pieces, but the report now treats a missed note there as low
confidence.

A concrete example of feedback that can be trusted: in the Nocturne in D-flat major, Op. 27 No. 2,
both transcription models flag the same two bars for timing, including a bar played about 14
percent faster than the typical expert shape.

**Stop blaming the player for the score (F-08c).** Some bars look wrong in expert performances too.
When professionals all "make" the same error, the problem is in the score file or in a playing
convention, not in the player. Bars where
expert recordings show the same "errors" are no longer flagged, and extra notes never count against
transcribed input. On the owner's reports, strong correctness flags fell from up to 30 per piece to
at most 2. To check this does not hide real mistakes, we injected synthetic mistakes into expert
performances: of the bars that were flagged before the change, about 85 percent stay flagged after
it.

**Keeping "strong" rare without hiding real mistakes (BL-18).** On transcribed input the strongest
note flag still fired more often than the intended 1 bar in 100, because with only 15 expert
transcriptions per piece, matching the worst expert was enough. The rule that won the pre-registered
test pushed the rate far below 1 percent and, in doing so, demoted nearly half of the bars with
three injected wrong notes. The auditor returned it: the test had only an upper limit, and the rule was
compensating for runs of bars where the transcription simply has no notes, which no per-bar limit can
fix. The interim rule is simpler: a bar is strong only when it has more errors than every expert
there, and a run of bars with almost every note missing is reported once as "passage not heard".

**The confirmation failed, for a reason outside the rule (BL-18b).** A fresh test on 12 new pieces
failed by its pre-registered rule. The new rule kept "strong" rare on clean playing (0.58 and 1.04
percent for the two transcribers) and kept most strong flags on injected mistakes, but only about 7 in
10 bars given three wrong notes came out strong, against a target of 95 percent. The old rule did no
better on that test, because the shortfall comes from the note checker: on transcriptions it did not
count 16 to 19 percent of the injected wrong notes, mostly because they landed more than 100 ms from
where the written note was expected (DF-12, DF-13). Whenever the checker counted all three, the bar
was strong. The registered response to a failure, going back to the old rule, was not applied,
because the old rule fails the rarity test on one transcriber (2.09 percent); that deviation is
recorded in DECISIONS. The interim rule stays, marked provisional: it meets the other three criteria
on one new sample of 12 pieces. For a learner this means that on a phone recording about 7 in 10
bars with three wrong notes are flagged strong, and fixing the checker, not the tier rule, is what
would raise that.

| Experiment | Question | Answer | Verdict |
|---|---|---|---|
| BL-22 | Where do the phantom high notes come from? | Mostly a second, independent melody; source unknown | Reading returned by the audit, then confirmed with caveats |
| BL-21 | Do fast repeated notes survive transcription? | Not below about 100 ms | Confirmed with caveats |
| F-08c | Can bars that experts also "get wrong" be excluded? | Yes, keeping about 85% of real flagged mistakes | Adopted |
| BL-18 | How should "strong" work on transcribed input? | Interim: more errors than every expert, plus "passage not heard" | Measurement confirmed; chosen rule returned |
| BL-18b | Does the interim rule hold on new pieces? | Meets C1 to C3 on 12 new pieces; about 7 in 10 three-wrong-note bars strong, limited by the checker (DF-12) | FAIL by the pre-registered rule; audited; interim rule kept as a disclosed deviation, Provisional |

**Hearing the difference (P-01).** Every flagged passage gets a player with four versions: the real
recording, the same notes re-rendered on a neutral piano, a typical expert on that same piano, and a
contrasting expert. Switching between them keeps your place in the bar, so you hear exactly what
changed.


## Part 4. How we kept ourselves honest

Research on performance scoring has a history of results that look strong and do not survive a fair
test. R-03 in Part 3 is one example. So this project was built around two habits: write down in
advance what would prove a claim wrong, and have an independent agent try to break every result
before it counts. This part explains the statistics and the process, then shows what the auditor
actually caught.


### How results are tested

This chapter explains how a number in this project earns the right to be believed: how data is
split so a model cannot just memorise pieces, how uncertainty is measured, what each result is
compared against, and which controls are needed before a pass means anything. The next two
chapters cover the listening study and the research process.

#### How do we stop a model from simply memorising the pieces?

A model that is trained and tested on the same pieces can look good for the wrong reason. It can
learn that a certain difficult piece tends to get low ratings, and then "predict" quality by
recognising the piece rather than by judging the playing. The project's answer is its first hard
rule: every claim about predicting quality or preference is tested on pieces the model never saw
in training. This is called leave-piece-out evaluation. Testing on unseen performers is also done,
but it is reported separately and never counts as a substitute. The motivation is recorded in
`DECISIONS.md` on the first day: published rating models fall from about 0.6 to about 0.2 rank
correlation when tested on unseen pieces. R-03 later showed the same collapse in this repo (log,
R-03).

The split works by giving each group, a piece or a performer, one fold number that all its rows
share. Groups are shuffled with a recorded seed, sorted from largest to smallest, and each is
placed in the fold that currently holds the fewest rows. This greedy balancing keeps folds of
similar size even when some pieces have far more performances than others; the shuffle only
decides between groups of equal size. Asking for no fixed number of folds gives one fold per
group, which is leave-one-group-out. A separate check raises an error if any group appears on
both the training and test side of any split. That check is the automatic guard against leakage,
and the auditor reruns it.

On PercePiano, the rating dataset used in R-01, R-03 and R-04, "piece" needs care. It has very few
works, and its short segments of the same passage overlap in bars. The project therefore defines
leave-piece-out there as leave-work-out. The published CrescendAI split held out passages, which
is weaker, and its later folds leak by performer. With only 4 works, results are reported per
work as well as pooled. The two movements of Schubert's D960 share all 12 human performers, so a
second version with those movements merged into one group (3 groups in total) is also required.
A claim stands only if it holds in both versions.

Holding out works creates a second problem. Average ratings differ between works, so a pooled
score across held-out works mostly measures whether a model can guess which work a segment came
from. The project therefore made within-passage measures co-primary: does the model put
different performances of the same passage in the right order?

Finally, nothing may be tuned on the test side. Settings are chosen with nested cross-validation
(a second split inside the training data) or on a fixed set of validation pieces. Picking the
best layer or seed by its test score is listed as a common failure in the experiment procedure,
and the auditor checks for it.

In the code: `src/pianolens/eval/splits.py` (`group_fold_ids`, `group_kfold`, `check_disjoint`);
rules in `CLAUDE.md` (hard rule 1) and `.claude/rules/experiments.md`; decisions of 2026-09-27 in
`DECISIONS.md`.

#### Which scores are computed, and what does a negative R² mean?

A small set of standard scores is used everywhere, so results can be compared across experiments.
All of them skip pairs where either value is missing.

R², the coefficient of determination, compares the model's squared errors with the squared spread
of the true values around their own mean. Predicting that mean for every item scores exactly 0,
and anything worse goes negative. So when R-03 reports R² of −0.087 on unseen works, it means the
model did worse than always guessing the average. The Pearson correlation measures how well
predictions line up with the truth on a straight line. The Spearman correlation does the same on
ranks, so only the order matters. Kendall's tau-b is another rank-agreement measure that handles
ties properly.

The score that matters most for PercePiano is pairwise accuracy: the share of pairs that the
prediction puts in the same order as the truth. Pairs tied in the truth are skipped, and pairs
tied only in the prediction count as half right. Given group labels, only pairs within the same
group are compared, which gives the "within-passage pairwise accuracy" used in R-03 and R-04.

In the code: `src/pianolens/eval/metrics.py`.

#### How sure are we of a number?

Every headline number comes with a 95% confidence interval: a range that, under the method's
assumptions, would contain the true value 95 times in 100. How that range is computed matters a
great deal. Performances of the same piece, by the same performer, or rated by the same rater are
correlated. A standard bootstrap, which resamples single rows, treats them as independent and
gives intervals that are far too narrow.

The project uses a cluster bootstrap. It draws whole groups with replacement, as many as there
are groups, keeps all rows of each drawn group, recomputes the score, and repeats. The default is
2,000 repetitions with seed 0, and the interval runs from the 2.5th to the 97.5th percentile of
the results. Repetitions where the score cannot be computed (for example, because a resample has
no variance) are dropped and counted, so a reader can see whether many failed. When the score is
itself computed within groups, such as within-passage pairwise accuracy, a group drawn twice gets
two different labels so its copies are not merged into one larger group. To compare two models,
a paired version applies the same resample to both and gives an interval for their difference on
identical data. Every "model A minus model B" claim in the log is made this way.

The cluster must be real. The R-09 audit found that MAJEPPA's `recording_id` identifies one video
per row, so clustering by it was a row bootstrap in disguise; the rule since then is to check that
a cluster id groups more than one row. On PercePiano, the same performers play every passage of a
work and D960 has overlapping 8- and 16-bar segments, so bootstraps there resample by performer as
well as by passage (R-06 lesson). R-06's tie-break interval was recomputed with this two-way
resampling. The auditor's memory also records a subtle trap. A cluster bootstrap of parallel
analysis (explained later) duplicates rows, and the permutation null then treats the copies as
independent. That lowers the thresholds and pushes toward retaining more factors. It is acceptable
for a claim like "never more than k factors", but must not be used to argue "at least k".

In the code: `src/pianolens/eval/bootstrap.py` (`bootstrap_ci`, `paired_bootstrap_diff`,
`bootstrap_indices`); rules in `.claude/rules/experiments.md` (R-06 and R-09 lessons).

#### What changes when there are only a handful of pieces?

Some tests have very few groups. Each R-08 test of LLM phrase annotation used 5 movements. With so
few, a percentile bootstrap is too optimistic: resampling five values cannot produce the spread
that a fresh sample of five would show. The rule since R-08a is to report a t-interval beside the
bootstrap whenever there are six or fewer groups. A t-interval treats the per-group values as a
small sample and widens the range to account for how few there are. In R-08a it changed the
story. The bootstrap interval sat above the 0.70 bar, but the t-interval, [0.696, 0.938], touched
it, so "entirely above the bar" was not claimed.

When a result lands near a bar with only five groups (R-08c lesson), three more figures are
required. The first is the mean with each group left out in turn, which shows whether one
movement carries the result. The second is the worst-run variant, which uses each movement's
weaker annotator run. The third is the one-sided p-value against the bar. After the run, the
observed spread between groups is compared with the spread assumed when the test was planned. In
R-08d it was 0.241 against 0.13 assumed. The interval was then too wide to say anything, only the
point-estimate rule decided, and the result was labelled a "fragile GO".

BL-17 is the follow-up done the other way round. Before any annotation, a simulation drawn from the
spreads seen in earlier tests showed that 24 pieces would give an interval about 0.06 to 0.10 wide on
each side: enough to decide "above 0.70" or "below 0.70" if the true mean was at least about 0.10
from the bar, and most likely "inconclusive" if it sat near R-08d's 0.737. The verdict rule was then
written on the interval, not the point estimate. The run came out inconclusive, with the planned
width (0.085) and an observed spread (0.202) inside the assumed range, so the result is informative
rather than an artefact of too few pieces. The audit added one more habit: before explaining why a
replication came out lower, test whether it is lower. BL-17 and R-08d differ by +0.103 with an
interval from -0.189 to +0.394, so sampling noise alone can explain the gap.

In the code: rules in `.claude/rules/experiments.md` (R-08a, R-08c and R-08d lessons); examples in
`experiments/2026-09-28-R-08a-llm-phrase-pilot/README.md` and the R-08c and R-08d folders.

#### Is the model as good as one human listener?

For targets rated by people, the natural yardstick is a single human rater. If a model agrees with
the panel as well as a typical rater does, it has reached "rater parity". The project's second
hard rule requires this comparison, as the ceiling, in any results table where per-rater labels
exist.

The computation is designed so that model and rater are compared like for like. For each rater,
the target is the mean of all the *other* raters on each segment that rater scored (the
leave-one-rater-out mean). A segment is used only if at least one other rater also scored it. The
rater's score is their correlation with that target. The model's score is its correlation with
the same target on exactly the same segments. Because both use the same target and segments, the
difference between them is a fair, paired comparison. Raters with fewer than 10 usable segments
are left out of the summary. Correlations are averaged through the Fisher transform, a standard
way to average correlations so that values near 1 are not under-weighted. The summary reports the
median and average for raters and model, the mean and median difference, the share of raters the
model beats, and the model's correlation with the full-panel mean. An optional bootstrap over
raters gives intervals. The model's predictions must be out-of-fold, because a model that has seen
a segment's label has an unfair advantage. The auditor checks that parity really uses a held-out
rater against the mean of the others.

R-03 and R-04 also measured parity as within-passage pairwise accuracy, and the R-03 audit found a
wrinkle. About 28% of a rater's same-passage pairs are ties, where the rater gave both
performances the same score. If ties count as half right, this caps a single rater's accuracy. So
parity is reported both ways: with ties counted as half, and on pairs the rater did not tie. The
second version favours the rater, because the pairs are chosen by that rater, so the two versions
bracket the truth.

In the code: `src/pianolens/eval/rater_parity.py` (`rater_parity`, `loo_means`, `ratings_matrix`);
the tie finding in `.claude/agent-memory/eval-auditor/r03-muq-audit-facts.md`.

#### How good could any model possibly get on these labels?

Rater parity says whether a model is as good as one person. It does not say how good a perfect
model could be, and confusing the two produced one of the first-pass overclaims (see "Where the auditor changed our minds" at the end of this part).
The tempting approach is to split the raters into two halves and measure how well one half's
average agrees with the other's. But a model is scored against the full panel's average, which is
less noisy than either half, so half-against-half agreement understates what is reachable.

The fix uses the Spearman-Brown formula, which predicts how reliable an average becomes when more
raters are added. The half-panel agreement is stepped up to the full panel, and its square root
gives the best correlation a noiseless predictor could reach against the full-panel mean. In R-04,
200 random splits of the raters gave a half-panel within-passage rank correlation of 0.374.
Stepped up, that is a full-panel reliability of about 0.54, so the attainable correlation is
about 0.74. Both models sat at about 0.35. The first-pass reading had been "little room left";
the corrected one is large headroom. The step-up treats a rank correlation as if it were a
Pearson correlation, so it is a rough extrapolation, and the README says so. The standing rule is
to report both the single-rater level and the full-panel ceiling. The same step is pre-registered
for the listening study's split-half reliability.

In the code: `experiments/2026-09-27-R-04-symbolic-percepiano/README.md` (panel split-half and
post-audit corrections); rule in `.claude/rules/experiments.md`; `study/protocol-S03.md` section
7.6.

#### What does "matches" mean, and can a pooled number hide a loss?

Several claims in this project are claims of non-inferiority: "not worse than the comparison by
more than a chosen margin". R-04's claim that interpretable MIDI features match the MuQ audio model
is one. Such a claim is only as strong as its margin, and a generous margin can make almost
anything look equivalent. So the audit rule is to report the tightest margins at which the claim
still holds. R-04 used margins of 0.02 for accuracy and 0.05 for rank correlation. It still holds
at 0.015 and 0.035, and fails at 0.01 and 0.03.

The second risk is that pooling hides a loss. With only four works, a pooled "matches" can combine
a significant loss on one work with a gain on another. That happened in R-04: the feature model
trailed MuQ significantly on D935 and led on D960's third movement, which held 47% of the rows. The
rule is to always add a per-group paired table and the unweighted mean over groups.

In the code: rules in `.claude/rules/experiments.md` (lessons from the R-01 to R-04 audits).

#### How many independent directions does the data really have?

Several hypotheses ask how many independent patterns underlie some data. H2 asks how many distinct
things PercePiano's 19 rating scales measure. H1 asks how many shapes of tempo and loudness expert
performances of one piece span. H1b builds on the answer. Counting such patterns is easy to do
badly, and the project's methods were refined by several audits.

The basic tool is principal component analysis (PCA). It finds the directions along which the
rows (performances, or rated segments) vary most, in decreasing order, and reports each
direction's share of the total variance. The H1 question, "how many components give 80%?", is
answered by adding up those shares until they reach the threshold.

A count made on the same data the PCA was fitted to is misleading. With n rows, in-sample PCA
always "explains" 100% using one fewer component than there are rows, however noisy the rows are.
The honest version fits the mean and the directions on 80% of the rows and measures how well k
directions reconstruct the remaining 20%, averaged over 5 random splits. A leave-one-row-out
version does the same one row at a time.

To tell real structure from chance, the project compares the data with nulls: fake data built to
lack the structure being tested. Phase randomisation (Theiler et al. 1992) gives each curve new
random phases while keeping its frequency content, and so its variance and smoothness. This
destroys any alignment of features across performances. When tempo and loudness curves are
analysed together, both curves of one performance get the same random phases, so their coupling
within that performance survives. A second null simply shuffles each position across rows. The
R-02 audit showed that plain phase randomisation is too easy to beat. Real performances vary more
at some places (a cadence, a climax) than others, and a phase null spreads variance evenly. The
audit added an "envelope null": phase randomisation followed by rescaling each beat to the real
per-beat spread. R-02's real count stayed below this stricter null too (19 against 24), but only
3 to 5 components per piece rose above it.

Those 3 to 5 components come from parallel analysis (Horn 1965). A component is kept only if its
variance exceeds the 95th percentile of the same-numbered component across many null copies, and
every earlier component also passed. R-01 used this as its pre-registered primary count, with
1,000 column-shuffled copies of the rating table as the null. It reported a factor-analysis
version and Velicer's MAP (a method that stops adding components when doing so no longer reduces
the average leftover correlation between items) as secondary counts. Because these methods
disagreed (4, 7 and 5), the rule became: report a count as a range across methods, and show how it
moves when near-duplicate items are merged. Merging R-01's two pedal items, which correlate 0.89,
dropped the primary count from 4 to 3.

The product code that uses this idea has two known properties. First, Horn's method undercounts
when several strong components overlap, because strong components leak into the surrogates. On
synthetic data it found 1 to 3 components correctly, but returned 1 to 2 when the truth was 4 or
5. A "sequential" variant after Green et al. (2012) exists but is not the default. Second, counts
grow with the number of rows, so the code runs parallel analysis on 5 random subsamples of 50
references and takes the median. That keeps counts comparable across pieces and with the R-02
audit, which used 50. Two counts are deliberately kept apart. The H1b test uses the R-02 audit
procedure exactly (whole piece, envelope null, 95th percentile of 20 surrogates, 50
performances), which gives 3 to 5. The report card's interpretation tier uses Horn's method on
16-bar windows, which gives about 1 to 2. Neither is substituted for the other.

Once the shared components are found, the report card needs the spread of expert performances in
that space, a covariance matrix. Estimated from a few dozen references, it is noisy and can be
nearly impossible to invert. Ledoit-Wolf shrinkage (Ledoit and Wolf 2004) pulls the estimate
toward a simple target, by an amount estimated from the data. The code shrinks the correlation
matrix and then rescales, rather than shrinking the raw covariance. The reason, stated in a code
comment, is that the coordinates have very different units (curve units against log magnitude),
and shrinking toward a scaled identity would inflate the small ones. A tiny extra diagonal term
keeps the inversion stable.

Curves are sometimes smoothed first with a Whittaker smoother (Eilers 2003), a penalised smoother
whose strength is set so that wiggles of a chosen period are halved. It uses the same convention
as the tempo model's smoothing.

One external library caused real errors. After an oblique rotation, `factor-analyzer` 0.5.1
re-sorts the factor loadings but not the factor correlations, so correlations were attached to the
wrong factors in R-01's first pass. Its communality function is wrong under oblique rotations and
produced a false "impossible value" warning. Its version check fails on scikit-learn 1.9; a small
shim fixes that and was verified not to change results.

In the code: `src/pianolens/eval/dimensionality.py` (`explained_variance_ratio`,
`n_components_for`, `heldout_r2_curve`, `loo_r2_curve`, `phase_randomize`, `column_shuffle`,
`whittaker_smooth`); `src/pianolens/features/interpretation.py` (`parallel_analysis`,
`shared_core`, `_fit_core`); `experiments/2026-09-27-R-01-percepiano-factors/` and
`experiments/2026-09-27-R-02-expression-dimensionality/`; `DECISIONS.md` (after F-06);
`.claude/agent-memory/eval-auditor/factor-analyzer-traps.md`.

#### Could the test have come out the other way?

A pre-registered test has branches, such as "supported", "falsified" and "inconclusive". If the
data can never be precise enough to reach one of them, the test is quietly rigged toward the
others, even though nobody intended it. The project calls the check for this "reachability".

The lesson came from R-09, which asked whether structural coherence rises with skill. Its smallest
effect of interest was smaller than the expected half-width of its intervals. Even if the true
effect were exactly zero, "falsified" had only about an 8% or 16% chance (for its two channels).
"Inconclusive" was the expected outcome before any data was seen, and that is how it ended. The
rule since then is to simulate or reason out the chance of each outcome at a true effect of zero
before running, write it into the pre-registration, and check afterwards that the assumptions held.

R-05 is the fullest example. Before any audio embedding was analysed, a script simulated scores on
the real sample's labels and folds, 200 times with 400 bootstrap repetitions each. It showed that
the verdict's reach depends on how strongly the scores under different conditions correlate. At
about 0.9, a zero effect usually ends "falsified" (0.85 of the time) and an effect of about +0.02
AUC is almost always detected. At 0.69, a zero effect almost always ends "inconclusive". The
README therefore reports which regime the real data fell into. BL-16 and F-05e carry similar
reachability paragraphs and post-run checks. F-07 is the cautionary case: its "falsified" branch
was close to unreachable, and the auditor flagged it as a repeat of the R-09 lesson.

In the code: `experiments/2026-09-28-R-05-context-shortcut/reachability.py`; rule in
`.claude/rules/experiments.md` (R-09 lesson); `.claude/agent-memory/eval-auditor/r09-coherence-skill-audit-facts.md`.

#### How do we know a pass means what we think it means?

A test can pass for a reason other than the one it was designed to detect. Several of the project's
most important corrections came from controls that pinned down what a pass actually showed.

F-07 tested whether a pianist's repeated takes separate intent from noise. It split timing into
the part two takes share and the part where they differ, and found that the score explains the
shared part. The auditor then ran a positive control: two recordings by *different* pianists. They
passed the same test (delta 0.097, against 0.121 for the same pianist). Whenever single recordings
have structure, the shared part of any two will be structured, so the pass said nothing specific
about the pianist. The rule is that any "shared part against difference part" contrast needs a
cross-unit control.

BL-16 refined this. A cross-pianist pair differs from a same-pianist pair in more than identity:
time between takes, tempo and noise level all differ too. BL-16 added a same-pianist pair recorded
on another day, and it was nearly as structured as a cross-pianist pair (0.011, interval −0.015 to
0.034). The apparent pianist effect was really a same-sitting effect. So a cross-unit control must
be matched on these nuisance axes. The same audit noted that R² gaps between pairs scale with each
pair's noise; one pianist's cross pairs had 1.7 times the variance of their same-pianist pairs.
Variance ratios are now reported next to such gaps.

For any score meant to measure how typical or likely a performance is, the control is a battery of
flat, expressionless versions (R-06 lesson): an exact deadpan, deadpan with velocity offset from
the conditioning, a 15% slower tempo, deadpan plus small noise, and half-deadpans (flat timing with
human loudness, and the reverse). The expression models' raw likelihood preferred every one of
them to the real performance (AUC 0.00 to 0.08), which is why raw likelihood is banned as a
quality score and any corrected score must pass the full battery.

Negative controls check the other direction. In R-05, assigning recording contexts at random,
independent of skill, should give no advantage. The pre-registration said that if it did, by an
interval lower end above +0.02, the design would be declared broken and no verdict given. It came
out at +0.002 (interval −0.004 to +0.008).

In the code: rules in `.claude/rules/experiments.md` (F-07, BL-16 and R-06 lessons); the experiment
folders `experiments/2026-09-27-F-07-H5-intent-vs-noise/`, `experiments/2026-09-28-BL-16-rach3-takes/`,
`experiments/2026-09-27-R-06-expression-model-h2h/`.

#### Could boundary density alone fake a phrase result?

Several measures depend on where phrases begin and end, for example the "slow-fast-slow" tempo arc
measure that the LLM's phrase boundaries now feed. Such measures can be moved by the number of
boundaries alone. More boundaries might raise or lower a score whether or not they are in the
right places. F-05e introduced two controls that every boundary-based measure now gets.

The first control places random boundaries at the same density as the method being tested. If
random boundaries score as well, placement does not matter. In F-05e they scored about zero
(−0.032 at note onsets, +0.006 at downbeats), and higher density did not raise them. The second
control takes the reference boundaries and halves every segment. This shows how the measure treats
a segmentation that is correct but finer. In F-05e halving cost −0.333, so the measure penalises
over-segmentation. "Recovered" therefore means recovered at the reference's phrase level. The ratio
of predicted to reference boundary counts is reported next to the measure, so a reader can see
whether a low score comes from finer phrases or from misplaced ones.

In the code: `experiments/2026-09-28-F-05e-llm-phrase-measures/README.md`; rule in
`.claude/rules/experiments.md` (F-05e lesson).

#### How big is a shortcut, really?

R-05 asked whether an audio skill model uses the recording context, such as phone in a room versus
concert hall, as a shortcut for skill. It does. The harder question is how much, and the audit
showed that the obvious answer was misleading.

The recording context could be read from the audio embedding with 0.997 balanced accuracy. When a
nuisance variable is that easy to read, the confounded model's advantage mostly reflects how
strongly context and skill are tied in the data, not anything particular about the audio model. To
measure that, the audit built an explicit-label ceiling: a stacked model that combines the matched
model's score with a one-hot label of the context (a column per context, set to 1 for the right
one), fitted on inner out-of-fold scores. Appending the label directly to the embedding under the
same penalty would be wrong, because the penalty shrinks the label's weight. The stacked ceiling
reached 0.959 (0.705 with contexts permuted), against the confounded model's 0.943 (0.730). The
model sat near the ceiling, so R-05 claims only the direction and mechanism of the shortcut, not a
size that would carry over to real recordings.

Two related rules came from shortcut work. When repertoire tracks the label, a within-piece AUC is
also reported. R-05's inflation was +0.073 pooled but +0.122 within piece, because harder pieces
lift the matched baseline. And when a comparison between pooled and context-matched data also drops
part of the range, as R-09 lost the top two skill levels, the pooled model is also reported on the
matched sample's levels only. Otherwise "the effect disappears when context is fixed" cannot be told
apart from "the effect needs the top levels".

In the code: `experiments/2026-09-28-R-05-context-shortcut/` (`analyze.py`, README Audit); rules in
`.claude/rules/experiments.md` (R-05 and R-09 lessons).

#### How do we turn "A beat B" judgements into a scale?

The planned preference studies will collect judgements of the form "I prefer performance A to
performance B". To analyse them, those choices must become a single score per performance. The
Bradley-Terry model does this, and it is built but has not yet been fitted to real judgements.

The model gives every item a strength. The chance that one item beats another is the logistic
function of the difference in their strengths, so only differences matter, and the strengths are
centred to average zero. They are fitted by maximum likelihood with the L-BFGS optimiser. A small
ridge penalty (0.0001) is added for two reasons. Without it, an item that wins every comparison
would get an infinite strength. And if the comparisons split the items into groups that never meet,
there would be no single scale. The penalty keeps the fit finite and pins the scale. Setting it to
zero gives the plain estimate, which requires every item to be connected to the others and no item
to be undefeated or winless. Comparisons can carry weights, so repeated pairs can be counted once
with a count. The model is tested by held-out accuracy: the share of unseen (winner, loser) pairs
that the scale orders correctly. Equal scores count half, and an item never seen in training gets
the average strength.

In the code: `src/pianolens/eval/bradley_terry.py` (`fit_bradley_terry`, `BradleyTerry`).

### The listening study

Every measure in Part 2 says how far a performance is from something. None of them says how much
that distance bothers a listener. This chapter describes the study built to find out: how its
sounds are made, what listeners do, and how their answers will become a verdict.

#### Why do we need listeners, and on what scale can different flaws be compared?

The feature code measures deviations in milliseconds, MIDI velocity and beats. Nothing in the data
says whether 10 milliseconds of uneven timing bothers a listener more or less than a few velocity
units of flattened dynamics. H6 claims that each kind of change has its own perceptual cost, and
that the costs differ enough to justify weighting features unequally. Only listeners can test it.
The perceptual cost study (ticket S-03) is fully designed and built. No listener has taken it, and
its protocol is marked as a draft pre-registration, not yet frozen.

Because the dimensions have different physical units, "the cost curves differ" needs a shared axis.
The primary axis is detection-threshold units: each change is expressed as a multiple of the
smallest change listeners can reliably detect in that dimension. The question becomes whether, at
equal audibility, one kind of change costs more preference than another. If costs per threshold
unit are equal, a scorer can weight every feature by audibility alone (one over its threshold), and
H6 is falsified in its useful sense. If they differ, dimension-specific weights are justified. This
axis is a design choice, provisionally approved by the lead and final only when the pilot freezes
the protocol. Other axes are run as robustness checks.

In the code: `study/protocol-S03.md` sections 1 and 2; `DECISIONS.md` (after S-01 / S-03).

#### How do we make a performance worse in exactly one way?

To measure what a flaw costs, the study plays listeners an expert performance next to a copy that
is worse in one respect only, at graded strengths. The degradation generator (ticket S-01) makes
those copies. It starts from an expert performance with exact timing (Disklavier or key-sensor
recordings only) and its note-by-note alignment to the score, and changes one dimension by a
controlled amount. Every result records the control value, the change actually measured on the
output in physical units, and, where the literature gives an audibility threshold, the ratio of the
change to that threshold. Where none exists, the result says so. Output performances are tagged as
synthetic.

| Dimension | What changes | Control | Published audibility reference |
|---|---|---|---|
| Timing jitter | random onset shift per chord, as a share of the local gap between notes, or in ms | `cv` or `sd_ms` | IOI spread 10.22 ms at 8 notes per second, CV about 0.08 (van Vugt et al. 2013) |
| Tempo flattening | the smooth tempo curve pulled toward constant tempo | `alpha` (0 unchanged, 1 constant) | none |
| Dynamics flattening | the loudness contour pulled toward the mean, melody balance kept | `alpha` | velocity JND 2.71 to 4.48 MIDI units (Slade et al. 2023) |
| Voicing | the melody-accompaniment loudness gap scaled | `k` (1 original, 0 none, −1 inverted) | same JND |
| Pedal blur | sustain pedal held across harmony changes | share of changes, or how late the pedal change comes | none |
| Articulation | key-down durations scaled | `factor` (below 1 is more detached) | none |
| Wrong notes | wrong pitches (neighbour keys, a few octaves), timing and loudness kept | `rate` | none |

Here IOI (inter-onset interval) is the time from one note start to the next, CV is a spread divided
by its mean so that relative jitter can be compared across tempi, and JND means just-noticeable
difference.

Most of the design effort went into keeping the dimensions separate, so that a change in one does
not leak into another.

Timing jitter moves all notes of a chord together, because spreading a chord is a different
dimension. Note ends move with note starts, so durations are unchanged, and each pedal event moves
with the chord it follows. Shifts are drawn from a normal distribution cut off at 0.45 of the
smaller neighbouring gap, so notes never change order. Where that bound bites, the code counts the
cases and reports the spread actually achieved. Because neighbouring intervals share a shift, onset
jitter of a given spread adds about 1.41 times (the square root of 2) as much spread to the
intervals. Van Vugt's 10.22 ms interval threshold therefore corresponds to about 7.2 ms of onset
jitter at 8 notes per second. That threshold was measured on even scales; in expressive music it is
a lower bound, not a norm. Most excerpts run at 2 to 8 positions per second, so the threshold ratio
uses the relative (CV) version.

Tempo flattening warps time. Each moment is moved part of the way, set by `alpha`, from where it
really falls toward where it would fall at a constant tempo with the same total duration. Every
event (note starts, note ends, pedal) passes through the same warp, so articulation and pedalling
stretch with the local tempo. The fine timing left over after the smooth tempo curve is kept in
beats.

For loudness, each matched note's velocity is split into three parts: the performance's average, a
voicing part and the rest (the dynamic contour, accents and noise). Melody notes are the score's
"skyline": the highest pitch starting at a given moment, provided no higher note is still held. The
local melody-accompaniment gap is a Gaussian-weighted average over about one bar. The voicing part
is built so that its local average is near zero, which means scaling it changes balance but not
overall loudness. Dynamics flattening scales the rest; voicing scales the voicing part. Results are
rounded and clipped to the MIDI range, and clipped notes are counted. The JND reference was measured
on a Disklavier, not on the study's sampled piano, so threshold ratios for loudness are approximate.

Pedal blur uses the project's harmony-change detector and its blur rule: a harmony change is blurred
if the pedal is down, with no lift, from a quarter beat before the change to half a beat after it.
To blur a change, the generator holds the pedal from a quarter beat before until a chosen number of
beats after, then inserts a late pedal change: a lift, and 60 ms later a return to the pianist's own
pedal state. The study-designer's notes record why the lift is essential. Without it, the blur ran
on until the pianist's next lift, and the chosen hold length had no effect. The study's short clips
contain very few harmony changes, so grading by the share of changes blurred is useless there. The
study instead blurs every cleanly pedalled change and grades by how late the pedal change comes.

Articulation scales every key-down duration, clipped so a key never overlaps the next start of the
same pitch and never lasts less than 20 ms. Where the pedal is down, shorter key-down times are
partly masked by the sustain, and the output reports the share of time the pedal is down. Wrong
notes change pitches only, using the same generator as the synthetic mistake set, so correctness
varies alone. In short clips, an option forces one wrong note when the chosen rate would round to
none.

In the code: `src/pianolens/study/degrade.py` (`degrade` and one function per dimension);
`.claude/agent-memory/study-designer/s03-build-notes.md`.

#### Which passages do listeners hear, and how is sound quality kept from being a cue?

The stimuli are eight short passages, each cut into a detection clip and a longer preference clip.
They come from Vienna 4x22 and Batik (key-sensor recordings) and from (n)ASAP/MAESTRO (Disklavier),
all with ground-truth alignment. Listeners see only the codes E1 to E8, never a composer, title or
performer. Where a source has several performances of a passage, the one with the median overall
tempo is used, which avoids extreme interpretations without anyone choosing by ear. On the pilot
build, detection clips last 5.9 to 9.0 seconds and preference clips 12.8 to 18.5 seconds.

Excerpts are cut by score bars through the alignment, not by fixed seconds. A clip starts at the
earliest played note in its first bar and ends at the median start of the first beat of the
following bar. Notes still held at the end are cut one second later. The pedal state at the start is
carried in, and the pedal is lifted at the release. Times are shifted so the first note sounds a
quarter second into the clip, and the score is cut to the same bars so that any analysis of the
excerpt sees only those bars. The build degrades each excerpt after cutting it, so the dose is exact
within the clip. Degrading the whole piece first gave zero wrong notes in short clips and pedal
changes outside the clip.

Sound quality must never hint at which version is which. Every clip is rendered by the same
pipeline: the Salamander C5 Light sampled piano in FluidSynth 2.6.1 with fixed settings, mono, at
44.1 kHz. Each clip is faded in and out and then normalised to −23 LUFS, a standard measure of
perceived loudness (ITU-R BS.1770). This matters because flattening dynamics changes the raw level.
The pilot build has 592 clips, none clipped, and its manifest records the render settings, the
soundfont's fingerprint, the synthesiser version and the code state.

Each dimension has an "analysis level", the number the statistics use, fixed before any data:

| Dimension | Analysis level |
|---|---|
| Timing jitter | added interval CV, measured |
| Tempo flattening | rubato removed: spread of log tempo before minus after |
| Dynamics flattening | root-mean-square velocity change per note, measured |
| Voicing | change in the melody-accompaniment gap, measured |
| Pedal blur | mean added hold in beats, measured |
| Articulation | log2 of one over the scaling factor |
| Wrong notes | wrong notes per note, measured |

For the main study, the build finds, for each excerpt, the control value that reaches each target
level by bisection (repeatedly halving the search range), which works because the level grows
steadily with the control.

Three limits were measured on the pilot build. The harmony detector finds 0 to 6 changes per
detection clip and 1 to 11 per preference clip, and three detection clips (E2, E5, E7) have none,
so pedal detection trials use the other five excerpts. Articulation is partly masked where the pedal
is down, which covers between 0 and 96% of a preference clip. Voicing doses vary between excerpts
because the original gaps vary (4.5 to 27.9 MIDI units), which is why the analysis level is the
measured gap change rather than the control value.

In the code: `src/pianolens/study/excerpt.py`; `scripts/build_study_s03.py`;
`study/stimuli-S03.json`; `study/protocol-S03.md` section 3.

#### What does a listener actually do?

A session runs in a fixed order: consent, five background questions, setting the volume on one
original clip, a headphone check, Part A, then Part B, and a debrief after which the participant
downloads a file of their answers. The headphone check (Woods et al. 2017) plays three low tones,
one of them quieter and one played in opposite phase between the two ears, and asks which is
quietest. The opposite-phase tone sounds quiet on loudspeakers but not on headphones, so the check
catches speaker listening. There are six questions, a pass needs five, and one retry is allowed.

Part A measures detection. Each trial plays the original, then two clips, A and B. One of them is the
original again and the other is degraded, and the listener says which one differs. Guessing gives
50%. Each clip plays once, and answers unlock only when the last clip ends, so response time is
measured from that moment. The main study uses the method of constant stimuli, meaning levels are
fixed in advance rather than adapted to the listener: four levels per dimension, at the pilot
threshold times 0.5, 1, 2 and 4, three trials each, for 84 trials. Four catch trials use a grossly
wrong-note version to check attention, and three practice trials give feedback.

Part B measures preference. Each trial plays the original and a degraded version, and the listener
says which they prefer. There are three levels per dimension, at the threshold times 2, 4 and 8
(capped at the largest level a dimension allows), two trials each, for 42 trials. Seven identical
pairs, the original against itself, measure how much listeners favour the second item when there is
nothing to hear. Two catch trials and one practice trial complete the part.

Three kinds of balancing keep the design fair. Listeners are known to favour the second of two
items (Kroger and Margulis 2017), so within each dimension the degraded clip comes first in half the
trials and second in the other half, and position is also modelled. Each listener walks through
their own random order of excerpts, so every excerpt meets every level across listeners, and clips
identical to their original are skipped. Trial order is shuffled with a random generator seeded by
the participant code, so any session can be reproduced exactly; catch trials are spread evenly, and
the same excerpt is not played twice in a row where that can be avoided. Part A takes about 37
minutes of listening and Part B about 25, so the recommended format is two sessions of 40 to 45
minutes.

In the code: `study/app/design.js` (trial builder); `study/app/app.js`; `study/protocol-S03.md`
section 4.

#### Who takes part, and whose answers are set aside?

Listeners are recruited in two groups of about equal size: musicians and non-musicians, by their own
description plus years of formal training. The H6 test pools both groups, and each group is also
analysed alone, because expertise may change what people notice. Participants must be 18 or older
and listen over headphones.

Three exclusions are fixed in advance and applied before anyone looks at the test trials:

- failing the headphone check on both attempts;
- getting fewer than 5 of the 6 catch trials right (in Part B, "right" means preferring the
  original);
- completing fewer than 80% of the test trials.

Listeners who report a hearing difficulty are kept, and the main analysis is repeated without them
as a check.

In the code: `study/protocol-S03.md` section 5.

#### How are listeners' answers turned into a verdict on H6?

The analysis has two stages. The first finds each dimension's detection threshold. The second
measures how much preference each dimension costs per threshold unit and asks whether those costs
differ.

A psychometric function is the curve that links the strength of a change to the chance of noticing
it. The detection fit assumes the chance of a correct answer is 0.5 plus (0.5 minus the lapse rate)
times a logistic curve of the log2 level. The threshold is the level at the curve's midpoint, which
is about 74% correct with a 2% lapse. The guess rate is fixed at one half, because there are two
choices. The lapse rate (mistakes from inattention even on easy trials) is fixed from the catch-trial
error rate rather than estimated, since the test trials alone cannot separate lapses from difficulty.

One listener's trials are not independent: a sharp listener is sharp on every trial. Ordinary
standard errors would treat each trial as new information and come out too small. Both fits
therefore use a cluster-robust ("CR1 sandwich") estimator, which judges uncertainty by how much each
listener's total contribution varies, with a small-sample correction based on the number of
listeners.

Preference is modelled with a logistic regression: the log-odds of choosing the original equals a
position term plus, for each dimension, a cost slope times the level in threshold units. The
position term is +1/2 when the original is second and −1/2 when it is first. The cost slope is the
quantity H6 is about. The model has no intercept, because identical pairs carry no preference; they
estimate the position bias alone. A tiny ridge penalty keeps the fit finite if some dimension is
chosen perfectly. The per-level preference curves, with intervals from 2,000 resamples of
listeners, are the study's descriptive "cost curves".

Each cost slope inherits the uncertainty of its threshold, since the level is divided by the
threshold. The delta method, a first-order way to pass uncertainty through a formula, adds that
share to the slope's variance. It covers the variance only, not a psychometric curve of the wrong
shape.

The verdict follows a reading fixed in advance, with a margin of 2: a two-fold difference in cost
per threshold unit is taken as the smallest difference that would change how a scorer weights
features.

- **Supported** if a Wald test (a joint test of whether several estimates are all equal) rejects
  "all seven slopes equal" at p below 0.05, and at least one ordered pair of dimensions has one
  slope more than twice the other at a one-sided level of 0.05 divided by 42. The division is a
  Bonferroni correction for the 42 ordered pairs of 7 dimensions.
- **Falsified** if every ordered pair is shown to be within a factor of 2 at a one-sided level of
  0.05. This is the "two one-sided tests" approach to showing equivalence. No correction for many
  tests is needed, because every one of them must pass.
- **Inconclusive** otherwise.

Several robustness analyses are reported but do not decide the verdict: a bootstrap of the whole
pipeline over listeners; a mixed model with listener and excerpt effects; the same test on the
physical axis without threshold normalisation; the same test on an "expert spread" axis (the level
divided by how much that feature varies across expert performances of the passage); dropping each
excerpt in turn, which is the study's version of leave-piece-out; dropping listeners with hearing
difficulty; and letting the lapse rate be estimated. Differences between musicians and
non-musicians are tested by adding group terms, but the study is not powered for per-group verdicts,
so those are descriptive. Reliability is measured by splitting listeners in half 1,000 times and
stepping the result up with Spearman-Brown, and by the pilot listener's repeat session. A dimension
whose threshold falls outside the tested range is reported as such and left out of the H6 test.

In the code: `src/pianolens/study/psychometric.py` (`fit_detection`, `fit_logit`);
`src/pianolens/study/power.py` (`h6_verdict`); `study/protocol-S03.md` sections 2 and 7.

#### How many listeners are needed?

No published study gives the numbers needed to calculate this study's sample size directly, so the
project simulates whole studies. Simulated listeners get their own thresholds and cost slopes and
answer every trial of the real design. Each simulated dataset is analysed exactly as pre-registered,
the H6 reading is applied, and this is repeated 200 times per setting to count how often each
verdict comes out. The script records its seed and command.

Every input to the simulation is an assumption, not a measurement:

| Assumption | Base value | Also tried |
|---|---|---|
| Steepness of the detection curve (per log2 of level) | 2 | 1 |
| Spread of log2 threshold between listeners | 0.5 | 0.25, 0.75 |
| Spread of log2 threshold between excerpts | 0.3 | not varied |
| Lapse rate | 0.02 | not varied |
| Cost slope per threshold unit (log-odds) | 0.4 | 0.2, 0.8 |
| Spread of cost slope between listeners | 0.2 | 0.4 |
| Bias toward the second item (log-odds) | 0.3 | not varied |
| Pilot places the level ladder correctly | yes | off by a factor of 2 |
| H6 margin | 2 | 1.5 |

The results, from the protocol, use "ratio" for the true cost of one dimension relative to the other
six; a ratio of 1 means H6 is false. Design A2 is the main design described above, and B2 doubles
every trial count by using two sessions per part.

| Design | Listeners | Chance of "supported" at ratio 3 | Chance of "supported" at ratio 1 | Chance of "falsified" at ratio 1 |
|---|---|---|---|---|
| A2 | 48 | 0.44 | 0.000 | 0.05 |
| A2 | 96 | 0.92 | 0.000 | 0.52 |
| A2 | 160 | 0.98 | 0.000 | 0.85 |
| B2 | 48 | 0.84 | 0.000 | 0.20 |
| B2 | 96 | 0.99 | 0.000 | 0.83 |

Under the base assumptions, detecting a three-fold difference needs about 96 listeners in A2 (48 to
128 across the variants) or 48 in B2. Being able to falsify H6 when costs are truly equal needs about
160 listeners in A2 or 96 in B2. A true ratio of exactly 2 equals the margin, so by construction it
is rarely "supported". False positives stayed at or below 0.02 in every variant. A large cost slope
turned out to hurt power, because the strongest level then sits near the top of the logistic curve,
so the pilot must not place preference levels too high.

The protocol's baseline recommendation is 96 listeners, 48 per group, knowing that this is powered
only for a large difference. The lead's recommendation favours B2 as the cheapest way to also be able
to falsify. Either way, the first 12 recruited listeners form an internal pilot that is used only to
re-estimate the spreads and slopes, never to look at the H6 comparison. The pre-registered rule is
that the sample size may go up after this, never down, and the internal-pilot listeners stay in the
final analysis. This stops the sample size from being tuned to the answer.

In the code: `src/pianolens/study/power.py` (`Assumptions`, `simulate_once`, `power_table`);
`scripts/power_s03.py`; `study/protocol-S03.md` section 6.

#### How does the study get from draft to frozen plan, and what does the app do?

The study cannot be frozen until its level ladders are set, and the ladders depend on thresholds
nobody has measured yet. So Henry acts as subject zero. He knows what the dimensions are, so his data
are not naive, and they are used only to set the ladders, never in the main analysis. He first
listens to each passage's original and strongest degradation and logs any artefacts, such as clicks,
stuck notes or a change that sounds like the wrong dimension. He then runs a pilot mode with five
levels per dimension, and repeats Part A on another day to measure test-retest reliability. His
fitted thresholds set the main ladders. At that point the protocol is updated, its sha256
fingerprint is recorded in `DECISIONS.md`, and the experiment folder is created. Any later change
goes into a "Deviations" section, never into the frozen text.

The study app is plain HTML and JavaScript with no server. It loads only local files and sends
nothing over the network. Answers are kept in the browser's local storage so a session can resume,
and the participant downloads a JSON file at the end; declining consent clears the storage. The app
can run the pilot or the main design, either part alone for split sessions, or an automatic test
mode with simulated answers and no audio. A smoke test serves the repository on the local machine,
runs the app in headless Chrome in that test mode, and checks that every trial was answered, that the
counts per dimension and level match the design, that positions are balanced, and that catch trials
are present.

The app collects as little as possible: a random participant code; the five background answers; the
headphone-check answers; for each trial, the clips, the answer and the response time; the day of the
session; and version strings. It collects no name, email, age (only a checkbox confirming 18 or
older), location, IP address or browser details. Consent wording, ethics review, payment, hosting
and recruiting are Henry's decisions. Agents draft these; they do not launch anything.

In the code: `study/app/` (`index.html`, `app.js`, `design.js`, `smoke_test.py`);
`study/protocol-S03.md` sections 8 to 12; ticket O-02 in `WORKBOARD.md`.

#### What comes after: the pairwise preference studies

H7 asks whether, among good performances, blind listener preference is explained by interpretable
features, beyond simple "closeness to the average expert". Testing it needs a dataset that does not
yet exist: many listeners comparing performances of the same passages. Three tickets describe it,
and none has been started.

The first (S-04) selects stimuli: the same passages played at different skill levels, from expert
recordings, aligned amateur recordings, the Expert-Novice set and Henry's own playing, all rendered
with the one fixed piano so that recording quality cannot be a cue. The second (S-05) builds a
pairwise app, possibly with adaptive pair selection, which chooses the next pair from earlier answers
to use listeners' time efficiently. The known risk, Bramley's caveat, is that adaptive selection can
inflate the apparent reliability, so if it is used, reliability must be measured on a set of
non-adaptive pairs. The third (S-06) fits a Bradley-Terry scale and regresses it on the features.

The standing requirements for any such study are set in advance:

- audio only, with no performer names or labels such as "professional", since labels and visuals are
  known to change judgements (Tsay 2013; Kroger and Margulis 2017);
- presentation order counterbalanced, and comparisons only within the same passage;
- musicians and non-musicians analysed separately as well as together;
- at least 20 comparisons per item on average, so total judgements at least 10 times the number of
  items;
- scale-separation reliability of at least 0.8 (a measure of how well the fitted scale separates
  items relative to its own error), plus split-half reliability.

The comparisons target was corrected once. The first research pass said 12 to 17 comparisons per
item give reliability of 0.70 to 0.80. A later methods check found this unsupported by its cited
sources. The corrected sources give 10 to 14 comparisons for 0.70 and 26 to 37 for 0.90 (Verhavert
et al. 2019), and the target was raised to 20.

In the code: `WORKBOARD.md` (S-04 to S-06); `.claude/rules/study.md`;
`docs/plans/2026-09-27-research-program.md` (Phase 4); `DECISIONS.md` (correction after L-03).

### The research process

This chapter covers how the research itself is run: the hypotheses, the habit of writing down the
test before running it, the agent whose job is to break results, and the lessons that became
standing rules. The last subsection lists what in this part has never been tested.

#### What exactly is being tested, and where does each hypothesis stand?

The research program states nine hypotheses, each with the result that would falsify it. The table
gives each claim in plain words and its status as recorded in `EXPERIMENTS.md`, `DECISIONS.md` and
`STATUS.md`.

| ID | Claim | Falsified if | Status |
|---|---|---|---|
| H1 | Expert expression across performances of one piece is low-dimensional: 10 or fewer components give 80% of tempo and loudness variation. | More than 20 components on most pieces | Not supported and not falsified (R-02). Median 19 components; 35% of pieces need more than 20. The audit refined it: the part experts share is 3 to 5 components (about 35 to 46% of the variance), the rest is individual. |
| H1b | Added after R-02. Given the score, a model can predict at least 50% of the held-out variance of the *shared* expert part on unseen pieces. | 20% or less | **Falsified (R-10, 2026-10-06, scoped to frozen SyMuPe).** On 56 fresh pieces the model's average curve explains 0.15 of the experts' loudness consensus and 0.07 of their timing (16 experts: about 0.88). Even with its loudness amplitude corrected it would explain at most 0.45 / 0.31. The score alone predicts only part of what experts share. |
| H2 | PercePiano's 19 rating scales collapse to 3 to 5 factors. | Parallel analysis keeps more than 8 | Supported with caveats (R-01). Primary count 4; the range across methods is 3 to 7. |
| H3 | Interpretable MIDI features match or beat MuQ audio embeddings on unseen works. | Worse by more than 0.05 R², with non-overlapping intervals | Supported as "matches", not "beats" (R-04). Both are at single-rater level, far below the ceiling. |
| H4 | Structural coherence separates skill levels. | No steady relation with skill | Inconclusive (R-09). "Falsified" was barely reachable, and the top skill levels are confounded with recording context. |
| H5 | Repeated takes separate intent from noise. | Consistent and inconsistent parts equally explained by the score | Passes as registered, but reinterpreted (F-07): a cross-pianist control also passes, so the consistent part is shared piece timing, not intent. What is supported is that a pianist's own take-to-take variation is mostly noise, within one sitting (BL-16). |
| H6 | Each dimension has its own perceptual cost curve. | Curves indistinguishable | Untested. The study is built, not run (O-02). |
| H7 | Preference among experts is explained by features beyond distance to the mean. | Features add nothing beyond distance to the mean | Untested. Needs S-04 to S-06, none built. |
| H8 | Audio skill accuracy partly reflects recording context. | Accuracy unchanged when context is fixed | Supported on simulated contexts (R-05): the mechanism is shown, but the size does not transfer to real audio. A real-audio test needs Henry's decision on re-fetching MAJEPPA's audio. |

R-03 also tested a reproduction target labelled H3a, reproducing CrescendAI's published number before
testing on unseen works. It reproduced by its pre-registered rule, by a thin margin.

In the code: `docs/plans/2026-09-27-research-program.md` section 2; `EXPERIMENTS.md`; `STATUS.md`.

#### How do we stop ourselves from moving the goalposts?

The easiest way to fool yourself in research is to decide what counts as success after seeing the
results. Pre-registration prevents this: before running anything, the experimenter writes down the
question, the data, the splits, the baseline and ceiling, the method, the exact command, and above
all the "Falsified if" criterion. Results, a provisional verdict and a section on threats to
validity are added afterwards, below that header.

A written plan only helps if later edits can be detected. The project fingerprints the header with
sha256, a hash that changes if a single character changes, and stores it in the README or in a small
file beside the results. Nothing in the repository has been committed to git yet, so git history
cannot prove when the header was written. The auditor instead retrieves the agent's original
file-write from its transcript log, hashes it, checks its timestamp against the first step that
touched data, and compares it with the first lines of the current README. The auditor's memory holds
the recipe for each experiment, including small traps such as a trailing newline (R-09) or a blank
separator line left out of the hash (R-05).

Several rules keep the practice honest. "Falsified if" is never edited after results; if it was
wrong, a new section says so. The hashed header is never touched, and the audited verdict is written
in the Verdict section instead, which is why some READMEs still say "Provisional" near the top after
an audit. Anything added after results were seen, such as a feature, a variant or a filter, is
disclosed, and the claim is refit without it; R-04's verdict was rechecked without two note-rate
features added late. Seeds, the code state, data versions and the exact command are recorded. The
pre-registered reading is applied word for word, looking at where the whole interval lies: in R-06,
an interval entirely below 0.5 was first called "inconclusive", but by the registered rule it is a
fail. Departures from the plan are disclosed rather than hidden, such as R-08a using five annotators
instead of one, or BL-16 ordering takes by note onset instead of file order.

In the code: `.claude/skills/run-experiment/SKILL.md`; `.claude/rules/experiments.md`;
`artifacts/prereg_sha256.txt` in several experiment folders; `.claude/agent-memory/eval-auditor/`.

#### What do the verdict labels mean?

Every result carries a label that says how far it has been checked. A result starts as
**Provisional**: the experimenter's own reading against the pre-registered rule, which is one of
supported, not supported or inconclusive. It becomes **Confirmed** only when the eval-auditor has
tried to break it and failed. **Confirmed with caveats** means it holds by the registered rule, but
the auditor found limits on what it means; the caveats are part of the result, not footnotes. Most
audited experiments have ended with this label. **Returned** means the auditor sent it back with
required fixes. Two results were returned: BL-18's chosen rule, whose measurements were confirmed but
whose selection overcorrected, and BL-22's reading, where the numbers stood but the pre-registered
label ("room or phone artefact") was replaced by a narrower one after the audit found a melody.

The wording inside a verdict is controlled as carefully as the label. "GO by the point-estimate
rule" is a weaker statement than "the interval lies above the bar". "Matches" is not "beats".
"Reinterpreted", as in F-07, means the registered test passed but a control changed what the pass
means. For important results, the lead records the exact headline sentence in `DECISIONS.md`, as was
done for R-04.

In the code: `.claude/rules/experiments.md`; `.claude/agents/eval-auditor.md`; `EXPERIMENTS.md`.

#### Who tries to break the results?

The eval-auditor is an agent whose only job is to break claims. It reads code, reruns commands and
tries to show that a result is wrong, leaky or overstated. It does not write features or models. It
works through a fixed checklist:

1. Did "Falsified if" change after the results?
2. When the folds are rebuilt, does any piece cross from training to test?
3. Was any normaliser, expert-average curve, PCA basis or scaler fitted on data that includes the
   test fold?
4. Was a layer, seed or setting chosen by its test score?
5. Is the trivial baseline present, and is rater parity computed against the average of the *other*
   raters?
6. Are intervals bootstrapped over the right unit, and is the sample size reported?
7. Does the headline number reproduce from the recorded command, within the stated tolerance?
8. Does the verdict actually follow from the table?

It writes an audit section into the experiment's README, sets the verdict and updates the index. In
practice audits went beyond the checklist. They ran controls the experimenter had not planned: the
cross-pianist test in F-07, the other-day pair in BL-16, the stacked ceiling in R-05 and the envelope
null in R-02. They also checked blinding by reading every LLM annotator's transcript for file access.
The table at the end of this part lists where audits changed a headline.

In the code: `.claude/agents/eval-auditor.md`; `.claude/agent-memory/eval-auditor/`.

#### Who does the work, and how does knowledge carry over between sessions?

The project is run by a lead session and a set of role agents, each with a narrow job:

| Agent | Owns |
|---|---|
| Lead session | planning, tickets, dispatching agents, merging work, decisions, status and the log |
| `data-engineer` | downloads, loaders, the dataset register, data quality |
| `feature-engineer` | alignment, error labels, the tier A to D features |
| `ml-researcher` | experiments and models |
| `eval-auditor` | adversarial review before any result is Confirmed |
| `lit-scout` | the literature map, and checking claims against sources |
| `audio-engineer` | transcription and loudness calibration |
| `study-designer` | the listening studies |

Agents claim tickets and work only inside the paths their ticket names. Some tickets are reserved
for Henry: anything that spends money, touches credentials, rents GPUs, recruits listeners or uses
his own recordings. Agents never commit to git unless he asks.

Agents do not remember previous sessions on their own, so each keeps a memory file that is loaded at
startup. It is an index of at most 150 lines, one line per note, with details in topic files beside
it. Agents save what the documentation lacks, such as dataset quirks, library traps, rerun recipes
and measured numbers, and correct or delete a note as soon as it proves wrong. When a lesson holds
beyond one ticket, it is promoted into a rules file. Rules files are tied to paths and load
automatically whenever an agent touches matching files. The experiment rules, for instance, load
for anything under `experiments/` or `src/pianolens/eval/`. So a lesson learned once is applied by
every later agent without anyone having to remember it. One small rule shows the style: scratch
files never go in the repository, and absolute paths are required, because an unexpanded shell
variable once created a literal `$SP/` folder at the repository root.

In the code: `CLAUDE.md` (agent roster, hard rules); `.claude/agents/*.md`;
`.claude/agent-memory/<agent>/MEMORY.md`; `.claude/rules/*.md`; `WORKBOARD.md`.

#### What traps have we already fallen into?

The rules files hold every lesson that was promoted from a single experiment to a standing rule.
Each one records a mistake or near miss, so together they are a map of where this kind of research
goes wrong. They are grouped here by theme, with the experiment that taught each one in brackets.

**Measuring uncertainty.**

- With six or fewer groups, report a t-interval beside the bootstrap, because the bootstrap is
  optimistic (R-08a).
- Resample real clusters, and check that the cluster id groups more than one row (R-09).
- On PercePiano, resample by performer as well as by passage (R-06).
- Near a bar with five groups, add leave-one-out means, the worst run and a one-sided p-value
  (R-08c).
- After the run, compare the observed spread between groups with the one assumed in the plan, and
  say so if the interval has become uninformative (R-08d).

**Baselines, ceilings and pooled numbers.**

- Half-panel agreement is not the ceiling. Step it up with Spearman-Brown and report both the
  single-rater level and the full-panel ceiling (R-04).
- Report per-group paired differences and the unweighted mean over groups, not only a pooled number
  (R-04).
- For non-inferiority, report the tightest margins that still hold (R-04).
- Every results table has a trivial baseline, the model, rater parity where per-rater labels exist,
  and bootstrap intervals (standing rule).

**Keeping the pre-registration honest.**

- Never edit the hashed header; put the audited status in the Verdict section (R-01 to R-04).
- Disclose anything added after results, and refit the claim without it (R-01 to R-04).
- Apply the registered reading word for word; an interval entirely below 0.5 is a fail (R-06).
- Before running, check that every verdict branch can be reached, and say when "inconclusive" is the
  expected outcome (R-09).
- A threshold stated as a ratio to a null has a ceiling of 1 divided by the null's hit rate; compute
  it for the positive controls first, and report the implied share rather than only the ratio
  (BL-22, where the controls could not reach the planned ratio).
- A calibration to a nominal rate needs a two-sided tolerance and a floor on detecting real mistakes;
  a one-sided "at most" rewards rules that make the tier unreachable. Before selecting on development
  data, set aside the cases no candidate can move (BL-18).

**Controls that give a pass its meaning.**

- Test any likelihood or typicality score against the full battery of flat versions (R-06).
- Any "shared part against difference part" contrast needs a cross-unit control (F-07).
- That control must match the within-unit pair on nuisance factors such as time apart, tempo and
  noise (BL-16).
- R² gaps scale with noise, so report variance ratios beside them (BL-16).
- Boundary-based measures get a random-at-the-same-density control, a halved-reference control, and
  the boundary-count ratio (F-05e).
- Nulls must keep the variance profile along the piece, and component counts are reported by
  parallel analysis against that null; phase randomisation alone is weak (R-02).
- A control that is zero by construction is not evidence. Before citing "0 with the ground truth" or
  "0 fired", check whether the upstream path can produce the outcome at all (BL-20, BL-23).
- Measure whether an injected mistake is detected on units that were clean before the injection,
  and check that an absolute threshold is not already breached by the easy baseline cell (BL-20).
- A correction step gets a precision check on real data: count the changes it repairs and the ones it
  breaks, against ground truth (BL-23).
- Break a no-harm check down by piece and by recurrence across performers before explaining it; one
  score can dominate the denominator (BL-23).
- A proxy-only measurement gets a recall check against any labels the data already carries, and a
  pass is worded as a pass on the proxy (BL-19).

**Shortcuts and confounds.**

- A skill result that is not controlled for recording context is not a skill result, for audio and
  for transcribed MIDI (hard rule 3; D-10, R-09).
- Measure a shortcut's size against an explicit-label ceiling built by stacking (R-05).
- When repertoire tracks the label, add a within-piece AUC (R-05).
- When a matched comparison also drops part of the range, restrict the pooled model to the same
  levels (R-09).

**Using an LLM as an annotator.**

- Famous repertoire needs a memorisation control (disguised scores or unfamiliar pieces) and
  run-to-run variance; record whether the piece was recognised and break results down by it (R-08a).
- Compare recognised and unrecognised runs within the same piece, never pooled across pieces; in
  R-08b the easiest movement was never named, which made named runs look worse overall (R-08b).
- Self-reported recognition is a lower bound, because the model's hidden reasoning is not in the
  transcript; a disguise rules out explicit recall, not familiarity with the structure (R-08b).
- Unfamiliar is not unseen: public labels released before the model's training cutoff may have been
  seen, and only labels made after the cutoff exclude that (R-08c).
- A check that boundary counts match the reference is one-sided: a good annotator and a label
  recaller would both pass it, and only a mismatch argues against recall (R-08d).
- With few labelled boundaries per piece, list every miss and extra with its distance, and separate
  finer subdivisions from real placement errors (R-08c, R-08d).
- Blind annotators never receive a repository path; their inputs are copied elsewhere, their
  transcripts are audited for file access, and their outputs are saved into the experiment folder
  at once (R-08a).
- Before explaining why a replication came out lower, test whether it is lower, and compare how the
  two studies weight their groups (BL-17).
- A wider matching tolerance needs its own grid, proxy and random controls, and misses must be split
  by distance before being called a placement convention (BL-17).

**Library traps.**

- `factor-analyzer` 0.5.1: re-order factor correlations after an oblique rotation, compute
  communalities correctly, and note that the scikit-learn shim is harmless (R-01).
- partitura: performance durations extend to the pedal release by default, while PianoLens stores
  key-down durations; one metrical-position option crashes with numpy 2; scores must be merged and
  unfolded before alignment ids resolve.
- parangonar: its aligner does not handle repeats, so unfold first; unfolding twice crashes; its
  path finder returns different results on a second call unless section markers are rebuilt; its
  repeat identifier is broken with numpy 2.

**Data and alignment.**

- Every dataset gets a register row with source, version, license and size; check the size before
  downloading, and stay under 60 GB on the Mac.
- Much of the "MIDI" is transcribed from audio, so provenance is tagged and exact timing is
  validated only on Disklavier or sensor data.
- Downstream code uses the score returned by the aligner, because performers skip some repeats (at
  least 13 of 99 ASAP performances do).
- Missed notes are reported per bar, not per note, because single-note deletion labels are
  unreliable (F1 0.75).
- Every feature must be localisable, documented with units and a citation, aware of tempo and of
  loudness, and tested on a synthetic performance whose answer is known.
- A limit estimated per transcriber can really measure the source corpus, when each transcriber was
  only run on one corpus (BL-18).

**Audio.**

- Loudness from audio is relative only, and note ends and pedalling from audio are unreliable under
  reverberation.
- Extra-note flags from phone audio are low confidence; real-room microphone audio does not reproduce
  the takes' extras, so it can check a filter's safety but not tune it (A-01, A-01b).
- Before explaining unexplained notes acoustically, check them for sequence structure: step sizes
  against shuffled pitches, regular timing, and phrases that recur across recordings. That is how the
  "phantom" extras turned out to be a melody (BL-22).
- Player-piano ground truth has soft echoes: most same-key "repeats" under 80 ms start at the previous
  note's release. Report results near such a threshold with and without them (BL-21).
- Logs that name personal recordings never go in the repository root (A-01 incident).

**Listening studies.**

- Audio only, no labels; one renderer and one loudness normalisation; counterbalanced order;
  comparisons only within a passage; musicians and non-musicians analysed separately.
- At least 20 comparisons per item and scale-separation reliability of at least 0.8, plus
  split-half; adaptive designs need a non-adaptive holdout.
- Collect no personal data beyond what the protocol needs; consent and recruiting are Henry's.

In the code: `.claude/rules/experiments.md`, `study.md`, `data.md`, `features.md`, `audio.md`.

#### Known gaps and untested assumptions

**Evaluation machinery**

- The Spearman-Brown ceiling in R-04 treats a rank correlation as a Pearson correlation. It is a
  rough extrapolation, not a measured ceiling.
- Horn's parallel analysis undercounts when several strong components overlap, as shown on synthetic
  data. The 3 to 5 shared components behind H1b may therefore be a lower bound. The sequential
  variant exists but has not been compared on real data.
- Component counts grow with the number of performances. Fixing the sample at 50 makes counts
  comparable, but the count at larger samples is not established.
- The rule of adding t-intervals for six or fewer groups came after R-04, which had four works.
  Whether R-04's intervals change under it is not recorded.
- The Bradley-Terry code has only been unit-tested. It has never been fitted to real judgements, and
  its ridge value was not tuned against anything.
- Rater parity by default allows a target built from a single other rater on some segments, which is
  a noisy target. No sensitivity to that setting is recorded.
- Reachability was simulated experiment by experiment from R-05 onward. Earlier experiments (R-01 to
  R-04, R-06) were not rechecked for it.

**The perceptual cost study**

- No listener has taken it. Every power figure rests on assumed spreads, slopes and biases. The
  internal pilot of 12 listeners is the planned check.
- The primary axis (cost per threshold unit) and the margin of 2 are design choices, provisionally
  approved, not validated.
- Thresholds are measured on one sampled piano. The loudness reference came from a Disklavier, so
  loudness threshold ratios are approximate, and thresholds on real pianos or recordings may differ.
- The preference model is linear in threshold units and may saturate at strong levels. Per-level
  curves make this visible, but no alternative model is pre-registered as primary.
- Eight excerpts, six of them Mozart, Chopin or Schubert openings. Dependence of cost on style is
  checked only by dropping one excerpt at a time.
- Pedal blur depends on a harmony detector validated only on Mozart, and three excerpts have no
  detectable harmony change in their detection clips.
- Articulation is partly masked by the pedal in some clips, so its cost may be underestimated.
- The pilot listener is not naive. Ladders set from his thresholds may be misplaced for naive
  listeners; the simulation of a factor-2 error shows the cost in power only.
- The headphone check catches loudspeaker listening but not poor devices or noisy rooms.
- Consent wording, ethics review, payment and hosting are undecided.

**The pairwise studies**

- They do not exist beyond ticket descriptions. The comparisons-per-item target comes from studies in
  other domains, not from piano stimuli.
- Whether distance to the mean is the right baseline for H7, and whether structural coherence rewards
  formulaic playing (a risk named in the plan), are untested.

**The process**

- Pre-registration timing is verified from agent transcripts, not from git, because nothing is
  committed. Transcripts may not survive a new session, so later re-verification may be impossible.
- LLM recognition of a piece is self-reported, and the model's hidden reasoning is not visible.
  Recognition counts are lower bounds.
- The auditor is an agent of the same model family as the experimenters. Its independence comes from
  procedure (a separate role, a separate context, a checklist), not from a second human reviewer.
- Almost every audited verdict is "Confirmed with caveats". There is no plain "Confirmed" for a whole
  experiment, and "Returned" has been used only twice, both times for a reading or a chosen rule
  rather than for the measurements (BL-18, BL-22). This may mean audits consistently find real limits,
  or that the label scale does not discriminate. It has not been examined.


### Where the auditor changed our minds

Every row below is a claim made by the first analysis and corrected by the audit. The pattern is
consistent: first-pass analyses overclaimed, and pre-registration plus an adversarial check caught
it each time.

| Result | First claim | After audit |
|---|---|---|
| R-01 | Exactly 4 factors, with an "impossible value" warning | 3 to 5 factors. The warning came from a bug in a statistics library, which had also mislabelled the factor correlations. |
| R-02 | Expression needs 19 components, so it is not low-dimensional | The shared part needs only 3 to 5. The rest is individuality. |
| R-03 | The published result reproduces | Their headline averaged 3 of 4 test folds, their leak fix made the leak worse, and about 60% of the remaining signal came from spotting flat computer renditions. |
| R-04 | Both models are near the ceiling | The wrong ceiling was used. There is large headroom. |
| R-06 | Keep both expression models | The pre-registered rule picks one. Flat playing also beats experts on likelihood even when perturbed. |
| R-07 | The likelihood ratio S-LR passes, so it is a typicality score; the H1b preview falsifies H1b | S-LR is a flatness detector plus a noise penalty, and cannot tell halved expression from real. Real performers capture only about a quarter of the shared variance at 16 samples, so the 0.50 bar was out of reach and the preview says nothing about H1b. |
| R-08a | The confidence interval clears the target | Too optimistic with only 5 pieces. A more appropriate interval touches the target. |
| R-08b | Recognised pieces scored lower | An artefact of mixing movements. Within a movement, recognition helped slightly. |
| R-09 / D-10 | The skill effect vanishes once context is fixed | Fixing context also removes the top skill levels, so context and skill cannot be separated. |
| F-07 | Repeated timing reveals intent | Different pianists pass the same test. It is shared piece timing. |
| Study design | 12 to 17 comparisons per item is enough | Not supported by its source. Current guidance is 20 or more. |
| BL-17 | Claude scores lower on Romantic music than in R-08d, a gap that needs explaining; most misses are a placement convention; within one bar the target is reached | The two studies do not differ detectably, so R-08d's pass is simply not confirmed. Only a quarter to a third of misses are within a bar. The one-bar score's interval also contains 0.70, and a plain grid gains more from the wider window. |
| BL-18 | The new strong rule passes its pre-registered test and becomes the default | It passes only a one-sided limit and demotes nearly half of clear three-wrong-note bars. The overshoot came from runs of empty bars no rule could move. Returned; a simpler interim rule plus "passage not heard" went to a confirmation run (BL-18b). |
| BL-18b | The interim rule fails only because of the checker, so the failed criterion can be swapped for one on bars where the checker counts all 3 wrong notes | FAIL stands as the verdict. The failed criterion could never separate the rules (100% by construction for both), and the proposed replacement has the same flaw. Keeping the rule is acceptable only as a disclosed deviation, Provisional, with the learner-facing figure (about 7 in 10) stated. The lost wrong notes are mostly the 100 ms pairing window on transcriptions, not aligner absorption. |
| BL-20 | Fast passages fail because of the aligner, not the labelling; bar-level flags hold up | With a perfect alignment the gap still exceeds the limit, mostly from the ornament allowance, so both contribute. In dense bars that were clean before, about 1 such wrong key in 15 goes unflagged. |
| BL-22 | The phantom high notes are a room or phone artefact, and a missing overtone argues against string resonance | They are a recurring stepwise melody, a second sound source. The overtone argument was dropped. The planned harmonic test could not have passed even for its positive controls. |
| BL-23 | The tight ornament rule fails mostly because ornaments are played on an unexpected side; the pitch check found nothing on real data | Most of the failure is one score's unexpanded tremolo shorthand. The pitch check is zero by construction under the default. The reassignment pass also moves a correct match about 1 time in 8. |
| BL-19b | Mismatches between staff and hand are single notes passed to the other hand, not whole passages | They are systematic: a mismatched note is mismatched again 90% of the time, and one score puts a whole left-hand passage on the upper staff. Hand synchrony's pass holds only at the boundary and fails if any one passing piece is dropped |
| DF-13 | The wider window's false-pairing excess comes from one piece, and the rest of the lost wrong notes are aligner re-matches | One piece is the only drop that flips the result, but the failure is not one piece's doing. Part of the "re-match" half is the aligner matching one played note to two written notes, a separate defect (DF-15) that also occurs on clean playing |


## Part 5. Where things stand

### What works today

- **Finding wrong and missed notes from MIDI,** bar by bar, with expert-checked bars excluded so the
  score file is not blamed on the player. In fast runs the report names the bar rather than the
  note, because the checker is more reliable about the bar than about which notes.
- **Measuring timing from MIDI or from a phone recording.** Tempo shape, rushing, evenness and hand
  synchrony are all timing-based, and timing survives transcription.
- **Comparing a performance with hundreds of expert performances of the same piece,** bar by bar,
  and letting you hear the difference at each flagged passage.
- **Reading phrase structure from a score with Claude,** clearly better than hand-built rules in
  every style tested, and above the project's accuracy bar on Classical music. The report now uses
  these boundaries where a cached set exists, with their measured accuracy stated, the rule
  detector's result shown beside them, and the finding marked undetermined when the two disagree.
- **A local app** that takes a performance and produces the report and the comparison player.

### What does not work yet

- **A single trustworthy quality grade.** Our best models agree with an expert panel about as well
  as one human rater does. The panel data shows much more is achievable.
- **A demonstrated link to skill.** No measure has yet been shown to rise with skill once players
  recorded in the same conditions are compared.
- **Loudness, articulation, pedal and extra notes from phone audio.** These are reported with low
  confidence or not at all.
- **Phrase boundaries on Romantic music at the accuracy bar.** Claude's average on Romantic character
  pieces (about 0.64) is below 0.70 as a point estimate, and single pieces vary widely.
- **Naming the exact wrong note in fast runs.** A same-pitch repair step helps a little, but wrong
  keys that equal a nearby written note are still named less reliably than in slow passages.
- **Hearing what a teacher marks at the level of single notes (R-11).** We compared three
  teachers' annotated scores (Chopin's Nocturne Op. 9 No. 2, Waltz Op. 64 No. 1 and Etude Op. 10
  No. 4, from tonebase lessons) with hundreds of expert recordings of the same pieces. Two people
  encoding the same score independently agreed closely, so the annotations are usable data. Do
  experts do what the teacher marks more than elsewhere in the piece? Perhaps a little, but the
  evidence is inconclusive (0.63 where 0.5 means no difference; interval 0.50 to 0.75), and
  weaker where the teacher asks for something the printed score does not. When we removed a
  marked effect from expert performances, the report did not notice. The reason is structural:
  the report reads smoothed tempo and loudness per bar, so one held note, one accent or one
  voiced melody note is invisible to it even when exaggerated fourfold. Only whole-bar timing and
  beat-level loudness contrasts were caught. Only about a third of the annotations are things
  MIDI can observe at all; the rest are fingering, practice advice, analysis and character.

### Known gaps that have never been tested

Each chapter in Part 2 ends with its own list. The ones that matter most for a learner:

- **Staff is not hand.** Hands are assigned from the score's staves. Score-based proxies flag about
  5% of notes as possibly played by the other hand, but they miss most places where engravers marked
  a hand swap, so the true rate is unknown until notes with real hand labels (from video) are
  checked (BL-19, BL-24). Scores with unusual staff numbering now work (DF-09); piano duets do not
  (DF-11).
- **Very fast passages.** Bar-level flags hold up, but in about 1 clean dense bar in 14 a wrong key
  that equals a nearby written note still goes unflagged, and all of this rests on isolated synthetic
  mistakes, not the clustered slips real players make (BL-20, BL-23).
- **Fast repeated notes in phone audio.** On microphone recordings a key struck again within about
  100 ms is often merged into one note, so the report treats such missed notes as low confidence.
  This has not been measured on phone audio (BL-21).
- **The source of the high extra notes in the owner's recordings.** They are mostly a quiet,
  separate high melody, not a phone or room artefact and probably not string resonance, but where it
  comes from, in the room or added in the video edit, is unknown. A listening check comes first
  (BL-22).
- **The strongest note flag on phone input.** The interim rule failed its confirmation on 12 new
  pieces by the pre-registered rule (BL-18b) and is kept, provisionally, as a disclosed deviation.
  On a phone recording about 7 in 10 bars with three wrong notes are flagged strong.
- **Wrong notes the checker does not count on transcriptions (DF-12, DF-13).** On transcribed
  input 16 to 19 percent of injected wrong notes are not counted as wrong, mostly because they sit
  more than 100 ms from the expected onset and are left as a missed note plus an extra. A wider
  pairing window was tested and failed (DF-13): it recovers only part of the loss and adds
  wrong-note labels on clean playing. The other half is the aligner (DF-15), not yet fixed.
- **Which hand played a note.** The staff is wrong for 6.66% of notes against real video hand
  labels (BL-19b). Per-hand feedback stays off until hands are assigned by a tested model (BL-34).

### What comes next

| Step | What it unblocks |
|---|---|
| Decide what the H1b result means for the project's central bet (proposed: "piece-conditioned, anchored by expert performances" instead of "score-conditioned") | The wording of the research bet in CLAUDE.md (R-10) |
| Decide whether the report needs note-level channels (voice-separated loudness, per-note timing against the expert band) | Teacher-style feedback on single notes (R-11, BL-32) |
| Record 2 to 3 takes of a passage in one sitting, MIDI and phone together | A real learner's noise floor and the first fully trustworthy personal report |
| Listen to the flagged passages of the owner's takes, and check the original phone files | Where the second melody comes from (BL-22) |
| Run the listening study, starting with a pilot | Which flaws listeners actually mind (H6), and the ground truth any grade needs |
| A pairwise preference study among good performances | What separates good from great (H7) |
| Real-audio recording-context test | How large the audio shortcut is outside simulation (H8) |
| Stop the aligner giving one played note two written notes, then a pre-registered re-pairing step for wrong pitches; rebuild the expert floor tables and recheck the strong rule on transcribed input | Counting more of a phone learner's wrong notes, and a settled strong rule for phone recordings (DF-12, DF-15, BL-28, BL-18b) |
| Improve Claude's Romantic phrase reading: phrase labels made after the model's cutoff, a rule for where a cadence arrives, a period cue | Phrase feedback on the repertoire most learners play (BL-17) |
| A hand-assignment model trained on PianoVAM's hand labels, tested on unseen pieces | Per-hand feedback and a sturdier hand-synchrony measure (BL-34) |
| Expand tremolo shorthand in scores, then retest a tighter ornament rule | Better wrong-note naming around ornaments (BL-26) |


## Appendix

### Experiment index

Ids start with a letter for the kind of work: R for a research experiment, F for a feature study, A
for audio, P for the product, D for a data check, BL for a backlog item that became a study.

| Id | Question | Verdict | Where |
|---|---|---|---|
| R-01 | Do 19 rating scales reduce to a few judgements? | Confirmed with caveats | Part 3, listeners |
| R-02 | Is expert expression low-dimensional? | Confirmed with caveats; H1 not supported | Part 3, listeners |
| R-03 | Does a published audio model hold up on unseen pieces? | Confirmed with caveats | Part 3, prediction |
| R-04 | Can MIDI features match the audio model? | Confirmed with caveats | Part 3, prediction |
| R-05 | Do audio skill models use recording context? | Mechanism shown in simulation | Part 3, prediction |
| R-06 | Which expression model to fine-tune? | Confirmed with caveats | Part 3, prediction |
| R-07 | Fine-tune the expression model | Confirmed with caveats (two audits); fine-tuning harms, S-LR not used | Part 3, prediction |
| R-10 | Can the score predict what experts share (H1b)? | H1b falsified for frozen SyMuPe (scoped); Confirmed with caveats | Part 3, prediction |
| R-11 | Do experts and the report follow teachers' marks? | Confirmed with caveats; (a) inconclusive, (b) the report does not notice | Part 5 |
| R-08a to R-08d | Can Claude read phrase structure from a score? | Confirmed with caveats; Romantic is fragile | Part 3, LLM |
| R-09 | Does coherence rise with skill? | Inconclusive | Part 3, skill |
| D-10 | Do control features rise with skill? | Not shown within matched contexts | Part 3, skill |
| F-05e | Do Claude's boundaries work for the tempo measures? | Adopted | Part 3, LLM |
| F-07 | Do repeated takes reveal intent? | Confirmed with caveats, reinterpreted | Part 3, skill |
| F-08c | Stop flagging bars experts also "get wrong" | Adopted | Part 3, learner |
| A-01 | Phone recordings of a real learner | Timing trusted, extras not | Part 3, learner |
| P-01, P-02 | Comparison player and local app | Built | Part 2, report chapter |
| BL-16 | Same-sitting takes as a noise estimate | Confirmed with caveats | Part 3, skill |
| BL-17 | Is Claude's phrase reading above 0.70 on Romantic repertoire? | Confirmed with caveats; inconclusive by its rule (0.635, range 0.549 to 0.720) | Part 3, LLM; Part 2, shaping chapter |
| BL-18 | A fairer strong tier for transcribed input | Measurement confirmed; chosen rule returned; interim rule set | Part 3, learner; Part 2, report chapter |
| BL-18b | Does the interim strong rule hold on 12 new pieces? | FAIL by the pre-registered rule (C4, which measured the checker); meets C1 to C3; interim rule kept as a disclosed deviation, Provisional | Part 3, learner; Part 2, report chapter |
| BL-19 | How often is staff not hand? | Confirmed with caveats; pass on the score proxies, true rate unknown | Part 2, alignment chapter |
| BL-20 | Does note checking hold up in fast passages? | Confirmed with caveats; bar flags hold, note naming degrades | Part 2, alignment chapter |
| BL-21 | Do fast repeated notes survive transcription? | Confirmed with caveats; lost below about 100 ms | Part 3, learner; Part 2, audio chapter |
| BL-22 | Where do the phantom high notes come from? | Reading returned, then confirmed with caveats: a second melody, source unknown | Part 3, learner; Part 2, audio chapter |
| BL-23 | Can a tighter ornament rule and a same-pitch repair close the fast-passage gap? | Confirmed with caveats; candidate failed, repair step adopted, gap still open | Part 2, alignment chapter |
| BL-19b | How often is staff not hand, against real hand labels? | Confirmed with caveats; 6.66% of notes, hand synchrony passes at the boundary | Part 2, alignment chapter |
| DF-13 | Does a wider wrong-note pairing window help on transcriptions? | FAIL by the pre-registered rule; Confirmed with caveats; 100 ms stays | Part 2, alignment chapter |

### Reproducing anything

Each experiment folder in `experiments/` has a README with its pre-registration, the exact commands,
the results and the audit. Data is re-fetched by following `DATASETS.md`. `STATUS.md` has the
current one-page state of the project. This page is rebuilt from `docs/RESEARCH_LOG.md` with
`uv run --with markdown python scripts/build_research_log.py`.


### Glossary

| Term | Meaning |
|---|---|
| MIDI | A digital record of a performance: for each note, which key, when it went down, how hard it was struck, and when it was released, plus the pedals. |
| Velocity | How hard a key was struck, stored in MIDI as a number from 1 to 127. It controls how loud the note is. |
| Onset | The moment a note starts. |
| Score | The written music, here as a machine-readable file (MusicXML or similar). |
| Alignment | Pairing every played note with the written note it was meant to be. |
| Transcription | Turning an audio recording into MIDI with a trained model. |
| Tempo curve | How fast the music is going at each beat, after smoothing out tiny note-to-note wobbles. |
| Jitter | The leftover timing wobble once the smooth tempo curve is removed. |
| Phrase, cadence | A phrase is a musical sentence; a cadence is the chord progression that ends one. |
| Tier A to D | The four layers of judgement: correctness, control, shaping, interpretation. |
| Expert band | The range that most expert performances of a piece fall inside, bar by bar. |
| Quantile (q95, q99) | The value that 95 or 99 percent of expert performances stay below. Used as thresholds for "notable" and "strong" findings. |
| F1 | A score from 0 to 1 for finding things: 1 means everything found and nothing wrongly flagged. |
| R² | The share of variation in a target that a model explains. 0 is no better than always guessing the average; negative is worse than that. |
| Leave-piece-out | Testing a model only on pieces it never saw in training, so it cannot win by memorising pieces. |
| Rater parity | Asking whether a model agrees with the panel as well as a single human rater does. |
| Ceiling | The best agreement any model could reach, given how noisy the human labels are. |
| Pre-registration | Writing down, before running an experiment, what result would prove the idea wrong. |
| Bootstrap | Estimating uncertainty by re-running an analysis on many resampled versions of the data. |
| DCML | A group of expert-annotated score corpora with phrase and harmony labels, used here as ground truth. |
| PianoCoRe | A large collection of MIDI performances of the same pieces by many pianists, used as the expert reference. |


