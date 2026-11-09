"""OPT (ADR 0071, ADR 0019 Amendment 16; design §4.13): the decomposition function of OPT's surface
move. Not collected.

`without_opt(node)` takes OPT's additions out of a (resolved) schema or a served MCP tool list:

- OPT's enum values: the job operation `optimize` and the six artifact kinds
  (`optimization_request`, `optimization_report`, `optimization_manifest`, `optimizer_record`,
  `candidate_revision`, `candidate_verification`);
- each `oneOf` branch whose `operation` is `optimize` (the request's and the result's), and the
  inlined `optimize_body` (the MCP binding serves the job body as a list of the bodies; it is found
  by its description prefix);
- `job_result`'s `optimization` member;
- `validate`'s `optimization` member (an object whose properties are `revision_id`, `task` and
  `optimization`);
- and, on a served tool list, the two description texts OPT changed (`validate.md`,
  `submit_job.md`), restored from their pre-OPT copies under `tests/fixtures/opt/`.

None of the members is required, so no `required` list changes. What remains must equal the
surface as the previous link left it (`scripts/m07a_rc.py` link c_6 over X02's c_5; D-51, D-87).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Final

#: Every enum value OPT adds to an existing schema (ADR 0071, Amendment 16).
OPT_ENUM_VALUES: Final = frozenset(
    {
        "optimize",
        "optimization_request",
        "optimization_report",
        "optimization_manifest",
        "optimizer_record",
        "candidate_revision",
        "candidate_verification",
    }
)
#: The `optimize_body` `$def`'s description prefix.
_OPTIMIZE_BODY: Final = "OPT design §4.10 (ADR 0071"
#: The description files OPT changed (operation name -> MCP tool name) and their pre-OPT copies.
OPT_DESCRIPTIONS: Final = {"submit_job": "submit_job", "validate": "validate_revision"}
PRE_OPT_TEXTS: Final = Path(__file__).resolve().parent / "fixtures" / "opt" / "pre_opt_descriptions"


def pre_opt_text(name: str) -> str:
    """The pre-OPT description file of operation `name` (one of `OPT_DESCRIPTIONS`)."""
    return (PRE_OPT_TEXTS / f"{name}.md").read_text("utf-8")


def _optimize_branch(node: Any) -> bool:
    """A `oneOf` branch for the `optimize` operation, or the inlined optimize body."""
    if not isinstance(node, dict):
        return False
    if str(node.get("description", "")).startswith(_OPTIMIZE_BODY) and "request" in node.get(
        "properties", {}
    ):
        return True
    operation = node.get("properties", {}).get("operation")
    return isinstance(operation, dict) and operation.get("const") == "optimize"


def _without(node: Any) -> Any:
    if isinstance(node, list):
        return [_without(item) for item in node if not _optimize_branch(item)]
    if not isinstance(node, dict):
        return node
    out: dict[str, Any] = {}
    for key, value in node.items():
        if key == "enum" and isinstance(value, list):
            out[key] = [item for item in value if item not in OPT_ENUM_VALUES]
        elif key == "properties" and isinstance(value, dict) and _opt_member(value) is not None:
            dropped = _opt_member(value)
            out[key] = {name: _without(item) for name, item in value.items() if name != dropped}
        else:
            out[key] = _without(value)
    return out


def _opt_member(properties: dict[str, Any]) -> str | None:
    """The member OPT added to this object's properties, if it is one OPT widened."""
    if {"run_result", "replay_report", "optimization"} <= set(properties):
        return "optimization"
    if set(properties) == {"revision_id", "task", "optimization"}:
        return "optimization"
    return None


def without_opt(node: Any) -> Any:
    """`node` with every OPT addition taken out (see the module docstring)."""
    out = _without(node)
    if isinstance(out, list):
        texts = {tool: pre_opt_text(name) for name, tool in OPT_DESCRIPTIONS.items()}
        for tool in out:
            if isinstance(tool, dict) and tool.get("name") in texts and "description" in tool:
                tool["description"] = texts[tool["name"]]
    return out
