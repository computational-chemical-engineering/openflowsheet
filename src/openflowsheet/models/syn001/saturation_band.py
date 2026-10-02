"""The saturation band: `T(β)`, its ends, its split, and the degeneracy test (T05b spec §4).

ADR 0012 D1's one primitive. For a flowing `n` at pressure `P` the **temperature form of
Rachford–Rice** is

    g(T; β) = Σ_{i: n_i > 0} z_i (K_i(T) − 1) / (1 + β (K_i(T) − 1)),   β ∈ [0, 1],

increasing in `T` on SYN-001's domain for every `β` (spec §4.2), so its root `T(β)` is unique when
it lies in the domain and bisection finds it. The band is `[T_b, T_d] = [T(0), T(1)]`; the split
at `β` is `v_i = n_i β K_i / D_i`, `l_i = n_i (1 − β) / D_i`, `D_i = 1 + β (K_i − 1)` — products and
quotients of nonnegatives, so no subtraction can make a flow negative, and an absent component's
flows are exactly `0.0`.

Unit layer. It asks the provider for `lnK` only (one `evaluate_phase` per evaluation of `g`), so
`thermo/syn001.py` is untouched; enthalpies are the caller's (the kernel's band route sums them
with `tp_state.enthalpy_flow`), which keeps this module importable by `tp_state` itself (T05b W3).
The verifier has its own implementation, sharing none of this code (R-016;
`verify/saturation.py`).

**Failures are typed, never values.** A provider refusal inside a search, or a bisection that
exhausts its budget, raises `BandError` with the provider's status (`not_converged` for the
budget); the caller maps it to its own registered code. A root outside the domain is not a
failure: `T(β)` reports where it lies (`below` or `above`), which the band route uses as its sign
oracle (spec §5.2) and the degeneracy test as "not degenerate".
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final, Literal

from openflowsheet.compiled import EvaluationContext
from openflowsheet.models.syn001 import TEMPERATURE_TOLERANCE
from openflowsheet.models.syn001.bisection import bracketed_root
from openflowsheet.thermo import PropertyProvider, PropertyRequest, PropertyStatus, StreamState

__all__ = [
    "MAX_TEMPERATURE_EVALUATIONS",
    "PRESCREEN_MARGIN",
    "BandError",
    "BandTemperature",
    "band_split",
    "band_temperature",
    "degeneracy_distance",
    "is_temperature_degenerate",
    "outside_the_degeneracy_window",
    "rachford_rice",
]

#: Spec §5.2: at most this many evaluations of `g` per `T(β)`, the two ends included; T05 §4.4
#: step 4's budget. Bisection on the SYN-001 domain reaches adjacent doubles in about 50.
MAX_TEMPERATURE_EVALUATIONS: Final = 200

#: T05b W6: where `outside_the_degeneracy_window` evaluates `g`, `T ∓ 2 τ_T`.
PRESCREEN_MARGIN: Final = 2.0 * TEMPERATURE_TOLERANCE

Position = Literal["inside", "below", "above"]


class BandError(Exception):
    """A provider refusal inside a band search, or an exhausted bisection (`not_converged`)."""

    def __init__(self, status: PropertyStatus, message: str) -> None:
        super().__init__(message)
        self.status: PropertyStatus = status
        self.message = message


@dataclass(frozen=True)
class BandTemperature:
    """`T(β)`, or where it lies when it is outside the domain.

    `inside`: `temperature` is the bisection's answer and `k_values` the provider's `K_i` there
    (one per declared component, in the provider's order); `below` / `above`: no temperature.
    """

    position: Position
    temperature: float | None = None
    k_values: tuple[float, ...] = ()
    #: Evaluations of `g` spent, the two domain ends included.
    evaluations: int = 0


def rachford_rice(flows: Sequence[float], k_values: Sequence[float], beta: float) -> float:
    """`g(T; β)` from the `K_i` at `T`, over the flowing components in declaration order."""
    total = sum(flows)
    value = 0.0
    for flow, k in zip(flows, k_values, strict=True):
        if flow > 0.0:
            value += (flow / total) * (k - 1.0) / (1.0 + beta * (k - 1.0))
    return value


def _k_values(
    provider: PropertyProvider,
    flows: tuple[float, ...],
    temperature: float,
    pressure: float,
    components: tuple[str, ...],
    context: EvaluationContext,
) -> tuple[float, ...]:
    result = provider.evaluate_phase(
        PropertyRequest(
            state=StreamState(n=flows, temperature=temperature, pressure=pressure),
            phase="LIQUID",
            properties=("lnK",),
        ),
        context,
    )
    if result.status != "ok":
        raise BandError(result.status, f"lnK at T = {temperature!r} K: {result.message}")
    return tuple(math.exp(result.values[f"lnK_{name}"]) for name in components)


def band_temperature(
    provider: PropertyProvider,
    flows: Sequence[float],
    pressure: float,
    beta: float,
    context: EvaluationContext,
    *,
    budget: int = MAX_TEMPERATURE_EVALUATIONS,
) -> BandTemperature:
    """`T(β)` by bisection on `[T_min, T_max]` (spec §5.2's first bullet).

    `g(T_min) > 0` → `below`; `g(T_max) < 0` → `above`; else T05 §4.4 step 4's rule: stop at
    `g = 0` exactly or adjacent doubles, return the end with the smaller `|g|`, the lower on a
    tie. Exhausting `budget` raises `BandError("not_converged", …)`.
    """
    n = tuple(float(value) for value in flows)
    if not any(value > 0.0 for value in n):
        raise ValueError("the saturation band is for a flowing stream; a dormant one has none")
    capabilities = provider.describe()
    components = capabilities.components
    if len(n) != len(components):
        raise ValueError(
            f"stream carries {len(n)} component flows; the provider declares {len(components)}"
        )
    t_min, t_max = capabilities.domain["T"]

    def g(temperature: float) -> tuple[float, tuple[float, ...]]:
        k = _k_values(provider, n, temperature, pressure, components, context)
        return rachford_rice(n, k, beta), k

    g_lo, k_lo = g(t_min)
    if g_lo > 0.0:
        return BandTemperature("below", evaluations=1)
    g_hi, k_hi = g(t_max)
    if g_hi < 0.0:
        return BandTemperature("above", evaluations=2)
    root = bracketed_root(g, (t_min, g_lo, k_lo), (t_max, g_hi, k_hi), evaluations=2, budget=budget)
    if not root.converged:
        raise BandError(
            "not_converged",
            f"the T(beta = {beta!r}) bisection did not close in {budget} evaluations",
        )
    return BandTemperature("inside", root.point, root.payload, root.evaluations)


def band_split(
    flows: Sequence[float], k_values: Sequence[float], beta: float
) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """`(v, l)` at `β` from the `K_i` at `T(β)` (spec §4.1); an absent component is `0.0, 0.0`."""
    vapor: list[float] = []
    liquid: list[float] = []
    for flow, k in zip(flows, k_values, strict=True):
        if flow == 0.0:
            vapor.append(0.0)
            liquid.append(0.0)
            continue
        denominator = 1.0 + beta * (k - 1.0)
        vapor.append(flow * beta * k / denominator)
        liquid.append(flow * (1.0 - beta) / denominator)
    return tuple(vapor), tuple(liquid)


def degeneracy_distance(
    provider: PropertyProvider,
    flows: Sequence[float],
    temperature: float,
    pressure: float,
    context: EvaluationContext,
) -> float:
    """`δ = max(|T − T_b|, |T − T_d|)` (spec §4.4), `inf` when either band end is off the domain."""
    bubble = band_temperature(provider, flows, pressure, 0.0, context)
    dew = band_temperature(provider, flows, pressure, 1.0, context)
    if bubble.temperature is None or dew.temperature is None:
        return math.inf
    return max(abs(temperature - bubble.temperature), abs(temperature - dew.temperature))


def outside_the_degeneracy_window(
    provider: PropertyProvider,
    flows: Sequence[float],
    temperature: float,
    pressure: float,
    context: EvaluationContext,
) -> bool:
    """A two-call sufficient condition for `δ > τ_T`: `True` only when this stream is certainly
    not temperature-degenerate; `False` means "not decided", never "degenerate".

    `g(·; β)` increases in `T` (spec §4.2), so `g(T − 2τ; 0) > 0` puts the bubble point below
    `T − 2τ`, and `g(T + 2τ; 1) < 0` the dew point above `T + 2τ`; either end then lies more than
    `2τ` from `T`. One `lnK` evaluation each, against `degeneracy_distance`'s two bisections
    (~100). A provider refusal at either point (a `T ∓ 2τ` off the domain) decides nothing.

    **It never contradicts `degeneracy_distance`** (the caller runs that whenever this returns
    `False`, so only a `True` could). A computed `δ ≤ τ` needs the computed band end within `τ` of
    `T`, hence the exact end within `τ + 1e-13 K` (the bisection closes to adjacent doubles, and
    `g`'s rounding, ~1e-15, moves a root by ~1e-13 K at the slope below). There `g(T ∓ 2τ)` is at
    least `g' (τ − 1e-13 K) ≈ 1.5e-8` from zero — `g' ≥ min_i Δh_i/(R T_max²) = 0.0155 K⁻¹` near
    either band end, where `Σ z_i K_i` or `Σ z_i / K_i` is 1 — seven decades above its rounding,
    so the sign test cannot land on the far side.
    """
    n = tuple(float(value) for value in flows)
    components = provider.describe().components
    try:
        below = _k_values(
            provider, n, temperature - PRESCREEN_MARGIN, pressure, components, context
        )
        if rachford_rice(n, below, 0.0) > 0.0:
            return True
        above = _k_values(
            provider, n, temperature + PRESCREEN_MARGIN, pressure, components, context
        )
    except BandError:
        return False
    return rachford_rice(n, above, 1.0) < 0.0


def is_temperature_degenerate(distance: float) -> bool:
    """Spec §4.4: within `τ_T = 1e-6 K` every vapour fraction is consistent with `T`."""
    return distance <= TEMPERATURE_TOLERANCE
