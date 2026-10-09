"""The `FailureBundle`: what a solve that did not converge is allowed to say. K04 §10.

Blueprint §8.2's list is long, and two of its clauses do the real work.

**"Distinguish observations from inferred causes."** They are separate fields here and never
mixed, because a bundle is read by someone deciding what to do next, and a guess that arrives
formatted like a measurement is worse than no guess.

**"An injected failure must not become a successful certificate through fallback."** So a
bundle carries no verdict word at all. The check set *may* be run over a failed solve's best
iterate and its `CheckReport` attached — that is the cheapest diagnosis a failure can carry —
but a budget-exhausted iterate that happens to satisfy every check still reads as the failure
it is, and the checkpoint says `checked_partial`, never `certified`.

And **no infeasibility claim**, ever (blueprint §7.7). `PHYSICALLY_INFEASIBLE` is not in K03's
outcome vocabulary and must not reappear here as prose: a solver may report that it failed,
never that no answer exists.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any, Final, Literal

#: §10.1 and K03 §11.1's map from a solver outcome onto blueprint §8.2's minimum taxonomy.
TAXONOMY: Final[Mapping[str, str]] = {
    "INITIALIZATION_FAILED": "initialization and recycle failures",
    "SCALE_UNAVAILABLE": "structure/specification conflicts",
    "SPECIFICATION_CONFLICT": "structure/specification conflicts",
    "UNSUPPORTED_RANK_STRUCTURE": "rank/linear/globalization failures",
    "ACTIVE_SET_CYCLING": "homotopy/PTC/active-set stalls",
    "PHASE_UPDATE_REQUIRED": "homotopy/PTC/active-set stalls",
    "ATTEMPTS_EXHAUSTED": "budget/cancellation outcomes",
    "BUDGET_EXHAUSTED": "budget/cancellation outcomes",
    "STAGNATION": "rank/linear/globalization failures",
    "LINE_SEARCH_FAILED": "rank/linear/globalization failures",
    "BOUND_BLOCKED": "rank/linear/globalization failures",
    "LINEAR_SOLVE_FAILED": "rank/linear/globalization failures",
    "INNER_SOLVE_INCONSISTENT": "model domain/conservation/derivative defects",
    "EVALUATION_ERROR": "model domain/conservation/derivative defects",
    # ADR 0009 D3 (T02). A recycle that stagnates is blueprint §8.2's own "recycle failure".
    "RECYCLE_STAGNATION": "initialization and recycle failures",
    # T02 §7.4: blueprint §8.2's only class naming derivatives. Its action is not the class's
    # `report_defect` but `provide_derivatives` (`OUTCOME_ACTIONS`).
    "CAPABILITY_UNAVAILABLE": "model domain/conservation/derivative defects",
    # ADR 0005 D6 (T03 §5.1): the controller that produced it; its action is overridden below.
    "CHECKPOINT_INCOMPATIBLE": "homotopy/PTC/active-set stalls",
    # ADR 0010 D8 (T04): the two failures to advance take their class's `supply_initial_guess`
    # (correct on both registered stalls, T04 §4.6); a mapping the validator refuses is a defect.
    "HOMOTOPY_STALLED": "homotopy/PTC/active-set stalls",
    "PTC_STALLED": "homotopy/PTC/active-set stalls",
    "PTC_MAPPING_INVALID": "model domain/conservation/derivative defects",
    # ADR 0034 D3 (M02 WO-10): the outer coupling's give-up, classed as its closest analogue, the
    # recycle iteration's `RECYCLE_STAGNATION` (an outer fixed-point iteration on a loop).
    "COUPLING_NOT_CONVERGED": "initialization and recycle failures",
}

SuggestedAction = Literal[
    "increase_budget",
    "supply_initial_guess",
    "revise_specification",
    "report_defect",
    # ADR 0009 D6 (T02).
    "provide_derivatives",
]

#: §10.1's registered vocabulary. Typed, so a bundle cannot smuggle executable content into a
#: field a reader might act on; `requires_permission` is always true because every one of them
#: is a proposal to a human and none is a thing the system may do by itself.
ACTIONS: Final[Mapping[str, SuggestedAction]] = {
    "budget/cancellation outcomes": "increase_budget",
    "initialization and recycle failures": "supply_initial_guess",
    "structure/specification conflicts": "revise_specification",
    "rank/linear/globalization failures": "report_defect",
    "homotopy/PTC/active-set stalls": "supply_initial_guess",
    "model domain/conservation/derivative defects": "report_defect",
}

#: Outcomes whose action is not their class's. ADR 0009 D6: a derivative a manifest declares
#: `unavailable` is an honest declaration (blueprint §5.2), so the proposal is to provide it —
#: `report_defect` would point the reader at the wrong object.
OUTCOME_ACTIONS: Final[Mapping[str, SuggestedAction]] = {
    "CAPABILITY_UNAVAILABLE": "provide_derivatives",
    # ADR 0005 D6: no registered path produces an incompatible opening state, so one that
    # appears is a defect; `supply_initial_guess` would point the reader at the wrong object.
    "CHECKPOINT_INCOMPATIBLE": "report_defect",
}

#: The four verdict words, which may not appear anywhere in a bundle (§8.3, A20).
VERDICT_WORDS: Final[frozenset[str]] = frozenset({"VERIFIED", "RELAXED", "UNVERIFIED", "FAILED"})


#: Registered outcome codes that contain a verdict word as a *part* of a code, not as a verdict:
#: without this, a bundle for any of them could not be built at all (found by T02 A16, whose merge
#: ends `LINEAR_SOLVE_FAILED`). Removed before the scan, so the words themselves stay forbidden
#: everywhere else — "the Newton FAILED" in a message is still refused.
OUTCOME_CODES_WITH_VERDICT_WORDS: Final[tuple[str, ...]] = (
    "INITIALIZATION_FAILED",
    "LINEAR_SOLVE_FAILED",
    "LINE_SEARCH_FAILED",
)


class InfeasibilityClaimError(ValueError):
    """A bundle tried to say no answer exists. Blueprint §7.7 forbids it outright."""


@dataclass(frozen=True)
class SuggestedActionEntry:
    action: SuggestedAction
    preconditions: str
    requires_permission: bool = True

    def as_document(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "preconditions": self.preconditions,
            "requires_permission": self.requires_permission,
        }


@dataclass(frozen=True)
class FailureBundle:
    """§10.1, all fields required; the two list fields may be empty but never absent."""

    outcome: str
    taxonomy: str
    observations: Mapping[str, Any]
    inferred_causes: tuple[Mapping[str, Any], ...]
    implicated_sources: tuple[str, ...]
    attempt_tree: tuple[Mapping[str, Any], ...]
    replay_identity: Mapping[str, str]
    best_checkpoint: Mapping[str, Any] | None = None
    check_report: Mapping[str, Any] | None = None
    suggested_actions: tuple[SuggestedActionEntry, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        text = repr(self.as_document())
        if "INFEASIBLE" in text.upper():
            raise InfeasibilityClaimError(
                "blueprint §7.7: a solver may report that it failed, never that no answer "
                "exists. `PHYSICALLY_INFEASIBLE` is not in the outcome vocabulary and must "
                "not reappear as prose"
            )
        scanned = text
        for code in OUTCOME_CODES_WITH_VERDICT_WORDS:
            scanned = scanned.replace(code, "")
        leaked = sorted(word for word in VERDICT_WORDS if word in scanned)
        if leaked:
            raise ValueError(
                f"§8.3 and A20: a failure bundle carries no verdict word, and this one has "
                f"{leaked}. A budget-exhausted iterate that satisfies every check still reads "
                "as the failure it is"
            )

    def as_document(self) -> dict[str, Any]:
        return {
            "outcome": self.outcome,
            "taxonomy": self.taxonomy,
            "observations": dict(self.observations),
            "inferred_causes": [dict(cause) for cause in self.inferred_causes],
            "implicated_sources": list(self.implicated_sources),
            "attempt_tree": [dict(entry) for entry in self.attempt_tree],
            "replay_identity": dict(self.replay_identity),
            "best_checkpoint": dict(self.best_checkpoint) if self.best_checkpoint else None,
            "check_report": dict(self.check_report) if self.check_report else None,
            "suggested_actions": [entry.as_document() for entry in self.suggested_actions],
        }


def bundle_for(
    result: Any,
    trace: Any,
    *,
    implicated: Sequence[str] = (),
    inferred: Sequence[Mapping[str, Any]] = (),
    check_report: Mapping[str, Any] | None = None,
) -> FailureBundle:
    """§10.2: a bundle from a K03 result, with nothing inferred that was not measured."""
    outcome = str(result.outcome)
    taxonomy = TAXONOMY.get(outcome)
    if taxonomy is None:
        raise ValueError(f"{outcome!r} has no §8.2 class in K03 §11.1's map")

    counters = result.counters
    closing = trace.events[-1] if len(trace) else None
    checkpoint = result.checkpoint
    plan = getattr(result, "plan", None)

    return FailureBundle(
        outcome=outcome,
        taxonomy=taxonomy,
        observations={
            "closing_event": closing.kind if closing else None,
            "message": result.message,
            "attempts": result.attempts,
            "iterations": result.iterations,
            "residual_inf_unscaled": _finite(result.residual_inf),
            "counters": {
                "property_calls": counters.property_calls,
                "requested_evaluations": counters.requested_evaluations,
                "cache_hits": counters.cache_hits,
                "residual_calls": counters.residual_calls,
                "jacobian_calls": counters.jacobian_calls,
                "factorizations": counters.factorizations,
            },
            "last_linear": (dict(closing.linear.__dict__) if closing and closing.linear else None),
            # T02 §4.4, A32: why a stalled loop was not re-solved as its region. Present only on
            # a result that had a merge edge to consider, so K03's bundles are unchanged.
            **_merge_observation(result),
        },
        inferred_causes=tuple(dict(cause) for cause in inferred),
        implicated_sources=tuple(implicated),
        attempt_tree=tuple(
            {
                "attempt": event.attempt,
                "signature": [list(pair) for pair in event.signature],
                "outcome": event.outcome,
                "iterations": event.iteration,
            }
            for event in trace.of_kind("attempt_closed")
            # ADR 0010 D7.2: a homotopy corrector closes its own Newton run inside the attempt,
            # stamped with its λ-trial; the attempt tree is the attempts, not their correctors.
            if event.homotopy_level is None
        ),
        replay_identity={
            "model_version": getattr(plan, "model_version", ""),
            "constants_sha256": getattr(plan, "constants_sha256", ""),
            "policy_id": getattr(plan, "policy_id", ""),
            "plan_id": getattr(plan, "plan_id", ""),
        },
        best_checkpoint=checkpoint.as_document() if checkpoint is not None else None,
        check_report=dict(check_report) if check_report else None,
        suggested_actions=(
            SuggestedActionEntry(
                action=OUTCOME_ACTIONS.get(outcome, ACTIONS[taxonomy]),
                preconditions=f"the {taxonomy} reported above is what a reader would act on",
            ),
        ),
    )


@dataclass(frozen=True)
class _RegionView:
    """A region result in the shape `bundle_for` reads: attempts counted, the residual taken from
    its checkpoint (the state it reports), nothing else invented. `plan` is the `ExecutionPlan`
    the run used, whose ids are the bundle's replay identity (T08 D2); `None` where the caller
    holds none, and then the identity stays empty as before."""

    outcome: str
    counters: Any
    checkpoint: Any
    message: str
    attempts: int
    iterations: int
    residual_inf: float
    plan: Any = None


@dataclass(frozen=True)
class _StepTrace:
    """A plan trace restricted to one step's events, read as a trace by `bundle_for`."""

    events: tuple[Any, ...]

    def __len__(self) -> int:
        return len(self.events)

    def of_kind(self, kind: str) -> tuple[Any, ...]:
        return tuple(event for event in self.events if event.kind == kind)


def region_bundle(
    result: Any,
    trace: Any,
    *,
    step_index: int | None,
    implicated: Sequence[str] = (),
    plan: Any = None,
) -> FailureBundle:
    """The bundle of an EO region solve (a `RegionResult`), through `bundle_for`'s one body.

    ADR 0010 D8 / T04 §4.6: a `HOMOTOPY_STALLED` region solve carries exactly one inferred cause,
    the stalled homotopy's, from the registered vocabulary — `phase_boundary_on_path(<unit>)`,
    `singular_path_or_fold` or `corrector_failure` — marked a hypothesis, never an observation
    (blueprint §7.4: "branch loss is a hypothesis unless supported by diagnostics"). Every other
    outcome infers nothing. With `step_index`, `trace` is a plan trace and only that step's events
    are read: its T02 §7.5 pre-solve, its region solve and, after edge 3, the recovery — not the
    other steps' (the attempt tree is the step's history).

    With `step_index`, the counters are what the executor metered for the step (its
    `region_closed` less its `region_opened`), as `initializer_bundle`'s are (T08 D3, T08.A12).
    `result.counters` holds only the last region solve's own core counts: the property calls are
    metered by the executor's `PropertyMeter` into the plan trace and never reach a
    `RegionResult`, and the step's pre-solve and, after edge 3, its failed first solve are not in
    the recovery's result.

    `step_index` is required (T08 review S7), and `None` only for a region solve's own trace, run
    outside a plan: a plan trace without it would report `result.counters`' false zero (D3), so
    it is refused as a defect (`ValueError`).

    `plan` is the `ExecutionPlan` the run used: its `model_version`, `constants_sha256`,
    `policy_id` and `plan_id` are the bundle's replay identity (T08 D2, T08.A11). A
    `RegionResult` carries no plan of its own, so without it every one of them was empty."""
    counters: Any = result.counters
    if step_index is None and any(e.step_index is not None for e in trace.events):
        raise ValueError(
            "defect: a plan trace's region bundle needs its step_index (T08 D3, review S7)"
        )
    if step_index is not None:
        trace = _StepTrace(tuple(e for e in trace.events if e.step_index == step_index))
        counters = _step_counters(trace, step_index)
    checkpoint = result.checkpoint
    view = _RegionView(
        outcome=str(result.outcome),
        counters=counters,
        checkpoint=checkpoint,
        message=result.message,
        attempts=len(result.attempts),
        iterations=result.iterations,
        residual_inf=(checkpoint.residual_inf_unscaled if checkpoint is not None else float("nan")),
        plan=plan,
    )
    record = getattr(result, "homotopy", None)
    inferred: list[Mapping[str, Any]] = []
    if result.outcome == "HOMOTOPY_STALLED":
        cause = getattr(record, "inferred_cause", None)
        if cause is None:
            raise ValueError("defect: a stalled homotopy with no inferred cause (T04 §4.6)")
        inferred.append({"cause": cause, "kind": "hypothesis", "rule": "T04 §4.6"})
    return bundle_for(view, trace, implicated=implicated, inferred=inferred)


#: T07 ruling round 3, Q1 item 2: the two registered messages of an EO step's initializer refusal
#: — T05's `InitialStateFailure` (the source is a unit id) and T03 §9's missing guess (a variable
#: id). Matched whole, so a message that differs in any one feature is not accepted.
_INITIALIZER_MESSAGES: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(r"initializer_failed\((?P<source>[^()]+)\): .+"),
    re.compile(r"missing_initial_guess\((?P<source>[^()]+)\)"),
)

_COUNTER_FIELDS: Final[tuple[str, ...]] = (
    "property_calls",
    "requested_evaluations",
    "cache_hits",
    "residual_calls",
    "jacobian_calls",
    "factorizations",
)


def initializer_source(message: str) -> str | None:
    """The unit or variable an EO step's initializer refusal names, or `None` when `message` is
    neither registered form (T07 ruling round 3, Q1 item 2)."""
    for pattern in _INITIALIZER_MESSAGES:
        match = pattern.fullmatch(message)
        if match is not None:
            return match.group("source")
    return None


def initializer_bundle(step: Any, trace: Any, *, plan: Any = None) -> FailureBundle:
    """The bundle of a `solve_eo` step whose registered initializer refused before any attempt
    opened (`INITIALIZATION_FAILED`, no `RegionResult`), through `bundle_for`'s one body. T07
    ruling round 3, Q1 item 3.

    `trace` is the plan trace; only the step's events are read. The counters are what the executor
    metered for the step (its `region_closed` less its `region_opened`), not the initializer's own
    provider calls (Q1-O2). The named source is the one implicated object; nothing is inferred.

    `plan` is the `ExecutionPlan` the run executed: its `model_version`, `constants_sha256`,
    `policy_id` and `plan_id` are the bundle's replay identity, obtained as `region_bundle`'s are
    (item 3's table as amended by T08 build-first Amendment 1 §Am1.6, Q-P1-1). Without it every
    one of them is empty."""
    source = initializer_source(step.message)
    refused = step.kind == "solve_eo" and step.outcome == "INITIALIZATION_FAILED"
    if not refused or step.detail is not None:
        raise ValueError(f"defect: step {step.index} is not an EO initializer refusal")
    if source is None:
        raise ValueError(f"defect: {step.message!r} is not a registered initializer refusal")
    events = _StepTrace(tuple(e for e in trace.events if e.step_index == step.index))
    view = _RegionView(
        outcome=str(step.outcome),
        counters=_step_counters(events, step.index),
        checkpoint=None,
        message=step.message,
        attempts=len(events.of_kind("attempt_closed")),
        iterations=step.iterations,
        residual_inf=float("nan"),
        plan=plan,
    )
    return bundle_for(view, events, implicated=(source,))


def _step_counters(events: _StepTrace, step_index: int) -> SimpleNamespace:
    """What the executor metered for one plan step: its `region_closed` counters less its
    `region_opened` ones (the plan trace's counters are cumulative)."""
    opened, closed = events.of_kind("region_opened"), events.of_kind("region_closed")
    if len(opened) != 1 or len(closed) != 1:
        raise ValueError(f"defect: step {step_index} does not open and close its region once")
    return SimpleNamespace(
        **{
            name: getattr(closed[0].counters, name) - getattr(opened[0].counters, name)
            for name in _COUNTER_FIELDS
        }
    )


def refusal_bundle(refusal: Any) -> FailureBundle:
    """T02 §7.4: the bundle of a plan refused for a missing EO derivative.

    Nothing was evaluated and no attempt opened, so every counter is zero and the attempt tree is
    empty — measured facts, not defaults. The unit is the first implicated source, the region's
    units and the specification follow.
    """
    error = refusal.error
    closing = refusal.trace.events[-1] if len(refusal.trace) else None
    counters = closing.counters if closing is not None else None
    taxonomy = TAXONOMY[refusal.outcome]
    return FailureBundle(
        outcome=refusal.outcome,
        taxonomy=taxonomy,
        observations={
            "closing_event": closing.kind if closing else None,
            "message": str(error),
            "unit": error.unit,
            "declared_method": error.method,
            "region_units": list(error.region_units),
            "specifications": list(refusal.specifications),
            "attempts": 0,
            "iterations": 0,
            "counters": {
                name: getattr(counters, name, 0)
                for name in (
                    "property_calls",
                    "requested_evaluations",
                    "cache_hits",
                    "residual_calls",
                    "jacobian_calls",
                    "factorizations",
                )
            },
        },
        inferred_causes=(),
        implicated_sources=(
            error.unit,
            *(unit for unit in error.region_units if unit != error.unit),
            *refusal.specifications,
        ),
        attempt_tree=(),
        replay_identity={
            "model_version": refusal.model_version,
            "constants_sha256": refusal.constants_sha256,
            "policy_id": refusal.policy_id,
            "plan_id": "",
        },
        suggested_actions=(
            SuggestedActionEntry(
                action=OUTCOME_ACTIONS[refusal.outcome],
                preconditions=(
                    f"{error.unit} declares its residual derivatives {error.method!r}; a model "
                    "change outside the solve, proposed to its author"
                ),
            ),
        ),
    )


def _merge_observation(result: Any) -> dict[str, Any]:
    decision = getattr(result, "merge_into_eo", None)
    if decision is None:
        return {}
    if decision == "unsupported":
        unit, method = result.merge_unsupported
        return {"merge_into_eo": f'unsupported({unit}, "derivatives: {method}")'}
    return {"merge_into_eo": str(decision)}


def _finite(value: float) -> float | None:
    return None if value != value or value in (float("inf"), float("-inf")) else float(value)
