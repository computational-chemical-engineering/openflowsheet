"""L01.A13-A21: the provider `pr-lib-v1` against its closed forms and against `pr-c1-v1`.

The expectations are `benchmarks/l01/reference_values.yaml` → `closed_form`, written at 50 digits by
`docs/derivations/scripts/l01_reference.py` (an mpmath transcription that never imports the
provider; its `--check` is run here too). The tolerances are M01 spec §9's (A07, A10, A12), which
L01.A15, A16 and A21 adopt with their arguments; A14's is the spec's own.
"""

from __future__ import annotations

import hashlib
import re
import subprocess
import sys
from collections.abc import Mapping
from itertools import combinations
from pathlib import Path
from typing import Any

import pytest
from conftest import REPO_ROOT, load_yaml

from openflowsheet.compiled import EvaluationContext
from openflowsheet.thermo import (
    FlashRequest,
    PropertyProvider,
    PropertyRequest,
    PropertyResult,
    StreamState,
    pr_c1,
    pr_lib,
)
from openflowsheet.thermo.pr_lib import (
    COMPONENTS,
    DERIVATIVE_INPUTS,
    PROPERTIES,
    PrLibProvider,
    load_records,
    real_roots,
)

GENERATOR = REPO_ROOT / "docs" / "derivations" / "scripts" / "l01_reference.py"
RECORDS = REPO_ROOT / "benchmarks" / "l01" / "components.yaml"
REFERENCE = load_yaml(REPO_ROOT / "benchmarks" / "l01" / "reference_values.yaml")
CLOSED = REFERENCE["closed_form"]
PHASE_STATES: Mapping[str, Any] = CLOSED["phase_states"]
GUARD_STATES: Mapping[str, Any] = CLOSED["guard_states"]
CONTEXT = EvaluationContext(model_version="l01-provider", constants_sha256="0" * 64)
PROVIDER = PrLibProvider()
CLAIM_COUNT = 46


def _rel(value: float, expected: float) -> float:
    """M01 spec §9's "rel": |impl − ref| / max(|ref|, 1)."""
    return abs(value - expected) / max(abs(expected), 1.0)


def _request(
    n: tuple[float, ...],
    temperature: float,
    pressure: float,
    properties: tuple[str, ...] = PROPERTIES,
    derivatives: tuple[str, ...] = (),
    phase: Any = "VAPOR",
) -> PropertyRequest:
    return PropertyRequest(
        state=StreamState(n=n, temperature=temperature, pressure=pressure),
        phase=phase,
        properties=properties,
        derivatives=derivatives,
    )


def _evaluate(sid: str, derivatives: tuple[str, ...] = ()) -> PropertyResult:
    state = PHASE_STATES[sid]
    request = _request(
        tuple(state["n_mol_s"]), state["T_K"], state["P_Pa"], derivatives=derivatives
    )
    return PROVIDER.evaluate_phase(request, CONTEXT)


def _assert_refused(result: PropertyResult, status: str, code: str) -> None:
    assert result.status == status, result.message
    assert result.message.startswith(f"{code}:"), result.message
    assert result.values == {} and result.derivatives == {} and result.phase_signature is None


# -- the reference generator ----------------------------------------------------------------------


def test_the_generator_rederives_every_claim_and_the_committed_bytes() -> None:
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
    assert re.search(
        rf"^{CLAIM_COUNT} claims hold; reference_values\.yaml matches$", completed.stdout, re.M
    ), output
    claims = REFERENCE["generator_claims"]
    assert len(claims) == CLAIM_COUNT and all(claim["holds"] is True for claim in claims)
    assert len({claim["id"] for claim in claims}) == CLAIM_COUNT


def test_the_reference_was_generated_from_the_committed_records() -> None:
    assert REFERENCE["components_yaml_sha256"] == hashlib.sha256(RECORDS.read_bytes()).hexdigest()
    assert REFERENCE["constants"]["order"] == list(COMPONENTS)
    assert set(PHASE_STATES) == {"V1L", "V2L", "P1"}
    assert set(CLOSED["derivatives"]) == {"V1L", "V2L"}


# -- A13: describe() and the refused requests ------------------------------------------------------


def test_a13_describe_declares_the_registered_surface() -> None:
    capabilities = PROVIDER.describe()
    assert isinstance(PROVIDER, PropertyProvider)
    assert capabilities.provider_id == "pr-lib-v1"
    assert capabilities.state_definition == "nTP-v1"
    assert capabilities.components == tuple(c.id for c in load_records().components) == COMPONENTS
    assert capabilities.phases == ("VAPOR",)
    assert capabilities.flashes == ()
    assert capabilities.reference_convention == "PR-C1-ref-v1"
    assert capabilities.properties == ("h", "Z", "v", *(f"lnphi_{c}" for c in COMPONENTS))
    assert dict(capabilities.derivative_order) == dict.fromkeys(DERIVATIVE_INPUTS, 1)
    assert dict(capabilities.domain) == {"T": (200.0, 1000.0), "P": (1.0e4, 3.0e7)}


def test_a13_identity_hashes_are_the_modules_and_the_records_bytes() -> None:
    capabilities = PROVIDER.describe()
    module = hashlib.sha256(Path(pr_lib.__file__).read_bytes()).hexdigest()
    assert capabilities.implementation_sha256 == module
    assert capabilities.data_sha256 == hashlib.sha256(RECORDS.read_bytes()).hexdigest()


def test_a13_a_liquid_request_is_refused_phase_unsupported() -> None:
    state = PHASE_STATES["P1"]
    request = _request(tuple(state["n_mol_s"]), state["T_K"], state["P_Pa"], phase="LIQUID")
    _assert_refused(PROVIDER.evaluate_phase(request, CONTEXT), "unsupported", "phase_unsupported")


@pytest.mark.parametrize("specification", ["TP", "PH"])
def test_a13_flash_is_refused_flash_unsupported(specification: str) -> None:
    state = PHASE_STATES["V1L"]
    request = FlashRequest(
        state=StreamState(n=tuple(state["n_mol_s"]), temperature=700.0, pressure=5e6),
        specification=specification,
    )
    result = PROVIDER.flash(request, CONTEXT)
    assert result.status == "unsupported"
    assert result.message.startswith("flash_unsupported:"), result.message
    assert result.phase_signature is None and result.vapor_fraction is None
    assert result.vapor is None and result.liquid is None and dict(result.k_values) == {}


# -- A14: the C1 cross-implementation identity ----------------------------------------------------

C1_LIGHT = ("H2", "N2", "Ar", "CH4")
C1_STATES = {
    "C1V": (700.0, 2.0e7, (0.6, 0.2, 0.05, 0.15)),
    "C1W": (300.0, 1.0e5, (0.25, 0.25, 0.25, 0.25)),
}


@pytest.mark.parametrize("sid", list(C1_STATES))
def test_a14_pr_lib_and_pr_c1_agree_on_the_shared_components(sid: str) -> None:
    """|Δ| ≤ 1e-12·max(|X|, 1) for Z, v, h, the four ln φ and their T, P, n derivatives.

    Measured at WO-L01-2: 0.0 for every entry at both states (bit-identical; docs/L01_DECISIONS.md).
    """
    temperature, pressure, flows = C1_STATES[sid]
    named = dict(zip(C1_LIGHT, flows, strict=True))
    properties = ("h", "Z", "v", *(f"lnphi_{c}" for c in C1_LIGHT))
    inputs = ("T", "P", *(f"n_{c}" for c in C1_LIGHT))
    results = []
    for module, provider in ((pr_c1, pr_c1.PrC1Provider()), (pr_lib, PROVIDER)):
        n = tuple(named.get(c, 0.0) for c in module.COMPONENTS)
        request = _request(n, temperature, pressure, properties, inputs)
        result = provider.evaluate_phase(request, CONTEXT)
        assert result.status == "ok", (module.__name__, result.message)
        results.append(result)
    c1, lib = results
    for name in properties:
        x = c1.values[name]
        assert abs(lib.values[name] - x) <= 1e-12 * max(abs(x), 1.0), name
        for wanted in inputs:
            x = c1.derivatives[name][wanted]
            assert abs(lib.derivatives[name][wanted] - x) <= 1e-12 * max(abs(x), 1.0), (
                name,
                wanted,
            )


# -- A15: values ----------------------------------------------------------------------------------


@pytest.mark.parametrize("sid", list(PHASE_STATES))
def test_a15_values_match_the_50_digit_reference(sid: str) -> None:
    """M01.A07's tolerance: Z, h, every ln φ rel 1e-12; v relative 1e-12."""
    result = _evaluate(sid)
    assert result.status == "ok", result.message
    assert result.phase_signature == "VAPOR"
    for name, value in PHASE_STATES[sid]["values"].items():
        if name == "v":
            assert abs(result.values[name] / value - 1.0) <= 1e-12, name
        else:
            assert _rel(result.values[name], value) <= 1e-12, name


@pytest.mark.parametrize("sid", ["V1L", "V2L"])
def test_a15_a_permuted_index_fails_the_value_check(sid: str) -> None:
    """M01.A09's argument: the nine ln φ differ pairwise by ≥ 1e6 times A15's tolerance."""
    values = [PHASE_STATES[sid]["values"][f"lnphi_{c}"] for c in COMPONENTS]
    assert min(abs(a - b) for a, b in combinations(values, 2)) >= 1e6 * 1e-12
    assert all(value != 0.0 for value in values)


@pytest.mark.parametrize(
    "sid", [*PHASE_STATES, *(g for g, s in GUARD_STATES.items() if "real_root_count" in s)]
)
def test_a15_root_counts_equal_the_references(sid: str) -> None:
    state = {**PHASE_STATES, **GUARD_STATES}[sid]
    roots = real_roots(state["T_K"], state["P_Pa"], state["n_mol_s"])
    assert len(roots) == state["real_root_count"], roots


# -- A16: derivatives -----------------------------------------------------------------------------


@pytest.mark.parametrize("sid", list(CLOSED["derivatives"]))
def test_a16_derivatives_match_the_50_digit_reference(sid: str) -> None:
    """M01.A10: |s·∂X_impl − s·∂X_ref| ≤ 1e-9·max(|X|, 1, |s·∂X_ref|), s = T, P or n_tot."""
    expected = CLOSED["derivatives"][sid]
    result = _evaluate(sid, DERIVATIVE_INPUTS)
    assert result.status == "ok", result.message
    state = PHASE_STATES[sid]
    scale = {"T": state["T_K"], "P": state["P_Pa"]}
    total = sum(state["n_mol_s"])
    assert set(expected) == set(PROPERTIES)
    for name, by_input in expected.items():
        value = result.values[name]
        assert set(by_input) == set(DERIVATIVE_INPUTS)
        for wanted, reference in by_input.items():
            s = scale.get(wanted, total)
            got = result.derivatives[name][wanted]
            bound = 1e-9 * max(abs(value), 1.0, abs(s * reference))
            assert abs(s * got - s * reference) <= bound, (name, wanted)


def test_a16_v1l_n_derivatives_are_all_nonzero() -> None:
    result = _evaluate("V1L", DERIVATIVE_INPUTS)
    for name, entry in result.derivatives.items():
        assert all(abs(entry[f"n_{c}"]) > 1e-12 for c in COMPONENTS), name


# -- A17-A20: the guards and the domain -----------------------------------------------------------


def _pure(component: str) -> tuple[float, ...]:
    return tuple(1.0 if c == component else 0.0 for c in COMPONENTS)


def _mixture(**flows: float) -> tuple[float, ...]:
    return tuple(flows.get(c, 0.0) for c in COMPONENTS)


V1L_FLOWS = tuple(PHASE_STATES["V1L"]["n_mol_s"])
#: Spec §5's states, written out here (not read from the reference) with their expected codes; the
#: reference's `guard_states` must name the same states and codes (the generator's claims).
GUARDS: dict[str, tuple[float, float, tuple[float, ...], str, str]] = {
    "A17_365K": (365.0, 101325.0, _pure("H2O"), "unsupported", "vapour_root_metastable"),
    "A17_385K": (385.0, 101325.0, _pure("H2O"), "ok", ""),
    "A18_H2O_300K": (300.0, 5.0e6, _pure("H2O"), "unsupported", "vapour_root_liquid_like"),
    "A18_CO2_250K": (250.0, 5.0e6, _pure("CO2"), "unsupported", "vapour_root_liquid_like"),
    "A19_330K": (
        330.0,
        1.0e5,
        _mixture(H2O=0.95, N2=0.05),
        "unsupported",
        "vapour_root_metastable",
    ),
    "A19_400K": (400.0, 1.0e5, _mixture(H2O=0.95, N2=0.05), "ok", ""),
    "A19_C3H8": (300.0, 1.5e6, _pure("C3H8"), "unsupported", "vapour_root_metastable"),
    "A20_T_low": (199.5, 5.0e6, V1L_FLOWS, "out_of_domain", "out_of_domain"),
    "A20_T_high": (1000.5, 5.0e6, V1L_FLOWS, "out_of_domain", "out_of_domain"),
    "A20_P_high": (700.0, 3.1e7, V1L_FLOWS, "out_of_domain", "out_of_domain"),
    "A20_P_low": (700.0, 9.9e3, V1L_FLOWS, "out_of_domain", "out_of_domain"),
    # Spec §12.3 (R-540, review M-1): unstable to a pure-component trial phase.
    "M1_H2O_N2_330K": (
        330.0,
        1.0e5,
        _mixture(H2O=0.6, N2=0.4),
        "unsupported",
        "vapour_unstable",
    ),
    "M1_syngas_313K": (
        313.15,
        3.0e6,
        _mixture(H2=0.45, N2=0.15, CH4=0.02, H2O=0.30, CO2=0.08),
        "unsupported",
        "vapour_unstable",
    ),
    "M1_C3H8_N2_250K": (
        250.0,
        1.0e6,
        _mixture(C3H8=0.5, N2=0.5),
        "unsupported",
        "vapour_unstable",
    ),
    # Spec §12.3 (review S-2): the liquid-like guard's mixture pair.
    "S2_CH4_C2H6_15MPa": (350.0, 1.5e7, _mixture(CH4=0.5, C2H6=0.5), "ok", ""),
    "S2_CH4_C2H6_20MPa": (
        350.0,
        2.0e7,
        _mixture(CH4=0.5, C2H6=0.5),
        "unsupported",
        "vapour_root_liquid_like",
    ),
}


def test_a17_a20_the_registered_guard_states_are_the_tests() -> None:
    assert set(GUARD_STATES) == set(GUARDS)


@pytest.mark.parametrize("gid", list(GUARDS))
def test_a17_a20_guard_and_domain_states(gid: str) -> None:
    temperature, pressure, n, status, code = GUARDS[gid]
    registered = GUARD_STATES[gid]
    assert (registered["T_K"], registered["P_Pa"], tuple(registered["n_mol_s"])) == (
        temperature,
        pressure,
        n,
    )
    assert registered["status_or_reason"] == (code or "ok")
    result = PROVIDER.evaluate_phase(
        _request(n, temperature, pressure, derivatives=DERIVATIVE_INPUTS), CONTEXT
    )
    if status == "ok":
        assert result.status == "ok", result.message
        assert result.phase_signature == "VAPOR"
    else:
        _assert_refused(result, status, code)
    if code == "vapour_unstable":
        # The 50-digit reference's most negative pure trial phase is the one the refusal names.
        component = registered["min_pure_trial_tm_component"]
        assert registered["min_pure_trial_tm"] <= -0.5
        assert result.message.startswith(f"vapour_unstable: pure-{component} trial phase"), (
            result.message
        )


def test_a17_the_bracket_straddles_prs_water_boiling_point() -> None:
    """IAPWS-95 T_b = 373.124 K; PR's (the reference's) is 374.53 K, ≥ 9.5 K from each state."""
    t_b = CLOSED["saturation"]["water_T_b_at_101325_Pa_K"]
    assert abs(t_b - 374.53) < 0.005
    assert t_b - GUARDS["A17_365K"][0] >= 9.5 and GUARDS["A17_385K"][0] - t_b >= 9.5


def test_a18_p1_is_admitted_within_the_iapws_band() -> None:
    """|Z − 0.9958| ≤ 0.002 (IAPWS-IF97 at 0.1 MPa, 500 K, †); PR gives 0.99620."""
    result = _evaluate("P1")
    assert result.status == "ok", result.message
    assert abs(result.values["Z"] - 0.9958) <= 0.002
    assert round(result.values["Z"], 5) == 0.99620


# -- A21: identities of the implementation --------------------------------------------------------


@pytest.mark.parametrize("sid", ["V1L", "V2L"])
def test_a21_homogeneity_gibbs_duhem_and_symmetry(sid: str) -> None:
    """M01.A12 as amended: J_ij = n_tot ∂ln φ_i/∂n_j, M = max |J_ij|; each identity ≤ 1e-12 M.
    Homogeneity of Z, v and h on its own row scale."""
    n = PHASE_STATES[sid]["n_mol_s"]
    total = sum(n)
    y = [value / total for value in n]
    result = _evaluate(sid, DERIVATIVE_INPUTS)
    dn = {name: [result.derivatives[name][f"n_{c}"] for c in COMPONENTS] for name in PROPERTIES}
    for name in ("Z", "v", "h"):
        terms = [nj * d for nj, d in zip(n, dn[name], strict=True)]
        assert abs(sum(terms)) <= 1e-12 * sum(abs(t) for t in terms), name
    block = [[total * value for value in dn[f"lnphi_{c}"]] for c in COMPONENTS]
    scale = max(abs(value) for row in block for value in row)
    size = len(COMPONENTS)
    for i in range(size):
        assert abs(sum(y[j] * block[i][j] for j in range(size))) <= 1e-12 * scale, ("hom", i)
    for j in range(size):
        assert abs(sum(y[i] * block[i][j] for i in range(size))) <= 1e-12 * scale, ("gd", j)
    for i in range(size):
        for j in range(size):
            assert abs(block[i][j] - block[j][i]) <= 1e-12 * scale, (i, j)


# -- request shape (M01.A50's refusals, carried over) ---------------------------------------------


def test_request_shape_refusals() -> None:
    state = PHASE_STATES["V1L"]
    n, t, p = tuple(state["n_mol_s"]), state["T_K"], state["P_Pa"]
    refusals = [
        (_request(n, t, p, derivatives=("n_NH3",)), "unsupported", "undeclared_derivative_input"),
        (_request(n, t, p, properties=("lnphi_NH3",)), "unsupported", "unknown_property"),
        (_request(n[:5], t, p), "error", "state_length"),
        (_request((0.0,) * len(COMPONENTS), t, p), "unsupported", "dormant_state"),
        (_request((-1.0, *n[1:]), t, p), "out_of_domain", "out_of_domain"),
    ]
    for request, status, code in refusals:
        _assert_refused(PROVIDER.evaluate_phase(request, CONTEXT), status, code)
