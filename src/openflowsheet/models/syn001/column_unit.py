"""`syn001.column` as a flowsheet unit (S11 design note §4.7, ADR 0050 D6).

Authority `docs/derivations/S11-design.md` §4.7. The column is embedded, not wrapped: in a
flowsheet it contributes S02/S06's own rows (`column.declared_rows(..., links=...)`), its inlet
pin rows become link rows to the connected streams, and link rows tie its two products to the
outlet streams.

This module holds what the builder and the verifier share: `ColumnStructure`, the instance's
configuration without any inlet state; `column_structure`, the pure parser of a revision instance
into it; and `structural_spec`, a `ColumnSpec` whose inlet states are NaN and carry only the
declared phase, which may be passed to `declared_rows(..., links=...)`, `column_solve.
lifted_splits`, `zero_flow_forms`, `closure_types` and `split_temperatures` and to nothing else
(§4.7.2).

Ports (§4.7.1): `feed` (side feeds, named `feed1, feed2, …` in connection order, each at the stage
`feed_stage.<connection id>`), `top` and `bottom` (optional; connected means condenser and
reboiler `none`), `distillate` and `bottoms`. A missing phase declaration on an inlet is
`port_unsupported`, a contradiction `specification_conflict`. Build decisions:
`docs/S11B_DECISIONS.md`.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Final

from openflowsheet.canonical import file_sha256
from openflowsheet.compiled import EvaluationContext
from openflowsheet.models import (
    Contribution,
    DeclaredEquation,
    DerivativeDeclaration,
    Initialization,
    Port,
    SpecificationError,
    UnitEvaluation,
    Validity,
    Wiring,
    flow_id,
    manifest_document,
)
from openflowsheet.models.revision_flowsheet import InstanceView, RevisionError
from openflowsheet.models.syn001 import P_MAX, P_MIN
from openflowsheet.models.syn001.cascade import (
    _TOKEN,
    BOTTOM,
    TOP,
    CascadeFailure,
    InletState,
    SideFeed,
    inlet_stream,
    stage_pressure_id,
    stage_temperature_id,
)
from openflowsheet.models.syn001.column import (
    COMPONENT_KINDS,
    CONDENSER,
    END_KINDS,
    EQUATIONS,
    F_REF,
    FLOWSHEET_EQUATIONS,
    GAMMA_PHI_KINDS,
    INVERSE_KINDS,
    MODEL_ID,
    REBOILER,
    ColumnSpec,
    EndSpecification,
    FlowsheetLinks,
    declared_rows,
    product_flow_id,
    product_total_id,
    purity_flow_id,
    recovery_flow_id,
)
from openflowsheet.models.syn001.column_solve import ColumnSolution, products, solve_column
from openflowsheet.models.syn001.equilibrium_form import equilibrium_form
from openflowsheet.models.syn001.ph_kernel import port_enthalpy, typed_failure
from openflowsheet.thermo import Phase, PropertyProvider, PropertyStatus, StreamState

#: The unit's material ports (§4.7.1).
FEED: Final = "feed"
DISTILLATE: Final = "distillate"
BOTTOMS: Final = "bottoms"
INLET_PORTS: Final[tuple[str, ...]] = (FEED, TOP, BOTTOM)
OUTLET_PORTS: Final[tuple[str, ...]] = (DISTILLATE, BOTTOMS)

#: The instance parameters (§4.7.1), by name up to the first `.`.
STAGE_COUNT: Final = "stage_count"
STAGE_PRESSURE: Final = "stage_pressure"
FEED_STAGE: Final = "feed_stage"
STAGE_DUTY: Final = "stage_duty"


@dataclass(frozen=True)
class PlacedPort:
    """One connected inlet: the unit `port` it is wired to, its `name` in the `ColumnSpec`
    (`top`, `bottom`, `feed<k>`; the `SideFeed.port` of row ids), its stage, its declared phase
    and its stream."""

    port: str
    name: str
    stage: int
    phase: Phase
    stream: str


@dataclass(frozen=True)
class ColumnStructure:
    """A column instance's configuration, everything but the inlet states (§4.7.2)."""

    unit_id: str
    stage_count: int
    condenser: str
    reboiler: str
    #: `P_j*`, Pa, one per stage, top to bottom.
    pressures: tuple[float, ...]
    #: `None` exactly at a column-specification stage; `0.0` where `stage_duty.<j>` is absent.
    duties: tuple[float | None, ...]
    condenser_spec: EndSpecification | None
    reboiler_spec: EndSpecification | None
    #: `top`, `bottom`, then the side feeds in connection order (`ColumnSpec.inlets()` order).
    inlets: tuple[PlacedPort, ...]
    distillate: str
    bottoms: str
    components: tuple[str, ...]

    def links(self) -> FlowsheetLinks:
        return FlowsheetLinks(
            inlets={inlet.name: inlet.stream for inlet in self.inlets},
            distillate=self.distillate,
            bottoms=self.bottoms,
        )

    def spec(self, states: Mapping[str, InletState]) -> ColumnSpec:
        """The `ColumnSpec` with each inlet's state, keyed by its `name`."""
        by_name = {inlet.name: inlet for inlet in self.inlets}
        if set(states) != set(by_name):
            raise ValueError(
                f"{self.unit_id}: states for {sorted(states)}, inlets {sorted(by_name)}"
            )
        top = states.get(TOP) if TOP in by_name else None
        bottom = states.get(BOTTOM) if BOTTOM in by_name else None
        sides = tuple(
            SideFeed(inlet.name, inlet.stage, states[inlet.name])
            for inlet in self.inlets
            if inlet.port == FEED
        )
        return ColumnSpec(
            unit_id=self.unit_id,
            stage_count=self.stage_count,
            pressures=self.pressures,
            duties=self.duties,
            condenser=self.condenser,
            reboiler=self.reboiler,
            condenser_spec=self.condenser_spec,
            reboiler_spec=self.reboiler_spec,
            top=top,
            bottom=bottom,
            sides=sides,
            components=self.components,
        )


def structural_spec(structure: ColumnStructure) -> ColumnSpec:
    """§4.7.2: the `ColumnSpec` whose inlet states are `n = (nan,)*C, T = nan, P = nan` with the
    declared phase. Only for `declared_rows(..., links=...)`, `column_solve.lifted_splits`,
    `zero_flow_forms`, `closure_types` and `split_temperatures`: none of them reads an inlet
    value."""
    nan = math.nan
    count = len(structure.components)
    return structure.spec(
        {
            inlet.name: InletState(
                n=(nan,) * count, temperature=nan, pressure=nan, phase=inlet.phase
            )
            for inlet in structure.inlets
        }
    )


# -- the parser ----------------------------------------------------------------------------------


def _integer(view: InstanceView, name: str) -> int:
    value = view.parameters[name]
    if not (math.isfinite(value) and float(value).is_integer()):
        raise RevisionError("unsupported", f"parameter_value_unsupported({view.unit_id}.{name})")
    return int(value)


def _phase_of(view: InstanceView, port: str) -> Phase:
    """An inlet's declared phase: `LIQUID` or `VAPOR`; `vapor_liquid` is `port_unsupported`."""
    phase = view.phases.get(port)
    if phase is None:
        raise RevisionError(
            "unsupported",
            f"port_unsupported({view.unit_id}.{port})",
            f"Declare the connection to {view.unit_id}.{port} phase_capability liquid or vapor: "
            "a column takes a single-phase inlet (S02 §5 R6).",
        )
    return phase


#: The end specification paths (§4.7.1): `<end>.<kind>`, `<end>.purity.<component>`,
#: `<end>.recovery.<component>`, `<end>.temperature.<stage>`.
END_PREFIXES: Final[tuple[str, ...]] = (f"{CONDENSER}.", f"{REBOILER}.")


def end_entries(view: InstanceView) -> dict[str, float]:
    """The instance's end specifications, `<end>.<kind>[.<attribute>]` → value (SI).

    Read from the instance's parameters (build decision, `docs/S11B_DECISIONS.md`: the revision
    reader routes no `condenser.*`/`reboiler.*` target path to a pin), so a `role: fixed`
    specification with target path `parameters.<end>.<kind>…` reaches it too."""
    return {name: value for name, value in view.parameters.items() if name.startswith(END_PREFIXES)}


def _end_specification(
    view: InstanceView, end: str, entries: Mapping[str, float]
) -> EndSpecification | None:
    """The one specification of `end`, or `None`; two are `specification_conflict(<U>.<end>)`.
    The kind and attribute are read as written: §5 S2 and S06 I1 judge them."""
    given = [name for name in entries if name.startswith(f"{end}.")]
    if not given:
        return None
    if len(given) > 1:
        raise RevisionError(
            "conflict",
            f"specification_conflict({view.unit_id}.{end})",
            f"Pin exactly one {end} specification; got {', '.join(sorted(given))}.",
        )
    (name,) = given
    kind, _, attribute = name.removeprefix(f"{end}.").partition(".")
    value = entries[name]
    if kind == "temperature":
        stage = int(attribute) if attribute.isdigit() else None
        if stage is None:
            raise RevisionError("unsupported", f"parameter_unsupported({view.unit_id}.{name})")
        return EndSpecification(kind, value, stage=stage)
    if kind in ("purity", "recovery"):
        return EndSpecification(kind, value, component=attribute or None)
    if attribute:
        raise RevisionError("unsupported", f"parameter_unsupported({view.unit_id}.{name})")
    return EndSpecification(kind, value)


def column_structure(view: InstanceView, components: Sequence[str]) -> ColumnStructure:
    """§4.7.2: a revision instance of `syn001.column` as a `ColumnStructure`. Pure; raises
    `RevisionError` for what the document's configuration contradicts or omits. The column's
    own refusals (S02 §5, S06 §5) are not applied here: `structural_refusal` applies the
    structural ones at bind, `column.validate` all of them at evaluate."""
    unit = view.unit_id
    if not _TOKEN.match(unit):
        # The column's property blocks are named after its id (S01's `_token`).
        raise RevisionError(
            "unsupported",
            f"id_unsupported({unit})",
            f"A {MODEL_ID} instance id names its property blocks: a letter followed by letters, "
            "digits and non-consecutive underscores (no '-').",
        )
    for port in view.ports:
        if port not in (*INLET_PORTS, *OUTLET_PORTS):
            raise RevisionError("unsupported", f"port_unsupported({unit}.{port})")
    for port in OUTLET_PORTS:
        if len(view.ports.get(port, ())) != 1:
            raise RevisionError("incomplete", f"port_unwired({unit}.{port})")
    for port in (TOP, BOTTOM):
        if len(view.ports.get(port, ())) > 1:
            raise RevisionError("unsupported", f"port_multiplicity_unsupported({unit}.{port})")

    # The ends, from the wiring and the declared phases (§4.7.1).
    distillate_phase = view.phases.get(DISTILLATE)
    if TOP in view.ports:
        if distillate_phase != "VAPOR":
            raise RevisionError(
                "conflict",
                f"specification_conflict({unit}.{DISTILLATE})",
                f"With {unit}.top connected the condenser is none and the distillate is the "
                "stage-1 vapour: declare it vapor.",
            )
        condenser = "none"
    elif distillate_phase == "VAPOR":
        condenser = "partial"
    elif distillate_phase == "LIQUID":
        condenser = "total"
    else:
        raise RevisionError(
            "unsupported",
            f"port_unsupported({unit}.{DISTILLATE})",
            f"Declare {unit}.distillate vapor (a partial condenser) or liquid (a total condenser).",
        )
    if view.phases.get(BOTTOMS) != "LIQUID":
        raise RevisionError(
            "unsupported",
            f"port_unsupported({unit}.{BOTTOMS})",
            f"Declare {unit}.bottoms liquid: it is the stage-N liquid.",
        )
    reboiler = "none" if BOTTOM in view.ports else "partial"

    # Parameters (§4.7.1).
    if STAGE_COUNT not in view.parameters:
        raise RevisionError("incomplete", f"parameter_missing({unit}.{STAGE_COUNT})")
    count = _integer(view, STAGE_COUNT)
    if count < 1:
        raise RevisionError("unsupported", f"parameter_value_unsupported({unit}.{STAGE_COUNT})")
    feeds = tuple(view.ports.get(FEED, ()))
    entries = end_entries(view)
    known = {
        STAGE_COUNT,
        *(f"{STAGE_PRESSURE}.{j}" for j in range(1, count + 1)),
        *(f"{STAGE_DUTY}.{j}" for j in range(1, count + 1)),
        *(f"{FEED_STAGE}.{stream}" for stream in feeds),
        *entries,
    }
    unknown = [name for name in view.parameters if name not in known]
    if unknown:
        raise RevisionError("unsupported", f"parameter_unsupported({unit}.{unknown[0]})")
    for j in range(1, count + 1):
        if f"{STAGE_PRESSURE}.{j}" not in view.parameters:
            raise RevisionError("incomplete", f"parameter_missing({unit}.{STAGE_PRESSURE}.{j})")
    for stream in feeds:
        if f"{FEED_STAGE}.{stream}" not in view.parameters:
            raise RevisionError("incomplete", f"parameter_missing({unit}.{FEED_STAGE}.{stream})")
    pressures = tuple(float(view.parameters[f"{STAGE_PRESSURE}.{j}"]) for j in range(1, count + 1))

    condenser_spec = _end_specification(view, CONDENSER, entries)
    reboiler_spec = _end_specification(view, REBOILER, entries)
    slot_stages = {
        stage
        for stage, present in ((1, condenser != "none"), (count, reboiler != "none"))
        if present
    }
    duties: list[float | None] = []
    for j in range(1, count + 1):
        name = f"{STAGE_DUTY}.{j}"
        if j in slot_stages:
            if name in view.parameters:
                raise RevisionError("unsupported", f"parameter_unsupported({unit}.{name})")
            duties.append(None)
        else:
            duties.append(float(view.parameters.get(name, 0.0)))

    placed: list[PlacedPort] = []
    if TOP in view.ports:
        placed.append(PlacedPort(TOP, TOP, 1, _phase_of(view, TOP), view.ports[TOP][0]))
    if BOTTOM in view.ports:
        placed.append(
            PlacedPort(BOTTOM, BOTTOM, count, _phase_of(view, BOTTOM), view.ports[BOTTOM][0])
        )
    if feeds:
        phase = _phase_of(view, FEED)
        placed.extend(
            PlacedPort(FEED, f"feed{k}", _integer(view, f"{FEED_STAGE}.{stream}"), phase, stream)
            for k, stream in enumerate(feeds, start=1)
        )
    return ColumnStructure(
        unit_id=unit,
        stage_count=count,
        condenser=condenser,
        reboiler=reboiler,
        pressures=pressures,
        duties=tuple(duties),
        condenser_spec=condenser_spec,
        reboiler_spec=reboiler_spec,
        inlets=tuple(placed),
        distillate=view.ports[DISTILLATE][0],
        bottoms=view.ports[BOTTOMS][0],
        components=tuple(components),
    )


# -- bind-time refusals (§4.7.2) -----------------------------------------------------------------


_NONE: Final = EndSpecification("none", 0.0)


def _refuse(unit: str, key: str, message: str) -> SpecificationError:
    """A structural item of S02 §5 / S06 §5 at bind: the column's own `invalid_spec(<key>)`."""
    return SpecificationError(f"{unit}: invalid_spec({key}): {message}")


def structural_refusal(structure: ColumnStructure, provider: PropertyProvider) -> None:
    """§4.7.2: the structural items of S02 §5 and S06 §5 (inventory in `docs/S11B_DECISIONS.md`),
    raised at bind: `RevisionError` for what the document's configuration leaves out or
    contradicts (an end without its specification, a specification at a `none` end, a kind the
    column or the basis does not offer), `SpecificationError` (`invalid_spec(<key>)`, the
    column's own keys) for a value. The inlet-dependent items are `column.validate`'s, at
    evaluate."""
    unit, count = structure.unit_id, structure.stage_count
    form = equilibrium_form(provider)
    composition_dependent = form is not None and form.composition_dependent
    p_bounds = form.domain["P"] if composition_dependent and form is not None else (P_MIN, P_MAX)
    # R3, the stage pressures
    for stage, value in enumerate(structure.pressures, start=1):
        if not (math.isfinite(value) and p_bounds[0] <= value <= p_bounds[1]):
            column = stage_pressure_id(unit, stage)
            raise _refuse(unit, f"domain:{column}", f"{column} = {value!r} outside {p_bounds}")
    # S2, S10-C D8, S06 I1 and I2: each end's specification
    given: dict[str, EndSpecification] = {}
    for end, kind, found in (
        (CONDENSER, structure.condenser, structure.condenser_spec),
        (REBOILER, structure.reboiler, structure.reboiler_spec),
    ):
        if kind == "none":
            if found is not None:
                raise RevisionError(
                    "conflict",
                    f"specification_conflict({unit}.{end})",
                    f"{unit} has no {end} (its {'top' if end == CONDENSER else 'bottom'} port "
                    "is connected); remove the specification.",
                )
            continue
        offered = tuple(
            k for k in END_KINDS[end] if not composition_dependent or k in GAMMA_PHI_KINDS
        )
        if found is None:
            raise RevisionError(
                "incomplete",
                f"specification_missing({unit}.{end})",
                f"Pin exactly one of {', '.join(f'{end}.{k}' for k in offered)}.",
            )
        if found.kind not in offered:
            raise RevisionError(
                "unsupported",
                f"specification_unsupported({unit}.{end}.{found.kind})",
                f"A {end} of {unit} on {_provider_id(provider)} takes {', '.join(offered)}.",
            )
        given[end] = found
    # S3
    if given.get(CONDENSER, _NONE).kind == "distillate_rate" and (
        given.get(REBOILER, _NONE).kind == "bottoms_rate"
    ):
        raise _refuse(unit, "redundant_specification", "distillate and bottoms rates together")
    for end, found in given.items():
        value = found.value
        if found.kind in INVERSE_KINDS:
            # I1, I2
            if found.kind == "temperature":
                wrong = found.stage is None or not 1 <= found.stage <= count
            else:
                wrong = found.component not in structure.components or not 0.0 < value < 1.0
            if wrong or not math.isfinite(value):
                raise _refuse(unit, f"{found.kind}:{end}", f"{end} {found.kind} = {value!r}")
            continue
        # S4
        if found.kind == "duty":
            wrong = value >= 0.0 if end == CONDENSER else value <= 0.0
        else:
            wrong = value <= 0.0
        if wrong or not math.isfinite(value):
            raise _refuse(unit, f"{found.kind}:{end}", f"{end} {found.kind} = {value!r}")
    # R4, S7
    slots = {stage for stage, duty in enumerate(structure.duties, start=1) if duty is None}
    taken: set[int] = set()
    for inlet in structure.inlets:
        if inlet.port != FEED:
            continue
        if not 1 <= inlet.stage <= count or inlet.stage in taken or inlet.stage in slots:
            raise _refuse(
                unit,
                f"side_feed_stage:{inlet.name}",
                f"side feed {inlet.name} ({inlet.stream}) at stage {inlet.stage} (N = {count}; one "
                "side feed per stage, none at a condenser or reboiler stage)",
            )
        taken.add(inlet.stage)
    # S8
    if count < 1 + len(slots):
        raise _refuse(unit, "stage_count", f"N = {count} cannot hold the condenser and reboiler")
    # S9
    for stage in range(1, count):
        if structure.pressures[stage] < structure.pressures[stage - 1]:
            raise _refuse(unit, "pressure_profile", f"P_{stage + 1}* < P_{stage}*")
    # S10's structural half: an end needs an inlet
    if slots and not structure.inlets:
        raise _refuse(unit, "no_feed", "a column with a condenser or reboiler and no inlet")


# -- the unit ------------------------------------------------------------------------------------

#: §4.7.1. `top` and `bottom` are optional: the binder requires every material port a unit
#: declares to be wired, so `ColumnUnit.ports()` declares only the ports its instance wires
#: (build decision Q7, `docs/S11B_DECISIONS.md`); this table is the model's full set.
PORTS: Final[tuple[Port, ...]] = (
    Port(
        name=FEED,
        kind="material",
        direction="inlet",
        multiplicity="many",
        component_mapping="revision_component_set",
        state_definition="nTP-v1",
        phase_capabilities=("liquid", "vapor"),
    ),
    *(
        Port(
            name=name,
            kind="material",
            direction="inlet",
            multiplicity=1,
            component_mapping="revision_component_set",
            state_definition="nTP-v1",
            phase_capabilities=("liquid", "vapor"),
        )
        for name in (TOP, BOTTOM)
    ),
    Port(
        name=DISTILLATE,
        kind="material",
        direction="outlet",
        multiplicity=1,
        component_mapping="revision_component_set",
        state_definition="nTP-v1",
        phase_capabilities=("liquid", "vapor"),
    ),
    Port(
        name=BOTTOMS,
        kind="material",
        direction="outlet",
        multiplicity=1,
        component_mapping="revision_component_set",
        state_definition="nTP-v1",
        phase_capabilities=("liquid",),
    ),
)

#: §4.7.3 item 5.
UNIT_EQUATIONS: Final[tuple[DeclaredEquation, ...]] = (
    *EQUATIONS,
    *FLOWSHEET_EQUATIONS,
)

#: §4.11's L-COL rows as the manifest states them.
LIMITATIONS: Final[tuple[str, ...]] = (
    "L-COL-1: one side feed per stage; every side feed on the `feed` port shares one declared "
    "phase (liquid or vapor); a two-phase feed needs a flash first (S02 §5 R4, R6).",
    "L-COL-2: `top` and `bottom` are optional inlets; connected, the condenser or reboiler is "
    "`none`.",
    "L-COL-3: the stage pressures are pinned instance parameters, one per stage.",
    "L-COL-4: on a composition-dependent (gamma-phi) basis the end specifications are the direct "
    "kinds only (S10-C D8).",
    "L-COL-5: evaluate runs the standalone solve_column on the inlet states; its typed refusal is "
    "the unit's failure.",
    "L-COL-6: in a flowsheet a purity's tolerance acts on x directly (F_ref = 1 mol/s), the "
    "standalone tolerance on F x (S06 §15 Q7 ruling).",
)


def _provider_id(provider: PropertyProvider) -> str:
    return provider.describe().provider_id


def _artifact_hash() -> str:
    """The module source's SHA-256; read per manifest, uncached (no process-global state)."""
    return file_sha256(Path(__file__))


def _status(outcome: str) -> PropertyStatus:
    """A column failure's outcome as a unit's status: a refusal is `unsupported`, an
    unconverged or conflicting solve `not_converged`."""
    if outcome in ("INVALID_SPECIFICATION", "CAPABILITY_UNAVAILABLE"):
        return "unsupported"
    return "not_converged"


@dataclass(frozen=True)
class ColumnUnit:
    """One `syn001.column` instance in a flowsheet (§4.7)."""

    unit_id: str
    structure: ColumnStructure
    provider: PropertyProvider
    context: EvaluationContext

    @property
    def model_id(self) -> str:
        return MODEL_ID

    @property
    def components(self) -> tuple[str, ...]:
        return self.structure.components

    def ports(self) -> tuple[Port, ...]:
        wired = {inlet.port for inlet in self.structure.inlets} | set(OUTLET_PORTS)
        return tuple(port for port in PORTS if port.name in wired)

    def declared_equations(self) -> tuple[DeclaredEquation, ...]:
        return UNIT_EQUATIONS

    def manifest(self) -> Mapping[str, Any]:
        described = self.provider.describe()
        return manifest_document(
            model_id=MODEL_ID,
            title="SYN-001 MESH column",
            description=(
                "S02/S06's MESH column embedded in a flowsheet: its own rows, link rows from the "
                "inlet streams and to the two products (S11 §4.7)."
            ),
            ports=PORTS,
            equations=UNIT_EQUATIONS,
            derivatives=(
                DerivativeDeclaration(
                    output="rows",
                    with_respect_to=("stage.l", "stage.v", "stage.T", "inlet.state", "stream"),
                    method="analytic",
                    regime="all",
                    notes="The standalone column's rows; the link rows are linear.",
                ),
            ),
            initialization=Initialization(
                strategy="registered_initializer",
                notes="evaluate runs the standalone solve_column; the EO start takes its root.",
                registered_initializer="s02-profile-cmo-v1",
            ),
            validity=Validity(
                components=self.components,
                phases=("liquid", "vapor"),
                limitations=LIMITATIONS,
                temperature_k=described.domain.get("T"),
                pressure_pa=described.domain.get("P"),
            ),
            module=__name__,
            artifact_hash=_artifact_hash(),
            execution_class="native_equation",
            thread_safety="thread_safe",
            evaluation_cost_class="expensive",
            property_provider=described.provider_id,
            reference_convention=described.reference_convention,
        )

    def _check(self, wiring: Wiring) -> None:
        for inlet_port in INLET_PORTS:
            expected = tuple(i.stream for i in self.structure.inlets if i.port == inlet_port)
            if tuple(wiring.streams.get(inlet_port, ())) != expected:
                raise SpecificationError(
                    f"{self.unit_id}: port {inlet_port!r} wired to "
                    f"{list(wiring.streams.get(inlet_port, ()))}, built for {list(expected)}"
                )
        if (wiring.one(DISTILLATE), wiring.one(BOTTOMS)) != (
            self.structure.distillate,
            self.structure.bottoms,
        ):
            raise SpecificationError(f"{self.unit_id}: products rewired since the build")

    def contribute(self, wiring: Wiring, components: Sequence[str]) -> Contribution:
        """§4.7.3: S02/S06's rows on the structural spec, with the flowsheet's links."""
        self._check(wiring)
        if tuple(components) != self.components:
            raise SpecificationError(f"{self.unit_id}: components {list(components)}")
        return declared_rows(
            structural_spec(self.structure),
            self.provider,
            self.context,
            links=self.structure.links(),
        )

    def evaluate(
        self, inlets: Mapping[str, Sequence[StreamState]], context: EvaluationContext
    ) -> UnitEvaluation:
        """§4.7.5: the standalone `solve_column` on the inlet states."""
        described = self.provider.describe()
        states: dict[str, InletState] = {}
        position: dict[str, int] = {}
        for inlet in self.structure.inlets:
            index = position.get(inlet.port, 0)
            position[inlet.port] = index + 1
            connected = tuple(inlets.get(inlet.port, ()))
            if index >= len(connected):
                raise SpecificationError(f"{self.unit_id}: no stream at {inlet.port}[{index}]")
            stream = connected[index]
            checked = port_enthalpy(
                self.provider, stream, inlet.phase, self.components, context, port=inlet.port
            )
            if checked.failure is not None:
                return replace(checked.failure, reference_convention=described.reference_convention)
            states[inlet.name] = InletState(
                n=tuple(stream.n),
                temperature=stream.temperature,
                pressure=stream.pressure,
                phase=inlet.phase,
            )
        spec = self.structure.spec(states)
        answer = solve_column(spec, self.provider)
        if isinstance(answer, CascadeFailure):
            return self._failure(_status(answer.outcome), answer.cause, answer.message)
        if answer.outcome != "CONVERGED":
            return self._failure("not_converged", str(answer.cause), "")
        state = answer.state
        flows = products(spec, state)
        count = spec.stage_count
        outlets = {
            DISTILLATE: StreamState(
                n=flows[DISTILLATE],
                temperature=float(state[stage_temperature_id(self.unit_id, 1)]),
                pressure=float(state[stage_pressure_id(self.unit_id, 1)]),
            ),
            BOTTOMS: StreamState(
                n=flows[BOTTOMS],
                temperature=float(state[stage_temperature_id(self.unit_id, count)]),
                pressure=float(state[stage_pressure_id(self.unit_id, count)]),
            ),
        }
        return UnitEvaluation(
            status="ok",
            outlets=outlets,
            duty=None,
            phase_signature=None,
            iterations=answer.result.iterations if isinstance(answer, ColumnSolution) else 0,
            provider_id=described.provider_id,
            reference_convention=described.reference_convention,
            message="",
            owned=self._owned(spec, state),
        )

    def _failure(self, status: PropertyStatus, cause: str, detail: str) -> UnitEvaluation:
        failed = typed_failure(status, cause, detail)
        return replace(failed, reference_convention=self.provider.describe().reference_convention)

    def _owned(self, spec: ColumnSpec, state: Mapping[str, float]) -> dict[str, float]:
        """§4.7.5: every owned column of the flowsheet face; the standalone ones from the
        solution, `u = fl(n_c/P)` and `w = fl(n_c/F_c)` (F_ref = 1) for the inverse ends."""
        unit = self.unit_id
        owned: dict[str, float] = {}
        flowsheet_only: dict[str, float] = {}
        for end in spec.ends():
            given = spec.end_specification(end)
            assert given is not None
            stage = spec.end_stage(end)
            if given.kind not in COMPONENT_KINDS:
                continue
            assert given.component is not None
            flow = float(state[product_flow_id(spec, end, given.component)])
            if given.kind == "purity":
                flowsheet_only[purity_flow_id(unit, stage)] = (
                    F_REF * flow / float(state[product_total_id(spec, end)])
                )
            else:
                total = 0.0
                for k, inlet in enumerate(spec.inlets()):
                    value = float(state[flow_id(inlet_stream(unit, inlet.port), given.component)])
                    total = value if k == 0 else total + value
                flowsheet_only[recovery_flow_id(unit, stage)] = F_REF * flow / total
        for name in self.contribute_ids():
            owned[name] = flowsheet_only[name] if name in flowsheet_only else float(state[name])
        return owned

    def contribute_ids(self) -> tuple[str, ...]:
        return declared_rows(
            structural_spec(self.structure),
            self.provider,
            self.context,
            links=self.structure.links(),
        ).variable_ids
