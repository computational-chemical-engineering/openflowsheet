"""The process multigraph: units, material connections, and who owns which column.

T01 specification §3.1. One node per model instance, one directed edge per material connection
from producer to consumer, in the revision's connection order. SYN-001 has only material edges.

The graph is what makes **column ownership** a fact rather than a guess: a stream column belongs
to the unit that *produces* its stream (`S3.vap.A` is the heater's, because the heater produces
a stream), and a unit-named column belongs to that unit. Ownership is what
§8.3's unit-local degree-of-freedom count is taken over, and that count is what names the heater
in the over-specified case — the Dulmage-Mendelsohn partition alone cannot, because after
certificates the conflicting revision's over-determined part holds ten specification rows and
relaxing any one of them closes the system.

Increment 1 uses the graph only for ownership. The loops, cycle edges and boundary distances are
carried here because they are the same data, and increment 2's tear rule reads them.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

__all__ = ["Connection", "ProcessGraph"]


@dataclass(frozen=True)
class Connection:
    """One material edge, producer to consumer, carrying the stream whose columns it owns."""

    stream_id: str
    producer: str
    consumer: str
    #: The columns of the stream's *declared state* — for a `nTP-v1` connection the component
    #: molar flows, the temperature and the pressure (ADR 0001 D2.1). Lifted columns are not
    #: here: ADR 0001 D2.5 makes a lifted split a reconstructable result, never a tear variable.
    #: The binding fills this from the connection's `state_definition` and the component set, so
    #: the graph layer never has to know a coordinate naming convention.
    state_columns: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProcessGraph:
    """Units and material edges, with the revision instance id each unit was bound from."""

    units: tuple[str, ...]
    connections: tuple[Connection, ...]
    #: Compiled unit id -> the `ProcessRevision` instance id, for naming objects in a report.
    #: A finding names what the user wrote, not what the assembler called it.
    instance_ids: Mapping[str, str]
    #: Column id -> the unit that owns it, **given by the caller**. An earlier version derived
    #: this by splitting the id on its first dot; A15's relabelling preserves a dot, so the test
    #: could not see it, but register R-019 says this layer parses no id and that version did
    #: (should-fix S4 of the Fable review of T01).
    column_owners: Mapping[str, str] = field(default_factory=dict)

    def producer_of(self, stream_id: str) -> str | None:
        for connection in self.connections:
            if connection.stream_id == stream_id:
                return connection.producer
        return None

    def column_owner(self, column_id: str) -> str | None:
        """Who owns this column, from the map the caller supplied. Nothing is inferred."""
        return self.column_owners.get(column_id)

    def owners_of(self, column_ids: Sequence[str]) -> dict[str, str | None]:
        return {column: self.column_owner(column) for column in column_ids}

    def boundary_units(self) -> tuple[str, ...]:
        """Units with no material inlet. SYN-001 has one, the feed."""
        consumers = {connection.consumer for connection in self.connections}
        return tuple(unit for unit in self.units if unit not in consumers)

    def instance_of(self, unit_id: str) -> str:
        return self.instance_ids.get(unit_id, unit_id)
