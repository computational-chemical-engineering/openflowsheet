"""S02 WO-2b — the bubble-point easy endpoint and ADR 0044's trigger: spec §18.6.

Expectations are values of `docs/derivations/scripts/s02_reference.json` (the design lane's
50-digit generator: `cases.*.bubble_point`, `.bubble_point_continued`,
`variants.*.*.bubble_point`, `variants.M2.duty+duty.second_root`), codes and rules of
`docs/derivations/S02-spec.md` §18 and ADR 0044, or arithmetic done here. Each test names the
assertion of §18.6 it closes.
"""

from __future__ import annotations

from typing import get_args

from openflowsheet.orchestrator.recovery import EO_RECOVERY_TRIGGERS, eo_recovery_due
from openflowsheet.orchestrator.region import SolveOutcome

# -- A20: ADR 0044's trigger ---------------------------------------------------------------------


def test_a20_the_trigger_table() -> None:
    """A20: every ADR 0010 D3 trigger is due whatever the attempt count; `LINEAR_SOLVE_FAILED` is
    due iff the failed solve ran two or more attempts; every other outcome is never due."""
    budgets = {"BUDGET_EXHAUSTED": "newton_iterations"}
    for outcome in get_args(SolveOutcome):
        for attempts in (1, 2, 3, 7):
            due = eo_recovery_due(outcome, budgets.get(outcome), attempts)
            if outcome in EO_RECOVERY_TRIGGERS:
                assert due, (outcome, attempts)
            elif outcome == "LINEAR_SOLVE_FAILED":
                assert due == (attempts >= 2), attempts
            else:
                assert not due, (outcome, attempts)
    assert not eo_recovery_due("LINEAR_SOLVE_FAILED", None)
    assert not eo_recovery_due("LINEAR_SOLVE_FAILED", None, 1)
    assert eo_recovery_due("LINEAR_SOLVE_FAILED", None, 2)
    assert not eo_recovery_due("BUDGET_EXHAUSTED", "property_calls", 3)
    assert "LINEAR_SOLVE_FAILED" not in EO_RECOVERY_TRIGGERS
