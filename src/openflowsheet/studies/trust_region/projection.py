"""The glass box: a `ProblemSpec` projected into a Pyomo model for TRF (M05 design note §6.1-§6.2;
ADR 0038 D2, D3; R-261).

**Not a second model and not a backend** (R-003; gate G13). Every row is the spec's own
`EquationSpec.build`, called with Pyomo variables as symbols and a `PyomoAlgebra` — the same
callables `compile/casadi_backend.py` traces, evaluated with a different algebra, as
`compile/reference.py` evaluates them with floats. Property blocks are not re-authored: each output
becomes one Python-callback `ExternalFunction` that calls the block through an `EFHolder`, behind
an explicit output variable. `PyomoAlgebra` implements no `CompiledProblem`, no route can select
it, and nothing outside `studies/trust_region/` imports this module; this module imports nothing
from `openflowsheet.models` (`tests/test_m05_isolation.py`).

**Construction order** (§6.1) fixes Pyomo's component order and therefore TRF's walk order and the
numbering of its `trf_data.ef_outputs`: variables `x`, decisions `d`, link variables `w`, the link
`ExternalFunction`s and their constraints `link`, the block `ExternalFunction`s, their output
variables `y` and constraints `ydef`, the rows `row`, the inequalities `ineq`, the objective `obj`,
and last the `scaling_factor` suffix. Pyomo names are index-based; canonical ids appear only in the
source map.

**Omitted rows** (a build-lane decision in WO-2, escalated to the design lane: design note §6.1
projects every row). A caller may name rows
the retained rows imply — SYN-001's two certified pressure alias rows, which make its 49 rows over
47 variables redundant by two — with a reason; they are not projected, and the source map lists
them under `omitted_rows`. With every row, such a spec is refused `PROJECTION_DOF`, correctly.

**Scales** (R-275, design note §16.2). One source: K03's `Scaling.from_spec(spec)`, the scales
M03's full-space NLP and the certificate use. They give the Ipopt `scaling_factor` suffixes —
variables `1/S_x`, rows `1/S_F` (Ipopt's `user-scaling`) — the scales recorded in the source map,
and `Projection.scaling`, which G4's denominators and P2's state comparison read.
`ProblemSpec.row_scales` and `column_scales` are not read. A spec that declares no kinds at all
(the test-only TR-E1) gets unit scales, recorded as `scale_provenance: "unit_no_kinds"`; a spec
that declares some kinds but not a registered one for every variable and row is refused
`PROJECTION_SCALES_UNAVAILABLE(<ids>)`. The objective carries `1/scale`. Each `ExternalFunction`
output k has the power-of-two scale s_k = 2^⌈log₂ max(|y_k(x₀)|, 1e-6)⌉: the holder returns
`value / s_k`, the defining constraint multiplies by s_k, so the scaling is exact and TRF's
θ = Σ|y − d(w)| over the holder variables is a sum of relative discrepancies (§6.1). The output
variable and its defining constraint carry `1/s_k` as well.

**Refusals** (typed, raised before TRF runs): `PROJECTION_SCALES_UNAVAILABLE(<ids>)` — above;
`PARAMETER_NOT_DIFFERENTIABLE(<equation_id>)` — a row builder cannot take a decision or link
symbol (ADR 0031 D2's meaning); `PROJECTION_NONSMOOTH(<id>)` — a row, inequality or objective
contains `abs`, `Expr_if`, `min`/`max`, `ceil`/`floor` or a piecewise node;
`PROJECTION_STRUCTURE(<id>)` — a variable appears in no constraint (or a row in no variable);
`PROJECTION_DOF(<n>)` — n_vars − n_equalities = n ≠ n_decisions, TRF's own count, repeated here so
the failure is typed.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final, Literal

import pyomo.environ as pyo
from pyomo.common.collections import ComponentSet
from pyomo.core.expr.numeric_expr import (
    AbsExpression,
    Expr_ifExpression,
    MaxExpression,
    MinExpression,
    UnaryFunctionExpression,
)
from pyomo.core.expr.visitor import identify_variables

from openflowsheet.canonical import (
    constants_sha256,
    document_sha256,
    model_version,
    structure_sha256,
)
from openflowsheet.compile.spec import Expr, ProblemSpec, RowBuilder
from openflowsheet.numerics.scaling import REGISTERED_NOMINALS, ScaleUnavailableError, Scaling
from openflowsheet.studies.trust_region.holders import (
    EFHolder,
    PropertyBlockBox,
    TruthBox,
    TruthModel,
)

SOURCE_MAP_SCHEMA: Final = "projection-source-map-v1"
#: §6.1: the floor under |y(x₀)| in an output scale, so a zero start value gets a finite scale.
OUTPUT_SCALE_FLOOR: Final = 1e-6
#: §6.1 step 3 / ADR 0038 D3: an external unit's coupling coordinates and their admissible ranges
#: (M04 spec §3.2's A(s) bounds on X̂ and ΔT̂, in K).
LINK_COORDINATES: Final = ("X", "dT")
LINK_BOUNDS: Final[Mapping[str, tuple[float, float]]] = {"X": (0.0, 0.95), "dT": (-50.0, 250.0)}
#: §6.1: the inlet order of an external link, (n_H₂, n_N₂, n_NH₃, n_Ar, n_CH₄, T, P).
LINK_INLET_SIZE: Final = 7
#: R-275: the provenance of the unit scales a spec without any declared kind is projected with.
UNIT_NO_KINDS: Final = "unit_no_kinds"
_NONSMOOTH_FUNCTIONS: Final = frozenset({"abs", "ceil", "floor"})
_NONSMOOTH_NODES: Final = (AbsExpression, Expr_ifExpression, MaxExpression, MinExpression)

RefusalCode = Literal[
    "PROJECTION_SCALES_UNAVAILABLE",
    "PARAMETER_NOT_DIFFERENTIABLE",
    "PROJECTION_NONSMOOTH",
    "PROJECTION_STRUCTURE",
    "PROJECTION_DOF",
]


class ProjectionRefusedError(Exception):
    """A `ProblemSpec` that cannot be projected for TRF, named by code and subject (§6.1)."""

    def __init__(self, code: RefusalCode, subject: str, detail: str) -> None:
        super().__init__(f"{code}({subject}): {detail}")
        self.code = code
        self.subject = subject
        self.detail = detail

    @property
    def reason(self) -> str:
        return f"{self.code}({self.subject})"


class PyomoAlgebra:
    """The `Algebra` protocol over Pyomo expressions — exactly the protocol, nothing more.

    Not a compile backend: it builds expressions for one projection and implements no
    `CompiledProblem` (R-003)."""

    def exp(self, value: Expr) -> Expr:
        return pyo.exp(value)

    def log(self, value: Expr) -> Expr:
        return pyo.log(value)

    def sqrt(self, value: Expr) -> Expr:
        return pyo.sqrt(value)


# -- the declarations (§6.1 "Inputs") -------------------------------------------------------------


@dataclass(frozen=True)
class DecisionSpec:
    """A pinned input promoted to a decision. Bounded: the scaled variable d ∈ [−1, 1] with the
    symbol c + h·d. `lower = upper = None`: unbounded, the variable is the parameter itself."""

    parameter_id: str
    lower: float | None
    upper: float | None

    @property
    def bounded(self) -> bool:
        return self.lower is not None and self.upper is not None

    def center_half_width(self) -> tuple[float, float]:
        """(c, h) in binary64: c = (lo + hi)·0.5, h = (hi − lo)·0.5; (0, 1) when unbounded."""
        if self.lower is None and self.upper is None:
            return 0.0, 1.0
        if self.lower is None or self.upper is None or not self.lower < self.upper:
            raise ValueError(
                f"decision {self.parameter_id!r}: a box needs finite lower < upper, or neither "
                f"(got [{self.lower!r}, {self.upper!r}])"
            )
        return (self.lower + self.upper) * 0.5, (self.upper - self.lower) * 0.5


@dataclass(frozen=True)
class ExternalLinkSpec:
    """An external unit whose pinned coupling coordinates (X̂, ΔT̂) become variables linked to its
    truth's two outputs on its seven inlet variables (ADR 0038 D3)."""

    unit_id: str
    x_param_id: str
    dt_param_id: str
    inlet_variable_ids: tuple[str, ...]
    truth: TruthModel


@dataclass(frozen=True)
class InequalitySpec:
    """`build ≤ bound` (`sense "<="`) or `build ≥ bound` (`">="`), tightened inward by
    `margin_rel · |bound|`. `build` is a `RowBuilder` over the projection's symbols."""

    inequality_id: str
    build: RowBuilder
    bound: float
    source: str
    margin_rel: float
    sense: Literal["<=", ">="] = "<="

    def tightened(self) -> float:
        if self.sense == "<=":
            return self.bound - self.margin_rel * abs(self.bound)
        return self.bound + self.margin_rel * abs(self.bound)


@dataclass(frozen=True)
class ObjectiveSpec:
    objective_id: str
    sense: Literal["minimize", "maximize"]
    build: RowBuilder
    scale: float


def output_scale(start_value: float) -> float:
    """s = 2^⌈log₂ max(|y|, 1e-6)⌉, exactly: from the binary exponent, never from `log2`."""
    magnitude = max(abs(start_value), OUTPUT_SCALE_FLOOR)
    mantissa, exponent = math.frexp(magnitude)  # magnitude = mantissa·2^exponent, 0.5 ≤ m < 1
    return math.ldexp(1.0, exponent - 1 if mantissa == 0.5 else exponent)


# -- the projection -------------------------------------------------------------------------------


@dataclass(frozen=True)
class Projection:
    """A projected spec: the Pyomo model TRF solves, its holders and its source map.

    `model` is the original; TRF works on a clone of it and returns that clone. `row_ids` and
    `row_expressions` are the projected rows in order, kept so that equivalence tests evaluate
    exactly the expressions the constraints hold.
    `ef_names` maps each value callback — the object TRF's clone shares with the original — to its
    `ExternalFunction`'s component name."""

    model: Any
    spec: ProblemSpec
    decisions: tuple[DecisionSpec, ...]
    centers: tuple[float, ...]
    half_widths: tuple[float, ...]
    holders: tuple[EFHolder, ...]
    row_ids: tuple[str, ...]
    row_expressions: tuple[Any, ...]
    ef_names: Mapping[Callable[..., float], str]
    source_map: Mapping[str, Any]
    #: R-275: the row and column scales of every projected quantity — the suffixes', G4's and P2's.
    scaling: Scaling

    @property
    def source_map_sha256(self) -> str:
        return document_sha256(self.source_map)

    @property
    def decision_variables(self) -> list[Any]:
        return [self.model.d[j] for j in range(len(self.decisions))]

    def parameter_value(self, index: int, scaled: float) -> float:
        """The parameter a decision variable value stands for: c + h·d, or d when unbounded."""
        if not self.decisions[index].bounded:
            return scaled
        return self.centers[index] + self.half_widths[index] * scaled

    def decision_parameters(self, model: Any = None) -> dict[str, float]:
        """The decisions of `model` (the original by default, or TRF's returned clone) as
        parameter values, by parameter id."""
        source = self.model if model is None else model
        return {
            decision.parameter_id: self.parameter_value(j, float(pyo.value(source.d[j])))
            for j, decision in enumerate(self.decisions)
        }

    def set_state(self, values: Mapping[str, float]) -> None:
        """Set every `x` to `values` and every block output `y` to its block's value there.

        The blocks are called directly, not through the holders, so the holders' ledgers hold
        TRF's requests only."""
        model = self.model
        for index, name in enumerate(self.spec.variable_ids):
            model.x[index].set_value(float(values[name]), skip_validation=True)
        _initialize_outputs(model, self.spec, values)


def _initialize_outputs(model: Any, spec: ProblemSpec, values: Mapping[str, float]) -> None:
    index = 0
    for block in spec.blocks:
        produced = block.values([float(values[name]) for name in spec.block_inputs[block.block_id]])
        for value in produced:
            model.y[index].set_value(float(value), skip_validation=True)
            index += 1


def project(
    spec: ProblemSpec,
    x0: Mapping[str, float],
    *,
    decisions: Sequence[DecisionSpec],
    objective: ObjectiveSpec,
    domain: Mapping[str, tuple[float, float]],
    external_links: Sequence[ExternalLinkSpec] = (),
    inequalities: Sequence[InequalitySpec] = (),
    omitted_rows: Mapping[str, str] | None = None,
) -> Projection:
    """Project `spec` at the state `x0` (every variable id → binary64) for TRF (§6.1).

    `domain` gives the bounds of the `temperature` and `pressure` variable kinds — the bound
    property provider's declared domain. Raises `ProjectionRefusedError` for a spec TRF cannot be
    given, and `ValueError` for an inconsistent call.

    `omitted_rows` maps an equation id to the reason it is not projected. It exists for rows that
    the retained rows imply — a flowsheet's certified alias rows (`orchestrator/rank.py`'s
    elimination), which M03's full-space NLP also leaves out of its equality constraints (ADR 0032
    D1, "the kept rows F_K") — and that would otherwise make TRF's DOF count wrong and its
    equality Jacobian rank-deficient. The projection does not judge the reason; the caller owns
    it, and the source map records it."""
    spec.validate()
    _check_call(spec, x0, decisions, external_links)
    scaling = projection_scaling(spec)
    omitted = dict(omitted_rows or {})
    unknown_rows = sorted(set(omitted) - set(spec.equation_ids))
    if unknown_rows:
        raise ValueError(f"omitted_rows names {unknown_rows}, which are not equations of the spec")
    projected = [equation for equation in spec.equations if equation.equation_id not in omitted]
    model = pyo.ConcreteModel(name=spec.label)

    # 1. Variables.
    variable_ids = spec.variable_ids
    variable_index = {name: index for index, name in enumerate(variable_ids)}
    bounds = [_variable_bounds(spec, name, float(x0[name]), domain) for name in variable_ids]
    model.x = pyo.Var(
        range(len(variable_ids)),
        initialize={index: float(x0[name]) for index, name in enumerate(variable_ids)},
        bounds=lambda m, index: bounds[index],
    )

    # 2. Decisions.
    centers: list[float] = []
    half_widths: list[float] = []
    starts: list[float] = []
    for decision in decisions:
        center, half_width = decision.center_half_width()
        start = float(spec.parameters[decision.parameter_id])
        if decision.bounded:
            if not decision.lower <= start <= decision.upper:  # type: ignore[operator]
                raise ValueError(
                    f"decision {decision.parameter_id!r} starts at {start!r}, outside "
                    f"[{decision.lower!r}, {decision.upper!r}]"
                )
            starts.append((start - center) / half_width)
        else:
            starts.append(start)
        centers.append(center)
        half_widths.append(half_width)
    model.d = pyo.Var(
        range(len(decisions)),
        initialize=dict(enumerate(starts)),
        bounds=lambda m, j: (-1.0, 1.0) if decisions[j].bounded else (None, None),
    )
    parameters: dict[str, Any] = dict(spec.parameters)
    for j, decision in enumerate(decisions):
        parameters[decision.parameter_id] = (
            centers[j] + half_widths[j] * model.d[j] if decision.bounded else model.d[j]
        )

    # 3. External links.
    holders: list[EFHolder] = []
    ef_names: dict[Callable[..., float], str] = {}
    link_starts = [
        float(spec.parameters[parameter])
        for link in external_links
        for parameter in (link.x_param_id, link.dt_param_id)
    ]
    link_scales = [output_scale(value) for value in link_starts]
    model.w = pyo.Var(
        range(len(link_starts)),
        initialize=dict(enumerate(link_starts)),
        bounds=lambda m, k: LINK_BOUNDS[LINK_COORDINATES[k % 2]],
    )
    link_calls: list[Any] = []
    link_rows: list[dict[str, Any]] = []
    for position, link in enumerate(external_links):
        box = TruthBox(link.truth)
        scales = link_scales[2 * position : 2 * position + 2]
        holder = EFHolder(f"link:{link.unit_id}", box, scales, kind="truth")
        holders.append(holder)
        inlet = [model.x[variable_index[name]] for name in link.inlet_variable_ids]
        for coordinate, parameter in enumerate((link.x_param_id, link.dt_param_id)):
            k = 2 * position + coordinate
            name = f"ef_ext_{k}"
            value = holder.value_callback(coordinate)
            function = pyo.ExternalFunction(
                function=value, gradient=holder.gradient_callback(coordinate)
            )
            model.add_component(name, function)
            ef_names[value] = name
            link_calls.append(function(*inlet))
            parameters[parameter] = model.w[k]
            link_rows.append(
                {
                    "pyomo_var": f"w[{k}]",
                    "ef": name,
                    "unit_id": link.unit_id,
                    "parameter_id": parameter,
                    "coordinate": LINK_COORDINATES[coordinate],
                    "input_variable_ids": list(link.inlet_variable_ids),
                    "truth": {key: box.identity.get(key) for key in ("kind", "id", "sha256")},
                    "output_scale": scales[coordinate],
                }
            )
    model.link = pyo.Constraint(
        range(len(link_calls)), rule=lambda m, k: m.w[k] == link_scales[k] * link_calls[k]
    )

    # 4. Property blocks.
    output_starts: list[float] = []
    output_rows: list[dict[str, Any]] = []
    block_calls: list[Any] = []
    block_outputs: dict[str, Any] = {}
    for block in spec.blocks:
        feeding = spec.block_inputs[block.block_id]
        produced = [float(v) for v in block.values([float(x0[name]) for name in feeding])]
        scales = [output_scale(value) for value in produced]
        holder = EFHolder(
            f"block:{block.block_id}", PropertyBlockBox(block), scales, kind="property_block"
        )
        holders.append(holder)
        inputs = [model.x[variable_index[name]] for name in feeding]
        for k, output_id in enumerate(block.output_ids):
            g = len(output_starts)
            name = f"ef_{g}"
            value = holder.value_callback(k)
            function = pyo.ExternalFunction(function=value, gradient=holder.gradient_callback(k))
            model.add_component(name, function)
            ef_names[value] = name
            block_calls.append(function(*inputs))
            output_starts.append(produced[k])
            output_rows.append(
                {
                    "pyomo_var": f"y[{g}]",
                    "ef": name,
                    "block_id": block.block_id,
                    "output_id": output_id,
                    "input_variable_ids": list(feeding),
                    "output_scale": scales[k],
                }
            )
    output_scales = [row["output_scale"] for row in output_rows]
    model.y = pyo.Var(range(len(output_starts)), initialize=dict(enumerate(output_starts)))
    model.ydef = pyo.Constraint(
        range(len(block_calls)), rule=lambda m, g: m.y[g] == output_scales[g] * block_calls[g]
    )
    for g, row in enumerate(output_rows):
        block_outputs[f"{row['block_id']}.{row['output_id']}"] = model.y[g]

    # 5. Rows.
    symbols = {name: model.x[index] for index, name in enumerate(variable_ids)}
    row_ids = tuple(equation.equation_id for equation in projected)
    expressions = [
        _build(equation.equation_id, equation.build, symbols, block_outputs, parameters, spec)
        for equation in projected
    ]
    model.row = pyo.Constraint(range(len(expressions)), rule=lambda m, i: expressions[i] == 0)

    # 6. Inequalities.
    inequality_expressions = [
        _build(item.inequality_id, item.build, symbols, block_outputs, parameters, spec)
        for item in inequalities
    ]

    def inequality_rule(m: Any, k: int) -> Any:
        item = inequalities[k]
        if item.sense == "<=":
            return inequality_expressions[k] <= item.tightened()
        return inequality_expressions[k] >= item.tightened()

    model.ineq = pyo.Constraint(range(len(inequalities)), rule=inequality_rule)

    # 7. Objective.
    objective_expression = _build(
        objective.objective_id, objective.build, symbols, block_outputs, parameters, spec
    )
    model.obj = pyo.Objective(
        expr=objective_expression,
        sense=pyo.minimize if objective.sense == "minimize" else pyo.maximize,
    )

    # Scaling (Ipopt `user-scaling`).
    model.scaling_factor = pyo.Suffix(direction=pyo.Suffix.EXPORT)
    for index, name in enumerate(variable_ids):
        model.scaling_factor[model.x[index]] = 1.0 / scaling.column[name]
    for k, scale in enumerate(link_scales):
        model.scaling_factor[model.w[k]] = 1.0 / scale
        model.scaling_factor[model.link[k]] = 1.0 / scale
    for g, scale in enumerate(output_scales):
        model.scaling_factor[model.y[g]] = 1.0 / scale
        model.scaling_factor[model.ydef[g]] = 1.0 / scale
    for index, name in enumerate(row_ids):
        model.scaling_factor[model.row[index]] = 1.0 / scaling.row[name]
    model.scaling_factor[model.obj] = 1.0 / objective.scale

    # Refusals, in §6.1's order (PARAMETER_NOT_DIFFERENTIABLE was raised by `_build`).
    for subject, expression in (
        *zip(row_ids, expressions, strict=True),
        *(
            (item.inequality_id, e)
            for item, e in zip(inequalities, inequality_expressions, strict=True)
        ),
        (objective.objective_id, objective_expression),
    ):
        found = find_nonsmooth_node(expression)
        if found is not None:
            raise ProjectionRefusedError("PROJECTION_NONSMOOTH", subject, f"contains {found}")
    _check_structure(model, spec, decisions, external_links, output_rows, len(decisions))

    source_map = _source_map(
        spec,
        scaling,
        bounds,
        row_ids,
        output_rows,
        decisions,
        centers,
        half_widths,
        link_rows,
        inequalities,
        objective,
        omitted,
    )
    return Projection(
        model=model,
        spec=spec,
        decisions=tuple(decisions),
        centers=tuple(centers),
        half_widths=tuple(half_widths),
        holders=tuple(holders),
        row_ids=row_ids,
        row_expressions=tuple(expressions),
        ef_names=ef_names,
        source_map=source_map,
        scaling=scaling,
    )


# -- helpers --------------------------------------------------------------------------------------


def projection_scaling(spec: ProblemSpec) -> Scaling:
    """R-275: K03's `Scaling.from_spec(spec)`; unit scales, provenance `unit_no_kinds`, for a spec
    that declares no kind at all; `PROJECTION_SCALES_UNAVAILABLE(<ids>)` for one that declares
    some, naming every variable and row without a kind that has a registered nominal."""
    if not spec.variable_kinds and not spec.row_kinds:
        return Scaling(
            column={name: 1.0 for name in spec.variable_ids},
            row={name: 1.0 for name in spec.equation_ids},
            provenance=UNIT_NO_KINDS,
        )
    try:
        return Scaling.from_spec(spec)
    except ScaleUnavailableError as error:
        missing = [
            name
            for ids, kinds in (
                (spec.variable_ids, spec.variable_kinds),
                (spec.equation_ids, spec.row_kinds),
            )
            for name in ids
            if kinds.get(name) not in REGISTERED_NOMINALS
        ]
        raise ProjectionRefusedError(
            "PROJECTION_SCALES_UNAVAILABLE", ",".join(missing), str(error)
        ) from error


def _check_call(
    spec: ProblemSpec,
    x0: Mapping[str, float],
    decisions: Sequence[DecisionSpec],
    links: Sequence[ExternalLinkSpec],
) -> None:
    missing = [name for name in spec.variable_ids if name not in x0]
    if missing:
        raise ValueError(f"x0 has no value for {missing}")
    nonfinite = [name for name in spec.variable_ids if not math.isfinite(float(x0[name]))]
    if nonfinite:
        raise ValueError(f"x0 is not finite at {nonfinite}")
    promoted = [decision.parameter_id for decision in decisions] + [
        parameter for link in links for parameter in (link.x_param_id, link.dt_param_id)
    ]
    unknown = [name for name in promoted if name not in spec.parameters]
    if unknown:
        raise ValueError(f"{unknown} are not pinned inputs of {spec.label!r}")
    if len(set(promoted)) != len(promoted):
        raise ValueError(f"a pinned input is promoted twice: {promoted}")
    known = set(spec.variable_ids)
    for link in links:
        if len(link.inlet_variable_ids) != LINK_INLET_SIZE:
            raise ValueError(f"link {link.unit_id!r} needs {LINK_INLET_SIZE} inlet variables")
        strangers = [name for name in link.inlet_variable_ids if name not in known]
        if strangers:
            raise ValueError(f"link {link.unit_id!r}: {strangers} are not variables")


def _variable_bounds(
    spec: ProblemSpec, name: str, start: float, domain: Mapping[str, tuple[float, float]]
) -> tuple[float | None, float | None]:
    """§6.1 step 1: the provider's domain for temperatures and pressures; molar flows ≥ 0 except
    a flow exactly 0.0 at x₀, which the regime's own rows pin (ADR 0032 D4); none otherwise."""
    kind = spec.variable_kinds.get(name)
    if kind in ("temperature", "pressure"):
        if kind not in domain:
            raise ValueError(f"no {kind} domain given for {name!r}")
        low, high = domain[kind]
        return float(low), float(high)
    if kind == "molar_flow":
        return (None, None) if start == 0.0 else (0.0, None)
    return None, None


def _build(
    subject: str,
    build: RowBuilder,
    symbols: Mapping[str, Any],
    outputs: Mapping[str, Any],
    parameters: Mapping[str, Any],
    spec: ProblemSpec,
) -> Any:
    """One builder with the decision and link symbols in place; `PARAMETER_NOT_DIFFERENTIABLE`
    if it cannot take them but can take the floats, and the builder's own error if it cannot even
    do that (a defect, not a refusal)."""
    try:
        expression = build(symbols, outputs, parameters, PyomoAlgebra())
    except Exception as error:  # noqa: BLE001 - a builder may raise anything on a symbol
        try:
            build(symbols, outputs, spec.parameters, PyomoAlgebra())
        except Exception:  # noqa: BLE001 - see above; the original error is the one re-raised
            raise error from None
        message = (str(error).splitlines() or [type(error).__name__])[0][:300]
        raise ProjectionRefusedError("PARAMETER_NOT_DIFFERENTIABLE", subject, message) from error
    if isinstance(expression, int | float) or not list(identify_variables(expression)):
        raise ProjectionRefusedError(
            "PROJECTION_STRUCTURE", subject, "the expression has no variable"
        )
    return expression


def find_nonsmooth_node(expression: Any) -> str | None:
    stack = [expression]
    while stack:
        node = stack.pop()
        if isinstance(node, _NONSMOOTH_NODES) or type(node).__name__ == "PiecewiseLinearExpression":
            return type(node).__name__
        if isinstance(node, UnaryFunctionExpression) and node.getname() in _NONSMOOTH_FUNCTIONS:
            return str(node.getname())
        if hasattr(node, "is_expression_type") and node.is_expression_type():
            stack.extend(node.args)
    return None


def _check_structure(
    model: Any,
    spec: ProblemSpec,
    decisions: Sequence[DecisionSpec],
    links: Sequence[ExternalLinkSpec],
    output_rows: Sequence[Mapping[str, Any]],
    n_decisions: int,
) -> None:
    """Every declared variable in some constraint, and TRF's DOF count equal to the decisions."""
    seen = ComponentSet()
    equalities = 0
    for constraint in model.component_data_objects(pyo.Constraint, active=True):
        seen.update(identify_variables(constraint.expr, include_fixed=True))
        if constraint.equality:
            equalities += 1
    declared = [
        *((model.x[i], name) for i, name in enumerate(spec.variable_ids)),
        *((model.d[j], d.parameter_id) for j, d in enumerate(decisions)),
        *(
            (model.w[2 * p + c], parameter)
            for p, link in enumerate(links)
            for c, parameter in enumerate((link.x_param_id, link.dt_param_id))
        ),
        *((model.y[g], f"{r['block_id']}.{r['output_id']}") for g, r in enumerate(output_rows)),
    ]
    for variable, name in declared:
        if variable not in seen:
            raise ProjectionRefusedError(
                "PROJECTION_STRUCTURE", name, "the variable appears in no constraint"
            )
    dof = len(seen) - equalities
    if dof != n_decisions:
        raise ProjectionRefusedError(
            "PROJECTION_DOF",
            str(dof),
            f"{len(seen)} variables in constraints less {equalities} equalities is {dof}, "
            f"not the {n_decisions} decisions TRF is given",
        )


def _source_map(
    spec: ProblemSpec,
    scaling: Scaling,
    bounds: Sequence[tuple[float | None, float | None]],
    row_ids: Sequence[str],
    output_rows: Sequence[Mapping[str, Any]],
    decisions: Sequence[DecisionSpec],
    centers: Sequence[float],
    half_widths: Sequence[float],
    link_rows: Sequence[Mapping[str, Any]],
    inequalities: Sequence[InequalitySpec],
    objective: ObjectiveSpec,
    omitted: Mapping[str, str],
) -> dict[str, Any]:
    """`projection-source-map-v1` (§6.2), without its `trf` part, which a run fills."""
    structure = structure_sha256(
        spec.variable_ids, spec.equation_ids, spec.parameter_ids, spec.row_accumulation
    )
    origins = {equation.equation_id: equation.origin for equation in spec.equations}
    return {
        "schema_version": SOURCE_MAP_SCHEMA,
        "problem": {
            "label": spec.label,
            "model_version": model_version(spec.label, structure),
            "structure_sha256": structure,
            "constants_sha256": constants_sha256(spec.parameters, spec.parameter_ids),
        },
        "variables": [
            {
                "pyomo": f"x[{index}]",
                "variable_id": name,
                "kind": spec.variable_kinds.get(name),
                "column_scale": scaling.column[name],
                "bounds": list(bounds[index]),
            }
            for index, name in enumerate(spec.variable_ids)
        ],
        "rows": [
            {
                "pyomo": f"row[{index}]",
                "equation_id": name,
                "origin": origins[name],
                "row_scale": scaling.row[name],
            }
            for index, name in enumerate(row_ids)
        ],
        "omitted_rows": [
            {"equation_id": name, "origin": origins[name], "reason": omitted[name]}
            for name in spec.equation_ids
            if name in omitted
        ],
        "block_outputs": [dict(row) for row in output_rows],
        "decisions": [
            {
                "pyomo_var": f"d[{j}]",
                "parameter_id": decision.parameter_id,
                "center": centers[j],
                "half_width": half_widths[j],
                "lower": decision.lower,
                "upper": decision.upper,
            }
            for j, decision in enumerate(decisions)
        ],
        "external_links": [dict(row) for row in link_rows],
        "inequalities": [
            {
                "pyomo": f"ineq[{k}]",
                "inequality_id": item.inequality_id,
                "source": item.source,
                "sense": item.sense,
                "bound": item.bound,
                "margin_rel": item.margin_rel,
            }
            for k, item in enumerate(inequalities)
        ],
        "objective": {
            "objective_id": objective.objective_id,
            "sense": objective.sense,
            "scale": objective.scale,
        },
        "scale_provenance": scaling.provenance,
        "trf": [],
    }
