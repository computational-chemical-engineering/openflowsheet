"""T05b W2: the PH kernel's closure-rows acceptance and its band route (T05b spec §5).

B01 (replaces T05 A29): the 40 near-pure grid calls of §12.1 are `ok`, by the route §5.1 orders,
with the closure's three rows within K04's tolerances and `T`, `V` and every flowing `q_i` within
§13's grid tolerances of the 40-digit reference. B03 and B04: the two provider test doubles of
§12.2 — JUMP, where monotonicity fails and the chain ends in its typed refusal, and BIASED, where
only §5.3's equilibrium clause can see that the flash is wrong. B02 is `test_t05b_kernel_inert.py`.

Every expected value is `ref` (`benchmarks/t05b/reference_values.yaml`); the rows are evaluated
here from the provider, not read from the kernel. The routes are regression values
(self-generated): pinned, and a change is reported to the design lane, never re-pinned.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

import pytest
from t05_support import CONTEXT, PROVIDER, first_line
from t05b_support import REF, Biased, Jump, error, number

from openflowsheet.models.syn001.ph_kernel import (
    BETA_WIDTH_FLOOR,
    EQUILIBRIUM_TOLERANCE,
    MAX_BAND_EVALUATIONS,
    PHState,
    ph_state,
)
from openflowsheet.thermo import FlashRequest, PropertyRequest, StreamState

COMPONENTS = ("A", "B", "C")
TOLERANCES = REF["tolerances"]
TAU_FLOW = number(TOLERANCES["molar_flow"])
TAU_EQ = number(TOLERANCES["molar_flow_squared"])
TAU_E = number(TOLERANCES["heat_rate"])
GRID_T, GRID_V, GRID_Q = (number(TOLERANCES["grid"][key]) for key in ("T", "V", "q"))

#: Regression values (measured 2026-09-25 on this implementation; equal state for state to the
#: twin's 53-bit emulation `ref.kernel_grid.*.measured_53_bit.route`): the route of every grid
#: call. The temperature route is accepted at every `ε = 1e-6`, at `φ = 0.5` for `ε ≤ 1e-9`, and
#: at six of the ten `ε = 1e-7` states; the band route everywhere else.
B01_BRACKET = frozenset(
    {
        *(f"NPK-{t}-1.0e-6-{phi}" for t in "AC" for phi in ("0.1", "0.3", "0.5", "0.7", "0.9")),
        *(f"NPK-{t}-{eps}-0.5" for t in "AC" for eps in ("1.0e-12", "1.0e-9")),
        "NPK-A-1.0e-7-0.1",
        "NPK-A-1.0e-7-0.3",
        "NPK-A-1.0e-7-0.7",
        "NPK-C-1.0e-7-0.1",
        "NPK-C-1.0e-7-0.3",
        "NPK-C-1.0e-7-0.7",
        "NPK-C-1.0e-7-0.9",
    }
)


def rows(answer: PHState, n: tuple[float, ...], target: float) -> tuple[float, float, float]:
    """The closure's rows at the answer (T05b §5.3), from the provider, largest of each kind."""
    assert answer.temperature is not None and answer.split is not None
    assert answer.split.vapor is not None and answer.split.liquid is not None
    temperature, pressure = answer.temperature, answer.split.vapor.pressure
    vapor, liquid = answer.split.vapor.n, answer.split.liquid.n
    state = StreamState(n=n, temperature=temperature, pressure=pressure)
    ln_k = PROVIDER.evaluate_phase(
        PropertyRequest(state=state, phase="LIQUID", properties=("lnK",)), CONTEXT
    ).values
    h = {
        phase: PROVIDER.evaluate_phase(
            PropertyRequest(state=state, phase=phase, properties=("h",)), CONTEXT
        ).values
        for phase in ("VAPOR", "LIQUID")
    }
    total_v, total_l = sum(vapor), sum(liquid)
    material = max(abs(v + liq - flow) for v, liq, flow in zip(vapor, liquid, n, strict=True))
    equilibrium = max(
        abs(vapor[i] * total_l - math.exp(ln_k[f"lnK_{c}"]) * liquid[i] * total_v)
        for i, c in enumerate(COMPONENTS)
    )
    energy = abs(
        sum(vapor[i] * h["VAPOR"][f"h_{c}"] for i, c in enumerate(COMPONENTS))
        + sum(liquid[i] * h["LIQUID"][f"h_{c}"] for i, c in enumerate(COMPONENTS))
        - target
    )
    return material, equilibrium, energy


def grid_inputs(state: Mapping[str, Any]) -> tuple[tuple[float, ...], float, float]:
    inputs = state["inputs"]
    n = tuple(number(value) for value in inputs["n_mol_per_s"])
    return n, number(inputs["P_Pa"]), number(inputs["H_target_W"])


# ------------------------------------------------------------------------------------- B01


@pytest.mark.parametrize("state_id", list(REF["kernel_grid"]))
def test_b01_the_near_pure_grid(state_id: str) -> None:
    state = REF["kernel_grid"][state_id]
    n, pressure, target = grid_inputs(state)
    answer = ph_state(PROVIDER, n, pressure, target, CONTEXT)
    expected = state["expected"]
    assert answer.status == expected["status"] == "ok", answer.message
    assert answer.route in {"bracket", "band"}
    epsilon, phi = min(value for value in n if value > 0.0), state_id.rsplit("-", 1)[1]
    if epsilon <= 1e-9 and phi != "0.5":
        assert answer.route == "band"
    # Regression value: the route (self-generated; equal to the twin's emulation).
    assert answer.route == ("bracket" if state_id in B01_BRACKET else "band")
    assert answer.route == state["measured_53_bit"]["route"]

    material, equilibrium, energy = rows(answer, n, target)
    assert material <= TAU_FLOW and equilibrium <= TAU_EQ and energy <= TAU_E

    assert answer.temperature is not None and answer.split is not None
    assert answer.split.vapor is not None
    assert error(answer.temperature, expected["T_K"]) <= GRID_T
    assert error(sum(answer.split.vapor.n), expected["V_mol_per_s"]) <= GRID_V
    for index, q in enumerate(expected["vapour_fraction_by_component"]):
        if q is None:
            assert answer.split.vapor.n[index] == 0.0 and n[index] == 0.0
            continue
        assert error(answer.split.vapor.n[index] / n[index], q) <= GRID_Q, (index, q)
    assert answer.split.phase_signature == "TWO_PHASE"


def test_b01_the_band_routes_floor() -> None:
    """Spec §13's floors: on the band route the grid's worst `|T − T*|`, `|V − V*|` and
    `|q − q*|` are the emulation's (5.7e-14 K, 5.5e-16 mol/s, 7.5e-16), far inside §13's
    tolerances; the measured values are stated in the failure message."""
    worst = {"T": 0.0, "V": 0.0, "q": 0.0}
    for state_id, state in REF["kernel_grid"].items():
        if state_id in B01_BRACKET:
            continue
        n, pressure, target = grid_inputs(state)
        answer = ph_state(PROVIDER, n, pressure, target, CONTEXT)
        assert answer.route == "band" and answer.temperature is not None
        assert answer.split is not None and answer.split.vapor is not None
        assert 2 < answer.evaluations <= MAX_BAND_EVALUATIONS
        expected = state["expected"]
        worst["T"] = max(worst["T"], error(answer.temperature, expected["T_K"]))
        worst["V"] = max(worst["V"], error(sum(answer.split.vapor.n), expected["V_mol_per_s"]))
        for index, q in enumerate(expected["vapour_fraction_by_component"]):
            if q is not None:
                share = answer.split.vapor.n[index] / n[index]
                worst["q"] = max(worst["q"], error(share, q))
    assert worst["T"] <= 1e-12 and worst["V"] <= 1e-14 and worst["q"] <= 1e-14, worst


def test_the_band_constants_are_the_specifications() -> None:
    band = REF["tolerances"]["band_route"]
    assert band["beta_width_floor"] == "2^-60" and BETA_WIDTH_FLOOR == 2.0**-60
    assert band["max_beta_evaluations"] == MAX_BAND_EVALUATIONS == 64
    assert EQUILIBRIUM_TOLERANCE == pytest.approx(TAU_EQ, rel=1e-15)


# --------------------------------------------------------------------- the provider doubles


def test_b03_jump_ends_the_chain_in_its_typed_refusal() -> None:
    case = REF["kernel_doubles"]["JUMP"]
    n, pressure, target = grid_inputs(case)
    answer = ph_state(Jump(PROVIDER), n, pressure, target, CONTEXT)
    assert (answer.status, answer.code) == (case["expected"]["status"], case["expected"]["code"])
    assert first_line(answer.message) == "ph_ill_conditioned"
    assert answer.temperature is None and answer.split is None and answer.route is None
    # Both routes ran and both closed on the jump, |f| ≈ jump/2 = 680 W (spec §12.2): the
    # message names them and their row ratios.
    assert "bracket route at T = " in answer.message and "band route at T = " in answer.message
    assert "closest: the " in answer.message


def test_b03_the_double_is_what_the_spec_registers() -> None:
    """JUMP's jump at 360 K for (1, 1, 1) at P_r is `1 000 · V(360 K)`, the registered value."""
    state = StreamState(n=(1.0, 1.0, 1.0), temperature=360.0, pressure=1.0e5)
    flashed = PROVIDER.flash(FlashRequest(state=state), CONTEXT)
    assert flashed.vapor is not None
    jump = 1_000.0 * sum(flashed.vapor.n)
    assert error(jump, REF["kernel_doubles"]["JUMP"]["jump_W"]) <= 1e-9


def test_b04_biased_is_caught_by_the_equilibrium_rows_and_answered_by_the_band() -> None:
    """PHF-1's inputs through the BIASED flash: the temperature route meets the energy row at a
    temperature 2.2e-4 K off, its equilibrium rows fail (84 τ_eq, emulated), and the band route
    returns PHF-1's registered answer (T05 §14's tolerances)."""
    case = REF["kernel_doubles"]["BIASED"]
    expected = case["expected"]
    target = 50_000.0  # (1, 1, 1) liquid at 300 K and P_r carries zero enthalpy; Q = 50 000 W
    n = (1.0, 1.0, 1.0)
    biased = Biased(PROVIDER)
    answer = ph_state(biased, n, 1.0e5, target, CONTEXT)
    assert answer.status == expected["status"] == "ok", answer.message
    assert answer.route == expected["route"] == "band"
    assert answer.temperature is not None and answer.split is not None
    assert answer.split.vapor is not None and answer.split.liquid is not None
    assert error(answer.temperature, expected["T_K"]) <= 1e-6
    for got, registered in zip(answer.split.vapor.n, expected["vapor_mol_per_s"], strict=True):
        assert error(got, registered) <= TAU_FLOW
    for got, registered in zip(answer.split.liquid.n, expected["liquid_mol_per_s"], strict=True):
        assert error(got, registered) <= TAU_FLOW
    # Without the equilibrium clause the answer would have been the temperature route's: an
    # energy-only acceptance fails `T` by 2.2e-4 K (the spec's discriminating fact, measured).
    measured = case["measured_53_bit"]
    assert abs(float(measured["temperature_route_T_K"]) - number(expected["T_K"])) > 1e-4
    assert float(measured["temperature_route_max_equilibrium_row"]) > 10 * TAU_EQ


def test_b04_the_honest_flash_takes_the_temperature_route_on_the_same_inputs() -> None:
    answer = ph_state(PROVIDER, (1.0, 1.0, 1.0), 1.0e5, 50_000.0, CONTEXT)
    assert answer.status == "ok" and answer.route == "bracket"
    assert answer.temperature is not None
    assert error(answer.temperature, REF["kernel_doubles"]["BIASED"]["expected"]["T_K"]) <= 1e-12


# ------------------------------------------------------------- the chain's other endings


def test_one_flowing_component_never_takes_the_band_route() -> None:
    """§5.1 step 4 needs two flowing components: a single-component answer that failed §5.3
    would be `ph_ill_conditioned`, never a band answer. At PHF-6's saturation route it passes."""
    answer = ph_state(PROVIDER, (0.0, 2.0, 0.0), 1.0e5, 30_000.0, CONTEXT)
    assert answer.status == "ok" and answer.route == "saturation"
    material, equilibrium, energy = rows(answer, (0.0, 2.0, 0.0), 30_000.0)
    assert (material, equilibrium) == (0.0, 0.0) and energy <= TAU_E


def test_an_exhausted_band_budget_is_not_converged(monkeypatch: pytest.MonkeyPatch) -> None:
    """A budget exhausted in any route is `ph_not_converged` (§5.1 step 5)."""
    from openflowsheet.models.syn001 import ph_kernel  # noqa: PLC0415

    monkeypatch.setattr(ph_kernel, "MAX_BAND_EVALUATIONS", 10)
    n, pressure, target = grid_inputs(REF["kernel_grid"]["NPK-A-1.0e-12-0.3"])
    answer = ph_state(PROVIDER, n, pressure, target, CONTEXT)
    assert (answer.status, answer.code) == ("not_converged", "ph_not_converged")
    assert answer.temperature is None and answer.split is None
