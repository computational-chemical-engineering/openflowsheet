"""M05 WO-6 in the audited `nlp` environment: `trust_region_readiness`'s projection and start
halves (design note §6.8, §16.4), every reason produced by a fixture and `READY` on TR-E2's
configuration; P3's C1 constraints at S0; and the production stage runner `TrfStage` on TR-E1.

Every test here is marked `nlp`. The framework-unavailable answer of the default install is
`tests/test_m05_study_loop.py`'s.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

import pytest
import test_m05_c1_projection as c1
import test_m05_projection as projection_tests
import test_m05_zero_flow as zero_flow
from m05_support import AT_START, at_projection, link_toy_projection, tr_e1_projection

from openflowsheet.compile.spec import Expr
from openflowsheet.studies.trust_region.checks import ParentSolve
from openflowsheet.studies.trust_region.study import (
    READINESS_CODES,
    TrfStage,
    c1_constraint_values,
    trust_region_readiness,
)
from openflowsheet.studies.trust_region.trf_state import framework_readiness

pytestmark = pytest.mark.nlp


def start(certified: bool = True, state: Mapping[str, float] | None = None) -> ParentSolve:
    return ParentSolve(
        solve_id="start",
        purpose="start",
        decisions={},
        revision_sha256="0" * 64,
        outcome="CONVERGED" if certified else "FAILED",
        certificate="VERIFIED" if certified else None,
        objective=1.0 if certified else None,
        state={"x": 1.0} if state is None else state,
    )


def _branching(v: Mapping[str, Expr], b: Mapping[str, Expr], p: Mapping[str, Any], a: Any) -> Expr:
    return p["z2"] ** 4 * p["z1"] ** 2 + (2.0 if p["z1"] > 0.0 else 1.0) * p["z1"] - 8.0


def _kinked(v: Mapping[str, Expr], b: Mapping[str, Expr], p: Mapping[str, Any], a: Any) -> Expr:
    return abs(v["x1"]) * p["z2"] ** 4 * p["z1"] ** 2 + p["z1"] - 8.0


def _pin(v: Mapping[str, Expr], b: Mapping[str, Expr], p: Mapping[str, Any], a: Any) -> Expr:
    return v["x1"] - 1.0


def _extra_decision() -> Any:
    base = projection_tests.tr_e1_spec()
    return projection_tests.tr_e1_variant(
        parameter_ids=(*base.parameter_ids, "z3"),
        parameters={**base.parameters, "z3": 1.0},
        decisions=(*projection_tests.TR_E1_DECISIONS, "z3"),
    )


row, c1_row = projection_tests.row, projection_tests.c1
#: One fixture per projection refusal (the same specs `test_m05_projection.py` and
#: `test_m05_zero_flow.py` refuse), each ignoring the start it is given.
PROJECTION_FIXTURES: Mapping[str, Callable[[], Any]] = {
    "PARAMETER_NOT_DIFFERENTIABLE": lambda: projection_tests.tr_e1_variant(
        equations=(row("c1", c1_row), row("c2-branching", _branching))
    ),
    "PROJECTION_NONSMOOTH": lambda: projection_tests.tr_e1_variant(
        equations=(row("c1", c1_row), row("c2-abs", _kinked))
    ),
    "PROJECTION_STRUCTURE": _extra_decision,
    "PROJECTION_DOF": lambda: projection_tests.tr_e1_variant(
        equations=(*projection_tests.tr_e1_spec().equations, row("c3", _pin))
    ),
    "PROJECTION_SCALES_UNAVAILABLE": lambda: projection_tests.tr_e1_variant(
        variable_kinds={"x0": "temperature", "x1": "no_such_kind"},
        row_kinds={"c1": "heat_rate"},
    ),
    "PROJECTION_IMPLICIT_EF_INPUT": lambda: link_toy_projection("implicit"),
    "PROJECTION_OMITTED_ROW_UNCERTIFIED": lambda: at_projection(
        start={**AT_START, "Pa": 1.0e5 + 1.0, "Pb": 1.0e5 + 1.0}
    ),
    "PROJECTION_ZERO_FLOW": lambda: zero_flow.toy_projection(
        zero_flow.toy_spec(pin=lambda v, b, p, a: v["n0"] - 0.5 * (p["z"] - 1.0))
    ),
}


@pytest.mark.parametrize("code", sorted(PROJECTION_FIXTURES))
def test_each_projection_refusal_is_a_readiness_reason(code: str) -> None:
    fixture = PROJECTION_FIXTURES[code]
    found = trust_region_readiness(start=start, project=lambda solve: fixture())
    assert (found.status, found.codes) == ("UNSUPPORTED", (code,))
    assert found.reasons[0][1].startswith(f"{code}(")


@pytest.mark.parametrize(
    ("code", "overrides"),
    [
        ("TRUST_REGION_FRAMEWORK_UNPINNED", {"version": "6.9.0"}),
        ("TRSP_SOLVER_UNAUDITED", {"executable": projection_tests.__file__}),
    ],
)
def test_each_framework_reason_is_a_readiness_reason(code: str, overrides: dict[str, Any]) -> None:
    from pathlib import Path

    overrides = {k: Path(v) if k == "executable" else v for k, v in overrides.items()}
    found = trust_region_readiness(start=start, framework=lambda: framework_readiness(**overrides))
    assert found.codes == (code,)


def test_the_unavailable_reason_stops_readiness_before_any_solve() -> None:
    """TRUST_REGION_FRAMEWORK_UNAVAILABLE's fixture here: Pyomo reported absent."""
    from openflowsheet.studies.trust_region.trf_state import FrameworkReadiness, ReadinessReason

    def absent() -> FrameworkReadiness:
        return FrameworkReadiness(
            "UNSUPPORTED", (ReadinessReason("TRUST_REGION_FRAMEWORK_UNAVAILABLE", "absent"),)
        )

    def never() -> ParentSolve:
        raise AssertionError("readiness solved without the framework")

    assert trust_region_readiness(start=never, framework=absent).codes == (
        "TRUST_REGION_FRAMEWORK_UNAVAILABLE",
    )


def test_an_uncertified_start_is_a_readiness_reason_and_the_projection_still_runs() -> None:
    fixture = PROJECTION_FIXTURES["PROJECTION_DOF"]
    found = trust_region_readiness(start=lambda: start(False), project=lambda s: fixture())
    assert found.codes == ("START_NOT_CERTIFIED", "PROJECTION_DOF")


def test_every_readiness_code_has_a_fixture() -> None:
    covered = set(PROJECTION_FIXTURES) | {
        "TRUST_REGION_FRAMEWORK_UNAVAILABLE",
        "TRUST_REGION_FRAMEWORK_UNPINNED",
        "TRSP_SOLVER_UNAUDITED",
        "START_NOT_CERTIFIED",
    }
    assert covered == set(READINESS_CODES)


# == TR-E2's configuration ========================================================================


def tr_e2_start() -> tuple[ParentSolve, Any, Any]:
    """S0 of TR-E2 (the reference-coupled loop at 673.15 K, its inner solve certified) as a
    parent solve, with the binding and formulation it projects with."""
    binding, state, certificate = c1.s0()
    formulation, _, _ = c1.tr_e2()
    solved = ParentSolve(
        solve_id="S0",
        purpose="start",
        decisions={formulation.decisions[0].parameter_id: c1.NOMINAL},
        revision_sha256="0" * 64,
        outcome="CONVERGED",
        certificate=certificate.verification_status,
        objective=state[f"{formulation.liquid_stream}.n.NH3"],
        state=state,
    )
    return solved, binding, formulation


def test_readiness_is_ready_on_tr_e2_s_configuration() -> None:
    from openflowsheet.studies.trust_region.study import project_c1

    solved, binding, formulation = tr_e2_start()
    found = trust_region_readiness(
        start=lambda: solved,
        project=lambda s: project_c1(binding, s.state or {}, formulation),
    )
    assert found.as_document() == {"status": "READY", "reasons": []}


def test_p3_s_c1_constraints_hold_at_s0_and_catch_a_violation() -> None:
    solved, binding, formulation = tr_e2_start()
    assert solved.state is not None
    reactor = c1.reference.reactor_of(binding)
    coupling = (float(reactor.conversion), float(reactor.temperature_rise))
    values = c1_constraint_values(
        formulation,
        solved.state,
        solved.decisions,
        coupling,
        binding.spec.variable_kinds,
        reactor.n_tubes,
    )
    kinds = binding.spec.variable_kinds
    expected = (
        len(formulation.inequalities)
        + 2 * len(formulation.decisions)
        + 2 * len(formulation.variable_bounds)
        + 4
        + 2 * sum(1 for name in solved.state if kinds.get(name) in formulation.domain)
        + sum(1 for name in solved.state if kinds.get(name) == "molar_flow")
    )
    assert len(values) == expected
    assert [v.constraint_id for v in values if not v.holds] == []
    hot = {**solved.state, f"{formulation.inlet_stream}.T": 2000.0}
    violated = c1_constraint_values(
        formulation, hot, solved.decisions, coupling, kinds, reactor.n_tubes
    )
    assert {v.constraint_id for v in violated if not v.holds} >= {
        f"hard_domain.{formulation.inlet_stream}.T.upper"
    }


# == the stage runner on TR-E1 =====================================================================


def test_trf_stage_is_run_trf_with_the_radius_scaled() -> None:
    """At radius factor 1 the stage runner's run is TR-E1's through `run_trf` (same iterations,
    bitwise); at ¼ only the configured radius changes. TR-E1's EF is a property block: no
    truth, no cold truth request."""
    from openflowsheet.studies.trust_region.trf import run_trf
    from openflowsheet.studies.trust_region.trf_state import TRSP_SOLVER_ALIAS, zero_basis

    config = {"solver": TRSP_SOLVER_ALIAS, "trust_radius": 1.0}

    def basis(projection: Any) -> Any:
        return zero_basis(projection.ef_names.values())

    from openflowsheet.studies.trust_region.study import IN_PROCESS_BUDGET, StudyBudget

    stage = TrfStage(lambda s: tr_e1_projection(), basis, config, [{"id": "A1"}])
    budget = StudyBudget(IN_PROCESS_BUDGET)
    staged = stage(start(), run_id="C1", radius_factor=1.0, budget=budget)
    direct_projection = tr_e1_projection()
    direct = run_trf(
        direct_projection, {"solver": TRSP_SOLVER_ALIAS}, basis=basis(direct_projection)
    )
    assert staged.outcome == direct.outcome == "TRF_CONVERGED"
    assert staged.document["iterations"] == [r.as_document() for r in direct.iterations]
    assert direct.final is not None and staged.decisions == direct.final.decisions
    assert staged.point is not None and staged.point.final_state_checks == {
        "omitted_rows": True,
        "zero_pins": True,
    }
    assert (staged.cold, budget.cold.used) == (0, 0)
    assert staged.document["assumptions"] == [{"id": "A1"}]
    assert staged.document["projection"]["n_block_efs"] == 1
    quarter = stage(start(), run_id="C1-retry", radius_factor=0.25, budget=budget)
    assert quarter.document["config"]["trust_radius"] == 0.25
