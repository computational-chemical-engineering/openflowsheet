"""The assessment program: cost and impact as explicit functionals `y = G(x, d; θ, ρ)` of a solved
state, compiled by the existing compiler (E01 design §4.2; ADR 0052 D1, D2; register R-850, R-851).

A set of functionals is assembled as a *functional* `ProblemSpec`: the host's variables in the
host's order, one `algebraic` row per output and per admissibility row, the host's pinned inputs
plus the assessment parameters `θ` as parameters, and the property blocks the sizing needs. It is
compiled by the unchanged `ParametricTwin` (value, `∂/∂x`, `∂/∂p` from one graph) and evaluated on
floats by `compile.reference.row_values`, from the same builders. It is never handed to a solver
or a certificate and no `CompiledProblem` of it exists: an attached assessment changes nothing the
simulation, its certificate or its replay identity depends on.

Contributors (`cost`, `lca`, `derived`, in that order) plan their outputs from the document, the
view and the state; each regime choice is made in that planning pass on floats and handed to the
builders as data (§4.2.2). The builders never branch on a symbol.
"""

from __future__ import annotations

import dataclasses
import math
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Final, Literal, Protocol

import numpy as np

from openflowsheet.assessment.quantities import ASSESSMENT_PREFIX, classify
from openflowsheet.assessment.regimes import Regime, RegimeEntry
from openflowsheet.assessment.spec import AssessmentSpec
from openflowsheet.assessment.views import FlowsheetView
from openflowsheet.compile.casadi_backend import (
    ParametricTwin,
    TwinEvaluationError,
    TwinMatrix,
    compile_parametric_twin,
)
from openflowsheet.compile.reference import row_values
from openflowsheet.compile.spec import (
    Algebra,
    DomainError,
    EquationSpec,
    Expr,
    ProblemSpec,
    PropertyBlock,
)

__all__ = [
    "CONTRIBUTOR_ORDER",
    "THETA_PREFIX",
    "AssessmentProgram",
    "BuildContext",
    "ContributionPlan",
    "Contributor",
    "FunctionalBuilder",
    "Limitation",
    "Linearization",
    "OutputDef",
    "Refusal",
    "Symbols",
    "Theta",
    "register_contributor",
]

#: §4.2.2: contributors run in this order; `derived` may reference any earlier output.
CONTRIBUTOR_ORDER: Final[tuple[str, ...]] = ("cost", "lca", "derived")
#: §4.2.3: assessment parameters are `asm:<path>`; no host pinned input has this prefix.
THETA_PREFIX: Final = "asm:"

#: `(symbols, algebra) -> expression` (§4.2.2).
FunctionalBuilder = Callable[["Symbols", Algebra], Expr]


# -- typed results (§4.12) -----------------------------------------------------------------------


@dataclass(frozen=True)
class Refusal:
    """A typed refusal (or an `unsupported` result): never an exception to the caller (§4.12)."""

    code: str
    target: str = ""
    detail: str = ""
    kind: Literal["refusal", "unsupported"] = "refusal"

    def as_document(self) -> dict[str, Any]:
        return {"kind": self.kind, "code": self.code, "target": self.target, "detail": self.detail}


@dataclass(frozen=True)
class Limitation:
    """A typed limitation of a computed result (§4.12)."""

    code: str
    target: str = ""
    detail: Mapping[str, Any] = field(default_factory=dict)

    def as_document(self) -> dict[str, Any]:
        return {"code": self.code, "target": self.target, **dict(self.detail)}


# -- the plug-in protocol (§4.2.2) ---------------------------------------------------------------


@dataclass(frozen=True)
class Theta:
    """One assessment parameter: `asm:<path>`, its value, unit and provenance (§4.2.3).

    `structural` marks a value that selects a regime or is an integer, a material or `E_o`: it is
    never symbolic, and a request to make it so is refused `ASSESSMENT_PARAMETER_STRUCTURAL`.
    `relative_range` is the declared `[lo, hi]` of §4.9's propagation, when there is one.
    """

    theta_id: str
    value: float
    unit: str
    provenance: str
    relative_range: tuple[float, float] | None = None
    structural: bool = False

    def __post_init__(self) -> None:
        if not self.theta_id.startswith(THETA_PREFIX):
            raise ValueError(f"θ id {self.theta_id!r} does not start with {THETA_PREFIX!r}")
        if not math.isfinite(self.value):
            raise ValueError(f"θ {self.theta_id!r} has the non-finite value {self.value!r}")


@dataclass(frozen=True)
class OutputDef:
    output_id: str
    unit: str
    build: FunctionalBuilder


@dataclass(frozen=True)
class ContributionPlan:
    outputs: tuple[OutputDef, ...] = ()
    theta: tuple[Theta, ...] = ()
    #: Each block with the host variable ids feeding it, in its input order.
    blocks: tuple[tuple[PropertyBlock, tuple[str, ...]], ...] = ()
    regime_entries: tuple[RegimeEntry, ...] = ()
    refusals: tuple[Refusal, ...] = ()
    limitations: tuple[Limitation, ...] = ()
    #: The contributor's report section from evaluated values (§4.2.2; written at WO-A5).
    section: Callable[[Mapping[str, float]], dict[str, Any]] | None = None
    #: Outputs withheld because they would depend on a refused, not excluded item, or on an
    #: input the document lacks: `(output_id, reason)`. The report prints them as `null` and a
    #: study naming one is refused `ASSESSMENT_OUTPUT_UNAVAILABLE` (§4.9, A40).
    unavailable: tuple[tuple[str, str], ...] = ()


class Contributor(Protocol):
    name: str

    def plan(self, ctx: BuildContext, state: Mapping[str, float]) -> ContributionPlan: ...


_REGISTERED: dict[str, Callable[[], Contributor]] = {}


def register_contributor(name: str, factory: Callable[[], Contributor]) -> None:
    """Register contributor `name` (one of `CONTRIBUTOR_ORDER`) for `AssessmentProgram.build`."""
    if name not in CONTRIBUTOR_ORDER:
        raise ValueError(f"contributor {name!r} is not one of {list(CONTRIBUTOR_ORDER)}")
    _REGISTERED[name] = factory


def _registered() -> tuple[Contributor, ...]:
    return tuple(_REGISTERED[name]() for name in CONTRIBUTOR_ORDER if name in _REGISTERED)


# -- symbols and the per-pass memo (§4.2.2, §4.2.3) ----------------------------------------------


class Symbols:
    """What a functional builder reads: host variables, pinned inputs, θ, block outputs, and the
    expressions of other outputs (`out`), which the memo shares within one build pass."""

    def __init__(
        self,
        variables: Mapping[str, Expr],
        blocks: Mapping[str, Expr],
        pins: Mapping[str, Expr],
        algebra: Algebra,
        resolve: Callable[[str, Symbols], Expr],
    ) -> None:
        self._variables = variables
        self._blocks = blocks
        self._pins = pins
        self.algebra = algebra
        self._resolve = resolve

    def x(self, variable_id: str) -> Expr:
        try:
            return self._variables[variable_id]
        except KeyError:
            raise KeyError(f"ASSESSMENT_VARIABLE_UNKNOWN({variable_id})") from None

    def pin(self, parameter_id: str) -> Expr:
        if parameter_id.startswith(THETA_PREFIX):
            raise KeyError(f"{parameter_id!r} is a θ; read it with theta()")
        return self._pins[parameter_id]

    def theta(self, theta_id: str) -> Expr:
        if not theta_id.startswith(THETA_PREFIX):
            raise KeyError(f"{theta_id!r} is not a θ id ({THETA_PREFIX}<path>)")
        return self._pins[theta_id]

    def block(self, block_id: str, output_id: str) -> Expr:
        return self._blocks[f"{block_id}.{output_id}"]

    def out(self, output_id: str) -> Expr:
        return self._resolve(output_id, self)


class _Memo:
    """Shares `out(id)` expressions across the rows of one build pass (§4.2.3).

    A pass is recognised by the identity of the objects the compiler hands every row: the
    variables mapping, the block-output mapping and the algebra, plus the identities of the pinned
    values. `ParametricTwin` and `reference.row_values` each pass one variables mapping to every
    row of a pass (verified by `tests/test_e01_a_core.py`); the twin builds a fresh pins mapping
    per row but over the same value objects, hence the value identities rather than the mapping's.
    The previous pass's objects are held, so no identity can be reused while it is compared.
    With `enabled=False` every `out` rebuilds (correct, slower).
    """

    def __init__(self, builders: Mapping[str, FunctionalBuilder], *, enabled: bool = True) -> None:
        self._builders = builders
        self.enabled = enabled
        self._pass: tuple[Any, ...] | None = None
        self._held: tuple[Any, ...] = ()
        self._cache: dict[str, Expr] = {}
        self._building: set[str] = set()
        self.builds = 0

    def row(
        self,
        output_id: str,
        variables: Mapping[str, Expr],
        blocks: Mapping[str, Expr],
        pins: Mapping[str, Expr],
        algebra: Algebra,
    ) -> Expr:
        if self.enabled:
            key = (id(variables), id(blocks), id(algebra), tuple(map(id, pins.values())))
            if key != self._pass:
                self._pass, self._held = key, (variables, blocks, algebra, pins)
                self._cache = {}
        else:
            self._cache = {}
        symbols = Symbols(variables, blocks, pins, algebra, self._resolve)
        return self._resolve(output_id, symbols)

    def _resolve(self, output_id: str, symbols: Symbols) -> Expr:
        if output_id in self._cache:
            return self._cache[output_id]
        builder = self._builders.get(output_id)
        if builder is None:
            raise KeyError(f"ASSESSMENT_OUTPUT_UNKNOWN({output_id})")
        if output_id in self._building:
            raise ValueError(f"output {output_id!r} depends on itself")
        self._building.add(output_id)
        try:
            value = builder(symbols, symbols.algebra)
        finally:
            self._building.discard(output_id)
        self.builds += 1
        if self.enabled:
            self._cache[output_id] = value
        return value


def _row_builder(memo: _Memo, output_id: str) -> Callable[..., Expr]:
    def build(
        variables: Mapping[str, Expr],
        blocks: Mapping[str, Expr],
        pins: Mapping[str, Expr],
        algebra: Algebra,
    ) -> Expr:
        return memo.row(output_id, variables, blocks, pins, algebra)

    return build


def _admissibility_builder(row_build: FunctionalBuilder, nominal: float) -> FunctionalBuilder:
    def build(symbols: Symbols, algebra: Algebra) -> Expr:
        return row_build(symbols, algebra) / nominal

    return build


@dataclass(frozen=True)
class _Row:
    output_id: str
    unit: str
    origin: str
    build: FunctionalBuilder


def _assemble(
    label: str,
    host_spec: ProblemSpec,
    rows: Sequence[_Row],
    theta: Sequence[Theta],
    blocks: Sequence[tuple[PropertyBlock, tuple[str, ...]]],
    *,
    memo_enabled: bool = True,
) -> tuple[ProblemSpec, _Memo]:
    """The functional `ProblemSpec` of `rows` over the host (§4.2.3), and its memo."""
    memo = _Memo({row.output_id: row.build for row in rows}, enabled=memo_enabled)
    clash = sorted(set(host_spec.parameters) & {t.theta_id for t in theta})
    if clash:
        raise ValueError(f"θ ids {clash} collide with host pinned inputs")
    parameters = {**host_spec.parameters, **{t.theta_id: t.value for t in theta}}
    spec = ProblemSpec(
        label=label,
        variable_ids=host_spec.variable_ids,
        equations=tuple(
            EquationSpec(
                equation_id=row.output_id,
                build=_row_builder(memo, row.output_id),
                accumulation="algebraic",
                origin=row.origin,
            )
            for row in rows
        ),
        parameter_ids=(*host_spec.parameter_ids, *(t.theta_id for t in theta)),
        parameters=MappingProxyType(parameters),
        blocks=tuple(block for block, _ in blocks),
        block_inputs={block.block_id: tuple(inputs) for block, inputs in blocks},
    )
    spec.validate()
    return spec, memo


def _float_rows(spec: ProblemSpec, state: Mapping[str, float]) -> dict[str, float]:
    """`reference.row_values`, with every domain failure an evaluation error (§4.2.3)."""
    try:
        values = row_values(spec, state)
    except (DomainError, ValueError, ZeroDivisionError, OverflowError) as error:
        raise TwinEvaluationError(f"{type(error).__name__}: {error}") from error
    except TypeError as error:
        # A float power of a negative base is complex in Python (CasADi gives NaN): the cube root
        # of a negative ΔT, say. Any other TypeError is a defect and propagates.
        if "complex" not in str(error):
            raise
        raise TwinEvaluationError(f"a complex value (negative base of a power): {error}") from error
    bad = [name for name, value in values.items() if not math.isfinite(value)]
    if bad:
        raise TwinEvaluationError(f"non-finite assessment values {bad}")
    return values


# -- the build context ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BuildContext:
    """What a contributor plans from: the view, the host spec, the document, and the regime as
    data (the held choices; empty when every entry is the rule's to choose)."""

    view: FlowsheetView
    host_spec: ProblemSpec
    spec: AssessmentSpec
    regime: Regime
    #: The plans of the contributors that ran before this one, by name (§4.2.2: `derived` may
    #: reference any earlier output). Empty for the first contributor.
    earlier: Mapping[str, ContributionPlan] = MappingProxyType({})

    def evaluate(
        self,
        state: Mapping[str, float],
        outputs: Sequence[OutputDef],
        theta: Sequence[Theta] = (),
        blocks: Sequence[tuple[PropertyBlock, tuple[str, ...]]] = (),
    ) -> dict[str, float]:
        """The float values of `outputs` at `state`, for the selection pass (§4.3.2); raises
        `TwinEvaluationError` where they cannot be evaluated."""
        rows = [_Row(o.output_id, o.unit, "assessment:plan", o.build) for o in outputs]
        spec, _ = _assemble("ASM1-plan", self.host_spec, rows, theta, blocks)
        return _float_rows(spec, state)


@dataclass(frozen=True)
class Linearization:
    values: Mapping[str, float]
    d_dx: TwinMatrix
    d_dp: TwinMatrix


def _submatrix(matrix: TwinMatrix, rows: Sequence[str], cols: Sequence[str]) -> TwinMatrix:
    """`matrix` restricted to `rows` x `cols` (in those orders), canonical CSC kept."""
    row_index = {name: i for i, name in enumerate(matrix.row_ids)}
    keep_rows = {row_index[name]: new for new, name in enumerate(rows)}
    col_index = {name: j for j, name in enumerate(matrix.col_ids)}
    indptr: list[int] = [0]
    indices: list[int] = []
    data: list[float] = []
    for name in cols:
        j = col_index[name]
        entries = sorted(
            (keep_rows[matrix.indices[k]], matrix.data[k])
            for k in range(matrix.indptr[j], matrix.indptr[j + 1])
            if matrix.indices[k] in keep_rows
        )
        indices.extend(i for i, _ in entries)
        data.extend(v for _, v in entries)
        indptr.append(len(indices))
    return TwinMatrix(tuple(rows), tuple(cols), tuple(indptr), tuple(indices), tuple(data))


def _feasibility_tolerance() -> float:
    """M03's V3 feasibility tolerance on scaled inequalities (§4.2.1), imported, never redefined.
    Imported here, not at module load, because `studies.nlp` will import this package."""
    from openflowsheet.studies.nlp.verification import TAU_FEAS  # noqa: PLC0415

    return float(TAU_FEAS)


# -- the program ---------------------------------------------------------------------------------


class AssessmentProgram:
    """One assessment over one host at one held regime (§4.1, §4.2.1)."""

    def __init__(
        self,
        *,
        ctx: BuildContext,
        contributors: tuple[Contributor, ...],
        rows: tuple[_Row, ...],
        output_count: int,
        theta: tuple[Theta, ...],
        blocks: tuple[tuple[PropertyBlock, tuple[str, ...]], ...],
        entries: tuple[RegimeEntry, ...],
        plans: Mapping[str, ContributionPlan],
    ) -> None:
        self._ctx = ctx
        self._contributors = contributors
        self._rows = rows
        self.regime = Regime.of(entries)
        self.entries = entries
        self.output_ids: tuple[str, ...] = tuple(row.output_id for row in rows)
        self.admissibility_ids: tuple[str, ...] = self.output_ids[output_count:]
        #: The rows of the `domain` entries, each to the output it guards: an entry
        #: `<output_id>.<what>` bounds the domain of `<output_id>` (§4.7.5 erratum, R-868).
        self.domain_rows: Mapping[str, str] = MappingProxyType(
            {
                f"adm.{entry.entry_id}.{row.row_id}": entry.entry_id.rsplit(".", 1)[0]
                for entry in entries
                if entry.kind == "domain"
                for row in entry.admissibility
            }
        )
        self.units: Mapping[str, str] = MappingProxyType({r.output_id: r.unit for r in rows})
        self.theta: Mapping[str, Theta] = MappingProxyType({t.theta_id: t for t in theta})
        self.plans = MappingProxyType(dict(plans))
        self.refusals = tuple(r for plan in plans.values() for r in plan.refusals)
        self.limitations = tuple(lim for plan in plans.values() for lim in plan.limitations)
        self.unavailable: Mapping[str, str] = MappingProxyType(
            {name: why for plan in plans.values() for name, why in plan.unavailable}
        )
        label = f"ASM1-{ctx.spec.assessment_sha256[:12]}-{self.regime.sha256[:8]}"
        self._functional, self.memo = _assemble(label, ctx.host_spec, rows, theta, blocks)
        self._twins: dict[tuple[str, ...], ParametricTwin] = {}

    # -- construction ----------------------------------------------------------------------------

    @classmethod
    def build(
        cls,
        view: FlowsheetView,
        host_spec: ProblemSpec,
        spec: AssessmentSpec,
        state: Mapping[str, float],
        regime: Regime | None = None,
        *,
        contributors: Sequence[Contributor] | None = None,
    ) -> AssessmentProgram | Refusal:
        """Plan every contributor at `state` and compile the functional spec (§4.2.1).

        `regime=None` selects by the rule at `state`. A given regime is held: every one of its
        entries must be one the program has, and every admissibility row must be ≥ −τ_feas at
        `state`, else `ASSESSMENT_REGIME_INADMISSIBLE`. `contributors` defaults to the registered
        ones in `CONTRIBUTOR_ORDER`.
        """
        chosen = _registered() if contributors is None else tuple(contributors)
        held = regime if regime is not None else Regime()
        program = cls._plan(view, host_spec, spec, state, held, chosen)
        if regime is None:
            return program
        unknown = sorted(set(regime.entries) - set(program.regime.entries))
        if unknown:
            return Refusal(
                "ASSESSMENT_REGIME_INADMISSIBLE", ",".join(unknown), "entries the program lacks"
            )
        return program._admissible_at(state)

    @classmethod
    def _plan(
        cls,
        view: FlowsheetView,
        host_spec: ProblemSpec,
        spec: AssessmentSpec,
        state: Mapping[str, float],
        held: Regime,
        contributors: tuple[Contributor, ...],
    ) -> AssessmentProgram:
        ctx = BuildContext(view, host_spec, spec, held)
        plans: dict[str, ContributionPlan] = {}
        outputs: list[_Row] = []
        admissibility: list[_Row] = []
        theta: list[Theta] = []
        blocks: list[tuple[PropertyBlock, tuple[str, ...]]] = []
        entries: list[RegimeEntry] = []
        for contributor in contributors:
            if contributor.name in plans:
                raise ValueError(f"contributor {contributor.name!r} given twice")
            plan = contributor.plan(
                dataclasses.replace(ctx, earlier=MappingProxyType(dict(plans))), state
            )
            plans[contributor.name] = plan
            origin = f"assessment:{contributor.name}"
            outputs.extend(_Row(o.output_id, o.unit, origin, o.build) for o in plan.outputs)
            for entry in plan.regime_entries:
                held_choice = held.choice(entry.entry_id)
                if held_choice is not None and held_choice != entry.choice:
                    raise ValueError(
                        f"contributor {contributor.name!r} replaced the held choice "
                        f"{entry.entry_id}={held_choice!r} by {entry.choice!r}"
                    )
                admissibility.extend(
                    _Row(
                        f"adm.{entry.entry_id}.{row.row_id}",
                        "1",
                        origin,
                        _admissibility_builder(row.build, row.nominal),
                    )
                    for row in entry.admissibility
                )
            entries.extend(plan.regime_entries)
            theta.extend(plan.theta)
            blocks.extend(plan.blocks)
        rows = (*outputs, *admissibility)
        unknown = [row.output_id for row in rows if classify(row.output_id) is None]
        if unknown:
            raise ValueError(f"output ids outside the catalogue (§4.1): {unknown}")
        prefixed = [name for name in host_spec.variable_ids if name.startswith(ASSESSMENT_PREFIX)]
        if prefixed:
            raise ValueError(f"host variables use the assessment prefix: {prefixed}")
        return cls(
            ctx=ctx,
            contributors=contributors,
            rows=rows,
            output_count=len(outputs),
            theta=tuple(theta),
            blocks=tuple(blocks),
            entries=tuple(entries),
            plans=plans,
        )

    def _admissible_at(self, state: Mapping[str, float]) -> AssessmentProgram | Refusal:
        tau = _feasibility_tolerance()
        try:
            values = self.evaluate(state)
        except TwinEvaluationError as error:
            return Refusal("ASSESSMENT_REGIME_INADMISSIBLE", "", f"not evaluable: {error}")
        assert isinstance(values, Mapping)
        violated = [name for name in self.admissibility_ids if values[name] < -tau]
        if violated:
            return Refusal("ASSESSMENT_REGIME_INADMISSIBLE", ",".join(violated), f"tau_feas={tau}")
        return self

    # -- evaluation ------------------------------------------------------------------------------

    @property
    def label(self) -> str:
        return self._functional.label

    @property
    def parameter_ids(self) -> tuple[str, ...]:
        return self._functional.parameter_ids

    def _with_decisions(self, decisions: Mapping[str, float]) -> ProblemSpec | Refusal:
        if not decisions:
            return self._functional
        assessment = sorted(name for name in decisions if name in self.theta)
        if assessment:
            return Refusal(
                "ASSESSMENT_PARAMETER_DECISION", ",".join(assessment), kind="unsupported"
            )
        unknown = sorted(set(decisions) - set(self._functional.parameters))
        if unknown:
            raise ValueError(f"decisions {unknown} are not pinned inputs of the host")
        parameters = {**self._functional.parameters, **{k: float(v) for k, v in decisions.items()}}
        return dataclasses.replace(self._functional, parameters=MappingProxyType(parameters))

    def evaluate(
        self,
        x: Mapping[str, float],
        decisions: Mapping[str, float] = MappingProxyType({}),
        *,
        domain_guard: bool = True,
    ) -> Mapping[str, float] | Refusal:
        """Every output and admissibility row at `(x, d)` on the float path (§4.2.1).

        Raises `TwinEvaluationError` where a value cannot be evaluated (§4.2.3), including a
        `domain` row ≤ 0: `METRIC_UNDEFINED(<output_id>)` at every state (§4.7.5 erratum, R-868).
        `domain_guard=False` is the report's alone: it nulls each undefined output itself and
        reports the others (§4.9)."""
        spec = self._with_decisions(decisions)
        if isinstance(spec, Refusal):
            return spec
        values = _float_rows(spec, x)
        if domain_guard:
            undefined = [
                f"METRIC_UNDEFINED({output_id}): {row} = {values[row]!r} ≤ 0"
                for row, output_id in self.domain_rows.items()
                if not values[row] > 0.0
            ]
            if undefined:
                raise TwinEvaluationError("; ".join(undefined))
        return MappingProxyType(values)

    def twin(self, symbolic: Sequence[str]) -> ParametricTwin | Refusal:
        """The functional spec compiled with `symbolic` (host pins or continuous θ) as symbols,
        cached per tuple (§4.13). With none requested, the first non-structural parameter is the
        twin's one symbol (a `ParametricTwin` needs one); its column is never read."""
        requested = tuple(symbolic)
        structural = [n for n in requested if n in self.theta and self.theta[n].structural]
        if structural:
            return Refusal("ASSESSMENT_PARAMETER_STRUCTURAL", ",".join(structural))
        unknown = [n for n in requested if n not in self._functional.parameters]
        if unknown:
            raise ValueError(f"{unknown} are neither host pinned inputs nor θ of this program")
        if not requested:
            anchor = next(
                (
                    name
                    for name in self._functional.parameter_ids
                    if not (name in self.theta and self.theta[name].structural)
                ),
                None,
            )
            if anchor is None:
                return Refusal("ASSESSMENT_EVALUATION_FAILED", "", "no parameter to compile over")
            requested = (anchor,)
        if requested not in self._twins:
            self._twins[requested] = compile_parametric_twin(self._functional, requested)
        return self._twins[requested]

    def linearize(
        self,
        x: Mapping[str, float],
        decisions: Mapping[str, float],
        outputs: Sequence[str],
        symbolic: Sequence[str] = (),
    ) -> Linearization | Refusal:
        """Values (twin) of every row, and `∂(outputs)/∂x` (outputs x host variable ids) and
        `∂(outputs)/∂p` (outputs x `symbolic`), at `(x, d)`. The decisions are symbols of the twin
        whether or not they are requested, so the graph is the one the NLP differentiates."""
        withheld = [name for name in outputs if name in self.unavailable]
        if withheld:
            return Refusal(
                "ASSESSMENT_OUTPUT_UNAVAILABLE",
                ",".join(withheld),
                "; ".join(self.unavailable[name] for name in withheld),
            )
        unknown = [name for name in outputs if name not in self.units]
        if unknown:
            return Refusal("ASSESSMENT_OUTPUT_UNKNOWN", ",".join(unknown))
        if any(name in self.theta for name in decisions):
            return Refusal(
                "ASSESSMENT_PARAMETER_DECISION",
                ",".join(sorted(n for n in decisions if n in self.theta)),
                kind="unsupported",
            )
        requested = tuple(symbolic) + tuple(d for d in decisions if d not in symbolic)
        twin = self.twin(requested)
        if isinstance(twin, Refusal):
            return twin
        parameters = self._functional.parameters
        bound = {name: float(decisions.get(name, parameters[name])) for name in twin.parameter_ids}
        vector = np.array([float(x[name]) for name in self._functional.variable_ids])
        values = twin.residual(vector, bound)
        d_dx = _submatrix(twin.jacobian_x(vector, bound), outputs, self._functional.variable_ids)
        d_dp = _submatrix(twin.jacobian_p(vector, bound), outputs, tuple(symbolic))
        return Linearization(
            MappingProxyType(dict(zip(self.output_ids, values, strict=True))), d_dx, d_dp
        )

    @property
    def context(self) -> BuildContext:
        """The context the program was planned in (the view, host, document and held regime)."""
        return self._ctx

    def report(
        self, x: Mapping[str, float], *, state_sha256: str, uncertainty: bool = True
    ) -> dict[str, Any]:
        """The assessment report at `x` (§4.2.1, §4.9, §4.11): a document valid against
        `assessment-report.schema.json`. Built by `assessment.report.build_report`."""
        from openflowsheet.assessment.report import build_report  # noqa: PLC0415

        return build_report(self, x, state_sha256=state_sha256, uncertainty=uncertainty)

    def select(
        self,
        x: Mapping[str, float],
        decisions: Mapping[str, float] = MappingProxyType({}),
        *,
        release: Sequence[str] = (),
    ) -> Regime:
        """The regime at `x` (§4.3.2): the held choice of every entry whose admissibility rows are
        ≥ −τ_feas at `x`, the rule for the others. A held regime that cannot be evaluated at `x`
        is released whole.

        `decisions` are host pins at other values than the program's (a study's candidate,
        §4.10.3 V7): the rows and the rule then read them. `release` gives entries to the rule
        whatever their rows — V7's dormancy entries, which have none (§4.3.1)."""
        tau = _feasibility_tolerance()
        try:
            values = self.evaluate(x, decisions)
        except TwinEvaluationError:
            released: Iterable[str] = self.regime.entries
        else:
            if not isinstance(values, Mapping):
                raise ValueError(f"the program refuses evaluation at the decisions: {values}")
            released = [
                entry.entry_id
                for entry in self.entries
                if entry.entry_id in release
                or any(
                    values[f"adm.{entry.entry_id}.{row.row_id}"] < -tau
                    for row in entry.admissibility
                )
            ]
        held = self.regime.without(tuple(released))
        ctx = self._ctx
        host = ctx.host_spec
        if decisions:
            pins = {**host.parameters, **{k: float(v) for k, v in decisions.items()}}
            host = dataclasses.replace(host, parameters=MappingProxyType(pins))
        program = type(self)._plan(ctx.view, host, ctx.spec, x, held, self._contributors)
        return program.regime
