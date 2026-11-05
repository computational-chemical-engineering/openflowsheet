"""MSG-G10 (design note §7; ADR 0058): the decomposition function of MSG's surface move. Not
collected.

`without_msg(node)` takes MSG's additions out of a schema, a resolved response schema or a served
MCP tool list:

- `RunResult`'s member `failure` (ADR 0058 D5), from every object whose properties are a run
  result's (`job_id`, `run_id`, `solve_path`, `failure`), and from its `required`;
- the `$defs` MSG added: `run-result.schema.json`'s `run_failure` and
  `application-results.schema.json`'s `explanation` and `message_entry` (ADR 0058 D7, WO-7);
- the `explain` operation's MCP tool (ADR 0058 D7), from a served tool list.

With them removed, every R4-G3 snapshot and the served MCP digest equal their pre-MSG values
(`tests/test_t07_w5e_application_results.py`, `tests/test_t08_w2_surface_digest.py`); the
`explain` row of `OPERATIONS` is new and has no pre-MSG snapshot (`MSG_OPERATIONS`).
"""

from __future__ import annotations

from typing import Any

#: The members that make an object schema a run result's.
RUN_RESULT_MEMBERS = frozenset({"job_id", "run_id", "solve_path", "failure"})
#: The `$defs` MSG added.
MSG_DEFS = frozenset({"run_failure", "explanation", "message_entry"})
#: The operations MSG added (ADR 0058 D7): their rows, and their MCP tools, are new.
MSG_OPERATIONS = frozenset({"explain"})


def _is_msg_tool(node: Any) -> bool:
    """A served MCP tool (`{name, description, inputSchema, …}`) of an MSG operation."""
    return isinstance(node, dict) and "inputSchema" in node and node.get("name") in MSG_OPERATIONS


def without_msg(node: Any) -> Any:
    """`node` with every MSG addition taken out (see the module docstring)."""
    if isinstance(node, list):
        return [without_msg(item) for item in node if not _is_msg_tool(item)]
    if not isinstance(node, dict):
        return node
    out = {key: without_msg(value) for key, value in node.items()}
    properties = out.get("properties")
    if isinstance(properties, dict) and RUN_RESULT_MEMBERS <= set(properties):
        properties.pop("failure")
        out["required"] = [member for member in out["required"] if member != "failure"]
    definitions = out.get("$defs")
    if isinstance(definitions, dict) and MSG_DEFS & set(definitions):
        for name in MSG_DEFS:
            definitions.pop(name, None)
        if not definitions:  # `run-result.schema.json` had no `$defs` before MSG
            del out["$defs"]
    return out
