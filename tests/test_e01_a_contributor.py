"""E01 WO-A4: the `cost` contributor end to end on solved S11 flowsheets (design §4.5–§4.7, §4.9,
§9.2.6, §9.2.7; assertions A21–A23, A40, A44 drives).

Hand values are recomputed here from the stated formulas and the source's printed coefficients
(SSLW.py, restated below), never read from the module under test.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from functools import cache
from typing import Any

import pytest
from s11_thermal_support import committed_case, solve

from openflowsheet.assessment.cost import uncertainty
from openflowsheet.assessment.cost.contributor import CostContributor
from openflowsheet.assessment.cost.forms import FORMS
from openflowsheet.assessment.cost.index import load_series
from openflowsheet.assessment.cost.sets import NoCorrelation, load_set, resolve
from openflowsheet.assessment.program import AssessmentProgram
from openflowsheet.assessment.spec import load_assessment
from openflowsheet.assessment.views import view_of
from openflowsheet.compile.reference import FloatAlgebra

#: SSLW.py:1636-1641 (η_m) and :1150-1178 (compressor), restated.
KAPPA_W = 1.0 / 745.6998715822702
YEAR = 2023


@pytest.fixture
def registered() -> None:
    """Since S11 I1b the thermal models are rows of the binder's tables: nothing to register."""


C2_DOC: dict[str, Any] = {
    "schema_version": "assessment-v1",
    "assessment_id": "e01-a4-th-c2",
    "basis": {"currency": "USD", "year": YEAR},
    "operation": {"hours_per_year": 8000.0, "lifetime_years": 20, "discount_rate": 0.08},
    "correlation_set": "sslw-idaes-v1",
    "defaults": {"U_by_service": {"heating": 800.0, "cooling": 500.0}},
    "items": {"C": {"F_BM": 3.17}, "E": {"F_BM": 3.17}, "G": {"F_BM": 2.15}},
    "utilities": [
        {
            "utility_id": "LPS",
            "kind": "heating",
            "T_supply": 433.15,
            "dT_min": 10.0,
            "price": {"value": 8.0, "per": "GJ"},
        },
        {
            "utility_id": "CW",
            "kind": "cooling",
            "T_supply": 293.15,
            "T_return": 303.15,
            "dT_min": 5.0,
            "price": {"value": 0.5, "per": "GJ"},
        },
        {"utility_id": "EL", "kind": "electricity", "price": {"value": 0.1, "per": "kWh"}},
    ],
    "capital": {"chain": "ebtf-prisma-v1"},
    "fixed_opex": [{"line": "maintenance", "fraction_of": {"of": "fci", "fraction": 0.03}}],
}


def water_heat_pump() -> dict[str, Any]:
    """S11's TH-C2 loop (compressor, condenser, valve, evaporator) on IAPWS-95 water instead of
    R134a (CoolProp is an optional extra): steam at 0.2 MPa, 410 K → 1 MPa → quality 0 → 0.2 MPa
    → quality 1."""
    text = json.dumps(committed_case("TH-C2")).replace('"R134a"', '"H2O"')
    document: dict[str, Any] = json.loads(text)
    document["component_set"]["record_source"] = "benchmarks/s05/components.yaml"  # TH-C1's
    for spec in document["specifications"]:
        if spec["id"] == "SPEC-S1-T":
            spec["value"] = 410.0
    return document


@cache
def _c2() -> tuple[Any, Any, dict[str, float]]:
    binding, run = solve(water_heat_pump())
    assert run.state is not None
    return binding, binding.spec, dict(run.state)


def _program(document: Mapping[str, Any]) -> tuple[AssessmentProgram, dict[str, float]]:
    binding, host, state = _c2()
    program = AssessmentProgram.build(
        view_of(binding.flowsheet),
        host,
        load_assessment(dict(document)),
        state,
        contributors=[CostContributor()],
    )
    assert isinstance(program, AssessmentProgram), program
    return program, state


def eta_m(w_hp: float) -> float:
    lw = math.log(w_hp)
    return 0.80 + 0.0319 * lw - 0.00182 * lw * lw


def test_a44_motor_efficiency_points() -> None:
    assert eta_m(1.0) == 0.8
    assert eta_m(10.0) == pytest.approx(0.8638030099054395, rel=1e-15)


def test_th_c2_complete_cost_and_a22(registered: None) -> None:  # noqa: F811
    program, state = _program(C2_DOC)
    assert not program.refusals, program.refusals
    assert not program.unavailable, dict(program.unavailable)
    values = program.evaluate(state)
    assert isinstance(values, Mapping)
    # A44 drives: the compressor costs its motor; the drive's electricity is W/η_m(W/N).
    assert values["capex.purchased.G.drive"] == 0.0
    w = state["G.W"]
    choice = program.regime.entries["G.size"]
    n = 1 if choice == "floor" else int(choice.split(":")[1])
    assert values["size.G.drive.power"] == pytest.approx(w / eta_m(w / n * KAPPA_W), rel=1e-15)
    assert "asm:item.G.drive.eta_drive" not in program.theta
    # §10.5 A44: the compressor's size S(N) (consumed power, hp) over κ_W is its drive's
    # electricity.
    sslw = load_set("sslw-idaes-v1")
    comp = resolve(sslw, "compressor", {})
    assert not isinstance(comp, NoCorrelation)
    size_n = FORMS[comp.form].quantities(comp, {"power": w}, FloatAlgebra(), n)
    consumed = size_n["consumed_power_hp"] / KAPPA_W
    assert consumed == pytest.approx(values["size.G.drive.power"], rel=1e-15)
    # §4.7.2: electricity and utilities by hand.
    h = 8000.0
    el = 0.1 / 3.6e6 * values["size.G.drive.power"] * 3600.0 * h
    assert values["opex.utility.EL"] == pytest.approx(el, rel=1e-14)
    # §4.7.1: the chain and its aliases.
    tdc = values["capex.sum_bare_module"]
    assert values["capex.TDC"] == tdc
    assert values["capex.total"] / tdc == pytest.approx(1.744314, rel=4 * 2.0**-52)
    # A22: tac from the report's own fields, independently of the builders.
    i, years = 0.08, 20
    crf = i * (1 + i) ** years / ((1 + i) ** years - 1)
    opex = sum(values[k] for k in values if k.startswith("opex.") and k != "opex.total")
    assert values["opex.total"] == pytest.approx(opex, rel=1e-15)
    assert values["tac"] == pytest.approx(
        crf * values["capex.total"] + values["opex.total"], rel=1e-15
    )
    assert values["opex.fixed.maintenance"] == pytest.approx(0.03 * values["capex.fci"], rel=1e-15)
    # §4.6: the SSLW basis maps CE 500 to 2006 on the USD PPI (INDEX_BASIS_MAPPED).
    ppi = load_series("bls-ppi-wpu11-annual-v1")
    e = ppi.value(YEAR) / ppi.value(2006)  # type: ignore[operator]
    assert program.theta["asm:item.G.E"].value == pytest.approx(e, rel=1e-15)
    assert "INDEX_BASIS_MAPPED" in [lim.code for lim in program.limitations]
    assert "ELECTRICITY_NETTED" not in [lim.code for lim in program.limitations]


def test_a40_refused_item_withholds_totals_and_exclude_restores(registered: None) -> None:  # noqa: F811
    document = {
        **C2_DOC,
        "items": {
            **C2_DOC["items"],
            "C": {"F_BM": 3.17, "correlation": {"set": "sslw-idaes-v1", "entry": "pump"}},
        },
    }
    program, state = _program(document)
    codes = {r.code for r in program.refusals}
    assert "NO_CORRELATION" in codes or "SIZING_INPUT_UNAVAILABLE" in codes
    for name in ("capex.sum_purchased", "capex.total", "tac", "annual.capital_charge"):
        assert name in program.unavailable and name not in program.output_ids
    excluded = {
        **document,
        "items": {**document["items"], "C": {"exclude": {"reason": "vendor package"}}},
    }
    program, state = _program(excluded)
    assert not program.refusals and "tac" in program.output_ids


def test_missing_bare_module_factor_refuses_only_a_bare_module_chain(registered: None) -> None:  # noqa: F811
    document = {**C2_DOC, "items": {"C": {"F_BM": 3.17}, "E": {"F_BM": 3.17}}}
    program, _ = _program(document)
    assert [(r.code, r.target) for r in program.refusals] == [("BARE_MODULE_FACTOR_MISSING", "G")]
    purchased = {
        **document,
        "capital": {
            "steps": [{"name": "TCI", "terms": [{"of": "sum_purchased", "factor": 4.0}]}],
            "capital_total": "TCI",
            "fci": "TCI",
        },
    }
    program, state = _program(purchased)
    assert not program.refusals and "tac" in program.output_ids


def test_a21_discount_rate_domain(registered: None) -> None:  # noqa: F811
    program, _ = _program({**C2_DOC, "operation": {"discount_rate": 0.0009}})
    assert ("DISCOUNT_RATE_OUT_OF_DOMAIN", "operation") in [
        (r.code, r.target) for r in program.refusals
    ]
    assert "tac" in program.unavailable


def test_a23_class_is_the_maximum_and_extrapolation_makes_it_none() -> None:
    assert uncertainty.estimate_class([4, 3, 4], extrapolated=False) == 4
    assert uncertainty.estimate_class([4, 3], extrapolated=True) is None
    assert uncertainty.AACE_RANGES[4] == ((-0.15, -0.30), (0.20, 0.50))
