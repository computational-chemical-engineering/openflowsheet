# ADR 0009 — The execution plan, the recycle policy block and the recycle trace: an additive extension of the K03 schemas

**Status:** Accepted 2026-09-24 — T02's manifest `evidence/T02/b68585f775cc2b009ae1b130eebb865150cf943c/manifest.json` is `tested` (37 of 37 checks, A02/A34 measured on the CI pair, run 35984230481) and the fixtures of every extended schema were regenerated from live code (R-015). Proposed by the T02 specification pass (`docs/derivations/T02-recycle-spec.md` §3.4, §5.8, §9).  
**Date:** 2026-09-24  
**Amended:** 2026-09-24, D3's reproducibility classes for `kappa_2` and `gamma_inf` (the T02 review, `docs/reviews/T02-review.md` M4, on the CI pair's measurement); the schema does not change  
**Author:** Fable 5.1 (Fable owns every ADR and the globalization policy, plan §1.3)  
**Affected requirements:** D01 (explicit plans and attempts for a hybrid SM/EO execution — the plan must be able to say *which* parts run causally, which are torn and which are solved EO), D20 and blueprint §8.3 R0 (the plan is a structural artifact and must be bit-identical on the registered platforms), A02 (the region a cross-unit specification promotes must be recorded, and the capability failure must be a typed outcome), blueprint §7.2 ("record depth, regularization, restart, and coefficient safeguards" — recorded means on the trace, under the declared numerical policy)  
**Affected packages:** T02 (introduces everything below), K03 (its five schemas are extended, never narrowed; its fixtures are regenerated; its assertions A00–A35 must stay green), K04/K05 (the run bundle carries an `ExecutionPlan`; replay compares it as R0), T03 (the phase-closure reasons are the hooks its controller will fill), T06 (scoring reads `RECYCLE_STAGNATION` and `CAPABILITY_UNAVAILABLE` as typed failures)  
**Blueprint authority:** §7.1 (the plan stage and its record: "deterministic structural rules; recorded estimates"; "the plan distinguishes structural-only decisions from numerical observations"), §7.2 (the recycle safeguards to record), §7.7 (every fallback edge typed, counted, with a checkpoint policy), §8.3 (R0 versus R1/R2)  
**Companions:** `docs/interfaces-frozen.md` §2 (the schema list and the change rule this ADR follows); ADR 0007 D1–D2 (the classes and floors of the new fields); K03 §12 (the five field sets extended here); T02 §3.4 (`ExecutionPlan`), §5.8 (the trace fields), §9 (the vocabulary).

## Context

`docs/interfaces-frozen.md` froze K03's five schemas with `additionalProperties: false` and single-valued literals on purpose, so that a later policy is a *new value a reader can see* rather than a silent change of meaning. T02 needs three things the frozen five cannot express: a plan with more than one step (K03's `SolvePlan` describes one tear problem, and a flowsheet with an EO region, a nested loop or a promoted specification has several), a recycle policy with nine registered constants and a method selector (there is no field to hold them, and `SolvePolicy` refuses unknown ones), and trace events for an acceleration step, a restart and a plan-step boundary (`SolveEvent.kind` is a closed enum). The freeze's rule is that each of these is a Fable-authored ADR stating reason, affected requirements, migration impact and acceptance evidence. This is that ADR.

The alternative the T02 brief proposed — a new runtime type holding per-region `SolvePlan`s, "so that `SolvePlan` itself is untouched and no ADR is needed" — is right about `SolvePlan` and wrong about the ADR: the policy constants and the trace kinds still have nowhere to go, and a plan document that is in every bundle and in the identity job is a schema in the frozen list's sense whether or not a JSON Schema file is written for it (T01's `StructuralReport` set that precedent without one; this ADR writes the schema, because the plan is compared byte for byte across platforms and a comparison needs a documented shape).

## Decision

### D1. `ExecutionPlan` — a new schema, added to the frozen list under T02

`schemas/execution-plan.schema.json`, `additionalProperties: false`, required: `plan_id`, `model_version`, `constants_sha256`, `policy_id`, `structural_report_ref` (`{model_version, constants_sha256}` of the T01 report the plan was built from), `steps` (array, `minItems: 1`), `estimates` (`{loop_count, region_count, largest_region_dimension}`, integers).

A step is an object with `kind ∈ {evaluate, converge, solve_eo}`, `index` (dense, increasing), `units` (ordered ids, `minItems: 1`), and:

- `evaluate`: nothing more (the unit's local evaluator with every inlet known).
- `converge`: `tear_streams` (ordered), `method ∈ {newton_tear, anderson}` (the resolved value; never `auto`), `solve_plan` (a K03 `SolvePlan`, validated against the unchanged `solve-plan.schema.json`), `region_on_merge` (a `solve_eo` step object, the region that replaces the loop under T02 §4.4; `null` when a unit of the loop is not EO-capable, with `merge_unsupported: {unit, method}` beside it).
- `solve_eo`: `solve_plan` (a K03 `SolvePlan` with `tear_variable_ids = tear_row_ids = []`), `specification_rows`, `adjusted_variables`, `target_variables`, `removed_specification_rows` (arrays of ids, empty for a region that is not a promoted specification), `signature_units` duplicated from the `SolvePlan` for readers that do not open it.

Reproducibility class: **R0 entire** (ADR 0007 D1: ids, integers, orderings, declared scales and bounds). Its R0 projection is the whole document. It joins the G05 identity comparison beside the `StructuralReport`.

### D2. `SolvePolicy.recycle` — one required object added to the frozen `SolvePolicy`

`recycle`: `additionalProperties: false`, required `method ∈ {auto, newton_tear, anderson, eo}`, `depth_max`, `beta`, `beta_substitution`, `beta_substitution_oscillating`, `condition_max`, `coefficient_max`, `stagnation_window`, `stagnation_ratio`, `oscillation_window`, `max_restarts`, `max_iterations_per_attempt`, `step_halvings_max`; optional `tear_streams` (an override naming a tear set that leaves the loop acyclic, T02 §3.3). Registered defaults and the argument for each: T02 §5.10, policy id `T02-recycle-policy-v1`. `eo` promotes every loop to a region (T02 §6.1's registered override). Every value is R0 (a policy constant).

No other `SolvePolicy` field changes. The K03 fields keep their literals; `derivative_path` keeps its two values (the region Newton uses the assembled Jacobian directly, which is the `assembled_schur` path with an empty tear).

### D3. `SolveEvent` — kinds, fields, an outcome and closure reasons, added

- `kind` gains `unit_evaluated`, `region_opened`, `region_closed`, `acceleration`, `restart`. K03's eleven keep their meaning; `plan_built` is emitted once for the `ExecutionPlan` and carries `step_count`.
- Fields, all nullable and null except on the event that defines them: `step_index` (int; on every event from `region_opened` to `region_closed`, and on `unit_evaluated`), `depth_used` (int), `columns_dropped_condition` (int), `columns_dropped_coefficient` (int), `kappa_2` (number ≥ 1), `gamma_inf` (number ≥ 0), `beta_substitution` (number), `oscillation_flag` (bool), `restart_reason ∈ {stagnation}`, `restart_count` (int), `merge_into_eo ∈ {null, "taken", "unsupported"}` with `merge_unsupported: {unit, method}` when `"unsupported"`.
- `outcome` gains `RECYCLE_STAGNATION` (attempt level; the give-up of T02 §5.6) and `CAPABILITY_UNAVAILABLE` (plan level; T02 §7.4). `PHYSICALLY_INFEASIBLE` stays absent.
- *Amended by ADR 0005 D8 (T03): the structured phase reasons below move to the next `attempt_opened` (`phase_update(<cause>)`) or the terminal `solve_closed`; `attempt_closed` records what the core did.* `message` on an `attempt_closed` with outcome `PHASE_UPDATE_REQUIRED` is structured: `phase_disappeared(unit, phase, variable)`, `inadmissible(stream, branch, value)` or `kernel_disagrees(unit, regime)` (T02 §6.3), or K03's wall message on the tear path. `message` on an `initializer_candidate` whose lifted split was overwritten from the kernel is `projected(stream, supplied_branch, kernel_regime)` (T02 §6.2; K03 A08's precedent for a projected guess — no new kind). A structured message is a string with a registered grammar, so the schema does not change for it; the grammar is T02 §9's.
- `rejection_reason` is unchanged.

Reproducibility classes (ADR 0007 D2.3, added by T02 in the same change, with provenance T02 §5.8): R0 — `step_index`, `depth_used`, both drop counts, `beta_substitution`, `oscillation_flag`, `restart_reason`, `restart_count`, `merge_into_eo`; R1/R2 — `kappa_2` and `gamma_inf`, **compared within a comparability window and recorded outside it** (amended 2026-09-24 by the T02 review, M4, on the CI pair's measurement): the two are least-squares quantities of *residual differences*, whose cross-platform agreement scales as `ε / ‖f̂_k‖∞` — measured `≤ 3.3e-13` relative on every accelerated event with scaled residual `‖f̂_k‖∞ ≥ 1e-4`, and up to `1.06e-8` (REC-03 γ=0.1, event 6, `‖f̂‖ = 5.5e-8`) below it, four decades above `κ₂ ε` — so no constant floor describes them. They are compared under ADR 0007 D2.1's relative rule with **no absolute floor** on `acceleration` events whose `residual_inf_unscaled / S ≥ 1e-4`, and are recorded and shape-checked, not value-compared, on events below that (the treatment `UNREPRODUCIBLE_COUNTS` receive). The decisions they feed (`depth_used`, the drop counts) are R0 and promised, in D2.4's sense, only when not near threshold: `kappa_2 ∉ [1e7, 1e9]` and `gamma_inf ∉ [1e3, 1e5]` on every accelerated event of a registered case, asserted per platform (T02 A19's clause, generalized). The first version of this paragraph registered floors `1.0` and `1e-12`; both are withdrawn — the `kappa_2` floor was a category error (`κ₂ ≥ 1` by definition, so it acted as an absolute allowance of one), the `gamma_inf` floor the wrong kind of object.

### D4. `AttemptContext` and `Checkpoint` — one field each

`AttemptContext.active_phases`: the per-unit active phase set of T02 §6.3.1 (`[[unit, regime], ...]`, the same shape as `signature`), so that a region attempt records *which lifted variables were pinned*, not only which regime was declared. `Checkpoint.step_index`. Both R0.

### D5. `SolvePlan` does not change

Its field set, its schema and `test_k03_schemas.py`'s two structural rules (square inner block; tear rows match tear variables — both vacuous for a region) are unchanged. A region's `SolvePlan` has empty tear arrays, which the schema already permits (`uniqueItems` without `minItems`).

### D6. `FailureBundle.suggested_actions[].action` — one value added

`schemas/failure-bundle.schema.json`'s action enum (`increase_budget`, `supply_initial_guess`, `revise_specification`, `report_defect`) gains **`provide_derivatives`**: the typed proposal for a `CAPABILITY_UNAVAILABLE` solve (T02 §7.4), with the unit whose manifest declares the derivative `unavailable` among the bundle's implicated source objects, taxonomy class "model domain/conservation/derivative defects" (blueprint §8.2's minimum taxonomy, the class that names derivatives). `report_defect` is **not** the answer: blueprint §5.2 makes `unavailable` an honest declaration, and a bundle that calls an honest declaration a defect points the reader at the wrong object. The interim code path that mapped `CAPABILITY_UNAVAILABLE` to `report_defect` is replaced when this ADR's schema change lands. Preconditions and permissions of the action (blueprint §8.2): it proposes a model change outside the solve and needs no runtime permission.

## Alternatives considered

- **A runtime type with no schema for the plan, on T01's `StructuralReport` precedent.** Rejected: the plan is compared byte for byte in G05 and replayed by K05; a compared document needs a documented shape, and "not in the list" would only postpone the ADR to the first mismatch nobody could read.
- **A second policy document (`RecyclePolicy`) pinned beside `SolvePolicy` in the run manifest.** Rejected: one solve, one policy; two documents would let a replay pin one and not the other, and `policy_id` would name half a policy.
- **A separate trace for the recycle iteration.** Rejected: one `sequence`, one identity comparison, one replay; the K03 kinds already cover the attempt boundaries and the trials, and five kinds plus nullable fields cost less than a second stream with its own ordering rules.
- **Widening `SolvePlan` with a `steps` array.** Rejected: it would change the meaning of every existing K03 fixture and of `test_k03_schemas.py`; the plan is a list *of* `SolvePlan`s, not a bigger one.
- **Making `recycle` optional with defaults.** Rejected: K03 §12's rule — "no field has a default that could be mistaken for a declaration" — and a policy hash must cover the constants that were in force.

## Consequences

- C1. `schemas/execution-plan.schema.json` is added; `schemas/solve-policy.schema.json`, `solve-event.schema.json`, `attempt-context.schema.json`, `checkpoint.schema.json` and `failure-bundle.schema.json` are extended as D2–D4 and D6 say; `schemas/README.md` and `docs/interfaces-frozen.md` §2 list the change under T02 with this ADR's number.
- C2. **Migration:** every K03 round-trip fixture under `tests/fixtures/schemas/` for the four extended schemas is regenerated by the committed generator from a real solve (R-015), and the migration report is this section: the only instances are the repository's own fixtures; no user document exists yet. A K03 `SolvePolicy` document without `recycle` is invalid after this ADR — by design: the policy in force must be visible.
- C3. `tests/test_k03_schemas.py` gains: an `ExecutionPlan`'s steps are dense and increasing and every `converge`/`solve_eo` step's `solve_plan` validates against the unchanged `SolvePlan` schema; `acceleration` events carry `kappa_2`/`gamma_inf` iff `depth_used ≥ 1`; no event serializes a non-finite number (unchanged rule, new fields).
- C4. ADR 0007 D2.2's table gains the two float rows of D3 with their provenance; by D2.3 that is an ordinary addition, not a reopening.
- C5. `docs/decision-register.md` gains an entry pointing here (the schema-list change) and one for T02's policy rulings (`T02-recycle-spec.md` §5.10, §6.3).

## Acceptance evidence

- T02 assertion A01 (plan shape and per-step `SolvePlan` validity), A02 (R0 identity across the CI pair), A24 (the `projected(...)` message on the existing kind), A25 (the A02 region's record), A27 (`provide_derivatives` in the failure bundle), A32 (the merge fields), A33 (trace well-formedness with the new kinds), A34 (reproducibility classes), A35 (K03 A00–A35 still green) — `evidence/T02/<commit>/manifest.json`.
- The regenerated fixtures validate against the extended schemas and the K03 gate is green on both architectures.
