# ADR 0019 — The application contract v1: protocols, schemas, idempotency and authorization

**Status:** **Accepted, 2026-09-28**, with T07's tested evidence (`evidence/T07/`); approved by Frank
2026-09-27 (question round after the design note, `71c2e4e`); Amendments 1 and 2 approved by Frank
2026-09-27. Register R-091…R-096. It adds to the
frozen interface list (the precedents are ADR 0012, 0015 and 0018).
**Date:** 2026-09-27
**Author:** design lane (`architect`), T07. The build lane commits it as the design lane's text.
**Normative text:** `docs/design/T07-jobs-and-bindings.md`. §4 holds the surface, §5 the schemas,
§7 idempotency and §10 authorization.
**Amends (additively):** `docs/interfaces-frozen.md` §1, with two new protocols and one result
name, and §2, which delivers the K06/T07 row and adds four schemas.
**Reverses:** K06's replay-on-mismatch idempotency (`application/transactions.py:136`).
**Affected requirements:** D15 (common transport semantics), V17, blueprint §11.1–§11.3.
**Affected packages:** T07. Every later client (M-packages, the §12 workbench) builds on this.

## Context

Plan §2.1 froze `Application(validate, commit_change, solve, reproduce)` at P01. K06 never
declared it: it shipped `Application.commit(change_set)` with an in-memory store. T07 has to add
job control (submit, status, events, cancellation) and §11.2's inspection surface, and must bind
HTTP and MCP to the same contract. The K06/T07 row of the schema list names ChangeSet, Job, job
events and capability references without field sets. ADR 0008 Amendment 1 C6 J1–J6 constrains
Job and job events.

## Decision

- **D1 — The protocols.** `Application` keeps its four methods verbatim: names, parameter names,
  order, arity and return-type names. Type annotations follow the precedent of
  `CompiledProblem`/`PropertyProvider`. `commit_change` returns `TransactionResult`, and that name
  joins the frozen result-type names. Two sibling protocols are added: `JobControl` (`submit_job`,
  `get_job`, `list_jobs`, `list_job_events`, `wait_job`, `cancel_job`, `get_job_result`) and
  `Inspection` (`get_project`, `list_models`, `list_revisions`, `get_revision`, `diff_revisions`,
  `inspect_structure`, `preview_change`, `get_artifact`). The exact signatures are in design note
  §4.1. The frozen `solve` and `reproduce` are compositions: submit with a reserved `auto:` key,
  wait, return the result. They are exposed in-process only (Python, CLI).
- **D2 — The schemas.**
  - The K06/T07 row delivered: `change-set`, `job` (with `$defs` `job_request`, `artifact_ref`,
    `budgets` and `job_ending`), `job-event`, and `capability-reference`.
  - Added: `run-result`, `transaction-result`, `api-error` and `project-policy`.

  The field sets and enums are those of design note §5. `job_request` selects its body by the
  required, closed `operation` enum `["solve", "reproduce"]`, one `oneOf` branch per value (J3).
  Job outputs are an ordered, possibly empty array of `artifact_ref` with no maximum (J1). An
  `output` event carries exactly one reference (J2). Whether an event ends the job is the member
  `ends_job`, and consumers ignore unknown kinds (J5). Sequences are dense from 0, progress is
  `completed`/`total`, there is exactly one ending event, and a re-run is a new job (J6). Resume is
  absent (J4 is followed by absence). A later operation is an added enum value and branch.
- **D3 — Idempotency.** The scope is `(principal_id, operation, idempotency_key)`, compared by the
  normalized request's SHA-256. The same hash returns the original: a transaction `replayed`, the
  existing job with `replayed = true`. A different hash is refused `idempotency_key_reused`. The
  ledger is persistent in the project store. `auto:` is reserved.
- **D4 — Authorization.**
  - The rights are blueprint §11.3's six: `read`, `draft`, `execute`, `install`, `policy`,
    `publish`.
  - Authority comes only from the credential. HTTP presents a bearer token; an MCP stdio session
    is bound to a token file at start and re-authorized every call; in-process callers use the
    built-in `LOCAL_OWNER`, which no transport can produce.
  - `authorize(capability, operation, target_principal)` is pure and has no other input.
  - Policy is the schema-validated `project-policy.json`. It changes only through audited
    operator CLI commands, is hot-reloaded, and an invalid file is refused rather than defaulted.
  - No in-band `install`, `policy` or `publish` operation exists in v0.1.
- **D5 — Error shape.** One `ApiError{code, message, detail, retryable}` with the closed code enum
  and the HTTP mapping of design note §5.8. Domain results (a conflicted transaction, an INVALID
  report, a non-converged or cancelled job) are results, not errors.
- **D6 — Transports add nothing.**
  - One `OPERATIONS` table drives the Python dispatch, CLI `api`, HTTP (Starlette) and MCP
    (low-level SDK server, stdio).
  - A bijection test and an import-graph lint cover the table and the bindings, and one
    conformance suite runs over the four clients.
  - Every response string is bounded and sanitized by the contract's own projection function.

## Alternatives considered

- **Widening `Application` with the job and inspection methods.** Rejected: it changes a frozen
  signature where a sibling protocol suffices.
- **One generic `call(operation, request)` method.** Rejected: untyped, and it hides the contract.
- **Keeping job control and inspection informal** (module functions, with no protocol and no
  schemas). Rejected: HTTP and MCP clients would bind to shapes nobody froze, which is the
  migration cost ADR 0008 A1 C6 warns about.
- **Idempotency keyed on the key alone, or replay on mismatch.** Rejected: collisions across
  principals, and a changed request silently receives the old answer.
- **Authorization in the transports, or role fields in requests.** Rejected: two enforcement
  points drift, and request text would then grant authority (§11.3).
- **FastAPI, stdlib `http.server`, FastMCP decorators.** Rejected: respectively a second schema
  source, hand-written parsing with no MCP co-hosting, and schemas inferred from type hints rather
  than the reviewed JSON Schemas.

## Consequences

- `docs/interfaces-frozen.md` §1 gains the `JobControl` and `Inspection` signatures and the name
  `TransactionResult`. §2's K06/T07 row is marked delivered, with the four added schemas listed.
  No existing signature or schema changes.
- K06's `transactions.Application` becomes a façade over the shared transaction core, with the D3
  semantics. Any K06 test asserting replay-on-mismatch is updated with a reference to D3.
- An optional `server` extra (`mcp`, `starlette`, `uvicorn` and their closure) is added. The
  default install is unchanged. The licences are read from `dist-info` (ADR 0006).

## Acceptance evidence

Design note gates G2, G3, G4, G11, G13, G14 and G15. The ADR 0008 A1 module
`tests/test_t07_adr0008_jobs.py` covers (a)–(d). Schema fixtures are emitted by real jobs and
transactions. Register entries R-091 onward are added on acceptance.

## Amendment 1 (2026-09-27, T07 ruling round 4) — the JobControl and Inspection result shapes are frozen

**Authority:** design lane (`architect`). Design note `docs/design/T07-jobs-and-bindings.md`,
"Ruling round 4", W5a-Q2, with §11.3 and §11.4 as amended there. The amendment is additive.
**Approved by Frank, 2026-09-27** (in the session, after the build lane held the change on
`wp/T07-w5e`); Accepted with T07's tested evidence, like the ADR it amends.

- **D2 gains one schema,** `schemas/application-results.schema.json`.
  - Its `$defs` are the response shapes of the operations in `OPERATIONS` that have no published
    schema. Those are the `JobControl` and `Inspection` results other than `job`, `job-event`,
    `job_result`, `run-result` and `transaction-result`.
  - The members are those that `operations.py` states at `9b541df`, moved unchanged.
  - Each `$def` is named in snake_case after its Python result type, and a page is
    `<item>_page`.
- **Reason.** This ADR rejected keeping inspection informal because HTTP and MCP clients would
  bind to shapes nobody froze. D1 froze the signatures and the return-type names, but not the
  shapes. An MCP client binds to those shapes through `outputSchema`.
- **Unchanged.** D1, D3–D6; the eight schemas of D2; `solution-state` (ADR 0020, ruling round 2).
  Request shapes stay the method parameters of D1.
- **Migration.** None. No store or client has been released, and the move is proved inert: each
  operation's resolved response schema is canonically equal before and after (design note gate
  R4-G3).
- **Acceptance evidence.** Gates R4-G3 and R4-G4. The valid fixtures come from real responses,
  with one invalid fixture per `$def`. `docs/interfaces-frozen.md` §2 lists the file.
- **Approval.** The change rule of `docs/interfaces-frozen.md` asks for a design-lane ADR for an
  addition to the schema list, and this amendment is that ADR (precedent: T07 ruling round 2,
  F1.2). Frank approved D2's list explicitly, so he is informed. His approval is not a
  precondition.

## Amendment 2 (2026-09-27, T07 ruling round 6) — `list_models` pins list their specifications

**Authority:** design lane (`architect`). Design note `docs/design/T07-jobs-and-bindings.md`,
"Ruling round 6", B2 item 4, where this text was drafted. The amendment is additive.
**Approved by Frank, 2026-09-27** (question round after the `v17-c1` failure analysis,
`docs/T07_DECISIONS.md`). Accepted with T07's tested evidence, like the ADR it amends.

- **`application-results.schema.json#/$defs/model_registry_view`:** every pin and every choice
  option gains the required member `specifications`. It holds the encodings the revision binder
  reads for that pin, derived from `MODEL_SIGNATURES` and the target-path table
  (`revision_binding.pin_encodings`; design note ruling round 6, B2): an array (`minItems` 1) of
  `{object_type, object_id, path, component, kind, si_unit, fixes}`, all seven required and no
  other; `object_type` is `instance` or `connection`; `object_id` a template matching
  `^\{(instance|connection:[^}]+)\}$`; `component` is `{component}` or null; `kind` is
  `quantity.schema.json#/$defs/kind`; `si_unit` a string; `fixes` a non-empty string array.
- **Reason.** V17 `v17-c1` B2. Three of three agents did not find `heat_rate` / `duty.Q`.
- **Additive.** No store or client has been released, and there is no migration.
- **Acceptance evidence.** Gate G-R6-6. The response validates against the amended schema, and
  each pin's and option's `specifications` equals `pin_encodings`. R4-G3's snapshot is re-taken
  for `list_models` only; with the member removed it is the `b13d556` snapshot again, and every
  other operation stays canonically equal. One valid fixture from a real response and two
  invalid ones (`missing_models`, `pin_missing_specifications`), `scripts/t07_schema_fixtures.py`.
- **Rejected.** An example specification per pin: every member of a specification other than
  `kind`, `unit` and `target` is independent of the model, and an example would duplicate the
  encoding and need its own rule for tolerance and provenance.
