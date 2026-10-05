"""DF-02: build the per-piece LLM phrase cache with the validated R-08 protocol.

    uv run python scripts/build_llm_phrases.py render --henry --out <folder outside the repo>
    # launch blind annotators on <out>/run_A and <out>/run_B (prompt in <work>/prompt.txt)
    uv run python scripts/build_llm_phrases.py ingest --henry --ann <out> --agents <json>

Protocol (so the boundaries are produced the same way as in R-08d, the Romantic validation that
F-05e measured):

* **Rendering:** R-08a's ``common.render`` (imported, unchanged) of the maximally unfolded score,
  part kept. As in R-08d, every printed text item that hits the identity check (composer, title,
  catalogue and corpus words: R-08d's list and title words, plus the title words of the pieces
  being built) is removed from the part before rendering, and each removal is recorded.
  ``tempo`` and ``major`` are added to R-08d's generic-word list (they occur in the piece ids
  here but also in ordinary score text such as "a tempo"; disclosed in the build record).
* **Leakage check:** R-08a's banned annotation vocabulary and Roman numerals, the identity check,
  and stray ids of earlier runs, on every rendering and on INSTRUCTIONS.md / SCHEMA.json; the check
  must fire on planted cues. The build stops if it fails.
* **Instructions and schema:** R-08d's files (no period phrase, worked example at bars 4 / 7),
  ids ``R`` -> ``P``.
* **Annotators:** two runs (A, B), one fresh blind annotator per piece per run, prompt =
  R-08d's template with the folder and id replaced (``PROMPT``). The annotators see only their
  run folder. Their JSON is copied verbatim to ``<work>/annotations/<run>/P#.json`` at ingest.
* **Mapping:** R-08a's ``score.map_events`` (imported, unchanged: onset snapping within half a
  beat, propagation to pointer bars), then phrase starts and ends per run, as F-05e used them.

``<work>`` is ``data/interim/phrases_llm/_build`` (gitignored): the id key, bar tables, rendering
copies, removals and the leakage check output. The cache files go to
``data/interim/phrases_llm/`` (:mod:`pianolens.features.phrases_llm`).
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import logging
import re
import shutil
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
EXP = ROOT / "experiments"
R08A = EXP / "2026-09-28-R-08a-llm-phrase-pilot"
R08D = EXP / "2026-09-28-R-08d-llm-romantic-repertoire"
HENRY_SCORES = ROOT / "data" / "interim" / "henry_takes" / "scores"
warnings.filterwarnings("ignore")
logging.disable(logging.WARNING)
sys.path.insert(0, str(R08A))
sys.path.insert(0, str(ROOT / "scripts"))


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


B8D = _load("r08d_build", R08D / "build.py")  # identity list, R-08a vocabulary, renderer
C = B8D.C  # R-08a common (render, bar table, parse_beat)
S8A = _load("r08a_score", R08A / "score.py")  # map_events

from pianolens.features.phrases_llm import (  # noqa: E402
    anchors,
    default_root,
    edition_hash,
    score_hash,
    write_cache,
)

WORK = default_root() / "_build"
SEED = 20260929
MODEL = "claude-opus-5-5"
RUNS = ("A", "B")
PROTOCOL = ("R-08 (R-08a renderer and mapping, R-08d instructions without a period cue, blind "
            "in-session general-purpose annotators, one per piece per run, 2 runs); F-05e "
            "measure use: raw phrase starts per run")
EXTRA_STOP = {"tempo", "major"}
COMPOSER_STYLE = {"chopin": "romantic", "schumann": "romantic", "liszt": "romantic",
                  "grieg": "romantic", "tchaikovsky": "romantic", "brahms": "romantic",
                  "mendelssohn": "romantic", "schubert": "romantic", "mozart": "classical",
                  "haydn": "classical", "clementi": "classical"}  # fmt: skip
OLD_IDS = re.compile(r"\b[MQR][1-9]\b")  # D1..D5 / P-ids are checked separately
PROMPT = (
    "You are a music-theory annotator. Your whole world for this task is the folder {folder}/ . "
    "Read ONLY these files there: INSTRUCTIONS.md, SCHEMA.json and {mid}.txt. Do not open, list "
    "or search any other file or folder on the computer, do not use the web, and do not use any "
    "tool other than reading those three files and writing your output. The instructions "
    "mention five movements; you are assigned ONLY {mid}. Follow INSTRUCTIONS.md exactly: one "
    "pass, annotate from the rendering, name the piece in recognised_piece if you recognise it "
    "(but do not annotate from remembered analyses). Write your answer as valid JSON conforming "
    "to SCHEMA.json to out/{mid}.json in that folder. Then reply with: the number of events by "
    "type and cadence, whether you recognised the piece, and any difficulties with the format.")


# --------------------------------------------------------------------------- pieces


def henry_pieces() -> list[dict]:
    meta = json.loads((HENRY_SCORES / "scores.json").read_text())
    return [{"piece_id": v["piece_id"], "score": str(HENRY_SCORES / f"{k}_score.mxl")}
            for k, v in sorted(meta.items())]


def style_of(piece_id: str) -> str:
    low = piece_id.lower()
    hits = {s for c, s in COMPOSER_STYLE.items() if c in low}
    return hits.pop() if len(hits) == 1 else "unknown"


def title_words(pieces: list[dict]) -> list[str]:
    words: set[str] = set()
    for p in pieces:
        words |= {w.lower() for w in re.findall(r"[^\W\d_]{4,}", p["piece_id"])}
    return sorted(words - B8D.TITLE_STOP - EXTRA_STOP)


def identity_hits(text: str, titles: list[str]) -> list[str]:
    out = B8D.identity_hits(text)
    out += [w for w in titles if re.search(r"(?<![^\W\d_])" + re.escape(w) + r"(?![^\W\d_])",
                                          text, re.I)]
    return out


def unfolded_score(path: str, piece_id: str):
    """The maximally unfolded score with its part (ids with repeat suffix, as in alignment)."""
    from pianolens.align.core import _variants_with_paths, unfold_variant
    from pianolens.data.types import score_from_partitura
    from pianolens.report.io import load_score

    sc = load_score(path, piece_id)
    variants = _variants_with_paths(sc.part)
    best = max(variants, key=lambda v: v[1])[0] if len(variants) > 1 else None
    upart = unfold_variant(sc.part, best)
    return score_from_partitura(upart, score_id=sc.score_id, piece_id=sc.piece_id,
                                source_path=sc.source_path, meta={**sc.meta, "unfolded": best},
                                keep_part=True)


TEMPO_PRIMO = re.compile(r"^\s*temp(o|\.)\s*(I|Ⅰ)\.?\s*$", re.I)


def strip_identity(score, titles: list[str]) -> list[dict]:
    """R-08d identity rule: remove every printed text item that hits the identity check.
    D-13's normalisation first: "Tempo I" is printed "Tempo primo" (R-08a's Roman-numeral check
    would read it as a label)."""
    import partitura as pt

    part = score.part
    removed, seen = [], set()
    for cls in (pt.score.Words, pt.score.Direction):
        for d in list(part.iter_all(cls, include_subclasses=True)):
            if id(d) in seen:
                continue
            seen.add(id(d))
            txt = str(getattr(d, "text", "") or "").strip()
            if TEMPO_PRIMO.match(txt):
                d.text = txt = "Tempo primo"
            h = identity_hits(txt, titles) if txt else []
            if h:
                removed.append({"text": txt, "hits": h, "t": int(d.start.t)})
                part.remove(d)
    return removed


def check_text(text: str, titles: list[str], ids_ok: set[str]) -> dict[str, list[str]]:
    return {"banned": [w for w in B8D.R8.BANNED_WORDS if re.search(w, text, re.I)],
            "roman": sorted({m.group(0) for m in B8D.R8.ROMAN.finditer(text)}),
            "identity": identity_hits(text, titles),
            "old_ids": sorted(set(OLD_IDS.findall(text))),
            "other_p_ids": sorted(set(re.findall(r"\bP[1-9]\b", text)) - ids_ok)}


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


# --------------------------------------------------------------------------- render


def render(pieces: list[dict], out: Path) -> bool:
    WORK.mkdir(parents=True, exist_ok=True)
    blind = WORK / "blind_input"
    blind.mkdir(exist_ok=True)
    rng = np.random.default_rng(SEED)
    order = rng.permutation(len(pieces))
    titles = title_words(pieces)
    key, removed_all, log = {}, {}, []
    for j, i in enumerate(order):
        p, mid = pieces[int(i)], f"P{j + 1}"
        score = unfolded_score(p["score"], p["piece_id"])
        removed = strip_identity(score, titles)
        r = C.render(score, mid)
        (blind / f"{mid}.txt").write_text(r.text)
        r.bars.to_csv(WORK / f"bars_{mid}.csv", index=False)
        ts = sorted(set(r.bars["ts"]))
        key[mid] = {**p, "score_sha256": sha(Path(p["score"])), "score_hash": score_hash(score),
                    "edition_hash": edition_hash(score), "unfolded": score.meta.get("unfolded"),
                    "meters": ts, "style": style_of(p["piece_id"]),
                    "rendering_sha256": sha(blind / f"{mid}.txt"),
                    "bars": len(r.bars), "pointer_bars": r.n_pointer_bars,
                    "chars": len(r.text)}  # fmt: skip
        removed_all[mid] = removed
        log.append(f"{mid}: {len(r.bars)} bars, {r.n_pointer_bars} pointer bars, "
                   f"{len(r.text):,} chars, meters {ts}, {len(removed)} text items removed")
    # instructions and schema: R-08d's, R -> P
    t = (R08D / "blind_input" / "INSTRUCTIONS.md").read_text()
    for a, b in (("(`R1.txt` to `R5.txt`)", "(`P1.txt` to `P5.txt`)"),
                 ("`R1.txt`..`R5.txt`", "`P1.txt`..`P5.txt`"),
                 ("`R1.json` .. `R5.json`", "`P1.json` .. `P5.json`"),
                 ('"movement": "R1"', '"movement": "P1"')):
        assert t.count(a) == 1, a
        t = t.replace(a, b)
    assert not re.search(r"\bR\d\b", t)
    if len(pieces) != 5:
        t = t.replace("five text renderings", f"{len(pieces)} text renderings")
        t = t.replace("five movements", f"{len(pieces)} movements")
    (blind / "INSTRUCTIONS.md").write_text(t)
    sch = json.loads((R08D / "blind_input" / "SCHEMA.json").read_text())
    sch["properties"]["movement"]["pattern"] = "^P[1-9]$"
    sch["properties"]["movement"]["description"] = "The id in the rendering's first line, e.g. P1."
    (blind / "SCHEMA.json").write_text(json.dumps(sch, indent=2) + "\n")
    # leakage check
    ok = True
    for mid in key:
        txt = (blind / f"{mid}.txt").read_text()
        h = check_text(txt, titles, {mid})
        marks = sorted({m.strip() for g in re.findall(r"\| \[(.*)\]$", txt, re.M)
                        for m in g.split(", ")})
        log.append(f"{mid} check: " + "; ".join(f"{k} {v[:8]}" for k, v in h.items())
                   + f"\n   printed markings: {marks}")
        ok &= not any(h.values())
        plants = {"composer": " Chopin ", "catalogue": " op. 27 ", "banned": " PAC ",
                  "roman": " V7 ", "old id": " R3 ",
                  "title": f" {titles[0].capitalize()} "}  # fmt: skip
        fired = {k: any(check_text(txt + v, titles, {mid}).values()) for k, v in plants.items()}
        log.append(f"   planted cues fire: {fired}")
        ok &= all(fired.values())
    for extra in ("INSTRUCTIONS.md", "SCHEMA.json"):
        h = check_text((blind / extra).read_text(), titles, {f"P{k + 1}" for k in range(9)})
        h.pop("roman")  # the cadence names and "V" of the instructions are part of the task
        h.pop("banned")
        log.append(f"{extra} check: " + "; ".join(f"{k} {v[:8]}" for k, v in h.items()))
        ok &= not any(h.values())
    log.append("LEAKAGE CHECK " + ("PASSED" if ok else "FAILED"))
    (WORK / "leakage_check.txt").write_text("\n".join(log) + "\n")
    (WORK / "identity_removals.json").write_text(json.dumps(removed_all, indent=1,
                                                            ensure_ascii=False))
    (WORK / "key.json").write_text(json.dumps(key, indent=1, ensure_ascii=False))
    print("\n".join(log))
    if not ok:
        return False
    for run in RUNS:
        d = out / f"run_{run}"
        if d.exists():
            shutil.rmtree(d)
        (d / "out").mkdir(parents=True)
        for f in blind.iterdir():
            shutil.copy2(f, d / f.name)
    (WORK / "prompt.txt").write_text(PROMPT + "\n")
    print(f"blind folders: {', '.join(str(out / f'run_{r}') for r in RUNS)}")
    return True


# --------------------------------------------------------------------------- ingest


def pointer_map(text: str) -> dict[int, int]:
    """As R-08a ``score.pointer_map``, from a rendering's text."""
    m: dict[int, int] = {}
    for a, b, c, d in re.findall(r"^BARS (\d+)-(\d+) .*as bars (\d+)-(\d+)$", text, re.M):
        a, b, c, d = map(int, (a, b, c, d))
        for k in range(b - a + 1):
            m[a + k] = c + k
    for a, c in re.findall(r"^BAR (\d+) .*same notes and markings as bar (\d+)$", text, re.M):
        m[int(a)] = int(c)
    return m


def ingest(ann: Path, agents: dict) -> None:
    key = json.loads((WORK / "key.json").read_text())
    titles = title_words(list(key.values()))
    today = dt.date.today().isoformat()
    for mid, k in key.items():
        score = unfolded_score(k["score"], k["piece_id"])
        strip_identity(score, titles)
        assert score_hash(score) == k["score_hash"], mid
        text = (WORK / "blind_input" / f"{mid}.txt").read_text()
        assert sha(WORK / "blind_input" / f"{mid}.txt") == k["rendering_sha256"], mid
        bars = pd.read_csv(WORK / f"bars_{mid}.csv", dtype={"written": str})
        na = score.notes[~score.notes["is_grace"].astype(bool)]
        mv = {"bars": bars, "d": {"onset_beats": np.unique(na["onset_beat"].astype(float))},
              "pointers": pointer_map(text)}
        runs, recog = [], {}
        for run in RUNS:
            src = ann / f"run_{run}" / "out" / f"{mid}.json"
            if not src.exists():
                print(f"{mid} run {run}: missing, skipped")
                continue
            dst = WORK / "annotations" / run / f"{mid}.json"
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)  # verbatim, before mapping
            doc = json.loads(dst.read_text())
            df, stats = S8A.map_events(doc.get("events", []), mv)
            st = sorted(df.loc[df["type"] == "phrase_start", "beat"].astype(float))
            en = sorted(df.loc[df["type"] == "phrase_end", "beat"].astype(float))
            recog[run] = doc.get("recognised_piece")
            runs.append({"run": run, "starts": st, "ends": en,
                         "start_anchors": anchors(score, st), "end_anchors": anchors(score, en),
                         "n_events": len(doc.get("events", [])), "map_stats": stats,
                         "annotation_sha256": sha(dst),
                         "agent_id": agents.get(run, {}).get(mid, "")})  # fmt: skip
            print(f"{mid} run {run}: {len(st)} starts, {len(en)} ends, map {stats}, "
                  f"recognised {doc.get('recognised_piece')!r}")
        if not runs:
            continue
        prov = {"model": MODEL, "date": today, "protocol": PROTOCOL,
                "score_file": k["score"], "score_sha256": k["score_sha256"],
                "score_hash": k["score_hash"], "edition_hash": k["edition_hash"],
                "unfolded": k["unfolded"], "style": k["style"], "meters": k["meters"],
                "blind_id": mid, "rendering_sha256": k["rendering_sha256"],
                "instructions_sha256": sha(WORK / "blind_input" / "INSTRUCTIONS.md"),
                "schema_sha256": sha(WORK / "blind_input" / "SCHEMA.json"),
                "recognised_piece": recog, "ticket": "DF-02"}  # fmt: skip
        p = write_cache(k["piece_id"], prov, runs)
        print(f"{mid}: wrote {p.name}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("render", "ingest"))
    ap.add_argument("--henry", action="store_true", help="the 5 pieces of O-01 (A-01 scores)")
    ap.add_argument("--pieces", type=Path, help="JSON list of {piece_id, score}")
    ap.add_argument("--out", type=Path, help="render: folder outside the repo for the runs")
    ap.add_argument("--ann", type=Path, help="ingest: the --out folder after annotation")
    ap.add_argument("--agents", type=Path, help="ingest: JSON {run: {P#: agent id}}")
    a = ap.parse_args()
    if a.cmd == "render":
        pieces = henry_pieces() if a.henry else json.loads(a.pieces.read_text())
        assert a.out and ROOT not in a.out.resolve().parents, "--out must be outside the repo"
        sys.exit(0 if render(pieces, a.out) else 1)
    agents = json.loads(a.agents.read_text()) if a.agents else {}
    ingest(a.ann, agents)


if __name__ == "__main__":
    main()
