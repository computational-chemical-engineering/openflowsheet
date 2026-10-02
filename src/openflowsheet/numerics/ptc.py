"""Pseudo-transient continuation with safeguarded SER (switched evolution relaxation). T04 §7.

Written, like K03's Newton core, for a generic square problem `F(x) = 0` — here with a declared
mass matrix — so that every rule can be exercised on a one-variable problem with no thermodynamics
in it (T04 §9.4's seeds) before it runs on a flowsheet. The SYN-001 region is one instance.

**The step** is blueprint §7.5's linearly implicit pseudo-step, in scaled variables,

    (M̂_k / Δτ + Ĵ_σ,k) d̂ = −F̂_σ,k,     F̂_σ = σ ⊙ S_F⁻¹ F,  Ĵ_σ = σ ⊙ S_F⁻¹ J S_x,  M̂ = S_F⁻¹ M S_x,

with `M = ∂(holdup)/∂x` evaluated at the accepted iterate and frozen during its retries, and
`σ = PTC_ROW_SIGN[row_accumulation]`. ADR 0008 D3.3 writes every balance row as inflow − outflow,
so that the physical balance reads `d(holdup)/dt = +F`; the pseudo-dynamics `M ẋ = −F̃` therefore
need `σ = −1` on a `holdup_balance` row. The map is one named constant, applied here, to the
residual and the Jacobian together, and nowhere else (T04 §6.1).

ADR 0010 D4. **Four rules are not the textbook's, and each is registered** (T04 §7.3–§7.5):

- **One trial per pseudo-step size, at K03 §5.3's `α_max`, with no merit test.** An accepted
  pseudo-step may increase the residual; a rejected one — out of bounds at once, unfactorizable,
  not evaluable, or in another regime — is retried at half the pseudo-step, at most `retries_max`
  times and never below `tau_min`. What ends the retries is `PTC_STALLED`, or `BOUND_BLOCKED` with
  the blocking columns when the last rejection was a bound (so T03 §4.6's disappearance applies).
- **SER reads accepted iterates only.** `Δτ_{k+1} = clip(Δτ_used · clip(φ_k / max(φ_{k+1},
  φ_floor)))`: no quantity of a rejected trial — neither the pseudo-step it proposed nor its
  residual — enters the update.
- **The stop is K03 §5.2's**, on the unscaled residual row by row, at pseudo-step 0 and after
  every accepted pseudo-step, *before* any SER update: a near-zero residual never inflates a ratio.
- **A stop after at least one pseudo-step is polished** by one Newton step, kept iff it evaluates,
  keeps the frozen signature, meets K03 §5.2 and is no worse in its worst row. PTC's terminal
  convergence is linear and leaves every row just under its tolerance with a common sign; the sum
  of four such rows is K04's envelope, which measured 1.31 τ without the polish (register R-033).

The bound handling is K03 §5.3's — the same two functions Newton calls, not a copy of them — so a
component that reaches its bound lands on it at `+0.0` exactly (ADR 0001 D3.1).
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import Final

import numpy as np
import numpy.typing as npt
import scipy.sparse as sp

from openflowsheet.canonical import normalize_zero, state_sha256
from openflowsheet.numerics.linear import LinearSolveFailedError, solve_linear
from openflowsheet.numerics.newton import (
    Evaluation,
    IterationObserver,
    JacobianUnavailableError,
    NewtonResult,
    Problem,
    _bound_aware_alpha,
    _scale_matrix,
    _trial_point,
    another_signature,
)
from openflowsheet.orchestrator.trace import (
    AttemptSignature,
    Counters,
    LinearRecord,
    PtcPolicy,
    RejectionReason,
    SolveOutcome,
    Trace,
)

__all__ = [
    "PTC_ROW_SIGN",
    "MassUnavailableError",
    "PseudoStep",
    "PtcProblem",
    "PtcRecord",
    "PtcRejection",
    "pseudo_step_direction",
    "row_signs",
    "solve_ptc",
]

#: ADR 0008 D3.4, T04 §6.1: σ by row accumulation. A `holdup_balance` row is written inflow −
#: outflow, so its pseudo-dynamics are `M ẋ = +F` and it enters the step with `−1`; a zero-holdup
#: balance and an algebraic row have no `M` row and keep their orientation. `absent` has no entry:
#: a row whose accumulation is unknown has no pseudo-dynamics, and the mapping refuses it first.
PTC_ROW_SIGN: Final[Mapping[str, int]] = MappingProxyType(
    {"holdup_balance": -1, "zero_holdup_balance": 1, "algebraic": 1}
)


class MassUnavailableError(RuntimeError):
    """The mass matrix could not be evaluated at an accepted iterate — a provider that refused, or
    a spent property budget. Not a rejection: the iterate was already accepted, so the attempt
    ends `EVALUATION_ERROR`, as a residual `error` would (K03 §5.5)."""


#: Returns the unscaled `M = ∂(holdup)/∂x` at `x`, rows × variables in the problem's order, in
#: any form `scipy.sparse` accepts; or raises `MassUnavailableError`.
MassEvaluator = Callable[[npt.NDArray[np.float64]], sp.spmatrix | npt.NDArray[np.float64]]


@dataclass(frozen=True)
class PtcProblem:
    """A square residual problem with a declared mass matrix and each row's accumulation."""

    problem: Problem
    mass: MassEvaluator
    #: ADR 0008 D3: what each row accumulates, by row id — what `PTC_ROW_SIGN` maps to σ.
    row_accumulation: Mapping[str, str]


@dataclass(frozen=True)
class PseudoStep:
    """One accepted pseudo-step `k`: from `x_before` to `x` at `alpha` with `Δτ = tau`."""

    index: int
    tau: float
    alpha: float
    #: Rejections at this pseudo-step before the accepted trial (its retry index).
    retries: int
    phi_before: float
    phi: float
    #: The SER proposal and the clipped ratio; `None` when `x` met the stop test.
    tau_next: float | None
    ser_ratio: float | None
    x_before: npt.NDArray[np.float64]
    x: npt.NDArray[np.float64]
    residual_before: tuple[float, ...]
    residual: tuple[float, ...]
    #: Variables that landed exactly on their bound at `alpha = α_max < 1`.
    landing: tuple[str, ...] = ()


@dataclass(frozen=True)
class PtcRejection:
    """One rejected trial: pseudo-step `index`, its `retry`-th trial, at `tau`."""

    index: int
    retry: int
    tau: float
    reason: RejectionReason
    #: `α_max` when a trial point was formed; `None` for a bound block or a failed factorization.
    alpha: float | None = None
    blocked_by: tuple[str, ...] = ()


@dataclass(frozen=True)
class PtcRecord:
    """What a PTC attempt did (T04 §7.8), in memory: every accepted pseudo-step and every rejected
    trial in order, where the SER state ended, and the polish's verdict with the stop it left."""

    steps: tuple[PseudoStep, ...]
    rejections: tuple[PtcRejection, ...]
    #: The pseudo-step the controller held at the end: the next proposal after an accepted step,
    #: or the last one tried when the retries ran out. Only the reset ablation reads it.
    tau_end: float
    #: `accepted`, `rejected:<reason>`, or `None` when no polish was due.
    polish: str | None = None
    #: The stopped iterate `x_c` and its residual, before the polish replaced them (A22).
    stopped_x: npt.NDArray[np.float64] | None = None
    stopped_residual: tuple[float, ...] | None = None


def row_signs(
    row_ids: Sequence[str],
    row_accumulation: Mapping[str, str],
    sign: Mapping[str, int] = PTC_ROW_SIGN,
) -> npt.NDArray[np.float64]:
    """σ per row, from `PTC_ROW_SIGN` by accumulation. `sign` is an ablation seam only (T04 §9.9:
    the row sign σ = +1), never a policy."""
    return np.array([float(sign[row_accumulation[name]]) for name in row_ids], dtype=np.float64)


def _row_scaled(matrix: sp.csc_matrix, sigma: npt.NDArray[np.float64]) -> sp.csc_matrix:
    """`σ ⊙ A`, row by row. σ is ±1, so this is exact."""
    coordinate = matrix.tocoo()
    return sp.csc_matrix(
        sp.coo_matrix(
            (coordinate.data * sigma[coordinate.row], (coordinate.row, coordinate.col)),
            shape=matrix.shape,
        )
    )


def _norm(scaled: npt.NDArray[np.float64]) -> float:
    """`φ = ‖F̂‖₂`. σ is ±1, so the signed and unsigned residuals have the same norm."""
    return math.sqrt(float(np.dot(scaled, scaled)))


def pseudo_step_direction(
    ptc: PtcProblem,
    x: npt.NDArray[np.float64],
    values: Sequence[float],
    tau: float,
    *,
    sign: Mapping[str, int] = PTC_ROW_SIGN,
) -> npt.NDArray[np.float64]:
    """The unscaled direction `d = S_x d̂` of one pseudo-step of size `tau` at `x` (T04 §6.1, §7.3).

    The core forms the same matrices once per pseudo-step and reuses them across its retries; this
    is the one-shot form, for the checks of T04 §6.4 and §6.7 (steady-state equivalence, reference
    invariance, the algebraic components of PHS-05's first step). Raises `LinearSolveFailedError`
    when the shifted matrix does not factorize."""
    problem = ptc.problem
    sigma = row_signs(problem.row_ids, ptc.row_accumulation, sign)
    jacobian = _row_scaled(_scale_matrix(sp.csc_matrix(problem.jacobian(x)), problem), sigma)
    mass = _scale_matrix(sp.csc_matrix(ptc.mass(x)), problem)
    residual = sigma * problem.scaling.scale_residual(values, problem.row_ids)
    step, _ = solve_linear(sp.csc_matrix(jacobian + mass / tau), -residual)
    return problem.scaling.unscale_state(step, problem.variable_ids)


def solve_ptc(
    ptc: PtcProblem,
    x0: Sequence[float] | npt.NDArray[np.float64],
    settings: PtcPolicy,
    *,
    trace: Trace,
    signature: AttemptSignature = (),
    attempt: int = 0,
    counters: Counters | None = None,
    observer: IterationObserver | None = None,
    tau_start: float | None = None,
    sign: Mapping[str, int] = PTC_ROW_SIGN,
    compare_empty: bool = False,
) -> tuple[NewtonResult, PtcRecord]:
    """Run T04 §7's PTC core as one attempt and record every decision on `trace`.

    Returns the core's result in the shape `phase_contract.decide` reads — `iterations` is the
    number of accepted pseudo-steps, the polish excluded — and the attempt's `PtcRecord`.

    The SER state is the attempt's: it opens at `tau_initial_s` (T04 §7.4's reset). `tau_start`
    and `sign` exist for T04 §9.9's ablations (the carried pseudo-step, σ = +1) and for nothing
    else; the registered path passes neither.
    """
    problem = ptc.problem
    x = np.array([normalize_zero(float(value)) for value in x0], dtype=np.float64)
    tolerance = problem.tolerance_vector()
    lower = problem.lower_bound_vector()
    sigma = row_signs(problem.row_ids, ptc.row_accumulation, sign)
    running = counters or Counters()
    steps: list[PseudoStep] = []
    rejections: list[PtcRejection] = []
    tau = settings.tau_initial_s if tau_start is None else tau_start

    def digest(vector: npt.NDArray[np.float64]) -> str:
        return state_sha256(vector, problem.variable_ids)

    def evaluate(vector: npt.NDArray[np.float64]) -> Evaluation:
        nonlocal running
        running = running.plus(residual_calls=1)
        return problem.residual(vector)

    def met(values: Sequence[float]) -> bool:
        return bool(np.all(np.abs(np.asarray(values, dtype=np.float64)) <= tolerance))

    def record(
        outcome: SolveOutcome,
        values: tuple[float, ...],
        *,
        iterations: int,
        tau_end: float,
        message: str = "",
        budget: str | None = None,
        blocked_by: tuple[str, ...] = (),
        polish: str | None = None,
        stopped: tuple[npt.NDArray[np.float64], tuple[float, ...]] | None = None,
    ) -> tuple[NewtonResult, PtcRecord]:
        array = np.asarray(values, dtype=np.float64)
        infinity = float(np.max(np.abs(array))) if array.size else 0.0
        merit = problem.scaling.merit(values, problem.row_ids)
        trace.record(
            kind="attempt_closed",
            attempt=attempt,
            iteration=iterations,
            signature=signature,
            state_sha256=digest(x),
            residual_inf_unscaled=infinity,
            merit=merit,
            counters=running,
            outcome=outcome,
            message=message,
        )
        result = NewtonResult(
            outcome=outcome,
            x=x,
            residual=values,
            residual_inf=infinity,
            merit=merit,
            iterations=iterations,
            counters=running,
            converged=outcome == "CONVERGED",
            budget=budget,
            message=message,
            accepted_any=bool(steps),
            blocked_by=blocked_by,
        )
        return result, PtcRecord(
            steps=tuple(steps),
            rejections=tuple(rejections),
            tau_end=tau_end,
            polish=polish,
            stopped_x=None if stopped is None else stopped[0],
            stopped_residual=None if stopped is None else stopped[1],
        )

    evaluation = evaluate(x)
    if evaluation.status != "ok" or evaluation.values is None:
        return record(
            "EVALUATION_ERROR" if evaluation.status == "error" else "PTC_STALLED",
            tuple(np.full(len(problem.row_ids), np.nan)),
            iterations=0,
            tau_end=tau,
            message=f"the initial point could not be evaluated: {evaluation.status}: "
            f"{evaluation.message}",
        )
    values = evaluation.values

    for k in range(settings.max_steps_per_attempt + 1):
        scaled_residual = problem.scaling.scale_residual(values, problem.row_ids)
        phi = _norm(scaled_residual)
        infinity = float(np.max(np.abs(np.asarray(values)))) if values else 0.0
        merit = 0.5 * phi * phi

        # §7.4: the stop, K03 §5.2's test, before anything else — and before any SER update.
        if met(values):
            if k == 0:
                return record("CONVERGED", values, iterations=0, tau_end=tau)
            stopped = (x.copy(), values)
            verdict, polished = _polish(
                problem, x, values, signature, attempt, k, trace, running, compare_empty
            )
            running = polished.counters
            if polished.outcome == "EVALUATION_ERROR":
                return record(
                    "EVALUATION_ERROR",
                    values,
                    iterations=k,
                    tau_end=tau,
                    message=polished.message,
                    polish=verdict,
                    stopped=stopped,
                )
            if verdict == "accepted":
                x, values = polished.x, polished.values
            return record(
                "CONVERGED", values, iterations=k, tau_end=tau, polish=verdict, stopped=stopped
            )

        if k == settings.max_steps_per_attempt:
            return record(
                "BUDGET_EXHAUSTED",
                values,
                iterations=k,
                tau_end=tau,
                budget="ptc_steps",
                message=f"{k} accepted pseudo-steps without convergence",
            )

        # The matrices of pseudo-step k, formed once and frozen during its retries (§7.3).
        running = running.plus(jacobian_calls=1)
        try:
            unscaled = sp.csc_matrix(problem.jacobian(x))
        except JacobianUnavailableError as unavailable:
            # T04 review M1: a derivative defect at an accepted iterate, never a retry.
            return record(
                "EVALUATION_ERROR",
                values,
                iterations=k,
                tau_end=tau,
                message=f"the Jacobian could not be evaluated: {unavailable}",
            )
        jacobian = _row_scaled(_scale_matrix(unscaled, problem), sigma)
        try:
            mass = _scale_matrix(sp.csc_matrix(ptc.mass(x)), problem)
        except MassUnavailableError as unavailable:
            return record(
                "EVALUATION_ERROR",
                values,
                iterations=k,
                tau_end=tau,
                message=f"the mass matrix could not be evaluated: {unavailable}",
            )
        trace.record(
            kind="jacobian",
            attempt=attempt,
            iteration=k,
            signature=signature,
            state_sha256=digest(x),
            residual_inf_unscaled=infinity,
            merit=merit,
            counters=running,
        )
        rhs = -(sigma * scaled_residual)

        tau_try, retry = tau, 0
        accepted: tuple[npt.NDArray[np.float64], tuple[float, ...], float, float, tuple[str, ...]]
        while True:
            reason: RejectionReason | None = None
            alpha: float | None = None
            blocked: tuple[str, ...] = ()
            trial: npt.NDArray[np.float64] = x
            trial_evaluation: Evaluation | None = None
            step_inf: float | None = None
            failure_message = ""
            running = running.plus(factorizations=1)
            try:
                step_scaled, linear = solve_linear(sp.csc_matrix(jacobian + mass / tau_try), rhs)
            except LinearSolveFailedError as failure:
                reason = "linear_solve_failed"
                failure_message = str(failure)
            else:
                trace.record(
                    kind="linear_solve",
                    attempt=attempt,
                    iteration=k,
                    signature=signature,
                    state_sha256=digest(x),
                    residual_inf_unscaled=infinity,
                    merit=merit,
                    counters=running,
                    linear=LinearRecord(
                        residual_normalized=linear.residual_normalized,
                        u_diag_min_abs=linear.min_abs_u_diagonal,
                        u_diag_max_abs=linear.max_abs_u_diagonal,
                        nnz_l=linear.nnz_l,
                        nnz_u=linear.nnz_u,
                    ),
                    pseudo_step=tau_try,
                )
                direction = problem.scaling.unscale_state(step_scaled, problem.variable_ids)
                alpha_max, landing = _bound_aware_alpha(x, direction, lower)
                if alpha_max == 0.0:
                    reason = "bound_blocked"
                    blocked = tuple(problem.variable_ids[index] for index in landing)
                    failure_message = f"blocked by {', '.join(blocked)}"
                else:
                    alpha = alpha_max
                    trial = _trial_point(x, direction, alpha_max, lower, landing)
                    trial_evaluation = evaluate(trial)
                    step_inf = float(np.max(np.abs(step_scaled))) * alpha_max
                    failure_message = trial_evaluation.message
                    if trial_evaluation.status == "error":
                        trace.record(
                            kind="trial",
                            attempt=attempt,
                            iteration=k,
                            signature=signature,
                            state_sha256=digest(trial),
                            residual_inf_unscaled=float("nan"),
                            merit=float("nan"),
                            counters=running,
                            alpha=alpha_max,
                            step_inf_scaled=step_inf,
                            trial_status="rejected",
                            message=trial_evaluation.message,
                            pseudo_step=tau_try,
                        )
                        return record(
                            "EVALUATION_ERROR",
                            values,
                            iterations=k,
                            tau_end=tau_try,
                            message=trial_evaluation.message,
                        )
                    if trial_evaluation.status != "ok" or trial_evaluation.values is None:
                        reason = "invalid_trial"
                    elif another_signature(
                        signature, trial_evaluation.signature, compare_empty=compare_empty
                    ):
                        reason = "phase_update_required"
                    else:
                        landed = (
                            tuple(problem.variable_ids[index] for index in landing)
                            if alpha_max < 1.0
                            else ()
                        )
                        accepted = (trial, trial_evaluation.values, alpha_max, step_inf, landed)
                        break

            # §7.3.5: a rejection keeps x_k and F_k; nothing of the trial is kept.
            rejections.append(PtcRejection(k, retry, tau_try, reason, alpha, blocked))
            trial_values = (
                trial_evaluation.values
                if trial_evaluation is not None and trial_evaluation.values is not None
                else None
            )
            trace.record(
                kind="trial",
                attempt=attempt,
                iteration=k,
                signature=(
                    trial_evaluation.signature
                    if trial_evaluation is not None and trial_evaluation.signature
                    else signature
                ),
                state_sha256=digest(trial) if alpha is not None else "",
                residual_inf_unscaled=(
                    float(np.max(np.abs(trial_values))) if trial_values else float("nan")
                ),
                merit=(
                    problem.scaling.merit(trial_values, problem.row_ids)
                    if trial_values
                    else float("nan")
                ),
                counters=running,
                alpha=alpha,
                step_inf_scaled=step_inf,
                trial_status="rejected",
                rejection_reason=reason,
                message=failure_message,
                pseudo_step=tau_try,
            )
            if observer is not None:
                # T04 §7.6: the wall observer hears every rejection, with the pseudo-step index
                # and `2^−retry`, so a candidate's halving index is its retry index.
                observer.rejected(
                    k,
                    2.0**-retry,
                    trial,
                    reason,
                    trial_evaluation.signature if trial_evaluation is not None else None,
                )
            retry += 1
            shrunk = tau_try * settings.retry_shrink
            if retry > settings.retries_max or shrunk < settings.tau_min_s:
                outcome: SolveOutcome = (
                    "BOUND_BLOCKED" if reason == "bound_blocked" else "PTC_STALLED"
                )
                return record(
                    outcome,
                    values,
                    iterations=k,
                    tau_end=tau_try,
                    blocked_by=blocked if reason == "bound_blocked" else (),
                    # R0: the message reaches a provenance item's cause, so it carries no float.
                    message=f"pseudo-step {k}: {retry} trials rejected, the last {reason}",
                )
            tau_try = shrunk

        # §7.3.6 and §7.4: accepted; SER on accepted iterates only, unless the stop test holds.
        trial, trial_values, alpha_max, accepted_step_inf, landed = accepted
        before, residual_before = x, values
        x, values = trial, trial_values
        next_scaled = problem.scaling.scale_residual(values, problem.row_ids)
        phi_next = _norm(next_scaled)
        tau_next: float | None = None
        ratio: float | None = None
        if not met(values):
            ratio = min(
                max(phi / max(phi_next, settings.phi_floor), settings.gamma_min),
                settings.gamma_max,
            )
            tau_next = min(max(tau_try * ratio, settings.tau_min_s), settings.tau_max_s)
            tau = tau_next
        steps.append(
            PseudoStep(
                index=k,
                tau=tau_try,
                alpha=alpha_max,
                retries=retry,
                phi_before=phi,
                phi=phi_next,
                tau_next=tau_next,
                ser_ratio=ratio,
                x_before=before,
                x=x,
                residual_before=residual_before,
                residual=values,
                landing=landed,
            )
        )
        trace.record(
            kind="step_accepted",
            attempt=attempt,
            iteration=k,
            signature=signature,
            state_sha256=digest(x),
            residual_inf_unscaled=float(np.max(np.abs(np.asarray(values)))),
            merit=0.5 * phi_next * phi_next,
            counters=running,
            alpha=alpha_max,
            step_inf_scaled=accepted_step_inf,
            trial_status="accepted",
            pseudo_step=tau_try,
            pseudo_step_next=tau_next,
            ser_ratio=ratio,
        )
        if observer is not None:
            requested = observer.should_close(k)
            if requested is not None:
                return record(
                    requested,
                    values,
                    iterations=k + 1,
                    tau_end=tau,
                    message=(
                        "the attempt controller closed the attempt: a persistent phase wall, "
                        "not an overshoot (§9.3)"
                    ),
                )

    raise AssertionError("unreachable: the pseudo-step budget is checked inside the loop")


@dataclass(frozen=True)
class _Polished:
    outcome: SolveOutcome | None
    x: npt.NDArray[np.float64]
    values: tuple[float, ...]
    counters: Counters
    message: str = ""


def _polish(
    problem: Problem,
    x: npt.NDArray[np.float64],
    values: tuple[float, ...],
    signature: AttemptSignature,
    attempt: int,
    iteration: int,
    trace: Trace,
    counters: Counters,
    compare_empty: bool = False,
) -> tuple[str, _Polished]:
    """T04 §7.5: one Newton step from the stopped iterate `x_c`, with the unsigned Jacobian, K03
    §5.3's `α_max` and one trial. It replaces `x_c` iff it evaluates `ok`, reports the frozen
    signature, meets K03 §5.2 and its worst row ratio is no larger than `x_c`'s.

    Returns the verdict — `accepted` or `rejected:<reason>` — and the state to report. An `error`
    evaluation is not a verdict on the trial but a defect (K03 §5.5), as everywhere else, and ends
    the attempt `EVALUATION_ERROR`."""
    tolerance = problem.tolerance_vector()
    lower = problem.lower_bound_vector()
    running = counters.plus(jacobian_calls=1)
    array = np.asarray(values, dtype=np.float64)
    infinity = float(np.max(np.abs(array))) if array.size else 0.0
    merit = problem.scaling.merit(values, problem.row_ids)
    digest = state_sha256(x, problem.variable_ids)
    trace.record(
        kind="jacobian",
        attempt=attempt,
        iteration=iteration,
        signature=signature,
        state_sha256=digest,
        residual_inf_unscaled=infinity,
        merit=merit,
        counters=running,
        message="polish",
    )
    kept = _Polished(None, x, values, running)

    def rejected(
        reason: str,
        rejection: RejectionReason | None,
        *,
        alpha: float | None = None,
        state: str = "",
        at: Counters = running,
    ) -> tuple[str, _Polished]:
        trace.record(
            kind="trial",
            attempt=attempt,
            iteration=iteration,
            signature=signature,
            state_sha256=state,
            residual_inf_unscaled=float("nan"),
            merit=float("nan"),
            counters=at,
            alpha=alpha,
            trial_status="rejected",
            rejection_reason=rejection,
            message=f"polish(rejected:{reason})",
        )
        return f"rejected:{reason}", replace(kept, counters=at)

    try:
        unscaled = sp.csc_matrix(problem.jacobian(x))
    except JacobianUnavailableError as unavailable:
        # F15 (h) and T04 review M1: the Jacobian at x_c failing is a defect, like a trial's
        # `error` — the attempt ends `EVALUATION_ERROR` with x_c kept, never a rejected polish.
        rejected("error", None, at=running)
        return "rejected:error", _Polished(
            "EVALUATION_ERROR", x, values, running, f"the Jacobian at x_c: {unavailable}"
        )
    running = running.plus(factorizations=1)
    scaled = _scale_matrix(unscaled, problem)
    try:
        step_scaled, linear = solve_linear(
            scaled, -problem.scaling.scale_residual(values, problem.row_ids)
        )
    except LinearSolveFailedError:
        return rejected("linear_solve_failed", "linear_solve_failed", at=running)
    # ADR 0004 D2/D3: every factorization carries its record onto an event, the polish's too.
    trace.record(
        kind="linear_solve",
        attempt=attempt,
        iteration=iteration,
        signature=signature,
        state_sha256=digest,
        residual_inf_unscaled=infinity,
        merit=merit,
        counters=running,
        linear=LinearRecord(
            residual_normalized=linear.residual_normalized,
            u_diag_min_abs=linear.min_abs_u_diagonal,
            u_diag_max_abs=linear.max_abs_u_diagonal,
            nnz_l=linear.nnz_l,
            nnz_u=linear.nnz_u,
        ),
        message="polish",
    )
    direction = problem.scaling.unscale_state(step_scaled, problem.variable_ids)
    alpha_max, landing = _bound_aware_alpha(x, direction, lower)
    if alpha_max == 0.0:
        return rejected("bound_blocked", "bound_blocked", at=running)
    trial = _trial_point(x, direction, alpha_max, lower, landing)
    running = running.plus(residual_calls=1)
    evaluation = problem.residual(trial)
    trial_digest = state_sha256(trial, problem.variable_ids)
    if evaluation.status == "error":
        rejected("error", None, alpha=alpha_max, state=trial_digest, at=running)
        return "rejected:error", _Polished(
            "EVALUATION_ERROR", x, values, running, evaluation.message
        )
    if evaluation.status != "ok" or evaluation.values is None:
        return rejected(
            "invalid_trial", "invalid_trial", alpha=alpha_max, state=trial_digest, at=running
        )
    if another_signature(signature, evaluation.signature, compare_empty=compare_empty):
        return rejected(
            "phase_update_required",
            "phase_update_required",
            alpha=alpha_max,
            state=trial_digest,
            at=running,
        )
    polished = np.asarray(evaluation.values, dtype=np.float64)
    if not bool(np.all(np.abs(polished) <= tolerance)) or float(
        np.max(np.abs(polished) / tolerance)
    ) > float(np.max(np.abs(array) / tolerance)):
        return rejected("not_better", None, alpha=alpha_max, state=trial_digest, at=running)
    trace.record(
        kind="trial",
        attempt=attempt,
        iteration=iteration,
        signature=signature,
        state_sha256=trial_digest,
        residual_inf_unscaled=float(np.max(np.abs(polished))) if polished.size else 0.0,
        merit=problem.scaling.merit(evaluation.values, problem.row_ids),
        counters=running,
        alpha=alpha_max,
        trial_status="accepted",
        message="polish",
    )
    return "accepted", _Polished(None, trial, evaluation.values, running)
