"""R-10 secondary arm (no deciding role; DECISIONS 2026-10-05): frozen Pianist Transformer
generation (pt venv).

Copied from R-07 job/pt_train.py (``_pa`` and ``cmd_eval --job gen``). The R-06 PT adapter's
``generate`` calls the authors' ``batch_performance_render`` with top-p 0.95; this script
replaces that function in the adapter module with one that forces ``--top-p`` (default 1.0), so
the samples come from the same distribution setting as the primary SyMuPe arm. Frozen released
weights only (no checkpoint).

    python pt_gen.py --items SET/gen_items --out OUT/gen/pt_frozen_p100/fresh --k 16 --top-p 1.0
"""

from __future__ import annotations

import argparse
import functools
import importlib
import json
import os
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
R06 = HERE.parents[1] / "2026-09-27-R-06-expression-model-h2h"
PT_REPO = os.environ.get("R07_PT_REPO", str(R06 / "envs" / "PianistTransformer"))
sys.path.insert(0, str(R06 / "adapters"))
os.environ.setdefault("PT_REPO", PT_REPO)


def _pa():
    """R-07 pt_train._pa: import the PT code from PT_REPO before the adapter adds its R-06 path."""
    if PT_REPO not in sys.path:
        sys.path.insert(0, PT_REPO)
    for mod in ("src.model.generate", "src.model.pianoformer", "src.utils.midi"):
        importlib.import_module(mod)
    return importlib.import_module("pt_adapter")


def main(argv=None) -> None:
    import torch

    ap = argparse.ArgumentParser()
    ap.add_argument("--items", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--model", default=os.environ.get("R07_PT_MODEL"))
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--k", type=int, default=16)
    ap.add_argument("--top-p", type=float, default=1.0)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args(argv)
    pa = _pa()
    if a.model:
        pa.MODEL = a.model
    orig = pa.batch_performance_render

    @functools.wraps(orig)
    def render(*args, **kw):
        kw["top_p"] = a.top_p
        return orig(*args, **kw)

    pa.batch_performance_render = render
    sc = pa.PTScorer(a.device)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    paths = sorted(Path(a.items).glob("*.npz"))
    if a.limit:
        paths = paths[: a.limit]
    logp = out / "_log_gen.json"
    log = json.loads(logp.read_text())["items"] if logp.exists() else []
    for p in paths:
        dst = out / p.name
        if dst.exists():
            continue
        it = pa.load_item(p)
        t0 = time.perf_counter()
        try:
            r = sc.generate(it, a.k, a.seed)
        except Exception as e:  # noqa: BLE001
            print("FAIL", p.name, repr(e), file=sys.stderr, flush=True)
            log.append({"item": p.stem, "error": repr(e)[:300]})
            if "out of memory" in repr(e).lower():
                torch.cuda.empty_cache()
            continue
        dt = time.perf_counter() - t0
        tmp = dst.with_suffix(".tmp.npz")
        np.savez_compressed(tmp, **r, seconds=dt, k=a.k, top_p=a.top_p, seed=a.seed)
        os.replace(tmp, dst)
        n = int(len(it["pitch"]))
        log.append({"item": p.stem, "n": n, "seconds": dt, "ms_per_note": 1000 * dt / n})
        print(f"{p.stem}: {n} notes, {dt:.1f} s", flush=True)
    logp.write_text(json.dumps({"model": a.model, "k": a.k, "top_p": a.top_p, "seed": a.seed,
                                "items": log}, indent=1))
    print(f"pt gen -> {out}", flush=True)


if __name__ == "__main__":
    main()
