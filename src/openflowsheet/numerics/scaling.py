"""Variable and residual scales, from the registered physical nominals.

K03 specification §4. `x = x_ref + S_x x̂` with **`x_ref = 0` for every variable**, `F̂ = S_F⁻¹ F`,
`Ĵ = S_F⁻¹ J S_x` (blueprint §7.3).

**Scales come from registered nominals and never from an iterate.** ADR 0001 D3.5 is explicit:
"variable scales are never derived from a current value that may be zero", and SYN-001 has a
tear vector that is exactly zero at r = 0. So a scale is assigned by the *declared quantity kind*
of a variable or a row, and the nominals are derivation §9's: 3 mol/s of component flow, 100 K,
1e5 Pa, 1e5 W.

**A kind the nominals do not name is a refusal, not a 1.0.** An unscaled pressure column against
a flow row gives a condition number around 1e10 where the scaled block gives a few hundred, so a
silent default would hide exactly the failure scaling exists to prevent. Plan construction raises
`ScaleUnavailableError` naming the id (specification §4.3, assertion A32).

**Scales are frozen within an attempt** (D06, blueprint §7.3). A refresh would open a recorded
segment; K03 v0.0 never refreshes, so `segment` exists, is always 0, and is asserted to be
(A34). The counter is here rather than added later because a segment number that appears
retroactively cannot be read back into traces already written.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Final

import numpy as np
import numpy.typing as npt

from openflowsheet.compile.spec import ProblemSpec, QuantityKind

#: Anything the scaling helpers accept as a vector of doubles. They are called with plain lists
#: (from a test or a registry) and with arrays (from the Newton core), and converting once at the
#: boundary keeps the conversion in one place.
Vector = Sequence[float] | npt.NDArray[np.float64]

#: Derivation §9, `benchmarks/registry.yaml` `scales`. The squared entry is the equilibrium row
#: `v_i L - K_i l_i V`, a product of two flows, so its scale is the square of the flow nominal.
REGISTERED_NOMINALS: Final[Mapping[QuantityKind, float]] = {
    "molar_flow": 3.0,
    "molar_flow_squared": 9.0,
    "temperature": 100.0,
    "pressure": 1.0e5,
    "heat_rate": 1.0e5,
}

SCALE_PROVENANCE: Final = (
    "docs/derivations/SYN-001.md §9 (registered physical nominals; benchmarks/registry.yaml "
    "`scales`), assigned by declared quantity kind"
)


class ScaleUnavailableError(ValueError):
    """A variable or row has no declared kind, or a kind with no registered nominal.

    Raised when the plan is built, before anything is initialized or solved, because a scale that
    cannot be justified is not a scale. The message names every offending id.
    """


@dataclass(frozen=True)
class Scaling:
    """`S_x` and `S_F`, by id, with the provenance that justifies them.

    Both mappings are complete for the problem they were built for: every variable and every row
    has an entry, or construction failed. Lookups therefore never default.
    """

    column: Mapping[str, float]
    row: Mapping[str, float]
    provenance: str = SCALE_PROVENANCE
    #: Blueprint §7.3's recorded scale segment. Always 0 in v0.0; a refresh would increment it.
    segment: int = 0
    kinds: Mapping[str, QuantityKind] = field(default_factory=dict)

    def __post_init__(self) -> None:
        bad = sorted(
            name for name, value in (*self.column.items(), *self.row.items()) if not value > 0.0
        )
        if bad:
            raise ScaleUnavailableError(
                f"a scale divides, so a zero or negative one is a division by zero or a silent "
                f"sign flip, not a scaling: {bad}"
            )

    # -- construction --------------------------------------------------------------------------

    @classmethod
    def from_spec(cls, spec: ProblemSpec) -> Scaling:
        """Build from the kinds the units declared on the spec."""
        return cls.from_kinds(
            variable_ids=spec.variable_ids,
            equation_ids=spec.equation_ids,
            variable_kinds=spec.variable_kinds,
            row_kinds=spec.row_kinds,
        )

    @classmethod
    def from_kinds(
        cls,
        *,
        variable_ids: Sequence[str],
        equation_ids: Sequence[str],
        variable_kinds: Mapping[str, QuantityKind],
        row_kinds: Mapping[str, QuantityKind],
        nominals: Mapping[QuantityKind, float] = REGISTERED_NOMINALS,
        provenance: str = SCALE_PROVENANCE,
    ) -> Scaling:
        undeclared: list[str] = []
        unnominated: list[str] = []
        column: dict[str, float] = {}
        row: dict[str, float] = {}
        kinds: dict[str, QuantityKind] = {}

        for ids, declared, target in (
            (variable_ids, variable_kinds, column),
            (equation_ids, row_kinds, row),
        ):
            for name in ids:
                kind = declared.get(name)
                if kind is None:
                    undeclared.append(name)
                    continue
                nominal = nominals.get(kind)
                if nominal is None:
                    unnominated.append(f"{name} ({kind})")
                    continue
                target[name] = float(nominal)
                kinds[name] = kind

        if undeclared or unnominated:
            parts = []
            if undeclared:
                parts.append(f"no declared quantity kind: {sorted(undeclared)}")
            if unnominated:
                parts.append(f"no registered nominal for the declared kind: {sorted(unnominated)}")
            raise ScaleUnavailableError(
                "SCALE_UNAVAILABLE. "
                + "; ".join(parts)
                + ". A silent 1.0 is forbidden: an unscaled pressure column against a flow row "
                "gives a condition number around 1e10 where the scaled block gives a few hundred"
            )
        return cls(column=column, row=row, provenance=provenance, kinds=kinds)

    # -- application ---------------------------------------------------------------------------

    def column_vector(self, variable_ids: Sequence[str]) -> npt.NDArray[np.float64]:
        return np.array([self.column[name] for name in variable_ids], dtype=np.float64)

    def row_vector(self, equation_ids: Sequence[str]) -> npt.NDArray[np.float64]:
        return np.array([self.row[name] for name in equation_ids], dtype=np.float64)

    def scale_residual(
        self, values: Vector, equation_ids: Sequence[str]
    ) -> npt.NDArray[np.float64]:
        """`F̂ = S_F⁻¹ F`."""
        return np.asarray(values, dtype=np.float64) / self.row_vector(equation_ids)

    def scale_state(self, x: Vector, variable_ids: Sequence[str]) -> npt.NDArray[np.float64]:
        """`x̂ = S_x⁻¹ x`, with `x_ref = 0`."""
        return np.asarray(x, dtype=np.float64) / self.column_vector(variable_ids)

    def unscale_state(self, scaled: Vector, variable_ids: Sequence[str]) -> npt.NDArray[np.float64]:
        """`x = S_x x̂`. Also the step transformation: a step is a difference of states."""
        return np.asarray(scaled, dtype=np.float64) * self.column_vector(variable_ids)

    def scale_jacobian_entries(
        self,
        data: Vector,
        row_index: Sequence[int],
        column_index: Sequence[int],
        row_ids: Sequence[str],
        col_ids: Sequence[str],
    ) -> npt.NDArray[np.float64]:
        """`Ĵ_ij = J_ij S_x[j] / S_F[i]`, entry by entry, by *name* and never by position."""
        rows = self.row_vector(row_ids)
        columns = self.column_vector(col_ids)
        entries = np.asarray(data, dtype=np.float64)
        scaled = entries * columns[np.asarray(column_index)] / rows[np.asarray(row_index)]
        return np.asarray(scaled, dtype=np.float64)

    def merit(self, values: Vector, equation_ids: Sequence[str]) -> float:
        """`½‖S_F⁻¹ F‖²`, the specification's merit function (§5)."""
        scaled = self.scale_residual(values, equation_ids)
        return 0.5 * float(np.dot(scaled, scaled))
