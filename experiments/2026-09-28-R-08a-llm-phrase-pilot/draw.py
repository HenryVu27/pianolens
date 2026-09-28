"""R-08a: seeded draw of the 5 pilot movements (one per stratum). See README "Movement selection".

    uv run python experiments/2026-09-28-R-08a-llm-phrase-pilot/draw.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SEED = 20260928
STRATA = {
    "S1_middle": ["kv284_2", "kv330_2", "kv331_2", "kv332_2", "kv333_2", "kv457_2", "kv533_2"],
    "S2_first_4_4": ["kv284_1", "kv333_1", "kv457_1"],
    "S3_first_other": ["kv330_1", "kv332_1", "kv533_1"],
    "S4_finale_duple": ["kv330_3", "kv331_3", "kv333_3", "kv533_3"],
    "S5_finale_triple": ["kv332_3", "kv457_3"],
}
EXCLUDED = {"kv284_3": "variations, 4661 onsets", "kv331_1": "variations, 3475 onsets"}


def main() -> None:
    train = {f"kv{k}_{m}" for k in (279, 280, 281, 282, 283) for m in (1, 2, 3)}
    allm = [s for v in STRATA.values() for s in v]
    assert len(allm) == len(set(allm)) == 19 and not set(allm) & train
    rng = np.random.default_rng(SEED)
    picks = []
    for i, (name, members) in enumerate(STRATA.items(), start=1):
        members = sorted(members)
        stem = members[int(rng.choice(len(members)))]
        picks.append({"id": f"M{i}", "stem": stem, "stratum": name})
    out = {"seed": SEED, "strata": STRATA, "excluded": EXCLUDED, "picks": picks}
    (HERE / "artifacts").mkdir(exist_ok=True)
    (HERE / "artifacts" / "selection.json").write_text(json.dumps(out, indent=1))
    for p in picks:
        print(p)


if __name__ == "__main__":
    main()
