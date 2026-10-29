# V03 brief: ruling round 1 — two build-lane questions before the 0.3.0 candidate (design lane, `specifier`)

Worktree `/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/v03`, branch `wp/V03` (head `98701cca`; ADR 0053 and
`docs/derivations/V03-release-spec.md` are yours to amend). Docs-only; commit, do not push. Register from **R-881** (R-872…
R-880 are V03's, R-890…R-899 are E01b's on another branch).

## Q1 — `semantic_role` has no role for S11's new units (a defect found by the docs engineer, verified by the orchestrator)
- `schemas/process-revision.schema.json:73` (frozen, plan §2.2) enumerates `semantic_role`: feed, product_sink, mixer,
  heater, flash, splitter, reactor, separator, valve, pump, heat_exchanger. There is no turbine, compressor, column or
  `other`.
- **Ten committed S11 cases use `"semantic_role": "other"`** (`grep -rl '"semantic_role": *"other"' benchmarks tests`, e.g.
  `benchmarks/s11/thermal/TH-C2.json`, `TH-R1.json`, `TH-V1.json`, `benchmarks/s11/gp/GP-M1.json`, `GP-C3.json`). Through the
  application layer they fail validation with `SCHEMA-01` (`wp/DOC`'s `docs/DOC_DECISIONS.md` D3/Q1 has the reproduction).
  The binder does not read the role (it is descriptive); the S11 tests bypass application validation.
- The docs examples therefore label a turbine and a compressor `pump` — a workaround that misdescribes the unit.
- Decide: the additive enum values (at least `compressor`, `turbine`; whether `column`, and whether an `other`), the route for
  a change to a frozen schema (ADR: new ADR 0054 or an amendment to ADR 0051, with migration impact — an additive enum value
  keeps every existing document valid), whether `$id`/schema version moves (R-149/R-185: the `$id` move is out of scope),
  how the ten cases are corrected, the test that would have caught it (every committed case validates through the
  application's validator), and the work-order text (fold it into V03's WO-3/WO-4, one engineer).

## Q2 — does `wilson-ig-v1` bind from package data without a path? (from WO-1/WO-2's engineer)
- V03.A12 and A19 say `wilson-ig-v1` binds from package data. WO-2 made the binder and verifier pass the packaged records path
  to `wilson_ig` (D-1/D-4 in `docs/V03_DECISIONS.md`, commits `365607f2`, `34236737`), leaving `wilson_ig.py` untouched so
  S11.A75 and both providers' `implementation_sha256` stay. But `WilsonIdealGasProvider()` with no argument still finds the
  records only in a source checkout. Changing that edits v1 (identity; S11.A75 amended).
- Decide: is passing the path enough for A12/A19 (amend their text), or must the no-argument provider find package data (then
  the identity consequence and the exact amendment)?

## Constraints
Frank's directives: as few limitations as possible; batch, then test once; finish lean. Nothing registered moves numerically.
No production code. Do not start subagents. Do not send personal identifiers to any external service. Temp files under
`/home/frankp/.cache/`. Context cap ~120k. Deliverable: amendments to ADR 0053/V03 spec (and the new ADR if you choose one),
register entries, one docs-only commit including this brief. Report in at most 15 lines.
