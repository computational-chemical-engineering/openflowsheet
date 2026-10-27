"""S11 WO-D6: the Wilson (γ–φ) flowsheets solved through the region (units design §5.3 D6, §6.1).

The spike first (Q18, D6's half): do the region's γ–φ paths carry the five K02/T05 units on
`wilson-ig-v2`? GP-C1 (heater → TP flash on S10 C-MW's feed) is the first case through the region:
from the units' own start it closes with no Newton step, and from a perturbed start Newton iterates
on the γ–φ rows (`GammaPhiLnKBlock`, the mixture enthalpy blocks) back to the same root.

"VERIFIED" is `verify_revision`'s certificate with the v2 basis dispatched to the γ–φ form
(`s11_gp_support.dispatch_gamma_phi`, I1b's hook), every check passing. Each certificate's
derivative witness records |Z| (S11 rulings item 2, R-831: the exactly-zero component columns
beside a positive sibling, differenced one-sided) and the one-sided part's worst, which must stay
≤ `DERIVATIVE_TOLERANCE`/10 (a larger value is a stop, never a widening).
"""

from __future__ import annotations

import time
from collections.abc import Mapping
from typing import Any

import pytest
from s11_gp_support import (
    CASES,
    GP_M1_INLET,
    GP_M1_OUTLET_P,
    GP_M2_INLET,
    GP_M2_OUTLET_P,
    admit_machines,
    admit_wilson,
    committed_case,
    dispatch_gamma_phi,
    gp_c3,
    solve,
)

from openflowsheet.application.policies import T06_REVISION_V2
from openflowsheet.compile.casadi_backend import compile_problem
from openflowsheet.compiled import EvaluationContext
from openflowsheet.models import (
    SpecificationError,
    UnitEvaluation,
    flow_id,
    pressure_id,
    temperature_id,
)
from openflowsheet.models.revision_flowsheet import WILSON_BASIS, parse_revision
from openflowsheet.models.syn001 import REFERENCE_CONVENTION
from openflowsheet.models.syn001.ph_flash import PHFlash
from openflowsheet.models.syn001.ph_kernel import ph_state
from openflowsheet.models.syn001.pump import work_id
from openflowsheet.models.syn001.saturation_band import band_temperature
from openflowsheet.models.syn001.tp_state import tp_state
from openflowsheet.models.syn001.valve import Valve
from openflowsheet.models.thermal.machines import ThermalMachine
from openflowsheet.orchestrator.executor import execute_plan
from openflowsheet.thermo import FlashRequest, PropertyProvider, PropertyRequest, StreamState
from openflowsheet.thermo.syn001 import Syn001Provider
from openflowsheet.verify.certificate import BoundDeclaration, fresh_provider, verify_revision
from openflowsheet.verify.checks import (
    DERIVATIVE_TOLERANCE,
    KIND_TOLERANCE,
    derivative_witness,
    one_sided_columns,
)
from openflowsheet.verify.thermal import additive_isentropic_enthalpy

TAU_E = KIND_TOLERANCE["heat_rate"]
TAU_FLOW = KIND_TOLERANCE["molar_flow"]
TAU_T = KIND_TOLERANCE["temperature"]
P_ATM = 101_325.0
CONTEXT = EvaluationContext(model_version="t", constants_sha256="0" * 64, phase_signature=None)


@pytest.fixture(autouse=True)
def wilson_admitted(monkeypatch: pytest.MonkeyPatch) -> None:
    admit_wilson(monkeypatch)


@pytest.fixture
def gamma_phi(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    return dispatch_gamma_phi(monkeypatch)


@pytest.mark.parametrize("name", sorted(CASES))
def test_the_committed_case_is_the_generated_one(name: str) -> None:
    """`benchmarks/s11/gp/<name>.json` is `CASES[name]()` (regenerate with
    `python tests/s11_gp_support.py`)."""
    assert committed_case(name) == CASES[name]()


def _stream(state: Mapping[str, float], stream: str) -> StreamState:
    return StreamState(
        n=tuple(state[flow_id(stream, c)] for c in WILSON_BASIS.components),
        temperature=state[temperature_id(stream)],
        pressure=state[pressure_id(stream)],
    )


def certified(
    document: Mapping[str, Any], dispatched: list[int]
) -> tuple[Any, dict[str, float], dict[str, Any], float]:
    """Solve `document`, certify it, and measure its one-sided witness part (R-831): the
    certificate, x_final, `{"Z": |Z|, "one_sided_worst": ...}` and the solve's wall time."""
    start = time.perf_counter()
    binding, plan, run = solve(document)
    elapsed = time.perf_counter() - start
    assert run.outcome == "CONVERGED", run.message
    assert run.state is not None
    state = dict(run.state)
    certificate = verify_revision(binding, document, run, solve_plan=plan.steps[-1].solve_plan)
    assert dispatched and all(count > 0 for count in dispatched)
    view = parse_revision(document)
    domain = fresh_provider(view.basis).describe().domain["P"]
    target = BoundDeclaration(
        binding.spec, compile_problem(binding.spec), state, pressure_domain=domain
    )
    z = one_sided_columns(binding.spec.variable_ids, state, view.components)
    witness: dict[str, Any] = {"Z": len(z), "one_sided_worst": None}
    if z:
        rest = frozenset(binding.spec.variable_ids) - z
        one_sided = derivative_witness(target, state, unstenciled=rest, one_sided=z)
        assert [c.result for c in one_sided] == ["pass", "pass"], one_sided
        witness["one_sided_worst"] = max(c.value or 0.0 for c in one_sided)
    return certificate, state, witness, elapsed


def assert_verified(certificate: Any) -> None:
    failing = [
        (c.id, c.result, c.value, c.reason) for c in certificate.checks if c.result != "pass"
    ]
    assert not failing, failing
    assert certificate.verification_status == "VERIFIED"
    assert not [x for x in certificate.limitations if x.kind == "derivative_witness_partial"]
    witness = [c for c in certificate.checks if c.category == "derivative_witness"]
    assert [c.id for c in witness] == [
        "derivative_witness.on_pattern",
        "derivative_witness.off_pattern",
    ]


# -- Q18 and S11.A69: GP-C1 --------------------------------------------------------------------


def test_q18_the_region_carries_the_gamma_phi_heater_and_flash() -> None:
    """Q18 (D6): GP-C1 from a start 1 % off its root in every flow, split and temperature (the
    root is the units' own start, closed with no step): Newton iterates on the γ–φ rows and
    returns to the same root (measured: 5 accepted steps, max |Δx| 1.1e-9)."""
    binding, plan, run = solve(committed_case("GP-C1"))
    assert run.outcome == "CONVERGED" and run.state is not None, run.message
    assert [step.iterations for step in run.steps] == [0]
    root = dict(run.state)
    moved = {
        k: v * 1.01
        if v != 0.0 and (k.endswith(".T") or ".n." in k or ".vap." in k or ".liq." in k)
        else v
        for k, v in root.items()
    }
    again = execute_plan(
        plan=plan,
        flowsheet=binding.flowsheet,
        spec=binding.spec,
        policy=T06_REVISION_V2,
        user_start=moved,
    )
    assert again.outcome == "CONVERGED" and again.state is not None, again.message
    accepted = sum(1 for e in again.trace.events if e.kind == "step_accepted")
    assert accepted >= 1
    assert max(abs(again.state[k] - v) for k, v in root.items()) <= TAU_FLOW


def test_a69_gp_c1_heater_to_tp_flash(gamma_phi: list[int]) -> None:
    """S11.A69: CONVERGED and VERIFIED; the flash products equal the provider's own TP flash at
    the solved (n, T, P) within τ_flow per component; the energy balances ≤ τ_E. Measured: 0
    Newton steps; energy_balance H −1.19e-9 W, D 1.22e-9 W, envelope 2.2e-11 W; |Z| = 6 (the six
    ethanol flow columns), one-sided worst 1.19e-10, central on-pattern 3.5e-9."""
    certificate, state, witness, _ = certified(committed_case("GP-C1"), gamma_phi)
    assert_verified(certificate)
    energy = [c for c in certificate.checks if c.category == "energy_balance"]
    assert {c.id for c in energy} == {
        "energy_balance.H",
        "energy_balance.D",
        "energy_balance.envelope",
    }
    assert all(c.value is not None and abs(c.value) <= TAU_E for c in energy)
    provider = fresh_provider(WILSON_BASIS)
    inlet = _stream(state, "S2")
    drum = StreamState(
        n=inlet.n, temperature=state[temperature_id("S3")], pressure=state[pressure_id("S3")]
    )
    flash = provider.flash(FlashRequest(drum), CONTEXT)
    assert flash.status == "ok" and flash.vapor is not None and flash.liquid is not None
    for k, c in enumerate(WILSON_BASIS.components):
        assert abs(state[flow_id("S3", c)] - flash.vapor.n[k]) <= TAU_FLOW, c
        assert abs(state[flow_id("S4", c)] - flash.liquid.n[k]) <= TAU_FLOW, c
    assert witness["Z"] == 6
    assert witness["one_sided_worst"] <= DERIVATIVE_TOLERANCE / 10, witness


def test_a69_the_wilson_heater_to_flash_time_gate() -> None:
    """§4.11: the Wilson heater→flash ≤ 10 s wall (measured 0.15 s solve, 0.22 s certificate)."""
    start = time.perf_counter()
    _, _, run = solve(committed_case("GP-C1"))
    assert run.outcome == "CONVERGED"
    assert time.perf_counter() - start <= 10.0


# -- S11.A70: GP-C2 --------------------------------------------------------------------------------


def test_a70_gp_c2_valve_to_ph_flash(gamma_phi: list[int]) -> None:
    """S11.A70: VERIFIED; the PH flash's T and split equal `ph_state` at the same inputs (the
    inlet's lifted enthalpy plus the duty, at the drum pressure) within the kind tolerances, and
    |Ḣ_in − Ḣ_out| ≤ τ_E across the valve. Measured: 0 Newton steps; energy_balance V −6.75e-9 W,
    D 6.78e-9 W; |Z| = 6, one-sided worst 1.67e-10, on-pattern 1.67e-10."""
    certificate, state, witness, _ = certified(committed_case("GP-C2"), gamma_phi)
    assert_verified(certificate)
    energy = {c.id: c for c in certificate.checks if c.category == "energy_balance"}
    valve = energy["energy_balance.V"]
    assert valve.value is not None and abs(valve.value) <= TAU_E
    provider = fresh_provider(WILSON_BASIS)
    inlet = tp_state(provider, _stream(state, "S2"), CONTEXT)
    assert inlet.status == "ok" and inlet.enthalpy_flow is not None
    closure = ph_state(
        provider,
        _stream(state, "S2").n,
        state[pressure_id("S3")],
        inlet.enthalpy_flow + 5.0e3,
        CONTEXT,
    )
    assert closure.status == "ok" and closure.temperature is not None, closure.message
    split = closure.split
    assert split is not None and split.vapor is not None and split.liquid is not None
    for stream in ("S3", "S4"):
        assert abs(state[temperature_id(stream)] - closure.temperature) <= TAU_T
    for k, c in enumerate(WILSON_BASIS.components):
        assert abs(state[flow_id("S3", c)] - split.vapor.n[k]) <= TAU_FLOW, c
        assert abs(state[flow_id("S4", c)] - split.liquid.n[k]) <= TAU_FLOW, c
    assert witness["Z"] == 6
    assert witness["one_sided_worst"] <= DERIVATIVE_TOLERANCE / 10, witness


# -- S11.A71: GP-C3 --------------------------------------------------------------------------------


def test_a71_gp_c3_mixer_of_two_liquids_to_heater(gamma_phi: list[int]) -> None:
    """S11.A71: VERIFIED, the mixer's declared liquid outlet judged by `single_phase_admissible`
    (its admissibility row passes). Measured: 0 Newton steps; energy_balance M 0.0, H −3.1e-9 W;
    |Z| = 2 (S1's ethanol, S2's methanol), one-sided worst 6.87e-11, on-pattern 2.6e-9."""
    certificate, _, witness, _ = certified(committed_case("GP-C3"), gamma_phi)
    assert_verified(certificate)
    admissibility = [
        c for c in certificate.checks if c.category == "phase_admissibility" and "S3" in c.id
    ]
    assert admissibility and all(c.result == "pass" for c in admissibility), admissibility
    assert witness["Z"] == 2
    assert witness["one_sided_worst"] <= DERIVATIVE_TOLERANCE / 10, witness


def test_oq5_a_liquid_only_lifted_heater_outlet_leaves_the_witness_unsupported(
    gamma_phi: list[int],
) -> None:
    """S11 rulings OQ-5, a fact for the design lane: GP-C3 with the heater at 345 K, below the
    mixture's bubble point, lifts a liquid-only outlet (β = 0: `S4.vap.<c>` exactly 0.0 for every
    c, so no column of that phase has a positive sibling and Z leaves them out). The central
    stencil's backward point is a negative flow, which the vapour enthalpy block refuses, so the
    witness is `unsupported` and the certificate UNVERIFIED. Recorded, not widened."""
    document = gp_c3(heater_temperature=345.0)
    binding, plan, run = solve(document)
    assert run.outcome == "CONVERGED" and run.state is not None
    assert all(run.state[f"S4.vap.{c}"] == 0.0 for c in WILSON_BASIS.components)
    certificate = verify_revision(binding, document, run, solve_plan=plan.steps[-1].solve_plan)
    witness = {c.id: c for c in certificate.checks if c.category == "derivative_witness"}
    assert {c.result for c in witness.values()} == {"unsupported"}
    assert {c.reason for c in witness.values()} == {
        "witness_stencil_invalid_trial_state(S4.vap.CH3OH)"
    }
    assert certificate.verification_status == "UNVERIFIED"


# -- S11 rulings item 11 (R-840): the `ph_kernel` failure labels -----------------------------------


def _labelled(provider: PropertyProvider) -> dict[str, UnitEvaluation]:
    """One typed failure of each `ph_kernel` path the valve and the PH flash return:
    `typed_failure` (a pressure rise; an outlet pressure out of the domain; a duty into a
    dormant stream), `port_enthalpy`'s (a vapour declared liquid) and `closure_failure` (a duty
    past the records' T range)."""
    described = provider.describe()
    faces: dict[str, Any] = {}
    if described.provider_id != "syn001":
        faces = {
            "property_provider": described.provider_id,
            "reference_convention": described.reference_convention,
            "domain": {"T": described.domain["T"], "P": described.domain["P"]},
            "components": described.components,
        }
    n = (0.4, 0.0, 0.6)
    zero = (0.0, 0.0, 0.0)

    def stream(flows: tuple[float, ...], t: float, p: float) -> dict[str, tuple[StreamState]]:
        return {"inlet": (StreamState(n=flows, temperature=t, pressure=p),)}

    def valve(p: float) -> Valve:
        return Valve(unit_id="V", provider=provider, outlet_pressure=p, context=CONTEXT, **faces)

    def ph_flash(duty: float, drop: float = 0.0) -> PHFlash:
        return PHFlash(
            unit_id="P",
            provider=provider,
            duty=duty,
            pressure_drop=drop,
            context=CONTEXT,
            **faces,
        )

    return {
        "pressure_rise(valve)": valve(180e3).evaluate(stream(n, 330.0, P_ATM), CONTEXT),
        "inadmissible_phase(inlet, LIQUID)": valve(50e3).evaluate(stream(n, 390.0, P_ATM), CONTEXT),
        "pressure_outside_domain(outlet)": ph_flash(0.0, 10e3).evaluate(
            stream(n, 330.0, 35e3), CONTEXT
        ),
        "ph_outside_domain(above)": ph_flash(5e5).evaluate(stream(n, 330.0, P_ATM), CONTEXT),
        "duty_into_dormant_stream": ph_flash(1.0).evaluate(stream(zero, 330.0, P_ATM), CONTEXT),
    }


def test_r840_a_wilson_valve_and_ph_flash_failure_name_wilson() -> None:
    """Each typed failure of the valve and the PH flash on `wilson-ig-v2` carries the bound
    provider's id and `WILSON-IG-ref-v1` (ADR 0001 D5.2), not SYN-001's label."""
    for code, failure in _labelled(fresh_provider(WILSON_BASIS)).items():
        assert failure.status != "ok" and failure.message.split("\n", 1)[0] == code
        assert (failure.provider_id, failure.reference_convention) == (
            "wilson-ig-v2",
            "WILSON-IG-ref-v1",
        ), code


def test_r840_syn001s_failure_label_is_the_same_constant() -> None:
    """The same failures on SYN-001 keep the label they always had: SYN-001's convention and no
    provider id."""
    for code, failure in _labelled(Syn001Provider()).items():
        assert failure.status != "ok" and failure.message.split("\n", 1)[0] == code
        assert (failure.provider_id, failure.reference_convention) == ("", REFERENCE_CONVENTION)


# -- S11.A80: GP-M1, the Wilson compressor ---------------------------------------------------------


def _pure_vapour_enthalpy(
    provider: PropertyProvider, flows: tuple[float, ...], temperature: float, pressure: float
) -> float:
    """Σ_j n_j h_j(T, P), h_j the provider's VAPOR h at the pure composition e_j."""
    total = 0.0
    for j, flow in enumerate(flows):
        pure = tuple(1.0 if k == j else 0.0 for k in range(len(flows)))
        result = provider.evaluate_phase(
            PropertyRequest(
                state=StreamState(n=pure, temperature=temperature, pressure=pressure),
                phase="VAPOR",
                properties=("h",),
            ),
            CONTEXT,
        )
        assert result.status == "ok", result.message
        total += flow * result.values["h"]
    return total


def test_a80_gp_m1_wilson_compressor(gamma_phi: list[int], monkeypatch: pytest.MonkeyPatch) -> None:
    """S11.A80: VERIFIED with the γ–φ dispatch; W = Σ_j n_j[h_j(T_s, P_O) − h_j(T_I, P_I)]/η with
    T_s from the verifier's own bisection, within τ_E; the outlet's `stability` is
    STABLE_WITHIN_TESTED_SCOPE; the outlet inside the records' 400 K with a dew-point margin of
    at least 5 K at both ends. Measured: CONVERGED, 41 checks; T_O 391.72 K, W 878.17 W, equal to
    the verifier's Ḣ_s form to 0.0 W; dew margins 31.2 K (inlet) and 47.7 K (outlet); the
    outlet's liquid-trial tm 0.826; |Z| = 2 (the ethanol columns), one-sided worst 1.75e-10."""
    admit_machines(monkeypatch)
    certificate, state, witness, _ = certified(committed_case("GP-M1"), gamma_phi)
    assert_verified(certificate)
    assert {c.id for c in certificate.checks if c.category == "energy_balance"} >= {
        "energy_balance.M",
        "energy_balance.envelope",
    }
    assert "specification.M.isentropic_work" in {c.id for c in certificate.checks}
    provider = fresh_provider(WILSON_BASIS)
    inlet, outlet = _stream(state, "S1"), _stream(state, "S2")
    assert (inlet.temperature, inlet.pressure) == GP_M1_INLET
    assert outlet.pressure == GP_M1_OUTLET_P
    isentropic = additive_isentropic_enthalpy(
        provider, CONTEXT, inlet.n, inlet.temperature, inlet.pressure, outlet.pressure
    )
    entering = _pure_vapour_enthalpy(provider, inlet.n, inlet.temperature, inlet.pressure)
    work = state[work_id("M")]
    assert abs(work - (isentropic - entering) / 0.8) <= TAU_E, work
    report = provider.stability(outlet, "VAPOR", CONTEXT)  # type: ignore[attr-defined]
    assert report.label == "STABLE_WITHIN_TESTED_SCOPE", report
    assert outlet.temperature <= 400.0
    for end in (inlet, outlet):
        dew = band_temperature(provider, end.n, end.pressure, 1.0, CONTEXT)
        assert dew.position == "inside"
        assert end.temperature - dew.temperature >= 5.0, (end, dew.temperature)
    assert witness["Z"] == 2  # the ethanol columns of S1 and S2
    assert witness["one_sided_worst"] <= DERIVATIVE_TOLERANCE / 10, witness


# -- S11.A81: GP-M2, a Wilson turbine whose expansion crosses the dew point; no pump on Wilson -----


def test_a81_gp_m2_a_wilson_turbine_crossing_the_dew_point_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """S11.A81: C-MW's vapour 2.75 K above its dew point at 150 kPa (372.25 K), expanded to 90 kPa
    (dew point 358.47 K): T_s = 336.82 K, a vapour the provider judges UNSTABLE, so the machine
    refuses at initialization, typed, before any Newton step. A81 admits either code; with
    S11D WO-I1b B's reading it is `isentropic_state_two_phase(M)` (without it, the outlet's
    `phase_regime_mismatch(S2)`)."""
    admit_machines(monkeypatch)
    document = committed_case("GP-M2")
    _, _, run = solve(document)
    assert run.outcome == "INITIALIZATION_FAILED", (run.outcome, run.message)
    assert run.message is not None
    assert run.message.split("\n", 1)[0] in {
        "initializer_failed(M): isentropic_state_two_phase(M)",
        "initializer_failed(M): phase_regime_mismatch(S2)",
    }, run.message
    provider = fresh_provider(WILSON_BASIS)
    feed = StreamState(n=(0.4, 0.0, 0.6), temperature=GP_M2_INLET[0], pressure=GP_M2_INLET[1])
    assert band_temperature(provider, feed.n, feed.pressure, 1.0, CONTEXT).temperature < (
        feed.temperature
    )
    dew = band_temperature(provider, feed.n, GP_M2_OUTLET_P, 1.0, CONTEXT).temperature
    assert 358.4 < dew < 358.5


def test_a81_the_pump_is_not_admitted_on_wilson() -> None:
    """A81's other half at unit level: `thermal.pump` on `wilson-ig-v2` is refused at construction
    `provider_not_admitted(thermal.pump)`. The binder's `model_unsupported(thermal.pump)` with the
    no-volume reason is I1b's `_UNADMITTED` text, written at its registration commit."""
    with pytest.raises(SpecificationError, match=r"^provider_not_admitted\(thermal\.pump\)\n"):
        ThermalMachine(
            unit_id="P",
            machine="pump",
            provider=fresh_provider(WILSON_BASIS),
            context=CONTEXT,
            streams={"inlet": ("S1",), "outlet": ("S2",)},
            forms={"S1": "LIQUID", "S2": "LIQUID"},
            outlet_pressure=2.0e5,
            efficiency=0.75,
        )
