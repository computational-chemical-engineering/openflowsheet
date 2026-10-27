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

import math
from collections.abc import Sequence
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import yaml
from s07_coolprop_support import require_coolprop
from test_s11_thermal_kernel import FD_TOL, _fd_worst

from openflowsheet.compile.spec import DomainError
from openflowsheet.compiled import EvaluationContext
from openflowsheet.models import (
    SpecificationError,
)
from openflowsheet.models.thermal import kernel as k
from openflowsheet.models.thermal.blocks import (
    IsentropicEnthalpyBlock,
    isentropic_block_id,
)
from openflowsheet.thermo import PropertyProvider, PropertyRequest, PropertyResult
from openflowsheet.thermo.iapws95 import Iapws95Provider

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
