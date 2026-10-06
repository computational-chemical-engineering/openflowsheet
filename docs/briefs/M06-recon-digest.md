# M06 Web-Shell Diagnostic Browser UI — Reconnaissance Digest

*Recon-grade digest (read-only reconnaissance, 2026-10-06): locations and excerpts, no judgement. Verify any claim against the code before relying on it.*

**Date:** 2026-10-06  
**Purpose:** Architect design input for M06 (diagnostic web shell). M06 is a build-lane package (SYS) that builds on T07 (job execution and HTTP/MCP binding, merged 2026-09-28). The package builds a browser-based diagnostic UI using only the public application contract.

---

## 1. Application Contract (ADR 0019, ADR 0020)

### Entry Points (src/openflowsheet/application/)

**Protocols** — `contract.py:227–270` (signatures frozen by ADR 0019)

```
class Application(Protocol):
    def validate(revision_id: str, task: Task) -> ValidationReport
    def commit_change(change: Change, expected_revision: str|None, 
                      idempotency_key: str) -> TransactionResult
    def solve(revision_id: str, policy_id: str) -> RunResult
    def reproduce(bundle_path: str|PathLike, policy: ReplayPolicy) -> ReplayReport

class JobControl(Protocol):
    def submit_job(request: JobRequest) -> SubmitResult
    def get_job(job_id: str) -> Job
    def list_jobs(status: JobStatus|None=None, cursor: str|None=None, 
                  limit: int=50) -> Page[Job]
    def list_job_events(job_id: str, after_sequence: int=-1, 
                        limit: int=100) -> Page[JobEvent]
    def wait_job(job_id: str, after_sequence: int=-1, 
                 timeout_s: float=20) -> JobWait
    def cancel_job(job_id: str) -> Job
    def get_job_result(job_id: str) -> JobResult

class Inspection(Protocol):
    def get_project() -> ProjectSummary
    def list_models() -> ModelRegistryView
    def list_revisions(cursor: str|None=None, limit: int=50) -> Page[RevisionSummary]
    def get_revision(revision_id: str, pointer: str="", depth: int=4, 
                     cursor: str|None=None, limit: int=50) -> Projection
    def diff_revisions(from_revision: str, to_revision: str) -> SemanticDiff
    def inspect_structure(revision_id: str, pointer: str="", depth: int=4, 
                          cursor: str|None=None, limit: int=50) -> Projection
    def preview_change(change: Change, expected_revision: str|None) -> TransactionResult
    def get_artifact(artifact_id: str, pointer: str="", depth: int=4, 
                     cursor: str|None=None, limit: int=50) -> Projection
```

**Concrete implementation:** `local.py:260–270` — `LocalApplication` implements all three protocols. Created with `create()`, `open()`, or `in_memory()`. Exports `artifact_bytes(artifact_id: str) -> bytes` for raw download (not exposed over HTTP/MCP).

**Authorization:** `authz.py` — `authorize(capability, operation, target) -> bool` (pure). Six rights: `read`, `draft`, `execute`, `install`, `policy`, `publish`. Credential is a bearer token (HTTP) or token file (MCP); in-process uses built-in `LOCAL_OWNER` (unreachable from transport).

### Operations Table — `operations.py:373–410`

Single source for all four clients (Python, CLI, HTTP, MCP). Each row: name, method, required right, request/response schemas, HTTP verb/path, MCP tool name, transports, description file.

| Operation | Right | HTTP | Transports |
|---|---|---|---|
| validate | read | POST /v1/revisions/{revision_id}/validate | all |
| commit_change | draft | POST /v1/changes | all |
| solve | execute | — | python, cli |
| reproduce | execute | — | python, cli |
| submit_job | execute | POST /v1/jobs | all |
| get_job | read | GET /v1/jobs/{job_id} | all |
| list_jobs | read | GET /v1/jobs?status&cursor&limit | all |
| list_job_events | read | GET /v1/jobs/{job_id}/events?after_sequence&limit | all |
| wait_job | read | GET /v1/jobs/{job_id}/wait?after_sequence&timeout_s | all |
| cancel_job | execute | POST /v1/jobs/{job_id}/cancel | all |
| get_job_result | read | GET /v1/jobs/{job_id}/result | all |
| get_project | read | GET /v1/project | all |
| list_models | read | GET /v1/models | all |
| list_revisions | read | GET /v1/revisions?cursor&limit | all |
| get_revision | read | GET /v1/revisions/{revision_id}?pointer&depth&cursor&limit | all |
| diff_revisions | read | GET /v1/revisions/{a}/diff/{b} | all |
| inspect_structure | read | GET /v1/revisions/{revision_id}/structure?pointer&… | all |
| preview_change | read | POST /v1/changes/preview | all |
| get_artifact | read | GET /v1/artifacts/{artifact_id}?pointer&depth&cursor&limit | all |
| artifact_bytes | read | GET /v1/artifacts/{artifact_id}/raw | python, cli, http |

---

## 2. HTTP Binding

**Framework:** Starlette + uvicorn (stdlib for the application; optional `server` extra).

**Module:** `bindings/http.py` (40 lines introductory comment, full file ~500 lines)

**Route structure** — each `OPERATIONS` row with `http` transport becomes one Starlette route:
- Verb and path from the table
- Query/path parameters percent-decoded and validated
- JSON body at most 1 MiB; canonical form required (non-canonical → 422 before method)
- Bearer token (`Authorization: Bearer prt_…`) → `LocalApplication.authenticated()` view
- Authorization checked inside the method, never by the binding
- Response: 200 with domain result JSON, or API error status with error document

**Server defaults** (`http.py:73–75`):
- Host: `127.0.0.1` (loopback only)
- Port: 8765
- No CORS (browser preflight rejected like any unknown method)
- No TLS (loopback or explicit stderr warning if `allow_remote` given)

**CLI entry:** `openflowsheet serve` (from `cli.py` entry point `openflowsheet`)

**Error shape:** One `ApiError{code, message, detail, retryable}` with closed code enum (§5.8 of design note). Unimplemented capabilities return typed `unsupported`.

**Imports** (§11.6 linting): only `contract`, `types`, `operations`, `projection` of application; stdlib; starlette; uvicorn. Never imports `local` or `authz`.

---

## 3. MCP Binding

**Framework:** `mcp==1.30.0` (low-level server over stdio, not decorators; protocol 2025-06-18).

**Module:** `bindings/mcp.py`

**Tool coverage:** Every operation except `solve`, `reproduce`, and `artifact_bytes`. Each tool name matches the operation name (snake_case). Input and output schemas come from the same `OPERATIONS` table.

**Credential model:** Token file bound at server startup and re-authorized on every call (design note §10.2).

**Imports:** same as HTTP binding.

---

## 4. Record Shapes for UI Display

### Run and Job Results
- **`RunResult`** (`schemas/run-result.schema.json`): `run_id`, `revision_id`, `policy_id`, `solve_path`, `outcome` (typed enum: CONVERGED or failure reason), `elapsed_seconds`, `run_manifest`, `structural_report`, `solution_certificate` or `failure_bundle`, `execution_plan` (if present)
- **`Job`** (`schemas/job.schema.json`): `job_id`, `principal_id`, `operation`, `status` (queued|running|ended), `created_at`, `started_at`, `ended_at`, `progress{completed, total}`, `error`, `replayed`, `outputs[]{kind, artifact_id}`
- **`JobEvent`** (`schemas/job-event.schema.json`): `sequence`, `kind` (event type), `ends_job`, and kind-specific fields (e.g. `output` for an output event carries one `artifact_ref`)
- **`TransactionResult`** (`schemas/transaction-result.schema.json`): `status` (committed|conflict|rejected|previewed), `revision_id`, `expected_revision`, `invalidations[]`, `validation_result`, `diff`

### Revisions & Structure
- **`RevisionSummary`** (`application-results.schema.json#/$defs/revision_summary_page`): `revision_id`, `parent_revision`, `content_sha256`, `principal_id`, `created_at`, validation status, last run reference
- **`StructuralReport`** (no dedicated schema; part of `ValidationReport` or returned by `inspect_structure`): `equations`, `free_variables`, `matched`, `unmatched`, `blocks`, `graph_cycles`, `candidate_specifications[]`, `unit_degrees_of_freedom[]`, `structure_hash`, `certificates` (redundant row counts)
- **`Projection`** (recursive paging, `application-results.schema.json#/$defs/projection`): `document` (current fragment), `$ref` (JSON pointer origin), `overflow` (paging info)

### Certificates & Verification
- **`SolutionCertificate`** (`schemas/solution-certificate.schema.json`): `verification_status` (VERIFIED|RELAXED|UNVERIFIED|FAILED), `checks[]` with `{id, category, subject, value, tolerance, reference, near_threshold}`, `limitations[]`, `scaled_error_bound`, `state_sha256`, `branch_provenance[]` (recovery edges), `phase_branch`, `statements[]`
- **`RegularityEvidence`** (in certificate): `regularization_outcome` (NO_RANK_LOSS_DETECTED or other), `explicit_rank`, `implicit_rank`, `deficient_pivot_count`

### Trace & Failures
- **`SolveEvent`** (`schemas/solve-event.schema.json`): `kind` (plan_built|region_opened|attempt_opened|residual|jacobian|linear_solve|step_accepted|trial|attempt_closed|region_closed|solve_closed), `sequence`, `merit`, `counters`, `state_sha256`, `signature`, and kind-specific fields. Events carry cumulative counter state, so per-attempt counters = `attempt_closed` values minus `attempt_opened` values.
- **`FailureBundle`** (`schemas/failure-bundle.schema.json`): `outcome` (typed failure reason), `observations{counters, best_checkpoint{state_sha256, verification_scope}, inferred_causes[]}, `replay_identity` (currently broken for region results — D2), `region[]` (per-region diagnostics)

### Inspection & Artifacts
- **`ProjectSummary`** (`application-results.schema.json#/$defs/project_summary`): `project_id`, `head`, `revision_count`, `job_counts`, `solve_policies[]`, `default_policy_id`, `principal_id`, `capability_id`, `rights`, `limits`, `server{package_version, git_commit|null, store_schema}`
- **`ModelRegistryView`** (`application-results.schema.json#/$defs/model_registry_view`): each model carries `ModelSignature` with ports, parameters, and (**Amendment 2**) `specifications` (pin encodings from `MODEL_SIGNATURES` and binding path table)
- **`ValidationReport`** (`schemas/validation-report.schema.json`): ordered checks with PASS|FAIL|NOT_RUN, messages, structural counts, implicated objects, candidate rows

### Pagination & Error
- **`Page[T]`** (`application-results.schema.json#/$defs/<item>_page`): `items[]`, `cursor`, `count`, `remaining`
- **`ApiError`** (`schemas/api-error.schema.json`): `code` (closed enum), `message`, `detail`, `retryable`

---

## 5. Web-Shell Design Inputs (Current on Main)

### Design Brief
**File:** `docs/design/web-shell-design-brief.md` (sections 1–9)

**Product:** The workbench is the human window onto evidence: model inspection, DOF diagnostics, raw/scaled residuals, attempts, phase changes, branch comparisons. Equations and units reachable from every diagnostic. Education mode exposes transformations. Operations use the same contract as agents.

**Nine screens:**
1. Revision overview (flowsheet, status, last run)
2. Validation and DOF (ordered checks, structural counts, candidate specs)
3. Solve run (outcome, attempt tree, recovery path, counters, trace)
4. Certificate (verification status, checks by result, limitations, comparisons)
5. Streams and units (component flows, T, P, phase split, with equation links)
6. Failure bundle (taxonomy, observations, attempt tree, suggested actions)
7. Compare (two revisions or two runs, side-by-side)
8. Agent history (transactions: expected revision, key, diff, validation, authorization)
9. Education mode (same screens annotated with transformations)

**Design system:** IBM Plex Sans + Mono; tabular numerals; status always glyph + word + tone (never hue alone). Green only for VERIFIED/PASS/MATCH; CONVERGED is info-blue.

### Prototype
**File:** `docs/design/web-shell/Workbench.dc.html` + `support.js`

**Technology:** Claude Design runtime (`<x-dc>` templates with React; `support.js` is the `dc-runtime` auto-generated). Prototype is design reference, not product code.

**Screens implemented:** revision list, overview, validation/DOF, solve run with trace, certificate, streams and units, failure bundle, compare, education toggle, gap-note toggle.

**Not shipped with application:** the prototype lives in `docs/` only.

### Gap Triage
**File:** `docs/design/web-shell/gap-triage.md` (11 gaps; three defects D1–D3; five contract asks; five design questions)

#### **Contract Requests** (five asks for T07 amendment, to be backlog v0.2 if ADR 0019 amendment needed):
1. **Ask 1:** `inspect_structure` for invalid revision (no route) should return the validation analysis, not just `not_run_reason`.
2. **Ask 2:** Map from specification id to rows in `inspect_structure` envelope (for candidate-row linking).
3. **Ask 3:** `blocked_by` variable ids from `NewtonResult` into failure-bundle `observations` (for BOUND_BLOCKED diagnosis).
4. **Ask 4:** `list_audit(principal, operation, cursor, limit)` for agent history (audit rows + commit ledger).
5. **Ask 5:** Operation names and their required rights in `get_project` response (so UI does not duplicate the `OPERATIONS` table).

#### **Record Defects** (build-lane, three need design-lane review because they touch replay artifacts):
- **D1:** STR-03 message prints binder's internal `unit_id` (U-HEAT) not instance_id (heater); fix `validation.py:385`.
- **D2:** `replay_identity` in region/K03 failure bundles reads all `""` because `RegionResult` has no `plan` field; `policy_id`/`plan_id` in revision-path certificates also broken.
- **D3:** Failure bundle's `property_calls` reads 0; hypothesis: executor meter excluded from `RegionResult.counters`.

#### **Design Questions** (defaults set; all return NO or deferred):
- **Q1:** Add redundant/excess counts to frozen validation schema? → No; use `inspect_structure` (structured source).
- **Q2:** What is an "equation view"? → Row id, instance, incidence, scale from existing data; no symbolic text.
- **Q3:** Record per-event/per-attempt wall time as telemetry? → No; stays outside identity.
- **Q4:** Run comparison with registered reference root? → No; corpus page only.
- **Q5:** Which right reads audit (read or policy)? → policy for other principals, read for own rows.

---

## 6. Python Packaging

### pyproject.toml

**Base dependencies** (unchanged by T07):
- numpy 2.2.4, scipy 1.15.3, pyyaml 6.0.2, jsonschema 4.26.0, casadi 3.8.0

**Optional extra `server`** (T07 §11.1):
- mcp 1.30.0 (protocol 2025-06-18)
- starlette 1.7.0
- uvicorn 0.54.0

**Package data** (`tool.setuptools.package-data`):
- Schemas under `_data/schemas/*.schema.json`
- MCP tool descriptions: `openflowsheet.application.bindings` includes `descriptions/*.md` and `descriptions/REVIEW.json`
- Benchmarks: K04 and SYN-001 reference values YAML; T08 numerical policy YAML

**Package-data delivery:** Symbolic links in `_data/` to single-repo copies; wheel carries bytes, checkout reads originals.

**No existing JS/Node tooling** in the repo (confirmed).

---

## 7. CI

**File:** `.github/workflows/ci.yml`

**Jobs** (one line each):
1. **check** — both architectures (x86-64, aarch64). Install project + server extra, run checks, emit structural identity R0 document.
2. **default-install** — x86-64 only. Verify base + dev extras work without server extra; server modules absent.
3. **identity** — Compare structural identity across two architectures (G05).
4. **ensemble** — On-demand robustness runs (T06 closing records 2r and holdout1, 2×440 starts each architecture).
5. **dist** — Distribution tests (wheel, sdist, clean install, RC bundle set).

---

## 8. Existing ADRs & Blueprint Sections

### ADR 0019 — Application Contract v1 (Accepted 2026-09-28)
- Frozen `Application` verbatim (four methods, names unchanged)
- Two new sibling protocols: `JobControl` (7 methods), `Inspection` (8 methods)
- One concrete `LocalApplication` implements all three
- Adds schemas: `change-set`, `job`, `job-event`, `capability-reference`, `run-result`, `transaction-result`, `api-error`, `project-policy`
- Amendment 1: adds `application-results.schema.json` for `JobControl` and `Inspection` result shapes
- Amendment 2: `list_models` pins carry `specifications` (encodings)
- Affected: every later client including M06 workbench

### ADR 0020 — Job Execution & Revision Runs (Accepted 2026-09-28)
- Each job spawns its own process; in-process uses compute lock
- Cancellation is cooperative (hook in `Trace.record`) then forced after grace period
- Revision-built runs on `revision_eo` path; fallback to `legacy_eo` if only legacy binder binds
- Idempotency scope: `(principal, operation, key)` checked against request hash
- Amendment 1 (ruling round 1): `select_route` chooses path at admission
- Amendment 2 (ruling round 2): solution-state.json in bundle when certificate present
- `solution-state` schema added to frozen list

### Blueprint §12 — Web Workbench (v3.1)
- Prioritizes: model inspection, DOF diagnostics, raw/scaled residuals, attempts, phase changes, branch comparisons
- Minimal canvas follows reliable headless workflows
- Equations and units reachable from every diagnostic
- Education mode exposes transformations
- GUI operations use the same revision and application contracts as agents
- Adapters listed (SFILES 2.0 in v0.2 if real comparison needed; FMI/SSP/DEXPI/CAPE-OPEN later; JSON-LD deferred)

### Plan §4.4 — M06 and Gates W26, W27

**M06 package:** T08 (as dep): diagnostic web shell; bounded topology/SFILES work only if actual comparison needs it; external agent benchmark adaptation.
- Exit condition: All actions use public application contract; equation/trace/scenario views; benchmark coverage and artifact-access report.
- Lane: SYS, Build / Design.

**W26 — Diagnostic web shell through shared contract**

**W27 — External agent benchmark adaptation attempted; inaccessible assets disclosed**

---

## 9. Decision Register Entries for M06

- **R-152** (Frank, 2026-10-06): M01 pins K_NH₃ enthalpy term in ammonia synthesis reactor
- **R-153** (Frank, 2026-10-06): v0.2 order — M01 design first (critical path M01→M02→M04→M05→M07), M06 built alongside, M03 when critical path allows; pre-release 0.2.0a1 after M02

**Note:** R-153 rejects M06-first; M06 is build-led, off the critical path.

---

## 10. Not Found

- **No existing ADR on web UI or workbench design decisions:** blueprint §12 is descriptive; no design-lane ADR for M06 exists (that is the architect's deliverable).
- **No existing web-shell code in production:** prototype is design reference in `docs/` only.
- **No equation-view operation:** blueprint asks for "equations one step from every diagnostic" (§12, §5 Q2), but no operation serves a row. Design Q2 defaults to: row id, instance, incidence, scale from existing data; symbolic text deferred.
- **No audit read operation:** Asked for by gap-triage Ask 4; not implemented. Design-lane (architect) must decide which right grants access.
- **No node modules or JS build tooling:** Confirmed absent; prototype uses Claude Design's `dc-runtime` (not a project dependency).

---

## 11. Existing Pattern: How Comparable Features Are Done

### Nested Resource Paging (list_revisions, list_models, get_artifact with pointer & depth)
**Pattern:** `application-results.schema.json#/$defs/projection` — recursive paging with `document` (current fragment), `$ref` (pointer origin), `overflow` (paging info).
- Example call: `get_revision(revision_id="rev-000001", pointer="", depth=4, cursor=None, limit=50)`
- Returns: top-level keys + nested structure up to depth 4, next cursor if overflow.

### Validation & Structured Failure Reporting
**Pattern:** `ValidationReport` schema with ordered checks (PASS|FAIL|NOT_RUN), messages, and structured diagnostics.
- Example: STR-03 over-specification check lists candidates and implicated units; structural counts (equations, free_variables, matched, unmatched) guide UI.
- Accessed via: `validate()` method (returns ValidationReport) or `inspect_structure()` with fallback analysis.

### Job Progress & Cancellation
**Pattern:** Job status (queued|running|ended), event stream (sequence, kind, progress), cancellation via `cancel_job()`.
- Example: `wait_job(job_id="job-000001", after_sequence=-1, timeout_s=20)` polls every 0.1 s; returns events and ended flag.

### Schema Projection & Bounding
**Pattern:** `operation.project_response(result.as_document())` in `dispatch()` (§10.4).
- Untrusted strings bounded and sanitized; raw copies retained; no stdout or exception text inlined.
- Example: revision ids in `list_revisions` response are bounded by JSON schema and the pattern `^[A-Za-z0-9._:~-]{1,128}$`.

---

## 12. Guidance — Applicable Documents

- **Authority:** `docs/blueprint-v3.1.md` §12 (web workbench requirements), `docs/implementation-plan.md` M06 row + W26/W27 gates
- **Contract (frozen):** ADR 0019 (application/job control/inspection protocols and schemas), ADR 0020 (execution and revision runs)
- **Design inputs:** `docs/design/web-shell-design-brief.md` (product vision, nine screens, principles), `docs/design/web-shell/gap-triage.md` (data gaps, defects, asks, questions)
- **Prototype reference:** `docs/design/web-shell/Workbench.dc.html` (visual starting point; Claude Design artifact, not product code)
- **Decision register:** R-152, R-153 (v0.2 sequencing and M06 build order)
- **Session start:** Read `CLAUDE.md` (repository rules), then `docs/progress.md` (where we are), then decision register entries covering M06

