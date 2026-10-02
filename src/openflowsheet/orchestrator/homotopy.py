"""The typed homotopy: specification continuation. T04 §4; ADR 0010 D2.

A region with a promoted specification row `v_j − p_j` (T02 §7.3) has a continuation parameter:
the pinned input `p_j`. The homotopy re-binds it from where the opening state already satisfies it
to its target,

    H(x, λ) = F(x; p(λ)),      p_j(λ) = p_j* + (1 − λ)(p_j⁰ − p_j*),      p_j⁰ = x⁰[v_j],

so every λ-level is a real flowsheet — the target's `model_version`, its own `constants_sha256` —
and the λ = 1 level is the target compiled instance itself, not a re-binding of it (§4.2). λ never
reaches the evaluation boundary: it lives here, as an exact dyadic fraction, and leaves only as
the parameter value it produces and as the `p/q` strings of the records.

The controller (§4.3) is natural-parameter continuation with K03's Newton core as the corrector,
unchanged in every rule and capped at `corrector_max_iterations`: a λ-trial is accepted iff its
corrector ends `CONVERGED`; Δλ doubles on acceptance and halves on rejection, and a rejection rolls
the state back to the last accepted level, discarding the corrector's end state. Δλ below
`delta_lambda_min` is `HOMOTOPY_STALLED` (§4.6), which brackets its obstruction to within
`2 Δλ_min` in λ. The homotopy never changes the active set (§4.5): a corrector that meets a phase
wall or a bound fails, and the λ-trial is rejected.

This module knows nothing of phases or regions: the region solve hands it a corrector per level
and a way to say which unit a rejected corrector's phase boundary belongs to.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from fractions import Fraction
from typing import Any, Literal

import numpy as np
import numpy.typing as npt

from openflowsheet.canonical import state_sha256
from openflowsheet.compile.spec import ProblemSpec
from openflowsheet.numerics.newton import NewtonResult
from openflowsheet.orchestrator.trace import (
    AttemptSignature,
    Counters,
    HomotopyPolicy,
    SolveOutcome,
    Trace,
    fraction_string,
)

__all__ = [
    "Continuation",
    "CorrectorOutcome",
    "HomotopyRecord",
    "HomotopyTrial",
    "continuation_parameter",
    "continue_specification",
    "level_values",
    "rebind",
]


@dataclass(frozen=True)
class Continuation:
    """A region's continuation parameter (§4.1): the pinned inputs of its promoted specification
    rows, and the columns those rows specify, in the same order."""

    type: Literal["specification_continuation"]
    parameter_ids: tuple[str, ...]
    variable_ids: tuple[str, ...]

    def as_context(self) -> dict[str, Any]:
        """`AttemptContext.continuation` (ADR 0010 D7.3)."""
        return {"type": self.type, "parameter_ids": list(self.parameter_ids)}


def continuation_parameter(
    *,
    specification_rows: Sequence[str],
    target_variables: Sequence[str],
    spec: ProblemSpec,
    structural_pattern: Sequence[tuple[str, str]],
) -> Continuation | None:
    """§4.1: the continuation parameter of a region, or `None` when it has none.

    A promoted specification row qualifies when it is of the written form `v − p`: its pinned
    input is the parameter the binding names after the row (`binding._promotion_row`), and its
    structural pattern is exactly the one column it specifies. Anything else is not a row this
    homotopy knows how to move, and a region with no qualifying row has no continuation — edge 3
    then records `unsupported(no_continuation_parameter)` (§5.2) rather than guessing.
    """
    if not specification_rows or len(specification_rows) != len(target_variables):
        return None
    columns: dict[str, set[str]] = {}
    for row, column in structural_pattern:
        columns.setdefault(row, set()).add(column)
    for row, column in zip(specification_rows, target_variables, strict=True):
        if row not in spec.parameters or column not in spec.variable_ids:
            return None
        if columns.get(row) != {column}:
            return None
    return Continuation(
        type="specification_continuation",
        parameter_ids=tuple(specification_rows),
        variable_ids=tuple(target_variables),
    )


def level_values(
    continuation: Continuation,
    target: Mapping[str, float],
    opening: Mapping[str, float],
    lam: Fraction,
) -> dict[str, float]:
    """§4.2: `p_j(λ) = p_j* + (1 − λ)(p_j⁰ − p_j*)`, formed exactly and rounded once.

    The arithmetic is done in exact rationals (every double is one), so each level's value is the
    correctly rounded point on the path and does not depend on an evaluation order. `p(1)` is never
    formed: the λ = 1 level is the target instance itself."""
    if lam == 1:
        raise ValueError("the λ = 1 level is the target instance itself; it is never re-bound")
    values: dict[str, float] = {}
    pairs = zip(continuation.parameter_ids, continuation.variable_ids, strict=True)
    for parameter, column in pairs:
        star = Fraction(target[parameter])
        start = Fraction(opening[column])
        values[parameter] = float(star + (1 - lam) * (start - star))
    return values


def rebind(spec: ProblemSpec, values: Mapping[str, float]) -> ProblemSpec:
    """A λ-level's declaration: `spec` with pinned inputs replaced **by id**, nothing else.

    ADR 0008 D1.2(ii)/D1.3: a stage-varying specification is a re-bound pinned input, identified
    by the instance's `(model_version, constants_sha256)`. Every equation, block and scale is the
    target's; a value for an id the declaration does not pin is refused, not added."""
    unknown = sorted(set(values) - set(spec.parameters))
    if unknown:
        raise ValueError(f"re-binding names pinned inputs the declaration does not have: {unknown}")
    return replace(spec, parameters={**spec.parameters, **values})


@dataclass(frozen=True)
class CorrectorOutcome:
    """One λ-trial's corrector: K03's result, the level's identity, and — for a corrector that
    stopped at a phase wall or on a watched variable's bound — the unit concerned (§4.6)."""

    result: NewtonResult
    level_constants_sha256: str
    boundary_unit: str | None = None


@dataclass(frozen=True)
class HomotopyTrial:
    """One λ-trial (index 0 is the easy endpoint) and its verdict."""

    index: int
    lambda_value: Fraction
    delta_lambda: Fraction
    accepted: bool
    corrector: CorrectorOutcome


@dataclass(frozen=True)
class HomotopyRecord:
    """What the homotopy did (§4.7): its trials in order, where it got to, and — on a stall — the
    one hypothesis §4.6's vocabulary infers. The hypothesis is never an observation."""

    continuation: Continuation
    trials: tuple[HomotopyTrial, ...]
    lambda_reached: Fraction
    #: The attempt's free columns, the order of every corrector's `x`.
    variable_ids: tuple[str, ...]
    #: `easy_endpoint` when the λ = 0 corrector failed, `resolution` when Δλ fell below its
    #: minimum; `None` on every other end.
    stalled_at: Literal["easy_endpoint", "resolution"] | None = None
    inferred_cause: str | None = None

    @property
    def lambda_levels(self) -> tuple[Fraction, ...]:
        """The accepted λ-levels after the easy endpoint, in order."""
        return tuple(trial.lambda_value for trial in self.trials[1:] if trial.accepted)

    @property
    def rejected_trials(self) -> int:
        return sum(1 for trial in self.trials if not trial.accepted)

    def provenance(self) -> dict[str, Any]:
        """The `branch_provenance` item's `continuation` (ADR 0010 D7.5)."""
        return {
            "type": self.continuation.type,
            "parameter_ids": list(self.continuation.parameter_ids),
            "lambda_levels": [fraction_string(level) for level in self.lambda_levels],
            "lambda_reached": fraction_string(self.lambda_reached),
            "rejected_trials": self.rejected_trials,
        }


#: A corrector for one level: `(λ, start, counters) -> outcome`, run by the caller in the frozen
#: signature on the level's instance and context.
Corrector = Callable[[Fraction, npt.NDArray[np.float64], Counters], CorrectorOutcome]


def _inferred_cause(rejections: Sequence[CorrectorOutcome], signature: AttemptSignature) -> str:
    """§4.6's table, over the corrector outcomes of the rejections since the last acceptance."""
    outcomes = [rejection.result.outcome for rejection in rejections]
    if rejections and all(
        rejection.boundary_unit is not None
        and rejection.result.outcome in ("BOUND_BLOCKED", "PHASE_UPDATE_REQUIRED")
        for rejection in rejections
    ):
        order = [unit for unit, _ in signature]
        units = {
            rejection.boundary_unit
            for rejection in rejections
            if rejection.boundary_unit is not None
        }
        first = min(units, key=lambda unit: order.index(unit) if unit in order else len(order))
        return f"phase_boundary_on_path({first})"
    if outcomes and all(outcome == "LINEAR_SOLVE_FAILED" for outcome in outcomes):
        return "singular_path_or_fold"
    return "corrector_failure"


def continue_specification(
    *,
    correct: Corrector,
    x0: npt.NDArray[np.float64],
    continuation: Continuation,
    policy: HomotopyPolicy,
    trace: Trace,
    attempt: int,
    signature: AttemptSignature,
    variable_ids: Sequence[str],
    counters: Counters,
) -> tuple[NewtonResult, HomotopyRecord]:
    """§4.3's controller, run as the core of one attempt. Returns the core's result in the shape
    `phase_contract.decide` reads, and the record of what it did.

    The core outcome is `CONVERGED` at λ = 1, or `HOMOTOPY_STALLED`, `BUDGET_EXHAUSTED` with budget
    `homotopy_steps`, or `EVALUATION_ERROR` (a corrector's defect, never a rejection). On every end
    but `CONVERGED` the reported state is the last accepted level's root — rollback's evidence —
    with the residual of *that level's* problem, never a corrector's end state.
    """
    trials: list[HomotopyTrial] = []
    iterations = 0
    running = counters

    def run(index: int, lam: Fraction, start: npt.NDArray[np.float64]) -> CorrectorOutcome:
        nonlocal running, iterations
        trace.open_level(index)
        try:
            outcome = correct(lam, start, running)
        finally:
            trace.close_level()
        running = outcome.result.counters
        iterations += outcome.result.iterations
        return outcome

    def record(trial: HomotopyTrial, message: str = "") -> None:
        result = trial.corrector.result
        trace.record(
            kind="homotopy_step",
            attempt=attempt,
            iteration=trial.index,
            signature=signature,
            state_sha256=state_sha256(result.x, variable_ids),
            residual_inf_unscaled=result.residual_inf,
            merit=result.merit,
            counters=running,
            trial_status="accepted" if trial.accepted else "rejected",
            message=message,
            lambda_value=fraction_string(trial.lambda_value),
            delta_lambda=fraction_string(trial.delta_lambda),
            corrector_outcome=result.outcome,
            corrector_iterations=result.iterations,
            level_constants_sha256=trial.corrector.level_constants_sha256,
        )

    def closed(
        outcome: SolveOutcome,
        at: NewtonResult | None,
        record_: HomotopyRecord,
        *,
        message: str = "",
        budget: str | None = None,
    ) -> tuple[NewtonResult, HomotopyRecord]:
        """The attempt's end: at `at`, the last accepted level's corrector result (or nothing,
        when even the easy endpoint failed — then the opening, with no residual to report)."""
        if at is None:
            x = np.array(x0, dtype=np.float64)
            residual: tuple[float, ...] = ()
            residual_inf = merit = float("nan")
        else:
            x, residual, residual_inf, merit = at.x, at.residual, at.residual_inf, at.merit
        trace.record(
            kind="attempt_closed",
            attempt=attempt,
            iteration=iterations,
            signature=signature,
            state_sha256=state_sha256(x, variable_ids),
            residual_inf_unscaled=residual_inf,
            merit=merit,
            counters=running,
            outcome=outcome,
            message=message,
        )
        result = NewtonResult(
            outcome=outcome,
            x=x,
            residual=residual,
            residual_inf=residual_inf,
            merit=merit,
            iterations=iterations,
            counters=running,
            converged=outcome == "CONVERGED",
            budget=budget,
            message=message,
            accepted_any=at is not None,
        )
        return result, record_

    def summary(
        reached: Fraction,
        stalled_at: Literal["easy_endpoint", "resolution"] | None = None,
        cause: str | None = None,
    ) -> HomotopyRecord:
        return HomotopyRecord(
            continuation=continuation,
            trials=tuple(trials),
            lambda_reached=reached,
            variable_ids=tuple(variable_ids),
            stalled_at=stalled_at,
            inferred_cause=cause,
        )

    # §4.3.1: the easy endpoint, from the opening state.
    zero = Fraction(0)
    easy = run(0, zero, np.array(x0, dtype=np.float64))
    trials.append(HomotopyTrial(0, zero, zero, easy.result.converged, easy))
    if easy.result.outcome == "EVALUATION_ERROR":
        record(trials[-1])
        return closed("EVALUATION_ERROR", None, summary(zero), message=easy.result.message)
    if not easy.result.converged:
        message = f"homotopy_stalled({easy.result.outcome})"
        record(trials[-1], message)
        cause = _inferred_cause([easy], signature)
        return closed(
            "HOMOTOPY_STALLED",
            None,
            summary(zero, "easy_endpoint", cause),
            message=message,
        )
    record(trials[-1])

    accepted = easy.result
    lam, step = zero, Fraction(policy.delta_lambda_initial)
    rejections: list[CorrectorOutcome] = []
    for index in range(1, policy.max_lambda_trials + 1):
        # §4.3.2: the trial and its corrector, from the last accepted state.
        trial_lambda = min(lam + step, Fraction(1))
        outcome = run(index, trial_lambda, accepted.x)
        verdict = outcome.result.converged
        trials.append(HomotopyTrial(index, trial_lambda, trial_lambda - lam, verdict, outcome))
        if outcome.result.outcome == "EVALUATION_ERROR":
            # §4.3.4: a defect, not a rejection (K03 §5.5). The step's message stays in §10's
            # grammar; the corrector's own message is on its `attempt_closed` and on the result.
            record(trials[-1])
            return closed(
                "EVALUATION_ERROR", accepted, summary(lam), message=outcome.result.message
            )
        if verdict:
            # §4.3.3: accepted — the checkpoint moves; Δλ grows, never past λ = 1.
            record(trials[-1])
            lam, accepted, rejections = trial_lambda, outcome.result, []
            if lam == 1:
                return closed("CONVERGED", accepted, summary(lam))
            step = min(step * policy.growth, 1 - lam)
            continue
        # §4.3.4: rejected — roll back (the corrector's end state is discarded) and shrink.
        rejections.append(outcome)
        step = step * policy.shrink
        if step < policy.delta_lambda_min:
            message = f"homotopy_stalled({outcome.result.outcome})"
            record(trials[-1], message)
            return closed(
                "HOMOTOPY_STALLED",
                accepted,
                summary(lam, "resolution", _inferred_cause(rejections, signature)),
                message=message,
            )
        record(trials[-1])

    # §4.3.5: the λ-trial budget.
    return closed(
        "BUDGET_EXHAUSTED",
        accepted,
        summary(lam),
        message=f"{policy.max_lambda_trials} λ-trials without reaching λ = 1",
        budget="homotopy_steps",
    )
