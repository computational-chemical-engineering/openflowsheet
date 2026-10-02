"""T02's part of the cross-platform identity (A02, A34), included by `k05_structural_identity.py`.

Two documents. **`r0`** — floats-free, as K05's identity document must be — is compared for
equality across the CI pair: the `ExecutionPlan` of every
registered SYN-001 plan (the whole plan is R0, ADR 0009 D1), and, for every registered recycle case,
the recycle's decisions — per event its kind, iteration, outcome, rejection reason and ADR 0009 D3's
R0 fields (`depth_used`, both drop counts, `beta_substitution`, `oscillation_flag`,
`restart_reason`, `restart_count`, `merge_into_eo`). **`floats`** carries `kappa_2` and `gamma_inf`
per `acceleration` event, the two R1/R2 floats, compared under ADR 0007 D2 with their registered
floors (`1.0` and `1e-12`) by `openflowsheet.run.compare.differences` — never for equality.
They are written to their own artifact (`--floats-out`), because the identity document holds no
float at all.

Usage:
    PYTHONPATH=. .venv/bin/python scripts/t02_identity.py --floats-out t02-floats.json

The manufactured maps are built from `benchmarks/t02/reference_values.yaml`, as the tests build
them: `G(t) = t* + A (t − t*) + γ q(t − t*) / S`.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt
import yaml

from openflowsheet.application.binding import Binding, bind_revision, structural_inputs
from openflowsheet.compiled import EvaluationContext
from openflowsheet.graph.analysis import analyse
from openflowsheet.graph.trace import trace_declaration
from openflowsheet.models.syn001.flowsheet import Syn001Flowsheet
from openflowsheet.numerics.anderson import RecyclePolicy, solve_recycle
from openflowsheet.numerics.newton import Evaluation, Problem
from openflowsheet.numerics.scaling import Scaling
from openflowsheet.orchestrator.budget import PropertyMeter
from openflowsheet.orchestrator.execution import (
    ExecutionPlan,
    build_execution_plan,
    declaration_identity,
    specification_regions,
)
from openflowsheet.orchestrator.executor import execute_plan
from openflowsheet.orchestrator.tear import Syn001TearProblem
from openflowsheet.orchestrator.trace import RecyclePolicy as Recycle
from openflowsheet.orchestrator.trace import SolveEvent, SolvePolicy, Trace
from openflowsheet.run.identity import execution_plan_r0
from openflowsheet.thermo.syn001 import Syn001Provider

ROOT = Path(__file__).resolve().parent.parent
TOLERANCE = 3.1e-8
Vector = npt.NDArray[np.float64]

#: ADR 0009 D3's R0 fields, plus the K03 fields that say what a decision was.
R0_FIELDS = (
    "kind",
    "attempt",
    "iteration",
    "outcome",
    "rejection_reason",
    "trial_status",
    "step_index",
    "step_count",
    "depth_used",
    "columns_dropped_condition",
    "columns_dropped_coefficient",
    "beta_substitution",
    "oscillation_flag",
    "restart_reason",
    "restart_count",
    "merge_into_eo",
    "merge_unsupported",
)


def _floats(values: Sequence[Any]) -> Vector:
    return np.array([float(value) for value in values], dtype=np.float64)


def _problem(
    g_map: Callable[[Vector], Vector], scale: Sequence[float], *, bounded: bool
) -> Problem:
    n = len(scale)
    ids = tuple(f"t{i}" for i in range(n))
    rows = tuple(f"R{i}" for i in range(n))

    def residual(t: Vector) -> Evaluation:
        if bounded and bool(np.any(t < 0.0)):
            return Evaluation(status="invalid_trial_state", message="negative component flow")
        return Evaluation(status="ok", values=tuple(float(v) for v in g_map(t) - t))

    return Problem(
        variable_ids=ids,
        row_ids=rows,
        residual=residual,
        jacobian=lambda t: np.zeros((n, n)),
        scaling=Scaling(
            column=dict(zip(ids, scale, strict=True)), row=dict(zip(rows, scale, strict=True))
        ),
        row_tolerance=dict.fromkeys(rows, TOLERANCE),
        lower_bounds=dict.fromkeys(ids, 0.0) if bounded else {},
    )


def _rec(case: Mapping[str, Any], gamma: float) -> tuple[Problem, Vector]:
    a = np.array([_floats(row) for row in case["A"]])
    t_star = _floats(case["t_star"])
    s = float(case["scale_mol_per_s"])

    def g(t: Vector) -> Vector:
        d = t - t_star
        return t_star + a @ d + gamma * np.array([d[1] * d[2], d[2] * d[0], d[0] * d[1]]) / s

    start = case["start"]
    t0 = _floats(start) if isinstance(start, list) else float(start) * t_star
    return _problem(g, [s] * 3, bounded=True), t0


def _recycle_cases(ref: Mapping[str, Any]) -> dict[str, tuple[Problem, Vector, RecyclePolicy]]:
    cases: dict[str, tuple[Problem, Vector, RecyclePolicy]] = {}
    for name, case in ref["cases_rec"].items():
        for gamma in (0.0, 0.1):
            problem, t0 = _rec(case, gamma)
            cases[f"{name} gamma={gamma}"] = (problem, t0, RecyclePolicy())
    div = ref["cases_auxiliary"]["RCY-DIV"]
    a = np.array([_floats(row) for row in div["A"]])
    t_star = _floats(ref["cases_rec"]["REC-01"]["t_star"])
    cases["RCY-DIV depth=0"] = (
        _problem(lambda t: t_star + a @ (t - t_star), [3.0] * 3, bounded=False),
        _floats(div["start"]),
        RecyclePolicy(depth_max=0),
    )
    cases["RCY-STALL"] = (
        _problem(lambda t: t + 1.0, [3.0] * 3, bounded=False),
        np.zeros(3),
        RecyclePolicy(),
    )
    cases["RCY-COEF"] = (
        _problem(lambda t: t + 1.0 + 1e-6 * t, [1.0], bounded=False),
        np.zeros(1),
        RecyclePolicy(),
    )
    return cases


def _uniform_scale(problem: Problem) -> float:
    """The recycle's scale `S`. Every registered tear is scaled uniformly (one kind, one `S`), so
    `‖f̂_k‖∞ = residual_inf_unscaled / S`; anything else is refused rather than approximated."""
    scales = {problem.scaling.column[name] for name in problem.variable_ids}
    if len(scales) != 1:
        raise ValueError(f"a non-uniform tear scale {sorted(scales)} has no single S")
    return float(scales.pop())


def _project(
    events: Sequence[SolveEvent], scale: float | None = None
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    r0: list[dict[str, Any]] = []
    floats: list[dict[str, Any]] = []
    for event in events:
        document = event.as_document()
        projected = {name: document[name] for name in R0_FIELDS if name in document}
        if "beta_substitution" in projected:
            # One of two registered constants (1 and 0.5), compared exactly; written as its
            # shortest decimal so that the R0 document stays free of floats (K05's rule).
            projected["beta_substitution"] = repr(projected["beta_substitution"])
        r0.append(projected)
        if event.kind == "acceleration":
            if scale is None:
                raise ValueError("an acceleration event needs the recycle's scale")
            # ADR 0007 D2.2's comparability window selects on the scaled residual at the event.
            floats.append(
                {
                    "kappa_2": document["kappa_2"],
                    "gamma_inf": document["gamma_inf"],
                    "residual_inf_scaled": event.residual_inf_unscaled / scale,
                }
            )
    return r0, floats


def _tear_scale(flowsheet: Syn001Flowsheet) -> float:
    return _uniform_scale(Syn001TearProblem(flowsheet).as_newton_problem())


def _flowsheet() -> Syn001Flowsheet:
    return Syn001Flowsheet(
        provider=PropertyMeter(Syn001Provider()),
        context=EvaluationContext(
            model_version="t02", constants_sha256="0" * 64, phase_signature=None
        ),
    )


def _plan(
    flowsheet: Syn001Flowsheet, policy: SolvePolicy, binding: Binding | None = None
) -> tuple[ExecutionPlan, Any]:
    if binding is None:
        spec, graph, row_units = structural_inputs(flowsheet)
        specification_ids: Mapping[str, str] = {}
    else:
        spec, graph, row_units = binding.spec, binding.graph, binding.row_units
        specification_ids = binding.specification_ids
    model_version, constants = declaration_identity(spec)
    identity = {
        "row_units": row_units,
        "specification_ids": specification_ids,
        "model_version": model_version,
        "constants_sha256": constants,
    }
    declaration = trace_declaration(spec, **identity)
    report = analyse(spec, graph, **identity)
    regions = (
        specification_regions(
            declaration,
            graph,
            report,
            freed=binding.freed,
            promoted=binding.promoted,
            missing_guesses=binding.missing_guesses,
        )
        if binding is not None and binding.freed
        else ()
    )
    plan = build_execution_plan(
        spec=spec,
        declaration=declaration,
        graph=graph,
        report=report,
        manifests={unit.unit_id: unit.manifest() for unit in flowsheet.units()},
        policy=policy,
        specifications=regions,
    )
    return plan, spec


def identity() -> dict[str, Any]:
    ref = yaml.safe_load((ROOT / "benchmarks" / "t02" / "reference_values.yaml").read_text())
    r0: dict[str, Any] = {"plans": {}, "recycle": {}, "runs": {}}
    floats: dict[str, Any] = {"recycle": {}, "runs": {}}

    for name, (problem, t0, policy) in _recycle_cases(ref).items():
        trace = Trace()
        solve_recycle(problem, t0, policy=policy, trace=trace)
        r0["recycle"][name], floats["recycle"][name] = _project(
            trace.events, _uniform_scale(problem)
        )

    # Plans: the tear, EO and Anderson plans of the nominal variant, and A02's.
    for method in ("auto", "eo", "anderson"):
        policy = SolvePolicy(
            policy_id=f"T02-{method}",
            residual_tolerances={},
            scales={},
            recycle=Recycle(method=method),  # type: ignore[arg-type]
        )
        flowsheet = _flowsheet()
        plan, spec = _plan(flowsheet, policy)
        r0["plans"][f"SYN-001-nominal {method}"] = execution_plan_r0(plan.as_document())
        run = execute_plan(plan=plan, flowsheet=flowsheet, spec=spec, policy=policy)
        r0["runs"][f"SYN-001-nominal {method}"], floats["runs"][f"SYN-001-nominal {method}"] = (
            _project(run.trace.events, _tear_scale(flowsheet))
        )

    policy = SolvePolicy(policy_id="T02", residual_tolerances={}, scales={})
    for case_id in ("SYN-001-A02-360", "SYN-001-A02-355-liquid-guess"):
        document = yaml.safe_load(
            (ROOT / "benchmarks" / "syn001" / "cases" / f"{case_id}.yaml").read_text()
        )
        binding = bind_revision(document)
        assert isinstance(binding, Binding), case_id
        plan, spec = _plan(binding.flowsheet, policy, binding)
        r0["plans"][case_id] = execution_plan_r0(plan.as_document())
        run = execute_plan(plan=plan, flowsheet=binding.flowsheet, spec=spec, policy=policy)
        r0["runs"][case_id], floats["runs"][case_id] = _project(
            run.trace.events, _tear_scale(binding.flowsheet)
        )

    return {"r0": r0, "floats": floats}


def main() -> int:
    import argparse
    import json

    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--floats-out", type=Path, required=True)
    arguments = parser.parse_args()
    arguments.floats_out.write_text(
        json.dumps(identity()["floats"], indent=1, sort_keys=True, allow_nan=False) + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
