"""The merge edge: a stalled Anderson loop re-solved as its EO region. T02 §4.4.

Blueprint §7.7's "recycle stagnation → … merge into EO", plan §4.3's recovery edge 2. A
`converge` step whose attempt closes with one of `MERGE_TRIGGERS` under `anderson` is re-solved,
once, by the region solve from the attempt's best iterate — the accepted iterate of least scaled
residual norm. Under `newton_tear` the same closures are K03's and there is no merge: a Newton that
has stalled with exact derivatives will not do better as the same Newton on a larger system.

When a loop unit is not EO-capable the merge is `unsupported(unit, method)`: the solve ends with
the recycle's own outcome and says why no merge was made. Nothing is invented in its place — no
secant, no control loop, no damping sweep (blueprint [A02]'s last sentence, applied to recycles).

The merge changes the *solver*, not the *problem*: the region's rows are the loop's rows, under the
same `model_version` and `constants_sha256` (A32). That is a property of the plan's
`region_on_merge`, which this module is handed, not something it constructs.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Final, Literal

import numpy as np
import numpy.typing as npt

from openflowsheet.canonical import state_sha256
from openflowsheet.numerics.anderson import RecyclePolicy, RecycleResult, solve_recycle
from openflowsheet.numerics.newton import Problem
from openflowsheet.orchestrator.roots import root_fingerprint
from openflowsheet.orchestrator.trace import Counters, SolveOutcome, Trace

__all__ = [
    "MERGE_TRIGGERS",
    "ConvergeResult",
    "converge_with_merge",
    "merge_due",
    "merged_provenance",
    "unsupported_note",
]

#: §4.4's trigger: the recycle attempt's closures after which the region is tried.
MERGE_TRIGGERS: Final = frozenset(
    {"RECYCLE_STAGNATION", "LINE_SEARCH_FAILED", "BOUND_BLOCKED", "BUDGET_EXHAUSTED"}
)


def merge_due(outcome: str, method: str) -> bool:
    """§4.4's trigger, decided in one place (review S2): a closure of `MERGE_TRIGGERS` under
    `anderson`. Under `newton_tear` the same closures are K03's and nothing is merged."""
    return method == "anderson" and outcome in MERGE_TRIGGERS


def unsupported_note(unit: str, method: str) -> str:
    """The registered wording of a merge that cannot be made (A32), in one place."""
    return f'merge_into_eo: unsupported({unit}, "derivatives: {method}")'


@dataclass(frozen=True)
class ConvergeResult:
    """A `converge` step under `anderson`, with its merge edge if it took one.

    It reads as a solve result to `verify.failure.bundle_for` (outcome, counters, message,
    attempts, iterations, residual_inf, checkpoint, plan), so a failed step has a bundle.
    """

    outcome: SolveOutcome
    x: npt.NDArray[np.float64]
    recycle: RecycleResult
    #: ADR 0009 D3's field: `None` when no merge was due, `"taken"` or `"unsupported"`.
    merge_into_eo: Literal["taken", "unsupported"] | None = None
    #: `(unit, method)` when `merge_into_eo == "unsupported"`.
    merge_unsupported: tuple[str, str] | None = None
    #: The region solve's own result when the merge was taken (a `NewtonResult` or a
    #: `RegionResult`), so its outcome, iterations and landing are read from the solver that ran.
    merged: Any = None
    residual_inf: float = float("nan")
    counters: Counters = field(default_factory=Counters)
    message: str = ""
    checkpoint: Any = None
    plan: Any = None
    #: ADR 0005 D7 (T03 §8.1): the loop's attempt, then the merged region's (a merge's region
    #: attempts follow the loop's).
    branch_provenance: tuple[Mapping[str, Any], ...] = ()
    #: T03 §8.2: issued on a converged step when the caller names the problem's identity.
    root_fingerprint: Mapping[str, Any] | None = None

    @property
    def converged(self) -> bool:
        return self.outcome == "CONVERGED"

    @property
    def attempts(self) -> int:
        """The recycle's one attempt, plus the merged solve's own (a `RegionResult` counts its
        attempts; a bare Newton is one)."""
        if self.merged is None:
            return 1
        return 1 + len(getattr(self.merged, "attempts", ()) or (None,))

    @property
    def iterations(self) -> int:
        merged = 0 if self.merged is None else int(self.merged.iterations)
        return self.recycle.iterations + merged


def converge_with_merge(
    problem: Problem,
    t0: npt.NDArray[np.float64],
    *,
    policy: RecyclePolicy | None = None,
    merge: Callable[[npt.NDArray[np.float64], Counters], Any] | None,
    merge_unsupported: tuple[str, str] | None = None,
    trace: Trace | None = None,
    identity: tuple[str, str] | None = None,
) -> ConvergeResult:
    """Run the recycle on `problem`; on a trigger, run `merge(best_x, counters)` once, or say why
    not.

    `merge` is the step's region solve started from the best iterate — for a flowsheet loop, the
    region Newton of §6 on `region_on_merge` from that iterate's traversal; for a manufactured map,
    the Newton on `R(t) = G(t) − t` itself (the loop's rows and nothing else). Its result must
    carry `outcome`, `iterations` and `counters`; it is handed the recycle's counters so that the
    merged solve's are cumulative, as K03's are across attempts. `merge_unsupported` is the plan's
    `merge_unsupported` (`(unit, method)`), and exactly one of the two is given.
    """
    if (merge is None) == (merge_unsupported is None):
        raise ValueError(
            "a converge step has either a region to merge into or a reason it has none"
        )
    recycle = solve_recycle(problem, t0, policy=policy, trace=trace)
    ids = tuple(problem.variable_ids)
    loop_item = _item(
        attempt=0,
        core="anderson",
        source="initializer",
        initializer_source="user_guess",
        opening_state_sha256=state_sha256(np.asarray(t0, dtype=np.float64), ids),
        core_outcome=recycle.outcome,
        iterations=recycle.iterations,
        decision="converged" if recycle.converged else "terminal",
        cause="" if recycle.converged else recycle.message,
    )

    def fingerprint(x: npt.NDArray[np.float64]) -> dict[str, Any] | None:
        if identity is None:
            return None
        return root_fingerprint(
            model_version=identity[0],
            constants_sha256=identity[1],
            variable_ids=ids,
            branch_found=(),
            full_state_sha256=state_sha256(x, ids),
        )

    residual_inf = (
        float(np.max(np.abs(recycle.residual)))
        if recycle.residual is not None and recycle.residual
        else float("nan")
    )
    if recycle.converged or not merge_due(recycle.outcome, "anderson"):
        return ConvergeResult(
            outcome=recycle.outcome,
            x=recycle.x,
            recycle=recycle,
            residual_inf=residual_inf,
            counters=recycle.counters,
            message=recycle.message,
            branch_provenance=(loop_item,),
            root_fingerprint=fingerprint(recycle.x) if recycle.converged else None,
        )
    if merge is None:
        assert merge_unsupported is not None
        unit, method = merge_unsupported
        return ConvergeResult(
            outcome=recycle.outcome,
            x=recycle.x,
            recycle=recycle,
            merge_into_eo="unsupported",
            merge_unsupported=merge_unsupported,
            residual_inf=residual_inf,
            counters=recycle.counters,
            message=f"{recycle.message}; {unsupported_note(unit, method)}",
            branch_provenance=(loop_item,),
        )
    start = recycle.best_x.copy()
    merged = merge(start, recycle.counters)
    # A merge that is a region solve carries its own attempts; a bare Newton on the loop's rows
    # (a manufactured map) is one attempt.
    region_items = tuple(getattr(merged, "branch_provenance", ())) or (
        _item(
            attempt=0,
            core="newton",
            source="initializer",
            initializer_source=None,
            opening_state_sha256=state_sha256(start, ids),
            core_outcome=str(merged.outcome),
            iterations=int(merged.iterations),
            decision="converged" if merged.outcome == "CONVERGED" else "terminal",
            cause="" if merged.outcome == "CONVERGED" else str(getattr(merged, "message", "")),
        ),
    )
    items = merged_provenance((loop_item,), region_items)
    x_final = np.asarray(getattr(merged, "x", recycle.best_x), dtype=np.float64)
    return ConvergeResult(
        outcome=merged.outcome,
        x=x_final,
        recycle=recycle,
        merge_into_eo="taken",
        merged=merged,
        residual_inf=float(getattr(merged, "residual_inf", float("nan"))),
        counters=merged.counters,
        message=str(getattr(merged, "message", "")),
        branch_provenance=items,
        root_fingerprint=fingerprint(x_final) if merged.outcome == "CONVERGED" else None,
    )


def merged_provenance(
    loop: Sequence[Mapping[str, Any]], region: Sequence[Mapping[str, Any]]
) -> tuple[dict[str, Any], ...]:
    """T03 §8.1 as amended (review S2): a merge's region attempts continue the loop's list.

    The loop's last item proposed the merge (`restart`, `cause = merge_into_eo`); the region's
    items follow with dense attempt numbers, the first opened from the loop's best iterate
    (`merge_best_iterate`, no initializer). The one function both merge paths use — the plan
    executor's and `converge_with_merge`.
    """
    items = [dict(item) for item in loop]
    items[-1] = {**items[-1], "decision": "restart", "cause": "merge_into_eo"}
    offset = len(items)
    for position, item in enumerate(region):
        continued = {**item, "attempt": offset + int(item["attempt"])}
        if position == 0:
            continued["opening_source"] = "merge_best_iterate"
            continued["initializer_source"] = None
        items.append(continued)
    return tuple(items)


def _item(
    *,
    attempt: int,
    core: str,
    source: str,
    initializer_source: str | None,
    opening_state_sha256: str,
    core_outcome: str,
    iterations: int,
    decision: str,
    cause: str,
) -> dict[str, Any]:
    """A `branch_provenance` item (T03 §8.1) for a bare recycle and its merge; no phases."""
    return {
        "attempt": attempt,
        "signature": [],
        "core": core,
        "opening_source": source,
        "initializer_source": initializer_source,
        "opening_trial": None,
        "opening_state_sha256": opening_state_sha256,
        "core_outcome": core_outcome,
        "iterations": iterations,
        "decision": decision,
        "cause": cause,
        "continuation": None,
    }
