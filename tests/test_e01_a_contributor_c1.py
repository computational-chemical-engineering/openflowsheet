"""E01 WO-A4: the `cost` contributor on S11's TH-C1 Rankine loop (pump, boiler, turbine, condenser;
IAPWS-95 water): a pump's drive costed by `motor.electric`, turbine generation netted, a quote item,
a held regime's round trip, and an extrapolated item making the class `none` (design §4.4.5,
§4.5.4, §4.7.2, §4.9, §9.2.4 V, §9.2.7; A19, A23, A44 drives).

Hand values are recomputed from the stated formulas and SSLW.py's printed coefficients (restated
below), never read from the module under test.
"""

from __future__ import annotations

import copy
import math
from collections.abc import Mapping
from functools import cache
from typing import Any

import pytest
from s11_thermal_support import committed_case, solve
from test_e01_a_contributor import (
    C2_DOC,
    KAPPA_W,
    YEAR,
    eta_m,
    registered,  # noqa: F401
)

from openflowsheet.assessment.cost.contributor import CostContributor
from openflowsheet.assessment.cost.index import load_series
from openflowsheet.assessment.lca.section import LcaContributor
from openflowsheet.assessment.program import AssessmentProgram, Refusal
from openflowsheet.assessment.regimes import Regime
from openflowsheet.assessment.spec import load_assessment
from openflowsheet.assessment.views import view_of

#: SSLW.py:1650-1661, the motor's base cost at λ = ℓ(W_m) = 0 (the floor, W_m = 1 hp), CE 394.
MOTOR_FLOOR_CE394 = math.exp(5.8259)
#: The set's CE 500 over the motor entry's CE 394 (§9.2.6).
CE_RATIO = 500.0 / 394.0
#: §4.4.5's defaults.generator_efficiency.
ETA_GEN = 0.95
#: §4.7.2: an annual amount is rate·3600·h_op; the price is per SI unit (kWh → J).
H_OP = 8000.0
P_EL = 0.1 / 3.6e6

C1_DOC: dict[str, Any] = {
    **C2_DOC,
    "assessment_id": "e01-a4-th-c1",
    "items": {
        "P": {"F_BM": 3.3},
        "P.drive": {"F_BM": 1.5},
        "B": {"F_BM": 3.17},
        "T": {"F_BM": 3.5},
        "C": {"F_BM": 3.17},
    },
    "utilities": [
        {
            "utility_id": "HPS",
            "kind": "heating",
            "T_supply": 750.0,
            "dT_min": 10.0,
            "price": {"value": 12.0, "per": "GJ"},
        },
        *C2_DOC["utilities"],
    ],
}


@cache
def _c1(pump_outlet: float = 3.0e6) -> tuple[Any, Any, dict[str, float]]:
    document = copy.deepcopy(committed_case("TH-C1"))
    for spec in document["specifications"]:
        if spec["id"] == "SPEC-P-P":
            spec["value"] = pump_outlet
    binding, run = solve(document)
    assert run.state is not None
    return binding, binding.spec, dict(run.state)


def _program(
    document: Mapping[str, Any], pump_outlet: float = 3.0e6, regime: Regime | None = None
) -> tuple[AssessmentProgram | Refusal, dict[str, float]]:
    binding, host, state = _c1(pump_outlet)
    program = AssessmentProgram.build(
        view_of(binding.flowsheet),
        host,
        load_assessment(dict(document)),
        state,
        regime,
        # C1 documents may declare an `lca` functional unit; its section needs its contributor
        # (R-869), which adds no output for it.
        contributors=[CostContributor(), LcaContributor()],
    )
    return program, state


def _escalation() -> float:
    ppi = load_series("bls-ppi-wpu11-annual-v1")
    return ppi.value(YEAR) / ppi.value(2006)  # type: ignore[operator]


def _items(program: AssessmentProgram, values: Mapping[str, float]) -> dict[str, dict[str, Any]]:
    section = program.plans["cost"].section
    assert section is not None
    return {i["item_id"]: i for i in section(values)["items"]}


def test_pump_drive_costed_by_motor_and_turbine_generation_netted(registered: None) -> None:  # noqa: F811
    program, state = _program(C1_DOC)
    assert isinstance(program, AssessmentProgram), program
    assert not program.refusals, program.refusals
    values = program.evaluate(state)
    assert isinstance(values, Mapping)
    # §9.2.7: the centrifugal pump does not include its drive, so `P.drive` is costed by
    # `motor.electric` at the pump's N; W_hp < 1 hp puts the motor on its floor (W_m = 1 hp).
    w_p = state["P.W"]
    assert w_p * KAPPA_W / eta_m(w_p * KAPPA_W) < 1.0
    assert program.regime.entries["P.drive.size"] == "floor"
    expected = MOTOR_FLOOR_CE394 * CE_RATIO * _escalation()
    assert values["capex.purchased.P.drive"] == pytest.approx(expected, rel=1e-14)
    assert values["capex.bare_module.P.drive"] == pytest.approx(1.5 * expected, rel=1e-15)
    drive = _items(program, values)["P.drive"]
    assert drive["source"]["entry"] == "motor.electric" and drive["included_in"] is None
    # §4.7.2 electricity: import price × the pump's W/η_m − export (= import) × −W_T·η_gen.
    consumed = w_p / eta_m(w_p * KAPPA_W)
    generated = -state["T.W"] * ETA_GEN
    el = P_EL * consumed * 3600.0 * H_OP - P_EL * generated * 3600.0 * H_OP
    assert values["opex.utility.EL"] == pytest.approx(el, rel=1e-13)
    codes = [lim.code for lim in program.limitations]
    assert "ELECTRICITY_NETTED" in codes and "GENERATOR_NOT_COSTED" in codes
    section = program.plans["cost"].section
    assert section is not None
    keys = {d["key"] for d in section(values)["defaulted_inputs"]}
    assert {"electricity_export_price", "generator_efficiency"} <= keys


def test_export_price_replaces_netting(registered: None) -> None:  # noqa: F811
    utilities = [
        {**u, "export_price": {"value": 0.04, "per": "kWh"}} if u["utility_id"] == "EL" else u
        for u in C1_DOC["utilities"]
    ]
    program, state = _program({**C1_DOC, "utilities": utilities})
    assert isinstance(program, AssessmentProgram), program
    values = program.evaluate(state)
    assert isinstance(values, Mapping)
    w_p = state["P.W"]
    consumed = w_p / eta_m(w_p * KAPPA_W)
    generated = -state["T.W"] * ETA_GEN
    el = P_EL * consumed * 3600.0 * H_OP - 0.04 / 3.6e6 * generated * 3600.0 * H_OP
    assert values["opex.utility.EL"] == pytest.approx(el, rel=1e-13)
    assert "ELECTRICITY_NETTED" not in [lim.code for lim in program.limitations]


def test_a19_quote_item_through_the_contributor(registered: None) -> None:  # noqa: F811
    quote = {"cost": 1.0e5, "currency": "USD", "year": YEAR, "kind": "purchased", "source": "v"}
    items = {**C1_DOC["items"], "T": {"F_BM": 3.5, "quote": quote}}
    program, state = _program({**C1_DOC, "items": items})
    assert isinstance(program, AssessmentProgram), program
    values = program.evaluate(state)
    assert isinstance(values, Mapping)
    # Same currency and year as the basis, location factor 1: E = 1 and C = cost exactly.
    assert values["capex.purchased.T"] == 1.0e5
    record = _items(program, values)["T"]
    assert record["source"]["quote"]["source"] == "v" and record["accuracy_class"] is None
    # With a size exponent: cost·E·(S/S_q)^n (rel 1e-15).
    scaled = {
        **quote,
        "size": {"quantity": "power", "value": 1.0e4},
        "exponent": 0.6,
        "accuracy_class": 3,
        "relative_range": [-0.2, 0.3],
    }
    items = {**C1_DOC["items"], "T": {"F_BM": 3.5, "quote": scaled}}
    program, state = _program({**C1_DOC, "items": items})
    assert isinstance(program, AssessmentProgram), program
    values = program.evaluate(state)
    assert isinstance(values, Mapping)
    s = -state["T.W"]
    assert values["capex.purchased.T"] == pytest.approx(1.0e5 * (s / 1.0e4) ** 0.6, rel=1e-15)
    record = _items(program, values)["T"]
    assert record["accuracy_class"] == 3 and record["relative_range"] == [-0.2, 0.3]
    assert program.theta["asm:item.T.accuracy"].relative_range == (-0.2, 0.3)


def test_held_regime_round_trip_and_inadmissible_hold(registered: None) -> None:  # noqa: F811
    program, state = _program(C1_DOC)
    assert isinstance(program, AssessmentProgram)
    values = program.evaluate(state)
    held, _ = _program(C1_DOC, regime=program.regime)
    assert isinstance(held, AssessmentProgram), held
    assert held.regime.sha256 == program.regime.sha256
    assert held.label == program.label
    again = held.evaluate(state)
    assert isinstance(values, Mapping) and isinstance(again, Mapping)
    assert {k: repr(v) for k, v in again.items()} == {k: repr(v) for k, v in values.items()}
    assert held.select(state).sha256 == program.regime.sha256
    # Holding `units:1` for a pump below its size minimum violates the row S ≥ S_min.
    assert program.regime.entries["P.size"] == "floor"
    wrong = Regime({**program.regime.entries, "P.size": "units:1"})
    refused, _ = _program(C1_DOC, regime=wrong)
    assert isinstance(refused, Refusal)
    assert refused.code == "ASSESSMENT_REGIME_INADMISSIBLE" and "P.size" in refused.target


def test_a23_extrapolated_item_end_to_end(registered: None) -> None:  # noqa: F811
    # A 16 MPa boiler exceeds the exchanger's 2000 psig pressure-factor range (§9.2.4 I).
    program, _ = _program(C1_DOC, pump_outlet=1.6e7)
    assert isinstance(program, AssessmentProgram)
    assert ("CORRELATION_OUT_OF_RANGE", "B.pressure") in [
        (r.code, r.target) for r in program.refusals
    ]
    items = {**C1_DOC["items"], "B": {"F_BM": 3.17, "allow_extrapolation": True}}
    program, state = _program({**C1_DOC, "items": items}, pump_outlet=1.6e7)
    assert isinstance(program, AssessmentProgram)
    assert not program.refusals, program.refusals
    assert ("CORRELATION_EXTRAPOLATED", "B.pressure") in [
        (lim.code, lim.target) for lim in program.limitations
    ]
    values = program.evaluate(state)
    assert isinstance(values, Mapping)
    assert _items(program, values)["B"]["extrapolated"] is True


def test_materials_revenue_functional_unit_and_lcox(registered: None) -> None:  # noqa: F811
    document = {
        **C1_DOC,
        "materials": [
            {
                "connection": "S1",
                "role": "raw_material",
                "basis": "mass_total",
                "price": {"value": 0.002, "per": "kg"},
            },
            {
                "connection": "S5",
                "role": "product",
                "basis": "molar_total",
                "price": {"value": 0.05, "per": "kmol"},
            },
        ],
        "lca": {"functional_unit": {"connection": "S5", "basis": "mass_total"}},
    }
    program, state = _program(document)
    assert isinstance(program, AssessmentProgram), program
    assert not program.refusals, program.refusals
    values = program.evaluate(state)
    assert isinstance(values, Mapping)
    # The loop carries 1 mol/s of water (S1 spec; S5 saturated liquid, sat.V = 0).
    assert state["S1.n.H2O"] == 1.0 and state["S5.sat.L"] + state["S5.sat.V"] == 1.0
    m_dot = 0.018015268  # kg/s: M(H2O) of benchmarks/s05/components.yaml times 1 mol/s
    year = 3600.0 * H_OP
    assert values["opex.material.S1"] == pytest.approx(0.002 * m_dot * year, rel=1e-15)
    assert values["revenue.S5"] == pytest.approx(0.05 / 1e3 * 1.0 * year, rel=1e-15)
    assert values["revenue.total"] == values["revenue.S5"]
    assert values["product.annual"] == pytest.approx(m_dot * year, rel=1e-15)
    assert values["lcox"] == pytest.approx(values["tac"] / (m_dot * year), rel=1e-15)
    assert values["profit"] == pytest.approx(values["revenue.S5"] - values["tac"], rel=1e-15)
    opex = sum(values[k] for k in values if k.startswith("opex.") and k != "opex.total")
    assert values["opex.total"] == pytest.approx(opex, rel=1e-14)
