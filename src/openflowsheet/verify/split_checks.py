"""The check table's admissibility, independent-split and temperature-degeneracy rows (T05 design
note §4, register R-046; T05b spec §9.1-§9.2, ADR 0012 D7). `verify.table` re-exports
`Degeneracy` and `degeneracy`."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, NamedTuple

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
    Route,
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
    Judging,
    blocked_check,
    declared_streams,
    degenerate_split_rows,
    independent_split_rows,
)

if TYPE_CHECKING:
    from openflowsheet.models.lifted import LiftedSplit
    from openflowsheet.models.revision_flowsheet import InstanceView


# -- admissibility and the independent split ---------------------------------------------------


def _split_checks(
    split: LiftedSplit, judging: Judging, distance: float | None = None, *, unresolved: bool = False
) -> list[CheckResult]:
    """K04 §4.7 on one lifted split, read from the state at the split's `(T, P)`: K03 §8.2's
    admissibility (`_split_admissibility`), then a fresh flash of the split's feed compared with
    the split.

    A flowing split judged temperature-degenerate (`distance` is its `δ`; T05b spec §9.1) has
    instead `phase_admissibility.<U>.<S>.saturation` (value `δ`, kind temperature) in place of its
    branch's bubble, dew or closure check, and `independent_split.<U>.<S>` `not_applicable`
    (`temperature_degenerate`): its fresh flash cannot recompute what the state carries
    (`table_kit.degenerate_split_rows`, returned before the split is read).

    An `unresolved` two-phase split (ADR 0013 D3; K04-F9 spec §5.3) keeps its branch's own
    admissibility check — it is not degenerate — and has `independent_split.<U>.<S>`
    `not_applicable` (`fresh_flash_unresolved`): one ulp of its temperature moves the fresh
    flash's vapour flow by at least a tenth of the tolerance it would be judged at."""
    name = f"{split.unit}.{split.stream}"
    subject = split.stream

    if distance is not None:
        return degenerate_split_rows(name, subject, distance, judging.tolerances, judging.note)

    at = _SplitAt(
        name,
        subject,
        vapor=tuple(judging.state[column] for column in split.vapor),
        liquid=tuple(judging.state[column] for column in split.liquid),
        temperature=judging.state[split.temperature],
        pressure=judging.state[split.pressure],
    )
    checks = [_split_admissibility(at, judging)]

    carried = StreamState(
        n=tuple(judging.state[column] for column in split.feed),
        temperature=at.temperature,
        pressure=at.pressure,
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

    flashed = judging.provider.flash(FlashRequest(state=carried), judging.context)
    if flashed.status != "ok" or flashed.vapor is None:
        raise VerifierError(f"the verifier's own split of {name} returned {flashed.status}")
    total = judging.state[split.vapor_total] - sum(flashed.vapor.n)
    differences = [
        at.vapor[index] - flashed.vapor.n[index] for index in range(len(judging.components))
    ]
    checks += independent_split_rows(name, subject, total, differences, judging)
    return checks


class _SplitAt(NamedTuple):
    """A lifted split as `_split_checks` reads it from the state, at the split's own `(T, P)`."""

    #: `<U>.<S>`, the middle of its check ids.
    name: str
    #: `S`, the split's stream: the subject of its checks.
    subject: str
    #: Its vapour and liquid flows, in the order of the split's own columns.
    vapor: tuple[float, ...]
    liquid: tuple[float, ...]
    temperature: float
    pressure: float


def _split_admissibility(at: _SplitAt, judging: Judging) -> CheckResult:
    """K03 §8.2's admissibility of the split read `at` (K04 §4.7): `phase_admissibility.<U>.<S>`
    `not_applicable` when both phases are empty; else, from `k_values` at the split's `(T, P)`,
    the bubble test of an all-liquid split, the dew test of an all-vapour one, or the two-phase
    closure (`closure_check`, at the temperature kind's tolerance of `judging.tolerances`), each
    qualified by `judging.note`."""
    total_vapor, total_liquid = sum(at.vapor), sum(at.liquid)
    if total_vapor + total_liquid == 0.0:
        return dormant(
            id=f"phase_admissibility.{at.name}", category="phase_admissibility", subject=at.subject
        )
    constants = k_values(judging.provider, at.temperature, at.pressure, judging.context)
    if total_vapor == 0.0:
        return _one_sided(
            id=f"phase_admissibility.{at.name}.bubble",
            subject=at.subject,
            value=sum(x * k for x, k in zip(_fractions(at.liquid), constants, strict=True)),
            note=judging.note,
        )
    if total_liquid == 0.0:
        return _one_sided(
            id=f"phase_admissibility.{at.name}.dew",
            subject=at.subject,
            value=sum(y / k for y, k in zip(_fractions(at.vapor), constants, strict=True)),
            note=judging.note,
        )
    return closure_check(
        id=f"phase_admissibility.{at.name}.closure",
        subject=at.subject,
        provider=judging.provider,
        vapor=at.vapor,
        liquid=at.liquid,
        temperature=at.temperature,
        pressure=at.pressure,
        context=judging.context,
        tolerance=judging.tolerances["temperature"],
        note=judging.note,
    )


def _declared_phase(
    stream: str, phase: Phase, enthalpy: Mapping[str, float], judging: Judging
) -> float:
    """`(Ḣ(S) − Ḣ_φ(S)) / Σ_i n_i ∂h_i^φ/∂T` at the stream's `(T, P)`: how far, in kelvin, the
    stream's fresh-flash enthalpy is from the declared phase's."""
    carried = stream_of(judging.state, stream)
    result = judging.provider.evaluate_phase(
        PropertyRequest(state=carried, phase=phase, properties=("h",), derivatives=("T",)),
        judging.context,
    )
    if result.status != "ok":
        raise VerifierError(
            f"the verifier's own {phase} enthalpy of {stream} returned {result.status}"
        )
    phase_enthalpy, capacity = 0.0, 0.0
    for component, flow in zip(judging.components, carried.n, strict=True):
        phase_enthalpy += flow * result.values[f"h_{component}"]
    for component, flow in zip(judging.components, carried.n, strict=True):
        capacity += flow * result.derivatives[f"h_{component}"]["T"]
    return (enthalpy[stream] - phase_enthalpy) / capacity


def _declared_port_checks(
    view: RevisionView,
    declared_ports: Mapping[str, tuple[tuple[str, bool], ...]],
    enthalpy: Mapping[str, float],
    degenerate: Degeneracy,
    judging: Judging,
) -> list[CheckResult]:
    checks: list[CheckResult] = []
    for declared in declared_streams(view, declared_ports):
        identifier, stream = declared.identifier, declared.stream
        if stream_of(judging.state, stream, view.components).is_dormant:
            checks.append(dormant(id=identifier, category="phase_admissibility", subject=stream))
            continue
        if stream in degenerate.unlifted:
            checks.append(blocked_check(identifier, "phase_admissibility", stream, stream))
            continue
        checks.append(
            evaluated(
                id=identifier,
                category="phase_admissibility",
                subject=stream,
                value=_declared_phase(stream, declared.phase, enthalpy, judging),
                tolerance=judging.tolerances["temperature"],
                reference=KIND_REFERENCE["temperature"],
                independence_qualification=judging.note + degenerate.notes.get(stream, ""),
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
            if direction != "outlet":
                continue
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
    stage) is heater-style: its stream is its key, which no flowsheet stream is. The owning
    instance's ports decide the style (`_product_streams`) and so the streams the split owns
    (`_owned_streams`); `_split_substitution` tests each split and `_degenerate_streams` every
    other stream. Raises `VerifierError` when the verifier's own band or phase evaluation fails."""
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
        product_streams = _product_streams(instance)
        owned.update(_owned_streams(split, product_streams))
        substitution = _split_substitution(
            provider, context, state, split, flow_tolerance, product_streams
        )
        if substitution is None:
            continue
        if substitution.route == "degenerate":
            distances[split.unit] = substitution.distance
            template = SPLIT_ENTHALPY_NOTE
        else:
            floor = substitution.floor
            unresolved[split.unit] = floor if floor is not None else math.inf
            template = UNRESOLVED_ENTHALPY_NOTE
        for stream, value in substitution.enthalpy.items():
            enthalpy[stream] = value
            notes[stream] = template.format(stream=stream)

    declared_enthalpy, declared_notes, unlifted = _degenerate_streams(
        view, state, provider, context, owned
    )
    enthalpy.update(declared_enthalpy)
    notes.update(declared_notes)
    return Degeneracy(distances, enthalpy, notes, frozenset(unlifted), unresolved)


def _product_streams(instance: InstanceView) -> tuple[str, str] | None:
    """The vapour and liquid streams of a products-style split's owning `instance`: the single
    stream of each of its `vapor` and `liquid` ports. None when it lacks either port (a
    heater-style split). Unpacking raises `ValueError` when either port carries more or fewer
    than one stream."""
    if "vapor" in instance.ports and "liquid" in instance.ports:
        (vapor_stream,) = instance.ports["vapor"]
        (liquid_stream,) = instance.ports["liquid"]
        return vapor_stream, liquid_stream
    return None


def _owned_streams(split: LiftedSplit, product_streams: tuple[str, str] | None) -> tuple[str, ...]:
    """The streams `split` owns, which §9.2 leaves to it (`_degenerate_streams`' `owned`): a
    products-style split's vapour and liquid streams (`product_streams`), else, `product_streams`
    None (a heater-style split, or a staged one whose stream is its key), its own stream."""
    if product_streams is not None:
        return product_streams
    return (split.stream,)


class _SplitSubstitution(NamedTuple):
    """A flowing split that is not resolved, and the enthalpies §9.1 gives its streams."""

    #: `degenerate` (§9.1) or `unresolved` (ADR 0013 D3).
    route: Route
    #: `δ` of its feed at the split's `(T, P)`.
    distance: float
    #: Its fresh flash's floor over `τ_flow`; None outside the band.
    floor: float | None
    #: Stream -> `Ḣ` from the state's split (`_split_enthalpies`).
    enthalpy: dict[str, float]


def _split_substitution(
    provider: PropertyProvider,
    context: EvaluationContext,
    state: Mapping[str, float],
    split: LiftedSplit,
    flow_tolerance: float,
    product_streams: tuple[str, str] | None,
) -> _SplitSubstitution | None:
    """§9.1 and ADR 0013 D3 at one split of `state`: its feed tested at the split's `(T, P)`
    (`split_route`), and, when it is degenerate or unresolved, the enthalpies
    `_split_enthalpies` gives its streams (`product_streams` as there).

    None when every feed flow is zero (not tested) or when the split is resolved. Raises
    `VerifierError` when the verifier's own band or phase evaluation fails."""
    feed = tuple(state[column] for column in split.feed)
    if all(flow == 0.0 for flow in feed):
        return None
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
        return None
    split_enthalpy = _split_enthalpies(
        provider, context, state, split, temperature, pressure, product_streams
    )
    return _SplitSubstitution(route, distance, floor, split_enthalpy)


def _split_enthalpies(
    provider: PropertyProvider,
    context: EvaluationContext,
    state: Mapping[str, float],
    split: LiftedSplit,
    temperature: float,
    pressure: float,
    product_streams: tuple[str, str] | None,
) -> dict[str, float]:
    """§9.1 at `state`: the enthalpy a degenerate or unresolved split gives each of its streams,
    read from the state's split rather than from a fresh flash.

    `product_streams` are a products-style split's vapour and liquid streams: each one that is not
    dormant gets its own phase's enthalpy at its own `(T, P)`, vapour first. None is a
    heater-style split: its stream gets `Σ v_i h_i^V(T, P) + Σ l_i h_i^L(T, P)` at the split's
    `temperature` and `pressure`. Raises `VerifierError` when the verifier's own phase
    evaluation fails."""
    vapor = tuple(state[column] for column in split.vapor)
    liquid = tuple(state[column] for column in split.liquid)
    if product_streams is not None:
        vapor_stream, liquid_stream = product_streams
        products_phases: tuple[tuple[str, tuple[float, ...], Phase], ...] = (
            (vapor_stream, vapor, "VAPOR"),
            (liquid_stream, liquid, "LIQUID"),
        )
        found: dict[str, float] = {}
        for stream, flows, phase in products_phases:
            if stream_of(state, stream).is_dormant:
                continue
            found[stream] = _phase_enthalpy(
                provider,
                context,
                flows,
                state[temperature_id(stream)],
                state[pressure_id(stream)],
                phase,
                stream,
            )
        return found
    stream = split.stream
    return {
        stream: _phase_enthalpy(provider, context, vapor, temperature, pressure, "VAPOR", stream)
        + _phase_enthalpy(provider, context, liquid, temperature, pressure, "LIQUID", stream)
    }


def _degenerate_streams(
    view: RevisionView,
    state: Mapping[str, float],
    provider: PropertyProvider,
    context: EvaluationContext,
    owned: set[str],
) -> tuple[dict[str, float], dict[str, str], set[str]]:
    """§9.2 at `state`: every flowing stream of `view` outside `owned` (the splits' streams),
    tested at its own `(n, T, P)`. Returns the enthalpies and notes of the degenerate ones in
    their declared phase (read at the producer's outlet port), in stream order, and the
    degenerate ones with no declared phase there (declared `vapor_liquid`, or no producer),
    which are unlifted.

    Raises `VerifierError` when the verifier's own band or phase evaluation fails."""
    declared = _producer_phases(view)
    declared_enthalpy: dict[str, float] = {}
    declared_notes: dict[str, str] = {}
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
        declared_enthalpy[stream] = _phase_enthalpy(
            provider, context, carried.n, carried.temperature, carried.pressure, capability, stream
        )
        declared_notes[stream] = DECLARED_ENTHALPY_NOTE.format(stream=stream, phase=capability)
    return declared_enthalpy, declared_notes, unlifted
