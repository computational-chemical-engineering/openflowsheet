"""M03 WO-1: `KeptFactorization.solve_transposed` (spec §3.6; ADR 0031 D4, ADR 0004 D3).

The adjoint sensitivity `Ĵᵀ Λ̂ = −Ĉᵀ` is a back-solve on the forward solve's factorization, so the
count of factorizations cannot grow with the number of outputs. What has to be shown is that it
solves the *transposed* system (a missing transpose is the O(1) error spec §5's linear toy exists
to catch), that it is judged against `Aᵀ` and not against `A`, and that it costs no factorization.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pytest
import scipy.sparse as sp

from openflowsheet.numerics import linear
from openflowsheet.numerics.linear import (
    KeptFactorization,
    LinearSolveFailedError,
    factorize,
    normalized_residual,
    solve_linear_kept,
)


def nonsymmetric(seed: int, size: int = 7) -> sp.csc_matrix:
    rng = np.random.default_rng(seed)
    dense = np.eye(size) * 3.0 + rng.normal(scale=0.4, size=(size, size))
    dense[0, size - 1] = 5.0  # far from symmetric, so A and Aᵀ give different answers
    return sp.csc_matrix(dense)


def test_the_transposed_solve_solves_the_transpose() -> None:
    matrix = nonsymmetric(31)
    rng = np.random.default_rng(32)
    rhs = rng.normal(size=7)
    _, _, kept = solve_linear_kept(matrix, rhs)
    solution, record = kept.solve_transposed(rhs)

    expected = np.linalg.solve(matrix.toarray().T, rhs)
    assert np.max(np.abs(solution - expected)) <= 1e-13 * np.max(np.abs(expected))
    # Not the untransposed answer: on this matrix the two differ at O(1).
    untransposed = np.linalg.solve(matrix.toarray(), rhs)
    assert np.max(np.abs(solution - untransposed)) > 1e-2
    # The record is ADR 0004 D3's, judged against the matrix actually solved.
    assert record.residual_normalized == normalized_residual(sp.csc_matrix(matrix.T), solution, rhs)
    assert record.residual_normalized <= 1e-15
    assert record.dimension == 7


def test_several_transposed_columns_are_the_per_column_answers_bit_for_bit() -> None:
    matrix = nonsymmetric(33)
    columns = np.random.default_rng(34).normal(size=(7, 3))
    _, _, kept = solve_linear_kept(matrix, columns[:, 0])
    together, record = kept.solve_transposed(columns)
    per_column = [kept.solve_transposed(columns[:, k]) for k in range(3)]
    assert [value.hex() for value in together.ravel()] == [
        value.hex() for value in np.column_stack([s for s, _ in per_column]).ravel()
    ]
    assert record.residual_normalized == max(r.residual_normalized for _, r in per_column)


def test_the_transposed_solve_costs_no_factorization() -> None:
    matrix = nonsymmetric(35)
    factorizations: list[int] = []
    original = linear.splu

    def counting(*args: Any, **kwargs: Any) -> Any:
        factorizations.append(1)
        return original(*args, **kwargs)

    linear.splu = counting
    try:
        _, _, kept = solve_linear_kept(matrix, np.ones(7))
        kept.solve(np.ones(7))
        kept.solve_transposed(np.ones((7, 4)))
    finally:
        linear.splu = original
    assert len(factorizations) == 1


def test_the_transposed_solve_is_judged_and_refused_like_a_forward_one() -> None:
    """A factorization of another matrix fails ADR 0004 D3.2's threshold against this one's `Aᵀ`."""
    matrix = nonsymmetric(36)
    other = nonsymmetric(37)
    kept = KeptFactorization(matrix, factorize(other))
    with pytest.raises(LinearSolveFailedError, match="transposed system") as failed:
        kept.solve_transposed(np.ones(7))
    assert failed.value.reason == "residual"


def test_a_transposed_right_hand_side_of_the_wrong_height_is_refused() -> None:
    _, _, kept = solve_linear_kept(nonsymmetric(38), np.ones(7))
    with pytest.raises(ValueError, match="does not match"):
        kept.solve_transposed(np.ones(6))
    with pytest.raises(ValueError, match="does not match"):
        kept.solve_transposed(np.ones((7, 2, 2)))


def test_the_forward_back_solve_is_unchanged_by_the_transposed_path() -> None:
    """`solve` after `solve_transposed` returns what `solve_linear_kept` returned, bit for bit."""
    matrix = nonsymmetric(39)
    rhs = np.random.default_rng(40).normal(size=7)
    first, first_record, kept = solve_linear_kept(matrix, rhs)
    kept.solve_transposed(rhs)
    again, again_record = kept.solve(rhs)
    assert [v.hex() for v in again] == [v.hex() for v in first]
    assert again_record == first_record
