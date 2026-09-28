"""R-08d: seeded draw of 5 Romantic movements, one per DCML corpus, each from a seeded
within-corpus size tertile. See README "Movement selection".

    uv run python experiments/2026-09-28-R-08d-llm-romantic-repertoire/draw.py --sizes  # pool only
    uv run python experiments/2026-09-28-R-08d-llm-romantic-repertoire/draw.py          # draw
"""

from __future__ import annotations

import json
import logging
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
R08A = ROOT / "experiments" / "2026-09-28-R-08a-llm-phrase-pilot"
sys.path.insert(0, str(R08A))
SEED = 20261001
CORPORA = ("chopin_mazurkas", "grieg_lyric_pieces", "tchaikovsky_seasons",
           "schumann_kinderszenen", "liszt_pelerinage")  # draw order, fixed
MIN_ENDS = 5  # folded DCML phrase ends (}, }{), as D-13's `eligible`
MAX_CHARS = 120_000  # rendered characters with the placeholder id X
D13 = ROOT / "data" / "interim" / "dcml_romantic" / "pieces.csv"


def meter_class(ts: str) -> str:
    num = int(ts.split("/")[0])
    return "simple" if num in (2, 3, 4) else "compound" if num in (6, 9, 12) else "other"


def pool() -> pd.DataFrame:
    """Every labelled movement of the 5 corpora with its filters and rendered size."""
    warnings.filterwarnings("ignore")
    logging.disable(logging.WARNING)
    from common import render  # R-08a renderer, unchanged

    from pianolens.data import dcml

    rows = []
    for corpus in CORPORA:
        for stem in dcml.pieces(corpus, labelled=True):
            s = dcml.load_score(corpus, stem, tempo_word=False)
            ms = dcml.read_facet(corpus, stem, "measures")
            tss = list(dict.fromkeys(ms["timesig"]))
            lab = dcml.load_labels(corpus, stem)
            ends = int(lab["phraseend"].isin(["}", "}{"]).sum())
            rows.append({"corpus": corpus, "stem": stem, "timesig": " ".join(tss),
                         "simple_meter": all(meter_class(t) == "simple" for t in tss),
                         "unfold_validated": bool(s.meta["unfold_validated"]),
                         "ends_folded": ends,
                         "chars_X": len(render(s, "X").text)})
            print(rows[-1], flush=True)
    P = pd.DataFrame(rows)
    P["eligible"] = (P.ends_folded >= MIN_ENDS) & P.simple_meter & P.unfold_validated \
        & (P.chars_X <= MAX_CHARS)
    # cross-check against D-13's table (eligible_simple and unfold flags)
    d = pd.read_csv(D13).set_index(["corpus", "stem"])
    for _, r in P.iterrows():
        x = d.loc[(r.corpus, r.stem)]
        assert bool(x.eligible_simple) == (r.ends_folded >= MIN_ENDS and r.simple_meter), r.stem
        assert bool(x.unfold_validated) == r.unfold_validated, r.stem
    return P


def tertiles(P: pd.DataFrame) -> dict[str, list[list[str]]]:
    out = {}
    for corpus in CORPORA:
        g = P[(P.corpus == corpus) & P.eligible]
        order = g.sort_values(["chars_X", "stem"])["stem"].tolist()
        out[corpus] = [sorted(a.tolist()) for a in np.array_split(np.array(order, dtype=object), 3)]
    return out


def main(draw: bool) -> None:
    P = pool()
    T = tertiles(P)
    for corpus in CORPORA:
        g = P[P.corpus == corpus]
        n5 = int((g.ends_folded >= MIN_ENDS).sum())
        print(f"{corpus}: labelled {len(g)}, >= {MIN_ENDS} ends {n5}"
              f", + simple {int(((g.ends_folded >= MIN_ENDS) & g.simple_meter).sum())}"
              f", + unfold validated "
              f"{int(((g.ends_folded >= MIN_ENDS) & g.simple_meter & g.unfold_validated).sum())}"
              f", + <= {MAX_CHARS:,} chars (eligible) {int(g.eligible.sum())}; tertile sizes "
              f"{[len(t) for t in T[corpus]]}")
        size = g.set_index("stem")["chars_X"]
        for i, t in enumerate(T[corpus], start=1):
            print(f"   T{i}: " + ", ".join(f"{s} ({size[s]:,})" for s in t))
    if not draw:
        return
    rng = np.random.default_rng(SEED)
    # tertile per corpus: 1, 2, 3 once each plus two distinct extra tertiles, shuffled over the
    # corpora in CORPORA order
    extra = (rng.choice(3, size=2, replace=False) + 1).tolist()
    assign = rng.permutation(np.array([1, 2, 3] + extra)).tolist()
    picks = []
    for corpus, t in zip(CORPORA, assign, strict=True):
        members = T[corpus][t - 1]
        stem = members[int(rng.choice(len(members)))]
        row = P[(P.corpus == corpus) & (P.stem == stem)].iloc[0]
        picks.append({"corpus": corpus, "stem": stem, "tertile": f"T{t}",
                      "timesig": row.timesig, "chars_X": int(row.chars_X)})
    # blind ids R1..R5 by a seeded permutation, so an id does not encode the corpus order
    for p, k in zip(picks, rng.permutation(5).tolist(), strict=True):
        p["id"] = f"R{k + 1}"
    picks.sort(key=lambda p: p["id"])
    out = {"seed": SEED, "min_ends": MIN_ENDS, "max_chars": MAX_CHARS,
           "tertile_assignment": dict(zip(CORPORA, assign, strict=True)),
           "pool": P.to_dict(orient="records"), "tertiles": T, "picks": picks}
    (HERE / "artifacts").mkdir(exist_ok=True)
    (HERE / "artifacts" / "selection.json").write_text(json.dumps(out, indent=1))
    for p in picks:
        print(p)


if __name__ == "__main__":
    main(draw="--sizes" not in sys.argv)
