"""S11 WO-C2: `thermal.heater`, `thermal.valve`, `thermal.mixer`, `thermal.flash` by direct
construction (S11 units design §4.4; S11.A50 for these four, A51, A52, A56, A57, A58).

Independent expectations: CoolProp 8.0.0's PH flashes (`benchmarks/s11/thermal_reference.yaml`,
whose steam-table brackets bound it), and the unit's own EO rows evaluated at its causal answer
(every row within its kind's registered tolerance: the energy balances close, and the evaluate
and the rows describe the same function). Water on the in-tree `iapws95-v1`; no CoolProp needed.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
import yaml

from openflowsheet.compile.reference import row_values
from openflowsheet.compiled import EvaluationContext
from openflowsheet.models import (
    SpecificationError,
    UnitEvaluation,
    Wiring,
    assemble,
    duty_id,
    flow_id,
    pressure_id,
    temperature_id,
)
from openflowsheet.models.thermal import kernel as k
from openflowsheet.models.thermal.flash import ThermalFlash
from openflowsheet.models.thermal.heater import ThermalHeater
from openflowsheet.models.thermal.mixer import ThermalMixer
from openflowsheet.models.thermal.state import SaturatedStreamState, liquid_id, vapor_id
from openflowsheet.models.thermal.valve import ThermalValve
from openflowsheet.thermo import StreamState
from openflowsheet.thermo.iapws95 import Iapws95Provider
from openflowsheet.verify.checks import KIND_TOLERANCE

ROOT = Path(__file__).resolve().parents[1]
UNITS = yaml.safe_load((ROOT / "benchmarks/s11/thermal_reference.yaml").read_text())["units"]
CONTEXT = EvaluationContext(model_version="s11-thermal-units", constants_sha256="0" * 64)
WATER = Iapws95Provider()
P_ATM = 101325.0
H2O = "H2O"


def _sat(pressure: float) -> k.Sat:
    sat = k.saturation(WATER, pressure, CONTEXT)
    assert not isinstance(sat, k.Failure), sat.message
    return sat


def _saturated(total: float, pressure: float, beta: float) -> SaturatedStreamState:
    return SaturatedStreamState((total,), _sat(pressure).temperature, pressure, vapor_fraction=beta)


# -- the EO face at the causal answer -------------------------------------------------------------


def _stream_values(stream: str, state: StreamState) -> dict[str, float]:
    values = {
        flow_id(stream, H2O): state.n[0],
        temperature_id(stream): state.temperature,
        pressure_id(stream): state.pressure,
    }
    if isinstance(state, SaturatedStreamState):
        vapour = state.vapor_fraction * state.n[0]
        values[vapor_id(stream)] = vapour
        values[liquid_id(stream)] = state.n[0] - vapour
    return values


def _check_face(
    unit: Any,
    inlets: Mapping[str, tuple[StreamState, ...]],
    answer: UnitEvaluation,
) -> None:
    """Square, and every row within its kind's tolerance at the evaluate's answer."""
    streams = [s for port in unit.streams for s in unit.streams[port]]
    spec = assemble(
        label="S11-C2",
        units=[unit],
        wiring={unit.unit_id: Wiring(dict(unit.streams))},
        streams=streams,
        components=(H2O,),
    )
    # A saturated inlet's carried split is its producer's column; a unit-only spec allocates it.
    carried = tuple(
        name
        for port in inlets
        for stream in unit.streams[port]
        if unit.forms[stream] == "SATURATED"
        for name in (vapor_id(stream), liquid_id(stream))
    )
    spec = dataclasses.replace(spec, variable_ids=(*spec.variable_ids, *carried))
    contribution = unit.contribute(Wiring(dict(unit.streams)), (H2O,))
    # Unknowns: the outlet streams' (n, T, P) and the unit's owned columns; the inlets are given.
    # A mixer's TM-pressure rows also fix all but one inlet pressure in a flowsheet (as K02's
    # MIX-pressure does), so it authors K - 1 rows beyond its own unknowns.
    unknowns = {
        name
        for port, connected in unit.streams.items()
        if port not in inlets
        for stream in connected
        for name in (flow_id(stream, H2O), temperature_id(stream), pressure_id(stream))
    } | set(contribution.variable_ids)
    extra = len(unit.streams["inlet"]) - 1 if unit.model_id == "thermal.mixer" else 0
    assert len(spec.equations) == len(unknowns) + extra, (len(spec.equations), sorted(unknowns))

    values: dict[str, float] = {}
    for port, states in inlets.items():
        for stream, state in zip(unit.streams[port], states, strict=True):
            values.update(_stream_values(stream, state))
    for port, state in answer.outlets.items():
        (stream,) = unit.streams[port]
        values.update(_stream_values(stream, state))
    values.update(answer.owned)  # type: ignore[attr-defined]
    if duty_id(unit.unit_id) in spec.variable_ids:
        assert answer.duty is not None
        values[duty_id(unit.unit_id)] = answer.duty
    residuals = row_values(spec, values)
    for row, value in residuals.items():
        kind = spec.row_kinds[row]
        assert abs(value) <= KIND_TOLERANCE[kind], (row, value)


def _forms(**forms: str) -> dict[str, Any]:
    return dict(forms)


def _heater(outlet_form: str, inlet_form: str = "LIQUID", **spec: float) -> ThermalHeater:
    return ThermalHeater(
        unit_id="U1",
        provider=WATER,
        context=CONTEXT,
        streams={"inlet": ("S1",), "outlet": ("S2",)},
        forms=_forms(S1=inlet_form, S2=outlet_form),
        **spec,  # type: ignore[arg-type]
    )


def _ok(answer: UnitEvaluation) -> UnitEvaluation:
    assert answer.status == "ok", answer.message
    return answer


# -- S11.A50 DOF and refusals ---------------------------------------------------------------------

HEATER_CASES = [
    ("T", "LIQUID", "LIQUID", StreamState((1.0,), 300.0, P_ATM), {"outlet_temperature": 350.0}),
    ("T", "VAPOR", "LIQUID", StreamState((1.0,), 300.0, P_ATM), {"outlet_temperature": 500.0}),
    ("duty", "LIQUID", "LIQUID", StreamState((1.0,), 300.0, P_ATM), {"duty": 2000.0}),
    ("duty", "VAPOR", "VAPOR", StreamState((1.0,), 400.0, P_ATM), {"duty": 1000.0}),
    ("duty", "SATURATED", "LIQUID", StreamState((1.0,), 300.0, P_ATM), {"duty": 25000.0}),
    ("quality", "SATURATED", "SATURATED", "sat0", {"outlet_vapor_fraction": 0.4}),
    (
        "quality",
        "SATURATED",
        "VAPOR",
        StreamState((1.0,), 400.0, P_ATM),
        {"outlet_vapor_fraction": 1.0},
    ),
]


@pytest.mark.parametrize(("mode", "outlet_form", "inlet_form", "feed", "spec"), HEATER_CASES)
def test_a50_heater_every_mode_and_form_is_square_and_closes(
    mode: str, outlet_form: str, inlet_form: str, feed: Any, spec: dict[str, float]
) -> None:
    if feed == "sat0":
        feed = _saturated(1.0, P_ATM, 0.0)
    unit = _heater(outlet_form, inlet_form, **spec)
    assert unit.mode == mode
    assert unit.dormancy_configuration == f"{mode}:{outlet_form}"
    answer = _ok(unit.evaluate({"inlet": (feed,)}, CONTEXT))
    _check_face(unit, {"inlet": (feed,)}, answer)
    unit.manifest()


@pytest.mark.parametrize("outlet_form", ["LIQUID", "VAPOR", "SATURATED"])
def test_a50_valve_every_form_is_square_and_closes(outlet_form: str) -> None:
    feeds = {
        "LIQUID": (StreamState((1.0,), 300.0, 1.0e6), 1.0e5),
        "VAPOR": (StreamState((1.0,), 600.0, 1.0e6), 1.0e5),
        "SATURATED": (_saturated(1.0, 1.0e6, 0.0), 1.0e5),
    }
    feed, pressure = feeds[outlet_form]
    inlet_form = "SATURATED" if isinstance(feed, SaturatedStreamState) else outlet_form
    unit = ThermalValve(
        "U1",
        WATER,
        CONTEXT,
        {"inlet": ("S1",), "outlet": ("S2",)},
        _forms(S1=inlet_form, S2=outlet_form),
        outlet_pressure=pressure,
    )
    answer = _ok(unit.evaluate({"inlet": (feed,)}, CONTEXT))
    _check_face(unit, {"inlet": (feed,)}, answer)
    unit.manifest()


@pytest.mark.parametrize("outlet_form", ["LIQUID", "VAPOR", "SATURATED"])
def test_a50_mixer_every_form_is_square_and_closes(outlet_form: str) -> None:
    temperatures = {"LIQUID": (300.0, 340.0), "VAPOR": (400.0, 450.0), "SATURATED": (400.0, 300.0)}
    first, second = temperatures[outlet_form]
    feeds = (StreamState((1.0,), first, P_ATM), StreamState((1.0,), second, P_ATM))
    forms = {
        "LIQUID": ("LIQUID", "LIQUID"),
        "VAPOR": ("VAPOR", "VAPOR"),
        "SATURATED": ("VAPOR", "LIQUID"),
    }[outlet_form]
    unit = ThermalMixer(
        "U1",
        WATER,
        CONTEXT,
        {"inlet": ("S1", "S3"), "outlet": ("S2",)},
        _forms(S1=forms[0], S3=forms[1], S2=outlet_form),
    )
    answer = _ok(unit.evaluate({"inlet": feeds}, CONTEXT))
    _check_face(unit, {"inlet": feeds}, answer)
    unit.manifest()


def _drum(inlet_form: str = "SATURATED", **spec: float) -> ThermalFlash:
    return ThermalFlash(
        "U1",
        WATER,
        CONTEXT,
        {"inlet": ("S1",), "vapor": ("S2",), "liquid": ("S3",)},
        _forms(S1=inlet_form, S2="SATURATED", S3="SATURATED"),
        **spec,  # type: ignore[arg-type]
    )


def test_a50_flash_is_square_and_closes() -> None:
    feed = _saturated(1.0, 5.0e5, 0.3)
    unit = _drum(duty=500.0, pressure_drop=1.0e4)
    answer = _ok(unit.evaluate({"inlet": (feed,)}, CONTEXT))
    _check_face(unit, {"inlet": (feed,)}, answer)
    assert len(unit.contribute(Wiring(dict(unit.streams)), (H2O,)).equations) == 11
    unit.manifest()


@pytest.mark.parametrize(
    ("build", "what", "hint"),
    [
        (
            lambda: _heater("SATURATED", outlet_temperature=400.0),
            "outlet.T",
            "a pure-fluid outlet at a specified temperature is single-phase; specify "
            "outlet_vapor_fraction or the duty",
        ),
        (
            lambda: _heater("LIQUID", outlet_vapor_fraction=0.5),
            "outlet_vapor_fraction",
            "declare the outlet vapor_liquid",
        ),
        (
            lambda: _heater("SATURATED", outlet_vapor_fraction=1.5),
            "outlet_vapor_fraction",
            "outside [0, 1]",
        ),
        (
            lambda: _heater("LIQUID", outlet_temperature=300.0, duty=1.0),
            "specification",
            "exactly one of",
        ),
        (lambda: _heater("LIQUID"), "specification", "exactly one of"),
        (
            lambda: ThermalFlash(
                "U1",
                WATER,
                CONTEXT,
                {"inlet": ("S1",), "vapor": ("S2",), "liquid": ("S3",)},
                _forms(S1="SATURATED", S2="VAPOR", S3="SATURATED"),
            ),
            "vapor",
            "a drum's products are saturated (ADR 0051 D4)",
        ),
    ],
)
def test_a50_refusals_give_their_code_and_hint(build: Any, what: str, hint: str) -> None:
    with pytest.raises(SpecificationError) as raised:
        build()
    code, detail = str(raised.value).split("\n", 1)
    assert code == f"specification_unsupported(U1.{what})"
    assert hint in detail


# -- S11.A51 throttling ---------------------------------------------------------------------------


def _valve(outlet_form: str, pressure: float, inlet_form: str = "SATURATED") -> ThermalValve:
    return ThermalValve(
        "U1",
        WATER,
        CONTEXT,
        {"inlet": ("S1",), "outlet": ("S2",)},
        _forms(S1=inlet_form, S2=outlet_form),
        outlet_pressure=pressure,
    )


def test_a51_throttling_saturated_liquid() -> None:
    ref = UNITS["A51_throttling"]
    feed = _saturated(1.0, ref["inlet"]["P"], 0.0)
    answer = _ok(_valve("SATURATED", ref["outlet"]["P"]).evaluate({"inlet": (feed,)}, CONTEXT))
    out = answer.outlets["outlet"]
    assert isinstance(out, SaturatedStreamState)
    assert abs(out.vapor_fraction - ref["outlet"]["beta"]) <= 1e-7
    assert abs(out.vapor_fraction - 0.1528) <= 5e-4
    assert out.temperature == _sat(ref["outlet"]["P"]).temperature
    assert abs(out.temperature - ref["outlet"]["T_sat"]) <= 2e-6
    assert answer.phase_signature == "TWO_PHASE"


def test_valve_refuses_a_pressure_rise() -> None:
    answer = _valve("LIQUID", 2.0e6, "LIQUID").evaluate(
        {"inlet": (StreamState((1.0,), 300.0, 1.0e6),)}, CONTEXT
    )
    assert answer.status == "out_of_domain"
    assert answer.message.splitlines()[0] == "pressure_rise(valve)"


# -- S11.A52 heater -------------------------------------------------------------------------------


def test_a52_i_quality_zero_to_one_is_the_latent_heat() -> None:
    ref = UNITS["A52_heater"]
    feed = _saturated(ref["n"], ref["P"], 0.0)
    answer = _ok(
        _heater("SATURATED", "SATURATED", outlet_vapor_fraction=1.0).evaluate(
            {"inlet": (feed,)}, CONTEXT
        )
    )
    expected = ref["n"] * ref["quality_0_to_1"]["Q"]
    assert answer.duty is not None and abs(answer.duty - expected) <= 1e-8 * abs(expected)
    assert answer.phase_signature == "VAPOR"


def test_a52_ii_temperature_mode_liquid_to_vapour() -> None:
    ref = UNITS["A52_heater"]["t_mode"]
    feed = StreamState((1.0,), ref["T_in"], P_ATM)
    answer = _ok(
        _heater("VAPOR", outlet_temperature=ref["T_out"]).evaluate({"inlet": (feed,)}, CONTEXT)
    )
    assert answer.duty is not None and abs(answer.duty - ref["Q"]) <= 1e-8 * abs(ref["Q"])


def test_a52_iii_duty_mode_lands_at_half_quality() -> None:
    ref = UNITS["A52_heater"]["duty_mode"]
    feed = StreamState((1.0,), ref["T_in"], P_ATM)
    answer = _ok(_heater("SATURATED", duty=ref["Q"]).evaluate({"inlet": (feed,)}, CONTEXT))
    out = answer.outlets["outlet"]
    assert isinstance(out, SaturatedStreamState)
    assert ref["regime"] == "SATURATED"
    assert abs(out.vapor_fraction - ref["beta"]) <= 1e-7


def test_a52_iv_duty_mode_declared_liquid_landing_saturated_is_a_mismatch() -> None:
    ref = UNITS["A52_heater"]["duty_mode"]
    feed = StreamState((1.0,), ref["T_in"], P_ATM)
    answer = _heater("LIQUID", duty=ref["Q"]).evaluate({"inlet": (feed,)}, CONTEXT)
    assert answer.status == "unsupported"
    code, detail = answer.message.split("\n", 1)
    assert code == "phase_regime_mismatch(S2)"
    assert "closure SATURATED" in detail and detail.endswith("declare vapor_liquid")


def test_heater_temperature_mode_outside_the_declared_phase_is_a_mismatch() -> None:
    answer = _heater("LIQUID", outlet_temperature=450.0).evaluate(
        {"inlet": (StreamState((1.0,), 300.0, P_ATM),)}, CONTEXT
    )
    assert answer.message.split("\n")[0] == "phase_regime_mismatch(S2)"
    assert answer.message.endswith("declare vapor")


def test_inlet_refusals_are_typed() -> None:
    vapour = StreamState((1.0,), 450.0, P_ATM)
    answer = _heater("VAPOR", "LIQUID", duty=10.0).evaluate({"inlet": (vapour,)}, CONTEXT)
    assert answer.message.split("\n")[0] == "inadmissible_phase(inlet, LIQUID)"
    plain = StreamState((1.0,), _sat(P_ATM).temperature, P_ATM)
    answer = _heater("VAPOR", "SATURATED", duty=10.0).evaluate({"inlet": (plain,)}, CONTEXT)
    assert answer.status == "error"
    assert answer.message.split("\n")[0] == "carried_split_missing(S1)"
    off_line = SaturatedStreamState((1.0,), plain.temperature + 1e-5, P_ATM, vapor_fraction=0.5)
    answer = _heater("VAPOR", "SATURATED", duty=10.0).evaluate({"inlet": (off_line,)}, CONTEXT)
    assert answer.message.split("\n")[0] == "carried_split_inconsistent(S1)"


# -- S11.A56 mixer --------------------------------------------------------------------------------


def _mixer(outlet_form: str, *inlet_forms: str) -> ThermalMixer:
    inlet_ids = tuple(f"S{2 * i + 1}" for i in range(len(inlet_forms)))
    forms = dict(zip(inlet_ids, inlet_forms, strict=True))
    forms["S2"] = outlet_form
    return ThermalMixer("U1", WATER, CONTEXT, {"inlet": inlet_ids, "outlet": ("S2",)}, forms)  # type: ignore[arg-type]


def test_a56_vapour_and_liquid_make_a_saturated_outlet() -> None:
    ref = UNITS["A56_mixer"]
    feeds = tuple(StreamState((row["n"],), row["T"], ref["P"]) for row in ref["inlets"])
    unit = _mixer("SATURATED", "VAPOR", "LIQUID")
    answer = _ok(unit.evaluate({"inlet": feeds}, CONTEXT))
    out = answer.outlets["outlet"]
    assert isinstance(out, SaturatedStreamState)
    assert abs(out.vapor_fraction - ref["outlet"]["beta"]) <= 1e-7
    assert out.n == (ref["outlet"]["n"],)
    _check_face(unit, {"inlet": feeds}, answer)


def test_a56_a_dormant_inlet_leaves_the_other_inlets_state() -> None:
    flowing = StreamState((1.3,), 320.0, P_ATM)
    dormant = StreamState((0.0,), 500.0, 2.0e5)
    answer = _ok(
        _mixer("LIQUID", "LIQUID", "VAPOR").evaluate({"inlet": (flowing, dormant)}, CONTEXT)
    )
    out = answer.outlets["outlet"]
    assert out.n == flowing.n and out.pressure == flowing.pressure
    assert abs(out.temperature - flowing.temperature) <= 1e-9


def test_mixer_refuses_unequal_flowing_pressures() -> None:
    feeds = (StreamState((1.0,), 300.0, P_ATM), StreamState((1.0,), 300.0, 2.0e5))
    answer = _mixer("LIQUID", "LIQUID", "LIQUID").evaluate({"inlet": feeds}, CONTEXT)
    assert answer.status == "error" and "are not equal" in answer.message


# -- S11.A57 drum ---------------------------------------------------------------------------------


def test_a57_drum_splits_wet_steam_at_its_saturation_temperature() -> None:
    ref = UNITS["A57_drum"]
    total, beta = 2.0, 0.3
    feed = _saturated(total, ref["P"], beta)
    answer = _ok(_drum().evaluate({"inlet": (feed,)}, CONTEXT))
    top, bottom = answer.outlets["vapor"], answer.outlets["liquid"]
    flow = KIND_TOLERANCE["molar_flow"]
    assert abs(top.n[0] - beta * total) <= flow
    assert abs(bottom.n[0] - (1.0 - beta) * total) <= flow
    t_sat = _sat(ref["P"]).temperature
    assert top.temperature == bottom.temperature == t_sat
    assert abs(t_sat - ref["T_sat"]) <= 2e-6
    assert isinstance(top, SaturatedStreamState) and top.vapor_fraction == 1.0
    assert isinstance(bottom, SaturatedStreamState) and bottom.vapor_fraction == 0.0
    assert answer.owned == {  # type: ignore[attr-defined]
        "S2.sat.V": top.n[0],
        "S2.sat.L": 0.0,
        "S3.sat.V": 0.0,
        "S3.sat.L": bottom.n[0],
    }


def test_drum_refuses_a_single_phase_state() -> None:
    feed = StreamState((1.0,), 300.0, P_ATM)
    answer = _drum("LIQUID").evaluate({"inlet": (feed,)}, CONTEXT)
    code, detail = answer.message.split("\n", 1)
    assert code == "phase_regime_mismatch(S1)"
    assert "thermal.flash needs a two-phase state at the drum pressure" in detail


def test_drum_at_beta_zero_gives_a_dormant_vapour_product() -> None:
    feed = _saturated(1.0, 5.0e5, 0.0)
    answer = _ok(_drum().evaluate({"inlet": (feed,)}, CONTEXT))
    assert answer.outlets["vapor"].is_dormant
    assert answer.phase_signature == "LIQUID"


# -- S11.A58 carriage -----------------------------------------------------------------------------


def test_a58_the_carried_split_travels_bitwise_into_a_reader() -> None:
    ref = UNITS["A58_carriage"]
    feed = _saturated(ref["n"], 1.0e6, 0.0)
    valve = _ok(_valve("SATURATED", ref["P"]).evaluate({"inlet": (feed,)}, CONTEXT))
    out = valve.outlets["outlet"]
    assert isinstance(out, SaturatedStreamState)
    vapour = out.vapor_fraction * out.n[0]
    assert valve.owned == {"S2.sat.V": vapour, "S2.sat.L": out.n[0] - vapour}  # type: ignore[attr-defined]
    heater = ThermalHeater(
        "U2",
        WATER,
        CONTEXT,
        {"inlet": ("S2",), "outlet": ("S4",)},
        _forms(S2="SATURATED", S4="SATURATED"),
        outlet_vapor_fraction=1.0,
    )
    answer = _ok(heater.evaluate({"inlet": (out,)}, CONTEXT))
    expected = ref["n"] * ref["Q"]
    assert answer.duty is not None and abs(answer.duty - expected) <= 1e-8 * abs(expected)


# -- dormancy -------------------------------------------------------------------------------------


@pytest.mark.parametrize("outlet_form", ["LIQUID", "SATURATED"])
def test_dormant_inlets_give_labelled_dormant_outlets(outlet_form: str) -> None:
    feed = StreamState((0.0,), 310.0, 2.0e5)
    spec = {"duty": 0.0}
    answer = _ok(
        _heater(outlet_form, pressure_drop=1.0e3, **spec).evaluate({"inlet": (feed,)}, CONTEXT)
    )
    out = answer.outlets["outlet"]
    assert out.is_dormant and out.temperature == 310.0 and out.pressure == 2.0e5 - 1.0e3
    assert answer.duty == 0.0 and answer.phase_signature == "ZERO_FLOW"
    if outlet_form == "SATURATED":
        assert isinstance(out, SaturatedStreamState) and out.vapor_fraction == 0.0
        assert answer.owned == {"S2.sat.V": 0.0, "S2.sat.L": 0.0}  # type: ignore[attr-defined]
    drum = _ok(_drum("LIQUID").evaluate({"inlet": (feed,)}, CONTEXT))
    assert drum.outlets["vapor"].is_dormant and drum.outlets["liquid"].is_dormant
    assert drum.duty == 0.0
