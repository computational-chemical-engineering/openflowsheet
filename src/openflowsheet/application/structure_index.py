"""`inspect_structure`'s row and column index (M06 design note §4.1; ADR 0019 Amendment 3, A3.1).

What the equation view and the degrees-of-freedom screen read: for every row of the traced
declaration its authoring unit and instance, its role, the revision specification it realises, its
kind and SI unit and its incidence; for every column its kind and SI unit, its owner, the connection
whose declared state it is and, on a `nTP-v1` connection, its coordinate.

**Pure, and from the same objects as the report.** The caller passes the `Declaration` and the
`ProcessGraph` that produced the structural report of that call, the binding they came from and the
revision document; nothing is traced, bound or analysed here. The index sits beside
`structural_report` in the document, never inside it, so `structural_sha256` and R0 cannot move.

**No member is parsed from an id** (R-019). Owners, instances and connections are the graph's;
roles are `TracedRow.is_specification_row`, the predicate `unit_degrees_of_freedom` uses; a
coordinate is the column's position in its connection's `state_columns` under ADR 0001 D1.1's
`(n, T, P)` order (`_coordinates`, the one place that rule lives).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Final

from openflowsheet.application.binding import Binding
from openflowsheet.application.revision_binding import RevisionBinding, specification_rows
from openflowsheet.graph.process import ProcessGraph
from openflowsheet.graph.trace import Declaration
from openflowsheet.units import KIND_SI_UNITS

__all__ = ["structure_index"]

#: The state definition whose `state_columns` the positional rule reads (ADR 0001 D1.1).
_NTP: Final = "nTP-v1"


def _si_unit(kind: str | None) -> str | None:
    """`models.revision_flowsheet.si_unit(kind)` when `kind` is known to it, else `None`."""
    return KIND_SI_UNITS.get(kind) if kind is not None else None


def _state_definitions(revision: Mapping[str, Any]) -> dict[str, Any]:
    """Connection id -> its `state_definition`, for the ids that name exactly one connection."""
    seen: dict[str, list[Any]] = {}
    for entry in revision.get("connections") or ():
        if isinstance(entry, Mapping) and isinstance(entry.get("id"), str):
            seen.setdefault(entry["id"], []).append(entry.get("state_definition"))
    return {stream: values[0] for stream, values in seen.items() if len(values) == 1}


def _coordinates(
    graph: ProcessGraph, revision: Mapping[str, Any], components: Sequence[str]
) -> dict[str, tuple[str, str | None]]:
    """Column id -> `(coordinate, component)`: on a connection whose revision `state_definition`
    is `nTP-v1` and whose `state_columns` has `N_c + 2` members, position `i < N_c` is
    `("n", components[i])`, `N_c` is `("T", None)` and `N_c + 1` is `("P", None)`."""
    definitions = _state_definitions(revision)
    count = len(components)
    named: dict[str, tuple[str, str | None]] = {}
    for connection in graph.connections:
        columns = connection.state_columns
        if definitions.get(connection.stream_id) != _NTP or len(columns) != count + 2:
            continue
        for position, column in enumerate(columns):
            if position < count:
                named[column] = ("n", components[position])
            else:
                named[column] = ("T" if position == count else "P", None)
    return named


def structure_index(
    declaration: Declaration,
    graph: ProcessGraph,
    binding: Binding | RevisionBinding,
    revision: Mapping[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    """`{"rows": [RowEntry, ...], "columns": [ColumnEntry, ...]}` in `declaration.row_ids` and
    `declaration.column_ids` order (design note §4.1's tables; every member always present).

    A row's `specification_id` is the legacy binder's `specification_ids` on a `Binding`, and the
    revision binder's attribution (`specification_rows`) on a `RevisionBinding`."""
    named = (
        specification_rows(binding, declaration)
        if isinstance(binding, RevisionBinding)
        else dict(binding.specification_ids)
    )
    rows = []
    for row_id in declaration.row_ids:
        row = declaration.rows[row_id]
        rows.append(
            {
                "row_id": row_id,
                "unit_id": row.unit,
                "instance_id": None if row.unit is None else graph.instance_ids.get(row.unit),
                "role": "specification" if row.is_specification_row else "model",
                "specification_id": named.get(row_id),
                "kind": row.kind,
                "si_unit": _si_unit(row.kind),
                "columns": list(row.columns),
            }
        )

    connections = {
        column: connection.stream_id
        for connection in reversed(graph.connections)
        for column in connection.state_columns
    }
    coordinates = _coordinates(graph, revision, binding.flowsheet.components)
    columns = []
    for column_id in declaration.column_ids:
        kind = declaration.column_kinds.get(column_id)
        owner = graph.column_owners.get(column_id)
        coordinate, component = coordinates.get(column_id, (None, None))
        columns.append(
            {
                "column_id": column_id,
                "kind": kind,
                "si_unit": _si_unit(kind),
                "owner_unit": owner,
                "owner_instance": None if owner is None else graph.instance_ids.get(owner),
                "connection": connections.get(column_id),
                "coordinate": coordinate,
                "component": component,
            }
        )
    return {"rows": rows, "columns": columns}
