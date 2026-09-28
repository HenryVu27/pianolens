"""R-02 exploratory (post hoc, not in the verdict): total-variance held-out R², R² vs n.

(a) "Total-variance" held-out R²: the same 5 splits as ``heldout_r2_curve``, but the held-out
    curves' sum of squares is taken about zero (each curve is already centered on its own mean),
    so the training mean curve counts as explained. k = 0 is the mean curve alone.
(b) Held-out R² at k = 10 (column-centered, as pre-registered) by number of performances, using
    the "all" analysis, and by nested subsamples of the 100 pieces with more than 300 performances.

    uv run python experiments/2026-09-27-R-02-expression-dimensionality/extra.py
"""

from __future__ import annotations

import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from analyze import ART, CURVES, N_SUB, joint, load_blocks  # noqa: E402

from pianolens.eval.dimensionality import heldout_r2_curve  # noqa: E402

KS = list(range(0, 41))


def total_r2(x: np.ndarray, n_splits: int = 5, seed: int = 0) -> np.ndarray:
    n = len(x)
    n_te = max(1, round(0.2 * n))
    out = np.zeros(len(KS))
    for s in range(n_splits):
        perm = np.random.default_rng(seed + s).permutation(n)
        te, tr = x[perm[:n_te]], x[perm[n_te:]]
        mu = tr.mean(0)
        _, _, vt = np.linalg.svd(tr - mu, full_matrices=False)
        d = te - mu
        sc = d @ vt.T
        tot = (te**2).sum()
        base = (d**2).sum()
        for j, k in enumerate(KS):
            out[j] += 1 - (base - (sc[:, :k] ** 2).sum()) / tot
    return out / n_splits


def piece(path: Path) -> list[dict]:
    b = load_blocks(path)
    if b is None or len(b["T"]) < N_SUB:
        return []
    n = len(b["T"])
    sub = np.sort(np.random.default_rng(0).permutation(n)[:N_SUB])
    rows = []
    for blk, x in (("joint", joint(b["T"][sub], b["Vs"][sub])), ("tempo", b["T"][sub])):
        r = total_r2(x)
        k80 = next((k for k, v in zip(KS, r, strict=True) if v >= 0.8), 41)
        rows.append({"piece_id": b["info"]["piece_id"], "kind": "total_r2", "block": blk,
                     "n": N_SUB, "k80_ho_total": k80, "r2_k0": r[0], "r2_k5": r[5],
                     "r2_k10": r[10], "r2_k20": r[20]})
    if n > 300:
        rng = np.random.default_rng(1)
        order = rng.permutation(n)
        for m in (50, 100, 200, 300):
            x = joint(b["T"][order[:m]], b["Vs"][order[:m]])
            h = heldout_r2_curve(x, [10, 20], seed=0)
            rows.append({"piece_id": b["info"]["piece_id"], "kind": "nested_n", "block": "joint",
                         "n": m, "r2_k10": h[0], "r2_k20": h[1]})
    return rows


def main() -> None:
    files = sorted(CURVES.glob("*.npz"))
    rows = []
    with ProcessPoolExecutor(13) as ex:
        for r in ex.map(piece, files, chunksize=4):
            rows.extend(r)
    df = pd.DataFrame(rows)
    df.to_csv(ART / "extra_exploratory.csv", index=False)
    t = df[df.kind == "total_r2"]
    print("(a) total-variance held-out R², n = 50 (median over pieces)")
    print(t.groupby("block")[["r2_k0", "r2_k5", "r2_k10", "r2_k20", "k80_ho_total"]].median())
    for blk, g in t.groupby("block"):
        print(blk, "share k80_ho_total <= 10:", round(float(np.mean(g.k80_ho_total <= 10)), 3),
              "> 20:", round(float(np.mean(g.k80_ho_total > 20)), 3))
    nn = df[df.kind == "nested_n"]
    print("(b) joint held-out R² (column-centered) vs n, pieces with > 300 performances:",
          nn.piece_id.nunique())
    print(nn.groupby("n")[["r2_k10", "r2_k20"]].median())


if __name__ == "__main__":
    main()
