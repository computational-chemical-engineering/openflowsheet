"""The general NLP bridge's solver-independent half (M03 spec §8; ADR 0032).

`formulation` declares an optimization problem over a flowsheet's pinned inputs and builds its
full-space form over the parametric twin; `verification` judges a candidate on the re-solved,
certified simulation (V1-V6, with a reduced KKT check from M03's adjoints); `closure` is the
study-level optimization closure — `optimization_readiness`, the `OptimizationReport` type and
`optimize()`, which without an audited NLP solver returns `UNSUPPORTED` and never raises.

No module here imports Pyomo, cyipopt or any other third-party optimizer: the one module allowed to
is the gray-box adapter `openflowsheet.studies.nlp.greybox` (WO-8), which exists only with the
optional `nlp` extra after the [A10] audit (`docs/m03-ipopt-audit.md`) and Frank's licence answer.
"""
