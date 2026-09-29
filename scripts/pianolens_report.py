"""PianoLens practice report (F-08): one performance MIDI in, one HTML page + one JSON out.

Examples::

    uv run python scripts/pianolens_report.py take1.mid --piece-id chopin_op10_no3 \\
        --provenance disklavier --out data/interim/reports/take1.html
    uv run python scripts/pianolens_report.py p01.mid --score excerpt.musicxml \\
        --piece-id chopin_op10_no3 --provenance sensor \\
        --reference-midi other_pianists/*.mid --reference-provenance sensor --out r.html
    uv run python scripts/pianolens_report.py take1.mid --piece-id ... --take take2.mid take3.mid
    uv run python scripts/pianolens_report.py phone.mid --piece-id ... --provenance transcribed \\
        --filter-extras rule --out r.html

``--filter-extras rule`` (off by default, transcribed input only) removes short notes at C7 or
above on recurring pitches with no harmonic source before scoring: the A-01b rule, validated
for Transkun output only (numbers in ``docs/specs/phone-audio-baseline.md``, A-01b).

``--piece-id`` looks the score up in ASAP when ``--score`` is not given, and loads the
PianoCoRe expert references of that piece. See ``pianolens.report`` for what the report holds.
"""

from __future__ import annotations

import argparse
import logging
import tempfile
import warnings
from pathlib import Path

from pianolens.report import report_from_files, write_report


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("performance", help="performance MIDI file")
    ap.add_argument("--score", help="score file (MusicXML, MEI, ...)")
    ap.add_argument("--piece-id", help="canonical piece id, e.g. chopin_op10_no3")
    ap.add_argument("--title", default="")
    ap.add_argument("--provenance", default="unknown",
                    choices=["disklavier", "sensor", "transcribed", "synthetic", "unknown"],
                    help="how the MIDI was captured (velocity confidence depends on it)")
    ap.add_argument("--take", nargs="*", default=[], help="repeated takes of the same passage")
    ap.add_argument("--reference-midi", nargs="*", default=[],
                    help="other performances of the same score (expert references)")
    ap.add_argument("--reference-provenance", default="unknown",
                    choices=["disklavier", "sensor", "transcribed", "synthetic", "unknown"])
    ap.add_argument("--exclude-reference", nargs="*", default=[],
                    help="PianoCoRe performance / source ids to leave out")
    ap.add_argument("--no-pianocore", action="store_true", help="do not load PianoCoRe refs")
    ap.add_argument("--note", action="append", default=[], help="extra provenance note")
    ap.add_argument("--filter-extras", choices=["off", "rule"], default="off",
                    help="remove likely transcription extras first (transcribed input only)")
    ap.add_argument("--out", required=True, help="output .html (the .json goes beside it)")
    args = ap.parse_args()
    warnings.filterwarnings("ignore")
    logging.basicConfig(level=logging.WARNING)
    td = tempfile.TemporaryDirectory()
    if args.filter_extras != "off":
        if args.provenance != "transcribed":
            ap.error("--filter-extras applies to --provenance transcribed only")
        args.performance, args.take = _filter_extras(args, Path(td.name))
    rep = report_from_files(
        args.performance, score=args.score, piece_id=args.piece_id, provenance=args.provenance,
        title=args.title, takes=args.take, reference_midis=args.reference_midi,
        reference_provenance=args.reference_provenance, use_pianocore=not args.no_pianocore,
        exclude_references=args.exclude_reference, notes=args.note)  # fmt: skip
    td.cleanup()
    h, j = write_report(rep, Path(args.out))
    print(f"wrote {h}\nwrote {j}")
    for k, d in enumerate(rep["practise"], 1):
        print(f"{k}. [{d['tier']}] {d['text']}")
    if rep["errors"]:
        print("component errors:", rep["errors"])


def _filter_extras(args: argparse.Namespace, tmp: Path) -> tuple[str, list[str]]:
    """Filter the performance and takes into ``tmp``; add a provenance note saying so."""
    from pianolens.audio.extra_filter import filter_midi

    out, removed, total = [], 0, 0
    for k, f in enumerate([args.performance, *args.take]):
        dst = tmp / f"{k:02d}_{Path(f).name}"
        info = filter_midi(f, dst)
        removed, total = removed + info["n_removed"], total + info["n_in"]
        out.append(str(dst))
    args.note.append(f"Extra-note filter (A-01b rule) removed {removed} of {total} transcribed "
                     "notes before scoring: short notes at C7 or above on recurring pitches with "
                     "no harmonic source. It removes only part of such artefacts, so extra-note "
                     "flags stay low confidence.")
    return out[0], out[1:]


if __name__ == "__main__":
    main()
