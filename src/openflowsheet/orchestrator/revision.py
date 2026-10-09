"""Planning and starting a revision-built flowsheet's solve. T05 design note §2 (register R-045).

A flowsheet assembled from a revision (`models.revision_flowsheet.RevisionFlowsheet`) is solved as
**one EO region over every unit that authors a row**, started from a sequential traversal from
dormant torn streams — K03's `G(0)` pattern, two passes (`INITIALIZER_ID`). The tear path stays
SYN-001's and refuses a revision-built flowsheet, typed (`executor`, `tear.solve_tear`).

**`plan_revision`** is T02's planning pipeline unchanged — the declaration's identity, T01's trace
and analysis, `build_region`, `plan_or_refusal` — with the whole flowsheet handed in as the one
region, so the plan is one `solve_eo` step whose signature units are the lifted units in
declaration order. Before the region is built, the lifted-split registry is checked against the
rows the units authored (§3.3; `splits.check_agreement`): a drift between them is a defect, raised,
never a plan.

**`initial_state`** reads the start off the traversal and nothing else (§2.2): stream values, each
unit's reported duty, work and extent, and each lifted split re-split from the stream by the same
kernel the unit used. No compiled residual or Jacobian is called, and every property call made here
is outside the region's metered window — as the legacy start (`Syn001TearProblem.reconstruct`) is.
A heater-style split whose unit closed its outlet by the PH kernel is seeded from that closure's
split (T05b spec §6.4, ADR 0012 D5), which on the kernel's bracket route is the TP flash of the
same inputs bit for bit; `traversal_start` also names the units whose closure took the band route
(ADR 0012 D10 F1), for the region's record.

**`restart_start`** is recovery edge 3's second initializer, `traversal-G0-pass8-v1` (ADR 0015
D2): the same traversal continued to eight passes, reconstructed by the same steps
(`_start_from_pass`). The executor runs it only under `eo_recovery =
"homotopy_or_sequential_restart"`, after the region solve from `traversal-G0-v1` failed.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from openflowsheet.graph.analysis import analyse
from openflowsheet.graph.report import StructuralReport
from openflowsheet.graph.trace import trace_declaration
from openflowsheet.models import Wiring, duty_id, flow_id, pressure_id, temperature_id
from openflowsheet.models.revision_flowsheet import FlowsheetPass, RevisionFlowsheet
from openflowsheet.models.syn001.conversion_reactor import extent_id
from openflowsheet.models.syn001.ph_kernel import PHState
from openflowsheet.models.syn001.pump import work_id
from openflowsheet.models.syn001.tp_state import tp_state
from openflowsheet.orchestrator.execution import (
    ExecutionPlan,
    PlanRefusal,
    build_region,
    declaration_identity,
    plan_or_refusal,
)
from openflowsheet.orchestrator.splits import (
    SPLIT_RULES,
    check_agreement,
    closure_types,
    dormancy_forms,
    lifted_splits,
    vapour_only_forms,
    zero_flow_forms,
)
from openflowsheet.orchestrator.trace import SolvePolicy, Trace
from openflowsheet.thermo import StreamState

if TYPE_CHECKING:
    from openflowsheet.application.revision_binding import RevisionBinding

__all__ = [
    "INITIALIZER_ID",
    "RESTART_INITIALIZER_ID",
    "RESTART_PASSES",
    "InitialStateFailure",
    "RestartStart",
    "SplitRefusal",
    "TraversalStart",
    "initial_state",
    "instances_of",
    "lifted_split_values",
    "plan_revision",
    "restart_start",
    "traversal_start",
]

#: The registered initializer of a revision-built flowsheet's region: two traversal passes from
#: dormant torn streams (§2.2). It is item 0's `initializer_source` on every such solve.
INITIALIZER_ID: Final = "traversal-G0-v1"

#: Recovery edge 3's second action (ADR 0015 D2; design note `docs/design/T06-F4-recovery.md`
#: §5.3): the traversal from dormant torn streams continued to `RESTART_PASSES` passes. The pass
#: count is part of the id — a different count is a new initializer id, never a changed constant.
RESTART_INITIALIZER_ID: Final = "traversal-G0-pass8-v1"
RESTART_PASSES: Final = 8


@dataclass(frozen=True)
class InitialStateFailure:
    """The traversal could not produce a start: the unit that refused and its first message line."""

    unit: str
    code: str

    @property
    def message(self) -> str:
        return f"initializer_failed({self.unit}): {self.code}"


def instances_of(flowsheet: RevisionFlowsheet) -> tuple[tuple[str, str, Wiring], ...]:
    """`(unit id, model id, wiring)` per instance, in declaration order — what `lifted_splits`
    and `check_agreement` read."""
    return tuple(
        (unit.unit_id, unit.model_id, flowsheet.wiring[unit.unit_id]) for unit in flowsheet.units()
    )


def _failure(traversed: FlowsheetPass) -> InitialStateFailure | None:
    if traversed.status == "ok":
        return None
    return InitialStateFailure(traversed.failed_unit, traversed.code)


@dataclass(frozen=True)
class TraversalStart:
    """`initial_state`'s start, and what the region records about how the traversal reached it."""

    values: dict[str, float]
    #: The units whose PH closure answered by the band route (T05b spec §5.1 step 4), in
    #: declaration order: ADR 0012 D10 F1's record, `closure_route(<unit>, band)`.
    band_routes: tuple[str, ...] = ()


@dataclass(frozen=True)
class RestartStart:
    """`restart_start`'s start: the values and band routes of the pass it kept, how many passes
    that was, and the passes it rejected on the way."""

    #: Over `variable_ids`, in their order.
    values: dict[str, float]
    band_routes: tuple[str, ...]
    #: 1 (nothing torn) or 2..`RESTART_PASSES`.
    passes_used: int
    #: `(pass, unit, status, code)` of each rejected pass, in the order they were rejected.
    rejected: tuple[tuple[int, str, str, str], ...]


def initial_state(
    flowsheet: RevisionFlowsheet, variable_ids: Sequence[str]
) -> dict[str, float] | InitialStateFailure:
    """§2.2's six steps: the start over `variable_ids`, in that order, or the unit that refused.

    A missing value is a defect (`ValueError`), never a zero: every column of a revision-built
    declaration is a stream coordinate, a unit's reported duty, work or extent, or a lifted split.
    """
    start = traversal_start(flowsheet, variable_ids)
    return start if isinstance(start, InitialStateFailure) else start.values


def traversal_start(
    flowsheet: RevisionFlowsheet, variable_ids: Sequence[str]
) -> TraversalStart | InitialStateFailure:
    """`initial_state`, with the units whose traversal closure took the band route."""
    first = flowsheet.traverse({})
    failed = _failure(first)
    if failed is not None:
        return failed
    traversed = first
    if first.torn:
        traversed = flowsheet.traverse(first.computed_torn)
        # A refused pass stops at the refusing unit, so it has torn a prefix of the first pass's
        # streams, not necessarily all of them (C3X: pass 2 stops at U-HX after tearing S7 only).
        failed = _failure(traversed)
        expected = first.torn[: len(traversed.torn)] if failed is not None else first.torn
        if traversed.torn != expected:
            raise ValueError(
                f"the second traversal tore {list(traversed.torn)}, the first {list(first.torn)}"
            )
        if failed is not None:
            return failed
    return _start_from_pass(flowsheet, variable_ids, traversed)


def _start_from_pass(
    flowsheet: RevisionFlowsheet, variable_ids: Sequence[str], traversed: FlowsheetPass
) -> TraversalStart | InitialStateFailure:
    """§2.2 steps 3–6 on one successful pass: the streams, the units' reported duty, work and
    extent, each lifted split re-split from its stream, and the band routes — or the unit whose
    split the kernel refused. `traversal_start` calls it on pass 2 (pass 1 when nothing is torn);
    `restart_start` on the last pass its sequence kept."""
    wanted = set(variable_ids)
    values: dict[str, float] = {}
    for stream in flowsheet.streams:
        carried = traversed.streams[stream]
        for index, component in enumerate(flowsheet.components):
            values[flow_id(stream, component)] = carried.n[index]
        values[temperature_id(stream)] = carried.temperature
        values[pressure_id(stream)] = carried.pressure

    for unit, evaluation in traversed.evaluations.items():
        duty = duty_id(unit)
        if duty in wanted:
            reported = [x for x in (evaluation.duty, evaluation.transferred_duty) if x is not None]
            if len(reported) != 1:
                raise ValueError(
                    f"{unit} reports duty={evaluation.duty!r} and "
                    f"transferred_duty={evaluation.transferred_duty!r}; {duty} needs exactly one"
                )
            values[duty] = reported[0]
        for name, reported_value in (
            (work_id(unit), evaluation.work),
            (extent_id(unit), evaluation.extent),
        ):
            if name in wanted:
                if reported_value is None:
                    raise ValueError(f"{unit} reports no value for its column {name}")
                values[name] = reported_value

    split_values = lifted_split_values(
        flowsheet,
        values,
        traversed.streams,
        {unit: evaluation.closure for unit, evaluation in traversed.evaluations.items()},
    )
    if isinstance(split_values, SplitRefusal):
        return InitialStateFailure(split_values.unit, f"kernel_refused({split_values.stream})")
    values.update(split_values)

    for name in variable_ids:
        if name not in values:
            raise ValueError(f"initial_state_incomplete({name})")
    band_routes: list[str] = []
    for model in flowsheet.units():
        answered = traversed.evaluations.get(model.unit_id)
        if answered is not None and answered.closure is not None:
            if answered.closure.route == "band":
                band_routes.append(model.unit_id)
    return TraversalStart({name: values[name] for name in variable_ids}, tuple(band_routes))


@dataclass(frozen=True)
class SplitRefusal:
    """§2.2 step 5's refusal: the unit whose split the kernel refused, the stream it was asked to
    split, and the kernel's status (`absent` when a PH closure carried no split)."""

    unit: str
    stream: str
    status: str


def lifted_split_values(
    flowsheet: RevisionFlowsheet,
    values: Mapping[str, float],
    streams: Mapping[str, StreamState],
    closures: Mapping[str, PHState | None],
) -> dict[str, float] | SplitRefusal:
    """§2.2 step 5: every lifted split's columns, re-split from its stream.

    `values` holds the stream columns (a products-style split's totals are sums of its product
    streams' flows, read there); `streams` is each stream's `(n, T, P)`; `closures` is each
    split unit's PH closure, `None` where the unit closed by TP or the stream is not a unit's
    closure. `_start_from_pass` passes one traversal pass's; T06's ensemble passes a perturbed
    start's streams with no closure (spec §6.2: the split is a function of the stream). Returns
    the split columns, or the first split the kernel refused, in declaration order.
    """
    out: dict[str, float] = {}
    instances = instances_of(flowsheet)
    styles = {
        unit: SPLIT_RULES[model].style for unit, model, _ in instances if model in SPLIT_RULES
    }
    for split in lifted_splits(instances, flowsheet.components):
        if styles[split.unit] == "outlet":
            closure = closures[split.unit]
            if closure is not None:
                # T05b spec §6.4 (ADR 0012 D5): the split the unit's PH closure returned. On the
                # bracket route it is the provider's TP flash at the outlet's (n, T*, P) (T05
                # spec §4.4 step 6) — the re-flash below, bit for bit; on the saturation and band
                # routes the re-flash would lose the vapour fraction (`ln K_B(T_sat) = 0`: the
                # flash calls a pure stream at T_sat liquid).
                resplit = closure.split
            else:
                # A TP closure (the K02 heater, the outlet-temperature reactor) or a dormant
                # outlet: the provider's TP flash at the outlet's (n, T, P) (design note §2.2
                # step 5), which is the split the unit's own closure computed.
                resplit = tp_state(flowsheet.provider, streams[split.stream], flowsheet.context)
            if (
                resplit is None
                or resplit.status != "ok"
                or resplit.vapor is None
                or resplit.liquid is None
            ):
                status = "absent" if resplit is None else str(resplit.status)
                return SplitRefusal(split.unit, split.stream, status)
            for index, (vapor, liquid) in enumerate(zip(split.vapor, split.liquid, strict=True)):
                out[vapor] = resplit.vapor.n[index]
                out[liquid] = resplit.liquid.n[index]
            out[split.vapor_total] = sum(resplit.vapor.n)
            out[split.liquid_total] = sum(resplit.liquid.n)
        else:
            # Flash style: the split is the product streams, already assigned.
            out[split.vapor_total] = sum(values[name] for name in split.vapor)
            out[split.liquid_total] = sum(values[name] for name in split.liquid)
    return out


def _check_torn(first: FlowsheetPass, traversed: FlowsheetPass) -> None:
    """A later pass tears the first pass's streams (the deadlock depends only on the graph); a
    refused pass stops at the refusing unit, so it has torn a prefix of them. Else a defect."""
    expected = first.torn[: len(traversed.torn)] if traversed.status != "ok" else first.torn
    if traversed.torn != expected:
        raise ValueError(
            f"a later traversal tore {list(traversed.torn)}, the first {list(first.torn)}"
        )


def restart_start(
    flowsheet: RevisionFlowsheet, variable_ids: Sequence[str]
) -> RestartStart | InitialStateFailure:
    """`traversal-G0-pass8-v1` (design note §5.3, ADR 0015 D2): the traversal from dormant torn
    streams continued to `RESTART_PASSES` passes, each from the previous pass's `computed_torn`.

    Passes 1 and 2 must succeed, as `traversal_start`'s do. A pass `j ≥ 3` that a unit refuses
    ends the sequence at pass `j − 1`, recorded in `rejected`; so does a reconstruction the kernel
    refuses at a kept pass `≥ 3`, which falls back one pass. Like `traversal_start`, it makes no
    compiled residual or Jacobian call, and its provider calls fall outside the region's metered
    window (T05 §2.2's rule for initializers). The decisions are the units' typed statuses and
    integers, never a comparison of floats.
    """
    first = flowsheet.traverse({})
    failed = _failure(first)
    if failed is not None:
        return failed
    kept = [first]
    rejected: list[tuple[int, str, str, str]] = []
    if first.torn:
        for index in range(2, RESTART_PASSES + 1):
            traversed = flowsheet.traverse(kept[-1].computed_torn)
            _check_torn(first, traversed)
            failed = _failure(traversed)
            if failed is not None:
                if index == 2:
                    return failed
                rejected.append((index, traversed.failed_unit, traversed.status, traversed.code))
                break
            kept.append(traversed)
    while True:
        start = _start_from_pass(flowsheet, variable_ids, kept[-1])
        if not isinstance(start, InitialStateFailure):
            return RestartStart(start.values, start.band_routes, len(kept), tuple(rejected))
        if len(kept) <= 2:
            return start
        rejected.append((len(kept), start.unit, "kernel_refused", start.code))
        kept.pop()


def plan_revision(
    binding: RevisionBinding, policy: SolvePolicy, *, trace: Trace | None = None
) -> tuple[ExecutionPlan | PlanRefusal, StructuralReport]:
    """§2.1 step 2: one `solve_eo` step over every unit that authors a row, or T02's refusal.

    Raises `ValueError` when the lifted-split registry and the units' rows disagree (§3.3 (a)–(e);
    T05b's zero-flow and dormancy forms, (f)–(g)) and when T01 does not report the declaration
    `STRUCTURALLY_CLOSED` (`build_execution_plan`).
    """
    flowsheet, spec, graph = binding.flowsheet, binding.spec, binding.graph
    model_version, constants = declaration_identity(spec)
    declaration = trace_declaration(
        spec,
        model_version=model_version,
        constants_sha256=constants,
        specification_ids={},
        row_units=binding.row_units,
    )
    report = analyse(
        spec,
        graph,
        model_version=model_version,
        constants_sha256=constants,
        specification_ids={},
        row_units=binding.row_units,
    )

    instances = instances_of(flowsheet)
    splits = lifted_splits(instances, flowsheet.components)
    check_agreement(
        instances,
        splits,
        spec,
        binding.row_units,
        declaration,
        # T05b spec §6.1: the `ZERO_FLOW` forms' ids, checked like the descriptors.
        zero_flow_forms(instances, splits, closure_types(flowsheet.units()), flowsheet.components),
        # T05b spec §7.6: the dormancy forms of the units without a lifted split, likewise.
        dormancy_forms(instances, flowsheet.units(), flowsheet.components),
        # M02 design note §14.2 B13 (h): the vapour-only forms, likewise.
        vapour_only_forms(instances, splits, flowsheet.components),
    )

    authors = set(binding.row_units.values())
    whole = build_region(
        declaration,
        graph,
        report,
        tuple(unit.unit_id for unit in flowsheet.units() if unit.unit_id in authors),
    )
    plan = plan_or_refusal(
        spec=spec,
        declaration=declaration,
        graph=graph,
        report=report,
        manifests={unit.unit_id: unit.manifest() for unit in flowsheet.units()},
        policy=policy,
        specifications=(whole,),
        trace=trace,
    )
    return plan, report
