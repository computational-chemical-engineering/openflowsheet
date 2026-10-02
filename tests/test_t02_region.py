"""T02 §6: the equation-oriented region solve and its phase policy, on SYN-001 under `eo`.

The EO path and the tear path are two independent routes to one state: K03's tear solve (its own
solver, already gated against P01's 20-digit values) and the region Newton of §6.1 from the
sequential initializer. Agreement is asserted against P01, per quantity kind, at ten times each
kind's residual tolerance (§6.4): flows `3.1e-7 mol/s`, temperatures `1e-5 K`, pressures `0.1 Pa`,
duties `1e-2 W`.

A21 is the case that corrected the specification. Under §6.3.3 as first written the nominal solve
ended `BOUND_BLOCKED`, because a vapour *component* lands on zero while the vapour total is still
4.4e-5 mol/s, and the rule fired only on a total. Fable ruled on 2026-09-24 that any lifted variable
of an active phase landing on its bound is the phase leaving, with the premise stated; the counts
did not change.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
import yaml

from openflowsheet.application.binding import structural_inputs
from openflowsheet.compile.casadi_backend import compile_problem
from openflowsheet.compile.spec import ProblemSpec
from openflowsheet.compiled import CompiledProblem, EvaluationContext
from openflowsheet.graph.analysis import analyse
from openflowsheet.graph.trace import trace_declaration
from openflowsheet.models.syn001.flowsheet import Syn001Flowsheet
from openflowsheet.orchestrator.execution import (
    Region,
    build_execution_plan,
    declaration_identity,
)
from openflowsheet.orchestrator.region import (
    EQUILIBRIUM_TOLERANCE,
    RegionResult,
    solve_region,
    syn001_lifted_splits,
)
from openflowsheet.orchestrator.tear import INITIALIZER_ID, Syn001TearProblem, solve_tear
from openflowsheet.orchestrator.trace import RecyclePolicy, SolvePolicy
from openflowsheet.thermo.syn001 import Syn001Provider

REPO_ROOT = Path(__file__).resolve().parents[1]
POLICY = SolvePolicy(
    policy_id="T02-eo", residual_tolerances={}, scales={}, recycle=RecyclePolicy(method="eo")
)
AGREEMENT = {"molar_flow": 3.1e-7, "temperature": 1e-5, "pressure": 0.1, "heat_rate": 1e-2}


@dataclass(frozen=True)
class Case:
    flowsheet: Syn001Flowsheet
    spec: ProblemSpec
    compiled: CompiledProblem
    region: Region
    p01: Mapping[str, Any]


def case(case_id: str) -> Case:
    entry = {
        item["case_id"]: item
        for item in yaml.safe_load(
            (REPO_ROOT / "benchmarks" / "syn001" / "reference_values.yaml").read_text()
        )["variants"]
    }[case_id]
    flowsheet = Syn001Flowsheet(
        provider=Syn001Provider(),
        context=EvaluationContext(
            model_version="t02", constants_sha256="0" * 64, phase_signature=None
        ),
        split_fraction=float(entry["r"]),
        flash_temperature=float(entry["T_flash_K"]),
        heater_temperature=float(entry["T_heater_K"]),
        pressure=float(entry["P_Pa"]),
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
        policy=POLICY,
    )
    region = plan.steps[1].region
    assert region is not None
    return Case(flowsheet, spec, compile_problem(spec), region, entry)


def solve(
    item: Case, state: Mapping[str, float], trace: Any = None, source: str = "user_guess"
) -> RegionResult:
    """`source` is item 0's `initializer_source` (T03 §8.1): the registered initializer's id when
    `state` is its reconstruction, `x(t⁰)`; `user_guess` for a state the test supplies."""
    return solve_region(
        compiled=item.compiled,
        spec=item.spec,
        region=item.region,
        state=state,
        splits=syn001_lifted_splits(item.flowsheet.components),
        provider=item.flowsheet.provider,
        policy=POLICY,
        trace=trace,
        initializer_source=source,
    )


def initializer(item: Case) -> dict[str, float]:
    """`x(t⁰)`: the sequential pre-solve's reconstruction at the registered initializer (§6.2)."""
    return dict(Syn001TearProblem(item.flowsheet).reconstruct(item.flowsheet.initial_recycle()))


def disagreement(item: Case, state: Mapping[str, float]) -> list[str]:
    """Where `state` departs from the tear solution by more than §6.4's allowance for its kind."""
    tear, _ = solve_tear(item.flowsheet)
    assert tear.final_state is not None
    return [
        f"{name}: {state[name]!r} vs {tear.final_state[name]!r}"
        for name in item.spec.variable_ids
        if abs(state[name] - tear.final_state[name])
        > AGREEMENT.get(item.spec.variable_kinds.get(name, "molar_flow"), 3.1e-7)
    ]


def test_the_equilibrium_tolerance_is_k04s() -> None:
    """Restated in the region module to avoid an import cycle; pinned here so it cannot drift."""
    from openflowsheet.verify.checks import EQUILIBRIUM_TOLERANCE as REGISTERED

    assert EQUILIBRIUM_TOLERANCE == REGISTERED


def test_a21_nominal_the_heater_vapour_leaves_and_the_solve_restarts_liquid() -> None:
    """Two attempts. The first, both lifted units two-phase, closes at iteration 1: a vapour
    variable
    of the heater's split lands on its bound (measured `S3.vap.B`, `S3.V` still 4.4e-5 —
    which one lands first is a roundoff-level race, so the assertion names the set). The second,
    heater LIQUID, converges; the pinned vapour total is exactly zero."""
    item = case("SYN-001-nominal")
    result = solve(item, initializer(item), source=INITIALIZER_ID)
    assert result.outcome == "CONVERGED"
    assert len(result.attempts) == 2
    first, second = result.attempts
    assert dict(first.signature) == {"U-HEAT": "TWO_PHASE", "U-FLASH": "TWO_PHASE"}
    assert first.outcome == "PHASE_UPDATE_REQUIRED" and first.iterations <= 2
    assert first.reason.startswith("phase_disappeared(U-HEAT, vapor, ")
    variable = first.reason.removeprefix("phase_disappeared(U-HEAT, vapor, ").rstrip(")")
    assert variable in {"S3.vap.A", "S3.vap.B", "S3.vap.C", "S3.V"}
    assert dict(second.signature) == {"U-HEAT": "LIQUID", "U-FLASH": "TWO_PHASE"}
    assert second.outcome == "CONVERGED" and second.iterations <= 5
    assert result.state["S3.V"] == 0.0
    assert not disagreement(item, result.state)


@pytest.mark.parametrize(
    ("case_id", "iterations"),
    [
        ("SYN-001-high-recycle", 10),
        ("SYN-001-all-liquid-310K", 5),
        ("SYN-001-once-through", 0),
        ("SYN-001-all-vapor-420K", 0),
    ],
)
def test_a22_eo_agrees_with_the_tear_solution(case_id: str, iterations: int) -> None:
    """One attempt at each; the high-recycle heater outlet is liquid from the start, because on its
    ray the flip point `s_flip = 0.0288` lies below the initializer's 0.05 (a closed form)."""
    item = case(case_id)
    result = solve(item, initializer(item), source=INITIALIZER_ID)
    assert result.outcome == "CONVERGED"
    assert len(result.attempts) == 1
    assert result.iterations <= iterations
    assert not disagreement(item, result.state)
    if case_id == "SYN-001-high-recycle":
        assert dict(result.signatures[0])["U-HEAT"] == "LIQUID"
        assert result.state["S3.V"] == 0.0, "pinned, exactly"


@pytest.mark.parametrize(
    "case_id",
    [
        "SYN-001-nominal",
        "SYN-001-high-recycle",
        "SYN-001-all-liquid-310K",
        "SYN-001-once-through",
        "SYN-001-all-vapor-420K",
    ],
)
def test_a23_the_region_solves_the_same_function_as_the_tear(case_id: str) -> None:
    """Started from the tear solution, the region converges at iteration 0 with no Jacobian and no
    factorization: the residual K04 verifies is the residual the region solves."""
    item = case(case_id)
    tear, _ = solve_tear(item.flowsheet)
    assert tear.final_state is not None
    result = solve(item, dict(tear.final_state))
    assert result.outcome == "CONVERGED"
    assert result.iterations == 0
    assert result.counters.jacobian_calls == 0
    assert result.counters.factorizations == 0


def test_a24_eo_triv_the_projection_keeps_the_solve_off_the_trivial_root() -> None:
    """R-010's hazard in the flesh: the all-liquid heater outlet at once-through is an exact root of
    every row and inadmissible (`Σ x K(350 K) = 1.070`). Forced into the supplied state, it is
    overwritten by the kernel's split before anything is solved, and that overwrite is recorded."""
    item = case("SYN-001-once-through")
    state = initializer(item)
    feed = [state[f"S3.n.{component}"] for component in item.flowsheet.components]
    for component, amount in zip(item.flowsheet.components, feed, strict=True):
        state[f"S3.liq.{component}"] = amount
        state[f"S3.vap.{component}"] = 0.0
    state["S3.V"], state["S3.L"] = 0.0, float(sum(feed))

    from openflowsheet.orchestrator.trace import Trace

    trace = Trace()
    result = solve(item, state, trace)
    assert result.projections == ("S3",)
    candidates = trace.of_kind("initializer_candidate")
    assert [event.message for event in candidates] == ["projected(S3, all_liquid, TWO_PHASE)"]
    assert len(trace.of_kind("initializer_accepted")) == 1
    assert result.outcome == "CONVERGED"
    assert len(result.attempts) == 1 and result.iterations == 0
    beta = result.state["S3.V"] / (result.state["S3.V"] + result.state["S3.L"])
    assert beta == pytest.approx(float(item.p01["heater_outlet_vapor_fraction"]), rel=1e-12)


def test_s5_a_kernel_refusal_is_an_evaluation_error_not_an_exception() -> None:
    """Review S5: from the nominal solution with the heater outlet at 450 K — outside the
    provider's 280–440 K domain — the projection's flash is refused, and the region says so."""
    item = case("SYN-001-nominal")
    tear, _ = solve_tear(item.flowsheet)
    assert tear.final_state is not None
    state = {**tear.final_state, "S3.T": 450.0}
    result = solve(item, state)
    assert result.outcome == "EVALUATION_ERROR"
    assert "S3" in result.message and "provider returned" in result.message


def test_s6_newton_names_the_variable_that_blocks() -> None:
    """Review S6: BND-02's scalar (`R = x + 1`, `x ≥ 0`, `x⁰ = 0`) reports `x` as the blocker, so
    the region attributes a block instead of guessing at the first watched variable at zero."""
    import numpy as np
    import scipy.sparse as sp

    from openflowsheet.numerics.newton import Evaluation, Problem, solve_newton
    from openflowsheet.numerics.scaling import Scaling
    from openflowsheet.orchestrator.trace import Trace

    problem = Problem(
        variable_ids=("x",),
        row_ids=("r",),
        residual=lambda x: Evaluation(status="ok", values=(float(x[0]) + 1.0,)),
        jacobian=lambda x: sp.csc_matrix(np.array([[1.0]])),
        scaling=Scaling(column={"x": 1.0}, row={"r": 1.0}),
        row_tolerance={"r": 1e-12},
        lower_bounds={"x": 0.0},
    )
    result = solve_newton(problem, [0.0], POLICY, trace=Trace())
    assert result.outcome == "BOUND_BLOCKED"
    assert result.blocked_by == ("x",)
