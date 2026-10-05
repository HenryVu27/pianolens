"""File loading for the practice report: score and MIDI files in, HTML + JSON out (F-08)."""

from __future__ import annotations

import json
import warnings
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np

from pianolens.align import align_performance, load_score_part
from pianolens.data.midi_io import performance_from_midi
from pianolens.data.types import PerformerId, PieceId, Score, score_from_partitura
from pianolens.report import calibration as cal
from pianolens.report.build import (
    ReportConfig,
    ReportInputs,
    bar_error_table,
    bar_labels,
    build_report,
    to_jsonable,
)
from pianolens.report.render import render_html

__all__ = ["expert_bar_tables", "find_score", "load_performance", "load_score",
           "pianocore_expert_midis", "report_from_files", "write_report"]


def find_score(piece_id: str) -> Path | None:
    """The ASAP MusicXML score of a canonical piece id, if ASAP has it."""
    from pianolens.data import asap

    if not asap.data_available():
        return None
    idx = asap.asap_index()
    rows = idx[idx["piece_id"] == piece_id]
    return Path(asap.DEFAULT_ROOT) / rows.iloc[0]["xml_score"] if len(rows) else None


def load_score(path: Path | str, piece_id: str | None = None) -> Score:
    """A score file (MusicXML, MEI, ...) as a folded ``Score`` with its part kept;
    ``align_performance`` re-reads ``source_path`` and unfolds it to the path played."""
    path = Path(path)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        part = load_score_part(path)
    return score_from_partitura(part, score_id=f"file:{path.stem}",
                                piece_id=PieceId(piece_id or path.stem), source_path=path,
                                keep_part=True)


def load_performance(path: Path | str, provenance: str, piece_id: str | None = None,
                     performance_id: str | None = None) -> Any:
    path = Path(path)
    prov = provenance if provenance in ("disklavier", "transcribed", "sensor",
                                        "synthetic") else "synthetic"
    perf = performance_from_midi(path, dataset="user", performance_id=performance_id or path.stem,
                                 piece_id=PieceId(piece_id or ""),
                                 performer_id=PerformerId("user:unknown"), provenance=prov,
                                 meta={"declared_provenance": provenance})
    return perf


def _same_variant(a: Any, b: Any) -> bool:
    sa, sb = a.score.notes["onset_beat"], b.score.notes["onset_beat"]
    return len(sa) == len(sb) and bool(np.allclose(np.sort(sa), np.sort(sb)))


def report_from_files(
    performance: Path | str,
    *,
    score: Path | str | None = None,
    piece_id: str | None = None,
    provenance: str = "unknown",
    title: str = "",
    takes: Sequence[Path | str] = (),
    reference_midis: Sequence[Path | str] = (),
    reference_provenance: str = "unknown",
    use_pianocore: bool = True,
    exclude_references: Sequence[str] = (),
    config: ReportConfig | None = None,
    notes: Sequence[str] = (),
    correctness_reference_midis: Sequence[Path | str] | None = None,
    max_correctness_references: int = 6,
    expert_check: bool = True,
    expert_tables: Sequence[Any] | None = None,
    expert_check_midis: Sequence[Path | str] | None = None,
    expert_check_provenance: str | None = None,
    expert_capture_model: str | None = None,
    max_expert_checks: int = cal.EXPERT_CHECK_MAX_REFS,
) -> dict[str, Any]:
    """Load, align and analyse. ``score`` or ``piece_id`` (ASAP lookup) must be given.

    ``reference_midis`` are other performances of the same score (e.g. the other Vienna 4x22
    pianists); only those that take the same repeat path as the target are used.
    ``exclude_references``: PianoCoRe performance or source ids to leave out (the target's own
    source, e.g. ``ASAP_SunMeiting08``; derived automatically for files under the ASAP folder).
    ``correctness_reference_midis``: expert performances of the same score, used only to remove
    checker artefacts from errors that recur across ``takes``. None = with takes, up to
    ``max_correctness_references`` ASAP performances of ``piece_id`` (the target's own source
    and ``exclude_references`` left out), if ASAP is available.

    Per-bar expert check (F-08c, ``expert_check``): per-bar error counts of expert performances
    of the same score with the target's capture method. ``expert_tables`` (precomputed,
    :func:`expert_bar_tables`) or ``expert_check_midis`` (aligned here, capture method
    ``expert_check_provenance``); by default, for transcribed input up to ``max_expert_checks``
    PianoCoRe transcriptions of ``piece_id`` (``expert_capture_model``, e.g. ``"Transkun V2"``,
    restricts them to one transcriber, as in the A-01 floor), otherwise up to
    ``max_expert_checks`` ASAP (Disklavier) performances of ``piece_id``. ``reference_midis`` of
    the same capture class (transcribed or key-sensor) are used instead when there are at least
    ``calibration.EXPERT_CHECK_MIN_REFS`` of them on the target's repeat path.
    """
    cfg = config or ReportConfig()
    performance = Path(performance)
    if score is None:
        if piece_id is None:
            raise ValueError("give a score file or a piece id")
        score = find_score(piece_id)
        if score is None:
            raise FileNotFoundError(f"no score for piece {piece_id!r} in ASAP; pass --score")
    sc = load_score(score, piece_id)
    perf = load_performance(performance, provenance, piece_id)
    ap = align_performance(sc, perf)
    src = ""
    parts = performance.resolve().parts
    if "asap" in parts:
        src = f"ASAP_{performance.stem}"
    excl = [*exclude_references, *([src] if src else [])]

    refs = None
    ref_note = []
    if use_pianocore and piece_id:
        try:
            from pianolens.data import pianocore_cache as pc
            from pianolens.features.interpretation import load_pianocore_references

            if pc.cache_available():
                refs = load_pianocore_references(piece_id, exclude=excl,
                                                 config=cfg.interpretation)
                if not len(refs):
                    refs = None
        except Exception as e:  # noqa: BLE001 - no references is a valid report
            ref_note.append(f"PianoCoRe references could not be loaded ({e!r}).")
    same, skipped = [], 0
    for m in reference_midis:
        m = Path(m)
        if m.resolve() == performance.resolve():
            continue
        rp = load_performance(m, reference_provenance, piece_id)
        rap = align_performance(sc, rp)
        if _same_variant(rap, ap):
            rap.score = ap.score  # identical notes; share the target's score object
            same.append(rap)
        else:
            skipped += 1
    if skipped:
        ref_note.append(f"{skipped} same-score reference(s) took another repeat path and were "
                        "not used.")
    cref_paths: list[Path] = []
    if correctness_reference_midis is not None:
        cref_paths = [Path(m) for m in correctness_reference_midis]
    elif takes and piece_id:
        cref_paths = _asap_performances(piece_id, excl, max_correctness_references)
    cref = []
    for m in cref_paths:
        if m.resolve() == performance.resolve():
            continue
        try:
            rap = align_performance(sc, load_performance(m, "disklavier", piece_id))
        except Exception as e:  # noqa: BLE001 - an expert that fails to align is skipped
            ref_note.append(f"Correctness reference {m.name} could not be aligned ({e!r}).")
            continue
        if _same_variant(rap, ap):
            cref.append(rap)
    xtabs: list[Any] = []
    xprov = expert_check_provenance or ("transcribed" if provenance == "transcribed"
                                        else "disklavier")
    if expert_check:
        if expert_tables is not None:
            xtabs = list(expert_tables)
        else:
            xpaths: list[Path] = []
            tmp = None
            same_ok = [r for r in same if _capture_class(reference_provenance)
                       == _capture_class(provenance)]
            if expert_check_midis is not None:
                xpaths = [Path(m) for m in expert_check_midis]
            elif len(same_ok) >= cal.EXPERT_CHECK_MIN_REFS:
                from pianolens.features.correctness import correctness

                for r in same_ok:  # already aligned to the same performed score
                    cr = correctness(r)
                    if not cr.summary.get("alignment_suspect"):
                        xtabs.append(bar_error_table(cr, bar_labels(r.score)))
                xprov = expert_check_provenance or reference_provenance
            elif piece_id and xprov == "transcribed":
                import tempfile

                tmp = tempfile.TemporaryDirectory()
                for rid, data in pianocore_expert_midis(piece_id, expert_capture_model,
                                                        max_expert_checks, exclude=excl):
                    f = Path(tmp.name) / f"{rid}.mid"
                    f.write_bytes(data)
                    xpaths.append(f)
            elif piece_id:
                xpaths = _asap_performances(piece_id, excl, max_expert_checks)
            if xpaths:
                xtabs, xnote = expert_bar_tables(sc, xpaths, xprov, piece_id, skip=performance)
                ref_note.extend(xnote)
            if tmp is not None:
                tmp.cleanup()
    tk = [align_performance(sc, load_performance(t, provenance, piece_id,
                                                 performance_id=f"take{k + 2}:{Path(t).stem}"))
          for k, t in enumerate(takes)]
    inp = ReportInputs(
        ap=ap, piece_id=piece_id, title=title or (piece_id or Path(score).stem),
        provenance=provenance, source_id=src, references=refs, same_score_refs=same,
        same_score_provenance=reference_provenance, takes=tk, correctness_refs=cref,
        expert_bar_tables=xtabs, expert_bar_provenance=xprov, transcriber=expert_capture_model,
        paths={"score": str(score), "performance": str(performance),
               "takes": [str(t) for t in takes], "n_reference_midis": len(reference_midis),
               "excluded_references": excl,
               "correctness_references": [str(p) for p in cref_paths]},
        notes=[*notes, *ref_note])  # fmt: skip
    return build_report(inp, cfg)


def _capture_class(provenance: str) -> str:
    """Transcribed MIDI and key-sensor MIDI are checked only against their own kind (A-01)."""
    return "transcribed" if provenance == "transcribed" else "key"


def expert_bar_tables(score: Score, midis: Sequence[Path | str], provenance: str,
                      piece_id: str | None = None, skip: Path | str | None = None
                      ) -> tuple[list[Any], list[str]]:
    """Align expert performances to ``score`` and return their per-bar error tables
    (:func:`pianolens.report.build.bar_error_table`) and notes on the ones left out.
    Performances whose alignment is suspect (match ratio below 0.8) are left out, as in the A-01
    floor."""
    from pianolens.features.correctness import correctness

    tabs, notes, bad = [], [], 0
    for m in midis:
        m = Path(m)
        if skip is not None and m.resolve() == Path(skip).resolve():
            continue
        try:
            rap = align_performance(score, load_performance(m, provenance, piece_id))
            cr = correctness(rap)
        except Exception as e:  # noqa: BLE001 - an expert that fails to align is skipped
            notes.append(f"Expert check: {m.name} could not be aligned ({e!r}).")
            continue
        if cr.summary.get("alignment_suspect"):
            bad += 1
            continue
        tabs.append(bar_error_table(cr, bar_labels(rap.score)))
    if bad:
        notes.append(f"Expert check: {bad} expert performance(s) with a suspect alignment were "
                     "left out.")
    return tabs, notes


def pianocore_expert_midis(piece_id: str, capture_model: str | None = None, n: int = 15,
                           seed: int = 0, exclude: Sequence[str] = ()
                           ) -> list[tuple[str, bytes]]:
    """Up to ``n`` raw PianoCoRe tier A transcriptions of a piece (seeded draw), as
    ``(id, MIDI bytes)``. ``capture_model`` (e.g. ``"Transkun V2"``, ``"Aria-AMT"``) restricts
    them to one transcriber; otherwise any transcription. Ids or performance ids in ``exclude``
    are left out."""
    import zipfile

    from pianolens.data import pianocore as pcm

    if not pcm.data_available():
        return []
    idx = pcm.PianoCoRe().index
    rows = idx[(idx["piece_id"] == piece_id) & idx["is_transcription"].astype(bool)]
    if capture_model:
        rows = rows[rows["capture_model"] == capture_model]
    ex = set(exclude)
    rows = rows[~rows["id"].isin(ex) & ~rows["performance_id"].isin(ex)].sort_values("id")
    if not len(rows):
        return []
    pick = np.sort(np.random.default_rng(seed).choice(len(rows), size=min(n, len(rows)),
                                                      replace=False))
    out = []
    with zipfile.ZipFile(pcm.DEFAULT_ROOT / pcm.RAW_ZIP) as z:
        for i in pick:
            r = rows.iloc[int(i)]
            out.append((str(r["id"]), z.read(pcm.RAW_PREFIX + str(r["performance_midi_path"]))))
    return out


def _asap_performances(piece_id: str, exclude: Sequence[str], k: int) -> list[Path]:
    """Up to ``k`` ASAP performance MIDIs of a piece (file stems in ``exclude`` or
    ``ASAP_<stem>`` left out), in a fixed order."""
    from pianolens.data import asap

    if not asap.data_available():
        return []
    idx = asap.asap_index()
    rows = idx[idx["piece_id"] == piece_id].sort_values("midi_performance")
    ex = set(exclude)
    out = []
    for m in rows["midi_performance"]:
        p = Path(asap.DEFAULT_ROOT) / m
        if p.stem in ex or f"ASAP_{p.stem}" in ex:
            continue
        out.append(p)
    return out[:k]


def write_report(rep: dict[str, Any], out_html: Path | str) -> tuple[Path, Path]:
    """Write ``<name>.html`` and ``<name>.json`` side by side."""
    out_html = Path(out_html)
    out_html.parent.mkdir(parents=True, exist_ok=True)
    data = to_jsonable(rep)
    out_json = out_html.with_suffix(".json")
    out_json.write_text(json.dumps(data, indent=1, allow_nan=False))
    out_html.write_text(render_html(data, out_html.parent))
    return out_html, out_json
