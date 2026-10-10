"""PianoVAM loader: MIDI and per-note hand labels. This loader reads no audio; a 4.4 GB audio
subset (84 of the 107 ``Audio/*.wav``, list in ``Audio_SUBSET.txt``) is on this Mac since A-01b
and is read by ``pianolens.audio`` code (DATASETS.md, DECISIONS 2026-09-28 after A-01b). Video
and hand skeletons are not downloaded.

Source: https://huggingface.co/datasets/PianoVAM/PianoVAM_v1 (ISMIR 2025, arXiv 2509.08800),
v1.2, commit ``1f039ab9``; ``MIDI/*.mid`` and ``metadata.json`` under ``data/raw/pianovam``.
License CC BY-NC-SA 4.0 (dataset card). The MIDI was captured live from a Disklavier during
daily practice by 10 amateur pianists (none music majors), so provenance is ``disklavier``.

Labels: ``P1_skill`` is self-reported (Beginner / Intermediate / Advanced). No scores are
released, and the piece names are free text (70 pieces, some improvisations), so piece ids are
``pianovam:<composer>/<piece>`` prefixed ids. Performer ids use the first name given
(``pianovam:<name>``, lower-cased). One four-hands recording has a second performer (P2_*),
kept in ``meta``.

Hand labels (BL-24, v1.2 ``Fingering/``, ``Fingering_GT/`` and ``TSV/``, same commit):

* ``video``: ``Fingering/<record_time>.tsv``, 106 solo recordings (not the four-hands one). Made
  automatically by the authors from MediaPipe hand landmarks matched to the keys held down in
  the MIDI; no manual correction. ``Noinfo`` (no finger qualifies, or no clear winner) becomes
  ``""``. Card: 19.9% ``Noinfo``; 99.2% correct hand on labelled notes against ``manual``.
* ``manual``: ``Fingering_GT/<record_time>.tsv``, the authors' annotations of the first 150
  TSV rows of 10 recordings and the first 300 of one (1,800 notes). Notes after that prefix
  get ``""``.

The label files list the notes in the authors' order, which differs from the onset-sorted
``Performance.notes`` within chords. ``hand_labels`` matches each row to the note with the same
pitch and an onset within 0.5 ms (measured on all 107 files: every row matches exactly one
note, velocities agree, onsets differ by at most 0.12 ms) and returns ``HAND_LABEL_DTYPE`` rows
in ``Performance.notes`` order.

``SCORE_CANDIDATES`` maps PianoVAM titles to app-catalogue piece ids by title only. The
recordings are practice sessions (fragments, restarts), and none was aligned to its score here.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from pianolens.data.midi_io import performance_from_midi
from pianolens.data.piece_ids import prefixed_piece_id
from pianolens.data.types import HAND_LABEL_DTYPE, Performance, PerformerId

log = logging.getLogger(__name__)

DATASET = "pianovam"
DEFAULT_ROOT = Path(__file__).resolve().parents[3] / "data" / "raw" / "pianovam"
SKILLS = ("Beginner", "Intermediate", "Advanced")


def data_available(root: Path | str = DEFAULT_ROOT) -> bool:
    root = Path(root)
    return (root / "metadata.json").is_file() and (root / "MIDI").is_dir()


def _slug(x: object) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(x).lower()).strip("_")


def pianovam_index(root: Path | str = DEFAULT_ROOT) -> pd.DataFrame:
    """One row per recording: metadata.json fields plus ``performance_id``, ``piece_id``,
    ``performer_id`` and ``midi_path``."""
    root = Path(root)
    md = pd.DataFrame(json.loads((root / "metadata.json").read_text()).values())
    md["performance_id"] = DATASET + ":" + md["record_time"]
    md["piece_id"] = [prefixed_piece_id(DATASET, f"{_slug(c)}/{_slug(p)}")
                      for c, p in zip(md["composer"], md["piece"], strict=True)]  # fmt: skip
    md["performer_id"] = DATASET + ":" + md["P1_name"].str.strip().str.lower()
    md["midi_path"] = [root / "MIDI" / f"{t}.mid" for t in md["record_time"]]
    return md


@dataclass
class PianoVAMStats:
    loaded: int = 0
    failed: int = 0
    missing: int = 0
    failures: list[tuple[str, str]] = field(default_factory=list)


def iter_performances(
    root: Path | str = DEFAULT_ROOT,
    limit: int | None = None,
    stats: PianoVAMStats | None = None,
) -> Iterator[Performance]:
    """Yield every recording as a ``Performance`` (no score exists)."""
    stats = stats if stats is not None else PianoVAMStats()
    md = pianovam_index(root)
    for r in (md.head(limit) if limit else md).itertuples():
        if not Path(r.midi_path).is_file():
            stats.missing += 1
            continue
        try:
            yield performance_from_midi(
                Path(r.midi_path), dataset=DATASET, performance_id=r.performance_id,
                piece_id=r.piece_id, performer_id=PerformerId(r.performer_id),
                provenance="disklavier",
                meta={"skill": r.P1_skill, "composer": r.composer, "piece": r.piece,
                      "performance_method": r.performance_method, "split": r.split,
                      "age": r.P1_age, "p2_name": r.P2_name, "p2_skill": r.P2_skill})  # fmt: skip
            stats.loaded += 1
        except Exception as e:  # noqa: BLE001 - count and continue
            stats.failed += 1
            stats.failures.append((r.record_time, repr(e)))
            log.warning("pianovam %s failed: %r", r.record_time, e)


# --------------------------------------------------------------------------- hand labels (BL-24)

HAND_SOURCES = {"video": "Fingering", "manual": "Fingering_GT"}
"""Label source -> folder under the PianoVAM root."""

ONSET_TOL_SEC = 5e-4
"""Row-to-note onset tolerance. Distinct onsets in the MIDI are at least 1.04 ms apart."""


class HandLabelMismatch(ValueError):
    """A label file does not map one-to-one onto the performance notes."""


def hand_labels_available(root: Path | str = DEFAULT_ROOT, source: str = "video") -> bool:
    return (Path(root) / HAND_SOURCES[source]).is_dir()


def record_time(perf: Performance) -> str:
    """The PianoVAM file stem (``YYYY-MM-DD_hh-mm-ss``) of a performance from this loader."""
    return perf.performance_id.removeprefix(DATASET + ":")


def read_label_file(path: Path | str) -> pd.DataFrame:
    """One ``Fingering/`` or ``Fingering_GT/`` TSV as it is on disk (authors' row order)."""
    return pd.read_csv(path, sep="\t", dtype={"hand": str, "finger": str}, keep_default_na=False)


def _match_rows(notes: np.ndarray, onset: np.ndarray, pitch: np.ndarray) -> np.ndarray:
    """Index into ``notes`` for every row (same pitch, nearest onset within tolerance), or -1."""
    idx = np.full(len(onset), -1, dtype=np.int64)
    n_on = notes["onset_sec"].astype(np.float64)
    for p in np.unique(pitch):
        cand = np.flatnonzero(notes["pitch"] == p)
        rows = np.flatnonzero(pitch == p)
        if len(cand) == 0:
            continue
        order = np.argsort(n_on[cand], kind="stable")
        cand, on = cand[order], n_on[cand[order]]
        j = np.clip(np.searchsorted(on, onset[rows]), 1, max(len(on) - 1, 1))
        lo = np.where(len(on) > 1, j - 1, 0)
        hi = np.where(len(on) > 1, j, 0)
        best = np.where(np.abs(on[lo] - onset[rows]) <= np.abs(on[hi] - onset[rows]), lo, hi)
        ok = np.abs(on[best] - onset[rows]) <= ONSET_TOL_SEC
        idx[rows[ok]] = cand[best[ok]]
    return idx


def hand_labels(
    perf: Performance, source: str = "video", root: Path | str = DEFAULT_ROOT
) -> np.ndarray | None:
    """Hand labels for ``perf`` (from this loader) as ``HAND_LABEL_DTYPE``, one row per
    ``perf.notes`` row in the same order. ``None`` when the recording has no file for
    ``source``. Raises ``HandLabelMismatch`` if a row matches no note, two rows match the same
    note, or a matched velocity differs."""
    path = Path(root) / HAND_SOURCES[source] / f"{record_time(perf)}.tsv"
    if not path.is_file():
        return None
    df = read_label_file(path)
    notes = perf.notes
    idx = _match_rows(notes, df["onset"].to_numpy(np.float64), df["note"].to_numpy(np.int64))
    hit = idx[idx >= 0]
    bad_vel = int((notes["velocity"][hit] != df["velocity"].to_numpy()[idx >= 0]).sum())
    n_dup = len(hit) - len(np.unique(hit))
    if (idx < 0).any() or n_dup or bad_vel:
        raise HandLabelMismatch(
            f"{path.name}: {int((idx < 0).sum())} unmatched rows, {n_dup} duplicate matches, "
            f"{bad_vel} velocity mismatches ({len(df)} rows, {len(notes)} notes)"
        )
    out = np.zeros(len(notes), dtype=HAND_LABEL_DTYPE)
    out["id"] = notes["id"]
    hand = df["hand"].to_numpy(str)
    finger = df["finger"].to_numpy(str)
    known = np.isin(hand, ["L", "R"])
    out["hand"][idx[known]] = hand[known]
    fk = known & np.isin(finger, ["1", "2", "3", "4", "5"])
    out["finger"][idx[fk]] = finger[fk].astype(np.int8)
    return out


@dataclass
class HandLabelStats:
    loaded: int = 0
    no_labels: int = 0
    failed: int = 0
    failures: list[tuple[str, str]] = field(default_factory=list)


def iter_hand_labels(
    source: str = "video",
    root: Path | str = DEFAULT_ROOT,
    limit: int | None = None,
    stats: HandLabelStats | None = None,
) -> Iterator[tuple[Performance, np.ndarray]]:
    """Yield ``(performance, labels)`` for every recording that has a ``source`` label file.
    Recordings without one are counted in ``no_labels``; mismatches are logged and counted."""
    stats = stats if stats is not None else HandLabelStats()
    for perf in iter_performances(root, limit=limit):
        try:
            labels = hand_labels(perf, source, root)
        except HandLabelMismatch as e:
            stats.failed += 1
            stats.failures.append((record_time(perf), str(e)))
            log.warning("pianovam hand labels %s: %s", record_time(perf), e)
            continue
        if labels is None:
            stats.no_labels += 1
            continue
        stats.loaded += 1
        yield perf, labels


def hand_label_summary(root: Path | str = DEFAULT_ROOT) -> pd.DataFrame:
    """One row per recording from the label files alone (no MIDI parsing): note count, video
    labels (left, right, none), manual rows, and the title-level score candidates."""
    root = Path(root)
    md = pianovam_index(root)
    rows = []
    for r in md.itertuples():
        row: dict[str, object] = {
            "record_time": r.record_time,
            "performance_id": r.performance_id,
            "piece_id": r.piece_id,
            "skill": r.P1_skill,
            "split": r.split,
        }
        vid = root / HAND_SOURCES["video"] / f"{r.record_time}.tsv"
        man = root / HAND_SOURCES["manual"] / f"{r.record_time}.tsv"
        if vid.is_file():
            h = read_label_file(vid)["hand"]
            known = h.isin(["L", "R"])
            row.update(n_notes=len(h), n_left=int((h == "L").sum()),
                       n_right=int((h == "R").sum()), n_noinfo=int((~known).sum()))  # fmt: skip
        row["n_manual"] = len(read_label_file(man)) if man.is_file() else 0
        cand = SCORE_CANDIDATES.get(r.piece_id)
        row["score_candidates"] = cand[0] if cand else ()
        row["score_match"] = cand[1] if cand else ""
        rows.append(row)
    out = pd.DataFrame(rows)
    for c in ("n_notes", "n_left", "n_right", "n_noinfo"):
        out[c] = out[c].astype("Int64")
    return out


_OP17 = tuple(f"schumann_op17_mv{i}" for i in (1, 2, 3))
_K545 = ("mozart_k545_mv1", "mozart_k545_mv2", "mozart_k545_mv3", "mozart_k545")
_TOMBEAU = tuple(
    f"pianocore:Ravel,_Maurice/Le_Tombeau_de_Couperin,_M.68/{m}"
    for m in ("1._Prelude", "2._Fugue", "3._Forlane", "4._Rigaudon", "5._Menuet", "6._Toccata")
)
_ITALIAN = ("asap:Bach/Italian_concerto", "bach_bwv971")

SCORE_CANDIDATES: dict[str, tuple[tuple[str, ...], str]] = {
    # PianoVAM piece id -> (app-catalogue piece ids, match kind). Title-level only (BL-24).
    # "unit": the title names the same piece or movement as the catalogue score.
    # "ambiguous": movement or number not in the title, or the catalogue unit differs.
    "pianovam:a_scriabin/sonata_no_2": (("scriabin_op19",), "unit"),
    "pianovam:c_debussy/clair_de_lune": (("debussy_l75_mv3",), "unit"),
    "pianovam:debussy/images_3_mouvement": (("debussy_l110_no3",), "unit"),
    "pianovam:e_satie/gymnopedie_no_1": (
        ("pianocore:Satie,_Erik/3_Gymnopédies,_IES_26/1._Lent_et_douloureux",), "unit"),
    "pianovam:f_chopin/ballade_no_1": (("chopin_op23",), "unit"),
    "pianovam:f_chopin/grande_valse_brillante_op_18": (("chopin_op18",), "unit"),
    "pianovam:f_chopin/nocturne_op_9_no_3": (
        ("pianocore:Chopin,_Frédéric/Nocturnes,_Op.9/Nocturne_No.3_in_B_major,_Allegretto",),
        "unit"),
    # title says "Waltz in A, B. 150"; B. 150 is the A minor waltz
    "pianovam:f_chopin/waltz_in_a_b_150": (
        ("pianocore:Chopin,_Frédéric/Waltz_No.19_in_A_minor,_Op.posth.",), "unit"),
    # ASAP's movement is unknown (DATASETS.md); the PianoCoRe score is the whole concerto
    "pianovam:j_s_bach/italian_concerto_mvt_1": (_ITALIAN, "ambiguous"),
    "pianovam:j_s_bach/italian_concerto_mvt_3": (_ITALIAN, "ambiguous"),
    "pianovam:j_s_bach/prelude_i_in_c": (("bach_bwv846_prelude",), "unit"),
    "pianovam:l_beethoven/piano_sonata_no_23_mvt_1": (("beethoven_op57_mv1",), "unit"),
    "pianovam:l_beethoven/piano_sonata_no_23_mvt_3": (("beethoven_op57_mv3",), "unit"),
    "pianovam:l_v_beethoven/fur_elise": (("beethoven_woo59",), "unit"),
    "pianovam:l_v_beethoven/sonata_no_28_mvt_4": (("beethoven_op101_mv4",), "unit"),
    # Op. 36 has six sonatinas; the catalogue has No. 1 (whole and mvt 1) and No. 3
    "pianovam:m_clementi/sonatine_op_36": (
        ("clementi_op36_no1",
         "pianocore:Clementi,_Muzio/Piano_Sonatina_in_C_major,_Op.36,_No.1/1._Spiritoso",
         "clementi_op36_no3"), "ambiguous"),  # fmt: skip
    "pianovam:m_ravel/gaspard_de_la_nuit_ondine": (
        ("pianocore:Ravel,_Maurice/Gaspard_de_la_nuit,_M.55/Ondine",
         "asap:Ravel/Gaspard_de_la_Nuit_1_Ondine"), "unit"),  # fmt: skip
    "pianovam:m_ravel/jeux_d_eau": (("pianocore:Ravel,_Maurice/Jeux_d'eau,_M.30",), "unit"),
    "pianovam:m_ravel/le_tombeau_de_couperin": (_TOMBEAU, "ambiguous"),
    "pianovam:m_ravel/sonatine_mvt_1": (("pianocore:Ravel,_Maurice/Sonatine,_M.40/1._Modéré",),
                                        "unit"),  # fmt: skip
    "pianovam:n_a_mozart/n_a_piano_sonata_no_16_in_c_major_k_545_1st_mvt": (
        ("mozart_k545_mv1",), "unit"),
    "pianovam:w_a_mozart/sonata_k_545": (_K545, "ambiguous"),
    "pianovam:w_a_mozart/sonata_no_15_k_545": (_K545, "ambiguous"),
    "pianovam:w_a_mozart/sonata_k_310": (("mozart_k310_mv1", "mozart_k310_mv3"), "ambiguous"),
    "pianovam:r_schumann/fantasie_op_17": (_OP17, "ambiguous"),
    "pianovam:s_rachmaninoff/etude_tableaux_op_39_no_8": (("rachmaninoff_op39_no8",), "unit"),
    "pianovam:s_rachmaninoff/moment_musicaux_op_16_no_4": (("rachmaninoff_op16_no4",), "unit"),
    "pianovam:s_rachmaninoff/prelude_op_3_no_2": (("rachmaninoff_op3_no2",), "unit"),
    "pianovam:s_rachmaninoff/prelude_op_32_no_10": (("rachmaninoff_op32_no10",), "unit"),
}
