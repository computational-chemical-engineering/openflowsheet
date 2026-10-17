"""M03 WO-8: the gray-box adapter solved by the audited cyipopt (spec §8; ADR 0032) — A35-A40,
the Q-F2 and Q-F4 measurements, and the start fixtures, in the audited environment only.

Every test here is marked `nlp`: the default gate deselects them (`addopts` in pyproject.toml), and
`scripts/m03_nlp_check.sh` runs them in the environment of `docs/m03-ipopt-audit.md` with
`OMP_NUM_THREADS=1`, `PYTHONNOUSERSITE=1` and `PYOMO_CONFIG_DIR` set (audit §9). Nothing at module
level imports Pyomo or cyipopt, so the default gate collects this module without them.

Termination is not feasibility and stationarity is not optimality: every number asserted about a
candidate is the re-solved, certified simulation's (V1-V6), not Ipopt's. Ipopt's own status is
checked only where the specification names it (A37's statuses, A40's records, Q-F4).
"""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Iterator
from functools import cache
from pathlib import Path
from typing import Any

import pytest
from conftest import REPO_ROOT, load_json
from m03_fixture_compare import fixture_differences, measurement_differences
from m03_support import flowsheet, nlp_formulation, number, record_measurement, reference
from test_m03_schemas import FIXTURES, REPORT, report_violations

from openflowsheet.application.types import schema_errors
from openflowsheet.studies.nlp.closure import (
    AUDITED_PYNUMERO_ASL_SHA256,
    OptimizationReport,
    optimization_readiness,
    optimize,
)
from openflowsheet.studies.nlp.formulation import HESSIAN_POLICY, IPOPT_OPTIONS, FullSpaceNlp
from openflowsheet.studies.syn001 import with_pinned

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import m03_nlp_measurements  # noqa: E402
import m03_schema_fixtures  # noqa: E402

pytestmark = pytest.mark.nlp

TAU_DECISION = 1e-6  # A35, scaled
TAU_OBJECTIVE = 1e-5  # A35
TAU_V2 = 1e-6  # A36
TAU_ACTIVE = 1e-6  # A36 V3
TAU_FEAS = 1e-8  # A36 V3
TAU_MARGIN = 1e-4  # A36 V4
TAU_MULTIPLIER_REL = 1e-4  # A36 V5
TAU_STATIONARITY = 1e-6  # A36 V5


class _Spy:
    """`casadi.nlpsol` refused and counted (A39), and Ipopt solves counted (A38)."""

    def __init__(self) -> None:
        self.nlpsol_calls: list[str] = []
        self.ipopt_solves = 0


@pytest.fixture(scope="module")
def spy() -> Iterator[_Spy]:
    import casadi
    from pyomo.contrib.pynumero.interfaces.cyipopt_interface import CyIpoptProblemInterface

    record = _Spy()
    solve = CyIpoptProblemInterface.solve

    def refuse(*args: Any, **kwargs: Any) -> Any:
        record.nlpsol_calls.append(str(args[:2]))
        raise RuntimeError("casadi.nlpsol is not on the NLP path (ADR 0006 D2.4)")

    def counted(self: Any, *args: Any, **kwargs: Any) -> Any:
        record.ipopt_solves += 1
        return solve(self, *args, **kwargs)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(casadi, "nlpsol", refuse)
        patch.setattr(CyIpoptProblemInterface, "solve", counted)
        yield record


@cache
def _solved(problem: str) -> OptimizationReport:
    return optimize(nlp_formulation(problem), flowsheet({}))


@pytest.fixture(scope="module")
def nlp_1(spy: _Spy) -> OptimizationReport:
    before = spy.ipopt_solves
    report = _solved("NLP-1")
    assert spy.ipopt_solves - before in (0, 3)  # 0: an earlier test already solved it
    return report


@pytest.fixture(scope="module")
def nlp_inf(spy: _Spy) -> OptimizationReport:
    return _solved("NLP-INF")


def test_the_environment_is_the_audited_one() -> None:
    """Audit §9 items 1-4: the audited ASL build, no forbidden object, single-threaded OpenMP."""
    from openflowsheet.studies.nlp import greybox

    library, digest = greybox.pynumero_asl()
    assert digest == AUDITED_PYNUMERO_ASL_SHA256, library
    assert greybox.environment_problems() == []
    assert os.environ.get("OMP_NUM_THREADS") == "1", "scripts/m03_nlp_check.sh sets it"
    assert os.environ.get("PYTHONNOUSERSITE") == "1"


def test_the_report_records_the_thread_configuration_it_was_produced_under(
    nlp_1: OptimizationReport, nlp_inf: OptimizationReport
) -> None:
    """M03 review F2 (ADR 0007 D6): `solver.environment` records the thread variables, the
    effective `omp_get_max_threads()` of each mapped OpenMP runtime, and the ASL library actually
    loaded. The evidence here is valid only single-threaded (review ruling Q2), so the recorded
    effective count must be 1; the adapter itself enforces nothing."""
    from openflowsheet.studies.nlp import greybox

    library, _ = greybox.pynumero_asl()
    for report in (nlp_1, nlp_inf):
        environment = report.as_document()["solver"]["environment"]
        assert environment["thread_variables"]["OMP_NUM_THREADS"] == "1"
        assert environment["openmp"], "no OpenMP runtime is mapped after the solves"
        assert all(runtime["max_threads"] == 1 for runtime in environment["openmp"])
        assert environment["pynumero_asl"] == {
            "path": library,
            "sha256": AUDITED_PYNUMERO_ASL_SHA256,
        }


# -- A35 and A36: NLP-1 ---------------------------------------------------------------------------


def test_a35_every_start_reaches_the_reference_optimum_verified(
    nlp_1: OptimizationReport, record_property: Any
) -> None:
    optimum = reference()["nlp"]["NLP-1"]["reference_optimum"]
    formulation = nlp_formulation()
    document = nlp_1.as_document()
    assert nlp_1.status == "KKT_POINT_VERIFIED"
    assert nlp_1.reasons == ()
    assert len(nlp_1.starts) == 3
    worst_decision = worst_objective = 0.0
    for start in document["starts"]:
        assert start["classification"] == "KKT_POINT_VERIFIED"
        decisions = start["final_decisions"]
        for decision in formulation.decisions:
            error = abs(decisions[decision.parameter_id] - number(optimum[decision.parameter_id]))
            assert error / decision.scale <= TAU_DECISION
            worst_decision = max(worst_decision, error / decision.scale)
        objective = next(item for item in start["checks"] if item["check"] == "V6")["objective"]
        assert abs(objective - number(optimum["objective"])) <= TAU_OBJECTIVE
        worst_objective = max(worst_objective, abs(objective - number(optimum["objective"])))
    record_measurement(
        record_property, "A35", "max over starts of |d - d*| / s_d", worst_decision, TAU_DECISION
    )
    record_measurement(
        record_property, "A35", "max over starts of |phi - phi*|", worst_objective, TAU_OBJECTIVE
    )
    assert nlp_1.distinct_local_solutions == 1
    assert document["hessian_policy"] == dict(HESSIAN_POLICY)
    assert document["solver"]["options"] == dict(IPOPT_OPTIONS)
    assert document["solver"]["linear_solver"] == "mumps"
    assert document["solver"]["ipopt"] == "3.14.20"
    assert schema_errors(REPORT, document) == []
    assert report_violations(document) == []


def test_a36_the_candidate_is_verified_on_the_resolved_simulation(
    nlp_1: OptimizationReport, record_property: Any
) -> None:
    optimum = reference()["nlp"]["NLP-1"]["reference_optimum"]
    candidate = nlp_1.candidate
    assert candidate is not None
    checks = {item["check"]: item for item in candidate["checks"]}
    assert all(checks[name]["outcome"] == "pass" for name in ("V1", "V2", "V3", "V4", "V5"))
    assert checks["V1"]["certificate_status"] == "VERIFIED"
    assert checks["V2"]["scaled_difference_inf"] <= TAU_V2
    (value,) = candidate["constraint_values"].values()
    assert abs(value) <= TAU_ACTIVE and value >= -TAU_FEAS
    assert [item["name"] for item in candidate["active_set"]] == ["recovery_A"]
    assert checks["V4"]["regime_changed"] == [] and checks["V4"]["declared"] == {
        "U-HEAT": "LIQUID",
        "U-FLASH": "TWO_PHASE",
    }
    assert min(split["margin"] for split in checks["V4"]["splits"]) >= TAU_MARGIN
    kkt = candidate["kkt"]
    mu_star = number(optimum["multiplier_recovery_scaled"])
    assert abs(kkt["multipliers"]["recovery_A"] - mu_star) <= TAU_MULTIPLIER_REL * mu_star
    assert kkt["stationarity_residual_inf"] <= TAU_STATIONARITY
    assert kkt["licq"] and kkt["second_order"] == "not_assessed"
    for quantity, measured, tolerance, sense in (
        ("V2 scaled difference", checks["V2"]["scaled_difference_inf"], TAU_V2, "<="),
        ("V3 |g| of the active constraint", abs(value), TAU_ACTIVE, "<="),
        ("V3 g of the active constraint", value, -TAU_FEAS, ">="),
        ("V4 min regime margin", min(s["margin"] for s in checks["V4"]["splits"]), TAU_MARGIN,
         ">="),
        ("V5 |mu / mu* - 1|", abs(kkt["multipliers"]["recovery_A"] / mu_star - 1.0),
         TAU_MULTIPLIER_REL, "<="),
        ("V5 stationarity residual", kkt["stationarity_residual_inf"], TAU_STATIONARITY, "<="),
    ):  # fmt: skip
        record_measurement(record_property, "A36", quantity, measured, tolerance, sense)
    assert nlp_1.claims == {
        "global_optimality": False,
        "local_stationarity": True,
        "second_order": "not_assessed",
    }


# -- A37: NLP-INF ---------------------------------------------------------------------------------


def test_a37_an_infeasible_problem_is_never_a_verified_point(nlp_inf: OptimizationReport) -> None:
    assert nlp_inf.status in {"INFEASIBLE_REPORTED", "NOT_VERIFIED", "SOLVER_FAILED"}
    assert nlp_inf.candidate is None
    assert nlp_inf.distinct_local_solutions == 0
    assert nlp_inf.claims["local_stationarity"] is False
    document = nlp_inf.as_document()
    assert all(start["classification"] != "KKT_POINT_VERIFIED" for start in document["starts"])
    assert [reason["subject"] for reason in document["reasons"]] == [
        "start 0",
        "start 1",
        "start 2",
    ]
    assert schema_errors(REPORT, document) == []
    assert report_violations(document) == []


# -- A38: the exact Hessian -----------------------------------------------------------------------


def test_a38_an_exact_hessian_is_refused_with_zero_ipopt_calls(spy: _Spy) -> None:
    from openflowsheet.studies.nlp import greybox

    before = spy.ipopt_solves
    report = optimize(nlp_formulation(hessian="exact"), flowsheet({}))
    assert report.status == "UNSUPPORTED"
    assert report.reason_codes == ("HESSIAN_UNAVAILABLE",)
    assert report.starts == () and report.candidate is None
    assert spy.ipopt_solves == before
    # The adapter refuses it as well, should anything hand it one.
    formulation = nlp_formulation(hessian="exact")
    ready = optimization_readiness(nlp_formulation(), flowsheet({}))
    with pytest.raises(ValueError, match="refused before any solver call"):
        greybox.optimize(formulation, flowsheet({}), ready)
    assert spy.ipopt_solves == before


def test_the_pynumero_problem_has_no_hessian_and_ipopt_approximates_it() -> None:
    """Spec §8.3: no Hessian of any kind is supplied; the gray box implements none."""
    from pyomo.contrib.pynumero.interfaces.cyipopt_interface import CyIpoptNLP
    from pyomo.contrib.pynumero.interfaces.pyomo_grey_box_nlp import PyomoNLPWithGreyBoxBlocks

    from openflowsheet.studies.nlp import greybox

    nlp, _ = _full_space()
    box = greybox.FullSpaceGreyBox(nlp)
    for method in ("evaluate_hessian_equality_constraints", "evaluate_hessian_outputs"):
        assert not hasattr(box, method)
    problem = CyIpoptNLP(PyomoNLPWithGreyBoxBlocks(greybox.build_model(nlp, box)))
    assert problem._hessian_available is False
    assert greybox._typed_options()["hessian_approximation"] == "limited-memory"
    assert greybox._typed_options()["limited_memory_max_history"] == 6


# -- A39: no CasADi METIS-closure object, no nlpsol -----------------------------------------------


def test_a39_no_casadi_metis_closure_object_is_mapped_and_nlpsol_is_never_called(
    spy: _Spy, nlp_1: OptimizationReport
) -> None:
    from openflowsheet.studies.nlp import greybox

    assert nlp_1.status == "KKT_POINT_VERIFIED"
    assert spy.nlpsol_calls == []
    assert greybox.forbidden_mapped_objects() == []
    # G2 by the audit's own derivation: every ELF of the CasADi wheel that reaches a METIS 4
    # carrier through DT_NEEDED, none of which may be mapped.
    import casadi
    import m03_ipopt_inventory

    site = Path(casadi.__file__).resolve().parent.parent
    closure = {
        os.path.realpath(site / key) for key in m03_ipopt_inventory.casadi_metis_closure(site)
    }
    inventory = load_json(REPO_ROOT / "benchmarks" / "m03" / "ipopt-inventory-x86_64.json")
    assert len(closure) == inventory["gates"]["G2"]["casadi_metis_closure_size"] > 0
    assert not closure & {os.path.realpath(path) for path in mapped_paths()}


def mapped_paths() -> set[str]:
    with open("/proc/self/maps", encoding="utf-8") as handle:
        rows = [line.rstrip("\n").split(None, 5) for line in handle]
    return {row[5] for row in rows if len(row) == 6 and row[5].startswith("/")}


# -- A40: the start records -----------------------------------------------------------------------


def test_a40_every_start_records_status_iterations_counters_and_time_within_budget(
    nlp_1: OptimizationReport, nlp_inf: OptimizationReport, record_property: Any
) -> None:
    """A40 (Amendment 2, review ruling Q1): every start of both reports records its status,
    iterations, counters and wall time, each within §8.4's per-run limits. The budget is per Ipopt
    run, for every run; a multistart sum is recorded cost, not a gate, so the sums are recorded as
    observations (`record_property`), never asserted."""
    for report in (nlp_1, nlp_inf):
        starts = report.as_document()["starts"]
        for start in starts:
            assert isinstance(start["ipopt_status"], int)
            assert isinstance(start["ipopt_message"], str) and start["ipopt_message"]
            assert isinstance(start["iterations"], int) and start["iterations"] > 0
            counters = start["evaluations"]
            assert counters["residual_calls"] > 0 and counters["jacobian_calls"] > 0
            assert counters["property_calls"] > 0 and counters["evaluation_errors"] == 0
            assert start["wall_time_s"] > 0.0
            assert start["ipopt_final"] is not None
            assert start["iterations"] <= IPOPT_OPTIONS["max_iter"]
            assert start["wall_time_s"] <= IPOPT_OPTIONS["max_wall_time"]
        problem = report.as_document()["formulation"]["problem_id"]
        for quantity, measured, limit in (
            ("iterations", max(s["iterations"] for s in starts), IPOPT_OPTIONS["max_iter"]),
            ("wall time, s", max(s["wall_time_s"] for s in starts), IPOPT_OPTIONS["max_wall_time"]),
        ):
            record_measurement(
                record_property, "A40", f"{problem}: max over starts of {quantity}", measured, limit
            )
        record_property(
            f"{problem} iterations over all starts", sum(s["iterations"] for s in starts)
        )
        record_property(
            f"{problem} wall time over all starts", sum(s["wall_time_s"] for s in starts)
        )
    # D1: per Ipopt iteration at most one twin Jacobian; residuals beyond one per iteration are
    # line-search trials. Two Jacobians are taken before the first iteration (PyNumero's and
    # cyipopt's structure probes).
    for start in nlp_1.as_document()["starts"]:
        assert start["evaluations"]["jacobian_calls"] <= start["iterations"] + 3


# -- the bridge itself ----------------------------------------------------------------------------


def _full_space() -> tuple[FullSpaceNlp, Any]:
    formulation = nlp_formulation()
    sheet = flowsheet({})
    ready = optimization_readiness(formulation, sheet)
    start = ready.starts[0]
    assert start.state is not None
    pinned = with_pinned(sheet, formulation.decision_values(start.start))
    return FullSpaceNlp(pinned, formulation, start.state, start.start), ready


def test_the_gray_box_hands_pynumero_the_twins_rows_and_jacobian_bitwise() -> None:
    """D1: what Ipopt is given is `FullSpaceNlp`'s residual and Jacobian (A31's), in PyNumero's
    primal order, and PyNumero's primal maps back onto `primal_ids` exactly."""
    import numpy as np
    from pyomo.contrib.pynumero.interfaces.pyomo_grey_box_nlp import PyomoNLPWithGreyBoxBlocks

    from openflowsheet.studies.nlp import greybox

    nlp, _ = _full_space()
    box = greybox.FullSpaceGreyBox(nlp)
    model = greybox.build_model(nlp, box)
    pynumero = PyomoNLPWithGreyBoxBlocks(model)
    z = nlp.initial_point()
    primal = pynumero.init_primals()
    assert np.array_equal(greybox._by_primal_id(model, pynumero, nlp, primal), z)
    pynumero.set_primals(primal)
    rows = pynumero.constraint_names()
    residual = pynumero.evaluate_constraints()
    expected = nlp.equality_residual(z)
    positions = [rows.index(f"greybox.{name}") for name in nlp.equality_ids]
    assert np.array_equal(residual[positions], expected)
    # The one Pyomo constraint is `recovery_A`, the rest are the gray box's rows.
    assert len(rows) == len(nlp.equality_ids) + 1
    jacobian = pynumero.evaluate_jacobian().toarray()
    columns = [
        pynumero.primals_names().index(model.greybox.inputs[name].getname(fully_qualified=True))
        for name in nlp.primal_ids
    ]
    assert np.array_equal(jacobian[np.ix_(positions, columns)], nlp.equality_jacobian(z).toarray())
    lower, upper = nlp.bound_arrays()
    assert np.array_equal(pynumero.primals_lb()[columns], lower)
    assert np.array_equal(pynumero.primals_ub()[columns], upper)
    assert np.array_equal(pynumero.get_primals_scaling()[columns], nlp.primal_scaling())
    assert np.array_equal(pynumero.get_constraints_scaling()[positions], nlp.equality_scaling())


# -- Q-F4: evaluation errors ----------------------------------------------------------------------


def test_q_f4_a_twin_evaluation_error_reaches_pynumero_as_an_evaluation_error() -> None:
    """Never a NaN, never a clipped value: the gray box raises PyNumero's evaluation error and
    counts it."""
    import numpy as np
    from pyomo.contrib.pynumero.exceptions import PyNumeroEvaluationError

    from openflowsheet.studies.nlp import greybox

    nlp, _ = _full_space()
    box = greybox.FullSpaceGreyBox(nlp)
    z = nlp.initial_point()
    z[nlp.primal_ids.index("U-FLASH.T_spec")] = 500.0  # outside the provider's declared domain
    z[nlp.primal_ids.index("S4.T")] = 500.0
    box.set_input_values(z)
    with pytest.raises(PyNumeroEvaluationError, match="twin residual evaluation failed"):
        box.evaluate_equality_constraints()
    with pytest.raises(PyNumeroEvaluationError, match="twin jacobian evaluation failed"):
        box.evaluate_jacobian_equality_constraints()
    assert len(box.evaluation_errors) == 2
    box.set_input_values(nlp.initial_point())
    assert np.all(np.isfinite(box.evaluate_equality_constraints()))


@pytest.mark.parametrize("case", sorted(m03_nlp_measurements.QF4_CASES))
def test_q_f4_injected_domain_errors(case: str) -> None:
    """Spec §14 Q-F4 with the pinned Pyomo 6.10.1 and cyipopt 1.7.0: a residual evaluation error
    at a trial point is a rejected step (the start still verifies); one at an accepted point's
    Jacobian or at the start ends Ipopt with `Invalid_Number_Detected`, and the start is
    `SOLVER_FAILED` (spec §8.5 rule 4) with V1-V6 run on what it returned."""
    from openflowsheet.studies.nlp import greybox
    from openflowsheet.studies.nlp.closure import classify_starts

    formulation, sheet = nlp_formulation(), flowsheet({})
    ready = optimization_readiness(formulation, sheet)
    with m03_nlp_measurements.injected_domain(**m03_nlp_measurements.QF4_CASES[case]):
        run = greybox.solve_start(sheet, formulation, ready.starts[0], 0)
    (classification,) = classify_starts([run.evidence()]).classifications
    assert run.evaluations["evaluation_errors"] >= 1
    assert run.detail is not None and "injected" in run.detail
    assert run.verification is not None and len(run.verification.checks) == 6
    if case == "residual_at_a_trial_point":
        assert run.ipopt_status == 0
        assert classification == "KKT_POINT_VERIFIED"
    else:
        assert run.ipopt_status == -13
        assert classification == "SOLVER_FAILED"


# -- the refusals and failures of the adapter itself ----------------------------------------------


def test_an_unaudited_asl_build_is_refused_before_any_solve(
    spy: _Spy, monkeypatch: pytest.MonkeyPatch
) -> None:
    from openflowsheet.studies.nlp import greybox

    monkeypatch.setattr(greybox, "AUDITED_PYNUMERO_ASL_SHA256", "0" * 64)
    before = spy.ipopt_solves
    report = optimize(nlp_formulation(), flowsheet({}))
    assert report.status == "UNSUPPORTED"
    assert report.reason_codes == ("NLP_SOLVER_UNAVAILABLE",)
    assert "PYOMO_CONFIG_DIR" in report.reasons[0].detail
    assert spy.ipopt_solves == before
    assert schema_errors(REPORT, report.as_document()) == []


def test_an_adapter_exception_is_a_solver_failed_start_never_a_raise(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Spec §8.5 rule 4: an exception in the adapter is a result: no Ipopt status, no decisions,
    no V checks, `SOLVER_FAILED`, and the report still validates."""
    from openflowsheet.studies.nlp import greybox

    def broken(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("injected adapter fault")

    monkeypatch.setattr(greybox, "build_model", broken)
    report = optimize(nlp_formulation(), flowsheet({}))
    document = report.as_document()
    assert report.status == "SOLVER_FAILED" and report.candidate is None
    for start in document["starts"]:
        assert start["ipopt_status"] is None and start["final_decisions"] is None
        assert start["checks"] == [] and start["classification"] == "SOLVER_FAILED"
    assert all("injected adapter fault" in reason["detail"] for reason in document["reasons"])
    assert schema_errors(REPORT, document) == []
    assert report_violations(document) == []


# -- reproducibility: the fixtures and the measurements -------------------------------------------


def test_the_nlp_fixtures_are_what_the_adapter_emits_today() -> None:
    """R-015 for the audited environment's fixtures: regenerated, what the committed ones record
    under the numerical policy and M03's rules (`m03_fixture_compare`; M03 review F1 and ruling
    Q3.3), with the measured wall times checked for kind only."""
    emitted = m03_schema_fixtures.nlp_documents()
    assert sorted(emitted) == sorted(m03_schema_fixtures.NLP_FIXTURES)
    for name, document in emitted.items():
        committed = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
        fresh = json.loads(m03_schema_fixtures.serialize(document))
        found = fixture_differences(fresh, committed)
        assert not found, (name, found)


def test_the_q_f2_and_q_f4_measurements_reproduce_and_keep_their_margin() -> None:
    """Spec §14 Q-F2: no measured value within 10x of its registered tolerance; and the committed
    record is what the adapter measures now, for structure and margin (M03 review F1)."""
    measured = m03_nlp_measurements.measure()
    assert measured["q_f2"]["within_margin_factor"] == []
    assert measured["q_f2"]["closest"]["ratio"] >= m03_nlp_measurements.MARGIN_FACTOR
    committed = json.loads(m03_nlp_measurements.OUT.read_text(encoding="utf-8"))
    fresh = json.loads(m03_nlp_measurements.serialize(measured))
    assert measurement_differences(fresh, committed) == []
