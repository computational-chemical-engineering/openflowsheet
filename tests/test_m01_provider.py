"""M01.A03-A14, A35, A36, A50: the provider `pr-c1-v1` against its closed forms (spec §4, §5.2-5.4).

The expectations are `benchmarks/m01/reference_values.yaml` → `closed_form`, written at 50 digits
by `docs/derivations/scripts/m01_reference.py` (whose `--check` is M01.A34) and never imported by
the provider: two transcriptions of spec §4, one in mpmath and one in double. The tolerances are
spec §9's, each >= 1e3 above the measured double floor (`measured.transcription_floor`, <= 4.1e-16)
and >= 1e3 below the smallest defect worth catching.
"""

from __future__ import annotations

import ast
import hashlib
import math
import tomllib
from collections.abc import Mapping
from typing import Any

import pytest
from conftest import REPO_ROOT, load_yaml

from openflowsheet.compiled import EvaluationContext
from openflowsheet.thermo import (
    FlashRequest,
    FlashResult,
    PropertyProvider,
    PropertyRequest,
    PropertyResult,
    StreamState,
)
from openflowsheet.thermo.cache import ExactPropertyCache
from openflowsheet.thermo.pr_c1 import (
    COMPONENTS,
    DERIVATIVE_INPUTS,
    PROPERTIES,
    PrC1Provider,
    cp_ig,
    h_ig,
    load_records,
    parameters,
    real_roots,
)

REFERENCE = load_yaml(REPO_ROOT / "benchmarks" / "m01" / "reference_values.yaml")
CLOSED = REFERENCE["closed_form"]
PHASE_STATES: Mapping[str, Any] = CLOSED["phase_states"]
EVALUATED = [sid for sid, state in PHASE_STATES.items() if state["status_or_reason"] == "ok"]
REFUSED = [sid for sid, state in PHASE_STATES.items() if state["status_or_reason"] != "ok"]
CONTEXT = EvaluationContext(model_version="m01-provider", constants_sha256="0" * 64)
PROVIDER = PrC1Provider()


def _rel(value: float, expected: float) -> float:
    """Spec §9's "rel": |impl − ref| / max(|ref|, 1) for dimensionless and J/mol quantities."""
    return abs(value - expected) / max(abs(expected), 1.0)


def _state(sid: str) -> StreamState:
    state = PHASE_STATES[sid]
    return StreamState(n=tuple(state["n_mol_s"]), temperature=state["T_K"], pressure=state["P_Pa"])


def _evaluate(sid: str, properties: tuple[str, ...], derivatives: tuple[str, ...] = ()) -> Any:
    request = PropertyRequest(
        state=_state(sid),
        phase=PHASE_STATES[sid]["phase"],
        properties=properties,
        derivatives=derivatives,
    )
    return PROVIDER.evaluate_phase(request, CONTEXT)


# -- A03, A04: identity and declaration -----------------------------------------------------------


def test_a04_describe_declares_exactly_the_registered_surface() -> None:
    described = PROVIDER.describe()
    assert isinstance(PROVIDER, PropertyProvider)
    assert described.provider_id == "pr-c1-v1"
    assert described.reference_convention == "PR-C1-ref-v1"
    assert described.state_definition == "nTP-v1"
    assert described.components == ("H2", "N2", "NH3", "Ar", "CH4")
    assert described.phases == ("LIQUID", "VAPOR")
    assert set(described.properties) >= {"h", "Z", "v", *(f"lnphi_{c}" for c in COMPONENTS)}
    assert described.flashes == ("TP",)
    assert dict(described.derivative_order) == {
        "T": 1,
        "P": 1,
        "n_H2": 1,
        "n_N2": 1,
        "n_NH3": 1,
        "n_Ar": 1,
        "n_CH4": 1,
    }
    assert dict(described.domain) == {"T": (200.0, 1000.0), "P": (1e4, 3e7)}
    assert described.thread_safety == "thread_safe"


def test_a03_identity_hashes_are_the_records_bytes_and_the_modules_source() -> None:
    described = PROVIDER.describe()
    records = REPO_ROOT / "benchmarks" / "m01" / "components.yaml"
    module = REPO_ROOT / "src" / "openflowsheet" / "thermo" / "pr_c1.py"
    assert described.data_sha256 == hashlib.sha256(records.read_bytes()).hexdigest()
    assert described.implementation_sha256 == hashlib.sha256(module.read_bytes()).hexdigest()
    assert REFERENCE["components_yaml_sha256"] == described.data_sha256


def test_a03_the_providers_parameters_are_the_records_values_bitwise() -> None:
    document = load_yaml(REPO_ROOT / "benchmarks" / "m01" / "components.yaml")
    par = parameters()
    for index, record in enumerate(document["components"]):
        values = record["parameters"]
        assert (
            par.critical_temperature[index].hex() == values["critical_temperature"]["value"].hex()
        )
        assert par.formation_enthalpy[index].hex() == (
            values["standard_formation_enthalpy"]["value"].hex()
        )
        assert [b.hex() for b in par.cp_coefficients[index]] == [
            values[f"ideal_gas_cp_b{k}"]["value"].hex() for k in range(5)
        ]
        loaded = load_records().components[index]
        assert loaded.critical_pressure.hex() == values["critical_pressure"]["value"].hex()
        assert loaded.acentric_factor.hex() == values["acentric_factor"]["value"].hex()


# -- A05, A06: parameters and the ideal gas -------------------------------------------------------


@pytest.mark.parametrize("index", range(5), ids=COMPONENTS)
def test_a05_kappa_a_c_b_per_component(index: int) -> None:
    expected = CLOSED["components"][COMPONENTS[index]]
    par = parameters()
    assert _rel(par.kappa[index], expected["kappa"]) <= 1e-14
    assert abs(par.a_c[index] / expected["a_c_Pa_m6_per_mol2"] - 1.0) <= 1e-14
    assert abs(par.b[index] / expected["b_m3_per_mol"] - 1.0) <= 1e-14


def test_a05_nh3_eos_critical_point() -> None:
    expected = CLOSED["nh3_eos_critical"]
    par = parameters()
    assert abs(par.nh3_critical_temperature / expected["T_K"] - 1.0) <= 1e-13
    assert abs(par.nh3_critical_pressure / expected["P_Pa"] - 1.0) <= 1e-13
    assert abs(par.nh3_critical_volume / expected["v_m3_per_mol"] - 1.0) <= 1e-13
    assert par.nh3_critical_temperature < expected["T_c_record_K"]


@pytest.mark.parametrize("index", range(5), ids=COMPONENTS)
def test_a06_ideal_gas_heat_capacity_and_enthalpy(index: int) -> None:
    expected = CLOSED["components"][COMPONENTS[index]]
    assert _rel(cp_ig(298.15, index), expected["cp_ig_298_15"]) <= 1e-12
    assert _rel(cp_ig(700.0, index), expected["cp_ig_700"]) <= 1e-12
    assert _rel(h_ig(268.15, index), expected["h_ig_268_15"]) <= 1e-12
    assert _rel(h_ig(700.0, index), expected["h_ig_700"]) <= 1e-12
    assert abs(h_ig(298.15, index) - parameters().formation_enthalpy[index]) <= 1e-9


# -- A07-A09: phase values, roots, labels ---------------------------------------------------------


@pytest.mark.parametrize("sid", EVALUATED)
def test_a07_phase_state_values(sid: str) -> None:
    expected = PHASE_STATES[sid]["values"]
    result = _evaluate(sid, tuple(expected))
    assert result.status == "ok", result.message
    assert result.phase_signature == PHASE_STATES[sid]["phase"]
    for name, value in expected.items():
        if name == "v":
            assert abs(result.values[name] / value - 1.0) <= 1e-12, name
        else:
            assert _rel(result.values[name], value) <= 1e-12, name


@pytest.mark.parametrize("sid", EVALUATED)
def test_a08_root_counts_equal_the_references(sid: str) -> None:
    state = PHASE_STATES[sid]
    roots = real_roots(state["T_K"], state["P_Pa"], state["n_mol_s"])
    assert len(roots) == state["real_root_count"]


def test_a08_the_three_root_state_gives_the_smallest_and_largest_root() -> None:
    liquid, vapour = _evaluate("L2", ("Z",)), _evaluate("V3", ("Z",))
    roots = real_roots(350.0, 1e6, (0.0, 0.0, 1.0, 0.0, 0.0))
    assert len(roots) == 3
    assert liquid.values["Z"] == roots[0] and vapour.values["Z"] == roots[-1]
    assert liquid.values["Z"] != vapour.values["Z"]
    assert _rel(liquid.values["Z"], PHASE_STATES["L2"]["values"]["Z"]) <= 1e-12
    assert _rel(vapour.values["Z"], PHASE_STATES["V3"]["values"]["Z"]) <= 1e-12


def test_a08_l1_is_a_single_liquid_like_root_and_v4_the_single_supercritical_one() -> None:
    (z_l1,) = real_roots(268.15, 1e7, (0.0, 0.0, 1.0, 0.0, 0.0))
    assert _evaluate("L1", ("Z",)).values["Z"] == z_l1
    assert _evaluate("L1", ("v",)).values["v"] < parameters().nh3_critical_volume
    (z_v4,) = real_roots(420.0, 5e6, (0.0, 0.0, 1.0, 0.0, 0.0))
    assert 420.0 > parameters().nh3_critical_temperature
    assert _evaluate("V4", ("Z",)).values["Z"] == z_v4


@pytest.mark.parametrize("sid", ["V1", "V2"])
def test_a09_five_lnphi_pairwise_distinct_and_nonzero(sid: str) -> None:
    values = _evaluate(sid, tuple(f"lnphi_{c}" for c in COMPONENTS)).values
    lnphi = list(values.values())
    assert all(value != 0.0 for value in lnphi)
    gaps = [abs(a - b) for i, a in enumerate(lnphi) for b in lnphi[i + 1 :]]
    # Spec §9.2 A09 as amended (Amendment 1): the smallest pairwise gap is at least 1e6 times A07's
    # tolerance 1e-12, so a permuted component index fails A07; the generator's PH-GAP holds the
    # same of the reference (V1's H2/CH4 gap 4.35e-4 is the smallest, assertion_margins).
    assert min(gaps) >= 1e6 * 1e-12


@pytest.mark.parametrize("sid", EVALUATED)
def test_a09_every_departure_enthalpy_exceeds_one_joule(sid: str) -> None:
    state = PHASE_STATES[sid]
    h = _evaluate(sid, ("h",)).values["h"]
    total = sum(state["n_mol_s"])
    if state["phase"] == "LIQUID":
        ideal = h_ig(state["T_K"], 2)
    else:
        ideal = sum(n / total * h_ig(state["T_K"], i) for i, n in enumerate(state["n_mol_s"]))
    assert abs(h - ideal) > 1.0
    assert _rel(h - ideal, state["h_departure_J_mol"]) <= 1e-11


# -- A10-A13: derivatives -------------------------------------------------------------------------


@pytest.mark.parametrize("sid", list(CLOSED["derivatives"]))
def test_a10_derivatives_match_the_50_digit_reference(sid: str) -> None:
    expected = CLOSED["derivatives"][sid]
    result = _evaluate(sid, tuple(expected), DERIVATIVE_INPUTS)
    assert result.status == "ok", result.message
    state = PHASE_STATES[sid]
    scale = {"T": state["T_K"], "P": state["P_Pa"]}
    total = sum(state["n_mol_s"])
    for name, by_input in expected.items():
        value = result.values[name]
        for wanted, reference in by_input.items():
            s = scale.get(wanted, total)
            got = result.derivatives[name][wanted]
            bound = 1e-9 * max(abs(value), 1.0, abs(s * reference))
            assert abs(s * got - s * reference) <= bound, (name, wanted)


def test_a11_liquid_n_derivatives_are_exactly_zero_and_vapour_ones_are_not() -> None:
    liquid = _evaluate("L1", ("h", "Z", "v", "lnphi_NH3"), DERIVATIVE_INPUTS)
    for entry in liquid.derivatives.values():
        assert all(entry[f"n_{c}"] == 0.0 for c in COMPONENTS)
    for sid in ("V1", "V2"):
        vapour = _evaluate(sid, PROPERTIES, DERIVATIVE_INPUTS)
        for name, entry in vapour.derivatives.items():
            assert all(abs(entry[f"n_{c}"]) > 1e-12 for c in COMPONENTS), name


@pytest.mark.parametrize("sid", ["V1", "V2"])
def test_a12_homogeneity_gibbs_duhem_and_symmetry_of_the_implementation(sid: str) -> None:
    """Spec §9.3 A12 as amended (Amendment 1): the lnphi block's three identities on one scale.

    J_ij = n_tot d lnphi_i/d n_j and M = max |J_ij|. Homogeneity of Z, v and h keeps its own row
    scale; the lnphi rows (homogeneity), the columns (Gibbs-Duhem) and the pairs (symmetry) are
    bounded by 1e-12 M, the scale their roundoff is made at (measured <= 3.8e-16 M at 13bcef7).
    """
    n = PHASE_STATES[sid]["n_mol_s"]
    total = sum(n)
    y = [value / total for value in n]
    result = _evaluate(sid, PROPERTIES, DERIVATIVE_INPUTS)
    dn = {name: [result.derivatives[name][f"n_{c}"] for c in COMPONENTS] for name in PROPERTIES}
    for name in ("Z", "v", "h"):
        terms = [nj * d for nj, d in zip(n, dn[name], strict=True)]
        assert abs(sum(terms)) <= 1e-12 * sum(abs(t) for t in terms), name
    block = [[total * value for value in dn[f"lnphi_{c}"]] for c in COMPONENTS]
    scale = max(abs(value) for row in block for value in row)
    for i in range(5):
        assert abs(sum(y[j] * block[i][j] for j in range(5))) <= 1e-12 * scale, ("hom", i)
    for j in range(5):
        assert abs(sum(y[i] * block[i][j] for i in range(5))) <= 1e-12 * scale, ("gd", j)
    for i in range(5):
        for j in range(5):
            assert abs(block[i][j] - block[j][i]) <= 1e-12 * scale, (i, j)


@pytest.mark.parametrize("wanted", ["n_H2O", "x_NH3", "T2"])
def test_a13_an_undeclared_derivative_input_is_unsupported(wanted: str) -> None:
    result = _evaluate("V1", ("h",), ("T", wanted))
    assert result.status == "unsupported"
    assert result.message == f"undeclared_derivative_input: {wanted}"
    assert result.values == {} and result.derivatives == {}


# -- A14: refusals --------------------------------------------------------------------------------


@pytest.mark.parametrize("sid", REFUSED)
def test_a14_registered_refusals(sid: str) -> None:
    reason = PHASE_STATES[sid]["status_or_reason"]
    result = _evaluate(sid, ("h", "Z"))
    if reason == "out_of_domain":
        assert result.status == "out_of_domain"
    else:
        assert result.status == "unsupported"
    assert result.message.startswith(f"{reason}:"), result.message
    assert result.values == {} and result.derivatives == {} and result.phase_signature is None


@pytest.mark.parametrize("phase", ["LIQUID", "VAPOR"])
def test_a14_a_dormant_state_is_refused(phase: str) -> None:
    request = PropertyRequest(
        state=StreamState(n=(0.0, -0.0, 0.0, 0.0, 0.0), temperature=300.0, pressure=1e6),
        phase=phase,  # type: ignore[arg-type]
        properties=("h",),
    )
    result = PROVIDER.evaluate_phase(request, CONTEXT)
    assert result.status == "unsupported"
    assert result.message == "dormant_state: composition undefined"
    assert result.values == {}


def test_a14_a_liquid_asked_for_a_light_gas_lnphi_is_refused() -> None:
    result = _evaluate("L1", ("h", "lnphi_H2"))
    assert result.status == "unsupported"
    assert result.message.startswith("light_gas_in_liquid:")
    assert result.values == {}


@pytest.mark.parametrize(
    ("n", "temperature", "pressure"),
    [
        ((0.7, 0.235, 0.03, 0.015, 0.02), math.nan, 1e7),
        ((0.7, 0.235, 0.03, 0.015, 0.02), 1000.0000000000001, 1e7),
        ((0.7, 0.235, 0.03, 0.015, 0.02), 673.15, 9999.999999999998),
        ((0.7, -0.235, 0.03, 0.015, 0.02), 673.15, 1e7),
        ((0.7, 0.235, math.inf, 0.015, 0.02), 673.15, 1e7),
    ],
)
def test_outside_the_domain_or_the_state_space_is_out_of_domain(
    n: tuple[float, ...], temperature: float, pressure: float
) -> None:
    request = PropertyRequest(
        state=StreamState(n=n, temperature=temperature, pressure=pressure),
        phase="VAPOR",
        properties=("h",),
    )
    result = PROVIDER.evaluate_phase(request, CONTEXT)
    assert result.status == "out_of_domain"
    assert result.message.startswith("out_of_domain:")
    assert result.values == {}


def test_the_domain_bounds_are_inclusive() -> None:
    for temperature, pressure in ((200.0, 1e4), (1000.0, 3e7)):
        request = PropertyRequest(
            state=StreamState(
                n=(0.7, 0.235, 0.03, 0.015, 0.02), temperature=temperature, pressure=pressure
            ),
            phase="VAPOR",
            properties=("h",),
        )
        assert PROVIDER.evaluate_phase(request, CONTEXT).status == "ok"


# -- A50: request checks (Amendment 1, spec §5.3, §5.4 step 0) -------------------------------------

V1 = _state("V1")
F1_STATE = CLOSED["flash_states"]["F1"]
F1 = StreamState(
    n=tuple(F1_STATE["n_mol_s"]), temperature=F1_STATE["T_K"], pressure=F1_STATE["P_Pa"]
)
#: One defect each: V1's T and P with one flow too few or too many; V1 with one bad coordinate.
SHORT_OR_LONG = {"4_flows": V1.n[:4], "6_flows": (*V1.n, 0.0)}
OUTSIDE = {
    "n_N2_negative": StreamState(
        n=(0.7, -0.235, 0.03, 0.015, 0.02), temperature=673.15, pressure=1e7
    ),
    "n_NH3_inf": StreamState(
        n=(0.7, 0.235, math.inf, 0.015, 0.02), temperature=673.15, pressure=1e7
    ),
    "T_nan": StreamState(n=V1.n, temperature=math.nan, pressure=V1.pressure),
}


def _phase_refusal(result: PropertyResult, status: str, prefix: str) -> None:
    assert result.status == status, result.message
    assert result.message.startswith(f"{prefix}:"), result.message
    assert result.phase_signature is None
    assert result.values == {} and result.derivatives == {}


def _flash_refusal(result: FlashResult, status: str, prefix: str) -> None:
    assert result.status == status, result.message
    assert result.message.startswith(f"{prefix}:"), result.message
    assert result.phase_signature is None and result.vapor_fraction is None
    assert result.vapor is None and result.liquid is None
    assert result.k_values == {}


def test_a50_the_states_have_one_defect_each() -> None:
    assert V1.n == (0.7, 0.235, 0.03, 0.015, 0.02) and (V1.temperature, V1.pressure) == (
        673.15,
        1e7,
    )
    assert PHASE_STATES["V1"]["phase"] == "VAPOR"
    for state in OUTSIDE.values():
        assert len(state.n) == len(COMPONENTS)
        defects = [i for i, (a, b) in enumerate(zip(state.n, V1.n, strict=True)) if a != b]
        defects += ["T"] if not state.temperature == V1.temperature else []
        defects += ["P"] if state.pressure != V1.pressure else []
        assert len(defects) == 1, defects


def test_a50_an_unknown_property_is_unsupported() -> None:
    request = PropertyRequest(state=V1, phase="VAPOR", properties=("h", "s"))
    _phase_refusal(PROVIDER.evaluate_phase(request, CONTEXT), "unsupported", "unknown_property")


@pytest.mark.parametrize("case", sorted(SHORT_OR_LONG))
def test_a50_a_wrong_state_length_is_an_error_in_either_method(case: str) -> None:
    state = StreamState(n=SHORT_OR_LONG[case], temperature=V1.temperature, pressure=V1.pressure)
    request = PropertyRequest(state=state, phase="VAPOR", properties=("h",))
    _phase_refusal(PROVIDER.evaluate_phase(request, CONTEXT), "error", "state_length")
    _flash_refusal(PROVIDER.flash(FlashRequest(state=state), CONTEXT), "error", "state_length")


@pytest.mark.parametrize("case", sorted(OUTSIDE))
def test_a50_a_negative_or_non_finite_coordinate_is_out_of_domain_in_either_method(
    case: str,
) -> None:
    state = OUTSIDE[case]
    request = PropertyRequest(state=state, phase="VAPOR", properties=("h",))
    _phase_refusal(PROVIDER.evaluate_phase(request, CONTEXT), "out_of_domain", "out_of_domain")
    _flash_refusal(
        PROVIDER.flash(FlashRequest(state=state), CONTEXT), "out_of_domain", "out_of_domain"
    )


def test_a50_a_ph_flash_is_unsupported() -> None:
    result = PROVIDER.flash(FlashRequest(state=F1, specification="PH"), CONTEXT)
    _flash_refusal(result, "unsupported", "unsupported_specification")


def test_a50_flash_derivatives_are_refused_not_ignored() -> None:
    assert PROVIDER.flash(FlashRequest(state=F1), CONTEXT).phase_signature == "TWO_PHASE"
    result = PROVIDER.flash(FlashRequest(state=F1, derivatives=("T",)), CONTEXT)
    _flash_refusal(result, "unsupported", "flash_derivatives_unsupported")


def test_a50_the_derivatives_check_follows_the_specification_and_precedes_the_state_length() -> (
    None
):
    # WO-8 item 1: after the specification check, before the state-length check.
    both = FlashRequest(state=F1, specification="PH", derivatives=("T",))
    _flash_refusal(PROVIDER.flash(both, CONTEXT), "unsupported", "unsupported_specification")
    short = StreamState(n=F1.n[:4], temperature=F1.temperature, pressure=F1.pressure)
    result = PROVIDER.flash(FlashRequest(state=short, derivatives=("T",)), CONTEXT)
    _flash_refusal(result, "unsupported", "flash_derivatives_unsupported")


# -- A35, A36: no new runtime dependency; exact caching -------------------------------------------

FORBIDDEN = {"chemicals", "thermo", "CoolProp", "cantera", "mpmath"}


def test_a35_no_runtime_import_of_the_retrieval_or_reference_tools() -> None:
    found = []
    for path in sorted((REPO_ROOT / "src" / "openflowsheet").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names = [node.module]
            found += [
                f"{path.relative_to(REPO_ROOT)}: {name}"
                for name in names
                if name.split(".")[0] in FORBIDDEN
            ]
    assert found == []


def test_a35_the_runtime_dependencies_are_unchanged() -> None:
    project = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert project["dependencies"] == [
        "numpy==2.2.4",
        "scipy==1.15.3",
        "pyyaml==6.0.2",
        "jsonschema==4.26.0",
        "casadi==3.8.0",
    ]


def test_a36_one_ulp_in_t_is_a_different_key_and_both_evaluate() -> None:
    cached = ExactPropertyCache(PROVIDER)
    described = cached.describe()
    assert described.implementation_sha256 and described.data_sha256
    state = _state("V1")
    nudged = StreamState(
        n=state.n, temperature=math.nextafter(state.temperature, math.inf), pressure=state.pressure
    )
    requests = [
        PropertyRequest(state=s, phase="VAPOR", properties=("h",)) for s in (state, nudged, state)
    ]
    first, second, third = (cached.evaluate_phase(r, CONTEXT) for r in requests)
    assert cached.counters.provider_calls == 2
    assert cached.counters.cache_hits == 1
    assert first is third and first.values["h"] != second.values["h"]
