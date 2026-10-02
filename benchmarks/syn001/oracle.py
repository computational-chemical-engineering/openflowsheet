"""SYN-001 independent scalar oracle.

Implements `docs/derivations/SYN-001-oracle-spec.md` §1-§2 exactly, from the definitions of
implementation plan §3.1 and the algebra of `docs/derivations/SYN-001.md`. Semantics of units,
state, zero flow and duty signs are ADR 0001.

**Scope.** This is an algebraic reference for a synthetic model. It is not an experimental
validation, not a simulator benchmark result, and not the production flash/recycle solver
(implementation plan §3.2). It must never be imported by `openflowsheet` and imports nothing
from it; `tests/test_syn001_oracle.py::test_k_oracle_module_does_not_import_openflowsheet`
enforces that. No derivatives, no PH flash, no property caching, no mutable global state
(oracle specification §5).

Conventions used throughout (ADR 0001):

* Component flows `n` are in mol/s, ordered (A, B, C); `T` in K; `P` in Pa; duties in W.
* Duties are positive **into** the unit, so a heater duty may be negative (D4.1-D4.2).
* A stream with total flow exactly `0.0` is dormant: its composition is `None`, its enthalpy
  flow is exactly `0.0`, and its phase signature is `ZERO_FLOW` (D3.1). Nothing here divides by
  total flow before testing it against zero, and `log` is never applied to a composition (D3.2,
  D3.3).
* Signed zero is normalized to `+0.0` on input (D1.5).

The public names, dataclass fields and algorithms are fixed by the oracle specification. The
physical symbols (`T`, `P`, `K`, `V`, `L`, `Q_*`, `H_*`) are the derivation's symbols and are
deliberately not renamed to satisfy a naming lint; see the per-file ignore in `pyproject.toml`.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

__all__ = [
    "DomainError",
    "PhaseState",
    "RecycleOracleResult",
    "SYN001",
    "Syn001Constants",
    "TPFlashResult",
    "g_liquid",
    "g_vapor",
    "h_liquid",
    "h_vapor",
    "k_values",
    "linear_recycle",
    "recycle_oracle",
    "stream_enthalpy_flow",
    "tp_flash",
]

PhaseState = Literal["LIQUID", "VAPOR", "TWO_PHASE", "ZERO_FLOW"]
Phase = Literal["LIQUID", "VAPOR"]
Triple = tuple[float, float, float]

N_COMPONENTS = 3
COMPONENT_IDS: tuple[str, str, str] = ("A", "B", "C")

# Rachford-Rice termination (oracle specification §2.2): safeguarded Newton with a bisection
# fallback, converged on both the residual and the bracket width. The derivation §9 records
# RR'(beta*) ~ -0.56 at the nominal state, so |RR| <= 1e-15 corresponds to |dbeta| <~ 2e-15,
# a few ulp of beta. MAX_ITERATIONS is a guard, not a tolerance: exceeding it raises.
_RR_RESIDUAL_TOLERANCE = 1e-15
_RR_BRACKET_TOLERANCE = 1e-15
_RR_MAX_ITERATIONS = 200


@dataclass(frozen=True)
class Syn001Constants:
    """SYN-001 constants (implementation plan §3.1) and the declared test domain.

    `T_b` are reference boiling temperatures at `P_r`, `L` the vapor reference enthalpy offsets,
    `c_p` the (phase-independent) molar heat capacities, `v` the liquid molar volumes and `M` the
    molecular weights of the three synthetic pseudo-components. Outside
    `[T_min, T_max] x [P_min, P_max]` every property function raises `DomainError`; no
    critical-region or extra-phase claim is made.
    """

    R: float = 8.31446261815324
    T_r: float = 300.0
    P_r: float = 100_000.0
    c_p: Triple = (100.0, 100.0, 100.0)
    T_b: Triple = (320.0, 360.0, 400.0)
    L: Triple = (25_000.0, 30_000.0, 35_000.0)
    v: Triple = (1e-4, 1e-4, 1e-4)
    M: Triple = (0.100, 0.100, 0.100)
    T_min: float = 280.0
    T_max: float = 440.0
    P_min: float = 50_000.0
    P_max: float = 200_000.0


SYN001 = Syn001Constants()
"""The single registered SYN-001 constant set. Immutable; there is no global mutable state."""


class DomainError(ValueError):
    """`T` or `P` outside the declared SYN-001 domain. The message names the offending value."""


# --------------------------------------------------------------------------------------------
# Argument validation (ADR 0001 D1.5: nonfinite inputs are rejected; -0.0 normalizes to +0.0)
# --------------------------------------------------------------------------------------------


def _finite(name: str, value: float) -> float:
    if not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number, got {value!r}")
    return float(value)


def _normalize_zero(value: float) -> float:
    """ADR 0001 D1.5: -0.0 and +0.0 are the same state; canonical form is +0.0."""
    return 0.0 if value == 0.0 else value


def _check_state(T: float, P: float, c: Syn001Constants) -> None:
    """Reject nonfinite `T`/`P`, then the declared domain (oracle specification §2.1)."""
    _finite("T", T)
    _finite("P", P)
    if not (c.T_min <= T <= c.T_max):
        raise DomainError(
            f"T = {T!r} K is outside the declared SYN-001 domain [{c.T_min}, {c.T_max}] K"
        )
    if not (c.P_min <= P <= c.P_max):
        raise DomainError(
            f"P = {P!r} Pa is outside the declared SYN-001 domain [{c.P_min}, {c.P_max}] Pa"
        )


def _validated_flows(n: Sequence[float], name: str = "n") -> Triple:
    """Return `n` as three finite, non-negative floats with signed zeros normalized."""
    values = list(n)
    if len(values) != N_COMPONENTS:
        raise ValueError(f"{name} must have {N_COMPONENTS} component flows, got {len(values)}")
    out: list[float] = []
    for index, raw in enumerate(values):
        value = _finite(f"{name}[{index}]", float(raw))
        if value < 0.0:
            raise ValueError(
                f"{name}[{index}] = {raw!r} mol/s is negative; component molar flows are "
                "bounded below by 0 (ADR 0001 D2.3)"
            )
        out.append(_normalize_zero(value))
    return (out[0], out[1], out[2])


def _validated_ratio(r: float, name: str = "r") -> float:
    """Recycle ratio: 0 <= r < 1. `r >= 1` has no steady state and is rejected, not clipped."""
    value = _finite(name, r)
    if value < 0.0:
        raise ValueError(f"{name} = {r!r} is negative; the recycle fraction must satisfy 0 <= r")
    if value >= 1.0:
        raise ValueError(
            f"{name} = {r!r} is >= 1; the overall balance F = (1 - r) L x has no steady state"
        )
    return value


# --------------------------------------------------------------------------------------------
# Pure-component potentials and enthalpies (derivation §1-§2)
# --------------------------------------------------------------------------------------------


def _a(index: int, T: float, c: Syn001Constants) -> float:
    """a(T) = c_p [(T - T_r) - T ln(T/T_r)] (implementation plan §3.1)."""
    return c.c_p[index] * ((T - c.T_r) - T * math.log(T / c.T_r))


def g_liquid(T: float, P: float, c: Syn001Constants = SYN001) -> Triple:
    """Pure-component liquid molar Gibbs energies, J/mol: g_i^L = a(T) + v_i (P - P_r)."""
    _check_state(T, P, c)
    return (
        _a(0, T, c) + c.v[0] * (P - c.P_r),
        _a(1, T, c) + c.v[1] * (P - c.P_r),
        _a(2, T, c) + c.v[2] * (P - c.P_r),
    )


def _g_vapor_one(index: int, T: float, P: float, c: Syn001Constants) -> float:
    return (
        _a(index, T, c) + c.L[index] - T * c.L[index] / c.T_b[index] + c.R * T * math.log(P / c.P_r)
    )


def g_vapor(T: float, P: float, c: Syn001Constants = SYN001) -> Triple:
    """Vapor molar Gibbs energies: g_i^V = a(T) + L_i - T L_i/T_b,i + R T ln(P/P_r), J/mol."""
    _check_state(T, P, c)
    return (
        _g_vapor_one(0, T, P, c),
        _g_vapor_one(1, T, P, c),
        _g_vapor_one(2, T, P, c),
    )


def h_liquid(T: float, P: float, c: Syn001Constants = SYN001) -> Triple:
    """Liquid molar enthalpies, J/mol: h_i^L = c_p (T - T_r) + v_i (P - P_r) (derivation §2)."""
    _check_state(T, P, c)
    return (
        c.c_p[0] * (T - c.T_r) + c.v[0] * (P - c.P_r),
        c.c_p[1] * (T - c.T_r) + c.v[1] * (P - c.P_r),
        c.c_p[2] * (T - c.T_r) + c.v[2] * (P - c.P_r),
    )


def h_vapor(T: float, P: float, c: Syn001Constants = SYN001) -> Triple:
    """Vapor molar enthalpies, J/mol: h_i^V = c_p (T - T_r) + L_i (derivation §2).

    Pressure-independent by construction; `P` is still domain-checked.
    """
    _check_state(T, P, c)
    return (
        c.c_p[0] * (T - c.T_r) + c.L[0],
        c.c_p[1] * (T - c.T_r) + c.L[1],
        c.c_p[2] * (T - c.T_r) + c.L[2],
    )


def _k_one(index: int, T: float, P: float, c: Syn001Constants) -> float:
    return (
        c.P_r
        / P
        * math.exp(
            (c.L[index] / c.R) * (1.0 / c.T_b[index] - 1.0 / T)
            + c.v[index] * (P - c.P_r) / (c.R * T)
        )
    )


def k_values(T: float, P: float, c: Syn001Constants = SYN001) -> Triple:
    """K_i(T, P) = (P_r/P) exp[(L_i/R)(1/T_b,i - 1/T) + v_i (P - P_r)/(R T)] (derivation §3).

    Composition-independent (ideal mixing in both phases), so `y_i = K_i x_i` never evaluates
    `ln 0` for an absent component (ADR 0001 D3.3). Evaluated exactly as written; no caching.
    """
    _check_state(T, P, c)
    return (_k_one(0, T, P, c), _k_one(1, T, P, c), _k_one(2, T, P, c))


def stream_enthalpy_flow(
    n: Sequence[float],
    T: float,
    P: float,
    phase: Phase,
    c: Syn001Constants = SYN001,
) -> float:
    """Enthalpy flow of a single-phase stream, W: Hdot = sum_i n_i h_i^phase(T, P).

    Linear in the component flows, so exact zeros pass straight through. A dormant stream
    (every `n_i` exactly zero) returns exactly `0.0` and no property is evaluated for it
    (ADR 0001 D3.1); its `T` and `P` remain labels and are not domain-checked.
    """
    flows = _validated_flows(n)
    if phase not in ("LIQUID", "VAPOR"):
        raise ValueError(f"phase must be 'LIQUID' or 'VAPOR', got {phase!r}")
    if flows == (0.0, 0.0, 0.0):
        return 0.0
    h = h_liquid(T, P, c) if phase == "LIQUID" else h_vapor(T, P, c)
    return _normalize_zero(math.fsum(flows[i] * h[i] for i in range(N_COMPONENTS)))


# --------------------------------------------------------------------------------------------
# Isothermal-isobaric flash (derivation §5.1, oracle specification §2.2)
# --------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class TPFlashResult:
    """Result of one TP flash. `x`/`y` are `None` when the corresponding phase has zero flow."""

    state: PhaseState
    beta: float
    V: float
    L: float
    vapor: Triple
    liquid: Triple
    x: Triple | None
    y: Triple | None
    K: Triple
    sum_zK: float
    sum_z_over_K: float
    rr_residual: float
    iterations: int


def _rachford_rice(beta: float, z: Triple, K: Triple, active: tuple[int, ...]) -> float:
    """RR(beta) = sum_{i in A} z_i (K_i - 1) / (1 + beta (K_i - 1)); strictly decreasing."""
    return math.fsum(z[i] * (K[i] - 1.0) / (1.0 + beta * (K[i] - 1.0)) for i in active)


def _rachford_rice_prime(beta: float, z: Triple, K: Triple, active: tuple[int, ...]) -> float:
    return -math.fsum(z[i] * (K[i] - 1.0) ** 2 / (1.0 + beta * (K[i] - 1.0)) ** 2 for i in active)


def _solve_rachford_rice(z: Triple, K: Triple, active: tuple[int, ...]) -> tuple[float, float, int]:
    """Safeguarded Newton with bisection fallback. Returns (beta, RR(beta), iterations).

    The bracket is (max(0, 1/(1 - K_max,A)), min(1, 1/(1 - K_min,A))) over the **active** set
    only; an absent component never takes part in bracket selection (derivation §5.1). A
    bisection step is forced whenever the Newton candidate leaves the bracket or the previous
    step failed to halve it, so the bracket width is guaranteed to shrink geometrically.
    """
    k_active = [K[i] for i in active]
    k_max = max(k_active)
    k_min = min(k_active)
    if k_max <= 1.0 or k_min >= 1.0:
        raise RuntimeError(
            "two-phase branch entered with a degenerate K spread over the active set: "
            f"K_max = {k_max!r}, K_min = {k_min!r}"
        )
    lo = max(0.0, 1.0 / (1.0 - k_max))
    hi = min(1.0, 1.0 / (1.0 - k_min))
    f_lo = _rachford_rice(lo, z, K, active)
    f_hi = _rachford_rice(hi, z, K, active)
    if not (f_lo > 0.0 > f_hi):
        raise RuntimeError(
            "Rachford-Rice bracket does not straddle a root: "
            f"RR({lo!r}) = {f_lo!r}, RR({hi!r}) = {f_hi!r}"
        )

    beta = 0.5 * (lo + hi)
    previous_width = hi - lo
    iterations = 0
    while True:
        iterations += 1
        residual = _rachford_rice(beta, z, K, active)
        if residual > 0.0:
            lo = beta
        elif residual < 0.0:
            hi = beta
        else:
            lo = beta
            hi = beta
        width = hi - lo
        if abs(residual) <= _RR_RESIDUAL_TOLERANCE and width <= _RR_BRACKET_TOLERANCE:
            return beta, residual, iterations
        if iterations >= _RR_MAX_ITERATIONS:
            raise RuntimeError(
                f"Rachford-Rice did not converge in {_RR_MAX_ITERATIONS} iterations: "
                f"beta = {beta!r}, RR = {residual!r}, bracket width = {width!r}"
            )
        force_bisection = width > 0.5 * previous_width
        previous_width = width
        derivative = _rachford_rice_prime(beta, z, K, active)
        candidate = beta - residual / derivative if derivative < 0.0 else math.nan
        beta = candidate if (not force_bisection and lo < candidate < hi) else 0.5 * (lo + hi)


def tp_flash(n: Sequence[float], T: float, P: float, c: Syn001Constants = SYN001) -> TPFlashResult:
    """Isothermal-isobaric flash of `n` at `(T, P)` (oracle specification §2.2).

    Classification order is liquid test, then vapor test, then two-phase; derivation §5.1 proves
    it unambiguous on the SYN-001 domain (Cauchy-Schwarz gives (sum zK)(sum z/K) >= 1 with
    equality only if all K_i are equal, which never happens here). Compositions are reported as
    computed and are never renormalized.
    """
    flows = _validated_flows(n)
    K = k_values(T, P, c)

    total = math.fsum(flows)
    if total == 0.0:
        # ADR 0001 D3.1: dormant stream. Composition undefined; nothing divides by `total`.
        return TPFlashResult(
            state="ZERO_FLOW",
            beta=math.nan,
            V=0.0,
            L=0.0,
            vapor=(0.0, 0.0, 0.0),
            liquid=(0.0, 0.0, 0.0),
            x=None,
            y=None,
            K=K,
            sum_zK=math.nan,
            sum_z_over_K=math.nan,
            rr_residual=0.0,
            iterations=0,
        )

    z: Triple = (flows[0] / total, flows[1] / total, flows[2] / total)
    active = tuple(i for i in range(N_COMPONENTS) if flows[i] > 0.0)
    sum_zK = math.fsum(z[i] * K[i] for i in active)
    sum_z_over_K = math.fsum(z[i] / K[i] for i in active)

    if sum_zK <= 1.0:
        return TPFlashResult(
            state="LIQUID",
            beta=0.0,
            V=0.0,
            L=total,
            vapor=(0.0, 0.0, 0.0),
            liquid=flows,
            x=z,
            y=None,
            K=K,
            sum_zK=sum_zK,
            sum_z_over_K=sum_z_over_K,
            rr_residual=0.0,
            iterations=0,
        )
    if sum_z_over_K <= 1.0:
        return TPFlashResult(
            state="VAPOR",
            beta=1.0,
            V=total,
            L=0.0,
            vapor=flows,
            liquid=(0.0, 0.0, 0.0),
            x=None,
            y=z,
            K=K,
            sum_zK=sum_zK,
            sum_z_over_K=sum_z_over_K,
            rr_residual=0.0,
            iterations=0,
        )

    beta, rr_residual, iterations = _solve_rachford_rice(z, K, active)
    x_list = [
        z[i] / (1.0 + beta * (K[i] - 1.0)) if i in active else 0.0 for i in range(N_COMPONENTS)
    ]
    y_list = [K[i] * x_list[i] if i in active else 0.0 for i in range(N_COMPONENTS)]
    x: Triple = (x_list[0], x_list[1], x_list[2])
    y: Triple = (y_list[0], y_list[1], y_list[2])
    V = beta * total
    L = total - V
    return TPFlashResult(
        state="TWO_PHASE",
        beta=beta,
        V=V,
        L=L,
        vapor=(V * y[0], V * y[1], V * y[2]),
        liquid=(L * x[0], L * x[1], L * x[2]),
        x=x,
        y=y,
        K=K,
        sum_zK=sum_zK,
        sum_z_over_K=sum_z_over_K,
        rr_residual=rr_residual,
        iterations=iterations,
    )


# --------------------------------------------------------------------------------------------
# The SYN-001 recycle flowsheet (derivation §4-§7, oracle specification §2.3)
# --------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class RecycleOracleResult:
    """Algebraic reference for one registered SYN-001 flowsheet case.

    `flash` is a single TP flash of the **fresh** feed: derivation §5.1 shows the closed loop
    reduces to it, so the external split (vapor product and purge) is read straight off it and
    is independent of `r`. Duties are positive into the unit (ADR 0001 D4.1). `balance_residual`
    and `energy_residual` are computed here and asserted by the tests, never inside the oracle.
    """

    case_id: str
    r: float
    T_flash: float
    T_heater: float
    P: float
    flash: TPFlashResult
    q: float | None
    recycle: Triple
    purge: Triple
    vapor_product: Triple
    recycle_state: PhaseState
    purge_state: PhaseState
    vapor_product_state: PhaseState
    mixed_feed: Triple
    T_mix: float
    mixer_outlet_state: PhaseState
    sum_zK_at_T_mix: float
    heater_outlet: TPFlashResult
    Q_heater: float
    Q_flash: float
    H_fresh: float
    H_recycle: float
    H_mixed: float
    H_heater_out: float
    H_flash_out: float
    H_products: float
    balance_residual: Triple
    energy_residual: float


def recycle_oracle(
    F: Sequence[float],
    r: float,
    T_flash: float,
    *,
    T_heater: float = 350.0,
    P: float = 100_000.0,
    T_feed: float = 300.0,
    case_id: str = "",
    c: Syn001Constants = SYN001,
) -> RecycleOracleResult:
    """Direct reference for the SYN-001 flash-recycle loop (derivation §5-§7).

    The fresh feed is liquid at `(T_feed, P)`, the mixer is adiabatic, the heater has a TP-state
    outlet at `T_heater`, the flash is isothermal-isobaric at `(T_flash, P)` and the splitter
    sends fraction `r` of the flash liquid back to the mixer. All pressure drops and shaft work
    are zero. This bypasses the iterative flowsheet traversal entirely; it is not the production
    solver.
    """
    fresh = _validated_flows(F, "F")
    ratio = _validated_ratio(r)
    _finite("T_flash", T_flash)
    _finite("T_heater", T_heater)
    _finite("T_feed", T_feed)
    _finite("P", P)

    flash = tp_flash(fresh, T_flash, P, c)
    _check_state(T_heater, P, c)
    _check_state(T_feed, P, c)

    vapor_product = flash.vapor
    purge = flash.liquid
    factor = ratio / (1.0 - ratio)
    recycle: Triple = (
        _normalize_zero(factor * purge[0]),
        _normalize_zero(factor * purge[1]),
        _normalize_zero(factor * purge[2]),
    )

    fresh_total = math.fsum(fresh)
    recycle_total = math.fsum(recycle)
    purge_total = math.fsum(purge)
    vapor_total = math.fsum(vapor_product)
    liquid_total = purge_total + recycle_total
    q = flash.V / liquid_total if liquid_total > 0.0 else None

    recycle_state: PhaseState = "ZERO_FLOW" if recycle_total == 0.0 else "LIQUID"
    purge_state: PhaseState = "ZERO_FLOW" if purge_total == 0.0 else "LIQUID"
    vapor_product_state: PhaseState = "ZERO_FLOW" if vapor_total == 0.0 else "VAPOR"

    mixed_feed: Triple = (
        fresh[0] + recycle[0],
        fresh[1] + recycle[1],
        fresh[2] + recycle[2],
    )

    # Adiabatic mixer, analytic closure (derivation §4.1). It is valid only because both inlets
    # are liquid with equal c_p at the same P; the precondition is checked, never assumed.
    if recycle_state == "ZERO_FLOW":
        T_mix = T_feed
    else:
        if flash.L <= 0.0:
            raise ValueError(
                "a flowing recycle requires a flowing flash liquid; "
                f"flash state is {flash.state} with L = {flash.L!r} mol/s"
            )
        feed_state = tp_flash(fresh, T_feed, P, c).state
        if feed_state not in ("LIQUID", "ZERO_FLOW"):
            raise ValueError(
                "the analytic mixer temperature assumes a liquid fresh feed, but the feed is "
                f"{feed_state} at T_feed = {T_feed!r} K (the v0.0 mixer is restricted to the "
                "subcooled-liquid domain, implementation plan §3.2)"
            )
        T_mix = (fresh_total * T_feed + recycle_total * T_flash) / (fresh_total + recycle_total)

    mixer_flash = tp_flash(mixed_feed, T_mix, P, c)
    heater_outlet = tp_flash(mixed_feed, T_heater, P, c)

    H_fresh = stream_enthalpy_flow(fresh, T_feed, P, "LIQUID", c)
    H_recycle = stream_enthalpy_flow(recycle, T_flash, P, "LIQUID", c)
    H_mixed = H_fresh + H_recycle
    H_heater_out = stream_enthalpy_flow(
        heater_outlet.vapor, T_heater, P, "VAPOR", c
    ) + stream_enthalpy_flow(heater_outlet.liquid, T_heater, P, "LIQUID", c)
    flash_liquid: Triple = (
        recycle[0] + purge[0],
        recycle[1] + purge[1],
        recycle[2] + purge[2],
    )
    H_vapor_product = stream_enthalpy_flow(vapor_product, T_flash, P, "VAPOR", c)
    H_flash_out = H_vapor_product + stream_enthalpy_flow(flash_liquid, T_flash, P, "LIQUID", c)
    H_products = H_vapor_product + stream_enthalpy_flow(purge, T_flash, P, "LIQUID", c)

    Q_heater = H_heater_out - H_mixed
    Q_flash = H_flash_out - H_heater_out

    return RecycleOracleResult(
        case_id=case_id,
        r=ratio,
        T_flash=T_flash,
        T_heater=T_heater,
        P=P,
        flash=flash,
        q=q,
        recycle=recycle,
        purge=purge,
        vapor_product=vapor_product,
        recycle_state=recycle_state,
        purge_state=purge_state,
        vapor_product_state=vapor_product_state,
        mixed_feed=mixed_feed,
        T_mix=T_mix,
        mixer_outlet_state=mixer_flash.state,
        sum_zK_at_T_mix=mixer_flash.sum_zK,
        heater_outlet=heater_outlet,
        Q_heater=Q_heater,
        Q_flash=Q_flash,
        H_fresh=H_fresh,
        H_recycle=H_recycle,
        H_mixed=H_mixed,
        H_heater_out=H_heater_out,
        H_flash_out=H_flash_out,
        H_products=H_products,
        balance_residual=(
            fresh[0] - vapor_product[0] - purge[0],
            fresh[1] - vapor_product[1] - purge[1],
            fresh[2] - vapor_product[2] - purge[2],
        ),
        energy_residual=Q_heater + Q_flash - (H_products - H_fresh),
    )


def linear_recycle(f: Sequence[float], r: float) -> tuple[float, ...]:
    """Analytic linear recycle t = f + r t, solution t = f/(1 - r) (derivation §8).

    Isolates tear-solver behavior from the flash (implementation plan §3.3; case NUM-02).
    """
    ratio = _validated_ratio(r)
    values = [_finite(f"f[{index}]", float(raw)) for index, raw in enumerate(f)]
    return tuple(value / (1.0 - ratio) for value in values)
