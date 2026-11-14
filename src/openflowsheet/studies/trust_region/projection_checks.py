"""The projection's checks before any solve: the structural shape check (R-278) and the
certification of the rows the alias elimination omits (R-274; M05 design note §6.1).
`studies.trust_region.projection` re-exports every public name."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final, Literal

import numpy as np
import numpy.typing as npt
from pyomo.common.collections import ComponentMap
from pyomo.core.expr.calculus.derivatives import Modes, differentiate
from pyomo.core.expr.visitor import identify_variables

from openflowsheet.compile.reference import block_outputs
from openflowsheet.compile.spec import DomainError, ProblemSpec
from openflowsheet.numerics.linear import LinearSolveFailedError, solve_linear
from openflowsheet.numerics.scaling import Scaling
from openflowsheet.orchestrator.rank import (
    EliminatedRow,
    eliminate_alias_rows,
    pressure_shifted_state,
)
from openflowsheet.studies.sensitivity import TAU_ALIAS
from openflowsheet.studies.trust_region.holders import DecisionSpec, ExternalLinkSpec
from openflowsheet.studies.trust_region.projection_support import (
    OmittedRow,
    ProjectionRefusedError,
    _float_rows,
    _RowDerivatives,
)

#: R-278: whether `project` enforces the shape check. `exempt_oracle` is TR-E1's only (test-only).
ShapeCheck = Literal["required", "exempt_oracle"]


SHAPE_CHECK_CRITERION: Final = (
    "structural perfect matching of the projected equations to every variable but the decisions, "
    "link-EF outputs fixed and property relations kept (R-278)"
)


# -- the shape check (R-278) ----------------------------------------------------------------------


@dataclass(frozen=True)
class _ShapeVerdict:
    """The shape check's result: the matching's size against the system's, and on a failure the
    refusal it raises (unless the projection is TR-E1's exempt oracle)."""

    matched: int
    size: int
    refusal: ProjectionRefusedError | None

    def as_document(self, mode: ShapeCheck) -> dict[str, Any]:
        status = "exempt_oracle" if mode == "exempt_oracle" else "pass"
        return {
            "status": status,
            "criterion": SHAPE_CHECK_CRITERION,
            "matched": self.matched,
            "size": self.size,
            "refusal": None if self.refusal is None else self.refusal.reason,
        }


def _shape_check(
    model: Any,
    spec: ProblemSpec,
    row_ids: Sequence[str],
    expressions: Sequence[Any],
    output_rows: Sequence[Mapping[str, Any]],
    links: Sequence[ExternalLinkSpec],
    projected: Sequence[int],
) -> _ShapeVerdict:
    """R-278 (module docstring): the structural incidence of the projected equations on every
    variable but the decisions, with the link-EF outputs fixed and the property relations kept,
    and whether it has a perfect matching. Called after the DOF check, so it is square. The
    unknowns are the projection's: `x` at the spec positions `projected` (R-296), `y` and `w`."""
    import scipy.sparse as sp
    from scipy.sparse.csgraph import maximum_bipartite_matching

    variable_index = {spec.variable_ids[i]: c for c, i in enumerate(projected)}
    n_x, n_y = len(projected), len(output_rows)
    link_parameters = [p for link in links for p in (link.x_param_id, link.dt_param_id)]
    unknown_names = [
        *(spec.variable_ids[i] for i in projected),
        *(f"{row['block_id']}.{row['output_id']}" for row in output_rows),
        *link_parameters,
    ]
    column = ComponentMap(
        [
            *((model.x[i], c) for c, i in enumerate(projected)),
            *((model.y[g], n_x + g) for g in range(n_y)),
            *((model.w[k], n_x + n_y + k) for k in range(len(link_parameters))),
        ]
    )
    # A row's incidence is the unknowns its expression contains; the decisions are not unknowns.
    equations: list[tuple[str, list[int]]] = [
        (name, sorted({column[v] for v in identify_variables(expression) if v in column}))
        for name, expression in zip(row_ids, expressions, strict=True)
    ]
    for g, row in enumerate(output_rows):
        feeding = spec.block_inputs[row["block_id"]]
        inputs = {variable_index[name] for name in feeding if name in variable_index}
        equations.append((f"ydef:{row['block_id']}.{row['output_id']}", sorted({n_x + g, *inputs})))
    for k, parameter in enumerate(link_parameters):
        equations.append((f"link:{parameter}", [n_x + n_y + k]))

    size = len(unknown_names)
    if len(equations) != size:  # the DOF check guarantees it; a defect otherwise
        raise AssertionError(f"shape check: {len(equations)} equations, {size} unknowns")
    rows = [r for r, (_, columns) in enumerate(equations) for _ in columns]
    columns = [c for _, cols in equations for c in cols]
    incidence = sp.csr_matrix(
        (np.ones(len(rows), dtype=np.int8), (rows, columns)), shape=(size, size)
    )
    row_match = maximum_bipartite_matching(incidence, perm_type="column")
    matched = int(np.count_nonzero(row_match >= 0))
    if matched == size:
        return _ShapeVerdict(matched, size, None)

    column_match = np.full(size, -1, dtype=np.int64)
    for r, c in enumerate(row_match):
        if c >= 0:
            column_match[c] = r
    incident: list[list[int]] = [[] for _ in range(size)]
    for r, (_, cols) in enumerate(equations):
        for c in cols:
            incident[c].append(r)
    # Alternating paths from the unmatched variables: variable → any incident equation → the
    # variable that equation is matched to. What they reach is the under-determined block.
    undetermined = {c for c in range(size) if column_match[c] < 0}
    frontier = sorted(undetermined)
    while frontier:
        reached = []
        for c in frontier:
            for r in incident[c]:
                partner = int(row_match[r])
                if partner >= 0 and partner not in undetermined:
                    undetermined.add(partner)
                    reached.append(partner)
        frontier = reached
    link_inputs = {name for link in links for name in link.inlet_variable_ids}
    under = [unknown_names[c] for c in sorted(undetermined)]
    flagged = [name for name in under if name in link_inputs]
    unmatched_equations = [equations[r][0] for r in range(size) if row_match[r] < 0]
    unmatched_variables = [unknown_names[c] for c in range(size) if column_match[c] < 0]
    refusal = ProjectionRefusedError(
        "PROJECTION_IMPLICIT_EF_INPUT",
        ",".join(under),
        f"with the decisions and the link-EF outputs fixed, a maximum matching pairs {matched} of "
        f"the {size} equations and unknowns; unmatched equations {unmatched_equations}, unmatched "
        f"variables {unmatched_variables}; structurally undetermined variables {under}, of which "
        f"link-EF inputs {flagged}",
    )
    return _ShapeVerdict(matched, size, refusal)


# -- the omitted rows (R-274) ---------------------------------------------------------------------


def _row_derivatives(
    model: Any,
    spec: ProblemSpec,
    x0: Mapping[str, float],
    built: Mapping[str, Any],
    n_outputs: int,
    n_decisions: int,
) -> _RowDerivatives:
    """Pyomo's reverse-mode derivatives of every row in `x`, `y` and `d`, at the model's start
    values, with ∂y/∂x from each block's own Jacobian at x₀ (the block called directly, never
    through a holder, and only when some row depends on its outputs)."""
    n_x = len(spec.variable_ids)
    wrt = [
        *(model.x[i] for i in range(n_x)),
        *(model.y[g] for g in range(n_outputs)),
        *(model.d[j] for j in range(n_decisions)),
    ]
    gradients = np.array(
        [
            differentiate(built[name], wrt_list=wrt, mode=Modes.reverse_numeric)
            for name in spec.equation_ids
        ],
        dtype=np.float64,
    ).reshape(len(spec.equation_ids), len(wrt))
    by_y = gradients[:, n_x : n_x + n_outputs]
    dy_dx = np.zeros((n_outputs, n_x))
    index = {name: i for i, name in enumerate(spec.variable_ids)}
    first = 0
    for block in spec.blocks:
        count = len(block.output_ids)
        if np.any(by_y[:, first : first + count] != 0.0):
            feeding = spec.block_inputs[block.block_id]
            for row, column, value in block.jacobian([float(x0[name]) for name in feeding]):
                dy_dx[first + row, index[feeding[column]]] += float(value)
        first += count
    return _RowDerivatives(
        x=gradients[:, :n_x] + by_y @ dy_dx, d=gradients[:, n_x + n_outputs :].copy()
    )


def _eliminate(
    spec: ProblemSpec,
    x0: Mapping[str, float],
    outputs_x0: Mapping[str, float],
    jacobian_x: npt.NDArray[np.float64],
    domain: Mapping[str, tuple[float, float]],
) -> tuple[tuple[EliminatedRow, ...], dict[str, float]]:
    """R-274's facts 1 and 2: `eliminate_alias_rows` on every row, with the certificate's inputs —
    the rows' Jacobian by column id, the variable kinds, and the residuals (with the pinned
    parameters) at x₀ and at its pressure-shifted witness state — then each eliminated row's
    residual at x₀ within the elimination's tolerance. Returns the eliminated rows and every
    row's residual at x₀."""
    state = {name: float(x0[name]) for name in spec.variable_ids}
    at_x0 = _float_rows(spec, state, outputs_x0, spec.parameters)
    reason = ""
    second = at_x0
    if any(spec.variable_kinds.get(name) == "pressure" for name in spec.variable_ids):
        shifted, reason = pressure_shifted_state(
            spec.variable_ids, spec.variable_kinds, state, domain["pressure"]
        )
        if not reason:
            try:
                second = _float_rows(spec, shifted, block_outputs(spec, shifted), spec.parameters)
            except DomainError:
                reason = "shifted_state_property_domain_error"
    coefficients = {
        name: {
            column: float(value)
            for column, value in zip(spec.variable_ids, jacobian_x[i], strict=True)
            if value != 0.0
        }
        for i, name in enumerate(spec.equation_ids)
    }
    elimination = eliminate_alias_rows(
        row_ids=spec.equation_ids,
        coefficients=coefficients,
        column_kinds=spec.variable_kinds,
        residuals=[at_x0, second],
    )
    for row in elimination.eliminated:
        if reason:
            raise ProjectionRefusedError(
                "PROJECTION_OMITTED_ROW_UNCERTIFIED",
                row.row_id,
                f"the elimination's second state could not be built ({reason}), so the constancy "
                "of its mismatch is not witnessed",
            )
        if not abs(at_x0[row.row_id]) <= row.tolerance:
            raise ProjectionRefusedError(
                "PROJECTION_OMITTED_ROW_UNCERTIFIED",
                row.row_id,
                f"its residual at x0 is {at_x0[row.row_id]!r}, beyond the elimination's "
                f"pressure_tolerance {row.tolerance:g}",
            )
    return elimination.eliminated, at_x0


def _certify(
    spec: ProblemSpec,
    scaling: Scaling,
    decisions: Sequence[DecisionSpec],
    eliminated: Sequence[EliminatedRow],
    residuals_x0: Mapping[str, float],
    derivatives: _RowDerivatives,
) -> tuple[OmittedRow, ...]:
    """R-274's fact 3, M03's Q3 in the projection's scales: Ĵ_K X̂ = −F̂_d,K at x₀ (one ADR 0004
    solve for every decision), and every decision's tangent residual Ĵ_E X̂ + F̂_d,E on each
    eliminated row within τ_alias. Called after the DOF check, so Ĵ_K is square."""
    if not eliminated:
        return ()
    position = {name: i for i, name in enumerate(spec.equation_ids)}
    removed = [row.row_id for row in eliminated]
    kept = [name for name in spec.equation_ids if name not in set(removed)]
    column_scales = scaling.column_vector(spec.variable_ids)

    def scaled(
        rows: Sequence[str],
    ) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
        at = [position[name] for name in rows]
        row_scales = scaling.row_vector(rows)[:, None]
        return (
            derivatives.x[at] * column_scales[None, :] / row_scales,
            derivatives.d[at] / row_scales,
        )

    tangent: npt.NDArray[np.float64] = np.zeros((len(removed), len(decisions)))
    if decisions:
        j_kept, d_kept = scaled(kept)
        j_removed, d_removed = scaled(removed)
        try:
            solution, _ = solve_linear(j_kept, -d_kept)
        except LinearSolveFailedError as error:
            raise ProjectionRefusedError(
                "PROJECTION_OMITTED_ROW_UNCERTIFIED",
                removed[0],
                f"the tangent of the retained rows at x0 is not defined: {error}",
            ) from error
        tangent = j_removed @ solution.reshape(len(kept), len(decisions)) + d_removed
    origins = {equation.equation_id: equation.origin for equation in spec.equations}
    certified = []
    for i, row in enumerate(eliminated):
        residuals = {
            decision.parameter_id: float(tangent[i, j]) for j, decision in enumerate(decisions)
        }
        over = sorted(name for name, value in residuals.items() if not abs(value) <= TAU_ALIAS)
        if over:
            raise ProjectionRefusedError(
                "PROJECTION_OMITTED_ROW_UNCERTIFIED",
                row.row_id,
                f"the tangent residual of decisions {over} on it exceeds tau_alias "
                f"{TAU_ALIAS:g}: {residuals}",
            )
        certified.append(OmittedRow(row, origins[row.row_id], residuals_x0[row.row_id], residuals))
    return tuple(certified)
