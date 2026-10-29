# Quickstart

This page solves one flowsheet — a once-through Rankine cycle on IAPWS-95 water — first from
Python, then from the command line, and reads the result and its certificate. The flowsheet is
written out member by member in [Your first flowsheet](../tutorials/first-flowsheet.md); here it is
taken ready-made from the repository's `examples/rankine-cycle.changeset.json`
([download](https://github.com/computational-chemical-engineering/openflowsheet/blob/main/examples/rankine-cycle.changeset.json)),
a change set that creates the revision.

## From Python

```python
import json
from openflowsheet.application.local import LocalApplication
from openflowsheet.application.types import Change

with open("rankine-cycle.changeset.json") as handle:
    change_set = json.load(handle)
change, expected_revision, key = Change.from_change_set(change_set)

with LocalApplication.create("plant") as app:          # a project directory, created empty
    committed = app.commit_change(change, expected_revision, key)
    report = app.validate(committed.revision_id, "simulation")
    print(report.status)                               # READY_FOR_SIMULATION

    run = app.solve(committed.revision_id, "default")
    print(run.outcome, run.verification_status)        # CONVERGED VERIFIED

    bundle = next(o.artifact_id for o in run.outputs if o.kind == "replay_bundle")
    state = json.loads(app.artifact_bytes(f"{bundle}/solution-state.json"))["variables"]
    print(state["T.W"], state["B.Q"])                  # turbine work, boiler duty (W)
```

`solve` runs a job to its end and returns a `RunResult`: whether the job completed, the solver's
outcome, the verifier's verdict, and the artifacts the run registered — the solution certificate,
the run manifest and a replay bundle. The bundle's `solution-state.json` holds every solved
variable by id: stream states as `<stream>.T`, `<stream>.P`, `<stream>.n.<component>`, and unit
works and duties as `<unit>.W`, `<unit>.Q` in watts, positive into the fluid.

## From the command line

The same steps, through the same operations:

```bash
openflowsheet project init plant
openflowsheet api --project plant commit_change --json-file rankine-cycle.changeset.json
openflowsheet api --project plant solve --json '{"revision_id": "rev-000001", "policy_id": "default"}'
```

Each `api` call prints the operation's response as JSON, exactly the document Python's
`as_document()` gives. Read single values out of the run's artifacts with a JSON pointer:

```bash
openflowsheet api --project plant get_artifact \
  --json '{"artifact_id": "job-000001:bundle/solution-state.json", "pointer": "/variables/T.W"}'
openflowsheet api --project plant get_artifact \
  --json '{"artifact_id": "job-000001:bundle/solution-certificate.json", "pointer": "/verification_status"}'
```

The first prints a projection whose `value` is the turbine work, `-15905.09…` W; the second,
`"VERIFIED"`. The exit status of `api` is 0 for a domain result — a failed solve included — and
2–16 for a refusal, by error code (`openflowsheet api --help` lists them).

## Reading the certificate

The certificate lists every check the verifier ran, each with its result and value. Inside the
`with` block above:

```python
certificate = json.loads(app.artifact_bytes(f"{bundle}/solution-certificate.json"))
for check in certificate["checks"]:
    if check["result"] != "pass":
        print(check["id"], check["result"], check["reason"])
print(*certificate["statements"], sep="\n")
```

For this cycle every residual, material and energy balance and specification check passes; the
two independent phase-split checks are `not_applicable`, because the state is a saturated pure
fluid. The statements say what `VERIFIED` means — residuals at registered tolerances, not an
experimental validation or an optimality claim. [Concepts](../guide/concepts.md) explains the four
verdicts.

## Next

- [Your first flowsheet](../tutorials/first-flowsheet.md) builds the revision document yourself.
- The [examples](../examples/index.md) carry this further: a sweep, a refrigeration cycle and a
  distillation column.
