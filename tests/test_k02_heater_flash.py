"""K02: the heater and the flash, which share one TP-state kernel (plan §4.2).

The expectations here are Fable's 20-digit reference values in
`benchmarks/syn001/reference_values.yaml`, generated with mpmath at 40 digits from the plan §3.1
definitions and independent of every implementation in this repository. They are compared at the
tolerances ADR 0001 D6 registers for SYN-001 and nowhere else.

All five registered variants are exercised, because they are not five samples of one behaviour:
three have a two-phase heater outlet, one has a negative heater duty, one has a vapour product of
exactly zero flow and one has a liquid, purge and recycle of exactly zero flow (derivation §7).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np
import pytest

from openflowsheet.compile.casadi_backend import compile_problem
from openflowsheet.compile.reference import row_values, row_vector, state_vector
from openflowsheet.compiled import EvaluationContext
from openflowsheet.models import (
    SpecificationError,
    Wiring,
    assemble,
    duty_id,
    flow_id,
    pressure_id,
    row_id,
    temperature_id,
)
from openflowsheet.models.syn001 import COMPONENTS, P_MIN
from openflowsheet.models.syn001.flash import TPFlash, total_flow_id
from openflowsheet.models.syn001.heater import TPHeater
from openflowsheet.models.syn001.tp_state import (
    liquid_flow_id,
    liquid_total_id,
    vapor_flow_id,
    vapor_total_id,
)
from openflowsheet.thermo import (
    FlashRequest,
    FlashResult,
    PropertyCapabilities,
    PropertyRequest,
    PropertyResult,
    StreamState,
)
from openflowsheet.thermo.cache import ExactPropertyCache
from openflowsheet.thermo.syn001 import Syn001Provider

CONTEXT = EvaluationContext(
    model_version="K02-unit-evaluator@" + "0" * 64, constants_sha256="0" * 64
)
PROVIDER = Syn001Provider()

#: ADR 0001 D6, registered for SYN-001 only.
ENERGY_TOLERANCE = 1e-5 + 1e-8 * 1e5
FLOW_TOLERANCE = 1e-9 + 1e-8 * 3.0
TEMPERATURE_TOLERANCE = 1e-6


def variants(reference_values: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {entry["case_id"]: entry for entry in reference_values["variants"]}


CASE_IDS = [
    "SYN-001-nominal",
    "SYN-001-once-through",
    "SYN-001-high-recycle",
    "SYN-001-all-liquid-310K",
    "SYN-001-all-vapor-420K",
]


def stream_of(case: Mapping[str, Any], key: str, temperature_key: str) -> StreamState:
    return StreamState(
        n=tuple(float(value) for value in case[key]),
        temperature=float(case[temperature_key]),
        pressure=float(case["P_Pa"]),
    )


# ------------------------------------------------------------- the heater against the reference


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_heater_duty_matches_the_twenty_digit_reference(
    case_id: str, reference_values: Mapping[str, Any]
) -> None:
    """Q_heater at every registered variant, including the negative one at r = 0.95."""
    case = variants(reference_values)[case_id]
    heater = TPHeater(
        unit_id="U-HEAT",
        provider=PROVIDER,
        outlet_temperature=float(case["T_heater_K"]),
        context=CONTEXT,
        inlet_phase="LIQUID",
    )
    inlet = stream_of(case, "mixed_feed_mol_per_s", "T_mix_K")
    result = heater.evaluate({"inlet": (inlet,)}, CONTEXT)
    assert result.status == "ok", result.message
    assert result.duty is not None
    assert result.duty == pytest.approx(float(case["Q_heater_W"]), abs=ENERGY_TOLERANCE)


def test_heater_duty_is_negative_at_high_recycle(reference_values: Mapping[str, Any]) -> None:
    """ADR 0001 D4.2: an implementation asserting Q >= 0 fails this registered variant."""
    case = variants(reference_values)["SYN-001-high-recycle"]
    heater = TPHeater(
        unit_id="U-HEAT",
        provider=PROVIDER,
        outlet_temperature=float(case["T_heater_K"]),
        context=CONTEXT,
        inlet_phase="LIQUID",
    )
    result = heater.evaluate(
        {"inlet": (stream_of(case, "mixed_feed_mol_per_s", "T_mix_K"),)}, CONTEXT
    )
    assert result.duty is not None
    assert result.duty < 0.0
    assert result.duty == pytest.approx(-16144.627684760118980, abs=ENERGY_TOLERANCE)


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_heater_outlet_phase_is_the_registered_one(
    case_id: str, reference_values: Mapping[str, Any]
) -> None:
    """Two-phase in three of the five variants, which is the point of the TP-state outlet."""
    case = variants(reference_values)[case_id]
    heater = TPHeater(
        unit_id="U-HEAT",
        provider=PROVIDER,
        outlet_temperature=float(case["T_heater_K"]),
        context=CONTEXT,
        inlet_phase="LIQUID",
    )
    result = heater.evaluate(
        {"inlet": (stream_of(case, "mixed_feed_mol_per_s", "T_mix_K"),)}, CONTEXT
    )
    assert result.phase_signature == case["heater_outlet_state"]


def test_heater_outlet_carries_the_inlet_flows_and_the_specified_temperature() -> None:
    heater = TPHeater(
        unit_id="U-HEAT", provider=PROVIDER, outlet_temperature=350.0, context=CONTEXT
    )
    inlet = StreamState(n=(1.0, 2.0, 3.0), temperature=300.0, pressure=100_000.0)
    result = heater.evaluate({"inlet": (inlet,)}, CONTEXT)
    outlet = result.outlets["outlet"]
    assert outlet.n == inlet.n
    assert outlet.temperature == 350.0
    assert outlet.pressure == 100_000.0


# -------------------------------------------------------------- the flash against the reference


def flash_inlet(case: Mapping[str, Any]) -> StreamState:
    """The flash feed is the heater outlet: the mixed feed at the heater setpoint."""
    return stream_of(case, "mixed_feed_mol_per_s", "T_heater_K")


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_flash_split_matches_the_twenty_digit_reference(
    case_id: str, reference_values: Mapping[str, Any]
) -> None:
    case = variants(reference_values)[case_id]
    unit = TPFlash(
        unit_id="U-FLASH",
        provider=PROVIDER,
        temperature=float(case["T_flash_K"]),
        pressure=float(case["P_Pa"]),
        context=CONTEXT,
    )
    result = unit.evaluate({"inlet": (flash_inlet(case),)}, CONTEXT)
    assert result.status == "ok", result.message
    assert result.phase_signature == case["flash_phase_state"]

    vapor, liquid = result.outlets["vapor"], result.outlets["liquid"]
    assert sum(vapor.n) == pytest.approx(float(case["V_mol_per_s"]), abs=FLOW_TOLERANCE)
    assert sum(liquid.n) == pytest.approx(float(case["L_mol_per_s"]), abs=FLOW_TOLERANCE)


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_flash_duty_matches_the_twenty_digit_reference(
    case_id: str, reference_values: Mapping[str, Any]
) -> None:
    case = variants(reference_values)[case_id]
    unit = TPFlash(
        unit_id="U-FLASH",
        provider=PROVIDER,
        temperature=float(case["T_flash_K"]),
        pressure=float(case["P_Pa"]),
        context=CONTEXT,
    )
    result = unit.evaluate({"inlet": (flash_inlet(case),)}, CONTEXT)
    assert result.duty is not None
    assert result.duty == pytest.approx(float(case["Q_flash_W"]), abs=ENERGY_TOLERANCE)


def test_duties_sum_to_products_minus_fresh_feed(reference_values: Mapping[str, Any]) -> None:
    """Derivation §6: Q_h + Q_f = H(products) - H(fresh feed), for every r.

    Blueprint A09 label: this check shares SYN-001's thermodynamics with the units it checks. It
    verifies bookkeeping, not enthalpy data.
    """
    for case_id in CASE_IDS:
        case = variants(reference_values)[case_id]
        heater = TPHeater(
            unit_id="U-HEAT",
            provider=PROVIDER,
            outlet_temperature=float(case["T_heater_K"]),
            context=CONTEXT,
            inlet_phase="LIQUID",
        )
        flash = TPFlash(
            unit_id="U-FLASH",
            provider=PROVIDER,
            temperature=float(case["T_flash_K"]),
            pressure=float(case["P_Pa"]),
            context=CONTEXT,
        )
        heated = heater.evaluate(
            {"inlet": (stream_of(case, "mixed_feed_mol_per_s", "T_mix_K"),)}, CONTEXT
        )
        flashed = flash.evaluate({"inlet": (heated.outlets["outlet"],)}, CONTEXT)
        assert heated.duty is not None
        assert flashed.duty is not None
        assert heated.duty + flashed.duty == pytest.approx(
            float(case["Q_total_W"]), abs=ENERGY_TOLERANCE
        ), case_id


@pytest.mark.parametrize(
    ("case_id", "dormant_port"),
    [("SYN-001-all-liquid-310K", "vapor"), ("SYN-001-all-vapor-420K", "liquid")],
)
def test_a_vanished_phase_leaves_an_exactly_dormant_outlet(
    case_id: str, dormant_port: str, reference_values: Mapping[str, Any]
) -> None:
    """ADR 0001 D3.4: V = 0 or L = 0 gives one dormant outlet and a single-phase unit signature."""
    case = variants(reference_values)[case_id]
    unit = TPFlash(
        unit_id="U-FLASH",
        provider=PROVIDER,
        temperature=float(case["T_flash_K"]),
        pressure=float(case["P_Pa"]),
        context=CONTEXT,
    )
    result = unit.evaluate({"inlet": (flash_inlet(case),)}, CONTEXT)
    assert result.outlets[dormant_port].is_dormant
    assert result.outlets[dormant_port].n == (0.0, 0.0, 0.0)
    assert result.phase_signature in ("LIQUID", "VAPOR")


# ------------------------------------------------------------------------------- zero flow


class SpyProvider:
    """Counts what a unit asked the provider, so "never consulted" can be asserted."""

    def __init__(self, inner: Any) -> None:
        self.inner = inner
        self.phase_calls = 0
        self.flash_calls = 0

    def describe(self) -> PropertyCapabilities:
        return self.inner.describe()

    def evaluate_phase(
        self, request: PropertyRequest, context: EvaluationContext
    ) -> PropertyResult:
        self.phase_calls += 1
        return self.inner.evaluate_phase(request, context)

    def flash(self, request: FlashRequest, context: EvaluationContext) -> FlashResult:
        self.flash_calls += 1
        return self.inner.flash(request, context)


def test_a_dormant_heater_inlet_gives_zero_duty_without_consulting_the_provider() -> None:
    """ADR 0001 D3.4 and D3.1: exactly zero duty, and no property is evaluated."""
    spy = SpyProvider(Syn001Provider())
    heater = TPHeater(unit_id="U-HEAT", provider=spy, outlet_temperature=350.0, context=CONTEXT)
    dormant = StreamState(n=(0.0, 0.0, 0.0), temperature=300.0, pressure=100_000.0)
    result = heater.evaluate({"inlet": (dormant,)}, CONTEXT)
    assert result.status == "ok"
    assert result.duty == 0.0
    assert result.phase_signature == "ZERO_FLOW"
    assert result.outlets["outlet"].is_dormant
    assert (spy.phase_calls, spy.flash_calls) == (0, 0)


def test_a_dormant_flash_feed_gives_two_dormant_outlets_and_zero_duty() -> None:
    spy = SpyProvider(Syn001Provider())
    unit = TPFlash(
        unit_id="U-FLASH",
        provider=spy,
        temperature=360.0,
        pressure=100_000.0,
        context=CONTEXT,
    )
    dormant = StreamState(n=(0.0, 0.0, 0.0), temperature=360.0, pressure=100_000.0)
    result = unit.evaluate({"inlet": (dormant,)}, CONTEXT)
    assert result.status == "ok"
    assert result.duty == 0.0
    assert result.phase_signature == "ZERO_FLOW"
    assert result.outlets["vapor"].is_dormant and result.outlets["liquid"].is_dormant
    assert (spy.phase_calls, spy.flash_calls) == (0, 0)


def test_a_zero_component_passes_through_both_units_exactly() -> None:
    """ADR 0001 D3.3 (STA-02): n_tot > 0 with n_i == 0 exactly, through heater and flash."""
    feed = StreamState(n=(1.0, 0.0, 1.0), temperature=300.0, pressure=100_000.0)
    heater = TPHeater(
        unit_id="U-HEAT",
        provider=PROVIDER,
        outlet_temperature=350.0,
        context=CONTEXT,
        inlet_phase="LIQUID",
    )
    heated = heater.evaluate({"inlet": (feed,)}, CONTEXT)
    assert heated.status == "ok", heated.message
    assert heated.outlets["outlet"].n[1] == 0.0

    unit = TPFlash(
        unit_id="U-FLASH", provider=PROVIDER, temperature=360.0, pressure=100_000.0, context=CONTEXT
    )
    flashed = unit.evaluate({"inlet": (heated.outlets["outlet"],)}, CONTEXT)
    assert flashed.status == "ok", flashed.message
    assert flashed.outlets["vapor"].n[1] == 0.0
    assert flashed.outlets["liquid"].n[1] == 0.0


# ------------------------------------------------------------------------- cache on and off


def _run_pair(provider: Any, inlet: StreamState) -> tuple[Any, ...]:
    """One heater-then-flash pass, returning everything a caller could act on."""
    heater = TPHeater(
        unit_id="U-HEAT",
        provider=provider,
        outlet_temperature=350.0,
        context=CONTEXT,
        inlet_phase="LIQUID",
    )
    flash = TPFlash(
        unit_id="U-FLASH",
        provider=provider,
        temperature=360.0,
        pressure=100_000.0,
        context=CONTEXT,
    )
    heated = heater.evaluate({"inlet": (inlet,)}, CONTEXT)
    flashed = flash.evaluate({"inlet": (heated.outlets["outlet"],)}, CONTEXT)
    return (
        heated.status,
        heated.duty,
        heated.phase_signature,
        heated.outlets["outlet"].n,
        flashed.status,
        flashed.duty,
        flashed.phase_signature,
        flashed.outlets["vapor"].n,
        flashed.outlets["liquid"].n,
    )


def test_the_cache_changes_nothing_a_unit_reports(reference_values: Mapping[str, Any]) -> None:
    """Plan §4.2's "cache on/off" test, at bit equality rather than at a tolerance.

    Two anti-vacuity guards, because "the cache changed nothing" is also what a cache that was
    never consulted would report. The spy witnesses that the provider *was* reached, and the
    second pass must reach it strictly fewer times than the first, which is only true if entries
    were actually served.
    """
    case = variants(reference_values)["SYN-001-nominal"]
    inlet = stream_of(case, "mixed_feed_mol_per_s", "T_mix_K")

    without_cache = _run_pair(Syn001Provider(), inlet)

    spy = SpyProvider(Syn001Provider())
    cached = ExactPropertyCache(spy)
    first = _run_pair(cached, inlet)
    calls_after_first = (spy.phase_calls, spy.flash_calls)
    second = _run_pair(cached, inlet)
    calls_after_second = (spy.phase_calls, spy.flash_calls)

    assert first == without_cache, "the cache changed an answer on a cold pass"
    assert second == without_cache, "the cache changed an answer on a warm pass"
    assert calls_after_first > (0, 0), "the provider was never reached; the comparison is vacuous"
    assert calls_after_second == calls_after_first, (
        "the warm pass reached the provider again, so nothing was served from the cache and "
        "this test would pass with the cache removed"
    )


# ----------------------------------------------------------------------- perturbed inputs


def test_heater_duty_responds_to_a_perturbed_setpoint_at_the_analytic_slope() -> None:
    """dQ/dT_out = c_p n_tot while the outlet stays liquid, from h^L = c_p (T - T_r) + v (P - P_r).

    An independent expectation: the slope comes from the derivation, not from a second run of the
    same code at a different step.
    """
    inlet = StreamState(n=(1.0, 1.0, 1.0), temperature=300.0, pressure=100_000.0)
    duties = []
    for setpoint in (330.0, 330.0 + 1e-3):
        heater = TPHeater(
            unit_id="U-HEAT",
            provider=PROVIDER,
            outlet_temperature=setpoint,
            context=CONTEXT,
            inlet_phase="LIQUID",
        )
        result = heater.evaluate({"inlet": (inlet,)}, CONTEXT)
        assert result.phase_signature == "LIQUID"
        assert result.duty is not None
        duties.append(result.duty)
    slope = (duties[1] - duties[0]) / 1e-3
    assert slope == pytest.approx(100.0 * 3.0, rel=1e-9)


def test_a_perturbed_flash_temperature_moves_the_split_the_right_way() -> None:
    """Warmer at fixed pressure means more vapour: monotone, and checked as such."""
    feed = StreamState(n=(1.0, 1.0, 1.0), temperature=350.0, pressure=100_000.0)
    totals = []
    for temperature in (350.0, 355.0, 360.0):
        unit = TPFlash(
            unit_id="U-FLASH",
            provider=PROVIDER,
            temperature=temperature,
            pressure=100_000.0,
            context=CONTEXT,
        )
        result = unit.evaluate({"inlet": (feed,)}, CONTEXT)
        assert result.status == "ok"
        totals.append(sum(result.outlets["vapor"].n))
    assert totals[0] < totals[1] < totals[2]


# --------------------------------------------------------------- malformed and out of domain


def test_a_heater_with_both_a_temperature_and_a_duty_is_rejected() -> None:
    """ADR 0001 D4.4 / STR-03: a structural over-specification, refused at validation."""
    with pytest.raises(SpecificationError, match="over-specification"):
        TPHeater(
            unit_id="U-HEAT",
            provider=PROVIDER,
            outlet_temperature=350.0,
            context=CONTEXT,
            specified_duty=1000.0,
        )


def test_a_setpoint_outside_the_declared_domain_is_rejected_at_construction() -> None:
    with pytest.raises(SpecificationError, match="declared domain"):
        TPHeater(unit_id="U-HEAT", provider=PROVIDER, outlet_temperature=1000.0, context=CONTEXT)
    with pytest.raises(SpecificationError, match="declared domain"):
        TPFlash(
            unit_id="U-FLASH",
            provider=PROVIDER,
            temperature=360.0,
            pressure=1.0,
            context=CONTEXT,
        )


def test_an_inlet_outside_the_declared_domain_is_reported_not_extrapolated() -> None:
    heater = TPHeater(
        unit_id="U-HEAT", provider=PROVIDER, outlet_temperature=350.0, context=CONTEXT
    )
    cold = StreamState(n=(1.0, 1.0, 1.0), temperature=200.0, pressure=100_000.0)
    result = heater.evaluate({"inlet": (cold,)}, CONTEXT)
    assert result.status == "out_of_domain"
    assert result.outlets == {}
    assert result.duty is None


def test_a_heater_inlet_outside_its_declared_regime_is_refused() -> None:
    """Blueprint §6.3's final admissibility check: the rows were written for LIQUID."""
    heater = TPHeater(
        unit_id="U-HEAT",
        provider=PROVIDER,
        outlet_temperature=360.0,
        context=CONTEXT,
        inlet_phase="LIQUID",
    )
    two_phase = StreamState(n=(1.0, 1.0, 1.0), temperature=350.0, pressure=100_000.0)
    result = heater.evaluate({"inlet": (two_phase,)}, CONTEXT)
    assert result.status == "unsupported"
    assert "declared LIQUID" in result.message
    assert result.duty is None


def test_a_flash_fed_at_the_wrong_pressure_refuses_rather_than_repairs() -> None:
    """ADR 0001 D4.5: a pressure mismatch is a validation failure, never a silent repair."""
    unit = TPFlash(
        unit_id="U-FLASH", provider=PROVIDER, temperature=360.0, pressure=100_000.0, context=CONTEXT
    )
    feed = StreamState(n=(1.0, 1.0, 1.0), temperature=350.0, pressure=P_MIN)
    result = unit.evaluate({"inlet": (feed,)}, CONTEXT)
    assert result.status == "error"
    assert result.outlets == {}


# ================================================================== the rows, and ADR 0008 D4.3

HF_STREAMS = ("S2", "S3", "S4", "S5")
HF_WIRING = {
    "U-HEAT": Wiring({"inlet": ("S2",), "outlet": ("S3",)}),
    "U-FLASH": Wiring({"inlet": ("S3",), "vapor": ("S4",), "liquid": ("S5",)}),
}


def build_heater_flash_spec() -> Any:
    heater = TPHeater(
        unit_id="U-HEAT",
        provider=PROVIDER,
        outlet_temperature=350.0,
        context=CONTEXT,
        inlet_phase="LIQUID",
    )
    flash = TPFlash(
        unit_id="U-FLASH",
        provider=PROVIDER,
        temperature=360.0,
        pressure=100_000.0,
        context=CONTEXT,
    )
    return assemble(
        label="K02-M2-heater-flash",
        units=[heater, flash],
        wiring=HF_WIRING,
        streams=HF_STREAMS,
        components=COMPONENTS,
    )


def consistent_state(spec: Any) -> dict[str, float]:
    """A state every variable of the heater-flash spec has a plausible value at."""
    state = {name: 0.0 for name in spec.variable_ids}
    for index, component in enumerate(COMPONENTS):
        for stream in HF_STREAMS:
            state[flow_id(stream, component)] = 1.0 + 0.1 * index
        state[vapor_flow_id("S3", component)] = 0.4
        state[liquid_flow_id("S3", component)] = 0.6 + 0.1 * index
    for stream, temperature in (("S2", 321.2), ("S3", 350.0), ("S4", 360.0), ("S5", 360.0)):
        state[temperature_id(stream)] = temperature
        state[pressure_id(stream)] = 100_000.0
    state[vapor_total_id("S3")] = 1.2
    state[liquid_total_id("S3")] = 2.1
    state[total_flow_id("S4")] = 3.3
    state[total_flow_id("S5")] = 3.3
    state[duty_id("U-HEAT")] = 13_000.0
    state[duty_id("U-FLASH")] = 43_000.0
    return state


def test_d4_3_heat_mole_is_exactly_plus_one_half() -> None:
    """ADR 0008 D4.3, verbatim: `HEAT-mole` with n_in,i = 1, n_out,i = 0.5 gives +0.5 mol/s.

    Exact, not approximate: the row is linear and 1.0 - 0.5 is representable. The value is
    checked on the row itself rather than through a compile and a CSC extraction, which would be
    testing the compiler.
    """
    spec = build_heater_flash_spec()
    state = consistent_state(spec)
    state[flow_id("S2", "A")] = 1.0
    state[flow_id("S3", "A")] = 0.5
    rows = row_values(spec, state)
    assert rows[row_id("U-HEAT", "HEAT-mole", "A")] == 0.5


def test_d4_3_flash_mole_carries_the_same_orientation() -> None:
    """`FLASH-mole` is `n_in - n_vap - n_liq`: inflow minus outflow, like every balance row."""
    spec = build_heater_flash_spec()
    state = consistent_state(spec)
    state[flow_id("S3", "A")] = 1.0
    state[flow_id("S4", "A")] = 0.25
    state[flow_id("S5", "A")] = 0.25
    rows = row_values(spec, state)
    assert rows[row_id("U-FLASH", "FLASH-mole", "A")] == 0.5


@pytest.mark.parametrize(
    ("unit", "equation", "component"),
    [("U-HEAT", "HEAT-mole", "B"), ("U-FLASH", "FLASH-mole", "B")],
)
def test_d4_3_balance_rows_change_sign_with_the_imbalance(
    unit: str, equation: str, component: str
) -> None:
    """D4.3's general rule: sign(F_row) = sign(inflow - outflow + sources).

    Two states, one either side. A row written outflow-minus-inflow passes neither.
    """
    spec = build_heater_flash_spec()
    inlet = "S2" if unit == "U-HEAT" else "S3"
    outlets = ("S3",) if unit == "U-HEAT" else ("S4", "S5")

    surplus = consistent_state(spec)
    surplus[flow_id(inlet, component)] = 3.0
    for stream in outlets:
        surplus[flow_id(stream, component)] = 0.5
    assert row_values(spec, surplus)[row_id(unit, equation, component)] > 0.0

    deficit = consistent_state(spec)
    deficit[flow_id(inlet, component)] = 0.5
    for stream in outlets:
        deficit[flow_id(stream, component)] = 3.0
    assert row_values(spec, deficit)[row_id(unit, equation, component)] < 0.0


@pytest.mark.parametrize("unit", ["U-HEAT", "U-FLASH"])
def test_d4_3_duty_rows_treat_the_duty_as_a_source(unit: str) -> None:
    """`Q` enters a duty row with `+`: positive into the unit (ADR 0001 D4.1).

    Raising the duty at a fixed enthalpy state must raise the residual by exactly the same
    amount, which is what "source" means in `inflow - outflow + sources`.
    """
    spec = build_heater_flash_spec()
    base = consistent_state(spec)
    raised = dict(base)
    raised[duty_id(unit)] = base[duty_id(unit)] + 1000.0
    equation = row_id(unit, "HEAT-duty" if unit == "U-HEAT" else "FLASH-duty")
    delta = row_values(spec, raised)[equation] - row_values(spec, base)[equation]
    assert delta == pytest.approx(1000.0, rel=1e-12)


def test_the_duty_row_vanishes_at_the_reference_solution(
    reference_values: Mapping[str, Any],
) -> None:
    """A residual is only right if it is zero where the reference says the answer is.

    The heater's rows are evaluated at the registered nominal state, with the duty set to Fable's
    20-digit `Q_heater_W`. A sign error, a missing term or a wrong enthalpy reference would all
    show here and nowhere in the sign tests above.
    """
    case = variants(reference_values)["SYN-001-nominal"]
    spec = build_heater_flash_spec()
    state = {name: 0.0 for name in spec.variable_ids}
    mixed = [float(value) for value in case["mixed_feed_mol_per_s"]]
    for index, component in enumerate(COMPONENTS):
        state[flow_id("S2", component)] = mixed[index]
        state[flow_id("S3", component)] = mixed[index]
        # The heater outlet is LIQUID in this variant, so the lifted split is all liquid.
        state[vapor_flow_id("S3", component)] = 0.0
        state[liquid_flow_id("S3", component)] = mixed[index]
    state[temperature_id("S2")] = float(case["T_mix_K"])
    state[temperature_id("S3")] = float(case["T_heater_K"])
    # The flash rows are evaluated too, so its streams need a state inside the declared domain
    # even though this test asserts only about the heater's rows.
    state[temperature_id("S4")] = float(case["T_flash_K"])
    state[temperature_id("S5")] = float(case["T_flash_K"])
    for stream in HF_STREAMS:
        state[pressure_id(stream)] = float(case["P_Pa"])
    state[vapor_total_id("S3")] = 0.0
    state[liquid_total_id("S3")] = sum(mixed)
    state[duty_id("U-HEAT")] = float(case["Q_heater_W"])

    rows = row_values(spec, state)
    assert rows[row_id("U-HEAT", "HEAT-duty")] == pytest.approx(0.0, abs=ENERGY_TOLERANCE)
    for component in COMPONENTS:
        assert rows[row_id("U-HEAT", "HEAT-mole", component)] == 0.0
        assert rows[row_id("U-HEAT", "split", component)] == 0.0
    assert rows[row_id("U-HEAT", "HEAT-T")] == 0.0
    assert rows[row_id("U-HEAT", "HEAT-pressure")] == 0.0
    assert rows[row_id("U-HEAT", "Vdef")] == 0.0
    # `Ldef` is `L - l_A - l_B - l_C` and the test set `L` with Python's `sum`. The two
    # associations differ by one rounding, 6.7e-16 mol/s here, which is associativity and not a
    # defect; the registered component tolerance is 3.1e-8 mol/s.
    assert rows[row_id("U-HEAT", "Ldef")] == pytest.approx(0.0, abs=FLOW_TOLERANCE)


def test_the_flash_rows_vanish_at_the_reference_solution(
    reference_values: Mapping[str, Any],
) -> None:
    """The same, for the flash, at the registered nominal split."""
    case = variants(reference_values)["SYN-001-nominal"]
    spec = build_heater_flash_spec()
    state = {name: 0.0 for name in spec.variable_ids}
    mixed = [float(value) for value in case["mixed_feed_mol_per_s"]]
    total = float(case["V_mol_per_s"]) + float(case["L_mol_per_s"])
    vapor = [float(value) * float(case["V_mol_per_s"]) for value in case["y"]]
    liquid = [float(value) * float(case["L_mol_per_s"]) for value in case["x"]]
    for index, component in enumerate(COMPONENTS):
        state[flow_id("S3", component)] = mixed[index]
        state[flow_id("S4", component)] = vapor[index]
        state[flow_id("S5", component)] = liquid[index]
        state[vapor_flow_id("S3", component)] = 0.0
        state[liquid_flow_id("S3", component)] = mixed[index]
    for stream, temperature in (
        ("S3", float(case["T_heater_K"])),
        ("S4", float(case["T_flash_K"])),
        ("S5", float(case["T_flash_K"])),
    ):
        state[temperature_id(stream)] = temperature
    for stream in HF_STREAMS:
        state[pressure_id(stream)] = float(case["P_Pa"])
    state[liquid_total_id("S3")] = sum(mixed)
    state[total_flow_id("S4")] = float(case["V_mol_per_s"])
    state[total_flow_id("S5")] = float(case["L_mol_per_s"])
    state[duty_id("U-FLASH")] = float(case["Q_flash_W"])

    rows = row_values(spec, state)
    for component in COMPONENTS:
        assert rows[row_id("U-FLASH", "FLASH-mole", component)] == pytest.approx(
            0.0, abs=FLOW_TOLERANCE
        )
        # (mol/s)^2, so the equilibrium residual scales with the square of the throughput.
        assert rows[row_id("U-FLASH", "FLASH-equilibrium", component)] == pytest.approx(
            0.0, abs=FLOW_TOLERANCE * total
        )
    for port in ("vapor", "liquid"):
        assert rows[row_id("U-FLASH", "FLASH-T", port)] == 0.0
        assert rows[row_id("U-FLASH", "FLASH-P", port)] == 0.0
    assert rows[row_id("U-FLASH", "FLASH-P", "inlet")] == 0.0
    assert rows[row_id("U-FLASH", "Ndef", "vapor")] == pytest.approx(0.0, abs=FLOW_TOLERANCE)
    assert rows[row_id("U-FLASH", "Ndef", "liquid")] == pytest.approx(0.0, abs=FLOW_TOLERANCE)
    assert rows[row_id("U-FLASH", "FLASH-duty")] == pytest.approx(0.0, abs=ENERGY_TOLERANCE)


def test_equilibrium_is_exact_when_a_component_is_absent() -> None:
    """ADR 0001 D3.3: `v_i L - K_i l_i V` never touches ln(0) and is exactly zero at n_i = 0."""
    spec = build_heater_flash_spec()
    state = consistent_state(spec)
    for name in (flow_id("S4", "B"), flow_id("S5", "B")):
        state[name] = 0.0
    rows = row_values(spec, state)
    assert rows[row_id("U-FLASH", "FLASH-equilibrium", "B")] == 0.0


def test_the_declared_pressure_rows_over_determine_the_pressure_network() -> None:
    """A measured structural finding, recorded rather than repaired.

    `FLASH-P` declares `P_in - P_spec = 0` as well as both outlet pressures, and `HEAT-pressure`
    already fixes the same inlet pressure from upstream. In a loop whose declared pressure drops
    are all zero, that row is linearly dependent. K02 assembles the rows as the manifests declare
    them; finding and reporting the rank is K03's structural analysis, and dropping a row here to
    make a count come out would hide it.
    """
    spec = build_heater_flash_spec()
    spec.validate()
    pressure_rows = [
        equation.equation_id for equation in spec.equations if "-P" in equation.equation_id
    ]
    assert row_id("U-FLASH", "FLASH-P", "inlet") in pressure_rows
    # S2 is an open boundary here, so its five variables are unconstrained by these two units.
    assert len(spec.variable_ids) == 32
    assert len(spec.equations) == 28
    assert len(spec.equations) == len(spec.variable_ids) - 5 + 1


def test_compiled_heater_flash_rows_agree_with_the_float_route() -> None:
    """Checks the adapter's wiring of five blocks and thirty-two variables, not the equations."""
    spec = build_heater_flash_spec()
    problem = compile_problem(spec)
    metadata = problem.metadata
    context = EvaluationContext(
        model_version=metadata.model_version, constants_sha256=metadata.constants_sha256
    )
    state = consistent_state(spec)
    result = problem.residual(np.array(state_vector(spec, state)), context)
    assert result.status == "ok", result.message
    assert result.values is not None
    expected = row_vector(spec, state)
    for equation_id, got, want in zip(result.equation_ids, result.values, expected, strict=True):
        assert got == pytest.approx(want, rel=1e-12, abs=1e-9), equation_id


def test_the_compiled_jacobian_keeps_the_blocks_structural_zeros() -> None:
    """`has_jac_sparsity` is what stops an opaque call becoming a dense one (P02's 66 vs 60).

    The enthalpy block declares `dH_i/dn_j = 0` for `j != i`; if that declaration were ignored,
    the assembled duty row would gain entries against flows it does not depend on.
    """
    spec = build_heater_flash_spec()
    problem = compile_problem(spec)
    metadata = problem.metadata
    context = EvaluationContext(
        model_version=metadata.model_version, constants_sha256=metadata.constants_sha256
    )
    result = problem.jacobian(np.array(state_vector(spec, consistent_state(spec))), context)
    assert result.status == "ok", result.message
    assert result.pattern_provenance == "backend-declared"
    entries = set()
    for column, col_id in enumerate(result.col_ids):
        for offset in range(result.indptr[column], result.indptr[column + 1]):
            entries.add((result.row_ids[result.indices[offset]], col_id))

    # dQ_h/dQ_h is exactly 1 and must be present; the duty row depends on every lifted flow of
    # its outlet but on no flow of a stream it does not read.
    assert (row_id("U-HEAT", "HEAT-duty"), duty_id("U-HEAT")) in entries
    assert (row_id("U-HEAT", "HEAT-duty"), vapor_flow_id("S3", "A")) in entries
    assert (row_id("U-HEAT", "HEAT-duty"), flow_id("S4", "A")) not in entries
    assert (row_id("U-HEAT", "HEAT-mole", "A"), temperature_id("S2")) not in entries


def test_the_equilibrium_row_has_the_sign_its_statement_declares() -> None:
    """`y_i - K_i x_i`, scaled by V L, so an over-vaporized component gives a positive residual.

    The root of the row does not depend on its overall sign, so the "vanishes at the reference"
    tests above cannot see a flipped one. This can.
    """
    spec = build_heater_flash_spec()
    state = consistent_state(spec)
    # K_B(360 K, P_r) = 1 exactly, so equilibrium at these totals means v_B / V = l_B / L.
    state[total_flow_id("S4")] = 1.0
    state[total_flow_id("S5")] = 1.0
    state[flow_id("S5", "B")] = 0.4
    state[temperature_id("S4")] = 360.0
    state[pressure_id("S4")] = 100_000.0

    state[flow_id("S4", "B")] = 0.4
    assert row_values(spec, state)[row_id("U-FLASH", "FLASH-equilibrium", "B")] == pytest.approx(
        0.0, abs=1e-15
    )

    state[flow_id("S4", "B")] = 0.6
    assert row_values(spec, state)[row_id("U-FLASH", "FLASH-equilibrium", "B")] > 0.0

    state[flow_id("S4", "B")] = 0.2
    assert row_values(spec, state)[row_id("U-FLASH", "FLASH-equilibrium", "B")] < 0.0


def jacobian_entries(spec: Any, state: Mapping[str, float]) -> dict[tuple[str, str], float]:
    """The assembled Jacobian read back by name, never by position."""
    problem = compile_problem(spec)
    metadata = problem.metadata
    context = EvaluationContext(
        model_version=metadata.model_version, constants_sha256=metadata.constants_sha256
    )
    result = problem.jacobian(np.array(state_vector(spec, state)), context)
    assert result.status == "ok", result.message
    entries: dict[tuple[str, str], float] = {}
    for column, col_id in enumerate(result.col_ids):
        for offset in range(result.indptr[column], result.indptr[column + 1]):
            entries[(result.row_ids[result.indices[offset]], col_id)] = result.data[offset]
    return entries


def test_the_enthalpy_blocks_state_derivatives_are_the_analytic_ones() -> None:
    """Written out from the derivation, not read back from the block.

    `HEAT-duty` is `Q + Hdot(S2) - Hdot(S3)`, so

        d/dT_S3 = -sum_i (v_i dh_i^V/dT + l_i dh_i^L/dT) = -c_p (V_sum + L_sum),
        d/dP_S3 = -sum_i l_i v_i^molar,   because h^V has no pressure dependence at all,

    with c_p = 100 J/(mol K) and v_i^molar = 1e-4 m3/mol from the SYN-001 constants. A block
    that forgets to multiply its state derivative by the flow gets both of these wrong while
    still returning correct values.
    """
    spec = build_heater_flash_spec()
    state = consistent_state(spec)
    entries = jacobian_entries(spec, state)

    lifted_total = sum(
        state[vapor_flow_id("S3", name)] + state[liquid_flow_id("S3", name)] for name in COMPONENTS
    )
    liquid_total = sum(state[liquid_flow_id("S3", name)] for name in COMPONENTS)

    assert entries[(row_id("U-HEAT", "HEAT-duty"), temperature_id("S3"))] == pytest.approx(
        -100.0 * lifted_total, rel=1e-12
    )
    assert entries[(row_id("U-HEAT", "HEAT-duty"), pressure_id("S3"))] == pytest.approx(
        -1e-4 * liquid_total, rel=1e-12
    )
    # And the inlet side, which is a single-phase liquid block: +c_p n_tot, opposite sign.
    inlet_total = sum(state[flow_id("S2", name)] for name in COMPONENTS)
    assert entries[(row_id("U-HEAT", "HEAT-duty"), temperature_id("S2"))] == pytest.approx(
        100.0 * inlet_total, rel=1e-12
    )


def test_the_enthalpy_block_flow_derivative_is_the_molar_enthalpy() -> None:
    """`dH_i/dn_i = h_i`, so the duty row's flow column is the molar enthalpy itself.

    h_i^L(T, P) = c_p (T - T_r) + v_i (P - P_r) from the derivation §2; at S2's state in
    `consistent_state` that is 100 (321.2 - 300) + 1e-4 (0) = 2120 J/mol.
    """
    spec = build_heater_flash_spec()
    entries = jacobian_entries(spec, consistent_state(spec))
    expected = 100.0 * (321.2 - 300.0)
    assert entries[(row_id("U-HEAT", "HEAT-duty"), flow_id("S2", "A"))] == pytest.approx(
        expected, rel=1e-12
    )


def test_the_lnk_block_declares_a_pressure_column_that_carries_a_real_derivative() -> None:
    """dlnK_i/dP = -1/P + v_i/(RT), which the reference values pin at 360 K and P_r.

    A block that declared only the temperature column would drop the equilibrium row's entire
    pressure dependence, and the assembled system would be wrong in a way no value test sees.
    """
    spec = build_heater_flash_spec()
    state = consistent_state(spec)
    state[temperature_id("S4")] = 360.0
    state[pressure_id("S4")] = 100_000.0
    entries = jacobian_entries(spec, state)
    #  d(eq_B)/dP = -K_B l_B V dlnK_B/dP, with K_B(360 K, P_r) = 1 exactly.
    d_ln_k_d_p = -9.9665910124881316552e-6
    expected = -1.0 * state[flow_id("S5", "B")] * state[total_flow_id("S4")] * d_ln_k_d_p
    assert entries[
        (row_id("U-FLASH", "FLASH-equilibrium", "B"), pressure_id("S4"))
    ] == pytest.approx(expected, rel=1e-9)


def test_a_state_outside_the_declared_domain_reaches_the_boundary_as_a_typed_failure() -> None:
    """A block's `DomainError` becomes `invalid_trial_state`, not `ok` and not a bare crash.

    This is the compiled path, not the evaluator path: a solver that steps outside the provider's
    domain has to be told to shorten its step, and it learns that from the status.
    """
    spec = build_heater_flash_spec()
    problem = compile_problem(spec)
    metadata = problem.metadata
    context = EvaluationContext(
        model_version=metadata.model_version, constants_sha256=metadata.constants_sha256
    )
    state = consistent_state(spec)
    state[temperature_id("S2")] = 200.0
    result = problem.residual(np.array(state_vector(spec, state)), context)
    assert result.status == "invalid_trial_state"
    assert result.values is None
    assert "outside" in result.message


def test_a_nonzero_declared_pressure_drop_lowers_the_outlet() -> None:
    """`HEAT-pressure` is `P_out - P_in + dP = 0`, so dP is a *drop*: P_out = P_in - dP.

    Every registered SYN-001 case declares dP = 0, which makes the sign of that term invisible.
    A sweep found it: flipping `+ parameters[offset]` to `- parameters[offset]` passed the whole
    suite. ADR 0001 D4.5 makes the pressure row explicit precisely so it can be wrong in a way
    someone notices, so it is exercised here at a drop the fixture never uses.
    """
    heater = TPHeater(
        unit_id="U-HEAT",
        provider=PROVIDER,
        outlet_temperature=350.0,
        context=CONTEXT,
        inlet_phase="LIQUID",
        pressure_drop=20_000.0,
    )
    inlet = StreamState(n=(1.0, 1.0, 1.0), temperature=300.0, pressure=100_000.0)
    result = heater.evaluate({"inlet": (inlet,)}, CONTEXT)
    assert result.status == "ok", result.message
    assert result.outlets["outlet"].pressure == 80_000.0

    spec = assemble(
        label="K02-pressure-drop",
        units=[heater],
        wiring={"U-HEAT": Wiring({"inlet": ("S2",), "outlet": ("S3",)})},
        streams=("S2", "S3"),
        components=COMPONENTS,
    )
    state = {name: 0.0 for name in spec.variable_ids}
    for stream, pressure in (("S2", 100_000.0), ("S3", 80_000.0)):
        state[temperature_id(stream)] = 350.0
        state[pressure_id(stream)] = pressure
        for component in COMPONENTS:
            state[flow_id(stream, component)] = 1.0
    for component in COMPONENTS:
        state[liquid_flow_id("S3", component)] = 1.0
    state[liquid_total_id("S3")] = 3.0
    rows = row_values(spec, state)
    assert rows[row_id("U-HEAT", "HEAT-pressure")] == 0.0

    # And the row is not satisfied by the zero-drop answer, which is what makes this a test.
    state[pressure_id("S3")] = 100_000.0
    assert row_values(spec, state)[row_id("U-HEAT", "HEAT-pressure")] == 20_000.0


def test_a_lifting_definition_row_has_the_sign_its_name_implies() -> None:
    """`Vdef` is `V - sum_i v_i`, so too large a total is a positive residual.

    At any solution the row is zero either way round, so the reference-state tests cannot see a
    negated definition row. A sweep found that too.
    """
    spec = build_heater_flash_spec()
    state = consistent_state(spec)
    total = sum(state[vapor_flow_id("S3", name)] for name in COMPONENTS)

    state[vapor_total_id("S3")] = total
    # `sum()` and the row's sequential subtraction associate differently, so this is a rounding
    # bound and not an exact zero -- the same associativity point as the `Ldef` test elsewhere.
    assert row_values(spec, state)[row_id("U-HEAT", "Vdef")] == pytest.approx(0.0, abs=1e-15)

    state[vapor_total_id("S3")] = total + 0.25
    assert row_values(spec, state)[row_id("U-HEAT", "Vdef")] == pytest.approx(0.25, abs=1e-15)

    state[total_flow_id("S4")] = sum(state[flow_id("S4", name)] for name in COMPONENTS) - 0.5
    assert row_values(spec, state)[row_id("U-FLASH", "Ndef", "vapor")] == pytest.approx(
        -0.5, abs=1e-15
    )
