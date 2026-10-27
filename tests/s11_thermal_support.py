"""S11 WO-C6: the registered `thermal.*` flowsheet cases (S11 units design §5.2 C6, §6.1 A59–A63).

Each case is a revision document built here and committed under `benchmarks/s11/thermal/`; the
test `test_the_committed_case_is_the_generated_one` keeps the two equal. The seven `thermal.*`
models enter the binder's tables only at I1b, so a solve registers them in monkeypatched tables
(`test_s11_thermal_binding.register`). Regenerate the committed cases with
`PYTHONPATH=src:tests python tests/s11_thermal_support.py`.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from m02_c1_support import connection, revision
from test_s11_thermal_binding import duty, feed, instance, outlet_pressure, pascal

from openflowsheet.application.policies import T06_REVISION_V2
from openflowsheet.application.revision_binding import RevisionBinding, bind_revision_flowsheet
from openflowsheet.models.revision_flowsheet import IAPWS95_RECORDS
from openflowsheet.orchestrator.execution import ExecutionPlan
from openflowsheet.orchestrator.executor import PlanResult, execute_plan
from openflowsheet.orchestrator.revision import plan_revision
from openflowsheet.orchestrator.trace import SolvePolicy

THERMAL = Path(__file__).resolve().parents[1] / "benchmarks" / "s11" / "thermal"


def _water(
    revision_id: str,
    instances: list[dict[str, Any]],
    connections: list[dict[str, Any]],
    specifications: list[dict[str, Any]],
) -> dict[str, Any]:
    return revision(
        instances,
        connections,
        specifications,
        components=("H2O",),
        record_source=IAPWS95_RECORDS,
        revision_id=revision_id,
    )


def th_v1() -> dict[str, Any]:
    """TH-V1 (the C6 spike, Q18): liquid H2O at 1 MPa, 450 K → valve (0.2 MPa, wet) → drum
    (Q = 0, ΔP = 0) → vapour and liquid sinks."""
    return _water(
        "S11-TH-V1",
        [
            instance("F", "syn001.feed_source"),
            instance("V", "thermal.valve"),
            instance("D", "thermal.flash", {"pressure_drop": pascal(0.0)}),
            instance("K1", "syn001.product_sink"),
            instance("K2", "syn001.product_sink"),
        ],
        [
            connection("S1", ("F", "outlet"), ("V", "inlet"), "liquid"),
            connection("S2", ("V", "outlet"), ("D", "inlet"), "vapor_liquid"),
            connection("S3", ("D", "vapor"), ("K1", "inlet"), "vapor_liquid"),
            connection("S4", ("D", "liquid"), ("K2", "inlet"), "vapor_liquid"),
        ],
        [*feed("S1", "H2O", 450.0, 1.0e6), outlet_pressure("V", 2.0e5), duty("D", 0.0)],
    )


#: Case name -> document builder; the committed file is `THERMAL / f"{name}.json"`.
CASES: Mapping[str, Callable[[], dict[str, Any]]] = {"TH-V1": th_v1}


def committed_case(name: str) -> dict[str, Any]:
    document: dict[str, Any] = json.loads((THERMAL / f"{name}.json").read_bytes())
    return document


def solve(
    document: Mapping[str, Any],
    policy: SolvePolicy = T06_REVISION_V2,
    user_start: Mapping[str, float] | None = None,
) -> tuple[RevisionBinding, PlanResult]:
    """Bind, plan and execute `document` (the thermal models registered by the caller)."""
    binding = bind_revision_flowsheet(document)
    assert isinstance(binding, RevisionBinding), binding
    plan, _ = plan_revision(binding, policy)
    assert isinstance(plan, ExecutionPlan), plan
    run = execute_plan(
        plan=plan,
        flowsheet=binding.flowsheet,
        spec=binding.spec,
        policy=policy,
        user_start=user_start,
    )
    return binding, run


if __name__ == "__main__":
    THERMAL.mkdir(parents=True, exist_ok=True)
    for case, build in CASES.items():
        text = json.dumps(build(), indent=2, sort_keys=True) + "\n"
        (THERMAL / f"{case}.json").write_text(text, encoding="utf-8")
