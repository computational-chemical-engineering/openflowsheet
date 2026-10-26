"""S10-C WO-3, gate G8: the column's admission, domain and specification-kind refusals (design note
`docs/derivations/S10C-design.md` §4.1, §4.8; specification `docs/derivations/S10C-spec.md` §5.6,
assertions S10C.A50–A56).

Every refusal is decided before any provider evaluation except the vapour-identity probe (exactly
one call). The S01 cascade keeps S03 §9 S11 unchanged (A55).
"""

from __future__ import annotations

import dataclasses
from typing import Any

import pytest
from test_s01_cascade_wo1 import CONTEXT as S01_CONTEXT
from test_s01_cascade_wo1 import REFERENCE as S01_REFERENCE
from test_s01_cascade_wo1 import _spec as s01_spec
from test_s03_s11_refusal import PROVIDERS as S03_PROVIDERS
from test_s10c_blocks import CONTEXT, REAL, column_spec

import openflowsheet.models.syn001.column as column_module
from openflowsheet.compiled import EvaluationContext
from openflowsheet.models.syn001.cascade import (
    CascadeFailure,
    InletState,
    SideFeed,
    property_method_refusal,
)
from openflowsheet.models.syn001.cascade import validate as cascade_validate
from openflowsheet.models.syn001.column import (
    GAMMA_PHI_KINDS,
    EndSpecification,
    energy_precheck,
    validate,
)
from openflowsheet.models.syn001.column_solve import solve_column
from openflowsheet.models.syn001.gamma_phi import enthalpy_flow
from openflowsheet.thermo import (
    FlashRequest,
    FlashResult,
    PropertyCapabilities,
    PropertyRequest,
    PropertyResult,
    StreamState,
)
from openflowsheet.thermo.syn001 import Syn001Provider

C_MW = column_spec("C-MW")
SYN001 = Syn001Provider()
#: The scope every identity refusal names (design note §4.1 step 1).
SCOPE = (
    "SYN-001 (provider_id 'syn001', reference_convention 'SYN-001-ref-v1') and wilson-ig-v1 "
    "(reference conventions 'WILSON-IG-ref-v1', 'S10-VER-ref-v1')"
)


class Spy:
    """Delegates to `inner`, answers `describe()` with `capabilities`, records every evaluation;
    `vapour` is added to every vapour `lnphi_<c>` value (A53's non-identity)."""

    def __init__(
        self, inner: Any, capabilities: PropertyCapabilities | None = None, vapour: float = 0.0
    ) -> None:
        self._inner = inner
        self._capabilities = capabilities or inner.describe()
        self._vapour = vapour
        self.requests: list[PropertyRequest] = []
        self.flashes = 0

    def describe(self) -> PropertyCapabilities:
        return self._capabilities

    def evaluate_phase(
        self, request: PropertyRequest, context: EvaluationContext
    ) -> PropertyResult:
        self.requests.append(request)
        result = self._inner.evaluate_phase(request, context)
        if request.phase != "VAPOR" or not self._vapour:
            return result
        values = {
            k: v + self._vapour if k.startswith("lnphi_") else v for k, v in result.values.items()
        }
        return dataclasses.replace(result, values=values)

    def flash(self, request: FlashRequest, context: EvaluationContext) -> FlashResult:
        self.flashes += 1
        return self._inner.flash(request, context)


def _identity(inner: Any, provider_id: str, convention: str) -> Spy:
    capabilities = dataclasses.replace(
        inner.describe(), provider_id=provider_id, reference_convention=convention
    )
    return Spy(inner, capabilities)


def _refused_without_evaluation(provider: Spy) -> CascadeFailure:
    """`validate` and `solve_column` on C-MW refuse identically with S11's cause and no
    evaluation; returns the refusal."""
    provider_id = provider.describe().provider_id
    refused = validate(C_MW, provider, CONTEXT)
    assert isinstance(refused, CascadeFailure)
    assert refused.outcome == "CAPABILITY_UNAVAILABLE"
    assert refused.cause == f"unsupported(column_property_method:{provider_id})"
    assert solve_column(C_MW, provider) == refused
    assert (provider.requests, provider.flashes) == ([], 0)
    return refused


# -- A50, A51: outside the allow-list --------------------------------------------------------------

NON_ADMITTED = {
    name: S03_PROVIDERS[name] for name in ("pr_c1", "pr_lib", "iapws95", "coolprop_heos")
}


@pytest.mark.parametrize("name", sorted(NON_ADMITTED))
def test_a50_a_non_admitted_provider_is_refused_by_identity(name: str) -> None:
    built = NON_ADMITTED[name]()
    refused = _refused_without_evaluation(Spy(built))
    assert SCOPE in refused.message
    assert repr(built.describe().provider_id) in refused.message


SPIES = {
    "s03-spy/SYN-001-ref-v1": lambda: _identity(SYN001, "s03-spy", "SYN-001-ref-v1"),
    "syn001/spy-ref": lambda: _identity(SYN001, "syn001", "spy-ref"),
    "wilson-ig-v1/spy-ref": lambda: _identity(REAL, "wilson-ig-v1", "spy-ref"),
}


@pytest.mark.parametrize("name", sorted(SPIES))
def test_a51_an_identity_spy_is_refused_without_evaluation(name: str) -> None:
    refused = _refused_without_evaluation(SPIES[name]())
    assert SCOPE in refused.message


# -- A52, A53: the identity without the capabilities or without ln φ^V ≡ 0 -------------------------


def test_a52_the_identity_without_lnphi_is_refused_without_evaluation() -> None:
    described = REAL.describe()
    lnphi = [f"lnphi_{c}" for c in described.components]
    spy = Spy(
        REAL,
        dataclasses.replace(
            described,
            properties=tuple(name for name in described.properties if name not in lnphi),
        ),
    )
    refused = _refused_without_evaluation(spy)
    assert (
        f"{described.provider_id} declares wilson-ig-v1's identity but not its capabilities: "
        f"missing {lnphi}"
    ) in refused.message


def test_a53_a_non_zero_vapour_lnphi_is_refused_after_exactly_one_probe() -> None:
    spy = Spy(REAL, vapour=1e-3)
    refused = validate(C_MW, spy, CONTEXT)
    assert isinstance(refused, CascadeFailure)
    assert (refused.outcome, refused.cause) == (
        "CAPABILITY_UNAVAILABLE",
        "unsupported(column_property_method:wilson-ig-v1)",
    )
    assert "vapour ln phi is not identically zero" in refused.message
    assert len(spy.requests) == 1 and spy.flashes == 0
    (request,) = spy.requests
    (t_lo, t_hi), (p_lo, p_hi) = REAL.describe().domain["T"], REAL.describe().domain["P"]
    assert request.phase == "VAPOR"
    assert request.state.n == (1.0, 1.0, 1.0)
    assert (request.state.temperature, request.state.pressure) == (
        (t_lo + t_hi) / 2.0,
        (p_lo + p_hi) / 2.0,
    )
    spy.requests.clear()
    assert solve_column(C_MW, spy) == refused and len(spy.requests) == 1


def test_the_admitted_column_passes_validation() -> None:
    """Not vacuous: C-MW with the real records is admitted (A45: its feed is admissible)."""
    assert validate(C_MW, REAL, CONTEXT) is None


# -- A54: the specification kinds ------------------------------------------------------------------

INVERSE = {
    "purity": EndSpecification("purity", 0.99, component="CH3OH"),
    "recovery": EndSpecification("recovery", 0.9, component="CH3OH"),
    "temperature": EndSpecification("temperature", 340.0, stage=1),
}


@pytest.mark.parametrize("end", ["condenser", "reboiler"])
@pytest.mark.parametrize("kind", sorted(INVERSE))
def test_a54_inverse_kinds_are_refused_before_i1(
    kind: str, end: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    def unreachable(*_: object) -> None:
        raise AssertionError("a SYN-001 closed form was reached")

    monkeypatch.setattr(column_module, "stage_band", unreachable)
    monkeypatch.setattr(column_module, "saturation_temperature", unreachable)
    given = INVERSE[kind]
    if end == "reboiler":
        given = dataclasses.replace(given, stage=C_MW.stage_count if given.stage else None)
    spec = dataclasses.replace(C_MW, **{f"{end}_spec": given})
    refused = validate(spec, REAL, CONTEXT)
    assert isinstance(refused, CascadeFailure)
    assert (refused.outcome, refused.cause) == (
        "CAPABILITY_UNAVAILABLE",
        f"unsupported(column_specification:{kind}:wilson-ig-v1)",
    )
    assert str(GAMMA_PHI_KINDS) in refused.message
    assert solve_column(spec, REAL) == refused


def test_a54_an_s_refusal_precedes_the_kind_refusal() -> None:
    """The kind rule sits after S1–S10: a feedless column is refused by S5 (the bottoms rate
    exceeds F = 0), not by the kind rule."""
    spec = dataclasses.replace(
        C_MW,
        condenser_spec=INVERSE["purity"],
        sides=(SideFeed("feed", 10, InletState((0.0, 0.0, 0.0), 348.0, 101325.0, "LIQUID")),),
    )
    refused = validate(spec, REAL, CONTEXT)
    assert refused is not None and refused.cause == "infeasible_spec(bottoms_rate_exceeds_feed)"


# -- §4.8: the provider's domain replaces SYN-001's constants --------------------------------------


def test_the_domain_checks_read_the_providers_box() -> None:
    """R3 for a composition-dependent form: inlet T outside the provider's `T` box and a stage
    pressure outside its `P` box are refused with the provider's bounds; a pressure inside the
    provider's box but outside SYN-001's (5e4 Pa) is not a domain refusal."""
    (t_lo, t_hi), (p_lo, p_hi) = REAL.describe().domain["T"], REAL.describe().domain["P"]
    feed = C_MW.sides[0]
    cold = dataclasses.replace(
        C_MW,
        sides=(
            dataclasses.replace(
                feed, state=dataclasses.replace(feed.state, temperature=t_lo - 1.0)
            ),
        ),
    )
    refused = validate(cold, REAL, CONTEXT)
    assert refused is not None and refused.cause.startswith("invalid_spec(domain:")
    assert str((t_lo, t_hi)) in refused.message
    high = dataclasses.replace(C_MW, pressures=(p_hi * 1.25,) + C_MW.pressures[1:])
    refused = validate(high, REAL, CONTEXT)
    assert refused is not None and refused.cause.startswith("invalid_spec(domain:")
    assert str((p_lo, p_hi)) in refused.message
    low = dataclasses.replace(C_MW, pressures=(4.0e4,) * C_MW.stage_count)
    refused = validate(low, REAL, CONTEXT)
    assert refused is None or "domain:" not in refused.cause


def test_r7_energy_precheck_uses_the_providers_temperature_box() -> None:
    """R7 for a duty-only column: the bounds are `n_tot h` of the feed at the provider's `T_min`
    (liquid) and `T_max` (vapour), at the bottom pressure."""
    spec = dataclasses.replace(
        C_MW,
        condenser_spec=EndSpecification("duty", -3.0e4),
        reboiler_spec=EndSpecification("duty", 3.0e4),
    )
    (t_lo, t_hi) = REAL.describe().domain["T"]
    precheck = energy_precheck(spec, REAL, CONTEXT)
    feed = spec.sides[0].state
    bottom = spec.pressures[-1]
    lower = enthalpy_flow(
        REAL, StreamState(n=feed.n, temperature=t_lo, pressure=bottom), "LIQUID", CONTEXT
    )
    upper = enthalpy_flow(
        REAL, StreamState(n=feed.n, temperature=t_hi, pressure=bottom), "VAPOR", CONTEXT
    )
    assert (precheck.lower, precheck.upper) == (lower[1], upper[1])
    assert precheck.lower < precheck.target < precheck.upper
    assert validate(spec, REAL, CONTEXT) is None


# -- A55: the S01 cascade keeps S11 ----------------------------------------------------------------


def test_a55_the_cascade_keeps_s11_for_wilson() -> None:
    c1 = s01_spec(S01_REFERENCE["cases"]["C1"])
    spy = Spy(REAL)
    refused = cascade_validate(c1, spy, S01_CONTEXT)
    assert refused == property_method_refusal(c1.unit_id, spy)
    assert isinstance(refused, CascadeFailure)
    assert refused.cause == "unsupported(column_property_method:wilson-ig-v1)"
    assert "SYN-001 only" in refused.message
    assert (spy.requests, spy.flashes) == ([], 0)
