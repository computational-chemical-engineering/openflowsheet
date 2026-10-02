"""T05 W7: `syn001.component_separator` against the registered cases (spec §7; A11, A14, A16).

Every input and every expected value is read from `benchmarks/t05/reference_values.yaml`, the
design lane's 40-digit twin, which is independent of this implementation: no number is copied into
this file. Tolerances are spec §14's unit-case tolerances, which the YAML registers as
`constants.tolerances`; exact zeros (SEP-2's `n_top,C`, the dormant outlets of SEP-3 and SEP-4,
and every flow of SEP-Z) are compared with `==`.

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
from openflowsheet.models import SpecificationError, Wiring, origin
from openflowsheet.models.syn001 import COMPONENTS
from openflowsheet.models.syn001.admission import admitted_enthalpy
from openflowsheet.models.syn001.component_separator import MODEL_ID, ComponentSeparator
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
TRIAL_STATES: dict[str, Any] = REF["trial_states"][MODEL_ID]["states"]


def stream(document: Mapping[str, Any]) -> StreamState:
    return StreamState(
        n=tuple(float(value) for value in document["n_mol_per_s"]),
        temperature=float(document["T_K"]),
        pressure=float(document["P_Pa"]),
    )


def separator(inputs: Mapping[str, Any], unit_id: str = "U-SEP") -> ComponentSeparator:
    return ComponentSeparator(
        unit_id=unit_id,
        provider=PROVIDER,
        split=tuple(float(value) for value in inputs["split"]),
        context=CONTEXT,
        inlet_phase=inputs["inlet_phase"],
        top_phase=inputs["top_phase"],
        bottom_phase=inputs["bottom_phase"],
    )


def first_line(message: str) -> str:
    return message.splitlines()[0] if message else ""


def test_every_registered_separator_case_is_exercised() -> None:
    """A11 names SEP-1…4, Z and F2; a case silently dropped from the YAML would shrink A11."""
    assert CASE_IDS == ["SEP-1", "SEP-2", "SEP-3", "SEP-4", "SEP-F2", "SEP-Z"]


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_registered_case(case_id: str) -> None:
    case = CASES[case_id]
    expected = case["expected"]
    unit = separator(case["inputs"])
    result = unit.evaluate({"inlet": [stream(case["inputs"]["inlet"])]}, CONTEXT)

    assert result.status == expected["status"]
    # A16: the first line is the registered code, byte for byte; '' for an `ok` answer.
    assert first_line(result.message) == expected["code"]
    if result.status != "ok":
        assert result.outlets == {}
        assert result.duty is None
        return

    assert result.phase_signature == expected["signature"]
    assert result.duty is not None
    assert result.duty == pytest.approx(float(expected["duty_W"]), rel=0.0, abs=DUTY_TOL)
    assert result.work is None and result.extent is None and result.transferred_duty is None
    for port in ("top", "bottom"):
        got, want = result.outlets[port], expected[port]
        assert got.temperature == pytest.approx(float(want["T_K"]), rel=0.0, abs=T_TOL)
        assert got.pressure == float(want["P_Pa"])
        for component, value, registered in zip(
            COMPONENTS, got.n, want["n_mol_per_s"], strict=True
        ):
            if float(registered) == 0.0:
                # Spec §14: a registered zero is exact (`s x = 0`, `x - x = 0`), never "small".
                assert value == 0.0, (port, component, value)
            else:
                assert value == pytest.approx(float(registered), rel=0.0, abs=FLOW_TOL), (
                    port,
                    component,
                )


def test_a_dormant_inlet_gives_its_labels_and_exactly_zero_duty() -> None:
    """A14: SEP-Z's outlets keep the inlet's (T, P) as labels and the duty is exactly 0.0."""
    case = CASES["SEP-Z"]
    inlet = stream(case["inputs"]["inlet"])
    result = separator(case["inputs"]).evaluate({"inlet": [inlet]}, CONTEXT)
    assert result.status == "ok"
    assert result.duty == 0.0
    assert result.phase_signature == "ZERO_FLOW"
    for port in ("top", "bottom"):
        outlet = result.outlets[port]
        assert outlet.n == (0.0, 0.0, 0.0)
        assert (outlet.temperature, outlet.pressure) == (inlet.temperature, inlet.pressure)
        assert outlet.temperature == float(case["expected"][port]["T_K"])


def test_sep_f2_fails_only_the_top_phase() -> None:
    """SEP-F2 registers exactly one failure: the inlet and the bottom are admissible as declared,
    so the refusal is the top's and not the first thing the evaluator happened to look at."""
    case = CASES["SEP-F2"]
    inputs = case["inputs"]
    assert case["expected"]["failures"] == [case["expected"]["code"]]
    inlet = stream(inputs["inlet"])
    split = [float(value) for value in inputs["split"]]
    bottom = StreamState(
        n=tuple(flow - s * flow for s, flow in zip(split, inlet.n, strict=True)),
        temperature=inlet.temperature,
        pressure=inlet.pressure,
    )
    for port, state, phase in (
        ("inlet", inlet, inputs["inlet_phase"]),
        ("bottom", bottom, inputs["bottom_phase"]),
    ):
        answer = admitted_enthalpy(
            PROVIDER, COMPONENTS, CONTEXT, unit_id="U-SEP", port=port, stream=state, phase=phase
        )
        assert isinstance(answer, float), (port, answer)


def test_a_declared_inlet_is_admitted_by_r007() -> None:
    """Spec §5.2 (3), applied by §7: a declared inlet phase R-007 refuses is typed, not written.

    The stream is PHF-1's registered two-phase outlet state: its flows at its registered `T`.
    """
    phf1 = REF["unit_cases"]["PHF-1"]
    assert phf1["expected"]["signature"] == "TWO_PHASE"
    feed = StreamState(
        n=tuple(float(value) for value in phf1["inputs"]["inlet"]["n_mol_per_s"]),
        temperature=float(phf1["expected"]["T_K"]),
        pressure=float(phf1["inputs"]["inlet"]["P_Pa"]),
    )
    inputs = dict(CASES["SEP-1"]["inputs"])
    result = separator(inputs).evaluate({"inlet": [feed]}, CONTEXT)
    assert result.status == "unsupported"
    assert first_line(result.message) == "inadmissible_phase(inlet, LIQUID)"


def test_a_lifted_inlet_reads_the_tp_state() -> None:
    """`inlet_phase = None` takes the inlet's enthalpy from its TP state (spec §5.2 (3)).

    On SEP-2's subcooled inlet the TP state *is* liquid, so the answer must agree with the
    declared-liquid inlet to §14 — a metamorphic check that the lifted route is wired at all.
    """
    case = CASES["SEP-2"]
    inputs = dict(case["inputs"])
    declared = separator(inputs).evaluate({"inlet": [stream(inputs["inlet"])]}, CONTEXT)
    inputs["inlet_phase"] = None
    lifted = separator(inputs).evaluate({"inlet": [stream(inputs["inlet"])]}, CONTEXT)
    assert declared.status == lifted.status == "ok"
    assert declared.duty is not None and lifted.duty is not None
    assert lifted.duty == pytest.approx(declared.duty, rel=0.0, abs=DUTY_TOL)
    assert lifted.outlets == declared.outlets


def test_sep_s1_is_refused_at_construction_with_its_code() -> None:
    """A16: SEP-S1's refusal is a `SpecificationError` whose first line is the registered code."""
    registered = REF["specification_errors"]["SEP-S1"]
    assert registered["model"] == MODEL_ID
    inputs = {**CASES["SEP-1"]["inputs"], **registered["change_from_nominal"]}
    with pytest.raises(SpecificationError) as refused:
        separator(inputs)
    assert first_line(str(refused.value)) == registered["code"]


@pytest.mark.parametrize("fraction", [-0.1, float("nan"), float("inf")])
def test_a_split_fraction_outside_the_unit_interval_names_its_component(fraction: float) -> None:
    inputs = dict(CASES["SEP-1"]["inputs"])
    inputs["split"] = [0.5, fraction, 0.5]
    with pytest.raises(SpecificationError) as refused:
        separator(inputs)
    assert first_line(str(refused.value)) == "split_fraction_outside_unit_interval(B)"


@pytest.mark.parametrize("state_id", sorted(TRIAL_STATES))
def test_contribute_authors_exactly_the_registered_rows(state_id: str) -> None:
    """The row ids and kinds of `ref.trial_states.<model>.<J>.rows`, and nothing else."""
    state = TRIAL_STATES[state_id]
    configuration = state["configuration"]
    regime = configuration["inlet_regime"]
    unit = ComponentSeparator(
        unit_id=configuration["unit"],
        provider=PROVIDER,
        split=tuple(float(value) for value in state["parameters"]["split"]),
        context=CONTEXT,
        inlet_phase=None if regime == "lifted" else regime,
        top_phase=configuration["top_phase"],
        bottom_phase=configuration["bottom_phase"],
    )
    wiring = Wiring({port: (configuration[port],) for port in ("inlet", "top", "bottom")})
    contribution = unit.contribute(wiring, COMPONENTS)
    authored = {equation.equation_id for equation in contribution.equations}
    assert authored == set(state["rows"])
    assert len(authored) == len(contribution.equations)
    assert dict(contribution.row_kinds) == {
        row: registered["kind"] for row, registered in state["rows"].items()
    }


def test_rows_trace_to_the_declaration_with_its_accumulation() -> None:
    """Every declared equation authors a row, every row names a declared equation (D4.4)."""
    state = TRIAL_STATES["J1"]
    configuration = state["configuration"]
    unit = separator(
        {
            "split": state["parameters"]["split"],
            "inlet_phase": configuration["inlet_regime"],
            "top_phase": configuration["top_phase"],
            "bottom_phase": configuration["bottom_phase"],
        },
        unit_id=configuration["unit"],
    )
    wiring = Wiring({port: (configuration[port],) for port in ("inlet", "top", "bottom")})
    declared = {
        origin(MODEL_ID, equation.equation_id): equation.accumulation.kind
        for equation in unit.declared_equations()
    }
    equations = unit.contribute(wiring, COMPONENTS).equations
    assert {equation.origin for equation in equations} == set(declared)
    for equation in equations:
        assert equation.accumulation == declared[equation.origin], equation.equation_id


def test_manifest_validates_against_the_frozen_schema() -> None:
    unit = separator(CASES["SEP-1"]["inputs"])
    document = dict(unit.manifest())
    assert schema_errors("model_manifest", document) == []
    assert document["id"] == MODEL_ID
    assert document["introduced_by_package"] == "T05"
    assert document["implementation_artifact"]["planned_package"] == "T05"
    requirements = document["execution_requirements"]
    assert requirements["property_provider"] == "syn001"
    assert requirements["reference_convention"] == "SYN-001-ref-v1"


# --------------------------------------------------------------------------- A04/A05


def build_trial(configuration: Mapping[str, Any], parameters: Mapping[str, str]) -> TrialUnit:
    regime = configuration["inlet_regime"]
    unit = ComponentSeparator(
        unit_id=configuration["unit"],
        provider=PROVIDER,
        split=tuple(float(value) for value in parameters["split"]),
        context=CONTEXT,
        inlet_phase=None if regime == "lifted" else regime,
        top_phase=configuration["top_phase"],
        bottom_phase=configuration["bottom_phase"],
    )
    inlet, top, bottom = configuration["inlet"], configuration["top"], configuration["bottom"]
    return TrialUnit(
        unit=unit,
        wiring=Wiring({"inlet": (inlet,), "top": (top,), "bottom": (bottom,)}),
        streams=(inlet, top, bottom),
        lifted_inlets=(inlet,) if regime == "lifted" else (),
    )


@pytest.mark.parametrize("state_id", sorted(TRIAL_STATES))
def test_rows_and_jacobian_at_the_registered_trial_state(state_id: str) -> None:
    comparison = compare_trial_state(MODEL_ID, state_id, build_trial)
    assert comparison.failures == [], comparison.summary()
