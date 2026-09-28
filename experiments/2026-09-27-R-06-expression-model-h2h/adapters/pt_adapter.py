"""Pianist Transformer (yhj137/pianist-transformer-rendering) adapter for R-06.
Runs in envs/pt-venv with the repo at envs/PianistTransformer on sys.path.

* ``score``: teacher-forced log-probabilities of a rendition given its score. The label sequence
  is built exactly as the authors build SFT labels (``src/utils/midi.py``,
  ``align_score_and_performance``), with our alignment instead of Nakamura's: notes in score order,
  the *sorted* performed onsets assigned in that order, each note's own velocity and key-down
  duration (ms), sustain pedal sampled at 4 points and binarised at 64 (``sft.py``,
  ``group_ids``). Each field is renormalised over its valid id range, as their logits processor
  does when sampling.
* ``generate``: K samples with the authors' ``batch_performance_render`` (temperature 1.0,
  top-p 0.95), returned per score note.

Conditioning (pre-registered, same as SyMuPe): the score MIDI has one tempo (60 / spq_cond) and one
velocity (vel_cond) on every note.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch

HERE = Path(__file__).resolve().parent
REPO = HERE.parent / "envs" / "PianistTransformer"
sys.path.insert(0, str(REPO))

from miditoolkit import ControlChange, Instrument, MidiFile, Note, TempoChange  # noqa: E402

from src.model.generate import batch_performance_render  # noqa: E402
from src.model.pianoformer import PianoT5Gemma  # noqa: E402
from src.utils.midi import midi_to_ids  # noqa: E402

MODEL = "yhj137/pianist-transformer-rendering"
TPQ = 480
WIN_NOTES = 512  # 4096 tokens, the authors' max context
FIELDS = {1: "interval", 2: "velocity", 3: "duration", 4: "pedal1", 5: "pedal2", 6: "pedal3",
          7: "pedal4"}


def load_item(path: Path) -> dict:
    z = np.load(path, allow_pickle=False)
    return {k: z[k] for k in z.files}


def build_score(it: dict) -> MidiFile:
    m = MidiFile(ticks_per_beat=TPQ)
    m.tempo_changes.append(TempoChange(float(60.0 / it["spq_cond"]), 0))
    origin = float(it["origin"])
    vel = int(it["vel_cond"])
    notes = []
    for on, du, p in zip(it["score_onset_q"], it["score_dur_q"], it["pitch"], strict=True):
        du = du if du > 0 else 1 / 16
        st = int(round((on - origin) * TPQ))
        notes.append(Note(vel, int(p), st, st + max(1, int(round(du * TPQ)))))
    m.instruments.append(Instrument(program=0, is_drum=False, name="Piano", notes=notes))
    m.max_tick = max(n.end for n in notes) + TPQ
    return m


def label_midi(it: dict) -> MidiFile:
    """The authors' aligned label MIDI (500 ticks per beat at 120 bpm = 1 ms per tick)."""
    on = np.round((it["perf_onset_sec"] - it["perf_onset_sec"].min()
                   + (it["score_onset_q"].min() - it["origin"]) * it["spq_cond"]) * 1000)
    on = on.astype(int)
    dur = np.maximum(1, np.round(it["perf_dur_sec"] * 1000).astype(int))
    pitch = it["pitch"].astype(int)
    # their normalize_midi cuts a note at the next onset of the same pitch
    end = on + dur
    by = defaultdict(list)
    for i in np.argsort(on, kind="stable"):
        by[pitch[i]].append(i)
    for idx in by.values():
        for a, b in zip(idx[:-1], idx[1:], strict=True):
            if end[a] >= on[b]:
                end[a] = max(on[b], on[a] + 1)
    dur = end - on
    starts = np.sort(on)  # sorted performed onsets assigned in score order
    notes = [Note(int(np.clip(v, 1, 127)), int(p), int(s), int(s + d))
             for v, p, s, d in zip(it["velocity"], pitch, starts, dur, strict=True)]
    ccs = []
    t0 = it["perf_onset_sec"].min() - (it["score_onset_q"].min() - it["origin"]) * it["spq_cond"]
    for t, v in it["pedal"]:
        tick = int(round((t - t0) * 1000))
        if tick >= 0:
            ccs.append(ControlChange(64, int(v), tick))
    ccs.sort(key=lambda c: c.time)
    m = MidiFile(ticks_per_beat=500)
    m.tempo_changes.append(TempoChange(120, 0))
    m.instruments.append(Instrument(program=0, is_drum=False, name="Piano", notes=notes,
                                    control_changes=ccs))
    m.max_tick = int(max(n.end for n in notes) + 5000)
    return m


class PTScorer:
    def __init__(self, device: str = "cpu", dtype: str = "float32"):
        self.device = torch.device(device)
        dt = {"float32": torch.float32, "bfloat16": torch.bfloat16}[dtype]
        self.model = PianoT5Gemma.from_pretrained(MODEL, torch_dtype=dt).to(self.device)
        self.model.eval()
        self.cfg = self.model.config

    def ids(self, it: dict) -> tuple[list[int], list[int]]:
        cfg = self.cfg
        x = midi_to_ids(cfg, build_score(it))
        lab = midi_to_ids(cfg, label_midi(it), normalize=False)
        n = len(it["pitch"])
        if len(x) != 8 * n or len(lab) != 8 * n:
            raise RuntimeError(f"token count {len(x)}/{len(lab)} != 8 x {n}")
        xp = np.array(x[0::8]) - cfg.pitch_start
        if not np.array_equal(xp, it["pitch"].astype(int)):
            raise RuntimeError("score token order differs from interchange order")
        for j in range(4, 8):  # sft.py group_ids: binarise pedal labels
            lab[j::8] = [cfg.pedal_start + 127 if v >= cfg.pedal_start + 64 else cfg.pedal_start
                         for v in lab[j::8]]
        return x, lab

    @torch.inference_mode()
    def logprobs(self, it: dict) -> dict[str, np.ndarray]:
        cfg = self.cfg
        x, lab = self.ids(it)
        n = len(it["pitch"])
        out = {name: np.full(n, np.nan) for name in FIELDS.values()}
        w = WIN_NOTES
        starts = [0] if n <= w else list(range(0, n - w + 1, w // 2))
        if n > w and starts[-1] != n - w:
            starts.append(n - w)
        for wi, st in enumerate(starts):
            en = min(n, st + w)
            xi = torch.tensor([x[8 * st: 8 * en]], device=self.device)
            li = torch.tensor([lab[8 * st: 8 * en]], device=self.device)
            logits = self.model(input_ids=xi, labels=li,
                                attention_mask=torch.ones_like(xi)).logits[0].float()
            lp_all = {}
            for j, name in FIELDS.items():
                lo, hi = cfg.valid_id_range[j]
                lg = logits[j::8, lo:hi]
                lp = torch.log_softmax(lg, dim=-1)
                tgt = li[0, j::8] - lo
                lp_all[name] = lp.gather(1, tgt.clamp(0, hi - lo - 1)[:, None])[:, 0].cpu().numpy()
            first_scored = 0 if wi == 0 else (w - w // 2)
            for name, v in lp_all.items():
                seg = slice(st + first_scored, en)
                out[name][seg] = v[first_scored:]
        return out

    @torch.inference_mode()
    def generate(self, it: dict, k: int, seed: int) -> dict[str, np.ndarray]:
        cfg = self.cfg
        torch.manual_seed(seed)
        score = build_score(it)
        _, res_ids = batch_performance_render(self.model, [score] * k, temperature=1.0,
                                              top_p=0.95, device=str(self.device))
        n = len(it["pitch"])
        on = np.full((k, n), np.nan)
        du = np.full((k, n), np.nan)
        ve = np.full((k, n), np.nan)
        for i, ids in enumerate(res_ids):
            a = np.array(ids).reshape(-1, 8)
            if len(a) != n or not np.array_equal(a[:, 0] - cfg.pitch_start,
                                                 it["pitch"].astype(int)):
                raise RuntimeError("generated order differs from score order")
            on[i] = np.cumsum(a[:, 1] - cfg.timing_start) / 1000.0
            du[i] = (a[:, 3] - cfg.timing_start) / 1000.0
            ve[i] = a[:, 2] - cfg.velocity_start
        return {"onset": on, "dur": du, "vel": ve}


def selftest(sc: PTScorer, it: dict) -> dict:
    cfg = sc.cfg
    _, lab = sc.ids(it)
    a = np.array(lab).reshape(-1, 8)
    on = np.cumsum(a[:, 1] - cfg.timing_start) / 1000.0
    ref = np.sort(it["perf_onset_sec"])
    return {
        "onset_mae_ms": float(np.mean(np.abs((on - on[0]) - (ref - ref[0]))) * 1000),
        "vel_mae": float(np.mean(np.abs((a[:, 2] - cfg.velocity_start) - it["velocity"]))),
        "dur_mae_ms": float(np.mean(np.abs((a[:, 3] - cfg.timing_start) / 1000.0
                                           - it["perf_dur_sec"])) * 1000),
    }


def cost(sc: PTScorer, it: dict, batches=(1, 2, 4), steps: int = 3) -> list[dict]:
    """Peak memory / time of AdamW steps at the authors' SFT context (4096 tokens = 512 notes)."""
    x, lab = sc.ids(it)
    reps = -(-4096 // len(x))
    x, lab = (x * reps)[:4096], (lab * reps)[:4096]
    dev = sc.device
    model = sc.model
    model.train()
    opt = torch.optim.AdamW(model.parameters(), lr=5e-4)
    out = []
    for b in batches:
        xi = torch.tensor([x] * b, device=dev)
        li = torch.tensor([lab] * b, device=dev)
        try:
            if dev.type == "mps":
                torch.mps.empty_cache()
            t0 = time.perf_counter()
            peak = 0
            for _ in range(steps):
                loss = model(input_ids=xi, labels=li, attention_mask=torch.ones_like(xi)).loss
                opt.zero_grad()
                loss.backward()
                opt.step()
                if dev.type == "mps":
                    torch.mps.synchronize()
                    peak = max(peak, torch.mps.driver_allocated_memory())
            dt = (time.perf_counter() - t0) / steps
            out.append({"batch": b, "tokens": 4096, "sec_per_step": dt, "mps_driver_bytes": peak})
        except Exception as e:  # noqa: BLE001
            out.append({"batch": b, "error": repr(e)})
        print(out[-1], flush=True)
    model.eval()
    return out


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("job", choices=["score", "generate", "selftest", "cost"])
    ap.add_argument("--items", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--dtype", default="float32")
    ap.add_argument("--k", type=int, default=8)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args(argv)
    items = Path(a.items)
    paths = (sorted(items.glob("*.npz")) if items.is_dir()
             else [Path(p) for p in items.read_text().split()])
    if a.limit:
        paths = paths[: a.limit]
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    sc = PTScorer(a.device, a.dtype)
    if a.job == "cost":
        n_params = sum(p.numel() for p in sc.model.parameters())
        r = cost(sc, load_item(paths[0]))
        (out / "cost.json").write_text(json.dumps({"params": n_params, "device": a.device,
                                                   "dtype": a.dtype, "steps": r}, indent=1))
        return
    log = []
    for p in paths:
        dst = out / p.name
        if dst.exists() and a.job != "selftest":
            continue
        it = load_item(p)
        t0 = time.perf_counter()
        try:
            if a.job == "score":
                r = sc.logprobs(it)
            elif a.job == "generate":
                r = sc.generate(it, a.k, a.seed)
            else:
                r = selftest(sc, it)
                print(p.name, r)
                log.append({"item": p.stem, **r})
                continue
        except Exception as e:  # noqa: BLE001
            print("FAIL", p.name, repr(e), file=sys.stderr)
            log.append({"item": p.stem, "error": repr(e)})
            continue
        dt = time.perf_counter() - t0
        np.savez_compressed(dst, **r, seconds=dt)
        log.append({"item": p.stem, "n": int(len(it["pitch"])), "seconds": dt})
    (out / f"_log_{a.job}.json").write_text(json.dumps(log, indent=1))


if __name__ == "__main__":
    main()
