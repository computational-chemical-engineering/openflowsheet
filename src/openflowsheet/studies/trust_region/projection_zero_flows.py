"""The projection's exact-zero flows: the flows exactly 0.0 at x₀, eliminated with their pins,
single or in joint blocks (R-296, R-326; M05 design note §17.1, §18.1).
`studies.trust_region.projection` re-exports every public name."""

from __future__ import annotations

from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final

import numpy as np
import numpy.typing as npt
from pyomo.common.collections import ComponentMap
from pyomo.core.expr.calculus.derivatives import Modes, differentiate
from pyomo.core.expr.visitor import identify_variables

from openflowsheet.canonical import normalize_zero
from openflowsheet.compile.spec import ProblemSpec
from openflowsheet.numerics.scaling import Scaling
from openflowsheet.studies.trust_region.holders import DecisionSpec, EFHolder, ExternalLinkSpec
from openflowsheet.studies.trust_region.projection_support import (
    ProjectionRefusedError,
    _float_rows,
    _RowDerivatives,
)

#: R-326 (b): a joint block's least scaled σ_min/σ_max (§18.1; F-12: not moved to fit a block).
JOINT_RCOND_MIN: Final = 1e-10


#: R-326 (c): the persistence states' relative move, and G4's seed, whose draw ξ it uses.
JOINT_PERTURBATION: Final = 1e-3


JOINT_SEED: Final = 20261009


@dataclass(frozen=True)
class ZeroEliminated:
    """A flow exactly 0.0 at x₀ that is not a variable of the projection but the constant +0.0,
    eliminated together with the row that pins it (R-296): its pin's residual and its derivative
    in the flow at x₀ (criteria (i) and (ii)). A flow a certified block pins jointly (R-326) has
    no pin of its own: its pin fields are None and `block` is its `ZeroBlock`'s number."""

    variable_id: str
    row_id: str | None
    residual_x0: float | None
    dr_dx: float | None
    block: int | None = None

    def as_document(self) -> dict[str, Any]:
        document: dict[str, Any] = {
            "variable_id": self.variable_id,
            "row_id": self.row_id,
            "residual_x0": self.residual_x0,
            "dr_dx": self.dr_dx,
        }
        if self.block is not None:
            document["block"] = self.block
        return document


@dataclass(frozen=True)
class ZeroBlock:
    """A square block of kept rows that pins zero flows jointly (`M05-zero-flow-v2`, R-326): its
    variables in variable order, its rows in spec order with their residuals at x₀, the scaled
    block's σ_min/σ_max, and the largest |r_e| at the two persistence states (0.0 when
    certified)."""

    block: int
    variables: tuple[str, ...]
    rows: tuple[str, ...]
    residuals_x0: tuple[float, ...]
    rcond: float
    persistence_max_abs: float

    def as_document(self) -> dict[str, Any]:
        return {
            "block": self.block,
            "variables": list(self.variables),
            "rows": list(self.rows),
            "residuals_x0": list(self.residuals_x0),
            "rcond": self.rcond,
            "persistence_max_abs": self.persistence_max_abs,
        }


@dataclass
class _Assembly:
    """§6.1 steps 1-4 and every row's expression (not yet a constraint): the model with its
    variables, decisions, links and blocks, built with the eliminated zero flows (§17.1) as the
    constant +0.0."""

    model: Any
    bounds: list[tuple[float | None, float | None]]
    centers: list[float]
    half_widths: list[float]
    holders: list[EFHolder]
    holder_inputs: list[tuple[int, ...]]
    ef_names: dict[Callable[..., float], str]
    link_rows: list[dict[str, Any]]
    link_scales: list[float]
    output_rows: list[dict[str, Any]]
    output_starts: list[float]
    output_scales: list[float]
    symbols: dict[str, Any]
    block_outputs: dict[str, Any]
    parameters: dict[str, Any]
    #: Every row's expression by equation id, but those in `skip` (the zero-flow pins).
    built: dict[str, Any]


# -- the exact-zero flows (R-296) -----------------------------------------------------------------


def _eliminate_zero_flows(
    spec: ProblemSpec,
    x0: Mapping[str, float],
    assembly: _Assembly,
    omitted: Collection[str],
    residuals_x0: Mapping[str, float],
    derivatives: _RowDerivatives,
    links: Sequence[ExternalLinkSpec],
    scaling: Scaling,
    decisions: Sequence[DecisionSpec],
) -> tuple[tuple[ZeroEliminated, ...], tuple[ZeroBlock, ...]]:
    """`M05-zero-flow-v2` (module docstring) on the model with every variable: the candidates
    Z₀; §17.1's single pins, found by repeated passes over the kept rows in spec order; §18.1's
    joint stage on the flows they leave, alternating with the passes until neither adds anything;
    and the refusals. Returns the eliminated flows in variable order and the certified blocks."""
    variable_ids = spec.variable_ids
    candidates = [
        name
        for name in variable_ids
        if spec.variable_kinds.get(name) == "molar_flow" and float(x0[name]) == 0.0
    ]
    if not candidates:
        return (), ()
    model = assembly.model
    # A row's structural incidence: the unknowns of the shape check (x, y, w) its expression
    # contains — never the decisions, whose derivative is criterion (iii).
    unknowns = {
        **{name: model.x[i] for i, name in enumerate(variable_ids)},
        **{f"y[{g}]": model.y[g] for g in range(len(assembly.output_rows))},
        **{f"w[{k}]": model.w[k] for k in range(len(assembly.link_rows))},
    }
    column = ComponentMap((variable, name) for name, variable in unknowns.items())
    incidence = {
        name: frozenset(column[v] for v in identify_variables(expression) if v in column)
        for name, expression in assembly.built.items()
    }
    position = {name: i for i, name in enumerate(spec.equation_ids)}
    index = {name: i for i, name in enumerate(variable_ids)}
    zero = set(candidates)
    found: dict[str, ZeroEliminated] = {}
    pins: set[str] = set()
    blocks: list[ZeroBlock] = []
    xi: npt.NDArray[np.float64] | None = None
    while True:
        # §17.1 step 2: single pins, to the fixpoint.
        changed = True
        while changed:
            changed = False
            for row in spec.equation_ids:
                if row in omitted or row in pins:
                    continue
                rest = incidence[row] - found.keys()
                if len(rest) != 1:
                    continue
                (j,) = rest
                if j not in zero:
                    continue
                e = position[row]
                pivot = float(derivatives.x[e, index[j]])
                if (
                    residuals_x0[row] == 0.0
                    and pivot != 0.0
                    and all(float(value) == 0.0 for value in derivatives.d[e])
                ):
                    found[j] = ZeroEliminated(j, row, float(residuals_x0[row]), pivot)
                    pins.add(row)
                    changed = True
        if zero <= found.keys():
            break
        # §18.1: the joint stage on the flows the passes leave.
        joint = _joint_blocks(
            spec, assembly, omitted, pins, found.keys(), zero, incidence, unknowns,
            residuals_x0, derivatives,
        )  # fmt: skip
        if not joint:
            break
        if xi is None:
            draws = len(variable_ids) + len(assembly.output_rows) + len(assembly.link_rows)
            xi = np.random.default_rng(JOINT_SEED).uniform(-1.0, 1.0, draws + len(decisions))
        for rows, variables in joint:
            block = _certify_block(
                len(blocks), rows, variables, spec, x0, assembly, scaling, decisions,
                residuals_x0, derivatives, found.keys(), xi,
            )  # fmt: skip
            blocks.append(block)
            pins.update(rows)
            for name in variables:
                found[name] = ZeroEliminated(name, None, None, None, block.block)
    unpinned = [name for name in candidates if name not in found]
    if unpinned:
        raise ProjectionRefusedError(
            "PROJECTION_ZERO_FLOW",
            f"{unpinned[0]}:unpinned",
            f"the flows {unpinned} are exactly 0.0 at x0 and no kept row pins them alone with a "
            "zero residual, a nonzero pivot and a zero decision tangent at x0 (R-296), nor does "
            "a certified block of rows pin them jointly (R-326)",
        )
    redundant = [
        row
        for row in spec.equation_ids
        if row not in omitted
        and row not in pins
        and incidence[row] & found.keys()
        and not incidence[row] - found.keys()
    ]
    if redundant:
        raise ProjectionRefusedError(
            "PROJECTION_ZERO_FLOW",
            f"{redundant[0]}:redundant_row",
            f"the rows {redundant} have no unknown left once the zero flows are eliminated (R-296)",
        )
    inputs = [name for link in links for name in link.inlet_variable_ids if name in found]
    if inputs:
        raise ProjectionRefusedError(
            "PROJECTION_ZERO_FLOW",
            f"{inputs[0]}:link_input",
            f"the eliminated flows {inputs} are inlet arguments of an external link; the FD policy "
            "has no rule for a constant inlet coordinate (R-296)",
        )
    return tuple(found[name] for name in variable_ids if name in found), tuple(blocks)


def _joint_blocks(
    spec: ProblemSpec,
    assembly: _Assembly,
    omitted: Collection[str],
    pins: Collection[str],
    eliminated: Collection[str],
    zero: Collection[str],
    incidence: Mapping[str, frozenset[str]],
    unknowns: Mapping[str, Any],
    residuals_x0: Mapping[str, float],
    derivatives: _RowDerivatives,
) -> list[tuple[tuple[str, ...], tuple[str, ...]]]:
    """§18.1 steps 1-3 up to certification: the candidate rows R_J with their numerical
    incidence N_e, and the connected components of the bipartite graph (R_J, Z_J), ordered by
    their first variable, rows in spec order and variables in variable order."""
    free = set(zero) - set(eliminated)
    index = {name: i for i, name in enumerate(spec.variable_ids)}
    numerical: dict[str, frozenset[str]] = {}
    for e, row in enumerate(spec.equation_ids):
        if row in omitted or row in pins:
            continue
        if residuals_x0[row] != 0.0 or any(float(value) != 0.0 for value in derivatives.d[e]):
            continue
        rest = incidence[row] - set(eliminated)
        columns = {k for k in rest if k in index and float(derivatives.x[e, index[k]]) != 0.0}
        if not columns or not columns <= free:
            continue
        # A `y` or `w` column is in N_e iff the row's own partial in it is nonzero at x₀; such a
        # column is never a zero flow, so the row is then no candidate.
        others = sorted(k for k in rest if k not in index)
        if others:
            partials = differentiate(
                assembly.built[row],
                wrt_list=[unknowns[k] for k in others],
                mode=Modes.reverse_numeric,
            )
            if any(float(value) != 0.0 for value in partials):
                continue
        numerical[row] = frozenset(columns)
    rows_of: dict[str, list[str]] = {}
    for row, incident in numerical.items():
        for name in incident:
            rows_of.setdefault(name, []).append(row)
    blocks: list[tuple[tuple[str, ...], tuple[str, ...]]] = []
    seen: set[str] = set()
    for start in (name for name in spec.variable_ids if name in rows_of):
        if start in seen:
            continue
        rows: set[str] = set()
        variables = {start}
        frontier = [start]
        while frontier:
            for row in rows_of[frontier.pop()]:
                if row not in rows:
                    rows.add(row)
                    for name in numerical[row] - variables:
                        variables.add(name)
                        frontier.append(name)
        seen |= variables
        blocks.append(
            (
                tuple(name for name in spec.equation_ids if name in rows),
                tuple(name for name in spec.variable_ids if name in variables),
            )
        )
    return blocks


def _certify_block(
    number: int,
    rows: Sequence[str],
    variables: Sequence[str],
    spec: ProblemSpec,
    x0: Mapping[str, float],
    assembly: _Assembly,
    scaling: Scaling,
    decisions: Sequence[DecisionSpec],
    residuals_x0: Mapping[str, float],
    derivatives: _RowDerivatives,
    eliminated: Collection[str],
    xi: npt.NDArray[np.float64],
) -> ZeroBlock:
    """§18.1 step 3: (a) square, (b) the scaled block's σ_min/σ_max ≥ `JOINT_RCOND_MIN`, (c) its
    rows exactly 0.0 at the two persistence states; or the refusal, named by its first variable."""
    subject = variables[0]
    if len(rows) != len(variables):
        raise ProjectionRefusedError(
            "PROJECTION_ZERO_FLOW",
            f"{subject}:joint_not_square",
            f"the rows {list(rows)} pin the zero flows {list(variables)} jointly, but are not a "
            "square block (R-326)",
        )
    position = {name: i for i, name in enumerate(spec.equation_ids)}
    index = {name: i for i, name in enumerate(spec.variable_ids)}
    block = derivatives.x[np.ix_([position[r] for r in rows], [index[v] for v in variables])]
    scaled = block * scaling.column_vector(variables)[None, :] / scaling.row_vector(rows)[:, None]
    singular = np.linalg.svd(scaled, compute_uv=False)
    rcond = float(singular[-1] / singular[0]) if singular[0] > 0.0 else 0.0
    if not rcond >= JOINT_RCOND_MIN:
        raise ProjectionRefusedError(
            "PROJECTION_ZERO_FLOW",
            f"{subject}:joint_singular",
            f"the scaled block of the rows {list(rows)} on the zero flows {list(variables)} has "
            f"sigma_min/sigma_max {rcond!r} < {JOINT_RCOND_MIN:g} (R-326)",
        )
    held = set(eliminated) | set(variables)
    values = [
        value
        for sign in (1.0, -1.0)
        for value in _persistence_rows(
            spec, x0, assembly, scaling, decisions, xi, held, rows, sign
        ).values()
    ]
    persistence = max(abs(value) for value in values)
    if not all(value == 0.0 for value in values):
        raise ProjectionRefusedError(
            "PROJECTION_ZERO_FLOW",
            f"{subject}:joint_not_persistent",
            f"the rows {list(rows)} do not vanish at the persistence states with the zero flows "
            f"{list(variables)} held at +0.0: max |r| = {persistence!r} (R-326)",
        )
    return ZeroBlock(
        number,
        tuple(variables),
        tuple(rows),
        tuple(float(residuals_x0[row]) for row in rows),
        rcond,
        persistence,
    )


def _persistence_rows(
    spec: ProblemSpec,
    x0: Mapping[str, float],
    assembly: _Assembly,
    scaling: Scaling,
    decisions: Sequence[DecisionSpec],
    xi: npt.NDArray[np.float64],
    held: Collection[str],
    rows: Collection[str],
    sign: float,
) -> dict[str, float]:
    """§18.1 (c): `rows` evaluated with floats at one persistence state. The variables in `held`
    are +0.0; every other unknown — `x`, the block outputs `y` and the link outputs `w`, the two
    as plain values, no EF called — and every decision (its model coordinate `d`, scale 1) moves
    by `sign` · 10⁻³ ξ_k max(|v₀_k|, s_k), with ξ drawn over x, y, w, d in that order."""
    n_x, n_y, n_w = len(spec.variable_ids), len(assembly.output_rows), len(assembly.link_rows)

    def moved(value: float, scale: float, k: int) -> float:
        return value + sign * JOINT_PERTURBATION * float(xi[k]) * max(abs(value), scale)

    state = {
        name: normalize_zero(0.0)
        if name in held
        else moved(float(x0[name]), scaling.column[name], i)
        for i, name in enumerate(spec.variable_ids)
    }
    outputs = {
        f"{row['block_id']}.{row['output_id']}": moved(
            assembly.output_starts[g], assembly.output_scales[g], n_x + g
        )
        for g, row in enumerate(assembly.output_rows)
    }
    parameters = dict(spec.parameters)
    for k, row in enumerate(assembly.link_rows):
        name = row["parameter_id"]
        parameters[name] = moved(
            float(spec.parameters[name]), assembly.link_scales[k], n_x + n_y + k
        )
    for j, decision in enumerate(decisions):
        name, k = decision.parameter_id, n_x + n_y + n_w + j
        start = float(spec.parameters[name])
        if decision.bounded:
            center, half_width = assembly.centers[j], assembly.half_widths[j]
            parameters[name] = center + half_width * moved((start - center) / half_width, 1.0, k)
        else:
            parameters[name] = moved(start, 1.0, k)
    return _float_rows(spec, state, outputs, parameters, rows)
