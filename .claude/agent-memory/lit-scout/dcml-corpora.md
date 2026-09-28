# DCML corpora: how to survey phrase labels (R-08b, R-08d; 2026-09-28)

- Enumerate: `gh api --paginate 'orgs/DCMLab/repos?per_page=100'` (127 repos). `pushed_at` covers
  all branches, so it is a quick "anything new since X?" check.
- Labels: `harmonies/*.tsv`, column `phraseend`. Current standard `{` start, `}` end, `}{` both.
  **Deprecated `\\`** = old-style phrase ending with no starts (winterreise, liederkreis,
  mendelssohn_quartets, ravel, wagner): those corpora also lack cadence labels.
- Version/license: `.zenodo.json` (GitHub API says NOASSERTION); all CC BY-NC-SA 4.0.
- Romantic piano with `}` ends (all v2.3-v3.2, 2025-04-27): chopin_mazurkas 55/606,
  grieg_lyric_pieces 66/559, tchaikovsky_seasons 12/298, medtner_tales 19/287, liszt_pelerinage
  19/277, dvorak_silhouettes 12/169, schumann_kinderszenen 13/87, rachmaninoff_piano 22/80,
  debussy_suite_bergamasque 4/25; beethoven_piano_sonatas 64/1387. None post-cutoff.
- No DCML Schubert piano, no Lieder ohne Worte. Meta-repos: romantic_piano_corpus,
  distant_listening_corpus (submodules only).
- Overlap: PianoCoRe tier A has 33 DCML mazurkas; MazurkaBL covers 45 of DCML's 55 (not op30-1).
- Scan scripts lived in the session scratchpad (scan.sh / count.py); easy to rewrite.
