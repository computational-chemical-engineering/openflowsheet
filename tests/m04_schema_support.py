"""M04 (ADR 0037 D6, ADR 0019 Amendment 5): a schema with M04's additive changes taken out.

`without_m04` removes, anywhere in a (resolved) schema or a served tool list: M04's enum values
(`surrogate_study`, `surrogate_manifest`, `model_evidence`, and the replacement facet
`surrogate_evidence`, ADR 0037 D3); each `oneOf` branch whose `operation` is `surrogate_study`,
and the inlined `surrogate_study_body` (the MCP binding serves the job body as a list of the
bodies); and `job_result`'s `surrogate_study` member. What remains must equal the
schemas as M02 left them — the proof that M04 moved nothing but what ADR 0037 D6 adds. It is
applied before M02's `without_m02`, whose snapshots predate M04.
"""

from __future__ import annotations

from typing import Any, Final

#: Every enum value M04 adds to an existing schema (ADR 0037 D6).
M04_ENUM_VALUES: Final = frozenset(
    {"surrogate_study", "surrogate_manifest", "model_evidence", "surrogate_evidence"}
)
#: The model M04 adds to `MODEL_BUILDERS`, hence to `list_models` (W27 Amendment 3, R-301). A
#: test of an earlier package's registry or served surface takes it out first (R-295).
M04_MODELS: Final = ("c1.reactor_surrogate",)
#: The `surrogate_study_body` `$def`'s description prefix.
_STUDY_BODY: Final = "M04 spec §10.3 (ADR 0037 D6, ADR 0019 Amendment 5)"


def _study_branch(node: Any) -> bool:
    """A `oneOf` branch for the `surrogate_study` operation, or the inlined study body."""
    if not isinstance(node, dict):
        return False
    if str(node.get("description", "")).startswith(_STUDY_BODY):
        return True
    operation = node.get("properties", {}).get("operation")
    return isinstance(operation, dict) and operation.get("const") == "surrogate_study"


def without_m04(node: Any) -> Any:
    """`node` with every M04 addition taken out (see the module docstring)."""
    if isinstance(node, list):
        return [without_m04(item) for item in node if not _study_branch(item)]
    if not isinstance(node, dict):
        return node
    out: dict[str, Any] = {}
    for key, value in node.items():
        if key == "enum" and isinstance(value, list):
            out[key] = [item for item in value if item not in M04_ENUM_VALUES]
        elif (
            key == "properties"
            and isinstance(value, dict)
            and {"run_result", "replay_report", "surrogate_study"} <= set(value)
        ):
            out[key] = {
                name: without_m04(item) for name, item in value.items() if name != "surrogate_study"
            }
        else:
            out[key] = without_m04(value)
    return out
