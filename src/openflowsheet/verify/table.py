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
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Any, Final

from openflowsheet.compiled import EvaluationContext
from openflowsheet.models import duty_id, flow_id, pressure_id, temperature_id
from openflowsheet.models.revision_flowsheet import InstanceView, RevisionView
from openflowsheet.models.syn001.conversion_reactor import extent_id
from openflowsheet.models.syn001.flash import total_flow_id
from openflowsheet.models.syn001.pump import work_id
from openflowsheet.models.syn001.tp_state import (
    liquid_flow_id,
    liquid_total_id,
    vapor_flow_id,
    vapor_total_id,
)
from openflowsheet.thermo import (
    FlashRequest,
    Phase,
    PropertyProvider,
    PropertyRequest,
    StreamState,
)
from openflowsheet.verify import (
    NEAR_THRESHOLD_MARGIN,
    CheckCategory,
    CheckResult,
    dormant,
    evaluated,
    pr_c1,
    unsupported,
)
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

#: §4.3: appended to `qualification(provider)` on a reacting unit's energy balance and on the
#: envelope's when a reactor is present. `{convention}` is the provider's reference convention.
REACTION_DATUM_NOTE: Final = (
    "; reacting unit: this balance is meaningful only under ADR 0011 D2, the provider's "
    "reference convention {convention} declared a formation datum, so the heat of reaction is "
    "carried by Hdot and never added separately"
)

#: T05b spec §9.1 (ADR 0012 D7): appended to the qualification of every energy and declared-port
#: check that reads the enthalpy of a stream of a temperature-degenerate split.
SPLIT_ENTHALPY_NOTE: Final = (
    "; enthalpy of {stream} from the state's split: temperature-degenerate (ADR 0012 D7)"
)
#: §9.2: the same, for a degenerate stream outside any split, evaluated in its declared phase.
DECLARED_ENTHALPY_NOTE: Final = (
    "; enthalpy of {stream} in its declared phase {phase}: temperature-degenerate (ADR 0012 D7)"
)
#: ADR 0013 D3 (K04-F9 spec §5.3): the same, for a stream of an unresolved two-phase split.
UNRESOLVED_ENTHALPY_NOTE: Final = (
    "; enthalpy of {stream} from the state's split: fresh flash unresolved (ADR 0013 D3)"
)

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
)
#: `W`: the shaft work `<U>.W`.
WORK_MODELS: Final = frozenset({"syn001.liquid_pump"})
#: `ν_c ξ` on the material envelope; ADR 0011 D2's note on the energy balances. A conversion
#: reactor's `ξ` is its extent column; a kinetic CSTR's is its rate `r`, which it does not own and
#: the table recomputes from the state and the revision (`_cstr_rate`, T08 build-first §A1.6).
#: The C1 reactors' `ξ` is their extent column too, and their `ν` the verifier's own copy of the
#: C1 reaction (`pr_c1.REACTION_NU`; M02 WO-9), which no revision states.
REACTING_MODELS: Final = frozenset(
    {"syn001.conversion_reactor", "syn001.kinetic_cstr", *pr_c1.REACTOR_MODELS}
)
KINETIC_CSTR: Final = "syn001.kinetic_cstr"


@dataclass(frozen=True)
class Unit:
    """One instance as a table entry reads it: its revision view, the state being judged, each
    stream's fresh-flash enthalpy flow, the tolerances, and the qualification its energy rows
    carry. Ids are `<category>.<unit>.<item>` (spec §12.1)."""

    view: InstanceView
    state: Mapping[str, float]
    #: `Ḣ(S)` by stream, computed once per stream in allocation order.
    enthalpy: Mapping[str, float]
    tolerances: Mapping[str, float]
    #: `qualification(provider)`, plus `REACTION_DATUM_NOTE` on a reacting unit.
    energy_note: str
    #: The fresh provider and the declaration's context, for a rule that evaluates a phase
    #: property of its own (the pump's work relation); `None` where no rule needs one.
    provider: PropertyProvider | None = None
    context: EvaluationContext | None = None
    #: T05b spec §9.1–§9.2: the qualification suffix of each stream whose enthalpy the state's
    #: split or its declared phase supplies (a temperature-degenerate stream).
    notes: Mapping[str, str] = field(default_factory=dict)
    #: §9.2: flowing, temperature-degenerate `vapor_liquid` streams outside any split, whose
    #: enthalpy the state does not determine; a check reading one is `unsupported`.
    unlifted: frozenset[str] = frozenset()
    #: The order a stream's flows are read in: the revision's view's (M02 design note §14.2 B15
    #: item 1); SYN-001's by default.
    components: tuple[str, ...] = COMPONENTS

    @property
    def id(self) -> str:
        return self.view.unit_id

    def streams(self, port: str) -> tuple[str, ...]:
        """A port's streams in connection order (R1)."""
        return tuple(self.view.ports.get(port, ()))

    def stream(self, port: str) -> str:
        """A single-stream port's stream."""
        connected = self.streams(port)
        if len(connected) != 1:
            raise VerifierError(f"port_not_single({self.id}.{port})")
        return connected[0]

    def inlets(self) -> tuple[str, ...]:
        return tuple(
            stream
            for port, direction in self.view.directions.items()
            if direction == "inlet"
            for stream in self.view.ports[port]
        )

    def n(self, stream: str, component: str) -> float:
        return self.state[flow_id(stream, component)]

    def pinned(self, *columns: str) -> str | None:
        """The one of `columns` the revision pins, or `None` (the builder allows exactly one)."""
        found = [column for column in columns if column in self.view.pins]
        if len(found) > 1:
            raise VerifierError(f"pin_conflict({self.id}, {', '.join(found)})")
        return found[0] if found else None

    def pin(self, column: str) -> float:
        """The revision's value for a pinned column (R5)."""
        if column not in self.view.pins:
            raise VerifierError(f"pin_missing({self.id}, {column})")
        return self.view.pins[column]

    def parameter(self, name: str) -> float:
        """The revision's value of an instance parameter (R6)."""
        if name not in self.view.parameters:
            raise VerifierError(f"parameter_missing({self.id}.{name})")
        return self.view.parameters[name]

    def check(
        self,
        category: CheckCategory,
        item: str,
        value: float,
        kind: str,
        *,
        reads: Sequence[str] | None = None,
    ) -> CheckResult:
        """A two-sided check, `|value| <= tolerances[kind]`; `item` empty names the unit's
        balance itself (`energy_balance.<U>`). Every energy row carries the qualification.

        An energy row names the streams whose enthalpy (from `Unit.enthalpy`) it `reads`: each
        temperature-degenerate one appends its note (T05b spec §9.1), and an unlifted degenerate
        one makes the check `unsupported` (§9.2). A rule that reads no enthalpy says `()`."""
        identifier = f"{category}.{self.id}.{item}" if item else f"{category}.{self.id}"
        note: str | None = None
        if category == "energy_balance":
            if reads is None:
                raise VerifierError(f"energy_reads_undeclared({identifier})")
            blocked = _unlifted_read(reads, self.unlifted)
            if blocked is not None:
                return blocked_check(identifier, category, self.id, blocked)
            note = self.energy_note + stream_notes(reads, self.notes)
        return evaluated(
            id=identifier,
            category=category,
            subject=self.id,
            value=value,
            tolerance=self.tolerances[kind],
            reference=KIND_REFERENCE[kind],
            independence_qualification=note,
        )

    def one_sided(
        self, item: str, value: float, kind: str, *, judged_at_dormancy: bool = False
    ) -> CheckResult:
        """A `bounds_and_domain` check: passes iff `value <= τ`, near threshold iff
        `τ/10 < value <= 10τ`; not applicable when any inlet of the unit is dormant, unless the
        check reads nothing a dormant stream's label decides (`judged_at_dormancy`)."""
        identifier = f"bounds_and_domain.{self.id}.{item}"
        if not judged_at_dormancy and any(
            stream_of(self.state, stream, self.components).is_dormant for stream in self.inlets()
        ):
            return dormant(id=identifier, category="bounds_and_domain", subject=self.id)
        tolerance = self.tolerances[kind]
        return CheckResult(
            id=identifier,
            category="bounds_and_domain",
            subject=self.id,
            result="pass" if value <= tolerance else "fail",
            value=value,
            tolerance=tolerance,
            reference=KIND_REFERENCE[kind],
            near_threshold=(
                tolerance / NEAR_THRESHOLD_MARGIN < value <= tolerance * NEAR_THRESHOLD_MARGIN
            ),
        )


def stream_notes(reads: Sequence[str], notes: Mapping[str, str]) -> str:
    """The degenerate-enthalpy notes of the streams a check reads, in reading order, once each."""
    return "".join(notes[stream] for stream in dict.fromkeys(reads) if stream in notes)


def _unlifted_read(reads: Sequence[str], unlifted: frozenset[str]) -> str | None:
    return next((stream for stream in reads if stream in unlifted), None)


def blocked_check(
    identifier: str, category: CheckCategory, subject: str, stream: str
) -> CheckResult:
    """T05b spec §9.2: a check reading an enthalpy the state does not determine."""
    return unsupported(
        id=identifier,
        category=category,
        subject=subject,
        reason=f"temperature_degenerate_unlifted({stream})",
    )


Rule = Callable[[Unit, Sequence[str]], list[CheckResult]]


def _nothing(unit: Unit, components: Sequence[str]) -> list[CheckResult]:
    return []


@dataclass(frozen=True)
class ModelChecks:
    """One model's rows of §4.3's table, by category, each in the table's row order.

    A rule takes the unit and the component order and returns its checks. `declared_ports` are
    the ports whose declared phase is checked (§4.3's admissibility category), each with whether
    it carries several streams (`phase_admissibility.<U>.<port>.<S>`) or one
    (`phase_admissibility.<U>.<port>`); a port declared `vapor_liquid` is skipped."""

    material: Rule = _nothing
    energy: Rule = _nothing
    specification: Rule = _nothing
    #: One-sided `bounds_and_domain` rows (`Unit.one_sided`), after the generic bounds.
    bounds: Rule = _nothing
    declared_ports: tuple[tuple[str, bool], ...] = ()


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
MODEL_CHECKS: Final[Mapping[str, ModelChecks]] = {
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
    `vapor_liquid`, is `unlifted`."""
    flow_tolerance = routing_tolerances(tolerances)["molar_flow"]
    instances = {instance.unit_id: instance for instance in view.instances}
    distances: dict[str, float] = {}
    enthalpy: dict[str, float] = {}
    notes: dict[str, str] = {}
    unresolved: dict[str, float] = {}
    owned: set[str] = set()
    for split in splits:
        instance = instances[split.unit]
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


def revision_checks(
    view: RevisionView,
    splits: Sequence[LiftedSplit],
    state: Mapping[str, float],
    *,
    provider: PropertyProvider,
    context: EvaluationContext,
    tolerances: Mapping[str, float],
    judged_at: Mapping[str, float] | None = None,
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
    forms; material balances, specifications and bounds stay at `state`. `None` is `state`."""
    at = state if judged_at is None else judged_at
    note = qualification(provider)
    reacting = any(i.model_id in REACTING_MODELS for i in view.instances)
    reaction_note = note + REACTION_DATUM_NOTE.format(
        convention=provider.describe().reference_convention
    )
    components = view.components
    # M02 design note §14.2 B15: a `pr-c1-v1` revision takes `verify.pr_c1`'s forms at the
    # sites below; every other basis runs SYN-001's lines.
    pr = view.basis.provider_id == pr_c1.PROVIDER_ID
    degenerate = Degeneracy() if pr else degeneracy(view, splits, at, provider, context, tolerances)

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
    material += _envelope_material(view, state, tolerances)
    energy.append(
        _envelope_energy(
            view, at, enthalpy, tolerances, reaction_note if reacting else note, degenerate
        )
    )

    admissibility: list[CheckResult] = []
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
