"""The verifier's check table for revision-built flowsheets. T05 design note §4 (register R-046).

SYN-001 keeps its legacy check set (`checks.material_checks` and its siblings), ids and code
unchanged; a flowsheet built from a revision is judged by this table instead, keyed by model id.
The table reads **only** the state, the revision (through `parse_revision`'s view: ids, pins and
parameters — the declaration's inputs) and a fresh provider. It shares no row builder, causal
evaluator, kernel or cache with the solver (R-016): a balance here is a plain sum over stream
flows, an enthalpy a fresh flash of the stream's own `(n, T, P)` (`checks.enthalpy_flow`), and a
phase property a fresh `evaluate_phase`.

**Why a second set and not a rewrite of the first** (D4): every legacy id, order and value stays
protected by construction. The two are held together by a bitwise cross-validation on the
SYN-001-shaped revision (`tests/test_t05_w1d_verifier.py`): each legacy value equals its general
counterpart to the bit, at the root and at a non-root. That is why every formula below is written
out in the operation order §4.3 states — left to right, sums over ports, streams and instances
accumulated from `0.0` in declaration order — and must stay so. A sum over one stream's
components is `_component_sum`, Python's `sum`, because that is what the legacy builders call
(see its docstring).

**Order** is category-major, as the legacy engine's: material, energy, specification, bounds,
then admissibility and the independent split. Within a category: instances in declaration order,
each model's items in its entry's order, components in component order; then the flowsheet rows.
A model id without an entry yields one `unsupported` check and caps the verdict at `UNVERIFIED`.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from types import ModuleType
from typing import TYPE_CHECKING, Any, Final

from openflowsheet.compiled import EvaluationContext
from openflowsheet.models import duty_id, flow_id, pressure_id, temperature_id
from openflowsheet.models.revision_flowsheet import InstanceView, RevisionView
from openflowsheet.models.syn001.conversion_reactor import extent_id
from openflowsheet.models.syn001.pump import work_id
from openflowsheet.thermo import (
    FlashRequest,
    Phase,
    PropertyProvider,
    PropertyRequest,
    StreamState,
)
from openflowsheet.verify import (
    CheckResult,
    dormant,
    evaluated,
    forms,
    pr_c1,
    unsupported,
)
from openflowsheet.verify import column as column_rows
from openflowsheet.verify.checks import (
    COMPONENTS,
    KIND_REFERENCE,
    VerifierError,
    _fractions,
    _one_sided,
    bounds_checks,
    closure_check,
    enthalpy_flow,
    k_values,
    qualification,
    routing_tolerances,
    stream_of,
)
from openflowsheet.verify.saturation import (
    SaturationError,
    band_distance,
    band_ends,
    is_temperature_degenerate,
    split_route,
)
from openflowsheet.verify.table_kit import DECLARED_ENTHALPY_NOTE as DECLARED_ENTHALPY_NOTE
from openflowsheet.verify.table_kit import REACTION_DATUM_NOTE as REACTION_DATUM_NOTE
from openflowsheet.verify.table_kit import SPLIT_ENTHALPY_NOTE as SPLIT_ENTHALPY_NOTE
from openflowsheet.verify.table_kit import UNRESOLVED_ENTHALPY_NOTE as UNRESOLVED_ENTHALPY_NOTE
from openflowsheet.verify.table_kit import ModelChecks as ModelChecks
from openflowsheet.verify.table_kit import Rule as Rule
from openflowsheet.verify.table_kit import Unit as Unit
from openflowsheet.verify.table_kit import _unlifted_read
from openflowsheet.verify.table_kit import blocked_check as blocked_check
from openflowsheet.verify.table_kit import stream_notes as stream_notes
from openflowsheet.verify.unit_checks import MODEL_CHECKS as MODEL_CHECKS
from openflowsheet.verify.unit_checks import _c1_flash_material as _c1_flash_material
from openflowsheet.verify.unit_checks import _c1_reactor_material as _c1_reactor_material
from openflowsheet.verify.unit_checks import _cstr_rate
from openflowsheet.verify.unit_checks import _feed_specification as _feed_specification
from openflowsheet.verify.unit_checks import _flash_energy as _flash_energy
from openflowsheet.verify.unit_checks import _flash_specification as _flash_specification
from openflowsheet.verify.unit_checks import _heater_energy as _heater_energy
from openflowsheet.verify.unit_checks import _heater_specification as _heater_specification
from openflowsheet.verify.unit_checks import _mixer_energy as _mixer_energy
from openflowsheet.verify.unit_checks import _mixer_material as _mixer_material
from openflowsheet.verify.unit_checks import _pump_material as _pump_material
from openflowsheet.verify.unit_checks import _reactor_energy as _reactor_energy
from openflowsheet.verify.unit_checks import _splitter_energy as _splitter_energy
from openflowsheet.verify.unit_checks import _splitter_material as _splitter_material
from openflowsheet.verify.unit_checks import _splitter_specification as _splitter_specification

if TYPE_CHECKING:
    from openflowsheet.orchestrator.region import LiftedSplit

__all__ = [
    "DECLARED_ENTHALPY_NOTE",
    "MODEL_CHECKS",
    "REACTION_DATUM_NOTE",
    "SPLIT_ENTHALPY_NOTE",
    "UNRESOLVED_ENTHALPY_NOTE",
    "Degeneracy",
    "ModelChecks",
    "Unit",
    "degeneracy",
    "revision_checks",
    "revision_phase_branch",
]


# §4.3's flowsheet rows name their terms by model id, so the envelope is the same function
# whether or not a model's own entry is in the table yet.
#: Feeds are the outlet streams of these instances.
FEED_MODELS: Final = frozenset({"syn001.feed_source", "c1.feed_source"})
#: Products are the inlet streams of these instances.
PRODUCT_MODELS: Final = frozenset({"syn001.product_sink", "c1.product_sink"})
#: `Q_ext`: the external duty `<U>.Q` — never the exchanger's internal `Q`.
EXTERNAL_DUTY_MODELS: Final = (
    "syn001.tp_heater",
    "syn001.tp_flash",
    "syn001.ph_flash",
    "syn001.conversion_reactor",
    "syn001.component_separator",
    "syn001.kinetic_cstr",
    "c1.tp_heater",
    "c1.tp_flash",
    # M02 WO-9: the C1 reactor's duty `<U>.Q`, positive into the unit (design note §4.1).
    "c1.reactor",
    "c1.reactor_standin",
    # M04 WO-7: the surrogate's duty `<U>.Q`, M02's row (spec §3.2).
    "c1.reactor_surrogate",
    # S11 units design §4.4 (I1b): the thermal heater's and flash's duty `<U>.Q`.
    "thermal.heater",
    "thermal.flash",
)
#: S11 design §4.8: a staged unit's duties are its own (`verify.column.duty`: each end's `Q_j` at
#: the state, then the fixed `Q_j*`), not one `<U>.Q`.
STAGED_DUTY_MODELS: Final = frozenset({"syn001.column"})
#: `W`: the shaft work `<U>.W`.
WORK_MODELS: Final = frozenset(
    # S11 units design §4.4 (I1b): the three thermal machines' `<U>.W`.
    {"syn001.liquid_pump", "thermal.pump", "thermal.compressor", "thermal.turbine"}
)
#: `ν_c ξ` on the material envelope; ADR 0011 D2's note on the energy balances. A conversion
#: reactor's `ξ` is its extent column; a kinetic CSTR's is its rate `r`, which it does not own and
#: the table recomputes from the state and the revision (`_cstr_rate`, T08 build-first §A1.6).
#: The C1 reactors' `ξ` is their extent column too, and their `ν` the verifier's own copy of the
#: C1 reaction (`pr_c1.REACTION_NU`; M02 WO-9), which no revision states.
REACTING_MODELS: Final = frozenset(
    {"syn001.conversion_reactor", "syn001.kinetic_cstr", *pr_c1.REACTOR_MODELS}
)
KINETIC_CSTR: Final = "syn001.kinetic_cstr"


# -- the flowsheet rows ------------------------------------------------------------------------


def _feeds(view: RevisionView) -> list[str]:
    return [
        stream
        for instance in view.instances
        if instance.model_id in FEED_MODELS
        for port, direction in instance.directions.items()
        if direction == "outlet"
        for stream in instance.ports[port]
    ]


def _products(view: RevisionView) -> list[str]:
    return [
        stream
        for instance in view.instances
        if instance.model_id in PRODUCT_MODELS
        for port, direction in instance.directions.items()
        if direction == "inlet"
        for stream in instance.ports[port]
    ]


def _extent(reactor: InstanceView, state: Mapping[str, float]) -> float:
    """A reacting instance's `ξ`: the conversion reactor's extent column, the CSTR's rate."""
    if reactor.model_id == KINETIC_CSTR:
        return _cstr_rate(reactor, state)
    return state[extent_id(reactor.unit_id)]


def _nu(reactor: InstanceView, component: str) -> float:
    """A reacting instance's `ν_c`: the revision's `nu.<c>`, or for a C1 reactor the verifier's
    own copy of the C1 reaction (M02 WO-9)."""
    if reactor.model_id in pr_c1.REACTOR_MODELS:
        return pr_c1.REACTION_NU[component]
    return reactor.parameters[f"nu.{component}"]


def _envelope_material(
    view: RevisionView, state: Mapping[str, float], tolerances: Mapping[str, float]
) -> list[CheckResult]:
    """`Σ_feeds n + Σ_reactors ν_c ξ − Σ_products n`, accumulated in that order into one sum."""
    feeds, products = _feeds(view), _products(view)
    reactors = [i for i in view.instances if i.model_id in REACTING_MODELS]
    checks: list[CheckResult] = []
    for c in view.components:
        value = 0.0
        for stream in feeds:
            value += state[flow_id(stream, c)]
        for reactor in reactors:
            value += _nu(reactor, c) * _extent(reactor, state)
        for stream in products:
            value -= state[flow_id(stream, c)]
        checks.append(
            evaluated(
                id=f"material_balance.envelope.{c}",
                category="material_balance",
                subject="flowsheet",
                value=value,
                tolerance=tolerances["molar_flow"],
                reference=KIND_REFERENCE["molar_flow"],
            )
        )
    return checks


def _envelope_energy(
    view: RevisionView,
    state: Mapping[str, float],
    enthalpy: Mapping[str, float],
    tolerances: Mapping[str, float],
    note: str,
    degenerate: Degeneracy,
) -> CheckResult:
    """`(Σ Q_ext + Σ W) − (Σ Ḣ(products) − Σ Ḣ(feeds))`, each sum in declaration order."""
    reads = (*_products(view), *_feeds(view))
    blocked = _unlifted_read(reads, degenerate.unlifted)
    if blocked is not None:
        return blocked_check("energy_balance.envelope", "energy_balance", "flowsheet", blocked)
    duty = 0.0
    for instance in view.instances:
        if instance.model_id in EXTERNAL_DUTY_MODELS:
            duty += state[duty_id(instance.unit_id)]
        elif instance.model_id in STAGED_DUTY_MODELS:
            duty += column_rows.duty(instance, state, view.components)
    work = 0.0
    for instance in view.instances:
        if instance.model_id in WORK_MODELS:
            work += state[work_id(instance.unit_id)]
    products = 0.0
    for stream in _products(view):
        products += enthalpy[stream]
    feeds = 0.0
    for stream in _feeds(view):
        feeds += enthalpy[stream]
    return evaluated(
        id="energy_balance.envelope",
        category="energy_balance",
        subject="flowsheet",
        value=(duty + work) - (products - feeds),
        tolerance=tolerances["heat_rate"],
        reference=KIND_REFERENCE["heat_rate"],
        independence_qualification=note + stream_notes(reads, degenerate.notes),
    )


# -- admissibility and the independent split ---------------------------------------------------


def _split_checks(
    split: LiftedSplit,
    components: Sequence[str],
    state: Mapping[str, float],
    provider: PropertyProvider,
    context: EvaluationContext,
    tolerances: Mapping[str, float],
    note: str,
    distance: float | None = None,
    *,
    unresolved: bool = False,
) -> list[CheckResult]:
    """K04 §4.7 on one lifted split, read from the state at the split's `(T, P)`: K03 §8.2's
    admissibility, then a fresh flash of the split's feed compared with the split.

    A flowing split judged temperature-degenerate (`distance` is its `δ`; T05b spec §9.1) has
    instead `phase_admissibility.<U>.<S>.saturation` (value `δ`, kind temperature) in place of its
    branch's bubble, dew or closure check, and `independent_split.<U>.<S>` `not_applicable`
    (`temperature_degenerate`): its fresh flash cannot recompute what the state carries.

    An `unresolved` two-phase split (ADR 0013 D3; K04-F9 spec §5.3) keeps its branch's own
    admissibility check — it is not degenerate — and has `independent_split.<U>.<S>`
    `not_applicable` (`fresh_flash_unresolved`): one ulp of its temperature moves the fresh
    flash's vapour flow by at least a tenth of the tolerance it would be judged at."""
    name = f"{split.unit}.{split.stream}"
    subject = split.stream
    checks: list[CheckResult] = []

    if distance is not None:
        return [
            evaluated(
                id=f"phase_admissibility.{name}.saturation",
                category="phase_admissibility",
                subject=subject,
                value=distance,
                tolerance=tolerances["temperature"],
                reference=KIND_REFERENCE["temperature"],
                independence_qualification=note,
            ),
            dormant(
                id=f"independent_split.{name}",
                category="independent_split",
                subject=subject,
                reason="temperature_degenerate",
            ),
        ]

    vapor = tuple(state[column] for column in split.vapor)
    liquid = tuple(state[column] for column in split.liquid)
    temperature = state[split.temperature]
    pressure = state[split.pressure]
    total_vapor, total_liquid = sum(vapor), sum(liquid)

    if total_vapor + total_liquid == 0.0:
        checks.append(
            dormant(
                id=f"phase_admissibility.{name}", category="phase_admissibility", subject=subject
            )
        )
    else:
        constants = k_values(provider, temperature, pressure, context)
        if total_vapor == 0.0:
            checks.append(
                _one_sided(
                    id=f"phase_admissibility.{name}.bubble",
                    subject=subject,
                    value=sum(x * k for x, k in zip(_fractions(liquid), constants, strict=True)),
                    note=note,
                )
            )
        elif total_liquid == 0.0:
            checks.append(
                _one_sided(
                    id=f"phase_admissibility.{name}.dew",
                    subject=subject,
                    value=sum(y / k for y, k in zip(_fractions(vapor), constants, strict=True)),
                    note=note,
                )
            )
        else:
            checks.append(
                closure_check(
                    id=f"phase_admissibility.{name}.closure",
                    subject=subject,
                    provider=provider,
                    vapor=vapor,
                    liquid=liquid,
                    temperature=temperature,
                    pressure=pressure,
                    context=context,
                    tolerance=tolerances["temperature"],
                    note=note,
                )
            )

    carried = StreamState(
        n=tuple(state[column] for column in split.feed),
        temperature=temperature,
        pressure=pressure,
    )
    if carried.is_dormant:
        checks.append(
            dormant(id=f"independent_split.{name}", category="independent_split", subject=subject)
        )
        return checks
    if unresolved:
        checks.append(
            dormant(
                id=f"independent_split.{name}",
                category="independent_split",
                subject=subject,
                reason="fresh_flash_unresolved",
            )
        )
        return checks

    flashed = provider.flash(FlashRequest(state=carried), context)
    if flashed.status != "ok" or flashed.vapor is None:
        raise VerifierError(f"the verifier's own split of {name} returned {flashed.status}")
    checks.append(
        evaluated(
            id=f"independent_split.{name}.total",
            category="independent_split",
            subject=subject,
            value=state[split.vapor_total] - sum(flashed.vapor.n),
            tolerance=tolerances["molar_flow"],
            reference=KIND_REFERENCE["molar_flow"],
            independence_qualification=note,
        )
    )
    for index, component in enumerate(components):
        checks.append(
            evaluated(
                id=f"independent_split.{name}.{component}",
                category="independent_split",
                subject=subject,
                value=vapor[index] - flashed.vapor.n[index],
                tolerance=tolerances["molar_flow"],
                reference=KIND_REFERENCE["molar_flow"],
                independence_qualification=note,
            )
        )
    return checks


def _declared_phase(
    stream: str,
    phase: Phase,
    components: Sequence[str],
    state: Mapping[str, float],
    enthalpy: Mapping[str, float],
    provider: PropertyProvider,
    context: EvaluationContext,
) -> float:
    """`(Ḣ(S) − Ḣ_φ(S)) / Σ_i n_i ∂h_i^φ/∂T` at the stream's `(T, P)`: how far, in kelvin, the
    stream's fresh-flash enthalpy is from the declared phase's."""
    carried = stream_of(state, stream)
    result = provider.evaluate_phase(
        PropertyRequest(state=carried, phase=phase, properties=("h",), derivatives=("T",)),
        context,
    )
    if result.status != "ok":
        raise VerifierError(
            f"the verifier's own {phase} enthalpy of {stream} returned {result.status}"
        )
    phase_enthalpy, capacity = 0.0, 0.0
    for component, flow in zip(components, carried.n, strict=True):
        phase_enthalpy += flow * result.values[f"h_{component}"]
    for component, flow in zip(components, carried.n, strict=True):
        capacity += flow * result.derivatives[f"h_{component}"]["T"]
    return (enthalpy[stream] - phase_enthalpy) / capacity


def _declared_port_checks(
    view: RevisionView,
    state: Mapping[str, float],
    enthalpy: Mapping[str, float],
    provider: PropertyProvider,
    context: EvaluationContext,
    tolerances: Mapping[str, float],
    note: str,
    degenerate: Degeneracy,
) -> list[CheckResult]:
    checks: list[CheckResult] = []
    for instance in view.instances:
        entry = MODEL_CHECKS.get(instance.model_id)
        if entry is None:
            continue
        for port, several in entry.declared_ports:
            phase = instance.phases.get(port)
            if phase is None:
                continue
            for stream in instance.ports.get(port, ()):
                identifier = (
                    f"phase_admissibility.{instance.unit_id}.{port}.{stream}"
                    if several
                    else f"phase_admissibility.{instance.unit_id}.{port}"
                )
                if stream_of(state, stream, view.components).is_dormant:
                    checks.append(
                        dormant(id=identifier, category="phase_admissibility", subject=stream)
                    )
                    continue
                if stream in degenerate.unlifted:
                    checks.append(blocked_check(identifier, "phase_admissibility", stream, stream))
                    continue
                checks.append(
                    evaluated(
                        id=identifier,
                        category="phase_admissibility",
                        subject=stream,
                        value=_declared_phase(
                            stream, phase, view.components, state, enthalpy, provider, context
                        ),
                        tolerance=tolerances["temperature"],
                        reference=KIND_REFERENCE["temperature"],
                        independence_qualification=note + degenerate.notes.get(stream, ""),
                    )
                )
    return checks


# -- temperature-degenerate streams (T05b spec §9.1–§9.2; ADR 0012 D7) -------------------------


@dataclass(frozen=True)
class Degeneracy:
    """What the state's temperature does not determine, and what the verifier reads instead.

    A flowing stream is **temperature-degenerate** when its bubble and dew temperatures both lie
    within `τ_T` of its temperature (spec §4.4; `verify.saturation`, the verifier's own band):
    every vapour fraction is then consistent with its `(n, T, P)`, so the fresh flash of K04
    §4.4 cannot recompute the enthalpy the state carries. Empty at every registered state (the
    nearest is 16.28 K away, T05b W0.5), where the table is exactly K04's."""

    #: Split unit -> `δ` of its feed at the split's `(T, P)`, for each flowing degenerate split.
    splits: Mapping[str, float] = field(default_factory=dict)
    #: Stream -> `Ḣ` from the state's split (§9.1) or in its declared phase (§9.2).
    enthalpy: Mapping[str, float] = field(default_factory=dict)
    #: Stream -> the qualification suffix a check reading that enthalpy appends.
    notes: Mapping[str, str] = field(default_factory=dict)
    #: §9.2's `vapor_liquid` degenerate streams outside any split (unreachable after T05's S1
    #: ruling; specified so that it cannot become a silent path).
    unlifted: frozenset[str] = frozenset()
    #: ADR 0013 D3: split unit -> its fresh flash's floor `N ulp(T) / (w τ_flow)`, for each
    #: flowing two-phase split that is not degenerate and that the fresh flash cannot resolve.
    unresolved: Mapping[str, float] = field(default_factory=dict)


def _band(
    provider: PropertyProvider,
    flows: Sequence[float],
    pressure: float,
    context: EvaluationContext,
    what: str,
) -> tuple[float | None, float | None]:
    try:
        return band_ends(provider, flows, pressure, context)
    except SaturationError as error:
        raise VerifierError(
            f"the verifier's own band of {what} returned {error.status}: {error.message}"
        ) from error


def _phase_enthalpy(
    provider: PropertyProvider,
    context: EvaluationContext,
    flows: tuple[float, ...],
    temperature: float,
    pressure: float,
    phase: Phase,
    what: str,
) -> float:
    """`Σ_i n_i h_i^phase(T, P)` from a fresh `evaluate_phase`; exactly `0.0`, and not evaluated,
    when every flow is zero (ADR 0001 D3.1)."""
    carried = StreamState(n=flows, temperature=temperature, pressure=pressure)
    if carried.is_dormant:
        return 0.0
    result = provider.evaluate_phase(
        PropertyRequest(state=carried, phase=phase, properties=("h",)), context
    )
    if result.status != "ok":
        raise VerifierError(
            f"the verifier's own {phase} enthalpy of {what} returned {result.status}"
        )
    names = provider.describe().components
    total = 0.0
    for name, flow in zip(names, flows, strict=True):
        total += flow * result.values[f"h_{name}"]
    return total


def _producer_phases(view: RevisionView) -> dict[str, Phase | None]:
    """Each stream's declared capability, read at its producer's outlet port (R4)."""
    phases: dict[str, Phase | None] = {}
    for instance in view.instances:
        for port, direction in instance.directions.items():
            if direction == "outlet":
                for stream in instance.ports[port]:
                    phases[stream] = instance.phases.get(port)
    return phases


def degeneracy(
    view: RevisionView,
    splits: Sequence[LiftedSplit],
    state: Mapping[str, float],
    provider: PropertyProvider,
    context: EvaluationContext,
    tolerances: Mapping[str, float] | None = None,
    owners: Mapping[str, str] | None = None,
) -> Degeneracy:
    """§9.1–§9.2 at `state`: the degenerate splits and streams, and the enthalpies read instead;
    and ADR 0013 D3's unresolved splits, read the same way.

    Each flowing split's feed is tested at the split's `(T, P)`. A degenerate heater-style split
    gives its outlet `Σ v_i h_i^V(T, P) + Σ l_i h_i^L(T, P)`; a products-style one gives each
    product its own phase's enthalpy at its own `(T, P)`. A split that is not degenerate but
    unresolved (`verify.saturation.split_route`: two-phase, inside its band, its fresh flash's
    floor at least a tenth of the routing tolerance ρ_flow of `tolerances`, ADR 0013 A2) is
    substituted alike, with its own note. Every other flowing stream is tested at its own
    `(n, T, P)`; a degenerate one is evaluated in its declared phase, or, declared
    `vapor_liquid`, is `unlifted`.

    `owners` (S11 design §10.11) maps a staged split's key to the instance that owns it; a split
    the registry lifted is its own instance's (`owners.get(key, key)`). A staged split (a column
    stage) is heater-style: its stream is its key, which no flowsheet stream is."""
    flow_tolerance = routing_tolerances(tolerances)["molar_flow"]
    instances = {instance.unit_id: instance for instance in view.instances}
    owner = owners or {}
    distances: dict[str, float] = {}
    enthalpy: dict[str, float] = {}
    notes: dict[str, str] = {}
    unresolved: dict[str, float] = {}
    owned: set[str] = set()
    for split in splits:
        instance = instances[owner.get(split.unit, split.unit)]
        products = "vapor" in instance.ports and "liquid" in instance.ports
        if products:
            (vapor_stream,) = instance.ports["vapor"]
            (liquid_stream,) = instance.ports["liquid"]
            owned.update((vapor_stream, liquid_stream))
        else:
            owned.add(split.stream)
        feed = tuple(state[column] for column in split.feed)
        if all(flow == 0.0 for flow in feed):
            continue
        temperature, pressure = state[split.temperature], state[split.pressure]
        t_bubble, t_dew = _band(provider, feed, pressure, context, f"{split.unit}.{split.stream}")
        distance = band_distance(temperature, t_bubble, t_dew)
        route, floor = split_route(
            temperature,
            sum(feed),
            t_bubble,
            t_dew,
            two_phase=state[split.vapor_total] > 0.0 and state[split.liquid_total] > 0.0,
            flow_tolerance=flow_tolerance,
        )
        if route == "resolved":
            continue
        if route == "degenerate":
            distances[split.unit] = distance
            template = SPLIT_ENTHALPY_NOTE
        else:
            unresolved[split.unit] = floor if floor is not None else math.inf
            template = UNRESOLVED_ENTHALPY_NOTE
        vapor = tuple(state[column] for column in split.vapor)
        liquid = tuple(state[column] for column in split.liquid)
        if products:
            products_phases: tuple[tuple[str, tuple[float, ...], Phase], ...] = (
                (vapor_stream, vapor, "VAPOR"),
                (liquid_stream, liquid, "LIQUID"),
            )
            for stream, flows, phase in products_phases:
                if stream_of(state, stream).is_dormant:
                    continue
                enthalpy[stream] = _phase_enthalpy(
                    provider,
                    context,
                    flows,
                    state[temperature_id(stream)],
                    state[pressure_id(stream)],
                    phase,
                    stream,
                )
                notes[stream] = template.format(stream=stream)
        else:
            stream = split.stream
            enthalpy[stream] = _phase_enthalpy(
                provider, context, vapor, temperature, pressure, "VAPOR", stream
            ) + _phase_enthalpy(provider, context, liquid, temperature, pressure, "LIQUID", stream)
            notes[stream] = template.format(stream=stream)

    declared = _producer_phases(view)
    unlifted: set[str] = set()
    for stream in view.streams:
        carried = stream_of(state, stream)
        if stream in owned or carried.is_dormant:
            continue
        t_bubble, t_dew = _band(provider, carried.n, carried.pressure, context, stream)
        if not is_temperature_degenerate(band_distance(carried.temperature, t_bubble, t_dew)):
            continue
        capability = declared.get(stream)
        if capability is None:
            unlifted.add(stream)
            continue
        enthalpy[stream] = _phase_enthalpy(
            provider, context, carried.n, carried.temperature, carried.pressure, capability, stream
        )
        notes[stream] = DECLARED_ENTHALPY_NOTE.format(stream=stream, phase=capability)
    return Degeneracy(distances, enthalpy, notes, frozenset(unlifted), unresolved)


# -- the check set -----------------------------------------------------------------------------


def _thermal_rows() -> ModuleType:
    """`verify.thermal`, imported at the call: it imports this module."""
    from openflowsheet.verify import thermal  # noqa: PLC0415

    return thermal


def revision_checks(
    view: RevisionView,
    splits: Sequence[LiftedSplit],
    state: Mapping[str, float],
    *,
    provider: PropertyProvider,
    context: EvaluationContext,
    tolerances: Mapping[str, float],
    judged_at: Mapping[str, float] | None = None,
    owners: Mapping[str, str] | None = None,
) -> list[CheckResult]:
    """§4.3: the table's check set at `state`, category-major, for a revision-built flowsheet.

    Everything but the residual rows, the alias certificates and the derivative witness, which
    `verify_revision` runs as SYN-001's `_run_checks` and `_issue` do. `provider` is fresh.

    A temperature-degenerate split or stream (T05b spec §9.1–§9.2, `degeneracy`) is judged by
    what the state carries: its enthalpy in the one map every energy and declared-port check
    reads, its admissibility `.saturation`, its independent split `not_applicable`.

    `judged_at` (ADR 0013 D1; K04-F9 spec §5.1) is where the fresh-flash categories are
    evaluated — the energy balances and the enthalpy map they read, the splits' admissibility and
    independent split, the declared ports, and the degeneracy routing that selects among their
    forms; material balances, specifications and bounds stay at `state`. `None` is `state`.

    `owners` (S11 design §10.11): a staged split's key → its instance (`degeneracy`); `None`
    when no instance is staged. A model's own admissibility rows (`ModelChecks.admissibility`)
    follow the declared ports on every form."""
    at = state if judged_at is None else judged_at
    note = qualification(provider)
    reacting = any(i.model_id in REACTING_MODELS for i in view.instances)
    reaction_note = note + REACTION_DATUM_NOTE.format(
        convention=provider.describe().reference_convention
    )
    components = view.components
    # S11 design §4.6 (ADR 0050 D5): the form is resolved from the basis. M02 design note §14.2
    # B15: a `pr-c1-v1` revision takes `verify.pr_c1`'s forms at the sites below, SYN-001's runs
    # SYN-001's lines, and every other basis the declared-phase mixture form (`verify.forms`).
    form = forms.form_of(view.basis.provider_id)
    if form == forms.GAMMA_PHI_UNITS:
        # Units design §4.8 (I1b): `wilson-ig-v2` revisions take the γ–φ form, which imports this
        # module.
        from openflowsheet.verify import gamma_phi_units  # noqa: PLC0415

        return gamma_phi_units.revision_checks(
            view,
            splits,
            state,
            provider=provider,
            context=context,
            tolerances=tolerances,
            judged_at=judged_at,
            owners=owners,
        )
    pr = form == forms.PR
    mixture = form == forms.DECLARED_MIXTURE
    declared = forms.declared_phases(view) if mixture else {}
    # Units design §4.8 (I1b): on a pure-fluid basis a `vapor_liquid` outlet of a `thermal.*` unit
    # is saturated (ADR 0051 D1; L-TH-2), read from its carried split by `verify.thermal`; any other
    # stream without a declared phase stays unlifted (S11.A17).
    saturated = (
        frozenset(
            stream
            for instance in view.instances
            if instance.model_id.startswith("thermal.")
            for port, streams in instance.ports.items()
            if instance.directions.get(port) == "outlet" and instance.phases.get(port) is None
            for stream in streams
        )
        if mixture and forms.pure_fluid_provider(provider)
        else frozenset()
    )
    if mixture:
        # No bands; a flowing stream without a declared phase is unlifted (its checks blocked).
        degenerate = Degeneracy(
            notes={
                stream: _thermal_rows().CARRIED_SPLIT_NOTE.format(stream=stream)
                for stream in saturated
            },
            unlifted=frozenset(
                stream
                for stream, phase in declared.items()
                if phase is None
                and stream not in saturated
                and not stream_of(at, stream, components).is_dormant
            ),
        )
    else:
        degenerate = (
            Degeneracy()
            if pr
            else degeneracy(view, splits, at, provider, context, tolerances, owners)
        )

    energy: list[CheckResult] = []
    enthalpy: dict[str, float] = {}
    for stream in view.streams:
        carried = stream_of(at, stream, components)
        if stream in degenerate.enthalpy:
            enthalpy[stream] = degenerate.enthalpy[stream]
        elif carried.is_dormant:
            enthalpy[stream] = 0.0
            energy.append(
                dormant(
                    id=f"energy_balance.enthalpy.{stream}",
                    category="energy_balance",
                    subject=stream,
                )
            )
        elif pr:
            enthalpy[stream] = pr_c1.enthalpy_flow(provider, carried, context, components)
        elif mixture:
            phase = declared[stream]
            if stream in saturated:
                enthalpy[stream] = _thermal_rows().saturated_enthalpy(
                    provider, at, stream, context, components
                )
            else:
                # An unlifted stream's value is never judged: every check reading it is blocked.
                enthalpy[stream] = (
                    0.0 if phase is None else forms.enthalpy_flow(provider, carried, phase, context)
                )
        else:
            enthalpy[stream] = enthalpy_flow(provider, carried, context)

    # Each instance is read twice when the two points differ: its energy rows at `at`, its
    # material, specification and bounds rows at `state`.
    units: list[tuple[Unit, ModelChecks | None]] = [
        (
            Unit(
                view=instance,
                state=at,
                enthalpy=enthalpy,
                tolerances=tolerances,
                energy_note=reaction_note if instance.model_id in REACTING_MODELS else note,
                provider=provider,
                context=context,
                notes=degenerate.notes,
                unlifted=degenerate.unlifted,
                components=tuple(components),
            ),
            MODEL_CHECKS.get(instance.model_id),
        )
        for instance in view.instances
    ]

    material: list[CheckResult] = []
    specification: list[CheckResult] = []
    own_admissibility: list[CheckResult] = []
    bounds: list[CheckResult] = bounds_checks(
        provider, state, streams=view.streams, components=components
    )
    for judged, entry in units:
        certified = judged if at is state else replace(judged, state=state)
        if entry is None:
            material.append(
                unsupported(
                    id=f"material_balance.{certified.id}.all",
                    category="material_balance",
                    subject=certified.id,
                    reason=f"model_unsupported({certified.view.model_id})",
                )
            )
            continue
        material += entry.material(certified, components)
        energy += entry.energy(judged, components)
        specification += entry.specification(certified, components)
        bounds += entry.bounds(certified, components)
        own_admissibility += entry.admissibility(judged, components)
    material += _envelope_material(view, state, tolerances)
    energy.append(
        _envelope_energy(
            view, at, enthalpy, tolerances, reaction_note if reacting else note, degenerate
        )
    )

    admissibility: list[CheckResult] = []
    if mixture:
        admissibility += forms.stream_admissibility(view, declared, at, provider, context, note)
        if saturated:
            admissibility += _thermal_rows().saturated_stream_checks(
                view, at, provider, context, tolerances, note
            )
        admissibility += own_admissibility
        return [*material, *energy, *specification, *bounds, *admissibility]
    if pr:
        for split in splits:
            admissibility += pr_c1.split_checks(
                split, components, at, provider, context, tolerances, note
            )
        admissibility += pr_c1.declared_port_checks(
            view,
            at,
            provider,
            context,
            note,
            {model: entry.declared_ports for model, entry in MODEL_CHECKS.items()},
        )
        admissibility += own_admissibility
        return [*material, *energy, *specification, *bounds, *admissibility]
    for split in splits:
        admissibility += _split_checks(
            split,
            components,
            at,
            provider,
            context,
            tolerances,
            note,
            degenerate.splits.get(split.unit),
            unresolved=split.unit in degenerate.unresolved,
        )
    admissibility += _declared_port_checks(
        view, at, enthalpy, provider, context, tolerances, note, degenerate
    )
    admissibility += own_admissibility
    return [*material, *energy, *specification, *bounds, *admissibility]


def revision_phase_branch(
    state: Mapping[str, float],
    streams: Sequence[str],
    splits: Sequence[LiftedSplit],
    *,
    components: Sequence[str] = COMPONENTS,
) -> dict[str, Any]:
    """§4.2: every stream's regime, and each lifted split read from the state, keyed
    `<unit>:<stream>`; `components` the order a stream's flows are read in (the revision's)."""
    branch: dict[str, Any] = {
        stream: "ZERO_FLOW" if stream_of(state, stream, components).is_dormant else "FLOWING"
        for stream in streams
    }
    for split in splits:
        branch[f"{split.unit}:{split.stream}"] = {
            "vapor_total": state[split.vapor_total],
            "liquid_total": state[split.liquid_total],
            "vapor": [state[column] for column in split.vapor],
            "liquid": [state[column] for column in split.liquid],
        }
    return branch
