"""An optimization problem over a flowsheet's pinned inputs, and its full-space form over the
parametric twin. M03 spec §8.1-§8.4; ADR 0032 D1, D2, D4.

**Declaration.** Decisions are pinned inputs (ADR 0031 D1), each with a box and a scale. The
objective and the inequality constraints are linear or quadratic expressions of named state
variables — no other form in M03 — and each constraint is a constraint with explicit bounds, never
a penalty term (blueprint §10: a penalty is not constraint satisfaction).

**Full space** (D1). The variables are all the state variables and the decisions; the equality
constraints are the kept rows `F_K(x; p(d))`, evaluated by the parametric twin with the decisions
symbolic, and their Jacobian is the twin's exact `[F_x,K  F_p,K]`. The base compiled problem bakes
the start's decisions in and is not used during a solve.

**Bounds** (D4, spec §8.2) are true domain restrictions: decisions their box; temperatures and
pressures the property provider's declared domain, outside which a property block refuses; molar
flows a lower bound of 0, **except** a flow that is exactly 0.0 at the verified start, which is left
unbounded — the declared regime's own rows pin it there (the liquid heater's vapour), and a bound on
it would be weakly active with a gradient dependent on the equality rows, breaking LICQ. If the
regime changed, such a flow is free to go negative; verification (V2, V4) then catches it. Heat
rates are unbounded.

**Scaling** is the K03 nominals: variables `1/S_x`, decisions `1/s_d`, equality rows `1/S_F`,
objective and constraints 1 (they are declared scaled).

**Assessment outputs** (E01 §4.10.2). With an `AssessmentBinding`, an expression may also name
`assessment:<id>`, a bound output of an assessment program; the gray box then has outputs — the
bound outputs and the admissibility rows of their dependency closure — evaluated by the program's
twin with the decisions symbolic. Without one, there are no outputs and nothing here differs.

**Hessian** (D2): `Capabilities.hessian` is `absent`; the solver is configured with Ipopt's
limited-memory approximation and a request for an exact Hessian is refused `HESSIAN_UNAVAILABLE`
before any solver call. No finite-difference, Gauss-Newton or zero Hessian exists anywhere.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Final

import numpy as np
import numpy.typing as npt
import scipy.sparse as sp

from openflowsheet.assessment.quantities import ASSESSMENT_PREFIX
from openflowsheet.compile.casadi_backend import ParametricTwin, compile_parametric_twin
from openflowsheet.compile.reference import state_vector
from openflowsheet.models.syn001.flowsheet import Syn001Flowsheet
from openflowsheet.orchestrator.tear import Syn001TearProblem

if TYPE_CHECKING:
    from openflowsheet.assessment.program import AssessmentProgram

#: Spec §8.3: the only Hessian policy M03 accepts, and how every report records it.
HESSIAN_APPROXIMATION: Final = "limited-memory"
LIMITED_MEMORY_HISTORY: Final = 6
HESSIAN_POLICY: Final[Mapping[str, Any]] = {
    "capability": "absent",
    "approximation": "ipopt-limited-memory",
    "history": LIMITED_MEMORY_HISTORY,
}
#: Spec §8.4, pinned and recorded verbatim in every report. Provisional until WO-8 measures the
#: achieved termination (spec §14 Q-F2).
IPOPT_OPTIONS: Final[Mapping[str, Any]] = {
    "hessian_approximation": HESSIAN_APPROXIMATION,
    "limited_memory_max_history": LIMITED_MEMORY_HISTORY,
    "linear_solver": "mumps",
    "nlp_scaling_method": "user-scaling",
    "tol": 1e-10,
    "constr_viol_tol": 1e-8,
    "dual_inf_tol": 1e-6,
    "compl_inf_tol": 1e-8,
    "acceptable_tol": 1e-8,
    "acceptable_iter": 15,
    "max_iter": 500,
    "max_wall_time": 120,
    "bound_relax_factor": 0,
    "honor_original_bounds": "yes",
    "mu_strategy": "monotone",
    "print_level": 0,
}
FORMULATION_KIND: Final = "full_space"


# -- the declaration ------------------------------------------------------------------------------


@dataclass(frozen=True)
class QuadraticExpression:
    """`constant + Σ a_i x_i + Σ q_ij x_i x_j` over named state variables (spec §8.2)."""

    linear: Mapping[str, float] = field(default_factory=dict)
    quadratic: Mapping[tuple[str, str], float] = field(default_factory=dict)
    constant: float = 0.0
    #: How the problem states it, recorded in the report beside the coefficients.
    text: str = ""

    def __post_init__(self) -> None:
        if not self.variables:
            raise ValueError("an expression names at least one state variable")
        values = [*self.linear.values(), *self.quadratic.values(), self.constant]
        if not all(math.isfinite(value) for value in values):
            raise ValueError("expression coefficients must be finite")

    @property
    def variables(self) -> tuple[str, ...]:
        """Every variable the expression names, in first-mention order."""
        named = list(self.linear)
        for first, second in self.quadratic:
            named.extend((first, second))
        return tuple(dict.fromkeys(named))

    def value(self, state: Mapping[str, float]) -> float:
        terms = [self.constant]
        terms.extend(coefficient * state[name] for name, coefficient in self.linear.items())
        terms.extend(
            coefficient * state[first] * state[second]
            for (first, second), coefficient in self.quadratic.items()
        )
        return math.fsum(terms)

    def gradient(self, state: Mapping[str, float]) -> dict[str, float]:
        """`∂/∂x` at `state`, over `variables` (a zero entry is kept: the functional is the
        expression's linearization, whatever its value)."""
        parts: dict[str, list[float]] = {name: [] for name in self.variables}
        for name, coefficient in self.linear.items():
            parts[name].append(coefficient)
        for (first, second), coefficient in self.quadratic.items():
            parts[first].append(coefficient * state[second])
            parts[second].append(coefficient * state[first])
        return {name: math.fsum(values) for name, values in parts.items()}

    def as_document(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "constant": self.constant,
            "linear": dict(self.linear),
            "quadratic": [
                {"variables": [first, second], "coefficient": coefficient}
                for (first, second), coefficient in self.quadratic.items()
            ],
        }


@dataclass(frozen=True)
class Decision:
    """A decision: a pinned input with a box and a scale (spec §8.1). The box is not checked
    here, so that `optimization_readiness` can report a missing or empty one
    (`BOUNDS_UNDECLARED`) rather than an exception."""

    parameter_id: str
    lower: float | None
    upper: float | None
    scale: float

    def __post_init__(self) -> None:
        if not (math.isfinite(self.scale) and self.scale > 0.0):
            raise ValueError(f"{self.parameter_id}: a scale divides, so it must be finite and > 0")

    @property
    def bounded(self) -> bool:
        return (
            self.lower is not None
            and self.upper is not None
            and math.isfinite(self.lower)
            and math.isfinite(self.upper)
            and self.lower < self.upper
        )

    def as_document(self) -> dict[str, Any]:
        return {
            "id": self.parameter_id,
            "lower": self.lower,
            "upper": self.upper,
            "scale": self.scale,
        }


@dataclass(frozen=True)
class InequalityConstraint:
    """`lower ≤ g(x) ≤ upper`, at least one side present; `g` is declared scaled (spec §8.2)."""

    constraint_id: str
    expression: QuadraticExpression
    lower: float | None = None
    upper: float | None = None

    def __post_init__(self) -> None:
        if self.lower is None and self.upper is None:
            raise ValueError(f"{self.constraint_id}: a constraint has at least one bound")

    def as_document(self) -> dict[str, Any]:
        return {
            "id": self.constraint_id,
            "expression": self.expression.as_document(),
            "lower": self.lower,
            "upper": self.upper,
        }


class AssessmentOutputUnknownError(ValueError):
    """`ASSESSMENT_OUTPUT_UNKNOWN` (E01 §4.10.2): a formulation names `assessment:<id>` that its
    binding does not declare, or that the program does not publish. Raised before any solve."""

    code: Final = "ASSESSMENT_OUTPUT_UNKNOWN"

    def __init__(self, names: Sequence[str]) -> None:
        self.names = tuple(names)
        super().__init__(f"{self.code}({','.join(self.names)})")


def assessment_names(names: Sequence[str]) -> tuple[str, ...]:
    """The output ids of the `assessment:<id>` names among `names`, in their order."""
    return tuple(name[len(ASSESSMENT_PREFIX) :] for name in names if is_assessment_name(name))


def is_assessment_name(name: str) -> bool:
    return name.startswith(ASSESSMENT_PREFIX)


@dataclass(frozen=True)
class AssessmentBinding:
    """The assessment a formulation may name (E01 §4.10.2): a program at its held regime, the
    output ids the formulation may reference as `assessment:<id>`, and each one's scale.

    The scales are fixed per formulation, so that every start is scaled alike and the report
    records one scale per output; `at` takes them as §4.10.2's `max(|y(x₀)|, 1)` at a state."""

    program: AssessmentProgram
    outputs: tuple[str, ...]
    output_scales: Mapping[str, float]

    def __post_init__(self) -> None:
        if not self.outputs or len(set(self.outputs)) != len(self.outputs):
            raise ValueError(f"binding outputs must be present and distinct: {self.outputs}")
        if set(self.output_scales) != set(self.outputs):
            raise ValueError("a binding gives exactly one scale per output")
        bad = [n for n, v in self.output_scales.items() if not (math.isfinite(v) and v > 0.0)]
        if bad:
            raise ValueError(f"output scales divide, so they must be finite and > 0: {bad}")

    @classmethod
    def at(
        cls, program: AssessmentProgram, outputs: Sequence[str], state: Mapping[str, float]
    ) -> AssessmentBinding:
        """The binding with each output's scale `max(|y(state)|, 1)` (§4.10.2), `y` on the
        float reference path. Raises `TwinEvaluationError` where `y` cannot be evaluated."""
        values = program.evaluate(state)
        if not isinstance(values, Mapping):
            raise ValueError(f"the program refuses evaluation: {values}")
        unknown = [name for name in outputs if name not in values]
        if unknown:
            raise AssessmentOutputUnknownError(unknown)
        return cls(
            program,
            tuple(outputs),
            {name: max(abs(float(values[name])), 1.0) for name in outputs},
        )

    @property
    def unknown(self) -> tuple[str, ...]:
        """Declared outputs the program does not publish (or publishes only as an admissibility
        row, which a formulation never names)."""
        published = set(self.program.output_ids) - set(self.program.admissibility_ids)
        return tuple(name for name in self.outputs if name not in published)


@dataclass(frozen=True)
class NlpFormulation:
    """Spec §8.1: decisions, a minimized objective, inequality constraints, starts (each a value
    per decision, in decision order) and the Hessian policy requested."""

    problem_id: str
    decisions: tuple[Decision, ...]
    objective: QuadraticExpression
    constraints: tuple[InequalityConstraint, ...]
    starts: tuple[tuple[float, ...], ...]
    hessian: str = HESSIAN_APPROXIMATION
    #: E01 §4.10.2: the assessment `assessment:<id>` names refer to; `None` names none.
    assessment: AssessmentBinding | None = None

    def __post_init__(self) -> None:
        ids = [decision.parameter_id for decision in self.decisions]
        if not ids or len(set(ids)) != len(ids):
            raise ValueError(f"decision ids must be present and distinct: {ids}")
        names = [constraint.constraint_id for constraint in self.constraints]
        if len(set(names)) != len(names):
            raise ValueError(f"constraint ids repeat: {names}")
        if not self.starts or any(len(start) != len(ids) for start in self.starts):
            raise ValueError("at least one start, each with one value per decision")

    @property
    def decision_ids(self) -> tuple[str, ...]:
        return tuple(decision.parameter_id for decision in self.decisions)

    def decision_values(self, values: Sequence[float]) -> dict[str, float]:
        return {
            decision.parameter_id: float(value)
            for decision, value in zip(self.decisions, values, strict=True)
        }

    def _named(self) -> tuple[str, ...]:
        named = list(self.objective.variables)
        for constraint in self.constraints:
            named.extend(constraint.expression.variables)
        return tuple(dict.fromkeys(named))

    @property
    def variables(self) -> tuple[str, ...]:
        """Every state variable the objective and constraints name (not `assessment:<id>`)."""
        return tuple(name for name in self._named() if not is_assessment_name(name))

    @property
    def assessment_outputs(self) -> tuple[str, ...]:
        """The output ids the objective and constraints name as `assessment:<id>`, in
        first-mention order (E01 §4.10.2)."""
        return assessment_names(self._named())

    def unknown_assessment_outputs(self) -> tuple[str, ...]:
        """Named assessment outputs without a binding, not declared by it, or not published by
        its program: `ASSESSMENT_OUTPUT_UNKNOWN`."""
        named = self.assessment_outputs
        if self.assessment is None:
            return named
        declared = set(self.assessment.outputs) - set(self.assessment.unknown)
        return tuple(name for name in named if name not in declared)

    def as_document(self) -> dict[str, Any]:
        return {
            "problem_id": self.problem_id,
            "kind": FORMULATION_KIND,
            "decisions": [decision.as_document() for decision in self.decisions],
            "objective": {"sense": "minimize", **self.objective.as_document()},
            "constraints": [constraint.as_document() for constraint in self.constraints],
            "starts": [list(start) for start in self.starts],
            "hessian": self.hessian,
        }


# -- the full-space problem -----------------------------------------------------------------------


@dataclass(frozen=True)
class AssessmentClosure:
    """E01 §4.10.2's gray-box outputs of a binding: the bound outputs in catalogue (program)
    order, then every admissibility row whose regime entry is in their dependency closure, in
    catalogue order; each with its scale, and each admissibility row with its nominal."""

    outputs: tuple[str, ...]
    admissibility: tuple[str, ...]
    scales: Mapping[str, float]
    nominals: Mapping[str, float]

    @property
    def output_ids(self) -> tuple[str, ...]:
        return (*self.outputs, *self.admissibility)


def assessment_twin(
    binding: AssessmentBinding, variable_ids: Sequence[str], decision_ids: Sequence[str]
) -> ParametricTwin:
    """The binding program's twin with the decisions symbolic, over the host's variables."""
    program = binding.program
    twin = program.twin(tuple(decision_ids))
    if not isinstance(twin, ParametricTwin):
        raise ValueError(f"the assessment twin is refused: {twin}")
    if tuple(program.context.host_spec.variable_ids) != tuple(variable_ids):
        raise ValueError("the assessment program's host is not this flowsheet's spec")
    if tuple(twin.parameter_ids) != tuple(decision_ids):
        raise ValueError("the assessment twin's symbols are not the decisions")
    return twin


def assessment_closure(
    binding: AssessmentBinding,
    twin: ParametricTwin,
    x: npt.NDArray[np.float64],
    decisions: Mapping[str, float],
) -> AssessmentClosure:
    """An admissibility row is a gray-box output when its regime entry is in the dependency
    closure of a bound output: some row of the entry has a structural nonzero in a column (state
    or decision) of `[G_x  G_d]` at `(x, d)` in which some bound output has one."""
    program = binding.program
    jacobian = _twin_jacobian(twin, x, decisions).tocsr()
    pattern = {
        name: set(jacobian.indices[jacobian.indptr[i] : jacobian.indptr[i + 1]].tolist())
        for i, name in enumerate(program.output_ids)
    }
    outputs = [name for name in program.output_ids if name in set(binding.outputs)]
    used = set().union(*(pattern[name] for name in outputs))
    rows_of: dict[str, list[str]] = {}
    nominal: dict[str, float] = {}
    for entry in program.entries:
        for row in entry.admissibility:
            name = f"adm.{entry.entry_id}.{row.row_id}"
            rows_of.setdefault(entry.entry_id, []).append(name)
            nominal[name] = row.nominal
    closure = {
        name
        for names in rows_of.values()
        if any(pattern[name] & used for name in names)
        for name in names
    }
    admissibility = [name for name in program.admissibility_ids if name in closure]
    scales = {name: float(binding.output_scales[name]) for name in outputs}
    # The program's admissibility rows are `a/nominal` already (§4.3.1): their scale is 1.
    scales.update({name: 1.0 for name in admissibility})
    return AssessmentClosure(
        tuple(outputs),
        tuple(admissibility),
        MappingProxyType(scales),
        MappingProxyType({name: nominal[name] for name in admissibility}),
    )


def _twin_jacobian(
    twin: ParametricTwin, x: npt.NDArray[np.float64], decisions: Mapping[str, float]
) -> sp.csc_matrix:
    state = _sparse(twin.jacobian_x(x, decisions))
    parameter = _sparse(twin.jacobian_p(x, decisions))
    return sp.csc_matrix(sp.hstack([state, parameter], format="csc"))


@dataclass(frozen=True)
class VariableBound:
    """One primal's bounds (`None` is unbounded on that side) and why (spec §8.2)."""

    lower: float | None
    upper: float | None
    reason: str


class FullSpaceNlp:
    """Spec §8.2's formulation at one verified start: the primal `z = (x, d)` — the state
    variables in `variable_ids` order, then the decisions in declaration order — the kept rows as
    equality constraints, their exact Jacobian from the twin, the bounds, the scaling and the
    initial point. Evaluation errors from a property block propagate as the twin's
    `TwinEvaluationError`; the solver adapter maps them to a rejected trial point (spec §8.2,
    Q-F4), never to a NaN or a clipped value.
    """

    def __init__(
        self,
        flowsheet: Syn001Flowsheet,
        formulation: NlpFormulation,
        start_state: Mapping[str, float],
        start: Sequence[float],
    ) -> None:
        tear = Syn001TearProblem(flowsheet)
        self.spec = tear.spec
        self.formulation = formulation
        self.scaling = tear.scaling
        eliminated = {row.row_id for row in tear.partition.elimination.eliminated}
        self.equality_ids = tuple(name for name in self.spec.equation_ids if name not in eliminated)
        self.eliminated_ids = tuple(name for name in self.spec.equation_ids if name in eliminated)
        self.variable_ids = self.spec.variable_ids
        self.decision_ids = formulation.decision_ids
        self.primal_ids = self.variable_ids + self.decision_ids
        self.twin: ParametricTwin = compile_parametric_twin(self.spec, self.decision_ids)
        self._kept = np.array(
            [self.spec.equation_ids.index(name) for name in self.equality_ids], dtype=np.intp
        )
        self.start = tuple(float(value) for value in start)
        self.start_state = dict(start_state)
        self.bounds = self._bounds(flowsheet)
        self.counters = {"residual_calls": 0, "jacobian_calls": 0}
        unknown = formulation.unknown_assessment_outputs()
        if unknown:
            raise AssessmentOutputUnknownError(unknown)
        self.assessment = formulation.assessment
        #: E01 §4.10.2: the gray box's outputs — the bound outputs, then the admissibility rows
        #: in their closure — each with its scale; empty without an assessment.
        self.output_ids: tuple[str, ...] = ()
        self.output_scales: dict[str, float] = {}
        self.admissibility_nominals: dict[str, float] = {}
        self.closure: AssessmentClosure | None = None
        if self.assessment is not None:
            self._bind(self.assessment)

    def _bind(self, binding: AssessmentBinding) -> None:
        """The gray box's outputs over the program's twin with the decisions symbolic (E01
        §4.10.2): `assessment_closure` at the start."""
        self.assessment_twin: ParametricTwin = assessment_twin(
            binding, self.variable_ids, self.decision_ids
        )
        self._assessment_calls = _block_calls(self.assessment_twin)
        x, decisions = self.split(self.initial_point())
        closure = assessment_closure(binding, self.assessment_twin, x, decisions)
        program = binding.program
        self.closure = closure
        self.output_ids = closure.output_ids
        self._outputs = np.array(
            [program.output_ids.index(name) for name in self.output_ids], dtype=np.intp
        )
        self.output_scales = dict(closure.scales)
        self.admissibility_nominals = dict(closure.nominals)

    def _assessment_jacobian(
        self, x: npt.NDArray[np.float64], decisions: Mapping[str, float]
    ) -> sp.csc_matrix:
        return _twin_jacobian(self.assessment_twin, x, decisions)

    # -- primal layout -------------------------------------------------------------------------

    @property
    def n_variables(self) -> int:
        return len(self.variable_ids)

    def split(self, z: npt.NDArray[np.float64]) -> tuple[npt.NDArray[np.float64], dict[str, float]]:
        """`z` → (the state vector, the decisions by id)."""
        if z.shape != (len(self.primal_ids),):
            raise ValueError(f"primal has shape {z.shape}; expected ({len(self.primal_ids)},)")
        n = self.n_variables
        return z[:n], {
            name: float(value) for name, value in zip(self.decision_ids, z[n:], strict=True)
        }

    def initial_point(self) -> npt.NDArray[np.float64]:
        """The verified simulation state at the start decisions (spec §8.2)."""
        return np.concatenate(
            [np.array(state_vector(self.spec, self.start_state)), np.array(self.start)]
        )

    # -- evaluation ----------------------------------------------------------------------------

    def equality_residual(self, z: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
        """`F_K(x; d)`, the kept rows in `equation_ids` order, from the twin."""
        self.counters["residual_calls"] += 1
        x, decisions = self.split(z)
        return np.asarray(self.twin.residual(x, decisions), dtype=np.float64)[self._kept]

    def equality_jacobian(self, z: npt.NDArray[np.float64]) -> sp.csc_matrix:
        """`[F_x,K  F_p,K]` at `z`: rows the kept rows, columns `primal_ids`; exact, one graph."""
        self.counters["jacobian_calls"] += 1
        x, decisions = self.split(z)
        state = _sparse(self.twin.jacobian_x(x, decisions))
        parameter = _sparse(self.twin.jacobian_p(x, decisions))
        return sp.csc_matrix(sp.hstack([state, parameter], format="csc")[self._kept, :])

    def output_values(self, z: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
        """The gray box's outputs `G(x; d)` in `output_ids` order, from the assessment twin."""
        self.counters["output_calls"] = self.counters.get("output_calls", 0) + 1
        x, decisions = self.split(z)
        values = np.asarray(self.assessment_twin.residual(x, decisions), dtype=np.float64)
        return values[self._outputs]

    def output_jacobian(self, z: npt.NDArray[np.float64]) -> sp.csc_matrix:
        """`[G_x  G_d]` at `z`: rows `output_ids`, columns `primal_ids`; exact, canonical CSC."""
        self.counters["output_jacobian_calls"] = self.counters.get("output_jacobian_calls", 0) + 1
        x, decisions = self.split(z)
        return sp.csc_matrix(self._assessment_jacobian(x, decisions)[self._outputs, :])

    def assessment_property_calls(self) -> int:
        """Property-block callbacks of the assessment twin since this problem was built."""
        if self.assessment is None:
            return 0
        return _block_calls(self.assessment_twin) - self._assessment_calls

    # -- bounds and scaling --------------------------------------------------------------------

    def _bounds(self, flowsheet: Syn001Flowsheet) -> dict[str, VariableBound]:
        domain = flowsheet.provider.describe().domain
        temperature, pressure = domain["T"], domain["P"]
        bounds: dict[str, VariableBound] = {}
        for name in self.variable_ids:
            kind = self.spec.variable_kinds[name]
            if kind == "temperature":
                bounds[name] = VariableBound(*temperature, "provider_domain")
            elif kind == "pressure":
                bounds[name] = VariableBound(*pressure, "provider_domain")
            elif kind == "molar_flow":
                if self.start_state[name] == 0.0:
                    bounds[name] = VariableBound(None, None, "zero_at_start_pinned_by_regime")
                else:
                    bounds[name] = VariableBound(0.0, None, "nonnegative_flow")
            elif kind == "heat_rate":
                bounds[name] = VariableBound(None, None, "heat_rate_unbounded")
            else:
                raise ValueError(f"{name}: no M03 bound policy for variable kind {kind!r}")
        for decision in self.formulation.decisions:
            bounds[decision.parameter_id] = VariableBound(
                decision.lower, decision.upper, "decision_box"
            )
        return bounds

    def bound_arrays(self) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
        """Lower and upper bounds over `primal_ids`, `∓inf` where unbounded."""
        lower = [self.bounds[name].lower for name in self.primal_ids]
        upper = [self.bounds[name].upper for name in self.primal_ids]
        return (
            np.array([-math.inf if value is None else value for value in lower]),
            np.array([math.inf if value is None else value for value in upper]),
        )

    def primal_scaling(self) -> npt.NDArray[np.float64]:
        """Ipopt's user scaling of the primal: `1/S_x`, then `1/s_d`."""
        state = [1.0 / self.scaling.column[name] for name in self.variable_ids]
        decisions = [1.0 / decision.scale for decision in self.formulation.decisions]
        return np.array(state + decisions)

    def equality_scaling(self) -> npt.NDArray[np.float64]:
        """Ipopt's user scaling of the kept rows: `1/S_F`."""
        return np.array([1.0 / self.scaling.row[name] for name in self.equality_ids])

    def output_scaling(self) -> npt.NDArray[np.float64]:
        """Ipopt's user scaling of the gray box's output rows: `1/scale` (E01 §4.10.2)."""
        return np.array([1.0 / self.output_scales[name] for name in self.output_ids])

    def as_document(self) -> dict[str, Any]:
        return {
            "kind": FORMULATION_KIND,
            "primal_ids": list(self.primal_ids),
            "equality_ids": list(self.equality_ids),
            "eliminated_rows": list(self.eliminated_ids),
            "bounds": {
                name: {"lower": bound.lower, "upper": bound.upper, "reason": bound.reason}
                for name, bound in self.bounds.items()
            },
            "objective_scaling": 1.0,
            "constraint_scaling": 1.0,
        }


def _sparse(matrix: Any) -> sp.csc_matrix:
    return sp.csc_matrix(
        (np.array(matrix.data), np.array(matrix.indices), np.array(matrix.indptr)),
        shape=(len(matrix.row_ids), len(matrix.col_ids)),
    )


def _block_calls(twin: ParametricTwin) -> int:
    return sum(c["value_calls"] + c["jacobian_calls"] for c in twin.block_calls().values())
