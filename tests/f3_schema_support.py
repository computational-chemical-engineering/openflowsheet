"""F3-WO5b (ADR 0061 D13, ADR 0019 Amendment 8): the decomposition function of F3's surface move,
and the one user record the transport corpora register. Not collected.

F3 adds the protocol `Records`, five operations (`search_records`, `get_record`,
`register_record`, `validate_record`, `assess_rights`), with new response `$defs` of
`application-results.schema.json` (`record_page`, `record_view`, `record_registration_result`,
`record_validation_report`, `rights_assessment_result` and the shapes they reference): no
existing `$def` moves, and no other operation's resolved response does. The one MCP-visible change
is their five tools in the served list; no existing description text changes.

`without_f3(node)` takes those tools out of a served MCP tool list (any other node is returned
as it is, copied). With them removed the served list is F1's (`F1_SERVED_SHA256`, link c_9),
and every R4-G3 snapshot other than the new rows' is unchanged (`F3_OPERATIONS`).
"""

from __future__ import annotations

from typing import Any

#: The operations F3 added (ADR 0061 D13): their rows, and their MCP tools, are new.
F3_OPERATIONS = frozenset(
    {"search_records", "get_record", "register_record", "validate_record", "assess_rights"}
)


def _is_f3_tool(node: Any) -> bool:
    """A served MCP tool (`{name, description, inputSchema, …}`) of an F3 operation."""
    return isinstance(node, dict) and "inputSchema" in node and node.get("name") in F3_OPERATIONS


def without_f3(node: Any) -> Any:
    """`node` with every F3 addition taken out (see the module docstring)."""
    if isinstance(node, list):
        return [without_f3(item) for item in node if not _is_f3_tool(item)]
    if not isinstance(node, dict):
        return node
    return {key: without_f3(value) for key, value in node.items()}


def user_component(
    ident: str = "user.xenonol", name: str = "xenonol", *, source: str = "user.lab"
) -> dict[str, Any]:
    """A valid D2 `mol` component of a user source, with one identifier (a CAS number no
    committed record carries)."""
    return {
        "record_format": "openflowsheet-record-v2",
        "record_type": "component",
        "type_version": "1.0.0",
        "id": ident,
        "name": name,
        "sources": {source: {"version": "1"}},
        "synthetic": False,
        "identifiers": {"cas": "999-99-5"},
        "amount_basis": "mol",
        "charge": 0,
        "elemental_verification": "NOT_APPLICABLE",
        "molar_mass": {
            "value": 0.05,
            "unit": "kg/mol",
            "kind": "molar_mass",
            "provenance": {"origin": ["measured"], "derivation": "direct", "source": source},
        },
    }


def records_requests(record_sha256: str) -> list[tuple[str, dict[str, Any]]]:
    """One succeeding request of each `Records` operation after `user_component()` is
    registered as `record_sha256` (the registration itself is the first)."""
    return [
        ("register_record", {"record": user_component()}),
        ("search_records", {"key": "xenonol", "limit": 2}),
        ("get_record", {"record_sha256": record_sha256}),
        ("validate_record", {"record": user_component()}),
        (
            "assess_rights",
            {
                "source_id": "user.lab",
                "record_sha256": record_sha256,
                "scope": "record",
                "assessment": "permitted",
                "basis": "the lab's own measurement",
            },
        ),
    ]


def user_record_sha256() -> str:
    """`user_component()`'s record SHA (D3), as `register_record` returns it."""
    from openflowsheet.records.identity import identify

    sha = identify(user_component()).record_sha256
    assert sha is not None
    return sha
