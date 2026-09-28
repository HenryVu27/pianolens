# factor-analyzer 0.5.1 traps (found in R-01 audit, 2026-09-27)

- **`phi_` is misaligned with `loadings_` for oblique rotations.** `FactorAnalyzer.fit` flips
  signs, then re-sorts the loading columns by variance (`new_order`) and re-sorts `structure_`,
  but never re-sorts `phi_`. Any factor-correlation table built from `phi_` is wrong whenever
  the sort permutes columns (in R-01 k=4 it swapped F3/F4: reported "F1-F4 0.49" was really
  quality x pedal). Correct phi: `pinv(L) @ (A @ A.T) @ pinv(L).T` with `A` the unrotated
  loadings of the same fit (diag comes out exactly 1; residual ~1e-15), or re-sort `phi_`
  yourself. Sanity check with raw item-cluster means.
- **`get_communalities()` = row sum of squared pattern loadings**, which is not the communality
  under an oblique rotation (needs diag(L phi L')). It can exceed 1 without any Heywood case.
  True communality = row sum of squared *unrotated* loadings (rotation-invariant). R-01's
  "Heywood 1.02" was this artifact (true h2 0.89). Same for `get_factor_variance()` shares.
- sklearn 1.9 `force_all_finite` crash: the keyword shim in R-01 run.py is safe. Verified: k=4/5
  oblimin loadings identical (max diff 0.0) to factor-analyzer 0.5.1 + scikit-learn 1.5.2 with no
  shim (`uv run --no-project --with factor-analyzer==0.5.1 --with scikit-learn==1.5.2 ...`).
