"""M03 WO-7: the NLP formulation, the V5 verifier and the optimization closure (spec §8) —
A31-A34, in the default environment (no Ipopt, no Pyomo).

The reference optimum of NLP-1 is the design lane's closed form (`benchmarks/m03/
reference_values.json`, `nlp`): the recovery constraint fixes T_f*, stationarity in r idles the
heater, and the scaled multiplier is μ* = ∂φ/∂T̂_f / ∂g/∂T̂_f. The verifier computes the same
quantities from M03's adjoint sensitivities on the re-solved flowsheet; nothing here asks an
optimizer anything.
"""

from __future__ import annotations

import dataclasses
from functools import cache
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from m03_support import flowsheet, nlp_formulation, number, reference
from t07_corpus import CORPUS

from openflowsheet.application.contract import ApplicationError
from openflowsheet.application.local import LocalApplication
from openflowsheet.compile.casadi_backend import compile_parametric_twin, compile_problem
from openflowsheet.compiled import EvaluationContext
from openflowsheet.studies.nlp.closure import (
    AUDIT_DOCUMENT,
    Readiness,
    SolverAvailability,
    optimization_readiness,
    optimize,
)
from openflowsheet.studies.nlp.formulation import (
    HESSIAN_POLICY,
    IPOPT_OPTIONS,
    Decision,
    FullSpaceNlp,
    NlpFormulation,
    QuadraticExpression,
)
from openflowsheet.studies.nlp.verification import CandidateVerification, verify_candidate
from openflowsheet.studies.syn001 import solve_certified, with_pinned

TAU_MULTIPLIER_REL = 1e-6
TAU_STATIONARITY_OPTIMUM = 1e-8
STATIONARITY_AT_START = 1e-2
#: The heater's vapour at a LIQUID heater: exactly zero at the start, so left unbounded (§8.2).
ZERO_AT_START = ("S3.vap.A", "S3.vap.B", "S3.vap.C", "S3.V")


def available() -> SolverAvailability:
    """A probe standing in for the audited extra, so each other reason can be seen alone."""
    return SolverAvailability(True, "test double: the audited extra is present")


@cache
def readiness(problem_id: str = "NLP-1") -> Readiness:
    return optimization_readiness(nlp_formulation(problem_id), flowsheet({}))


@cache
def full_space() -> tuple[FullSpaceNlp, Any]:
    formulation = nlp_formulation()
    start = formulation.starts[0]
    sheet = with_pinned(flowsheet({}), formulation.decision_values(start))
    solve = solve_certified(sheet)
    assert solve.verified and solve.final_state is not None
    return FullSpaceNlp(sheet, formulation, solve.final_state, start), sheet


@cache
def at_optimum() -> CandidateVerification:
    optimum = reference()["nlp"]["NLP-1"]["reference_optimum"]
    decisions = (number(optimum["U-SPLIT.split_fraction"]), number(optimum["U-FLASH.T_spec"]))
    regimes = readiness().declared_regimes
    assert regimes is not None
    return verify_candidate(flowsheet({}), nlp_formulation(), decisions, regimes=regimes)


# -- A31: the full-space formulation ---------------------------------------------------------------


def test_a31_the_equality_rows_and_their_jacobian_are_the_twins_bitwise() -> None:
    nlp, sheet = full_space()
    z = nlp.initial_point()
    x, decisions = nlp.split(z)
    assert decisions == {"U-SPLIT.split_fraction": 0.6, "U-FLASH.T_spec": 360.0}
    # An independently compiled twin, and the base compiled problem at the same state.
    twin = compile_parametric_twin(nlp.spec, nlp.decision_ids)
    kept = [nlp.spec.equation_ids.index(name) for name in nlp.equality_ids]
    assert len(kept) == len(nlp.variable_ids) == 47
    residual = nlp.equality_residual(z)
    assert np.array_equal(residual, np.array(twin.residual(x, decisions))[kept])
    jacobian = nlp.equality_jacobian(z).toarray()
    n = nlp.n_variables
    state_columns = _dense(twin.jacobian_x(x, decisions))[kept]
    decision_columns = _dense(twin.jacobian_p(x, decisions))[kept]
    assert np.array_equal(jacobian[:, :n] + 0.0, state_columns + 0.0)
    assert np.array_equal(jacobian[:, n:] + 0.0, decision_columns + 0.0)
    # And the base problem, which bakes the start's decisions in, at the same state (A01's guard).
    base = compile_problem(sheet.spec())
    context = EvaluationContext(
        model_version=base.metadata.model_version,
        constants_sha256=base.metadata.constants_sha256,
    )
    evaluation = base.residual(x, context)
    assert evaluation.values is not None
    assert np.array_equal(np.array(evaluation.values)[kept] + 0.0, residual + 0.0)
    assert np.array_equal(_dense(base.jacobian(x, context))[kept] + 0.0, state_columns + 0.0)
    assert np.count_nonzero(decision_columns) > 0
    # The start is a root of the kept rows (scaled), as the verified simulation state must be.
    assert float(np.max(np.abs(residual * nlp.equality_scaling()))) <= 1e-10
    assert nlp.counters == {"residual_calls": 1, "jacobian_calls": 1}


def test_a31_the_bounds_are_true_domain_restrictions() -> None:
    nlp, sheet = full_space()
    domain = sheet.provider.describe().domain
    kinds = nlp.spec.variable_kinds
    for name in nlp.variable_ids:
        bound = nlp.bounds[name]
        if kinds[name] == "molar_flow" and name in ZERO_AT_START:
            assert nlp.start_state[name] == 0.0
            assert (bound.lower, bound.upper) == (None, None), name
        elif kinds[name] == "molar_flow":
            assert nlp.start_state[name] != 0.0, name
            assert (bound.lower, bound.upper) == (0.0, None), name
        elif kinds[name] == "temperature":
            assert (bound.lower, bound.upper) == domain["T"] == (280.0, 440.0)
        elif kinds[name] == "pressure":
            assert (bound.lower, bound.upper) == domain["P"] == (5e4, 2e5)
        else:
            assert kinds[name] == "heat_rate"
            assert (bound.lower, bound.upper) == (None, None)
    unbounded_flows = {
        name
        for name in nlp.variable_ids
        if kinds[name] == "molar_flow" and nlp.bounds[name].lower is None
    }
    assert unbounded_flows == set(ZERO_AT_START)
    for decision in nlp.formulation.decisions:
        bound = nlp.bounds[decision.parameter_id]
        assert (bound.lower, bound.upper) == (decision.lower, decision.upper)
    lower, upper = nlp.bound_arrays()
    z = nlp.initial_point()
    assert np.all(lower <= z) and np.all(z <= upper)
    scaling = nlp.primal_scaling()
    assert scaling[nlp.primal_ids.index("U-FLASH.T_spec")] == 1.0 / 100.0
    assert scaling[nlp.primal_ids.index("S4.n.A")] == 1.0 / 3.0


def _dense(matrix: Any) -> Any:
    result = np.zeros((len(matrix.row_ids), len(matrix.col_ids)))
    for column in range(len(matrix.col_ids)):
        for offset in range(matrix.indptr[column], matrix.indptr[column + 1]):
            result[matrix.indices[offset], column] = matrix.data[offset]
    return result


# -- A32: the V5 verifier --------------------------------------------------------------------------


def test_a32_the_reduced_kkt_check_at_the_reference_optimum() -> None:
    verification = at_optimum()
    optimum = reference()["nlp"]["NLP-1"]["reference_optimum"]
    assert verification.outcome("V1") == "pass"
    assert verification.outcome("V3") == "pass"
    assert verification.outcome("V4") == "pass"
    assert verification.outcome("V5") == "pass"
    assert verification.active_names == tuple(reference()["nlp"]["NLP-1"]["active_set"])
    kkt = verification.kkt
    assert kkt is not None
    mu = kkt.multipliers["recovery_A"]
    mu_star = number(optimum["multiplier_recovery_scaled"])
    mu_error = abs(mu - mu_star) / mu_star
    assert mu_error <= TAU_MULTIPLIER_REL
    assert kkt.stationarity_residual <= TAU_STATIONARITY_OPTIMUM
    assert kkt.licq
    assert kkt.second_order == reference()["nlp"]["NLP-1"]["second_order_expected_report"]
    assert kkt.second_order == "not_assessed"
    gradient_errors = [
        abs(value - number(closed))
        for value, closed in zip(
            kkt.objective_gradient + kkt.constraint_gradients["recovery_A"],
            optimum["objective_gradient_scaled"] + optimum["constraint_gradient_scaled"],
            strict=True,
        )
    ]
    assert verification.objective is not None
    objective_error = abs(verification.objective - number(optimum["objective"]))
    print(
        f"A32 mu relative error {mu_error:.3e}; stationarity {kkt.stationarity_residual:.3e}; "
        f"gradient errors {max(gradient_errors):.3e}; objective error {objective_error:.3e}"
    )
    # Without the optimizer's state there is no V2, so no candidate here is ever "passed".
    assert verification.outcome("V2") == "not_evaluated"
    assert not verification.passed
    # The record says what the checks say: no detail member replaces a verdict.
    document = verification.as_document()
    assert [(item["check"], item["outcome"]) for item in document["checks"]] == [
        (item.check, item.outcome) for item in verification.checks
    ]
    assert document["checks"][0]["resolve_outcome"] == "CONVERGED"


def test_a32_the_same_verifier_discriminates_at_the_start() -> None:
    regimes = readiness().declared_regimes
    assert regimes is not None
    formulation = nlp_formulation()
    verification = verify_candidate(
        flowsheet({}), formulation, formulation.starts[0], regimes=regimes
    )
    assert verification.kkt is not None
    assert verification.kkt.stationarity_residual >= STATIONARITY_AT_START
    assert verification.outcome("V5") == "fail"
    # The start violates the recovery constraint (spec §8.1), which V3 reports.
    assert verification.outcome("V3") == "fail"
    expected = number(reference()["nlp"]["NLP-1"]["starts"][0]["constraint_scaled"])
    assert abs(verification.constraint_values["recovery_A"] - expected) <= 1e-12
    print(f"A32 stationarity at the start {verification.kkt.stationarity_residual:.3e}")


def test_a32_v2_compares_the_optimizer_state_with_the_resolved_simulation() -> None:
    """A32 as amended (spec §8.5): supplied the re-solved state as the optimizer state, V2 is
    `pass` and the verification is `passed`; a gross error in that state fails V2."""
    verification = at_optimum()
    state = verification.simulation_state
    assert state is not None
    regimes = readiness().declared_regimes
    assert regimes is not None
    decisions = tuple(verification.decisions.values())
    same = verify_candidate(
        flowsheet({}), nlp_formulation(), decisions, regimes=regimes, optimizer_state=state
    )
    assert same.outcome("V2") == "pass" and same.passed
    # A negative-flow pseudo-solution of the heater's vapour is a gross error, not a precision one.
    shifted = {**state, "S3.vap.A": state["S3.vap.A"] - 0.03}
    other = verify_candidate(
        flowsheet({}), nlp_formulation(), decisions, regimes=regimes, optimizer_state=shifted
    )
    assert other.outcome("V2") == "fail" and not other.passed
    assert "V2" in other.failures


# -- A33: readiness, one reason at a time ----------------------------------------------------------


def _ready(formulation: NlpFormulation) -> Readiness:
    return optimization_readiness(formulation, flowsheet({}), solver_probe=available)


def _with_decision(formulation: NlpFormulation, index: int, decision: Decision) -> NlpFormulation:
    decisions = list(formulation.decisions)
    decisions[index] = decision
    return dataclasses.replace(formulation, decisions=tuple(decisions))


def test_a33_nlp_1_is_ready_only_when_the_audited_extra_is_present() -> None:
    ready = _ready(nlp_formulation())
    assert ready.status == "READY_FOR_OPTIMIZATION"
    assert ready.reasons == ()
    assert ready.declared_regimes == {"U-HEAT": "LIQUID", "U-FLASH": "TWO_PHASE"}
    default = readiness()
    assert default.status == "unsupported"
    assert default.codes == ("NLP_SOLVER_UNAVAILABLE",)
    (reason,) = default.reasons
    assert AUDIT_DOCUMENT in reason.detail and reason.subject == AUDIT_DOCUMENT


def test_a33_unknown_decision() -> None:
    formulation = _with_decision(
        nlp_formulation(), 1, Decision("U-FLASH.T_set", 356.0, 366.0, 100.0)
    )
    assert _ready(formulation).codes == ("UNKNOWN_DECISION",)


def test_a33_bounds_undeclared() -> None:
    formulation = _with_decision(
        nlp_formulation(), 1, Decision("U-FLASH.T_spec", 356.0, None, 100.0)
    )
    assert _ready(formulation).codes == ("BOUNDS_UNDECLARED",)
    empty = _with_decision(nlp_formulation(), 0, Decision("U-SPLIT.split_fraction", 0.7, 0.7, 1.0))
    starts = ((0.7, 360.0),)
    assert _ready(dataclasses.replace(empty, starts=starts)).codes == ("BOUNDS_UNDECLARED",)


def test_a33_start_outside_bounds() -> None:
    formulation = dataclasses.replace(nlp_formulation(), starts=((0.6, 367.0),))
    assert _ready(formulation).codes == ("START_OUTSIDE_BOUNDS",)


def test_a33_decision_inconsistent_with_eliminated_rows() -> None:
    base = nlp_formulation()
    formulation = dataclasses.replace(
        base,
        decisions=base.decisions + (Decision("U-FLASH.P_spec", 5e4, 2e5, 1e5),),
        starts=tuple((*start, 1e5) for start in base.starts),
    )
    ready = _ready(formulation)
    assert ready.codes == ("DECISION_INCONSISTENT_WITH_ELIMINATED_ROWS",)
    assert {reason.subject for reason in ready.reasons} == {"U-FLASH.P_spec"}
    for start in ready.starts:
        assert start.alias_residuals is not None
        assert abs(start.alias_residuals["U-FLASH.P_spec"] - 1.0) <= 1e-12  # type: ignore[operator]


def test_a33_unknown_variable() -> None:
    formulation = dataclasses.replace(
        nlp_formulation(), objective=QuadraticExpression(linear={"S9.T": 1.0})
    )
    assert _ready(formulation).codes == ("UNKNOWN_VARIABLE",)


def test_a33_hessian_unavailable() -> None:
    assert _ready(nlp_formulation(hessian="exact")).codes == ("HESSIAN_UNAVAILABLE",)


def test_a33_simulation_not_ready() -> None:
    formulation = _with_decision(
        nlp_formulation(), 1, Decision("U-FLASH.T_spec", 356.0, 445.0, 100.0)
    )
    formulation = dataclasses.replace(formulation, starts=((0.6, 445.0),))
    ready = _ready(formulation)
    assert ready.codes == ("SIMULATION_NOT_READY",)
    assert "SPECIFICATION_REFUSED" in ready.reasons[0].detail


def test_a33_validate_for_optimization_is_still_r129s_unsupported(tmp_path: Path) -> None:
    from openflowsheet.application.types import Change, Edit

    document = CORPUS["SYN-001-nominal"]()
    with LocalApplication.create(tmp_path / "project", project_id="m03-a33") as app:
        edits = tuple(Edit("set", (key,), value) for key, value in document.items())
        revision_id = app.commit_change(Change(edits=edits), None, "seed").revision_id
        assert revision_id is not None
        with pytest.raises(ApplicationError) as refused:
            app.validate(revision_id, "optimization")
    assert refused.value.error.as_document()["code"] == "unsupported"
    assert refused.value.error.as_document()["message"] == "task_unsupported(optimization)"


# -- A34: optimize() without the extra -------------------------------------------------------------


def test_a34_optimize_without_the_extra_is_a_typed_unsupported_report() -> None:
    report = optimize(nlp_formulation(), flowsheet({}))
    assert report.status == "UNSUPPORTED"
    assert report.reason_codes == ("NLP_SOLVER_UNAVAILABLE",)
    assert report.candidate is None
    assert report.starts == ()
    assert report.distinct_local_solutions == 0
    assert report.claims == {
        "global_optimality": False,
        "local_stationarity": False,
        "second_order": "not_assessed",
    }
    document = report.as_document()
    assert document["schema_version"] == "optimization-report-v1"
    assert document["hessian_policy"] == dict(HESSIAN_POLICY)
    assert document["solver"]["options"] == dict(IPOPT_OPTIONS)
    assert document["solver"]["audit"]["document"] == AUDIT_DOCUMENT
    assert document["formulation"]["kind"] == "full_space"
    assert (
        document["model"]["model_version"]
        == compile_problem(flowsheet({}).spec()).metadata.model_version
    )


def test_a34_a_ready_closure_without_the_adapter_is_still_unsupported_and_never_raises() -> None:
    report = optimize(nlp_formulation(), flowsheet({}), solver_probe=available)
    assert report.status == "UNSUPPORTED"
    assert report.reason_codes == ("NLP_SOLVER_UNAVAILABLE",)
    assert "could not be imported" in report.reasons[0].detail


def test_the_nlp_capability_requires_the_licence_acceptance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """M03 review F4: `audited_solver()` checks `NLP_LICENCES_ACCEPTED` (N1), so declining N1
    withdraws `optimize()`'s capability even where the extra is installed."""
    import openflowsheet.studies.nlp.closure as closure_module

    monkeypatch.setattr(closure_module, "NLP_LICENCES_ACCEPTED", False)
    solver = closure_module.audited_solver()
    assert not solver.available
    assert "not accepted (N1)" in solver.detail
    monkeypatch.setattr(closure_module, "NLP_LICENCES_ACCEPTED", True)
    assert "N1" not in closure_module.audited_solver().detail


def test_a34_an_exact_hessian_request_is_refused_before_any_solver_call() -> None:
    report = optimize(nlp_formulation(hessian="exact"), flowsheet({}))
    assert report.status == "UNSUPPORTED"
    assert report.reason_codes == ("HESSIAN_UNAVAILABLE", "NLP_SOLVER_UNAVAILABLE")


def test_a_check_detail_cannot_overwrite_the_verdict_in_its_record() -> None:
    from openflowsheet.studies.nlp.verification import VerificationCheck
    from openflowsheet.studies.sensitivity import QualificationOutcome

    with pytest.raises(ValueError, match="overwrite"):
        VerificationCheck("V1", "pass", {"outcome": "CONVERGED"})
    with pytest.raises(ValueError, match="reserved"):
        QualificationOutcome("Q1", "pass", {"qualification": "Q2"})
