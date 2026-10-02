# ADR 0020 — Job execution, cancellation, revision-built runs through the contract, and R-088 Q26–Q29

**Status:** **Accepted, 2026-09-28**, with T07's tested evidence (`evidence/T07/`); proposed 2026-09-27; a
design-lane decision, amended by ruling rounds 1–7. Register R-097…R-104.
D5 goes to Frank only if W0.4 measures a move of the `t06` key (design note §12.4, §17 F2).
*Ruling round 2:* it adds one schema, `solution-state`, to the frozen list, additively, under the
change rule's design-lane authority (precedent: ADR 0009 D1).
**Date:** 2026-09-27
**Author:** design lane (`architect`), T07. The build lane commits it as the design lane's text.
**Normative text:** `docs/design/T07-jobs-and-bindings.md` §8 (cancellation, budgets), §9
(execution, concurrency), §12 (revision runs) and §13 (R-088).
**Amends:**
- `orchestrator/trace.py`: `Trace.record` gains an inert context-local interrupt check.
- `run/identity.py`: `r0_projection` gains an `execution-plan.json` branch. It is inert for every
  existing bundle.
- `application/validation.py`: SCHEMA-01 widens to cover canonicality, and the structural stage
  gains the revision-binder fallback. *(Ruling round 1, R3:)* `provenance` and `revision_id`
  conform to the frozen `validation-report` schema.
- The entry points of both binders.
- *(Ruling round 1, R2:)* `benchmarks/t06/ensemble.py::_legacy_plan` moves verbatim into
  `application/revision_run.py`, and the benchmark delegates to it.
- *(Ruling round 2, F1:)* `run/identity.py::r0_projection` gains a `solution-state.json` branch
  (its `variable_ids` only), and `run/bundle.py::verify_bundle` cross-checks that file. Both are
  inert for every bundle without it. `docs/interfaces-frozen.md` §2 gains
  `schemas/solution-state.schema.json`, and `job.schema.json`'s `artifact_ref.kind` gains
  `solution_state`.

**Ruling round 1 (2026-09-27)** amends D4, D5 and the alternatives. W0.4 measured no move of any
identity key, so D5 does not go to Frank. Design note: "Ruling round 1".

**Ruling round 2 (2026-09-27)** amends D4 (the bundle's file list) on the V17 specification's
finding F1. No identity key moves. Design note: "Ruling round 2 (V17 F1: solution state)".

**Supersedes:** T06 A59's clause "`validate()` `DRAFT`" for STA-04 (T06 F5, deferred to T07 by
T06 Q2).
**Decides:** R-088 Q26, Q27, Q28 and Q29. It hands Q24 and Q25 to the `specifier`.
**Affected requirements:** D15, V17, D20 and blueprint §8.3 (R0), and §11.1 (budgets,
cancellation).

## Decision

- **D1 — Execution.**
  - Under a server, each job runs in a freshly spawned process that executes that job alone. The
    process is supervised by the application instance that accepted the job, and at most
    `executor.max_workers` jobs run at once (default 1).
  - In-process, the inline executor serializes jobs under a process-wide compute lock.
  - Instance ownership is an `flock`. Worker writes are fenced by `owner_instance` and status.
  - At open, recovery ends jobs whose owner is dead as `failed(owner_lost)`.
- **D2 — Q27.** The global-RNG hazard of `inverse_one_norm_estimate` is excluded by process
  isolation, not by a lock. No verification shares an interpreter with another thread that draws
  from `np.random`. `onenormest` and its seeding are unchanged.
  - The residual in-process case, a caller's own thread drawing from `np.random`, is documented,
    and its remedy is `executor="process"`.
  - The absence of other process-global mutable state is enforced by an allowlisted static scan
    and an A-then-B dynamic test.
  - The vendored-estimator alternative is recorded in design note §9.6 with its bit-identity
    argument, for the day in-process concurrency is required.
- **D3 — Cancellation and budgets.**
  - **Cooperative checks** run at every `Trace.record`, through the ContextVar `INTERRUPT_CHECK`
    (default `None`, which is inert), and at every stage boundary. They raise
    `JobInterrupted(BaseException)`.
  - **The forced stop** follows after `executor.grace_s`: a kill.
  - **An interrupted solve** emits only `partial_solve_trace`, with no certificate and no failure
    bundle.
  - **Wall time** is the job budget, and running out of it ends the job `timed_out`.
  - **`max_property_calls`** tightens the policy's registered property-call budget. Running out of
    it is the solver's own `BUDGET_EXHAUSTED` inside a `completed` job. The effective policy is
    stored and hashed.
  - **There is no iteration budget and no resume** in v0.1. J6 makes any re-run a new job.
- **D4 — Revision-built runs.**
  - A solve through the contract runs `revision_eo`: `bind_revision_flowsheet` → `plan_revision`
    → `execute_plan` → `verify_revision`.
  - It uses the application default policy `T06-revision-v2`, subject to W0 confirming
    `eo_core = newton_refined` and `eo_recovery = homotopy_or_sequential_restart`, and the
    registered `CheckPolicy()`, which may only be tightened.
  - Admission requires `READY_FOR_SIMULATION` and a successful revision binding.
  - The bundle is `run_session`-shaped plus `revision.json`, `solve-policy.json` and
    `check-policy.json`, and `RunManifest` is unchanged.
  - Rerun rebuilds from those files after the recorded hashes are verified.
  - **Amended (ruling round 1, R2).**
    - The route is chosen at admission by `select_route`, a pure function of the document. It is
      `revision_eo` when `bind_revision_flowsheet` binds. Otherwise it is `legacy_eo`
      (`bind_revision` → the T02 §7.5 plan → `execute_plan` → `verify_bound`) when
      `bind_revision` binds.
    - Admission requires a route.
    - The policy id `"default"` resolves to the route's registered policy: `T06-revision-v2` or
      `T04-W12`. A named registered policy runs on either route.
    - The route is recorded in `RunResult.solve_path` and in the bundle's `solve-path.json`, and
      rerun follows the recorded route.
    - An outcome-driven `revision_eo` → `legacy_eo` fallback is authorized in the shape the
      design note fixes. It is built only if W3a measures a case that needs it.
  - **Amended (ruling round 2, F1).** The revision bundle's files are `solve-events.json`,
    `execution-plan.json`, `solve-plan.json` (if built), `structural-report.json`,
    `revision.json`, `solve-policy.json`, `check-policy.json`, `solve-path.json`,
    `solution-certificate.json` **xor** `failure-bundle.json`, and **`solution-state.json`
    exactly when `solution-certificate.json` is present**.
    - `solution-state.json` (kind `solution_state`, schema `solution-state`) is the state the
      certificate judged: `{schema_version, state_sha256, variable_ids, variables}`, values in
      unprefixed SI, `state_sha256` equal to the certificate's `target_state_sha256`. It is a
      bundle member, not a job output.
    - R0 takes only its `variable_ids`. `verify_bundle` reports it `tampered` when it is
      inconsistent with itself or with the certificate.
    - `run_session`'s SYN-001 bundles do not gain it. No non-converged iterate is exposed.
- **D5 — F5.** When the legacy binder reports `unsupported`, `validate()`'s structural stage falls
  back to `bind_revision_flowsheet`, with the analysis inputs `plan_revision` uses. The legacy
  binder stays first, so SYN-001-topology reports are unchanged. Validate and plan must agree on
  the structural finding for every corpus revision.
  - **Amended (ruling round 1, R1).**
    - The fallback triggers on `unsupported` **or `incomplete`**, and never on `conflict`.
    - When both binders refuse, `conflict` outranks `incomplete`, which outranks `unsupported`. A
      tie goes to the revision binder.
    - Agreement is judged against `select_route`'s route:
      - READY ⇒ a plan with no structural refusal;
      - the findings are equal;
      - the counts are equal where one binder binds;
      - where both bind, the structural deficiencies (`equations − matched`,
        `free − matched`) are equal.
- **D6 — Q29.** `canonical.first_noncanonical(document)` gives an RFC 6901 pointer, and the
  following refuse typed:
  - `validate()`: SCHEMA-01 `FAIL`, status `INVALID`, the pointer named;
  - both binders: `Unbound("unsupported", "document_not_canonical(<pointer>)")`;
  - every request: `ApiError(document_not_canonical)`;
  - `commit_change`: `rejected`.

  SCHEMA-01's PASS text is unchanged.
- **D7 — Q26.** No T07 operation accepts a matrix or state from outside. A schema scan over every
  request reachable from `OPERATIONS` enforces this, and a forged-bundle rerun test proves an
  archived state is never trusted. The first operation that accepts one (a future `solve_resume`)
  must add a W14 path test.
- **D8 — Q28.** Event messages stay outside R0. Job events carry no solver messages, and the `t07`
  key carries no message text.

## Alternatives considered

- **Threads with a lock around the seeding.** Rejected: R-088's "watch for" — other threads can
  still observe the seeded state. There is also no GIL speed-up here and no hard cancel.
- **A reused worker pool.** Rejected: it saves about 0.3 s per job (measured cold import 0.29–0.33
  s) at the price of a cross-job state proof per job.
- **A vendored `onenormest` with a local `RandomState`.** Rejected for T07: it is a numerics-path
  change that is not needed.
- **Cancellation reported as a solver outcome.** Rejected: a `solve-event` schema change and a
  false diagnosis.
- **Delivering signals to the worker.** Rejected: the interrupt can land inside cleanup.
- **The tear path, or a tear fallback, for revision solves.** Rejected: its registered policy is
  `SYN-001-K03`, where the application defaults do not apply, and a cross-path fallback is an
  unspecified second ladder.
  - *Ruling round 1:* the tear path stays rejected. It cannot consume a GUESS specification, its
    bundle has no `revision.json`, and it reruns only for registered case ids.
  - `legacy_eo` is accepted instead, as a binding-driven route with its own registered policy.
- **Leaving legacy-only revisions unsolvable (`unsupported(solve_path_unavailable)`).** Rejected
  in ruling round 1: a READY revision with no solve path is a limitation with no reason.
- **GUESS-role specifications on the revision binder.** Deferred to the `specifier`: it is a new
  semantic for seeding the initializer.
- **Leaving F5.** Rejected: `validate()` would keep saying DRAFT for revisions the contract can
  solve, so admission would have to bypass validation.

## Consequences

- Every existing identity key is unchanged. The `Trace.record` hook and the `r0_projection` branch
  are inert, which the identity protocol at each W commit proves. The one exception is D5's move,
  if W0.4 measures one.
- T06 A59's validate clause and `tests/test_t06_w1b_order.py:141` are updated with a reference to
  D5.
- A new identity key `t07` covers float-free R0 records of the application path.

## Acceptance evidence

Design note gates G1, G5, G6, G7, G8, G9, G10, G12, G18 and G20. Register entries are added on
acceptance.
