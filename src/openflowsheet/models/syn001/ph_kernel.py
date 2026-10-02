"""The PH closure's causal kernel, and the evaluator steps T05's units share (T05 spec §4).

`ph_state(provider, n, P, H*)` answers "at what temperature does this set of component flows,
at this pressure, carry this enthalpy, and how is it split?" It is built on K02's `tp_state` and
asks the provider only for what it already offers — a TP flash, `h` and `lnK` — so no provider
capability is added and `thermo/syn001.py` is not touched (ADR 0011 D1, D3).

**Why a bracket is enough** (spec §4.2). For a flowing SYN-001 stream with at least two flowing
components, `Hdot_TP(T)` at fixed `P` is continuous and strictly increasing with slope at least
`n_tot c_p`, so the root on the domain is unique when it exists and bisection finds it. With a
single flowing component the two-phase region collapses to `T_sat(P)` and `Hdot_TP` *jumps* there
by `n_k dh_k`; the provider's flash calls `T_sat` liquid, so no temperature reproduces an enthalpy
inside the jump. The saturation route (step 2) exists for exactly that state.

**Why a bracket is not always enough, and the band route** (T05b spec §4–§5, ADR 0012 D2). Near
purity the two-phase band is a few hundred doubles of `T` wide and carries the whole latent heat
(2.1e-11 K and 60 000 W for 2 mol/s of B with 1e-12 mol/s of A), so no double of `T` meets most
targets inside it. The answer is accepted only if it satisfies the PH closure's own rows at K04's
registered tolerances (§5.3); when the temperature route's answer does not and at least two
components flow, the kernel falls back to the **band route**, a bisection in the vapour fraction
`β` of `H(β) − H*`, whose parameter carries the latent heat over a width of 1 instead of 2e-11 K
(`saturation_band`). The fallback is deterministic and recorded in `PHState.route` (ADR 0012
D10's F1); it runs only after the temperature route failed, so every answer the temperature route
gave before T05b is returned bit for bit.

**What the kernel does not do.** It solves nothing for a dormant stream (the caller owns ADR 0001
D3's labels, spec §4.7); it does not extrapolate (a target outside the domain's bracket is
`out_of_domain`); it supplies no derivative (the sensitivity of `T*` to `H*` changes slope at
every phase boundary and is declared `unavailable`, spec §4.5); and it never returns a state it
has not verified against the closure's rows (T05b §5.3): material within `3.1e-8 mol/s`,
equilibrium within `9.3e-8 (mol/s)²`, energy within `1.01e-3 W`.

**Typed failures.** Every non-`ok` answer carries a registered code (spec §13.3) as the first
line of its message and nothing else a caller could mistake for a result (spec §3.5). A provider
refusal inside the kernel is surfaced with the provider's own status, K02's pattern (spec §3.3);
the one the kernel can name — an inner search that did not converge — is `ph_not_converged`.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final, Literal

from openflowsheet.compiled import EvaluationContext, PhaseSignature
from openflowsheet.models import UnitEvaluation
from openflowsheet.models.syn001 import ENERGY_TOLERANCE, FLOW_TOLERANCE, REFERENCE_CONVENTION
from openflowsheet.models.syn001.bisection import Root, bracketed_root
from openflowsheet.models.syn001.saturation_band import (
    BandError,
    band_split,
    band_temperature,
)
from openflowsheet.models.syn001.tp_state import (
    TPState,
    enthalpy_flow,
    single_phase_admissible,
    tp_state,
)
from openflowsheet.thermo import (
    Phase,
    PropertyProvider,
    PropertyRequest,
    PropertyStatus,
    StreamState,
)

__all__ = [
    "BETA_WIDTH_FLOOR",
    "EQUILIBRIUM_TOLERANCE",
    "MAX_BAND_EVALUATIONS",
    "MAX_EVALUATIONS",
    "PortEnthalpy",
    "PHState",
    "Root",
    "bracketed_root",
    "closure_failure",
    "port_enthalpy",
    "ph_state",
    "typed_failure",
]

#: Spec §4.4 step 4: at most this many evaluations of `f`, else `ph_not_converged`. Plain
#: bisection on the SYN-001 domain reaches adjacent doubles in about 44.
MAX_EVALUATIONS: Final = 200

#: T05b spec §5.2: at most this many evaluations of `F(β)`, the two ends included; the width
#: floor below is reached after 60 halvings, so the budget is never the binding stop on SYN-001.
MAX_BAND_EVALUATIONS: Final = 64
#: T05b spec §5.2: the `β` bracket stops at this width. Near `β = 0` adjacent doubles are ~1 000
#: halvings away; at `2⁻⁶⁰` every flow's spread across the bracket is below the flow floor for
#: `n ≤ 1e4 mol/s` and the enthalpy's below `τ_E` for `n ≤ 3e10 mol/s`.
BETA_WIDTH_FLOOR: Final = 2.0**-60

#: K04 §5.1–§5.2's registered tolerance of a division-free equilibrium row `v_i L − K_i l_i V`,
#: `(mol/s)²`, written as the sum the registry states (the verifier's `EQUILIBRIUM_TOLERANCE`;
#: restated here because the unit layer does not import the verifier). T05b spec §5.3.
EQUILIBRIUM_TOLERANCE: Final = 1e-9 * 3.0 + 1e-8 * 9.0

Route = Literal["saturation", "bracket", "band"]

# ------------------------------------------------------------------------------------ kernel


@dataclass(frozen=True)
class PHState:
    """The kernel's answer.

    On `ok`: the temperature, the split at `(T*, P)` (the provider's flash on the bracket route,
    the lever rule on the saturation route, the band split at `β*` on the band route), the route
    taken, and the energy row's value in W. On any other status: the registered code, and no
    temperature and no split.
    """

    status: PropertyStatus
    code: str = ""
    temperature: float | None = None
    split: TPState | None = None
    route: Route | None = None
    #: Evaluations of the route's search function: `f(T)` on the bracket route (spec §4.4 step 4
    #: counts these, and only these), `F(β)` on the band route (T05b §5.2), none on the
    #: saturation route. A failure after both routes ran reports their sum.
    evaluations: int = 0
    #: `Hdot(split) - H*`, W.
    residual: float | None = None
    message: str = ""

    def __post_init__(self) -> None:
        if self.status == "ok":
            if self.temperature is None or self.split is None or self.route is None:
                raise ValueError("an ok PH state carries a temperature, a split and a route")
        elif self.temperature is not None or self.split is not None:
            raise ValueError(
                f"PH state status {self.status!r} carries a temperature or a split; a failed "
                "closure reports why and nothing an outlet could be built from"
            )


class _InnerFailureError(Exception):
    """A provider call inside the search failed; carries the answer the kernel returns."""

    def __init__(self, state: PHState) -> None:
        super().__init__(state.message)
        self.state = state


def _failed(status: PropertyStatus, code: str, detail: str = "", evaluations: int = 0) -> PHState:
    message = code if not detail else f"{code}\n{detail}"
    return PHState(status=status, code=code, evaluations=evaluations, message=message)


def _surfaced(status: PropertyStatus, what: str, detail: str, evaluations: int) -> PHState:
    """A provider refusal inside the kernel. The one the kernel can name is named."""
    if status == "not_converged":
        return _failed(status, "ph_not_converged", f"{what}: {detail}", evaluations)
    return PHState(status=status, evaluations=evaluations, message=f"{what}: {detail}")


# -------------------------------------------------------------- the acceptance (T05b §5.3)


@dataclass(frozen=True)
class _Rows:
    """The PH closure's rows at a candidate, as the largest absolute value of each kind."""

    material: float
    equilibrium: float
    energy: float

    @property
    def accepted(self) -> bool:
        # Written so that a NaN row is never accepted.
        return (
            self.material <= FLOW_TOLERANCE
            and self.equilibrium <= EQUILIBRIUM_TOLERANCE
            and self.energy <= ENERGY_TOLERANCE
        )

    def ratios(self) -> str:
        return (
            f"rows/tolerance: material {self.material / FLOW_TOLERANCE:.3g}, equilibrium "
            f"{self.equilibrium / EQUILIBRIUM_TOLERANCE:.3g}, energy "
            f"{self.energy / ENERGY_TOLERANCE:.3g}"
        )

    @property
    def worst(self) -> float:
        return max(
            self.material / FLOW_TOLERANCE,
            self.equilibrium / EQUILIBRIUM_TOLERANCE,
            self.energy / ENERGY_TOLERANCE,
        )


def _closure_rows(
    provider: PropertyProvider,
    n: tuple[float, ...],
    candidate: TPState,
    temperature: float,
    pressure: float,
    target: float,
    context: EvaluationContext,
) -> _Rows:
    """T05b §5.3: every material row, every equilibrium row `v_i L − K_i l_i V` and the energy
    row of the PH closure (T05 §4.3's EO rows) at the candidate, with `K_i` from the provider's
    `lnK` at `(T, P)` (one call; the flash's own report is not trusted) and the energy from the
    candidate's enthalpy — evaluated here, trusting no provider tolerance."""
    assert candidate.vapor is not None and candidate.liquid is not None
    components = provider.describe().components
    vapor, liquid = candidate.vapor.n, candidate.liquid.n
    result = provider.evaluate_phase(
        PropertyRequest(
            state=StreamState(n=n, temperature=temperature, pressure=pressure),
            phase="LIQUID",
            properties=("lnK",),
        ),
        context,
    )
    if result.status != "ok":
        raise _InnerFailureError(
            _surfaced(result.status, f"lnK at T = {temperature!r} K", result.message, 0)
        )
    total_vapor, total_liquid = sum(vapor), sum(liquid)
    material = equilibrium = 0.0
    for index, name in enumerate(components):
        k_value = math.exp(result.values[f"lnK_{name}"])
        material = max(material, abs(vapor[index] + liquid[index] - n[index]))
        equilibrium = max(
            equilibrium,
            abs(vapor[index] * total_liquid - k_value * liquid[index] * total_vapor),
        )
    # The energy row: the candidate's enthalpy is the kernel's own sum of the provider's `h` over
    # its two streams at `(T, P)` (`tp_state`'s total on the bracket route, the lever rule's or
    # the band's in this module), so it is not evaluated twice.
    assert candidate.enthalpy_flow is not None
    total = candidate.enthalpy_flow
    return _Rows(material, equilibrium, abs(total - target))


def _ill_conditioned(attempts: Sequence[tuple[str, float, _Rows]], evaluations: int) -> PHState:
    """No route's answer passed §5.3. The first line is the code; the later lines name the route
    that came closest (the smallest worst row ratio) and every route's row ratios."""
    closest = min(attempts, key=lambda attempt: attempt[2].worst)
    lines = [f"closest: the {closest[0]} route"]
    lines += [f"{route} route at T = {t!r} K: {rows.ratios()}" for route, t, rows in attempts]
    return _failed("not_converged", "ph_ill_conditioned", "\n".join(lines), evaluations)


def ph_state(
    provider: PropertyProvider,
    flows: Sequence[float],
    pressure: float,
    target: float,
    context: EvaluationContext,
    *,
    max_evaluations: int = MAX_EVALUATIONS,
) -> PHState:
    """Solve the PH closure `(n, P, H*)` on the provider's domain (T05 spec §4.4, T05b §5.1).

    `flows` must be flowing; a dormant stream is the caller's (spec §4.7). `max_evaluations` is
    the registered 200 and exists as a keyword only so the budget failure can be exercised; it
    bounds step 4's evaluations of `f` and, separately, step 2's `T_sat` bisection.
    """
    n = tuple(float(value) for value in flows)
    if sum(n) == 0.0:
        raise ValueError("ph_state is for a flowing stream; a dormant one is the caller's (§4.7)")
    capabilities = provider.describe()
    components = capabilities.components
    if len(n) != len(components):
        raise ValueError(
            f"stream carries {len(n)} component flows; the provider declares {len(components)}"
        )
    t_min, t_max = capabilities.domain["T"]
    p_min, p_max = capabilities.domain["P"]

    # Step 1.
    if not p_min <= pressure <= p_max:
        return _failed(
            "out_of_domain",
            "pressure_outside_domain(outlet)",
            f"P = {pressure!r} Pa outside [{p_min}, {p_max}] Pa",
        )

    lower_end, upper_end = t_min, t_max

    # Step 2: the saturation route, for exactly one flowing component.
    flowing = [index for index, value in enumerate(n) if value > 0.0]
    if len(flowing) == 1:
        saturation = _saturation_temperature(
            provider, n, pressure, components[flowing[0]], t_min, t_max, context, max_evaluations
        )
        if isinstance(saturation, PHState):
            return saturation
        if saturation is not None:
            outcome = _saturation_split(
                provider, n, pressure, target, saturation, flowing[0], context
            )
            if isinstance(outcome, PHState):
                return outcome
            lower_end, upper_end = outcome

    # Step 3: the temperature (bracket) route.
    def f(temperature: float) -> tuple[float, TPState]:
        state = tp_state(
            provider, StreamState(n=n, temperature=temperature, pressure=pressure), context
        )
        if state.status != "ok":
            raise _InnerFailureError(
                _surfaced(state.status, f"TP flash at T = {temperature!r} K", state.message, 0)
            )
        assert state.enthalpy_flow is not None
        return state.enthalpy_flow - target, state

    try:
        f_lo, state_lo = f(lower_end)
        f_hi, state_hi = f(upper_end)
        if f_lo > 0.0:
            return _failed(
                "out_of_domain",
                "ph_outside_domain(below)",
                f"Hdot_TP({lower_end!r} K) exceeds the target by {f_lo!r} W",
                2,
            )
        if f_hi < 0.0:
            return _failed(
                "out_of_domain",
                "ph_outside_domain(above)",
                f"the target exceeds Hdot_TP({upper_end!r} K) by {-f_hi!r} W",
                2,
            )
        # Step 4.
        root = bracketed_root(
            f,
            (lower_end, f_lo, state_lo),
            (upper_end, f_hi, state_hi),
            evaluations=2,
            budget=max_evaluations,
        )
        if not root.converged:
            return _failed(
                "not_converged",
                "ph_not_converged",
                f"the bracket did not close in {max_evaluations} evaluations",
                root.evaluations,
            )
        # Step 5 (T05b §5.3): the candidate is the bracket's better end with the provider's TP
        # split there (step 6); it is accepted on the closure's rows.
        rows = _closure_rows(provider, n, root.payload, root.point, pressure, target, context)
        if rows.accepted:
            return PHState(
                status="ok",
                temperature=root.point,
                split=root.payload,
                route="bracket",
                evaluations=root.evaluations,
                residual=root.value,
            )
        attempts: list[tuple[str, float, _Rows]] = [("bracket", root.point, rows)]
        evaluations = root.evaluations
        # T05b §5.1 step 4: the band route, only with at least two flowing components.
        if len(flowing) >= 2:
            band = _band_route(provider, n, pressure, target, context)
            if isinstance(band, PHState):
                return band
            if band is not None:
                answer, band_rows = band
                if band_rows.accepted:
                    return answer
                assert answer.temperature is not None
                attempts.append(("band", answer.temperature, band_rows))
                evaluations += answer.evaluations
        # T05b §5.1 step 5: no route's answer passed.
        return _ill_conditioned(attempts, evaluations)
    except _InnerFailureError as failure:
        return failure.state


# --------------------------------------------------------------- the band route (T05b §5.2)


def _band_route(
    provider: PropertyProvider,
    n: tuple[float, ...],
    pressure: float,
    target: float,
    context: EvaluationContext,
) -> tuple[PHState, _Rows] | PHState | None:
    """Bisection on `β ∈ [0, 1]` of `F(β) = H(β) − H*` (T05b spec §5.2).

    Returns the candidate (an `ok` state, not yet accepted) with its rows; `None` when the band
    route has no answer (the target outside the band, or only an end with an infinite `F`);
    a typed failure when a search exhausted its budget or the provider refused.
    """
    capabilities = provider.describe()
    components = capabilities.components

    def big_f(beta: float) -> tuple[float, tuple[float, TPState] | None]:
        at = band_temperature(provider, n, pressure, beta, context)
        if at.temperature is None:
            # The sign oracle: a band point below the domain carries less enthalpy than the
            # domain's end, which step 3 already found below the target; above, more.
            return (-math.inf if at.position == "below" else math.inf), None
        temperature = at.temperature
        vapor_n, liquid_n = band_split(n, at.k_values, beta)
        vapor = StreamState(n=vapor_n, temperature=temperature, pressure=pressure)
        liquid = StreamState(n=liquid_n, temperature=temperature, pressure=pressure)
        total = 0.0
        parts: tuple[tuple[Phase, StreamState], ...] = (("VAPOR", vapor), ("LIQUID", liquid))
        for phase, stream in parts:
            status, value, message = enthalpy_flow(provider, stream, phase, components, context)
            if status != "ok":
                raise _InnerFailureError(
                    _surfaced(status, f"{phase.lower()} enthalpy at beta = {beta!r}", message, 0)
                )
            total += value
        signature: PhaseSignature = "TWO_PHASE"
        if beta == 0.0:
            signature = "LIQUID"
        elif beta == 1.0:
            signature = "VAPOR"
        split = TPState(
            status="ok",
            phase_signature=signature,
            vapor=vapor,
            liquid=liquid,
            vapor_fraction=sum(vapor_n) / sum(n),
            enthalpy_flow=total,
            provider_id=capabilities.provider_id,
            reference_convention=capabilities.reference_convention,
        )
        return total - target, (temperature, split)

    try:
        f_lo, p_lo = big_f(0.0)
        f_hi, p_hi = big_f(1.0)
        if f_lo > 0.0 or f_hi < 0.0:
            return None
        root = bracketed_root(
            big_f,
            (0.0, f_lo, p_lo),
            (1.0, f_hi, p_hi),
            evaluations=2,
            budget=MAX_BAND_EVALUATIONS,
            min_width=BETA_WIDTH_FLOOR,
        )
    except BandError as error:
        return _surfaced(error.status, "band route", error.message, 0)
    if not root.converged:
        return _failed(
            "not_converged",
            "ph_not_converged",
            f"the band route's beta bracket did not close in {MAX_BAND_EVALUATIONS} evaluations",
            root.evaluations,
        )
    if root.payload is None:
        return None
    temperature, split = root.payload
    rows = _closure_rows(provider, n, split, temperature, pressure, target, context)
    answer = PHState(
        status="ok",
        temperature=temperature,
        split=split,
        route="band",
        evaluations=root.evaluations,
        residual=root.value,
    )
    return answer, rows


# ---------------------------------------------------------- the saturation route (step 2)


def _ln_k(
    provider: PropertyProvider,
    n: tuple[float, ...],
    temperature: float,
    pressure: float,
    component: str,
    context: EvaluationContext,
) -> float:
    result = provider.evaluate_phase(
        PropertyRequest(
            state=StreamState(n=n, temperature=temperature, pressure=pressure),
            phase="LIQUID",
            properties=("lnK",),
        ),
        context,
    )
    if result.status != "ok":
        raise _InnerFailureError(
            _surfaced(result.status, f"lnK at T = {temperature!r} K", result.message, 0)
        )
    return result.values[f"lnK_{component}"]


def _saturation_temperature(
    provider: PropertyProvider,
    n: tuple[float, ...],
    pressure: float,
    component: str,
    t_min: float,
    t_max: float,
    context: EvaluationContext,
    budget: int,
) -> float | PHState | None:
    """`T_sat` with `ln K_k(T_sat, P) = 0` by bisection, or `None` with no sign change.

    `ln K` is increasing in `T` (spec §4.2). This search is not an evaluation of `f`: it has its
    own budget of step 4's size, counted the same way (the two ends included), and exhausting it
    is `ph_not_converged` (spec §4.4 step 2 as amended, review N2). It closes in about 44 steps.
    """

    def g(temperature: float) -> tuple[float, None]:
        return _ln_k(provider, n, temperature, pressure, component, context), None

    try:
        g_lo, _ = g(t_min)
        g_hi, _ = g(t_max)
        if g_lo > 0.0 or g_hi < 0.0:
            return None
        root = bracketed_root(
            g, (t_min, g_lo, None), (t_max, g_hi, None), evaluations=2, budget=budget
        )
    except _InnerFailureError as failure:
        return failure.state
    if not root.converged:
        return _failed(
            "not_converged",
            "ph_not_converged",
            f"the T_sat bisection on ln K_{component} did not close in {budget} evaluations",
        )
    return root.point


def _saturation_split(
    provider: PropertyProvider,
    n: tuple[float, ...],
    pressure: float,
    target: float,
    saturation: float,
    flowing: int,
    context: EvaluationContext,
) -> PHState | tuple[float, float]:
    """Spec §4.4 step 2: the lever rule inside the jump, or the half-domain to bracket on."""
    components = provider.describe().components
    at_saturation = StreamState(n=n, temperature=saturation, pressure=pressure)
    enthalpies: dict[Phase, float] = {}
    phases: tuple[Phase, ...] = ("LIQUID", "VAPOR")
    for phase in phases:
        status, value, message = enthalpy_flow(provider, at_saturation, phase, components, context)
        if status != "ok":
            return _surfaced(status, f"{phase.lower()} enthalpy at T_sat", message, 0)
        enthalpies[phase] = value
    h_liquid, h_vapor = enthalpies["LIQUID"], enthalpies["VAPOR"]
    t_min, t_max = provider.describe().domain["T"]
    if target < h_liquid:
        return t_min, saturation
    if target > h_vapor:
        return saturation, t_max

    beta = (target - h_liquid) / (h_vapor - h_liquid)
    vapor_flow = beta * n[flowing]
    vapor = StreamState(
        n=tuple(vapor_flow if index == flowing else 0.0 for index in range(len(n))),
        temperature=saturation,
        pressure=pressure,
    )
    liquid = StreamState(
        n=tuple(n[flowing] - vapor_flow if index == flowing else 0.0 for index in range(len(n))),
        temperature=saturation,
        pressure=pressure,
    )
    signature: PhaseSignature = "TWO_PHASE"
    if beta == 0.0:
        signature = "LIQUID"
    elif beta == 1.0:
        signature = "VAPOR"
    total = 0.0
    parts: tuple[tuple[Phase, StreamState], ...] = (("VAPOR", vapor), ("LIQUID", liquid))
    for phase, stream in parts:
        status, value, message = enthalpy_flow(provider, stream, phase, components, context)
        if status != "ok":
            return _surfaced(status, f"{phase.lower()} enthalpy of the split", message, 0)
        total += value
    residual = total - target
    capabilities = provider.describe()
    split = TPState(
        status="ok",
        phase_signature=signature,
        vapor=vapor,
        liquid=liquid,
        vapor_fraction=beta,
        enthalpy_flow=total,
        provider_id=capabilities.provider_id,
        reference_convention=capabilities.reference_convention,
    )
    # T05b §5.3 applies to the lever-rule answer as to every route's (it replaces T05 review N2's
    # energy-only check). On SYN-001 the split's enthalpy is affine in `beta` and `ln K_k(T_sat)`
    # is zero to its last bit, so it holds by construction; it is checked. With one flowing
    # component there is no band route to fall back to (§5.1 step 4).
    try:
        rows = _closure_rows(provider, n, split, saturation, pressure, target, context)
    except _InnerFailureError as failure:
        return failure.state
    if not rows.accepted:
        return _ill_conditioned([("saturation", saturation, rows)], 0)
    return PHState(
        status="ok",
        temperature=saturation,
        split=split,
        route="saturation",
        residual=residual,
    )


# ------------------------------------------------------------ evaluator steps the units share


def typed_failure(status: PropertyStatus, code: str, detail: str = "") -> UnitEvaluation:
    """A non-`ok` `UnitEvaluation` whose message's first line is the registered `code` (§3.5)."""
    message = code if not detail else f"{code}\n{detail}"
    return UnitEvaluation(status=status, message=message, reference_convention=REFERENCE_CONVENTION)


def closure_failure(state: PHState) -> UnitEvaluation:
    """The unit's answer when the kernel did not return `ok`: the kernel's code, unchanged."""
    return UnitEvaluation(
        status=state.status, message=state.message, reference_convention=REFERENCE_CONVENTION
    )


@dataclass(frozen=True)
class PortEnthalpy:
    """A stream's enthalpy flow as the unit's rows write it, or the typed reason it has none."""

    status: PropertyStatus
    enthalpy_flow: float | None = None
    #: R-007's temperature-equivalent gap, K, for a declared phase; `None` for a lifted stream.
    admissibility: float | None = None
    failure: UnitEvaluation | None = None


def port_enthalpy(
    provider: PropertyProvider,
    stream: StreamState,
    phase: Phase | None,
    components: tuple[str, ...],
    context: EvaluationContext,
    *,
    port: str,
) -> PortEnthalpy:
    """Spec §5.2 step (3), shared by every T05 unit that reads a stream's enthalpy.

    A declared phase: R-007's admissibility criterion (K02's `single_phase_admissible`, the
    heater's and mixer's), then the single-phase enthalpy — the one the rows write, so the
    evaluator and the rows describe the same function (spec F7). A lifted stream (`phase` is
    `None`): the provider's TP state at the stream's own `(T, P)`, which is what the producer's
    lifted rows describe at their physical root.
    """
    if phase is not None:
        admissible, enthalpy, gap, status, message = single_phase_admissible(
            provider, stream, phase, components, context
        )
        if status != "ok":
            return PortEnthalpy(status=status, failure=_state_failure(status, port, message))
        if not admissible:
            return PortEnthalpy(
                status="unsupported",
                failure=typed_failure(
                    "unsupported",
                    f"inadmissible_phase({port}, {phase})",
                    f"writing the stream's enthalpy as {phase} would be wrong by {gap:.3g} K",
                ),
            )
        return PortEnthalpy(status="ok", enthalpy_flow=enthalpy, admissibility=gap)

    state = tp_state(provider, stream, context)
    if state.status != "ok":
        return PortEnthalpy(
            status=state.status, failure=_state_failure(state.status, port, state.message)
        )
    assert state.enthalpy_flow is not None
    return PortEnthalpy(status="ok", enthalpy_flow=state.enthalpy_flow)


def _state_failure(status: PropertyStatus, port: str, detail: str) -> UnitEvaluation:
    if status == "out_of_domain":
        return typed_failure(status, f"state_outside_domain({port})", detail)
    # A refusal the unit has no code for is surfaced with the provider's own status (§3.3).
    return UnitEvaluation(
        status=status, message=f"{port} state: {detail}", reference_convention=REFERENCE_CONVENTION
    )
