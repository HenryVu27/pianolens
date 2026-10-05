# BL-17 Romantic LLM phrase test (run 2026-09-29; audited: Confirmed with caveats)

Folder `experiments/2026-09-29-BL-17-romantic-llm/`, prereg sha256 c3803f83...2462. 24 simple +
6 compound DCML movements (ids P01..P30, map in `artifacts/selection.json`), R-08d's 5 excluded.
Result: simple mean 0.635 t [0.549, 0.720] -> INCONCLUSIVE; detector 0.307; +-1 bar 0.702;
compound 0.654; disguise effect (U, n 8) +0.032 t [-0.082, +0.147].

## Reuse
- `build.py` = R-08d `load/hits/text_hits` + R-08b `disguised` context manager (importlib), plus
  a k fallback for triple accidentals (never needed). Disguise check compares against the same
  code with s=k=c=0 (markings dropped too), not the undisguised rendering (pointer bars differ).
- `score.py` imports R-08d score.py as D (D.S = R-08a scoring); pointers via R-08b
  `parse_pointers` (handles "same notes as" and "same notes and markings as").
- `power.py`: reachability sim (normal + empirical-15 from R-08a/c/d artifacts).
- `artifacts/audit_transcripts.py`: transcript check by agent id; flags "cat >" heredoc writes
  and `cd <own>` (false positives); the real test is absolute paths outside the own folder.

## Running annotators myself (ml-researcher can launch them)
- Concurrency limit 20 subagents per session (other agents count): launch in batches; "limit
  reached" errors are harmless, relaunch after completions. 68 annotators took about 35 min.
- One folder per annotator (3 files + out/), prompt = R-08d template minus "five movements"
  sentence plus "read it to the END line". 15/68 needed 2-4 Reads; all reached END.
- Transcripts: ~/.claude/projects/-Users-vuducdung-personal/<session>/subagents/agent-<id>.jsonl.

## Audit outcome (2026-09-29) and post-audit text fixes (applied by me, same day)
- Verdict INCONCLUSIVE stands; all numbers reproduced. Text fixes applied in place plus a
  "## Post-audit corrections" section; prereg hash rechecked after (python slice of raw bytes up
  to b'## Preparation record'), still c3803f83...2462. EXPERIMENTS R-08d row now says its GO is
  not confirmed by BL-17.
- What I overclaimed and must not repeat: (1) explaining a replication gap before testing it
  (Welch R-08d - BL-17 +0.103 [-0.189, +0.394], p 0.41; corpus-equal BL-17 0.687); (2) "recall is
  high" / "placement, not missed phrases" (88/314 misses per run, only 21-26 within 1 bar;
  158-188 extras); (3) P19 1-bar pattern generalised from run A (7/9) to both (B 4/8); (4) +-1 bar
  as a route to the bar (interval also contains 0.70; grid4 0.171 -> 0.405); (5) run record
  omitted the 14 concurrency-refused Agent calls and the env-block working-directory disclosure.
- The lead handles DF-02 disclosure in the report (feature-engineer), not me.

## Findings worth remembering
- Arrival-placement convention drives some +-1 beat misses (bass arrival under appoggiatura vs
  resolution: P19 run A, 7/9 misses 1 bar off). Overall only a quarter to a third of misses are
  within 1 bar. Instructions give no rule for split arrivals.
- Level mismatch both ways (DCML finer on Chopin BI85, 2-bar units; LLM finer on P11/P28).
- Disguised bar offsets make annotators think the file is an excerpt ("starts mid-movement").
- Style recognition: "Chopin" guessed in 2 strings + 5 hand-backs, only on Chopin movements.
