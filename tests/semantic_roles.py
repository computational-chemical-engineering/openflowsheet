"""V03 Amendment 1 (ADR 0054, R-881): the `semantic_role` of each model the binder accepts.

`ROLE_OF_MODEL` is Table R of the V03 release specification §9.4. Its keys are exactly
`revision_binding.MODEL_SIGNATURES`; its values are the schema's `semantic_role` enum without
`other`. It is a repository convention the test-side builders follow and V03.A30 checks, not a
validation rule: a user document is constrained by the schema alone (ADR 0054 D4), and nothing under
`src/` reads the role (V03.A31).

`role_of` raises `KeyError` for a model without a row, so a new model forces its row (ADR 0054 D5).
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

__all__ = ["ROLE_OF_MODEL", "role_of"]

ROLE_OF_MODEL: Final[Mapping[str, str]] = MappingProxyType(
    {
        "c1.adiabatic_mixer": "mixer",
        "c1.feed_source": "feed",
        "c1.product_sink": "product_sink",
        "c1.reactor": "reactor",
        "c1.reactor_standin": "reactor",
        "c1.reactor_surrogate": "reactor",
        "c1.stream_splitter": "splitter",
        "c1.tp_flash": "flash",
        "c1.tp_heater": "heater",
        "syn001.adiabatic_mixer": "mixer",
        "syn001.column": "separator",
        "syn001.component_separator": "separator",
        "syn001.conversion_reactor": "reactor",
        "syn001.feed_source": "feed",
        "syn001.kinetic_cstr": "reactor",
        "syn001.ph_flash": "flash",
        "syn001.product_sink": "product_sink",
        "syn001.stream_splitter": "splitter",
        "syn001.tp_flash": "flash",
        "syn001.tp_heater": "heater",
        "syn001.valve": "valve",
        "thermal.compressor": "compressor",
        "thermal.flash": "flash",
        "thermal.heater": "heater",
        "thermal.mixer": "mixer",
        "thermal.pump": "pump",
        "thermal.turbine": "turbine",
        "thermal.valve": "valve",
        "syn001.heat_exchanger": "heat_exchanger",
        "syn001.liquid_pump": "pump",
    }
)


def role_of(model: str) -> str:
    """Table R's role for `model`; `KeyError` for a model the table does not name."""
    return ROLE_OF_MODEL[model]
