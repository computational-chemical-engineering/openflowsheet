"""Provider-level state types (ADR 0062 D2): what one substream is at the provider boundary.

`StreamState` is the `nTP-v1` stream K02 introduced in `openflowsheet.thermo`; it lives here, below
`thermo`, so that the provider contract (`thermo`) can re-export the state types of the material
model without an import cycle, and `openflowsheet.thermo.StreamState` is the same class (F2
decision WO1-3).

`EvaluationState` is one substream of any connection definition as a provider sees it: parent
amounts in the provider's own basis, T, P, and the attribute values the provider declared it reads.
`from_stream_state` copies the three references and does no arithmetic, so the round trip through
`to_stream_state` is bitwise by construction (E-F2-1 proves it over the corpus).
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["Attributes", "EvaluationState", "StreamState"]


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


#: `(attribute key, values)` pairs, sorted by the UTF-8 bytes of the key, each key once. A key is
#: `<kind id>` (substream scope) or `<kind id>[<component>]` (ADR 0062 D2).
type Attributes = tuple[tuple[str, tuple[float, ...]], ...]


@dataclass(frozen=True, slots=True)
class EvaluationState:
    """One substream at the provider level (ADR 0062 D2).

    `n` is the parent amount per component of the provider's `components`, in each component's own
    basis; `temperature` in K; `pressure` in Pa. A partition attribute's parent is formed by the
    material model before `n` is (Q6.R2): a provider sees classes only through `attributes`, and
    only those it declared it reads.
    """

    n: tuple[float, ...]
    temperature: float
    pressure: float
    attributes: Attributes = ()

    def __post_init__(self) -> None:
        keys = [key.encode("utf-8") for key, _ in self.attributes]
        if any(later <= earlier for earlier, later in zip(keys, keys[1:], strict=False)):
            raise ValueError("attribute keys must be strictly increasing by their UTF-8 bytes")

    @classmethod
    def from_stream_state(cls, s: StreamState) -> EvaluationState:
        """The `nTP-v1` stream as an evaluation state: the three references, no arithmetic."""
        return cls(s.n, s.temperature, s.pressure)

    def to_stream_state(self) -> StreamState:
        """The `nTP-v1` stream this state is; `ValueError` if it carries attributes, which a
        `StreamState` cannot hold."""
        if self.attributes:
            raise ValueError("an evaluation state with attributes has no StreamState")
        return StreamState(self.n, self.temperature, self.pressure)
