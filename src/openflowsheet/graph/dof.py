"""Unit-local degrees of freedom: the layer that names the over-specified unit.

T01 specification §8.3, and the finding that made it necessary. The Dulmage-Mendelsohn partition
says *how many* equations are in excess and which ones could be the ones left out; it cannot say
*which unit is wrong*, because after certificates the conflicting SYN-001 revision's
over-determined part holds ten specification rows and relaxing **any one** of them closes the
system. Relaxing the feed temperature would close it too. That is blueprint [A02]'s cross-unit
design specification seen from the other side, and it is why statement S4 says the candidate list
is complete and not minimal.

So the report carries a second, independent count. For each unit, with its inlets treated as known
and the certified rows removed:

    dof_u = |columns u owns| - structural rank of u's own model rows over those columns

against `specs_u`, the specification rows targeting those columns whoever wrote them. A unit with
more specifications than degrees of freedom is over-specified, and that is a statement about the
unit's own declaration. In the conflicting revision exactly one unit qualifies: the heater, with
two specifications against one degree of freedom.

The two layers are tied together by a bookkeeping identity that holds by construction and is
asserted rather than assumed:

    sum(specs_u) + sum(local excess) - sum(dof_u) = excess - deficit

`local excess` is a unit's own over-determination with its inlets known — the mixer's two pressure
equalities are one constraint on *its inlets* (ADR 0001 D4.5), not a defect, and the identity
would not balance if they were silently dropped.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from openflowsheet.graph.matching import DulmageMendelsohn, dulmage_mendelsohn
from openflowsheet.graph.process import ProcessGraph
from openflowsheet.graph.trace import Declaration

__all__ = ["UnitDegreesOfFreedom", "unit_degrees_of_freedom"]


@dataclass(frozen=True)
class UnitDegreesOfFreedom:
    """One unit's local count. `over_specified` is the finding; the rest is the evidence for it."""

    unit_id: str
    instance_id: str
    columns: tuple[str, ...]
    model_rows: tuple[str, ...]
    model_rank: int
    degrees_of_freedom: int
    specification_rows: tuple[str, ...]
    #: Rows over-determining the unit's own columns with its inlets known — a constraint the unit
    #: places on what feeds it, not a defect (ADR 0001 D4.5).
    local_excess_rows: tuple[str, ...]
    #: `|R+| - |C+|` of that local partition: how many constraints the unit places on its inlets.
    #: The *count*, not the row list, is what the bookkeeping identity of the module docstring
    #: adds up; two rows over one column are one constraint.
    local_excess: int

    @property
    def specifications(self) -> int:
        return len(self.specification_rows)

    @property
    def over_specified(self) -> bool:
        return self.specifications > self.degrees_of_freedom

    def as_document(self) -> dict[str, object]:
        return {
            "unit_id": self.unit_id,
            "instance_id": self.instance_id,
            "columns": len(self.columns),
            "model_rank": self.model_rank,
            "degrees_of_freedom": self.degrees_of_freedom,
            "specifications": self.specifications,
            "specification_rows": list(self.specification_rows),
            "local_excess_rows": list(self.local_excess_rows),
            "local_excess": self.local_excess,
            "over_specified": self.over_specified,
        }


def unit_degrees_of_freedom(
    declaration: Declaration,
    graph: ProcessGraph,
    *,
    retained_rows: Sequence[str],
) -> tuple[UnitDegreesOfFreedom, ...]:
    """§8.3's table, over the rows left after certified redundancy is removed."""
    owners = graph.owners_of(declaration.column_ids)
    owned: dict[str, list[str]] = {unit: [] for unit in graph.units}
    for column, unit in owners.items():
        if unit in owned:
            owned[unit].append(column)

    kept = [row_id for row_id in retained_rows]
    results: list[UnitDegreesOfFreedom] = []
    for unit in graph.units:
        columns = tuple(owned[unit])
        inside = set(columns)
        model_rows: list[str] = []
        specification_rows: list[str] = []
        for row_id in kept:
            row = declaration.rows[row_id]
            touched = inside.intersection(row.columns)
            if not touched:
                continue
            if row.is_specification_row:
                specification_rows.append(row_id)
            elif row.unit == unit:
                model_rows.append(row_id)

        local = _local_partition(declaration, model_rows, columns)
        rank = local.structural_rank
        results.append(
            UnitDegreesOfFreedom(
                unit_id=unit,
                instance_id=graph.instance_of(unit),
                columns=columns,
                model_rows=tuple(model_rows),
                model_rank=rank,
                degrees_of_freedom=len(columns) - rank,
                specification_rows=tuple(specification_rows),
                local_excess_rows=local.over_rows,
                local_excess=local.excess,
            )
        )
    return tuple(results)


def _local_partition(
    declaration: Declaration, model_rows: Sequence[str], columns: Sequence[str]
) -> DulmageMendelsohn:
    inside = set(columns)
    incidence: Mapping[str, frozenset[str]] = {
        row_id: frozenset(inside.intersection(declaration.rows[row_id].columns))
        for row_id in model_rows
    }
    return dulmage_mendelsohn(list(model_rows), list(columns), incidence)
