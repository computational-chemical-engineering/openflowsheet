"""K03 §11.2 and assertion A15: the property-call budget, enforced at the provider boundary.

The Fable review of K03 found this unimplemented: `max_property_calls` was a field of
`SolvePolicy` that nothing read, and `property_calls`, `requested_evaluations` and `cache_hits`
were fields of `Counters` that nothing wrote — so every event in every trace carried three
zeros, and a reader could not tell "no properties were evaluated" from "nobody counted".

Two things are tested that are easy to get almost right. The count on exhaustion must be
*exactly* the cap, which needs the guard to refuse the call rather than notice afterwards that
it made it. And the wrapping must be invisible to identity: the guard and the cache both pass
`describe()` through unchanged, so the flowsheet label — and therefore `model_version`, and
therefore every hash downstream of it — must be bit-for-bit what it was without them.
"""

from __future__ import annotations

from typing import Any

import pytest

from openflowsheet.compiled import EvaluationContext
from openflowsheet.models.syn001.flowsheet import Syn001Flowsheet
from openflowsheet.orchestrator.budget import BudgetedProvider, BudgetExhaustedError
from openflowsheet.orchestrator.tear import solve_tear
from openflowsheet.orchestrator.trace import SolvePolicy
from openflowsheet.thermo.cache import ExactPropertyCache
from openflowsheet.thermo.syn001 import Syn001Provider

CONTEXT = EvaluationContext(model_version="K03-budget@" + "0" * 64, constants_sha256="0" * 64)


def flowsheet() -> Syn001Flowsheet:
    return Syn001Flowsheet(provider=Syn001Provider(), context=CONTEXT)


def policy(cap: int) -> SolvePolicy:
    return SolvePolicy(
        policy_id="SYN-001-capped", residual_tolerances={}, scales={}, max_property_calls=cap
    )


def test_a15_the_count_on_exhaustion_is_exactly_the_cap() -> None:
    """A15: `BUDGET_EXHAUSTED`, `counters.property_calls == 20`, zero accepted iterations.

    Exactly the cap, not one more. The guard refuses the call that would exceed it; a guard
    that checked after the call would read 21, and so would a count taken from the exact
    cache, which increments before it calls the provider.
    """
    result, trace = solve_tear(flowsheet(), policy=policy(20))

    assert result.outcome == "BUDGET_EXHAUSTED"
    assert result.counters.property_calls == 20
    assert result.iterations == 0
    assert result.checkpoint is None, "nothing was accepted, so there is nothing to checkpoint"
    assert result.converged is False

    # The trace closes rather than simply stopping: a solve with no `solve_closed` is one a
    # reader cannot distinguish from a solve still running.
    assert [event.kind for event in trace.events] == ["solve_closed"]
    assert trace.events[-1].outcome == "BUDGET_EXHAUSTED"
    assert "property-call budget of 20" in trace.events[-1].message
    assert result.plan is None, "no plan was built, and a plan_built event would say one was"


def test_a_budget_large_enough_changes_nothing_about_the_answer() -> None:
    """The budget must be inert when it is not binding, including bit-for-bit in the answer."""
    generous, _ = solve_tear(flowsheet(), policy=policy(1_000_000))
    default, _ = solve_tear(flowsheet())
    assert generous.outcome == default.outcome == "CONVERGED"
    assert [value.hex() for value in generous.x] == [value.hex() for value in default.x]


def test_the_counters_are_written_and_are_not_all_the_same_number() -> None:
    """Three separate quantities, per blueprint §6.4, not one cost folded three ways."""
    result, trace = solve_tear(flowsheet())
    counters = result.counters
    assert counters.property_calls > 0
    assert counters.cache_hits > 0
    assert counters.requested_evaluations == counters.cache_hits + counters.property_calls, (
        "requests are hits plus misses, and every miss reached the provider on this path"
    )
    assert counters.property_calls < counters.requested_evaluations, "the cache did something"

    # Cumulative on every event, and never decreasing (§11.2).
    seen = [event.counters.property_calls for event in trace.events]
    assert seen == sorted(seen)
    assert seen[-1] == counters.property_calls


def test_the_budget_wrapping_is_invisible_to_model_identity() -> None:
    """ADR 0002: `model_version` is `<label>@<structure_sha256>`, and the label names the
    provider. A guard or a cache that changed it would silently fork every downstream hash.
    """
    bare = flowsheet()
    wrapped = Syn001Flowsheet(
        provider=ExactPropertyCache(BudgetedProvider(Syn001Provider(), 1_000_000)),
        context=CONTEXT,
    )
    assert wrapped.label == bare.label
    assert wrapped.spec().equation_ids == bare.spec().equation_ids

    solved, _ = solve_tear(bare)
    assert solved.plan is not None
    assert solved.plan.model_version.split("@")[0] == bare.label


def test_the_guard_refuses_rather_than_reports() -> None:
    """Directly, without a solve: the call that would exceed the cap does not happen."""
    provider = Syn001Provider()
    calls: list[str] = []

    class Counting:
        def describe(self) -> Any:
            return provider.describe()

        def evaluate_phase(self, request: Any, context: Any) -> Any:
            calls.append("evaluate_phase")
            return provider.evaluate_phase(request, context)

        def flash(self, request: Any, context: Any) -> Any:
            calls.append("flash")
            return provider.flash(request, context)

    guard = BudgetedProvider(Counting(), 0)
    assert guard.describe() == provider.describe(), "describing costs nothing"
    assert calls == []

    from openflowsheet.thermo import PropertyRequest, StreamState

    request = PropertyRequest(
        state=StreamState(n=(1.0, 1.0, 1.0), temperature=350.0, pressure=1e5),
        phase="LIQUID",
        properties=("h",),
    )
    with pytest.raises(BudgetExhaustedError) as raised:
        guard.evaluate_phase(request, CONTEXT)
    assert calls == [], "the refused call was not made"
    assert raised.value.budget == "property_calls"
    assert raised.value.cap == 0
    assert guard.calls == 0


def test_a_negative_budget_is_refused_rather_than_treated_as_zero() -> None:
    with pytest.raises(ValueError, match="must not be negative"):
        BudgetedProvider(Syn001Provider(), -1)
