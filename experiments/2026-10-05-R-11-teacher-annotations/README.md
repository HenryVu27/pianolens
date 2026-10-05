# R-11: teacher annotations vs the expert band and the report (pilot)

Ticket: R-11    Hypothesis: none of H1-H8 directly. Tests the plan's Localization metric
(section 4) and the premise of the report's expert band: where a teacher marks a MIDI-observable
demand, the expert consensus does it and the report notices its absence.    Status: Provisional
(pre-registered, not run)

Licence (BL-29): the tonebase material is subscription content with unclear terms. This README
carries counts and statistics only. Annotation text, encodings and the per-row operationalisation
stay in `data/interim/tonebase_annotations/` (gitignored).

## Question

Three teachers' annotated scores (tonebase, D-14) mark bars and notes of three Chopin pieces that
PianoCoRe tier A covers with hundreds of expert performances: Nocturne Op. 9 No. 2 (Claire Huangci;
2,011 tier A), Waltz Op. 64 No. 1 (Benjamin Laude; 832), Etude Op. 10 No. 4 (Marina Lomazov; 846).

- **(a)** Where a teacher marks a MIDI-observable demand, does the expert consensus do it more
  often than at matched unannotated bars of the same piece?
- **(b)** When the marked effect is removed from expert performances in the marked bars only, does
  the report flag those bars, and does it stay quiet on the untouched originals?
- **(c)** Descriptive: what share of teacher annotations can MIDI observe at all, by category?
- **(gate)** Can a second, blind encoder reproduce the encoding (agreement on one piece)?

## Falsified if

Pre-registered decision rules. "Row" = one encoded annotation in the primary set (defined in
Method). r = the row's null percentile (Method, (a)).

- **(a) supported**: mean r over primary rows >= 0.65 **and** its 95% bootstrap CI lower bound
  > 0.50 **and** at least 2 of 3 piece means > 0.50.
- **(a) not supported (falsified for this pilot)**: the CI upper bound < 0.65, that is, a
  localisation effect of the smallest size of interest is ruled out.
- **(a) inconclusive**: anything else.
- **(b) the report notices**: mean over (b)-primary rows of (hit rate on degraded minus flag rate
  on originals, same bars) >= 0.25 **and** CI lower bound > 0.10. **Does not notice**: CI upper
  bound < 0.25. Otherwise inconclusive. **Stays quiet**: pooled flag rate (notable or strong) on
  the untouched originals in the marked bars <= 0.10; otherwise "not quiet", reported with its
  Wilson CI next to the same channel's flag rate over all bars.
- **(c)** is descriptive: no decision rule.
- **Gate**: on the doubly encoded piece, category Cohen's kappa >= 0.60 (10 classes) and
  observable linearly weighted kappa >= 0.60 on matched rows, at least 80% of each encoder's rows
  matched, and identical PianoCoRe measures for at least 95% of edition bars. If the gate fails,
  (a)-(c) still run on encoder A's encoding but are labelled "encoding not reproducible", and the
  lead decides on a protocol revision.

**Reachability (R-09 lesson), checked before running.** Under no localisation effect, r is
uniform, so the mean of 23 primary rows has SD 0.289 / sqrt(23) = 0.060 and a 95% CI half-width
of about 0.12. Then "falsified" needs a mean below about 0.53 (probability about 0.69 under a true
0.50), and "supported" is likely (about 0.9) only for a true mean of about 0.75 or more. Per
piece (5 to 11 rows) every piece-level reading will be inconclusive; piece means are descriptive.
The t-interval over 3 piece means will be uninformative (2 degrees of freedom) and is reported,
not used. (b) will have few rows (only timing and dynamics rows in which the consensus follows
the mark), so "inconclusive" is the expected (b) outcome; this is a pilot.

## Data

- **Teacher annotations:** tonebase export 2026-10-01 (D-14, `pianolens.data.tonebase`), the three
  annotated-score PDFs listed in the protocol. Encoded under the protocol
  `data/interim/tonebase_annotations/PROTOCOL.md` (v1.2) by encoder A (ml-researcher, this
  session), blind to expert data and report output (see "Blindness record").
- **Scores:** PianoCoRe Zenodo v1.0 refined score MIDI (`score_PDMX_refined.mid` for the nocturne
  and the waltz, `score_ASAP_refined.mid` for the etude), measure numbers from MIDI time
  signatures (= `s_measure` in the tier A cache). Hands (staffs) from the PianoCoRe MusicXML
  (`score_xml_path`) matched to refined-score notes by unfolded onset and pitch; unmatched notes
  take the staff of the nearest matched note at the same onset, else of the nearest pitch.
- **Expert performances:** PianoCoRe tier A (D-07 cache `data/processed/pianocore_A/`), aligned
  pairs with label `match` only. Provenance (metadata counts, D-03 table): nocturne 2,011 tier A,
  0 Disklavier; waltz 832, 0 Disklavier; etude 846, 22 Disklavier (the ASAP rows). MAESTRO v3 has 1
  Disklavier nocturne Op. 9 No. 2, 0 of the waltz, 9 rows titled Etude Op. 10 No. 4 (overlapping
  ASAP). The tier A cache has no pedal.

### Encoding counts (encoder A, protocol v1.2)

154 rows: nocturne 44, waltz 58, etude 52. 24 of them are grouped fingering-digit or
harmonic-label rows (nocturne 8, waltz 12, etude 4).

| Category | NOC | WAL | ETU | All | observable yes | partly | no |
|---|---|---|---|---|---|---|---|
| voicing | 8 | 3 | 1 | 12 | 9 | 3 | 0 |
| dynamics | 3 | 2 | 4 | 9 | 6 | 3 | 0 |
| timing | 4 | 10 | 2 | 16 | 11 | 5 | 0 |
| articulation | 2 | 0 | 5 | 7 | 7 | 0 | 0 |
| pedal | 1 | 0 | 0 | 1 | 1 | 0 | 0 |
| evenness | 1 | 1 | 0 | 2 | 1 | 1 | 0 |
| character | 9 | 8 | 0 | 17 | 0 | 3 | 14 |
| fingering_physical | 13 | 12 | 9 | 34 | 0 | 0 | 34 |
| practice | 0 | 1 | 24 | 25 | 0 | 0 | 25 |
| analysis | 3 | 21 | 7 | 31 | 0 | 0 | 31 |
| **All** | 44 | 58 | 52 | 154 | 35 | 15 | 104 |

By piece, observable yes / partly / no: nocturne 14 / 7 / 23, waltz 12 / 5 / 41, etude 9 / 3 / 40.
Modality: 106 demand, 38 info, 8 option, 2 caution. Of the 50 observable rows, 3 restate a
printed marking and 5 partly restate one. `practice` and `analysis` are protocol additions to
the ticket's eight categories (merge rule in the protocol).

(a) eligibility from the frozen operationalisation of the 50 observable rows: 23 primary,
15 secondary, 12 excluded.

| | primary | secondary | excluded |
|---|---|---|---|
| NOC | 11 | 5 | 5 |
| WAL | 5 | 8 | 4 |
| ETU | 7 | 2 | 3 |

Primary rows by quantity: velocity 14 (NOC 8, WAL 4, ETU 2), inter-onset interval 4 (NOC 3,
WAL 1), key-down duration 5 (ETU). By category: voicing 9, dynamics 5, articulation 5, timing 4.
Exclusion reasons: global row (2), no testable sign (5: two "different from earlier", one
"different from neighbours", two low-level), no hairpin data in the score MIDI (2), no soft-pedal
data (1), no computable target (2, both anchored on an upbeat).

### Bar-map facts (edition bars to PianoCoRe measures)

- Nocturne: upbeat padded to a full 12/8 measure (PianoCoRe = edition + 1 for bars 0-31). The
  cadenza bar 32 spans PianoCoRe m33-36, and PianoCoRe bar lines after it are shifted by one
  quarter (edition 33 = m36 q5 to m37 q5; edition 34 = m37 q5 to m38).
- Waltz: PianoCoRe unfolds the repeat of bars 21-36 (edition bars 21-35 map to two measures each;
  both endings carry the printed number 36: first ending m36, second ending m52; edition 37-124 =
  m53-140). The trill bars 69-72 hold one note each in the score MIDI; the free run in 121-123 is
  spaced differently (the A natural of bar 123 sits at q1, not on the downbeat).
- Etude: upbeat padded to a full measure (PianoCoRe = edition + 1; edition 82 = m83).
- Every system start and every bar that carries a row was checked by pitch content
  (`<TAG>_barmap.csv`, `check` column); all 147 rows with bars have `conf_map` high or medium
  (4 medium).

## Splits

No model is fitted: every statistic is a fixed function of the score, the encoding and each
performance, so there is no train/test split and no leakage path through fitting. The unit of
inference is the annotation row; rows are clustered in pieces (3) and teachers (3, one per
piece), so pieces and teachers are confounded. Bootstrap: rows resampled within piece strata
(B = 10,000, seed 20261005); the t-interval over 3 piece means and leave-one-piece-out means are
reported next to it (R-08a lesson, six or fewer groups). Performances are not resampled for (a)
(f is a share over hundreds of performances; its sampling error is small next to the between-row
spread); for (b) performances are resampled within rows.

## Baselines

- **(a) Shuffled bar positions (the ticket's baseline), done exhaustively.** For each row, the
  same operationalised test is applied at every admissible unannotated position of the same piece
  (Method). r is the row's mid-rank percentile among those positions. No-effect value: r = 0.5.
- **(a) absolute level.** f_marked itself (share of experts doing it) and the share of primary
  rows with f_marked > 0.5 ("the consensus does what the teacher marks"), reported but not used
  for the decision: a high f at the marked bars can be generic (most bass notes are louder than
  the chords everywhere), which is what the shuffled baseline removes.
- **(b)** The same degradation applied at one admissible null position per performance (seeded):
  does the report flag the removal of teacher-marked effects more than the same removal at
  random bars? And the untouched original's flag rate (nominal about 5% notable, 1% strong per
  bar and channel).
- **Ceiling.** There are no per-rater labels for the expert side. The encoding's reliability is
  the inter-encoder agreement (gate); teacher-to-teacher agreement cannot be measured (one
  teacher per piece).

## Method

### Encoding (done before this pre-registration)

Protocol v1.2 (`data/interim/tonebase_annotations/PROTOCOL.md`): one row per demand, colour marks
only, mechanical anchor rules (edition bars from the marks or the text span, at least 20% of a
bar), a bar map per piece checked by pitch content, target notes as `hand:pitch@measure:q`
validated against the score dump, ten categories (the ticket's eight plus `practice` and
`analysis`), MIDI-observable yes / partly / no, direction and reference codes. Encoder A outputs:
`data/interim/tonebase_annotations/encoder_A/{NOC,WAL,ETU}_{barmap,annotations}.csv`.

### Gate: blind second encoding

The lead dispatches a second encoder (B), who gets only the protocol, the PDFs, the render and
score-dump scripts, and one piece (recommended: the nocturne, the piece with the most observable
rows and the cadenza bar-map case). B must not open `encoder_A/` or this README's results.
Matching: rows match when they are on the same PDF page, their anchor bars overlap (or both are
global), and their text token Jaccard >= 0.5, or their target sets have Jaccard >= 0.5, or both
are digit or label rows of the same system and hand; one-to-one greedy by highest Jaccard.
Reported: row counts, matched shares, category kappa (10 classes and the ticket's 8 after the
merge rule), observable weighted kappa, direction agreement on rows both call observable, target
Jaccard, exact `ed_bars` and `pc_measures` agreement, bar-map agreement over all edition bars,
and a bar x category presence kappa.

### (a) Expert consensus at marked bars

1. **Rows.** Encoder A's rows with observable yes or partly. Their per-row target and reference
   rules are frozen in `data/interim/tonebase_annotations/encoder_A/operationalisation_A.csv`
   (sha256 in `artifacts/prereg_sha256.txt`), written from the encoding fields before any expert
   data were loaded. **Primary set**: observable yes, modality demand or caution, quantity
   velocity, inter-onset interval or key-down duration, a direction with a sign, a reference that
   is not an earlier statement, not global, and a computable target at the anchor; duration rows
   only where at least 10 Disklavier or sensor performances exist (the etude's ASAP rows).
   Everything else that is observable is **secondary** (options, partly, earlier-statement
   references, pattern statistics, duration on transcribed MIDI) or **excluded** with its reason.
   A primary row drops to secondary at run time only by these mechanical checks: fewer than 10
   admissible null positions, or fewer than 50 performances (10 for Disklavier-only rows) with
   at least half the targets and one reference note matched.
2. **Per performance p, a signed effect E_p** (direction codes as in the protocol):
   - velocity contrast (LOUDER / SOFTER_THAN_REF): mean velocity of targets minus mean of
     reference notes (sign flipped for SOFTER). Reference by code: `same_onset` = the other notes
     at the targets' onsets; `same_beat_same_hand` = other notes of the target's staff in the
     same notated beat (dotted quarter in 12/8, quarter otherwise); `same_bar` = other notes of
     the target's staff in the same measures; `neighbour_bars` = notes of the same staff at the
     same within-measure onset in the measures before and after. Row rules override.
   - CRESC / DIM: OLS slope of velocity on score onset over the targets (sign flipped for DIM).
   - LENGTHEN_IOI_AT: for each target, log(IOI to the next score position / notated IOI) minus
     the median of the same quantity over the other score positions within +-1 measure; mean over
     targets.
   - SLOWER / FASTER_THAN_REF, ACCEL_TO_TEMPO: log seconds per notated quarter of the marked
     measures (or span S) minus that of the reference measures (neighbours, or P), signed so that
     the teacher's direction is positive.
   - SHORTER / LONGER_DURATION (reference `notated`): r_p = median over targets of key-down
     duration / notated duration in seconds at the local tempo (median seconds per quarter over
     +-1 measure). Expected direction: r_p < 0.75 (shorter) or r_p >= 0.90 (longer).
   Repeated passes (waltz) are averaged within a performance. A performance enters a row when at
   least half its targets and one reference note are matched.
3. **Row statistic**: f = share of performances in the expected direction (E_p > 0, ties count
   half; duration rows by the r_p thresholds).
4. **Null positions (shuffled bar positions)**: transplant the row's targets and references to
   every other position: each target note keeps its staff, its onset relative to the start of
   its measure (relative measure offset for multi-measure rows) and its pitch rank within its
   staff at that onset (from the top for the upper staff, from the bottom for the lower staff).
   A position is admissible when its measures have the same time signature, carry no encoder-A
   row with observable yes or partly (anchor or extent, any category), are not in the nocturne
   cadenza region (m33-38) or the waltz trill bars (m85-88), and at least half the targets and one
   reference note exist there. Span rows use windows of the same length. r = (number of null
   positions with f below f_marked + half the ties) / number of admissible positions.
5. **Primary statistic**: the mean of r over primary rows (each row weighted equally), with the
   stratified bootstrap CI; also per piece, leave-one-piece-out, the t-interval over piece means,
   and the mean of f_marked and the share of rows with f_marked > 0.5.
6. **Breakdowns** (descriptive): by category, by quantity, by `restates_print` (a printed marking
   at the same place makes consensus likelier and is a weaker test), by provenance: velocity rows
   on the etude are also computed on its 22 Disklavier performances only; the nocturne's single
   MAESTRO Disklavier performance is reported as its own E per row; duration rows on transcribed
   MIDI (secondary) next to the etude's Disklavier rows.
7. **Secondary rows**: same statistics, reported separately; options are expected to have lower f
   (an option is not a consensus claim).
8. **Sensitivity**: for the doubly encoded piece, (a) is rerun with encoder B's rows where B's
   fields permit (B's rows operationalised by the same generic rules, row-specific rules only
   where B's targets match A's).

### (b) Report sensitivity to removing the marked effect

1. **Rows**: primary (a) rows with f_marked > 0.5, split by channel coverage. Timing rows map to
   the report's per-bar tempo-shape channel; dynamics rows to the per-bar loudness-shape channel
   ((b)-primary set = these two). Voicing rows map to the loudness channel only indirectly (the
   channel smooths velocity across voices) and are reported separately. Articulation (duration)
   rows have no report channel and are counted as "uncovered".
2. **Performances**: per piece, K = 20 tier A performances (seed 20261005; for the etude the 22
   Disklavier performances are drawn first, then transcribed ones); K drops to 10 if one report
   run takes more than 60 s on this Mac. Each report excludes the performance from its own
   references (`ReferenceSet.exclude`, as the report already does).
3. **Degradations** (marked measures only; nothing else changes):
   - velocity contrast: each matched target's velocity set to the mean velocity of its matched
     reference notes in that performance;
   - CRESC / DIM: target velocities set to their mean;
   - LENGTHEN_IOI_AT: the IOI after each target shrunk to the local reference IOI (the median
     normalised IOI used in (a) times the notated IOI); later notes and pedal events shifted by
     the difference;
   - SLOWER / FASTER_THAN_REF: the marked measures re-timed to the mean seconds per quarter of the
     reference measures; later events shifted.
4. **Outcomes per (row, performance)**: hit = a notable or strong flag in the row's channel in any
   marked measure of the degraded performance; false alarm = the same on the untouched original;
   null hit = flag in the null measures after the same degradation at one admissible null position.
5. **Statistics**: per row, hit rate, false-alarm rate and null-hit rate over K; primary = mean
   over (b)-primary rows of (hit - false alarm), bootstrap over rows within pieces with
   performances resampled within rows (B = 10,000); secondary = mean (hit - null hit). "Stays
   quiet" uses the pooled false-alarm rate (rule above), next to the original's flag rate in the
   same channel over all bars. Loudness flags on transcribed references are low confidence in the
   report; they are counted (the flag exists in the data) and the report's `velocity_confidence`
   is reported per piece.
6. If the report cannot be built for a piece (for example too few tier D references), that piece
   is out of (b) and the reason is recorded.

### (c) Observability shares

Share of rows with observable yes, partly, no, per category and per piece, with Wilson 95%
intervals, in three views: all 154 rows; without the 24 grouped digit and label rows; the
ticket's eight categories after the merge rule. Also by modality. For the doubly encoded piece,
the same shares from encoder B and the observable kappa.

## Command

Code is written after this pre-registration and implements it as written; any deviation goes in
a "Deviations" section before results. Planned entry points:

```
uv run python experiments/2026-10-05-R-11-teacher-annotations/run.py gate --b-dir data/interim/tonebase_annotations/encoder_B
uv run python experiments/2026-10-05-R-11-teacher-annotations/run.py a
uv run python experiments/2026-10-05-R-11-teacher-annotations/run.py b
uv run python experiments/2026-10-05-R-11-teacher-annotations/run.py c
```

Encoding aids already in this folder: `render_pages.py` (PDF pages to PNG plus positioned text),
`score_dump.py` (PianoCoRe score measures). Encoder A's files are regenerated by
`uv run python data/interim/tonebase_annotations/encoder_A/build_encoder_A.py` and
`.../build_operationalisation_A.py`.

Run record to fill in: git commit (pre-registered on `dd13ab2` with an uncommitted working tree),
seeds (20261005), wall time, library versions.

## Threats to validity (named before running)

1. **Transcribed velocity.** Nocturne and waltz tier A have no Disklavier performances, so every
   velocity row there rests on transcription velocities (Aria-AMT, Transkun V2, ATEPP, ByteDance).
   Contrasts within a performance are less exposed than levels, but transcribers blur inner-voice
   and chord-note velocities, which is where most voicing rows sit. Provenance is reported per
   row; the etude's Disklavier subset is the only key-sensor check; the nocturne has one MAESTRO
   Disklavier performance. Durations on transcribed MIDI are not trusted (R-09 noise floor) and
   are secondary.
2. **Pilot size.** Three pieces, three teachers, one teacher per piece: piece and teacher are
   confounded, and nothing here generalises to teachers or repertoire. 23 primary rows.
3. **Single encoder who also wrote the protocol and this analysis.** The gate measures
   reproducibility on one piece only; the other two pieces rest on encoder A. Encoder A saw the
   PDFs (not expert data) before writing the operationalisation.
4. **Score mismatches.** The PianoCoRe score MIDI differs from the edition in the nocturne cadenza
   (shifted bar lines), the waltz run (bars 121-123) and trill bars, and the waltz quadruplet
   (bar 44) is unevenly spaced in the score MIDI itself. Rows touching these places are marked;
   the null excludes the cadenza and trill regions. Alignment quality in the cadenza is unknown.
5. **Restated markings.** Some marks repeat a printed hairpin or accent; consensus there is
   expected from the print, not from the teacher. Broken down by `restates_print`.
6. **Conservative null.** Unannotated bars can carry the same effect (teachers comment sparsely),
   which pulls r towards 0.5; a null r is "no more than elsewhere", not "experts ignore it".
7. **Pedagogical register.** Many marks address learners (practice, fingering, analysis), and
   the etude's edition is a technique course: low observability there is partly a property of the
   course, not of teaching in general.
8. **Report channels.** The report flags tempo and loudness shapes per bar after smoothing; it
   has no voicing or articulation channel, so (b) can only test timing and dynamics rows. Loudness
   flags on transcribed references are low confidence in the report itself.
9. **Hand assignment.** Staffs come from the MusicXML matched to the refined score MIDI; cross-
   staff writing and mismatches put some notes in the wrong reference set.

## Blindness record

Before this pre-registration was hashed, for these three pieces: loaded the PianoCoRe refined
score MIDI only (`score_dump.py`), dataset metadata counts (`piece_ids.parquet`
`n_performances`, PianoCoRe index rows to find the score paths, MAESTRO csv titles) and the
source code of `pianolens.report.build` and `pianolens.study.degrade` (no output). No
performance MIDI, alignment, tier A cache file, expert-band feature or report output was loaded.

<!-- end of pre-registration: sha256 of everything above this line is in artifacts/prereg_sha256.txt -->

## Run record (2026-10-05)

- Pre-registration verified before any expert data were loaded: the section above the end
  marker hashes to `390903481b69...29ca`, and every input hash in `artifacts/prereg_sha256.txt`
  checks OK. Encoder B's files (nocturne, blind, from a copied packet outside the repo) were
  hashed at the start of the gate step and appended to the same file.
- Lead decision (DECISIONS 2026-10-05): the `practice` and `analysis` categories are accepted.
- Code: `run.py` (gate, (c), drivers), `part_a.py`, `part_b.py`. Commands as registered:
  `uv run python experiments/2026-10-05-R-11-teacher-annotations/run.py {gate,a,b,c}`.
- Git: `dd13ab2` with an uncommitted working tree (many files changed by other tickets; nothing
  here is committed). Python 3.12.15, numpy 2.5.3, pandas 3.0.6, scipy 1.18.1, partitura 1.9.0.
  Seed 20261005 for every bootstrap and draw.
- Wall time on this Mac: gate under 5 s, (a) 25 s, (c) under 5 s, (b) about 13 min.
- Reproducibility: after behaviour-neutral lint edits, gate, (a) and (c) outputs were rerun and
  are byte-identical (`gate.json`, `a_rows.csv`, `a_summary.json`, `a_rows_encoderB_NOC.csv`,
  `c_summary.json`). **Reproduction of (b):** a full rerun after the lint edits gave
  byte-identical `b_rows.csv`, `b_summary.json` and `b_original_bars.csv` (first run kept as
  `*_run1`).
- Outputs: `artifacts/gate.json`, `a_rows.csv`, `a_summary.json`, `a_rows_encoderB_NOC.csv`,
  `b_rows.csv`, `b_original_bars.csv`, `b_summary.json`, `c_summary.json` (ids, codes and
  numbers only).

## Deviations and implementation choices (disclosed after the run; the timing of each fix is stated)

1. **Gate, digit and label rows.** The registered matching allows "both digit or label rows of
   the same system and hand"; hand is not a schema field. Implemented as: both rows have `digits`
   (or both `labels`) in `mark_type`, same page, overlapping anchor bars; ranked by the Jaccard of
   their bar sets. 5 of 41 matches used this rule.
2. **Gate, bar-map key (fixed after a printed gate fail).** The first gate run (16:50:00 UTC)
   printed all five criteria and `gate_pass False`: four passed, and the bar map showed 0.0 over
   70 merged rows. The fix followed 8 s later. The 0.0 was an outer merge with no key overlap:
   encoder A wrote an empty `pass` for bars played once, B wrote `1`. Empty is now read as
   pass 1, and the registered rule (identical PianoCoRe measures per edition bar) is unchanged.
   The auditor's independent comparison by edition bar also gives 35 of 35 identical
   PianoCoRe measures.
3. **(a) sensitivity with encoder B, set assignment (fixed after a printed result).** My first
   run used A's primary/secondary set for B rows whose targets matched A's. It printed 7 rows,
   mean r 0.504 [0.248, 0.766].
   - The registered method takes the set from B's own fields, and only the target and
     reference rule from A. After the fix, NOC-B-038 (r = 0.000; B coded it observable
     "partly") moved from primary to secondary, and the mean became 0.588 (6 rows). The fix
     follows the registered text, but it moved the estimate up by 0.084.
   - The fix also carries A's frozen "anchor not computable" exclusions over to B rows with the
     same targets. That carry-over is not registered. It touches only NOC-B-003, which has no
     implementation, so it changes no number.
4. **(a) the nocturne's MAESTRO Disklavier performance was not analysed.** It is not in
   PianoCoRe tier A, and using it would need a new alignment. Registered as a descriptive item;
   dropped.
5. **(a) null positions.** The registered rule fixes when a position is admissible but not a
   minimum number of performances there. f at a null position uses every performance with the
   template matched (at least one).
6. **(b) report path.** The registered "report" is the report's per-bar tempo-shape and
   loudness-shape channels. I ran exactly that code (`pianolens.report.build.
   _interpretation_section`, notable = 95th, strong = 99th percentile) and not the whole
   `build_report`, whose other channels (notes, control, shaping) play no part in (b). Every
   version is built with the same arithmetic as `target_from_notes`, on the reference grid:
   original, degraded and null-degraded. On unmodified notes this reproduces
   `target_from_references` tiers exactly (3 nocturne performances, both channels, 100%
   agreement). The building on the reference grid was needed because performances whose matched
   notes do not span the whole score made `interpret` reject the target.
7. **(b) measure-to-bar mapping.** The PianoCoRe reference set has no bar for measures without
   notes (waltz trill bars: 137 bars for 140 measures) and starts bar 1 at the first note. Marked
   measures are mapped to report bars by start beat, not by `measure - 1`. A first attempt with
   `measure - 1` crashed on the waltz; no output from it was used.
8. **(b) LENGTHEN degradation.** "IOI shrunk to the local reference IOI" is applied only when the
   performed IOI is longer than the reference (no change otherwise). SLOWER re-timing is always
   applied. K stayed 20 (about 2.5 s per run, under the 60 s rule). The etude sample is 20 of its
   22 Disklavier performances; nocturne and waltz samples are transcribed.
9. **(b) rows.** Primary (a) rows with status ok and f_marked > 0.5. (b)-primary = 6 timing or
   dynamics rows (nocturne 4, waltz 1, etude 1); voicing = 3 rows, reported separately; the 5
   articulation rows are uncovered.

## Results

### Gate (nocturne, encoder A 44 rows vs encoder B 45 rows): PASS

| Measure | Value | Gate |
|---|---|---|
| Rows matched | 41 (A 0.932, B 0.911) | >= 0.80 each: pass |
| Category kappa, 10 classes (matched rows) | 0.970 (bootstrap [0.906, 1.000]) | >= 0.60: pass |
| Category kappa, ticket's 8 | 0.969 | |
| Observable, linearly weighted kappa | 0.865 ([0.741, 0.969]); raw agreement 0.878 | >= 0.60: pass |
| Direction agreement, rows both call observable | 0.95 (n = 20) | |
| Target Jaccard, rows both with targets | 0.769 (n = 13) | |
| Anchor edition bars identical / PianoCoRe measures identical | 1.000 / 0.976 | |
| Bar map, identical PianoCoRe measures (35 edition bars) | 1.000 (also identical quarter offsets) | >= 0.95: pass |
| Bar x category presence kappa (38 measures x 10) | 0.909 | |

Bootstrap intervals on the kappas are descriptive (not registered). Disagreements on matched
rows: 1 category (voicing vs dynamics) and 5 observable (yes vs partly, in both directions).
Unmatched: 3 A rows and 4 B rows. Three of these are the same texts anchored to different systems
under the vertical-gap rule (one of them is the primary timing row NOC-A-027); one is a B split
of a text A kept whole. Without the bar-overlap requirement, 44 rows match (A 1.000, B 0.978).
Encoder B's notes, read only after agreement was computed, confirm the cause. The gap rule gave
near ties (106 vs 109 px, 21 vs 25 px), and the result depends on whether the gap is measured
locally or across the page. This is a protocol limitation (see Threats), not a reason to recode.

### (a) Expert consensus at marked bars vs shuffled positions: INCONCLUSIVE

Primary set: 23 registered rows. 18 were evaluable. 4 nocturne rows fell to "fewer than 10
null positions" by the registered mechanical rule: the nocturne has only 15 unannotated measures,
so multi-bar and some single-bar templates find few positions. WAL-A-031 had no computable
reference set: the waltz MusicXML puts the LH chords of those bars in the upper part.

| | n rows | mean r | 95% CI | other |
|---|---|---|---|---|
| **All pieces (primary statistic)** | 18 | **0.634** | bootstrap [0.503, 0.750]; t over 3 piece means [0.385, 0.878] | 14 of 18 rows have r > 0.5; one-sided t p = 0.034 vs 0.5 (descriptive) |
| Nocturne | 7 | 0.539 | | leave-out: without NOC 0.694 |
| Waltz | 4 | 0.620 | | without WAL 0.638 |
| Etude | 7 | 0.736 | | without ETU 0.568 |
| Baseline (no localisation) | | 0.500 | | |
| Absolute: mean f_marked / share of rows f_marked > 0.5 | 18 | 0.620 / 0.667 | | mean null-median f 0.540 |

Decision by the registered rule: the mean of 0.634 is below 0.65, so not "supported". The CI
upper bound of 0.750 is not below 0.65, so not "falsified". **Inconclusive.** Post-run
reachability check: the row SD of r was 0.292 (0.289 assumed), and the CI half-width was about
0.12, as registered. The between-piece SD of the piece means was 0.099.

Primary rows (ids only; f = share of expert performances in the teacher's direction, r = null
percentile):

| Row | Category | Quantity | Status | f_marked | n perf | n null | null median f | r |
|---|---|---|---|---|---|---|---|---|
| NOC-A-004 | dynamics | velocity | ok | 0.274 | 1830 | 15 | 0.409 | 0.267 |
| NOC-A-005 | voicing | velocity | too few null (4) | 0.616 | 1990 | 4 | | |
| NOC-A-011 | timing | IOI | ok | 0.521 | 1992 | 15 | 0.377 | 0.600 |
| NOC-A-015 | dynamics | velocity | ok | 0.622 | 1998 | 15 | 0.535 | 0.933 |
| NOC-A-018 | voicing | velocity | ok | 0.043 | 1911 | 14 | 0.041 | 0.571 |
| NOC-A-021 | voicing | velocity | too few null (6) | 0.131 | 2004 | 6 | | |
| NOC-A-027 | timing | IOI | ok | 0.944 | 2008 | 15 | 0.573 | 0.800 |
| NOC-A-037 | dynamics | velocity | ok | 0.284 | 1945 | 15 | 0.578 | 0.000 |
| NOC-A-039 | timing | IOI | ok | 0.678 | 1805 | 15 | 0.590 | 0.600 |
| NOC-A-040 | voicing | velocity | too few null (2) | 0.859 | 1827 | 2 | | |
| NOC-A-044 | voicing | velocity | too few null (6) | 0.899 | 1535 | 6 | | |
| WAL-A-023 | voicing | velocity | ok | 0.949 | 810 | 13 | 0.924 | 0.692 |
| WAL-A-031 | voicing | velocity | anchor not computable | | | | | |
| WAL-A-041 | timing | IOI | ok | 0.496 | 832 | 44 | 0.619 | 0.295 |
| WAL-A-052 | dynamics | velocity | ok | 0.622 | 774 | 73 | 0.535 | 0.849 |
| WAL-A-055 | voicing | velocity | ok | 0.918 | 823 | 45 | 0.899 | 0.644 |
| ETU-A-006 | articulation | duration (Disklavier) | ok | 1.000 | 22 | 16 | 1.000 | 0.625 |
| ETU-A-007 | articulation | duration (Disklavier) | ok | 0.619 | 21 | 39 | 0.409 | 0.667 |
| ETU-A-008 | articulation | duration (Disklavier) | ok | 1.000 | 22 | 35 | 0.545 | 0.886 |
| ETU-A-014 | dynamics | velocity | ok | 0.965 | 811 | 33 | 0.553 | 0.939 |
| ETU-A-035 | articulation | duration (Disklavier) | ok | 0.238 | 21 | 15 | 0.000 | 1.000 |
| ETU-A-039 | articulation | duration (Disklavier) | ok | 0.000 | 22 | 39 | 0.273 | 0.128 |
| ETU-A-040 | voicing | velocity | ok | 0.983 | 838 | 33 | 0.860 | 0.909 |

Breakdowns (evaluable primary rows; descriptive):
- **By category:** articulation 5 rows, mean r 0.661; dynamics 5, 0.598; timing 4, 0.574;
  voicing 4, 0.704.
- **By quantity:** duration 0.661, IOI 0.574, velocity 0.645.
- **By whether the print already says it:** rows that restate a printed marking 0.894 (n = 2),
  partly 0.800 (n = 2), not at all 0.573 (n = 14). The rows where the teacher adds something
  the print lacks are close to the null.
- **Provenance:** for the etude velocity rows on the 22 Disklavier performances only,
  ETU-A-014 f = 1.000, r = 0.970 and ETU-A-040 f = 1.000, r = 0.894 (all tier A: 0.965 / 0.939
  and 0.983 / 0.909).
- **Secondary rows:** 8 evaluable, mean r 0.457 [0.270, 0.632]. The 6 waltz rows give 0.610;
  waltz option rows WAL-A-003 and WAL-A-014 have r 0.915 and 0.972.
- **Sensitivity, encoder B's nocturne rows:** 6 evaluable primary rows, mean r 0.588 [0.336,
  0.841], against A's nocturne 0.539 (7 rows). B's anchor for the text of A's primary timing row NOC-A-027 sits one
  system earlier: f 0.988, r 1.000 there, against A's anchor f 0.944, r 0.800. Both anchors are
  bars where experts slow down.

### (b) Report tempo/loudness tiers after removing the marked effect: DOES NOT NOTICE; stays quiet (point estimate)

| | n rows | mean | 95% CI | decision |
|---|---|---|---|---|
| (b)-primary: hit on degraded - flag on original, same bars | 6 | **0.057** | bootstrap [-0.001, 0.116]; t over rows [-0.095, 0.212] | CI upper < 0.25: **does not notice** |
| hit at marked bars - hit at a random admissible position | 6 | 0.039 | [-0.047, 0.117] | |
| Voicing rows (indirect, loudness channel): hit - flag on original | 3 | -0.033 | [-0.150, 0.083] | |
| Flag rate on untouched originals in the marked bars (pooled) | 120 row-performances | 0.050 | Wilson [0.023, 0.105] | <= 0.10: **stays quiet** (upper bound 0.105) |
| Same originals, flag rate over all bars | | tempo 0.038, loudness 0.062 | | |

Per row (hit / flag on original / null hit):
- NOC-A-011: 0.05 / 0.05 / 0.00
- NOC-A-015: 0.10 / 0.10 / 0.05
- NOC-A-027: 0.05 / 0.00 / 0.18
- NOC-A-039: 0.00 / 0.00 / 0.00
- WAL-A-052: 0.00 / 0.05 / 0.00
- ETU-A-014: 0.45 / 0.10 / 0.20
- Voicing rows: WAL-A-023 0.05 / 0.20, WAL-A-055 0.05 / 0.00, ETU-A-040 0.15 / 0.15.

Here "the report" means its tempo- and loudness-shape tiers: per bar, plus the window-level
too-flat / too-extreme tiers, which changed in 0 of 117 degradations (auditor check). Its other
channels play no part. The registered bootstrap stratifies by piece; the waltz and etude strata
hold one row each, so the t-interval over rows is reported next to it.

Gain sweep (auditor, same 20 performances per piece). g = 1 is the registered removal; g = 3
reverses the performer's own effect at 2x; g = 5 reverses it at 4x. At g = 1 the sweep
reproduces every hit rate above.

| Row | Notes changed (g = 1) | hit g = 1 | g = 3 | g = 5 | flag on original |
|---|---|---|---|---|---|
| ETU-A-014 | 1.00 | 0.45 | 0.95 | 0.95 | 0.10 |
| NOC-A-027 | 1.00 | 0.05 | 0.75 | 0.75 | 0.00 |
| NOC-A-011 | 0.75 | 0.05 | 0.05 | 0.10 | 0.05 |
| NOC-A-015 | 0.85 | 0.10 | 0.15 | 0.15 | 0.10 |
| NOC-A-039 | 0.47 | 0.00 | 0.00 | 0.00 | 0.00 |
| WAL-A-052 | 0.94 | 0.00 | 0.00 | 0.06 | 0.06 |
| Voicing WAL-A-023 / WAL-A-055 / ETU-A-040 | 1.00 | 0.05 / 0.05 / 0.15 | 0.20 / 0.10 / 0.20 | 0.35 / 0.15 / 0.25 | 0.20 / 0.00 / 0.15 |

- 4 of the 6 (b)-primary rows stay at 0.15 or less even reversed at 4x: one or two IOIs, one
  note's velocity, a three-note slope. For these rows "does not notice" is a property of the
  smoothed per-bar channels.
- Only the two bar-level rows (NOC-A-027, ETU-A-014) can be flagged.
- Reversing every effect at 2x would give a pooled statistic of only 0.266. The registered 0.25
  bar was barely reachable with this row mix.
- The 120 original flags are not independent: the four nocturne rows share the same 20
  performances.

### (c) Observability (encoder A; Wilson 95% intervals)

| View | n | yes | partly | no |
|---|---|---|---|---|
| All rows | 154 | 0.227 [0.168, 0.300] | 0.097 [0.060, 0.154] | 0.675 [0.598, 0.744] |
| Without the 24 digit / label rows | 130 | 0.269 [0.200, 0.351] | 0.108 [0.065, 0.173] | 0.623 [0.537, 0.702] |
| Demands only (modality demand) | 106 | 0.264 [0.190, 0.355] | 0.132 [0.080, 0.210] | 0.604 [0.509, 0.692] |

By category (all rows), yes / partly / no:

| Category | n | yes | partly | no |
|---|---|---|---|---|
| articulation | 7 | 7 | 0 | 0 |
| voicing | 12 | 9 | 3 | 0 |
| timing | 16 | 11 | 5 | 0 |
| dynamics | 9 | 6 | 3 | 0 |
| pedal | 1 | 1 | 0 | 0 |
| evenness | 2 | 1 | 1 | 0 |
| character | 17 | 0 | 3 | 14 |
| fingering_physical | 34 | 0 | 0 | 34 |
| practice | 25 | 0 | 0 | 25 |
| analysis | 31 | 0 | 0 | 31 |

With the ticket's 8 categories (practice merged into fingering_physical and analysis into
character): character 48 rows, 0 / 3 / 45; fingering_physical 59 rows, 0 / 0 / 59.

By piece, yes / partly / no:
- nocturne 14 / 7 / 23
- waltz 12 / 5 / 41
- etude 9 / 3 / 40

The nocturne observable share:
- encoder A: 0.318 yes, 0.159 partly;
- encoder B: 0.244 yes, 0.244 partly;
- agreement: weighted kappa 0.865.

## Verdict (Confirmed with caveats, eval-auditor 2026-10-05)

Audited 2026-10-05 (eval-auditor): **Confirmed with caveats**. The labels stand. The README text
needs the fixes listed in the Audit section, chiefly the (a) direction sentence, the waltz hand
sensitivity, the (b) reachability and the timing of deviations 2 and 3.

- **Gate: passed.** The encoding is reproducible on the nocturne (category kappa 0.97,
  observable kappa 0.87, bar map identical). The one weak rule is the vertical-gap anchor for
  text between systems.
- **(a): inconclusive; no direction claim.**
  - Point estimate: mean null percentile 0.634 on 18 rows. Registered bootstrap [0.503, 0.750];
    t-interval over rows [0.489, 0.779]. 2 of 3 piece means are above 0.5.
  - That is short of the registered 0.65 bar, and not ruled out. The registered bootstrap
    lower bound is the only interval that excludes 0.5.
  - Rows that do not restate a printed marking: 0.573 [0.426, 0.701] (14 rows).
  - Sensitivities (auditor), all still inconclusive:
    - waltz hands corrected (LH chords moved to the lower staff): 0.598 [0.471, 0.714]
      (19 rows; waltz mean 0.620 to 0.486; WAL-A-031 evaluable at r 0.176);
    - null pool admitting annotated bars outside the row's own window: 0.589 [0.469, 0.701]
      (21 rows);
    - both changes: 0.576 [0.460, 0.685] (22 rows).
- **(b): the report's tempo and loudness tiers do not notice (per-bar tiers, and window tiers
  per the audit).**
  - Removing a teacher-marked effect that a majority of experts show (f 0.52-0.97) raised the
    flag rate in the marked bars by 0.057 over the untouched originals: registered bootstrap
    [-0.001, 0.116], t-interval over the 6 rows [-0.095, 0.212]. Both are below the 0.25 of
    interest.
  - The auditor's gain sweep shows 4 of the 6 rows cannot be flagged by these channels at any
    tested gain, even with the effect reversed at 4x. Only the two bar-level rows can be
    flagged (0.75-0.95 when reversed at 2x), so the 0.25 bar was barely reachable with this
    row mix.
  - The untouched originals are flagged at 0.050 (Wilson [0.023, 0.105]), which is the
    calibration target of the q95 tiers. This is a calibration check, not evidence of
    specificity to teacher bars.
- **(c):** about a third of these teacher annotations are MIDI-observable at least in part
  (0.325 yes or partly; 0.377 without digit and label rows). Every voicing, timing, dynamics,
  articulation, pedal and evenness annotation is observable at least in part, and no character, fingering, practice or
  analysis annotation is, except 3 character rows that are partly observable.

Pilot scope: three pieces and three teachers, one teacher per piece. eval-auditor signed off on
2026-10-05: Confirmed with caveats (see Audit).

## Threats realised

1. **Hands.** The waltz MusicXML is two single-staff parts. Its upper part holds the LH chords
   in 19 measures (62 notes: m29-33, 45-49, 117-121, 133-136), where the lower part has one note
   per bar.
   - WAL-A-031 lost its reference set, and the other waltz voicing rows compared against too
     few lower-staff notes.
   - With these notes moved to the lower staff (auditor heuristic: upper-part notes below MIDI
     70 in those measures):
     - WAL-A-031 becomes evaluable at r 0.176;
     - WAL-A-023 falls from 0.692 to 0.588, and WAL-A-055 from 0.644 to 0.521;
     - the waltz mean falls from 0.620 to 0.486;
     - the pooled (a) mean becomes 0.598 [0.471, 0.714] (19 rows).
   - In the nocturne, 21 of 1,243 notes (the cadenza) took a fallback staff.
2. **Small null pool.** The nocturne has 15 unannotated measures, which cost 4 primary rows.
   Single-bar nocturne rows have r in steps of about 1/15.
3. **Transcribed velocity.** All nocturne and waltz velocity rows are transcribed. The etude
   Disklavier split agrees with all tier A on both velocity rows.
4. **Anchor ambiguity.** One primary timing row moves by one system between encoders. Both
   placements land on bars where experts slow down, so (a) for that row does not depend on it.
5. **Report resolution.** (b) shows that the per-bar loudness and tempo channels cannot see
   note-level or single-IOI removals. This was named before running and is now measured.
6. **The registered (b) rule depends on (a).** Only rows the consensus follows enter (b). With
   6 rows, (b) is a pilot measurement.

## Post-audit corrections (2026-10-05)

Text only, applying the six required fixes from the Audit below. No rerun; no number in the
artifacts changed. The pre-registered section (hash unchanged) and the Audit section were not
edited. The copy before these edits is `artifacts/README_pre_postaudit.md`.

1. Deviation 2 now states that the bar-map fix followed a printed `gate_pass False` (8 s
   later), and cites the auditor's independent 35-of-35 check.
2. Deviation 3 now reports the pre-fix encoder B sensitivity (7 rows, 0.504 [0.248, 0.766]), the
   row the fix moved (NOC-B-038, r 0.000), and the unregistered carry-over rule (no number
   changes).
3. The Deviations heading now says the section was disclosed after the run.
4. The (a) verdict drops the direction sentence. It gives the point estimate with the t-interval
   over rows [0.489, 0.779], the non-restating rows 0.573 [0.426, 0.701], and the auditor's
   sensitivities: waltz hands 0.598 [0.471, 0.714]; null pool 0.589; both 0.576 [0.460, 0.685].
   All are inconclusive.
5. Threats realised 1 now quantifies the waltz hand problem (19 measures, 62 notes; WAL-A-031
   r 0.176; waltz mean 0.620 to 0.486).
6. (b):
   - adds the auditor's gain sweep and the t-interval over rows [-0.095, 0.212];
   - scopes "the report" to its tempo/loudness tiers;
   - replaces "experts share" with "a majority of experts show (f 0.52-0.97)";
   - replaces the earlier 5-performance positive check with the sweep.

## Audit (2026-10-05)

Auditor: eval-auditor. **Verdict: Confirmed with caveats.** Every registered label follows from
the registered rules and reproduces: gate pass, (a) inconclusive, (b) "does not notice" and
"stays quiet", (c) descriptive. The caveats change how (a) and (b) are explained, and three
statements about when fixes were made are inaccurate. Required fixes are listed at the end. This
section carries ids, counts and statistics only (BL-29).

**Pre-registration and order.** The text above the end marker hashes to `390903481b69...29ca`
(identical to `artifacts/prereg_section.md`). All 15 input hashes in `prereg_sha256.txt` check
OK, and the encoder B hashes match the lead's prefixes. Order in the author transcript
(`agent-a278c06becfb7bc29`, times UTC):
- prereg written 16:28:24, hashed in the same minute (file header 11:28 CDT);
- encoder B ran 16:33-16:48 (`agent-a25bcee0832fdf633`);
- B's files arrived 16:48:33 and were hashed at 16:48:51;
- first gate run 16:50:00, bar-map fix 16:50:08, B's notes read 16:50:14;
- first (a) run 16:57;
- (b) results 17:45;
- run record and deviations written from 17:49.

So nothing about the encoding or the operationalisation changed after expert data were loaded.
Encoder B was blind in practice: its 37 tool calls all stay inside the copied packet folder, and
it opened no repo path. Its prompt did contain the repo path once, inside the instruction never
to access it. That is a minor departure from the R-08a rule ("never receive a repo path"), with
no consequence here.

**Reproduction.** I reran gate, (a) and (c) into a scratch folder (`run.ART` patched; inputs
read-only). `gate.json`, `a_rows.csv`, `a_summary.json`, `a_rows_encoderB_NOC.csv` and
`c_summary.json` are byte-identical. A full (b) rerun gives byte-identical `b_rows.csv`,
`b_summary.json` and `b_original_bars.csv`. Every number in Results matches the artifacts.

**Deviations: were the fixes blind?**
- **Dev. 2 (gate bar map).** The README says "bug fixed before reading the gate outcome". That
  is not accurate. The first gate run printed all five criteria and `gate_pass False`: four
  passed, and the bar map showed 0.0 over 70 merged rows. The key fix came 8 s later. The fix
  is still correct and changes no conclusion:
  - the 0.0 was an outer merge with no key overlap (35 + 35 rows; A's `pass` is empty, B's is
    `1`);
  - my own comparison by edition bar gives 35 of 35 identical PianoCoRe measures.
- **Dev. 3 (B sensitivity).** The first run was printed before the fix: 7 rows, mean r 0.504
  [0.248, 0.766]. The fix takes each B row's set from B's own fields, as registered. It moved
  one row, NOC-B-038 (r = 0.000, which B coded observable "partly"), from primary to secondary,
  and the mean rose to 0.588 (6 rows). The fix follows the registered text, but "only the
  corrected numbers are reported" hides that the fix moved the estimate up by 0.084. The added
  carry-over of A's "not computable" exclusions is not registered. It touches only NOC-B-003,
  which has no implementation, so no number changes.
- **Dev. 7 / grid target in (b).** These came before any (b) result. The first (b) launch was
  killed after 1 of 20 nocturne performances, and the second crashed in the waltz. Neither
  printed a statistic.
- **Section heading.** "Written before the results below were interpreted" does not match the
  transcript: the section was written after (a) and (b) were seen. Each fix's timing is now
  recorded above.

**Gate.** The registered pass holds. Two limits:
- Rows are matched mainly by token Jaccard of the transcribed teacher text (35 of 41 matches).
  The kappas therefore measure agreement on fields once the same text is found, which is what
  was registered.
- The gate does not cover the frozen per-row operationalisation (targets, references, row
  rules), which (a) depends on. On the nocturne, target Jaccard is 0.769 (13 rows). 11 of the
  18 evaluable (a) rows (waltz and etude) rest on encoder A alone.

The vertical-gap ambiguity is directional: all three texts A and B placed differently sit one
system (2 edition bars) earlier in B's encoding. Only one is primary (NOC-A-027: r 0.800 under
A's anchor, 1.000 under B's). Swapping it in would move the pooled mean by +0.011, so (a) does
not depend on this rule.

**(a): "inconclusive" is right, but the README's direction sentence is not supported.**
- **Intervals.** The registered stratified bootstrap gives [0.503, 0.750]. A t-interval over
  the 18 rows gives [0.489, 0.779]. The 14 rows that do not restate the print give 0.573
  [0.426, 0.701] (bootstrap). Removing any single row moves the mean between 0.612 and 0.671.
- **Waltz hands (threat 9, now measured).** The waltz MusicXML puts the LH chords in the upper
  part in 19 measures (m29-33, 45-49, 117-121, 133-136; 62 notes). In each of these, the lower
  part has one note per bar.
  - I moved upper-part notes below MIDI 70 in those measures to the lower staff (an auditor
    heuristic).
  - WAL-A-031 then becomes evaluable, with r = 0.176.
  - WAL-A-023 falls from 0.692 to 0.588, and WAL-A-055 from 0.644 to 0.521.
  - The waltz mean falls from 0.620 to 0.486.
  - The pooled mean becomes 0.598 [0.471, 0.714] (19 rows; t-interval [0.452, 0.743]).
- **Nocturne null pool.** The 4 dropped nocturne rows were dropped by the registered mechanical
  rule. Their null counts depend only on the score and the encoding, so the drop is
  outcome-blind. It still favoured the estimate:
  - With the 2-6 null positions they had, 3 of the 4 would have had r = 0 and one r = 0.833.
  - If the null pool admits annotated bars outside the row's own window, 10 nocturne rows are
    evaluable. Their mean is 0.450, and the pooled mean is 0.589 [0.469, 0.701] (21 rows).
  - With both changes, the pooled mean is 0.576 [0.460, 0.685] (22 rows).
- **Reading.** In every variant the registered reading stays inconclusive. The registered
  bootstrap lower bound of 0.503 is the only interval that excludes 0.5. The verdict sentence
  "expert consensus follows the teacher's direction somewhat more often than at unannotated
  positions" should become a point-estimate statement that names this fragility.
- **Reachability check.** The post-run check holds: the row SD of r is 0.292, against 0.289
  assumed.

**(b): "does not notice" is right, and mostly fixed by construction.**
- **Stand-in.** Running `_interpretation_section` rather than `build_report` is a valid stand-in
  for the registered per-bar channels. The tiers are the report's own, and the author checked
  agreement with `target_from_references` on 3 performances. I also checked the report's other
  tempo/loudness output, the window-level too-flat / too-extreme tiers: they changed in 0 of
  117 (row, performance) degradations. So "the report" may be used, but scoped to its tempo and
  loudness shape output.
- **Interval.** The registered bootstrap stratifies by piece. The waltz and etude strata hold one
  row each, so those rows are never resampled. The t-interval over the 6 rows is [-0.095,
  0.212], and its upper bound is still below 0.25. Without ETU-A-014 the mean is 0.000.
- **Reachability (gain sweep, same 20 performances).** I applied each registered degradation at
  gain g: g = 1 is the registered removal, g = 3 reverses the performer's own effect at twice
  its size, and g = 5 at four times. At g = 1 the sweep reproduces every hit rate in Results.

| Row | Notes changed (g = 1) | hit g = 1 | g = 3 | g = 5 | flag on original |
|---|---|---|---|---|---|
| ETU-A-014 | 1.00 | 0.45 | 0.95 | 0.95 | 0.10 |
| NOC-A-027 | 1.00 | 0.05 | 0.75 | 0.75 | 0.00 |
| NOC-A-011 | 0.75 | 0.05 | 0.05 | 0.10 | 0.05 |
| NOC-A-015 | 0.85 | 0.10 | 0.15 | 0.15 | 0.10 |
| NOC-A-039 | 0.47 | 0.00 | 0.00 | 0.00 | 0.00 |
| WAL-A-052 | 0.94 | 0.00 | 0.00 | 0.06 | 0.06 |
| Voicing WAL-A-023 / WAL-A-055 / ETU-A-040 | 1.00 | 0.05 / 0.05 / 0.15 | 0.20 / 0.10 / 0.20 | 0.35 / 0.15 / 0.25 | 0.20 / 0.00 / 0.15 |

- **What the sweep shows.**
  - Four of the six (b)-primary rows (one or two IOIs, one note's velocity, or a three-note
    slope) stay at 0.15 or less even when the effect is reversed at four times its size. The per-bar
    channels cannot see them at any plausible size, so for these rows "does not notice" is a
    property of the channel.
  - Only the two bar-level rows can be flagged at all.
  - At the registered gain, the pooled statistic is 0.057. A degradation that reversed every
    effect at twice its size would reach only 0.266.
  - The registered 0.25 was therefore barely reachable with this row mix.
- **Wording.**
  - The README says "removing a teacher-marked effect that experts share". The f_marked of the
    6 rows runs from 0.52 to 0.97, so say "that a majority of experts show".
  - The "positive check on 5 performances" should cite this sweep instead.
- **"Stays quiet".** The flag rate on the originals is 6 of 120 (0.050, Wilson [0.023, 0.105]),
  and the registered rule uses the point estimate. Two limits:
  - The 120 are not independent: the four nocturne rows share the same 20 performances.
  - Because the thresholds are q95 of out-of-fold experts, about 5% is the calibration target.
    This is a calibration check, not evidence of specificity to teacher bars.

**(c).** The numbers match `c_summary.json`. "Observable" is encoder A's judgement. On the
nocturne the at-least-partly share is 0.477 for A and 0.489 for B.

**Required fixes (README text only; no rerun needed):**
1. Dev. 2: replace "fixed before reading the gate outcome" with what happened. The fix came
   after a first gate run printed `gate_pass False`, with only the bar map failing (0.0 over 70
   merged rows). Add that an independent comparison gives 35 of 35.
2. Dev. 3: report the pre-fix result (7 rows, 0.504 [0.248, 0.766]) and the row that moved
   (NOC-B-038, r = 0.000, B: observable partly). State the unregistered carry-over rule, and
   that it changes no number.
3. Retitle the Deviations section as disclosed after the run.
4. (a) verdict: drop "follows ... somewhat more often". State the point estimate with the
   t-interval over rows [0.489, 0.779] and the non-restating rows 0.573 [0.426, 0.701]. Add
   the waltz hand sensitivity (0.598 [0.471, 0.714]; waltz 0.620 to 0.486; WAL-A-031
   evaluable at r 0.176), and the null-pool sensitivity (0.589, or 0.576 with both changes).
5. Threats realised 1: quantify the waltz hand problem (19 measures, 62 notes) and its effect
   on r, as above.
6. (b): add the gain sweep, and the t-interval over rows [-0.095, 0.212]. Scope "the report" to
   its per-bar and window tempo/loudness tiers. Say that 4 of 6 rows are unreachable at any
   tested gain. Replace "experts share" with "a majority of experts show (f 0.52-0.97)".

**Proposed EXPERIMENTS.md row update** (lead to apply). Verdict column:

    Confirmed with caveats (eval-auditor 2026-10-05): gate pass; (a) inconclusive, mean r 0.634
    [0.503, 0.750] (t over rows [0.489, 0.779]); with the waltz LH-chord staff fix 0.598 [0.471,
    0.714]; no-restate rows 0.573 [0.426, 0.701]; no direction claim. (b) does not notice
    (0.057 [-0.001, 0.116]; t over rows [-0.095, 0.212]); 4 of 6 rows unreachable by the per-bar
    channels even reversed at 4x (gain sweep), bar-level rows flagged 0.75-0.95 when reversed at
    2x; stays quiet 0.050 (calibration check). (c) descriptive. Reruns byte-identical.

Auditor checks (scratch scripts, not in the repo):
- the rerun with `run.ART` patched;
- the waltz staff reassignment and the null-pool variants on `part_a`;
- the gain sweep and the window-tier check on `part_b` (`sets_for`, `degrade`, `target_on_grid`,
  `interpret` / `_interpretation_section`, performances taken from `b_rows.csv`).
