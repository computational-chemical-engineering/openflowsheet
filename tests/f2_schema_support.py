"""F2-WO2b (ADR 0062 D1): the decomposition function of F2's surface move. Not collected.

F2-WO1 appends ADR 0062 D1's 14 quantity kinds to the kind enum of `quantity.schema.json` and
adds one sentence to that enum's description. The enum is served wherever a schema reaches a
quantity's `kind`: in the resolved responses that is `list_models`' alone (`model_registry_view`,
its pins' and its choice options' `specifications`), and on the served MCP tool list that tool's
`outputSchema`, at the same two places. F2 adds no operation, no tool and no description text.

`without_f2(node)` takes those additions out of a (resolved) schema or a served MCP tool list:
from every kind enum that ends in the 14 kinds, the 14 values and the description's sentence.
Any other node is returned as it is, copied. What remains must equal the surface as the previous
link left it: the served list is F3's `f7ec3c94…` (`F3_SERVED_SHA256`), and `list_models`' R4-G3
snapshot is its value before F2 (ADR 0019 Amendment 2's `12d88245…`); no other snapshot moves.
"""

from __future__ import annotations

from typing import Any, Final

#: ADR 0062 D1's 14 kinds, in the order F2-WO1 appended them to the enum.
F2_KINDS: Final = (
    "specific_enthalpy",
    "specific_entropy",
    "specific_volume",
    "specific_heat_capacity",
    "molar_entropy",
    "segment_molar_flow",
    "segment_molar_mass",
    "segment_molar_enthalpy",
    "segment_molar_entropy",
    "segment_molar_heat_capacity",
    "segment_molar_volume",
    "enthalpy_flow",
    "mass_fraction",
    "number_flow",
)
#: The sentence F2-WO1 appended to the kind enum's description.
F2_KIND_NOTE: Final = " The last 14 are ADR 0062 D1's (F2-WO1)."
#: The operations whose resolved response F2 moved (`SNAPSHOT_F2`).
F2_MOVED_OPERATIONS: Final = frozenset({"list_models"})


def is_f2_kind_enum(node: Any) -> bool:
    """A kind enum with F2's 14 kinds at its end."""
    if not isinstance(node, dict):
        return False
    enum = node.get("enum")
    return isinstance(enum, list) and tuple(enum[-len(F2_KINDS) :]) == F2_KINDS


def without_f2(node: Any) -> Any:
    """`node` with every F2 addition taken out (see the module docstring)."""
    if isinstance(node, list):
        return [without_f2(item) for item in node]
    if not isinstance(node, dict):
        return node
    out = {key: without_f2(value) for key, value in node.items()}
    if is_f2_kind_enum(node):
        out["enum"] = node["enum"][: -len(F2_KINDS)]
        description = node.get("description")
        if isinstance(description, str):
            out["description"] = description.removesuffix(F2_KIND_NOTE)
    return out
