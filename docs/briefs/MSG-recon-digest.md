# MSG recon digest — OpenFlowsheet (read-only, 2026-11-05)

Repo: /home/frankp/Codes/OpenFlowsheet (package: src/openflowsheet/). Paths below are relative to src/openflowsheet/ unless absolute.

## 1. Typed failure / refusal codes

**There is no single error-code catalogue, no code registry and no failure-kind enum.** Codes live in four places:

a. **API error codes (closed enum, 15)** — `application/types.py:69-86` `ApiErrorCode = Literal[...]`:
   invalid_request, document_not_canonical, unauthenticated, forbidden, not_found, idempotency_key_reused,
   not_ready, revision_not_ready, revision_unsupported, verification_weakening_refused, budget_exceeds_ceiling,
   limit_exceeded, unsupported, internal_error, model_replacement_incompatible.
   HTTP status map `types.py:88-104` (`API_ERROR_HTTP_STATUS`); e.g. not_found→404, unsupported→501, internal_error→500, limit_exceeded→429.
   Mirrored in `schemas/api-error.schema.json:16-32` (enum).

b. **Reason-prefixed refusal strings (open text, convention: `code(detail)` as first token)** — no enum. Examples:
   - `initializer_failed(<INITIALIZER_ID>): <status>: <first_line>` — built at `orchestrator/tear.py:681`.
   - `phase_regime_mismatch(<stream>)` — `models/thermal/kernel.py:552` (f-string `f"phase_regime_mismatch({stream})"`); docstring list of typed codes at `models/thermal/kernel.py:19-23`:
     `phase_regime_mismatch`, `no_saturation`, `isentropic_state_two_phase`, `isentropic_state_single_phase` (R-839); set at `kernel.py:85`; `isentropic_state_two_phase` emitted ~`kernel.py:663`.
   - `model_unsupported(<id>)` — revision binder (docs-site/guide/limitations.md table).
   - `unsupported(<code>)` job-error form — `application/jobs/runner.py:51-53` (RunUnsupportedError code).
   - `failure_bundle_unmapped(<outcome>,<kind>,<held>)` — `application/revision_run.py:654` (RunUnsupportedError).
   - `internal_error(solution_state_mismatch)` — jobs/runner.py:53.
   - `legacy_route_not_admitted(<code>)` — `application/revision_run.py:245`.
   - `reactor_not_accepted(<stage>)` — R-198 (decision register), M02 code.
   - Helper `refusal_code(detail)` = text before first "(" — `application/binding.py:298-300`.
   - Binding refusal class `Unbound` — `application/binding.py:263`: `kind: Literal["conflict","inadmissible","incomplete","unsupported"]`, `detail`, `implicated`, `hint` (bounded to HINT_LIMIT=512, `binding.py` ~line 297).

c. **Outcome / taxonomy codes in failure bundles** — `verify/failure.py:28-75` `TAXONOMY` map (about 21 solver outcome codes, e.g. INITIALIZATION_FAILED, SCALE_UNAVAILABLE, SPECIFICATION_CONFLICT, UNSUPPORTED_RANK_STRUCTURE, ACTIVE_SET_CYCLING, BUDGET_EXHAUSTED, STAGNATION, LINE_SEARCH_FAILED, LINEAR_SOLVE_FAILED, INNER_SOLVE_INCONSISTENT, EVALUATION_ERROR, RECYCLE_STAGNATION, CAPABILITY_UNAVAILABLE, HOMOTOPY_STALLED, PTC_STALLED, COUPLING_NOT_CONVERGED, ...) mapped onto blueprint §8.2 classes. `class FailureBundle` at `verify/failure.py:126`.
   Schema: `schemas/failure-bundle.schema.json` (required: outcome, taxonomy, observations, inferred_causes, implicated_sources, attempt_tree, replay_identity, best_checkpoint, check_report, suggested_actions).

d. **Job endings** — `application/jobs/model.py:85-92` `ENDING_REASONS`: completed/operation_completed; failed/{operation_error, verifier_refused, worker_lost, owner_lost, store_error}; cancelled/{cancel_requested, server_shutdown, keyboard_interrupt}; timed_out/wall_time_exhausted. `REQUIRES_STARTED` at `jobs/model.py:96-101`. Event kinds `jobs/model.py:36-40` include `operation_error`, `store_error`.

e. **Validation check ids** (PASS/FAIL/WARN/NOT_RUN) — `application/validation.py:85` `Result`; `Check` dataclass `validation.py:92`; `ValidationReport` `validation.py:132`; check ids like SCHEMA-01, DIM-01, GRAPH-01, COMP-01, CAP-01, VER-02 (decision register). WARN produced at `validation.py:314`, `:798`.

## 2. Exception / error class hierarchy

| Class | Base | Where | Raised by / notes |
|---|---|---|---|
| `ApplicationError(Exception)` | Exception | `application/contract.py:45` | Non-domain contract outcome; carries `.error: ApiError`, `.code`. Constructed via `api_error(code, message, *, retryable, **detail)` at `contract.py:57`. |
| `LocalApplication._refuse(code, message, *, operation, **detail) -> NoReturn` | — | `application/local.py:416-425` | Audits, then `raise api_error(...)`. Used for every LocalApplication refusal. |
| `StoreError(RuntimeError)` | RuntimeError | `application/store.py:102` | "A project directory or database that cannot be created or opened as asked." |
| `IdempotencyKeyReusedError(StoreError)` | | `store.py:106` | message "this idempotency key was used with a different request …" |
| `ActiveJobLimitError(StoreError)` | | `store.py:117` | "the principal has N active jobs" |
| `DocumentSchemaError(ValueError)` | ValueError | `application/types.py:130` | schema validation of documents |
| `ServeRefusedError(Exception)` | | `application/serving.py:38` | serve refuses to start |
| `PolicyRefusedError(RuntimeError)` | | `application/authz.py:199` | invalid policy file |
| `PolicyAdministrationError(ValueError)` | | `authz.py:269` | |
| `RevisionError(RuntimeError)`, `RevisionConflictError` | | `application/revisions.py:29,33` | |
| `EditPathError(ValueError)` | | `application/transactions.py:81` | |
| `CouplingUnsupportedError(ValueError)` | | `application/coupled_run.py:107` | |
| `ReplayDivergenceError(RuntimeError)` | | `application/coupled_run.py:495` | |
| `SolutionStateMismatchError`, `RunUnsupportedError(RuntimeError)` | | `application/revision_run.py:159,169` | RunUnsupported `code` → job `unsupported(<code>)`. |
| `CanonicalizationError(ValueError)` | | `canonical.py:232` | |
| `DocumentError(ValueError)` | | `serialize.py:36` | |
| `SpecificationError(ValueError)` | | `models/__init__.py:88` | base of model-construction refusals |
| `InitializerFailedError(SpecificationError)` | | `models/syn001/flowsheet.py:80` | raised in tear path → `initializer_failed(...)` |
| `DomainError(ValueError)` | | `compile/spec.py:102` | |
| `UnitConversionError(ValueError)`, `UnknownKindError(ValueError)` | | `units/__init__.py:469,156` | unit conversion refusals |
| `CapabilityUnavailableError`, `UnsupportedRankStructureError` (ValueError) | | `orchestrator/execution.py:305,326` | |
| `SpecificationConflictError(ValueError)` | | `orchestrator/rank.py:48` | |
| `ScaleUnavailableError(ValueError)` | | `numerics/scaling.py:61` | |
| `LinearSolveFailedError(RuntimeError)`, `StructurallySingularError` | | `numerics/linear.py:50,102` | |
| `JacobianUnavailableError`, `MassUnavailableError` | RuntimeError | `numerics/newton.py:114`, `numerics/ptc.py:94` | |
| `BudgetExhaustedError(RuntimeError)` | | `orchestrator/budget.py:40` | |
| `BundleError(RuntimeError)` | | `run/bundle.py:31` | |
| `WebShellMissingError(RuntimeError)` | | `application/bindings/web.py:86` | |
| `StructureUnavailableError(ValueError)` | | `graph/trace.py:44` | |
| `ParameterNotDifferentiableError(ValueError)`, `TwinEvaluationError(RuntimeError)` | | `compile/casadi_backend.py:647,662` | |
| `RootComparisonError(ValueError)` | | `orchestrator/roots.py:48` | |
| `InnerSolveInconsistentError(RuntimeError)` | | `orchestrator/tear.py:95` | |
| `_RefusedError(Exception)` | | `application/bindings/http.py:104` (private; carries ApiError) | |
| Others (private/internal) | | `models/syn001/pump.py:532`, `column_blocks.py:190`, `ph_kernel.py:159`, `cascade_solve.py:381`, `saturation_band.py:63` | |

Counting: about 70 `class …(Exception|RuntimeError|ValueError)` definitions under src/ (grep `class .*Error|Refusal|Failure`). No common base class across the stack; `ApplicationError` and `StoreError` are unrelated.

**`LocalApplication.create`** — `application/local.py:190-212`:
```
def create(cls, directory, *, project_id=None) -> LocalApplication:
    ProjectStore.create(Path(directory), project_id=...).close()
    return cls.open(directory)
```
Its "not empty" refusal is raised one level down in `ProjectStore.create`, `application/store.py:252-256`:
```
    def create(cls, directory: Path, *, project_id: str) -> ProjectStore:
        """A new project in `directory`, which must be absent or empty."""
        ...
        if directory.exists() and any(directory.iterdir()):
            raise StoreError(f"{directory} is not empty; a project is created in a new directory")
```
It is a plain `StoreError` (RuntimeError), **not** an ApplicationError/ApiError: it has no code and no audit record. The CLI catches it (cli.py:230-232, prints to stderr, exit 2).

**`LocalApplication.open()` exists**: `application/local.py:214-…`, signature `open(cls, directory, *, capability: CapabilityReference | None = None, executor: Executor | ProcessExecutor = "inline") -> LocalApplication`. Store-level open is `store.py:291` and raises `StoreError(f"{directory} is not a project (no {DATABASE_NAME})")` when the db is missing (store.py ~296). Invalid policy → `PolicyRefusedError` (documented in open's docstring).
**No `exist_ok` parameter exists** on `create` (grep: none in src). The FB-01 request for `create(..., exist_ok=True)` / `open_or_create` is therefore unimplemented.

## 3. RunResult and the failed-run path

`application/types.py:1142-1158` `@dataclass(frozen=True) class RunResult`:
fields: `job_id, run_id|None, revision_id, revision_content_sha256, policy_id, policy_sha256|None, check_policy_sha256|None, job_status: TerminalStatus, outcome: str|None, verification_status: VerificationStatus|None, structural_sha256|None, outputs: tuple[ArtifactRef,...], error: ApiError|None = None, solve_path: SolvePath = "revision_eo"`.
`__post_init__` (types.py:1160-1166): verification_status requires a solution_certificate output.

Construction: `application/local.py:1002-1017` `_run_result(job)`: `error=job.error`, `outcome=run["outcome"]`, `verification_status=run["verification_status"]`, `outputs=job.outputs`.

**Why `error` is None on a failed run**: a solve that does not converge is not a job error. The runner ends the job `completed / operation_completed` with `error=None` (`application/jobs/runner.py:591-593`; also 680, 741). The failure is recorded as `outcome` (e.g. INITIALIZATION_FAILED) plus a `failure-bundle.json` output:
- `application/revision_run.py:864` `artifacts["failure-bundle.json"] = result.failure.as_document()`; `FAILURE_NAME` at `revision_run.py:1182`.
- `run/session.py:70` same for the legacy/session path.
- `application/jobs/model.py:127` `"failure_bundle": "failure-bundle.json"`.
- `run/identity.py:155` reads it.
- Revision coupled path: `application/coupled_run.py:348`.
So `error` is set only for operational failures: `RunUnsupportedError` → `failed(operation_error)` with `unsupported(<code>)`; `VerifierError` → `failed(verifier_refused)`; store/worker errors (runner.py:274-308; doc at runner.py:48-58).

**The `not_found: no such artifact` path**: `application/local.py:1481-1488` `_artifact_row(artifact_id, operation)`: `self._store.artifact(artifact_id)` (store.py:1019, SQL on `artifacts` by `artifact_id`); if None → `self._refuse("not_found", "no such artifact", operation=..., artifact_id=...)`. Called from `artifact_bytes` (local.py:1456; docstring 1447 gives `<bundle id>/solution-state.json` as the example) and the read at local.py:1331. The `detail` carries `operation` and `artifact_id` but **not** the bundle's member list or the run outcome. Sibling: `_revision` at local.py:1474 → `"no such revision"`. A replay bundle path (`artifact_bytes` on a directory) → `unsupported` at local.py:1466-1472.

## 4. How errors travel to each surface

**Core rule**: `application/operations.py:544` `dispatch(app, name, request)` is the one path; raises `ApplicationError` with a bounded `ApiError`; unknown op → `invalid_request` (operations.py:550-560). `project_error(error)` at `operations.py:526-533` bounds message and detail (§10.4). `TEXT_LIMIT` used for message. Domain outcomes are returned, never raised (ADR 0019 D5).

**CLI** — entry point `pyproject.toml:4`: `openflowsheet = "openflowsheet.application.cli:main"`. `cli.py:572` `main(argv) -> int`; `cli.py:580` `raise SystemExit(main())`.
- Exit-code map `cli.py:52-55` `API_EXIT_CODES = {code: 2 + index}` over `ApiErrorCode` order (2..16). 0 = domain result; 1 = call never made (unreadable request file / project cannot open, printed on stderr; cli.py:17-20 doc); argparse usage error = 2.
- `command_api` `cli.py:298-395`: prints ApiError document as canonical JSON on stdout, exits `API_EXIT_CODES[code]` (`cli.py:328-330`); `except (StoreError, PolicyRefusedError)` at `cli.py:322` → stderr, exit 1.
- `command_validate` `cli.py:66-100`: `except ApplicationError` → `_print_document(refused.error.as_document())`, exit by code (cli.py:76-78). Text output prints `[ok|FAIL|warn|-]  id: message` and "implicated:" lines (cli.py:86-90). Exit 1 iff INVALID.
- `command_solve` `cli.py:103-121`: prints `case / outcome / verification / structural sha256 / bundle`; exit 0 iff `verification_status == "VERIFIED"`, else 1. **It does not print the failure reason.** Unknown case → stderr, exit 2 (cli.py:110).
- `command_inspect` `cli.py:124-180`: when `failure-bundle.json` is present, prints `=== failure <outcome>`, `taxonomy`, `implicated`, and `suggested_actions` (cli.py:165-171). This is the only CLI place that surfaces the failure reason.
- `command_project_init` `cli.py:223-237`: StoreError → `print(str(error), file=stderr)`, return 2.
- Uncaught exceptions: no top-level catch in `main` (cli.py:572-577) — a raw traceback escapes unless caught in a command.
- No `explain` subcommand. Subcommands: validate, solve, inspect, replay, project {init,grant,revoke}, api, serve-http, serve-mcp (cli.py:470-562).

**HTTP** — `application/bindings/http.py`:
- Docstring §5.8 at lines 22-23: domain result 200 with document; raised ApiError → its §5.8 status with error document.
- `_error_response(error, headers)` `http.py:123-131`: `bounded = project_error(error)`; `Response(_json_bytes(bounded.as_document()), status_code=bounded.http_status, media_type=_JSON_MEDIA_TYPE)`.
- `_internal_error(operation)` `http.py:134-143`: logs traceback; body code `internal_error`, message "the server failed to complete this request; the defect is logged", detail `{operation}`.
- Dispatch catch: `http.py:375` `except ApplicationError as raised:` (plus `_RefusedError` at :104-109 for request-shape refusals).
- Status = `API_ERROR_HTTP_STATUS[code]` (types.py:88-104). Error JSON = `ApiError.as_document()` = `{code, message, detail, retryable}` (types.py:273-279); schema `schemas/api-error.schema.json`.
- Web shell (`--ui`) is a client of the HTTP binding: `application/bindings/web.py:86` WebShellMissingError.

**MCP** — `application/bindings/mcp.py`:
- Module doc lines 17-20: a response is `structuredContent` plus §10.6 text; a refusal is a tool error (`isError`) carrying the ApiError document in both places (§5.8); defect → `internal_error` with fixed message (`bindings/mcp.py:72` `INTERNAL_ERROR_MESSAGE = "internal error; the details are in the server's log"`).
- `_tool(operation)` `mcp.py:184`; `call_tool` path `mcp.py:209-224`: `except ApplicationError as refused: return _error_result(tool, refused.error)` (213); generic `except Exception` → `_LOG.exception`, `internal_error` (215-222).
- `_unknown_tool` `mcp.py:228-238` → `invalid_request` (also used for tools not exposed, e.g. `solve`, `reproduce`, `artifact_bytes`).
- `_error_result(tool, error)` `mcp.py:241-245`: `CallToolResult(content=[_text(tool, document)], structuredContent=document, isError=True)`.
- `serving.py:70` `serve_mcp` (stdio); `serving.py:38` ServeRefusedError.

**Shared envelope**: `ApiError{code, message, detail, retryable}` — `application/types.py:261-290` (`from_document` validates `api-error.schema.json`), `schemas/api-error.schema.json` (message maxLength 2048). `retryable` semantics: ADR 0019 / R-095 ("a new job may succeed unchanged").

**Jobs**: job error = `ApiError` stored on the job (`jobs/runner.py:186-205` WorkerResult.as_document/from_document with `error`). `LocalApplication` job results carry `error=job.error` (local.py:966-975).

## 5. Warnings, certificate statuses, limitations, notices

- **Certificate / verification statuses**: `application/types.py:114` `VerificationStatus = Literal["VERIFIED","RELAXED","UNVERIFIED","FAILED"]`; same literal `src/openflowsheet/verify/__init__.py:41`. `RegularityStatus` `verify/__init__.py:42-44` (NO_RANK_LOSS_DETECTED, RANK_DEFICIENT, ILL_CONDITIONED, INCONCLUSIVE). `CheckOutcome` `verify/__init__.py:39` (pass, fail, unsupported, not_applicable). `CheckScope` line 40.
- **Job status / outcome**: `TerminalStatus` imported in types.py:45; `RunResult.outcome: str|None` free string (e.g. CONVERGED, INITIALIZATION_FAILED); `coupled_run.py:707` and `revision_run.py:579` branch on `"CONVERGED"`.
- **Validation WARN**: `application/validation.py:85` Result includes WARN; WARN emitted at validation.py:314, :798. No separate "warning" list on RunResult (no `warnings` field found in types.py).
- **Notice failure kind**: **not found** (`grep '"notice"'` hits only `assessment/lca/tables.py` rights notices, unrelated).
- **Failure kind (input / unsupported / numerical / internal)**: **not found** as an enum or field anywhere in src. Nearest analogues: `ApiErrorCode` (invalid_request vs unsupported vs internal_error), job `ENDING_REASONS`, failure-bundle `TAXONOMY` (solver classes), `Unbound.kind` (conflict|inadmissible|incomplete|unsupported).
- **Limitation ids**: docs only. `docs/support-matrix.md` tables carry ids L01, L10, L49, L-CSTR-1..3, L-COL-1..10, L-TH-1..8 (e.g. L-TH-4 wording in FB-05), L-GP-1..3, L-S11-1..3, L-WS-1..2, L-WEB-1..4, L-STR etc.; each row cites tests/docs. Generated by `scripts/t08_support_matrix.py` (`--check`). Registered limitations are also in the T08 envelope `benchmarks/t08/support_envelope.yaml` (R-193, R-216). **Not found**: any `L-TH-4` string in src/*.py (only comments/markers in models/thermal/machines.py:21, 138 use L-GP-2 style). Limitation ids are not emitted in any runtime message today (the FB-05 example `limitation L-TH-4` is aspirational).
- **Hints**: `Unbound.hint` (binding.py ~297, 512 cp limit), R-109 "every missing pin and every specification refusal names the accepted encoding, beside an unchanged code"; R-841 hints name bases (decision register line 16577).

## 6. Tests that pin strings, codes or envelopes

Rough counts (grep over tests/, 513 files in tests/):
- ~15 asserts of the form `status_code == <4xx/5xx>` (test_t07_w6a_http.py has 17 matching lines overall for codes/status; test_t07_w4a_jobs.py 20).
- ~229 lines asserting `.code ==`, `["code"] ==`, `isError`, `API_EXIT_CODES`, `API_ERROR_HTTP_STATUS` across the file set.
- ~650 `pytest.raises(...Error)` lines (broad; most check exception class, not message).
- ~65 files mention a specific code/message token (`phase_regime_mismatch`, `INITIALIZATION_FAILED`, `initializer_failed`, `model_unsupported`, `not_found`, `no such artifact`, `not empty`).
Key files:
- `tests/test_t07_w6a_http.py` (HTTP status/envelope), `tests/test_t07_w6b_mcp.py` (isError, structuredContent), `tests/test_t07_w5b_cli.py` (CLI exit codes/stdout), `tests/test_t07_conformance.py` (one conformance suite over four clients, ADR 0019 D6), `tests/test_t07_w4a_jobs.py` (job errors), `tests/test_t07_store.py` (StoreError), `tests/test_t07_authz.py` (forbidden/unauthenticated), `tests/test_t07_r6_hints.py` (refusal hint text; R-109), `tests/test_t07_w5a_projection.py` (bounded messages), `tests/test_t08_w2_unsupported.py`, `tests/test_t08_w1_typed_ends.py` (typed ends), `tests/test_s11_thermal_kernel.py`, `tests/test_s11_thermal_solve.py`, `tests/test_s11_thermal_units.py` (phase_regime_mismatch / isentropic_state_* strings).
- **Golden file**: `tests/fixtures/t07/cli-existing-commands.json` — argv/exit/stdout golden records for existing CLI commands (e.g. `validate <CASE>` exit 0 with full stdout). It contains `no such artifact` / `not empty` text; a change to those strings breaks it. Consumed by `tests/test_t07_w5b_cli.py` (and grep hits in tests/t08_*.py for the fixture name).
- R-159 says "tests match the prefix, not the prose" — the design intent for the existing `code(...)` convention.
- Test runner: `scripts/check.sh` runs `ruff check .`, `ruff format --check .`, `mypy`, `pytest -q -rs` (scripts/check.sh:23-28). `scripts/gate.sh [log]` wraps it, prints one summary line, log in a file. pytest config: `pyproject.toml:187-196` (testpaths=tests, pythonpath=["."]); opt-in markers `nlp`, `pymrm` deselected by default.

## 7. Frozen interfaces and governing decisions

- `docs/implementation-plan.md:55` — "The Protocol signatures in §2.1 and the schema list in §2.2 are frozen at the end of P01 and thereafter change only by a design-lane ADR."
- `docs/implementation-plan.md:68-97` §2.1 Protocols (CompiledProblem, PropertyProvider, Application). §2.2 (line 97+) schema table lists P01 ProcessRevision, Quantity, ComponentRecord, ModelManifest, Specification, ValidationReport; K03 SolvePolicy, SolvePlan, SolveEvent…; K04/K05 SolutionCertificate, FailureBundle, RunManifest. **api-error.schema.json and the error codes are not named in §2.2.**
- `docs/interfaces-frozen.md:6-20` §1 verbatim Protocols (Application at line 20). "Frozen, `docs/interfaces-frozen.md` §1 — verbatim (ADR 0019 D1)" (contract.py:~64). Amendments to schemas listed in interfaces-frozen.md:68-110.
- **ADR 0019 D5** (`docs/adr/0019-application-contract-v1.md:63-65`): "One `ApiError{code, message, detail, retryable}` with the closed code enum and the HTTP mapping of design note §5.8. Domain results … are results, not errors." Amendment 1 (line 105) freezes JobControl/Inspection shapes.
- **R-095** (`docs/decision-register.md:2424`): "One `ApiError` shape with a closed code enum; domain outcomes are results, not errors." Rejected: "New codes in the closed enum … for the two job cases." Watch for: "a code added outside an ADR."
- **R-159** (`docs/decision-register.md:3727`): "every refusal's `message` begins with its reason code"; codes out_of_domain, light_gas_in_liquid, no_liquid_root, no_vapour_root, vapour_root_metastable, undeclared_derivative_input, dormant_state (ADR 0026 D6, M01-spec §5.3, §9.1, §9.4). "Tests match the prefix, not the prose after it." Rejected: a new status or result field for the reason.
- **R-109** (decision-register.md:2687): every missing pin and specification refusal names the accepted encoding, beside an unchanged code.
- **R-104 / ADR 0020 D8** (decision-register.md:2593-2603): job events carry no solver messages; the `t07` identity key carries no message text.
- **ADR 0025** (`docs/adr/0025-cross-platform-replay-comparison.md:173`): replay comparator treats `message`/`cause` as "template exact; tokens D2.1"; line 192: "Float-free messages at the producer". So message templates are compared in replay.
- **R-022** (decision-register; cited in binding.py:266): kinds conflict / incomplete / unsupported, not interchangeable.
- **R-251**: stage `model_exception`, a deterministic cached refusal.
- **R-838 / R-841** (decision-register.md:16511, 16577): refusal hints name bases.
- **Message text stability**: **no document found that freezes message wording or the error-code list beyond the ADR-closed enum.** R-159 is the only stated stability mechanism (prefix match in tests).

## 8. Explain command, error docs, number formatting

- **`openflowsheet explain`**: **not found**. No `explain` in cli.py, no subcommand, no test.
- **Per-code docs pages**: **not found**. docs-site has no error-code page. docs-site/guide/limitations.md:21-33 has a "Not supported, and how each is refused" table (informal, e.g. `model_unsupported(<id>)`, `INITIALIZATION_FAILED`, `invalid_trial_state`, `task_unsupported(optimization)`, `UNSUPPORTED_RANK_STRUCTURE`).
- Generated doc pages: `scripts/doc_pages.py` generates only `docs-site/guide/units.md` (unit catalogue); `--check` mode (doc_pages.py:12, 163-165). `scripts/t08_support_matrix.py` generates `docs/support-matrix.md`.
- docs-site/api/*.md (assessment, contract, index, local, operations, replay, types, validation): API reference pages; check whether they list ApiErrorCode (not checked in depth).
- docs-site/examples/what-if-and-refusals.ipynb: an example notebook on refusals (not read).
- **Units in messages**: no shared number-formatting helper for messages was found. `grep` for `def .*format|fmt` in src returns only `orchestrator/phase_contract.py:117 format_signature`. Three `.3g/.4g/:g}` format uses in application/. Units machinery: `units/__init__.py` (`convert_input_value` line 494-530 → SI value + `UnitConversion` record; `UnitConversionError` 469; `check_quantity` 244); `schemas/units.json`; `schemas/quantity.schema.json`; docs-site/guide/units.md. Messages today are generally in SI or internal units (e.g. `phase_regime_mismatch` carries only the stream id, no values).
- No "what to do" / suggested-action field on ApiError (fields: code, message, detail, retryable). Failure bundles have `suggested_actions` (schema `failure-bundle.schema.json`, printed by `inspect` at cli.py:170-171).

## 9. FEEDBACK.md (tutorial repo, outside this repo; read only that file)

Source: /home/frankp/Codes/OpenFlowsheet_tutorial/FEEDBACK.md — FB-01 (lines 8-20), FB-03 (24-32), FB-05 (41-80) copied verbatim below.

## FB-01 — Misleading error when the quickstart is re-run (open; user-endorsed proposal)
- **What happened:** The user ran the README/quickstart snippet a second time (in Jupyter). `LocalApplication.create("plant")` raised
  `StoreError: plant is not empty; a project is created in a new directory`.
  The user read the second half as a statement of what had happened ("it says a project is created in a new directory, but it does not do this").
- **Why it confuses:** "a project is created in a new directory" is a rule, but it reads as a report of an action. The message does not point to the fix: `LocalApplication.open("plant")`.
- **Suggestion:** e.g. `plant is not empty: create() needs a new or empty directory. To use the existing project, call LocalApplication.open("plant")`. Optionally, the quickstart could note that it can't be re-run as is (or use a fresh or temporary directory name). A typical notebook user re-runs cells.
- **Repro:** run the README Python quickstart twice in the same working directory.
- **User's idea:** create a new directory anyway and warn, with the warning saying how to reuse the existing one.
  Counterpoint (tutorial session): a silently renamed project splits the work, and later `open("plant")` calls hit the old project. Warnings are easy to miss in scripts and notebooks.
  Alternative: keep the refusal with a better message, and add an explicit opt-in such as `create(..., exist_ok=True)` (which opens the project if one is there, like `os.makedirs`) or `LocalApplication.open_or_create(...)`. The quickstart could then use the opt-in and be safe to re-run.
- **User decision (2026-11-01):** proposal = refusal with a clearer message + `create(..., exist_ok=True)`, and the quickstart uses it. Keep "directory". Edge case for the dev: with exist_ok=True, a non-empty directory that is *not* a project must still be refused (as with a file in place of a directory for os.makedirs).
- **Wording:** keep "directory" in the API/CLI messages (it matches the parameter name `directory` and Python/Linux usage). "Folder" can go in beginner docs and the web shell.


## FB-03 — The failure reason is hard to find, and "no such artifact" is unhelpful (open)
- **What happened:** Rankine example with boiler-T = 973.15 K. `solve` returned `INITIALIZATION_FAILED None`. The quickstart code then asked for `<bundle>/solution-state.json` and got `ApplicationError: not_found: no such artifact`. The user found the message uninformative.
- **Issues:**
  (a) The error doesn't name the artifact id it looked up, and doesn't say which members the bundle has (here `failure-bundle.json`, `run-manifest.json`; there is no solution state because the run failed).
  (b) `RunResult.error` is `None` on a failed run. The actual cause (`initializer_failed(T): phase_regime_mismatch(S4)`) is only inside `failure-bundle.json`, which a new user doesn't know about.
  (c) The quickstart snippet doesn't check `run.outcome` before reading the solution state, so any failure surfaces as this unrelated-looking `not_found`.
- **Suggestions:** put the failure message (and the suggested action) on `RunResult`, e.g. `run.message`. Make `not_found` for a bundle member say "bundle job-000004:bundle has no solution-state.json (run outcome INITIALIZATION_FAILED); members: ...". Add an outcome check to the quickstart.
- **Repro:** quickstart, then `Edit("set", ("specifications",4,"value"), 973.15)`, then solve.


## FB-05 — Error and warning messages should be understandable for inexperienced users (open; user's general request, high priority for the user)
**User's position:** messages must give even a student a clue to what went wrong and what to do. Today they're written for the developer or the verifier, not the user. In the FB-03/FB-04 case the user saw only `ApplicationError: not_found: no such artifact`, while the real story was "phase regime mismatch at the turbine outlet, and the case that would fix it is not supported in 0.3".

### What the message for this specific case could have been
Case 1, the S4 exhaust declared wet but coming out superheated:
```
SolveFailed: rev-000005 could not be initialised at unit 'T' (thermal.turbine).
  Cause:   phase regime mismatch at stream 'S4' (turbine outlet). S4 is declared
           'vapor_liquid' (wet steam), but at these conditions the outlet is
           superheated vapour (h = 2627 kJ/kg > saturated-vapour h_g = 2585 kJ/kg at 0.1 bar).
  Fix:     declare S4 as 'vapor':  Edit("set", ("connections", 3, "phase_capability"), "vapor")
  Details: run.failure (code phase_regime_mismatch; docs: <link>)
```
Case 2, S4 declared vapour while the isentropic reference is wet:
```
SolveFailed: rev-000006 could not be initialised at unit 'T' (thermal.turbine).
  Cause:   NOT SUPPORTED in OpenFlowsheet 0.3: a turbine whose actual outlet is vapour
           while its ideal (isentropic) outlet is two-phase (limitation L-TH-4).
           This is a limitation of the software, not an error in your flowsheet.
  Options: keep the turbine outlet wet (e.g. a lower boiler temperature or a higher
           pump pressure), or wait for a later version. Limitations: <link>
```
And the follow-up `artifact_bytes` call should not have been the first visible failure (see FB-03).

### General principles proposed
1. **Answer four questions in plain words:** *what* failed, *where* (in the user's own names: unit `T`, stream `S4`, `specifications[4]`, revision, job), *why*, and *what to do next*.
2. **Say which kind of failure it is**, because the right response differs:
   (a) an input error ("fix your flowsheet");
   (b) a feature not supported in this version ("not your fault; limitation L-xx; workaround or wait");
   (c) a numerical failure ("try an initial guess, continuation, another policy");
   (d) an internal bug ("please report, with this bundle").
   A student who can't tell (a) from (b) wastes hours.
3. **Layer the message; don't replace the codes.** Line 1 is a human summary. Then the stable typed code (agents and tests keep relying on it). Then the details and evidence. Both humans and agents are served.
4. **Fail where the problem is.** A failed solve should be obvious at `solve()`, not surface later as an unrelated `not_found`. Options: `run.message` / `run.failure` on `RunResult`, a `run.raise_for_outcome()` helper (as in `requests`), or a printable `RunResult.__str__` that summarises the outcome.
5. **Show the numbers that triggered it**, in the units the user specified: the computed value against the limit (T vs T_sat, h vs h_g, P vs the domain bound).
6. **Avoid internal jargon in the first line, or explain it:** e.g. closure, regime, initializer, region_closed, revision_eo, T06/A21-style document ids. Those are fine in the details, and a short glossary in the docs helps.
7. **One docs page per error code**, reachable from the message, and a command such as `openflowsheet explain phase_regime_mismatch` (cf. `rustc --explain E0308`). The support-matrix limitation ids (L-TH-4, ...) should link to readable explanations.
8. **Warnings follow the same structure.** Also give a plain-language meaning of every certificate status (RELAXED, UNVERIFIED, ...) and of near-limit results (close to a domain edge or the critical point), and point to whether the user should worry.
9. **Test the messages.** Keep a small corpus of typical beginner mistakes (wrong phase declaration, over/under-specification, a unit typo, out of domain, re-running `create`, reading the solution of a failed run) with the expected message, checked in CI. The tutorial can keep supplying cases.

