"""The diagnostic sidecar (MSG design note §4.6): the numbers of a refusal, carried on its value.

A producer that refuses may attach a `Diagnostic(code, params)` to the failure value it already
returns. The field is never serialized into an artifact (I3); it is persisted only as
`run["diagnosis"]` in the job store's `worker_result`. This module is the one part of
`openflowsheet.messages` the solver path imports, so it uses the standard library only.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any


@dataclass(frozen=True)
class Quantity:
    """A number with its SI unit and quantity kind (`schemas/units.json`); MSG converts nothing."""

    value: float
    unit: str
    kind: str

    def as_document(self) -> dict[str, Any]:
        return {"value": self.value, "unit": self.unit, "kind": self.kind}


def _finite(value: object) -> bool:
    if isinstance(value, Quantity):
        return math.isfinite(value.value)
    if isinstance(value, float):
        return math.isfinite(value)
    return True


@dataclass(frozen=True)
class Diagnostic:
    """A refusal's code and its structured params. Non-finite numbers are dropped here, so a
    rendering never shows `nan` or `inf`."""

    code: str
    params: Mapping[str, str | int | bool | float | Quantity] = field(default_factory=dict)

    def __post_init__(self) -> None:
        kept = {name: value for name, value in self.params.items() if _finite(value)}
        object.__setattr__(self, "params", MappingProxyType(kept))

    def as_document(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "params": {
                name: value.as_document() if isinstance(value, Quantity) else value
                for name, value in self.params.items()
            },
        }
