"""The `thermal.*` unit family: basis-generic thermal units on the pure-fluid bases (S11, ADR 0051).

S11 units design §4 (R-813…R-821). Seven models — `thermal.heater`, `thermal.valve`,
`thermal.mixer`, `thermal.flash`, `thermal.pump`, `thermal.compressor`, `thermal.turbine` — written
over `iapws95-v1` and `coolprop-heos-v1`, and, for the vapour compressor and turbine only, over
`wilson-ig-v2`.

**Pure-fluid regimes are declared, not discovered** (ADR 0051 D1). A port's form is the stream's
declared `phase_capability`: LIQUID and VAPOR are single-phase; SATURATED (`vapor_liquid`) is a
stream on the saturation line, `nTP-v1` plus a carried split (`<S>.sat.V`, `<S>.sat.L`) that only
a `thermal.*` unit produces (D2-D4). A closure that lands in another regime is refused
`phase_regime_mismatch(<S>)`, naming the declaration to use.

The package is layered: `kernel` (procedural, floats in, typed results out), `blocks` (the
`PropertyBlock`s the rows read), `rows` (the row shapes `models.rows` does not have), `state`
(the causal traversal's saturated stream), and one module per unit.
"""

from __future__ import annotations

from typing import Final, Literal

from openflowsheet.models import SpecificationError
from openflowsheet.thermo import PropertyProvider

__all__ = [
    "ADDITIVE_VAPOUR",
    "FORM_CAPABILITY",
    "Form",
    "PURE",
    "admitted_identity",
]

#: A port's declared form. `SATURATED` is `vapor_liquid` on a pure-fluid basis (ADR 0051 D1).
Form = Literal["LIQUID", "VAPOR", "SATURATED"]

#: The manifest capability that declares each form; also what a mismatch tells the user to declare.
FORM_CAPABILITY: Final[dict[str, str]] = {
    "LIQUID": "liquid",
    "VAPOR": "vapor",
    "SATURATED": "vapor_liquid",
}

#: Providers admitted by identity, `(provider_id, reference_convention)` (units design §4.4).
PURE: Final[frozenset[tuple[str, str]]] = frozenset(
    {("iapws95-v1", "IAPWS95-ref-v1"), ("coolprop-heos-v1", "COOLPROP-DEF-ref-v1")}
)
#: The additive-vapour premise holds by identity only here (§4.3); compressor and turbine only.
ADDITIVE_VAPOUR: Final[frozenset[tuple[str, str]]] = frozenset(
    {("wilson-ig-v2", "WILSON-IG-ref-v1"), ("wilson-ig-v2", "S10-VER-ref-v1")}
)


def admitted_identity(
    provider: PropertyProvider, unit_id: str, model_id: str, *, additive_vapour: bool = False
) -> tuple[str, str]:
    """The provider's `(provider_id, reference_convention)` if the model admits it; otherwise
    `SpecificationError` at construction (§4.4). A pure-fluid identity must also have C = 1."""
    described = provider.describe()
    identity = (described.provider_id, described.reference_convention)
    if identity in PURE:
        if len(described.components) != 1:
            raise SpecificationError(
                f"provider_not_admitted({model_id})\n{unit_id}: {identity} with "
                f"{len(described.components)} components; a pure-fluid basis has one"
            )
        return identity
    if additive_vapour and identity in ADDITIVE_VAPOUR:
        return identity
    raise SpecificationError(
        f"provider_not_admitted({model_id})\n{unit_id}: {model_id} is not admitted on {identity}"
    )
