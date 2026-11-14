"""The projection's shared vocabulary: its refusal codes and error, the omitted-row record and
the row derivatives both of its checks read (M05 design note §6.1, R-274).
`studies.trust_region.projection` re-exports every public name."""

from __future__ import annotations

from collections.abc import Collection, Mapping
from dataclasses import dataclass
from typing import Any, Final, Literal

import numpy as np
import numpy.typing as npt

from openflowsheet.compile.reference import FloatAlgebra
from openflowsheet.compile.spec import ProblemSpec
from openflowsheet.orchestrator.rank import EliminatedRow
from openflowsheet.studies.sensitivity import TAU_ALIAS

#: R-274: why an omitted row is not projected, as the source map records it.
OMITTED_ROW_REASON: Final = (
    "eliminated by orchestrator/rank.py's alias elimination: implied by the retained rows (R-274)"
)


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


# -- the omitted rows (R-274) ---------------------------------------------------------------------


@dataclass(frozen=True)
class _RowDerivatives:
    """Every row's derivatives at x₀, in spec order: `x`, the total x-Jacobian — through the block
    outputs, so it is the Jacobian of the function the compiled problem holds — and `d`, the
    decision columns (per unit of the scaled decision)."""

    x: npt.NDArray[np.float64]
    d: npt.NDArray[np.float64]


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
