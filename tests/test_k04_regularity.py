"""K04 §7: the [A08] regularity screen, and the bound a rank test cannot replace.

Two things are easy to get wrong here and both are held by construction rather than by opinion.

**The U-diagonal must not decide.** Blueprint [A08] and ADR 0004 D3.4 both say it is a warning
screen and not a rank-revealing test. The triangular family `U = I - N` has every `U_ii = 1`, so
`min|U_ii| / max|U_ii|` is exactly 1 at every size — while at n = 16, 32 and 64 the same
construction is in turn well conditioned, ill conditioned and rank deficient. One family, three
statuses, one U-diagonal ratio. A screen that consulted it would report the same thing three
times.

**A rank test is not enough.** `x^2 = 0` from `x0 = 1` converges under K03's Newton to
`x = 2^-14` with a 1x1 Jacobian of `2^-13`, whose `rcond` is 1. The matrix is not singular and
the screen is right to say so; what has failed is that the residual tolerance no longer bounds
the solution, and only `||J^-1|| ||F||` sees it.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np
import pytest
import scipy.sparse as sp
from conftest import REPO_ROOT, load_yaml
from test_k04_checks import CASE_IDS, flowsheet_for

from openflowsheet.orchestrator.tear import Syn001TearProblem, solve_tear
from openflowsheet.verify.regularity import (
    SVD_DIMENSION_CAP,
    TAU_ILL,
    TAU_SCALED_MIN,
    absolute_conditioning_threshold,
    screen,
    solution_error_bound,
    target_jacobian,
)


@pytest.fixture(scope="module")
def reference() -> Mapping[str, Any]:
    return load_yaml(REPO_ROOT / "benchmarks" / "k04" / "reference_values.yaml")


@pytest.fixture(scope="module")
def variants() -> dict[str, Mapping[str, Any]]:
    loaded = load_yaml(REPO_ROOT / "benchmarks" / "syn001" / "reference_values.yaml")
    return {entry["case_id"]: entry for entry in loaded["variants"]}


def triangular(n: int) -> sp.csc_matrix:
    """Plan §6.3's matrix "with innocuous diagonal entries": `U = I - N`, `U^-1_ij = 2^(j-i-1)`."""
    return sp.csc_matrix(np.eye(n) - np.triu(np.ones((n, n)), 1))


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_a11_a13_a14_the_screen_at_the_registered_solutions(
    case_id: str, variants: dict[str, Mapping[str, Any]]
) -> None:
    """A11, A13, A14: the 47 x 47 matrix, a clean status, and the bound four orders under."""
    flowsheet = flowsheet_for(variants[case_id])
    result, _ = solve_tear(flowsheet)
    assert result.final_state is not None

    tear = Syn001TearProblem(flowsheet)
    matrix, residual, identity = target_jacobian(tear, result.final_state)

    assert matrix.shape == (47, 47), "A11: 49 rows minus the two eliminated, by 47 variables"
    assert len(residual) == 47
    assert identity["state_sha256"] == result.checkpoint.full_state_sha256

    evidence = screen(matrix, jacobian_identity=identity)
    assert evidence.status == "NO_RANK_LOSS_DETECTED", case_id
    assert evidence.rcond_1 is not None and evidence.rcond_1 >= 1e-5, case_id
    assert evidence.factorization_source == "evaluated_at_final_state"
    assert evidence.u_diagonal_ratio is not None, "recorded, and never consulted"

    # §7.4 as amended: the bound is recorded, and the *absolute* conditioning limit is what
    # can move the verdict. Measured maximum `||J^-1||_1` here is 476 against a limit of
    # 9.58e5 — a margin of 2000.
    assert evidence.ill_conditioned_reason is None, case_id
    assert evidence.inverse_one_norm_threshold == pytest.approx(
        absolute_conditioning_threshold(47), rel=1e-12
    )
    assert evidence.inverse_one_norm_estimate < evidence.inverse_one_norm_threshold
    bound = solution_error_bound(matrix, residual)
    assert bound is not None and bound <= 1e-11, case_id


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_the_screen_reproduces_the_registered_condition_numbers(
    case_id: str, variants: dict[str, Mapping[str, Any]], reference: Mapping[str, Any]
) -> None:
    """The scaled `rcond_1` is a measured figure Fable registered; reproducing it is the check.

    It also pins the *scaled* matrix: unscaled, these same matrices give 9e-12 to 5.9e-11 and a
    fixed threshold would call every correct answer ill conditioned, which is why [A08] says
    "recorded scales".
    """
    key = case_id.removeprefix("SYN-001-").replace("-", "_")
    expected = reference["floors_measured_2026_09_22"]["rcond_1_target_47x47_scaled"][key]
    flowsheet = flowsheet_for(variants[case_id])
    result, _ = solve_tear(flowsheet)
    tear = Syn001TearProblem(flowsheet)
    matrix, _, _ = target_jacobian(tear, result.final_state)
    evidence = screen(matrix)
    assert evidence.rcond_1 == pytest.approx(float(expected), rel=1e-3), case_id


@pytest.mark.parametrize(
    ("size", "status", "rank"),
    [(16, "NO_RANK_LOSS_DETECTED", 16), (32, "ILL_CONDITIONED", 32), (64, "RANK_DEFICIENT", 63)],
)
def test_a23_one_construction_three_statuses_and_a_useless_u_diagonal(
    size: int, status: str, rank: int, reference: Mapping[str, Any]
) -> None:
    """A23. Three sizes so no threshold can be tuned to pass all three."""
    registered = reference["regularity_fixtures"]["triangular_unit_diagonal"][str(size)]
    evidence = screen(triangular(size))

    assert evidence.status == status
    assert evidence.rcond_1 == pytest.approx(float(registered["rcond_1_exact"]), rel=1e-9)
    assert evidence.rcond_1 == pytest.approx(1.0 / (size * 2.0 ** (size - 1)), rel=1e-9)
    assert evidence.u_diagonal_ratio == 1.0, (
        "every U_ii is 1 at all three sizes: a screen that consulted the U-diagonal would "
        "report the same thing for a well-conditioned, an ill-conditioned and a rank-deficient "
        "matrix (blueprint [A08], ADR 0004 D3.4)"
    )
    if status == "NO_RANK_LOSS_DETECTED":
        assert evidence.escalation is None
    else:
        assert evidence.escalation is not None
        assert evidence.escalation["performed"] is True
        assert evidence.escalation["rank"] == int(registered["expected_svd_rank"]) == rank
        low, high = registered["svd_rank_tolerance_bounds"]
        assert float(low) <= evidence.escalation["tolerance"] <= float(high)


def test_a26_a_matrix_too_large_to_decide_says_so(reference: Mapping[str, Any]) -> None:
    """A26: `INCONCLUSIVE(svd_budget)` retained, never guessed. §1 invariant 4."""
    matrix = sp.csc_matrix(np.diag([1.0] * SVD_DIMENSION_CAP + [1e-12]))
    evidence = screen(matrix)
    assert evidence.status == "INCONCLUSIVE"
    assert evidence.inconclusive_reason == "svd_budget"
    assert evidence.escalation is not None
    assert evidence.escalation["performed"] is False
    assert evidence.escalation["cap"] == SVD_DIMENSION_CAP
    assert evidence.rcond_1 is not None and evidence.rcond_1 < TAU_ILL


def test_a24_an_exactly_singular_matrix_is_rank_deficient_not_a_crash(
    reference: Mapping[str, Any],
) -> None:
    """A24, SQ-0: `x^2 = 0` at its root. Residual exactly 0 and the Jacobian exactly 0.

    Blueprint [A08]: residual satisfaction and regularity are separate, so `RANK_DEFICIENT`
    here does not make `F = 0` false and asserts no continuum — `x^2 = 0` has an isolated root.
    """
    registered = reference["regularity_fixtures"]["x_squared"]["exact_root"]
    evidence = screen(sp.csc_matrix(np.array([[0.0]])))
    assert evidence.status == registered["expected_status"] == "RANK_DEFICIENT"
    assert evidence.escalation is not None
    assert evidence.escalation["rank"] == int(registered["svd_rank"]) == 0
    assert solution_error_bound(sp.csc_matrix(np.array([[0.0]])), np.array([0.0])) is None


def test_a25_the_bound_is_recorded_and_the_verdict_is_verified(
    reference: Mapping[str, Any],
) -> None:
    """A25 as amended, SQ-1, and what a certificate actually promises.

    K03's Newton on `x^2 = 0` from `x0 = 1` halves every step and stops at 14, where the
    residual `2^-28` is inside `1e-8`. The Jacobian `2^-13` is nonsingular and well inside the
    absolute limit (8192 against 4.5e7), so the verdict is **VERIFIED** — and correctly: the
    residuals *are* certified at the registered tolerance. The root is 0 and the answer is
    6e-5, and the certificate says so, because `b = 2^-15` is recorded and the third statement
    explains that no solution accuracy beyond `b` is claimed.

    This fixture is registered because the verdict is VERIFIED there. It is the clearest
    statement in the suite of what the promise is and is not.
    """
    registered = reference["regularity_fixtures"]["x_squared"]["k03_newton_from_1"]
    x_final = float(registered["x_final"])
    assert x_final == 2.0**-14

    jacobian = sp.csc_matrix(np.array([[2.0 * x_final]]))
    residual = np.array([x_final**2])
    assert float(residual[0]) == pytest.approx(float(registered["F_final"]), rel=1e-15)

    evidence = screen(jacobian)
    assert evidence.status == "NO_RANK_LOSS_DETECTED"
    assert evidence.rcond_1 == pytest.approx(1.0, rel=1e-12)

    bound = solution_error_bound(jacobian, residual)
    assert bound is not None
    assert bound == pytest.approx(float(registered["solution_error_bound_scaled"]), rel=1e-15)
    assert bound == pytest.approx(2.0**-15, rel=1e-15)
    assert bound > TAU_SCALED_MIN * 1000, (
        "the bound is three thousand times the scaled tolerance, recorded and disclosed — and "
        "it does not change the verdict, because a certificate certifies residuals"
    )
    assert evidence.inverse_one_norm_estimate == pytest.approx(2.0**13, rel=1e-9)
    assert evidence.inverse_one_norm_estimate < absolute_conditioning_threshold(1, 1e-8)


def test_a34_a_tolerance_tight_enough_trips_the_absolute_limit(
    reference: Mapping[str, Any],
) -> None:
    """A34, SQ-2: the same seed at `tau = 1e-12`, where the limit bites.

    K03's Newton stops at `x = sqrt(tau)`, so `||J^-1||_1 = 1/(2 sqrt(tau))` against the limit
    `tau/eps`. At 1e-8 that is 8192 against 4.5e7 and passes; at 1e-12 it is 524288 against
    4503.6 and trips, so the status is `ILL_CONDITIONED(absolute)` and the verdict `UNVERIFIED`.
    A scale-free `rcond_1` is exactly 1 at both — it cannot see this, which is the whole reason
    the absolute limit exists.

    The specification's closed form puts the transition at `tau^(3/2) < eps`, i.e. 3.7e-11.
    Measured, it sits between 2.5e-11 and 3e-11: the exact continuous condition carries a
    factor of two, and the halving quantizes `x` to a power of two in any case. Both registered
    tolerances are orders away from the boundary, so nothing turns on it.
    """
    registered = reference["regularity_fixtures"]["x_squared"]["k03_newton_from_1_tol_1e-12"]
    x_final = float(registered["x_final"])
    assert x_final == 2.0**-20

    jacobian = sp.csc_matrix(np.array([[2.0 * x_final]]))
    evidence = screen(jacobian, tau_scaled_min=1e-12)

    assert evidence.rcond_1 == pytest.approx(1.0, rel=1e-12), (
        "the relative condition number is 1 here, exactly as at tau = 1e-8"
    )
    assert evidence.status == "ILL_CONDITIONED"
    assert evidence.ill_conditioned_reason == "absolute"
    assert evidence.inverse_one_norm_estimate == pytest.approx(2.0**19, rel=1e-9)
    assert evidence.inverse_one_norm_threshold == pytest.approx(
        absolute_conditioning_threshold(1, 1e-12), rel=1e-12
    )
    assert evidence.inverse_one_norm_estimate > evidence.inverse_one_norm_threshold

    # And the same matrix under the registered 1e-8 tolerance is clean.
    assert screen(jacobian, tau_scaled_min=1e-8).status == "NO_RANK_LOSS_DETECTED"


def test_k03s_newton_really_does_stop_where_the_specification_says() -> None:
    """A25's first clause, run rather than assumed: 14 halvings to `2^-14`, bit-exact.

    The specification derives this; it is cheap to confirm that K03's actual line search and
    convergence test land there, because the whole argument of §7.4 rests on a solver that
    stops at a point it is entitled to stop at.
    """
    from openflowsheet.numerics.newton import Evaluation, Problem, solve_newton
    from openflowsheet.numerics.scaling import Scaling
    from openflowsheet.orchestrator.trace import SolvePolicy, Trace

    def residual(x: np.ndarray) -> Evaluation:
        return Evaluation(status="ok", values=(float(x[0]) ** 2,))

    problem = Problem(
        variable_ids=("x",),
        row_ids=("r",),
        residual=residual,
        jacobian=lambda x: sp.csc_matrix(np.array([[2.0 * float(x[0])]])),
        scaling=Scaling(column={"x": 1.0}, row={"r": 1.0}),
        row_tolerance={"r": 1e-8},
    )
    result = solve_newton(
        problem,
        [1.0],
        SolvePolicy(policy_id="x-squared", residual_tolerances={}, scales={}),
        trace=Trace(),
    )
    assert result.outcome == "CONVERGED"
    assert result.iterations == 14
    assert float(result.x[0]) == 2.0**-14


def test_the_trivial_root_passes_the_screen_which_is_why_it_is_registered(
    variants: dict[str, Mapping[str, Any]], reference: Mapping[str, Any]
) -> None:
    """§7.6: the spurious state is a regularity fixture *because the screen is clean there*.

    Rank evidence does not detect a wrong branch. Registering the trivial root here, with its
    passing status, is what stops a later session from treating the screen as a false-success
    detector and quietly dropping §4.7.
    """
    flowsheet = flowsheet_for(variants["SYN-001-once-through"])
    result, _ = solve_tear(flowsheet)
    state = dict(result.final_state or {})
    for component in ("A", "B", "C"):
        state[f"S3.liq.{component}"] = state[f"S3.n.{component}"]
        state[f"S3.vap.{component}"] = 0.0
    state["S3.L"] = sum(state[f"S3.n.{c}"] for c in ("A", "B", "C"))
    state["S3.V"] = 0.0
    state["U-HEAT.Q"] -= 8237.8503930694530451
    state["U-FLASH.Q"] += 8237.8503930694530451

    tear = Syn001TearProblem(flowsheet)
    matrix, residual, _ = target_jacobian(tear, state)
    evidence = screen(matrix)
    expected = reference["floors_measured_2026_09_22"]["rcond_1_target_47x47_scaled"][
        "trivial_root_spurious"
    ]

    assert evidence.status == "NO_RANK_LOSS_DETECTED"
    assert evidence.rcond_1 == pytest.approx(float(expected), rel=1e-3)
    bound = solution_error_bound(matrix, residual)
    assert bound is not None and bound <= 1e-11, (
        "and the bound is small too: the spurious state is a genuine root of the assembled "
        "system, which is exactly why only a check outside that system finds it"
    )


def test_a_converged_solve_always_has_a_candidate_root_to_certify(
    variants: dict[str, Mapping[str, Any]],
) -> None:
    """A01's precondition, and a K03 defect that building the verifier found.

    `once-through` has r = 0, so `G(0)` is already the answer and K03's Newton converges at
    iteration 0 having accepted no step. The checkpoint was guarded on `accepted_any`, so two
    of the five registered variants produced none — and a verifier would have had to report
    them `final_state_absent`, meaning two registered solutions could never be certified.
    """
    for case_id in CASE_IDS:
        result, _ = solve_tear(flowsheet_for(variants[case_id]))
        assert result.outcome == "CONVERGED"
        assert result.checkpoint is not None, case_id
        assert result.checkpoint.label == "candidate_root", case_id
        assert result.checkpoint.full_state_sha256 is not None, case_id
    zero_iteration = [
        case_id
        for case_id in CASE_IDS
        if solve_tear(flowsheet_for(variants[case_id]))[0].iterations == 0
    ]
    assert zero_iteration, "the case that exposed it must stay in the registered set"


def test_a_structurally_singular_matrix_never_reaches_superlu(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ADR 0004 D3.3 as amended (T04 review S5), at the screen's and the bound's `splu` (found at
    T05 A28, where SciPy 1.15.3's SuperLU segfaulted on the dormant PH flash's 18 x 18 target of
    structural rank 15). A matrix with an empty row is singular for every value its pattern can
    hold: the screen escalates to the SVD and the bound is `None`, as SuperLU's own "exactly
    singular" gave, and SuperLU is never called. A structurally nonsingular matrix is."""
    # `numerics.linear.factorize` is the one guarded `splu` call (ADR 0004 D3.3 as amended
    # 2026-09-25); the screen and the bound reach SuperLU only through it.
    from openflowsheet.numerics import linear

    calls: list[tuple[int, int]] = []
    real = linear.splu

    def spy(matrix: sp.csc_matrix, **options: Any) -> Any:
        calls.append(matrix.shape)
        return real(matrix, **options)

    monkeypatch.setattr(linear, "splu", spy)
    singular = sp.csc_matrix(np.array([[1.0, 2.0, 0.0], [0.0, 0.0, 0.0], [0.0, 3.0, 4.0]]))
    evidence = screen(singular, scaled_residual=np.zeros(3))
    assert evidence.status == "RANK_DEFICIENT"
    assert evidence.as_document()["escalation"]["rank"] == 2
    assert evidence.inverse_one_norm_estimate == float("inf")
    assert solution_error_bound(singular, np.zeros(3)) is None
    assert calls == []

    regular = sp.csc_matrix(np.array([[1.0, 2.0, 0.0], [0.0, 5.0, 0.0], [0.0, 3.0, 4.0]]))
    assert screen(regular, scaled_residual=np.zeros(3)).status == "NO_RANK_LOSS_DETECTED"
    assert solution_error_bound(regular, np.ones(3)) is not None
    assert calls == [(3, 3), (3, 3)]
