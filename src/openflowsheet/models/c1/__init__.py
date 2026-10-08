"""The C1 unit models: the ammonia synthesis loop on `pr-c1-v1` (M01 spec §8, ADR 0027).

M01 implements the reactor boundary (`boundary.py`: the mapping onto the group's per-tube reactor,
the outlet's extent projection, the zero-pressure-drop convention, the process-side duty, the
result envelope and its refusal codes) and a synthetic stand-in reactor
(`reactor_standin.py`, `c1.reactor_standin`) that exercises every boundary path in the in-repo
gate without PyMRM. The out-of-process adapter to the pinned reactor and the PR flash, heater,
mixer and splitter units are M02's (spec §8.14).
"""

from __future__ import annotations

from typing import Final

from openflowsheet.thermo.pr_c1 import COMPONENTS, PROVIDER_ID, REFERENCE_CONVENTION

__all__ = [
    "COMPONENTS",
    "ELEMENTS",
    "ELEMENT_MATRIX",
    "NU",
    "PROVIDER_ID",
    "REFERENCE_CONVENTION",
]

#: N2 + 3 H2 -> 2 NH3 over (H2, N2, NH3, Ar, CH4) (spec §8.2).
NU: Final[tuple[int, ...]] = (-3, -1, 2, 0, 0)

#: The element balance rows over (H2, N2, NH3, Ar, CH4) (spec §8.9): E ν = 0 for every element.
ELEMENTS: Final[tuple[str, ...]] = ("Ar", "C", "H", "N")
ELEMENT_MATRIX: Final[tuple[tuple[int, ...], ...]] = (
    (0, 0, 0, 1, 0),
    (0, 0, 0, 0, 1),
    (2, 0, 3, 0, 4),
    (0, 2, 1, 0, 0),
)

#: Dimension vectors in the `Quantity` schema's base order (as `models.syn001`'s).
MOLAR_FLOW: Final = (0, 0, -1, 0, 1, 0, 0)
MOLE: Final = (0, 0, 0, 0, 1, 0, 0)
TEMPERATURE: Final = (0, 0, 0, 1, 0, 0, 0)
PRESSURE: Final = (-1, 1, -2, 0, 0, 0, 0)
POWER: Final = (2, 1, -3, 0, 0, 0, 0)
ENERGY: Final = (2, 1, -2, 0, 0, 0, 0)
