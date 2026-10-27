"""S11 WO-B3d/B3e: the column solved in a flowsheet (design note §4.7.5, §6.1, §10.8, §10.11).

S11.A28 (a column under a phase-contract-v1 policy is refused before the traversal). The column
is registered for the test only (`s11_column_support.column_registered`), as I1 has not
registered it yet.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from s11_column_support import column_registered, column_revision
from test_s02_column_wo1 import SPECS

from openflowsheet.application.policies import T04_W12, T06_REVISION_V2
from openflowsheet.application.revision_binding import RevisionBinding, bind_revision_flowsheet
from openflowsheet.orchestrator.execution import ExecutionPlan
from openflowsheet.orchestrator.executor import PlanResult, execute_plan
from openflowsheet.orchestrator.revision import plan_revision
from openflowsheet.orchestrator.trace import SolvePolicy

M1 = SPECS["M1"]


@pytest.fixture
def registered(monkeypatch: pytest.MonkeyPatch) -> Iterator[pytest.MonkeyPatch]:
    with column_registered(monkeypatch):
        yield monkeypatch


def _run(document: dict[str, object], policy: SolvePolicy) -> PlanResult:
    binding = bind_revision_flowsheet(document)
    assert isinstance(binding, RevisionBinding), binding
    plan, _ = plan_revision(binding, policy)
    assert isinstance(plan, ExecutionPlan), plan
    return execute_plan(plan=plan, flowsheet=binding.flowsheet, spec=binding.spec, policy=policy)


# -- S11.A28 ---------------------------------------------------------------------------------------


def test_a_column_under_a_v1_policy_is_capability_unavailable(
    registered: pytest.MonkeyPatch,
) -> None:
    """S11.A28: `CAPABILITY_UNAVAILABLE phase_contract_unsupported(syn001.column)`, before the
    traversal: no attempt is opened."""
    assert T04_W12.phase_contract == "T03-phase-contract-v1"
    run = _run(column_revision(M1), T04_W12)
    assert run.outcome == "CAPABILITY_UNAVAILABLE"
    (step,) = run.steps
    assert step.outcome == "CAPABILITY_UNAVAILABLE"
    assert step.message == "phase_contract_unsupported(syn001.column)"
    assert step.detail is None and run.counters.property_calls == 0


def test_the_same_column_under_the_revision_policy_converges(
    registered: pytest.MonkeyPatch,
) -> None:
    """A28's control: the application's revision policy carries phase contract v2."""
    assert T06_REVISION_V2.phase_contract == "T05b-phase-contract-v2"
    run = _run(column_revision(M1), T06_REVISION_V2)
    assert run.outcome == "CONVERGED", run.message
