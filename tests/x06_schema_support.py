"""X06 (ADR 0078 D6, ADR 0019 Amendment 18): the decomposition function of X06's surface move. Not
collected.

`without_x06(node)` takes X06's additions out of a served MCP tool list (any other node is
returned with the same members taken out, copied). From X06-WO2 (branches, D2) they are:

- the three tools of the protocol `Branches`, `list_branches`, `create_branch` and
  `delete_branch`, and from X06-WO3 (solve policies, D4) the two of `SolvePolicies`,
  `register_solve_policy` and `get_solve_policy`, and from X06-WO4 (administration, D5) the
  four of `Administration`, `get_policy`, `grant_capability`, `revoke_capability` and
  `set_ambient_pressure` (`X06_OPERATIONS`);
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

#: The operations X06 added (ADR 0078 D2.5, D4.5, D5.2): their rows, and their MCP tools, are
#: new.
X06_OPERATIONS: Final = frozenset(
    {
        "list_branches",
        "create_branch",
        "delete_branch",
        "register_solve_policy",
        "get_solve_policy",
        "get_policy",
        "grant_capability",
        "revoke_capability",
        "set_ambient_pressure",
    }
)
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


def solve_policy_document(policy_id: str = "user.copy") -> dict[str, Any]:
    """`T06-revision-v2`'s document with only `policy_id` changed (ADR 0078 E-X06-12)."""
    from openflowsheet.orchestrator.policies import T06_REVISION_V2

    return {**T06_REVISION_V2.as_document(), "policy_id": policy_id}


def solve_policies_requests() -> list[tuple[str, dict[str, Any]]]:
    """One succeeding request of each `SolvePolicies` operation (ADR 0078 D4.5): a copy of the
    revision path's policy registered, then read."""
    return [
        (
            "register_solve_policy",
            {"policy": solve_policy_document(), "idempotency_key": "sp1"},
        ),
        ("get_solve_policy", {"policy_id": "user.copy"}),
    ]


#: ADR 0078 D5.2: the grant `administration_requests` makes and revokes.
ADMINISTERED_CAPABILITY: Final = "cap-x06-delegate"


def administration_requests() -> list[tuple[str, dict[str, Any]]]:
    """One succeeding request of each `Administration` operation (ADR 0078 D5.2), for a caller
    holding `read` and `policy` with at most `project grant`'s limits and no expiry, in a
    project whose operator switched in-band administration on: the policy read, the ambient
    pressure declared, a `read` grant within the limits made, then revoked."""
    return [
        ("get_policy", {}),
        ("set_ambient_pressure", {"value": 1.0, "unit": "bar", "idempotency_key": "ad1"}),
        (
            "grant_capability",
            {
                "principal_id": "x06-delegate",
                "rights": ["read"],
                "limits": {"default_wall_time_s": 60, "max_wall_time_s": 60, "max_active_jobs": 1},
                "capability_id": ADMINISTERED_CAPABILITY,
                "idempotency_key": "ad2",
            },
        ),
        ("revoke_capability", {"capability_id": ADMINISTERED_CAPABILITY, "idempotency_key": "ad3"}),
    ]


def stable_administration(document: Any) -> Any:
    """`document` with what a grant draws at random replaced by placeholders: a `prt_` token,
    every `token_sha256`, and a `grant_result`'s `policy_sha256` (the hash of a policy holding
    the new token's hash; a grant result is the object with both `capability` and `token`, so
    one lacking its `status` is one too). Two projects granting the same request differ in these
    alone."""
    if isinstance(document, dict):
        grant = {"capability", "token"} <= set(document)
        out = {
            key: (
                "<random>"
                if key == "token_sha256"
                and value is not None
                or key == "token"
                and isinstance(value, str)
                or key == "policy_sha256"
                and grant
                else stable_administration(value)
            )
            for key, value in document.items()
        }
        return out
    if isinstance(document, list):
        return [stable_administration(item) for item in document]
    return document
