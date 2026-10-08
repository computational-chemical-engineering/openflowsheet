"""M05 WO-2: the projection compiler against the CasADi compiled problem — gate G4's TR-E1 and
SYN-001 parts (design note §6.1-§6.2, §13; ADR 0038 D2).

G4 at each registered state: (a) the source map is a bijection on every category and TRF's DOF
count equals the number of decisions; (b) every projected row's value agrees with CasADi's within
1e-12 · max(1, |r|/row_scale) scaled; (c) every x-Jacobian entry — the row's own derivative chained
through the block outputs' defining constraints, i.e. the derivative of the function CasADi
compiles — within 1e-10 · (|J| + row_scale/column_scale); (d) every decision column within
1e-7 · (|J| + row_scale) of a central difference of CasADi's residual (the test oracle, h = 1e-6
scaled); (e) no nonsmooth node. The CasADi side is M03's parametric twin, which is bitwise the
base compiled problem (M03 A01) with the decisions symbolic.

Every test here is marked `nlp`: Pyomo exists only in the audited environment
(`scripts/m03_nlp_check.sh`). Nothing at module level imports it.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from typing import Any

import numpy as np
import numpy.typing as npt
import pytest
from m05_support import (
    TR_E1_DECISIONS,
    TR_E1_START,
    SineBlock,
    tr_e1_objective_build,
    tr_e1_projection,
    tr_e1_spec,
)

from openflowsheet.compile.casadi_backend import TwinMatrix, compile_parametric_twin
from openflowsheet.compile.spec import EquationSpec, Expr, ProblemSpec

pytestmark = pytest.mark.nlp

RESIDUAL_TOLERANCE = 1e-12
JACOBIAN_TOLERANCE = 1e-10
DECISION_TOLERANCE = 1e-7
FD_STEP = 1e-6


def dense(matrix: TwinMatrix) -> npt.NDArray[np.float64]:
    out = np.zeros((len(matrix.row_ids), len(matrix.col_ids)))
    for column in range(len(matrix.col_ids)):
        for position in range(matrix.indptr[column], matrix.indptr[column + 1]):
            out[matrix.indices[position], column] = matrix.data[position]
    return out


def structure(projection: Any) -> None:
    """G4 (a) and (e): the source map's bijections, TRF's DOF count, one node per EF, and no
    nonsmooth node."""
    import pyomo.environ as pyo
    from pyomo.core.expr.numeric_expr import ExternalFunctionExpression

    from openflowsheet.studies.trust_region.projection import find_nonsmooth_node

    spec: ProblemSpec = projection.spec
    model = projection.model
    source = projection.source_map
    decision_ids = tuple(d.parameter_id for d in projection.decisions)

    # (a) bijections, and the DOF TRF will count.
    assert [v["variable_id"] for v in source["variables"]] == list(spec.variable_ids)
    assert [v["pyomo"] for v in source["variables"]] == [
        f"x[{i}]" for i in range(len(spec.variable_ids))
    ]
    assert [r["equation_id"] for r in source["rows"]] == list(projection.row_ids)
    assert len(set(projection.row_ids)) == len(projection.row_ids)
    assert set(projection.row_ids) <= set(spec.equation_ids)
    pairs = [(b["block_id"], b["output_id"]) for b in source["block_outputs"]]
    assert pairs == [(b.block_id, o) for b in spec.blocks for o in b.output_ids]
    assert [d["parameter_id"] for d in source["decisions"]] == list(decision_ids)
    efs = [b["ef"] for b in source["block_outputs"]] + [e["ef"] for e in source["external_links"]]
    assert sorted(efs) == sorted(projection.ef_names.values()) and len(set(efs)) == len(efs)
    variables: set[int] = set()
    equalities = 0
    ef_nodes: Counter[str] = Counter()
    for constraint in model.component_data_objects(pyo.Constraint, active=True):
        variables.update(id(v) for v in pyo.expr.identify_variables(constraint.expr))
        equalities += int(constraint.equality)
        stack = [constraint.expr]
        while stack:
            node = stack.pop()
            if isinstance(node, ExternalFunctionExpression):
                ef_nodes[projection.ef_names[node._fcn._fcn]] += 1
            if hasattr(node, "is_expression_type") and node.is_expression_type():
                stack.extend(node.args)
    assert len(variables) - equalities == len(decision_ids)
    assert ef_nodes == Counter(efs)  # every EF in exactly one node

    # (e) no nonsmooth node.
    for expression in projection.row_expressions:
        assert find_nonsmooth_node(expression) is None


def equivalence(projection: Any, x0: Mapping[str, float]) -> dict[str, float]:
    """G4 (a)-(e) for one projection at its start; returns the worst measured ratios.

    The row and column scales are the projection's own (R-275): K03's `Scaling.from_spec`, or
    unit scales for a spec without kinds — the scales its Ipopt suffixes carry."""
    import pyomo.environ as pyo
    from pyomo.core.expr.calculus.derivatives import Modes, differentiate

    structure(projection)
    spec: ProblemSpec = projection.spec
    model = projection.model
    source = projection.source_map
    decision_ids = tuple(d.parameter_id for d in projection.decisions)

    # The CasADi side, at the parameters the Pyomo model stands for (c + h·d₀, in binary64).
    twin = compile_parametric_twin(spec, decision_ids)
    parameters = projection.decision_parameters()
    x = np.array([float(x0[name]) for name in spec.variable_ids])
    residual = np.array(twin.residual(x, parameters))
    jacobian_x = dense(twin.jacobian_x(x, parameters))
    rows = [spec.equation_ids.index(name) for name in projection.row_ids]
    row_scales = projection.scaling.row_vector(projection.row_ids)
    column_scales = projection.scaling.column_vector(spec.variable_ids)

    # (b) residuals.
    pyomo_rows = np.array([float(pyo.value(e)) for e in projection.row_expressions])
    casadi_rows = residual[rows]
    scaled = np.abs(pyomo_rows - casadi_rows) / row_scales
    allowed = RESIDUAL_TOLERANCE * np.maximum(1.0, np.abs(casadi_rows) / row_scales)
    assert np.all(scaled <= allowed), np.max(scaled / allowed)

    # (c) the x-Jacobian: ∂r/∂x + ∂r/∂y · ∂y/∂x, with ∂y/∂x from y = s · EF(inputs).
    xs = [model.x[i] for i in range(len(spec.variable_ids))]
    ys = [model.y[g] for g in range(len(source["block_outputs"]))]
    dy_dx = np.zeros((len(ys), len(xs)))
    for g in range(len(ys)):
        left, right = model.ydef[g].expr.args
        assert left is model.y[g]
        dy_dx[g] = differentiate(right, wrt_list=xs, mode=Modes.reverse_numeric)
    pyomo_jacobian = np.zeros((len(rows), len(xs)))
    for i, expression in enumerate(projection.row_expressions):
        gradient = differentiate(expression, wrt_list=xs + ys, mode=Modes.reverse_numeric)
        pyomo_jacobian[i] = np.array(gradient[: len(xs)]) + np.array(gradient[len(xs) :]) @ dy_dx
    casadi_jacobian = jacobian_x[rows]
    j_scale = row_scales[:, None] / column_scales[None, :]
    allowed_j = JACOBIAN_TOLERANCE * (np.abs(casadi_jacobian) + j_scale)
    jacobian_error = np.abs(pyomo_jacobian - casadi_jacobian)
    assert np.all(jacobian_error <= allowed_j), np.max(jacobian_error / allowed_j)

    # (d) decision columns against a central difference of CasADi's residual.
    ds = projection.decision_variables
    pyomo_decisions = np.array(
        [
            differentiate(e, wrt_list=ds, mode=Modes.reverse_numeric)
            for e in projection.row_expressions
        ]
    )
    fd = np.zeros_like(pyomo_decisions)
    for j, name in enumerate(decision_ids):
        step = projection.half_widths[j] * FD_STEP
        plus = twin.residual(x, {**parameters, name: parameters[name] + step})
        minus = twin.residual(x, {**parameters, name: parameters[name] - step})
        fd[:, j] = (np.array(plus)[rows] - np.array(minus)[rows]) / (2.0 * FD_STEP)
    allowed_d = DECISION_TOLERANCE * (np.abs(fd) + row_scales[:, None])
    decision_error = np.abs(pyomo_decisions - fd)
    assert np.all(decision_error <= allowed_d), np.max(decision_error / allowed_d)

    return {
        "residual_abs_max": float(np.max(np.abs(pyomo_rows - casadi_rows))),
        "residual": float(np.max(scaled / allowed)),
        "jacobian": float(np.max(jacobian_error / allowed_j)),
        "decision": float(np.max(decision_error / allowed_d)),
        "residual_bitwise": float(np.all(pyomo_rows == casadi_rows)),
    }


# -- TR-E1 ----------------------------------------------------------------------------------------


def test_g4_tr_e1_at_its_start(record_property: Any) -> None:
    projection = tr_e1_projection()
    measured = equivalence(projection, TR_E1_START)
    for name, value in measured.items():
        record_property(f"M05.G4.tr-e1.{name}", value)
    assert projection.source_map["decisions"][0] == {
        "pyomo_var": "d[0]",
        "parameter_id": "z0",
        "center": 0.0,
        "half_width": 1.0,
        "lower": None,
        "upper": None,
    }
    assert projection.decision_parameters() == {"z0": 2.0, "z1": 2.0, "z2": 2.0}


def test_the_source_map_is_canonical_and_reproducible() -> None:
    first, second = tr_e1_projection(), tr_e1_projection()
    assert first.source_map == second.source_map
    assert first.source_map_sha256 == second.source_map_sha256
    assert first.source_map["schema_version"] == "projection-source-map-v1"
    assert first.source_map["trf"] == []
    assert first.source_map["problem"]["model_version"].startswith("M05-TR-E1-eason-example-1@")


def test_the_projection_does_not_call_the_holders() -> None:
    """Start values and scales come from the blocks directly: a holder's ledger is TRF's alone."""
    block = SineBlock()
    projection = tr_e1_projection(block)
    assert block.value_calls == 1
    assert all(holder.ledger == () for holder in projection.holders)


# -- the output scale -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0.0, 2.0**-19),
        (1e-6, 2.0**-19),
        (0.5, 0.5),
        (0.84, 1.0),
        (1.0, 1.0),
        (-90.0, 128.0),
        (128.0, 128.0),
        (128.00000000000003, 256.0),
        (-3e7, 2.0**25),
    ],  # fmt: skip
)
def test_the_output_scale_is_the_next_power_of_two(value: float, expected: float) -> None:
    from openflowsheet.studies.trust_region.projection import output_scale

    assert output_scale(value) == expected


# -- the scales (R-275) ---------------------------------------------------------------------------


def suffix(projection: Any) -> tuple[list[float], list[float]]:
    """The Ipopt `scaling_factor` suffix of every `x` and every projected row."""
    model = projection.model
    factors = model.scaling_factor
    return (
        [factors[model.x[i]] for i in range(len(projection.spec.variable_ids))],
        [factors[model.row[i]] for i in range(len(projection.row_ids))],
    )


def test_a_spec_without_kinds_is_projected_with_unit_scales_and_says_so() -> None:
    projection = tr_e1_projection()
    assert projection.scaling.provenance == "unit_no_kinds"
    assert projection.source_map["scale_provenance"] == "unit_no_kinds"
    assert [v["column_scale"] for v in projection.source_map["variables"]] == [1.0, 1.0]
    assert [r["row_scale"] for r in projection.source_map["rows"]] == [1.0, 1.0]
    assert suffix(projection) == ([1.0, 1.0], [1.0, 1.0])


def test_a_spec_without_kinds_ignores_its_own_scales() -> None:
    """`ProblemSpec.row_scales` and `column_scales` are never read (R-275)."""
    from openflowsheet.studies.trust_region.projection import DecisionSpec, ObjectiveSpec, project

    base = tr_e1_spec()
    spec = ProblemSpec(**{**base.__dict__, "row_scales": {"c1": 8.0}, "column_scales": {"x0": 4.0}})
    projection = project(
        spec,
        TR_E1_START,
        decisions=[DecisionSpec(name, None, None) for name in TR_E1_DECISIONS],
        objective=ObjectiveSpec("tr-e1-objective", "minimize", tr_e1_objective_build, 1.0),
        domain={},
    )
    assert suffix(projection) == ([1.0, 1.0], [1.0, 1.0])
    assert projection.source_map == tr_e1_projection().source_map


def test_a_spec_with_partial_kinds_is_refused() -> None:
    from openflowsheet.studies.trust_region.projection import ProjectionRefusedError

    base = tr_e1_spec()
    with pytest.raises(ProjectionRefusedError) as refused:
        tr_e1_variant(
            variable_kinds={"x0": "temperature", "x1": "no_such_kind"},
            row_kinds={"c1": "heat_rate"},
        )
    assert refused.value.reason == "PROJECTION_SCALES_UNAVAILABLE(x1,c2)"
    assert base.variable_kinds == {}  # TR-E1 itself declares none


def test_syn001_is_projected_in_k03s_scales() -> None:
    """The suffixes and the source map carry K03's `Scaling.from_spec`, and nothing else."""
    from openflowsheet.numerics.scaling import SCALE_PROVENANCE, Scaling

    projection, _ = syn001_projection("P1", omitted_rows=syn001_alias_rows("P1"))
    spec = projection.spec
    k03 = Scaling.from_spec(spec)
    assert projection.scaling == k03
    source = projection.source_map
    assert source["scale_provenance"] == SCALE_PROVENANCE
    assert [v["column_scale"] for v in source["variables"]] == [
        k03.column[name] for name in spec.variable_ids
    ]
    assert [r["row_scale"] for r in source["rows"]] == [
        k03.row[name] for name in projection.row_ids
    ]
    columns, rows = suffix(projection)
    assert columns == [1.0 / k03.column[name] for name in spec.variable_ids]
    assert rows == [1.0 / k03.row[name] for name in projection.row_ids]
    assert set(columns) != {1.0} and set(rows) != {1.0}


# -- refusals (§6.1) ------------------------------------------------------------------------------


def tr_e1_variant(**changes: Any) -> Any:
    """TR-E1's spec with rows or parameters replaced, projected with `decisions`."""
    from openflowsheet.studies.trust_region.projection import (
        DecisionSpec,
        ObjectiveSpec,
        project,
    )

    base = tr_e1_spec()
    decisions = changes.pop("decisions", TR_E1_DECISIONS)
    spec = ProblemSpec(**{**base.__dict__, **changes})
    return project(
        spec,
        TR_E1_START,
        decisions=[DecisionSpec(name, None, None) for name in decisions],
        objective=ObjectiveSpec("tr-e1-objective", "minimize", tr_e1_objective_build, 1.0),
        domain={},
    )


def row(name: str, build: Any) -> EquationSpec:
    return EquationSpec(name, build, "algebraic", "test")


def c1(v: Mapping[str, Expr], b: Mapping[str, Expr], p: Mapping[str, Any], a: Any) -> Expr:
    return tr_e1_spec().equations[0].build(v, b, p, a)


def test_a_builder_that_branches_on_a_decision_is_not_differentiable() -> None:
    from openflowsheet.studies.trust_region.projection import ProjectionRefusedError

    def branching(
        v: Mapping[str, Expr], b: Mapping[str, Expr], p: Mapping[str, Any], a: Any
    ) -> Expr:
        scale = 2.0 if p["z1"] > 0.0 else 1.0
        return p["z2"] ** 4 * p["z1"] ** 2 + scale * p["z1"] - 8.0

    with pytest.raises(ProjectionRefusedError) as refused:
        tr_e1_variant(equations=(row("c1", c1), row("c2-branching", branching)))
    assert refused.value.reason == "PARAMETER_NOT_DIFFERENTIABLE(c2-branching)"


def test_a_builder_that_fails_on_floats_too_is_a_defect_not_a_refusal() -> None:
    def broken(v: Mapping[str, Expr], b: Mapping[str, Expr], p: Mapping[str, Any], a: Any) -> Expr:
        raise KeyError("no such symbol")

    with pytest.raises(KeyError, match="no such symbol"):
        tr_e1_variant(equations=(row("c1", c1), row("c2", broken)))


def test_a_nonsmooth_row_is_refused() -> None:
    from openflowsheet.studies.trust_region.projection import ProjectionRefusedError

    def kinked(v: Mapping[str, Expr], b: Mapping[str, Expr], p: Mapping[str, Any], a: Any) -> Expr:
        return abs(v["x1"]) * p["z2"] ** 4 * p["z1"] ** 2 + p["z1"] - 8.0

    with pytest.raises(ProjectionRefusedError) as refused:
        tr_e1_variant(equations=(row("c1", c1), row("c2-abs", kinked)))
    assert refused.value.reason == "PROJECTION_NONSMOOTH(c2-abs)"


def test_a_decision_in_no_constraint_is_a_structure_refusal() -> None:
    from openflowsheet.studies.trust_region.projection import ProjectionRefusedError

    base = tr_e1_spec()
    with pytest.raises(ProjectionRefusedError) as refused:
        tr_e1_variant(
            parameter_ids=(*base.parameter_ids, "z3"),
            parameters={**base.parameters, "z3": 1.0},
            decisions=(*TR_E1_DECISIONS, "z3"),
        )
    assert refused.value.reason == "PROJECTION_STRUCTURE(z3)"


def test_a_row_with_no_variable_is_a_structure_refusal() -> None:
    from openflowsheet.studies.trust_region.projection import ProjectionRefusedError

    def constant(
        v: Mapping[str, Expr], b: Mapping[str, Expr], p: Mapping[str, Any], a: Any
    ) -> Expr:
        return p["z1"] - 2.0

    with pytest.raises(ProjectionRefusedError) as refused:
        tr_e1_variant(equations=(row("c1", c1), row("c2-constant", constant)), decisions=("z0",))
    assert refused.value.reason == "PROJECTION_STRUCTURE(c2-constant)"


def test_a_dof_count_other_than_the_decisions_is_refused() -> None:
    from openflowsheet.studies.trust_region.projection import ProjectionRefusedError

    def pin(v: Mapping[str, Expr], b: Mapping[str, Expr], p: Mapping[str, Any], a: Any) -> Expr:
        return v["x1"] - 1.0

    base = tr_e1_spec()
    with pytest.raises(ProjectionRefusedError) as refused:
        tr_e1_variant(equations=(*base.equations, row("c3", pin)))
    assert refused.value.reason == "PROJECTION_DOF(2)"


# -- SYN-001 --------------------------------------------------------------------------------------


def syn001_projection(state: str, **options: Any) -> tuple[Any, Mapping[str, float]]:
    """SYN-001 at an M03 registered state with M05's G4 configuration (`m05_support`)."""
    from m03_support import solved
    from m05_support import (
        SYN001_DECISION_BOX,
        nlp1_objective_build,
        nlp1_recovery_build,
    )

    from openflowsheet.studies.trust_region.projection import (
        DecisionSpec,
        InequalitySpec,
        ObjectiveSpec,
        project,
    )
    from openflowsheet.thermo.syn001 import Syn001Provider

    sheet, result = solved(state)
    assert result.final_state is not None
    declared = Syn001Provider().describe().domain
    projection = project(
        sheet.spec(),
        result.final_state,
        decisions=[DecisionSpec(name, *box) for name, box in SYN001_DECISION_BOX.items()],
        objective=ObjectiveSpec("nlp-1-objective", "minimize", nlp1_objective_build, 1.0),
        inequalities=[
            InequalitySpec("recovery_A", nlp1_recovery_build, 0.0, "M03 NLP-1", 1e-6, ">=")
        ],
        domain={"temperature": declared["T"], "pressure": declared["P"]},
        **options,
    )
    return projection, result.final_state


def test_syn001_with_every_row_is_refused_for_its_redundant_pressure_rows() -> None:
    """SYN-001's 49 rows over 47 variables include two pressure alias rows that the retained rows
    imply (the orchestrator's certified alias elimination, `orchestrator/rank.py`; M03's
    `FullSpaceNlp` keeps only the retained rows). Projected with every row, TRF's DOF count is
    5 − 2 = 3, not the 5 decisions, and the projection says so, typed, before any run."""
    from openflowsheet.studies.trust_region.projection import ProjectionRefusedError

    with pytest.raises(ProjectionRefusedError) as refused:
        syn001_projection("P1")
    assert refused.value.reason == "PROJECTION_DOF(3)"


#: The reason recorded for SYN-001's omitted rows.
ALIAS_REASON = "pressure alias row implied by the retained rows (orchestrator alias elimination)"


def syn001_alias_rows(state: str) -> dict[str, str]:
    """The rows the orchestrator's certified alias elimination removes at `state` (M03's
    `FullSpaceNlp` leaves exactly these out of its equality constraints)."""
    from m03_support import solved

    from openflowsheet.orchestrator.tear import Syn001TearProblem

    sheet, _ = solved(state)
    eliminated = Syn001TearProblem(sheet).partition.elimination.eliminated
    return {row.row_id: ALIAS_REASON for row in eliminated}


@pytest.mark.parametrize("state", ["P1", "P2", "P3", "B1", "B2", "B3"])
def test_syn001_without_its_alias_rows_projects_with_dof_equal_to_the_decisions(state: str) -> None:
    """G4 (a) and (e) at M03's registered states: the source map is a bijection, the two alias
    rows are recorded as omitted with their reason, TRF's DOF count is the 5 decisions, and no
    projected expression has a nonsmooth node."""
    omitted = syn001_alias_rows(state)
    assert sorted(omitted) == ["U-FLASH:FLASH-P:inlet", "U-SPLIT:SPLIT-P:recycle"]
    projection, x0 = syn001_projection(state, omitted_rows=omitted)
    structure(projection)
    source = projection.source_map
    assert [row["equation_id"] for row in source["omitted_rows"]] == sorted(omitted)
    assert all(row["reason"] == ALIAS_REASON for row in source["omitted_rows"])
    assert len(source["rows"]) == len(projection.spec.equations) - 2
    assert len(source["decisions"]) == 5
    # Bounds: the provider's T and P domain, flows ≥ 0 except those exactly 0.0 at x₀.
    for entry in source["variables"]:
        if entry["kind"] == "molar_flow":
            expected = [None, None] if x0[entry["variable_id"]] == 0.0 else [0.0, None]
            assert entry["bounds"] == expected, entry
        elif entry["kind"] == "temperature":
            assert entry["bounds"] == [280.0, 440.0]
        elif entry["kind"] == "pressure":
            assert entry["bounds"] == [50_000.0, 200_000.0]
        else:
            assert entry["bounds"] == [None, None]


@pytest.mark.parametrize("state", ["P1", "P2", "P3", "B1", "B2", "B3"])
def test_g4_syn001_at_the_registered_states(state: str, record_property: Any) -> None:
    """G4 (a)-(e) at M03's registered states, judged in the projection's scales, which are K03's
    registered nominals for SYN-001's declared kinds (R-275; `Scaling.from_spec`, as M03's
    full-space NLP and the certificate's root test use). The heat-rate rows sum terms of order
    1e4-1e5 W, so the two evaluation orders differ by a few ulps of those terms — measured up to
    2.2e-11 W absolute at P2 — which is 2.2e-16 in the registered 1e5 W scale and above 1e-12
    only in watts."""
    projection, x0 = syn001_projection(state, omitted_rows=syn001_alias_rows(state))
    measured = equivalence(projection, x0)
    for name, value in measured.items():
        record_property(f"M05.G4.syn001.{state}.{name}", value)


def test_an_unknown_omitted_row_is_refused() -> None:
    with pytest.raises(ValueError, match="not equations"):
        syn001_projection("P1", omitted_rows={"no-such-row": "test"})
