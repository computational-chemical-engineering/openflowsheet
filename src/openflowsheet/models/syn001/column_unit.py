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
from dataclasses import dataclass
from typing import Final

from openflowsheet.models.revision_flowsheet import InstanceView, RevisionError
from openflowsheet.models.syn001.cascade import BOTTOM, TOP, InletState, SideFeed
from openflowsheet.models.syn001.column import (
    CONDENSER,
    REBOILER,
    ColumnSpec,
    EndSpecification,
    FlowsheetLinks,
)
from openflowsheet.thermo import Phase

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
