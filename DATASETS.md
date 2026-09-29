# Datasets

The manifest of every dataset on disk. The `data-engineer` agent owns it. Data lives under
`data/raw/<name>/`, which is gitignored and never committed.

**Licenses:** nearly all of these are non-commercial. Research use only (CLAUDE.md, rule 4).

| Name | Path | Source | Version / commit | License | Size | Loader | Contents | Status |
|---|---|---|---|---|---|---|---|---|
| (n)ASAP | `data/raw/asap` | https://github.com/CPJKU/asap-dataset | commit 4097b45 (2025-07-31, (n)ASAP v2.1), shallow clone 2026-09-27 | CC BY-NC-SA 4.0 | 1.9 GB | `pianolens.data.asap` (`iter_asap`) | 1,066 Disklavier performance MIDI, 242 MusicXML score folders (222 composer+title pieces), 1,063 note-alignment TSVs + match files (in the repo, no separate release) | loaded: 1,066/1,066 perf + score, 1,063 with alignment, 0 failures |
| PercePiano | `data/raw/percepiano` | https://github.com/JonghoKimSNU/PercePiano | commit e672299 (2024-10-21), shallow clone 2026-09-27 | data CC BY-NC-ND 4.0 (paper, Sci. Rep. 2024); repo code MIT (`LICENSE`) | 45 MB | `pianolens.data.percepiano` (`iter_percepiano`, `load_percepiano_ratings`, `load_percepiano_official_means`) | 1,202 segment MIDI (4 works), 1,202 segment MusicXML, per-rater labels (14,934 CSV rows), authors' mean labels (1,189 segments) | loaded: 1,202/1,202 segments + scores, 0 failures; ratings for 1,189 segments from 63 raters |
| Salamander C5 Light (soundfont asset, S-02) | `data/raw/soundfonts/salamander_c5_light` | hed-sounds, https://sites.google.com/view/hed-sounds/salamander-c5-light ; Google Drive id `0B5gPxvwx-I4KWjZ2SHZOLU42dHM` (the id CrescendAI's `render_midi.py` downloads, commit 1ec53b10) | `SalC5Light2.sf2` dated 2017-07-23, sha256 `f0c8cb73...68fca4`; zip sha256 `ece48e17...6d6eb9`; fetched 2026-09-27 | SF2: no resale or repackaging for sale (`license.txt`); underlying samples: Salamander Grand Piano by Alexander Holm, CC BY 3.0. Research use fine; do not redistribute | 25 MB | `pianolens.audio.render` | One SF2 piano (Yamaha C5 samples, 7 velocity layers, 44.1 kHz) | renders PercePiano 1,202/1,202 |
| PianoCoRe | `data/raw/pianocore` | https://doi.org/10.5281/zenodo.19186016 (also HF `SyMuPe/PianoCoRe`, GitHub ilya16/PianoCoRe) | Zenodo v1.0, downloaded 2026-09-27. sha256 refined.zip `68f1b182741387eb8c74d98a5805bc382435136e8c9228dabe351627cc74ef0f`, raw-midi.zip `c9bff1c6f1d859fe45be9c7ff30e1a5d199808d2ba3a4d08524f4dee5b5ce804`; md5 of all 4 files match Zenodo | CC BY-NC-SA 4.0 | 6.2 GB | `pianolens.data.pianocore` (`PianoCoRe(tier="a"/"a_star").iter_aligned`) | metadata.csv (250,046 rows, tier flags), refined.zip (refined score + performance MIDI + note alignment npz for 184,230 rows), raw-midi.zip (250,046 raw performance MIDI, 1,607 MusicXML/MXL scores). raw-alignments.zip (5.2 GB) not downloaded | downloaded; full tier A pass cached (D-07): 157,207/157,207 performances, 0 failures, 9 with pitch-disagreeing pairs; see "PianoCoRe tier A cache" |
| Expert-Novice | `data/raw/expert_novice` | https://zenodo.org/records/8392772 | Zenodo record 8392772, 2026-09-27; md5 of all 4 files match; sha256 recordings zip `2a2b2029767a9b5b3038aab0984132c4b0fd4204d75cf3d828f82bf4f6bfb1c3` | CC BY-NC-SA 4.0 | 1.1 GB (WAV) | `pianolens.data.expert_novice` (`load_ratings`, `recordings_index`, `load_beat_alignment`) | 83 WAV (48 kHz) of 7 pieces by 21 players, 83 beat alignments, 7 MXL scores, 803 ratings (4 instructors + novices), self-rated skill | loaded: 83/83 recordings, 803 ratings (paper: 83, 803) |
| NeuroPiano | `data/raw/neuropiano` | https://huggingface.co/datasets/anusfoil/NeuroPiano-data | HF commit 1341e63, 2026-09-27 | MIT (dataset card) | 197 MB (audio in parquet) | `pianolens.data.neuropiano` (`load_ratings`, `load_audio_bytes`) | 104 student recordings, 39 students, 35 raters, 13 questions, score 0-6, JP + EN text answers | loaded: 2,265 rows, 104 recordings (card: 2,255 entries, 104 recordings) |
| Vienna 4x22 | `data/raw/vienna4x22` | https://github.com/CPJKU/vienna4x22 | commit 1033ade, shallow clone 2026-09-27 | CC BY 4.0 | 23 MB | `pianolens.data.vienna4x22` (`iter_aligned`) | 88 match files (4 excerpts x 22 pianists), Boesendorfer SE MIDI, MusicXML scores | loaded: 88/88 with ground-truth alignment, 0 failures |
| Batik-plays-Mozart | `data/raw/batik_mozart` | https://github.com/huispaty/batik_plays_mozart | commit 9c5f700, submodule `annotations` = DCMLab/mozart_piano_sonatas 7cfeb73 | CC BY-NC-SA 4.0 (LICENSE.md); DCML annotations submodule CC BY-NC-SA 4.0 (`annotations/LICENSE`, checked 2026-09-27 by F-04b) | 306 MB | `pianolens.data.batik_mozart` (`iter_aligned(musicxml_score=)`, `load_aligned`, `performed_score`, `phrase_annotations`, `load_note_annotations`; D-11) | 36 movements: match files, MIDI, MusicXML, per-note harmony / cadence / phrase CSVs | loaded: 36/36 with ground-truth alignment, 0 failures |
| DCML J. C. Bach keyboard sonatas (D-12) | `data/raw/dcml_jc_bach` | https://github.com/DCMLab/jc_bach_sonatas (Zenodo DOI 10.5281/zenodo.14996292; data report Hentschel et al. 2025, Sci. Data 12:685) | tag v2.4, commit ac9fd07 (`ac9fd07905eb62c3d8cfbd96811491170a216232`, 2025-04-27), shallow clone 2026-09-28 | CC BY-NC-SA 4.0 (README badge and `.zenodo.json`; no LICENSE file, GitHub shows no SPDX) | 38 MB | `pianolens.data.dcml_jc_bach` (`load_score` label-free, `phrase_annotations`, `iter_scores`, `label_strings`; a wrapper of `pianolens.data.dcml` since D-13, outputs unchanged) | score-only: 29 movements of op. 5 and op. 17 (12 sonatas) as MuseScore 3 `.mscx` with embedded DCML labels, ms3 TSVs (`notes`, `measures`, `chords`, `harmonies`), PDFs, `reviewed/`; no performances, no MusicXML | loaded: 29/29, 0 failures; notes = metadata `n_onsets` in 29/29; unfolding = metadata bar count and length in 29/29; 442 phrase ends and 406 cadence labels (folded), all mapped |
| DCML Chopin Mazurkas (D-13) | `data/raw/dcml_chopin_mazurkas` | https://github.com/DCMLab/chopin_mazurkas (Zenodo concept DOI 10.5281/zenodo.7473566) | tag v3.2, commit 5931135 (`5931135e614985023b96de2a291c74b7ef90b287`, 2025-04-27), sparse shallow clone 2026-09-28 (`notes`, `measures`, `chords`, `harmonies`, `metadata.tsv`, README, LICENSE; no `MS3/`) | CC BY-NC-SA 4.0 (`LICENSE`, `.zenodo.json`) | 10 MB | `pianolens.data.dcml` (`load_score(corpus, stem)` label-free, `phrase_annotations`, `iter_scores`, `label_strings`, `pieces(labelled=)`; D-13) | score-only: 56 mazurkas (all 3/4) as ms3 TSVs; 55 with DCML labels (op. 30/1 has no `harmonies/`) | loaded: 56/56, 0 failures; notes = metadata `n_onsets` in 56/56; unfolding = metadata in 52/56 (4 hand-checked, see notes); 606 phrase ends, 344 cadence labels (folded), all mapped |
| DCML Grieg Lyric Pieces (D-13) | `data/raw/dcml_grieg_lyric_pieces` | https://github.com/DCMLab/grieg_lyric_pieces (Zenodo concept DOI 10.5281/zenodo.7473578) | tag v2.3, commit 91a3045 (`91a304563521f3f273b8c0aadec1ce2ede2d1384`, 2025-04-27), sparse shallow clone 2026-09-28 (`notes`, `measures`, `chords`, `harmonies`, `metadata.tsv`, README, LICENSE; no `MS3/`) | CC BY-NC-SA 4.0 (`LICENSE`, `.zenodo.json`) | 12 MB | `pianolens.data.dcml` (`load_score(corpus, stem)` label-free, `phrase_annotations`, `iter_scores`, `label_strings`, `pieces(labelled=)`; D-13) | score-only: 66 pieces (10 books) as ms3 TSVs, all labelled | loaded: 66/66, 0 failures; notes = `n_onsets` 66/66; unfolding = metadata 66/66; 559 phrase ends, 433 cadence labels, all mapped |
| DCML Tchaikovsky The Seasons (D-13) | `data/raw/dcml_tchaikovsky_seasons` | https://github.com/DCMLab/tchaikovsky_seasons (Zenodo concept DOI 10.5281/zenodo.7473586) | tag v2.3, commit 281afa3 (`281afa3c6637b7f881fc18928f074f3f9d7dbfcf`, 2025-04-27), sparse shallow clone 2026-09-28 (`notes`, `measures`, `chords`, `harmonies`, `metadata.tsv`, README, LICENSE; no `MS3/`) | CC BY-NC-SA 4.0 (`LICENSE`, `.zenodo.json`) | 3.2 MB | `pianolens.data.dcml` (`load_score(corpus, stem)` label-free, `phrase_annotations`, `iter_scores`, `label_strings`, `pieces(labelled=)`; D-13) | score-only: 12 pieces of op. 37a as ms3 TSVs, all labelled | loaded: 12/12, 0 failures; notes = `n_onsets` 12/12; unfolding = metadata 12/12; 298 phrase ends, 185 cadence labels, all mapped |
| DCML Schumann Kinderszenen (D-13) | `data/raw/dcml_schumann_kinderszenen` | https://github.com/DCMLab/schumann_kinderszenen (Zenodo concept DOI 10.5281/zenodo.7473582) | tag v2.3, commit ee929c1 (`ee929c1556bc937fe1ea7303cac4476e37caa4d1`, 2025-04-27), sparse shallow clone 2026-09-28 (`notes`, `measures`, `chords`, `harmonies`, `metadata.tsv`, README, LICENSE; no `MS3/`) | CC BY-NC-SA 4.0 (`LICENSE`, `.zenodo.json`) | 1.4 MB | `pianolens.data.dcml` (`load_score(corpus, stem)` label-free, `phrase_annotations`, `iter_scores`, `label_strings`, `pieces(labelled=)`; D-13) | score-only: 13 pieces of op. 15 as ms3 TSVs, all labelled | loaded: 13/13, 0 failures; notes = `n_onsets` 12/13 (no. 7: 3 orphan tie heads, see notes); unfolding = metadata 13/13; 87 phrase ends, 79 cadence labels, all mapped |
| DCML Liszt Années de pèlerinage (D-13) | `data/raw/dcml_liszt_pelerinage` | https://github.com/DCMLab/liszt_pelerinage (Zenodo concept DOI 10.5281/zenodo.7473580) | tag v2.3, commit f1cfd30 (`f1cfd308adba5763aad3a18885eac48d42449fc4`, 2025-04-27), sparse shallow clone 2026-09-28 (`notes`, `measures`, `chords`, `harmonies`, `metadata.tsv`, README, LICENSE; no `MS3/`) | CC BY-NC-SA 4.0 (`LICENSE`, `.zenodo.json`) | 9.7 MB | `pianolens.data.dcml` (`load_score(corpus, stem)` label-free, `phrase_annotations`, `iter_scores`, `label_strings`, `pieces(labelled=)`; D-13) | score-only: 19 pieces of S.160-162 as ms3 TSVs, all labelled | loaded: 19/19, 0 failures; notes = `n_onsets` 16/19 (4 orphan tie heads in 3 pieces); unfolding = metadata 19/19 (length to 0.01 quarter: metadata is rounded); 277 phrase ends, 272 cadence labels, all mapped |
| MazurkaBL | `data/raw/mazurkabl` | https://github.com/katkost/MazurkaBL | commit 00c5b67, shallow clone 2026-09-27 | CC BY-NC-SA 4.0 (README only, no LICENSE file) | 900 MB | `pianolens.data.mazurkabl` (`load_beat_curves`, `iter_beat_curves` -> `BeatCurve`; `load_mazurka`, `load_all` long DataFrame) | beat times + normalised beat loudness per recording, markings, sones curves, 44 MusicXML scores | loaded: 46 mazurkas, 2,098 recordings, 700,008 beat rows (landscape: 44 mazurkas, ~2,000 recordings) |
| PianoJudges labels | `data/raw/pianojudges` | https://github.com/anusfoil/PianoJudges | commit 79dd1b7, shallow clone 2026-09-27 | unclear (no LICENSE file) | 6.7 MB | `pianolens.data.pianojudges` (`load_cipi_index`, `load_channel_lists`, `load_technique_urls`) | code repo; CIPI label index (652 works, Henle 1-9, 5 folds), YouTube channel / URL lists by expertise and technique. No audio or MIDI | loaded: 652 CIPI works, 73 channel lines (18 advanced, 55 novice; 3 active), 167 technique URLs (headers mix technique names and annotator notes) |
| MAESTRO v3 (MIDI) | `data/raw/maestro_v3_midi` | https://magenta.tensorflow.org/datasets/maestro | v3.0.0 `maestro-v3.0.0-midi.zip`, sha256 `70470ee253295c8d2c71e6d9d4a815189e35c89624b76d22fce5a019d5dde12c`, 2026-09-27 | CC BY-NC-SA 4.0 | 139 MB | `pianolens.data.maestro` (`iter_performances`) | 1,276 Disklavier MIDI (962 train / 137 validation / 177 test), no audio | loaded: 1,276/1,276, 7,040,150 notes, 0 failures |
| PSyllabus | `data/raw/psyllabus` | https://zenodo.org/records/14794592 | Zenodo 14794592, 2026-09-27; md5 match; sha256 mid.zip `2142b223650e35b2692798169f59269ae11e0b39f75ffa9decaa9045ec636a02` | conflicting: record metadata CC BY 4.0, description "Research use only" | 146 MB | `pianolens.data.psyllabus` (`psyllabus_index`, `iter_performances`) | 7,901 transcribed MIDI with difficulty 0-10 from syllabi, 5 folds. cqt5.zip (2 GB) not downloaded | loaded: 7,900/7,901 (1 empty MIDI: Tchaikovsky Impromptu op 72 no 1); fold 0: 4,736 train / 1,575 val / 1,589 test |
| MAJEPPA | `data/raw/majeppa` | https://huggingface.co/datasets/kkwsts/MAJEPPA-Dataset (paper arXiv 2608.11026, code github kkwsts/majeppa) | HF commit 7a462f4, 2026-09-27 | unclear: HF `license: other`, "mixed-see-description", no terms stated | 148 MB | `pianolens.data.majeppa` (`iter_aligned`, `load_dtw_path`) | 4,449 transcribed performance MIDI, 886 score MIDI, expertise level (6) x recording type (7), DTW time alignment (not note-level), YouTube links | loaded: 4,449 performances (card: 4,449; paper abstract: 3,979); 4,207 with a score id, 4,199 of them with a parsed score; 8 point at score MIDI partitura cannot read (yielded with score=None) |
| PianoVAM (D-10) | `data/raw/pianovam` | https://huggingface.co/datasets/PianoVAM/PianoVAM_v1 (ISMIR 2025, arXiv 2509.08800; project page https://yonghyunk1m.github.io/PianoVAM) | v1.2, HF commit 1f039ab9, fetched 2026-09-27 (`MIDI/*`, `metadata.json`, `README.md` only) | CC BY-NC-SA 4.0 (dataset card; the ticket said CC BY-NC) | 6.2 MB MIDI + **4.4 GB audio subset** (A-01b, 2026-09-28: 84 of 107 `Audio/*.wav`, mono 44.1 kHz, list in `Audio_SUBSET.txt`, sha256 per file in `Audio_SHA256SUMS.txt`; all except the 4-hands take and the 22 largest of Yonghyun's 34 train takes). Full audio 6.7 GB; video and hand skeletons (about 38 GB) not downloaded | `pianolens.data.pianovam` (`iter_performances`, `pianovam_index`) | 107 Disklavier practice recordings, 10 amateur pianists (none music majors), self-reported skill (Advanced 70 recordings / 3 pianists, Intermediate 27 / 4, Beginner 10 / 3), 70 free-text pieces; **no scores** | loaded: 107/107, 0 failures, 527,302 notes, 96 with pedal events |
| Rach3, Hanon subset (D-10) | `data/raw/rach3` | https://github.com/Rach3Project/rach3_midi_dataset (ISMIR 2025) | commit a9519492 (`data/raw/rach3/COMMIT`), fetched 2026-09-27: `rehearsals/p{1,2,3}/*hanoncexercs*.mid`, `scores/hanoncexercs.musicxml`, README, LICENSE, piece list | CC BY-NC-SA 4.0 (repo LICENSE) | 21 MB (full repo about 350 MB, 3,160 MIDI, 136 MusicXML: not downloaded) | `pianolens.data.rach3` (`iter_performances`, `rach3_index`) | Hanon practice sessions: p1 124 files, p2 36 (advanced), p3 87 (beginner); p4 (advanced) has no Hanon. One file = one piece in one session, often 7 to 30 min with repeats and stops. The Hanon score is the whole book (22,071 notes, 1,433 bars) | loaded: 247/247, 0 failures, 1,396,336 notes, 18 files with pedal. Provenance tagged `sensor`: keyboard MIDI, instrument not stated in README. **BL-16 takes** (derived, `data/interim/rach3_hanon_takes/`, `scripts/build_rach3_hanon_takes.py`, loader `pianolens.data.rach3_takes.HanonTakes`): complete passes of Hanon Part I Nos. 1-20 against generated one-pass exercise scores; 2,038 takes, 1,149 pass QC (p1 372, p2 191, p3 586); Part II not split. p3 almost never repeats an exercise within a day |
| CIPI | (not downloaded) | https://zenodo.org/records/8037327 | v0.1 | n/a | 0 | none | scores + Henle difficulty labels | **gated**: Zenodo access restricted (request needed). Labels available via PianoJudges `index.json`; PSyllabus used as open substitute |
| MAESTRO-E | (not downloaded) | https://github.com/ben2002chou/Polytune (Globus endpoint) | n/a | unclear (repo: NOASSERTION) | 0 | none | synthetic mistakes injected into MAESTRO (Polytune, AAAI 2025) | **gated**: Globus login required. Can be regenerated from MAESTRO MIDI with github ben2002chou/CocoChorales-E_MAESTRO-E |
| SKY-Piano | (not downloaded) | https://joonhyungbae.github.io/skypiano/ (paper arXiv 2607.27296, ISMIR 2026) | checked 2026-09-27: no dataset download link; github joonhyungbae/skypiano returns 404; no HF or Zenodo record | **unclear**: paper text CC BY 4.0; dataset "per-modality license terms" (page and paper, section 9), terms not published | 0 | none | 7 professional + 12 amateur pianists, Disklavier DC7X MIDI, MusicXML, audio, video, mocap; slow C-major scale played by all 19 | **not available** (D-09 stopped). Explorer hosts 5 professional sample trials (graded pieces, no scales, no amateurs), under the same unstated terms; not downloaded |
| mistakes_v1 (synthetic mistake set, D-08) | `data/processed/mistakes_v1` | derived from (n)ASAP (above) by `scripts/build_mistake_set.py` with `pianolens.data.perturb` | v1, built 2026-09-27 (`spec.json` records specs, seeds, selection) | CC BY-NC-SA 4.0 (inherits (n)ASAP) | 21 MB | `pianolens.data.perturb.load_mistake_set` | 100 (n)ASAP Disklavier performances (robust GT alignment, single repeat path, <= 6,000 notes; 12 composers: Bach, Beethoven, Chopin, Haydn, Liszt, Mozart, Schubert 12 each, Schumann 5, Rachmaninoff 4, Scriabin 3, Debussy 2, Ravel 2), each as a clean copy (rate 0) and with injected mistakes at rates 0.02 / 0.05 / 0.10 (wrong pitch, extra, missed in equal shares); 400 performances, 246,324 notes per rate; per-note exact ground truth. Injected totals: rate 0.02: 1,592 wrong / 1,559 extra / 1,523 missed; 0.05: 3,922 / 3,894 / 3,863; 0.10: 7,813 / 7,791 / 7,754 | built, 0 failures, 53 s on 12 workers |
| study_s03 pilot stimuli (S-03 listening clips, S-01 degradations) | `data/interim/study_s03` | derived from Vienna 4x22, Batik-plays-Mozart and (n)ASAP/MAESTRO (above) by `scripts/build_study_s03.py` (spec `study/stimuli-S03.json`) with `pianolens.study.degrade` and the S-02 renderer | spec 0.1-pilot, built 2026-09-27 (`manifest.json` records seeds, render config, soundfont hash, FluidSynth 2.6.1, code state) | CC BY-NC-SA 4.0 (the most restrictive source: Batik, (n)ASAP); research use only, not for redistribution without O-02 review | 552 MB (592 WAV 44.1 kHz mono + MIDI + manifests) | `manifest.json` / `manifest.js` (read by `study/app/`) | 8 excerpts x 2 spans (detection, preference) x (original, 7 dimensions x 5 pilot levels, catch) | built; not yet listened to (pilot step 1) |
| SyMuPe EncDec-base (model weights asset, R-06) | HF cache `~/.cache/huggingface/hub/models--SyMuPe--EncDec-base` | https://huggingface.co/SyMuPe/EncDec-base (code github ilya16/SyMuPe, cloned in `experiments/2026-09-27-R-06-expression-model-h2h/envs/SyMuPe`, gitignored) | HF commit 1b942f28, code commit 13cc57d (symupe 1.1.0), fetched 2026-09-27 | weights CC BY-NC-SA 4.0 (trained on PERiScoPe v1.0); code Apache-2.0 | 192 MB | `experiments/2026-09-27-R-06-expression-model-h2h/adapters/symupe_adapter.py` (own venv) | 25.1M-parameter encoder-decoder score-to-performance model | loaded, scored 9,295 items and generated 106 passages; MPS crashes (float64), CPU only |
| Pianist Transformer rendering (model weights asset, R-06) | HF cache `~/.cache/huggingface/hub/models--yhj137--pianist-transformer-rendering` | https://huggingface.co/yhj137/pianist-transformer-rendering (code github yhj137/PianistTransformer, cloned in `.../envs/PianistTransformer`, gitignored) | HF commit 8f156820, code commit 747df2d, fetched 2026-09-27 | Apache-2.0 (weights and code); trained on Aria-MIDI etc. + ASAP (CC BY-NC-SA), so research use only in practice | 259 MB | `.../adapters/pt_adapter.py` (own venv: torch 2.7.1, transformers 4.54.0) | 135.7M-parameter T5-Gemma-style model; SFT held-out ASAP scores = its `data/midis/testset/score/0..22.mid` (matched to 23 ASAP folders, list in R-06 `prepare.py`) | loaded, scored 9,295 items (MPS) and generated 106 passages (CPU) |

## Per-dataset notes

Record quirks here: missing files, id mismatches, alignment problems.

### (n)ASAP (D-01, measured 2026-09-27 with `scripts/check_asap.py`, about 5 min)

- **Counts vs README.** README says 1,067 performances, 236 distinct scores (its table totals 222
  score folders). On disk: `metadata.csv` has 1,066 rows, 1,066 performance MIDI files, 242 score
  folders (`score_id`), 222 unique (composer, title) pairs. 834 rows have
  `robust_note_alignment == 1`, 228 have 0, 4 are blank.
- **Alignments ship in the repo** (`<perf>_note_alignments/note_alignment.tsv` and `<perf>.match`,
  v2.1). No separate download needed.
- **Missing alignments:** 3 performances have no alignment folder: Beethoven 17-2 `KaszoS10`,
  Beethoven 29-4 `DANILO01`, Schubert D.935/1 `Lisiecki10M`. The loader yields them with
  `alignment=None`.
- **metadata.csv bug:** the `note_alignments` column is mangled for all 28 Schubert D.899 rows
  (`Schubert/Impromptu_op_note_alignments/note_alignment.tsv`). The loader derives the path from
  the MIDI path instead; the files exist.
- **Alignment totals over 1,063 alignments:** 3,338,534 matches, 237,940 insertions, 259,624
  deletions, no other labels.
- **Score ids:** the MusicXML is parts-merged and maximally unfolded (partitura
  `unfold_part_maximal`), giving ids like `n22-1`, `n22-2`. 636 alignment score ids (over the
  whole set) are not in `Score.notes`: they name tied-continuation notes, which partitura's note
  array folds into the first note of the tie. Mostly deletions, a few matches (e.g. Ravel
  Alborada). 6,362 score notes are referenced by no alignment row.
- **Performance ids:** 22 alignment performance ids are not in the loaded note array; 475
  performed notes are not referenced by any alignment row. Not investigated further.
- **Piece ids:** 221 `PieceId`s (Schumann `Toccata` and `Toccata_repeat` share `schumann_op7`),
  201 canonical and 20 kept as `asap:<composer>/<title>` because the catalogue number is not
  certain from the title: Haydn sonatas (ASAP numbering unclear), Debussy, Ravel, Glinka, Bach
  Italian Concerto (movement unknown), Liszt Mephisto Waltz (number not in title).
  ASAP's `Gran_Etudes_de_Paganini_2_La_campanella` maps to `liszt_s141_no3`: La campanella is
  No. 3 of S.141, the ASAP "2" does not match that.
- **Performer ids are heuristic:** from the file name (`SunMeiting08` -> `asap:sunmeiting`,
  `Na_2009_02` -> `asap:na`). 322 ids. Same-surname pianists merge (e.g. `asap:huang`, 17
  performances), so leave-performer-out on ASAP is approximate.
- **Provenance:** all `disklavier` (Yamaha e-Competition via MAESTRO).

### Salamander C5 Light soundfont and renders (S-02, 2026-09-27, ml-researcher)

- **Which Salamander.** CrescendAI rendered PercePiano with "SalamanderC5-Light" (`SalC5Light2.sf2`)
  from hed-sounds, via the FluidSynth CLI at 44.1 kHz, gain 0.8, default reverb and chorus
  (`model/src/percepiano/audio/render_midi.py`, CrescendAI commit 1ec53b10). It is a 25 MB SF2
  conversion, not the 1.1 GB SFZ "Salamander Grand Piano V3". We use the same file.
- **Fetch:** `uvx gdown "https://drive.google.com/uc?id=0B5gPxvwx-I4KWjZ2SHZOLU42dHM" -O salamander.zip`,
  then unzip `SalC5Light2.sf2` and `license.txt` into `data/raw/soundfonts/salamander_c5_light/`.
  `pianolens.audio.render.SOUNDFONT_SHA256` pins the file.
- **Renders:** `scripts/render_percepiano.py` -> `data/interim/renders/salc5light2-fc5f24d36e3e/percepiano/`
  (`<stem>.wav`, 24 kHz mono PCM_16, plus `manifest.csv` and `render_meta.json`). 1,202/1,202 files,
  1.8 GB, 209 s wall with 8 workers. FluidSynth 2.6.1 (Homebrew). Durations 9.0-122.9 s (mean 33.1),
  including 2-3 s of FluidSynth tail after the last MIDI event. No loudness normalisation (velocity
  is the signal). Peak 0.046-1.178 (median 0.21); 8 files exceed full scale and clip in the WAV.
- The raters heard Logic Pro's "Yamaha Grand Piano", not this piano.

### PercePiano (D-02, measured 2026-09-27 with `scripts/check_percepiano.py`)

- **File names are `<work>_<N>bars_<player>_<segment>`.** The README says
  `<segment>_<player>`; the repo code and the data say otherwise. One file name starts with a
  space (` Schubert_D935_no.3_4bars_2_1.mid`); ids strip it.
- **Segments:** 1,202 MIDI files (paper: 1,202). By piece: `beethoven_woo80` 238,
  `schubert_d935_no3` 117, `schubert_d960_mv2` 288, `schubert_d960_mv3` 559. By length: 8 bars
  940, 16 bars 145, 4 bars 117. Every segment has its segment MusicXML
  (`virtuoso/data/score_xml/<work>_<N>bars_Score_<segment>.musicxml`, bars renumbered from 1).
  No score-performance alignments ship with the repo. 1,110 segments contain pedal events.
- **Only 4 pieces.** Leave-piece-out on PercePiano has 4 groups. The Beethoven "pieces" in the
  file names are variations of one work (WoO 80), so one `PieceId`; the variation is in
  `Performance.meta["work"]`.
- **Performers:** 25 human performer ids (paper: 25 pianists) plus `percepiano:score` and
  `percepiano:score2` (129 segments, provenance `synthetic`). Beethoven uses 12 player numbers,
  the two Schubert works together 13 (`01` == `1`). Treating the numbering as per composer is our
  inference: it is the only reading that gives the paper's 25. Pooling raw tokens across
  composers, as PercePiano's `PIANIST_MAP` does, gives 20 human tokens (22 with Score/Score2).
  R-01's "21 performers" is presumably one of those raw-token counts; it is not the 25 pianists.
- **Provenance:** human segments are `disklavier` (the paper: Yamaha e-Competition performance
  MIDI and MAESTRO). Raters heard them rendered in Logic Pro, not the original audio.
- **Labels, per rater** (`labels/total_2rounds.csv`, 14,934 rows, 65 user ids):
  - 20 question columns; the 19 dimensions are the first 19, in the README table order (checked:
    recomputing the authors' means from these columns reproduces their JSON exactly).
    `Question_9_2_1` (mixed numbers and Korean free text) and `message` are ignored.
  - Values 8 and 9 occur. Following the authors, rows with any value > 7.1 are dropped whole
    (208 rows, leaving 63 raters; paper says 53 annotators). Blank / 0 = "I don't know",
    dropped per dimension.
  - Author renames: rated `_score` -> `_Score`; `_Score_` -> `_Score2_` for WoO 80 segments 5-16
    and D.935 segment 1. After that 1,189 segments have ratings; the 13 `_Score_` MIDI files
    those renames empty have none.
  - Verbatim duplicate rows (same user, `dataID`, values) are dropped by default, leaving 12,444
    rating submissions (paper: 12,652 annotations). A further 25,150 (segment, rater, dimension)
    cells still hold more than one rating from different submissions; `Ratings.matrix()`
    averages them.
  - Distinct raters per rated segment: min 4, median 10, max 17, mean 9.25 (paper: 5 to 12,
    mean 10.52).
- **Mean labels:** `load_percepiano_official_means()` returns the authors' JSON (1,189 segments,
  0-1 scale = mean / 7). It counts verbatim duplicates twice: our de-duplicated means differ from
  it by up to 0.070 on that scale; without de-duplication they match exactly.
- **Bar ranges** (`scripts/build_percepiano_spans.py` -> `data/processed/percepiano_spans.csv`,
  read by the loader into `Performance.span`): 337 of 1,202 segments have one.
  - WoO 80: all 238, matched against the full score in the repo (theme = bars 1-8, variation n
    = 8n+1 to 8n+8; 14 from that formula where the note match failed).
  - D.935 no.3: 99 of 117, matched against the (n)ASAP score in performance order (repeats
    taken). Approximate: a few matches overlap (segments 25/26, 42-44), and segments 46 and 50
    did not match.
  - D.960 mv2 / mv3: none. No full score is available, so the position in the movement is unknown.


- **PercePiano filename order.** Files are `<work>_<N>bars_<player>_<segment>`. The PercePiano README (line 44) gets this wrong; the authors' code and the data agree with the order here. Articulation item 2 is named `Long_Short` in the code but `Short_Long` in the README, so which end is high is undocumented.

### PianoCoRe (D-03, measured 2026-09-27, `scripts/build_pianocore_piece_counts.py`)

- **Distribution.** Zenodo 19186016 v1.0 holds `metadata.csv`, `composers.csv` and three zips
  (refined 3.58 GB, raw-midi 2.87 GB, raw-alignments 5.22 GB). HF `SyMuPe/PianoCoRe` has the same
  rows as parquet with MIDI bytes (8.6 GB). Tiers are boolean columns (`tier_b`, `tier_a`,
  `tier_a_star`), not separate downloads. We keep the Zenodo layout and read the zips in place.
- **Counts vs paper (all match the README tier table):** 250,046 rows (C), 214,092 B, 157,207 A,
  130,275 A*; 5,625 pieces (C), 1,591 with A. A covers 1,355 distinct score ids and 151 composers.
- **Pieces with many performances:** tier A: 1,227 pieces with 10+, 730 with 50+, 479 with 100+.
  Tier C: 2,616 with 10+, 1,104 with 50+, 662 with 100+. The landscape doc's "1,104 pieces have
  50+ performances" is the tier C figure, not tier A.
- **Provenance:** only 1,066 rows are not transcriptions (source ASAP, Disklavier). The rest are
  Aria-AMT (200,504 rows, Aria-MIDI), Transkun V2 (34,773, PERiScoPe), ATEPP (11,564) and
  ByteDance (2,139, GiantMIDI). No row has `performance_dataset` MAESTRO.
- **Refined alignment format.** `*_refined_align.npz` holds `perf_idx` (one entry per refined
  score note) and an `interpolated` mask. The index order is the MIDI notes sorted by (tick,
  pitch) in each file, not partitura note ids (partitura numbers score-MIDI notes by voice). The
  loader reads note order with mido and maps to partitura ids by (tick, pitch). On a
  75-performance sample across all 5 sources: 0 pitch mismatches; 8 notes in 2 files dropped by
  partitura on import (turned into deletion / insertion and counted); 22,031 of 244,660 pairs
  (9%) are `interpolated` (synthetic notes added by RAScoP; labelled `interpolated`, not
  `match`).
- **Scores** are the refined single-track score MIDI (what the alignment refers to), so measure
  maps come from MIDI time signatures. MusicXML is in raw-midi.zip (`score_xml_path`) if needed.
- **Piece ids:** 1,167 of 1,591 A pieces (3,986 of 5,625 C pieces) get canonical ids; the rest
  keep `pianocore:<composer>/<composition>/<movement>`. Only catalogue numbers in the composition
  and a bare leading "N." or "No.N" in the movement are trusted. "Nocturne No.8" under
  "Nocturnes, Op.27" is the global nocturne number, so it stays prefixed (this is why Op.9 No.2
  is prefixed in the table below). Ids that two different strings would share are demoted.
  Mapping: `data/processed/pianocore_piece_map.csv` (input for `piece_ids.parquet`).
- **Performers:** named for some sources only; unnamed rows get one id per performance
  (`pianocore:unknown/<id>`), so leave-performer-out never pools them.
- **Speed:** about 0.9 s per aligned performance on a random sample (score re-parsed each time);
  sorted by score the score cache hits and it falls to roughly 0.06-0.2 s. The full tier A pass
  took 29 min with 12 workers (see the cache section below).
- Full per-piece table: `data/processed/pianocore_piece_counts.csv` (columns `n_c`, `n_b`, `n_a`,
  `n_a_star`, `n_a_disklavier`, `n_a_performers`, `n_scores_a`).

Top 50 pieces by tier A count. "A named performers" counts distinct non-empty `performer`
values among the A rows.

| # | piece_id | Composition | Movement | A | A* | C | A Disklavier | A named performers |
|---|---|---|---|---|---|---|---|---|
| 1 | (prefixed) | Nocturnes, Op.9 | Nocturne No.2 in E flat major, Andante | 2011 | 1588 | 2439 | 0 | 46 |
| 2 | debussy_l75_mv3 | Suite bergamasque, L.75 | 3. Clair de lune | 1929 | 1778 | 2339 | 0 | 75 |
| 3 | chopin_op66 | Impromptu No.4 in C sharp minor, Op.66, "Fantaisie-Impromptu" |  | 1859 | 1304 | 2027 | 0 | 35 |
| 4 | (prefixed) | Nocturne No.20 in C sharp minor, Op.posth. |  | 1631 | 1444 | 1826 | 0 | 23 |
| 5 | beethoven_op27_no2_mv1 | Piano Sonata No.14 in C sharp minor, Op.27 No.2 ("Moonlight") | 1. Adagio sostenuto | 1514 | 1470 | 2028 | 0 | 84 |
| 6 | chopin_op23 | Ballade No.1 in G minor, Op.23 |  | 1482 | 1376 | 1755 | 18 | 77 |
| 7 | beethoven_woo59 | Für Elise, WoO 59 |  | 1373 | 1001 | 1673 | 0 | 49 |
| 8 | liszt_s541_no3 | Liebesträume, S.541 | 3. Nocturne in A flat major | 1223 | 1128 | 1408 | 0 | 30 |
| 9 | (prefixed) | 2 Arabesques | 1. Andantino con moto (E major) | 1068 | 1035 | 1209 | 0 | 21 |
| 10 | chopin_op10_no12 | 12 Études, Op.10 | No.12 in C minor "Revolutionary" | 1066 | 952 | 1172 | 13 | 57 |
| 11 | (prefixed) | Waltzes, Op.64 | Waltz No.7 in C sharp minor, Tempo giusto | 1010 | 916 | 1122 | 0 | 18 |
| 12 | beethoven_op13_mv2 | Piano Sonata No.8 in C minor, Op.13 ("Pathétique") | 2. Adagio cantabile | 998 | 668 | 1256 | 1 | 72 |
| 13 | chopin_op52 | Ballade No.4 in F minor, Op.52, B.146 |  | 957 | 881 | 1142 | 12 | 63 |
| 14 | chopin_op53 | Polonaise No.6 in A flat major, Op.53, "Heroic" |  | 879 | 680 | 1021 | 2 | 33 |
| 15 | schumann_op15_no7 | Kinderszenen, Op.15 | 7. Träumerei | 867 | 805 | 1025 | 0 | 62 |
| 16 | chopin_op10_no4 | 12 Études, Op.10 | No.4 in C sharp minor | 846 | 747 | 950 | 22 | 47 |
| 17 | liszt_s141_no3 | Grandes études de Paganini, S.141 | 3. La campanella | 846 | 659 | 953 | 29 | 12 |
| 18 | chopin_op10_no1 | 12 Études, Op.10 | No.1 in C major "Waterfall" | 838 | 816 | 933 | 25 | 48 |
| 19 | (prefixed) | Waltzes, Op.64 | Waltz No.6 in D flat major, "Minute Waltz", Molto vivace | 832 | 627 | 918 | 0 | 21 |
| 20 | (prefixed) | Waltz No.19 in A minor, Op.posth. |  | 825 | 387 | 919 | 0 | 9 |
| 21 | chopin_op28_no15 | 24 Préludes, Op.28 | No.15 in D flat major "Raindrop": Sostenuto | 813 | 739 | 968 | 0 | 79 |
| 22 | chopin_op31 | Scherzo No.2 in B flat minor, Op.31, B.111 |  | 812 | 740 | 916 | 12 | 38 |
| 23 | bach_bwv846_prelude | The Well-Tempered Clavier, Book I, BWV 846-869 | No.1 in C major, BWV 846: Prelude | 784 | 746 | 888 | 1 | 40 |
| 24 | chopin_op28_no4 | 24 Préludes, Op.28 | No.4 in E minor: Largo | 779 | 673 | 915 | 0 | 75 |
| 25 | (prefixed) | Nocturnes, Op.9 | Nocturne No.1 in B flat minor, Larghetto | 754 | 703 | 987 | 0 | 26 |
| 26 | chopin_op10_no5 | 12 Études, Op.10 | No.5 in G flat major "Black Keys" | 736 | 676 | 800 | 10 | 61 |
| 27 | chopin_op60 | Barcarolle in F sharp major, Op.60 |  | 734 | 655 | 861 | 9 | 51 |
| 28 | chopin_op47 | Ballade No.3 in A flat major, Op.47 |  | 732 | 626 | 838 | 3 | 61 |
| 29 | brahms_op118_no2 | 6 Piano Pieces, Op.118 | 2. Intermezzo in A major | 727 | 683 | 770 | 1 | 10 |
| 30 | chopin_op10_no3 | 12 Études, Op.10 | No.3 in E major "Tristesse" | 715 | 683 | 836 | 1 | 65 |
| 31 | mozart_k331_mv3 | Piano Sonata No.11 in A major, K.331 | 3. Alla Turca. Allegretto | 707 | 302 | 970 | 1 | 35 |
| 32 | (prefixed) | Nocturnes, Op.27 | Nocturne No.8 in D flat major, Lento sostenuto | 701 | 682 | 832 | 0 | 27 |
| 33 | (prefixed) | Nocturnes, Op.48 | Nocturne No.13 in C minor, Lento | 676 | 165 | 779 | 0 | 20 |
| 34 | (prefixed) | 3 Gymnopédies, IES 26 | 1. Lent et douloureux | 669 | 623 | 894 | 0 | 32 |
| 35 | chopin_op25_no11 | 12 Études, Op.25 | No.11 in A minor "Winter Wind" | 650 | 578 | 746 | 24 | 47 |
| 36 | beethoven_op13_mv3 | Piano Sonata No.8 in C minor, Op.13 ("Pathétique") | 3. Rondo. Allegro | 632 | 601 | 761 | 1 | 74 |
| 37 | schubert_d899_no3 | 4 Impromptus, Op.90, D.899 | 3. Andante | 630 | 613 | 725 | 12 | 25 |
| 38 | rachmaninoff_op3_no2 | Morceaux de Fantasie, Op.3 | 2. Prelude in C sharp minor | 630 | 600 | 689 | 0 | 16 |
| 39 | chopin_op25_no1 | 12 Études, Op.25 | No.1 in A flat major "Harp Study" | 618 | 451 | 710 | 5 | 43 |
| 40 | beethoven_op27_no2_mv3 | Piano Sonata No.14 in C sharp minor, Op.27 No.2 ("Moonlight") | 3. Presto agitato | 614 | 471 | 708 | 1 | 79 |
| 41 | schubert_d899_no2 | 4 Impromptus, Op.90, D.899 | 2. Allegro | 613 | 558 | 655 | 7 | 27 |
| 42 | beethoven_op57_mv3 | Piano Sonata No.23 in F minor, Op.57 ("Appassionata") | 3. Allegro ma non troppo - Presto | 607 | 547 | 750 | 0 | 53 |
| 43 | beethoven_op57_mv1 | Piano Sonata No.23 in F minor, Op.57 ("Appassionata") | 1. Allegro assai | 601 | 540 | 787 | 17 | 69 |
| 44 | debussy_l117_no8 | Préludes, Book 1, L.117 | 8. La fille aux cheveux de lin | 581 | 545 | 691 | 0 | 26 |
| 45 | beethoven_op53_mv1 | Piano Sonata No.21 in C major, Op.53, ("Waldstein") | 1. Allegro con brio | 554 | 499 | 663 | 27 | 50 |
| 46 | chopin_op38 | Ballade No.2 in F major, Op.38 |  | 536 | 470 | 627 | 5 | 51 |
| 47 | debussy_l61 | Rêverie, L.61 |  | 510 | 477 | 619 | 0 | 29 |
| 48 | chopin_op25_no12 | 12 Études, Op.25 | No.12 in C minor | 507 | 429 | 581 | 9 | 44 |
| 49 | liszt_s172_no3 | Consolations, S.172 | 3. Lento, quasi recitativo (E major) | 506 | 494 | 571 | 0 | 15 |
| 50 | mozart_k545_mv1 | Piano Sonata No.16 in C major, K.545 "Sonata facile" | 1. Allegro | 496 | 450 | 565 | 0 | 13 |

### PianoCoRe tier A cache (D-07, built 2026-09-27, `scripts/build_pianocore_cache.py`)

- **Path:** `data/processed/pianocore_A/` (derived, gitignored, 4.1 GB). Reader:
  `pianolens.data.pianocore_cache` (`load_piece_notes(piece_id, columns=, labels=)`,
  `load_performances`, `load_pieces`). Layout and column meanings are in that module's docstring.
  - `notes/<slug>.parquet`: one file per piece (1,591), zstd. One row per alignment pair:
    ids (`performance_id`, `piece_id`, `performer_id`, `provenance`, `label`), score fields
    `s_id s_onset_beat s_duration_beat s_onset_quarter s_duration_quarter s_pitch s_voice s_staff
    s_is_grace s_ts_beats s_ts_beat_type s_measure`, performance fields `p_id p_onset_sec
    p_duration_sec p_pitch p_velocity`. Missing side: NaN / -1 / "". Durations are key-down.
    No pedal events (use the loader).
  - `performances.parquet` (157,207 rows: source, capture model, split, `tier_a_star`, quality
    label, label counts, pitch-mismatch flag), `pieces.parquet`, `failures.parquet`, `build.log`.
- **Build:** 12 spawn workers, one piece per task, largest pieces first. Resumable: a piece is
  skipped when `_state/<slug>.json` exists; each file is written under a temp name and renamed.
  Wall time 29.0 min for 157,207 performances, with another agent's 12-worker alignment job
  running on the same machine. About 0.9 GB RSS per worker (~11 GB total).
- **Counts:** 157,207/157,207 performances loaded, **0 failures**; 377,786,620 rows:
  344,030,350 `match`, 33,726,317 `interpolated` (8.9%), 29,953 `deletion`, 0 `insertion`.
  All 29,953 deletions come from score notes partitura drops on import (7,157 performances
  affected). 9 performances have at least one aligned pair whose pitches disagree (flag
  `pitch_mismatch`). Provenance: 156,229 transcribed, 978 Disklavier (the ASAP rows in tier A);
  130,275 rows are also A*.
- **Load time** (measured right after the build, so the files were probably in the OS page
  cache): `chopin_op10_no3` (715 performances, 1.34 M rows) 0.02 s for all columns; the Op.9 No.2
  nocturne (2,011 performances, 2.50 M rows) 0.03 s; `debussy_l75_mv3` (1,929 performances,
  2.89 M rows, 216 MB in pandas) 0.03 s. Loading from the MIDI zips with the loader would take
  minutes per piece.

### Cross-dataset piece ids (D-07, `scripts/build_piece_ids.py`)

- `data/processed/piece_ids.parquet`: one row per (dataset, source_key) with the loader's
  `piece_id`, `canonical`, composer / title / movement and performance counts (PianoCoRe:
  `n_performances` = tier C rows, `n_tier_a` = tier A rows). Reader:
  `pianolens.data.piece_ids.load_piece_id_table`, `datasets_by_piece`. Build it after
  `scripts/build_pianocore_piece_counts.py`.
- 6,852 rows. Canonical piece ids: ASAP 201 of 221, PianoCoRe 3,986 of 5,625, PercePiano 4 of 4,
  MAJEPPA 653 of 884 (655 of 886 scores), Vienna 4 of 4, Batik 36 of 36, MazurkaBL 46 of 46,
  DCML J. C. Bach 29 of 29 (D-12, `jcbach_op5_no1_mv1` style; 0 in PianoCoRe, which has only
  J. C. Bach's March W.A 22). 4,308 canonical ids overall; 515 occur in 2+ datasets.
- Also in PianoCoRe (canonical): ASAP 197 of 201 (missing: `beethoven_op110_mv3to4`,
  `liszt_s145_no1/no2`, `liszt_s244_no6`), PercePiano 4/4, MAJEPPA 376/653, Vienna 3/4 (not
  `schubert_d783_no15`), Batik 33/36 (not K.533), MazurkaBL 38/46 (PianoCoRe lists some mazurka
  sets as a whole opus).
- MAESTRO, PSyllabus, Expert-Novice and NeuroPiano are not in the table (free-text or local ids).
- `make_piece_id` folds accents with NFKD (D-07). Recomputing every id for ASAP, PianoCoRe
  (5,625 keys), MazurkaBL, Batik, Vienna and PercePiano before and after the change: 0 ids changed.
- **MAJEPPA ids changed (D-07):** they were all `majeppa:<score_id>`; now a score whose title has
  an unambiguous catalogue number (and movement where needed) gets a canonical id
  (`majeppa.majeppa_piece_id`). Titles such as "Sonatina Op 36 No 1 Allegro" (movement not
  numbered) stay prefixed.

### D-04 / D-05 small sets (measured 2026-09-27; download: `scripts/download_labeled_sets.sh`)

- **Expert-Novice:** counts match the paper (83 recordings, 7 pieces, 803 ratings: 332
  instructor, 471 novice). Audio only; 21 players (by recording: 8 self-rated beginner, 30
  intermediate, 45 advanced). Novice rater ids run 1-21, the same range as `Player_id`; the
  files do not say whether raters are the players. The zips contain `__MACOSX` folders (ignored).
- **NeuroPiano:** 2,265 rows on disk vs 2,255 on the card. 104 recordings, 39 students, 35
  raters, 13 questions (q1-q2 good / bad points, q3-q13 specific aspects), scores 0-6 (64 zeros).
  Audio is WAV inside the parquet. Some (recording, rater, question) triples appear twice.
- **Vienna 4x22:** provenance tagged `sensor` (Boesendorfer SE), not `disklavier`. 88 match
  files: 43,472 matches, 418 deletions, 184 insertions. `midi/*-average.mid` are averages, skipped.
- **Batik-plays-Mozart:** provenance `sensor`. 36 match files: 98,317 matches, 4,104 insertions,
  208 deletions. Per-note annotation CSVs use the match score ids (`n15-1`).
  D-11: `musicxml_score=True` unfolds `scores_edited/<stem>.musicxml` to the pianist's repeat
  path: every match id resolves in all 36 movements (id Jaccard 1.0 in 35; kv281_3 0.9996, one
  extra MusicXML note `n636-1`). Beats agree with the match score except 9 notes of one fast
  run in kv331_1 (+0.25 quarter). The MusicXML has dynamics and tempo words but no slurs.
  kv284_3 takes about 95 s to unfold. DCML labels: 1,068 phrase starts, 1,068 ends, 1,144
  cadence rows, all mapped.
- **MazurkaBL:** 46 mazurkas with beat data but 44 MusicXML scores (landscape says 44
  mazurkas); 2,098 recordings; 134 performer ids, 10 without a name in `pianistID_name.csv`.
  Recording ids can carry a letter (`pid9070b-01`). Beat times are annotations of commercial
  audio, not MIDI, so no provenance value applies (`BeatCurve.provenance` is None). `beat` is
  MazurkaBL's 0-based `beat_number` (a pickup can start at beat 2); loudness unit `sone_norm`.
- **MAESTRO v3 MIDI:** no performer names, so performer ids are per performance. Piece ids are
  prefixed (free-text titles, not parsed).
- **PSyllabus:** open substitute for CIPI. The MIDI is transcribed from YouTube recordings; the
  difficulty label is a piece property, kept in `Performance.meta`.
- **MAJEPPA (D-05):** released on HF (not linked from the arXiv HTML; found via github
  kkwsts/majeppa). The card counts 4,449 performances; the paper abstract says 3,979. The
  alignment is a DTW path in seconds, not note-level. Performer ids use `recording_id` (one source
  video). Some score MIDIs crash partitura `load_score_midi` (time-signature assertion in
  `add_measures`); those performances are yielded with `score=None`.
- **PianoJudges:** the repo's `data_collection/index.json` + `splits.json` are the CIPI label
  index (652 works: Henle 1-9; fold 0: 389 train / 131 val / 132 test). Expertise data is only
  YouTube channel lists (73 lines, 70 commented out) and technique URL lists.
- **SKY-Piano (D-09, 2026-09-27):** not downloadable and license unclear, so nothing is on disk.
  The project page says "the full dataset is distributed through this project page", but it has no
  download link; the "GitHub" link points at github joonhyungbae/skypiano, which returns 404 (the
  author's public repos do not include it). The explorer manifest
  (`/skypiano/explorer/Data/manifest.json`, generated 2026-04-25) lists only 5 sample trials,
  all professional graded pieces (Clementi Op.36 No.1, Bach BWV Anh.114, Schubert Op.90 No.4,
  Chopin Op.28 No.4, Mozart K.545). None is a scale and none is an amateur, so the samples cannot
  support the expert vs amateur check. License: the CC BY 4.0 in the paper covers the paper
  text (ISMIR template); the data is under "per-modality license terms reflecting [the] consent
  structure", which are not stated anywhere we could find. See BACKLOG BL-11.
- **Gated (OWNER):** CIPI scores (Zenodo access request) and MAESTRO-E (Globus login). See
  BACKLOG BL-04, BL-05.

### D-10 additions (data-engineer, 2026-09-27; spec `docs/specs/skill-control-check.md`)

- **MAJEPPA transcriber is Transkun** (paper, arXiv 2608.11026: "transcribed into MIDI using
  Transkun ... we did not explicitly check transcription quality (including pedal
  artefacts)").
- **MAJEPPA score MIDIs lack staff and hold playback durations.** 829 of 886 have exactly two
  note tracks (right / left hand). Durations are shortened by one tick (0.4979 quarter for an
  eighth) or to about 95% (0.4729). `majeppa.prepare_aligned` (after `align_performance`) sets
  staff 1/2 from the tracks and extends near-legato notes to the next onset in their stream
  (gap at most 7% of the IOI). 17 of the 309 D-10 scores are unquantized (more than 10% of
  onsets off a 1/48-quarter grid), e.g. S_0194 Kreisleriana I.
- **`score_coverage >= 0.85` does not guarantee a usable clip.** Some clips hold several times
  the score's notes (S_0194: 13,905 performed notes against 1,796 score notes), and 28% of
  the 1,604 D-10 performances align with match ratio below 0.8 (suspect). The suspect share is
  highest for adult beginners (36%) and lowest for child professionals (18%).
- **Recording context tracks level:** all 156 virtuoso clips are `concert_performance`; piano
  teachers are mostly `demo_class` / `slow_demo`; adult beginners are mostly `practice` /
  `sight_read`.
- **PianoCoRe has 68 same-performance Disklavier/transcription pairs** (`is_duplicate` with an
  ASAP `lead_performance`, or the reverse): 62 Aria-AMT, 6 Transkun V2. PianoCoRe's copies of
  the ASAP MIDI files are trimmed by a few notes (not byte-identical). 66 matched to
  `data/raw/asap` by name + note count + length. Other duplicates (about 34,000) are the same
  YouTube audio transcribed by two models (e.g. Aria-AMT vs GiantMIDI ByteDance): usable for
  transcriber-vs-transcriber disagreement if ever needed.
- **PianoVAM** license is CC BY-NC-SA 4.0 (the ticket said CC BY-NC). No scores. Only Satie
  Gymnopedie No. 1 is played at more than one level (titles "No.1" and "no.1", slugged to one
  id): 1 recording per level.
- **PianoVAM audio (A-01b)** is a dedicated microphone on the Disklavier in a practice room
  (paper: "a dedicated microphone and a Disklavier piano provided the audio and MIDI"; mic model
  and placement not stated), down-mixed to mono, and aligned to the MIDI by the authors (global
  offset + DTW). Measured offset after that is a few ms (see `docs/specs/phone-audio-baseline.md`,
  A-01b). The audio is on this Mac by the lead's A-01b ticket (subset budget about 5 GB), an
  exception to `rules/audio.md`; bulk audio work still belongs on the GPU box.
- **Rach3** file names end in `mi` before `.mid` (the README's 25-character description omits
  it). The commit fetched is recorded in `data/raw/rach3/COMMIT`.
- **Rach3 Hanon takes (BL-16).** The book MusicXML is one part. Part I exercises restart the
  printed measure number at 1 and end with a repeat barline and a one-chord bar. Part II (from
  0-based measure 583) has no separators. Hand asynchrony differs by player: p3 plays the hands up
  to about 50 ms apart, so a fixed 40 ms chord threshold splits p3's events. The build picks 40, 60
  or 80 ms per session. Most QC failures are pauses (often at the bar-14 turnaround). p1 files are
  usually one take each. Only 44% of p1's session notes fall in Part I takes.

### DCML J. C. Bach sonatas (D-12, data-engineer, 2026-09-28; QA: `scripts/check_dcml_jc_bach.py`)

- **Why it is here:** R-08c, the unfamiliar-repertoire test of LLM phrase analysis (DECISIONS
  2026-09-28, R-08b). Chosen from the R-08b survey of DCML phrase-labelled corpora.
- **Label-free score path.** No MuseScore binary on this Mac and no MusicXML in the repo, so
  `load_score` builds a partitura `Part` from the ms3 TSV facets `notes/`, `measures/` and
  `chords/` only. These have no label columns; the labels live only in `harmonies/` and the
  `.mscx`. `Score.meta["source_files"]` lists what was read. Leakage: the R-08a renderer run on
  all 29 unfolded scores contains no DCML label string (length >= 3), none of R-08a's banned words
  and no Roman-numeral token (`LEAKAGE CHECK PASSED`); a planted label is caught (test).
- **Not in the three facets:** fermatas (15 `<Fermata>` elements in the `.mscx`, in 8 movements), hairpins, printed
  rests (derived as the gaps in each staff), key mode (`KeySignature(mode=None)`; Batik's
  MusicXML has no `<mode>` either, so the F-05c detector reads mode 1 for minor keys in both).
  Tempo words: only the movement title from `metadata.tsv` (e.g. "Allegretto"), put at the first
  onset (the renderings name no composer, opus or catalogue number; checked). Staff texts kept: "Var. 1-5", "Segue", "Min. D.C.",
  "Da Capo il Maggiore", "L" / "R" and a few more.
- **Unfolding** follows the `next` column (first visit takes the first target). It gives the
  metadata's `last_mc_unfolded` and `length_qb_unfolded` in 29/29. No voltas in this corpus.
  Da capo is not unfolded (ms3 does not either).
- `duration_qb` in `notes/` is a rounded float (e.g. 0.333333); use the exact `duration`
  (whole-note fraction) x 4. partitura's `quarter_map` puts the first full bar at 0 (anacrusis
  offset), so labels are mapped via divs, not `inv_quarter_map` (a first version that went
  through `inv_quarter_map` put labels of anacrusis movements off their onsets, 26 of them in
  op. 17/2 iii, one eighth late; caught by the off-onset count).
- **Labels:** `phraseend` values `{`, `}`, `}{` and 3 rows of `\\` (op. 5/1 i: 1, op. 5/4 i: 2;
  not a start or end; dropped, counted in `n_other`). Cadences: PAC, IAC, HC, EC, DC and PC
  (plagal, 9 unfolded; Batik has none). Unfolded distinct beats: 832 phrase ends, 763 cadences
  (PAC 342, IAC 77, HC 235, EC 55, DC 45, PC 9). All labels sit on a note onset except 1 phrase
  start in op. 5/5 ii (bar 40, beat 119.667).
- **F-05c detector runs** (shipped Batik-fitted defaults, unchanged). Mean end F1 at +-1 beat over
  the 29 unfolded movements: detector 0.427, proxy last onset 0.235, 4-bar grid 0.273
  (`data/interim/dcml_jc_bach/comparators.csv`, `summary.txt`). Detector recall by type at
  +-1 beat, pooled: PAC 212/342, IAC 24/77, HC 55/235, EC 14/55, DC 10/45, PC 0/9.
  `cands.pkl` has the same layout as `data/interim/phrase_f05c/cands.pkl`, for R-08a's scorer.
- `piece_id`: `jcbach_op<k>_no<n>_mv<m>` (movement = the letter after the sonata number).
- **Pilot-size movements** (unfolded bars within R-08a's 110-344 and rendering <= 88k chars;
  `pieces.csv` column `pilot_size_ok`), by R-08a stratum:
  - first movement 4/4: op. 5/3, 5/5, 17/4, 17/5, 5/2, 17/3, 5/4, 17/6 i (8);
  - first movement, other metre: op. 5/1 i (2/4), 17/2 i (2/4) (2);
  - middle: op. 5/5 ii Adagio (3/4, 110 bars), 17/6 ii Andante (4/4, 148) (2). Near misses:
    5/2 ii (104 bars, 18k chars); 5/6 ii and 17/2 ii are 71-77 long bars (30-34k chars);
  - finale duple: op. 5/3 ii, 17/2 iii (12/8), 5/5 iii, 17/6 iii (12/8) (4);
  - finale triple: op. 5/4 ii, 5/1 ii, 17/4 ii (3/8), 17/3 ii (3/8), 17/5 ii (3/8) (5);
  - excluded like R-08a's variation sets: op. 17/1 (minuet with variations); also the short
    minuet-trio pair ending op. 5/2.
  - **Familiarity caveat:** the README says op. 5 nos. 2-4 are the sonatas Mozart arranged as
    his K.107 concertos, so those are the likeliest to be recognised.

### DCML Romantic corpora (D-13, data-engineer, 2026-09-28; QA: `scripts/check_dcml_romantic.py`)

- **Why they are here:** R-08d, the Romantic-repertoire test of LLM phrase analysis (DECISIONS
  2026-09-28, R-08d design; landscape section 2.1). Pool: `chopin_mazurkas`,
  `grieg_lyric_pieces`, `tchaikovsky_seasons`, `schumann_kinderszenen`, `liszt_pelerinage`.
  Labels predate the model cutoff (all released 2025-04-27), so exposure is not excluded.
- **Loader:** the J. C. Bach loader is generalised into `pianolens.data.dcml` (corpus as the
  first argument; `CORPORA`, `ROMANTIC`); `dcml_jc_bach` is now a thin wrapper and its outputs
  are unchanged (R-08a rendering, notes, phrase tables and meta hashed for all 29 movements x
  unfold x tempo word: identical before and after). Same label-free path: `notes/`,
  `measures/`, `chords/` only.
- **What the Romantic path adds or changes** (J. C. Bach unaffected):
  - hairpins and crescendo / diminuendo lines (spanner columns of `chords/`) become partitura
    loudness directions; text lines and text hairpins (`TextLine_stringendo`,
    `HairPin:2_poco a poco cresc.`) become words; system text is read;
  - tempo comes from the `Tempo` events (tempo words and metronome marks, spelled
    `quarter=144`), **not** from the movement title, which names the piece ("Träumerei",
    "Gondoliera"). Titles are in `Score.meta["title"]` only. Liszt stems contain titles, so
    blind ids are needed downstream;
  - text markup (`<font .../>`, `<i>`) and private-use glyphs are stripped; texts with no
    letter or digit (a lone natural sign) are dropped;
  - two spellings are normalised because R-08a's leakage check reads them as labels:
    "Tempo I" / "Temp. I." -> "Tempo primo" (Roman numeral), Liszt's "una chorda" / "tres
    chorde" -> "una corda" / "tres corde" ("chord"). This was found by the leakage check
    (Grieg op. 68/6, Liszt 161.07) and is the only text rewriting;
  - not read: fermatas, slurs, pedal marks, ottava lines (pitches are already sounding: ms3's
    `octave` / `midi` agree with the spelling for every note), `lyrics_1` (Chopin: brackets and
    hairpin glyphs; Grieg: two dynamics).
- **Ties:** ms3 exports some tie continuations that start after a gap or on the other staff.
  They are merged if they start within 4 quarters of the head's end (`meta["n_gap_ties"]`:
  Chopin 6, Grieg 14, Tchaikovsky 6, Schumann 4, Liszt 14). Left as separate notes (orphan tie
  heads, so notes exceed `n_onsets`): Kinderszenen no. 7 (3, grace notes coded as tie
  continuations), Liszt 160.02 (1, same), 161.04 (1) and 161.07 Dante (2).
- **Unfolding** follows `next` and equals `metadata.tsv` for 162 of 166 movements. The four
  others are Chopin mazurkas where ms3 itself gets it wrong or gives up, hand-checked:
  - B.16/2 and B.73: ms3 ends the piece at the *Fine* before the D.C. / D.S. is played
    (metadata 24 and 12 bars); the loader plays on and stops at the Fine after the jump (64 and
    62 bars);
  - op. 7/5 (D.S. *senza fine*, metadata empty): the segno section is played once more (36);
  - op. 17/3 (D.S. al Fine, the Fine in the first ending, metadata empty): after the jump the
    first ending is taken and the piece ends there (174).
  - `Score.meta["unfold_validated"]` is False for these four.
- **Labels:** only `{`, `}`, `}{` (no deprecated `\\`). Cadences PAC, IAC, HC, EC, DC, PC.
  Unfolded distinct beats over the 165 labelled movements: PAC 634, IAC 295, HC 431, EC 12,
  DC 6, PC 50. All labels map to the playthrough (0 unmapped); 33 unfolded placements are not
  on a note onset (on a rest or a tied-over note; kept at their exact beat).
- **Leakage:** R-08a's `common.render` on all 165 labelled unfolded movements contains no DCML
  label string (length >= 3, incl. `alt_label` and `special`), none of R-08a's banned words and
  no Roman-numeral token (`LEAKAGE CHECK PASSED`); a planted label is caught for every corpus
  (tests). Identity report (capitalised title words or the composer in the rendering, not a
  failure): only "Valse" in Grieg op. 68/6 ("Tempo di Valse tranquillo", a printed tempo mark).
- **Eligibility for R-08d** (`pieces.csv`): `eligible` = labelled and >= 5 folded phrase ends;
  `simple_meter` = every time signature has numerator 2, 3 or 4; `meter_changes` flags changes.
  - Chopin 52 eligible, all simple (excluded: op. 68/4, op. 6/4, op. 7/5; op. 30/1 unlabelled);
  - Grieg 53 eligible, 45 simple (op. 43/2, 47/2, 47/3, 54/1, 54/2, 65/4 in 6/8; 57/3 in
    6/8 and 9/8; 54/4 mixed 9/8-6/8-3/8);
  - Tchaikovsky 12 eligible, 9 simple (April, August in 6/8; May 9/8-2/4);
  - Schumann 10 eligible, all simple (excluded: nos. 1, 5, 9 with 3-4 ends);
  - Liszt 19 eligible, 8 simple (compound or mixed: 160.03 Pastorale, 160.04 Au bord d'une
    source, 160.08 Le mal du pays, 160.09 Les cloches de Genève, 161.01 Sposalizio, the three
    sonetti 161.04-06, 161.07 Dante, 162.01 Gondoliera, 162.03 Tarantella).
  - Rendered size of the eligible simple-meter movements, median (range) in characters: Chopin
    19,011 (9,424-50,164), Grieg 19,212 (9,619-70,199), Tchaikovsky 34,134 (15,842-42,660),
    Schumann 10,033 (6,905-13,543), Liszt 42,672 (14,729-121,773). Dante renders to 215,692.
- **F-05c detector** (shipped Batik-fitted defaults, unchanged), mean end F1 at +-1 beat over
  the eligible movements (unfolded): detector / proxy last onset / 4-bar grid: Chopin 0.341 /
  0.241 / 0.185; Grieg 0.307 / 0.225 / 0.208; Tchaikovsky 0.181 / 0.207 / 0.171; Schumann
  0.420 / 0.433 / 0.359; Liszt 0.227 / 0.179 / 0.112 (J. C. Bach, D-12: 0.427). Pooled
  detector recall by type at +-1 beat: PAC 285/634, IAC 96/295, HC 86/431, EC 0/12, DC 1/6,
  PC 7/50. Per movement: `comparators.csv`; `cands.pkl` (key `score_id`) has the F-05c layout.
- `piece_id`: `chopin_op<k>_no<n>` (opus numbers as the corpus gives them, Sapp's numbering,
  e.g. op. 41/1 = C# minor), `chopin_b<n>[_no<k>]` for the 7 mazurkas without opus (Brown
  number from the file name), `grieg_op<k>_no<n>`, `tchaikovsky_op37a_no<n>`,
  `schumann_op15_no<n>`, `liszt_s16<k>_no<n>`. In `piece_ids.parquet`: all 46 MazurkaBL
  mazurkas share an id with DCML (45 labelled; op. 30/1 has no labels). PianoCoRe tier A ids:
  Chopin 33, Grieg 12, Tchaikovsky 10, Schumann 4, Liszt 2; ASAP: Gondoliera; MAJEPPA: 12
  Kinderszenen pieces.

### mistakes_v1 (D-08, feature-engineer, 2026-09-27)

- Mistake model: `src/pianolens/data/perturb.py` docstring (MAESTRO-E generator read and compared;
  differences listed there). Rebuild: `uv run python scripts/build_mistake_set.py`.
- Keys are `<performance_id>#r<rate>-s<seed>`; seed = 1000 x performance index + rate index.
- Natural mistakes: the (n)ASAP ground truth already has insertions and deletions (on the rate-0
  copies: 51.7 insertions and 40.5 deletions per 1,000 performed notes). They are kept with
  `injected=False`. Some are real slips, some are ground-truth noise. Evaluations treat them as
  "don't care".
- Only single-path scores are used, so the ground-truth score ids equal the ids that
  `align_performance` produces and measure rows are unique. Performances with repeats are not in v1.
- Balakirev (Islamey) is absent: every performance has more than 6,000 notes.


- **PERiScoPe v1.0 metadata** (lead, 2026-09-28): `experiments/2026-09-28-R-07-symupe-finetune/artifacts/`, a 13 MB CSV
  from HF `SyMuPe/PERiScoPe` dataset commit 5a637bd9. License as PERiScoPe (CC BY-NC-SA 4.0).
  Used to determine which pieces SyMuPe saw score-paired (the R-07 / R-10 split).
