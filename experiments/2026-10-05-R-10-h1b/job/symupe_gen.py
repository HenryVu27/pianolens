"""R-10 generation runner for frozen SyMuPe EncDec-base (symupe venv).

Copied from R-07 job/symupe_eval.py (``gen``), with the nucleus threshold as a parameter. R-10
generates two sample sets: top-p 0.95 (arm frozen_p95, the registered H1b-consensus arm) and
top-p 1.0 (arm frozen_p100, the registered H1b-axes arm; DECISIONS 2026-10-05). Everything
else is the R-06 adapter: same score MIDI, conditioning (one tempo = 60 / spq_cond, one velocity =
vel_cond), ``use_score_context=True``, per-note onset / duration / velocity in score order.

Trap (found in the R-10 dry run): for EncDec-base, ``perform_score(lm_top_p=...)`` is ignored.
The seq2seq generator's ``_prepare_generator_kwargs`` reads ``top_p`` (or ``mlm_top_p``) from the
extra kwargs and defaults to 0.95. So every R-06 / R-07 SyMuPe sample was drawn at top-p 0.95,
including R-07's S-TYP "top-p 1.0" reference samples. This script passes ``top_p`` explicitly and
checks at start-up that the generator receives it.

    python symupe_gen.py --items SET/gen_items --out OUT/gen/frozen_p100/fresh --k 16 --top-p 1.0

Resumable: an item whose output exists is skipped. One output per item, written after success;
failures are logged in _log_gen.json and retried on the next run.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import torch

HERE = Path(__file__).resolve().parent
R06_ADAPTERS = HERE.parents[1] / "2026-09-27-R-06-expression-model-h2h" / "adapters"
sys.path.insert(0, str(R06_ADAPTERS))
import symupe_adapter as sa  # noqa: E402


@torch.inference_mode()
def generate(sc: sa.SyMuPeScorer, it: dict, k: int, seed: int, top_p: float) -> dict:
    """R-06 ``SyMuPeScorer.generate`` with ``lm_top_p`` exposed (body otherwise identical)."""
    tok = sc.tok
    score = sa.build_score(it)
    res = sc.gen.perform_score(score, use_score_context=True, num_samples=k, seed=seed,
                               lm_top_p=top_p, top_p=top_p, show_progress=False)
    n = len(it["pitch"])
    t2n = tok.encode_score(sa.build_score(it)).token_to_note
    score_perm = np.arange(n) if t2n is None else np.asarray(t2n, dtype=int)
    on = np.full((k, n), np.nan)
    du = np.full((k, n), np.nan)
    ve = np.full((k, n), np.nan)
    for i, r in enumerate(res):
        seq = r.perf_seq
        vals = seq.values
        voc = seq.vocab
        pitch = vals[:, voc["Pitch"]].astype(int)
        if len(seq) != n or not np.array_equal(pitch, it["pitch"].astype(int)[score_perm]):
            raise RuntimeError("generated sequence order differs from score order")
        on[i, score_perm] = np.cumsum(vals[:, voc["TimeShift"]])
        du[i, score_perm] = vals[:, voc["TimeDuration"]]
        ve[i, score_perm] = vals[:, voc["Velocity"]]
    return {"onset": on, "dur": du, "vel": ve}


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--items", required=True, help="gen_items dir")
    ap.add_argument("--out", required=True)
    ap.add_argument("--model", default=os.environ.get("R07_SYMUPE_MODEL"))
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--k", type=int, default=16)
    ap.add_argument("--top-p", type=float, default=1.0)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--only", nargs="*", default=None, help="item stems to run (default all)")
    a = ap.parse_args(argv)
    torch.manual_seed(a.seed)
    paths = sorted(Path(a.items).glob("*.npz"))
    if a.only:
        paths = [p for p in paths if p.stem in set(a.only)]
    if a.limit:
        paths = paths[: a.limit]
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    if a.model:
        sa.MODEL = a.model
    sc = sa.SyMuPeScorer(a.device)
    got = sc.gen._prepare_generator_kwargs(lm_top_p=a.top_p, top_p=a.top_p).get("top_p")
    if got != a.top_p:
        raise SystemExit(f"generator would sample at top_p={got}, not {a.top_p}")
    logp = out / "_log_gen.json"
    log = json.loads(logp.read_text())["items"] if logp.exists() else []
    t_all = time.perf_counter()
    done = 0
    for p in paths:
        dst = out / p.name
        if dst.exists():
            continue
        it = sa.load_item(p)
        t0 = time.perf_counter()
        try:
            r = generate(sc, it, a.k, a.seed, a.top_p)
        except Exception as e:  # noqa: BLE001
            print("FAIL", p.name, repr(e), file=sys.stderr, flush=True)
            log.append({"item": p.stem, "error": repr(e)[:300]})
            continue
        dt = time.perf_counter() - t0
        tmp = dst.with_suffix(".tmp.npz")
        np.savez_compressed(tmp, **r, seconds=dt, k=a.k, top_p=a.top_p, seed=a.seed)
        os.replace(tmp, dst)
        n = int(len(it["pitch"]))
        log.append({"item": p.stem, "n": n, "seconds": dt, "ms_per_note": 1000 * dt / n})
        done += 1
        print(f"{p.stem}: {n} notes, {dt:.1f} s ({1000 * dt / n:.1f} ms/note)", flush=True)
    logp.write_text(json.dumps({"model": a.model, "device": a.device, "k": a.k,
                                "top_p": a.top_p, "seed": a.seed, "items": log}, indent=1))
    print(f"gen: {done} new items in {time.perf_counter() - t_all:.0f} s -> {out}", flush=True)


if __name__ == "__main__":
    main()
