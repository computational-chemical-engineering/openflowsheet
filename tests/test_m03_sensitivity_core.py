"""M03 WO-2: the sensitivity core (spec §3.3-§3.7, §5) — A03, A07 (toy), A10-A15, A18, A20, A04.

The toys test the qualification mapping and the transposition, not the [A08] screen (K04's tests
own the screen; spec §15). `x² − p` at `p = 0` is the case the whole policy exists for: its
residual is exactly zero and its sensitivity does not exist, and a study that reported one would be
relabelling residual satisfaction as regularity (blueprint §8.1). The linear toy's `C = [1, 10]`
separates `Ĉ X̂` from the missing-transpose value `[−13, 7]` by O(1).

A03 and A10 are counted rather than inspected: a finite-difference fallback would show as extra
residual evaluations, re-solves or factorizations long before it showed as a wrong digit.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable, Sequence
from typing import Any

import numpy as np
import pytest
from m03_support import (
    REGISTERED_PARAMETERS,
    linear_spec,
    reference,
    registered_outputs,
    registered_parameters,
    solved,
    syn001_host,
    toy_host,
    toy_parameter,
    x_squared_spec,
)

from openflowsheet.compile.casadi_backend import ParametricTwin, compile_parametric_twin
from openflowsheet.compile.spec import EquationSpec, ProblemSpec
from openflowsheet.compiled import EvaluationContext
from openflowsheet.models.syn001.flowsheet import Syn001Flowsheet
from openflowsheet.numerics import linear
from openflowsheet.orchestrator import tear as tear_module
from openflowsheet.studies.sensitivity import (
    POLICY_ID,
    CertificateEvidence,
    OutputFunctional,
    SensitivityHost,
    SensitivityRequest,
    SensitivityResult,
    evaluate_sensitivity,
)
from openflowsheet.verify.certificate import verify

#: Spec §4.7 and §5.
TAU_ABS = 1e-11
TAU_REL = 1e-10
#: A12 (spec §5, Amendment 1): §4.7's tau_abs. Measured 2.13e-14 (C = [1, 10]) and 6.2e-15
#: (X); the a priori estimate of the 2 x 2 solve is 4.4e-12 (generator claim C6).
TOY_LINEAR = TAU_ABS


def x_squared(p: float, x: float, *, mode: str = "both", convert: bool = False) -> Any:
    host, context = toy_host(x_squared_spec(p, convert=convert))
    request = SensitivityRequest(
        context,
        (toy_parameter("p"),),
        (OutputFunctional.of_variable("x", 1.0),),
        mode,  # type: ignore[arg-type]
    )
    return host, evaluate_sensitivity(host, np.array([x]), request)


def linear_toy(delta: float, outputs: Sequence[OutputFunctional], mode: str = "both") -> Any:
    host, context = toy_host(linear_spec(delta))
    request = SensitivityRequest(
        context,
        (toy_parameter("p1"), toy_parameter("p2")),
        tuple(outputs),
        mode,  # type: ignore[arg-type]
    )
    return evaluate_sensitivity(host, np.array([1.0, 0.0]), request)


def all_null(result: SensitivityResult) -> bool:
    blocks = [block for block in (result.forward, result.adjoint) if block is not None]
    return bool(blocks) and all(
        value is None
        for block in blocks
        for matrix in (block.scaled, block.unscaled)
        for row in matrix
        for value in row
    )


IDENTITY_OUTPUTS = (
    OutputFunctional.of_variable("x1", 1.0),
    OutputFunctional.of_variable("x2", 1.0),
)
C_OUTPUT = (OutputFunctional("C", {"x1": 1.0, "x2": 10.0}, 1.0),)


# -- A11, A12, A07 (toy) --------------------------------------------------------------------------


@pytest.mark.parametrize("mode", ["forward", "adjoint", "both"])
def test_a11_x_squared_at_a_quarter_is_qualified_with_derivative_one(mode: str) -> None:
    _, result = x_squared(0.25, 0.5, mode=mode)
    assert result.status == "QUALIFIED"
    assert result.refusals == ()
    for block in (result.forward, result.adjoint):
        if block is not None:
            assert abs(block.scaled[0][0] - 1.0) <= 1e-15  # type: ignore[operator]
            assert block.unscaled == block.scaled


def test_a12_the_linear_toy_inverts_and_transposes_correctly() -> None:
    expected_x = reference()["toys"]["linear_2x2"]["states"][0]
    result = linear_toy(1.0, IDENTITY_OUTPUTS, mode="forward")
    assert result.status == "QUALIFIED"
    inverse = np.array(result.forward.scaled, dtype=float)
    assert np.max(np.abs(inverse - np.array(expected_x["dx_dp"], dtype=float))) <= TOY_LINEAR

    for mode in ("forward", "adjoint"):
        block = linear_toy(1.0, C_OUTPUT, mode=mode)
        values = np.array(getattr(block, mode).scaled, dtype=float)
        assert np.max(np.abs(values - np.array(expected_x["dy_dp"], dtype=float))) <= TOY_LINEAR
        # The missing-transpose value is O(1) away, so "not equal" means "not even near".
        missing = np.array(expected_x["missing_transpose_value"], dtype=float)
        assert np.min(np.abs(values - missing)) > 0.5


@pytest.mark.parametrize(
    "case", ["x_squared", "linear_identity", "linear_c"], ids=lambda case: str(case)
)
def test_a07_toy_forward_and_adjoint_agree_and_the_record_says_by_how_much(case: str) -> None:
    if case == "x_squared":
        _, result = x_squared(0.25, 0.5)
    else:
        result = linear_toy(1.0, IDENTITY_OUTPUTS if case == "linear_identity" else C_OUTPUT)
    forward = np.array(result.forward.scaled, dtype=float)
    adjoint = np.array(result.adjoint.scaled, dtype=float)
    difference = np.abs(forward - adjoint)
    assert np.all(difference <= TAU_ABS + TAU_REL * np.max(np.abs(forward)))
    assert result.consistency is not None
    assert result.consistency["max_abs_difference"] == float(np.max(difference))
    assert result.consistency["within_tolerance"] is True


# -- A13, A14, A15 --------------------------------------------------------------------------------


def test_a13_a_zero_residual_at_a_singular_root_is_refused_not_differentiated() -> None:
    host, result = x_squared(0.0, 0.0)
    context = EvaluationContext(
        host.compiled.metadata.model_version, host.compiled.metadata.constants_sha256
    )
    assert host.compiled.residual(np.array([0.0]), context).values == (0.0,)
    assert result.status == "REFUSED"
    assert result.refusal_codes == ("RANK_DEFICIENT",)
    assert all_null(result)
    assert result.outcome("Q1").outcome == "pass"  # residual satisfied, still refused


def test_a14_the_singular_linear_toy_is_rank_deficient() -> None:
    result = linear_toy(0.0, C_OUTPUT)
    assert result.status == "REFUSED"
    assert result.refusal_codes == ("RANK_DEFICIENT",)
    assert all_null(result)


def test_a15_ill_conditioning_is_refused_with_the_screens_reason() -> None:
    _, absolute = x_squared(1e-20, 1e-10)
    assert absolute.refusal_codes == ("ILL_CONDITIONED",)
    assert absolute.regularity is not None
    assert absolute.regularity.ill_conditioned_reason == "absolute"
    assert all_null(absolute)

    relative = linear_toy(1e-12, C_OUTPUT)
    assert relative.refusal_codes == ("ILL_CONDITIONED",)
    assert relative.regularity is not None
    assert relative.regularity.ill_conditioned_reason == "relative"
    assert all_null(relative)


# -- A04 (study level) ----------------------------------------------------------------------------


def test_a04_an_unknown_parameter_is_a_typed_refusal() -> None:
    host, context = toy_host(x_squared_spec(0.25))
    request = SensitivityRequest(
        context, (toy_parameter("q"),), (OutputFunctional.of_variable("x", 1.0),), "both"
    )
    result = evaluate_sensitivity(host, np.array([0.5]), request)
    assert result.status == "REFUSED"
    assert result.refusal_codes == ("UNKNOWN_PARAMETER",)
    assert all_null(result)


def test_a04_a_builder_that_cannot_take_a_symbol_is_a_typed_refusal() -> None:
    _, result = x_squared(0.25, 0.5, convert=True)
    assert result.status == "REFUSED"
    assert result.refusal_codes == ("PARAMETER_NOT_DIFFERENTIABLE",)
    assert result.refusals[0].parameter_id == "p"
    assert all_null(result)


# -- A01's test double: an altered row is a TWIN_MISMATCH ------------------------------------------


def one_ulp_off(spec: ProblemSpec, equation_id: str) -> ProblemSpec:
    """`spec` with one row multiplied by `1 + 2⁻⁵²`: one ulp in that row's Jacobian entries."""

    def altered(equation: EquationSpec) -> EquationSpec:
        if equation.equation_id != equation_id:
            return equation
        build = equation.build

        def scaled(*arguments: Any) -> Any:
            return build(*arguments) * (1.0 + 2.0**-52)

        return dataclasses.replace(equation, build=scaled)

    return dataclasses.replace(spec, equations=tuple(altered(e) for e in spec.equations))


def test_a01_a_twin_with_one_row_altered_is_refused_twin_mismatch() -> None:
    host, tear, x = syn001_host("P1")
    row = "U-SPLIT:SPLIT-recycle:A"

    def factory(spec: ProblemSpec, ids: Sequence[str]) -> ParametricTwin:
        return compile_parametric_twin(one_ulp_off(spec, row), ids)

    request = SensitivityRequest(
        tear.context, registered_parameters(), registered_outputs(), "both"
    )
    result = evaluate_sensitivity(host, x, request, twin_factory=factory)
    assert result.status == "REFUSED"
    assert result.refusal_codes == ("TWIN_MISMATCH",)
    guard = result.outcome("Q0'")
    assert guard.outcome == "fail"
    assert guard.detail["jacobian_entries_differing"] > 0
    assert guard.detail["max_abs_difference"] < 1e-12  # a one-ulp defect is still refused
    assert result.outcome("Q3").outcome == "not_evaluated"
    assert all_null(result)


# -- A03, A10 -------------------------------------------------------------------------------------


class Counting:
    """Counts calls of named methods on a wrapped object, delegating everything else."""

    def __init__(self, wrapped: Any, names: Sequence[str]) -> None:
        self._wrapped = wrapped
        self.calls = dict.fromkeys(names, 0)

    def __getattr__(self, name: str) -> Any:
        attribute = getattr(self._wrapped, name)
        if name not in self.calls:
            return attribute

        def counted(*arguments: Any, **keywords: Any) -> Any:
            self.calls[name] += 1
            return attribute(*arguments, **keywords)

        return counted


def certificate_for(state: str) -> CertificateEvidence:
    sheet, result = solved(state)
    return CertificateEvidence.of(verify(sheet, result))


def test_a03_a_core_request_evaluates_each_function_once_and_solves_no_flowsheet(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    host, tear, x = syn001_host("P1")
    certificate = certificate_for("P1")
    base = Counting(host.compiled, ["residual", "jacobian"])
    counted_host = SensitivityHost(host.spec, base, host.scaling, host.eliminated_rows)  # type: ignore[arg-type]
    twins: list[Counting] = []

    def factory(spec: ProblemSpec, ids: Sequence[str]) -> ParametricTwin:
        twin = Counting(
            compile_parametric_twin(spec, ids), ["residual", "jacobian_x", "jacobian_p"]
        )
        twins.append(twin)
        return twin  # type: ignore[return-value]

    solves: list[str] = []
    traverse = Syn001Flowsheet.traverse

    def counted_traverse(self: Syn001Flowsheet, *arguments: Any) -> Any:
        solves.append("traverse")
        return traverse(self, *arguments)

    def counted_solve(*arguments: Any, **keywords: Any) -> Any:
        solves.append("solve_tear")
        raise AssertionError("a sensitivity request must not re-solve the flowsheet")

    monkeypatch.setattr(Syn001Flowsheet, "traverse", counted_traverse)
    monkeypatch.setattr(tear_module, "solve_tear", counted_solve)

    request = SensitivityRequest(
        tear.context, registered_parameters(), registered_outputs(), "both"
    )
    assert len(request.parameters) == 5 and len(request.outputs) == 12
    result = evaluate_sensitivity(
        counted_host, x, request, certificate=certificate, twin_factory=factory
    )
    assert result.status == "QUALIFIED"
    assert base.calls == {"residual": 1, "jacobian": 1}
    assert len(twins) == 1
    assert twins[0].calls == {"residual": 1, "jacobian_x": 1, "jacobian_p": 1}
    assert solves == []


def counting_factorizations(run: Callable[[], SensitivityResult]) -> tuple[int, SensitivityResult]:
    factorizations: list[int] = []
    original = linear.splu

    def counted(*arguments: Any, **keywords: Any) -> Any:
        factorizations.append(1)
        return original(*arguments, **keywords)

    linear.splu = counted
    try:
        result = run()
    finally:
        linear.splu = original
    return len(factorizations), result


def test_a10_the_factorization_count_does_not_depend_on_parameters_or_outputs() -> None:
    host, tear, x = syn001_host("P1")
    large = SensitivityRequest(tear.context, registered_parameters(), registered_outputs(), "both")
    small = SensitivityRequest(
        tear.context, registered_parameters()[:1], registered_outputs()[:1], "forward"
    )
    large_count, large_result = counting_factorizations(
        lambda: evaluate_sensitivity(host, x, large)
    )
    small_count, small_result = counting_factorizations(
        lambda: evaluate_sensitivity(host, x, small)
    )
    assert large_result.status == small_result.status == "QUALIFIED"
    # One for the [A08] screen (K04 §7.5: it factorizes what it judges), one for the solves.
    assert large_count == small_count == 2
    assert [record.dimension for record in large_result.linear_solves] == [47, 47]
    assert len(small_result.linear_solves) == 1


# -- A18, A20 -------------------------------------------------------------------------------------


def test_a18_a_state_off_the_root_is_refused_before_the_screen() -> None:
    host, tear, x = syn001_host("P1")
    moved = x.copy()
    moved[tear.spec.variable_ids.index("S2.T")] += 1.0
    request = SensitivityRequest(
        tear.context, registered_parameters(), registered_outputs(), "both"
    )
    result = evaluate_sensitivity(host, moved, request)
    assert result.status == "REFUSED"
    assert result.refusal_codes[0] == "ROOT_NOT_CONVERGED"
    assert result.outcome("Q2").outcome == "not_evaluated"
    assert result.regularity is None
    assert all_null(result)


def test_a20_a_context_that_pins_other_constants_is_refused_before_any_evaluation() -> None:
    host, tear, x = syn001_host("P1")
    base = Counting(host.compiled, ["residual", "jacobian"])
    counted_host = SensitivityHost(host.spec, base, host.scaling, host.eliminated_rows)  # type: ignore[arg-type]
    built: list[int] = []

    def factory(spec: ProblemSpec, ids: Sequence[str]) -> ParametricTwin:
        built.append(1)
        return compile_parametric_twin(spec, ids)

    other = dataclasses.replace(tear.context, constants_sha256="f" * 64)
    request = SensitivityRequest(other, registered_parameters(), registered_outputs(), "both")
    result = evaluate_sensitivity(counted_host, x, request, twin_factory=factory)
    assert result.status == "REFUSED"
    assert result.refusal_codes == ("IDENTITY_MISMATCH",)
    assert base.calls == {"residual": 0, "jacobian": 0}
    assert built == []
    assert all(
        item.outcome == "not_evaluated"
        for item in result.qualification
        if item.qualification != "Q0"
    )
    assert all_null(result)


def test_a20_a_qualified_result_carries_the_base_evaluations_identity() -> None:
    host, tear, x = syn001_host("P1")
    request = SensitivityRequest(
        tear.context, registered_parameters(), registered_outputs(), "both"
    )
    result = evaluate_sensitivity(host, x, request)
    evaluation = tear.compiled.residual(x, tear.context)
    assert result.status == "QUALIFIED"
    assert result.policy_id == POLICY_ID == "M03-sensitivity-v1"
    assert (
        result.model_version,
        result.constants_sha256,
        result.state_sha256,
        result.phase_signature,
    ) == (
        evaluation.model_version,
        evaluation.constants_sha256,
        evaluation.state_sha256,
        evaluation.phase_signature,
    )
    assert result.derivative_provenance == "implicit-exact"
    assert [column.parameter_id for column in result.parameters] == list(REGISTERED_PARAMETERS)
