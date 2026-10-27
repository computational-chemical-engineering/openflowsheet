"""S11 WO-C3: the isentropic block variants and `thermal.pump`, `thermal.compressor`,
`thermal.turbine` by direct construction (S11 units design §4.3, §4.4; S11.A50 for the machines,
A53-A55; A46/A48 for the new block variants).

Independent expectations: CoolProp 8.0.0's PS and PH flashes
(`benchmarks/s11/thermal_reference.yaml`, whose steam-table brackets bound it); the thermodynamic
identities dHs/dP_O = n v_s (dh = v dP at constant s, in one phase or two) and
dHs/dT_I = n T_s c_p,I / T_I; an ideal gas's closed-form isentrope for `additive-vapour`; and the
unit's own EO rows evaluated at its causal answer. Water on the in-tree `iapws95-v1`; CO2 and
n-Pentane need CoolProp and skip cleanly without it.
"""

from __future__ import annotations

import dataclasses
import math
from collections.abc import Sequence
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest
import yaml
from s07_coolprop_support import require_coolprop
from test_s11_thermal_kernel import FD_STEP, FD_TOL, _fd_worst

from openflowsheet.compile.casadi_backend import compile_problem
from openflowsheet.compile.reference import row_values
from openflowsheet.compile.spec import DomainError
from openflowsheet.compiled import EvaluationContext
from openflowsheet.models import (
    SpecificationError,
    UnitEvaluation,
    Wiring,
    assemble,
    flow_id,
    pressure_id,
    temperature_id,
)
from openflowsheet.models.syn001.pump import work_id
from openflowsheet.models.syn001.tp_state import enthalpy_block_id
from openflowsheet.models.thermal import kernel as k
from openflowsheet.models.thermal.blocks import (
    IsentropicEnthalpyBlock,
    isentropic_block_id,
    isentropic_state,
)
from openflowsheet.models.thermal.machines import ThermalMachine
from openflowsheet.models.thermal.state import SaturatedStreamState, liquid_id, vapor_id
from openflowsheet.thermo import PropertyProvider, PropertyRequest, PropertyResult, StreamState
from openflowsheet.thermo.iapws95 import Iapws95Provider
from openflowsheet.thermo.wilson_ig_v2 import WilsonIdealGasProviderV2
from openflowsheet.verify.checks import KIND_TOLERANCE

ROOT = Path(__file__).resolve().parents[1]
UNITS = yaml.safe_load((ROOT / "benchmarks/s11/thermal_reference.yaml").read_text())["units"]
CONTEXT = EvaluationContext(model_version="s11-thermal-machines", constants_sha256="0" * 64)
WATER = Iapws95Provider()
H2O = "H2O"
IDENTITY_TOL = 1e-8


def _ok(value: Any) -> Any:
    assert not isinstance(value, k.Failure), value.message
    return value


def _coolprop(component: str) -> PropertyProvider:
    require_coolprop()
    from openflowsheet.thermo.coolprop_heos import CoolPropHeosProvider  # noqa: PLC0415

    return CoolPropHeosProvider(component)


def _sat(pressure: float, provider: PropertyProvider = WATER) -> k.Sat:
    return _ok(k.saturation(provider, pressure, CONTEXT))


# -- the pure variants (A46, A48, identities) -----------------------------------------------------


def _block(variant: str, inlet: str, isentropic: str) -> IsentropicEnthalpyBlock:
    return IsentropicEnthalpyBlock(
        WATER,
        H2O,
        CONTEXT,
        block_id=isentropic_block_id("U1"),
        variant=variant,  # type: ignore[arg-type]
        inlet_phase=inlet,  # type: ignore[arg-type]
        isentropic_phase=isentropic,  # type: ignore[arg-type]
    )


#: (variant, inlet phase, isentropic phase, 20 input tuples): pump and compressor from a saturated
#: inlet, turbine expansions that land wet from superheated or saturated steam.
VARIANT_STATES = [
    (
        "pure-sat/single",
        "LIQUID",
        "LIQUID",
        [(1.0 + 0.1 * i, 1.0e3 * 2**i, 3.0e6 + 1.0e6 * i) for i in range(10)]
        + [(0.5 + 0.1 * i, 1.0e5 * (1 + i), 1.0e7 + 1.0e6 * i) for i in range(10)],
    ),
    (
        "pure-sat/single",
        "VAPOR",
        "VAPOR",
        [(1.0 + 0.1 * i, 1.0e3 * 2**i, 3.0e3 * 2**i) for i in range(10)]
        + [(0.5 + 0.1 * i, 1.0e5 * (1 + i), 2.5e5 * (1 + i)) for i in range(10)],
    ),
    (
        "pure-single/sat",
        "VAPOR",
        "SATURATED",
        [(1.0 + 0.1 * i, 520.0 + 20.0 * i, 3.0e6, 1.0e4 * (1 + i % 5)) for i in range(10)]
        + [(0.5 + 0.1 * i, 460.0 + 10.0 * i, 1.0e6, 2.0e3 * (1 + i)) for i in range(10)],
    ),
    (
        "pure-sat/sat",
        "VAPOR",
        "SATURATED",
        [(1.0 + 0.1 * i, 1.0e5 * (1 + i), 1.0e3 * (1 + i)) for i in range(10)]
        + [(0.5 + 0.1 * i, 1.0e6 * (1 + i % 5), 5.0e4 - 4.0e3 * i) for i in range(10)],
    ),
]
VARIANT_IDS = [f"{variant}:{inlet}" for variant, inlet, _, _ in VARIANT_STATES]


@pytest.mark.parametrize(
    ("variant", "inlet", "isentropic", "states"), VARIANT_STATES, ids=VARIANT_IDS
)
def test_a46_new_isentropic_variants_jacobian(
    variant: str, inlet: str, isentropic: str, states: list[tuple[float, ...]]
) -> None:
    block = _block(variant, inlet, isentropic)
    assert len(states) == 20
    assert block.input_ids == (
        ("n", "P_I", "P_O") if "sat/" in variant else ("n", "T_I", "P_I", "P_O")
    )
    worst = max(_fd_worst(block, state) for state in states)
    assert worst <= FD_TOL, worst


def _v_s(block: IsentropicEnthalpyBlock, state: tuple[float, ...]) -> tuple[float, Any]:
    t_in = None if len(state) == 3 else state[1]
    solved = block.state(t_in, state[-2], state[-1])
    if solved.sat is None:
        phase = block._phase  # noqa: SLF001
        v = _ok(k.phase_properties(WATER, CONTEXT, solved.temperature, state[-1], phase, ("v",)))
        return v["v"][0], solved
    volumes = [
        _ok(k.phase_properties(WATER, CONTEXT, solved.temperature, state[-1], phase, ("v",)))["v"][
            0
        ]
        for phase in ("LIQUID", "VAPOR")
    ]
    assert solved.beta is not None
    return volumes[0] + solved.beta * (volumes[1] - volumes[0]), solved


@pytest.mark.parametrize(
    ("variant", "inlet", "isentropic", "states"), VARIANT_STATES, ids=VARIANT_IDS
)
def test_new_variants_obey_the_isentropic_identities(
    variant: str, inlet: str, isentropic: str, states: list[tuple[float, ...]]
) -> None:
    """dHs/dP_O = n v_s in one phase or two (dh = v dP at constant s); for a single-phase inlet
    also dHs/dT_I = n T_s c_p,I / T_I and dHs/dP_I = -n T_s (dv/dT)_I (Maxwell)."""
    block = _block(variant, inlet, isentropic)
    for state in states[::4]:
        entries = {j: value for _, j, value in block.jacobian(state)}
        total = state[0]
        v_s, solved = _v_s(block, state)
        by_p_out = total * v_s
        assert abs(entries[len(state) - 1] - by_p_out) <= IDENTITY_TOL * abs(by_p_out)
        if len(state) == 4:
            jets = _ok(k.phase_properties(WATER, CONTEXT, state[1], state[2], inlet, ("cp", "v")))  # type: ignore[arg-type]
            by_t_in = total * solved.temperature * jets["cp"][0] / state[1]
            by_p_in = -total * solved.temperature * jets["v"][1]
            assert abs(entries[1] - by_t_in) <= IDENTITY_TOL * abs(by_t_in)
            assert abs(entries[2] - by_p_in) <= IDENTITY_TOL * abs(by_p_in)


@pytest.mark.parametrize(
    ("variant", "inlet", "isentropic", "states"), VARIANT_STATES, ids=VARIANT_IDS
)
def test_a48_dormant_new_variants(
    variant: str, inlet: str, isentropic: str, states: list[tuple[float, ...]]
) -> None:
    block = _block(variant, inlet, isentropic)
    state = states[3]
    dormant = (0.0, *state[1:])
    assert block.values(dormant) == [0.0]
    (unit,) = block.values((1.0, *state[1:]))
    entries = block.jacobian(dormant)
    assert entries[0] == (0, 0, unit)
    assert all(value == 0.0 for _, j, value in entries if j > 0)


def test_saturated_variants_refuse_a_single_phase_isentropic_state() -> None:
    """beta_s outside [0, 1] is a trial-state DomainError (and the evaluate's refusal)."""
    with pytest.raises(DomainError, match="isentropic_state_two_phase"):
        _block("pure-single/sat", "VAPOR", "SATURATED").values((1.0, 900.0, 1.0e6, 5.0e5))
    with pytest.raises(DomainError, match="isentropic_state_two_phase"):
        # Saturated steam compressed: the isentropic state is superheated, not wet.
        _block("pure-sat/sat", "VAPOR", "SATURATED").values((1.0, 1.0e5, 3.0e5))


def test_variant_constructor_refusals() -> None:
    with pytest.raises(SpecificationError, match="not one of"):
        _block("pure-wet/single", "LIQUID", "LIQUID")
    with pytest.raises(SpecificationError, match="admitted only"):
        _block("additive-vapour", "VAPOR", "VAPOR")


# -- additive-vapour against a closed-form ideal gas ----------------------------------------------

GAS_CONSTANT = 8.31446261815324
T_REF, P_REF = 298.15, 101325.0
CP = {"A": 29.1, "B": 37.4, "C": 75.0}
H_REF = {"A": 0.0, "B": -3.9e5, "C": -1.0e5}


class _IdealGas:
    """Constant-c_p ideal-gas vapour answering s and h at a pure composition e_j only, as
    `wilson-ig-v2` is asked (§4.3): s_j = c_p,j ln(T/T0) - R ln(P/P0), h_j = h0_j + c_p,j (T - T0).
    It claims the Wilson identity because the block admits the premise by identity only."""

    def __init__(self, components: tuple[str, ...], provider_id: str = "wilson-ig-v2") -> None:
        self._components = components
        self.calls = 0
        self._described = SimpleNamespace(
            provider_id=provider_id,
            reference_convention="WILSON-IG-ref-v1",
            components=components,
            domain={"T": (150.0, 2000.0), "P": (1.0e3, 1.0e7)},
        )

    def describe(self) -> Any:
        return self._described

    def evaluate_phase(
        self, request: PropertyRequest, context: EvaluationContext
    ) -> PropertyResult:
        del context
        self.calls += 1
        assert request.phase == "VAPOR"
        assert sorted(request.state.n) == [0.0] * (len(self._components) - 1) + [1.0]
        name = self._components[request.state.n.index(1.0)]
        t, p, cp = request.state.temperature, request.state.pressure, CP[name]
        return PropertyResult(
            status="ok",
            phase_signature="VAPOR",
            values={
                "s": cp * math.log(t / T_REF) - GAS_CONSTANT * math.log(p / P_REF),
                "h": H_REF[name] + cp * (t - T_REF),
            },
            derivatives={"s": {"T": cp / t, "P": -GAS_CONSTANT / p}, "h": {"T": cp, "P": 0.0}},
        )


def _additive(components: tuple[str, ...] = ("A", "B", "C")) -> IsentropicEnthalpyBlock:
    return IsentropicEnthalpyBlock(
        _IdealGas(components),  # type: ignore[arg-type]
        components,
        CONTEXT,
        block_id=isentropic_block_id("U1"),
        variant="additive-vapour",
        inlet_phase="VAPOR",
        isentropic_phase="VAPOR",
    )


ADDITIVE_STATES = [
    (0.2 + 0.1 * i, 0.5 + 0.05 * i, 0.1 * (i % 3), 300.0 + 15.0 * i, 1.0e5, 1.0e5 * (1.5 + 0.3 * i))
    for i in range(10)
] + [
    (1.0 + 0.1 * i, 0.3, 0.2 + 0.1 * i, 700.0 + 20.0 * i, 2.0e6, 2.0e6 / (2.0 + 0.5 * i))
    for i in range(10)
]


def _closed_form(state: Sequence[float]) -> tuple[float, float]:
    *flows, t_in, p_in, p_out = state
    cps = [CP[name] for name in ("A", "B", "C")]
    exponent = GAS_CONSTANT * sum(flows) / sum(n * c for n, c in zip(flows, cps, strict=True))
    t_s = t_in * (p_out / p_in) ** exponent
    hs = sum(
        n * (H_REF[name] + CP[name] * (t_s - T_REF))
        for n, name in zip(flows, ("A", "B", "C"), strict=True)
    )
    return t_s, hs


def test_additive_vapour_equals_the_ideal_gas_isentrope() -> None:
    block = _additive()
    assert block.input_ids == ("n_A", "n_B", "n_C", "T_I", "P_I", "P_O")
    for state in ADDITIVE_STATES:
        _, expected = _closed_form(state)
        (hs,) = block.values(state)
        assert abs(hs - expected) <= 1e-11 * max(abs(expected), 1.0e3), (state, hs, expected)


def test_a46_additive_vapour_jacobian() -> None:
    assert len(ADDITIVE_STATES) == 20
    worst = max(_fd_worst(_additive(), state) for state in ADDITIVE_STATES)
    assert worst <= FD_TOL, worst


def test_a48_additive_vapour_dormant_rule() -> None:
    """n_tot = 0: value 0.0; derivatives at the probe n = (1, 1, 1), T and P entries scaled by 0."""
    block = _additive()
    t_in, p_in, p_out = 350.0, 1.0e5, 4.0e5
    assert block.values((0.0, 0.0, 0.0, t_in, p_in, p_out)) == [0.0]
    dormant = block.jacobian((0.0, 0.0, 0.0, t_in, p_in, p_out))
    probe = block.jacobian((1.0, 1.0, 1.0, t_in, p_in, p_out))
    assert dormant[:3] == probe[:3]
    assert [value for _, _, value in dormant[3:]] == [0.0, 0.0, 0.0]


def test_additive_vapour_is_admitted_by_identity_only() -> None:
    with pytest.raises(SpecificationError, match="admitted only"):
        IsentropicEnthalpyBlock(
            _IdealGas(("A", "B"), provider_id="wilson-ig-v1"),  # type: ignore[arg-type]
            ("A", "B"),
            CONTEXT,
            block_id=isentropic_block_id("U1"),
            variant="additive-vapour",
            inlet_phase="VAPOR",
            isentropic_phase="VAPOR",
        )
    with pytest.raises(SpecificationError, match="vapour on both sides"):
        IsentropicEnthalpyBlock(
            _IdealGas(("A", "B")),  # type: ignore[arg-type]
            ("A", "B"),
            CONTEXT,
            block_id=isentropic_block_id("U1"),
            variant="additive-vapour",
            inlet_phase="LIQUID",
            isentropic_phase="VAPOR",
        )


# -- the machines ---------------------------------------------------------------------------------


def _machine(
    machine: str,
    inlet_form: str,
    outlet_form: str,
    outlet_pressure: float,
    efficiency: float = 0.8,
    provider: Any = WATER,
    **extra: Any,
) -> ThermalMachine:
    return ThermalMachine(
        unit_id="U1",
        machine=machine,  # type: ignore[arg-type]
        provider=provider,
        context=CONTEXT,
        streams={"inlet": ("S1",), "outlet": ("S2",)},
        forms={"S1": inlet_form, "S2": outlet_form},  # type: ignore[dict-item]
        outlet_pressure=outlet_pressure,
        efficiency=efficiency,
        **extra,
    )


def _saturated(
    total: float, pressure: float, beta: float, provider: PropertyProvider = WATER
) -> SaturatedStreamState:
    return SaturatedStreamState(
        (total,), _sat(pressure, provider).temperature, pressure, vapor_fraction=beta
    )


def _run(unit: ThermalMachine, feed: StreamState) -> UnitEvaluation:
    return unit.evaluate({"inlet": (feed,)}, CONTEXT)


def _good(answer: UnitEvaluation) -> UnitEvaluation:
    assert answer.status == "ok", answer.message
    return answer


def _refusal(answer: UnitEvaluation, code: str, status: str = "unsupported") -> None:
    assert answer.status == status, (answer.status, answer.message)
    assert answer.message.split("\n", 1)[0] == code, answer.message


def _stream_values(stream: str, component: str, state: StreamState) -> dict[str, float]:
    values = {
        flow_id(stream, component): state.n[0],
        temperature_id(stream): state.temperature,
        pressure_id(stream): state.pressure,
    }
    if isinstance(state, SaturatedStreamState):
        vapour = state.vapor_fraction * state.n[0]
        values[vapor_id(stream)] = vapour
        values[liquid_id(stream)] = state.n[0] - vapour
    return values


def _check_face(unit: ThermalMachine, feed: StreamState, answer: UnitEvaluation) -> None:
    """Square (rows = the outlet's (n, T, P) and the owned columns), and every row within its
    kind's tolerance at the evaluate's answer: the work and energy rows close, and the evaluate
    and the rows describe the same function."""
    component = unit.component
    spec = assemble(
        label="S11-C3",
        units=[unit],
        wiring={unit.unit_id: Wiring(dict(unit.streams))},
        streams=["S1", "S2"],
        components=(component,),
    )
    if unit.inlet_form == "SATURATED":  # the producer's columns; a unit-only spec allocates them
        spec = dataclasses.replace(
            spec, variable_ids=(*spec.variable_ids, vapor_id("S1"), liquid_id("S1"))
        )
    contribution = unit.contribute(Wiring(dict(unit.streams)), (component,))
    unknowns = {
        flow_id("S2", component),
        temperature_id("S2"),
        pressure_id("S2"),
    } | set(contribution.variable_ids)
    assert len(spec.equations) == len(unknowns), (len(spec.equations), sorted(unknowns))

    values = _stream_values("S1", component, feed)
    values.update(_stream_values("S2", component, answer.outlets["outlet"]))
    values.update(answer.owned)  # type: ignore[attr-defined]
    assert answer.work is not None
    values[work_id(unit.unit_id)] = answer.work
    for row, value in row_values(spec, values).items():
        kind = spec.row_kinds[row]
        assert abs(value) <= KIND_TOLERANCE[kind], (row, value)


#: (machine, inlet form, outlet form, feed, P_spec, eta, extra, expected variant, signature)
MACHINE_CASES: list[tuple[str, str, str, Any, float, float, dict[str, Any], str, str]] = [
    ("pump", "LIQUID", "LIQUID", (300.0, 1.0e5), 3.0e6, 0.75, {}, "pure-single/single", "LIQUID"),
    (
        "pump",
        "SATURATED",
        "LIQUID",
        ("sat", 1.0e4, 0.0),
        3.0e6,
        0.75,
        {},
        "pure-sat/single",
        "LIQUID",
    ),
    ("compressor", "VAPOR", "VAPOR", (400.0, 1.0e5), 3.0e5, 0.8, {}, "pure-single/single", "VAPOR"),
    (
        "compressor",
        "SATURATED",
        "VAPOR",
        ("sat", 1.0e5, 1.0),
        3.0e5,
        0.8,
        {},
        "pure-sat/single",
        "VAPOR",
    ),
    ("turbine", "VAPOR", "VAPOR", (800.0, 2.0e6), 2.0e5, 0.85, {}, "pure-single/single", "VAPOR"),
    (
        "turbine",
        "VAPOR",
        "VAPOR",
        (673.15, 3.0e6),
        1.0e5,
        0.3,
        {"isentropic_phase": "vapor_liquid"},
        "pure-single/sat",
        "VAPOR",
    ),
    (
        "turbine",
        "VAPOR",
        "SATURATED",
        (673.15, 3.0e6),
        1.0e4,
        0.85,
        {},
        "pure-single/sat",
        "TWO_PHASE",
    ),
    (
        "turbine",
        "SATURATED",
        "SATURATED",
        ("sat", 1.0e6, 1.0),
        1.0e4,
        0.85,
        {},
        "pure-sat/sat",
        "TWO_PHASE",
    ),
    (
        "turbine",
        "SATURATED",
        "VAPOR",
        ("sat", 1.0e6, 1.0),
        5.0e5,
        0.1,
        {"isentropic_phase": "vapor_liquid"},
        "pure-sat/sat",
        "VAPOR",
    ),
]


def _feed(spec: Any, total: float = 1.0, provider: PropertyProvider = WATER) -> StreamState:
    if spec[0] == "sat":
        return _saturated(total, spec[1], spec[2], provider)
    return StreamState((total,), spec[0], spec[1])


@pytest.mark.parametrize(
    ("machine", "inlet", "outlet", "feed", "p_out", "eta", "extra", "variant", "signature"),
    MACHINE_CASES,
)
def test_a50_every_machine_form_is_square_and_closes(
    machine: str,
    inlet: str,
    outlet: str,
    feed: Any,
    p_out: float,
    eta: float,
    extra: dict[str, Any],
    variant: str,
    signature: str,
) -> None:
    unit = _machine(machine, inlet, outlet, p_out, eta, **extra)
    assert unit.variant == variant
    assert unit.model_id == f"thermal.{machine}"
    assert unit.dormancy_configuration == outlet
    state = _feed(feed, 1.3)
    answer = _good(_run(unit, state))
    assert answer.phase_signature == signature
    assert answer.duty is None and answer.work is not None
    assert (answer.work < 0.0) if machine == "turbine" else (answer.work > 0.0)
    assert answer.outlets["outlet"].pressure == p_out
    assert {e.equation_id for e in unit.declared_equations()} >= {
        f"{unit.family}-{name}" for name in ("mole", "P", "work", "energy")
    }
    manifest = unit.manifest()
    assert manifest["id"] == f"thermal.{machine}"
    assert manifest["derivatives"][1]["method"] == "implicit"
    _check_face(unit, state, answer)


@pytest.mark.parametrize(
    ("machine", "outlet"),
    [("pump", "LIQUID"), ("compressor", "VAPOR"), ("turbine", "VAPOR"), ("turbine", "SATURATED")],
)
def test_dormant_machine_is_labelled_with_zero_work(machine: str, outlet: str) -> None:
    inlet = "LIQUID" if machine == "pump" else "VAPOR"
    p_out = 1.0e4 if machine == "turbine" else 3.0e6
    feed = StreamState(
        (0.0,), 350.0 if machine == "pump" else 700.0, 1.0e5 if machine != "turbine" else 3.0e6
    )
    answer = _good(_run(_machine(machine, inlet, outlet, p_out), feed))
    assert answer.work == 0.0
    assert answer.phase_signature == "ZERO_FLOW"
    state = answer.outlets["outlet"]
    assert (state.n, state.temperature, state.pressure) == ((0.0,), feed.temperature, p_out)
    if outlet == "SATURATED":
        assert isinstance(state, SaturatedStreamState) and state.vapor_fraction == 0.0
        assert answer.owned == {vapor_id("S2"): 0.0, liquid_id("S2"): 0.0}  # type: ignore[attr-defined]


# -- S11.A50 refusals -----------------------------------------------------------------------------

CONSTRUCTION_REFUSALS: list[tuple[str, str, str, dict[str, Any], str]] = [
    ("pump", "VAPOR", "LIQUID", {}, "specification_unsupported(U1.inlet)"),
    ("pump", "LIQUID", "VAPOR", {}, "specification_unsupported(U1.outlet)"),
    ("pump", "LIQUID", "SATURATED", {}, "specification_unsupported(U1.outlet)"),
    ("compressor", "LIQUID", "VAPOR", {}, "specification_unsupported(U1.inlet)"),
    ("compressor", "VAPOR", "LIQUID", {}, "specification_unsupported(U1.outlet)"),
    ("compressor", "VAPOR", "SATURATED", {}, "specification_unsupported(U1.outlet)"),
    ("turbine", "LIQUID", "VAPOR", {}, "specification_unsupported(U1.inlet)"),
    ("turbine", "VAPOR", "LIQUID", {}, "specification_unsupported(U1.outlet)"),
    (
        "turbine",
        "VAPOR",
        "SATURATED",
        {"isentropic_phase": "vapor"},
        "specification_unsupported(U1.isentropic_phase)",
    ),
    (
        "pump",
        "LIQUID",
        "LIQUID",
        {"isentropic_phase": "vapor"},
        "specification_unsupported(U1.isentropic_phase)",
    ),
    ("pump", "LIQUID", "LIQUID", {"efficiency": 0.0}, "efficiency_outside_interval"),
    ("turbine", "VAPOR", "VAPOR", {"efficiency": 1.1}, "efficiency_outside_interval"),
]


@pytest.mark.parametrize(("machine", "inlet", "outlet", "extra", "code"), CONSTRUCTION_REFUSALS)
def test_a50_construction_refusals(
    machine: str, inlet: str, outlet: str, extra: dict[str, Any], code: str
) -> None:
    with pytest.raises(SpecificationError) as raised:
        _machine(machine, inlet, outlet, 1.0e5, **{"efficiency": 0.8, **extra})
    assert str(raised.value).split("\n", 1)[0] == code


def test_a50_the_wet_outlet_hint() -> None:
    with pytest.raises(SpecificationError, match="a wet outlet has a wetter isentropic state"):
        _machine("turbine", "VAPOR", "SATURATED", 1.0e4, isentropic_phase="vapor")


@pytest.mark.parametrize(
    ("machine", "inlet", "outlet", "extra", "what"),
    [
        ("compressor", "SATURATED", "VAPOR", {}, "inlet"),
        ("compressor", "LIQUID", "VAPOR", {}, "inlet"),
        ("turbine", "SATURATED", "VAPOR", {}, "inlet"),
        ("turbine", "VAPOR", "SATURATED", {}, "outlet"),
        ("turbine", "VAPOR", "VAPOR", {"isentropic_phase": "vapor_liquid"}, "isentropic_phase"),
    ],
)
def test_a_wilson_machine_is_vapour_on_both_ports(
    machine: str, inlet: str, outlet: str, extra: dict[str, Any], what: str
) -> None:
    """§4.4 (L-GP-2): the additive-vapour machine refuses any non-vapour form, with the binder's
    code and hint; the pump stays unadmitted on Wilson."""
    with pytest.raises(SpecificationError) as raised:
        _machine(machine, inlet, outlet, 3.0e5, provider=_IdealGas(("A", "B")), **extra)
    assert str(raised.value) == (
        f"specification_unsupported(U1.{what})\nno γ–φ two-phase PS closure (L-GP-2)"
    )
    with pytest.raises(SpecificationError, match=r"provider_not_admitted\(thermal\.pump\)"):
        _machine("pump", "LIQUID", "LIQUID", 3.0e6, provider=_IdealGas(("A", "B")))
    vapour = _machine(machine, "VAPOR", "VAPOR", 3.0e5, provider=_IdealGas(("A", "B")))
    assert vapour.variant == "additive-vapour"
    assert vapour.isentropic_form == "VAPOR"


EVALUATE_REFUSALS: list[tuple[str, str, str, Any, float, dict[str, Any], str, str]] = [
    ("pump", "LIQUID", "LIQUID", (300.0, 1.0e6), 1.0e5, {}, "pressure_fall(pump)", "out_of_domain"),
    (
        "compressor",
        "VAPOR",
        "VAPOR",
        (400.0, 2.0e5),
        1.0e5,
        {},
        "pressure_fall(compressor)",
        "out_of_domain",
    ),
    (
        "turbine",
        "VAPOR",
        "VAPOR",
        (700.0, 1.0e5),
        2.0e5,
        {},
        "pressure_rise(turbine)",
        "out_of_domain",
    ),
    (
        "pump",
        "SATURATED",
        "LIQUID",
        ("sat", 1.0e4, 0.3),
        3.0e6,
        {},
        "inadmissible_phase(inlet, LIQUID)",
        "unsupported",
    ),
    (
        "compressor",
        "SATURATED",
        "VAPOR",
        ("sat", 1.0e5, 0.0),
        3.0e5,
        {},
        "inadmissible_phase(inlet, VAPOR)",
        "unsupported",
    ),
    (
        "pump",
        "LIQUID",
        "LIQUID",
        (400.0, 1.0e5),
        3.0e6,
        {},
        "inadmissible_phase(inlet, LIQUID)",
        "unsupported",
    ),
    # Saturated steam expanded with a declared vapour isentropic state: water is wet, so it is not.
    (
        "turbine",
        "SATURATED",
        "VAPOR",
        ("sat", 1.0e6, 1.0),
        1.0e5,
        {"isentropic_phase": "vapor"},
        "isentropic_state_two_phase(U1)",
        "unsupported",
    ),
    # A wet isentropic state declared where it is superheated (C3-2).
    (
        "turbine",
        "VAPOR",
        "VAPOR",
        (900.0, 1.0e6),
        5.0e5,
        {"isentropic_phase": "vapor_liquid"},
        "isentropic_state_two_phase(U1)",
        "unsupported",
    ),
    # A53's expansion with a vapour outlet declared: it lands wet.
    (
        "turbine",
        "VAPOR",
        "VAPOR",
        (673.15, 3.0e6),
        1.0e4,
        {"isentropic_phase": "vapor_liquid"},
        "phase_regime_mismatch(S2)",
        "unsupported",
    ),
]


@pytest.mark.parametrize(
    ("machine", "inlet", "outlet", "feed", "p_out", "extra", "code", "status"), EVALUATE_REFUSALS
)
def test_a50_evaluate_refusals(
    machine: str,
    inlet: str,
    outlet: str,
    feed: Any,
    p_out: float,
    extra: dict[str, Any],
    code: str,
    status: str,
) -> None:
    unit = _machine(machine, inlet, outlet, p_out, 0.85, **extra)
    _refusal(_run(unit, _feed(feed)), code, status)


# -- S11.A53-A55 against CoolProp 8.0.0 -----------------------------------------------------------

REL_TOL = 1e-7
T_TOL = 1e-5


def _close(value: float, expected: float, tolerance: float = REL_TOL) -> None:
    assert abs(value - expected) <= tolerance * abs(expected), (value, expected)


def test_a53_turbine() -> None:
    ref = UNITS["A53_turbine"]
    unit = _machine("turbine", "VAPOR", "SATURATED", ref["P_out"], ref["efficiency"])
    feed = StreamState((ref["n"],), ref["inlet"]["T"], ref["inlet"]["P"])
    answer = _good(_run(unit, feed))
    ideal = _ok(
        isentropic_state(
            WATER,
            CONTEXT,
            "pure-single/sat",
            "VAPOR",
            "VAPOR",
            feed.temperature,
            feed.pressure,
            ref["P_out"],
        )
    )
    state = answer.outlets["outlet"]
    assert isinstance(state, SaturatedStreamState)
    assert answer.work is not None
    _close(ideal.beta, ref["isentropic"]["beta"])
    _close(state.vapor_fraction, ref["outlet"]["beta"])
    _close(answer.work, ref["W"])
    assert abs(state.temperature - ref["outlet"]["T"]) <= T_TOL
    # The steam-table brackets of S11.A53.
    assert abs(ideal.beta - 0.8366) <= 5e-4
    assert abs(state.vapor_fraction - 0.9017) <= 5e-4
    assert abs(answer.work / 1000.0 + 15.91) <= 0.02
    _check_face(unit, feed, answer)


def test_a54_pump() -> None:
    ref = UNITS["A54_pump"]
    unit = _machine("pump", "SATURATED", "LIQUID", ref["P_out"], ref["efficiency"])
    feed = _saturated(ref["n"], ref["inlet"]["P"], 0.0)
    assert abs(feed.temperature - ref["inlet"]["T"]) <= T_TOL
    answer = _good(_run(unit, feed))
    assert answer.work is not None
    _close(answer.work, ref["W"])
    assert abs(answer.outlets["outlet"].temperature - ref["outlet"]["T"]) <= T_TOL
    assert abs(answer.work - 72.5) <= 0.3
    _check_face(unit, feed, answer)


def test_a55_compressor_co2() -> None:
    ref = UNITS["A55_compressor"]
    co2 = _coolprop("CO2")
    unit = _machine("compressor", "VAPOR", "VAPOR", ref["P_out"], ref["efficiency"], provider=co2)
    feed = StreamState((ref["n"],), ref["inlet"]["T"], ref["inlet"]["P"])
    answer = _good(_run(unit, feed))
    assert answer.work is not None
    _close(answer.work, ref["W"])
    assert abs(answer.outlets["outlet"].temperature - ref["outlet"]["T"]) <= T_TOL
    _check_face(unit, feed, answer)


def test_a55_dry_fluid_saturated_vapour_is_refused() -> None:
    """n-Pentane (S07 table, tier B; S11C_DECISIONS C3-6): its saturated vapour at 1 bar
    compressed to 3 bar has a wet isentropic state (CoolProp: SATURATED, beta_s = 0.938)."""
    ref = UNITS["A55_dry_fluid"]
    assert ref["isentropic"]["regime"] == "SATURATED"
    pentane = _coolprop("n-Pentane")
    unit = _machine("compressor", "SATURATED", "VAPOR", ref["P_out"], 0.8, provider=pentane)
    answer = _run(unit, _saturated(1.0, ref["inlet"]["P"], 1.0, pentane))
    _refusal(answer, "isentropic_state_two_phase(U1)")
    # The same state on the saturated variant lands where CoolProp's PS flash does.
    wet = _ok(
        isentropic_state(
            pentane,
            CONTEXT,
            "pure-sat/sat",
            "VAPOR",
            "VAPOR",
            None,
            ref["inlet"]["P"],
            ref["P_out"],
        )
    )
    _close(wet.beta, ref["isentropic"]["beta"])
    assert abs(wet.temperature - ref["isentropic"]["T"]) <= T_TOL


@pytest.mark.parametrize(
    "case", [1, 6, 7], ids=["pump-sat", "turbine-single-sat", "turbine-sat-sat"]
)
def test_the_machine_compiles_and_agrees_with_the_reference_rows(case: int) -> None:
    """The backend evaluates the same rows at the causal answer as the reference evaluator, and
    its Jacobian (the blocks' declared derivatives) is answered."""
    machine, inlet, outlet, feed, p_out, eta, extra, _, _ = MACHINE_CASES[case]
    unit = _machine(machine, inlet, outlet, p_out, eta, **extra)
    state = _feed(feed, 1.3)
    answer = _good(_run(unit, state))
    spec = assemble(
        label="S11-C3",
        units=[unit],
        wiring={unit.unit_id: Wiring(dict(unit.streams))},
        streams=["S1", "S2"],
        components=(H2O,),
    )
    if inlet == "SATURATED":
        spec = dataclasses.replace(
            spec, variable_ids=(*spec.variable_ids, vapor_id("S1"), liquid_id("S1"))
        )
    values = _stream_values("S1", H2O, state)
    values.update(_stream_values("S2", H2O, answer.outlets["outlet"]))
    values.update(answer.owned)  # type: ignore[attr-defined]
    assert answer.work is not None
    values[work_id("U1")] = answer.work
    compiled = compile_problem(spec)
    context = EvaluationContext(
        model_version=compiled.metadata.model_version,
        constants_sha256=compiled.metadata.constants_sha256,
    )
    x = np.array([values[name] for name in compiled.metadata.variable_ids])
    result = compiled.residual(x, context)
    assert result.status == "ok", result.message
    assert result.values is not None
    reference = row_values(spec, values)
    for row, value in zip(result.equation_ids, result.values, strict=True):
        assert abs(value - reference[row]) <= 1e-9 * max(1.0, abs(reference[row])), row
    assert compiled.jacobian(x, context).status == "ok"


# -- the additive-vapour (Wilson) machines on wilson-ig-v2's real records (§4.4, C3-4 wired) -----

WILSON = WilsonIdealGasProviderV2(ROOT / "benchmarks" / "s10" / "records.yaml")
WILSON_COMPONENTS = WILSON.describe().components
#: (machine, feed n, T_I, P_I, P_spec, eta): GP-M1's compression and an expansion, both vapour.
WILSON_CASES = [
    ("compressor", (0.4, 0.1, 0.5), 370.0, 40_000.0, 50_000.0, 0.8),
    ("turbine", (0.4, 0.1, 0.5), 375.0, 60_000.0, 45_000.0, 0.85),
]
WILSON_IDS = ["compressor", "turbine"]


def _wilson(machine: str, outlet_pressure: float, efficiency: float) -> ThermalMachine:
    return _machine(machine, "VAPOR", "VAPOR", outlet_pressure, efficiency, provider=WILSON)


def _wilson_values(
    unit: ThermalMachine, feed: StreamState, answer: UnitEvaluation
) -> dict[str, float]:
    values: dict[str, float] = {}
    for stream, state in (("S1", feed), ("S2", answer.outlets["outlet"])):
        for name, flow in zip(WILSON_COMPONENTS, state.n, strict=True):
            values[flow_id(stream, name)] = flow
        values[temperature_id(stream)] = state.temperature
        values[pressure_id(stream)] = state.pressure
    assert answer.work is not None
    values[work_id(unit.unit_id)] = answer.work
    return values


def _wilson_spec(unit: ThermalMachine) -> Any:
    return assemble(
        label="S11-I1b",
        units=[unit],
        wiring={unit.unit_id: Wiring(dict(unit.streams))},
        streams=["S1", "S2"],
        components=WILSON_COMPONENTS,
    )


@pytest.mark.parametrize(
    ("machine", "n", "t_in", "p_in", "p_out", "eta"), WILSON_CASES, ids=WILSON_IDS
)
def test_the_wilson_machine_rows_vanish_at_its_evaluation(
    machine: str, n: tuple[float, ...], t_in: float, p_in: float, p_out: float, eta: float
) -> None:
    """Square (C + 3 rows: the outlet's n, T, P and W), every row within its kind's tolerance at
    the evaluate's answer, and the faces are the syn001 units' VAPOR mixture blocks (§4.3)."""
    unit = _wilson(machine, p_out, eta)
    feed = StreamState(n, t_in, p_in)
    answer = _good(_run(unit, feed))
    assert answer.phase_signature == "VAPOR"
    assert (answer.provider_id, answer.reference_convention) == (
        "wilson-ig-v2",
        "WILSON-IG-ref-v1",
    )
    assert answer.outlets["outlet"].n == n
    assert answer.outlets["outlet"].pressure == p_out
    assert answer.work is not None and (answer.work < 0.0) == (machine == "turbine")
    spec = _wilson_spec(unit)
    contribution = unit.contribute(Wiring(dict(unit.streams)), WILSON_COMPONENTS)
    assert [block.block_id for block in contribution.blocks] == [
        enthalpy_block_id("S1", "VAPOR"),
        enthalpy_block_id("S2", "VAPOR"),
        isentropic_block_id("U1"),
    ]
    family = unit.family
    assert set(spec.row_kinds) == {
        *(f"U1:{family}-mole:{c}" for c in WILSON_COMPONENTS),
        f"U1:{family}-P",
        f"U1:{family}-work",
        f"U1:{family}-energy",
    }
    assert len(spec.equations) == len(WILSON_COMPONENTS) + 3
    for row, value in row_values(spec, _wilson_values(unit, feed, answer)).items():
        assert abs(value) <= KIND_TOLERANCE[spec.row_kinds[row]], (row, value)


@pytest.mark.parametrize(
    ("machine", "n", "t_in", "p_in", "p_out", "eta"), WILSON_CASES, ids=WILSON_IDS
)
def test_a46_the_wilson_machine_jacobian(
    machine: str, n: tuple[float, ...], t_in: float, p_in: float, p_out: float, eta: float
) -> None:
    """A46's convention on the compiled contribution at the evaluated state: each Jacobian entry
    against a central difference of step 1e-6 x_j, judged relative to the larger of |dF_i/dx_j|
    and the row's largest scaled entry max_k |dF_i/dx_k x_k| over |x_j| (the residual itself is
    ~0 at the root, so C1-3's |F_i/x_j| has no scale here)."""
    unit = _wilson(machine, p_out, eta)
    feed = StreamState(n, t_in, p_in)
    answer = _good(_run(unit, feed))
    spec = _wilson_spec(unit)
    compiled = compile_problem(spec)
    context = EvaluationContext(
        model_version=compiled.metadata.model_version,
        constants_sha256=compiled.metadata.constants_sha256,
    )
    values = _wilson_values(unit, feed, answer)
    ids = compiled.metadata.variable_ids
    x = np.array([values[name] for name in ids])
    jac = compiled.jacobian(x, context)
    assert jac.status == "ok"
    dense = np.zeros((len(jac.row_ids), len(jac.col_ids)))
    for column in range(len(jac.col_ids)):
        for at in range(jac.indptr[column], jac.indptr[column + 1]):
            dense[jac.indices[at], column] = jac.data[at]
    assert list(jac.col_ids) == list(ids)
    scaled = np.abs(dense * x)
    worst = 0.0
    for j, value in enumerate(x):
        h = FD_STEP * abs(value)
        up, down = x.copy(), x.copy()
        up[j], down[j] = value + h, value - h
        f_up, f_down = compiled.residual(up, context), compiled.residual(down, context)
        assert f_up.status == "ok" and f_down.status == "ok", ids[j]
        assert f_up.values is not None and f_down.values is not None
        fd = (np.array(f_up.values) - np.array(f_down.values)) / (up[j] - down[j])
        for i in range(len(jac.row_ids)):
            scale = max(abs(dense[i, j]), scaled[i].max() / abs(value))
            worst = max(worst, abs(fd[i] - dense[i, j]) / scale)
    assert worst <= FD_TOL, worst


def test_the_wilson_machine_refusals_carry_the_bound_provider() -> None:
    """The bound, a liquid inlet written as vapour (R-007), and a turbine whose vapour outlet the
    provider judges unstable, each typed and labelled with `wilson-ig-v2` (R-840)."""
    labels = ("wilson-ig-v2", "WILSON-IG-ref-v1")
    compressor = _wilson("compressor", 50_000.0, 0.8)
    bound = _run(compressor, StreamState((0.4, 0.1, 0.5), 370.0, 60_000.0))
    _refusal(bound, "pressure_fall(compressor)", "out_of_domain")
    wet = _run(compressor, StreamState((0.4, 0.1, 0.5), 320.0, 40_000.0))
    _refusal(wet, "inadmissible_phase(inlet, VAPOR)")
    assert (wet.provider_id, wet.reference_convention) == labels
    # C-MW's vapour 3 K above its dew point at 150 kPa, expanded to 90 kPa (dew 358.5 K).
    turbine = _wilson("turbine", 90_000.0, 0.85)
    crossed = _run(turbine, StreamState((0.4, 0.0, 0.6), 375.25, 150_000.0))
    assert crossed.status == "unsupported", crossed.message
    assert crossed.message.split("\n", 1)[0] in {
        "phase_regime_mismatch(S2)",
        "isentropic_state_two_phase(U1)",
    }
    assert (crossed.provider_id, crossed.reference_convention) == labels


def test_the_dormant_wilson_machine_and_its_manifest() -> None:
    unit = _wilson("compressor", 50_000.0, 0.8)
    answer = _good(_run(unit, StreamState((0.0, 0.0, 0.0), 370.0, 40_000.0)))
    assert answer.work == 0.0 and answer.phase_signature == "ZERO_FLOW"
    assert answer.outlets["outlet"] == StreamState((0.0, 0.0, 0.0), 370.0, 50_000.0)
    limitations = unit.manifest()["validity"]["limitations"]
    assert [text for text in limitations if text.startswith("L-GP-2")]
    assert not [
        text
        for text in _machine("compressor", "VAPOR", "VAPOR", 3.0e5).manifest()["validity"][
            "limitations"
        ]
        if text.startswith("L-GP-2")
    ]


def test_a_wilson_isentropic_state_past_the_dew_point_is_refused() -> None:
    """§4.4 step 2 read on Wilson (S11D WO-I1b B): C-MW's vapour 3 K above its dew point at
    150 kPa expanded to 90 kPa has T_s = 337.05 K, below the dew point there (358.5 K); the
    provider judges that vapour UNSTABLE, so the machine refuses before its outlet."""
    turbine = _wilson("turbine", 90_000.0, 0.85)
    answer = _run(turbine, StreamState((0.4, 0.0, 0.6), 375.25, 150_000.0))
    _refusal(answer, "isentropic_state_two_phase(U1)")
    assert (answer.provider_id, answer.reference_convention) == ("wilson-ig-v2", "WILSON-IG-ref-v1")
