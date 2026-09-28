# F-07 / H5 audit facts (2026-09-28)

- Prereg: `head -98 README.md` sha b1f57ae2...40ae. It equals the feature-engineer `cat > README.md`
  heredoc (Bash, not Write) in subagents/agent-a5dbb818429903ca6.jsonl at 04:08:20Z. To extract it,
  awk the heredoc body out of `.input.command`. Commit e4becf8 (00:13 local) postdates the results,
  so it is not evidence of order.
- Rerun recipe: copy `groups.jsonl`, `asap_groups.jsonl` and `meta.json` into scratch/artifacts,
  copy analyze.py beside them, and run it (ART is relative to __file__). Byte-identical, 6 s.
  Never run the in-repo analyze.py: it overwrites the artifacts csvs.
- run.py resumes from groups.jsonl (skips done keys), so a killed run leaves its rows in the next run.
- KEY FINDING: the pairwise half-sum/half-diff test passes for cross-pianist pairs too. Timing delta
  0.097 [0.085, 0.109]; R²(sum) 0.146 cross vs 0.132 same. The half-diff has no shared component, so
  delta is about R²(sum) whenever per-take R² > 0, and "falsified" is nearly unreachable. What is
  informative: R²(diff) same 0.011 vs cross 0.049. Script and data: experiments/.../artifacts/audit/
  (cross.py, cross.jsonl; about 5 min at 6 workers, 411 pieces). Pick cross takes on the same
  refined_score_midi_path: 345 pieces have 2 refined scores.
- Duplicates: 93/1,390 eligible groups keep a pair with timing r > 0.92 (the ASAP max). Dropping
  them gives 0.116. A duplicate deflates delta (the half-sum is then a noisy single take).
- ASAP basis = MusicXML with markings, while PianoCoRe = MIDI without. The Disklavier comparison is
  not like-for-like on the basis either.
- General rule candidate: any "shared part vs difference part" contrast needs a cross-unit
  (cross-performer) positive control. Candidate for the rules file if it recurs.
