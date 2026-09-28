# Landscape: piano performance assessment (as of 2026-09-27)

This document compiles four parallel web-research passes run on 2026-09-27. Items marked
**[U]** were not verified against the primary source. `lit-scout` owns this file; the ticket to
verify the [U] items is L-01.

**L-01 pass, 2026-09-27 (lit-scout).**
- **[V 2026-09-27]** means I opened the primary source that day (paper, abstract page, repo,
  licence file or Hugging Face API).
- Unmarked items were not re-checked in this pass.
- Deep dives:
  - `2026-09-27-crescendai.md` (L-02)
  - `2026-09-27-expression-models.md` (R-06 prep)

**L-04 and L-03 pass, 2026-09-27 (lit-scout).**
- Section 1.5 is new: evenness, pedalling and hand-synchrony sources, reference ranges, and the
  F-04 citation map.
- L-03 additions are tagged "(L-03 2026-09-27)" in sections 2, 3.3 and 3.4.

**R-08d corpus check, 2026-09-28 (lit-scout).** Section 2.1 is new: Romantic phrase-labelled corpora (DCML and others) and a recommended R-08d draw.

**L-03 methods pass, 2026-09-28 (lit-scout).**
- Section 6 is new: primary sources for the statistical and psychophysical methods used in code
  and in `study/protocol-S03.md`.
- **Correction in 1.4:** the comparative-judgement line said "12 comparisons per item give .70;
  17 give .80". The cited paper (Kinnear et al. 2025) does not say this. Replaced with what it
  and Verhavert et al. 2019 do say.

## 1. Metrics

### 1.1 Correctness
- **Note P/R/F1 with a ±50 ms onset tolerance** (mir_eval / MIREX). [V 2026-09-27]
  - **Offset variant:** the offset tolerance is the larger of 20% of the reference note's duration
    and 50 ms (`offset_ratio=0.2`, `offset_min_tolerance=0.05`).
  - **Velocity variant** (`mir_eval.transcription_velocity`):
    - reference velocities are scaled to [0, 1];
    - estimated velocities are mapped onto them by a linear regression over matched notes;
    - the match tolerance is 0.1.
  - https://mir-eval.readthedocs.io/latest/api/transcription.html
- **Correct / extra / missed labels.** A wrong pitch counts as one extra plus one missed.
  - RUMAA (Chang, Dixon, Benetos, WASPAA 2025): https://arxiv.org/abs/2507.12175
- **Wang, Ewert, Dixon 2017.** Score-informed detection of missing and extra notes, IEEE TASLP.
  https://www.eecs.qmul.ac.uk/~simond/pub/2017/WangEwertDixon-TASLP2017.pdf
- **Nakamura, Yoshii, Katayose, ISMIR 2017.** Symbolic alignment with error detection.
  https://archives.ismir.net/ismir2017/paper/000035.pdf
  - Tool: https://midialignment.github.io/demo.html
- **Polytune** (AAAI 2025). End-to-end error detection from audio + score, 64.1% average F1.
  https://github.com/ben2002chou/Polytune
- **LadderSym** (ICLR 2026). Missed-note F1 from 26.8% to 56.3% on MAESTRO-E.
  https://github.com/ben2002chou/LadderSYM
- **Hu, Marták, Cancino-Chacón, Widmer, ISMIR 2024.** Musically informed metrics for
  articulation, dynamics and rhythm. https://arxiv.org/abs/2406.08454
- **"Sounds Out of Place?"** (ISMIR 2023). Mistakes as listeners perceive them.
  https://ismir2023program.ismir.net/poster_118.html

### 1.2 Expressive features
- **Tempo curves from inter-onset intervals** (Repp; Hu et al., TISMIR 2026, 636+ h). Timing scales
  with tempo; chord asynchrony peaks at strong metrical positions.
  https://transactions.ismir.net/articles/10.5334/tismir.317
- **Articulation: KOT, KDT, KOR** (key overlap/detached time, overlap ratio). Bresin and Battel 2000.
  https://www.tandfonline.com/doi/abs/10.1076/jnmr.29.3.211.3092
- **Melody lead** of about 30 ms, which is mostly a velocity artifact (Goebl, JASA 2001). Measure
  it with velocity as a covariate.
  https://iwk.mdw.ac.at/goebl/papers/Goebl_JASA2001_melodyLead.pdf
- **partitura performance codec**: beat_period, velocity, timing, articulation_log, plus
  functions for asynchrony, articulation, dynamics and pedal.
  https://partitura.readthedocs.io/en/latest/modules/partitura.musicanalysis.html
- **Pedaling**: Liang, Fazekas, Sandler, JAES 2018 (sensor data). Fang et al. 2025 (pedal depth
  from audio; not robust to unseen rooms). https://arxiv.org/abs/2507.04230
- **Review**: Cancino-Chacón, Grachten, Goebl, Widmer 2018, Frontiers in Digital Humanities.
  https://doi.org/10.3389/fdigh.2018.00025

### 1.3 Comparing a performance to a reference distribution
- **Repp 1992** (JASA 92(5):2546-2568): inter-onset intervals from 28 recordings of Schumann's
  Träumerei. [V 2026-09-27, abstract]
  - Methods: PCA over longer stretches, plus curve fitting within gestures.
  - Global timing follows the grouping structure.
  - Within-gesture ritardandi follow a parabola "with a single degree of freedom".
  - The abstract gives no component count. https://doi.org/10.1121/1.404425
- **Repp 1998** (JASA 104(2):1085-1100): **this is the "about 4 timing strategies" result.**
  [V 2026-09-27, abstract]
  - PCA of bars 1-5 of 115 recordings of Chopin's Etude Op. 10 No. 3 found "at least four
    independent timing strategies".
  - Each pianist's pattern is a weighted combination of the four plus idiosyncratic variation.
  - https://doi.org/10.1121/1.423325
- **Repp 1997** (Music Perception 14(4):419-444). [V 2026-09-27, abstract]
  - Experiment 1: the average of 10 student Träumerei performances was rated second-highest in
    quality and second-lowest in individuality.
  - Experiment 2: the expert-average timing pattern was rated highest of 30 synthesized
    performances.
  - Rated quality and individuality were negatively correlated.
  - https://doi.org/10.2307/40285732
  - The 2018 replication is at https://mp.ucpress.edu/content/36/1/98 (not re-checked).
- **Wöllner 2013**: individuality measured as deviation from the average of many humans.
  https://pmc.ncbi.nlm.nih.gov/articles/PMC3685802/
- **Sapp 2007 timescapes** (Mazurka Project).
  https://ismir2007.ismir.net/proceedings/ISMIR2007_p497_sapp.pdf
- **Functional data analysis of tempo curves**: Almansa and Delicado 2009.

### 1.4 Rater reliability
- **Thompson and Williamon 2003**: mean inter-judge rho of .50; categories highly intercorrelated.
  https://mp.ucpress.edu/content/21/1/21.abstract
- **Bergee 2003**: panels of 5 or more judges recommended.
  https://journals.sagepub.com/doi/10.2307/3345847
- **Objective error counts** are reliable (r about .9). Tempo and expression judgments are not
  (r .5 to .74) (Stivers 1972 via Shih 2018).
- **PercePiano** (Park et al., Sci. Rep. 14:23002, 2024). [V 2026-09-27]
  - Reliability: single-rater ICC(1,1) .16 to .42; the mean of the raters reaches ICC(1,k) .92
    to .98.
  - Raters: 53 expert annotators in total (graduate-level or professional pianists, or music
    theory graduates). Each segment has 5 to 12 raters, mean 10.52 (SD 3.62). They are not
    crowdworkers.
  - Labels: 7-point scale; the label is the plain mean after "I don't know" answers are removed.
  - 12,652 annotations in total, 7.3% of them "I don't know".
  - The 19 dimensions sit in 8 groups: Timing, Articulation, Pedal, Timbre, Dynamic, Music making,
    Emotion, Interpretation.
  - https://pmc.ncbi.nlm.nih.gov/articles/PMC11450231/
- **Jiang ISMIR 2023**: rank agreement is much better than raw-scale agreement. Better players are
  not better judges. https://archives.ismir.net/ismir2023/paper/000043.pdf
- **NeuroPiano**: dynamics and legato are the most disputed dimensions.
  https://arxiv.org/abs/2410.03139
- **Comparative judgement: how many comparisons per item.** [V 2026-09-28, full text / abstract]
  (corrected 2026-09-28; the earlier "12 give .70, 17 give .80" is in neither paper)
  - Kinnear, Jones, Davies 2025, "Comparative judgement as a research tool: a meta-analysis of
    application and reliability", *Behavior Research Methods* 57:222.
    https://doi.org/10.3758/s13428-025-02744-w (PMC12246014)
    - 101 CJ datasets across disciplines; 64 non-adaptive sessions used for the reliability
      analyses.
    - Only the comparisons-per-item ratio predicted reliability. Their recommendation: each
      item should appear in at least 20 comparisons on average (total judgements at least 10
      times the number of items). That tends to give scale separation reliability (SSR) of .8
      or more and split-half reliability (SHR) of .7 or more.
    - Use SSR of .8, not .7, as the threshold, since SSR runs higher than SHR. In 9% of
      datasets with SSR of .8 or more, SHR was still below .7.
    - For a new kind of stimulus (piano excerpts qualify) they recommend also reporting SHR and
      collecting more comparisons, so that each split half on its own has at least 10 per item.
      Their text gives the multiplier two ways ("N_CR >= 20", "multiply N_R by 20"), so the
      exact figure is ambiguous; the larger reading is the safe one.
  - Verhavert, Bouwer, Donche, De Maeyer 2019, "A meta-analysis on the reliability of
    comparative judgement", *Assessment in Education* 26(5):541-562 (49 assessments):
    10 to 14 comparisons per item for reliability .70; 26 to 37 for .90.
    https://doi.org/10.1080/0969594X.2019.1602027
  - Adaptive pairing inflates SSR: Bramley and Vitello 2019, *Assessment in Education*
    26(1):43-58 (online 2018). https://doi.org/10.1080/0969594X.2017.1418734 [V 2026-09-28,
    Crossref metadata and as cited by Kinnear et al.]

### 1.5 Motor control: evenness, pedalling, hand synchrony (L-04, 2026-09-27)

Sources for the tier B features in `src/pianolens/features/control.py` (F-04). "Derived" means I
divided a reported SD by the reported IOI; the paper does not state that number.

**How to read the reference ranges.** Every scale study below uses instructed, metronomic,
non-expressive scales on a MIDI keyboard. The unevenness measure is the raw SD of the
inter-onset intervals (IOIs) within a scale run, in ms. PianoLens's `even_ioi_cv` is
tempo-normalized and computed in repertoire, so it also contains expressive micro-timing and
alignment noise. Treat these values as a floor for skilled deliberate evenness, not as a norm for
repertoire. Variability depends on tempo (MacKenzie and Van Eerd), so compare only at a similar
note rate.

#### Evenness of scales and figuration (timing)
- **Jabusch, Vauth, Altenmüller 2004**, *Movement Disorders* 19(2):171-180. [V 2026-09-27, abstract
  via PubMed]
  - This paper introduced "MIDI-based Scale Analysis".
  - Participants: 8 pianists with focal dystonia and 8 matched healthy professionals.
  - Measures: key velocities and timing parameters, as SDs within a scale run.
  - Affected hands had higher mean SDs of the timing parameters, and the mean SD of the IOIs
    correlated with the disability scale (ADDS).
  - The abstract gives no values. https://doi.org/10.1002/mds.10671
  - A secondary source (Frontiers in Psychology 2020, a drummers paper, PMC7693443) credits
    "Jabusch et al. (2004)" with 13 professional pianists at a mean IOI SD of 8.1 ms (thumb-under
    direction) and 8.9 ms (cross-over direction). This conflicts with the abstract's 8 healthy
    pianists. **[U]** until the full text is read (paywalled).
- **Jabusch, Alpers, Kopiez, Vauth, Altenmüller 2009**, *Human Movement Science* 28:74-84.
  [V 2026-09-27, abstract]
  - Temporal evenness of scales was measured twice, about 27 months apart, in 19 pianists.
  - The change in evenness tracked accumulated practice time, which explained 43% of the
    variance. Pianists practising 3.75 h/day or more improved.
  - This supports IOI SD as a skill-sensitive measure. https://doi.org/10.1016/j.humov.2008.08.001
- **van Vugt, Jabusch, Altenmüller 2012**, *Frontiers in Psychology* 3:495 (conservatory
  students, two-octave scales). [V 2026-09-27, full text PMC3499913]
  - Method: fit a straight line to onset time against note rank. The deviation of each onset is
    split into two parts:
    - *irregularity*: systematic deviation, the mean over trials;
    - *instability*: the trial-to-trial SD, which the authors read as motor noise.
  - Some notes are systematically late: note 5 by about 8 ms in one pianist; the last note of
    ascending scales by 9.3 ms against 1.1 ms at the octave.
  - Instability peaks at the octave boundary (motor chunking).
  - A simulated jitter of SD 9 ms reproduced the pianists' average instability profile at
    8 notes/s.
  - **Relevance:** part of the unevenness inside a scale is systematic and neuromuscular (thumb
    passage, octave boundary), not random. A pooled CV mixes the two parts.
- **van Vugt, Jabusch, Altenmüller 2013**, *Frontiers in Psychology* 4:134. [V 2026-09-27, full text
  PMC3604639]
  - Setup: 8 professional pianists (students and teachers, Hanover); two-octave C-major scales at
    8 notes/s (IOI 125 ms), legato, mf, instructed "as evenly as possible, without expression".
  - **Unevenness (SD of IOIs):**
    - left hand 9.19 ms (SD 1.67);
    - right hand 8.44 ms (SD 1.81);
    - derived CV about 0.067 to 0.074.
  - **Perception threshold:** listeners detected unevenness at about **10.22 ms (SD 2.51)** IOI
    SD at 8 notes/s (derived CV about 0.08). Most of the professionals' unevenness was below what
    listeners could hear.
  - Each pianist's systematic deviation trace is a stable "fingerprint" (100% identification)
    that listeners cannot hear.
  - https://doi.org/10.3389/fpsyg.2013.00134
- **van Vugt, Treutler, Altenmüller, Jabusch 2013**, *Frontiers in Human Neuroscience* 7:347
  (chronotype study). [V 2026-09-27, full text PMC3705811]
  - Setup: 22 piano students (21 in the ANOVA); two-octave C-major scales at **10.7 notes/s** (IOI about 94 ms).
  - Unevenness: right hand 10.4 ms (SD 2.12), left hand 12.3 ms (SD 2.64); derived CV about
    0.11 and 0.13.
  - https://doi.org/10.3389/fnhum.2013.00347
- **van Vugt, Furuya, Vauth, Jabusch, Altenmüller 2014**, *Experimental Brain Research*
  232:3555-3567. [V 2026-09-27, abstract]
  - At slow tempi, scale timing deviations follow a "phrasal template": slowing at the start and
    end.
  - At fast tempi, they follow a "neuromuscular template": three peak delays at the thumb-unders.
  - A four-parameter model predicts the note-level deviations across tempi (R² 0.70).
  - https://doi.org/10.1007/s00221-014-4036-4
- **Cheng, Großbach, Altenmüller 2013**, *Frontiers in Human Neuroscience* 7:868. [V 2026-09-27, full
  text PMC3865372]
  - Pianists with dystonia had a median IOI SD of **14.76 ms** at IOI 187.5 ms (derived CV about
    0.079).
  - An earlier, more severe cohort had 20.0 ms.
  - This gives a clinical upper reference. https://doi.org/10.3389/fnhum.2013.00868
- **MacKenzie and Van Eerd 1990**, "Rhythmic precision in the performance of piano scales",
  *Attention and Performance* XIII:375-408. [V 2026-09-27, abstract via OpenAlex]
  - Setup: 7 highly skilled pianists, C-major scales at 4, 6, 8 and 12 notes/s and as fast as
    possible.
  - **The within-trial SD and CV of the inter-note intervals rose with speed. So did the SD of
    key-press velocity.** Hand and uni- vs bimanual playing did not change these measures.
  - This is the reason `even_*` must be compared at a matched note rate.
  - https://doi.org/10.4324/9780203772010-12
- **Dalla Bella and Palmer 2011**, *PLoS ONE* 6:e20518. [V 2026-09-27, full text PMC3121738]
  - 4 skilled pianists played isochronous melodies at 5 tempi.
  - The IOI CV increased with tempo (values are only in a figure).
  - https://doi.org/10.1371/journal.pone.0020518
- **Kim, Park, Rhyu, Nam, Lee 2021**, "Quantitative analysis of piano performance proficiency
  focusing on difference between hands", *PLoS ONE* 16:e0250299. [V 2026-09-27, full text
  PMC8133499]
  - **This is the only expert vs amateur MIDI comparison found.**
  - Participants: 34 piano majors (Seoul National University) and 34 amateurs, on a Disklavier
    C7X.
  - Tasks: Hanon No. 1 and a four-octave C-major scale at 4 notes/s.
  - The SD of the relative IOI (IOI / notated duration) separated the groups (F(1,66) = 30.7,
    partial eta² .32). So did the duration SD and the articulation SD.
  - The velocity SD showed a hand x group interaction, not a clean group effect.
  - **Group means are only in figures.** Data are not public (IRB-restricted).
  - https://doi.org/10.1371/journal.pone.0250299
- **Wagner 1971** (scale timing vs tempo) and **Seashore 1938**: the original IOI-SD unevenness
  measure, cited by van Vugt 2012. **[U]**, not opened.
- **Lipke-Perry, Dutto, Levy 2019**, *Music & Science*: scale timing patterns persist across
  instruments. **[U]**, search snippet only. https://doi.org/10.1177/2059204319870733
- No MIDI study of **Alberti bass** or arpeggio evenness with reported values was found.
  - Kim 2021's Hanon pattern is the closest figuration.
  - Profy (2026, section 3.3) recorded 6 arpeggios and SKY-Piano (2026, section 2) recorded
    arpeggios and broken octaves, but neither reports evenness values.

#### Evenness of loudness (velocity)
- **Tominaga, Lee, Altenmüller, Miyazaki, Furuya 2016**, *PLoS ONE* 11:e0161324. [V 2026-09-27,
  full text PMC4990412]
  - Setup: 7 prize-winning pianists, an 8-note right-hand melody at IOI 250 ms, target velocity 75.
  - **Across-trial** variability per keystroke:
    - IOI: 7.9 ± 1.2 ms (range 4.5 to 12.3);
    - velocity: **4.1 ± 1.2 MIDI units** (range 1.2 to 7.5).
  - Timing and velocity inconsistency were uncorrelated (r = 0.08).
  - These are across-trial SDs, not within-run, but they bound expert keystroke noise.
  - https://doi.org/10.1371/journal.pone.0161324
- **Slade, Gascón, Comeau, Russell 2023**, *Psychology of Music* 51:924. [V 2026-09-27, abstract]
  - Just-noticeable difference in key velocity between consecutive tones: **2.71 to 4.48
    velocity units** (0.68 to 1.22 dBC on a Disklavier).
  - Experienced pianists had lower JNDs.
  - Use this as the audibility scale for `even_vel_sd_midi`.
  - https://doi.org/10.1177/03057356221126203
- Jabusch 2004 and MacKenzie and Van Eerd 1990 measured the velocity SD within scales. Neither
  abstract gives values. **[U]** for the values.
- **Furuya and Altenmüller 2013** (*Frontiers in Human Neuroscience* 7:173, review) and **Furuya
  2011** (*Frontiers in Human Neuroscience* 5:50) [V 2026-09-27, abstracts]: expert vs amateur
  movement organization. They give kinematics, not MIDI evenness values. Background only.

#### Pedalling relative to harmony
- **Repp 1996**, "Pedal timing and tempo in expressive piano performance", *Psychology of Music*
  24:199-221. [V 2026-09-27, abstract]
  - Setup: 2 pianists, 9 Träumerei performances each at 3 tempi.
  - Pedal release, depression and change times were measured against key events.
  - Neither absolute nor relative invariance held across tempo changes.
  - Timing was consistent within a pianist. The two pianists, who differed in skill, pedalled
    strikingly differently.
  - The abstract gives no ms values. https://doi.org/10.1177/0305735696242011
- **Repp 1997**, "The effect of tempo on pedal timing in piano performance", *Psychological
  Research* 60:164-172. **[U]**
  - The abstract is paywalled. Only the Semantic Scholar summary was seen: 10 pianists; excerpts
    needing repeated pedal changes between chords; Disklavier MIDI; 3 tempi.
  - That summary says pedal timing is "neither absolutely nor relatively invariant".
  - https://doi.org/10.1007/BF00419764
- **Liang, Fazekas, Sandler 2018**, *JAES* 66(6):448. [V 2026-09-27, abstract; the full-text PDF did
  not download]
  - A sensor system records sustain-pedal gestures alongside audio.
  - Pedal onset and offset detection, plus technique classification (SVM vs HMM): F1 above 0.7
    per technique and above 0.9 on average.
  - https://doi.org/10.17743/jaes.2018.0035
- **Liang, Fazekas, Sandler, EUSIPCO 2018**, "Piano legato-pedal onset detection based on a
  sympathetic resonance measure". [V 2026-09-27, full text]
  - Defines **legato (syncopated) pedalling**: the pedal is held through the chord change; then,
    "immediately after the [new] chord onset, the pedal is released to avoid blurring", and it is
    pressed again.
  - The paper cites Banowetz, *The Pianist's Guide to Pedaling* **[U]**, and Rosenblum 1993,
    *Performance Practice Review* 6(2) **[U]**.
  - https://www.eurasip.org/Proceedings/Eusipco/Eusipco2018/papers/1570437306.pdf
- **Heinlein 1929**: early pedal-timing measurements. **[U]** (cited by Bernays and Traube 2014).
- **Bernays and Traube 2014**, *Frontiers in Psychology* 5:157. [V 2026-09-27, full text PMC3941302]
  - Setup: 4 pianists on a Bösendorfer CEUS (pedal position at 500 Hz, 8-bit); pedal use
    measured per chord.
  - Sustain and soft-pedal use and part-pedalling varied with the intended timbre and with the
    pianist.
  - **Relevance:** pedal depth is continuous, and a binary CC64 threshold loses part-pedalling.
  - https://doi.org/10.3389/fpsyg.2014.00157
- **Zhang, Fang, Wang, Fujinaga** (arXiv 2510.03750 v2, 2026-02-03). [V 2026-09-27, full text]
  - Action-level (press / hold / release timing) and gesture-level metrics for continuous pedal
    depth.
  - They note that frames at harmonic changes and intended releases are "musically critical".
  - Relevant if pedal comes from audio (Phase 6). https://arxiv.org/abs/2510.03750
- **What was not found:**
  - no study reports the share of harmony changes pedalled cleanly, or typical lift latencies
    after a chord change, for experts vs students;
  - Repp's ms values sit behind paywalls.
  - So the `pedal_blur_*` window defaults (0.25 beat before, 0.5 beat after) rest on the
    pedagogical definition above, not on measured norms. F-04b should tune them on sensor-pedal
    data.

#### Hand and chord asynchrony (beyond Goebl 2001)
- **Repp 1996**, "Patterns of note onset asynchronies in expressive piano performance", *JASA*
  100(6):3917. [V 2026-09-27, abstract]
  - Setup: 10 graduate students, 3 pieces, 2 takes each, Disklavier.
  - Findings:
    - The highest notes lead.
    - Within each hand, the lead correlates strongly with the velocity difference.
    - **Some pianists consistently lead with the left hand, independent of velocity.** This is
      stable across pieces, unrelated to handedness, and partly deliberate.
  - This supports reporting `hand_async_mean_ms` as possibly stylistic and using the robust SD
    after the velocity fit as the noise measure. https://doi.org/10.1121/1.417245
- **Goebl, Flossmann, Widmer, SMC 2009**, "Computational investigations into between-hand
  synchronization in piano playing: Magaloff's complete Chopin". [V 2026-09-27, full text]
  - The journal version is *Computer Music Journal* 34(3):35-44, 2010,
    https://doi.org/10.1162/comj_a_00002 [V, bibliographic record only].
  - Data: 163,208 between-hand asynchronies (lower staff minus upper staff; positive = right hand
    early). Mean **4.4 ms**, mode **13 ms**.
  - Notated arpeggios, ornaments, trills and grace notes (about 10% of events) were excluded.
  - Faster pieces had **lower absolute asynchrony and lower variability**.
  - Bass anticipations (lowest left-hand note more than 50 ms early): below 1% of events in
    Etudes and Preludes, almost 2% in Mazurkas and Nocturnes. They fall most often on the first
    beat (1.80%), then other on-beats (1.48%), then off-beats (0.66%).
  - It uses a ±30 ms band as the perceptual limit for asynchrony, citing Goebl and Parncutt,
    ICMPC 2002 **[U]**.
  - **Sign:** F-04 uses staff 1 minus staff 2 (positive = left hand first), the opposite of this
    paper.
  - https://www.jku.at/fileadmin/gruppen/173/Research/Investigations_of_Between-Hand_Synchronization_in_.pdf
- **Kim et al. 2021** (above): the SD of the between-hand "attack deviation" was 0.008 for
  experts vs 0.014 for amateurs (all excerpts, t(66) = 5.24).
  - The unit is not stated; it is probably seconds, which would be 8 vs 14 ms.
  - Tasks were Hanon and the scale in parallel octaves at 4 notes/s.
  - This is the only expert vs amateur hand-synchrony figure found.
- **Hu et al., TISMIR 2026** (section 1.2): chord asynchrony peaks at strong metrical positions.
  Not re-checked here.

#### Reference ranges at a glance (all instructed scales unless noted)

| Measure | Group | Value | Rate | Source |
|---|---|---|---|---|
| IOI SD within run | professionals | 8.4 ms (RH), 9.2 ms (LH); CV about 0.07 (derived) | 8 notes/s | van Vugt 2013 |
| IOI SD within run | music students | 10.4 ms (RH), 12.3 ms (LH); CV about 0.11 to 0.13 (derived) | 10.7 notes/s | van Vugt, Treutler et al. 2013 |
| IOI SD within run | dystonia patients | 14.8 ms median; CV about 0.08 (derived) | 5.3 notes/s | Cheng 2013 |
| Audible unevenness threshold | listeners | about 10.2 ms IOI SD; CV about 0.08 (derived) | 8 notes/s | van Vugt 2013 |
| IOI SD across trials, per keystroke | prize-winning pianists | 7.9 ms (4.5 to 12.3) | 4 notes/s | Tominaga 2016 |
| Velocity SD across trials, per keystroke | prize-winning pianists | 4.1 MIDI (1.2 to 7.5) | 4 notes/s | Tominaga 2016 |
| Velocity JND, consecutive tones | pianists and non-musicians | 2.7 to 4.5 MIDI units | n/a | Slade 2023 |
| Between-hand onset SD | experts vs amateurs | 0.008 vs 0.014 (unit unstated; likely s) | 4 notes/s | Kim 2021 |
| Between-hand asynchrony, repertoire | one virtuoso (Magaloff) | mean +4.4 ms, mode +13 ms (right hand early) | Chopin corpus | Goebl 2009 |
| Asynchrony audibility band | n/a | ±30 ms | n/a | Goebl 2009, citing Goebl and Parncutt 2002 [U] |

#### F-04 feature to citation map (for the feature-engineer; not yet applied to the code)

| F-04 feature | Should cite | Note for the docstring |
|---|---|---|
| 1. `timing_noise_*` | Repp 1992 and 1998 (1.3); van Vugt 2012 (the split into systematic and trial-to-trial parts is the same idea as residual minus consensus); Tominaga 2016 (expert keystroke noise about 8 ms at 250 ms IOI) | The consensus plays the role of van Vugt's "irregularity"; the noise plays the role of "instability". |
| 2. `even_ioi_cv` | Jabusch 2004 (IOI-SD scale analysis); van Vugt 2012 and 2013; MacKenzie and Van Eerd 1990 (CV rises with rate); Kim 2021 (expert vs amateur) | Replace "no source specific to scale / Alberti evenness yet" with these. Say that the published values are raw IOI SD in metronomic scales and that CV depends on note rate: report notes/s next to it. Audibility is about 0.08 CV at 8 notes/s (van Vugt 2013). |
| 2. `even_vel_sd_midi` | MacKenzie and Van Eerd 1990 (velocity SD rises with rate); Tominaga 2016 (expert 4.1 MIDI across trials); Slade 2023 (JND 2.7 to 4.5 units) | No published within-run expert value was found. |
| 3. `hand_async_*` | Goebl 2001 (already cited); Repp 1996 JASA (velocity-linked leads, individual left-hand lead); Goebl, Flossmann, Widmer 2009 / 2010 (corpus norms; faster pieces are more synchronous; ±30 ms audibility); Kim 2021 (expert vs amateur SD) | Note the opposite sign convention of Goebl 2009. Excluding notated arpeggios follows Goebl 2009. |
| 4. `tempo_instability_*` | Repp 1992 (already cited); van Vugt 2014 (phrasal slowing at run edges); no source measures "wobble beyond the phrase level" as such | The 4-bar phrase allowance remains our own choice. |
| 5. `pedal_blur_*` | Liang, Fazekas, Sandler JAES 2018 (already cited); Liang et al. EUSIPCO 2018 (legato-pedal definition: release immediately after the new chord onset); Repp 1996 (pedal timing varies with tempo and skill, no invariance); Repp 1997 [U]; Bernays and Traube 2014 (part-pedalling: CC64 is not binary) | Say that the before/after window has no measured norm; F-04b tunes it on Batik/Vienna sensor pedal data. |

## 2. Datasets
See `DATASETS.md` for what is downloaded. Candidate list:

| Dataset | Key facts | License | URL |
|---|---|---|---|
| **PianoCoRe** (TISMIR 9(1):144-163, 2026) [V 2026-09-27] | Tiers: C 250,046 perfs / 5,625 pieces / 483 composers / 21,763 h; B (dedup + quality) 214,092 / 5,591; **A (note-aligned) 157,207 / 1,591 pieces / 151 composers / 12,509 h**; A* (high quality, ≥85% aligned) 130,275 / 1,517. **"1,104 pieces have 50+ performances" is for tier C, not A**; the count for A is not stated. Performances from MAESTRO, ASAP, (n)ASAP, ATEPP, GiantMIDI, Aria-MIDI, PERiScoPe; scores from PDMX, MuseScore (KunstderFuge/ClassicalMIDI used for matching only). Only works public-domain in the EU (best effort). HF parquet is about 8.6 GB. | CC BY-NC-SA 4.0 | https://github.com/ilya16/PianoCoRe, https://huggingface.co/datasets/SyMuPe/PianoCoRe, https://arxiv.org/abs/2605.06627 |
| (n)ASAP | 1,067 performances, 222 scores, human-checked note alignments, partly with audio | CC BY-NC-SA | https://github.com/CPJKU/asap-dataset |
| ATEPP [V 2026-09-27] | Current release 11,674 transcribed performances (v1.0 had 11,742), about 1,000 h, 49 pianists, 1,595 movements, 25 composers; scores for about half | **CC BY 4.0** (README); download behind a disclaimer | https://github.com/tangjjbetsy/ATEPP |
| MAESTRO v3 | 1,276 performances, about 199 h of audio + MIDI | CC BY-NC-SA 4.0 | https://magenta.tensorflow.org/datasets/maestro |
| Aria-MIDI | 1.19M transcribed files, about 100k h, includes amateurs | CC BY-NC-SA 4.0 | https://github.com/loubbrad/aria-midi |
| PERiScoPe [V 2026-09-27] | v1.1: 35,815 aligned score-performance pairs, 1,163 scores, 66 composers, about 2,848 h; from (n)ASAP, ATEPP and web performances. Trains the SyMuPe models | CC BY-NC-SA 4.0 | https://huggingface.co/datasets/SyMuPe/PERiScoPe |
| **PercePiano** [V 2026-09-27] | 1,202 segments (4/8/16 bars), 19 dimensions, 53 expert raters, about 10.5 per segment. 4 works: Schubert D.960 mv2 and mv3, D.935 no.3, Beethoven WoO 80; 25 pianists plus 'Score' renditions. Raters heard MIDI rendered in Logic Pro with its 'Yamaha Grand Piano' instrument. **Filename trap:** the README says `<work>_<N>bars_<segment>_<player>`, but the code (`get_performer_id`) and the data are `<work>_<N>bars_<player>_<segment>`. | Data CC BY-NC-ND 4.0 (paper); repo code MIT | https://github.com/JonghoKimSNU/PercePiano |
| MazurkaBL [V 2026-09-27] | 46 mazurkas (46 beat-time files); about 2,000 recordings (2,144 performer columns in `beat_time`); beat times, per-beat loudness (sones), expressive markings; no audio. Kosta, Bandtlow, Chew, TENOR 2018 | CC BY-NC-SA 4.0 (README) | https://github.com/katkost/MazurkaBL |
| Vienna 4x22 | 4 excerpts x 22 pianists, Bösendorfer MIDI + alignment | research | CPJKU GitHub |
| Batik-plays-Mozart | 12 sonatas; harmony, cadence and phrase annotations | see repo | https://github.com/huispaty/batik_plays_mozart |
| Expert-Novice (Jiang 2023) | 83 amateur recordings, MusicXML, alignment, 803 ratings | CC BY-NC-SA | https://zenodo.org/records/8392772 |
| NeuroPiano | 104 student recordings, teacher ratings + text | see HF | https://huggingface.co/datasets/anusfoil/NeuroPiano-data |
| MAJEPPA (ISMIR 2026) [V 2026-09-27] | Paper: 3,979 recordings, 6 expertise levels, 6 recording contexts. The HF release has 4,449 transcribed performance MIDI files (279 h), 886 score MIDIs, DTW alignments, and expertise and context labels. **No audio is distributed** (YouTube source links only). Model weights: HF `anusfoil/majeppa` (Apache-2.0) | Data 'other / mixed'; code MIT | https://huggingface.co/datasets/kkwsts/MAJEPPA-Dataset, https://github.com/kkwsts/majeppa |
| PianoJudges / Pianism-Labelling | Expertise, difficulty, technique labels | see repo | https://github.com/anusfoil/PianoJudges |
| Rach3 [V 2026-09-27] | 3,152 rehearsal MIDI files, 750+ h, 4 pianists (3 advanced, 1 beginner) over 4+ years, MusicXML for many pieces, one recital. ISMIR 2025 | CC BY-NC-SA 4.0 (repo LICENSE) | https://github.com/Rach3Project/rach3_midi_dataset |
| **SKY-Piano** (ISMIR 2026; arXiv 2607.27296) [V 2026-09-27, paper] (L-03 2026-09-27) | 7 professional + 12 amateur pianists, 11 h. Disklavier DC7X MIDI (with pedal), audio, multi-view video, optical hand and body mocap, MusicXML. Shared core: technique drills (scale, arpeggio, octaves) at slow and fast tempi; the slow C-major scale is played by all 19; graded pieces. **A candidate expert vs amateur evenness check for F-04.** | Paper CC BY 4.0; dataset **not publicly released**, license unclear (checked 2026-09-27; see DATASETS.md, BL-11) | https://joonhyungbae.github.io/skypiano/ |
| PianoVAM, PISA, YCU-PPE-III, ICPC-2015 | Multimodal / skill / competition sets | various (PianoVAM: CC BY-NC-SA 4.0, checked 2026-09-27 by D-10) | see agent report |
| Mistake sets | MAESTRO-E, Burgmüller mistakes, Polytune data | various | Polytune repo |
| CIPI / PSyllabus | Difficulty labels | CC | zenodo 8037327 / 14794592 |

### 2.1 Romantic phrase-labelled corpora for R-08d (lit-scout, 2026-09-28)

**Question.** Which Romantic piano scores carry expert phrase-boundary labels (ideally also
cadences) at onset level, usable like DCML's `phraseend` column?

**Method [V 2026-09-28].**
- I listed all 127 DCMLab repos through the GitHub API.
- For every 19th-century corpus I downloaded all `harmonies/*.tsv` files from the default
  branch. These are small TSVs, kept in the session scratchpad only, not in `data/`.
- "Ends" counts `}` (so `}{` counts once as an end and once as a start), as R-08b did.
- Version and license come from `.zenodo.json` and the latest GitHub release.
- Overlap with performance data comes from the local `data/raw/pianocore/metadata.csv` (tier A
  only), ASAP folders and MazurkaBL `beat_time/`.

**Main finding: DCML has no post-cutoff Romantic labels.** Every Romantic DCML corpus was last
pushed on 2025-04-27/28 (releases v2.3 to v3.2). `pushed_at` covers all branches. The labels
were also published earlier, in "An Annotated Corpus of Tonal Piano Music from the Long 19th
Century" (the `romantic_piano_corpus` meta-repo, v2.1, 2023-12-05), and they are rendered on
public GitHub Pages. So R-08d on DCML carries the same caveat as R-08c: exposure of DCML labels
in training is not excluded. **Only the OWNER route (option 2 in DECISIONS) gives labels made
after the cutoff.**

**Second finding: the old phrase symbol.** DCML's current standard marks phrase ends with `}`.
The deprecated symbol `\\` marks the old kind of phrase ending, with no start marks. Several
corpora use only `\\` and have no cadence labels, so the R-08a scorer cannot read them as they
stand.

| Rank | Repo (DCMLab) | Music | Pieces | Ends (`}`) | Cadence labels | Version, release | Performances on the same pieces |
|---|---|---|---|---|---|---|---|
| 1 | `chopin_mazurkas` | Chopin, Mazurkas (all 3/4) | 55 | 606 (median 10 per piece, range 2-24) | 344 (PAC 212, HC 64, IAC 56) | v3.2, 2025-04-27 | **PianoCoRe tier A: 33 mazurkas, 2,712 perfs; MazurkaBL: 45 of its 46** |
| 2 | `grieg_lyric_pieces` | Grieg, Lyric Pieces (10 books) | 66 | 559 (1-25) | 433 (HC 148, PAC 193) | v2.3, 2025-04-27 | PianoCoRe A: 12 pieces, 1,178 perfs |
| 3 | `tchaikovsky_seasons` | Tchaikovsky, The Seasons op. 37a | 12 | 298 (10-51) | 185 | v2.3, 2025-04-27 | PianoCoRe A: 10 of 12, 1,818 perfs |
| 4 | `schumann_kinderszenen` | Schumann, Kinderszenen op. 15 | 13 | 87 (3-12) | 79 | v2.3, 2025-04-27 | PianoCoRe A: 4 movements plus whole-work rows, 1,576 perfs |
| 5 | `liszt_pelerinage` | Liszt, Années de pèlerinage S.160-162 | 19 | 277 (5-47) | 272 | v2.3, 2025-04-27 | ASAP: Gondoliera (162.01); PianoCoRe A: Gondoliera 47, Tarantella 187 |
| 6 | `dvorak_silhouettes` | Dvořák, Silhouettes op. 8 | 12 | 169 (3-29) | 139 | v2.3, 2025-04-27 | none in tier A (66 lower-tier rows) |
| 7 | `medtner_tales` | Medtner, Tales (early 20th c.) | 19 | 287 (5-45) | 233 | v2.3, 2025-04-27 | none in tier A |
| 8 | `debussy_suite_bergamasque` | Debussy, Suite bergamasque | 4 | 25 (3-10) | 29 | v2.3, 2025-04-27 | PianoCoRe A: 4 movements, 2,534 perfs |
| 9 | `rachmaninoff_piano` | Rachmaninoff, Corelli Variations op. 42 | 22 | 80 (1-10) | 49 | v2.4, 2025-04-27 | none in tier A |
| - | `beethoven_piano_sonatas` | Beethoven, 32 sonatas (Classical to early Romantic) | 64 | 1,387 (3-47) | 1,370 | v2.5, 2025-04-27 | many (ASAP, PianoCoRe); famous, so a memorisation risk |
| - | `mahler_kindertotenlieder` | voice and orchestra | 5 | 30 | 30 | v3.2 | not piano |

No usable phrase ends:

| Repo | What is there |
|---|---|
| `schubert_winterreise` (v2.4, 2025-04-27) | 24 songs (voice and piano), 414 old-style `\\` ends, no `{`, no cadence labels. Vocal. Lower priority. |
| `schumann_liederkreis` (v2.5) | songs, 86 `\\`, no cadences |
| `mendelssohn_quartets` (v2.4) | string quartets, 451 `\\`, no cadences |
| `ravel_piano` (v2.6), `wagner_overtures` (v2.6) | 39 and 13 `\\`, no cadences |
| `c_schumann_lieder` (v2.4) | MuseScore files only, no TSVs |
| `debussy_piano` (v0.9.1), `debussy_*` sub-repos | no harmony TSVs (pitch-class data only) |
| `romantic_piano_corpus`, `distant_listening_corpus` | meta-repos (submodules) of the corpora above; no new data |

**Does not exist on DCMLab (2026-09-28):** no Schubert piano corpus, no
`mendelssohn_lieder_ohne_worte`, and no other Chopin set (for example Preludes or Nocturnes).
Repos pushed after June 2026 (`choro`, `corpusinterface`, `data_reports`, `dimcat`,
`haskell-musicology`, `reductive_analysis_app`, `short_phrase_collections`, `coup`) hold no
Romantic piano phrase labels. `short_phrase_collections` (Feb-Aug 2026) is 8 short polyphonic
phrases chosen as experiment stimuli, not a labelled corpus.

**Non-DCML resources [mostly U].**
- **Batik-plays-Mozart** (Classical) is still the only corpus that links DCML phrase labels to
  note-aligned performances. The TISMIR 2026 multi-corpus timing study ("Revisiting Expressive Timing in Piano Performance at Scale", published
  2026-07-17, tismir.317) [V 2026-09-28, article page] adds no Romantic phrase labels. Its
  Magaloff/Chopin data are proprietary.
- **MazurkaBL** (local) has beat times and dynamics for about 2,000 recordings of 46 mazurkas,
  but no phrase labels. Joined with `chopin_mazurkas` it gives phrase labels on performed pieces
  at beat level, for 45 mazurkas.
- **GTTM database** (Hamanaka, Hirata, Tojo): 300 grouping-structure analyses, reportedly
  CC BY 4.0 [U]. They are mostly short monophonic excerpts, so a weak fit for polyphonic
  onset-level phrase ends.
- **Schubert Winterreise Dataset** (Weiss et al.): harmony and form annotations for a vocal
  cycle [U]. Form is coarser than phrase.
- **JKU-PDD**: 5 pieces with pattern and phrase annotations, one Chopin (a mazurka) [U]. Too
  small.
- An arXiv API sweep ("phrase AND cadence", "phrase segmentation symbolic", sorted by date) and
  web searches found **no new 2026 Romantic phrase dataset**.

**Recommendation for the R-08d 5-movement draw.**
1. **Pool:** DCML Romantic corpora that have PianoCoRe/ASAP performances: `chopin_mazurkas`,
   `grieg_lyric_pieces`, `tchaikovsky_seasons`, `schumann_kinderszenen` and `liszt_pelerinage`.
   Draw **one movement per corpus with a seed**, stratified as in R-08c by rendered size within
   each corpus. This covers 5 composers.
   - Exclude movements with fewer than 5 ends (some Grieg and Rachmaninoff pieces have 1).
   - Exclude pieces in compound or changing meter, to keep R-08c's "simple meters" scope, or
     disclose them.
2. **If the lead wants target composers only:** draw 5 mazurkas from the 33 that are in
   PianoCoRe tier A. The cost is less stylistic breadth: all are in 3/4 and use the same dance
   genre.
3. **Recognition risk:** Kinderszenen (Träumerei) and the best-known mazurkas are as famous as
   the Batik Mozart pieces. Keep the R-08b-style within-piece recognition analysis. If a clean
   control is wanted, Dvořák's Silhouettes (rank 6) is the unfamiliar Romantic control. It has
   no performances, which does not matter for an LLM label test.
4. **Loader:** D-12's `dcml_jc_bach` loader reads the same MS3 `.mscx` plus TSV layout. The
   Romantic TSVs add columns (for example `special`), so a `data-engineer` ticket is needed to
   generalise it and re-run the leakage check. The MuseScore files embed the labels.
5. **All candidates are CC BY-NC-SA 4.0** (`.zenodo.json`). Register them in DATASETS.md
   before use.
6. **Pre-cutoff caveat:** DCML labels predate the model cutoff by more than a year. If R-08d
   must rule out label exposure, the OWNER task (Henry or a teacher labels about 5 passages)
   is the only option. A mazurka or a MAJEPPA practice piece would suit it best.

## 3. Models and tools

### 3.1 Transcription
- **Transkun**: notes, velocity, sustain and soft pedal. Strongest open piano model.
  https://github.com/Yujia-Yan/Transkun
- **Aria-AMT**: robust to recording conditions; needs Python 3.11.
  https://github.com/EleutherAI/aria-amt
- **Kong HPT**: `piano-transcription-inference`; old torch.
- **hFT-Transformer** (Sony): no pedal.
- **Score-informed velocity refinement** (SMC 2026). https://arxiv.org/abs/2508.07757
- **Robustness studies**: models overfit to MAESTRO acoustics
  (https://arxiv.org/abs/2402.01424). Velocity is more fragile than onsets
  (https://arxiv.org/abs/2512.14602).

### 3.2 Alignment
- **parangonar**: DualDTWNoteMatcher, TheGlueNoteMatcher, online matchers.
  https://github.com/sildater/parangonar
- **partitura**: the data layer. https://github.com/CPJKU/partitura
- **synctoolbox** (audio-score, coarse). https://github.com/meinardmueller/synctoolbox
- **Matchmaker**: real-time following, about 240 ms median error.
  https://github.com/pymatchmaker/matchmaker

### 3.3 Embeddings and quality prediction
- **MuQ**: beats MERT on MARBLE; weights CC-BY-NC; use fp32, 24 kHz input.
  https://github.com/tencent-ailab/MuQ
- **MERT**: https://huggingface.co/m-a-p
- **CLaMP 3**: https://github.com/sanderwood/clamp3
- **Aria**: piano MIDI LM + embedding model, Apache-2.0. [V 2026-09-27]
  - About **650M parameters** (`aria-medium-base` 658.5M, `aria-medium-embedding` 632.1M). It uses
    a LLaMA 3.2 1B-style architecture but is not 1B parameters.
  - Trained on about 60k h of Aria-MIDI (CC BY-NC-SA).
  - https://github.com/EleutherAI/aria
- **PianoJudges** (Zhang, Liang, Dixon, ISMIR 2024). [V 2026-09-27]
  - 2-way expertise ranking: 93.56% (Audio-MAE).
  - Chopin Competition 2015 pairs: 49-60% across encoders, best 60.49%, against a 50% chance
    level.
  - **Caveat from the paper itself:** the beginner / advanced / virtuoso groups "differ not only
    on performance but also on repertoire and recording environment". Beginners are 562 mostly
    adult self-taught practice recordings; virtuosi are ATEPP commercial recordings.
  - So the 93.6% is not a same-piece, same-room skill result.
  - https://arxiv.org/abs/2407.04518
- **Dhiman 2026** (arXiv v1 only, no venue): MuQ layers 9-12 reach R² 0.537 on PercePiano vs
  0.347 for a symbolic model, on rendered audio. https://arxiv.org/abs/2601.19029
  [V 2026-09-27; see `2026-09-27-crescendai.md`]
  - The split is PercePiano's leave-passage-out folds, **not leave-piece-out**.
  - 0.537 averages 3 of 4 folds. The clean 4-fold Salamander run gives 0.536.
  - The quoted CI and p-value belong to other experiments.
  - The symbolic baseline is PercePiano's HAN trained from scratch. The comparison does not
    isolate modality.
  - Code: **CrescendAI** (MuQ + Transkun + score following + LLM teacher), CC BY-NC 4.0. No
    public weights found. https://github.com/Jai-Dhiman/crescendai
- **LLaQo** (ICASSP 2025): audio-LLM feedback. https://arxiv.org/abs/2409.08795
- **MAJEPPA / EVPMR benchmark**: https://arxiv.org/abs/2608.11026
- **MAESTROCaps / MuNo-SP**: https://arxiv.org/abs/2609.10351
- **Listener-rating prediction under distribution shift** (Bai, Hui, Li, Han, *Electronics*
  15(17):3855, 2026-08-27). [V 2026-09-27, abstract only via OpenAlex; the MDPI page returns 403]
  - Setup: PercePiano, frozen MERT and MuQ, 1,072 human-performance segments, with the reference
    renderings excluded.
  - Rank association with mean ratings, held-out composition vs held-out performer:
    - MERT 0.203 vs 0.599;
    - MuQ 0.206 vs 0.629.
  - Renderer transfer penalties were positive in all four encoder-source pairs.
  - Whether "composition ID" means a whole work or a PercePiano passage is not stated in the
    abstract.
  - https://doi.org/10.3390/electronics15173855
- **Profy** (Kawamura, Nakamura, Nishioka, Shioki, Furuya, Rekimoto, DIS 2026; arXiv 2606.10627).
  [V 2026-09-27, full text] (L-03 2026-09-27)
  - Data: 80 pianists (73 in the valid set), 1,083 takes of 9 scales and 6 arpeggios.
    - 1 kHz optical key-position sensing (HackKey) plus audio.
    - Expert vs amateur take labels come from a median split of 6,517 ratings by 53 raters.
  - Results:
    - Weakly supervised classification, 3-fold performer-disjoint.
    - The highlight score matched spans marked by 21 expert pianists on 20 clips: r 0.61,
      ROC-AUC 0.75.
  - Scales and arpeggios only, so no piece hold-out question arises.
  - https://arxiv.org/abs/2606.10627
- **MuSP-Bench** (arXiv 2608.28212, 2026-08-28). [V 2026-09-27, abstract] (L-03 2026-09-27)
  - 490 human-written questions on score and performance understanding (piano and orchestral).
  - Frontier multimodal LLMs struggle with scores and even more with performance audio.
  - https://arxiv.org/abs/2608.28212
- **A Dual Evaluation for Music Transcription** (Wang, Yang, Tamer, Ebert, Smith; arXiv 2608.04511,
  2026-08). [V 2026-09-27, abstract] (L-03 2026-09-27)
  - A listening study: over 100 participants, 230 piano recordings, 23 works, 30 performers.
  - Among playback-similarity metrics, CLEWS correlated best with human judgments.
  - https://arxiv.org/abs/2608.04511
- **General audio LLMs** are weak at hearing harmony and meter.
  https://arxiv.org/html/2510.19055, https://arxiv.org/html/2510.22455

### 3.4 Expression models
- **Basis Mixer**: https://github.com/CPJKU/basismixer
- **VirtuosoNet**: https://github.com/jdasam/virtuosoNet
- **ScorePerformer**: https://github.com/ilya16/ScorePerformer
- **DExter**: https://github.com/anusfoil/DExter
- **Pianist Transformer** (You et al., ICML 2026; arXiv v2 2026-06-25). [V 2026-09-27]
  - 136M parameters, pretrained on 10B MIDI tokens, fine-tuned on ASAP.
  - Code and weights are Apache-2.0 (HF `yhj137/pianist-transformer-*`).
  - https://arxiv.org/abs/2512.02652, https://github.com/yhj137/PianistTransformer
- **SyMuPe / PianoFlow** (Borovik, Gavrilev, Viro, ACM MM 2025). [V 2026-09-27]
  - The ScorePerformer successor.
  - About 25M-parameter PianoFlow, EncDec and MLM models trained on PERiScoPe.
  - Weights on HF `SyMuPe/*` (CC BY-NC-SA 4.0); code Apache-2.0.
  - https://github.com/ilya16/SyMuPe
- **RenCon 2025** (Zhang et al.). [V 2026-09-27]
  - 9 entries. Rule-based Director Musices won the preliminary round (4.33/5).
  - VirtuosoNet won the live round (3.62/5).
  - The human reference scored 4.40/5; 75% of 48 respondents identified it.
  - Dynamics-related variability correlated with audience scores more consistently than large
    tempo deviations did. Timing variability also correlated positively.
  - https://arxiv.org/abs/2605.02059

- **Delta-VA** (Ching and Widmer, ISMIR 2026; arXiv 2607.28876). [V 2026-09-27, abstract]
  (L-03 2026-09-27)
  - Predicts each performance's valence-arousal *deviation from an average performance*, from
    performance-only features.
  - Data: 6 commercial recordings of WTC Book I.
  - Directions are right, but predicted magnitudes are compressed.
  - This is the same "relative to the reference distribution" framing as tier D.
  - https://arxiv.org/abs/2607.28876

## 4. Human judgment
- **Tsay 2013 (PNAS)**: people identified competition winners better from silent video than from
  audio. Replicated by Mehr 2018 (fragile to design) and Vogt 2026.
  https://www.pnas.org/doi/10.1073/pnas.1221454110
- **Kroger and Margulis 2017** (*Psychology of Music* 45(1):49-64; online 2016). [V 2026-09-27, abstract]
  - Listeners **without formal music training** heard pairs of solo-piano performances: one by a
    conservatory student, one by a world-renowned professional.
  - Experiment 1: listeners were asked to pick the professional. Choices reflected both the true
    professional and a bias toward the second item.
  - Experiment 2: listeners were told, correctly or not, who played each item, then gave a
    preference. Performer identity, order and the label all influenced preference.
  - This is the closest prior work to Phase 4.
  - https://doi.org/10.1177/0305735616642543
- **Morijiri and Welch 2022**: pianists judge peers on tone, phrasing, pedalling and expression
  more than on precision.
- **Contextual-embedding metrics vs listener MOS**: Kendall tau about 0.44-0.51.
  https://arxiv.org/html/2607.27909v1
- **Novelty check**: no study has combined blind pairwise preference across skill levels, a
  Bradley-Terry fit and regression on measured features. No pairwise-preference dataset of human
  piano performances exists.

## 5. Products (none score interpretation)

| Product | Status |
|---|---|
| Simply Piano, Yousician, Flowkey, Skoove, Playground Sessions | Note and rhythm accuracy |
| Piano Marvel | Adds adaptive sight-reading tests |
| SmartMusic, MatchMySound | Accuracy scoring for school ensembles |
| ROLI AI Music Coach (Feb 2026) | Hands and posture via camera |
| Tonara | Shut down 2023 |
| Roland Piano Every Day | Discontinued |
| ABRSM and Trinity exams | Human-marked |

## 6. Methods references (L-03 methods pass, 2026-09-28)

Primary sources for the statistical and psychophysical methods used in `src/` and `study/`.
"[V 2026-09-28, metadata]" means I checked authors, title, journal, volume and pages against the
publisher record (Crossref DOI lookup); "abstract" or "full text" means I also read that.

### 6.1 Listening-study methods (`study/app/`, `study/protocol-S03.md`)
- **Woods, Siegel, Traer, McDermott 2017**, "Headphone screening to facilitate web-based auditory
  experiments", *Attention, Perception, & Psychophysics* 79(7):2064-2072.
  https://doi.org/10.3758/s13414-017-1361-2 (PMC5693749) [V 2026-09-28, full text]
  - Six trials of a 3-AFC "which tone is quietest?" task. Three 200 Hz pure tones, 1000 ms each
    with 100 ms Hann ramps, 500 ms apart. One tone is 6 dB quieter; one of the two louder tones is
    phase-reversed between the channels. Over loudspeakers the antiphase tone cancels and sounds
    quietest.
  - Pass is at least 5 of 6 correct. Online, 64.7% of 5,154 participants passed.
  - `study/app/app.js` matches these parameters. The one retry is ours, not theirs.
- **Milne, Bianco, Poole, Zhao, Oxenham, Billig, Chait 2021**, "An online headphone screening
  test based on dichotic pitch", *Behavior Research Methods* 53:1551-1562.
  https://doi.org/10.3758/s13428-020-01514-0 [V 2026-09-28, abstract]
  - A Huggins-pitch test that they report as more selective for headphones than the Woods test.
  - Combining it with the Woods test lowers the false-positive rate to about 7%.
  - JavaScript code is public. **An option for S-03 if loudspeaker listeners slip through.**
- **Bradley and Terry 1952**, "Rank analysis of incomplete block designs: I. The method of paired
  comparisons", *Biometrika* 39(3/4):324-345. https://doi.org/10.1093/biomet/39.3-4.324
  (JSTOR DOI 10.2307/2334029) [V 2026-09-28, metadata]. Used in `src/pianolens/eval/bradley_terry.py`.
- **Comparative-judgement reliability** (Kinnear et al. 2025; Verhavert et al. 2019; Bramley and
  Vitello 2019): see 1.4. The protocol's "Bramley's caveat" (section 7.6) is Bramley and Vitello
  2019.
- **Psychometric function with a lapse rate** (protocol 7.1): Wichmann and Hill 2001, "The
  psychometric function: I. Fitting, sampling, and goodness of fit", *Perception &
  Psychophysics* 63(8):1293-1313. https://doi.org/10.3758/BF03194544 [V 2026-09-28, metadata]
- **Cluster-robust (CR1 sandwich) standard errors** (protocol 7.1-7.2): Cameron and Miller 2015,
  "A practitioner's guide to cluster-robust inference", *Journal of Human Resources*
  50(2):317-372. https://doi.org/10.3368/jhr.50.2.317 [V 2026-09-28, metadata]
- **Equivalence reading of H6** (protocol section 2: two one-sided tests, intersection-union test
  with no multiplicity correction):
  - Schuirmann 1987, *Journal of Pharmacokinetics and Biopharmaceutics* 15(6):657-680 (TOST).
    https://doi.org/10.1007/BF01068419 [V 2026-09-28, metadata]
  - Berger 1982, "Multiparameter hypothesis testing and acceptance sampling", *Technometrics*
    24(4):295-300 (intersection-union tests). https://doi.org/10.1080/00401706.1982.10487790
    [V 2026-09-28, metadata]
- **Loudness normalization** (protocol 3.2): ITU-R BS.1770, as implemented by pyloudnorm. [U]
  I did not check which revision pyloudnorm follows.

### 6.2 Reliability
- **Spearman-Brown prophecy formula** `k r / (1 + (k - 1) r)`. The standard cite is the pair of
  back-to-back papers in *British Journal of Psychology* 3(3), 1910 [V 2026-09-28, metadata]:
  - Spearman, "Correlation calculated from faulty data", 271-295.
    https://doi.org/10.1111/j.2044-8295.1910.tb00206.x
  - Brown, "Some experimental results in the correlation of mental abilities", 296-322.
    https://doi.org/10.1111/j.2044-8295.1910.tb00207.x
- **ICC** (`src/pianolens/features/takes.py`) [V 2026-09-28, metadata]:
  - McGraw and Wong 1996, "Forming inferences about some intraclass correlation coefficients",
    *Psychological Methods* 1(1):30-46. https://doi.org/10.1037/1082-989X.1.1.30
  - Shrout and Fleiss 1979, "Intraclass correlations: uses in assessing rater reliability",
    *Psychological Bulletin* 86(2):420-428. https://doi.org/10.1037/0033-2909.86.2.420

### 6.3 Dimensionality and covariance (`features/interpretation.py`, `eval/dimensionality.py`)
- **Horn 1965**, "A rationale and test for the number of factors in factor analysis",
  *Psychometrika* 30(2):179-185. https://doi.org/10.1007/BF02289447 [V 2026-09-28, abstract]
  - The original compares eigenvalues of the sample correlation matrix with those from random
    uncorrelated data of the same size. Our "horn" variant keeps the idea but swaps the null
    for phase-randomized surrogates of the curves. It is an adaptation, not Horn's test as
    published.
- **Green, Levy, Thompson, Lu, Lo 2012**, "A proposed solution to the problem with using
  completely random data to assess the number of factors with parallel analysis", *Educational
  and Psychological Measurement* 72(3):357-374 (online 2011).
  https://doi.org/10.1177/0013164411422252 [V 2026-09-28, abstract]
  - Revised parallel analysis: the k-th eigenvalue is tested against a null that already
    contains the first k - 1 factors, not against pure noise. Their recommended form uses
    principal axis factoring and the 95th percentile.
  - This is the right cite for the `"sequential"` variant in `interpretation.py`. That variant
    uses PCA and envelope surrogates of the residual, so it too is an adaptation.
- **Ledoit and Wolf 2004**, "A well-conditioned estimator for large-dimensional covariance
  matrices", *Journal of Multivariate Analysis* 88(2):365-411.
  https://doi.org/10.1016/S0047-259X(03)00096-4 [V 2026-09-28, metadata]. This is the
  estimator in `sklearn.covariance.LedoitWolf`.
- **Phase-randomized surrogates** (`eval/dimensionality.phase_randomize`, used as the null in
  both parallel-analysis variants): Theiler, Eubank, Longtin, Galdrikian, Farmer 1992, "Testing
  for nonlinearity in time series: the method of surrogate data", *Physica D* 58(1-4):77-94.
  https://doi.org/10.1016/0167-2789(92)90102-S [V 2026-09-28, metadata]

### 6.4 Smoothing (`features/tempo.py`, `eval/dimensionality.py`)
- **Eilers and Marx 1996**, "Flexible smoothing with B-splines and penalties", *Statistical
  Science* 11(2). https://doi.org/10.1214/ss/1038425655 [V 2026-09-28, abstract]. Many
  equally spaced B-splines plus a difference penalty on adjacent coefficients. Pages 89-121
  [U]: the publisher metadata gives no page range.
- **Whittaker smoother** (`eval/dimensionality.whittaker_smooth`): Eilers 2003, "A perfect
  smoother", *Analytical Chemistry* 75(14):3631-3636. https://doi.org/10.1021/ac034173t
  [V 2026-09-28, metadata]
