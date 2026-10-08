# Frozen interfaces and schema list (end of P01)

**Authority:** plan v1.1 §1.3 ("Interface freeze"), §2.1, §2.2. **Frozen by:** Fable 5.1 at the close of P01, 2026-09-06.  
**Change rule:** after this freeze, any widening, narrowing, renaming, or re-typing of the signatures below, and any addition to or removal from the schema list, requires a Fable-authored ADR under `docs/adr/` stating reason, affected requirements, migration impact, and acceptance evidence. Opus lanes build against these and may not change them unilaterally.

## 1. Protocol signatures (plan §2.1, verbatim)

```python
class CompiledProblem(Protocol):
    metadata: CompiledProblemMetadata
    def residual(self, x, context) -> EvaluationResult: ...
    def jacobian(self, x, context) -> JacobianResult: ...
    def reconstruct(self, x, context) -> ProcessState: ...

class PropertyProvider(Protocol):
    def describe(self) -> PropertyCapabilities: ...
    def evaluate_phase(self, request, context) -> PropertyResult: ...
    def flash(self, request, context) -> FlashResult: ...

class Application(Protocol):
    def validate(self, revision_id, task) -> ValidationReport: ...
    def commit_change(self, change, expected_revision, idempotency_key): ...
    def solve(self, revision_id, policy_id) -> RunResult: ...
    def reproduce(self, bundle_path, policy) -> ReplayReport: ...
```

Binding semantics attached to the signatures (plan §2.1, blueprint §3.2, §6.4):

- `x` is a dense NumPy vector of the ordered free variables; sparse Jacobians use a documented CSC ordering with explicit row and column IDs and source maps.
- `EvaluationResult` carries status, active-set (phase) signature, state/model hash, accuracy information, and evaluation counters. `JacobianResult` is valid only for the same state, model version, phase regime, and evaluation policy as its residual; `residual` and `jacobian` describe the same function at the same state. `state_sha256` covers exactly the dense vector `x` as passed, in `variable_ids` order, after signed-zero normalization, and nothing else; the pairing identity is equality of `model_version`, `constants_sha256`, `state_sha256` and `phase_signature` under the same context (ADR 0008 D2). Encoding of the hash is ADR 0002's.
- `EvaluationContext` pins model/data versions, phase signature, accuracy policy, and run-local workspace; the outer active-set controller constructs a new context after a phase restart. Time is not a coordinate of this boundary (ADR 0008 D1): no field of `EvaluationContext` and no argument of `residual`, `jacobian` or `reconstruct` carries physical time, pseudo-time, a time step or a state history. Parameter and specification values — including the current value of a time-varying boundary specification — are pinned inputs evaluated by the orchestrator before the call and identified by the pair (`model_version`, `constants_sha256`). `workspace` carries run-local work buffers only; the evaluated function never depends on its contents.
- Metadata is typed and immutable and serializable; executable objects are runtime-local. There is no mutable global property provider.
- Optional JVP/VJP/Hessian capabilities are negotiated through `CompiledProblemMetadata`/`PropertyCapabilities`; a missing exact Hessian is reported as absent, never replaced with zeros.
- Result-type names (`CompiledProblemMetadata`, `EvaluationResult`, `JacobianResult`, `ProcessState`, `PropertyCapabilities`, `PropertyResult`, `FlashResult`, `ValidationReport`, `RunResult`, `ReplayReport`) are frozen as names; their field sets are fixed by the schema packages below when each schema is first used (plan §2.2) and are then covered by this freeze.

**ADR 0019 Amendment 3 (M06, A3.3; approved by Frank on 2026-10-08).** ADR 0019 D1's `Inspection` protocol gains a ninth method, `list_audit(*, principal_id=None, operation=None, order="ascending", cursor=None, limit=50) -> Page[AuditRecord]`, carried by Python, the CLI and HTTP (`GET /v1/audit`; no MCP tool), and `AuditRecord` joins the frozen result-type names. D4 is amended: `authorize` reads `target_principal` for `cancel_job` and `list_audit`, and another principal's rows, or all principals', need `policy` as well as `read`.

The Python `typing.Protocol` objects are introduced in code by the package that first needs each one (P02 for `CompiledProblem` metadata and `EvaluationResult`, K02 for `PropertyProvider`, K06 for `Application`) and must match this document verbatim.

## 2. Schema delivery list (plan §2.2, frozen)

| Package | Schemas |
| --- | --- |
| P01 | ProcessRevision, Quantity, ComponentRecord, ModelManifest, Specification, ValidationReport |
| P02/K01 | CompiledProblem metadata, EvaluationResult, Jacobian metadata, PropertyCapabilities |
| K03 | SolvePolicy, SolvePlan, SolveEvent, AttemptContext, Checkpoint metadata — **delivered 2026-09-21** as `schemas/solve-policy`, `solve-plan`, `solve-event`, `attempt-context`, `checkpoint`, with fixtures generated from a real SYN-001 solve |
| K04/K05 | SolutionCertificate, FailureBundle, RunManifest, replay artifact manifest |
| K06/T07 | ChangeSet, Job, job events, authorization capability references (Job and job events: ADR 0008 Amendment 1 J1–J3 and J5 binding from its acceptance, J4 and J6 recommended) |
| M01–M04 | ExperimentRequest/Result, ModelEvidence, Study, SurrogateManifest, OptimizationReport |

Schemas are JSON Schema (draft 2020-12) under `schemas/`, each with round-trip fixtures under `tests/fixtures/schemas/`. A schema changes only with a real migration and migration report (blueprint §4.4). Canonical JSON encoding rules are ADR 0002 (P01 records defaults; closes when canonicalization is implemented). **K03's five, delivered.** Their field sets are `docs/derivations/K03-solver-spec.md` §12 and
their round-trip fixtures are *emitted by a real solve* rather than written by hand, which is the
rule P01 used for the `ProcessRevision` fixtures: a hand-made document tests the author's reading
of the schema, an emitted one tests the code. Four rules a JSON Schema cannot express are checked
by `tests/test_k03_schemas.py`: a plan's inner block must be square and its tear rows must match
its tear variables (`UNSUPPORTED_RANK_STRUCTURE` otherwise); a trace's `sequence` must be dense
and strictly increasing and must open on `plan_built` and close on `solve_closed`; no event may
serialize a non-finite number, so a quantity that does not exist is `null` and never `0.0`; and
an `AttemptContext` must not serialize a `workspace`, which ADR 0008 D1.4 makes inert.

Three of the five carry single-valued literals on purpose — `merit`, `redundant_row_policy`,
`cycle_rule`, and the two-valued `derivative_path`. A later second policy is then a *new value* a
reader can see rather than a silent change of meaning, and K04 can refuse a certificate issued on
the finite-difference derivative path because the path is recorded.

`ModelManifest` was migrated by ADR 0008 (a required per-equation `accumulation` declaration, D3); the migration report is ADR 0008 “Consequences” C3–C5 and the only instances, the six declared SYN-001 manifests, were migrated in the same change.

**T02, ADR 0009 (Proposed; accepted when T02's manifest is `tested`).** Additive: `schemas/execution-plan.schema.json` is new (D1); `solve-policy` gains the required `recycle` object (D2); `solve-event` gains the outcomes `RECYCLE_STAGNATION` and `CAPABILITY_UNAVAILABLE` (D3); `failure-bundle`'s action enum gains `provide_derivatives` (D6). `SolvePlan` is unchanged (D5). A solve refused at plan construction (`CAPABILITY_UNAVAILABLE`) leaves a trace of one `solve_closed` event and no `plan_built`, K03's precedent for a solve that ends before its plan exists. The event-kind and `AttemptContext`/`Checkpoint` additions (D3, D4) land with T02's increment E.

**T03, ADR 0005 (Proposed; accepted when T03's manifest is `tested`).** `solve-policy` gains the required single-valued `phase_contract = "T03-phase-contract-v1"` (D1), so a replay under a policy without it is refused; `solve-event`'s outcome enum gains `CHECKPOINT_INCOMPATIBLE` (D6); `attempt-context` gains the required, nullable `jacobian_pattern` (D5); `solution-certificate` gains the required, nullable `root_fingerprint` and a defined `branch_provenance` item (D7). The binding semantics "the outer active-set controller constructs a new context after a phase restart" (§1) is now what both controllers do. Message grammars change no schema (T03 §4.10).

**T04, ADR 0010 (Proposed; accepted when T04's manifest is `tested`).** `solve-policy` gains the required `globalization` object (D1), so a replay under a policy without it is refused; `solve-event` gains the kind `homotopy_step`, the outcomes `HOMOTOPY_STALLED`, `PTC_STALLED` and `PTC_MAPPING_INVALID`, the rejection reasons `bound_blocked` and `linear_solve_failed`, and nullable fields for the homotopy (`lambda_value`, `delta_lambda`, `corrector_outcome`, `corrector_iterations`, `level_constants_sha256`, `homotopy_level`), edge 3 (`eo_recovery`, `eo_recovery_unsupported`) and PTC (`pseudo_step`, `pseudo_step_next`, `ser_ratio`) (D7.2); `attempt-context` gains the required `core` and nullable `continuation` (D7.3); `checkpoint` the required, nullable `continuation_lambda`, a value other than `1` requiring `partial`/`unverified` (D7.4); `solution-certificate`'s `branch_provenance` item gains the cores `ptc`, `homotopy`, the source `eo_recovery_start` and the required, nullable `continuation` (D7.5). K04's input contract is extended by D9: a certificate is issued on the declaration the solve solved, behind an identity guard, and `transformations` gains `declaration` (open object; no schema change). `failure-bundle` is unchanged (D7.6).

**T05b, ADR 0012 (Proposed; the widening approved by Frank on 2026-09-25, `docs/T05_DECISIONS.md`).** `solve-policy`'s `phase_contract` widens from `const "T03-phase-contract-v1"` to `enum ["T03-phase-contract-v1", "T05b-phase-contract-v2"]` (D4 (d), C1); `SolvePolicy.phase_contract` defaults to v1, which every registered policy keeps; fixtures regenerate identically (R-015).

**T06, ADR 0015 (Proposed; the widening approved by Frank on 2026-09-26, `docs/T06_DECISIONS.md`).** Two additive enum widenings: `solve-policy`'s `globalization.eo_recovery` gains `homotopy_or_sequential_restart` (D1), and `solve-event`'s `eo_recovery_unsupported` gains `no_restart_initializer`, `restart_start_unchanged` and `restart_initializer_failed` (D4); the matching `Literal`s (`GlobalizationPolicy.eo_recovery`, `trace.EoRecoveryUnsupported`) widen with them. `GlobalizationPolicy.eo_recovery` defaults to `homotopy`, which every registered policy keeps or pins to `none`; fixtures regenerate identically (R-015).

**T06, ADR 0018 (Proposed; the widening approved by Frank on 2026-09-26, `docs/T06_DECISIONS.md`).** One additive enum widening: `solve-policy`'s `globalization.eo_core` gains `newton_refined` (D1), and the matching `Literal` (`GlobalizationPolicy.eo_core`) widens with it. `GlobalizationPolicy.eo_core` defaults to `newton`, which every registered policy keeps or pins to `ptc`; fixtures regenerate identically (R-015).

**T07, ADR 0020 D4 as amended by design note ruling round 2 (V17 F1; a design-lane ADR, as ADR 0009 D1 added `execution-plan`; no approval by Frank needed).** One schema added: `schemas/solution-state.schema.json`, the `solution-state.json` member of a revision bundle — `{schema_version: "solution-state-v1", state_sha256, variable_ids, variables}`, the state the certificate judged, written iff `solution-certificate.json` is, with no run id and no verdict copy. `job.schema.json`'s `artifact_ref.kind` gains `solution_state`, additively. Three rules a JSON Schema cannot express — `variables` has exactly the ids of `variable_ids`, `state_sha256` is `canonical.state_sha256` of the values in that order, and it equals the certificate's `target_state_sha256` — are `run/solution_state.py::inconsistencies`, which `verify_bundle` runs; R0 takes `variable_ids` only. SYN-001 tear-path bundles (`run_session`, K05) do not gain the file, so no identity key moves. Round-trip fixture emitted by a real `revision_eo` solve (`scripts/t07_schema_fixtures.py`).

**T07, ADR 0019 Amendment 1 (design note ruling round 4, W5a-Q2; a design-lane ADR, precedent ruling round 2 F1.2; Frank informed, his approval not a precondition).** One schema added: `schemas/application-results.schema.json`, the JobControl and Inspection response shapes that had no published schema — one `$def` each, named in snake_case after the Python result type, a page `<item>_page`: `submit_result`, `job_page`, `job_event_page`, `job_wait`, `project_summary`, `model_registry_view`, `revision_summary`, `revision_page`, `projection`, `semantic_diff`. Their members are those `operations.py` stated at `9b541df`, moved unchanged; `OPERATIONS` `$ref`s them, and `job`, `job-event`, `job_result`, `run-result`, `transaction-result`, `validation-report` and `replay-report` stay where they are. The move is inert: each of the 20 operations' fully `$ref`-resolved response schema is canonically equal to its snapshot at `9b541df` (gate R4-G3). Request shapes stay the method parameters (ADR 0019 D1). Fixtures: one valid per `$def` emitted from real `dispatch` responses, one invalid per `$def` with a required member removed (`scripts/t07_schema_fixtures.py`).

**T07, ADR 0019 Amendment 2 (design note ruling round 6, B2 item 4; approved by Frank on 2026-09-27).** One additive member: in `application-results.schema.json#/$defs/model_registry_view`, every pin and every choice option gains the required `specifications`, the encodings the revision binder reads for that pin (`revision_binding.pin_encodings`: `{object_type, object_id, path, component, kind, si_unit, fixes}`, `object_id` a template `{instance}` or `{connection:<port>}`). No other `$def` moves: R4-G3's snapshot is re-taken for `list_models` only, and with the member removed it equals its `b13d556` snapshot (gate G-R6-6). Fixtures regenerated from a real response, with a second invalid fixture (a pin without `specifications`).

**T08, ADR 0025 (Proposed; a design-lane ADR under Frank's go-ahead of 2026-10-01, his Q4 answer of 2026-10-02, R-146/R-147).** Two additive widenings: `run-manifest`'s and `solution-certificate`'s `numerical_policy_id` widen from `const "K04-numerical-policy-v1"` to `enum ["K04-numerical-policy-v1", "T08-numerical-policy-v2"]` (D1.2), so every existing document still validates and a third id (`K04-numerical-policy-v3`, say) is refused (A15). A record is replayed and compared under the policy it names (`run.compare.differences(..., policy_id=...)`, no default); a record naming a policy this build does not know is inspected and not re-run. No served MCP schema reaches either document, so the served tool list is unchanged (A49's `171dd768…`).

**M06, ADR 0019 Amendment 3 (design note `docs/design/M06-web-shell.md` §4; approved by Frank on 2026-10-08).** Additive. A3.2: `application-results.schema.json#/$defs/semantic_diff` gains the required member `elements`, `[{member, id, change, paths}]` — the items of `instances`, `connections` and `specifications` that differ, paired by `id` (`transactions.element_diff`) — emitted by `diff_revisions` only; `added`, `removed` and `changed` are unchanged, and `transaction-result.schema.json` (whose `diff` is `commit_change`'s and `preview_change`'s, and every ledger replay's) is not changed. R4-G3's snapshot is re-taken for `diff_revisions` only; with the member removed it equals its `b13d556` snapshot (gate G5). Since `diff_revisions`' served MCP `outputSchema` carries `elements`, the served MCP tool list moves from `171dd768…` (R-133, named as the served list in the T08 paragraph above, which records 0.1) to `6c4375b4…` (R-192), and by that member alone: `tests/test_t08_w2_surface_digest.py` removes it and recovers `171dd768…`. A3.1 adds `rows`, `columns` and, when no route binds, `validation_structural_report` to `inspect_structure`'s document, which is served as a `projection` and changes no schema; `rows` and `columns` are null on either branch when no declaration was traced. A3.3: the same file gains the `$defs` `audit_record` (closed, all required: `seq, at, principal_id, capability_id, operation, outcome, code, request_sha256, effect, idempotency_key`) and `audit_page` (`{items, next_cursor}`), `list_audit`'s response; one valid fixture each from a real response and one invalid each (`scripts/t07_schema_fixtures.py`). The store schema stays `t07-store-v1`: `list_audit` is one read-only LEFT JOIN of `audit` with `ledger` on `(principal_id, operation, request_sha256)`, exact because a keyed request's hash covers its key (R2, tested).

**M03, ADR 0031 D7 and ADR 0032 D6 (Proposed; spec §10, Amendment 1).** Two schemas added for the M01–M04 row's Study and OptimizationReport: `schemas/study.schema.json` and `schemas/optimization-report.schema.json`, with fixtures emitted by real study runs; the schema list is registered in `schemas/registry.json` (R-213), which mirrors this section and replaces the literal counts in `tests/test_t08_w4_package_data.py`.

## 3. Semantic rules covered by the freeze

ADR 0001 D1–D5 (units, state definition `nTP-v1`, zero flow, signs, reference conventions) and ADR 0008 D1–D3 (no time at the evaluation boundary, `state_sha256` coverage, per-row accumulation declarations and the balance-row sign convention) are part of this freeze.

**T06, ADR 0016 (Proposed; the widening of ADR 0001 D1 approved by Frank on 2026-09-26, spec Q11, `docs/T06_DECISIONS.md`).** ADR 0001 D1.1 and D1.4 are widened for input documents only: a specification value or an instance parameter written in a unit of ADR 0016 D3's table is converted to its kind's SI unit at validation and binding by `unit-conversion-v2` (`SI = RN(a·D(v) + b)`), and the conversion is recorded in `input_mapping` and `DIM-01`. Internal storage stays unprefixed SI (D1.1 stands); no `Protocol`, schema keyword, quantity kind or tolerance changes.

ADR 0001 D5's reference convention `SYN-001-ref-v1` also carries ADR 0011 D2's declaration (accepted 2026-09-25): it is a formation datum — the pure liquids A, B, C have equal (zero) formation enthalpy and Gibbs energy at `(T_r, P_r)`. No number changes; a reacting unit is constructed only over a convention in ADR 0011 D2's registered set.

**M01, ADR 0026 (Proposed; accepted when M01's manifest is `tested` and the `reviewer` has passed the provider; C1, written by M01 spec Amendment 1).** ADR 0001 D5's reference conventions now include `PR-C1-ref-v1`, the convention of provider `pr-c1-v1`. It is a formation datum: each C1 component's ideal gas at 298.15 K has h = Δ_fH°(298.15 K), and elements in their reference states have zero (ADR 0026 D4, M01 spec §6). ADR 0011 D2's registered reaction-consistent set therefore has two members, `{"SYN-001-ref-v1", "PR-C1-ref-v1"}`, held in `thermo/conventions.py`. SYN-001's own constant is not edited, and a test holds it as a subset (M01.A24). ADR 0001 D5.2 is unchanged: streams of the two conventions never mix. No `Protocol`, schema, quantity kind or check category changes.
