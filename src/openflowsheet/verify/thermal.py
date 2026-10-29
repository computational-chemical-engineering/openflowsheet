"""The verifier's rows for the `thermal.*` family and the saturated pure-fluid stream (S11 units
design §4.8; ADR 0051; WO-C5).

Hooked at I1b into the first pass's `DECLARED_MIXTURE` form: `verify.table.MODEL_CHECKS` reads
this module's `MODEL_CHECKS`, and on a pure-fluid basis `revision_checks` takes a saturated
stream's enthalpy and checks from here. Everything here is the verifier's own computation
from the fresh provider and the state; nothing calls `models.thermal.kernel` (S11.A66).

- **The enthalpy map** (`enthalpy_map`). A single-phase stream keeps A3's rule, `n·h(T, P, phase)`
  in its declared phase (`forms.enthalpy_flow`). A `vapor_liquid` stream on a pure-fluid basis is
  saturated, read from the state's carried split as `V·h^V_sat(P) + L·h^L_sat(P)`, with the fresh
  provider at `(T_sat(P), P)`; every energy check reading it carries `CARRIED_SPLIT_NOTE`.
- **The saturated stream's checks** (`saturated_stream_checks`):
  `phase_admissibility.stream.<S>.saturation` (`T − T_sat(P)` against τ_T),
  `phase_admissibility.stream.<S>.fraction` (`min(V, L) ≥ −τ_flow` and `|V + L − n| ≤ τ_flow`) and
  `independent_split.<S>`, `not_applicable` with reason `temperature_degenerate` (ADR 0012 D7).
  A single-phase stream's admissibility stays `forms.stream_admissibility`.
- **`MODEL_CHECKS`**: each model's material and energy balances, its specifications as configured,
  its bounds, and for the machines `specification.<U>.isentropic_work`, whose isentropic enthalpy
  flow is this module's own: a bisection on T over the declared isentropic side of
  `s^φ(T, P_O) − s*` (60 halvings, or until the bracket is ≤ 4ε·T), or the saturated closed form.
  On an additive-vapour (Wilson) identity it is the same bisection, over the provider's T domain,
  of `Σ_j n_j [s_j(T, P_O) − s_j(T_I, P_I)]`, with `s_j`, `h_j` the fresh provider's VAPOR `s` and
  `h` at the pure composition `e_j`, and `Ḣ_s = Σ_j n_j h_j(T_s, P_O)` (S11.A80).
"""

from __future__ import annotations

import sys
from collections.abc import Mapping, Sequence
from typing import Final

from openflowsheet.compiled import EvaluationContext
from openflowsheet.models import duty_id, pressure_id, temperature_id
from openflowsheet.models.revision_flowsheet import RevisionView
from openflowsheet.models.syn001.pump import work_id
from openflowsheet.models.thermal import ADDITIVE_VAPOUR
from openflowsheet.models.thermal.state import liquid_id, vapor_id
from openflowsheet.thermo import Phase, PropertyProvider, PropertyRequest, StreamState
from openflowsheet.verify import CheckResult, dormant, evaluated, unsupported
from openflowsheet.verify.checks import KIND_REFERENCE, VerifierError, stream_of
from openflowsheet.verify.forms import _critical_temperature, declared_phases, enthalpy_flow
from openflowsheet.verify.table import ModelChecks, Unit

__all__ = [
    "CARRIED_SPLIT_NOTE",
    "MODEL_CHECKS",
    "IsentropicStateError",
    "additive_isentropic_enthalpy",
    "enthalpy_map",
    "isentropic_enthalpy",
    "saturated_enthalpy",
    "saturated_stream_checks",
    "saturated_streams",
]

#: §4.8: appended to every energy check that reads a saturated stream's enthalpy.
CARRIED_SPLIT_NOTE: Final = "; enthalpy of {stream} from its carried split (ADR 0051 D2)"
#: The heater's quality-mode parameter (`application.thermal_binding.OUTLET_VAPOR_FRACTION`).
_OUTLET_VAPOR_FRACTION: Final = "outlet_vapor_fraction"
#: §4.8: the bisection's halvings, and its bracket floor in units of ε·T.
_HALVINGS: Final = 60
_BRACKET_ULPS: Final = 4.0


class IsentropicStateError(Exception):
    """The verifier's own isentropic state could not be computed on the declared side."""


# -- the fresh provider, at unit flow (every property here is intensive for a pure fluid) --------


def _properties(
    provider: PropertyProvider,
    context: EvaluationContext,
    temperature: float,
    pressure: float,
    phase: Phase,
    names: tuple[str, ...],
) -> Mapping[str, float]:
    result = provider.evaluate_phase(
        PropertyRequest(
            state=StreamState(n=(1.0,), temperature=temperature, pressure=pressure),
            phase=phase,
            properties=names,
        ),
        context,
    )
    if result.status != "ok":
        raise IsentropicStateError(
            f"{'/'.join(names)} of {phase} at ({temperature!r} K, {pressure!r} Pa) returned "
            f"{result.status}: {result.message}"
        )
    return result.values


def _t_min(provider: PropertyProvider) -> float:
    return float(provider.describe().domain["T"][0])


def _saturation_temperature(
    provider: PropertyProvider, context: EvaluationContext, pressure: float
) -> float:
    """`T_sat(P)` from the fresh provider (its `Tsat` does not depend on the request's T)."""
    return _properties(provider, context, _t_min(provider), pressure, "LIQUID", ("Tsat",))["Tsat"]


def _saturated_phases(
    provider: PropertyProvider, context: EvaluationContext, pressure: float, names: tuple[str, ...]
) -> tuple[float, Mapping[str, float], Mapping[str, float]]:
    """`T_sat(P)`, then the named properties of the liquid and of the vapour at `(T_sat, P)`."""
    t_sat = _saturation_temperature(provider, context, pressure)
    liquid = _properties(provider, context, t_sat, pressure, "LIQUID", names)
    vapor = _properties(provider, context, t_sat, pressure, "VAPOR", names)
    return t_sat, liquid, vapor


# -- the saturated stream ------------------------------------------------------------------------


def saturated_streams(view: RevisionView) -> tuple[str, ...]:
    """The streams a pure-fluid revision declares `vapor_liquid`: saturated (ADR 0051 D1), in
    allocation order."""
    declared = declared_phases(view)
    return tuple(stream for stream in view.streams if declared[stream] is None)


def _split(state: Mapping[str, float], stream: str) -> tuple[float, float]:
    return state[vapor_id(stream)], state[liquid_id(stream)]


def saturated_enthalpy(
    provider: PropertyProvider,
    state: Mapping[str, float],
    stream: str,
    context: EvaluationContext,
    components: Sequence[str],
) -> float:
    """`V·h^V_sat(P) + L·h^L_sat(P)` from the carried split; 0.0 when dormant (ADR 0001 D3.1)."""
    if stream_of(state, stream, components).is_dormant:
        return 0.0
    vapor_flow, liquid_flow = _split(state, stream)
    try:
        _, liquid, vapor = _saturated_phases(provider, context, state[pressure_id(stream)], ("h",))
    except IsentropicStateError as error:
        raise VerifierError(f"the verifier's own saturated enthalpy of {stream}: {error}") from None
    return vapor_flow * vapor["h"] + liquid_flow * liquid["h"]


def enthalpy_map(
    view: RevisionView,
    state: Mapping[str, float],
    provider: PropertyProvider,
    context: EvaluationContext,
) -> tuple[dict[str, float], dict[str, str]]:
    """Every stream's `Ḣ` on a pure-fluid basis, and the note each saturated one adds to the
    energy checks reading it (`Unit.notes`)."""
    components = view.components
    declared = declared_phases(view)
    enthalpy: dict[str, float] = {}
    notes: dict[str, str] = {}
    for stream in view.streams:
        phase = declared[stream]
        if phase is None:
            enthalpy[stream] = saturated_enthalpy(provider, state, stream, context, components)
            notes[stream] = CARRIED_SPLIT_NOTE.format(stream=stream)
        else:
            enthalpy[stream] = enthalpy_flow(
                provider, stream_of(state, stream, components), phase, context
            )
    return enthalpy, notes


def saturated_stream_checks(
    view: RevisionView,
    state: Mapping[str, float],
    provider: PropertyProvider,
    context: EvaluationContext,
    tolerances: Mapping[str, float],
    note: str,
) -> list[CheckResult]:
    """`.saturation`, `.fraction` and `independent_split.<S>` for each saturated stream, in
    allocation order (§4.8). `.saturation` is `not_applicable` at zero flow, as a single-phase
    stream's admissibility is; `.fraction` reads no property and is judged at every flow, so a
    dormant stream's split `V = −L ≠ 0` fails it (§4.9)."""
    checks: list[CheckResult] = []
    for stream in saturated_streams(view):
        base = f"phase_admissibility.stream.{stream}"
        carried = stream_of(state, stream, view.components)
        if carried.is_dormant:
            checks.append(
                dormant(id=f"{base}.saturation", category="phase_admissibility", subject=stream)
            )
        else:
            try:
                t_sat = _saturation_temperature(provider, context, carried.pressure)
            except IsentropicStateError as error:
                checks.append(
                    unsupported(
                        id=f"{base}.saturation",
                        category="phase_admissibility",
                        subject=stream,
                        reason=f"saturation_refused: {error}",
                    )
                )
            else:
                checks.append(
                    evaluated(
                        id=f"{base}.saturation",
                        category="phase_admissibility",
                        subject=stream,
                        value=carried.temperature - t_sat,
                        tolerance=tolerances["temperature"],
                        reference=KIND_REFERENCE["temperature"],
                        independence_qualification=note,
                    )
                )
        vapor_flow, liquid_flow = _split(state, stream)
        fraction = max(
            0.0, -vapor_flow, -liquid_flow, abs(vapor_flow + liquid_flow - carried.total_flow)
        )
        checks.append(
            evaluated(
                id=f"{base}.fraction",
                category="phase_admissibility",
                subject=stream,
                value=fraction,
                tolerance=tolerances["molar_flow"],
                reference=KIND_REFERENCE["molar_flow"],
            )
        )
        checks.append(
            dormant(
                id=f"independent_split.{stream}",
                category="independent_split",
                subject=stream,
                reason="temperature_degenerate",
            )
        )
    return checks


# -- the machines' own isentropic state ----------------------------------------------------------


def _side_bracket(
    provider: PropertyProvider, context: EvaluationContext, pressure: float, side: Phase
) -> tuple[float, float]:
    """The declared side's temperature interval at `pressure`: below or above `T_sat(P)`, or
    `T_c` where the provider has no saturation there (supercritical labels follow `T_c`, §4.1)."""
    described = provider.describe()
    t_min, t_max = (float(bound) for bound in described.domain["T"])
    try:
        boundary = _saturation_temperature(provider, context, pressure)
    except IsentropicStateError:
        (component,) = described.components
        boundary = _critical_temperature(component, described.provider_id)
    return (t_min, boundary) if side == "LIQUID" else (boundary, t_max)


def isentropic_enthalpy(
    provider: PropertyProvider,
    context: EvaluationContext,
    entropy: float,
    pressure: float,
    side: Phase | None,
) -> float:
    """`h_s` at `(s*, P_O)` on the declared isentropic side, `None` for the saturated side.

    A single-phase side is solved by bisection on T of `s^φ(T, P_O) − s*` over the side's
    interval (s rises with T); a root at an end of the interval is not on the side. The
    saturated side is the closed form `h^L + β_s (h^V − h^L)`, `β_s = (s* − s^L)/(s^V − s^L)`,
    which must lie in [0, 1]. Raises `IsentropicStateError`."""
    if side is None:
        _, liquid, vapor = _saturated_phases(provider, context, pressure, ("h", "s"))
        beta = (entropy - liquid["s"]) / (vapor["s"] - liquid["s"])
        if not 0.0 <= beta <= 1.0:
            raise IsentropicStateError(
                f"the isentropic state at {pressure!r} Pa has beta_s {beta!r}"
            )
        return liquid["h"] + beta * (vapor["h"] - liquid["h"])
    low, high = _side_bracket(provider, context, pressure, side)
    lower, upper = low, high
    for _ in range(_HALVINGS):
        if upper - lower <= _BRACKET_ULPS * sys.float_info.epsilon * upper:
            break
        middle = 0.5 * (lower + upper)
        if _properties(provider, context, middle, pressure, side, ("s",))["s"] < entropy:
            lower = middle
        else:
            upper = middle
    if lower == low or upper == high:
        raise IsentropicStateError(
            f"the isentropic state at {pressure!r} Pa is not {side} (its root is at an end of "
            f"[{low!r}, {high!r}] K)"
        )
    temperature = 0.5 * (lower + upper)
    return _properties(provider, context, temperature, pressure, side, ("h",))["h"]


def _vapour_at_pure(
    provider: PropertyProvider,
    context: EvaluationContext,
    flows: Sequence[float],
    temperature: float,
    pressure: float,
    name: str,
) -> list[float]:
    """`n_j` times `name` of the VAPOR at the pure composition `e_j`, for each flowing component
    (`n_j != 0`); a zero flow adds nothing and is not asked."""
    weighted: list[float] = []
    for j, flow in enumerate(flows):
        if flow == 0.0:
            continue
        result = provider.evaluate_phase(
            PropertyRequest(
                state=StreamState(
                    n=tuple(1.0 if k == j else 0.0 for k in range(len(flows))),
                    temperature=temperature,
                    pressure=pressure,
                ),
                phase="VAPOR",
                properties=(name,),
            ),
            context,
        )
        if result.status != "ok":
            raise IsentropicStateError(
                f"{name} of VAPOR at e_{j} ({temperature!r} K, {pressure!r} Pa) returned "
                f"{result.status}: {result.message}"
            )
        weighted.append(flow * result.values[name])
    return weighted


def additive_isentropic_enthalpy(
    provider: PropertyProvider,
    context: EvaluationContext,
    flows: Sequence[float],
    inlet_temperature: float,
    inlet_pressure: float,
    outlet_pressure: float,
) -> float:
    """`Ḣ_s = Σ_j n_j h_j(T_s, P_O)` of an additive-vapour (Wilson) machine, the verifier's own.

    T_s by bisection on the provider's T domain of `Σ_j n_j [s_j(T, P_O) − s_j(T_I, P_I)]` (it
    rises with T), 60 halvings or until the bracket is ≤ 4ε·T, as `isentropic_enthalpy`; a root
    at an end of the domain is not inside it. Raises `IsentropicStateError`."""
    target = sum(_vapour_at_pure(provider, context, flows, inlet_temperature, inlet_pressure, "s"))
    low, high = (float(bound) for bound in provider.describe().domain["T"])
    lower, upper = low, high
    for _ in range(_HALVINGS):
        if upper - lower <= _BRACKET_ULPS * sys.float_info.epsilon * upper:
            break
        middle = 0.5 * (lower + upper)
        entropy = sum(_vapour_at_pure(provider, context, flows, middle, outlet_pressure, "s"))
        if entropy < target:
            lower = middle
        else:
            upper = middle
    if lower == low or upper == high:
        raise IsentropicStateError(
            f"the additive-vapour isentropic state at {outlet_pressure!r} Pa is outside the "
            f"domain (its root is at an end of [{low!r}, {high!r}] K)"
        )
    temperature = 0.5 * (lower + upper)
    return sum(_vapour_at_pure(provider, context, flows, temperature, outlet_pressure, "h"))


def _inlet_entropy(unit: Unit, inlet: str, phase: Phase | None) -> float:
    """`s*`: the inlet's molar entropy in its declared phase, or from its carried split."""
    provider, context = _provider(unit)
    pressure = unit.state[pressure_id(inlet)]
    if phase is not None:
        return _properties(
            provider, context, unit.state[temperature_id(inlet)], pressure, phase, ("s",)
        )["s"]
    vapor_flow, liquid_flow = _split(unit.state, inlet)
    _, liquid, vapor = _saturated_phases(provider, context, pressure, ("s",))
    return (vapor_flow * vapor["s"] + liquid_flow * liquid["s"]) / (vapor_flow + liquid_flow)


def _provider(unit: Unit) -> tuple[PropertyProvider, EvaluationContext]:
    if unit.provider is None or unit.context is None:
        raise VerifierError(f"provider_missing({unit.id})")
    return unit.provider, unit.context


# -- the model rows ------------------------------------------------------------------------------


def _total(unit: Unit, stream: str, components: Sequence[str]) -> float:
    return sum(unit.n(stream, c) for c in components)


def _through_material(unit: Unit, components: Sequence[str]) -> list[CheckResult]:
    """`n_I,c − n_O,c`: the heater's, the valve's and the machines'."""
    inlet, outlet = unit.stream("inlet"), unit.stream("outlet")
    return [
        unit.check("material_balance", c, unit.n(inlet, c) - unit.n(outlet, c), "molar_flow")
        for c in components
    ]


def _duty_energy(unit: Unit, components: Sequence[str]) -> list[CheckResult]:
    """The heater's `Q + Ḣ_I − Ḣ_O`."""
    inlet, outlet = unit.stream("inlet"), unit.stream("outlet")
    value = unit.enthalpy[inlet] + unit.state[duty_id(unit.id)] - unit.enthalpy[outlet]
    return [unit.check("energy_balance", "", value, "heat_rate", reads=(inlet, outlet))]


def _pressure_after_drop(unit: Unit, outlet: str, inlet: str) -> float:
    """`P_O − (P_I − ΔP)`, ΔP the parameter `pressure_drop` (the heater's defaults to 0)."""
    drop = unit.view.parameters.get("pressure_drop", 0.0)
    return unit.state[pressure_id(outlet)] - (unit.state[pressure_id(inlet)] - drop)


def _heater_specification(unit: Unit, components: Sequence[str]) -> list[CheckResult]:
    """The configured one of `T`, `duty`, `vapor_fraction` (`V_O − β n_O`), then `P`."""
    inlet, outlet = unit.stream("inlet"), unit.stream("outlet")
    state = unit.state
    temperature, duty = temperature_id(outlet), duty_id(unit.id)
    pinned = unit.pinned(temperature, duty)
    if pinned == temperature:
        check = unit.check(
            "specification", "T", state[temperature] - unit.pin(temperature), "temperature"
        )
    elif pinned == duty:
        check = unit.check("specification", "duty", state[duty] - unit.pin(duty), "heat_rate")
    else:
        beta = unit.parameter(_OUTLET_VAPOR_FRACTION)
        value = state[vapor_id(outlet)] - beta * _total(unit, outlet, components)
        check = unit.check("specification", "vapor_fraction", value, "molar_flow")
    return [
        check,
        unit.check("specification", "P", _pressure_after_drop(unit, outlet, inlet), "pressure"),
    ]


def _through_energy(unit: Unit, components: Sequence[str]) -> list[CheckResult]:
    """The valve's `Ḣ_I − Ḣ_O`."""
    inlet, outlet = unit.stream("inlet"), unit.stream("outlet")
    value = unit.enthalpy[inlet] - unit.enthalpy[outlet]
    return [unit.check("energy_balance", "", value, "heat_rate", reads=(inlet, outlet))]


def _outlet_pressure_specification(unit: Unit, components: Sequence[str]) -> list[CheckResult]:
    """`P_O − P_spec`: the valve's and the machines'."""
    column = pressure_id(unit.stream("outlet"))
    return [unit.check("specification", "P", unit.state[column] - unit.pin(column), "pressure")]


def _pressure_fall(unit: Unit, components: Sequence[str]) -> list[CheckResult]:
    """`P_O − P_I ≤ τ`: the valve and the turbine do not raise the pressure."""
    value = (
        unit.state[pressure_id(unit.stream("outlet"))]
        - unit.state[pressure_id(unit.stream("inlet"))]
    )
    return [unit.one_sided("direction", value, "pressure")]


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
    outlet = unit.stream("outlet")
    reads = (*unit.streams("inlet"), outlet)
    return [
        unit.check("energy_balance", "", inflow - unit.enthalpy[outlet], "heat_rate", reads=reads)
    ]


def _mixer_specification(unit: Unit, components: Sequence[str]) -> list[CheckResult]:
    """`P.<k>`: `P_k − P_O` for every inlet k (`TM-pressure:<k>`)."""
    outlet = pressure_id(unit.stream("outlet"))
    return [
        unit.check(
            "specification",
            f"P.{index}",
            unit.state[pressure_id(stream)] - unit.state[outlet],
            "pressure",
        )
        for index, stream in enumerate(unit.streams("inlet"))
    ]


def _flash_material(unit: Unit, components: Sequence[str]) -> list[CheckResult]:
    inlet, vapor, liquid = unit.stream("inlet"), unit.stream("vapor"), unit.stream("liquid")
    return [
        unit.check(
            "material_balance",
            c,
            unit.n(inlet, c) - unit.n(vapor, c) - unit.n(liquid, c),
            "molar_flow",
        )
        for c in components
    ]


def _flash_energy(unit: Unit, components: Sequence[str]) -> list[CheckResult]:
    inlet, vapor, liquid = unit.stream("inlet"), unit.stream("vapor"), unit.stream("liquid")
    value = (
        unit.state[duty_id(unit.id)]
        + unit.enthalpy[inlet]
        - unit.enthalpy[vapor]
        - unit.enthalpy[liquid]
    )
    return [unit.check("energy_balance", "", value, "heat_rate", reads=(inlet, vapor, liquid))]


def _flash_specification(unit: Unit, components: Sequence[str]) -> list[CheckResult]:
    """`duty`, `P.vapor`, `P.liquid`, and the products' fixed splits: the vapour product carries
    no liquid and the liquid product no vapour (`sat-fix`)."""
    inlet, vapor, liquid = unit.stream("inlet"), unit.stream("vapor"), unit.stream("liquid")
    duty = duty_id(unit.id)
    state = unit.state
    return [
        unit.check("specification", "duty", state[duty] - unit.pin(duty), "heat_rate"),
        unit.check(
            "specification", "P.vapor", _pressure_after_drop(unit, vapor, inlet), "pressure"
        ),
        unit.check(
            "specification", "P.liquid", _pressure_after_drop(unit, liquid, inlet), "pressure"
        ),
        unit.check("specification", "vapor_fraction.vapor", state[liquid_id(vapor)], "molar_flow"),
        unit.check("specification", "vapor_fraction.liquid", state[vapor_id(liquid)], "molar_flow"),
    ]


#: Each machine's isentropic side by its outlet's declared phase: the pump's is liquid and the
#: compressor's vapour; the turbine's is its outlet's form (S11C build decision C4-3).
_ISENTROPIC_SIDE: Final[Mapping[str, Phase | None]] = {
    "thermal.pump": "LIQUID",
    "thermal.compressor": "VAPOR",
}
_EXPANDS: Final = "thermal.turbine"


def _machine_energy(unit: Unit, components: Sequence[str]) -> list[CheckResult]:
    """`W + Ḣ_I − Ḣ_O`."""
    inlet, outlet = unit.stream("inlet"), unit.stream("outlet")
    value = unit.state[work_id(unit.id)] + unit.enthalpy[inlet] - unit.enthalpy[outlet]
    return [unit.check("energy_balance", "", value, "heat_rate", reads=(inlet, outlet))]


def _machine_specification(unit: Unit, components: Sequence[str]) -> list[CheckResult]:
    """`P`, then `isentropic_work`: `η W − (Ḣ_s − Ḣ_I)` (pump, compressor) or
    `W − η (Ḣ_s − Ḣ_I)` (turbine), Ḣ_s this module's own (§4.8, S11.A66)."""
    checks = _outlet_pressure_specification(unit, components)
    identifier = f"specification.{unit.id}.isentropic_work"
    inlet, outlet = unit.stream("inlet"), unit.stream("outlet")
    carried = stream_of(unit.state, inlet, components)
    if carried.is_dormant:
        return [*checks, dormant(id=identifier, category="specification", subject=unit.id)]
    model = unit.view.model_id
    side = _ISENTROPIC_SIDE.get(model, unit.view.phases.get("outlet"))
    provider, context = _provider(unit)
    described = provider.describe()
    pressure = unit.state[pressure_id(outlet)]
    try:
        if (described.provider_id, described.reference_convention) in ADDITIVE_VAPOUR:
            isentropic = additive_isentropic_enthalpy(
                provider, context, carried.n, carried.temperature, carried.pressure, pressure
            )
        else:
            entropy = _inlet_entropy(unit, inlet, unit.view.phases.get("inlet"))
            isentropic = carried.total_flow * isentropic_enthalpy(
                provider, context, entropy, pressure, side
            )
    except IsentropicStateError as error:
        return [
            *checks,
            unsupported(
                id=identifier,
                category="specification",
                subject=unit.id,
                reason=f"isentropic_state_refused: {error}",
            ),
        ]
    rise = isentropic - unit.enthalpy[inlet]
    work = unit.state[work_id(unit.id)]
    efficiency = unit.parameter("efficiency")
    value = work - efficiency * rise if model == _EXPANDS else efficiency * work - rise
    return [*checks, unit.check("specification", "isentropic_work", value, "heat_rate")]


def _machine_bounds(unit: Unit, components: Sequence[str]) -> list[CheckResult]:
    """The pressure direction and the sign of W (the pump and compressor raise P and take work,
    the turbine lowers P and gives it), and `0 < η ≤ 1`, judged exactly (a parameter)."""
    inlet = unit.state[pressure_id(unit.stream("inlet"))]
    outlet = unit.state[pressure_id(unit.stream("outlet"))]
    work = unit.state[work_id(unit.id)]
    expands = unit.view.model_id == _EXPANDS
    efficiency = unit.parameter("efficiency")
    outside = 0.0 if 0.0 < efficiency <= 1.0 else (1.0 - efficiency if efficiency > 1.0 else 1.0)
    return [
        unit.one_sided("direction", outlet - inlet if expands else inlet - outlet, "pressure"),
        unit.one_sided("work_sign", work if expands else -work, "heat_rate"),
        evaluated(
            id=f"bounds_and_domain.{unit.id}.efficiency",
            category="bounds_and_domain",
            subject=unit.id,
            value=outside,
            tolerance=0.0,
        ),
    ]


#: §4.8's rows for the seven models, merged into `verify.table.MODEL_CHECKS` at I1b.
MODEL_CHECKS: Final[Mapping[str, ModelChecks]] = {
    "thermal.heater": ModelChecks(
        material=_through_material,
        energy=_duty_energy,
        specification=_heater_specification,
    ),
    "thermal.valve": ModelChecks(
        material=_through_material,
        energy=_through_energy,
        specification=_outlet_pressure_specification,
        bounds=_pressure_fall,
    ),
    "thermal.mixer": ModelChecks(
        material=_mixer_material,
        energy=_mixer_energy,
        specification=_mixer_specification,
    ),
    "thermal.flash": ModelChecks(
        material=_flash_material,
        energy=_flash_energy,
        specification=_flash_specification,
    ),
    **{
        model: ModelChecks(
            material=_through_material,
            energy=_machine_energy,
            specification=_machine_specification,
            bounds=_machine_bounds,
        )
        for model in ("thermal.pump", "thermal.compressor", "thermal.turbine")
    },
}
