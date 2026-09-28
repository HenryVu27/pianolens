"""Aria-AMT on a Mac (CPU or MPS), single process, no CUDA (A-01).

Aria-AMT's own CLI (``aria-amt transcribe``) asserts CUDA and runs a multi-process GPU queue.
This driver reuses its model, tokenizer, per-segment decoder (``process_segments``) and segment
stitching (``transcribe_file``) unchanged, and replaces only the CUDA plumbing:

* ``Tensor.cuda`` / ``Module.cuda`` are redirected to the chosen device;
* ``recalculate_tok_ids`` is re-implemented without the TorchScript mask hard-wired to "cuda"
  (same arithmetic);
* the bf16 autocast wrapper is bypassed (fp32 throughout; the Mac has no CUDA bf16);
* the GPU task queue is a synchronous stand-in that decodes each 30 s segment immediately;
* audio segments (30 s windows, 10 s stride, last one zero-padded) are cut from the whole file
  resampled to 16 kHz with soxr, instead of torchaudio's ffmpeg StreamReader.

It must run in the Python 3.11 venv that has Aria-AMT installed, not the project env::

    data/interim/envs/aria-amt/bin/python scripts/transcribe_aria_amt_mac.py \\
        --checkpoint data/interim/envs/aria-weights/piano-medium-double-1.0.safetensors \\
        --out-dir data/interim/henry_takes/transcribed/aria_amt in1.wav in2.wav

Setup (gitignored paths): ``uv venv data/interim/envs/aria-amt --python 3.11`` then
``uv pip install -e <clone of github.com/EleutherAI/aria-amt> soxr soundfile``. Tested with
aria-amt commit a1ab73f, torch 2.5.0, weights ``piano-medium-double-1.0``.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import soundfile as sf
import soxr
import torch


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("audio", nargs="+")
    ap.add_argument("--checkpoint", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--device", default="mps", choices=["mps", "cpu"])
    ap.add_argument("--model", default="medium-double")
    ap.add_argument("--names", nargs="*", help="output stems, one per audio file")
    args = ap.parse_args()
    dev = torch.device(args.device)

    torch.Tensor.cuda = lambda self, *a, **k: self.to(dev)  # type: ignore[method-assign]
    torch.nn.Module.cuda = lambda self, *a, **k: self.to(dev)  # type: ignore[method-assign]

    import amt.inference.transcribe as tr
    from amt.config import load_model_config
    from amt.inference.model import AmtEncoderDecoder, ModelConfig
    from amt.tokenizer import AmtTokenizer
    from amt.utils import _load_weight

    def recalculate_tok_ids(logits: torch.Tensor, tok_ids: torch.Tensor) -> torch.Tensor:
        probs = torch.softmax(logits, dim=-1)
        col = torch.arange(3419, device=logits.device).unsqueeze(0)
        interval = (col >= 392) & (col <= 3418)
        t = tok_ids.unsqueeze(1)
        beam = (col <= t + 2) & (col >= t - 2)
        keep = torch.zeros_like(probs, dtype=torch.bool)
        keep.scatter_(1, t, True)
        probs = torch.where((interval & beam) | keep, probs, torch.zeros_like(probs))
        w = probs * torch.arange(probs.size(1), device=probs.device).float().unsqueeze(0)
        return (w.sum(dim=1) / (probs.sum(dim=1) + 1e-9)).round().to(torch.long)

    tr.recalculate_tok_ids = recalculate_tok_ids

    tokenizer = AmtTokenizer()
    cfg = ModelConfig(**load_model_config(args.model))
    cfg.set_vocab_size(tokenizer.vocab_size)
    model = AmtEncoderDecoder(cfg)
    state = _load_weight(ckpt_path=args.checkpoint)
    state = {k.removeprefix("_orig_mod."): v for k, v in state.items()}
    model.load_state_dict(state)
    model.decoder.setup_cache(batch_size=1, max_seq_len=tr.MAX_BLOCK_LEN, dtype=torch.float)
    model.to(dev).eval()
    audio_transform = tr.AudioTransform().to(dev)
    logger = tr._setup_logger(name="mac")
    process = tr.process_segments.__wrapped__  # skip the CUDA bf16 autocast wrapper

    class SyncQueue:
        def __init__(self, results: dict) -> None:
            self.results = results

        def put(self, item) -> None:  # noqa: ANN001
            (task, pid) = item
            self.results[pid] = process(tasks=[(task, pid)], model=model,
                                        audio_transform=audio_transform,
                                        tokenizer=tokenizer, logger=logger)[0]

    sr, chunk_s, stride_f = tr.SAMPLE_RATE, tr.LEN_MS // 1000, tr.STRIDE_FACTOR

    def segments_of(path: str):
        def gen(audio_path: str, stride_factor=None, pad_last=True, segment=None):  # noqa: ANN001
            y, fs = sf.read(audio_path, dtype="float32", always_2d=True)
            y = soxr.resample(y.mean(1), fs, sr, quality="HQ").astype(np.float32)
            chunk, stride = sr * chunk_s, sr * chunk_s // stride_f
            if len(y) <= chunk:
                yield torch.from_numpy(np.pad(y, (0, chunk - len(y))))
                return
            n_strides = int(np.ceil(len(y) / stride))
            y = np.pad(y, (0, n_strides * stride - len(y)))
            buf = np.zeros(0, np.float32)
            for k in range(n_strides):
                seg = y[k * stride:(k + 1) * stride]
                buf = np.concatenate([buf, seg]) if len(buf) < chunk else \
                    np.concatenate([buf[stride:], seg])
                if len(buf) == chunk:
                    yield torch.from_numpy(buf.copy())
            if len(buf) > stride:
                rest = buf[stride:]
                yield torch.from_numpy(np.pad(rest, (0, chunk - len(rest))))
        return gen

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    names = args.names or [Path(a).stem for a in args.audio]
    log = []
    for path, name in zip(args.audio, names, strict=True):
        tr.get_wav_segments = segments_of(path)
        t0 = time.time()
        results: dict = {}
        seq = tr.transcribe_file(path, SyncQueue(results), results, pid=0, tokenizer=tokenizer)
        last = next(t[1] for t in seq[::-1] if isinstance(t, tuple) and t[0] == "onset")
        mid = tokenizer.detokenize(tokenized_seq=seq, len_ms=last)
        mid.remove_redundant_pedals()
        mid.to_midi().save(str(out / f"{name}.mid"))
        dt = time.time() - t0
        info = sf.info(path)
        log.append({"name": name, "seconds": round(dt, 1),
                    "audio_seconds": round(info.frames / info.samplerate, 1),
                    "device": args.device})
        print(json.dumps(log[-1]), flush=True)
    with open(out / "runtime.jsonl", "a") as f:
        for r in log:
            f.write(json.dumps(r) + "\n")


if __name__ == "__main__":
    main()
