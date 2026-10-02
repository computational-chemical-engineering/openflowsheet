"""The trial-state harness for T05's A04/A05: one unit's rows and Jacobian at a registered state.

Not collected as tests. Model-agnostic: a test supplies a `build` callable that turns the YAML's
`configuration` and `parameters` for a state into a `TrialUnit` (the unit, its wiring, the streams
whose `(n, T, P)` are columns, and any lifted inlet whose split the harness must add as free
columns); the harness does the rest.

What it does (T05 spec §13.4, §14, A04, A05):

1. Assembles the one unit through `models.assemble`, exactly as a flowsheet would, and adds each
   lifted inlet's split (`<S>.vap.<c>`, `<S>.liq.<c>`, `<S>.V`, `<S>.L`) as free columns — the
   producer that would own them is not in the problem, and the reader's rows read them.
2. Requires the assembled columns to be exactly the registered state's `x` keys, and the rows
   exactly its `rows` keys with the registered kinds.
3. Compiles through K01's CasADi adapter (`compile_problem`), the path K02's tests use, and
   evaluates the residual and the Jacobian at the registered `x`.
4. Compares every row value within `row_relative_tolerance x term_scale`; every registered
   Jacobian nonzero within `jacobian_relative_tolerance` relative; every registered cancelling
   partial within `jacobian_relative_tolerance x` its registered partial scale; and every other
   entry the compiled structure holds in the unit's rows must be exactly `0.0`.

Errors are measured against the registered 20-digit strings at full precision (`decimal`), so the
ratios it reports are the implementation's own floors (W0.3), not the conversion error of the
expectation.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from decimal import Decimal
from typing import Any

import numpy as np
from t05_support import REF

from openflowsheet.compile.casadi_backend import compile_problem
from openflowsheet.compile.spec import ProblemSpec, QuantityKind
from openflowsheet.compiled import EvaluationContext
from openflowsheet.models import UnitModel, Wiring, assemble
from openflowsheet.models.syn001 import COMPONENTS
from openflowsheet.models.syn001.tp_state import (
    liquid_flow_id,
    liquid_total_id,
    vapor_flow_id,
    vapor_total_id,
)

ROW_RELATIVE = float(REF["constants"]["row_relative_tolerance"])
JACOBIAN_RELATIVE = float(REF["constants"]["jacobian_relative_tolerance"])


@dataclass(frozen=True)
class TrialUnit:
    """What a test builds from one registered trial state."""

    unit: UnitModel
    wiring: Wiring
    #: Streams whose `(n, T, P)` are free columns, in allocation order.
    streams: tuple[str, ...]
    #: Streams read as lifted: their split is allocated here as free columns.
    lifted_inlets: tuple[str, ...] = ()


@dataclass
class TrialComparison:
    """One state's measurement. `failures` empty means A04 and A05 hold at this state."""

    model_id: str
    state_id: str
    #: Largest `|row error| / (row_relative x term_scale)` over the unit's rows.
    worst_row_ratio: float = 0.0
    worst_row: str = ""
    #: Largest `relative error / jacobian_relative` over the registered nonzeros, and the
    #: cancelling partials measured against their partial scale.
    worst_jacobian_ratio: float = 0.0
    worst_entry: str = ""
    failures: list[str] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"{self.model_id} {self.state_id}: worst row {self.worst_row_ratio:.3g} of its "
            f"tolerance ({self.worst_row}); worst Jacobian entry {self.worst_jacobian_ratio:.3g} "
            f"of its tolerance ({self.worst_entry})"
        )


def trial_states(model_id: str) -> list[str]:
    return list(REF["trial_states"][model_id]["states"])


def assemble_trial(trial: TrialUnit, label: str) -> ProblemSpec:
    """Step 1: the one unit through `models.assemble`, plus each lifted inlet's split columns."""
    spec = assemble(
        label=label,
        units=[trial.unit],
        wiring={trial.unit.unit_id: trial.wiring},
        streams=trial.streams,
        components=COMPONENTS,
    )
    extra: list[str] = []
    kinds: dict[str, QuantityKind] = dict(spec.variable_kinds)
    for stream in trial.lifted_inlets:
        for name in (
            *(vapor_flow_id(stream, component) for component in COMPONENTS),
            *(liquid_flow_id(stream, component) for component in COMPONENTS),
            vapor_total_id(stream),
            liquid_total_id(stream),
        ):
            if name not in spec.variable_ids and name not in extra:
                extra.append(name)
                kinds[name] = "molar_flow"
    return replace(spec, variable_ids=(*spec.variable_ids, *extra), variable_kinds=kinds)


def compare_trial_state(
    model_id: str,
    state_id: str,
    build: Callable[[Mapping[str, Any], Mapping[str, str]], TrialUnit],
) -> TrialComparison:
    """Assemble, compile and evaluate one unit at `ref.trial_states.<model>.<state>`."""
    entry = REF["trial_states"][model_id]["states"][state_id]
    comparison = TrialComparison(model_id=model_id, state_id=state_id)
    failures = comparison.failures

    trial = build(entry["configuration"], entry["parameters"])
    spec = assemble_trial(trial, label=f"T05-trial-{model_id}-{state_id}")

    registered_x: Mapping[str, str] = entry["x"]
    if set(spec.variable_ids) != set(registered_x):
        failures.append(
            f"columns differ: extra {sorted(set(spec.variable_ids) - set(registered_x))}, "
            f"missing {sorted(set(registered_x) - set(spec.variable_ids))}"
        )
        return comparison
    registered_rows: Mapping[str, Mapping[str, str]] = entry["rows"]
    row_ids = [equation.equation_id for equation in spec.equations]
    if set(row_ids) != set(registered_rows) or len(row_ids) != len(registered_rows):
        failures.append(
            f"rows differ: extra {sorted(set(row_ids) - set(registered_rows))}, "
            f"missing {sorted(set(registered_rows) - set(row_ids))}"
        )
        return comparison
    for row, registered in registered_rows.items():
        if spec.row_kinds.get(row) != registered["kind"]:
            failures.append(
                f"{row}: kind {spec.row_kinds.get(row)!r}, registered {registered['kind']}"
            )

    problem = compile_problem(spec)
    context = EvaluationContext(
        model_version=problem.metadata.model_version,
        constants_sha256=problem.metadata.constants_sha256,
    )
    x = np.array([float(registered_x[name]) for name in spec.variable_ids])

    residual = problem.residual(x, context)
    if residual.status != "ok" or residual.values is None:
        failures.append(f"residual evaluation: {residual.status} {residual.message}")
        return comparison
    for row, value in zip(residual.equation_ids, residual.values, strict=True):
        registered = registered_rows[row]
        tolerance = ROW_RELATIVE * float(registered["term_scale"])
        ratio = float(abs(Decimal(float(value)) - Decimal(registered["value"]))) / tolerance
        if ratio > comparison.worst_row_ratio:
            comparison.worst_row_ratio, comparison.worst_row = ratio, row
        if ratio > 1.0:
            failures.append(f"{row} = {float(value)!r}, registered {registered['value']}")

    jacobian = problem.jacobian(x, context)
    if jacobian.status != "ok":
        failures.append(f"jacobian evaluation: {jacobian.status} {jacobian.message}")
        return comparison
    stored: dict[tuple[str, str], float] = {}
    for column, column_id in enumerate(jacobian.col_ids):
        for offset in range(jacobian.indptr[column], jacobian.indptr[column + 1]):
            stored[(jacobian.row_ids[jacobian.indices[offset]], column_id)] = float(
                jacobian.data[offset]
            )

    checked: set[tuple[str, str]] = set()
    for row, column, value in entry["jacobian"]:
        key = (row, column)
        checked.add(key)
        got = stored.get(key, 0.0)
        scale = abs(Decimal(value))
        ratio = float(abs(Decimal(got) - Decimal(value)) / scale) / JACOBIAN_RELATIVE
        if ratio > comparison.worst_jacobian_ratio:
            comparison.worst_jacobian_ratio, comparison.worst_entry = ratio, f"{row} / {column}"
        if ratio > 1.0:
            failures.append(f"d({row})/d({column}) = {got!r}, registered {value}")
    for row, column, partial_scale in entry["cancelling_partials"]:
        key = (row, column)
        checked.add(key)
        got = stored.get(key, 0.0)
        ratio = abs(got) / (JACOBIAN_RELATIVE * float(partial_scale))
        if ratio > comparison.worst_jacobian_ratio:
            comparison.worst_jacobian_ratio = ratio
            comparison.worst_entry = f"{row} / {column} (cancelling)"
        if ratio > 1.0:
            failures.append(
                f"cancelling d({row})/d({column}) = {got!r}, allowed "
                f"{JACOBIAN_RELATIVE} x {partial_scale}"
            )
    for key, got in stored.items():
        if key not in checked and got != 0.0:
            failures.append(f"d({key[0]})/d({key[1]}) = {got!r}, registered exactly 0.0")
    return comparison
