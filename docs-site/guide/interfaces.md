# Interfaces

Python, the command line, HTTP and MCP are four transports of **one** operations table. Each
operation has the same request and response documents on every transport that offers it, the same
authorisation right, and the same refusals.

| Transport | How | Notes |
| --- | --- | --- |
| Python | `LocalApplication.create(path)`, `.open(path)`, `.in_memory()` | in-process; no network round trip |
| CLI | `openflowsheet api --project <dir> <operation> --json …`, and the commands `validate`, `replay`, `streams`, `project` | prints canonical JSON; the exit status encodes the error code |
| HTTP | `openflowsheet serve-http --project <dir>` | `/v1/...` routes; bearer token; loopback unless `--allow-remote`; `--ui` adds the read-only web shell |
| MCP | `openflowsheet serve-mcp --project <dir> --token-file <file>` | stdio; one tool per operation offered on MCP, with reviewed descriptions and output schemas |
| MCP over HTTP | `openflowsheet serve-http --project <dir>`, endpoint `/mcp` | the same tools as stdio, one JSON-RPC message per `POST`; bearer token on every request |

`solve` and `reproduce` are Python and CLI only; over HTTP and MCP a solve is a job
(`submit_job`, `wait_job`, `get_job_result`). `artifact_bytes` and `list_audit` are not MCP tools.
The full table, with each operation's transports, is generated from the code into the
[operations table](../api/operations.md).

## Authority

The local Python and CLI owner holds every right. A served project acts for a **capability**: a
grant in the project policy with rights (`read`, `draft`, `execute`, `install`, `policy`,
`publish`), budgets and an optional expiry, presented as a bearer token. A request never names its
own identity, a revoked grant stops working on the next call, and every call is audited.

## MCP over HTTP

`serve-http` also serves MCP, at the path `/mcp` of the same host and port as the `/v1/...` routes and
the web shell; there is no second command or port. The tool list is the one `serve-mcp` serves. The
server keeps no session: each `POST /mcp` carries one JSON-RPC message and gets one JSON response.
`GET` and `DELETE` on `/mcp` are answered `405`.

A client needs the URL and one header, `Authorization: Bearer prt_…`, with a token from
`openflowsheet project grant` (the same tokens the REST routes accept). The token is checked on every
request, including `initialize` and `tools/list`, so a revoked grant is refused on its next call. How
a client names the URL and the header differs by client; a configuration that takes both reads like

```json
{
  "mcpServers": {
    "openflowsheet": {
      "type": "http",
      "url": "http://127.0.0.1:8765/mcp",
      "headers": { "Authorization": "Bearer prt_…" }
    }
  }
}
```

Only a static bearer token is supported; MCP's OAuth authorization is not implemented. A request with
no valid token is `401`; a request whose `Origin` header names another origin is `403`
(`origin_refused`); a body over 1 MiB is `413`.

`serve-http` binds the loopback interface. Binding another host needs `--allow-remote`, and the server
then prints on standard error that it serves **without TLS** and that bearer tokens cross the network in
clear text, on the REST routes and on `/mcp`. There is no TLS in the server: for remote use put a
TLS-terminating reverse proxy in front of a loopback binding.

## Branches

A branch is a named pointer to a revision, kept in the project store and in no revision document, so
a revision's hash does not depend on the branch it was committed on. `head` is the main line and its
name is reserved. A branch name matches `^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$`.

| Operation | Right | Does |
| --- | --- | --- |
| `list_branches` | `read` | `head` first when it exists, then the branches by name |
| `create_branch` | `draft` | `{name, revision_id, idempotency_key}`: a new branch at an existing revision; an existing name is a `conflict` |
| `delete_branch` | `draft` | `{name, expected_revision, idempotency_key}`: removes the pointer only; every revision stays readable |

`commit_change` and `preview_change` take an optional `branch`. The commit moves only that branch, and
`expected_revision` is compared with that branch's tip; a mismatch is the usual `conflict`. Without
`branch` the main line moves, as before. A job still names a revision, never a branch.

To try a what-if, create a branch at the current revision and commit on it. To **promote** it, commit on
`head` with `restore_from` set to the branch's tip and no edits. There is no merge or rebase.

## Solve policies of a project

Besides the five offered solve policies, a project can register its own: `register_solve_policy` takes
a `solve-policy` document whose `policy_id` starts with `user.` (then a letter or digit and up to 63 of
letters, digits, `_`, `.`, `-`) and needs the `draft` right. The document is checked at registration,
including every value the schema leaves open (initializer chain, linear solver, residual tolerances,
scales, recycle and globalization strings), and an unknown value is refused with its pointer. A
registered policy is **immutable**: the same id with the same bytes answers `exists`, the same id with
other bytes is a `conflict`, and an id is never re-bound. A job names it by id like an offered policy.

`get_solve_policy` (`read`) returns the document, its `policy_sha256` and its origin, `builtin` or
`project`. `get_project` lists the offered policies first, then the project's by id.

A policy changes how the solver searches, never what is accepted: the verifier reads no solve policy.
A run under a project policy carries the policy document in its bundle and replays without the project.
The seven benchmark-registered policy names stay unsupported.

## Administering a project over the interface

By default only the operator changes the project policy, with the `openflowsheet project` commands.
Four operations let a principal holding the `policy` right do it in-band:

| Operation | Does |
| --- | --- |
| `get_policy` | the stored project policy document |
| `grant_capability` | a new grant; its token is in the response and nowhere else |
| `revoke_capability` | removes a grant |
| `set_ambient_pressure` | declares or clears the ambient pressure |

The three writes are **off by default**. The operator switches them on and off for the project:

```
openflowsheet project administration on --project <dir>
openflowsheet project administration off --project <dir>
```

With the switch off they are refused as `unsupported` (`administration_disabled`); `get_policy` is not
gated by it. Whatever the switch, a write is also refused (`administration_remote_refused`) when the
serving process binds a non-loopback interface, and the refusal has no override. A grant cannot exceed
its caller (`grant_exceeds_caller`): rights must be a subset of the caller's, and a limit or expiry the
caller holds needs a limit or expiry no larger. Every write is audited.

## Resuming a job

Resuming an interrupted job is not offered in 0.6. It is planned with the checkpoints of the run
operations (ADR 0066 D14, version 0.8). What exists today: a job resubmitted for an experiment, a
surrogate study or a coupled solve reuses the experiments that completed before, from the project's
experiment store (`test_g5_a_new_key_with_the_same_body_is_a_cache_hit_with_no_new_attempt`,
`test_a_second_solve_serves_both_experiments_from_the_cache`).

## The web shell

`serve-http --ui` serves a browser view of the project — revisions, validation and degrees of
freedom, runs and traces, certificates and failure bundles, streams, comparisons and the audit
history — that uses nothing but the HTTP operations. It edits nothing: Solve and Cancel are its
only actions.

A run's streams screen shows the stream table that `get_stream_table` returns (the same table as
`openflowsheet streams`): for each stream its total and its phases, where the phases come from
(`phase_source`) and whether the state lies near a phase boundary, phase fractions, flows and
enthalpy flows, then the energy summary per unit. Values are in the SI unit the column names. A
value the table does not give is shown as `—` with the reason in plain words, for example a stream
whose phase split could not be computed.
