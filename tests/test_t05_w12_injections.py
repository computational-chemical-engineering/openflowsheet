"""T05 W12, A22: the injected false successes INJ-T1…T4 through the verifier.

Spec `docs/derivations/T05-unit-models-spec.md` §12.5 and `ref.injections`; design note
`docs/design/T05-generalization.md` §8 (W12). Each injection runs on a mini-revision — a feed (two
for the exchanger), the unit, a sink per outlet — written here as a test fixture, not a registry
case. The state is obtained by a real solve: `plan_revision`/`execute_plan` where the traversal
reaches it (INJ-T1, T3, T4), else `solve_region(..., state=<twin state>, initializer_source=
"user_guess")` (INJ-T2: the exchanger's causal evaluator refuses HX-F1's temperature cross, which
is the point). The injected state is then judged by `verify_revision(..., state=<injected>)`, so
the solver called it `CONVERGED` and the verifier must say `FAILED`: a detected false success.

Every registered number is read from `ref.injections` (or `ref.unit_cases` for the state it
perturbs) and compared at spec §14's tolerance for its kind. A value §12.5 does not register is
asserted by its verdict only.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import Any

import pytest
from t05_support import (
    BETA_TOLERANCE,
    ENERGY_TOLERANCE,
    FLOW_TOLERANCE,
    REF,
    TEMPERATURE_TOLERANCE,
    error,
)
from t05_w12_support import (
    POLICY,
    Feed,
    Outlet,
    bind,
    connection_pin,
    mini_revision,
    planned_step,
    solve_from,
    unit_instance,
)

from openflowsheet.application.revision_binding import RevisionBinding
from openflowsheet.models.syn001.conversion_reactor import MOLAR_MASSES
from openflowsheet.orchestrator.execution import ExecutionPlan
from openflowsheet.orchestrator.executor import execute_plan
from openflowsheet.orchestrator.revision import plan_revision
from openflowsheet.verify import CheckResult
from openflowsheet.verify.certificate import SolutionCertificate, verify_revision

INJECTIONS: dict[str, Any] = REF["injections"]
CASES: dict[str, Any] = REF["unit_cases"]
#: Spec §12.5: each injection fails by at least `10³ τ` (generator-checked).
DETECTION_FACTOR = float(REF["constants"]["detection_factor"])


def _inputs(case: str, port: str = "inlet") -> tuple[tuple[float, float, float], float, float]:
    document = CASES[case]["inputs"][port]
    flows = tuple(float(n) for n in document["n_mol_per_s"])
    assert len(flows) == 3
    return (flows[0], flows[1], flows[2]), float(document["T_K"]), float(document["P_Pa"])


def _executed(document: dict[str, Any]) -> tuple[RevisionBinding, Any, Any]:
    """`plan_revision` then `execute_plan`: the traversal start, the region Newton, converged."""
    binding = bind(document)
    plan, _ = plan_revision(binding, POLICY)
    assert isinstance(plan, ExecutionPlan), plan
    run = execute_plan(plan=plan, flowsheet=binding.flowsheet, spec=binding.spec, policy=POLICY)
    assert run.outcome == "CONVERGED", run.message
    return binding, plan.steps[-1].solve_plan, run


def _judged(
    document: dict[str, Any],
    binding: RevisionBinding,
    result: Any,
    solve_plan: Any,
    state: Mapping[str, float],
) -> tuple[SolutionCertificate, dict[str, CheckResult], list[str]]:
    certificate = verify_revision(binding, document, result, state=state, solve_plan=solve_plan)
    assert certificate.verification_status == "FAILED", certificate.limitations
    assert certificate.false_success_detected
    by_id = {check.id: check for check in certificate.checks}
    failing = sorted(check.id for check in certificate.checks if check.result == "fail")
    return certificate, by_id, failing


def _value(check: CheckResult) -> float:
    assert check.value is not None, check.id
    return check.value


def _registered(check: CheckResult, expected: str, tolerance: float) -> None:
    """The check fails, carries the registered value to §14's tolerance, and misses its own `τ`
    by at least spec §12.5's `10³` (a detection with margin, not one on the threshold)."""
    assert check.result == "fail", check.id
    assert error(_value(check), expected) <= tolerance, (
        f"{check.id} = {check.value!r}, registered {expected}"
    )
    assert check.tolerance is not None
    assert abs(_value(check)) >= DETECTION_FACTOR * check.tolerance, check.id


def _passing(by_id: Mapping[str, CheckResult], prefix: str) -> list[str]:
    """Every check under `prefix`, which must all pass; returns their ids."""
    found = [name for name in by_id if name.startswith(prefix)]
    assert found, prefix
    failed = [name for name in found if by_id[name].result != "pass"]
    assert failed == [], failed
    return found


# -- INJ-T1: the valve's classical trivial root ----------------------------------------------


def _valve() -> dict[str, Any]:
    flows, temperature, pressure = _inputs("VLV-2")
    outlet_pressure = float(CASES["VLV-2"]["inputs"]["outlet_pressure"])
    return mini_revision(
        "INJ-T1",
        unit_instance("SYN-001-UL-C1", "U-VLV"),
        [Feed("inlet", "S1", "liquid", flows, temperature, pressure)],
        [Outlet("outlet", "S2", "vapor_liquid")],
        [connection_pin("SPEC-valve-P", "S2", "state.P", outlet_pressure)],
    )


def test_inj_t1_the_valves_trivial_root_is_caught_by_the_fresh_flash_and_the_split() -> None:
    """VLV-2 solved (`TWO_PHASE`, `T = 348.4999 K`), then its outlet split forced `LIQUID` at the
    PH trivial root `T = 360.08 K`: every valve row still vanishes, because the compiled
    `VLV-energy` reads the lifted split; the fresh flash, the admissibility sum and the
    independent split do not."""
    document = _valve()
    binding, solve_plan, run = _executed(document)
    entry = INJECTIONS["INJ-T1"]
    assert run.state is not None
    # The solve found VLV-2's true root, which the injection replaces.
    assert error(run.state["S2.T"], entry["true_T_K"]) <= TEMPERATURE_TOLERANCE

    state = dict(run.state)
    state["S2.T"] = float(entry["T_trivial_K"])
    for c in "ABC":
        state[f"S2.vap.{c}"] = 0.0
        state[f"S2.liq.{c}"] = state[f"S2.n.{c}"]
    state["S2.V"] = 0.0
    state["S2.L"] = sum(state[f"S2.n.{c}"] for c in "ABC")

    _, by_id, failing = _judged(document, binding, run, solve_plan, state)
    assert failing == [
        "energy_balance.U-VLV",
        "energy_balance.envelope",
        "independent_split.U-VLV.S2.A",
        "independent_split.U-VLV.S2.B",
        "independent_split.U-VLV.S2.C",
        "independent_split.U-VLV.S2.total",
        "phase_admissibility.U-VLV.S2.bubble",
    ]
    # §12.5's values. The fresh-flash gap is registered as a magnitude; §12.2's `Ḣ(in) − Ḣ(out)`
    # is negative because the outlet's own flash at 360.08 K is part vapour.
    _registered(
        by_id["phase_admissibility.U-VLV.S2.bubble"],
        entry["admissibility_sum_xK_minus_1"],
        BETA_TOLERANCE,
    )
    _registered(
        by_id["energy_balance.U-VLV"], f"-{entry['fresh_flash_energy_gap_W']}", ENERGY_TOLERANCE
    )
    _registered(
        by_id["independent_split.U-VLV.S2.total"],
        f"-{entry['independent_split_V_gap_mol_s']}",
        FLOW_TOLERANCE,
    )
    # The envelope sees the same stream pair, so the same gap.
    assert _value(by_id["energy_balance.envelope"]) == _value(by_id["energy_balance.U-VLV"])
    # What passes: every valve row (`VLV-energy` included), every material balance.
    rows = _passing(by_id, "residual.U-VLV:")
    assert "residual.U-VLV:VLV-energy" in rows
    assert abs(_value(by_id["residual.U-VLV:VLV-energy"])) <= ENERGY_TOLERANCE
    _passing(by_id, "material_balance.")


# -- INJ-T2: the exchanger's rows solved across a temperature cross --------------------------


def _exchanger() -> dict[str, Any]:
    hot, hot_t, hot_p = _inputs("HX-F1", "hot_inlet")
    cold, cold_t, cold_p = _inputs("HX-F1", "cold_inlet")
    inputs = CASES["HX-F1"]["inputs"]
    assert inputs["specification"] == "cold_outlet_temperature"
    return mini_revision(
        "INJ-T2",
        unit_instance("SYN-001-UL-C3", "U-HX"),
        [
            Feed("hot_inlet", "S1", "liquid", hot, hot_t, hot_p),
            Feed("cold_inlet", "S2", "liquid", cold, cold_t, cold_p),
        ],
        [Outlet("hot_outlet", "S3", "liquid"), Outlet("cold_outlet", "S4", "liquid")],
        [
            # The builder takes exactly one exchanger specification; C3's is on the hot outlet.
            connection_pin("SPEC-hx-T", "S4", "state.T", float(inputs["value"]))
        ],
    )


def _hx_f1_state() -> dict[str, float]:
    """HX-F1's registered solution of the rows, as doubles, by column."""
    expected = CASES["HX-F1"]["expected"]
    state: dict[str, float] = {}
    streams = {
        "S1": CASES["HX-F1"]["inputs"]["hot_inlet"],
        "S2": CASES["HX-F1"]["inputs"]["cold_inlet"],
        "S3": expected["hot_outlet"],
        "S4": expected["cold_outlet"],
    }
    for stream, document in streams.items():
        for c, n in zip("ABC", document["n_mol_per_s"], strict=True):
            state[f"{stream}.n.{c}"] = float(n)
        state[f"{stream}.T"] = float(document["T_K"])
        state[f"{stream}.P"] = float(document["P_Pa"])
    state["U-HX.Q"] = float(expected["duty_W"])
    return state


def test_inj_t2_the_exchangers_hot_end_cross_is_the_one_failing_check() -> None:
    """HX-F1's rows have a solution with `T_co = 345 K` above `T_hi = 340 K`. The traversal cannot
    reach it (the causal evaluator refuses `temperature_cross(hot_end)`), so the region is solved
    from it; every row and balance holds and only the one-sided hot-end check fails, `+5 K`."""
    document = _exchanger()
    binding = bind(document)
    result, step = solve_from(binding, _hx_f1_state())
    assert result.outcome == "CONVERGED", result.message
    entry = INJECTIONS["INJ-T2"]

    _, by_id, failing = _judged(document, binding, result, step.solve_plan, dict(result.state))
    assert failing == ["bounds_and_domain.U-HX.hot_end"]
    # §12.2: the check's value is `−(T_hi − T_co)`; `ref` registers `T_hi − T_co`.
    _registered(
        by_id["bounds_and_domain.U-HX.hot_end"],
        str(-Decimal(entry["hot_end_K"])),
        TEMPERATURE_TOLERANCE,
    )
    # What passes: every exchanger row and balance; the other end and the heat flow too.
    _passing(by_id, "residual.U-HX:")
    _passing(by_id, "material_balance.U-HX.")
    _passing(by_id, "energy_balance.U-HX.")
    _passing(by_id, "specification.U-HX.")
    assert error(-_value(by_id["bounds_and_domain.U-HX.cold_end"]), entry["cold_end_K"]) <= (
        TEMPERATURE_TOLERANCE
    )
    assert error(-_value(by_id["bounds_and_domain.U-HX.heat_flow"]), entry["duty_W"]) <= (
        ENERGY_TOLERANCE
    )
    assert by_id["bounds_and_domain.U-HX.cold_end"].result == "pass"
    assert by_id["bounds_and_domain.U-HX.heat_flow"].result == "pass"


def test_inj_t2_the_traversal_cannot_reach_it() -> None:
    """Why INJ-T2 needs the region solve from the twin state: the plan's own start is refused."""
    document = _exchanger()
    binding = bind(document)
    plan, _ = plan_revision(binding, POLICY)
    run = execute_plan(plan=plan, flowsheet=binding.flowsheet, spec=binding.spec, policy=POLICY)
    assert [(step.outcome, step.message) for step in run.steps] == [
        ("INITIALIZATION_FAILED", "initializer_failed(U-HX): temperature_cross(hot_end)")
    ]
    assert planned_step(binding).region is not None


# -- INJ-T3: a permuted stoichiometry that conserves moles and mass ---------------------------


def _reactor() -> dict[str, Any]:
    flows, temperature, pressure = _inputs("RX-2")
    inputs = CASES["RX-2"]["inputs"]
    unit = unit_instance("SYN-001-UL-C2", "U-RX")
    # C2's reactor is RX-2's reaction (`ν`, key A, `X = 1/2`, no drop); stated, not assumed.
    parameters = {name: quantity["value"] for name, quantity in unit["parameters"].items()}
    assert parameters == {
        **{f"nu.{c}": float(nu) for c, nu in zip("ABC", inputs["nu"], strict=True)},
        f"conversion.{inputs['key']}": float(inputs["conversion"]),
        "pressure_drop": float(inputs["pressure_drop"]),
    }
    assert inputs["energy_specification"] == "outlet_temperature"
    return mini_revision(
        "INJ-T3",
        unit,
        [Feed("inlet", "S1", "vapor", flows, temperature, pressure)],
        [Outlet("outlet", "S2", "vapor_liquid")],
        [connection_pin("SPEC-reactor-outlet-T", "S2", "state.T", float(inputs["value"]))],
    )


#: Spec §12.5: the permutation `ν' = (−1, −2, 3)` of RX-2's `ν = (−2, −1, 3)`.
NU_PERMUTED = (-1.0, -2.0, 3.0)


def test_inj_t3_a_permuted_stoichiometry_fails_per_component() -> None:
    """RX-2 solved, then its outlet rebuilt from `ν'` at the right extent, with the split, the
    duty and the energy balance consistent with that outlet (what a solver whose rows carried `ν'`
    would report). Moles and mass are conserved; the per-component balances with the revision's
    `ν` are not, by `∓0.3 mol/s`.

    The compiled `RX-mole` rows carry the revision's `ν` too, so they fail at the injected state
    as well: the injection models a defect in the rows the solver ran, and the verifier's table
    catches it without reading those rows (R-016)."""
    document = _reactor()
    binding, solve_plan, run = _executed(document)
    assert run.state is not None
    extent = run.state["U-RX.xi"]
    assert error(extent, CASES["RX-2"]["expected"]["extent_mol_per_s"]) <= FLOW_TOLERANCE

    state = dict(run.state)
    for c, nu in zip("ABC", NU_PERMUTED, strict=True):
        flow = state[f"S1.n.{c}"] + nu * extent
        state[f"S2.n.{c}"] = flow
        state[f"S2.vap.{c}"] = flow  # RX-2's outlet is vapour: the split is all vapour
        state[f"S2.liq.{c}"] = 0.0
    state["S2.V"] = sum(state[f"S2.vap.{c}"] for c in "ABC")
    state["S2.L"] = 0.0
    # The duty that balances the permuted outlet, from the verifier's own fresh-flash enthalpies
    # at the solved state: `Q' = Ḣ(out') − Ḣ(in)`, so the energy balance is not what fails.
    probe = verify_revision(binding, document, run, state=state, solve_plan=solve_plan)
    gap = next(c for c in probe.checks if c.id == "energy_balance.U-RX").value
    assert gap is not None
    state["U-RX.Q"] = state["U-RX.Q"] - gap

    certificate, by_id, failing = _judged(document, binding, run, solve_plan, state)
    assert failing == [
        "material_balance.U-RX.A",
        "material_balance.U-RX.B",
        "material_balance.envelope.A",
        "material_balance.envelope.B",
        "residual.U-RX:RX-mole:A",
        "residual.U-RX:RX-mole:B",
    ]
    registered = INJECTIONS["INJ-T3"]["component_balance_mol_s"]
    for c, expected in zip("ABC", registered, strict=True):
        check = by_id[f"material_balance.U-RX.{c}"]
        if Decimal(expected) == 0:
            assert check.result == "pass" and abs(_value(check)) <= FLOW_TOLERANCE
        else:
            _registered(check, expected, FLOW_TOLERANCE)
    # What passes: total moles and mass, both conserved (`Σ ν' = 0`, equal molar masses) — the
    # reason a mole or mass envelope could not stand in for the per-component check.
    values = [_value(by_id[f"material_balance.U-RX.{c}"]) for c in "ABC"]
    assert error(sum(values), INJECTIONS["INJ-T3"]["total_moles_mol_s"]) <= FLOW_TOLERANCE
    mass = sum(m * v for m, v in zip(MOLAR_MASSES, values, strict=True))
    assert error(mass, INJECTIONS["INJ-T3"]["mass_balance_kg_s"]) <= FLOW_TOLERANCE
    assert by_id["energy_balance.U-RX"].result == "pass"
    assert by_id["phase_admissibility.U-RX.S2.dew"].result == "pass"
    _passing(by_id, "independent_split.U-RX.S2.")


# -- INJ-T4: the pump's work without its efficiency -------------------------------------------


def _pump() -> dict[str, Any]:
    flows, temperature, pressure = _inputs("PUMP-1")
    inputs = CASES["PUMP-1"]["inputs"]
    unit = unit_instance("SYN-001-UL-C1", "U-PUMP")
    assert unit["parameters"]["efficiency"]["value"] == float(inputs["efficiency"])
    return mini_revision(
        "INJ-T4",
        unit,
        [Feed("inlet", "S1", "liquid", flows, temperature, pressure)],
        [Outlet("outlet", "S2", "liquid")],
        [connection_pin("SPEC-pump-P", "S2", "state.P", float(inputs["outlet_pressure"]))],
    )


def test_inj_t4_the_pumps_ideal_work_fails_the_work_relation_only() -> None:
    """PUMP-1 solved, then `W = W_s` (the isothermal ideal work, efficiency ignored) with the
    outlet temperature that balances it: SYN-001's liquid enthalpy is `c_p (T − T_0) + v (P −
    P_0)`, so an isothermal compression's enthalpy rise is `W_s` itself and `T_out = T_in`. The
    energy balance holds; the work relation `η W − ΔḢ^L` is `−(1 − η) W_s = −4.8 W`."""
    document = _pump()
    binding, solve_plan, run = _executed(document)
    assert run.state is not None
    expected = CASES["PUMP-1"]["expected"]
    assert error(run.state["U-PUMP.W"], expected["work_W"]) <= ENERGY_TOLERANCE

    state = dict(run.state)
    state["U-PUMP.W"] = float(expected["work_ideal_W"])
    state["S2.T"] = state["S1.T"]

    _, by_id, failing = _judged(document, binding, run, solve_plan, state)
    # The compiled `PUMP-work` row is the same relation, so it fails with the same value.
    assert failing == ["energy_balance.U-PUMP.work_relation", "residual.U-PUMP:PUMP-work"]
    entry = INJECTIONS["INJ-T4"]
    _registered(
        by_id["energy_balance.U-PUMP.work_relation"], entry["work_relation_W"], ENERGY_TOLERANCE
    )
    balance = by_id["energy_balance.U-PUMP"]
    assert balance.result == "pass"
    assert error(_value(balance), entry["energy_balance_W"]) <= ENERGY_TOLERANCE


@pytest.mark.parametrize("injection", ["INJ-T1", "INJ-T2", "INJ-T3", "INJ-T4"])
def test_every_registered_injection_is_exercised(injection: str) -> None:
    """The registry's injection list is this file's: nothing registered goes unexercised."""
    assert injection in INJECTIONS
    assert set(INJECTIONS) == {"INJ-T1", "INJ-T2", "INJ-T3", "INJ-T4"}
