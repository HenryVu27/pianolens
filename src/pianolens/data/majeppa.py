"""MAJEPPA loader: transcribed amateur-to-virtuoso performances with expertise labels.

Source: https://huggingface.co/datasets/kkwsts/MAJEPPA-Dataset (ISMIR 2026, arXiv
2608.11026) under ``data/raw/majeppa``; ``performance.zip`` / ``score.zip`` extracted to
``extracted/``. HF license field: ``other`` / "mixed-see-description" with no terms given
(see DATASETS.md). MIDI is transcribed from YouTube audio, so provenance is ``transcribed``.

Labels per performance: ``expertise_level`` (6 levels) and ``recording_type`` (practice,
sight_read, ...). The released alignment is a DTW warping path in seconds
(``alignment.parquet``: performance_id, score_s, perf_s), not a note alignment, so
``AlignedPerformance.alignment`` is None; use ``load_dtw_path``.

Performer identity is not released. ``recording_id`` groups clips cut from one source video
(one performer), so it is used as the performer id: ``majeppa:recording/R_NNNN``. Different
videos by the same person get different ids.

Piece ids: ``majeppa_piece_id`` maps a score's composer + title to a canonical id through the
PianoCoRe parser when a catalogue number and (for multi-movement works) a movement are
unambiguous; otherwise ``majeppa:<score_id>``. Performances without a score keep
``majeppa:<performance_id>``.

Staff: score MIDIs carry no staff, so partitura gives every note staff 0 and hand-synchrony
features are empty. 829 of 886 score MIDIs have exactly two note tracks (right / left hand).
``score_track_staff`` / ``with_track_staff`` put staff 1 on the track with the higher mean pitch
and staff 2 on the other, matching score notes by (onset quarter, pitch); notes whose key sits in
both tracks (unisons) or in neither keep staff 0 and are counted (D-10).

Durations: score MIDIs hold *playback* durations, shortened by one tick (0.4979 quarter for an
eighth) or to about 95% (0.4729). Features that need "no rest between notes" (F-04 even runs)
then find none. ``snap_score_durations`` extends a note to the next onset of its (staff, voice)
stream when the gap is at most ``max_gap_rel`` (7%) of that inter-onset interval. Real
staccato gaps are larger and are kept. ``prepare_aligned`` applies both fixes (D-10).
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterator
from dataclasses import dataclass, field, replace
from pathlib import Path

import mido
import numpy as np
import pandas as pd

from pianolens.data.midi_io import performance_from_midi, score_from_midi
from pianolens.data.pianocore import pianocore_piece_id
from pianolens.data.piece_ids import prefixed_piece_id
from pianolens.data.types import AlignedPerformance, PerformerId, PieceId, Score

log = logging.getLogger(__name__)

DATASET = "majeppa"
DEFAULT_ROOT = Path(__file__).resolve().parents[3] / "data" / "raw" / "majeppa"
EXPERTISE_LEVELS = (
    "child_beginner", "adult_beginner", "adult_intermediate", "child_professional",
    "piano_teacher", "virtuoso",
)  # fmt: skip


def data_available(root: Path | str = DEFAULT_ROOT) -> bool:
    root = Path(root)
    return (root / "metadata.csv").is_file() and (root / "extracted" / "performance").is_dir()


_ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8, "IX": 9,
          "X": 10, "XI": 11, "XII": 12}  # fmt: skip
_OP = re.compile(r"(?<![A-Za-z])Op\.?\s*(?=\d)")
_NO = re.compile(r"(?<![A-Za-z])No\.?\s*(?=\d)")
_LEAD_ROMAN = re.compile(r"^([IVX]+)\.\s")
# Without a " - " separator a title such as "Sonatina Op 36 No 1 Allegro" names one movement
# of a multi-movement work but gives no movement number: never canonical.
_MULTI_NO_SEP = re.compile(r"Sonat|Suite|Concert|Partita|Variation|Fantas|Symphon", re.I)
_ROMAN_TOKEN = re.compile(r"(?<![A-Za-z])(?:I|II|III|IV|V|VI|VII|VIII|IX|X)(?![A-Za-z])", re.I)


def majeppa_piece_id(composer: object, title: object, fallback: str) -> PieceId:
    """Canonical piece id for a MAJEPPA score, or ``majeppa:<fallback>``.

    ``"Frederic Chopin"`` / ``"12 Etudes, Op. 10 - No. 2 in A Minor"`` -> ``chopin_op10_no2``.
    The title is rewritten into PianoCoRe's ``composition`` / ``movement`` form (text after
    " - " is the movement; a leading roman numeral becomes ``N.``) and parsed by
    ``pianocore_piece_id``. Titles without " - " that name a multi-movement form, or that carry
    a bare roman numeral (``"Op 26 I Allegro"``), stay prefixed.
    """
    fb = prefixed_piece_id(DATASET, fallback)
    if not isinstance(composer, str) or not isinstance(title, str) or not composer.strip():
        return fb
    names = composer.split()
    comp = f"{names[-1]},_{'_'.join(names[:-1])}" if len(names) > 1 else names[0]
    t = _NO.sub("No.", _OP.sub("Op.", title))
    if " - " in t:
        work, mv = t.split(" - ", 1)
        m = _LEAD_ROMAN.match(mv)
        if m and m[1] in _ROMAN:
            mv = f"{_ROMAN[m[1]]}. {mv[m.end():]}"
    else:
        work, mv = t, ""
        after_cat = t[t.rfind("Op."):] if "Op." in t else t
        if _MULTI_NO_SEP.search(t) or _ROMAN_TOKEN.search(after_cat):
            return fb
    pid = pianocore_piece_id(comp, work.replace(" ", "_"), mv.replace(" ", "_") or None)
    return fb if pid.startswith("pianocore:") else pid


def _score_piece_ids(md: pd.DataFrame) -> dict[str, PieceId]:
    """score_id -> piece id; ids reached from two different titles are demoted (ambiguous)."""
    scores = md.dropna(subset=["score_id"]).drop_duplicates("score_id")
    ids = {
        s: majeppa_piece_id(c, t, s)
        for s, c, t in zip(scores["score_id"], scores["composer"], scores["piece_title"],
                           strict=True)
    }  # fmt: skip
    titles: dict[str, set[str]] = {}
    for s, t in zip(scores["score_id"], scores["piece_title"], strict=True):
        titles.setdefault(ids[s], set()).add(str(t).strip().lower())
    return {
        s: pid if pid.startswith(f"{DATASET}:") or len(titles[pid]) == 1
        else prefixed_piece_id(DATASET, s)
        for s, pid in ids.items()
    }


def majeppa_index(root: Path | str = DEFAULT_ROOT) -> pd.DataFrame:
    md = pd.read_csv(Path(root) / "metadata.csv")
    by_score = _score_piece_ids(md)
    md["piece_id"] = [
        by_score[s] if isinstance(s, str) else prefixed_piece_id(DATASET, p)
        for s, p in zip(md["score_id"], md["performance_id"], strict=True)
    ]
    return md


@dataclass
class MajeppaStats:
    loaded: int = 0
    failed: int = 0
    score_failed: int = 0  # score MIDI partitura cannot read (the performance is still yielded)
    failures: list[tuple[str, str]] = field(default_factory=list)


def iter_aligned(
    root: Path | str = DEFAULT_ROOT,
    limit: int | None = None,
    with_scores: bool = True,
    stats: MajeppaStats | None = None,
) -> Iterator[AlignedPerformance]:
    """Yield performances with their reference score (None when unmatched or not wanted)."""
    root = Path(root)
    stats = stats if stats is not None else MajeppaStats()
    md = majeppa_index(root)
    scores: dict[str, Score | None] = {}
    rows = md.head(limit) if limit else md
    for r in rows.itertuples():
        try:
            perf = performance_from_midi(
                root / "extracted" / "performance" / f"{r.performance_id}.mid",
                dataset=DATASET,
                performance_id=f"{DATASET}:{r.performance_id}",
                piece_id=r.piece_id,
                performer_id=PerformerId(f"{DATASET}:recording/{r.recording_id}"),
                provenance="transcribed",
                meta={
                    "expertise_level": r.expertise_level,
                    "recording_type": r.recording_type,
                    "composer": r.composer if isinstance(r.composer, str) else "",
                    "piece_title": r.piece_title,
                    "score_coverage": r.score_coverage,
                    "alignment_cost": r.alignment_cost,
                    "youtube_url": r.youtube_url,
                },
            )
            score = None
            if with_scores and isinstance(r.score_id, str):
                if r.score_id not in scores:
                    try:
                        scores[r.score_id] = score_from_midi(
                            root / "extracted" / "score" / f"{r.score_id}.mid",
                            score_id=f"{DATASET}:{r.score_id}",
                            piece_id=r.piece_id,
                        )
                    except Exception as e:  # noqa: BLE001 - e.g. partitura time-signature assert
                        scores[r.score_id] = None
                        stats.failures.append((r.score_id, repr(e)))
                        log.warning("majeppa score %s failed: %r", r.score_id, e)
                score = scores[r.score_id]
                if score is None:
                    stats.score_failed += 1
            stats.loaded += 1
            yield AlignedPerformance(perf, score, None)
        except Exception as e:  # noqa: BLE001 - count and continue
            stats.failed += 1
            stats.failures.append((r.performance_id, repr(e)))
            log.warning("majeppa %s failed: %r", r.performance_id, e)


def load_dtw_path(performance_id: str, root: Path | str = DEFAULT_ROOT) -> pd.DataFrame:
    """DTW warping path (``score_s``, ``perf_s``) for one ``P_NNNN`` performance."""
    pid = performance_id.removeprefix(f"{DATASET}:")
    return pd.read_parquet(
        Path(root) / "alignment.parquet", filters=[("performance_id", "==", pid)]
    )[["score_s", "perf_s"]].reset_index(drop=True)


def score_track_staff(score_id: str, root: Path | str = DEFAULT_ROOT
                      ) -> dict[tuple[float, int], int] | None:
    """(onset quarter rounded to 1e-3, pitch) -> staff (1 upper, 2 lower, 0 in both tracks).

    None unless the score MIDI has exactly two tracks with notes. Staff 1 is the track with the
    higher mean pitch. Quarters are ticks / ticks-per-beat, as partitura reads a score MIDI.
    """
    sid = score_id.removeprefix(f"{DATASET}:")
    m = mido.MidiFile(Path(root) / "extracted" / "score" / f"{sid}.mid")
    tracks: list[list[tuple[float, int]]] = []
    for t in m.tracks:
        tick, keys = 0, []
        for msg in t:
            tick += msg.time
            if msg.type == "note_on" and msg.velocity > 0:
                keys.append((round(tick / m.ticks_per_beat, 3), int(msg.note)))
        if keys:
            tracks.append(keys)
    if len(tracks) != 2:
        return None
    upper = 0 if np.mean([p for _, p in tracks[0]]) >= np.mean([p for _, p in tracks[1]]) else 1
    out: dict[tuple[float, int], int] = {}
    for ti, keys in enumerate(tracks):
        staff = 1 if ti == upper else 2
        for k in keys:
            out[k] = 0 if out.get(k, staff) != staff else staff
    return out


def with_track_staff(ap: AlignedPerformance, score_id: str, root: Path | str = DEFAULT_ROOT
                     ) -> tuple[AlignedPerformance, dict[str, int]]:
    """Copy of ``ap`` whose score notes carry staff 1 / 2 from the score MIDI tracks.

    Use on the score returned by ``align_performance`` (MIDI scores have no repeats, so its
    quarters are the file's). Returns ``(ap, counts)`` with ``n_staff1``, ``n_staff2`` and
    ``n_staff0`` (unisons across tracks or keys not found). Unchanged when the score MIDI does
    not have exactly two note tracks (``counts["two_tracks"] == 0``).
    """
    keys = score_track_staff(score_id, root)
    sn = ap.score.notes
    if keys is None or "staff" not in (sn.dtype.names or ()):
        return ap, {"two_tracks": 0, "n_staff1": 0, "n_staff2": 0, "n_staff0": len(sn)}
    staff = np.array([keys.get((round(float(q), 3), int(p)), 0)
                      for q, p in zip(sn["onset_quarter"], sn["pitch"], strict=True)], dtype=int)
    notes = sn.copy()
    notes["staff"] = staff
    score = replace(ap.score, notes=notes)
    counts = {"two_tracks": 1, "n_staff1": int((staff == 1).sum()),
              "n_staff2": int((staff == 2).sum()), "n_staff0": int((staff == 0).sum())}
    return AlignedPerformance(ap.performance, score, ap.alignment), counts


def snap_score_durations(notes: np.ndarray, max_gap_rel: float = 0.07) -> tuple[np.ndarray, int]:
    """Copy of a score note array with playback-shortened durations extended to the next onset.

    Within each (staff, voice) stream, a note ending ``gap`` quarters before the stream's next
    onset gets ``duration + gap`` when ``0 < gap <= max_gap_rel * (next onset - onset)``.
    ``duration_beat`` is scaled by the same factor. Returns ``(notes, n_changed)``.
    """
    out = notes.copy()
    names = notes.dtype.names or ()
    staff = notes["staff"] if "staff" in names else np.zeros(len(notes), int)
    voice = notes["voice"] if "voice" in names else np.zeros(len(notes), int)
    on = notes["onset_quarter"].astype(float)
    dur = notes["duration_quarter"].astype(float)
    new = dur.copy()
    for key in set(zip(staff.tolist(), voice.tolist(), strict=True)):
        idx = np.flatnonzero((staff == key[0]) & (voice == key[1]))
        onsets = np.unique(on[idx])
        nxt_pos = np.searchsorted(onsets, on[idx], side="right")
        has = nxt_pos < len(onsets)
        i, nx = idx[has], onsets[nxt_pos[has]]
        gap = nx - (on[i] + dur[i])
        ok = (gap > 1e-9) & (gap <= max_gap_rel * (nx - on[i]))
        new[i[ok]] = nx[ok] - on[i[ok]]
    changed = new != dur
    out["duration_quarter"] = new
    if "duration_beat" in names:
        with np.errstate(divide="ignore", invalid="ignore"):
            f = np.where(dur > 0, new / dur, 1.0)
        out["duration_beat"] = notes["duration_beat"] * f
    return out, int(changed.sum())


def prepare_aligned(ap: AlignedPerformance, score_id: str, root: Path | str = DEFAULT_ROOT
                    ) -> tuple[AlignedPerformance, dict[str, int]]:
    """``with_track_staff`` then ``snap_score_durations`` on an aligned MAJEPPA performance."""
    ap, counts = with_track_staff(ap, score_id, root)
    notes, n = snap_score_durations(ap.score.notes)
    counts["n_durations_snapped"] = n
    return AlignedPerformance(ap.performance, replace(ap.score, notes=notes), ap.alignment), counts
