"""K04-F9 W3–W4: the fresh flash's phase reading at `ε_adm` (D2) and the unresolved-split routing
(D3), at the function level (spec §5.2–§5.3; ADR 0013 D2–D3; X20, X21).

**D2** is `checks.enthalpy_flow`, the one function both check engines call for a fresh-flash
enthalpy. The streams are SYN-001's fresh feed composition at `P_r`, placed a registered excess
past its bubble or dew point: the band ends come from the verifier's own bisection
(`verify.saturation.band_ends`, adjacent doubles), the offset from the excess's slope, and the
excess each test asserts is recomputed with §4.7's own arithmetic, so the window is not assumed.
"The provider's value" is the flash's outlets summed as `enthalpy_flow` summed them before D2.

**D3** is `verify.saturation.split_route`, which `table.degeneracy` applies at the state it
judges. X21 routes every entry of `ref.closed_form.routing` from its registered `T`, `N` and band
ends (parsed to binary64, as a bisection to adjacent doubles delivers them), and compares the
floor ratio with the closed form of the same registered fields — the six printed digits are that
closed form rounded, which is checked too.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from decimal import ROUND_HALF_EVEN, Decimal
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest
import yaml
from t05_support import CONTEXT, PROVIDER

from openflowsheet.thermo import FlashRequest, PropertyRequest, StreamState
from openflowsheet.verify.checks import (
    ADMISSIBILITY_EPSILON,
    COMPONENTS,
    KIND_TOLERANCE,
    enthalpy_flow,
    k_values,
)
from openflowsheet.verify.saturation import (
    UNRESOLVED_FLOOR_OVER_TOLERANCE,
    band_ends,
    resolution_floor,
    split_route,
)

P_R = 1.0e5
FEED = (1.0, 1.0, 1.0)
EPS = ADMISSIBILITY_EPSILON


def _phase_value(stream: StreamState, phase: str) -> float:
    """`Σ n_i h_i^phase(T, P)`, summed as `enthalpy_flow` sums an outlet."""
    result = PROVIDER.evaluate_phase(
        PropertyRequest(state=stream, phase=phase, properties=("h",)),  # type: ignore[arg-type]
        CONTEXT,
    )
    assert result.status == "ok"
    total = 0.0
    total += sum(
        flow * result.values[f"h_{c}"] for c, flow in zip(COMPONENTS, stream.n, strict=True)
    )
    return total


def _provider_value(stream: StreamState) -> float:
    """The pre-D2 `enthalpy_flow`: the provider's flash, its outlets summed."""
    flashed = PROVIDER.flash(FlashRequest(state=stream), CONTEXT)
    assert flashed.status == "ok"
    total = 0.0
    for phase, outlet in (("VAPOR", flashed.vapor), ("LIQUID", flashed.liquid)):
        if outlet is None or outlet.is_dormant:
            continue
        result = PROVIDER.evaluate_phase(
            PropertyRequest(state=outlet, phase=phase, properties=("h",)),  # type: ignore[arg-type]
            CONTEXT,
        )
        total += sum(
            flow * result.values[f"h_{c}"] for c, flow in zip(COMPONENTS, outlet.n, strict=True)
        )
    return total


def _excesses(stream: StreamState) -> tuple[float, float]:
    """§4.7's `Σ x K − 1` and `Σ y / K − 1`, in `admissibility_checks`'s arithmetic."""
    constants = k_values(PROVIDER, stream.temperature, stream.pressure, CONTEXT)
    total = sum(stream.n)
    fractions = tuple(flow / total for flow in stream.n)
    bubble = sum(x * k for x, k in zip(fractions, constants, strict=True))
    dew = sum(y / k for y, k in zip(fractions, constants, strict=True))
    return bubble - 1.0, dew - 1.0


def _at(temperature: float, n: Sequence[float] = FEED) -> StreamState:
    return StreamState(n=tuple(n), temperature=temperature, pressure=P_R)


def _offset(end: float, excess: float, which: int, sign: float) -> StreamState:
    """The feed at `end + sign · ΔT`, `ΔT` the first-order offset for `excess` on test `which`."""
    step = 1e-6
    slope = abs(_excesses(_at(end + step))[which] - _excesses(_at(end - step))[which]) / (2 * step)
    return _at(end + sign * excess / slope)


@pytest.fixture(scope="module")
def band() -> tuple[float, float]:
    t_bubble, t_dew = band_ends(PROVIDER, FEED, P_R, CONTEXT)
    assert t_bubble is not None and t_dew is not None
    return t_bubble, t_dew


def test_x20_a_liquid_within_eps_adm_past_its_bubble_point_is_read_as_a_liquid(
    band: tuple[float, float],
) -> None:
    stream = _offset(band[0], 0.5 * EPS, 0, +1.0)
    bubble, _ = _excesses(stream)
    assert 0.0 < bubble <= EPS, bubble
    flashed = PROVIDER.flash(FlashRequest(state=stream), CONTEXT)
    assert flashed.phase_signature == "TWO_PHASE"  # the provider would split it
    liquid = _phase_value(stream, "LIQUID")
    assert enthalpy_flow(PROVIDER, stream, CONTEXT) == liquid
    assert _provider_value(stream) != liquid  # the rule acted: the kink is removed


def test_x20_a_liquid_two_eps_adm_past_its_bubble_point_is_flashed(
    band: tuple[float, float],
) -> None:
    stream = _offset(band[0], 2.0 * EPS, 0, +1.0)
    bubble, _ = _excesses(stream)
    assert 1.5 * EPS < bubble <= 3.0 * EPS, bubble
    value = enthalpy_flow(PROVIDER, stream, CONTEXT)
    assert value == _provider_value(stream)
    # ≠ the liquid value by the kink, A_L · b (spec §4.2), to first order.
    constants = k_values(PROVIDER, stream.temperature, stream.pressure, CONTEXT)
    liquid_h = PROVIDER.evaluate_phase(
        PropertyRequest(state=stream, phase="LIQUID", properties=("h",)), CONTEXT
    ).values
    vapor_h = PROVIDER.evaluate_phase(
        PropertyRequest(state=stream, phase="VAPOR", properties=("h",)), CONTEXT
    ).values
    total = sum(stream.n)
    x = [flow / total for flow in stream.n]
    amplification = (
        total
        * sum(
            xi * k * (vapor_h[f"h_{c}"] - liquid_h[f"h_{c}"])
            for xi, k, c in zip(x, constants, COMPONENTS, strict=True)
        )
        / sum(xi * (k - 1.0) ** 2 for xi, k in zip(x, constants, strict=True))
    )
    kink = value - _phase_value(stream, "LIQUID")
    assert kink == pytest.approx(amplification * bubble, rel=1e-2)


def test_x20_a_liquid_below_its_bubble_point_keeps_the_providers_value_bit_for_bit(
    band: tuple[float, float],
) -> None:
    for offset in (1.0, 1e-6, 1e-9):
        stream = _at(band[0] - offset)
        assert _excesses(stream)[0] <= 0.0
        assert PROVIDER.flash(FlashRequest(state=stream), CONTEXT).phase_signature == "LIQUID"
        assert enthalpy_flow(PROVIDER, stream, CONTEXT) == _provider_value(stream)


def test_x20_a_vapour_within_eps_adm_past_its_dew_point_is_read_as_a_vapour(
    band: tuple[float, float],
) -> None:
    stream = _offset(band[1], 0.5 * EPS, 1, -1.0)
    bubble, dew = _excesses(stream)
    assert 0.0 < dew <= EPS and bubble > EPS, (bubble, dew)
    assert PROVIDER.flash(FlashRequest(state=stream), CONTEXT).phase_signature == "TWO_PHASE"
    vapor = _phase_value(stream, "VAPOR")
    assert enthalpy_flow(PROVIDER, stream, CONTEXT) == vapor
    assert _provider_value(stream) != vapor


def test_x20_a_vapour_two_eps_adm_past_its_dew_point_is_flashed(
    band: tuple[float, float],
) -> None:
    stream = _offset(band[1], 2.0 * EPS, 1, -1.0)
    _, dew = _excesses(stream)
    assert 1.5 * EPS < dew <= 3.0 * EPS, dew
    value = enthalpy_flow(PROVIDER, stream, CONTEXT)
    assert value == _provider_value(stream)
    assert value != _phase_value(stream, "VAPOR")


def test_x20_a_vapour_above_its_dew_point_keeps_the_providers_value_bit_for_bit(
    band: tuple[float, float],
) -> None:
    for offset in (1.0, 1e-6, 1e-9):
        stream = _at(band[1] + offset)
        assert _excesses(stream)[1] <= 0.0
        assert PROVIDER.flash(FlashRequest(state=stream), CONTEXT).phase_signature == "VAPOR"
        assert enthalpy_flow(PROVIDER, stream, CONTEXT) == _provider_value(stream)


def test_x20_a_stream_inside_its_band_is_flashed_and_a_dormant_one_is_zero(
    band: tuple[float, float],
) -> None:
    stream = _at(0.5 * (band[0] + band[1]))
    assert enthalpy_flow(PROVIDER, stream, CONTEXT) == _provider_value(stream)
    dormant = _at(350.0, (0.0, 0.0, 0.0))
    value = enthalpy_flow(PROVIDER, dormant, CONTEXT)
    assert value == 0.0 and math.copysign(1.0, value) > 0


# -- D3: the routing (X21) ------------------------------------------------------------------------

K04F9_REF = yaml.safe_load(
    (
        Path(__file__).resolve().parents[1] / "benchmarks" / "k04f9" / "reference_values.yaml"
    ).read_text()
)
ROUTING = K04F9_REF["closed_form"]["routing"]
TAU_FLOW = KIND_TOLERANCE["molar_flow"]
#: Spec §7's routing row as amended (Q-S2, 2026-09-25): the floor ratio's relative tolerance is
#: `max(1e-6, 4 ulp(T)/w)`. Each band end is a double adjacent to the exact end, so `w` is off by
#: `<= 2 ulp(T)`; the tolerance keeps a margin of 2 on that quantization bound by construction —
#: 1.06e-2 at NP-1 (a 2.14e-11 K band, 377 doubles at 360 K), 1e-6 at every other entry.
FLOOR_RELATIVE = Fraction(1, 10**6)
#: NP-1's measured relative error (171130.3 against the exact 171213; W4, *measured*).
NP1_FLOOR_ERROR = 4.8e-4


def _exact_floor(entry: dict[str, Any]) -> Fraction:
    """`N ulp(T) / (w τ_flow)` from the registered 20-digit `T`, `N`, `T_b`, `T_d`, exactly
    (`ulp` at the double nearest `T`, as the implementation reads it)."""
    width = Fraction(entry["T_dew_K"]) - Fraction(entry["T_bubble_K"])
    return (
        Fraction(entry["N_mol_per_s"])
        * Fraction(math.ulp(float(entry["T_K"])))
        / (width * Fraction(TAU_FLOW))
    )


def _floor_tolerance(entry: dict[str, Any]) -> Fraction:
    """`max(1e-6, 4 ulp(T)/w)`, relative (`ulp` at the double nearest `T`, `w` from the registered
    20-digit band ends)."""
    width = Fraction(entry["T_dew_K"]) - Fraction(entry["T_bubble_K"])
    return max(FLOOR_RELATIVE, 4 * Fraction(math.ulp(float(entry["T_K"]))) / width)


def _six_digits(value: Fraction) -> Decimal:
    """`value` rounded to six significant digits (spec §9's printing)."""
    exact = Decimal(value.numerator) / Decimal(value.denominator)
    return exact.quantize(Decimal(1).scaleb(exact.adjusted() - 5), rounding=ROUND_HALF_EVEN)


def _route(entry: dict[str, Any], *, two_phase: bool = True) -> tuple[str, float | None]:
    ends = [
        None if entry.get(key) is None else float(entry[key]) for key in ("T_bubble_K", "T_dew_K")
    ]
    return split_route(
        float(entry["T_K"]),
        float(entry["N_mol_per_s"]),
        ends[0],
        ends[1],
        two_phase=two_phase,
        flow_tolerance=TAU_FLOW,
    )


@pytest.mark.parametrize("key", sorted(ROUTING))
def test_x21_every_registered_split_and_stream_is_routed_as_registered(key: str) -> None:
    entry = ROUTING[key]
    route, floor = _route(entry)
    assert route == entry["route"]
    assert (floor is not None) == bool(entry["inside_band"])
    if not entry["inside_band"]:
        assert entry["floor_over_tau_flow"] is None
        return
    assert floor is not None
    registered = entry["floor_over_tau_flow"]
    if registered == "inf":  # a zero-width band: SC-1…SC-3, pure B at T_sat
        assert math.isinf(floor) and Fraction(entry["width_K"]) == 0
        return
    # The registered six digits are the exact closed form rounded (spec §9's printing).
    exact = _exact_floor(entry)
    assert Decimal(registered) == _six_digits(exact), (float(exact), registered)
    assert abs(Fraction(floor) - exact) <= _floor_tolerance(entry) * exact, (floor, float(exact))


def test_x21_np1_its_floor_is_held_at_its_quantization_floor() -> None:
    """NP-1 (Q-S2): its tolerance is 4 ulp(T)/w = 1.06e-2, and its relative error from binary64
    band ends is the measured 4.8e-4 (recorded; 22x inside)."""
    entry = ROUTING["NP-1:U-PHF.S1"]
    assert float(_floor_tolerance(entry)) == pytest.approx(1.06e-2, rel=5e-3)
    _, floor = _route(entry)
    assert floor is not None
    exact = _exact_floor(entry)
    relative = float(abs(Fraction(floor) - exact) / exact)
    assert relative == pytest.approx(NP1_FLOOR_ERROR, rel=5e-2), relative


def test_x21_the_routing_margins() -> None:
    """NP-G unresolved 8.9x over the 1/10 threshold, NP-3 resolved 5.8x under it; only a
    two-phase stored branch is routed unresolved (a single-phase one inside its band is the
    fresh flash's to judge, and fails its bubble or dew check by the band's excess)."""
    route, floor = _route(ROUTING["NP-G:U-PHF.S1"])
    assert route == "unresolved" and floor is not None and floor / 0.1 > 8.8
    assert _route(ROUTING["NP-G:U-PHF.S1"], two_phase=False)[0] == "resolved"
    route, floor = _route(ROUTING["NP-3:U-PHF.S1"])
    assert route == "resolved" and floor is not None and 0.1 / floor > 5.8
    assert UNRESOLVED_FLOOR_OVER_TOLERANCE == 0.1


def test_x21_a_pure_stream_off_saturation_is_outside_its_zero_width_band() -> None:
    """INJ-B2′: pure B 2e-5 K above `T_sat` is neither degenerate nor unresolved — its
    temperature lies outside its band — so the fresh flash judges it (spec §5.3)."""
    entry = ROUTING["INJ-B2':S2"]
    t_bubble, t_dew = band_ends(PROVIDER, (0.0, 2.0, 0.0), P_R, CONTEXT)
    assert t_bubble is not None and t_dew is not None
    assert t_bubble == t_dew  # a pure component's band has zero width
    assert split_route(
        float(entry["T_K"]), 2.0, t_bubble, t_dew, two_phase=True, flow_tolerance=TAU_FLOW
    ) == ("resolved", None)
    assert resolution_floor(2.0, 360.0, 0.0, TAU_FLOW) == math.inf
