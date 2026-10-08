"""M03 WO-3: SYN-001 sensitivities against closed forms (spec §4) — A01 (every state), A05-A09,
A16, A17, A19.

The expectations are the design lane's 60-digit closed forms (`m03_reference.py`), which import
nothing from `openflowsheet`; they are the independent check. The finite-difference oracle (A09)
shares the production solver and property backend with the implicit path, so it is a consistency
test and not validation (blueprint §5.2; spec §15) — it is here because a twin row that ignored its
parameter would pass a self-consistent implicit computation and fail it by O(1e-2).

Every tolerance is on the scaled sensitivity `Ŝ = (∂y/∂p) s_p / s_y` (spec §2, §4.7).
"""

from __future__ import annotations

from functools import cache
from typing import Any

import numpy as np
import numpy.typing as npt
import pytest
from m03_support import (
    PRESSURE_PARAMETERS,
    REGISTERED_PARAMETERS,
    converged_sweep_states,
    fd_sensitivity,
    number,
    pressure_parameters,
    reference,
    registered_outputs,
    registered_parameters,
    solved,
)

from openflowsheet.compile.casadi_backend import compile_parametric_twin
from openflowsheet.compile.reference import state_vector
from openflowsheet.orchestrator.tear import Syn001TearProblem
from openflowsheet.studies.sensitivity import SensitivityResult
from openflowsheet.studies.syn001 import split_regimes, syn001_sensitivity
from openflowsheet.verify.certificate import verify

TAU_ABS = 1e-11
TAU_REL = 1e-10
TAU_FD = 1e-9
MARGIN = 1e-12
SENSITIVITY_STATES = ("P1", "P2", "P3")
BOUNDARY_STATES = ("B1", "B2", "B3")


@cache
def certificate(state: str) -> Any:
    sheet, result = solved(state)
    return verify(sheet, result)


@cache
def sensitivity(
    state: str, mode: str = "both", parameters: str = "registered"
) -> SensitivityResult:
    sheet, result = solved(state)
    chosen = registered_parameters()
    if parameters == "with_pressures":
        chosen = chosen + pressure_parameters()
    return syn001_sensitivity(
        sheet,
        result,
        parameters=chosen,
        outputs=registered_outputs(),
        mode=mode,  # type: ignore[arg-type]
        certificate=certificate(state),
    )


def expected_scaled(state: str) -> npt.NDArray[np.float64]:
    """The JSON's closed-form `∂y/∂p`, scaled: rows the twelve outputs, columns the five."""
    table = reference()["sensitivity_states"][state]["sensitivity"]
    return np.array(
        [
            [
                number(table[output.output_id][parameter.parameter_id])
                * parameter.scale
                / output.scale
                for parameter in registered_parameters()
            ]
            for output in registered_outputs()
        ]
    )


def matrix(block: Any) -> npt.NDArray[np.float64]:
    values = np.array(block.scaled, dtype=object)
    assert not any(value is None for value in values.ravel())
    return values.astype(float)


def assert_within(
    measured: npt.NDArray[np.float64], expected: npt.NDArray[np.float64], label: str
) -> None:
    allowed = TAU_ABS + TAU_REL * np.abs(expected)
    error = np.abs(measured - expected)
    assert np.all(error <= allowed), (label, float(np.max(error / allowed)))


# -- A01 at every state ---------------------------------------------------------------------------


@pytest.mark.parametrize("state", SENSITIVITY_STATES + BOUNDARY_STATES + converged_sweep_states())
def test_a01_the_twin_is_bitwise_the_base_at_every_registered_state(state: str) -> None:
    """Q-F1: measured bitwise at all 14 states; the guard (Q0′) passes at each."""
    sheet, result = solved(state)
    assert result.final_state is not None
    tear = Syn001TearProblem(sheet)
    x = np.array(state_vector(tear.spec, result.final_state))
    subset = REGISTERED_PARAMETERS + PRESSURE_PARAMETERS
    twin = compile_parametric_twin(tear.spec, subset)
    p0 = {name: tear.spec.parameters[name] for name in subset}
    base = tear.compiled.residual(x, tear.context)
    base_jacobian = tear.compiled.jacobian(x, tear.context)
    twin_jacobian = twin.jacobian_x(x, p0)
    assert np.array_equal(np.asarray(twin.residual(x, p0)) + 0.0, np.asarray(base.values) + 0.0)
    assert twin_jacobian.indptr == base_jacobian.indptr
    assert twin_jacobian.indices == base_jacobian.indices
    assert np.array_equal(
        np.asarray(twin_jacobian.data) + 0.0, np.asarray(base_jacobian.data) + 0.0
    )
    assert twin.model_version == tear.compiled.metadata.model_version

    outcome = syn001_sensitivity(
        sheet,
        result,
        parameters=registered_parameters(),
        outputs=registered_outputs()[:1],
        mode="forward",
    ).outcome("Q0'")
    assert outcome.outcome == "pass", outcome


# -- A05, A06, A07 --------------------------------------------------------------------------------


@pytest.mark.parametrize("state", SENSITIVITY_STATES)
def test_a05_forward_sensitivities_are_the_closed_form(state: str) -> None:
    result = sensitivity(state, "forward")
    assert result.status == "QUALIFIED", result.refusals
    assert result.adjoint is None
    assert_within(matrix(result.forward), expected_scaled(state), f"{state} forward")


@pytest.mark.parametrize("state", SENSITIVITY_STATES)
def test_a06_adjoint_sensitivities_are_the_closed_form(state: str) -> None:
    result = sensitivity(state, "adjoint")
    assert result.status == "QUALIFIED", result.refusals
    assert result.forward is None
    assert_within(matrix(result.adjoint), expected_scaled(state), f"{state} adjoint")


@pytest.mark.parametrize("state", SENSITIVITY_STATES)
def test_a07_forward_and_adjoint_agree_entry_by_entry(state: str) -> None:
    result = sensitivity(state, "both")
    forward, adjoint = matrix(result.forward), matrix(result.adjoint)
    difference = np.abs(forward - adjoint)
    assert np.all(difference <= TAU_ABS + TAU_REL * np.max(np.abs(forward)))
    assert result.consistency is not None
    assert result.consistency["max_abs_difference"] == float(np.max(difference))
    assert result.consistency["within_tolerance"] is True
    # The unscaled block is `S_y Ŝ S_p⁻¹` of the scaled one.
    unscaled = np.array(result.forward.unscaled, dtype=float)  # type: ignore[union-attr]
    for row, output in enumerate(registered_outputs()):
        for column, parameter in enumerate(registered_parameters()):
            assert unscaled[row, column] == output.scale * forward[row, column] / parameter.scale


# -- A08 ------------------------------------------------------------------------------------------


@pytest.mark.parametrize("state", SENSITIVITY_STATES)
def test_a08_every_registered_structural_zero_is_reproduced(state: str) -> None:
    forward = matrix(sensitivity(state, "forward").forward)
    rows = {output.output_id: index for index, output in enumerate(registered_outputs())}
    columns = {name: index for index, name in enumerate(REGISTERED_PARAMETERS)}
    zeros = reference()["sensitivity_states"][state]["structural_zeros"]
    assert zeros
    for output_id, parameter_id, _ in zeros:
        assert output_id in rows, output_id  # every registered zero is on a requested output
        assert abs(forward[rows[output_id], columns[parameter_id]]) <= TAU_ABS, (
            state,
            output_id,
            parameter_id,
        )


def test_a08_the_heater_vapour_row_is_live_at_p3_where_it_is_zero_at_p1() -> None:
    p1 = matrix(sensitivity("P1", "forward").forward)
    p3 = matrix(sensitivity("P3", "forward").forward)
    row = [output.output_id for output in registered_outputs()].index("S3.V")
    for column, name in enumerate(REGISTERED_PARAMETERS):
        if name == "U-FEED.T_spec":
            continue  # universal: T_feed changes no flow (spec §4.3 item 2)
        assert abs(p1[row, column]) <= TAU_ABS
        assert abs(p3[row, column]) >= 1e-3, name


# -- A09 ------------------------------------------------------------------------------------------


@pytest.mark.parametrize("state", ["P1", "P3"])
def test_a09_the_finite_difference_oracle_agrees(state: str) -> None:
    implicit = matrix(sensitivity(state, "forward").forward)
    oracle = fd_sensitivity(state, registered_parameters(), registered_outputs())
    assert oracle.shape == implicit.shape == (12, 5)
    assert np.max(np.abs(oracle - implicit)) <= TAU_FD


# -- A16 ------------------------------------------------------------------------------------------


@pytest.mark.parametrize("state", ["B1", "B2"])
def test_a16_a_state_inside_tau_regime_is_refused_phase_boundary_only(state: str) -> None:
    registered = reference()["boundary_states"][state]
    result = sensitivity(state, "both")
    assert result.status == "REFUSED"
    assert result.refusal_codes == ("PHASE_BOUNDARY",)
    flash = next(split for split in result.splits if split.unit_id == "U-FLASH")
    assert flash.regime == registered["flash_regime"]
    assert flash.margin is not None
    assert abs(flash.margin - number(registered["flash_margin"])) <= MARGIN
    heater = next(split for split in result.splits if split.unit_id == "U-HEAT")
    assert heater.regime == registered["heater_regime"]
    assert result.outcome("Q1'").outcome == "pass"
    assert result.outcome("Q1'").detail["verification_status"] == "VERIFIED"
    assert result.regularity is not None
    assert result.regularity.status == "NO_RANK_LOSS_DETECTED"
    assert result.forward is not None and result.adjoint is not None
    assert all(value is None for row in result.forward.scaled for value in row)
    assert all(value is None for row in result.adjoint.scaled for value in row)
    assert result.consistency is None


def test_a16_b3_lists_every_failing_qualification_in_order() -> None:
    result = sensitivity("B3", "both")
    assert result.status == "REFUSED"
    codes = result.refusal_codes
    for code in ("ROOT_NOT_VERIFIED", "ILL_CONDITIONED", "PHASE_BOUNDARY"):
        assert code in codes
    assert (
        codes.index("ROOT_NOT_VERIFIED")
        < codes.index("ILL_CONDITIONED")
        < codes.index("PHASE_BOUNDARY")
    )
    assert result.outcome("Q1'").detail["verification_status"] == "UNVERIFIED"
    assert all(value is None for row in result.forward.scaled for value in row)  # type: ignore[union-attr]


# -- A17 ------------------------------------------------------------------------------------------


def test_a17_a_pressure_alone_leaves_the_solution_set_and_only_its_column_is_refused() -> None:
    combined = sensitivity("P1", "both", "with_pressures")
    alone = sensitivity("P1", "both")
    assert combined.status == "PARTIALLY_QUALIFIED"
    assert [
        (refusal.code, refusal.scope, refusal.parameter_id) for refusal in combined.refusals
    ] == [("INCONSISTENT_WITH_ELIMINATED_ROWS", "column", name) for name in PRESSURE_PARAMETERS]
    by_id = {column.parameter_id: column for column in combined.parameters}
    for name in PRESSURE_PARAMETERS:
        assert by_id[name].status == "REFUSED"
        assert by_id[name].alias_residual is not None
        assert abs(by_id[name].alias_residual - 1.0) <= MARGIN
    for name in REGISTERED_PARAMETERS:
        assert by_id[name].status == "QUALIFIED"
        assert by_id[name].alias_residual is not None
        assert by_id[name].alias_residual <= 1e-8

    for block_name in ("forward", "adjoint"):
        combined_block = getattr(combined, block_name)
        alone_block = getattr(alone, block_name)
        for combined_row, alone_row in zip(combined_block.scaled, alone_block.scaled, strict=True):
            assert combined_row[5:] == (None, None)
            # Bitwise: the five qualified columns do not depend on which others were requested.
            assert [value.hex() for value in combined_row[:5]] == [  # type: ignore[union-attr]
                value.hex()
                for value in alone_row  # type: ignore[union-attr]
            ]


# -- A19 ------------------------------------------------------------------------------------------


@pytest.mark.parametrize("state", SENSITIVITY_STATES)
def test_a19_the_regime_margins_are_the_closed_form(state: str) -> None:
    registered = reference()["sensitivity_states"][state]["regime_margins"]
    sheet, result = solved(state)
    assert result.final_state is not None
    splits = {split.unit_id: split for split in split_regimes(sheet, result.final_state)}
    assert set(splits) == {"U-HEAT", "U-FLASH"}
    for unit_id in ("U-HEAT", "U-FLASH"):
        assert splits[unit_id].kind == "TP"
        assert splits[unit_id].regime == registered[unit_id]["regime"], unit_id
        assert splits[unit_id].margin is not None
        assert abs(splits[unit_id].margin - number(registered[unit_id]["margin"])) <= MARGIN
    assert sensitivity(state, "both").outcome("Q4").outcome == "pass"
