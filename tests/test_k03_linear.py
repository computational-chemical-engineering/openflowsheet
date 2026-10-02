"""K03 M2: the one linear solve and its evidence (ADR 0004, specification §6, assertion A25).

ADR 0004 exists because an implicit option is not a declared one: `relax` and `panel_size` left
to SciPy's defaults give a different last bit, so a replay "within the declared numerical policy"
would not be reproducible. These tests hold the configuration to the ADR *and* hold the ADR to
the code, because a decision recorded in prose that the code has drifted from is worse than no
decision at all.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np
import pytest
import scipy.sparse as sp
from conftest import REPO_ROOT

from openflowsheet.numerics import linear
from openflowsheet.numerics.linear import (
    RESIDUAL_THRESHOLD,
    SUPERLU_OPTIONS,
    SUSPECT_PIVOT_RATIO,
    LinearSolveFailedError,
    normalized_residual,
    solve_linear,
)

ADR = REPO_ROOT / "docs" / "adr" / "0004-superlu-options.md"


# ------------------------------------------------------------------ the configuration itself


def test_the_options_are_adr_0004_d1_verbatim() -> None:
    """Written out here, so the code and the ADR are two transcriptions and not one."""
    assert SUPERLU_OPTIONS == {
        "permc_spec": "COLAMD",
        "diag_pivot_thresh": 1.0,
        "relax": 1,
        "panel_size": 10,
        "options": {"Equil": False, "IterRefine": "NOREFINE", "SymmetricMode": False},
    }
    assert RESIDUAL_THRESHOLD == 1e-12
    assert SUSPECT_PIVOT_RATIO == 1e-10


def test_the_adr_text_still_says_what_the_code_does() -> None:
    """Drift between a recorded decision and the code is the failure the register exists for."""
    text = ADR.read_text(encoding="utf-8")
    for fragment in (
        'permc_spec="COLAMD"',
        "diag_pivot_thresh=1.0",
        "relax=1",
        "panel_size=10",
        '"Equil": False',
        '"IterRefine": "NOREFINE"',
        '"SymmetricMode": False',
    ):
        assert fragment in text, fragment
    assert "1e-12" in text
    assert "1e-10" in text


def test_scipy_still_rejects_the_spelling_the_adr_says_it_rejects() -> None:
    """`IterRefine="NO"` is refused and `"NOREFINE"` accepted — ADR 0004 D1.1's measured claim.

    Pinned because it is the kind of thing a SciPy upgrade changes silently, and because the ADR
    states it as measured rather than as documentation.
    """
    from scipy.sparse.linalg import splu

    matrix = sp.eye(4, format="csc") * 2.0
    with pytest.raises(ValueError, match="IterRefine"):
        splu(matrix, options={"IterRefine": "NO"})
    splu(matrix, options={"IterRefine": "NOREFINE"})


def test_equil_is_inert_on_this_path_as_the_adr_records() -> None:
    """ADR 0004 D1.3, measured: `splu` performs no equilibration, so the flag changes nothing.

    Worth pinning rather than trusting: the ADR uses it to justify that the registered scales
    are the only scaling in play, and a SciPy change would quietly falsify that.
    """
    from scipy.sparse.linalg import splu

    rng = np.random.default_rng(11)
    matrix = sp.csc_matrix(
        sp.random(30, 30, density=0.2, format="csc", random_state=5) + sp.eye(30) * 4.0
    )
    base = {k: v for k, v in SUPERLU_OPTIONS.items() if k != "options"}
    off = splu(matrix, **base, options={**SUPERLU_OPTIONS["options"], "Equil": False})
    on = splu(matrix, **base, options={**SUPERLU_OPTIONS["options"], "Equil": True})
    assert np.array_equal(off.L.toarray(), on.L.toarray())
    assert np.array_equal(off.U.toarray(), on.U.toarray())
    b = rng.normal(size=30)
    assert np.array_equal(off.solve(b), on.solve(b))


# -------------------------------------------------------------------------- the solve itself


def test_a_known_system_is_solved_and_fully_recorded() -> None:
    """A25: every field ADR 0004 D3.1 requires, on a system whose answer is written out."""
    matrix = sp.csc_matrix(np.array([[2.0, 1.0, 0.0], [0.0, 3.0, 0.0], [0.0, 0.0, 4.0]]))
    solution, record = solve_linear(matrix, [4.0, 6.0, 8.0])
    assert list(solution) == [1.0, 2.0, 2.0]

    assert record.residual_normalized <= RESIDUAL_THRESHOLD
    assert record.dimension == 3
    assert record.min_abs_u_diagonal > 0.0
    assert record.max_abs_u_diagonal >= record.min_abs_u_diagonal
    assert record.nnz_l > 0 and record.nnz_u > 0
    assert record.options == SUPERLU_OPTIONS
    assert record.linear_suspect is False


def test_a_dense_three_by_three_goes_through_the_same_path() -> None:
    """ADR 0004 D2: one path. A small system is not quietly solved another way."""
    dense = np.array([[2.0, 0.0, 0.0], [0.0, 5.0, 0.0], [0.0, 0.0, 10.0]])
    solution, record = solve_linear(dense, [2.0, 10.0, 30.0])
    assert list(solution) == [1.0, 2.0, 3.0]
    assert record.dimension == 3
    assert record.options == SUPERLU_OPTIONS


def test_an_exactly_singular_matrix_is_a_typed_failure() -> None:
    """ADR 0004 D3.3, with its registered state: NUM-02 at r = 1, where dR/dt is identically 0.

    Nothing is regularized and nothing is re-solved by least squares.
    """
    identically_zero = sp.csc_matrix((3, 3))
    with pytest.raises(LinearSolveFailedError) as raised:
        solve_linear(identically_zero, [1.0, 1.0, 1.0])
    assert raised.value.reason == "exactly_singular"

    # The NUM-02 tear Jacobian at r = 1 is `r I - I = 0`, which is that matrix.
    num02 = sp.csc_matrix(np.eye(3) * 1.0 - np.eye(3))
    with pytest.raises(LinearSolveFailedError) as raised_num02:
        solve_linear(num02, [1.0, 1.0, 1.0])
    assert raised_num02.value.reason == "exactly_singular"


def test_a_tiny_pivot_is_flagged_and_changes_nothing() -> None:
    """ADR 0004 D3.4: `linear_suspect` is a screen, not a rank statement, and not an outcome."""
    matrix = sp.csc_matrix(np.diag([1.0, 1.0, 1e-14]))
    solution, record = solve_linear(matrix, [1.0, 1.0, 1e-14])
    assert record.linear_suspect is True
    assert record.min_abs_u_diagonal / record.max_abs_u_diagonal < SUSPECT_PIVOT_RATIO
    assert list(solution) == [1.0, 1.0, 1.0], "the solve still succeeded and still answered"


def test_the_residual_threshold_branch_is_reachable_and_typed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The failure ADR 0004 D3.2 registers.

    A well-formed matrix cannot reach it — LU with partial pivoting is backward stable, so the
    measured residual is around 1e-16 against a 1e-12 bound, which is the point of the bound.
    The branch is therefore exercised by lowering the threshold below the achievable residual,
    which tests the guard rather than pretending to test the arithmetic.
    """
    rng = np.random.default_rng(3)
    matrix = sp.csc_matrix(
        sp.random(40, 40, density=0.15, format="csc", random_state=9) + sp.eye(40) * 3.0
    )
    b = rng.normal(size=40)
    _, record = solve_linear(matrix, b)
    assert 0.0 < record.residual_normalized < 1e-12

    monkeypatch.setattr(linear, "RESIDUAL_THRESHOLD", record.residual_normalized / 2.0)
    with pytest.raises(LinearSolveFailedError) as raised:
        solve_linear(matrix, b)
    assert raised.value.reason == "residual"
    assert "not a factorization of this matrix" in str(raised.value)


def test_the_normalized_residual_is_the_adrs_formula() -> None:
    """`‖A x − b‖∞ / (‖A‖max ‖x‖∞ + ‖b‖∞)`, computed by hand."""
    matrix = sp.csc_matrix(np.array([[2.0, 0.0], [0.0, 4.0]]))
    x = np.array([1.0, 1.0])
    b = np.array([2.0, 4.0])
    assert normalized_residual(matrix, x, b) == 0.0
    # Ax - b = (0, 1); ‖A‖max = 4, ‖x‖∞ = 1, ‖b‖∞ = 3  ->  1 / (4 + 3)
    assert normalized_residual(matrix, x, np.array([2.0, 3.0])) == pytest.approx(1.0 / 7.0)
    # A zero system is zero, not undefined.
    assert normalized_residual(sp.csc_matrix((2, 2)), np.zeros(2), np.zeros(2)) == 0.0


def test_a_mismatched_right_hand_side_is_refused() -> None:
    with pytest.raises(ValueError, match="does not match"):
        solve_linear(sp.eye(3, format="csc"), [1.0, 2.0])
    with pytest.raises(ValueError, match="square"):
        solve_linear(sp.csc_matrix(np.ones((2, 3))), [1.0, 2.0])


# ------------------------------------------------------ on the real assembled SYN-001 Jacobian


def test_the_scaled_syn001_jacobian_solves_well_inside_the_threshold(
    reference_values: Mapping[str, Any],
) -> None:
    """ADR 0004 D3.2's floor argument, re-measured here rather than quoted.

    The scaled square system at the reference state: the recorded residual must sit orders of
    magnitude below 1e-12, and the `|U_ii|` screen must not fire on a registered case — the ADR
    says the ratio is at least 7.1e-3 at every registered state.
    """
    import sys

    sys.path.insert(0, "tests")
    import test_k02_flowsheet as reference_module

    from openflowsheet.compile.casadi_backend import compile_problem
    from openflowsheet.compile.reference import state_vector
    from openflowsheet.compiled import EvaluationContext
    from openflowsheet.numerics.scaling import Scaling

    cases = {entry["case_id"]: entry for entry in reference_values["variants"]}
    for case_id in (
        "SYN-001-nominal",
        "SYN-001-once-through",
        "SYN-001-high-recycle",
        "SYN-001-all-liquid-310K",
        "SYN-001-all-vapor-420K",
    ):
        case = cases[case_id]
        spec = reference_module.flowsheet_for(case).spec()
        state = reference_module.reference_state(case, spec)
        scaling = Scaling.from_spec(spec)
        problem = compile_problem(spec)
        metadata = problem.metadata
        context = EvaluationContext(
            model_version=metadata.model_version, constants_sha256=metadata.constants_sha256
        )
        jacobian = problem.jacobian(np.array(state_vector(spec, state)), context)
        assert jacobian.status == "ok"

        rows, columns, data = [], [], []
        for column in range(len(jacobian.col_ids)):
            for offset in range(jacobian.indptr[column], jacobian.indptr[column + 1]):
                rows.append(jacobian.indices[offset])
                columns.append(column)
                data.append(jacobian.data[offset])
        scaled = scaling.scale_jacobian_entries(
            data, rows, columns, jacobian.row_ids, jacobian.col_ids
        )
        full = sp.csr_matrix(
            (scaled, (rows, columns)), shape=(len(jacobian.row_ids), len(jacobian.col_ids))
        )
        # Specification §7.2: the inner block is 44 x 44. From the assembled 49 x 47, drop the
        # two consistent-redundant pressure rows the rank policy eliminates, the three
        # SPLIT-recycle rows that *define* the tear, and the three tear columns themselves.
        drop_rows = {
            jacobian.row_ids.index(name)
            for name in (
                "U-FLASH:FLASH-P:inlet",
                "U-SPLIT:SPLIT-P:recycle",
                "U-SPLIT:SPLIT-recycle:A",
                "U-SPLIT:SPLIT-recycle:B",
                "U-SPLIT:SPLIT-recycle:C",
            )
        }
        drop_columns = {jacobian.col_ids.index(name) for name in ("S6.n.A", "S6.n.B", "S6.n.C")}
        keep_rows = [i for i in range(len(jacobian.row_ids)) if i not in drop_rows]
        keep_columns = [i for i in range(len(jacobian.col_ids)) if i not in drop_columns]
        inner = sp.csc_matrix(full.toarray()[np.ix_(keep_rows, keep_columns)])
        assert inner.shape == (44, 44)

        rng = np.random.default_rng(4)
        solution, record = solve_linear(inner, rng.normal(size=44))
        assert record.residual_normalized < 1e-13, (case_id, record.residual_normalized)
        ratio = record.min_abs_u_diagonal / record.max_abs_u_diagonal
        assert ratio >= 7.1e-3, (case_id, ratio)
        assert record.linear_suspect is False
        assert np.all(np.isfinite(solution))
        if case_id == "SYN-001-nominal":
            # ADR 0004 D1.2 quotes these for COLAMD on this block; reproduced, not trusted.
            assert (record.nnz_l, record.nnz_u) == (111, 160)


# ------------------------------------------- one factorization for several columns (review M5)


def test_several_columns_are_one_factorization_and_the_same_answer() -> None:
    """ADR 0004 Consequences and spec §3.4: "three solves against one factorization".

    The Schur complement needs `Ĵ_φu⁻¹ Ĵ_φt`, three columns against one 44 x 44 matrix. Solving
    column by column factorized it three times and discarded two thirds of the evidence. The
    multi-column form must give **bit-identical** answers, or it is a different computation
    wearing the same name.
    """
    rng = np.random.default_rng(11)
    matrix = sp.csc_matrix(np.eye(9) * 3.0 + rng.normal(scale=0.1, size=(9, 9)))
    columns = rng.normal(size=(9, 3))

    factorizations = []
    original = linear.splu

    def counting(*args: Any, **kwargs: Any) -> Any:
        factorizations.append(1)
        return original(*args, **kwargs)

    linear.splu = counting
    try:
        per_column = np.column_stack([solve_linear(matrix, columns[:, k])[0] for k in range(3)])
        assert len(factorizations) == 3
        factorizations.clear()
        together, record = solve_linear(matrix, columns)
        assert len(factorizations) == 1, "several columns, one factorization"
    finally:
        linear.splu = original

    assert together.shape == (9, 3)
    assert [value.hex() for value in together.ravel()] == [
        value.hex() for value in per_column.ravel()
    ], "the multi-column solve must be bit-identical to the per-column one"
    assert record.dimension == 9


def test_the_recorded_residual_of_a_multi_column_solve_is_the_worst_column() -> None:
    """A record that averaged, or took the first column, could not be better than the weakest."""
    rng = np.random.default_rng(12)
    matrix = sp.csc_matrix(np.eye(6) * 2.0 + rng.normal(scale=0.05, size=(6, 6)))
    columns = rng.normal(size=(6, 4))
    together, record = solve_linear(matrix, columns)
    per_column = [solve_linear(matrix, columns[:, k])[1].residual_normalized for k in range(4)]
    assert record.residual_normalized == max(per_column)


def test_a_right_hand_side_of_the_wrong_height_is_still_refused() -> None:
    matrix = sp.csc_matrix(np.eye(4))
    with pytest.raises(ValueError, match="does not match"):
        solve_linear(matrix, np.zeros((5, 2)))
    with pytest.raises(ValueError, match="does not match"):
        solve_linear(matrix, np.zeros((4, 2, 2)))
