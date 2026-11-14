"""The verifier's registered row tolerances by declared quantity kind (K04 §5.1, §5.2).

A leaf: `checks` and `saturation` both read them, and `checks` re-exports every name. They are the
verifier's own objects (R-016), not the solver's `KIND_TOLERANCE`.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

from openflowsheet.models.syn001 import (
    ENERGY_TOLERANCE,
    FLOW_TOLERANCE,
    TEMPERATURE_TOLERANCE,
)

#: §5.1, from ADR 0001 D6. Pressure and the lifted equilibrium row are the two the K03 work
#: left implicit; §5.2 derives the equilibrium row's from the flow rule at the flow scale.
PRESSURE_TOLERANCE: Final = 1e-2
#: §5.2: `a = 1e-9 x 3`, `r s = 1e-8 x 9`. Dividing the row by the flow scale gives a flow.
EQUILIBRIUM_TOLERANCE: Final = 1e-9 * 3.0 + 1e-8 * 9.0

#: §5.1's mapping from a declared quantity kind to its registered tolerance.
KIND_TOLERANCE: Final[Mapping[str, float]] = {
    "molar_flow": FLOW_TOLERANCE,
    "molar_flow_squared": EQUILIBRIUM_TOLERANCE,
    "heat_rate": ENERGY_TOLERANCE,
    "temperature": TEMPERATURE_TOLERANCE,
    "pressure": PRESSURE_TOLERANCE,
}
