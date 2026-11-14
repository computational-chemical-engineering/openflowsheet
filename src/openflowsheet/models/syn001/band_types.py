"""The saturation band's value types: search budget, position of `T(β)`, answer and error.

A leaf: `saturation_band` (the band search) and `gamma_phi` (the composition-dependent band
point) both produce them, and `saturation_band` re-exports every name.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

from openflowsheet.thermo import PropertyStatus

#: Spec §5.2: at most this many evaluations of `g` per `T(β)`, the two ends included; T05 §4.4
#: step 4's budget. Bisection on the SYN-001 domain reaches adjacent doubles in about 50.
MAX_TEMPERATURE_EVALUATIONS: Final = 200

Position = Literal["inside", "below", "above"]


class BandError(Exception):
    """A provider refusal inside a band search, or an exhausted bisection (`not_converged`)."""

    def __init__(self, status: PropertyStatus, message: str) -> None:
        super().__init__(message)
        self.status: PropertyStatus = status
        self.message = message


@dataclass(frozen=True)
class BandTemperature:
    """`T(β)`, or where it lies when it is outside the domain.

    `inside`: `temperature` is the bisection's answer and `k_values` the provider's `K_i` there
    (one per declared component, in the provider's order); `below` / `above`: no temperature.
    For a composition-dependent form (`gamma_phi.band_point`, S10-C §4.3) an `inside` point also
    carries its liquid composition `liquid`; SYN-001's K needs none, and leaves it empty.
    """

    position: Position
    temperature: float | None = None
    k_values: tuple[float, ...] = ()
    #: Evaluations of `g` spent, the two domain ends included.
    evaluations: int = 0
    #: The liquid composition `x` at `T(β)`, composition-dependent forms only (S10-C §4.3).
    liquid: tuple[float, ...] = ()
