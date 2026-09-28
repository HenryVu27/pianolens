# R-08b memorisation control (preparation 2026-09-28)

Folder `experiments/2026-09-28-R-08b-llm-memorisation-control/`. Pre-registered (hash in README
Preparation record). Condition A = `blind_input_disguised/D1..D5.txt`; condition B = R-08a's
`blind_input/` unchanged, 2 reruns (B1, B2). D<->M map, semitones, fifths shift, bar offset only
in `artifacts/disguise.json` (seed 20260929).

## How the disguise works (reuse, don't rewrite)
- `disguise.py` imports R-08a `common.py` and swaps four module attributes inside a context
  manager (`bar_table` +c bars/+k fifths, `_spelling` transposed, `_events` markings dropped,
  `LEGEND`). `common.render` resolves them as globals, so layout is byte-for-byte R-08a code.
- Respelling on the line of fifths: f = base(step) + 7*alter; shift by k with 7k = s (mod 12);
  octave from midi + s. `choose_k` minimises max |key fifths|.
- R-08a `score.py` is loaded with importlib under another name (`r08a_score`): a plain
  `import score` from R-08b's own score.py would import itself.
- Removing dynamics merged no pointer bars (pointer maps identical to R-08a, shifted by c), so
  R-08a annotations replay exactly through the A path (harness check 3).

## Traps
- Hash of "README up to ## Preparation record": compute it AFTER appending (the append adds a
  blank line to the slice). First recorded value was wrong, fixed.
- The k rule can give 7 sharps (kv330_2 down a major third: F major / F minor sections).
  Double accidentals: D4 4.0%, D5 2.2% of note tokens; R-08a had none. Disclosed, not redrawn.

## DCMLab corpora with phrase labels (checked 2026-09-28, main branch, .zenodo.json licenses)
jc_bach_sonatas 29 pieces / 442 phrase ends (best unfamiliar candidate); wf_bach_sonatas 9/167;
cpe_bach_keyboard 66/968; scarlatti_sonatas 69/999; handel_keyboard 6/28; pleyel_quartets 6/128
(strings). kozeluh_sonatas 49 pieces but 0 phrase / cadence labels. All CC BY-NC-SA 4.0.
Score-only (MuseScore + TSV); the .mscx files embed the labels, as the Batik MusicXML does.

## Next
Lead runs 15 annotators; save to annotations_A/, annotations_B1/, annotations_B2/; score;
fill recognition.json; `score.py --compare` -> artifacts/r08b_summary.txt; append Results.
