"""Provider-level state types (ADR 0062 D2): what one substream is at the provider boundary.

`StreamState` is the `nTP-v1` stream K02 introduced in `openflowsheet.thermo`; it lives here, below
`thermo`, so that the provider contract (`thermo`) can re-export the state types of the material
model without an import cycle, and `openflowsheet.thermo.StreamState` is the same class.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["StreamState"]


@dataclass(frozen=True)
class StreamState:
    """A material stream in the `nTP-v1` state definition (ADR 0001 D2.1).

    `n` is component molar flows in `components` order, mol/s; `T` is absolute temperature in K;
    `P` is pressure in Pa. Nothing derived is stored: total flow, mole fractions, mass flow and
    enthalpy flow are computed, and mole fractions only where the total flow is positive
    (D2.2, D3.2).
    """

    n: tuple[float, ...]
    temperature: float
    pressure: float

    @property
    def total_flow(self) -> float:
        return sum(self.n)

    @property
    def is_dormant(self) -> bool:
        """Exact IEEE zero after signed-zero normalization (ADR 0001 D3.1).

        Exact, not "small": a stream with 1e-30 mol/s of everything has a defined composition and a
        dormant one does not, and a tolerance here would silently move the boundary between them.
        """
        return self.total_flow == 0.0
