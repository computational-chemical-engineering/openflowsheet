"""Successive substitution with safeguarded Anderson acceleration. T02 specification §5.

A generic core, like `newton.py` beside it: it solves `R(t) = G(t) − t = 0` for any `Problem`
whose residual is a recycle residual, and it knows nothing about thermodynamics. The SYN-001 tear
is one instance; the manufactured recycles `REC-01…05` that Frank required are others, and they
are the reason every safeguard below has a case that reaches it.

It is written against `docs/derivations/scripts/t02_reference.py`'s `accelerate`, which states the
registered policy a second time at 40 digits. An implementation of the same policy must reproduce
that trajectory; a different policy will not. So the order of operations here is the twin's, and
where the prose of the specification leaves a choice open the twin's choice is the one taken.

What is not the textbook, and why each departure is a rule rather than a taste:

- **No merit test** (§5.5). An accepted Anderson trial may have a larger residual than the iterate
  it came from — on the non-normal `REC-05` the residual rises 0.217 → 0.617 → 0.640 before the
  iteration terminates at 4. An Armijo condition on an accelerator rejects exactly the steps that
  make it one. Bounds and the evaluator's refusal are the only reasons a trial is not taken.
- **Column filters, not Tikhonov** (§5.4). A ridge term changes the coefficient even when the
  least squares is well posed and destroys the one sharp statement an accelerator allows: on a
  linear map with `I − A` nonsingular, full-memory Anderson is GMRES and terminates at the Krylov
  grade plus one. Dropping a column that carries no information keeps that.
- **Depth capped at the tear dimension** (§5.3). Beyond `n` columns the difference matrix is
  rank-deficient in exact arithmetic and the coefficient is not unique; two correct
  implementations could legitimately disagree. The twin refused such a system until the cap was
  written, which is how the cap was found.
- **Growth counts as stagnation** (§5.6), and there is no separate divergence factor. Any factor
  small enough to fire before the stagnation window would misfire on `REC-05`'s 8.7× transient.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Literal, NamedTuple

import numpy as np
import numpy.typing as npt

from openflowsheet.canonical import normalize_zero, state_sha256
from openflowsheet.numerics.newton import Evaluation, IterationObserver, Problem
from openflowsheet.numerics.solve_record import (
    AttemptSignature,
    Counters,
    RecyclePolicy,
    RejectionReason,
    Trace,
)

__all__ = [
    "AccelerationEvent",
    "RecycleOutcome",
    "RecyclePolicy",
    "RecycleResult",
    "RestartEvent",
    "solve_recycle",
]

RecycleOutcome = Literal[
    "CONVERGED",
    "RECYCLE_STAGNATION",
    "BUDGET_EXHAUSTED",
    "BOUND_BLOCKED",
    "LINE_SEARCH_FAILED",
    "EVALUATION_ERROR",
    "PHASE_UPDATE_REQUIRED",
]


@dataclass(frozen=True)
class AccelerationEvent:
    """One step's decision (§5.8): what was used, what was refused and why.

    `kappa_2` and `gamma_inf` describe the *accepted* least squares and are `None` on a plain
    step. What was *refused* is in `dropped`, as `(reason, value)` per column — so a coefficient
    that had to be refused (`RCY-COEF`'s 1 000 001) is on the record without pretending a plain
    step used it.
    """

    iteration: int
    depth_used: int
    columns_dropped_condition: int
    columns_dropped_coefficient: int
    kappa_2: float | None
    gamma_inf: float | None
    beta_substitution: float
    oscillation_flag: bool
    dropped: tuple[tuple[str, float], ...] = ()

    @property
    def plain(self) -> bool:
        return self.depth_used == 0


@dataclass(frozen=True)
class RestartEvent:
    iteration: int
    count: int
    reason: str = "stagnation"


@dataclass(frozen=True)
class RecycleResult:
    """Where the recycle iteration got to, why it stopped, and every decision on the way."""

    outcome: RecycleOutcome
    iterations: int
    x: npt.NDArray[np.float64]
    residual: tuple[float, ...] | None
    #: `‖f̂_k‖∞` at every evaluated accepted iterate, `k = 0…iterations` — the "trajectory" the
    #: specification's assertions compare with the twin.
    residual_inf_scaled: tuple[float, ...]
    accelerations: tuple[AccelerationEvent, ...]
    restarts: tuple[RestartEvent, ...]
    stagnation_closures: tuple[int, ...]
    oscillation_detected_at: int | None
    bound_landings: int
    invalid_trials: int
    residual_calls: int
    #: The accepted iterate of least scaled residual norm, and its norm: the merge edge's start
    #: (§4.4), and the checkpoint a failed attempt leaves behind.
    best_x: npt.NDArray[np.float64]
    best_residual_inf_scaled: float
    message: str = ""
    signature: AttemptSignature = ()
    counters: Counters = field(default_factory=Counters)
    trajectory: tuple[npt.NDArray[np.float64], ...] = field(default=(), repr=False)

    @property
    def converged(self) -> bool:
        return self.outcome == "CONVERGED"

    @property
    def residual_increases(self) -> int:
        norms = self.residual_inf_scaled
        return sum(
            1 for previous, current in zip(norms, norms[1:], strict=False) if current > previous
        )

    @property
    def anderson_steps(self) -> int:
        return sum(1 for event in self.accelerations if not event.plain)

    @property
    def plain_steps(self) -> int:
        return sum(1 for event in self.accelerations if event.plain)

    @property
    def columns_dropped_condition(self) -> int:
        return sum(event.columns_dropped_condition for event in self.accelerations)

    @property
    def columns_dropped_coefficient(self) -> int:
        return sum(event.columns_dropped_coefficient for event in self.accelerations)


def _least_squares(
    columns: Sequence[npt.NDArray[np.float64]], rhs: npt.NDArray[np.float64]
) -> tuple[npt.NDArray[np.float64] | None, float]:
    """`γ = argmin ‖rhs − [columns] γ‖₂` by QR, and `κ₂` of the column matrix by SVD.

    A zero smallest singular value is `κ₂ = ∞` and no coefficient: the column carries nothing,
    and a pseudo-inverse's minimum-norm answer would be one choice among infinitely many.
    """
    matrix = np.column_stack(columns)
    singular = np.linalg.svd(matrix, compute_uv=False)
    smallest, largest = float(singular.min()), float(singular.max())
    if smallest == 0.0:
        return None, float("inf")
    q, r = np.linalg.qr(matrix)
    gamma = np.linalg.solve(r, q.T @ rhs)
    return gamma, largest / smallest


def solve_recycle(
    problem: Problem,
    t0: Sequence[float] | npt.NDArray[np.float64],
    *,
    policy: RecyclePolicy | None = None,
    signature: AttemptSignature = (),
    observer: IterationObserver | None = None,
    keep_trajectory: bool = False,
    trace: Trace | None = None,
    attempt: int = 0,
    counters: Counters | None = None,
) -> RecycleResult:
    """Run §5's policy on `problem`, whose residual is `R(t) = G(t) − t`.

    `signature` is the attempt's frozen phase signature (K03 §9): a trial whose evaluation reports
    another is rejected as `phase_update_required` and its step halved, exactly as the Newton core
    does, and `observer` hears about it and may close the attempt.

    With a `trace`, the core records K03's own event kinds exactly as the Newton core does — a
    `trial` per rejected trial with its registered reason, a `step_accepted` per accepted one, and
    the `attempt_closed` that ends the attempt — so the attempt controller's pairing of
    `attempt_opened` and `attempt_closed` holds whichever core ran.
    """
    rules = policy or RecyclePolicy()
    n = len(problem.variable_ids)
    scale = np.array([problem.scaling.column[name] for name in problem.variable_ids])
    tolerance_hat = problem.tolerance_vector() / scale
    lower = problem.lower_bound_vector()

    x = np.array([normalize_zero(float(value)) for value in t0], dtype=np.float64)
    run = _RecycleRun(
        problem=problem,
        rules=rules,
        signature=signature,
        observer=observer,
        keep_trajectory=keep_trajectory,
        trace=trace,
        attempt=attempt,
        n=n,
        scale=scale,
        tolerance_hat=tolerance_hat,
        lower=lower,
        x=x,
        history_x=[],
        history_f=[],
        norms=[],
        trajectory=[],
        accelerations=[],
        restarts=[],
        closures=[],
        beta_sub=rules.beta_substitution,
        best_x=x.copy(),
        running=counters or Counters(),
    )

    run.current = run.evaluate(run.x)
    k = 0
    while True:
        if run.current.status != "ok" or run.current.values is None:
            return run.finish("EVALUATION_ERROR", k, None, run.current.message)
        residual = np.array(run.current.values, dtype=np.float64)
        f_hat = residual / scale
        norm = float(np.max(np.abs(f_hat))) if n else 0.0
        run.norms.append(norm)
        if keep_trajectory:
            run.trajectory.append(run.x.copy())
        if norm < run.best_norm:
            run.best_norm, run.best_x = norm, run.x.copy()

        # §5.2: convergence, tested before anything else.
        if bool(np.all(np.abs(f_hat) <= tolerance_hat)):
            return run.finish("CONVERGED", k, tuple(run.current.values))

        # §5.6: stagnation over accepted iterates. Growth counts: a residual that grows is a
        # residual that is not shrinking, which is why no divergence factor exists.
        if k > 0:
            if run.norms[-1] / run.norms[-2] > rules.stagnation_ratio:
                run.stagnation += 1
            else:
                run.stagnation = 0
            if run.stagnation >= rules.stagnation_window:
                run.closures.append(k)
                if len(run.restarts) < rules.max_restarts:
                    run.restarts.append(RestartEvent(iteration=k, count=len(run.restarts) + 1))
                    if trace is not None:
                        trace.record(
                            kind="restart",
                            attempt=attempt,
                            iteration=k,
                            signature=signature,
                            state_sha256=run.digest(run.x),
                            residual_inf_unscaled=run.unscaled_inf(run.current.values),
                            merit=problem.scaling.merit(run.current.values, problem.row_ids),
                            counters=run.running,
                            restart_reason="stagnation",
                            restart_count=len(run.restarts),
                        )
                    run.history_x.clear()
                    run.history_f.clear()
                    run.stagnation = 0
                else:
                    return run.finish("RECYCLE_STAGNATION", k, tuple(run.current.values))

        # §5.6: the oscillation detector on the dominant component, damping plain steps only.
        dominant = int(np.argmax(np.abs(f_hat)))
        if (
            run.previous_f is not None
            and abs(run.previous_f[dominant]) > tolerance_hat[dominant]
            and run.previous_f[dominant] * f_hat[dominant] < 0.0
        ):
            run.flips += 1
        else:
            run.flips = 0
        if run.flips >= rules.oscillation_window and run.oscillation_at is None:
            run.oscillation_at = k
            run.beta_sub = rules.beta_substitution_oscillating
        run.previous_f = f_hat

        if observer is not None:
            closing = observer.should_close(k)
            if closing is not None:
                return run.finish("PHASE_UPDATE_REQUIRED", k, tuple(run.current.values))

        if k >= rules.max_iterations_per_attempt:
            return run.finish("BUDGET_EXHAUSTED", k, tuple(run.current.values))

        # §5.3: history, the effective depth, and the filtered least squares (§5.4).
        run.history_x.append(run.x / scale)
        run.history_f.append(f_hat)
        step_hat, depth, by_condition, by_coefficient, kappa, gamma_inf, dropped = _mixing(
            run.history_x, run.history_f, f_hat, rules, n
        )
        if step_hat is None:
            depth = 0
            step_hat = run.history_x[-1] + run.beta_sub * f_hat
        run.accelerations.append(
            AccelerationEvent(
                iteration=k,
                depth_used=depth,
                columns_dropped_condition=by_condition,
                columns_dropped_coefficient=by_coefficient,
                kappa_2=kappa,
                gamma_inf=gamma_inf,
                # The damping *applied to this step*: the oscillation response touches plain steps
                # only (§5.6), so an Anderson step records its own mixing `β` and never the
                # substitution damping — RCY-TRUNC's flag sets at 7 with no effect on its Anderson
                # steps, and the record has to be able to show that (A20).
                beta_substitution=run.beta_sub if depth == 0 else rules.beta,
                oscillation_flag=run.oscillation_at is not None,
                dropped=tuple(dropped),
            )
        )
        if trace is not None:
            decision = run.accelerations[-1]
            trace.record(
                kind="acceleration",
                attempt=attempt,
                iteration=k,
                signature=signature,
                state_sha256=run.digest(run.x),
                residual_inf_unscaled=run.unscaled_inf(run.current.values),
                merit=problem.scaling.merit(run.current.values, problem.row_ids),
                counters=run.running,
                depth_used=decision.depth_used,
                columns_dropped_condition=decision.columns_dropped_condition,
                columns_dropped_coefficient=decision.columns_dropped_coefficient,
                kappa_2=decision.kappa_2,
                gamma_inf=decision.gamma_inf,
                beta_substitution=decision.beta_substitution,
                oscillation_flag=decision.oscillation_flag,
            )

        # K03 §5.3: the bound-aware step length, with an exact landing on the bound.
        direction = (step_hat - run.history_x[-1]) * scale
        alpha_max = 1.0
        for i in range(n):
            if direction[i] < 0.0 and run.x[i] + direction[i] < lower[i]:
                alpha_max = min(alpha_max, (lower[i] - run.x[i]) / direction[i])
        if alpha_max == 0.0:
            return run.finish("BOUND_BLOCKED", k, tuple(run.current.values))
        if alpha_max < 1.0:
            run.landings += 1

        # K03 §5.4–§5.5: a typed refusal or another phase signature shortens the step; nothing
        # else does. There is no merit test (§5.5).
        alpha = alpha_max
        accepted: tuple[npt.NDArray[np.float64], Evaluation] | None = None
        for _ in range(rules.step_halvings_max + 1):
            trial = run.x + alpha * direction
            if alpha == alpha_max:
                for i in range(n):
                    if direction[i] < 0.0 and run.x[i] + alpha_max * direction[i] <= lower[i]:
                        trial[i] = lower[i]
            trial = np.array([normalize_zero(float(value)) for value in trial])
            evaluation = run.evaluate(trial)
            if evaluation.status == "ok":
                if (
                    signature
                    and evaluation.signature is not None
                    and evaluation.signature != signature
                ):
                    run.record_trial(k, alpha, trial, evaluation, "phase_update_required")
                    if observer is not None:
                        observer.rejected(
                            k, alpha, trial, "phase_update_required", evaluation.signature
                        )
                    alpha /= 2.0
                    continue
                accepted = (trial, evaluation)
                break
            run.invalid += 1
            run.record_trial(k, alpha, trial, evaluation, "invalid_trial")
            if observer is not None:
                observer.rejected(k, alpha, trial, "invalid_trial", evaluation.signature)
            alpha /= 2.0
        if accepted is None:
            return run.finish("LINE_SEARCH_FAILED", k, tuple(run.current.values))
        run.x, run.current = accepted
        if trace is not None and run.current.values is not None:
            trace.record(
                kind="step_accepted",
                attempt=attempt,
                iteration=k,
                signature=signature,
                state_sha256=run.digest(run.x),
                residual_inf_unscaled=run.unscaled_inf(run.current.values),
                merit=problem.scaling.merit(run.current.values, problem.row_ids),
                counters=run.running,
                alpha=alpha,
                step_inf_scaled=float(np.max(np.abs(direction / scale))) * alpha,
                trial_status="accepted",
            )
        k += 1


@dataclass
class _RecycleRun:
    """One call of `solve_recycle`: its fixed frame and the state carried between iterations.

    The state: the iterate `x` and its evaluation `current`, the scaled history (§5.3), the norms
    and trajectory, the decisions the result lists (accelerations, restarts, stagnation closures,
    the oscillation onset), the counters of §5.6 and of the trials, and the best iterate.
    """

    problem: Problem
    rules: RecyclePolicy
    signature: AttemptSignature
    observer: IterationObserver | None
    keep_trajectory: bool
    trace: Trace | None
    attempt: int
    n: int
    scale: npt.NDArray[np.float64]
    tolerance_hat: npt.NDArray[np.float64]
    lower: npt.NDArray[np.float64]
    x: npt.NDArray[np.float64]
    history_x: list[npt.NDArray[np.float64]]
    history_f: list[npt.NDArray[np.float64]]
    norms: list[float]
    trajectory: list[npt.NDArray[np.float64]]
    accelerations: list[AccelerationEvent]
    restarts: list[RestartEvent]
    closures: list[int]
    beta_sub: float
    best_x: npt.NDArray[np.float64]
    running: Counters
    oscillation_at: int | None = None
    stagnation: int = 0
    flips: int = 0
    previous_f: npt.NDArray[np.float64] | None = None
    landings: int = 0
    invalid: int = 0
    calls: int = 0
    best_norm: float = float("inf")
    current: Evaluation = field(init=False)

    def evaluate(self, point: npt.NDArray[np.float64]) -> Evaluation:
        """The residual at `point`; counts `calls` and `running` first, so both counts stand when
        the residual raises."""
        self.calls += 1
        self.running = self.running.plus(residual_calls=1)
        return self.problem.residual(point)

    def finish(
        self, outcome: RecycleOutcome, k: int, residual: tuple[float, ...] | None, message: str = ""
    ) -> RecycleResult:
        """Closes the attempt: writes `attempt_closed` when `trace` is set and returns the result
        with copies of `x` and `best_x`."""
        if self.trace is not None:
            self.trace.record(
                kind="attempt_closed",
                attempt=self.attempt,
                iteration=k,
                signature=self.signature,
                state_sha256=self.digest(self.x),
                residual_inf_unscaled=self.unscaled_inf(residual),
                merit=(
                    self.problem.scaling.merit(residual, self.problem.row_ids)
                    if residual is not None
                    else float("nan")
                ),
                counters=self.running,
                outcome=outcome,
                message=message,
            )
        return RecycleResult(
            outcome=outcome,
            iterations=k,
            x=self.x.copy(),
            residual=residual,
            residual_inf_scaled=tuple(self.norms),
            accelerations=tuple(self.accelerations),
            restarts=tuple(self.restarts),
            stagnation_closures=tuple(self.closures),
            oscillation_detected_at=self.oscillation_at,
            bound_landings=self.landings,
            invalid_trials=self.invalid,
            residual_calls=self.calls,
            best_x=self.best_x.copy(),
            best_residual_inf_scaled=self.best_norm,
            message=message,
            signature=self.signature,
            counters=self.running,
            trajectory=tuple(self.trajectory) if self.keep_trajectory else (),
        )

    def digest(self, point: npt.NDArray[np.float64]) -> str:
        return state_sha256(point, self.problem.variable_ids)

    def unscaled_inf(self, values: Sequence[float] | None) -> float:
        return float(np.max(np.abs(np.asarray(values)))) if values else float("nan")

    def record_trial(
        self,
        k: int,
        alpha: float,
        point: npt.NDArray[np.float64],
        evaluation: Evaluation,
        reason: RejectionReason,
    ) -> None:
        """Writes a rejected `trial` event when `trace` is set."""
        if self.trace is None:
            return
        self.trace.record(
            kind="trial",
            attempt=self.attempt,
            iteration=k,
            signature=evaluation.signature or self.signature,
            state_sha256=self.digest(point),
            residual_inf_unscaled=self.unscaled_inf(evaluation.values),
            merit=(
                self.problem.scaling.merit(evaluation.values, self.problem.row_ids)
                if evaluation.values
                else float("nan")
            ),
            counters=self.running,
            alpha=alpha,
            step_inf_scaled=float("nan"),
            trial_status="rejected",
            rejection_reason=reason,
            message=evaluation.message,
        )


class _Mixing(NamedTuple):
    """One iteration's filtered least squares (§5.3–§5.4): the Anderson step, or none."""

    step_hat: npt.NDArray[np.float64] | None
    depth: int
    by_condition: int
    by_coefficient: int
    kappa: float | None
    gamma_inf: float | None
    dropped: list[tuple[str, float]]


def _mixing(
    history_x: list[npt.NDArray[np.float64]],
    history_f: list[npt.NDArray[np.float64]],
    f_hat: npt.NDArray[np.float64],
    rules: RecyclePolicy,
    n: int,
) -> _Mixing:
    """§5.3's effective depth and §5.4's filtered least squares over the scaled history; pure.

    The depth starts at `min(depth_max, len(history_f) − 1, n)` and drops the oldest column while
    the difference matrix is singular or conditioned above `condition_max`, or the coefficient
    exceeds `coefficient_max`. `step_hat` is the Anderson step at the first depth that passes both
    filters; it is `None`, at depth 0, when none does, and the caller then takes the plain
    substitution step.
    """
    depth = min(rules.depth_max, len(history_f) - 1, n)
    dropped: list[tuple[str, float]] = []
    by_condition = by_coefficient = 0
    step_hat: npt.NDArray[np.float64] | None = None
    kappa: float | None = None
    gamma_inf: float | None = None
    while depth >= 1:
        delta_f = [history_f[-j] - history_f[-j - 1] for j in range(1, depth + 1)]
        delta_x = [history_x[-j] - history_x[-j - 1] for j in range(1, depth + 1)]
        gamma, condition = _least_squares(delta_f, f_hat)
        if gamma is None or condition > rules.condition_max:
            by_condition += 1
            dropped.append(("condition", condition))
            depth -= 1
            continue
        size = float(np.max(np.abs(gamma)))
        if size > rules.coefficient_max:
            by_coefficient += 1
            dropped.append(("coefficient", size))
            depth -= 1
            continue
        kappa, gamma_inf = condition, size
        correction = sum((delta_x[j] + rules.beta * delta_f[j]) * gamma[j] for j in range(depth))
        step_hat = history_x[-1] + rules.beta * f_hat - correction
        break
    return _Mixing(step_hat, depth, by_condition, by_coefficient, kappa, gamma_inf, dropped)
