"""The saturated pure-fluid stream in the causal traversal, and its carried split (ADR 0051 D2).

A saturated stream is `nTP-v1` plus a carried split: (n, T, P) alone does not determine V and L on
the saturation line (ADR 0012 D7). In the EO the producer authors the columns `<S>.sat.V` and
`<S>.sat.L`; in the causal traversal the stream travels as `SaturatedStreamState`, a `StreamState`
subclass with the vapour fraction. The class lives in the models layer and is never passed to a
provider: the kernel takes floats (units design §2.4, §4.1).
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field

from openflowsheet.models import UnitEvaluation
from openflowsheet.models.thermal.kernel import Failure
from openflowsheet.thermo import StreamState

__all__ = [
    "SaturatedStreamState",
    "ThermalEvaluation",
    "carried_fraction",
    "liquid_id",
    "saturated_owned",
    "vapor_id",
]


@dataclass(frozen=True)
class SaturatedStreamState(StreamState):
    """A stream on the saturation line: `temperature` is the kernel's T_sat(P), bit for bit."""

    #: beta = V/n; finite, 0 <= beta <= 1; 0.0 for a dormant stream (a label).
    vapor_fraction: float

    def __post_init__(self) -> None:
        beta = self.vapor_fraction
        if not (math.isfinite(beta) and 0.0 <= beta <= 1.0):
            raise ValueError(f"vapor_fraction {beta!r} is not a finite number in [0, 1]")


def vapor_id(stream: str) -> str:
    """The carried vapour flow of a saturated stream, mol/s (§4.1)."""
    return f"{stream}.sat.V"


def liquid_id(stream: str) -> str:
    """The carried liquid flow of a saturated stream, mol/s (§4.1)."""
    return f"{stream}.sat.L"


def saturated_owned(stream: str, total: float, beta: float) -> dict[str, float]:
    """`{<S>.sat.V: beta n, <S>.sat.L: n - beta n}`, computed in that order, so that `sat-split`
    holds exactly at the EO start (§4.1)."""
    vapour = beta * total
    return {vapor_id(stream): vapour, liquid_id(stream): total - vapour}


def carried_fraction(state: StreamState, stream: str) -> float | Failure:
    """The beta a thermal reader of a `vapor_liquid` inlet reads (§4.1).

    A `SaturatedStreamState` gives its own; a dormant plain `StreamState` (a torn guess) reads as
    beta = 0; anything else is the defect `carried_split_missing(<S>)`.
    """
    if isinstance(state, SaturatedStreamState):
        return state.vapor_fraction
    if state.is_dormant:
        return 0.0
    return Failure(
        "error",
        f"carried_split_missing({stream})",
        f"{stream} is declared vapor_liquid but arrived without its carried split",
    )


if "owned" in UnitEvaluation.__dataclass_fields__:
    ThermalEvaluation = UnitEvaluation
else:  # pragma: no cover - removed when WO-B2's `UnitEvaluation.owned` reaches this branch

    @dataclass(frozen=True)
    class ThermalEvaluation(UnitEvaluation):  # type: ignore[no-redef]
        """`UnitEvaluation` with WO-B2's `owned` (S11 design §4.7.5), until B2 merges.

        Track C is built on `wp/S11` before track B's B2 lands; `models/__init__.py` is track B's
        file, so the field is bridged here with B2's exact semantics (a failed evaluation owns
        nothing) and the bridge disappears once the base class has it (S11C_DECISIONS C1-1).
        """

        owned: Mapping[str, float] = field(default_factory=dict)

        def __post_init__(self) -> None:
            super().__post_init__()
            if self.status != "ok" and self.owned:
                raise ValueError(
                    f"status {self.status!r} carries owned values; a failed evaluation reports "
                    "what went wrong and nothing a caller could mistake for an answer"
                )
