"""M01.A24 (unit half), A25-A32, A49, A51: the C1 reactor boundary and its synthetic stand-in (§8).

A51 (iii) is restated and A51 (v) added by Amendment 2 (review F3, spec §20).

Expectations: `benchmarks/m01/reference_values.yaml` → `closed_form.boundary` (the generator's
stand-in and projection at 50 digits). The stand-in is synthetic: these tests certify the boundary
code — mapping, projection, conventions, envelope, refusals — never the reactor.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from dataclasses import replace
from typing import Any

import pytest
from conftest import REPO_ROOT, load_yaml
from t07_corpus import CORPUS
from test_schemas_p01 import validator_for

from openflowsheet.application.binding import Unbound
from openflowsheet.application.revision_binding import MODEL_BUILDERS, bind_revision_flowsheet
from openflowsheet.compiled import EvaluationContext
from openflowsheet.models import SpecificationError
from openflowsheet.models.c1 import COMPONENTS, ELEMENT_MATRIX, NU
from openflowsheet.models.c1.boundary import (
    ENVELOPE_FIELDS,
    IDENTITY_FIELDS,
    Boundary,
    NotAccepted,
    ReactorResult,
    TubeInlet,
    hard_domain_violations,
    project,
    tube_inlet,
)
from openflowsheet.models.c1.reactor_standin import MODEL_ID, ReactorStandin
from openflowsheet.thermo import (
    FlashRequest,
    FlashResult,
    PropertyCapabilities,
    PropertyRequest,
    PropertyResult,
    StreamState,
)
from openflowsheet.thermo.pr_c1 import PrC1Provider

BOUNDARY: Mapping[str, Any] = load_yaml(REPO_ROOT / "benchmarks" / "m01" / "reference_values.yaml")[
    "closed_form"
]["boundary"]
STANDIN = BOUNDARY["standin"]
CLOSED_FLASH: Mapping[str, Any] = load_yaml(
    REPO_ROOT / "benchmarks" / "m01" / "reference_values.yaml"
)["closed_form"]["flash_states"]
PROJECTION = BOUNDARY["projection"]
CONTEXT = EvaluationContext(model_version="m01-boundary", constants_sha256="0" * 64)
PROVIDER = PrC1Provider()
INLET = StreamState(
    n=tuple(STANDIN["inlet_n_mol_s"]), temperature=STANDIN["T_in_K"], pressure=STANDIN["P_in_Pa"]
)


def _unit(**overrides: Any) -> ReactorStandin:
    return ReactorStandin(unit_id="R1", provider=PROVIDER, context=CONTEXT, **overrides)


def _flow_rel(value: float, expected: float) -> float:
    return abs(value / expected - 1.0)


def _carries_no_outlet_values(result: ReactorResult) -> bool:
    return all(
        getattr(result, name) is None
        for name in ENVELOPE_FIELDS
        if name not in ("status", "code", "message", "identity")
    )


# -- A24: the C1 reacting unit and the registry ---------------------------------------------------


class _Shifted:
    """`pr-c1-v1` under an unregistered reference convention (a datum ADR 0011 D2 never named)."""

    def describe(self) -> PropertyCapabilities:
        return replace(PROVIDER.describe(), reference_convention="PR-C1-shifted")

    def evaluate_phase(
        self, request: PropertyRequest, context: EvaluationContext
    ) -> PropertyResult:
        return PROVIDER.evaluate_phase(request, context)

    def flash(self, request: FlashRequest, context: EvaluationContext) -> FlashResult:
        return PROVIDER.flash(request, context)


def test_a24_a_c1_reacting_unit_constructs_over_pr_c1_v1_and_refuses_an_unregistered_datum() -> (
    None
):
    assert _unit().model_id == MODEL_ID == "c1.reactor_standin"
    with pytest.raises(SpecificationError) as raised:
        ReactorStandin(unit_id="R1", provider=_Shifted(), context=CONTEXT)
    assert str(raised.value).splitlines()[0] == (
        "reference_convention_not_reaction_consistent(PR-C1-shifted)"
    )


def test_the_manifest_validates_and_says_synthetic() -> None:
    manifest = _unit().manifest()
    validator = validator_for("model_manifest")
    assert [error.message for error in validator.iter_errors(manifest)] == []
    assert manifest["id"] == MODEL_ID and manifest["introduced_by_package"] == "M01"
    assert manifest["status"] == "tested"
    assert "SYNTHETIC" in manifest["description"]
    assert manifest["validity"]["limitations"][0].startswith("SYNTHETIC")
    assert manifest["execution_requirements"]["property_provider"] == "pr-c1-v1"
    assert manifest["execution_requirements"]["reference_convention"] == "PR-C1-ref-v1"
    assert len(manifest["mathematics"]["equations"]) == 5  # 5 component rows + 4 = 9 rows


def test_the_tube_mapping_is_spec_8_3s() -> None:
    tube = tube_inlet(INLET, n_tubes=4.0, sweep_ratio=1.0)
    assert isinstance(tube, TubeInlet)
    assert tube.flow == INLET.total_flow / 4.0
    assert tube.composition == tuple(value / INLET.total_flow for value in INLET.n)
    assert (tube.temperature, tube.outlet_pressure) == (INLET.temperature, INLET.pressure)
    assert tube.coolant_flow == tube.flow
    assert tube.coolant_composition == (0.0, 1.0, 0.0, 0.0, 0.0)
    assert (tube.coolant_temperature, tube.coolant_outlet_pressure) == (INLET.temperature, 1e5)


# -- A25-A29 -------------------------------------------------------------------------------------


def test_a25_the_standin_at_v1s_inlet() -> None:
    result = _unit().evaluate(INLET)
    assert result.status == "ok" and result.code == "ok", result.message
    assert result.xi is not None and result.Q is not None and result.outlet is not None
    assert _flow_rel(result.xi, STANDIN["xi_mol_s"]) <= 1e-14
    for got, expected in zip(result.outlet.n, STANDIN["outlet_n_mol_s"], strict=True):
        assert _flow_rel(got, expected) <= 1e-14
    assert result.outlet.temperature == INLET.temperature
    assert result.outlet.pressure == INLET.pressure
    assert abs(result.Q / STANDIN["Q_W"] - 1.0) <= 1e-10
    h_in = PROVIDER.evaluate_phase(
        PropertyRequest(state=INLET, phase="VAPOR", properties=("h",)), CONTEXT
    ).values["h"]
    h_out = PROVIDER.evaluate_phase(
        PropertyRequest(state=result.outlet, phase="VAPOR", properties=("h",)), CONTEXT
    ).values["h"]
    assert abs(INLET.total_flow * h_in / STANDIN["H_in_W"] - 1.0) <= 1e-11
    assert abs(result.outlet.total_flow * h_out / STANDIN["H_out_W"] - 1.0) <= 1e-11
    assert abs(result.Q / result.xi / STANDIN["Q_over_xi_J_mol"] - 1.0) <= 1e-10


def test_a26_the_projection_of_the_registered_raw_outlet() -> None:
    n_in = STANDIN["inlet_n_mol_s"]
    projection = project(n_in, PROJECTION["raw_outlet_mol_s"])
    assert _flow_rel(projection.xi, PROJECTION["xi_mol_s"]) <= 1e-12
    for got, expected in zip(projection.outlet, PROJECTION["projected_outlet_mol_s"], strict=True):
        assert _flow_rel(got, expected) <= 1e-12
    assert projection.outlet[3] == n_in[3] and projection.outlet[4] == n_in[4]  # inerts bitwise
    assert projection.defect[4] == 0.0  # CH4: raw and inlet are the same double, nu = 0
    # Spec §9.6 A26 as amended (Amendment 1, R-195): the defect vector, defect_rel and the element
    # balances on the flow scale, 1e-13 x n_tot,in. A 1e-6 mol/s defect is the difference of
    # O(0.5) mol/s flows; the 53-bit floor on these inputs is 5.6e-17 x n_tot,in (2.5e-11 of the
    # defect itself, set by the raw outlet's own rounding), the generator's BD-04 holds the 1e3
    # margin and BD-05 that every listed wrong projection moves the defect by >= 1e3 x tolerance.
    total = sum(n_in)
    for got, expected in zip(projection.defect, PROJECTION["defect_mol_s"], strict=True):
        assert abs(got - expected) <= 1e-13 * total
    assert abs(projection.defect_rel - PROJECTION["defect_rel"]) <= 1e-13
    for row in ELEMENT_MATRIX:
        inflow = sum(e * n for e, n in zip(row, n_in, strict=True))
        outflow = sum(e * n for e, n in zip(row, projection.outlet, strict=True))
        assert abs(outflow - inflow) <= 1e-13 * total, row
    assert [sum(e * v for e, v in zip(row, NU, strict=True)) for row in ELEMENT_MATRIX] == [0] * 4


@pytest.mark.parametrize(("drop", "status"), [(5000.0, "ok"), (20000.0, "unsupported")])
def test_a27_the_pressure_convention(drop: float, status: str) -> None:
    assert PROJECTION is not None and BOUNDARY["pressure_convention"]["P_in_Pa"] == INLET.pressure
    result = _unit(pressure_drop=drop).evaluate(INLET)
    assert result.status == status
    if status == "ok":
        assert result.pressure_drop_relative == drop / INLET.pressure
        assert result.outlet is not None and result.outlet.pressure == INLET.pressure
    else:
        assert result.code == "pressure_drop_exceeds_convention"
        assert _carries_no_outlet_values(result)


def test_a28_a_dormant_inlet_is_zero_flow() -> None:
    dormant = StreamState(n=(0.0,) * 5, temperature=673.15, pressure=1e7)
    result = _unit().evaluate(dormant)
    assert result.status == "ok" and result.code == "ZERO_FLOW"
    assert result.Q == 0.0 and math.copysign(1.0, result.Q) == 1.0
    assert result.xi == 0.0
    assert result.outlet is not None
    assert all(value == 0.0 and math.copysign(1.0, value) == 1.0 for value in result.outlet.n)
    assert (result.outlet.temperature, result.outlet.pressure) == (673.15, 1e7)


@pytest.mark.parametrize("k", [2.0, 7.0])
def test_a29_per_tube_scaling_is_homogeneous_of_degree_one(k: float) -> None:
    base = _unit(n_tubes=3.0).evaluate(INLET)
    scaled_inlet = replace(INLET, n=tuple(k * value for value in INLET.n))
    scaled = _unit(n_tubes=3.0 * k).evaluate(scaled_inlet)
    assert base.status == scaled.status == "ok"
    assert base.xi is not None and scaled.xi is not None
    assert base.Q is not None and scaled.Q is not None
    assert base.outlet is not None and scaled.outlet is not None
    assert abs(scaled.xi / (k * base.xi) - 1.0) <= 1e-15
    assert abs(scaled.Q / (k * base.Q) - 1.0) <= 1e-15
    for got, one in zip(scaled.outlet.n, base.outlet.n, strict=True):
        assert abs(got / (k * one) - 1.0) <= 1e-15


# -- A30-A32 -------------------------------------------------------------------------------------


def _with_nh3_fraction(fraction: float) -> StreamState:
    others = INLET.n[0] + INLET.n[1] + INLET.n[3] + INLET.n[4]
    nh3 = fraction * others / (1.0 - fraction)
    return replace(INLET, n=(INLET.n[0], INLET.n[1], nh3, INLET.n[3], INLET.n[4]))


@pytest.mark.parametrize(
    ("case", "status", "code"),
    [
        ("inlet_liquid", "unsupported", "liquid_at_reactor_inlet"),
        ("permuted_components", "unsupported", "component_set_mismatch"),
        ("trace", "unsupported", "nh3_below_trace"),
        ("hard_domain", "out_of_domain", "out_of_domain"),
        ("defect", "not_converged", "element_balance_defect"),
    ],
)
def test_a30_each_refusal_the_standin_can_reach(case: str, status: str, code: str) -> None:
    unit, inlet, components = _unit(), INLET, COMPONENTS
    if case == "inlet_liquid":  # F7's state: pure compressed liquid NH3
        inlet = StreamState(n=(0.0, 0.0, 1.0, 0.0, 0.0), temperature=268.15, pressure=1e7)
    elif case == "permuted_components":
        components = ("N2", "H2", "NH3", "Ar", "CH4")
    elif case == "trace":
        inlet = _with_nh3_fraction(1e-10)
        assert inlet.n[2] / inlet.total_flow == pytest.approx(1e-10, rel=1e-12)
    elif case == "hard_domain":
        inlet = replace(INLET, temperature=550.0)
    else:
        d = tuple(0.7 * value for value in PROJECTION["perturbation_mol_s"])
        unit = _unit(perturbation=d)
        assert project(INLET.n, [n + v for n, v in zip(INLET.n, d, strict=True)]).defect_rel == (
            pytest.approx(2e-6, rel=1e-6)
        )
    result = unit.evaluate(inlet, components)
    assert (result.status, result.code) == (status, code), result.message
    assert result.message.startswith(f"{code}:")
    assert _carries_no_outlet_values(result)


def test_a30_an_unaccepted_evaluation_is_not_converged_with_its_stage() -> None:
    boundary = Boundary(provider=PROVIDER, n_tubes=1.0, identity=_unit().identity())
    result = boundary.evaluate(INLET, COMPONENTS, lambda tube: NotAccepted("S3"), CONTEXT)
    assert (result.status, result.code) == ("not_converged", "reactor_not_accepted(S3)")
    assert _carries_no_outlet_values(result)


@pytest.mark.parametrize(
    ("temperature", "status", "bounds"),
    [(623.15, "extrapolated", ("T_in",)), (673.15, "within_data_domain", ())],
)
def test_a31_the_data_domain_flags_and_never_refuses(
    temperature: float, status: str, bounds: tuple[str, ...]
) -> None:
    result = _unit().evaluate(replace(INLET, temperature=temperature))
    assert result.status == "ok", result.message
    assert result.domain_status == status
    assert result.extrapolated_bounds == bounds


def test_a32_an_ok_envelope_has_every_field_and_the_standins_diagnostics_are_null() -> None:
    result = _unit().evaluate(INLET)
    document = result.as_document()
    assert tuple(document) == ENVELOPE_FIELDS
    assert set(ENVELOPE_FIELDS) >= {
        "status",
        "code",
        "outlet",
        "xi",
        "Q",
        "defect_rel",
        "pressure_drop_relative",
        "Q_coolant",
        "inlet_face_heat_loss",
        "discretization_estimate",
        "domain_status",
        "identity",
    }
    assert document["Q_coolant"] is None and document["inlet_face_heat_loss"] is None
    assert document["discretization_estimate"] is None
    assert tuple(document["identity"]) == IDENTITY_FIELDS
    identity = document["identity"]
    assert identity["synthetic"] is True and identity["model_id"] == MODEL_ID
    for name in ("reactor_commit", "pymrm_version", "overlay_sha256", "profile"):
        assert identity[name] is None
    assert len(identity["configuration_sha256"]) == 64
    for name in ("outlet", "xi", "Q", "defect_rel", "pressure_drop_relative", "domain_status"):
        assert document[name] is not None, name


# -- A49: the synthetic label (Amendment 1, §8.13) -------------------------------------------------


def test_a49_the_manifest_carries_the_synthetic_label_where_spec_8_13_puts_it() -> None:
    manifest = _unit().manifest()
    assert [e.message for e in validator_for("model_manifest").iter_errors(manifest)] == []
    assert "synthetic" in manifest["title"].lower()
    assert manifest["description"].startswith("SYNTHETIC")
    assert manifest["validity"]["limitations"][0].startswith("SYNTHETIC:")


@pytest.mark.parametrize(
    "inlet",
    [
        INLET,
        StreamState(n=(0.0,) * 5, temperature=673.15, pressure=1e7),  # ZERO_FLOW
        replace(INLET, temperature=623.15),  # extrapolated
    ],
    ids=["V1", "zero_flow", "extrapolated"],
)
def test_a49_every_ok_result_is_labelled_synthetic(inlet: StreamState) -> None:
    result = _unit().evaluate(inlet)
    assert result.status == "ok", result.message
    assert result.identity is not None and result.identity["synthetic"] is True
    assert result.as_document()["identity"]["synthetic"] is True


def test_a49_the_standin_is_not_bound_and_a_revision_naming_it_is_refused() -> None:
    """A49's binder clause, as M02 supersedes it (design note §6.1, §10.1 G8 (e); ADR 0034 D9;
    R-231): the stand-in is variant-backed, so an instance naming it must pin
    `standin-x025-v1` by id and SHA-256 (`model_variant_mismatch` otherwise, M02 WO-7). Until
    M02 WO-9 adds its builder, a pinned instance is still `model_unsupported`; G8 (e) replaces
    this test then."""
    from openflowsheet.adapters import variants

    assert MODEL_ID not in MODEL_BUILDERS
    document = CORPUS["SYN-001-nominal"]()
    (heater,) = (i for i in document["instances"] if i["id"] == "heater")  # T08 U02/U04's path
    heater["model"]["id"] = MODEL_ID
    refused = bind_revision_flowsheet(document)
    assert isinstance(refused, Unbound)
    assert (refused.kind, refused.detail) == ("unsupported", "model_variant_mismatch(heater)")
    heater["model"]["version"] = "standin-x025-v1"
    heater["model"]["artifact_ref"] = variants.registry()["standin-x025-v1"]
    refused = bind_revision_flowsheet(document)
    assert isinstance(refused, Unbound)
    assert (refused.kind, refused.detail) == ("unsupported", f"model_unsupported({MODEL_ID})")


# -- A51: boundary paths beyond A30 (Amendment 1, §8.12) -------------------------------------------

STAGE_CODE = re.compile(r"^reactor_not_accepted\([A-Za-z0-9_]+\)$")
REGISTERED_STAGES = ("S1", "S2", "S3", "certificate", "backflow", "nonpositive_flow")


class _RefusesEnthalpy:
    """`pr-c1-v1`'s `describe` and `flash`, but every `evaluate_phase` refused (A51 (ii))."""

    MESSAGE = "out_of_domain: the double refuses every phase evaluation"

    def describe(self) -> PropertyCapabilities:
        return PROVIDER.describe()

    def evaluate_phase(
        self, request: PropertyRequest, context: EvaluationContext
    ) -> PropertyResult:
        return PropertyResult(
            status="out_of_domain",
            phase_signature=None,
            values={},
            provider_id="pr-c1-v1",
            reference_convention="PR-C1-ref-v1",
            message=self.MESSAGE,
        )

    def flash(self, request: FlashRequest, context: EvaluationContext) -> FlashResult:
        return PROVIDER.flash(request, context)


@pytest.mark.parametrize("stage", REGISTERED_STAGES)
def test_a51_i_an_unaccepted_evaluation_is_reactor_not_accepted_with_its_stage(stage: str) -> None:
    boundary = Boundary(provider=PROVIDER, n_tubes=1.0, identity=_unit().identity())
    result = boundary.evaluate(INLET, COMPONENTS, lambda tube: NotAccepted(stage), CONTEXT)
    assert (result.status, result.code) == ("not_converged", f"reactor_not_accepted({stage})")
    assert STAGE_CODE.fullmatch(result.code)
    assert result.message.startswith(f"{result.code}:")
    assert _carries_no_outlet_values(result)


@pytest.mark.parametrize("stage", ["", "S 3", "S3)", "s-3", "(S3", "S3\n", "Ş3", 3])
def test_a51_i_a_stage_outside_the_grammar_is_a_value_error(stage: Any) -> None:
    with pytest.raises(ValueError, match="A-Za-z0-9_"):
        NotAccepted(stage)


def test_a51_ii_a_refused_stream_enthalpy_is_an_error_carrying_the_providers_message() -> None:
    unit = ReactorStandin(unit_id="R1", provider=_RefusesEnthalpy(), context=CONTEXT)
    result = unit.evaluate(INLET)
    assert (result.status, result.code) == ("error", "stream_enthalpy_refused")
    assert result.message.startswith("stream_enthalpy_refused:")
    assert _RefusesEnthalpy.MESSAGE in result.message
    assert _carries_no_outlet_values(result)


class _RefusesFlash:
    """`pr-c1-v1`'s `describe` and `evaluate_phase`, but every `flash` refused (A51 (iii))."""

    MESSAGE = "vapour_root_metastable: the double refuses every flash"

    def describe(self) -> PropertyCapabilities:
        return PROVIDER.describe()

    def evaluate_phase(
        self, request: PropertyRequest, context: EvaluationContext
    ) -> PropertyResult:
        return PROVIDER.evaluate_phase(request, context)

    def flash(self, request: FlashRequest, context: EvaluationContext) -> FlashResult:
        return FlashResult(
            status="unsupported",
            phase_signature=None,
            vapor_fraction=None,
            vapor=None,
            liquid=None,
            provider_id="pr-c1-v1",
            reference_convention="PR-C1-ref-v1",
            message=self.MESSAGE,
        )


def test_a51_iii_the_inlet_flashs_refusal_passes_through() -> None:
    # Amendment 2 (review F3): a negative flow, this assertion's state before, is now refused by
    # the boundary's own state-space check (A51 (v)); no inlet inside the state space and the hard
    # domain is refused by pr-c1-v1's flash, so the pass-through is held with a refusing double.
    unit = ReactorStandin(unit_id="R1", provider=_RefusesFlash(), context=CONTEXT)
    result = unit.evaluate(INLET)
    assert (result.status, result.code) == ("unsupported", "vapour_root_metastable")
    assert result.message == _RefusesFlash.MESSAGE
    assert _carries_no_outlet_values(result)


#: Review F3's inlets outside nTP-v1's state space, each with one defect (the three of the review's
#: P8, then the remaining kinds); before Amendment 2 the dormant ones answered `ok`, `ZERO_FLOW`.
OUTSIDE_THE_STATE_SPACE = {
    "flows_summing_to_zero": replace(INLET, n=(0.5, -0.5, 0.0, 0.0, 0.0)),
    "dormant_nan_temperature": StreamState(n=(0.0,) * 5, temperature=math.nan, pressure=1e7),
    "dormant_negative_pressure": StreamState(n=(0.0,) * 5, temperature=673.15, pressure=-1.0),
    "flowing_negative_n2": replace(INLET, n=(0.7, -0.235, 0.03, 0.015, 0.02)),
    "flowing_nan_flow": replace(INLET, n=(0.7, 0.235, math.nan, 0.015, 0.02)),
    "flowing_infinite_flow": replace(INLET, n=(math.inf, 0.235, 0.03, 0.015, 0.02)),
    "dormant_infinite_pressure": StreamState(n=(0.0,) * 5, temperature=673.15, pressure=math.inf),
    "dormant_zero_temperature": StreamState(n=(0.0,) * 5, temperature=0.0, pressure=1e7),
}


@pytest.mark.parametrize("case", sorted(OUTSIDE_THE_STATE_SPACE))
def test_a51_v_an_inlet_outside_the_state_space_is_out_of_domain_before_the_dormant_check(
    case: str,
) -> None:
    result = _unit().evaluate(OUTSIDE_THE_STATE_SPACE[case])
    assert (result.status, result.code) == ("out_of_domain", "out_of_domain"), result.message
    assert result.message.startswith("out_of_domain:") and "ADR 0001 D2" in result.message
    assert _carries_no_outlet_values(result)


def test_a51_v_a_dormant_inlets_labels_stay_free_inside_the_state_space() -> None:
    # ADR 0001 D3.1: a dormant inlet's T and P are labels; outside the provider's box and the
    # hard domain (50 K, 1 Pa) they are still answered ZERO_FLOW, and -0.0 is a zero flow.
    dormant = StreamState(n=(0.0, -0.0, 0.0, 0.0, 0.0), temperature=50.0, pressure=1.0)
    result = _unit().evaluate(dormant)
    assert (result.status, result.code) == ("ok", "ZERO_FLOW")
    assert result.outlet is not None
    assert (result.outlet.temperature, result.outlet.pressure) == (50.0, 1.0)


def test_a51_v_the_component_set_precedes_the_state_space() -> None:
    inlet = OUTSIDE_THE_STATE_SPACE["flows_summing_to_zero"]
    result = _unit().evaluate(inlet, ("N2", "H2", "NH3", "Ar", "CH4"))
    assert (result.status, result.code) == ("unsupported", "component_set_mismatch")


def test_a51_iv_a_liquid_inlet_outside_the_hard_domain_is_liquid_at_reactor_inlet() -> None:
    # F7's state has two defects: it flashes LIQUID, and it lies outside the hard domain (T_in =
    # 268.15 K below 573.15 K; pure NH3 also fails H2/N2). The normative order (§8.12, claim BD-06)
    # checks the inlet phase first, so the liquid's code is returned.
    f7 = CLOSED_FLASH["F7"]
    inlet = StreamState(n=tuple(f7["n_mol_s"]), temperature=f7["T_K"], pressure=f7["P_Pa"])
    assert f7["phase_signature"] == "LIQUID"
    assert any(bound.startswith("T_in") for bound in hard_domain_violations(inlet))
    result = _unit().evaluate(inlet)
    assert (result.status, result.code) == ("unsupported", "liquid_at_reactor_inlet")
    assert _carries_no_outlet_values(result)
