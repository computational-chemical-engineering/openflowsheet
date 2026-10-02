"""Process loops, tear candidates, the inner system, and the attempt-signature rule.

T01 specification §9. The obligation this discharges is plan §3.2's: SYN-001's tear is three
variables and not five, and **T01 must rediscover that from the incidence graph** rather than read
it from the flowsheet module. So nothing here knows what a flash is, what a recycle is, or which
stream SYN-001 tears; assertion A15 relabels every id in the declaration and requires the image of
the registered answer, and greps this package for the literal ids.

**Where "three, not five" comes from (§9.1).** A stream carries five `nTP-v1` coordinates. Three of
them lie in a non-singleton block of the square block-triangular form — they are genuinely coupled
— and the other two are singleton blocks that nothing in the loop feeds back into. That is a
structural fact about the declaration, read without knowing that the two are a temperature and a
pressure fixed by an isothermal flash.

**The score and its tie chain (§9.3).** Least tear dimension first; then least *consumer boundary
distance*, the number of material edges from a boundary unit to the unit that consumes the torn
stream, because that is the unit a traversal can evaluate first once the stream is guessed; then
the connection's declaration order. Each step is a minimum over a finite non-empty set with an
integer key and the last key is injective, so the chain always ends in one candidate. Which step
decided is recorded, so a reader can see whether the answer rested on the tie-break or on the
score.

**The signature rule (§9.6).** K03 §9.1 left the general rule to T01 and declared the instance.
A phase-selecting unit — one that declares an equilibrium row, which the `molar_flow_squared`
row kind marks — belongs in the attempt signature exactly when its lifted block is an ancestor of
a block the tear rows read. Ancestry, not membership in the loop: K03 measured that freezing the
heater's regime puts a spurious phase wall at the nominal state, and the heater's block is *not*
an ancestor of the tear rows even though the heater is in the loop.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from openflowsheet.graph.blocks import BlockTriangularForm, block_triangular_form
from openflowsheet.graph.matching import canonical_matching
from openflowsheet.graph.process import ProcessGraph
from openflowsheet.graph.trace import Declaration

__all__ = ["Candidate", "LoopTear", "TearAnalysis", "analyse_tear"]

#: The declared row kind that marks a phase equilibrium, and so a unit that selects a phase split.
#: Read from the declaration rather than from an id: `QuantityKind`'s `molar_flow_squared` exists
#: precisely because the division-free equilibrium row is a product of two flows.
EQUILIBRIUM_KIND = "molar_flow_squared"


@dataclass(frozen=True)
class Candidate:
    """One cycle edge considered as a tear, with everything the score reads."""

    stream_id: str
    producer: str
    consumer: str
    breaks_loop: bool
    torn_variables: tuple[str, ...]
    not_torn: tuple[str, ...]
    consumer_boundary_distance: int

    @property
    def dimension(self) -> int:
        return len(self.torn_variables)

    def as_document(self) -> dict[str, object]:
        return {
            "stream": self.stream_id,
            "producer": self.producer,
            "consumer": self.consumer,
            "breaks_loop": self.breaks_loop,
            "dimension": self.dimension,
            "torn_variables": list(self.torn_variables),
            "not_torn": list(self.not_torn),
            "consumer_boundary_distance": self.consumer_boundary_distance,
        }


@dataclass(frozen=True)
class LoopTear:
    """One process loop and the tear chosen for it, or the reason none was."""

    units: tuple[str, ...]
    cycle_edges: tuple[str, ...]
    candidates: tuple[Candidate, ...]
    chosen_stream: str | None
    tie_break_used: str | None
    tear_variables: tuple[str, ...]
    tear_rows: tuple[str, ...]
    unsupported: str | None = None

    def as_document(self) -> dict[str, object]:
        document: dict[str, object] = {
            "units": list(self.units),
            "cycle_edges": list(self.cycle_edges),
            "candidates": [candidate.as_document() for candidate in self.candidates],
            "chosen_stream": self.chosen_stream,
            "tie_break_used": self.tie_break_used,
            "tear_variables": list(self.tear_variables),
            "tear_rows": list(self.tear_rows),
        }
        if self.unsupported is not None:
            document["unsupported"] = self.unsupported
        return document


@dataclass(frozen=True)
class TearAnalysis:
    """The loops, the inner system they leave, and the attempt signature it implies."""

    loops: tuple[LoopTear, ...]
    inner_rows: tuple[str, ...]
    inner_variables: tuple[str, ...]
    inner_form: BlockTriangularForm | None
    signature_units: tuple[str, ...]
    phase_selecting: tuple[tuple[str, tuple[int, ...], bool], ...] = ()
    ancestor_blocks_of_tear_rows: tuple[int, ...] = ()

    def as_document(self) -> dict[str, object]:
        return {
            "loops": [loop.as_document() for loop in self.loops],
            "inner_rows": len(self.inner_rows),
            "inner_variables": len(self.inner_variables),
            "inner_block_sizes_sorted": (
                [] if self.inner_form is None else list(self.inner_form.block_sizes_sorted)
            ),
            "inner_block_count": 0 if self.inner_form is None else self.inner_form.block_count,
            "signature_units": list(self.signature_units),
            "phase_selecting": [
                {"unit": unit, "lifted_blocks": list(blocks), "upstream_of_tear": upstream}
                for unit, blocks, upstream in self.phase_selecting
            ],
            "ancestor_blocks_of_tear_rows": list(self.ancestor_blocks_of_tear_rows),
        }


def _strongly_connected(units: Sequence[str], edges: Sequence[tuple[str, str]]) -> list[list[str]]:
    """Kosaraju on the unit digraph, in declaration order. Small graphs; clarity over speed."""
    forward: dict[str, list[str]] = {unit: [] for unit in units}
    backward: dict[str, list[str]] = {unit: [] for unit in units}
    for source, target in edges:
        if source in forward and target in forward:
            forward[source].append(target)
            backward[target].append(source)

    order: list[str] = []
    seen: set[str] = set()

    def visit(start: str) -> None:
        stack = [(start, iter(forward[start]))]
        seen.add(start)
        while stack:
            node, children = stack[-1]
            advanced = False
            for child in children:
                if child not in seen:
                    seen.add(child)
                    stack.append((child, iter(forward[child])))
                    advanced = True
                    break
            if not advanced:
                order.append(stack.pop()[0])

    for unit in units:
        if unit not in seen:
            visit(unit)

    assigned: set[str] = set()
    components: list[list[str]] = []
    for unit in reversed(order):
        if unit in assigned:
            continue
        component: list[str] = []
        stack = [unit]
        assigned.add(unit)
        while stack:
            node = stack.pop()
            component.append(node)
            for previous in backward[node]:
                if previous not in assigned:
                    assigned.add(previous)
                    stack.append(previous)
        components.append(sorted(component, key=units.index))
    return components


def _boundary_distances(graph: ProcessGraph) -> dict[str, int]:
    """Material edges from a boundary unit, breadth first. Unreachable units are absent."""
    distance: dict[str, int] = {unit: 0 for unit in graph.boundary_units()}
    frontier = list(distance)
    while frontier:
        following: list[str] = []
        for unit in frontier:
            for connection in graph.connections:
                if connection.producer == unit and connection.consumer not in distance:
                    distance[connection.consumer] = distance[unit] + 1
                    following.append(connection.consumer)
        frontier = following
    return distance


def analyse_tear(
    declaration: Declaration,
    graph: ProcessGraph,
    *,
    retained_rows: Sequence[str],
    square_form: BlockTriangularForm,
) -> TearAnalysis:
    """§9's rule on the square system `square_form` describes."""
    incidence = declaration.incidence()
    distances = _boundary_distances(graph)
    edges = [(connection.producer, connection.consumer) for connection in graph.connections]
    loops = [
        component
        for component in _strongly_connected(list(graph.units), edges)
        if len(component) > 1
    ]

    results: list[LoopTear] = []
    for units in loops:
        inside = set(units)
        cycle = [
            connection
            for connection in graph.connections
            if connection.producer in inside and connection.consumer in inside
        ]
        candidates: list[Candidate] = []
        for connection in cycle:
            # Does removing *this* edge break the loop? Parallel edges between the same pair of
            # units are possible, so the edge is dropped by identity and not by endpoint.
            remaining = [
                (other.producer, other.consumer)
                for other in graph.connections
                if other is not connection
            ]
            # "No cycle remains among these units", not "the component is no longer the whole
            # set". Two recycles sharing a unit split into two smaller loops when either is cut,
            # and the weaker test called every edge breaking — so one tear was chosen and a
            # recycle survived inside the supposedly acyclic inner system. Measured by the Fable
            # review of T01 (M1); SYN-001's single simple cycle cannot distinguish the two tests.
            still_looped = any(
                len(component) > 1 for component in _strongly_connected(list(units), remaining)
            )
            torn = tuple(
                column
                for column in connection.state_columns
                if _in_coupled_block(square_form, column)
            )
            candidates.append(
                Candidate(
                    stream_id=connection.stream_id,
                    producer=connection.producer,
                    consumer=connection.consumer,
                    breaks_loop=not still_looped,
                    torn_variables=torn,
                    not_torn=tuple(
                        column for column in connection.state_columns if column not in set(torn)
                    ),
                    consumer_boundary_distance=distances.get(connection.consumer, len(graph.units)),
                )
            )

        breaking = [candidate for candidate in candidates if candidate.breaks_loop]
        if not breaking:
            results.append(
                LoopTear(
                    units=tuple(units),
                    cycle_edges=tuple(candidate.stream_id for candidate in candidates),
                    candidates=tuple(candidates),
                    chosen_stream=None,
                    tie_break_used=None,
                    tear_variables=(),
                    tear_rows=(),
                    unsupported="multi_edge_feedback_set",
                )
            )
            continue

        chosen, decided_by = _choose(breaking)
        tear_variables = chosen.torn_variables
        torn_here = set(tear_variables)
        tear_rows = tuple(
            row_id
            for row_id in retained_rows
            if declaration.rows[row_id].unit == chosen.producer
            and torn_here.intersection(incidence[row_id])
        )
        results.append(
            LoopTear(
                units=tuple(units),
                cycle_edges=tuple(candidate.stream_id for candidate in candidates),
                candidates=tuple(candidates),
                chosen_stream=chosen.stream_id,
                tie_break_used=decided_by,
                tear_variables=tear_variables,
                tear_rows=tear_rows,
            )
        )

    torn_rows = {row_id for loop in results for row_id in loop.tear_rows}
    torn_columns = {column for loop in results for column in loop.tear_variables}
    inner_rows = tuple(row_id for row_id in retained_rows if row_id not in torn_rows)
    inner_variables = tuple(
        column for column in declaration.column_ids if column not in torn_columns
    )

    inner_form: BlockTriangularForm | None = None
    if len(inner_rows) == len(inner_variables):
        restricted = {
            row_id: frozenset(set(inner_variables).intersection(incidence[row_id]))
            for row_id in inner_rows
        }
        matching = canonical_matching(list(inner_rows), list(inner_variables), restricted)
        if len(matching) == len(inner_rows):
            inner_form = block_triangular_form(list(inner_rows), restricted, matching)

    signature, phase_selecting, ancestors = _signature(
        declaration, inner_form, inner_variables, torn_rows, incidence
    )
    return TearAnalysis(
        loops=tuple(results),
        inner_rows=inner_rows,
        inner_variables=inner_variables,
        inner_form=inner_form,
        signature_units=signature,
        phase_selecting=phase_selecting,
        ancestor_blocks_of_tear_rows=ancestors,
    )


def _in_coupled_block(form: BlockTriangularForm, column: str) -> bool:
    """Is the column inside a block bigger than one? That is what makes a coordinate coupled."""
    index = form.index_of_column(column)
    return index is not None and form.blocks[index].size > 1


#: §9.3's score, in order. Each key is an integer, so each step is a minimum over a finite
#: non-empty set; the last fallback is declaration order, which is injective, so the chain is
#: total and always ends in exactly one candidate.
_SCORE: tuple[tuple[str, Callable[[Candidate], int]], ...] = (
    ("dimension", lambda candidate: candidate.dimension),
    ("boundary_distance", lambda candidate: candidate.consumer_boundary_distance),
)


def _choose(candidates: Sequence[Candidate]) -> tuple[Candidate, str]:
    """§9.3's chain, recording which step decided rather than only the winner."""
    remaining = list(candidates)
    for label, key in _SCORE:
        best = min(key(candidate) for candidate in remaining)
        narrowed = [candidate for candidate in remaining if key(candidate) == best]
        if len(narrowed) == 1:
            return narrowed[0], label
        remaining = narrowed
    return remaining[0], "declaration_order"


def _signature(
    declaration: Declaration,
    form: BlockTriangularForm | None,
    inner_variables: Sequence[str],
    tear_rows: set[str],
    incidence: Mapping[str, frozenset[str]],
) -> tuple[tuple[str, ...], tuple[tuple[str, tuple[int, ...], bool], ...], tuple[int, ...]]:
    """§9.6: a phase-selecting unit is in the signature iff its block is upstream of the tear."""
    if form is None or not tear_rows:
        return (), (), ()

    read = {
        index
        for row_id in tear_rows
        for column in incidence[row_id]
        if (index := form.index_of_column(column)) is not None
    }
    ancestors = form.ancestors_of(sorted(read))

    lifted: dict[str, set[int]] = {}
    for row_id in declaration.row_ids:
        row = declaration.rows[row_id]
        if row.kind != EQUILIBRIUM_KIND or row.unit is None:
            continue
        index = form.index_of_row(row_id)
        if index is not None:
            lifted.setdefault(row.unit, set()).add(index)

    phase_selecting: list[tuple[str, tuple[int, ...], bool]] = []
    signature: list[str] = []
    order = _unit_order(declaration)
    for unit in sorted(lifted, key=lambda name: order.get(name, len(declaration.row_ids))):
        blocks = tuple(sorted(lifted[unit]))
        upstream = bool(set(blocks).intersection(ancestors))
        phase_selecting.append((unit, blocks, upstream))
        if upstream:
            signature.append(unit)
    return tuple(signature), tuple(phase_selecting), tuple(sorted(ancestors))


def _unit_order(declaration: Declaration) -> dict[str, int]:
    """Units in declaration order, taken from the order their rows first appear."""
    seen: dict[str, int] = {}
    for index, row_id in enumerate(declaration.row_ids):
        unit = declaration.rows[row_id].unit
        if unit is not None and unit not in seen:
            seen[unit] = index
    return seen
