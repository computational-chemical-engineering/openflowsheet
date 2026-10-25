"""S10.A01-A11, A23 (the `evaluate_phase` half) and A24-A28: the `wilson-ig-v1` provider, its
records and its registrations (S10 spec §5.1-§5.3, §7; ADR 0047; WO-S10-1).

Every expectation comes from `benchmarks/s10/reference_values.yaml`, which
`docs/derivations/scripts/s10_reference.py` (S10.A25) writes at 50 digits from
`benchmarks/s10/verification-records.yaml` and never from the implementation. The records are three
SYNTHETIC components (spec §6): nothing here is evidence about a real mixture. Tolerances are spec
§7.2's: |impl - expected| <= TOL_VALUE * max(|expected|, s_q), and the identity zeros of §3.6
exactly 0.0.
"""

from __future__ import annotations

import hashlib
import math
import re
import subprocess
import sys
from collections.abc import Callable, Mapping
from pathlib import Path, PurePosixPath
from typing import Any

import pytest
import yaml
from conftest import REPO_ROOT

from openflowsheet.application import revision_binding
from openflowsheet.resources import PACKAGED
from openflowsheet.thermo import (
    PropertyProvider,
    PropertyRequest,
    PropertyResult,
    StreamState,
    wilson_ig,
)
from openflowsheet.thermo.stability import StabilityReport
from openflowsheet.thermo.wilson_ig import RecordError, WilsonIdealGasProvider

RECORDS = REPO_ROOT / "benchmarks" / "s10" / "verification-records.yaml"
REFERENCE_PATH = REPO_ROOT / "benchmarks" / "s10" / "reference_values.yaml"
GENERATOR = REPO_ROOT / "docs" / "derivations" / "scripts" / "s10_reference.py"
REFERENCE: dict[str, Any] = yaml.safe_load(REFERENCE_PATH.read_text("utf-8"))
E_STATES: dict[str, Any] = REFERENCE["closed_form"]["evaluate_phase"]
STATE_IDS = tuple(E_STATES)
PHASES = ("LIQUID", "VAPOR")
COMPONENTS = ("VA", "VB", "VC")
PROPERTIES = ("h", "lnphi_VA", "lnphi_VB", "lnphi_VC")
INPUTS = ("T", "P", "n_VA", "n_VB", "n_VC")
#: Spec §7.2.
TOL_VALUE = 1.0e-12
#: S10.A08's bound on the implementation's own identities.
TOL_IDENTITY = 1.0e-11
CONTEXT: Any = None

#: Spec §5.7, verbatim (S10.A01).
LIMITATIONS = (
    "Gamma-phi with a Wilson liquid (constant Lambda) and an ideal-gas vapour; no Poynting factor; "
    "h^E = 0; no liquid volume (v is not offered).",
    "One liquid phase only: the Wilson liquid cannot split (strict convexity, S10 spec section "
    "4.1); no LLE, and no statement that the real mixture has none.",
    "Stability: STABLE_WITHIN_TESTED_SCOPE is global within the model (one Wilson liquid, one "
    "ideal gas) at resolution 1e-10 in the tangent-plane distance; scope S10-tpd-v1.",
    "TP flash only; a flash that asks for derivatives is refused; PH flash is not a provider "
    "capability (FlashRequest carries no enthalpy).",
    "Successive substitution capped at 1000 iterations per loop; reaching the cap returns "
    "not_converged with stability UNKNOWN, never a split.",
)

#: The U02 limitation S10's evidence manifest carries (R-569, R-709; spec §10): T08 C3 requires
#: every S10 harvest item with U02 in `to` to name the provider in back-ticks and `library-only`.
#: Until S10's manifest generator exists it lives here; that generator takes it over verbatim
#: (docs/S10_DECISIONS.md, B-3).
U02_LIBRARY_ONLY = (
    "`wilson-ig-v1` is library-only (R-568, R-569, R-709): it is not in "
    "revision_binding.SELECTABLE_BASES, so no revision can select it and no development case "
    "becomes runnable (U02); it is registered in the T08 envelope's LIBRARY_ONLY_PROVIDERS and its "
    "scanned_providers (S10 spec §10). The column's refusal S11 is unchanged and no unit model "
    "accepts the provider. Coverage counts are unchanged."
)


@pytest.fixture(scope="module")
def provider() -> WilsonIdealGasProvider:
    return WilsonIdealGasProvider(RECORDS)


def _state(sid: str) -> StreamState:
    entry = E_STATES[sid]["state"]
    return StreamState(n=tuple(entry["n"]), temperature=entry["T"], pressure=entry["P"])


def _full(provider: WilsonIdealGasProvider, state: StreamState, phase: str) -> PropertyResult:
    request = PropertyRequest(
        state=state,
        phase=phase,  # type: ignore[arg-type]
        properties=PROPERTIES,
        derivatives=INPUTS,
    )
    return provider.evaluate_phase(request, CONTEXT)


def _scale(prop: str, wrt: str | None, n_tot: float, pressure: float) -> float:
    """s_q of spec §7.2 (`reference_values.yaml` `tolerances.evaluate_phase.s_q`)."""
    if prop == "h":
        return {None: 1.0e3, "T": 10.0, "P": 0.0}.get(wrt, 1.0e3 / n_tot)
    return {None: 1.0, "T": 1.0e-2, "P": 1.0 / pressure}.get(wrt, 1.0 / n_tot)


def _identity_zero(phase: str, prop: str, wrt: str) -> bool:
    """§3.6's identity zeros: every VAPOR ln phi derivative, dh/dP in both phases."""
    return (phase == "VAPOR" and prop != "h") or (prop == "h" and wrt == "P")


def _within(got: float, want: float, scale: float) -> bool:
    return abs(got - want) <= TOL_VALUE * max(abs(want), scale)


def _assert_refused(result: PropertyResult, status: str, code: str) -> None:
    assert result.status == status, result.message
    assert result.message.startswith(f"{code}:"), result.message
    assert result.values == {} and result.derivatives == {} and result.phase_signature is None
    assert result.provider_id == "wilson-ig-v1"


# -- A01: describe() -------------------------------------------------------------------------------


def test_a01_describe_is_spec_5_2(provider: WilsonIdealGasProvider) -> None:
    caps = provider.describe()
    document = yaml.safe_load(RECORDS.read_text("utf-8"))
    assert caps.provider_id == "wilson-ig-v1"
    module = REPO_ROOT / "src" / "openflowsheet" / "thermo" / "wilson_ig.py"
    assert caps.implementation_sha256 == hashlib.sha256(module.read_bytes()).hexdigest()
    assert caps.data_sha256 == hashlib.sha256(RECORDS.read_bytes()).hexdigest()
    assert caps.reference_convention == "S10-VER-ref-v1"
    assert caps.state_definition == "nTP-v1"
    assert caps.components == COMPONENTS
    assert caps.phases == ("LIQUID", "VAPOR")
    assert caps.properties == PROPERTIES
    assert caps.flashes == ("TP",)
    assert dict(caps.derivative_order) == dict.fromkeys(INPUTS, 1)
    assert list(caps.derivative_order) == list(INPUTS)
    assert dict(caps.domain) == {"T": (300.0, 420.0), "P": (50000.0, 300000.0)}
    assert caps.uncertainty == document["uncertainty"]
    assert caps.data_provenance == document["data_provenance"]
    assert caps.thread_safety == "thread_safe"
    assert caps.numerical_limitations == LIMITATIONS
    assert isinstance(provider, PropertyProvider)


def test_a01_the_default_records_are_the_real_records() -> None:
    """`None` is the real records, a source checkout's `benchmarks/s10/records.yaml` (spec §5.1),
    committed by WO-S10-3; a missing file is an explicit refusal."""
    real = REPO_ROOT / wilson_ig.RECORDS_PATH
    assert real.is_file()
    caps = WilsonIdealGasProvider().describe()
    assert caps.reference_convention == "WILSON-IG-ref-v1"
    assert caps.uncertainty == (  # spec §17 A4-3 (R-721) and §19 A6-9 (VAL-2's sentence)
        "Validation (S10 spec §9.6; docs/s10-validation-report.md): VAL-1 within band (38 "
        "held-out ternary points, 101.3 kPa, 339.7-368.0 K: AAD(T) 0.21 K, AAD(y) <= 0.0057, "
        "max |dy| 0.021). VAL-3: latent heat of methanol not validated within band (+5.72 % at "
        "T_b(101325 Pa) against 5 %, from the ideal-gas vapour); ethanol and water latent heats "
        "and all liquid c_p within band, the c_p low by up to 19.7 % (methanol). VAL-2 within "
        "band (constant Lambda off the 101.3 kPa isobar: 159 held-out isothermal binary points, "
        "323.15-333.15 K, Kurihara et al. 1995; judged per binary): methanol-water within band, "
        "AAD(dP/P) 1.09 %, AAD(y) 0.0048; ethanol-water within band, AAD(dP/P) 0.29 %, AAD(y) "
        "0.0041; 40 of the 159 measured pressures lie below the records' 30 kPa domain bound, "
        "which is not extended. The methanol-ethanol "
        "Lambda are individually undetermined by the binary data; the fit's second minimum "
        "moves ternary bubble temperatures by up to 0.46 K (S10 spec §17 A4-2)."
    )
    assert caps.uncertainty == yaml.safe_load(real.read_text("utf-8"))["uncertainty"]
    with pytest.raises(RecordError, match=r"^records_missing: "):
        WilsonIdealGasProvider(REPO_ROOT / "benchmarks" / "s10" / "no-such-records.yaml")


# -- A02: the loader -------------------------------------------------------------------------------


def test_a02_the_loader_hands_over_the_files_floats_bitwise(
    provider: WilsonIdealGasProvider,
) -> None:
    document = yaml.safe_load(RECORDS.read_text("utf-8"))
    records = provider.records
    assert records.components == tuple(c["id"] for c in document["components"])
    for index, component in enumerate(document["components"]):
        parameters = {name: q["value"] for name, q in component["parameters"].items()}
        cp = tuple(float(parameters[f"ideal_gas_cp_b{k}"]) for k in range(5))
        psat = tuple(float(parameters[f"vapour_pressure_{c}"]) for c in "abcd")
        assert records.cp[index] == cp, component["id"]
        assert records.vapour_pressure[index] == psat, component["id"]
        assert records.formation_enthalpy[index] == parameters["standard_formation_enthalpy"]
    for entry in document["wilson_lambda"]:
        i, j = COMPONENTS.index(entry["i"]), COMPONENTS.index(entry["j"])
        assert records.wilson_lambda[i][j] == float(entry["value"]), entry
    assert all(records.wilson_lambda[i][i] == 1.0 for i in range(3))
    assert records.temperature_domain == (300.0, 420.0)
    assert records.pressure_domain == (50000.0, 300000.0)
    assert records.synthetic is True and records.data_set == "S10-verification-v1"


def _mutate_component_unknown_key(d: dict[str, Any]) -> None:
    d["components"][0]["cas_rn"] = "000-00-0"


def _mutate_parameter_missing(d: dict[str, Any]) -> None:
    del d["components"][1]["parameters"]["vapour_pressure_d"]


def _mutate_duplicate_id(d: dict[str, Any]) -> None:
    d["components"][2]["id"] = "VA"


def _mutate_schema_version(d: dict[str, Any]) -> None:
    d["schema_version"] = 2


def _mutate_top_unknown(d: dict[str, Any]) -> None:
    d["extra"] = 1


def _mutate_top_missing(d: dict[str, Any]) -> None:
    del d["domain"]


def _mutate_unit(d: dict[str, Any]) -> None:
    d["components"][0]["parameters"]["standard_formation_enthalpy"]["unit"] = "kJ/mol"


def _mutate_kind(d: dict[str, Any]) -> None:
    d["components"][1]["parameters"]["vapour_pressure_b"]["kind"] = "temperature"


def _mutate_convention(d: dict[str, Any]) -> None:
    d["reference_convention"] = "SYN-001-ref-v1"


def _mutate_real_convention_synthetic(d: dict[str, Any]) -> None:
    d["reference_convention"] = "WILSON-IG-ref-v1"


def _mutate_component_synthetic(d: dict[str, Any]) -> None:
    d["components"][2]["synthetic"] = False


def _mutate_lambda_missing(d: dict[str, Any]) -> None:
    del d["wilson_lambda"][3]


def _mutate_lambda_duplicate(d: dict[str, Any]) -> None:
    d["wilson_lambda"][1] = dict(d["wilson_lambda"][0])


def _mutate_lambda_diagonal(d: dict[str, Any]) -> None:
    d["wilson_lambda"].append({"i": "VB", "j": "VB", "value": 1.0})


def _mutate_lambda_nan(d: dict[str, Any]) -> None:
    d["wilson_lambda"][2]["value"] = float("nan")


def _mutate_lambda_zero(d: dict[str, Any]) -> None:
    d["wilson_lambda"][4]["value"] = 0.0


def _mutate_lambda_negative(d: dict[str, Any]) -> None:
    d["wilson_lambda"][5]["value"] = -0.3


def _mutate_domain_order(d: dict[str, Any]) -> None:
    d["domain"]["P"] = [300000.0, 300000.0]


def _mutate_domain_nasa(d: dict[str, Any]) -> None:
    d["domain"]["T"] = [150.0, 420.0]


MALFORMED: dict[str, tuple[str, Callable[[dict[str, Any]], None]]] = {
    "component_unknown_key": ("record_structure", _mutate_component_unknown_key),
    "parameter_missing": ("record_structure", _mutate_parameter_missing),
    "duplicate_id": ("record_structure", _mutate_duplicate_id),
    "schema_version": ("record_structure", _mutate_schema_version),
    "top_unknown_key": ("record_structure", _mutate_top_unknown),
    "top_missing_key": ("record_structure", _mutate_top_missing),
    "unit": ("record_units", _mutate_unit),
    "kind": ("record_units", _mutate_kind),
    "convention": ("record_convention", _mutate_convention),
    "real_convention_on_synthetic_data": ("record_convention", _mutate_real_convention_synthetic),
    "component_synthetic_flag": ("record_convention", _mutate_component_synthetic),
    "lambda_missing": ("record_lambda", _mutate_lambda_missing),
    "lambda_duplicate": ("record_lambda", _mutate_lambda_duplicate),
    "lambda_diagonal": ("record_lambda", _mutate_lambda_diagonal),
    "lambda_nan": ("record_lambda", _mutate_lambda_nan),
    "lambda_zero": ("record_lambda", _mutate_lambda_zero),
    "lambda_negative": ("record_lambda", _mutate_lambda_negative),
    "domain_lo_ge_hi": ("record_domain", _mutate_domain_order),
    "domain_outside_nasa": ("record_domain", _mutate_domain_nasa),
}


def _write(document: Mapping[str, Any], path: Path) -> Path:
    path.write_text(yaml.safe_dump(dict(document), sort_keys=False), "utf-8")
    return path


@pytest.mark.parametrize("case", sorted(MALFORMED))
def test_a02_a_malformed_copy_is_refused_with_its_code(case: str, tmp_path: Path) -> None:
    code, mutate = MALFORMED[case]
    document = yaml.safe_load(RECORDS.read_text("utf-8"))
    # control: the unmutated copy, re-serialised, loads
    WilsonIdealGasProvider(_write(document, tmp_path / "control.yaml"))
    mutate(document)
    with pytest.raises(RecordError) as raised:
        WilsonIdealGasProvider(_write(document, tmp_path / "malformed.yaml"))
    assert str(raised.value).startswith(f"{code}: "), str(raised.value)


def test_a02_every_spec_code_is_exercised() -> None:
    codes = {code for code, _ in MALFORMED.values()}
    assert codes == {
        "record_structure",
        "record_units",
        "record_convention",
        "record_lambda",
        "record_domain",
    }


# -- A03: the fixture's identity -------------------------------------------------------------------


def test_a03_the_reference_was_generated_from_these_records() -> None:
    digest = hashlib.sha256(RECORDS.read_bytes()).hexdigest()
    assert REFERENCE["records_sha256"] == digest
    assert digest.startswith("234d165d") and digest.endswith("aab392")


# -- A04, A05: values and derivatives at E1-E6 -----------------------------------------------------


def _worst(provider: WilsonIdealGasProvider) -> tuple[float, str]:
    """The largest |impl - expected| / (TOL_VALUE max(|expected|, s_q)) over every non-identity
    entry of A04 and A05, and where it is."""
    worst, where = 0.0, ""
    for sid in STATE_IDS:
        state = _state(sid)
        n_tot, pressure = state.total_flow, state.pressure
        for phase in PHASES:
            result = _full(provider, state, phase)
            expected = E_STATES[sid][phase]
            for prop, want in expected["values"].items():
                scale = _scale(prop, None, n_tot, pressure)
                ratio = abs(result.values[prop] - want) / (TOL_VALUE * max(abs(want), scale))
                if ratio > worst:
                    worst, where = ratio, f"{sid}.{phase}.{prop}"
            for prop, row in expected["derivatives"].items():
                for wrt, want in row.items():
                    if _identity_zero(phase, prop, wrt):
                        continue
                    scale = _scale(prop, wrt, n_tot, pressure)
                    got = result.derivatives[prop][wrt]
                    ratio = abs(got - want) / (TOL_VALUE * max(abs(want), scale))
                    if ratio > worst:
                        worst, where = ratio, f"{sid}.{phase}.d{prop}/d{wrt}"
    return worst, where


@pytest.mark.parametrize("phase", PHASES)
@pytest.mark.parametrize("sid", STATE_IDS)
def test_a04_values(provider: WilsonIdealGasProvider, sid: str, phase: str) -> None:
    state = _state(sid)
    result = _full(provider, state, phase)
    assert result.status == "ok" and result.phase_signature == phase
    assert result.reference_convention == "S10-VER-ref-v1"
    expected = E_STATES[sid][phase]["values"]
    assert set(result.values) == set(PROPERTIES) == set(expected)
    for prop, want in expected.items():
        scale = _scale(prop, None, state.total_flow, state.pressure)
        assert _within(result.values[prop], want, scale), (prop, result.values[prop], want)


@pytest.mark.parametrize("phase", PHASES)
@pytest.mark.parametrize("sid", STATE_IDS)
def test_a05_derivatives(provider: WilsonIdealGasProvider, sid: str, phase: str) -> None:
    state = _state(sid)
    result = _full(provider, state, phase)
    expected = E_STATES[sid][phase]["derivatives"]
    assert set(result.derivatives) == set(PROPERTIES) == set(expected)
    for prop, row in expected.items():
        assert list(result.derivatives[prop]) == list(INPUTS)
        for wrt, want in row.items():
            got = result.derivatives[prop][wrt]
            if _identity_zero(phase, prop, wrt):
                continue  # A06
            scale = _scale(prop, wrt, state.total_flow, state.pressure)
            assert _within(got, want, scale), (prop, wrt, got, want)


def test_a04_a05_worst_agreement(provider: WilsonIdealGasProvider) -> None:
    """The worst entry is well inside the tolerance (the floor argument of §7.2: about 0.07)."""
    worst, where = _worst(provider)
    assert worst <= 1.0, (worst, where)


# -- A06: the identity zeros -----------------------------------------------------------------------


def test_a06_the_102_identity_zeros_are_present_and_exactly_zero(
    provider: WilsonIdealGasProvider,
) -> None:
    count = 0
    for sid in STATE_IDS:
        for phase in PHASES:
            result = _full(provider, _state(sid), phase)
            for prop in PROPERTIES:
                for wrt in INPUTS:
                    if _identity_zero(phase, prop, wrt):
                        value = result.derivatives[prop][wrt]
                        assert value == 0.0 and math.copysign(1.0, value) == 1.0, (sid, phase)
                        assert E_STATES[sid][phase]["derivatives"][prop][wrt] == 0.0
                        count += 1
            if phase == "VAPOR":
                assert all(result.values[f"lnphi_{c}"] == 0.0 for c in COMPONENTS)
    assert count == 102


# -- A07: E3's structural zeros --------------------------------------------------------------------


def _structural(prop: str, wrt: str) -> bool:
    """At E3 (pure VC): d ln phi_VC^L / dn_j for every j, and dX/dn_VC for every X (spec §3.6)."""
    return prop == "lnphi_VC" or wrt == "n_VC"


def test_a07_e3s_structural_zeros_vanish_there_and_not_at_e1(
    provider: WilsonIdealGasProvider,
) -> None:
    checked = 0
    for phase in PHASES:
        at_e3 = _full(provider, _state("E3"), phase)
        at_e1 = _full(provider, _state("E1"), phase)
        n3, p3 = _state("E3").total_flow, _state("E3").pressure
        for prop in PROPERTIES:
            for wrt in INPUTS[2:]:
                if not _structural(prop, wrt) or _identity_zero(phase, prop, wrt):
                    continue
                assert abs(at_e3.derivatives[prop][wrt]) <= TOL_VALUE * _scale(prop, wrt, n3, p3)
                want = E_STATES["E1"][phase]["derivatives"][prop][wrt]
                assert want != 0.0 and at_e1.derivatives[prop][wrt] != 0.0, (phase, prop, wrt)
                checked += 1
    # LIQUID: d ln phi_VC/dn_{VA,VB,VC} and dX/dn_VC of h, ln phi_VA, ln phi_VB; VAPOR: dh/dn_VC
    assert checked == 3 + 3 + 1


# -- A08: Gibbs-Duhem, symmetry and homogeneity on the implementation ----------------------------


@pytest.mark.parametrize("phase", PHASES)
@pytest.mark.parametrize("sid", STATE_IDS)
def test_a08_the_implementations_own_identities(
    provider: WilsonIdealGasProvider, sid: str, phase: str
) -> None:
    state = _state(sid)
    result = _full(provider, state, phase)
    n, n_tot = state.n, state.total_flow
    x = [v / n_tot for v in n]
    d = result.derivatives
    for j in COMPONENTS:
        duhem = sum(x[i] * d[f"lnphi_{c}"][f"n_{j}"] for i, c in enumerate(COMPONENTS))
        assert n_tot * abs(duhem) <= TOL_IDENTITY, (j, duhem)
        for c in COMPONENTS:
            asym = d[f"lnphi_{c}"][f"n_{j}"] - d[f"lnphi_{j}"][f"n_{c}"]
            assert n_tot * abs(asym) <= TOL_IDENTITY, (c, j, asym)
    for prop in PROPERTIES:
        euler = sum(n[k] * d[prop][f"n_{c}"] for k, c in enumerate(COMPONENTS))
        bound = TOL_IDENTITY * max(1.0, abs(result.values[prop]))
        assert abs(euler) <= bound, (prop, euler)


# -- A10, A11: refusals through evaluate_phase -----------------------------------------------------


def _request(
    n: tuple[float, ...] = (0.6, 1.0, 0.4),
    t: float = 350.0,
    p: float = 1.2e5,
    properties: tuple[str, ...] = PROPERTIES,
    derivatives: tuple[str, ...] = INPUTS,
) -> PropertyRequest:
    return PropertyRequest(
        state=StreamState(n=n, temperature=t, pressure=p),
        phase="LIQUID",
        properties=properties,
        derivatives=derivatives,
    )


R_STATES: dict[str, tuple[PropertyRequest, str, str]] = {
    "R1": (_request(t=299.0), "out_of_domain", "out_of_domain"),
    "R2": (_request(p=4.0e5), "out_of_domain", "out_of_domain"),
    "R3": (_request(n=(-1e-12, 1.0, 1.0)), "out_of_domain", "out_of_domain"),
    "R4": (_request(t=math.nan), "out_of_domain", "out_of_domain"),
    "R5": (_request(n=(1.0, 1.0)), "error", "state_length"),
    "R8": (_request(properties=("h", "v")), "unsupported", "unknown_property"),
    "R9": (_request(derivatives=("T", "n_X")), "unsupported", "undeclared_derivative_input"),
}


@pytest.mark.parametrize("rid", sorted(R_STATES))
def test_a10_refusals(provider: WilsonIdealGasProvider, rid: str) -> None:
    request, status, code = R_STATES[rid]
    for phase in PHASES:
        asked = PropertyRequest(
            state=request.state,
            phase=phase,  # type: ignore[arg-type]
            properties=request.properties,
            derivatives=request.derivatives,
        )
        _assert_refused(provider.evaluate_phase(asked, CONTEXT), status, code)


def test_a10_the_domain_corners_are_inclusive(provider: WilsonIdealGasProvider) -> None:
    """Control for R1/R2: E5 and E6 sit on the corners and are answered (A04)."""
    for corner in ((300.0, 3.0e5), (420.0, 5.0e4)):
        result = provider.evaluate_phase(_request(t=corner[0], p=corner[1]), CONTEXT)
        assert result.status == "ok", result.message


@pytest.mark.parametrize("prop", ["v", "Z", "g", "s"])
def test_a10_properties_the_method_does_not_offer(
    provider: WilsonIdealGasProvider, prop: str
) -> None:
    result = provider.evaluate_phase(_request(properties=(prop,)), CONTEXT)
    _assert_refused(result, "unsupported", "unknown_property")


def test_a11_a_dormant_state_is_refused(provider: WilsonIdealGasProvider) -> None:
    for phase in PHASES:
        request = PropertyRequest(
            state=StreamState(n=(0.0, 0.0, 0.0), temperature=350.0, pressure=1.0e5),
            phase=phase,  # type: ignore[arg-type]
            properties=PROPERTIES,
        )
        _assert_refused(provider.evaluate_phase(request, CONTEXT), "unsupported", "dormant_state")


def test_a11_the_answer_holds_exactly_what_was_asked(provider: WilsonIdealGasProvider) -> None:
    result = provider.evaluate_phase(
        _request(properties=("lnphi_VB",), derivatives=("n_VC", "P")), CONTEXT
    )
    assert result.status == "ok"
    assert list(result.values) == ["lnphi_VB"]
    assert {k: list(v) for k, v in result.derivatives.items()} == {"lnphi_VB": ["n_VC", "P"]}
    bare = provider.evaluate_phase(_request(properties=("h",), derivatives=()), CONTEXT)
    assert list(bare.values) == ["h"] and bare.derivatives == {}


# -- A23 (evaluate_phase half): permutation --------------------------------------------------------

PERMUTED = ("VC", "VA", "VB")


def test_a23_permuted_records_give_the_permuted_answers(tmp_path: Path) -> None:
    document = yaml.safe_load(RECORDS.read_text("utf-8"))
    by_id = {c["id"]: c for c in document["components"]}
    document["components"] = [by_id[c] for c in PERMUTED]
    permuted = WilsonIdealGasProvider(_write(document, tmp_path / "permuted.yaml"))
    assert permuted.describe().components == PERMUTED
    assert permuted.describe().properties == ("h", *(f"lnphi_{c}" for c in PERMUTED))
    entry = E_STATES["E1"]["state"]
    n = dict(zip(COMPONENTS, entry["n"], strict=True))
    state = StreamState(
        n=tuple(n[c] for c in PERMUTED), temperature=entry["T"], pressure=entry["P"]
    )
    inputs = ("T", "P", *(f"n_{c}" for c in PERMUTED))
    for phase in PHASES:
        request = PropertyRequest(
            state=state,
            phase=phase,  # type: ignore[arg-type]
            properties=PROPERTIES,
            derivatives=inputs,
        )
        result = permuted.evaluate_phase(request, CONTEXT)
        assert result.status == "ok"
        expected = E_STATES["E1"][phase]
        for prop, want in expected["values"].items():
            assert _within(result.values[prop], want, _scale(prop, None, 2.0, entry["P"])), prop
        for prop, row in expected["derivatives"].items():
            for wrt, want in row.items():
                got = result.derivatives[prop][wrt]
                if _identity_zero(phase, prop, wrt):
                    assert got == 0.0
                    continue
                assert _within(got, want, _scale(prop, wrt, 2.0, entry["P"])), (prop, wrt)


def test_a23_a_permuted_index_would_be_caught(provider: WilsonIdealGasProvider) -> None:
    """Control: the same flows in the wrong order miss E1's expectations by far more than the
    tolerance (DIST-01)."""
    entry = E_STATES["E1"]["state"]
    wrong = StreamState(
        n=tuple(entry["n"][k] for k in (2, 0, 1)), temperature=350.0, pressure=1.2e5
    )
    result = _full(provider, wrong, "LIQUID")
    want = E_STATES["E1"]["LIQUID"]["values"]["lnphi_VA"]
    assert abs(result.values["lnphi_VA"] - want) > 1.0e-3


# -- A24: no hidden state --------------------------------------------------------------------------


def test_a24_identical_calls_are_bitwise_identical(provider: WilsonIdealGasProvider) -> None:
    other = WilsonIdealGasProvider(RECORDS)
    for sid in STATE_IDS:
        for phase in PHASES:
            first = _full(provider, _state(sid), phase)
            again = _full(provider, _state(sid), phase)
            fresh = _full(other, _state(sid), phase)
            for result in (again, fresh):
                assert result == first
                for prop in PROPERTIES:
                    assert result.values[prop].hex() == first.values[prop].hex()
                    for wrt in INPUTS:
                        a, b = result.derivatives[prop][wrt], first.derivatives[prop][wrt]
                        assert a.hex() == b.hex()


# -- A25: the generator ----------------------------------------------------------------------------


def test_a25_the_generator_rederives_every_claim_and_the_committed_bytes() -> None:
    completed = subprocess.run(
        [sys.executable, str(GENERATOR), "--check"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=900,
        check=False,
    )
    output = completed.stdout + completed.stderr
    assert completed.returncode == 0, output
    assert re.search(r"^113 claims hold; reference_values\.yaml matches$", completed.stdout, re.M)
    assert len(REFERENCE["generator_claims"]) == 113
    assert all(claim["holds"] is True for claim in REFERENCE["generator_claims"])


# -- A26: the other providers are untouched --------------------------------------------------------

UNTOUCHED = ("syn001.py", "pr_c1.py", "pr_lib.py", "iapws95.py", "coolprop_heos.py")


def _git(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *arguments], cwd=REPO_ROOT, capture_output=True, text=True, check=False
    )


def test_a26_the_other_providers_are_byte_identical_to_main() -> None:
    ref = next(
        (r for r in ("main", "origin/main") if _git("rev-parse", "--verify", r).returncode == 0),
        None,
    )
    if ref is None:
        pytest.skip("no `main` ref in this checkout")
    for name in UNTOUCHED:
        path = f"src/openflowsheet/thermo/{name}"
        on_main = _git("rev-parse", f"{ref}:{path}")
        here = _git("hash-object", path)
        assert on_main.returncode == 0 and here.returncode == 0, path
        assert here.stdout.strip() == on_main.stdout.strip(), path


# -- A27: library-only -----------------------------------------------------------------------------


def _script(name: str) -> Any:
    import importlib.util

    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / "scripts" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_a27_library_only_registration() -> None:
    from test_t08_w2_support_envelope import LIBRARY_ONLY_PROVIDERS

    selectable = {basis.provider_id for basis in revision_binding.SELECTABLE_BASES}
    assert "wilson-ig-v1" not in selectable
    assert LIBRARY_ONLY_PROVIDERS["wilson-ig-v1"] == "S10"
    matrix = _script("t08_support_matrix")
    assert "wilson-ig-v1" in matrix.code_facts()["scanned_providers"]
    # control: the S07 provider is registered the same way, under its own package
    assert LIBRARY_ONLY_PROVIDERS["coolprop-heos-v1"] == "S07"


def test_a27_the_u02_note_names_the_provider() -> None:
    """The U02 limitation names `wilson-ig-v1` and library-only; once an S10 manifest is
    harvested, every S10 U02 item's note does and there is at least one (T08 C3 judges the same on
    the whole registry, and fails until then)."""
    assert "`wilson-ig-v1`" in U02_LIBRARY_ONLY and "library-only" in U02_LIBRARY_ONLY
    matrix = _script("t08_support_matrix")
    items = [
        entry
        for entry in matrix.load()["harvest"]
        if entry["manifest"].startswith("evidence/S10/") and "U02" in (entry.get("to") or [])
    ]
    for entry in items:
        assert "`wilson-ig-v1`" in entry["note"] and "library-only" in entry["note"], entry


def test_a27_the_registry_carries_the_s10_family() -> None:
    registry = yaml.safe_load((REPO_ROOT / "benchmarks" / "registry.yaml").read_text("utf-8"))
    (family,) = (f for f in registry["families"] if f["id"] == "S10")
    assert family["provider"] == "wilson-ig-v1"
    assert family["components"] == "benchmarks/s10/verification-records.yaml"
    assert family["reference"] == "benchmarks/s10/reference_values.yaml"
    assert family["reference_sha256"] == hashlib.sha256(REFERENCE_PATH.read_bytes()).hexdigest()
    assert family["records_sha256"] == REFERENCE["records_sha256"]
    assert family["reference_convention"] == "S10-VER-ref-v1"
    assert family["property_domain"]["temperature_K"] == {"min": 300.0, "max": 420.0}
    assert family["property_domain"]["pressure_Pa"] == {"min": 50000.0, "max": 300000.0}
    assert family["tolerances"]["evaluate_phase"]["TOL_VALUE"] == TOL_VALUE
    assert not any(case.get("family") == "S10" for case in registry["cases"])


# -- A28: not package data -------------------------------------------------------------------------


def _covers(entry: str, path: str) -> bool:
    entry_parts, path_parts = PurePosixPath(entry).parts, PurePosixPath(path).parts
    return path_parts[: len(entry_parts)] == entry_parts or entry_parts[: len(path_parts)] == (
        path_parts
    )


def test_a28_no_s10_records_file_is_packaged() -> None:
    forbidden = (
        wilson_ig.RECORDS_PATH,
        "benchmarks/s10/verification-records.yaml",
        "benchmarks/s10/reference_values.yaml",
        "benchmarks/s10",
    )
    assert [(e, p) for e in PACKAGED for p in forbidden if _covers(e, p)] == []
    # control: `_covers` does see a packaged file and a file below a packaged directory
    assert _covers("benchmarks/m01/components.yaml", "benchmarks/m01/components.yaml")
    assert _covers("schemas", "schemas/component-record.schema.json")


# -- the stability type (WO-S10-1 holds the type; WO-S10-2 fills it) -------------------------------


def test_the_stability_report_is_frozen_with_spec_5_5s_fields() -> None:
    import dataclasses

    fields = [f.name for f in dataclasses.fields(StabilityReport)]
    assert fields == [
        "label",
        "scope",
        "phase",
        "tm",
        "trial_composition",
        "iterations",
        "residual",
        "epsilon",
        "reason",
    ]
    report = StabilityReport(
        label="UNKNOWN",
        scope="S10-tpd-v1",
        phase="VAPOR",
        tm={"VAPOR": None, "LIQUID": None},
        trial_composition=None,
        iterations=0,
        residual=None,
        epsilon=1e-10,
        reason="dormant_state: composition undefined",
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        report.label = "UNSTABLE"  # type: ignore[misc]
