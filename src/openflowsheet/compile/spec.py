"""What a problem *is*, described without reference to any backend.

A `ProblemSpec` is the compiler's input: ordered variables, ordered equations, ordered pinned
inputs, the property blocks the equations call, and the scales. It holds data and callables, no
expression objects, and this module imports no backend — that is ADR 0003 D5.7, and
`tests/test_k01_no_backend_in_orchestrator.py` enforces it for the whole package outside the
adapter.

The awkward part of staying backend-free is the equations themselves, which are expressions. They
are written as builders that receive an `Algebra` — arithmetic comes from operator overloading,
which every backend's expression type already provides, so only the transcendental functions need
an abstraction. A model author writes `algebra.exp(ln_k)` and never imports CasADi; the adapter
supplies the implementation. This is the whole reason a unit model in `models/` can be tested,
reviewed and reasoned about without the backend present.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from openflowsheet.compiled import RowAccumulation

#: The physical kind of a variable or a row, used to assign it a registered scale.
#: `molar_flow_squared` exists because the division-free equilibrium row `v_i L - K_i l_i V` is a
#: product of two flows; K03's specification §4.2 scales it by the square of the flow nominal.
#: A kind is *declared* by the unit that owns the variable or authors the row, never inferred
#: from the shape of an id: an id convention that drifts would silently mis-scale a column.
QuantityKind = Literal["molar_flow", "molar_flow_squared", "temperature", "pressure", "heat_rate"]

#: A backend expression. Deliberately `Any`: this module must not name a backend's type, and
#: parameterizing every signature over a TypeVar would buy nothing a reader can act on, because
#: only the adapter ever creates one of these and it only ever holds one backend's.
Expr = Any


class Algebra(Protocol):
    """The functions an equation needs that operator overloading does not provide.

    Kept deliberately small. Every addition here is a function every future backend must implement,
    so it is a cost paid by the architecture, not by the caller; add one only when an equation
    genuinely cannot be written without it.
    """

    def exp(self, value: Expr) -> Expr: ...

    def log(self, value: Expr) -> Expr: ...

    def sqrt(self, value: Expr) -> Expr: ...


#: Builds one residual row. Receives the variable symbols by id, the block outputs by
#: `"<block_id>.<output_id>"`, the pinned inputs by id, and the algebra. Returns a scalar
#: expression whose value is the residual of that row — zero at a solution.
RowBuilder = Callable[
    [Mapping[str, Expr], Mapping[str, Expr], Mapping[str, float], Algebra],
    Expr,
]


class PropertyBlock(Protocol):
    """An opaque evaluator the residual calls: values and a declared-sparse first derivative.

    "Opaque" is the point. The compiler cannot see inside, so the block must *declare* its Jacobian
    sparsity, and the backend must be told that the declaration exists. Without that declaration a
    backend propagates the dependency structure of an opaque call — every output depends on every
    input — and the block's structural zeros reappear as stored zeros in the assembled system. P02
    measured exactly that: 66 stored entries instead of 60.
    """

    @property
    def block_id(self) -> str: ...

    @property
    def input_ids(self) -> tuple[str, ...]: ...

    @property
    def output_ids(self) -> tuple[str, ...]: ...

    def jacobian_pattern(self) -> tuple[tuple[int, int], ...]:
        """Structural nonzeros of d(outputs)/d(inputs) as `(output_index, input_index)` pairs.

        This is a claim about the function, not about one evaluation: a pair absent here asserts
        that the derivative is zero at *every* state. `jacobian` returning a value for a pair that
        is not declared, or omitting one that is, is a defect in the block and
        `tests/test_k01_compile_syn001.py` looks for both.
        """

    def values(self, inputs: Sequence[float]) -> Sequence[float]:
        """Evaluate the outputs. Raise `DomainError` outside the block's stated domain."""

    def jacobian(self, inputs: Sequence[float]) -> Sequence[tuple[int, int, float]]:
        """Evaluate the declared nonzeros as `(output_index, input_index, value)` triples."""


class DomainError(ValueError):
    """Raised by a block asked to evaluate outside its stated domain.

    The compiled problem turns this into `EvaluationStatus` `"invalid_trial_state"` with the
    block's message. It is not an error in the caller and it is never a silent extrapolation: a
    solver is expected to see it, reject the trial point and shorten its step.
    """


@dataclass(frozen=True)
class EquationSpec:
    """One residual row: its id, how it accumulates, and how to build it."""

    equation_id: str
    build: RowBuilder
    #: ADR 0008 D3/D4.4. A row the compiler itself authors — a tear or a specification-promotion
    #: row — is `"algebraic"`, never `"absent"`: the compiler wrote it and knows what it is.
    #: `"absent"` is reserved for a row whose accumulation genuinely cannot be known.
    accumulation: RowAccumulation
    #: Where this row came from, carried into `JacobianResult.source_map` so a nonzero can be
    #: traced back to the declaration that produced it.
    origin: str = ""


@dataclass(frozen=True)
class ProblemSpec:
    """A complete problem, ready to compile. Ordered, named, and free of any backend."""

    #: The human-readable name of the *function family*, e.g. `SYN-001-L-1`. This is a **label**,
    #: not the full `model_version`: `compile_problem` appends `@<structure_sha256>` computed from
    #: this spec, because a spec is not trusted to supply its own structural digest (ADR 0002 D2.5).
    #:
    #: The label still carries one thing the digest cannot — two problems with identical ids whose
    #: equation *expressions* differ share a structure digest — so **the label must change whenever
    #: the equation set changes** (ADR 0002 D2.7). That is a code-review obligation until a compiled
    #: problem is assembled from manifests rather than from Python.
    label: str
    variable_ids: tuple[str, ...]
    equations: tuple[EquationSpec, ...]
    #: The order `constants_sha256` hashes `parameters` in. Every key of `parameters` appears here
    #: exactly once; the ordering is explicit rather than derived from dict order so that the hash
    #: does not depend on how the mapping happened to be built.
    parameter_ids: tuple[str, ...]
    parameters: Mapping[str, float]
    blocks: tuple[PropertyBlock, ...] = ()
    #: Block inputs, by `"<block_id>"` -> the variable ids feeding it, in the block's input order.
    block_inputs: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    column_scales: Mapping[str, float] = field(default_factory=dict)
    row_scales: Mapping[str, float] = field(default_factory=dict)
    #: The physical kind of each variable and each row, declared by whoever owns it. K03 turns
    #: these into scales from the registered nominals (its specification §4). They are metadata:
    #: nothing in the compiled function reads them, so `structure_sha256` and `model_version` do
    #: not depend on them and adding them to an existing spec changes no number.
    variable_kinds: Mapping[str, QuantityKind] = field(default_factory=dict)
    row_kinds: Mapping[str, QuantityKind] = field(default_factory=dict)

    @property
    def equation_ids(self) -> tuple[str, ...]:
        return tuple(equation.equation_id for equation in self.equations)

    @property
    def row_accumulation(self) -> Mapping[str, RowAccumulation]:
        return {equation.equation_id: equation.accumulation for equation in self.equations}

    def validate(self) -> None:
        """Refuse a spec that could only produce a wrong answer. Called by every compile.

        Every check here is for a mistake that is silent rather than loud: a duplicate id makes a
        later entry shadow an earlier one; a parameter missing from `parameter_ids` drops out of
        `constants_sha256` so two different problems claim the same identity; a block whose inputs
        are not variables would be fed a symbol that does not exist.
        """
        _no_duplicates(self.variable_ids, "variable_ids")
        _no_duplicates(self.equation_ids, "equation_ids")
        _no_duplicates(self.parameter_ids, "parameter_ids")

        if set(self.parameter_ids) != set(self.parameters):
            missing = sorted(set(self.parameters) - set(self.parameter_ids))
            extra = sorted(set(self.parameter_ids) - set(self.parameters))
            raise ValueError(
                "parameter_ids must name exactly the pinned inputs, because it is the order "
                f"constants_sha256 hashes them in (ADR 0008 D4.1). Unordered: {missing}. "
                f"Named but absent: {extra}."
            )

        known = set(self.variable_ids)
        for block in self.blocks:
            feeding = self.block_inputs.get(block.block_id)
            if feeding is None:
                raise ValueError(f"block {block.block_id!r} has no entry in block_inputs")
            if len(feeding) != len(block.input_ids):
                raise ValueError(
                    f"block {block.block_id!r} declares {len(block.input_ids)} inputs but is fed "
                    f"{len(feeding)}"
                )
            unknown = [name for name in feeding if name not in known]
            if unknown:
                raise ValueError(f"block {block.block_id!r} is fed unknown variables {unknown}")
            _check_pattern(block)

        block_ids = [block.block_id for block in self.blocks]
        _no_duplicates(tuple(block_ids), "block ids")
        for name in self.block_inputs:
            if name not in block_ids:
                raise ValueError(f"block_inputs names {name!r}, which is not a declared block")

        for kinds, names, label in (
            (self.variable_kinds, known, "variable_kinds"),
            (self.row_kinds, set(self.equation_ids), "row_kinds"),
        ):
            unknown_kind = sorted(set(kinds) - names)
            if unknown_kind:
                raise ValueError(f"{label} names unknown ids {unknown_kind}")

        for scales, names, label in (
            (self.column_scales, known, "column_scales"),
            (self.row_scales, set(self.equation_ids), "row_scales"),
        ):
            unknown_scale = sorted(set(scales) - names)
            if unknown_scale:
                raise ValueError(f"{label} names unknown ids {unknown_scale}")
            nonpositive = sorted(name for name, value in scales.items() if not value > 0.0)
            if nonpositive:
                raise ValueError(
                    f"{label} has non-positive entries {nonpositive}; a scale divides, so a zero "
                    "or negative one is a silent sign flip or a division by zero, not a scaling"
                )


def _no_duplicates(names: tuple[str, ...], label: str) -> None:
    counted = Counter(names)
    repeated = sorted(name for name, count in counted.items() if count > 1)
    if repeated:
        raise ValueError(f"{label} contains duplicates {repeated}")


def _check_pattern(block: PropertyBlock) -> None:
    pattern = block.jacobian_pattern()
    rows, columns = len(block.output_ids), len(block.input_ids)
    out_of_range = [
        pair for pair in pattern if not (0 <= pair[0] < rows and 0 <= pair[1] < columns)
    ]
    if out_of_range:
        raise ValueError(
            f"block {block.block_id!r} declares Jacobian entries outside its "
            f"{rows}x{columns} shape: {out_of_range}"
        )
    if len(set(pattern)) != len(pattern):
        raise ValueError(f"block {block.block_id!r} declares a repeated Jacobian entry")
