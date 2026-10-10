"""Regenerate the synthetic PianoVAM-layout fixture (no PianoVAM content is copied).

One recording, six notes. The label files list the first chord in a different order from the
MIDI (as the real files do within chords), one note is ``Noinfo``, and the manual file covers the
first three rows only. Run: ``uv run python tests/fixtures/pianovam/make_fixture.py``.
"""

import json
from pathlib import Path

import mido

HERE = Path(__file__).parent
STEM = "2000-01-01_00-00-00"
TPB = 480  # default tempo 500,000 us per beat, so 1 tick = 1/960 s
# (onset_tick, off_tick, pitch, velocity) in MIDI order
NOTES = [(480, 960, 60, 70), (480, 960, 64, 71), (480, 960, 67, 72),
         (960, 1200, 48, 60), (960, 1440, 72, 80), (1440, 1920, 60, 65)]  # fmt: skip
# label rows in the authors' order: (index into NOTES, hand, finger)
ROWS = [(2, "R", "5"), (0, "R", "1"), (1, "R", "3"), (3, "L", "5"), (4, "Noinfo", "Noinfo"),
        (5, "R", "1")]  # fmt: skip
MANUAL = [(2, "R", "5"), (0, "L", "1"), (1, "R", "2")]  # differs from video on row 2


def sec(tick: int) -> float:
    return tick / (2 * TPB)


def write_midi() -> None:
    ev = [(on, "note_on", p, v) for on, _, p, v in NOTES]
    ev += [(off, "note_off", p, 0) for _, off, p, _ in NOTES]
    ev.sort(key=lambda e: (e[0], e[1] == "note_on"))
    mid, tr, now = mido.MidiFile(ticks_per_beat=TPB), mido.MidiTrack(), 0
    for t, kind, p, v in ev:
        tr.append(mido.Message(kind, note=p, velocity=v, time=t - now))
        now = t
    mid.tracks.append(tr)
    (HERE / "MIDI").mkdir(exist_ok=True)
    mid.save(HERE / "MIDI" / f"{STEM}.mid")


def write_labels(folder: str, rows: list[tuple[int, str, str]]) -> None:
    (HERE / folder).mkdir(exist_ok=True)
    lines = ["onset\tkey_offset\tframe_offset\tnote\tvelocity\thand\tfinger"]
    for i, hand, finger in rows:
        on, off, p, v = NOTES[i]
        lines.append(f"{sec(on):.6f}\t{sec(off):.6f}\t{sec(off):.6f}\t{p}\t{v}\t{hand}\t{finger}")
    (HERE / folder / f"{STEM}.tsv").write_text("\n".join(lines) + "\n")


def write_metadata() -> None:
    rec = {"record_time": STEM, "composer": "Test", "piece": "Fixture", "P1_name": "Tester",
           "P1_skill": "Advanced", "P1_age": 0, "P2_name": None, "P2_skill": None,
           "performance_method": "Solo", "split": "test"}  # fmt: skip
    (HERE / "metadata.json").write_text(json.dumps({"0": rec}, indent=1) + "\n")


if __name__ == "__main__":
    write_midi()
    write_labels("Fingering", ROWS)
    write_labels("Fingering_GT", MANUAL)
    write_metadata()
