"""T06 W3: the regularity estimate is deterministic (spec §8.1; ADR 0014 D4; register R-069).

scipy's `onenormest` draws its starting columns from numpy's legacy global generator, so before
W3 `rcond₁` and `b` depended on the caller's random state (measured, M5: C2's `b` took two values
over 20 seeds, C3's three) and the call consumed the caller's draws. Both call sites now run it
with the global state saved, seeded with `20260925` and restored. Assertions T6-A37 and, on the
seed-varying registered certificates, A38; A38 over every certificate the suite issues is the
inertness measurement of the W3 commit, recorded in its message.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import cache
from typing import Any

import numpy as np
import pytest
import scipy.sparse as sp
import yaml
from scipy.sparse.linalg import LinearOperator, onenormest
from t05b_support import POLICY_V2
from test_t05_coupled import CASE_DIR
from test_t05b_contract import Solved, solve

from openflowsheet.canonical import canonical_json
from openflowsheet.compile.casadi_backend import compile_problem
from openflowsheet.numerics.linear import factorize
from openflowsheet.verify.certificate import BoundDeclaration, verify_revision
from openflowsheet.verify.regularity import (
    ONENORMEST_SEED,
    screen,
    solution_error_bound,
    target_jacobian,
)

#: M5 (`docs/t06-measurements-m45.md`): `rcond₁` and `b` of the two seed-varying registered
#: certificates over numpy global seeds 0…19, as printed there (seven digits).
M5_SPREAD = {
    "SYN-001-UL-C2": {"rcond_1": (5.449931e-3, 7.028362e-3), "b": (3.008824e-15, 3.880252e-15)},
    "SYN-001-UL-C3": {"rcond_1": (1.224535e-2, 1.390923e-2), "b": (2.990123e-9, 3.396415e-9)},
}
#: The printed digits' half unit in the last place, relative.
PRINTED = 1e-6
C2 = "SYN-001-UL-C2"


@cache
def solved(case: str) -> Solved:
    document = yaml.safe_load((CASE_DIR / f"{case}.yaml").read_text())
    return solve(document, POLICY_V2)


@cache
def case_matrix(case: str) -> tuple[sp.csc_matrix, np.ndarray]:
    """A case's screened matrix and scaled residual at its certified state."""
    run = solved(case)
    state = run.region.state
    target = BoundDeclaration(run.binding.spec, compile_problem(run.binding.spec), state)
    matrix, scaled_residual, _ = target_jacobian(target, state)
    return matrix, scaled_residual


def raw_estimate(matrix: sp.csc_matrix, seed: int) -> float:
    """`onenormest` of the inverse as `regularity` builds it, under `np.random.seed(seed)`."""
    factorization = factorize(sp.csc_matrix(matrix))
    operator = LinearOperator(
        matrix.shape,
        matvec=lambda b: factorization.solve(b),
        rmatvec=lambda b: factorization.solve(b, trans="T"),
        dtype=np.float64,
    )
    np.random.seed(seed)
    return float(onenormest(operator))


def same_state(first: Any, second: Any) -> bool:
    name, keys, position, gauss, cached = first
    return (
        name == second[0]
        and np.array_equal(keys, second[1])
        and position == second[2]
        and gauss == second[3]
        and cached == second[4]
    )


@cache
def disagreeing_seeds(case: str) -> tuple[int, int]:
    """Two global seeds under which the raw estimate of the case's inverse differs (M5: C2 two
    values over seeds 0…19, C3 three), so agreement is the guard's doing, not the matrix's."""
    matrix, _ = case_matrix(case)
    estimates = {seed: raw_estimate(matrix, seed) for seed in range(20)}
    first = min(estimates)
    second = next(seed for seed in estimates if estimates[seed] != estimates[first])
    return first, second


def test_a37_two_screens_with_random_use_between_them_agree_bit_for_bit() -> None:
    matrix, scaled_residual = case_matrix(C2)
    first_seed, second_seed = disagreeing_seeds(C2)
    np.random.seed(first_seed)
    first = screen(matrix, scaled_residual=scaled_residual)
    np.random.seed(second_seed)
    second = screen(matrix, scaled_residual=scaled_residual)
    np.random.rand(17)
    third = screen(matrix, scaled_residual=scaled_residual)
    assert first == second == third
    assert first.status == second.status == "NO_RANK_LOSS_DETECTED"
    for field in ("inverse_one_norm_estimate", "rcond_1", "solution_error_bound_scaled"):
        assert getattr(first, field) == getattr(second, field), field
    assert first.inverse_one_norm_estimate == raw_estimate(matrix, ONENORMEST_SEED)
    assert ONENORMEST_SEED == 20260925


@pytest.mark.parametrize(
    "estimate",
    [
        lambda m, r: screen(m, scaled_residual=r),
        lambda m, r: solution_error_bound(m, r),
    ],
    ids=["screen", "solution_error_bound"],
)
def test_a37_the_callers_random_state_is_unchanged(
    estimate: Callable[[sp.csc_matrix, np.ndarray], Any],
) -> None:
    matrix, scaled_residual = case_matrix(C2)
    np.random.seed(5)
    np.random.rand(3)
    before = np.random.get_state()
    estimate(matrix, scaled_residual)
    assert same_state(before, np.random.get_state())


def test_a37_the_bound_is_the_same_estimate_times_the_residual() -> None:
    matrix, scaled_residual = case_matrix(C2)
    np.random.seed(11)
    bound = solution_error_bound(matrix, scaled_residual)
    np.random.seed(12)
    evidence = screen(matrix, scaled_residual=scaled_residual)
    assert bound == evidence.solution_error_bound_scaled


@pytest.mark.parametrize("case", sorted(M5_SPREAD))
def test_a37_a38_a_certificate_is_a_function_of_its_solve_alone(case: str) -> None:
    """End to end: the certificate document is byte-identical under different global states,
    and its `rcond₁` and `b` lie inside M5's 20-seed spread with the verdict and status as
    registered (`VERIFIED`, `NO_RANK_LOSS_DETECTED`)."""
    run = solved(case)
    documents = []
    for seed in (*disagreeing_seeds(case), ONENORMEST_SEED):
        np.random.seed(seed)
        certificate = verify_revision(
            run.binding, run.document, run.run, solve_plan=run.plan.steps[-1].solve_plan
        )
        documents.append(canonical_json(certificate.as_document()))
    assert documents[0] == documents[1] == documents[2]
    assert certificate.verification_status == "VERIFIED"
    assert certificate.regularity is not None
    assert certificate.regularity.status == "NO_RANK_LOSS_DETECTED"
    values = {
        "rcond_1": certificate.regularity.rcond_1,
        "b": certificate.solution_error_bound_scaled,
    }
    for name, (low, high) in M5_SPREAD[case].items():
        value = values[name]
        assert value is not None
        assert low * (1 - PRINTED) <= value <= high * (1 + PRINTED), (name, value, low, high)
