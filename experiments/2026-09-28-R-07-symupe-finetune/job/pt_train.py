"""R-07 secondary arm (pre-registered, DECISIONS 2026-09-28): fine-tune Pianist Transformer
(``yhj137/pianist-transformer-rendering``) on the same split and items as the primary arm.

Runs in the PT job env (setup.sh pt). Token construction is the R-06 adapter's (``PTScorer.ids``:
the authors' SFT label format with our alignment). Windows are 512 notes (4096 tokens, the
authors' context), random note-aligned start; loss = the model's own seq2seq cross-entropy.

  tokenize   interchange items -> pickled (x, labels) int32 arrays per item, per split
  train      resumable (trainlib.py); bf16 autocast on CUDA
  calibrate  time N steps, print projected hours
  eval       score | gen with a checkpoint (the R-06 adapter's definitions)

    python pt_train.py tokenize --data OUT/data --tokens OUT/tokens_pt --model PT_DIR
    python pt_train.py train --tokens OUT/tokens_pt --out OUT/pt_ft --model PT_DIR
"""

from __future__ import annotations

import argparse
import json
import os
import pickle
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader, IterableDataset, get_worker_info

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
R06 = EXP.parent / "2026-09-27-R-06-expression-model-h2h"
PT_REPO = os.environ.get("R07_PT_REPO", str(R06 / "envs" / "PianistTransformer"))
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(R06 / "adapters"))
os.environ.setdefault("PT_REPO", PT_REPO)

import trainlib  # noqa: E402

WIN = 512
SEED = 20260928
SPLIT_CSV = EXP / "split" / "pieces.csv"


def _pa():
    """Import the R-06 PT adapter; the PT code comes from PT_REPO (the pinned clone), imported
    before the adapter adds its own R-06 path."""
    if PT_REPO not in sys.path:
        sys.path.insert(0, PT_REPO)
    import importlib

    for mod in ("src.model.generate", "src.model.pianoformer", "src.utils.midi"):
        importlib.import_module(mod)  # cached in sys.modules from PT_REPO
    return importlib.import_module("pt_adapter")


def load_item(path: Path) -> dict:
    z = np.load(path, allow_pickle=False)
    return {k: z[k] for k in z.files}


def _model_config(model_dir: str | None):
    """The model's config (``PianoT5GemmaConfig.from_pretrained`` fails on transformers 4.54;
    loading the model, as the R-06 adapter does, works)."""
    pa = _pa()
    from src.model.pianoformer import PianoT5Gemma

    return PianoT5Gemma.from_pretrained(model_dir or pa.MODEL).config


_W: dict = {}


def _tok_init(cfg):
    torch.set_num_threads(1)
    pa = _pa()
    sc = pa.PTScorer.__new__(pa.PTScorer)
    sc.cfg = cfg
    _W["sc"] = sc


def _tok_shard(args):
    rows, data_dir, dst = args
    sc = _W["sc"]
    out, fails = [], []
    for item_rel, piece_id in rows:
        try:
            x, lab = sc.ids(load_item(Path(data_dir) / item_rel))
        except Exception as e:  # noqa: BLE001
            fails.append((item_rel, repr(e)[:200]))
            continue
        out.append({"item": item_rel, "piece_id": piece_id, "n": len(x) // 8,
                    "x": np.asarray(x, np.int32), "lab": np.asarray(lab, np.int32)})
    with open(dst, "wb") as f:
        pickle.dump(out, f, protocol=5)
    return {"shard": str(dst), "n_items": len(out), "fails": fails}


def cmd_tokenize(a):
    data = Path(a.data)
    man = pd.read_csv(data / "manifest.csv", keep_default_na=False)
    man = man[man["item"] != ""]
    split = pd.read_csv(a.split).set_index("piece_id")
    bad = man[(man["split"] == "train") & (man["piece_id"].map(split["split"]) != "train")]
    if len(bad):
        raise SystemExit(f"LEAKAGE: {len(bad)} train items not on train pieces")
    out = Path(a.tokens)
    cfg = _model_config(a.model)
    meta = {}
    for sp in a.splits:
        rows = man[man["split"] == sp][["item", "piece_id"]].sort_values("item")
        rows = rows.sample(frac=1.0, random_state=SEED) if sp == "train" else rows
        rows = list(rows.itertuples(index=False, name=None))
        (out / sp).mkdir(parents=True, exist_ok=True)
        jobs = [(rows[i:i + a.shard_size], str(data),
                 out / sp / f"shard_{i // a.shard_size:05d}.pkl")
                for i in range(0, len(rows), a.shard_size)]
        jobs = [j for j in jobs if not Path(j[2]).exists()]
        with ProcessPoolExecutor(a.workers, initializer=_tok_init, initargs=(cfg,)) as ex:
            res = list(ex.map(_tok_shard, jobs))
        meta[sp] = {"items": len(rows), "new_shards": len(res),
                    "fails": [f for r in res for f in r["fails"]]}
    (out / "tokenize_meta.json").write_text(json.dumps(meta, indent=1))
    print(json.dumps({k: {"items": v["items"], "fails": len(v["fails"])} for k, v in meta.items()}))


def window(o: dict, st: int, en: int) -> tuple[torch.Tensor, torch.Tensor]:
    return (torch.from_numpy(o["x"][8 * st: 8 * en].astype(np.int64)),
            torch.from_numpy(o["lab"][8 * st: 8 * en].astype(np.int64)))


def collate(samples, pad_id: int) -> dict:
    L = max(x.shape[0] for x, _ in samples)
    x = torch.full((len(samples), L), pad_id, dtype=torch.long)
    y = torch.full((len(samples), L), -100, dtype=torch.long)
    for i, (xi, yi) in enumerate(samples):
        x[i, : len(xi)] = xi
        y[i, : len(yi)] = yi
    return {"input_ids": x, "labels": y, "attention_mask": (x != pad_id).long()}


class Stream(IterableDataset):
    def __init__(self, shards, start_step, mb, pad_id):
        self.shards, self.start_step, self.mb, self.pad_id = shards, start_step, mb, pad_id

    def __iter__(self):
        wi = get_worker_info()
        rng = np.random.default_rng([SEED, self.start_step, 0 if wi is None else wi.id])
        batch = []
        while True:
            with open(self.shards[rng.integers(len(self.shards))], "rb") as f:
                data = pickle.load(f)
            for _ in range(len(data)):
                o = data[rng.integers(len(data))]
                st = 0 if o["n"] <= WIN else int(rng.integers(0, o["n"] - WIN + 1))
                batch.append(window(o, st, min(o["n"], st + WIN)))
                if len(batch) == self.mb:
                    yield collate(batch, self.pad_id)
                    batch = []


def loss_fn(model, b):
    return model(**b).loss, {}


def _setup(a):
    pa = _pa()
    from src.model.pianoformer import PianoT5Gemma

    device = torch.device(a.device if a.device != "auto" else
                          ("cuda" if torch.cuda.is_available() else "cpu"))
    model = PianoT5Gemma.from_pretrained(a.model or pa.MODEL, torch_dtype=torch.float32)
    if a.grad_ckpt and hasattr(model, "gradient_checkpointing_enable"):
        model.gradient_checkpointing_enable()
    pad = model.config.pad_token_id
    tokens = Path(a.tokens)
    tr = sorted((tokens / "train").glob("shard_*.pkl"))
    va = sorted((tokens / "val").glob("shard_*.pkl"))
    cfg = trainlib.TrainConfig(max_steps=a.max_steps, micro_batch=a.micro_batch, accum=a.accum,
                               lr=a.lr, warmup=a.warmup, eval_every=a.eval_every,
                               ckpt_every=a.ckpt_every, log_every=a.log_every,
                               patience=a.patience, bf16=not a.fp32)

    def batches(start):
        return iter(DataLoader(Stream(tr, start, cfg.micro_batch, pad), batch_size=None,
                               num_workers=a.workers, pin_memory=device.type == "cuda"))

    vw = []
    for sh in va:
        with open(sh, "rb") as f:
            for o in pickle.load(f):
                for st in range(0, o["n"], WIN):
                    if len(vw) < a.max_val_windows:
                        vw.append(window(o, st, min(o["n"], st + WIN)))

    def val_fn(m):
        tot, n = 0.0, 0
        for i in range(0, len(vw), cfg.micro_batch):
            b = {k: v.to(device) for k, v in collate(vw[i:i + cfg.micro_batch], pad).items()}
            k = b["input_ids"].shape[0]
            tot += float(m(**b).loss) * k
            n += k
        return {"val_loss": tot / max(1, n), "val_windows": n}

    return device, model, cfg, batches, val_fn


def cmd_train(a):
    device, model, cfg, batches, val_fn = _setup(a)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "run_meta.json").write_text(json.dumps({
        "argv": sys.argv, "torch": torch.__version__, "device": str(device),
        "n_params": sum(p.numel() for p in model.parameters())}, indent=1))
    st = trainlib.train(model, batches, loss_fn, val_fn, cfg, out, device,
                        max_steps_this_run=a.stop_after)
    print(json.dumps({"final_state": st}))


def cmd_calibrate(a):
    device, model, cfg, batches, _ = _setup(a)
    model.to(device).train()
    opt = torch.optim.AdamW(model.parameters(), lr=cfg.lr)
    it = batches(0)
    use_bf16 = cfg.bf16 and device.type == "cuda"
    if device.type == "cuda":
        torch.cuda.reset_peak_memory_stats(device)
    times = []
    for _ in range(a.calib_steps):
        t0 = time.perf_counter()
        opt.zero_grad(set_to_none=True)
        for _ in range(cfg.accum):
            b = {k: v.to(device) for k, v in next(it).items()}
            with torch.autocast(device_type=device.type, dtype=torch.bfloat16, enabled=use_bf16):
                loss = model(**b).loss
            (loss / cfg.accum).backward()
        opt.step()
        if device.type == "cuda":
            torch.cuda.synchronize()
        times.append(time.perf_counter() - t0)
    sps = float(np.median(times[min(5, len(times) - 1):]))
    rec = {"device": str(device), "micro_batch": cfg.micro_batch, "accum": cfg.accum,
           "sec_per_step_median": sps, "projected_hours_max_steps": sps * cfg.max_steps / 3600,
           "max_steps": cfg.max_steps,
           "peak_mem_gb": (torch.cuda.max_memory_allocated(device) / 1e9
                           if device.type == "cuda" else None)}
    Path(a.out).mkdir(parents=True, exist_ok=True)
    (Path(a.out) / "calibrate.json").write_text(json.dumps(rec, indent=1))
    print(json.dumps(rec))


def cmd_eval(a):
    """score / gen items with a checkpoint (same definitions as the R-06 adapter)."""
    pa = _pa()
    if a.model:
        pa.MODEL = a.model
    sc = pa.PTScorer(a.device)
    if a.ckpt:
        sc.model.load_state_dict(torch.load(a.ckpt, map_location="cpu",
                                            weights_only=False)["model"])
        sc.model.eval()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    paths = sorted(Path(a.items).glob("*.npz"))
    if a.limit:
        paths = paths[: a.limit]
    log = []
    for p in paths:
        if (out / p.name).exists():
            continue
        it = load_item(p)
        t0 = time.perf_counter()
        try:
            r = sc.logprobs(it) if a.job == "score" else sc.generate(it, a.k, a.seed)
        except Exception as e:  # noqa: BLE001
            log.append({"item": p.stem, "error": repr(e)[:300]})
            continue
        np.savez_compressed(out / p.name, **r, seconds=time.perf_counter() - t0)
        log.append({"item": p.stem, "seconds": time.perf_counter() - t0})
    (out / f"_log_{a.job}.json").write_text(json.dumps({"ckpt": a.ckpt, "items": log}, indent=1))
    print(f"{a.job}: {len(log)} items -> {out}")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["tokenize", "train", "calibrate", "eval"])
    ap.add_argument("--data")
    ap.add_argument("--tokens")
    ap.add_argument("--out")
    ap.add_argument("--items")
    ap.add_argument("--job", choices=["score", "gen"], default="score")
    ap.add_argument("--ckpt")
    ap.add_argument("--k", type=int, default=8)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--split", default=str(SPLIT_CSV))
    ap.add_argument("--splits", nargs="+", default=["train", "val"])
    ap.add_argument("--shard-size", type=int, default=256)
    ap.add_argument("--model", default=os.environ.get("R07_PT_MODEL"))
    ap.add_argument("--device", default="auto")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--max-steps", type=int, default=8000)
    ap.add_argument("--micro-batch", type=int, default=2)
    ap.add_argument("--accum", type=int, default=16)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--warmup", type=int, default=200)
    ap.add_argument("--eval-every", type=int, default=500)
    ap.add_argument("--ckpt-every", type=int, default=250)
    ap.add_argument("--log-every", type=int, default=25)
    ap.add_argument("--patience", type=int, default=5)
    ap.add_argument("--max-val-windows", type=int, default=512)
    ap.add_argument("--stop-after", type=int, default=None)
    ap.add_argument("--calib-steps", type=int, default=20)
    ap.add_argument("--grad-ckpt", action="store_true")
    ap.add_argument("--fp32", action="store_true")
    a = ap.parse_args(argv)
    if a.device == "auto" and a.cmd == "eval":
        a.device = "cuda" if torch.cuda.is_available() else "cpu"
    {"tokenize": cmd_tokenize, "train": cmd_train, "calibrate": cmd_calibrate,
     "eval": cmd_eval}[a.cmd](a)
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)  # never hang on a data-loader worker of the endless window stream


if __name__ == "__main__":
    main()
