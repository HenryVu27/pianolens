# partitura 1.9.0 / parangonar 3.3.3 API traps (found in F-01, 2026-09-27)

- `DualDTWNoteMatcher()(score_na, perf_na, process_ornaments=, score_part=)` needs the score
  note array built with `part.note_array(include_grace_notes=True)`; without it: `ValueError: no
  field of name is_grace`. Returned ids are `np.str_`; cast to `str` before comparing / hashing
  into JSON.
- DualDTW does NOT handle repeats. The score must already be unfolded to the performer's path.
  `pt.score.get_paths(part, no_repeats=False, all_repeats=False, ignore_leap_info=True)` lists
  every path (1 for most ASAP scores, up to 2048 for Schubert D.935/3);
  `pt.score.new_part_from_path(path, part, update_ids=True)` builds one, ids get `-1`, `-2`.
  Note counts per path can be computed from `get_segments(part)` without building parts.
- Unfolding an already unfolded part crashes (`AttributeError: 'NoneType' object has no
  attribute 'start'` in `replace_refs`). `pianolens.align.is_unfolded` detects it by id suffix.
- `get_paths` / `unfold_part_maximal` recurse deeply; raise `sys.setrecursionlimit` (we use
  100k) before calling on long sonatas.
- `pt.load_match(path)` returns a 2-tuple `(performance, alignment)` unless `create_score=True`.
  It crashes with `min() iterable argument is empty` on an empty match stub.
- `parangonar.fscore_alignments` is O(n^2) (`pred in gt_list`); use
  `pianolens.align.evaluate_alignment` (set-based) instead.
- `parangonar.RepeatIdentifier()(score, performance)` wants an object with `.parts` and a
  partitura Performance; returns `(path_string, Path)` or `(None, None)` if one path.
- Nakamura AlignmentTool_v190813 builds on macOS arm64 with the stock `compile.sh` (g++ -O2,
  about 15 s, no errors). Its match file: col 9 = score time in ticks (`//TPQN:` in
  `*_fmt3x.txt`), col 11 = errorindex (0 ok, 1 pitch error, 3 extra). Wrapper:
  `pianolens.align.nakamura`.
- `get_paths` is STATEFUL: it calls `add_segments(part)` without `force_new`, so after a
  `new_part_from_path` on the same part a second call can return far fewer paths (Beethoven
  11-3: 70 then 4). Always `pt.score.add_segments(part, force_new=True)` first. This silently
  broke da-capo pieces in validation run 1.
- `RepeatIdentifier` is broken with numpy 2 (`np.row_stack` removed); don't use it.
- Nakamura tool crashes (SIGABRT/SIGSEGV) on ~9% of ASAP single-path performances.

# Found in BL-26 (2026-10-10)
- parangonar 3.3.3 `CleanOrnamentMatcher` ornament step (matchers.py ~1370-1440): every matched
  score note with ANY ornament is unmatched and re-matched to the earliest insertion within +-2
  semitones in [onset - 0.25 s, offset]; the same-pitch preference compares against a stale loop
  variable `pitch`, not the ornament's pitch, and the chosen insertion is not removed from the
  insertion list. So tagging notes as ornaments changes their matches; do not tag written notes.
- `pt.score.iter_parts(score)` fails on a `Score` (no `.children`); pass `score.parts`.
- `pt.load_musicxml(io.BytesIO(...), force_note_ids="keep")` loads edited XML without a temp file.
