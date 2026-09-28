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
from pianolens.report.build import ReportConfig, ReportInputs, build_report, to_jsonable
from pianolens.report.render import render_html

__all__ = ["find_score", "load_performance", "load_score", "report_from_files", "write_report"]


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
    tk = [align_performance(sc, load_performance(t, provenance, piece_id,
                                                 performance_id=f"take{k + 2}:{Path(t).stem}"))
          for k, t in enumerate(takes)]
    inp = ReportInputs(
        ap=ap, piece_id=piece_id, title=title or (piece_id or Path(score).stem),
        provenance=provenance, source_id=src, references=refs, same_score_refs=same,
        same_score_provenance=reference_provenance, takes=tk, correctness_refs=cref,
        paths={"score": str(score), "performance": str(performance),
               "takes": [str(t) for t in takes], "n_reference_midis": len(reference_midis),
               "excluded_references": excl,
               "correctness_references": [str(p) for p in cref_paths]},
        notes=[*notes, *ref_note])  # fmt: skip
    return build_report(inp, cfg)


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
