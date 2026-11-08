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

`solve` and `reproduce` are Python and CLI only; over HTTP and MCP a solve is a job
(`submit_job`, `wait_job`, `get_job_result`). `artifact_bytes` and `list_audit` are not MCP tools.
The full table, with each operation's transports, is generated from the code into the
[operations table](../api/operations.md).

## Authority

The local Python and CLI owner holds every right. A served project acts for a **capability**: a
grant in the project policy with rights (`read`, `draft`, `execute`, `install`, `policy`,
`publish`), budgets and an optional expiry, presented as a bearer token. A request never names its
own identity, a revoked grant stops working on the next call, and every call is audited.

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
