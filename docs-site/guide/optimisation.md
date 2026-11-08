# Optimising a revision

OpenFlowsheet optimises a stored revision over some of its own fixed specifications: you name the
decisions, an objective and optional constraints in an **optimisation request**; Ipopt searches;
and every candidate it returns is solved again as an ordinary simulation and checked before it is
called verified. The result is a report, a record of every file the search and the checks wrote,
and a change set that turns the candidate into a new revision when you commit it.

The normative text is ADR 0071 and the OPT design note, linked from [Design](../design.md).

## What you need

- The `nlp` extra in its **audited** environment (Pyomo, cyipopt and Ipopt; see
  [Studies and optimisation](studies.md#the-nlp-extra)), on **Linux x86-64**. Elsewhere — the
  default install, aarch64, macOS — validation and submission are refused `unsupported`
  (`nlp_solver_unavailable`) before anything is read, and the library returns an `UNSUPPORTED`
  report. Replaying a record needs neither Ipopt nor the extra, on any supported platform.
- A revision that solves on the `revision_eo` route (one equation-oriented region). A coupled
  (sequential-modular, torn) flowsheet and a `legacy_eo` document are refused
  `UNSUPPORTED` with `OPTIMIZATION_ROUTE_UNAVAILABLE`.

## The request

A JSON document (`schemas/optimization-request.schema.json`):

```json
{
  "request_format": "openflowsheet-optimization-request-v1",
  "problem_id": "boiler-gwp",
  "decisions": [
    {"specification_id": "SPEC-B-T", "unit": "K", "lower": 640.0, "upper": 720.0, "scale": 100.0}
  ],
  "objective": {
    "sense": "minimize",
    "scale": 0.01,
    "expression": {"linear": {"assessment:impact.climate_change_test.rate": 1}}
  },
  "constraints": [
    {"id": "W-net-min", "lower": 1.56, "upper": null,
     "expression": {"linear": {"T.W": -1e-4, "P.W": -1e-4}, "text": "(-T.W - P.W)/1e4"}}
  ],
  "starts": {"include_revision": false, "explicit": [[650.0]]},
  "assessment": {"...": "an E01 assessment document, when the objective names assessment outputs"}
}
```

- **Decisions** are `role: fixed` specifications of the revision, in the internal SI unit of their
  kind, each with a finite box and a scale. A specification that is not continuous, a unit that is
  not the internal one, or an open box is refused before any solve.
- **Expressions** are `constant + Σ linear + Σ quadratic` over state variable ids,
  `decision:<specification_id>` and `assessment:<output_id>` (cost and LCA outputs of the
  request's `assessment`, see [Cost estimation and LCA](assessment.md)). The objective is divided
  by its `scale`; a constraint's expression is **declared scaled** — write it at order one, as
  above.
- **Starts**: the revision's own values (`include_revision`, default true), then `explicit` points,
  then `halton` points of the box; 1 to 32 in all. Each start is solved and certified before Ipopt
  sees it, and holds that start's phase regime.
- **Options**: `max_iter` (default 500) and `max_wall_time_s` (default 120) per start. Only the
  limited-memory Hessian is supported.

`validate` with `task: "optimization"` runs the static checks (codes `OPT.<CODE>`, for example
`UNKNOWN_DECISION`, `BOUNDS_UNDECLARED`, `START_OUTSIDE_BOUNDS`, `ASSESSMENT_OUTPUT_UNKNOWN`) and
answers `READY_FOR_OPTIMIZATION` when nothing stops the run. It never solves. With an assessment,
`ASSESSMENT_OUTPUT_UNKNOWN`, `ASSESSMENT_PARAMETER_STRUCTURAL` and `ASSESSMENT_PARAMETER_DECISION`
are `WARN` ("not established statically"): the assessment program is planned at a solved state, so
these are judged at the first certified start.

## Running it

**CLI**

```bash
openflowsheet validate rev.json --task optimization --request request.json
openflowsheet optimize rev.json --request request.json --out record/
openflowsheet replay record/ --rerun
```

`optimize` writes the record and exits 0 only when the report is `KKT_POINT_VERIFIED` (1 for any
other report). A request with problems prints an `invalid_request` error and writes nothing.

**Python**

```python
from pathlib import Path

from openflowsheet.application.policies import DEFAULT_POLICY_ID, resolve_policy
from openflowsheet.application.revision_routes import REVISION_ROUTES
from openflowsheet.studies.nlp.revision import optimize_revision
from openflowsheet.verify.certificate import CheckPolicy

outcome = optimize_revision(
    document,
    request,
    directory=Path("record"),
    routes=REVISION_ROUTES,
    solve_policy=resolve_policy(DEFAULT_POLICY_ID, "revision_eo"),
    check_policy=CheckPolicy(),
)
report = outcome.report.as_document()
```

Through the application (`LocalApplication`), as over HTTP and MCP:

| Step | Python | HTTP | MCP tool |
| --- | --- | --- | --- |
| Check | `app.validate(revision_id, "optimization", optimization=request)` | `POST /v1/revisions/{revision_id}/validate` | `validate_revision` |
| Run | `app.submit_job(...)` with operation `optimize`, body `{"revision_id", "request", ...}` | `POST /v1/jobs` | `submit_job` |
| Result | the job result's `optimization` report; record files are artifacts `<job_id>:optimization/<path>` | `/v1/jobs/...`, `GET /v1/artifacts/{artifact_id}` | `wait_job`, `get_job_result`, `get_artifact` |
| Replay | `app.reproduce(<record>, ReplayPolicy(rerun=True))` | — | — |

The job's stages are `resolve`, `starts`, `optimize`, `record`; it can be cancelled, and its
`wall_time_s` budget bounds the whole search. A cancelled job keeps the start bundles already
written and writes no report.

## What "verified" means

Each start ends in one classification, and the report's status is the best of them:

| Status | Meaning |
| --- | --- |
| `KKT_POINT_VERIFIED` | V1–V5 passed at the candidate (below) |
| `NOT_VERIFIED` | Ipopt claimed a solution that the re-solved simulation refuted (a failing V check is named) |
| `INFEASIBLE_REPORTED` | Ipopt reported the problem locally infeasible |
| `SOLVER_FAILED` | anything else (iteration or time limit, an evaluation error) |
| `UNSUPPORTED` | refused before any solve: no audited solver, an unsupported route, a static check |

The checks at a candidate, all independent of Ipopt's own convergence test:

- **V1** the candidate document (the revision with the decisions written in) solved cold by the
  ordinary simulation path, its certificate `VERIFIED` (or, at a phase boundary, see below);
- **V2** Ipopt's state equals that re-solved state within a gross tolerance;
- **V3** the box, your constraints, the assessment's admissibility rows and the phase rows hold on
  the re-solved state;
- **V4** every unit is in the phase regime the start held, with margin;
- **V5** stationarity: the objective gradient is a non-negative combination of the active
  constraints' gradients, from exact sensitivities of the re-solved state (not Ipopt's
  multipliers), with linearly independent active gradients;
- **V6** the objective and constraint values, recomputed on the re-solved state;
- **V7** the assessment's held cost and impact regimes (size ranges, utilities) still hold.

`KKT_POINT_VERIFIED` is **local stationarity of the held-regime problem**, numerically verified. It
is not a global optimum, nor a certified local minimum (second-order conditions are not
assessed), and it is not empirical validation. `distinct_local_solutions` counts the distinct
verified candidates across starts. The report's `candidate.change_set` commits the candidate as a
new revision; a solve of that revision reproduces V1's certificate.

A record replays (`replay --rerun`, `reproduce`): integrity of every file, every bundle
re-solved, V1–V7 recomputed and compared under the registered numerical policy, and the
classification recomputed. A change of the active set within 1e-9 relative of its threshold is
listed as `verdict_changed_near_threshold`, not as a mismatch.

## Declared limitations

- **Platform and route**: optimising needs the audited `nlp` environment on Linux x86-64 and the
  `revision_eo` route; coupled flowsheets and `legacy_eo` documents are refused.
- **Phase regimes are held.** Each start keeps its phase regime; a candidate whose units changed
  regime is `NOT_VERIFIED` (`PHASE_REGIME_CHANGED`). An optimum exactly at a bubble or dew point of
  a single-phase unit is found and verified on the **phase-boundary** form: the report flags it
  (`phase_bounds_active`, `regime_note`, `certificate_basis: phase_boundary_form`), and a plain
  solve of the committed candidate certifies `UNVERIFIED` (rank-limited), as the report says in
  advance. A boundary optimum on the two-phase side, or of an **unguarded** regime (one whose
  closure is not the phase margin, listed under `regimes_unguarded`), is `NOT_VERIFIED`; so is a
  candidate in the gap where the certificate is rank-limited but no phase row is active.
- **Which held single-phase splits can start.** On a γ–φ property provider (for example
  `wilson-ig-v2`) a split held LIQUID or VAPOR certifies, and can be a start: the certificate's
  derivative witness leaves the held, exactly zero side undifferenced and lists it (for a held
  VAPOR split, `wilson_dormant_liquid_columns`). Such a split is **unguarded** (its closure is not
  the phase margin): the start record names it under `regimes_unguarded`, and a boundary optimum of
  it is `NOT_VERIFIED`, as above. On `pr-c1-v1` a held single-phase split has no phase margin, and
  the start is refused `REGIME_MARGIN_UNDEFINED`.
- **Boundary optima at a thermal port.** A candidate whose thermal port (declared liquid or
  vapour) sits at its saturation row with a rank-limited certificate fails V1: the
  phase-boundary form covers a guarded LIQUID/VAPOR split's phase row only.
- **Dormant splits.** A revision with a split held `ZERO_FLOW` (a dormant branch) is `NOT_VERIFIED`
  at every candidate today: V4 counts the dormant split, which has no margin, as inside its
  regime's tolerance, although its exact-dormancy check (the attempt signature) holds. This fails
  safe; a fix is queued.
- **Absolute flow thresholds.** A phase row counts as active when |a/N0| ≤ 1e-6 and a two-phase
  split's margin is min(V, L)/N0 ≥ 1e-4, with N0 = 3 mol/s. Both are absolute in flow: on a
  laboratory-scale flowsheet (total flows far below N0) a row can be labelled active at a larger
  relative closure gap, and a two-phase split with min(V, L) < 3e-4 mol/s fails V4. Both errors
  fail safe (a start or candidate is not verified, or a point is labelled a boundary point).
- **Zero flows**: a subsystem of flows that are exactly zero is held at zero per start (`held`);
  when a decision would move one, the subsystem is `unresolved` and those flows are bounded below
  by zero instead. It is all or nothing per start.
- **Assessment regimes** (size ranges, floors, utility choices) are held too: a floor has a zero
  derivative, so capital on a floor does not steer the search.
- **Robustness**: Ipopt runs with fixed options (monotone barrier, limited-memory Hessian). On a
  nearly linear objective whose constraint must become active from inside the feasible region it
  can stall at `max_iter`; another start (for example one on the infeasible side) is the remedy.
  Every such start is reported `SOLVER_FAILED`, never verified.
- Wall-clock members (start times, elapsed seconds) are recorded but are not part of any
  reproducibility claim.
