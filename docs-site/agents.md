# Coding Agents

OpenFlowsheet is built to be driven by coding agents as well as by people. Agents and humans use
the same contract: the same operations, the same documents, the same refusals. Nothing an agent
does bypasses validation, and nothing it reports needs to be taken on trust — every result points
at a certificate and a replay bundle.

## Three ways in

| Door | Best for | Start with |
| --- | --- | --- |
| **Python** | an agent that writes and runs code in a notebook or script | `LocalApplication` ([API](api/local.md)) |
| **CLI** | an agent with a shell | `openflowsheet api --project <dir> <operation> --json …` ([tutorial](tutorials/cli.md)) |
| **MCP** | an assistant that calls tools | `openflowsheet serve-mcp` (needs the `server` extra) |

HTTP (`openflowsheet serve-http`) serves the same operations under `/v1` for a client of your own.

### MCP

The MCP server speaks over standard input and output, and serves one tool per operation that is
offered on MCP (`validate_revision`, `commit_change`, `preview_change`, `submit_job`, `wait_job`,
`get_job_result`, `list_models`, `get_artifact`, `inspect_structure` and the other inspection
tools). Each tool's description is reviewed text that ships with the package, and each result
carries its JSON schema. Solves run as jobs (`submit_job`, then `wait_job`).

Grant the agent a capability with only the rights it needs, and point the client at the server:

```bash
openflowsheet project init plant
openflowsheet project grant --project plant --principal agent --rights read,draft,execute > token.txt
# Claude Code, for example:
claude mcp add openflowsheet -- openflowsheet serve-mcp --project "$PWD/plant" --token-file "$PWD/token.txt"
```

`grant` prints the token once; keep the file private. Authority comes from the credential only:
the server never trusts an identity a request claims, and every call — refused ones included — is
in the project's audit log (`list_audit`).

## Asking an agent to work with OpenFlowsheet

A good request names the process, the property basis, the specifications and what must come back
as evidence. For example:

> Using OpenFlowsheet's MCP tools, build a Rankine cycle on IAPWS-95 water: 1 mol/s, pump to 3 MPa
> (efficiency 0.75), boiler to 673.15 K, turbine to 10 kPa (efficiency 0.85), condenser to
> saturated liquid. Validate it, solve it, and report the thermal efficiency with the run id, the
> verification status and any certificate check that did not pass.

Rules worth giving an agent, because they are how the software is meant to be read:

- **Check the verdict, not just the outcome.** `CONVERGED` is the solver's view; only a
  `VERIFIED` certificate says that every residual, balance and specification check passed at its
  registered tolerance. Report `RELAXED`, `UNVERIFIED` and `FAILED` as such.
- **Treat a refusal as an answer.** `model_unsupported(...)`, `revision_not_ready` or
  `INITIALIZATION_FAILED` mean the request is outside what is supported; they are not obstacles to
  work around by loosening a tolerance or swapping a model silently.
- **Keep the claims apart.** A verified solve is numerical verification of the stated equations
  at the stated state. It is not empirical validation of the property model, and not an optimality
  claim. The certificate's `statements` say so in words an agent can quote.
- **Use `list_models` and `inspect_structure` before guessing.** They state every model's ports,
  parameters and accepted specifications, and the degrees of freedom of a revision.
- **Commit against the head you read.** `commit_change` takes the expected head revision and an
  idempotency key; a conflict is reported, never overwritten.

## For agents working on OpenFlowsheet itself

The repository's `CLAUDE.md` holds the working rules for agents that change the code: the design
authorities, the two-lane protocol, branch and evidence discipline and the scientific conduct the
project holds itself to.

!!! note "What has been measured about agents"
    The agent evidence so far is limited: one pinned model and configuration, over MCP only, on
    registered tasks (see [Limitations and support](guide/limitations.md)).
