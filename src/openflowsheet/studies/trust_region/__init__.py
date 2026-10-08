"""The trust-region adapter: Pyomo 6.10.1's `contrib.trustregion` (TRF) over a projection of the
canonical `ProblemSpec` (M05 design note `docs/design/M05-trust-region.md`; ADRs 0038-0040;
R-260 to R-273).

- `projection` — the glass box: the spec's own row builders called with a `PyomoAlgebra`, each
  property-block output an `ExternalFunction` behind an explicit output variable, and the source
  map (§6.1-§6.2). It is not a compile backend (R-003; gate G13).
- `holders` — the `ExternalFunction` contract: identity under TRF's clone, an exact-key memo,
  typed refusals, budgets and the request ledger (§6.3).

Only `projection` imports Pyomo, and only it is missing from an install without the audited `nlp`
environment; this package and the other modules import without it (M03 G6's rule,
`tests/test_m03_nlp_isolation.py`, extended by `tests/test_m05_isolation.py`).
"""
