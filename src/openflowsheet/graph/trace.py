"""The declaration-traced incidence: what each row references, read from the declaration.

T01 specification §3.3. The incidence of a row is obtained by running its `RowBuilder` under an
algebra whose values are *incidence sets* rather than numbers: a variable symbol is `{its id}`,
a block output is the set of the block's inputs its declared `jacobian_pattern` names for that
output, arithmetic is set union, and a parameter is an **opaque token that does not fold**.

**Why not the backend's sparsity pattern.** The compiler substitutes parameter *values* before
building the expression, so CasADi's sparsity is that of the expression after constant folding at
the pinned values. Measured on `main` at `f603e9b`: nnz 170 at `r = 0.5`, but **167 at `r = 0`**,
where `0.0 * r_i` folds away and the three recycle-split entries vanish.
The registered once-through case would then have no recycle edge in its graph, an empty tear, and
a "structural" result the same flowsheet does not share at `r = 0.5`. A conclusion that moves with
a parameter value is not a structural conclusion, exactly as a conclusion that moves with the
enthalpy datum is not one. The declaration does not move.

That is also why `parameters` arrives here as opaque tokens and not as floats: handing the
builders their real values would reproduce the folding inside this module. A builder that
*branches* in Python on a parameter value defeats the trace — and does so loudly, because
comparing a token raises rather than silently taking a branch.

The same trace records, for each row, whether it is **affine with literal coefficients** — a sum
of `+/-1 * variable` and parameters — which is what the §8.2 certificate needs and what a
parameter-scaled row -- a splitter's, whose coefficient is the split fraction -- is not.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final

from openflowsheet.compile.spec import ProblemSpec, QuantityKind

__all__ = [
    "Declaration",
    "StructureUnavailableError",
    "TracedRow",
    "parameters_read",
    "trace_declaration",
]


class StructureUnavailableError(ValueError):
    """A row whose builder cannot be traced: it raised, or it returned something that is not a term.

    Named with the row, and turned into `finding: UNSUPPORTED` by the analysis rather than into a
    pass (§12.4). A builder that compares a parameter to a number lands here, which is the point.
    """

    def __init__(self, row_id: str, reason: str) -> None:
        super().__init__(f"row {row_id!r} cannot be traced structurally: {reason}")
        self.row_id = row_id
        self.reason = reason


@dataclass(frozen=True)
class _Constant:
    """The parameter-and-literal part of a traced expression.

    `literal` is the value when no parameter is involved, and `None` otherwise; that distinction
    is what separates a *literal* coefficient from a parameter-scaled one. `evaluate` computes
    the part from the actual parameter values, which is how §8.2 gets a certificate's mismatch
    without evaluating an equation.
    """

    literal: float | None
    evaluate: Callable[[Mapping[str, float]], float]

    @staticmethod
    def of(value: float) -> _Constant:
        return _Constant(literal=float(value), evaluate=lambda _: float(value))

    @staticmethod
    def parameter(name: str) -> _Constant:
        return _Constant(literal=None, evaluate=lambda parameters: parameters[name])

    def _combine(self, other: _Constant, operator: Callable[[float, float], float]) -> _Constant:
        literal = (
            None
            if self.literal is None or other.literal is None
            else operator(self.literal, other.literal)
        )
        return _Constant(
            literal=literal,
            evaluate=lambda parameters: operator(
                self.evaluate(parameters), other.evaluate(parameters)
            ),
        )

    def __add__(self, other: _Constant) -> _Constant:
        return self._combine(other, lambda a, b: a + b)

    def __sub__(self, other: _Constant) -> _Constant:
        return self._combine(other, lambda a, b: a - b)

    def __mul__(self, other: _Constant) -> _Constant:
        return self._combine(other, lambda a, b: a * b)

    def __truediv__(self, other: _Constant) -> _Constant:
        return self._combine(other, lambda a, b: a / b)

    def __neg__(self) -> _Constant:
        return _Constant(
            literal=None if self.literal is None else -self.literal,
            evaluate=lambda parameters: -self.evaluate(parameters),
        )

    def opaque(self) -> _Constant:
        """The result of a transcendental function: still evaluable, no longer a literal."""
        return _Constant(literal=None, evaluate=self.evaluate)


_ZERO: Final = _Constant.of(0.0)


@dataclass(frozen=True, eq=False)
class _Term:
    """One traced expression: what it references, and its affine form when it has one.

    `columns` is the **incidence** and is never pruned — a coefficient that cancels to zero keeps
    its column, because the declaration still references it. `coefficients` is `None` when the
    expression is not affine with literal coefficients (a product of two variables, a
    transcendental, a parameter-scaled variable); it is a mapping otherwise, and may hold a zero.
    """

    columns: frozenset[str]
    coefficients: Mapping[str, float] | None
    constant: _Constant
    #: True when a block output is involved. A block is opaque by construction, so its value is
    #: neither a literal nor an affine function of anything, *even when its declared pattern is
    #: empty*. Without this, `exp(block_output_with_no_declared_inputs)` collapsed to a plain
    #: constant and a row reading it classified as a specification row pinning a parameter
    #: (should-fix S1 of the Fable review of T01). Latent today — no SYN-001 block declares an
    #: empty pattern — and wrong the day one does.
    opaque: bool = False

    # -- construction ------------------------------------------------------------------------

    @staticmethod
    def variable(name: str) -> _Term:
        return _Term(columns=frozenset({name}), coefficients={name: 1.0}, constant=_ZERO)

    @staticmethod
    def from_block(columns: frozenset[str]) -> _Term:
        """A block output: it references its declared inputs and has no affine form."""
        return _Term(columns=columns, coefficients=None, constant=_ZERO, opaque=True)

    @staticmethod
    def constant_of(constant: _Constant) -> _Term:
        return _Term(columns=frozenset(), coefficients={}, constant=constant)

    @staticmethod
    def _coerce(value: Any) -> _Term:
        if isinstance(value, _Term):
            return value
        if isinstance(value, bool):
            raise TypeError("a boolean is not a term; a builder branched on a traced value")
        if isinstance(value, int | float):
            return _Term.constant_of(_Constant.of(float(value)))
        raise TypeError(f"{value!r} is not a term")

    # -- arithmetic --------------------------------------------------------------------------

    def _linear(self, other: _Term, sign: float) -> _Term:
        coefficients: dict[str, float] | None
        if self.coefficients is None or other.coefficients is None:
            coefficients = None
        else:
            coefficients = dict(self.coefficients)
            for name, value in other.coefficients.items():
                coefficients[name] = coefficients.get(name, 0.0) + sign * value
        constant = self.constant + other.constant if sign > 0 else self.constant - other.constant
        opaque = self.opaque or other.opaque
        return _Term(
            columns=self.columns | other.columns,
            coefficients=None if opaque else coefficients,
            constant=constant,
            opaque=opaque,
        )

    def __add__(self, other: Any) -> _Term:
        return self._linear(_Term._coerce(other), 1.0)

    def __radd__(self, other: Any) -> _Term:
        return _Term._coerce(other)._linear(self, 1.0)

    def __sub__(self, other: Any) -> _Term:
        return self._linear(_Term._coerce(other), -1.0)

    def __rsub__(self, other: Any) -> _Term:
        return _Term._coerce(other)._linear(self, -1.0)

    def __neg__(self) -> _Term:
        return _Term.constant_of(_ZERO)._linear(self, -1.0)

    def __pos__(self) -> _Term:
        return self

    def _scaled(self, factor: float) -> _Term:
        """Multiply by a *literal*: the affine form survives, scaled. The incidence does not."""
        coefficients = (
            None
            if self.coefficients is None
            else {name: value * factor for name, value in self.coefficients.items()}
        )
        return _Term(
            columns=self.columns,
            coefficients=None if self.opaque else coefficients,
            constant=self.constant * _Constant.of(factor),
            opaque=self.opaque,
        )

    def __mul__(self, other: Any) -> _Term:
        right = _Term._coerce(other)
        if not right.columns and right.constant.literal is not None:
            return self._scaled(right.constant.literal)
        if not self.columns and self.constant.literal is not None:
            return right._scaled(self.constant.literal)
        if not self.columns and not right.columns:
            return _Term.constant_of(self.constant * right.constant)
        # A parameter coefficient, or a product of two variables: the incidence is the union and
        # there is no literal-coefficient affine form: a split row scaled by a parameter is the
        # first case, an equilibrium row's product of two flows the second.
        return _Term(columns=self.columns | right.columns, coefficients=None, constant=_ZERO)

    def __rmul__(self, other: Any) -> _Term:
        return _Term._coerce(other).__mul__(self)

    def __truediv__(self, other: Any) -> _Term:
        right = _Term._coerce(other)
        if not right.columns and right.constant.literal is not None:
            return self._scaled(1.0 / right.constant.literal)
        if not self.columns and not right.columns:
            return _Term.constant_of(self.constant / right.constant)
        return _Term(columns=self.columns | right.columns, coefficients=None, constant=_ZERO)

    def __rtruediv__(self, other: Any) -> _Term:
        return _Term._coerce(other).__truediv__(self)

    def _transcendental(self) -> _Term:
        if not self.columns and not self.opaque:
            return _Term.constant_of(self.constant.opaque())
        return _Term(columns=self.columns, coefficients=None, constant=_ZERO, opaque=self.opaque)

    # -- the refusals ------------------------------------------------------------------------

    def __eq__(self, other: object) -> bool:
        raise TypeError(
            "a traced term cannot be compared for equality: a row builder branched on a value, "
            "which the structural trace cannot follow (T01 §3.3)"
        )

    def __ne__(self, other: object) -> bool:
        raise TypeError("a traced term cannot be compared: a row builder branched on a value")

    def __hash__(self) -> int:
        return id(self)

    def __bool__(self) -> bool:
        raise TypeError(
            "a traced term has no truth value: a row builder branched on a value, which the "
            "structural trace cannot follow (T01 §3.3)"
        )

    def __lt__(self, other: Any) -> bool:
        raise TypeError("a traced term cannot be compared: a row builder branched on a value")

    __le__ = __lt__
    __gt__ = __lt__
    __ge__ = __lt__

    def __float__(self) -> float:
        raise TypeError(
            "a traced term is not a number: a row builder used a parameter or a variable as a "
            "Python float, which the structural trace cannot follow (T01 §3.3)"
        )


class _StructuralAlgebra:
    """`Algebra` over incidence sets. Every function is the identity on the incidence."""

    def exp(self, value: Any) -> _Term:
        return _Term._coerce(value)._transcendental()

    def log(self, value: Any) -> _Term:
        return _Term._coerce(value)._transcendental()

    def sqrt(self, value: Any) -> _Term:
        return _Term._coerce(value)._transcendental()


@dataclass(frozen=True)
class TracedRow:
    """One row's structural content: what it references, and its affine form when it has one."""

    row_id: str
    #: The columns the declaration references, in `variable_ids` order. Never pruned by value.
    columns: tuple[str, ...]
    #: `{column: coefficient}` when the row is affine with literal coefficients, else `None`.
    coefficients: Mapping[str, float] | None
    kind: QuantityKind | None
    #: The instance that authored the row, as the caller declared it. Never parsed from the id.
    unit: str | None
    #: The revision specification this row promotes, for an assembler-authored row (§5.1).
    specification_id: str | None
    origin: str
    _constant: _Constant

    @property
    def is_affine(self) -> bool:
        return self.coefficients is not None

    @property
    def is_specification_row(self) -> bool:
        """A single column with coefficient `+/-1` pinned to a parameter (§3.2).

        The constant must be *parameter-dependent*: a row whose constant is a literal is baked
        into the expression and is not a specification, which ADR 0008 D1.3 forbids anyway.
        """
        if self.coefficients is None or len(self.coefficients) != 1:
            return False
        (coefficient,) = self.coefficients.values()
        return abs(coefficient) == 1.0 and self._constant.literal is None

    def constant(self, parameters: Mapping[str, float]) -> float:
        """The row's constant term at these parameter values. No equation is evaluated."""
        return self._constant.evaluate(parameters)

    def is_copy_row(self) -> bool:
        """Affine over at most two columns with `+/-1` coefficients that cancel: §8.2's shape.

        Two columns must *cancel*: a copy is a difference. `P1 + P2 - s` has two `+1`
        coefficients and is a sum, not a copy, and certifying it as one asserts an identity that
        is false at every state (the Fable review of T01, M4).
        """
        if self.coefficients is None or len(self.coefficients) > 2:
            return False
        if not self.coefficients or any(abs(value) != 1.0 for value in self.coefficients.values()):
            return False
        return len(self.coefficients) == 1 or sum(self.coefficients.values()) == 0.0


@dataclass(frozen=True)
class Declaration:
    """The traced declaration: the incidence graph and everything read from the declaration."""

    model_version: str
    constants_sha256: str
    column_ids: tuple[str, ...]
    row_ids: tuple[str, ...]
    rows: Mapping[str, TracedRow]
    column_kinds: Mapping[str, QuantityKind]
    parameters: Mapping[str, float]

    @property
    def nnz(self) -> int:
        return sum(len(row.columns) for row in self.rows.values())

    def incidence(self) -> Mapping[str, frozenset[str]]:
        return {row_id: frozenset(self.rows[row_id].columns) for row_id in self.row_ids}


def _trace_row(
    equation_id: str,
    build: Any,
    symbols: Mapping[str, _Term],
    outputs: Mapping[str, _Term],
    parameters: Mapping[str, _Term],
    order: Mapping[str, int],
) -> tuple[tuple[str, ...], Mapping[str, float] | None, _Constant]:
    try:
        traced = build(symbols, outputs, parameters, _StructuralAlgebra())
    except StructureUnavailableError:
        raise
    except Exception as error:  # noqa: BLE001 - any builder failure is one unsupported row
        raise StructureUnavailableError(equation_id, f"{type(error).__name__}: {error}") from error
    if not isinstance(traced, _Term):
        raise StructureUnavailableError(
            equation_id, f"the builder returned {type(traced).__name__}, not a traced term"
        )
    columns = tuple(sorted(traced.columns, key=lambda name: order[name]))
    coefficients = (
        None
        if traced.coefficients is None
        else {name: traced.coefficients[name] for name in columns if name in traced.coefficients}
    )
    return columns, coefficients, traced.constant


class _ReadTokens(dict[str, "_Term"]):
    """The parameter tokens, recording every one a builder looks up.

    Every way a builder can reach a parameter records it (review N2): `get` and `in` record the
    key, and any iteration records *every* parameter — a builder that walks the mapping may depend
    on all of it, and a parameter wrongly kept costs nothing while one wrongly dropped would be
    silently replaced by the builder's default.
    """

    def __init__(self, tokens: Mapping[str, _Term]) -> None:
        super().__init__(tokens)
        self.read: set[str] = set()

    def __getitem__(self, key: str) -> _Term:
        self.read.add(key)
        return super().__getitem__(key)

    def get(self, key: str, default: Any = None) -> Any:
        self.read.add(key)
        return super().get(key, default)

    def __contains__(self, key: object) -> bool:
        if isinstance(key, str):
            self.read.add(key)
        return super().__contains__(key)

    def _all(self) -> None:
        self.read.update(super().keys())

    def __iter__(self) -> Iterator[str]:
        self._all()
        return super().__iter__()

    def keys(self) -> Any:
        self._all()
        return super().keys()

    def values(self) -> Any:
        self._all()
        return super().values()

    def items(self) -> Any:
        self._all()
        return super().items()


def parameters_read(spec: ProblemSpec) -> dict[str, frozenset[str]]:
    """Which parameters each row's builder looks up, by row id. Evaluates nothing.

    A parameter no row reads is not part of the function; it is used to keep a removed row's
    parameter (a freed specification's pin, T02 §7.1) out of the declaration's identity, where it
    would make two revisions that differ only in an initial guess two different problems.
    """
    order = {name: index for index, name in enumerate(spec.variable_ids)}
    symbols = {name: _Term.variable(name) for name in spec.variable_ids}
    outputs: dict[str, _Term] = {}
    for block in spec.blocks:
        feeding: Sequence[str] = spec.block_inputs[block.block_id]
        declared: dict[int, set[str]] = {index: set() for index in range(len(block.output_ids))}
        for output_index, input_index in block.jacobian_pattern():
            declared[output_index].add(feeding[input_index])
        for index, output_id in enumerate(block.output_ids):
            outputs[f"{block.block_id}.{output_id}"] = _Term.from_block(frozenset(declared[index]))
    reads: dict[str, frozenset[str]] = {}
    for equation in spec.equations:
        tokens = _ReadTokens(
            {name: _Term.constant_of(_Constant.parameter(name)) for name in spec.parameters}
        )
        _trace_row(equation.equation_id, equation.build, symbols, outputs, tokens, order)
        reads[equation.equation_id] = frozenset(tokens.read)
    return reads


def trace_declaration(
    spec: ProblemSpec,
    *,
    model_version: str = "",
    constants_sha256: str = "",
    specification_ids: Mapping[str, str] | None = None,
    row_units: Mapping[str, str] | None = None,
) -> Declaration:
    """Run every row builder under the structural algebra. Evaluates nothing (A03).

    `specification_ids` names, for each row that pins one, the revision specification it carries.
    `row_units` names the instance that authored each row.

    **Both are given, never parsed from the id.** An earlier version read the authoring unit off
    the `<unit>:<family>:<part>` prefix, and assertion A15 caught it: relabelling every id by a
    bijection emptied the attribution silently, which would have emptied the unit-local degree of
    freedom count and with it the localization that names an over-specified unit. A layer that
    guesses from a name is a layer that stops working when the name changes.
    """
    order = {name: index for index, name in enumerate(spec.variable_ids)}
    symbols = {name: _Term.variable(name) for name in spec.variable_ids}

    outputs: dict[str, _Term] = {}
    for block in spec.blocks:
        feeding: Sequence[str] = spec.block_inputs[block.block_id]
        declared: dict[int, set[str]] = {index: set() for index in range(len(block.output_ids))}
        for output_index, input_index in block.jacobian_pattern():
            declared[output_index].add(feeding[input_index])
        for index, output_id in enumerate(block.output_ids):
            outputs[f"{block.block_id}.{output_id}"] = _Term.from_block(frozenset(declared[index]))

    tokens = {name: _Term.constant_of(_Constant.parameter(name)) for name in spec.parameters}

    rows: dict[str, TracedRow] = {}
    for equation in spec.equations:
        columns, coefficients, constant = _trace_row(
            equation.equation_id, equation.build, symbols, outputs, tokens, order
        )
        rows[equation.equation_id] = TracedRow(
            row_id=equation.equation_id,
            columns=columns,
            coefficients=coefficients,
            kind=spec.row_kinds.get(equation.equation_id),
            unit=(row_units or {}).get(equation.equation_id),
            specification_id=(specification_ids or {}).get(equation.equation_id),
            origin=equation.origin,
            _constant=constant,
        )

    return Declaration(
        model_version=model_version,
        constants_sha256=constants_sha256,
        column_ids=tuple(spec.variable_ids),
        row_ids=tuple(spec.equation_ids),
        rows=rows,
        column_kinds=dict(spec.variable_kinds),
        parameters=dict(spec.parameters),
    )
