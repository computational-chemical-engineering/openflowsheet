"""X02 (ADR 0070, ADR 0019 Amendment 15; design note §5.1): the decomposition function of X02's
surface move. Not collected.

`without_x02(node)` takes X02's three optional members out of a schema, a resolved response schema
or a served MCP tool list:

- `warm_start`, from every object whose properties are a solve body's (`revision_id`,
  `policy_id`, `check_tolerances`, `max_property_calls`, `warm_start`);
- `start`, from every object whose properties are an experiment request's (`experiment_key`,
  `model`, `boundary`, `inputs`, `start`);
- `profile_sha256`, from every object whose properties are an experiment result's
  (`experiment_key`, `request_sha256`, `outcome_class`, `envelope`, `profile_sha256`).

None of the three is required, so no `required` list changes. With them removed, the served MCP
digest and every resolved response schema equal their pre-X02 values
(`tests/test_t08_w2_surface_digest.py`, `scripts/m07a_rc.py` link c_4).
"""

from __future__ import annotations

from typing import Any, Final

#: (the members that identify the object, the member X02 added to it).
X02_MEMBERS: Final = (
    (
        frozenset({"revision_id", "policy_id", "check_tolerances", "max_property_calls"}),
        "warm_start",
    ),
    (frozenset({"experiment_key", "model", "boundary", "inputs"}), "start"),
    (
        frozenset({"experiment_key", "request_sha256", "outcome_class", "envelope"}),
        "profile_sha256",
    ),
)


def without_x02(node: Any) -> Any:
    """`node` with every X02 addition taken out (see the module docstring)."""
    if isinstance(node, list):
        return [without_x02(item) for item in node]
    if not isinstance(node, dict):
        return node
    out = {key: without_x02(value) for key, value in node.items()}
    properties = out.get("properties")
    if isinstance(properties, dict):
        for members, added in X02_MEMBERS:
            if members | {added} <= set(properties):
                properties.pop(added)
    return out
