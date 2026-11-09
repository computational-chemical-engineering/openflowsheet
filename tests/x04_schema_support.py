"""X04 (ADR 0075, ADR 0019 Amendment 17): the decomposition function of X04's surface move. Not
collected.

`without_x04(node)` takes X04's additions out of a (resolved) schema or a served MCP tool list:

- `project_summary`'s `ambient_pressure` member (D6.3), from its properties and its `required`;
- the `display` member of an explanation's number (D7.1–D7.2);
- `job_result`'s `display_units` member (D7.4–D7.5);
- the optional `display_units` request member (D8) of `get_job_result` and `get_stream_table`;
- and, on a served tool list, the two description texts X04 changed (`get_job_result.md`,
  `get_stream_table.md`), restored from their pre-X04 copies under `tests/fixtures/x04/`.

Only `ambient_pressure` is required, so only `project_summary`'s `required` list changes. What
remains must equal the surface as the previous link left it (`scripts/m07a_rc.py` link c_8 over
ST's c_7, R-1010): the served list is ST's `553b7612…` (`ST_SERVED_SHA256`), and every R4-G3
snapshot X04 moved (`SNAPSHOT_X04`) is its value before X04.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Final

#: The description files X04 changed (operation name -> MCP tool name) and their pre-X04 copies.
X04_DESCRIPTIONS: Final = {
    "get_job_result": "get_job_result",
    "get_stream_table": "get_stream_table",
}
PRE_X04_TEXTS: Final = Path(__file__).resolve().parent / "fixtures" / "x04" / "pre_x04_descriptions"
#: ADR 0075 D8: the request member's schema (`operations.DISPLAY_UNITS`).
_DISPLAY_UNITS_REQUEST: Final = {"type": "string", "minLength": 1, "maxLength": 1024}


def pre_x04_text(name: str) -> str:
    """The pre-X04 description file of operation `name` (one of `X04_DESCRIPTIONS`)."""
    return (PRE_X04_TEXTS / f"{name}.md").read_text("utf-8")


def _x04_member(properties: dict[str, Any]) -> str | None:
    """The member X04 added to this object's properties, if it is one X04 widened."""
    if {"project_id", "revision_count", "solve_policies", "ambient_pressure"} <= set(properties):
        return "ambient_pressure"
    if {"name", "label", "kind", "value", "unit", "display"} <= set(properties):
        return "display"
    if {"run_result", "replay_report", "display_units"} <= set(properties):
        return "display_units"
    if properties.get("display_units") == _DISPLAY_UNITS_REQUEST and "job_id" in properties:
        return "display_units"
    return None


def _without(node: Any) -> Any:
    if isinstance(node, list):
        return [_without(item) for item in node]
    if not isinstance(node, dict):
        return node
    properties = node.get("properties")
    dropped = _x04_member(properties) if isinstance(properties, dict) else None
    out: dict[str, Any] = {}
    for key, value in node.items():
        if key == "properties" and dropped is not None:
            out[key] = {name: _without(item) for name, item in value.items() if name != dropped}
        elif key == "required" and dropped is not None and isinstance(value, list):
            out[key] = [name for name in value if name != dropped]
        else:
            out[key] = _without(value)
    return out


def without_x04(node: Any) -> Any:
    """`node` with every X04 addition taken out (see the module docstring)."""
    out = _without(node)
    if isinstance(out, list):
        texts = {tool: pre_x04_text(name) for name, tool in X04_DESCRIPTIONS.items()}
        for tool in out:
            if isinstance(tool, dict) and tool.get("name") in texts and "description" in tool:
                tool["description"] = texts[tool["name"]]
    return out
