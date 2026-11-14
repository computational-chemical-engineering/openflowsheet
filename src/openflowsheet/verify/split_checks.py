"""The check table's admissibility, independent-split and temperature-degeneracy rows (T05 design
note §4, register R-046; T05b spec §9.1-§9.2, ADR 0012 D7). `verify.table` re-exports
`Degeneracy` and `degeneracy`."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from openflowsheet.compiled import EvaluationContext
from openflowsheet.models import pressure_id, temperature_id
from openflowsheet.models.revision_flowsheet import RevisionView
from openflowsheet.thermo import FlashRequest, Phase, PropertyProvider, PropertyRequest, StreamState
from openflowsheet.verify import CheckResult, dormant, evaluated
from openflowsheet.verify.checks import (
    KIND_REFERENCE,
    VerifierError,
    _fractions,
    _one_sided,
    closure_check,
    k_values,
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
from openflowsheet.verify.table_kit import (
    DECLARED_ENTHALPY_NOTE,
    SPLIT_ENTHALPY_NOTE,
    UNRESOLVED_ENTHALPY_NOTE,
    blocked_check,
)
from openflowsheet.verify.unit_checks import MODEL_CHECKS

if TYPE_CHECKING:
    from openflowsheet.orchestrator.region import LiftedSplit


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
