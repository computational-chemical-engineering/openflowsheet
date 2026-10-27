# E01 track A — build decisions and facts

Design: `docs/derivations/E01-design.md` (ADR 0052 Proposed; R-850…R-862). One line per choice
(`DECISION: <q> → <choice>. Alternative: <x>. Reversible by: <how>.`); facts as `FACT:`. Folded into
the single `reviewer` pass (§5.1).

Identity check per commit (§4.14, A1 at the branch base): `git diff --stat f8a68fed..HEAD --
src/openflowsheet/{compile,thermo,models,verify,orchestrator,numerics,application,adapters,graph,ir,run,units}
src/openflowsheet/{canonical,compiled,serialize}.py src/openflowsheet/studies/{trust_region,sensitivity.py,sweep.py,estimation.py}`
must be empty. (`main...wp/E01` also shows S11's own changes until S11 merges, so the base is E01's
merge commit `f8a68fed`.) A2 (`scripts/s11_identity.py`) runs the whole suite in two trees and is
I1's.

## WO-A1 (core)

- FACT (§4.2.3 memo, Q16): `ParametricTwin.__init__` passes one `symbols` mapping to every row of a pass, but
  `_build` makes a fresh pins mapping per row (same value objects); `_builds` (failure path only) rebuilds a row
  with a different pins mapping. `reference.row_values` passes one `symbols` and `spec.parameters` to every row.
  Verified by `tests/test_e01_a_core.py::test_the_twin_and_the_reference_pass_one_mapping_to_every_row_of_a_pass`.
  The memo is enabled.
- DECISION: memo key → identities of (variables, block outputs, algebra) plus the identities of the pinned *values*,
  previous pass's objects held so no id is reused. Alternative: the variables mapping's identity alone (§4.2.3's
  wording), which would hand `_builds`' culprit search a row built with other pins. Reversible by: `_Memo.row` key.
- DECISION: contributors given to `AssessmentProgram.build` → keyword-only `contributors=` (default: the
  `register_contributor` registry in `cost, lca, derived` order). Alternative: registry only (a test toy would
  pollute it). Reversible by: dropping the keyword.
- DECISION: request refusals of `evaluate`/`twin`/`linearize` → returned as `Refusal` (the union return), as `build`
  does; evaluation domain failures raise `TwinEvaluationError` (§4.2.3). Alternative: raise a typed exception.
  Reversible by: the three methods' returns.
- DECISION: `twin(())` → compiled over the first non-structural parameter (a `ParametricTwin` needs ≥ 1); its column
  is never exposed. Alternative: an artificial anchor θ in every program. Reversible by: `AssessmentProgram.twin`.
- DECISION: `linearize` → the decisions are always symbols of the twin (columns reported only for `symbolic`), so
  `∂/∂x` is taken at the decision values. Alternative: refuse decisions not in `symbolic`. Reversible by: `linearize`.
- DECISION: a held regime naming an entry the program lacks → `ASSESSMENT_REGIME_INADMISSIBLE` (detail "entries
  the program lacks"). Alternative: ignore the extra entry. Reversible by: `build`.
- DECISION: `select` when the held regime cannot be evaluated at `x` (`TwinEvaluationError`) → release every entry
  to the rule. Alternative: propagate the error. Reversible by: `select`.
- DECISION: the float path maps a complex power (negative base of `**(1/3)`) to `TwinEvaluationError`, as CasADi's
  NaN is. Other `TypeError`s propagate. Reversible by: `_float_rows`.
- DECISION: `view_of` molar masses → the `selectable_bases()` entry with the provider's id over the same component
  set (`RevisionFlowsheet` does not carry its basis). Alternative: a `molar_masses=` argument. Reversible by:
  `views._basis`.
- DECISION: `UnitRef.parameters` → the unit's `Contribution.parameters` keyed by full pin ids; `structure` → the
  unit object. Reversible by: `views._unit_ref`.
- DECISION: schema field names the note does not spell (item inputs, `utilities[]`, `materials[]`, `lca` exchanges,
  `derived` numerator/denominator, `defaults` keys) → named after the note's symbols (`schemas/assessment.schema.json`,
  `defaults.py`), `additionalProperties: false` throughout, `schema_version: "assessment-v1"`; `functional_unit`
  sits under `lca` as §4.11 lists it. Later WOs extend it. Alternative: an open schema until A4/B2. Reversible by:
  the schema file (no fixture yet).
- DECISION: admissibility nominal of every `size` row → `S_max` (§4.3.1's example), set by the contributor.

## Escalations (open)

- **ESC-A1 (schema identity partition; blocks green on 4 tests).** `schemas/assessment.schema.json` declares
  `applies_to.configuration_sha256` (§4.11 names it). T08's sha256 partition (`scripts/t08_numerical_policy.py`
  `schema_sha256_names`, `benchmarks/t08/numerical_policy_v2.yaml`) classifies every `*sha256*` property of every
  schema; `configuration_sha256` is classified only in M02's addendum, so it is now unclassified in v2. Failing:
  `test_m04_numerical_policy.py::test_a37_the_sha256_partition_follows_the_schemas`,
  `test_m02_schemas.py::test_g1_the_sha256_partition_holds_over_m02s_schemas`,
  `test_t08_adr0025.py::test_a1_the_policy_file_is_what_its_generator_emits` and `…a_tampered_policy_file_fails_its_audit`.
  (`report`'s schema at A5 adds `assessment_sha256`, `state_sha256`, `regime_sha256`.) Neither file is in E01's
  ownership (§5.1) and §4.14 did not list them. Proposed (M05/M04 precedent): an E01 addendum in `ADDENDA` with its
  own policy table classifying the assessment schemas' names, so v2's content does not move. Not taken: renaming the
  note's field, or editing v2 (moves a registered policy file). Owner to decide: I1 / design lane.
  (`test_m07_journey.py::test_a21_…` failed only on the uncommitted tree: it compares HEAD to the working tree.)
