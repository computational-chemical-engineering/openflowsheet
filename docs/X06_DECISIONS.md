# X06 build decisions (append-only)

Build-lane choices for package X06 (application capabilities) that ADR 0078 leaves open. ADR 0078 is Proposed; the
build follows its text as it stands. Where it is silent, the reading taken is the one that changes no existing byte.
Each line: `DECISION`, the choice, the alternative, and where it lives. Each is revertible on its own. Batched for the
package's one design-lane ruling round (CLAUDE.md, agent budget).

## X06-WO1 (MCP over streamable HTTP, D1), 2026-11-26

Files: `src/openflowsheet/application/bindings/{mcp,mcp_http,http}.py`, `application/{serving,cli}.py`,
`messages/catalogue/refusals.yaml` (`origin_refused`) and its generated `docs-site/messages/refusals.md`;
`tests/test_x06_mcp_http.py`, the sixth client (`tests/t07_transport_support.py` `McpHttpClient`,
`tests/test_t07_conformance.py`), the import-graph allowlists (`tests/test_t07_w6{a_http,b_mcp}.py`), and the two
tests that intercepted the CLI's serve call (`tests/test_t07_w5b_cli.py`, `tests/test_m06_wo4_serving.py`).

- **DECISION WO1-1. Composition in `serving`.** `serving.http_application(owner, host, port, ui)` builds what
  `serve-http` serves (REST routes, the shell with `--ui`, `/mcp` through `mcp_http.mount`); `serving.serve_http` runs
  it under `http.run`; the CLI calls `serving.serve_http`. `http.serve` and `web.serve` are unchanged (REST only, REST
  plus shell) and are no longer the CLI's path; the two tests that monkeypatched them to intercept the CLI now patch
  `serving.serve_http` and `http.run`. Alternative: a hook argument on `http.serve`/`web.serve`. Reversible by moving
  the composition back behind those two.
- **DECISION WO1-2. The warning text.** `http.run` gains `warning=NO_TLS_WARNING` (the old text, byte for byte, so
  `http.serve`/`web.serve` print what they printed); `serve-http` passes `serving.HTTP_NO_TLS_WARNING`, the same
  sentence ending "on the REST routes and on /mcp". Alternative: change the one text everywhere.
- **DECISION WO1-3. What the guard is given.** `McpGuard(manager, authenticate, origins=, max_body_bytes=)`: the
  composition passes `owner.authenticated`, `served_origins(host, port, loopback=http.is_loopback(host))` and
  `http.MAX_BODY_BYTES`, so `mcp_http` imports exactly D1.7's list (no `bindings.http`). The bearer grammar is
  repeated; a test holds `mcp_http._BEARER.pattern == http._BEARER.pattern`.
- **DECISION WO1-4. What is audited.** Nothing the guard refuses is audited: 405, 403 and 413 come before the
  credential is read (D1.5's order), and the 401 is not audited on the REST routes either (no principal is known).
  REST audits its 413 because it authenticates first; D1.5 puts the size check first.
- **DECISION WO1-5. The refusal documents.** 405: `invalid_request`, `detail {method, allowed: "POST"}` (REST's
  wrong-method shape) at status 405, `Allow: POST`. 413: `invalid_request`, `detail {pointer: "", limit_bytes}` (REST's
  shape) at 413. 403: `forbidden`, `detail {code: origin_refused, origin}`, the message led by `origin_refused:` because
  the explanation reads its chain from the message (MSG §4.4; as `nlp_solver_unavailable`). 401: REST's two messages,
  `WWW-Authenticate: Bearer`. Each is `project_error`-bounded JSON as REST writes it.
- **DECISION WO1-6. The body is read before the credential.** D1.5 (c) before (d): the guard reads the body whole, up
  to `MAX_BODY_BYTES` (an unauthenticated client can make it buffer at most 1 MiB, as REST does after its check), then
  replays it to the SDK. A client that disconnects mid-body gets no answer. The SDK's own body limit (4 MiB default) is
  left as it is; the guard's comes first.
- **DECISION WO1-7. Served origins are fixed at composition** from `--host` and `--port`. With `--port 0` no browser
  origin matches (fail closed; clients that send no `Origin` are unaffected). Alternative: read the bound port from
  the ASGI scope's `server` per request.
- **DECISION WO1-8. The conformance client.** `McpHttpClient` opens a session per call (`initialize`, then the call):
  the server is stateless, and the SDK client ends its session on any HTTP error status, so the revoked step's 401 is
  read from a recording transport and compared by code and `retryable` (relation `code`, as REST's). `Run` carries the
  client's operation set, which replaces the per-name `SERVED` lookups.

### Q9 measured (`mcp==1.30.0`, stateless JSON mode, past the guard, `tests/test_x06_mcp_http.py`)

Batch (JSON array): 400, JSON-RPC -32602. Accept `text/plain`, or `text/event-stream` only: 406, -32600. Content-Type
`text/plain`: 400, plain text "Invalid Content-Type header". `MCP-Protocol-Version: 1999-01-01`: 400, -32600. Body not
JSON: 400, -32700. Notification: 202, empty body. None of these runs a tool (no refusal audited). A `tools/call`
without `initialize`: 200, runs (stateless: no session requires it). The guard answers `GET`, `DELETE`, `PUT` with 405.
The SDK client negotiates protocol `2025-11-25`; no `Mcp-Session-Id` is sent.

## X06-WO2 (branches, D2), 2026-11-26

- **DECISION WO2-1. E-X06-7's sources.** At `aa5822ac` no JSON file under `tests/fixtures/` validates against
  `change-set.schema.json` (0 of 840), so the ADR's set alone gives an empty list, which E-X06-7 forbids. The golden
  list (`tests/fixtures/x06/change_set_golden.json`, written by `tests/test_x06_change_set_golden.py --write` in a
  detached worktree at `aa5822ac`) takes that set (still empty) plus every `commit_change` and `preview_change` tool
  input recorded in the committed transcripts under `benchmarks/` (V17 c1/c2, OpenIDAES-450): 78 commits and 225
  previews that validate (8 previews do not and are skipped), 303 entries, each normalized as the operation does
  (preview completed by the key `preview`). These are real requests agents sent, which is what the test protects.
  Alternative: synthetic ChangeSet fixtures written now (proves less: they never hashed under the old code in use).
  Reversible by: deleting the transcript source from the module and adding fixtures. ADR divergence, reported.
- **DECISION WO2-2. `ChangeSet` (K06's one-object form) gains `branch` too.** The ADR names only `Change`; without
  it `ChangeSet.from_document` would drop a request's `branch` silently. Its `as_document` goes through
  `Change.as_change_set`, so the omission rule (absent or `"head"`) is one rule. Reversible by removing the field.
- **DECISION WO2-3. Where the branch types and checks live.** `Branch` and `BranchResult` are in
  `transaction_types.py` (contract vocabulary, beside `TransactionResult`; no new layer). `ref_name`,
  `BRANCH_NOT_FOUND` and `BRANCH_NAME_RESERVED` are in `branch_service.py`, which `revision_service` imports (the
  layer order puts `branch_service` below it). `head`'s public spelling is `transaction_types.HEAD_REF`; the store's
  row name stays `store.HEAD`. Alternative: a `branch_types.py` module and layer.
- **DECISION WO2-4. A commit re-assigns an auto id taken by a concurrent commit on another ref.** E-X06-8's "a branch
  commit racing a head commit → both succeed" cannot hold otherwise: both prepare `rev-<next ordinal>` from one
  snapshot, and the second writer found the id taken and returned `rejected revision_id_taken`. `commit_change` now
  prepares again (fresh id, re-validated, outside the lock) when, inside the lock, its ref is still at
  `expected_revision` and only the assigned id was taken; at most `ASSIGNED_ID_ATTEMPTS = 8` times. A caller-named
  id is never re-assigned. Head-only behaviour is unchanged (a taken id there means the head moved: `conflict`, as
  before). Falsifier: with 1 attempt the `mixed` race fails in threads and processes. Escalation item: this is a
  behaviour change of `commit_change` the ADR did not state (it states the outcome).
- **DECISION WO2-5. Preview checks that the branch exists** (`not_found branch_not_found`, audited), and nothing
  else about it (no tip check, as a preview has no head check). Alternative: ignore `branch` in a preview.
- **DECISION WO2-6. Branch writes and their records.** Ledger rows are written only for `created` and `deleted` (as
  `commit_change` ledgers only `committed`); a `conflict` is re-judged on retry. Request hash: `document_sha256` of
  the request as the operation's schema states it (`{name, revision_id, idempotency_key}` /
  `{name, expected_revision, idempotency_key}`). Audit effect `branch:<name>:created|deleted`. Conflicts are not
  audited (as `commit_change`'s). `list_branches`' cursor is `base64url(canonical {"after": <last name>})`, `head`
  standing before every branch. The HTTP `delete_branch` takes `name` from the path only (the body repeating it is
  §11.3's "given more than once").
- **DECISION WO2-7. Description texts.** `commit_change.md` was at its 1500-character bound; the `branch` sentence
  fits by tightening four phrases (no meaning removed; the generated target table untouched; 1499 characters).
  Both changed texts and the three new ones are recorded `pending` in `REVIEW.json`, so
  `test_t08_w2_description_reviews.py` stays red (by its design) until the design lane and the user review the five
  hashes. Pre-X06 copies: `tests/fixtures/x06/pre_x06_descriptions/`.
- **DECISION WO2-8. Surface registration.** `X06_SERVED_SHA256 = 7e8393a5…`; `without_x06` removes the three tools,
  the ChangeSet's `branch` wherever served (also the optimization report's `candidate.change_set` inside
  `get_job_result`'s `outputSchema`, which `$ref`s the ChangeSet) and restores the two texts: the result is F3's
  `f7ec3c94…` exactly. Chain link c_12 (R-1073) in `scripts/m07a_rc.py` onto c_10; R-1073's register entry is on
  `main`, so the c_12 test does not read the register (the c_10 form does); its digests go there at the merge.
- **DECISION WO2-9. The support envelope follows the lifted limitation.** `benchmarks/t08/support_envelope.yaml`:
  U08 no longer names branches (capability, outcome, and its evidence line), and
  `test_u08_a_change_set_naming_a_branch_is_refused_by_its_schema` is removed (its premise is what R-110's lift
  for branches reverses; E-X06-6 tests the name pattern's refusals). The interfaces row lists the three operations
  and reads "thirty-three"; `scripts/t08_support_matrix.py`'s A20 count is 33; `docs/support-matrix.md`
  regenerated. U08 still names MCP over HTTP, which WO1 served: left for WO5 (not this WO's change).
- **DECISION WO2-10. Fixtures.** `scripts/t07_schema_fixtures.py` emits `branch_result`, `branch_page` and `branch`
  from real responses; the two `message_entry` fixtures' catalogue sha256 re-taken for the two new entries (as
  WO1 did for `origin_refused`). R4-G3: `SNAPSHOT_X06` holds the three new rows and the six job rows that embed the
  optimization report's candidate ChangeSet; `without_x06` restores each to its earlier snapshot. The G14 suites
  (CLI, HTTP, MCP) run `x06_schema_support.branches_requests`.
