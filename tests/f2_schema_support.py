"""F2-WO2b (ADR 0062 D1): the decomposition function of F2's surface move. Not collected.

F2-WO1 appends ADR 0062 D1's 14 quantity kinds to the kind enum of `quantity.schema.json` and
adds one sentence to that enum's description. The enum is served wherever a schema reaches a
quantity's `kind`: in the resolved responses that is `list_models`' alone (`model_registry_view`,
its pins' and its choice options' `specifications`), and on the served MCP tool list that tool's
`outputSchema`, at the same two places. F2 adds no operation and no tool; F2-WO8 (the F2 review's
ruling 3) changed one description text, `check_admission.md` (`<schema_version 1 or 2 document>`).

`without_f2(node)` takes those additions out of a (resolved) schema or a served MCP tool list:
from every kind enum that ends in the 14 kinds, the 14 values and the description's sentence;
on a served tool list, `check_admission`'s description is its pre-F2 copy (as X04's are).
Any other node is returned as it is, copied. What remains must equal the surface as the previous
link left it: the served list is F3's `f7ec3c94…` (`F3_SERVED_SHA256`), and `list_models`' R4-G3
snapshot is its value before F2 (ADR 0019 Amendment 2's `12d88245…`); no other snapshot moves.
"""

from __future__ import annotations

from pathlib import Path
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
#: The description files F2 changed (operation name -> MCP tool name) and their pre-F2 copies.
F2_DESCRIPTIONS: Final = {"check_admission": "check_admission"}
PRE_F2_TEXTS: Final = Path(__file__).resolve().parent / "fixtures" / "f2" / "pre_f2_descriptions"


def pre_f2_text(name: str) -> str:
    """The pre-F2 description file of operation `name` (one of `F2_DESCRIPTIONS`)."""
    return (PRE_F2_TEXTS / f"{name}.md").read_text("utf-8")


def is_f2_kind_enum(node: Any) -> bool:
    """A kind enum with F2's 14 kinds at its end."""
    if not isinstance(node, dict):
        return False
    enum = node.get("enum")
    return isinstance(enum, list) and tuple(enum[-len(F2_KINDS) :]) == F2_KINDS


def without_f2(node: Any) -> Any:
    """`node` with every F2 addition taken out (see the module docstring)."""
    out = _without(node)
    if isinstance(out, list):
        texts = {tool: pre_f2_text(name) for name, tool in F2_DESCRIPTIONS.items()}
        for tool in out:
            if isinstance(tool, dict) and tool.get("name") in texts and "description" in tool:
                tool["description"] = texts[tool["name"]]
    return out


def _without(node: Any) -> Any:
    if isinstance(node, list):
        return [_without(item) for item in node]
    if not isinstance(node, dict):
        return node
    out = {key: _without(value) for key, value in node.items()}
    if is_f2_kind_enum(node):
        out["enum"] = node["enum"][: -len(F2_KINDS)]
        description = node.get("description")
        if isinstance(description, str):
            out["description"] = description.removesuffix(F2_KIND_NOTE)
    return out
