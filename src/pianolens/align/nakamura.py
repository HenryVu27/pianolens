"""Cross-check aligner: Nakamura et al.'s HMM MusicXML-to-MIDI alignment tool.

Nakamura, Yoshii, Katayose, "Performance Error Detection and Post-Processing for Fast and
Accurate Symbolic Music Alignment", ISMIR 2017. Tool: https://midialignment.github.io/
(``AlignmentTool_v190813.zip``). It is not a Python package and is not vendored here: download
it, run its ``compile.sh`` (plain ``g++ -O2``; builds on macOS arm64 in about 15 s), and pass
the folder (the one holding ``Programs/``) as ``tool_dir`` or set ``PIANOLENS_NAKAMURA_DIR``.

The tool reads the MusicXML itself and does not unfold repeats the way partitura does, so this
wrapper is only meaningful for scores with a single repeat path. Its score notes are mapped to
partitura's unfolded ids by (score time in quarters, pitch); its performance notes are mapped
to partitura performance ids by (onset time, pitch). Notes it marks as pitch errors
(``errorindex == 1``) become an insertion plus a deletion, as in partitura's convention.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any

import partitura as pt

from pianolens.align.core import AlignmentList, score_note_array, unfold_variant

_STEPS = ("midi2pianoroll", "MusicXMLToHMM", "MusicXMLToFmt3x", "ScorePerfmMatcher",
          "ErrorDetection", "RealignmentMOHMM")  # fmt: skip


def find_tool(tool_dir: str | Path | None = None) -> Path | None:
    """The tool folder if its compiled programs exist, else None."""
    d = Path(tool_dir or os.environ.get("PIANOLENS_NAKAMURA_DIR", "")).expanduser()
    if d and all((d / "Programs" / p).is_file() for p in _STEPS):
        return d
    return None


def run_nakamura(xml_path: str | Path, midi_path: str | Path, tool_dir: str | Path) -> Path:
    """Run the tool's MusicXML-to-MIDI pipeline in a temp dir; return the ``*_match.txt`` path.

    Mirrors ``MusicXMLToMIDIAlign.sh`` (same programs, same parameters 0.01 / 0 / 0.3).
    The caller owns the returned file's parent directory.
    """
    prog = Path(tool_dir).resolve() / "Programs"
    work = Path(tempfile.mkdtemp(prefix="nakamura_"))
    shutil.copy(xml_path, work / "ref.xml")
    shutil.copy(midi_path, work / "perf.mid")

    def run(*args: str) -> None:
        subprocess.run(args, cwd=work, check=True, capture_output=True, timeout=1800)

    run(str(prog / "midi2pianoroll"), "0", "perf")
    run(str(prog / "MusicXMLToHMM"), "ref.xml", "ref_hmm.txt")
    run(str(prog / "MusicXMLToFmt3x"), "ref.xml", "ref_fmt3x.txt")
    run(str(prog / "ScorePerfmMatcher"), "ref_hmm.txt", "perf_spr.txt", "pre.txt", "0.01")
    run(str(prog / "ErrorDetection"), "ref_fmt3x.txt", "ref_hmm.txt", "pre.txt", "err.txt", "0")
    run(
        str(prog / "RealignmentMOHMM"),
        "ref_fmt3x.txt", "ref_hmm.txt", "err.txt", "perf_match.txt", "0.3",
    )  # fmt: skip
    return work / "perf_match.txt"


def _tpqn(fmt3x: Path) -> int:
    with open(fmt3x) as f:
        for line in f:
            if line.startswith("//TPQN:"):
                return int(line.split()[1])
    raise ValueError(f"no TPQN in {fmt3x}")


def _read_match(path: Path) -> tuple[list[tuple], list[float]]:
    """Rows (perf_onset, pitch, score_ticks, errorindex) and ticks of missing score notes."""
    rows, missing = [], []
    with open(path) as f:
        for line in f:
            if line.startswith("//Missing"):
                missing.append(float(line.split()[1]))
                continue
            if line.startswith("//") or not line.strip():
                continue
            c = line.split()
            pitch = int(pt.utils.music.note_name_to_midi_pitch(c[3]))
            rows.append((float(c[1]), pitch, float(c[8]), int(c[10])))
    return rows, missing


def nakamura_align(
    xml_path: str | Path, midi_path: str | Path, tool_dir: str | Path, part: Any = None
) -> AlignmentList:
    """Align with Nakamura's tool; return a partitura-style alignment in partitura ids.

    Score ids are those of the (single-path) unfolded ``part`` (loaded from ``xml_path`` if not
    given); performance ids are those of ``partitura.load_performance_midi(midi_path)``.
    """
    perf_na = pt.load_performance_midi(str(midi_path)).note_array()
    if part is None:
        part = pt.score.merge_parts(pt.load_score(str(xml_path)).parts)
    upart = unfold_variant(part)  # raises for scores with repeats
    sna = score_note_array(upart)

    match_path = run_nakamura(xml_path, midi_path, tool_dir)
    try:
        tpqn = _tpqn(match_path.parent / "ref_fmt3x.txt")
        rows, missing = _read_match(match_path)
    finally:
        shutil.rmtree(match_path.parent, ignore_errors=True)

    all_ticks = [r[2] for r in rows if r[3] != 3] + missing
    offset = float(sna["onset_quarter"].min()) - min(all_ticks) / tpqn

    score_pool: dict[tuple, list[str]] = defaultdict(list)
    for q, p, i in zip(sna["onset_quarter"], sna["pitch"], sna["id"], strict=True):
        score_pool[(round(float(q) * 96), int(p))].append(str(i))
    perf_pool: dict[tuple, list[str]] = defaultdict(list)
    for t, p, i in zip(perf_na["onset_sec"], perf_na["pitch"], perf_na["id"], strict=True):
        perf_pool[(round(float(t) * 1000), int(p))].append(str(i))

    def take(pool: dict, key: tuple, tol: int) -> str | None:
        for d in sorted(range(-tol, tol + 1), key=abs):
            ids = pool.get((key[0] + d, key[1]))
            if ids:
                return ids.pop(0)
        return None

    alignment: AlignmentList = []
    for onset, pitch, ticks, err in rows:
        pid = take(perf_pool, (round(onset * 1000), pitch), 2)
        sid = None
        if err == 0:
            sid = take(score_pool, (round((ticks / tpqn + offset) * 96), pitch), 1)
        if pid is None:
            continue
        if sid is None:
            alignment.append({"label": "insertion", "performance_id": pid})
        else:
            alignment.append({"label": "match", "score_id": sid, "performance_id": pid})
    for ids in perf_pool.values():
        alignment += [{"label": "insertion", "performance_id": i} for i in ids]
    for ids in score_pool.values():
        alignment += [{"label": "deletion", "score_id": i} for i in ids]
    return alignment


def available() -> bool:
    return find_tool() is not None


__all__ = ["available", "find_tool", "nakamura_align", "run_nakamura"]

