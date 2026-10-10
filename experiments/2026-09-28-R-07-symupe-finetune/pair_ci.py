"""R-07: paired pt_E - pt_frozen differences (pre-registered secondary comparison, README
"Baselines": "Pianist Transformer frozen vs fine-tuned (pt_E), same (a) and (b)").

`job/summarize_eval.py` only differences each arm against frozen SyMuPe, so on the RTX box the
pt_E - pt_frozen difference was computed afterwards with the summariser's own `boot_ci` (two-way
passage x performer pigeonhole bootstrap, 2,000 resamples, seed 0, unweighted mean over works) and
`t_interval` (over works, only when there are six or fewer works). That box script was never
committed (AUDIT.md section 6 / section 9 item 6). This file is its committed replacement: it
rebuilds the three JSONs from `results/<set>/a_per_rendition.csv` with the same functions and the
same pairing as the summariser's `<arm>-frozen` block (inner join on `stem`), and checks them
against the committed files.

    uv run python experiments/2026-09-28-R-07-symupe-finetune/pair_ci.py            # check only
    uv run python experiments/2026-09-28-R-07-symupe-finetune/pair_ci.py --write    # rewrite

Outputs (same layout as the box script):
    results/pt_E_vs_pt_frozen.json        sets P, V, A
    results/pt_E_vs_pt_frozen_R10u.json   set R10u
    results/pt_E_vs_pt_frozen_R10s.json   set R10s
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "job"))
import summarize_eval as se  # noqa: E402  (job/summarize_eval.py, unchanged since e4becf8)

ARM, BASE = "pt_E", "pt_frozen"
OUTPUTS = {
    "pt_E_vs_pt_frozen.json": ("P", "V", "A"),
    "pt_E_vs_pt_frozen_R10u.json": ("R10u",),
    "pt_E_vs_pt_frozen_R10s.json": ("R10s",),
}


def pair(A: pd.DataFrame, arm: str = ARM, base: str = BASE) -> dict:
    """Mirror of summarize_eval.main's `<arm>-frozen` block with `base` in place of frozen."""
    b = A[A["arm"] == base].set_index("stem")
    g = A[A["arm"] == arm].set_index("stem")
    j = g.join(b[list(se.TARGETS) + ["composite"]], rsuffix="_base", how="inner")
    for t in (*se.TARGETS, "composite"):
        j[f"d_{t}"] = j[t] - j[f"{t}_base"]
    j = j.reset_index()
    out: dict = {t: se.boot_ci(j, f"d_{t}", pooled=False) for t in (*se.TARGETS, "composite")}
    out["per_work_composite"] = j.groupby("work")["d_composite"].mean().to_dict()
    if j["work"].nunique() <= 6:
        out["t_interval_composite"] = se.t_interval(j, "d_composite")
    out["n"] = int(len(j))
    return out


def same(a, b) -> bool:
    """Exact equality of parsed JSON (floats compared with ==, NaN equal to NaN)."""
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(same(a[k], b[k]) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b, strict=True))
    if isinstance(a, float) and isinstance(b, float) and np.isnan(a) and np.isnan(b):
        return True
    return type(a) is type(b) and a == b


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--results", type=Path, default=HERE / "results")
    ap.add_argument("--write", action="store_true", help="rewrite the JSONs instead of checking")
    a = ap.parse_args(argv)
    for name, sets in OUTPUTS.items():
        res = {s: pair(pd.read_csv(a.results / s / "a_per_rendition.csv")) for s in sets}
        text = json.dumps(res, indent=1, default=float)
        path = a.results / name
        if a.write:
            path.write_text(text)
            print(f"wrote {path}")
            continue
        committed_text = path.read_text()
        parsed_equal = same(json.loads(text), json.loads(committed_text))
        bytes_equal = text == committed_text
        for s in sets:
            c = res[s]["composite"]
            print(f"{name:32s} {s:5s} n={res[s]['n']:5d} composite {c[0]:+.4f} "
                  f"[{c[1]:+.4f}, {c[2]:+.4f}]")
        print(f"{name:32s} parsed values equal: {parsed_equal}; bytes equal: {bytes_equal}")
        assert parsed_equal, f"{name}: recomputed values differ from the committed file"


if __name__ == "__main__":
    main()
