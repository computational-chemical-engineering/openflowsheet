"""K02: the SYN-001 property provider, against the independent oracle and the 20-digit references.

**What is independent of what**, stated first because it is what the assertions are worth.

`src/openflowsheet/thermo/syn001.py` and `benchmarks/syn001/oracle.py` are two *separate*
transcriptions of `docs/derivations/SYN-001.md`, which plan §3.2 requires: "Implement the oracle
separately from the production flash/recycle solver." Neither imports the other. So an agreement
between them is evidence that two independent transcriptions of one derivation agree — which
catches a transcription slip in either, and does **not** catch an error in the derivation itself.
That shared root is the limit of what this file can establish, and is why the comparisons that
carry the most weight are against `benchmarks/p02/reference_values.yaml`, computed by Fable with
mpmath at 40 digits from the derivation's closed forms with no code from either implementation.

None of this is empirical validation. SYN-001's constants are invented; the provider says so in its
own `PropertyCapabilities.data_provenance`, and that declaration is asserted here so it cannot
quietly become a claim about a real substance.
"""

from __future__ import annotations

import math

import pytest

from benchmarks.p02.reference import load_reference
from benchmarks.syn001 import oracle
from openflowsheet.compiled import EvaluationContext
from openflowsheet.thermo import (
    FlashRequest,
    PropertyProvider,
    PropertyRequest,
    StreamState,
)
from openflowsheet.thermo.syn001 import (
    COMPONENTS,
    P_REF,
    Syn001Provider,
    d_ln_k_d_pressure,
    d_ln_k_d_temperature,
    h_liquid,
    h_vapor,
    ln_k,
)

REFERENCE = load_reference()
CONTEXT = EvaluationContext(model_version="k02-provider", constants_sha256="0" * 64)

#: States spanning the registered SYN-001 variants: nominal two-phase, all-liquid and all-vapor
#: (plan §3.2 registers 310 K and 420 K as exactly those), plus interior points off the grid.
STATES = [
    (360.0, P_REF),
    (350.0, P_REF),
    (310.0, P_REF),
    (420.0, P_REF),
    (372.0, 130_000.0),
    (295.0, 60_000.0),
    (430.0, 190_000.0),
]


@pytest.fixture(scope="module")
def provider() -> Syn001Provider:
    return Syn001Provider()


def test_the_provider_satisfies_the_frozen_protocol(provider: Syn001Provider) -> None:
    assert isinstance(provider, PropertyProvider)


# -- agreement with the independent oracle -------------------------------------------------------


@pytest.mark.parametrize(("temperature", "pressure"), STATES)
def test_k_values_agree_with_the_independent_oracle(temperature: float, pressure: float) -> None:
    """Two separate transcriptions of the same derivation, neither importing the other."""
    expected = oracle.k_values(temperature, pressure)
    for index in range(len(COMPONENTS)):
        assert math.exp(ln_k(temperature, pressure, index)) == pytest.approx(
            expected[index], rel=1e-15
        )


@pytest.mark.parametrize(("temperature", "pressure"), STATES)
def test_the_flash_split_agrees_with_the_independent_oracle(
    provider: Syn001Provider, temperature: float, pressure: float
) -> None:
    state = StreamState(n=(1.0, 1.0, 1.0), temperature=temperature, pressure=pressure)
    result = provider.flash(FlashRequest(state=state), CONTEXT)
    expected = oracle.tp_flash(state.n, temperature, pressure)

    assert result.status == "ok", result.message
    assert result.vapor is not None and result.liquid is not None
    assert result.vapor_fraction == pytest.approx(expected.beta, abs=1e-13)
    for index in range(len(COMPONENTS)):
        assert result.vapor.n[index] == pytest.approx(expected.vapor[index], abs=1e-12)
        assert result.liquid.n[index] == pytest.approx(expected.liquid[index], abs=1e-12)


@pytest.mark.parametrize(("temperature", "pressure"), STATES)
def test_the_flash_closes_the_component_balance_exactly(
    provider: Syn001Provider, temperature: float, pressure: float
) -> None:
    """`n_in,i = n_vap,i + n_liq,i`. A split that does not conserve moles is not a split."""
    state = StreamState(n=(0.5, 1.0, 1.5), temperature=temperature, pressure=pressure)
    result = provider.flash(FlashRequest(state=state), CONTEXT)
    assert result.status == "ok"
    assert result.vapor is not None and result.liquid is not None
    for index in range(len(COMPONENTS)):
        closure = result.vapor.n[index] + result.liquid.n[index] - state.n[index]
        assert abs(closure) <= 1e-14 * max(1.0, state.n[index]), f"component {index}"


# -- agreement with the 20-digit references ------------------------------------------------------


@pytest.mark.parametrize("state_id", sorted(REFERENCE.states))
def test_k_values_and_derivatives_match_the_20_digit_references(state_id: str) -> None:
    """The comparison that carries the most weight: neither implementation contributed to these."""
    state = REFERENCE.states[state_id]
    raw = REFERENCE.raw["states"]
    record = next(item for item in raw if item["state_id"] == state_id)
    temperature = float(state.x_l["T"])
    pressure = float(state.x_l["P"])

    for index in range(len(COMPONENTS)):
        assert ln_k(temperature, pressure, index) == pytest.approx(
            float(record["lnK"][index]), rel=1e-15
        )
        assert d_ln_k_d_temperature(temperature, pressure, index) == pytest.approx(
            float(record["dlnK_dT_per_K"][index]), rel=1e-15
        )
        assert d_ln_k_d_pressure(temperature, pressure, index) == pytest.approx(
            float(record["dlnK_dP_per_Pa"][index]), rel=1e-15
        )
        assert h_liquid(temperature, pressure, index) == pytest.approx(
            float(record["hL_J_per_mol"][index]), rel=1e-15
        )
        assert h_vapor(temperature, index) == pytest.approx(
            float(record["hV_J_per_mol"][index]), rel=1e-15
        )


# -- ADR 0001 D3: zero flow is an answer, not an edge case ---------------------------------------


def test_a_dormant_feed_flashes_to_two_dormant_outlets(provider: Syn001Provider) -> None:
    """ADR 0001 D3.4, verbatim: two dormant outlets, zero duty, ZERO_FLOW — a valid result."""
    state = StreamState(n=(0.0, 0.0, 0.0), temperature=360.0, pressure=P_REF)
    result = provider.flash(FlashRequest(state=state), CONTEXT)

    assert result.status == "ok"
    assert result.phase_signature == "ZERO_FLOW"
    assert result.vapor is not None and result.liquid is not None
    assert result.vapor.n == result.liquid.n == (0.0, 0.0, 0.0)
    # D3.1: T and P are retained as labels even though composition is undefined.
    assert result.vapor.temperature == 360.0
    assert result.vapor.pressure == P_REF
    # An undefined vapour fraction is `None`, not 0.0 — those are different answers.
    assert result.vapor_fraction is None


def test_a_negative_zero_feed_is_dormant_too(provider: Syn001Provider) -> None:
    """ADR 0001 D3.1 says exact IEEE zero *after signed-zero normalization*."""
    state = StreamState(n=(-0.0, 0.0, -0.0), temperature=360.0, pressure=P_REF)
    assert state.is_dormant
    assert provider.flash(FlashRequest(state=state), CONTEXT).phase_signature == "ZERO_FLOW"


def test_a_tiny_but_nonzero_feed_is_not_dormant(provider: Syn001Provider) -> None:
    """The boundary is exact, not a tolerance: 1e-300 mol/s has a defined composition."""
    state = StreamState(n=(1e-300, 1e-300, 1e-300), temperature=360.0, pressure=P_REF)
    assert not state.is_dormant
    assert provider.flash(FlashRequest(state=state), CONTEXT).phase_signature == "TWO_PHASE"


def test_a_zero_component_in_a_flowing_stream_stays_zero(provider: Syn001Provider) -> None:
    """ADR 0001 D3.3: `x_i = 0` exactly, and the K-value form never evaluates `ln(0)`."""
    state = StreamState(n=(1.0, 0.0, 1.0), temperature=360.0, pressure=P_REF)
    result = provider.flash(FlashRequest(state=state), CONTEXT)
    assert result.status == "ok"
    assert result.vapor is not None and result.liquid is not None
    assert result.vapor.n[1] == 0.0
    assert result.liquid.n[1] == 0.0


# -- the declared domain is the public contract --------------------------------------------------


@pytest.mark.parametrize(
    ("temperature", "pressure"),
    [(270.0, P_REF), (450.0, P_REF), (360.0, 40_000.0), (360.0, 250_000.0)],
)
def test_outside_the_declared_domain_is_reported_not_extrapolated(
    provider: Syn001Provider, temperature: float, pressure: float
) -> None:
    """There is no `PropertyStatus` meaning "extrapolated"; leaving the domain is reported."""
    state = StreamState(n=(1.0, 1.0, 1.0), temperature=temperature, pressure=pressure)

    flashed = provider.flash(FlashRequest(state=state), CONTEXT)
    assert flashed.status == "out_of_domain"
    assert flashed.vapor is None and flashed.liquid is None and flashed.vapor_fraction is None
    assert "outside" in flashed.message

    evaluated = provider.evaluate_phase(
        PropertyRequest(state=state, phase="LIQUID", properties=("h",)), CONTEXT
    )
    assert evaluated.status == "out_of_domain"
    assert evaluated.values == {}


def test_a_non_finite_state_is_out_of_domain(provider: Syn001Provider) -> None:
    state = StreamState(n=(1.0, 1.0, 1.0), temperature=float("nan"), pressure=P_REF)
    assert provider.flash(FlashRequest(state=state), CONTEXT).status == "out_of_domain"


# -- capabilities are queried, not assumed (D08) -------------------------------------------------


def test_an_unsupported_property_is_reported_unsupported(provider: Syn001Provider) -> None:
    result = provider.evaluate_phase(
        PropertyRequest(
            state=StreamState(n=(1.0, 1.0, 1.0), temperature=360.0, pressure=P_REF),
            phase="LIQUID",
            properties=("entropy",),
        ),
        CONTEXT,
    )
    assert result.status == "unsupported"
    assert result.values == {}


def test_an_undeclared_derivative_is_unsupported_not_silently_omitted(
    provider: Syn001Provider,
) -> None:
    """The failure this guards is a caller asking for d/dn and receiving a result without it."""
    result = provider.evaluate_phase(
        PropertyRequest(
            state=StreamState(n=(1.0, 1.0, 1.0), temperature=360.0, pressure=P_REF),
            phase="LIQUID",
            properties=("h",),
            derivatives=("n_A",),
        ),
        CONTEXT,
    )
    assert result.status == "unsupported"


def test_an_unsupported_flash_specification_is_reported(provider: Syn001Provider) -> None:
    """Plan §3.2: no general PH flash in v0.0. Asking for one gets a typed refusal."""
    result = provider.flash(
        FlashRequest(
            state=StreamState(n=(1.0, 1.0, 1.0), temperature=360.0, pressure=P_REF),
            specification="PH",
        ),
        CONTEXT,
    )
    assert result.status == "unsupported"
    assert "TP" in result.message


def test_describe_declares_everything_blueprint_6_1_requires(provider: Syn001Provider) -> None:
    """The checklist, asserted rather than trusted to have been followed."""
    capabilities = provider.describe()
    assert capabilities.components == COMPONENTS
    assert capabilities.state_definition == "nTP-v1"
    assert capabilities.reference_convention == "SYN-001-ref-v1"
    assert capabilities.flashes == ("TP",)
    assert capabilities.derivative_order == {"T": 1, "P": 1}
    assert capabilities.domain["T"] == (280.0, 440.0)
    assert capabilities.thread_safety == "thread_safe"
    assert len(capabilities.numerical_limitations) >= 3
    # SYN-001 is synthetic, and the provider must keep saying so where a caller reads it.
    assert "synthetic" in capabilities.uncertainty.lower()
    assert "no experimental source" in capabilities.data_provenance.lower()


def test_implementation_and_data_hashes_are_separate_and_stable(
    provider: Syn001Provider,
) -> None:
    """Blueprint §6.4 puts both in the exact cache key, separately.

    The same code with different constants is a different provider for caching, and so is the same
    data under changed code. One combined hash could not tell those apart.
    """
    first, second = provider.describe(), Syn001Provider().describe()
    assert first.implementation_sha256 == second.implementation_sha256
    assert first.data_sha256 == second.data_sha256
    assert first.implementation_sha256 != first.data_sha256
    assert len(first.implementation_sha256) == len(first.data_sha256) == 64


# -- the phase behaviour the plan registers ------------------------------------------------------


@pytest.mark.parametrize(
    ("temperature", "expected"),
    [(310.0, "LIQUID"), (360.0, "TWO_PHASE"), (420.0, "VAPOR")],
)
def test_the_registered_phase_variants_are_reproduced(
    provider: Syn001Provider, temperature: float, expected: str
) -> None:
    """Plan §3.2 registers 310 K all-liquid and 420 K all-vapor as variants, not accidents."""
    state = StreamState(n=(1.0, 1.0, 1.0), temperature=temperature, pressure=P_REF)
    assert provider.flash(FlashRequest(state=state), CONTEXT).phase_signature == expected


def test_a_single_phase_result_has_one_dormant_outlet(provider: Syn001Provider) -> None:
    """All-liquid means the vapour outlet is dormant, with T and P retained as labels."""
    state = StreamState(n=(1.0, 1.0, 1.0), temperature=310.0, pressure=P_REF)
    result = provider.flash(FlashRequest(state=state), CONTEXT)
    assert result.vapor is not None and result.liquid is not None
    assert result.vapor.n == (0.0, 0.0, 0.0)
    assert result.vapor.is_dormant
    assert result.liquid.n == state.n
    assert result.vapor.temperature == state.temperature
    assert result.vapor_fraction == 0.0
