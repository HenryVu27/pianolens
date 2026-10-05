"""R-10 evaluation set builder (any env with pianolens installed; CPU).

Copies R-07's item rules (job/prep_data.py ``select_pianocore`` + ``_pianocore_piece`` and
job/make_eval_items.py ``from_prep``) for a given list of PianoCoRe pieces, without the deadpan
variants (R-10 needs only the real renditions and one generation item per piece):

  * tier A rows of the listed pieces, minus rows whose source is ASAP, restricted to the piece's
    majority refined score by metadata (R-02 rule; R-07 took the majority after the cap draw,
    ``--r07-cap-rule``); at most ``--cap`` performances per piece, drawn with R-07's per-piece
    seed (20260928 + crc32(piece) mod 100,003);
  * interchange items (``expression_data.interchange_from_aligned``); items with matched share
    below ``--min-match`` (0.8) are dropped;
  * majority refined score per piece over the usable items (R-02 rule, as R-07);
  * generation score = union of matched score notes over renditions, first ``--max-notes``
    (3,000) distinct score notes; every rendition is capped at the same score onset and kept if
    it still has at least 16 notes.

Writes under --out: items/<stem>__real.npz, gen_items/<piece slug>.npz, manifest.csv (one row per
kept rendition, with capture_model and source dataset), excluded.csv, digest.json (sha256 over
every array of every file; the box rebuild must match the Mac's committed digest).

    python build_set.py --pieces ../pieces/fresh_pieces.csv --pianocore DATA/pianocore \\
        --out OUT/sets/fresh --workers 8
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
import zlib
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 20260928  # R-07 per-piece cap seed (kept so R10u pieces reproduce R-07's draw)


def slug(s: str) -> str:
    return "".join(c if c.isalnum() or c in "-." else "_" for c in s)


def select_rows(idx: pd.DataFrame, pieces: list[str], cap: int,
                majority_first: bool = True) -> pd.DataFrame:
    """R-07 select_pianocore for the listed pieces (test-cap rule).

    ``majority_first`` (R-10 default; R-02 rule): keep only the rows of the piece's majority
    refined score (by metadata count, ties broken by path, as select_pieces.py) *before* the cap
    draw. R-07 drew the cap over all scores and took the majority afterwards, which can leave
    fewer than ``cap`` majority-score renditions."""
    idx = idx[idx["piece_id"].isin(pieces) & (idx["performance_dataset"] != "ASAP")]
    if majority_first:
        n = idx.groupby(["piece_id", "refined_score_midi_path"]).size().rename("n").reset_index()
        n = n.sort_values(["piece_id", "n", "refined_score_midi_path"],
                          ascending=[True, False, True]).drop_duplicates("piece_id")
        maj = set(zip(n["piece_id"], n["refined_score_midi_path"], strict=True))
        keep = [(p, s) in maj for p, s in zip(idx["piece_id"], idx["refined_score_midi_path"],
                                               strict=True)]
        idx = idx[np.array(keep, dtype=bool)]
    out = []
    for pid, g in idx.groupby("piece_id", sort=True):
        rng = np.random.default_rng(SEED + zlib.crc32(pid.encode()) % 100_003)
        ids = np.sort(g["id"].to_numpy())
        take = ids if len(ids) <= cap else np.sort(rng.choice(ids, size=cap, replace=False))
        out.append(g[g["id"].isin(take)])
    return pd.concat(out, ignore_index=True)


def _cap(it: dict, cutoff: float) -> dict:
    k = it["score_onset_q"] <= cutoff + 1e-9
    out = dict(it)
    for key in ("score_onset_q", "score_dur_q", "pitch", "perf_onset_sec", "perf_dur_sec",
                "velocity", "score_id"):
        out[key] = it[key][k]
    return out


def build_piece(args) -> tuple[list[dict], list[dict]]:
    root, pid, rows, out, min_match, max_notes = args
    from pianolens.data.pianocore import PianoCoRe
    from pianolens.models.expression_data import interchange_from_aligned, save_item

    pc = PianoCoRe(root)
    loaded, excl = [], []
    rows = rows.sort_values("refined_score_midi_path", kind="stable")
    for _, row in rows.iterrows():
        base = {"piece_id": pid, "row_id": row["id"], "performance_id": row["performance_id"],
                "source_dataset": row["performance_dataset"],
                "capture_model": row["capture_model"], "score_key": row["refined_score_midi_path"]}
        try:
            item, info = interchange_from_aligned(pc.load(row))
        except Exception as e:  # noqa: BLE001 - record and continue
            excl.append({**base, "excluded": f"load_error: {e!r}"[:200]})
            continue
        if item is not None and info["match_share"] < min_match:
            info["excluded"] = "match_share"
        if item is None or info["excluded"]:
            excl.append({**base, "excluded": info.get("excluded", "none"),
                         "match_share": info.get("match_share")})
            continue
        loaded.append((base, item, info))
    pc.close()
    if not loaded:
        return [], excl
    keys = pd.Series([b["score_key"] for b, _, _ in loaded])
    key = keys.value_counts().idxmax()
    for b, _, _ in loaded:
        if b["score_key"] != key:
            excl.append({**b, "excluded": "minority_score"})
    loaded = [x for x in loaded if x[0]["score_key"] == key]
    its = [it for _, it, _ in loaded]
    sid = np.concatenate([i["score_id"] for i in its])
    on = np.concatenate([i["score_onset_q"] for i in its])
    du = np.concatenate([i["score_dur_q"] for i in its])
    pi = np.concatenate([i["pitch"] for i in its])
    _, first = np.unique(sid, return_index=True)
    order = first[np.lexsort((pi[first], on[first]))]
    cutoff = float(on[order][min(len(order), max_notes) - 1])
    order = order[on[order] <= cutoff + 1e-9]
    z = np.zeros(len(order))
    gen = {"score_onset_q": on[order], "score_dur_q": du[order], "pitch": pi[order],
           "perf_onset_sec": z, "perf_dur_sec": z, "velocity": z.astype(int),
           "pedal": np.zeros((0, 2)), "score_id": sid[order],
           "spq_cond": float(np.median([i["spq_cond"] for i in its])),
           "vel_cond": float(np.median([i["vel_cond"] for i in its])),
           "origin": float(its[0]["origin"]), "ts": its[0]["ts"]}
    save_item(out / "gen_items" / f"{slug(pid)}.npz", gen)
    kept = []
    for b, it, info in loaded:
        it = _cap(it, cutoff)
        if len(it["pitch"]) < 16:
            excl.append({**b, "excluded": "under_16_notes_after_cap"})
            continue
        stem = slug(f"{pid}__{b['row_id']}")[:150]
        save_item(out / "items" / f"{stem}__real.npz", it)
        kept.append({**b, "stem": stem, "kind": "real", "passage": pid, "work": pid,
                     "performer": b["performance_id"], "n_notes": int(len(it["pitch"])),
                     "match_share": info["match_share"], "spq_cond": it["spq_cond"],
                     "vel_cond": it["vel_cond"], "gen_notes": int(len(order))})
    return kept, excl


def digest(out: Path) -> dict:
    """sha256 over every array of every npz (floats rounded to 1e-9; R-07 audit B3 recipe)."""
    res = {}
    for kind in ("items", "gen_items"):
        h, n = hashlib.sha256(), 0
        for p in sorted((out / kind).glob("*.npz")):
            z = np.load(p, allow_pickle=True)
            h.update(p.name.encode())
            for k in sorted(z.files):
                a = np.asarray(z[k])
                if a.dtype.kind in "fc":
                    a = np.round(a.astype(np.float64), 9)
                h.update(k.encode())
                h.update(str(a.shape).encode())
                h.update(a.tobytes() if a.dtype != object else repr(a.tolist()).encode())
            n += 1
        res[kind] = {"n": n, "sha256": h.hexdigest()}
    return res


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pieces", required=True, help="CSV with a piece_id column")
    ap.add_argument("--pianocore", required=True, help="dir with metadata.csv + refined zip")
    ap.add_argument("--out", required=True)
    ap.add_argument("--cap", type=int, default=50)
    ap.add_argument("--min-match", type=float, default=0.8)
    ap.add_argument("--max-notes", type=int, default=3000)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--limit", type=int, default=0, help="first N pieces of the list")
    ap.add_argument("--work-col", default="work", help="column of --pieces holding the work key")
    ap.add_argument("--r07-cap-rule", action="store_true",
                    help="cap over all scores, majority afterwards (R-07); default majority first")
    a = ap.parse_args(argv)
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    from pianolens.data.pianocore import pianocore_index

    t0 = time.time()
    out = Path(a.out)
    (out / "items").mkdir(parents=True, exist_ok=True)
    (out / "gen_items").mkdir(parents=True, exist_ok=True)
    plist = pd.read_csv(a.pieces)
    if a.limit:
        plist = plist.head(a.limit)
    pieces = plist["piece_id"].tolist()
    work = dict(zip(plist["piece_id"], plist[a.work_col], strict=True)) \
        if a.work_col in plist else {}
    idx = pianocore_index(a.pianocore, tier="a")
    sel = select_rows(idx, pieces, a.cap, majority_first=not a.r07_cap_rule)
    jobs = [(a.pianocore, pid, g, out, a.min_match, a.max_notes)
            for pid, g in sel.groupby("piece_id")]
    kept, excl = [], []
    with ProcessPoolExecutor(a.workers) as ex:
        for k, e in ex.map(build_piece, jobs):
            kept.extend(k)
            excl.extend(e)
    man = pd.DataFrame(kept)
    if work:
        man["work"] = man["piece_id"].map(work)
    man.to_csv(out / "manifest.csv", index=False)
    pd.DataFrame(excl).to_csv(out / "excluded.csv", index=False)
    per = man.groupby("piece_id").size()
    meta = {"args": vars(a), "seconds": round(time.time() - t0, 1), "pieces_listed": len(pieces),
            "pieces_with_items": int(man["piece_id"].nunique()) if len(man) else 0,
            "rows_selected": int(len(sel)), "renditions": int(len(man)),
            "renditions_per_piece": {"min": int(per.min()), "median": float(per.median()),
                                     "max": int(per.max())} if len(per) else {},
            "excluded": pd.DataFrame(excl)["excluded"].astype(str).str.split(":").str[0]
            .value_counts().to_dict() if excl else {},
            "by_capture_model": man["capture_model"].value_counts().to_dict() if len(man) else {},
            "digest": digest(out)}
    (out / "build_meta.json").write_text(json.dumps(meta, indent=1, default=str))
    (out / "digest.json").write_text(json.dumps(meta["digest"], indent=1))
    print(json.dumps(meta, indent=1, default=str), flush=True)


if __name__ == "__main__":
    main()
