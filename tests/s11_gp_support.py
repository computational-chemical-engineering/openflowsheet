"""S11 WO-D6: the Wilson (γ–φ) flowsheet cases (units design §5.3 D6, §6.1 A69–A71, A80, A81).

Each case is a revision on Wilson's real records (`WILSON_RECORDS`, which select `wilson-ig-v2`
since WO-D5), built here and committed as `benchmarks/s11/gp/<name>.json` (regenerate with
`python tests/s11_gp_support.py`; a test asserts the committed file is the generated one).

`MODEL_BASES` admits the five K02/T05 units on SYN-001's basis only until the integration WO (I1b)
adds Wilson's row, so `admit_wilson` monkeypatches that row, as `test_s11_gp_binding` does; and
`table.revision_checks` dispatches the v2 basis to `gamma_phi_units.revision_checks` only from
I1b, so `dispatch_gamma_phi` patches that one call.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest
from m02_c1_support import connection, quantity, revision, specification

from openflowsheet.application.policies import T06_REVISION_V2
from openflowsheet.application.revision_binding import (
    MODEL_BASES,
    RevisionBinding,
    bind_revision_flowsheet,
)
from openflowsheet.models.revision_flowsheet import WILSON_BASIS, WILSON_RECORDS
from openflowsheet.orchestrator.execution import ExecutionPlan
from openflowsheet.orchestrator.executor import PlanResult, execute_plan
from openflowsheet.orchestrator.revision import plan_revision
from openflowsheet.orchestrator.trace import SolvePolicy
from openflowsheet.verify import CheckResult, gamma_phi_units, table

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


#: Case name -> document builder; the committed file is `GP / f"{name}.json"`.
CASES: Mapping[str, Callable[[], Document]] = {
    "GP-C1": gp_c1,
}


def committed_case(name: str) -> Document:
    document: Document = json.loads((GP / f"{name}.json").read_bytes())
    return document


def admit_wilson(monkeypatch: pytest.MonkeyPatch) -> None:
    """`MODEL_BASES` with Wilson's row for the five, as I1b will add it."""
    for model in FIVE:
        monkeypatch.setitem(
            MODEL_BASES, model, frozenset({*MODEL_BASES[model], WILSON_BASIS.provider_id})
        )


def dispatch_gamma_phi(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """`table.revision_checks` sending the v2 basis to the γ–φ form, as I1b's hook will; returns
    the number of checks of each dispatched call, so a test can see the form was used."""
    original = table.revision_checks
    calls: list[int] = []

    def dispatch(view: Any, *args: Any, **kwargs: Any) -> list[CheckResult]:
        if view.basis.provider_id == WILSON_BASIS.provider_id:
            found = gamma_phi_units.revision_checks(view, *args, **kwargs)
            calls.append(len(found))
            return found
        return original(view, *args, **kwargs)

    monkeypatch.setattr(table, "revision_checks", dispatch)
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
