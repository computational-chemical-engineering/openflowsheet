"""S05.A01-A21, A23-A24: the `iapws95-v1` provider against `s05_reference.json` (WO-S05-1).

Every expectation is a key of `docs/derivations/scripts/s05_reference.json`, the 50-digit
evaluation of spec §2's closed form; the tolerances are spec §6.1's, with §6.2's NC widening.
Refusal probes and their answered controls are spec §5.5's. Neither generator is imported here.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

import pytest

from openflowsheet.compiled import EvaluationContext
from openflowsheet.thermo import (
    FlashRequest,
    FlashResult,
    Phase,
    PropertyRequest,
    PropertyResult,
    StreamState,
)
from openflowsheet.thermo import iapws95 as w

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "docs" / "derivations" / "scripts"
REF: dict[str, Any] = json.loads((SCRIPTS / "s05_reference.json").read_text("utf-8"))
REGISTERED_SHA256 = "b9e93877e37874f1b3a483e298a45692e264d70686d4c158372084b96abbe6ed"
CONTEXT = EvaluationContext(model_version="s05-provider", constants_sha256="0" * 64)
PROVIDER = w.Iapws95Provider()
SIX = w.PHASE_PROPERTIES
TP_STATES: dict[str, dict[str, str]] = REF["tp_states"]
NC = {"NC_vapour", "NC_liquid"}
SATURATION: dict[str, dict[str, str]] = REF["saturation"]
BAND: dict[str, dict[str, Any]] = REF["band"]["probes"]
BAND_T = float(REF["band"]["T"])


def ev(
    t: float,
    p: float,
    phase: Phase,
    properties: tuple[str, ...] = SIX,
    derivatives: tuple[str, ...] = ("T", "P", "n_H2O"),
    n: tuple[float, ...] = (1.0,),
) -> PropertyResult:
    state = StreamState(n=n, temperature=t, pressure=p)
    return PROVIDER.evaluate_phase(PropertyRequest(state, phase, properties, derivatives), CONTEXT)


def flash(
    t: float, p: float, spec: str = "TP", n: tuple[float, ...] = (1.0,), der: tuple[str, ...] = ()
) -> FlashResult:
    state = StreamState(n=n, temperature=t, pressure=p)
    return PROVIDER.flash(FlashRequest(state, spec, der), CONTEXT)


def tp(name: str) -> tuple[float, float, Phase]:
    state = TP_STATES[name]
    phase: Phase = "LIQUID" if state["phase"] == "LIQUID" else "VAPOR"
    return float(state["T"]), float(state["P"]), phase


def refused(result: PropertyResult | FlashResult, status: str, code: str) -> None:
    assert (result.status, result.message.split(":")[0]) == (status, code), result.message
    assert result.message.startswith(code + ":")
    assert result.phase_signature is None
    if isinstance(result, PropertyResult):
        assert result.values == {} and result.derivatives == {}


def value_bound(name: str, x: str, t: float, expected: float) -> float:
    """Spec §6.1 A05's bound on |Δx| for state `name`, NC ×100."""
    scale = 100.0 if name in NC else 1.0
    absolute = {"h": 1e-8 * w.R * t, "s": 1e-8 * w.R, "lnphi_H2O": 1e-8}
    if x in absolute:
        return scale * absolute[x]
    relative = 1e-9 if x == "v" else 1e-8
    return scale * relative * abs(expected)


# -- A01, A02, A24: identity -----------------------------------------------------------------------


def test_a01_coefficient_file_is_the_generators_and_constants_are_bitwise() -> None:
    provider_copy = (ROOT / w.COEFFICIENTS_PATH).read_bytes()
    assert provider_copy == (SCRIPTS / "s05_iapws95_coefficients.json").read_bytes()
    assert hashlib.sha256(provider_copy).hexdigest() == REGISTERED_SHA256 == w.COEFFICIENTS_SHA256
    assert (w.R_S, w.M, w.T_C, w.RHO_C, w.P_C, w.T_T) == (
        461.51805,
        0.018015268,
        647.096,
        322.0,
        22064000.0,
        273.16,
    )
    assert w.R == w.R_S * w.M and round(w.R, 12) == 8.314371357587
    assert w.R != 8.31446261815324  # not CODATA's (R-587)
    # Control: one changed byte is refused.
    with pytest.raises(ValueError, match="SHA-256"):
        w.parse_coefficients(provider_copy.replace(b"461.51805", b"461.51806"))


def test_a02_describe() -> None:
    caps = PROVIDER.describe()
    assert caps.provider_id == "iapws95-v1"
    assert caps.reference_convention == "IAPWS95-ref-v1"
    assert caps.state_definition == "nTP-v1"
    assert caps.components == ("H2O",)
    assert caps.phases == ("LIQUID", "VAPOR")
    assert caps.properties == ("h", "s", "v", "Z", "cp", "lnphi_H2O", "Psat", "Tsat")
    assert caps.flashes == ("TP",)
    assert dict(caps.derivative_order) == {"T": 1, "P": 1, "n_H2O": 1}
    assert dict(caps.domain) == {"T": (273.16, 1273.15), "P": (1.0e2, 1.0e8)}
    limitations = " ".join(caps.numerical_limitations)
    assert "near_critical" in limitations and "eps_sigma = 1e-6" in limitations
    assert caps.thread_safety == "thread_safe"


def test_a24_identities_are_the_files_hashes() -> None:
    caps = PROVIDER.describe()
    source = (ROOT / "src" / "openflowsheet" / "thermo" / "iapws95.py").read_bytes()
    assert caps.implementation_sha256 == hashlib.sha256(source).hexdigest()
    assert caps.data_sha256 == REGISTERED_SHA256


# -- A03, A04: the φ jet ---------------------------------------------------------------------------

LOW_ORDER = ("", "_d", "_dd", "_t", "_tt", "_dt")
FIELD = {"": "phi", "_d": "d", "_dd": "dd", "_t": "t", "_tt": "tt", "_dt": "dt"}


def jet(name: str) -> tuple[w.PhiJet, w.PhiJet]:
    state = REF["phi_states"][name]
    return w.phi_jet(w.T_C / float(state["T"]), float(state["rho"]) / w.RHO_C)


@pytest.mark.parametrize("name", ["R6_500", "R6_647", "delta_one"])
def test_a03_phi_jet_orders_up_to_two(name: str) -> None:
    ideal, residual = jet(name)
    state = REF["phi_states"][name]
    for suffix in LOW_ORDER:
        for part, got in (("phi0", ideal), ("phir", residual)):
            expected = float(state[part + suffix])
            value = getattr(got, FIELD[suffix])
            assert abs(value - expected) <= 1e-12 * max(abs(expected), 1.0), part + suffix


def test_a03_delta_one_is_exact_and_takes_the_zero_jet() -> None:
    assert float(REF["phi_states"]["delta_one"]["rho"]) / w.RHO_C == 1.0
    assert w._abs_power(0.0, 10.0 / 3.0) == (0.0, 0.0, 0.0, 0.0)
    # Control: off δ = 1 the factor is not zero.
    assert w._abs_power(1e-3, 10.0 / 3.0)[0] > 0.0


@pytest.mark.parametrize("name", ["R6_500", "R6_647"])
def test_a04_third_partials_of_phir(name: str) -> None:
    _, residual = jet(name)
    state = REF["phi_states"][name]
    for key in ("ddd", "ddt", "dtt", "ttt"):
        expected = float(state[f"phir_{key}"])
        assert abs(getattr(residual, key) - expected) <= 1e-11 * max(abs(expected), 1.0), key


@pytest.mark.parametrize("name", ["R6_500", "R6_647", "delta_one"])
def test_a03_supplement_properties_at_t_rho(name: str) -> None:
    """Not a numbered assertion: §3.1's closed forms at the φ states, A05's bounds."""
    state = REF["phi_states"][name]
    t = float(state["T"])
    answer, pressure = w._at(t, float(state["rho"]))
    assert abs(pressure / float(state["p"]) - 1.0) <= 1e-12
    for x in ("h", "s", "cp", "lnphi_H2O"):
        expected = float(state[x])
        assert abs(answer[x][0] - expected) <= value_bound(name, x, t, expected), x


# -- A05-A07: single-phase states ------------------------------------------------------------------


@pytest.mark.parametrize("name", list(TP_STATES))
def test_a05_values(name: str) -> None:
    t, p, phase = tp(name)
    result = ev(t, p, phase)
    assert result.status == "ok" and result.phase_signature == phase, result.message
    for x in SIX:
        expected = float(TP_STATES[name][x])
        assert abs(result.values[x] - expected) <= value_bound(name, x, t, expected), x


@pytest.mark.parametrize("name", list(TP_STATES))
def test_a06_t_and_p_derivatives(name: str) -> None:
    t, p, phase = tp(name)
    result = ev(t, p, phase)
    bound = (100.0 if name in NC else 1.0) * 1e-8
    for x in SIX:
        for wrt in ("T", "P"):
            expected = float(TP_STATES[name][f"d{x}_d{wrt}"])
            got = result.derivatives[x][wrt]
            assert abs(got - expected) <= bound * abs(expected), f"d{x}/d{wrt}"


@pytest.mark.parametrize("name", list(TP_STATES))
def test_a07_n_derivatives_are_exactly_zero(name: str) -> None:
    t, p, phase = tp(name)
    result = ev(t, p, phase)
    for x in SIX:
        assert "n_H2O" in result.derivatives[x]
        assert result.derivatives[x]["n_H2O"] == 0.0
        assert result.derivatives[x]["T"] != 0.0  # control: the mapping is not all zeros


# -- A08-A12: saturation ---------------------------------------------------------------------------


def psat(t: float) -> PropertyResult:
    return ev(t, 1.0e5, "LIQUID", ("Psat",), ("T", "P", "n_H2O"))


@pytest.mark.parametrize("key", list(SATURATION))
def test_a08_psat_and_its_slope(key: str) -> None:
    entry = SATURATION[key]
    result = psat(float(entry["T"]))
    assert result.status == "ok", result.message
    expected, slope = float(entry["Psat"]), float(entry["dPsat_dT"])
    assert abs(result.values["Psat"] / expected - 1.0) <= 2e-9
    assert abs(result.derivatives["Psat"]["T"] / slope - 1.0) <= 1e-8
    assert result.derivatives["Psat"]["P"] == 0.0
    assert result.derivatives["Psat"]["n_H2O"] == 0.0


@pytest.mark.parametrize("key", list(REF["tsat"]))
def test_a09_tsat_and_its_slope(key: str) -> None:
    entry = REF["tsat"][key]
    result = ev(300.0, float(entry["P"]), "VAPOR", ("Tsat",), ("T", "P", "n_H2O"))
    assert result.status == "ok", result.message
    assert abs(result.values["Tsat"] / float(entry["Tsat"]) - 1.0) <= 1e-9
    assert abs(result.derivatives["Tsat"]["P"] / float(entry["dTsat_dP"]) - 1.0) <= 1e-8
    assert result.derivatives["Tsat"]["T"] == 0.0
    assert result.derivatives["Tsat"]["n_H2O"] == 0.0


def both_phases_at_psat(t: float) -> tuple[PropertyResult, PropertyResult, PropertyResult]:
    sat = psat(t)
    p = sat.values["Psat"]
    return sat, ev(t, p, "LIQUID"), ev(t, p, "VAPOR")


@pytest.mark.parametrize("key", list(SATURATION))
def test_a10_maxwell_on_the_providers_own_psat(key: str) -> None:
    entry = SATURATION[key]
    _, liquid, vapour = both_phases_at_psat(float(entry["T"]))
    assert liquid.status == vapour.status == "ok", (liquid.message, vapour.message)
    assert abs(liquid.values["lnphi_H2O"] - vapour.values["lnphi_H2O"]) <= 1e-8
    latent = float(entry["h_v"]) - float(entry["h_l"])
    bound = 1e-6 if key == "647" else 1e-9
    assert abs((vapour.values["h"] - liquid.values["h"]) / latent - 1.0) <= bound


@pytest.mark.parametrize("key", list(SATURATION))
def test_a11_clausius_clapeyron_on_the_providers_answers(key: str) -> None:
    sat, liquid, vapour = both_phases_at_psat(float(SATURATION[key]["T"]))
    ratio = (vapour.values["s"] - liquid.values["s"]) / (vapour.values["v"] - liquid.values["v"])
    bound = 1e-6 if key == "647" else 1e-8
    assert abs(sat.derivatives["Psat"]["T"] / ratio - 1.0) <= bound


def internal_energy_and_entropy(t: float) -> tuple[float, float]:
    sat, liquid, _ = both_phases_at_psat(t)
    u = liquid.values["h"] - sat.values["Psat"] * liquid.values["v"]
    return u, liquid.values["s"]


def test_a12_the_datum() -> None:
    u, s = internal_energy_and_entropy(273.16)
    assert abs(u) <= 1e-6 and abs(s) <= 1e-8, (u, s)
    assert abs(float(REF["datum"]["u_l_triple"])) <= 1e-6
    # Control: the same quantities at 450 K are far from zero.
    u450, s450 = internal_energy_and_entropy(450.0)
    assert abs(u450) > 1000.0 and abs(s450) > 10.0


# -- A13: the band ---------------------------------------------------------------------------------


@pytest.mark.parametrize("key", list(BAND))
def test_a13_band_probes(key: str) -> None:
    probe = BAND[key]
    p = float(probe["P"])
    for phase in ("LIQUID", "VAPOR"):
        result = ev(BAND_T, p, phase, derivatives=())
        if phase not in probe["answered"]:
            refused(result, "unsupported", "phase_not_stable")
            continue
        assert result.status == "ok" and result.phase_signature == phase, result.message
        for x in SIX:
            expected = float(probe[phase][x])
            assert abs(result.values[x] - expected) <= value_bound(key, x, BAND_T, expected), x


# -- A14-A16, A18, A19, A21: refusal probes and their controls (spec §5.5) -------------------------


def test_a14_near_critical() -> None:
    for phase in ("VAPOR", "LIQUID"):
        refused(ev(647.5, 2.21e7, phase), "unsupported", "near_critical")
    refused(flash(647.5, 2.21e7), "unsupported", "near_critical")
    refused(ev(647.05, 2.20e7, "LIQUID"), "unsupported", "near_critical")
    # Controls: T = 648.0 is outside the open interval; 2.19e7 Pa is below the box.
    assert ev(648.0, 2.21e7, "VAPOR").status == "ok"
    assert flash(648.0, 2.21e7).status == "ok"
    assert ev(*tp("NC_vapour")).status == "ok"


def test_a15_supercritical_label_and_the_647_edge() -> None:
    probes = [
        ((700.0, 3.0e7, "LIQUID"), (700.0, 3.0e7, "VAPOR")),
        ((647.05, 2.19e7, "LIQUID"), tp("NC_vapour")),
        ((647.05, 2.23e7, "VAPOR"), tp("NC_liquid")),
        ((647.0, 2.21e7, "VAPOR"), (647.0, 2.21e7, "LIQUID")),
        (
            (BAND_T, float(BAND["out_lo"]["P"]), "LIQUID"),
            (BAND_T, float(BAND["in_lo"]["P"]), "LIQUID"),
        ),
        (
            (BAND_T, float(BAND["out_hi"]["P"]), "VAPOR"),
            (BAND_T, float(BAND["in_hi"]["P"]), "VAPOR"),
        ),
    ]
    for (t, p, phase), (ct, cp, cphase) in probes:
        refused(ev(t, p, phase), "unsupported", "phase_not_stable")  # type: ignore[arg-type]
        control = ev(ct, cp, cphase)  # type: ignore[arg-type]
        assert control.status == "ok", (ct, cp, cphase, control.message)


DOMAIN_PROBES = [
    ((273.15, 1.0e5, "LIQUID"), "L_corner"),
    ((1273.16, 1.0e5, "VAPOR"), "SC_corner"),
    ((400.0, 99.0, "VAPOR"), "V_corner"),
    ((700.0, 1.0000001e8, "VAPOR"), "SC_corner"),
]


@pytest.mark.parametrize(("probe", "control"), DOMAIN_PROBES)
def test_a16_domain_edges(probe: tuple[float, float, Phase], control: str) -> None:
    t, p, phase = probe
    refused(ev(t, p, phase, ("h",)), "out_of_domain", "out_of_domain")
    refused(ev(t, p, phase, ("Psat",)), "out_of_domain", "out_of_domain")
    refused(ev(t, p, phase, ("Tsat",)), "out_of_domain", "out_of_domain")
    refused(flash(t, p), "out_of_domain", "out_of_domain")
    ct, cp, cphase = tp(control)
    assert ev(ct, cp, cphase, ("h",)).status == "ok"
    assert flash(ct, cp).status == "ok"
    assert ev(ct, 1.0e5, cphase, ("Psat",)).status == "ok" or ct > w.T_SIGMA_MAX
    assert ev(300.0, 1.0e5, "LIQUID", ("Tsat",)).status == "ok"


def test_a18_no_saturation() -> None:
    for t in (647.0001, 700.0):
        refused(psat(t), "unsupported", "no_saturation")
    for p in (2.21e7, 1.0e2):
        refused(ev(300.0, p, "LIQUID", ("Tsat",)), "unsupported", "no_saturation")
    assert psat(647.0).status == "ok"
    assert ev(300.0, 1.0e7, "LIQUID", ("Tsat",)).status == "ok"


def test_a19_saturation_only_skips_the_phase_check() -> None:
    only = ev(450.0, 1.0e4, "LIQUID", ("Psat",))
    assert only.status == "ok" and only.phase_signature == "LIQUID"
    refused(ev(450.0, 1.0e4, "LIQUID", ("Psat", "h")), "unsupported", "phase_not_stable")


def test_a21_contract_refusals() -> None:
    t, p, phase = tp("L_ambient")
    refused(ev(t, p, phase, derivatives=("n_N2",)), "unsupported", "undeclared_derivative_input")
    refused(ev(t, p, phase, ("g",)), "unsupported", "unknown_property")
    refused(ev(t, p, phase, n=(1.0, 0.0)), "error", "state_length")
    refused(ev(t, p, phase, n=(0.0,)), "unsupported", "dormant_state")
    assert ev(t, p, phase).status == "ok"


# -- A17: value/derivative consistency (spec §6.3) -------------------------------------------------

FD_TOL = 1e-10
FD_STEP = 1e-6
#: Spec §14 (R-597a): NC's step; the 1e-6·x stencil's truncation was measured at 1.25e-9.
FD_STEP_NC = 1e-7


def fd_scale(x: str, t: float) -> float:
    return {"h": w.R * t, "s": w.R, "cp": w.R, "Z": 1.0, "lnphi_H2O": 1.0, "v": 0.0}[x]


def fd_stencil(t: float, p: float, wrt: str, kind: str) -> tuple[float, float]:
    """Spec §14 (R-597): the step h and the side s of the stencil in `wrt` (s = 0 central; ±1 the
    inward one-sided stencil at a box edge, R-597b). `kind` is "nc" (R-597a), "band" (R-597c:
    h_P = (ε_σ/4)·P, h_T = (ε_σ/4)/|d ln p_σ/dT| from the provider's own Psat) or "tp"."""
    x, low, high = (t, w.T_MIN, w.T_MAX) if wrt == "T" else (p, w.P_MIN, w.P_MAX)
    side = 1.0 if x == low else -1.0 if x == high else 0.0
    if kind == "band":
        if wrt == "P":
            return w.EPS_SIGMA / 4.0 * p, side
        psat = ev(t, 1.0e5, "LIQUID", ("Psat",), ("T", "P", "n_H2O"))
        assert psat.status == "ok", psat.message
        slope = psat.derivatives["Psat"]["T"] / psat.values["Psat"]
        return w.EPS_SIGMA / 4.0 / abs(slope), side
    return (FD_STEP_NC if kind == "nc" else FD_STEP) * x, side


def fd_ratios(
    t: float, p: float, phase: Phase, wrt: str, h: float, side: float
) -> dict[str, float]:
    """Per property, the central |f(x+h) − f(x−h) − 2h f′| / max(|f(x±h)|, s_f), or at a box edge
    the inward |s(−3f₀ + 4f₁ − f₂) − 2h f′| / max(|f₀|, |f₁|, |f₂|, s_f) with f_k = f(x + k s h);
    raises on a refusal."""

    def at(k: float) -> PropertyResult:
        return ev(t + k * h, p, phase) if wrt == "T" else ev(t, p + k * h, phase)

    centre = ev(t, p, phase)
    first, second = (at(1.0), at(-1.0)) if side == 0.0 else (at(side), at(2.0 * side))
    for result in (centre, first, second):
        if result.status != "ok":
            raise AssertionError(f"a stencil point is refused: {result.message}")
    ratios = {}
    for x in SIX:
        f0, f1, f2 = centre.values[x], first.values[x], second.values[x]
        slope = 2.0 * h * centre.derivatives[x][wrt]
        if side == 0.0:
            miss, scale = abs(f1 - f2 - slope), max(abs(f1), abs(f2), fd_scale(x, t))
        else:
            miss = abs(side * (-3.0 * f0 + 4.0 * f1 - f2) - slope)
            scale = max(abs(f0), abs(f1), abs(f2), fd_scale(x, t))
        ratios[x] = miss / scale
    return ratios


def fd_cases() -> list[Any]:
    """Every §5.2 state and every answered band phase, in T and in P: no case is dropped (R-597)."""
    cases = []
    for name in TP_STATES:
        for wrt in ("T", "P"):
            t, p, phase = tp(name)
            kind = "nc" if name in NC else "tp"
            cases.append(pytest.param(t, p, phase, wrt, kind, id=f"{name}-{wrt}"))
    for key, probe in BAND.items():
        for phase in probe["answered"]:
            for wrt in ("T", "P"):
                p = float(probe["P"])
                case_id = f"band_{key}-{phase}-{wrt}"
                cases.append(pytest.param(BAND_T, p, phase, wrt, "band", id=case_id))
    return cases


@pytest.mark.parametrize(("t", "p", "phase", "wrt", "kind"), fd_cases())
def test_a17_finite_differences(t: float, p: float, phase: Phase, wrt: str, kind: str) -> None:
    h, side = fd_stencil(t, p, wrt, kind)
    ratios = fd_ratios(t, p, phase, wrt, h, side)
    assert max(ratios.values()) <= FD_TOL, ratios


# -- A20: flash ------------------------------------------------------------------------------------


@pytest.mark.parametrize("name", list(TP_STATES))
def test_a20_single_phase_flash(name: str) -> None:
    t, p, phase = tp(name)
    result = flash(t, p)
    assert result.status == "ok" and result.phase_signature == phase, result.message
    state = StreamState(n=(1.0,), temperature=t, pressure=p)
    empty = StreamState(n=(0.0,), temperature=t, pressure=p)
    assert result.vapor_fraction == (1.0 if phase == "VAPOR" else 0.0)
    assert (result.vapor, result.liquid) == ((state, empty) if phase == "VAPOR" else (empty, state))
    assert dict(result.k_values) == {}


def test_a20_band_dormant_and_contract() -> None:
    refused(flash(BAND_T, float(BAND["in_lo"]["P"])), "unsupported", "tp_flash_degenerate")
    control = flash(BAND_T, float(BAND["out_lo"]["P"]))
    assert control.status == "ok" and control.vapor_fraction == 1.0
    t, p, _ = tp("L_ambient")
    dormant = flash(t, p, n=(0.0,))
    zero = StreamState(n=(0.0,), temperature=t, pressure=p)
    assert (dormant.status, dormant.phase_signature, dormant.vapor_fraction) == (
        "ok",
        "ZERO_FLOW",
        None,
    )
    assert (dormant.vapor, dormant.liquid) == (zero, zero)
    refused(flash(t, p, spec="PH"), "unsupported", "unsupported_specification")
    refused(flash(t, p, der=("T",)), "unsupported", "flash_derivatives_unsupported")
    refused(flash(t, p, n=(1.0, 0.0)), "error", "state_length")
    assert flash(t, p).status == "ok"


# -- A23: determinism and identity on every result -------------------------------------------------


def test_a23_determinism_and_identity() -> None:
    t, p, phase = tp("L_ambient")
    calls = [
        lambda: ev(t, p, phase),
        lambda: ev(*tp("NC_vapour")),
        lambda: ev(BAND_T, float(BAND["at"]["P"]), "LIQUID"),
        lambda: psat(450.0),
        lambda: ev(300.0, 1.0e6, "VAPOR", ("Tsat",)),
        lambda: ev(647.5, 2.21e7, "VAPOR"),
        lambda: ev(t, p, phase, ("g",)),
        lambda: ev(273.15, p, phase),
        lambda: flash(t, p),
        lambda: flash(t, p, spec="PH"),
        lambda: flash(BAND_T, float(BAND["in_lo"]["P"])),
    ]
    for call in calls:
        first, second = call(), call()
        assert repr(first) == repr(second)
        assert first.provider_id == "iapws95-v1"
        assert first.reference_convention == "IAPWS95-ref-v1"
        assert first.achieved_accuracy == "exact-double"
        if isinstance(first, PropertyResult):
            for value in first.values.values():
                assert math.isfinite(value)
