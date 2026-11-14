"""The region solver's registered row tolerances by declared kind (ADR 0001 D6; K04 §5.2).

The solver's own objects, separate from the verifier's `verify.kind_tolerance` (R-016): the region
solver, the rank elimination and the units that judge their rows read them, and
`orchestrator.region` and `orchestrator.rank` re-export them. The verifier may not import this
module (`verifier-not-through-the-solver`).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

from openflowsheet.models.syn001 import (
    ENERGY_TOLERANCE,
    FLOW_TOLERANCE,
    TEMPERATURE_TOLERANCE,
)

#: ADR 0001 D6's registered pressure tolerance: the bound on a consistent mismatch.
PRESSURE_TOLERANCE: Final = 1e-2

#: K04 §5.2's registered tolerance for the division-free equilibrium row, `a + r s` with
#: `a = 1e-9 · 3`, `r = 1e-8`, `s = 9 (mol/s)²`. Restated here, not imported from the verifier's
#: `verify.kind_tolerance`, because the solver and the verifier share no tolerance object (R-016);
#: `tests/test_t02_region.py` pins the two equal so they cannot drift.
EQUILIBRIUM_TOLERANCE: Final = 1e-9 * 3.0 + 1e-8 * 9.0

#: The row acceptance rule by declared kind (ADR 0001 D6; K04 §5.2), K03 §5.2's per-row test.
KIND_TOLERANCE: Final[Mapping[str, float]] = {
    "molar_flow": FLOW_TOLERANCE,
    "molar_flow_squared": EQUILIBRIUM_TOLERANCE,
    "heat_rate": ENERGY_TOLERANCE,
    "temperature": TEMPERATURE_TOLERANCE,
    "pressure": PRESSURE_TOLERANCE,
}
