"""The γ–φ-IG primitives: K at a liquid, mixture enthalpy flows, the constant-β point and the
fixed-T incipient liquid (S10-C design note §4.2–§4.4, ADR 0049 D2–D3).

For a provider of form `gamma-phi-ig-v1` (`equilibrium_form`), `ln φ_i^V ≡ 0`, so

    ln K_i(T, P, x) = ln φ_i^L(T, P, x) = ln γ_i(x) + ln P_i^sat(T) − ln P,

a function of the **liquid** composition only, read from the provider's `lnphi_<c>`. Enthalpies are
the provider's mixture `h`, and a stream's enthalpy flow is `Ḣ = n_tot h`.

**The constant-β point** `(T, x)(n, P, β)` generalises ADR 0012 D1's `T(β)` (`saturation_band`):
composition successive substitution with an exact, bracketed temperature solve per step. β is a
parameter, never solved from K, so the iteration has no E-2 noise floor (S10 spec §14):
`|∂ ln x_i/∂ ln K_i| = β K_i/D_i ≤ 1`, so a step's noise is ≈ `‖G‖u`, not `u‖G‖/min|K − 1|`.
`β = 0` is the bubble point, exact in one step; `β = 1` is the dew point (the liquid-trial
stationary point of S10 §5.4 step 3, `g = tm*`).

**Failures are typed, never values**, as in `saturation_band`: a provider refusal or an exhausted
budget raises `BandError(status, message)`, and callers keep their typed mapping. Every evaluation
is one `evaluate_phase` of `LIQUID` `lnphi_<c>`; nothing here calls the provider's TP flash.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Final

from openflowsheet.compiled import EvaluationContext
from openflowsheet.models.syn001.saturation_band import (
    MAX_TEMPERATURE_EVALUATIONS,
    BandError,
    BandTemperature,
    Position,
)
from openflowsheet.thermo import (
    Phase,
    PropertyProvider,
    PropertyRequest,
    PropertyStatus,
    StreamState,
)

__all__ = [
    "BETA_SS_MAX",
    "DELTA_BETA",
    "INCIPIENT_DELTA",
    "INCIPIENT_MAX",
    "band_point",
    "enthalpy_and_slope",
    "enthalpy_flow",
    "incipient_liquid",
    "ln_k",
]

#: §4.3: the constant-β point stops at `max_{i∈F} |Δ ln K_i| ≤ DELTA_BETA`, 28× the ln K rounding
#: floor 3.55e-15 (S10 §5.6); measured last steps ≤ 9.95e-14 (`measured.txt` M-a).
DELTA_BETA: Final = 1.0e-13
#: §4.3: the successive-substitution cap; measured ≤ 61 iterations (M-a), 16× below.
BETA_SS_MAX: Final = 1000
#: §4.4: the incipient liquid's stop in `max |Δ ln W|` and its cap (S10 §5.4 step 3's values).
INCIPIENT_DELTA: Final = 1.0e-13
INCIPIENT_MAX: Final = 1000


# -- K at a liquid composition (§4.2) ------------------------------------------------------------


def _ln_k(
    provider: PropertyProvider,
    components: tuple[str, ...],
    temperature: float,
    pressure: float,
    liquid: Sequence[float],
    context: EvaluationContext,
    derivatives: tuple[str, ...],
) -> tuple[tuple[float, ...], tuple[float, ...], tuple[tuple[float, ...], ...]]:
    if not sum(liquid) > 0.0:
        raise ValueError("ln K is evaluated at a flowing liquid; a dormant one has no composition")
    names = tuple(f"lnphi_{c}" for c in components)
    by_n = tuple(f"n_{c}" for c in components)
    wants_n = [name for name in derivatives if name in by_n]
    if wants_n and len(wants_n) != len(by_n):
        raise ValueError(f"composition derivatives are all of {by_n} or none, not {wants_n}")
    result = provider.evaluate_phase(
        PropertyRequest(
            state=StreamState(n=tuple(liquid), temperature=temperature, pressure=pressure),
            phase="LIQUID",
            properties=names,
            derivatives=derivatives,
        ),
        context,
    )
    if result.status != "ok":
        raise BandError(result.status, f"ln phi^L at T = {temperature!r} K: {result.message}")
    values = tuple(result.values[name] for name in names)
    d_t = tuple(result.derivatives[name]["T"] for name in names) if "T" in derivatives else ()
    d_n = (
        tuple(tuple(result.derivatives[name][wrt] for wrt in by_n) for name in names)
        if wants_n
        else ()
    )
    return values, d_t, d_n


def ln_k(
    provider: PropertyProvider,
    temperature: float,
    pressure: float,
    liquid: Sequence[float],
    context: EvaluationContext,
    *,
    derivatives: tuple[str, ...] = (),
) -> tuple[tuple[float, ...], tuple[float, ...], tuple[tuple[float, ...], ...]]:
    """`(ln K_i, ∂ ln K_i/∂T, ∂ ln K_i/∂n_j)` at `(T, P)` and the liquid `liquid` (§4.2).

    One `evaluate_phase(LIQUID, lnphi_<c>…)`; the values are the provider's bitwise. `liquid` is a
    composition or flows (the provider normalises) and must be flowing (`ValueError` otherwise, a
    caller defect). `d_T` is empty unless `"T"` is requested; `d_n` (rows `i`, columns `j` in the
    provider's order: the projected derivatives, which at `n = l` *are* `∂ ln K_i/∂l_j`) is empty
    unless every `n_<c>` is. A provider refusal raises `BandError`.
    """
    components = provider.describe().components
    return _ln_k(provider, components, temperature, pressure, liquid, context, derivatives)


# -- mixture enthalpy flows (§4.2) ---------------------------------------------------------------


def enthalpy_flow(
    provider: PropertyProvider, state: StreamState, phase: Phase, context: EvaluationContext
) -> tuple[PropertyStatus, float, str]:
    """`Ḣ = n_tot h^phase(T, P, n)` for one single-phase stream, W.

    A dormant stream contributes exactly `0.0` and the provider is not called (ADR 0001 D3.1).
    """
    if state.is_dormant:
        return "ok", 0.0, ""
    result = provider.evaluate_phase(
        PropertyRequest(state=state, phase=phase, properties=("h",)), context
    )
    if result.status != "ok":
        return result.status, 0.0, result.message
    return "ok", state.total_flow * result.values["h"], ""


def enthalpy_and_slope(
    provider: PropertyProvider, state: StreamState, phase: Phase, context: EvaluationContext
) -> tuple[PropertyStatus, float, float, str]:
    """`(status, Ḣ, dḢ/dT, message)` for a flowing single-phase stream, from one call:
    `Ḣ = n_tot h`, `dḢ/dT = n_tot ∂h/∂T` (`tp_state.single_phase_admissible`'s inputs)."""
    result = provider.evaluate_phase(
        PropertyRequest(state=state, phase=phase, properties=("h",), derivatives=("T",)),
        context,
    )
    if result.status != "ok":
        return result.status, 0.0, 0.0, result.message
    total = state.total_flow
    return "ok", total * result.values["h"], total * result.derivatives["h"]["T"], ""


# -- the constant-β point (§4.3) -----------------------------------------------------------------


class _Evaluation:
    """`ln K` and `∂ ln K/∂T` at one `(T, x)`, and `g`, `g'` of the frozen-x function there."""

    __slots__ = ("g", "ln_k", "slope", "temperature")

    def __init__(
        self,
        temperature: float,
        ln_k: tuple[float, ...],
        d_t: tuple[float, ...],
        z: tuple[float, ...],
        flowing: tuple[int, ...],
        beta: float,
    ) -> None:
        self.temperature = temperature
        self.ln_k = ln_k
        g = 0.0
        slope = 0.0
        for i in flowing:
            k = math.exp(ln_k[i])
            d = 1.0 + beta * (k - 1.0)
            g += z[i] * (k - 1.0) / d
            slope += z[i] * k * d_t[i] / (d * d)
        self.g = g
        self.slope = slope


class _Point:
    """The constant-β point's state: the stream, β, and the evaluation counter."""

    def __init__(
        self,
        provider: PropertyProvider,
        components: tuple[str, ...],
        n: tuple[float, ...],
        pressure: float,
        beta: float,
        domain: tuple[float, float],
        context: EvaluationContext,
    ) -> None:
        self._provider = provider
        self._components = components
        self._pressure = pressure
        self._context = context
        self.beta = beta
        self.domain = domain
        total = sum(n)
        self.z = tuple(value / total for value in n)
        # F on z, not n: an n_i < 2^-1075 n_tot underflows to z_i = 0.0 (S10 spec §14 E-1).
        self.flowing = tuple(i for i, value in enumerate(self.z) if value > 0.0)
        self.evaluations = 0

    def evaluate(self, temperature: float, x: tuple[float, ...]) -> _Evaluation:
        self.evaluations += 1
        values, d_t, _ = _ln_k(
            self._provider,
            self._components,
            temperature,
            self._pressure,
            x,
            self._context,
            ("T",),
        )
        return _Evaluation(temperature, values, d_t, self.z, self.flowing, self.beta)

    def composition(self, ln_k: tuple[float, ...]) -> tuple[float, ...]:
        """`x_i = z_i/D_i` over F, normalised; `0.0` off F."""
        beta, z = self.beta, self.z
        weights = {i: z[i] / (1.0 + beta * (math.exp(ln_k[i]) - 1.0)) for i in self.flowing}
        total = sum(weights.values())
        return tuple(weights[i] / total if i in weights else 0.0 for i in range(len(z)))

    def temperature(
        self, x: tuple[float, ...], start: _Evaluation, budget: int
    ) -> tuple[_Evaluation, Position]:
        """`Tsolve(x, start)`: the root of the frozen-x `g(·; x)`, increasing in T (§4.3).

        Safeguarded Newton inside a sign bracket that every evaluation narrows, stepping from the
        bracket end with the smaller `|g|` (the lower on a tie); the midpoint when Newton leaves
        the open bracket or the bracket has not halved over the last two steps. An
        unknown domain end is evaluated before a step past it: `g(T_min) > 0` is `below`,
        `g(T_max) < 0` is `above`, each returned with that end's evaluation. Stops on `g = 0` or
        adjacent doubles (the end with the smaller `|g|`, the lower on a tie). `start` is one of the
        `budget` evaluations.
        """
        t_min, t_max = self.domain
        lo: _Evaluation | None = None  # the highest evaluation with g < 0
        hi: _Evaluation | None = None  # the lowest evaluation with g > 0
        widths: list[float] = []
        current = start
        spent = 1
        while True:
            if current.g == 0.0:
                return current, "inside"
            if current.g < 0.0:
                if current.temperature == t_max:
                    return current, "above"
                lo = current
            else:
                if current.temperature == t_min:
                    return current, "below"
                hi = current
            low = t_min if lo is None else lo.temperature
            high = t_max if hi is None else hi.temperature
            widths.append(high - low)
            if math.nextafter(low, math.inf) >= high:
                if lo is None or hi is None:
                    # The bracket has closed against an end whose value is unknown.
                    following = t_min if lo is None else t_max
                else:
                    return (lo, "inside") if abs(lo.g) <= abs(hi.g) else (hi, "inside")
            else:
                base = min(
                    (end for end in (lo, hi) if end is not None),
                    key=lambda end: (abs(end.g), end.temperature),
                )
                following = self._step(base, low, high, lo is None, hi is None, widths)
            if spent >= budget:
                raise BandError(
                    "not_converged",
                    f"constant-beta point (beta = {self.beta!r}): the temperature solve did not "
                    f"close in {budget} evaluations",
                )
            current = self.evaluate(following, x)
            spent += 1

    @staticmethod
    def _step(
        base: _Evaluation,
        low: float,
        high: float,
        low_unknown: bool,
        high_unknown: bool,
        widths: list[float],
    ) -> float:
        newton = (
            base.temperature - base.g / base.slope
            if base.slope > 0.0 and math.isfinite(base.slope)
            else math.nan
        )
        if newton == base.temperature:
            # Newton has stalled on a bracket end: the adjacent double towards the root.
            return math.nextafter(newton, math.inf if base.g < 0.0 else -math.inf)
        if low_unknown and newton <= low:
            return low
        if high_unknown and newton >= high:
            return high
        stalled = len(widths) >= 3 and widths[-1] > 0.5 * widths[-3]
        if not low < newton < high or stalled:
            return 0.5 * (low + high)
        return newton


def band_point(
    provider: PropertyProvider,
    flows: Sequence[float],
    pressure: float,
    beta: float,
    context: EvaluationContext,
    *,
    budget: int = MAX_TEMPERATURE_EVALUATIONS,
) -> BandTemperature:
    """The constant-β point `(T, x)(n, P, β)` (§4.3), as a `BandTemperature`.

    Find `T` and a liquid `x` with `x_i = z_i/D_i`, `D_i = 1 + β (K_i(T, P, x) − 1)` on the
    flowing set F (`x_i = 0` off it) and `g(T; x) = Σ_{i∈F} z_i (K_i − 1)/D_i = 0`: from `x⁰ = z`,
    each step solves `g(·; x^{m−1}) = 0` for `T^m` (`budget` evaluations per solve), sets
    `K^m = K(T^m, x^{m−1})` and `x^m` from `K^m`, and stops at `max_{i∈F} |ln K_i(T^m, x^m) −
    ln K^m_i| ≤ DELTA_BETA`; that evaluation starts the next solve. Every point starts cold at
    `x = z`. `β = 0` returns after one solve (`x = z`, the bubble point).

    `inside`: `temperature = T^m`, `k_values = K^m` (all components; an absent one's is the
    infinite-dilution K of the same evaluation), `liquid = x^m`. A solve that ends `below` /
    `above` clamps `T^m` to that domain end and the iteration continues; the last step's position
    is reported, and `below` / `above` carry no temperature (the `BandTemperature` contract).
    `evaluations` counts every `evaluate_phase`. No stop within `BETA_SS_MAX` steps raises
    `BandError("not_converged", …)`.
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
    point = _Point(provider, components, n, pressure, beta, (t_min, t_max), context)
    x = point.z
    start = point.evaluate(0.5 * (t_min + t_max), x)
    at, position = point.temperature(x, start, budget)
    if beta == 0.0:
        return _band(position, at, x, point.evaluations)
    step = math.inf
    for _ in range(BETA_SS_MAX):
        x_next = point.composition(at.ln_k)
        start = point.evaluate(at.temperature, x_next)
        step = max(abs(start.ln_k[i] - at.ln_k[i]) for i in point.flowing)
        if step <= DELTA_BETA:
            return _band(position, at, x_next, point.evaluations)
        x = x_next
        at, position = point.temperature(x, start, budget)
    raise BandError(
        "not_converged",
        f"constant-beta point (beta = {beta!r}): no stop in {BETA_SS_MAX} iterations; last step "
        f"{step!r}",
    )


def _band(
    position: Position, at: _Evaluation, x: tuple[float, ...], evaluations: int
) -> BandTemperature:
    if position != "inside":
        return BandTemperature(position, evaluations=evaluations)
    return BandTemperature(
        "inside",
        at.temperature,
        tuple(math.exp(value) for value in at.ln_k),
        evaluations,
        liquid=x,
    )


# -- the fixed-T incipient liquid (§4.4) ---------------------------------------------------------


def incipient_liquid(
    provider: PropertyProvider,
    temperature: float,
    pressure: float,
    vapor: Sequence[float],
    context: EvaluationContext,
) -> tuple[float, tuple[float, ...]]:
    """`(ΣW, w)`: S10 §5.4 step 3's liquid trial against the vapour `y` at fixed `(T, P)` (§4.4).

    `W⁰_i = y_i/K_i(T, y)`; `w = W/ΣW`; `W'_i = y_i/K_i(T, w)` on F; stop at `max |ln W' − ln W| ≤
    INCIPIENT_DELTA` within `INCIPIENT_MAX` iterations, else `BandError("not_converged", …)`.
    `ΣW ≤ 1` ⇔ the vapour is stable (the dew value). W is carried as `ln W = ln y − ln K`.
    """
    components = provider.describe().components
    y_total = sum(vapor)
    if not y_total > 0.0:
        raise ValueError("the incipient liquid is for a flowing vapour; a dormant one has none")
    y = tuple(value / y_total for value in vapor)
    flowing = tuple(i for i, value in enumerate(y) if value > 0.0)
    ln_y = {i: math.log(y[i]) for i in flowing}

    def ln_k_at(liquid: tuple[float, ...]) -> tuple[float, ...]:
        values, _, _ = _ln_k(provider, components, temperature, pressure, liquid, context, ())
        return values

    def normalised(ln_w: dict[int, float]) -> tuple[float, ...]:
        weights = {i: math.exp(value) for i, value in ln_w.items()}
        total = sum(weights.values())
        return tuple(weights[i] / total if i in weights else 0.0 for i in range(len(y)))

    start = ln_k_at(y)
    ln_w = {i: ln_y[i] - start[i] for i in flowing}
    step = math.inf
    for _ in range(INCIPIENT_MAX):
        ln_k_w = ln_k_at(normalised(ln_w))
        new = {i: ln_y[i] - ln_k_w[i] for i in flowing}
        step = max(abs(new[i] - ln_w[i]) for i in flowing)
        ln_w = new
        if step <= INCIPIENT_DELTA:
            return sum(math.exp(value) for value in ln_w.values()), normalised(ln_w)
    raise BandError(
        "not_converged",
        f"incipient liquid at T = {temperature!r} K: no stop in {INCIPIENT_MAX} iterations; "
        f"last step {step!r}",
    )
