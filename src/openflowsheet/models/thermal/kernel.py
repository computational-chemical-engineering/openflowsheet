"""The pure-fluid kernel: saturation, PH/PS closures and declared-regime outlets (S11 units §4.2).

Procedural; floats in, typed results out. Every routine asks a Helmholtz provider (`iapws95-v1`,
`coolprop-heos-v1`) for what it declares — `Tsat` with dT_sat/dP, `Psat`, and h, s with their
(T, P) derivatives in a stated phase — and never evaluates a phase off the side the provider
answers (§2.2: beyond the band eps_sigma a metastable phase is refused `phase_not_stable`).

**Closures** (`ph_closure`, `ps_closure`). With the saturation at P answered, the target's
position against the saturated values decides the regime: inside, SATURATED at T_sat with
beta = (x* - x^L_sat)/(x^V_sat - x^L_sat); below, LIQUID on [T_min, T_sat]; above, VAPOR on
[T_sat, T_max]. Outside the saturation range, the provider's TP-flash label decides, over the
whole domain. The single-phase solve is a safeguarded Newton on T (the slope dh/dT = c_p and
ds/dT = c_p/T are positive), with a bisection step whenever Newton leaves the bracket, converging
by S05's rule on two consecutive relative Newton corrections (4 eps, or the residual floor;
R-595), at most `MAX_ITERATIONS` evaluations.

**Declared outlets** (`declared_state`). A single-phase form solves on its own side of T_sat, the
band edge included, and accepts iff a root exists and `declared_admissible` holds; the saturated
form accepts iff the closure is SATURATED. Otherwise `phase_regime_mismatch(<S>)`, naming the
declaration that would fit.

**Typed codes** (each the first line of a refusal message): `phase_regime_mismatch`,
`no_saturation`, `isentropic_state_two_phase`, `inadmissible_phase(<port>, <PHASE>)`,
`carried_split_missing`, `not_converged`, `out_of_domain`, `near_critical`.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from functools import cache
from typing import Final, Literal

from openflowsheet.compiled import EvaluationContext
from openflowsheet.thermo import (
    FlashRequest,
    Phase,
    PropertyProvider,
    PropertyRequest,
    PropertyStatus,
    StreamState,
)

__all__ = [
    "ADMISSIBILITY_MARGIN",
    "MAX_ITERATIONS",
    "Closure",
    "Failure",
    "Limits",
    "Mismatch",
    "Outlet",
    "Regime",
    "Sat",
    "declared_admissible",
    "declared_state",
    "isentropic_temperature",
    "limits",
    "phase_properties",
    "ph_closure",
    "ps_closure",
    "saturation",
]

Regime = Literal["LIQUID", "VAPOR", "SATURATED"]
Prop = Literal["h", "s"]

#: The inner solves' declared evaluation bound (§4.2).
MAX_ITERATIONS: Final = 100
#: S05's convergence rule (R-595): a relative Newton correction <= 4 eps, or, at the residual
#: floor, `previous` <= sqrt(eps) and `previous` <= `step` <= sqrt(eps).
STEP_TOLERANCE: Final = 4.0 * 2.0**-52
FLOOR_ONSET: Final = 2.0**-26
#: The first pass's §4.6 pure-fluid admissibility margin, the verifier's `PURE_FLUID_MARGIN`.
ADMISSIBILITY_MARGIN: Final = 1e-9

#: Provider refusal codes that mean "outside this regime's domain" (§4.1 trial states).
DOMAIN_CODES: Final[frozenset[str]] = frozenset(
    {"phase_not_stable", "near_critical", "no_saturation", "out_of_domain"}
)


def _converged(step: float, previous: float) -> bool:
    return step <= STEP_TOLERANCE or previous <= step <= FLOOR_ONSET


@dataclass(frozen=True)
class Failure:
    """A typed refusal: a status and a code that is the first line of the message."""

    status: PropertyStatus
    code: str
    detail: str = ""

    @property
    def message(self) -> str:
        return self.code if not self.detail else f"{self.code}\n{self.detail}"


def _refusal(status: PropertyStatus, message: str) -> Failure:
    """A provider refusal carried with its own reason code (`<code>: <detail>`)."""
    code = message.split(":", 1)[0].strip() if ":" in message else message
    return Failure(status, code, message)


# -- the fluid's limits -------------------------------------------------------------------------


@dataclass(frozen=True)
class Limits:
    """A pure fluid's constants the kernel needs, from package data (never the binder)."""

    component: str
    t_c: float
    t_min: float
    t_max: float
    #: The provider's refused near-critical box: T in the open interval, P in the closed one.
    nc_t: tuple[float, float]
    nc_p: tuple[float, float]


@cache
def _limits(provider_id: str, component: str, t_min: float, t_max: float) -> Limits:
    if provider_id == "iapws95-v1":
        from openflowsheet.thermo import iapws95  # noqa: PLC0415

        return Limits(
            component, iapws95.T_C, t_min, t_max, iapws95.NEAR_CRITICAL_T, iapws95.NEAR_CRITICAL_P
        )
    if provider_id == "coolprop-heos-v1":
        from openflowsheet.thermo._coolprop_heos_fluids import FLUIDS  # noqa: PLC0415

        (row,) = [row for row in FLUIDS if row["id"] == component]
        return Limits(
            component,
            float(row["T_c"]),
            t_min,
            t_max,
            (float(row["nc_T"][0]), float(row["nc_T"][1])),
            (float(row["nc_P"][0]), float(row["nc_P"][1])),
        )
    raise ValueError(f"{provider_id!r} is not a pure-fluid provider")


def limits(provider: PropertyProvider) -> Limits:
    described = provider.describe()
    (component,) = described.components
    t_min, t_max = described.domain["T"]
    return _limits(described.provider_id, component, float(t_min), float(t_max))


def _crosses_near_critical(fluid: Limits, pressure: float, low: float, high: float) -> bool:
    """Whether a bracket [low, high] at `pressure` enters the provider's refused box."""
    nc_t, nc_p = fluid.nc_t, fluid.nc_p
    return nc_p[0] <= pressure <= nc_p[1] and low < nc_t[1] and high > nc_t[0]


# -- provider access ------------------------------------------------------------------------------

#: `(value, d/dT, d/dP)` per property.
Jet = tuple[float, float, float]


def phase_properties(
    provider: PropertyProvider,
    context: EvaluationContext,
    temperature: float,
    pressure: float,
    phase: Phase,
    names: tuple[str, ...],
) -> dict[str, Jet] | Failure:
    """The named properties of one phase at (T, P) with their T and P derivatives.

    Evaluated at unit flow: every property here is intensive for a pure fluid, so this is exact
    and never meets `dormant_state`.
    """
    result = provider.evaluate_phase(
        PropertyRequest(
            state=StreamState(n=(1.0,), temperature=temperature, pressure=pressure),
            phase=phase,
            properties=names,
            derivatives=("T", "P"),
        ),
        context,
    )
    if result.status != "ok":
        return _refusal(result.status, result.message)
    return {
        name: (
            result.values[name],
            result.derivatives[name]["T"],
            result.derivatives[name]["P"],
        )
        for name in names
    }


def _label(
    provider: PropertyProvider, context: EvaluationContext, temperature: float, pressure: float
) -> Phase | Failure:
    """The provider's own TP-flash label at (T, P), for a state outside the saturation range."""
    result = provider.flash(
        FlashRequest(state=StreamState(n=(1.0,), temperature=temperature, pressure=pressure)),
        context,
    )
    if result.status != "ok":
        return _refusal(result.status, result.message)
    signature = result.phase_signature
    if signature not in ("LIQUID", "VAPOR"):
        raise RuntimeError(f"the TP flash labelled a pure fluid {signature!r}")
    return signature  # type: ignore[return-value]


# -- saturation -----------------------------------------------------------------------------------


@dataclass(frozen=True)
class Sat:
    """The saturation at P: T_sat, dT_sat/dP, and both phases' h and s jets at (T_sat, P)."""

    pressure: float
    temperature: float
    dtsat_dp: float
    liquid: dict[str, Jet]
    vapor: dict[str, Jet]

    def value(self, phase: Phase, name: str) -> float:
        return (self.liquid if phase == "LIQUID" else self.vapor)[name][0]

    def along(self, phase: Phase, name: str) -> float:
        """d/dP of a saturated property along the line: (d/dT) dT_sat/dP + d/dP."""
        jet = (self.liquid if phase == "LIQUID" else self.vapor)[name]
        return jet[1] * self.dtsat_dp + jet[2]


def saturation(
    provider: PropertyProvider, pressure: float, context: EvaluationContext
) -> Sat | Failure:
    """T_sat(P), then h and s of both phases at (T_sat, P), each on its own root (T_sat lies
    inside the band). A refusal of `Tsat` is `no_saturation`."""
    fluid = limits(provider)
    result = provider.evaluate_phase(
        PropertyRequest(
            state=StreamState(n=(1.0,), temperature=fluid.t_min, pressure=pressure),
            phase="LIQUID",
            properties=("Tsat",),
            derivatives=("P",),
        ),
        context,
    )
    if result.status != "ok":
        return _refusal(result.status, result.message)
    t_sat = result.values["Tsat"]
    phases: list[dict[str, Jet]] = []
    for phase in ("LIQUID", "VAPOR"):
        jets = phase_properties(provider, context, t_sat, pressure, phase, ("h", "s"))
        if isinstance(jets, Failure):
            return jets
        phases.append(jets)
    return Sat(pressure, t_sat, result.derivatives["Tsat"]["P"], phases[0], phases[1])


# -- the inner solve ------------------------------------------------------------------------------

_Evaluate = Callable[[float], "tuple[float, float] | Failure"]


def _solve(
    evaluate: _Evaluate,
    low: float,
    high: float,
    *,
    start: float | None = None,
    what: str,
) -> tuple[float, int] | Failure:
    """The root of an increasing `g(T) = evaluate(T)[0]` on [low, high], with its evaluations.

    Safeguarded Newton: the bracket shrinks on every evaluation, a step that leaves it is replaced
    by bisection, and only a Newton correction converges (S05's rule, tested before the safeguard).
    `start` (if inside) is the first iterate; otherwise the secant point of the two ends. A
    target outside the bracket is `out_of_domain`.
    """
    floor, ceiling = low, high
    ends: list[float] = []
    for point in (low, high):
        answer = evaluate(point)
        if isinstance(answer, Failure):
            return answer
        ends.append(answer[0])
    g_low, g_high = ends
    if g_low == 0.0:
        return low, 2
    if g_high == 0.0:
        return high, 2
    if g_low > 0.0 or g_high < 0.0:
        return Failure(
            "out_of_domain", "out_of_domain", f"{what}: no root on [{low!r}, {high!r}] K"
        )
    if start is not None and low < start < high:
        temperature = start
    else:
        temperature = low - g_low * (high - low) / (g_high - g_low)
        if not low < temperature < high:
            temperature = 0.5 * (low + high)
    previous = math.inf
    for evaluations in range(3, MAX_ITERATIONS + 1):
        answer = evaluate(temperature)
        if isinstance(answer, Failure):
            return answer
        residual, slope = answer
        if residual == 0.0:
            return temperature, evaluations
        if residual < 0.0:
            low = temperature
        else:
            high = temperature
        if not slope > 0.0:
            temperature, previous = 0.5 * (low + high), math.inf
            continue
        new = temperature - residual / slope
        step = abs(new - temperature) / temperature
        if _converged(step, previous):
            return min(max(new, floor), ceiling), evaluations
        if low < new < high:
            temperature, previous = new, step
        else:
            temperature, previous = 0.5 * (low + high), math.inf
    return Failure(
        "not_converged", "not_converged", f"{what}: no convergence in {MAX_ITERATIONS} evaluations"
    )


def _phase_target(
    provider: PropertyProvider,
    context: EvaluationContext,
    pressure: float,
    phase: Phase | None,
    prop: Prop,
    target: float,
) -> _Evaluate:
    """`T -> (x(T, P) - target, dx/dT)` in `phase`, or in the provider's label when `None`."""

    def evaluate(temperature: float) -> tuple[float, float] | Failure:
        evaluated = phase
        if evaluated is None:
            label = _label(provider, context, temperature, pressure)
            if isinstance(label, Failure):
                return label
            evaluated = label
        jets = phase_properties(provider, context, temperature, pressure, evaluated, (prop,))
        if isinstance(jets, Failure):
            return jets
        value, d_t, _ = jets[prop]
        return value - target, d_t

    return evaluate


def _side(fluid: Limits, sat: Sat, phase: Phase) -> tuple[float, float]:
    return (fluid.t_min, sat.temperature) if phase == "LIQUID" else (sat.temperature, fluid.t_max)


# -- closures -------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Closure:
    """Where a (P, x*) lands: the regime, T, beta (SATURATED only) and the route taken."""

    regime: Regime
    temperature: float
    beta: float | None
    route: str
    iterations: int = 0


def _unsaturated(
    provider: PropertyProvider,
    context: EvaluationContext,
    fluid: Limits,
    pressure: float,
    prop: Prop,
    target: float,
) -> Closure | Failure:
    """P outside the saturation range: the regime is the provider's label at the root."""
    if _crosses_near_critical(fluid, pressure, fluid.t_min, fluid.t_max):
        return Failure(
            "unsupported",
            "near_critical",
            f"the {prop} closure at {pressure!r} Pa crosses the provider's near-critical box",
        )
    solved = _solve(
        _phase_target(provider, context, pressure, None, prop, target),
        fluid.t_min,
        fluid.t_max,
        what=f"{prop} closure at {pressure!r} Pa",
    )
    if isinstance(solved, Failure):
        return solved
    temperature, evaluations = solved
    label = _label(provider, context, temperature, pressure)
    if isinstance(label, Failure):
        return label
    return Closure(label, temperature, None, "label", evaluations)


def _single_phase(
    provider: PropertyProvider,
    context: EvaluationContext,
    fluid: Limits,
    sat: Sat,
    phase: Phase,
    prop: Prop,
    target: float,
) -> tuple[float, int] | Failure:
    low, high = _side(fluid, sat, phase)
    if _crosses_near_critical(fluid, sat.pressure, low, high):
        return Failure(
            "unsupported",
            "near_critical",
            f"the {phase} {prop} solve at {sat.pressure!r} Pa crosses the near-critical box",
        )
    return _solve(
        _phase_target(provider, context, sat.pressure, phase, prop, target),
        low,
        high,
        what=f"{phase} {prop} at {sat.pressure!r} Pa",
    )


def _closure(
    provider: PropertyProvider,
    total: float,
    pressure: float,
    extensive: float,
    prop: Prop,
    context: EvaluationContext,
) -> Closure | Failure:
    if not total > 0.0:
        raise ValueError(f"a closure needs a positive flow, got {total!r}")
    target = extensive / total
    fluid = limits(provider)
    sat = saturation(provider, pressure, context)
    if isinstance(sat, Failure):
        if sat.code != "no_saturation":
            return sat
        return _unsaturated(provider, context, fluid, pressure, prop, target)
    liquid, vapour = sat.value("LIQUID", prop), sat.value("VAPOR", prop)
    if liquid <= target <= vapour:
        beta = (target - liquid) / (vapour - liquid)
        return Closure("SATURATED", sat.temperature, beta, "saturated")
    phase: Phase = "LIQUID" if target < liquid else "VAPOR"
    solved = _single_phase(provider, context, fluid, sat, phase, prop, target)
    if isinstance(solved, Failure):
        return solved
    return Closure(phase, solved[0], None, phase.lower(), solved[1])


def ph_closure(
    provider: PropertyProvider,
    total: float,
    pressure: float,
    enthalpy_flow: float,
    context: EvaluationContext,
) -> Closure | Failure:
    """Where n, P, H land (§4.2); n > 0."""
    return _closure(provider, total, pressure, enthalpy_flow, "h", context)


def ps_closure(
    provider: PropertyProvider,
    total: float,
    pressure: float,
    entropy_flow: float,
    context: EvaluationContext,
) -> Closure | Failure:
    """Where n, P, S land (§4.2); n > 0."""
    return _closure(provider, total, pressure, entropy_flow, "s", context)


# -- admissibility and declared outlets -----------------------------------------------------------


def declared_admissible(
    provider: PropertyProvider,
    temperature: float,
    pressure: float,
    phase: Phase,
    context: EvaluationContext,
) -> bool | Failure:
    """The first pass's §4.6 rule, the verifier's `_pure_fluid_margin` restated:
    LIQUID iff T < T_c and P >= P_sat(T)(1 - 1e-9); VAPOR iff T >= T_c or P <= P_sat(T)(1 + 1e-9);
    where `Psat` is refused (T in (T_sigma,max, T_c)), the provider's TP-flash label decides."""
    fluid = limits(provider)
    if temperature >= fluid.t_c:
        return phase == "VAPOR"
    result = provider.evaluate_phase(
        PropertyRequest(
            state=StreamState(n=(1.0,), temperature=temperature, pressure=pressure),
            phase=phase,
            properties=("Psat",),
        ),
        context,
    )
    if result.status != "ok":
        failure = _refusal(result.status, result.message)
        if failure.code != "no_saturation":
            return failure
        label = _label(provider, context, temperature, pressure)
        return label if isinstance(label, Failure) else label == phase
    p_sat = result.values["Psat"]
    if phase == "LIQUID":
        return pressure >= p_sat * (1.0 - ADMISSIBILITY_MARGIN)
    return pressure <= p_sat * (1.0 + ADMISSIBILITY_MARGIN)


@dataclass(frozen=True)
class Outlet:
    """An accepted declared outlet: its form, T, beta (SATURATED only) and the work done."""

    form: Regime
    temperature: float
    beta: float | None
    iterations: int = 0


@dataclass(frozen=True)
class Mismatch:
    """The closure landed outside the declared regime (§4.2)."""

    declared: Regime
    regime: Regime
    beta: float | None

    def failure(self, stream: str) -> Failure:
        capability = {"LIQUID": "liquid", "VAPOR": "vapor", "SATURATED": "vapor_liquid"}
        landed = f"closure {self.regime}"
        if self.beta is not None:
            landed += f" beta={self.beta:.6g}"
        return Failure(
            "unsupported",
            f"phase_regime_mismatch({stream})",
            f"declared {capability[self.declared]}, {landed}; declare {capability[self.regime]}",
        )


def _classify(sat: Sat, prop: Prop, target: float) -> tuple[Regime, float | None]:
    liquid, vapour = sat.value("LIQUID", prop), sat.value("VAPOR", prop)
    if liquid <= target <= vapour:
        return "SATURATED", (target - liquid) / (vapour - liquid)
    return ("LIQUID" if target < liquid else "VAPOR"), None


def declared_state(
    provider: PropertyProvider,
    total: float,
    pressure: float,
    extensive: float,
    form: Regime,
    prop: Prop,
    context: EvaluationContext,
) -> Outlet | Mismatch | Failure:
    """The evaluate's routine for an outlet of a declared form (§4.2); n > 0."""
    if form == "SATURATED":
        closure = _closure(provider, total, pressure, extensive, prop, context)
        if isinstance(closure, Failure):
            return closure
        if closure.regime != "SATURATED":
            return Mismatch(form, closure.regime, None)
        return Outlet("SATURATED", closure.temperature, closure.beta, closure.iterations)

    if not total > 0.0:
        raise ValueError(f"a declared outlet needs a positive flow, got {total!r}")
    target = extensive / total
    fluid = limits(provider)
    sat = saturation(provider, pressure, context)
    if isinstance(sat, Failure):
        if sat.code != "no_saturation":
            return sat
        closure = _unsaturated(provider, context, fluid, pressure, prop, target)
        if isinstance(closure, Failure):
            return closure
        temperature, evaluations = closure.temperature, closure.iterations
        if closure.regime != form:
            return Mismatch(form, closure.regime, None)
    else:
        regime, beta = _classify(sat, prop, target)
        end = sat.value(form, prop)
        on_side = target <= end if form == "LIQUID" else target >= end
        if not on_side:
            return Mismatch(form, regime, beta)
        solved = _single_phase(provider, context, fluid, sat, form, prop, target)
        if isinstance(solved, Failure):
            return solved
        temperature, evaluations = solved
    admissible = declared_admissible(provider, temperature, pressure, form, context)
    if isinstance(admissible, Failure):
        return admissible
    if not admissible:
        other: Regime = "VAPOR" if form == "LIQUID" else "LIQUID"
        return Mismatch(form, other, None)
    return Outlet(form, temperature, None, evaluations)


# -- the isentropic state -------------------------------------------------------------------------


def isentropic_temperature(
    provider: PropertyProvider,
    context: EvaluationContext,
    entropy: float,
    pressure: float,
    phase: Phase,
    start: float,
) -> tuple[float, int] | Failure:
    """T_s with s^phase(T_s, P) = s*, on the phase's side of T_sat(P) when it exists (§4.3).

    Safeguarded Newton from `start` (the machine's inlet temperature: a fixed rule, so T_s is a
    function of its inputs). No root on the declared side is `isentropic_state_two_phase`; outside
    the saturation range the root's label must be `phase`.
    """
    fluid = limits(provider)
    sat = saturation(provider, pressure, context)
    if isinstance(sat, Failure):
        if sat.code != "no_saturation":
            return sat
        if _crosses_near_critical(fluid, pressure, fluid.t_min, fluid.t_max):
            return Failure("unsupported", "near_critical", f"the PS solve at {pressure!r} Pa")
        solved = _solve(
            _phase_target(provider, context, pressure, None, "s", entropy),
            fluid.t_min,
            fluid.t_max,
            start=start,
            what=f"isentropic state at {pressure!r} Pa",
        )
        if isinstance(solved, Failure):
            return solved
        label = _label(provider, context, solved[0], pressure)
        if isinstance(label, Failure):
            return label
        if label != phase:
            return Failure(
                "unsupported",
                "isentropic_state_two_phase",
                f"the isentropic state at {pressure!r} Pa is {label}, not {phase}",
            )
        return solved
    end = sat.value(phase, "s")
    if not (entropy <= end if phase == "LIQUID" else entropy >= end):
        return Failure(
            "unsupported",
            "isentropic_state_two_phase",
            f"s* = {entropy!r} lies past the saturated {phase} entropy {end!r} at {pressure!r} Pa",
        )
    low, high = _side(fluid, sat, phase)
    if _crosses_near_critical(fluid, pressure, low, high):
        return Failure("unsupported", "near_critical", f"the PS solve at {pressure!r} Pa")
    return _solve(
        _phase_target(provider, context, pressure, phase, "s", entropy),
        low,
        high,
        start=start,
        what=f"isentropic {phase} state at {pressure!r} Pa",
    )
