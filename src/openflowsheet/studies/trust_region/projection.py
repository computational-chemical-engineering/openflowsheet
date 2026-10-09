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

**Omitted rows** (R-274, design note §16.1). A row is not projected **iff**
`orchestrator/rank.py`'s `eliminate_alias_rows` eliminates it — the certificate's and M03's
elimination, applied by the projection itself to the spec's rows at x₀ and at the certificate's
pressure-shifted witness state (`pressure_shifted_state`), with the elimination's own tolerances.
SYN-001's 49 rows over 47 variables have two such rows; projected with them, TRF's DOF count is the
decisions less two. Each omitted row is certified by four facts, recorded in the source map's
`omitted_rows` (the first three) and on every TRF run (the fourth):
1. the elimination removes it, on the retained-forest path recorded as `retained_path`, with its
   two-state witness (no witness state is no certificate);
2. its residual at x₀, `residual_x0`, is within the elimination's `pressure_tolerance`;
3. every decision's scaled tangent residual on it, Ĵ_E X̂_j + F̂_d,E,j with Ĵ_K X̂ = −F̂_d,K at x₀
   in the projection's scales (M03's Q3, ADR 0031 D3), is within τ_alias = 1e-8;
4. at a TRF final state its residual is within `pressure_tolerance` (`Projection.omitted_rows_at`,
   which `trf.run_trf` records; a failure there fails P2, `PROJECTION_DISAGREES`).
A failure of 1-3 is `PROJECTION_OMITTED_ROW_UNCERTIFIED(<id>)`, before any solve. A caller may
name the omitted rows; a set other than the certified one is refused the same way. The
elimination's own refusals (`SpecificationConflictError`, `UnsupportedRankStructureError`)
propagate unchanged: an alias pattern it cannot read is an escalation, not a row to drop by hand.

**Exact-zero flows** (R-296, design note §17.1, rule `M05-zero-flow-v1`). A molar flow exactly 0.0
at x₀ is pinned there by its regime's own rows (ADR 0032 D4) but left unbounded; Ipopt satisfies the
pin only to roundoff, and a truth or block evaluated at n = −O(1e-27) rightly refuses it. So such a
flow is not a variable of the projection but the constant +0.0, eliminated together with its pin,
after R-274's set is computed and before the model TRF sees is built. Candidates Z₀: the
`molar_flow` variables with x₀ == 0.0. Repeated passes over the kept rows in spec order (rows not
omitted by R-274 and not already a pin) pair a row e whose structural incidence — the shape
check's unknowns `x`, `y`, `w` its expression contains — less the eliminated flows is exactly {j},
j ∈ Z₀, iff (i) r_e(x₀) == 0.0, (ii) ∂r_e/∂x_j(x₀) ≠ 0 (the projection's x-Jacobian at x₀, which
G4 holds to CasADi's) and (iii) ∂r_e/∂d(x₀) == 0.0 for every decision (a link variable is in the
incidence, so a pin has none); the first certified row wins. Refusals,
`PROJECTION_ZERO_FLOW(<id>:<reason>)`: `unpinned` (a candidate left unpaired), `redundant_row` (a
kept row, not a pin, whose unknowns were all eliminated) and `link_input` (an eliminated flow among
an external link's inlet arguments). The eliminated flows are +0.0 in every builder's symbols and
every EF's arguments (so neither Pyomo's differentiation, TRF's `identify_variables` nor the affine
basis sees a column for them, and every holder key equals x₀'s); their pins are not built. The
source map records `zero_eliminated` ({variable_id, row_id, residual_x0, dr_dx}) and lists the
flows among `variables` with `pyomo: null`; `Projection.state_of` is the inverse map (+0.0 for
each), and `Projection.zero_pins_at` evaluates the pins at a final state against 0.0, P2's hook as
`omitted_rows_at` is.

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
the failure is typed; `PROJECTION_IMPLICIT_EF_INPUT(<ids>)` — below;
`PROJECTION_OMITTED_ROW_UNCERTIFIED(<id>)` — above; `PROJECTION_ZERO_FLOW(<id>:<reason>)` — above.

**The shape check** (R-278, design note §16.5). TRF fixes an external link's output in every
subproblem only through its model r_k(w), so the glass box must determine each link-EF input
without inverting the link: an output pinned by the decisions alone (`X̂ − 90 z = 0`) leaves the
link's inlet undetermined and the output over-determined. The check is structural. Unknowns: every
projection variable except the decisions — `x`, the block outputs `y` and the link variables `w`.
Equations: the projected rows (incident on the unknowns their expressions contain), the block
definitions `ydef` (incident on their output and on every input of their block: property relations
stay functions) and the link definitions `link` (incident on their `w` only: the link output is
fixed). After the DOF check this incidence is square; the projection passes **iff** it has a
perfect matching (`scipy.sparse.csgraph.maximum_bipartite_matching`). Otherwise it is refused
`PROJECTION_IMPLICIT_EF_INPUT(<ids>)`, naming the structurally undetermined variables — those an
alternating path reaches from a variable the maximum matching leaves unmatched, the column side of
the Dulmage-Mendelsohn under-determined block, which does not depend on which maximum matching was
found — with the link-EF inputs among them flagged, and the unmatched equations. Numeric regularity
is S0's K04 certificate on the same system, not this check. TR-E1 is exempt as the oracle
(`shape_check="exempt_oracle"`: Pyomo's example is itself implicit, `x1` entering only through the
EF and `c2` only decisions); the verdict is still computed and recorded in the source map's
`shape_check`.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final, Literal

import numpy as np
import numpy.typing as npt
import pyomo.environ as pyo
from pyomo.common.collections import ComponentMap, ComponentSet
from pyomo.core.expr.calculus.derivatives import Modes, differentiate
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
    normalize_zero,
    structure_sha256,
)
from openflowsheet.compile.reference import FloatAlgebra, block_outputs
from openflowsheet.compile.spec import DomainError, Expr, ProblemSpec, RowBuilder
from openflowsheet.numerics.linear import LinearSolveFailedError, solve_linear
from openflowsheet.numerics.scaling import REGISTERED_NOMINALS, ScaleUnavailableError, Scaling
from openflowsheet.orchestrator.rank import (
    EliminatedRow,
    eliminate_alias_rows,
    pressure_shifted_state,
)
from openflowsheet.studies.sensitivity import TAU_ALIAS
from openflowsheet.studies.trust_region.holders import (
    LINK_BOUNDS,
    LINK_COORDINATES,
    EFHolder,
    PropertyBlockBox,
    TruthBox,
    TruthModel,
)

SOURCE_MAP_SCHEMA: Final = "projection-source-map-v1"
#: §6.1: the floor under |y(x₀)| in an output scale, so a zero start value gets a finite scale.
OUTPUT_SCALE_FLOOR: Final = 1e-6
#: §6.1: the inlet order of an external link, (n_H₂, n_N₂, n_NH₃, n_Ar, n_CH₄, T, P).
LINK_INLET_SIZE: Final = 7
#: R-275: the provenance of the unit scales a spec without any declared kind is projected with.
UNIT_NO_KINDS: Final = "unit_no_kinds"
#: R-274: why an omitted row is not projected, as the source map records it.
OMITTED_ROW_REASON: Final = (
    "eliminated by orchestrator/rank.py's alias elimination: implied by the retained rows (R-274)"
)
#: R-296: the rule that eliminates the flows exactly 0.0 at x₀ with their pins (design note §17.1).
ZERO_FLOW_RULE: Final = "M05-zero-flow-v1"
#: R-296: a pin's residual at a final state, with its flow the constant +0.0 (M05 build log Z1).
ZERO_PIN_TOLERANCE: Final = 0.0
_NONSMOOTH_FUNCTIONS: Final = frozenset({"abs", "ceil", "floor"})
_NONSMOOTH_NODES: Final = (AbsExpression, Expr_ifExpression, MaxExpression, MinExpression)

RefusalCode = Literal[
    "PROJECTION_SCALES_UNAVAILABLE",
    "PARAMETER_NOT_DIFFERENTIABLE",
    "PROJECTION_NONSMOOTH",
    "PROJECTION_STRUCTURE",
    "PROJECTION_DOF",
    "PROJECTION_IMPLICIT_EF_INPUT",
    "PROJECTION_OMITTED_ROW_UNCERTIFIED",
    "PROJECTION_ZERO_FLOW",
]
#: R-278: whether `project` enforces the shape check. `exempt_oracle` is TR-E1's only (test-only).
ShapeCheck = Literal["required", "exempt_oracle"]
SHAPE_CHECK_CRITERION: Final = (
    "structural perfect matching of the projected equations to every variable but the decisions, "
    "link-EF outputs fixed and property relations kept (R-278)"
)


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
class OmittedRow:
    """A row the projection leaves out, with what certifies it (R-274's facts 1-3)."""

    elimination: EliminatedRow
    origin: str
    residual_x0: float
    #: Each decision's scaled tangent residual on the row, by parameter id.
    tangent_residuals: Mapping[str, float]

    @property
    def equation_id(self) -> str:
        return self.elimination.row_id

    @property
    def tolerance(self) -> float:
        """The elimination's `pressure_tolerance`, which facts 2 and 4 are judged by."""
        return self.elimination.tolerance

    def as_document(self) -> dict[str, Any]:
        return {
            "equation_id": self.equation_id,
            "origin": self.origin,
            "reason": OMITTED_ROW_REASON,
            "retained_path": [[name, sign] for name, sign in self.elimination.equals],
            "constant_mismatch": self.elimination.constant_mismatch,
            "residual_x0": self.residual_x0,
            "pressure_tolerance": self.tolerance,
            "tangent_residuals": dict(self.tangent_residuals),
            "tau_alias": TAU_ALIAS,
        }


@dataclass(frozen=True)
class OmittedRowsCheck:
    """R-274's fact 4 at one state: every omitted row's residual against its tolerance.

    `failed` names the rows above it; `detail` says why the rows could not be evaluated (a block
    refusing the state), which fails the check too. P2 reads `status` (`PROJECTION_DISAGREES` on a
    failure)."""

    residuals: Mapping[str, float]
    failed: tuple[str, ...] = ()
    detail: str = ""

    @property
    def status(self) -> Literal["pass", "fail"]:
        return "fail" if self.failed or self.detail else "pass"

    @property
    def code(self) -> str | None:
        return "PROJECTION_DISAGREES" if self.status == "fail" else None

    def as_document(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "code": self.code,
            "residuals": dict(self.residuals),
            "failed": list(self.failed),
            "detail": self.detail,
        }


@dataclass(frozen=True)
class ZeroEliminated:
    """A flow exactly 0.0 at x₀ that is not a variable of the projection but the constant +0.0,
    eliminated together with the row that pins it (`M05-zero-flow-v1`, R-296): its pin's residual
    and its derivative in the flow at x₀ (criteria (i) and (ii))."""

    variable_id: str
    row_id: str
    residual_x0: float
    dr_dx: float

    def as_document(self) -> dict[str, Any]:
        return {
            "variable_id": self.variable_id,
            "row_id": self.row_id,
            "residual_x0": self.residual_x0,
            "dr_dx": self.dr_dx,
        }


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
    #: Each holder's `x` indices, in its box's input order: the arguments its `ExternalFunction`s
    #: are called with (R-276's pre-flight evaluates them at x₀).
    holder_inputs: tuple[tuple[int, ...], ...]
    row_ids: tuple[str, ...]
    row_expressions: tuple[Any, ...]
    ef_names: Mapping[Callable[..., float], str]
    source_map: Mapping[str, Any]
    #: R-275: the row and column scales of every projected quantity — the suffixes', G4's and P2's.
    scaling: Scaling
    #: R-274: the rows not projected, each with its certificate, in spec order.
    omitted_rows: tuple[OmittedRow, ...] = ()
    #: R-296: the exact-zero flows eliminated as constants with their pins, in variable order.
    zero_eliminated: tuple[ZeroEliminated, ...] = ()

    @property
    def source_map_sha256(self) -> str:
        return document_sha256(self.source_map)

    @property
    def eliminated_ids(self) -> frozenset[str]:
        """The variable ids of the eliminated zero flows (R-296): constants, not `x`."""
        return frozenset(entry.variable_id for entry in self.zero_eliminated)

    @property
    def variable_indices(self) -> tuple[int, ...]:
        """The spec positions of the projection's `x`: every variable but the eliminated zero
        flows."""
        constants = self.eliminated_ids
        return tuple(i for i, name in enumerate(self.spec.variable_ids) if name not in constants)

    def state_of(self, model: Any = None) -> dict[str, float]:
        """The inverse map: every variable of the spec at `model` (the original by default, or
        TRF's returned clone) — its `x`, and +0.0 for each eliminated zero flow (R-296)."""
        source = self.model if model is None else model
        constants = self.eliminated_ids
        return {
            name: normalize_zero(0.0) if name in constants else float(pyo.value(source.x[index]))
            for index, name in enumerate(self.spec.variable_ids)
        }

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
        TRF's requests only. An eliminated zero flow is the constant +0.0 (R-296): `values` must
        hold 0.0 for it, or this is a `ValueError`."""
        model = self.model
        constants = self.eliminated_ids
        moved = sorted(name for name in constants if float(values[name]) != 0.0)
        if moved:
            raise ValueError(f"{moved} are eliminated zero flows (R-296); they stay 0.0")
        state = {}
        for index, name in enumerate(self.spec.variable_ids):
            if name in constants:
                state[name] = normalize_zero(0.0)
                continue
            state[name] = float(values[name])
            model.x[index].set_value(state[name], skip_validation=True)
        _initialize_outputs(model, self.spec, state)

    def parameters_of(self, model: Any = None) -> dict[str, float]:
        """Every pinned input of the spec at `model` (the original by default, or TRF's returned
        clone): the decisions and the link coordinates as `model` holds them, the rest pinned."""
        source = self.model if model is None else model
        values = {name: float(value) for name, value in self.spec.parameters.items()}
        values.update(self.decision_parameters(source))
        for k, link in enumerate(self.source_map["external_links"]):
            values[link["parameter_id"]] = float(pyo.value(source.w[k]))
        return values

    def omitted_rows_at(self, model: Any) -> OmittedRowsCheck:
        """R-274's fact 4 at the state `model` holds (TRF's returned clone at a final state): every
        omitted row evaluated with floats — its builder, the blocks called directly (never
        through a holder), the parameters `parameters_of(model)` — against its tolerance."""
        return self._rows_at(model, [(row.equation_id, row.tolerance) for row in self.omitted_rows])

    def zero_pins_at(self, model: Any) -> OmittedRowsCheck:
        """R-296's final-state check at the state `model` holds: every pin of an eliminated zero
        flow evaluated with floats, as `omitted_rows_at` evaluates the omitted rows, against
        `ZERO_PIN_TOLERANCE` (0.0: the pin holds exactly by construction). A failure fails P2
        (`PROJECTION_DISAGREES`)."""
        return self._rows_at(
            model, [(entry.row_id, ZERO_PIN_TOLERANCE) for entry in self.zero_eliminated]
        )

    def _rows_at(self, model: Any, rows: Sequence[tuple[str, float]]) -> OmittedRowsCheck:
        if not rows:
            return OmittedRowsCheck(residuals={})
        state = self.state_of(model)
        try:
            outputs = block_outputs(self.spec, state)
        except DomainError as error:
            return OmittedRowsCheck(residuals={}, detail=f"property_domain_error: {error}")
        wanted = {name for name, _ in rows}
        residuals = _float_rows(self.spec, state, outputs, self.parameters_of(model), wanted)
        failed = tuple(name for name, tolerance in rows if not abs(residuals[name]) <= tolerance)
        return OmittedRowsCheck(residuals=residuals, failed=failed)


def _initialize_outputs(model: Any, spec: ProblemSpec, values: Mapping[str, float]) -> None:
    index = 0
    for block in spec.blocks:
        produced = block.values([float(values[name]) for name in spec.block_inputs[block.block_id]])
        for value in produced:
            model.y[index].set_value(float(value), skip_validation=True)
            index += 1


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


def project(
    spec: ProblemSpec,
    x0: Mapping[str, float],
    *,
    decisions: Sequence[DecisionSpec],
    objective: ObjectiveSpec,
    domain: Mapping[str, tuple[float, float]],
    external_links: Sequence[ExternalLinkSpec] = (),
    inequalities: Sequence[InequalitySpec] = (),
    omitted_rows: Collection[str] | None = None,
    shape_check: ShapeCheck = "required",
    variable_bounds: Mapping[str, tuple[float, float]] | None = None,
) -> Projection:
    """Project `spec` at the state `x0` (every variable id → binary64) for TRF (§6.1).

    `domain` gives the bounds of the `temperature` and `pressure` variable kinds — the bound
    property provider's declared domain. Raises `ProjectionRefusedError` for a spec TRF cannot be
    given, and `ValueError` for an inconsistent call.

    The rows not projected are the certified alias rows, computed here (R-274; module docstring).
    `omitted_rows`, if given, must name exactly that set, or the projection is refused
    `PROJECTION_OMITTED_ROW_UNCERTIFIED(<id>)` with the first id, in spec order, on which the two
    differ; an id that is not an equation of the spec is a `ValueError`.

    The flows exactly 0.0 at x₀ are then eliminated as constants with the rows that pin them
    (`M05-zero-flow-v1`, module docstring), before the model TRF sees is built.

    `shape_check="exempt_oracle"` is TR-E1's alone (R-278): the shape check's verdict is recorded
    but does not refuse.

    `variable_bounds` tightens named variables' bounds beyond their kind's (§7.1: a truth's hard
    domain on its inlet T and P): each bound is the intersection, and the source map records the
    result. A name that is not a variable, or an eliminated zero flow (R-300 E5), is a
    `ValueError`."""
    spec.validate()
    _check_call(spec, x0, decisions, external_links)
    scaling = projection_scaling(spec)
    requested = None if omitted_rows is None else frozenset(omitted_rows)
    unknown_rows = sorted((requested or frozenset()) - set(spec.equation_ids))
    if unknown_rows:
        raise ValueError(f"omitted_rows names {unknown_rows}, which are not equations of the spec")

    # R-274's set, on the model with every variable.
    assembly = _assemble(spec, x0, decisions, domain, external_links, variable_bounds, {}, ())
    output_rows = assembly.output_rows
    derivatives = _row_derivatives(
        assembly.model, spec, x0, assembly.built, len(output_rows), len(decisions)
    )
    starts_by_key = {
        f"{row['block_id']}.{row['output_id']}": value
        for row, value in zip(output_rows, assembly.output_starts, strict=True)
    }
    elimination, residuals_x0 = _eliminate(spec, x0, starts_by_key, derivatives.x, domain)
    omitted = {row.row_id for row in elimination}
    if requested is not None and requested != omitted:
        subject = next(
            name for name in spec.equation_ids if (name in requested) != (name in omitted)
        )
        raise ProjectionRefusedError(
            "PROJECTION_OMITTED_ROW_UNCERTIFIED",
            subject,
            f"the caller omits {sorted(requested)}; the certified alias elimination omits "
            f"{sorted(omitted)}",
        )

    # §17.1 (R-296): the exact-zero flows and their pins leave the projection together.
    zero = _eliminate_zero_flows(
        spec, x0, assembly, omitted, residuals_x0, derivatives, external_links
    )
    constants = {entry.variable_id: normalize_zero(0.0) for entry in zero}
    pins = frozenset(entry.row_id for entry in zero)
    bounded = sorted(set(constants) & set(variable_bounds or {}))
    if bounded:
        raise ValueError(f"variable_bounds names {bounded}, which are eliminated zero flows")
    if constants:
        assembly = _assemble(
            spec, x0, decisions, domain, external_links, variable_bounds, constants, pins
        )
    model = assembly.model
    output_rows, output_scales = assembly.output_rows, assembly.output_scales
    symbols, block_outputs, parameters = (
        assembly.symbols,
        assembly.block_outputs,
        assembly.parameters,
    )

    # 5. Rows: the certified alias rows (R-274) and the zero-flow pins (R-296) are not projected.
    row_ids = tuple(name for name in spec.equation_ids if name not in omitted and name not in pins)
    expressions = [assembly.built[name] for name in row_ids]
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
    variable_ids = spec.variable_ids
    projected = [index for index, name in enumerate(variable_ids) if name not in constants]
    model.scaling_factor = pyo.Suffix(direction=pyo.Suffix.EXPORT)
    for index in projected:
        model.scaling_factor[model.x[index]] = 1.0 / scaling.column[variable_ids[index]]
    for k, scale in enumerate(assembly.link_scales):
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
    _check_structure(model, spec, decisions, external_links, output_rows, len(decisions), projected)
    shape = _shape_check(model, spec, row_ids, expressions, output_rows, external_links, projected)
    if shape_check == "required" and shape.refusal is not None:
        raise shape.refusal
    certified = _certify(spec, scaling, decisions, elimination, residuals_x0, derivatives)

    source_map = _source_map(
        spec,
        scaling,
        assembly.bounds,
        row_ids,
        output_rows,
        decisions,
        assembly.centers,
        assembly.half_widths,
        assembly.link_rows,
        inequalities,
        objective,
        certified,
        shape.as_document(shape_check),
        zero,
    )
    return Projection(
        model=model,
        spec=spec,
        decisions=tuple(decisions),
        centers=tuple(assembly.centers),
        half_widths=tuple(assembly.half_widths),
        holders=tuple(assembly.holders),
        holder_inputs=tuple(assembly.holder_inputs),
        row_ids=row_ids,
        row_expressions=tuple(expressions),
        ef_names=assembly.ef_names,
        source_map=source_map,
        scaling=scaling,
        omitted_rows=certified,
        zero_eliminated=zero,
    )


def _assemble(
    spec: ProblemSpec,
    x0: Mapping[str, float],
    decisions: Sequence[DecisionSpec],
    domain: Mapping[str, tuple[float, float]],
    external_links: Sequence[ExternalLinkSpec],
    variable_bounds: Mapping[str, tuple[float, float]] | None,
    constants: Mapping[str, float],
    skip: Collection[str],
) -> _Assembly:
    """§6.1 steps 1-4 and the row expressions, with `constants` (the eliminated zero flows, by
    variable id) in place of their variables and the rows in `skip` (their pins) not built."""
    model = pyo.ConcreteModel(name=spec.label)

    # 1. Variables.
    variable_ids = spec.variable_ids
    variable_index = {name: index for index, name in enumerate(variable_ids)}
    bounds = [_variable_bounds(spec, name, float(x0[name]), domain) for name in variable_ids]
    for name, (low, high) in (variable_bounds or {}).items():
        if name not in variable_index:
            raise ValueError(f"variable_bounds names {name!r}, which is not a variable")
        before_low, before_high = bounds[variable_index[name]]
        bounds[variable_index[name]] = (
            float(low) if before_low is None else max(before_low, float(low)),
            float(high) if before_high is None else min(before_high, float(high)),
        )
    projected = [index for index, name in enumerate(variable_ids) if name not in constants]
    model.x = pyo.Var(
        projected if constants else range(len(variable_ids)),
        initialize={index: float(x0[variable_ids[index]]) for index in projected},
        bounds=lambda m, index: bounds[index],
    )
    symbols: dict[str, Any] = {
        name: constants[name] if name in constants else model.x[index]
        for index, name in enumerate(variable_ids)
    }

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
    holder_inputs: list[tuple[int, ...]] = []
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
        holder_inputs.append(tuple(variable_index[name] for name in link.inlet_variable_ids))
        inlet = [symbols[name] for name in link.inlet_variable_ids]
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
        holder_inputs.append(tuple(variable_index[name] for name in feeding))
        inputs = [symbols[name] for name in feeding]
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

    # 5. The rows' expressions (the constraints are made once the projected rows are known).
    built = {
        equation.equation_id: _build(
            equation.equation_id, equation.build, symbols, block_outputs, parameters, spec
        )
        for equation in spec.equations
        if equation.equation_id not in skip
    }
    return _Assembly(
        model=model,
        bounds=bounds,
        centers=centers,
        half_widths=half_widths,
        holders=holders,
        holder_inputs=holder_inputs,
        ef_names=ef_names,
        link_rows=link_rows,
        link_scales=link_scales,
        output_rows=output_rows,
        output_starts=output_starts,
        output_scales=output_scales,
        symbols=symbols,
        block_outputs=block_outputs,
        parameters=parameters,
        built=built,
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
    projected: Sequence[int],
) -> None:
    """Every declared variable in some constraint, and TRF's DOF count equal to the decisions.
    `projected` are the spec positions of `x` (the eliminated zero flows are not variables)."""
    seen = ComponentSet()
    equalities = 0
    for constraint in model.component_data_objects(pyo.Constraint, active=True):
        seen.update(identify_variables(constraint.expr, include_fixed=True))
        if constraint.equality:
            equalities += 1
    declared = [
        *((model.x[i], spec.variable_ids[i]) for i in projected),
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


@dataclass(frozen=True)
class _RowDerivatives:
    """Every row's derivatives at x₀, in spec order: `x`, the total x-Jacobian — through the block
    outputs, so it is the Jacobian of the function the compiled problem holds — and `d`, the
    decision columns (per unit of the scaled decision)."""

    x: npt.NDArray[np.float64]
    d: npt.NDArray[np.float64]


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


# -- the exact-zero flows (R-296) -----------------------------------------------------------------


def _eliminate_zero_flows(
    spec: ProblemSpec,
    x0: Mapping[str, float],
    assembly: _Assembly,
    omitted: Collection[str],
    residuals_x0: Mapping[str, float],
    derivatives: _RowDerivatives,
    links: Sequence[ExternalLinkSpec],
) -> tuple[ZeroEliminated, ...]:
    """`M05-zero-flow-v1` (module docstring) on the model with every variable: the candidates
    Z₀, the certified pairs (j, e) found by repeated passes over the kept rows in spec order, and
    the three refusals. Returns the pairs in variable order."""
    variable_ids = spec.variable_ids
    candidates = [
        name
        for name in variable_ids
        if spec.variable_kinds.get(name) == "molar_flow" and float(x0[name]) == 0.0
    ]
    if not candidates:
        return ()
    model = assembly.model
    # A row's structural incidence: the unknowns of the shape check (x, y, w) its expression
    # contains — never the decisions, whose derivative is criterion (iii).
    column = ComponentMap(
        [
            *((model.x[i], name) for i, name in enumerate(variable_ids)),
            *((model.y[g], f"y[{g}]") for g in range(len(assembly.output_rows))),
            *((model.w[k], f"w[{k}]") for k in range(len(assembly.link_rows))),
        ]
    )
    incidence = {
        name: frozenset(column[v] for v in identify_variables(expression) if v in column)
        for name, expression in assembly.built.items()
    }
    position = {name: i for i, name in enumerate(spec.equation_ids)}
    index = {name: i for i, name in enumerate(variable_ids)}
    zero = set(candidates)
    found: dict[str, ZeroEliminated] = {}
    changed = True
    while changed:
        changed = False
        for row in spec.equation_ids:
            if row in omitted or any(entry.row_id == row for entry in found.values()):
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
                changed = True
    unpinned = [name for name in candidates if name not in found]
    if unpinned:
        raise ProjectionRefusedError(
            "PROJECTION_ZERO_FLOW",
            f"{unpinned[0]}:unpinned",
            f"the flows {unpinned} are exactly 0.0 at x0 and no kept row pins them alone with a "
            "zero residual, a nonzero pivot and a zero decision tangent at x0 (R-296)",
        )
    pins = {entry.row_id for entry in found.values()}
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
    return tuple(found[name] for name in variable_ids if name in found)


def _float_rows(
    spec: ProblemSpec,
    state: Mapping[str, float],
    outputs: Mapping[str, float],
    parameters: Mapping[str, float],
    wanted: Collection[str] | None = None,
) -> dict[str, float]:
    """The rows (`wanted`, or every one) evaluated with floats, as `compile/reference.py` does,
    with the given block outputs and parameters."""
    algebra = FloatAlgebra()
    return {
        equation.equation_id: float(equation.build(state, outputs, parameters, algebra))
        for equation in spec.equations
        if wanted is None or equation.equation_id in wanted
    }


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
    omitted: Sequence[OmittedRow],
    shape_check: Mapping[str, Any],
    zero: Sequence[ZeroEliminated],
) -> dict[str, Any]:
    """`projection-source-map-v1` (§6.2), without its `trf` part, which a run fills."""
    structure = structure_sha256(
        spec.variable_ids, spec.equation_ids, spec.parameter_ids, spec.row_accumulation
    )
    origins = {equation.equation_id: equation.origin for equation in spec.equations}
    eliminated = {entry.variable_id for entry in zero}
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
                "pyomo": None if name in eliminated else f"x[{index}]",
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
        "omitted_rows": [row.as_document() for row in omitted],
        "zero_eliminated": [entry.as_document() for entry in zero],
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
        "shape_check": dict(shape_check),
        "trf": [],
    }
