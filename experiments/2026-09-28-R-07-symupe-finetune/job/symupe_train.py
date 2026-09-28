"""R-07 primary arm: fine-tune SyMuPe EncDec-base on the R-07 training split.

Runs in the R-07 job env (symupe + torch + pianolens, see setup.sh). Three commands:

  tokenize   interchange items (prep_data.py) -> pickled SyMuPe token shards, per split.
             Re-checks the split independently (every train item's piece must be "train").
             --flat builds the flat-model (F) data instead: one random flat rendition per item
             (pianolens.models.expression_data.flat_training_rendition).
  train      fine-tune from the pretrained weights; resumable (trainlib.py).
  calibrate  time N optimizer steps at the configured batch and print projected hours.

Windows: 256 notes (the paper's context), random start; SOS only on a window that starts at the
first note and EOS only on one that ends at the last, exactly as the R-06 adapter scores. The
encoder input masks the performance fields (the package's own ``prepare_sequence``).

    python symupe_train.py tokenize --data OUT/data --tokens OUT/tokens [--flat]
    python symupe_train.py train --tokens OUT/tokens --out OUT/symupe_ft --model MODEL_DIR
    python symupe_train.py calibrate --tokens OUT/tokens --out OUT/calib --model MODEL_DIR
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import pickle
import sys
import time
import zlib
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader, IterableDataset, get_worker_info

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
R06_ADAPTERS = EXP.parent / "2026-09-27-R-06-expression-model-h2h" / "adapters"
sys.path.insert(0, str(R06_ADAPTERS))
sys.path.insert(0, str(HERE))

import symupe_adapter as sa  # noqa: E402  (R-06 adapter: encode_pair, MODEL)
import trainlib  # noqa: E402

WIN = 256
SEED = 20260928
ENC_KEYS = ("enc_tokens", "enc_values", "dec_tokens", "dec_values", "dec_score_tokens",
            "dec_score_values")


def load_generator(model_dir: str | None, device: str = "cpu"):
    from symupe import AutoGenerator

    return AutoGenerator.from_pretrained(model_dir or sa.MODEL, device=torch.device(device))


# --------------------------------------------------------------------------------- tokenize

_W: dict = {}


def compact(seq):
    """Store ids as int16 and values as float32 (about 3x smaller shards); :func:`restore`
    converts back to the package's int64 / float64 before use."""
    if seq.ids is not None and np.abs(seq.ids).max(initial=0) < 32767:
        seq.ids = np.asarray(seq.ids).astype(np.int16)
    if seq.values is not None:
        seq.values = np.asarray(seq.values).astype(np.float32)
    return seq


def restore(o: dict) -> dict:
    if not o.get("_restored"):
        for k in ("score", "perf"):
            seq = o[k]
            seq.ids = np.asarray(seq.ids).astype(np.int64)
            if seq.values is not None:
                seq.values = np.asarray(seq.values).astype(np.float64)
        o["_restored"] = True
    return o


def _tok_init(model_dir: str | None) -> None:
    torch.set_num_threads(1)
    gen = load_generator(model_dir)
    sc = sa.SyMuPeScorer.__new__(sa.SyMuPeScorer)
    sc.device, sc.gen, sc.tok, sc.model = torch.device("cpu"), gen, gen.tokenizer, gen.model
    _W["sc"] = sc


def _tok_shard(args) -> dict:
    rows, data_dir, dst, flat = args
    from pianolens.models.expression_data import flat_training_rendition, load_item

    sc = _W["sc"]
    out, fails = [], []
    for item_rel, piece_id in rows:
        it = load_item(Path(data_dir) / item_rel)
        if flat:
            it = flat_training_rendition(
                it, np.random.default_rng(SEED + zlib.crc32(item_rel.encode()) % 1_000_003))
        try:
            score_perf, perf_seq, _ = sc.encode_pair(it)
        except Exception as e:  # noqa: BLE001 - count and continue
            fails.append((item_rel, repr(e)[:200]))
            continue
        out.append({"item": item_rel, "piece_id": piece_id, "n": len(perf_seq),
                    "score": compact(score_perf), "perf": compact(perf_seq)})
    with open(dst, "wb") as f:
        pickle.dump(out, f, protocol=5)
    return {"shard": str(dst), "n_items": len(out), "n_notes": int(sum(o["n"] for o in out)),
            "fails": fails}


def cmd_tokenize(a) -> None:
    import pandas as pd

    from pianolens.models.expression_split import leakage_check

    data = Path(a.data)
    man = pd.read_parquet(data / "manifest.parquet")
    man = man[man["item"] != ""]
    split = pd.read_csv(a.split)
    rep = leakage_check(split, man.loc[man["split"] == "train", "piece_id"])  # raises
    out = Path(a.tokens)
    meta = {"flat": a.flat, "leakage": rep.as_dict(), "splits": {}}
    for sp in a.splits:
        rows = man[man["split"] == sp][["item", "piece_id"]].sort_values("item")
        rows = rows.sample(frac=1.0, random_state=SEED) if sp == "train" else rows
        rows = list(rows.itertuples(index=False, name=None))
        (out / sp).mkdir(parents=True, exist_ok=True)
        jobs = [(rows[i:i + a.shard_size], str(data),
                 out / sp / f"shard_{i // a.shard_size:05d}.pkl", a.flat)
                for i in range(0, len(rows), a.shard_size)]
        jobs = [j for j in jobs if not Path(j[2]).exists()]  # resumable
        t0 = time.time()
        res = []
        with ProcessPoolExecutor(a.workers, initializer=_tok_init,
                                 initargs=(a.model,)) as ex:
            for r in ex.map(_tok_shard, jobs):
                res.append(r)
                print(json.dumps({k: r[k] for k in ("shard", "n_items", "n_notes")}), flush=True)
        meta["splits"][sp] = {"items": len(rows), "new_shards": len(res),
                              "fails": [f for r in res for f in r["fails"]],
                              "seconds": round(time.time() - t0, 1)}
    (out / f"tokenize_meta{'_flat' if a.flat else ''}.json").write_text(
        json.dumps(meta, indent=1, default=str))
    print(json.dumps({k: {kk: (vv if kk != "fails" else len(vv)) for kk, vv in v.items()}
                      for k, v in meta["splits"].items()}), flush=True)


# --------------------------------------------------------------------------------- windows


def make_window(gen, tok, score_perf, perf_seq, st: int, en: int) -> dict[str, torch.Tensor]:
    n = len(perf_seq)
    gen.reset()
    d = gen.prepare_sequence(seq=perf_seq[st:en], task="performance",
                             score_seq=score_perf[st:en], add_sos_eos=False, context_len=0)
    init, target, sc = d.init_seq, copy.deepcopy(d.target_seq).torch(device="cpu"), d.score_seq
    if st == 0:
        init, target, sc = tok.add_sos_token(init), tok.add_sos_token(target), \
            tok.add_sos_token(sc)
    if en == n:
        init, target, sc = tok.add_eos_token(init), tok.add_eos_token(target), \
            tok.add_eos_token(sc)

    def t(x, dt):
        return torch.as_tensor(x).to(dt).cpu()

    return {"enc_tokens": t(init.ids, torch.long), "enc_values": t(init.values, torch.float32),
            "dec_tokens": t(target.ids, torch.long), "dec_values": t(target.values, torch.float32),
            "dec_score_tokens": t(sc.ids, torch.long),
            "dec_score_values": t(sc.values, torch.float32)}


def collate(samples: list[dict]) -> dict[str, torch.Tensor]:
    L = max(s["dec_tokens"].shape[0] for s in samples)
    Le = max(s["enc_tokens"].shape[0] for s in samples)
    out = {}
    for k in ENC_KEYS:
        ln = Le if k.startswith("enc") else L
        x0 = samples[0][k]
        buf = torch.zeros((len(samples), ln, *x0.shape[1:]), dtype=x0.dtype)
        for i, s in enumerate(samples):
            buf[i, : s[k].shape[0]] = s[k]
        out[k] = buf
    out["enc_mask"] = torch.zeros((len(samples), Le), dtype=torch.bool)
    out["dec_mask"] = torch.zeros((len(samples), L), dtype=torch.bool)
    for i, s in enumerate(samples):
        out["enc_mask"][i, : s["enc_tokens"].shape[0]] = True
        out["dec_mask"][i, : s["dec_tokens"].shape[0]] = True
    lab = out["dec_tokens"].clone()
    lab[~out["dec_mask"]] = -100
    out["labels"] = lab
    return out


class WindowStream(IterableDataset):
    """Endless random windows: a worker picks a random shard, draws as many windows as the shard
    has items (random item, random start), then moves on. Seeded by (seed, start_step, worker)."""

    def __init__(self, shards: list[Path], model_dir: str | None, start_step: int,
                 micro_batch: int, seed: int = SEED):
        self.shards, self.model_dir, self.start_step = shards, model_dir, start_step
        self.mb, self.seed = micro_batch, seed

    def __iter__(self):
        wi = get_worker_info()
        wid = 0 if wi is None else wi.id
        torch.set_num_threads(1)
        rng = np.random.default_rng([self.seed, self.start_step, wid])
        gen = load_generator(self.model_dir)
        tok = gen.tokenizer
        batch = []
        while True:
            with open(self.shards[rng.integers(len(self.shards))], "rb") as f:
                data = pickle.load(f)
            if not data:
                continue
            for _ in range(len(data)):
                o = restore(data[rng.integers(len(data))])
                n = o["n"]
                st = 0 if n <= WIN else int(rng.integers(0, n - WIN + 1))
                try:
                    batch.append(make_window(gen, tok, o["score"], o["perf"], st,
                                             min(n, st + WIN)))
                except Exception as e:  # noqa: BLE001
                    print("window failed", o["item"], st, repr(e)[:200], flush=True)
                    continue
                if len(batch) == self.mb:
                    yield collate(batch)
                    batch = []


def val_windows(shards: list[Path], model_dir: str | None, max_windows: int) -> list[dict]:
    """Deterministic validation windows: non-overlapping 256-note windows from the start of each
    validation item, in shard order, up to ``max_windows``."""
    gen = load_generator(model_dir)
    tok = gen.tokenizer
    out = []
    for sh in shards:
        with open(sh, "rb") as f:
            data = pickle.load(f)
        for o in data:
            o = restore(o)
            for st in range(0, o["n"], WIN):
                out.append(make_window(gen, tok, o["score"], o["perf"], st, min(o["n"], st + WIN)))
                if len(out) >= max_windows:
                    return out
    return out


def loss_fn(model, batch):
    res = model(**{k: v for k, v in batch.items()})
    info = {f"loss/{k}": float(v.detach()) for k, v in (res.losses or {}).items()}
    return res.loss, info


def make_val_fn(windows: list[dict], micro_batch: int, device: torch.device):
    def fn(model) -> dict:
        tot, n, parts = 0.0, 0, {}
        for i in range(0, len(windows), micro_batch):
            b = {k: v.to(device) for k, v in collate(windows[i:i + micro_batch]).items()}
            loss, info = loss_fn(model, b)
            m = b["dec_mask"].shape[0]
            tot += float(loss) * m
            n += m
            for k, v in info.items():
                parts[k] = parts.get(k, 0.0) + v * m
        return {"val_loss": tot / max(1, n), "val_windows": n,
                **{f"val_{k}": v / max(1, n) for k, v in parts.items()}}
    return fn


def _setup(a):
    torch.manual_seed(SEED)
    device = torch.device(a.device if a.device != "auto" else
                          ("cuda" if torch.cuda.is_available() else "cpu"))
    tokens = Path(a.tokens)
    train_shards = sorted((tokens / "train").glob("shard_*.pkl"))
    val_shards = sorted((tokens / "val").glob("shard_*.pkl"))
    if not train_shards or not val_shards:
        raise SystemExit(f"no token shards under {tokens}")
    gen = load_generator(a.model)
    cfg = trainlib.TrainConfig(max_steps=a.max_steps, micro_batch=a.micro_batch, accum=a.accum,
                               lr=a.lr, warmup=a.warmup, eval_every=a.eval_every,
                               ckpt_every=a.ckpt_every, log_every=a.log_every,
                               patience=a.patience, bf16=not a.fp32)

    def batches(start_step: int):
        ds = WindowStream(train_shards, a.model, start_step, cfg.micro_batch)
        dl = DataLoader(ds, batch_size=None, num_workers=a.workers,
                        persistent_workers=a.workers > 0,
                        prefetch_factor=4 if a.workers > 0 else None,
                        pin_memory=device.type == "cuda")
        return iter(dl)

    return device, gen, cfg, batches, val_shards


def cmd_train(a) -> None:
    device, gen, cfg, batches, val_shards = _setup(a)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    vw = val_windows(val_shards, a.model, a.max_val_windows)
    (out / "run_meta.json").write_text(json.dumps({
        "argv": sys.argv, "torch": torch.__version__, "device": str(device),
        "cuda": torch.version.cuda, "val_windows": len(vw),
        "n_params": sum(p.numel() for p in gen.model.parameters()),
        "gpu": torch.cuda.get_device_name(0) if device.type == "cuda" else None}, indent=1))
    state = trainlib.train(gen.model, batches, loss_fn, make_val_fn(vw, cfg.micro_batch, device),
                           cfg, out, device, max_steps_this_run=a.stop_after)
    print(json.dumps({"final_state": state}), flush=True)


def cmd_calibrate(a) -> None:
    device, gen, cfg, batches, _ = _setup(a)
    model = gen.model.to(device)
    model.train()
    opt = torch.optim.AdamW(model.parameters(), lr=cfg.lr)
    it = batches(0)
    use_bf16 = cfg.bf16 and device.type == "cuda"
    times = []
    if device.type == "cuda":
        torch.cuda.reset_peak_memory_stats(device)
    for _ in range(a.calib_steps):
        t0 = time.perf_counter()
        opt.zero_grad(set_to_none=True)
        for _ in range(cfg.accum):
            b = {k: v.to(device) for k, v in next(it).items()}
            with torch.autocast(device_type=device.type, dtype=torch.bfloat16, enabled=use_bf16):
                loss, _ = loss_fn(model, b)
            (loss / cfg.accum).backward()
        opt.step()
        if device.type == "cuda":
            torch.cuda.synchronize()
        times.append(time.perf_counter() - t0)
    warm = times[min(5, len(times) - 1):]
    sps = float(np.median(warm))
    rec = {"device": str(device), "micro_batch": cfg.micro_batch, "accum": cfg.accum,
           "windows_per_step": cfg.micro_batch * cfg.accum, "sec_per_step_median": sps,
           "steps_timed": len(warm), "projected_hours_max_steps": sps * cfg.max_steps / 3600,
           "max_steps": cfg.max_steps,
           "peak_mem_gb": (torch.cuda.max_memory_allocated(device) / 1e9
                           if device.type == "cuda" else None)}
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "calibrate.json").write_text(json.dumps(rec, indent=1))
    print(json.dumps(rec), flush=True)
    if hasattr(it, "_shutdown_workers"):
        it._shutdown_workers()


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["tokenize", "train", "calibrate"])
    ap.add_argument("--data")
    ap.add_argument("--tokens")
    ap.add_argument("--out")
    ap.add_argument("--split", default=str(EXP / "split" / "pieces.csv"))
    ap.add_argument("--splits", nargs="+", default=["train", "val"])
    ap.add_argument("--flat", action="store_true")
    ap.add_argument("--shard-size", type=int, default=256)
    ap.add_argument("--model", default=os.environ.get("R07_SYMUPE_MODEL"))
    ap.add_argument("--device", default="auto")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--max-steps", type=int, default=30000)
    ap.add_argument("--micro-batch", type=int, default=32)
    ap.add_argument("--accum", type=int, default=2)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--warmup", type=int, default=500)
    ap.add_argument("--eval-every", type=int, default=1000)
    ap.add_argument("--ckpt-every", type=int, default=500)
    ap.add_argument("--log-every", type=int, default=50)
    ap.add_argument("--patience", type=int, default=5)
    ap.add_argument("--max-val-windows", type=int, default=2048)
    ap.add_argument("--stop-after", type=int, default=None)
    ap.add_argument("--calib-steps", type=int, default=30)
    ap.add_argument("--fp32", action="store_true")
    a = ap.parse_args(argv)
    {"tokenize": cmd_tokenize, "train": cmd_train, "calibrate": cmd_calibrate}[a.cmd](a)
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)  # never hang on a data-loader worker of the endless window stream


if __name__ == "__main__":
    main()
