# Superseded: exploratory only (R-10b)

This folder was pre-registered on the RTX 5080 box on 2026-10-05 as "R-10" by an agent that could
not see the Mac session's R-10 pre-registration, which was already in the shared history (pushed
2026-10-05, with an eval-auditor pre-run review). **The official R-10 is
`experiments/2026-10-05-R-10-h1b/` (mean-curve R²c primary, fresh pieces).** This duplicate was
renamed R-10b and is **exploratory and non-deciding**. Its result does not decide H1b and must not
be used to choose between statistics after the fact.

- The `README.md` pre-registration is kept as written (its hash is still checkable), but its
  "deciding statistic" wording no longer decides anything.
- Run state when stopped (2026-10-06 ~01:55 UTC, by the lead, on Henry's decision): prep done
  (42 pieces); frozen SyMuPe and E generation complete (K = 32); Pianist Transformer generation
  started, not finished; no analysis run. Outputs stay local in `job/outputs/` (gitignored) and the
  job is resumable.
- Worth keeping, as a methods note for future work: on R-02 curves, the span "captured share" has
  an envelope-null floor of about 0.58 at K = 32 (simulate.py, calibration pieces), so any
  captured-share statistic needs a structure-free floor.
