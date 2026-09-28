# Defects

Things that are broken in this repo's code or data.

| ID | Date | Reporter | Status | Item |
|---|---|---|---|---|
| DF-01 | 2026-09-27 | data-engineer (D-10) | FIXED 2026-09-27 (lead; scale-aware ridge retry, then pseudo-inverse, in `_penalized_fit`; regression test in `test_tempo.py`; the real failing pair has not been rerun yet) | **`tempo_stability` crashes with `LinAlgError` (Cholesky, "potrf return info 7213")** in `features/tempo.py` `_penalized_fit` (`cho_factor`), reached from `control.control_features` -> `tempo_stability` -> `fit_time_map` (the 4-bar phrase fit). Seen once in 66 pairs: PianoCoRe Aria-AMT transcription `Aria_888980_0` of ASAP Beethoven 23-1 `Cai01` (Appassionata I) aligned to the ASAP score. Reproduce: `scripts/check_transcription_noise_d10.py` (the pair shows in `transcription_pairs_failures.csv`). Suggested fix (feature-engineer): fall back to `lstsq`, or add a small ridge when the penalized normal matrix is not positive definite. Not seen on MAJEPPA (1,604 performances). |
