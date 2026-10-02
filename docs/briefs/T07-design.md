# Brief — T07 design: job lifecycle, authorization, and the HTTP/MCP bindings over the application contract

**To:** `architect` (design lane). **From:** build lane, 2026-09-27. **Branch:** `wp/T07` (from `main`
at `78d3647`; T06 and ADR 0008 Amendment 1 merged).
**Deliverable:** a design note `docs/design/T07-jobs-and-bindings.md` — decisions, the `Application`
surface with signatures, the Job / job-event / capability schemas (field sets, enums), the concurrency
model, the dependency choice with licences, the V17 evaluation harness, an explicit **frozen-interface
impact section**, questions for `specifier` (if any), and a build-lane work order in phases, each with
its tests. No production code; do not commit (the build lane commits it). ADR 0019 is the next free
number — draft any ADR the note needs.

## 1. The question

What does T07 build so that one transport-independent application contract serves Python, CLI, HTTP and
MCP with the same validation, jobs (budgets, progress, cancellation, artifacts, idempotent duplicates)
and an authorization model that ordinary tools cannot escalate — and how is V17 (ten agent tasks,
≥ 80 % completion, zero unauthorized actions, zero false verification) measured honestly?

## 2. Why the architect

It fixes public interfaces every later client depends on (the `Application` protocol, Job, job events,
capability references — `docs/interfaces-frozen.md` §2 row K06/T07, frozen as a *list* since P01 but
without field sets), the execution model of long work (threads/processes vs. the verifier's global-RNG
seeding, R-088 Q27), and the trust boundary (blueprint §11.3). Getting cardinality, idempotency or the
capability model wrong is costly to migrate once HTTP/MCP clients exist (ADR 0008 A1 C6's argument).

## 3. Authority text (pasted)

**Plan §4.3 row T07 (binding):** "T03, K06: job lifecycle and small HTTP/MCP bindings over the local
application contract. | Ten agent tasks, ≥80% completion, zero unauthorized changes/false verification;
duplicate jobs, cancellation, injection and revision tests. | SYS | Build / Design". Gate **V17**:
"Local/HTTP/MCP, ten agent tasks, >=80% success, zero unauthorized actions/false verification".
Requirement **D15** minimum evidence: "In-process scientific use and common transport semantics" (K06
delivered the in-process half; the transport half is T07's).

**Blueprint §11.1:** "The canonical application contract is transport-independent. Local Python and CLI
call it in process; HTTP and MCP wrap the same operations and validation. A server is optional for local
modeling. Schema generation may assist binding consistency, but human-reviewed tool descriptions and
bounded projections are still required. Transactions accept an expected revision and idempotency key.
They return validation, semantic diff, and downstream invalidations. Draft edits can be grouped
atomically. Long work is a job with budgets, progress, cancellation, checkpoint/resume semantics, and
artifacts. Retrying an idempotent request cannot duplicate an expensive experiment."

**§11.2 minimum tool surface:** Inspect — summary, model registry, unit/stream/equation views, DOF
report, trace slices, failure evidence. Edit — begin, add/replace model, connect, set specification,
preview, validate, commit, rollback. Execute — compile, initialize, solve, cancel, resume compatible
checkpoint, verify. Compare — branch, semantic diff, compare runs, compare plans, replay. Study — later.
"Inspection supports bounded scope and pagination; complete exports remain available as files …
Every property/parameter value carries provenance; user assumptions are allowed if labeled."

**§11.3:** "Separate read, draft mutation, execution, model installation, policy administration, and
publication. Authorized agents may operate autonomously within project policy, including draft commits.
Policy changes are explicit transactions; ordinary solve tools cannot weaken verification. Tighter
requested tolerances and budgets within authorized limits do not require a new global approval
mechanism. Models and imported text are untrusted data. Inspect manifests without executing them. …
Names, citations, comments, and stdout cannot grant permissions. Envelope and bound untrusted text,
retain raw artifacts, and test prompt-injection attempts. … Installing executable plugins is a distinct
capability."

**§11.4:** "Publish internal tasks for constructing, diagnosing, repairing, replacing, optimizing,
reproducing, and resisting injected instructions. Report task completion, false verification,
unauthorized actions, semantic error rate, and cost separately. A no-false-verification gate is stricter
than a high task-success percentage."

**ADR 0008 Amendment 1, C6 (Accepted; binding on T07: J1, J2, J3, J5; recommended: J4, J6):**
- J1 — a `Job` carries outputs as an ordered array of typed artifact references (≥ kind from a closed
  enum, artifact id, content SHA-256), possibly empty, no maximum; no member holds exactly one solve
  result, run manifest, certificate or failure bundle.
- J2 — an output event appends exactly one J1 reference, in order, any number, interleaved, before the
  ending event; outputs are never read from the ending event's payload.
- J3 — a job request names its operation in a required member with a closed enum; the body is selected
  by it (one branch per value); a later operation is an added value and branch.
- J4 (rec.) — resume is operation-owned; the checkpoint is a J1-style typed reference whose kind the
  operation owns; the lifecycle does not assume the solver `Checkpoint` schema.
- J5 — artifact and event kinds closed for producers, open for consumers: every shipped consumer (CLI,
  Python/HTTP/MCP) ignores an unknown output or event kind without error; whether an event ends the job
  is stated in a member other than `kind` (T07 names it).
- J6 (rec.) — dense `sequence` from 0; operation-neutral progress `completed`/`total` (nullable);
  exactly one ending event, nothing after; resuming a cancelled/failed job is a new job.
- Acceptance in a T07 test module citing "ADR 0008 A1 J1–J3, J5": (a) Job fixtures with 0, 1, 3
  outputs (the last mixing kinds) validate; (b) a lifecycle checker accepts two output events and a
  progress event before the ending event, and the job's list then holds both references in order;
  (c) an operation outside the enum is rejected, each value has exactly one branch; (d) each shipped
  consumer ignores an unknown-kind output and an unknown-kind event without error and still recognizes
  an unknown-kind event that ends the job. RunManifest, SolutionCertificate and replay: no change.

## 4. Current state (verified by the build lane at `1b36bc9`)

**Frozen protocol** (`docs/interfaces-frozen.md` §1, "must match this document verbatim"; any widening,
narrowing, renaming or re-typing needs a design-lane ADR):

```python
class Application(Protocol):
    def validate(self, revision_id, task) -> ValidationReport: ...
    def commit_change(self, change, expected_revision, idempotency_key): ...
    def solve(self, revision_id, policy_id) -> RunResult: ...
    def reproduce(self, bundle_path, policy) -> ReplayReport: ...
```
`RunResult` and `ReplayReport` are frozen as names; field sets are fixed "when each schema is first
used". **Finding:** K06 never declared this protocol. `application/transactions.py:126` is a dataclass
`Application(store, _completed, _runs)` with `record_run(run_id, revision_id)` and
`commit(change_set: ChangeSet) -> TransactionResult` (status `committed`/`replayed`/`conflict`; the
idempotency map is in-memory, keyed by key alone; the change set carries `expected_revision`,
`new_revision_id`, `edits`, `task`, `idempotency_key`). No `validate`, `solve`, `reproduce` methods;
`validate(document, task)` is a free function in `application/validation.py:129`. `RevisionStore`
(`revisions.py:79`) is in-memory, no persistence. Its docstring: "The one local contract. A later HTTP
or MCP binding wraps this and adds nothing."

**Solve paths.** SYN-001: `run/session.py:29 run_session(flowsheet: Syn001Flowsheet, directory, *,
run_id, policy, check_policy, initial_recycle, reproducibility_class) -> RunManifest` — solve, verify,
write a replay bundle; refuses anything else with `TypeError("syn001_only(run_session)")` (T05 design
Q-G deferred revision-built sessions/bundles/CLI to T07). Revision-built flowsheets:
`application/revision_binding.py:484 bind_revision_flowsheet(document) -> RevisionBinding | Unbound`
plus `orchestrator/revision.py`; today they are solved and verified only through the T06 ensemble
harness (`benchmarks/t06/ensemble.py`). No K05 bundle for them (T06 Q6), and `validate()` cannot read
them (T06 F5).

**CLI** (`application/cli.py`): `validate`, `solve` (registered SYN-001 cases only), `inspect`
(bundle), `replay`, `gate`. Thin by design ("anything it computed for itself would be behaviour a
Python caller could not get").

**Schemas** (`schemas/`, JSON Schema 2020-12, round-trip fixtures emitted by real code, never hand-made
— the P01/K03 rule): 23 exist; none for Job, job events, ChangeSet or capabilities. Canonical JSON:
ADR 0002.

**Concurrency hazard.** `verify/regularity.py:76 inverse_one_norm_estimate` saves numpy's legacy
**global** RNG state, seeds it with `ONENORMEST_SEED = 20260925`, calls scipy `onenormest`, restores
(ADR 0014 D4, R-069). Not thread-safe (R-088 Q27: "Watch for … a lock that still lets other threads
observe the seeded global state"). No other known process-global mutable state is registered, but the
note should say how that was established.

**Dependencies.** `requirements.lock` pins none of mcp, fastapi, starlette, uvicorn, httpx, flask,
anyio. Licences are governed by ADR 0006 (distribution/data rights). The build lane adds and pins
whatever you choose.

## 5. Constraints and invariants

- SYN-001 and every registered T02–T06 result unchanged; identity keys `t02`…`t06`, structural
  `915c97e8…`, K05 document `9a7b4e6d…`. T07 adds identity only under a new key.
- R-016 (verifier independence); the certificate judges only the target declaration (R-035).
- No placeholder success paths: an unimplemented operation returns an explicit unsupported result.
- "Ordinary solve tools cannot weaken verification" — a request may tighten tolerances/budgets within
  authorized limits; it may never loosen a check policy.
- Schemas: 2020-12, fixtures emitted by real code, canonical JSON per ADR 0002.
- The gate (`scripts/check.sh`) must not need a network, an LLM or an external service; the V17 agent
  runs are evidence recorded with hashes (like T06's reference comparisons).
- Both CI architectures (x86-64, aarch64); ADR 0007 (roundoff floats are not cross-platform promises).

## 6. Already decided — do not reopen

- ADR 0008 A1 J1, J2, J3, J5 (binding), J4/J6 (recommended — decide otherwise only with a recorded reason).
- Frank: `eo_core = newton_refined` (ADR 0018) and the F4 sequential restart (ADR 0015) are the
  **application defaults** for solves.
- Frank's standing directives: "as little limitations as possible"; robustness first — a method that
  fails may hand over to another, recorded and deterministic, never a relaxed check.
- R-088's defaults stay in force until T07 decides each (table below).
- No re-planning of the blueprint; no survey of alternative technologies beyond the dependency choice.

## 7. Genuinely open — decide these

1. **The `Application` surface.** Reconcile K06's class with the frozen protocol; add job submission,
   status, event stream, cancellation and (if supported) resume; say for each whether it is inside the
   frozen four or a widening. **If anything widens, narrows or re-types the frozen protocol, say so
   prominently in the frozen-interface section and draft the ADR** — the build lane takes it to Frank
   before implementing it. Prefer a design that keeps the frozen four verbatim if that is honest.
2. **Job, job-event, capability-reference schemas**: field sets, enums (operations, artifact kinds,
   event kinds, the J5 ending member), the lifecycle state machine, budgets (iterations, wall time,
   evaluations) and what exhausting one produces.
3. **Duplicate jobs**: idempotency-key scope (per principal? per operation? what if the same key comes
   with a different body?), persistence across process restarts (the store is in-memory today).
4. **Cancellation** semantics (cooperative checkpoints in the solver loop? granularity?), and whether
   resume is supported in v0.1 (J4) or explicitly unsupported.
5. **Concurrency model** — threads, processes, or one worker — given Q27; how verification is made
   safe (process isolation, a scipy-independent estimator with a local generator, …). If the fix would
   change `onenormest` numerics, that is a design-lane numerics change needing bit-identity proof at
   every registered state — say which you choose and why.
6. **Authorization**: principals, capabilities (§11.3's six separations), how a capability reference is
   presented per transport, what the local in-process default is, how policy changes are explicit
   transactions, and how "names, citations, comments, and stdout cannot grant permissions" is enforced
   (envelope/bounding of untrusted text in every response an agent reads).
7. **HTTP and MCP bindings**: libraries (licence per ADR 0006, pin), which operations each exposes,
   error mapping, bounded projections and pagination, human-reviewed tool descriptions, and the
   mechanism that proves the transports add nothing (one conformance suite run against every binding).
8. **Revision-built flowsheets through the contract**: solve, verify, bundle (T06 Q6) and validate
   (T06 F5), with the newton_refined + F4 defaults.
9. **R-088**: for each of Q24–Q29 say decided-here (how), or handed to `specifier` (why), or left at
   its default with reason. Q24 (closure wording) and Q25 (alias shift) look like certificate policy →
   probably `specifier`; Q26, Q27, Q29 look like yours; Q28 depends on whether event messages enter R0.
10. **V17 evaluation harness**: how "an agent task" is run and scored so that completion, false
    verification, unauthorized actions, semantic error rate and cost are measured separately and
    reproducibly; what counts as an unauthorized action (an attempt refused? an effect?); the ten tasks'
    category coverage (§11.4's seven plus unsupported requests). **Constraint:** the agents must run
    within this project's existing means — Claude Code subagents / headless sessions the build lane
    can launch; no separately billed API key or paid service without Frank's approval (flag it if you
    think the honest protocol needs one). Say what the `specifier` must author (task texts, oracles,
    injection payloads, scoring rules) and write those questions as a list the build lane can brief.

| R-088 | Question | Default in force |
| --- | --- | --- |
| Q24 | closure failure at `x_final` (projection refused) inside the rows' T window: FAILED vs UNVERIFIED | FAILED |
| Q25 | alias shift `997·(j+1)` Pa by position → large flowsheets UNVERIFIED | unchanged |
| Q26 | W14 identity refusal cannot fire on the production path | defence in depth; T07 adds a test through every API path taking a matrix/state from outside |
| Q27 | W3 global-RNG seeding not thread-safe | no concurrent verification within one process |
| Q28 | ADR 0018 D5 message floats harmless only while event messages stay outside R0 | messages outside R0 |
| Q29 | non-canonical number (NaN, int > 2⁵³) in an unread field escapes as untyped `CanonicalizationError` | not fixed; recommended `validate()` INVALID naming the JSON pointer, bindings `Unbound("unsupported", "document_not_canonical(<pointer>)")` |

## 8. Already tried / known dead ends

None for T07 itself. Relevant lessons: worktree agents must be told their base commit; roundoff floats
must not be pinned across architectures (ADR 0007); fixtures emitted, not hand-written.

## 9. How it will be verified

The gate (green at 4249 on `main`); ADR 0008 A1's (a)–(d); plan acceptance: duplicate-job, cancellation,
injection and revision tests; one conformance suite over Python/CLI/HTTP/MCP; identity protocol (every
registered result and key unchanged); V17 agent runs recorded as evidence; `reviewer`; CI on both
architectures; `evidence/T07/<commit>/manifest.json`.

## 10. Out of scope

Study operations (sweep, sensitivity, optimize — M-packages); the web workbench (§12); external model
installation/isolation beyond an explicit "unsupported" (no plugin loader in v0.1 unless you argue
otherwise); T08 release evidence; publication.
