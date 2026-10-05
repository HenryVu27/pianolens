"""Dump the PianoCoRe refined score of each R-11 pilot piece, measure by measure.

Reads the score only (no performance MIDI, no alignment, no expert features), so it is allowed
before the R-11 pre-registration. One text file per piece:

    m<N> start=<quarters> ts=<beats>/<type>
      <q>:<pitch>/<pitch> ...      (q = onset in quarters from the measure start)

PianoCoRe measure numbers come from the refined score MIDI's time signatures (they equal
``s_measure`` in the tier A cache), not from printed bar numbers.

    uv run python score_dump.py data/interim/tonebase_annotations/scores
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

from pianolens.data.pianocore import PianoCoRe

PIECES = {
    "NOC": "pianocore:Chopin,_Frédéric/Nocturnes,_Op.9/Nocturne_No.2_in_E_flat_major,_Andante",
    "WAL": 'pianocore:Chopin,_Frédéric/Waltzes,_Op.64/Waltz_No.6_in_D_flat_major,_"Minute_Waltz",'
           "_Molto_vivace",
    "ETU": "chopin_op10_no4",
}  # fmt: skip
NAMES = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]


def name(p: int) -> str:
    return f"{NAMES[p % 12]}{p // 12 - 1}"


def dump(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    pc = PianoCoRe()
    idx = pc.index
    for tag, pid in PIECES.items():
        rows = idx[idx["piece_id"] == pid]
        assert rows["refined_score_midi_path"].nunique() == 1, (tag, "expected one score")
        s = pc.load_score(rows.iloc[0])
        nm, n = s.note_measures(), s.notes
        lines = [f"# {tag} {pid}", f"# score {rows.iloc[0]['refined_score_midi_path']}",
                 f"# {len(s.measures)} PianoCoRe measures, {len(n)} notes"]
        for m in s.measures:
            sel = n[nm == m["number"]]
            sel = sel[np.lexsort((sel["pitch"], sel["onset_quarter"]))]
            ts = f"{sel['ts_beats'][0]}/{sel['ts_beat_type'][0]}" if len(sel) else "?"
            lines.append(f"m{m['number']} start={m['start_quarter']:g} "
                         f"end={m['end_quarter']:g} ts={ts} n={len(sel)}")
            parts = []
            for o in np.unique(sel["onset_quarter"]):
                ps = sel["pitch"][sel["onset_quarter"] == o]
                parts.append(f"{o - m['start_quarter']:g}:" + "/".join(name(int(p)) for p in ps))
            lines.append("  " + "  ".join(parts))
        (out / f"{tag}_pc_measures.txt").write_text("\n".join(lines) + "\n")
        print(tag, len(s.measures), "measures")


if __name__ == "__main__":
    dump(Path(sys.argv[1]))
