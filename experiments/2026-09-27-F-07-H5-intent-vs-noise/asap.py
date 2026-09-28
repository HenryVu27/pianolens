"""F-07 / H5 Disklavier check (descriptive): ASAP same-performer repeats.

Groups = (ASAP folder, heuristic performer id) with >= 2 performances. Each take is aligned with
``align_performance`` (own repeat path; notes matched across takes by score id). Same duplicate
rule as run.py (timing or smooth-tempo r > 0.98 -> same recording). Writes
``artifacts/asap_groups.jsonl``.

    uv run python experiments/2026-09-27-F-07-H5-intent-vs-noise/asap.py
"""

from __future__ import annotations

import json
import sys
import time
import warnings
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from run import THRESHOLDS, _components, _jsonable  # noqa: E402

ART = HERE / "artifacts"


def main() -> None:
    warnings.simplefilter("ignore")
    from pianolens.align import align_performance
    from pianolens.data.asap import asap_index, load_asap_performance, load_asap_score
    from pianolens.features.takes import TakesConfig, decompose_takes, take_structure
    from pianolens.features.tempo import tempo_model

    md = asap_index()
    sizes = md.groupby(["folder", "performer_id"]).size()
    keys = [k for k, n in sizes.items() if n >= 2]
    print(f"ASAP groups with >= 2: {len(keys)}", flush=True)
    t0 = time.time()
    with (ART / "asap_groups.jsonl").open("w") as fh:
        for folder, performer in keys:
            rows = md[(md["folder"] == folder) & (md["performer_id"] == performer)]
            out: dict = {"folder": folder, "piece_id": rows["piece_id"].iloc[0],
                         "performer_id": performer, "errors": []}
            aps, tempos, ids = [], [], []
            for _, r in rows.iterrows():
                try:
                    ap = align_performance(load_asap_score(r), load_asap_performance(r))
                    tempos.append(tempo_model(ap))
                    aps.append(ap)
                    ids.append(Path(r["midi_performance"]).stem)
                except Exception as e:  # noqa: BLE001
                    out["errors"].append(repr(e)[:200])
            out["takes"] = ids
            if len(aps) < 2:
                fh.write(json.dumps(_jsonable(out)) + "\n")
                continue
            full = decompose_takes(aps, tempos=tempos, take_ids=ids)
            pr = full.pairs[full.pairs["channel"].isin(["timing", "tempo"])]
            pw = pr.pivot_table(index=["take_a", "take_b"], columns="channel",
                                values="r").reset_index()
            out["pairs"] = pw.to_dict("records")
            out["n_common_timing"] = int(full.summary.set_index("channel").loc["timing", "n"])
            out["by_threshold"] = {}
            for thr in THRESHOLDS:
                links = [(a, b) for a, b, rt, rp in zip(pw["take_a"], pw["take_b"], pw["timing"],
                                                         pw["tempo"], strict=True)
                         if (np.isfinite(rt) and rt > thr) or (np.isfinite(rp) and rp > thr)]
                comps = _components(ids, links)
                keep = sorted(c[0] for c in comps)
                res: dict = {"k": len(keep), "kept": keep}
                if len(keep) >= 2:
                    sub = [ids.index(t) for t in keep]
                    dec = decompose_takes([aps[i] for i in sub], tempos=[tempos[i] for i in sub],
                                          take_ids=keep)
                    res["summary"] = dec.summary.to_dict("records")
                    res["structure"] = take_structure(dec, TakesConfig()).to_dict("records")
                out["by_threshold"][str(thr)] = res
            fh.write(json.dumps(_jsonable(out)) + "\n")
            fh.flush()
            print(f"{folder} {performer}: {len(aps)} takes, "
                  f"k(0.98)={out['by_threshold']['0.98']['k']} "
                  f"({time.time() - t0:.0f} s)", flush=True)


if __name__ == "__main__":
    main()
