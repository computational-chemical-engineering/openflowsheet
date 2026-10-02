"""T08.A11 (D2): bundles and certificates carry the ids of the plan and policy the run used.

T08 release spec §6.1 D2, §9 A11. `bundle_for` read `getattr(result, "plan")`, which a region
result view does not have, so every region failure bundle had an empty-string `replay_identity`;
and neither object a revision-route verifier is handed carries a plan, so revision-path
certificates had empty `policy_id` and `plan_id`. Each id is now compared, not merely found
non-empty, with the run's own records: the trace's `plan_built` (it carries the `ExecutionPlan`'s
`plan_id`), the `ExecutionPlan` the route built, and the `SolvePolicy` it ran under — so junk cannot
pass.

States: (a) a region failure bundle, NET-02 under `T05b-v2` (`BOUND_BLOCKED`, T06 A63); (b) a
revision-path `VERIFIED` certificate on each route, T05's C1 (`revision_eo`) and SYN-001-A02-360
(`legacy_eo`); (c) the tear path's `SYN-001-capped-budget` bundle, the control, unchanged: its K03
solve spends its cap before any plan is built, so its replay identity was and stays empty.
"""

from __future__ import annotations

import sys
from typing import Any

import pytest
from conftest import REPO_ROOT
from t07_corpus import CORPUS

from openflowsheet.application.policies import DEFAULT_POLICY_ID, T05B_V2, resolve_policy
from openflowsheet.application.revision_run import Route, RouteRun, select_route, solve_route
from openflowsheet.orchestrator.execution import ExecutionPlan
from openflowsheet.orchestrator.tear import solve_tear
from openflowsheet.orchestrator.trace import SolvePolicy
from openflowsheet.verify.certificate import CheckPolicy
from openflowsheet.verify.failure import bundle_for


def _solved(name: str, policy: SolvePolicy | None = None) -> tuple[RouteRun, SolvePolicy]:
    document = CORPUS[name]()
    route = select_route(document)
    assert isinstance(route, Route)
    used = policy or resolve_policy(DEFAULT_POLICY_ID, route.solve_path)
    assert used is not None
    return solve_route(route, document, policy=used, check_policy=CheckPolicy()), used


def _records(result: RouteRun, policy: SolvePolicy) -> dict[str, Any]:
    """The run's own ids: the trace's `plan_built` and the plan and policy it ran."""
    assert isinstance(result.plan, ExecutionPlan) and result.run is not None
    opening = result.run.trace.events[0]
    assert opening.kind == "plan_built"
    assert opening.message == result.plan.plan_id
    assert result.plan.policy_id == policy.policy_id
    return {
        "model_version": result.plan.model_version,
        "constants_sha256": result.plan.constants_sha256,
        "policy_id": policy.policy_id,
        "plan_id": opening.message,
    }


def test_a11_a_region_failure_bundle_names_the_run() -> None:
    result, policy = _solved("SYN-001-T06-NET02", T05B_V2)
    assert result.failure is not None and result.failure.outcome == "BOUND_BLOCKED"
    records = _records(result, policy)
    assert all(records.values())
    assert dict(result.failure.replay_identity) == records


@pytest.mark.parametrize(
    ("name", "solve_path"), [("SYN-001-UL-C1", "revision_eo"), ("SYN-001-A02-360", "legacy_eo")]
)
def test_a11_a_revision_certificate_names_the_run(name: str, solve_path: str) -> None:
    result, policy = _solved(name)
    assert result.route.solve_path == solve_path
    certificate = result.certificate
    assert certificate is not None and certificate.verification_status == "VERIFIED"
    records = _records(result, policy)
    assert certificate.policy_id == records["policy_id"] != ""
    assert certificate.plan_id == records["plan_id"] != ""
    # The declaration the certificate judged is the one the plan was built on.
    assert certificate.model_version == records["model_version"]
    assert certificate.constants_sha256 == records["constants_sha256"]


def test_a11_the_tear_path_bundle_is_the_control() -> None:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from k03_schema_fixtures import flowsheet

    policy = SolvePolicy(
        policy_id="SYN-001-capped", residual_tolerances={}, scales={}, max_property_calls=20
    )
    result, trace = solve_tear(flowsheet(), policy=policy)
    assert result.plan is None
    assert [event.kind for event in trace.events] == ["solve_closed"]
    bundle = bundle_for(result, trace)
    assert dict(bundle.replay_identity) == dict.fromkeys(
        ("model_version", "constants_sha256", "policy_id", "plan_id"), ""
    )
