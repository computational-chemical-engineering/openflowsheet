"""S11 WO-C6: the `thermal.*` flowsheets solved through the region (S11 units design §5.2 C6, §6.1).

The spike first (Q18): does the region backtrack on a block's `invalid_trial_state` during a Newton
trial? A duty-mode heater with a liquid outlet, started cold, takes a full Newton step past T_sat;
the liquid block refuses it (`phase_not_stable`, a `DomainError`), the compiled boundary reports
`invalid_trial_state`, and the Newton core halves the step. TH-V1 (valve → drum) is the first
registered case through the region. The seven models are rows of the binder's tables (I1b);
"VERIFIED" here is the C5 check set
(`test_s11_thermal_verifier.verifier_checks`, the I1b hook's assembly) at x_final, every check
computed and passing.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
import yaml
from m02_c1_support import connection, quantity, revision
from s07_coolprop_support import require_coolprop
from s11_thermal_support import CASES, _water, committed_case, solve
from test_s11_thermal_binding import (
    dimensionless,
    duty,
    feed,
    instance,
    outlet_pressure,
    outlet_temperature,
)
from test_s11_thermal_verifier import CONTEXT, evaluated_state, verifier_checks

from openflowsheet.application.policies import T04_W12
from openflowsheet.application.revision_binding import RevisionBinding, bind_revision_flowsheet
from openflowsheet.models.revision_flowsheet import parse_revision
from openflowsheet.models.thermal.kernel import Sat, phase_properties, saturation
from openflowsheet.orchestrator.executor import PlanResult, execute_plan
from openflowsheet.orchestrator.revision import plan_revision
from openflowsheet.orchestrator.splits import DORMANCY_RULES, DormancyRule
from openflowsheet.thermo import PropertyProvider, StreamState
from openflowsheet.thermo.iapws95 import Iapws95Provider
from openflowsheet.verify import CheckResult
from openflowsheet.verify.certificate import SolutionCertificate, verify_revision
from openflowsheet.verify.checks import KIND_TOLERANCE
from openflowsheet.verify.thermal import enthalpy_map

ROOT = Path(__file__).resolve().parents[1]

TAU_E = KIND_TOLERANCE["heat_rate"]
TAU_FLOW = KIND_TOLERANCE["molar_flow"]
TAU_T = KIND_TOLERANCE["temperature"]


def accepted_steps(run: PlanResult) -> int:
    return sum(1 for event in run.trace.events if event.kind == "step_accepted")


def all_pass(
    document: Mapping[str, Any],
    state: Mapping[str, float],
    provider: PropertyProvider | None = None,
) -> list[CheckResult]:
    """Every C5 check at `state` is computed and passes (the column-free `independent_split`
    rows are `not_applicable` by design, C5's A64 test)."""
    checks = verifier_checks(parse_revision(document), state, provider)
    assert checks
    for check in checks:
        if check.category == "independent_split":
            assert (check.result, check.reason) == ("not_applicable", "temperature_degenerate")
            continue
        assert check.result == "pass", (check.id, check.result, check.value, check.reason)
    return checks


@pytest.mark.parametrize("name", sorted(CASES))
def test_the_committed_case_is_the_generated_one(name: str) -> None:
    """`benchmarks/s11/thermal/<name>.json` is `CASES[name]()` (regenerate with
    `python tests/s11_thermal_support.py`)."""
    assert committed_case(name) == CASES[name]()


# -- Q18: the spike --------------------------------------------------------------------------------


def _heater(specification: dict[str, Any]) -> dict[str, Any]:
    """Liquid H2O at 1 MPa, 300 K → heater (liquid outlet) → sink."""
    return _water(
        "S11-C6-SPIKE",
        [
            instance("F", "syn001.feed_source"),
            instance("H", "thermal.heater"),
            instance("K", "syn001.product_sink"),
        ],
        [
            connection("S1", ("F", "outlet"), ("H", "inlet"), "liquid"),
            connection("S2", ("H", "outlet"), ("K", "inlet"), "liquid"),
        ],
        [*feed("S1", "H2O", 300.0, 1.0e6), specification],
    )


def test_q18_the_region_backtracks_on_a_blocks_invalid_trial_state() -> None:
    """Q18: the duty that takes 300 K liquid to 452.5 K at 1 MPa (T_sat 453.03 K), solved from a
    start with the outlet at 300 K. The first full Newton step lands above T_sat; the trial is
    rejected `invalid_trial` with the liquid block's `phase_not_stable`, the step halves, and
    the solve converges to the T-mode root."""
    _, by_temperature = solve(_heater(outlet_temperature("H", 452.5)))
    assert by_temperature.outcome == "CONVERGED"
    assert by_temperature.state is not None
    q = by_temperature.state["H.Q"]
    document = _heater(duty("H", q))
    start = dict(by_temperature.state)
    start["S2.T"] = 300.0
    _, run = solve(document, user_start=start)
    assert run.outcome == "CONVERGED", run.message
    assert run.state is not None
    rejected = [
        event
        for event in run.trace.events
        if event.kind == "trial" and event.rejection_reason == "invalid_trial"
    ]
    assert rejected, "no trial was rejected: the start no longer probes Q18"
    for event in rejected:
        assert event.alpha == 1.0
        assert "phase_not_stable" in event.message and "LIQUID" in event.message
    halved = [e for e in run.trace.events if e.kind == "step_accepted" and e.alpha == 0.5]
    assert len(halved) == len(rejected)
    assert abs(run.state["S2.T"] - 452.5) <= TAU_T


# -- TH-V1 -----------------------------------------------------------------------------------------


def test_th_v1_valve_to_drum_converges_and_verifies() -> None:
    """TH-V1 through the region from the traversal start: CONVERGED; the state is the units' own
    sequential evaluation; every C5 check passes; Ḣ_S1 = Ḣ_S3 + Ḣ_S4 (Q = 0) within τ_E."""
    document = committed_case("TH-V1")
    binding, run = solve(document)
    assert run.outcome == "CONVERGED", run.message
    assert run.state is not None
    state = dict(run.state)
    sequential = evaluated_state(document)
    for column in binding.spec.variable_ids:
        kind = binding.spec.variable_kinds[column]
        assert abs(state[column] - sequential[column]) <= KIND_TOLERANCE[kind], column
    checks = {check.id: check for check in all_pass(document, state)}
    for stream in ("S2", "S3", "S4"):
        assert checks[f"phase_admissibility.stream.{stream}.saturation"].result == "pass"
        assert checks[f"phase_admissibility.stream.{stream}.fraction"].result == "pass"
    assert state["S3.sat.L"] == 0.0 and state["S4.sat.V"] == 0.0
    beta = state["S2.sat.V"] / state["S2.n.H2O"]
    assert 0.0 < beta < 1.0
    assert abs(state["S3.n.H2O"] - beta * state["S1.n.H2O"]) <= TAU_FLOW


# -- §4.9: the dormancy registry, and S11.A62 ------------------------------------------------------


def test_the_dormancy_registry_holds_the_thermal_entries() -> None:
    """§4.9, literally: one rule per single-phase outlet whose temperature no row reads at
    dormancy; every other configuration a key with no rule; `thermal.flash` absent."""
    forms = ("LIQUID", "VAPOR", "SATURATED")
    expected: dict[tuple[str, str | None], tuple[DormancyRule, ...]] = {
        **{("thermal.heater", f"{m}:{f}"): () for m in ("T", "duty", "quality") for f in forms},
        **{
            (model, f): ()
            for model in (
                "thermal.valve",
                "thermal.mixer",
                "thermal.pump",
                "thermal.compressor",
                "thermal.turbine",
            )
            for f in forms
        },
    }
    for key, swapped, form in (
        (("thermal.heater", "duty:LIQUID"), "TH-energy", "LIQUID"),
        (("thermal.heater", "duty:VAPOR"), "TH-energy", "VAPOR"),
        (("thermal.valve", "LIQUID"), "TV-energy", "LIQUID"),
        (("thermal.valve", "VAPOR"), "TV-energy", "VAPOR"),
        (("thermal.mixer", "LIQUID"), "TM-energy", "LIQUID"),
        (("thermal.mixer", "VAPOR"), "TM-energy", "VAPOR"),
        (("thermal.pump", "LIQUID"), "TPU-energy", "LIQUID"),
        (("thermal.compressor", "VAPOR"), "TCO-energy", "VAPOR"),
        (("thermal.turbine", "VAPOR"), "TTU-energy", "VAPOR"),
    ):
        expected[key] = (DormancyRule("outlet", "inlet", swapped, None, form),)
    thermal = {key: rules for key, rules in DORMANCY_RULES.items() if key[0].startswith("thermal.")}
    assert thermal == expected


def _dormant_heater(q: float) -> dict[str, Any]:
    """F → splitter (fraction 0) → recycle → heater (duty `q`, liquid outlet) → sink; the purge to
    a sink. The heater's inlet is exactly dormant."""
    return _water(
        "S11-C6-A62",
        [
            instance("F", "syn001.feed_source"),
            instance(
                "SP",
                "syn001.stream_splitter",
                {"split_fraction": quantity(0.0, "1", "dimensionless", [0] * 7)},
            ),
            instance("H", "thermal.heater"),
            instance("K1", "syn001.product_sink"),
            instance("K2", "syn001.product_sink"),
        ],
        [
            connection("S1", ("F", "outlet"), ("SP", "inlet"), "liquid"),
            connection("S2", ("SP", "recycle"), ("H", "inlet"), "liquid"),
            connection("S3", ("SP", "purge"), ("K2", "inlet"), "liquid"),
            connection("S4", ("H", "outlet"), ("K1", "inlet"), "liquid"),
        ],
        [*feed("S1", "H2O", 300.0, 1.0e6), duty("H", q)],
    )


def test_a62_a_dormant_heater_with_zero_duty_converges_on_the_label_row() -> None:
    """S11.A62 (Q_spec = 0, `T05b-phase-contract-v2`): CONVERGED in the attempt whose signature
    holds `H.outlet` ZERO_FLOW, the outlet at its label temperature."""
    _, run = solve(_dormant_heater(0.0))
    assert run.outcome == "CONVERGED", run.message
    assert run.state is not None
    (step,) = run.steps
    assert step.detail.attempts[-1].signature == (("H.outlet", "ZERO_FLOW"),)
    assert run.state["S2.n.H2O"] == 0.0 and run.state["S4.n.H2O"] == 0.0
    assert run.state["S4.T"] == run.state["S2.T"] == 300.0
    assert run.state["H.Q"] == 0.0


def test_a62_a_dormant_heater_with_a_duty_is_a_specification_conflict() -> None:
    """S11.A62 (Q_spec = 1 kW): `SPECIFICATION_CONFLICT` `zero_flow_conflict(H:TH-energy)`."""
    _, run = solve(_dormant_heater(1.0e3))
    assert run.outcome == "SPECIFICATION_CONFLICT"
    assert run.message == "zero_flow_conflict(H:TH-energy)"


def _under_v1(document: dict[str, Any]) -> tuple[PlanResult, SolutionCertificate | None]:
    """Bind, plan and execute under `T04-W12` (the v1 phase contract); certify a converged run."""
    binding = bind_revision_flowsheet(document)
    assert isinstance(binding, RevisionBinding), binding
    plan, _ = plan_revision(binding, T04_W12)
    run = execute_plan(plan=plan, flowsheet=binding.flowsheet, spec=binding.spec, policy=T04_W12)
    if run.outcome != "CONVERGED":
        return run, None
    return run, verify_revision(binding, document, run, solve_plan=plan.steps[-1].solve_plan)


def _dormant_syn001_pump() -> dict[str, Any]:
    """`_dormant_heater`'s topology on SYN-001's basis with the SYN-001 pump (0.1 → 0.18 MPa,
    eta = 0.75, PUMP-1's pressures) in the heater's place: its inlet is exactly dormant."""
    fraction = quantity(0.0, "1", "dimensionless", [0] * 7)
    return revision(
        [
            instance("F", "syn001.feed_source"),
            instance("SP", "syn001.stream_splitter", {"split_fraction": fraction}),
            instance("P", "syn001.liquid_pump", {"efficiency": dimensionless(0.75)}),
            instance("K1", "syn001.product_sink"),
            instance("K2", "syn001.product_sink"),
        ],
        [
            connection("S1", ("F", "outlet"), ("SP", "inlet"), "liquid"),
            connection("S2", ("SP", "recycle"), ("P", "inlet"), "liquid"),
            connection("S3", ("SP", "purge"), ("K2", "inlet"), "liquid"),
            connection("S4", ("P", "outlet"), ("K1", "inlet"), "liquid"),
        ],
        [
            *feed("S1", "A", 300.0, 1.0e5),
            *(dict(feed("S1", c, 300.0, 1.0e5)[0], id=f"SPEC-S1-n-{c}") for c in ("B", "C")),
            outlet_pressure("P", 1.8e5),
        ],
        components=("A", "B", "C"),
        record_source="benchmarks/syn001/components.yaml",
        revision_id="S11-O-C6-1-PUMP",
    )


def test_o_c6_1_under_v1_a_dormant_heater_is_rank_deficient_or_singular() -> None:
    """Rulings item 10, O-C6-1 (§4.9's v1 sentence, restated): A62's flowsheet under `T04-W12`.
    Q = 0: CONVERGED, the certificate's regularity `RANK_DEFICIENT`. Q = 1 kW:
    `LINEAR_SOLVE_FAILED` (the dormant single-phase outlet's Jacobian is singular)."""
    run, certificate = _under_v1(_dormant_heater(0.0))
    assert run.outcome == "CONVERGED", run.message
    assert certificate is not None
    assert certificate.regularity.status == "RANK_DEFICIENT"
    assert certificate.verification_status == "UNVERIFIED"
    moved, _ = _under_v1(_dormant_heater(1.0e3))
    assert moved.outcome == "LINEAR_SOLVE_FAILED", moved.message


def test_o_c6_1_the_syn001_pumps_dormant_case_under_v1_is_recorded() -> None:
    """Rulings item 10, O-C6-1: the SYN-001 pump's dormant case beside A62, under `T04-W12`.
    Measured (a regression pin, recorded for the design lane): CONVERGED and `VERIFIED` with
    regularity `NO_RANK_LOSS_DETECTED`, not `RANK_DEFICIENT`: the verifier reduces the pump's
    dormant outlet by its own transcription (`verify.zero_flow.DORMANT_OUTLETS`, spec §7.6), under
    either phase contract, and that registry carries no `thermal.*` outlet."""
    run, certificate = _under_v1(_dormant_syn001_pump())
    assert run.outcome == "CONVERGED", run.message
    assert run.state is not None and run.state["S2.n.A"] == 0.0
    assert certificate is not None
    assert certificate.regularity.status == "NO_RANK_LOSS_DETECTED"
    assert certificate.verification_status == "VERIFIED"


# -- S11.A59–A61: the registered cycles and the recycle -------------------------------------------

#: The C6 references: CoolProp 8.0.0's cycles and TH-R1's sequential-modular solution.
FLOWSHEETS = yaml.safe_load((ROOT / "benchmarks/s11/thermal_reference.yaml").read_text())[
    "flowsheets"
]


def energy_closure(
    document: Mapping[str, Any],
    state: Mapping[str, float],
    feeds: tuple[str, ...],
    products: tuple[str, ...],
    provider: PropertyProvider | None = None,
) -> float:
    """Σ(Q + W) − (Ḣ_products − Ḣ_feeds), each Ḣ from a fresh provider (`verify.thermal`'s map)."""
    provider = Iapws95Provider() if provider is None else provider
    enthalpy, _ = enthalpy_map(parse_revision(document), state, provider, CONTEXT)
    supplied = sum(v for k, v in state.items() if k.endswith((".Q", ".W")))
    return supplied - (sum(enthalpy[s] for s in products) - sum(enthalpy[s] for s in feeds))


def test_a59_th_c1_rankine() -> None:
    """S11.A59: CONVERGED and every C5 check passing; the cycle's energy closes within 5 τ_E;
    (−W_t − W_p)/Q_b equals CoolProp's reference cycle within 1e-7 relative."""
    document = committed_case("TH-C1")
    _, run = solve(document)
    assert run.outcome == "CONVERGED", run.message
    assert run.state is not None
    state = dict(run.state)
    all_pass(document, state)
    assert abs(energy_closure(document, state, ("S1",), ("S5",))) <= 5.0 * TAU_E
    reference = FLOWSHEETS["TH-C1"]
    efficiency = (-state["T.W"] - state["P.W"]) / state["B.Q"]
    assert abs(efficiency - reference["efficiency"]) <= 1e-7 * reference["efficiency"]
    for column, key in (("P.W", "W_pump"), ("B.Q", "Q_boiler"), ("T.W", "W_turbine")):
        assert abs(state[column] - reference[key]) <= 1e-7 * abs(reference[key]), column
    beta = state["S4.sat.V"] / state["S4.n.H2O"]
    assert abs(beta - reference["turbine_outlet"]["beta"]) <= 1e-7


def test_a60_th_c2_refrigeration() -> None:
    """S11.A60 on `coolprop-heos-v1` R134a: CONVERGED, every C5 check passing; the COP equals
    the reference within 1e-7 relative."""
    require_coolprop()
    from openflowsheet.thermo.coolprop_heos import CoolPropHeosProvider  # noqa: PLC0415

    document = committed_case("TH-C2")
    _, run = solve(document)
    assert run.outcome == "CONVERGED", run.message
    assert run.state is not None
    state = dict(run.state)
    all_pass(document, state, CoolPropHeosProvider("R134a"))
    closure = energy_closure(document, state, ("S1",), ("S5",), CoolPropHeosProvider("R134a"))
    assert abs(closure) <= 5.0 * TAU_E
    reference = FLOWSHEETS["TH-C2"]
    cop = state["E.Q"] / state["G.W"]
    assert abs(cop - reference["COP"]) <= 1e-7 * reference["COP"]


def test_a61_th_r1_recycle() -> None:
    """S11.A61: CONVERGED, every C5 check passing; every stream's flow and T equal the reference
    script's sequential-modular solution within 1e-6 relative and 1e-5 K; 0.1 < β < 0.9 at the
    drum."""
    document = committed_case("TH-R1")
    _, run = solve(document)
    assert run.outcome == "CONVERGED", run.message
    assert run.state is not None
    state = dict(run.state)
    all_pass(document, state)
    assert abs(energy_closure(document, state, ("S1",), ("S5", "S9"))) <= 5.0 * TAU_E
    reference = FLOWSHEETS["TH-R1"]
    expected = {
        "S2": reference["mixer_outlet"],
        "S3": reference["heater_outlet"],
        "S4": reference["drum"],
        "S7": reference["pump_outlet"],
    }
    drum = reference["drum"]
    flows = {
        **{stream: entry["n"] for stream, entry in expected.items()},
        "S1": 1.0,
        "S5": drum["V"],
        "S6": drum["L"],
        "S8": reference["recycle"]["n"],
        "S9": reference["purge"]["n"],
    }
    for stream, flow in flows.items():
        assert abs(state[f"{stream}.n.H2O"] - flow) <= 1e-6 * flow, stream
    temperatures = {
        **{stream: entry["T"] for stream, entry in expected.items()},
        "S5": drum["T"],
        "S6": drum["T"],
        "S8": reference["pump_outlet"]["T"],
        "S9": reference["pump_outlet"]["T"],
    }
    for stream, temperature in temperatures.items():
        assert abs(state[f"{stream}.T"] - temperature) <= 1e-5, stream
    assert abs(state["S4.sat.V"] - drum["V"]) <= 1e-6 * drum["V"]
    assert abs(state["P.W"] - reference["W_pump"]) <= 1e-6 * reference["W_pump"]
    assert 0.1 < state["S4.sat.V"] / state["S4.n.H2O"] < 0.9


# -- S11.A63 ---------------------------------------------------------------------------------------


def _throttle(outlet: str) -> dict[str, Any]:
    """Liquid at 1 MPa, 450 K → valve (0.2 MPa), outlet declared `outlet` → sink."""
    return _water(
        "S11-C6-A63",
        [
            instance("F", "syn001.feed_source"),
            instance("V", "thermal.valve"),
            instance("K", "syn001.product_sink"),
        ],
        [
            connection("S1", ("F", "outlet"), ("V", "inlet"), "liquid"),
            connection("S2", ("V", "outlet"), ("K", "inlet"), outlet),
        ],
        [*feed("S1", "H2O", 450.0, 1.0e6), outlet_pressure("V", 2.0e5)],
    )


def test_a63_a_liquid_valve_outlet_that_flashes_is_a_regime_mismatch() -> None:
    """S11.A63: the traversal refuses `phase_regime_mismatch(S2)`; the valve's answer, the line
    the traversal reads, carries the hint "declare vapor_liquid". Declared `vapor_liquid`, the
    same throttle converges."""
    binding, run = solve(_throttle("liquid"))
    assert run.outcome == "INITIALIZATION_FAILED"
    assert run.message == "initializer_failed(V): phase_regime_mismatch(S2)"
    valve = next(unit for unit in binding.flowsheet.units() if unit.unit_id == "V")
    feed_state = StreamState(n=(1.0,), temperature=450.0, pressure=1.0e6)
    answer = valve.evaluate({"inlet": [feed_state]}, CONTEXT)
    code, hint = answer.message.split("\n", 1)
    assert (answer.status, code) == ("unsupported", "phase_regime_mismatch(S2)")
    assert hint.endswith("declare vapor_liquid"), hint
    _, corrected = solve(_throttle("vapor_liquid"))
    assert corrected.outcome == "CONVERGED", corrected.message


# -- rulings item 10, Q-C2 (R-839) -----------------------------------------------------------------


def _wet_expansion() -> dict[str, Any]:
    """Steam at 1 MPa, 573.15 K → turbine (0.1 MPa, eta = 0.5), outlet declared `vapor` → sink."""
    return _water(
        "S11-Q-C2",
        [
            instance("F", "syn001.feed_source"),
            instance("T", "thermal.turbine", {"efficiency": dimensionless(0.5)}),
            instance("K", "syn001.product_sink"),
        ],
        [
            connection("S1", ("F", "outlet"), ("T", "inlet"), "vapor"),
            connection("S2", ("T", "outlet"), ("K", "inlet"), "vapor"),
        ],
        [*feed("S1", "H2O", 573.15, 1.0e6), outlet_pressure("T", 1.0e5)],
    )


def test_q_c2_a_revision_turbines_isentropic_state_takes_the_vapour_outlets_form() -> None:
    """Rulings item 10, Q-C2 (L-TH-4): the isentropic state is wet (x_s = 0.9613 on iapws95-v1)
    although the actual outlet is a vapour 2.61 kJ/mol above h^V_sat; a revision cannot state the
    saturated isentropic form, so the turbine is refused `isentropic_state_two_phase(T)`. The
    `isentropic_phase` parameter's refusal is
    `test_s11_thermal_binding::test_the_turbine_takes_no_isentropic_phase_parameter`."""
    provider = Iapws95Provider()
    inlet = phase_properties(provider, CONTEXT, 573.15, 1.0e6, "VAPOR", ("h", "s"))
    sat = saturation(provider, 1.0e5, CONTEXT)
    assert isinstance(inlet, dict) and isinstance(sat, Sat)
    (s_in, _, _), (h_in, _, _) = inlet["s"], inlet["h"]
    s_l, s_v = sat.value("LIQUID", "s"), sat.value("VAPOR", "s")
    h_l, h_v = sat.value("LIQUID", "h"), sat.value("VAPOR", "h")
    x_s = (s_in - s_l) / (s_v - s_l)
    h_out = h_in + 0.5 * (h_l + x_s * (h_v - h_l) - h_in)
    assert round(x_s, 4) == 0.9613
    assert round((h_out - h_v) / 1.0e3, 2) == 2.61
    _, run = solve(_wet_expansion())
    assert run.outcome == "INITIALIZATION_FAILED"
    assert run.message == "initializer_failed(T): isentropic_state_two_phase(T)"
