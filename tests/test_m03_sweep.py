"""M03 WO-4: sweeps of one pinned input (spec §6) — A21-A24.

The registered sweep is SYN-001 at r = 0.5 over nine flash temperatures, one of them outside the
provider's declared domain. The expected values are the design lane's closed forms
(`benchmarks/m03/reference_values.json`, `sweep`); the single-phase points carry registered zeros of
∂V/∂T_f with their non-vanishing counterparts in the same sweep (spec §6, claim C7).
"""

from __future__ import annotations

import json
from functools import cache
from typing import Any

import pytest
from m03_support import FLOWSHEET_CONTEXT, number, record_measurement, reference

from openflowsheet.models.syn001.flowsheet import Syn001Flowsheet
from openflowsheet.studies.sensitivity import OutputFunctional, StudyParameter
from openflowsheet.studies.sweep import SweepResult, SweepSensitivity, run_sweep
from openflowsheet.thermo.syn001 import Syn001Provider

#: A21's tolerance on the outputs, and A22's on the scaled sensitivity.
OUTPUT_ABS = 1e-9
OUTPUT_REL = 1e-10
TAU_ABS = 1e-11
TAU_REL = 1e-10

FLOW_SCALE = 3.0
T_F = StudyParameter("U-FLASH.T_spec", 100.0, 280.0, 440.0)
OUTPUTS = (
    OutputFunctional.of_variable("S4.N", FLOW_SCALE),
    OutputFunctional.of_variable("S5.N", FLOW_SCALE),
)
SENSITIVITY = SweepSensitivity(
    parameters=(T_F,), outputs=(OutputFunctional.of_variable("S4.N", FLOW_SCALE),)
)


def registered() -> tuple[Syn001Flowsheet, str, tuple[float, ...]]:
    sweep = reference()["sweep"]
    sheet = Syn001Flowsheet(
        provider=Syn001Provider(),
        context=FLOWSHEET_CONTEXT,
        split_fraction=number(sweep["split_fraction"]),
    )
    parameter = sweep["parameter"]
    return sheet, parameter, tuple(number(point[parameter]) for point in sweep["points"])


@cache
def sweep(order: str = "forward", max_points: int | None = None) -> SweepResult:
    sheet, parameter, values = registered()
    if order == "reverse":
        values = values[::-1]
    return run_sweep(
        sheet, parameter, values, OUTPUTS, sensitivity=SENSITIVITY, max_points=max_points
    )


def canonical(document: object) -> str:
    """A byte-exact rendering: `json` writes −0.0 and every binary64 by its shortest `repr`."""
    return json.dumps(document, sort_keys=True, allow_nan=False)


def test_a21_the_registered_sweep_records_every_point_in_input_order(record_property: Any) -> None:
    result = sweep()
    expected = reference()["sweep"]["points"]
    _, parameter, values = registered()
    assert result.parameter_id == parameter
    assert result.start == "registered_initializer"
    assert [point.value for point in result.points] == list(values)
    worst = 0.0
    for point, entry in zip(result.points, expected, strict=True):
        if entry["expected_outcome"] == "CONVERGED":
            assert point.outcome == "CONVERGED", (point.value, point.message)
            assert point.solve_outcome == "CONVERGED"
            assert point.certificate_status == entry["expected_certificate"] == "VERIFIED"
            assert point.root_fingerprint is not None
            assert point.state_sha256 == point.root_fingerprint["full_state_sha256"]
            assert point.outputs is not None
            for output in ("S4.N", "S5.N"):
                closed = number(entry[output])
                error = abs(point.outputs[output] - closed)
                assert error <= OUTPUT_ABS + OUTPUT_REL * abs(closed), (point.value, output)
                worst = max(worst, error / (OUTPUT_ABS + OUTPUT_REL * abs(closed)))
        else:
            assert point.outcome == "SPECIFICATION_REFUSED" == entry["expected_outcome"]
            assert "outside the declared domain" in point.message
            assert point.outputs is None
            assert point.sensitivity is None
            assert point.certificate_status is None
            assert point.root_fingerprint is None
    record_measurement(
        record_property,
        "A21",
        "max over converged points of |y - y*| / (1e-9 + 1e-10 |y*|), S4.N and S5.N",
        worst,
        1.0,
    )
    assert result.summary == {
        "total": 9,
        "converged": 8,
        "verified": 8,
        "sensitivity_qualified": 8,
        "failed": 1,
        "not_run": 0,
    }
    assert result.status == "COMPLETE"


def test_a22_the_sweep_sensitivity_is_the_closed_form_and_zero_only_where_single_phase(
    record_property: Any,
) -> None:
    result = sweep()
    worst = worst_abs = 0.0
    for point, entry in zip(result.points, reference()["sweep"]["points"], strict=True):
        if entry["expected_outcome"] != "CONVERGED":
            continue
        assert point.sensitivity is not None
        assert point.sensitivity.status == entry["expected_sensitivity"] == "QUALIFIED"
        assert point.sensitivity.forward is not None
        (value,) = point.sensitivity.forward.scaled[0]
        assert value is not None
        closed = number(entry["dS4.N_dT_f"]) * T_F.scale / FLOW_SCALE
        error = abs(value - closed)
        assert error <= TAU_ABS + TAU_REL * abs(closed), (point.value, value, closed)
        worst = max(worst, error / (TAU_ABS + TAU_REL * abs(closed)))
        worst_abs = max(worst_abs, error)
        single_phase = entry["flash_regime"] in ("LIQUID", "VAPOR")
        assert (closed == 0.0) == single_phase
        if not single_phase:
            assert abs(value) > 1e-3
    record_measurement(
        record_property,
        "A22",
        "max over converged points of |S - S*| / (1e-11 + 1e-10 |S*|), scaled",
        worst,
        1.0,
    )


def test_a23_a_reversed_sweep_reproduces_every_point_record_bitwise() -> None:
    forward = sweep()
    reverse = sweep("reverse")
    assert [point.value for point in reverse.points] == [point.value for point in forward.points][
        ::-1
    ]
    by_value = {point.value: point for point in reverse.points}
    for point in forward.points:
        assert canonical(point.as_document()) == canonical(by_value[point.value].as_document())
    assert forward.summary == reverse.summary


def test_a24_a_sweep_out_of_budget_is_incomplete_and_lists_the_unrun_points() -> None:
    result = sweep(max_points=4)
    assert result.status == "INCOMPLETE"
    assert len(result.points) == 9
    run, unrun = result.points[:4], result.points[4:]
    assert all(point.outcome == "CONVERGED" for point in run)
    assert len(unrun) == 5
    for point in unrun:
        assert point.outcome == "NOT_RUN"
        assert point.outputs is None
        assert point.sensitivity is None
        assert point.solve_outcome is None
    assert result.summary["not_run"] == 5
    assert result.summary["failed"] == 0
    # The points that ran are the full sweep's, bit for bit: a budget truncates, never alters.
    for short, full in zip(run, sweep().points[:4], strict=True):
        assert canonical(short.as_document()) == canonical(full.as_document())


def test_an_ill_formed_sweep_raises_before_any_point_runs() -> None:
    sheet, _, _ = registered()
    with pytest.raises(KeyError):
        run_sweep(sheet, "U-FLASH.not_a_parameter", (360.0,), OUTPUTS)
    with pytest.raises(ValueError, match="cannot be moved alone"):
        run_sweep(sheet, "U-FLASH.P_spec", (1.1e5,), OUTPUTS)
