# Working from the command line

Every command is a thin wrapper over the same application layer Python uses; nothing is
available on one side and not the other.

## A project

```bash
openflowsheet project init plant          # a directory: project.sqlite3, its policy, jobs/
openflowsheet api --project plant get_project --json '{}'
```

A project holds the revision history, the jobs and their artifacts, and the audit log. The policy
file `plant/project-policy.json` holds the capability grants and the executor's settings.

## Operations

`openflowsheet api --project <dir> <operation>` sends one request document (`--json` or
`--json-file`, `-` for standard input) and prints the response as canonical JSON:

| Operation | What it does |
| --- | --- |
| `commit_change`, `preview_change` | commit (or only preview) a change set |
| `validate` | validate a revision for a task |
| `solve` | run a solve to its end and return the run result |
| `submit_job`, `wait_job`, `get_job`, `get_job_result`, `list_jobs`, `list_job_events`, `cancel_job` | run work as jobs and follow their events |
| `get_project`, `list_models`, `list_revisions`, `get_revision`, `diff_revisions`, `inspect_structure` | inspect the project, the model registry and revisions |
| `get_artifact`, `artifact_bytes` | read a run's artifacts, projected by JSON pointer or as raw bytes |
| `reproduce` | replay a bundle |
| `list_audit` | read the audit log |

The request and response schemas are in the repository's `schemas/` directory and in the
[operations table](../api/operations.md).

## Validating a document before committing it

```bash
openflowsheet validate revision.json --json
```

checks a `ProcessRevision` file (YAML or JSON) without a project.

## A run's stream table

```bash
openflowsheet streams --project plant --job job-000001             # text, SI units
openflowsheet streams --project plant --job job-000001 --format csv --output streams.csv
openflowsheet streams plant/jobs/job-000001/bundle --format json   # a bundle directory
```

prints each stream's temperature, pressure, flows, composition, vapour fractions, enthalpy,
entropy and density, then each unit's duty, work and energy balance and the flowsheet's overall
balance. `--format` is `text` (the default), `json` (the `stream-table-v1` document, as the
`get_stream_table` operation returns it) or `csv` (one row per stream total and per phase). A value
that cannot be given is `-` with a footnote naming its reason. The table is computed from the run's
bundle on every call and stored nowhere; a refusal exits with its error code's number, as `api`
does. See the [stream table guide](../guide/stream-table.md).

## Replaying a run

A replay bundle carries everything a run needs to be repeated. Inspect it, or solve again and
compare:

```bash
openflowsheet replay plant/jobs/job-000001/bundle
openflowsheet replay --rerun plant/jobs/job-000001/bundle
```

The report says how the rerun compares (`MATCH`, bitwise or within the run's numerical policy) and
why an exact comparison was not possible — for example when the BLAS thread counts were not pinned
(`OPENBLAS_NUM_THREADS`, `OMP_NUM_THREADS`, `MKL_NUM_THREADS`).

## Serving the project

With the `server` extra, the same operations are served over HTTP and MCP. Both need a capability
token, granted once:

```bash
openflowsheet project grant --project plant --principal me --rights read,draft,execute  # prints a token once
openflowsheet serve-http --project plant --ui      # http://127.0.0.1:8765/v1 and the web shell at /ui/
openflowsheet serve-mcp --project plant --token-file token.txt
```

The HTTP server binds to loopback unless `--allow-remote` is given. See
[Interfaces](../guide/interfaces.md) and [Coding Agents](../agents.md).
