"""T02 §4.4: the merge edge — a stalled Anderson loop re-solved, once, as its EO region.

The recycle halves of A14–A17 (the closures, restarts and drops) live in `test_t02_recycle.py`;
these are their merge halves, plus A32 and MERGE-U. For a manufactured map the loop is the map
alone, so its region is `R(t) = G(t) − t` itself — the loop's rows and nothing else — solved by
K03's Newton with the exact Jacobian `∂G/∂t − I` from the best iterate.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt
import pytest
import yaml

from openflowsheet.numerics.anderson import RecyclePolicy
from openflowsheet.numerics.newton import Evaluation, NewtonResult, Problem, solve_newton
from openflowsheet.numerics.scaling import Scaling
from openflowsheet.orchestrator.merge import ConvergeResult, converge_with_merge
from openflowsheet.orchestrator.trace import Counters, SolvePolicy, Trace
from openflowsheet.verify.failure import bundle_for

REPO_ROOT = Path(__file__).resolve().parents[1]
TOLERANCE = 3.1e-8
NEWTON = SolvePolicy(policy_id="T02-merge", residual_tolerances={}, scales={})

Vector = npt.NDArray[np.float64]


@pytest.fixture(scope="module")
def ref() -> dict[str, Any]:
    loaded: dict[str, Any] = yaml.safe_load(
        (REPO_ROOT / "benchmarks" / "t02" / "reference_values.yaml").read_text()
    )
    return loaded


def floats(values: Sequence[Any]) -> Vector:
    return np.array([float(value) for value in values], dtype=np.float64)


class Loop:
    """`R(t) = G(t) − t` with its exact Jacobian, counting residual calls."""

    def __init__(
        self,
        g_map: Callable[[Vector], Vector],
        g_jacobian: Callable[[Vector], Vector],
        scale: Sequence[float],
        *,
        bounded: bool,
    ) -> None:
        self.calls = 0
        n = len(scale)
        ids = tuple(f"t{i}" for i in range(n))
        rows = tuple(f"R{i}" for i in range(n))

        def residual(t: Vector) -> Evaluation:
            self.calls += 1
            if bounded and bool(np.any(t < 0.0)):
                return Evaluation(status="invalid_trial_state", message="negative component flow")
            return Evaluation(status="ok", values=tuple(float(v) for v in g_map(t) - t))

        self.problem = Problem(
            variable_ids=ids,
            row_ids=rows,
            residual=residual,
            jacobian=lambda t: g_jacobian(t) - np.eye(n),
            scaling=Scaling(
                column=dict(zip(ids, scale, strict=True)), row=dict(zip(rows, scale, strict=True))
            ),
            row_tolerance=dict.fromkeys(rows, TOLERANCE),
            lower_bounds=dict.fromkeys(ids, 0.0) if bounded else {},
        )

    def region(self, trace: Trace) -> Callable[[Vector, Counters], NewtonResult]:
        """The merge: K03's Newton on the loop's own rows, from the best iterate."""

        def solve(x: Vector, counters: Counters) -> NewtonResult:
            return solve_newton(self.problem, x, NEWTON, trace=trace, attempt=1, counters=counters)

        return solve


def rec_05(ref: Mapping[str, Any], gamma: float) -> tuple[Loop, Vector]:
    case = ref["cases_rec"]["REC-05"]
    a = np.array([floats(row) for row in case["A"]])
    t_star = floats(case["t_star"])
    s = float(case["scale_mol_per_s"])

    def g(t: Vector) -> Vector:
        d = t - t_star
        return t_star + a @ d + gamma * np.array([d[1] * d[2], d[2] * d[0], d[0] * d[1]]) / s

    def jacobian(t: Vector) -> Vector:
        d = t - t_star
        dq = np.array([[0.0, d[2], d[1]], [d[2], 0.0, d[0]], [d[1], d[0], 0.0]])
        return a + gamma * dq / s

    start = case["start"]
    t0 = floats(start) if isinstance(start, list) else float(start) * t_star
    return Loop(g, jacobian, [s] * 3, bounded=True), t0


def run(
    loop: Loop,
    t0: Vector,
    *,
    policy: RecyclePolicy | None = None,
    unsupported: tuple[str, str] | None = None,
) -> tuple[ConvergeResult, Trace]:
    trace = Trace()
    result = converge_with_merge(
        loop.problem,
        t0,
        policy=policy,
        merge=None if unsupported else loop.region(trace),
        merge_unsupported=unsupported,
        trace=trace,
    )
    return result, trace


def restarts_are_registered(result: ConvergeResult) -> None:
    """A32: every restart is a stagnation restart, and there are at most two."""
    assert all(event.reason == "stagnation" for event in result.recycle.restarts)
    assert all(event.count <= 2 for event in result.recycle.restarts)


# ----------------------------------------------------------------- A14–A17: the merge halves


def test_a14_rec_05_with_the_tail_merges_and_the_landing_is_recorded(
    ref: dict[str, Any],
) -> None:
    """Substitution stagnates at 20; the region Newton from the best iterate converges to *a*
    fixed point. Which one is recorded, not asserted (§12): the quadratic map has more than two,
    and only `t*` and `S1` are registered. Measured 2026-09-24: `S1`, like the accelerated run
    from the same start (spec §15.1)."""
    loop, t0 = rec_05(ref, 0.1)
    result, _ = run(loop, t0, policy=RecyclePolicy(depth_max=0))
    assert result.recycle.outcome == "RECYCLE_STAGNATION"
    assert result.recycle.iterations == 20
    assert result.merge_into_eo == "taken"
    assert result.outcome == "CONVERGED"
    assert result.merged.residual_inf <= TOLERANCE
    restarts_are_registered(result)

    roots = ref["cases_rec"]["REC-05"]["fixed_points_gamma=0.1"]
    identity = next(
        (
            name
            for name in ("t*", "S1")
            if np.max(np.abs(result.x - floats(roots[name]))) <= 10 * TOLERANCE
        ),
        "unregistered",
    )
    print(f"A14 merge landing: {identity}, x = {result.x.tolist()}")


def test_a15_rcy_div_merges_in_exactly_one_newton_iteration(ref: dict[str, Any]) -> None:
    case = ref["cases_auxiliary"]["RCY-DIV"]
    a = np.array([floats(row) for row in case["A"]])
    t_star = floats(ref["cases_rec"]["REC-01"]["t_star"])
    loop = Loop(lambda t: t_star + a @ (t - t_star), lambda t: a, [3.0] * 3, bounded=False)

    result, _ = run(loop, floats(case["start"]), policy=RecyclePolicy(depth_max=0))
    assert result.recycle.outcome == "RECYCLE_STAGNATION"
    assert result.recycle.stagnation_closures == (6, 11, 16)
    assert result.merge_into_eo == "taken"
    assert result.outcome == "CONVERGED"
    assert result.merged.iterations == 1
    assert np.max(np.abs(result.x - t_star)) <= TOLERANCE
    restarts_are_registered(result)

    accelerated, _ = run(loop, floats(case["start"]))
    assert accelerated.outcome == "CONVERGED" and accelerated.iterations == 4
    assert accelerated.merge_into_eo is None, "no trigger, no merge"


def test_a16_rcy_stall_the_merge_fails_exactly_singular_and_says_nothing_about_existence() -> None:
    loop = Loop(lambda t: t + 1.0, lambda t: np.eye(3), [3.0] * 3, bounded=False)
    result, trace = run(loop, np.zeros(3))
    assert result.recycle.outcome == "RECYCLE_STAGNATION"
    assert result.recycle.stagnation_closures == (5, 10, 15)
    assert result.merge_into_eo == "taken"
    assert result.outcome == "LINEAR_SOLVE_FAILED"
    assert result.merged.linear_reason == "exactly_singular"
    assert result.checkpoint is None, "no certificate path opens on a failure"
    restarts_are_registered(result)
    bundle = bundle_for(result, trace)  # raises if anything in it claims infeasibility
    assert "INFEASIBLE" not in repr(bundle.as_document()).upper()


def test_a17_rcy_coef_merges_in_one_iteration_to_minus_a_million() -> None:
    loop = Loop(
        lambda t: t + 1.0 + 1e-6 * t, lambda t: np.array([[1.0 + 1e-6]]), [1.0], bounded=False
    )
    result, _ = run(loop, np.zeros(1))
    assert result.recycle.outcome == "RECYCLE_STAGNATION"
    assert result.recycle.stagnation_closures == (5, 10, 15)
    assert result.merge_into_eo == "taken"
    assert result.outcome == "CONVERGED"
    assert result.merged.iterations == 1
    assert result.x[0] == pytest.approx(-1e6, rel=1e-9)
    restarts_are_registered(result)


# ----------------------------------------------------------------------- A32: MERGE-U


def test_a32_merge_u_a_non_capable_unit_ends_the_step_with_the_recycles_own_outcome() -> None:
    """RCY-STALL's map on a loop with one non-capable unit (test double): the recycle's
    `RECYCLE_STAGNATION`, `merge_into_eo: unsupported(...)` in the message and the bundle, and no
    residual call after the closure."""
    loop = Loop(lambda t: t + 1.0, lambda t: np.eye(3), [3.0] * 3, bounded=False)
    result, trace = run(loop, np.zeros(3), unsupported=("U-HEAT", "unavailable"))
    assert result.outcome == "RECYCLE_STAGNATION"
    assert result.merge_into_eo == "unsupported"
    assert result.merged is None
    expected = 'merge_into_eo: unsupported(U-HEAT, "derivatives: unavailable")'
    assert expected in result.message
    assert loop.calls == result.recycle.residual_calls, "nothing evaluated after the closure"
    restarts_are_registered(result)

    bundle = bundle_for(result, trace, implicated=("U-HEAT",)).as_document()
    assert bundle["observations"]["merge_into_eo"] == expected.removeprefix("merge_into_eo: ")
    assert bundle["implicated_sources"] == ["U-HEAT"]
    assert bundle["outcome"] == "RECYCLE_STAGNATION"


def test_a32_at_most_one_merge_per_loop() -> None:
    """The merged solve fails and nothing tries again: one recycle, one region, then the end."""
    loop = Loop(lambda t: t + 1.0, lambda t: np.eye(3), [3.0] * 3, bounded=False)
    result, trace = run(loop, np.zeros(3))
    assert result.attempts == 2
    closures = [(event.attempt, event.outcome) for event in trace.of_kind("attempt_closed")]
    assert closures == [(0, "RECYCLE_STAGNATION"), (1, "LINEAR_SOLVE_FAILED")]
    assert result.outcome == "LINEAR_SOLVE_FAILED"


def test_a32_a_step_has_a_region_or_a_reason_never_both_or_neither() -> None:
    loop = Loop(lambda t: t + 1.0, lambda t: np.eye(3), [3.0] * 3, bounded=False)
    with pytest.raises(ValueError):
        converge_with_merge(loop.problem, np.zeros(3), merge=None, merge_unsupported=None)
    with pytest.raises(ValueError):
        converge_with_merge(
            loop.problem,
            np.zeros(3),
            merge=loop.region(Trace()),
            merge_unsupported=("U-HEAT", "unavailable"),
        )


def test_a32_the_merge_region_is_the_loop_with_nothing_added() -> None:
    """On SYN-001 under `anderson`: `region_on_merge` has the loop's `model_version` and
    `constants_sha256`, and its rows — solved and eliminated — are exactly the loop units' rows."""
    from openflowsheet.application.binding import structural_inputs
    from openflowsheet.compiled import EvaluationContext
    from openflowsheet.graph.analysis import analyse
    from openflowsheet.graph.trace import trace_declaration
    from openflowsheet.models.syn001.flowsheet import Syn001Flowsheet
    from openflowsheet.orchestrator.execution import build_execution_plan, declaration_identity
    from openflowsheet.orchestrator.trace import RecyclePolicy as Recycle
    from openflowsheet.thermo.syn001 import Syn001Provider

    flowsheet = Syn001Flowsheet(
        provider=Syn001Provider(),
        context=EvaluationContext(
            model_version="t02", constants_sha256="0" * 64, phase_signature=None
        ),
    )
    spec, graph, row_units = structural_inputs(flowsheet)
    model_version, constants = declaration_identity(spec)
    declaration = trace_declaration(
        spec, row_units=row_units, model_version=model_version, constants_sha256=constants
    )
    report = analyse(
        spec, graph, row_units=row_units, model_version=model_version, constants_sha256=constants
    )
    plan = build_execution_plan(
        spec=spec,
        declaration=declaration,
        graph=graph,
        report=report,
        manifests={unit.unit_id: unit.manifest() for unit in flowsheet.units()},
        policy=SolvePolicy(
            policy_id="T02", residual_tolerances={}, scales={}, recycle=Recycle(method="anderson")
        ),
    )
    (converge,) = [step for step in plan.steps if step.kind == "converge"]
    assert converge.method == "anderson"
    merged = converge.region_on_merge
    assert merged is not None and merged.region is not None and merged.solve_plan is not None
    assert converge.solve_plan is not None
    assert merged.solve_plan.model_version == converge.solve_plan.model_version
    assert merged.solve_plan.constants_sha256 == converge.solve_plan.constants_sha256
    assert merged.units == converge.units
    loop_rows = {
        row for row in declaration.row_ids if declaration.rows[row].unit in set(converge.units)
    }
    region = merged.region
    assert set(region.row_ids) | set(region.eliminated_rows) == loop_rows
    assert not set(region.row_ids) & set(region.eliminated_rows)
    assert not region.specification_rows, "the merge adds no equation"
