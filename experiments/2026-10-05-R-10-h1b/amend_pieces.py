"""R-10 pre-run amendments A1, A2, A4 and R3 (Mac, project env; expert data and scores only).

Writes, under pieces/ (committed before the box run):
  content_overlap.csv            A1 check for every fresh piece: distinct 12-onset pitch-set n-grams
                                 of its majority refined score (first 1,500 onsets) found in any
                                 held refined score, and the held piece with the most hits
  excluded_content_overlap.csv   A1: fresh pieces with >= 10 hits (excluded from every statistic)
  duplicate_renditions.csv       A2: within-piece rendition pairs whose deviations from the expert
                                 mean curve correlate > 0.9 (log IOI or centered velocity); the
                                 later one in manifest order is dropped (review appendix rule)
  sibling_flag.csv               A4: another piece of the same PianoCoRe composition title, or the
                                 same composer and opus number, is PERiScoPe-paired or possibly
                                 paired
  r10u_content_overlap.csv       R3: the same content check for R-07's R10u development pieces
  amendment_summary.json         counts

Held pieces (A1): R-07 split rows with n_periscope_paired > 0, or periscope_possible, or role in
P / V / A / R10u / R10s; all their refined scores in PianoCoRe (any tier).

    uv run python experiments/2026-10-05-R-10-h1b/amend_pieces.py
"""

from __future__ import annotations

import json
import re
import sys
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "job"))
import summarize_h1b as sh  # noqa: E402

from pianolens.data.pianocore import (  # noqa: E402
    DEFAULT_ROOT,
    REFINED_PREFIX,
    REFINED_ZIP,
    _midi_note_keys,
    pianocore_index,
)

SPLIT = HERE.parent / "2026-09-28-R-07-symupe-finetune" / "split" / "pieces.csv"
FRESH_SET = HERE / "artifacts" / "sets" / "fresh"
PIECES = HERE / "pieces"
NGRAM, MAX_ONSETS, HIT_LIMIT, DUP_R = 12, 1500, 10, 0.9
EVAL_ROLES = {"P", "V", "A", "R10u", "R10s"}


def onset_tuples(zf: zipfile.ZipFile, rel: str) -> list[tuple]:
    keys = _midi_note_keys(zf.read(REFINED_PREFIX + rel))
    by = defaultdict(list)
    for tick, pitch in keys:
        by[tick].append(pitch)
    return [tuple(sorted(by[t])) for t in sorted(by)]


def ngrams(seq: list[tuple], limit: int | None = None) -> set:
    s = seq[:limit] if limit else seq
    return {tuple(s[i:i + NGRAM]) for i in range(len(s) - NGRAM + 1)}


def majority_scores(idx: pd.DataFrame, pieces) -> dict:
    g = idx[idx["piece_id"].isin(pieces) & (idx["performance_dataset"] != "ASAP")]
    n = g.groupby(["piece_id", "refined_score_midi_path"]).size().rename("n").reset_index()
    n = n.sort_values(["piece_id", "n", "refined_score_midi_path"], ascending=[True, False, True])
    return dict(n.drop_duplicates("piece_id")[["piece_id", "refined_score_midi_path"]]
                .itertuples(index=False, name=None))


def content_check(zf, held_paths: dict, query: dict) -> pd.DataFrame:
    """held_paths: rel -> held piece id; query: piece -> majority score rel."""
    index: dict[tuple, set] = defaultdict(set)
    for rel, hp in held_paths.items():
        try:
            seq = onset_tuples(zf, rel)
        except Exception as e:  # noqa: BLE001
            print("skip", rel, repr(e)[:80])
            continue
        for g in ngrams(seq):
            index[g].add(hp)
    rows = []
    for piece, rel in query.items():
        q = ngrams(onset_tuples(zf, rel), MAX_ONSETS)
        per = Counter()
        hits = 0
        for g in q:
            other = index.get(g, set()) - {piece}   # never count the piece's own scores
            if other:
                hits += 1
                per.update(other)
        best, nb = per.most_common(1)[0] if per else ("", 0)
        rows.append({"piece_id": piece, "ngrams": len(q), "hits": hits,
                     "top_held_piece": best, "top_held_hits": nb})
    return pd.DataFrame(rows).sort_values("hits", ascending=False)


def duplicates(set_dir: Path) -> pd.DataFrame:
    """Review appendix rule, verbatim in substance."""
    man = pd.read_csv(set_dir / "manifest.csv")
    man = man[man["kind"] == "real"]
    cache, rows = {}, []

    def nz(X):
        X = sh._fill(X)
        X = X - X.mean(0)
        X = X - X.mean(1, keepdims=True)
        return X / np.linalg.norm(X, axis=1, keepdims=True)

    for piece, g in man.groupby("passage"):
        gi = sh.load_item(set_dir / "gen_items" / (sh._slug(piece) + ".npz"))
        idx = pd.Index(np.unique(np.round(gi["score_onset_q"], 6)))
        V, T = sh.expert_matrix(set_dir, g["stem"].tolist(), idx, cache)
        keep = (np.isfinite(V).mean(0) >= .5) & (np.isfinite(T).mean(0) >= .5)
        V, T = V[:, keep], T[:, keep]
        Ct = nz(T) @ nz(T).T
        Cv = nz(sh.center_rows(V)) @ nz(sh.center_rows(V)).T
        C = np.maximum(Ct, Cv)
        pid, gone = g["performance_id"].tolist(), set()
        src = g["capture_model"].tolist()
        for i in range(len(pid)):
            if i in gone:
                continue
            for j in range(i + 1, len(pid)):
                if j not in gone and C[i, j] > DUP_R:
                    gone.add(j)
                    rows.append({"piece_id": piece, "dropped_performance_id": pid[j],
                                 "dropped_capture_model": src[j], "kept_performance_id": pid[i],
                                 "kept_capture_model": src[i], "r_log_ioi": float(Ct[i, j]),
                                 "r_velocity": float(Cv[i, j]), "r_max": float(C[i, j])})
    return pd.DataFrame(rows)


# collections whose numbers carry separate titles in PianoCoRe (review F4, by hand)
MANUAL_COLLECTION = {f"mozart_k{i}": "Mozart early keyboard pieces K. 1-5 (Nannerl Notebook)"
                     for i in range(1, 6)}


def opus_key(piece_id: str, composer: str, composition: str) -> str | None:
    if piece_id in MANUAL_COLLECTION:
        return MANUAL_COLLECTION[piece_id]
    m = re.search(r"\bop\.?\s*_?(\d+)", f"{composition} {piece_id.replace('_', ' ')}",
                  flags=re.IGNORECASE)
    return f"{composer}|op{m.group(1)}" if m else None


def sibling_flags(sp: pd.DataFrame, idx: pd.DataFrame, fresh: list[str]) -> pd.DataFrame:
    comp = idx.groupby("piece_id")["composition"].first()
    compo = idx.groupby("piece_id")["composer"].first()
    t = sp.set_index("piece_id")
    paired = t[(t["n_periscope_paired"] > 0) | t["periscope_possible"]].index
    pc = {(compo.get(p), comp.get(p)) for p in paired if p in comp.index}
    po = {opus_key(p, compo.get(p, ""), comp.get(p, "")) for p in paired if p in comp.index}
    po.discard(None)
    rows = []
    for f in fresh:
        key_c = (compo.get(f), comp.get(f))
        key_o = opus_key(f, compo.get(f, ""), comp.get(f, ""))
        by_c = key_c in pc
        by_o = key_o is not None and key_o in po
        sib = [p for p in paired if p in comp.index and ((compo.get(p), comp.get(p)) == key_c
               or (key_o is not None and opus_key(p, compo.get(p, ""), comp.get(p, "")) == key_o))]
        rows.append({"piece_id": f, "composition": comp.get(f), "sibling_paired": by_c or by_o,
                     "by_composition": by_c, "by_opus": by_o,
                     "paired_siblings": ";".join(sorted(sib))[:500]})
    return pd.DataFrame(rows)


def main() -> None:
    sp = pd.read_csv(SPLIT)
    fresh_list = pd.read_csv(PIECES / "fresh_pieces.csv")
    fresh = fresh_list["piece_id"].tolist()
    idx_a = pianocore_index(tier="a")
    idx_c = pianocore_index(tier="c")
    held_ids = set(sp.loc[(sp["n_periscope_paired"] > 0) | sp["periscope_possible"]
                          | sp["role"].isin(EVAL_ROLES), "piece_id"])
    hp = idx_c[idx_c["piece_id"].isin(held_ids) & idx_c["refined_score_midi_path"].notna()]
    held_paths = dict(hp.drop_duplicates("refined_score_midi_path")[
        ["refined_score_midi_path", "piece_id"]].itertuples(index=False, name=None))
    zf = zipfile.ZipFile(Path(DEFAULT_ROOT) / REFINED_ZIP)
    print("held score files", len(held_paths), flush=True)

    # A1 on the fresh set (held set excludes the fresh pieces by construction)
    A1 = content_check(zf, held_paths, majority_scores(idx_a, fresh))
    A1.to_csv(PIECES / "content_overlap.csv", index=False)
    ex = A1[A1["hits"] >= HIT_LIMIT]
    ex.to_csv(PIECES / "excluded_content_overlap.csv", index=False)
    print(A1.head(6).to_string(index=False))

    # R3 on R-07's R10u pieces: held set minus the R10u ids themselves (their own scores)
    r10u = sp.loc[sp["role"] == "R10u", "piece_id"].tolist()
    R3 = content_check(zf, held_paths, majority_scores(idx_a, r10u))
    t = sp.set_index("piece_id")
    R3["r07_unseen"] = R3["piece_id"].map(
        lambda p: bool(t.at[p, "r02"] and t.at[p, "n_periscope_paired"] == 0))
    R3["top_held_paired"] = R3["top_held_piece"].map(
        lambda p: bool(p in t.index and (t.at[p, "n_periscope_paired"] > 0
                                         or t.at[p, "periscope_possible"])))
    R3.to_csv(PIECES / "r10u_content_overlap.csv", index=False)
    print(R3.head(10).to_string(index=False))

    # A2 on the built fresh set
    D = duplicates(FRESH_SET)
    D.to_csv(PIECES / "duplicate_renditions.csv", index=False)

    # A4 sibling flag
    S = sibling_flags(sp, idx_c, fresh)
    S.to_csv(PIECES / "sibling_flag.csv", index=False)

    man = pd.read_csv(FRESH_SET / "manifest.csv")
    man = man[~man["piece_id"].isin(ex["piece_id"])
              & ~man["performance_id"].isin(D["dropped_performance_id"])]
    per = man.groupby("piece_id").size()
    prim = per[per >= 20].index
    summ = {"A1_excluded": ex["piece_id"].tolist(),
            "A1_max_hits_other_pieces": int(A1.loc[A1["hits"] < HIT_LIMIT, "hits"].max()),
            "A2_dropped_renditions": int(len(D)),
            "A2_pieces_affected": int(D["piece_id"].nunique()) if len(D) else 0,
            "primary_pieces_after": int(len(prim)),
            "primary_works_after": int(fresh_list.set_index("piece_id").loc[prim, "work"]
                                       .nunique()),
            "primary_renditions_after": int(per[prim].sum()),
            "sibling_paired_primary": int(S.set_index("piece_id").loc[prim, "sibling_paired"]
                                          .sum()),
            "R3_r10u_flagged": R3.loc[R3["hits"] >= HIT_LIMIT, "piece_id"].tolist(),
            "R3_r10u_unseen_flagged_by_paired": R3.loc[
                (R3["hits"] >= HIT_LIMIT) & R3["r07_unseen"] & R3["top_held_paired"],
                "piece_id"].tolist()}
    (PIECES / "amendment_summary.json").write_text(json.dumps(summ, indent=1))
    print(json.dumps(summ, indent=1))


if __name__ == "__main__":
    main()
