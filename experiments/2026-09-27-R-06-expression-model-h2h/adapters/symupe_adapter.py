"""SyMuPe EncDec-base adapter for R-06. Runs in envs/symupe-venv (not the project env).

Two jobs, both reading the interchange npz files written by ../prepare.py:

* ``score``: teacher-forced per-note log-probabilities of a rendition given its score
  (Velocity, TimeShift, TimeDuration, TimeDurationSustain). Each categorical is renormalised over
  non-special tokens, as the generator does when sampling (``filter_key_ids``).
* ``generate``: K sampled renderings of a score (the package's own ``perform_score`` loop),
  returned per score note as onset / duration / velocity.

Conditioning (pre-registered): the score MIDI carries one tempo (60 / spq_cond) and one velocity
(vel_cond) for every note. SyMuPe reads them as the score-side ``Tempo`` / ``Velocity`` context
tokens. No other performance information reaches the model.

Usage:
    python symupe_adapter.py score    --items DIR --out DIR [--device cpu|mps]
    python symupe_adapter.py generate --items DIR --out DIR --k 8 --seed 0
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch
from symusic import ControlChange, Note, Score, Tempo, TimeSignature, Track

MODEL = "SyMuPe/EncDec-base"
TPQ = 480
PERF_QPM = 120.0  # performance MIDI: 1 quarter = 0.5 s, 1 tick = 1/960 s
KEYS = ["Velocity", "TimeShift", "TimeDuration", "TimeDurationSustain"]


def load_item(path: Path) -> dict:
    z = np.load(path, allow_pickle=False)
    return {k: z[k] for k in z.files}


def build_score(it: dict) -> Score:
    s = Score(TPQ)
    s.tempos.append(Tempo(0, qpm=float(60.0 / it["spq_cond"])))
    for q, n, d in it["ts"]:
        s.time_signatures.append(TimeSignature(int(round(q * TPQ)), int(n), int(d)))
    tr = Track(program=0, is_drum=False, name="Piano")
    vel = int(it["vel_cond"])
    origin = float(it["origin"])
    for on, du, p in zip(it["score_onset_q"], it["score_dur_q"], it["pitch"], strict=True):
        du = du if du > 0 else 1 / 16
        tr.notes.append(Note(int(round((on - origin) * TPQ)), max(1, int(round(du * TPQ))),
                             int(p), vel))
    s.tracks.append(tr)
    return s


def build_perf(it: dict) -> Score:
    s = Score(TPQ)
    s.tempos.append(Tempo(0, qpm=PERF_QPM))
    tpsec = TPQ * PERF_QPM / 60.0
    tr = Track(program=0, is_drum=False, name="Piano")
    # first note sits where the score puts it (bar grid at the conditioning tempo), as for PT
    t0 = float(np.min(it["perf_onset_sec"])
               - (np.min(it["score_onset_q"]) - it["origin"]) * it["spq_cond"])
    for on, du, p, v in zip(it["perf_onset_sec"], it["perf_dur_sec"], it["pitch"],
                            it["velocity"], strict=True):
        tr.notes.append(Note(int(round((on - t0) * tpsec)), max(1, int(round(du * tpsec))),
                             int(p), int(np.clip(v, 1, 127))))
    for t, v in it["pedal"]:
        tick = int(round((t - t0) * tpsec))
        if tick >= 0:
            tr.controls.append(ControlChange(tick, 64, int(v)))
    s.tracks.append(tr)
    return s


class SyMuPeScorer:
    def __init__(self, device: str = "cpu"):
        from symupe import AutoGenerator

        self.device = torch.device(device)
        self.gen = AutoGenerator.from_pretrained(MODEL, device=self.device)
        self.tok = self.gen.tokenizer
        self.model = self.gen.model
        self.model.eval()

    # ---- encoding -------------------------------------------------------------------
    def encode_pair(self, it: dict):
        tok = self.tok
        score = build_score(it)
        score_seq = tok.encode_score(score)
        n = len(it["pitch"])
        # token t of the score sequence is interchange note perm[t] (the tokenizer's grid
        # quantisation can reorder notes whose onsets fall into one grid cell)
        perm = (np.arange(n) if score_seq.token_to_note is None
                else np.asarray(score_seq.token_to_note, dtype=int))
        if sorted(perm.tolist()) != list(range(n)):
            raise RuntimeError("score tokens are not a permutation of the interchange notes")
        perf = build_perf(it)
        perf_seq = tok.encode_performance(perf, score_tokens=score_seq,
                                          note_alignment=np.arange(n))
        # as in training data: pedal tokens fill TimeDurationSustain, then are removed and the
        # sequence is put back in score order
        perf_seq = tok.add_pedal_tokens(perf_seq)
        perf_seq = tok.remove_pedal_tokens(perf_seq)
        perf_seq = tok.sort_tokens(perf_seq, by_time=False)
        v = tok.get_values(perf_seq, "Pitch")
        if len(perf_seq) != n or not np.array_equal(np.asarray(v).astype(int),
                                                    it["pitch"].astype(int)[perm]):
            raise RuntimeError("performance token order differs from interchange order")
        score_perf = tok.score_tokens_as_performance(score_seq)
        return score_perf, perf_seq, perm

    # ---- teacher-forced log-probs ---------------------------------------------------------
    @torch.inference_mode()
    def logprobs(self, it: dict, win: int = 256, hop: int = 128) -> dict[str, np.ndarray]:
        tok, gen = self.tok, self.gen
        score_perf, perf_seq, perm = self.encode_pair(it)
        n = len(perf_seq)
        out = {k: np.full(n, np.nan) for k in KEYS}  # indexed by token, mapped to notes below
        starts = [0] if n <= win else list(range(0, n - win + 1, hop))
        if n > win and starts[-1] != n - win:
            starts.append(n - win)
        zero = tok.zero_token
        for wi, st in enumerate(starts):
            en = min(n, st + win)
            first = st == 0
            last = en == n
            seq = perf_seq[st:en]
            sseq = score_perf[st:en]
            gen.reset()
            data = gen.prepare_sequence(seq=seq, task="performance", score_seq=sseq,
                                        add_sos_eos=False, context_len=0)
            init, target, sc = data.init_seq, copy.deepcopy(data.target_seq), data.score_seq
            target = target.torch(device=self.device)
            if first:
                init, target = tok.add_sos_token(init), tok.add_sos_token(target)
                sc = tok.add_sos_token(sc)
            if last:
                init, target = tok.add_eos_token(init), tok.add_eos_token(target)
                sc = tok.add_eos_token(sc)
            if not first:
                # the AR wrapper predicts token t+1 from tokens <= t; without SOS the first note
                # of a window is context only (it is scored by the previous window)
                pass
            res = self.model(
                enc_tokens=init.ids[None], enc_values=init.values[None],
                dec_tokens=target.ids[None], dec_values=target.values[None],
                labels=target.ids[None], dec_score_tokens=sc.ids[None],
                dec_score_values=sc.values[None],
            )
            logits = res.decoder.logits
            labels = target.ids[None][:, 1:]
            vocab = target.vocab
            n_pos = labels.shape[1]
            # decoder position j predicts token j+1 of target
            offs = 1 if first else 0  # index of note 0 of the window inside target
            for key in KEYS:
                lg = logits[key][0].float()
                lg[:, :zero] = -float("inf")
                lp = torch.log_softmax(lg, dim=-1)
                lab = labels[0, :, vocab[key]]
                g = lp.gather(1, lab.clamp(min=0)[:, None])[:, 0].cpu().numpy()
                # map target position p (1..) -> note index
                for p in range(n_pos):
                    note = st + (p + 1) - offs
                    if note < st or note >= en:
                        continue
                    if not first and note < st + (win - hop):
                        continue
                    if int(lab[p]) < zero:
                        continue
                    out[key][note] = g[p]
        res = {}
        for key, v in out.items():
            by_note = np.full(n, np.nan)
            by_note[perm] = v
            res[key] = by_note
        return res

    # ---- generation ---------------------------------------------------------------------
    @torch.inference_mode()
    def generate(self, it: dict, k: int, seed: int) -> dict[str, np.ndarray]:
        tok = self.tok
        score = build_score(it)
        res = self.gen.perform_score(score, use_score_context=True, num_samples=k, seed=seed,
                                     show_progress=False)
        n = len(it["pitch"])
        t2n = tok.encode_score(build_score(it)).token_to_note
        score_perm = np.arange(n) if t2n is None else np.asarray(t2n, dtype=int)
        on = np.full((k, n), np.nan)
        du = np.full((k, n), np.nan)
        ve = np.full((k, n), np.nan)
        for i, r in enumerate(res):
            seq = r.perf_seq
            vals = seq.values
            voc = seq.vocab
            pitch = vals[:, voc["Pitch"]].astype(int)
            perm = score_perm
            if len(seq) != n or not np.array_equal(pitch, it["pitch"].astype(int)[perm]):
                raise RuntimeError("generated sequence order differs from score order")
            on[i, perm] = np.cumsum(vals[:, voc["TimeShift"]])
            du[i, perm] = vals[:, voc["TimeDuration"]]
            ve[i, perm] = vals[:, voc["Velocity"]]
        return {"onset": on, "dur": du, "vel": ve}


def selftest(scorer: SyMuPeScorer, it: dict) -> dict:
    """Round trip: encoded TimeShift / TimeDuration / Velocity equal the interchange values."""
    _, perf_seq, perm = scorer.encode_pair(it)
    vals = scorer.tok.decode_values(perf_seq.ids) if perf_seq.values is None else perf_seq.values
    voc = perf_seq.vocab
    on = np.cumsum(vals[:, voc["TimeShift"]])
    ref = (it["perf_onset_sec"] - it["perf_onset_sec"].min())[perm]
    return {
        "onset_mae_ms": float(np.mean(np.abs((on - on[0]) - (ref - ref[0]))) * 1000),
        "dur_mae_ms": float(np.mean(np.abs(vals[:, voc["TimeDuration"]]
                                           - it["perf_dur_sec"][perm])) * 1000),
        "vel_mae": float(np.mean(np.abs(vals[:, voc["Velocity"]] - it["velocity"][perm]))),
        "permuted": int(np.sum(perm != np.arange(len(perm)))),
    }


def cost(scorer: SyMuPeScorer, it: dict, batches=(8, 32, 128), steps: int = 3) -> list[dict]:
    """Peak memory and time of AdamW training steps at the paper's context (256 notes)."""
    tok, gen, dev = scorer.tok, scorer.gen, scorer.device
    score_perf, perf_seq, _ = scorer.encode_pair(it)
    seq, sseq = perf_seq[:256], score_perf[:256]
    gen.reset()
    data = gen.prepare_sequence(seq=seq, task="performance", score_seq=sseq, add_sos_eos=True)
    init, sc = data.init_seq, data.score_seq
    target = tok.add_eos_token(tok.add_sos_token(copy.deepcopy(data.target_seq).torch(device=dev)))
    model = scorer.model
    model.train()
    opt = torch.optim.AdamW(model.parameters(), lr=2e-4, weight_decay=1e-2)
    out = []
    for b in batches:
        def rep(x):
            return x[None].expand(b, *x.shape).contiguous()
        try:
            if dev.type == "mps":
                torch.mps.empty_cache()
            t0 = time.perf_counter()
            peak = 0
            for _ in range(steps):
                res = model(enc_tokens=rep(init.ids), enc_values=rep(init.values),
                            dec_tokens=rep(target.ids), dec_values=rep(target.values),
                            labels=rep(target.ids), dec_score_tokens=rep(sc.ids),
                            dec_score_values=rep(sc.values))
                opt.zero_grad()
                res.loss.backward()
                opt.step()
                if dev.type == "mps":
                    torch.mps.synchronize()
                    peak = max(peak, torch.mps.driver_allocated_memory())
            dt = (time.perf_counter() - t0) / steps
            import resource
            out.append({"batch": b, "notes": 256, "sec_per_step": dt, "mps_driver_bytes": peak,
                        "max_rss_bytes_process": resource.getrusage(
                            resource.RUSAGE_SELF).ru_maxrss})
        except Exception as e:  # noqa: BLE001
            out.append({"batch": b, "error": repr(e)})
        print(out[-1], flush=True)
    model.eval()
    return out


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("job", choices=["score", "generate", "selftest", "cost"])
    ap.add_argument("--items", required=True, help="dir of interchange npz files or a list file")
    ap.add_argument("--out", required=True)
    ap.add_argument("--device", default="cpu")
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
    torch.manual_seed(a.seed)
    sc = SyMuPeScorer(a.device)
    if a.job == "cost":
        n_params = sum(p.numel() for p in sc.model.parameters())
        r = cost(sc, load_item(paths[0]))
        (out / "cost.json").write_text(json.dumps({"params": n_params, "device": a.device,
                                                   "steps": r}, indent=1))
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
