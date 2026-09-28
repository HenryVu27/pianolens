"""R-07 shared training loop (pure torch; imported by symupe_train.py and pt_train.py).

Resumable: ``<out>/ckpt/last.pt`` holds model, optimizer, scheduler, step, best validation loss and
early-stopping state. It is written atomically (temp file + rename) every ``ckpt_every`` steps,
at the end, and on SIGINT / SIGTERM. A restart with the same ``--out`` continues from it. The data
stream after a resume is re-seeded from ``(seed, step)``, so a run that is interrupted and
resumed sees the same windows as one resumed at the same step, not the same windows as an
uninterrupted run (disclosed in the README).

``<out>/ckpt/best.pt`` holds the model weights with the lowest validation loss.
``<out>/train_log.jsonl`` has one JSON line per logged step and per validation.
"""

from __future__ import annotations

import json
import math
import os
import signal
import time
from collections.abc import Callable, Iterator
from dataclasses import asdict, dataclass
from pathlib import Path

import torch


@dataclass
class TrainConfig:
    max_steps: int = 30000
    micro_batch: int = 16
    accum: int = 4
    lr: float = 1e-4
    weight_decay: float = 0.01
    warmup: int = 500
    min_lr_ratio: float = 0.1
    clip: float = 1.0
    log_every: int = 50
    eval_every: int = 1000
    ckpt_every: int = 500
    patience: int = 5  # evaluations without a 0.1% relative improvement
    bf16: bool = True
    seed: int = 20260928


def lr_factor(step: int, cfg: TrainConfig) -> float:
    if step < cfg.warmup:
        return (step + 1) / max(1, cfg.warmup)
    t = (step - cfg.warmup) / max(1, cfg.max_steps - cfg.warmup)
    return cfg.min_lr_ratio + (1 - cfg.min_lr_ratio) * 0.5 * (1 + math.cos(math.pi * min(1.0, t)))


def _atomic_save(obj, path: Path) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    torch.save(obj, tmp)
    os.replace(tmp, path)


class _Stop:
    def __init__(self):
        self.flag = False
        for s in (signal.SIGINT, signal.SIGTERM):
            signal.signal(s, self._set)

    def _set(self, *_):
        print("signal received: checkpointing and stopping", flush=True)
        self.flag = True


def train(model: torch.nn.Module, batches: Callable[[int], Iterator[dict]],
          loss_fn: Callable[[torch.nn.Module, dict], tuple[torch.Tensor, dict]],
          val_fn: Callable[[torch.nn.Module], dict], cfg: TrainConfig, out: Path,
          device: torch.device, max_steps_this_run: int | None = None) -> dict:
    """Train until ``cfg.max_steps`` or early stopping; resume from ``out/ckpt/last.pt``.

    Args:
        batches: ``batches(start_step)`` returns an endless iterator of micro-batches (dicts of
            tensors on CPU) seeded by ``(cfg.seed, start_step)``.
        loss_fn: ``(model, batch on device) -> (loss, {name: float})``.
        val_fn: ``model -> {"val_loss": float, ...}`` (called under ``torch.no_grad``).
        max_steps_this_run: stop (with a checkpoint) after this many steps in this process
            (used by the dry run to test resume).
    """
    out = Path(out)
    (out / "ckpt").mkdir(parents=True, exist_ok=True)
    logf = open(out / "train_log.jsonl", "a")
    opt = torch.optim.AdamW(model.parameters(), lr=cfg.lr, weight_decay=cfg.weight_decay)
    sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda s: lr_factor(s, cfg))
    state = {"step": 0, "best_val": float("inf"), "bad_evals": 0, "stopped_early": False}
    last = out / "ckpt" / "last.pt"
    if last.exists():
        ck = torch.load(last, map_location="cpu", weights_only=False)
        model.load_state_dict(ck["model"])
        opt.load_state_dict(ck["opt"])
        sched.load_state_dict(ck["sched"])
        state.update(ck["state"])
        print(f"resumed from step {state['step']}", flush=True)
        logf.write(json.dumps({"event": "resume", "step": state["step"]}) + "\n")
    else:
        (out / "train_config.json").write_text(json.dumps(asdict(cfg), indent=1))
    model.to(device)
    for g in opt.state.values():  # optimizer tensors to the model's device
        for k, v in g.items():
            if torch.is_tensor(v):
                g[k] = v.to(device)

    def save_last():
        _atomic_save({"model": model.state_dict(), "opt": opt.state_dict(),
                      "sched": sched.state_dict(), "state": state, "config": asdict(cfg)}, last)

    use_bf16 = cfg.bf16 and device.type == "cuda"

    def validate(step: int) -> None:
        model.eval()
        with torch.no_grad(), torch.autocast(device_type=device.type, dtype=torch.bfloat16,
                                             enabled=use_bf16):
            v = val_fn(model)
        model.train()
        improved = v["val_loss"] < state["best_val"] * (1 - 1e-3)
        if v["val_loss"] < state["best_val"]:
            state["best_val"] = v["val_loss"]
            _atomic_save({"model": model.state_dict(), "step": step, **v},
                         out / "ckpt" / "best.pt")
        if step > 0:
            state["bad_evals"] = 0 if improved else state["bad_evals"] + 1
            if state["bad_evals"] >= cfg.patience:
                state["stopped_early"] = True
        rec = {"event": "val", "step": step, **v, "best_val": state["best_val"],
               "bad_evals": state["bad_evals"]}
        logf.write(json.dumps(rec) + "\n")
        logf.flush()
        print(json.dumps(rec), flush=True)

    if state["step"] == 0 and not last.exists():
        validate(0)  # the starting weights (pretrained) are the first "best"
    stop = _Stop()
    it = batches(state["step"])
    start_step = state["step"]
    t_last, n_last = time.perf_counter(), 0
    if device.type == "cuda":
        torch.cuda.reset_peak_memory_stats(device)
    model.train()
    while state["step"] < cfg.max_steps and not state["stopped_early"]:
        opt.zero_grad(set_to_none=True)
        tot, parts = 0.0, {}
        for _ in range(cfg.accum):
            batch = {k: v.to(device, non_blocking=True) for k, v in next(it).items()}
            with torch.autocast(device_type=device.type, dtype=torch.bfloat16, enabled=use_bf16):
                loss, info = loss_fn(model, batch)
            (loss / cfg.accum).backward()
            tot += float(loss.detach()) / cfg.accum
            for k, v in info.items():
                parts[k] = parts.get(k, 0.0) + v / cfg.accum
        if not math.isfinite(tot):
            raise FloatingPointError(f"non-finite loss at step {state['step']}")
        gnorm = float(torch.nn.utils.clip_grad_norm_(model.parameters(), cfg.clip))
        opt.step()
        sched.step()
        state["step"] += 1
        n_last += 1
        step = state["step"]
        if step % cfg.log_every == 0 or step == 1:
            dt = (time.perf_counter() - t_last) / max(1, n_last)
            rec = {"step": step, "loss": tot, "lr": sched.get_last_lr()[0], "grad_norm": gnorm,
                   "sec_per_step": dt, **parts}
            if device.type == "cuda":
                rec["max_mem_gb"] = torch.cuda.max_memory_allocated(device) / 1e9
            logf.write(json.dumps(rec) + "\n")
            logf.flush()
            print(json.dumps(rec), flush=True)
            t_last, n_last = time.perf_counter(), 0
        if step % cfg.eval_every == 0 or step == cfg.max_steps:
            validate(step)
        done_here = max_steps_this_run is not None and step - start_step >= max_steps_this_run
        if step % cfg.ckpt_every == 0 or stop.flag or done_here:
            save_last()
        if stop.flag or done_here:
            break
    save_last()
    logf.close()
    if hasattr(it, "_shutdown_workers"):  # DataLoader over an endless stream: stop workers
        it._shutdown_workers()
    return state
