"""T06 W24 (review M1): ADR 0018 D4′ at the plan level — the refinement spends the solve's
property budget like any iteration (spec A96).

The refinement never changes an *attempt's* outcome (D4), but its calls are metered, so under a
property budget a solve whose `newton` run converges can end `BUDGET_EXHAUSTED(property_calls)`
under `newton_refined`: once the refinement has spent the budget, the region's closure at `x_k`
cannot be evaluated. The attempt keeps the core's word for the refused kernel call,
`abandoned: EVALUATION_ERROR` (D5′); the step carries the cause.

THM-09 start 1 of the published nominal starts, through `execute_plan` with `user_start` (the
harness's injection point), under `T06-revision-v2` and under the same policy document with
`globalization.eo_core = "newton"` — nothing else differs. Every cap is measured here from the
uncapped runs: `N₀` (`newton`'s calls) and `N₁` (`newton_refined`'s). *Measured (A5)* on
`ref-x86-64`: `N₀ = 365`, `N₁ = 386`.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import replace
from functools import cache
from typing import Literal

import pytest
from t06_ensemble_support import STARTS_FILE, ensemble_cases

from openflowsheet.application.revision_binding import RevisionBinding, bind_revision_flowsheet
from openflowsheet.orchestrator import revision
from openflowsheet.orchestrator.execution import ExecutionPlan
from openflowsheet.orchestrator.executor import PlanResult, execute_plan
from openflowsheet.orchestrator.region import RegionResult
from openflowsheet.orchestrator.trace import SolvePolicy

CASE, START = "THM-09", 1

Core = Literal["newton", "newton_refined"]

ABANDONED = re.compile(
    r"^terminal_refinement\(abandoned: EVALUATION_ERROR\): chord \S+ at S[34]\.T$"
)
ACCEPTED = re.compile(r"^terminal_refinement\(accepted: ")


def _policy(core: Core, cap: int | None = None) -> SolvePolicy:
    (entry,) = [c for c in ensemble_cases() if c.case == CASE]
    registered = entry.policy
    assert registered.policy_id == "T06-revision-v2"
    assert registered.globalization.eo_core == "newton_refined"
    policy = replace(registered, globalization=replace(registered.globalization, eo_core=core))
    return policy if cap is None else replace(policy, max_property_calls=cap)


@cache
def _solve(core: Core, cap: int | None = None) -> PlanResult:
    (entry,) = [c for c in ensemble_cases() if c.case == CASE]
    published = json.loads(STARTS_FILE.read_bytes())
    (starts,) = [e for e in published["cases"] if e["case"] == CASE]
    (start,) = [s for s in starts["starts"] if s["start"] == START]
    vector = {name: float(value) for name, value in start["vector"].items()}
    policy = _policy(core, cap)
    binding = bind_revision_flowsheet(entry.document())
    assert isinstance(binding, RevisionBinding), binding
    plan, _ = revision.plan_revision(binding, policy)
    assert isinstance(plan, ExecutionPlan), plan
    return execute_plan(
        plan=plan,
        flowsheet=binding.flowsheet,
        spec=binding.spec,
        policy=policy,
        user_start=vector,
    )


def _region(result: PlanResult) -> RegionResult:
    (step,) = [step for step in result.steps if step.kind == "solve_eo"]
    assert isinstance(step.detail, RegionResult)
    return step.detail


def _refinements(result: PlanResult) -> list[tuple[str, str]]:
    """`(outcome, first line)` of every attempt closing whose message names ADR 0018's rule."""
    return [
        (str(event.outcome), event.message.splitlines()[0])
        for event in result.trace.of_kind("attempt_closed")
        if event.message and event.message.startswith("terminal_refinement(")
    ]


def _n0() -> int:
    result = _solve("newton")
    assert result.outcome == "CONVERGED", result.message
    return result.counters.property_calls


def _n1() -> int:
    result = _solve("newton_refined")
    assert result.outcome == "CONVERGED", result.message
    return result.counters.property_calls


def test_a96_uncapped_the_refinement_is_metered() -> None:
    """Uncapped: both converge; the refined run's one refinement is accepted, and its calls are
    charged (`N₁ > N₀`); `newton` fires none."""
    n0, n1 = _n0(), _n1()
    assert n1 > n0, (n0, n1)
    (closing,) = _refinements(_solve("newton_refined"))
    assert closing[0] == "CONVERGED" and ACCEPTED.match(closing[1]), closing
    assert _refinements(_solve("newton")) == []


#: A96 (a) `N₀` and (b) `N₁ − 1`, with the two caps between them the ruling also measured.
CAPS: dict[str, Callable[[int, int], int]] = {
    "N0": lambda n0, n1: n0,
    "N0+1": lambda n0, n1: n0 + 1,
    "mid": lambda n0, n1: (n0 + n1) // 2,
    "N1-1": lambda n0, n1: n1 - 1,
}


@pytest.mark.parametrize("which", sorted(CAPS))
def test_a96_ab_a_cap_below_the_refineds_total_exhausts_the_budget(which: str) -> None:
    """(a)/(b): at a cap in `[N₀, N₁ − 1]`, `newton` converges in `N₀` calls, and `newton_refined`
    ends `BUDGET_EXHAUSTED(property_calls)` with exactly the cap charged (A93), the meter's
    message, and the attempt that converged closing with its refinement abandoned."""
    n0, n1 = _n0(), _n1()
    cap = CAPS[which](n0, n1)
    assert n0 <= cap < n1, (n0, cap, n1)

    plain = _solve("newton", cap)
    assert plain.outcome == "CONVERGED", plain.message
    assert plain.counters.property_calls == n0

    refined = _solve("newton_refined", cap)
    assert refined.outcome == "BUDGET_EXHAUSTED", refined.message
    region = _region(refined)
    assert region.outcome == "BUDGET_EXHAUSTED"
    assert region.budget == "property_calls"
    assert refined.counters.property_calls == cap
    assert refined.message.splitlines()[0].startswith(f"the property-call budget of {cap} is spent")
    assert [a.outcome for a in region.attempts].count("CONVERGED") == 1
    (closing,) = _refinements(refined)
    assert closing[0] == "CONVERGED" and ABANDONED.match(closing[1]), closing


def test_a96_c_at_the_refineds_total_it_converges() -> None:
    """(c): at `N₁`, `newton_refined` converges in exactly `N₁` calls, the refinement accepted —
    a refinement charged twice would fail here."""
    n1 = _n1()
    refined = _solve("newton_refined", n1)
    assert refined.outcome == "CONVERGED", refined.message
    assert refined.counters.property_calls == n1
    (closing,) = _refinements(refined)
    assert closing[0] == "CONVERGED" and ACCEPTED.match(closing[1]), closing
