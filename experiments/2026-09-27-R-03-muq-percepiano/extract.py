"""R-03 step 1: frozen MuQ embeddings of the S-02 PercePiano renders, pooled per layer.

For every clip: one MuQ-large-msd-iter forward pass (fp32, MPS, whole clip), then for each
hidden state 0-12 and for the average of hidden states 9-12 (CrescendAI's "L9-12"), mean ‖ std
pooling (population std, sqrt(var + 1e-8), as MuQStatsModel.pool) over the first T frames,
T in {1000, 300}. Output: artifacts/muq_pooled.npz with

  stems (N,), n_frames (N,), pooled_1000 (N, 14, 2048), pooled_300 (N, 14, 2048)

Row 13 of the layer axis is the L9-12 average. Resumable via artifacts/muq_partial/.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import soundfile as sf
import torch

from pianolens.audio import render as R
from pianolens.data.percepiano import percepiano_index

HERE = Path(__file__).resolve().parent
ART = HERE / "artifacts"
MODEL_ID = "OpenMuQ/MuQ-large-msd-iter"
TRUNCS = (1000, 300)


def pool(h: torch.Tensor) -> np.ndarray:
    """h: (T, D) float -> (2D,) mean ‖ std, population variance, +1e-8 inside the sqrt."""
    h = h.double()
    mean = h.mean(0)
    var = ((h - mean) ** 2).mean(0)
    return torch.cat([mean, (var + 1e-8).sqrt()]).float().numpy()


def main() -> None:
    from muq import MuQ

    wav_dir = R.render_dir(R.CRESCENDAI_SALAMANDER, "percepiano")
    stems = [p.split(":", 1)[1] for p in percepiano_index().performance_id]
    part = ART / "muq_partial"
    part.mkdir(parents=True, exist_ok=True)
    dev = "mps" if torch.backends.mps.is_available() else "cpu"
    # load straight onto the device: MuQ caches rotary tables on the device of the first call
    model = MuQ.from_pretrained(MODEL_ID).to(dev).eval()
    t0 = time.time()
    done = 0
    for i, stem in enumerate(stems):
        out = part / f"{stem}.npz"
        if out.is_file():
            continue
        y, sr = sf.read(str(wav_dir / f"{stem}.wav"), dtype="float32")
        assert sr == 24_000 and y.ndim == 1
        with torch.no_grad():
            o = model(torch.from_numpy(y)[None].to(dev), output_hidden_states=True)
            hs = torch.stack([h[0] for h in o.hidden_states]).cpu()  # (13, T, 1024)
        assert hs.shape[0] == 13
        layers = torch.cat([hs, hs[9:13].mean(0, keepdim=True)])  # (14, T, 1024)
        res = {f"pooled_{t}": np.stack([pool(layers[k, :t]) for k in range(14)])
               for t in TRUNCS}
        np.savez(out, n_frames=hs.shape[1], **res)
        done += 1
        if done % 100 == 0:
            el = time.time() - t0
            print(f"{i + 1}/{len(stems)}  {el:.0f}s  {el / done:.2f}s/clip", flush=True)
    wall = time.time() - t0

    n_frames, pooled = [], {t: [] for t in TRUNCS}
    for stem in stems:
        z = np.load(part / f"{stem}.npz")
        n_frames.append(int(z["n_frames"]))
        for t in TRUNCS:
            pooled[t].append(z[f"pooled_{t}"])
    np.savez(ART / "muq_pooled.npz", stems=np.array(stems), n_frames=np.array(n_frames),
             **{f"pooled_{t}": np.stack(pooled[t]).astype(np.float32) for t in TRUNCS})
    meta = {"model": MODEL_ID, "device": dev, "dtype": "float32", "n": len(stems),
            "new_clips": done, "wall_sec_new": round(wall, 1), "torch": torch.__version__,
            "render_config": R.CRESCENDAI_SALAMANDER.config_hash(),
            "frames_min_median_max": [int(np.min(n_frames)), int(np.median(n_frames)),
                                      int(np.max(n_frames))],
            "clips_over_1000_frames": int(np.sum(np.array(n_frames) > 1000))}
    (ART / "extract_meta.json").write_text(json.dumps(meta, indent=2))
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
