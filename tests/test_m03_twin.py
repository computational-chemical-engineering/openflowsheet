"""M03 WO-1: the parametric twin (spec §3.2; ADR 0031 D2) — A01 at P1-P3, A02, A04's twin half.

The twin is `ProblemSpec` compiled a second time with the requested pinned inputs as CasADi
symbols. Its whole licence is that it is *the same function* as the frozen base problem, so the
first group of tests checks the consequence rather than the construction: at each registered state
the residual and every one of the 49 x 47 Jacobian entries equal the base problem's bit for bit
after signed-zero normalization (A01; the tolerance is 0), and the twin's identity is the base's.
The second group checks the base did not move (no identity of the frozen `CompiledProblem` depends
on the twin). A02 pins the parameter Jacobian's pattern and values at P1 against the generator's
closed form; A04's twin half is that a builder that cannot take a symbol is named, not guessed at.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np
import numpy.typing as npt
import pytest
from m03_support import (
    PRESSURE_PARAMETERS,
    REGISTERED_PARAMETERS,
    number,
    reference,
    solved,
    x_squared_spec,
)

from openflowsheet.canonical import constants_sha256
from openflowsheet.compile.casadi_backend import (
    ParameterNotDifferentiableError,
    TwinMatrix,
    compile_parametric_twin,
    compile_problem,
)
from openflowsheet.compile.reference import state_vector
from openflowsheet.compiled import EvaluationContext, JacobianResult
from openflowsheet.orchestrator.tear import Syn001TearProblem

SENSITIVITY_STATES = ("P1", "P2", "P3")
#: The subsets A01 is measured with: the seven pinned inputs the specification probed symbolic,
#: all ten, and a single one.
SUBSETS: dict[str, tuple[str, ...]] = {
    "seven": REGISTERED_PARAMETERS + PRESSURE_PARAMETERS,
    "one": ("U-FLASH.T_spec",),
}


def dense(matrix: TwinMatrix | JacobianResult) -> npt.NDArray[np.float64]:
    """The CSC arrays as a dense matrix with structural zeros as +0.0."""
    result = np.zeros((len(matrix.row_ids), len(matrix.col_ids)))
    for column in range(len(matrix.col_ids)):
        for offset in range(matrix.indptr[column], matrix.indptr[column + 1]):
            result[matrix.indices[offset], column] = matrix.data[offset]
    return result


def normalized(values: Sequence[float] | npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
    """Spec §3.2's signed-zero normalization, `v + 0.0`."""
    return np.asarray(values, dtype=np.float64) + 0.0


def at_state(state: str) -> tuple[Syn001TearProblem, npt.NDArray[np.float64]]:
    sheet, result = solved(state)
    assert result.final_state is not None
    tear = Syn001TearProblem(sheet)
    return tear, np.array(state_vector(tear.spec, result.final_state))


def pinned_values(tear: Syn001TearProblem, subset: Sequence[str]) -> dict[str, float]:
    return {name: tear.spec.parameters[name] for name in subset}


def assert_bitwise_twin(tear: Syn001TearProblem, x: npt.NDArray[np.float64], subset: Any) -> None:
    twin = compile_parametric_twin(tear.spec, subset)
    p0 = pinned_values(tear, subset)
    base_residual = tear.compiled.residual(x, tear.context)
    base_jacobian = tear.compiled.jacobian(x, tear.context)
    assert base_residual.status == "ok" and base_residual.values is not None
    assert base_jacobian.status == "ok"

    twin_residual = normalized(twin.residual(x, p0))
    twin_jacobian = normalized(dense(twin.jacobian_x(x, p0)))
    assert twin_jacobian.shape == (49, 47)
    # Tolerance 0: `array_equal` is exact, and an unequal count is the size of the defect.
    assert np.array_equal(twin_residual, normalized(base_residual.values))
    assert np.array_equal(twin_jacobian, normalized(dense(base_jacobian)))
    assert twin.model_version == tear.compiled.metadata.model_version
    assert twin.constants_sha256(p0) == tear.compiled.metadata.constants_sha256


# -- A01 at P1-P3 -------------------------------------------------------------------------------


@pytest.mark.parametrize("state", SENSITIVITY_STATES)
@pytest.mark.parametrize("subset", ["seven", "all", "one"])
def test_a01_the_twin_is_the_base_problem_bit_for_bit(state: str, subset: str) -> None:
    tear, x = at_state(state)
    chosen = tear.spec.parameter_ids if subset == "all" else SUBSETS[subset]
    assert_bitwise_twin(tear, x, chosen)


#: M03 review F5: a twin built at one registered state, evaluated at another, and the pinned
#: inputs that move between the two.
MOVED: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("P1", "P2", ("U-SPLIT.split_fraction",)),
    ("P1", "P3", ("U-SPLIT.split_fraction", "U-FLASH.T_spec")),
    ("P1", "P2", REGISTERED_PARAMETERS + PRESSURE_PARAMETERS),
)


@pytest.mark.parametrize(("built", "moved", "subset"), MOVED, ids=lambda value: str(value)[:24])
def test_the_twin_built_at_one_state_is_the_base_problem_compiled_at_another(
    built: str, moved: str, subset: tuple[str, ...]
) -> None:
    """M03 review F5: Q0′ proves the twin equal to the base only at the base's own pinned values,
    and the NLP evaluates the twin at d ≠ d₀ on every iteration. A row builder that reached a
    pinned value by closure rather than through `parameters` would pass Q0′ with a twin that does
    not move with p. So: the twin compiled at `built`, evaluated at `moved`'s root and pinned
    values, equals `moved`'s own base problem bit for bit (tolerance 0, signed zeros
    normalized)."""
    tear, _ = at_state(built)
    target, x = at_state(moved)
    p = pinned_values(target, subset)
    assert p != pinned_values(tear, subset)
    twin = compile_parametric_twin(tear.spec, subset)
    base_residual = target.compiled.residual(x, target.context)
    base_jacobian = target.compiled.jacobian(x, target.context)
    assert base_residual.status == "ok" and base_residual.values is not None
    assert base_jacobian.status == "ok"
    assert np.array_equal(normalized(twin.residual(x, p)), normalized(base_residual.values))
    assert np.array_equal(
        normalized(dense(twin.jacobian_x(x, p))), normalized(dense(base_jacobian))
    )
    assert twin.constants_sha256(p) == target.compiled.metadata.constants_sha256
    # The comparison sees p: a twin frozen at `built`'s values (the closure defect) differs here.
    frozen = normalized(twin.residual(x, pinned_values(tear, subset)))
    assert not np.array_equal(frozen, normalized(base_residual.values))


def test_a01_the_twin_and_its_parameter_columns_come_from_one_graph() -> None:
    """`jacobian_p`'s rows are the base's rows and its columns the requested ids, in order."""
    tear, x = at_state("P1")
    twin = compile_parametric_twin(tear.spec, REGISTERED_PARAMETERS)
    jacobian = twin.jacobian_p(x, pinned_values(tear, REGISTERED_PARAMETERS))
    assert jacobian.row_ids == tear.spec.equation_ids
    assert jacobian.col_ids == REGISTERED_PARAMETERS
    assert twin.parameter_ids == REGISTERED_PARAMETERS


# -- A02 ------------------------------------------------------------------------------------------


def test_a02_the_parameter_jacobian_at_p1_is_the_closed_form() -> None:
    expected = reference()["parameter_jacobian_P1"]
    tear, x = at_state("P1")
    twin = compile_parametric_twin(tear.spec, REGISTERED_PARAMETERS)
    jacobian = twin.jacobian_p(x, pinned_values(tear, REGISTERED_PARAMETERS))

    found: dict[str, dict[str, float]] = {name: {} for name in jacobian.col_ids}
    for column, name in enumerate(jacobian.col_ids):
        for offset in range(jacobian.indptr[column], jacobian.indptr[column + 1]):
            value = jacobian.data[offset]
            if value != 0.0:
                found[name][jacobian.row_ids[jacobian.indices[offset]]] = value

    assert set(found) == set(expected)
    for name, entries in expected.items():
        assert set(found[name]) == set(entries), name
        for row, value in entries.items():
            closed = number(value)
            if name == "U-SPLIT.split_fraction":
                # ∓S5.n_i on the recycle and purge rows, within 1e-15 relative.
                assert abs(found[name][row] - closed) <= 1e-15 * abs(closed), (name, row)
            else:
                assert closed == -1.0
                assert found[name][row] == -1.0, (name, row)
    # Six non-zeros for r; one per specification row elsewhere (two for the flash T).
    assert len(found["U-SPLIT.split_fraction"]) == 6
    assert len(found["U-FLASH.T_spec"]) == 2


# -- identity: the base problem does not move -----------------------------------------------------


def test_compiling_a_twin_moves_no_identity_of_the_base_problem() -> None:
    tear, x = at_state("P1")
    base = compile_problem(tear.spec)
    before = (
        base.metadata.model_version,
        base.metadata.constants_sha256,
        base.metadata.capabilities,
        base.metadata.parameter_ids,
        base.structural_pattern(),
    )
    compile_parametric_twin(tear.spec, tear.spec.parameter_ids)
    after = compile_problem(tear.spec)
    assert (
        after.metadata.model_version,
        after.metadata.constants_sha256,
        after.metadata.capabilities,
        after.metadata.parameter_ids,
        after.structural_pattern(),
    ) == before
    assert base.metadata == after.metadata
    context = EvaluationContext(
        model_version=base.metadata.model_version,
        constants_sha256=base.metadata.constants_sha256,
    )
    assert base.residual(x, context).values == after.residual(x, context).values


def test_the_twins_constants_identity_is_the_base_identity_at_the_moved_inputs() -> None:
    """`constants_sha256(p)` names the pinned-input vector at `p`, as a recompiled base would."""
    tear, _ = at_state("P1")
    twin = compile_parametric_twin(tear.spec, ("U-SPLIT.split_fraction",))
    p2, _ = at_state("P2")
    moved = twin.constants_sha256({"U-SPLIT.split_fraction": 0.95})
    assert moved == p2.compiled.metadata.constants_sha256
    assert moved != tear.compiled.metadata.constants_sha256
    assert moved == constants_sha256(
        {**tear.spec.parameters, "U-SPLIT.split_fraction": 0.95}, tear.spec.parameter_ids
    )


# -- A04's twin half ------------------------------------------------------------------------------


def test_a04_an_id_that_is_not_a_pinned_input_does_not_build_a_twin() -> None:
    tear, _ = at_state("P1")
    with pytest.raises(ValueError, match="not pinned inputs"):
        compile_parametric_twin(tear.spec, ("S2.T",))


def test_a04_a_builder_that_converts_its_parameter_is_named() -> None:
    spec = x_squared_spec(0.25, convert=True)
    compile_problem(spec)  # the base problem is unaffected: `float(0.25)` is a float
    with pytest.raises(ParameterNotDifferentiableError) as raised:
        compile_parametric_twin(spec, ("p",))
    assert raised.value.parameter_ids == ("p",)
    assert raised.value.equation_id == "R"


def test_the_twin_refuses_values_for_other_inputs_than_it_was_built_for() -> None:
    spec = x_squared_spec(0.25)
    twin = compile_parametric_twin(spec, ("p",))
    with pytest.raises(ValueError, match="exactly"):
        twin.residual(np.array([0.5]), {"q": 0.25})
    assert twin.residual(np.array([0.5]), {"p": 0.25}) == (0.0,)
