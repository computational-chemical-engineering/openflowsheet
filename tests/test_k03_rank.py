"""K03 M4: structural alias elimination of the consistent-redundant rows (§7, R-011).

The SYN-001 flowsheet as its manifests declare it is over-determined by two: nine pressure rows
over seven pressure columns. K02 assembled them all and reported it rather than dropping any,
because blueprint §7.7 makes a regularized least-squares step a recovery edge and "never
permission to discard equations". This is the structural answer: the rows form a graph, a row
closing a cycle is a combination of the path around it, and the combination is *certified* at
two states before anything is removed.

The tests below check the algorithm on the real assembled flowsheet — where the answer is
registered in the specification, so this is two independent derivations of the same thing — and
on small synthetic graphs where each refusal can be provoked exactly.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np
import pytest

from openflowsheet.compile.casadi_backend import compile_problem
from openflowsheet.compile.reference import row_values, state_vector
from openflowsheet.compiled import EvaluationContext
from openflowsheet.orchestrator.rank import (
    CONST,
    SpecificationConflictError,
    UnsupportedRankStructureError,
    eliminate_alias_rows,
)


def assembled(case: Mapping[str, Any]) -> tuple[Any, dict[str, float], Any]:
    import sys

    sys.path.insert(0, "tests")
    import test_k02_flowsheet as reference_module

    spec = reference_module.flowsheet_for(case).spec()
    state = reference_module.reference_state(case, spec)
    problem = compile_problem(spec)
    metadata = problem.metadata
    context = EvaluationContext(
        model_version=metadata.model_version, constants_sha256=metadata.constants_sha256
    )
    jacobian = problem.jacobian(np.array(state_vector(spec, state)), context)
    return spec, state, jacobian


def coefficients_of(jacobian: Any) -> dict[str, dict[str, float]]:
    rows: dict[str, dict[str, float]] = {name: {} for name in jacobian.row_ids}
    for column in range(len(jacobian.col_ids)):
        for offset in range(jacobian.indptr[column], jacobian.indptr[column + 1]):
            rows[jacobian.row_ids[jacobian.indices[offset]]][jacobian.col_ids[column]] = (
                jacobian.data[offset]
            )
    return rows


def probe_states(spec: Any, state: Mapping[str, float]) -> list[Mapping[str, float]]:
    """Two states differing in *every* pressure coordinate, as §7.2 requires."""

    def shifted(delta: float) -> Mapping[str, float]:
        moved = dict(state)
        for index, name in enumerate(spec.variable_ids):
            if spec.variable_kinds.get(name) == "pressure":
                moved[name] = state[name] + delta * (index + 1)
        return row_values(spec, moved)

    return [shifted(0.0), shifted(1234.5)]


def test_the_algorithm_finds_the_registered_two_rows_and_their_signs(
    reference_values: Mapping[str, Any],
) -> None:
    """§7.2's registered table, derived here by the graph rather than read from the document.

    The signs matter and were wrong once: the specification's first version recorded the second
    row negated, which is invisible at a consistent state where the mismatch is zero either way.
    This derivation is independent of that table.
    """
    case = {entry["case_id"]: entry for entry in reference_values["variants"]}["SYN-001-nominal"]
    spec, state, jacobian = assembled(case)

    result = eliminate_alias_rows(
        row_ids=spec.equation_ids,
        coefficients=coefficients_of(jacobian),
        column_kinds=spec.variable_kinds,
        residuals=probe_states(spec, state),
    )

    assert len(result.retained_rows) == 47
    assert result.eliminated_ids == {"U-FLASH:FLASH-P:inlet", "U-SPLIT:SPLIT-P:recycle"}
    assert len(result.retained_rows) + len(result.eliminated) == 49

    by_id = {row.row_id: row for row in result.eliminated}
    assert dict(by_id["U-FLASH:FLASH-P:inlet"].equals) == {
        "U-FEED:FEED-P": +1,
        "U-MIX:MIX-pressure:0": -1,
        "U-HEAT:HEAT-pressure": +1,
    }
    assert dict(by_id["U-SPLIT:SPLIT-P:recycle"].equals) == {
        "U-FEED:FEED-P": +1,
        "U-MIX:MIX-pressure:0": -1,
        "U-MIX:MIX-pressure:1": +1,
        "U-FLASH:FLASH-P:liquid": -1,
    }
    for row in result.eliminated:
        assert row.constant_mismatch == 0.0
        assert row.tolerance == 1e-2


@pytest.mark.parametrize(
    "case_id",
    [
        "SYN-001-nominal",
        "SYN-001-once-through",
        "SYN-001-high-recycle",
        "SYN-001-all-liquid-310K",
        "SYN-001-all-vapor-420K",
    ],
)
def test_the_elimination_is_the_same_at_every_registered_variant(
    case_id: str, reference_values: Mapping[str, Any]
) -> None:
    """A30: the pressure pattern is state-invariant, so the plan does not depend on the iterate.

    A rank decision that moved with the state would not be structural, and the plan is built
    once, before anything is initialized.
    """
    case = {entry["case_id"]: entry for entry in reference_values["variants"]}[case_id]
    spec, state, jacobian = assembled(case)
    result = eliminate_alias_rows(
        row_ids=spec.equation_ids,
        coefficients=coefficients_of(jacobian),
        column_kinds=spec.variable_kinds,
        residuals=probe_states(spec, state),
    )
    assert result.eliminated_ids == {"U-FLASH:FLASH-P:inlet", "U-SPLIT:SPLIT-P:recycle"}
    assert len(result.retained_rows) == 47


def test_an_inconsistent_specification_is_reported_not_factorized(
    reference_values: Mapping[str, Any],
) -> None:
    """§7.2's registered conflict state: the flash at 150 kPa against a feed at 100 kPa.

    `m_e = −50 000 Pa` — the closed form is `P_feed − P_f`. A flowsheet declaring both has no
    state satisfying it, and saying so is more useful than factorizing something that splits the
    difference.
    """
    from dataclasses import replace

    case = {entry["case_id"]: entry for entry in reference_values["variants"]}["SYN-001-nominal"]
    spec, state, jacobian = assembled(case)
    conflicted = replace(spec, parameters={**spec.parameters, "U-FLASH.P_spec": 150_000.0})

    with pytest.raises(SpecificationConflictError) as raised:
        eliminate_alias_rows(
            row_ids=conflicted.equation_ids,
            coefficients=coefficients_of(jacobian),
            column_kinds=conflicted.variable_kinds,
            residuals=probe_states(conflicted, state),
        )
    message = str(raised.value)
    assert "SPECIFICATION_CONFLICT" in message
    assert "-50000" in message.replace(" ", "") or "-5e+04" in message


# ------------------------------------------------------------------- the refusals, provoked


def synthetic(
    rows: Mapping[str, Mapping[str, float]],
    constants: Mapping[str, float],
    kinds: Mapping[str, str] | None = None,
) -> Any:
    """A tiny pressure graph, with each row's value taken to be affine in its columns."""
    columns = sorted({name for row in rows.values() for name in row})
    column_kinds = kinds or dict.fromkeys(columns, "pressure")

    def values_at(point: Mapping[str, float]) -> dict[str, float]:
        return {
            row_id: sum(c * point[name] for name, c in row.items()) + constants[row_id]
            for row_id, row in rows.items()
        }

    first = {name: 1.0 * (index + 1) for index, name in enumerate(columns)}
    second = {name: 7.5 * (index + 3) for index, name in enumerate(columns)}
    return eliminate_alias_rows(
        row_ids=tuple(rows),
        coefficients=rows,
        column_kinds=column_kinds,
        residuals=[values_at(first), values_at(second)],
    )


def test_a_simple_cycle_is_eliminated_with_the_right_path() -> None:
    """`a − b`, `b − c`, `a − c`: the third closes the cycle and equals the first two."""
    result = synthetic(
        rows={
            "ab": {"a": 1.0, "b": -1.0},
            "bc": {"b": 1.0, "c": -1.0},
            "ac": {"a": 1.0, "c": -1.0},
        },
        constants={"ab": 0.0, "bc": 0.0, "ac": 0.0},
    )
    assert result.retained_rows == ("ab", "bc")
    assert len(result.eliminated) == 1
    assert dict(result.eliminated[0].equals) == {"ab": +1, "bc": +1}
    assert result.eliminated[0].constant_mismatch == 0.0


def test_a_specification_row_uses_the_constant_node() -> None:
    """`a − 100`, `a − b`, `b − 100`: the third is redundant through the constant node."""
    result = synthetic(
        rows={"spec_a": {"a": 1.0}, "ab": {"a": 1.0, "b": -1.0}, "spec_b": {"b": 1.0}},
        constants={"spec_a": -100.0, "ab": 0.0, "spec_b": -100.0},
    )
    assert result.eliminated_ids == {"spec_b"}
    assert result.eliminated[0].constant_mismatch == pytest.approx(0.0, abs=1e-12)
    assert CONST not in result.retained_rows


def test_two_specifications_that_disagree_are_a_conflict() -> None:
    """The same graph with the second specification at a different value."""
    with pytest.raises(SpecificationConflictError, match="contradict"):
        synthetic(
            rows={"spec_a": {"a": 1.0}, "ab": {"a": 1.0, "b": -1.0}, "spec_b": {"b": 1.0}},
            constants={"spec_a": -100.0, "ab": 0.0, "spec_b": -150.0},
        )


def test_a_coefficient_that_is_not_plus_or_minus_one_is_refused() -> None:
    """A pressure *ratio* is not a copy; generalizing is T01/T06's and guessing is nobody's."""
    with pytest.raises(UnsupportedRankStructureError, match="not ±1"):
        synthetic(
            rows={"ab": {"a": 1.0, "b": -1.0}, "ratio": {"a": 2.0, "b": -1.0}},
            constants={"ab": 0.0, "ratio": 0.0},
        )


def test_a_row_over_three_pressure_columns_is_refused() -> None:
    with pytest.raises(UnsupportedRankStructureError, match="3 pressure columns"):
        synthetic(
            rows={"abc": {"a": 1.0, "b": -1.0, "c": 1.0}},
            constants={"abc": 0.0},
        )


def test_a_row_touching_another_kind_is_left_alone() -> None:
    """Only rows entirely over the eligible kind qualify; everything else is retained untouched."""
    result = synthetic(
        rows={"ab": {"a": 1.0, "b": -1.0}, "mixed": {"a": 1.0, "n": -1.0}},
        constants={"ab": 0.0, "mixed": 0.0},
        kinds={"a": "pressure", "b": "pressure", "n": "molar_flow"},
    )
    assert result.eliminated == ()
    assert set(result.retained_rows) == {"ab", "mixed"}


def test_a_mismatch_that_is_not_constant_is_not_a_certificate() -> None:
    """The linearity witness, and the state that makes it bite.

    Two states must give the *same* mismatch: a row that looks structurally redundant but whose
    mismatch moves is not a linear combination of the path, and eliminating it would remove a
    real equation. The synthetic graphs above are affine by construction, so nothing there can
    catch a missing witness; these residuals are supplied directly and disagree.
    """
    with pytest.raises(UnsupportedRankStructureError, match="not constant"):
        eliminate_alias_rows(
            row_ids=("ab", "bc", "ac"),
            coefficients={
                "ab": {"a": 1.0, "b": -1.0},
                "bc": {"b": 1.0, "c": -1.0},
                "ac": {"a": 1.0, "c": -1.0},
            },
            column_kinds={"a": "pressure", "b": "pressure", "c": "pressure"},
            residuals=[
                {"ab": 1.0, "bc": 1.0, "ac": 2.0},
                {"ab": 1.0, "bc": 1.0, "ac": 5.0},
            ],
        )


def test_one_probe_state_is_not_a_certificate() -> None:
    """A single value of a quantity is not evidence that the quantity is constant."""
    with pytest.raises(ValueError, match="two states"):
        eliminate_alias_rows(
            row_ids=("a",),
            coefficients={"a": {"p": 1.0}},
            column_kinds={"p": "pressure"},
            residuals=[{"a": 0.0}],
        )


def test_a_path_of_two_node_edges_telescopes_exactly() -> None:
    """Why two probe states certify the whole identity here (Fable review of K03, S4).

    The probes witness that the *mismatch* is constant. The *linear* part is covered by
    structure instead: every eligible row has exactly two pressure columns with coefficients
    ±1, so the signed sum along any path cancels the interior nodes exactly and equals the
    endpoints. This test is the argument in executable form — build a chain of any length,
    and the combination the certificate names is the row it certifies, coefficient for
    coefficient, with no tolerance anywhere.

    It matters because it is the answer to "is a two-probe certificate a certificate?", and
    because a later policy that admitted a ratio or a scaled drop would break the premise and
    need an explicit coefficient check that today would be unfailable.
    """
    length = 6
    columns = [f"P{index}" for index in range(length + 1)]
    coefficients = {
        f"edge{index}": {columns[index]: 1.0, columns[index + 1]: -1.0} for index in range(length)
    }
    coefficients["alias"] = {columns[0]: 1.0, columns[length]: -1.0}
    kinds = dict.fromkeys(columns, "pressure")
    zero = dict.fromkeys(coefficients, 0.0)

    elimination = eliminate_alias_rows(
        row_ids=(*[f"edge{index}" for index in range(length)], "alias"),
        coefficients=coefficients,
        column_kinds=kinds,
        residuals=[zero, dict(zero)],
    )
    assert [row.row_id for row in elimination.eliminated] == ["alias"]
    path = elimination.eliminated[0].equals
    assert len(path) == length

    combination: dict[str, float] = {}
    for name, sign in path:
        for column, value in coefficients[name].items():
            combination[column] = combination.get(column, 0.0) + sign * value
    interior = {column: value for column, value in combination.items() if value != 0.0}
    assert interior == coefficients["alias"], "the interior nodes cancel exactly, not nearly"
    assert all(value == int(value) for value in combination.values())


# ---------------------------------------------- the duty over-specification, measured not assumed


def test_a_duty_over_specification_is_refused_as_structure_and_not_as_a_conflict() -> None:
    """`SYN-001-conflicting-heater-spec` downstream: what actually happens, and what does not.

    Until 2026-09-23 three places in this repository said the solver rejects that revision with
    `SPECIFICATION_CONFLICT`. Nobody had run it: `Syn001Flowsheet` has no heater-duty parameter,
    so the revision had never been compiled, and the sentence was a prediction written as a
    measurement. It is wrong. `SPECIFICATION_CONFLICT` is for a *pressure-graph* cycle whose
    mismatch exceeds ADR 0001 D6's 1e-2 Pa; a duty row is over a `heat_rate` column, which alias
    elimination never examines, so the row is retained and the assembled system is 50 rows over
    47 columns. What refuses it is `SolvePlan.__post_init__`, on squareness.

    That refusal is correct but says the wrong thing: it describes a limit of this tool where the
    truth is that the heater is specified twice. Closing that gap is T01's, and this test is what
    stops the claim drifting back.
    """
    from dataclasses import replace

    from openflowsheet.compile.spec import EquationSpec
    from openflowsheet.models.syn001.flowsheet import Syn001Flowsheet
    from openflowsheet.orchestrator.tear import Syn001TearProblem
    from openflowsheet.thermo.syn001 import Syn001Provider

    flowsheet = Syn001Flowsheet(
        provider=Syn001Provider(),
        context=EvaluationContext(
            model_version="probe", constants_sha256="0" * 64, phase_signature=None
        ),
    )
    nominal = flowsheet.spec()

    def duty_row(
        variables: Mapping[str, Any],
        blocks: Mapping[str, Any],
        parameters: Mapping[str, float],
        algebra: Any,
    ) -> Any:
        return variables["U-HEAT.Q"] - parameters["SPEC-heater-duty"]

    conflicted = replace(
        nominal,
        label="SYN-001-conflicting-heater-spec-probe",
        equations=(
            *nominal.equations,
            EquationSpec(
                equation_id="SPEC-heater-duty",
                build=duty_row,
                accumulation="algebraic",
                origin="test#SPEC-heater-duty",
            ),
        ),
        parameter_ids=(*nominal.parameter_ids, "SPEC-heater-duty"),
        parameters={**nominal.parameters, "SPEC-heater-duty": 50_000.0},
        row_kinds={**nominal.row_kinds, "SPEC-heater-duty": "heat_rate"},
    )
    assert len(conflicted.equations) == len(nominal.equations) + 1
    assert len(conflicted.variable_ids) == len(nominal.variable_ids)

    original = Syn001Flowsheet.spec
    try:
        Syn001Flowsheet.spec = lambda self: conflicted  # type: ignore[assignment,method-assign]
        assert flowsheet.spec() is conflicted, "the substitution did not land"
        with pytest.raises(ValueError) as raised:
            Syn001TearProblem(flowsheet)
    finally:
        Syn001Flowsheet.spec = original  # type: ignore[method-assign]

    message = str(raised.value)
    assert "UNSUPPORTED_RANK_STRUCTURE" in message
    assert "45x44" in message
    assert "SPECIFICATION_CONFLICT" not in message


def test_a_two_node_row_whose_coefficients_do_not_cancel_is_refused_as_structure() -> None:
    """A copy is a difference; `P_a + P_b − P_spec` is a sum (T01 review M4, register R-021).

    This row qualified as a copy under "at most two columns, every coefficient ±1", took `P_a` as
    its positive node and the constant as its negative, and would have been certified as
    `P_a − P_spec` — false at every state. K03 was never wrong about it, because the two-state
    witness sees the mismatch move by `P_b` and refuses; the test below holds that. But the
    refusal was numerical, and R-011 makes this elimination structural, so the guard now fires
    first and says what is actually wrong.
    """
    coefficients = {"p1": {"P1": 1.0}, "p2": {"P2": 1.0}, "p3": {"P1": 1.0, "P2": 1.0}}
    kinds: Mapping[str, Any] = {"P1": "pressure", "P2": "pressure"}

    def at(first: float, second: float, spec: float = 100_000.0) -> dict[str, float]:
        return {"p1": first - spec, "p2": second - spec, "p3": first + second - spec}

    with pytest.raises(UnsupportedRankStructureError) as raised:
        eliminate_alias_rows(
            row_ids=("p1", "p2", "p3"),
            coefficients=coefficients,
            column_kinds=kinds,
            residuals=[at(100_000.0, 100_000.0), at(101_000.0, 102_000.0)],
        )
    assert "do not cancel" in str(raised.value)

    # And the numerical witness would have caught it too, which is why no K03 result was wrong.
    # Removing the structural guard is what this asserts against: a genuine copy still passes.
    elimination = eliminate_alias_rows(
        row_ids=("q1", "q2", "q3"),
        coefficients={"q1": {"P1": 1.0}, "q2": {"P2": 1.0, "P1": -1.0}, "q3": {"P2": 1.0}},
        column_kinds=kinds,
        residuals=[
            {"q1": 0.0, "q2": 0.0, "q3": 0.0},
            {"q1": 1000.0, "q2": 0.0, "q3": 1000.0},
        ],
    )
    assert [row.row_id for row in elimination.eliminated] == ["q3"]
