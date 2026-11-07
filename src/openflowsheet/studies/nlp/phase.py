"""Held-regime phase admissibility rows (OPT design §4.7, WO-5; ADR 0071 D7).

At a start's certified point, every held phase regime that a row can hold gets one `a ≥ 0`, built
as a functional program (E01 D2: `RowBuilder`s against `Algebra`, one `ProblemSpec` over the
host's variables, compiled through the unchanged `ParametricTwin`; never solved, never
certified):

- lifted split LIQUID (TP or PH type): `Σᵢ nᵢ − Σᵢ nᵢ·exp(lnKᵢ)` over the split's feed flows at
  its T, P (`phase.<unit>.bubble`; molar_flow);
- lifted split VAPOR: `Σᵢ nᵢ − Σᵢ nᵢ·exp(−lnKᵢ)` (`phase.<unit>.dew`; molar_flow);
- lifted split TWO_PHASE, ZERO_FLOW, dormancy items: none (held by `V, L ≥ 0`; V4's exact
  dormancy check);
- thermal port declared liquid / vapour: `T_sat(P) − T` / `T − T_sat(P)` (`phase.<stream>.
  subcooled` / `.superheated`; temperature, nominal 1 K);
- thermal port declared wet: none (held by its `sat.V, sat.L ≥ 0`).

`lnK` is the block the split's equilibrium rows read — the same `LnKBlock` instance of the host's
spec, fed by the split's `(T, P)`, so the row has the same derivative path. `T_sat(P)` is the
thermal kernel's saturated block (`SaturatedFlowBlock`, the block `sat-T` reads) restricted to its
`Tsat` output. Each row is divided by its K03 nominal, so the gray box's scale is 1 (as E01's
admissibility rows, §4.3.1). A held LIQUID/VAPOR split whose provider's closure judges it by
another test (OPT_DECISIONS D-12: no margin), or whose K-block is composition-dependent, and a
declared port whose `T_sat` is not defined at the start, have no row: `undefined` names them, and
the start fails `REGIME_MARGIN_UNDEFINED(<unit>)`.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Final, Literal

import numpy as np
import numpy.typing as npt

from openflowsheet.compile.casadi_backend import (
    ParametricTwin,
    TwinEvaluationError,
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
    RowBuilder,
)
from openflowsheet.compiled import EvaluationContext
from openflowsheet.models.syn001.blocks import LnKBlock
from openflowsheet.models.thermal.blocks import PhaseFlowBlock, SaturatedFlowBlock
from openflowsheet.numerics.scaling import REGISTERED_NOMINALS
from openflowsheet.studies.sensitivity import SplitRegime
from openflowsheet.thermo import PropertyProvider

#: The Pyomo component that holds the rows (OPT §4.4's second output block).
PHASE_COMPONENT: Final = "phase_admissibility"
#: The functional program's label (ADR 0002 D2.7: each row id names its expression's form).
PHASE_LABEL: Final = "OPT-PHASE-ROWS"
#: The prefix a row's value carries in V3/V5's augmented state (as `assessment:` does).
PHASE_PREFIX: Final = "phase:"
#: §4.7: a declared port's row is a temperature with nominal 1 K.
PORT_NOMINAL: Final = 1.0

RowKind = Literal["split_liquid", "split_vapor", "port_liquid", "port_vapor"]


@dataclass(frozen=True)
class PhaseRow:
    """One row: its id, the unit (a lifted split's) or stream (a declared port's) it holds, its
    kind and its nominal (the row is `a/nominal`)."""

    row_id: str
    unit: str
    kind: RowKind
    nominal: float

    @property
    def split(self) -> bool:
        return self.kind.startswith("split_")

    def as_document(self) -> dict[str, Any]:
        return {"id": self.row_id, "unit": self.unit, "kind": self.kind, "nominal": self.nominal}


@dataclass
class PhaseRows:
    """A start's phase rows (§4.7) over the host spec's variables, and the held regimes no row
    can hold (`undefined`, by unit or stream, in discovery order)."""

    rows: tuple[PhaseRow, ...]
    undefined: tuple[str, ...]
    spec: ProblemSpec | None
    _twins: dict[tuple[str, ...], ParametricTwin] = field(default_factory=dict, repr=False)

    @property
    def ids(self) -> tuple[str, ...]:
        return tuple(row.row_id for row in self.rows)

    @property
    def nominals(self) -> Mapping[str, float]:
        return MappingProxyType({row.row_id: row.nominal for row in self.rows})

    def row(self, row_id: str) -> PhaseRow:
        return next(row for row in self.rows if row.row_id == row_id)

    def twin(self, decision_ids: Sequence[str]) -> ParametricTwin:
        """The rows' twin with the decisions symbolic (the gray box's path), once per ids."""
        if self.spec is None:
            raise ValueError("no phase rows to compile")
        key = tuple(decision_ids)
        if key not in self._twins:
            self._twins[key] = compile_parametric_twin(self.spec, key)
        return self._twins[key]

    def values(self, state: Mapping[str, float]) -> dict[str, float]:
        """The rows at `state` on the float reference path (V3, V6's path); a domain failure is
        a `TwinEvaluationError`."""
        if self.spec is None:
            return {}
        try:
            values = row_values(self.spec, state)
        except (DomainError, ValueError, ZeroDivisionError, OverflowError) as error:
            raise TwinEvaluationError(f"{type(error).__name__}: {error}") from error
        bad = [name for name, value in values.items() if not math.isfinite(value)]
        if bad:
            raise TwinEvaluationError(f"non-finite phase rows {bad}")
        return values

    def linearize(
        self, x: npt.NDArray[np.float64], decisions: Mapping[str, float]
    ) -> tuple[dict[str, dict[str, float]], dict[str, npt.NDArray[np.float64]]]:
        """`∂a/∂x` by row as `{variable_id: value}` and `∂a/∂d` by row in decision order, from
        the twin at `(x, d)` (V5's chain rule)."""
        assert self.spec is not None
        twin = self.twin(tuple(decisions))
        state = twin.jacobian_x(x, decisions)
        d_dx: dict[str, dict[str, float]] = {row: {} for row in self.ids}
        for j, variable_id in enumerate(state.col_ids):
            for k in range(state.indptr[j], state.indptr[j + 1]):
                d_dx[state.row_ids[state.indices[k]]][variable_id] = float(state.data[k])
        parameter = twin.jacobian_p(x, decisions)
        d_dd: dict[str, npt.NDArray[np.float64]] = {
            row: np.zeros(len(decisions), dtype=np.float64) for row in self.ids
        }
        for j in range(len(parameter.col_ids)):
            for k in range(parameter.indptr[j], parameter.indptr[j + 1]):
                d_dd[parameter.row_ids[parameter.indices[k]]][j] = float(parameter.data[k])
        return d_dx, d_dd


class PortSaturationBlock:
    """`P -> T_sat(P)`: the thermal kernel's `SaturatedFlowBlock` restricted to its `Tsat`
    output (whose only structural input is P), for a port that declares one phase and so carries
    no saturated block of its own (OPT_DECISIONS F4)."""

    def __init__(
        self, provider: PropertyProvider, component: str, context: EvaluationContext, block_id: str
    ) -> None:
        self._saturated = SaturatedFlowBlock(provider, component, context, block_id=block_id)
        self._block_id = block_id

    @property
    def block_id(self) -> str:
        return self._block_id

    @property
    def input_ids(self) -> tuple[str, ...]:
        return ("P",)

    @property
    def output_ids(self) -> tuple[str, ...]:
        return ("Tsat",)

    def jacobian_pattern(self) -> tuple[tuple[int, int], ...]:
        return ((0, 0),)

    def values(self, inputs: Sequence[float]) -> Sequence[float]:
        (pressure,) = inputs
        return [self._saturated.values([0.0, 0.0, float(pressure)])[0]]

    def jacobian(self, inputs: Sequence[float]) -> Sequence[tuple[int, int, float]]:
        (pressure,) = inputs
        entries = self._saturated.jacobian([0.0, 0.0, float(pressure)])
        return [(0, 0, value) for row, column, value in entries if (row, column) == (0, 2)]


def _split_row(
    feed: tuple[str, ...], keys: tuple[str, ...], sign: float, nominal: float
) -> RowBuilder:
    """`(Σ n − Σ n·exp(sign·lnK)) / nominal`: the bubble (sign +1) or dew (−1) test times the
    feed total, defined at any flow, no division by a flow."""

    def build(
        variables: Mapping[str, Expr],
        blocks: Mapping[str, Expr],
        parameters: Mapping[str, float],
        algebra: Algebra,
    ) -> Expr:
        total = variables[feed[0]]
        weighted = variables[feed[0]] * algebra.exp(sign * blocks[keys[0]])
        for name, key in zip(feed[1:], keys[1:], strict=True):
            total = total + variables[name]
            weighted = weighted + variables[name] * algebra.exp(sign * blocks[key])
        return (total - weighted) / nominal

    return build


def _port_row(temperature: str, key: str, sign: float, nominal: float) -> RowBuilder:
    """`sign·(T_sat(P) − T) / nominal`: liquid `+1` (subcooled), vapour `−1` (superheated)."""

    def build(
        variables: Mapping[str, Expr],
        blocks: Mapping[str, Expr],
        parameters: Mapping[str, float],
        algebra: Algebra,
    ) -> Expr:
        return sign * (blocks[key] - variables[temperature]) / nominal

    return build


def phase_rows(
    spec: ProblemSpec,
    state: Mapping[str, float],
    splits: Sequence[tuple[SplitRegime, tuple[str, ...], str, str]],
    provider: PropertyProvider,
    components: Sequence[str],
    context: EvaluationContext,
) -> PhaseRows:
    """§4.7's rows at a start: `splits` are each lifted split's regime record with its feed flow
    ids, temperature and pressure ids; the declared ports are the spec's `PhaseFlowBlock`s."""
    equations: list[EquationSpec] = []
    blocks: dict[str, tuple[PropertyBlock, tuple[str, ...]]] = {}
    rows: list[PhaseRow] = []
    undefined: list[str] = []
    flow_nominal = float(REGISTERED_NOMINALS["molar_flow"])
    for record, feed, temperature, pressure in splits:
        if record.regime not in ("LIQUID", "VAPOR"):
            continue
        block = next(
            (
                candidate
                for candidate in spec.blocks
                if isinstance(candidate, LnKBlock)
                and tuple(spec.block_inputs[candidate.block_id]) == (temperature, pressure)
            ),
            None,
        )
        if record.margin is None or block is None:
            undefined.append(record.unit_id)
            continue
        # The feed flows are in component order (as `tp_margin` reads them).
        if len(feed) != len(components):
            raise ValueError(
                f"{record.unit_id}: {len(feed)} feed flows, {len(components)} components"
            )
        keys = tuple(f"{block.block_id}.lnK_{name}" for name in components)
        blocks.setdefault(block.block_id, (block, (temperature, pressure)))
        liquid = record.regime == "LIQUID"
        row = PhaseRow(
            f"phase.{record.unit_id}.{'bubble' if liquid else 'dew'}",
            record.unit_id,
            "split_liquid" if liquid else "split_vapor",
            flow_nominal,
        )
        rows.append(row)
        equations.append(
            EquationSpec(
                row.row_id,
                _split_row(feed, keys, 1.0 if liquid else -1.0, flow_nominal),
                "algebraic",
                origin=f"OPT §4.7 {row.kind}",
            )
        )
    ports = [
        block
        for block in spec.blocks
        if isinstance(block, PhaseFlowBlock)
        and block.block_id.rsplit("_", 1)[-1] in ("liquid", "vapor")
    ]
    for port in ports:
        _, temperature, pressure = spec.block_inputs[port.block_id]
        stream = temperature.removesuffix(".T")
        liquid = port.block_id.endswith("_liquid")
        saturation = PortSaturationBlock(
            provider, components[0], context, block_id=f"PFtsat_{port.block_id[3:]}"
        )
        try:
            saturation.values([float(state[pressure])])
        except DomainError:
            undefined.append(stream)
            continue
        blocks.setdefault(saturation.block_id, (saturation, (pressure,)))
        row = PhaseRow(
            f"phase.{stream}.{'subcooled' if liquid else 'superheated'}",
            stream,
            "port_liquid" if liquid else "port_vapor",
            PORT_NOMINAL,
        )
        rows.append(row)
        equations.append(
            EquationSpec(
                row.row_id,
                _port_row(
                    temperature,
                    f"{saturation.block_id}.Tsat",
                    1.0 if liquid else -1.0,
                    PORT_NOMINAL,
                ),
                "algebraic",
                origin=f"OPT §4.7 {row.kind}",
            )
        )
    if not equations:
        return PhaseRows((), tuple(undefined), None)
    functional = ProblemSpec(
        label=PHASE_LABEL,
        variable_ids=spec.variable_ids,
        equations=tuple(equations),
        parameter_ids=spec.parameter_ids,
        parameters=spec.parameters,
        blocks=tuple(block for block, _ in blocks.values()),
        block_inputs={block_id: inputs for block_id, (_, inputs) in blocks.items()},
    )
    functional.validate()
    return PhaseRows(tuple(rows), tuple(undefined), functional)
