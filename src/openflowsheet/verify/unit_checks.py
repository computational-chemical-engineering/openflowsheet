"""The check table's entries for the K02, T05 and T08 models, and `MODEL_CHECKS`: the table keyed
by model id, which also reads `verify.thermal`'s rows (T05 design note §4, register R-046).

Every formula is written out in the operation order `verify.table`'s docstring states, and must
stay so. `verify.table` re-exports `MODEL_CHECKS`."""

from __future__ import annotations

import math
from collections.abc import Iterable, Iterator, Mapping, MutableMapping, Sequence
from typing import Final

from openflowsheet.models import duty_id, flow_id, pressure_id, temperature_id
from openflowsheet.models.revision_flowsheet import InstanceView
from openflowsheet.models.syn001.conversion_reactor import extent_id
from openflowsheet.models.syn001.flash import total_flow_id
from openflowsheet.models.syn001.pump import work_id
from openflowsheet.models.syn001.tp_state import (
    liquid_flow_id,
    liquid_total_id,
    vapor_flow_id,
    vapor_total_id,
)
from openflowsheet.thermo import PropertyRequest, StreamState
from openflowsheet.verify import CheckResult, pr_c1
from openflowsheet.verify import column as column_rows
from openflowsheet.verify.checks import VerifierError
from openflowsheet.verify.table_kit import ModelChecks, Unit

# -- the K02 entries ---------------------------------------------------------------------------


def _component_sum(values: Iterable[float]) -> float:
    """`Σ_c` over one stream's components: Python's `sum`, as K04's legacy builders compute it.

    Not a left-to-right accumulation: on CPython >= 3.12 `sum` of floats is Neumaier-compensated.
    At the SYN-001-shaped start `x⁰` the two differ in the last bit of `Σ_c S3.liq.c`
    (3.7937936767848512 compensated, 3.7937936767848517 accumulated), which is the whole of
    `material_balance.total.S3.L` there (0.0 against -4.44e-16). Using the legacy primitive keeps
    the cross-validation bitwise; ratified by the design lane (register R-048, note §4.3).
    """
    return sum(values)


def _feed_specification(unit: Unit, components: Sequence[str]) -> list[CheckResult]:
    outlet = unit.stream("outlet")
    state = unit.state
    checks = [
        unit.check(
            "specification",
            f"n.{c}",
            unit.n(outlet, c) - unit.pin(flow_id(outlet, c)),
            "molar_flow",
        )
        for c in components
    ]
    checks.append(
        unit.check(
            "specification",
            "T",
            state[temperature_id(outlet)] - unit.pin(temperature_id(outlet)),
            "temperature",
        )
    )
    checks.append(
        unit.check(
            "specification",
            "P",
            state[pressure_id(outlet)] - unit.pin(pressure_id(outlet)),
            "pressure",
        )
    )
    return checks


def _mixer_material(unit: Unit, components: Sequence[str]) -> list[CheckResult]:
    outlet = unit.stream("outlet")
    checks: list[CheckResult] = []
    for c in components:
        inflow = 0.0
        for stream in unit.streams("inlet"):
            inflow += unit.n(stream, c)
        checks.append(unit.check("material_balance", c, inflow - unit.n(outlet, c), "molar_flow"))
    return checks


def _mixer_energy(unit: Unit, components: Sequence[str]) -> list[CheckResult]:
    inflow = 0.0
    for stream in unit.streams("inlet"):
        inflow += unit.enthalpy[stream]
    value = inflow - unit.enthalpy[unit.stream("outlet")]
    reads = (*unit.streams("inlet"), unit.stream("outlet"))
    return [unit.check("energy_balance", "", value, "heat_rate", reads=reads)]


def _heater_material(unit: Unit, components: Sequence[str]) -> list[CheckResult]:
    inlet, outlet = unit.stream("inlet"), unit.stream("outlet")
    checks = [
        unit.check("material_balance", c, unit.n(inlet, c) - unit.n(outlet, c), "molar_flow")
        for c in components
    ]
    return checks + _lifted_outlet_material(unit, outlet, components)


def _lifted_outlet_material(
    unit: Unit, outlet: str, components: Sequence[str]
) -> list[CheckResult]:
    """A heater-style lifted outlet's `lifted_split.<c>` (`n_out − v − l`), `total.V` (`V − Σv`)
    and `total.L` (`L − Σl`): the heater's, the valve's and the reactor's."""
    state = unit.state
    checks = [
        unit.check(
            "material_balance",
            f"lifted_split.{c}",
            unit.n(outlet, c) - state[vapor_flow_id(outlet, c)] - state[liquid_flow_id(outlet, c)],
            "molar_flow",
        )
        for c in components
    ]
    vapor = _component_sum(state[vapor_flow_id(outlet, c)] for c in components)
    liquid = _component_sum(state[liquid_flow_id(outlet, c)] for c in components)
    checks.append(
        unit.check(
            "material_balance", "total.V", state[vapor_total_id(outlet)] - vapor, "molar_flow"
        )
    )
    checks.append(
        unit.check(
            "material_balance", "total.L", state[liquid_total_id(outlet)] - liquid, "molar_flow"
        )
    )
    return checks


def _heater_energy(unit: Unit, components: Sequence[str]) -> list[CheckResult]:
    value = (
        unit.enthalpy[unit.stream("inlet")]
        + unit.state[duty_id(unit.id)]
        - unit.enthalpy[unit.stream("outlet")]
    )
    reads = (unit.stream("inlet"), unit.stream("outlet"))
    return [unit.check("energy_balance", "", value, "heat_rate", reads=reads)]


def _heater_specification(unit: Unit, components: Sequence[str]) -> list[CheckResult]:
    column = temperature_id(unit.stream("outlet"))
    return [unit.check("specification", "T", unit.state[column] - unit.pin(column), "temperature")]


def _flash_material(unit: Unit, components: Sequence[str]) -> list[CheckResult]:
    inlet, vapor, liquid = unit.stream("inlet"), unit.stream("vapor"), unit.stream("liquid")
    checks = [
        unit.check(
            "material_balance",
            c,
            unit.n(inlet, c) - unit.n(vapor, c) - unit.n(liquid, c),
            "molar_flow",
        )
        for c in components
    ]
    for phase, stream in (("vapor", vapor), ("liquid", liquid)):
        total = _component_sum(unit.n(stream, c) for c in components)
        checks.append(
            unit.check(
                "material_balance",
                f"total.{phase}",
                unit.state[total_flow_id(stream)] - total,
                "molar_flow",
            )
        )
    return checks


def _c1_flash_material(unit: Unit, components: Sequence[str]) -> list[CheckResult]:
    """`_flash_material`, then `material_balance.<U>.liquid.<i>` = `n_L,i` for each vapour-only
    component: the verifier's own reading of R-143 (M02 design note §14.2 B15 item 6)."""
    liquid = unit.stream("liquid")
    return _flash_material(unit, components) + [
        unit.check("material_balance", f"liquid.{c}", unit.n(liquid, c), "molar_flow")
        for c in pr_c1.VAPOUR_ONLY
    ]


def _flash_energy(unit: Unit, components: Sequence[str]) -> list[CheckResult]:
    value = (
        unit.enthalpy[unit.stream("inlet")]
        + unit.state[duty_id(unit.id)]
        - unit.enthalpy[unit.stream("vapor")]
        - unit.enthalpy[unit.stream("liquid")]
    )
    reads = (unit.stream("inlet"), unit.stream("vapor"), unit.stream("liquid"))
    return [unit.check("energy_balance", "", value, "heat_rate", reads=reads)]


def _flash_specification(unit: Unit, components: Sequence[str]) -> list[CheckResult]:
    checks: list[CheckResult] = []
    for coordinate, identify, kind in (
        ("temperature", temperature_id, "temperature"),
        ("pressure", pressure_id, "pressure"),
    ):
        for phase in ("vapor", "liquid"):
            column = identify(unit.stream(phase))
            checks.append(
                unit.check(
                    "specification",
                    f"{coordinate}.{phase}",
                    unit.state[column] - unit.pin(column),
                    kind,
                )
            )
    return checks


def _splitter_material(unit: Unit, components: Sequence[str]) -> list[CheckResult]:
    inlet, recycle, purge = unit.stream("inlet"), unit.stream("recycle"), unit.stream("purge")
    return [
        unit.check(
            "material_balance",
            c,
            unit.n(inlet, c) - unit.n(recycle, c) - unit.n(purge, c),
            "molar_flow",
        )
        for c in components
    ]


def _splitter_energy(unit: Unit, components: Sequence[str]) -> list[CheckResult]:
    """`Ḣ(inlet) − Ḣ(recycle) − Ḣ(purge)`, the legacy `flows["S5"] - flows["S6"] - flows["S7"]`
    operation for operation; the only independent check of the splitter's temperature copies
    (ruling round Q-R3)."""
    value = (
        unit.enthalpy[unit.stream("inlet")]
        - unit.enthalpy[unit.stream("recycle")]
        - unit.enthalpy[unit.stream("purge")]
    )
    reads = (unit.stream("inlet"), unit.stream("recycle"), unit.stream("purge"))
    return [unit.check("energy_balance", "", value, "heat_rate", reads=reads)]


def _splitter_specification(unit: Unit, components: Sequence[str]) -> list[CheckResult]:
    inlet, recycle = unit.stream("inlet"), unit.stream("recycle")
    ratio = unit.parameter("split_fraction")
    return [
        unit.check(
            "specification",
            f"ratio.{c}",
            unit.n(recycle, c) - ratio * unit.n(inlet, c),
            "molar_flow",
        )
        for c in components
    ]


# -- the T05 entries (spec §12.2, errata applied; W12) -----------------------------------------
#
# Each formula is written out left to right as §12.2 states it; `ν`, `X`, `s`, `η` and `ΔP` are
# the revision's parameters, `P_spec`, `T_spec` and `Q_spec` its pins. The PH flash's balances are
# the tp_flash's formulas (the same rows of §12.2) and share their functions; the valve's material
# rows are the heater's.


def _pressure_after_drop(unit: Unit, outlet: str, inlet: str) -> float:
    """`P_out − (P_in − ΔP)`."""
    return unit.state[pressure_id(outlet)] - (
        unit.state[pressure_id(inlet)] - unit.parameter("pressure_drop")
    )


def _ph_flash_specification(unit: Unit, components: Sequence[str]) -> list[CheckResult]:
    inlet, vapor, liquid = unit.stream("inlet"), unit.stream("vapor"), unit.stream("liquid")
    duty = duty_id(unit.id)
    state = unit.state
    return [
        unit.check("specification", "duty", state[duty] - unit.pin(duty), "heat_rate"),
        unit.check(
            "specification",
            "temperature",
            state[temperature_id(vapor)] - state[temperature_id(liquid)],
            "temperature",
        ),
        unit.check(
            "specification",
            "pressure.vapor",
            _pressure_after_drop(unit, vapor, inlet),
            "pressure",
        ),
        unit.check(
            "specification",
            "pressure.liquid",
            _pressure_after_drop(unit, liquid, inlet),
            "pressure",
        ),
    ]


def _through_energy(unit: Unit, components: Sequence[str]) -> list[CheckResult]:
    """The valve's `Ḣ(in) − Ḣ(out)`: adiabatic and work-free."""
    value = unit.enthalpy[unit.stream("inlet")] - unit.enthalpy[unit.stream("outlet")]
    reads = (unit.stream("inlet"), unit.stream("outlet"))
    return [unit.check("energy_balance", "", value, "heat_rate", reads=reads)]


def _outlet_pressure_specification(unit: Unit, components: Sequence[str]) -> list[CheckResult]:
    """`P_out − P_spec`: the valve's and the pump's."""
    column = pressure_id(unit.stream("outlet"))
    return [
        unit.check(
            "specification", "outlet_pressure", unit.state[column] - unit.pin(column), "pressure"
        )
    ]


def _valve_bounds(unit: Unit, components: Sequence[str]) -> list[CheckResult]:
    """`P_out − P_in ≤ τ`: a valve does not raise the pressure."""
    value = (
        unit.state[pressure_id(unit.stream("outlet"))]
        - unit.state[pressure_id(unit.stream("inlet"))]
    )
    return [unit.one_sided("direction", value, "pressure")]


def _pump_material(unit: Unit, components: Sequence[str]) -> list[CheckResult]:
    inlet, outlet = unit.stream("inlet"), unit.stream("outlet")
    return [
        unit.check("material_balance", c, unit.n(inlet, c) - unit.n(outlet, c), "molar_flow")
        for c in components
    ]


def _liquid_enthalpy_flow(
    unit: Unit, stream: str, pressure: float, components: Sequence[str]
) -> float:
    """`Ḣ^L(n, T, P)`: the provider's liquid enthalpy at `stream`'s flows and temperature and the
    given pressure — a fresh `evaluate_phase`, never the unit's isothermal block. Zero flow
    carries zero enthalpy and is not evaluated (ADR 0001 D3.1)."""
    if unit.provider is None or unit.context is None:
        raise VerifierError(f"provider_missing({unit.id})")
    carried = StreamState(
        n=tuple(unit.n(stream, c) for c in components),
        temperature=unit.state[temperature_id(stream)],
        pressure=pressure,
    )
    if carried.is_dormant:
        return 0.0
    result = unit.provider.evaluate_phase(
        PropertyRequest(state=carried, phase="LIQUID", properties=("h",)), unit.context
    )
    if result.status != "ok":
        raise VerifierError(
            f"the verifier's own liquid enthalpy of {stream} at {pressure!r} Pa returned "
            f"{result.status}"
        )
    return _component_sum(
        flow * result.values[f"h_{component}"]
        for component, flow in zip(components, carried.n, strict=True)
    )


def _pump_energy(unit: Unit, components: Sequence[str]) -> list[CheckResult]:
    """`Ḣ(in) + W − Ḣ(out)`, then the work relation
    `η W − [Ḣ^L(n_in, T_in, P_out) − Ḣ^L(n_in, T_in, P_in)]` from the provider's liquid enthalpies
    — the check an energy balance alone cannot make (INJ-T4)."""
    inlet, outlet = unit.stream("inlet"), unit.stream("outlet")
    work = unit.state[work_id(unit.id)]
    balance = unit.enthalpy[inlet] + work - unit.enthalpy[outlet]
    raised = _liquid_enthalpy_flow(unit, inlet, unit.state[pressure_id(outlet)], components)
    held = _liquid_enthalpy_flow(unit, inlet, unit.state[pressure_id(inlet)], components)
    relation = unit.parameter("efficiency") * work - (raised - held)
    return [
        unit.check("energy_balance", "", balance, "heat_rate", reads=(inlet, outlet)),
        # Reads no stream enthalpy: its liquid enthalpies are its own fresh evaluations.
        unit.check("energy_balance", "work_relation", relation, "heat_rate", reads=()),
    ]


def _pump_bounds(unit: Unit, components: Sequence[str]) -> list[CheckResult]:
    """`P_in − P_out ≤ τ`: a pump does not lower the pressure."""
    value = (
        unit.state[pressure_id(unit.stream("inlet"))]
        - unit.state[pressure_id(unit.stream("outlet"))]
    )
    return [unit.one_sided("direction", value, "pressure")]


def _reactor_material(unit: Unit, components: Sequence[str]) -> list[CheckResult]:
    """`n_in + ν ξ − n_out` per component, `ν` from the revision — a mole or mass envelope would
    pass a permuted stoichiometry (INJ-T3); then the lifted outlet's rows."""
    inlet, outlet = unit.stream("inlet"), unit.stream("outlet")
    extent = unit.state[extent_id(unit.id)]
    checks = [
        unit.check(
            "material_balance",
            c,
            unit.n(inlet, c) + unit.parameter(f"nu.{c}") * extent - unit.n(outlet, c),
            "molar_flow",
        )
        for c in components
    ]
    return checks + _lifted_outlet_material(unit, outlet, components)


def _c1_reactor_material(unit: Unit, components: Sequence[str]) -> list[CheckResult]:
    """`n_in + ν ξ − n_out` per component, as `_reactor_material` with `ν` the verifier's own
    copy of the C1 reaction (M02 WO-9); the outlet is not lifted."""
    inlet, outlet = unit.stream("inlet"), unit.stream("outlet")
    extent = unit.state[extent_id(unit.id)]
    return [
        unit.check(
            "material_balance",
            c,
            unit.n(inlet, c) + pr_c1.REACTION_NU[c] * extent - unit.n(outlet, c),
            "molar_flow",
        )
        for c in components
    ]


def _reactor_key(unit: Unit) -> str:
    """The key component `k` of the one `conversion.<k>` parameter (the builder allows one)."""
    keys = [name for name in unit.view.parameters if name.startswith("conversion.")]
    if len(keys) != 1:
        raise VerifierError(f"parameter_missing({unit.id}.conversion)")
    return keys[0].removeprefix("conversion.")


def _reactor_specification(unit: Unit, components: Sequence[str]) -> list[CheckResult]:
    """`ξ − X n_in,k/(−ν_k)`; `T_out − T_spec` or `Q − Q_spec`, whichever the revision pins;
    `P_out − (P_in − ΔP)`."""
    inlet, outlet = unit.stream("inlet"), unit.stream("outlet")
    state = unit.state
    key = _reactor_key(unit)
    extent, fraction = state[extent_id(unit.id)], unit.parameter(f"conversion.{key}")
    nu = unit.parameter(f"nu.{key}")
    conversion = extent - fraction * unit.n(inlet, key) / (-nu)
    checks = [unit.check("specification", "conversion", conversion, "molar_flow")]
    temperature, duty = temperature_id(outlet), duty_id(unit.id)
    pinned = unit.pinned(temperature, duty)
    if pinned == temperature:
        checks.append(
            unit.check(
                "specification", "T", state[temperature] - unit.pin(temperature), "temperature"
            )
        )
    elif pinned == duty:
        checks.append(
            unit.check("specification", "duty", state[duty] - unit.pin(duty), "heat_rate")
        )
    else:
        raise VerifierError(f"pin_missing({unit.id}, energy_specification)")
    checks.append(
        unit.check(
            "specification", "pressure", _pressure_after_drop(unit, outlet, inlet), "pressure"
        )
    )
    return checks


def _reactor_energy(unit: Unit, components: Sequence[str]) -> list[CheckResult]:
    """`Ḣ(in) + Q − Ḣ(out)`; its note names ADR 0011 D2 (`Unit.energy_note`)."""
    value = (
        unit.enthalpy[unit.stream("inlet")]
        + unit.state[duty_id(unit.id)]
        - unit.enthalpy[unit.stream("outlet")]
    )
    reads = (unit.stream("inlet"), unit.stream("outlet"))
    return [unit.check("energy_balance", "", value, "heat_rate", reads=reads)]


# -- the T08 entry (build-first §A1.6) ----------------------------------------------------------


def _cstr_key(view: InstanceView) -> str:
    """The key component `k` of the one `damkohler.<k>` parameter (the builder allows one)."""
    keys = [name for name in view.parameters if name.startswith("damkohler.")]
    if len(keys) != 1:
        raise VerifierError(f"parameter_missing({view.unit_id}.damkohler)")
    return keys[0].removeprefix("damkohler.")


def _cstr_rate(view: InstanceView, state: Mapping[str, float]) -> float:
    """`r = Da exp((T_out − T_ref)/T_s) n_out,k`, recomputed in binary64 from the state and the
    revision's parameters — its own code path, not the compiled row (§A1.6), as the pump's work
    relation is. A state whose exponent the double cannot hold is not a state this judges."""
    (outlet,) = view.ports["outlet"]
    key = _cstr_key(view)
    parameters = view.parameters
    exponent = (state[temperature_id(outlet)] - parameters["T_ref"]) / parameters["T_scale"]
    if not exponent <= 700.0:
        raise VerifierError(f"rate_not_finite({view.unit_id}): exponent {exponent!r}")
    return parameters[f"damkohler.{key}"] * math.exp(exponent) * state[flow_id(outlet, key)]


def _cstr_material(unit: Unit, components: Sequence[str]) -> list[CheckResult]:
    """`n_in,c − n_out,c + ν_c r` per component, `ν` from the revision and `r` recomputed."""
    inlet, outlet = unit.stream("inlet"), unit.stream("outlet")
    rate = _cstr_rate(unit.view, unit.state)
    return [
        unit.check(
            "material_balance",
            c,
            unit.n(inlet, c) - unit.n(outlet, c) + unit.parameter(f"nu.{c}") * rate,
            "molar_flow",
        )
        for c in components
    ]


def _cstr_energy(unit: Unit, components: Sequence[str]) -> list[CheckResult]:
    """`Ḣ(in) + Q − Ḣ(out)` from fresh enthalpies (its note names ADR 0011 D2), then the cooling
    relation `Q − F_c c_c (T_c − T_out)`, which reads no enthalpy (the pump's work relation's
    place, T05 §12.2)."""
    outlet = unit.stream("outlet")
    capacity = unit.parameter("coolant_flow") * unit.parameter("coolant_cp")
    relation = unit.state[duty_id(unit.id)] - capacity * (
        unit.parameter("T_coolant") - unit.state[temperature_id(outlet)]
    )
    return [
        *_reactor_energy(unit, components),
        unit.check("energy_balance", "cooling_relation", relation, "heat_rate", reads=()),
    ]


def _separator_material(unit: Unit, components: Sequence[str]) -> list[CheckResult]:
    inlet, top, bottom = unit.stream("inlet"), unit.stream("top"), unit.stream("bottom")
    return [
        unit.check(
            "material_balance",
            c,
            unit.n(inlet, c) - unit.n(top, c) - unit.n(bottom, c),
            "molar_flow",
        )
        for c in components
    ]


def _separator_specification(unit: Unit, components: Sequence[str]) -> list[CheckResult]:
    """`n_top − s n_in` per component, then each outlet's `T` and `P` copied from the inlet."""
    inlet, top, bottom = unit.stream("inlet"), unit.stream("top"), unit.stream("bottom")
    state = unit.state
    checks = [
        unit.check(
            "specification",
            f"split.{c}",
            unit.n(top, c) - unit.parameter(f"split.{c}") * unit.n(inlet, c),
            "molar_flow",
        )
        for c in components
    ]
    for coordinate, identify, kind in (
        ("temperature", temperature_id, "temperature"),
        ("pressure", pressure_id, "pressure"),
    ):
        for port, outlet in (("top", top), ("bottom", bottom)):
            checks.append(
                unit.check(
                    "specification",
                    f"{coordinate}.{port}",
                    state[identify(outlet)] - state[identify(inlet)],
                    kind,
                )
            )
    return checks


def _separator_energy(unit: Unit, components: Sequence[str]) -> list[CheckResult]:
    value = (
        unit.enthalpy[unit.stream("inlet")]
        + unit.state[duty_id(unit.id)]
        - unit.enthalpy[unit.stream("top")]
        - unit.enthalpy[unit.stream("bottom")]
    )
    reads = (unit.stream("inlet"), unit.stream("top"), unit.stream("bottom"))
    return [unit.check("energy_balance", "", value, "heat_rate", reads=reads)]


#: The exchanger's sides, in §12.2's order: `(side, inlet port, outlet port)`.
_SIDES: Final = (("hot", "hot_inlet", "hot_outlet"), ("cold", "cold_inlet", "cold_outlet"))


def _exchanger_material(unit: Unit, components: Sequence[str]) -> list[CheckResult]:
    checks: list[CheckResult] = []
    for side, inlet_port, outlet_port in _SIDES:
        inlet, outlet = unit.stream(inlet_port), unit.stream(outlet_port)
        checks += [
            unit.check(
                "material_balance",
                f"{side}.{c}",
                unit.n(inlet, c) - unit.n(outlet, c),
                "molar_flow",
            )
            for c in components
        ]
    return checks


def _exchanger_energy(unit: Unit, components: Sequence[str]) -> list[CheckResult]:
    """`Ḣ(hi) − Q − Ḣ(ho)`, `Ḣ(ci) + Q − Ḣ(co)`: `Q` is the heat moved from hot to cold."""
    enthalpy, duty = unit.enthalpy, unit.state[duty_id(unit.id)]
    hot = enthalpy[unit.stream("hot_inlet")] - duty - enthalpy[unit.stream("hot_outlet")]
    cold = enthalpy[unit.stream("cold_inlet")] + duty - enthalpy[unit.stream("cold_outlet")]
    return [
        unit.check(
            "energy_balance",
            "hot",
            hot,
            "heat_rate",
            reads=(unit.stream("hot_inlet"), unit.stream("hot_outlet")),
        ),
        unit.check(
            "energy_balance",
            "cold",
            cold,
            "heat_rate",
            reads=(unit.stream("cold_inlet"), unit.stream("cold_outlet")),
        ),
    ]


def _exchanger_specification(unit: Unit, components: Sequence[str]) -> list[CheckResult]:
    """`specification.<U>.<mode>` — the mode the revision pins, spec §10.1's name for it — then
    each side's pressure copy `P_out − P_in`."""
    state = unit.state
    modes = {
        temperature_id(unit.stream("cold_outlet")): ("cold_outlet_temperature", "temperature"),
        temperature_id(unit.stream("hot_outlet")): ("hot_outlet_temperature", "temperature"),
        duty_id(unit.id): ("duty", "heat_rate"),
    }
    pinned = unit.pinned(*modes)
    if pinned is None:
        raise VerifierError(f"pin_missing({unit.id}, specification)")
    mode, kind = modes[pinned]
    checks = [unit.check("specification", mode, state[pinned] - unit.pin(pinned), kind)]
    for side, inlet_port, outlet_port in _SIDES:
        checks.append(
            unit.check(
                "specification",
                f"pressure.{side}",
                state[pressure_id(unit.stream(outlet_port))]
                - state[pressure_id(unit.stream(inlet_port))],
                "pressure",
            )
        )
    return checks


def _exchanger_bounds(unit: Unit, components: Sequence[str]) -> list[CheckResult]:
    """`−Q ≤ τ` (heat flows from hot to cold), `−(T_hi − T_co) ≤ τ` and `−(T_ho − T_ci) ≤ τ` (no
    temperature cross at either end; a pinch, exactly 0, passes).

    T05b spec §9.3: at a dormant side the two terminal differences are not applicable — each
    reads a dormant side's temperature, a label and not a point of a flowing profile — while
    `heat_flow` reads only `Q` and is judged."""
    state = unit.state

    def temperature(port: str) -> float:
        return state[temperature_id(unit.stream(port))]

    return [
        unit.one_sided("heat_flow", -state[duty_id(unit.id)], "heat_rate", judged_at_dormancy=True),
        unit.one_sided(
            "hot_end", -(temperature("hot_inlet") - temperature("cold_outlet")), "temperature"
        ),
        unit.one_sided(
            "cold_end", -(temperature("hot_outlet") - temperature("cold_inlet")), "temperature"
        ),
    ]


#: §4.3's table, keyed by model id: the K02 entries (W1.d) and the T05 ones (W12), with spec
#: §12.2's ids and formulas in §4.3's order and conventions.
_OWN_MODEL_CHECKS: Final[dict[str, ModelChecks]] = {
    "syn001.feed_source": ModelChecks(specification=_feed_specification),
    "syn001.adiabatic_mixer": ModelChecks(
        material=_mixer_material,
        energy=_mixer_energy,
        declared_ports=(("inlet", True), ("outlet", False)),
    ),
    "syn001.tp_heater": ModelChecks(
        material=_heater_material,
        energy=_heater_energy,
        specification=_heater_specification,
        declared_ports=(("inlet", False),),
    ),
    "syn001.tp_flash": ModelChecks(
        material=_flash_material,
        energy=_flash_energy,
        specification=_flash_specification,
        declared_ports=(("inlet", False),),
    ),
    "syn001.stream_splitter": ModelChecks(
        material=_splitter_material,
        energy=_splitter_energy,
        specification=_splitter_specification,
    ),
    "syn001.product_sink": ModelChecks(),
    "syn001.ph_flash": ModelChecks(
        material=_flash_material,
        energy=_flash_energy,
        specification=_ph_flash_specification,
        declared_ports=(("inlet", False),),
    ),
    "syn001.valve": ModelChecks(
        material=_heater_material,
        energy=_through_energy,
        specification=_outlet_pressure_specification,
        bounds=_valve_bounds,
        declared_ports=(("inlet", False),),
    ),
    "syn001.liquid_pump": ModelChecks(
        material=_pump_material,
        energy=_pump_energy,
        specification=_outlet_pressure_specification,
        bounds=_pump_bounds,
        declared_ports=(("inlet", False), ("outlet", False)),
    ),
    "syn001.conversion_reactor": ModelChecks(
        material=_reactor_material,
        energy=_reactor_energy,
        specification=_reactor_specification,
        declared_ports=(("inlet", False),),
    ),
    "syn001.component_separator": ModelChecks(
        material=_separator_material,
        energy=_separator_energy,
        specification=_separator_specification,
        declared_ports=(("inlet", False), ("top", False), ("bottom", False)),
    ),
    "syn001.kinetic_cstr": ModelChecks(
        material=_cstr_material,
        energy=_cstr_energy,
        declared_ports=(("inlet", False), ("outlet", False)),
    ),
    "syn001.heat_exchanger": ModelChecks(
        material=_exchanger_material,
        energy=_exchanger_energy,
        specification=_exchanger_specification,
        bounds=_exchanger_bounds,
        declared_ports=(
            ("hot_inlet", False),
            ("hot_outlet", False),
            ("cold_inlet", False),
            ("cold_outlet", False),
        ),
    ),
    # S11 design §4.8 (WO-B4, registered at I1): the column's rows, from `verify/column.py`.
    "syn001.column": ModelChecks(
        material=column_rows.material,
        energy=column_rows.energy,
        specification=column_rows.specification,
        declared_ports=column_rows.DECLARED_PORTS,
        admissibility=column_rows.admissibility,
    ),
    # M02 design note §14.2 B15 item 6: the C1 units, each rule an existing SYN-001 function.
    "c1.feed_source": ModelChecks(specification=_feed_specification),
    "c1.product_sink": ModelChecks(),
    "c1.stream_splitter": ModelChecks(
        material=_splitter_material,
        energy=_splitter_energy,
        specification=_splitter_specification,
    ),
    "c1.adiabatic_mixer": ModelChecks(
        material=_mixer_material,
        energy=_mixer_energy,
        declared_ports=(("inlet", True), ("outlet", False)),
    ),
    "c1.tp_heater": ModelChecks(
        material=_pump_material,
        energy=_heater_energy,
        specification=_heater_specification,
        declared_ports=(("inlet", False), ("outlet", False)),
    ),
    "c1.tp_flash": ModelChecks(
        material=_c1_flash_material,
        energy=_flash_energy,
        specification=_flash_specification,
        declared_ports=(("inlet", False),),
    ),
    # M02 WO-9 (design note §4.1; build log D47): the C1 reactor's material balance on the C1
    # reaction and SYN-001's reactor energy balance `Ḣ(in) + Q − Ḣ(out)`; both ports declared
    # vapour. No specification entry: X̂ and ΔT̂ are the coupled route's inputs, not the
    # revision's, so the verifier holds no independent value of them; their rows are judged as
    # residual rows, and on the coupled route against the experiment (§4.4). M04's surrogate
    # takes the same entry (spec §8.1): its rows are M02's with (X̂, ΔT̂) its prediction, and its
    # domain is judged by the certificate's `SURROGATE-DOMAIN:<unit>` check (`verify.surrogate`).
    **{
        model: ModelChecks(
            material=_c1_reactor_material,
            energy=_reactor_energy,
            declared_ports=(("inlet", False), ("outlet", False)),
        )
        for model in sorted(pr_c1.REACTOR_MODELS)
    },
}


class _ModelChecksTable(MutableMapping[str, ModelChecks]):
    """`MODEL_CHECKS`: this module's rows, then `verify.thermal.MODEL_CHECKS`'s seven `thermal.*`
    rows (units design §4.8, I1b), imported at the read because that module imports this one.
    A write goes to this module's rows (a test registering one, `monkeypatch.setitem`)."""

    def __init__(self, own: dict[str, ModelChecks]) -> None:
        self._own = own

    @staticmethod
    def _thermal() -> Mapping[str, ModelChecks]:
        from openflowsheet.verify import thermal  # noqa: PLC0415

        return thermal.MODEL_CHECKS

    def __getitem__(self, model: str) -> ModelChecks:
        if model in self._own:
            return self._own[model]
        return self._thermal()[model]

    def __setitem__(self, model: str, entry: ModelChecks) -> None:
        self._own[model] = entry

    def __delitem__(self, model: str) -> None:
        del self._own[model]

    def __iter__(self) -> Iterator[str]:
        yield from self._own
        yield from (model for model in self._thermal() if model not in self._own)

    def __len__(self) -> int:
        return len(self._own.keys() | self._thermal().keys())


#: Model id -> its rows: SYN-001's, C1's, the column's, and the seven `thermal.*` models'.
MODEL_CHECKS: Final[MutableMapping[str, ModelChecks]] = _ModelChecksTable(_OWN_MODEL_CHECKS)
