"""E01 WO-B2: the LCA contributor on P4 (P1 = S11 TH-C1 with an LCA section on `test-background-v1`
plus `gwp100-ipcc-ar6-v1`) — design §4.8.1, §4.8.3, §4.8.6; A26, A27, A28, A29 (P4 part), and
A25's hand clause (rel ≤ 1e-12 against track A's mpmath superposition, R-861).

Independent expectations: `benchmarks/e01/lca_hand/lca_hand.yaml` (track A, mpmath, nothing from
openflowsheet) for P4; hand arithmetic on the program's own θ and inventory values for the
allocation forms and the derivatives (A26 is a bitwise statement about the assembly).
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_e01_a_report import P1_DOC, _solved, registered  # noqa: E402, F401

from openflowsheet.application.types import schema_errors  # noqa: E402
from openflowsheet.assessment.cost.contributor import CostContributor  # noqa: E402
from openflowsheet.assessment.cost.derived import DerivedContributor  # noqa: E402
from openflowsheet.assessment.lca import tables  # noqa: E402
from openflowsheet.assessment.lca.section import LcaContributor  # noqa: E402
from openflowsheet.assessment.lca.tables import table_sha256  # noqa: E402
from openflowsheet.assessment.program import AssessmentProgram  # noqa: E402
from openflowsheet.assessment.report import SCHEMA_REFERENCE  # noqa: E402
from openflowsheet.assessment.spec import load_assessment  # noqa: E402
from openflowsheet.assessment.views import view_of  # noqa: E402
from openflowsheet.canonical import state_sha256  # noqa: E402
from openflowsheet.models import flow_id  # noqa: E402
from openflowsheet.models.thermal.state import liquid_id, vapor_id  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
HAND = yaml.safe_load((ROOT / "benchmarks/e01/lca_hand/lca_hand.yaml").read_text("utf-8"))
FRAGMENT = HAND["p4"]["document_fragment"]
CONTRIBUTORS = (CostContributor(), LcaContributor(), DerivedContributor())
RATE = "impact.climate_change_test.rate"


def _p4_document() -> dict[str, Any]:
    document = copy.deepcopy(P1_DOC)
    document["assessment_id"] = "e01-b2-p4"
    for utility in document["utilities"]:
        key = f"utilities.{utility['utility_id']}.lca"
        if key in FRAGMENT:
            utility["lca"] = copy.deepcopy(FRAGMENT[key])
    document["materials"][0]["lca"] = copy.deepcopy(FRAGMENT["materials.S1.lca"])
    document["lca"] = {
        "tables": ["test-background-v1"],
        "direct_factors": ["gwp100-ipcc-ar6-v1"],
        "categories": list(FRAGMENT["lca.categories"]),
        "functional_unit": dict(FRAGMENT["lca.functional_unit"]),
    }
    return document


P4_DOC = _p4_document()


def _program(document: dict[str, Any]) -> tuple[AssessmentProgram, dict[str, float], str]:
    binding, host, state = _solved("TH-C1")
    program = AssessmentProgram.build(
        view_of(binding.flowsheet),
        host,
        load_assessment(document),
        state,
        contributors=CONTRIBUTORS,
    )
    assert isinstance(program, AssessmentProgram), program
    return program, state, state_sha256(state, host.variable_ids)


def _mass(stream: str, state: dict[str, float]) -> float:
    """A TH-C1 stream's mass (water only), kg/s: `M·(V + L)` on a two-phase stream, `M·n`
    otherwise."""
    binding, _, _ = _solved("TH-C1")
    ((component, molar_mass),) = view_of(binding.flowsheet).molar_masses().items()
    if vapor_id(stream) in state:
        return molar_mass * (state[vapor_id(stream)] + state[liquid_id(stream)])
    return molar_mass * state[flow_id(stream, component)]


def _values(document: dict[str, Any], x: dict[str, float] | None = None) -> dict[str, float]:
    program, state, _ = _program(document)
    values = program.evaluate(state if x is None else x)
    assert not isinstance(values, tables.Refusal)
    return dict(values)


def _rel(a: float, b: float) -> float:
    return abs(a - b) / abs(b)


def test_p4_matches_the_hand_superposition(
    registered: None,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A25 (hand clause, rel ≤ 1e-12) and A29 (P4 evaluates from its tables without Brightway)."""
    monkeypatch.setitem(sys.modules, "bw2data", None)
    monkeypatch.setitem(sys.modules, "bw2calc", None)
    program, state, _ = _program(P4_DOC)
    values = program.evaluate(state)
    assert not isinstance(values, tables.Refusal)
    expected = HAND["p4"]
    amounts = expected["exchange_amounts_per_s"]
    assert (
        _rel(values["inventory.utility.EL.tb.electricity.rate"], amounts["tb.electricity"]["value"])
        <= 1e-12
    )
    assert _rel(values["inventory.utility.HPS.tb.heat.rate"], amounts["tb.heat"]["value"]) <= 1e-12
    assert (
        _rel(values["inventory.material.S1.tb.chemical_x.rate"], amounts["tb.chemical_x"]["value"])
        <= 1e-12
    )
    # Electricity is net: the turbine's generation exceeds the pump motor's draw.
    assert values["inventory.utility.EL.tb.electricity.rate"] < 0.0
    for suffix in ("rate", "annual", "per_fu"):
        name = f"impact.climate_change_test.{suffix}"
        assert _rel(values[name], expected[name]["value"]) <= 1e-12, (name, values[name])
    assert program.units[RATE] == "kg CO2-eq/s"
    assert program.units["impact.climate_change_test.per_fu"] == "kg CO2-eq/kg"
    codes = {lim.code for lim in program.limitations}
    assert {"LCA_BACKGROUND_UNCERTAINTY_NOT_PROPAGATED", "LCA_CAPITAL_GOODS_EXCLUDED"} <= codes
    assert program.refusals == () or all(not r.code.startswith("LCA") for r in program.refusals)


def test_p4_report_lists_the_tables_and_validates(registered: None) -> None:  # noqa: F811
    program, state, digest = _program(P4_DOC)
    report = program.report(state, state_sha256=digest)
    assert schema_errors(SCHEMA_REFERENCE, report) == []
    assert report["status"] == "COMPLETE"
    assert [t["id"] for t in report["lca"]["tables"]] == [
        "test-background-v1",
        "gwp100-ipcc-ar6-v1",
    ]
    impacts = {row["id"]: row["value"] for row in report["lca"]["impacts"]}
    assert _rel(impacts[RATE], HAND["p4"][RATE]["value"]) <= 1e-12
    assert len(report["lca"]["inventory"]) == 3


def _scaled(document: dict[str, Any], factor: float) -> dict[str, Any]:
    scaled = copy.deepcopy(document)
    for entry in [*scaled["utilities"], *scaled["materials"]]:
        for exchange in entry.get("lca", ()):
            exchange["amount"] *= factor
    return scaled


def test_a26_doubling_every_amount_doubles_h_bitwise(registered: None) -> None:  # noqa: F811
    one = _values(P4_DOC)
    two = _values(_scaled(P4_DOC, 2.0))
    for suffix in ("rate", "annual", "per_fu"):
        name = f"impact.climate_change_test.{suffix}"
        assert two[name] == 2.0 * one[name]


def _jacobian_columns(
    program: AssessmentProgram, state: dict[str, float], rows: list[str]
) -> dict[str, dict[str, float]]:
    d = program.linearize(state, {}, rows).d_dx
    found: dict[str, dict[str, float]] = {row: {} for row in rows}
    for j, name in enumerate(d.col_ids):
        for k in range(d.indptr[j], d.indptr[j + 1]):
            found[d.row_ids[d.indices[k]]][name] = d.data[k]
    return found


def test_a26_the_derivative_is_the_hand_assembled_sum(registered: None) -> None:  # noqa: F811
    """`∂h/∂x = Σ_k (q_k·α_k)·∂φ_k/∂x`, bitwise, folded in construction order. `∂φ_k/∂x` is read
    from the same program with every `α_k = 1` exactly (amount 1 per J or kg), so it is the
    derivative of the same `φ_k` expression."""
    program, state, _ = _program(P4_DOC)
    exchanges = [
        ("tb.electricity", "inventory.utility.EL.tb.electricity.rate"),
        ("tb.heat", "inventory.utility.HPS.tb.heat.rate"),
        ("tb.chemical_x", "inventory.material.S1.tb.chemical_x.rate"),
    ]
    unit = copy.deepcopy(P4_DOC)
    for entry in [*unit["utilities"], *unit["materials"]]:
        for exchange in entry.get("lca", ()):
            exchange["amount"] = 1.0
            exchange["per"] = "kg" if exchange["activity"] == "tb.chemical_x" else "J"
    unit_program, _, _ = _program(unit)
    phi = _jacobian_columns(unit_program, state, [o for _, o in exchanges])
    rate = _jacobian_columns(program, state, [RATE])[RATE]
    weight = {
        a: program.theta[f"asm:lca.q.test-background-v1.climate_change_test.{a}"].value
        * program.theta[f"asm:lca.alpha.{o[len('inventory.') : -len('.rate')]}"].value
        for a, o in exchanges
    }
    assert rate, "the rate depends on the state"
    for name in sorted(set(rate) | {n for p in phi.values() for n in p}):
        hand = 0.0
        for k, (activity, output) in enumerate(exchanges):
            term = weight[activity] * phi[output].get(name, 0.0)
            hand = term if k == 0 else hand + term
        assert rate.get(name, 0.0) == hand, name
    # ∂h/∂q = a(x): contribution analysis from the twin.
    symbolic = [f"asm:lca.q.test-background-v1.climate_change_test.{a}" for a, _ in exchanges]
    lin_q = program.linearize(state, {}, [RATE], symbolic)
    values = program.evaluate(state)
    assert not isinstance(values, tables.Refusal)
    for (_, output), theta_id in zip(exchanges, symbolic, strict=True):
        j = lin_q.d_dp.col_ids.index(theta_id)
        got = lin_q.d_dp.data[lin_q.d_dp.indptr[j]]
        assert got == values[output]


def test_a27_one_kg_per_s_of_fossil_methane_is_29_8(registered: None) -> None:  # noqa: F811
    binding, host, state = _solved("TH-C1")
    view = view_of(binding.flowsheet)
    (component,) = view.components
    molar_mass = view.molar_masses()[component]
    document = copy.deepcopy(P4_DOC)
    document["materials"].append(
        {
            "connection": "S5",
            "role": "emission",
            "basis": "component",
            "component": component,
            "emission": {"table": "gwp100-ipcc-ar6-v1", "flows": {component: "ch4_fossil_air"}},
        }
    )
    document["lca"] = {
        "direct_factors": ["gwp100-ipcc-ar6-v1"],
        "categories": ["climate_change_gwp100_ar6"],
    }
    for entry in [*document["utilities"], *document["materials"]]:
        entry.pop("lca", None)
    program = AssessmentProgram.build(
        view, host, load_assessment(document), state, contributors=[LcaContributor()]
    )
    assert isinstance(program, AssessmentProgram), program
    x = dict(state)
    total = x[vapor_id("S5")] + x[liquid_id("S5")]
    x[vapor_id("S5")] *= 1.0 / total / molar_mass  # 1 kg/s through S5
    x[liquid_id("S5")] *= 1.0 / total / molar_mass
    values = program.evaluate(x)
    assert not isinstance(values, tables.Refusal)
    kg = values[f"inventory.emission.S5.{component}.rate"]
    assert abs(kg - 1.0) <= 2.0**-50
    rate = values["impact.climate_change_gwp100_ar6.rate"]
    assert rate == 29.8 * kg
    if kg == 1.0:
        assert rate == 29.8


def _with_allocation(
    allocation: dict[str, Any], extra_materials: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    document = copy.deepcopy(P4_DOC)
    document["lca"]["allocation"] = allocation
    document["materials"].extend(extra_materials or [])
    return document


def test_allocation_factor_and_mass(registered: None) -> None:  # noqa: F811
    none = _values(P4_DOC)[RATE]
    factor = _values(_with_allocation({"method": "factor", "factor": 0.25}))[RATE]
    assert factor == 0.25 * none
    program, state, _ = _program(_with_allocation({"method": "mass", "products": ["S5", "S1"]}))
    values = program.evaluate(state)
    assert not isinstance(values, tables.Refusal)
    share = _mass("S5", state) / (_mass("S5", state) + _mass("S1", state))
    assert values[RATE] == share * none


def test_allocation_economic_and_its_domain(registered: None) -> None:  # noqa: F811
    product = {
        "connection": "S5",
        "role": "product",
        "basis": "mass_total",
        "price": {"value": 0.006, "per": "kg"},
    }
    document = _with_allocation({"method": "economic", "products": ["S5", "S1"]}, [product])
    program, state, _ = _program(document)
    values = program.evaluate(state)
    assert not isinstance(values, tables.Refusal)
    p5 = program.theta["asm:material.S5.price"].value
    p1 = program.theta["asm:material.S1.price"].value
    m5, m1 = _mass("S5", state), _mass("S1", state)
    share = (p5 * m5) / (p5 * m5 + p1 * m1)
    assert values[RATE] == share * _values(P4_DOC)[RATE]
    negative = copy.deepcopy(product)
    negative["price"]["value"] = -0.006
    refused = _with_allocation({"method": "economic", "products": ["S5"]}, [negative])
    program, state, digest = _program(refused)
    assert any(
        r.code == "ASSESSMENT_EVALUATION_FAILED" and r.target == "lca.allocation"
        for r in program.refusals
    )
    report = program.report(state, state_sha256=digest)
    assert report["status"] == "PARTIAL"
    assert RATE in report["unavailable"]


def test_substitution_takes_the_declared_negative_amount(registered: None) -> None:  # noqa: F811
    document = _with_allocation({"method": "substitution"})
    document["materials"][0]["lca"].append(
        {"table": "test-background-v1", "activity": "tb.chemical_x", "amount": -0.5, "per": "kg"}
    )
    values = _values(document)
    base = _values(P4_DOC)
    q = tables.load_shipped("test-background-v1").value("climate_change_test", "tb.chemical_x")
    avoided = values["inventory.material.S1.tb.chemical_x.2.rate"]
    assert avoided < 0.0
    assert values[RATE] == base[RATE] + q * avoided


def test_an_unknown_activity_or_a_wrong_hash_withholds_the_impacts(registered: None) -> None:  # noqa: F811
    document = copy.deepcopy(P4_DOC)
    document["materials"][0]["lca"][0]["activity"] = "tb.nothing"
    program, state, digest = _program(document)
    assert [(r.code, r.target) for r in program.refusals if r.code.startswith("LCA")] == [
        ("LCA_ACTIVITY_UNKNOWN", "test-background-v1.tb.nothing")
    ]
    report = program.report(state, state_sha256=digest)
    assert report["status"] == "PARTIAL"
    assert {RATE, "impact.climate_change_test.annual", "impact.climate_change_test.per_fu"} <= set(
        report["unavailable"]
    )
    document = copy.deepcopy(P4_DOC)
    document["data"] = {
        **document.get("data", {}),
        "tables": [{"id": "test-background-v1", "sha256": "0" * 64}],
    }
    program, _, _ = _program(document)
    assert {r.code for r in program.refusals if r.code.startswith("LCA")} == {
        "LCA_TABLE_HASH_MISMATCH"
    }
    assert RATE in program.unavailable


def _licensed(tmp_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """A user-licensed copy of test-background-v1 (redistribution forbidden, other scores) and
    P4's document reading it."""
    licensed = copy.deepcopy(dict(tables.load_shipped("test-background-v1").document))
    licensed.pop("brightway")
    licensed["table_id"] = "licensed-background"
    licensed["scores"] = [[0.731904826153927, 0.268172539041863, 1.192837465019283]]
    licensed["rights"] = {
        "class": "user-licensed",
        "licence": "a database licensed per user",
        "redistribution": "forbidden",
        "notice": "",
    }
    licensed["sha256"] = table_sha256(licensed)
    path = tmp_path / "licensed.json"
    path.write_text(json.dumps(licensed), encoding="utf-8")
    document = copy.deepcopy(P4_DOC)
    for entry in [*document["utilities"], *document["materials"]]:
        for exchange in entry.get("lca", ()):
            exchange["table"] = "licensed-background"
    document["lca"]["tables"] = ["licensed-background"]
    document["data"] = {
        **document.get("data", {}),
        "tables": [{"id": "licensed-background", "sha256": licensed["sha256"], "path": str(path)}],
    }
    return licensed, document


def test_a28_a_forbidden_table_leaves_only_its_id_and_hash(
    registered: None,  # noqa: F811
    tmp_path: Path,
) -> None:
    licensed, document = _licensed(tmp_path)
    program, state, digest = _program(document)
    report = program.report(state, state_sha256=digest)
    assert report["status"] == "COMPLETE"
    used = tables.parse_table(licensed)
    export = {
        "assessment": document,
        "report": report,
        "tables": [tables.exportable(used)],
    }
    text = json.dumps(export, ensure_ascii=False)
    assert "licensed-background" in text and licensed["sha256"] in text
    for score in licensed["scores"][0]:
        assert repr(score) not in text
        assert repr(score)[:12] not in text
    assert report["lca"]["tables"][0] == (
        {
            "id": "licensed-background",
            "sha256": licensed["sha256"],
            "rights": "user-licensed; redistribution forbidden; a database licensed per user",
        }
    )


def test_a28_a_ranged_score_of_a_forbidden_table_is_withheld(
    registered: None,  # noqa: F811
    tmp_path: Path,
) -> None:
    """ESC-B3: a declared range on a forbidden table's score lists the θ with the reason in place
    of its value; the θ still propagates, and no score reaches the report."""
    licensed, document = _licensed(tmp_path)
    theta = "asm:lca.q.licensed-background.climate_change_test.tb.electricity"
    document["uncertainty"] = {theta: {"relative_range": [-0.1, 0.1]}}
    program, state, digest = _program(document)
    report = program.report(state, state_sha256=digest)
    assert schema_errors(SCHEMA_REFERENCE, report) == []
    assert report["status"] == "COMPLETE"
    entries = [p for p in report["uncertainty"]["parameters"] if p["theta"] == theta]
    assert entries == [
        {
            "theta": theta,
            "withheld": "a score of table licensed-background, whose rights forbid redistribution",
            "relative_range": [-0.1, 0.1],
        }
    ]
    low, high = report["uncertainty"]["linear_interval"][RATE]
    assert low < high
    text = json.dumps(report, ensure_ascii=False)
    for score in licensed["scores"][0]:
        assert repr(score) not in text
        assert repr(score)[:12] not in text
