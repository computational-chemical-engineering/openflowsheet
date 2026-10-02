"""Recovery edge 3: EO globalization failure → specification continuation. T04 §5; ADR 0010 D3.

Blueprint §7.7's fallback edges each state a trigger, preconditions, a maximum count, a
checkpoint policy and a typed outcome; plan §4.3 names this one "EO globalization failure → typed
homotopy". A region solve — a `solve_eo` step's, or the region a T02 §4.4 merge ran — that ends in
one of `EO_RECOVERY_TRIGGERS` is re-solved **once**, by a fresh region solve whose attempt 0 runs
the homotopy from the failed solve's item-0 opening state (T04 §5.3; register R-031: the failed
end state is where the globalization got lost, and is not a root of any level).

`ACTIVE_SET_CYCLING` and `ATTEMPTS_EXHAUSTED` are triggers because on the lifted path the contract
turns a core's globalization failure into a restart (T03 §4.8 rows 2–5), so the failure surfaces
as the contract's terminal outcome: PHS-05's Newton failure *is* its cycling. The rank failure
`LINEAR_SOLVE_FAILED` has its own row in blueprint §7.7; the defects, the refusals before any
attempt, a spent property budget and `HOMOTOPY_STALLED` itself are not triggers — the last so that
the edge cannot recurse.

The edge changes the *solver*, not the *problem*: the recovery's λ = 1 instance has the failed
solve's `(model_version, constants_sha256)` and the region's rows and columns (§5.4).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Final

__all__ = ["EO_RECOVERY_TRIGGERS", "eo_recovery_due", "recovered_provenance"]

#: §5.1: the terminal outcomes of a region solve after which edge 3 runs. `BUDGET_EXHAUSTED` is a
#: trigger only for the cores' own budgets (`EO_RECOVERY_BUDGETS`), never for property calls.
EO_RECOVERY_TRIGGERS: Final = frozenset(
    {
        "LINE_SEARCH_FAILED",
        "STAGNATION",
        "BOUND_BLOCKED",
        "BUDGET_EXHAUSTED",
        "PTC_STALLED",
        "ACTIVE_SET_CYCLING",
        "ATTEMPTS_EXHAUSTED",
    }
)

#: §5.1: the budgets whose exhaustion is a globalization failure (Newton's iterations, PTC's
#: pseudo-steps). `property_calls` is not one: there is nothing left to spend.
EO_RECOVERY_BUDGETS: Final = frozenset({"newton_iterations", "ptc_steps"})


def eo_recovery_due(outcome: str, budget: str | None) -> bool:
    """§5.1's trigger, decided in one place."""
    if outcome not in EO_RECOVERY_TRIGGERS:
        return False
    return outcome != "BUDGET_EXHAUSTED" or budget in EO_RECOVERY_BUDGETS


def recovered_provenance(
    failed: Sequence[Mapping[str, Any]],
    recovery: Sequence[Mapping[str, Any]],
    *,
    first_initializer_source: str | None = None,
) -> tuple[dict[str, Any], ...]:
    """§5.3: the recovery's attempts continue the failed solve's `branch_provenance` densely.

    The failed solve's items are kept as they are — its last item already says how it ended. The
    recovery's first item opened as edge 3's recovery (`eo_recovery_start`) and names its
    initializer source: the homotopy's is item 0's (`first_initializer_source` is `None`), the
    sequential restart's is its own initializer (ADR 0015 D3, `traversal-G0-pass8-v1`). The
    region solve writes both, and they are checked here."""
    items = [dict(item) for item in failed]
    offset = len(items)
    for position, item in enumerate(recovery):
        continued = {**item, "attempt": offset + int(item["attempt"])}
        if position == 0:
            if first_initializer_source is None:
                misnamed = bool(items) and (
                    continued["initializer_source"] != items[0]["initializer_source"]
                )
            else:
                misnamed = continued["initializer_source"] != first_initializer_source
            if continued["opening_source"] != "eo_recovery_start" or misnamed:
                raise ValueError(
                    "defect: a recovery's first attempt opens at the failed solve's item-0 "
                    "state or at the restart initializer's, and this one names "
                    f"{continued['opening_source']!r} / {continued['initializer_source']!r}"
                )
        items.append(continued)
    return tuple(items)
