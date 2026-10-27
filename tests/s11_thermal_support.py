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
from typing import Any, Final

from m02_c1_support import connection, revision
from test_s11_thermal_binding import (
    dimensionless,
    duty,
    feed,
    instance,
    outlet_pressure,
    outlet_temperature,
    pascal,
)

from openflowsheet.application.policies import T06_REVISION_V2
from openflowsheet.application.revision_binding import RevisionBinding, bind_revision_flowsheet
from openflowsheet.models.revision_flowsheet import COOLPROP_RECORDS, IAPWS95_RECORDS
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


def th_c1() -> dict[str, Any]:
    """TH-C1 (S11.A59), Rankine once-through: liquid at 10 kPa, 318.15 K → pump (3 MPa, η 0.75)
    → boiler (T mode, 673.15 K, vapour) → turbine (10 kPa, η 0.85, wet) → condenser (quality 0)
    → sink."""
    return _water(
        "S11-TH-C1",
        [
            instance("F", "syn001.feed_source"),
            instance("P", "thermal.pump", {"efficiency": dimensionless(0.75)}),
            instance("B", "thermal.heater"),
            instance("T", "thermal.turbine", {"efficiency": dimensionless(0.85)}),
            instance("C", "thermal.heater", {"outlet_vapor_fraction": dimensionless(0.0)}),
            instance("K", "syn001.product_sink"),
        ],
        [
            connection("S1", ("F", "outlet"), ("P", "inlet"), "liquid"),
            connection("S2", ("P", "outlet"), ("B", "inlet"), "liquid"),
            connection("S3", ("B", "outlet"), ("T", "inlet"), "vapor"),
            connection("S4", ("T", "outlet"), ("C", "inlet"), "vapor_liquid"),
            connection("S5", ("C", "outlet"), ("K", "inlet"), "vapor_liquid"),
        ],
        [
            *feed("S1", "H2O", 318.15, 1.0e4),
            outlet_pressure("P", 3.0e6),
            outlet_temperature("B", 673.15),
            outlet_pressure("T", 1.0e4),
        ],
    )


def th_c2() -> dict[str, Any]:
    """TH-C2 (S11.A60), refrigeration on `coolprop-heos-v1` R134a: vapour at 0.2 MPa, 270 K →
    compressor (1 MPa, η 0.75) → condenser (quality 0) → valve (0.2 MPa) → evaporator (quality 1)
    → sink."""
    return revision(
        [
            instance("F", "syn001.feed_source"),
            instance("G", "thermal.compressor", {"efficiency": dimensionless(0.75)}),
            instance("C", "thermal.heater", {"outlet_vapor_fraction": dimensionless(0.0)}),
            instance("V", "thermal.valve"),
            instance("E", "thermal.heater", {"outlet_vapor_fraction": dimensionless(1.0)}),
            instance("K", "syn001.product_sink"),
        ],
        [
            connection("S1", ("F", "outlet"), ("G", "inlet"), "vapor"),
            connection("S2", ("G", "outlet"), ("C", "inlet"), "vapor"),
            connection("S3", ("C", "outlet"), ("V", "inlet"), "vapor_liquid"),
            connection("S4", ("V", "outlet"), ("E", "inlet"), "vapor_liquid"),
            connection("S5", ("E", "outlet"), ("K", "inlet"), "vapor_liquid"),
        ],
        [
            *feed("S1", "R134a", 270.0, 2.0e5),
            outlet_pressure("G", 1.0e6),
            outlet_pressure("V", 2.0e5),
        ],
        components=("R134a",),
        record_source=COOLPROP_RECORDS,
        revision_id="S11-TH-C2",
    )


#: TH-R1's fixed inputs (S11.A61; S11C_DECISIONS C6-4): the drum's beta is 0.292.
TH_R1_FEED_T: Final = 300.0
TH_R1_DUTY: Final = 2.5e4


def th_r1() -> dict[str, Any]:
    """TH-R1 (S11.A61), recycle on H2O: feed liquid (1 mol/s, 300 K, 0.5 MPa) → mixer → heater
    (duty 25 kW, wet outlet) → valve (0.2 MPa, wet) → drum (Q = 0, ΔP = 0); the drum liquid →
    pump (0.5 MPa, η 0.75, liquid) → splitter (0.5) → back to the mixer, the purge to a sink;
    the drum vapour to a sink."""
    return _water(
        "S11-TH-R1",
        [
            instance("F", "syn001.feed_source"),
            instance("M", "thermal.mixer"),
            instance("H", "thermal.heater"),
            instance("V", "thermal.valve"),
            instance("D", "thermal.flash", {"pressure_drop": pascal(0.0)}),
            instance("P", "thermal.pump", {"efficiency": dimensionless(0.75)}),
            instance("SP", "syn001.stream_splitter", {"split_fraction": dimensionless(0.5)}),
            instance("KV", "syn001.product_sink"),
            instance("KP", "syn001.product_sink"),
        ],
        [
            connection("S1", ("F", "outlet"), ("M", "inlet"), "liquid"),
            connection("S2", ("M", "outlet"), ("H", "inlet"), "liquid"),
            connection("S3", ("H", "outlet"), ("V", "inlet"), "vapor_liquid"),
            connection("S4", ("V", "outlet"), ("D", "inlet"), "vapor_liquid"),
            connection("S5", ("D", "vapor"), ("KV", "inlet"), "vapor_liquid"),
            connection("S6", ("D", "liquid"), ("P", "inlet"), "vapor_liquid"),
            connection("S7", ("P", "outlet"), ("SP", "inlet"), "liquid"),
            connection("S8", ("SP", "recycle"), ("M", "inlet"), "liquid"),
            connection("S9", ("SP", "purge"), ("KP", "inlet"), "liquid"),
        ],
        [
            *feed("S1", "H2O", TH_R1_FEED_T, 5.0e5),
            duty("H", TH_R1_DUTY),
            outlet_pressure("V", 2.0e5),
            duty("D", 0.0),
            outlet_pressure("P", 5.0e5),
        ],
    )


#: Case name -> document builder; the committed file is `THERMAL / f"{name}.json"`.
CASES: Mapping[str, Callable[[], dict[str, Any]]] = {
    "TH-V1": th_v1,
    "TH-C1": th_c1,
    "TH-C2": th_c2,
    "TH-R1": th_r1,
}


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
