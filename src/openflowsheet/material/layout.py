"""The material layout (ADR 0062 D8): where each connection's variables sit in the state vector.

`MaterialLayout.build` is called once, at validation, with the revision's connections (each with its
definition instance and `definition_sha256`), the facts of its components and attribute kinds, and
the problem's variable order. Per connection it records, in D3's carried-index order of the
normalised instance, one `Slot` per variable (`substream`, `field`, `index`, `quantity_kind`,
`variable_index`), and per substream its molar masses (M, M_g for groups, M = 1 for a `kg`-basis
component, a class its component's) and its carried slots (the dormancy partition, D4). Each slot's
`variable_index` is the position of its rendered id (D7) in the variable order; that lookup is the
only place an id is used, and it renders, never parses. After it, `layout.state(x, connection)`
reads by index alone (E-F2-6).

D3's order, per connection: for each substream (instance order) its carried amounts (for each
component in definition order its parent amount, or the classes of the partition attribute that
targets it, ascending; for a group basis the groups, by id, in place of the species), then its
non-partition attributes (attribute order, then component order, then class order); after the last
substream the stream fields once: `h` (or `T`, by the thermal coordinate), then `P`. `nTP-v1` is
today's order (flows, T, P) with today's ids; `heat-v1`, `work-v1` and `signal-v1` have one slot,
`~Q`, `~W`, `~s`.

`document()` is `solution-state-v2`'s `material_layout`: the slots without `variable_index` (the
document's `variable_ids` order gives it) and without the molar masses, which are floats and stay
out of R0 (D8).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final, Protocol, SupportsFloat

from openflowsheet.material.basis import group_molar_masses
from openflowsheet.material.definitions import LEGACY_TEMPLATE, normalise_instance, species_basis
from openflowsheet.material.vid import VariableId, legacy_variable_id
from openflowsheet.registry.tokens import Coded

__all__ = [
    "AttributeKind",
    "ComponentFacts",
    "ConnectionInput",
    "ConnectionLayout",
    "LayoutRefusalError",
    "MaterialFacts",
    "MaterialLayout",
    "MaterialState",
    "Slot",
    "SubstreamLayout",
    "SubstreamState",
    "Vector",
    "draft_connection",
]

#: The carried amount's quantity kind per component amount basis (ADR 0061, ADR 0062 D1).
FLOW_KIND: Final = {"mol": "molar_flow", "kg": "mass_flow", "segment_mol": "segment_molar_flow"}
#: The thermal field and its kind per thermal coordinate (D3, D11).
THERMAL: Final = {"h_mass": ("h", "specific_enthalpy"), "T": ("T", "temperature")}
#: The one slot of an energy or signal connection (D3's table; `signal-v1` takes its kind from the
#: instance).
SINGLE: Final = {"heat-v1": ("Q", "heat_rate"), "work-v1": ("W", "power"), "signal-v1": ("s", "")}


class LayoutRefusalError(ValueError):
    """A definition the layout cannot place, for a reason ADR 0062's catalogue names (F2-WO4):
    `coded` is the typed refusal the revision validator reports for the same definition first
    (`attribute_grid_mismatch`, `attribute_redundant`). The layout's other refusals stay plain
    `ValueError`s (F2 decision WO3-6)."""

    def __init__(self, coded: Coded, message: str) -> None:
        super().__init__(message)
        self.coded = coded


@dataclass(frozen=True, slots=True)
class ComponentFacts:
    """What the layout reads of a component's record (ADR 0061): its amount basis and molar mass
    (kg per mol or per segment mol; `None` for a `kg`-basis component, whose M is 1, D4) and its
    charge (for a group basis's M_g, Q3.R7)."""

    amount_basis: str
    molar_mass: float | None
    charge: int = 0


@dataclass(frozen=True, slots=True)
class AttributeKind:
    """What the layout reads of an `attribute_kind` descriptor's payload (D5)."""

    scope: str
    partition: bool
    classed: bool
    quantity_kind: str


@dataclass(frozen=True, slots=True)
class MaterialFacts:
    """The revision's facts the layout needs: the component-set order (`nTP-v1`'s one substream),
    each component's facts, and each attribute kind's by id."""

    components: tuple[str, ...]
    component_facts: Mapping[str, ComponentFacts]
    attribute_kinds: Mapping[str, AttributeKind]


@dataclass(frozen=True, slots=True)
class ConnectionInput:
    """One connection of the revision: its id, its `definition` reference (D11), its definition
    instance (D3) and that instance's `definition_sha256`."""

    connection: str
    definition: str
    instance: Mapping[str, Any]
    definition_sha256: str


@dataclass(frozen=True, slots=True)
class Slot:
    """One variable of a connection (D8). `index` holds ids and 1-based class indices (`int`)."""

    substream: str | None
    field: str
    index: tuple[str | int, ...]
    quantity_kind: str
    variable_index: int

    def document(self) -> dict[str, Any]:
        """The slot as `material_layout` records it: without `variable_index`."""
        return {
            "substream": self.substream,
            "field": self.field,
            "index": list(self.index),
            "quantity_kind": self.quantity_kind,
        }


@dataclass(frozen=True, slots=True)
class SubstreamLayout:
    """One substream: its carried slots (positions in the connection's `slots`, the dormancy
    partition), its non-partition attribute slots, and M per carried slot."""

    substream: str
    kind: str
    carried: tuple[int, ...]
    attributes: tuple[int, ...]
    molar_masses: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class ConnectionLayout:
    """One connection's part of the layout."""

    connection: str
    definition: str
    definition_sha256: str
    template: str
    thermal_coordinate: str | None
    slots: tuple[Slot, ...]
    substreams: tuple[SubstreamLayout, ...]

    def variable_id(self, slot: Slot) -> str:
        """`slot`'s id (D7), rendered; an `nTP-v1` connection's are today's ids."""
        if self.template == LEGACY_TEMPLATE:
            component = None if slot.substream is None else str(slot.index[0])
            return legacy_variable_id(self.connection, slot.field, component)
        index = tuple(str(part) for part in slot.index)
        return VariableId((self.connection,), slot.field, index, slot.substream).render()

    def document(self) -> dict[str, Any]:
        return {
            "connection": self.connection,
            "definition": self.definition,
            "definition_sha256": self.definition_sha256,
            "slots": [slot.document() for slot in self.slots],
        }


@dataclass(frozen=True, slots=True)
class SubstreamState:
    """One substream of a material state: its carried amounts and its non-partition attribute
    values, each in the layout's order."""

    substream: str
    carried: tuple[float, ...]
    attributes: tuple[float, ...]

    @property
    def is_dormant(self) -> bool:
        """D4: every carried amount is zero (`-0.0 == 0.0`, so signed zeros count as zero)."""
        return all(amount == 0.0 for amount in self.carried)


@dataclass(frozen=True, slots=True)
class MaterialState:
    """A material connection's state, read from the state vector by the layout (D8):
    its substreams, the thermal coordinate's value (`h` in J/kg or `T` in K) and `P` in Pa."""

    connection: str
    definition_sha256: str
    thermal_coordinate: str
    substreams: tuple[SubstreamState, ...]
    thermal: float
    pressure: float

    @property
    def is_dormant(self) -> bool:
        """D4: a stream is dormant iff all its substreams are."""
        return all(substream.is_dormant for substream in self.substreams)


class Vector(Protocol):
    """A state vector: anything indexable by position to a float (a list, a numpy array)."""

    def __getitem__(self, index: int, /) -> SupportsFloat: ...


class _Slots:
    """A connection's slots under construction, with their quantity kinds; indices come last."""

    def __init__(self) -> None:
        self.entries: list[tuple[str | None, str, tuple[str | int, ...], str]] = []

    def add(
        self, substream: str | None, field: str, index: tuple[str | int, ...], kind: str
    ) -> int:
        self.entries.append((substream, field, index, kind))
        return len(self.entries) - 1


def _index(*parts: str | int | None) -> tuple[str | int, ...]:
    """A slot index from its parts, the absent ones (`None`) left out."""
    return tuple(part for part in parts if part is not None)


def _molar_mass(facts: MaterialFacts, component: str) -> float:
    found = facts.component_facts[component]
    if found.amount_basis == "kg":
        return 1.0
    if found.molar_mass is None:
        raise ValueError(f"component {component!r} ({found.amount_basis}) has no molar mass")
    return found.molar_mass


def _flow_kind(facts: MaterialFacts, component: str) -> str:
    return FLOW_KIND[facts.component_facts[component].amount_basis]


def _ntp_substream(facts: MaterialFacts, slots: _Slots) -> SubstreamLayout:
    carried = tuple(slots.add("mixed", "n", (c,), "molar_flow") for c in facts.components)
    masses = tuple(_molar_mass(facts, c) for c in facts.components)
    return SubstreamLayout("mixed", "mixed", carried, (), masses)


def _mat_substream(
    substream: Mapping[str, Any], facts: MaterialFacts, slots: _Slots, definition: str
) -> SubstreamLayout:
    """One `mat-v1` substream of the normalised instance, in D3's order."""
    sid: str = substream["id"]

    def refusal(code: str, kind: str, message: str) -> LayoutRefusalError:
        params = {"definition": definition, "substream": sid, "kind": kind}
        return LayoutRefusalError(Coded(code, params), f"{sid}: {message}")

    components: list[str] = list(substream["components"])
    grids = {grid["id"]: len(grid["edges"]) - 1 for grid in substream["grids"]}

    def classes(attribute: Mapping[str, Any], kind: AttributeKind) -> tuple[int, ...]:
        if not kind.classed:
            return ()
        if attribute["grid"] not in grids:
            message = f"attribute {attribute['kind']!r} has no grid of its substream"
            raise refusal("attribute_grid_mismatch", attribute["kind"], message)
        return tuple(range(1, grids[attribute["grid"]] + 1))

    partitioned: dict[str, tuple[int, ...]] = {}
    others: list[tuple[Mapping[str, Any], AttributeKind]] = []
    for attribute in substream["attributes"]:
        kind = facts.attribute_kinds[attribute["kind"]]
        if not kind.partition:
            others.append((attribute, kind))
            continue
        if attribute["components"] is None or not kind.classed:
            raise ValueError(f"{sid}: partition attribute {attribute['kind']!r} names no classes")
        for component in attribute["components"]:
            if component in partitioned:
                message = f"{component!r} is in two partition attributes"
                raise refusal("attribute_redundant", attribute["kind"], message)
            if component not in components:
                raise ValueError(f"{sid}: {component!r} is not one partitionable component")
            partitioned[component] = classes(attribute, kind)

    carried: list[int] = []
    masses: list[float] = []
    basis = substream["conserved_basis"]
    if "groups" in basis:
        if set(basis["species"]) != set(components) or partitioned:
            raise ValueError(f"{sid}: a group basis replaces exactly the substream's components")
        charges = {c: facts.component_facts[c].charge for c in components}
        group_masses = group_molar_masses(
            species_basis(substream, charges),
            [_molar_mass(facts, s) for s in basis["species"]],
        ).group_masses
        for group, mass in zip(basis["groups"], group_masses, strict=True):
            carried.append(slots.add(sid, "n", (group["id"],), "molar_flow"))
            masses.append(mass)
    else:
        for component in components:
            flow = _flow_kind(facts, component)
            mass = _molar_mass(facts, component)
            for index in partitioned.get(component, ()) or (None,):
                carried.append(slots.add(sid, "n", _index(component, index), flow))
                masses.append(mass)

    attributes: list[int] = []
    for attribute, kind in others:
        named = attribute["components"]
        targets: list[str | None] = (
            [None] if named is None else [c for c in components if c in set(named)]
        )
        if named is not None and len(targets) != len(named):
            raise ValueError(f"{sid}: attribute {attribute['kind']!r} names a foreign component")
        for component in targets:
            for index in classes(attribute, kind) or (None,):
                where = _index(attribute["kind"], component, index)
                attributes.append(slots.add(sid, "a", where, kind.quantity_kind))
    return SubstreamLayout(sid, substream["kind"], tuple(carried), tuple(attributes), tuple(masses))


def draft_connection(given: ConnectionInput, facts: MaterialFacts) -> ConnectionLayout:
    """`given`'s layout before placement: its slots in D3's order, each with `variable_index`
    -1. The validator (F2-WO4) renders a connection's ids from it (`variable_id`), never parses
    one; `MaterialLayout.build` places it in a variable order."""
    instance = normalise_instance(given.instance)
    template: str = instance["template"]
    slots = _Slots()
    substreams: tuple[SubstreamLayout, ...] = ()
    thermal: str | None = None
    if template == LEGACY_TEMPLATE:
        thermal = "T"
        substreams = (_ntp_substream(facts, slots),)
    elif template == "mat-v1":
        thermal = instance["thermal_coordinate"]
        substreams = tuple(
            _mat_substream(s, facts, slots, given.definition) for s in instance["substreams"]
        )
    elif template in SINGLE:
        field, kind = SINGLE[template]
        slots.add(None, field, (), kind or instance["quantity_kind"])
    else:
        raise ValueError(f"{given.connection}: template {template!r} is not one of D3's")
    if thermal is not None:
        field, kind = THERMAL[thermal]
        slots.add(None, field, (), kind)
        slots.add(None, "P", (), "pressure")
    return ConnectionLayout(
        given.connection,
        given.definition,
        given.definition_sha256,
        template,
        thermal,
        tuple(Slot(s, f, i, k, -1) for s, f, i, k in slots.entries),
        substreams,
    )


def _connection(
    given: ConnectionInput, facts: MaterialFacts, positions: Mapping[str, int]
) -> ConnectionLayout:
    draft = draft_connection(given, facts)
    placed = []
    for slot in draft.slots:
        vid = draft.variable_id(slot)
        if vid not in positions:
            raise ValueError(f"{given.connection}: variable {vid!r} is not in the variable order")
        placed.append(
            Slot(slot.substream, slot.field, slot.index, slot.quantity_kind, positions[vid])
        )
    return ConnectionLayout(
        draft.connection,
        draft.definition,
        draft.definition_sha256,
        draft.template,
        draft.thermal_coordinate,
        tuple(placed),
        draft.substreams,
    )


class MaterialLayout:
    """Every connection's slots and substreams (D8), built once and immutable after."""

    __slots__ = ("_connections",)

    def __init__(self, connections: Sequence[ConnectionLayout]) -> None:
        self._connections: Mapping[str, ConnectionLayout] = {c.connection: c for c in connections}
        if len(self._connections) != len(connections):
            raise ValueError("a connection is laid out once")
        indices = [slot.variable_index for c in connections for slot in c.slots]
        if len(set(indices)) != len(indices):
            raise ValueError("two slots of the layout share a variable")

    @classmethod
    def build(
        cls,
        connections: Sequence[ConnectionInput],
        facts: MaterialFacts,
        variable_ids: Sequence[str],
    ) -> MaterialLayout:
        """The layout of `connections` in the problem whose variables are `variable_ids` (in the
        state vector's order). `ValueError` if a slot's variable is not among them, two slots share
        one, or a definition is outside what the layout can place (the validator's refusals,
        F2-WO4, come first)."""
        positions = {vid: i for i, vid in enumerate(variable_ids)}
        if len(positions) != len(variable_ids):
            raise ValueError("variable_ids holds an id twice")
        return cls([_connection(given, facts, positions) for given in connections])

    @property
    def connections(self) -> tuple[ConnectionLayout, ...]:
        return tuple(self._connections.values())

    def connection(self, connection: str) -> ConnectionLayout:
        return self._connections[connection]

    def state(self, x: Vector, connection: str) -> MaterialState:
        """The material state of `connection` in `x`, read by index (D8)."""
        layout = self._connections[connection]
        if layout.thermal_coordinate is None:
            raise ValueError(f"{connection} is not a material connection")
        slots = layout.slots

        def read(positions: tuple[int, ...]) -> tuple[float, ...]:
            return tuple(float(x[slots[p].variable_index]) for p in positions)

        return MaterialState(
            connection,
            layout.definition_sha256,
            layout.thermal_coordinate,
            tuple(
                SubstreamState(s.substream, read(s.carried), read(s.attributes))
                for s in layout.substreams
            ),
            float(x[slots[-2].variable_index]),
            float(x[slots[-1].variable_index]),
        )

    def thermal_substreams(self, x: Vector, connection: str) -> tuple[str, ...]:
        """The substreams whose models fix `connection`'s T in `x` (Q8.R5, R6; E-F2-8's Q8.A4):
        the flowing substreams in instance order, `()` when the stream is dormant (its T is
        undefined, D4). D3 carries one `h` per connection, the mass-weighted mean, so T solves
        ṁĥ = Σ_s ṁ_s ĥ_s(T, P) over these jointly (Q8.R6: "fixed by the flowing substreams");
        Q8.A4 is the case of one."""
        state = self.state(x, connection)
        return tuple(found.substream for found in state.substreams if not found.is_dormant)

    def value(self, x: Vector, connection: str) -> float:
        """The one value of an energy or signal connection in `x` (`~Q`, `~W`, `~s`)."""
        layout = self._connections[connection]
        if layout.template not in SINGLE:
            raise ValueError(f"{connection} is not an energy or signal connection")
        return float(x[layout.slots[0].variable_index])

    def document(self) -> list[dict[str, Any]]:
        """`solution-state-v2`'s `material_layout` (D8)."""
        return [c.document() for c in self._connections.values()]
