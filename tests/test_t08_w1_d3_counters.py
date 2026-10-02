"""T08.A12 (D3): a failure bundle's counters are the run's own trace meter.

T08 release spec §6.1 D3, §9 A12. Isolated cause (W1.3): a region failure bundle read
`RegionResult.counters`, which holds only the last region solve's core counts. The property calls
are metered by the executor's `PropertyMeter` into the plan trace (`executor._region`'s `sample`)
and never reach a `RegionResult`, so `property_calls`, `requested_evaluations` and `cache_hits`
were 0; and a step's T02 §7.5 pre-solve and, after edge 3, its failed first solve are in the trace
but not in the recovery's result, so the core counts were short too. The bundle now reads what the
executor metered for the step, as the initializer's bundle already did.

States: (a) `SYN-001-A02-352-vapor-guess-410` (`legacy_eo`, `T04-W12`, `HOMOTOPY_STALLED` after edge
3, with a pre-solve); (b) NET-02 under `T05b-v2` (`BOUND_BLOCKED`, no homotopy; T06 A63's edge-off
control); (c) `SYN-001-capped-budget` on the tear path (the control, cap 20). Counts are compared
within one run only (ADR 0007 D5), and each state's meter is nonzero, so an accidental 0 fails.
"""

from __future__ import annotations

import sys
from typing import Any

import pytest
from conftest import REPO_ROOT
from t07_corpus import CORPUS

from openflowsheet.application.policies import DEFAULT_POLICY_ID, T05B_V2, resolve_policy
from openflowsheet.application.revision_run import Route, select_route, solve_route
from openflowsheet.orchestrator.tear import solve_tear
from openflowsheet.orchestrator.trace import SolvePolicy
from openflowsheet.verify.certificate import CheckPolicy
from openflowsheet.verify.failure import bundle_for, region_bundle

COUNTERS = (
    "property_calls",
    "requested_evaluations",
    "cache_hits",
    "residual_calls",
    "jacobian_calls",
    "factorizations",
)


def _meter(trace: Any) -> dict[str, int]:
    closing = trace.events[-1]
    assert closing.kind == "solve_closed"
    return {name: getattr(closing.counters, name) for name in COUNTERS}


@pytest.mark.parametrize(
    ("name", "policy_id", "outcome"),
    [
        ("SYN-001-A02-352-vapor-guess-410", DEFAULT_POLICY_ID, "HOMOTOPY_STALLED"),
        ("SYN-001-T06-NET02", "T05b-v2", "BOUND_BLOCKED"),
    ],
)
def test_a12_a_region_bundle_counts_what_the_run_metered(
    name: str, policy_id: str, outcome: str
) -> None:
    document = CORPUS[name]()
    route = select_route(document)
    assert isinstance(route, Route)
    policy = T05B_V2 if policy_id == "T05b-v2" else resolve_policy(policy_id, route.solve_path)
    assert policy is not None

    result = solve_route(route, document, policy=policy, check_policy=CheckPolicy())

    assert result.run is not None and result.failure is not None
    assert result.failure.outcome == outcome
    meter = _meter(result.run.trace)
    assert meter["property_calls"] > 0
    assert result.failure.observations["counters"] == meter
    # The failing step is the run's only metered one (the SYN-001 feed's `evaluate` spends none),
    # so the step's meter and the run's agree.
    (step,) = [s for s in result.run.steps if s.kind == "solve_eo"]
    events = [e for e in result.run.trace.events if e.step_index == step.index]
    assert events[0].kind == "region_opened"
    assert all(getattr(events[0].counters, n) == 0 for n in COUNTERS)


def test_a12_the_tear_path_bundle_is_the_control() -> None:
    """(c) `SYN-001-capped-budget`: the tear path's bundle already read its K03 result's counters,
    which are the trace's; it stays at the cap, `max_property_calls` = 20."""
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from k03_schema_fixtures import flowsheet

    policy = SolvePolicy(
        policy_id="SYN-001-capped", residual_tolerances={}, scales={}, max_property_calls=20
    )
    result, trace = solve_tear(flowsheet(), policy=policy)
    bundle = bundle_for(result, trace)

    assert bundle.outcome == "BUDGET_EXHAUSTED"
    assert bundle.observations["counters"] == _meter(trace)
    assert bundle.observations["counters"]["property_calls"] == 20


def test_a_plan_trace_region_bundle_needs_its_step_index() -> None:
    """Review S7: `step_index` is required, and a plan trace without it is refused rather than
    bundled with `RegionResult.counters`' false zero (D3). `None` stays for a region solve's own
    trace, outside a plan (T04's standalone bundles, `test_t04_schemas`)."""
    document = CORPUS["SYN-001-T06-NET02"]()
    route = select_route(document)
    assert isinstance(route, Route)
    result = solve_route(route, document, policy=T05B_V2, check_policy=CheckPolicy())
    assert result.run is not None and result.failure is not None
    (step,) = [s for s in result.run.steps if s.kind == "solve_eo"]
    with pytest.raises(TypeError):
        region_bundle(step.detail, result.run.trace)  # type: ignore[call-arg]
    with pytest.raises(ValueError, match="step_index"):
        region_bundle(step.detail, result.run.trace, step_index=None)
    bundle = region_bundle(step.detail, result.run.trace, step_index=step.index)
    assert bundle.observations["counters"] == _meter(result.run.trace)
