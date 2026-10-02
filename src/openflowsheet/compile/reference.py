"""Evaluate a `ProblemSpec`'s rows with plain Python floats, no backend.

**This is not a backend and it is not a second production route.** It returns row *values* and
nothing else: no derivatives, no sparsity, no `CompiledProblem`, no identity hashes. ADR 0003
selected CasADi and ADR 0003 D5.7 keeps the backend import inside one adapter; nothing here
changes either, because nothing here compiles anything.

What it is for is that a `RowBuilder` is written against the `Algebra` protocol, so the same
function that CasADi traces symbolically can be called on floats. Two things follow that are worth
the forty lines:

1. **ADR 0008 D4.3 is checkable directly.** "`HEAT-mole` with `n_in,i = 1`, `n_out,i = 0.5` returns
   `+0.5 mol/s` exactly" is a statement about one row at one state. Going through a compile, a
   dense assembly and a CSC extraction to check it would test the compiler, not the row.
2. **The backend plumbing gets an independent witness.** Evaluating the same spec both ways must
   agree. That checks the adapter — variable ordering, block wiring, parameter binding — and it is
   honest about what it does not check: both routes call the same `build` and the same
   `PropertyBlock`, so this is a plumbing cross-check, not an independent derivation of the
   equations (blueprint A09's rule, applied to code rather than to thermodynamics).
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

from openflowsheet.compile.spec import Expr, ProblemSpec


class FloatAlgebra:
    """The `Algebra` protocol over `float`. Deliberately the whole of it, so it cannot drift."""

    def exp(self, value: Expr) -> Expr:
        return math.exp(value)

    def log(self, value: Expr) -> Expr:
        return math.log(value)

    def sqrt(self, value: Expr) -> Expr:
        return math.sqrt(value)


def block_outputs(spec: ProblemSpec, values: Mapping[str, float]) -> dict[str, float]:
    """Call every block on its declared inputs and key the results as the row builders see them.

    Raises `KeyError` naming the variable if a block's declared input is missing from `values`,
    rather than defaulting it — a defaulted input is a plausible wrong number.
    """
    outputs: dict[str, float] = {}
    for block in spec.blocks:
        feeding = spec.block_inputs[block.block_id]
        inputs = [float(values[name]) for name in feeding]
        produced = block.values(inputs)
        if len(produced) != len(block.output_ids):
            raise ValueError(
                f"block {block.block_id!r} declares {len(block.output_ids)} outputs but returned "
                f"{len(produced)}"
            )
        for output_id, produced_value in zip(block.output_ids, produced, strict=True):
            outputs[f"{block.block_id}.{output_id}"] = float(produced_value)
    return outputs


def row_values(spec: ProblemSpec, values: Mapping[str, float]) -> dict[str, float]:
    """Every row of `spec` at the state `values`, keyed by equation id.

    `values` must supply every declared variable. A missing one raises rather than defaulting,
    for the same reason as above.
    """
    missing = [name for name in spec.variable_ids if name not in values]
    if missing:
        raise KeyError(f"no value for variables {missing}")
    symbols = {name: float(values[name]) for name in spec.variable_ids}
    outputs = block_outputs(spec, symbols)
    algebra = FloatAlgebra()
    return {
        equation.equation_id: float(equation.build(symbols, outputs, spec.parameters, algebra))
        for equation in spec.equations
    }


def row_vector(spec: ProblemSpec, values: Mapping[str, float]) -> tuple[float, ...]:
    """The rows in `spec.equations` order, for comparison with a compiled `EvaluationResult`."""
    evaluated = row_values(spec, values)
    return tuple(evaluated[equation_id] for equation_id in spec.equation_ids)


def state_vector(spec: ProblemSpec, values: Mapping[str, float]) -> Sequence[float]:
    """`values` as the dense `x` the compiled problem expects, in `variable_ids` order."""
    return [float(values[name]) for name in spec.variable_ids]
