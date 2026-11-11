"""F1-WO4a (ADR 0060 D11, ADR 0019 Amendment 7): the decomposition function of F1's surface move.
Not collected.

F1 adds two operations, `list_capabilities` and `check_admission`, with two new response `$defs`
of `application-results.schema.json` (`capability_page`, its items `capability_descriptor`, and
`admission_report`): no existing `$def` moves, and no other operation's resolved response does.
The one MCP-visible change is their two tools in the served list; no existing description text
changes.

`without_f1(node)` takes those tools out of a served MCP tool list (any other node is returned
as it is, copied). With them removed the served list is X04's (`X04_SERVED_SHA256`, link c_8),
and every R4-G3 snapshot other than the new rows' is unchanged (`F1_OPERATIONS`).
"""

from __future__ import annotations

from typing import Any

#: The operations F1 added (ADR 0060 D11): their rows, and their MCP tools, are new.
F1_OPERATIONS = frozenset({"list_capabilities", "check_admission"})


def _is_f1_tool(node: Any) -> bool:
    """A served MCP tool (`{name, description, inputSchema, …}`) of an F1 operation."""
    return isinstance(node, dict) and "inputSchema" in node and node.get("name") in F1_OPERATIONS


def without_f1(node: Any) -> Any:
    """`node` with every F1 addition taken out (see the module docstring)."""
    if isinstance(node, list):
        return [without_f1(item) for item in node if not _is_f1_tool(item)]
    if not isinstance(node, dict):
        return node
    return {key: without_f1(value) for key, value in node.items()}
