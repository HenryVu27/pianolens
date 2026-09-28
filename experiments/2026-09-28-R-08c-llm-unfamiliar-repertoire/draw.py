"""R-08c: seeded draw of 5 J. C. Bach movements, one per rendered-size stratum. See README
"Movement selection".

    uv run python experiments/2026-09-28-R-08c-llm-unfamiliar-repertoire/draw.py
"""

from __future__ import annotations

import json
import logging
import sys
import warnings
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
R08A = ROOT / "experiments" / "2026-09-28-R-08a-llm-phrase-pilot"
sys.path.insert(0, str(R08A))
SEED = 20260930
EXCLUDED_PREFIXES = ("wa02", "wa03", "wa04")  # op. 5 nos. 2-4: Mozart's K.107 sources


def main() -> None:
    warnings.filterwarnings("ignore")
    logging.disable(logging.WARNING)
    from common import render  # R-08a renderer, unchanged

    from pianolens.data import dcml_jc_bach as jc

    stems = [s for s in jc.pieces() if not s.startswith(EXCLUDED_PREFIXES)]
    assert len(stems) == 21, len(stems)
    sizes = {s: len(render(jc.load_score(s, tempo_word=False), "X").text) for s in stems}
    order = sorted(stems, key=lambda s: (sizes[s], s))
    strata = [list(a) for a in np.array_split(np.array(order, dtype=object), 5)]
    assert [len(a) for a in strata] == [5, 4, 4, 4, 4]
    rng = np.random.default_rng(SEED)
    picks = []
    for i, members in enumerate(strata, start=1):
        members = sorted(members)
        stem = members[int(rng.choice(len(members)))]
        picks.append({"id": f"Q{i}", "stem": stem, "stratum": f"S{i}", "chars_X": sizes[stem]})
    out = {"seed": SEED, "excluded_prefixes": list(EXCLUDED_PREFIXES), "sizes_chars_X": sizes,
           "strata": {f"S{i}": sorted(m) for i, m in enumerate(strata, start=1)},
           "picks": picks}
    (HERE / "artifacts").mkdir(exist_ok=True)
    (HERE / "artifacts" / "selection.json").write_text(json.dumps(out, indent=1))
    for i, m in enumerate(strata, start=1):
        print(f"S{i}: " + ", ".join(f"{s} ({sizes[s]:,})" for s in m))
    for p in picks:
        print(p)


if __name__ == "__main__":
    main()
