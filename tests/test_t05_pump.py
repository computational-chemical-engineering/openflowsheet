"""T05 W5: `syn001.liquid_pump` against the registered cases (T05 spec §9; A09, A14, A16, A04/A05).

Every expectation is read from `benchmarks/t05/reference_values.yaml`. The shaft work is reported
in `UnitEvaluation.work` (positive into the pump); the pump has no heat port, so `duty` is `None`.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest
from t05_support import (
    CONTEXT,
    ENERGY_TOLERANCE,
    PRESSURE_TOLERANCE,
    PROVIDER,
    REF,
    TEMPERATURE_TOLERANCE,
    assert_close,
    assert_flows,
    cases,
    first_line,
    specification_errors,
    stream,
)
from t05_trial_states import TrialUnit, compare_trial_state, trial_states

from openflowsheet.models import SpecificationError, Wiring
from openflowsheet.models.syn001.pump import MODEL_ID, LiquidPump, isothermal_block_id, work_id

CASES = cases(MODEL_ID)


def unit_for(inputs: Mapping[str, Any]) -> LiquidPump:
    return LiquidPump(
        unit_id="U-PUMP",
        provider=PROVIDER,
        outlet_pressure=float(inputs["outlet_pressure"]),
        efficiency=float(inputs["efficiency"]),
        context=CONTEXT,
    )


def test_every_registered_case_is_exercised() -> None:
    assert sorted(CASES) == sorted(
        [f"PUMP-{i}" for i in range(1, 5)] + [f"PUMP-F{i}" for i in range(1, 4)] + ["PUMP-Z"]
    )


@pytest.mark.parametrize("case_id", CASES)
def test_pump_case(case_id: str) -> None:
    case = REF["unit_cases"][case_id]
    inputs, expected = case["inputs"], case["expected"]
    result = unit_for(inputs).evaluate({"inlet": [stream(inputs["inlet"])]}, CONTEXT)

    assert result.status == expected["status"], result.message
    assert first_line(result.message) == expected["code"]
    if expected["status"] != "ok":
        assert result.outlets == {} and result.work is None and result.duty is None
        return

    assert result.duty is None
    assert result.phase_signature == expected["signature"]
    assert_close(result.work, expected["work_W"], ENERGY_TOLERANCE, "work")
    if "work_ideal_W" in expected:
        assert result.work is not None
        ideal = result.work * float(inputs["efficiency"])
        assert_close(ideal, expected["work_ideal_W"], ENERGY_TOLERANCE, "ideal work")
    registered = expected["outlet"]
    outlet = result.outlets["outlet"]
    assert_flows(outlet.n, registered["n_mol_per_s"], f"{case_id} outlet.n")
    assert_close(outlet.temperature, registered["T_K"], TEMPERATURE_TOLERANCE, "outlet.T")
    assert_close(outlet.pressure, registered["P_Pa"], PRESSURE_TOLERANCE, "outlet.P")
    if expected["signature"] == "ZERO_FLOW":
        # A14: exactly zero work, and the label is the inlet's temperature, exactly.
        assert result.work == 0.0
        assert outlet.temperature == float(inputs["inlet"]["T_K"])


@pytest.mark.parametrize("case_id", specification_errors(MODEL_ID))
def test_pump_construction_refusal(case_id: str) -> None:
    """A16 for PUMP-S1/S2: the nominal case (PUMP-1) with the registered change."""
    registered = REF["specification_errors"][case_id]
    inputs = {**REF["unit_cases"]["PUMP-1"]["inputs"], **registered["change_from_nominal"]}
    with pytest.raises(SpecificationError) as refused:
        unit_for(inputs)
    assert first_line(str(refused.value)) == registered["code"]


def test_an_outlet_pressure_off_the_domain_is_refused_at_construction() -> None:
    """The valve's construction code on the pump's `P_spec` (spec §9.1: 'in the domain')."""
    inputs = {**REF["unit_cases"]["PUMP-1"]["inputs"], "outlet_pressure": 2.5e5}
    with pytest.raises(SpecificationError) as refused:
        unit_for(inputs)
    assert first_line(str(refused.value)) == "pressure_outside_domain(outlet_pressure)"


def test_the_isothermal_block_and_the_work_variable_have_their_registered_ids() -> None:
    """Spec §3.2: `<U>.W` and `H_<inlet>_liquid_isothermal`."""
    unit = unit_for(REF["unit_cases"]["PUMP-1"]["inputs"])
    contribution = unit.contribute(Wiring({"inlet": ("S1",), "outlet": ("S2",)}), ("A", "B", "C"))
    assert contribution.variable_ids == (work_id("U-PUMP"),) == ("U-PUMP.W",)
    assert contribution.variable_kinds == {"U-PUMP.W": "heat_rate"}
    block_ids = {block.block_id for block in contribution.blocks}
    assert isothermal_block_id("S1") == "H_S1_liquid_isothermal" in block_ids
    assert contribution.block_inputs["H_S1_liquid_isothermal"] == (
        "S1.n.A",
        "S1.n.B",
        "S1.n.C",
        "S1.T",
        "S2.P",
    )


# --------------------------------------------------------------------------- A04/A05


def build_trial(configuration: Mapping[str, Any], parameters: Mapping[str, str]) -> TrialUnit:
    unit = LiquidPump(
        unit_id=configuration["unit"],
        provider=PROVIDER,
        outlet_pressure=float(parameters["outlet_pressure"]),
        efficiency=float(parameters["efficiency"]),
        context=CONTEXT,
    )
    inlet, outlet = configuration["inlet"], configuration["outlet"]
    return TrialUnit(
        unit=unit,
        wiring=Wiring({"inlet": (inlet,), "outlet": (outlet,)}),
        streams=(inlet, outlet),
    )


@pytest.mark.parametrize("state_id", trial_states(MODEL_ID))
def test_rows_and_jacobian_at_the_registered_trial_state(state_id: str) -> None:
    comparison = compare_trial_state(MODEL_ID, state_id, build_trial)
    assert comparison.failures == [], comparison.summary()
