"""T05 W8: `syn001.heat_exchanger` against the registered cases (spec §10; A12, A13, A14, A16).

Every input and every expected value is read from `benchmarks/t05/reference_values.yaml`, the
design lane's 40-digit twin, which is independent of this implementation: no number is copied into
this file. Tolerances are spec §14's unit-case tolerances (`constants.tolerances` in the YAML).

**A12 is about order, not only about the first failure.** Each registered failure case fails one
check of §10.2 and passes every other, and the YAML registers the full list as
`expected.failures`. `HeatExchanger.assess` evaluates every check it can and returns them all, so
the tests below compare the whole list, and then that `evaluate` answers with its first entry.
The YAML also registers the state each failure case is judged at (duty, terminal differences,
outlet temperatures); those are compared too, so a case cannot fail "for the right reason" at the
wrong state.

The trial-state row values and Jacobians (A04, A05) are another harness's; this file checks only
that `contribute()` authors exactly the registered row ids with the registered kinds.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest
from conftest import REPO_ROOT, load_yaml
from t05_trial_states import TrialUnit, compare_trial_state
from test_schemas_p01 import schema_errors

from openflowsheet.compiled import EvaluationContext
from openflowsheet.models import SpecificationError, UnitEvaluation, Wiring, origin
from openflowsheet.models.syn001 import COMPONENTS
from openflowsheet.models.syn001.heat_exchanger import MODEL_ID, HeatExchanger
from openflowsheet.thermo import StreamState
from openflowsheet.thermo.syn001 import Syn001Provider

REF: dict[str, Any] = load_yaml(REPO_ROOT / "benchmarks" / "t05" / "reference_values.yaml")
TOLERANCES: Mapping[str, str] = REF["constants"]["tolerances"]
T_TOL = float(TOLERANCES["temperature"])
FLOW_TOL = float(TOLERANCES["molar_flow"])
DUTY_TOL = float(TOLERANCES["heat_rate"])

CONTEXT = EvaluationContext(
    model_version="T05-unit-evaluator@" + "0" * 64, constants_sha256="0" * 64
)
PROVIDER = Syn001Provider()

CASES: dict[str, Any] = {
    case_id: case for case_id, case in REF["unit_cases"].items() if case["model"] == MODEL_ID
}
CASE_IDS = sorted(CASES)
FAILURE_IDS = sorted(case_id for case_id, case in CASES.items() if "failures" in case["expected"])
TRIAL_STATES: dict[str, Any] = REF["trial_states"][MODEL_ID]["states"]
PORTS = ("hot_outlet", "cold_outlet")


def stream(document: Mapping[str, Any]) -> StreamState:
    return StreamState(
        n=tuple(float(value) for value in document["n_mol_per_s"]),
        temperature=float(document["T_K"]),
        pressure=float(document["P_Pa"]),
    )


def exchanger(inputs: Mapping[str, Any], unit_id: str = "U-HX") -> HeatExchanger:
    return HeatExchanger(
        unit_id=unit_id,
        provider=PROVIDER,
        specification=inputs["specification"],
        value=float(inputs["value"]),
        context=CONTEXT,
        hot_phase=inputs["hot_phase"],
        cold_phase=inputs["cold_phase"],
    )


def inlets(inputs: Mapping[str, Any]) -> dict[str, list[StreamState]]:
    return {port: [stream(inputs[port])] for port in ("hot_inlet", "cold_inlet")}


def run(case_id: str) -> UnitEvaluation:
    inputs = CASES[case_id]["inputs"]
    return exchanger(inputs).evaluate(inlets(inputs), CONTEXT)


def first_line(message: str) -> str:
    return message.splitlines()[0] if message else ""


def assert_stream(got: StreamState, want: Mapping[str, Any], label: str) -> None:
    assert got.temperature == pytest.approx(float(want["T_K"]), rel=0.0, abs=T_TOL), label
    assert got.pressure == float(want["P_Pa"]), label
    for value, registered in zip(got.n, want["n_mol_per_s"], strict=True):
        if float(registered) == 0.0:
            assert value == 0.0, label
        else:
            assert value == pytest.approx(float(registered), rel=0.0, abs=FLOW_TOL), label


def test_every_registered_exchanger_case_is_exercised() -> None:
    """A12 names HX-1…5, Z0, Z1, F1…F4; a case silently dropped from the YAML would shrink it."""
    assert CASE_IDS == [
        "HX-1", "HX-2", "HX-3", "HX-4", "HX-5",
        "HX-F1", "HX-F2", "HX-F3", "HX-F4", "HX-Z0", "HX-Z1",
    ]  # fmt: skip
    assert FAILURE_IDS == ["HX-F1", "HX-F2", "HX-F3", "HX-F4"]


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_registered_case(case_id: str) -> None:
    expected = CASES[case_id]["expected"]
    result = run(case_id)

    assert result.status == expected["status"]
    # A16: the first line is the registered code, byte for byte; '' for an `ok` answer.
    assert first_line(result.message) == expected["code"]
    # No energy port: the unit has no duty at all, which is not a zero duty.
    assert result.duty is None
    if result.status != "ok":
        assert result.outlets == {}
        assert result.transferred_duty is None
        return

    assert result.phase_signature == expected["signature"]
    assert result.transferred_duty is not None
    assert result.transferred_duty == pytest.approx(
        float(expected["duty_W"]), rel=0.0, abs=DUTY_TOL
    )
    assert result.work is None and result.extent is None
    for port in PORTS:
        assert_stream(result.outlets[port], expected[port], f"{case_id} {port}")


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_the_assessment_lists_exactly_the_registered_failures(case_id: str) -> None:
    """A12: a failure case fails its one registered check and passes every other one.

    `assess` runs (5)–(8) all, so an equal list is the statement "and every other check passes";
    an `ok` case has an empty list. Where the YAML registers the state the checks were judged at,
    it is compared as well.
    """
    case = CASES[case_id]
    expected = case["expected"]
    inputs = case["inputs"]
    assessment = exchanger(inputs).assess(inlets(inputs), CONTEXT)

    registered = expected.get("failures", [expected["code"]] if expected["code"] else [])
    assert list(assessment.failures) == registered
    result = exchanger(inputs).evaluate(inlets(inputs), CONTEXT)
    assert first_line(result.message) == (registered[0] if registered else "")

    if "duty_W" in expected:
        assert assessment.transferred_duty is not None
        assert assessment.transferred_duty == pytest.approx(
            float(expected["duty_W"]), rel=0.0, abs=DUTY_TOL
        )
    for key, value in (("hot_end_K", assessment.hot_end), ("cold_end_K", assessment.cold_end)):
        if key in expected:
            assert value is not None
            assert value == pytest.approx(float(expected[key]), rel=0.0, abs=T_TOL), key
    for port in PORTS:
        if port in expected:
            got = assessment.hot_outlet if port == "hot_outlet" else assessment.cold_outlet
            assert got is not None
            assert_stream(got, expected[port], f"{case_id} {port}")


@pytest.mark.parametrize("case_id", FAILURE_IDS)
def test_the_registered_state_fails_only_its_registered_second_law_check(case_id: str) -> None:
    """§10.2 (6)–(8) restated on the registered numbers alone, independent of the implementation.

    The YAML's duty and terminal differences must violate exactly the second-law checks its
    `failures` list names (a pinch, a difference of exactly zero, is allowed), so the order that
    the assessment test pins is the order of the specification and not of this code.
    """
    expected = CASES[case_id]["expected"]
    violated = []
    if float(expected["duty_W"]) < 0.0:
        violated.append("heat_flow_reversed")
    if float(expected["hot_end_K"]) < 0.0:
        violated.append("temperature_cross(hot_end)")
    if float(expected["cold_end_K"]) < 0.0:
        violated.append("temperature_cross(cold_end)")
    second_law = [code for code in expected["failures"] if not code.startswith("inadmissible")]
    assert violated == second_law


def test_the_three_specifications_give_one_state() -> None:
    """A13: HX-1, HX-2 and HX-3 fix the same exchanger by the three modes; they agree to §14."""
    results = [run(case_id) for case_id in ("HX-1", "HX-2", "HX-3")]
    assert [result.status for result in results] == ["ok", "ok", "ok"]
    reference = results[0]
    assert reference.transferred_duty is not None
    for other in results[1:]:
        assert other.transferred_duty is not None
        assert other.transferred_duty == pytest.approx(
            reference.transferred_duty, rel=0.0, abs=DUTY_TOL
        )
        for port in PORTS:
            got, want = other.outlets[port], reference.outlets[port]
            assert got.temperature == pytest.approx(want.temperature, rel=0.0, abs=T_TOL)
            assert (got.n, got.pressure) == (want.n, want.pressure)


def test_a_zero_duty_returns_the_inlets_exactly() -> None:
    """HX-5: with Q = 0 the inversion starts at the inlet temperature and is already at the root."""
    inputs = CASES["HX-5"]["inputs"]
    result = run("HX-5")
    assert result.transferred_duty == 0.0
    assert result.outlets["hot_outlet"] == stream(inputs["hot_inlet"])
    assert result.outlets["cold_outlet"] == stream(inputs["cold_inlet"])


def test_a_dormant_side_keeps_its_label_and_moves_exactly_no_heat() -> None:
    """A14: HX-Z0's dormant hot side keeps its registered label; the transferred heat is 0.0."""
    expected = CASES["HX-Z0"]["expected"]
    result = run("HX-Z0")
    assert result.status == "ok"
    assert result.transferred_duty == 0.0
    hot = result.outlets["hot_outlet"]
    assert hot.n == (0.0, 0.0, 0.0)
    assert hot.temperature == float(expected["hot_outlet"]["T_K"])
    assert result.outlets["cold_outlet"] == stream(CASES["HX-Z0"]["inputs"]["cold_inlet"])


@pytest.mark.parametrize(
    ("specification", "satisfiable"),
    [
        ("hot_outlet_temperature", True),  # on the dormant side: its label
        ("cold_outlet_temperature", False),  # moves the flowing side: needs heat
    ],
)
def test_a_dormant_side_admits_only_a_specification_q_zero_can_meet(
    specification: str, satisfiable: bool
) -> None:
    """§10.2 (1): an outlet temperature on the dormant side becomes its label; one that would
    move the flowing side is HX-Z1's typed error. The value is HX-1's registered hot outlet."""
    inputs = {
        **CASES["HX-Z1"]["inputs"],
        "specification": specification,
        "value": CASES["HX-1"]["expected"]["hot_outlet"]["T_K"],
    }
    result = exchanger(inputs).evaluate(inlets(inputs), CONTEXT)
    if satisfiable:
        assert result.status == "ok"
        assert result.transferred_duty == 0.0
        assert result.outlets["hot_outlet"].temperature == float(inputs["value"])
        assert result.outlets["cold_outlet"] == stream(inputs["cold_inlet"])
    else:
        assert result.status == "error"
        assert first_line(result.message) == "specification_unsatisfiable_with_dormant_side"


def test_the_flowing_sides_own_inlet_temperature_is_satisfiable_with_a_dormant_side() -> None:
    inputs = {**CASES["HX-Z1"]["inputs"]}
    inputs["value"] = inputs["cold_inlet"]["T_K"]
    result = exchanger(inputs).evaluate(inlets(inputs), CONTEXT)
    assert result.status == "ok"
    assert result.transferred_duty == 0.0
    assert result.outlets["cold_outlet"] == stream(inputs["cold_inlet"])


def test_a_pinch_is_allowed() -> None:
    """§10.2: a terminal difference of exactly zero is not a cross. HX-1 with the cold outlet at
    the hot inlet's temperature pinches the hot end exactly."""
    inputs = {**CASES["HX-1"]["inputs"]}
    inputs["value"] = inputs["hot_inlet"]["T_K"]
    assessment = exchanger(inputs).assess(inlets(inputs), CONTEXT)
    assert assessment.hot_end == 0.0
    assert assessment.failures == ()
    assert exchanger(inputs).evaluate(inlets(inputs), CONTEXT).status == "ok"


def test_hx_s1_is_refused_at_construction_with_its_code() -> None:
    """A16: HX-S1's refusal is a `SpecificationError` whose first line is the registered code."""
    registered = REF["specification_errors"]["HX-S1"]
    assert registered["model"] == MODEL_ID
    inputs = {**CASES["HX-1"]["inputs"], **registered["change_from_nominal"]}
    with pytest.raises(SpecificationError) as refused:
        exchanger(inputs)
    assert first_line(str(refused.value)) == registered["code"]


@pytest.mark.parametrize("state_id", sorted(TRIAL_STATES))
def test_contribute_authors_exactly_the_registered_rows(state_id: str) -> None:
    """The row ids and kinds of `ref.trial_states.<model>.<J>.rows`, and nothing else."""
    state = TRIAL_STATES[state_id]
    configuration = state["configuration"]
    unit = exchanger(
        {**configuration, "value": state["parameters"]["value"]}, unit_id=configuration["unit"]
    )
    wiring = Wiring({port: (configuration[port],) for port in ("hot_inlet", "cold_inlet", *PORTS)})
    contribution = unit.contribute(wiring, COMPONENTS)
    authored = {equation.equation_id for equation in contribution.equations}
    assert authored == set(state["rows"])
    assert len(authored) == len(contribution.equations)
    assert dict(contribution.row_kinds) == {
        row: registered["kind"] for row, registered in state["rows"].items()
    }


def test_rows_trace_to_the_declaration_with_its_accumulation() -> None:
    """Every declared equation authors a row, every row names a declared equation (D4.4)."""
    unit = exchanger(CASES["HX-1"]["inputs"])
    wiring = Wiring(
        {"hot_inlet": ("S1",), "hot_outlet": ("S2",), "cold_inlet": ("S3",), "cold_outlet": ("S4",)}
    )
    declared = {
        origin(MODEL_ID, equation.equation_id): equation.accumulation.kind
        for equation in unit.declared_equations()
    }
    equations = unit.contribute(wiring, COMPONENTS).equations
    assert {equation.origin for equation in equations} == set(declared)
    for equation in equations:
        assert equation.accumulation == declared[equation.origin], equation.equation_id


def test_manifest_validates_and_declares_no_energy_port() -> None:
    document = dict(exchanger(CASES["HX-1"]["inputs"]).manifest())
    assert schema_errors("model_manifest", document) == []
    assert document["id"] == MODEL_ID
    assert document["introduced_by_package"] == "T05"
    assert [port["kind"] for port in document["ports"]] == ["material"] * 4
    requirements = document["execution_requirements"]
    assert requirements["property_provider"] == "syn001"
    assert requirements["reference_convention"] == "SYN-001-ref-v1"


# --------------------------------------------------------------------------- A04/A05


def build_trial(configuration: Mapping[str, Any], parameters: Mapping[str, str]) -> TrialUnit:
    unit = exchanger({**configuration, "value": parameters["value"]}, unit_id=configuration["unit"])
    ports = ("hot_inlet", "hot_outlet", "cold_inlet", "cold_outlet")
    return TrialUnit(
        unit=unit,
        wiring=Wiring({port: (configuration[port],) for port in ports}),
        streams=tuple(configuration[port] for port in ports),
    )


@pytest.mark.parametrize("state_id", sorted(TRIAL_STATES))
def test_rows_and_jacobian_at_the_registered_trial_state(state_id: str) -> None:
    comparison = compare_trial_state(MODEL_ID, state_id, build_trial)
    assert comparison.failures == [], comparison.summary()
