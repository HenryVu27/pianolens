---
name: gpu-job
description: How to run GPU work for PianoLens on Henry's RTX 5080 box or a rented cloud GPU. Use before planning any training, fine-tuning, bulk transcription or bulk embedding extraction that is too slow on the Mac.
---

# GPU jobs

## Where things run

| Work | Where |
|---|---|
| Symbolic features, GBMs, small MLPs, factor analysis | Mac (CPU) |
| MuQ/MERT embeddings for at most a few thousand clips | Mac (MPS, fp32), or the 5080 |
| Transcription fine-tuning, expression-model training, bulk embedding | RTX 5080 |
| Needs more than 16 GB VRAM, or more than about 24 h on the 5080 | Cloud, only after O-04 approval |

## RTX 5080 facts

- 16 GB VRAM, Blackwell (sm_120).
- It needs PyTorch wheels built for CUDA 12.8 or newer: `uv pip install torch --index-url
  https://download.pytorch.org/whl/cu128`, or a newer CUDA index. Older wheels fail with "no
  kernel image is available".
- Mixed precision: bf16 is supported. MuQ must run in fp32.
- Connection method is not yet set (O-03). Until it is, agents write a self-contained job folder
  and Henry runs it.

## Job folder contract (works for the 5080 and for cloud)

Create `experiments/<id>/job/` with these files:

- `README.md`: what the job does, expected runtime and VRAM, and the exact commands.
- `setup.sh`: creates the env with uv and pins the torch index.
- `run.sh`: the entry point. Idempotent and resumable (checkpoints every N steps).
- `fetch_data.sh`: pulls the needed data from its public source on the GPU box, not by copying
  from the Mac, unless the data is small derived data.
- `outputs/` is written on the GPU box. Henry copies it back into `experiments/<id>/artifacts/`.

## Before asking for cloud

Estimate GPU-hours from a short timed run on the 5080. State price times hours. Add the request
to O-04 in `WORKBOARD.md`. Never create cloud accounts or enter credentials.
