# `schemas/`

Normative JSON Schemas (draft 2020-12) for every serialized contract of the process runtime,
plus the round-trip fixtures that exercise them. A schema is added when the object it describes
is actually used, not in advance (implementation plan §2.2).

Present now (introduced by **P00**, repository bootstrap):

| File | Describes |
| --- | --- |
| `requirements-ledger.schema.json` | `docs/requirements.yaml`: requirements, gates, and packages |
| `evidence-manifest.schema.json` | `evidence/<package>/<commit>/manifest.json` per plan §7 |

Added by **P01** (the plan §2.2 P01 row, frozen in `docs/interfaces-frozen.md` §2):

| File | Describes |
| --- | --- |
| `quantity.schema.json` | A physical quantity in internal SI units, with `kind`, dimension, role, bounds and nominal |
| `component-record.schema.json` | Chemical identity, molecular weight, elemental composition or its explicit absence, parameters with provenance, and data rights |
| `specification.schema.json` | A target with a fixed value or bounds, its unit, tolerance, role and provenance |
| `model-manifest.schema.json` | Ports, mathematics, per-output derivative declarations, initialization, validity domain, implementation artifact and execution requirements; per-equation accumulation declaration (ADR 0008, migrated 2026-09-16) |
| `process-revision.schema.json` | Component set, instances, connections, specifications and provenance for one revision |
| `validation-report.schema.json` | The result of validating one revision for one task: status, staged checks and structural counts |
| `units.json` | Not a JSON Schema: the `kind` -> dimension/SI-unit table of ADR 0001 D1, mirrored by `process_runtime.units` and checked against it by `tests/test_schemas_p01.py` |

Added by **K01** (the plan §2.2 P02/K01 row; promoted in the window ADR 0008 D4.1 and D4.4 name,
because adding `parameter_ids` or `row_accumulation` afterwards would be a migration):

| File | Describes |
| --- | --- |
| `compiled-problem-metadata.schema.json` | `CompiledProblemMetadata`: the ordered variables, equations and pinned inputs, the scales, the per-row accumulation, the negotiated capabilities and the identity hash |
| `evaluation-result.schema.json` | `EvaluationResult`: status, residual values or their honest absence, phase signature, state and problem identity, and the per-block call counters |
| `jacobian-result.schema.json` | `JacobianResult`: a sparse Jacobian in canonical CSC with explicit row and column identity, pattern provenance and source map |

`PropertyCapabilities` is on the same plan row and is deliberately **not** here: no
`PropertyProvider` exists yet, and a schema is added when the object it describes is used. It waits
for K02.

The CSC arrays of a `JacobianResult` are anonymous integers, so almost every rule that makes them
mean a matrix is cross-field and cannot be stated in JSON Schema: `indptr` has one more entry than
`col_ids`, starts at zero, is non-decreasing and ends at `nnz`; `indices` and `data` are both `nnz`
long; every index is a row; and rows ascend within a column. Those, and the rule that
`row_accumulation` keys exactly `equation_ids`, and that `values` is present exactly when the status
is `ok`, are `process_runtime.serialize.check_*`, which `tests/test_k01_schemas.py` runs alongside
the schema. Every invalid fixture there is wrong in exactly one way and says so in a `_why_invalid`
line; the test asserts that each is rejected by the schema or by the checks, because a fixture
nothing rejects is a hole rather than a test.

Two cross-field rules a JSON Schema cannot express are `process_runtime.units.check_quantity`,
which every round-trip fixture runs alongside the schema: a decoded `NaN` or infinity satisfies
`type: number` but is rejected in every semantic input (ADR 0001 D1.5), and `dimension` and
`unit` must be the ones registered for the declared `kind`.

Delivery order for the process schemas (implementation plan §2.2):

| Package | Schemas |
| --- | --- |
| P01 | ProcessRevision, Quantity, ComponentRecord, ModelManifest, Specification, ValidationReport |
| P02/K01 | CompiledProblem metadata, EvaluationResult, Jacobian metadata, PropertyCapabilities |
| K03 | SolvePolicy, SolvePlan, SolveEvent, AttemptContext, Checkpoint metadata |
| K04/K05 | SolutionCertificate, FailureBundle, RunManifest, replay artifact manifest |
| K06/T07 | ChangeSet, Job, job events, authorization capability references |
| M01–M04 | ExperimentRequest/Result, ModelEvidence, Study, SurrogateManifest, OptimizationReport |

The schema list is frozen at the end of P01 and changes thereafter only by a design-lane ADR
under `docs/adr/` (implementation plan §1.3). A real migration is tested when a schema actually
changes.

Added by **T02** under ADR 0009 (additive; every K03 fixture regenerated from a real solve, R-015):

| File | Describes |
| --- | --- |
| `execution-plan.schema.json` | `ExecutionPlan`: the ordered steps — acyclic `evaluate`, `converge` over a tear set, `solve_eo` over a region — each loop or region carrying an unchanged K03 `SolvePlan`; R0 entire |

`solve-policy.schema.json` gains the required `recycle` object (ADR 0009 D2) and
`solve-event.schema.json` the outcomes `RECYCLE_STAGNATION` and `CAPABILITY_UNAVAILABLE` (D3);
`failure-bundle.schema.json`'s `suggested_actions[].action` gains `provide_derivatives`, the
proposal of a `CAPABILITY_UNAVAILABLE` solve (D6).

Changed by **T03** under ADR 0005 (the phase-attempt contract; fixtures regenerated from live code,
R-015): `solve-policy` gains the required literal `phase_contract` (D1); `solve-event`'s outcome enum
gains `CHECKPOINT_INCOMPATIBLE` (D6); `attempt-context` gains the required, nullable
`jacobian_pattern` (D5); `solution-certificate` gains the required, nullable `root_fingerprint` and a
defined `branch_provenance` item (D7).

Changed by **T04** under ADR 0010 (Proposed; fixtures regenerated from live code, R-015), in two
passes. The homotopy track: `solve-policy` gains the required `globalization` object (D1);
`solve-event` gains the kind `homotopy_step`, the outcomes `HOMOTOPY_STALLED`, `PTC_STALLED` and
`PTC_MAPPING_INVALID`, and the nullable fields `lambda_value`, `delta_lambda`,
`corrector_outcome`, `corrector_iterations`, `level_constants_sha256`, `homotopy_level`,
`eo_recovery` and `eo_recovery_unsupported` (D7.2); `attempt-context` the required `core` and
nullable `continuation` (D7.3); `checkpoint` the required, nullable `continuation_lambda`, a value
other than `1` requiring `partial`/`unverified` (D7.4); `solution-certificate`'s
`branch_provenance` item the cores `ptc` and `homotopy`, the source `eo_recovery_start` and the
required, nullable `continuation` (D7.5). The PTC track: `solve-event` gains the nullable
`pseudo_step`, `pseudo_step_next` and `ser_ratio` (R1/R2) and the rejection reasons
`bound_blocked` and `linear_solve_failed` (D7.2). K04 on the bound declaration (D9) adds
`transformations.declaration` to every certificate (empty on a nominal one); `transformations` is
an open object, so no schema changes. T04's own fixtures (`t04_*.json` in the schema directories)
are emitted by `scripts/t04_schema_fixtures.py` from real plan runs and compared in
`tests/test_t04_schemas.py`.

Changed by **T05b** under ADR 0012 (Proposed; C1, approved by Frank on 2026-09-25):
`solve-policy`'s `phase_contract` widens from the single literal `T03-phase-contract-v1` to the
enum of it and `T05b-phase-contract-v2` (D4 (d)). The default and every registered policy stay v1;
the fixtures regenerate identically (R-015).

Changed by **T06** under ADR 0015 (Proposed; the two widenings approved by Frank on 2026-09-26,
`docs/T06_DECISIONS.md`): `solve-policy`'s `globalization.eo_recovery` widens from `homotopy`,
`none` to add `homotopy_or_sequential_restart` (D1, recovery edge 3's second action, the
sequential restart of a revision-built region); `solve-event`'s `eo_recovery_unsupported` adds
`no_restart_initializer`, `restart_start_unchanged` and `restart_initializer_failed` (D4). No field
is added or removed and no default changes; every registered policy keeps `homotopy` or `none`,
and the fixtures regenerate identically (R-015).

Changed by **T06** under ADR 0018 (Proposed; the widening approved by Frank on 2026-09-26,
`docs/T06_DECISIONS.md`): `solve-policy`'s `globalization.eo_core` widens from `newton`, `ptc` to
add `newton_refined` (D1, the Newton core with one terminal refinement at a converged exit whose
chord correction exceeds the kind tolerance). No field is added or removed and no default
changes; every registered policy keeps `newton` or `ptc`, and the fixtures regenerate identically
(R-015).

Added by **T07** under ADR 0019 (the application contract v1; approved by Frank) — the K06/T07 row
of the delivery table delivered, plus four schemas that row does not list. The field sets and enums
are those of design note `docs/design/T07-jobs-and-bindings.md` §5; `Job` and `JobEvent` also carry
ADR 0008 Amendment 1 C6 (J1–J3 and J5 binding, J4 and J6 recommended):

| File | Describes |
| --- | --- |
| `change-set.schema.json` | `ChangeSet`: the HTTP/MCP body of `commit_change` — edits (`set`, `remove`, `append`) applied whole or not at all, against an expected revision, under an idempotency key |
| `transaction-result.schema.json` | `TransactionResult`: `commit_change`'s and `preview_change`'s result — status, validation, semantic diff, invalidations, conflict or error |
| `job.schema.json` | `Job`, with the `$defs` `job_request` (the closed `operation` discriminator, one `oneOf` branch per value — J3), `artifact_ref` (J1), `budgets`, `job_ending` and `job_result` (`get_job_result`'s answer, ruling round 1 R4), and the shared `id`, `artifact_id`, `sha256` and `timestamp` patterns (§5.1) the other T07 schemas reference |
| `job-event.schema.json` | `JobEvent`: one lifecycle event; `ends_job` states whether it ends the job (J5), and an `output` event carries exactly one reference (J2) |
| `run-result.schema.json` | `RunResult`: the frozen result name of `solve`, its field set fixed at this first use |
| `api-error.schema.json` | `ApiError`: the one error shape of every binding, with the closed code enum |
| `capability-reference.schema.json` | `CapabilityReference`: what a credential grants — rights, token hash, limits |
| `project-policy.schema.json` | `ProjectPolicy`: `project-policy.json`, the capability grants and executor settings of a project |

Added by **T07 ruling round 2** (V17 F1) under ADR 0020 D4 as amended — a design-lane addition to
the schema list, as ADR 0009 D1 added `execution-plan` — with its round-trip fixture emitted by a
real `revision_eo` solve of SYN-001-nominal (`scripts/t07_schema_fixtures.py`):

| File | Describes |
| --- | --- |
| `solution-state.schema.json` | `solution-state.json`: the state a revision bundle's certificate judged — `variable_ids` in the order `state_sha256` is defined over and `variables` in unprefixed SI — written iff the certificate is; the cross-checks JSON Schema cannot state are `run/solution_state.py::inconsistencies`, which `verify_bundle` runs; `job.schema.json`'s `artifact_ref.kind` gains `solution_state` |

Every member without a stated default is required, the nullable ones included; a member the note
gives a default is optional, and `process_runtime.application.types` writes it at that default, so
the typed documents' `as_document()` is the normalized form `request_sha256` hashes (§5.3). The
artifact- and event-kind enums are **closed for producers** — these schemas — and **open for
consumers**: `from_document(..., lenient=True)` keeps an unknown kind opaque rather than refusing the
document (J5). Rules a JSON Schema cannot state are in the code and tested with it: the lifecycle
(`application/jobs/model.py::check_lifecycle`, §6.3), sorted `rights`, unique capability ids and
tokens, and a `verification_status` only beside a certificate output.

Under R-015 round-trip fixtures are emitted by the W-step that first produces a real instance
(design note §5). `job` and `job-event` fixtures are emitted by three real jobs (W4a,
`scripts/t07_schema_fixtures.py`): a solve cancelled while queued (0 outputs), a `reproduce`
without rerun (1) and a converged solve (3, of three kinds), and one event of each producer kind;
`tests/test_t07_adr0008_jobs.py` holds them to ADR 0008 A1 (a). The other T07 schemas' fixtures are
not yet present; `tests/test_t07_types.py` round-trips constructed documents, which test the types
and are not fixtures.
