"""The execution plan: acyclic evaluations, tear loops and EO regions, in order. T02 §3, §4, §7.1.

Everything here is decided from the declaration, the parameters, the unit manifests and the policy
— never from an iterate, a Jacobian value or a measured contraction (T02 design invariant 2). The
plan is built from T01's `StructuralReport`, which is computed **once** and read, not recomputed
(A01): its block-triangular form, its tear per loop, its certificates.

**Unit granularity.** A step is `evaluate(unit)`, `converge(loop)` or `solve_eo(region)`, placed in
the canonical topological order of the process graph's condensation (T01 §7.2's least-first-member
rule, on units). A loop is never split into nested loops and never "controlled" by another: a loop
no single edge breaks is torn by iterating T01's rule until it is acyclic, and the torn streams'
variables are one simultaneous tear vector ([A02]'s "no nested SM secant/control loops", applied to
recycles as well as to specifications).

**Why the loop's `SolvePlan` is built here and not by K03's `build_plan`.** K03's estimates the
Jacobian's non-zeros by *evaluating* one at the initializer, which is an evaluation during plan
construction (A01 forbids it) and, at `r = 0`, reads 167 where the declaration has 170 — the
constant folding of register R-018. The structural count is the declaration's.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Any, Final, Literal

from openflowsheet.compile.spec import ProblemSpec
from openflowsheet.graph.process import ProcessGraph
from openflowsheet.graph.report import StructuralReport
from openflowsheet.graph.tear import Candidate
from openflowsheet.graph.trace import Declaration
from openflowsheet.numerics.scaling import Scaling
from openflowsheet.orchestrator.trace import (
    Counters,
    EliminatedRowRecord,
    SolveOutcome,
    SolvePlan,
    SolvePolicy,
    Trace,
)

__all__ = [
    "EO_CAPABLE_METHODS",
    "declaration_identity",
    "ExecutionPlan",
    "PlanRefusal",
    "PlanStep",
    "Region",
    "condensation_order",
    "eo_capability",
    "iterated_tear_set",
    "plan_or_refusal",
    "specification_regions",
]

#: T02 §4.2: a unit is EO-capable iff its manifest declares a derivative of its residuals with
#: respect to its free variables by one of these. `finite_difference` is a test oracle (plan §4.2
#: K03 constraint) and `unavailable` is an honest absence; neither qualifies.
EO_CAPABLE_METHODS: Final = frozenset({"analytic", "ad", "implicit"})

#: The declared row kind that marks a lifted phase split (T01 §9.6's criterion).
_EQUILIBRIUM_KIND: Final = "molar_flow_squared"

StepKind = Literal["evaluate", "converge", "solve_eo"]


def eo_capability(manifest: Mapping[str, Any]) -> tuple[bool, str]:
    """Whether a unit's manifest makes it EO-capable, and the method its residuals declare."""
    for entry in manifest.get("derivatives", ()) or ():
        if entry.get("output") == "residuals" and "free_variables" in (
            entry.get("with_respect_to") or ()
        ):
            method = str(entry.get("method", "unavailable"))
            return method in EO_CAPABLE_METHODS, method
    return False, "undeclared"


@dataclass(frozen=True)
class Region:
    """An EO region's square system (T02 §6.1, §7.1): units, rows and columns after certificates."""

    units: tuple[str, ...]
    row_ids: tuple[str, ...]
    variable_ids: tuple[str, ...]
    eliminated_rows: tuple[str, ...]
    signature_units: tuple[str, ...]
    fixed_upstream: tuple[str, ...]
    specification_rows: tuple[str, ...] = ()
    adjusted_variables: tuple[str, ...] = ()
    target_variables: tuple[str, ...] = ()
    removed_specification_rows: tuple[str, ...] = ()
    #: T03 §9 as amended (review M2): adjusted variables whose `role: free` specification gave
    #: no value. The plan carries the fact, so the executor refuses from the plan it runs — no
    #: caller can omit it. (Runtime only: the `ExecutionPlan` document's schema is ADR 0009's
    #: and does not list it; flagged for the design lane.)
    missing_guesses: tuple[str, ...] = ()

    @property
    def square(self) -> bool:
        return len(self.row_ids) == len(self.variable_ids)


@dataclass(frozen=True)
class PlanStep:
    """One plan step. A `converge` or `solve_eo` step carries an unchanged K03 `SolvePlan`."""

    index: int
    kind: StepKind
    units: tuple[str, ...]
    solve_plan: SolvePlan | None = None
    tear_streams: tuple[str, ...] = ()
    method: Literal["newton_tear", "anderson"] | None = None
    region: Region | None = None
    #: For a `converge` step: the region that replaces the loop under the merge edge (T02 §4.4),
    #: precomputed so that a merge is a plan-time fact and not a run-time invention.
    region_on_merge: PlanStep | None = None
    #: `(unit, method)` when a loop unit is not EO-capable, so the merge cannot be made.
    merge_unsupported: tuple[str, str] | None = None

    def as_document(self) -> dict[str, Any]:
        document: dict[str, Any] = {
            "kind": self.kind,
            "index": self.index,
            "units": list(self.units),
        }
        if self.kind == "converge":
            assert self.solve_plan is not None and self.method is not None
            document["tear_streams"] = list(self.tear_streams)
            document["method"] = self.method
            document["solve_plan"] = self.solve_plan.as_document()
            document["region_on_merge"] = (
                None if self.region_on_merge is None else self.region_on_merge.as_document()
            )
            if self.merge_unsupported is not None:
                unit, method = self.merge_unsupported
                document["merge_unsupported"] = {"unit": unit, "method": method}
        elif self.kind == "solve_eo":
            assert self.solve_plan is not None and self.region is not None
            document["solve_plan"] = self.solve_plan.as_document()
            document["specification_rows"] = list(self.region.specification_rows)
            document["adjusted_variables"] = list(self.region.adjusted_variables)
            document["target_variables"] = list(self.region.target_variables)
            document["removed_specification_rows"] = list(self.region.removed_specification_rows)
            document["signature_units"] = list(self.region.signature_units)
        return document


@dataclass(frozen=True)
class ExecutionPlan:
    """ADR 0009 D1. R0 entire: ids, integers, orderings, declared scales and bounds."""

    plan_id: str
    model_version: str
    constants_sha256: str
    policy_id: str
    structural_report_ref: Mapping[str, str]
    steps: tuple[PlanStep, ...]
    estimates: Mapping[str, int] = field(default_factory=dict)

    def as_document(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "model_version": self.model_version,
            "constants_sha256": self.constants_sha256,
            "policy_id": self.policy_id,
            "structural_report_ref": dict(self.structural_report_ref),
            "steps": [step.as_document() for step in self.steps],
            "estimates": dict(self.estimates),
        }


def declaration_identity(spec: ProblemSpec) -> tuple[str, str]:
    """`(model_version, constants_sha256)` from the spec alone, as the compiler assigns them.

    ADR 0002 D2.5: `model_version` is `<label>@<structure_sha256>` over the spec's own ids and
    accumulation kinds, and `constants_sha256` hashes the complete pinned-input vector. Both are
    pure functions of the declaration, so a plan can carry them without compiling anything.
    """
    from openflowsheet.canonical import constants_sha256, model_version, structure_sha256

    return (
        model_version(
            spec.label,
            structure_sha256(
                spec.variable_ids, spec.equation_ids, spec.parameter_ids, spec.row_accumulation
            ),
        ),
        constants_sha256(spec.parameters, spec.parameter_ids),
    )


# -- the process graph's condensation, in canonical order -------------------------------------


def _components(units: Sequence[str], edges: Sequence[tuple[str, str]]) -> list[list[str]]:
    from openflowsheet.graph.tear import _strongly_connected

    return _strongly_connected(list(units), list(edges))


def condensation_order(graph: ProcessGraph) -> tuple[tuple[str, ...], ...]:
    """The process graph's SCCs in canonical topological order (T02 §3.2 rule 2).

    Among the nodes whose predecessors are all placed, the one whose first unit in declaration
    order comes first is placed next — T01 §7.2's rule on the condensation. Total and R0.
    """
    order = {unit: index for index, unit in enumerate(graph.units)}
    edges = [(connection.producer, connection.consumer) for connection in graph.connections]
    components = [
        tuple(sorted(component, key=order.__getitem__))
        for component in _components(graph.units, edges)
    ]
    member = {unit: index for index, component in enumerate(components) for unit in component}
    waiting = {
        index: {
            member[producer]
            for producer, consumer in edges
            if member.get(consumer) == index and member[producer] != index
        }
        for index in range(len(components))
    }
    placed: list[tuple[str, ...]] = []
    while waiting:
        ready = [index for index, before in waiting.items() if not before]
        chosen = min(ready, key=lambda index: order[components[index][0]])
        placed.append(components[chosen])
        del waiting[chosen]
        for before in waiting.values():
            before.discard(chosen)
    return tuple(placed)


# -- tear sets for a loop no single edge breaks (T02 §3.3) ------------------------------------


@dataclass(frozen=True)
class TearRound:
    loop_units: tuple[str, ...]
    cycle_edges: tuple[str, ...]
    chosen: str


def iterated_tear_set(
    graph: ProcessGraph,
    loop_units: Sequence[str],
    candidates: Sequence[Candidate],
) -> tuple[tuple[str, ...], tuple[TearRound, ...]]:
    """Iterate T01's single-edge rule until the loop is acyclic (T02 §3.3).

    Each round takes, among the remaining cycle edges of a non-trivial component, the one with
    least dimension, then least consumer boundary distance, then earliest declaration order;
    removes it; and recomputes the components. Greedy, total and R0; it does not claim a minimum
    feedback set (blueprint §7.2: "simple documented rules").
    """
    declared = {connection.stream_id: index for index, connection in enumerate(graph.connections)}
    by_stream = {candidate.stream_id: candidate for candidate in candidates}
    removed: list[str] = []
    rounds: list[TearRound] = []
    inside = set(loop_units)
    while True:
        remaining = [
            connection
            for connection in graph.connections
            if connection.stream_id not in removed
            and connection.producer in inside
            and connection.consumer in inside
        ]
        loops = [
            component
            for component in _components(
                list(loop_units), [(edge.producer, edge.consumer) for edge in remaining]
            )
            if len(component) > 1
        ]
        if not loops:
            return tuple(removed), tuple(rounds)
        first = min(loops, key=lambda component: min(graph.units.index(u) for u in component))
        members = set(first)
        cycle = [
            edge.stream_id
            for edge in remaining
            if edge.producer in members and edge.consumer in members
        ]
        chosen = min(
            cycle,
            key=lambda stream: (
                by_stream[stream].dimension,
                by_stream[stream].consumer_boundary_distance,
                declared[stream],
            ),
        )
        removed.append(chosen)
        rounds.append(
            TearRound(
                loop_units=tuple(sorted(members, key=graph.units.index)),
                cycle_edges=tuple(cycle),
                chosen=chosen,
            )
        )


# -- the plan -------------------------------------------------------------------------------


class CapabilityUnavailableError(ValueError):
    """T02 §7.4: a unit of an EO region lacks the derivatives it needs. The plan is not built."""

    def __init__(
        self,
        unit: str,
        method: str,
        region_units: Sequence[str],
        specification_rows: Sequence[str],
    ) -> None:
        served = list(specification_rows) if specification_rows else "the plan"
        super().__init__(
            f"CAPABILITY_UNAVAILABLE: {unit} declares its residual derivatives as {method!r}, "
            f"and the EO region {list(region_units)} for {served} needs them; "
            "no nested loop is built in their place"
        )
        self.unit, self.method = unit, method
        self.region_units = tuple(region_units)
        self.specification_rows = tuple(specification_rows)


class UnsupportedRankStructureError(ValueError):
    """T02 §7.1: a region that is structurally closed but not square after certificates, or a
    pairing of freed variables and targets v0.1 does not solve. K03 §7.2's code, same meaning."""

    def __init__(self, message: str) -> None:
        super().__init__(f"UNSUPPORTED_RANK_STRUCTURE: {message}")


def _tear_of(
    declaration: Declaration,
    candidates: Sequence[Candidate],
    streams: Sequence[str],
    retained: Sequence[str],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """T01 §9's rule, per torn stream: its torn variables, and its producer's retained rows that
    touch *those* variables. Pairing each stream with its own variables matters on a multi-edge
    set: a producer's row that merely reads another torn stream is not a tear row (NEST-1, where
    `B:s2` reads the torn `s5.x`)."""
    by_stream = {candidate.stream_id: candidate for candidate in candidates}
    variables: list[str] = []
    rows: list[str] = []
    for stream in streams:
        candidate = by_stream[stream]
        torn = set(candidate.torn_variables)
        variables.extend(candidate.torn_variables)
        rows.extend(
            row
            for row in retained
            if declaration.rows[row].unit == candidate.producer
            and torn.intersection(declaration.rows[row].columns)
            and row not in rows
        )
    return tuple(variables), tuple(rows)


def _validated_override(
    graph: ProcessGraph,
    loop_units: Sequence[str],
    candidates: Sequence[Candidate],
    streams: tuple[str, ...],
) -> tuple[str, ...]:
    """`recycle.tear_streams` (§3.3: "may name any set that leaves the loop acyclic"), checked."""
    known = {candidate.stream_id for candidate in candidates}
    stray = [stream for stream in streams if stream not in known]
    if stray:
        raise UnsupportedRankStructureError(
            f"recycle.tear_streams names {stray}, which are not cycle edges of the loop "
            f"{list(loop_units)} (its candidates are {sorted(known)})"
        )
    inside = set(loop_units)
    remaining = [
        (connection.producer, connection.consumer)
        for connection in graph.connections
        if connection.stream_id not in streams
        and connection.producer in inside
        and connection.consumer in inside
    ]
    cyclic = [c for c in _components(list(loop_units), remaining) if len(c) > 1] or [
        [producer] for producer, consumer in remaining if producer == consumer
    ]
    if cyclic:
        raise UnsupportedRankStructureError(
            f"recycle.tear_streams {list(streams)} leaves the loop {list(loop_units)} cyclic "
            f"(still cyclic: {cyclic[0]})"
        )
    return streams


def _lifted_units(declaration: Declaration, units: Sequence[str]) -> tuple[str, ...]:
    """The region's units that declare an equilibrium row, in declaration order (T02 §6.3.1)."""
    lifted = {
        declaration.rows[row].unit
        for row in declaration.row_ids
        if declaration.rows[row].kind == _EQUILIBRIUM_KIND
    }
    return tuple(unit for unit in units if unit in lifted)


def build_region(
    declaration: Declaration,
    graph: ProcessGraph,
    report: StructuralReport,
    units: Sequence[str],
    *,
    specification_rows: Sequence[str] = (),
    adjusted_variables: Sequence[str] = (),
    target_variables: Sequence[str] = (),
    removed_specification_rows: Sequence[str] = (),
) -> Region:
    """The region's square system: its units' rows minus certified redundancy, over its columns."""
    inside = set(units)
    certified = {entry.row_id for entry in report.certificates if entry.consistent}
    region_rows = [row for row in declaration.row_ids if declaration.rows[row].unit in inside]
    rows = tuple(row for row in region_rows if row not in certified)
    columns = tuple(
        column for column in declaration.column_ids if graph.column_owner(column) in inside
    )
    upstream = tuple(
        column
        for column in declaration.column_ids
        if column not in set(columns)
        and any(column in declaration.rows[row].columns for row in rows)
    )
    return Region(
        units=tuple(units),
        row_ids=rows,
        variable_ids=columns,
        eliminated_rows=tuple(row for row in region_rows if row in certified),
        signature_units=_lifted_units(declaration, units),
        fixed_upstream=upstream,
        specification_rows=tuple(specification_rows),
        adjusted_variables=tuple(adjusted_variables),
        target_variables=tuple(target_variables),
        removed_specification_rows=tuple(removed_specification_rows),
    )


def _reach(graph: ProcessGraph, start: str, *, forward: bool) -> set[str]:
    """Every unit reachable from `start` along material edges (or against them)."""
    seen = {start}
    frontier = [start]
    while frontier:
        unit = frontier.pop()
        for connection in graph.connections:
            source, target = (
                (connection.producer, connection.consumer)
                if forward
                else (connection.consumer, connection.producer)
            )
            if source == unit and target not in seen:
                seen.add(target)
                frontier.append(target)
    return seen


def specification_regions(
    declaration: Declaration,
    graph: ProcessGraph,
    report: StructuralReport,
    *,
    freed: Mapping[str, str],
    promoted: Mapping[str, str],
    missing_guesses: Sequence[str],
) -> tuple[Region, ...]:
    """T02 §7.1: the region of each cross-unit specification.

    A freed variable and its promoted target always define a region (review M1: a one-owner pair
    too, since no v0.1 unit solves a freed outlet locally). Its region is the target's owner, the
    adjusted variable's owner, every unit on a directed path between them in either direction, and
    every process loop containing any of those — blueprint [A02]'s "any connected recycle SCC needed
    for closure". The unit whose specified outlet is freed has no local evaluator any more, so the
    loop cannot be traversed around it and must be solved with the region.

    v0.1 pairs one freed variable with one promoted target; any other count is a typed refusal
    rather than a guess at which target a freed variable serves.
    """
    if not freed and not promoted:
        return ()
    if len(freed) != 1 or len(promoted) != 1:
        raise UnsupportedRankStructureError(
            f"{len(freed)} freed variables against {len(promoted)} promoted targets; v0.1 "
            "pairs exactly one of each (T02 §7.1)"
        )
    ((removed_row, adjusted),) = freed.items()
    ((promoted_row, target),) = promoted.items()
    adjusted_owner, target_owner = graph.column_owner(adjusted), graph.column_owner(target)
    if adjusted_owner is None or target_owner is None:
        raise ValueError(f"no owner for {adjusted!r} or {target!r}")
    # T02 review M1 (§7.1 as amended): a pair with one owner is a region too. Blueprint [A02]'s
    # "the unit's evaluator serves it" presumes a unit whose local solver computes the freed outlet
    # from the target; no v0.1 unit declares one (the SYN-001 heater takes `T` and reports `Q`),
    # so the loop cannot be torn around it. The region is that unit and every loop containing it.
    between: set[str] = set()
    if adjusted_owner != target_owner:
        between = (
            _reach(graph, adjusted_owner, forward=True) & _reach(graph, target_owner, forward=False)
        ) | (
            _reach(graph, target_owner, forward=True) & _reach(graph, adjusted_owner, forward=False)
        )
    members = between | {adjusted_owner, target_owner}
    edges = [(connection.producer, connection.consumer) for connection in graph.connections]
    for component in _components(graph.units, edges):
        if len(component) > 1 and members.intersection(component):
            members |= set(component)
    units = tuple(unit for unit in graph.units if unit in members)
    region = build_region(
        declaration,
        graph,
        report,
        units,
        specification_rows=(promoted_row,),
        adjusted_variables=(adjusted,),
        target_variables=(target,),
        removed_specification_rows=(removed_row,),
    )
    return (
        replace(
            region, missing_guesses=tuple(name for name in missing_guesses if name == adjusted)
        ),
    )


def _solve_plan(
    *,
    plan_id: str,
    declaration: Declaration,
    report: StructuralReport,
    scaling: Scaling,
    policy: SolvePolicy,
    tear_variables: Sequence[str],
    tear_rows: Sequence[str],
    inner_variables: Sequence[str],
    inner_rows: Sequence[str],
    eliminated: Sequence[str],
    bounded: Sequence[str],
    signature_units: Sequence[str],
    initializer_chain: Sequence[str],
) -> SolvePlan:
    """A K03 `SolvePlan`, unchanged in shape (ADR 0009 D5), built from the declaration alone."""
    rows = set(inner_rows) | set(tear_rows)
    columns = set(inner_variables) | set(tear_variables)
    certificates = {entry.row_id: entry for entry in report.certificates}
    return SolvePlan(
        plan_id=plan_id,
        model_version=declaration.model_version,
        constants_sha256=declaration.constants_sha256,
        policy_id=policy.policy_id,
        tear_variable_ids=tuple(tear_variables),
        tear_row_ids=tuple(tear_rows),
        inner_variable_ids=tuple(inner_variables),
        inner_row_ids=tuple(inner_rows),
        eliminated_rows=tuple(
            EliminatedRowRecord(
                row_id=row,
                equals=certificates[row].equals,
                constant_mismatch=certificates[row].constant_mismatch,
                tolerance=certificates[row].tolerance,
            )
            for row in eliminated
        ),
        column_scales={
            name: scaling.column[name] for name in declaration.column_ids if name in columns
        },
        row_scales={name: scaling.row[name] for name in declaration.row_ids if name in rows},
        scale_provenance=scaling.provenance,
        bounds=dict.fromkeys(bounded, (0.0, None)),
        signature_units=tuple(signature_units),
        initializer_chain=tuple(initializer_chain),
        estimates={
            "inner_dimension": len(inner_variables),
            # The *declared* incidence of the assembled rows — the certified ones included, as
            # K03's plan counts them — not an evaluated Jacobian's stored entries (R-018): the two
            # agree at every registered variant except r = 0, where the compiled pattern folds.
            "jacobian_nnz": sum(
                1
                for row in (*rows, *eliminated)
                for column in declaration.rows[row].columns
                if column in columns
            ),
        },
    )


def build_execution_plan(
    *,
    spec: ProblemSpec,
    declaration: Declaration,
    graph: ProcessGraph,
    report: StructuralReport,
    manifests: Mapping[str, Mapping[str, Any]],
    policy: SolvePolicy,
    specifications: Sequence[Region] = (),
) -> ExecutionPlan:
    """T02 §3.2's rule. Reads `report`; evaluates nothing.

    `specifications` are the cross-unit specification regions (T02 §7.1), already delimited; a
    region absorbs every loop and every evaluation of a unit it contains.
    """
    if report.finding != "STRUCTURALLY_CLOSED" or report.tear is None:
        raise ValueError(
            "an execution plan needs a structurally closed declaration; "
            f"T01 reports {report.finding}"
        )
    scaling = Scaling.from_spec(spec)
    capable = {unit: eo_capability(manifests.get(unit, {})) for unit in graph.units}
    units_with_rows = {row.unit for row in declaration.rows.values() if row.unit is not None}
    label = declaration.model_version.split("@")[0] or "plan"

    claimed: dict[str, Region] = {}
    for promoted in specifications:
        for unit in promoted.units:
            claimed[unit] = promoted
    for promoted in specifications:
        for unit in promoted.units:
            ok, declared = capable[unit]
            if not ok:
                raise CapabilityUnavailableError(
                    unit, declared, promoted.units, promoted.specification_rows
                )
        if not promoted.square:
            raise UnsupportedRankStructureError(
                f"the region {list(promoted.units)} for {list(promoted.specification_rows)} is "
                f"{len(promoted.row_ids)} rows over {len(promoted.variable_ids)} columns after "
                "certificates"
            )

    loops = {tuple(loop.units): loop for loop in report.tear.loops}
    certified = {entry.row_id for entry in report.certificates if entry.consistent}
    retained = tuple(row for row in declaration.row_ids if row not in certified)
    steps: list[PlanStep] = []
    placed_regions: set[int] = set()

    def region_step(region: Region, index: int, suffix: str) -> PlanStep:
        return PlanStep(
            index=index,
            kind="solve_eo",
            units=region.units,
            region=region,
            solve_plan=_solve_plan(
                plan_id=f"{label}-{policy.policy_id}-{suffix}",
                declaration=declaration,
                report=report,
                scaling=scaling,
                policy=policy,
                tear_variables=(),
                tear_rows=(),
                inner_variables=region.variable_ids,
                inner_rows=region.row_ids,
                eliminated=region.eliminated_rows,
                # T02 §6.1: every molar-flow column of the region, the lifted split included.
                bounded=tuple(
                    name
                    for name in region.variable_ids
                    if declaration.column_kinds.get(name) == "molar_flow"
                ),
                signature_units=region.signature_units,
                initializer_chain=("user_guess", "sequential_pre_solve"),
            ),
        )

    for node in condensation_order(graph):
        owner: Region | None = next((claimed[unit] for unit in node if unit in claimed), None)
        if owner is not None:
            if id(owner) not in placed_regions:
                placed_regions.add(id(owner))
                steps.append(region_step(owner, len(steps), f"region{len(steps)}"))
            continue
        self_loop = any(
            connection.producer == connection.consumer == node[0]
            for connection in graph.connections
        )
        if len(node) == 1 and not self_loop:
            # A sink owns no row and has no step (T02 §3.2).
            if node[0] in units_with_rows:
                steps.append(PlanStep(index=len(steps), kind="evaluate", units=node))
            continue

        loop = loops.get(tuple(node)) or next(
            (candidate for key, candidate in loops.items() if set(key) == set(node)), None
        )
        if loop is None:
            raise ValueError(f"T01 reports no loop for the process component {list(node)}")
        loop_region = build_region(declaration, graph, report, node)
        if policy.recycle.method == "eo":
            # Review S1: §7.4 holds for every region, a loop promoted by `method: eo` included.
            for unit in node:
                ok, declared = capable[unit]
                if not ok:
                    raise CapabilityUnavailableError(unit, declared, tuple(node), ())
            steps.append(region_step(loop_region, len(steps), f"region{len(steps)}"))
            continue

        if policy.recycle.tear_streams is not None:
            # Review M2: an override is resolved through the loop's own candidates and must leave
            # the loop acyclic (§3.3) — then the tear is *derived* from it, not just relabelled.
            tear_streams: tuple[str, ...] = _validated_override(
                graph, node, loop.candidates, tuple(policy.recycle.tear_streams)
            )
        elif loop.chosen_stream is not None:
            tear_streams = (loop.chosen_stream,)
        else:
            tear_streams, _ = iterated_tear_set(graph, node, loop.candidates)
        tear_variables, tear_rows = _tear_of(declaration, loop.candidates, tear_streams, retained)
        if len(tear_rows) != len(tear_variables):
            # A torn stream whose producer has more (or fewer) rows touching its torn variables
            # than it has torn variables is no tear K03's form can take — say so, by name.
            raise UnsupportedRankStructureError(
                f"tearing {list(tear_streams)} of the loop {list(node)} gives "
                f"{len(tear_rows)} tear rows {list(tear_rows)} for {len(tear_variables)} tear "
                "variables"
            )
        # The inner system is every retained row and every column not torn — by this loop, or by
        # T01's tear of any other loop (T01 §9's rule, restated so an override moves it too).
        other_rows = {
            row for other in report.tear.loops if other is not loop for row in other.tear_rows
        }
        other_columns = {
            column
            for other in report.tear.loops
            if other is not loop
            for column in other.tear_variables
        }
        inner_rows = tuple(
            row for row in retained if row not in set(tear_rows) and row not in other_rows
        )
        inner_variables = tuple(
            column
            for column in declaration.column_ids
            if column not in set(tear_variables) and column not in other_columns
        )
        incapable = next(((u, capable[u][1]) for u in node if not capable[u][0]), None)
        requested = policy.recycle.method
        method: Literal["newton_tear", "anderson"] = (
            "anderson"
            if requested == "anderson" or (requested == "auto" and incapable is not None)
            else "newton_tear"
        )
        steps.append(
            PlanStep(
                index=len(steps),
                kind="converge",
                units=tuple(node),
                tear_streams=tear_streams,
                method=method,
                solve_plan=_solve_plan(
                    plan_id=f"{label}-{policy.policy_id}-loop{len(steps)}",
                    declaration=declaration,
                    report=report,
                    scaling=scaling,
                    policy=policy,
                    tear_variables=tear_variables,
                    tear_rows=tear_rows,
                    inner_variables=inner_variables,
                    inner_rows=inner_rows,
                    eliminated=tuple(
                        entry.row_id for entry in report.certificates if entry.consistent
                    ),
                    # K03 §3: the tear flows are bounded below by 0 (ADR 0001 D3.5).
                    bounded=tear_variables,
                    signature_units=report.tear.signature_units,
                    initializer_chain=("user_guess", "registered_initializer"),
                ),
                region_on_merge=None
                if incapable is not None
                else region_step(loop_region, len(steps), f"merge{len(steps)}"),
                merge_unsupported=incapable,
            )
        )

    return ExecutionPlan(
        plan_id=f"{label}-{policy.policy_id}-execution",
        model_version=declaration.model_version,
        constants_sha256=declaration.constants_sha256,
        policy_id=policy.policy_id,
        structural_report_ref={
            "model_version": report.model_version,
            "constants_sha256": report.constants_sha256,
        },
        steps=tuple(steps),
        estimates={
            "loop_count": sum(1 for step in steps if step.kind == "converge"),
            "region_count": sum(1 for step in steps if step.kind == "solve_eo"),
            "largest_region_dimension": max(
                (len(step.region.variable_ids) for step in steps if step.region is not None),
                default=0,
            ),
        },
    )


@dataclass(frozen=True)
class PlanRefusal:
    """T02 §7.4: the solve ended at plan construction, before any evaluation.

    The trace holds exactly one event, `solve_closed`, with zero counters: K03's precedent for a
    solve that ends before its plan exists (a budget spent building it), where a `plan_built`
    event would say a plan was built.
    """

    outcome: SolveOutcome
    error: CapabilityUnavailableError
    trace: Trace
    #: The revision's ids of the specifications the refused region serves (not row ids).
    specifications: tuple[str, ...]
    model_version: str
    constants_sha256: str
    policy_id: str


def plan_or_refusal(
    *,
    spec: ProblemSpec,
    declaration: Declaration,
    graph: ProcessGraph,
    report: StructuralReport,
    manifests: Mapping[str, Mapping[str, Any]],
    policy: SolvePolicy,
    specifications: Sequence[Region] = (),
    specification_ids: Mapping[str, str] | None = None,
    trace: Trace | None = None,
) -> ExecutionPlan | PlanRefusal:
    """`build_execution_plan`, with the capability failure turned into the solve's typed end."""
    try:
        return build_execution_plan(
            spec=spec,
            declaration=declaration,
            graph=graph,
            report=report,
            manifests=manifests,
            policy=policy,
            specifications=specifications,
        )
    except CapabilityUnavailableError as error:
        run = trace if trace is not None else Trace()
        run.record(
            kind="solve_closed",
            attempt=0,
            iteration=0,
            signature=(),
            state_sha256="",
            residual_inf_unscaled=float("nan"),
            merit=float("nan"),
            counters=Counters(),
            outcome="CAPABILITY_UNAVAILABLE",
            message=str(error),
        )
        names = specification_ids or {}
        return PlanRefusal(
            outcome="CAPABILITY_UNAVAILABLE",
            error=error,
            trace=run,
            specifications=tuple(names.get(row, row) for row in error.specification_rows),
            model_version=declaration.model_version,
            constants_sha256=declaration.constants_sha256,
            policy_id=policy.policy_id,
        )
