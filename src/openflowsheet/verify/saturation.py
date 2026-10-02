"""The verifier's own bubble and dew temperatures, and its degeneracy test (T05b spec §4.4, §9.1).

R-016 for T05b (spec §9.5): the verifier judges whether a stream's phase fractions are a function
of its `(n, T, P)` at the registered temperature resolution by code of its own — no kernel, no
row builder, no unit-layer band (`models/syn001/saturation_band.py` is the solver's). It reads a
fresh provider's `lnK` and nothing else.

It needs only the band's two ends, so it bisects the two classical functions, not the family
`g(T; β)` the unit layer carries:

    bubble(T) = Σ_{i: n_i > 0} z_i K_i(T) − 1,      dew(T) = 1 − Σ_{i: n_i > 0} z_i / K_i(T),

both increasing in `T` on SYN-001's domain (every `∂ ln K_i/∂T > 0`), with roots `T_b` and `T_d`.
They are `g(T; 0)` and `g(T; 1)` of spec §4.1 rearranged, so the roots agree with the unit layer's
up to the last bits of each bisection's final bracket (B05: within 1e-10 K; both reach adjacent
doubles, a few 1e-14 K). The stopping rule is spec §5.2's: an exact zero or adjacent doubles, the
end with the smaller `|f|` (the lower on a tie), at most 200 evaluations with the two ends.

A root outside the domain means the stream has no band end there, so it is not degenerate
(`δ = inf`). A provider refusal or an exhausted bisection raises `SaturationError`; what a
check reports then is the check's to decide (W4), never a silent "not degenerate".
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from typing import Final, Literal

from openflowsheet.compiled import EvaluationContext
from openflowsheet.thermo import PropertyProvider, PropertyRequest, PropertyStatus, StreamState
from openflowsheet.verify import NEAR_THRESHOLD_MARGIN
from openflowsheet.verify.checks import KIND_TOLERANCE

__all__ = [
    "BISECTION_BUDGET",
    "UNRESOLVED_FLOOR_OVER_TOLERANCE",
    "Route",
    "SaturationError",
    "band_distance",
    "band_ends",
    "degeneracy_distance",
    "is_temperature_degenerate",
    "resolution_floor",
    "saturation_closure",
    "split_route",
]

#: Spec §5.2 (and T05 §4.4 step 4): evaluations per bisection, the two domain ends included.
BISECTION_BUDGET: Final = 200


class SaturationError(Exception):
    """The provider refused `lnK` inside the search, or a bisection did not close."""

    def __init__(self, status: PropertyStatus, message: str) -> None:
        super().__init__(message)
        self.status: PropertyStatus = status
        self.message = message


def _ln_k(
    provider: PropertyProvider,
    flows: tuple[float, ...],
    temperature: float,
    pressure: float,
    context: EvaluationContext,
) -> dict[str, float]:
    result = provider.evaluate_phase(
        PropertyRequest(
            state=StreamState(n=flows, temperature=temperature, pressure=pressure),
            phase="LIQUID",
            properties=("lnK",),
        ),
        context,
    )
    if result.status != "ok":
        raise SaturationError(result.status, f"lnK at {temperature!r} K: {result.message}")
    return dict(result.values)


def _root(
    function: Callable[[float], float], low: float, high: float, *, clamp: bool = False
) -> float | None:
    """The root of an increasing `function` on `[low, high]`, or `None` when it has none there —
    with `clamp`, the domain end on the root's side instead (the sign of `function` at the end
    says which: positive at `low` puts the root below it, negative at `high` above it)."""
    f_low = function(low)
    if f_low > 0.0:
        return low if clamp else None
    f_high = function(high)
    if f_high < 0.0:
        return high if clamp else None
    spent = 2
    if f_low == 0.0:
        return low
    if f_high == 0.0:
        return high
    while True:
        middle = low + 0.5 * (high - low)
        if not low < middle < high:
            return high if abs(f_high) < abs(f_low) else low
        if spent >= BISECTION_BUDGET:
            raise SaturationError(
                "not_converged", f"bisection did not close in {BISECTION_BUDGET} evaluations"
            )
        f_middle = function(middle)
        spent += 1
        if f_middle == 0.0:
            return middle
        if f_middle < 0.0:
            low, f_low = middle, f_middle
        else:
            high, f_high = middle, f_middle


def band_ends(
    provider: PropertyProvider,
    flows: Sequence[float],
    pressure: float,
    context: EvaluationContext,
) -> tuple[float | None, float | None]:
    """`(T_b, T_d)` of a flowing `n` at `P` on the provider's domain; `None` for an end off it."""
    bubble, dew, (t_min, t_max) = _band_functions(provider, flows, pressure, context)
    return _root(bubble, t_min, t_max), _root(dew, t_min, t_max)


def _band_functions(
    provider: PropertyProvider,
    flows: Sequence[float],
    pressure: float,
    context: EvaluationContext,
) -> tuple[Callable[[float], float], Callable[[float], float], tuple[float, float]]:
    """The classical `bubble(T)` and `dew(T)` of a flowing `n` at `P`, and the domain in `T`."""
    n = tuple(float(value) for value in flows)
    total = sum(n)
    if not total > 0.0:
        raise ValueError("a dormant stream has no bubble or dew temperature")
    capabilities = provider.describe()
    names = capabilities.components
    flowing = [(names[index], value / total) for index, value in enumerate(n) if value > 0.0]
    t_min, t_max = capabilities.domain["T"]

    def bubble(temperature: float) -> float:
        ln_k = _ln_k(provider, n, temperature, pressure, context)
        return sum(z * math.exp(ln_k[f"lnK_{name}"]) for name, z in flowing) - 1.0

    def dew(temperature: float) -> float:
        ln_k = _ln_k(provider, n, temperature, pressure, context)
        return 1.0 - sum(z / math.exp(ln_k[f"lnK_{name}"]) for name, z in flowing)

    return bubble, dew, (t_min, t_max)


def saturation_closure(
    provider: PropertyProvider,
    vapor: Sequence[float],
    liquid: Sequence[float],
    temperature: float,
    pressure: float,
    context: EvaluationContext,
) -> float:
    """T06 spec §8.8's two-phase closure `max(|T − T_b(l, P)|, |T − T_d(v, P)|)` in kelvin: the
    liquid product's bubble temperature and the vapour product's dew temperature, each the same
    double `band_ends` gives for that end (one bisection per phase, not two).

    At an equilibrium split `y = K x`, so `Σ K x = Σ y = 1` and `Σ y/K = Σ x = 1`: both ends are
    `T`. An end off the domain is the domain end on its side, so the value is then a lower bound
    on the true distance. Both phases must flow (`ValueError` otherwise); a provider refusal or
    an exhausted bisection raises `SaturationError`."""
    bubble, _, (t_min, t_max) = _band_functions(provider, liquid, pressure, context)
    _, dew, _ = _band_functions(provider, vapor, pressure, context)
    t_bubble = _root(bubble, t_min, t_max, clamp=True)
    t_dew = _root(dew, t_min, t_max, clamp=True)
    assert t_bubble is not None and t_dew is not None  # clamped: always an end
    return max(abs(temperature - t_bubble), abs(temperature - t_dew))


def degeneracy_distance(
    provider: PropertyProvider,
    flows: Sequence[float],
    temperature: float,
    pressure: float,
    context: EvaluationContext,
) -> float:
    """`δ = max(|T − T_b|, |T − T_d|)`, `inf` when either end lies off the domain (spec §4.4)."""
    t_bubble, t_dew = band_ends(provider, flows, pressure, context)
    return band_distance(temperature, t_bubble, t_dew)


def band_distance(temperature: float, t_bubble: float | None, t_dew: float | None) -> float:
    """`δ` from the band's two ends: `max(|T − T_b|, |T − T_d|)`, `inf` for an end off the
    domain."""
    if t_bubble is None or t_dew is None:
        return math.inf
    return max(abs(temperature - t_bubble), abs(temperature - t_dew))


def is_temperature_degenerate(distance: float) -> bool:
    """Within the registered temperature tolerance of both band ends (spec §4.4, `τ_T`)."""
    return distance <= KIND_TOLERANCE["temperature"]


#: ADR 0013 D3: ADR 0007 D2.4's margin — a fresh flash whose floor reaches a tenth of the
#: tolerance its answer is judged at cannot resolve the split. No new constant (K04-F9 §5.3).
UNRESOLVED_FLOOR_OVER_TOLERANCE: Final = 1.0 / NEAR_THRESHOLD_MARGIN

Route = Literal["degenerate", "unresolved", "resolved"]


def resolution_floor(
    total_flow: float, temperature: float, width: float, flow_tolerance: float
) -> float:
    """ADR 0013 D3: `N · ulp(T) / (w · τ_flow)` — how far one ulp of the temperature a fresh flash
    is given moves its vapour flow across a band of width `w` (mean slope `N/w`), in units of
    the tolerance the flow is judged at (K04-F9 spec §4.3). A zero-width band is unresolvable."""
    if width == 0.0:
        return math.inf
    return total_flow * math.ulp(temperature) / (width * flow_tolerance)


def split_route(
    temperature: float,
    total_flow: float,
    t_bubble: float | None,
    t_dew: float | None,
    *,
    two_phase: bool,
    flow_tolerance: float,
) -> tuple[Route, float | None]:
    """How the verifier judges a flowing lifted split at `temperature` with feed band
    `[T_b, T_d]` (K04-F9 spec §5.3), and its resolution floor over `τ_flow` when its temperature
    lies inside the band (`None` otherwise):

    - `"degenerate"` — within `τ_T` of both band ends (ADR 0012 D7, which keeps precedence);
    - `"unresolved"` — its stored branch two-phase (`two_phase`), its temperature inside the
      band, and the floor at least a tenth of `τ_flow` (ADR 0013 D3);
    - `"resolved"` — otherwise: the fresh flash judges it.

    `flow_tolerance` is the routing tolerance ρ_flow = max(τ_flow(policy), τ_flow(registered))
    (`checks.routing_tolerances`, ADR 0013 Amendment 2), never a tighter policy's own τ_flow: the
    route decides which checks exist, and a tightened policy must not remove one."""
    inside = t_bubble is not None and t_dew is not None and t_bubble <= temperature <= t_dew
    floor = (
        resolution_floor(total_flow, temperature, t_dew - t_bubble, flow_tolerance)
        if inside and t_bubble is not None and t_dew is not None
        else None
    )
    if is_temperature_degenerate(band_distance(temperature, t_bubble, t_dew)):
        return "degenerate", floor
    if two_phase and floor is not None and floor >= UNRESOLVED_FLOOR_OVER_TOLERANCE:
        return "unresolved", floor
    return "resolved", floor
