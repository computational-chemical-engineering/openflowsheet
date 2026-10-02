"""T05b's part of the cross-platform identity (spec B22), included by `k05_structural_identity.py`.

`docs/derivations/T05b-limitations-spec.md` B22, per case under the policy `T05b-v2`
(`t05b_support.POLICY_V2`, spec §6.6):

- the full R0 projection — as `t05_identity.py` builds it: the execution plan's R0 projection
  (`execution_plan_r0`, T02 A02), the outcome, `r0_projection` of the solve events, the structural
  report and, when the run converged, the certificate `verify_revision` issues on it, the root
  fingerprint through T03's projection (`t03_identity._fingerprint`), and the typed message's
  first line (`""` when there is none) — of SC-1…SC-4, NP-1…NP-3, DZ-1…DZ-5, DZ-6…DZ-10 and DZ-12;
- the outcome and the message's first line of DZ-11 and DZ-2C (`SPECIFICATION_CONFLICT`, no
  certificate, no root);
- NP-G's outcome only: its verdict can sit in ADR 0007 D2.4's band (spec §17, B13).

Every case whose traversal gives its start runs the common path (`plan_revision` →
`execute_plan` → `verify_revision` when `CONVERGED`), as `test_t05b_contract.solve` does. DZ-3,
DZ-10, DZ-12, DZ-11 and DZ-2C start from their registered states (`ref.*.start`; the traversal
cannot give them: a perturbed label, a liquid-form root, a refused traversal): the planned region
is solved from that state as `t05b_support.solve_from_v2` does, its trace's events are the
events, and the certificate is `verify_revision` on the region's final state against the planned
step's solve plan, as the tests certify them. The plan's R0 projection is the planned one in both
paths.

Only existing projections, floats-free: no free-text message beyond the typed first line (a
registered code with ids, R-029, spec B20 (c)), no computed float, and no digest of a computed
state — the fingerprint's `constants_sha256` and `variable_ids_sha256` are digests of declared
inputs, its two state digests are dropped by T03's projection. Every case is built by the
package's tests (`tests/t05b_support.py`), from uncached entry points, so two calls in one
process are two solves.
"""

from __future__ import annotations

import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "scripts"))

from t03_identity import _fingerprint  # noqa: E402

#: B22's cases with the full R0 projection, in its order.
FULL = (
    "SC-1",
    "SC-2",
    "SC-3",
    "SC-4",
    "NP-1",
    "NP-2",
    "NP-3",
    "DZ-1",
    "DZ-2",
    "DZ-3",
    "DZ-4",
    "DZ-5",
    "DZ-6",
    "DZ-7",
    "DZ-8",
    "DZ-9",
    "DZ-10",
    "DZ-12",
)
#: B22's cases that close without a root: the outcome and the message's first line.
CONFLICTS = ("DZ-11", "DZ-2C")
#: B22: NP-G's outcome only.
OUTCOME_ONLY = ("NP-G",)
#: The cases whose start is registered rather than the traversal's, with their `ref` section.
REGISTERED_STARTS = {
    "DZ-3": "dormant_cases",
    "DZ-10": "dormant_non_lifted_cases",
    "DZ-12": "dormant_non_lifted_cases",
    "DZ-11": "zero_flow_conflicts",
    "DZ-2C": "zero_flow_conflicts",
}


def _builders() -> dict[str, Callable[[], dict[str, Any]]]:
    import t05b_support as support

    return {
        **support.SINGLE_COMPONENT_CASES,
        **{name: (lambda name=name: support.near_pure(name)) for name in support.NEAR_PURE_CASES},
        **support.DORMANT_CASES,
        **support.DORMANT_NON_LIFTED_CASES,
    }


def _first_line(message: str | None) -> str:
    return message.splitlines()[0] if message else ""


def _case(case: str, document: Mapping[str, Any]) -> dict[str, Any]:
    import t05b_support as support
    from t05_w12_support import bind

    from openflowsheet.orchestrator.execution import ExecutionPlan
    from openflowsheet.orchestrator.executor import execute_plan
    from openflowsheet.orchestrator.region import RegionResult
    from openflowsheet.orchestrator.revision import plan_revision
    from openflowsheet.orchestrator.trace import Trace
    from openflowsheet.run.identity import execution_plan_r0, r0_projection
    from openflowsheet.verify.certificate import verify_revision

    policy = support.POLICY_V2
    binding = bind(dict(document))
    plan, report = plan_revision(binding, policy)
    assert isinstance(plan, ExecutionPlan), plan
    solve_plan = plan.steps[-1].solve_plan
    if case in REGISTERED_STARTS:
        start = support.registered_state(support.REF[REGISTERED_STARTS[case]][case]["start"])
        trace = Trace()
        region = support.solve_from_v2(binding, start, policy, trace=trace)
        outcome, message, events = region.outcome, region.message, trace.events
        state = dict(region.state) if region.outcome == "CONVERGED" else None
        detail: Any = region
        claim: Any = region
    else:
        run = execute_plan(plan=plan, flowsheet=binding.flowsheet, spec=binding.spec, policy=policy)
        outcome, message, events = run.outcome, run.message, run.trace.events
        state = None
        detail = run.steps[-1].detail if run.steps else None
        claim = run
    converged = outcome == "CONVERGED"
    if case in OUTCOME_ONLY:
        return {"outcome": outcome}
    if case in CONFLICTS:
        return {"outcome": outcome, "message": _first_line(message)}
    artifacts: dict[str, Any] = {
        "solve-events.json": [event.as_document() for event in events],
        "structural-report.json": report.as_document(),
    }
    if converged:
        certificate = verify_revision(
            binding, dict(document), claim, state=state, solve_plan=solve_plan
        )
        artifacts["solution-certificate.json"] = certificate.as_document()
    fingerprint = (
        detail.root_fingerprint if converged and isinstance(detail, RegionResult) else None
    )
    return {
        "plan": execution_plan_r0(plan.as_document()),
        "outcome": outcome,
        **r0_projection(artifacts),
        "root_fingerprint": _fingerprint(fingerprint),
        "message": _first_line(message),
    }


def identity() -> dict[str, Any]:
    builders = _builders()
    return {case: _case(case, builders[case]()) for case in (*FULL, *CONFLICTS, *OUTCOME_ONLY)}
