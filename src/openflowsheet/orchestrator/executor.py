"""Running an `ExecutionPlan`: its steps in order, on one trace. T02 §3, §4.4, §6, §7.5; ADR 0009.

The trace of a plan run opens with the one `plan_built` of the `ExecutionPlan` (carrying
`step_count`) and closes with one `solve_closed`. Between them every step is bracketed — an
`evaluate` step by its `unit_evaluated`, a `converge` or `solve_eo` step by `region_opened` …
`region_closed` — and every event inside a step carries its `step_index` (the trace stamps it).

**Inner solves run on their own trace and are absorbed.** A step's K03 tear solve and §6 region
solve are complete solves with their own `plan_built` and `solve_closed`; recorded straight into the
plan's trace they would make a trace with several of each, which is not a trace K03's
well-formedness rule (opens on `plan_built`, closes on `solve_closed`) can read. So each inner solve
records into a scratch trace, and its events are copied into the plan's — in order, with fresh
`sequence` numbers, their counters offset by what the plan had spent before the step, so the
counters stay cumulative — except the inner `plan_built` (the step's `SolvePlan` is in the
`ExecutionPlan` already) and the inner `solve_closed`, whose outcome and message the step's
`region_closed` carries. One sequence, one identity comparison, one replay (ADR 0009's rejected
alternative "a separate trace for the recycle iteration"). The K03 solver is unchanged.

v0.1 runs SYN-001's plans: the flowsheet is the SYN-001 object, an `evaluate` step is its boundary
feed, and a loop's tear is K03's. A step this runner cannot run is a typed refusal, not a guess.

**A revision-built flowsheet** (T05 design note §2.3, register R-045) runs the one `solve_eo` step
`orchestrator.revision.plan_revision` builds, started from `initial_state` (`traversal-G0-v1`),
with its lifted splits and mass mapping read off its instances. Every SYN-001 expression is the
pre-T05 one; the dispatch is `isinstance(flowsheet, Syn001Flowsheet)` in the helpers below. What
the general path does not run — the tear path, a specification region — is a typed refusal.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, fields, replace
from typing import Any, Literal

import numpy as np

from openflowsheet.compile.casadi_backend import compile_problem
from openflowsheet.compile.spec import ProblemSpec
from openflowsheet.compiled import EvaluationContext
from openflowsheet.models.revision_flowsheet import RevisionFlowsheet
from openflowsheet.models.syn001.flowsheet import FEED_UNIT, WIRING, Syn001Flowsheet
from openflowsheet.orchestrator import revision
from openflowsheet.orchestrator.budget import BudgetExhaustedError, PropertyMeter
from openflowsheet.orchestrator.execution import ExecutionPlan, PlanStep, Region
from openflowsheet.orchestrator.homotopy import continuation_parameter
from openflowsheet.orchestrator.mass import (
    MassMapping,
    declared_phases,
    residence_time,
    syn001_residence_time,
)
from openflowsheet.orchestrator.merge import merge_due, merged_provenance, unsupported_note
from openflowsheet.orchestrator.recovery import eo_recovery_due, recovered_provenance
from openflowsheet.orchestrator.region import (
    ClosureType,
    DormancyForm,
    LiftedSplit,
    RecoveryStart,
    RegionResult,
    VapourOnlyForm,
    ZeroFlowForm,
    solve_region,
    syn001_lifted_splits,
)
from openflowsheet.orchestrator.splits import (
    closure_types,
    dormancy_forms,
    lifted_splits,
    split_temperatures,
    vapour_only_forms,
    zero_flow_forms,
)
from openflowsheet.orchestrator.tear import INITIALIZER_ID, Syn001TearProblem, solve_tear
from openflowsheet.orchestrator.trace import (
    Checkpoint,
    Counters,
    EoRecoveryUnsupported,
    EventKind,
    RecyclePolicy,
    SolveOutcome,
    SolvePlan,
    SolvePolicy,
    Trace,
)
from openflowsheet.orchestrator.warm_start import (
    WARM_START_REJECTED,
    WARM_START_SOURCE,
    WarmStartCandidate,
    WarmStartRecord,
    compatible,
    intact,
    project_bounds,
)

__all__ = ["PlanResult", "StepResult", "execute_plan"]

#: The flowsheets a plan runs on: SYN-001's own, and one built from a revision (T05 §2.3).
Flowsheet = Syn001Flowsheet | RevisionFlowsheet


@dataclass(frozen=True)
class StepResult:
    index: int
    kind: str
    units: tuple[str, ...]
    outcome: SolveOutcome
    iterations: int = 0
    merge_into_eo: Literal["taken", "unsupported"] | None = None
    merge_unsupported: tuple[str, str] | None = None
    message: str = ""
    #: The step's own solver result (a K03 `SolveResult` or a `RegionResult`), or `None`.
    detail: Any = None
    #: The step's checkpoint with its `step_index` (ADR 0009 D4), or `None`.
    checkpoint: Checkpoint | None = None
    #: After a merge: the recycle's own K03 result, beside the region's in `detail` (review S8).
    recycle: Any = None
    #: ADR 0010 D3 (T04 §5.2): `None` when edge 3 was not due, `"taken"` or `"unsupported"`.
    eo_recovery: Literal["taken", "unsupported"] | None = None
    eo_recovery_unsupported: EoRecoveryUnsupported | None = None
    #: After edge 3: the failed region solve, whose attempts, checkpoint and provenance are kept
    #: beside the recovery's in `detail` (T04 §5.3).
    recovered_from: Any = None
    #: ADR 0024 D4: what the compatible warm start did, when the policy's chain names it and no
    #: `user_start` was given; `None` otherwise (every other policy, every other step kind).
    warm_start: WarmStartRecord | None = None


@dataclass(frozen=True)
class PlanResult:
    outcome: SolveOutcome
    #: The full state over the declaration's variables after the last step that ran.
    state: Mapping[str, float] | None
    steps: tuple[StepResult, ...]
    trace: Trace
    counters: Counters
    message: str = ""

    @property
    def converged(self) -> bool:
        return self.outcome == "CONVERGED"

    @property
    def warm_start(self) -> WarmStartRecord | None:
        """ADR 0024 D4: the warm-start record of the step that consulted the source, if any."""
        return next((step.warm_start for step in self.steps if step.warm_start is not None), None)


def _offset(counters: Counters, by: Counters) -> Counters:
    return Counters(**{f.name: getattr(counters, f.name) + getattr(by, f.name) for f in fields(by)})


def _absorb(
    plan_trace: Trace, inner: Trace, spent: Counters, attempts_before: int = 0
) -> tuple[Counters, str, int]:
    """Copy `inner` into `plan_trace` (see the module note); return the new total, the inner
    solve's closing message and the next free attempt index of the step.

    Attempt indices are offset by the attempts the step already holds (review S7): a region
    step's pre-solve and its region solve are two solves, and one trace must not show two
    attempt 0s in one step."""
    total = spent
    closing = ""
    following = attempts_before
    for event in inner.events:
        if event.kind == "plan_built":
            continue
        counters = _offset(event.counters, spent)
        total = counters
        if event.kind == "solve_closed":
            closing = event.message
            continue
        document = {f.name: getattr(event, f.name) for f in fields(event) if f.name != "sequence"}
        document["counters"] = counters
        document["attempt"] = event.attempt + attempts_before
        following = max(following, event.attempt + attempts_before + 1)
        plan_trace.record(**document)
    return total, closing, following


def _bracket(
    trace: Trace,
    kind: Literal["region_opened", "region_closed", "unit_evaluated"],
    counters: Counters,
    *,
    outcome: SolveOutcome | None = None,
    message: str = "",
    merge_into_eo: Literal["taken", "unsupported"] | None = None,
    merge_unsupported: tuple[str, str] | None = None,
    eo_recovery: Literal["taken", "unsupported"] | None = None,
    eo_recovery_unsupported: EoRecoveryUnsupported | None = None,
) -> None:
    trace.record(
        kind=kind,
        attempt=0,
        iteration=0,
        signature=(),
        state_sha256="",
        residual_inf_unscaled=float("nan"),
        merit=float("nan"),
        counters=counters,
        outcome=outcome,
        message=message,
        merge_into_eo=merge_into_eo,
        merge_unsupported=merge_unsupported,
        eo_recovery=eo_recovery,
        eo_recovery_unsupported=eo_recovery_unsupported,
    )


def execute_plan(
    *,
    plan: ExecutionPlan,
    flowsheet: Flowsheet,
    spec: ProblemSpec,
    policy: SolvePolicy,
    trace: Trace | None = None,
    user_start: Mapping[str, float] | None = None,
    warm_start: WarmStartCandidate | None = None,
) -> PlanResult:
    """Run `plan`'s steps in order; stop at the first step that does not converge.

    `flowsheet` is the SYN-001 object the loop and the pre-solve traverse — for a cross-unit
    specification, the binding's flowsheet with the freed coordinate at its guess (§7.5) — or a
    revision-built flowsheet, whose plan is `plan_revision`'s one region (T05 §2.3). `spec` is the
    declaration the plan was built from, whose rows the regions solve.

    `user_start` (T06 spec §6.2, W6) is a start over every one of `spec.variable_ids` that a
    revision-built flowsheet's region opens from **instead of** `traversal-G0-v1`'s: it enters at
    the one point the registered initializer's output enters (`_solve_revision_region`'s region
    start), item 0's `initializer_source` is `user_guess` (T03 §8.1), and every recovery edge and
    fallback of the registered path runs unchanged. Absent (`None`, every registered caller),
    nothing here differs. It is refused, before anything is recorded, on a SYN-001 flowsheet
    (whose starts enter through `solve_tear`'s `initial_recycle` or a freed guess) and when its
    columns are not exactly the declaration's.

    `warm_start` (ADR 0024; T08 build-first spec §B2) is the application's source-2 candidate,
    read only when `policy.initializer_chain` names `compatible_warm_start` and there is no
    `user_start`, on a revision-built flowsheet's region; then `None` means the lookup found none
    (recorded `absent`). Its checks and record are `_warm_start`'s.
    """
    if user_start is not None:
        if isinstance(flowsheet, Syn001Flowsheet):
            raise ValueError("user_start_unsupported(syn001_flowsheet)")
        if set(user_start) != set(spec.variable_ids):
            missing = sorted(set(spec.variable_ids) - set(user_start))
            extra = sorted(set(user_start) - set(spec.variable_ids))
            raise ValueError(f"user_start_columns(missing={missing[:3]}, extra={extra[:3]})")
    run = trace if trace is not None else Trace()
    run.record(
        kind="plan_built",
        attempt=0,
        iteration=0,
        signature=(),
        state_sha256="",
        residual_inf_unscaled=float("nan"),
        merit=float("nan"),
        counters=Counters(),
        message=plan.plan_id,
        step_count=len(plan.steps),
    )
    spent = Counters()
    state: dict[str, float] | None = None
    done: list[StepResult] = []
    outcome: SolveOutcome = "CONVERGED"
    message = ""

    for step in plan.steps:
        run.open_step(step.index)
        try:
            result, spent, state = _run_step(
                step, flowsheet, spec, policy, run, spent, state, user_start, warm_start
            )
        finally:
            run.close_step()
        done.append(result)
        if result.outcome != "CONVERGED":
            outcome, message = result.outcome, result.message
            break

    run.record(
        kind="solve_closed",
        attempt=0,
        iteration=0,
        signature=(),
        state_sha256="",
        residual_inf_unscaled=float("nan"),
        merit=float("nan"),
        counters=spent,
        outcome=outcome,
        message=message,
    )
    return PlanResult(
        outcome=outcome,
        state=state,
        steps=tuple(done),
        trace=run,
        counters=spent,
        message=message,
    )


def _run_step(
    step: PlanStep,
    flowsheet: Flowsheet,
    spec: ProblemSpec,
    policy: SolvePolicy,
    run: Trace,
    spent: Counters,
    state: dict[str, float] | None,
    user_start: Mapping[str, float] | None = None,
    warm_start: WarmStartCandidate | None = None,
) -> tuple[StepResult, Counters, dict[str, float] | None]:
    if step.kind == "evaluate":
        (unit,) = step.units
        if unit != FEED_UNIT:
            # Review N9: a typed refusal, not a traceback — v0.1 evaluates no unit sequentially
            # outside a loop but the SYN-001 feed, and this runner does not guess at one.
            refusal = _refused(
                step,
                f"evaluating {unit} outside a loop is not supported by the v0.1 plan runner "
                "(SYN-001's only such unit is its feed)",
            )
            _bracket(run, "unit_evaluated", spent, outcome=refusal.outcome, message=refusal.message)
            return refusal, spent, state
        # The feed is a boundary: its outlet is fixed by the revision's specifications and is
        # part of every state the later steps reconstruct. Nothing is computed for it here.
        _bracket(run, "unit_evaluated", spent, message=f"{unit}: boundary; outlet specified")
        return StepResult(step.index, step.kind, step.units, "CONVERGED"), spent, state

    _bracket(
        run,
        "region_opened",
        spent,
        message=f"{step.kind} {list(step.units)}" + (f" {step.method}" if step.method else ""),
    )
    if step.kind == "converge":
        result, spent, state = _converge(step, flowsheet, spec, policy, run, spent)
    else:
        assert step.region is not None
        # T03 §9 as amended (review M2): the plan says which adjusted variable has no start, so
        # the refusal holds for every caller of the plan, by construction.
        if step.region.missing_guesses:
            result = _missing_guess(step, step.region.missing_guesses[0], run, spent)
        else:
            result, spent, state = _solve_eo(
                step.index, step.region, flowsheet, spec, policy, run, spent, user_start, warm_start
            )
    taken = getattr(result.detail, "checkpoint", None)
    if taken is not None:
        result = replace(result, checkpoint=replace(taken, step_index=step.index))
    _bracket(
        run,
        "region_closed",
        spent,
        outcome=result.outcome,
        message=result.message,
        merge_into_eo=result.merge_into_eo,
        merge_unsupported=result.merge_unsupported,
        eo_recovery=result.eo_recovery,
        eo_recovery_unsupported=result.eo_recovery_unsupported,
    )
    return result, spent, state


def _missing_guess(step: PlanStep, variable: str, run: Trace, spent: Counters) -> StepResult:
    """T03 §9 (ADR 0005 D8): a freed variable with no user guess has no initializer source for a
    temperature (K03 §4.1), so the chain rejects it and the solve ends `INITIALIZATION_FAILED` —
    no pre-solve, no attempt, no Jacobian."""
    message = f"missing_initial_guess({variable})"
    _reject_initializer(run, spent, message)
    return StepResult(step.index, step.kind, step.units, "INITIALIZATION_FAILED", message=message)


def _reject_initializer(run: Trace, spent: Counters, message: str) -> None:
    _initializer_event(run, spent, "initializer_rejected", message)


def _initializer_event(run: Trace, spent: Counters, kind: EventKind, message: str) -> None:
    run.record(
        kind=kind,
        attempt=0,
        iteration=0,
        signature=(),
        state_sha256="",
        residual_inf_unscaled=float("nan"),
        merit=float("nan"),
        counters=spent,
        message=message,
    )


def _splits(flowsheet: Flowsheet) -> tuple[LiftedSplit, ...]:
    """T05 §2.3's dispatch: SYN-001's own flowsheet takes every pre-T05 expression unchanged."""
    if isinstance(flowsheet, Syn001Flowsheet):
        return syn001_lifted_splits(flowsheet.components)
    return lifted_splits(revision.instances_of(flowsheet), flowsheet.components)


def _closure_types(flowsheet: Flowsheet) -> dict[str, ClosureType]:
    """T05b spec §6.1, as `_splits`: SYN-001's two splits are TP-type (the region's default)."""
    if isinstance(flowsheet, Syn001Flowsheet):
        return {}
    return closure_types(flowsheet.units())


def _zero_flow_forms(flowsheet: Flowsheet) -> dict[str, ZeroFlowForm]:
    """T05b spec §6.1, §7.2, as `_splits`: each split's `ZERO_FLOW` form, from the registry;
    SYN-001's two splits read their rules from SYN-001's own wiring."""
    if isinstance(flowsheet, Syn001Flowsheet):
        instances = tuple((u.unit_id, u.model_id, WIRING[u.unit_id]) for u in flowsheet.units())
    else:
        instances = revision.instances_of(flowsheet)
    return zero_flow_forms(
        instances, _splits(flowsheet), _closure_types(flowsheet), flowsheet.components
    )


def _vapour_only_forms(flowsheet: Flowsheet) -> dict[str, VapourOnlyForm]:
    """M02 design note §14.2 B13, as `_zero_flow_forms`: each split's vapour-only form, from the
    registry; SYN-001's own flowsheet has none (its rules declare no vapour-only component)."""
    if isinstance(flowsheet, Syn001Flowsheet):
        return {}
    instances = revision.instances_of(flowsheet)
    return vapour_only_forms(instances, _splits(flowsheet), flowsheet.components)


def _split_temperatures(flowsheet: Flowsheet) -> dict[str, tuple[str, ...]]:
    """T05b spec §6.2 step 3 as amended (Q-S11 (a)), as `_zero_flow_forms`: every temperature
    column of each split's streams, which an opening from a PH closure sets (read only under v2)."""
    if isinstance(flowsheet, Syn001Flowsheet):
        instances = tuple((u.unit_id, u.model_id, WIRING[u.unit_id]) for u in flowsheet.units())
    else:
        instances = revision.instances_of(flowsheet)
    return split_temperatures(instances, _splits(flowsheet))


def _dormancy_forms(flowsheet: Flowsheet) -> tuple[DormancyForm, ...]:
    """T05b spec §7.6, as `_zero_flow_forms`: every dormancy-form outlet of the flowsheet, from
    the registry, in declaration order (read by the region only under v2)."""
    if isinstance(flowsheet, Syn001Flowsheet):
        instances = tuple((u.unit_id, u.model_id, WIRING[u.unit_id]) for u in flowsheet.units())
    else:
        instances = revision.instances_of(flowsheet)
    return dormancy_forms(instances, flowsheet.units(), flowsheet.components)


def _mass_mapping(flowsheet: Flowsheet) -> MassMapping:
    """T05 §2.3's dispatch, as `_splits`."""
    if isinstance(flowsheet, Syn001Flowsheet):
        return syn001_residence_time(flowsheet.components)
    return residence_time(
        flowsheet.wiring, flowsheet.components, declared_phases(flowsheet.units())
    )


def _converge(
    step: PlanStep,
    flowsheet: Flowsheet,
    spec: ProblemSpec,
    policy: SolvePolicy,
    run: Trace,
    spent: Counters,
) -> tuple[StepResult, Counters, dict[str, float] | None]:
    if not isinstance(flowsheet, Syn001Flowsheet):
        # T05 §2.3 (register R-045): the tear path is SYN-001's; `plan_revision` emits no loop.
        return _refused(step, "tear_path_unsupported(revision_flowsheet)"), spent, None
    method = step.method or "newton_tear"
    step_policy = replace(policy, recycle=replace(policy.recycle, method=method))
    # Review M3, before anything runs: the tear path solves the flowsheet's own declaration, so it
    # must *be* the declaration the plan was built from. A freed coordinate, a removed row or a
    # promoted one makes them differ (M1's shape), and then the loop is not this step's loop.
    differs = _rows_differ(flowsheet.spec(), spec)
    if differs:
        return (
            _refused(step, f"the flowsheet's declaration is not the plan's: {differs}"),
            (spent),
            None,
        )
    # solve_tear builds its own trace so that its property sampler (the budget guard's count) is
    # on it; a trace handed in from here would carry structurally zero property counters.
    result, inner = solve_tear(flowsheet, policy=step_policy)
    spent, closing, attempts = _absorb(run, inner, spent)
    # Review M3, after: what K03 built from the flowsheet is what the plan recorded. A difference
    # means the run solved another problem, and its result is not reported as this step's.
    assert step.solve_plan is not None
    mismatch = _plan_mismatch(step.solve_plan, result.plan)
    if mismatch:
        return (
            _refused(step, f"the executed SolvePlan is not the planned one: {mismatch}"),
            (spent),
            None,
        )
    state = dict(result.final_state) if result.final_state is not None else None
    base = StepResult(
        step.index,
        step.kind,
        step.units,
        result.outcome,
        iterations=result.iterations,
        message=closing,
        detail=result,
    )
    # §4.4: a stalled Anderson loop, and only that, is re-solved once as its region.
    if result.converged or not merge_due(result.outcome, method):
        return base, spent, state
    if step.merge_unsupported is not None:
        unit, declared = step.merge_unsupported
        return (
            replace(
                base,
                merge_into_eo="unsupported",
                merge_unsupported=(unit, declared),
                message=f"{closing}; {unsupported_note(unit, declared)}",
            ),
            spent,
            state,
        )
    merged = step.region_on_merge
    if merged is None or merged.region is None or result.best_x is None:
        raise ValueError(f"step {step.index}: a merge was due and the plan gives no region")
    tear = Syn001TearProblem(flowsheet)
    start = dict(tear.reconstruct(tear.tear_state(np.asarray(result.best_x))))
    region_result, spent, state, following = _region(
        merged.region, start, flowsheet, spec, policy, run, spent, attempts, None
    )
    # T03 §8.1 (review S2): the region's attempts continue the loop's provenance list.
    region_result = replace(
        region_result,
        branch_provenance=merged_provenance(
            result.branch_provenance, region_result.branch_provenance
        ),
    )
    merged_step = replace(
        base,
        outcome=region_result.outcome,
        iterations=result.iterations + region_result.iterations,
        merge_into_eo="taken",
        message=region_result.message,
        detail=region_result,
        # Review S8: the recycle's own result (attempts, checkpoint, contexts) is kept.
        recycle=result,
    )
    # T04 §5.1: a merged region is a region solve, so edge 3 follows it too. It has no promoted
    # specification, so in v0.1 the edge after edge 2 is always `unsupported` — recorded.
    return _eo_recovery(
        merged_step, merged.region, flowsheet, spec, policy, run, spent, state, following
    )


def _rows_differ(ran: ProblemSpec, planned: ProblemSpec) -> str:
    ran_rows = {equation.equation_id for equation in ran.equations}
    planned_rows = {equation.equation_id for equation in planned.equations}
    if ran_rows == planned_rows:
        return ""
    return (
        f"rows only in the flowsheet {sorted(ran_rows - planned_rows)}, "
        f"only in the plan {sorted(planned_rows - ran_rows)}"
    )


#: The fields of a `SolvePlan` that say which problem it is (review M3). Scales and bounds are
#: policy constants both sides take from the same declaration; the ids and the identity decide.
_PLAN_IDENTITY = (
    "model_version",
    "constants_sha256",
    "tear_variable_ids",
    "tear_row_ids",
    "inner_variable_ids",
    "inner_row_ids",
    "signature_units",
)


def _plan_mismatch(planned: SolvePlan, ran: SolvePlan | None) -> str:
    if ran is None:
        return "no plan was built (the solve ended before it)"
    for name in _PLAN_IDENTITY:
        if getattr(planned, name) != getattr(ran, name):
            return f"{name}: planned {getattr(planned, name)!r}, ran {getattr(ran, name)!r}"
    planned_rows = [row.row_id for row in planned.eliminated_rows]
    ran_rows = [row.row_id for row in ran.eliminated_rows]
    if planned_rows != ran_rows:
        return f"eliminated_rows: planned {planned_rows}, ran {ran_rows}"
    return ""


def _refused(step: PlanStep, message: str) -> StepResult:
    return StepResult(
        step.index, step.kind, step.units, "UNSUPPORTED_RANK_STRUCTURE", message=message
    )


def _solve_eo(
    index: int,
    region: Region,
    flowsheet: Flowsheet,
    spec: ProblemSpec,
    policy: SolvePolicy,
    run: Trace,
    spent: Counters,
    user_start: Mapping[str, float] | None = None,
    warm_start: WarmStartCandidate | None = None,
) -> tuple[StepResult, Counters, dict[str, float] | None]:
    if not isinstance(flowsheet, Syn001Flowsheet):
        return _solve_revision_region(
            index, region, flowsheet, spec, policy, run, spent, user_start, warm_start
        )
    if region.specification_rows:
        # §7.5: the sequential pre-solve with the freed coordinate pinned at its guess.
        pre, inner = solve_tear(
            flowsheet, policy=replace(policy, recycle=RecyclePolicy(method="newton_tear"))
        )
        spent, closing, attempts = _absorb(run, inner, spent)
        if pre.final_state is None:
            return (
                StepResult(
                    index,
                    "solve_eo",
                    region.units,
                    pre.outcome,
                    iterations=pre.iterations,
                    message=f"the pre-solve (§7.5) ended {pre.outcome}: {closing}",
                    detail=pre,
                ),
                spent,
                None,
            )
        start = dict(pre.final_state)
    else:
        # §6.2: the sequential pre-solve's reconstruction at the registered initializer.
        attempts = 0
        start = dict(Syn001TearProblem(flowsheet).reconstruct(flowsheet.initial_recycle()))
    # T03 §8.1 as amended (review S2): the source of item 0's opening state, never a default — the
    # user's value of a freed coordinate seeds a specification region (through the pre-solve), the
    # registered initializer's reconstruction a promoted loop.
    source = "user_guess" if region.specification_rows else INITIALIZER_ID
    result, spent, state, following = _region(
        region, start, flowsheet, spec, policy, run, spent, attempts, source
    )
    step = StepResult(
        index,
        "solve_eo",
        region.units,
        result.outcome,
        iterations=result.iterations,
        message=result.message,
        detail=result,
    )
    return _eo_recovery(step, region, flowsheet, spec, policy, run, spent, state, following)


def _solve_revision_region(
    index: int,
    region: Region,
    flowsheet: RevisionFlowsheet,
    spec: ProblemSpec,
    policy: SolvePolicy,
    run: Trace,
    spent: Counters,
    user_start: Mapping[str, float] | None = None,
    warm_start: WarmStartCandidate | None = None,
) -> tuple[StepResult, Counters, dict[str, float] | None]:
    """T05 §2.3's general branch of `_solve_eo`: the region from `traversal-G0-v1`'s start, or
    from `user_start` (`execute_plan`), recorded `user_guess`, with no closure routes. With no
    `user_start` and a chain that names it, the compatible warm start comes first (ADR 0024)."""
    if region.specification_rows:
        # No cross-unit specification on a revision-built flowsheet in v0.1 (T05 §9).
        return (
            StepResult(
                index,
                "solve_eo",
                region.units,
                "UNSUPPORTED_RANK_STRUCTURE",
                message="specification_region_unsupported(revision_flowsheet)",
            ),
            spent,
            None,
        )
    record: WarmStartRecord | None = None
    if user_start is None and WARM_START_SOURCE in policy.initializer_chain:
        warm, record, spent = _warm_start(
            index, region, flowsheet, spec, policy, run, spent, warm_start
        )
        if warm is not None:
            step, spent, state = warm
            return replace(step, warm_start=record), spent, state
    if user_start is not None:
        start: revision.TraversalStart | revision.InitialStateFailure = revision.TraversalStart(
            {name: float(user_start[name]) for name in spec.variable_ids}
        )
        source = "user_guess"
    else:
        start = revision.traversal_start(flowsheet, spec.variable_ids)
        source = revision.INITIALIZER_ID
    if isinstance(start, revision.InitialStateFailure):
        _reject_initializer(run, spent, start.message)
        return (
            StepResult(
                index,
                "solve_eo",
                region.units,
                "INITIALIZATION_FAILED",
                message=start.message,
                warm_start=record,
            ),
            spent,
            None,
        )
    result, spent, state, following = _region(
        region,
        start.values,
        flowsheet,
        spec,
        policy,
        run,
        spent,
        0,
        source,
        band_routes=start.band_routes,
    )
    step = StepResult(
        index,
        "solve_eo",
        region.units,
        result.outcome,
        iterations=result.iterations,
        message=result.message,
        detail=result,
        warm_start=record,
    )
    return _eo_recovery(step, region, flowsheet, spec, policy, run, spent, state, following)


def _warm_start(
    index: int,
    region: Region,
    flowsheet: RevisionFlowsheet,
    spec: ProblemSpec,
    policy: SolvePolicy,
    run: Trace,
    spent: Counters,
    candidate: WarmStartCandidate | None,
) -> tuple[tuple[StepResult, Counters, dict[str, float] | None] | None, WarmStartRecord, Counters]:
    """ADR 0024 D3 (T08 build-first spec §B2): source 2. The region solved from the candidate
    when every check holds — the step as `_solve_revision_region` would return it — else `None`
    and the next source; with the record, and the counters after the checks' evaluation.

    The candidate enters where a `user_start` does, recorded `compatible_warm_start`. A failed
    solve from it keeps the policy's recovery edges and gains none (§B2, "No new fallback")."""
    present = "present" if candidate is not None else "absent"
    _initializer_event(run, spent, "initializer_candidate", f"{WARM_START_SOURCE}({present})")
    if candidate is None:
        return None, WarmStartRecord("absent"), spent

    def rejected(
        check: str, projections: tuple[tuple[str, float, float], ...] = ()
    ) -> tuple[None, WarmStartRecord, Counters]:
        _reject_initializer(run, spent, f"{WARM_START_REJECTED}({check})")
        return None, WarmStartRecord("rejected", check, candidate, projections), spent

    document = candidate.document
    if not intact(document):
        return rejected("integrity")
    if not compatible(document, spec):
        return rejected("compatibility")
    start, projections = project_bounds(document["variables"], spec)
    ok, spent = _evaluates(start, flowsheet, spec, policy, spent)
    if not ok:
        return rejected("evaluation", projections)
    result, spent, state, following = _region(
        region, start, flowsheet, spec, policy, run, spent, 0, WARM_START_SOURCE, warm_start=True
    )
    if result.outcome == "INITIALIZATION_FAILED" and not result.attempts:
        # §B2's `opening` check refused attempt 0's opening (`solve_region`): `opening:<check>`.
        check = result.message.removeprefix(f"{WARM_START_REJECTED}(").removesuffix(")")
        return rejected(check, projections)
    if not result.attempts and result.outcome != "BUDGET_EXHAUSTED":
        # Any other end before an attempt opened (review S4): §6.2's kernel refused the
        # candidate's state (`EVALUATION_ERROR`), or its opening did not settle (§7.8 (ii)). The
        # run never fails because of the warm start (§B2): `opening:<outcome>`, and the next
        # source. A spent plan budget is not the candidate's, and no source could open.
        return rejected(f"opening:{result.outcome}", projections)
    record = WarmStartRecord("accepted", None, candidate, projections)
    step = StepResult(
        index,
        "solve_eo",
        region.units,
        result.outcome,
        iterations=result.iterations,
        message=result.message,
        detail=result,
    )
    return (
        _eo_recovery(step, region, flowsheet, spec, policy, run, spent, state, following),
        record,
        spent,
    )


def _evaluates(
    start: Mapping[str, float],
    flowsheet: RevisionFlowsheet,
    spec: ProblemSpec,
    policy: SolvePolicy,
    spent: Counters,
) -> tuple[bool, Counters]:
    """§B2's `evaluation` check: the residual at `start` evaluates `ok`. Metered as a region's
    calls are (`_region`): against what the plan has left of the property budget, and counted —
    one residual call and its property calls — in the counters returned."""
    meter = flowsheet.provider
    if not isinstance(meter, PropertyMeter):
        raise TypeError(
            "a plan run meters the region's property calls, so the flowsheet's provider must be "
            f"a PropertyMeter; got {type(meter).__name__}"
        )
    before = meter.calls
    compiled = compile_problem(spec)
    context = EvaluationContext(
        model_version=compiled.metadata.model_version,
        constants_sha256=compiled.metadata.constants_sha256,
        phase_signature=None,
    )
    meter.limit = before + max(0, policy.max_property_calls - spent.property_calls)
    meter.cap, meter.refused = policy.max_property_calls, None
    try:
        vector = np.array([start[name] for name in spec.variable_ids], dtype=np.float64)
        ok = compiled.residual(vector, context).status == "ok"
    except BudgetExhaustedError:
        ok = False
    finally:
        meter.limit = None
    if meter.refusal() is not None:
        ok = False
    calls = meter.calls - before
    return ok, spent.plus(property_calls=calls, requested_evaluations=calls, residual_calls=1)


def _eo_recovery(
    step: StepResult,
    region: Region,
    flowsheet: Flowsheet,
    spec: ProblemSpec,
    policy: SolvePolicy,
    run: Trace,
    spent: Counters,
    state: dict[str, float],
    following: int,
) -> tuple[StepResult, Counters, dict[str, float]]:
    """T04 §5 (ADR 0010 D3): recovery edge 3 after a region solve, at most once per step.

    Preconditions in §5.2's order: the policy names the edge; the region solve ended in a trigger;
    the region has a continuation parameter — else, under `eo_recovery = "homotopy"`,
    `unsupported(no_continuation_parameter)` is recorded and the failed outcome stands, and under
    `"homotopy_or_sequential_restart"` the sequential restart's preconditions decide (ADR 0015;
    `_sequential_restart`). The count of one is structural: this runs once per region step, on
    the region solve the step ran, and never on its own recovery.
    """
    failed = step.detail
    if policy.globalization.eo_recovery not in (
        "homotopy",
        "homotopy_or_sequential_restart",
    ) or not isinstance(failed, RegionResult):
        return step, spent, state
    if not eo_recovery_due(failed.outcome, failed.budget):
        return step, spent, state
    continuation = continuation_parameter(
        specification_rows=region.specification_rows,
        target_variables=region.target_variables,
        spec=spec,
        structural_pattern=compile_problem(spec).structural_pattern(),
    )
    if continuation is None:
        if policy.globalization.eo_recovery == "homotopy_or_sequential_restart":
            return _sequential_restart(
                step, region, flowsheet, spec, policy, run, spent, state, following
            )
        return (
            replace(
                step,
                eo_recovery="unsupported",
                eo_recovery_unsupported="no_continuation_parameter",
            ),
            spent,
            state,
        )
    if failed.opening is None or not failed.branch_provenance:
        raise ValueError(
            f"defect: step {step.index}'s region solve ended {failed.outcome}, an edge-3 trigger, "
            "without an opened attempt to recover from"
        )
    opening_state, opening_regimes = failed.opening
    recovered, spent, state, _ = _region(
        region,
        dict(opening_state),
        flowsheet,
        spec,
        policy,
        run,
        spent,
        following,
        None,
        RecoveryStart(
            state=opening_state,
            regimes=opening_regimes,
            continuation=continuation,
            initializer_source=failed.branch_provenance[0]["initializer_source"],
        ),
    )
    recovered = replace(
        recovered,
        branch_provenance=recovered_provenance(
            failed.branch_provenance, recovered.branch_provenance
        ),
        # The step's checkpoint is the recovery's last accepted level (T04 §4.4: `partial` with
        # its λ below 1); the failed solve's own stays on `recovered_from`.
        checkpoint=recovered.checkpoint if recovered.checkpoint is not None else failed.checkpoint,
    )
    return (
        replace(
            step,
            outcome=recovered.outcome,
            iterations=step.iterations + recovered.iterations,
            message=recovered.message,
            detail=recovered,
            eo_recovery="taken",
            recovered_from=failed,
        ),
        spent,
        state,
    )


def _sequential_restart(
    step: StepResult,
    region: Region,
    flowsheet: Flowsheet,
    spec: ProblemSpec,
    policy: SolvePolicy,
    run: Trace,
    spent: Counters,
    state: dict[str, float],
    following: int,
) -> tuple[StepResult, Counters, dict[str, float]]:
    """ADR 0015 D1–D3 (design note `docs/design/T06-F4-recovery.md` §5.2–§5.5): edge 3's second
    action, reached when the region has no continuation parameter.

    P3: the flowsheet is revision-built, else `unsupported(no_restart_initializer)`. P4: the
    restart initializer `traversal-G0-pass8-v1` builds, else one `initializer_rejected` event and
    `unsupported(restart_initializer_failed)`; each pass it rejected is recorded first, whatever
    P5 decides. P5: the restart start is not the failed item 0's start by construction —
    `traversal-G0-v1` with at most two passes kept is the same code on the same passes — else
    `unsupported(restart_start_unchanged)`. Decided on integers and ids, never on floats.

    The action is one ordinary region solve from the restart start: §6.2's projection and pins,
    the policy's core and contract, a fresh contract state, attempt indices continuing from
    `following`, property calls metered with what the plan has left. Its outcome is the step's.
    """
    failed = step.detail

    def unsupported(reason: EoRecoveryUnsupported) -> tuple[StepResult, Counters, dict[str, float]]:
        return (
            replace(step, eo_recovery="unsupported", eo_recovery_unsupported=reason),
            spent,
            state,
        )

    if not isinstance(flowsheet, RevisionFlowsheet):
        return unsupported("no_restart_initializer")
    restart = revision.restart_start(flowsheet, spec.variable_ids)
    if isinstance(restart, revision.InitialStateFailure):
        _reject_initializer(run, spent, f"restart_initializer_failed: {restart.message}")
        return unsupported("restart_initializer_failed")
    for index, unit, _, code in restart.rejected:
        _reject_initializer(run, spent, f"restart_pass_rejected({index}): {unit}: {code}")
    # A revision region's first solve starts from `traversal_start` (`_solve_revision_region`);
    # an opening that did not settle opened no item, but started there all the same.
    failed_source = (
        failed.branch_provenance[0]["initializer_source"]
        if failed.branch_provenance
        else revision.INITIALIZER_ID
    )
    if failed_source == revision.INITIALIZER_ID and restart.passes_used <= 2:
        return unsupported("restart_start_unchanged")
    recovered, spent, state, _ = _region(
        region,
        restart.values,
        flowsheet,
        spec,
        policy,
        run,
        spent,
        following,
        revision.RESTART_INITIALIZER_ID,
        band_routes=restart.band_routes,
        item0_opening_source="eo_recovery_start",
    )
    recovered = replace(
        recovered,
        branch_provenance=recovered_provenance(
            failed.branch_provenance,
            recovered.branch_provenance,
            first_initializer_source=revision.RESTART_INITIALIZER_ID,
        ),
        checkpoint=recovered.checkpoint if recovered.checkpoint is not None else failed.checkpoint,
    )
    return (
        replace(
            step,
            outcome=recovered.outcome,
            iterations=step.iterations + recovered.iterations,
            message=recovered.message,
            detail=recovered,
            eo_recovery="taken",
            recovered_from=failed,
        ),
        spent,
        state,
    )


def _region(
    region: Region,
    start: dict[str, float],
    flowsheet: Flowsheet,
    spec: ProblemSpec,
    policy: SolvePolicy,
    run: Trace,
    spent: Counters,
    attempts_before: int,
    initializer_source: str | None,
    recovery: RecoveryStart | None = None,
    band_routes: Sequence[str] = (),
    item0_opening_source: Literal["initializer", "eo_recovery_start"] = "initializer",
    warm_start: bool = False,
) -> tuple[Any, Counters, dict[str, float], int]:
    """One region solve, metered; also the next free attempt index of the step. `initializer_source`
    is item 0's (T03 §8.1); `None` for a merge, whose caller continues the loop's provenance list
    instead (`merged_provenance`), and for edge 3's homotopy recovery, which names the failed item
    0's. `item0_opening_source` is item 0's opening source without `recovery` (`solve_region`)."""
    meter = flowsheet.provider
    if not isinstance(meter, PropertyMeter):
        raise TypeError(
            "a plan run meters the region's property calls, so the flowsheet's provider must be "
            "a PropertyMeter installed before the declaration was built (its property blocks "
            f"capture the provider); got {type(meter).__name__}"
        )
    before = meter.calls

    def sample() -> dict[str, int]:
        # This step's own calls; `_absorb` adds what the plan had spent before it. No cache sits
        # on the region path, so every requested evaluation is a provider call.
        delta = meter.calls - before
        return {"property_calls": delta, "requested_evaluations": delta, "cache_hits": 0}

    inner = Trace(property_sampler=sample)
    compiled = compile_problem(spec)
    # Review S4: K03 §11.2's budget holds inside a region too — what the plan has left of the
    # policy's cap. The refusal is read off the meter, because the compiled residual turns a
    # block's exception into an `error` evaluation before it could reach here.
    meter.limit = before + max(0, policy.max_property_calls - spent.property_calls)
    meter.cap, meter.refused = policy.max_property_calls, None
    try:
        result = solve_region(
            compiled=compiled,
            spec=spec,
            region=region,
            state=start,
            splits=_splits(flowsheet),
            provider=flowsheet.provider,
            policy=policy,
            trace=inner,
            initializer_source=initializer_source,
            recovery=recovery,
            compile_level=compile_problem,
            # T04 §7.2: the PTC core's holdups, read only under `eo_core = "ptc"`.
            mass_mapping=_mass_mapping(flowsheet),
            # T05b spec §6.1–§6.5: read only under `T05b-phase-contract-v2`.
            closure_types=_closure_types(flowsheet),
            band_routes=band_routes,
            zero_flow_forms=_zero_flow_forms(flowsheet),
            dormancy_forms=_dormancy_forms(flowsheet),
            split_temperatures=_split_temperatures(flowsheet),
            item0_opening_source=item0_opening_source,
            warm_start=warm_start,
            # M02 design note §14.2 B13: read in every TWO_PHASE attempt; none for SYN-001.
            vapour_only_forms=_vapour_only_forms(flowsheet),
        )
    except BudgetExhaustedError:
        result = RegionResult(
            outcome="BUDGET_EXHAUSTED", state=dict(start), attempts=(), budget="property_calls"
        )
    finally:
        meter.limit = None
    refusal = meter.refusal()
    if refusal is not None:
        result = replace(
            result, outcome="BUDGET_EXHAUSTED", message=str(refusal), budget="property_calls"
        )
    before_step = spent
    spent, _, following = _absorb(run, inner, spent, attempts_before)
    # T06 A93: the step's property counts are the meter's, not the last inner event's sample —
    # calls made after that event (the phase controller between iterations, the call a budget
    # refusal interrupts) were charged against the budget all the same. So the plan's next
    # events, and at `BUDGET_EXHAUSTED(property_calls)` its closing one, carry exactly what the
    # budget charged: `max_property_calls` on exhaustion (K03 §11.2).
    spent = replace(
        spent, **{name: getattr(before_step, name) + count for name, count in sample().items()}
    )
    return result, spent, dict(result.state), following
