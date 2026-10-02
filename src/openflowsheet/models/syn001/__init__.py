"""The six SYN-001 unit models, implementing the manifests P01 declared.

One module per model, named after the manifest id: `syn001.feed_source` is in `feed.py`,
`syn001.tp_heater` in `heater.py`, and so on. Introduced by package K02.

**The equations are not this package's to choose.** `docs/derivations/SYN-001.md` §4 states them,
ADR 0008 D3.5 fixes every row's accumulation kind in a normative table, and the six manifests in
`tests/fixtures/schemas/model_manifest/valid/` fix the ports, the statements, the dependencies,
the domain and the limitations. Each model here re-states its declaration in Python and
`tests/test_k02_unit_models.py` compares the two transcriptions: a divergence is a test failure,
not a discrepancy for a later reader to find.

**Nothing here sets a scale.** ADR 0001 D3.5 gives scale construction to K03 — "variable scales
are never derived from a current value that may be zero" — so a `Contribution` leaves
`column_scales` and `row_scales` empty rather than guessing them one unit at a time.
"""

from __future__ import annotations

from typing import Final

#: The SYN-001 component set, in the order every manifest and the provider declare.
COMPONENTS: Final[tuple[str, ...]] = ("A", "B", "C")

#: The declared test domain (plan §3.1). Repeated in every manifest's `validity.domain`.
T_MIN: Final = 280.0
T_MAX: Final = 440.0
P_MIN: Final = 50_000.0
P_MAX: Final = 200_000.0

PROVIDER_ID: Final = "syn001"
REFERENCE_CONVENTION: Final = "SYN-001-ref-v1"

DERIVATION: Final = "docs/derivations/SYN-001.md §4"

#: ADR 0001 D6's tolerances, registered for SYN-001 and applied to nothing else. Written as the
#: sums the ADR states so the arithmetic is visible: the energy tolerance is 1.01e-3 W, not
#: 1.001e-3, because 1e-8 x 1e5 is 1e-3.
TEMPERATURE_TOLERANCE: Final = 1e-6
ENERGY_TOLERANCE: Final = 1e-5 + 1e-8 * 1e5
FLOW_TOLERANCE: Final = 1e-9 + 1e-8 * 3.0

#: Dimension vectors in the `Quantity` schema's base order. Named because a transposed exponent
#: vector is invisible at a glance and these four are used in every manifest.
MOLAR_FLOW: Final = (0, 0, -1, 0, 1, 0, 0)
MOLE: Final = (0, 0, 0, 0, 1, 0, 0)
TEMPERATURE: Final = (0, 0, 0, 1, 0, 0, 0)
PRESSURE: Final = (-1, 1, -2, 0, 0, 0, 0)
POWER: Final = (2, 1, -3, 0, 0, 0, 0)
ENERGY: Final = (2, 1, -2, 0, 0, 0, 0)
