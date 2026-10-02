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
from typing import Literal

import numpy as np
import numpy.typing as npt

from openflowsheet.canonical import normalize_zero, state_sha256
from openflowsheet.numerics.newton import Evaluation, IterationObserver, Problem
from openflowsheet.orchestrator.trace import (
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
    history_x: list[npt.NDArray[np.float64]] = []
    history_f: list[npt.NDArray[np.float64]] = []
    norms: list[float] = []
    trajectory: list[npt.NDArray[np.float64]] = []
    accelerations: list[AccelerationEvent] = []
    restarts: list[RestartEvent] = []
    closures: list[int] = []
    oscillation_at: int | None = None
    beta_sub = rules.beta_substitution
    stagnation = 0
    flips = 0
    previous_f: npt.NDArray[np.float64] | None = None
    landings = 0
    invalid = 0
    calls = 0
    best_x = x.copy()
    best_norm = float("inf")
    running = counters or Counters()

    def evaluate(point: npt.NDArray[np.float64]) -> Evaluation:
        nonlocal calls, running
        calls += 1
        running = running.plus(residual_calls=1)
        return problem.residual(point)

    def digest(point: npt.NDArray[np.float64]) -> str:
        return state_sha256(point, problem.variable_ids)

    def unscaled_inf(values: Sequence[float] | None) -> float:
        return float(np.max(np.abs(np.asarray(values)))) if values else float("nan")

    def record_trial(
        k: int,
        alpha: float,
        point: npt.NDArray[np.float64],
        evaluation: Evaluation,
        reason: RejectionReason,
    ) -> None:
        if trace is None:
            return
        trace.record(
            kind="trial",
            attempt=attempt,
            iteration=k,
            signature=evaluation.signature or signature,
            state_sha256=digest(point),
            residual_inf_unscaled=unscaled_inf(evaluation.values),
            merit=(
                problem.scaling.merit(evaluation.values, problem.row_ids)
                if evaluation.values
                else float("nan")
            ),
            counters=running,
            alpha=alpha,
            step_inf_scaled=float("nan"),
            trial_status="rejected",
            rejection_reason=reason,
            message=evaluation.message,
        )

    def finish(
        outcome: RecycleOutcome, k: int, residual: tuple[float, ...] | None, message: str = ""
    ) -> RecycleResult:
        if trace is not None:
            trace.record(
                kind="attempt_closed",
                attempt=attempt,
                iteration=k,
                signature=signature,
                state_sha256=digest(x),
                residual_inf_unscaled=unscaled_inf(residual),
                merit=(
                    problem.scaling.merit(residual, problem.row_ids)
                    if residual is not None
                    else float("nan")
                ),
                counters=running,
                outcome=outcome,
                message=message,
            )
        return RecycleResult(
            outcome=outcome,
            iterations=k,
            x=x.copy(),
            residual=residual,
            residual_inf_scaled=tuple(norms),
            accelerations=tuple(accelerations),
            restarts=tuple(restarts),
            stagnation_closures=tuple(closures),
            oscillation_detected_at=oscillation_at,
            bound_landings=landings,
            invalid_trials=invalid,
            residual_calls=calls,
            best_x=best_x.copy(),
            best_residual_inf_scaled=best_norm,
            message=message,
            signature=signature,
            counters=running,
            trajectory=tuple(trajectory) if keep_trajectory else (),
        )

    current = evaluate(x)
    k = 0
    while True:
        if current.status != "ok" or current.values is None:
            return finish("EVALUATION_ERROR", k, None, current.message)
        residual = np.array(current.values, dtype=np.float64)
        f_hat = residual / scale
        norm = float(np.max(np.abs(f_hat))) if n else 0.0
        norms.append(norm)
        if keep_trajectory:
            trajectory.append(x.copy())
        if norm < best_norm:
            best_norm, best_x = norm, x.copy()

        # §5.2: convergence, tested before anything else.
        if bool(np.all(np.abs(f_hat) <= tolerance_hat)):
            return finish("CONVERGED", k, tuple(current.values))

        # §5.6: stagnation over accepted iterates. Growth counts: a residual that grows is a
        # residual that is not shrinking, which is why no divergence factor exists.
        if k > 0:
            if norms[-1] / norms[-2] > rules.stagnation_ratio:
                stagnation += 1
            else:
                stagnation = 0
            if stagnation >= rules.stagnation_window:
                closures.append(k)
                if len(restarts) < rules.max_restarts:
                    restarts.append(RestartEvent(iteration=k, count=len(restarts) + 1))
                    if trace is not None:
                        trace.record(
                            kind="restart",
                            attempt=attempt,
                            iteration=k,
                            signature=signature,
                            state_sha256=digest(x),
                            residual_inf_unscaled=unscaled_inf(current.values),
                            merit=problem.scaling.merit(current.values, problem.row_ids),
                            counters=running,
                            restart_reason="stagnation",
                            restart_count=len(restarts),
                        )
                    history_x.clear()
                    history_f.clear()
                    stagnation = 0
                else:
                    return finish("RECYCLE_STAGNATION", k, tuple(current.values))

        # §5.6: the oscillation detector on the dominant component, damping plain steps only.
        dominant = int(np.argmax(np.abs(f_hat)))
        if (
            previous_f is not None
            and abs(previous_f[dominant]) > tolerance_hat[dominant]
            and previous_f[dominant] * f_hat[dominant] < 0.0
        ):
            flips += 1
        else:
            flips = 0
        if flips >= rules.oscillation_window and oscillation_at is None:
            oscillation_at = k
            beta_sub = rules.beta_substitution_oscillating
        previous_f = f_hat

        if observer is not None:
            closing = observer.should_close(k)
            if closing is not None:
                return finish("PHASE_UPDATE_REQUIRED", k, tuple(current.values))

        if k >= rules.max_iterations_per_attempt:
            return finish("BUDGET_EXHAUSTED", k, tuple(current.values))

        # §5.3: history, the effective depth, and the filtered least squares (§5.4).
        history_x.append(x / scale)
        history_f.append(f_hat)
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
            correction = sum(
                (delta_x[j] + rules.beta * delta_f[j]) * gamma[j] for j in range(depth)
            )
            step_hat = history_x[-1] + rules.beta * f_hat - correction
            break
        if step_hat is None:
            depth = 0
            step_hat = history_x[-1] + beta_sub * f_hat
        accelerations.append(
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
                beta_substitution=beta_sub if depth == 0 else rules.beta,
                oscillation_flag=oscillation_at is not None,
                dropped=tuple(dropped),
            )
        )
        if trace is not None:
            decision = accelerations[-1]
            trace.record(
                kind="acceleration",
                attempt=attempt,
                iteration=k,
                signature=signature,
                state_sha256=digest(x),
                residual_inf_unscaled=unscaled_inf(current.values),
                merit=problem.scaling.merit(current.values, problem.row_ids),
                counters=running,
                depth_used=decision.depth_used,
                columns_dropped_condition=decision.columns_dropped_condition,
                columns_dropped_coefficient=decision.columns_dropped_coefficient,
                kappa_2=decision.kappa_2,
                gamma_inf=decision.gamma_inf,
                beta_substitution=decision.beta_substitution,
                oscillation_flag=decision.oscillation_flag,
            )

        # K03 §5.3: the bound-aware step length, with an exact landing on the bound.
        direction = (step_hat - history_x[-1]) * scale
        alpha_max = 1.0
        for i in range(n):
            if direction[i] < 0.0 and x[i] + direction[i] < lower[i]:
                alpha_max = min(alpha_max, (lower[i] - x[i]) / direction[i])
        if alpha_max == 0.0:
            return finish("BOUND_BLOCKED", k, tuple(current.values))
        if alpha_max < 1.0:
            landings += 1

        # K03 §5.4–§5.5: a typed refusal or another phase signature shortens the step; nothing
        # else does. There is no merit test (§5.5).
        alpha = alpha_max
        accepted: tuple[npt.NDArray[np.float64], Evaluation] | None = None
        for _ in range(rules.step_halvings_max + 1):
            trial = x + alpha * direction
            if alpha == alpha_max:
                for i in range(n):
                    if direction[i] < 0.0 and x[i] + alpha_max * direction[i] <= lower[i]:
                        trial[i] = lower[i]
            trial = np.array([normalize_zero(float(value)) for value in trial])
            evaluation = evaluate(trial)
            if evaluation.status == "ok":
                if (
                    signature
                    and evaluation.signature is not None
                    and evaluation.signature != signature
                ):
                    record_trial(k, alpha, trial, evaluation, "phase_update_required")
                    if observer is not None:
                        observer.rejected(
                            k, alpha, trial, "phase_update_required", evaluation.signature
                        )
                    alpha /= 2.0
                    continue
                accepted = (trial, evaluation)
                break
            invalid += 1
            record_trial(k, alpha, trial, evaluation, "invalid_trial")
            if observer is not None:
                observer.rejected(k, alpha, trial, "invalid_trial", evaluation.signature)
            alpha /= 2.0
        if accepted is None:
            return finish("LINE_SEARCH_FAILED", k, tuple(current.values))
        x, current = accepted
        if trace is not None and current.values is not None:
            trace.record(
                kind="step_accepted",
                attempt=attempt,
                iteration=k,
                signature=signature,
                state_sha256=digest(x),
                residual_inf_unscaled=unscaled_inf(current.values),
                merit=problem.scaling.merit(current.values, problem.row_ids),
                counters=running,
                alpha=alpha,
                step_inf_scaled=float(np.max(np.abs(direction / scale))) * alpha,
                trial_status="accepted",
            )
        k += 1
