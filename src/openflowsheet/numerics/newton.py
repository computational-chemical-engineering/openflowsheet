"""Damped Newton with a bound-aware line search. K03 specification §5.

Written for a generic square problem `F(x) = 0` so that it can be exercised on problems with no
thermodynamics in them at all — `NUM-02`'s affine recycle, a bound that blocks, an evaluator with
a domain, a residual with no root. The SYN-001 tear is one instance of it and arrives later; a
solver first tested on the problem it was written for has been tested against itself.

Four things here are not the textbook and each is a rule from the blueprint or the specification:

- **Convergence is tested on the *unscaled* residual, row by row, against the registered
  tolerance, and before any Jacobian is evaluated.** Blueprint §7.3: "an already valid root need
  not take a small additional step to qualify", and verification tolerances stay independent of
  numerical scaling. A root passed in converges at iteration 0 with no factorization.
- **A small step is never evidence of convergence** (§5.7). Stagnation is a ratio of merits over
  a window, which separates the two cases blueprint §7.3 names: a small step with a small
  residual has already converged above; a small step with a large residual has `q ≈ 1`.
- **A trial that cannot be evaluated is shortened, not clipped and not retried** (§5.5). A typed
  non-`ok` status is a *result* — it is recorded with its unit and message and the step halves,
  which is blueprint §7.7's authorized action for an invalid trial.
- **A component that reaches its bound lands on it exactly** (§5.3), at `+0.0` rather than at
  `-4e-16`. ADR 0001 D3.1 makes exact zero the difference between a dormant stream and a flowing
  one, so a bound landing that misses by an ulp changes what the state *means*.
- **Structural zeros are released before `BOUND_BLOCKED` is declared** (§5.3 as amended, R-064):
  where the exact Newton step on a set of components sitting on their bounds is provably zero,
  the factorization's roundoff there is discarded rather than read as an outward direction —
  and, since R-782, at every step where it is nonzero, so that roundoff pointing inward cannot
  lift the set off its bound either (S10-C absent-component note §4.1).

One more is optional and off unless the caller supplies it (ADR 0018, `eo_core =
"newton_refined"`): a `CONVERGED` exit at `k ≥ 1` whose chord correction — one back-solve against
the attempt's last factorization — exceeds the kind tolerance on some column takes **one** more
iteration, kept only if it achieved the tolerance. It never changes the attempt's outcome (D4). Its
calls are metered like any iteration's, so under a property budget the solve can end
`BUDGET_EXHAUSTED(property_calls)` where `newton` would converge (ADR 0018 D4′, T06 A96).
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

import numpy as np
import numpy.typing as npt
import scipy.sparse as sp
from scipy.sparse.csgraph import maximum_bipartite_matching

from openflowsheet.canonical import normalize_zero, state_sha256
from openflowsheet.numerics.linear import (
    KeptFactorization,
    LinearSolveFailedError,
    LinearSolveRecord,
    solve_linear,
    solve_linear_kept,
)
from openflowsheet.numerics.scaling import Scaling
from openflowsheet.numerics.solve_record import (
    AttemptSignature,
    Counters,
    LinearRecord,
    RejectionReason,
    SolveOutcome,
    SolvePolicy,
    Trace,
)

EvaluationStatus = Literal[
    "ok", "invalid_trial_state", "out_of_domain", "unsupported", "not_converged", "error"
]


@dataclass(frozen=True)
class Evaluation:
    """What a residual evaluator returns: an answer, or a typed reason there is none.

    `signature` lets the caller detect blueprint [A01]'s phase-update condition without the core
    knowing anything about phases: the core compares it with the attempt's and rejects a trial
    that differs, which is §5.4(ii).
    """

    status: EvaluationStatus
    values: tuple[float, ...] | None = None
    signature: AttemptSignature | None = None
    message: str = ""

    def __post_init__(self) -> None:
        if self.status == "ok" and self.values is None:
            raise ValueError("an ok evaluation must carry values")
        if self.status != "ok" and self.values is not None:
            raise ValueError(f"a {self.status!r} evaluation must not carry values")


def another_signature(
    frozen: AttemptSignature,
    reported: AttemptSignature | None,
    *,
    compare_empty: bool = False,
) -> bool:
    """§5.4(ii): a trial whose evaluation reports a signature other than the attempt's frozen one
    is phase-rejected; an evaluation that reports none (`None`) never is.

    An empty frozen signature is compared only when the caller says so (`compare_empty`): T05b
    spec §7.8 (iii), ruled 2026-09-25 (Q-S4 (6)) — every trial of a v2 attempt in a region with a
    dormancy-form outlet is screened, and such an attempt opens with `()` when no item is active,
    so a trial that makes a trigger exactly dormant reports the item. Elsewhere `()` is what a
    caller that freezes no signature passes (K03's tear problem, driven directly, reports the
    flash's), and it is not compared, as before."""
    if not frozen and not compare_empty:
        return False
    return reported is not None and reported != frozen


class JacobianUnavailableError(RuntimeError):
    """The derivative could not be evaluated at an iterate whose residual was (T04 review M1).

    A failed Jacobian is not a zero matrix: factoring one turned an evaluation defect into a
    globalization failure, a false `CONVERGED` at a PTC polish, or a SuperLU crash. A problem's
    `jacobian` raises this instead, and a core ends the attempt `EVALUATION_ERROR` (K03 §5.5) —
    never a rejection, never a step. `status` is the evaluator's own."""

    def __init__(self, status: str, message: str = "") -> None:
        super().__init__(f"{status}: {message}" if message else status)
        self.status = status


class IterationObserver(Protocol):
    """What the core tells a controller about rejected trials, and what it asks back.

    The core stays generic: it knows a trial was rejected and for which registered reason, and
    it asks after each iteration whether to close. *Which* rejections matter, and what to do
    about them, is the controller's policy — §9's, not §5's. Without this the controller would
    have to infer iteration numbers and step lengths from outside, which is guessing.
    """

    def rejected(
        self,
        iteration: int,
        alpha: float,
        x: npt.NDArray[np.float64],
        reason: RejectionReason,
        signature: AttemptSignature | None,
    ) -> None: ...

    def should_close(self, iteration: int) -> SolveOutcome | None: ...


def _notify_landing(
    observer: IterationObserver | None,
    iteration: int,
    landing: tuple[int, ...],
    x: npt.NDArray[np.float64],
) -> None:
    """T02 §6.3.3's hook: after a full step lands components exactly on their bounds, say which.

    Optional and additive. An observer that defines `landed(iteration, indices, x)` hears about
    it; K03's phase-wall observer does not define it and nothing changes for the tear path. The
    EO region needs it because on the lifted form a phase *leaves* when its total lands on zero,
    and that is a fact about the accepted iterate that no rejection ever reports.
    """
    hook = getattr(observer, "landed", None)
    if hook is not None and landing:
        hook(iteration, landing, x)


ResidualEvaluator = Callable[[npt.NDArray[np.float64]], Evaluation]
#: Returns the unscaled Jacobian of `F` at `x`, in any form `scipy.sparse` accepts.
JacobianEvaluator = Callable[[npt.NDArray[np.float64]], sp.spmatrix | npt.NDArray[np.float64]]


@dataclass(frozen=True)
class NewtonResult:
    """Where the attempt got to, and why it stopped."""

    outcome: SolveOutcome
    x: npt.NDArray[np.float64]
    residual: tuple[float, ...]
    residual_inf: float
    merit: float
    iterations: int
    counters: Counters
    converged: bool = False
    budget: str | None = None
    linear_reason: str | None = None
    message: str = ""
    accepted_any: bool = False
    #: T02 §4.4: the accepted iterate of least scaled residual norm, where a core tracks one
    #: (the Anderson recycle does; K03's Newton does not, and leaves it `None`).
    best_x: npt.NDArray[np.float64] | None = None
    #: On `BOUND_BLOCKED`: the variables on their bound that the direction points out of.
    blocked_by: tuple[str, ...] = ()


@dataclass(frozen=True)
class _Converged:
    """ADR 0018 D2: the row-converged iterate `x_k` a terminal refinement starts from, and what
    the attempt returns if the refinement is reverted or abandoned (D4)."""

    x: npt.NDArray[np.float64]
    values: tuple[float, ...]
    iteration: int
    accepted_any: bool
    #: The chord's `max_j ρ_j` at `x_k` and the column it was reached on.
    ratio: float
    column: str

    def message(self, result: str) -> str:
        """D5's closing message: `terminal_refinement(<result>): chord <ρ_max!r> at <column>`."""
        return f"terminal_refinement({result}): chord {self.ratio!r} at {self.column}"


@dataclass(frozen=True)
class Problem:
    """A square residual problem with bounds, ids and a tolerance per row."""

    variable_ids: tuple[str, ...]
    row_ids: tuple[str, ...]
    residual: ResidualEvaluator
    jacobian: JacobianEvaluator
    scaling: Scaling
    #: Absolute acceptance tolerance per row id, the `a_i + r_i s_i` of blueprint §8.1 already
    #: summed: the rule is registered per quantity kind and the sum is what a row is judged by.
    row_tolerance: Mapping[str, float]
    lower_bounds: Mapping[str, float] = field(default_factory=dict)
    #: What the derivative evaluation measured about itself, recorded on the `jacobian` event.
    #: The SYN-001 tear computes the inner-consistency residual eta on every Jacobian (§3.4)
    #: and used to discard it, which left `SolveEvent.inner_consistency` a field with no writer
    #: and assertion A24's trace clause unverifiable from a trace.
    jacobian_diagnostics: Callable[[], Mapping[str, Any] | None] | None = None
    #: Linear solves performed *inside* `jacobian`, returned so the core can record them.
    #: A reduced problem assembles its derivative with a solve of its own -- the SYN-001 tear's
    #: Schur complement is one 44 x 44 factorization per Jacobian -- and ADR 0004 D2/D3 require
    #: every solve on a K03 path to carry its record onto a `SolveEvent`. Without this hook the
    #: only recorded solve is the 3 x 3 reduced system, and the trace understates both the
    #: factorization count and the evidence by the larger of the two.
    jacobian_evidence: Callable[[], Sequence[LinearSolveRecord]] | None = None

    def tolerance_vector(self) -> npt.NDArray[np.float64]:
        return np.array([self.row_tolerance[name] for name in self.row_ids], dtype=np.float64)

    def lower_bound_vector(self) -> npt.NDArray[np.float64]:
        return np.array(
            [self.lower_bounds.get(name, -np.inf) for name in self.variable_ids],
            dtype=np.float64,
        )


def solve_newton(
    problem: Problem,
    x0: Sequence[float] | npt.NDArray[np.float64],
    policy: SolvePolicy,
    *,
    trace: Trace,
    signature: AttemptSignature = (),
    attempt: int = 0,
    counters: Counters | None = None,
    observer: IterationObserver | None = None,
    compare_empty: bool = False,
    opening: Sequence[float] | npt.NDArray[np.float64] | None = None,
    refinement: Mapping[str, float] | None = None,
) -> NewtonResult:
    """Run the damped Newton of §5 and record every decision on `trace`.

    `compare_empty` screens trials against an empty frozen `signature` too (`another_signature`;
    T05b spec §7.8 (iii)); only the region sets it, for a v2 attempt with a dormancy-form outlet.

    `opening` is the attempt's opening state, where a released component must already sit on its
    bound (§5.3 as amended; note of 2026-09-25, T05b Q-S13). A caller that runs one attempt
    through several calls — T04's homotopy corrector — passes the attempt's `x⁰`; by default the
    call's start is the opening.

    `refinement` enables ADR 0018's terminal refinement (D2–D4): the kind tolerance `τ_kind` of
    each free column that has one, by column id; a column it omits is never judged. `None` — every
    caller but an EO region under `eo_core = "newton_refined"` — is K03 §5's core unchanged."""
    x = np.array([normalize_zero(float(value)) for value in x0], dtype=np.float64)
    if opening is None:
        opened = x.copy()
    else:
        opened = np.array([normalize_zero(float(value)) for value in opening], dtype=np.float64)
        if opened.shape != x.shape:
            raise ValueError(f"opening has {opened.size} components, the start {x.size}")
    run = _NewtonRun(
        problem=problem,
        policy=policy,
        trace=trace,
        signature=signature,
        attempt=attempt,
        observer=observer,
        compare_empty=compare_empty,
        opened=opened,
        tolerance=problem.tolerance_vector(),
        lower=problem.lower_bound_vector(),
        x=x,
        running=counters or Counters(),
        merits=[],
        column_tolerance=(
            None
            if refinement is None
            else np.array([refinement.get(name, np.inf) for name in problem.variable_ids])
        ),
    )

    evaluation, run.running = run.evaluate(run.x)
    if evaluation.status != "ok" or evaluation.values is None:
        outcome: SolveOutcome = (
            "EVALUATION_ERROR" if evaluation.status == "error" else "LINE_SEARCH_FAILED"
        )
        return run.finish(
            outcome,
            tuple(np.full(len(problem.row_ids), np.nan)),
            message=f"the initial point could not be evaluated: {evaluation.status}: "
            f"{evaluation.message}",
            iterations=0,
            accepted_any=False,
        )
    run.values = evaluation.values
    run.accepted_any = False

    for iteration in range(policy.max_iterations_per_attempt + 1):
        array = np.asarray(run.values, dtype=np.float64)
        infinity = float(np.max(np.abs(array))) if array.size else 0.0
        merit = problem.scaling.merit(run.values, problem.row_ids)

        # §5.2: the convergence test, on the unscaled residual, before any Jacobian.
        closed = run._closing_at_convergence(iteration, array)
        if closed is not None:
            return closed

        if iteration == policy.max_iterations_per_attempt:
            return run.finish(
                "BUDGET_EXHAUSTED",
                run.values,
                budget="newton_iterations",
                message=f"{iteration} accepted iterations without convergence",
                iterations=iteration,
                accepted_any=run.accepted_any,
            )

        # §5.7: stagnation, on accepted steps only, before spending another factorization.
        closed = run._stagnation(iteration)
        if closed is not None:
            return closed

        matrices = run._jacobian(iteration, infinity, merit)
        if isinstance(matrices, NewtonResult):
            return matrices
        unscaled, scaled = matrices
        solved = run._linear_step(iteration, scaled, infinity, merit)
        if isinstance(solved, NewtonResult):
            return solved
        step_scaled = solved

        direction = problem.scaling.unscale_state(step_scaled, problem.variable_ids)
        direction, alpha_max, landing, released = _bound_aware_step(
            run.x, direction, run.lower, opening=run.opened, residual=run.values, jacobian=unscaled
        )
        if released:
            # The step taken is the exact Newton step on the released set; so is its record.
            step_scaled = step_scaled.copy()
            step_scaled[list(released)] = 0.0
        if alpha_max == 0.0:
            return run.finish(
                "BOUND_BLOCKED",
                run.values,
                blocked_by=tuple(problem.variable_ids[index] for index in landing),
                message=(
                    "a component sits on its lower bound and the Newton direction points out of "
                    "the feasible set; no trial can be taken along it"
                ),
                iterations=iteration,
                accepted_any=run.accepted_any,
            )

        accepted = False
        for halving in range(policy.step_halvings_max + 1):
            alpha = alpha_max / (2.0**halving)
            trial = _trial_point(
                run.x, direction, alpha, run.lower, landing if halving == 0 else ()
            )
            trial_evaluation, run.running = run.evaluate(trial)
            step_inf = float(np.max(np.abs(step_scaled))) * alpha

            reason: RejectionReason | None = None
            trial_values: tuple[float, ...] | None = None
            if trial_evaluation.status == "error":
                trace.record(
                    kind="trial",
                    attempt=attempt,
                    iteration=iteration,
                    signature=signature,
                    state_sha256=run.digest(trial),
                    residual_inf_unscaled=float("nan"),
                    merit=float("nan"),
                    counters=run.running,
                    alpha=alpha,
                    step_inf_scaled=step_inf,
                    trial_status="rejected",
                    message=trial_evaluation.message,
                )
                return run.finish(
                    "EVALUATION_ERROR",
                    run.values,
                    message=trial_evaluation.message,
                    iterations=iteration,
                    accepted_any=run.accepted_any,
                )
            if trial_evaluation.status != "ok" or trial_evaluation.values is None:
                reason = "invalid_trial"
            elif another_signature(
                signature, trial_evaluation.signature, compare_empty=compare_empty
            ):
                reason = "phase_update_required"
            else:
                trial_values = trial_evaluation.values
                trial_merit = problem.scaling.merit(trial_values, problem.row_ids)
                if trial_merit > (1.0 - 2.0 * policy.armijo_c * alpha) * merit:
                    reason = "armijo"

            if reason is not None:
                trace.record(
                    kind="trial",
                    attempt=attempt,
                    iteration=iteration,
                    signature=trial_evaluation.signature or signature,
                    state_sha256=run.digest(trial),
                    residual_inf_unscaled=(
                        float(np.max(np.abs(trial_values))) if trial_values else float("nan")
                    ),
                    merit=(
                        problem.scaling.merit(trial_values, problem.row_ids)
                        if trial_values
                        else float("nan")
                    ),
                    counters=run.running,
                    alpha=alpha,
                    step_inf_scaled=step_inf,
                    trial_status="rejected",
                    rejection_reason=reason,
                    message=trial_evaluation.message,
                )
                if observer is not None:
                    observer.rejected(iteration, alpha, trial, reason, trial_evaluation.signature)
                continue

            assert trial_values is not None
            next_merit = problem.scaling.merit(trial_values, problem.row_ids)
            run.merits.append(next_merit / merit if merit > 0.0 else 0.0)
            run.x = trial
            run.values = trial_values
            accepted = True
            run.accepted_any = True
            trace.record(
                kind="step_accepted",
                attempt=attempt,
                iteration=iteration,
                signature=signature,
                state_sha256=run.digest(run.x),
                residual_inf_unscaled=float(np.max(np.abs(np.asarray(run.values)))),
                merit=next_merit,
                counters=run.running,
                alpha=alpha,
                step_inf_scaled=step_inf,
                trial_status="accepted",
            )
            if halving == 0:
                _notify_landing(observer, iteration, landing, run.x)
            break

        if observer is not None:
            requested = observer.should_close(iteration)
            if requested is not None:
                return run.finish(
                    requested,
                    run.values,
                    message=(
                        "the attempt controller closed the attempt: a persistent phase wall, "
                        "not an overshoot (§9.3)"
                    ),
                    iterations=iteration + (1 if accepted else 0),
                    accepted_any=run.accepted_any,
                )

        if not accepted:
            return run.finish(
                "LINE_SEARCH_FAILED",
                run.values,
                message=(
                    f"no trial accepted in {policy.step_halvings_max + 1} steps from "
                    f"alpha = {alpha_max}"
                ),
                iterations=iteration,
                accepted_any=run.accepted_any,
            )

    raise AssertionError("unreachable: the iteration budget is checked inside the loop")


@dataclass
class _NewtonRun:
    """One call of `solve_newton`: its fixed frame and the state carried between iterations.

    The state: the iterate `x`, its residual `values`, whether a step was accepted, the counters,
    and the merit ratios of the accepted steps (§5.7). ADR 0018: the column tolerances, the
    attempt's last factorization (`kept`), the iterate a refinement started from (`refining`), and
    the last chord solve's record (`chord_linear`; D5: it goes on the closing event).
    """

    problem: Problem
    policy: SolvePolicy
    trace: Trace
    signature: AttemptSignature
    attempt: int
    observer: IterationObserver | None
    compare_empty: bool
    opened: npt.NDArray[np.float64]
    tolerance: npt.NDArray[np.float64]
    lower: npt.NDArray[np.float64]
    column_tolerance: npt.NDArray[np.float64] | None
    x: npt.NDArray[np.float64]
    running: Counters
    merits: list[float]
    kept: KeptFactorization | None = None
    refining: _Converged | None = None
    chord_linear: LinearRecord | None = None
    values: tuple[float, ...] = field(init=False)
    accepted_any: bool = field(init=False)

    def evaluate(self, vector: npt.NDArray[np.float64]) -> tuple[Evaluation, Counters]:
        """Count one residual call on `running`, then evaluate `vector`; returns both.

        The count comes first, so it stands when `problem.residual` raises.
        """
        self.running = self.running.plus(residual_calls=1)
        return self.problem.residual(vector), self.running

    def finish(
        self,
        outcome: SolveOutcome,
        values: tuple[float, ...],
        *,
        message: str = "",
        budget: str | None = None,
        linear_reason: str | None = None,
        iterations: int,
        accepted_any: bool,
        blocked_by: tuple[str, ...] = (),
        linear: LinearRecord | None = None,
    ) -> NewtonResult:
        """Write `attempt_closed` on `trace` and return the attempt's result at `x`.

        Inside a refinement (ADR 0018 D4) it first restores `x` to the iterate the refinement
        started from and clears `refining`, and closes `CONVERGED` there instead.
        """
        if self.refining is not None:
            # ADR 0018 D4: whatever would have ended the attempt inside its refinement abandons
            # the refinement; the attempt returns `x_k`, `CONVERGED`, with its counters as spent.
            start, self.refining = self.refining, None
            self.x = start.x
            ended = f"{outcome}({budget})" if budget else outcome
            return self.finish(
                "CONVERGED",
                start.values,
                message=start.message(f"abandoned: {ended}"),
                iterations=start.iteration,
                accepted_any=start.accepted_any,
                linear=self.chord_linear,
            )
        array = np.asarray(values, dtype=np.float64)
        infinity = float(np.max(np.abs(array))) if array.size else 0.0
        merit = self.problem.scaling.merit(values, self.problem.row_ids)
        self.trace.record(
            kind="attempt_closed",
            attempt=self.attempt,
            iteration=iterations,
            signature=self.signature,
            state_sha256=self.digest(self.x),
            residual_inf_unscaled=infinity,
            merit=merit,
            counters=self.running,
            outcome=outcome,
            message=message,
            linear=linear,
        )
        return NewtonResult(
            outcome=outcome,
            x=self.x,
            residual=values,
            residual_inf=infinity,
            merit=merit,
            iterations=iterations,
            counters=self.running,
            converged=outcome == "CONVERGED",
            budget=budget,
            linear_reason=linear_reason,
            message=message,
            accepted_any=accepted_any,
            blocked_by=blocked_by,
        )

    def digest(self, vector: npt.NDArray[np.float64]) -> str:
        return state_sha256(vector, self.problem.variable_ids)

    def _closing_at_convergence(
        self, iteration: int, array: npt.NDArray[np.float64]
    ) -> NewtonResult | None:
        """§5.2's convergence test on the unscaled residual `array` of `values`; ADR 0018's exits.

        Returns the closing result, or None when the loop goes on: rows unconverged outside a
        refinement, or D3's one more iteration from `_refinement`. Converged at iteration 0, or
        without column tolerances or a kept factorization, it closes `CONVERGED`; converged
        otherwise, it returns `_refinement`'s answer. Unconverged inside a refinement (D4), it
        restores `x` to `x_k`, clears `refining` and closes `CONVERGED` there. Every close writes
        `attempt_closed` through `finish`.
        """
        if bool(np.all(np.abs(array) <= self.tolerance)):
            if self.column_tolerance is None or self.kept is None or iteration == 0:
                return self.finish(
                    "CONVERGED", self.values, iterations=iteration, accepted_any=self.accepted_any
                )
            return self._refinement(iteration, self.kept, self.column_tolerance)
        if self.refining is not None:
            # D4: the refined iterate does not pass every row; the attempt returns `x_k`.
            start, self.refining = self.refining, None
            self.x = start.x
            return self.finish(
                "CONVERGED",
                start.values,
                message=start.message("reverted: rows unconverged"),
                iterations=start.iteration,
                accepted_any=start.accepted_any,
                linear=self.chord_linear,
            )
        return None

    def _refinement(
        self, iteration: int, kept: KeptFactorization, column_tolerance: npt.NDArray[np.float64]
    ) -> NewtonResult | None:
        """ADR 0018 D2 to D4 at a converged iterate `x`, with the fields `kept` and
        `column_tolerance` (the caller has checked both are set).

        The chord correction with the last factorization (D2) sets `chord_linear` when the
        back-solve succeeds. Inside a refinement it judges the refined iterate (D4): it keeps it
        or restores `x` to `x_k`, clears `refining`, and closes `CONVERGED`. Outside one a failed
        back-solve closes `CONVERGED` ("abandoned: chord"); else it closes `CONVERGED` when the
        chord is within the kind tolerance or at the iteration budget, and otherwise opens the
        refinement (D3: sets `refining`) and returns None for one more iteration. Every close
        writes `attempt_closed` through `finish`.
        """
        # ADR 0018 D2: the chord correction at this iterate with the last factorization.
        try:
            ratio, column, self.chord_linear = _chord(
                self.problem, kept, self.values, column_tolerance
            )
        except LinearSolveFailedError as failure:
            # ADR 0004 D3's test failed on the back-solve: there is no estimate. Before a
            # refinement the iterate is returned as `newton` returns it, and after one the
            # attempt returns `x_k` (D4); either way the closing message says so.
            if self.refining is None:
                return self.finish(
                    "CONVERGED",
                    self.values,
                    message=f"terminal_refinement(abandoned: chord {failure.reason})",
                    iterations=iteration,
                    accepted_any=self.accepted_any,
                )
            start, self.refining = self.refining, None
            self.x = start.x
            return self.finish(
                "CONVERGED",
                start.values,
                message=start.message(f"reverted: chord {failure.reason}"),
                iterations=start.iteration,
                accepted_any=start.accepted_any,
                linear=self.chord_linear,
            )
        if self.refining is not None:
            # D4: the refined iterate is kept iff its own chord, with `x_k`'s factorization,
            # is within the kind tolerance on every column.
            start, self.refining = self.refining, None
            if ratio <= 1.0:
                return self.finish(
                    "CONVERGED",
                    self.values,
                    message=start.message(f"accepted: chord {ratio!r} at {column}"),
                    iterations=iteration,
                    accepted_any=self.accepted_any,
                    linear=self.chord_linear,
                )
            self.x = start.x
            return self.finish(
                "CONVERGED",
                start.values,
                message=start.message(f"reverted: chord {ratio!r} at {column}"),
                iterations=start.iteration,
                accepted_any=start.accepted_any,
                linear=self.chord_linear,
            )
        if not ratio > 1.0:
            return self.finish(
                "CONVERGED",
                self.values,
                iterations=iteration,
                accepted_any=self.accepted_any,
                linear=self.chord_linear,
            )
        converged = _Converged(
            self.x.copy(), self.values, iteration, self.accepted_any, ratio, column
        )
        if iteration == self.policy.max_iterations_per_attempt:
            # D2: never at the iteration budget; the estimate is disclosed all the same.
            return self.finish(
                "CONVERGED",
                self.values,
                message=converged.message("abandoned: BUDGET_EXHAUSTED(newton_iterations)"),
                iterations=iteration,
                accepted_any=self.accepted_any,
                linear=self.chord_linear,
            )
        # D3: one more iteration of this loop from `x_k`, unchanged.
        self.refining = converged
        return None

    def _stagnation(self, iteration: int) -> NewtonResult | None:
        """§5.7's stagnation test over `merits`, the merit ratios of the accepted steps: closes
        `STAGNATION` through `finish` (writing `attempt_closed`) when the last
        `stagnation_window` ratios all exceed `stagnation_ratio`. None when fewer ratios exist
        than the window, or when one of them does not exceed the ratio."""
        if len(self.merits) < self.policy.stagnation_window:
            return None
        window = self.merits[-self.policy.stagnation_window :]
        if all(ratio > self.policy.stagnation_ratio for ratio in window):
            return self.finish(
                "STAGNATION",
                self.values,
                message=(
                    f"{self.policy.stagnation_window} consecutive merit ratios above "
                    f"{self.policy.stagnation_ratio} with the residual unconverged; a small step "
                    "with a large residual is stagnation, not convergence"
                ),
                iterations=iteration,
                accepted_any=self.accepted_any,
            )
        return None

    def _jacobian(
        self, iteration: int, infinity: float, merit: float
    ) -> tuple[sp.csc_matrix, sp.csc_matrix] | NewtonResult:
        """The Jacobian at `x`, unscaled and scaled, with its evidence: counts the call in
        `running` before the evaluation, closes `EVALUATION_ERROR` through `finish` when the
        Jacobian is unavailable, and writes the `jacobian` event (with the inner consistency
        diagnostics when the problem has them) and one `linear_solve` event per inner
        factorization of `jacobian_evidence`, each counted in `running` before its record."""
        self.running = self.running.plus(jacobian_calls=1)
        try:
            unscaled = sp.csc_matrix(self.problem.jacobian(self.x))
        except JacobianUnavailableError as unavailable:
            return self.finish(
                "EVALUATION_ERROR",
                self.values,
                message=f"the Jacobian could not be evaluated: {unavailable}",
                iterations=iteration,
                accepted_any=self.accepted_any,
            )
        scaled = _scale_matrix(unscaled, self.problem)
        self.trace.record(
            kind="jacobian",
            attempt=self.attempt,
            iteration=iteration,
            signature=self.signature,
            state_sha256=self.digest(self.x),
            residual_inf_unscaled=infinity,
            merit=merit,
            counters=self.running,
            inner_consistency=(
                self.problem.jacobian_diagnostics() if self.problem.jacobian_diagnostics else None
            ),
        )
        for inner in self.problem.jacobian_evidence() if self.problem.jacobian_evidence else ():
            self.running = self.running.plus(factorizations=1)
            self.trace.record(
                kind="linear_solve",
                attempt=self.attempt,
                iteration=iteration,
                signature=self.signature,
                state_sha256=self.digest(self.x),
                residual_inf_unscaled=infinity,
                merit=merit,
                counters=self.running,
                linear=LinearRecord(
                    residual_normalized=inner.residual_normalized,
                    u_diag_min_abs=inner.min_abs_u_diagonal,
                    u_diag_max_abs=inner.max_abs_u_diagonal,
                    nnz_l=inner.nnz_l,
                    nnz_u=inner.nnz_u,
                ),
                message=f"assembling the derivative: {inner.dimension}x{inner.dimension}",
            )
        return unscaled, scaled

    def _linear_step(
        self, iteration: int, scaled: sp.csc_matrix, infinity: float, merit: float
    ) -> npt.NDArray[np.float64] | NewtonResult:
        """The scaled Newton step: solves `scaled` against the scaled residual of `values`, the
        factorization counted in `running` before the solve, keeping the factorization in `kept`
        when the call has column tolerances (ADR 0018). A failed solve writes its
        `linear_solve` event and closes `LINEAR_SOLVE_FAILED` through `finish`; a solved one
        writes the `linear_solve` event with the solve's record and returns the step."""
        scaled_residual = self.problem.scaling.scale_residual(self.values, self.problem.row_ids)
        self.running = self.running.plus(factorizations=1)
        try:
            if self.column_tolerance is None:
                step_scaled, record = solve_linear(scaled, -scaled_residual)
            else:
                step_scaled, record, self.kept = solve_linear_kept(scaled, -scaled_residual)
        except LinearSolveFailedError as failure:
            self.trace.record(
                kind="linear_solve",
                attempt=self.attempt,
                iteration=iteration,
                signature=self.signature,
                state_sha256=self.digest(self.x),
                residual_inf_unscaled=infinity,
                merit=merit,
                counters=self.running,
                outcome="LINEAR_SOLVE_FAILED",
                message=str(failure),
            )
            return self.finish(
                "LINEAR_SOLVE_FAILED",
                self.values,
                linear_reason=failure.reason,
                message=str(failure),
                iterations=iteration,
                accepted_any=self.accepted_any,
            )
        self.trace.record(
            kind="linear_solve",
            attempt=self.attempt,
            iteration=iteration,
            signature=self.signature,
            state_sha256=self.digest(self.x),
            residual_inf_unscaled=infinity,
            merit=merit,
            counters=self.running,
            linear=LinearRecord(
                residual_normalized=record.residual_normalized,
                u_diag_min_abs=record.min_abs_u_diagonal,
                u_diag_max_abs=record.max_abs_u_diagonal,
                nnz_l=record.nnz_l,
                nnz_u=record.nnz_u,
            ),
        )
        return step_scaled


def _chord(
    problem: Problem,
    kept: KeptFactorization,
    values: tuple[float, ...],
    column_tolerance: npt.NDArray[np.float64],
) -> tuple[float, str, LinearRecord]:
    """ADR 0018 D2: `c = −S_x Ĵ⁻¹ F̂(x)` with a kept factorization — no Jacobian, no factorization,
    no residual evaluation — and `max_j |c_j| / τ_kind(j)` with the column it is reached on (the
    first such column, in `variable_ids` order). The back-solve carries its ADR 0004 record."""
    scaled_residual = problem.scaling.scale_residual(values, problem.row_ids)
    step_scaled, record = kept.solve(-scaled_residual)
    correction = problem.scaling.unscale_state(step_scaled, problem.variable_ids)
    ratios = np.abs(np.asarray(correction, dtype=np.float64)) / column_tolerance
    linear = LinearRecord(
        residual_normalized=record.residual_normalized,
        u_diag_min_abs=record.min_abs_u_diagonal,
        u_diag_max_abs=record.max_abs_u_diagonal,
        nnz_l=record.nnz_l,
        nnz_u=record.nnz_u,
    )
    if not ratios.size:
        return 0.0, "", linear
    worst = int(np.argmax(ratios))
    return float(ratios[worst]), problem.variable_ids[worst], linear


def _scale_matrix(matrix: sp.csc_matrix, problem: Problem) -> sp.csc_matrix:
    """`Ĵ = S_F⁻¹ J S_x`, by id."""
    rows = problem.scaling.row_vector(problem.row_ids)
    columns = problem.scaling.column_vector(problem.variable_ids)
    coordinate = matrix.tocoo()
    scaled = coordinate.data * columns[coordinate.col] / rows[coordinate.row]
    return sp.csc_matrix(
        sp.coo_matrix((scaled, (coordinate.row, coordinate.col)), shape=matrix.shape)
    )


def _bound_aware_alpha(
    x: npt.NDArray[np.float64],
    direction: npt.NDArray[np.float64],
    lower: npt.NDArray[np.float64],
) -> tuple[float, tuple[int, ...]]:
    """§5.3's `α_max`, and which components land exactly on a bound there — or, when `α_max` is
    zero, which components block: those on their bound with the direction pointing out (T02
    review S6, so that a caller attributes the block instead of guessing)."""
    alpha = 1.0
    crossing = (direction < 0.0) & np.isfinite(lower) & ((x + direction) < lower)
    if np.any(crossing):
        ratios = (lower[crossing] - x[crossing]) / direction[crossing]
        alpha = float(min(1.0, float(np.min(ratios))))
    if alpha <= 0.0:
        return 0.0, tuple(int(index) for index in np.flatnonzero(crossing & (x <= lower)))
    landing = tuple(
        int(index)
        for index in np.flatnonzero(crossing)
        if np.isclose((lower[index] - x[index]) / direction[index], alpha, rtol=0.0, atol=0.0)
        or (lower[index] - x[index]) / direction[index] == alpha
    )
    return alpha, landing


def _bound_aware_step(
    x: npt.NDArray[np.float64],
    direction: npt.NDArray[np.float64],
    lower: npt.NDArray[np.float64],
    *,
    opening: npt.NDArray[np.float64],
    residual: Sequence[float],
    jacobian: sp.csc_matrix,
) -> tuple[npt.NDArray[np.float64], float, tuple[int, ...], tuple[int, ...]]:
    """§5.3 as amended (T05b ruling Q-S11 (b), R-064; R-782): the direction taken, `α_max`, the
    components landing on a bound there (the blockers when `α_max = 0`), and the released set.

    When `α_max = 0`, the released set `Z*` (`_released`) has its direction set to zero exactly —
    the factorization's roundoff there is discarded — and `α_max` is recomputed. If a component
    outside `Z*` still blocks, nothing is released and the blockers are the original direction's,
    exactly as before the amendment.

    When `α_max > 0` (R-782, S10-C absent-component note §4.1): if a component on its bound at
    the opening and at `x` has a nonzero direction entry, `Z*` is computed, and if it meets the
    direction's support its entries are set to zero exactly — the exact Newton step there. `α_max`
    and the landing are unchanged by it (no component of `Z*` can be in their minimum without
    making `α_max = 0`; note §4.2) and are recomputed on the direction taken. Otherwise the
    direction is returned as it came, with nothing released; `_released` runs only when the mask
    is non-empty."""
    alpha_max, landing = _bound_aware_alpha(x, direction, lower)
    if alpha_max > 0.0:
        moving = np.isfinite(lower) & (x == lower) & (opening == lower) & (direction != 0.0)
        if not np.any(moving):
            return direction, alpha_max, landing, ()
        released = _released(x, opening, lower, residual, jacobian)
        if not any(direction[index] != 0.0 for index in released):
            return direction, alpha_max, landing, ()
        kept = direction.copy()
        kept[list(released)] = 0.0
        alpha_kept, landing_kept = _bound_aware_alpha(x, kept, lower)
        return kept, alpha_kept, landing_kept, released
    released = _released(x, opening, lower, residual, jacobian)
    if not released:
        return direction, alpha_max, landing, ()
    kept = direction.copy()
    kept[list(released)] = 0.0
    alpha_kept, landing_kept = _bound_aware_alpha(x, kept, lower)
    if alpha_kept == 0.0:
        return direction, alpha_max, landing, ()
    return kept, alpha_kept, landing_kept, released


def _released(
    x: npt.NDArray[np.float64],
    opening: npt.NDArray[np.float64],
    lower: npt.NDArray[np.float64],
    residual: Sequence[float],
    jacobian: sp.csc_matrix,
) -> tuple[int, ...]:
    """§5.3 as amended (T05b ruling Q-S11 (b), R-064): the largest released set `Z*`, as indices.

    `Z₀` are the components exactly on a finite lower bound at the attempt's `opening` and at `x`.
    A set `Z ⊆ Z₀` is released when the rows closed on it — `F_r(x) == 0.0` exactly and every
    nonzero `J_{r,c}(x)` in a column of `Z` — number exactly `|Z|`; with `J` nonsingular the exact
    step on `Z` is then zero. The union of released sets is released, so `Z*` is unique. Found by
    a maximum matching of the closed rows into `Z₀`: a column is outside `Z*` exactly when an
    unmatched column is reachable from it through its matched row's support (the Dulmage–Mendelsohn
    over-determined part). The count is re-checked on the answer; a set that fails it (a singular
    `J`, which the factorization has just excluded) releases nothing.

    The matching is SciPy's iterative Hopcroft–Karp and the reachable set a worklist (R-786,
    replacing R-064's recursive augmenting search): no recursion at any `|Z₀|`, and the identical
    result, since the reachable set is the columns some maximum matching leaves uncovered
    (Gallai–Edmonds), whichever maximum matching is found."""
    on_bound = np.isfinite(lower) & (x == lower) & (opening == lower)
    if not on_bound.any():
        return ()
    rows = sp.csr_matrix(jacobian)
    m = rows.shape[0]
    kept = rows.data != 0.0
    row_of = np.repeat(np.arange(m), np.diff(rows.indptr))
    n_kept = np.bincount(row_of[kept], minlength=m)
    n_in = np.bincount(row_of[kept & on_bound[rows.indices]], minlength=m)
    closed = (np.asarray(residual, dtype=np.float64) == 0.0) & (n_kept > 0) & (n_in == n_kept)
    if not closed.any():
        return ()
    z0 = np.flatnonzero(on_bound)
    local = np.full(on_bound.shape[0], -1, dtype=np.int64)
    local[z0] = np.arange(z0.size)
    crow = np.full(m, -1, dtype=np.int64)
    closed_rows = np.flatnonzero(closed)
    crow[closed_rows] = np.arange(closed_rows.size)
    entries = kept & closed[row_of]
    incidence = sp.csr_matrix(
        (
            np.ones(int(entries.sum())),
            (crow[row_of[entries]], local[rows.indices[entries]]),
        ),
        shape=(closed_rows.size, z0.size),
    )
    incidence.sum_duplicates()  # data 1.0: duplicates add, never cancel
    match = maximum_bipartite_matching(incidence, perm_type="column")  # row -> column, or -1
    row_of_col = np.full(z0.size, -1, dtype=np.int64)
    row_of_col[match[match >= 0]] = np.flatnonzero(match >= 0)
    outside = row_of_col < 0
    by_column = incidence.tocsc()
    worklist = deque(int(column) for column in np.flatnonzero(outside))
    while worklist:
        column = worklist.popleft()
        for row in by_column.indices[by_column.indptr[column] : by_column.indptr[column + 1]]:
            other = int(match[row])
            if other >= 0 and not outside[other]:
                outside[other] = True
                worklist.append(other)
    released = ~outside
    if not released.any():
        return ()
    entry_rows = np.repeat(np.arange(incidence.shape[0]), np.diff(incidence.indptr))
    touches_outside = np.bincount(
        entry_rows[outside[incidence.indices]], minlength=incidence.shape[0]
    )
    count = int(np.count_nonzero(touches_outside == 0))
    if count != int(released.sum()):
        return ()
    return tuple(int(index) for index in z0[released])


def _trial_point(
    x: npt.NDArray[np.float64],
    direction: npt.NDArray[np.float64],
    alpha: float,
    lower: npt.NDArray[np.float64],
    landing: tuple[int, ...],
) -> npt.NDArray[np.float64]:
    """`x + α d`, with §5.3's exact landing on a bound for the components that reach it."""
    trial = x + alpha * direction
    for index in landing:
        trial[index] = normalize_zero(float(lower[index]))
    return np.array([normalize_zero(float(value)) for value in trial], dtype=np.float64)
