"""BL-17: seeded draw of 24 simple-meter + 6 compound-meter DCML Romantic movements (R-08d's 5
excluded), the disguise parameters per movement, and the undisguised (U) subset. See README
"Movement selection" and "Disguise".

    uv run python experiments/2026-09-29-BL-17-romantic-llm/draw.py --sizes   # pool only
    uv run python experiments/2026-09-29-BL-17-romantic-llm/draw.py           # draw
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
R08D = ROOT / "experiments" / "2026-09-28-R-08d-llm-romantic-repertoire"
R08B = ROOT / "experiments" / "2026-09-28-R-08b-llm-memorisation-control"
ART = HERE / "artifacts"
SEED = 20261002
# per-corpus allocation, fixed in the pre-registration
ALLOC_SIMPLE = {"chopin_mazurkas": 10, "grieg_lyric_pieces": 8, "tchaikovsky_seasons": 2,
                "schumann_kinderszenen": 2, "liszt_pelerinage": 2}
ALLOC_COMPOUND = {"grieg_lyric_pieces": 3, "tchaikovsky_seasons": 1, "liszt_pelerinage": 2}
N_U = 8  # simple-stratum movements that also get one undisguised run
SEMITONES = [-6, -5, -4, -3, -2, -1, 1, 2, 3, 4, 5, 6]  # R-08b
OFFSET_RANGE = (20, 480)  # R-08b: integers(20, 480) -> 20..479


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def compound(ts: str) -> bool:
    return all(int(t.split("/")[0]) in (6, 9, 12) for t in ts.split())


def pool() -> pd.DataFrame:
    """R-08d's pool (every labelled movement of the 5 corpora, rendered size with id X), plus
    the stratum and the R-08d exclusion."""
    D = _load("r08d_draw", R08D / "draw.py")
    P = D.pool()
    used = {(p["corpus"], p["stem"]) for p in
            json.loads((R08D / "artifacts" / "selection.json").read_text())["picks"]}
    P["in_r08d"] = [(c, s) in used for c, s in zip(P.corpus, P.stem, strict=True)]
    base = (P.ends_folded >= D.MIN_ENDS) & P.unfold_validated & (P.chars_X <= D.MAX_CHARS) \
        & ~P.in_r08d
    P["stratum"] = np.where(base & P.simple_meter, "simple",
                            np.where(base & P.timesig.map(compound), "compound", ""))
    return P


def main(draw: bool) -> None:
    P = pool()
    for stratum, alloc in (("simple", ALLOC_SIMPLE), ("compound", ALLOC_COMPOUND)):
        g = P[P.stratum == stratum]
        print(f"{stratum}: " + ", ".join(f"{c} {int((g.corpus == c).sum())} (draw {n})"
                                         for c, n in alloc.items()))
    if not draw:
        return
    rng = np.random.default_rng(SEED)
    picks = []
    for stratum, alloc in (("simple", ALLOC_SIMPLE), ("compound", ALLOC_COMPOUND)):
        for corpus, n in alloc.items():
            members = sorted(P[(P.stratum == stratum) & (P.corpus == corpus)].stem)
            for i in sorted(rng.choice(len(members), size=n, replace=False).tolist()):
                row = P[(P.corpus == corpus) & (P.stem == members[i])].iloc[0]
                picks.append({"stratum": stratum, "corpus": corpus, "stem": members[i],
                              "timesig": row.timesig, "chars_X": int(row.chars_X),
                              "ends_folded": int(row.ends_folded)})
    # blind ids P01..P30 by a seeded permutation over all picks
    for p, k in zip(picks, rng.permutation(len(picks)).tolist(), strict=True):
        p["id"] = f"P{k + 1:02d}"
    # disguise parameters (R-08b's distributions), in id order
    picks.sort(key=lambda p: p["id"])
    for p in picks:
        p["semitones"] = int(rng.choice(SEMITONES))
        p["bar_offset"] = int(rng.integers(*OFFSET_RANGE))
    # the undisguised subset: N_U of the simple-stratum picks (in id order)
    simple_ids = [p["id"] for p in picks if p["stratum"] == "simple"]
    u = sorted(rng.choice(simple_ids, size=N_U, replace=False).tolist())
    for p in picks:
        p["undisguised_run"] = p["id"] in u
    out = {"seed": SEED, "alloc_simple": ALLOC_SIMPLE, "alloc_compound": ALLOC_COMPOUND,
           "n_u": N_U, "semitones_choices": SEMITONES, "offset_range": list(OFFSET_RANGE),
           "pool": P.to_dict(orient="records"), "picks": picks}
    ART.mkdir(exist_ok=True)
    (ART / "selection.json").write_text(json.dumps(out, indent=1))
    for p in picks:
        print({k: p[k] for k in ("id", "stratum", "corpus", "stem", "timesig", "chars_X",
                                 "ends_folded", "undisguised_run")})


if __name__ == "__main__":
    main(draw="--sizes" not in sys.argv)
