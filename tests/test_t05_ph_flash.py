"""T05 W3: `syn001.ph_flash` against the registered cases (spec §5; A07, A13, A14, A16, A04/A05).

Every expectation is read from `benchmarks/t05/reference_values.yaml`: status, code (the message's
first line, byte-exact, §3.5), signature and route exactly; `T` to `1e-6 K`, flows to
`3.1e-8 mol/s`, `beta` to `1e-10`, duty to `1.01e-3 W`; registered zeros `== 0.0` (§14).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest
from t05_support import (
    BETA_TOLERANCE,
    CONTEXT,
    ENERGY_TOLERANCE,
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
from openflowsheet.models.syn001.flash import TPFlash
from openflowsheet.models.syn001.ph_flash import MODEL_ID, PHFlash

CASES = cases(MODEL_ID)


def unit_for(inputs: Mapping[str, Any]) -> PHFlash:
    return PHFlash(
        unit_id="U-PHF",
        provider=PROVIDER,
        duty=float(inputs["duty"]),
        context=CONTEXT,
        pressure_drop=float(inputs["pressure_drop"]),
        inlet_phase=inputs["inlet_phase"],
    )


def test_every_registered_case_is_exercised() -> None:
    """A07 names PHF-1…7, Z0, Z1, F1…F4; the list below is read from the YAML, so pin its size."""
    assert sorted(CASES) == sorted(
        [f"PHF-{i}" for i in range(1, 8)]
        + ["PHF-Z0", "PHF-Z1"]
        + [f"PHF-F{i}" for i in range(1, 5)]
    )


@pytest.mark.parametrize("case_id", CASES)
def test_ph_flash_case(case_id: str) -> None:
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

    assert result.phase_signature == expected["signature"]
    if "route" in expected:
        assert closure is not None and closure.route == expected["route"]
    else:
        # The dormant cases register no route: the kernel is never reached (spec §4.7).
        assert closure is None
    assert_close(result.duty, expected["duty_W"], ENERGY_TOLERANCE, "duty")
    for port in ("vapor", "liquid"):
        outlet = result.outlets[port]
        registered = expected[port]
        assert_flows(outlet.n, registered["n_mol_per_s"], f"{case_id} {port}.n")
        assert_close(outlet.temperature, registered["T_K"], TEMPERATURE_TOLERANCE, f"{port}.T")
        assert_close(outlet.pressure, registered["P_Pa"], PRESSURE_TOLERANCE, f"{port}.P")
    if "T_K" in expected:
        assert closure is not None
        assert_close(closure.temperature, expected["T_K"], TEMPERATURE_TOLERANCE, "T")
    if "beta" in expected:
        assert closure is not None and closure.split is not None
        assert_close(closure.split.vapor_fraction, expected["beta"], BETA_TOLERANCE, "beta")
    if expected["signature"] == "ZERO_FLOW":
        # A14: a dormant case's duty is exactly zero and its outlets carry the label exactly.
        assert result.duty == 0.0
        label = float(inputs["inlet"]["T_K"])
        assert all(outlet.temperature == label for outlet in result.outlets.values())


@pytest.mark.parametrize("case_id", specification_errors(MODEL_ID))
def test_ph_flash_construction_refusal(case_id: str) -> None:
    """A16 for PHF-S1: the nominal case (PHF-1) with the registered change, refused at build."""
    registered = REF["specification_errors"][case_id]
    inputs = {**REF["unit_cases"]["PHF-1"]["inputs"], **registered["change_from_nominal"]}
    with pytest.raises(SpecificationError) as refused:
        unit_for(inputs)
    assert first_line(str(refused.value)) == registered["code"]


def test_ph_of_tp_is_the_identity_at_360_k() -> None:
    """A13: PHF-2 returns 360 K and K02's TP flash split at 360 K on the same stream."""
    inputs = REF["unit_cases"]["PHF-2"]["inputs"]
    feed = stream(inputs["inlet"])
    result = unit_for(inputs).evaluate({"inlet": [feed]}, CONTEXT)
    assert result.status == "ok", result.message
    for outlet in result.outlets.values():
        assert abs(outlet.temperature - 360.0) <= TEMPERATURE_TOLERANCE

    flash = TPFlash(
        unit_id="U-FLASH",
        provider=PROVIDER,
        temperature=360.0,
        pressure=feed.pressure,
        context=CONTEXT,
        inlet_phase="LIQUID",
    )
    reference = flash.evaluate({"inlet": [feed]}, CONTEXT)
    assert reference.status == "ok", reference.message
    for port in ("vapor", "liquid"):
        for got, want in zip(result.outlets[port].n, reference.outlets[port].n, strict=True):
            assert abs(got - want) <= FLOW_TOLERANCE, port
    # Duty closes the loop: K02's flash from the same inlet at 360 K needs the registered duty.
    assert reference.duty is not None
    assert abs(reference.duty - float(inputs["duty"])) <= ENERGY_TOLERANCE


def test_a_ph_flash_with_an_inadmissible_vapour_inlet_names_the_phase() -> None:
    """A16's grammar with the other phase: `inadmissible_phase(inlet, VAPOR)`."""
    inputs = {**REF["unit_cases"]["PHF-F3"]["inputs"], "inlet_phase": "VAPOR"}
    result = unit_for(inputs).evaluate({"inlet": [stream(inputs["inlet"])]}, CONTEXT)
    assert result.status == "unsupported"
    assert first_line(result.message) == "inadmissible_phase(inlet, VAPOR)"


# --------------------------------------------------------------------------- A04/A05


def build_trial(configuration: Mapping[str, Any], parameters: Mapping[str, str]) -> TrialUnit:
    regime = configuration["inlet_regime"]
    unit = PHFlash(
        unit_id=configuration["unit"],
        provider=PROVIDER,
        duty=float(parameters["duty"]),
        context=CONTEXT,
        pressure_drop=float(parameters["pressure_drop"]),
        inlet_phase=None if regime == "lifted" else regime,
    )
    inlet, vapor, liquid = (configuration[port] for port in ("inlet", "vapor", "liquid"))
    return TrialUnit(
        unit=unit,
        wiring=Wiring({"inlet": (inlet,), "vapor": (vapor,), "liquid": (liquid,)}),
        streams=(inlet, vapor, liquid),
        lifted_inlets=(inlet,) if regime == "lifted" else (),
    )


@pytest.mark.parametrize("state_id", trial_states(MODEL_ID))
def test_rows_and_jacobian_at_the_registered_trial_state(state_id: str) -> None:
    comparison = compare_trial_state(MODEL_ID, state_id, build_trial)
    assert comparison.failures == [], comparison.summary()
