"""BL-40: the app's wrong-piece stop when the quick check aligns with ``partial=True``.

Run (stages write under ``data/interim/bl40/``; every stage resumes from its files):

``OMP_NUM_THREADS=1 uv run python scripts/eval_wrong_piece_bl40.py --set dev|heldout --stage
pool|takes|probe|readout [--workers 5]``

* ``pool``: dev = every piece of the BL-36 dev, BL-36 held-out, BL-37 held-out and BL-39
  held-out draws (their earlier targets); held-out = a new seeded draw from the app catalogue,
  disjoint from every earlier draw, half of it pairs of sibling movements (same work folder),
  ``pianocore.guard_jobs`` after the draw.
* ``takes``: per piece and transcriber family, the first candidate whose whole take aligns to
  its own score with match ratio >= 0.8 (the app's ``alignment_suspect`` line); excerpts of
  2-4, 5-8, 9-16 and 17-32 graded bars cut at bar boundaries (BL-36 helpers).
* ``probe``: every take aligned to every score of the pool (all ordered pairs) exactly as the
  app's quick check does (``load_score`` of a score file, ``align_performance(...,
  partial=True)``, ``correctness(ap).summary["match_ratio"]``); whole takes also with
  ``partial=False`` (today's baseline) to their own score and to sampled wrong scores (dev) or
  every wrong score (held-out).
* ``readout``: decisions of candidate rules (:func:`pianolens.app.quick_check.decide`) per
  length band, per-piece means, piece bootstrap, leave-one-piece-out.

Pre-registration: ``experiments/2026-10-27-BL-40-wrong-piece-stop/README.md`` (hash by anchor).
"""

from __future__ import annotations

import argparse
import dataclasses
import importlib.util
import json
import pickle
import sys
import time
import warnings
import zlib
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "data" / "interim" / "bl40"
BL36 = REPO / "data" / "interim" / "bl36"
BL37 = REPO / "data" / "interim" / "bl37"
BL39 = REPO / "data" / "interim" / "bl39"
HELDOUT_SEED = 4040
CUT_SEED = 40
N_SIBLING_GROUPS = 8  # held-out: 8 works with two fresh sibling movements each
N_SINGLES = 8  # plus 8 pieces from other works
N_CANDIDATES = 3  # takes tried per piece and family before the piece-family is dropped
BANDS = {"2-4": (2, 4), "5-8": (5, 8), "9-16": (9, 16), "17-32": (17, 32)}
EXCERPTS_PER_BAND = {"dev": 1, "heldout": 1}
DEV_WRONG_WHOLE = 8  # dev: wrong scores per whole take (seeded sample; held-out: every one)
SUSPECT = 0.8  # correctness: alignment_suspect below this ratio
FAMILIES = {"Transkun V2": "transkun", "Aria-AMT": "aria_amt"}


def _mod(name: str, file: str):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, REPO / "scripts" / file)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


def b36():
    return _mod("bl36", "eval_partial_bl36.py")


def b39():
    return _mod("bl39", "eval_edge_narrow_bl39.py")


def _quiet() -> None:
    import logging

    warnings.filterwarnings("ignore")
    logging.disable(logging.WARNING)


def _slug(piece: str) -> str:
    return f"{zlib.crc32(piece.encode()):08x}"


def _dump(path: Path, obj) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=1, default=str))
    tmp.replace(path)


# ----------------------------------------------------------------------------- pools


# Dev = the two most recent draws (32 pieces). The BL-36 dev and held-out pieces (28 more) were
# dropped for machine time: all ordered pairs of 60 pieces measured at about 3.6 h (BL-40 run
# record), over the ticket's budget; their takes were cut but are not probed.
DEV_SOURCES = (("BL-37 held-out", BL37 / "heldout_rows.pkl"),
               ("BL-39 held-out", BL39 / "heldout_rows.pkl"))  # fmt: skip


def dev_pool() -> dict:
    """Every piece of the four earlier draws; candidates = their targets in draw order."""
    pieces: dict[str, dict] = {}
    for src, f in DEV_SOURCES:
        for r in pickle.loads(f.read_bytes())["rows"]:
            if r["role"] != "target":
                continue
            p = pieces.setdefault(r["piece"], {"piece": r["piece"], "piece_id": r["piece_id"],
                                               "score": r["score"], "source": src,
                                               "candidates": {}})
            p["candidates"].setdefault(r["family"], []).append(
                {"id": str(r["id"]), "midi": r["midi"], "order": int(r["order"])})
    for p in pieces.values():
        for fam, c in p["candidates"].items():
            p["candidates"][fam] = sorted(c, key=lambda x: (x["order"], x["id"]))
    return {"set": "dev", "pieces": dict(sorted(pieces.items()))}


def exclusion_sets() -> dict[str, dict[str, set]]:
    """Every earlier draw (BL-39's list plus BL-39 held-out): piece ids and transcription ids."""
    sets = b39().exclusion_sets()
    r39 = pickle.loads((BL39 / "heldout_rows.pkl").read_bytes())["rows"]
    sets["pieces"]["BL-39 held-out"] = {r["piece"] for r in r39}
    sets["ids"]["BL-39"] = {str(r["id"]) for r in r39}
    return sets


def _work(score: str) -> str | None:
    """Work folder of a PianoCoRe score path ``Composer/Work/Movement/score.*``; None for a
    single-piece folder ``Composer/Work/score.*`` (no siblings)."""
    parts = Path(score).parts
    return "/".join(parts[:2]) if len(parts) >= 4 else None


def heldout_pool() -> dict:
    """Seeded draw (HELDOUT_SEED) from the app catalogue's PianoCoRe pieces, disjoint from every
    earlier draw: N_SIBLING_GROUPS works with two eligible movements each, plus N_SINGLES pieces
    of other works. Candidates: N_CANDIDATES unused transcriptions per family, seeded order.
    ``guard_jobs`` runs on the candidates after the draw."""
    import zipfile

    from pianolens.data.pianocore import DEFAULT_ROOT, RAW_PREFIX, RAW_ZIP, PianoCoRe, guard_jobs
    from pianolens.data.piece_ids import SCORE_VERSION_MISMATCH

    idx = PianoCoRe().index
    tr = idx[idx["is_transcription"].astype(bool) & idx["capture_model"].isin(FAMILIES)]
    sets = exclusion_sets()
    excl = set().union(*sets["pieces"].values()) | set(SCORE_VERSION_MISMATCH)
    used = set().union(*sets["ids"].values())
    # the app's cached catalogue (read only; CATALOG_VERSION 4 = BL-38)
    cat = json.loads((REPO / "data" / "interim" / "app" / "catalog.json").read_text())
    assert cat["version"] == 4, cat["version"]
    cat_scores = {p["score"] for p in cat["pieces"]
                  if p["source"] == "pianocore" and not p["four_hands"]}
    with zipfile.ZipFile(DEFAULT_ROOT / RAW_ZIP) as z:
        names = set(z.namelist())
    tr = tr[~tr["id"].astype(str).isin(used)]
    elig = []
    for pid, g in tr.groupby("piece_id"):
        sx = sorted(set(g["score_xml_path"].dropna().astype(str)))
        if (pid in excl or len(sx) != 1 or sx[0] not in cat_scores
                or RAW_PREFIX + sx[0] not in names):
            continue
        if min((g["capture_model"] == cm).sum() for cm in FAMILIES) < N_CANDIDATES:
            continue
        elig.append((str(pid), sx[0]))
    elig.sort()
    rng = np.random.default_rng(HELDOUT_SEED)
    groups: dict[str, list] = {}
    for pid, sx in elig:
        w = _work(sx)
        if w is not None:
            groups.setdefault(w, []).append((pid, sx))
    multi = sorted(w for w, v in groups.items() if len(v) >= 2)
    chosen, chosen_works = [], []
    for i in rng.permutation(len(multi))[:N_SIBLING_GROUPS]:
        w = multi[i]
        pick = rng.choice(len(groups[w]), size=2, replace=False)
        chosen += [groups[w][j] for j in sorted(pick)]
        chosen_works.append(w)
    rest = [e for e in elig if _work(e[1]) not in chosen_works]
    chosen += [rest[i] for i in rng.permutation(len(rest))[:N_SINGLES]]
    pieces, cand_jobs = {}, []
    for pid, sx in sorted(chosen):
        p = {"piece": pid, "piece_id": pid, "score": sx, "source": "BL-40 held-out",
             "work": _work(sx), "candidates": {}}
        for cm, fam in FAMILIES.items():
            r = tr[(tr["piece_id"] == pid) & (tr["capture_model"] == cm)].sort_values("id")
            perm = rng.permutation(len(r))[:N_CANDIDATES]
            p["candidates"][fam] = [{"id": str(r.iloc[i]["id"]), "order": k,
                                     "midi": str(r.iloc[i]["performance_midi_path"])}
                                    for k, i in enumerate(perm)]
            cand_jobs += [{"id": c["id"], "piece": pid, "family": fam}
                          for c in p["candidates"][fam]]
        pieces[pid] = p
    kept = {j["id"] for j in guard_jobs(cand_jobs, idx, label="BL-40 held-out")}
    guarded = sorted({j["id"] for j in cand_jobs} - kept)
    for p in pieces.values():
        for fam in p["candidates"]:
            p["candidates"][fam] = [c for c in p["candidates"][fam] if c["id"] in kept]
    return {"set": "heldout", "seed": HELDOUT_SEED, "pieces": pieces, "guarded_ids": guarded,
            "n_eligible": len(elig), "n_sibling_works_eligible": len(multi),
            "sibling_works": chosen_works,
            "exclusions": {k: sorted(v) for k, v in sets["pieces"].items()},
            "n_excluded_ids": {k: len(v) for k, v in sets["ids"].items()}}


# ----------------------------------------------------------------------------- takes


def score_file(piece: dict) -> Path:
    """A persistent copy of the piece's score, so ``align_performance`` re-reads it as the app
    does (``load_score`` of a file; BL-27 trap: a temp-dir copy is gone when align runs)."""
    import zipfile

    from pianolens.data.pianocore import DEFAULT_ROOT, RAW_PREFIX, RAW_ZIP

    d = OUT / "scores"
    d.mkdir(parents=True, exist_ok=True)
    f = d / (_slug(piece["piece"]) + "".join(Path(piece["score"]).suffixes[-1:]))
    if not f.is_file():
        with zipfile.ZipFile(DEFAULT_ROOT / RAW_ZIP) as z:
            tmp = f.with_suffix(".part")
            tmp.write_bytes(z.read(RAW_PREFIX + piece["score"]))
            tmp.replace(f)
    return f


def load_take(piece: dict, cand: dict):
    """The candidate's performance as the app loads a transcribed MIDI upload."""
    import tempfile
    import zipfile

    from pianolens.data.pianocore import DEFAULT_ROOT, RAW_PREFIX, RAW_ZIP
    from pianolens.report.io import load_performance

    with zipfile.ZipFile(DEFAULT_ROOT / RAW_ZIP) as z, tempfile.TemporaryDirectory() as td:
        f = Path(td) / "perf.mid"
        f.write_bytes(z.read(RAW_PREFIX + cand["midi"]))
        return load_performance(f, "transcribed", piece["piece_id"], performance_id=cand["id"])


def quick(score, perf, partial: bool) -> dict:
    """The app's quick check (``app/pipeline.py`` step 2): match ratio and recorded span.
    ``score`` is ``report.io.load_score`` of a persistent file; ``align_performance`` re-reads
    that file on every call, as in the app (so one loaded Score serves many calls)."""
    from pianolens.align import align_performance
    from pianolens.features.correctness import correctness

    ap = align_performance(score, perf, partial=partial)
    cr = correctness(ap)
    span = ap.score.meta.get("recorded_span") or {}
    return {"ratio": float(cr.summary["match_ratio"]), "whole": bool(span.get("whole", True)),
            "n_performed": int(cr.summary["n_performed_notes"]), "cr": cr}


def takes_one(args: tuple) -> dict:
    """First candidate whose whole take is not suspect on its own score; its excerpts."""
    _quiet()
    piece, fam, n_exc = args
    from pianolens.report.io import load_score

    m = b36()
    sc = load_score(score_file(piece), piece["piece_id"])
    tried = []
    for cand in piece["candidates"].get(fam, [])[:N_CANDIDATES]:
        perf = load_take(piece, cand)
        q = quick(sc, perf, partial=False)
        tried.append({"id": cand["id"], "ratio": q["ratio"]})
        if q["ratio"] < SUSPECT:
            continue
        fl = m._graded_first_last(q["cr"])
        notes = perf.notes
        rng = np.random.default_rng([CUT_SEED, zlib.crc32(cand["id"].encode())])
        base = {"piece": piece["piece"], "family": fam, "id": cand["id"]}
        takes = [({**base, "take": "whole", "band": "whole", "n_bars": len(fl),
                   "n_notes": len(notes)}, perf)]
        skipped = []
        for band, (lo, hi) in BANDS.items():
            for e in range(n_exc):
                length = int(rng.integers(lo, hi + 1))
                if len(fl) < length + 2:
                    skipped.append(f"{band}#{e}")
                    continue
                k0 = int(rng.integers(1, len(fl) - length))
                t0, t1 = m._bar_boundary(fl, k0), m._bar_boundary(fl, k0 + length)
                na = notes[(notes["onset_sec"] >= t0) & (notes["onset_sec"] < t1)].copy()
                takes.append(({**base, "take": f"{band}#{e}", "band": band, "n_bars": length,
                               "first_bar": k0, "t_lo": t0, "t_hi": t1, "n_notes": len(na)},
                              dataclasses.replace(perf, notes=na)))
        return {"piece": piece["piece"], "family": fam, "tried": tried, "takes": takes,
                "skipped": skipped}
    return {"piece": piece["piece"], "family": fam, "tried": tried, "takes": [], "skipped": []}


def takes_stage(pool: dict, set_: str, workers: int) -> None:
    d = OUT / f"{set_}_takes"
    d.mkdir(parents=True, exist_ok=True)
    todo = [(p, fam, EXCERPTS_PER_BAND[set_]) for p in pool["pieces"].values()
            for fam in FAMILIES.values()
            if not (d / f"{_slug(p['piece'])}_{fam}.pkl").is_file()]
    print(f"takes: {len(todo)} piece-family jobs to run", flush=True)
    with ProcessPoolExecutor(workers) as ex:
        futs = [ex.submit(takes_one, a) for a in todo]
        for f in as_completed(futs):
            r = f.result()
            (d / f"{_slug(r['piece'])}_{r['family']}.pkl").write_bytes(pickle.dumps(r))
            print(f"takes {r['piece']} {r['family']}: {len(r['takes'])} takes, "
                  f"tried {[round(t['ratio'], 3) for t in r['tried']]}", flush=True)


def load_takes(set_: str, fam: str | None = None, pieces: set[str] | None = None) -> list[dict]:
    """Takes of the pool's pieces (``pieces``; None = every file)."""
    out = []
    for f in sorted((OUT / f"{set_}_takes").glob("*.pkl")):
        r = pickle.loads(f.read_bytes())
        if (fam is None or r["family"] == fam) and (pieces is None or r["piece"] in pieces):
            out.append(r)
    return out


# ----------------------------------------------------------------------------- probe


def whole_wrong_sample(set_: str, take_id: str, piece: str, pieces: list[str]) -> set[str]:
    """Wrong scores a whole take is aligned to, with ``partial`` on and off (dev: a seeded
    sample of DEV_WRONG_WHOLE, since whole takes cost most of the time; held-out: all)."""
    others = sorted(p for p in pieces if p != piece)
    if set_ != "dev":
        return set(others)
    rng = np.random.default_rng([CUT_SEED, zlib.crc32(take_id.encode()), 1])
    return {others[i] for i in rng.choice(len(others), DEV_WRONG_WHOLE, replace=False)}


def probe_one(args: tuple) -> list[dict]:
    """Every take of one family aligned to one score, as the app's quick check."""
    _quiet()
    from pianolens.report.io import load_score

    set_, score_piece, fam, whole_ids, pieces = args
    sc = load_score(score_file(score_piece), score_piece["piece_id"])
    rows = []
    for r in load_takes(set_, fam, pieces):
        for meta, perf in r["takes"]:
            rel = "right" if meta["piece"] == score_piece["piece"] else "wrong"
            modes = [True]
            if meta["band"] == "whole":
                if rel == "wrong" and meta["id"] not in whole_ids:
                    continue
                modes.append(False)
            for partial in modes:
                t0 = time.time()
                try:
                    q = quick(sc, perf, partial)
                    q.pop("cr")
                except Exception as e:  # noqa: BLE001 - a failed alignment is recorded
                    q = {"ratio": float("nan"), "whole": None, "n_performed": -1,
                         "error": f"{type(e).__name__}: {e}"[:200]}
                rows.append({**{k: meta.get(k) for k in ("piece", "family", "id", "take", "band",
                                                         "n_bars", "n_notes")},
                             "score_piece": score_piece["piece"], "relation": rel,
                             "partial": partial, **q, "sec": round(time.time() - t0, 3)})
    return rows


def whole_pairs(set_: str, names: list[str]) -> dict[str, set[str]]:
    """Score piece -> whole-take ids aligned to it as a wrong score."""
    off: dict[str, set[str]] = {}
    for r in load_takes(set_, pieces=set(names)):
        for meta, _ in r["takes"]:
            if meta["band"] == "whole":
                for s in whole_wrong_sample(set_, meta["id"], meta["piece"], names):
                    off.setdefault(s, set()).add(meta["id"])
    return off


def probe_stage(pool: dict, set_: str, workers: int) -> None:
    d = OUT / f"{set_}_probe"
    d.mkdir(parents=True, exist_ok=True)
    names = sorted(pool["pieces"])
    off = whole_pairs(set_, names)
    todo = [(set_, pool["pieces"][s], fam, off.get(s, set()), set(names)) for s in names
            for fam in FAMILIES.values() if not (d / f"{_slug(s)}_{fam}.csv").is_file()]
    print(f"probe: {len(todo)} score-family jobs to run", flush=True)
    t_start = time.time()
    with ProcessPoolExecutor(workers) as ex:
        futs = {ex.submit(probe_one, a): a for a in todo}
        for i, f in enumerate(as_completed(futs), 1):
            a = futs[f]
            rows = f.result()
            tmp = d / f"{_slug(a[1]['piece'])}_{a[2]}.csv.tmp"
            pd.DataFrame(rows).to_csv(tmp, index=False)
            tmp.replace(d / f"{_slug(a[1]['piece'])}_{a[2]}.csv")
            print(f"probe {i}/{len(todo)} {a[1]['piece'][:40]} {a[2]}: {len(rows)} rows, "
                  f"{(time.time() - t_start) / 60:.1f} min", flush=True)



# ----------------------------------------------------------------------------- readout

EXC_BANDS = tuple(BANDS)
T_GRID = tuple(round(0.5 + 0.025 * i, 3) for i in range(13))  # 0.50 .. 0.80
N_GRID = (0, 25, 50, 75, 100, 150)
MODES = ("high", "all")  # below N notes: confirm only at or above the stop / confirm always


def load_probe(set_: str) -> pd.DataFrame:
    fs = sorted((OUT / f"{set_}_probe").glob("*.csv"))
    df = pd.concat([pd.read_csv(f) for f in fs], ignore_index=True)
    names = sorted(json.loads((OUT / f"{set_}_pool.json").read_text())["pieces"])
    df = df[df["piece"].isin(names) & df["score_piece"].isin(names)]  # the pool only
    df["ratio"] = df["ratio"].fillna(0.0)  # a failed alignment counts as no match (app: NaN)
    df["whole"] = df["whole"].astype(str).eq("True")
    # whole takes on wrong scores: only the registered pairs (the first dev jobs ran all)
    pairs = whole_pairs(set_, names)
    ww = (df["band"] == "whole") & (df["relation"] == "wrong")
    keep = [i in pairs.get(s, set()) for i, s in zip(df["id"].astype(str), df["score_piece"],
                                                     strict=True)]
    return df[~ww | np.array(keep)].reset_index(drop=True)


def decisions(df: pd.DataFrame, t: float, n_min: int, mode: str,
              trimmed_rule_on_whole: bool = False) -> np.ndarray:
    """Vectorised :func:`pianolens.app.quick_check.decide` for one candidate rule
    (``trimmed_rule_on_whole``: sabotage for the bite check, the trimmed-span rule everywhere).
    Returns an array of "pass" / "stop" / "confirm"."""
    r = df["ratio"].to_numpy(float)
    part = df["partial"].astype(bool).to_numpy()
    whole = df["whole"].to_numpy(bool) & ~np.full(len(df), trimmed_rule_on_whole)
    short = df["n_notes"].to_numpy(int) < n_min
    today = np.where(r < 0.5, "stop", "pass")
    trim = np.where(r < t, "stop", "pass")
    if mode == "all":
        trim = np.where(short, "confirm", trim)
    else:
        trim = np.where(short & (r >= t), "confirm", trim)
    return np.where(~part | whole, today, trim)


def _per_piece(df: pd.DataFrame, hit: np.ndarray) -> pd.Series:
    return pd.Series(hit.astype(float), index=df.index).groupby(df["piece"]).mean()


def _stat(per: pd.Series, rng: np.random.Generator, n_boot: int = 2000) -> dict:
    v = per.to_numpy(float)
    if len(v) == 0:
        return {"mean": float("nan"), "n_pieces": 0}
    boot = v[rng.integers(0, len(v), (n_boot, len(v)))].mean(1)
    return {"mean": float(v.mean()), "lo": float(np.quantile(boot, 0.025)),
            "hi": float(np.quantile(boot, 0.975)), "n_pieces": int(len(v)),
            "max_piece": float(v.max()), "worst": str(per.idxmax()),
            "boot": boot}



def rule_rows(df: pd.DataFrame, t: float, n_min: int, mode: str, seed: int = 0,
              sabotage: bool = False) -> dict:
    """Every row for one rule. Excerpt rows are means over source pieces of per-piece shares:
    ``H`` wrong-score alignments passed silently (harm), ``Hc`` wrong ones asked to confirm,
    ``F`` right-score excerpts stopped, ``C`` right ones asked to confirm. Whole takes: ``W1``
    right takes whose decision is worse than today's (today pass -> stop or confirm), ``W2``
    wrong-score whole takes passed silently, ``W3`` wrong whole takes today stops but the rule
    passes (sampled pairs), counts and per-piece shares."""
    rng = np.random.default_rng(seed)
    dec = decisions(df, t, n_min, mode, trimmed_rule_on_whole=sabotage)
    out: dict = {}
    on = df["partial"].astype(bool)
    for b in EXC_BANDS:
        for rel, rows in (("wrong", (("H", "pass"), ("Hc", "confirm"))),
                          ("right", (("F", "stop"), ("C", "confirm")))):
            m = (on & (df["band"] == b) & (df["relation"] == rel)).to_numpy()
            for name, val in rows:
                st = _stat(_per_piece(df[m], dec[m] == val), rng)
                st["n_items"], st["n_hits"] = int(m.sum()), int((dec[m] == val).sum())
                out[f"{name} {b}"] = st
    wh = df["band"] == "whole"
    key = ["id", "score_piece"]
    new = df[wh & on].assign(dec=dec[(wh & on).to_numpy()]).set_index(key)["dec"]
    old = df[wh & ~on].assign(dec=dec[(wh & ~on).to_numpy()]).set_index(key)["dec"]
    rel = df[wh & on].set_index(key)["relation"]
    pair = pd.DataFrame({"new": new, "old": old, "rel": rel}).dropna()
    worse = (pair["old"] == "pass") & (pair["new"] != "pass")
    better = (pair["old"] != "pass") & (pair["new"] == "pass")
    pr = pair["rel"] == "right"
    out["W1 right whole worse"] = {"n_hits": int((worse & pr).sum()), "n_items": int(pr.sum()),
                                   "n_better": int((better & pr).sum())}
    wn = df[wh & on & (df["relation"] == "wrong")]
    hit = dec[(wh & on & (df["relation"] == "wrong")).to_numpy()] == "pass"
    st = _stat(_per_piece(wn, hit), rng)
    st["n_items"], st["n_hits"] = int(len(wn)), int(hit.sum())
    out["W2 wrong whole pass"] = st
    out["W3 wrong whole today stop -> pass"] = {"n_hits": int((better & ~pr).sum()),
                                                "n_items": int((~pr).sum()),
                                                "n_worse": int((worse & ~pr).sum())}
    return out



#: The registered rule and bars (set on dev; see the pre-registration).
REGISTERED: dict | None = {"t": 0.625, "n_min": 75, "mode": "all"}
BARS: dict[str, tuple[str, float]] = {  # row prefix -> ("mean" | "count", max value)
    "H 2-4": ("mean", 0.0025), "H 5-8": ("mean", 0.0025), "H 9-16": ("mean", 0.0025),
    "H 17-32": ("mean", 0.0025),
    "F 2-4": ("mean", 0.025), "F 5-8": ("mean", 0.025), "F 9-16": ("mean", 0.025),
    "F 17-32": ("mean", 0.025),
    "C 9-16": ("mean", 0.05), "C 17-32": ("mean", 0.05),
    "W1 right whole worse": ("count", 0), "W2 wrong whole pass": ("count", 0)}
#: Rules each registered row must be able to fail under on dev (bite check): name -> (rule,
#: sabotage = the trimmed-span rule applied to whole spans too).
BITE_RULES: dict[str, tuple[dict, bool]] = {
    "H: stop 0.55, no minimum": ({"t": 0.55, "n_min": 0, "mode": "high"}, False),
    "F: stop 0.80, no minimum": ({"t": 0.80, "n_min": 0, "mode": "high"}, False),
    "C: minimum 300 notes": ({"t": 0.625, "n_min": 300, "mode": "all"}, False),
    "W1: stop 0.96 on every span": ({"t": 0.96, "n_min": 0, "mode": "high"}, True),
    "W2: stop 0.30 on every span": ({"t": 0.30, "n_min": 0, "mode": "high"}, True)}


def verdict(rows: dict, bars: dict | None = None) -> dict[str, bool]:
    """Pass/fail per registered row: excerpt rows on the mean, whole rows on the count."""
    bars = BARS if bars is None else bars
    out = {}
    for name, st in rows.items():
        for prefix, (kind, val) in bars.items():
            if name == prefix:
                x = st["mean"] if kind == "mean" else st["n_hits"]
                out[name] = bool(x <= val + 1e-12)
    return out


def _clean(rows: dict) -> dict:
    return {k: {kk: vv for kk, vv in v.items() if kk != "boot"} for k, v in rows.items()}


def loo(df: pd.DataFrame, rule: dict, base: dict[str, bool]) -> dict:
    """Leave one piece out (as source and as score): rows whose verdict flips."""
    flips: dict[str, list[str]] = {}
    for p in sorted(df["piece"].unique()):
        d = df[(df["piece"] != p) & (df["score_piece"] != p)]
        v = verdict(rule_rows(d, **rule))
        for k, ok in v.items():
            if ok != base.get(k):
                flips.setdefault(k, []).append(p)
    return flips


def resample_pass(rows: dict, bars: dict | None = None) -> dict[str, float]:
    """Share of piece-bootstrap resamples whose mean meets the bar (excerpt rows)."""
    bars = BARS if bars is None else bars
    out = {}
    for name, st in rows.items():
        for prefix, (kind, val) in bars.items():
            if kind == "mean" and name == prefix and "boot" in st:
                out[name] = float((st["boot"] <= val + 1e-12).mean())
    return out


def ratio_quantiles(df: pd.DataFrame) -> pd.DataFrame:
    on = df[df["partial"].astype(bool)]
    g = on.groupby(["band", "relation"])["ratio"]
    q = g.quantile([0.0, 0.01, 0.05, 0.5, 0.95, 0.99, 1.0]).unstack()
    q["n"] = g.size()
    return q.round(3)



def reachability(df: pd.DataFrame, rule: dict, n_pieces: int, n: int = 500,
                 seed: int = 4041) -> dict:
    """Dev: chance the rule passes every registered row on a pool of ``n_pieces`` drawn from
    dev without replacement (all ordered pairs within the drawn pool), and per row."""
    rng = np.random.default_rng(seed)
    names = np.array(sorted(df["piece"].unique()))
    ok_all, per_row = 0, {}
    for _ in range(n):
        keep = set(rng.choice(names, size=min(n_pieces, len(names)), replace=False))
        d = df[df["piece"].isin(keep) & df["score_piece"].isin(keep)]
        v = verdict(rule_rows(d, **rule))
        ok_all += all(v.values())
        for k, ok in v.items():
            per_row[k] = per_row.get(k, 0) + ok
    return {"n": n, "n_pieces": n_pieces, "all": ok_all / n,
            "per_row": {k: c / n for k, c in per_row.items()}}


def key_of(score_path: Path) -> int:
    """First key signature of a score (sharps positive, flats negative; 0 if none)."""
    import partitura as pt

    part = pt.score.merge_parts(pt.load_score(str(score_path)).parts)
    ks = sorted(part.iter_all(pt.score.KeySignature), key=lambda k: k.start.t)
    return int(ks[0].fifths) if ks else 0


def hard_cases(df: pd.DataFrame, pool: dict, rules: dict[str, dict]) -> pd.DataFrame:
    """Wrong-score excerpts by pair kind (information): sibling movements (same work folder),
    same key signature, other; count, top ratios and silent passes under each rule."""
    pieces = pool["pieces"]
    work = {p: _work(v["score"]) for p, v in pieces.items()}
    key = {p: key_of(score_file(v)) for p, v in pieces.items()}
    w = df[df["partial"].astype(bool) & (df["relation"] == "wrong")].copy()
    sib = [work[a] is not None and work[a] == work[b]
           for a, b in zip(w["piece"], w["score_piece"], strict=True)]
    same = [key[a] == key[b] for a, b in zip(w["piece"], w["score_piece"], strict=True)]
    w["kind"] = np.where(sib, "sibling", np.where(same, "same key", "other"))
    recs = []
    for (kind, band), g in w.groupby(["kind", "band"]):
        rec = {"kind": kind, "band": band, "n": len(g), "max": g["ratio"].max(),
               "q99": g["ratio"].quantile(0.99)}
        for name, r in rules.items():
            rec[f"pass {name}"] = int((decisions(g, **r) == "pass").sum())
        recs.append(rec)
    return pd.DataFrame(recs)


def decide_agrees(df: pd.DataFrame) -> dict:
    """Plumbing check: the vectorised registered rule equals ``quick_check.decide`` with its
    module defaults on every alignment row."""
    from pianolens.app.quick_check import decide

    vec = decisions(df, **REGISTERED)
    one = [decide(r, partial=bool(p), span_whole=bool(w), n_performed=int(n))
           for r, p, w, n in zip(df["ratio"], df["partial"], df["whole"], df["n_notes"],
                                 strict=True)]
    return {"n": len(df), "n_differ": int((vec != np.array(one)).sum())}


def grid(df: pd.DataFrame) -> pd.DataFrame:
    """Every candidate rule's rows (point estimates), for the dev selection."""
    recs = []
    for t in T_GRID:
        for n in N_GRID:
            for mode in MODES if n else ("high",):
                rows = rule_rows(df, t, n, mode)
                rec = {"t": t, "n_min": n, "mode": mode}
                for k, st in rows.items():
                    rec[k] = st.get("mean", st["n_hits"]) if "mean" in st else st["n_hits"]
                recs.append(rec)
    return pd.DataFrame(recs)


def readout_stage(pool: dict, set_: str) -> None:
    df = load_probe(set_)
    res: dict = {"n_rows": len(df), "n_errors": int(df["error"].notna().sum())
                 if "error" in df else 0,
                 "n_pieces": int(df["piece"].nunique()),
                 "sec_total": float(df["sec"].sum())}
    q = ratio_quantiles(df)
    print(q.to_string())
    res["ratio_quantiles"] = q.reset_index().to_dict("records")
    base = {"t": 0.5, "n_min": 0, "mode": "high"}  # partial on, today's stop unchanged
    res["baseline_rows"] = _clean(rule_rows(df, **base))
    if set_ == "dev" or REGISTERED is None:
        g = grid(df)
        g.to_csv(OUT / f"{set_}_grid.csv", index=False)
        print(g.round(4).to_string())
    rules = {"baseline": base, **({"registered": REGISTERED} if REGISTERED else {})}
    hard = hard_cases(df, pool, rules)
    hard.to_csv(OUT / f"{set_}_hard_cases.csv", index=False)
    print(hard.round(3).to_string())
    res["hard_cases"] = hard.to_dict("records")
    if REGISTERED is not None and set_ == "dev":
        res["reachability"] = reachability(df, REGISTERED, n_pieces=24)
        print("reachability", res["reachability"])
    if REGISTERED is not None:
        res["decide_agrees"] = decide_agrees(df)
        rows = rule_rows(df, **REGISTERED)
        v = verdict(rows)
        res["registered"] = REGISTERED
        res["rows"] = _clean(rows)
        res["verdict_rows"] = v
        res["verdict"] = "PASS" if all(v.values()) else "FAIL"
        res["resample_pass"] = resample_pass(rows)
        res["loo_flips"] = loo(df, REGISTERED, v)
        res["bite"] = {k: verdict(rule_rows(df, **r, sabotage=sab))
                       for k, (r, sab) in BITE_RULES.items()}
        for k, ok in v.items():
            st = res["rows"][k]
            print(f"{k:38s} {'pass' if ok else 'FAIL'} {st}")
        print("verdict", res["verdict"], "loo flips", res["loo_flips"])
    _dump(OUT / f"{set_}_readout.json", res)


# ----------------------------------------------------------------------------- main


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--set", choices=("dev", "heldout"), required=True)
    ap.add_argument("--stage", choices=("pool", "takes", "probe", "readout"), required=True)
    ap.add_argument("--workers", type=int, default=5)
    args = ap.parse_args()
    _quiet()
    OUT.mkdir(parents=True, exist_ok=True)
    pool_f = OUT / f"{args.set}_pool.json"
    if args.stage == "pool":
        if pool_f.is_file():
            print(f"{pool_f} exists; not redrawn")
            return
        pool = dev_pool() if args.set == "dev" else heldout_pool()
        _dump(pool_f, pool)
        print(f"{len(pool['pieces'])} pieces -> {pool_f}")
        return
    pool = json.loads(pool_f.read_text())
    if args.stage == "takes":
        takes_stage(pool, args.set, args.workers)
    elif args.stage == "probe":
        probe_stage(pool, args.set, args.workers)
    else:
        readout_stage(pool, args.set)


if __name__ == "__main__":
    main()
