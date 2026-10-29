"""S11 WO-D6: the Wilson (γ–φ) flowsheet cases (units design §5.3 D6, §6.1 A69–A71, A80, A81).

Each case is a revision on Wilson's real records (`WILSON_RECORDS`, which select `wilson-ig-v2`
since WO-D5), built here and committed as `benchmarks/s11/gp/<name>.json` (regenerate with
`python tests/s11_gp_support.py`; a test asserts the committed file is the generated one).

Since I1b `MODEL_BASES` admits the five K02/T05 units and the Wilson compressor and turbine on
`wilson-ig-v2`, and `table.revision_checks` dispatches the v2 basis to
`gamma_phi_units.revision_checks`; `count_gamma_phi` counts those calls, so a test can see the
form was used.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest
from m02_c1_support import connection, quantity, revision, specification
from test_s11_thermal_binding import dimensionless

from openflowsheet.application.policies import T06_REVISION_V2
from openflowsheet.application.revision_binding import (
    RevisionBinding,
    bind_revision_flowsheet,
)
from openflowsheet.models.revision_flowsheet import WILSON_BASIS, WILSON_RECORDS
from openflowsheet.orchestrator.execution import ExecutionPlan
from openflowsheet.orchestrator.executor import PlanResult, execute_plan
from openflowsheet.orchestrator.revision import plan_revision
from openflowsheet.orchestrator.trace import SolvePolicy
from openflowsheet.verify import CheckResult, gamma_phi_units

GP = Path(__file__).resolve().parents[1] / "benchmarks" / "s11" / "gp"

MIXER = "syn001.adiabatic_mixer"
HEATER = "syn001.tp_heater"
TP_FLASH = "syn001.tp_flash"
PH_FLASH = "syn001.ph_flash"
VALVE = "syn001.valve"
#: The five γ–φ-faced K02/T05 units (units design §4.5).
FIVE = (MIXER, HEATER, TP_FLASH, PH_FLASH, VALVE)
ROLES = {"syn001.feed_source": "feed", "syn001.product_sink": "product_sink"}
#: S10 C-MW's feed composition on the real records (CH3OH, C2H5OH, H2O), mol/s; ethanol exactly
#: +0.0 (a binary on the ternary provider).
C_MW_FEED = (0.4, 0.0, 0.6)
P_ATM = 101_325.0

Document = dict[str, Any]


def _instance(unit: str, model: str, parameters: Mapping[str, Any] | None = None) -> Document:
    return {
        "id": unit,
        "model": {"id": model, "version": "0.0.0-declared", "artifact_ref": None},
        "semantic_role": ROLES.get(model, "other"),
        "parameters": dict(parameters or {}),
        "policy": {"fidelity": "test", "validity": "test"},
    }


def _zero_drop() -> dict[str, Any]:
    return {"pressure_drop": quantity(0.0, "Pa", "pressure", [-1, 1, -2, 0, 0, 0, 0])}


def _feed_pins(
    stream: str, flows: Sequence[float], temperature: float, pressure: float
) -> list[Document]:
    return [
        *(
            specification(
                f"SPEC-{stream}-n-{c}",
                "connection",
                stream,
                "state.n",
                v,
                "molar_flow",
                component=c,
            )
            for c, v in zip(WILSON_BASIS.components, flows, strict=True)
        ),
        specification(
            f"SPEC-{stream}-T", "connection", stream, "state.T", temperature, "temperature"
        ),
        specification(f"SPEC-{stream}-P", "connection", stream, "state.P", pressure, "pressure"),
    ]


def _t(name: str, stream: str, value: float) -> Document:
    return specification(name, "connection", stream, "state.T", value, "temperature")


def _p(name: str, stream: str, value: float) -> Document:
    return specification(name, "connection", stream, "state.P", value, "pressure")


def gp_c1() -> Document:
    """S11.A69 GP-C1: C-MW's feed, liquid at 330 K and 101 325 Pa → `tp_heater` (outlet pinned at
    352 K, lifted, β ≈ 0.32) → `tp_flash` at 355 K and 101 325 Pa (β ≈ 0.53) → two sinks."""
    instances = [
        _instance("F", "syn001.feed_source"),
        _instance("H", HEATER, _zero_drop()),
        _instance("D", TP_FLASH, _zero_drop()),
        _instance("KV", "syn001.product_sink"),
        _instance("KL", "syn001.product_sink"),
    ]
    connections = [
        connection("S1", ("F", "outlet"), ("H", "inlet"), "liquid"),
        connection("S2", ("H", "outlet"), ("D", "inlet"), "vapor_liquid"),
        connection("S3", ("D", "vapor"), ("KV", "inlet"), "vapor"),
        connection("S4", ("D", "liquid"), ("KL", "inlet"), "liquid"),
    ]
    pins = [
        *_feed_pins("S1", C_MW_FEED, 330.0, P_ATM),
        _t("SPEC-H-T", "S2", 352.0),
        _t("SPEC-S3-T", "S3", 355.0),
        _p("SPEC-S3-P", "S3", P_ATM),
        _t("SPEC-S4-T", "S4", 355.0),
        _p("SPEC-S4-P", "S4", P_ATM),
    ]
    return revision(
        instances,
        connections,
        pins,
        components=WILSON_BASIS.components,
        record_source=WILSON_RECORDS,
        revision_id="S11-GP-C1",
    )


def gp_c2() -> Document:
    """S11.A70 GP-C2: C-MW's feed, liquid at 360 K and 180 kPa → `valve` to 101 325 Pa (lifted
    outlet) → `ph_flash` with 5 kW duty and no pressure drop → two sinks."""
    instances = [
        _instance("F", "syn001.feed_source"),
        _instance("V", VALVE),
        _instance("D", PH_FLASH, _zero_drop()),
        _instance("KV", "syn001.product_sink"),
        _instance("KL", "syn001.product_sink"),
    ]
    connections = [
        connection("S1", ("F", "outlet"), ("V", "inlet"), "liquid"),
        connection("S2", ("V", "outlet"), ("D", "inlet"), "vapor_liquid"),
        connection("S3", ("D", "vapor"), ("KV", "inlet"), "vapor"),
        connection("S4", ("D", "liquid"), ("KL", "inlet"), "liquid"),
    ]
    pins = [
        *_feed_pins("S1", C_MW_FEED, 360.0, 180_000.0),
        _p("SPEC-V-P", "S2", P_ATM),
        specification("SPEC-D-Q", "instance", "D", "duty.Q", 5.0e3, "heat_rate"),
    ]
    return revision(
        instances,
        connections,
        pins,
        components=WILSON_BASIS.components,
        record_source=WILSON_RECORDS,
        revision_id="S11-GP-C2",
    )


#: GP-C3's second liquid: ethanol-water (no methanol), mol/s.
EW_FEED = (0.0, 0.2, 0.3)


def gp_c3(heater_temperature: float = 354.0) -> Document:
    """S11.A71 GP-C3: C-MW's feed (liquid, 330 K) and an ethanol-water liquid (320 K), both at
    101 325 Pa → `adiabatic_mixer` (declared liquid outlet, judged by `single_phase_admissible`) →
    `tp_heater` to 354 K (lifted outlet, β ≈ 0.41) → a sink. At 345 K the lifted outlet is
    liquid only (β = 0, the vapour columns exactly zero): S11 rulings OQ-5's case, kept as a test
    of its own."""
    instances = [
        _instance("FA", "syn001.feed_source"),
        _instance("FB", "syn001.feed_source"),
        _instance("M", MIXER),
        _instance("H", HEATER, _zero_drop()),
        _instance("K", "syn001.product_sink"),
    ]
    connections = [
        connection("S1", ("FA", "outlet"), ("M", "inlet"), "liquid"),
        connection("S2", ("FB", "outlet"), ("M", "inlet"), "liquid"),
        connection("S3", ("M", "outlet"), ("H", "inlet"), "liquid"),
        connection("S4", ("H", "outlet"), ("K", "inlet"), "vapor_liquid"),
    ]
    pins = [
        *_feed_pins("S1", C_MW_FEED, 330.0, P_ATM),
        *_feed_pins("S2", EW_FEED, 320.0, P_ATM),
        _t("SPEC-H-T", "S4", heater_temperature),
    ]
    return revision(
        instances,
        connections,
        pins,
        components=WILSON_BASIS.components,
        record_source=WILSON_RECORDS,
        revision_id="S11-GP-C3",
    )


COMPRESSOR = "thermal.compressor"
TURBINE = "thermal.turbine"
#: GP-M1's inlet (S11.A80): C-MW's vapour at 370 K, 40 kPa (dew point 338.84 K), compressed to
#: 50 kPa (dew point 343.99 K) at eta = 0.8.
GP_M1_INLET = (370.0, 40_000.0)
GP_M1_OUTLET_P = 50_000.0


def _outlet_pressure(unit: str, value: float) -> Document:
    return specification(f"SPEC-{unit}-P", "instance", unit, "outlet.P", value, "pressure")


def _machine_case(
    model: str,
    efficiency: float,
    inlet: tuple[float, float],
    outlet_pressure: float,
    revision_id: str,
) -> Document:
    """C-MW's vapour → one Wilson machine → a sink, every stream declared `vapor` (L-GP-2)."""
    instances = [
        _instance("F", "syn001.feed_source"),
        _instance("M", model, {"efficiency": dimensionless(efficiency)}),
        _instance("K", "syn001.product_sink"),
    ]
    connections = [
        connection("S1", ("F", "outlet"), ("M", "inlet"), "vapor"),
        connection("S2", ("M", "outlet"), ("K", "inlet"), "vapor"),
    ]
    pins = [*_feed_pins("S1", C_MW_FEED, *inlet), _outlet_pressure("M", outlet_pressure)]
    return revision(
        instances,
        connections,
        pins,
        components=WILSON_BASIS.components,
        record_source=WILSON_RECORDS,
        revision_id=revision_id,
    )


def gp_m1() -> Document:
    """S11.A80 GP-M1: C-MW's vapour at 370 K and 40 kPa → `thermal.compressor` to 50 kPa at
    eta = 0.8 (outlet ≈ 391.7 K, inside the records' 400 K) → a sink."""
    return _machine_case(COMPRESSOR, 0.8, GP_M1_INLET, GP_M1_OUTLET_P, "S11-GP-M1")


#: GP-M2's inlet (S11.A81): C-MW's vapour at 375 K, 150 kPa (2.75 K above its dew point there,
#: 372.25 K), expanded to 90 kPa (dew point 358.47 K) at eta = 0.85.
GP_M2_INLET = (375.0, 150_000.0)
GP_M2_OUTLET_P = 90_000.0


def gp_m2() -> Document:
    """S11.A81 GP-M2: C-MW's vapour near its dew point → `thermal.turbine` to 90 kPa at
    eta = 0.85 → a sink; the expansion crosses the dew point, so the machine refuses it."""
    return _machine_case(TURBINE, 0.85, GP_M2_INLET, GP_M2_OUTLET_P, "S11-GP-M2")


#: Case name -> document builder; the committed file is `GP / f"{name}.json"`.
CASES: Mapping[str, Callable[[], Document]] = {
    "GP-C1": gp_c1,
    "GP-C2": gp_c2,
    "GP-C3": gp_c3,
    "GP-M1": gp_m1,
    "GP-M2": gp_m2,
}


def committed_case(name: str) -> Document:
    document: Document = json.loads((GP / f"{name}.json").read_bytes())
    return document


def count_gamma_phi(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """`gamma_phi_units.revision_checks` wrapped to record the number of checks of each call that
    `table.revision_checks` dispatches to it (I1b's hook), so a test can see the form was used."""
    original = gamma_phi_units.revision_checks
    calls: list[int] = []

    def counted(*args: Any, **kwargs: Any) -> list[CheckResult]:
        found = original(*args, **kwargs)
        calls.append(len(found))
        return found

    monkeypatch.setattr(gamma_phi_units, "revision_checks", counted)
    return calls


def solve(
    document: Mapping[str, Any], policy: SolvePolicy = T06_REVISION_V2
) -> tuple[RevisionBinding, ExecutionPlan, PlanResult]:
    """Bind, plan and execute `document` (the caller admits the five on Wilson)."""
    binding = bind_revision_flowsheet(document)
    assert isinstance(binding, RevisionBinding), binding
    plan, _ = plan_revision(binding, policy)
    assert isinstance(plan, ExecutionPlan), plan
    run = execute_plan(plan=plan, flowsheet=binding.flowsheet, spec=binding.spec, policy=policy)
    return binding, plan, run


if __name__ == "__main__":
    GP.mkdir(parents=True, exist_ok=True)
    for case, build in CASES.items():
        text = json.dumps(build(), indent=2, sort_keys=True) + "\n"
        (GP / f"{case}.json").write_text(text, encoding="utf-8")
