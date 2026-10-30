# Concepts

## Projects, revisions and changes

A **project** holds a history of **revisions**, the **jobs** run on them, their **artifacts** and
an audit log. A revision is an immutable `ProcessRevision` document: a component set (which also
selects the property basis), unit instances, material connections and specifications. You never
edit a revision in place: `commit_change` applies a change set — edits as JSON paths with
`set`, `append` or `remove` — to the head and stores the result as a new revision. It takes the
head you expect (a stale expectation is reported as a conflict) and an idempotency key (repeating a
request with the same key returns the first answer, never a second commit).
`preview_change` shows what a change would do without storing it, and `diff_revisions` compares
two revisions element by element.

## Validation

`validate(revision_id, task)` runs staged checks — schema, dimensions and units, components,
structure and degrees of freedom — and reports each with an id (`SCHEMA-01`, `DIM-01`,
`STR-01`, …), a result and the objects it implicates. The status is one of:

| Status | Meaning |
| --- | --- |
| `INVALID` | the document breaks a rule (schema, units, an unknown component) |
| `DRAFT` | well-formed but not solvable as it stands — for example a model the basis cannot bind, or open degrees of freedom |
| `READY_FOR_SIMULATION` | it can be solved |

`solve` refuses a revision that is not ready (`revision_not_ready`). Validation for the
`optimization` task is not offered through the application.

## Solving, and what a run returns

`solve(revision_id, policy_id)` runs one job to its end and returns a `RunResult`:

- `job_status` — whether the job ran to its end (`completed` says nothing about convergence);
- `outcome` — the solver's result: `CONVERGED`, or a typed failure such as
  `INITIALIZATION_FAILED`, `LINEAR_SOLVE_FAILED`, `HOMOTOPY_STALLED`;
- `verification_status` — the independent verifier's verdict on the converged state;
- `outputs` — the artifacts: the solution certificate, the run manifest and the replay bundle
  (with `solution-state.json`, every solved variable by id).

The policy `default` resolves to the route's registered policy (`T06-revision-v2` for
equation-oriented revision solves). `T08-ptc-v1` (pseudo-transient continuation, experimental) and
`T08-warm-v1` (compatible warm starts) are offered by explicit id. Longer work can run as jobs
(`submit_job`, `wait_job`, `list_job_events`, `cancel_job`).

## Certificates

After a solve converges, a verifier that does not trust the solver re-evaluates the flowsheet at
the converged state and issues a **solution certificate**:

| Verdict | Meaning |
| --- | --- |
| `VERIFIED` | every residual, material and energy balance, specification and phase check passed at its registered tolerance, and the regularity screen passed |
| `RELAXED` | as `VERIFIED`, but under a supplied check policy that loosens a tolerance or waives a check; every relaxation is listed, and a `RELAXED` run never counts as verified |
| `UNVERIFIED` | the checks could not establish the state — for example a rank-deficient Jacobian or a phase label not demonstrated |
| `FAILED` | a check failed, including a solver success the verifier detected as false |

Each check is listed with its id, result (`pass`, `fail`, `not_applicable`, `unsupported`),
value and reason; `limitations` and `statements` say what the verdict does not cover. A
`VERIFIED` run certifies residuals at registered tolerances, with a recorded solution-error
bound; it is not empirical validation of the property model and not an optimality claim. Energy
checks share the property provider with the solver, and say so.

## Refusals are results

What is not supported is refused with a type, never approximated:

- an operation refused before it runs is an **`ApiError`** with a bounded code —
  `invalid_request`, `document_not_canonical`, `unauthenticated`, `forbidden`, `not_found`,
  `idempotency_key_reused`, `not_ready`, `revision_not_ready`, `revision_unsupported`,
  `verification_weakening_refused`, `budget_exceeds_ceiling`, `limit_exceeded`, `unsupported`,
  `internal_error`, `model_replacement_incompatible` (Python raises it as `ApplicationError`);
- a binding refusal names the cause: `model_unsupported(thermal.pump)` with the bases the model
  does bind on, `components_unsupported`, `specification_conflict(...)`;
- a state outside a property model's domain is reported, not extrapolated: the run ends
  `INITIALIZATION_FAILED`, or the evaluation returns `invalid_trial_state` inside a solve.

## Replay

A replay bundle holds the revision, the policy, the plan, the trace, the solved state and the
certificate. `reproduce(bundle_path, policy)` (CLI: `openflowsheet replay`) checks its integrity
and, with `rerun`, solves again and compares under the numerical policy the record names. Bitwise
agreement is reported when it happens, never promised across platforms.

## Units

Inside the software every quantity is unprefixed SI (mol/s, K, Pa, W). Input documents may write a
specification or a parameter in one of the registered spellings, converted at validation:
`%` (dimensionless and mole fraction); `kW`, `MW` (heat rate and power); `g/s`, `kg/h`,
`kg/s`, `kmol/h`, `kmol/s`, `mmol/s`, `mol/h` (molar flow, mass-based ones through the
molar masses); `atm`, `bar`, `kPa`, `MPa`, `psi` (pressure); `degC`, `degF` (temperature
and temperature difference). Each spelling is exact and case-sensitive; gauge pressures are
refused.

## Signs

Work and heat are positive **into** the fluid: a pump's `W` and a boiler's `Q` are positive, a
turbine's `W` and a condenser's `Q` negative. A cooler is a heater with negative duty.

The normative definitions are the ADRs ([Design](../design.md)): ADR 0001 for units, state and
signs, ADR 0007 for certificates and reproducibility, ADR 0019 for the application contract.
