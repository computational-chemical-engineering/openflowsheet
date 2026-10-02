"""K03 M3: the damped Newton and its bounded line search, on the registered synthetic seeds.

Specification §13.7 registers seven problems with no thermodynamics in them, each chosen so that
one rule of §5 is the thing that decides the outcome: an affine recycle that must converge in
exactly one step, a root passed in that must converge with no factorization at all, a residual
with no root that must stagnate rather than claim infeasibility, a bound that must be landed on
exactly and a bound that must block, an evaluator with a domain that must produce twenty-one
rejected trials, and a singular Jacobian that must be a typed failure.

Testing the solver here first is deliberate. A solver first exercised on the flowsheet it was
written for has been tested against itself; these seeds have closed-form answers that owe
nothing to any code in this repository.
"""

from __future__ import annotations

import math

import numpy as np
import pytest
import scipy.sparse as sp

from openflowsheet.numerics.newton import Evaluation, Problem, solve_newton
from openflowsheet.numerics.scaling import Scaling
from openflowsheet.orchestrator.trace import SolvePolicy, Trace

POLICY = SolvePolicy(policy_id="K03-synthetic-seeds", residual_tolerances={}, scales={})


def scalar_problem(
    residual: object,
    derivative: object,
    *,
    tolerance: float = 1e-8,
    lower: float | None = None,
    scale: float = 1.0,
    domain: object = None,
) -> Problem:
    """One equation in one unknown, with an optional bound and an optional evaluator domain."""

    def evaluate(x: np.ndarray) -> Evaluation:
        value = float(x[0])
        if domain is not None and not domain(value):  # type: ignore[operator]
            return Evaluation(
                status="invalid_trial_state", message=f"x = {value} is outside the domain"
            )
        return Evaluation(status="ok", values=(float(residual(value)),))  # type: ignore[operator]

    def jacobian(x: np.ndarray) -> sp.csc_matrix:
        return sp.csc_matrix(np.array([[float(derivative(float(x[0])))]]))  # type: ignore[operator]

    return Problem(
        variable_ids=("x",),
        row_ids=("r",),
        residual=evaluate,
        jacobian=jacobian,
        scaling=Scaling(column={"x": scale}, row={"r": scale}),
        row_tolerance={"r": tolerance},
        lower_bounds={} if lower is None else {"x": lower},
    )


def linear_recycle(recycle_fraction: float) -> Problem:
    """NUM-02: `R(t) = f + r t − t`, `f = (1, 1, 1)`, scale 3 mol/s (registry)."""
    feed = np.array([1.0, 1.0, 1.0])
    ids = ("t_A", "t_B", "t_C")
    rows = ("R_A", "R_B", "R_C")

    def evaluate(t: np.ndarray) -> Evaluation:
        return Evaluation(status="ok", values=tuple(feed + recycle_fraction * t - t))

    def jacobian(t: np.ndarray) -> sp.csc_matrix:
        return sp.csc_matrix(np.eye(3) * (recycle_fraction - 1.0))

    return Problem(
        variable_ids=ids,
        row_ids=rows,
        residual=evaluate,
        jacobian=jacobian,
        scaling=Scaling(column=dict.fromkeys(ids, 3.0), row=dict.fromkeys(rows, 3.0)),
        # ADR 0001 D6's registered component-balance tolerance.
        row_tolerance=dict.fromkeys(rows, 1e-9 + 1e-8 * 3.0),
    )


# --------------------------------------------------------------------------------- NUM-02


@pytest.mark.parametrize(("recycle_fraction", "analytic"), [(0.5, 2.0), (0.95, 20.0)])
def test_num02_converges_in_exactly_one_step_to_the_analytic_answer(
    recycle_fraction: float, analytic: float
) -> None:
    """§13.7: `CONVERGED` in exactly 1 iteration, `α = 1`, residual exactly 0.0 after the step.

    `t = f/(1 − r)` is derivation §8's closed form. The problem is affine, so a Newton step is
    the answer and the residual after it is exactly zero — any damping at all would show here.

    The answer is compared against the closed form *evaluated in doubles*, exactly, and against
    the analytic value at the registered tolerance. Those are two different numbers at r = 0.95:
    `1 − 0.95` is `0.050000000000000044`, so `f/(1 − r)` is `19.999999999999982` and not 20.
    Demanding exactly 20 would demand the solver be more accurate than the closed form it is
    checked against.
    """
    problem = linear_recycle(recycle_fraction)
    trace = Trace()
    result = solve_newton(problem, [1.0, 1.0, 1.0], POLICY, trace=trace)

    assert result.outcome == "CONVERGED"
    assert result.iterations == 1
    closed_form = 1.0 / (1.0 - recycle_fraction)
    assert list(result.x) == [closed_form] * 3
    assert all(abs(value - analytic) < 1e-9 + 1e-8 * 3.0 for value in result.x)
    assert result.residual == (0.0, 0.0, 0.0)
    assert result.counters.factorizations == 1

    accepted = trace.of_kind("step_accepted")
    assert len(accepted) == 1
    assert accepted[0].alpha == 1.0
    assert trace.of_kind("trial") == (), "no trial was rejected, so none is recorded"


def test_num02_at_r_one_is_a_typed_singular_failure() -> None:
    """§13.7 and ADR 0004 D3.3: `dR/dt ≡ 0`, so the factorization is exactly singular."""
    problem = linear_recycle(1.0)
    trace = Trace()
    result = solve_newton(problem, [1.0, 1.0, 1.0], POLICY, trace=trace)

    assert result.outcome == "LINEAR_SOLVE_FAILED"
    assert result.linear_reason == "exactly_singular"
    assert result.iterations == 0
    assert result.residual == (1.0, 1.0, 1.0)
    assert not result.accepted_any
    assert trace.of_kind("linear_solve")[-1].outcome == "LINEAR_SOLVE_FAILED"


def test_num02_is_scale_invariant_in_its_step_but_not_in_its_merit() -> None:
    """A31: the merit is `1/24` at `t⁰ = f` with `S_R = 3`, and `0.375` with `S_R = 1`.

    The accepted step is the same either way — a Newton direction is scale-invariant — so this
    is the test that the transformation is *applied* rather than merely present.
    """
    problem = linear_recycle(0.5)
    # The merit is of the *residual* at t0 = f, which is f + r f - f = (0.5, 0.5, 0.5), not of
    # the state. With S_R = 3: ½ · 3 · (0.5/3)² = 1/24.
    residual_at_f = (0.5, 0.5, 0.5)
    scaled_merit = problem.scaling.merit(residual_at_f, problem.row_ids)
    assert scaled_merit == pytest.approx(1.0 / 24.0, rel=1e-15)

    unscaled = Scaling(
        column=dict.fromkeys(problem.variable_ids, 1.0),
        row=dict.fromkeys(problem.row_ids, 1.0),
    )
    assert unscaled.merit(residual_at_f, problem.row_ids) == pytest.approx(0.375, rel=1e-15)

    mixed = Problem(
        variable_ids=problem.variable_ids,
        row_ids=problem.row_ids,
        residual=problem.residual,
        jacobian=problem.jacobian,
        scaling=Scaling(
            column=dict.fromkeys(problem.variable_ids, 1.0),
            row=dict.fromkeys(problem.row_ids, 3.0),
        ),
        row_tolerance=problem.row_tolerance,
    )
    both = [
        solve_newton(candidate, [1.0, 1.0, 1.0], POLICY, trace=Trace())
        for candidate in (problem, mixed)
    ]
    assert [list(r.x) for r in both] == [[2.0] * 3, [2.0] * 3]


# ---------------------------------------------------------------------- the other six seeds


def test_num01_a_root_converges_at_iteration_zero_with_no_factorization() -> None:
    """§13.7 and blueprint §7.3: an already valid root takes no additional step to qualify."""
    problem = scalar_problem(lambda x: x - 2.0, lambda x: 1.0)
    trace = Trace()
    result = solve_newton(problem, [2.0], POLICY, trace=trace)

    assert result.outcome == "CONVERGED"
    assert result.iterations == 0
    assert result.counters.factorizations == 0
    assert result.counters.jacobian_calls == 0
    assert trace.of_kind("jacobian") == ()


def test_num05_a_residual_with_no_root_stagnates_and_claims_nothing() -> None:
    """§13.7: `R = x² + 0.01` has no root; the merit has a strict positive minimum.

    The outcome must be `STAGNATION`, not an infeasibility claim — blueprint §7.7 forbids
    calling a failure to converge `PHYSICALLY_INFEASIBLE` without independent evidence, and
    `PHYSICALLY_INFEASIBLE` is not in the vocabulary at all.
    """
    problem = scalar_problem(lambda x: x * x + 0.01, lambda x: 2.0 * x)
    result = solve_newton(problem, [1.0], POLICY, trace=Trace())

    assert result.outcome == "STAGNATION"
    assert 0.01 <= abs(result.residual[0]) <= 0.0101
    assert result.iterations <= 50
    assert "stagnation, not convergence" in result.message


def test_bnd01_lands_on_its_bound_exactly_and_then_converges() -> None:
    """§13.7's registered numbers, and the bit pattern of the first accepted iterate.

    `R = ln(1 + x) − ½` with `x ≥ 0` from `x⁰ = 4`. The Newton direction overshoots the bound,
    so the first trial is at `α_max` and lands on `0`. It must be **exactly** `+0.0`: ADR 0001
    D3.1 makes exact zero the difference between a dormant stream and a flowing one, so a
    landing that misses by an ulp changes what the state means.
    """
    problem = scalar_problem(
        lambda x: math.log1p(x) - 0.5,
        lambda x: 1.0 / (1.0 + x),
        tolerance=1e-12,
        lower=0.0,
        domain=lambda x: x > -1.0,
    )
    trace = Trace()
    result = solve_newton(problem, [4.0], POLICY, trace=trace)

    first = trace.of_kind("step_accepted")[0]
    assert first.alpha == pytest.approx(0.72108586792820575129, rel=1e-12)

    assert result.outcome == "CONVERGED"
    assert result.x[0] == pytest.approx(0.64872127070012814685, abs=1e-12)
    assert result.iterations <= 10

    # The registered direction, recomputed rather than read from the solver.
    assert -(math.log1p(4.0) - 0.5) / (1.0 / 5.0) == pytest.approx(-5.547189562170501873, rel=1e-15)


def test_bnd01_first_iterate_is_positive_zero_bit_for_bit() -> None:
    """The landing itself, separated out so it cannot be lost in a tolerance above."""
    seen: list[float] = []

    def evaluate(x: np.ndarray) -> Evaluation:
        seen.append(float(x[0]))
        return Evaluation(status="ok", values=(math.log1p(float(x[0])) - 0.5,))

    problem = Problem(
        variable_ids=("x",),
        row_ids=("r",),
        residual=evaluate,
        jacobian=lambda x: sp.csc_matrix(np.array([[1.0 / (1.0 + float(x[0]))]])),
        scaling=Scaling(column={"x": 1.0}, row={"r": 1.0}),
        row_tolerance={"r": 1e-12},
        lower_bounds={"x": 0.0},
    )
    solve_newton(problem, [4.0], POLICY, trace=Trace())
    landing = seen[1]
    assert landing == 0.0
    assert math.copysign(1.0, landing) == 1.0, "the bound landing must be +0.0, not -0.0"


def test_bnd02_a_direction_pointing_out_of_the_feasible_set_blocks() -> None:
    """§13.7: `R = x + 1`, `x ≥ 0`, `x⁰ = 0`. The step is −1 and `α_max` is 0."""
    problem = scalar_problem(lambda x: x + 1.0, lambda x: 1.0, lower=0.0)
    result = solve_newton(problem, [0.0], POLICY, trace=Trace())

    assert result.outcome == "BOUND_BLOCKED"
    assert result.iterations == 0
    assert result.x[0] == 0.0
    assert not result.accepted_any


def test_num06_exhausts_the_line_search_on_an_evaluator_domain() -> None:
    """§13.7: twenty-one rejected trials, every one `invalid_trial`, no accepted step.

    `R = x − 5` from `x⁰ = 3` with the evaluator refusing `x > 3`. The Newton step is +2 and
    every halving of it still leaves the domain, so the line search runs out. Shortening the
    step is blueprint §7.7's authorized response to an invalid trial; nothing is clipped back
    into the domain, because clipping would answer a different problem.
    """
    problem = scalar_problem(lambda x: x - 5.0, lambda x: 1.0, domain=lambda x: x <= 3.0)
    trace = Trace()
    result = solve_newton(problem, [3.0], POLICY, trace=trace)

    assert result.outcome == "LINE_SEARCH_FAILED"
    assert result.iterations == 0
    assert result.residual == (-2.0,)
    assert abs(result.residual[0]) == 2.0

    trials = trace.of_kind("trial")
    assert len(trials) == 21, "alpha = 1, 1/2, ..., 2^-20 is twenty-one trials"
    assert {trial.rejection_reason for trial in trials} == {"invalid_trial"}
    assert trials[0].alpha == 1.0
    assert trials[-1].alpha == pytest.approx(2.0**-20)
    assert trace.of_kind("step_accepted") == ()


# ------------------------------------------------------------------------- the trace itself


def test_a01_the_trace_is_well_formed() -> None:
    """A01, on the part of it M3 produces: strictly increasing, one close, counters monotone."""
    trace = Trace()
    result = solve_newton(linear_recycle(0.5), [1.0, 1.0, 1.0], POLICY, trace=trace)

    events = trace.events
    assert [event.sequence for event in events] == list(range(len(events)))
    assert len(trace.of_kind("attempt_closed")) == 1
    assert trace.of_kind("attempt_closed")[0].outcome == result.outcome

    for earlier, later in zip(events, events[1:], strict=False):
        for field_name in (
            "property_calls",
            "residual_calls",
            "jacobian_calls",
            "factorizations",
        ):
            assert getattr(later.counters, field_name) >= getattr(earlier.counters, field_name), (
                field_name
            )


def test_the_armijo_condition_is_the_registered_one() -> None:
    """`c = 1e-4` and twenty halvings, from §5.9, asserted on the policy the solver was given."""
    assert POLICY.armijo_c == 1e-4
    assert POLICY.step_halvings_max == 20
    assert POLICY.stagnation_window == 5
    assert POLICY.stagnation_ratio == 0.99
    assert POLICY.max_iterations_per_attempt == 50
    assert POLICY.merit == "scaled_residual_half_norm2"


def test_a_policy_records_the_linear_solver_it_used() -> None:
    """The ADR 0004 configuration travels with the policy, so a trace is self-describing."""
    assert POLICY.linear_solver["name"] == "scipy.sparse.linalg.splu"
    assert POLICY.linear_solver["permc_spec"] == "COLAMD"
    assert POLICY.linear_solver["options"]["IterRefine"] == "NOREFINE"


def test_an_evaluation_cannot_carry_both_a_failure_and_an_answer() -> None:
    """The placeholder-success path, refused by the type."""
    with pytest.raises(ValueError, match="must not carry values"):
        Evaluation(status="out_of_domain", values=(1.0,))
    with pytest.raises(ValueError, match="must carry values"):
        Evaluation(status="ok")


def test_the_iteration_budget_is_a_typed_outcome() -> None:
    """§5.6: reaching the cap unconverged is `BUDGET_EXHAUSTED(newton_iterations)`.

    `R = x³ − 2x + 2` from `x⁰ = 0` is the classical Newton two-cycle: it oscillates 0, 1, 0, 1
    forever without converging and without stagnating, because the merit returns to its previous
    value rather than settling.
    """
    capped = SolvePolicy(
        policy_id="capped",
        residual_tolerances={},
        scales={},
        max_iterations_per_attempt=6,
        stagnation_window=50,
    )
    problem = scalar_problem(
        lambda x: x**3 - 2.0 * x + 2.0, lambda x: 3.0 * x * x - 2.0, tolerance=1e-10
    )
    result = solve_newton(problem, [0.0], capped, trace=Trace())
    assert result.outcome == "BUDGET_EXHAUSTED"
    assert result.budget == "newton_iterations"
    assert result.iterations == 6


# ------------------------------------------------- the rules that needed a state to bite them


def test_convergence_is_judged_on_the_unscaled_residual() -> None:
    """§5.2: the acceptance rule is the registered tolerance against `F`, never against `F̂`.

    The state that makes it bite: a residual of 6e-8 with a row scale of 3 and the registered
    component tolerance of 3.1e-8. Unscaled it is *not* converged; scaled it is 2e-8 and would
    be. Blueprint §7.3 keeps verification tolerances independent of numerical scaling precisely
    so that choosing a scale cannot change whether an answer is accepted.
    """
    problem = Problem(
        variable_ids=("x",),
        row_ids=("r",),
        residual=lambda x: Evaluation(status="ok", values=(float(x[0]),)),
        jacobian=lambda x: sp.csc_matrix(np.array([[1.0]])),
        scaling=Scaling(column={"x": 3.0}, row={"r": 3.0}),
        row_tolerance={"r": 1e-9 + 1e-8 * 3.0},
    )
    result = solve_newton(problem, [6e-8], POLICY, trace=Trace())
    assert result.outcome == "CONVERGED"
    assert result.iterations == 1, (
        "6e-8 is above the registered 3.1e-8 unscaled and below it once divided by the row "
        "scale of 3; converging at iteration 0 means the test was made on the scaled residual"
    )
    assert result.x[0] == 0.0


def test_convergence_needs_every_row_and_not_merely_one() -> None:
    """§5.2: *every* row satisfies its tolerance. One converged row is not a converged solve."""
    problem = Problem(
        variable_ids=("a", "b"),
        row_ids=("ra", "rb"),
        residual=lambda x: Evaluation(status="ok", values=(float(x[0]), float(x[1]))),
        jacobian=lambda x: sp.csc_matrix(np.eye(2)),
        scaling=Scaling(column={"a": 1.0, "b": 1.0}, row={"ra": 1.0, "rb": 1.0}),
        row_tolerance={"ra": 1e-9, "rb": 1e-9},
    )
    result = solve_newton(problem, [0.0, 1.0], POLICY, trace=Trace())
    assert result.outcome == "CONVERGED"
    assert result.iterations == 1, (
        "row `ra` starts converged and `rb` does not; stopping at iteration 0 means the test "
        "was an `any` over rows rather than an `all`"
    )


def test_a_bound_landing_that_arithmetic_would_miss_is_exact() -> None:
    """§5.3: the component set to the bound *value*, not to `x_i + α d_i`.

    The state that makes it bite, found by search: from `x = 3.8139552653167543` along
    `d = −6.403089514483589` the exact `α_max` gives `x + α d = −4.440892098500626e-16`, which
    is below the bound and negative. The specification names that magnitude; here it is.

    It matters beyond tidiness. ADR 0001 D3.1 makes exact zero the difference between a dormant
    stream and a flowing one, so a tear component that lands at `−4e-16` instead of `0` is a
    stream the whole model treats differently — and a *negative* flow at that.
    """
    start = 3.8139552653167543
    direction = -6.403089514483589
    target = start + direction
    assert start + ((0.0 - start) / direction) * direction != 0.0, "the case must still miss"

    seen: list[float] = []

    def evaluate(x: np.ndarray) -> Evaluation:
        seen.append(float(x[0]))
        return Evaluation(status="ok", values=(float(x[0]) - target,))

    problem = Problem(
        variable_ids=("t",),
        row_ids=("R",),
        residual=evaluate,
        jacobian=lambda x: sp.csc_matrix(np.array([[1.0]])),
        scaling=Scaling(column={"t": 1.0}, row={"R": 1.0}),
        row_tolerance={"R": 1e-12},
        lower_bounds={"t": 0.0},
    )
    solve_newton(problem, [start], POLICY, trace=Trace())

    landing = seen[1]
    assert landing == 0.0
    assert math.copysign(1.0, landing) == 1.0
    assert landing != start + ((0.0 - start) / direction) * direction


def test_a_trial_in_another_phase_regime_is_rejected_not_accepted() -> None:
    """§5.4(ii) and blueprint [A01]: the attempt's phase set is frozen within the attempt.

    A trial that evaluates successfully but *in another regime* is not an answer to the problem
    the attempt is solving. It is rejected with `phase_update_required` and the step halves —
    §9.3 treats a phase change one step away as an overshoot first.
    """
    liquid = (("U-FLASH", "LIQUID"),)
    two_phase = (("U-FLASH", "TWO_PHASE"),)

    def evaluate(x: np.ndarray) -> Evaluation:
        value = float(x[0])
        signature = two_phase if value > 1.5 else liquid
        return Evaluation(status="ok", values=(value - 4.0,), signature=signature)

    problem = Problem(
        variable_ids=("x",),
        row_ids=("r",),
        residual=evaluate,
        jacobian=lambda x: sp.csc_matrix(np.array([[1.0]])),
        scaling=Scaling(column={"x": 1.0}, row={"r": 1.0}),
        row_tolerance={"r": 1e-12},
    )
    trace = Trace()
    result = solve_newton(problem, [0.0], POLICY, trace=trace, signature=liquid)

    rejected = [event for event in trace.of_kind("trial") if event.trial_status == "rejected"]
    assert rejected, "the full Newton step lands at 4.0, which is the other regime"
    assert rejected[0].rejection_reason == "phase_update_required"
    assert rejected[0].alpha == 1.0
    # What actually happens, measured: the step halves until it lands just short of the wall,
    # is accepted, and the next step does the same — so the solver *crawls* toward 1.5 and ends
    # in STAGNATION at 1.4999967 with the residual still 2.5. That is the behaviour the
    # specification's §9.3 predicts and the reason `phase_wall_patience` exists: an attempt that
    # keeps rejecting phase-changing trials is at a wall it should stop grinding against, and
    # the controller should close it and restart in the other regime. That controller is M5's.
    # What matters here, and what is asserted, is that the solve never silently crosses.
    assert result.outcome == "STAGNATION"
    assert result.x[0] < 1.5, "the accepted iterates stayed inside the attempt's own regime"
    assert abs(result.residual[0]) > 2.0, "it stagnated short of the root, it did not converge"


def test_an_error_from_an_evaluator_is_not_a_rejected_trial() -> None:
    """§5.5: `error` means a defect, not a bad trial, so it is `EVALUATION_ERROR` and stops.

    Halving the step in response to a defect would turn a bug into twenty-one quiet retries and
    then a `LINE_SEARCH_FAILED` that names the wrong cause.
    """

    def evaluate(x: np.ndarray) -> Evaluation:
        value = float(x[0])
        if value != 3.0:
            return Evaluation(status="error", message="the property provider raised")
        return Evaluation(status="ok", values=(value - 5.0,))

    problem = Problem(
        variable_ids=("x",),
        row_ids=("r",),
        residual=evaluate,
        jacobian=lambda x: sp.csc_matrix(np.array([[1.0]])),
        scaling=Scaling(column={"x": 1.0}, row={"r": 1.0}),
        row_tolerance={"r": 1e-12},
    )
    trace = Trace()
    result = solve_newton(problem, [3.0], POLICY, trace=trace)

    assert result.outcome == "EVALUATION_ERROR"
    assert "property provider raised" in result.message
    assert len(trace.of_kind("trial")) == 1, "it stopped at the first error, it did not halve"
