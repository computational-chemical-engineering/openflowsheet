"""K01: the compiler's obligations from ADR 0003 D5 and ADR 0008 D4, on a closed-form problem.

The fixture is deliberately tiny and analytic — `y0 = a²`, `y1 = b³` behind an opaque block, two
rows whose derivatives can be written down — so that every assertion compares against a number
derived by hand rather than against the compiler's own output. SYN-001 conformance is a separate
and larger fixture; this module tests the *machinery*, and it tests it where a wrong answer is
obvious.

The properties checked here are the ones whose failure is silent. A permuted Jacobian, a structural
zero quietly filled in, a finite-difference fallback, a fabricated Hessian and a pinned input that
does not reach the identity hash all produce a plausible result rather than an error, which is why
each has a test that would notice rather than a comment saying it was considered.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from pathlib import Path

import numpy as np
import pytest

from openflowsheet.compile.casadi_backend import compile_problem
from openflowsheet.compile.spec import DomainError, EquationSpec, ProblemSpec
from openflowsheet.compiled import CompiledProblem, EvaluationContext

ADR_BACKEND = "docs/adr/0003-compiled-problem-backend.md"
ADR_TRANSIENT = "docs/adr/0008-transient-extension-readiness.md"


class SquareCube:
    """`y0 = u0**2`, `y1 = u1**3`. The off-diagonal derivatives are structurally zero."""

    block_id = "sq"
    input_ids = ("u0", "u1")
    output_ids = ("y0", "y1")

    def jacobian_pattern(self) -> tuple[tuple[int, int], ...]:
        return ((0, 0), (1, 1))

    def values(self, inputs: Sequence[float]) -> Sequence[float]:
        if inputs[0] < 0.0:
            raise DomainError(f"u0 = {inputs[0]} is outside the block's stated domain u0 >= 0")
        return [inputs[0] ** 2, inputs[1] ** 3]

    def jacobian(self, inputs: Sequence[float]) -> Sequence[tuple[int, int, float]]:
        if inputs[0] < 0.0:
            raise DomainError(f"u0 = {inputs[0]} is outside the block's stated domain u0 >= 0")
        return [(0, 0, 2.0 * inputs[0]), (1, 1, 3.0 * inputs[1] ** 2)]


class OverDeclaring(SquareCube):
    """Declares a nonzero that is structurally zero: the pattern is a lie in the safe direction.

    It still *supplies* the entry, explicitly as 0.0, because a declared entry that is simply not
    returned is a different defect — see `Omitting` below.
    """

    def jacobian_pattern(self) -> tuple[tuple[int, int], ...]:
        return ((0, 0), (0, 1), (1, 1))

    def jacobian(self, inputs: Sequence[float]) -> Sequence[tuple[int, int, float]]:
        return [(0, 0, 2.0 * inputs[0]), (0, 1, 0.0), (1, 1, 3.0 * inputs[1] ** 2)]


class Omitting(SquareCube):
    """Declares (1, 1) but never returns it: the value would become a silent stored zero."""

    def jacobian(self, inputs: Sequence[float]) -> Sequence[tuple[int, int, float]]:
        return [(0, 0, 2.0 * inputs[0])]


class Repeating(SquareCube):
    """Returns (0, 0) twice. Letting the last win hides which the block meant."""

    def jacobian(self, inputs: Sequence[float]) -> Sequence[tuple[int, int, float]]:
        return [(0, 0, 2.0 * inputs[0]), (0, 0, 99.0), (1, 1, 3.0 * inputs[1] ** 2)]


class UnderDeclaring(SquareCube):
    """Returns a value at a coordinate it never declared: a lie in the dangerous direction."""

    def jacobian(self, inputs: Sequence[float]) -> Sequence[tuple[int, int, float]]:
        return [(0, 0, 2.0 * inputs[0]), (0, 1, 1.0), (1, 1, 3.0 * inputs[1] ** 2)]


def build_spec(k: float = 5.0, block: object | None = None) -> ProblemSpec:
    """`r0 = a + a² − k`, `r1 = exp(b) − b³`, with the squares and cubes hidden in a block."""
    return ProblemSpec(
        label="k01-fixture-1",
        variable_ids=("a", "b"),
        equations=(
            EquationSpec(
                "r0",
                lambda v, o, p, alg: v["a"] + o["sq.y0"] - p["k"],
                "algebraic",
                origin="fixture",
            ),
            EquationSpec("r1", lambda v, o, p, alg: alg.exp(v["b"]) - o["sq.y1"], "algebraic"),
        ),
        parameter_ids=("k",),
        parameters={"k": k},
        blocks=(block or SquareCube(),),  # type: ignore[arg-type]
        block_inputs={"sq": ("a", "b")},
    )


@pytest.fixture
def problem() -> object:
    return compile_problem(build_spec())


@pytest.fixture
def context(problem: object) -> EvaluationContext:
    metadata = problem.metadata  # type: ignore[attr-defined]
    return EvaluationContext(
        model_version=metadata.model_version, constants_sha256=metadata.constants_sha256
    )


X = np.array([2.0, 0.5])
#: Written out by hand: dr0/da = 1 + 2a, dr0/db = 0, dr1/da = 0, dr1/db = exp(b) - 3b².
EXPECTED_NONZEROS = {("r0", "a"): 5.0, ("r1", "b"): math.exp(0.5) - 0.75}


def csc_as_mapping(result: object) -> dict[tuple[str, str], float]:
    """Read a CSC result back into `{(row_id, col_id): value}` — by name, never by position."""
    out: dict[tuple[str, str], float] = {}
    for column, col_id in enumerate(result.col_ids):  # type: ignore[attr-defined]
        start, stop = result.indptr[column], result.indptr[column + 1]  # type: ignore[attr-defined]
        for offset in range(start, stop):
            row_id = result.row_ids[result.indices[offset]]  # type: ignore[attr-defined]
            out[(row_id, col_id)] = result.data[offset]  # type: ignore[attr-defined]
    return out


def test_the_compiled_object_satisfies_the_frozen_protocol(problem: object) -> None:
    assert isinstance(problem, CompiledProblem)


def test_the_residual_is_the_closed_form(problem: object, context: EvaluationContext) -> None:
    result = problem.residual(X, context)  # type: ignore[attr-defined]
    assert result.status == "ok"
    assert result.equation_ids == ("r0", "r1")
    assert result.values == pytest.approx((2.0 + 4.0 - 5.0, math.exp(0.5) - 0.125), rel=1e-15)


# -- D5.1 ordering pinned by name, not by position --------------------------------------------


def test_the_jacobian_is_the_closed_form_read_back_by_name(
    problem: object, context: EvaluationContext
) -> None:
    """ADR 0003 D5.1. Reading by `(row_id, col_id)` is what a consumer must be able to do."""
    result = problem.jacobian(X, context)  # type: ignore[attr-defined]
    assert result.status == "ok"
    assert csc_as_mapping(result) == pytest.approx(EXPECTED_NONZEROS, rel=1e-14)


def test_the_csc_arrays_are_column_major_with_ascending_rows(
    problem: object, context: EvaluationContext
) -> None:
    """The canonical ordering. A backend emitting triplets another way must not leak through."""
    result = problem.jacobian(X, context)  # type: ignore[attr-defined]
    assert result.indptr[0] == 0
    assert result.indptr[-1] == len(result.data) == result.nnz
    assert list(result.indptr) == sorted(result.indptr)
    for column in range(len(result.col_ids)):
        rows = result.indices[result.indptr[column] : result.indptr[column + 1]]
        assert list(rows) == sorted(rows), f"column {column} rows are not ascending"


def test_a_permuted_reading_of_the_same_arrays_is_detected(
    problem: object, context: EvaluationContext
) -> None:
    """Anti-vacuity for the two tests above.

    The permutation hazard is that values land under the wrong `(row_id, col_id)` while every
    array stays well-formed. This reverses the row identity and shows the by-name comparison
    notices — without it, "the Jacobian matched" could mean "we compared it to itself".
    """
    result = problem.jacobian(X, context)  # type: ignore[attr-defined]
    honest = csc_as_mapping(result)

    class Permuted:
        col_ids = result.col_ids
        row_ids = tuple(reversed(result.row_ids))
        indptr, indices, data = result.indptr, result.indices, result.data

    assert csc_as_mapping(Permuted()) != honest


# -- D5.2 declared sparsity is preserved, and a false declaration is caught --------------------


def test_the_blocks_structural_zeros_survive_into_the_assembled_system(
    problem: object, context: EvaluationContext
) -> None:
    """ADR 0003 D5.2. Without `has_jac_sparsity` this would be 4 stored entries, not 2.

    P02 measured the same failure at flowsheet scale as 66 entries instead of 60.
    """
    result = problem.jacobian(X, context)  # type: ignore[attr-defined]
    assert result.nnz == 2, f"expected the two diagonal entries, got {csc_as_mapping(result)}"
    assert result.pattern_provenance == "backend-declared"


def test_over_declared_sparsity_shows_up_as_a_stored_structural_zero(
    context: EvaluationContext,
) -> None:
    """A block claiming a nonzero it does not have costs storage and is visible in `nnz`.

    This is the *safe* direction of a wrong declaration — the answer stays right — but it is still
    a wrong claim about the function, and K01 must be able to see it rather than absorb it.
    """
    problem = compile_problem(build_spec(block=OverDeclaring()))
    result = problem.jacobian(X, context)
    assert result.nnz == 3
    assert csc_as_mapping(result)[("r0", "b")] == 0.0


def test_an_undeclared_nonzero_is_refused_rather_than_dropped(
    context: EvaluationContext,
) -> None:
    """The *dangerous* direction: a real derivative at a coordinate the block called structurally
    zero. Silently dropping it yields a wrong Jacobian that still looks well-formed, so it raises.
    """
    problem = compile_problem(build_spec(block=UnderDeclaring()))
    result = problem.jacobian(X, context)
    assert result.status == "error"
    assert "did not declare" in result.message


# -- D5.3 JVP and VJP are exact -----------------------------------------------------------------


@pytest.mark.parametrize(
    "seed", [np.array([1.0, 0.0]), np.array([0.0, 1.0]), np.array([1.0, -2.0])]
)
def test_jvp_is_exact_against_a_fourth_order_finite_difference(
    problem: object, context: EvaluationContext, seed: np.ndarray
) -> None:
    """ADR 0003 D5.3. The finite difference is the independent expectation, not the oracle."""
    step = 1e-5
    samples = [
        np.array(problem.residual(X + factor * step * seed, context).values)  # type: ignore[attr-defined]
        for factor in (-2.0, -1.0, 1.0, 2.0)
    ]
    reference = (samples[0] - 8.0 * samples[1] + 8.0 * samples[2] - samples[3]) / (12.0 * step)
    assert np.array(problem.jvp(X, seed, context)) == pytest.approx(reference, abs=1e-7)  # type: ignore[attr-defined]


def test_vjp_is_the_transpose_of_the_assembled_jacobian(
    problem: object, context: EvaluationContext
) -> None:
    dense = np.zeros((2, 2))
    for (row_id, col_id), value in csc_as_mapping(problem.jacobian(X, context)).items():  # type: ignore[attr-defined]
        dense[("r0", "r1").index(row_id), ("a", "b").index(col_id)] = value
    for adjoint in (np.array([1.0, 0.0]), np.array([0.0, 1.0]), np.array([2.0, -3.0])):
        assert np.array(problem.vjp(X, adjoint, context)) == pytest.approx(dense.T @ adjoint)  # type: ignore[attr-defined]


# -- D5.4 second order is absent, and absent is not zero ---------------------------------------


def test_the_hessian_is_reported_absent_and_raises_rather_than_returning_zeros(
    problem: object, context: EvaluationContext
) -> None:
    """ADR 0003 D5.4. Zeros would be indistinguishable from a true Hessian at a stationary point."""
    assert problem.metadata.capabilities.hessian == "absent"  # type: ignore[attr-defined]
    with pytest.raises(NotImplementedError, match="not zero"):
        problem.hessian(X, context)  # type: ignore[attr-defined]


# -- D5.5 callback accounting -------------------------------------------------------------------


def test_each_block_is_called_once_per_evaluation_not_n_inputs_plus_one(
    problem: object, context: EvaluationContext
) -> None:
    """ADR 0003 D5.5. `n_inputs + 1 = 3` value calls per Jacobian is the differencing signature."""
    residual = problem.residual(X, context)  # type: ignore[attr-defined]
    assert residual.counters["sq"] == {"value_calls": 1, "jacobian_calls": 0}

    jacobian = problem.jacobian(X, context)  # type: ignore[attr-defined]
    assert jacobian.counters["sq"]["jacobian_calls"] == 1
    assert jacobian.counters["sq"]["value_calls"] < 3, (
        "a value call per input plus one is what a finite-difference fallback looks like; "
        f"see {ADR_BACKEND} D5.5"
    )


# -- ADR 0008 D4.1 pinned-input identity --------------------------------------------------------


def test_same_structure_different_pinned_inputs_differ_only_where_they_should() -> None:
    """ADR 0008 D4.1, verbatim: same `model_version`, different `constants_sha256`, different
    residuals at the same `x`."""
    first, second = compile_problem(build_spec(k=5.0)), compile_problem(build_spec(k=7.0))
    assert first.metadata.model_version == second.metadata.model_version
    assert first.metadata.constants_sha256 != second.metadata.constants_sha256

    def evaluate(problem: object) -> tuple[float, ...]:
        metadata = problem.metadata  # type: ignore[attr-defined]
        ctx = EvaluationContext(
            model_version=metadata.model_version, constants_sha256=metadata.constants_sha256
        )
        values = problem.residual(X, ctx).values  # type: ignore[attr-defined]
        assert values is not None
        return values

    assert evaluate(first) != evaluate(second)


def test_a_pinned_input_missing_from_parameter_ids_is_refused() -> None:
    """The failure D4.1 exists to prevent: a value that changes the answer but not the identity."""
    spec = build_spec()
    broken = ProblemSpec(
        label=spec.label,
        variable_ids=spec.variable_ids,
        equations=spec.equations,
        parameter_ids=(),
        parameters=spec.parameters,
        blocks=spec.blocks,
        block_inputs=spec.block_inputs,
    )
    with pytest.raises(ValueError, match="constants_sha256"):
        compile_problem(broken)


# -- ADR 0008 D4.2 the workspace is inert -------------------------------------------------------


def test_the_workspace_is_inert(problem: object, context: EvaluationContext) -> None:
    """ADR 0008 D4.2, with the deliberately time-shaped keys the ADR names."""
    polluted = EvaluationContext(
        model_version=context.model_version,
        constants_sha256=context.constants_sha256,
        workspace={"time": 12.5, "t": 0.25, "tau": 3.0},
    )
    plain, other = problem.residual(X, context), problem.residual(X, polluted)  # type: ignore[attr-defined]
    assert (plain.values, plain.state_sha256, plain.constants_sha256) == (
        other.values,
        other.state_sha256,
        other.constants_sha256,
    )
    plain_j, other_j = problem.jacobian(X, context), problem.jacobian(X, polluted)  # type: ignore[attr-defined]
    assert (plain_j.data, plain_j.state_sha256) == (other_j.data, other_j.state_sha256)


# -- ADR 0008 D4.4 row accumulation -------------------------------------------------------------


def test_every_equation_has_a_row_accumulation_entry(problem: object) -> None:
    """ADR 0008 D4.4, and T04 reads this to place the nonzeros of the PTC mass matrix `M`."""
    metadata = problem.metadata  # type: ignore[attr-defined]
    assert set(metadata.row_accumulation) == set(metadata.equation_ids)
    assert all(value == "algebraic" for value in metadata.row_accumulation.values())


# -- the residual and the Jacobian describe the same function at the same state ------------------


def test_the_pairing_fields_agree(problem: object, context: EvaluationContext) -> None:
    """`docs/interfaces-frozen.md` §1 and ADR 0008 D2.4."""
    residual = problem.residual(X, context)  # type: ignore[attr-defined]
    jacobian = problem.jacobian(X, context)  # type: ignore[attr-defined]
    for field_name in ("model_version", "constants_sha256", "state_sha256", "phase_signature"):
        assert getattr(residual, field_name) == getattr(jacobian, field_name)
    assert residual.equation_ids == jacobian.row_ids


# -- a state outside a block's domain is reported, never extrapolated ---------------------------


def test_a_domain_error_becomes_an_invalid_trial_state(
    problem: object, context: EvaluationContext
) -> None:
    outside = np.array([-1.0, 0.5])
    residual = problem.residual(outside, context)  # type: ignore[attr-defined]
    assert residual.status == "invalid_trial_state"
    assert residual.values is None
    assert "outside the block's stated domain" in residual.message
    assert problem.jacobian(outside, context).status == "invalid_trial_state"  # type: ignore[attr-defined]


def test_a_state_of_the_wrong_length_is_refused(
    problem: object, context: EvaluationContext
) -> None:
    with pytest.raises(ValueError, match="ordered free variables"):
        problem.residual(np.array([1.0]), context)  # type: ignore[attr-defined]


# -- ADR 0003 D5.7 the backend import is confined ------------------------------------------------


def test_only_the_adapter_imports_the_backend(repo_root: Path) -> None:
    """ADR 0003 D5.7, checked by inspection of the source rather than trusted to convention.

    The orchestrator, the models and the application layer must remain runnable — and reviewable —
    without CasADi present. One module is permitted to import it.
    """
    permitted = {Path("src/openflowsheet/compile/casadi_backend.py")}
    offenders: list[str] = []
    for path in sorted((repo_root / "src").rglob("*.py")):
        relative = path.relative_to(repo_root)
        if relative in permitted:
            continue
        text = path.read_text(encoding="utf-8")
        if "import casadi" in text:
            offenders.append(str(relative))
    assert not offenders, (
        f"{offenders} import the backend. Only the adapter may ({ADR_BACKEND} D5.7)."
    )


def test_the_spec_layer_is_importable_without_the_backend() -> None:
    """The stronger form of the same claim: the backend-free layer really is backend-free."""
    import subprocess
    import sys

    program = (
        "import sys; sys.modules['casadi'] = None\n"
        "import openflowsheet.compile.spec as spec\n"
        "import openflowsheet.canonical, openflowsheet.compiled\n"
        "assert spec.ProblemSpec is not None\n"
        "print('ok')\n"
    )
    completed = subprocess.run(
        [sys.executable, "-c", program], capture_output=True, text=True, check=False
    )
    assert completed.returncode == 0, completed.stderr
    assert "ok" in completed.stdout


# -- a fixture dense enough for the CSC ordering to be falsifiable ------------------------------
#
# The two-variable fixture above has a diagonal Jacobian: one entry per row and per column. Sorting
# column-major and sorting row-major produce the same arrays for it, so every assertion about CSC
# ordering passes under either: a mutation sorting by `(row, column)` survived the whole module.
# This fixture has columns with two rows *and* rows with two columns, which is the smallest shape
# that can tell the two orderings apart.


def build_dense_spec() -> ProblemSpec:
    """`r0 = a+b`, `r1 = b*c`, `r2 = a+c`: each column holds two rows, each row two columns."""
    return ProblemSpec(
        label="k01-dense-1",
        variable_ids=("a", "b", "c"),
        equations=(
            EquationSpec("r0", lambda v, o, p, alg: v["a"] + v["b"], "algebraic"),
            EquationSpec("r1", lambda v, o, p, alg: v["b"] * v["c"], "algebraic"),
            EquationSpec("r2", lambda v, o, p, alg: v["a"] + v["c"], "algebraic"),
        ),
        parameter_ids=(),
        parameters={},
    )


DENSE_X = np.array([2.0, 3.0, 5.0])
#: By hand. dr1/db = c = 5, dr1/dc = b = 3; the rest are 1.
DENSE_EXPECTED = {
    ("r0", "a"): 1.0,
    ("r0", "b"): 1.0,
    ("r1", "b"): 5.0,
    ("r1", "c"): 3.0,
    ("r2", "a"): 1.0,
    ("r2", "c"): 1.0,
}


def test_csc_ordering_is_column_major_on_a_shape_that_can_tell_the_difference() -> None:
    """The arrays themselves, written out. A row-major sort produces different numbers here."""
    problem = compile_problem(build_dense_spec())
    context = EvaluationContext(
        model_version=problem.metadata.model_version,
        constants_sha256=problem.metadata.constants_sha256,
    )
    result = problem.jacobian(DENSE_X, context)

    assert result.nnz == 6
    # column a holds rows 0 and 2; column b rows 0 and 1; column c rows 1 and 2.
    assert result.indptr == (0, 2, 4, 6)
    assert result.indices == (0, 2, 0, 1, 1, 2)
    assert result.data == pytest.approx((1.0, 1.0, 1.0, 5.0, 3.0, 1.0))
    assert csc_as_mapping(result) == pytest.approx(DENSE_EXPECTED)


def test_the_dense_fixture_has_multi_entry_rows_and_columns() -> None:
    """Anti-vacuity for the test above: it only falsifies a row-major sort if the shape is right."""
    problem = compile_problem(build_dense_spec())
    context = EvaluationContext(
        model_version=problem.metadata.model_version,
        constants_sha256=problem.metadata.constants_sha256,
    )
    entries = csc_as_mapping(problem.jacobian(DENSE_X, context))
    rows_per_column: dict[str, int] = {}
    columns_per_row: dict[str, int] = {}
    for row_id, col_id in entries:
        rows_per_column[col_id] = rows_per_column.get(col_id, 0) + 1
        columns_per_row[row_id] = columns_per_row.get(row_id, 0) + 1
    assert min(rows_per_column.values()) >= 2, "no column holds two rows; ordering is unfalsifiable"
    assert min(columns_per_row.values()) >= 2, "no row spans two columns; ordering is unfalsifiable"


# -- holes found by a mutation sweep, and the tests that close them ------------------------------
#
# A sweep over thirteen mutations of the production code found two that every test survived. Both
# are the same class as the CSC-ordering hole above: an assertion that is true of the right answer
# and also of a wrong one, because the fixture is too symmetric to tell them apart.
#
#   1. Replacing the hashed state with a zero vector — `state_sha256(x * 0.0, ...)` — passed all
#      580 tests. Pairing and workspace-inertness both hold when the hash is a *constant*, so
#      nothing asserted that `state_sha256` is the hash of the state actually evaluated. That field
#      is replay identity; a constant would make every state look like every other.
#   2. Computing the reverse product with `tr=False`, i.e. `J @ adjoint` instead of `Jᵀ @ adjoint`,
#      passed everything. The two-variable fixture's Jacobian is diagonal, so `Jᵀ == J` and the
#      mutation is invisible there. The dense fixture is not symmetric, which is where it shows.


def test_the_state_hash_is_of_the_state_actually_evaluated(
    problem: object, context: EvaluationContext
) -> None:
    """Computed independently here, rather than only compared with itself.

    Closes mutation 1: a `state_sha256` that ignores `x` satisfies every pairing and inertness
    assertion in this module, because those compare the field against *another copy of itself*.
    """
    from openflowsheet.canonical import state_sha256

    for point in (X, np.array([1.0, 2.0]), np.array([-3.5, 0.25])):
        result = problem.residual(point, context)  # type: ignore[attr-defined]
        assert result.state_sha256 == state_sha256(point, ("a", "b"))
        assert problem.jacobian(point, context).state_sha256 == state_sha256(point, ("a", "b"))  # type: ignore[attr-defined]


def test_distinct_states_get_distinct_hashes(problem: object, context: EvaluationContext) -> None:
    """The weaker half of the same property, stated separately because it is the one that bites."""
    hashes = {
        problem.residual(point, context).state_sha256  # type: ignore[attr-defined]
        for point in (np.array([2.0, 0.5]), np.array([2.0, 0.6]), np.array([2.1, 0.5]))
    }
    assert len(hashes) == 3


def test_vjp_is_the_transpose_on_a_non_symmetric_jacobian() -> None:
    """Closes mutation 2. `Jᵀ @ adjoint` and `J @ adjoint` differ only where `J != Jᵀ`."""
    problem = compile_problem(build_dense_spec())
    context = EvaluationContext(
        model_version=problem.metadata.model_version,
        constants_sha256=problem.metadata.constants_sha256,
    )
    dense = np.zeros((3, 3))
    order_rows, order_columns = ("r0", "r1", "r2"), ("a", "b", "c")
    for (row_id, col_id), value in csc_as_mapping(problem.jacobian(DENSE_X, context)).items():
        dense[order_rows.index(row_id), order_columns.index(col_id)] = value
    assert not np.allclose(dense, dense.T), (
        "this fixture's Jacobian is symmetric, so it cannot distinguish a transposed product from "
        "an untransposed one; the test above it would be vacuous"
    )

    for adjoint in (
        np.array([1.0, 0.0, 0.0]),
        np.array([0.0, 1.0, 0.0]),
        np.array([2.0, -3.0, 1.5]),
    ):
        assert np.array(problem.vjp(DENSE_X, adjoint, context)) == pytest.approx(dense.T @ adjoint)
        assert np.array(problem.jvp(DENSE_X, adjoint, context)) == pytest.approx(dense @ adjoint)


# -- properties the Fable review found pinned by nothing ----------------------------------------
#
# Each of these corresponds to a mutation that survived all 583 tests when the review ran it. They
# are grouped rather than scattered so the next reader can see what class of thing went unchecked:
# everything here is a *contract* the adapter states and no fixture exercised, because every test
# built its context from `problem.metadata` and passed a finite, well-formed state.


@pytest.mark.parametrize(
    ("bad", "reason"),
    [
        (float("nan"), "non-finite"),
        (float("inf"), "non-finite"),
        # -inf is below the block's stated domain, so the block rejects it first and the honest
        # report names the domain rather than the arithmetic. Still `invalid_trial_state`, still no
        # values — which is the property under test; the message merely says which guard fired.
        (float("-inf"), "outside the block's stated domain"),
    ],
)
def test_a_non_finite_residual_is_not_reported_ok(
    problem: object, context: EvaluationContext, bad: float, reason: str
) -> None:
    """A NaN is not a residual, and `ok` would hand a solver a number it will act on.

    `serialize.check_evaluation_document` already refused such a document, so until this returned
    `invalid_trial_state` the two halves of K01 disagreed about what was valid — the adapter emitted
    output its own serializer rejected.
    """
    from openflowsheet.serialize import check_evaluation_document, evaluation_result_to_document

    result = problem.residual(np.array([bad, 0.5]), context)  # type: ignore[attr-defined]
    assert result.status == "invalid_trial_state"
    assert result.values is None
    assert reason in result.message
    check_evaluation_document(evaluation_result_to_document(result))


@pytest.mark.parametrize("bad", [float("nan"), float("inf")])
def test_a_non_finite_jacobian_entry_is_not_reported_ok(
    problem: object, context: EvaluationContext, bad: float
) -> None:
    from openflowsheet.serialize import check_jacobian_document, jacobian_result_to_document

    result = problem.jacobian(np.array([bad, 0.5]), context)  # type: ignore[attr-defined]
    assert result.status == "invalid_trial_state"
    assert result.data == ()
    check_jacobian_document(jacobian_result_to_document(result))


def test_a_context_pinning_a_different_problem_is_refused(problem: object) -> None:
    """The context *pins* model and data versions (plan §2.1); ignoring the pin is a wrong answer.

    The result would carry this problem's identity, so a caller would be told its pin had been
    honoured when it had been ignored.
    """
    metadata = problem.metadata  # type: ignore[attr-defined]
    with pytest.raises(ValueError, match="model_version"):
        problem.residual(  # type: ignore[attr-defined]
            X,
            EvaluationContext(
                model_version="somebody-elses-model",
                constants_sha256=metadata.constants_sha256,
            ),
        )
    with pytest.raises(ValueError, match="constants_sha256"):
        problem.jacobian(  # type: ignore[attr-defined]
            X,
            EvaluationContext(model_version=metadata.model_version, constants_sha256="0" * 64),
        )


def test_an_unsupported_accuracy_policy_is_reported_not_ignored(
    problem: object, context: EvaluationContext
) -> None:
    """Negotiated, not decorative: answering in double under a `float32-fast` pin is a lie."""
    policy = EvaluationContext(
        model_version=context.model_version,
        constants_sha256=context.constants_sha256,
        accuracy_policy="float32-fast",
    )
    for result in (problem.residual(X, policy), problem.jacobian(X, policy)):  # type: ignore[attr-defined]
        assert result.status == "unsupported"
        assert "float32-fast" in result.message


def test_the_phase_signature_is_the_contexts(problem: object, context: EvaluationContext) -> None:
    """It was hard-coded `None`, so the pairing test compared `None == None` and saw nothing."""
    two_phase = EvaluationContext(
        model_version=context.model_version,
        constants_sha256=context.constants_sha256,
        phase_signature="TWO_PHASE",
    )
    assert problem.residual(X, two_phase).phase_signature == "TWO_PHASE"  # type: ignore[attr-defined]
    assert problem.jacobian(X, two_phase).phase_signature == "TWO_PHASE"  # type: ignore[attr-defined]
    assert problem.reconstruct(X, two_phase).phase_signature == "TWO_PHASE"  # type: ignore[attr-defined]
    assert problem.residual(X, context).phase_signature is None  # type: ignore[attr-defined]


def test_a_declared_entry_that_is_never_supplied_is_refused(context: EvaluationContext) -> None:
    """Omission would land as the 0.0 the matrix was filled with — indistinguishable from intent."""
    problem = compile_problem(build_spec(block=Omitting()))
    result = problem.jacobian(X, context)
    assert result.status == "error"
    assert "returned no value for them" in result.message


def test_a_repeated_entry_is_refused(context: EvaluationContext) -> None:
    """Last-one-wins hides which of the two values the block actually meant."""
    problem = compile_problem(build_spec(block=Repeating()))
    result = problem.jacobian(X, context)
    assert result.status == "error"
    assert "two values" in result.message


def test_constants_sha256_does_not_depend_on_how_the_mapping_was_built(
    problem: object,
) -> None:
    """ADR 0008 D4.1: the digest is over `parameter_ids` order, not dict insertion order.

    Every fixture happened to build `parameters` in `parameter_ids` order, so a digest that ignored
    `parameter_ids` entirely — or sorted them — passed everything.
    """
    from openflowsheet.canonical import constants_sha256

    spec = build_spec()
    shuffled = ProblemSpec(
        label=spec.label,
        variable_ids=spec.variable_ids,
        equations=spec.equations,
        parameter_ids=("k", "extra"),
        parameters={"extra": 1.0, "k": 5.0},  # deliberately not in parameter_ids order
        blocks=spec.blocks,
        block_inputs=spec.block_inputs,
    )
    compiled = compile_problem(shuffled)
    assert compiled.metadata.constants_sha256 == constants_sha256(
        {"extra": 1.0, "k": 5.0}, ("k", "extra")
    )
    # And the order is load-bearing: the same values under a different declared order differ.
    assert (
        constants_sha256({"extra": 1.0, "k": 5.0}, ("extra", "k"))
        != compiled.metadata.constants_sha256
    )


# -- ProblemSpec.validate, one test per rule (the review found none) -----------------------------


@pytest.mark.parametrize(
    ("mutate", "match"),
    [
        (lambda s: {"variable_ids": ("a", "a")}, "duplicates"),
        (lambda s: {"parameter_ids": ("k", "k"), "parameters": {"k": 1.0}}, "duplicates"),
        (lambda s: {"parameter_ids": (), "parameters": {"k": 1.0}}, "constants_sha256"),
        (lambda s: {"column_scales": {"a": 0.0}}, "non-positive"),
        (lambda s: {"row_scales": {"r0": -1.0}}, "non-positive"),
        (lambda s: {"column_scales": {"nope": 1.0}}, "unknown ids"),
        (lambda s: {"block_inputs": {"sq": ("a", "nope")}}, "unknown variables"),
        (lambda s: {"block_inputs": {"sq": ("a",)}}, "declares 2 inputs"),
        (lambda s: {"block_inputs": {"sq": ("a", "b"), "ghost": ("a",)}}, "not a declared block"),
    ],
)
def test_validate_refuses_a_spec_that_could_only_answer_wrongly(
    mutate: Callable[[ProblemSpec], dict[str, object]], match: str
) -> None:
    base = build_spec()
    fields = {
        "label": base.label,
        "variable_ids": base.variable_ids,
        "equations": base.equations,
        "parameter_ids": base.parameter_ids,
        "parameters": dict(base.parameters),
        "blocks": base.blocks,
        "block_inputs": dict(base.block_inputs),
        "column_scales": dict(base.column_scales),
        "row_scales": dict(base.row_scales),
    }
    fields.update(mutate(base))
    with pytest.raises(ValueError, match=match):
        ProblemSpec(**fields).validate()  # type: ignore[arg-type]
