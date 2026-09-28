# R-08a LLM phrase pilot audit facts (2026-09-28)

- Blinding audit recipe: subagent transcripts are symlinked from
  `<scratchpad>/../tasks/<agentid>.output` to `~/.claude/projects/<proj>/<session>/subagents/agent-<id>.jsonl`.
  List every tool call with
  `jq -c 'select(.type=="assistant")|.message.content[]?|select(.type=="tool_use")|{name,input}'`.
  Check the `instructions` attachment to see which CLAUDE.md files the agent got. Here only the
  user's global one was loaded; the project CLAUDE.md was not. The env block still shows the cwd
  (project name). A grep for "pianolens" hits mostly the `cwd` fields; strip them with `del(.cwd)`.
- For Write-tool outputs, compare the transcript's `input.content` with the file on disk
  (`jq -S`). Bash heredoc writes: grep the command for `open(`, `glob` and `cat` to confirm there
  is no other access.
- Pointer-bar propagation (a repeated bar printed as "same as bar k"; its events are copied) is
  pre-registered. A "no propagation" variant that keeps the ground truth in pointer bars is
  lower by construction (the oracle drops to 0.874). The fair check drops pointer bars from both
  prediction and truth: LLM 0.822, detector 0.579.
- The F-05c detector gives identical calls in both passes of every repeat, so propagation does
  not change its score (0.565 every way).
- LLM events all sit on onsets, so snapping has no effect. The ±1 beat window is a half note in
  2/2 (kv533_1). The exact-onset mean is 0.793, so the go does not depend on the tolerance.
- Memorisation: 4 of 5 pieces were recognised. The unrecognised kv330_2 is the easiest movement
  (detector 0.919), so "it scored highest" does not argue against recall. The control I proposed:
  a disguised rerun (transposed, tempo words and dynamics removed, bar numbers offset), then
  unfamiliar DCML-labelled repertoire. Whether a Koželuch or J. C. Bach DCML corpus with phrase
  labels exists is unverified.
- With n = 5, the percentile bootstrap CI [0.747, 0.901] is narrower than the t-interval
  [0.696, 0.938]. Always report both for n ≤ 6.
- Rerun recipe: patch `score.ART` to a scratch copy of artifacts. Run with
  `PYTHONPATH=<exp>:scripts uv run python audit.py`, then `S.run_llm(ann_dir, prefix="rerun")`.
