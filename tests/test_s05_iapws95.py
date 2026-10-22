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


def fd_scale(x: str, t: float) -> float:
    return {"h": w.R * t, "s": w.R, "cp": w.R, "Z": 1.0, "lnphi_H2O": 1.0, "v": 0.0}[x]


def fd_ratios(t: float, p: float, phase: Phase, wrt: str) -> dict[str, float]:
    """|f(x+h) − f(x−h) − 2h f′(x)| / max(|f(x±h)|, s_f) per property; raises on a refusal."""
    centre = ev(t, p, phase)
    h = FD_STEP * (t if wrt == "T" else p)
    up = ev(t + h, p, phase) if wrt == "T" else ev(t, p + h, phase)
    down = ev(t - h, p, phase) if wrt == "T" else ev(t, p - h, phase)
    for result in (centre, up, down):
        if result.status != "ok":
            raise AssertionError(f"a central step is refused: {result.message}")
    ratios = {}
    for x in SIX:
        f_up, f_down = up.values[x], down.values[x]
        miss = abs(f_up - f_down - 2.0 * h * centre.derivatives[x][wrt])
        ratios[x] = miss / max(abs(f_up), abs(f_down), fd_scale(x, t))
    return ratios


#: Cases whose central step leaves what the provider answers (the domain box, or the band for a
#: metastable phase), so spec §6.3's stencil cannot be formed there: a measured miss, recorded as
#: a QUESTION in docs/C10_DECISIONS.md, never dropped.
_EDGE = "a central step of 1e-6·x leaves the domain box"
_BAND_EDGE = "a central step of 1e-6·x leaves the eps_sigma band for this phase"
FD_UNREACHABLE = {
    ("L_corner", "T"): _EDGE,
    ("L_corner", "P"): _EDGE,
    ("V_corner", "T"): _EDGE,
    ("V_corner", "P"): _EDGE,
    ("SC_corner", "T"): _EDGE,
    ("SC_corner", "P"): _EDGE,
    ("SC_ideal", "T"): _EDGE,
    ("SC_ideal", "P"): _EDGE,
    # Measured: the cp miss is truncation, falling 8x per halving of the step (1.25e-9, 1.56e-10,
    # 1.95e-11 at 1e-6, 5e-7, 2.5e-7 for NC_vapour; 4.11e-10, 5.16e-11, 6.23e-12 for NC_liquid);
    # the derivative itself meets A06 at 1e-8. Spec §6.3's truncation bound holds away from the
    # box only (Q-6, docs/C10_DECISIONS.md).
    ("NC_vapour", "T"): "near-critical truncation: cp miss 1.25e-9 > FD_TOL (Q-6)",
    ("NC_liquid", "T"): "near-critical truncation: cp miss 4.11e-10 > FD_TOL (Q-6)",
}


def fd_cases() -> list[Any]:
    cases = []
    for name in TP_STATES:
        for wrt in ("T", "P"):
            t, p, phase = tp(name)
            reason = FD_UNREACHABLE.get((name, wrt))
            marks = [pytest.mark.xfail(strict=True, reason=reason)] if reason else []
            cases.append(pytest.param(t, p, phase, wrt, id=f"{name}-{wrt}", marks=marks))
    for key, probe in BAND.items():
        for phase in probe["answered"]:
            for wrt in ("T", "P"):
                reason = BAND_FD_UNREACHABLE.get((key, phase, wrt))
                marks = [pytest.mark.xfail(strict=True, reason=reason)] if reason else []
                cases.append(
                    pytest.param(
                        BAND_T,
                        float(probe["P"]),
                        phase,
                        wrt,
                        id=f"band_{key}-{phase}-{wrt}",
                        marks=marks,
                    )
                )
    return cases


#: Measured: every band probe's T step moves ln(P/p_σ) by about 1e-5 ≫ eps_sigma, and the P step
#: by 1e-6 = eps_sigma, so the stepped state leaves the band on one side for these phases.
BAND_FD_UNREACHABLE: dict[tuple[str, str, str], str] = {
    (key, phase, wrt): _BAND_EDGE
    for key, phase, wrt in (
        ("out_lo", "VAPOR", "T"),
        ("in_lo", "LIQUID", "T"),
        ("in_lo", "LIQUID", "P"),
        ("in_lo", "VAPOR", "T"),
        ("at", "LIQUID", "T"),
        ("at", "LIQUID", "P"),
        ("at", "VAPOR", "T"),
        ("in_hi", "LIQUID", "T"),
        ("in_hi", "VAPOR", "T"),
        ("in_hi", "VAPOR", "P"),
        ("out_hi", "LIQUID", "T"),
    )
}


@pytest.mark.parametrize(("t", "p", "phase", "wrt"), fd_cases())
def test_a17_central_differences(t: float, p: float, phase: Phase, wrt: str) -> None:
    ratios = fd_ratios(t, p, phase, wrt)
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
