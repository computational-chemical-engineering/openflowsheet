"""E01 WO-A5: the assessment report (design §4.5.5, §4.9, §4.11; A23 report part, A38–A41, A43
report part) on real evaluations of S11 cases: TH-C1 and TH-R1 (P1's units: heater, pump,
turbine, second heater; flash) and the column case M1 (P3). I1 names P1 and P3; these are the
candidates their definitions (§5.4) point at.

The committed fixtures under `tests/fixtures/schemas/assessment_report/` are what the code emits
today: regenerate them with `python tests/test_e01_a_report.py --write` (the S11 models are
registered by the script as the tests register them). They are regression fixtures; correctness
is asserted against hand values below.
"""

from __future__ import annotations

import copy
import json
import math
import sys
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from functools import cache
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from s11_column_support import column_registered  # noqa: E402
from s11_column_support import committed_case as column_case  # noqa: E402
from s11_thermal_support import committed_case, solve  # noqa: E402
from test_e01_a_contributor import C2_DOC  # noqa: E402
from test_e01_a_contributor_c1 import C1_DOC, _c1  # noqa: E402
from test_s11_thermal_binding import register  # noqa: E402

from openflowsheet.application.policies import T06_REVISION_V2  # noqa: E402
from openflowsheet.application.revision_binding import bind_revision_flowsheet  # noqa: E402
from openflowsheet.application.types import schema_errors  # noqa: E402
from openflowsheet.assessment.cost import uncertainty as aace  # noqa: E402
from openflowsheet.assessment.cost.contributor import CostContributor  # noqa: E402
from openflowsheet.assessment.cost.derived import DerivedContributor  # noqa: E402
from openflowsheet.assessment.defaults import DEFAULTS  # noqa: E402
from openflowsheet.assessment.program import AssessmentProgram, Refusal  # noqa: E402
from openflowsheet.assessment.report import SCHEMA_REFERENCE, report_body  # noqa: E402
from openflowsheet.assessment.spec import load_assessment  # noqa: E402
from openflowsheet.assessment.views import view_of  # noqa: E402
from openflowsheet.canonical import canonical_json, state_sha256  # noqa: E402
from openflowsheet.orchestrator.executor import execute_plan  # noqa: E402
from openflowsheet.orchestrator.revision import plan_revision  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "schemas" / "assessment_report"
REPO = Path(__file__).resolve().parents[1]

#: P1 (TH-C1): every unit costed, materials and a functional unit, a derived ratio, and a
#: document-declared range on the electricity price.
P1_DOC: dict[str, Any] = {
    **C1_DOC,
    "assessment_id": "e01-a5-p1-th-c1",
    "materials": [
        {
            "connection": "S1",
            "role": "raw_material",
            "basis": "mass_total",
            "price": {"value": 0.002, "per": "kg"},
        }
    ],
    "lca": {"functional_unit": {"connection": "S5", "basis": "mass_total"}},
    "derived": [
        {
            "id": "capex_per_opex",
            "unit": "yr",
            "numerator": {"terms": {"capex.total": 1.0}},
            "denominator": {"terms": {"opex.total": 1.0}},
        }
    ],
    "uncertainty": {"asm:utility.EL.price": {"relative_range": [-0.2, 0.2]}},
}

_UTILITIES_520 = [
    {
        "utility_id": "HPS",
        "kind": "heating",
        "T_supply": 520.0,
        "dT_min": 10.0,
        "price": {"value": 20.0, "per": "GJ"},
    },
    *C2_DOC["utilities"][1:],
]
#: P1's flash (TH-R1): heater, flash drum, pump and its motor.
P1R_DOC: dict[str, Any] = {
    **C2_DOC,
    "assessment_id": "e01-a5-p1-th-r1",
    "items": {
        "H": {"F_BM": 3.17},
        "D.drum": {"F_BM": 4.16},
        "P": {"F_BM": 3.3},
        "P.drive": {"F_BM": 1.5},
    },
    "utilities": _UTILITIES_520,
}
#: P3 (M1): the column's shell, trays, condenser and reboiler.
P3_DOC: dict[str, Any] = {
    **C2_DOC,
    "assessment_id": "e01-a5-p3-m1",
    "items": {
        "S02.shell": {"F_BM": 4.16},
        "S02.trays": {"F_BM": 1.0},
        "S02.condenser": {"F_BM": 3.17},
        "S02.reboiler": {"F_BM": 3.17},
    },
    "utilities": _UTILITIES_520,
}

CONTRIBUTORS = (CostContributor(), DerivedContributor())


@contextmanager
def _registered() -> Iterator[pytest.MonkeyPatch]:
    patch = pytest.MonkeyPatch()
    try:
        register(patch)
        yield patch
    finally:
        patch.undo()


@pytest.fixture
def registered() -> Iterator[None]:
    with _registered():
        yield


@cache
def _solved(case: str) -> tuple[Any, Any, dict[str, float]]:
    """`(binding, host spec, state)` of an S11 case (the models registered by the caller)."""
    if case == "TH-C1":
        return _c1()
    if case == "M1":
        with (
            _registered() as patch,
            column_registered(patch, frozenset({"syn001", "wilson-ig-v2"})),
        ):
            binding = bind_revision_flowsheet(column_case("M1"))
            plan, _ = plan_revision(binding, T06_REVISION_V2)
            run = execute_plan(
                plan=plan, flowsheet=binding.flowsheet, spec=binding.spec, policy=T06_REVISION_V2
            )
            assert run.state is not None
            return binding, binding.spec, dict(run.state)
    binding, run = solve(committed_case(case))
    assert run.state is not None
    return binding, binding.spec, dict(run.state)


def _program(
    case: str, document: Mapping[str, Any]
) -> tuple[AssessmentProgram, dict[str, float], str]:
    binding, host, state = _solved(case)
    program = AssessmentProgram.build(
        view_of(binding.flowsheet),
        host,
        load_assessment(dict(document)),
        state,
        contributors=CONTRIBUTORS,
    )
    assert isinstance(program, AssessmentProgram), program
    return program, state, state_sha256(state, host.variable_ids)


def _report(
    case: str, document: Mapping[str, Any], x: Mapping[str, float] | None = None
) -> dict[str, Any]:
    program, state, digest = _program(case, document)
    return program.report(state if x is None else x, state_sha256=digest)


CASES = {"p1_th_c1": ("TH-C1", P1_DOC), "p1_th_r1": ("TH-R1", P1R_DOC), "p3_m1": ("M1", P3_DOC)}


def _body(report: Mapping[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in report.items() if k != "provenance"}


def _same(a: Any, b: Any, where: str = "") -> None:
    """Equal structure and strings; numbers to rel 1e-9 (regression across platforms' last bits
    of the solved state; logged in docs/E01A_DECISIONS.md)."""
    if isinstance(a, dict):
        assert isinstance(b, dict) and sorted(a) == sorted(b), where
        for k in a:
            _same(a[k], b[k], f"{where}/{k}")
    elif isinstance(a, list):
        assert isinstance(b, list) and len(a) == len(b), where
        for i, (u, v) in enumerate(zip(a, b, strict=True)):
            _same(u, v, f"{where}/{i}")
    elif isinstance(a, float) and not isinstance(b, bool):
        assert isinstance(b, int | float) and math.isclose(a, b, rel_tol=1e-9), (where, a, b)
    else:
        assert a == b, (where, a, b)


# -- A38: schemas, fixtures and the registry -----------------------------------------------------


def test_a38_registry_lists_both_schemas() -> None:
    registry = json.loads((REPO / "schemas" / "registry.json").read_text(encoding="utf-8"))
    assert {"assessment.schema.json", "assessment-report.schema.json"} <= set(registry)


@pytest.mark.parametrize("name", sorted(CASES))
def test_a38_fixtures_validate_and_are_what_the_code_emits(registered: None, name: str) -> None:
    fixture = json.loads((FIXTURES / "valid" / f"{name}.json").read_text(encoding="utf-8"))
    assert schema_errors(SCHEMA_REFERENCE, fixture) == []
    case, document = CASES[name]
    report = _report(case, document)
    assert schema_errors(SCHEMA_REFERENCE, report) == []
    _same(_body(report), _body(fixture))
    assert report["status"] == "COMPLETE", (report["refusals"], report["unavailable"])


def test_a38_invalid_fixture_is_rejected_for_its_reason() -> None:
    for path in sorted((FIXTURES / "invalid").glob("*.json")):
        fixture = json.loads(path.read_text(encoding="utf-8"))
        errors = schema_errors(SCHEMA_REFERENCE, fixture["document"])
        assert errors and fixture["expect_error"] in " | ".join(errors), path


def test_a43_report_digests_are_classified() -> None:
    """`assessment_sha256` is E01's exact digest; `state_sha256` keeps v2's float-digest class."""
    sys.path.insert(0, str(REPO / "scripts"))
    import t08_numerical_policy as policy  # noqa: PLC0415

    table = policy.external_policy(REPO / "benchmarks" / "e01" / "numerical_policy_external.yaml")
    assert "assessment-report.schema.json" in table["schemas"]
    assert "state_sha256" not in table["exact_sha256"]
    assert "state_sha256" in policy.FLOAT_DIGESTS
    declared = policy.schema_sha256_names(external=True, addendum=table)
    assert {"assessment_sha256", "state_sha256", "sha256"} <= declared


# -- A39: byte-identical canonical reports -------------------------------------------------------


def test_a39_two_evaluations_give_byte_identical_reports(registered: None) -> None:
    program, state, digest = _program("TH-C1", P1_DOC)
    first = canonical_json(report_body(program, state, state_sha256=digest, uncertainty=True))
    second = canonical_json(report_body(program, state, state_sha256=digest, uncertainty=True))
    rebuilt, _, _ = _program("TH-C1", P1_DOC)
    third = canonical_json(report_body(rebuilt, state, state_sha256=digest, uncertainty=True))
    assert first == second == third


# -- A40: refused items, exclusion, unavailable outputs ------------------------------------------


def test_a40_refused_item_nulls_totals_and_exclude_restores_them(registered: None) -> None:
    refused = {
        **P1_DOC,
        "items": {
            **P1_DOC["items"],
            "B": {"F_BM": 3.17, "correlation": {"set": "sslw-idaes-v1", "entry": "pump"}},
        },
    }
    program, state, digest = _program("TH-C1", refused)
    report = program.report(state, state_sha256=digest)
    assert schema_errors(SCHEMA_REFERENCE, report) == []
    assert report["status"] == "PARTIAL"
    assert report["capex"]["capex.total"] is None and report["annual"]["tac"] is None
    assert report["derived"]["derived.capex_per_opex"] is None
    assert "capex.total" in report["unavailable"]
    assert any(r["target"].startswith("B") for r in report["refusals"])
    assert {i["item_id"]: i["status"] for i in report["items"]}["B"] == "refused"
    assert report["capex"]["capex.purchased.P"] is not None
    # A study naming a withheld output is refused ASSESSMENT_OUTPUT_UNAVAILABLE.
    refusal = program.linearize(state, {}, ["tac"])
    assert isinstance(refusal, Refusal) and refusal.code == "ASSESSMENT_OUTPUT_UNAVAILABLE"
    excluded = {
        **P1_DOC,
        "items": {**P1_DOC["items"], "B": {"exclude": {"reason": "existing boiler"}}},
    }
    report = _report("TH-C1", excluded)
    assert report["status"] == "COMPLETE"
    assert isinstance(report["capex"]["capex.total"], float) and isinstance(
        report["annual"]["tac"], float
    )
    assert report["excluded"] == [{"item": "B", "reason": "existing boiler"}]
    assert {i["item_id"]: i["status"] for i in report["items"]}["B"] == "excluded"


# -- A41: every default used is reported ---------------------------------------------------------

#: `defaults.py` keys per item family, with the item key that overrides each (§4.4).
_FAMILY_DEFAULTS: dict[str, tuple[tuple[str, str], ...]] = {
    "exchanger.utility": (("F_T", "F_T"),),
    "exchanger.process": (("F_T", "F_T"),),
    "drum": (
        ("drum_residence_time", "residence_time_s"),
        ("drum_fill_fraction", "fill_fraction"),
        ("drum_LD", "LD"),
        ("drum_K_SB", "K_SB"),
        ("drum_orientation", "orientation"),
    ),
    "column.shell": (
        ("column_C_SB", "C_SB"),
        ("column_flooding_fraction", "flooding_fraction"),
        ("column_active_area_fraction", "active_area_fraction"),
        ("column_tray_spacing", "tray_spacing"),
        ("column_H_top", "H_top"),
        ("column_H_bottom", "H_bottom"),
        ("column_overall_efficiency", "overall_efficiency"),
    ),
    "machine.turbine": (("generator_efficiency", "generator_efficiency"),),
    "reactor.vessel": (("reactor_LD", "LD"),),
}


def _expected_defaults(
    report: Mapping[str, Any], document: Mapping[str, Any]
) -> set[tuple[str, str]]:
    doc_defaults = dict(document.get("defaults", {}))
    expected = {
        (f"operation.{k}", "")
        for k in ("hours_per_year", "lifetime_years", "discount_rate")
        if k not in document.get("operation", {})
    }
    basis = document["basis"]
    if "location_factor" not in basis:
        expected.add(("basis.location_factor", ""))
    if "exchange_rates" not in basis:
        expected.add(("exchange_rates", ""))
    expected |= {
        (f"escalation_series.{c}", "")
        for c in ("USD", "EUR")
        if c not in basis.get("escalation_series", {})
    }
    families = {i["family"] for i in report["items"]}
    for item in report["items"]:
        doc = document.get("items", {}).get(item["item_id"], {})
        for key, item_key in _FAMILY_DEFAULTS.get(item["family"], ()):
            if item_key not in doc and key not in doc_defaults:
                expected.add((key, item["item_id"]))
        quantities = {i["name"]: i["value"] for i in item["inputs"]}
        if item["family"].startswith("exchanger.") and quantities.get("Q") == 0.0:
            if "service" not in doc:
                expected.add(("service_at_zero_duty", item["item_id"]))
    if "machine.turbine" in families:
        for u in document.get("utilities", ()):
            if u["kind"] == "electricity" and "export_price" not in u:
                expected.add(("electricity_export_price", u["utility_id"]))
    # `drive_efficiency` is never taken while the set has a motor entry (§9.2.7).
    return expected


@pytest.mark.parametrize("name", sorted(CASES))
def test_a41_every_default_used_is_reported(registered: None, name: str) -> None:
    case, document = CASES[name]
    report = _report(case, document)
    listed = {(d["key"], d["target"]) for d in report["defaulted_inputs"]}
    assert {(k, t) for k, t in listed if k in DEFAULTS} == _expected_defaults(report, document)
    others = {k for k, _ in listed if k not in DEFAULTS}
    assert all(k.startswith("option.") or k in ("shell_thickness", "T_return") for k in others), (
        others
    )


# -- §4.9: class and propagation (A23 report part) -----------------------------------------------


def test_uncertainty_pass_against_hand_values(registered: None) -> None:
    report = _report("TH-C1", P1_DOC)
    unc = report["uncertainty"]
    assert unc["aace_class"] == 4
    assert unc["aace_range"] == {"low": [-0.15, -0.30], "high": [0.20, 0.50]}
    assert unc["assumptions"]["linear_interval"] == aace.ASSUMPTIONS["worst_case"]
    # One item: C ∝ u (u = 1, range [-0.3, 0.5]) → [0.7 C, 1.5 C], σ = 0.8 C/√12.
    c = report["capex"]["capex.purchased.P"]
    lo, hi = unc["linear_interval"]["capex.purchased.P"]
    assert lo == pytest.approx(0.7 * c, rel=1e-12) and hi == pytest.approx(1.5 * c, rel=1e-12)
    assert unc["rss_sigma"]["capex.purchased.P"] == pytest.approx(
        0.8 * c / math.sqrt(12.0), rel=1e-12
    )
    # capex.total = r·Σ C_BM,k with one range per item: [0.7, 1.5]·total and
    # σ = r·0.8/√12·sqrt(Σ C_BM,k²).
    total = report["capex"]["capex.total"]
    bm = [v for k, v in report["capex"].items() if k.startswith("capex.bare_module.")]
    r = total / sum(bm)
    lo, hi = unc["linear_interval"]["capex.total"]
    assert lo == pytest.approx(0.7 * total, rel=1e-12) and hi == pytest.approx(
        1.5 * total, rel=1e-12
    )
    sigma = r * 0.8 / math.sqrt(12.0) * math.sqrt(sum(v * v for v in bm))
    assert unc["rss_sigma"]["capex.total"] == pytest.approx(sigma, rel=1e-12)
    # The document's range on the electricity price; EL < 0 (generation netted), so the interval
    # is [1.2 EL, 0.8 EL].
    el = report["opex"]["opex.utility.EL"]
    assert el < 0.0
    lo, hi = unc["linear_interval"]["opex.utility.EL"]
    assert lo == pytest.approx(1.2 * el, rel=1e-12) and hi == pytest.approx(0.8 * el, rel=1e-12)
    ranged = {p["theta"]: p["relative_range"] for p in unc["parameters"]}
    assert ranged["asm:utility.EL.price"] == [-0.2, 0.2]
    assert ranged["asm:item.P.accuracy"] == [-0.3, 0.5]


def test_declared_ranges_on_structural_or_unknown_theta_are_refused(registered: None) -> None:
    document = {
        **P1_DOC,
        "uncertainty": {
            "asm:operation.discount_rate": {"relative_range": [-0.1, 0.1]},
            "asm:item.NOPE.U": {"relative_range": [-0.1, 0.1]},
        },
    }
    report = _report("TH-C1", document)
    codes = {(r["code"], r["target"]) for r in report["refusals"]}
    assert ("ASSESSMENT_PARAMETER_STRUCTURAL", "asm:operation.discount_rate") in codes
    assert ("ASSESSMENT_VARIABLE_UNKNOWN", "asm:item.NOPE.U") in codes
    assert report["status"] == "PARTIAL"


def test_a23_extrapolated_item_makes_the_report_class_none(registered: None) -> None:
    from test_e01_a_contributor_c1 import _program as c1_program  # noqa: PLC0415

    items = {**C1_DOC["items"], "B": {"F_BM": 3.17, "allow_extrapolation": True}}
    program, state = c1_program({**C1_DOC, "items": items}, pump_outlet=1.6e7)
    assert isinstance(program, AssessmentProgram)
    report = program.report(state, state_sha256="0" * 64)
    assert (
        report["uncertainty"]["aace_class"] is None and report["uncertainty"]["aace_range"] is None
    )
    assert any(lim["code"] == "CORRELATION_EXTRAPOLATED" for lim in report["limitations"])


def test_derived_undefined_at_the_reported_state(registered: None) -> None:
    binding, host, state = _solved("TH-C1")
    w = state["P.W"]
    document = {
        **P1_DOC,
        "derived": [
            {
                "id": "r",
                "unit": "1",
                "numerator": {"terms": {"tac": 1.0}},
                "denominator": {"terms": {"size.P.power": 1.0}, "constant": -0.999 * w},
            },
            {"id": "s", "unit": "1", "numerator": {"terms": {"derived.r": 2.0}}},
        ],
    }
    program, _, digest = _program("TH-C1", document)
    assert isinstance(program.evaluate(state)["derived.r"], float)  # type: ignore[index]
    x = {**state, "P.W": 0.99 * w}
    report = program.report(x, state_sha256=digest, uncertainty=False)
    assert ("METRIC_UNDEFINED", "derived.r") in {
        (r["code"], r["target"]) for r in report["refusals"]
    }
    assert report["derived"] == {"derived.r": None, "derived.s": None}
    assert report["status"] == "PARTIAL"


def test_statement_is_verbatim(registered: None) -> None:
    report = _report("TH-R1", P1R_DOC)
    assert report["statement"] == (
        "Assessment evidence: an estimate under the stated basis, correlations, data and regimes. "
        "It is not numerical verification of the flowsheet and not empirical validation."
    )


# -- fixture writer --------------------------------------------------------------------------------


def _write() -> None:
    (FIXTURES / "valid").mkdir(parents=True, exist_ok=True)
    (FIXTURES / "invalid").mkdir(parents=True, exist_ok=True)
    with _registered():
        for name, (case, document) in CASES.items():
            report = _report(case, document)
            assert schema_errors(SCHEMA_REFERENCE, report) == [], name
            text = json.dumps(report, indent=1, sort_keys=True, ensure_ascii=False, allow_nan=False)
            (FIXTURES / "valid" / f"{name}.json").write_text(text + "\n", encoding="utf-8")
            if name == "p1_th_r1":
                bad = copy.deepcopy(report)
                bad["capex"]["capex.total"] = "1e6"
                invalid = {"expect_error": "is not of type", "document": bad}
                path = FIXTURES / "invalid" / "string_output_value.json"
                path.write_text(
                    json.dumps(invalid, indent=1, sort_keys=True, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )


if __name__ == "__main__":
    if sys.argv[1:] != ["--write"]:
        raise SystemExit("usage: python tests/test_e01_a_report.py --write")
    _write()
