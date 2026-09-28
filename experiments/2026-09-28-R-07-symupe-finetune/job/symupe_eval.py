"""R-07 evaluation runner for SyMuPe (frozen, fine-tuned E, or flat model F).

Uses the R-06 adapter (same windows, same conditioning, same log-prob definition) with the
weights of a checkpoint loaded on top of the pretrained model.

  score    teacher-forced per-note log-probs of every item (real and variants)
  gen      K samples per generation item (top-p 0.95, as R-06), per score note
  typset   for every *real* item: K samples under that item's own conditioning with top-p 1.0
           (the model's full distribution), each sample teacher-forced; saves the per-field
           mean log-prob of each sample (the typical-set reference of S-TYP)

    python symupe_eval.py score  --items DIR --out DIR [--ckpt best.pt] [--model DIR]
    python symupe_eval.py gen    --items GEN_DIR --out DIR --k 8
    python symupe_eval.py typset --items DIR --out DIR --k 16
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

CORE = ("Velocity", "TimeShift", "TimeDuration")


class Scorer(sa.SyMuPeScorer):
    """R-06 scorer that can also teacher-force a given (score_perf, perf_seq, perm) triple."""

    def encode_pair(self, it):
        if "_seqs" in it:
            return it["_seqs"]
        return super().encode_pair(it)

    def samples_logprobs(self, it: dict, k: int, seed: int) -> dict[str, np.ndarray]:
        """Generate k samples at top-p 1.0 under the item's conditioning; teacher-force each."""
        tok = self.tok
        score = sa.build_score(it)
        res = self.gen.perform_score(score, use_score_context=True, num_samples=k, seed=seed,
                                     lm_top_p=1.0, show_progress=False)
        score_seq = tok.encode_score(sa.build_score(it))
        score_perf = tok.score_tokens_as_performance(score_seq)
        n = len(it["pitch"])
        perm = (np.arange(n) if score_seq.token_to_note is None
                else np.asarray(score_seq.token_to_note, dtype=int))
        out = {key: np.full(k, np.nan) for key in sa.KEYS}
        for i, r in enumerate(res):
            seq = r.perf_seq
            if len(seq) != n:
                raise RuntimeError("sample length differs from score")
            lp = self.logprobs({"_seqs": (score_perf, seq, perm)})
            for key in sa.KEYS:
                out[key][i] = float(np.nanmean(lp[key]))
        return out


def load_scorer(model_dir: str | None, ckpt: str | None, device: str) -> Scorer:
    if model_dir:
        sa.MODEL = model_dir
    sc = Scorer(device)
    if ckpt:
        state = torch.load(ckpt, map_location="cpu", weights_only=False)
        sc.model.load_state_dict(state["model"], strict=True)
        sc.model.eval()
    return sc


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("job", choices=["score", "gen", "typset"])
    ap.add_argument("--items", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--ckpt", default=None, help="trainlib checkpoint (best.pt); none = frozen")
    ap.add_argument("--model", default=os.environ.get("R07_SYMUPE_MODEL"))
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--k", type=int, default=8)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--only-real", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args(argv)
    torch.manual_seed(a.seed)
    paths = sorted(Path(a.items).glob("*.npz"))
    if a.job == "typset" or a.only_real:
        paths = [p for p in paths if p.stem.endswith("__real")]
    if a.limit:
        paths = paths[: a.limit]
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    sc = load_scorer(a.model, a.ckpt, a.device)
    log = []
    for p in paths:
        dst = out / p.name
        if dst.exists():
            continue
        it = sa.load_item(p)
        t0 = time.perf_counter()
        try:
            if a.job == "score":
                r = sc.logprobs(it)
            elif a.job == "gen":
                r = sc.generate(it, a.k, a.seed)
            else:
                r = sc.samples_logprobs(it, a.k, a.seed)
        except Exception as e:  # noqa: BLE001
            print("FAIL", p.name, repr(e), file=sys.stderr, flush=True)
            log.append({"item": p.stem, "error": repr(e)[:300]})
            continue
        dt = time.perf_counter() - t0
        np.savez_compressed(dst, **r, seconds=dt)
        log.append({"item": p.stem, "n": int(len(it["pitch"])), "seconds": dt})
    (out / f"_log_{a.job}.json").write_text(json.dumps(
        {"ckpt": a.ckpt, "model": a.model, "k": a.k, "seed": a.seed, "items": log}, indent=1))
    print(f"{a.job}: {len(log)} items -> {out}", flush=True)


if __name__ == "__main__":
    main()
