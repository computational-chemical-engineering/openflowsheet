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
`LINEAR_SOLVE_FAILED` has its own row in blueprint §7.7 and is not a trigger when it ends attempt 0
(the signature the homotopy would run in); it is one when the failed solve ran two or more attempts
and its attempt 0 ended in a core globalization failure (`EO_CORE_FAILURES`; ADR 0044 D1 as
narrowed, S02 spec §19 item 1, R-550): its final attempt was then opened by a contract restart
after a globalization failure, the same conversion as above, and says nothing about item 0's
signature. After a `CONVERGED` attempt 0 the restart is a physical correction, item 0's signature
is known wrong, and the rank reason applies unchanged. The defects, the refusals
before any attempt, a spent property budget and `HOMOTOPY_STALLED` itself are not triggers — the
last so that the edge cannot recurse.

The edge changes the *solver*, not the *problem*: the recovery's λ = 1 instance has the failed
solve's `(model_version, constants_sha256)` and the region's rows and columns (§5.4).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Final

__all__ = [
    "EO_CORE_FAILURES",
    "EO_RECOVERY_TRIGGERS",
    "eo_recovery_due",
    "recovered_provenance",
    "solver_outcomes",
]

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


#: ADR 0044 D1 as narrowed (R-550): the solver outcomes of a failed solve's attempt 0 after which a
#: closing `LINEAR_SOLVE_FAILED` is due — the core globalization failures. `BUDGET_EXHAUSTED` here
#: is a core budget's: the property budget closes the solve (T03 §4.8 row 5 restarts only on
#: `EO_RECOVERY_BUDGETS`), so it never ends an attempt 0 that a further attempt follows.
EO_CORE_FAILURES: Final = frozenset(
    {"LINE_SEARCH_FAILED", "STAGNATION", "BOUND_BLOCKED", "PTC_STALLED", "BUDGET_EXHAUSTED"}
)


def eo_recovery_due(outcome: str, budget: str | None, *, attempts: Sequence[str]) -> bool:
    """§5.1's trigger, decided in one place. `attempts` is the failed region solve's attempts'
    solver outcomes, in order: `LINEAR_SOLVE_FAILED` is due iff there are two or more and attempt
    0's is in `EO_CORE_FAILURES` (ADR 0044 D1 as narrowed, R-550)."""
    if outcome == "LINEAR_SOLVE_FAILED":
        return len(attempts) >= 2 and attempts[0] in EO_CORE_FAILURES
    if outcome not in EO_RECOVERY_TRIGGERS:
        return False
    return outcome != "BUDGET_EXHAUSTED" or budget in EO_RECOVERY_BUDGETS


def solver_outcomes(attempts: Sequence[Any]) -> tuple[str, ...]:
    """What each attempt's core ended on (`RegionAttempt.solver_outcome`), in attempt order — the
    `attempts` that `eo_recovery_due`'s call sites pass. An attempt that records none reads `""`,
    which is no core failure."""
    return tuple("" if a.solver_outcome is None else str(a.solver_outcome) for a in attempts)


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
