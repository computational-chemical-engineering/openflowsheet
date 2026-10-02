"""K03 M1: scales from the registered nominals (specification §4, assertions A04/A05/A32/A34).

Scaling is the kind of thing that looks right whatever it does: a wrong scale still produces a
step, still converges on an easy problem, and only shows up as a solver that stalls on a hard
one. So the tests here are against the specification's §4.2 table entry by entry, against the
registered nominals by value, and against the failure the whole mechanism exists to prevent —
the unscaled condition number.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np
import pytest

from openflowsheet.compile.spec import EquationSpec, ProblemSpec
from openflowsheet.compiled import EvaluationContext
from openflowsheet.models.syn001.flowsheet import Syn001Flowsheet
from openflowsheet.numerics.scaling import (
    REGISTERED_NOMINALS,
    SCALE_PROVENANCE,
    ScaleUnavailableError,
    Scaling,
)
from openflowsheet.thermo.syn001 import Syn001Provider

CONTEXT = EvaluationContext(model_version="K03-scaling@" + "0" * 64, constants_sha256="0" * 64)


def flowsheet() -> Syn001Flowsheet:
    return Syn001Flowsheet(provider=Syn001Provider(), context=CONTEXT)


def test_the_registered_nominals_are_derivation_section_9s() -> None:
    """Written out: 3 mol/s, 100 K, 1e5 Pa, 1e5 W, and the flow nominal squared."""
    assert REGISTERED_NOMINALS == {
        "molar_flow": 3.0,
        "molar_flow_squared": 9.0,
        "temperature": 100.0,
        "pressure": 1.0e5,
        "heat_rate": 1.0e5,
    }
    assert REGISTERED_NOMINALS["molar_flow_squared"] == REGISTERED_NOMINALS["molar_flow"] ** 2


def test_a04_the_scales_are_the_specifications_table_entry_by_entry() -> None:
    """A04: 47 columns and 49 rows with the exact §4.2 values, and a provenance that names §9."""
    from collections import Counter

    spec = flowsheet().spec()
    scaling = Scaling.from_spec(spec)

    assert set(scaling.column) == set(spec.variable_ids)
    assert set(scaling.row) == set(spec.equation_ids)
    assert Counter(scaling.column.values()) == Counter({3.0: 31, 100.0: 7, 1.0e5: 7 + 2})
    assert Counter(scaling.row.values()) == Counter({3.0: 25, 9.0: 6, 100.0: 6, 1.0e5: 9 + 3})
    assert "SYN-001.md §9" in scaling.provenance
    assert scaling.provenance == SCALE_PROVENANCE


def test_specific_ids_get_the_scale_their_kind_implies() -> None:
    """Spot checks by name, so a permuted kind map cannot pass the count test above."""
    scaling = Scaling.from_spec(flowsheet().spec())
    assert scaling.column["S1.n.A"] == 3.0
    assert scaling.column["S3.vap.B"] == 3.0
    assert scaling.column["S3.L"] == 3.0
    assert scaling.column["S4.N"] == 3.0
    assert scaling.column["S2.T"] == 100.0
    assert scaling.column["S2.P"] == 1.0e5
    assert scaling.column["U-HEAT.Q"] == 1.0e5
    assert scaling.row["U-MIX:MIX-mole:A"] == 3.0
    assert scaling.row["U-HEAT:Vdef"] == 3.0
    assert scaling.row["U-HEAT:HEAT-equilibrium:A"] == 9.0
    assert scaling.row["U-FLASH:FLASH-equilibrium:C"] == 9.0
    assert scaling.row["U-MIX:MIX-energy"] == 1.0e5
    assert scaling.row["U-FEED:FEED-T"] == 100.0
    assert scaling.row["U-SPLIT:SPLIT-P:purge"] == 1.0e5


def test_a32_a_row_without_a_declared_kind_refuses_to_produce_a_scale() -> None:
    """A32: `SCALE_UNAVAILABLE` naming the row; the SYN-001 assembly does not trip it."""
    spec = flowsheet().spec()
    Scaling.from_spec(spec)  # the real assembly is complete

    orphan = EquationSpec(
        equation_id="U-GHOST:no-kind",
        build=lambda variables, blocks, parameters, algebra: 0.0,
        accumulation="algebraic",
        origin="ghost#no-kind",
    )
    broken = ProblemSpec(
        label=spec.label,
        variable_ids=spec.variable_ids,
        equations=(*spec.equations, orphan),
        parameter_ids=spec.parameter_ids,
        parameters=spec.parameters,
        blocks=spec.blocks,
        block_inputs=spec.block_inputs,
        variable_kinds=spec.variable_kinds,
        row_kinds=spec.row_kinds,
    )
    with pytest.raises(ScaleUnavailableError, match="U-GHOST:no-kind"):
        Scaling.from_spec(broken)


def test_a_kind_with_no_registered_nominal_is_also_refused() -> None:
    """The other half: a declared kind the nominals do not name is not a silent 1.0 either."""
    with pytest.raises(ScaleUnavailableError, match="molar_flow"):
        Scaling.from_kinds(
            variable_ids=("a",),
            equation_ids=("r",),
            variable_kinds={"a": "molar_flow"},
            row_kinds={"r": "molar_flow"},
            nominals={"temperature": 100.0},
        )


def test_a_non_positive_scale_is_refused() -> None:
    """A scale divides. Zero or negative is a division by zero or a silent sign flip."""
    with pytest.raises(ScaleUnavailableError, match="sign flip"):
        Scaling(column={"a": 0.0}, row={"r": 1.0})
    with pytest.raises(ScaleUnavailableError, match="sign flip"):
        Scaling(column={"a": 1.0}, row={"r": -3.0})


def test_a34_there_is_one_scale_segment_and_it_is_zero() -> None:
    """A34: v0.0 never refreshes, so the counter exists and is always 0."""
    assert Scaling.from_spec(flowsheet().spec()).segment == 0


def test_the_transformations_are_the_blueprints() -> None:
    """`x̂ = S_x⁻¹ x`, `F̂ = S_F⁻¹ F`, `Ĵ = S_F⁻¹ J S_x`, with `x_ref = 0`."""
    scaling = Scaling(column={"a": 2.0, "b": 5.0}, row={"r": 4.0, "s": 10.0}, kinds={})
    assert list(scaling.scale_state([6.0, 10.0], ("a", "b"))) == [3.0, 2.0]
    assert list(scaling.unscale_state([3.0, 2.0], ("a", "b"))) == [6.0, 10.0]
    assert list(scaling.scale_residual([8.0, 30.0], ("r", "s"))) == [2.0, 3.0]
    # J = [[1, 0], [0, 1]] in (r,s) x (a,b): Ĵ_ij = J_ij S_x[j] / S_F[i]
    entries = scaling.scale_jacobian_entries(
        data=[1.0, 1.0],
        row_index=[0, 1],
        column_index=[0, 1],
        row_ids=("r", "s"),
        col_ids=("a", "b"),
    )
    assert list(entries) == [2.0 / 4.0, 5.0 / 10.0]


def test_the_scaled_state_round_trips_to_one_rounding() -> None:
    """`S_x (S_x⁻¹ x) = x` to a single rounding, and exactly where the scale is a power of two.

    Not exactly in general: 3, 100 and 1e5 are not powers of two, so dividing and multiplying
    back is two roundings of which at most one survives. Measured worst relative error over the
    47 columns is one ulp. The distinction matters because a Newton step is computed scaled and
    applied unscaled, so this rounding is in the step — it is bounded, not absent, and the
    convergence test is on the *unscaled* residual for exactly that reason (specification §5).
    """
    spec = flowsheet().spec()
    scaling = Scaling.from_spec(spec)
    rng = np.random.default_rng(20260921)
    x = rng.uniform(-50.0, 50.0, len(spec.variable_ids))
    back = scaling.unscale_state(scaling.scale_state(x, spec.variable_ids), spec.variable_ids)
    assert np.max(np.abs(back - x) / np.abs(x)) <= np.finfo(float).eps
    assert not np.array_equal(back, x), (
        "if this ever becomes exact the scales have changed to powers of two, and the comment "
        "above is then wrong rather than merely conservative"
    )

    powers_of_two = Scaling(column={"a": 4.0, "b": 0.25}, row={"r": 1.0}, kinds={})
    exact = powers_of_two.unscale_state(
        powers_of_two.scale_state([6.0, 10.0], ("a", "b")), ("a", "b")
    )
    assert list(exact) == [6.0, 10.0]


def test_the_merit_function_is_half_the_squared_scaled_residual() -> None:
    scaling = Scaling(column={"a": 1.0}, row={"r": 4.0, "s": 10.0}, kinds={})
    assert scaling.merit([8.0, 30.0], ("r", "s")) == 0.5 * (2.0**2 + 3.0**2)


def test_scaling_is_what_keeps_the_jacobian_conditioned(
    reference_values: Mapping[str, Any],
) -> None:
    """The failure a silent 1.0 would hide, measured rather than asserted from the specification.

    §4.3 justifies refusing an unnamed kind by the condition number an unscaled pressure column
    against a flow row produces. That is checkable: assemble the real Jacobian at the reference
    state, and compare the 2-norm condition number of the scaled and unscaled matrices.
    """
    import sys

    sys.path.insert(0, "tests")
    import test_k02_flowsheet as reference_module

    from openflowsheet.compile.casadi_backend import compile_problem
    from openflowsheet.compile.reference import state_vector

    case = {entry["case_id"]: entry for entry in reference_values["variants"]}["SYN-001-nominal"]
    spec = reference_module.flowsheet_for(case).spec()
    state = reference_module.reference_state(case, spec)
    scaling = Scaling.from_spec(spec)

    problem = compile_problem(spec)
    metadata = problem.metadata
    context = EvaluationContext(
        model_version=metadata.model_version, constants_sha256=metadata.constants_sha256
    )
    result = problem.jacobian(np.array(state_vector(spec, state)), context)
    assert result.status == "ok"

    dense = np.zeros((len(result.row_ids), len(result.col_ids)))
    rows, columns, data = [], [], []
    for column in range(len(result.col_ids)):
        for offset in range(result.indptr[column], result.indptr[column + 1]):
            dense[result.indices[offset], column] = result.data[offset]
            rows.append(result.indices[offset])
            columns.append(column)
            data.append(result.data[offset])
    scaled_entries = scaling.scale_jacobian_entries(
        data, rows, columns, result.row_ids, result.col_ids
    )
    scaled = np.zeros_like(dense)
    for entry, row, column in zip(scaled_entries, rows, columns, strict=True):
        scaled[row, column] = entry

    unscaled_condition = float(np.linalg.cond(dense))
    scaled_condition = float(np.linalg.cond(scaled))
    assert unscaled_condition > 1e8, unscaled_condition
    assert scaled_condition < 1e5, scaled_condition
    assert unscaled_condition / scaled_condition > 1e4
