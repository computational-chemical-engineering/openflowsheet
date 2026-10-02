"""T05 W4: `syn001.valve` against the registered cases (T05 spec §8; A08, A14, A16, A04/A05).

Every expectation is read from `benchmarks/t05/reference_values.yaml`. The valve has one outlet
stream and a lifted split; the split registered as `outlet.vapor_n_mol_per_s` /
`liquid_n_mol_per_s` is the PH kernel's, returned by `evaluate_with_closure`.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest
from t05_support import (
    CONTEXT,
    FLOW_TOLERANCE,
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
from openflowsheet.models.syn001.ph_flash import PHFlash
from openflowsheet.models.syn001.valve import MODEL_ID, Valve

CASES = cases(MODEL_ID)


def unit_for(inputs: Mapping[str, Any]) -> Valve:
    return Valve(
        unit_id="U-VLV",
        provider=PROVIDER,
        outlet_pressure=float(inputs["outlet_pressure"]),
        context=CONTEXT,
        inlet_phase=inputs["inlet_phase"],
    )


def test_every_registered_case_is_exercised() -> None:
    assert sorted(CASES) == sorted([f"VLV-{i}" for i in range(1, 6)] + ["VLV-Z", "VLV-F1"])


@pytest.mark.parametrize("case_id", CASES)
def test_valve_case(case_id: str) -> None:
    case = REF["unit_cases"][case_id]
    inputs, expected = case["inputs"], case["expected"]
    result, closure = unit_for(inputs).evaluate_with_closure(
        {"inlet": [stream(inputs["inlet"])]}, CONTEXT
    )

    assert result.status == expected["status"], result.message
    assert first_line(result.message) == expected["code"]
    if expected["status"] != "ok":
        assert result.outlets == {} and result.duty is None
        return

    # No energy port: the valve reports no duty at all, not a zero one.
    assert result.duty is None and result.work is None
    assert result.phase_signature == expected["signature"]
    registered = expected["outlet"]
    outlet = result.outlets["outlet"]
    assert_flows(outlet.n, registered["n_mol_per_s"], f"{case_id} outlet.n")
    assert_close(outlet.temperature, registered["T_K"], TEMPERATURE_TOLERANCE, "outlet.T")
    assert_close(outlet.pressure, registered["P_Pa"], PRESSURE_TOLERANCE, "outlet.P")

    if expected["signature"] == "ZERO_FLOW":
        # A14: the label is the inlet's temperature, exactly; the kernel is never reached.
        assert closure is None
        assert outlet.temperature == float(inputs["inlet"]["T_K"])
        assert all(float(value) == 0.0 for value in registered["vapor_n_mol_per_s"])
        assert all(float(value) == 0.0 for value in registered["liquid_n_mol_per_s"])
        return
    assert closure is not None and closure.split is not None
    assert closure.split.phase_signature == registered["regime"]
    assert closure.split.vapor is not None and closure.split.liquid is not None
    assert_flows(closure.split.vapor.n, registered["vapor_n_mol_per_s"], f"{case_id} vapour")
    assert_flows(closure.split.liquid.n, registered["liquid_n_mol_per_s"], f"{case_id} liquid")


@pytest.mark.parametrize("case_id", specification_errors(MODEL_ID))
def test_valve_construction_refusal(case_id: str) -> None:
    """A16 for VLV-S1: the nominal case (VLV-1) with the registered change, refused at build."""
    registered = REF["specification_errors"][case_id]
    inputs = {**REF["unit_cases"]["VLV-1"]["inputs"], **registered["change_from_nominal"]}
    with pytest.raises(SpecificationError) as refused:
        unit_for(inputs)
    assert first_line(str(refused.value)) == registered["code"]


def test_a_lifted_inlet_flashes_further_than_its_producer() -> None:
    """VLV-5's purpose: its inlet is VLV-2's outlet, and it ends with more vapour (spec §8)."""
    vapour = {}
    for case_id in ("VLV-2", "VLV-5"):
        inputs = REF["unit_cases"][case_id]["inputs"]
        _, closure = unit_for(inputs).evaluate_with_closure(
            {"inlet": [stream(inputs["inlet"])]}, CONTEXT
        )
        assert closure is not None and closure.split is not None
        assert closure.split.vapor is not None
        vapour[case_id] = sum(closure.split.vapor.n)
    assert vapour["VLV-5"] > vapour["VLV-2"]


def test_an_adiabatic_flash_across_a_drop_equals_the_valve() -> None:
    """A13: PHF-7 (Q = 0, dP = 8e4 Pa) and VLV-2 (to 1e5 Pa) are the same PH problem."""
    phf = REF["unit_cases"]["PHF-7"]["inputs"]
    vlv = REF["unit_cases"]["VLV-2"]["inputs"]
    assert phf["inlet"] == vlv["inlet"]
    flashed, flash_closure = PHFlash(
        unit_id="U-PHF",
        provider=PROVIDER,
        duty=float(phf["duty"]),
        context=CONTEXT,
        pressure_drop=float(phf["pressure_drop"]),
        inlet_phase=phf["inlet_phase"],
    ).evaluate_with_closure({"inlet": [stream(phf["inlet"])]}, CONTEXT)
    throttled, valve_closure = unit_for(vlv).evaluate_with_closure(
        {"inlet": [stream(vlv["inlet"])]}, CONTEXT
    )
    assert flashed.status == throttled.status == "ok"
    assert flash_closure is not None and valve_closure is not None
    assert flash_closure.temperature is not None and valve_closure.temperature is not None
    assert abs(flash_closure.temperature - valve_closure.temperature) <= TEMPERATURE_TOLERANCE
    assert flashed.phase_signature == throttled.phase_signature
    assert flash_closure.split is not None and valve_closure.split is not None
    for port in ("vapor", "liquid"):
        ours = getattr(flash_closure.split, port)
        theirs = getattr(valve_closure.split, port)
        for got, want in zip(ours.n, theirs.n, strict=True):
            assert abs(got - want) <= FLOW_TOLERANCE, port
    assert flashed.outlets["vapor"].pressure == throttled.outlets["outlet"].pressure


# --------------------------------------------------------------------------- A04/A05


def build_trial(configuration: Mapping[str, Any], parameters: Mapping[str, str]) -> TrialUnit:
    regime = configuration["inlet_regime"]
    unit = Valve(
        unit_id=configuration["unit"],
        provider=PROVIDER,
        outlet_pressure=float(parameters["outlet_pressure"]),
        context=CONTEXT,
        inlet_phase=None if regime == "lifted" else regime,
    )
    inlet, outlet = configuration["inlet"], configuration["outlet"]
    return TrialUnit(
        unit=unit,
        wiring=Wiring({"inlet": (inlet,), "outlet": (outlet,)}),
        streams=(inlet, outlet),
        lifted_inlets=(inlet,) if regime == "lifted" else (),
    )


@pytest.mark.parametrize("state_id", trial_states(MODEL_ID))
def test_rows_and_jacobian_at_the_registered_trial_state(state_id: str) -> None:
    comparison = compare_trial_state(MODEL_ID, state_id, build_trial)
    assert comparison.failures == [], comparison.summary()
