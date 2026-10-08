"""M01.A15-A24: the TP flash of `pr-c1-v1` and the reaction-consistent registry (spec §5.4, §6).

Expectations: `benchmarks/m01/reference_values.yaml` → `closed_form.flash_states` and `reaction`,
the generator's 50-digit solution of the same scalar equation (spec §5.4); the flash under test
finds its root by the same fixed samples and bisection in double.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

import pytest
from conftest import REPO_ROOT, load_yaml

from openflowsheet.compiled import EvaluationContext
from openflowsheet.models.syn001 import conversion_reactor
from openflowsheet.thermo import FlashRequest, FlashResult, PropertyRequest, StreamState
from openflowsheet.thermo.conventions import (
    REACTION_CONSISTENT_CONVENTIONS,
    is_reaction_consistent,
    reference_convention_not_reaction_consistent,
)
from openflowsheet.thermo.pr_c1 import SAMPLES, PrC1Provider, h_ig

CLOSED = load_yaml(REPO_ROOT / "benchmarks" / "m01" / "reference_values.yaml")["closed_form"]
FLASH: Mapping[str, Any] = CLOSED["flash_states"]
TWO_PHASE = [fid for fid, state in FLASH.items() if state["phase_signature"] == "TWO_PHASE"]
CONTEXT = EvaluationContext(model_version="m01-flash", constants_sha256="0" * 64)
PROVIDER = PrC1Provider()


def _flash(n: tuple[float, ...], temperature: float, pressure: float) -> FlashResult:
    state = StreamState(n=n, temperature=temperature, pressure=pressure)
    return PROVIDER.flash(FlashRequest(state=state), CONTEXT)


def _registered(fid: str) -> FlashResult:
    state = FLASH[fid]
    return _flash(tuple(state["n_mol_s"]), state["T_K"], state["P_Pa"])


def test_the_sample_sequence_is_spec_5_4s() -> None:
    assert len(SAMPLES) == 63 + 34
    assert SAMPLES[:3] == (1 / 64, 2 / 64, 3 / 64) and SAMPLES[62] == 63 / 64
    assert SAMPLES[63] == 1 - 2**-7 and SAMPLES[-1] == 1 - 2**-40
    assert list(SAMPLES) == sorted(set(SAMPLES))


def test_registered_two_phase_states_are_f1_f5_f11_f13() -> None:
    assert TWO_PHASE == ["F1", "F5", "F11", "F13"]


@pytest.mark.parametrize("fid", TWO_PHASE)
def test_a15_two_phase_split(fid: str) -> None:
    expected = FLASH[fid]
    result = _registered(fid)
    assert result.status == "ok", result.message
    assert result.phase_signature == "TWO_PHASE"
    assert list(result.k_values) == ["NH3"]
    y_star = result.k_values["NH3"]
    assert abs(y_star / expected["y_star"] - 1.0) <= 1e-11
    assert result.vapor_fraction is not None
    assert abs(result.vapor_fraction - expected["vapor_fraction"]) <= 1e-12
    assert result.vapor is not None and result.liquid is not None
    assert abs(result.vapor.n[2] / expected["v_nh3"] - 1.0) <= 1e-11
    assert abs(result.liquid.n[2] / expected["l_nh3"] - 1.0) <= 1e-11
    feed = expected["n_mol_s"]
    for k in (0, 1, 3, 4):
        assert math.copysign(1.0, result.liquid.n[k]) == 1.0 and result.liquid.n[k] == 0.0
        assert result.vapor.n[k].hex() == float(feed[k]).hex()
    # iterations = samples + halvings; the bracket index counts the negative samples.
    assert result.iterations > expected["bracket_sample_index"] + 1


@pytest.mark.parametrize("fid", TWO_PHASE)
def test_a16_the_equilibrium_row_closes_on_the_providers_own_evaluations(fid: str) -> None:
    result = _registered(fid)
    assert result.vapor is not None and result.liquid is not None
    vapour = PROVIDER.evaluate_phase(
        PropertyRequest(state=result.vapor, phase="VAPOR", properties=("lnphi_NH3",)), CONTEXT
    )
    liquid = PROVIDER.evaluate_phase(
        PropertyRequest(state=result.liquid, phase="LIQUID", properties=("lnphi_NH3",)), CONTEXT
    )
    assert vapour.status == liquid.status == "ok"
    residual = (
        math.log(result.k_values["NH3"]) + vapour.values["lnphi_NH3"] - liquid.values["lnphi_NH3"]
    )
    assert abs(residual) <= 1e-12


@pytest.mark.parametrize(
    ("fid", "phase"),
    [
        ("F2", "VAPOR"),
        ("F3", "VAPOR"),
        ("F6", "VAPOR"),
        ("F8", "VAPOR"),
        ("F9", "VAPOR"),
        ("F10", "VAPOR"),
        ("F7", "LIQUID"),
    ],
)
def test_a17_single_phase_routes(fid: str, phase: str) -> None:
    expected = FLASH[fid]
    assert expected["phase_signature"] == phase
    result = _registered(fid)
    assert result.status == "ok", result.message
    assert result.phase_signature == phase
    assert result.message == f"route: {expected['route']}"
    assert result.vapor_fraction == (1.0 if phase == "VAPOR" else 0.0)
    present, absent = (
        (result.vapor, result.liquid) if phase == "VAPOR" else (result.liquid, result.vapor)
    )
    assert present is not None and absent is not None
    assert [value.hex() for value in present.n] == [float(v).hex() for v in expected["n_mol_s"]]
    assert all(value == 0.0 and math.copysign(1.0, value) == 1.0 for value in absent.n)
    assert (absent.temperature, absent.pressure) == (expected["T_K"], expected["P_Pa"])
    assert dict(result.k_values) == {}


def test_a18_the_dew_point_is_vapour_or_an_ulp_liquid() -> None:
    feed = FLASH["F4"]["n_mol_s"]
    result = _registered("F4")
    assert result.status == "ok", result.message
    if result.phase_signature == "TWO_PHASE":
        assert result.liquid is not None
        assert result.liquid.n[2] <= 1e-12 * feed[2]
    else:
        assert result.phase_signature == "VAPOR"


def test_a19_the_near_critical_state_is_vapour() -> None:
    result = _registered("F12")
    assert result.status == "ok" and result.phase_signature == "VAPOR"
    assert result.message == "route: no_liquid"


def test_a20_a_dormant_feed_is_zero_flow() -> None:
    result = _registered("F14")
    assert result.status == "ok"
    assert result.phase_signature == "ZERO_FLOW"
    assert result.vapor_fraction is None
    for outlet in (result.vapor, result.liquid):
        assert outlet is not None
        assert all(value == 0.0 and math.copysign(1.0, value) == 1.0 for value in outlet.n)
        assert (outlet.temperature, outlet.pressure) == (300.0, 1e7)
    assert dict(result.k_values) == {}


def test_a21_y_star_does_not_depend_on_the_feeds_nh3() -> None:
    feed = list(FLASH["F1"]["n_mol_s"])
    doubled = (feed[0], feed[1], 2.0 * feed[2], feed[3], feed[4])
    base, more = _registered("F1"), _flash(doubled, 268.15, 1e7)
    assert more.phase_signature == "TWO_PHASE"
    assert more.k_values["NH3"].hex() == base.k_values["NH3"].hex()


@pytest.mark.parametrize("fid", TWO_PHASE)
def test_a22_vapour_plus_liquid_is_the_feed_within_one_ulp(fid: str) -> None:
    feed = FLASH[fid]["n_mol_s"]
    result = _registered(fid)
    assert result.vapor is not None and result.liquid is not None
    for k in range(5):
        total = result.vapor.n[k] + result.liquid.n[k]
        assert abs(total - feed[k]) <= math.ulp(feed[k]), k


def test_refused_flash_requests_carry_no_split() -> None:
    feed = tuple(FLASH["F1"]["n_mol_s"])
    state = StreamState(n=feed, temperature=268.15, pressure=1e7)
    for result, status, code in (
        (_flash(feed, 150.0, 1e7), "out_of_domain", "out_of_domain:"),
        (_flash(feed, 268.15, 5e7), "out_of_domain", "out_of_domain:"),
        (
            PROVIDER.flash(FlashRequest(state=state, specification="PH"), CONTEXT),
            "unsupported",
            "unsupported_specification:",
        ),
    ):
        assert result.status == status
        assert result.message.startswith(code)
        assert result.phase_signature is None and result.vapor_fraction is None
        assert result.vapor is None and result.liquid is None


# -- A23, A24: the datum and the registry ----------------------------------------------------------


def test_a23_the_ideal_gas_reaction_enthalpy_is_a_formation_datum() -> None:
    reaction = CLOSED["reaction"]
    nu = reaction["nu"]
    assert nu == [-3, -1, 2, 0, 0]
    at_ref = sum(nu[i] * h_ig(298.15, i) for i in range(5))
    assert abs(at_ref - reaction["dh_r_ig_298_15_J_mol"]) <= 1e-9
    assert reaction["dh_r_ig_298_15_J_mol"] == -91116.0
    hot = sum(nu[i] * h_ig(673.15, i) for i in range(5))
    expected = reaction["dh_r_ig_673_15_J_mol"]
    assert abs(hot - expected) / max(abs(expected), 1.0) <= 1e-12


def test_a24_the_registry_is_adr_0026s_set_and_syn001s_constant_is_unchanged_and_a_subset() -> None:
    assert frozenset({"SYN-001-ref-v1", "PR-C1-ref-v1"}) == REACTION_CONSISTENT_CONVENTIONS
    assert conversion_reactor.REACTION_CONSISTENT_CONVENTIONS == frozenset({"SYN-001-ref-v1"})
    assert conversion_reactor.REACTION_CONSISTENT_CONVENTIONS < REACTION_CONSISTENT_CONVENTIONS
    assert is_reaction_consistent(PROVIDER.describe().reference_convention)
    assert not is_reaction_consistent("PR-C1-shifted")
    assert reference_convention_not_reaction_consistent("X") == (
        conversion_reactor.reference_convention_not_reaction_consistent("X")
    )
