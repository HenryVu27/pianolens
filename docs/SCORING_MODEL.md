# How PianoLens scores a performance

PianoLens does not give your playing a mark out of ten. It compares what you played with the printed score and with hundreds of expert recordings of the same piece, bar by bar, and tells you where you stand outside what experts do, how far outside, and how much to trust each finding.

<!-- DIAGRAM:scoring-shape -->

## The short answer

When you give PianoLens a performance (a MIDI file from a digital piano, or a phone recording that it first turns into notes), it hands back a profile, not a grade. The profile has four parts.

- **Findings per layer.** Four summary cards, one each for correctness (the right notes), control (steady timing, even runs, clean pedalling, hands together), shaping (how the playing follows the music's structure) and interpretation (how your tempo and loudness shapes compare with experts). Each card is a few sentences with measured numbers.
- **Flags per bar.** A timeline with one row per channel and one column per bar. A bar is flagged "notable" or "strong" when its measurement lies beyond what almost all experts do at that same bar.
- **A practice list.** The three most important flagged passages, each with one sentence of plain advice.
- **Audible comparisons.** For each flagged passage, short clips of your playing, your notes replayed on a neutral piano, a typical expert and a contrasting expert, so you can hear what the flag means.

There is no overall grade because nobody yet knows how to add these things up honestly. Two results shaped that decision.

The first is what listeners judge (experiment R-01). In the PercePiano dataset, 1,202 short clips were rated on 19 scales by a panel of expert listeners. A factor analysis, which asks how many independent judgements hide behind many rating scales, found 3 to 5: one dominant general-quality judgement, plus loudness and energy, pedal and legato, and mood. Nobody has yet measured how wrong notes, uneven timing and flat phrasing trade off in a listener's mind, so any weights we chose would be invented.

The second is how experts differ (R-02). Across 698 pieces with 50 expert performances each, the part of tempo and loudness shaping that experts share beyond chance takes only 3 to 5 basic shapes and covers about 35 to 46 percent of the differences between them. The rest is individuality. A grade that rewarded closeness to the average expert would punish exactly the freedom that makes performances worth hearing. So PianoLens holds you to the small shared core, leaves the rest alone, and reports each layer separately.

## The shape of the model

The core idea is simple: PianoLens is a **comparison model, not a learned grader**. Nothing in the report was trained to predict "good". Every judgement is a comparison with one of two references.

- **The score**: what should be played. It decides which notes are right, where the bars and phrases are, where the harmony changes and which passages are written as even runs.
- **The expert distribution**: how the piece is actually played. For most pieces this is several hundred expert performances from the PianoCoRe collection, most of them transcribed from recordings. For a few pieces there are also performances captured on a Disklavier (an acoustic piano with key sensors) or on the same printed score.

A "percentile" is used throughout. The 95th percentile of a set of values is the value that 95 percent of them stay at or below. In the code, `q95` means the 95th percentile.

<!-- DIAGRAM:expert-band -->

### From a raw measurement to a finding

Every channel goes through the same steps. The code that does this is `build_report` in `src/pianolens/report/build.py`.

1. **Line up the notes with the score.** Each played note is matched to its written note. The score is first unfolded along the repeat path you actually took, so a repeated bar appears twice (labelled "12" and "12 (2)"). If fewer than 80 percent of your notes can be matched, the whole report is marked as unreliable.
2. **Measure, at the right grain.** Wrong and missed notes are counted per bar. Timing steadiness and tempo and loudness shape are measured per bar. Evenness is measured per run of fast notes. "Too flat" is measured per 16-bar section.
3. **Pick the matching expert population.** For each channel there is one population to compare against (table below). When an expert is also the performance being scored, it is left out of its own comparison.
4. **Take that population's 95th and 99th percentiles.** For tempo and loudness the experts are themselves scored by a model fitted without them (10-fold cross-fitting), so their spread is the spread of genuinely unseen performances. A value is only judged when at least 10 reference values exist at that bar or run. With fewer, it is shown but not judged.
5. **Assign a tier.** Beyond the 95th percentile the bar is **notable** ("outside the usual expert range"). Beyond the 99th it is **strong** ("well outside the expert range"). The comparison is strictly "greater than". By construction about 5 percent of genuine expert bars are notable and about 1 percent strong, so a flag means "rarer than this among experts here", not "wrong". The note channel on transcribed input uses an interim variant for strong, described under "How correctness is judged".
6. **Record how far past the line it is.** The magnitude is the value divided by its notable limit. It is used only to order the list, never shown as a score.
7. **Group and rank.** Consecutive flagged bars in one channel become one issue. Issues are ranked by tier (strong first), then by category (notes, then control, then shaping and interpretation), then recurring mistakes first, then magnitude, then the earlier bar. The top three that are allowed onto the practice list become "What to practise".

Two kinds of issue are listed but kept off the practice list: loudness findings when loudness is low confidence (see "How far to trust each number"), and a per-bar tempo or loudness flag that sits inside a section already flagged as too flat, because the flatness explains it.

| Channel | Compared against | Percentiles are taken over |
|---|---|---|
| Notes (correctness) | What the same note checker reports on clean expert playing | 12,940 bars of 100 clean expert performances, 62 pieces, plus a per-bar check against experts of the same piece |
| Tempo shape, loudness shape | Tier D references (the large expert set) | Out-of-fold deviations of the references at that bar |
| Too flat (tempo, loudness) | Tier D references | The amount of shaping of each reference in the same 16-bar section |
| Timing steadiness | Tier D references | Each reference's own timing noise at that bar, measured against the other references |
| Pedal blur, evenness | Only performances of the very same score | Their values at that bar or run |
| Whole-piece error rate | Clean expert performances | Error rate per performance: median 4.65 percent, 95th percentile 16.4, 99th percentile 20.7 |

### How correctness is judged

Correctness needs extra care because the note checker is not perfect: it also flags notes in expert playing, partly real slips and partly alignment and data noise. On clean expert recordings, 42 percent of bars in a typical performance have at least one flagged note. So the question is never "was a note flagged?" but "was more flagged than the checker flags on experts?".

**What the checker counts.** The aligner pairs each played note with a written note of the same pitch. Two clean-up steps then run before anything is counted (`src/pianolens/features/correctness.py`).

- **Same-pitch repair (BL-23, on by default).** In a dense run, a wrong key that happens to equal a nearby written pitch can take that written note's match, leaving the played note that really belonged to it unmatched. The repair step estimates when each written note was due from its matched neighbours, leaving its own match out. If an unmatched played note of the same pitch lies within 100 ms of that time and at least 30 ms closer to it than the current partner, the match moves to it (`src/pianolens/align/postpass.py`). It helps, but it does not close the gap: wrong keys that equal a nearby written note are still named less reliably in fast runs than in slow passages.
- **Pitch check on every match (DF-10).** A match between two different pitches stays "correct" only when the ornament rule allows it (a played note within 2 semitones of a trill, turn, mordent or grace note). Otherwise the match is undone and both notes go through wrong-pitch pairing. With the current aligner this check cannot fire, because the aligner only makes different-pitch matches at ornaments, which the rule already allows. It matters only if the aligner or the ornament rule changes.

A played note left unmatched becomes a wrong pitch when it lies within 100 ms of the time a still-unmatched written note was expected and within 2 semitones of it or an octave away; otherwise it is an extra note, or a tolerated ornament. A written note left unmatched is missed.

A bar is judged on two numbers: the count of wrong-pitch notes, and missed plus extra notes per graded score note. The bar's tier is the higher of the two. The global limits, measured on the 100 clean expert performances, are in `src/pianolens/report/calibration.py`.

| Quantity | Notable if more than | Strong if more than |
|---|---|---|
| Wrong-pitch notes in the bar | 1 | 2 |
| Missed plus extra notes per note (MIDI input) | 0.267 | 0.634 |
| Missed notes per note (phone input, extras ignored) | 0.158 | 0.286 |

So one wrong note in a bar is shown but never flagged (7.1 percent of expert bars have one), two are notable and three are strong.

Several refinements sit on top. The first and the last apply to any input; the others apply only to transcribed input (a phone recording, or MIDI marked as transcribed).

- **The per-bar expert check.** Some bars trip up every expert, usually because the edition differs from what pianists play. When at least 5 expert performances of the same score, captured the same way as yours (up to 15 expert transcriptions for phone input, up to 15 key-sensor recordings otherwise), cover a bar, each limit is raised to the larger of the global limit and those experts' value at that bar: their 80th percentile for notable, and for strong their 99th percentile on key-sensor input or the rule in the next item on transcribed input. A bar that no longer clears the raised limits is labelled a likely score or edition artefact.
- **Strong on transcribed input: more than the worst expert (interim).** With only up to 15 expert transcriptions at a bar, a 99th percentile interpolated between the two largest values made a learner who merely equalled the worst expert strong, and strong bars ran above 1 percent. The code now takes the strong limit at a bar as the value of rank 0.99 × (n + 1), rounded up, among the n experts there. With fewer than 99 experts that rank does not exist, which is always the case here, so the limit becomes the worst expert's value at that bar plus a margin of 0 notes. In plain terms: on transcribed input, a bar checked against experts is strong only when it has more wrong notes, or a higher missed-note rate, than every expert transcription at that bar, and also more than the global strong limit. Notable is unchanged, and so is key-sensor input. The per-transcriber strong limits tried in BL-18 are switched off.
- **Passage not heard.** A run of at least 3 consecutive graded bars in each of which at least 80 percent of the written notes were not found is not treated as mistakes. It is reported once, as a low-confidence item: "Passage not heard: bars ... (at the start or end of the recording, when it is). This passage was not played, or it may be missing from the recording." Its bars get no correctness tier. Bars without graded notes neither break nor extend a run. The rule exists because such runs in the expert transcriptions came from recordings that start late or are cut, and no per-bar limit could move them. Two known weaknesses are open: a bar just under 80 percent splits a run into fragments, so a cut ending can show as two or three items without the "at the end" note (BL-27); and a recurring mistake across takes can still promote a "not heard" bar to strong.
- **Extra notes are ignored.** Phone transcriptions of the owner's playing produced 15 to 29 percent extra notes on three of five recordings, many on fixed high pitches. A later analysis (BL-22) found that these are mostly a second, independent sound in those recordings: a recurring stepwise melody between G6 and G7, about 3 notes per second, with the same phrases in all three recordings and no relation to the notes being played. It is not a fault of the phone or the transcriber, and overtones of played notes are at most a small share. Where the melody comes from, in the room or added when the video was edited, is undetermined until a listening check. Transcribed extras are unreliable in general anyway, so the rule does not depend on that explanation: on transcribed input, extras stay visible but never count towards a tier or a practice item.
- **Fast repeated notes (BL-25).** Transcribers often merge a key struck again very quickly into one note: on microphone recordings of a player piano, only a third of same-key repeats closer than 80 ms were found, against 98 percent of other notes, and the loss sits below about 100 ms. So on transcribed input, a missed note whose previous written note of the same pitch was due less than 100 ms earlier (at the tempo you played) is shown on the timeline and in a confidence note but does not count towards any tier. The expert tables used today do not carry this count, so only your side is reduced, which errs towards fewer flags (BL-28).
- **Fast runs are judged per bar (BL-20).** Where played notes follow each other less than 100 ms apart, the checker is more reliable about the bar than about which notes were wrong: the aligner absorbs or mispairs 6.9 to 8.3 percent of wrong keys there, against 2.5 percent in slow passages. Wrong notes in such runs are worded per bar ("2 wrong notes in this fast run") and never as "D instead of C". Tiers do not change. Even the bar is not guaranteed on transcribed input: 21 to 24 percent of injected wrong notes in fast runs were not counted at all (BL-18b audit, DF-12).
- **Recurring mistakes.** With several takes, the same wrong pitch at the same written note in at least two takes is treated as learned, not a slip, and its bar becomes strong. Mistakes the checker also reports for any expert recording of that score are removed first, and promotion needs at least 2 such recordings. Missed and extra notes never count as recurring.

### How settled the strong note flag is on phone input

The interim strong rule and the "passage not heard" rule were tested once on fresh data (BL-18b): 12 new pieces, with expert transcriptions from both transcriber families treated as learners (238 of them), each also given synthetic mistakes. Four criteria were fixed in advance. The verdict is **FAIL by the pre-registered rule**.

| Criterion | Transkun V2 | Aria-AMT | Result |
|---|---|---|---|
| C1: strong on clean playing between 0.30 and 1.25 percent of bars | 0.58 percent | 1.04 percent | pass |
| C2: the same notable-or-strong bars as the old rule | 0 bars differ | 0 bars differ | pass |
| C3: strong flags on injected mistakes at least 0.75 of the old rule's | 0.81 | 0.84 | pass |
| C4: at least 95 percent of bars given exactly 3 wrong notes are strong | 71.5 percent | 68.4 percent | fail |

The pre-registered consequence of a FAIL was to go back to the old rule (the interpolated 99th percentile). That was not done, and the deviation is recorded in DECISIONS. The old rule scores the same on C4 (71.6 and 68.6 percent), because both rules make a tested bar strong whenever the checker counts all 3 wrong notes, so C4 measured the note checker rather than the rule. And the old rule fails C1 on Aria-AMT, with 2.09 percent. So the interim rule stays, and it is **Provisional**: it meets C1 to C3 on one new sample of 12 pieces, which is not a confirmation. For Transkun V2 the clean rate passes on the point estimate only (its t-interval runs from 0.09 to 0.59 percent).

What this means for a learner: **on transcribed input, about 7 in 10 bars with 3 wrong notes become strong.** The limit is the note checker, not the tier rule (DF-12). In these tests 16 to 19 percent of injected wrong notes were not counted as wrong notes, against 2.5 to 8.3 percent on key-sensor playing. The auditor followed them one by one: most were left unpaired, shown as an extra note plus a missed note, because they sat more than 100 ms from where the checker expected the written note (median 141 and 180 ms, against 12 to 13 ms for the notes that were counted) (DF-13). Bars where the checker did count all 3 were strong every time. A future confirmation waits for a fix to the checker and will compare the rule with the old one rather than use a fixed 95 percent floor.

### A small worked illustration (real numbers)

Bar 52 of the owner's phone recording of the Chopin Nocturne discussed later shows the correctness rule end to end.

- The checker found 1 wrong note, 12 missed notes and 2 extra notes among 60 graded score notes. The wrong note sits in a fast run.
- Wrong notes: 1 is not more than the limit of 1, so this quantity is not tiered.
- The recording is transcribed from a phone, so the 2 extras are set aside. None of the missed notes falls on a fast repeat, so all 12 count. Missed notes per note: 12 / 60 = 0.20. That is more than 0.158 (notable) and less than 0.286 (strong), so the bar is **notable**.
- The per-bar check ran against 15 expert transcriptions of the same score. The bar still cleared the raised limits, so the flag was confirmed rather than written off as an edition artefact.
- Magnitude: 0.20 / 0.158, about 1.27.
- The sentence produced: "Bar 52: 1 wrong note in this fast run (the checker is more reliable about the bar than about which notes), 12 missed notes; outside the usual expert range for the note checker. Play this bar slowly, hands separately, until every note is secure."

It did not reach the practice list, because three strong findings outranked every notable one.

### The shared core and your freedom

Tempo and loudness shaping are where "different" and "worse" are hardest to separate. The code in `src/pianolens/features/interpretation.py` handles this in four layers.

**The band.** At each beat, the expert band is the 10th, 50th and 90th percentile of the reference curves, after each curve is centred on its own average. Your curve is shifted to the same level before comparing, so playing the whole piece a little faster or louder than others does not colour every bar. The band is what the charts draw.

**The shared core and the individual part.** Each 16-bar section is analysed separately. The code asks how many directions of variation experts have in common beyond chance, using parallel analysis against "envelope" surrogates: fake expert sets with the same smoothness and the same per-beat spread but no agreement between performers. Components that beat those fakes form the shared core, usually 1 or 2 per section and channel. Your deviation from the expert mean is split into a shared part (your position along those directions) and an individual part (everything else). The individual part is treated as legitimate freedom: it does not enter the typicality score at all.

**Two-sided typicality.** Typicality asks how usual your position in the shared core is, as the likelihood under a bell-shaped model fitted to the experts, not as a distance to the average. It includes one extra coordinate: the log of how much you shape at all in that section. Without it, a completely flat performance would sit at the centre and look perfectly typical. That is exactly the failure found in neural expression models (below). With it, typicality is two-sided: too little shaping is as unusual as too much. `typicality_pct` is the share of held-out experts who are at least as unusual as you; small means atypical. In the deadpan sample report (a flat computer rendition of Chopin's Op. 10 No. 3), tempo typicality was at most 0.006 in every section. Typicality is shown on the interpretation card; it does not create flags.

**The too-flat guard.** Separately, each section compares how much you shape (the spread of your curve) with the experts. Below their 5th percentile is too flat at notable, below their 1st at strong; above their 95th is "more extreme than 95% of experts", which is shown on the card but never becomes a practice item. In the deadpan sample every tempo and loudness section was too flat at strong, and the only practice item was "Bars 1-77: too flat. Your tempo varies less than 99% of experts here (SD of log tempo 0.000 vs expert median 0.120)."

One honest detail: the per-bar tempo and loudness flags use your *total* deviation from the expert mean at that bar, compared with how far held-out experts deviate there. A flag on the shared part alone is computed but informational only. So individuality is protected in the sense that the threshold is set by how much real experts deviate, including their own individuality, and typicality ignores it; a bar where you go further than 95 percent of experts will still be flagged.

## What counts as good

The system never defines "good" directly. For each layer it defines what "within the expert range" means, and flags what falls outside. Here is the working definition layer by layer.

### Correctness

Good means the notes on the page, in the right bar, at no higher error level than the same checker reports on experts playing that bar. A wrong pitch is a played note within 100 ms of where a written note was expected and within 2 semitones of it or an octave away; a missed note is a written note with no partner; an extra is a played note with no written note. Deliberately not penalised: ornaments (extra notes within 2 semitones of a trill, turn, mordent or grace note, and unplayed grace notes), a single wrong note in a bar, errors that experts of the same score also show at that bar, and, on transcribed input, extra notes, missed notes on fast repeats and passages "not heard". In fast runs the report says how many notes in the bar were wrong, not which ones.

### Control

Good means your fine timing, once the intended tempo shape is removed, stays as close to the expert timing pattern as experts do at that bar; fast runs are as even as experts play the same run; and the pedal is changed at harmony changes as experts on that score do. Timing is measured in beats, so it scales with your tempo, and the expert consensus timing at each note is subtracted first, so a shared agogic lean does not count as unsteadiness. Deliberately not penalised: rubato and phrase-level tempo arcs (they belong to the smooth tempo curve, not to the residual), gradual ritardandi and accelerandi within an evenness run, a consistent lead of one hand (reported, not judged), and pedalling on scores with no expert pedal data.

Hands are assigned by staff: the upper staff is taken as the right hand. When a score is loaded, its staves are renumbered so that upper is 1 and lower is 2 (DF-09), so scores whose staves are numbered 3 and 4, or split one staff per part, now give hand-synchrony results (before the fix, 25 catalogue scores gave none). Two cases remain wrong. Piano duets have four hands, and the renumbering splits them arbitrarily, so hand synchrony means nothing there; duets are not yet flagged (DF-11). And wherever a hand plays notes from the other staff (cross-staff writing, hand crossings), the assignment is wrong. Score-based proxies put that at about 5 percent of notes, but they miss most places where the engraver marked a hand swap, so the true rate is unknown until it is checked against video hand labels (BL-19, BL-24).

### Shaping

Good, as far as the system measures it, means your expression is related to the music's structure: loudness that is predictable from pitch, harmony, metre and phrase position; phrases that slow at their edges more often than phrases placed at the wrong boundaries would; a melody louder than its accompaniment; hairpins and dynamic markings followed in the marked direction. None of this is compared with experts or flagged. It is reported as description, because no shaping measure has yet been shown to rise with skill once recording conditions are matched (D-10, R-09). Deliberately not penalised: anything. The cards say what you did, not whether it was right.

**Where the phrases come from.** The phrase-timing measure needs phrase boundaries, and the report now takes them from Claude when the piece has a cached set (DF-02). Claude reads a text rendering of the score with no title, twice, in independent blind readings, and the measure is averaged over the readings. Caches exist so far only for the owner's five pieces; any other piece falls back to a rule-based cadence detector, and the card says why. The accuracy is disclosed on the card itself. On Romantic character pieces (BL-17, 24 pieces), Claude's readings matched expert phrase ends at about 0.64 on average (plausible range 0.55 to 0.72), below the project's 0.70 bar, and anywhere from 0.14 to 0.92 on single pieces; the cadence detector reached 0.31. Compound metres such as 6/8 were tested on only 6 pieces, and no nocturne or waltz was ever tested, so the card adds a caution for each of these that applies. It also says how many readings named the piece, because a remembered analysis may have shaped the boundaries. Next to Claude's value the card always shows each reading's value and the cadence detector's value. When Claude's value and the detector's value point in opposite directions, the finding is labelled **undetermined** and no direction is stated. No practice item depends on it either way. The other shaping measures (structure in loudness and note lengths) still take phrase position from a simpler cue-based guess.

### Interpretation

Good means your tempo and loudness shapes, bar by bar, stay within the range of held-out experts, your amount of shaping in each 16-bar section is not below almost every expert's, and your overall tempo is reported against the experts' 10th to 90th percentile. Deliberately not penalised: being different from the average, choices outside the shared core, an overall tempo or loudness level (the shapes are compared after removing level), and anything "more extreme" than experts (shown, never practised). The card says so directly: "A flag says 'unusual here', not 'wrong'."

## Every metric

Column key. **Compared against**: score, experts (with which set), a published or perceptual value, a null (a deliberately wrong version of the same measure), or nothing. **From MIDI** and **From phone audio**: trusted, low confidence, or not available. **In the report?**: "yes, flagged" (tiers per bar), "yes, card" (a number in a summary card or chart), "data only" (in the report's data file but not on the page), or "research only" (computed by the feature modules, not by the report).

### Correctness

| Metric | What it measures | Unit | Good looks like | Compared against | From MIDI | From phone audio | In the report? |
|---|---|---|---|---|---|---|---|
| Wrong notes per bar, `n_wrong_pitch` | Played notes that replace a written note | count | At most 1 per bar | Score; clean experts (limits 1 / 2); per-bar experts (on transcribed input, strong needs more than every expert at the bar) | Trusted (bar-level precision at least 0.996) | Low confidence (transcription roughly doubles apparent errors; 16 to 19 percent of wrong notes go uncounted, DF-12) | yes, flagged |
| Missed notes per bar, `n_missed` | Written notes with no played partner, judged per bar | count; rate per note | Under 0.267 per note with extras, 0.158 without | Score; clean experts; per-bar experts | Trusted per bar, not per note | Low confidence (fast repeats and quiet inner notes can be lost) | yes, flagged |
| Extra notes per bar, `n_extra` | Played notes with no written note, not ornaments | count | Counted with missed notes (limit above) | Score; clean experts | Trusted | Not trusted (in three of the owner's recordings, mostly a second, independent melody, BL-22) | yes, shown only |
| Wrong notes in fast runs, `n_wrong_fast_run` | Wrong notes where played notes are under 100 ms apart | count | Not judged separately | Nothing (wording rule) | Trusted per bar, not per note | Same, and more of them go uncounted | yes, worded per bar |
| Missed notes on fast repeats, `n_missed_fast_repeat` | Missed notes whose previous same-pitch written note was due under 100 ms earlier | count | Not judged | Score | Counted like any missed note | Low confidence; not counted towards tiers | yes, confidence note and timeline |
| Passage not heard, `not_heard` | Runs of 3 or more graded bars, each with at least 80 percent of notes missed | bars | None | Score | Not applied | One low-confidence item; its bars get no tier | yes, confidence note |
| Checker clean-up, `n_reassigned`, `n_pitch_dissolved`, `n_ornament_matches` | Matches moved by the same-pitch repair; different-pitch matches undone or kept by the ornament rule | count | Not judged | Score | Trusted | Trusted | data only |
| Accuracy, `accuracy` | Share of graded score notes played as written | fraction | High; read against the transcription floor on phone input | Score | Trusted | Low confidence | yes, card |
| Error rate, `error_rate` | (wrong + missed + extra) per graded note | fraction | Below the expert 95th percentile (16.4%) | Clean experts (median 4.65%) | Trusted | Low confidence; a per-piece floor from 15 expert transcriptions is shown | yes, card (never a practice item) |
| Ornaments, `n_ornament`, `n_ornament_skipped` | Tolerated extra or skipped notes at ornaments | count | Not judged | Score | Trusted | Low confidence | data only |
| Match ratio, `match_ratio` | Share of notes that aligned to the score | fraction | At least 0.8, else the report is marked unreliable | Score | Trusted | Trusted as a warning | yes, confidence note |
| Recurring mistakes, `recurring` | Same wrong pitch at the same written note in 2 or more takes | takes | None | Other takes; expert recordings of the score | Trusted | Low confidence | yes, flagged strong |

### Control

| Metric | What it measures | Unit | Good looks like | Compared against | From MIDI | From phone audio | In the report? |
|---|---|---|---|---|---|---|---|
| Timing steadiness, `noise_rms_ms` / `noise_rms_beats` | Note timing left after removing your smooth tempo curve and the expert consensus timing | ms, beats (RMS) | Within the experts' 95th percentile at that bar | Tier D experts, each against the others | Trusted | Trusted (transcription adds about 2 ms to tens of ms of variation) | yes, flagged |
| Timing without references, `jitter_nometric_rms_ms` | Fallback: residual minus your own recurring within-bar pattern | ms | Lower is steadier | Nothing | Trusted | Trusted | yes, card, only without references |
| Tempo summaries, `tempo_bpm_geomean`, `tempo_log_sd`, `jitter_rms_ms` | Average tempo, amount of tempo variation, raw residual timing | BPM, log, ms | Descriptive | Nothing | Trusted | Trusted | data only |
| Evenness of runs (timing), `even_strict_ioi_cv` | Variation of note spacing in scales, arpeggios and repeated figures, tempo-normalised | fraction of note length | Below the 95th percentile of experts on the same run | Same-score experts; published scale values at a note rate within 20% | Trusted | Partial (one transcriber lowered it by about 15%) | yes, flagged (same-score experts only) and card |
| Evenness of runs (loudness), `even_strict_vel_sd_midi` | Loudness variation in the same runs, after removing a trend | MIDI velocity | Near or below the audible step of 2.7 to 4.5 units | Perceptual threshold (as context) | Trusted | Low confidence | yes, card |
| Note rate of runs, `even_strict_note_rate_nps` | Speed of the runs | notes per second | Descriptive; unevenness rises with speed | Nothing | Trusted | Trusted | yes, card |
| Broad evenness, `even_ioi_cv`, `even_vel_sd_midi` | Same, on any equal-note stretch | as above | As above | Nothing | Trusted | Partial / low | research only (data only in the report) |
| Hand synchrony, `hand_async_median_ms`, `hand_async_resid_sd_ms` | Which hand sounds first at shared onsets, and the spread after allowing for the louder hand sounding earlier | ms | Within about 30 ms, which is hard to hear | Perceptual threshold | Trusted, but hands are assigned by staff (staff numbers normalised, DF-09; meaningless for duets, DF-11) | Trusted for timing, same staff caveat | yes, card |
| Tempo instability, `tempo_instability_log_sd`, `tempo_drift_log` | Tempo wobble between 1.5 and 4 bars; net rushing or dragging in a section | log tempo | Descriptive | Nothing | Trusted | Trusted | data only (not on the page) |
| Pedal blur, `pedal_blur_fraction`, `pedal_blur_beats` | Share of detected harmony changes the sustain pedal is held through | fraction, beats | Below the 95th percentile of experts on the same score | Same-score experts; harmony changes from the score (detector F1 0.76) | Trusted, but rarely comparable (the large expert set has no pedal) | Not trusted (transcription under-reads pedal) | yes, flagged (same-score experts only) and card |
| Pedal down share, `pedal_down_fraction` | Share of time the pedal is down | fraction | Descriptive | Nothing | Trusted | Not trusted | data only |

### Shaping

| Metric | What it measures | Unit | Good looks like | Compared against | From MIDI | From phone audio | In the report? |
|---|---|---|---|---|---|---|---|
| Structure in loudness, `coherence_velocity.r2_no_markings` | Share of note-to-note loudness predictable from pitch, harmony, metre and phrase position (a cue-based guess) in held-out bars, markings left out | R² | Higher means more structured | Nothing (cross-validated; needs 12 bars and 3 blocks) | Trusted | Low confidence (loudness) | yes, card |
| Structure in note lengths, `coherence_articulation` | Same for how long keys are held | R² | As above | Nothing | Trusted | Not trusted (note ends are not audible under pedal) | yes, card |
| Structure in timing and tempo, `coherence` timing / tempo channels | Same for timing and tempo | R² | As above | Nothing | Trusted | Trusted | research only (needs annotated phrases) |
| Phrases in time, `concave_share`, `null_concave_share`, `concave_excess` | Share of phrases that slow at both ends, minus the share with boundaries shifted 2 bars | fraction, points | Positive excess | Shifted-boundary null; phrase boundaries from Claude's cached readings where a cache exists (about 0.64 on Romantic pieces, below the 0.70 bar), otherwise from the cadence detector, whose value is always shown too | Partial (boundary accuracy) | Partial (same) | yes, card; "undetermined" when the two boundary sources disagree in sign; never a practice item |
| Melody over accompaniment, `vel_diff_mean_midi`, `frac_melody_louder` | How much louder the top line is than the other notes at shared onsets | MIDI velocity, fraction | Melody louder | Nothing | Trusted | Low confidence | yes, card |
| Melody lead, `lead_mean_ms`, `lead_vel_corr` | Whether the melody sounds early, and whether that follows loudness | ms, r | Descriptive | Nothing | Trusted | Partial (timing fine, loudness not) | yes, card |
| Written dynamics, `hairpin_agree_frac`, `level_agree_frac` | Share of hairpins and dynamic level changes played in the marked direction | fraction | Most | Score | Trusted | Low confidence (not separately checked) | yes, card |
| Accents and level ranking, `accent_agree_frac`, `level_velocity_spearman` | Accented notes louder than neighbours; loudness follows marked levels | fraction, rank r | Positive | Score | Trusted | Low confidence | data only |
| Repeated passages, `repeated_material` | Whether a repeated passage is shaped the same way | r, concordance | Descriptive | Your first playing | Trusted | Partial | research only |

### Interpretation

| Metric | What it measures | Unit | Good looks like | Compared against | From MIDI | From phone audio | In the report? |
|---|---|---|---|---|---|---|---|
| Tempo shape per bar, `tempo.dev_rms`, `dev_mean` | How far your smooth tempo curve departs from the expert mean at that bar, and in which direction | log tempo ratio (shown as % faster or slower) | Within the held-out experts' 95th percentile | Tier D experts, out of fold | Trusted | Trusted | yes, flagged |
| Loudness shape per bar, `velocity.dev_rms`, `dev_mean` | Same for smooth loudness | MIDI velocity | As above | Tier D experts (key-sensor ones when at least 8 exist) | Trusted only if the experts are key-sensor too | Low confidence | yes, flagged, never practised when low confidence |
| Too flat / too extreme per section, `too_flat`, `too_extreme`, `magnitude` | Amount of shaping in each 16-bar section | SD of log tempo; SD of velocity | Not below the experts' 5th percentile | Tier D experts | Trusted (loudness as above) | Tempo trusted, loudness low | too flat: yes, flagged; too extreme: card only |
| Typicality, `typicality_pct` | Share of held-out experts at least as unusual in the shared core plus amount of shaping | fraction | Not near 0 | Tier D experts, out of fold | Trusted | Tempo trusted, loudness low | yes, card (least typical section) |
| Shared core, `k_shared`, `individual_share`, `target_z` | Number of shared expert directions; share of your deviation outside them | count, fraction | Descriptive | Tier D experts | Trusted | As above | data only |
| Expert band | 10th, 50th and 90th percentile of the experts at each beat | BPM, MIDI velocity | Your curve mostly inside | Tier D experts | Trusted | As above | yes, charts |
| Overall tempo, `tempo_overall` | Your average tempo over the bars you played, against the experts over the same bars | BPM, percentile | Descriptive | Tier D experts | Trusted | Trusted | yes, card |
| Agreement features, `ref__*_r`, `_rms`, `_rms_pct`, `_nn_rms` | Correlation and distance to the expert mean and to the nearest expert | r, units | Descriptive | Tier D experts | Trusted | As above | data only (research inputs from R-04) |

## The learned models

Beyond the comparison model, PianoLens has built or tested several learned models. None of them produces anything in today's report. Here is what each is and why.

### The rating model (R-04)

This is a small model that predicts listener ratings from interpretable MIDI measurements. Its main version uses 62 measurements of one performance alone: correctness, tempo, the control measures, the shaping measures and simple descriptors of loudness, articulation and pedal. It predicts the 19 PercePiano rating scales (the panel's average for each clip), and the model family and settings are chosen inside the training data only. It was tested on whole works it had never seen, with four held-out works, mostly slow Schubert, in short clips of 4 to 16 bars.

The key test is within a passage: given two performances of the same passage, how often does the model order them the same way as the panel? The model got this right 62.4 percent of the time, and a large pretrained audio model, MuQ, got 62.3 percent. Chance is 50 percent. A single human rater, scored against the panel, lands at 59.0 percent when the rater's ties count as half and 62.7 percent on the pairs the rater did not tie. So the model agrees with the panel about as well as one listener does. The ceiling is much higher: splitting the panel in half suggests a noiseless predictor could reach a within-passage rank correlation of roughly 0.74 against the full panel, against about 0.35 for both models. That extrapolation is rough, but the room is large.

What drives it, measured by how much accuracy drops when a group of measurements is scrambled: pedal first (0.097), then loudness and dynamics (0.058), tempo shape (0.032) and voicing (0.022), with hand synchrony (0.008) and note rate (0.006) behind. Correctness, fine timing, articulation, structural coherence and dynamic-marking compliance contribute almost nothing on this data (0.000 to 0.004). The single strongest measurement is average pedal depth, the top coefficient for 11 of the 19 scales, which looks like a halo: a wetter sound reads as richer, longer and more expressive.

Why it is not in the report: it is only at single-rater reliability; it was trained on four works of Disklavier MIDI; its strongest input, pedal, cannot be read from a phone; and correctness hardly matters in data made of expert performances, which says nothing about a learner who plays wrong notes. The report card says "Model-based quality ratings are not included".

### MuQ, the large audio model (R-03, R-05)

A published result reported that MuQ predicts expert ratings well (R², the share of rating variation explained, of 0.536). We reproduced it at 0.509, then tested on unseen works: it fell to -0.087, worse than always guessing the average, because the model had learned the pieces. Within a passage it still orders performances correctly about 62 percent of the time. A separate simulation (R-05) showed that audio models can read the recording setting as a stand-in for skill: tying the setting to skill raised a skill classifier's score from 0.87 to 0.94, and shuffling it at test time dropped it to 0.73. A model that can cheat on the room cannot judge a phone recording made at home.

### Expression models: SyMuPe and Pianist Transformer (R-06, R-07)

These models learn to generate human-like playing from a score. The tempting idea is to ask one how likely your performance is. Both were compared on unseen pieces; they tied on quality, and a pre-registered tie-break chose SyMuPe. The decisive finding was about likelihood: both models detect added random noise well (AUC at least 0.94, where AUC is the chance of ranking a real performance above a corrupted one) but give every flat, deadpan rendition a higher likelihood than the real expert performance (AUC 0.00). Likelihood rewards predictability, and flat playing is the most predictable of all. A fine-tuned version with corrected scores (a likelihood ratio against a model of flat playing, among others) is pre-registered as R-07 but has not been run. Until it passes the same deadpan tests, no expression model is used, and this failure is why the report's own typicality includes the amount-of-shaping coordinate.

### What listeners judge (R-01)

The listener factors are not a model of your playing, but they tell a future grade what it must cover. The ratings reduce to 3 to 5 factors; the four-factor solution is one dominant general-quality factor (interpretation, balance, spaciousness, colour, imagination, low rawness) plus loudness and energy, pedal and articulation, and dark mood. Timing stability is almost unrelated to the rest, and individual raters use about as many factors as the panel. Today's report layers do not map one-to-one onto these factors, which is one more reason not to combine them into a single number yet.

## How far to trust each number

"Trusted" means measured well enough to rank and practise from. "Partial" means shown with a caveat or only partly compared. "Not yet" means shown only, or not usable.

| Layer | MIDI from a key-sensor piano | Phone audio (transcribed) |
|---|---|---|
| Correctness: wrong and missed notes | Trusted per bar. Bar-level wrong-pitch precision at least 0.996; missed notes reliable per bar. In fast runs the checker is more reliable about the bar than about which notes. | Partial. Transcription roughly doubles the apparent error rate (0.039 to 0.080), so results are read against expert transcriptions of the same piece. Missed fast repeats are set aside, and near-empty runs of bars become "passage not heard". |
| Correctness: the strong note flag | Trusted as "beyond experts' 99th percentile". | Provisional. An interim rule (more errors than every expert transcription at the bar) that failed its confirmation by the pre-registered rule and is kept as a disclosed deviation. About 7 in 10 bars with 3 wrong notes become strong, because the checker misses some wrong notes (DF-12). |
| Correctness: extra notes | Trusted. | Not yet. In three of the owner's recordings mostly a second, independent melody (BL-22); ignored for tiers. |
| Control: timing steadiness, tempo | Trusted. | Trusted. Onset error of a few milliseconds against tens of milliseconds of real variation; timing measures moved by about 1 percent under transcription. |
| Control: evenness | Partial. Flagged only against experts on the same score, which learners rarely have. | Partial. Timing evenness shifts under one transcriber; loudness evenness is low confidence. |
| Control: hand synchrony | Partial. Measured well, not compared with experts, and hands are assigned by staff (normalised staff numbers; wrong for duets and hand crossings). | Partial. Same, timing survives. |
| Control: pedal | Partial. Measured well, rarely comparable (no expert pedal data for most pieces). | Not yet. Transcription roughly halves the pedal-down time. |
| Shaping | Partial. Descriptive only; not validated as a skill measure. Phrase boundaries come from Claude where cached (below the accuracy bar on Romantic pieces, untested on nocturnes, waltzes and most compound metres), otherwise from a rule detector; the phrase finding is undetermined when the two disagree. | Partial for timing-based measures, not yet for loudness and note-length ones. |
| Interpretation: tempo shape, too flat, typicality | Trusted as "unusual among experts", not as "wrong". Flag rates on expert playing near nominal (tempo strong 0.6 to 1.5 percent). | Trusted. Disklavier and transcribed versions of the same performance get the same flag rates. |
| Interpretation: loudness shape | Trusted only when the experts are key-sensor too (at least 8 of them). | Not yet. Loudness from a phone is only relative; kept off the practice list. |
| Whole-profile skill claim | Not yet. No measure has been shown to rise with skill once recording conditions are matched. | Not yet. Same. |

## A worked example

This is the current report (rebuilt on 2026-09-29 with the code described above) on the owner's phone recording of Chopin's Nocturne in D-flat major, Op. 27 No. 2, transcribed into notes by Transkun. The piece has 77 bars and 6 beats per bar; the recording lasts about 334 seconds and produced 1,836 notes.

**What it was compared with.** 701 expert performances of the piece from PianoCoRe. The tempo and loudness shape analysis used a random 500 of them; the timing-steadiness comparison used all 701. About 95 percent of the score could be mapped onto the reference edition. For the per-bar correctness check, 15 expert transcriptions of the same score, made by the same transcriber family, were used, and 76 of the 77 bars were covered by enough of them.

**The confidence notes at the top said:** loudness is low confidence because the input is transcribed; transcription roughly doubles the apparent note-error rate; extra notes are low confidence and not ranked; the per-bar expert check ran against 15 expert transcriptions; the checker also flags 42 percent of bars in a typical expert performance; and the control measures are not yet validated as measures of skill. A further note put the correctness numbers in context: the same transcriber on 15 expert recordings of this piece gives a median error rate of 5.4 percent (90th percentile 6.9 percent) and a median extra-note rate of 2.0 percent, against 10.7 and 4.7 percent for this take. There was no note about fast repeats or passages not heard, because neither occurred.

**Correctness.** 1,723 of 1,832 score notes were played as written (94.1 percent), with 19 wrong, 90 missed and 87 extra notes flagged in 54 of 77 bars. Before counting, the same-pitch repair step moved 5 matches. Three of the wrong notes fell in fast runs (in bars 32, 43 and 52), so those bars name their wrong notes only per bar. No missed note fell on a fast repeat, and no run of bars was "not heard". Five bars were notable and none strong, and the per-bar expert check confirmed all five.

| Bar | Wrong | Missed | Graded notes | Why it is notable |
|---|---|---|---|---|
| 32 | 2 (1 in a fast run) | 4 | 33 | 2 wrong notes, more than the limit of 1 |
| 39 | 2 | 0 | 46 | 2 wrong notes |
| 45 | 0 | 5 | 30 | 5 / 30 = 0.167 missed per note, above 0.158 |
| 52 | 1 (in a fast run) | 12 | 60 | 12 / 60 = 0.20 missed per note |
| 69 | 1 | 4 | 21 | 4 / 21 = 0.19 missed per note |

**Control.** Overall, the timing departed from the expert timing pattern by 79 ms RMS (0.108 beats). Five bars were flagged:

| Bar | Your timing noise | Experts' 95th percentile | Experts' 99th percentile | Tier |
|---|---|---|---|---|
| 32 | 0.186 beats (131 ms) | 0.158 beats | 0.211 beats | notable |
| 43 | 0.200 beats (96 ms) | 0.140 beats | 0.190 beats | strong |
| 52 | 0.207 beats (111 ms) | 0.148 beats | 0.237 beats | notable |
| 54 | 0.161 beats (110 ms) | 0.160 beats | 0.201 beats | notable |
| 60 | 0.303 beats (239 ms) | 0.225 beats | 0.287 beats | strong |

The control card also described things it did not judge: the left hand typically sounded 19 ms before the right, with a spread of 36 ms after allowing for loudness; the pedal was held through 52 percent of 102 detected harmony changes, "not compared" because no expert pedal data exist for this score; and six even runs had a timing variation of 0.42 of the note length at 3.9 notes per second.

**Interpretation.** The overall tempo was 85 beats per minute, against an expert range of 75 to 95 (10th to 90th percentile, median 84): faster than 51 percent of them, which is squarely typical. Four bars were flagged for tempo shape, each one faster than the typical expert shape relative to the owner's own average tempo.

| Bar | Direction | Your deviation (RMS, log tempo) | 95th / 99th percentile | Tier |
|---|---|---|---|---|
| 7 | about 16% faster | 0.168 | 0.137 / 0.208 | notable |
| 52 | about 26% faster | 0.304 | 0.254 / 0.382 | notable |
| 58 | about 21% faster | 0.196 | 0.179 / 0.240 | notable |
| 60 | about 14% faster | 0.649 | 0.423 / 0.507 | strong |

At bar 60, in absolute terms, the smooth tempo reached about 133 beats per minute where the experts' 10th to 90th percentile ran from about 71 to 123. The least typical 16-bar section was bars 49-64, where only 6 percent of held-out experts were at least as unusual. That section is also a clear case of the shared-core logic: no shared expert direction cleared the null there, so all of the owner's deviation counted as individual, and what made it unusual was the amount of tempo shaping (0.228 against an expert median of 0.143, more than 98.8 percent of experts). The card reported it as "more extreme than 95% of experts in 1 section", which is never a practice item. No section was too flat. One loudness bar, bar 24, was strong (about 14 velocity units louder than the typical shape) but was kept off the practice list because loudness from a phone is low confidence.

**Shaping,** reported without judgement: 41 percent of note-to-note loudness was predictable from the score's structure in held-out bars, but only 1 percent of note lengths; the melody was louder than the accompaniment at 96 percent of shared onsets; 53 percent of 72 hairpins went the marked way. The phrase-timing finding shows the new phrase source at work, and it came out **undetermined**. With Claude's boundaries (two blind readings, 19.5 phrases on average), 82 percent of phrases slowed at both ends against 51 percent with the boundaries shifted by 2 bars, an excess of +31 points (+32 and +30 in the two readings). With the cadence detector's 14 phrases the excess was -29 points. The two sources point in opposite directions, so the card says that whether the phrases slow at both ends more than chance is undetermined for this performance. It also said that Claude named the piece in both readings, and it carried three cautions: Romantic repertoire, a compound metre, and a nocturne, a genre never tested. No practice item depends on it.

**What to practise** listed three items, all strong, so every notable note bar ranked below them:

1. "Bar 43: note timing is less steady than experts (96 ms RMS away from the expert timing pattern, while 95% of experts stay within 67 ms here). Practise with a slow, steady inner pulse."
2. "Bar 60: note timing is less steady than experts (239 ms RMS away from the expert timing pattern, while 95% of experts stay within 178 ms here). Practise with a slow, steady inner pulse."
3. "Bar 60: you move ahead, about 14% faster than the typical expert shape (relative to your own average tempo); only 1% of experts depart this far here. Check that this timing is what you intend."

Two timing items outrank the tempo item at the same tier because control comes before interpretation in the ranking.

**The same recording through a second transcriber.** It was also transcribed with Aria-AMT and the report rebuilt. The same 5 timing bars and the same 4 tempo-shape bars were flagged; all 5 note bars reappeared and Aria-AMT added a sixth; and all three practice items were flagged there too. The loudness flags shared only 1 bar out of 9 flagged by either model, which is exactly why loudness is kept off the list. Tiers moved more than bars did. Aria-AMT counted 4 wrong notes in bar 52 (3 of them in a fast run) instead of 1, so that bar became strong and led its practice list, and its timing and tempo flags there also reached strong. That is the DF-12 point in miniature: whether a bar with several wrong notes reaches strong on phone input depends partly on how many of them the checker manages to count.

## What a real grade would take

Everything in this section is plan, not result.

A trustworthy grade needs ground truth that says how much each kind of flaw matters to a listener. Three studies are designed to supply it.

- **Perceptual cost per layer (S-03, hypothesis H6).** Expert recordings are degraded along one dimension at a time (timing jitter, flattened tempo, flattened dynamics, voicing, pedal blur, articulation, wrong notes) at graded levels, rendered on one fixed piano, and played to listeners. Each dimension gets a detection threshold and a preference cost per threshold unit. If the costs differ by a factor of two or more, each layer deserves its own weight; if not, weighting by audibility alone is enough. The study app and stimuli are built; nothing has been run on a listener. Under assumed parameters, 96 listeners would give 0.92 power to detect a three-fold cost difference.
- **Pairwise preference among good performances (Phase 4, H7).** Listeners hear two renditions of the same passage, blind and on the same piano, and pick one. A Bradley-Terry scale fitted to those choices is then explained by the measurements, to test whether preference among good players depends on more than closeness to the average.
- **Learner takes (O-01).** Two or three takes of one passage in one sitting, captured as MIDI and on a phone together. These give a real learner's noise floor, the first test of recurring mistakes on one player's own habits, and the first fully trusted personal report.

With those in hand, the profile would change in one specific way. Each layer's flags would carry a measured listener cost instead of an expert percentile alone, so "strong" would mean "a listener would mind this", and the layers could be combined with weights that were measured rather than invented. The grade, if one appears, would sit on top of the profile and never replace it, because the trust in each layer still depends on how the performance was captured.
