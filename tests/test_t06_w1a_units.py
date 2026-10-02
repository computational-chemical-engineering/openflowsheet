"""T06 W1a: STA-03 through the four readers (T06 spec §8.5, Amendments 1 and 2; ADR 0001
D1.3–D1.4 as widened by ADR 0016; ADR 0014 D6 as amended; register R-077). Assertions A55–A57.

Since W12 the converter is `unit-conversion-v2` (ADR 0016): A58 (v1's known answers) is superseded
by A67 in `test_t06_w12_units_v2.py`, which also holds the steps V0–V5; A57 (a) is re-pointed from
`degF` (now converted) to `°C` (A2). STA-03's two conversions and A56's control take the same
values under v2 (`units_v2.sta03_and_a02_control_unchanged_from_v1`, asserted below).

The expectation is the twin's, not ours: STA-03's two conversions are exact —
`fl(26.85 + 273.15) = 300.0`, `fl(0.1 / 0.1) = 1.0` (generator-checked) — so each converted
revision *is* SYN-001-nominal, and its trace and certificate are compared with nominal's byte for
byte, on the legacy tear path (A55) and on the revision path (A56). A56's control on reader R3
(`verify_bound`'s `_revision_values`) is A02-360 with its flash temperature and heater guess
written in degC: `fl(86.85 + 273.15) = 360.0`, `fl(84.85 + 273.15) = 358.0`.

**Policy.** The spec runs the revision path under `T06-revision-v1` (`T05b-v2` with only
`eo_recovery = homotopy_or_sequential_restart`, ADR 0015). That value does not exist in code until
F4's WO1 lands, so A56 is run here under `T05b-v2`; neither SYN-001-nominal nor its twins reach an
EO recovery, and the comparison is twin against twin under one policy.
"""

from __future__ import annotations

import copy
from collections.abc import Callable
from functools import cache
from typing import Any

import pytest
from conftest import REPO_ROOT, load_yaml
from t05b_support import POLICY_V2
from test_t04_edge3 import plan_run, region_step

from openflowsheet.application.binding import Binding, Unbound, bind_revision_or_reason
from openflowsheet.application.revision_binding import RevisionBinding, bind_revision_flowsheet
from openflowsheet.application.validation import ValidationReport, validate
from openflowsheet.canonical import canonical_json
from openflowsheet.models.revision_flowsheet import MOLECULAR_WEIGHTS, parse_revision
from openflowsheet.models.syn001.conversion_reactor import MOLAR_MASSES
from openflowsheet.orchestrator.execution import ExecutionPlan
from openflowsheet.orchestrator.executor import execute_plan
from openflowsheet.orchestrator.revision import plan_revision
from openflowsheet.orchestrator.tear import solve_tear
from openflowsheet.orchestrator.trace import SolvePolicy, Trace
from openflowsheet.thermo.syn001 import Syn001Provider
from openflowsheet.units import UnitConversion
from openflowsheet.verify.certificate import (
    SolutionCertificate,
    verify,
    verify_bound,
    verify_revision,
)

Document = dict[str, Any]

REFERENCE = load_yaml(REPO_ROOT / "benchmarks" / "t06" / "reference_values.yaml")
UNITS = REFERENCE["closed_form"]["unit_conversion_v1"]
UNITS_V2 = REFERENCE["closed_form"]["unit_conversion_v2"]

NOMINAL = REPO_ROOT / "benchmarks" / "syn001" / "cases" / "SYN-001-nominal.yaml"
A02_360 = REPO_ROOT / "benchmarks" / "syn001" / "cases" / "SYN-001-A02-360.yaml"
T06_CASES = REPO_ROOT / "benchmarks" / "t06" / "cases"

#: STA-03's two variants, their converted specification and the known answer each must equal.
STA03: dict[str, tuple[str, dict[str, Any]]] = {
    "SYN-001-T06-STA03-kgs": ("SPEC-feed-n-A", UNITS["known_answers"]["mass_basis"][0]),
    "SYN-001-T06-STA03-degC": ("SPEC-feed-T", UNITS["known_answers"]["degC"][0]),
}

#: The seven values `Syn001Flowsheet` is parameterized by (A55).
SETTINGS = (
    "components",
    "feed_flows",
    "feed_temperature",
    "pressure",
    "heater_temperature",
    "flash_temperature",
    "split_fraction",
)


def document(path: Any) -> Document:
    return copy.deepcopy(_load(str(path)))


@cache
def _load(path: str) -> Document:
    loaded: Document = load_yaml(REPO_ROOT / path)
    return loaded


def case(name: str) -> Document:
    return document(T06_CASES / f"{name}.yaml")


def specification(revision: Document, name: str) -> Document:
    entry: Document
    (entry,) = (s for s in revision["specifications"] if s["id"] == name)
    return entry


def checks(report: ValidationReport) -> dict[str, Any]:
    return {check.id: check for check in report.checks}


def legacy(revision: Document) -> Binding:
    binding = bind_revision_or_reason(revision)
    assert isinstance(binding, Binding), binding
    return binding


def bits(value: Any) -> Any:
    """A value with every float as its bit pattern, so equality is bit for bit."""
    if isinstance(value, float):
        return value.hex()
    if isinstance(value, tuple | list):
        return [bits(item) for item in value]
    return value


def events(trace: Trace) -> tuple[bytes, ...]:
    return tuple(canonical_json(event.as_document()) for event in trace.events)


def expected_record(name: str, answer: dict[str, Any]) -> UnitConversion:
    """The record a conversion must yield, from the twin's known answer (§8.5 *Records*)."""
    mass = answer["rule"] == "mass_to_molar"
    return UnitConversion(
        source="specification",
        input_id=name,
        value=float(answer["value"]),
        unit=answer["unit"],
        si_value=float.fromhex(answer["si_value_hex"]),
        si_unit=answer["si_unit"],
        rule=answer["rule"],
        component=answer["component"] if mass else None,
        molar_mass=float(answer["molar_mass_kg_per_mol"]) if mass else None,
    )


# -- the molecular-weight table (§8.5) -----------------------------------------------------------


def test_molecular_weights_equal_the_component_records() -> None:
    records = load_yaml(REPO_ROOT / "benchmarks" / "syn001" / "components.yaml")["components"]
    assert dict(MOLECULAR_WEIGHTS) == {
        record["id"]: record["molecular_weight"]["value"] for record in records
    }
    assert dict(MOLECULAR_WEIGHTS) == UNITS["syn001_molar_mass_kg_per_mol"]


def test_the_reactor_molar_masses_are_the_table_in_the_provider_order() -> None:
    order = Syn001Provider().describe().components
    assert tuple(MOLECULAR_WEIGHTS[component] for component in order) == MOLAR_MASSES


def test_sta03_and_the_a56_control_take_v1s_values_under_v2() -> None:
    """The v1 known answers this file reads are the values v2 registers for them (ADR 0016 D2)."""
    v1 = {
        (float(answer["value"]), answer["unit"]): answer["si_value_hex"]
        for answer in UNITS["known_answers"]["degC"] + UNITS["known_answers"]["mass_basis"]
        if answer.get("molar_mass_table", "SYN-001") == "SYN-001"
    }
    v2 = {
        (float(answer["value"]), answer["unit"]): answer["v2_hex"]
        for answer in UNITS_V2["known_answers"]["v1_known_answers_under_v2"]
        if answer.get("molar_mass_table", "SYN-001") == "SYN-001"
    }
    for name, answer in STA03.values():
        key = (float(answer["value"]), answer["unit"])
        assert float.fromhex(v1[key]).hex() == float.fromhex(v2[key]).hex(), name
    for control in (86.85, 84.85):
        assert (
            float.fromhex(v2[(control, "degC")]).hex() == float.fromhex(v1[(control, "degC")]).hex()
        )


# -- A55: STA-03 on the legacy path --------------------------------------------------------------


@cache
def tear_solved(name: str) -> tuple[tuple[bytes, ...], bytes, str]:
    """`solve_tear` (`SYN-001-K03`) and `verify` of a case (or nominal): the trace's events and
    the certificate, canonical bytes, and its verdict."""
    revision = document(NOMINAL) if name == "nominal" else case(name)
    flowsheet = legacy(revision).flowsheet
    result, trace = solve_tear(flowsheet)
    assert result.outcome == "CONVERGED", result.message
    certificate = verify(flowsheet, result)
    return events(trace), canonical_json(certificate.as_document()), certificate.verification_status


@pytest.mark.parametrize("name", STA03)
def test_a55_validation_records_the_conversion(name: str) -> None:
    converted, answer = STA03[name]
    report = validate(case(name))
    nominal = validate(document(NOMINAL))
    assert report.status == "READY_FOR_SIMULATION"
    found = checks(report)
    assert found["DIM-01"].result == "PASS"
    assert found["DIM-01"].stage == "dimensions"
    assert found["DIM-01"].implicated_objects == (converted,)
    if answer["rule"] == "mass_to_molar":
        assert "0.1 kg/s -> 1.0 mol/s" in found["DIM-01"].message
        assert "(M_A = 0.1 kg/mol)" in found["DIM-01"].message
    else:
        assert "26.85 degC -> 300.0 K" in found["DIM-01"].message
    assert found["DIM-01"].message.startswith("converted by unit-conversion-v2: ")
    assert found["COMP-03"].result == "PASS"
    structural = {k: v.as_document() for k, v in found.items() if k.startswith("STR-")}
    assert structural == {
        k: v.as_document() for k, v in checks(nominal).items() if k.startswith("STR-")
    }
    assert checks(nominal)["DIM-01"].message == (
        "every specification and parameter is in its kind's internal SI unit"
    )


@pytest.mark.parametrize("name", STA03)
def test_a55_the_legacy_binding_reads_nominal_bit_for_bit(name: str) -> None:
    converted, answer = STA03[name]
    binding = legacy(case(name))
    nominal = legacy(document(NOMINAL))
    assert binding.input_mapping.conversions == (expected_record(converted, answer),)
    assert nominal.input_mapping.conversions == ()
    for setting in SETTINGS:
        assert bits(getattr(binding.flowsheet, setting)) == bits(
            getattr(nominal.flowsheet, setting)
        ), setting
    assert bits(list(binding.spec.parameters.values())) == bits(
        list(nominal.spec.parameters.values())
    )
    assert binding.spec.variable_ids == nominal.spec.variable_ids


@pytest.mark.parametrize("name", STA03)
def test_a55_the_tear_solve_and_certificate_are_nominals(name: str) -> None:
    trace, certificate, status = tear_solved(name)
    nominal_trace, nominal_certificate, _ = tear_solved("nominal")
    assert status == "VERIFIED"
    assert trace == nominal_trace
    assert certificate == nominal_certificate


# -- A56: STA-03 on the revision path, and reader R3 ----------------------------------------------


def revision_bound(revision: Document) -> RevisionBinding:
    binding = bind_revision_flowsheet(revision)
    assert isinstance(binding, RevisionBinding), binding
    return binding


@cache
def revision_solved(name: str, policy: SolvePolicy = POLICY_V2) -> tuple[tuple[bytes, ...], bytes]:
    revision = document(NOMINAL) if name == "nominal" else case(name)
    binding = revision_bound(revision)
    plan, _ = plan_revision(binding, policy)
    assert isinstance(plan, ExecutionPlan), plan
    run = execute_plan(plan=plan, flowsheet=binding.flowsheet, spec=binding.spec, policy=policy)
    assert run.outcome == "CONVERGED", run.outcome
    certificate: SolutionCertificate = verify_revision(
        binding, revision, run, solve_plan=plan.steps[-1].solve_plan
    )
    assert certificate.verification_status == "VERIFIED"
    return events(run.trace), canonical_json(certificate.as_document())


@pytest.mark.parametrize("name", STA03)
def test_a56_the_revision_binding_reads_nominal_bit_for_bit(name: str) -> None:
    converted, answer = STA03[name]
    binding = revision_bound(case(name))
    nominal = revision_bound(document(NOMINAL))
    assert binding.input_mapping.conversions == (expected_record(converted, answer),)
    assert nominal.input_mapping.conversions == ()
    pins = {i.unit_id: bits(list(i.pins.items())) for i in parse_revision(case(name)).instances}
    assert pins == {
        i.unit_id: bits(list(i.pins.items())) for i in parse_revision(document(NOMINAL)).instances
    }
    assert binding.flowsheet.label == nominal.flowsheet.label
    assert binding.spec.variable_ids == nominal.spec.variable_ids
    assert bits(list(binding.spec.parameters.items())) == bits(
        list(nominal.spec.parameters.items())
    )


@pytest.mark.parametrize("name", STA03)
def test_a56_the_revision_solve_and_certificate_are_nominals(name: str) -> None:
    assert revision_solved(name) == revision_solved("nominal")


def _a02_celsius(revision: Document) -> None:
    specification(revision, "SPEC-flash-T").update(value=86.85, unit="degC")
    specification(revision, "GUESS-heater-outlet-T").update(value=84.85, unit="degC")


@cache
def a02_solved(celsius: bool) -> tuple[Binding, tuple[bytes, ...], bytes]:
    """A02-360 on the legacy EO path (the plan's pre-solve and region, `verify_bound`)."""
    revision = document(A02_360)
    if celsius:
        _a02_celsius(revision)
    run = plan_run(revision, SolvePolicy(policy_id="T04-W12", residual_tolerances={}, scales={}))
    step = region_step(run.result)
    assert step.outcome == "CONVERGED"
    (planned,) = [s for s in run.plan.steps if s.kind == "solve_eo"]
    binding = legacy(revision)
    certificate = verify_bound(binding, revision, step.detail, solve_plan=planned.solve_plan)
    assert certificate.verification_status == "VERIFIED"
    return binding, events(run.result.trace), canonical_json(certificate.as_document())


def test_a56_control_verify_bound_reads_the_converted_values() -> None:
    """Reader R3: without it `_revision_values` would judge `S4.T` against 86.85 K, a false
    `FAILED`; with it the binding, the executor trace and the certificate are A02-360's."""
    binding, trace, certificate = a02_solved(True)
    twin, twin_trace, twin_certificate = a02_solved(False)
    assert [record.rule for record in binding.input_mapping.conversions] == ["degC_to_K"] * 2
    # Specification order: A02-360 declares the heater guess before the flash temperature.
    assert [record.si_value for record in binding.input_mapping.conversions] == [358.0, 360.0]
    assert bits(list(binding.guesses.items())) == bits(list(twin.guesses.items()))
    assert bits(list(binding.spec.parameters.items())) == bits(list(twin.spec.parameters.items()))
    for setting in SETTINGS:
        assert bits(getattr(binding.flowsheet, setting)) == bits(getattr(twin.flowsheet, setting))
    assert trace == twin_trace
    assert certificate == twin_certificate


# -- A57: negative and alternate encodings --------------------------------------------------------


def _with(name: str, spec_id: str, **changes: Any) -> Callable[[], Document]:
    def build() -> Document:
        revision = case(name)
        specification(revision, spec_id).update(**changes)
        return revision

    return build


REFUSED = {
    # (A2) re-pointed from `degF`, which `unit-conversion-v2` converts (to 270.29 K).
    "°C": (
        _with("SYN-001-T06-STA03-degC", "SPEC-feed-T", unit="°C"),
        "SPEC-feed-T",
        "specification_unit_unsupported(SPEC-feed-T)",
    ),
    "K-on-a-flow": (
        _with("SYN-001-T06-STA03-kgs", "SPEC-feed-n-A", unit="K"),
        "SPEC-feed-n-A",
        "specification_unit_unsupported(SPEC-feed-n-A)",
    ),
    "temperature-kind-on-a-flow": (
        _with("SYN-001-T06-STA03-kgs", "SPEC-feed-n-A", kind="temperature"),
        "SPEC-feed-n-A",
        "specification_kind_unsupported(SPEC-feed-n-A)",
    ),
}


@pytest.mark.parametrize("encoding", REFUSED)
def test_a57_an_unconverted_unit_or_kind_is_refused(encoding: str) -> None:
    build, spec_id, code = REFUSED[encoding]
    report = validate(build())
    assert report.status == "INVALID"
    found = checks(report)["DIM-01"]
    assert bind_revision_or_reason(build()) == Unbound("unsupported", code, (spec_id,))
    refused = bind_revision_flowsheet(build())
    assert isinstance(refused, Unbound)
    assert (refused.kind, refused.detail) == ("unsupported", code)
    # T07 ruling round 6, B2: DIM-01 reports the code with its hint, the binders' own.
    assert refused.hint is not None
    assert (found.result, found.message, found.implicated_objects) == (
        "FAIL",
        f"{code}. {refused.hint}",
        (spec_id,),
    )


def test_a57_the_mass_flow_kind_converts_exactly_as_the_fixture() -> None:
    build = _with("SYN-001-T06-STA03-kgs", "SPEC-feed-n-A", kind="mass_flow")
    fixture = case("SYN-001-T06-STA03-kgs")
    assert checks(validate(build()))["DIM-01"] == checks(validate(fixture))["DIM-01"]
    assert legacy(build()).input_mapping == legacy(fixture).input_mapping
    assert bits(legacy(build()).flowsheet.feed_flows) == bits(legacy(fixture).flowsheet.feed_flows)
    assert revision_bound(build()).input_mapping == revision_bound(fixture).input_mapping


# -- the legacy binding's other refusals (§8.5) ---------------------------------------------------


def _parameter(instance: str, name: str, **changes: Any) -> Document:
    revision = document(NOMINAL)
    (entry,) = (i for i in revision["instances"] if i["id"] == instance)
    entry["parameters"][name].update(**changes)
    return revision


@pytest.mark.parametrize(
    ("revision", "where", "code"),
    [
        (
            _parameter("splitter", "split_fraction", dimension=[0, 0, 0, 0, 0, 0, 1]),
            "splitter.split_fraction",
            "parameter_quantity_invalid(splitter.split_fraction)",
        ),
        (
            # (A2) re-pointed from `kPa`, which `unit-conversion-v2` converts (ADR 0016 D9).
            _parameter("mixer", "pressure_drop", unit="mmHg"),
            "mixer.pressure_drop",
            "parameter_unit_unsupported(mixer.pressure_drop)",
        ),
        (
            _parameter("heater", "pressure_drop", kind="dimensionless", unit="1"),
            "heater.pressure_drop",
            "parameter_kind_unsupported(heater.pressure_drop)",
        ),
    ],
    ids=["quantity", "unit", "kind"],
)
def test_a_parameter_outside_the_table_is_refused_alike(
    revision: Document, where: str, code: str
) -> None:
    found = checks(validate(revision))["DIM-01"]
    assert (found.result, found.message, found.implicated_objects) == ("FAIL", code, (where,))
    assert bind_revision_or_reason(revision) == Unbound("unsupported", code, (where,))


def test_str06_component_references_are_checked() -> None:
    """COMP-03 (§8.5, unchanged by A1) and the legacy binding's `component_unknown` (R-071)."""
    revision = case("SYN-001-T06-STR06")
    report = validate(revision)
    assert report.status == "INVALID"
    found = checks(report)["COMP-03"]
    assert (found.result, found.stage, found.implicated_objects) == (
        "FAIL",
        "component_reference_compatibility",
        ("SPEC-feed-n-B",),
    )
    assert "'D'" in found.message and "['A', 'B', 'C']" in found.message
    assert checks(report)["DIM-01"].result == "PASS"
    assert bind_revision_or_reason(revision) == Unbound(
        "conflict", "component_unknown(SPEC-feed-n-B, D)", ("SPEC-feed-n-B",)
    )


def test_comp03_reads_component_keyed_parameter_names() -> None:
    revision = document(NOMINAL)
    (splitter,) = (i for i in revision["instances"] if i["id"] == "splitter")
    splitter["parameters"]["split.D"] = copy.deepcopy(splitter["parameters"]["split_fraction"])
    found = checks(validate(revision))["COMP-03"]
    assert (found.result, found.implicated_objects) == ("FAIL", ("splitter.split.D",))
