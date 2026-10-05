"""BL-19: how often score staff may differ from the playing hand, from score-only proxies.

Run::

    uv run python scripts/staff_hand_proxies.py [--workers 12] [--limit N]

Pre-registration: ``docs/specs/correctness-validation.md``, section "Pre-registration BL-19"
(copy and sha256 in ``experiments/2026-09-29-BL-19-staff-hand/artifacts/``).

Repertoire: the app catalogue ``data/interim/app/catalog.json`` (ASAP scores and PianoCoRe
tier A scores with >= 50 references). Each score is loaded folded, parts merged
(``pianolens.align.load_score_part``); grace notes are excluded; tied notes are merged by
partitura. Per note (see :func:`note_flags`):

* P1 ``cross_voice``: staff differs from the most common staff of the note's MusicXML voice.
* P2 ``cross_pitch`` (strict): an upper-staff note below every lower-staff note sounding at its
  onset, or a lower-staff note above every upper-staff note sounding at its onset.
  ``cross_pitch_loose``: below the highest / above the lowest.
* P3 ``capacity``: the notes of one staff starting together number more than 5
  (``capacity_count``) or span more than 16 semitones (``capacity_span``).
* ``at_risk`` = P1 or P2 strict or P3.

Hand-sync events (:func:`hand_sync_events`): onsets where staff 1 and staff 2 both start a
non-grace note, as ``pianolens.features.control.hand_synchrony`` pairs them (from the score
alone). Hand words (m.d., m.s., l.h., ...) are read from the MusicXML directions with their
staff (:func:`hand_words`).

Outputs (``--out``, default the experiment's ``artifacts/``, gitignored): ``per_piece.csv``,
``per_composer.csv``, ``hand_words.csv``, ``summary.json``.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import tempfile
import time
import warnings
import xml.etree.ElementTree as ET
import zipfile
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd

log = logging.getLogger("staff_hand_proxies")

MAX_NOTES_ONE_HAND = 5
MAX_SPAN_ONE_HAND = 16  # semitones: a major tenth
DEFAULT_OUT = Path("experiments/2026-09-29-BL-19-staff-hand/artifacts")
CATALOG = Path("data/interim/app/catalog.json")
SEED = 20260929

_LH = re.compile(r"^(m\.?\s?s\.?|m\.?\s?g\.?|l\.?\s?h\.?|g\.|sin\.?|mano\s+sinistra|"
                 r"main\s+gauche|linke(\s+hand)?|left\s+hand|l\.\s?m\.?)$")  # fmt: skip
_RH = re.compile(r"^(m\.?\s?d\.?|r\.?\s?h\.?|d\.|dest\.?|mano\s+destra|main\s+droite|"
                 r"rechte(\s+hand)?|right\s+hand|r\.\s?m\.?)$")  # fmt: skip
_CROSS = re.compile(r"^(sopra|sotto|dessus|dessous)\.?$")  # not "sotto voce"


# --------------------------------------------------------------------------- proxies


def note_flags(df: pd.DataFrame) -> pd.DataFrame:
    """Proxy flags per note.

    ``df`` columns: ``onset`` and ``duration`` (score quarters), ``pitch``, ``voice``,
    ``staff``. Grace notes must already be removed. Returns a copy with boolean columns
    ``cross_voice``, ``cross_pitch``, ``cross_pitch_loose``, ``capacity_count``,
    ``capacity_span``, ``capacity`` and ``at_risk``. Only staves 1 and 2 are compared; notes on
    other staves get False everywhere.
    """
    d = df.reset_index(drop=True).copy()
    n = len(d)
    for c in ("cross_voice", "cross_pitch", "cross_pitch_loose", "capacity_count",
              "capacity_span", "capacity", "at_risk"):  # fmt: skip
        d[c] = False
    if n == 0:
        return d
    s12 = d["staff"].isin([1, 2]).to_numpy()
    # P1: staff differs from the voice's most common staff
    modal = (d[s12].groupby("voice")["staff"]
             .agg(lambda s: s.value_counts().sort_index().idxmax()))  # fmt: skip
    d.loc[s12, "cross_voice"] = (d.loc[s12, "staff"].to_numpy()
                                 != d.loc[s12, "voice"].map(modal).to_numpy())  # fmt: skip
    # P2: pitch crossing against the other staff's notes sounding at the onset
    on = d["onset"].to_numpy(float)
    off = on + np.maximum(d["duration"].to_numpy(float), 0.0)
    p = d["pitch"].to_numpy(int)
    st = d["staff"].to_numpy(int)
    strict = np.zeros(n, bool)
    loose = np.zeros(n, bool)
    order = np.argsort(on, kind="stable")
    uniq, start = np.unique(on[order], return_index=True)
    bounds = list(start) + [n]
    for k, t in enumerate(uniq):
        idx = order[bounds[k]: bounds[k + 1]]
        sounding = (on <= t) & ((off > t) | (on == t))
        up = sounding & (st == 1)
        lo = sounding & (st == 2)
        if not up.any() or not lo.any():
            continue
        up_min, up_max = p[up].min(), p[up].max()
        lo_min, lo_max = p[lo].min(), p[lo].max()
        for i in idx:
            if st[i] == 1:
                strict[i] = p[i] < lo_min
                loose[i] = p[i] < lo_max
            elif st[i] == 2:
                strict[i] = p[i] > up_max
                loose[i] = p[i] > up_min
    d["cross_pitch"] = strict
    d["cross_pitch_loose"] = loose
    # P3: one-hand capacity per (onset, staff)
    g = d[s12].groupby(["onset", "staff"])["pitch"]
    cnt = g.transform("nunique")
    span = g.transform(lambda s: s.max() - s.min())
    d.loc[s12, "capacity_count"] = (cnt > MAX_NOTES_ONE_HAND).to_numpy()
    d.loc[s12, "capacity_span"] = (span > MAX_SPAN_ONE_HAND).to_numpy()
    d["capacity"] = d["capacity_count"] | d["capacity_span"]
    d["at_risk"] = d["cross_voice"] | d["cross_pitch"] | d["capacity"]
    return d


def hand_sync_events(flags: pd.DataFrame) -> pd.DataFrame:
    """Score onsets where staff 1 and staff 2 both start a note, with proxy flags per event.

    Returns one row per event: ``onset`` and, for each flag column, whether any note of the
    event (staff 1 or 2) carries it.
    """
    f = flags[flags["staff"].isin([1, 2])]
    cols = ["cross_voice", "cross_pitch", "cross_pitch_loose", "capacity", "at_risk"]
    both = f.groupby("onset")["staff"].nunique()
    ev = both.index[both.to_numpy() == 2]
    g = f[f["onset"].isin(ev)].groupby("onset")[cols].any()
    return g.reset_index()


# --------------------------------------------------------------------------- hand words


def _xml_root(path: Path) -> ET.Element:
    if path.suffix == ".mxl":
        with zipfile.ZipFile(path) as z:
            names = z.namelist()
            rootfile = None
            if "META-INF/container.xml" in names:
                c = ET.fromstring(z.read("META-INF/container.xml"))
                for el in c.iter():
                    if el.tag.endswith("rootfile") and el.get("full-path"):
                        rootfile = el.get("full-path")
                        break
            if rootfile is None:
                rootfile = next(n for n in names if n.endswith(".xml")
                                and not n.startswith("META-INF"))  # fmt: skip
            return ET.fromstring(z.read(rootfile))
    return ET.parse(path).getroot()


def classify_words(text: str) -> str | None:
    """``"LH"``, ``"RH"``, ``"cross"`` or None for a direction text."""
    t = " ".join(text.strip().lower().split()).rstrip(":;,")
    if not t:
        return None
    if _LH.match(t):
        return "LH"
    if _RH.match(t):
        return "RH"
    if _CROSS.match(t):
        return "cross"
    return None


def hand_words(path: Path) -> list[dict]:
    """Hand directions in a MusicXML file: one dict per ``<words>`` that names a hand or a
    crossing (sopra / sotto), with its global staff (parts numbered consecutively) and the
    measure number. ``contradicts`` is True for a left-hand word on staff 1 or a right-hand word
    on staff 2."""
    root = _xml_root(path)
    out = []
    offset = 0
    for part in root.iter("part"):
        n_staves = 1
        for st in part.iter("staves"):
            n_staves = max(n_staves, int(st.text or 1))
        for meas in part.iter("measure"):
            for direc in meas.iter("direction"):
                staff_el = direc.find("staff")
                staff = offset + int(staff_el.text) if staff_el is not None else None
                for w in direc.iter("words"):
                    kind = classify_words(w.text or "")
                    if kind is None:
                        continue
                    out.append({"text": (w.text or "").strip(), "kind": kind, "staff": staff,
                                "measure": meas.get("number"),
                                "contradicts": (kind == "LH" and staff == 1)
                                or (kind == "RH" and staff == 2)})  # fmt: skip
        offset += n_staves
    return out


# --------------------------------------------------------------------------- per piece


def _score_path(piece: dict, tmpdir: Path) -> Path:
    if piece["source"] == "asap":
        return Path("data/raw/asap") / piece["score"]
    from pianolens.data import pianocore

    suffix = Path(piece["score"]).suffix or ".mxl"
    dst = tmpdir / (re.sub(r"[^A-Za-z0-9]+", "_", piece["piece_id"])[-120:] + suffix)
    if not dst.is_file():
        with zipfile.ZipFile(pianocore.DEFAULT_ROOT / pianocore.RAW_ZIP) as z:
            dst.write_bytes(z.read(pianocore.RAW_PREFIX + piece["score"]))
    if dst.suffix == ".mxl" and not zipfile.is_zipfile(dst):  # a few .mxl files are plain XML
        dst = dst.rename(dst.with_suffix(".musicxml"))
    return dst


def run_piece(piece: dict) -> tuple[dict, list[dict]]:
    import partitura as pt

    from pianolens.align import load_score_part

    warnings.filterwarnings("ignore")
    with tempfile.TemporaryDirectory() as td:
        path = _score_path(piece, Path(td))
        n_parts = len(pt.load_score(str(path)).parts)
        part = load_score_part(path)
        na = part.note_array(include_staff=True, include_grace_notes=True)
        words = hand_words(path)
    df = pd.DataFrame({
        "onset": na["onset_quarter"].astype(float),
        "duration": na["duration_quarter"].astype(float),
        "pitch": na["pitch"].astype(int),
        "voice": na["voice"].astype(int),
        "staff": na["staff"].astype(int),
        "is_grace": na["is_grace"].astype(bool),
    })  # fmt: skip
    n_grace = int(df["is_grace"].sum())
    df = df[~df["is_grace"]].drop(columns="is_grace")
    fl = note_flags(df)
    ev = hand_sync_events(fl)
    s12 = fl["staff"].isin([1, 2])
    n12 = int(s12.sum())
    bars = part.measures
    bar_start = np.array([part.quarter_map(m.start.t) for m in bars], float) if bars else None
    row = {
        "piece_id": piece["piece_id"], "source": piece["source"],
        "composer": piece["composer"], "title": piece["title"], "score": piece["score"],
        "n_parts": n_parts, "n_notes": len(fl), "n_grace": n_grace, "n_notes_staff12": n12,
        "n_notes_other_staff": int((~s12).sum()), "n_staves": int(fl["staff"].nunique()),
        "n_events": len(ev), "n_hand_words": len(words),
        "n_hand_words_lh_rh": sum(w["kind"] in ("LH", "RH") for w in words),
        "n_hand_words_contradicting": sum(bool(w["contradicts"]) for w in words),
        "n_cross_words": sum(w["kind"] == "cross" for w in words),
        "n_bars": len(bars),
    }  # fmt: skip
    for c in ("cross_voice", "cross_pitch", "cross_pitch_loose", "capacity_count",
              "capacity_span", "capacity", "at_risk"):  # fmt: skip
        row[f"n_{c}"] = int(fl.loc[s12, c].sum())
    for c in ("cross_voice", "cross_pitch", "cross_pitch_loose", "capacity", "at_risk"):
        row[f"ev_{c}"] = int(ev[c].sum()) if len(ev) else 0
    if bar_start is not None and len(bar_start):
        b = np.searchsorted(bar_start, fl.loc[fl["cross_pitch"], "onset"].to_numpy(),
                            side="right") - 1  # fmt: skip
        row["n_bars_cross_pitch"] = int(len(np.unique(b[b >= 0])))
        b = np.searchsorted(bar_start, fl.loc[fl["at_risk"], "onset"].to_numpy(),
                            side="right") - 1  # fmt: skip
        row["n_bars_at_risk"] = int(len(np.unique(b[b >= 0])))
    for w in words:
        w.update(piece_id=piece["piece_id"], source=piece["source"],
                 composer=piece["composer"])  # fmt: skip
    return row, words


# --------------------------------------------------------------------------- summary


def _share(num: pd.Series, den: pd.Series) -> pd.Series:
    return num / den.where(den > 0)


def summarise(pp: pd.DataFrame, out: Path) -> dict:
    ok = pp[pp["n_notes_staff12"] > 0].copy()
    props = ("cross_voice", "cross_pitch", "cross_pitch_loose", "capacity", "at_risk")
    for c in props:
        ok[f"note_share_{c}"] = _share(ok[f"n_{c}"], ok["n_notes_staff12"])
        ok[f"event_share_{c}"] = _share(ok[f"ev_{c}"], ok["n_events"])
    ok.to_csv(out / "per_piece.csv", index=False)
    rows = []
    for (src, comp), g in list(ok.groupby(["source", "composer"])) + [
            (("all", "ALL"), ok)] + [((s, "ALL"), g) for s, g in ok.groupby("source")]:
        r = {"source": src, "composer": comp, "n_pieces": len(g),
             "n_notes": int(g["n_notes_staff12"].sum()), "n_events": int(g["n_events"].sum())}
        for c in props:
            r[f"notes_{c}"] = g[f"n_{c}"].sum() / max(1, g["n_notes_staff12"].sum())
            r[f"events_{c}"] = g[f"ev_{c}"].sum() / max(1, g["n_events"].sum())
        r["median_piece_events_at_risk"] = float(g["event_share_at_risk"].median())
        r["median_piece_notes_at_risk"] = float(g["note_share_at_risk"].median())
        r["pieces_events_at_risk_gt20"] = float((g["event_share_at_risk"] > 0.20).mean())
        r["pieces_with_hand_words"] = int((g["n_hand_words_lh_rh"] > 0).sum())
        r["pieces_with_contradicting_words"] = int((g["n_hand_words_contradicting"] > 0).sum())
        rows.append(r)
    pc = pd.DataFrame(rows)
    pc.to_csv(out / "per_composer.csv", index=False)
    # bootstrap by piece for the corpus-level shares (pooled) and the median piece
    rng = np.random.default_rng(SEED)
    boot = {"pooled_events_at_risk": [], "median_piece_events_at_risk": [],
            "pooled_notes_at_risk": []}  # fmt: skip
    for _ in range(2000):
        g = ok.iloc[rng.integers(0, len(ok), len(ok))]
        boot["pooled_events_at_risk"].append(g["ev_at_risk"].sum() / g["n_events"].sum())
        boot["median_piece_events_at_risk"].append(g["event_share_at_risk"].median())
        boot["pooled_notes_at_risk"].append(g["n_at_risk"].sum() / g["n_notes_staff12"].sum())
    ci = {k: [float(x) for x in np.nanpercentile(v, [2.5, 97.5])] for k, v in boot.items()}
    allrow = pc[(pc["source"] == "all")].iloc[0].to_dict()
    concern = (allrow["median_piece_events_at_risk"] > 0.05
               or allrow["pieces_events_at_risk_gt20"] > 0.10)
    res = {"n_pieces": len(ok), "n_failed_or_empty": int(len(pp) - len(ok)),
           "all": allrow, "bootstrap_ci_by_piece": ci,
           "verdict_rule": "concern" if concern else "pass"}  # fmt: skip
    (out / "summary.json").write_text(json.dumps(res, indent=2, default=float))
    return res


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    a.out.mkdir(parents=True, exist_ok=True)
    pieces = json.loads(CATALOG.read_text())["pieces"]
    if a.limit:
        pieces = pieces[: a.limit]
    t0 = time.time()
    rows, words, failed = [], [], []
    with ProcessPoolExecutor(a.workers) as ex:
        futs = {ex.submit(run_piece, p): p["piece_id"] for p in pieces}
        for n, f in enumerate(as_completed(futs), 1):
            try:
                r, w = f.result()
                rows.append(r)
                words.extend(w)
            except Exception as e:  # noqa: BLE001 - count and continue
                failed.append((futs[f], repr(e)[:200]))
            if n % 100 == 0:
                log.info("%d / %d (%.0f s)", n, len(futs), time.time() - t0)
    pp = pd.DataFrame(rows)
    pd.DataFrame(words).to_csv(a.out / "hand_words.csv", index=False)
    pd.DataFrame(failed, columns=["piece_id", "error"]).to_csv(a.out / "failed.csv", index=False)
    log.info("failed: %d %s", len(failed), failed[:3])
    res = summarise(pp, a.out)
    log.info("%s", json.dumps(res, indent=1, default=float)[:3000])
    log.info("done in %.0f s", time.time() - t0)


if __name__ == "__main__":
    main()
