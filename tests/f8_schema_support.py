"""F8-WO1b (ADR 0067 D3, D5; R-1076): the decomposition function of F8's surface move. Not
collected.

F8 widens two published schemas, additively:

- `replay-report.schema.json` (ADR 0019 Amendment 12, D5): the reserved value `forced_replay` at the
  end of `mode`'s enum (D8; refused by `run.manifest_v2.refuse_reserved_mode`, DECISION F8-WO1-6)
  and the two optional members `registry_comparison` and `data_availability`, each a `$ref` to
  `bundle-v2.schema.json`'s `$defs` of the same name;
- `job.schema.json` (D3): the seven v2 artifact kinds at the end of `artifact_ref.kind`'s enum
  (`F8_ARTIFACT_KINDS`).

The replay report is served wherever a response embeds it (`reproduce`, and `get_job`,
`cancel_job` and `get_job_result` through the job and its result); an artifact reference wherever a
response lists artifacts (the job operations and `solve`). On the served MCP tool list only
`get_job_result`'s `outputSchema` moves, in its `replay_report`: MCP serves J5's consumer reading
of the artifact kind, the enum opened. F8 adds no operation, no tool and no description text.

`without_f8(node)` takes those additions out of a (resolved) schema or a served MCP tool list:
from every replay-report object schema the two members, from every mode enum that ends in
`forced_replay` that value, and from every kind enum that ends in the seven kinds those values.
Any other node is returned as it is, copied. What remains must equal the surface as the previous
link left it: on `wp/F8`, which branches from `wp/F2`, the served list is F2's `9a4b4eb3…`
(`F2_SERVED_SHA256`, `scripts/m07a_rc.py` link c_11), and each moved R4-G3 snapshot is its value
before F8 (`SNAPSHOT_F8`'s rows). `without_f8` composes with the other `without_*` functions: it
touches no member they remove.
"""

from __future__ import annotations

from typing import Any, Final

#: ADR 0067 D3's artifact kinds, in the order F8-WO1b appended them to `artifact_ref.kind`.
F8_ARTIFACT_KINDS: Final = (
    "data_lock",
    "registry_snapshot",
    "records_index",
    "record",
    "run_evidence",
    "decision_record",
    "exchange_record",
)
#: ADR 0067 D5 (Amendment 12): the reserved replay mode, appended to `mode`'s enum.
F8_REPLAY_MODE: Final = "forced_replay"
#: The replay modes before F8 (ADR 0007 D4), in their order.
PRE_F8_REPLAY_MODES: Final = (
    "exact_replay",
    "compatible_reproduction",
    "inspected_archived_results",
)
#: ADR 0067 D5 (Amendment 12): the two optional members of the replay report.
F8_REPORT_MEMBERS: Final = ("registry_comparison", "data_availability")
#: The operations whose resolved response F8 moved (`SNAPSHOT_F8`).
F8_MOVED_OPERATIONS: Final = frozenset(
    {
        "solve",
        "reproduce",
        "submit_job",
        "get_job",
        "list_jobs",
        "list_job_events",
        "wait_job",
        "cancel_job",
        "get_job_result",
    }
)
#: The member only the replay report has, by which its object schema is recognised.
REPLAY_REPORT_MARK: Final = "verdict_changed_near_threshold"


def is_f8_mode_enum(node: Any) -> bool:
    """The replay report's `mode` enum with F8's reserved value at its end."""
    return isinstance(node, dict) and node.get("enum") == [*PRE_F8_REPLAY_MODES, F8_REPLAY_MODE]


def is_f8_kind_enum(node: Any) -> bool:
    """An artifact kind enum with F8's seven kinds at its end."""
    if not isinstance(node, dict):
        return False
    enum = node.get("enum")
    return isinstance(enum, list) and tuple(enum[-len(F8_ARTIFACT_KINDS) :]) == F8_ARTIFACT_KINDS


def is_replay_report(node: Any) -> bool:
    """A replay report's object schema: its properties carry `REPLAY_REPORT_MARK`."""
    if not isinstance(node, dict):
        return False
    properties = node.get("properties")
    return isinstance(properties, dict) and REPLAY_REPORT_MARK in properties


def without_f8(node: Any) -> Any:
    """`node` with every F8 addition taken out (see the module docstring)."""
    if isinstance(node, list):
        return [without_f8(item) for item in node]
    if not isinstance(node, dict):
        return node
    out = {key: without_f8(value) for key, value in node.items()}
    if is_replay_report(node):
        out["properties"] = {
            key: value for key, value in out["properties"].items() if key not in F8_REPORT_MEMBERS
        }
    if is_f8_mode_enum(node):
        out["enum"] = list(PRE_F8_REPLAY_MODES)
    if is_f8_kind_enum(node):
        out["enum"] = node["enum"][: -len(F8_ARTIFACT_KINDS)]
    return out
