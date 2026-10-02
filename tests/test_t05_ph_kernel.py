"""T05 W2: the PH kernel's routes and typed failures (T05 spec §4.4), and its `T` floor (W0.4).

Unit-level expectations are the registered cases' (`benchmarks/t05/reference_values.yaml`); the
kernel is called here directly with the target the unit would give it, `Hdot_in + Q`, where
`Hdot_in` is the declared-phase enthalpy of the registered inlet.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from typing import Any

import pytest
from t05_support import (
    BETA_TOLERANCE,
    CONTEXT,
    ENERGY_TOLERANCE,
    PROVIDER,
    REF,
    TEMPERATURE_TOLERANCE,
    error,
    first_line,
    stream,
)

from openflowsheet.models.syn001 import COMPONENTS
from openflowsheet.models.syn001.ph_kernel import (
    MAX_EVALUATIONS,
    bracketed_root,
    ph_state,
)
from openflowsheet.models.syn001.tp_state import enthalpy_flow
from openflowsheet.thermo import Phase, StreamState


def enthalpy(state: StreamState, phase: Phase) -> float:
    status, value, message = enthalpy_flow(PROVIDER, state, phase, COMPONENTS, CONTEXT)
    assert status == "ok", message
    return value


def phf_target(inputs: Mapping[str, Any]) -> tuple[StreamState, float, float]:
    """`(inlet, P_out, H*)` for a registered PH-flash case with a declared inlet phase."""
    feed = stream(inputs["inlet"])
    target = enthalpy(feed, inputs["inlet_phase"]) + float(inputs["duty"])
    return feed, feed.pressure - float(inputs["pressure_drop"]), target


# ------------------------------------------------------------------------------ the routes


def test_a_single_flowing_component_takes_the_saturation_route() -> None:
    """PHF-6: `T = T_sat(P)` and the lever rule, which no bisection on `T` can return (§4.2)."""
    case = REF["unit_cases"]["PHF-6"]
    feed, pressure, target = phf_target(case["inputs"])
    answer = ph_state(PROVIDER, feed.n, pressure, target, CONTEXT)
    assert answer.status == "ok" and answer.code == ""
    assert answer.route == "saturation" == case["expected"]["route"]
    assert answer.evaluations == 0  # the route evaluates no f
    assert answer.temperature is not None and answer.split is not None
    assert error(answer.temperature, case["expected"]["T_K"]) <= TEMPERATURE_TOLERANCE
    assert answer.split.vapor_fraction is not None
    assert error(answer.split.vapor_fraction, case["expected"]["beta"]) <= BETA_TOLERANCE
    assert answer.split.phase_signature == "TWO_PHASE"
    assert answer.residual is not None and abs(answer.residual) <= ENERGY_TOLERANCE
    flowing = feed.n.index(max(feed.n))
    for outlet in (answer.split.vapor, answer.split.liquid):
        assert outlet is not None
        assert all(v == 0.0 for i, v in enumerate(outlet.n) if i != flowing)


@pytest.mark.parametrize(("side", "phase"), [("below", "LIQUID"), ("above", "VAPOR")])
def test_a_single_component_target_outside_the_jump_brackets_on_its_half(
    side: str, phase: str
) -> None:
    """Step 2's restriction: below `H_L(T_sat)` the answer is liquid, above `H_V` vapour."""
    feed, pressure, _ = phf_target(REF["unit_cases"]["PHF-6"]["inputs"])
    at_saturation = StreamState(n=feed.n, temperature=360.0, pressure=pressure)
    h_liquid, h_vapor = enthalpy(at_saturation, "LIQUID"), enthalpy(at_saturation, "VAPOR")
    # 5 K of sensible heat either side of the jump; n c_p from the provider's own enthalpy.
    slope = enthalpy(StreamState(feed.n, 361.0, pressure), "LIQUID") - h_liquid
    target = h_liquid - 5.0 * slope if side == "below" else h_vapor + 5.0 * slope
    answer = ph_state(PROVIDER, feed.n, pressure, target, CONTEXT)
    assert answer.status == "ok", answer.message
    assert answer.route == "bracket"
    assert answer.split is not None and answer.split.phase_signature == phase
    assert answer.temperature is not None
    expected = 355.0 if side == "below" else 365.0
    assert abs(answer.temperature - expected) <= TEMPERATURE_TOLERANCE


def test_the_bracket_route_closes_to_adjacent_doubles_within_the_budget() -> None:
    feed, pressure, target = phf_target(REF["unit_cases"]["PHF-1"]["inputs"])
    answer = ph_state(PROVIDER, feed.n, pressure, target, CONTEXT)
    assert answer.status == "ok" and answer.route == "bracket"
    assert answer.evaluations < MAX_EVALUATIONS
    assert answer.residual is not None and abs(answer.residual) <= ENERGY_TOLERANCE


# ------------------------------------------------------------------------ typed failures


@pytest.mark.parametrize("case_id", ["PHF-F1", "PHF-F2"])
def test_a_target_outside_the_domain_bracket_is_out_of_domain(case_id: str) -> None:
    case = REF["unit_cases"][case_id]
    feed, pressure, target = phf_target(case["inputs"])
    answer = ph_state(PROVIDER, feed.n, pressure, target, CONTEXT)
    assert answer.status == case["expected"]["status"]
    assert answer.code == case["expected"]["code"] == first_line(answer.message)
    assert answer.temperature is None and answer.split is None
    assert answer.evaluations == 2


def test_an_outlet_pressure_off_the_domain_is_refused_before_any_evaluation() -> None:
    feed, _, target = phf_target(REF["unit_cases"]["PHF-1"]["inputs"])
    p_min, _ = PROVIDER.describe().domain["P"]
    answer = ph_state(PROVIDER, feed.n, p_min - 1.0, target, CONTEXT)
    assert (answer.status, answer.code) == ("out_of_domain", "pressure_outside_domain(outlet)")
    assert first_line(answer.message) == answer.code
    assert answer.evaluations == 0


# ----------------------------------------------- A29: the near-pure class (§4.4, ruling Q-R1)
#
# Retired by ADR 0012 (T05b spec §16): A29's pattern (`ok` only mid-jump, `ph_ill_conditioned`
# elsewhere) became `ok` everywhere when the kernel gained T05b §5.3's closure-rows acceptance and
# its band route. Its replacement is B01, `tests/test_t05b_kernel.py`, on the 40-state grid of
# T05b §12.1. What stays here is A29's closed forms, which B01's targets still use;
# `scripts/t05_evidence_manifest.py` records A29 retired (T05b W8).

#: A29's closed forms: pure B at `P_r` saturates at 360 K (PHF-6); `H_L = 2 c_p · 60 K` and the
#: latent jump `2 L_B`, W.
A29_T_SAT, A29_H_LIQUID, A29_JUMP = 360.0, 12_000.0, 60_000.0


def a29_flows(trace: str, epsilon: float) -> tuple[float, float, float]:
    return (epsilon, 2.0, 0.0) if trace == "A" else (0.0, 2.0, epsilon)


def refused_residual(message: str) -> float:
    """T05's step 5 `|f|` at the closest double, from a pre-T05b refusal's free-text line."""
    found = re.search(r"\|f\| = (\S+) W", message)
    assert found is not None, message
    return float(found.group(1))


def test_a29_the_closed_forms_are_the_providers() -> None:
    at_saturation = StreamState(n=(0.0, 2.0, 0.0), temperature=A29_T_SAT, pressure=1e5)
    h_liquid, h_vapor = enthalpy(at_saturation, "LIQUID"), enthalpy(at_saturation, "VAPOR")
    assert abs(h_liquid - A29_H_LIQUID) <= ENERGY_TOLERANCE
    assert abs(h_vapor - h_liquid - A29_JUMP) <= ENERGY_TOLERANCE


def test_an_exhausted_budget_is_not_converged() -> None:
    feed, pressure, target = phf_target(REF["unit_cases"]["PHF-1"]["inputs"])
    answer = ph_state(PROVIDER, feed.n, pressure, target, CONTEXT, max_evaluations=10)
    assert (answer.status, answer.code) == ("not_converged", "ph_not_converged")
    assert answer.evaluations == 10
    assert answer.temperature is None and answer.split is None


@pytest.mark.parametrize("budget", [1, 2, 3, 5])
def test_phf6s_t_sat_bisection_budget_pattern(budget: int) -> None:
    """Spec §4.4 step 2 as amended (ruling round Q-R1, review N2; acceptance replaced by the
    narrow review, `docs/briefs/T05-rulings.md` §4): PHF-6's T_sat = 360 K is the midpoint of the
    domain [280, 440] K and ln K_B(360 K, P_r) == 0.0 exactly, so its bisection closes in 3
    ln K evaluations (the two ends included). Measured pattern, pinned: budgets 1 and 2 are
    `ph_not_converged`; 3 and 5 are `ok` at exactly 360 K. The budget itself is exercised where
    the bisection does not close early, in the next test."""
    feed, pressure, target = phf_target(REF["unit_cases"]["PHF-6"]["inputs"])
    answer = ph_state(PROVIDER, feed.n, pressure, target, CONTEXT, max_evaluations=budget)
    if budget <= 2:
        assert (answer.status, answer.code) == ("not_converged", "ph_not_converged")
        assert first_line(answer.message) == "ph_not_converged"
        assert answer.temperature is None and answer.split is None
    else:
        assert answer.status == "ok"
        assert answer.temperature == 360.0


def test_an_exhausted_t_sat_bisection_is_not_converged() -> None:
    """The same budget where the bisection does not hit `T_sat` on a midpoint: pure B at
    `1.5e5 Pa`, a target 30% into its jump. The bisection needs 53 `ln K` evaluations (the two
    ends included; measured); with 5 it is `ph_not_converged`, and it spends no evaluation of `f`
    (step 2's budget is counted separately from step 4's)."""
    flows, pressure = (0.0, 2.0, 0.0), 1.5e5
    t_sat = 375.1151693190263  # the 200-budget bisection's root at 1.5e5 Pa (measured)
    at_saturation = StreamState(n=flows, temperature=t_sat, pressure=pressure)
    h_liquid, h_vapor = enthalpy(at_saturation, "LIQUID"), enthalpy(at_saturation, "VAPOR")
    target = h_liquid + 0.3 * (h_vapor - h_liquid)
    solved = ph_state(PROVIDER, flows, pressure, target, CONTEXT)
    assert solved.status == "ok" and solved.route == "saturation"
    assert solved.temperature == t_sat
    assert ph_state(PROVIDER, flows, pressure, target, CONTEXT, max_evaluations=53).status == "ok"
    for budget in (5, 52):
        answer = ph_state(PROVIDER, flows, pressure, target, CONTEXT, max_evaluations=budget)
        assert (answer.status, answer.code) == ("not_converged", "ph_not_converged")
        assert first_line(answer.message) == "ph_not_converged"
        assert answer.temperature is None and answer.split is None
        assert answer.evaluations == 0


def test_a_dormant_stream_is_the_callers() -> None:
    with pytest.raises(ValueError, match="dormant"):
        ph_state(PROVIDER, (0.0, 0.0, 0.0), 1e5, 0.0, CONTEXT)


# ---------------------------------------------------------------------- the bisection helper


def test_bracketed_root_stops_at_adjacent_doubles() -> None:
    def f(x: float) -> tuple[float, None]:
        return x * x - 2.0, None

    root = bracketed_root(f, (1.0, -1.0, None), (2.0, 2.0, None), evaluations=0, budget=200)
    assert root.converged
    assert abs(root.point - math.sqrt(2.0)) <= math.ulp(math.sqrt(2.0))


def test_bracketed_root_reports_an_exhausted_budget() -> None:
    def f(x: float) -> tuple[float, None]:
        return x - math.pi, None

    root = bracketed_root(
        f, (0.0, -math.pi, None), (4.0, 4.0 - math.pi, None), evaluations=0, budget=5
    )
    assert not root.converged and root.evaluations == 5


# ------------------------------------------------------------------------- W0.4: the T floor

#: The PH-type cases this kernel serves (spec §4.4's eight): the PH flash's two-phase cases, the
#: valve's, and the duty-mode reactor's.
PH_TYPE = ["PHF-1", "PHF-2", "PHF-5", "PHF-7", "VLV-2", "VLV-5", "RX-5", "RX-3"]


def kernel_target(case_id: str) -> tuple[tuple[float, ...], float, float]:
    inputs = REF["unit_cases"][case_id]["inputs"]
    if case_id.startswith("PHF"):
        feed, pressure, target = phf_target(inputs)
        return feed.n, pressure, target
    if case_id.startswith("RX"):
        # A duty-mode reactor's closure: the registered reacted flows, the inlet pressure less
        # the drop, and the declared-phase inlet enthalpy plus Q_spec (spec §6.3 (5)).
        feed = stream(inputs["inlet"])
        registered = REF["unit_cases"][case_id]["expected"]["outlet"]["n_mol_per_s"]
        reacted = tuple(float(value) for value in registered)
        target = enthalpy(feed, inputs["inlet_phase"]) + float(inputs["value"])
        return reacted, feed.pressure - float(inputs["pressure_drop"]), target
    feed = stream(inputs["inlet"])
    phase = inputs["inlet_phase"]
    if phase is None:
        from openflowsheet.models.syn001.tp_state import tp_state  # noqa: PLC0415

        state = tp_state(PROVIDER, feed, CONTEXT)
        assert state.enthalpy_flow is not None
        return feed.n, float(inputs["outlet_pressure"]), state.enthalpy_flow
    return feed.n, float(inputs["outlet_pressure"]), enthalpy(feed, phase)


@pytest.mark.parametrize("case_id", PH_TYPE)
def test_the_kernel_temperature_floor(case_id: str) -> None:
    """W0.4: `|T* - T_ref|` against the 40-digit root, far below the registered `1e-6 K`.

    The registered 53-bit floor of the twin's kernel is `ref.measured.floors_53_bit.ph_kernel_T_K`
    (`<= 9.8e-14 K`); the implementation's is reported in the assertion message.
    """
    n, pressure, target = kernel_target(case_id)
    answer = ph_state(PROVIDER, n, pressure, target, CONTEXT)
    assert answer.status == "ok" and answer.temperature is not None
    expected = REF["unit_cases"][case_id]["expected"]
    registered = expected["T_K"] if "T_K" in expected else expected["outlet"]["T_K"]
    floor = error(answer.temperature, registered)
    twin = REF["measured"]["floors_53_bit"]["ph_kernel_T_K"][case_id]
    assert floor <= TEMPERATURE_TOLERANCE, f"{case_id}: |T* - T_ref| = {floor:.3g} K (twin {twin})"
    # The floor this implementation reaches is a few ulps of T; hold it to 1e-12 K so a
    # regression by orders of magnitude shows here long before it reaches the tolerance.
    assert floor <= 1e-12, f"{case_id}: |T* - T_ref| = {floor:.3g} K (twin {twin})"
