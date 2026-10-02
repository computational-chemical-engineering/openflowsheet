"""The CasADi adapter. **This is the only module in `openflowsheet` that imports CasADi.**

ADR 0003 selected CasADi 3.8.0 on the P02/P03 evidence; ADR 0003 D5.7 confines the import to the
compiler and adapter so that the orchestrator, the models and the application layer never depend on
it. `tests/test_k01_no_backend_in_orchestrator.py` enforces that confinement by inspection rather
than by convention.

Three hazards shape this file, all of which produce a *plausible wrong answer* rather than an error,
and each of which is therefore accompanied by the test that would catch it.

**1. Two independent permutation hazards.** CasADi fills a sparse `DM` in column-major (CCS) order,
not in the order triples are supplied, so values written in triplet order silently produce a
permuted Jacobian; and a row's identity is its equation id, not its position. Both are handled by
never using a position where a name will do: the assembled matrix is read out through CasADi's own
`sparse()` triplets and mapped to `(row_id, col_id)` explicitly, and the CSC arrays are then built
from that mapping. `test_a_permuted_row_order_is_detected` perturbs the ordering to show the test
would notice.

**2. Undeclared block sparsity.** An opaque callback whose Jacobian sparsity is not declared makes
CasADi assume every output depends on every input, and the block's structural zeros reappear as
stored zeros. P02 measured 66 stored entries instead of 60. `has_jac_sparsity` and
`get_jac_sparsity` below are what prevent it.

**3. A fabricated second derivative.** Second order through an opaque callback is genuinely absent.
It is reported `absent` and any attempt to obtain it raises; it is never zeros
(`docs/interfaces-frozen.md` §1, ADR 0003 D5.4).
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

import casadi as ca

from openflowsheet.canonical import (
    constants_sha256,
    model_version,
    state_sha256,
    structure_sha256,
)
from openflowsheet.compile.spec import Algebra, DomainError, ProblemSpec, PropertyBlock
from openflowsheet.compiled import (
    Capabilities,
    CompiledProblemMetadata,
    EvaluationContext,
    EvaluationResult,
    JacobianResult,
    ProcessState,
    StateVector,
)

BACKEND = "casadi"


class _CasadiAlgebra:
    """The `Algebra` a model's row builders are handed. Thin by design."""

    def exp(self, value: Any) -> Any:
        return ca.exp(value)

    def log(self, value: Any) -> Any:
        return ca.log(value)

    def sqrt(self, value: Any) -> Any:
        return ca.sqrt(value)


class _Counters:
    """Per-block call accounting (ADR 0003 D5.5).

    The count is evidence, not telemetry. A backend that silently fell back to finite differences
    would call a block's value method `n_inputs + 1` times per Jacobian instead of once, so the
    ratio is how a differencing fallback is detected without trusting the backend's own claim.
    """

    def __init__(self, block_ids: Sequence[str]) -> None:
        self._counts: dict[str, dict[str, int]] = {
            block_id: {"value_calls": 0, "jacobian_calls": 0} for block_id in block_ids
        }

    def record_value(self, block_id: str) -> None:
        self._counts[block_id]["value_calls"] += 1

    def record_jacobian(self, block_id: str) -> None:
        self._counts[block_id]["jacobian_calls"] += 1

    def reset(self) -> None:
        for counts in self._counts.values():
            counts["value_calls"] = 0
            counts["jacobian_calls"] = 0

    def snapshot(self) -> Mapping[str, Mapping[str, int]]:
        return {block_id: dict(counts) for block_id, counts in self._counts.items()}


def _sparsity_of(block: PropertyBlock) -> ca.Sparsity:
    pattern = block.jacobian_pattern()
    sparsity = ca.Sparsity(len(block.output_ids), len(block.input_ids))
    for row, column in pattern:
        sparsity.add_nz(row, column)
    return sparsity


def _fill(sparsity: ca.Sparsity, triples: Sequence[tuple[int, int, float]]) -> ca.DM:
    """Place declared nonzeros into a sparse `DM` **by (row, column)**, never by triple order.

    `ca.DM(sparsity, values)` interprets `values` in the matrix's own column-major storage order.
    Handing it triples in declaration order is the permutation hazard this function exists to make
    impossible: every value is written through `dm[row, column]`, which cannot be order-sensitive.
    """
    result = ca.DM(sparsity, 0.0)
    supplied: set[tuple[int, int]] = set()
    for row, column, value in triples:
        if not sparsity.has_nz(row, column):
            raise ValueError(
                f"block returned a Jacobian value at ({row}, {column}), which it did not declare "
                "in jacobian_pattern(). An undeclared nonzero is a wrong sparsity claim, not a "
                "value to be silently dropped."
            )
        if (row, column) in supplied:
            raise ValueError(
                f"block returned two values for ({row}, {column}). Letting the last one win hides "
                "which of the two the block actually meant."
            )
        supplied.add((row, column))
        result[row, column] = value

    # A declared entry that is not supplied would land here as the 0.0 the matrix was filled with,
    # which is indistinguishable from a block that meant zero. The pattern is a claim about the
    # *function*, so a block that declares an entry must produce it — passing 0.0 explicitly where
    # the value happens to vanish.
    declared = {
        (int(row), int(column)) for row, column in zip(*sparsity.get_triplet(), strict=True)
    }
    missing = sorted(declared - supplied)
    if missing:
        raise ValueError(
            f"block declared Jacobian entries {missing} in jacobian_pattern() but returned no "
            "value for them. An omitted declared entry becomes a silent stored zero; pass 0.0 "
            "explicitly if the derivative genuinely vanishes there."
        )
    return result


# `ca.Callback` is `Any` because the local stub declares CasADi untyped (see stubs/casadi), so
# --strict's disallow-subclassing-any fires. Subclassing Callback *is* CasADi's documented
# extension mechanism and there is no alternative; the ignore is per-class, not a global relaxation.
class _JacobianCallback(ca.Callback):  # type: ignore[misc]
    """The Jacobian of a block, itself opaque, with the block's *declared* sparsity as its shape."""

    def __init__(self, name: str, owner: _BlockCallback) -> None:
        ca.Callback.__init__(self)
        self.owner = owner
        self.construct(name, {"enable_fd": False})

    def get_n_in(self) -> int:
        return 2

    def get_n_out(self) -> int:
        return 1

    def get_sparsity_in(self, index: int) -> ca.Sparsity:
        block = self.owner.block
        if index == 0:
            return ca.Sparsity.dense(len(block.input_ids), 1)
        return ca.Sparsity.dense(len(block.output_ids), 1)

    def get_sparsity_out(self, index: int) -> ca.Sparsity:
        del index
        return self.owner.sparsity

    def eval(self, arg: Sequence[ca.DM]) -> list[ca.DM]:
        block = self.owner.block
        inputs = [float(arg[0][index]) for index in range(len(block.input_ids))]
        self.owner.counters.record_jacobian(block.block_id)
        try:
            triples = block.jacobian(inputs)
        except DomainError as error:
            self.owner.domain_error = f"{block.block_id}: {error}"
            raise
        try:
            return [_fill(self.owner.sparsity, triples)]
        except ValueError as error:
            self.owner.block_error = f"{block.block_id}: {error}"
            raise


class _BlockCallback(ca.Callback):  # type: ignore[misc]
    """Wraps a backend-free `PropertyBlock` as a CasADi `Callback` with declared sparsity."""

    def __init__(self, block: PropertyBlock, counters: _Counters) -> None:
        ca.Callback.__init__(self)
        self.block = block
        self.counters = counters
        self.sparsity = _sparsity_of(block)
        self.domain_error: str | None = None
        # CasADi catches a Python exception raised inside `eval` and re-raises its own generic
        # "Error in Function::call" wrapper, discarding the message. A caller handed that text
        # learns nothing actionable, so the real reason is recorded here on the way out and the
        # boundary prefers it over the wrapper.
        self.block_error: str | None = None
        self._jacobian: _JacobianCallback | None = None
        self.construct(block.block_id, {"enable_fd": False})

    def get_n_in(self) -> int:
        return 1

    def get_n_out(self) -> int:
        return 1

    def get_sparsity_in(self, index: int) -> ca.Sparsity:
        del index
        return ca.Sparsity.dense(len(self.block.input_ids), 1)

    def get_sparsity_out(self, index: int) -> ca.Sparsity:
        del index
        return ca.Sparsity.dense(len(self.block.output_ids), 1)

    def eval(self, arg: Sequence[ca.DM]) -> list[ca.DM]:
        inputs = [float(arg[0][index]) for index in range(len(self.block.input_ids))]
        self.counters.record_value(self.block.block_id)
        try:
            return [ca.DM(list(self.block.values(inputs)))]
        except DomainError as error:
            self.domain_error = f"{self.block.block_id}: {error}"
            raise

    def has_jacobian(self) -> bool:
        return True

    def has_jac_sparsity(self, oind: int, iind: int) -> bool:
        """Yes — and saying so is what preserves the block's structural zeros.

        Without this, CasADi propagates the dependency structure of an opaque call: every output
        assumed to depend on every input. P02 measured the consequence as 66 stored entries in the
        assembled Jacobian instead of 60.
        """
        del oind, iind
        return True

    def get_jac_sparsity(self, oind: int, iind: int, symmetric: bool) -> ca.Sparsity:
        del oind, iind, symmetric
        return self.sparsity

    def get_jacobian(
        self, name: str, inames: Sequence[str], onames: Sequence[str], opts: Mapping[str, Any]
    ) -> ca.Callback:
        del inames, onames, opts
        if self._jacobian is None:
            self._jacobian = _JacobianCallback(name, self)
        return self._jacobian


def _csc_from_triplets(
    rows: Sequence[int],
    columns: Sequence[int],
    values: Sequence[float],
    row_ids: Sequence[str],
    col_ids: Sequence[str],
) -> tuple[tuple[int, ...], tuple[int, ...], tuple[float, ...]]:
    """Build canonical CSC arrays from `(row, column, value)` triplets.

    The triplets come from CasADi's own `sparse()` accessor, so the *values* are already paired
    with their true coordinates; what this function fixes is the ordering, which must be
    column-major with ascending row index inside each column, independently of what order the
    backend happened to emit. Sorting by `(column, row)` rather than trusting the emission order is
    the second half of the permutation defence: the first half is never writing a value by position.

    `row_ids` and `col_ids` are passed only to size and check the result — a triplet outside the
    declared shape means the assembled matrix and the declared identity disagree, which is exactly
    the confusion CSC arrays are too anonymous to reveal later.
    """
    n_rows, n_columns = len(row_ids), len(col_ids)
    out_of_range = [
        (row, column)
        for row, column in zip(rows, columns, strict=True)
        if not (0 <= row < n_rows and 0 <= column < n_columns)
    ]
    if out_of_range:
        raise ValueError(
            f"assembled Jacobian has entries outside its declared {n_rows}x{n_columns} shape: "
            f"{out_of_range[:5]}"
        )

    ordered = sorted(zip(columns, rows, values, strict=True))
    indptr = [0]
    indices: list[int] = []
    data: list[float] = []
    cursor = 0
    for column in range(n_columns):
        while cursor < len(ordered) and ordered[cursor][0] == column:
            _, row, value = ordered[cursor]
            indices.append(row)
            data.append(float(value))
            cursor += 1
        indptr.append(len(data))
    return tuple(indptr), tuple(indices), tuple(data)


class CasadiCompiledProblem:
    """A `CompiledProblem` on CasADi. Satisfies the frozen Protocol in `openflowsheet.compiled`.

    Construct it with `compile_problem`, which validates the spec first. The executable CasADi
    objects live here and are deliberately not serializable; only `metadata` is (blueprint §3.1).
    """

    def __init__(self, spec: ProblemSpec) -> None:
        spec.validate()
        self._spec = spec
        self._counters = _Counters([block.block_id for block in spec.blocks])
        self._callbacks = {
            block.block_id: _BlockCallback(block, self._counters) for block in spec.blocks
        }

        symbols = {name: ca.MX.sym(name) for name in spec.variable_ids}
        outputs: dict[str, Any] = {}
        for block in spec.blocks:
            feeding = spec.block_inputs[block.block_id]
            call = self._callbacks[block.block_id](ca.vertcat(*[symbols[n] for n in feeding]))
            for index, output_id in enumerate(block.output_ids):
                outputs[f"{block.block_id}.{output_id}"] = call[index]

        algebra: Algebra = _CasadiAlgebra()
        rows = [
            equation.build(symbols, outputs, spec.parameters, algebra)
            for equation in spec.equations
        ]
        vector = ca.vertcat(*rows)
        argument = ca.vertcat(*[symbols[name] for name in spec.variable_ids])

        self._residual = ca.Function("residual", [argument], [vector])
        self._jacobian = ca.Function("jacobian", [argument], [ca.jacobian(vector, argument)])

        seed = ca.MX.sym("seed", len(spec.variable_ids))
        adjoint = ca.MX.sym("adjoint", len(spec.equations))
        self._jvp = ca.Function("jvp", [argument, seed], [ca.jtimes(vector, argument, seed)])
        self._vjp = ca.Function(
            "vjp", [argument, adjoint], [ca.jtimes(vector, argument, adjoint, True)]
        )

        # ADR 0002 D2.5: the compiler assigns `model_version`, the spec supplies only the label.
        # Computed from the spec's own ids and accumulation kinds, so a structural change cannot
        # leave the identity behind.
        assigned_version = model_version(
            spec.label,
            structure_sha256(
                spec.variable_ids, spec.equation_ids, spec.parameter_ids, spec.row_accumulation
            ),
        )
        self.metadata = CompiledProblemMetadata(
            model_version=assigned_version,
            backend=BACKEND,
            backend_version=ca.__version__,
            variable_ids=spec.variable_ids,
            equation_ids=spec.equation_ids,
            parameter_ids=spec.parameter_ids,
            column_scales=dict(spec.column_scales),
            row_scales=dict(spec.row_scales),
            row_accumulation=dict(spec.row_accumulation),
            capabilities=Capabilities(
                jacobian="exact_sparse_csc",
                jvp="exact",
                vjp="exact",
                # Absent, and reported so. Second order through an opaque callback does not exist,
                # and `"exact"` here with zeros behind it would be the placeholder success path
                # CLAUDE.md forbids and the frozen interface calls out by name.
                hessian="absent",
            ),
            constants_sha256=constants_sha256(spec.parameters, spec.parameter_ids),
        )

    # -- the frozen boundary ---------------------------------------------------------------

    def _check_context(self, context: EvaluationContext) -> None:
        """The context *pins* model and data versions (plan §2.1). A mismatch is a wrong answer.

        Evaluating under a context that names a different problem would return this problem's
        identity in the result, so the caller would be told its own pin had been honoured when it
        had been ignored. Refused for the same reason a mismatched state length is.
        """
        if context.model_version != self.metadata.model_version:
            raise ValueError(
                f"context pins model_version {context.model_version!r} but this problem is "
                f"{self.metadata.model_version!r}"
            )
        if context.constants_sha256 != self.metadata.constants_sha256:
            raise ValueError(
                "context pins a different constants_sha256 than this problem's; the pinned inputs "
                "it names are not the ones compiled in"
            )

    def _check_state(self, x: StateVector) -> None:
        expected = len(self._spec.variable_ids)
        if x.shape != (expected,):
            raise ValueError(
                f"state has shape {x.shape}; this problem has {expected} ordered free variables. "
                "Evaluating a mismatched vector would silently answer about a different problem."
            )

    def _begin(self) -> None:
        """Clear the per-call accounting and any stale domain report before an evaluation."""
        self._counters.reset()
        for callback in self._callbacks.values():
            callback.domain_error = None
            callback.block_error = None

    def _domain_error(self) -> str | None:
        reports = [
            callback.domain_error
            for callback in self._callbacks.values()
            if callback.domain_error is not None
        ]
        return "; ".join(reports) if reports else None

    def _block_error(self) -> str | None:
        reports = [
            callback.block_error
            for callback in self._callbacks.values()
            if callback.block_error is not None
        ]
        return "; ".join(reports) if reports else None

    def _failure_message(self, error: BaseException) -> str:
        """What the block actually said, falling back to the backend's wrapper only if silent."""
        return self._domain_error() or self._block_error() or str(error).split("\n")[0][:300]

    def residual(self, x: StateVector, context: EvaluationContext) -> EvaluationResult:
        """Evaluate the residual at `x`. Nothing in `context` reaches the evaluated function.

        `workspace` is read here exactly nowhere, which is what ADR 0008 D4.2 requires and what
        `test_the_workspace_is_inert` demonstrates rather than asserts by inspection.
        """
        self._check_state(x)
        self._check_context(context)
        identity = self._identity(x, context)
        if context.accuracy_policy != "exact-double":
            return EvaluationResult(
                status="unsupported",
                values=None,
                equation_ids=self._spec.equation_ids,
                counters=self._counters.snapshot(),
                message=f"accuracy policy {context.accuracy_policy!r} is not supported",
                **identity,
            )
        self._begin()
        try:
            values = self._residual(ca.DM(x.tolist()))
        except Exception as error:  # noqa: BLE001 - the backend wraps the block's exception
            return EvaluationResult(
                status="invalid_trial_state" if self._domain_error() else "error",
                values=None,
                equation_ids=self._spec.equation_ids,
                counters=self._counters.snapshot(),
                message=self._failure_message(error),
                **identity,
            )
        evaluated = tuple(float(values[index]) for index in range(len(self._spec.equations)))
        non_finite = [
            equation
            for equation, value in zip(self._spec.equation_ids, evaluated, strict=True)
            if not math.isfinite(value)
        ]
        if non_finite:
            # A NaN or infinity is not a residual, and reporting it `ok` hands a solver a number it
            # will act on. `serialize.check_evaluation_document` already refused such a document,
            # so the two halves of K01 disagreed until this returned `invalid_trial_state` too.
            return EvaluationResult(
                status="invalid_trial_state",
                values=None,
                equation_ids=self._spec.equation_ids,
                counters=self._counters.snapshot(),
                message=f"non-finite residual at {non_finite}",
                **identity,
            )
        return EvaluationResult(
            status="ok",
            values=evaluated,
            equation_ids=self._spec.equation_ids,
            counters=self._counters.snapshot(),
            **identity,
        )

    def jacobian(self, x: StateVector, context: EvaluationContext) -> JacobianResult:
        """Evaluate the assembled sparse Jacobian at `x`, in canonical CSC with named identity."""
        self._check_state(x)
        self._check_context(context)
        identity = self._identity(x, context)
        row_ids, col_ids = self._spec.equation_ids, self._spec.variable_ids
        if context.accuracy_policy != "exact-double":
            return JacobianResult(
                status="unsupported",
                row_ids=row_ids,
                col_ids=col_ids,
                indptr=(0,) * (len(col_ids) + 1),
                indices=(),
                data=(),
                counters=self._counters.snapshot(),
                pattern_provenance="backend-declared",
                message=f"accuracy policy {context.accuracy_policy!r} is not supported",
                **identity,
            )
        self._begin()
        try:
            assembled = self._jacobian(ca.DM(x.tolist()))
        except Exception as error:  # noqa: BLE001 - the backend wraps the block's exception
            return JacobianResult(
                status="invalid_trial_state" if self._domain_error() else "error",
                row_ids=row_ids,
                col_ids=col_ids,
                indptr=(0,) * (len(col_ids) + 1),
                indices=(),
                data=(),
                counters=self._counters.snapshot(),
                pattern_provenance="backend-declared",
                message=self._failure_message(error),
                **identity,
            )

        rows, columns = assembled.sparsity().get_triplet()
        # `nonzeros()` materializes the whole list, so calling it per entry is quadratic in nnz:
        # measured 9.8 ms at 898 nonzeros but 424 ms at 5998, which would dominate K03's Newton at
        # flowsheet scale while being invisible at SYN-001's 60. Fetch it once.
        values = [float(value) for value in assembled.nonzeros()]
        indptr, indices, data = _csc_from_triplets(rows, columns, values, row_ids, col_ids)
        if any(not math.isfinite(value) for value in data):
            return JacobianResult(
                status="invalid_trial_state",
                row_ids=row_ids,
                col_ids=col_ids,
                indptr=(0,) * (len(col_ids) + 1),
                indices=(),
                data=(),
                counters=self._counters.snapshot(),
                pattern_provenance="backend-declared",
                message="non-finite Jacobian entry",
                **identity,
            )
        return JacobianResult(
            status="ok",
            row_ids=row_ids,
            col_ids=col_ids,
            indptr=indptr,
            indices=indices,
            data=data,
            counters=self._counters.snapshot(),
            # The pattern came from CasADi's structural propagation over blocks that declared their
            # own sparsity (`has_jac_sparsity`). Nothing here was obtained by thresholding a
            # numerical value, which is the other member of this vocabulary and would be a
            # different and much weaker claim.
            pattern_provenance="backend-declared",
            source_map=self._source_map(),
            **identity,
        )

    def structural_pattern(self) -> tuple[tuple[str, str], ...]:
        """The assembled Jacobian's **structural** pattern, as `(row id, column id)` pairs.

        Read from the compiled Jacobian function's declared output sparsity — CasADi's structural
        propagation over blocks that declare their own sparsity — so no Jacobian is evaluated and
        no entry is filtered by value (structural zeros included). T03 §5.2, ADR 0005 D5.
        """
        rows, columns = self._jacobian.sparsity_out(0).get_triplet()
        return tuple(
            (self._spec.equation_ids[row], self._spec.variable_ids[column])
            for row, column in zip(rows, columns, strict=True)
        )

    def reconstruct(self, x: StateVector, context: EvaluationContext) -> ProcessState:
        """Map the dense state back to named variables. K01 reconstructs variables only."""
        self._check_state(x)
        return ProcessState(
            variables=dict(
                zip(self._spec.variable_ids, (float(value) for value in x), strict=True)
            ),
            phase_signature=context.phase_signature,
        )

    # -- optional capabilities -------------------------------------------------------------

    def jvp(
        self, x: StateVector, seed: StateVector, context: EvaluationContext
    ) -> tuple[float, ...]:
        """Exact forward product J @ seed (ADR 0003 D5.3), negotiated via `capabilities.jvp`."""
        self._check_state(x)
        del context
        self._begin()
        product = self._jvp(ca.DM(x.tolist()), ca.DM(seed.tolist()))
        return tuple(float(product[index]) for index in range(len(self._spec.equations)))

    def vjp(
        self, x: StateVector, adjoint: StateVector, context: EvaluationContext
    ) -> tuple[float, ...]:
        """Exact reverse product Jᵀ @ adjoint (ADR 0003 D5.3)."""
        self._check_state(x)
        del context
        self._begin()
        product = self._vjp(ca.DM(x.tolist()), ca.DM(adjoint.tolist()))
        return tuple(float(product[index]) for index in range(len(self._spec.variable_ids)))

    def hessian(self, x: StateVector, context: EvaluationContext) -> None:
        """Absent through an opaque callback, and it raises rather than returning zeros.

        ADR 0003 D5.4 and `docs/interfaces-frozen.md` §1: a missing exact Hessian cannot be replaced
        with fabricated zeros. Returning a zero matrix here would be numerically indistinguishable
        from a genuine one at a stationary point, which is precisely why it is forbidden.
        """
        del x, context
        raise NotImplementedError(
            "second order is absent through an opaque property callback on this backend "
            "(capabilities.hessian == 'absent'). It is not zero; it is unavailable."
        )

    # -- identity --------------------------------------------------------------------------

    def _identity(self, x: StateVector, context: EvaluationContext) -> dict[str, Any]:
        """The four pairing fields both result types carry (ADR 0008 D2.4).

        Built in one place so a residual and a Jacobian at the same state cannot disagree about
        what state or what problem they describe.
        """
        return {
            "phase_signature": context.phase_signature,
            "model_version": self.metadata.model_version,
            "constants_sha256": self.metadata.constants_sha256,
            "state_sha256": state_sha256(x, self._spec.variable_ids),
        }

    def _source_map(self) -> tuple[Mapping[str, Any], ...]:
        return tuple(
            {"row_id": equation.equation_id, "origin": equation.origin}
            for equation in self._spec.equations
            if equation.origin
        )


def compile_problem(spec: ProblemSpec) -> CasadiCompiledProblem:
    """Compile a backend-free `ProblemSpec` into a runnable `CompiledProblem` on CasADi."""
    return CasadiCompiledProblem(spec)
