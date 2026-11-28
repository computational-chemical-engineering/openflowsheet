# ADR 0078: X06, application capabilities: MCP over streamable HTTP, branches, solve policies, in-band administration; job resume deferred to F7 D14

**Status:** **Accepted, 2026-11-26** (the user, Decision Desk `ofs-x06-accept-adr0078`, choice A, signed
2026-11-26T23:14:33Z: "Accept ADR 0078 as written at dcbab9b7 with its defaults: Q1 job resume deferred to F7 D14
(0.8); Q2 in-band administration off by default behind a per-project operator switch; Q3 administration writes refused
on a server bound beyond loopback, no override in 0.6; Q5 registering a solve policy needs the draft right; Q6 the
seven benchmark-registered policies stay unsupported."; Q4: `ofs-x06-mcp-clients`, choice A, static bearer only in
0.6, OAuth later; R-1071). Proposed 2026-11-26, LINE06 D1 (`docs/briefs/LINE06-X06-architect.md`); built in 0.6 on
`wp/X06` (R-1070, ADR 0057 Amendment 3). The text below is unchanged from `dcbab9b7`.
**Author:** design lane (`architect`). **Scope:** ADR 0056 row 8 in full and in its order (Decision Desk card
`ofs-line06-x06-scope`, choice A, signed 2026-11-26): MCP over HTTP, branches, job resume, further solve policies,
policy administration. **This ADR proposes deferring one part, job resume, to F7 (D3 below), for the user's
acceptance.**
**Lifts:** R-110 for MCP over HTTP, branches, further solve policies and in-band administration. R-110's resume
exclusion and ADR 0020 D3's "no resume" stand until F7 D14 is built.
**Amends** (each additive; every stored record, run identity and released number unchanged):
- ADR 0019 D1 as **Amendment 18**: three sibling protocols `Branches`, `SolvePolicies`, `Administration` (D2, D4, D5);
  D2: additive schema members and `$defs` (listed per decision); D4: "no in-band `policy` operation" is replaced by D5
  of this ADR (in-band `install` and `publish` stay excluded); D6: the MCP transport gains a second carrier,
  streamable HTTP (D1).
- ADR 0057 / note §2.6 C7: implemented as D2. C6's "per-kind checkpoints for resume (X06)" stays with F7 D14.
- `docs/interfaces-frozen.md` §2.1 (protocols) and §2.2 (schemas): the members named below.

## Context

- **Transports today.** One `OPERATIONS` table (`application/operations.py:445`) drives Python, CLI `api`, HTTP
  (Starlette, `bindings/http.py`) and MCP (`bindings/mcp.py`, the SDK's low-level server over **stdio only**). MCP
  stdio authenticates a token file once at start (`serving.serve_mcp`) and is re-authorized per call against the
  hot-reloaded policy. HTTP authenticates `Authorization: Bearer prt_…` per request through
  `Owner.authenticated(token)` (`http.py:179`), binds `127.0.0.1:8765` unless `--allow-remote`, has no TLS, no CORS,
  and caps bodies at `MAX_BODY_BYTES = 1 MiB`. The pinned SDK is `mcp==1.30.0` (extra `server`), which ships
  `StreamableHTTPSessionManager` (stateless and JSON-response modes); no new dependency is needed.
- **Refs today.** `project.sqlite3` (store schema `t07-store-v1`) already has `refs (name TEXT PRIMARY KEY,
  revision_id …)`; it holds one row, `head` (`store.py:81`, `:90`). `commit_change` compares `expected_revision` with
  `head` inside `BEGIN IMMEDIATE` and `commit_revision` upserts `head` (`store.py:356-382`,
  `revision_service.py:76-140`). `restore_from` already lets a commit start from any stored revision's document.
- **Jobs today.** Five job operations (`solve`, `reproduce`, `experiment`, `surrogate_study`, `optimize`), a process
  per job (ADR 0020 D1), cooperative then forced cancellation (D3), J6 "a re-run is a new job", J4 resume absent.
  `experiment`, `surrogate_study` and the coupled solve route record every experiment in the project-wide,
  content-addressed `ExperimentStore` (`adapters/experiments/store.py:120`, key `experiment_key(request)`), so a
  re-submitted job already reuses every completed experiment (`cache_hits`). An interrupted `optimize` keeps its
  completed per-start bundles as artifacts, not outputs (ADR 0071 D8). **F7's ADR 0066 already designs resume:** D11
  `submit_run(…, resume_from: <artifact_ref> | null)` and D14 per-kind `run-checkpoint` envelopes, "resume is a new
  job (J6) with `resume_from`", refusing `checkpoint_incompatible(<field>)`; its work orders WO5/WO6 name "X06
  (resume via D14)". F7 is in 0.8.
- **Solve policies today.** `APPLICATION_POLICIES` offers five (`orchestrator/policies.py:119`): `T06-revision-v2`,
  `T04-W12`, `T08-ptc-v1`, `T08-warm-v1`, `RRC-revision-v1`. Seven more names are registered for benchmark evidence
  and refused `unsupported` ("registered but not offered"); anything else is `not_found` (`admission.py:237`). A run's
  bundle carries `solve-policy.json`; replay rebuilds the policy from that file and checks its hash against the
  manifest (`revision_replay.py:189-194`), never by id lookup. The verifier imports no `SolvePolicy`: its tolerances
  and scales are `CheckPolicy`'s registered ones, which may only be tightened (`verification_weakening_refused`).
- **Policy administration today.** `project-policy.json` (schema `project-policy-v1`) changes only through the operator
  CLI (`project init`, `grant`, `revoke`, `ambient`; `authz.py:279-450`), each an atomic replace plus an audit row as
  `local-owner`, under the store's write transaction; `PolicyFile` hot-reloads it. Tokens are `prt_` + 43 base64url
  characters; only their SHA-256 is stored. Rights are blueprint §11.3's six. `policy` is held today by grants that
  asked for it; it already gates `assess_rights`, cancelling another principal's job and reading others' audit rows.

## Decisions

### D1. MCP over streamable HTTP: one server, one endpoint, stateless, bearer per request

1. **Where.** `openflowsheet serve-http` serves MCP at the exact path **`/mcp`** on the same Starlette application,
   host and port as the REST routes and the web shell. No new command, no second port. `serve-mcp` (stdio) is
   unchanged.
2. **Carrier, not transport.** A row whose `transports` include `"mcp"` is served on both carriers; the `Transport`
   literal gains no value. The tool list is `bindings.mcp.tools()` on both carriers, so the served tool list is one
   object (E-X06-2).
3. **Mode.** `StreamableHTTPSessionManager(app=<low-level server>, stateless=True, json_response=True,
   security_settings=None)`, run in the Starlette lifespan. Each `POST /mcp` carries one JSON-RPC message and gets one
   `application/json` response (or 202 for a notification). No `Mcp-Session-Id`, no SSE stream, no event store. `GET`
   and `DELETE` on `/mcp` are answered `405` with `Allow: POST` by the guard (item 5) before the SDK. The SDK's own
   header checks (Accept, Content-Type, `MCP-Protocol-Version`) stand; tests pin the statuses they produce.
4. **Binding refactor.** `bindings.mcp.build_server(app)` becomes `build_server(caller: Callable[[], Dispatchable])`;
   `call_tool` obtains its `Dispatchable` from `caller()` on every call. stdio passes `lambda: app`. HTTP passes a
   function that reads the caller the guard stored in the ASGI scope (`scope["state"]["openflowsheet.caller"]`, read
   through the SDK's `request_context.request.state`); a missing caller is a defect, `internal_error`, never a fallback.
   Everything else in `call` (dispatch in a worker thread, structured result plus text, `isError` with the `ApiError`
   document, fixed `internal_error` message, traceback to the log only) is shared unchanged.
5. **The guard** (new module `bindings/mcp_http.py`, an ASGI wrapper in front of the session manager), in this order:
   (a) method not `POST`: 405; (b) `Origin` present and not one of the served origins (`http://<host>:<port>` for the
   bound host, plus `http://localhost:<port>`, `http://127.0.0.1:<port>`, `http://[::1]:<port>` on a loopback
   binding): **403**, `ApiError forbidden`, `detail.code = origin_refused`; an absent `Origin` (non-browser client)
   passes (MCP 2025-06-18: servers MUST validate `Origin`); (c) declared `Content-Length` above `MAX_BODY_BYTES`, or a
   streamed body exceeding it: **413**, `ApiError invalid_request`, `detail.limit_bytes`; (d) no bearer, or a token
   `owner.authenticated` does not resolve (unknown, malformed, expired, revoked): **401**, `ApiError unauthenticated`,
   `WWW-Authenticate: Bearer`, audited exactly as the REST routes audit the same refusal; (e) otherwise the resolved
   view goes into the scope state and the request goes to the session manager. **No request reaches the SDK
   unauthenticated**, including `initialize` and `tools/list`. The token is read only from the `Authorization` header,
   never from a query parameter or the body, and is never logged (uvicorn's access log carries no headers).
6. **Security model (the HTTP surface as a whole, stated once).** Loopback by default; a non-loopback host needs
   `--allow-remote` and prints the existing no-TLS warning, which now names `/mcp` too. Authority comes from the
   bearer credential only (ADR 0019 D4), re-resolved on every HTTP request, so a revocation takes effect on the next
   call. There is no unauthenticated route that writes. No cookies, no CORS: a browser page on another origin cannot
   attach the bearer, which is what defeats DNS rebinding and CSRF here; the `Origin` rule is defence in depth. TLS is
   out of scope: remote use goes through a TLS-terminating reverse proxy that forwards to a loopback binding. MCP's
   OAuth authorization (protected-resource metadata, RFC 9728) is not implemented; clients send a static
   `Authorization: Bearer prt_…` header (Q4).
7. **Import graph.** `bindings/mcp_http.py` imports `bindings.mcp`, `mcp`, `starlette`, `anyio`, the contract modules
   and the standard library; `bindings/http.py` still imports no `mcp`. Composition happens where `serve-http` builds
   its application (`serving`/`cli`), as `bindings/web.py` adds the shell today. The import-graph tests' allowlists
   gain exactly these edges.

### D2. Branches: named refs in the store's existing `refs` table (C7, R-110 reconciled)

1. **Model.** A branch is a row of `refs` with `name = "branches/" + <branch name>` and the tip `revision_id`.
   `head` keeps its row name `head` and its meaning (the main line). No table, column or store-schema change; an
   existing project is a project with no branches. Revisions stay immutable and shared: a revision may be reachable
   from several refs, and deleting a branch deletes only its row.
2. **C7 and R-110 reconciled.** R-110 sketched "branches as an optional ChangeSet member"; C7 says branches live "in
   the project store, never in documents". Both hold: the `ChangeSet` is a transaction *request*, not a stored
   document. Its optional `branch` member selects which ref the transaction advances and is written into no
   `ProcessRevision`, no `content_hash`, no bundle, record or manifest (E-X06-9).
3. **Names.** `^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$` (no `/`, so C1's encoding rule never applies); `head` is reserved
   (`invalid_request`, `detail.code = branch_name_reserved`). The public name never carries the `branches/` prefix.
4. **`commit_change` / `preview_change`.** `change-set.schema.json` gains optional `branch` (the name pattern);
   absent means `head`. The Python `Change` gains `branch: str | None = None`; `Change.as_change_set` and the request
   normalization **omit `branch` when it is absent or equal to `"head"`**, so every existing request's normalized
   bytes and `request_sha256` are unchanged (E-X06-7). Check order inside the write transaction: canonical form,
   schema, reserved key, **ledger lookup** (a replay returns the original result even if the branch was deleted
   since), branch existence (`not_found`, `detail.code = branch_not_found`), then `expected_revision` against that
   ref's tip (a mismatch is the existing `conflict` result with `{expected, actual}`, `actual` the branch tip),
   then the commit, which moves only that ref. `expected_revision: null` is valid only on `head` (first commit).
   `restore_from` works on any ref; **promoting** a what-if is `commit_change` on `head` with `restore_from: <branch
   tip>` and no edits, which exists today. Invalidations (ADR 0035 D4) are per revision and unchanged.
5. **Operations** (protocol `Branches`; all four transports; `ledger` per ADR 0019 D3, scope `(principal, operation,
   key)`, `auto:` reserved):

   | Operation | Right | HTTP | Request | Response (`application-results` `$defs`) |
   | --- | --- | --- | --- | --- |
   | `list_branches` | read | `GET /v1/branches` | `{cursor?, limit?}` | `branch_page {items: [branch {name, revision_id}], next_cursor}`: `head` first when it exists, then names in bytewise ascending order |
   | `create_branch` | draft | `POST /v1/branches` | `{name, revision_id, idempotency_key}` | `branch_result {status: created \| replayed \| conflict, name, revision_id, conflict: {expected: null, actual} \| null}`; unknown revision `not_found` |
   | `delete_branch` | draft | `POST /v1/branches/{name}/delete` | `{name, expected_revision, idempotency_key}` | `branch_result` with `status: deleted \| replayed \| conflict`; unknown branch `not_found branch_not_found` |

   In `branch_result`, `revision_id` is the ref's tip after the call (`null` after a delete; the unchanged tip on a
   conflict). A create of an existing name is the domain result `conflict` (it expects absence), whatever the tip. There is no
   move, merge or rebase (D2 alternatives). Jobs keep naming immutable `revision_id`s; nothing in a job request names
   a branch.
6. **Store helpers** (`store.py`): `ref(connection, name) -> str | None`, `set_ref`, `delete_ref`,
   `branch_rows(connection, after, limit)`; `commit_revision` takes a required keyword `ref`. `head()` stays.
7. **Service.** `branch_service.BranchService` (new; `application-layers` directly below `records_service`), calling
   only the core and the store.

### D3. Job resume: deferred to F7 D14 (0.8); nothing is built in 0.6 (proposed for the user's acceptance)

**Reason, in three facts.** (1) The only work a job can reuse without a per-kind checkpoint is already reused: the
`experiment`, `surrogate_study` and coupled-solve kinds record every experiment in the project's content-addressed
`ExperimentStore`, so re-submitting the same request after an interruption recomputes only experiments that had not
completed. An X06 resume for these kinds would add API surface and no capability. (2) Every kind where resume would
add capability needs a per-kind checkpoint: a `solve`'s iterate, an `optimize` job's completed starts (its
incumbents, which OPT D8 keeps as artifacts and not outputs), a transient's integrator state. Their format, their
publication as output events, and their compatibility rule are C6's and ADR 0066 D14's (F7), and accepting an archived
state needs ADR 0020 D7's W14 path test, which F7 should write once for all kinds. (3) F7 has already fixed the
addressing: `submit_run(…, resume_from: <artifact_ref>)` of a `run_checkpoint` artifact. A 0.6 member such as
`resume_of: <job_id>` would be a second, coarser address for the same capability, to be removed again by F7 (the user
asked for no shims).
**In 0.6:** R-110's resume exclusion and ADR 0020 D3 stand; no request member, no operation. The user guide states
the reuse that exists (a re-submitted experiment, surrogate study or coupled solve reuses completed experiments),
citing the existing test that shows it, or omits the sentence if no test shows it. **After F7:** resume of the
existing kinds (`solve` iterate, `optimize` starts) is an X06 follow-up on D14, planned with F7-WO5/WO6.

### D4. Further solve policies: project-registered, immutable, `user.`-named policy documents

1. **What is admitted.** A project may register solve-policy documents (`solve-policy.schema.json`, unchanged) whose
   `policy_id` matches `^user\.[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$`. A job (`solve`, and `optimize`'s solve body) names one
   by id like any offered policy. The five offered policies and the seven benchmark-registered names keep exactly
   today's behaviour, refusal messages included.
2. **Why it is safe.** The certificate is the guard: the verifier reads no solve policy, so a project policy can change
   how the solver searches, never what is accepted. `CheckPolicy` stays the registered one or a tightening
   (E-X06-14). A run under a project policy is a new run; its bundle carries the policy document as
   `solve-policy.json` exactly as today, so it replays without the project (E-X06-13).
3. **Registration checks** (pure function `solve_policy_problems(document) -> list[(pointer, message)]`, new module
   `orchestrator/policy_validation.py`), in order: (a) the schema; (b) the id pattern (`invalid_request`,
   `detail.code = solve_policy_id_invalid`); (c) the round trip `canonical(SolvePolicy.from_document(d).as_document())
   == canonical(d)` (no member defaulted, dropped or reinterpreted); (d) **every member the schema leaves open is
   checked against the registry the solver dispatches on**: each `initializer_chain` entry, `linear_solver.name` (and
   its options), the keys of `residual_tolerances` and `scales` (registered quantity kinds), and every open string under
   `recycle` and `globalization`; an unknown value is refused at registration with its pointer
   (`detail.code = solve_policy_invalid`), never at run time. A test walks the schema and fails if an open member has no
   check (E-X06-11c).
4. **Storage.** A job-less artifact row (precedent: ADR 0035 D3's `model_replacement_report`): `artifact_id =
   "solve-policy:" + policy_id`, `job_id NULL`, `kind = "solve_policy"`, `name = policy_id + ".json"`, `sha256 =
   policy_sha256`, file `solve-policies/<policy_sha256>.json` holding the canonical bytes (named by hash so ids that
   differ only in case never collide on case-insensitive file systems). File first, then the row, in one write
   transaction. Write-once: an id is never re-bound. No table or schema change.
5. **Operations** (protocol `SolvePolicies`; all four transports):

   | Operation | Right | HTTP | Request | Response |
   | --- | --- | --- | --- | --- |
   | `register_solve_policy` | draft | `POST /v1/solve-policies` | `{policy: <solve-policy>, idempotency_key}` | `solve_policy_registration {status: registered \| exists \| replayed \| conflict, policy_id, policy_sha256, conflict: {expected_sha256, actual_sha256} \| null}`: same id and bytes `exists`, same id other bytes `conflict` |
   | `get_solve_policy` | read | `GET /v1/solve-policies/{policy_id}` | `{policy_id}` | `solve_policy_view {policy_id, policy_sha256, origin: builtin \| project, document}`; a benchmark-registered name is `unsupported` as at admission, anything else `not_found` |

   `get_project`'s `solve_policies` lists the offered five in today's order, then the project's by id (bytewise
   ascending); a project without registered policies returns byte-identical summaries (E-X06-15).
6. **Admission and the runner.** `resolve_policies(route, body)` becomes `resolve_policies(route, body,
   project_policies: Mapping[str, SolvePolicy])` and stays pure; a `user.` id absent from the mapping is `not_found`
   (`detail.code = solve_policy_not_found`). Both callers load the mapping through one low-level function,
   `solve_policy_registry.load(store, files_root)` (new module, persistence layer, directly above `authz`), which
   verifies each file's SHA-256 against its row; a mismatch is `internal_error` at admission and the ending reason
   `store_error` in the runner. The runner re-resolves at its `resolve` stage as today (ADR 0020 §6.4).
7. **Service.** `solve_policy_service.SolvePolicyService` (authorization, ledger, audit, registration), placed lowest
   among the services, directly above `service_core`, because `validation_service`, `job_service` and
   `inspection_service` call it.

### D5. In-band policy administration: audited operations, off by default, no escalation, never on a no-TLS remote server

1. **The switch.** `project-policy.json` gains an optional member `administration: {in_band: true}`; absent means off,
   and `ProjectPolicy.as_document` omits it when off, so every existing policy file keeps its bytes and its
   `policy_sha256` (E-X06-16). Only the operator sets it: `openflowsheet project administration on|off` (audited
   like `grant`). It is not an operation, as `project grant` is not today. Reason: without it, every existing grant
   holding `policy` would silently gain the power to mint credentials.
2. **Operations** (protocol `Administration`; all four transports; right `policy`; writes are ledgered):

   | Operation | HTTP | Request | Response |
   | --- | --- | --- | --- |
   | `get_policy` | `GET /v1/policy` | `{}` | the stored `project-policy` document (token hashes included: a SHA-256 of a 256-bit random token authenticates nothing) |
   | `grant_capability` | `POST /v1/policy/grants` | `{principal_id, rights?, limits?, expires_at?, note?, capability_id?, idempotency_key}`; defaults as `project grant` | `grant_result {status: granted \| replayed, capability, token: prt_… \| null, policy_sha256}` |
   | `revoke_capability` | `POST /v1/policy/grants/{capability_id}/revoke` | `{capability_id, idempotency_key}` | `revoke_result {status: revoked \| replayed, capability, policy_sha256}` |
   | `set_ambient_pressure` | `POST /v1/policy/ambient-pressure` | `{value: number \| null, unit?, idempotency_key}` (units as `project ambient`) | `{status: set \| replayed, ambient_pressure_pa, policy_sha256}` |

3. **Refusals of the three writes**, after `authorize` (unchanged, pure) allowed `policy`: switch off: `unsupported`,
   `detail.code = administration_disabled`; the serving process binds a non-loopback interface:
   `unsupported`, `detail.code = administration_remote_refused` (a flag `serving_remote` on the owner's `ServiceCore`,
   set by `serve-http` from `is_loopback(host)` before serving; stdio and in-process are local). Then the delegation
   rule, a pure deny-only function `authz.delegation_refusal(caller, requested) -> str | None`: requested rights ⊆
   caller's rights; for `max_wall_time_s` and `max_active_jobs`, a caller limit `L` requires a non-null requested
   limit `≤ L`; a caller expiry `E` requires a non-null requested expiry `≤ E`; principal and capability id are not
   `local-owner` (existing check). A refusal is `forbidden`, `detail.code = grant_exceeds_caller`. A revoke needs the
   target's rights ⊆ caller's rights (`forbidden revoke_exceeds_caller`); unknown id `not_found capability_not_found`;
   an existing `capability_id` on grant `invalid_request capability_exists`. Revoking oneself is allowed. The switch
   applies to every caller, the in-process owner included (one rule).
4. **The token is shown once.** `grant_capability` returns the new token in its response only. The ledger stores the
   result **with `token: null`**; a replay returns `status: replayed, token: null`. No token or `prt_` string is ever
   written to the store, the audit, the policy file or a log (E-X06-18).
5. **Writing.** `authz._change_policy` becomes `change_policy(store, directory, operation, apply, *, actor:
   CapabilityReference, request_sha256: str | None)`: read-modify-write of the policy file under the caller's
   `store.writing()` transaction, atomic replace, one audit row `allowed` with the actor's principal and capability,
   `effect` `grant:<id>`, `revoke:<id>`, `ambient:<value>` or `ambient:cleared`, as today's CLI effects. The CLI passes `LOCAL_OWNER` and its
   current `request_sha256` (the updated policy's hash), so CLI audit rows keep their form. Concurrent writers
   serialize on `BEGIN IMMEDIATE`; no update is lost (E-X06-20). Executor settings and `project init` stay operator-only.
6. **Service.** `administration_service.AdministrationService` (directly below `branch_service`).

### D6. Order and surface

Built in the user's order: D1 (WO1), D2 (WO2), D3 (nothing), D4 (WO3), D5 (WO4), close-out (WO5). Every new row is
on all four transports (C1). No `ApiError` code is added (the enum stays closed at 15); new specifics are
`detail.code` values with catalogue entries. Each work order that adds a tool extends `tests/x06_schema_support.py`
(`without_x06`, removing exactly X06's rows, schema members and description files) and re-pins
`X06_SERVED_SHA256` in `tests/test_t08_w2_surface_digest.py`, with the decomposition test onto the digest on `main`
(the F1/F3 pattern). If F2 merges first and moves the served list, X06 decomposes onto F2's digest, and conversely.
Each work order that adds operations also adds them as steps of the conformance scenario, so all six clients run them
(C1; the conformance project's policy turns the administration switch on).

## Alternatives rejected

- **D1.** A separate MCP HTTP server or `serve-mcp --http` (two ports, two security configurations). Stateful sessions
  with SSE and an event store (no server-initiated message exists; job progress is pulled by contract; a session id
  would become a second credential-like handle and server memory). The SDK's host allowlist as the guard (needs host
  lists for remote bindings; bearer-only authentication already defeats rebinding). Binding the token at `initialize`
  as stdio binds it at start (stateless mode has no session; per-request resolution is simpler and revocation-correct).
  A transport value `mcp_http` (would allow a tool on one MCP carrier only). OAuth now (an authorization server and
  audience-bound tokens are a package of their own; Q4).
- **D2.** The branch in the revision document (a revision's hash would depend on its branch; violates C7). A
  `branches` table (store-schema bump and a migration of every project, when `refs` is already a name-to-revision map).
  A separate `commit_to_branch` operation (duplicates `commit_change`). Merge and rebase (a three-way merge of
  flowsheet documents needs conflict semantics for specifications and connections, a design question with no demand;
  promotion by `restore_from` covers the need). `move_branch` (delete then create). A branch in job requests (a job
  must name an immutable revision for replay).
- **D3.** `resume_of: <job_id>` over the experiment cache (no capability gained; a second address F7 would remove).
  Per-start resume of `optimize` now (it is F7's incumbent checkpoint, and changes OPT D8's interrupted-job outputs).
  Mid-solve iterate resume (F7 D14's checkpoint body; ADR 0020 D7).
- **D4.** Offering the seven benchmark-registered policies (their constructors live in tests and harnesses and each needs
  route qualification; a project copy of an offered policy covers the need; Q6). Inline policy documents in
  `solve_body` (every request carries kilobytes; no reuse or discovery). Overrides on a base policy (unnamed policies
  whose identity is base plus patch, with a merge rule per member). Policies in `project-policy.json` (mixes
  authorization with numerics, and would demand the `policy` right). A new table (store-schema bump).
- **D5.** A seventh right `administer` (departs from blueprint §11.3). No switch (widens existing `policy` grants
  silently). Allowing writes on a no-TLS remote server (a sniffed `policy` token could mint credentials that survive
  its own revocation; Q3). Keeping the token in the ledger for replay (breaks "only its SHA-256 is stored"). In-band
  executor settings (host resources, not the project's collaborators).

## Migration proof

No stored record, run identity or released number moves: F0 (`scripts/corpus_identity.py --check`, M1 50/50 … M9
42/42) PASS after every work order. The store schema stays `t07-store-v1` (branches are `refs` rows, policies are
job-less artifact rows). Every existing ChangeSet normalizes to the same bytes and `request_sha256` (E-X06-7). Every
existing policy file keeps its `policy_sha256` (E-X06-16). `get_project` of a project without registered policies is
byte-identical (E-X06-15). The only moved pin is the served MCP tool list, by registration and decomposition (D6).

**Callers migrated (no shims):** `bindings.mcp.build_server(app)` → `build_server(caller)`: `serve_stdio`, the MCP
tests and the conformance `McpClient`. `ProjectStore.commit_revision(…)` gains required keyword `ref`:
`RevisionService.commit_change` and tests calling the store directly (ported in a test commit before the step).
`admission.resolve_policies(route, body)` gains `project_policies`: validation-service admission and
`jobs/runner.py`'s `resolve` stage. `authz._change_policy` → `change_policy(store, …, actor, request_sha256)`: the CLI's
`grant`, `revoke`, `ambient` paths. `Change` and `ProjectPolicy` each gain one optional field omitted from their
documents at its default. `Dispatchable` extends the three new protocols; `LocalApplication` delegates one line per
method (ADR 0076 I-12d).

## Exit tests (F0 PASS implied on each)

*MCP over HTTP (D1)*
- **E-X06-1** The conformance suite runs a sixth client, `McpHttpClient` (the SDK's streamable-HTTP client against
  the ASGI app, bearer header), compared with the Python process reference as `McpClient` is; every step's outcome
  equal after the suite's existing `stable` projection.
- **E-X06-2** `tools/list` over HTTP equals stdio's in canonical bytes, and its digest equals the registered served
  digest.
- **E-X06-3** Guard table, each with status, body code and **zero calls into the session manager** (spy): no header,
  malformed, unknown, expired, revoked token → 401 + `WWW-Authenticate: Bearer`; foreign `Origin` → 403
  `origin_refused`; allowed and absent `Origin` → passes; `GET`, `DELETE` → 405 `Allow: POST`; body of
  `MAX_BODY_BYTES + 1` (declared and streamed) → 413; `initialize` without a token → 401.
- **E-X06-4** Caller isolation: 50 concurrent `tools/call` requests alternating two tokens with different rights on
  one server; every result matches its own token's authorization and every audit row names its own principal.
- **E-X06-5** A token revoked through the CLI while the server runs is refused 401 on its next HTTP request; the token
  appears in no captured log line of the run.

*Branches (D2)*
- **E-X06-6** Lifecycle: create at a revision; commit on the branch advances it and leaves `head` unchanged; stale
  `expected_revision` → `conflict` with the branch tip; `expected_revision: null` on a branch → `conflict`; create of an
  existing name → `conflict`; delete with a stale tip → `conflict`, with the tip → `deleted`; `head` reserved on
  create, delete and as a name; unknown branch → `not_found branch_not_found`; every revision stays readable after its
  branch is deleted; `list_branches` order and paging over 120 branches with `limit` 50.
- **E-X06-7** Hash invariance: a golden list of `(normalized request bytes, request_sha256)` for every JSON file under
  `tests/fixtures/` that validates against `change-set.schema.json`, generated at `main` `aa5822ac` before WO2 and
  committed, is reproduced exactly (the list is non-empty; the test fails on zero files); `branch:
  "head"` and an absent `branch` give the same bytes.
- **E-X06-8** Races (20 trials each, threads and two processes): two commits on one branch from one tip → one
  `committed`, one `conflict`; two creates of one name → one `created`, one `conflict`; a branch commit racing a head
  commit → both succeed and each moves only its ref.
- **E-X06-9** C7: identical edits committed on `head` and on a branch from the same parent give equal
  `content_sha256`; solving both revisions gives equal `state_sha256` and byte-identical `solution-state.json`; no
  file of either bundle and no stored revision document contains the branch name.
- **E-X06-10** Idempotency: create, delete and branch commit replayed with the same key return the original result
  (also after the branch was deleted); the same key with another body → `idempotency_key_reused`.

*Solve policies (D4)*
- **E-X06-11** Registration: (a) schema-invalid → `invalid_request` with pointer; (b) id without `user.` →
  `solve_policy_id_invalid`; (c) a schema walk lists every open member of `solve-policy.schema.json` and, for each,
  registers a policy with an unregistered value and asserts `solve_policy_invalid` at that pointer (the test fails if
  the walk finds a member with no check); (d) round trip; (e) same id and bytes → `exists`, other bytes → `conflict`,
  the stored file unchanged.
- **E-X06-12** `user.copy` = the `T06-revision-v2` document with only `policy_id` changed: a solve of one corpus
  revision under it gives `state_sha256` and `solution-state.json` bytes equal to the `T06-revision-v2` run, the same
  certificate status and check values, and a manifest `policy_sha256` equal to `user.copy`'s. A difference means some
  path dispatches on the policy's name: STOP and report (Q7).
- **E-X06-13** The `user.copy` bundle reproduces in a fresh project where no policy is registered, with the same
  replay verdict as the `T06-revision-v2` bundle; where the `nlp` extra is present, an `optimize` record under a
  project policy reproduces likewise.
- **E-X06-14** A project policy with solver residual tolerances ×10⁶ looser on a corpus case: the certificate's
  `check_policy_sha256` equals the registered `CheckPolicy`'s, and the run is either verified under it or not
  verified, never verified under other tolerances; an import-graph assertion that `openflowsheet.verify` imports no
  solve-policy type.
- **E-X06-15** `get_project` lists the offered five then the project's by id; for a project with none, its document is
  byte-identical to the pre-X06 fixture; the seven benchmark names keep their exact refusal documents.

*Administration (D5)*
- **E-X06-16** Switch off (default): each write → `unsupported administration_disabled`, policy file bytes unchanged,
  one `refused` audit row; every committed policy fixture parses and re-serializes to the same `policy_sha256`.
- **E-X06-17** Delegation: a case table (rights superset, missing or larger limit under a limited caller, later or
  missing expiry under an expiring caller, `local-owner`, revoke of a more-privileged capability) each refused with
  its code; a generated test of 1000 random (caller, request) pairs: granted implies rights ⊆, limits ≤, expiry ≤.
- **E-X06-18** A granted token authenticates on the next REST, MCP stdio and MCP HTTP call; a replay returns `token:
  null`; the bytes of `project.sqlite3` (and its WAL), the policy file and the captured logs contain neither the token
  nor any `prt_` string.
- **E-X06-19** On an owner marked `serving_remote`, each write → `unsupported administration_remote_refused`, reads
  allowed; on a loopback owner the writes succeed.
- **E-X06-20** An in-band revoke takes effect on the revoked token's next call; 10 concurrent in-band grants plus one
  CLI grant all end in the policy file (no lost update).
- **E-X06-21** Every in-band write leaves exactly one `allowed` audit row naming the caller's principal and capability
  and the effect; CLI audit rows keep their current form (fixture).

*Surface and identity*
- **E-X06-22** `without_x06(served tool list)` equals the digest on `main` at merge; `X06_SERVED_SHA256` pinned; the
  bijection test (OPERATIONS, protocols, `OPERATION_RIGHTS`) passes.
- **E-X06-23** F0 PASS; store schema id still `t07-store-v1`; no file under `schemas/` changes except the additive
  members and `$defs` this ADR names.
- **E-X06-24** The catalogue check: every new `detail.code` has an entry (ADR 0058 C3 CI test).

## New catalogue codes (ADR 0058 C3; all `detail.code` values)

`origin_refused` (input), `branch_name_reserved` (input), `branch_not_found` (input), `solve_policy_id_invalid`
(input), `solve_policy_invalid` (input), `solve_policy_not_found` (input), `administration_disabled` (not supported),
`administration_remote_refused` (not supported), `grant_exceeds_caller` (input), `revoke_exceeds_caller` (input),
`capability_not_found` (input), `capability_exists` (input).

## Work orders (`wp/X06`; one engineer at a time, in this order)

| # | WO | Content and files | Acceptance | Identity | Lane |
| --- | --- | --- | --- | --- | --- |
| 1 | **X06-WO1** MCP over HTTP | `application/bindings/{mcp,mcp_http}.py`; `serve-http` composition in `serving.py`/`cli.py` (and the warning text); `tests/test_x06_mcp_http.py`; sixth client in `tests/test_t07_conformance.py`; import-graph allowlists in `tests/test_t07_w6{a_http,b_mcp}.py`; catalogue entry `origin_refused` | E-X06-1 to 5; existing MCP and HTTP suites green | no (tool list unchanged) | Opus |
| 2 | **X06-WO2** Branches | First commit: the E-X06-7 golden list from `aa5822ac`. Then `store.py` (D2.6), `revision_service.py`, `transaction_types.py` (`Change.branch`), `schemas/change-set.schema.json`, `schemas/application-results.schema.json` (`branch`, `branch_page`, `branch_result`), `contract.py` (`Branches`), `operations.py`, `authz.OPERATION_RIGHTS`, `branch_service.py`, `local.py`, `bindings/descriptions/{list_branches,create_branch,delete_branch}.md` and the `branch` sentence in `commit_change.md`, `preview_change.md`; `.codehealth/config.toml` layers; catalogue entries; `tests/x06_schema_support.py` and the digest pin | E-X06-6 to 10, 22 | no | Opus |
| 3 | **X06-WO3** Solve policies | `orchestrator/policy_validation.py`; `application/{solve_policy_registry,solve_policy_service}.py`; `admission.py`, `validation_service.py`, `jobs/runner.py` (D4.6); `inspection_service.py` (`get_project`); `contract.py` (`SolvePolicies`), `operations.py`, `authz`, `local.py`, descriptions, `application-results` `$defs`; layers; catalogue; digest pin | E-X06-11 to 15, 22 | no | Opus |
| 4 | **X06-WO4** Administration | `authz.py` (`change_policy`, `delegation_refusal`), `policy_types.py` and `schemas/project-policy.schema.json` (`administration`), `administration_service.py`, `service_core.py` (`serving_remote`), `serving.py`/`cli.py` (`project administration on\|off`, the flag), `contract.py` (`Administration`), `operations.py`, `local.py`, descriptions, `$defs`; layers; catalogue; digest pin | E-X06-16 to 21, 22 | no | Opus |
| 5 | **X06-WO5** Close-out | `docs/interfaces-frozen.md` paragraph; ADR 0019 "Amendment 18, pointer to ADR 0078" section; user guide (MCP HTTP client configuration with the bearer header, branches and promotion, project solve policies, the administration switch and its remote refusal, D3's sentence); `CHANGELOG.md`; `evidence/X06/<commit>/manifest.json` (`tested`, the commands run); F0 on the branch | E-X06-22 to 24; manifest validates | no | Sonnet |

Each WO commits its tests before or with its code, runs the tests it touches and F0, and stops at about 150k context
with what is complete committed and where it stopped written in the X06 decisions file.

## Risks and open questions (each with a default)

1. **Q1 (user's preference): defer job resume to F7 D14, 0.8 (D3).** *Default: accept.* If rejected, the smallest
   honest 0.6 delivery is still none: the alternative designs fix F7's structure (D3 reason 3). Reversible by: a
   follow-up X06-R package on D14.
2. **Q2 (user's preference, security): in-band administration off by default, operator switch per project (D5.1).**
   *Default: as designed.*
3. **Q3 (user's preference, security): refuse in-band writes on a server bound beyond loopback, no override in 0.6
   (D5.3).** *Default: refuse.* A TLS proxy forwarding to a loopback binding is allowed. Reversible by: an override
   flag in a later ADR.
4. **Q4 (fact): which MCP clients must reach `/mcp`, and can they send a static `Authorization` header?** Claude Code
   and SDK clients can; clients that accept only OAuth-protected remote servers cannot. *Default: static bearer; OAuth
   (RFC 9728 metadata, an authorization server) is a later package.* Experiment: connect each target client to a
   loopback `serve-http` with the header configured. Risk meanwhile: an OAuth-only client probes
   `/.well-known/oauth-protected-resource`, gets 404 and reports an error.
5. **Q5 (user's preference): registering a solve policy needs `draft`, not `policy`.** *Default: `draft`* (like
   `register_record`; registration changes nothing until a job with `execute` names it; wall-time limits bound use).
6. **Q6 (user's preference): the seven benchmark-registered policies stay `unsupported`.** *Default: yes*;
   `get_solve_policy` of an offered policy plus `register_solve_policy` is the route to variants.
7. **Q7 (fact): does any path dispatch on a policy's name rather than its content?** E-X06-12 decides. *Default:
   assume not; on a difference WO3 stops and reports to the design lane.*
8. **Q8 (fact): merge order with F2.** F2-WO6 touches the application's revision dispatch and may move the served
   tool list. *Default:* WO2 starts after F2-WO6 is on `main` if it is there first, else F2 rebases; whichever merges
   second decomposes its digest onto the first's (D6).
9. **Q9 (fact): the SDK's stateless behaviour for `GET`, batches and Accept headers.** *Default:* the guard answers
   `GET`/`DELETE` itself; WO1's tests pin whatever 1.30.0 answers to a batch and a wrong Accept, and a refusal there is
   acceptable as long as nothing is executed.
10. **Pre-existing window, not changed:** the policy file is replaced inside the write transaction before `COMMIT`; a
    crash between the two leaves a changed policy without its audit row (as for today's CLI). *Default: document it;
    no change in X06.*
11. **Thread pool:** MCP HTTP calls and REST handlers share anyio's default limiter (40); long `wait_job` calls (≤ 30 s)
    can delay other requests. *Default: unchanged; measured only if a user reports it.*

## What this ADR does not establish

Resume of any kind (F7 D14). TLS, OAuth, rate limiting, CORS. Branch merge, rebase or move. Branch-aware views in
the web shell. Offering the benchmark-registered policies. In-band `install`, `publish`, executor settings or project
creation. Any change to `CheckPolicy`, the verifier, a solver default or a registered policy.

## Edits other documents need (the orchestrator applies them)

`docs/decision-register.md`: R-1071 (this ADR) and a status line on R-110 ("lifted by X06 for MCP over HTTP, branches,
further solve policies and in-band administration; resume stands until F7 D14"); `docs/roadmap/roadmap.md` X06 row
(resume moves to the F7 line, Q1); `target-architecture.md` §4: X06's dependency row ("resume of long jobs through F7") reads "resume via F7 D14 (0.8);
the rest in 0.6".

## X06 ruling round R1 applied (`docs/X06_DECISIONS.md`, "Design-lane rulings R1", 2026-11-27)

Status stays Accepted (R-1071). Two clarifications, recorded in the decision register; no section above is edited
and nothing accepted is changed.

| Of | Clarification | Register |
| --- | --- | --- |
| D4.2, E-X06-13; T07 W3-Q4 | A bundle whose `solve-path.json` requests a `user.` id (D4.1, matched whole) is judged against its own `solve-policy.json`: the route known; the document indexed, intact and rebuilt; its `policy_id` equal to the request; its `policy_sha256` equal to the manifest's. The project store is never consulted. Every other request is judged as before. A coherent substitution of a `user.` policy is beyond integrity; replay and the certificate stay the guard. | R-1074 |
| D4.3(d), D4.5; R-088 Q26 | `register_solve_policy`'s `policy/scales`, a map of registered quantity kind to a positive constant, is the one numeric map R-088 Q26 admits in the `SolvePolicies` requests, by that full path and only there; the request's 40 numeric scalars are pinned by full path (`tests/test_t07_q26.py`). | R-1075 |
