# PercePiano quirks (checked 2026-09-27)

- Filename order: the README says `<work>_<N>bars_<segment>_<player>`, but it is WRONG.
  - The code (`get_performer_id` = token[-2] in `virtuoso/.../m2pf_dataset_compositionfold.py`)
    and the data say `<work>_<N>bars_<player>_<segment>`.
  - Proof: every Beethoven variation has 14 distinct token[-2] values, matching
    BEETHOVEN_PERFORMER_IDS plus 'Score', and exactly 1 token[-1] value.
  - CrescendAI fell into this trap (see crescendai.md).
- Label file `label_2round_mean_reg_19_with0_rm_highstd0.json`: 1,202 keys, 20 values each.
  The first 19 are dims; the 20th is a player id.
- 4 works (D960 mv2, D960 mv3, D935 no.3, Beethoven WoO80; each WoO80 variation is its own
  prefix), 99 passages (work, bars, segment), 25 pianists plus Score.
- Variance shares of the 19 mean labels (in-sample group means; my scratch script):
  - passage mean over dims 0.41 (timing 0.22 ... brightness 0.76, valence 0.77);
  - work 0.12; performer 0.23.
  - The MuQ-minus-symbolic advantage (CrescendAI A4) does NOT track passage share
    (Spearman -0.05).
- PercePiano's composition split = leave-passage-out, with a 15% held-out test set (random.seed(42)).
- Raters heard Logic Pro "Yamaha Grand Piano" renders (Sci. Rep. paper). The dataset licence is
  CC BY-NC-ND 4.0; the repo code is MIT.
