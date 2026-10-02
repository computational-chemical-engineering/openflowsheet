"""T05 W6: `syn001.conversion_reactor` against the registered cases (spec §6; A10, A13, A14, A16).

Every input and expected value is read from `benchmarks/t05/reference_values.yaml`, the design
lane's 40-digit twin; no number is copied into this file. Tolerances are spec §14's; the exact
zeros (RX-6 and RX-8's `n_A`, the dormant RX-Z) are compared with `==`. The outlet's split,
registered as `outlet.vapor_n_mol_per_s` / `liquid_n_mol_per_s`, is the one
`evaluate_with_split` returns. RX-S4 needs a provider whose reference convention is not
reaction-consistent; `ConventionDouble` is the real SYN-001 provider with only that field changed.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from typing import Any

import numpy as np
import pytest
from conftest import REPO_ROOT, load_yaml
from t05_support import (
    CONTEXT,
    ENERGY_TOLERANCE,
    FLOW_TOLERANCE,
    PRESSURE_TOLERANCE,
    PROVIDER,
    REF,
    TEMPERATURE_TOLERANCE,
    assert_close,
    assert_flows,
    cases,
    first_line,
    specification_errors,
    stream,
)
from t05_trial_states import TrialUnit, compare_trial_state, trial_states
from test_schemas_p01 import schema_errors

from openflowsheet.compiled import EvaluationContext
from openflowsheet.models import SpecificationError, Wiring, origin
from openflowsheet.models.syn001 import COMPONENTS
from openflowsheet.models.syn001.conversion_reactor import (
    MODEL_ID,
    MOLAR_MASSES,
    REACTION_CONSISTENT_CONVENTIONS,
    ConversionReactor,
)
from openflowsheet.models.syn001.heater import TPHeater
from openflowsheet.thermo import (
    FlashRequest,
    FlashResult,
    PropertyCapabilities,
    PropertyProvider,
    PropertyRequest,
    PropertyResult,
    StreamState,
)

CASES = cases(MODEL_ID)


@dataclasses.dataclass(frozen=True)
class ConventionDouble:
    """A provider test double: the real one, declaring a different reference convention."""

    inner: PropertyProvider
    reference_convention: str

    def describe(self) -> PropertyCapabilities:
        return dataclasses.replace(
            self.inner.describe(), reference_convention=self.reference_convention
        )

    def evaluate_phase(
        self, request: PropertyRequest, context: EvaluationContext
    ) -> PropertyResult:
        return self.inner.evaluate_phase(request, context)

    def flash(self, request: FlashRequest, context: EvaluationContext) -> FlashResult:
        return self.inner.flash(request, context)


def unit_for(inputs: Mapping[str, Any], unit_id: str = "U-RX") -> ConversionReactor:
    convention = inputs.get("provider_reference_convention")
    provider: PropertyProvider = (
        PROVIDER if convention is None else ConventionDouble(PROVIDER, convention)
    )
    return ConversionReactor(
        unit_id=unit_id,
        provider=provider,
        stoichiometry=tuple(float(value) for value in inputs["nu"]),
        key_component=inputs["key"],
        conversion=float(inputs["conversion"]),
        energy_specification=inputs["energy_specification"],
        value=float(inputs["value"]),
        context=CONTEXT,
        pressure_drop=float(inputs["pressure_drop"]),
        inlet_phase=inputs["inlet_phase"],
    )


def test_every_registered_case_is_exercised() -> None:
    expected = [f"RX-{i}" for i in range(1, 9)] + ["RX-Z", "RX-F1", "RX-F5"]
    assert sorted(CASES) == sorted(expected)
    assert sorted(specification_errors(MODEL_ID)) == [f"RX-S{i}" for i in range(1, 6)]


@pytest.mark.parametrize("case_id", CASES)
def test_reactor_case(case_id: str) -> None:
    """A10, A14, A16: status, code, signature; extent, duty, outlet and split to §14."""
    case = REF["unit_cases"][case_id]
    inputs, expected = case["inputs"], case["expected"]
    result, split = unit_for(inputs).evaluate_with_split(
        {"inlet": [stream(inputs["inlet"])]}, CONTEXT
    )

    assert result.status == expected["status"], result.message
    assert first_line(result.message) == expected["code"]
    if expected["status"] != "ok":
        # A failed evaluation carries no answer (RX-F1 registers the extent it would have had;
        # `UnitEvaluation` refuses a value on a failure, so the extent is in the free text).
        assert result.outlets == {} and result.duty is None and result.extent is None
        assert split is None
        return

    assert result.phase_signature == expected["signature"]
    assert result.work is None and result.transferred_duty is None
    assert_close(result.duty, expected["duty_W"], ENERGY_TOLERANCE, f"{case_id} duty")
    assert_close(result.extent, expected["extent_mol_per_s"], FLOW_TOLERANCE, f"{case_id} xi")
    registered = expected["outlet"]
    outlet = result.outlets["outlet"]
    assert_flows(outlet.n, registered["n_mol_per_s"], f"{case_id} outlet.n")
    assert_close(outlet.temperature, registered["T_K"], TEMPERATURE_TOLERANCE, "outlet.T")
    assert_close(outlet.pressure, registered["P_Pa"], PRESSURE_TOLERANCE, "outlet.P")

    if expected["signature"] == "ZERO_FLOW":
        # A14: the label (T_spec here), and exactly zero extent and duty; no split is computed.
        assert split is None
        assert outlet.temperature == float(inputs["value"])
        assert result.duty == 0.0 and result.extent == 0.0
        return
    assert split is not None
    assert split.phase_signature == registered["regime"]
    assert split.vapor is not None and split.liquid is not None
    assert_flows(split.vapor.n, registered["vapor_n_mol_per_s"], f"{case_id} vapour")
    assert_flows(split.liquid.n, registered["liquid_n_mol_per_s"], f"{case_id} liquid")


def test_a_dormant_duty_mode_inlet_is_labelled_with_its_own_temperature() -> None:
    """Spec §4.7, §6.3 (1): duty mode labels with `T_in`; a nonzero `Q_spec` is refused."""
    inputs = {**REF["unit_cases"]["RX-Z"]["inputs"], "energy_specification": "duty", "value": 0.0}
    feed = stream(inputs["inlet"])
    result = unit_for(inputs).evaluate({"inlet": [feed]}, CONTEXT)
    assert result.status == "ok" and result.phase_signature == "ZERO_FLOW"
    assert result.outlets["outlet"].temperature == feed.temperature
    assert result.duty == 0.0 and result.extent == 0.0

    refused = unit_for({**inputs, "value": 1.0}).evaluate({"inlet": [feed]}, CONTEXT)
    assert refused.status == "error"
    assert first_line(refused.message) == "duty_into_dormant_stream"


def test_the_reaction_enthalpy_is_carried_by_the_outlet_and_not_added_twice() -> None:
    """Rule 3 made concrete (spec §6.4): RX-1 vanishes and RX-2 does not, by `xi sum nu_i L_i`."""
    duties = {}
    for case_id in ("RX-1", "RX-2"):
        inputs = REF["unit_cases"][case_id]["inputs"]
        result = unit_for(inputs).evaluate({"inlet": [stream(inputs["inlet"])]}, CONTEXT)
        assert result.status == "ok" and result.duty is not None and result.extent is not None
        duties[case_id] = (result.duty, result.extent)
    assert duties["RX-1"][0] == 0.0
    reaction_enthalpy = float(REF["constants"]["reaction_enthalpy_vapour_J_per_mol"])
    duty, extent = duties["RX-2"]
    assert abs(duty - extent * reaction_enthalpy) <= ENERGY_TOLERANCE


def test_conversion_zero_is_the_tp_heater() -> None:
    """A13: RX-7's duty equals K02's `TPHeater` duty on the same stream to `1.01e-3 W`."""
    inputs = REF["unit_cases"]["RX-7"]["inputs"]
    feed = stream(inputs["inlet"])
    reacted = unit_for(inputs).evaluate({"inlet": [feed]}, CONTEXT)
    heated = TPHeater(
        unit_id="U-HEAT",
        provider=PROVIDER,
        outlet_temperature=float(inputs["value"]),
        context=CONTEXT,
        inlet_phase=inputs["inlet_phase"],
        pressure_drop=float(inputs["pressure_drop"]),
    ).evaluate({"inlet": [feed]}, CONTEXT)
    assert reacted.status == heated.status == "ok"
    assert reacted.duty is not None and heated.duty is not None
    assert abs(reacted.duty - heated.duty) <= ENERGY_TOLERANCE
    assert reacted.phase_signature == heated.phase_signature
    assert reacted.outlets["outlet"] == heated.outlets["outlet"]


# ------------------------------------------------------------------------- construction


@pytest.mark.parametrize("case_id", specification_errors(MODEL_ID))
def test_reactor_construction_refusal(case_id: str) -> None:
    """A16 for RX-S1…S5: the nominal case (RX-1) with the registered change, refused at build."""
    registered = REF["specification_errors"][case_id]
    inputs = {**REF["unit_cases"]["RX-1"]["inputs"], **registered["change_from_nominal"]}
    with pytest.raises(SpecificationError) as refused:
        unit_for(inputs)
    assert first_line(str(refused.value)) == registered["code"]


def test_the_registered_conventions_are_adr_0011_d2s() -> None:
    registered = REF["constants"]["reaction_consistent_conventions"]
    assert set(registered) == REACTION_CONSISTENT_CONVENTIONS
    assert PROVIDER.describe().reference_convention in REACTION_CONSISTENT_CONVENTIONS


def test_the_molar_masses_are_the_component_records() -> None:
    """The mass check's `M_i` (the provider declares none) are SYN-001's component records."""
    records = load_yaml(REPO_ROOT / "benchmarks" / "syn001" / "components.yaml")["components"]
    assert [record["id"] for record in records] == list(COMPONENTS)
    assert tuple(record["molecular_weight"]["value"] for record in records) == MOLAR_MASSES


@pytest.mark.parametrize(
    "nu", [(-1.0, -1.0, 2.0), (-2.0, 3.0, -1.0), (-1.0, 1.0, 0.0)], ids=["2to1", "mixed", "isom"]
)
def test_any_mass_conserving_stoichiometry_is_accepted(nu: tuple[float, ...]) -> None:
    inputs = {**REF["unit_cases"]["RX-1"]["inputs"], "nu": nu}
    assert unit_for(inputs).stoichiometry == nu


@pytest.mark.parametrize("nu", [(-1.0, -1.0, 2.0 + 1e-6), (-1.0, float("nan"), 1.0)])
def test_a_stoichiometry_off_by_a_slip_or_not_finite_is_refused(nu: tuple[float, ...]) -> None:
    inputs = {**REF["unit_cases"]["RX-1"]["inputs"], "nu": nu}
    with pytest.raises(SpecificationError) as refused:
        unit_for(inputs)
    assert first_line(str(refused.value)) == "stoichiometry_not_mass_conserving"


# ------------------------------------------------------- full conversion at any nu_k (R-051)


def full_conversion_reactor(nu: tuple[float, ...], conversion: float) -> ConversionReactor:
    """Ruling Q-R7's setup: RX-2's conditions (VAPOR, 420 K, `P_r`, `T_spec = 420 K`), key A."""
    return unit_for({**REF["unit_cases"]["RX-2"]["inputs"], "nu": nu, "conversion": conversion})


def vapour_feed(n_a: float) -> dict[str, list[StreamState]]:
    return {"inlet": [StreamState(n=(n_a, 0.5, 0.5), temperature=420.0, pressure=1e5)]}


def test_review_p2_full_conversion_at_nu_minus_3_is_exactly_zero() -> None:
    """Q-R7 (review S2, P2): `n_A + (-3)(n_A/3)` is `-2.2e-16` for this feed, which was refused as
    `reactant_exhausted(A)`; the key's outlet `n_A - 1·n_A` is exactly zero."""
    result = full_conversion_reactor((-3.0, 1.0, 2.0), 1.0).evaluate(
        vapour_feed(1.7383439417747188), CONTEXT
    )
    assert result.status == "ok", result.message
    assert result.outlets["outlet"].n[0] == 0.0


#: A deterministic sweep of `n_A ∈ [0.01, 5]`; under the old key arithmetic 61, 54 and 45 of
#: these 1 000 feeds were refused at `X = 1` for `nu_A = -3, -5, -7` (measured).
SWEEP = tuple(float(value) for value in np.random.default_rng(20260925).uniform(0.01, 5.0, 1000))


@pytest.mark.parametrize(
    "nu", [(-3.0, 1.0, 2.0), (-5.0, 2.0, 3.0), (-7.0, 3.0, 4.0)], ids=["nu3", "nu5", "nu7"]
)
def test_the_key_outlet_is_never_exhausted_by_rounding(nu: tuple[float, ...]) -> None:
    """Q-R7's sweep: at `X = 1` every feed is `ok` with `n_out,A == 0.0`; at `X ∈ {0.25, 0.5,
    0.75}` none is `reactant_exhausted(A)`; and `RX-mole:A`, written as the row writes it
    (`n_in + nu xi - n_out`), is within `1e-12` of its term scale at every answer."""
    for conversion in (1.0, 0.25, 0.5, 0.75):
        unit = full_conversion_reactor(nu, conversion)
        for n_a in SWEEP:
            result = unit.evaluate(vapour_feed(n_a), CONTEXT)
            assert result.status == "ok", (conversion, n_a, result.message)
            assert result.extent is not None
            n_out = result.outlets["outlet"].n[0]
            if conversion == 1.0:
                assert n_out == 0.0, n_a
            produced = nu[0] * result.extent
            row = n_a + produced - n_out
            assert abs(row) <= 1e-12 * max(abs(n_a), abs(produced), abs(n_out)), (conversion, n_a)


def test_a_negative_pressure_drop_is_refused() -> None:
    inputs = {**REF["unit_cases"]["RX-1"]["inputs"], "pressure_drop": -1.0}
    with pytest.raises(SpecificationError) as refused:
        unit_for(inputs)
    assert first_line(str(refused.value)) == "negative_pressure_drop"


# --------------------------------------------------------------------------- declaration


def test_manifest_validates_with_the_registered_accumulation_and_statements() -> None:
    """A01/A02 for the reactor: schema, identity, §13.2's classification and §6.2's statements."""
    for mode in ("outlet_temperature", "duty"):
        inputs = {**REF["unit_cases"]["RX-1"]["inputs"], "energy_specification": mode}
        document = dict(unit_for(inputs).manifest())
        assert schema_errors("model_manifest", document) == []
        assert document["id"] == MODEL_ID
        assert document["introduced_by_package"] == "T05"
        assert document["implementation_artifact"]["planned_package"] == "T05"
        assert [port["name"] for port in document["ports"]] == ["inlet", "outlet", "duty"]
        requirements = document["execution_requirements"]
        assert requirements["property_provider"] == "syn001"
        assert requirements["reference_convention"] == "SYN-001-ref-v1"
        equations = {entry["id"]: entry for entry in document["mathematics"]["equations"]}
        kinds = {name: entry["accumulation"]["kind"] for name, entry in equations.items()}
        assert kinds == {
            "RX-mole": "holdup_balance",
            "RX-duty": "holdup_balance",
            "RX-conversion": "algebraic",
            "RX-pressure": "algebraic",
            "RX-equilibrium": "algebraic",
            "RX-spec": "algebraic",
        }
        assert equations["RX-mole"]["accumulation"]["holdup"]["symbol"] == "N_i"
        assert equations["RX-duty"]["accumulation"]["holdup"]["symbol"] == "U"
        assert (
            equations["RX-mole"]["statement"]
            == "n_in,i - n_out,i + nu_i xi = 0 for every component i"
        )
        assert equations["RX-duty"]["statement"] == (
            "Q + Hdot_in - Hdot_out = 0, Q positive into the unit; enthalpies on the provider's "
            "formation datum (ADR 0011 D2), so the heat of reaction is carried by Hdot and never "
            "added separately"
        )
        derivatives = {entry["output"]: entry["method"] for entry in document["derivatives"]}
        assert derivatives == {"outlet.state": "unavailable", "duty.Q": "unavailable"} | {
            "residuals": "ad"
        }


def test_rows_trace_to_the_declaration_with_its_accumulation() -> None:
    """Every declared equation authors a row, every row names one (ADR 0008 D4.4), 15 rows."""
    for mode in ("outlet_temperature", "duty"):
        unit = unit_for({**REF["unit_cases"]["RX-1"]["inputs"], "energy_specification": mode})
        declared = {
            origin(MODEL_ID, equation.equation_id): equation.accumulation.kind
            for equation in unit.declared_equations()
        }
        contribution = unit.contribute(Wiring({"inlet": ("S1",), "outlet": ("S2",)}), COMPONENTS)
        lifting = origin(MODEL_ID, "lifting")
        assert {equation.origin for equation in contribution.equations} == {*declared, lifting}
        for equation in contribution.equations:
            expected = "algebraic" if equation.origin == lifting else declared[equation.origin]
            assert equation.accumulation == expected, equation.equation_id
        # Spec §6.2's DOF: 15 rows; the unit owns Q, xi and the 8 split variables, and the
        # outlet stream's 5 are the other unknowns.
        assert len(contribution.equations) == 15
        assert len(contribution.variable_ids) == 10


# --------------------------------------------------------------------------- A04/A05


def build_trial(configuration: Mapping[str, Any], parameters: Mapping[str, str]) -> TrialUnit:
    regime = configuration["inlet_regime"]
    mode = configuration["mode"]
    unit = ConversionReactor(
        unit_id=configuration["unit"],
        provider=PROVIDER,
        stoichiometry=tuple(float(value) for value in parameters["nu"]),
        key_component=COMPONENTS[int(configuration["key"])],
        conversion=float(parameters["conversion"]),
        energy_specification=mode,
        value=float(parameters[mode]),
        context=CONTEXT,
        pressure_drop=float(parameters["pressure_drop"]),
        inlet_phase=None if regime == "lifted" else regime,
    )
    inlet, outlet = configuration["inlet"], configuration["outlet"]
    return TrialUnit(
        unit=unit,
        wiring=Wiring({"inlet": (inlet,), "outlet": (outlet,)}),
        streams=(inlet, outlet),
        lifted_inlets=(inlet,) if regime == "lifted" else (),
    )


@pytest.mark.parametrize("state_id", trial_states(MODEL_ID))
def test_rows_and_jacobian_at_the_registered_trial_state(state_id: str) -> None:
    comparison = compare_trial_state(MODEL_ID, state_id, build_trial)
    assert comparison.failures == [], comparison.summary()
