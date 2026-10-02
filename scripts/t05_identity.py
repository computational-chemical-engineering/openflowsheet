"""T05's part of the cross-platform identity (A24), included by `k05_structural_identity.py`.

Design note `docs/design/T05-generalization.md` §6, per case — C1, C2 and C3 (the coupled solves)
and C3X (its `INITIALIZATION_FAILED` trace is R0 too): the execution plan's R0 projection
(`execution_plan_r0`, T02 A02), the plan run's outcome, `r0_projection` of the solve events, the
structural report and, when the run converged, the certificate `verify_revision` issues on it,
the region result's root fingerprint through T03's projection (`t03_identity._fingerprint`), and
the run's typed message, first line only (`""` when there is none; ruling round Q-R5, review N4:
for C3X it is A20's discriminant, `initializer_failed(U-HX): temperature_cross(cold_end)`).

Only existing projections (A24: "no new R0 field"). No free-text message, computed float or digest
of a computed state enters: the plan's floats are its declared scales and bounds, kept as their
shortest decimal strings by `execution_plan_r0` (ADR 0009 D1); the fingerprint's
`delta_scaled_inf` is a registered constant, written the same way; its `constants_sha256` and
`variable_ids_sha256` are digests of declared inputs, as in `t03`, and its two state digests are
dropped by T03's projection. A typed message's first line is a registered code, which carries no
float (R-029).

Every case is built by the package's tests (`test_t05_coupled.solve`, policy `T05-W13`;
`test_t05_certificates.certify`), so this document and the gate run the same fixtures, and from
their uncached entry points, so two calls in one process are two solves.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "scripts"))

from t03_identity import _fingerprint  # noqa: E402

#: The cases of design note §6, in its order.
CASES = ("SYN-001-UL-C1", "SYN-001-UL-C2", "SYN-001-UL-C3", "SYN-001-UL-C3X")


def _case(case: str) -> dict[str, Any]:
    from test_t05_certificates import certify
    from test_t05_coupled import solve

    from openflowsheet.orchestrator.region import RegionResult
    from openflowsheet.run.identity import execution_plan_r0, r0_projection

    solved = solve(case)
    run = solved.run
    converged = run.outcome == "CONVERGED"
    artifacts: dict[str, Any] = {
        "solve-events.json": [event.as_document() for event in run.trace.events],
        "structural-report.json": solved.report.as_document(),
    }
    if converged:
        artifacts["solution-certificate.json"] = certify(solved, case).as_document()
    detail = run.steps[-1].detail if run.steps else None
    fingerprint = (
        detail.root_fingerprint if converged and isinstance(detail, RegionResult) else None
    )
    return {
        "plan": execution_plan_r0(solved.plan.as_document()),
        "outcome": run.outcome,
        **r0_projection(artifacts),
        "root_fingerprint": _fingerprint(fingerprint),
        "message": run.message.splitlines()[0] if run.message else "",
    }


def identity() -> dict[str, Any]:
    return {case: _case(case) for case in CASES}
