"""ST G12 (design note `docs/design/ST-stream-table.md` §7, §11; ADR 0068): the decomposition
function of ST's surface move. Not collected.

ST adds one operation, `get_stream_table` (ADR 0019 Amendment 13), whose response is the existing
`projection` `$def`: no schema of `application-results.schema.json` moves, and no other operation's
resolved response does. The one MCP-visible change is its tool in the served list.

`without_st(node)` takes that tool out of a served MCP tool list (any other node is returned as it
is, copied). With it removed the served list is MSG's (`MSG_SERVED_SHA256`, link c_4), and every
R4-G3 snapshot other than the new row's is unchanged (`ST_OPERATIONS`).
"""

from __future__ import annotations

from typing import Any

#: The operations ST added (ADR 0068): their rows, and their MCP tools, are new.
ST_OPERATIONS = frozenset({"get_stream_table"})


def _is_st_tool(node: Any) -> bool:
    """A served MCP tool (`{name, description, inputSchema, …}`) of an ST operation."""
    return isinstance(node, dict) and "inputSchema" in node and node.get("name") in ST_OPERATIONS


def without_st(node: Any) -> Any:
    """`node` with every ST addition taken out (see the module docstring)."""
    if isinstance(node, list):
        return [without_st(item) for item in node if not _is_st_tool(item)]
    if not isinstance(node, dict):
        return node
    return {key: without_st(value) for key, value in node.items()}
