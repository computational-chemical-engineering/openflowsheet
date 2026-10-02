"""T06 W6: `execute_plan`'s start-injection point (`user_start`, spec §6.2).

The ensemble's perturbed start enters a revision-built flowsheet's registered path at the one
point `initial_state`'s output enters it (`_solve_revision_region`'s region start), recorded
`user_guess` (T03 §8.1), with every recovery edge and fallback of the path unchanged. Unused, it
is inert: every registered trace is byte-identical (the inertness protocol and the trace-by-trace
comparison against the executor at `1f07cdc` are in `docs/t06-measurements.md`; the registered
traces themselves are pinned by T02–T06's own tests). Here: handed the registered initializer's
own start, the injected run is the registered run event for event and bit for bit, except that
item 0 names its source `user_guess` — which is also what lets ADR 0015's restart run after it
(P5 fires only on `traversal-G0-v1`).
"""

from __future__ import annotations

from typing import Any

import pytest
import yaml
from conftest import REPO_ROOT
from t06_support import T06_REVISION_POLICY

from openflowsheet.application.binding import Binding, bind_revision
from openflowsheet.application.revision_binding import RevisionBinding, bind_revision_flowsheet
from openflowsheet.orchestrator import revision
from openflowsheet.orchestrator.execution import ExecutionPlan
from openflowsheet.orchestrator.executor import PlanResult, execute_plan
from openflowsheet.orchestrator.region import RegionResult

CASES = {
    "SYN-001-UL-C1": REPO_ROOT / "benchmarks" / "t05" / "cases" / "SYN-001-UL-C1.yaml",
    "SYN-001-T06-NET02": REPO_ROOT / "benchmarks" / "t06" / "cases" / "SYN-001-T06-NET02.yaml",
}


def _bound(case: str) -> tuple[RevisionBinding, ExecutionPlan]:
    binding = bind_revision_flowsheet(yaml.safe_load(CASES[case].read_text("utf-8")))
    assert isinstance(binding, RevisionBinding)
    plan, _ = revision.plan_revision(binding, T06_REVISION_POLICY)
    assert isinstance(plan, ExecutionPlan)
    return binding, plan


def _run(case: str, user_start: dict[str, float] | None = None) -> PlanResult:
    binding, plan = _bound(case)
    return execute_plan(
        plan=plan,
        flowsheet=binding.flowsheet,
        spec=binding.spec,
        policy=T06_REVISION_POLICY,
        user_start=user_start,
    )


def _registered_start(case: str) -> dict[str, float]:
    binding, _ = _bound(case)
    start = revision.traversal_start(binding.flowsheet, binding.spec.variable_ids)
    assert isinstance(start, revision.TraversalStart) and start.band_routes == ()
    return dict(start.values)


def _events(run: PlanResult) -> list[dict[str, Any]]:
    return [event.as_document() for event in run.trace.events]


def _provenance(run: PlanResult) -> list[dict[str, Any]]:
    (step,) = [step for step in run.steps if step.kind == "solve_eo"]
    detail = step.detail
    assert isinstance(detail, RegionResult)
    return [dict(item) for item in detail.branch_provenance]


@pytest.mark.parametrize("case", sorted(CASES))
def test_the_registered_start_injected_is_the_registered_run_but_for_item_0s_source(
    case: str,
) -> None:
    registered = _run(case)
    injected = _run(case, _registered_start(case))
    assert injected.outcome == registered.outcome == "CONVERGED"
    assert _events(injected) == _events(registered)
    assert registered.state is not None and injected.state is not None
    assert {k: v.hex() for k, v in injected.state.items()} == {
        k: v.hex() for k, v in registered.state.items()
    }
    ours, theirs = _provenance(injected), _provenance(registered)
    assert theirs[0]["initializer_source"] == revision.INITIALIZER_ID
    assert ours[0]["initializer_source"] == "user_guess"
    assert [dict(item, initializer_source=None) for item in ours] == [
        dict(item, initializer_source=None) for item in theirs
    ]


def test_net02s_restart_runs_after_an_injected_start() -> None:
    """NET-02's registered start ends `BOUND_BLOCKED` and edge 3 restarts from
    `traversal-G0-pass8-v1`; injected as `user_guess`, the same restart runs (P5 does not fire)."""
    injected = _run("SYN-001-T06-NET02", _registered_start("SYN-001-T06-NET02"))
    (step,) = [step for step in injected.steps if step.kind == "solve_eo"]
    assert step.eo_recovery == "taken"
    assert step.recovered_from is not None and step.recovered_from.outcome == "BOUND_BLOCKED"
    sources = [item["initializer_source"] for item in _provenance(injected)]
    assert sources[0] == "user_guess" and revision.RESTART_INITIALIZER_ID in sources


def test_user_start_is_refused_on_a_syn001_flowsheet_and_on_other_columns() -> None:
    nominal = bind_revision(
        yaml.safe_load(
            (REPO_ROOT / "benchmarks" / "syn001" / "cases" / "SYN-001-nominal.yaml").read_text()
        )
    )
    assert isinstance(nominal, Binding)
    binding, plan = _bound("SYN-001-UL-C1")
    with pytest.raises(ValueError, match="user_start_unsupported"):
        execute_plan(
            plan=plan,
            flowsheet=nominal.flowsheet,
            spec=nominal.spec,
            policy=T06_REVISION_POLICY,
            user_start={"S1.T": 300.0},
        )
    start = _registered_start("SYN-001-UL-C1")
    start.pop("S2.T")
    with pytest.raises(ValueError, match="user_start_columns"):
        execute_plan(
            plan=plan,
            flowsheet=binding.flowsheet,
            spec=binding.spec,
            policy=T06_REVISION_POLICY,
            user_start=start,
        )
