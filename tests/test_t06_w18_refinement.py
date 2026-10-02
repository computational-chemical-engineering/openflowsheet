"""T06 W18 (b): ADR 0018's terminal refinement in the Newton core, on constructed problems (A88).

`solve_newton(..., refinement=τ)` is K03 §5's core with D2–D4 added at a `CONVERGED` exit: at
`k ≥ 1` the chord correction `c = −S_x Ĵ_{k−1}⁻¹ F̂(x_k)` — one back-solve against the attempt's
last factorization — is judged column by column against `τ_kind`; above it the attempt takes one
more iteration of the same loop, kept only if its step was accepted, every row passes and its own
chord is within `τ_kind`. It never changes the attempt's outcome (D4′; the plan-level budget
behaviour is A96, `test_t06_w24_budget.py`). With `refinement=None` nothing here runs.

The problems have closed-form roots and owe nothing to the flowsheet code:

- `cubic`: `u + u³/2 − 3/2 = 0`, `v − u = 0`, root `(1, 1)`, from `(2, 0)`; rows judged at
  `1e-2`, so Newton stops at `k = 3` with `u − 1 = 2.30e-3` — 230 × a column tolerance of `1e-5`.
- `square`: `x² = 0`, the double root of A88 (d); Newton contracts by exactly ½ per step.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

import numpy as np
import numpy.typing as npt
import pytest
import scipy.sparse as sp

from openflowsheet.numerics.newton import (
    Evaluation,
    JacobianUnavailableError,
    NewtonResult,
    Problem,
    solve_newton,
)
from openflowsheet.numerics.scaling import Scaling
from openflowsheet.orchestrator.trace import AttemptSignature, SolvePolicy, Trace

POLICY = SolvePolicy(policy_id="T06-W18-constructed", residual_tolerances={}, scales={})
#: The column tolerance of the constructed problems (a stand-in for a registered `τ_kind`).
TAU = 1e-5
CUBIC_START = (2.0, 0.0)
#: `cubic` under K03's Newton: `CONVERGED` at this iteration (measured below, not assumed).
CUBIC_K = 3


def cubic(
    *,
    invalid_after: int | None = None,
    signature_after: int | None = None,
    jacobian_fails_after: int | None = None,
) -> Problem:
    """`cubic`, optionally made to fail from a given residual or Jacobian call on (A88 (e))."""
    ids, rows = ("u", "v"), ("r1", "r2")
    calls = {"residual": 0, "jacobian": 0}

    def evaluate(x: npt.NDArray[np.float64]) -> Evaluation:
        calls["residual"] += 1
        if invalid_after is not None and calls["residual"] > invalid_after:
            return Evaluation(
                status="invalid_trial_state", message="outside the constructed domain"
            )
        u, v = float(x[0]), float(x[1])
        signature: AttemptSignature | None = None
        if signature_after is not None and calls["residual"] > signature_after:
            signature = (("unit", "OTHER"),)  # type: ignore[assignment]
        return Evaluation(status="ok", values=(u + 0.5 * u**3 - 1.5, v - u), signature=signature)

    def jacobian(x: npt.NDArray[np.float64]) -> sp.csc_matrix:
        calls["jacobian"] += 1
        if jacobian_fails_after is not None and calls["jacobian"] > jacobian_fails_after:
            raise JacobianUnavailableError("error", "the property-call budget is spent")
        u = float(x[0])
        return sp.csc_matrix(np.array([[1.0 + 1.5 * u * u, 0.0], [-1.0, 1.0]]))

    return Problem(
        variable_ids=ids,
        row_ids=rows,
        residual=evaluate,
        jacobian=jacobian,
        scaling=Scaling(column=dict.fromkeys(ids, 1.0), row=dict.fromkeys(rows, 1.0)),
        row_tolerance=dict.fromkeys(rows, 1e-2),
    )


def square() -> Problem:
    """`x² = 0` judged at `1e-8`: Newton halves `x` each step and stops at `x = 2⁻¹⁴`."""

    def evaluate(x: npt.NDArray[np.float64]) -> Evaluation:
        return Evaluation(status="ok", values=(float(x[0]) ** 2,))

    def jacobian(x: npt.NDArray[np.float64]) -> sp.csc_matrix:
        return sp.csc_matrix(np.array([[2.0 * float(x[0])]]))

    return Problem(
        variable_ids=("x",),
        row_ids=("r",),
        residual=evaluate,
        jacobian=jacobian,
        scaling=Scaling(column={"x": 1.0}, row={"r": 1.0}),
        row_tolerance={"r": 1e-8},
    )


def run(
    problem: Problem,
    start: tuple[float, ...],
    refinement: Mapping[str, float] | None,
    policy: SolvePolicy = POLICY,
    **options: Any,
) -> tuple[NewtonResult, Trace]:
    trace = Trace()
    return solve_newton(
        problem, start, policy, trace=trace, refinement=refinement, **options
    ), trace


def r0(trace: Trace) -> list[tuple[Any, ...]]:
    """The events' R0 projection (`run.identity.r0_projection`'s fields) and their state hashes."""
    return [
        (e.kind, e.attempt, e.iteration, e.signature, e.outcome, e.state_sha256)
        for e in trace.events
    ]


def closing(trace: Trace) -> Any:
    (event,) = trace.of_kind("attempt_closed")
    return event


def everywhere(tau: float) -> dict[str, float]:
    return {"u": tau, "v": tau}


def test_cubic_under_newton_stops_inside_the_row_window() -> None:
    """The premise of (a): K03's Newton stops at `k = 3` with an error 230 × `TAU`."""
    result, _ = run(cubic(), CUBIC_START, None)
    assert result.outcome == "CONVERGED"
    assert result.iterations == CUBIC_K
    assert 200 * TAU < abs(result.x[0] - 1.0) < 300 * TAU


def test_a88_a_the_refinement_fires_once_and_is_kept() -> None:
    """(a): one refinement, kept; its own chord after it is `≤ 1`, and the true error with it."""
    plain, plain_trace = run(cubic(), CUBIC_START, None)
    refined, trace = run(cubic(), CUBIC_START, everywhere(TAU))
    assert refined.outcome == "CONVERGED"
    assert refined.iterations == CUBIC_K + 1
    message = closing(trace).message
    assert message.startswith("terminal_refinement(accepted: chord ")
    before = float(message.rsplit("): chord ", 1)[1].split(" at ")[0])
    after = float(message.split("accepted: chord ")[1].split(" at ")[0])
    assert before > 1.0 >= after
    assert message.endswith(" at u")
    # The chord estimates the first-order error within a few per cent; the refined iterate is
    # within `TAU` of the root.
    assert before == pytest.approx(abs(plain.x[0] - 1.0) / TAU, rel=0.1)
    assert np.all(np.abs(refined.x - 1.0) <= TAU)
    # D3: one more iteration, recorded as any iteration is; D5: nothing else in the trace moves.
    assert r0(trace)[: len(plain_trace.events) - 1] == r0(plain_trace)[:-1]
    extra = [event.kind for event in trace.events[len(plain_trace.events) - 1 : -1]]
    assert extra == ["jacobian", "linear_solve", "step_accepted"]
    assert refined.counters.factorizations == plain.counters.factorizations + 1
    assert refined.counters.jacobian_calls == plain.counters.jacobian_calls + 1
    assert refined.counters.residual_calls == plain.counters.residual_calls + 1
    assert closing(trace).linear is not None
    assert closing(trace).state_sha256 == trace.of_kind("step_accepted")[-1].state_sha256


def test_a88_b_no_refinement_below_the_tolerance_and_newton_bit_for_bit() -> None:
    """(b): stopped with `ρ_max ≤ 1`: no refinement; counters, R0 trace and state are `newton`'s;
    the closing event differs only in the chord's `linear` record (D5, A87 (b))."""
    plain, plain_trace = run(cubic(), CUBIC_START, None)
    judged, trace = run(cubic(), CUBIC_START, everywhere(1.0))
    assert judged.outcome == plain.outcome == "CONVERGED"
    assert judged.iterations == plain.iterations
    assert judged.counters == plain.counters
    assert judged.x.tobytes() == plain.x.tobytes()
    assert r0(trace) == r0(plain_trace)
    assert closing(trace).message == closing(plain_trace).message == ""
    assert closing(plain_trace).linear is None
    assert closing(trace).linear is not None
    documents = [e.as_document() for e in trace.events]
    plain_documents = [e.as_document() for e in plain_trace.events]
    assert documents[:-1] == plain_documents[:-1]
    assert {k: v for k, v in documents[-1].items() if k != "linear"} == plain_documents[-1]


def test_a88_b_a_column_without_a_tolerance_is_never_judged() -> None:
    """D2: only the columns whose kind has an acceptance rule; `v` alone at 1.0 does not fire."""
    plain, _ = run(cubic(), CUBIC_START, None)
    judged, trace = run(cubic(), CUBIC_START, {"v": 1.0})
    assert judged.counters == plain.counters
    assert closing(trace).message == ""


def test_a88_c_a_root_passed_in_is_not_refined() -> None:
    """(c): `k = 0` converges with no Jacobian and no chord (blueprint §7.3; NUM-04 holds)."""
    result, trace = run(cubic(), (1.0, 1.0), everywhere(TAU))
    assert result.outcome == "CONVERGED"
    assert result.iterations == 0
    assert result.counters.jacobian_calls == 0
    assert result.counters.factorizations == 0
    assert closing(trace).message == ""
    assert closing(trace).linear is None


def test_a88_d_a_double_root_does_not_contract_and_is_reverted() -> None:
    """(d): `x² = 0` stopped at its row tolerance. The chord with `J(x_{k−1}) = 4 x_k` reads
    `x_k/4`; the refinement halves `x` and its chord with `J(x_k)` reads `x_k/8` — a contraction
    of exactly ½, above 1 — so it is reverted and `x_k` is returned `CONVERGED`."""
    plain, plain_trace = run(square(), (1.0,), None)
    refined, trace = run(square(), (1.0,), {"x": 1e-7})
    assert plain.outcome == refined.outcome == "CONVERGED"
    assert refined.x.tobytes() == plain.x.tobytes() == np.array([2.0**-14]).tobytes()
    assert refined.iterations == plain.iterations == 14
    before = float(plain.x[0]) / 4 / 1e-7
    after = float(plain.x[0]) / 8 / 1e-7
    assert closing(trace).message == (
        f"terminal_refinement(reverted: chord {after!r} at x): chord {before!r} at x"
    )
    assert after == before / 2 > 1.0
    assert closing(trace).state_sha256 == closing(plain_trace).state_sha256
    assert closing(trace).iteration == 14
    # The refinement's calls were made and are counted (metered like any other iteration).
    assert refined.counters.jacobian_calls == plain.counters.jacobian_calls + 1
    assert refined.counters.residual_calls == plain.counters.residual_calls + 1


def _abandoned(
    problem: Problem, reason: str, policy: SolvePolicy = POLICY, **options: Any
) -> tuple[NewtonResult, Trace]:
    plain, plain_trace = run(cubic(), CUBIC_START, None)
    result, trace = run(problem, CUBIC_START, everywhere(TAU), policy, **options)
    assert result.outcome == "CONVERGED"
    assert result.x.tobytes() == plain.x.tobytes()
    assert result.residual == plain.residual
    assert result.iterations == CUBIC_K
    assert closing(trace).state_sha256 == closing(plain_trace).state_sha256
    assert closing(trace).iteration == CUBIC_K
    message = closing(trace).message
    assert message.startswith(f"terminal_refinement({reason}): chord ")
    assert message.endswith(" at u")
    return result, trace


#: `cubic`'s residual calls to `x_k` under `newton`: the start plus one accepted trial per step.
CUBIC_CALLS = CUBIC_K + 1


def test_a88_e_a_refinement_whose_trials_the_line_search_rejects_is_abandoned() -> None:
    _, trace = _abandoned(cubic(invalid_after=CUBIC_CALLS), "abandoned: LINE_SEARCH_FAILED")
    rejected = trace.of_kind("trial")
    assert len(rejected) == POLICY.step_halvings_max + 1
    assert {event.rejection_reason for event in rejected} == {"invalid_trial"}


def test_a88_e_a_refinement_whose_trials_change_the_signature_is_abandoned() -> None:
    frozen: AttemptSignature = (("unit", "SAME"),)  # type: ignore[assignment]
    _, trace = _abandoned(
        cubic(signature_after=CUBIC_CALLS),
        "abandoned: LINE_SEARCH_FAILED",
        signature=frozen,
    )
    rejected = trace.of_kind("trial")
    assert rejected
    assert {event.rejection_reason for event in rejected} == {"phase_update_required"}


def test_a88_e_a_refinement_whose_jacobian_evaluation_fails_typed_is_abandoned() -> None:
    result, trace = _abandoned(cubic(jacobian_fails_after=CUBIC_K), "abandoned: EVALUATION_ERROR")
    assert result.counters.jacobian_calls == CUBIC_K + 1
    assert result.counters.factorizations == CUBIC_K


def test_a88_e_no_refinement_at_the_iteration_budget() -> None:
    capped = SolvePolicy(
        policy_id="T06-W18-constructed",
        residual_tolerances={},
        scales={},
        max_iterations_per_attempt=CUBIC_K,
    )
    result, _ = _abandoned(cubic(), "abandoned: BUDGET_EXHAUSTED(newton_iterations)", capped)
    plain, _ = run(cubic(), CUBIC_START, None, capped)
    assert result.counters == plain.counters


def test_a88_e_an_observer_that_closes_the_attempt_abandons_the_refinement() -> None:
    """D4: the observer closing the attempt during the refinement's iteration."""

    class Closing:
        def rejected(self, *args: object) -> None:
            return None

        def should_close(self, iteration: int) -> Any:
            return "PHASE_UPDATE_REQUIRED" if iteration == CUBIC_K else None

    _abandoned(cubic(), "abandoned: PHASE_UPDATE_REQUIRED", observer=Closing())


@pytest.mark.parametrize("factory", [cubic, square])
def test_refinement_none_is_k03_newton(factory: Callable[[], Problem]) -> None:
    """Without `refinement` the core is K03 §5's: the same trace documents and state twice."""
    start = CUBIC_START if factory is cubic else (1.0,)
    first, first_trace = run(factory(), start, None)
    second, second_trace = run(factory(), start, None)
    assert [e.as_document() for e in first_trace.events] == [
        e.as_document() for e in second_trace.events
    ]
    assert all(event.linear is None for event in first_trace.of_kind("attempt_closed"))
    assert first.x.tobytes() == second.x.tobytes()
