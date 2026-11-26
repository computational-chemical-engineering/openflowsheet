"""X06 (ADR 0078 D6, ADR 0019 Amendment 18): the decomposition function of X06's surface move. Not
collected.

`without_x06(node)` takes X06's additions out of a served MCP tool list (any other node is
returned with the same members taken out, copied). From X06-WO2 (branches, D2) they are:

- the three tools of the protocol `Branches`, `list_branches`, `create_branch` and
  `delete_branch` (`X06_OPERATIONS`);
- the optional `branch` member of the ChangeSet (`change-set.schema.json`), wherever the ChangeSet
  is served: `commit_change`'s and `preview_change`'s `inputSchema` and the optimization
  report's `candidate.change_set` in `get_job_result`'s `outputSchema` (an object schema whose
  properties hold `edits`, `expected_revision` and `branch`), and its `$defs` member `branch_name`
  where a resolved schema keeps the ChangeSet's `$defs` (beside `edit`);
- the `branch` sentence in those two tools' description texts, restored from their pre-X06
  copies under `tests/fixtures/x06/pre_x06_descriptions/` (`X06_DESCRIPTIONS`).

With them removed the served list is the one on `main` before X06: F3's `f7ec3c94…`
(`F3_SERVED_SHA256`, `scripts/m07a_rc.py` link c_10) on `wp/X06`; whichever of X06 and F2 merges
second decomposes onto the first's (ADR 0078 D6, Q8). `without_x06` composes with the other
`without_*` functions: it touches no member they remove.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Final

#: The operations X06 added (ADR 0078 D2.5): their rows, and their MCP tools, are new.
X06_OPERATIONS: Final = frozenset({"list_branches", "create_branch", "delete_branch"})
#: The description files X06 changed (operation name -> MCP tool name) and their pre-X06 copies.
X06_DESCRIPTIONS: Final = {"commit_change": "commit_change", "preview_change": "preview_change"}
PRE_X06_TEXTS: Final = Path(__file__).resolve().parent / "fixtures" / "x06" / "pre_x06_descriptions"


def pre_x06_text(name: str) -> str:
    """The pre-X06 description file of operation `name` (one of `X06_DESCRIPTIONS`)."""
    return (PRE_X06_TEXTS / f"{name}.md").read_text("utf-8")


def _is_x06_tool(node: Any) -> bool:
    """A served MCP tool (`{name, description, inputSchema, …}`) of an X06 operation."""
    return isinstance(node, dict) and "inputSchema" in node and node.get("name") in X06_OPERATIONS


def _is_change_set(properties: Any) -> bool:
    """An object schema's `properties` that are the ChangeSet's, widened by `branch`."""
    return isinstance(properties, dict) and {"edits", "expected_revision", "branch"} <= set(
        properties
    )


def without_x06(node: Any) -> Any:
    """`node` with every X06 addition taken out (see the module docstring)."""
    if isinstance(node, list):
        out = []
        for item in node:
            if _is_x06_tool(item):
                continue
            if isinstance(item, dict) and "inputSchema" in item:
                name = item.get("name")
                if name in X06_DESCRIPTIONS.values() and "description" in item:
                    (operation,) = [op for op, tool in X06_DESCRIPTIONS.items() if tool == name]
                    item = {**item, "description": pre_x06_text(operation)}
            out.append(without_x06(item))
        return out
    if not isinstance(node, dict):
        return node
    out_node = {key: without_x06(value) for key, value in node.items()}
    definitions = out_node.get("$defs")
    if isinstance(definitions, dict) and {"edit", "branch_name"} <= set(definitions):
        out_node["$defs"] = {k: v for k, v in definitions.items() if k != "branch_name"}
    if _is_change_set(out_node.get("properties")):
        properties = out_node["properties"]
        out_node["properties"] = {k: v for k, v in properties.items() if k != "branch"}
    return out_node


def branches_requests(revision_id: str) -> list[tuple[str, dict[str, Any]]]:
    """One succeeding request of each `Branches` operation (ADR 0078 D2.5) in a project holding
    `revision_id`: a branch created there, the refs listed, the branch deleted."""
    return [
        ("create_branch", {"name": "what-if", "revision_id": revision_id, "idempotency_key": "b1"}),
        ("list_branches", {"limit": 2}),
        (
            "delete_branch",
            {"name": "what-if", "expected_revision": revision_id, "idempotency_key": "b2"},
        ),
    ]
