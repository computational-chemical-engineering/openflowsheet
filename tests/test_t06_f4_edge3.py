"""T06 F4: recovery edge 3's second action, the sequential restart (ADR 0015 D1–D3).

Design note `docs/design/T06-F4-recovery.md` §5.2 (P0–P5), §5.4 (the action), §5.5 (records) and
§8's gates. WO4: the seams — `recovered_provenance(first_initializer_source=...)` checks the
restart's first item against its own initializer; `solve_region(item0_opening_source=...)`
defaults to today's constant (the registered traces are unchanged: G5a, measured outside the
suite and by every registered trace test). WO5: G1–G4-legacy, P4's records, and the count of
one.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass, replace
from functools import cache
from typing import Any

import pytest
import t05b_support as t05b
from t06_support import CORPUS, T06_REVISION_POLICY, case_document, registered_root, worst_ratio
from test_t05_coupled import POLICY as POLICY_W13

from openflowsheet.application.revision_binding import RevisionBinding, bind_revision_flowsheet
from openflowsheet.orchestrator import executor, region, revision
from openflowsheet.orchestrator.execution import ExecutionPlan
from openflowsheet.orchestrator.executor import PlanResult, StepResult, execute_plan
from openflowsheet.orchestrator.recovery import recovered_provenance
from openflowsheet.orchestrator.revision import INITIALIZER_ID, RESTART_INITIALIZER_ID
from openflowsheet.orchestrator.trace import SolvePolicy
from openflowsheet.verify.certificate import verify_revision

RESTART = "homotopy_or_sequential_restart"
NET02 = "SYN-001-T06-NET02"
#: `T05-W13` with the new value: G1's contract-independence twin, G3's policy.
W13_RESTART = replace(
    POLICY_W13, globalization=replace(POLICY_W13.globalization, eo_recovery=RESTART)
)

# ------------------------------------------------------------------ WO4: the seams


def test_wo4_the_restart_provenance_names_the_restart_initializer() -> None:
    failed = (
        {"attempt": 0, "opening_source": "initializer", "initializer_source": INITIALIZER_ID},
    )
    restart = (
        {
            "attempt": 0,
            "opening_source": "eo_recovery_start",
            "initializer_source": RESTART_INITIALIZER_ID,
        },
        {"attempt": 1, "opening_source": "closure_projection", "initializer_source": None},
    )
    items = recovered_provenance(failed, restart, first_initializer_source=RESTART_INITIALIZER_ID)
    assert [item["attempt"] for item in items] == [0, 1, 2]
    assert [item["initializer_source"] for item in items] == [
        INITIALIZER_ID,
        RESTART_INITIALIZER_ID,
        None,
    ]
    # Without the keyword the homotopy's rule holds: the first item names item 0's source.
    with pytest.raises(ValueError, match="item-0 state"):
        recovered_provenance(failed, restart)
    with pytest.raises(ValueError, match="item-0 state"):
        recovered_provenance(
            failed,
            ({**restart[0], "initializer_source": INITIALIZER_ID},),
            first_initializer_source=RESTART_INITIALIZER_ID,
        )
    with pytest.raises(ValueError, match="item-0 state"):
        recovered_provenance(
            failed,
            ({**restart[0], "opening_source": "initializer"},),
            first_initializer_source=RESTART_INITIALIZER_ID,
        )


def test_wo4_the_opening_source_keyword_defaults_to_the_registered_constant() -> None:
    for function in (region.solve_region, executor._region):
        parameter = inspect.signature(function).parameters["item0_opening_source"]
        assert parameter.default == "initializer"
    assert inspect.signature(region.solve_region).parameters["item0_opening_source"].kind == (
        inspect.Parameter.KEYWORD_ONLY
    )


# ------------------------------------------------------------------ WO5: P0–P5 and the action


@dataclass(frozen=True)
class Solved:
    document: dict[str, Any]
    binding: RevisionBinding
    plan: ExecutionPlan
    run: PlanResult

    @property
    def step(self) -> StepResult:
        (step,) = [step for step in self.run.steps if step.kind == "solve_eo"]
        return step


def solve(document: dict[str, Any], policy: SolvePolicy) -> Solved:
    binding = bind_revision_flowsheet(document)
    assert isinstance(binding, RevisionBinding), binding
    plan, _ = revision.plan_revision(binding, policy)
    assert isinstance(plan, ExecutionPlan), plan
    run = execute_plan(plan=plan, flowsheet=binding.flowsheet, spec=binding.spec, policy=policy)
    return Solved(document, binding, plan, run)


_NET02_POLICIES = {
    "T06-revision-v2": T06_REVISION_POLICY,
    "T05-W13+restart": W13_RESTART,
    "T05b-v2": t05b.POLICY_V2,
    "T05-W13": POLICY_W13,
}


@cache
def net02(label: str) -> Solved:
    return solve(case_document(NET02), _NET02_POLICIES[label])


def _items(step: StepResult) -> list[tuple[Any, ...]]:
    return [
        (
            item["attempt"],
            item["opening_source"],
            item["initializer_source"],
            item["core"],
            item["core_outcome"],
        )
        for item in step.detail.branch_provenance
    ]


@pytest.mark.parametrize("label", ["T06-revision-v2", "T05-W13+restart"])
def test_g1_net02_is_solved_through_the_restart_and_certified(label: str) -> None:
    """G1: `CONVERGED` through edge 3's restart, `VERIFIED`, within T02 §6.4's allowances of the
    twin root, under the T06 policy and its `T05-W13` twin (contract independence)."""
    solved = net02(label)
    step, run = solved.step, solved.run
    assert run.outcome == step.outcome == "CONVERGED"
    assert (step.eo_recovery, step.eo_recovery_unsupported) == ("taken", None)
    failed = step.recovered_from
    assert failed.outcome == "BOUND_BLOCKED"
    assert step.iterations == failed.iterations + step.detail.iterations
    assert _items(step) == [
        (0, "initializer", INITIALIZER_ID, "newton", "BOUND_BLOCKED"),
        (1, "eo_recovery_start", RESTART_INITIALIZER_ID, "newton", "CONVERGED"),
    ]
    assert step.detail.branch_provenance[1]["continuation"] is None
    assert not run.trace.of_kind("homotopy_step")
    assert not run.trace.of_kind("initializer_rejected")
    (closed,) = run.trace.of_kind("region_closed")
    assert closed.as_document()["eo_recovery"] == "taken"
    assert closed.as_document().get("eo_recovery_unsupported") is None
    certificate = verify_revision(
        solved.binding, solved.document, run, solve_plan=solved.plan.steps[-1].solve_plan
    )
    assert certificate.verification_status == "VERIFIED"
    ratio, column = worst_ratio(step.detail.state, registered_root(CORPUS[NET02]))
    assert ratio <= 1.0, (ratio, column)


@pytest.mark.parametrize("label", ["T05b-v2", "T05-W13"])
def test_g2_the_edge_off_control_is_unchanged(label: str) -> None:
    """G2: under the registered policies NET-02 stays `BOUND_BLOCKED`, recorded
    `unsupported(no_continuation_parameter)` (its trace is byte-identical to 16be834's: G5a)."""
    solved = net02(label)
    step = solved.step
    assert solved.run.outcome == step.outcome == "BOUND_BLOCKED"
    assert (step.eo_recovery, step.eo_recovery_unsupported) == (
        "unsupported",
        "no_continuation_parameter",
    )
    assert step.recovered_from is None
    assert _items(step) == [(0, "initializer", INITIALIZER_ID, "newton", "BOUND_BLOCKED")]


def _events(run: PlanResult) -> list[dict[str, Any]]:
    return [event.as_document() for event in run.trace.events]


@pytest.mark.parametrize("case", ["SC-1", "SC-2", "SC-3"])
def test_g3_an_acyclic_registered_start_is_the_restart_start(case: str) -> None:
    """G3 (P5): the restart start of an acyclic flowsheet is `traversal-G0-v1`'s, so the
    registered `T05-W13` outcome stands, recorded `unsupported(restart_start_unchanged)`; the
    trace is otherwise `T05-W13`'s."""
    build = t05b.SINGLE_COMPONENT_CASES[case]
    registered = solve(build(), POLICY_W13)
    restarted = solve(build(), W13_RESTART)
    assert registered.run.outcome == restarted.run.outcome == "ACTIVE_SET_CYCLING"
    assert (registered.step.eo_recovery_unsupported, restarted.step.eo_recovery_unsupported) == (
        "no_continuation_parameter",
        "restart_start_unchanged",
    )
    assert restarted.step.eo_recovery == "unsupported"
    before, after = _events(registered.run), _events(restarted.run)
    assert len(before) == len(after)
    differing = [
        (a["kind"], key)
        for a, b in zip(before, after, strict=True)
        for key in sorted(set(a) | set(b))
        if a.get(key) != b.get(key)
    ]
    assert differing == [("region_closed", "eo_recovery_unsupported")]
    assert restarted.step.detail.branch_provenance == registered.step.detail.branch_provenance


def test_g4_legacy_a_syn001_region_has_no_restart_initializer() -> None:
    """G4-legacy (P3): T04's HOM-U with the new value — `BUDGET_EXHAUSTED(newton_iterations)`
    stands, recorded `unsupported(no_restart_initializer)`."""
    from test_t02_executor import nominal, policy
    from test_t04_edge3 import region_step

    registered = replace(policy("eo"), max_iterations_per_attempt=1)
    solve_policy = replace(
        registered, globalization=replace(registered.globalization, eo_recovery=RESTART)
    )
    result = nominal(solve_policy).result
    step = region_step(result)
    assert result.outcome == step.outcome == "BUDGET_EXHAUSTED"
    assert step.detail.budget == "newton_iterations"
    assert (step.eo_recovery, step.eo_recovery_unsupported) == (
        "unsupported",
        "no_restart_initializer",
    )
    (closed,) = result.trace.of_kind("region_closed")[-1:]
    assert closed.as_document()["eo_recovery_unsupported"] == "no_restart_initializer"
    assert not result.trace.of_kind("homotopy_step")
    assert not result.trace.of_kind("initializer_rejected")


def _messages(run: PlanResult, kind: str) -> list[str]:
    return [event.message for event in run.trace.of_kind(kind)]


def test_p4_a_refused_restart_initializer_is_recorded_and_the_failure_stands(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """P4: the restart initializer refused — one `initializer_rejected` event, then
    `unsupported(restart_initializer_failed)`; the failed outcome stands."""
    refused = revision.InitialStateFailure("U-MIX", "not_converged_probe")
    monkeypatch.setattr(revision, "restart_start", lambda *_: refused)
    solved = solve(case_document(NET02), T06_REVISION_POLICY)
    assert solved.run.outcome == solved.step.outcome == "BOUND_BLOCKED"
    assert (solved.step.eo_recovery, solved.step.eo_recovery_unsupported) == (
        "unsupported",
        "restart_initializer_failed",
    )
    assert _messages(solved.run, "initializer_rejected") == [
        "restart_initializer_failed: initializer_failed(U-MIX): not_converged_probe"
    ]
    kinds = [event.kind for event in solved.run.trace.events]
    assert kinds.index("initializer_rejected") < kinds.index("region_closed")


def test_p4_p5_rejected_passes_are_recorded_before_p5_decides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """§5.2: each rejected pass is recorded, whatever P5 decides — here a sequence truncated to
    two passes, which is `traversal-G0-v1`'s start: `unsupported(restart_start_unchanged)`."""
    real = revision.restart_start

    def truncated(flowsheet: Any, variable_ids: Any) -> revision.RestartStart:
        start = real(flowsheet, variable_ids)
        assert isinstance(start, revision.RestartStart)
        rejected = ((3, "U-MIX", "not_converged", "liquid enthalpy: probe"),)
        return replace(start, passes_used=2, rejected=rejected)

    monkeypatch.setattr(revision, "restart_start", truncated)
    solved = solve(case_document(NET02), T06_REVISION_POLICY)
    assert solved.step.outcome == "BOUND_BLOCKED"
    assert solved.step.eo_recovery_unsupported == "restart_start_unchanged"
    assert _messages(solved.run, "initializer_rejected") == [
        "restart_pass_rejected(3): U-MIX: liquid enthalpy: probe"
    ]


def test_the_restart_is_never_itself_recovered(monkeypatch: pytest.MonkeyPatch) -> None:
    """§5.4: the outcome is the restart's; a restart that fails again is not recovered (the count
    of one). Here the restart start is made `traversal-G0-v1`'s own values under the 8-pass id,
    so the restart fails as item 0 did."""

    def same_values(flowsheet: Any, variable_ids: Any) -> revision.RestartStart:
        start = revision.traversal_start(flowsheet, variable_ids)
        assert isinstance(start, revision.TraversalStart)
        return revision.RestartStart(start.values, start.band_routes, 8, ())

    monkeypatch.setattr(revision, "restart_start", same_values)
    solved = solve(case_document(NET02), T06_REVISION_POLICY)
    step = solved.step
    assert solved.run.outcome == step.outcome == "BOUND_BLOCKED"
    assert (step.eo_recovery, step.eo_recovery_unsupported) == ("taken", None)
    assert _items(step) == [
        (0, "initializer", INITIALIZER_ID, "newton", "BOUND_BLOCKED"),
        (1, "eo_recovery_start", RESTART_INITIALIZER_ID, "newton", "BOUND_BLOCKED"),
    ]
    assert len(solved.run.trace.of_kind("region_closed")) == 1
