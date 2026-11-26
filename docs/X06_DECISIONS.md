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
