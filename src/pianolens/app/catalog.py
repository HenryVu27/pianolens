"""The piece picker's catalogue: pieces the app can analyse with a score and expert references.

A piece is *supported* when the app has its score and can compare against experts:

* PianoCoRe tier A pieces with at least ``MIN_REFERENCES`` cached performances
  (``pianolens.data.pianocore_cache``). The score is the piece's MusicXML from the PianoCoRe raw
  zip (one per piece), copied on first use to ``<app root>/scores/``. The references are the
  cached tier A performances, as in every F-08 report.
* ASAP pieces (the MusicXML in the ASAP folder, looked up by ``report_from_files``). Their
  reference count is the PianoCoRe count for the same canonical piece id (often 0); the ASAP
  performances are listed too because the report uses them for the per-bar expert check.

Each piece is also checked for piano four hands (DF-11,
:func:`pianolens.report.four_hands.detect_four_hands`, from the score's structure): duets are
marked in the picker and their reports leave out per-hand features.

Building the list reads the PianoCoRe metadata and scans every score's staff layout (a few
seconds), so it is cached as ``<app root>/catalog.json`` and rebuilt when a source file is newer.
"""

from __future__ import annotations

import json
import re
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

__all__ = ["MIN_REFERENCES", "Piece", "build_catalog", "load_catalog", "resolve_score"]

MIN_REFERENCES = 50
CATALOG_VERSION = 2  # 2: four_hands (DF-11)


@dataclass(frozen=True)
class Piece:
    """One entry of the picker."""

    piece_id: str
    composer: str
    title: str
    n_references: int  # PianoCoRe tier A performances used as tier D references
    n_asap: int  # ASAP (Disklavier) performances of the same piece
    source: str  # "pianocore" or "asap": where the score comes from
    score: str  # PianoCoRe raw-zip path (source pianocore) or ASAP-relative MusicXML path
    four_hands: bool = False  # piano duet (DF-11): per-hand features are left out of reports


def _pretty(s: Any) -> str:
    if s is None or (isinstance(s, float) and s != s):
        return ""
    return re.sub(r"\s+", " ", str(s).replace("_", " ")).strip()


def _composer(s: str) -> str:
    """``"Chopin,_Frédéric"`` -> ``"Chopin"`` for display (surname first, as in the data)."""
    return _pretty(s).split(",")[0].strip()


def _sources(pianocore_root: Path, cache_root: Path, asap_root: Path) -> list[Path]:
    return [p for p in (pianocore_root / "metadata.csv", cache_root / "pieces.parquet",
                        asap_root) if p.exists()]  # fmt: skip


def build_catalog(
    pianocore_root: Path | str | None = None,
    cache_root: Path | str | None = None,
    asap_root: Path | str | None = None,
    min_references: int = MIN_REFERENCES,
) -> list[Piece]:
    """All supported pieces, most references first. Missing datasets contribute nothing."""
    from pianolens.data import asap, pianocore, pianocore_cache

    pc_root = Path(pianocore_root or pianocore.DEFAULT_ROOT)
    c_root = Path(cache_root or pianocore_cache.DEFAULT_CACHE)
    a_root = Path(asap_root or asap.DEFAULT_ROOT)
    counts: dict[str, int] = {}
    if pianocore_cache.cache_available(c_root):
        pcs = pianocore_cache.load_pieces(c_root)
        counts = dict(zip(pcs["piece_id"].astype(str), pcs["n_performances"].astype(int),
                          strict=True))  # fmt: skip
    asap_n: dict[str, int] = {}
    out: dict[str, Piece] = {}
    if asap.data_available(a_root):
        idx = asap.asap_index(a_root)
        for pid, g in idx.groupby("piece_id", sort=False):
            asap_n[str(pid)] = len(g)
        for pid, g in idx.groupby("piece_id", sort=False):
            r = g.iloc[0]
            pid = str(pid)
            out[pid] = Piece(pid, _pretty(r["composer"]), _pretty(r["title"]),
                             counts.get(pid, 0), len(g), "asap", str(r["xml_score"]))
    if pianocore.data_available(pc_root):
        md = pianocore.pianocore_index(pc_root, tier="a")
        md = md[md["refined_score_midi_path"].notna() & md["score_xml_path"].notna()]
        first = md.drop_duplicates("piece_id")
        for r in first.itertuples(index=False):
            pid = str(r.piece_id)
            n = counts.get(pid, 0)
            if n < min_references:
                continue
            title = " - ".join(t for t in (_pretty(r.composition), _pretty(r.movement)) if t)
            if pid in out:  # ASAP score kept (it is what find_score uses); nicer title
                out[pid] = Piece(**{**asdict(out[pid]), "n_references": n, "title": title})
                continue
            out[pid] = Piece(pid, _composer(r.composer), title, n, asap_n.get(pid, 0),
                             "pianocore", str(r.score_xml_path))
    pieces = _mark_four_hands(list(out.values()), pc_root, a_root)
    return sorted(pieces, key=lambda p: (-p.n_references, p.composer, p.title))


def _mark_four_hands(pieces: list[Piece], pianocore_root: Path, asap_root: Path) -> list[Piece]:
    """Set ``four_hands`` from each piece's score (DF-11); an unreadable score falls back to the
    known list inside :func:`detect_four_hands`."""
    from pianolens.data import pianocore
    from pianolens.report.four_hands import detect_four_hands

    zf = None
    if any(p.source == "pianocore" for p in pieces) and (pianocore_root /
                                                           pianocore.RAW_ZIP).is_file():
        zf = zipfile.ZipFile(pianocore_root / pianocore.RAW_ZIP)
    out = []
    try:
        for p in pieces:
            src: bytes | Path | None = None
            if p.source == "pianocore" and zf is not None:
                try:
                    src = zf.read(pianocore.RAW_PREFIX + p.score)
                except KeyError:
                    src = None
            elif p.source == "asap":
                src = asap_root / p.score
            fh = detect_four_hands(src, p.piece_id, quick=True).is_four_hands
            out.append(Piece(**{**asdict(p), "four_hands": fh}) if fh else p)
    finally:
        if zf is not None:
            zf.close()
    return out


def load_catalog(app_root: Path | str, **kw: Any) -> list[Piece]:
    """The catalogue, from ``<app_root>/catalog.json`` when it is newer than its sources."""
    from pianolens.data import asap, pianocore, pianocore_cache

    f = Path(app_root) / "catalog.json"
    srcs = _sources(Path(kw.get("pianocore_root") or pianocore.DEFAULT_ROOT),
                    Path(kw.get("cache_root") or pianocore_cache.DEFAULT_CACHE),
                    Path(kw.get("asap_root") or asap.DEFAULT_ROOT))
    if f.is_file() and all(s.stat().st_mtime <= f.stat().st_mtime for s in srcs):
        d = json.loads(f.read_text())
        if d.get("version") == CATALOG_VERSION:
            return [Piece(**p) for p in d["pieces"]]
    pieces = build_catalog(**kw)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps({"version": CATALOG_VERSION,
                             "pieces": [asdict(p) for p in pieces]}))  # fmt: skip
    return pieces


def resolve_score(piece: Piece, app_root: Path | str,
                  pianocore_root: Path | str | None = None) -> Path | None:
    """The score file to pass to ``report_from_files``: None for ASAP pieces (the report looks
    the score up itself), else the PianoCoRe MusicXML copied to ``<app_root>/scores/``."""
    if piece.source != "pianocore":
        return None
    from pianolens.data import pianocore, pianocore_cache

    root = Path(pianocore_root or pianocore.DEFAULT_ROOT)
    suffix = Path(piece.score).suffix or ".mxl"
    dst = Path(app_root) / "scores" / f"{pianocore_cache.piece_slug(piece.piece_id)}{suffix}"
    if not dst.is_file():
        dst.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(root / pianocore.RAW_ZIP) as z:
            data = z.read(pianocore.RAW_PREFIX + piece.score)
        tmp = dst.with_suffix(dst.suffix + ".part")
        tmp.write_bytes(data)
        tmp.replace(dst)
    return dst
