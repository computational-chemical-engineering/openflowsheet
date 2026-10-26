"""S10-C WO-1: the γ–φ-IG primitives — the constant-β point, the incipient liquid and `ln_k`
(design note `docs/derivations/S10C-design.md` §4.2–§4.4; ADR 0049 D2–D3).

Expectations are never the code's own output:

- **the ideal limit** (Λ ≡ 1: γ ≡ 1, K_i = P_i^sat(T)/P): `T_b` from `Σ z_i P_i^sat(T) = P`, `T_d`
  from `Σ z_i/P_i^sat(T) = 1/P`, an intermediate β from the temperature form of Rachford–Rice, each
  solved by bisection *in this file* from the record file's DIPPR-101 coefficients;
- **one component**: `T_sat` from `ln P^sat(T) = ln P`, solved the same way, at every β;
- **the fixed point**: `x_i = z_i/D_i`, `g = 0` and `Σ K_i x_i = 1`, re-evaluated through the
  provider's `evaluate_phase` at the returned `(T, x)`;
- **the dew point** against the provider's own `stability(state, "VAPOR")`, a separate search;
- **positions** against the provider's stability verdicts at the domain ends, or against the
  closed-form `T_sat` of a pure component.

The records are S10's synthetic verification set (plus two synthetic variants written here: Λ ≡ 1,
and a narrowed T domain) and the real methanol–ethanol–water records; nothing here is evidence about
a real mixture beyond what S10 already registered.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import pytest
import yaml
from conftest import REPO_ROOT
from test_s10_flash import NEAR_AZEOTROPE

from openflowsheet.compiled import EvaluationContext
from openflowsheet.models.syn001 import gamma_phi
from openflowsheet.models.syn001.gamma_phi import (
    DELTA_BETA,
    band_point,
    incipient_liquid,
    ln_k,
)
from openflowsheet.models.syn001.saturation_band import BandError, band_temperature
from openflowsheet.thermo import PropertyRequest, StreamState
from openflowsheet.thermo.wilson_ig import WilsonIdealGasProvider

CONTEXT = EvaluationContext(model_version="S10C-WO1@" + "0" * 64, constants_sha256="0" * 64)
VERIFICATION = REPO_ROOT / "benchmarks" / "s10" / "verification-records.yaml"
REAL = REPO_ROOT / "benchmarks" / "s10" / "records.yaml"
P_ATM = 101325.0
BETAS = (0.0, 0.1, 0.5, 0.9, 1.0)
#: G3's tolerances (design note §6): temperature and composition against an independent root.
TOL_T = 1.0e-9
TOL_X = 1.0e-10
#: The fixed point's residuals at the stop: the stop bounds |Δ ln K| by DELTA_BETA = 1e-13, so
#: x and g agree with their re-evaluation to that order; 10x headroom.
TOL_FIXED_POINT = 1.0e-12
#: G3: |tm(T_d)| at the dew point.
TOL_TM = 1.0e-12


# -- record files and closed forms (independent of the provider's code) ---------------------------


def _document(path: Path) -> dict[str, Any]:
    document = yaml.safe_load(path.read_text("utf-8"))
    assert isinstance(document, dict)
    return document


def _write(document: dict[str, Any], path: Path) -> Path:
    path.write_text(yaml.safe_dump(document, sort_keys=False), "utf-8")
    return path


def _ln_psat(document: dict[str, Any]) -> list[Callable[[float], float]]:
    """ln(P_i^sat/Pa) = a + b/θ + c ln θ + d θ², θ = T/1000 K (S10 spec eq. 3.3), from the file."""

    def one(record: dict[str, Any]) -> Callable[[float], float]:
        a, b, c, d = (float(record["parameters"][f"vapour_pressure_{k}"]["value"]) for k in "abcd")

        def ln_psat(temperature: float) -> float:
            theta = temperature / 1000.0
            return a + b / theta + c * math.log(theta) + d * theta * theta

        return ln_psat

    return [one(record) for record in document["components"]]


def _bisect(f: Callable[[float], float], lo: float, hi: float) -> float:
    """The root of an increasing `f` on `[lo, hi]`, to adjacent doubles."""
    f_lo, f_hi = f(lo), f(hi)
    assert f_lo < 0.0 < f_hi, (lo, f_lo, hi, f_hi)
    while True:
        mid = 0.5 * (lo + hi)
        if mid in (lo, hi):
            return lo if abs(f_lo) <= abs(f_hi) else hi
        value = f(mid)
        if value == 0.0:
            return mid
        if value < 0.0:
            lo, f_lo = mid, value
        else:
            hi, f_hi = mid, value


def _ideal_root(
    ln_psat: Sequence[Callable[[float], float]],
    z: Sequence[float],
    pressure: float,
    beta: float,
    domain: tuple[float, float],
) -> tuple[float, tuple[float, ...]]:
    """`(T, x)` of Raoult's law at β: Σ z_i (K_i − 1)/(1 + β (K_i − 1)) = 0, K_i = P_i^sat/P."""

    def k(temperature: float) -> list[float]:
        return [math.exp(f(temperature)) / pressure for f in ln_psat]

    def g(temperature: float) -> float:
        if beta == 0.0:  # Σ z_i P_i^sat = P
            return math.fsum(zi * ki for zi, ki in zip(z, k(temperature), strict=True)) - 1.0
        if beta == 1.0:  # Σ z_i/P_i^sat = 1/P
            return 1.0 - math.fsum(zi / ki for zi, ki in zip(z, k(temperature), strict=True) if zi)
        return math.fsum(
            zi * (ki - 1.0) / (1.0 + beta * (ki - 1.0))
            for zi, ki in zip(z, k(temperature), strict=True)
        )

    temperature = _bisect(g, *domain)
    raw = [zi / (1.0 + beta * (ki - 1.0)) for zi, ki in zip(z, k(temperature), strict=True)]
    total = math.fsum(raw)
    return temperature, tuple(value / total for value in raw)


@pytest.fixture(scope="module")
def verification() -> WilsonIdealGasProvider:
    return WilsonIdealGasProvider(VERIFICATION)


@pytest.fixture(scope="module")
def real() -> WilsonIdealGasProvider:
    return WilsonIdealGasProvider(REAL)


@pytest.fixture(scope="module")
def ideal_records(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The verification records with every Λ_ij = 1.0: γ ≡ 1, Raoult's law."""
    document = _document(VERIFICATION)
    for entry in document["wilson_lambda"]:
        entry["value"] = 1.0
    return _write(document, tmp_path_factory.mktemp("ideal") / "ideal-records.yaml")


def _lnphi_liquid(
    provider: WilsonIdealGasProvider, temperature: float, pressure: float, x: Sequence[float]
) -> list[float]:
    components = provider.describe().components
    result = provider.evaluate_phase(
        PropertyRequest(
            state=StreamState(n=tuple(x), temperature=temperature, pressure=pressure),
            phase="LIQUID",
            properties=tuple(f"lnphi_{c}" for c in components),
        ),
        CONTEXT,
    )
    assert result.status == "ok", result.message
    return [result.values[f"lnphi_{c}"] for c in components]


# -- the ideal limit and one component ------------------------------------------------------------


@pytest.mark.parametrize("flows", [(0.3, 0.3, 0.4), (0.5, 0.5, 0.0), (0.0, 0.2, 0.8)])
@pytest.mark.parametrize("beta", [0.0, 0.5, 1.0])
def test_the_ideal_limit_is_raoults_law(
    ideal_records: Path, flows: tuple[float, ...], beta: float
) -> None:
    """Λ ≡ 1: `T_b`, `T_d` and the β = 0.5 point equal Raoult's law's roots solved here (G3)."""
    provider = WilsonIdealGasProvider(ideal_records)
    document = _document(ideal_records)
    domain = provider.describe().domain["T"]
    total = sum(flows)
    z = [value / total for value in flows]
    t_ref, x_ref = _ideal_root(_ln_psat(document), z, P_ATM, beta, domain)
    point = band_point(provider, flows, P_ATM, beta, CONTEXT)
    assert point.position == "inside"
    assert point.temperature is not None
    assert abs(point.temperature - t_ref) <= TOL_T, (point.temperature, t_ref)
    assert max(abs(a - b) for a, b in zip(point.liquid, x_ref, strict=True)) <= TOL_X
    for i, flow in enumerate(flows):
        if flow == 0.0:
            assert point.liquid[i] == 0.0


@pytest.mark.parametrize("records", ["verification", "real"])
@pytest.mark.parametrize("component", [0, 1, 2])
@pytest.mark.parametrize("beta", BETAS)
def test_one_flowing_component_is_its_saturation_temperature_at_every_beta(
    records: str, component: int, beta: float, request: pytest.FixtureRequest
) -> None:
    """`x = e_c` (γ_c = 1 exactly), so `g = 0` ⇔ `ln P_c^sat(T) = ln P` for every β (§4.3)."""
    provider: WilsonIdealGasProvider = request.getfixturevalue(records)
    path = VERIFICATION if records == "verification" else REAL
    ln_psat = _ln_psat(_document(path))[component]
    domain = provider.describe().domain["T"]
    t_sat = _bisect(lambda t: ln_psat(t) - math.log(P_ATM), *domain)
    flows = tuple(2.5 if i == component else 0.0 for i in range(3))
    point = band_point(provider, flows, P_ATM, beta, CONTEXT)
    assert point.position == "inside"
    assert point.temperature is not None
    assert abs(point.temperature - t_sat) <= TOL_T, (point.temperature, t_sat)
    assert point.liquid == tuple(1.0 if i == component else 0.0 for i in range(3))


# -- the fixed point ------------------------------------------------------------------------------

FEEDS = (
    (0.5, 0.5, 0.0),
    (0.0, 0.3, 0.7),
    (0.2, 0.3, 0.5),
    (0.0, 0.9, 0.1),
    (1.0e-10, 1.0, 0.0),
    (3.0, 1.0, 2.0),
)


def _assert_fixed_point(
    provider: WilsonIdealGasProvider,
    flows: Sequence[float],
    pressure: float,
    beta: float,
) -> tuple[float, tuple[float, ...]]:
    point = band_point(provider, flows, pressure, beta, CONTEXT)
    assert point.position == "inside"
    assert point.temperature is not None
    temperature, x = point.temperature, point.liquid
    total = sum(flows)
    z = [value / total for value in flows]
    flowing = [i for i, value in enumerate(z) if value > 0.0]
    assert math.fsum(x) == pytest.approx(1.0, abs=1e-15)
    assert all(x[i] == 0.0 for i in range(len(z)) if i not in flowing)
    k = [math.exp(value) for value in _lnphi_liquid(provider, temperature, pressure, x)]
    d = {i: 1.0 + beta * (k[i] - 1.0) for i in flowing}
    for i in flowing:
        assert abs(x[i] - z[i] / d[i]) <= TOL_FIXED_POINT * x[i], (i, x[i], z[i] / d[i])
    g = math.fsum(z[i] * (k[i] - 1.0) / d[i] for i in flowing)
    assert abs(g) <= TOL_FIXED_POINT, g
    assert abs(math.fsum(k[i] * x[i] for i in flowing) - 1.0) <= TOL_FIXED_POINT
    # k_values: the K that produced x (S10 §5.4 4(c)), consistent with the re-evaluation.
    for i in flowing:
        assert abs(math.log(point.k_values[i]) - math.log(k[i])) <= DELTA_BETA
    return temperature, x


@pytest.mark.parametrize("records", ["verification", "real"])
@pytest.mark.parametrize("flows", FEEDS)
@pytest.mark.parametrize("beta", BETAS)
def test_the_band_point_is_a_fixed_point(
    records: str, flows: tuple[float, ...], beta: float, request: pytest.FixtureRequest
) -> None:
    """At the stop, `x_i = z_i/D_i(K(T, x))` on F, `g(T; x) = 0` and `Σ K_i x_i = 1` (§4.3)."""
    provider: WilsonIdealGasProvider = request.getfixturevalue(records)
    _assert_fixed_point(provider, flows, P_ATM, beta)


@pytest.mark.parametrize("flows", sorted({n for n, _ in NEAR_AZEOTROPE}))
def test_the_e2_states_lie_inside_their_constant_beta_band(
    verification: WilsonIdealGasProvider, flows: tuple[float, float]
) -> None:
    """At the 13 E-2 states (S10 Amendment 1, `test_s10_flash.NEAR_AZEOTROPE`) both trials are
    unstable, so each state's T lies strictly inside `[T_b, T_d]`; every band point there is a
    fixed point (M-b: the iteration has no E-2 floor)."""
    n = (0.0, *flows)
    bubble, _ = _assert_fixed_point(verification, n, P_ATM, 0.0)
    dew, _ = _assert_fixed_point(verification, n, P_ATM, 1.0)
    middle, _ = _assert_fixed_point(verification, n, P_ATM, 0.5)
    assert bubble < middle < dew
    for state_flows, temperature in NEAR_AZEOTROPE:
        if state_flows == flows:
            assert bubble < temperature < dew


@pytest.mark.parametrize("records", ["verification", "real"])
@pytest.mark.parametrize("flows", FEEDS)
def test_the_dew_point_is_the_liquid_trials_zero(
    records: str, flows: tuple[float, ...], request: pytest.FixtureRequest
) -> None:
    """`band_point(β = 1)` against the provider's own liquid trial: `|tm(T_d)| ≤ 1e-12` (G3)."""
    provider: WilsonIdealGasProvider = request.getfixturevalue(records)
    point = band_point(provider, flows, P_ATM, 1.0, CONTEXT)
    assert point.temperature is not None
    state = StreamState(n=flows, temperature=point.temperature, pressure=P_ATM)
    report = provider.stability(state, "VAPOR", CONTEXT)
    tm = report.tm["LIQUID"]
    assert tm is not None, report.reason
    assert abs(tm) <= TOL_TM, tm


# -- positions ------------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def narrow(tmp_path_factory: pytest.TempPathFactory) -> WilsonIdealGasProvider:
    """The verification records on T ∈ [340, 360] K: VA boils below it, VC above it at 1 atm."""
    document = _document(VERIFICATION)
    document["domain"]["T"] = [340.0, 360.0]
    path = _write(document, tmp_path_factory.mktemp("narrow") / "narrow-records.yaml")
    return WilsonIdealGasProvider(path)


@pytest.mark.parametrize("beta", BETAS)
def test_a_pure_component_off_the_domain_reports_its_side(
    narrow: WilsonIdealGasProvider, beta: float
) -> None:
    """VA's and VC's closed-form `T_sat` lie below and above the domain: `below`, `above`, with no
    temperature (the `BandTemperature` contract), at every β."""
    ln_psat = _ln_psat(_document(VERIFICATION))
    t_sat = [_bisect(lambda t, f=f: f(t) - math.log(P_ATM), 300.0, 420.0) for f in ln_psat]
    assert t_sat[0] < 340.0 < t_sat[1] < 360.0 < t_sat[2]
    for flows, side in (((1.0, 0.0, 0.0), "below"), ((0.0, 0.0, 1.0), "above")):
        point = band_point(narrow, flows, P_ATM, beta, CONTEXT)
        assert point.position == side
        assert point.temperature is None and point.k_values == () and point.liquid == ()
        assert point.evaluations > 0


@pytest.mark.parametrize(
    ("flows", "verdicts"),
    [
        ((0.9, 0.1, 0.0), (True, False)),
        ((0.9, 0.0, 0.1), (True, False)),
        ((0.6, 0.0, 0.4), (False, False)),
        ((0.0, 0.2, 0.8), (False, True)),
    ],
)
def test_a_mixture_band_end_off_the_domain_reports_its_side(
    narrow: WilsonIdealGasProvider, flows: tuple[float, ...], verdicts: tuple[bool, bool]
) -> None:
    """The provider's stability verdicts decide the side: a liquid unstable at `T_min` puts the
    bubble point below the domain; a vapour unstable at `T_max` puts the dew point above it.
    `verdicts` (liquid unstable at `T_min`, vapour unstable at `T_max`) only pins that the feeds
    cover both sides and the inside; the expectation is the provider's stability search."""
    t_min, t_max = narrow.describe().domain["T"]
    at_min = StreamState(n=flows, temperature=t_min, pressure=P_ATM)
    at_max = StreamState(n=flows, temperature=t_max, pressure=P_ATM)
    liquid_report = narrow.stability(at_min, "LIQUID", CONTEXT)
    vapour_report = narrow.stability(at_max, "VAPOR", CONTEXT)
    bubble = band_point(narrow, flows, P_ATM, 0.0, CONTEXT)
    dew = band_point(narrow, flows, P_ATM, 1.0, CONTEXT)
    assert (liquid_report.label == "UNSTABLE", vapour_report.label == "UNSTABLE") == verdicts
    assert (bubble.position == "below") == (liquid_report.label == "UNSTABLE")
    assert (dew.position == "above") == (vapour_report.label == "UNSTABLE")
    if bubble.position == "inside":
        assert bubble.temperature is not None and t_min <= bubble.temperature <= t_max
    if dew.position == "inside":
        assert dew.temperature is not None and t_min <= dew.temperature <= t_max


# -- the incipient liquid -------------------------------------------------------------------------


@pytest.mark.parametrize("flows", [(0.2, 0.3, 0.5), (0.0, 0.9, 0.1), (0.5, 0.5, 0.0)])
def test_the_incipient_liquid_is_the_providers_liquid_trial(
    verification: WilsonIdealGasProvider, flows: tuple[float, ...]
) -> None:
    """`ΣW = 1` at `T_d`; above it `ΣW < 1` (stable vapour), below it `ΣW > 1`; `w` is the
    provider's liquid-trial composition (§4.4, S10 §5.4 step 3)."""
    dew = band_point(verification, flows, P_ATM, 1.0, CONTEXT)
    assert dew.temperature is not None
    total, _ = incipient_liquid(verification, dew.temperature, P_ATM, flows, CONTEXT)
    assert abs(total - 1.0) <= TOL_FIXED_POINT
    for offset, stable in ((+2.0, True), (-0.5, False)):
        temperature = dew.temperature + offset
        total, w = incipient_liquid(verification, temperature, P_ATM, flows, CONTEXT)
        assert (total <= 1.0) is stable
        state = StreamState(n=flows, temperature=temperature, pressure=P_ATM)
        report = verification.stability(state, "VAPOR", CONTEXT)
        assert report.trial_composition is not None
        assert max(abs(a - b) for a, b in zip(w, report.trial_composition, strict=True)) <= 1e-12
        assert (report.label == "STABLE_WITHIN_TESTED_SCOPE") is stable


# -- ln_k and the dispatch of band_temperature ----------------------------------------------------


def test_ln_k_is_the_providers_liquid_ln_phi_bitwise(verification: WilsonIdealGasProvider) -> None:
    x = (0.2, 0.3, 0.5)
    components = verification.describe().components
    inputs = ("T", *(f"n_{c}" for c in components))
    values, d_t, d_n = ln_k(verification, 350.0, P_ATM, x, CONTEXT, derivatives=inputs)
    direct = verification.evaluate_phase(
        PropertyRequest(
            state=StreamState(n=x, temperature=350.0, pressure=P_ATM),
            phase="LIQUID",
            properties=tuple(f"lnphi_{c}" for c in components),
            derivatives=inputs,
        ),
        CONTEXT,
    )
    for i, c in enumerate(components):
        assert values[i] == direct.values[f"lnphi_{c}"]
        assert d_t[i] == direct.derivatives[f"lnphi_{c}"]["T"]
        assert d_n[i] == tuple(direct.derivatives[f"lnphi_{c}"][f"n_{o}"] for o in components)
    assert ln_k(verification, 350.0, P_ATM, x, CONTEXT)[1:] == ((), ())


def test_ln_k_refuses_a_dormant_liquid_a_partial_request_and_types_a_provider_refusal(
    verification: WilsonIdealGasProvider,
) -> None:
    with pytest.raises(ValueError, match="dormant"):
        ln_k(verification, 350.0, P_ATM, (0.0, 0.0, 0.0), CONTEXT)
    with pytest.raises(ValueError, match="all of"):
        ln_k(verification, 350.0, P_ATM, (0.2, 0.3, 0.5), CONTEXT, derivatives=("n_VA",))
    with pytest.raises(BandError) as refused:
        ln_k(verification, 500.0, P_ATM, (0.2, 0.3, 0.5), CONTEXT)
    assert refused.value.status == "out_of_domain"


def test_band_temperature_dispatches_to_the_constant_beta_point(
    verification: WilsonIdealGasProvider,
) -> None:
    """`saturation_band.band_temperature` answers a γ–φ-IG provider by `band_point` (§4.12)."""
    for beta in (0.0, 0.5, 1.0):
        assert band_temperature(verification, (0.2, 0.3, 0.5), P_ATM, beta, CONTEXT) == (
            band_point(verification, (0.2, 0.3, 0.5), P_ATM, beta, CONTEXT)
        )


def test_an_exhausted_iteration_is_typed_not_converged(
    verification: WilsonIdealGasProvider, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(gamma_phi, "BETA_SS_MAX", 2)
    with pytest.raises(BandError) as failed:
        band_point(verification, (0.2, 0.3, 0.5), P_ATM, 0.5, CONTEXT)
    assert failed.value.status == "not_converged"
    with pytest.raises(BandError) as exhausted:
        band_point(verification, (0.2, 0.3, 0.5), P_ATM, 0.0, CONTEXT, budget=2)
    assert exhausted.value.status == "not_converged"
