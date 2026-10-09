"""M02 G1 (c) (design note §10.1, R4-G3's method): a schema with M02's additive changes taken out.

`without_m02` removes, anywhere in a (resolved) schema or a served tool list: M02's enum values;
each `oneOf` branch whose `operation` is `experiment`; `job_result`'s `experiment` member; and the
two widened descriptions, restored to their pre-M02 text. What remains must equal the pre-M02
snapshots exactly — the proof that M02 moved nothing but what ADR 0033–0035 add.
"""

from __future__ import annotations

from typing import Any, Final

#: Every enum value M02 adds (ADR 0033 D9, ADR 0034, ADR 0035).
M02_ENUM_VALUES: Final = frozenset(
    {
        "experiment",
        "experiment_request",
        "experiment_result",
        "experiment_attempt",
        "external_coupling",
        "model_replacement_report",
        "revision_coupled",
        "COUPLING_NOT_CONVERGED",
        "model_replacement_incompatible",
    }
)
_API_ERROR_DETAIL: Final = (
    "Open. The code's own members: `pointer` (invalid_request, document_not_canonical), `report` "
    "(revision_not_ready), `unbound` (revision_unsupported), `kind` "
    "(verification_weakening_refused), `budget` (budget_exceeds_ceiling), "
    "`original_request_sha256` (idempotency_key_reused), `log_artifact_id` (internal_error)"
)
_INVALIDATIONS: Final = (
    "`run-<job_id>` for every solve job whose `revision_id` equals the expected revision"
)
#: The widened descriptions, each mapped to its pre-M02 text.
RESTORED: Final[dict[str, str]] = {
    f"{_API_ERROR_DETAIL}, `report` (model_replacement_incompatible: the `model-replacement` "
    "report, ADR 0035).": f"{_API_ERROR_DETAIL}.",
    f"{_INVALIDATIONS}; generalized by ADR 0035 D4 to every job of a registered "
    "evidence-producing operation whose request names the expected revision, each with its "
    "operation's prefix, in acceptance order. Experiment records are never invalidated: they are "
    "facts about a variant, not about a revision.": f"{_INVALIDATIONS}.",
}


#: The `experiment_body` `$def`'s description: the MCP binding serves the job body as a list of
#: the bodies, so the inlined `experiment_body` is a list item there, not an operation branch.
_EXPERIMENT_BODY: Final = "§3.5 (ADR 0019 Amendment 4, part 1)"


def _experiment_branch(node: Any) -> bool:
    """A `oneOf` branch for the `experiment` operation, or the inlined `experiment_body`."""
    if not isinstance(node, dict):
        return False
    if str(node.get("description", "")).startswith(_EXPERIMENT_BODY):
        return True
    operation = node.get("properties", {}).get("operation")
    return isinstance(operation, dict) and operation.get("const") == "experiment"


def without_m02(node: Any) -> Any:
    """`node` with every M02 addition taken out (see the module docstring)."""
    if isinstance(node, list):
        return [without_m02(item) for item in node if not _experiment_branch(item)]
    if not isinstance(node, dict):
        return node
    out: dict[str, Any] = {}
    for key, value in node.items():
        if key == "enum" and isinstance(value, list):
            out[key] = [item for item in value if item not in M02_ENUM_VALUES]
        elif key == "description" and isinstance(value, str) and value in RESTORED:
            out[key] = RESTORED[value]
        elif (
            key == "properties"
            and isinstance(value, dict)
            and {"run_result", "replay_report", "experiment"} <= set(value)
        ):
            out[key] = {
                name: without_m02(item) for name, item in value.items() if name != "experiment"
            }
        else:
            out[key] = without_m02(value)
    return out
